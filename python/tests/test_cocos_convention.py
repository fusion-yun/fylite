"""T-C22 〔一〕 — the sign and gauge conventions, asserted rather than declared.

★★Why this file exists.  The repo declares **COCOS 17** (IMAS v4's
convention, and the 2026-08-26 ruling's yardstick) in four places, and until
now nothing tested that the declaration held — which is the same position
upstream is in with "three conventions and a comment that lies", and has the
same consequence the moment data is exchanged.

What is asserted here, and what each assertion is worth:

* **the equation, not the label.**  The check that needs neither the COCOS
  table nor anybody's memory is the kernel's own written equation —
  ``Δ*ψ = −μ0 R² p' − F F'`` — evaluated on real fields.  A convention error
  (a flipped sign, ψ per radian where full flux was meant, a missing 2π)
  breaks it by a factor, loudly.  ``deltastar_apply`` is on the ABI (v114)
  precisely so this side can ask for the left-hand side instead of
  re-writing the stencil, i.e. instead of spelling the operator under test a
  second time.
* **the directions**, one by one, on two known configurations: the sign of
  I_p and B_0, whether ψ rises or falls outward, the sign and slope of q.
* **the orientation trap**: ``geqdsk.grid()`` hands back a ψ the kernel's
  row-major ``[i*nz + j]`` convention needs TRANSPOSED, and every caller
  carries that ``.T`` itself.  Measured while writing this file: forgetting
  it turns the GS identity from 8e-5 into 0.44 — right magnitude near the
  axis, wrong shape outward, the ratio drifting and finally changing sign.
  That is a trap with no error message, so it gets an assertion.

★What is NOT claimed: that the label "COCOS 17" is derivable from these
numbers.  Deriving an index needs the table, and the repo's rule is that a
constant nobody can check is not written from memory.  What these gates give
is the thing the label is FOR — that the signs and the gauge are one set and
do not move.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fylite import kernel as K
from fylite.io.geqdsk import read_geqdsk, grid

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC = ROOT / "tests/data/FYDOC-CASE-12-synthetic/g_synthetic.geqdsk"
MU0 = 4e-7 * np.pi


def _solve_one():
    """A fixed-boundary equilibrium solved HERE, from monomial p'/FF' in
    psibar — nothing read, nothing round-tripped through a file."""
    lib = K.load()
    n = 65
    r = np.ascontiguousarray(np.linspace(1.2, 2.4, n))
    z = np.ascontiguousarray(np.linspace(-0.8, 0.8, n))
    psi = np.full((n, n), -0.1)
    psi[0, :] = psi[-1, :] = psi[:, 0] = psi[:, -1] = 0.0
    psi = np.ascontiguousarray(psi)
    pp = np.ascontiguousarray([-8.0e3, 8.0e3])
    ffp = np.ascontiguousarray([-0.6, 0.6])
    out5 = np.empty(5)
    it = lib.fylite_rs_gs_fixed_solve(r, n, z, n, psi, 0.0, pp, pp.size,
                                      ffp, ffp.size, 0.5, 800, 1e-11, out5)
    assert it > 0, f"the fixed-boundary solve failed (rc={it})"
    return r, z, psi, pp, ffp, out5


def test_the_written_gs_equation_holds_on_a_solved_equilibrium():
    """★★The convention check that needs no table: the kernel's own equation,
    on a field the kernel just produced.

    ``Δ*ψ = −(μ0 R² dp/dψ + d(F²/2)/dψ)``, with the profiles as this entry
    takes them.  Measured 1.0e-11 when this landed — it is an identity of the
    discretisation, so anything but machine noise is a convention error.
    """
    r, z, psi, pp, ffp, out5 = _solve_one()
    psi_axis = float(out5[0])
    #: this entry's psi is per radian, zero on the boundary, negative on
    #: axis — so psibar rises from 0 at the axis to 1 at the boundary
    assert psi_axis < 0.0
    span = 0.0 - psi_axis
    psibar = (psi - psi_axis) / span

    lhs = K.deltastar_apply(r, z, psi)
    ppv = np.polyval(pp[::-1], np.clip(psibar, 0.0, 1.0))
    ffpv = np.polyval(ffp[::-1], np.clip(psibar, 0.0, 1.0))
    R = r[:, None] * np.ones((1, len(z)))
    rhs = -(MU0 * R ** 2 * ppv + ffpv)

    interior = np.zeros(psi.shape, bool)
    interior[2:-2, 2:-2] = True
    sel = interior & (psibar > 0.05) & (psibar < 0.9)
    assert sel.sum() > 500
    rel = float(np.max(np.abs(lhs[sel] - rhs[sel]))
                / np.max(np.abs(rhs[sel])))
    assert rel < 1e-8, (
        f"the solved field does not satisfy the equation the kernel writes: "
        f"{rel:.3e} (measured 1.0e-11).  A sign, a gauge or a 2π has moved.")

    #: ★and the two ways to get it WRONG must be loudly wrong — otherwise
    #: the check above would pass on a convention it cannot distinguish
    for name, bad in (("psi per radian vs full flux (2π)", 2 * np.pi),
                      ("a flipped poloidal-flux sign", -1.0)):
        off = float(np.max(np.abs(lhs[sel] * bad - rhs[sel]))
                    / np.max(np.abs(rhs[sel])))
        assert off > 0.5, f"the identity cannot tell {name} apart: {off:.2e}"


def test_the_shipped_equilibrium_satisfies_the_same_equation():
    """The same identity, on the g-file the whole suite is anchored on —
    so the WRITER's convention is checked, not only the solver's.

    ★The profiles a GEQDSK carries here are the solve's own ``dp/dψbar``
    resampled onto the file's normalised flux, and the file's ``sibry`` is
    the ψ of ψbar = 0.99 (the boundary it actually draws), so the lookup
    goes through that factor.  Measured 8.0e-5 — the floor is the file's
    own ~9 significant digits, not the physics.
    """
    if not SYNTHETIC.exists():
        pytest.skip("the synthetic fixture is not in this checkout")
    g = read_geqdsk(SYNTHETIC)
    r, z, psi_read = grid(g)
    #: ★TRANSPOSED — see the module docstring: `grid()` hands back the
    #: orientation the plotting side wants and every kernel caller carries
    #: this `.T` (`fylite/plot.py` does).  Without it this identity reads
    #: 0.44 instead of 8e-5, with no error anywhere.
    psi = np.ascontiguousarray(np.asarray(psi_read, float).T)

    sim = float(g["simag"])
    span_solve = 0.0 - sim
    psibar = (psi - sim) / span_solve
    x_lcfs = (float(g["sibry"]) - sim) / span_solve
    n_tab = len(g["pprime"])
    xtab = np.linspace(0.0, 1.0, n_tab)
    look = psibar / x_lcfs
    pp = np.interp(look, xtab, np.asarray(g["pprime"], float))
    ffp = np.interp(look, xtab, np.asarray(g["ffprim"], float))
    R = r[:, None] * np.ones((1, len(z)))
    lhs = K.deltastar_apply(r, z, psi)
    rhs = -(MU0 * R ** 2 * pp + ffp)

    interior = np.zeros(psi.shape, bool)
    interior[2:-2, 2:-2] = True
    sel = interior & (psibar > 0.1) & (psibar < 0.8)
    assert sel.sum() > 500
    rel = float(np.max(np.abs(lhs[sel] - rhs[sel]))
                / np.max(np.abs(rhs[sel])))
    assert rel < 1e-3, (
        f"the shipped equilibrium does not satisfy the kernel's own "
        f"equation: {rel:.3e} (measured 8.0e-5)")


def test_the_geqdsk_grid_orientation_is_the_transposed_one():
    """★The trap, asserted so the next reader meets an assertion instead of
    a 44 % discrepancy with no error message.

    ``grid()``'s ψ needs ``.T`` before it reaches a kernel entry, and the
    difference is not subtle once measured: with the transpose the GS
    identity closes to 8e-5, without it to 0.44.
    """
    if not SYNTHETIC.exists():
        pytest.skip("the synthetic fixture is not in this checkout")
    g = read_geqdsk(SYNTHETIC)
    r, z, psi_read = grid(g)
    p = np.asarray(psi_read, float)
    #: the fixture is square, so a shape check cannot catch it — the
    #: statement has to be about VALUES
    assert p.shape == (len(r), len(z))
    ok = np.ascontiguousarray(p.T)

    def identity(field):
        sim = float(g["simag"])
        span = 0.0 - sim
        pb = (field - sim) / span
        x_lcfs = (float(g["sibry"]) - sim) / span
        xtab = np.linspace(0.0, 1.0, len(g["pprime"]))
        pp = np.interp(pb / x_lcfs, xtab, np.asarray(g["pprime"], float))
        ffp = np.interp(pb / x_lcfs, xtab, np.asarray(g["ffprim"], float))
        R = r[:, None] * np.ones((1, len(z)))
        lhs = K.deltastar_apply(r, z, np.ascontiguousarray(field))
        rhs = -(MU0 * R ** 2 * pp + ffp)
        m = np.zeros(field.shape, bool)
        m[2:-2, 2:-2] = True
        sel = m & (pb > 0.1) & (pb < 0.8)
        return float(np.max(np.abs(lhs[sel] - rhs[sel]))
                     / np.max(np.abs(rhs[sel])))

    assert identity(ok) < 1e-3
    assert identity(p) > 0.1, (
        "the untransposed field now satisfies the equation too — either "
        "`grid()` changed orientation (update every kernel call site with "
        "it) or the fixture became symmetric enough to hide the difference")


@pytest.mark.parametrize("which", ["synthetic", "east"])
def test_the_direction_of_every_signed_quantity(which):
    """T-C22 〔一〕 verbatim: I_p, B_0, q, ψ and the gradient's direction,
    asserted on known configurations rather than described.

    ★Both are the same set, and that is the claim: one convention, two very
    different sources — an equilibrium this repo solved and a measured EAST
    reconstruction it read.
    """
    if which == "synthetic":
        if not SYNTHETIC.exists():
            pytest.skip("the synthetic fixture is not in this checkout")
        g = read_geqdsk(SYNTHETIC)
        ip, b0 = float(g["current"]), float(g["bcentr"])
        psi_axis, psi_bnd = float(g["simag"]), float(g["sibry"])
        q = np.asarray(g["qpsi"], float)
        f = np.asarray(g["fpol"], float)
        p = np.asarray(g["pres"], float)
    else:
        import json
        path = ROOT / "machine_desc/east/equilibrium_east137985_4000ms.fyo.jsonld"
        if not path.exists():
            pytest.skip("the EAST reference is not in this checkout")
        doc = json.loads(path.read_text())
        ts = doc["time_slice"][0]
        gq, p1 = ts["global_quantities"], ts["profiles_1d"]
        ip = float(gq["ip"])
        b0 = float(doc["vacuum_toroidal_field"]["b0"])
        psi_axis, psi_bnd = float(gq["psi_axis"]), float(gq["psi_boundary"])
        q = np.asarray(p1["q"], float)
        f = np.asarray(p1["f"], float)
        p = np.asarray(p1["pressure"], float)

    #: measured 2026-08-26; every one of these is a convention statement and
    #: a flip in any of them is a data-exchange defect, not a style change
    assert ip > 0, "I_p is positive in both shipped configurations"
    assert b0 > 0, "B_0 is positive in both"
    assert psi_bnd > psi_axis, (
        "ψ RISES from axis to boundary here — the axis is the MINIMUM.  "
        "★This is the g-file / IDS gauge; the browser's session documents "
        "carry the other one and SAY so in the document "
        "(`fylite:psi_convention: full_flux_Wb_axis_max`).  Two gauges, each "
        "declared, is the situation T-C22 〔二〕/〔三〕 is about — one gauge "
        "silently assumed is what it forbids.")
    assert q[0] > 0 and q[-1] > q[0], "q is positive and rises outward"
    assert f[0] > 0 and f[-1] < f[0], "F is positive and falls outward"
    assert p[0] > 0 and p[-1] < p[0], "pressure falls outward"


# --------------------------------------------------------------------------- #
# T-C22 〔二〕 — the reader measures the convention instead of assuming one
# --------------------------------------------------------------------------- #
def _fixture():
    if not SYNTHETIC.exists():
        pytest.skip("the synthetic fixture is not in this checkout")
    return read_geqdsk(SYNTHETIC)


def test_the_convention_is_measured_and_wins_by_a_margin():
    """★★A GEQDSK carries no convention field, so the only honest source is
    the file's own numbers: whichever candidate makes the kernel's equation
    close is the one the writer used.

    ★The MARGIN is asserted, not just the winner.  A measurement whose
    runner-up is nearly as good has not measured anything — it has picked
    the least bad of four guesses.  Here the margin is ~10^4.
    """
    from fylite.io.geqdsk import measure_cocos

    rec = measure_cocos(_fixture())
    assert rec["profile_gauge"] == "dpsi, per radian", rec
    assert rec["residual"] < 1e-3, rec
    runner, worse = rec["runner_up"]
    assert worse > 100 * rec["residual"], (
        f"the winner {rec['profile_gauge']!r} ({rec['residual']:.2e}) barely "
        f"beat {runner!r} ({worse:.2e}) — that is a guess, not a measurement")


def test_the_measurement_follows_the_file_rather_than_the_reader():
    """★★The gate that makes the one above mean something: put the SAME
    equilibrium into the other gauge and the answer must change.

    A measurement that always says "per radian" would pass every assertion
    above while measuring nothing at all.  Scaling ψ (and its two header
    levels) by 2π turns the file into total flux [Wb]; the reader must say
    so, on the file's numbers alone.
    """
    from fylite.io.geqdsk import measure_cocos

    g = dict(_fixture())
    two_pi = 2.0 * np.pi
    g["psirz"] = [v * two_pi for v in g["psirz"]]
    g["simag"] = g["simag"] * two_pi
    g["sibry"] = g["sibry"] * two_pi
    rec = measure_cocos(g)
    assert rec["profile_gauge"] == "dpsi, total flux [Wb]", rec
    assert rec["residual"] < 1e-3, rec


def test_a_file_that_satisfies_nothing_is_refused_not_rounded():
    """★No candidate closing means the answer is ``None`` WITH the residuals,
    never the nearest one: a convention picked by「least bad」is a convention
    nobody measured.

    ★The perturbation is a per-row SCRAMBLE of ``pprime``, not a scale.  A
    scale is the wrong instrument here and measuring said so (below): it
    degrades the fit without touching which candidate wins, because the
    candidates differ by 2*pi and by the span and a factor of 1.7 looks like
    neither.  A scramble leaves no single factor that works — margin 1.27.
    """
    from fylite.io.geqdsk import measure_cocos

    g = dict(_fixture())
    rng = np.random.default_rng(0)
    g["pprime"] = list(np.asarray(g["pprime"], float)
                       * (1.0 + 2.0 * rng.standard_normal(len(g["pprime"]))))
    rec = measure_cocos(g)
    assert rec["profile_gauge"] is None
    assert rec["residual"] is None
    assert "no candidate convention" in rec["note"]
    assert rec["runner_up"] is not None, "the closest miss must still be said"
    assert rec["margin"] < 3.0, rec["margin"]


def test_a_big_margin_on_a_nonsense_file_is_still_refused():
    """★★What the residual bound is FOR, and the proof it is load-bearing.

    The decision rests on the margin, because the margin is the scale-free
    quantity that answers「这是哪一种约定」.  But a margin can be large on a
    file that is not an equilibrium at all: add 30 % noise to psi and the
    best candidate wins by **26.7x** while its residual is **3.07** — the
    error is three times the term it is a residual of.

    1.0 is not fitted to anything: it is where the residual equals that
    term, and past it nothing has closed in any sense worth the word.
    """
    from fylite.io.geqdsk import measure_cocos

    g = dict(_fixture())
    rng = np.random.default_rng(0)
    span = abs(float(g["sibry"]) - float(g["simag"]))
    g["psirz"] = list(np.asarray(g["psirz"], float)
                      + 0.3 * span * rng.standard_normal(len(g["psirz"])))
    rec = measure_cocos(g)
    assert rec["profile_gauge"] is None, rec
    assert rec["margin"] > 10.0, rec["margin"]
    assert rec["runner_up"][1] > 1.0, rec["runner_up"]
    assert "nothing closed" in rec["note"], rec["note"]


def test_an_amplitude_error_is_not_a_convention_failure():
    """★★The distinction the whole rule is built on.

    Scaling one profile by 1.7 is a PHYSICS error — that file is not a
    solution of anything.  It is not a CONVENTION error: the candidates
    differ by 2*pi and by the span, and 1.7 looks like neither, so the
    convention is still determined (margin 4.4) and what the caller gets is
    the answer plus a residual that says the file is poor (0.18).

    This function is asked「哪一种约定」 and answers it; judging whether a
    file is a good equilibrium needs its grid and its provenance, which this
    function does not have and must not pretend to.
    """
    from fylite.io.geqdsk import measure_cocos

    g = dict(_fixture())
    g["pprime"] = [v * 1.7 for v in g["pprime"]]
    rec = measure_cocos(g)
    assert rec["profile_gauge"] == "dpsi, per radian", rec
    assert rec["margin"] > 3.0, rec["margin"]
    #: and it says the file got worse — a silent pass would be the failure
    assert rec["residual"] > 100 * measure_cocos(_fixture())["residual"]


def test_a_mismatched_convention_is_refused_by_name():
    """T-C22 〔二〕's rule: transform explicitly or refuse — never read as-is.

    ★There is deliberately NO silent transform here.  What a mismatch needs
    depends on the quantity about to be used (ψ alone scales one way, a
    ψ-derivative table the other), and guessing that is the failure being
    prevented.
    """
    from fylite.io.geqdsk import require_convention

    g = _fixture()
    rec = require_convention(g, profile_gauge="dpsi, per radian")
    assert rec["residual"] < 1e-3

    with pytest.raises(ValueError, match="dpsi, per radian"):
        require_convention(g, profile_gauge="dpsi, total flux [Wb]")


def test_a_file_with_no_profiles_says_so_rather_than_deciding():
    from fylite.io.geqdsk import measure_cocos

    g = dict(_fixture())
    g["pprime"] = []
    rec = measure_cocos(g)
    assert rec["profile_gauge"] is None
    assert "p'" in rec["note"]
    #: the direction facts do NOT need the equation and must survive
    assert rec["psi_axis"] == "minimum" and rec["sign_ip"] == 1


# --------------------------------------------------------------------------- #
# T-C22 〔三〕 — the explicit transform for exchange with another tool
# --------------------------------------------------------------------------- #
def test_every_convention_is_reachable_and_the_equation_still_closes():
    """★★A convention change is a RELABELLING, so the one thing that must not
    move is how well the file satisfies the Grad-Shafranov equation.

    All four declared conventions are produced from the shipped fixture, and
    each is re-measured: it must come back AS ITSELF, at the same residual
    the source had.  A transform that improved the residual would be as
    suspicious as one that spoiled it — it would mean the numbers changed in
    a way the equation noticed.
    """
    from fylite.io.geqdsk import CONVENTIONS, measure_cocos, to_convention

    g = _fixture()
    src = measure_cocos(g)
    for target in CONVENTIONS:
        out = to_convention(g, target)
        got = measure_cocos(out)
        assert got["profile_gauge"] == target, (target, got)
        assert abs(got["residual"] - src["residual"]) \
            < 0.01 * src["residual"], (target, got["residual"],
                                       src["residual"])


def test_the_transform_actually_moves_the_numbers():
    """★Without this, a `to_convention` that returned its input unchanged
    would pass every assertion above — the file would still measure as
    whatever it already was, at whatever residual it already had.  Each of
    the three non-identity targets must change something, and WHICH thing it
    changes is named."""
    from fylite.io.geqdsk import measure_cocos, to_convention

    g = _fixture()
    assert measure_cocos(g)["profile_gauge"] == "dpsi, per radian"
    two_pi = 2.0 * np.pi

    wb = to_convention(g, "dpsi, total flux [Wb]")
    #: the gauge moved: psi carries 2*pi, the tables do not
    assert wb["simag"] == pytest.approx(g["simag"] * two_pi, rel=1e-12)
    assert wb["pprime"][1] == pytest.approx(g["pprime"][1], rel=1e-12)

    bar = to_convention(g, "dpsibar, per radian")
    #: the abscissa moved: psi is untouched, the tables carry the span
    assert bar["simag"] == pytest.approx(g["simag"], rel=1e-12)
    assert bar["pprime"][1] != pytest.approx(g["pprime"][1], rel=1e-6)

    both = to_convention(g, "dpsibar, total flux [Wb]")
    assert both["simag"] == pytest.approx(g["simag"] * two_pi, rel=1e-12)
    assert both["pprime"][1] == pytest.approx(bar["pprime"][1], rel=1e-12)


@pytest.mark.parametrize("target", ["dpsi, total flux [Wb]",
                                    "dpsibar, per radian",
                                    "dpsibar, total flux [Wb]"])
def test_the_transform_round_trips(target):
    """★There and back must be the file that set out.  A transform that is
    right in one direction and lossy in the other is a data loss nobody sees
    until the file comes home."""
    from fylite.io.geqdsk import to_convention

    g = _fixture()
    back = to_convention(to_convention(g, target), "dpsi, per radian")
    for key in ("simag", "sibry", "rmaxis", "bcentr", "current"):
        assert back[key] == pytest.approx(g[key], rel=1e-12), key
    for key in ("pprime", "ffprim", "psirz", "qpsi", "pres", "fpol"):
        np.testing.assert_allclose(back[key], g[key], rtol=1e-12, atol=0.0,
                                   err_msg=key)


def test_a_field_nobody_classified_is_refused_not_copied():
    """★★The declaration is the point of this layer.  A g-file carrying a
    key `_RESPONSE` does not classify is carrying a quantity nobody decided
    about, and copying it through unchanged is a decision — the wrong kind,
    made silently."""
    from fylite.io.geqdsk import to_convention

    g = dict(_fixture())
    g["rotation"] = [1.0, 2.0, 3.0]
    with pytest.raises(ValueError, match="not classified"):
        to_convention(g, "dpsi, total flux [Wb]")


def test_the_self_check_is_load_bearing(monkeypatch):
    """★★The transform RE-MEASURES its own output, and this proves that check
    is doing work rather than decorating the return.

    `pprime` is misclassified as invariant — a plausible-looking edit, since
    a pressure gradient is "just a profile" — and the equation must reject
    the file that comes out.  Without the re-measurement this would ship a
    g-file that is wrong in exactly the way T-C22 exists to stop: internally
    consistent-looking, and no longer a solution of anything.
    """
    from fylite.io import geqdsk as G

    bad = dict(G._RESPONSE)
    bad["pprime"] = ("invariant", "deliberately wrong, for this test")
    monkeypatch.setattr(G, "_RESPONSE", bad)
    with pytest.raises(ValueError, match="did not produce a file|residual"):
        G.to_convention(_fixture(), "dpsibar, per radian")


def test_the_source_is_measured_and_not_taken_from_the_caller():
    """★T-C22 〔三〕's own words: 以物理量符号的实测校验为准，不采信对方自述.

    A file already in total flux is handed in.  Asking for total flux must
    be the identity; asking for per radian must scale psi DOWN.  A layer that
    believed a caller's claim, or assumed one convention as the default
    source, would move it the wrong way on one of these two.
    """
    from fylite.io.geqdsk import measure_cocos, to_convention

    wb = to_convention(_fixture(), "dpsi, total flux [Wb]")
    assert measure_cocos(wb)["profile_gauge"] == "dpsi, total flux [Wb]"

    same = to_convention(wb, "dpsi, total flux [Wb]")
    assert same["simag"] == pytest.approx(wb["simag"], rel=1e-12)

    rad = to_convention(wb, "dpsi, per radian")
    assert rad["simag"] == pytest.approx(wb["simag"] / (2.0 * np.pi),
                                        rel=1e-12)
    assert measure_cocos(rad)["profile_gauge"] == "dpsi, per radian"


# --------------------------------------------------------------------------- #
# T-C22 〔二〕 — on REAL EFIT reconstructions, not only on the analytic fixture
# --------------------------------------------------------------------------- #
#: ★★The fixture this file was built on is analytic-grade: its own writer
#: solved the equation it is checked against, so it closes at 7.5e-05 and
#: every band and mask works.  A real reconstruction is a different animal,
#: and the difference is not academic — measuring three EAST g-files
#: (2026-08-26) is what found the mask defect these gates now hold.
#:
#: The files are fydata's, not this repository's (station data is not
#: vendored — the same posture `test_device_document_vs_fydata.py` takes), so
#: this block SKIPS without a checkout:
#:
#:     FYDATA_DIR=~/workspace/fydata pytest python/tests/test_cocos_convention.py
FYDATA_ENV = "FYDATA_DIR"

#: measured 2026-08-26, inside each file's own boundary polygon.  ★The third
#: is here BECAUSE it fails: a corpus of only the files that work would say
#: nothing about whether the refusal fires on a real one.
_REAL = {
    "g080307.63000": {"gauge": "dpsi, per radian", "resid": 1.875e-02,
                      "margin_at_least": 20.0},
    "g070754.05000": {"gauge": "dpsi, per radian", "resid": 7.288e-02,
                      "margin_at_least": 8.0},
    #: EAST #63982: closest candidate 0.4636, margin 1.97 — refused
    "g063982.04800": {"gauge": None, "resid": None, "closest": 4.636e-01},
}


def _fydata_gfile(name):
    import os
    root = os.environ.get(FYDATA_ENV)
    if not root:
        pytest.skip(f"set ${FYDATA_ENV} to a fydata checkout to measure the "
                    "real EFIT reconstructions")
    q = Path(root) / "data" / name
    if not q.is_file():
        pytest.skip(f"{q} is not in this fydata checkout")
    return q


@pytest.mark.parametrize("name", sorted(_REAL))
def test_a_real_reconstruction_measures_as_it_was_measured(name):
    """★Real EFIT output, held to the numbers it actually gives.

    Two of these three close (1.9 % and 7.3 % max-norm inside their own
    boundary polygon — three orders looser than the analytic fixture, which
    is what a reconstruction costs), and the third does NOT and must be
    refused.  Keeping the failing one in the corpus is the point: a set
    containing only files that work cannot tell whether the refusal fires.
    """
    from fylite.io.geqdsk import measure_cocos, read_geqdsk

    want = _REAL[name]
    rec = measure_cocos(read_geqdsk(_fydata_gfile(name)))
    assert rec["mask"] == "inside the file's boundary polygon", rec["mask"]
    assert rec["profile_gauge"] == want["gauge"], rec
    if want["gauge"] is None:
        assert rec["residual"] is None
        assert rec["runner_up"][1] == pytest.approx(want["closest"], rel=0.02)
        assert "coin toss" in rec["note"], rec["note"]
    else:
        assert rec["residual"] == pytest.approx(want["resid"], rel=0.02), rec
        assert rec["margin"] >= want["margin_at_least"], rec["margin"]


@pytest.mark.parametrize("name", ["g080307.63000", "g070754.05000"])
def test_the_boundary_polygon_mask_is_what_makes_a_real_file_close(name):
    """★★The defect these files found, kept as a gate.

    `measure_cocos` used to select by a psi_N band alone.  On an analytic
    fixture that is harmless; on a real diverted reconstruction the band
    re-enters the private-flux region and the near SOL, where the current is
    zero while the profile lookup still returns a p'/FF' — so a minority of
    points sit far off the equation and a MAX-norm is decided by them.

    Measured: the band gives 0.43 / 0.66 while the same points' MEDIAN is
    0.006 / 0.008.  The bulk was closing all along; the statistic was
    reporting the leak.  Inside the polygon the max is 0.019 / 0.073, so the
    two masks differ by **23x and 9.1x** — the assertion below is 5x, set
    from the SMALLER of the two.  ★It was written as 10x from the first
    file's ratio alone and the second file failed it: a threshold taken from
    one member of a two-member corpus is a threshold nobody measured.
    """
    from fylite import kernel as K
    from fylite.io.geqdsk import grid, read_geqdsk

    g = read_geqdsk(_fydata_gfile(name))
    r, z, psi_read = grid(g)
    psi = np.ascontiguousarray(np.asarray(psi_read, float).T)
    sim, sib = float(g["simag"]), float(g["sibry"])
    psin = (psi - sim) / (sib - sim)
    xt = np.linspace(0.0, 1.0, len(g["pprime"]))
    look = np.clip(psin, 0.0, 1.0)
    pp = np.interp(look, xt, np.asarray(g["pprime"], float))
    ffp = np.interp(look, xt, np.asarray(g["ffprim"], float))
    mu0 = 4e-7 * np.pi
    R = np.asarray(r, float)[:, None] * np.ones((1, len(z)))
    bracket = -(mu0 * R ** 2 * pp + ffp)
    lhs = K.deltastar_apply(r, z, psi)
    inner = np.zeros(psi.shape, bool)
    inner[2:-2, 2:-2] = True
    band = inner & (psin > 0.05) & (psin < 0.95)
    rg, zg = np.meshgrid(np.asarray(r, float), np.asarray(z, float),
                         indexing="ij")
    ins = np.asarray(K.inside_polygon(
        rg.ravel(), zg.ravel(), np.asarray(g["rbbbs"], float),
        np.asarray(g["zbbbs"], float))).reshape(psi.shape).astype(bool)

    def worst(sel):
        a, b = lhs[sel], bracket[sel]
        return float(np.max(np.abs(a - b))
                     / max(float(np.max(np.abs(b))), 1e-300))

    band_worst, in_worst = worst(band), worst(band & ins)
    assert in_worst < 0.15, in_worst
    assert band_worst > 5 * in_worst, (band_worst, in_worst)
    #: ★and the band really does reach outside — otherwise the two masks
    #: would be the same set and the line above would be measuring noise
    assert (band & ~ins).sum() > 100, (band & ~ins).sum()


def test_the_analytic_fixture_stays_orders_better_than_a_reconstruction():
    """★The two tiers must not be conflated.  A tolerance loose enough for a
    real reconstruction (0.15) is meaningless for a file whose own writer
    solved the equation — so the fixture keeps its own, tight assertion, and
    that is why the DECISION rests on the scale-free margin rather than on
    one absolute number that would have to serve both."""
    from fylite.io.geqdsk import measure_cocos

    rec = measure_cocos(_fixture())
    assert rec["residual"] < 1e-3, rec
    assert rec["margin"] > 1000, rec["margin"]

