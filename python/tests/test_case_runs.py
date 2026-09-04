"""S-2: every corpus case is either runnable from Python or refused by name.

★The deliverable being gated is the ACCOUNTING (`engine/cases.py`): a case's
page-control config maps onto a Python entry field by field, and a key that is
neither mapped nor consciously classified (sub-capability / shared / ui) fails
here — silent drops are the failure mode S-2 exists to prevent.  The refusals
are gated too: a bar with no faithful mapping must say so BY NAME, because
「跑了一个别的计算」 is worse than「拒绝」.

Runs go through the REAL tool face into a private run root, same discipline as
``test_replay.py``: a mapping validated against a stub would validate the stub.
★``discharge`` (a ~14 s free-boundary anneal) runs in the physics tier
(``tests/test_case_runs_physics.py``); here its MAPPING is still fully gated.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fylite.engine import cases
from fylite.scenario import BROWSER_ONLY_BARS, TOOLS

ROOT = Path(__file__).resolve().parents[2]

#: catalogue bars, measured from the corpus itself
#:
#: ★★2026-09-01：语料（`cases/`）已随裁定移出本仓。`cases.catalogue()` 在找不到
#: 语料时抛的是 **`SystemExit`**（CLI 的错误路径：「run from a checkout or pass --dir」）
#: ——而在**收集期**抛 SystemExit，pytest 报的是 `INTERNALERROR` 并就地停掉整个收集。
#: 实测代价：本档从 2056 条掉到 **246 条**，停在字母序第六个模块之后，**没有任何
#: 一行说它停了**。一个模块缺了数据，把另外 72 个模块一起带走。
#: ⇒ 缺语料时**在模块级跳过并点名**：声明缺席≠默认没有，更不该是静默截断。
try:
    _CATALOGUE = cases.catalogue()
except cases.CorpusMissing as exc:                          # 语料不在本仓
    pytest.skip(f"算例语料不在本仓（{exc}）——它随 cases 移出，"
                "本档的判据要在有语料的检出上跑",
                allow_module_level=True)
BARS = sorted({e["bar"] for e in _CATALOGUE})
RUNNABLE = sorted(cases._BUILDERS)


@pytest.fixture()
def run_root(tmp_path, monkeypatch):
    monkeypatch.setenv("FYLITE_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("FYLITE_SESSION", tmp_path.name)
    return tmp_path


def test_every_bar_is_mapped_or_refused_by_name():
    """No third state: a catalogue bar either has a builder or a reason."""
    for bar in BARS:
        assert (bar in cases._BUILDERS) != (bar in cases.REFUSALS), (
            f"bar {bar!r} is "
            + ("both mapped and refused" if bar in cases._BUILDERS
               else "neither mapped nor refused — a silent gap"))
    #: and the refusal reasons for the declared browser-only bars come from
    #: the REGISTER, not a second hand-kept spelling
    for bar, why in BROWSER_ONLY_BARS.items():
        if bar in cases.REFUSALS:
            assert why in cases.REFUSALS[bar]


@pytest.mark.parametrize("cid", sorted(
    e["case_id"] for e in cases.catalogue()
    if e["bar"] in cases._BUILDERS))
def test_every_runnable_case_accounts_for_every_field(cid):
    """★The S-2 criterion verbatim: 逐字段对账，对不上的按名列出——and here,
    listed-by-name means the plan fails until someone classifies it.

    ★A mapped BAR may still refuse a CASE: the `evolve` bar's loop is the
    kernel's, and a case that wants a capability not yet sunk into it is
    refused with that capability named.  That is the same discipline one
    level down, so it satisfies this gate — but only if the refusal really
    names something (`test_the_evolve_scope_ledger_names_what_is_missing`).
    """
    try:
        p = cases.plan(cid)
    except SystemExit as e:
        assert "it needs" in str(e), (
            f"{cid} was refused without naming what it needs:\n{e}")
        return
    a = p["accounting"]
    assert not a["unclassified"], (
        f"{cid}: config keys neither mapped nor classified: "
        f"{a['unclassified']} — classify them in engine/cases.py "
        "(map / sub / shared / ui), never drop them silently")
    assert a["mapped"], f"{cid}: nothing mapped at all"
    #: the tool the plan names is the register's own correspondence
    assert TOOLS[p["tool"]]["bar"] == p["bar"]


@pytest.mark.parametrize("cid", sorted(
    e["case_id"] for e in cases.catalogue()
    if e["bar"] in cases.REFUSALS))
def test_every_unmappable_case_is_refused_with_its_reason(cid):
    with pytest.raises(SystemExit) as ei:
        cases.plan(cid)
    msg = str(ei.value)
    assert cid in msg and "not runnable" in msg
    #: the reason travels with the refusal — a bare "cannot" has no next move
    entry, _doc = cases.load(cid)
    assert cases.REFUSALS[entry["bar"]][:40] in msg


def test_the_zerod_case_runs_and_records(run_root):
    r = cases.run("zerod-iter-15ma")
    run_dir = Path(r["run_dir"])
    assert (run_dir / "acceptance.json").is_file()
    res = json.loads((run_dir / "result.json").read_text())
    assert res["tier"] == "prescribed"
    #: the mapped flattop is the case's own number, through the unit change
    _, doc = cases.load("zerod-iter-15ma")
    man = json.loads((run_dir / "manifest.json").read_text())
    assert man["config"]["arguments"]["ip_flattop"] == pytest.approx(
        cases.settings(doc)["ip"] * 1e3)


def test_the_transport_case_runs_and_passes(run_root):
    r = cases.run("transport-iter-15ma")
    acc = json.loads((Path(r["run_dir"]) / "acceptance.json").read_text())
    assert acc["state"] == "pass", acc
    #: the Miller metric was really built: vprime is not the cylindrical
    #: default (2x), which is what a silently-dropped geometry would give
    res_vp = json.loads((Path(r["run_dir"]) / "result.json").read_text())
    assert "vprime" in res_vp


def test_the_breakdown_case_runs_on_the_iter_deck(run_root):
    """★Exercises the whole device generalisation: `*_device.yaml` discovery,
    optional diagnostic groups, the derived channel map, the scalar cap
    broadcast — every one of which was an EAST-ism found by this case."""
    r = cases.run("breakdown-iter")
    res = json.loads((Path(r["run_dir"]) / "result.json").read_text())
    assert res["null_ok"] is True
    assert res["b_max"] <= 2e-3
    #: feasible is a RESULT, not a verdict — but a factory case that came
    #: out infeasible would mean the mapping bent a unit somewhere
    assert res["feasible"] is True


def test_the_discharge_mapping_is_complete_without_running():
    """The 14 s anneal itself runs in the physics tier; the MAPPING —
    target dict, kA->A, the designed start, the page's solve block — is
    default-tier."""
    p = cases.plan("discharge-iter")
    args = p["arguments"]
    assert args["ip"] == pytest.approx(15e6)
    assert set(args["target"]) == {"r0", "a", "kappa", "delta_upper",
                                   "delta_lower", "z0"}
    assert args["max_iter"] == 600 and args["relax"] == 0.3
    assert "aturns0" not in args, "startmode auto means a DESIGNED start"


def test_the_page_constants_are_pinned_to_the_page():
    """★The synthesis layer replicates page rules; this ties the copies to
    the page source so an edit there fails here instead of drifting."""
    #: ★★the page file is `scenario-pulse_design.js` — the design page was
    #: renamed `design` -> `pulse_design` and this gate kept the OLD name, so
    #: `read_text` raised `FileNotFoundError` and the whole claim stopped being
    #: made.  Measured 2026-09-02: it had been failing on every run, and the
    #: 0-D mapper drifted three control names (`t_ru` / `t_ft` / `paux`) behind
    #: the page in the meantime — exactly what pinning the constants here was
    #: supposed to prevent.  A gate that names a path must fail LOUDLY when the
    #: path moves, which is why the message below now says which file.
    page = ROOT / "app/assets/scenario-pulse_design.js"
    assert page.is_file(), (
        f"the 0-D page source is not at {page.relative_to(ROOT)} — this gate "
        f"pins the synthesis layer's copies to it, so a rename must be followed "
        f"here rather than leaving the claim unmade")
    src = page.read_text()
    m = re.search(r"NT_MIN = (\d+), NT_MAX = (\d+), PTS_PER_PHASE = (\d+)",
                  src)
    assert m, f"the zerod grid constants moved in {page.name}"
    assert (cases._NT_MIN, cases._NT_MAX, cases._PTS_PER_PHASE) == tuple(
        int(g) for g in m.groups())
    #: the transport closure indices are the kernel's own table
    from fylite import kernel as K
    for idx, name in cases._CLOSURES.items():
        assert K.TRANSPORT_MODELS[name] == idx


def test_the_iter_deck_resolves_and_refuses_at_the_point_of_use():
    """The deck door generalisation, gated from both sides: the document
    resolves without an EAST filename, and an EAST-only derived name is
    refused with the group named — at use, not at load.

    ★Through :func:`device.bound`, the same bounded rebind `fylite cases
    --run` uses — which also proves the restore contract: whatever machine
    the rest of the suite had resolved is back afterwards."""
    from fylite import device
    with device.bound(ROOT / "machine_desc/iter"):
        doc = device.document()
        assert doc["machine"]["name"].lower().startswith("iter")
        with pytest.raises(device.MachineDataMissing, match="does not carry"):
            device.MDS_SERVER


def test_the_evolve_scope_ledger_names_what_is_missing():
    """★★The batch ledger, gated: what the kernel loop does NOT yet carry is
    a table (`cases._EVOLVE_UNSUNK` + four scope tests), every out-of-scope
    case is refused against it BY FEATURE, and the in-scope count may only
    grow.

    Measured after the pedestal batch (2026-08-26): 11 of 13 run.  A batch
    that sinks a feature deletes its row, which is why the assertion below
    is a FLOOR — growth needs no edit here, a regression fails.

    ★★2026-08-27, after S-2c 批二–批五: **every capability the corpus names
    is sunk**, and the two cases still refused are refused for a different
    KIND of reason — the reference file is not here.  Device and shot decks
    stay out of this repository by rule, so a case carries controls and not
    data.  The gate now holds that distinction rather than blurring it:
    「等下一批」 and 「把那份件给我」 are different sentences and only the
    second has a next move the reader can take today.
    """
    evolve = [e["case_id"] for e in cases.catalogue()
              if e["bar"] == "evolve"]
    assert len(evolve) >= 13
    ran, refused = [], {}
    for cid in evolve:
        try:
            cases.plan(cid)
            ran.append(cid)
        except SystemExit as e:
            refused[cid] = str(e)
    assert len(ran) >= 11, (
        f"only {len(ran)} evolve cases are in scope; 11 were after the "
        "pedestal was sunk (S-2c 批一) — a capability left the entry")
    capability = set(cases._EVOLVE_UNSUNK.values()) | {
        "closure", "alternation", "heat channel"}
    #: ★a refusal about DATA, which is not a capability and must not be
    #: written as one: it names the file the caller has to supply
    datum = {"equilibrium"}
    for cid, why in refused.items():
        assert any(w in why for w in capability | datum), (
            f"{cid}'s refusal names neither a capability from the scope "
            f"ledger nor the datum it wants:\n{why}")
        if any(w in why for w in datum):
            #: ★★a data refusal has to say what to DO — a reader who is
            #: told 「缺一份参考件」 and not which one, or not that they may
            #: pass it in, has been told they are stuck
            assert "equilibrium=" in why, (
                f"{cid} is refused for want of a file but does not say how "
                f"to supply it:\n{why}")


def test_a_declared_but_inert_drive_does_not_turn_a_running_case_into_a_refusal():
    """★★The trap this nearly walked into, pinned.

    ``evolve-default`` declares ``ohmic: true`` beside ``ch-current: false``,
    and the page IGNORES it there (``worker.js``: ``if (ctx.channels.current
    && sp.ohmic)``).  When the current channel was sunk (S-2c 批二) the
    obvious move was to forward every one of its switches — which would have
    handed ``model.evolve`` a drive with no channel, met the refusal that
    exists for a DIRECT caller's mistake, and turned a case that runs today
    into a case that is refused.  A switch the page ignores must be
    classified as inert here, not forwarded.

    ★And inert is not the same as unmapped: it stays in the accounting with
    a reason, so 「declared and ignored, exactly as the page ignores it」 is
    visible rather than being indistinguishable from 「nobody looked」.
    """
    _entry, doc = cases.load("evolve-default")
    cfg = cases.settings(doc)
    assert cfg.get("ohmic") and not cfg.get("ch-current"), (
        "this gate's premise is that evolve-default declares a drive with "
        "the channel off; the corpus changed, so re-read the gate")
    acct = cases.Accounting({k: v for k, v in cfg.items() if ":" not in k})
    args = cases.args_for("evolve", cfg, acct=acct)
    assert args["current"] is False
    for key in ("ohmic", "bootstrap", "v_loop"):
        assert key not in args, (
            f"{key} was forwarded with the channel off; the page ignores it "
            "there, and forwarding it refuses a case that runs")
    summary = acct.summary()
    assert not summary["unclassified"], summary["unclassified"]


def test_the_sunk_current_channel_is_reachable_through_the_case_mapper():
    """★A capability sunk into the kernel but never reachable from the corpus
    path has no reader, and 「it works」 would rest on the entry gates alone.

    Both corpus cases that ask for the current channel are still refused for
    OTHER capabilities (geometry tier, sawtooth), so the mapper's own
    forwarding is exercised here against ``evolve-default`` with the switch
    flipped — the same config, one control moved, which is what a reader of
    the page would do.
    """
    import numpy as np

    from fylite.scenario import model as M

    _entry, doc = cases.load("evolve-default")
    cfg = dict(cases.settings(doc))
    cfg["ch-current"] = True
    args = cases.args_for("evolve", cfg)
    assert args["current"] is True
    #: the drives ride along now, and they are the case's OWN values
    assert args["ohmic"] == bool(cfg["ohmic"])
    assert args["bootstrap"] == bool(cfg["bootstrap"])
    assert args["v_loop"] == pytest.approx(float(cfg["vloop"]))
    #: and it marches: q is a RESULT here, so it must be positive and
    #: rising outward — a channel that returned the zeros of an off run
    #: would satisfy every assertion above
    args["n_steps"] = min(int(args["n_steps"]), 6)
    out = M.evolve(**args)
    q = np.asarray(out["q"])
    assert np.all(q[1:] > 0.0), q
    assert q[-1] > q[1], f"q does not rise outward: {q[:3]} .. {q[-3:]}"
    assert np.any(np.asarray(out["j_bs"]) != 0.0), "no bootstrap current"


def test_the_evolve_case_runs_and_marches(run_root):
    """The end-to-end claim of the descent: a corpus case, through the CLI's
    own path, into the kernel loop, out as a recorded run."""
    r = cases.run("evolve-default")
    res = json.loads((Path(r["run_dir"]) / "result.json").read_text())
    assert res["steps"] >= 1
    import numpy as np
    d = np.load(Path(r["run_dir"]) / "arrays.npz")
    #: it HEATED — 8 MW into this plasma with the edge held
    assert d["te"][0] > d["te_init"][0]
    assert d["te"][-1] == pytest.approx(300.0), "the Dirichlet edge moved"
    #: and the two channels stayed coupled: a decoupled pair is the failure
    #: the exchange ceiling exists to prevent, and it shows up as a split
    assert abs(d["te"][0] - d["ti"][0]) / d["te"][0] < 0.5


def test_a_pedestal_case_runs_and_its_verdict_says_where_the_number_came_from(
        run_root):
    """★★The batch's end-to-end claim AND the reason its acceptance criterion
    exists: `evolve-fuse-iter` is a fixed-chi burn, so it runs away to a
    beta_N far past EPED1-NN's training range — the pedestal still ANSWERS
    (upstream warns rather than refusing), and the only thing that says the
    number came from outside the box is the extrapolation distance.

    A run like that must come back `conditional`, never `pass` and never
    `fail`: it is a statement about how far the surrogate was extrapolated,
    not about whether the plasma was favourable.
    """
    r = cases.run("evolve-fuse-iter")
    res = json.loads((Path(r["run_dir"]) / "result.json").read_text())
    acc = json.loads((Path(r["run_dir"]) / "acceptance.json").read_text())
    assert res["ped_extrapolation"] > 0, (
        "this case is the one that leaves the training box — if it stopped "
        "doing so, pick another case for this gate rather than dropping it")
    assert acc["state"] == "conditional", acc
    ped = next(c for c in acc["criteria"] if c["name"] == "ped_extrapolation")
    assert ped["state"] == "conditional"
    import numpy as np
    d = np.load(Path(r["run_dir"]) / "arrays.npz")
    #: the edge FOLLOWED the model: the last boundary the march ran under is
    #: the pedestal top the step before it handed on
    assert d["te"][-1] == pytest.approx(d["t_ped"][int(res["steps"]) - 2],
                                        rel=1e-9)


def test_every_runnable_evolve_case_closes_its_energy_books(run_root):
    """★★T-C23 across the CORPUS — the physics cross-check the ledger asks
    for, in its internal-consistency form.

    Every runnable evolve case is marched and its worst per-channel
    conservation residual read back.  The scheme conserves by construction,
    so these are machine noise; what the sweep buys over the single-case
    crate gate is coverage of the ASSEMBLY — eleven different machines,
    metrics, impurities, burns and pedestals, each of which is a fresh chance
    for a source to land on the wrong weight.

    Measured 2026-08-26: worst 9.8e-13 (evolve-fuse-manta, 400 steps).
    """
    import numpy as np
    worst, where = 0.0, None
    ran = 0
    for e in cases.catalogue():
        if e["bar"] != "evolve":
            continue
        cid = e["case_id"]
        try:
            r = cases.run(cid)
        except (SystemExit, cases.RunFailed):
            continue                      # out of scope, or the run refused; named elsewhere
        ran += 1
        res = json.loads((Path(r["run_dir"]) / "result.json").read_text())
        b = float(res["balance_worst"])
        if b > worst:
            worst, where = b, cid
        d = np.load(Path(r["run_dir"]) / "arrays.npz")
        assert (d["balance"] > 0).any(), (
            f"{cid}: not one step was audited — a checker that skips every "
            "step reports a perfect zero, which is the one answer that "
            "cannot be trusted")
    if ran == 0:
        #: ★内核不在场时，上面每一条都在 `RunFailed` 那一支被跳过 —— 那是「输入
        #: 不在」，不是「一条算例都不在范围内」。两者在断言里长得一样，所以这里
        #: 点名分开：内核在场而仍然一条没跑，才是缺陷。
        from fylite import kernel as _k
        if _k.load() is None:
            pytest.skip("the kernel is absent in this checkout: no evolve case could run")
    assert ran >= 11, f"only {ran} evolve cases ran"
    assert worst < 1e-10, (
        f"a corpus case does not close its energy books: {where} at "
        f"{worst:.2e} (measured 9.8e-13 when this landed)")
