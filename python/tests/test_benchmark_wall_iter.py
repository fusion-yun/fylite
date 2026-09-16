"""The ITER passive circuit as a wall problem, run from THIS checkout (register record V-23).

★★2026-09-16 (/goal「完善磁平衡相关计算功能 … 导体壁等被动导体耦合」, the ITER side): V-21 closed the
evolution coupling on EAST.  ITER had NO passive structure reachable at all — its card carried
``pf_passive: None`` and not one of its fourteen vessel units had an ``element``, so ``code/wall`` and
``code/vstab`` saw nothing on that machine.  fydoc's ``static/now/pf_passive.jsonld`` (324 loops, discretised
from the CC BY 4.0 Zenodo original) and the generic assembler in ``tools/abox-to-facts.py`` fixed that; this
record is what the circuit then measures.

★★★**Two comparisons, and the second one took a wrong turn first — both are recorded.**

*The resistance side agrees with the literature.*  The two shells in parallel give 7.6272 µΩ against
``ITER_D_22FPWQ``'s 7.9 µΩ — **−3.45 %**, computed two independent ways (the kernel's element resistances,
and an analytic poloidal-strip sum straight off the original wall file) that match to the digit.

*The time constants agree ONCE THE SUPERCONDUCTING CIRCUITS ARE INCLUDED.*  ``ITER_D_22L4FE`` Table 4.1.a
gives 1st / 2nd plasmaless time constants 0.3623 / 0.2385 s (CREATE-NL) and 0.3705 / 0.2440 s (CREATE-L).
A bare vessel circuit measures 0.5834 / 0.3049 s on VV + OTS — **57 % high**.  Four candidate explanations
were tested and all four were falsified:

1. *discretisation* — coarsening 135+151 → 57+50 (CREATE's own count) → 28+25 moves τ₁ by **< 0.5 %**;
2. *the thickened shell* — emulating CREATE's 60 → 150 mm with η_eq = 1.90 µΩ·m RAISES τ₁ by 5 %;
3. *resistivity* — ρ/t is 12.67 (CREATE) against 13.33 (ours), a 5 % difference the wrong way;
4. *mode definition* — CREATE names its two constants by SHAPE ("nearly uniform current distribution",
   "nearly up-down antisymmetric").  Ours are like-for-like: mode k=0 has uniformity **1.0000**, mode k=1 has
   up-down antisymmetry **−0.9045**, and they are exactly the two slowest eigenvalues.

★**A fifth explanation was then proposed and it too was falsified**: that CREATE's passive circuit has
CONDUCTIVE joints (22L4FE does say "OTS connected electrically to the inner shell") while ours are
galvanically isolated rings.  For n = 0 toroidal eddy currents the rings couple only inductively, and a
radial joint merely redistributes current between shells — which the parallel resistance already carries.
Forcing the two shells onto one circuit reproduces the uniform mode that is already being solved.

★★★**What actually explains it is in the same document, one page earlier**: 22L4FE p.2 states "All
resistances (in SC coils, voltage amplifiers, connections) are **neglected**", and CREATE's plasmaless
matrices L₀ / R₀ carry the eleven PF/CS circuit loops.  **Zero-resistance loops conserve flux and SCREEN the
vessel modes.**  With the coils eliminated as flux conservers,
``L_eff = M_vv − M_vc M_cc⁻¹ M_cv`` (a Schur complement), the uniform-mode inductance falls 5.076 → 2.923 µH
and τ₁ falls 0.5834 → **0.3418 s**, i.e. −5.66 % against CREATE-NL's 0.3623 s.

★**Honest about the residual**: our own spread from how the COIL self-inductance is taken is **wider than the
remaining disagreement** — a = 0.25 m gives 0.3717 s, a from the rectangle (one filament, the kernel's own
a_eq convention, and the value reported here) 0.3418 s, a from the rectangle at 3×3 subdivision 0.3257 s.
CREATE's 0.3623 s sits inside that band.  So the claim is "agrees within our uncertainty", NOT "matches".
Two things that do NOT matter, both measured: the circuit topology (twelve independent coils and the eleven
real loops of Tables 2.1.b–f give the same L_eff to the digit) and whose coil geometry is used (the card's
2ACJT3 v3.1 gives 0.3418 s, 22L4FE's own Table 2.1.a gives 0.3395 s).

★**A known over-modelling of ours, recorded rather than hidden**: the three port groups are built as
CONTINUOUS toroidal rings, whereas the real machine has 18 ports about 5° wide each (~25 % toroidal duty).
Adding them drops R_parallel 7.63 → 6.10 µΩ and pushes the bare τ₁ to 0.884 s.  The port sets are therefore
recorded but are NOT the set any comparison should use.

No card or no kernel library: the gate SKIPS by name.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
READINGS = "wall_iter.json"
REPRO_REL, REPRO_ABS = 1e-9, 1e-12

#: ★the vessel's toroidal resistance against ITER_D_22FPWQ (7.9 µΩ) — a literature agreement.
V23_R_BAND = {"vv_both_R_uOhm": 7.6272, "rel_to_literature": 0.035}

#: ★the BARE circuit (no screening): recorded so the 57 % excess stays visible in the register.
V23_TAU_BARE = {"vv_both_tau1_s": 0.568922, "vv_ots_tau1_s": 0.583386, "vv_ots_tau2_s": 0.304886}

#: ★the SCREENED circuit — the like-for-like comparison with CREATE.  Reported value takes the coil
#: self-inductance from the rectangle with one filament (the kernel's own a_eq convention).
V23_TAU_SCREENED = {"vv_ots_tau1_s": 0.3418, "vv_ots_tau2_s": 0.2251, "rel_to_create_nl": 0.08}

#: ★our own spread from the coil self-inductance convention — it must CONTAIN CREATE's value, which is the
#: honest form of "they agree": the residual disagreement is smaller than our own uncertainty.
V23_BAND_CONTAINS_CREATE = {"lo": 0.3257, "hi": 0.3717, "create_nl": 0.3623, "create_l": 0.3705}

#: ★screening drops the uniform-mode inductance by about a third; that IS the explanation.
V23_L = {"unscreened_uH": 5.0657, "screened_uH": 2.9152}


@pytest.fixture(scope="module")
def want() -> dict:
    p = ROOT / "docs" / "benchmark" / "readings" / READINGS
    if not p.is_file():
        pytest.skip(f"no {READINGS} recorded in docs/benchmark/readings")
    return json.loads(p.read_text(encoding="utf-8"))


def _close(g: float, w: float, rel: float = REPRO_REL) -> bool:
    return abs(g - w) <= max(REPRO_ABS, rel * abs(w))


def test_v23_the_vessel_toroidal_resistance_agrees_with_the_literature(want):
    s = want["sets"]["vv_both"]
    assert _close(s["R_toroidal_parallel_uOhm"], V23_R_BAND["vv_both_R_uOhm"], 1e-4), s
    assert abs(want["checks"]["R_toroidal_rel_to_literature"]) <= V23_R_BAND["rel_to_literature"]


def test_v23_the_bare_time_constants_reproduce(want):
    """The bare circuit is 57 % above CREATE — kept in the register, not quietly dropped."""
    assert _close(want["sets"]["vv_both"]["tau_1_s"], V23_TAU_BARE["vv_both_tau1_s"], 1e-5)
    assert _close(want["sets"]["vv_ots"]["tau_1_s"], V23_TAU_BARE["vv_ots_tau1_s"], 1e-5)
    assert _close(want["sets"]["vv_ots"]["tau_2_s"], V23_TAU_BARE["vv_ots_tau2_s"], 1e-5)


def test_v23_the_modes_are_the_ones_create_names(want):
    """★The comparison is like-for-like IN DEFINITION, which is what makes it a comparison at all."""
    sc = want["screening"]
    assert sc["topology_independent"]["12_independent_coils"]["tau_1_s"] > 0
    assert want["sets"]["vv_ots"]["tau_1_s"] > want["sets"]["vv_ots"]["tau_2_s"]


def test_v23_screening_by_the_superconducting_circuits_closes_the_gap(want):
    """★The finding: zero-resistance PF/CS loops conserve flux and screen the vessel modes."""
    s = want["sets"]["vv_ots"]["sc_screened"]["a_rect_1fil"]
    assert _close(s["tau_1_s"], V23_TAU_SCREENED["vv_ots_tau1_s"], 1e-3), s
    assert abs(want["checks"]["tau1_screened_vs_create_nl"]) <= V23_TAU_SCREENED["rel_to_create_nl"]
    c = want["checks"]
    assert _close(c["L_uniform_unscreened_uH"], V23_L["unscreened_uH"], 1e-3)
    assert _close(c["L_uniform_screened_uH"], V23_L["screened_uH"], 1e-3)
    assert c["L_uniform_screened_uH"] < 0.65 * c["L_uniform_unscreened_uH"]


def test_v23_our_own_uncertainty_band_contains_creates_value(want):
    """★The honest form of agreement: our spread from the coil self-inductance convention is WIDER
    than what is left of the disagreement, and it brackets CREATE."""
    lo, hi = want["checks"]["tau1_screened_band"]
    assert _close(lo, V23_BAND_CONTAINS_CREATE["lo"], 1e-3)
    assert _close(hi, V23_BAND_CONTAINS_CREATE["hi"], 1e-3)
    assert lo < V23_BAND_CONTAINS_CREATE["create_nl"] < hi
    assert lo < V23_BAND_CONTAINS_CREATE["create_l"] < hi


def test_v23_neither_circuit_topology_nor_coil_geometry_changes_the_answer(want):
    """★Two things that could have explained it and do not — measured, so they stay settled."""
    t = want["screening"]["topology_independent"]
    assert _close(t["12_independent_coils"]["L_uniform_uH"], t["11_circuit_loops_tab_2_1_b_f"]["L_uniform_uH"], 1e-6)
    assert _close(t["12_independent_coils"]["tau_1_s"], t["11_circuit_loops_tab_2_1_b_f"]["tau_1_s"], 1e-3)
    g = want["screening"]["coil_geometry_independent"]
    assert abs(g["card_2ACJT3_v3_1"]["tau_1_s"] / g["22L4FE_table_2_1_a"]["tau_1_s"] - 1.0) < 0.02


def test_v23_the_door_itself_now_yields_the_screened_spectrum(want):
    """★2026-09-16: the elimination moved INTO the kernel (`code/wall` gained `screen_coils`).

    Before this, the screened spectrum was computed record-side and nothing in the register would
    have gone red if the kernel drifted.  The door's value is now the reading; the record-side
    number is kept beside it as an independent cross-check, and the two must agree.

    ★They are computed differently on purpose — the kernel takes the coil self-inductance from
    8x8 filaments, the record-side check from the analytic ring formula on the equal-area radius —
    so this asserts AGREEMENT, not identity."""
    for lab in ("vv_both", "vv_ots"):
        sc = want["sets"][lab]["sc_screened"]
        assert "door" in sc, f"{lab}: no door reading — re-run with a kernel carrying `screen_coils`"
        assert sc["door"]["n_coils"] == 12, sc["door"]
        rel = sc["door_vs_record_side_rel"]
        assert abs(rel) < 5e-3, (lab, rel, sc["door"]["tau_1_s"], sc["a_rect_1fil"]["tau_1_s"])
        #: screening can only shorten the decay
        assert sc["door"]["tau_1_s"] < want["sets"][lab]["tau_1_s"]


def test_v23_the_doors_screened_tau_stays_in_the_band_against_create(want):
    """★The comparison of record: the door's own number against CREATE, with the same 8 % tolerance
    the record declares (our coil self-inductance spread is wider than what is left of the gap)."""
    assert abs(want["checks"]["tau1_door_vs_create_nl"]) <= V23_TAU_SCREENED["rel_to_create_nl"]
    lo, hi = want["checks"]["tau1_screened_band"]
    assert lo < want["checks"]["tau1_door_screened_vv_ots"] < hi


def test_v23_the_port_sets_are_recorded_but_flagged_as_over_modelled(want):
    s = want["sets"]
    assert s["vv_ots_ports"]["R_toroidal_parallel_uOhm"] < s["vv_ots"]["R_toroidal_parallel_uOhm"]
    assert s["vv_ots_ports"]["tau_1_s"] > 1.4 * s["vv_ots"]["tau_1_s"]
