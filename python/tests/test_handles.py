"""Data handles: the half a digest cannot do.

★★``summarize`` has always stamped a ``sha256`` on every array it shapes —
which proves that two summaries describe the same bytes and gives a caller no
way to GET those bytes.  So a tool face could report a 65x65 psi map and a
caller could do nothing with it but ask for it again, inline, in full.  A
handle (``fylite://<run-id>/<port>``) closes that: the arrays are written into
a run directory, the summary names where, and an argument of the form
``{"$ref": …}`` is resolved back at the service boundary.

Three properties are worth gating, and the middle one is the fragile one:

* what is STORED and what is ADVERTISED use one path grammar (two traversals,
  one convention — the classic place for a silent drift);
* a handle resolves to the bytes its summary described (sha256, not shape);
* nothing deeper than the service boundary ever sees a handle.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from fylite.engine import handles
from fylite.engine import serve


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv(handles.RUN_ENV, str(tmp_path / "runs"))
    monkeypatch.setenv(handles.SESSION_ENV, "s-test")
    return tmp_path / "runs"


RESULT = {
    "q0": 1.2,                               # scalar: travels inline
    "flags": [1, 2, 3],                      # short scalar list: inline
    "qpsi": np.linspace(1.0, 4.0, 65),       # 1-D: stored
    "psi": np.arange(9.0).reshape(3, 3),     # 2-D: stored
    "profile": {"te": np.linspace(1.0, 2.0, 40)},        # nested
    "slices": [{"ne": np.linspace(1.0, 2.0, 30)}],       # nested in a list
    "gfile": "/tmp/g137985.04000",           # a path: inline
}


# --------------------------------------------------------------------------- #
# where things live
# --------------------------------------------------------------------------- #

def test_the_run_root_is_never_the_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv(handles.RUN_ENV, raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert handles.runs_root() == tmp_path / "fylite" / "runs"


def test_the_env_wins(root):
    assert handles.runs_root() == root


def test_the_session_id_is_fixed_for_the_life_of_the_process(monkeypatch,
                                                             root):
    """★★It used to be derived from the current SECOND on every call, so a
    process that ran two tools a second apart put them in two different
    "sessions" — two one-node ledgers, and the lineage edge between them
    silently gone.  The environment variable still wins on every call; only
    the derived id is fixed."""
    monkeypatch.delenv(handles.SESSION_ENV, raising=False)
    monkeypatch.setattr(handles, "_SESSION", None)
    ticks = iter(["20260825-000001", "20260825-000002", "20260825-000003"])
    monkeypatch.setattr(handles, "_stamp", lambda: next(ticks))
    first = handles.session_id()
    assert handles.session_id() == first          # the clock moved; the id did not
    a, b = handles.new_run(), handles.new_run()
    assert a.parent == b.parent == root / first


def test_the_environment_still_wins_over_the_cached_id(monkeypatch, root):
    monkeypatch.setattr(handles, "_SESSION", "s-cached")
    monkeypatch.setenv(handles.SESSION_ENV, "s-explicit")
    assert handles.session_id() == "s-explicit"


def test_a_new_run_never_reuses_a_directory(root):
    a, b = handles.new_run(), handles.new_run()
    assert a.is_dir() and b.is_dir() and a != b


def test_a_handle_finds_its_run_whatever_session_made_it(root):
    """★A handle names the RUN, not the session — so it survives being passed
    to a different process, which is the point of writing it down at all."""
    run = handles.new_run(session="s-somebody-else")
    handles.store(run, {"x": np.arange(20.0)}, {"x": {}})
    assert handles.find_run(handles.run_id_of(run)) == run


def test_an_unknown_run_says_where_it_looked(root):
    root.mkdir(parents=True, exist_ok=True)
    with pytest.raises(LookupError) as e:
        handles.resolve("fylite://r-nope/qpsi")
    assert str(root) in str(e.value)


# --------------------------------------------------------------------------- #
# one path grammar
# --------------------------------------------------------------------------- #

def test_what_is_stored_is_addressed_the_way_it_is_advertised(root):
    """★The anti-drift gate: every ``ref`` a summary emits must resolve, and
    every array that was stored must be advertised.  Two traversals share one
    convention and nothing but this keeps them together."""
    run = handles.new_run()
    rid = handles.run_id_of(run)
    payload = serve.summarize(RESULT, run_id=rid)
    handles.store(run, RESULT, payload)

    refs = set()

    def walk(node):
        if isinstance(node, dict):
            if "ref" in node and node.get("@type") == "fylite:ArraySummary":
                refs.add(node["ref"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)
    assert refs == {handles.handle(rid, p)
                    for p in handles.collect_arrays(RESULT)}
    for ref in refs:
        handles.resolve(ref)          # every advertised handle resolves


def test_a_handle_returns_the_bytes_its_summary_described(root):
    run = handles.new_run()
    rid = handles.run_id_of(run)
    payload = serve.summarize(RESULT, run_id=rid)
    handles.store(run, RESULT, payload)
    got = handles.resolve(payload["profile"]["te"]["ref"])
    digest = hashlib.sha256(np.ascontiguousarray(got).tobytes()).hexdigest()
    assert digest == payload["profile"]["te"]["sha256"]
    assert np.array_equal(got, RESULT["profile"]["te"])


def test_short_scalar_lists_stay_inline_and_are_not_stored(root):
    run = handles.new_run()
    payload = serve.summarize(RESULT, run_id=handles.run_id_of(run))
    assert payload["flags"] == [1, 2, 3]
    assert "flags" not in handles.collect_arrays(RESULT)


def test_a_path_is_reachable_by_handle_too(root):
    run = handles.new_run()
    rid = handles.run_id_of(run)
    payload = serve.summarize(RESULT, run_id=rid)
    handles.store(run, RESULT, payload)
    assert handles.resolve(handles.handle(rid, "gfile")) == RESULT["gfile"]


def test_an_unknown_port_lists_what_the_run_carries(root):
    run = handles.new_run()
    rid = handles.run_id_of(run)
    handles.store(run, RESULT, serve.summarize(RESULT, run_id=rid))
    with pytest.raises(LookupError) as e:
        handles.resolve(handles.handle(rid, "no_such_port"))
    assert "qpsi" in str(e.value)


def test_a_malformed_handle_says_what_one_looks_like():
    with pytest.raises(ValueError) as e:
        handles.parse("/tmp/somewhere.npz")
    assert "fylite://<run-id>/<port>" in str(e.value)


# --------------------------------------------------------------------------- #
# arguments by reference
# --------------------------------------------------------------------------- #

def test_deref_reaches_every_position(root):
    run = handles.new_run()
    rid = handles.run_id_of(run)
    handles.store(run, RESULT, serve.summarize(RESULT, run_id=rid))
    ref = {"$ref": handles.handle(rid, "qpsi")}
    out = handles.deref({"a": ref, "b": [ref], "c": {"d": ref}, "e": 3})
    for got in (out["a"], out["b"][0], out["c"]["d"]):
        assert np.array_equal(got, RESULT["qpsi"])
    assert out["e"] == 3


def test_a_handle_is_resolved_before_the_tool_sees_it(root, monkeypatch):
    """★The boundary rule: physics entry points take arrays, never handles."""
    run = handles.new_run()
    rid = handles.run_id_of(run)
    handles.store(run, RESULT, serve.summarize(RESULT, run_id=rid))
    seen = {}
    monkeypatch.setattr(serve, "_mcp_inspect_tool",
                        lambda args: seen.setdefault("path", args["path"]))
    serve.call_mcp_tool("fylite_inspect",
                        {"path": {"$ref": handles.handle(rid, "gfile")}})
    assert seen["path"] == RESULT["gfile"]


def test_a_dangling_handle_is_a_tool_error_not_a_crash(root):
    root.mkdir(parents=True, exist_ok=True)
    result = serve.call_mcp_tool("fylite_inspect",
                                 {"path": {"$ref": "fylite://r-gone/x"}})
    assert result["isError"] is True
    assert json.loads(result["content"][0]["text"])["error"] == "LookupError"


# --------------------------------------------------------------------------- #
# fylite_open
# --------------------------------------------------------------------------- #

def _open(**args):
    r = serve.call_mcp_tool("fylite_open", args)
    assert r["isError"] is False, r["content"][0]["text"]
    return json.loads(r["content"][0]["text"])


def test_open_samples_a_profile_without_inlining_it(root):
    run = handles.new_run()
    rid = handles.run_id_of(run)
    handles.store(run, RESULT, serve.summarize(RESULT, run_id=rid))
    got = _open(ref=handles.handle(rid, "qpsi"))
    assert len(got["sample"]) <= 16 and got["index"][0] == 0
    assert got["index"][-1] == RESULT["qpsi"].size - 1
    assert got["summary"]["shape"] == [65]


def test_open_takes_an_index_and_a_head(root):
    run = handles.new_run()
    rid = handles.run_id_of(run)
    handles.store(run, RESULT, serve.summarize(RESULT, run_id=rid))
    ref = handles.handle(rid, "qpsi")
    assert _open(ref=ref, index=3)["value"] == [RESULT["qpsi"][3]]
    assert _open(ref=ref, head=4)["value"] == list(RESULT["qpsi"][:4])


def test_open_will_not_flood_a_caller(root):
    run = handles.new_run()
    rid = handles.run_id_of(run)
    big = {"x": np.arange(5000.0)}
    handles.store(run, big, serve.summarize(big, run_id=rid))
    assert len(_open(ref=handles.handle(rid, "x"), head=5000)["value"]) == 64


def test_open_asks_where_for_a_two_dimensional_map(root):
    run = handles.new_run()
    rid = handles.run_id_of(run)
    handles.store(run, RESULT, serve.summarize(RESULT, run_id=rid))
    ref = handles.handle(rid, "psi")
    got = _open(ref=ref)
    assert "index=" in got["note"] and got["summary"]["shape"] == [3, 3]
    assert _open(ref=ref, index=[1, 2])["value"] == 5.0


# --------------------------------------------------------------------------- #
# delivery
# --------------------------------------------------------------------------- #

def test_a_result_with_nothing_bulky_opens_no_run_directory(root):
    payload = serve.deliver_result({"q0": 1.0, "converged": True})
    assert payload == {"q0": 1.0, "converged": True}
    assert not root.exists() or not list(root.glob("*/r-*"))


def test_every_array_returning_tool_delivers_handles(root):
    """★Not only the reconstruction: a face where one tool hands back
    references and the rest hand back walls of numbers cannot be composed."""
    payload = serve.deliver_result(dict(RESULT))
    assert payload["qpsi"]["ref"].startswith("fylite://")
    assert handles.resolve(payload["qpsi"]["ref"]).size == 65
    assert (root / "s-test" / payload["run"] / handles.ARRAYS).is_file()
