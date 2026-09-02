"""FR-DATA-003, finally on the路: every computed run emits its record.

★★``build_manifest`` / ``acceptance`` / ``deliver`` have been in this package
for a long time and had **no caller outside the test suite** — measured, not
guessed::

    grep -rn "build_manifest(\\|deliver(" --include=*.py python/
    → engine/provenance.py (itself), tests/test_engine_lifecycle.py

So the requirement "每次求解运行必须发射运行清单" was satisfied by machinery that
nothing ran.  A record nobody writes is a record nobody can read afterwards, and
the numbers a tool hands an LLM are exactly the numbers that get quoted out of
context later.

What is gated here is the SHAPE of the record and the line between a
computation (recorded) and a lookup (not).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from conftest import requires_machine

from fylite.engine import handles
from fylite.engine import serve


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv(handles.RUN_ENV, str(tmp_path / "runs"))
    monkeypatch.setenv(handles.SESSION_ENV, "s-record")
    return tmp_path / "runs"


def _call(name, args):
    r = serve.call_mcp_tool(name, args)
    assert r["isError"] is False, r["content"][0]["text"]
    return json.loads(r["content"][0]["text"])


def _manifest(payload) -> dict:
    return json.loads((Path(payload["run_dir"]) / "manifest.json").read_text())


# --------------------------------------------------------------------------- #
# a computation is recorded
# --------------------------------------------------------------------------- #

def test_a_computed_run_writes_its_manifest_and_verdict(root):
    p = _call("fylite_zerod", {"te_flattop": 10.0})
    d = Path(p["run_dir"])
    assert (d / "manifest.json").is_file() and (d / "acceptance.json").is_file()
    m = _manifest(p)
    assert m["@type"] == ["fylite:RunManifest", "prov:Entity"]
    assert m["code"]["rev"] and "python" in m["environment"]


def test_the_record_names_the_tool_and_the_entry(root):
    m = _manifest(_call("fylite_zerod", {"te_flattop": 10.0}))
    assert m["config"]["tool"] == "fylite_zerod"
    assert m["config"]["entry"] == "fylite.scenario.model:zerod"
    assert m["config"]["arguments"] == {"te_flattop": 10.0}


def test_bulk_inputs_are_digested_not_copied(root):
    """★A manifest that inlined the measurement set would be a copy of the
    data wearing the name of a record."""
    profile = [1.0 + 0.001 * i for i in range(41)]
    m = _manifest(_call("fylite_transport", {"power": 4.0,
                                             "y_init": profile}))
    assert m["config"]["arguments"] == {"power": 4.0}
    assert set(m["inputs"]) == {"y_init"}
    assert len(m["inputs"]["y_init"]) == 64        # a sha256, not the data
    assert "1.039" not in json.dumps(m)            # no profile point inlined


def test_a_handle_argument_stays_a_handle_in_the_record(root):
    """★★The lineage edge: the record keeps what the CALLER wrote, so the run
    it was built on is named.  Dereferencing first and recording second would
    replace that edge with a copy of the data."""
    first = _call("fylite_zerod", {})
    ref = first["te"]["ref"]
    m = _manifest(_call("fylite_transport", {"power": 4.0,
                                             "y_init": {"$ref": ref}}))
    assert m["config"]["arguments"]["y_init"] == ref
    assert first["run"] in m["config"]["arguments"]["y_init"]


def test_artifacts_are_hashed_and_the_hash_is_of_the_file(root):
    import hashlib
    p = _call("fylite_zerod", {})
    m = _manifest(p)
    names = {a["name"]: a for a in m["artifacts"]}
    assert {"arrays.npz", "result.json"} <= set(names)
    a = names["result.json"]
    blob = (Path(p["run_dir"]) / "result.json").read_bytes()
    assert a["sha256"] == hashlib.sha256(blob).hexdigest()
    assert a["bytes"] == len(blob)


def test_a_metric_that_is_absent_is_unevaluated_never_passed(root):
    """★The whole point of the four-state verdict: a missing criterion must
    not read as a satisfied one.

    ★★The criterion checked here changed on 2026-08-25 and the change is the
    subject: this used to assert ``terror`` — the RECONSTRUCTION's fit
    residual — on a 0-D discharge, because every tool was scored against one
    register.  It was `unevaluated`, truthfully, and it said nothing: the 0-D
    entry could not have produced that field under any circumstances.  What
    zerod actually declares is `converged`, `tbd` because only its `predict`
    mode has anything to converge and it does not report it — which is the
    same verdict for a reason a reader can act on.
    """
    m = _manifest(_call("fylite_zerod", {}))
    crit = {c["name"]: c for c in m["acceptance"]["criteria"]}
    assert crit["converged"]["state"] == "unevaluated"
    assert crit["converged"]["tbd"], (
        "an unevaluated criterion on a published capability must say why")
    assert "terror" not in crit, (
        "the 0-D discharge is still being scored against the "
        "reconstruction's register")
    assert m["acceptance"]["state"] == "unevaluated"


@requires_machine
def test_the_record_is_strict_json(root):
    """A record with ``Infinity`` in it is a record that cannot be read back.

    ★2026-09-01 加 `requires_machine`：`fylite_vstab` 要装置描述，而本发行版不带。
    缺装置时它在 **MCP 结果载荷里**回一个 `isError` ——异常没有抛出来，conftest 那条
    「MachineDataMissing 转跳过」的钩子接不到，于是这条以断言失败落地，看起来像
    「记录不是严格 JSON」。**缺输入要长得像缺输入**，不能借另一条判据的嘴说话。
    """
    p = _call("fylite_vstab", {"eq": "tests/data/synthetic/g_synthetic.geqdsk",
                               "coil_aturns": [0.0] * 12})
    text = (Path(p["run_dir"]) / "manifest.json").read_text()
    json.loads(text, parse_constant=lambda c: pytest.fail(f"not JSON: {c}"))


# --------------------------------------------------------------------------- #
# a lookup is not a computation
# --------------------------------------------------------------------------- #

def test_reading_a_file_back_leaves_handles_but_no_record(root):
    p = _call("fylite_inspect", {"path": "tests/data/synthetic/"
                                         "g_synthetic.geqdsk"})
    d = Path(p["run_dir"])
    assert (d / handles.ARRAYS).is_file()          # handles, so it composes
    assert not (d / "manifest.json").exists()      # but nothing was computed


def test_a_render_lands_in_the_run_not_beside_its_input(root, tmp_path):
    """★★The default used to be ``<gfile>.png`` — beside the INPUT.  The
    g-file a model hands this tool is usually a path inside the user's own
    checkout, so the render landed in their working copy with nothing
    recording who wrote it (measured: one probe call left a 217 kB PNG in
    ``tests/data/synthetic/``)."""
    src = Path("tests/data/synthetic/g_synthetic.geqdsk").resolve()
    before = set(src.parent.iterdir())
    p = _call("fylite_plot", {"gfile": str(src)})
    assert set(src.parent.iterdir()) == before, "the render polluted the input tree"
    plot = Path(p["plot"])
    assert plot.parent == Path(p["run_dir"]) and plot.is_file()
    #: and it is a recorded delivery, so the image is hashed in the manifest
    names = {a["name"] for a in _manifest(p)["artifacts"]}
    assert plot.name in names


def test_a_catalog_query_opens_no_run_at_all(root):
    serve.call_mcp_tool("fylite_describe", {})
    assert not root.exists() or not list(root.glob("*/r-*"))


# --------------------------------------------------------------------------- #
# the command line records the same way
# --------------------------------------------------------------------------- #

def test_the_cli_writes_the_same_record(root, monkeypatch, capsys):
    from fylite import engine

    monkeypatch.setattr(serve, "run_reconstruction",
                        lambda opts: {"q0": 1.1, "q95": 3.3,
                                      "qpsi": np.linspace(1.0, 3.0, 65),
                                      "device": "stub", "iterations": 4,
                                      "residual": 1e-11, "psi_axis": -0.1,
                                      "psi_bry": 0.0, "ip": 4e5,
                                      "bcentr": -1.8, "rmaxis": 1.85,
                                      "zmaxis": 0.0, "converged": True})
    monkeypatch.setattr(serve, "deliver_gfile", lambda res, out: "g.geqdsk")
    assert engine.cli_main(["run", "--shot", "1", "--time", "1.0"]) == 0
    out = capsys.readouterr().out
    run_dir = Path([ln.split(":", 1)[1].strip() for ln in out.splitlines()
                    if ln.startswith("run ")][0])
    m = json.loads((run_dir / "manifest.json").read_text())
    assert m["config"]["tool"] == "fylite run"
    assert m["config"]["arguments"]["shot"] == 1
    #: the loop-convergence criterion IS evaluable here, and it passed
    states = {c["name"]: c["state"] for c in m["acceptance"]["criteria"]}
    assert states["converged"] == "pass"


# --------------------------------------------------------------------------- #
# per-capability acceptance criteria
# --------------------------------------------------------------------------- #
#
# ★★Until 2026-08-25 every tool was scored against ONE register — the
# reconstruction's `terror` / `chi_pressure` / `converged`.  A 0-D discharge
# and a transport march both came back `unevaluated`, which was true and
# useless: it said「nothing could be scored」when the fact was「nobody had said
# what to score」.  Each capability declares its own criteria now, in its own
# manifest, and these gates hold that register to what the code can actually
# produce.
def _manifests() -> dict:
    from fylite.engine.manifest import load_manifests
    return load_manifests()


def test_every_capability_declares_its_acceptance_criteria():
    """★A published capability with no criteria is a gap, and it must show up
    HERE rather than as a run that quietly inherited somebody else's."""
    missing = sorted(n for n, d in _manifests().items()
                     if not isinstance(d.get("fylite:acceptance"), dict))
    assert not missing, (
        f"published capabilities with no acceptance criteria: {missing}\n"
        "Declare `fylite:acceptance` in each manifest — a criterion with a "
        "threshold, a `require` flag, or a `tbd` with the reason there is no "
        "threshold yet.  All three are answers; silence is not.")


def test_every_declared_criterion_is_one_of_the_three_forms():
    """The register is data the scorer reads; a fourth shape would be read as
    no criterion at all, which is the silent direction."""
    bad = []
    for name, doc in _manifests().items():
        for key, spec in (doc.get("fylite:acceptance") or {}).items():
            if key.startswith("@"):
                assert isinstance(spec, str) and spec.strip(), \
                    f"{name}: {key} must carry prose"
                continue
            if not isinstance(spec, dict):
                bad.append(f"{name}.{key}: not an object")
            elif "tbd" in spec:
                if not str(spec["tbd"]).strip():
                    bad.append(f"{name}.{key}: empty tbd reason")
            elif "require" in spec:
                if spec["require"] is not True:
                    bad.append(f"{name}.{key}: require must be true")
            elif not ("pass" in spec and "warn" in spec):
                bad.append(f"{name}.{key}: neither pass/warn, require, nor tbd")
    assert not bad, bad


def test_a_scored_criterion_names_a_field_the_entry_can_produce():
    """★★The half that keeps the register honest.

    A criterion the code never reports is `unevaluated` FOREVER — it looks
    like diligence and scores nothing.  So every criterion that is not `tbd`
    must name a key the entry's own source actually writes.  (`tbd` criteria
    are exempt by construction: saying「there is no threshold yet」is exactly
    the claim that it is not being scored.)
    """
    import importlib
    import inspect
    import re as _re

    bad = []
    for name, doc in _manifests().items():
        crit = {k: v for k, v in (doc.get("fylite:acceptance") or {}).items()
                if not k.startswith("@") and isinstance(v, dict)
                and "tbd" not in v}
        if not crit:
            continue
        mod, fn = doc["fylite:entry"].split(":")
        #: ★The entry's own source AND its module's — an entry is often a
        #: door (`analysis:reconstruction` validates and delegates to
        #: `recon_rs.reconstruct`), and a checker that read only the door
        #: would report every delegated field as unreported.  Reading the
        #: whole package the entry lives in is coarse ON PURPOSE: this gate
        #: is here to catch a criterion nothing anywhere produces, not to
        #: trace data flow.
        f = getattr(importlib.import_module(mod), fn)
        srcs = [inspect.getsource(f)]
        pkg = Path(inspect.getsourcefile(f)).parent
        srcs += [q.read_text() for q in sorted(pkg.glob("*.py"))]
        src = "\n".join(srcs)
        written = set(_re.findall(r'"([a-z_0-9]+)"\s*:', src)) \
            | set(_re.findall(r"'([a-z_0-9]+)'\s*:", src)) \
            | set(_re.findall(r'\[\s*["\']([a-z_0-9]+)["\']\s*\]\s*=', src))
        for key in crit:
            if key not in written:
                bad.append(f"{name}: scores {key!r}, which "
                           f"{doc['fylite:entry']} does not appear to report")
    assert not bad, (
        "\n".join(bad) + "\n\nA criterion the entry never reports scores "
        "`unevaluated` on every run — declare it `tbd` with the reason, or "
        "make the entry report it.")


def test_a_declared_register_replaces_the_defaults():
    """★A capability that states its criteria has stated ALL of them.

    Merging is how a transport march came to carry `terror` and
    `chi_pressure` — two criteria it can never meet, sitting `unevaluated`
    in its record and saying only that the wrong register was applied.
    """
    from fylite.engine import provenance
    got = provenance.acceptance({"converged": True},
                                {"converged": {"require": True}})
    assert [c["name"] for c in got["criteria"]] == ["converged"]
    assert got["state"] == provenance.PASS
    #: and passing nothing still gets the shipped defaults
    fallback = provenance.acceptance({"terror": 0.01})
    assert {c["name"] for c in fallback["criteria"]} >= {"terror"}


def test_a_tbd_criterion_is_unevaluated_and_carries_its_reason():
    """★`unevaluated` with a reason is a different fact from `unevaluated`
    because a number was missing, and a reader has to be able to tell."""
    from fylite.engine import provenance
    got = provenance.acceptance(
        {}, {"margin": {"tbd": "the margin is the ANSWER, not a verdict"}})
    (c,) = got["criteria"]
    assert c["state"] == provenance.UNEVALUATED
    assert "ANSWER" in c["tbd"]
    assert got["state"] == provenance.UNEVALUATED, (
        "a tbd criterion must not pass — nothing was checked")


def test_a_result_flag_is_never_scored_as_acceptance():
    """★★The category error this register is written against: `stable` and
    `feasible` are RESULTS.  A vertical-stability run that correctly reports
    an unstable column is a successful run, and scoring it `fail` would make
    that field mean two different things.

    The manifests that could plausibly score them must therefore NOT, and
    must say why — the note is the part that stops the next person.
    """
    for name, flag in (("vstab", "stable"), ("breakdown", "feasible"),
                       ("feasible", "feasible")):
        crit = _manifests()[name].get("fylite:acceptance") or {}
        assert flag not in crit, (
            f"{name} scores {flag!r} as acceptance — it is the run's ANSWER, "
            "not a verdict on whether the answer can be trusted")
        note = crit.get("@note", "")
        assert flag in note, (
            f"{name} does not say why {flag!r} is not a criterion; without "
            "the note this is indistinguishable from an oversight")


def test_the_catalog_carries_each_capability_s_criteria():
    """★A caller asks「what does a pass mean here」BEFORE it calls, so the
    criteria travel with the catalog — the same reason the response envelope
    does.  Declaring them only in the file would leave `fylite describe`
    describing everything about a capability except how it is judged."""
    from fylite.engine.manifest import manifest_catalog
    cat = manifest_catalog()
    missing = sorted(e["@id"] for e in cat["fylite:manifests"]
                     if not isinstance(e.get("acceptance"), dict))
    assert not missing, (
        f"the catalog does not carry acceptance criteria for {missing}")
