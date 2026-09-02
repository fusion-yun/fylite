"""The device / g-file geometry tier of ``evolve_heat`` (S-2c 批四).

★★What is claimed here is NOT that a march is right — it is that the tier
hands the entry the SAME plasma the equilibrium describes.  Two readings
carry that, and both are deliberately **non-self-consistent**: the g-file
states its own plasma current and its own q, neither of which takes part in
anything this repository computes.

★★★The reason that distinction is load-bearing.  Batch 二's round-trip gate
seeded ψ by inverting ``solve_psi``'s own q relation and then checked q with
that same relation — so it passed, and it would have passed in ANY gauge.
**Invert a relation and check it with the same relation and you always
agree.**  When this tier first ran, its q came out 2π above the
equilibrium's, and no self-consistent gate could have seen it (the repo
settled it: COCOS 17, ψ is full-turn Wb, which ``model/assembly.py`` already
stated for this channel; the ladder carries Wb/rad, so the tier converts).
These two gates are the ones that would have caught it.

Set ``FYDATA_DIR`` to a fydata checkout; without one they skip.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from fylite import kernel as K
from fylite._paths import KERNEL_LIB

pytestmark = pytest.mark.skipif(not KERNEL_LIB.exists(),
                                reason="libfylite_kernel.so not built (rust/build.sh)")

FYDATA_ENV = "FYDATA_DIR"
MU0 = 4.0e-7 * np.pi

#: the ITER 15 MA inductive-burn equilibrium the benchmark case waits for.
#: ★The LOW resolution one on purpose: it is the coarsest of the five, so a
#: claim that holds here is not resting on a fine grid.
_ITER = ("data/15MA inductive - burn/Standard domain R-Z/"
         "Low resolution - 65x129/g900003.00230_ITER_15MA_eqdsk16LR.txt")


def _iter_gfile():
    root = os.environ.get(FYDATA_ENV)
    if not root:
        pytest.skip(f"set ${FYDATA_ENV} to a fydata checkout — the device "
                    "and experimental decks stay out of this repository")
    q = Path(root) / _ITER
    if not q.is_file():
        pytest.skip(f"{q} is not in this fydata checkout")
    return q


def _march(gfile, **over):
    from fylite.scenario import model as M

    kw = dict(equilibrium=str(gfile), a=0.0, r0=0.0, b0=0.0,
              te_axis=20e3, ti_axis=18e3, ne_axis=1.0e20,
              edge_te=300.0, edge_ti=300.0, edge_ne=3.0e19,
              n_steps=2, dt=1e-9, chi0=0.6, p_e=2e6, p_i=2e6, ip=15e6,
              current=True)
    kw.update(over)
    return M.evolve(**kw)


def test_the_tier_reports_the_q_the_equilibrium_itself_has():
    """★The entry's q, off the flux it marched, against the q the kernel
    traced from the same map — two different computations of one number.

    ★★This is the gate the 2π would have failed.  It is not a tolerance on
    a residual: the two q profiles are produced by different code from
    different inputs, so agreement is a statement and a factor of 2π is not
    something either side can absorb.
    """
    from fylite import fyo as F

    g = _iter_gfile()
    lad = F.Ladder(str(g))
    out = _march(g)
    q = np.asarray(out["q"])
    traced = np.abs(np.asarray(lad.q))
    #: the entry's grid has the prepended axis node; compare where both have
    #: a traced surface
    assert q.size == traced.size + 1
    rel = np.abs(q[1:] - traced) / traced
    assert rel.max() < 0.05, (
        f"worst {rel.max():.3f} at index {int(rel.argmax())}: the entry "
        f"reports q = {q[1:][rel.argmax()]:.4g} where the traced ladder has "
        f"{traced[rel.argmax()]:.4g}.  A factor near 2 pi (6.28) means the "
        "psi gauge is wrong — COCOS 17 is full-turn Wb and the ladder "
        "carries Wb/rad")
    #: and the AXIS, which is where a sawtooth trigger reads.  This
    #: equilibrium is at q(0) ~ 1.02, i.e. just above the trigger — so the
    #: gauge is not a detail here, it decides whether it crashes.
    assert 0.9 < q[0] < 1.2, q[0]


def test_the_marched_flux_carries_the_current_the_file_states():
    """★★The reading no seed can satisfy by construction.

    ``I(rho) = V' <|grad rho|^2/R^2> (dpsi/drho) / (4 pi^2 mu0)`` for
    full-turn psi (COCOS 17) — the constant read off the kernel's own
    operator, not fitted.  The g-file states its own ``current`` in its
    header, and nothing in this repository put it there.

    ★It reads **0.926** of it, and that is REPORTED rather than tightened
    away: the ladder stops at psi_N = 0.95, so the current between that
    surface and the separatrix is outside the sum.  The band below is wide
    enough to admit that truncation and far too narrow to admit a 2 pi, a
    1/2 pi, or a 4 pi^2 — which is the whole point of the check.
    """
    from fylite import fyo as F
    from fylite.io import geqdsk

    g = _iter_gfile()
    stated = abs(float(geqdsk.read_geqdsk(str(g))["current"]))
    lad = F.Ladder(str(g))
    out = _march(g)
    rho = np.asarray(out["rho"])
    psi = np.asarray(out["psi"])
    vprime = np.asarray(out["vprime"])
    gm2 = np.concatenate([[lad.gm2[0]], np.asarray(lad.gm2)])
    d = np.gradient(psi, rho)
    i_edge = float((vprime * gm2 * d / (4.0 * np.pi ** 2 * MU0))[-1])
    ratio = i_edge / stated
    assert 0.85 < ratio < 1.05, (
        f"the marched flux carries {i_edge:.4g} A where the file states "
        f"{stated:.4g} A (ratio {ratio:.4f}).  Near 6.28 or 0.159 is the "
        "psi gauge; near 0.93 is the ladder's psi_N = 0.95 truncation and "
        "is expected")
    #: ★and it must be UNDER: the ladder cannot carry current it never
    #: enclosed.  Over-unity would mean the sum is not what it says it is.
    assert ratio < 1.0


def test_the_axis_flux_is_the_equilibriums_own_and_not_a_repeated_surface():
    """★Every other column repeats the innermost traced value at the
    prepended axis node — a flux-surface average has none on a degenerate
    surface.  ``psi`` does not: the axis flux is a number the equilibrium
    states.

    ★★Repeating it makes ``psi[0] == psi[1]``, and the Redl closure
    differentiates WITH RESPECT TO psi — ``gradient(p_th, psi)`` then divides
    by zero and the entire march comes back NaN on the FIRST step.  That is
    how this was found, and it is pinned here so it cannot come back as a
    tidy-looking `head(psi)`.
    """
    from fylite import fyo as F

    g = _iter_gfile()
    lad = F.Ladder(str(g))
    out = _march(g, bootstrap=True)
    psi = np.asarray(out["psi"])
    assert psi[0] != psi[1], "the axis node repeats psi[1]"
    #: it is the deck's psi_axis, in full-turn Wb
    want = float(F.psi_range_of(lad.eq)[0]) * 2.0 * np.pi
    assert psi[0] == pytest.approx(want, rel=1e-9)
    #: and with the bootstrap ON — the closure that divides by it — nothing
    #: is NaN
    for key in ("te", "ti", "psi", "q", "j_bs"):
        v = np.asarray(out[key])
        assert np.all(np.isfinite(v)), f"{key} is not finite: {v[:5]}"


def test_the_traced_tier_states_one_field_orientation():
    """★The ITER deck has ``B0 < 0``, and until this tier no caller had ever
    handed the entry a negative ``F = R B_tor``.

    The psi channel is already solved in a positive-B0 orientation
    (``solve_psi`` takes ``b0.abs()``, and the Redl closure is handed
    ``b0.abs()``), so a signed F would put two field orientations inside one
    closure.  The prescribed tier has always supplied ``r0 * abs(b0)``; this
    asserts the traced tier says the same thing rather than a different one.
    """
    from fylite import fyo as F

    g = _iter_gfile()
    lad = F.Ladder(str(g))
    assert float(F.field_of(lad.eq)[1]) < 0.0, (
        "this gate's premise is a reversed-field deck; the corpus changed")
    out = _march(g, bootstrap=True, ohmic=True)
    j = np.asarray(out["j_bs"])
    assert np.all(np.isfinite(j))
    #: the bootstrap is a real current, not a rounding artifact, and it is
    #: zero on axis by construction (no trapped fraction there)
    assert float(j[0]) == 0.0
    assert np.max(np.abs(j)) > 1e3, f"no bootstrap current at all: {j.max()}"


def test_the_prescribed_tier_cannot_sawtooth_and_the_traced_one_can_be_asked():
    """★Why the two tiers are not interchangeable, in one assertion.

    The prescribed tier builds ``q = 1 + (q95 - 1) x^2``, so ``q(0) = 1``
    exactly and the core can never fall through it — in BOTH hosts.  A
    traced ladder states whatever q the equilibrium has.  This ITER slice
    sits at ``q(0) ~ 1.02``, just ABOVE the trigger, so it correctly does
    NOT crash — and「没有触发」is recorded rather than silent.
    """
    g = _iter_gfile()
    out = _march(g, bootstrap=True, sawtooth=True, saw_mix=1.2, n_steps=4,
                 dt=1e-3)
    assert int(out["saw_count"]) == 0
    assert not np.any(np.asarray(out["saw_r1"])), \
        "a q(0) ~ 1.02 core reported a q = 1 surface"
    assert float(np.asarray(out["q"])[0]) > 1.0


# --- S-2c 批五: the driven current and the reference start ------------------

def test_the_prescribed_driven_current_carries_the_amperes_it_was_given():
    """★A prescribed profile's ONE claim: the current it integrates to is
    the current that was asked for.

    ``I_CD`` is a Gaussian in rho normalised on the AREA element
    ``dA/drho = V'/(2 pi R0)`` — exact on a circular surface and an
    approximation on this one, which is the honest description of a
    prescribed shape rather than a deposition model.  So the integral is
    the assertion, and the shape is only asserted to sit where it was told.
    """
    from fylite.scenario import model as M

    kw = dict(a=0.45, r0=1.85, b0=2.0, q95=4.0, kappa=1.7, delta=0.4,
              n_rho=81, te_axis=3000.0, ti_axis=2800.0, ne_axis=4e19,
              edge_te=100.0, edge_ti=100.0, edge_ne=5e18, ip=1e6,
              n_steps=2, dt=1e-9, current=True)
    want = 200e3
    out = M.evolve(i_cd=want, cd_centre=0.4, cd_width=0.2, **kw)
    rho = np.asarray(out["rho"])
    j = np.asarray(out["j_cd"])
    area = np.asarray(out["vprime"]) / (2.0 * np.pi * 1.85)
    got = float(np.trapezoid(j * area, rho))
    assert got == pytest.approx(want, rel=1e-9), (
        f"the driven current integrates to {got:.6g} A where {want:.6g} A "
        "was asked for — the normaliser is the area element, not the volume")
    assert rho[int(np.argmax(j))] / 0.45 == pytest.approx(0.4, abs=0.02)
    #: ★and it is reported APART from the bootstrap: which term put this
    #: current here is the question the channel is carried for
    assert "j_cd" in out and "j_bs" in out
    assert out["provenance"]["driven_current"] == pytest.approx(want)

    off = M.evolve(**kw)
    assert np.all(np.asarray(off["j_cd"]) == 0.0)
    assert off["provenance"]["driven_current"] is None
    #: a drive with no channel to drive is refused, by name, like the others
    with pytest.raises(ValueError, match="driven current"):
        M.evolve(i_cd=want, **dict(kw, current=False))


def test_the_reference_start_takes_the_tables_own_numbers():
    """★★「从参考剖面起步」 is a claim about WHICH profiles, so the run
    records which channels the table actually supplied.

    The march then starts on the published values and the readings measure
    how far this transport model drifts from them — the reproduction test
    itself, and not a fit.
    """
    from fylite.io.reference import read_reference
    from fylite.scenario import model as M

    root = os.environ.get(FYDATA_ENV)
    if not root:
        pytest.skip(f"set ${FYDATA_ENV} to a fydata checkout")
    csv = Path(root) / "data" / "15MA Inductive at burn-ASTRA.csv"
    if not csv.is_file():
        pytest.skip(f"{csv} is not in this fydata checkout")
    ref = read_reference(csv)
    g = _iter_gfile()

    plain = _march(g)
    started = _march(g, reference=ref)
    assert started["provenance"]["reference_channels"] == ("te", "ti", "ne")
    assert plain["provenance"]["reference_channels"] == ()

    #: the axis value IS the table's, not the control's
    axis = float(np.asarray(started["te_init"])[0])
    assert axis == pytest.approx(float(ref["te"][0]), rel=1e-9), (
        f"started at {axis:.6g} eV where the table's axis is "
        f"{ref['te'][0]:.6g} eV")
    #: and it is a different discharge from the shape-control one
    assert not np.allclose(np.asarray(started["te_init"]),
                           np.asarray(plain["te_init"]))


def test_a_reference_that_states_no_ion_temperature_leaves_ti_alone():
    """★★Per CHANNEL, and this is why.  A table carrying Te and nothing else
    must not hand back a plasma with ``T_i = T_e`` that nobody measured —
    the browser's own rule, in its own words: 「a reference with no ion
    temperature leaves T_i where the controls put it rather than silently
    making it the electron one」.
    """
    from fylite.scenario import model as M

    rho = np.linspace(0.0, 2.0, 9)
    partial = {"name": "te-only", "rho": rho,
               "te": np.linspace(9000.0, 400.0, 9),
               "ti": np.full(9, np.nan), "ne": np.full(9, np.nan),
               "q": np.full(9, np.nan), "x_norm": False}
    g = _iter_gfile()
    plain = _march(g)
    started = _march(g, reference=partial)
    assert started["provenance"]["reference_channels"] == ("te",)
    assert not np.allclose(np.asarray(started["te_init"]),
                           np.asarray(plain["te_init"]))
    #: T_i and n_e are exactly where the controls put them — bit for bit,
    #: because nothing touched them
    for key in ("ti_init", "ne"):
        assert np.array_equal(np.asarray(started[key]),
                              np.asarray(plain[key])), key
    #: and a table that states NOTHING is refused rather than quietly
    #: starting on the controls under the reference's name
    empty = dict(partial, te=np.full(9, np.nan))
    with pytest.raises(ValueError, match="none of"):
        _march(g, reference=empty)
