"""The ITER passive circuit as a wall problem, run from THIS checkout (register record V-23).

★★2026-09-16 (/goal「完善磁平衡相关计算功能 … 导体壁等被动导体耦合」, the ITER side): V-21 closed the
evolution coupling on EAST.  ITER had NO passive structure reachable at all — its card carried
``pf_passive: None`` and not one of its fourteen vessel units had an ``element``, so ``code/wall`` and
``code/vstab`` saw nothing on that machine.  fydoc's ``static/now/pf_passive.jsonld`` (324 loops, discretised
from the CC BY 4.0 Zenodo original) and the generic assembler in ``tools/abox-to-facts.py`` fixed that; this
record is what the circuit then measures.

★★★**The verdict is SPLIT on purpose, and the split is the finding.**

*The resistance side agrees with the literature.*  The two shells in parallel give 7.6272 µΩ against
``ITER_D_22FPWQ``'s 7.9 µΩ — **−3.45 %**, computed two independent ways (the kernel's element resistances,
and an analytic poloidal-strip sum straight off the original wall file) that match to the digit.

*The time-constant side is NOT comparable with CREATE, and no amount of tuning would make it so.*
``ITER_D_22L4FE`` Table 4.1.a gives 1st / 2nd plasmaless time constants 0.3623 / 0.2385 s (CREATE-NL) and
0.3705 / 0.2440 s (CREATE-L).  We measure 0.5834 / 0.3049 s on VV + OTS.  Four candidate explanations were
tested and **all four were falsified**:

1. *discretisation* — coarsening 135+151 → 57+50 (CREATE's own count) → 28+25 moves τ₁ by **< 0.5 %**
   (0.568922 → 0.569345 → 0.571403);
2. *the thickened shell* — emulating CREATE's 60 → 150 mm with η_eq = 1.90 µΩ·m RAISES τ₁ by 5 %
   (0.5689 → 0.5977), the opposite direction;
3. *resistivity* — ρ/t is 12.67 (CREATE) against 13.33 (ours), a 5 % difference the wrong way;
4. *mode definition* — CREATE names its two constants by SHAPE ("nearly uniform current distribution",
   "nearly up-down antisymmetric").  Ours are like-for-like: mode k=0 has uniformity **1.0000**, mode k=1 has
   up-down antisymmetry **−0.9045**, and they are exactly the two slowest eigenvalues.

What remains is inductance, and it is not reachable: τ₁ = 0.3623 s demands L_eff = **2.76 µH** while the
uniform mode measures **5.07 µH**, and L_eff of a ring at R ≈ 5.9 m enclosing 1.56 m² is fixed by geometry —
not a fitted parameter.  The single remaining candidate is a structural difference we have not modelled:
22L4FE states "OTS **connected electrically** to the inner shell", and its ports pierce both shells, i.e.
CREATE's passive circuit has CONDUCTIVE joints, while our fourteen units are mutually coupled but galvanically
isolated rings.  Conductive shorting lowers the uniform-mode inductance — the right direction.

★**A known over-modelling of ours, recorded rather than hidden**: the three port groups are built as
CONTINUOUS toroidal rings, whereas the real machine has 18 ports about 5° wide each (~25 % toroidal duty).
Adding them drops R_parallel 7.63 → 6.10 µΩ and pushes τ₁ to 0.884 s.  The port sets are therefore recorded
but are NOT the set any comparison should use.

No card or no kernel library: the gate SKIPS by name.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
READINGS = "wall_iter.json"
REPRO_REL, REPRO_ABS = 1e-9, 1e-12

#: ★the one comparison that HOLDS: the vessel's toroidal resistance against ITER_D_22FPWQ (7.9 µΩ).
#: Band is the measured deviation rounded out; it is a literature agreement, not a second code.
V23_R_BAND = {"vv_both_R_uOhm": 7.6272, "rel_to_literature": 0.035}

#: ★the time constants are held as REadings, not as an agreement — see the module docstring for why
#: comparing them with CREATE's 0.3623 / 0.2385 s is not like-for-like.
V23_TAU = {"vv_both_tau1_s": 0.568922, "vv_ots_tau1_s": 0.583386, "vv_ots_tau2_s": 0.304886}

#: ★what CREATE's tau would demand of the inductance, and what we measure.  The gap is the record.
V23_L = {"needed_for_create_uH": 2.7633, "ours_uH": 5.0657}


def _readings() -> dict:
    p = ROOT / "docs" / "benchmark" / "readings" / READINGS
    if not p.is_file():
        pytest.skip(f"no {READINGS} recorded in docs/benchmark/readings")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def want() -> dict:
    return _readings()


def _close(g: float, w: float, rel: float = REPRO_REL) -> bool:
    return abs(g - w) <= max(REPRO_ABS, rel * abs(w))


def test_v23_the_vessel_toroidal_resistance_agrees_with_the_literature(want):
    """★The one thing this record asserts as an agreement."""
    s = want["sets"]["vv_both"]
    assert _close(s["R_toroidal_parallel_uOhm"], V23_R_BAND["vv_both_R_uOhm"], 1e-4), s
    rel = want["checks"]["R_toroidal_rel_to_literature"]
    assert abs(rel) <= V23_R_BAND["rel_to_literature"], rel


def test_v23_the_time_constants_reproduce(want):
    assert _close(want["sets"]["vv_both"]["tau_1_s"], V23_TAU["vv_both_tau1_s"], 1e-5)
    assert _close(want["sets"]["vv_ots"]["tau_1_s"], V23_TAU["vv_ots_tau1_s"], 1e-5)
    assert _close(want["sets"]["vv_ots"]["tau_2_s"], V23_TAU["vv_ots_tau2_s"], 1e-5)


def test_v23_the_modes_are_the_ones_create_names(want):
    """★The comparison is like-for-like IN DEFINITION — that is what makes the disagreement real.

    CREATE names its two constants by shape; if ours were different modes, the mismatch would be a
    bookkeeping error rather than a physics difference.  They are not different modes."""
    sh = {m["k"]: m for m in want["mode_shapes"]}
    assert sh[0]["uniformity"] > 0.99, sh[0]
    assert sh[1]["up_down_antisymmetry"] < -0.85, sh[1]
    assert sh[0]["tau_s"] > sh[1]["tau_s"] > sh[2]["tau_s"]


def test_v23_creates_time_constant_needs_an_inductance_the_geometry_cannot_give(want):
    """★Why this is `not_comparable` and not a tolerance to be widened.

    Reaching CREATE's tau_1 needs L_eff 2.76 uH where the geometry gives 5.07 uH.  A ring at R ~ 5.9 m
    enclosing 1.56 m^2 has the inductance it has."""
    c = want["checks"]
    assert _close(c["L_uniform_needed_for_create_tau1_uH"], V23_L["needed_for_create_uH"], 1e-3)
    assert _close(c["L_uniform_ours_uH"], V23_L["ours_uH"], 1e-3)
    assert c["L_uniform_ours_uH"] / c["L_uniform_needed_for_create_tau1_uH"] > 1.7


def test_v23_the_port_sets_are_recorded_but_flagged_as_over_modelled(want):
    """★The ports are continuous rings here and 18 x 5 deg in the machine; recorded, not used."""
    s = want["sets"]
    assert s["vv_ots_ports"]["R_toroidal_parallel_uOhm"] < s["vv_ots"]["R_toroidal_parallel_uOhm"]
    assert s["vv_ots_ports"]["tau_1_s"] > 1.4 * s["vv_ots"]["tau_1_s"]
