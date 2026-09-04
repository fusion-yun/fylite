"""The evolve_heat scenario entry: the browser's heat-channel loop, sunk.

★★批一（S-2 / `FYL-REPORT-03` §10.3, 2026-08-26 裁定「内核下沉 + 双薄面」）：
the 含时演化 bar's outer time loop moved into the kernel as a declared
scenario entry.  What these gates hold:

* the entry is DECLARED into both hosts (the generated interface files);
* the sunk loop equals an EXPLICIT Python-driven loop of the same kernel
  calls, bit for bit — the loop-sinking correctness claim, from this face
  (the Rust suite holds the same claim from inside the crate);
* the browser loop's two hard-won rules survive the descent: sources are
  rebuilt every step (a burning plasma may not batch its steps), and the
  exchange ceiling binds and is COUNTED;
* refusals stay refusals: radiation with no named bulk, an impurity this
  batch cannot radiate honestly.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from fylite import kernel as K

ROOT = Path(__file__).resolve().parents[2]

#: deuteron mass [g] — the same constant the worker passes (EV_MD_G)
MD_G = 3.3435837724e-24


def _config(n=25, nt=12):
    """evolve-default-like numbers on an ITER-ish minor radius."""
    rho = np.linspace(0.0, 2.0, n)
    r0 = 6.2
    vprime = 4.0 * np.pi ** 2 * r0 * rho
    rb = rho / rho[-1]
    return {
        "n": n, "nt": nt, "rho": rho, "vprime": vprime,
        "gm3": np.ones(n),
        "te0": 300.0 + 2700.0 * (1.0 - rb ** 2),
        "ti0": 300.0 + 2200.0 * (1.0 - rb ** 2),
        "ne": 1.0e20 * (0.5 + 0.5 * (1.0 - rb ** 2)),
    }


def _params(**over):
    p = {"b0": 5.3, "chi0": 0.4, "chi_ratio": 1.0,
         "edge_te": 300.0, "edge_ti": 300.0,
         "dt": 0.002, "dt_target": 0.02, "dt_min": 1e-5, "dt_max": 0.02,
         "d_pc": 0.0, "p_e": 4.0e6, "p_i": 4.0e6,
         "dep_centre": 0.0, "dep_width": 0.3,
         "brem": 1.0, "bulk_id": K.adas_id("D"),
         "imp_id": -1.0, "imp_conc": 0.0, "imp_z": 0.0,
         "alpha": 0.0, "dt_fraction": 0.5, "zeff": 1.5,
         "pedestal": 0.0, "ip": 15.0e6, "a": 2.0, "r0": 6.2,
         "kappa": 1.86, "delta": 0.48}
    p.update(over)
    return p


def _run_entry(cfg, params):
    return K.scenario("evolve_heat", params=params,
                      inputs={"rho": cfg["rho"], "vprime": cfg["vprime"],
                              "gm3": cfg["gm3"], "te_init": cfg["te0"],
                              "ti_init": cfg["ti0"], "ne": cfg["ne"]},
                      n=cfg["n"], nt=cfg["nt"])


def _vol_int(rho, vprime, f):
    s = 0.0
    for i in range(1, len(rho)):
        s += 0.5 * (f[i] * vprime[i] + f[i - 1] * vprime[i - 1]) \
            * (rho[i] - rho[i - 1])
    return s


def test_the_entry_is_declared_into_both_hosts():
    from fylite import _fyo_interface as FI
    assert "evolve_heat" in FI.ENTRIES
    js = (ROOT / "app/assets/fyo-interface.js").read_text()
    assert "evolve_heat" in js, "run rust/build.sh"


def test_the_sunk_loop_equals_the_explicit_python_loop():
    """★★The claim that makes this a DESCENT and not a third implementation:
    the entry's answer is the answer of driving the same kernel calls step
    by step from this host — bit for bit, dt for dt."""
    cfg = _config()
    n, nt = cfg["n"], cfg["nt"]
    got = _run_entry(cfg, _params())

    # --- the reference: the browser loop's rules, spelled out here --------
    rb = cfg["rho"] / cfg["rho"][-1]
    shape = np.exp(-((rb - 0.0) / 0.3) ** 2)
    norm = _vol_int(cfg["rho"], cfg["vprime"], shape)
    heat_e = shape * 4.0e6 / norm
    heat_i = shape * 4.0e6 / norm
    ne_cgs = cfg["ne"] * 1e-6

    te, ti = cfg["te0"].copy(), cfg["ti0"].copy()
    dt_now = 0.002
    last_nu = {"nu": None}
    dts = []
    for _stp in range(nt):
        q_e = heat_e - K.rad_ion(te, ne_cgs, ne_cgs, [1.0],
                                 ["D"])["total"] * 0.1
        dt_max_now = 0.02
        if last_nu["nu"] is not None:
            nu = float(np.max(last_nu["nu"]))
            if nu > 0:
                cap = 0.25 / nu
                dt_max_now = min(dt_max_now, cap)
                dt_now = min(dt_now, cap)

        def closure(state):
            cr = K.collision_rates(state["ne"] * 1e-6, state["te"],
                                   state["ne"] * 1e-6, state["ti"],
                                   mass=[MD_G], z=[1.0], therm=[1.0])
            last_nu["nu"] = cr["nu_exch"]
            sx = K.exchange_power(cr["nu_exch"], state["ne"] * 1e-6,
                                  state["te"], state["ti"]) * 0.1
            chi_i = np.full(len(state["te"]), 0.4)
            return {"chi_e": chi_i * 1.0, "chi_i": chi_i, "s_exchange": sx}

        res = K.core_march(cfg["rho"], te=te, ti=ti, ni=cfg["ne"],
                           z=[1.0], edge_ni=[cfg["ne"][-1]],
                           psi=np.zeros(n), vprime=cfg["vprime"],
                           gm3=cfg["gm3"], gm2=cfg["gm3"],
                           fpol=np.ones(n), b0=5.3,
                           q_e=q_e, q_i=heat_i, s_n=np.zeros(n),
                           closure=closure, dt=dt_now, dt_target=0.02,
                           dt_min=min(1e-5, dt_max_now), dt_max=dt_max_now,
                           edge_te=300.0, edge_ti=300.0,
                           max_outer=1, heat=True)
        te, ti = res["te"], res["ti"]
        dt_now = res["dt"]
        dts.append(res["dt"])
        if res["steady"]:
            break

    assert int(got["steps"]) == len(dts)
    np.testing.assert_array_equal(got["te"], te)
    np.testing.assert_array_equal(got["ti"], ti)
    np.testing.assert_array_equal(got["dt_used"][:len(dts)], dts)


def test_sources_are_rebuilt_every_step():
    """★the physics requirement that forced one-step-per-call in the browser:
    the radiation follows the temperature the march is moving, so its trace
    must CHANGE while the temperature does."""
    cfg = _config()
    got = _run_entry(cfg, _params())
    steps = int(got["steps"])
    assert steps >= 3
    p_rad = got["p_rad"][:steps]
    assert p_rad.min() > 0
    assert np.unique(p_rad).size > 1, (
        "a constant radiation trace under a moving temperature means the "
        "sources were computed once — the batching the loop exists to avoid")


def test_the_exchange_ceiling_binds_and_is_counted():
    """★with a wide Te-Ti split and a greedy dt, the quarter-exchange-time
    cap must bind, and the report must say how often."""
    cfg = _config()
    #: colder, denser: nu_exch grows ~ n_e / T^1.5, so the cap comes down
    cfg["te0"] = 100.0 + 900.0 * (1.0 - (cfg["rho"] / cfg["rho"][-1]) ** 2)
    cfg["ti0"] = cfg["te0"] * 0.5
    cfg["ne"] = np.full(cfg["n"], 3.0e20)
    got = _run_entry(cfg, _params(dt=0.05, dt_max=0.5, dt_target=0.5))
    assert int(got["dt_capped"]) > 0, (
        "the exchange ceiling never engaged — the decoupling guard is gone")


def test_refusals_stay_refusals():
    cfg = _config()
    with pytest.raises(K.KernelError):
        _run_entry(cfg, _params(bulk_id=-1.0))          # radiation, no bulk
    with pytest.raises(K.KernelError):
        _run_entry(cfg, _params(imp_id=10.0, imp_conc=0.01))  # not this batch


def _hand_written_march(src_text: str) -> dict:
    """The JS the browser's own time loop is WRITTEN OUT IN, measured.

    The per-step loop body of ``evolveRun`` plus the transitive closure of
    every function it calls — with kernel calls (``fy.*``) removed before
    the scan, because a call into the kernel is the opposite of a
    hand-written semantic.

    Returns ``{"loop", "called", "total", "functions"}``.
    """
    import re

    lines = src_text.split("\n")

    def extent(i):
        depth, started = 0, False
        for k in range(i, len(lines)):
            for ch in lines[k]:
                if ch == "{":
                    depth += 1
                    started = True
                elif ch == "}":
                    depth -= 1
                    if started and depth == 0:
                        return i, k
        return i, len(lines) - 1

    fn = {}
    for i, ln in enumerate(lines):
        m = re.match(r"function ([A-Za-z_$][\w$]*)\s*\(", ln)
        if m:
            fn[m.group(1)] = extent(i)

    def called(a, b):
        seg = "\n".join(lines[a:b + 1])
        seg = re.sub(r"\bfy\.\w+", "", seg)
        return {c for c in re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", seg)
                if c in fn}

    a0, b0 = fn["evolveRun"]
    stp = next(i for i in range(a0, b0)
               if "for (var stp = 0; stp < take; stp++)" in lines[i])
    sa, sb = extent(stp)
    seen, frontier = set(), called(sa, sb)
    while frontier:
        nxt = set()
        for f in frontier:
            if f in seen:
                continue
            seen.add(f)
            nxt |= called(*fn[f])
        frontier = nxt - seen
    def weigh(a, b):
        """Lines where the host DECIDES, not where it delegates or explains.

        ★★Three exclusions, each with a reason the counter-proof checks:

        * a line carrying a ``fy.*`` call is the host handing the question
          to the kernel — the opposite of a hand-written semantic, and
          counting it would make「改调条目」read as growth, which is the
          exact failure that retired the old proxy;
        * COMMENTS and blank lines never count.  A ratchet that charges for
          explaining a decision teaches the opposite of what this repository
          wants, and it did: a batch here once spent an afternoon shrinking
          prose to hold a line count while the code stood still;
        * a bare brace or ``else`` carries nothing either.
        """
        n = 0
        for ln in lines[a:b + 1]:
            t = ln.strip()
            if not t or t.startswith(("//", "/*", "*", "*/")):
                continue
            if t in ("{", "}", "});", "};", "} else {", ")", ");"):
                continue
            if re.search(r"\bfy\.\w+", ln):
                continue
            n += 1
        return n

    body = weigh(sa, sb)
    reached = sum(weigh(*fn[f]) for f in seen)
    return {"loop": body, "called": reached, "total": body + reached,
            "functions": sorted(seen)}


def test_the_handwritten_march_only_shrinks():
    """★JS 手写编排/语义只减不增 (the descent ruling, TODO §2.8) — and this
    gate MEASURES that, where its predecessor measured a proxy for it.

    ★★What changed and why (2026-08-27).  The old gate ratcheted the raw
    LINE COUNT of ``worker.js`` and ``fylite.js``.  That is a proxy, and
    S-2b is precisely the move that breaks it: switching the in-scope path
    onto the kernel entry ADDS an entry-driving path while the JS loop stays
    for the capabilities that are not sunk yet, so the intent (hand-written
    semantics shrink) is served while the metric goes UP.  A gate that turns
    red on the right move is not protecting the ruling, it is standing in
    front of it — and the temptation then is to argue the baseline up, which
    is how a ratchet quietly stops meaning anything.

    So the measure is now the thing itself: the per-step loop body plus the
    transitive closure of what it calls, with ``fy.*`` kernel calls stripped
    first.  It has the properties the ruling wants:

    * adding a path that calls the entry and returns moves it by ~0 —
      a kernel call is not a hand-written semantic;
    * sinking a capability shrinks it, because the function that carried
      that capability leaves the closure;
    * it cannot be argued down by reformatting, only by deleting reachable
      hand-written physics.

    ★The raw line counts are still printed on failure, as READINGS.  They
    are not the criterion any more, and the difference is the whole point.
    """
    src = (ROOT / "app/assets/worker.js").read_text()
    got = _hand_written_march(src)
    #: measured 2026-08-27, after S-2c 批二–批五 closed: **538** = 84 (the
    #: per-step loop body) + 454 (26 functions it reaches), counting only
    #: lines where the host decides — no comments, no blank or brace lines,
    #: no line that hands the question to `fy.*`.
    #: ★The raw span is 986; the difference is prose, braces and kernel
    #: calls, and every one of those three is something this ratchet must
    #: NOT charge for.
    #: ★`evReadings` and the page's own progress reporting are inside this
    #: number and are not going anywhere, so it has a floor well above zero:
    #: it is a RATCHET, not a target.
    BASELINE = 538
    assert got["total"] <= BASELINE, (
        f"the hand-written march grew to {got['total']} lines "
        f"(loop body {got['loop']} + {len(got['functions'])} functions "
        f"{got['called']}), baseline {BASELINE}.\n"
        "The ruling is that it only shrinks: sink the capability into the "
        "kernel and call it, or argue the growth explicitly.\n"
        "Raw file lines, as a reading only: "
        + ", ".join(f"{n} {len((ROOT / 'app/assets' / n).read_text().splitlines())}"
                    for n in ("worker.js", "fylite.js")))
    #: ★and the measure must still be MEASURING: a refactor that renamed the
    #: loop or moved it out of `evolveRun` would send this to a small number
    #: and read as progress.  The floor says the closure is still found.
    assert got["loop"] >= 50 and len(got["functions"]) >= 10, (
        f"the measure collapsed to {got} — it is no longer finding the "
        "march it is supposed to be measuring, so a passing number here "
        "would mean nothing")

def test_the_pedestal_drives_the_edge_and_reports_its_extrapolation():
    """★★S-2c 批一: with the model on, the Dirichlet edge is NOT the
    caller's number — it is the EPED1-NN pedestal top, re-evaluated from the
    beta_N of the state each step reached and applied to the next one.

    Three things are held: the edge really moved off the parameter, the
    trace of what was handed on is there, and the extrapolation distance
    comes back so a reader can tell a surrogate answering inside its
    training box from one answering outside it.
    """
    cfg = _config(nt=6)
    off = _run_entry(cfg, _params())
    on = _run_entry(cfg, _params(pedestal=1.0))
    steps = int(on["steps"])
    t_ped = on["t_ped"][:steps]
    assert (t_ped > 0).all(), "the pedestal produced no top"
    #: the march ran under a different boundary, so it reached a different
    #: profile — identical answers would mean the edge never moved
    assert not np.allclose(on["te"], off["te"])
    assert (off["t_ped"] == 0).all(), "the model is off; nothing may be handed on"
    #: beta_N is a reading of the state, so it moves with the temperature
    assert on["beta_n"][0] > 0 and on["beta_n"][steps - 1] != on["beta_n"][0]
    assert on["ped_extrap"] >= 0.0


def test_a_pedestal_without_a_current_is_refused():
    """★beta_N is normalised by a*B0/Ip and this tier does not solve for Ip.
    Zero is refused rather than divided by: a beta_N of infinity is an input
    the surrogate would ANSWER, extrapolation distance and all."""
    cfg = _config(nt=3)
    with pytest.raises(K.KernelError):
        _run_entry(cfg, _params(pedestal=1.0, ip=0.0))


# --- S-2c 批二: the current channel ----------------------------------------

_EVOLVE_KW = dict(a=0.45, r0=1.85, b0=2.0, q95=4.0, kappa=1.7, delta=0.4,
                  te_axis=3000.0, ti_axis=2800.0, ne_axis=4.0e19,
                  edge_te=100.0, edge_ti=100.0, edge_ne=5.0e18, ip=1.0e6)


def _q_prescribed(n, q95=4.0):
    x = np.linspace(0.0, 1.0, n)
    return 1.0 + (q95 - 1.0) * x ** 2


def test_the_current_channel_is_seeded_from_the_entrys_own_q_relation():
    """★★The one check that says the seed uses the RIGHT relation.

    The host assembles ``psi_init``; the entry reports ``q``.  The entry's
    own relation is ``q = 2 pi B0 rho / (dpsi/drho)``
    (``transport::solve_psi``), so a ``psi_init`` built by inverting THAT
    relation from the prescribed q must come back as the prescribed q — and
    the residual must be pure discretisation, i.e. it must go to zero with
    resolution at the order each region's stencil has.

    ★★★The counter-proof, measured: seeding instead from the
    current-diffusion metric ``V' gm2 F / (4 pi^2 q)`` — which is what
    ``gm2`` is FOR, and which was the first thing written here — puts the
    interior off by a factor of **5.3** (relative 4.34), and no refinement
    moves it, because it is the wrong relation and not a coarse one.  The
    two are told apart by convergence, not by size: that is why this gate
    sweeps resolution instead of asserting one tolerance.

    The three regions and why they differ:

    * INTERIOR — centred difference, second order.  2.80e-3 at n = 41 down
      to 4.67e-5 at n = 321 (measured 2026-08-27), a factor 15.9 per 4x.
    * EDGE — one-sided end difference, first order.  6.21e-3 to 7.78e-4.
    * AXIS — second order, and only since S-2c 批三.  ``solve_psi``
      evaluates q at ``max(rho, rho[1]/2)`` with ``dpsi[0] = dpsi[1]``, so
      its raw axis node is **exactly half** the prescribed axis value —
      converging TO the 0.5, which is what makes it an artifact of the node
      rather than an error in it.  The entry now reports the axis with the
      convention the kernel itself states for the same quantity
      (``surfaces::q_profile``: a linear extrapolation from the innermost
      pair), so the round trip closes at the axis too: 9.2e-4 at n = 41 down
      to 8.9e-6 at n = 321.
      ★★The assertion below MOVED when that landed, and the reason is not
      cosmetic: the sawtooth's trigger is ``q(0) < 1``, so a raw node would
      have fired a crash on a q that is half of what the plasma has, on
      every discharge, for ever.  The convention had to be the entry's
      because the trigger and the reported profile must be one array.
    """
    from fylite.scenario import model as M
    worst = {}
    for n in (41, 161):
        r = M.evolve(current=True, n_steps=2, dt=1e-9, n_rho=n, **_EVOLVE_KW)
        q = np.asarray(r["q"])
        want = _q_prescribed(n)
        assert q.shape == (n,)
        rel = np.abs(q[1:-1] - want[1:-1]) / want[1:-1]
        worst[n] = {"interior": float(rel.max()),
                    "edge": float(abs(q[-1] - want[-1]) / want[-1]),
                    "axis": float(q[0] / want[0])}
        assert q[0] > 0.0
    #: the size, with headroom — the point is the next assertion
    assert worst[41]["interior"] < 5e-3, worst
    #: second order: 4x the points must cut the interior error by >=8x
    #: (16x is the ideal; 15.9x was measured).  A WRONG relation cannot pass
    #: this at any tolerance, which is the whole design of the gate.
    drop = worst[41]["interior"] / worst[161]["interior"]
    assert drop > 8.0, (
        f"the interior residual fell only {drop:.1f}x for 4x the points "
        f"({worst}); a discretisation error falls ~16x, a wrong relation "
        "does not fall at all")
    #: first order at the edge: >=2.5x for 4x the points (3.98x measured)
    edge_drop = worst[41]["edge"] / worst[161]["edge"]
    assert edge_drop > 2.5, f"edge residual fell only {edge_drop:.1f}x: {worst}"
    #: the axis carries the kernel's stated convention, so it closes on the
    #: prescribed value — and does so at SECOND order like the interior,
    #: which is the claim that it is the extrapolation and not a coincidence
    assert abs(worst[161]["axis"] - 1.0) < 5e-4, worst
    axis_drop = (abs(worst[41]["axis"] - 1.0)
                 / max(abs(worst[161]["axis"] - 1.0), 1e-15))
    assert axis_drop > 8.0, (
        f"the axis residual fell only {axis_drop:.1f}x for 4x the points; "
        "the raw node would not converge to the prescribed value at all "
        "(it converges to HALF of it)")


def test_seeding_psi_from_the_current_metric_instead_would_be_caught():
    """★The counter-proof as a live measurement, not a remembered number.

    ``V' gm2 F / (4 pi^2 q)`` is the current-diffusion METRIC, not the
    definition of q.  Both expressions are plausible-looking, both use the
    same columns, and confusing them produces a self-contradictory initial
    state that nothing in the output would show — so the size of the error
    is measured here rather than asserted from memory.
    """
    from fylite import kernel as K
    n, a, r0, b0, q95 = 41, 0.45, 1.85, 2.0, 4.0
    rho = np.linspace(0.0, a, n)
    x = rho / a
    qp = 1.0 + (q95 - 1.0) * x ** 2
    vp, gm2 = np.zeros(n), np.zeros(n)
    for i in range(1, n):
        shear = x[i] * (2.0 * (q95 - 1.0) * x[i]) / qp[i]
        g = K.geo_surface(rmin_over_a=rho[i], rmaj_over_a=r0, q=qp[i],
                          shear=shear, kappa=1.7, s_kappa=0.0, delta=0.4,
                          s_delta=0.0, ntheta=201)
        vp[i], gm2[i] = g["volume_prime"], g["fsa_grad_r2_over_r2"]
    gm2[0] = gm2[1]
    fpol = np.full(n, r0 * abs(b0))

    def q_back(dpsi_drho):
        psi = np.zeros(n)
        for i in range(1, n):
            psi[i] = psi[i - 1] + 0.5 * (dpsi_drho[i] + dpsi_drho[i - 1]) \
                * (rho[i] - rho[i - 1])
        d = np.gradient(psi, rho)
        d[0] = d[1]
        d = np.where(np.abs(d) > 1e-10, d, 1e-10)
        got = 2.0 * np.pi * abs(b0) * np.maximum(rho, rho[1] * 0.5) / d
        return float((np.abs(got[1:-1] - qp[1:-1]) / qp[1:-1]).max())

    right = q_back(2.0 * np.pi * abs(b0) * rho / qp)
    wrong = q_back(vp * gm2 * fpol / (4.0 * np.pi ** 2 * qp))
    assert right < 5e-3, f"the entry's own relation should close: {right}"
    assert wrong > 1.0, (
        f"the current-diffusion metric gave {wrong}, which is small enough "
        "to be mistaken for a discretisation error — re-read this gate")


def test_the_current_channel_states_nothing_when_it_is_off():
    """★Zeros, and zeros meaning「nothing was marched」.

    A heat-only run must not hand back the prescribed q that shaped its
    metric dressed as a result, and must not hand back a flux it never
    solved.  ``psi`` comes back as the flux it was given (zeros here,
    because a heat-only assembly builds none)."""
    from fylite.scenario import model as M
    off = M.evolve(current=False, n_steps=4, dt=2e-3, n_rho=41, **_EVOLVE_KW)
    for key in ("q", "psi", "j_bs"):
        v = np.asarray(off[key])
        assert np.all(v == 0.0), f"{key} is not zeros on a heat-only run: {v}"
    assert np.all(np.asarray(off["p_ohm"]) == 0.0)
    assert "current" not in off["provenance"]["channels"]

    on = M.evolve(current=True, ohmic=True, bootstrap=True,
                  n_steps=4, dt=2e-3, n_rho=41, **_EVOLVE_KW)
    assert "current" in on["provenance"]["channels"]
    assert np.any(np.asarray(on["q"]) > 0.0)
    assert np.any(np.asarray(on["j_bs"]) != 0.0)
    #: the bootstrap current vanishes on axis by construction (no trapped
    #: fraction there), and a non-zero there would be the closure leaking
    assert float(np.asarray(on["j_bs"])[0]) == 0.0


def test_ohmic_heating_reaches_the_electron_channel_and_only_with_it_on():
    """★The Ohmic term is a HEAT source, so the check is that it moves the
    heat channel — not merely that a p_ohm trace is non-zero.  A term
    computed and dropped on the floor would pass the weaker test."""
    from fylite.scenario import model as M
    kw = dict(n_steps=20, dt=2e-3, n_rho=41, **_EVOLVE_KW)
    plain = M.evolve(current=True, **kw)
    ohmic = M.evolve(current=True, ohmic=True, **kw)
    assert np.all(np.asarray(plain["p_ohm"]) == 0.0), \
        "p_ohm without `ohmic` is a term nobody asked for"
    assert np.any(np.asarray(ohmic["p_ohm"]) > 0.0)
    d = float(np.max(np.abs(np.asarray(ohmic["te"])
                            - np.asarray(plain["te"]))))
    assert d > 0.0, "the Ohmic power was computed and never reached Te"


def test_the_bootstrap_current_is_refused_without_the_channel_that_carries_it():
    """★★A bootstrap current with no current channel has nowhere to go: it
    would be computed, reported and ignored.  Refused by name."""
    from fylite.scenario import model as M
    kw = dict(n_steps=2, dt=2e-3, n_rho=41, **_EVOLVE_KW)
    for extra in ({"bootstrap": True}, {"ohmic": True}):
        with pytest.raises(Exception) as exc:
            M.evolve(current=False, **extra, **kw)
        assert "current" in str(exc.value).lower(), str(exc.value)


# --- S-2c 批三: the sawtooth ------------------------------------------------

def _hollow_q_call(n=41, nt=10, q0=0.80, q_a=4.0, saw_mix=1.2, sawtooth=True,
                   saw_period=0.0):
    """A call into the entry with a HOLLOW core — ``q(0) = q0 < 1``.

    ★★Built here rather than through ``model.evolve`` on purpose, and the
    reason is a real limit of that tier: the prescribed-Miller assembly
    builds ``q = 1 + (q95 - 1) x^2``, so its ``q(0)`` is exactly 1 and its
    core can never fall through it.  **Both hosts are the same way**
    (``worker.js``'s ``evMillerMetric``: ``var q0 = 1.0``).  A sawtoothing
    core is what the TRACED geometry tiers deliver, and until one of them is
    sunk the honest way to gate the crash is to hand the entry the hollow
    equilibrium those tiers will hand it — which is the entry's contract:
    ``q_init`` and ``psi_init`` are INPUTS.

    ★It is not a fabricated discharge either: the seed is the entry's own
    relation ``dpsi/drho = 2 pi B0 rho / q`` (the same one
    ``sawtooth_crash`` rebuilds psi with), so the state handed in is
    internally consistent — just centrally peaked enough to sawtooth.
    """
    a, r0, b0 = 0.45, 1.85, 2.0
    rho = np.linspace(0.0, a, n)
    x = rho / a
    q_init = q0 + (q_a - q0) * x ** 2
    vp, gm3, gm2 = np.zeros(n), np.ones(n), np.zeros(n)
    for i in range(1, n):
        shear = x[i] * (2.0 * (q_a - q0) * x[i]) / q_init[i]
        g = K.geo_surface(rmin_over_a=rho[i], rmaj_over_a=r0, q=q_init[i],
                          shear=shear, kappa=1.7, delta=0.4, ntheta=201)
        vp[i] = g["volume_prime"]
        gm3[i] = g["fsa_grad_r2"]
        gm2[i] = g["fsa_grad_r2_over_r2"]
    gm3[0], gm2[0] = gm3[1], gm2[1]
    dpsi = np.zeros(n)
    dpsi[1:] = 2.0 * np.pi * abs(b0) * rho[1:] / q_init[1:]
    psi = np.zeros(n)
    for i in range(1, n):
        psi[i] = psi[i - 1] + 0.5 * (dpsi[i] + dpsi[i - 1]) \
            * (rho[i] - rho[i - 1])
    params = {"b0": b0, "chi0": 1.0, "chi_ratio": 1.0, "edge_te": 100.0,
              "edge_ti": 100.0, "dt": 2e-3, "dt_target": 0.02,
              "dt_min": 1e-5, "dt_max": 0.02, "d_pc": 0.0,
              "p_e": 2e6, "p_i": 2e6, "dep_centre": 0.0, "dep_width": 0.3,
              "brem": 1.0, "bulk_id": K.adas_id("D"), "imp_id": -1.0,
              "imp_conc": 0.0, "imp_z": 0.0, "alpha": 0.0,
              "dt_fraction": 0.5, "zeff": 1.5, "pedestal": 0.0, "ip": 1e6,
              "a": a, "r0": r0, "kappa": 1.7, "delta": 0.4,
              "ch_current": 1.0, "ohmic": 1.0, "bootstrap": 1.0,
              "v_loop": 0.0, "sawtooth": float(bool(sawtooth)),
              "saw_mix": saw_mix if sawtooth else 0.0,
              "saw_period": saw_period}
    inputs = {"rho": rho, "vprime": vp, "gm3": gm3,
              "te_init": 300 + 2700 * (1 - x ** 2),
              "ti_init": 300 + 2200 * (1 - x ** 2),
              "ne": 4e19 * (0.5 + 0.5 * (1 - x ** 2)),
              "gm2": gm2, "fpol": np.full(n, r0 * abs(b0)), "psi_init": psi,
              "rmin": rho, "rmaj": np.full(n, r0), "q_init": q_init}
    return {"dims": {"n": n, "nt": nt}, "params": params, "inputs": inputs}


def test_the_sawtooth_fires_on_a_hollow_core_and_mixes_where_it_says():
    """★The crash, end to end: it triggers on ``q(0) < 1``, it mixes at
    ``saw_mix * r_1`` and not somewhere else, and it flattens the core."""
    #: ★nt = 1, so what comes out is the state the crash LEFT.  With more
    #: steps the core re-peaks by ordinary diffusion and a flatness
    #: assertion would be measuring how long the march ran, not the crash.
    call = _hollow_q_call(saw_mix=1.2, nt=1)
    out = K.scenario("evolve_heat", params=call["params"],
                     inputs=call["inputs"], **call["dims"])
    assert int(out["saw_count"]) >= 1, "a q(0) = 0.8 core did not sawtooth"
    r1 = np.asarray(out["saw_r1"])
    mixed = np.asarray(out["saw_mixed"])
    fired = np.flatnonzero(mixed)
    assert fired.size >= 1
    k = int(fired[0])
    assert r1[k] > 0.0
    #: the mixing radius is the multiple the caller asked for — pinned,
    #: because a crash at some other radius is a different discharge
    assert mixed[k] == pytest.approx(1.2 * r1[k], rel=1e-12)
    assert not np.any(np.asarray(out["saw_refused"])), \
        "the crash was refused; the mixing radius must sit on the grid"
    #: and the core came out FLAT out to the MIXING radius (not to r_1 —
    #: the crash mixes inside `saw_mix * r_1`, which is the wider of the two
    #: here and is the radius the model actually acts on)
    te = np.asarray(out["te"])
    rho = call["inputs"]["rho"]
    i_mix = int(np.argmax(rho > mixed[k]))
    assert i_mix >= 3, i_mix
    inner = te[:i_mix]
    assert np.ptp(inner) / inner.mean() < 1e-12, f"the core is not flat: {inner}"
    #: and it is flat at a value INSIDE the range it replaced, not at an
    #: endpoint — a "flattening" to the seam value would conserve nothing,
    #: and one to the peak would conserve nothing the other way.  The range
    #: is the PRE-crash profile of this same march, not the initial one:
    #: the step heats the axis before the crash lands on it.
    before = np.asarray(K.scenario(
        "evolve_heat", params=dict(call["params"], sawtooth=0.0, saw_mix=0.0),
        inputs=call["inputs"], **call["dims"])["te"])
    assert before[i_mix] < inner[0] < before[0], (
        f"mixed to {inner[0]}, outside the pre-crash core "
        f"[{before[i_mix]}, {before[0]}]")


def test_the_crash_conserves_the_content_it_mixes_and_leaves_the_rest_alone():
    """★★What makes it a MIXING model rather than a source: the integral
    ``int V' y drho`` over the mixed region is the same before and after,
    and nothing outside the mixing radius moves.

    ★The comparison run is the SAME march with the sawtooth off, so the
    difference is the crash and not the step."""
    #: ★nt = 1 on both sides: one march step, then the crash on one of them.
    #: With two steps the post-crash profile diffuses again before it is
    #: read, and the difference would be「碰撞 + 一步扩散」rather than the
    #: crash — content is conserved by the crash, not by the step after it.
    on = _hollow_q_call(sawtooth=True, nt=1)
    off = _hollow_q_call(sawtooth=False, nt=1)
    a = K.scenario("evolve_heat", params=on["params"],
                   inputs=on["inputs"], **on["dims"])
    b = K.scenario("evolve_heat", params=off["params"],
                   inputs=off["inputs"], **off["dims"])
    assert int(a["saw_count"]) == 1 and int(b["saw_count"]) == 0
    rho = on["inputs"]["rho"]
    vp = on["inputs"]["vprime"]
    r_mix = float(np.asarray(a["saw_mixed"])[0])
    assert r_mix > 0
    i_mix = int(np.argmax(rho > r_mix))

    def content(y):
        return float(np.trapezoid((vp * y)[:i_mix], rho[:i_mix]))

    for key in ("te", "ti"):
        ya, yb = np.asarray(a[key]), np.asarray(b[key])
        assert content(ya) == pytest.approx(content(yb), rel=1e-9), (
            f"{key}: the crash changed the mixed region's content")
        #: outside is untouched — bit for bit, because nothing acted there
        assert np.array_equal(ya[i_mix:], yb[i_mix:]), (
            f"{key} moved outside the mixing radius")
        #: and the crash DID something inside (otherwise every assertion
        #: above is satisfied by a no-op)
        assert not np.allclose(ya[:i_mix], yb[:i_mix])


def test_a_discharge_that_is_not_sawtoothing_says_so_rather_than_falling_silent():
    """★``saw_r1 == 0`` is the ANSWER for a core that never reaches q = 1 —
    a reading, not an absence.  Three states have to stay distinguishable:
    no q = 1 surface, a crash, and a crash the mixing model could not
    honour."""
    call = _hollow_q_call(q0=1.4, q_a=4.0)      # core well above 1
    out = K.scenario("evolve_heat", params=call["params"],
                     inputs=call["inputs"], **call["dims"])
    assert int(out["saw_count"]) == 0
    assert not np.any(np.asarray(out["saw_r1"]))
    assert not np.any(np.asarray(out["saw_mixed"]))
    assert not np.any(np.asarray(out["saw_refused"]))
    #: the rows EXIST and are zeros — the entry always states them
    for key in ("saw_r1", "saw_mixed", "saw_refused"):
        assert np.asarray(out[key]).shape == (call["dims"]["nt"],)


def test_a_mixing_radius_the_model_cannot_honour_is_recorded_not_swallowed():
    """★A crash triggered but not carried out must leave the state where the
    march put it AND say so.  A silent no-op would read as「没有锯齿」, which
    is a different discharge."""
    call = _hollow_q_call(saw_mix=1e-4, nt=2)   # r_mix inside the first cell
    out = K.scenario("evolve_heat", params=call["params"],
                     inputs=call["inputs"], **call["dims"])
    refused = np.asarray(out["saw_refused"])
    assert refused[0] == 1.0, (
        "a mixing radius inside the first cell was accepted; the model "
        "cannot honour it and must record the refusal")
    assert int(out["saw_count"]) == 0
    assert float(np.asarray(out["saw_mixed"])[0]) == 0.0
    #: and it was TRIGGERED — the refusal is about the mixing, not the
    #: trigger, and the r_1 that fired it is still reported
    assert float(np.asarray(out["saw_r1"])[0]) > 0.0


def test_the_sawtooth_is_refused_without_the_channel_that_makes_q_a_result():
    """★★With q prescribed, a crash would be fired by a profile nothing in
    the march can move.  The browser returns null there — right for a page
    redrawing itself, wrong for an entry, where silence cannot be told from
    having honoured the request."""
    from fylite.scenario import model as M
    call = _hollow_q_call()
    call["params"]["ch_current"] = 0.0
    call["params"]["ohmic"] = 0.0
    call["params"]["bootstrap"] = 0.0
    with pytest.raises(K.KernelError):
        K.scenario("evolve_heat", params=call["params"],
                   inputs=call["inputs"], **call["dims"])
    #: and named, on the host that has room to name it
    with pytest.raises(ValueError, match="current channel"):
        M.evolve(a=0.45, r0=1.85, b0=2.0, te_axis=3000.0, ti_axis=2800.0,
                 ne_axis=4e19, edge_te=100.0, edge_ti=100.0, edge_ne=5e18,
                 n_steps=2, dt=2e-3, sawtooth=True, current=False)
    #: a mixing radius of zero is a model choice nobody made — refused too,
    #: for the reason TGLF's `width` has no default
    with pytest.raises(ValueError, match="saw_mix"):
        M.evolve(a=0.45, r0=1.85, b0=2.0, te_axis=3000.0, ti_axis=2800.0,
                 ne_axis=4e19, edge_te=100.0, edge_ti=100.0, edge_ne=5e18,
                 n_steps=2, dt=2e-3, sawtooth=True, current=True, saw_mix=0.0)


def test_the_trigger_reads_the_axis_convention_and_not_the_raw_node():
    """★★★The trap this batch had to walk around, measured.

    ``solve_psi``'s raw axis node is ``q(rho_1)/2``.  If the trigger read it,
    a discharge with a perfectly healthy ``q(0) = 1.4`` would show ``0.7`` at
    the node and sawtooth on every step for ever.  The gate measures both
    numbers on the same run and asserts the entry reports the convention —
    otherwise the assertion above (「不锯齿的放电如实说」) would be passing
    for a reason that has nothing to do with the physics.
    """
    call = _hollow_q_call(q0=1.4, q_a=4.0)
    out = K.scenario("evolve_heat", params=call["params"],
                     inputs=call["inputs"], **call["dims"])
    q = np.asarray(out["q"])
    #: the reported axis is the extrapolation from the innermost pair
    want = abs(q[1] - (q[2] - q[1]) * call["inputs"]["rho"][1]
               / (call["inputs"]["rho"][2] - call["inputs"]["rho"][1]))
    assert q[0] == pytest.approx(want, rel=1e-12)
    #: and it is above the trigger, which is the whole point: this core is
    #: healthy and the entry says so
    assert q[0] > 1.0, q[0]
    assert int(out["saw_count"]) == 0
    #: THE COUNTER-PROOF: the raw node this replaces is about q[1]/2, which
    #: is below 1 — i.e. it would have triggered a crash on this discharge
    raw = q[1] / 2.0
    assert raw < 1.0 < q[0], (
        f"raw node {raw} vs reported {q[0]}: the two must straddle the "
        "trigger, or this gate is not testing what it says")


def test_a_declared_row_keeps_its_shape_when_the_dimension_happens_to_be_one():
    """★★A declared shape is a CONTRACT, and a contract that changes with
    the numbers is not one.

    ``kernel.scenario`` used to decide scalar-or-array from the computed
    LENGTH (``n == 1``), so an entry run at ``nt = 1`` handed its per-step
    traces back as bare floats.  ``model.evolve`` died on it with 「'float'
    object is not subscriptable」 — on the smallest march anyone would reach
    for while debugging, which is exactly when a caller least wants a
    different result shape.  The rule is now the declaration: shape ``"1"``
    is a scalar, a shape that NAMES a dimension is an array of that length,
    including length one.
    """
    call = _hollow_q_call(nt=1)
    out = K.scenario("evolve_heat", params=call["params"],
                     inputs=call["inputs"], **call["dims"])
    from fylite import _fyo_interface as FI

    shapes = {r["key"]: r["shape"]
              for r in FI.BLOCKS[FI.ENTRY_BLOCKS["evolve_heat"]["out"]]}
    per_step = [k for k, sh in shapes.items() if sh.strip() == "nt"]
    assert per_step, "this entry declares no per-step row; re-read the gate"
    for key in per_step:
        assert np.asarray(out[key]).shape == (1,), (
            f"{key} came back as {out[key]!r} at nt = 1; a row declared "
            f"{shapes[key]!r} is an array of that length, always")
    for key, sh in shapes.items():
        if sh.strip() == "1":
            assert isinstance(out[key], float), (
                f"{key} is declared a scalar and came back {type(out[key])}")
    #: and the assembly on top of it survives the same march
    from fylite.scenario import model as M
    r = M.evolve(a=0.45, r0=1.85, b0=2.0, te_axis=3000.0, ti_axis=2800.0,
                 ne_axis=4e19, edge_te=100.0, edge_ti=100.0, edge_ne=5e18,
                 n_rho=21, n_steps=1, dt=1e-3)
    assert np.asarray(r["t"]).shape == (1,)


# --- S-2b 的前置: the continuation pair -------------------------------------

def _resume(call, nt, prev=None, **over):
    """One block of a march — the first when ``prev`` is None."""
    params = dict(call["params"])
    params.update(over)
    inputs = dict(call["inputs"])
    if prev is not None:
        params.update(resume=1.0, t_start=prev["t_end"],
                      dt_start=prev["dt_next"],
                      edge_te_in=prev["edge_te_out"],
                      edge_ti_in=prev["edge_ti_out"],
                      capped_in=prev["dt_capped"],
                      saw_elapsed_in=prev["saw_elapsed_out"])
        inputs.update(te_init=prev["te"], ti_init=prev["ti"],
                      ne=prev["ne_out"], psi_init=prev["psi"],
                      psi_prev=prev["psi_prev_out"],
                      sigma_prev=prev["sigma_prev_out"],
                      exch_prev=prev["exch_prev_out"])
    return K.scenario("evolve_heat", params=params, inputs=inputs,
                      **dict(call["dims"], nt=nt))


@pytest.mark.parametrize("n_blocks,per", [(4, 3), (12, 1), (2, 6), (3, 4)])
def test_driving_the_entry_in_blocks_equals_one_long_run(n_blocks, per):
    """★★★S-2b's prerequisite, and the claim the whole switch rests on.

    A page that marches 400 steps cannot hand the run to one call and go
    dark — it drives the entry in BLOCKS and draws between them.  That is
    only honest if ``N`` blocks of ``k`` steps is the SAME MARCH as one run
    of ``N*k``: a reader who moved the progress-report slider and got a
    different discharge would have no way to know which one to believe.

    ★BIT for bit, not「close」.  The two are the same arithmetic in the same
    order on the same host; anything less than equality means some state
    that crosses a step boundary does not cross a block boundary, and a
    tolerance would hide exactly the defect this gate exists to find.

    ★★And it DID find one, which is why the gate is parameterised over
    block sizes rather than run once: ``ne`` became state when S-2c 批三
    let the sawtooth flatten the density along with the temperatures, and
    the entry had no ``ne`` output.  Every block boundary silently restored
    the caller's original density — undoing each crash — and nothing else
    in the suite could see it, because a single-block run never crosses a
    boundary.  The row exists now; this gate is why.
    """
    call = _hollow_q_call(nt=1)
    one = _resume(call, n_blocks * per)
    step = None
    for _ in range(n_blocks):
        step = _resume(call, per, step)
    for key in ("te", "ti", "ne_out", "psi", "q", "j_bs", "j_cd"):
        a, b = np.asarray(one[key]), np.asarray(step[key])
        assert np.array_equal(a, b), (
            f"{key} differs between one run of {n_blocks * per} steps and "
            f"{n_blocks} blocks of {per}: worst {np.max(np.abs(a - b)):.6g}")
    #: the clock and the controller are state too — a march that ended at a
    #: different time took different steps, whatever the profiles look like
    assert one["t_end"] == step["t_end"]
    assert one["dt_next"] == step["dt_next"]
    assert one["dt_capped"] == step["dt_capped"]


def test_a_first_block_ignores_every_carried_row():
    """★``resume = 0`` must mean「这是第一块」and nothing else: a caller that
    never blocks must not have to know the continuation exists.  Filling the
    carried rows with nonsense may not change a first block's answer."""
    call = _hollow_q_call(nt=4)
    clean = K.scenario("evolve_heat", params=call["params"],
                       inputs=call["inputs"], **call["dims"])
    n = call["dims"]["n"]
    junk = dict(call["inputs"])
    junk.update(psi_prev=np.full(n, -7.5), sigma_prev=np.full(n, 3.3e6),
                exch_prev=np.full(n, 9.9e4))
    noisy = dict(call["params"])
    noisy.update(t_start=42.0, dt_start=0.5, edge_te_in=9999.0,
                 edge_ti_in=8888.0, capped_in=17.0)
    got = K.scenario("evolve_heat", params=noisy, inputs=junk, **call["dims"])
    for key in ("te", "ti", "psi", "q"):
        assert np.array_equal(np.asarray(clean[key]), np.asarray(got[key])), (
            f"{key} moved when the carried rows were filled with a first "
            "block; `resume = 0` must ignore them")
    assert clean["t_end"] == got["t_end"]


#: Each carried row, with the configuration in which it is LOAD-BEARING.
#:
#: ★★`sigma_prev_out` carries the LAGGED CONDUCTIVITY for the Ohmic
#: heating, and the entry suppresses Ohmic power on the step after a crash
#: on purpose (reconnection moves psi by an amount no resistive step took,
#: so sigma E^2 on it would report a spike that never happened).  So on a
#: core that crashes EVERY step the row is never read — not because it is
#: dead, but because the configuration never reaches the branch that reads
#: it.  Gating it with the sawtooth off is what makes the claim
#: demonstrable; gating it with the sawtooth on would only be measuring the
#: suppression.
#:
#: ★`ne_out` is the other way round: the density is carried state ONLY
#: because the crash mixes it, so it is gated with the sawtooth on.
_CARRIED_ROWS = (
    ("psi_prev_out", lambda v: np.asarray(v) * 1.05, False),
    ("sigma_prev_out", lambda v: np.asarray(v) * 0.5, False),
    ("exch_prev_out", lambda v: np.asarray(v) * 4.0, False),
    ("dt_next", lambda v: float(v) * 0.5, False),
    ("edge_te_out", lambda v: float(v) + 250.0, False),
    ("ne_out", lambda v: np.asarray(v) * 1.1, True),
)


@pytest.mark.parametrize("key,bogus,sawtooth", _CARRIED_ROWS)
def test_the_carried_state_is_what_a_step_reads_from_the_step_before_it(
        key, bogus, sawtooth):
    """★A continuation row that carried the wrong thing would still let the
    gate above pass if it were never READ.  Each row is knocked out in turn
    and the block must then differ — a row nothing depends on is a row that
    should not be there."""
    call = _hollow_q_call(nt=1, sawtooth=sawtooth)
    first = _resume(call, 3)
    good = _resume(call, 3, first)
    bent = dict(first)
    bent[key] = bogus(first[key])
    out = _resume(call, 3, bent)
    assert not np.array_equal(np.asarray(good["te"]),
                              np.asarray(out["te"])) or \
           not np.array_equal(np.asarray(good["psi"]),
                              np.asarray(out["psi"])), (
        f"bending {key} changed nothing — either it is not read, or it "
        "is not the state the next block needs")


def test_the_browser_drives_every_in_scope_corpus_case_through_the_entry():
    """★★★What S-2b BUYS, measured — and it is not fewer lines.

    Before it, a corpus case ran through TWO orchestrations: Python called
    the kernel entry, the browser ran its own JS march, and a gate kept them
    equal.  That is an agreement by JUDGEMENT.  Now both hosts call the same
    entry for any configuration the declared scope ledger says it carries,
    so the agreement is by CONSTRUCTION and the gate checks the assembly
    (metric, initial profiles, the control-to-param mapping) instead.

    ★The number below is a FLOOR and the direction is the point: sinking a
    capability moves cases from「浏览器自己那圈循环」to「两个宿主同一套编
    排」, and nothing may move them back.  It is the measure the line
    ratchet cannot express — switching a case onto the entry adds an
    entry-driving path and removes no hand-written physics, so the size
    metric stays flat while THIS one moves.
    """
    from fylite.engine import cases

    evolve = [e["case_id"] for e in cases.catalogue()
              if e["bar"] == "evolve"]
    assert len(evolve) >= 13
    in_scope = []
    for cid in evolve:
        try:
            cases.plan(cid)
            in_scope.append(cid)
        except SystemExit:
            pass
    #: measured 2026-08-27, after S-2b: the eleven the entry carries whole.
    #: The other two are refused for want of a reference FILE, not a
    #: capability — see `test_the_evolve_scope_ledger_names_what_is_missing`.
    assert len(in_scope) >= 11, (
        f"only {len(in_scope)} evolve cases are in scope; 11 were after "
        "S-2b — a case moved back to the browser's own loop")

    #: ★and the browser decides it from the SAME declaration, not a list of
    #: its own: the routing test reads `ENTRY_SCOPE` out of the generated
    #: interface, so a capability that sinks releases both hosts at once
    worker = (ROOT / "app/assets/worker.js").read_text()
    assert "ENTRY_SCOPE" in worker, (
        "the worker no longer reads the declared scope ledger — a second "
        "opinion about what is in scope is the arrangement this replaced")
    assert "evEntryMarch(" in worker and "evScopeMiss(" in worker
    #: the worker must LOAD the generated interface, or the scope test
    #: throws at run time rather than defaulting to「在范围内」
    assert "'fyo-interface.js'" in worker


def test_the_scope_ledger_is_one_declaration_and_both_hosts_read_it():
    """★The single-source claim, checked from the kernel outwards: every row
    the browser tests against is a row the kernel declared, and Python's
    refusal vocabulary is built from the same rows."""
    from fylite import _fyo_interface as FI
    from fylite.engine import cases

    rows = FI.BLOCKS["ENTRY_SCOPE"]
    assert rows, "the kernel declares no scope ledger"
    verdicts = {r["units"] for r in rows}
    assert verdicts <= {"unsunk", "required"}, verdicts
    #: Python's two dicts are exactly the two verdicts, nothing added here
    assert set(cases._EVOLVE_UNSUNK) == {r["key"] for r in rows
                                         if r["units"] == "unsunk"}
    assert set(cases._EVOLVE_REQUIRED) == {r["key"] for r in rows
                                           if r["units"] == "required"}
    #: and the browser's side of each row names a field it can actually read
    js = (ROOT / "app/assets/fyo-interface.js").read_text()
    for r in rows:
        assert r["key"] in js, f"{r['key']} is not generated into the browser"


def _run(call, nt=None):
    dims = dict(call["dims"], **({"nt": nt} if nt else {}))
    return K.scenario("evolve_heat", params=call["params"],
                      inputs=call["inputs"], **dims)


def test_the_sawtooth_period_meters_the_crashes():
    """★★T-C28's mechanism, gated where the defect was measured.

    Without a period, a core holding a q = 1 surface crashed on EVERY step
    — 1280 crashes on the JINTRAC flat-top where the reference's
    ``DTSAW = 0.1 s`` took ~163.  With one, the crash count is the WINDOW
    over the period, not the step count.

    ★The dt here is the controller's, not the fixture's nominal one, so the
    period is stated against the TIME the run actually took (`t_end`) and
    the expected count derives from that — a gate that assumed the nominal
    dt would be gating the controller, not the meter.

    ★The phase starts ripe — a plasma carrying a q = 1 surface at t = 0 was
    sawtoothing before the window opened — so the first crash lands on the
    first triggered step.
    """
    nt = 12
    #: period 0 = the pre-period behaviour, crash whenever triggered
    every = _run(_hollow_q_call(nt=nt, saw_period=0.0))
    assert int(every["saw_count"]) == nt, (
        "period 0 no longer crashes every triggered step — the recorded "
        "pre-period behaviour is the backward-compatibility contract")
    #: a period spanning ~a third of the run: the count must collapse from
    #: 「every step」 to 「a handful」, and the exact number follows from the
    #: crash times the run itself reports
    span = float(every["t_end"])
    period = span / 3.0
    metered = _run(_hollow_q_call(nt=nt, saw_period=period))
    got = int(metered["saw_count"])
    assert 2 <= got <= 5, (
        f"{got} crashes in a {float(metered['t_end']):.4f} s run at a "
        f"{period:.4f} s period — the meter is not metering")
    assert got < nt // 2, "the period barely reduced the crash count"
    #: ★and the radius is still TRACED on withheld steps — a reader can see
    #: the q = 1 surface sit there between crashes
    r1 = np.asarray(metered["saw_r1"])
    mixed = np.asarray(metered["saw_mixed"])
    assert int((r1 > 0).sum()) > int((mixed > 0).sum()), (
        "withheld steps no longer trace the q = 1 radius — the cycle is "
        "invisible between crashes")


def test_blocks_equal_one_run_with_a_period_too():
    """★The continuation contract extended to the metered sawtooth: the
    elapsed-time carry (`saw_elapsed_in/out`) must make N blocks of k steps
    equal one run of N*k, crashes included — otherwise every block boundary
    would restart the period phase ripe and crash immediately."""
    nt = 12
    probe = _run(_hollow_q_call(nt=nt, saw_period=0.0))
    call = _hollow_q_call(nt=nt, saw_period=float(probe["t_end"]) / 3.0)
    one = _run(call)
    prev = None
    counts = []
    for _ in range(4):
        prev = _resume(call, 3, prev)
        counts.append(int(prev["saw_count"]))
    assert sum(counts) == int(one["saw_count"]) >= 2, (
        f"blocks crashed {sum(counts)} times against the long run's "
        f"{int(one['saw_count'])} — the period phase is not crossing the "
        "block boundary")
    for key in ("te", "ti", "psi"):
        assert np.array_equal(np.asarray(one[key]), np.asarray(prev[key])), (
            f"{key} differs between one run and blocks with a period — "
            "the carried elapsed is not the whole of the phase state")


def test_the_given_profile_closure_is_the_callers_chi():
    """★The `chi_source = 1` tier: the entry marches on the CALLER's
    diffusivity profiles instead of the constant pair.

    Three claims, each the kind that fails loudly if the wiring slips:
    a flat given profile equal to the constants must reproduce the constant
    tier BIT FOR BIT (same closure, different spelling); a shaped profile
    must move the answer; and a profile with a zero anywhere must be
    REFUSED, not marched on — a conductivity hole is not a closure.
    """
    call = _hollow_q_call(nt=4, sawtooth=False)
    n = call["dims"]["n"]
    base = _run(call)

    flat = dict(call["params"], chi_source=1.0)
    chi_i = np.full(n, call["params"]["chi0"])
    chi_e = chi_i * call["params"]["chi_ratio"]
    inputs = dict(call["inputs"], chi_e_in=chi_e, chi_i_in=chi_i)
    same = K.scenario("evolve_heat", params=flat, inputs=inputs,
                      **call["dims"])
    for key in ("te", "ti", "psi"):
        assert np.array_equal(np.asarray(base[key]), np.asarray(same[key])), (
            f"{key}: a flat given profile equal to the constants is the "
            "same closure and must be the same march")

    x = np.asarray(call["inputs"]["rho"]) / call["inputs"]["rho"][-1]
    shaped = dict(inputs, chi_e_in=chi_e * (0.5 + 2.0 * x ** 2),
                  chi_i_in=chi_i * (0.5 + 2.0 * x ** 2))
    moved = K.scenario("evolve_heat", params=flat, inputs=shaped,
                       **call["dims"])
    assert not np.array_equal(np.asarray(base["te"]),
                              np.asarray(moved["te"])), (
        "a shaped chi profile changed nothing — the given tier is not "
        "being read")

    holed = dict(inputs, chi_e_in=np.where(x > 0.5, 0.0, chi_e))
    with pytest.raises(K.KernelError):
        K.scenario("evolve_heat", params=flat, inputs=holed, **call["dims"])


def test_model_evolve_reaches_the_given_profile_tier():
    """★The Python assembly face carries the tier: `model.evolve` with the
    profile pair marches on them, refuses half a pair, and the constant
    call stays byte-stable (chi_source 0)."""
    from fylite.scenario import model as M

    kw = dict(a=0.45, r0=1.85, b0=2.0, te_axis=2.5e3, ti_axis=2.5e3,
              ne_axis=4e19, edge_te=100.0, edge_ti=100.0, edge_ne=1e19,
              n_rho=21, n_steps=3, dt=1e-3, chi0=1.0, p_e=1e6, p_i=1e6,
              ip=1e6)
    base = M.evolve(**kw)
    n = len(base["rho"])
    x = np.asarray(base["rho"]) / base["rho"][-1]
    shaped = M.evolve(**kw, chi_e_profile=1.0 + 2.0 * x ** 2,
                      chi_i_profile=1.0 + 2.0 * x ** 2)
    assert not np.array_equal(np.asarray(base["te"]),
                              np.asarray(shaped["te"])), (
        "the profiles did not reach the entry through the assembly face")
    with pytest.raises(ValueError, match="together or not at all"):
        M.evolve(**kw, chi_e_profile=np.ones(n))
