"""One admitted case, exported as ONE fyo/JSON-LD scenario, re-run by the runtime.

★What is gated: `tools/export-case-scenario.py` writes a single document whose
inputs are inline and whose process is an ordered list of steps; the runtime's
stepped runner (`fylite_runtime::case::run_steps`, behind
`fylite.io.fydoc.case_json` and `fy run <file>`) runs it end to end — every step
completes, the current is held, the ladder's q is ONETWO's to the measured band,
and the ray traces.  The numbers are the kernel's own 20 MA chain gate
(`the_20ma_chain_runs_from_the_document_alone`), measured 2026-09-11 and pinned
there; here they are re-read through the public door.

★★The case's values are `release: internal`: the test reads them from a fydoc
checkout named by `$FYDOC_ORACLE` (skipped without one), writes the scenario
into a temporary directory and never into this repository.  ONETWO's q is read
straight from the statefile for the comparison — nothing of the case is copied
here.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPORTER = ROOT / "tools/export-case-scenario.py"
#: the two admitted CFEDR cases: the statefile under `corpus/`, and the numbers
#: the chain's first current half was MEASURED to give (2026-09-11/12) — the
#: reference value where the delivery states one (CASE-21's summary V_loop
#: 0.02 V), else the measurement itself as a regression pin
CASES = {
    "FYDOC-CASE-21-cfedr-hmode-20ma": {"state": "corpus/CFEDR_260114/ONETWO/FILES/statefile_3.000000E+01.nc",
                                       "v_loop": (0.02, 0.012), "ip_ka": 20037.1, "q_median": 0.02, "q_worst": 0.35},
    "FYDOC-CASE-20-cfedr-hmode-15ma": {"state": "corpus/H model 15MA 20240522/statefile_1.200000E+01.nc",
                                       "v_loop": (0.0256, 0.005), "ip_ka": 15000.0, "q_median": 0.02, "q_worst": 0.35},
}


def _case_dir(case: str) -> pathlib.Path | None:
    root = os.environ.get("FYDOC_ORACLE")
    if not root:
        return None
    d = pathlib.Path(root) / "cases" / case
    return d if (d / "case.yaml").is_file() and (d / CASES[case]["state"]).is_file() else None


@pytest.fixture(scope="module", params=list(CASES))
def scenario(request, tmp_path_factory) -> tuple[str, dict, pathlib.Path]:
    case = request.param
    case_dir = _case_dir(case)
    if case_dir is None:
        pytest.skip(f"no fydoc checkout with {case} ($FYDOC_ORACLE)")
    pytest.importorskip("netCDF4")
    from fylite._paths import KERNEL_LIB
    if not KERNEL_LIB.exists():
        pytest.skip("no kernel (rust/build.sh)")
    out = tmp_path_factory.mktemp(case[:14]) / "scenario.jsonld"
    r = subprocess.run([sys.executable, str(EXPORTER), "--fydoc", str(case_dir.parents[1]), "--case", case,
                        "--rounds", "3", "-o", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return case, json.loads(out.read_text(encoding="utf-8")), out


def test_the_export_is_one_self_contained_document(scenario):
    _case, doc, path = scenario
    steps = doc["has_occurrent_part"]
    assert [s["prescribes_code"]["id"] for s in steps] == (
        ["code/ladder"] + ["code/steady_current", "code/steady_equilibrium"] * 3 + ["code/rf_ray"])
    #: every binding is a document or a reference to a step's document — no file, no URI
    for s in steps:
        for b in s["inputs"]:
            assert "bound_to" in b and "bound_endpoint" not in b, (s["id"], b["binds_port"])
    #: the provenance names the bodies by path + sha256, which is how a body under
    #: `cases/` is reached; the document links nothing
    assert all(len(src["fylite:sha256"]) == 64 for src in doc["dcterms:source"])
    text = path.read_text(encoding="utf-8")
    assert "href" not in text and "](" not in text
    assert doc["dcterms:rights"].startswith("release: internal")


@pytest.fixture(scope="module")
def record(scenario) -> tuple[str, dict]:
    from fylite.io import fydoc
    case, doc, path = scenario
    return case, fydoc.case_json(doc, base=path.parent)


def test_every_step_runs_through_the_public_door(record):
    _case, record = record
    assert record["run_state"] == "succeeded", record.get("comment")
    assert record["fylite:steps_run"] == record["fylite:steps_planned"] == 8
    for s in record["fylite:steps"]:
        assert s["run_state"] == "succeeded", (s["id"], s.get("comment"))


def _outputs(record) -> dict[str, dict]:
    return {o["binds_port"]["port_name"]: o["bound_to"] for o in record["inputs"]
            if o["binds_port"].get("port_direction") == "output"}


def test_the_ladders_q_is_onetwos_on_its_own_rows(record):
    """★Measured 2026-09-11 (kernel gate): median q/q_ONETWO − 1 = +9.8e-3 on 175
    rows, worst +0.26 at the edge — the rho-mapping difference S1 recorded."""
    import netCDF4
    case, record = record
    out = _outputs(record)
    lad = out["ladder/equilibrium"]["time_slice"]
    lad = lad[0] if isinstance(lad, list) else lad
    q = np.asarray(lad["profiles_1d"]["q"], float)
    psin = np.asarray(lad["profiles_1d"]["fylite:psi_norm"], float)
    d = netCDF4.Dataset(str(_case_dir(case) / CASES[case]["state"]))
    pa, pb = float(d.variables["psiaxis"][:]), float(d.variables["psibdry"][:])
    x = (np.asarray(d.variables["psir_grid"][:], float) - pa) / (pb - pa)
    q_ref = np.interp(psin, x, np.asarray(d.variables["q_value"][:], float))
    assert np.sign(q[1]) == np.sign(q_ref[1]), "q keeps the document's sign (B_T < 0 on CASE-21)"
    rel = q[1:] / q_ref[1:] - 1.0
    print(f"{case}: ladder q/q_ONETWO - 1 median {float(np.median(rel)):+.3e}, worst {float(np.max(np.abs(rel))):.3e}")
    assert abs(float(np.median(rel))) < CASES[case]["q_median"], float(np.median(rel))
    assert float(np.max(np.abs(rel))) < CASES[case]["q_worst"], float(np.max(np.abs(rel)))


def test_the_current_is_held_and_the_map_settles(record):
    """★Measured 2026-09-11: round 1 V_loop 0.0239 V (ONETWO 0.02), q0 1.490 (ONETWO
    1.425); max|dpsi| 1.06e-1 · 7.5e-2 · 4.8e-2 over three rounds."""
    case, record = record
    want, tol = CASES[case]["v_loop"]
    ip, first = None, True
    for s in record["fylite:steps"]:
        if s["executed_code"]["id"] == "code/steady_current":
            line = next(c for c in s["comment"] if c.startswith("steady current"))
            ip = float(line.split("I_p")[1].split("kA")[0])
            v = float(line.split("V_loop")[1].split("V")[0])
            if first:
                print(f"{case}: round 1 V_loop {v:.4f} V (pinned {want} ± {tol})")
                assert abs(v - want) < tol, line
                first = False
    assert ip is not None and abs(ip / CASES[case]["ip_ka"] - 1.0) < 0.02


def test_the_ray_traces_on_the_re_solved_map(record):
    _case, record = record
    rf = record["fylite:steps"][-1]
    assert rf["executed_code"]["id"] == "code/rf_ray"
    notes = " ".join(rf["comment"])
    assert "absorbed fraction" in notes and "F read on the document's own psi_N rows" in notes, notes
