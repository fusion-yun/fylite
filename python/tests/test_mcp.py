"""``fylite mcp`` + LLM tool emission + result shaping (SP-REPORT-15 route A/B/C).

Covers the MCP stdio server (initialize / tools/list / tools/call, notification
silence, error mapping), the reflection contract (reflected tools ≡ manifest
catalog — never hand-copied), the Anthropic/OpenAI schema adapters, and the
``engine.summarize`` by-reference result shaping.
"""
from __future__ import annotations

import io
import json

import pytest
import pathlib
import subprocess
import sys

import numpy as np

from fylite import engine

VERSION = engine.manifest_catalog()["fylite:version"]

REPO = pathlib.Path(__file__).resolve().parents[2]


def _req(method, params=None, rid=1):
    r = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        r["params"] = params
    return r


# --------------------------------------------------------------------------- #
# protocol surface
# --------------------------------------------------------------------------- #

def test_initialize_reports_tools_capability():
    resp = engine.handle_mcp_message(_req("initialize",
                                   {"protocolVersion": "2025-06-18"}))
    result = resp["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert "tools" in result["capabilities"]
    assert result["serverInfo"] == {"name": "fylite",
                                    "version": VERSION}


def test_notifications_get_no_reply():
    note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert engine.handle_mcp_message(note) is None


def test_unknown_method_and_tool_are_jsonrpc_errors():
    assert engine.handle_mcp_message(_req("nope"))["error"]["code"] == -32601
    resp = engine.handle_mcp_message(_req("tools/call", {"name": "fylite_nope",
                                                  "arguments": {}}))
    assert resp["error"]["code"] == -32602


def test_tools_list_is_curated_plus_reflected():
    resp = engine.handle_mcp_message(_req("tools/list"))
    names = [t["name"] for t in resp["result"]["tools"]]
    curated = ["fylite_describe", "fylite_run", "fylite_inspect",
               "fylite_open", "fylite_gaps", "fylite_plot"]
    assert names[:len(curated)] == curated
    #: reflection contract: exactly one tool per EXECUTABLE manifest.  A
    #: published capability that cannot be called (a workflow template whose
    #: entry does not bind) stays in the catalog and off the face — a tool a
    #: model can select and cannot run costs it a turn and teaches it the
    #: wrong thing about this package.
    docs = engine.load_manifests()
    assert set(names[len(curated):]) == {
        f"fylite_{n}" for n, d in docs.items()
        if d.get("fylite:executable") is not False}
    for t in resp["result"]["tools"]:
        assert t["inputSchema"]["type"] == "object"


def test_describe_tool_returns_the_catalog():
    resp = engine.handle_mcp_message(_req("tools/call",
                                   {"name": "fylite_describe"}))
    result = resp["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload == json.loads(json.dumps(engine.manifest_catalog()))


def test_inspect_tool_reads_a_jsonld_document():
    resp = engine.handle_mcp_message(_req("tools/call", {
        "name": "fylite_inspect",
        "arguments": {"path": str(engine.MANIFEST_DIR / "efit.jsonld"),
                      "keys": ["@id", "fylite:version"]}}))
    payload = json.loads(resp["result"]["content"][0]["text"])
    #: ★compare against THIS manifest's own version, not the catalogue's.
    #: They happened to be equal while every manifest sat at 0.1.0, so the
    #: test read the catalogue and nobody noticed the substitution — until
    #: the reconstruction entry moved to the Rust inverse and was bumped
    #: alone, at which point the assertion was comparing two different
    #: documents' versions and calling the difference a failure.
    import json as _json
    _efit = _json.loads((pathlib.Path(engine.__file__).resolve().parent.parent
                         / "_manifest" / "efit.jsonld").read_text())
    assert payload == {"@id": "fylite:efit",
                       "fylite:version": _efit["fylite:version"]}


def test_execution_failure_is_an_iserror_result_not_a_crash():
    resp = engine.handle_mcp_message(_req("tools/call", {
        "name": "fylite_inspect", "arguments": {"path": "/no/such/file.json"}}))
    result = resp["result"]
    assert result["isError"] is True
    err = json.loads(result["content"][0]["text"])
    assert err["error"] == "FileNotFoundError"


def test_reflected_tool_dispatch_resolves_manifest_entries():
    for name in engine.load_manifests():
        entry = engine.mcp_entry_for_tool(f"fylite_{name}")
        assert callable(engine.resolve_entry(entry))


def test_main_loop_serves_lines_and_skips_notifications():
    lines = "\n".join([
        json.dumps(_req("initialize", {"protocolVersion": "x"})),
        json.dumps({"jsonrpc": "2.0",
                    "method": "notifications/initialized"}),
        json.dumps(_req("tools/list", rid=2)),
        "garbage",
    ]) + "\n"
    out = io.StringIO()
    assert engine.mcp_stdio(stdin=io.StringIO(lines), stdout=out) == 0
    r1, r2, r3 = [json.loads(x) for x in out.getvalue().splitlines()]
    assert r1["result"]["serverInfo"]["name"] == "fylite"
    assert r2["id"] == 2 and "tools" in r2["result"]
    assert r3["error"]["code"] == -32700


# --------------------------------------------------------------------------- #
# route C — schema emission
# --------------------------------------------------------------------------- #

def test_llm_tools_reflect_entry_signatures():
    tools = {t["name"]: t for t in engine.llm_tools()}
    assert set(tools) == {f"fylite_{n}" for n, d in engine.load_manifests().items()
                          if d.get("fylite:executable") is not False}
    neo = tools["fylite_neo"]["input_schema"]
    assert "species" in neo["properties"]
    assert "species" in neo["required"]           # no default in the signature
    assert "shift" not in neo.get("required", []) # has a default
    assert "fyo:core_profiles" in tools["fylite_neo"]["description"]


def test_reflected_schemas_carry_types():
    """★★They did not: every property was a bare description reading
    ``parameter 'inputs' of …``, so a model calling the tool had to guess
    whether a parameter was a number, a name or a whole deck."""
    tools = {t["name"]: t for t in engine.llm_tools()}
    tglf = tools["fylite_tglf"]["input_schema"]["properties"]
    assert tglf["sat_rule"]["type"] == "integer"
    assert tglf["fluxes"]["type"] == "boolean"
    #: bulk data advertises the handle form beside its own type
    assert [b.get("type") for b in tglf["inputs"]["anyOf"]] == ["object",
                                                               "object"]
    assert tglf["inputs"]["anyOf"][1]["required"] == ["$ref"]
    #: an unannotated parameter says so rather than looking like a blank
    assert "[TBD]" in tglf["ky"]["description"]


def test_no_required_parameter_is_untyped():
    """★★A caller can omit an optional parameter it does not understand; it
    cannot omit a required one.  Measured before this: ``fylite_neo``'s FIVE
    required parameters and ``fylite_vstab``'s two carried no type at all, so
    the only way to learn whether ``species`` was a number, a name or a list
    of dicts was to call and read the ``TypeError``."""
    untyped = [f"{t['name']}.{n}"
               for t in engine.llm_tools()
               for n in t["input_schema"].get("required", [])
               if "type" not in t["input_schema"]["properties"][n]
               and "anyOf" not in t["input_schema"]["properties"][n]]
    assert not untyped, (
        f"required parameters with no declared type: {untyped} — annotate "
        "them at the source; the schema is reflected, not written")


def test_every_reflected_schema_is_valid_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    for t in engine.llm_tools():
        jsonschema.Draft202012Validator.check_schema(t["input_schema"])


def test_a_typed_schema_admits_a_handle_where_it_says_it_does():
    jsonschema = pytest.importorskip("jsonschema")
    schema = {t["name"]: t for t in
              engine.llm_tools()}["fylite_tglf"]["input_schema"]
    jsonschema.Draft202012Validator(schema).validate(
        {"inputs": {"$ref": "fylite://r-1/deck"}, "sat_rule": 2})
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate({"inputs": 3.0})


def test_anthropic_and_openai_adapters():
    t = engine.llm_tools()[0]
    a = engine.to_anthropic_tool(t)
    assert set(a) == {"name", "description", "input_schema"}
    o = engine.to_openai_tool(t)
    assert o["type"] == "function"
    assert o["function"]["parameters"] == t["input_schema"]


# --------------------------------------------------------------------------- #
# result shaping
# --------------------------------------------------------------------------- #

def test_an_execution_error_is_not_reported_as_an_unknown_tool():
    """★★``fylite_tglf`` with an incomplete deck raises ``KeyError('NS')``.
    That used to escape the execution guard as the protocol's "unknown tool"
    error — word for word what a caller is told about a tool that does not
    exist — so a model would conclude the capability was absent and stop
    asking for it."""
    result = engine.call_mcp_tool("fylite_tglf", {"inputs": {}})
    assert result["isError"] is True
    err = json.loads(result["content"][0]["text"])
    assert err["error"] == "KeyError" and "NS" in err["message"]
    with pytest.raises(KeyError):                 # a name that really is not there
        engine.call_mcp_tool("fylite_nosuch", {})


def test_a_published_but_uncallable_capability_says_which_it_is(monkeypatch):
    """★"published and not callable" is a different fact from "no such tool",
    and the caller can only act on the difference if it is told.

    ★★Checked against a manifest marked here rather than against whichever
    capability happens to be broken today: the mechanism has to work when
    the register is EMPTY, which is exactly when a defect-dependent test
    would stop testing it.  (It was defect-dependent for one day — the
    kinetic loop's — and that defect is fixed.)
    """
    from fylite.engine import serve
    docs = dict(engine.load_manifests())
    name, doc = "tglf", dict(docs["tglf"])
    doc["fylite:executable"] = False
    doc["fylite:executable_note"] = "held for a reason a caller can read"
    docs[name] = doc
    #: ★BOTH bindings: `serve` imported the name at import time (it decides
    #: the NotExecutable message), while `llm_tools` — which decides whether
    #: the tool is on the face at all — calls the one in `manifest`.  Patching
    #: only one made the earlier draft pass for the wrong reason.
    monkeypatch.setattr(serve, "load_manifests", lambda *a, **k: docs)
    monkeypatch.setattr("fylite.engine.manifest.load_manifests",
                        lambda *a, **k: docs)
    assert f"fylite_{name}" not in {t["name"] for t in serve.list_mcp_tools()}
    result = serve.call_mcp_tool(f"fylite_{name}", {"inputs": {}})
    assert result["isError"] is True
    err = json.loads(result["content"][0]["text"])
    assert err["error"] == "NotExecutable"
    assert "a caller can read" in err["message"]


def test_summarize_replaces_bulk_arrays_with_typed_summaries():
    arr = np.linspace(0.0, 1.0, 100)
    out = engine.summarize({"psi": arr, "q0": 1.02, "gfile": "/tmp/g1"})
    assert out["q0"] == 1.02 and out["gfile"] == "/tmp/g1"
    s = out["psi"]
    assert s["@type"] == "fylite:ArraySummary"
    assert s["shape"] == [100] and s["min"] == 0.0 and s["max"] == 1.0
    assert len(s["sha256"]) == 64
    json.dumps(out)  # JSON-clean


def test_summarize_keeps_short_scalar_lists_inline():
    out = engine.summarize({"few": [1, 2, 3], "many": list(range(100))})
    assert out["few"] == [1, 2, 3]
    assert out["many"]["@type"] == "fylite:ArraySummary"


def test_non_finite_numbers_travel_as_json():
    """★``json.dumps`` writes ``Infinity`` / ``NaN``, which are not JSON —
    a strict client rejects the whole message.  ``vstab`` reports an infinite
    margin for a stable equilibrium, so this is the normal case, not an edge
    one."""
    shaped = engine.summarize({"margin": float("inf"), "t": float("nan"),
                               "lo": float("-inf"), "q": 3.0})
    assert shaped == {"margin": "Infinity", "t": "NaN", "lo": "-Infinity",
                      "q": 3.0}
    text = json.dumps(shaped)
    json.loads(text, parse_constant=lambda c: pytest.fail(
        f"not JSON: {c}"))


def test_json_sanitize_is_json_too():
    out = engine.json_sanitize({"a": np.array([1.0, np.inf, np.nan])})
    assert out == {"a": [1.0, "Infinity", "NaN"]}
    json.loads(json.dumps(out), parse_constant=lambda c: pytest.fail(c))


def test_summarize_digest_matches_bytes():
    import hashlib
    arr = np.arange(5.0)
    s = engine.summarize(arr)
    assert s["sha256"] == hashlib.sha256(arr.tobytes()).hexdigest()
