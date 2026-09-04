"""The fyo document layer — the Python side's whole remit, tested as such.

★These are NOT physics tests, and since 2026-08-22 the file does not hold
any: the five ladder claims that used to sit at the bottom behind a
``physics`` mark are in the physics/numerics tier now
(``tests/test_fyo_ladder_metrics.py``).  Every claim here is
about the *conversion* — that the document says what the deck said, that the
kernel is handed the right arrays in the right index order, and that what
comes back survives a trip to disk unchanged.  A conversion layer that
quietly transposes, drops a section, or reorders an array of structure is
exactly the failure this repository has paid for before.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fylite import fyo

from fylite.io import geqdsk

ROOT = Path(__file__).resolve().parents[2]
GFILE = ROOT / "tests/data/FYDOC-CASE-12-synthetic/corpus/g_synthetic.geqdsk"

pytestmark = pytest.mark.skipif(not GFILE.exists(),
                                reason="bundled g-file not present")


@pytest.fixture(scope="module")
def doc():
    return fyo.equilibrium(GFILE)


def test_the_document_says_what_the_deck_said(doc):
    g = geqdsk.read_geqdsk(GFILE)
    sl = doc["time_slice"][0]
    assert doc["@type"] == "fyo:equilibrium"
    assert doc["@context"]["fyo"] == fyo.FYO_PREFIX
    assert sl["global_quantities"]["magnetic_axis"]["r"] == g["rmaxis"]
    assert sl["global_quantities"]["psi_boundary"] == g["sibry"]
    assert doc["vacuum_toroidal_field"]["b0"] == g["bcentr"]
    assert np.array_equal(sl["profiles_1d"]["f"], np.asarray(g["fpol"], float))


def test_the_two_dimensional_map_is_in_imas_order_not_the_decks(doc):
    """``psi[dim1, dim2] = psi[R, Z]``, whatever the deck wrote.

    ★On a square grid a missing transpose is not a crash — it is a different
    plasma (this repo measured kappa 1.41 against 2.05 once).  So the check
    is made on a deliberately RECTANGULAR map, where the wrong order cannot
    even be shaped.
    """
    g = geqdsk.read_geqdsk(GFILE)
    nw, nh = 9, 5
    r = np.linspace(1.0, 2.0, nw)
    z = np.linspace(-0.5, 0.5, nh)
    psi_rz = np.add.outer((r - 1.5) ** 2, (z * 2) ** 2)     # [r, z]
    rect = dict(g)
    rect.update(nw=nw, nh=nh, rleft=r[0], rdim=r[-1] - r[0],
                zmid=0.0, zdim=z[-1] - z[0], simag=0.0, sibry=1.0,
                fpol=np.ones(nw), pres=np.zeros(nw), ffprim=np.zeros(nw),
                pprime=np.zeros(nw), qpsi=np.ones(nw),
                psirz=psi_rz.T.ravel())                     # a deck writes [z, r]
    d = fyo.equilibrium(rect, source="rect")
    p2 = d["time_slice"][0]["profiles_2d"][0]
    assert p2["psi"].shape == (nw, nh)
    assert np.array_equal(p2["psi"], psi_rz)
    assert np.array_equal(p2["grid"]["dim1"], r)
    #: and the round trip back to the kernel's arguments is the same map
    grid, psin, dpsi = fyo.flux_map_of(d)
    g_grid, g_psin, g_dpsi = geqdsk.kernel_flux_map(rect)
    assert (grid.nr, grid.nz) == (nw, nh)
    assert np.array_equal(psin, g_psin) and dpsi == g_dpsi


def test_the_derived_document_is_the_kernels_answer_renamed(doc):
    d = fyo.derive(doc)
    p1 = d["time_slice"][0]["profiles_1d"]
    tm = fyo.transport_metrics(GFILE)
    for kern, dd in fyo.PROFILE_NAMES.items():
        assert np.array_equal(p1[dd], tm[kern]), dd
    assert d["fylite:derived_from"] == doc["@id"]
    assert (d["time_slice"][0]["global_quantities"]["fylite:rho_tor_boundary"]
            == tm["rho_b"])


def test_the_metric_and_the_shape_are_on_the_same_surfaces(doc):
    """★The reason the two live in one kernel call.

    They used to be two calls with different DEFAULT ladders (41 surfaces on
    [0.02, 0.95] against 24 on [0.1, 0.95]); a document carrying both then
    described a metric and a shape for surfaces that are not the same
    surfaces.
    """
    d = fyo.derive(doc, n_surfaces=17, edge=0.9)
    p1 = d["time_slice"][0]["profiles_1d"]
    mil = d["fylite:miller"]
    assert np.array_equal(p1["fylite:psi_norm"], mil["psin"])
    assert np.array_equal(p1["q"], mil["q"])


@pytest.mark.parametrize("ext", [".h5", ".json"])
def test_a_document_survives_the_disk(doc, tmp_path, ext):
    pytest.importorskip("h5py") if ext == ".h5" else None
    d = fyo.derive(doc, n_surfaces=9)
    back = fyo.read(fyo.write(d, tmp_path / ("eq" + ext)))
    assert back["@type"] == "fyo:equilibrium"
    for k in ("rho_tor", "volume", "q"):
        assert np.array_equal(
            np.asarray(back["time_slice"][0]["profiles_1d"][k], float),
            d["time_slice"][0]["profiles_1d"][k])
    assert np.array_equal(np.asarray(back["fylite:miller"]["kappa"], float),
                          d["fylite:miller"]["kappa"])


def test_an_array_of_structure_keeps_its_order_on_disk(tmp_path):
    pytest.importorskip("h5py")
    d = {"@type": "fyo:equilibrium",
         "time_slice": [{"global_quantities": {"ip": float(i)}}
                        for i in range(12)]}
    back = fyo.read(fyo.write(d, tmp_path / "aos.h5"))
    #: 10 sorts before 2 as a STRING; an index that reorders time is a
    #: different discharge
    assert [s["global_quantities"]["ip"] for s in back["time_slice"]] == \
        [float(i) for i in range(12)]


def test_the_writer_refuses_what_it_cannot_write(tmp_path):
    pytest.importorskip("h5py")
    with pytest.raises(TypeError):
        fyo.write({"@type": "fyo:equilibrium", "thing": object()},
                  tmp_path / "bad.h5")


# --------------------------------------------------------------------------- #
# the model layer's face: documents in, documents out                          #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def prof():
    pn = np.linspace(0.0, 1.0, 64)
    return fyo.core_profiles(pn, ne=4.2e19 * (1 - pn ** 2) + 2e18,
                             te=3200.0 * (1 - pn ** 2) ** 1.4 + 60.0,
                             zeff=1.8, source="test")


def test_a_profile_document_carries_the_grid_it_was_sampled_on(prof):
    """★A profile without its coordinate is the oldest way to get a plausible
    wrong answer out of this chain."""
    back = fyo.profiles_of(prof)
    assert back["psin"].size == back["ne"].size == back["te"].size
    assert back["zeff"] == 1.8
    assert prof["@type"] == "fyo:core_profiles"


def test_the_beam_face_is_the_model_in_dd_names(doc, prof):
    from fylite.scenario.model import nbi
    beams = nbi.east_beams([2.0e6, 0, 0, 0], [6.0e4] * 4, [1.26] * 4)
    d = fyo.beam_sources(doc, prof, beams)
    src = d["source"][0]
    assert d["@type"] == "fyo:core_sources"
    assert src["identifier"] == {"name": "nbi", "index": 2}
    #: the numbers are the model's, not this layer's
    pr = fyo.profiles_of(prof)
    ref = nbi.deposit(GFILE, pr["ne"], pr["te"], beams, psin_prof=pr["psin"],
                      zeff=pr["zeff"])
    assert np.array_equal(src["profiles_1d"]["j_parallel"], ref["j_nbi"])
    assert src["global_quantities"]["current"] == ref["i_nbi"]
    #: ★bit-identical means the document really is the deck: it was NOT,
    #: until the limiter travelled with it — without one every trace falls
    #: back to the grid box and the outermost beam shell moved by 30 %.


def test_a_wave_that_deposits_nothing_is_a_document_with_no_source(doc, prof):
    """★A result, not a failure — and one a persisted document must be able
    to state.  With no up-shift EAST's launchers resonate above the plasma."""
    from fylite.scenario.model import lh
    d = fyo.wave_sources(doc, prof, lh.east_launchers(0.0), eta_cd=1e19)
    assert d["@type"] == "fyo:core_sources" and d["source"] == []


def test_sources_merge_by_concatenation_not_by_addition(doc, prof):
    """★Adding here would hide that two sources were computed on different
    ladders; the caller adds what it means to add, on a grid it chose."""
    from fylite.scenario.model import lh, nbi
    a = fyo.beam_sources(doc, prof,
                         nbi.east_beams([2.0e6, 0, 0, 0], [6.0e4] * 4,
                                        [1.26] * 4))
    b = fyo.wave_sources(doc, prof, lh.east_launchers(2.0e6), eta_cd=1e19,
                         upshift=(1.4, 2.2))
    #: ★one face for one DD term: `bootstrap_source` and
    #: `neoclassical_source` both emitted `bootstrap_current`, and the
    #: solver is an argument now rather than a second function.
    c = fyo.neoclassical_source(doc, prof, solver="redl")
    merged = fyo.merge_sources(a, b, c)
    assert [s["identifier"]["name"] for s in merged["source"]] == \
        ["nbi", "lh", "bootstrap_current"]
    with pytest.raises(ValueError):
        fyo.merge_sources(doc)          # an equilibrium is not a source set


def test_a_source_document_survives_the_disk(doc, prof, tmp_path):
    pytest.importorskip("h5py")
    from fylite.scenario.model import nbi
    d = fyo.beam_sources(doc, prof,
                         nbi.east_beams([2.0e6, 0, 0, 0], [6.0e4] * 4,
                                        [1.26] * 4))
    back = fyo.read(fyo.write(d, tmp_path / "src.h5"))
    assert np.array_equal(
        np.asarray(back["source"][0]["profiles_1d"]["j_parallel"], float),
        d["source"][0]["profiles_1d"]["j_parallel"])
    assert back["source"][0]["identifier"]["name"] == "nbi"


# --------------------------------------------------------------------------- #
# The document is the record; the deck stops at the door                      #
# --------------------------------------------------------------------------- #

#: The model modules that take an equilibrium (the ladder itself lives in
#: `fyo`, checked separately below).  Each takes the DOCUMENT; a g-file
#: path or dict is accepted at the door (`fyo.as_equilibrium`) and never
#: read past it.  Before this, every one of them read `g["..."]` straight
#: off the deck — and `fyo` flattened the document BACK into deck keys to
#: feed them (`_as_geqdsk`, retired).
_TAKE_AN_EQUILIBRIUM = (
    "scenario/model/closure.py", "scenario/model/neoclassical.py",
    "scenario/model/neoclassical.py", "scenario/model/nbi.py", "scenario/model/lh.py",
)


def test_nothing_past_the_door_reads_a_deck():
    """★A machine check, because "the models take the document now" is
    the kind of sentence that decays: one `g["bcentr"]` in a refactor and
    the deck's names are back, with the `[z, r]` order behind them."""
    import ast
    pkg = Path(fyo.__file__).resolve().parent
    offenders = []
    for rel in _TAKE_AN_EQUILIBRIUM:
        tree = ast.parse((pkg / rel).read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and "geqdsk" in n.module:
                offenders.append(f"{rel}:{n.lineno} imports {n.module}")
            if isinstance(n, ast.ImportFrom) and any(a.name == "geqdsk" for a in n.names):
                offenders.append(f"{rel}:{n.lineno} imports geqdsk")
            if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                    and n.value.id == "g" and isinstance(n.slice, ast.Constant)
                    and isinstance(n.slice.value, str)):
                offenders.append(f"{rel}:{n.lineno} reads g[{n.slice.value!r}]")
    assert not offenders, "\n".join(offenders)
    #: and fyo itself reads the deck in exactly one place — the converter
    src = (pkg / "fyo.py").read_text()
    tree = ast.parse(src)
    readers = sorted({
        next(f.name for f in tree.body
             if isinstance(f, ast.FunctionDef) and f.lineno <= n.lineno <= f.end_lineno)
        for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
        and n.value.id == "geqdsk"})
    assert readers == ["equilibrium"], readers


def test_the_door_accepts_a_deck_and_passes_a_document_through(doc):
    assert fyo.as_equilibrium(doc) is doc
    from_path = fyo.as_equilibrium(GFILE)
    assert from_path["@type"] == "fyo:equilibrium"
    np.testing.assert_array_equal(fyo.flux_map_of(from_path)[1],
                                  fyo.flux_map_of(doc)[1])


def test_a_ladder_from_the_document_is_the_ladder_from_the_deck(doc):
    """Same numbers either way in — the door converts, it does not compute."""
    a = fyo.Ladder(doc)
    b = fyo.Ladder(GFILE)
    for k in a.metrics:
        np.testing.assert_array_equal(a.metrics[k], b.metrics[k], err_msg=k)
    assert a.miller == b.miller
    assert a.eq is doc and (a.a_minor, a.b0, a.dpsi) == (b.a_minor, b.b0, b.dpsi)


def test_the_accessors_say_what_the_deck_said(doc):
    g = geqdsk.read_geqdsk(GFILE)
    assert fyo.axis_of(doc) == (g["rmaxis"], g["zmaxis"])
    assert fyo.psi_range_of(doc) == (g["simag"], g["sibry"])
    assert fyo.field_of(doc) == (g["rcentr"], g["bcentr"])
    np.testing.assert_array_equal(fyo.profile_of(doc, "q"), g["qpsi"])
    np.testing.assert_array_equal(fyo.profile_of(doc, "f"), g["fpol"])
    np.testing.assert_array_equal(fyo.limiter_of(doc)[0], g["rlim"])
    np.testing.assert_array_equal(fyo.boundary_of(doc)[1], g["zbbbs"])
    #: and the flux map is the deck's, in the kernel's order, with NO
    #: transpose anywhere on the document side
    grid, psin, dpsi = fyo.flux_map_of(doc)
    g_grid, g_psin, g_dpsi = geqdsk.kernel_flux_map(g)
    assert (grid.nr, grid.nz, dpsi) == (g_grid.nr, g_grid.nz, g_dpsi)
    np.testing.assert_array_equal(psin, g_psin)


# --------------------------------------------------------------------------- #
# The Ladder: one trace, held as an object                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def traces(monkeypatch):
    """Count the kernel's ladder calls — the one thing the object exists
    to bound."""
    from fylite import kernel
    calls = []
    real = kernel.equilibrium_ladder

    def counted(*a, **k):
        calls.append(k.get("levels"))
        return real(*a, **k)
    monkeypatch.setattr(kernel, "equilibrium_ladder", counted)
    return calls


def test_the_views_are_the_functions(traces):
    """`transport_metrics` / `miller_geometry` are views of a fresh Ladder
    — bit-identical to the object's, and each exactly one trace."""
    tm = fyo.transport_metrics(GFILE)
    lad = fyo.Ladder(GFILE)
    for k, v in lad.transport_metrics().items():
        np.testing.assert_array_equal(v, tm[k], err_msg=k)
    mg = fyo.miller_geometry(GFILE)
    rows = fyo.Ladder(GFILE, fyo._levels(None, fyo.MILLER_LADDER,
                                                None, 0.95)).miller_geometry()
    assert mg == rows
    assert len(traces) == 4


def test_with_surfaces_carries_the_requested_surfaces_exactly(traces):
    req = [0.3, 0.5, 0.7]
    lad = fyo.Ladder.with_surfaces(GFILE, req)
    assert len(traces) == 1
    idx = lad.index_of(req)
    assert lad.psin[idx].tolist() == req                    # exact, not nearest
    rows = lad.miller_geometry(req)
    assert [r["psin"] for r in rows] == req
    # the dense part is still the transport ladder
    dense = np.linspace(*fyo.TRANSPORT_LADDER[:1], 0.95,
                        fyo.TRANSPORT_LADDER[1])
    assert np.all(np.isin(dense, lad.psin))
    # and the local quantities at a requested surface are the same numbers
    # a ladder of just those surfaces gives: same kernel, same level
    alone = fyo.miller_geometry(GFILE, psin=req)
    for a, b in zip(alone, rows):
        for k in ("psin", "r", "rmaj", "zmag", "q", "kappa", "delta", "zeta"):
            assert a[k] == b[k], k


def test_with_surfaces_returns_a_ladder_it_is_given_and_refuses_a_short_one(traces):
    lad = fyo.Ladder.with_surfaces(GFILE, [0.3, 0.5])
    assert fyo.Ladder.with_surfaces(lad, [0.5]) is lad
    assert len(traces) == 1                                  # no second trace
    with pytest.raises(ValueError, match="not on the ladder"):
        fyo.Ladder.with_surfaces(lad, [0.51])
    with pytest.raises(ValueError, match="not on the ladder"):
        lad.miller_geometry([0.3, 0.99])
    assert len(traces) == 1


def test_the_closure_builds_its_states_without_tracing(traces):
    """★The reason the object exists: `surface_states` on a held ladder
    touches the kernel's tracer zero times, where the g-file door used to
    trace three ladders per call — and was called once per outer step."""
    from fylite.scenario.model import closure
    psin_prof = np.linspace(0.0, 1.0, 51)
    ne = 4e19 * (1 - 0.9 * psin_prof ** 2)
    te = 2500.0 * (1 - 0.95 * psin_prof ** 2) + 50.0
    lad = fyo.Ladder.with_surfaces(GFILE, [0.3, 0.5, 0.7])
    assert len(traces) == 1
    for _ in range(3):
        st = closure.surface_states(lad, psin=[0.3, 0.5, 0.7],
                                    psin_prof=psin_prof, ne=ne, te=te)
    assert len(traces) == 1
    assert len(st) == 3 and all(s["b_unit"] > 0 for s in st)
    # the g-file door is the same builder behind one trace
    via_g = closure.equilibrium_surface_states(GFILE, psin=[0.3, 0.5, 0.7],
                                         psin_prof=psin_prof, ne=ne, te=te)
    assert len(traces) == 2
    for a, b in zip(st, via_g):
        assert a == b


def test_a_transport_ladder_of_four_surfaces_is_an_error_a_miller_one_is_not():
    """The policy lives in the transport VIEW, not the kernel and not the
    object: the same four-surface ladder is refused as metrics and served
    as shape."""
    lad = fyo.Ladder(GFILE, [0.3, 0.5, 0.7, 0.9])
    assert len(lad.miller_geometry()) == 4
    with pytest.raises(ValueError, match="survived tracing"):
        lad.transport_metrics()
    assert len(fyo.miller_geometry(GFILE, psin=[0.3, 0.5, 0.7, 0.9])) == 4


def test_a_deck_without_a_limiter_traces_as_the_grid_box(traces):
    """★"No limiter means the grid is the limiter" is the kernel's rule now
    (`surfaces::trace`); this layer passes the deck's limiter as it is —
    here, empty — and the answer is bit-identical to the four-point box
    of the grid's edges this module used to build for that case."""
    from fylite.io import geqdsk
    g = geqdsk.read_geqdsk(GFILE)
    bare = dict(g); bare["rlim"] = []; bare["zlim"] = []; bare["limitr"] = 0
    assert geqdsk.limiter(bare)[0].size == 0
    r, z, _ = geqdsk.grid(g)
    boxed = dict(g)
    boxed["rlim"] = [r[0], r[-1], r[-1], r[0]]
    boxed["zlim"] = [z[0], z[0], z[-1], z[-1]]
    a = fyo.transport_metrics(bare)
    b = fyo.transport_metrics(boxed)
    for k in a:
        np.testing.assert_array_equal(a[k], b[k], err_msg=k)
    assert fyo.miller_geometry(bare) == fyo.miller_geometry(boxed)

