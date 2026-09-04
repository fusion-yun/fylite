"""Plot verification: flux-map rendering (PNG/JPG) + X-point detection."""
from pathlib import Path

import pytest

from fylite.io import geqdsk
from fylite import device
from fylite.plot import find_x_points, plot_gfile


def test_xpoint_detection_reference(gref):
    """g093060.01000 is diverted (lower single null)."""
    g = geqdsk.read_geqdsk(gref)
    xp = find_x_points(g)
    assert xp, "expected a saddle point on the diverted reference"
    assert xp[0]["r"] == pytest.approx(1.655, abs=0.05)
    assert xp[0]["z"] == pytest.approx(-0.816, abs=0.06)
    assert xp[0]["psin"] == pytest.approx(1.0, abs=0.05)


def test_render_png(gref, tmp_path):
    out = plot_gfile(gref, tmp_path / "ref.png")
    assert out.endswith(".png")
    assert (tmp_path / "ref.png").stat().st_size > 10_000


def test_render_jpg(gref, tmp_path):
    """JPG needs Pillow; plot_gfile falls back to PNG without it."""
    out = plot_gfile(gref, tmp_path / "ref.jpg", dpi=120)
    from pathlib import Path
    assert Path(out).stat().st_size > 10_000
    if out.endswith(".png"):
        pytest.skip("Pillow unavailable: jpg fell back to png (documented)")
    assert out.endswith(".jpg")


# --------------------------------------------------------------------------- #
# Diagnostic geometry + NEO panel (the one-figure reconstruction, extended)
# --------------------------------------------------------------------------- #
def _fake_result(n_probe=79, n_loop=35, probes_weighted=False):
    import numpy as np
    psin = np.linspace(0.0, 1.0, 12)
    return {
        "q0": 0.78, "q95": 3.08, "ip": 3.9e5, "betap": 0.30, "ali": 1.95,
        "wplasm": 3.7e4, "chisq": 11.8,
        "ensemble": {"n": 4, "n_ok": 4, "perturb": ["pressure"]},
        "errorbars": {"q0": {"sigma": 0.009}},
        "profiles": {"q": {"psin": psin, "mean": 1 + 2 * psin,
                           "std": 0.05 + 0 * psin}},
        "diagnostics": {
            "mag_probes": {"measured": [0.1] * n_probe,
                           "computed": [0.11] * n_probe,
                           "alive": [probes_weighted] * n_probe, "unit": "T"},
            "flux_loops": {"measured": [0.4] * n_loop,
                           "computed": [0.41] * n_loop,
                           "alive": [True] * n_loop, "unit": "Wb/rad"}},
    }


def test_device_geometry_matches_the_fitted_channel_counts():
    """The overlay indexes straight into the diagnostic vectors — so the
    geometry must carry exactly as many channels as the fit reports."""
    from fylite import device_geometry
    from fylite import device as dev
    geom = device_geometry()
    assert len(geom["probes"]["r"]) == device.NMAGPRI
    assert len(geom["probes"]["z"]) == device.NMAGPRI
    assert len(geom["probes"]["angle_deg"]) == device.NMAGPRI
    assert len(geom["probes"]["node"]) == device.NMAGPRI
    assert len(geom["flux_loops"]["r"]) == device.NSILOP
    assert len(geom["flux_loops"]["node"]) == device.NSILOP
    assert len(geom["point_chords"]["z"]) == device.POINT_NCHORD
    assert geom["point_chords"]["r_ref"] == device.POINT_RPOL
    #: ★★``endswith("dprobe.dat")`` — the DECK reader, deleted when the
    #: geometry moved onto the fyo device document.  Every other assertion
    #: in this case passed on the document, so what the stale line pinned
    #: was the format, and the format is what changed.  The case was
    #: invisible because the file carried ``@requires_reference_case``,
    #: whose predicate named a file no test uses.
    assert geom["source"] == "fyo:device_document"
    # inside the vessel, and not all stacked at one point
    import numpy as np
    for fam in ("probes", "flux_loops"):
        r = np.asarray(geom[fam]["r"])
        z = np.asarray(geom[fam]["z"])
        assert (r > 1.0).all() and (r < 3.0).all()
        assert np.abs(z).max() < 2.0 and np.ptp(r) > 0.1


def test_reconstruction_figure_takes_geometry_and_neo(tmp_path):
    from fylite import device_geometry
    from fylite.plot import plot_reconstruction
    import numpy as np
    psin = np.linspace(0.05, 0.95, 12)
    neo = {"surface_psin": list(psin), "jpar_dke": list(np.exp(-psin)),
           "neo_resolution": "fast",
           "bootstrap_baseline": {"source": "neo:jpar_sauter_2021",
                                  "psin": list(psin),
                                  "j_bs": list(0.9 * np.exp(-psin)),
                                  "jpar_sauter_1999": list(1.3 * np.exp(-psin))}}
    cur = {"psin": psin, "j_ohm": 1 - 0.3 * psin,
           "j_bootstrap": 0.3 * np.exp(-psin), "j_total": 1 + 0 * psin}
    g = Path(__file__).resolve().parents[2] / "tests/data/FYDOC-CASE-12-synthetic/g_synthetic.geqdsk"
    out = plot_reconstruction(_fake_result(), g, tmp_path / "full.png",
                              current=cur, geometry=device_geometry(),
                              neo=neo, dpi=80)
    assert Path(out).stat().st_size > 50_000
    # the legacy call (no geometry, no neo, no current) must still render
    out2 = plot_reconstruction(_fake_result(), g, tmp_path / "plain.png",
                               dpi=80)
    assert Path(out2).stat().st_size > 20_000


def test_neo_panel_says_so_when_there_is_no_bootstrap_output():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from fylite.plot import _neo_panel
    fig, ax = plt.subplots()
    _neo_panel(ax, {})
    assert any("no bootstrap output" in t.get_text() for t in ax.texts)
    plt.close(fig)


def test_unweighted_channels_keep_their_forward_prediction():
    """FWTMP2=0 removes the probes from the fit, not from the figure: the
    loops-only benchmark's evidence IS the unweighted measured-vs-predicted."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from fylite.plot import _diag
    fig, ax = plt.subplots()
    _diag(ax, _fake_result()["diagnostics"]["mag_probes"], "probes")
    labels = [ln.get_label() for ln in ax.lines]
    assert "measured (unweighted)" in labels
    assert "predicted (unweighted)" in labels
    # the unweighted series carry every channel (nothing dropped)
    drawn = {ln.get_label(): len(ln.get_xdata()) for ln in ax.lines}
    assert drawn["measured (unweighted)"] == 79
    assert drawn["predicted (unweighted)"] == 79
    assert drawn["measured"] == 0 and drawn["reconstructed"] == 0
    plt.close(fig)


def test_fwtmp2_override_is_what_the_alive_mask_reports():
    """The mask must be the weight the solver got, not the data gate: an
    all-zero FWTMP2 cannot leave 21 probes reported as constraints."""
    #: ★where it lives — `fylite.run` used to re-export it, which was
    #: this package's only import cycle (see `run.py`)
    from fylite.scenario.analysis.recon_rs import _diagnostic_signals
    meas = {"expmp2": [0.1] * 79, "fwtmp2": [1.0] * 21 + [0.0] * 58,
            "coils": [0.4] * 35}
    afile = {"cmpr2": [0.11] * 79, "csilop": [0.41] * 35}
    gated = _diagnostic_signals(meas, afile, {})
    assert sum(gated["mag_probes"]["alive"]) == 21          # the data gate
    off = _diagnostic_signals(meas, afile, {}, {"FWTMP2": [0.0] * 79})
    assert sum(off["mag_probes"]["alive"]) == 0             # the solver's view
    assert len(off["mag_probes"]["measured"]) == 79         # still plotted
    # a loop override lands on the loops, independently
    lo = _diagnostic_signals(meas, afile, {}, {"FWTSI": [1.0] * 30 + [0.0] * 5})
    assert sum(lo["flux_loops"]["alive"]) == 30
    assert sum(lo["mag_probes"]["alive"]) == 21
