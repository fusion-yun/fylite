"""自洽稳态外环 —— `scenario.model.stationary` (TODO T-C14 判据〔五〕).

★★WHY THIS FILE EXISTS.  The browser has run this loop since T-C14 步 4/5/6
landed; the assembly layer had every piece of it and no caller — the same
shape as T-C13 (「内核有、宿主够不着」), one host over.  What is judged here
is the part a second host can be *held to*:

  the ORDER and the STOPPING RULES.  A loop that reports「收敛」on its first
  round is reporting that its initial guess had not moved; a loop that keeps
  alternating after its inner solve stalled is iterating a quantity nobody
  solved for.  Both are silent failures and both are pinned below.

  the STEADY-CURRENT STEP itself, which is the only step with arithmetic of
  its own — and it is pinned to be *the same call* the kernel gets from a
  caller writing it out by hand, so「装配层同口径」is an assertion about ONE
  solve rather than about two that happen to look alike.

  the CLAIM THAT `n_e` DOES NOT ENTER, which the module's docstring makes.
  It is measured here rather than believed: it is the reason this function
  may take a density it does not use, and a future edit that starts using it
  has to come past this test.

★The cross-host half of〔五〕 is not here — it needs a browser.  It lives in
`app/tests/validate-stationary.mjs`〔己〕, which feeds this module the arrays
the session file recorded and requires the two hosts to land on one ψ.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from fylite import kernel
from fylite.scenario.model import assembly, stationary


def _ladder(n=33):
    rho = np.linspace(0.0, 1.0, n)
    return {
        "rho": rho,
        "vprime": 2 * np.pi**2 * 1.8 * rho * 2.0 + 1e-6,
        "gm3": np.ones(n),
        "gm2": np.full(n, 0.3),
        "fpol": np.full(n, 3.0),
        "b0": 1.8,
        "te": np.linspace(2000.0, 200.0, n),
        "ti": np.linspace(1800.0, 200.0, n),
        "ne": np.linspace(4e19, 1e19, n),
        "psi": np.linspace(1.0, 0.0, n),
        "sigma_par": np.linspace(1e7, 1e5, n),
        "j_ni": np.linspace(1e5, 0.0, n),
    }


# --- the convergence measure ------------------------------------------------

def test_relative_change_is_the_worst_radius_not_the_average():
    """★L-infinity, deliberately: one radius that has not settled means the
    profile has not settled, and an RMS would let it hide under sixty that
    did."""
    old = np.ones(10)
    new = np.ones(10)
    new[7] = 1.5
    assert stationary.relative_change(new, old) == pytest.approx(0.5)


def test_relative_change_is_relative_to_the_previous_rounds_own_scale():
    """★The denominator is `max|old|`, not a per-point ratio — a per-point
    ratio is dominated by the edge, where both profiles are near zero."""
    old = np.array([100.0, 10.0, 1e-9])
    new = np.array([100.0, 10.0, 2e-9])
    assert stationary.relative_change(new, old) == pytest.approx(1e-11)


def test_relative_change_of_nothing_is_zero_not_nan():
    assert stationary.relative_change(np.zeros(5), np.zeros(5)) == 0.0


def test_relative_change_refuses_two_different_ladders():
    """★A change measured across a moving grid is mostly the grid.  The loop
    relabels first; this refuses to let it forget."""
    with pytest.raises(ValueError, match="ladder"):
        stationary.relative_change(np.ones(9), np.ones(10))


# --- the steady-current step ------------------------------------------------

def test_steady_current_is_the_kernel_call_written_out_by_hand():
    """★★「同口径」means ONE solve, not two that agree: the wrapper is held
    against the bare `core_march` a caller would otherwise write."""
    L = _ladder()
    got = stationary.steady_current(
        L["rho"], vprime=L["vprime"], gm3=L["gm3"], gm2=L["gm2"],
        fpol=L["fpol"], b0=L["b0"], te=L["te"], ti=L["ti"], ne=L["ne"],
        psi=L["psi"], sigma_par=L["sigma_par"], j_ni=L["j_ni"])
    ref = kernel.core_march(
        L["rho"], te=L["te"], ti=L["ti"], ni=L["ne"], z=[1.0],
        edge_ni=[L["ne"][-1]], psi=L["psi"], vprime=L["vprime"],
        gm3=L["gm3"], gm2=L["gm2"], fpol=L["fpol"], b0=L["b0"],
        closure=lambda s: {"sigma_par": L["sigma_par"], "j_ni": L["j_ni"]},
        dt=math.inf, edge_te=L["te"][-1], edge_ti=L["ti"][-1],
        edge_psi=L["psi"][-1], edge_psi_rate=0.0,
        heat=False, density=False, current=True,
        max_outer=1, tol_steady=1e-9, n_coupling=2, tol=1e-10, max_inner=60)
    assert np.array_equal(got["psi"], np.asarray(ref["psi"], float))


def test_the_density_does_not_enter_this_march():
    """★★The docstring's own claim, measured.  With the heat and density
    channels off no equation in the system contains `n_e` — so a future edit
    that starts using it has to come past this line."""
    L = _ladder()
    kw = dict(vprime=L["vprime"], gm3=L["gm3"], gm2=L["gm2"], fpol=L["fpol"],
              b0=L["b0"], te=L["te"], ti=L["ti"], psi=L["psi"],
              sigma_par=L["sigma_par"], j_ni=L["j_ni"])
    a = stationary.steady_current(L["rho"], ne=L["ne"], **kw)
    b = stationary.steady_current(L["rho"], ne=0.5 * L["ne"], **kw)
    assert np.array_equal(a["psi"], b["psi"])


def test_at_dt_infinity_the_steady_current_is_the_non_inductive_one_alone():
    """★★★THE STEP'S REAL CONTENT, and it corrects what T-C14 立项 wrote.

    The 裁定 said 步 4「跑在读者自己给的 vloop 上」.  It cannot: at
    ``dt = inf`` the time derivative is gone, so the Ohmic term ``sigma E``
    — which IS ``-dpsi/dt`` — is identically zero and the enclosed current is
    whatever ``j_ni`` carries.  Measured here, three ways at once:

      * **exactly linear in `j_ni`** (half → half, double → double),
      * **independent of `sigma_par`** over a decade,
      * **independent of the boundary flux and of its rate** — a constant
        added to psi does not change dpsi/drho, and a rate multiplied by an
        infinite step has nowhere to land.

    ★So the gap between this I_p and the requested one is the INDUCTIVE
    share, and no loop voltage on this tier can close it.  Reaching a
    requested I_p at steady state means solving for the loop voltage as an
    unknown — a different problem from the one this function solves, and one
    the marching tier's controller (T-C16) does on a finite dt.
    """
    L = _ladder()
    kw = dict(vprime=L["vprime"], gm3=L["gm3"], gm2=L["gm2"], fpol=L["fpol"],
              b0=L["b0"], te=L["te"], ti=L["ti"], ne=L["ne"], psi=L["psi"])
    base = stationary.steady_current(
        L["rho"], sigma_par=L["sigma_par"], j_ni=L["j_ni"], **kw)["i_p"]
    half = stationary.steady_current(
        L["rho"], sigma_par=L["sigma_par"], j_ni=0.5 * L["j_ni"], **kw)["i_p"]
    assert half == pytest.approx(0.5 * base, rel=1e-12)
    lowsig = stationary.steady_current(
        L["rho"], sigma_par=0.1 * L["sigma_par"], j_ni=L["j_ni"], **kw)["i_p"]
    assert lowsig == pytest.approx(base, rel=1e-12)
    driven = stationary.steady_current(
        L["rho"], sigma_par=L["sigma_par"], j_ni=L["j_ni"],
        edge_psi_rate=-5.0, **kw)["i_p"]
    assert driven == pytest.approx(base, rel=1e-12)
    shifted = stationary.steady_current(
        L["rho"], sigma_par=L["sigma_par"], j_ni=L["j_ni"],
        edge_psi=0.3, **kw)["i_p"]
    assert shifted == pytest.approx(base, rel=1e-9)


def test_solve_core_refuses_a_heat_channel_with_no_closure():
    with pytest.raises(ValueError, match="heat=False"):
        assembly.solve_core(np.linspace(0, 1, 9), vprime=np.ones(9),
                            gm3=np.ones(9), ne=np.ones(9), te=np.ones(9),
                            ti=np.ones(9), dt=1.0)


# --- the loop ---------------------------------------------------------------

def _driver(**over):
    """A loop whose six steps are arithmetic, so what is judged is the loop."""
    state = {"p": np.ones(5), "q": np.ones(5), "n": 0}

    def transport():
        state["n"] += 1
        #: each round halves the distance to 2.0 — a settling sequence, so a
        #: loop that stops too early and one that never stops both show
        state["p"] = 2.0 - (2.0 - state["p"]) * 0.5
        return {"converged": True, "match_iterations": 3}

    kw = dict(transport=transport,
              pressure=lambda: state["p"],
              q_of=lambda: state["q"],
              max_rounds=6, tolerance=5e-2)
    kw.update(over)
    return state, stationary.stationary_rounds(**kw)


def test_the_first_round_never_counts_as_converged():
    """★★It has no previous round to differ from — the profiles it is
    compared against came from the starting guess.  A loop that reported
    convergence there would be reporting that its guess had not moved."""
    _, out = _driver(max_rounds=6)
    assert out["converged"] is True
    assert len(out["rounds"]) >= 2
    #: and the first round's own numbers were inside the tolerance all along
    assert out["rounds"][0]["d_q"] == pytest.approx(0.0)


def test_one_round_is_a_single_match_and_says_so():
    """★`max_rounds = 1` is the tier's previous behaviour exactly: one match,
    no alternation, and no convergence claim about a loop that never ran."""
    _, out = _driver(max_rounds=1)
    assert len(out["rounds"]) == 1
    assert out["converged"] is True
    assert "d_pressure" not in out["rounds"][0]


def test_a_stalled_inner_solve_ends_the_loop_and_is_named():
    """★Alternating onto a state the inner solve never reached would be
    iterating a quantity nobody solved for."""
    out = stationary.stationary_rounds(
        transport=lambda: {"converged": False, "match_worst": 0.4},
        pressure=lambda: np.ones(4), max_rounds=5)
    assert out["converged"] is False
    assert out["why"] == "match"


def test_running_out_of_rounds_is_a_different_sentence_from_stalling():
    """★★「轮数用完了」 and「里层解不动了」 are different statements about a
    run, and a reader who cannot tell them apart cannot tell whether raising
    the cap would help."""
    step = {"k": 0}

    def pressure():
        #: a profile that keeps moving — every call is a new scale, so the
        #: loop can only stop by running out of rounds
        step["k"] += 1
        return np.array([1.0, 2.0, 3.0]) * (2.0 ** step["k"])

    out = stationary.stationary_rounds(
        transport=lambda: {"converged": True},
        pressure=pressure, max_rounds=3, tolerance=5e-2)
    assert out["converged"] is False
    assert out["why"] == ""
    assert len(out["rounds"]) == 3


def test_a_failed_step_stops_the_loop_with_its_own_reason():
    out = stationary.stationary_rounds(
        transport=lambda: {"converged": True},
        pressure=lambda: np.ones(4),
        current=lambda: {"failed": "steady current failed"},
        max_rounds=4)
    assert out["converged"] is False
    assert out["why"] == "steady current failed"


def test_a_skipped_equilibrium_is_recorded_with_its_reason():
    """★`equilibrium_rounds: 0` is written out rather than omitted: the
    geometry did NOT take part, and a reader must not have to infer that from
    a missing key."""
    out = stationary.stationary_rounds(
        transport=lambda: {"converged": True},
        pressure=lambda: np.ones(4),
        equilibrium=lambda: {"skipped": "metric came from a g-file"},
        max_rounds=3)
    assert out["equilibrium_rounds"] == 0
    assert out["rounds"][0]["equilibrium"] is None
    assert out["rounds"][0]["equilibrium_skipped"] == "metric came from a g-file"


def test_the_order_is_upstreams_sources_pedestal_transport_current_sawtooth_equilibrium():
    """★★The order is the loop's whole content, so it is judged directly:
    步 5 (the crash) rides with 步 4 (the current), and 步 6 comes last."""
    seen = []
    stationary.stationary_rounds(
        transport=lambda: (seen.append("transport"), {"converged": True})[1],
        pressure=lambda: np.ones(4),
        current=lambda: (seen.append("current"), {"i_p": 1.0})[1],
        sawtooth=lambda: (seen.append("sawtooth"), None)[1],
        equilibrium=lambda: (seen.append("equilibrium"), {})[1],
        max_rounds=2)
    assert seen[:4] == ["transport", "current", "sawtooth", "equilibrium"]
