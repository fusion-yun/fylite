"""The session ledger, the response envelope, and the records face (L-6).

★★A conversation is not a record: it is summarised, truncated and re-opened.
What a session actually produces — if anything is to survive it — is a
sequence of recorded runs and the data dependencies between them, which is a
DAG, which this ecosystem already has a normative document type for.  So the
ledger is a ``workflow-ir/2.0`` **instance**, appended to as the session goes,
and the edges are DERIVED from the handles each call was given: a handle names
the run it came from, so nobody has to declare the data flow.

What is gated here: that the document is valid and sealed, that lineage is
read off the calls, that a session cannot be mistaken for a registered
workflow, and that the two things a caller needs before calling — the response
tier and the reduced-tier caveat — are actually on the catalog.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fylite import engine
from fylite.engine import handles, ledger, serve


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setenv(handles.RUN_ENV, str(tmp_path / "runs"))
    monkeypatch.setenv(handles.SESSION_ENV, "s-ledger")
    return tmp_path / "runs" / "s-ledger"


def _call(name, args):
    r = serve.call_mcp_tool(name, args)
    assert r["isError"] is False, r["content"][0]["text"]
    return json.loads(r["content"][0]["text"])


def _doc(session) -> dict:
    return json.loads((session / "ledger.jsonld").read_text())


# --------------------------------------------------------------------------- #
# the ledger is a workflow instance
# --------------------------------------------------------------------------- #

def test_a_recorded_run_appends_a_node(session):
    p = _call("fylite_zerod", {})
    dag = _doc(session)["fylite:projection"]["dag"]
    assert [n["id"] for n in dag["nodes"]] == [p["run"]]
    node = dag["nodes"][0]
    assert node["display_name"] == "fylite_zerod"
    assert node["artifact_ref"]["artifact_id"].endswith("/zerod")
    assert node["attrs"]["manifest"].endswith("manifest.json")


def test_the_edges_are_read_off_the_handles(session):
    """★Nobody declares the data flow: a handle names the run it came from,
    so the edge is derivable — and derived is the only kind that cannot be
    forgotten."""
    a = _call("fylite_zerod", {})
    b = _call("fylite_transport", {"power": 4.0,
                                   "y_init": {"$ref": a["te"]["ref"]}})
    dag = _doc(session)["fylite:projection"]["dag"]
    assert dag["edges"] == [{"id": "e1", "source_node": a["run"],
                             "source_port": "te", "target_node": b["run"],
                             "target_port": "y_init"}]


def test_the_lineage_survives_the_clock(monkeypatch, tmp_path):
    """★★The measured regression, kept as a case: one process, two calls, the
    clock moving between them.  Before the session id was fixed per process
    this produced two session directories, two one-node ledgers and NO edge —
    the numbers were right and the only thing wrong was the record, which is
    what the ledger exists for."""
    monkeypatch.setenv(handles.RUN_ENV, str(tmp_path / "runs"))
    monkeypatch.delenv(handles.SESSION_ENV, raising=False)
    monkeypatch.setattr(handles, "_SESSION", None)
    ticks = iter([f"20260825-0000{i:02d}" for i in range(1, 20)])
    monkeypatch.setattr(handles, "_stamp", lambda: next(ticks))

    a = _call("fylite_zerod", {})
    b = _call("fylite_transport", {"power": 4.0,
                                   "y_init": {"$ref": a["te"]["ref"]}})
    sessions = sorted(p.name for p in (tmp_path / "runs").iterdir())
    assert len(sessions) == 1, f"the session fragmented: {sessions}"
    dag = json.loads((tmp_path / "runs" / sessions[0]
                      / "ledger.jsonld").read_text())["fylite:projection"]["dag"]
    assert len(dag["nodes"]) == 2
    assert [(e["source_node"], e["target_node"]) for e in dag["edges"]] == [
        (a["run"], b["run"])]


def test_the_instance_validates_and_stays_sealed(session):
    pytest.importorskip("jsonschema")
    _call("fylite_zerod", {})
    _call("fylite_transport", {"power": 4.0})
    doc = _doc(session)
    engine.validate_projection(doc)
    assert engine.seal_manifest(doc) == doc, "the seal is not idempotent"


def test_an_instance_binds_the_versions_it_ran(session):
    _call("fylite_zerod", {})
    header = _doc(session)["fylite:projection"]["header"]
    assert header["form"] == "instance"
    bound = header["bound_artifact_versions"]
    assert bound and all(v.count(".") == 2 for v in bound.values())


def test_a_session_cannot_pass_for_a_registered_workflow(session):
    """★★``sandbox_local`` + ``egress_allowed: false`` is the schema's own
    vocabulary for "assembled outside the registry, not for production until
    a human promotes it" — which is exactly what an LLM session is."""
    _call("fylite_zerod", {})
    header = _doc(session)["fylite:projection"]["header"]
    assert header["provenance_class"] == "sandbox_local"
    assert header["egress_allowed"] is False


def test_a_call_that_names_no_published_artifact_is_refused():
    """★An instance bound to a placeholder would assert a reproducibility it
    does not have, so the miss is loud."""
    with pytest.raises(ValueError) as e:
        ledger._artifact_of({"tool": "something_else", "arguments": {}})
    assert "no published artifact" in str(e.value)


def test_a_lookup_does_not_appear_in_the_ledger(session):
    _call("fylite_zerod", {})
    _call("fylite_inspect", {"path": "tests/data/FYDOC-CASE-12-synthetic/corpus/g_synthetic.geqdsk"})
    assert len(_doc(session)["fylite:projection"]["dag"]["nodes"]) == 1


# --------------------------------------------------------------------------- #
# NR-ENV-005: the response envelope travels with the catalog
# --------------------------------------------------------------------------- #

def test_every_capability_declares_a_response_tier():
    cat = engine.manifest_catalog()
    for e in cat["fylite:manifests"]:
        r = e["response"]
        assert r["tier"] in ("interactive", "batch", "network"), e["@id"]
        if r["tier"] == "interactive":
            assert r["budget_ms"] > 0
        assert r["measured_ms"] is not None or "[TBD]" in r["evidence"]


def test_the_description_says_which_tier_before_the_call():
    """★FR-HOST-002 forbids presenting a batch task as an interactive one —
    on a tool face that has to be visible BEFORE the call, or the caller
    blocks on a scan it expected in milliseconds."""
    tools = {t["name"]: t["description"] for t in engine.llm_tools()}
    assert "interactive, budget" in tools["fylite_zerod"]
    assert "batch" in tools["fylite_feasible"]


@pytest.mark.parametrize("tool,args", [
    ("zerod", {}),
    ("transport", {"power": 4.0}),
])
def test_an_interactive_tool_stays_inside_its_declared_budget(tool, args):
    """★A declared budget nothing measures is a sentence in a document;
    exceeding it is a regression defect (NR-ENV-005), so it is a test."""
    import time
    from fylite import scenario as S
    fn = getattr(S.model, tool)
    fn(**args)                                   # warm the library
    t = time.perf_counter()
    fn(**args)
    elapsed_ms = (time.perf_counter() - t) * 1000
    budget = engine.load_manifests()[tool]["fylite:response"]["budget_ms"]
    assert elapsed_ms < budget, f"{tool}: {elapsed_ms:.0f} ms > {budget} ms"


# --------------------------------------------------------------------------- #
# the records face
# --------------------------------------------------------------------------- #

def test_the_server_declares_resources(session):
    resp = engine.handle_mcp_message({"jsonrpc": "2.0", "id": 1,
                                      "method": "initialize", "params": {}})
    assert "resources" in resp["result"]["capabilities"]


def test_the_records_are_listed_and_readable(session):
    p = _call("fylite_zerod", {})
    listed = {r["uri"] for r in serve.list_mcp_resources()}
    assert f"fylite://{p['run']}/manifest.json" in listed
    assert "fylite://s-ledger/ledger.jsonld" in listed
    got = serve.read_mcp_resource(f"fylite://{p['run']}/acceptance.json")
    assert json.loads(got["text"])["state"] == "unevaluated"


def test_data_is_not_served_as_a_record(session):
    """★The two faces divide the work: ``resources`` serves RECORDS, handles
    serve DATA.  Handing back an array blob here would put the thing the whole
    handle mechanism exists to keep out of the conversation straight into it."""
    p = _call("fylite_zerod", {})
    with pytest.raises(LookupError) as e:
        serve.read_mcp_resource(f"fylite://{p['run']}/arrays.npz")
    assert "fylite_open" in str(e.value)
