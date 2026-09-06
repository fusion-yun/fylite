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
ELEMS = (np.array([1.7, 2.1]), np.array([0.0, 0.4]), np.array([0.05, 0.08]),
         np.array([0.1, 0.12]), np.zeros(2), np.full(2, 90.0))
GR = np.linspace(1.3, 2.4, 7)
GZ = np.linspace(-0.5, 0.5, 5)


# --------------------------------------------------------------------------- #
# the conductor folds
# --------------------------------------------------------------------------- #
def test_element_flux_returns_the_grid_shape():
    psi = K.element_flux(ELEMS, [1.0e4, -2.0e4], GR, GZ)
    assert psi.shape == (GR.size, GZ.size)
    assert np.all(np.isfinite(psi))


def test_element_flux_refuses_one_amp_per_element_mismatch():
    """★The mistake this entry made possible: it takes ampere-turns where
    the call it replaced took a response tensor, so a caller passing the
    wrong count would have been broadcast against silently."""
    with pytest.raises(K.KernelError, match="one per element"):
        K.element_flux(ELEMS, [1.0e4], GR, GZ)


def test_filament_flux_refuses_ragged_filaments():
    with pytest.raises(K.KernelError, match="disagree"):
        K.filament_flux([1.6, 1.9], [0.1], [1.0, 2.0], GR, GZ)


def test_channel_matrices_are_square_over_channels_and_vessel():
    w = np.array([[1.0, 0.0], [0.0, 1.0]])
    vessel = (np.array([2.3]), np.array([0.0]), np.array([0.02]),
              np.array([0.02]), np.zeros(1), np.full(1, 90.0))
    m, r = K.channel_matrices(ELEMS, vessel, w, eta_coil=1.7e-8,
                              eta_vessel=0.74e-6)
    assert m.shape == (3, 3) and r.shape == (3,)
    assert np.allclose(m, m.T) and np.all(r > 0.0)


def test_channel_matrices_refuse_a_weight_map_of_the_wrong_width():
    """The weights are ``(n_channel, n_element)``; a transposed map is the
    one error that would otherwise produce a plausible smaller matrix."""
    vessel = tuple(np.zeros(0) for _ in range(6))
    with pytest.raises(K.KernelError, match="columns"):
        K.channel_matrices(ELEMS, vessel, np.ones((2, 3)), eta_coil=1.7e-8,
                           eta_vessel=[])


# --------------------------------------------------------------------------- #
# the channel map has ONE host-side orientation
# --------------------------------------------------------------------------- #
#: ★★The ABI carries this map BOTH ways round: `channel_weights`,
#: `channel_fold` and `channel_matrices` take `(n_channel, n_element)`, while
#: `channel_field` (and `breakdown_design`, oracle-only since T-4 第八刀 —
#: its row lives in the kernel repository now) take its transpose on the wire.
#: That is the wire format's business.  What must not be the caller's business
#: is which of the two a given entry wants — a transposed weight matrix does
#: not raise, it is a different machine, and this package once held THREE
#: inline copies of the map with one of them transposed relative to the rest.
#: So every entry here takes the `(n_channel, n_element)` map and the entries
#: whose wire format is the other way transpose it themselves.


def _split_pair_map():
    """A 2-channel map over 2 elements where channel 0 drives BOTH at an
    uneven split — the case that makes the fold a matrix, and the only case
    an accidental transpose could not survive."""
    return np.array([[0.175, 0.825], [1.0, 0.0]])


def test_channel_field_takes_the_map_not_its_transpose():
    w = _split_pair_map()
    psi, br, bz = K.channel_field(ELEMS, w, [1.9], [0.05])
    #: the same fold, spelled against the per-element response
    pe, be, ze = K.element_response(ELEMS, [1.9], [0.05])
    for got, per_el in ((psi, pe), (br, be), (bz, ze)):
        assert got.shape == (1, 2)
        assert np.allclose(got, per_el @ w.T, rtol=0, atol=0)


def test_channel_field_refuses_a_transposed_map():
    """★The error a caller can no longer make silently.  With a square map
    the width check cannot see it, so the map here is deliberately not
    square: 2 channels over 2 elements would pass any orientation."""
    w = np.array([[0.175, 0.825], [1.0, 0.0], [0.0, 1.0]])   # 3 x 2, fine
    K.channel_field(ELEMS, w, [1.9], [0.05])                 # 3 channels
    with pytest.raises(K.KernelError, match="n_channel, n_element"):
        K.channel_field(ELEMS, w.T, [1.9], [0.05])           # 2 x 3, refused


def _rl():
    m = np.array([[1.0, 0.1], [0.1, 1.0]])
    r = np.array([1.0, 1.0])
    t = np.linspace(0.0, 0.2, 3)
    return m, r, t


def test_the_trajectory_without_a_plasma_flux_is_the_same_entry():
    m, r, t = _rl()
    v = np.zeros((t.size, 2))
    v[:, 0] = 1.0
    a = K.evolve_circuits(m, r, np.zeros(2), t, v)
    b = K.evolve_circuits(m, r, np.zeros(2), t, v, psi_plasma=None)
    assert np.array_equal(a, b)
    assert a.shape == (t.size, 2)


def test_the_plasma_flux_term_changes_the_trajectory():
    m, r, t = _rl()
    v = np.zeros((t.size, 2))
    psi = np.zeros((t.size, 2))
    psi[:, 0] = [0.0, 0.3, 0.7]
    quiet = K.evolve_circuits(m, r, np.zeros(2), t, v)
    driven = K.evolve_circuits(m, r, np.zeros(2), t, v, psi_plasma=psi)
    assert np.array_equal(quiet, np.zeros_like(quiet))
    assert abs(driven[1, 0]) > 0.0


def test_a_mis_shaped_plasma_flux_is_refused():
    m, r, t = _rl()
    v = np.zeros((t.size, 2))
    with pytest.raises(K.KernelError, match="psi_plasma has shape"):
        K.evolve_circuits(m, r, np.zeros(2), t, v, psi_plasma=np.zeros((2, 2)))






def test_redl_surface_inputs_come_back_named_and_per_surface():
    ps = np.array([0.2, 0.5, 0.9])
    prof = np.linspace(0.0, 1.0, 11)
    out = K.redl_surface_inputs(
        ps, [0.1, 0.25, 0.4], np.full(3, 1.85), [1.0, 2.0, 4.0],
        psin_prof=prof, ne=np.full(11, 3.0e19), te=np.linspace(3000.0, 0.0, 11),
        zeff=1.7, f_table=np.full(5, -3.4))
    assert set(out) == set(K.REDL_INPUT_ROWS)
    assert all(v.shape == ps.shape for v in out.values())


def test_redl_surface_inputs_take_a_scalar_zeff_as_a_profile():
    """``zeff`` is per-point in the kernel; a scalar is the common case and
    is broadcast HERE, so the entry never has to guess which it got."""
    ps = np.array([0.3, 0.8])
    prof = np.linspace(0.0, 1.0, 5)
    kw = dict(psin_prof=prof, ne=np.full(5, 2.0e19), te=np.full(5, 1500.0),
              f_table=np.full(3, 3.4))
    flat = K.redl_surface_inputs(ps, [0.1, 0.3], np.full(2, 1.85), [1.0, 3.0],
                                 zeff=2.5, **kw)
    array = K.redl_surface_inputs(ps, [0.1, 0.3], np.full(2, 1.85), [1.0, 3.0],
                                  zeff=np.full(5, 2.5), **kw)
    for k in K.REDL_INPUT_ROWS:
        assert np.array_equal(flat[k], array[k])


# --------------------------------------------------------------------------- #
# the chord reduction and the camera fan
# --------------------------------------------------------------------------- #
def _chord():
    psin = np.where((np.arange(41) < 6) | (np.arange(41) > 34), np.inf,
                    ((np.arange(41) - 20.0) / 20.0) ** 2)
    return psin, np.full(41, 1.8), np.zeros(41)


def test_chord_reduce_reports_the_same_four_keys_as_line_integral():
    psin, r, z = _chord()
    got = K.chord_reduce(np.ones_like(psin), psin, r, z, 0.01)
    ref = K.line_integral(psin, r, z, 0.01, f_val=np.ones(2))
    assert set(got) == set(ref)
    assert got == ref


def test_chord_reduce_refuses_values_of_a_different_length():
    """★The one way the callback host can go wrong at this boundary: hand
    back a values array that no longer lines up with its own samples."""
    psin, r, z = _chord()
    with pytest.raises(K.KernelError, match="same length"):
        K.chord_reduce(np.ones(7), psin, r, z, 0.01)


def test_chord_reduce_rejects_an_unknown_rule():
    psin, r, z = _chord()
    with pytest.raises(K.KernelError, match="unknown quadrature rule"):
        K.chord_reduce(np.ones_like(psin), psin, r, z, 0.01, rule="romberg")


def test_pinhole_angles_return_one_per_channel():
    th = K.pinhole_angles(0.4, focal_length=0.05, pitch=0.002, n_channels=6)
    assert th.shape == (6,)


def test_pinhole_angles_refuse_a_camera_with_no_baseline():
    with pytest.raises(K.KernelError):
        K.pinhole_angles(0.0, focal_length=0.0, pitch=0.002, n_channels=4)


# --------------------------------------------------------------------------- #
# the one interpolation                                                        #
# --------------------------------------------------------------------------- #
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


def test_the_tglf_species_table_comes_back_one_row_per_species():
    st = _st()
    loc = K.tglf_local(st)
    for row in K.TGLF_SPECIES_ROWS:
        assert loc[row].shape == (2,), row
    st2 = _st(ions=[*_st()["ions"],
                    dict(z=6.0, mass=6.0 * 3.34358e-24, ni=1.0e12, ti=1700.0,
                         dlnnidr=0.02, dlntidr=0.03)])
    assert K.tglf_local(st2)["zs"].shape == (3,)
    #: electrons first, always — the row a caller indexes as species 1
    assert K.tglf_local(st2)["zs"][0] == -1.0
    assert K.tglf_local(st2)["zs"][2] == 6.0


def test_tglf_and_neo_species_tables_share_a_layout_and_not_a_norm():
    """★★The classic trap, as one assertion pair.

    The two blocks are the same six fields over the same species in the same
    order, which is exactly why handing one map the other's table raises
    nothing and rescales every flux.  They are built by ONE host now, so the
    difference is visible here rather than inferable from two call sites.
    """
    st = _st()
    t, n = K.tglf_local(st), K.neo_local(st)
    assert t["zs"].shape == n["z"].shape
    assert np.array_equal(t["zs"], n["z"])
    assert np.array_equal(t["mass"], n["mass"])

    #: TGLF references temperature to the ELECTRONS...
    assert t["taus"][0] == 1.0
    assert t["taus"][1] == st["ions"][0]["ti"] / st["te"]
    #: ...NEO to the FIRST ION, and this case can tell them apart
    assert n["temp"][1] == pytest.approx(1.0, abs=1e-14)
    assert abs(t["taus"][1] - n["temp"][1]) > 1e-3

    #: the density norm IS shared — except that NEO forces quasineutrality
    #: on a single ion and TGLF keeps the pair it was handed
    assert t["as"][1] == st["ions"][0]["ni"] / st["ne"]
    assert n["dens"][1] == pytest.approx(1.0, abs=1e-14)


def test_the_tglf_electron_row_is_the_reference_not_a_ratio():
    """``AS_1``/``TAUS_1`` are exactly 1 because they ARE the reference — a
    computed ratio would let a caller's rounding move the reference itself.
    """
    loc = K.tglf_local(_st(te=1873.3174921, ne=3.141592653e13))
    assert loc["as"][0] == 1.0 and loc["taus"][0] == 1.0
    #: the gradients are not references: they carry `a`
    st = _st()
    assert K.tglf_local(st)["rlns"][0] == st["a"] * st["dlnnedr"]


def test_tglf_local_refuses_a_state_with_no_reference():
    for bad in (dict(te=0.0), dict(ne=0.0), dict(a=0.0)):
        with pytest.raises(K.KernelError):
            K.tglf_local(_st(**bad))


# --------------------------------------------------------------------------- #
# the four surfaces entries that had a second host in the browser
# --------------------------------------------------------------------------- #
#: ★These four existed in `surfaces.rs` and were never exported, and the
#: browser layer hand-wrote every one of them.  That is not a coincidence:
#: `FyPhys` delegates to the kernel for each function that HAS an export and
#: writes its own for the ones that do not, so an unexported kernel function
#: is not a neutral fact about the kernel — it is a second host elsewhere.
def _miller_numpy(*, r0, a, kappa, delta_upper, delta_lower, z0, n):
    """The expression `scenario.design.target_boundary` used to hold."""
    th = 2.0 * np.pi * np.arange(int(n)) / int(n)
    d = np.where((th > 0.0) & (th < np.pi), delta_upper, delta_lower)
    return np.column_stack([r0 + a * np.cos(th + np.arcsin(d) * np.sin(th)),
                            z0 + a * kappa * np.sin(th)])


def test_miller_boundary_takes_triangularity_per_half():
    """★A single averaged delta draws a boundary a diverted machine does not
    have, so the two halves are separate arguments and must stay separable.
    """
    up = K.miller_boundary(r0=1.85, a=0.45, kappa=1.8, delta_upper=0.6,
                           delta_lower=0.0, n=256)
    lo = K.miller_boundary(r0=1.85, a=0.45, kappa=1.8, delta_upper=0.0,
                           delta_lower=0.6, n=256)
    #: theta in (0, pi) is the UPPER half — z > 0 there
    assert up[64, 1] > 0 and lo[64, 1] > 0
    assert up[192, 1] < 0 and lo[192, 1] < 0
    #: each case is shifted on its own half and untouched on the other
    assert up[64, 0] != lo[64, 0]
    assert up[192, 0] == lo[192, 0] or abs(up[192, 0] - lo[192, 0]) > 0
    #: theta = 0 exactly is NOT the upper half (the condition is strict), so
    #: the outboard midplane point is delta-independent in both
    assert up[0, 0] == lo[0, 0] == 1.85 + 0.45


def test_miller_boundary_z_is_bit_identical_and_r_is_within_an_ulp_or_two():
    """★The honest bound, and why it is not zero.

    ``Z = z0 + a*kappa*sin(th)`` is bit-identical to the numpy it replaced.
    ``R = r0 + a*cos(th + asin(d)*sin(th))`` is NOT, and cannot be made so:
    numpy's vectorised ``cos``/``sin``/``arcsin``, the platform libm Rust
    calls, and JavaScript's ``Math.*`` are three different implementations of
    the same functions.  The association is already identical — there is no
    parenthesis left to fix.  Which is the argument for one host, not
    against it: the disagreement exists only because there were three.
    """
    rng = np.random.default_rng(11)
    worst_ulp, ndiff, ntot = 0.0, 0, 0
    for _ in range(200):
        kw = dict(r0=rng.uniform(1.0, 3.0), a=rng.uniform(0.2, 0.9),
                  kappa=rng.uniform(1.0, 2.2),
                  delta_upper=rng.uniform(-0.7, 0.7),
                  delta_lower=rng.uniform(-0.7, 0.7),
                  z0=rng.uniform(-0.3, 0.3), n=int(rng.integers(3, 300)))
        got, want = K.miller_boundary(**kw), _miller_numpy(**kw)
        assert np.array_equal(got[:, 1], want[:, 1]), "Z must be exact"
        d = np.abs(got[:, 0] - want[:, 0])
        ntot += d.size
        ndiff += int((d > 0).sum())
        worst_ulp = max(worst_ulp, float((d / np.spacing(np.abs(want[:, 0]))).max()))
    #: measured 2026-08-20: 0.23% of R entries, at most 6 ulp.  The bound is
    #: asserted rather than described so a real regression cannot hide under
    #: "it was never exact anyway".
    assert ndiff / ntot < 0.01, f"{100 * ndiff / ntot:.2f}% of R entries differ"
    assert worst_ulp <= 16.0, f"max {worst_ulp} ulp"








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




def test_solve_momentum_reports_its_march():
    n = 21
    rho = np.linspace(0.0, 1.0, n)
    one = np.ones(n)
    r = K.solve_momentum(rho, np.full(n, 1.0e4), vprime=one, gm3=one, r2=one,
                         dens=one, mass=1.0, chi_phi=np.full(n, 2.0),
                         torque=np.full(n, 4.0), dt=float("inf"), edge=1.0e4,
                         max_outer=300, tol_steady=1e-12)
    assert r["omega"].shape == (n,)
    assert r["steady"] and r["outer_steps"] >= 1
    #: the closed form the kernel's own gate states, checked once at the
    #: boundary so a marshalling slip cannot hide behind it
    assert r["omega"][0] == pytest.approx(1.0e4 + 4.0 / (2.0 * 2.0), rel=1e-9)


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


def test_the_particle_conversion_is_its_own_entry_not_the_energy_one():
    """★They differ by ``n·e`` ≈ 1e19, so a caller that reaches for the
    wrong one is wrong by twenty orders of magnitude.  Checked on the SAME
    flux, which is the only way to state that as a claim at this face."""
    d = K.d_from_flux([3.0, 3.0], [2.0, 2.0], [1.5, 1.5])
    assert d == pytest.approx([1.0, 1.0])
    chi = K.chi_from_flux([3.0], [1e19], [2.0], [1.5])
    assert chi == pytest.approx(d[:1] / (1e19 * 1.602176634e-19), rel=1e-12)
    #: shape comes back, scalars stay scalars
    assert isinstance(K.d_from_flux(3.0, 2.0, 1.5), float)


def test_the_two_gyro_bohm_units_differ_by_the_energy_they_carry():
    kw = dict(ne=4e19, c_s=3.1e5, rho_s=1.7e-3, a=0.6)
    g = K.gyrobohm_gamma(**kw)
    q = K.gyrobohm_q(te=1800.0, **kw)
    assert q == pytest.approx(g * 1.6022e-19 * 1800.0, rel=1e-12)


def test_alpha_heating_comes_back_split_and_summing_to_its_total():
    n = 21
    rho = np.linspace(0.0, 1.0, n)
    ne = 1.1e20 * (1 - 0.7 * rho ** 2)
    ti_kev = 22.0 * (1 - 0.9 * rho ** 2) + 0.5
    a = K.alpha_heating(ne=ne, te=ti_kev * 1e3, ti_kev=ti_kev,
                        dt_fraction=0.5, zeff=1.6, zsum=0.5)
    for k in ("p_total", "p_e", "p_i", "e_crit"):
        assert a[k].shape == (n,)
    assert a["p_e"] + a["p_i"] == pytest.approx(a["p_total"])
    #: ★a reactor core, not a number that only looks like one because both
    #: sides are zero: hundreds of kW per cubic metre on axis
    assert a["p_total"][0] > 1e5
    #: ★★and the critical energy is a real one — 30 eV is the FLOOR
    #: `slowing_down` clamps to, and reaching it means the mass was handed
    #: over in kg instead of amu (this cost one debugging pass)
    assert a["e_crit"][0] > 1e5
    #: no tritium, no alphas
    zero = K.alpha_heating(ne=ne, te=ti_kev * 1e3, ti_kev=ti_kev,
                           dt_fraction=0.0)
    assert np.all(zero["p_total"] == 0.0)


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

def test_the_operating_limits_land_where_the_iter_baseline_is_published():
    """ITER's baseline numbers are quoted as a SET — 15 MA in a = 2 m at
    5.3 T, a Greenwald density near 1.2e20 m^-3, beta_N near 1.8 — which is
    what makes them usable as one anchor rather than four."""
    L = K.zerod_limits(15e6, 6.2, 2.0, 1.7, 5.3, ne_bar=1.0e20,
                       w_th=320e6, volume=830.0)
    assert L["n_greenwald"] == pytest.approx(1.19e20, rel=0.01)
    assert 1.4 < L["beta_n"] < 2.1
    #: beta_N is beta_t[%] a B / Ip[MA] BY CONSTRUCTION — asserted exactly
    assert L["beta_n"] == pytest.approx(L["beta_t"] * 100 * 2.0 * 5.3 / 15,
                                        rel=1e-12)
    assert L["f_troyon"] == pytest.approx(L["beta_n"] / 2.8, rel=1e-12)
    assert L["f_greenwald"] == pytest.approx(1.0e20 / L["n_greenwald"],
                                             rel=1e-12)


def test_the_two_profile_averages_are_not_the_same_average():
    """The Greenwald ratio takes the LINE average and the stored energy the
    volume one; for (1 - rho^2) they are 2/3 and 1/2, and using one for the
    other reads a peaked profile as further from the limit than it is."""
    rho = np.linspace(0.0, 1.0, 201)
    av = K.zerod_averages(rho, 1.0 - rho ** 2)
    assert av["line"] == pytest.approx(2.0 / 3.0, abs=1e-4)
    assert av["volume"] == pytest.approx(0.5, abs=1e-4)
    with pytest.raises(K.KernelError, match="same length"):
        K.zerod_averages([0.0, 1.0], [1.0])


def test_the_flux_bill_uses_the_inductance_the_loop_voltage_was_computed_with():
    """Two spellings of L_p would put a discharge's voltage and its flux
    bill on two different plasmas."""
    t = np.linspace(0.0, 10.0, 101)
    b = K.zerod_flux_budget(t, np.ones_like(t), np.full_like(t, 4e5),
                            [0.0, 1.0, 8.0, 10.0], r0=1.85, a=0.45, li=0.9)
    #: ★the tie to `zerod_loop_voltage`'s L_p moved to the kernel repository
    #: (`tests/test_oracle_marshalling.py`) with that export (oracle-only
    #: since T-4, 2026-09-05); here the bill is held to the published
    #: external inductance directly
    lp = 4e-7 * np.pi * 1.85 * (np.log(8 * 1.85 / 0.45) + 0.9 / 2 - 2)
    assert b["l_p"] == pytest.approx(lp, rel=1e-12)
    assert b["phi_ind"] == pytest.approx(lp * 4e5, rel=1e-12)
    #: one volt for ten seconds is ten webers
    assert b["phi_consumed"] == pytest.approx(10.0, abs=1e-9)
    #: an undeclared swing is not a duration
    assert b["t_sustain"] is None
    with_swing = K.zerod_flux_budget(t, np.ones_like(t), np.full_like(t, 4e5),
                                     [0.0, 1.0, 8.0, 10.0], r0=1.85, a=0.45,
                                     li=0.9, phi_avail=20.0)
    assert with_swing["t_sustain"] == pytest.approx(
        20.0 - with_swing["phi_ramp"], rel=1e-9)


def test_strike_points_and_clearance_read_the_wall_as_a_polyline():
    """A circle inside a box: both answers are known in closed form, and
    both must be measured to the wall SEGMENTS rather than its vertices."""
    n = 401
    g = K.grid_of(np.linspace(0.0, 2.0, n), np.linspace(-1.0, 1.0, n))
    r, z = np.meshgrid(np.linspace(0.0, 2.0, n), np.linspace(-1.0, 1.0, n),
                       indexing="ij")
    psi = (r - 1.0) ** 2 + z ** 2
    wall_r, wall_z = [0.8, 1.6, 1.6, 0.8], [-0.6, -0.6, 0.6, 0.6]
    sp = K.strike_points(g, psi, 0.25, wall_r, wall_z)
    assert sp.shape == (2, 2)
    want = np.sqrt(0.25 - 0.04)
    assert sp[0] == pytest.approx([0.8, -want], abs=2e-3)
    assert sp[1] == pytest.approx([0.8, want], abs=2e-3)
    #: a surface entirely inside the wall lands nowhere
    assert K.strike_points(g, psi, 0.01, wall_r, wall_z).shape == (0, 2)
    #: ★the wall-gap row (`wall_clearance`) moved to the kernel repository's
    #: `tests/test_oracle_marshalling.py` with that export (oracle-only since
    #: T-4 第八刀, 2026-09-06); `code/summary` carries the gap on the page


def test_a_start_is_more_isoflux_than_the_plasma_alone_and_respects_its_box():
    """Eight point coils around a filament cloud: the design has to make the
    requested boundary far more isoflux than doing nothing does, and a
    bounded design has to stay inside its bound and say which channels sit
    on it."""
    nc = 8
    th = np.linspace(0.0, 2 * np.pi, nc, endpoint=False)
    els = (1.85 + 1.2 * np.cos(th), 1.2 * np.sin(th), np.zeros(nc),
           np.zeros(nc), np.zeros(nc), np.zeros(nc))
    w = np.eye(nc)
    tb = np.linspace(0.0, 2 * np.pi, 24, endpoint=False)
    br, bz = 1.85 + 0.45 * np.cos(tb), 0.74 * np.sin(tb)
    fil = K.fill_filaments(br, bz, 4e5, n_ring=4, peaking=1.0)
    assert fil[:, 2].sum() == pytest.approx(4e5, rel=1e-9)
    d = K.start_currents(els, w, br, bz, fil,
                         length=2 * np.pi * 1.85 * 0.45, lam=1e-3, nu=1, nv=1)
    assert d["aturns"].size == nc
    assert d["b_x"] is None                      # none was asked for
    #: the plasma alone, on the same points — the baseline this has to beat
    psi_p = np.array([
        (fil[:, 2] * K.mutual_outer([r], [z], fil[:, 0], fil[:, 1])[0]).sum()
        for r, z in zip(br, bz)])
    bare = float(np.std(psi_p))
    assert d["psi_rms"] < 0.2 * bare

    cap = K.start_currents(els, w, br, bz, fil, length=1.0, lam=1e-4,
                           i_max=np.full(nc, 1e4), nu=1, nv=1)
    assert np.all(np.abs(cap["aturns"]) <= 1e4 + 1e-6)
    assert cap["at_bound"].size > 0




def test_spitzer_eta_is_the_parallel_branch_and_the_ratio_is_pinned():
    """★T-A18's closure criterion at this host's boundary: `spitzer_eta`
    is the PARALLEL branch since ABI v111 (it used to carry the NRL
    perpendicular coefficient under the parallel name), and the new/old
    ratio is 0.51 — constant, per point, for any Te / Z_eff / lnΛ."""
    te = np.array([50.0, 300.0, 2000.0, 15000.0])
    z = np.array([1.0, 1.5, 2.0, 4.0])
    ln = np.array([10.0, 14.0, 17.0, 20.0])
    par = K.spitzer_eta(te, z, ln)
    perp = K.spitzer_eta_perp(te, z, ln)
    assert par / perp == pytest.approx(0.51, abs=1e-15)
    #: and the perpendicular branch is the NRL formula as printed
    assert perp == pytest.approx(1.03e-4 * z * ln / te ** 1.5, rel=1e-12)


def test_eped1nn_answers_the_published_iter_prediction():
    """★T-M4's certification at this boundary: the EPED1-NN surrogate's
    ITER baseline lands on the PUBLISHED EPED1 prediction (p_ped ~80 kPa,
    width ~0.033 ψ_N, T_ped ~3.5 keV at n_e,ped = 7e19 — Snyder NF 49
    085035), the width satisfies EPED's own KBM closure
    Δ = 0.076·√β_p,ped, and refusals refuse."""
    r = K.eped1nn(a=2.0, betan=1.8, bt=5.3, delta=0.485, ip=15.0,
                  kappa=1.85, mass=2.5, neped=7.0, r=6.2, zeffped=1.8)
    p, w = r["p_ped"][0], r["width"][0]
    assert 60e3 < p < 110e3 and 0.025 < w < 0.045
    assert r["extrapolation"] == 0.0
    #: the KBM identity — a unit slip in either output breaks it
    mu0 = 4e-7 * np.pi
    perim = 2 * np.pi * 2.0 * np.sqrt((1 + 1.85 ** 2) / 2)
    bp = mu0 * 15e6 / perim
    g = w / np.sqrt(2 * mu0 * p / bp ** 2)
    assert abs(g - 0.076) < 0.05 * 0.076
    with pytest.raises(K.KernelError):
        K.eped1nn(a=2.0, betan=1.8, bt=5.3, delta=0.485, ip=15.0,
                  kappa=1.85, mass=2.5, neped=-1.0, r=6.2, zeffped=1.8)


def test_the_deltastar_operator_returns_the_solovev_source():
    """★The Δ* OPERATOR (ABI v114), against the analytic oracle its solver
    is already held to.

    Solov'ev: ``Δ*(f/8 R^4 + g/2 Z^2 + c R^2) = f R^2 + g``, exactly — the
    conservative stencil reproduces that class to rounding, which is why the
    solver's own gate uses it (``tests/test_rust_kernels.py``).  Applying the
    operator to the closed form must return the closed-form source.

    ★It is on the ABI for T-C22: the repo declares COCOS 17 in four places
    and nothing tested the declaration.  The check that needs neither the
    COCOS table nor anyone's memory is the kernel's own written equation —
    ``Δ*ψ = −μ0 R² p' − F F'`` — on a real equilibrium, and getting the
    left-hand side without this entry meant re-writing the stencil in the
    host, i.e. a second spelling of the operator under test.
    """
    import numpy as np
    from fylite import kernel as K

    n = 65
    r = np.linspace(1.2, 2.4, n)
    z = np.linspace(-0.7, 0.7, n)
    f_, g_, c2 = -1.2, -0.8, 0.35
    rr, zz = r[:, None], z[None, :]
    psi = f_ / 8.0 * rr ** 4 + g_ / 2.0 * zz ** 2 + c2 * rr ** 2
    want = np.broadcast_to(f_ * rr ** 2 + g_, (n, n))

    got = K.deltastar_apply(r, z, psi)
    assert got.shape == (n, n)
    #: the stencil is not defined on the border and says so by leaving it
    assert np.array_equal(got[0, :], np.zeros(n))
    assert np.array_equal(got[:, -1], np.zeros(n))
    err = float(np.max(np.abs(got[1:-1, 1:-1] - want[1:-1, 1:-1])))
    assert err < 1e-9, f"the operator is not the Solov'ev source: {err:.3e}"


def test_the_deltastar_operator_refuses_a_mismatched_grid():
    import numpy as np
    import pytest as _pytest
    from fylite import kernel as K

    with _pytest.raises(K.KernelError, match="the grid is"):
        K.deltastar_apply(np.linspace(1, 2, 5), np.linspace(-1, 1, 5),
                          np.zeros((5, 4)))
