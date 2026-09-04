"""The replay driver: a recorded session, fed back in.

★★This is G-06's second closure criterion, which the report kept OPEN rather
than declaring satisfied ("『重放驱动』没有做：那是一个执行器…是新的能力而不是
本条差距的接线").  So the tests here are not about a module existing; they are
about the claim「可重放」being true: the same entry, the same arguments, the
handles re-pointed at what the replay itself produced, and the artefacts
coming back with the same hashes.

★Every test drives the REAL tool face (``serve.call_mcp_tool``) into a
temporary run root.  A replay driver tested against a stub would prove that
the stub is deterministic.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fylite.engine import replay, serve

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def run_root(tmp_path, monkeypatch):
    """A private run root, and a session of this test's own inside it.

    ★``FYLITE_SESSION`` rather than clearing a cache: ``handles.session_id``
    derives its id ONCE per process (G-14 — the defect was a session id
    recomputed from the current second), and the environment variable is the
    documented way to say otherwise.  Setting it also keeps the tests in this
    file from landing in one another's ledger, which would make every one of
    them read a document the previous test wrote.
    """
    monkeypatch.setenv("FYLITE_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("FYLITE_SESSION", tmp_path.name)
    return tmp_path


def _ledger(run_root: Path) -> Path:
    found = sorted(run_root.glob("*/ledger.jsonld"))
    assert len(found) == 1, f"expected one session ledger, got {found}"
    return found[0]


def _zerod(**kw) -> dict:
    out = serve.call_mcp_tool("fylite_zerod", {"n_rho": 9, **kw})
    assert not out.get("isError"), out
    return json.loads(out["content"][0]["text"])


def test_a_one_node_session_replays_with_the_same_artefacts(run_root):
    """The whole claim, at its smallest: record a run, feed the ledger back
    in, and every artefact comes back the same."""
    _zerod()
    rep = replay.replay(_ledger(run_root))
    assert rep["replayed"] == 1 and rep["refused"] == 0, rep
    (node,) = rep["nodes"]
    assert node["tool"] == "fylite_zerod"
    assert node["artifacts"], "nothing was compared"
    assert all(v in (replay.SAME, replay.SAME_MODULO_RUN_ID)
               for v in node["artifacts"].values()), node["artifacts"]
    #: the arrays are the computation, and they are byte-identical — the
    #: weaker verdict is only ever the JSON that carries the handles
    assert node["artifacts"]["arrays.npz"] == replay.SAME


def test_the_replay_lands_in_its_own_session_beside_the_original(run_root):
    """★A replay must not append to the ledger it is replaying: the original
    is the thing being checked against, and a driver that grew it would be
    comparing a document with its own output."""
    _zerod()
    src = _ledger(run_root)
    before = json.loads(src.read_text())
    rep = replay.replay(src)
    after = json.loads(src.read_text())
    assert after == before, "the replay appended to the source ledger"
    assert rep["session"] != src.parent.name
    assert (run_root / rep["session"] / "ledger.jsonld").is_file(), (
        "the replay left no ledger of its own — it is a session too")


def test_a_handle_edge_is_re_pointed_at_what_the_replay_produced(run_root):
    """★★The test that makes the driver worth having.

    The second node was called with a handle naming the FIRST run.  Replayed
    naively, that handle still resolves — to the original run's data — so
    every node would「succeed」while the second one read numbers the replay
    never computed.  What must happen is that the handle is re-pointed at the
    run this replay produced, and the proof is that the second node's
    recorded argument names a run id that does not exist in the new session.
    """
    first = _zerod()
    ref = first["rho"]["ref"]
    out = serve.call_mcp_tool("fylite_transport",
                              {"rho": {"$ref": ref}, "steps": 2})
    assert not out.get("isError"), out

    src = _ledger(run_root)
    doc = json.loads(src.read_text())
    dag = doc["fylite:projection"]["dag"]
    assert len(dag["nodes"]) == 2 and len(dag["edges"]) == 1, dag

    rep = replay.replay(src)
    assert rep["refused"] == 0, rep
    assert rep["replayed"] == 2, rep
    runs = [r["run"] for r in rep["nodes"]]
    assert len(set(runs)) == 2 and all(runs)

    #: the second replayed run's own record must name the FIRST replayed run,
    #: not the original one it was recorded against
    from fylite.engine import handles
    man = json.loads((handles.find_run(runs[1]) / "manifest.json").read_text())
    got = man["config"]["arguments"]["rho"]
    assert handles.parse(got)[0] == runs[0], (
        f"the replayed node was fed {got!r}; it should name the replay's own "
        f"first run {runs[0]!r}")
    #: ★and the run it names is the REPLAY's, not the original's.  Checking
    #: that the id merely differs would not do it: run ids are second-stamped
    #: per session, so two sessions can mint the same one — which is why
    #: `new_run` dedups across the whole run root, and why this asserts on
    #: the DIRECTORY the handle resolves to.
    assert handles.find_run(runs[0]).parent.name == rep["session"], (
        "the replayed handle resolves into a different session — a run id "
        "collided across sessions and the handle followed the wrong one")


def test_a_node_whose_bulk_argument_was_inline_is_refused_by_name(run_root):
    """★The limit, gated rather than described.

    ``provenance.build_manifest`` keeps bulk inputs as a DIGEST, so a call
    made with an inline array cannot be reconstructed from the record.  The
    driver must say so, and name the argument — dropping it would re-run a
    DIFFERENT computation under the same node id, which is the one outcome a
    replay may not produce.
    """
    #: ★TWELVE points, not five: `serve._split_call` keeps a short scalar
    #: list (<= 8) in `config` verbatim, so a small array IS replayable and
    #: this test would be asserting about the wrong branch.
    out = serve.call_mcp_tool(
        "fylite_transport",
        {"rho": [i / 11.0 for i in range(12)], "steps": 1})
    assert not out.get("isError"), out
    rep = replay.replay(_ledger(run_root))
    (node,) = rep["nodes"]
    assert node["status"] == replay.REFUSED, node
    assert "rho" in node["reason"], node["reason"]
    assert "DIGEST" in node["reason"] or "digest" in node["reason"]


def test_a_version_that_moved_is_refused_unless_it_is_allowed(run_root,
                                                              monkeypatch):
    """★An instance binds the EXACT version it ran; replaying it against a
    different one is not a replay of it.  The refusal is the default, and the
    override has to be asked for by name — and then SAYS so in the report."""
    _zerod()
    src = _ledger(run_root)

    real = serve.load_manifests

    def moved():
        docs = {k: json.loads(json.dumps(v)) for k, v in real().items()}
        docs["zerod"]["fylite:projection"]["version"] = "9.9.9"
        return docs

    from fylite.engine import manifest as _m
    monkeypatch.setattr(_m, "load_manifests", lambda *a, **k: moved())

    rep = replay.replay(src)
    (node,) = rep["nodes"]
    assert node["status"] == replay.REFUSED
    assert "9.9.9" in node["reason"], node["reason"]

    rep = replay.replay(src, allow_version_drift=True,
                        session="drifted")
    (node,) = rep["nodes"]
    assert node["status"] == replay.OK, node
    assert node["note"] and "9.9.9" in node["note"], (
        "a drifted replay must say which version it actually ran")


def test_a_template_is_not_replayable(run_root):
    """★``form: template`` says which versions it WOULD accept; only an
    instance says which one it ran.  Feeding the authored workflow template
    to the driver must be refused at the door, not attempted node by node."""
    tmpl = ROOT / "python/fylite/_manifest/kinetic_reconstruction.jsonld"
    with pytest.raises(ValueError, match="not an instance"):
        replay.replay(tmpl)


def test_the_plan_respects_edges_and_refuses_a_cycle(run_root):
    """★The order is topological, not the recorded order.  For a session
    ledger the two coincide — which is exactly why an executor that leaned on
    the recorded order would look correct until someone edited or branched
    the instance, which is what the document type is for."""
    first = _zerod()
    out = serve.call_mcp_tool(
        "fylite_transport",
        {"rho": {"$ref": first["rho"]["ref"]}, "steps": 1})
    assert not out.get("isError"), out
    doc = json.loads(_ledger(run_root).read_text())

    #: reverse the recorded order: the plan must still put the source first
    doc["fylite:projection"]["dag"]["nodes"].reverse()
    order = [n["id"] for n in replay.plan(doc)]
    edge = doc["fylite:projection"]["dag"]["edges"][0]
    assert order.index(edge["source_node"]) < order.index(edge["target_node"])

    #: and a cycle is refused rather than broken at an arbitrary edge
    a, b = edge["source_node"], edge["target_node"]
    doc["fylite:projection"]["dag"]["edges"].append(
        {"id": "e2", "source_node": b, "source_port": "rho",
         "target_node": a, "target_port": "rho"})
    with pytest.raises(ValueError, match="cycle"):
        replay.plan(doc)


def test_the_identity_keys_are_the_ones_the_service_stamps():
    """★★The comparison is allowed to drop exactly the keys the service adds,
    and this ties that list to the code that writes them.

    Without it, :data:`replay.IDENTITY_KEYS` is a hand-kept list beside a
    literal — and the failure mode is silent in the worst direction: a third
    key added there would start being dropped from every comparison, so a
    replay could report「same」about a result that had grown a field.
    """
    import ast

    src = (ROOT / "python/fylite/engine/serve.py").read_text()
    tree = ast.parse(src)
    stamped = None
    for node in ast.walk(tree):
        #: `result = {**result, "run": rid, "run_dir": str(run)}`
        if not isinstance(node, ast.Dict):
            continue
        keys = node.keys
        if not keys or keys[0] is not None:      # no `**result` first
            continue
        names = [k.value for k in keys[1:]
                 if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        if "run" in names:
            stamped = tuple(names)
            break
    assert stamped is not None, (
        "could not find the `{**result, 'run': …}` stamp in serve.py — if it "
        "moved, this gate is blind and replay.IDENTITY_KEYS is unchecked")
    assert stamped == replay.IDENTITY_KEYS, (
        f"serve.py stamps {stamped}, replay.IDENTITY_KEYS says "
        f"{replay.IDENTITY_KEYS}")


