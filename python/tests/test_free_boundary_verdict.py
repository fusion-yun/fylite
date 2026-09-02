"""The free solve's three-way verdict (T-M16) and the delivered-profile tier
(T-D6′), measured on the machines this tree carries.

★★What changed and why a gate.  Until ABI v108 the free solve's convergence
claim was `residual <= tol`, computed by every caller for itself — and the
mask, which is part of the iteration's state, was in nobody's criterion.
Two failures follow, one per direction:

  * a mask still swapping cells floors the field residual, so a solve at a
    tolerance ABOVE the floor could read "converged" over a boundary that
    is being re-decided every round;
  * a mask that jitters a few cells FOREVER (quantisation noise around a
    separatrix) keeps the residual above any tight tolerance while the
    span, the axis and the topology have long stopped moving — and the
    solver reported that steady state as a plain failure.

The kernel now answers for itself: ``verdict`` = 1 (converged: residual
within tol AND mask unchanged for consecutive rounds), 2 (settled: the
answer frozen, the jitter floor named), 0 (neither).

★The EAST case here is ALSO T-D6′'s closure half: the same reference
currents that the naive boundary rule solved as a limiter plasma (saddle
read at psi_N = 1.213 on the converged field) solve DIVERTED under the
private-region guard, and the delivered p'/FF' shape puts the X point and
the midplane radii on the delivered reconstruction.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from fylite import kernel as K

ROOT = Path(__file__).resolve().parents[2]
EAST = ROOT / "machine_desc" / "east" / "fylite_device_east.json"

pytestmark = pytest.mark.skipif(not K.available(),
                                reason="kernel library absent")


def _east():
    d = json.loads(EAST.read_text())
    coils = d["pf_active"]["coil"]
    er, ez, ew, eh = (np.asarray([c["element"][0]["geometry"]["rectangle"][k]
                                  for c in coils], float)
                      for k in ("r", "z", "width", "height"))
    elems = (er, ez, ew, eh, np.zeros(er.size), np.zeros(er.size))
    rd = d["fylite:reference_discharge"]
    at = np.asarray(rd["aturns"], float)
    elcur = np.zeros(er.size)
    for ci, entries in enumerate(d["fylite:channel_map"]):
        for idx, w in entries:
            elcur[idx] += w * at[ci]
    g = d["fylite:grid"]
    rg = np.linspace(g["rmin"], g["rmax"], g["nr"])
    zg = np.linspace(g["zmin"], g["zmax"], g["nz"])
    rr, zz = np.meshgrid(rg, zg, indexing="ij")
    psi_e, _, _ = K.element_response(elems, rr.ravel(), zz.ravel(),
                                     nu=4, nv=4)
    psi_ext = (psi_e @ elcur).reshape(g["nr"], g["nz"])
    lim = d["wall"]["description_2d"][0]["limiter"]["unit"][0]["outline"]
    return (d, rd, rg, zg, psi_ext,
            np.asarray(lim["r"], float), np.asarray(lim["z"], float))


@pytest.fixture(scope="module")
def east():
    if not EAST.exists():
        pytest.skip("no EAST description in this tree")
    return _east()


def test_the_reference_discharge_solves_diverted_not_limited(east):
    """T-D6′, the root cause half: the naive max-flux boundary rule read a
    wall point in the PRIVATE flux region as the limiter contact, which
    pushed psi_b toward the axis and put the true saddle outside psi_N = 1
    — 20 target scans never got a divertor and the entry blamed the
    profile family.  Under the 0.75|Z_x| guard the same currents, the same
    grid and the same analytic family classify diverted."""
    d, rd, rg, zg, psi_ext, lr, lz = east
    res = K.gs_free_solve(rg, zg, psi_ext, ip=rd["ip"], limiter_r=lr,
                          limiter_z=lz, beta0=0.55, emp=1.0, enp=1.0,
                          r0=1.75, relax=0.3, max_iter=4000, tol=1e-9,
                          fb_gain=8.0)
    assert res["bnd_kind"] == 1, (
        "EAST's own reference discharge must solve diverted — the "
        "delivered reconstruction is diverted, and the limiter verdict "
        "was the naive boundary rule's private-region misread")
    #: the delivered X point is (1.606, -0.7215); the solved one must be
    #: in its neighbourhood, not at some other saddle
    assert abs(res["xpt_z"] - (-0.7215)) < 0.15
    assert abs(res["xpt_r"] - 1.606) < 0.15


def test_the_delivered_profile_tier_reproduces_the_reconstruction(east):
    """T-D6′, the closure half: the delivered p'/FF' — which the analytic
    family cannot represent (sign reversal at psi_N ≈ 0.82) — used as a
    shape and normalised to the delivered Ip, on the delivered coil
    currents, must land on the delivered reconstruction's geometry."""
    d, rd, rg, zg, psi_ext, lr, lz = east
    dl = rd["delivered"]
    res = K.gs_free_solve_tab(
        rg, zg, psi_ext, x=np.asarray(dl["psi_norm"], float),
        pprime=np.asarray(dl["dpressure_dpsi"], float),
        ffprime=np.asarray(dl["f_df_dpsi"], float), ip=rd["ip"],
        limiter_r=lr, limiter_z=lz, relax=0.3, max_iter=4000, tol=1e-9,
        fb_gain=8.0)
    assert res["bnd_kind"] == 1
    #: delivered: X (1.606, -0.7215), R0 1.814, a 0.440.  The measured
    #: agreement is X (1.624, -0.660), R0 1.814, a 0.453 — the bounds are
    #: set a little outside that, NOT at "anything goes": the analytic
    #: family misses a by 0.05 and R0 by 0.05, and must keep failing them.
    assert abs(res["xpt_r"] - 1.606) < 0.05
    assert abs(res["xpt_z"] - (-0.7215)) < 0.10
    #: midplane radii off the solved field itself
    j = int(round((res["axis_z"] - zg[0]) / (zg[1] - zg[0])))
    row = res["psi"][:, j]
    pb = res["psi_bnd"]
    i0 = int(round((res["axis_r"] - rg[0]) / (rg[1] - rg[0])))
    ri = ro = np.nan
    for i in range(i0, 0, -1):
        if (row[i] - pb) * (row[i - 1] - pb) <= 0:
            t = (pb - row[i]) / (row[i - 1] - row[i])
            ri = rg[i] + t * (rg[i - 1] - rg[i])
            break
    for i in range(i0, rg.size - 1):
        if (row[i] - pb) * (row[i + 1] - pb) <= 0:
            t = (pb - row[i]) / (row[i + 1] - row[i])
            ro = rg[i] + t * (rg[i + 1] - rg[i])
            break
    a, r0 = (ro - ri) / 2, (ro + ri) / 2
    assert abs(r0 - 1.814) < 0.03, r0
    assert abs(a - 0.440) < 0.03, a


def test_the_settled_verdict_is_the_jitter_floor_not_a_failure(east):
    """T-M16: on the EAST reference the mask quantisation-jitters a few
    cells forever (measured 3-8 of ~2000 per round) and the residual
    floors at 2e-3…8e-3 — under the old criterion that ran to any cap and
    exited "failed".  The kernel now stops when the answer stops moving
    and says WHICH thing happened: settled, not converged, and the answer
    it returns sits inside the long-run jitter band."""
    d, rd, rg, zg, psi_ext, lr, lz = east
    dl = rd["delivered"]
    kw = dict(x=np.asarray(dl["psi_norm"], float),
              pprime=np.asarray(dl["dpressure_dpsi"], float),
              ffprime=np.asarray(dl["f_df_dpsi"], float), ip=rd["ip"],
              limiter_r=lr, limiter_z=lz, relax=0.3, tol=1e-9, fb_gain=8.0)
    res = K.gs_free_solve_tab(rg, zg, psi_ext, max_iter=4000, **kw)
    assert res["settled"] and not res["converged"]
    assert res["verdict"] == 2.0
    #: it STOPPED — the whole point of naming the floor is not to burn
    #: the rest of a 4000-round budget circling it
    assert res["iterations"] < 400
    assert 0 < res["mask_delta"] <= 20
    #: the settled answer is the long-run answer: span within the
    #: measured jitter band (caps 2960-3000: -1.0091..-1.0111)
    span = res["psi_bnd"] - res["psi_axis"]
    assert abs(span - (-1.0101)) < 0.005, span


def test_the_synthetic_machine_still_converges_outright():
    """The strict verdict must remain reachable: a limiter-bounded
    synthetic plasma (no separatrix for the mask to quantise around)
    converges, and its mask is still on exit."""
    nr = nz = 33
    rg = np.linspace(1.0, 2.6, nr)
    zg = np.linspace(-0.8, 0.8, nz)
    rr, zz = np.meshgrid(rg, zg, indexing="ij")
    fil_r = np.array([3.0, 3.0])
    fil_z = np.array([0.9, -0.9])
    cur = np.array([-8.0e5, -8.0e5])
    elems = (fil_r, fil_z, np.full(2, 0.01), np.full(2, 0.01),
             np.zeros(2), np.zeros(2))
    pe, _, _ = K.element_response(elems, rr.ravel(), zz.ravel(), nu=1, nv=1)
    psi_ext = (pe @ cur).reshape(nr, nz)
    th = np.linspace(0, 2 * np.pi, 41)
    res = K.gs_free_solve(rg, zg, psi_ext, ip=5e5,
                          limiter_r=1.8 + 0.7 * np.cos(th),
                          limiter_z=0.72 * np.sin(th), beta0=0.5, emp=1.0,
                          enp=1.5, r0=1.8, relax=0.4, max_iter=800,
                          tol=1e-9, fb_gain=8.0)
    assert res["converged"] and not res["settled"]
    assert res["verdict"] == 1.0
    assert res["residual"] <= 1e-9
