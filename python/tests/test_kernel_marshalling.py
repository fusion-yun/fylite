"""The ABI marshalling of the entries that absorbed Python assembly.

★What this module is NOT.  It makes no physics claim — those live in the
kernel's own ``mod tests`` now (``pytest.ini``, and
``tests/PHYSICS-MIGRATION.md``).  What it holds is the layer this
package still owns after the convergence: shapes, lengths, the optional
arguments that mean "this term is off", and the promise that a refused call
raises instead of handing back a plausible array.

Each entry here replaced a numpy expression in the assembly layer, so the
mistake it guards against is the one a caller now makes at the boundary
rather than in the formula.
"""
import numpy as np
import pytest

from fylite import kernel as K
from fylite._paths import KERNEL_LIB

pytestmark = pytest.mark.skipif(not KERNEL_LIB.exists(),
                                reason="libfylite_kernel.so not built "
                                       "(rust/build.sh)")

#: two rectangular elements, the six-parallel-array C-ABI layout

#: ★`channel_field`'s two orientation gates left with the wrapper for the kernel
#: repository's `tests/test_oracle_marshalling.py` (T-4 第二十五刀, 2026-09-06).


def test_interp_is_the_numpy_it_replaced_bit_for_bit():
    """★48 call sites moved onto this entry; the claim is that not one number
    changed.  numpy is the REFERENCE here, not a second implementation — the
    kernel function was written to its semantics on purpose, so this is the
    gate that says so out loud.
    """
    rng = np.random.default_rng(3)
    for _ in range(200):
        m, n = int(rng.integers(1, 40)), int(rng.integers(1, 30))
        xp = np.sort(rng.uniform(-3.0, 3.0, m))
        yp = rng.normal(size=m) * 10.0
        x = rng.uniform(-5.0, 5.0, n)          # deliberately outside xp too
        assert np.array_equal(K.interp(x, xp, yp), np.interp(x, xp, yp))


def test_interp_gives_back_the_shape_it_was_handed():
    assert np.ndim(K.interp(0.5, [0.0, 1.0], [2.0, 4.0])) == 0
    assert K.interp(np.zeros((2, 3)) + 0.5, [0.0, 1.0], [0.0, 10.0]).shape == (2, 3)
    with pytest.raises(K.KernelError):
        K.interp([0.5], [0.0, 1.0], [1.0])     # xp and yp of different lengths


def test_the_uniform_resamplers_keep_the_ends():
    src = [1.0, 2.0, 4.0, 7.0, 11.0]
    got = K.resample_uniform(src, 9)
    assert got[0] == 1.0 and got[-1] == 11.0
    assert np.array_equal(K.resample_uniform(src, 5), np.asarray(src))
    #: extrapolated, not clamped — the ends carry the end segments' slope
    q = K.to_uniform_extrap([0.2, 0.5, 0.8], [2.0, 5.0, 8.0], 11)
    assert abs(q[0]) < 1e-12 and abs(q[-1] - 10.0) < 1e-12


def _st(**over):
    """One surface, in the CGS the map speaks, with nothing degenerate.

    ★Ti != Te on purpose: it is the only thing separating TGLF's temperature
    norm from NEO's, so a case with Ti == Te cannot see the trap at all.
    """
    st = dict(a=60.0, rmin=30.0, rmaj=170.0, zmag=1.5, drmaj=-0.12,
              dzmag=0.03, q=2.35, s=1.15, shear=1.15, kappa=1.62,
              s_kappa=0.11, delta=0.24, s_delta=0.17, zeta=0.05, s_zeta=0.02,
              b_unit=2.1e4, te=2050.0, ne=3.1e13, dlnnedr=0.0125,
              dlntedr=0.0310, signb=-1.0, signq=1.0, shape={},
              ions=[dict(z=1.0, mass=3.34358e-24, ni=2.75e13, ti=1830.0,
                         dlnnidr=0.0118, dlntidr=0.0335)])
    st.update(over)
    return st


def test_sample_grid_is_nan_off_the_grid_and_exact_on_a_node():
    """★The out-of-grid answer is the whole reason this is one host.

    NaN, not a clamped edge value: a caller that clamps reads the boundary
    node for every point beyond it, which looks like a field that flattens
    outside the vessel rather than one that was never measured there.
    ``psin_along`` deliberately answers ``+inf`` for the same geometry — a
    different question, and it says so at its own definition.  Two
    conventions is fine; two IMPLEMENTATIONS of either is not.
    """
    g = K.grid_of(np.linspace(1.0, 3.0, 5), np.linspace(-1.0, 1.0, 5))
    f = np.arange(25.0).reshape(5, 5)
    #: exact on a node
    assert K.sample_grid(g, f, [1.5], [-0.5])[0] == f[1, 1]
    #: the middle of a cell is the mean of its four corners
    mid = K.sample_grid(g, f, [1.25], [-0.75])[0]
    assert mid == pytest.approx((f[0, 0] + f[0, 1] + f[1, 0] + f[1, 1]) / 4)
    #: off the grid, both sides, both axes
    off = K.sample_grid(g, f, [0.9, 3.1, 2.0, 2.0], [0.0, 0.0, -1.1, 1.1])
    assert not np.any(np.isfinite(off))
    #: ★the far edge is OUT, not in: i0 == nr-1 has no i0+1 to blend with
    assert not np.isfinite(K.sample_grid(g, f, [3.0], [0.0])[0])


def test_sample_grid_is_the_bilinear_it_replaced_bit_for_bit():
    """Two hosts held this read — the design layer's ``_sample`` and the
    browser's ``FyPhys.sample``.  numpy is the REFERENCE here, not a rival.
    """
    rng = np.random.default_rng(19)
    g = K.grid_of(np.linspace(1.05, 2.45, 71), np.linspace(-1.3, 1.3, 91))
    psi = rng.normal(size=(71, 91)) * 0.4

    def one(r, z):
        fi, fj = (r - g.r0) / g.dr, (z - g.z0) / g.dz
        i0, j0 = int(np.floor(fi)), int(np.floor(fj))
        if i0 < 0 or j0 < 0 or i0 >= g.nr - 1 or j0 >= g.nz - 1:
            return float("nan")
        u, v = fi - i0, fj - j0
        return float((1 - u) * (1 - v) * psi[i0, j0]
                     + u * (1 - v) * psi[i0 + 1, j0]
                     + (1 - u) * v * psi[i0, j0 + 1]
                     + u * v * psi[i0 + 1, j0 + 1])

    r = rng.uniform(0.95, 2.55, 2000)      # deliberately off the grid too
    z = rng.uniform(-1.4, 1.4, 2000)
    got = K.sample_grid(g, psi, r, z)
    want = np.array([one(r[i], z[i]) for i in range(2000)])
    assert np.array_equal(np.isnan(got), np.isnan(want))
    m = np.isfinite(want)
    assert m.sum() > 500, "this case must exercise the in-grid path"
    assert np.array_equal(got[m], want[m])


# --------------------------------------------------------------------------- #
# the core march — every channel on one time step
#
# ★The entry that absorbed the operator splitting the assembly layer used to
# do by hand (`solve_te_ti` then `solve_density` then `solve_psi`), so the
# mistake it guards against is now a boundary one: a switch that does not
# reach the machine, a count that arrives as the wrong argument, a closure
# field silently defaulted.
# --------------------------------------------------------------------------- #
def _core_grid(n=13):
    rho = np.linspace(0.0, 1.0, n)
    return rho, 2.0 * rho + 1e-3, np.ones(n)


def test_core_march_returns_every_channel_on_the_grid():
    n = 13
    rho, vp, gm3 = _core_grid(n)
    r = K.core_march(rho, te=np.full(n, 300.0), ti=np.full(n, 280.0),
                     ni=np.full(n, 1e19), vprime=vp, gm3=gm3,
                     closure=lambda st: {"chi_e": np.ones(n),
                                         "chi_i": np.ones(n)},
                     dt=1e-3, edge_te=100.0, edge_ti=100.0, max_outer=2)
    for k in ("te", "ti", "ne", "psi", "q", "s_exchange"):
        assert r[k].shape == (n,), k
        assert np.all(np.isfinite(r[k])), k
    assert isinstance(r["steady"], bool)
    assert isinstance(r["outer_steps"], int)
    assert r["psi_repaired"] == 0.0          # the channel was not switched on


def test_core_march_carries_the_step_cap_and_the_picard_count_across():
    """★The case that catches a mis-declared argument ORDER.

    A C call reads its arguments by position, and on this ABI integers and
    floats travel in different register files — so a declaration with the
    right types in the wrong order can still return a plausible profile.
    What it cannot do is get the two COUNTS right: the closure is called
    exactly ``max_outer * n_coupling`` times when nothing settles first.
    """
    n = 9
    rho, vp, gm3 = _core_grid(n)
    calls = []

    def closure(state):
        calls.append(state["te"].copy())
        return {"chi_e": np.ones(n), "chi_i": np.ones(n)}

    r = K.core_march(rho, te=np.full(n, 900.0), ti=np.full(n, 900.0),
                     ni=np.full(n, 1e19), vprime=vp, gm3=gm3,
                     q_e=np.full(n, 3e4), q_i=np.full(n, 3e4),
                     closure=closure, dt=1e-3, edge_te=100.0, edge_ti=100.0,
                     max_outer=3, n_coupling=2, tol_steady=1e-15)
    assert len(calls) == 3 * 2
    assert r["outer_steps"] == 3
    assert not r["steady"]                   # it ran out of steps, and says so


def test_core_march_defaults_the_closure_fields_it_is_not_given():
    """A closure that answers only what its channels need is complete: the
    fields for a channel that is off are zero, not missing."""
    n = 7
    rho, vp, gm3 = _core_grid(n)
    r = K.core_march(rho, te=np.full(n, 200.0), ti=np.full(n, 200.0),
                     ni=np.full(n, 1e19), vprime=vp, gm3=gm3,
                     closure=lambda st: {}, dt=1e-3, edge_te=200.0,
                     edge_ti=200.0, max_outer=2)
    assert np.allclose(r["te"], 200.0)
    assert np.all(r["s_exchange"] == 0.0)


def test_core_march_refuses_a_march_with_no_channel_switched_on():
    n = 7
    rho, vp, gm3 = _core_grid(n)
    with pytest.raises(K.KernelError, match="at least one channel"):
        K.core_march(rho, te=np.full(n, 200.0), ti=np.full(n, 200.0),
                     ni=np.full(n, 1e19), vprime=vp, gm3=gm3,
                     closure=lambda st: {}, dt=1e-3, edge_te=1.0,
                     edge_ti=1.0, heat=False)


def test_core_march_switches_the_density_channel_on_by_its_coefficients():
    """The density channel moves only when the closure supplies its D — and
    when it does, the heat pair sees the new n WITHIN the step."""
    n = 11
    rho, vp, gm3 = _core_grid(n)
    dt, s_n, n0 = 1e-3, 1e21, 1e19
    r = K.core_march(rho, te=np.full(n, 600.0), ti=np.full(n, 600.0),
                     ni=np.full(n, n0), vprime=vp, gm3=gm3, s_n=np.full(n, s_n),
                     closure=lambda st: {}, dt=dt, edge_te=600.0,
                     edge_ti=600.0, edge_ni=[n0 + dt * s_n], density=True,
                     max_outer=1, n_coupling=1)
    assert np.allclose(r["ne"][:-1], n0 + dt * s_n, rtol=1e-9)
    #: no conduction and no heating, so (3/2)V'nT is a constant of the step
    assert np.allclose(r["te"][:-1], 600.0 * n0 / (n0 + dt * s_n), rtol=1e-9)


def test_label_drift_is_zero_unless_the_field_moves():
    rho = np.linspace(0.0, 1.0, 5)
    assert np.all(K.label_drift(rho, b0=2.5, b0_dot=0.0) == 0.0)
    got = K.label_drift(rho, b0=2.0, b0_dot=0.4)
    assert np.allclose(got, -0.5 * rho * 0.4 / 2.0)


def test_the_previous_metric_is_off_by_default_and_carries_the_volume_change():
    """★The `dV'/dt` a caller meets when it re-traces the metric between
    rounds: with no conduction and no heating, `(3/2) V' n T` is a constant
    of the step, so a 4 % larger volume must cool the plasma by 4 %."""
    n = 11
    rho, vp, gm3 = _core_grid(n)
    kw = dict(te=np.full(n, 500.0), ti=np.full(n, 500.0), ni=np.full(n, 1e19),
              vprime=vp, gm3=gm3, closure=lambda st: {}, dt=1e-3,
              edge_te=500.0, edge_ti=500.0, max_outer=1)
    off = K.core_march(rho, **kw)
    same = K.core_march(rho, vprime_old=vp, **kw)
    assert np.array_equal(off["te"], same["te"])
    moved = K.core_march(rho, vprime_old=vp / 1.04, **kw)
    assert moved["te"][:-1] == pytest.approx(500.0 / 1.04, rel=1e-9)


def test_a_field_that_is_not_ramping_is_a_dead_path():
    n = 11
    rho, vp, gm3 = _core_grid(n)
    kw = dict(te=900.0 - 700.0 * rho ** 2, ti=np.full(n, 500.0),
              ni=np.full(n, 1e19), vprime=vp, gm3=gm3, b0=2.5,
              closure=lambda st: {"chi_e": np.full(n, 0.5),
                                  "chi_i": np.full(n, 0.5)},
              dt=1e-3, edge_te=200.0, edge_ti=200.0, max_outer=2)
    still = K.core_march(rho, **kw)
    named = K.core_march(rho, b0_dot=0.0, **kw)
    assert np.array_equal(still["te"], named["te"])
    #: a rising field contracts the labels, so the plasma drifts outward
    #: through the fixed grid and the axis cools
    assert K.core_march(rho, b0_dot=2.0, **kw)["te"][0] < still["te"][0]
    assert K.core_march(rho, b0_dot=-2.0, **kw)["te"][0] > still["te"][0]


def test_the_ion_channels_are_ion_major_and_the_electrons_follow_them():
    """★The layout is the one every multi-species block in this ABI uses —
    ion-major — and the electron density is not among the inputs at all."""
    n = 11
    rho, vp, gm3 = _core_grid(n)
    n_d, n_c, dt = 3e19, 2e18, 1e-3
    ni = np.concatenate([np.full(n, n_d), np.full(n, n_c)])
    s_n = np.concatenate([np.zeros(n), np.full(n, n_c / dt)])   # fuel carbon
    r = K.core_march(rho, te=np.full(n, 300.0), ti=np.full(n, 300.0),
                     ni=ni, z=[1.0, 6.0], edge_ni=[n_d, 2 * n_c],
                     vprime=vp, gm3=gm3, s_n=s_n,
                     closure=lambda st: {"d_n": np.zeros(2 * n)},
                     dt=dt, edge_te=300.0, edge_ti=300.0, heat=False,
                     density=True, max_outer=1, n_coupling=1)
    assert r["ni"].shape == (2, n)
    assert r["ni"][0][:-1] == pytest.approx(n_d, rel=1e-9)
    assert r["ni"][1][:-1] == pytest.approx(2 * n_c, rel=1e-6)
    #: six electrons per carbon, and the deuterium unchanged
    assert r["ne"][:-1] == pytest.approx(n_d + 6.0 * 2 * n_c, rel=1e-6)
    #: the closure's coefficients follow the same layout, and a block of the
    #: wrong length is refused rather than broadcast
    with pytest.raises(K.KernelError):
        K.core_march(rho, te=np.full(n, 300.0), ti=np.full(n, 300.0), ni=ni,
                     z=[1.0, 6.0], vprime=vp, gm3=gm3,
                     closure=lambda st: {"d_n": np.zeros(n + 1)},
                     dt=dt, edge_te=300.0, edge_ti=300.0, density=True,
                     max_outer=1)


def test_the_step_controller_is_off_by_default_and_reports_what_it_did():
    n = 13
    rho, vp, gm3 = _core_grid(n)
    kw = dict(te=900.0 - 700.0 * rho ** 2, ti=np.full(n, 500.0),
              ni=np.full(n, 1e19), vprime=vp, gm3=gm3,
              q_e=np.full(n, 2e4), q_i=np.full(n, 2e4),
              closure=lambda st: {"chi_e": np.full(n, 1e-4),
                                  "chi_i": np.full(n, 1e-4)},
              edge_te=200.0, edge_ti=200.0, max_outer=8, tol_steady=1e-14)
    off = K.core_march(rho, dt=1e-4, **kw)
    assert off["dt"] == 1e-4 and off["retries"] == 0
    #: ★a nearly frozen channel: the steps barely move, so the controller
    #: asks for a bigger one
    on = K.core_march(rho, dt=1e-4, dt_target=1e-3, dt_min=1e-8, dt_max=1.0,
                      **kw)
    assert on["dt"] > off["dt"]
    #: and it stays inside the cap it was given
    capped = K.core_march(rho, dt=1e-4, dt_target=1e9, dt_min=1e-8,
                          dt_max=2e-4, **kw)
    assert capped["dt"] <= 2e-4 + 1e-18


def test_an_adaptive_steady_solve_is_refused_at_the_boundary():
    n = 9
    rho, vp, gm3 = _core_grid(n)
    with pytest.raises(K.KernelError):
        K.core_march(rho, te=np.full(n, 300.0), ti=np.full(n, 300.0),
                     ni=np.full(n, 1e19), vprime=vp, gm3=gm3,
                     closure=lambda st: {}, dt=float("inf"), dt_target=1e-3,
                     dt_min=1e-9, dt_max=1.0, edge_te=300.0, edge_ti=300.0)


# --- the operating domain, the flux account, and the start ------------------
#
# ★These entries carry the design scenario's own CRITERIA, and they have no
# second implementation anywhere — so what is asserted here is either an
# identity the entry claims for itself or a published number from outside
# this repository.  The physics claims sit in the kernel's `mod tests`; what
# this module owns is the boundary: shapes, optional arguments, and the
# refusals.


#: ★the Δ* operator's two gates left with the wrapper for the kernel repository's
#: `tests/test_oracle_marshalling.py` (T-4 第二十九刀, 2026-09-06): `code/cocos`
#: measures the convention now.


