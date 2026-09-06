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


#: ★the core march's marshalling gates left with the state machine for the kernel
#: repository's `tests/test_oracle_marshalling.py` (T-4 第三十刀, 2026-09-06): no host
#: on either side calls `core_march_*` any more.


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


def test_label_drift_is_zero_unless_the_field_moves():
    rho = np.linspace(0.0, 1.0, 5)
    assert np.all(K.label_drift(rho, b0=2.5, b0_dot=0.0) == 0.0)
    got = K.label_drift(rho, b0=2.0, b0_dot=0.4)
    assert np.allclose(got, -0.5 * rho * 0.4 / 2.0)


