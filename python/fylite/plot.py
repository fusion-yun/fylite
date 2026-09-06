"""GEQDSK visualization: 2D flux-surface map -> PNG/JPG.

Rendered elements: normalized-psi contours (closed surfaces solid, open flux
dashed/faint), magnetic axis, numerically detected X-point(s) (the g-file
does not store them), the LCFS boundary polyline, and the limiter outline.

JPG output requires Pillow (matplotlib's jpg writer); PNG always works.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from . import kernel


#: ★The grid a g-file implies is :func:`fylite.io.geqdsk.grid`, not this

from .io import geqdsk
#: module's.  It used to live here, and `metrics`, `chords` and the beam
#: model each imported it OUT of the plotting module — a physics quantity
#: reached through matplotlib's neighbour.  The name stays as an alias
#: because this module's own figures use it on every page.
_grid = geqdsk.grid


def find_x_points(g: dict, *, psin_window: float = 0.15,
                  min_axis_dist: float = 0.25) -> list[dict]:
    """Saddle points of PSIRZ — the kernel's (:func:`fylite.kernel.x_points`).

    Returns at most two ``{r, z, psin, grad}``, nearest ψ_N = 1 first; an
    empty list means a limited configuration as far as the grid resolution
    can tell.

    ★The detector used to be numpy right here, in the module that draws the
    figures — so "is this discharge diverted" had an answer that depended on
    which module you asked.  What is left is reading the deck.  Measured
    against the numpy it replaces on ``g063982.04800``: the same two saddles,
    the same ranking, positions apart by < 9e-15 m (the 2x2 Newton step in
    closed form against LAPACK's).
    """
    r, z, psi = _grid(g)
    if g["sibry"] == g["simag"]:
        return []
    return kernel.x_points(
        kernel.grid_of(r, z),
        np.ascontiguousarray(np.asarray(psi, float).T),
        psi_axis=float(g["simag"]), psi_bnd=float(g["sibry"]),
        axis=(float(g["rmaxis"]), float(g["zmaxis"])),
        psin_window=psin_window, min_axis_dist=min_axis_dist)


def _title_from(path: Path, g: dict) -> str:
    m = re.match(r"g(\d+)\.(\d+)", path.name)
    if m:
        return f"shot {int(m.group(1))}  t = {int(m.group(2))} ms"
    return path.name


def plot_gfile(gfile_path: str | Path, out_path: str | Path, *,
               dpi: int = 150, levels=None) -> str:
    """Render the flux map of a GEQDSK to ``out_path`` (.png or .jpg/.jpeg).

    Returns the path actually written (may fall back from .jpg to .png when
    Pillow is unavailable).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    gfile_path = Path(gfile_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g = geqdsk.read_geqdsk(gfile_path)
    r, z, psi = _grid(g)
    dpsi = g["sibry"] - g["simag"]
    psin = (psi - g["simag"]) / dpsi if dpsi != 0 else psi * 0.0

    fig, ax = plt.subplots(figsize=(6, 8.5))
    closed = levels if levels is not None else np.arange(0.1, 1.0, 0.1)
    cf = ax.contourf(r, z, psin, levels=np.linspace(0.0, 1.0, 21),
                     cmap="viridis", alpha=0.35)
    ax.contour(r, z, psin, levels=closed, colors="steelblue",
               linewidths=0.7)
    # open flux (divertor legs / private region structure)
    ax.contour(r, z, psin, levels=[1.02, 1.05, 1.1, 1.2, 1.3],
               colors="slategray", linewidths=0.6, linestyles="dashed",
               alpha=0.7)
    fig.colorbar(cf, ax=ax, label=r"$\bar\psi$", shrink=0.8)

    if g["limitr"]:
        ax.plot(list(g["rlim"]) + [g["rlim"][0]],
                list(g["zlim"]) + [g["zlim"][0]],
                color="0.4", lw=1.5, label="limiter")
    if g["nbbbs"]:
        ax.plot(g["rbbbs"], g["zbbbs"], "r-", lw=2.0, label="LCFS")
    ax.plot([g["rmaxis"]], [g["zmaxis"]], "k+", ms=12, mew=2)
    ax.annotate(f"axis ({g['rmaxis']:.3f}, {g['zmaxis']:+.3f})",
                (g["rmaxis"], g["zmaxis"]), textcoords="offset points",
                xytext=(8, 6), fontsize=8)

    xpts = find_x_points(g)
    for k, xp in enumerate(xpts):
        ax.plot([xp["r"]], [xp["z"]], "x", color="crimson", ms=11, mew=2.5)
        ax.annotate(f"X ({xp['r']:.3f}, {xp['z']:+.3f})",
                    (xp["r"], xp["z"]), textcoords="offset points",
                    xytext=(8, -10), fontsize=8, color="crimson")
    if not xpts:
        ax.text(0.02, 0.02, "limited configuration (no saddle found)",
                transform=ax.transAxes, fontsize=8, color="0.3")

    ax.set_xlabel("R [m]")
    ax.set_ylabel("Z [m]")
    ax.set_aspect("equal")
    ax.set_title(f"{_title_from(gfile_path, g)}\n"
                 rf"$\psi_a$={g['simag']:+.4f}  $\psi_b$={g['sibry']:+.4f} "
                 rf"Wb/rad   $I_p$={g['current']:.3e} A", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()

    try:
        fig.savefig(out_path, dpi=dpi)
        written = out_path
    except (ValueError, RuntimeError, ImportError) as e:
        if out_path.suffix.lower() in (".jpg", ".jpeg"):
            written = out_path.with_suffix(".png")
            fig.savefig(written, dpi=dpi)
            print(f"[fylite] jpg save failed ({e}); wrote {written} instead "
                  f"(jpg needs Pillow)")
        else:
            plt.close(fig)
            raise
    plt.close(fig)
    return str(written)


def _overlay_geometry(ax, geom: dict, diags: dict | None = None) -> None:
    """Draw the fitted diagnostics onto the flux map (who saw this plasma).

    Probes and loops are coloured by whether the fit was allowed to use them —
    the ``alive`` mask on ``result["diagnostics"]`` — so a loops-only benchmark
    (``FWTMP2=0``) is visible as a ring of grey probes rather than being a fact
    buried in the namelist.  Probe orientation (``AMP2``) is drawn as a short
    tick: the direction the channel measures.
    """
    diags = diags or {}

    def _alive(key, n):
        a = np.asarray((diags.get(key) or {}).get("alive", []), dtype=bool)
        return a if a.size == n else np.ones(n, dtype=bool)

    ch = geom.get("point_chords") or {}
    if ch.get("z"):
        rlo = float(np.min(geom["limiter"]["r"]))
        rhi = max(float(np.max(geom["limiter"]["r"])),   # out to the entry port
                  float(ch.get("r_ref") or 0.0))
        for i, zc in enumerate(ch["z"]):
            ax.plot([rlo, rhi], [zc, zc], "-", color="tab:cyan", lw=0.8,
                    alpha=0.85, label="POINT chords" if i == 0 else None)

    pr = geom.get("probes") or {}
    if pr.get("r"):
        pr_r, pr_z = np.asarray(pr["r"]), np.asarray(pr["z"])
        ang = np.radians(np.asarray(pr["angle_deg"]))
        ln = np.asarray(pr["length"]) * 1.6
        live = _alive("mag_probes", pr_r.size)
        for sel, col, lab in ((live, "tab:red", "probes (weighted)"),
                              (~live, "0.6", "probes (unweighted)")):
            if not sel.any():
                continue
            ax.plot(pr_r[sel], pr_z[sel], ".", ms=3.0, color=col, label=lab)
            for rr, zz, aa, ll in zip(pr_r[sel], pr_z[sel], ang[sel], ln[sel]):
                ax.plot([rr - ll * np.cos(aa), rr + ll * np.cos(aa)],
                        [zz - ll * np.sin(aa), zz + ll * np.sin(aa)],
                        "-", color=col, lw=0.9)

    fl = geom.get("flux_loops") or {}
    if fl.get("r"):
        fl_r, fl_z = np.asarray(fl["r"]), np.asarray(fl["z"])
        live = _alive("flux_loops", fl_r.size)
        ax.plot(fl_r[live], fl_z[live], "s", ms=3.2, mfc="none", mew=0.9,
                color="tab:blue", label="flux loops (weighted)")
        if (~live).any():
            ax.plot(fl_r[~live], fl_z[~live], "s", ms=3.2, mfc="none", mew=0.9,
                    color="0.6", label="flux loops (unweighted)")


def _flux_map(ax, g: dict, geometry: dict | None = None,
              diags: dict | None = None) -> None:
    """Render the flux map + LCFS/axis/X-point into an existing axis."""
    r, z, psi = _grid(g)
    dpsi = g["sibry"] - g["simag"]
    psin = (psi - g["simag"]) / dpsi if dpsi != 0 else psi * 0.0
    cf = ax.contourf(r, z, psin, levels=np.linspace(0.0, 1.0, 21),
                     cmap="viridis", alpha=0.35)
    ax.contour(r, z, psin, levels=np.arange(0.1, 1.0, 0.1),
               colors="steelblue", linewidths=0.6)
    ax.contour(r, z, psin, levels=[1.02, 1.05, 1.1, 1.2],
               colors="slategray", linewidths=0.5, linestyles="dashed",
               alpha=0.7)
    ax.figure.colorbar(cf, ax=ax, label=r"$\bar\psi$", shrink=0.7)
    if g["limitr"]:
        ax.plot(list(g["rlim"]) + [g["rlim"][0]],
                list(g["zlim"]) + [g["zlim"][0]], color="0.4", lw=1.3)
    if g["nbbbs"]:
        ax.plot(g["rbbbs"], g["zbbbs"], "r-", lw=1.8, label="LCFS")
    ax.plot([g["rmaxis"]], [g["zmaxis"]], "k+", ms=11, mew=2)
    for xp in find_x_points(g):
        ax.plot([xp["r"]], [xp["z"]], "x", color="crimson", ms=10, mew=2)
    if geometry:
        _overlay_geometry(ax, geometry, diags)
    ax.set_xlabel("R [m]")
    ax.set_ylabel("Z [m]")
    ax.set_aspect("equal")
    ax.legend(loc="upper right", fontsize=6 if geometry else 7,
              framealpha=0.85)


def _band(ax, band: dict, color: str, label: str, ylabel: str) -> None:
    """Profile central line + 1-sigma error band from a _profile_band dict."""
    if not band:
        ax.text(0.5, 0.5, f"{label}: no ensemble", transform=ax.transAxes,
                ha="center", va="center", fontsize=8, color="0.5")
        ax.set_ylabel(ylabel, fontsize=8)
        return
    x = np.asarray(band["psin"])
    mu = np.asarray(band["mean"])
    sd = np.asarray(band["std"])
    ax.fill_between(x, mu - sd, mu + sd, color=color, alpha=0.25,
                    label=r"$\pm1\sigma$")
    ax.plot(x, mu, color=color, lw=1.6, label=label)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.legend(loc="best", fontsize=7)
    ax.grid(alpha=0.25)


def _diag(ax, fam: dict, title: str) -> None:
    """Measured vs reconstructed signal for one diagnostic family.

    Unweighted channels keep BOTH their measurement and the forward prediction,
    drawn muted: with ``FWTMP2=0`` the probes are not constraints but they are
    still the loops-only benchmark's evidence — the fit predicts them, and
    whether it predicts them well is the question that benchmark asks.
    """
    meas = np.asarray(fam["measured"])
    comp = np.asarray(fam["computed"])
    alive = np.asarray(fam.get("alive", [True] * len(meas)), dtype=bool)
    idx = np.arange(len(meas))
    ax.plot(idx[alive], meas[alive], "o", ms=3.5, color="tab:blue",
            label="measured")
    ax.plot(idx[alive], comp[alive], "x", ms=4, color="tab:red", mew=1.3,
            label="reconstructed")
    if (~alive).any():
        ax.plot(idx[~alive], meas[~alive], "o", ms=2.5, mfc="none", mew=0.8,
                color="tab:blue", alpha=0.45, label="measured (unweighted)")
        ax.plot(idx[~alive], comp[~alive], "x", ms=3, mew=0.8,
                color="tab:red", alpha=0.45, label="predicted (unweighted)")
    ax.set_title(f"{title}  [{fam.get('unit', '')}]", fontsize=8)
    ax.set_xlabel("channel", fontsize=7)
    ax.tick_params(labelsize=7)
    ax.legend(loc="best", fontsize=6, ncol=2)
    ax.grid(alpha=0.25)


_DIAG_TITLES = {"mag_probes": "magnetic probes", "flux_loops": "flux loops",
                "faraday": "POINT Faraday", "interferometry": "POINT n_e-line"}


def _current_panel(ax, current: dict) -> None:
    """J_ohm / J_bootstrap / J_total vs psi_N (self-consistent decomposition)."""
    x = np.asarray(current["psin"], dtype=float)
    ax.plot(x, current["j_ohm"], "-o", ms=3, color="tab:blue", label=r"$J_\mathrm{ohm}$")
    ax.plot(x, current["j_bootstrap"], "-s", ms=3, color="tab:red",
            label=r"$J_\mathrm{bs}$")
    ax.plot(x, current["j_total"], "-", lw=1.8, color="0.2", label=r"$J_\mathrm{tot}$")
    ax.fill_between(x, 0, current["j_bootstrap"], color="tab:red", alpha=0.12)
    ax.set_xlabel(r"$\bar\psi$", fontsize=8)
    ax.set_ylabel(r"$J/\langle J\rangle$", fontsize=8)
    ax.set_ylim(bottom=0)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=7, ncol=3, loc="upper right")
    ax.grid(alpha=0.25)


def _neo_panel(ax, neo: dict) -> None:
    """NEO's own bootstrap output, next to the analytic models it supersedes.

    ``neo`` is a ``oracles.loop.self_consistent`` (the kernel repository) result: ``jpar_dke`` is the
    drift-kinetic solve, and ``bootstrap_baseline`` carries NEO's *internally*
    evaluated Sauter-1999 / Redl-2021 coefficients — same surfaces, same
    geometry, same collisionality, same normalization, so the three curves are
    directly comparable and the analytic-vs-kinetic gap is read off the plot.

    On the Python-``redl`` fallback the baseline is in different units, so the
    curves are peak-normalized and the panel says so rather than pretending.
    """
    base = neo.get("bootstrap_baseline") or {}
    dke = np.asarray(neo.get("jpar_dke") or [], dtype=float)
    x = np.asarray(neo.get("surface_psin")
                   or (neo.get("current") or {}).get("psin")
                   or base.get("psin") or [], dtype=float)
    if x.size == 0 or (dke.size == 0 and not base):
        ax.text(0.5, 0.5, "NEO: no bootstrap output", transform=ax.transAxes,
                ha="center", va="center", fontsize=8, color="0.5")
        return
    same_units = base.get("source", "").startswith("neo:")
    unit = r"$\langle j_\parallel B\rangle$ [NEO]" if same_units else "normalized"

    def _prep(v):
        v = np.asarray(v, dtype=float)
        if same_units or v.size == 0:
            return v
        pk = np.max(np.abs(v))
        return v / pk if pk else v

    if dke.size == x.size:
        ax.plot(x, _prep(dke), "-o", ms=3, color="tab:red", lw=1.7,
                label="NEO DKE")
    if base.get("j_bs") is not None and len(base["j_bs"]) == x.size:
        lab = ("Sauter-2021 (NEO)" if same_units
               else f"{base.get('source', 'baseline')}")
        ax.plot(x, _prep(base["j_bs"]), "--s", ms=3, color="tab:blue", lw=1.3,
                label=lab)
    if base.get("jpar_sauter_1999") is not None \
            and len(base["jpar_sauter_1999"]) == x.size:
        ax.plot(x, _prep(base["jpar_sauter_1999"]), ":^", ms=3,
                color="tab:green", lw=1.3, label="Sauter-1999 (NEO)")
    res = neo.get("neo_resolution")
    ax.set_title("NEO bootstrap" + (f"  (res={res})" if res else ""), fontsize=8)
    ax.set_xlabel(r"$\bar\psi$", fontsize=8)
    ax.set_ylabel(unit, fontsize=8)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=6, loc="best")
    ax.grid(alpha=0.25)


def plot_reconstruction(result: dict, gfile_path: str | Path, out_path: str | Path,
                        *, dpi: int = 150, build_time=None, current=None,
                        geometry=None, neo=None) -> str:
    """One-figure reconstruction summary with error bars (K-12 deliverable).

    Panels, left→right: the equilibrium flux map (from ``gfile_path``); the
    q / pressure / n_e profiles with their ensemble ±1σ bands
    (``result["profiles"]``); and the measured-vs-reconstructed signal per
    diagnostic family (``result["diagnostics"]``).  A header line prints the key
    scalars with their posterior 1σ from ``result["errorbars"]``.

    ``result`` is the dict a reconstruction returns with ``uncertainty=N``
    (:func:`fylite.scenario.analysis.recon_rs.reconstruct_shot`), or the
    ``["result"]`` of one slice of
    :func:`fylite.scenario.analysis.recon_rs.run_series`.

    ★It named ``run`` and ``run_ensemble``.  The first was the EFIT driver;
    the second has never existed in this package under that name.

    ``build_time`` stamps the figure with when it was generated (provenance) —
    a ``datetime``/string, or the local now when omitted.
    """
    import datetime as _dt
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if build_time is None:
        build_time = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(build_time, _dt.datetime):
        build_time = build_time.strftime("%Y-%m-%d %H:%M:%S")
    from matplotlib.gridspec import GridSpec

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g = geqdsk.read_geqdsk(gfile_path)
    profiles = result.get("profiles") or {}
    diags = result.get("diagnostics") or {}
    eb = result.get("errorbars") or {}

    # col-1 stack grows with what the run produced; the flux map then yields its
    # bottom row to the posterior text.
    stack = ["q", "pressure", "ne"]
    if current:
        stack.append("current")
    if neo:
        stack.append("neo")
    rows = max(4, len(stack))
    side = len(stack) > 3          # text under the flux map rather than in col 1

    fig = plt.figure(figsize=(15, 2.25 * rows))
    gs = GridSpec(rows, 3, figure=fig, width_ratios=[1.15, 1.0, 1.0],
                  hspace=0.42, wspace=0.30)

    _flux_map(fig.add_subplot(gs[:rows - 1, 0] if side else gs[:, 0]), g,
              geometry=geometry, diags=diags)

    for row, key in enumerate(stack):
        ax = fig.add_subplot(gs[row, 1])
        if key == "current":
            _current_panel(ax, current)
        elif key == "neo":
            _neo_panel(ax, neo)
        else:
            _band(ax, profiles.get(key),
                  {"q": "tab:green", "pressure": "tab:purple",
                   "ne": "tab:orange"}[key],
                  {"q": "q", "pressure": "p", "ne": r"$n_e$"}[key],
                  {"q": r"$q(\bar\psi)$", "pressure": r"$p$ [Pa]",
                   "ne": r"$n_e$ [$10^{19}$]"}[key])

    # scalar summary with posterior error bars (col-1 bottom, or under the flux
    # map when the col-1 stack has taken that cell)
    ax_txt = fig.add_subplot(gs[rows - 1, 0] if side else gs[3, 1])
    ax_txt.axis("off")

    def _pm(k, sc=1.0, u=""):
        v = result.get(k)
        s = eb.get(k, {}).get("sigma")
        if v is None:
            return f"{k}: —"
        vs = f"{v * sc:.3g}"
        return f"{vs}±{s * sc:.2g}{u}" if s is not None else vs + u
    lines = [
        f"q0 = {_pm('q0')}    q95 = {_pm('q95')}",
        f"Ip = {_pm('ip', 1e-3, ' kA')}   βp = {_pm('betap')}",
        f"li = {_pm('ali')}   W = {_pm('wplasm', 1e-3, ' kJ')}",
        f"χ² = {_pm('chisq')}   n = {result.get('ensemble', {}).get('n', '?')}"
        f" ({result.get('ensemble', {}).get('n_ok', '?')} ok)",
    ]
    ax_txt.text(0.0, 0.95, "posterior (mean ± 1σ)\n" + "\n".join(lines),
                transform=ax_txt.transAxes, va="top", fontsize=9,
                family="monospace")

    order = [k for k in ("mag_probes", "flux_loops", "faraday",
                         "interferometry") if k in diags]
    for row, key in enumerate(order[:4]):
        _diag(fig.add_subplot(gs[row, 2]), diags[key], _DIAG_TITLES[key])

    # geometry provenance: how many channels of each family exist vs were used
    if geometry and rows > 4:
        ax_geo = fig.add_subplot(gs[4, 2])
        ax_geo.axis("off")

        def _n_used(key, n):
            a = (diags.get(key) or {}).get("alive")
            return int(np.count_nonzero(a)) if a is not None and len(a) == n else n
        n_pr = len(geometry.get("probes", {}).get("r", []))
        n_fl = len(geometry.get("flux_loops", {}).get("r", []))
        n_ch = len(geometry.get("point_chords", {}).get("z", []))
        ax_geo.text(
            0.0, 0.95,
            "diagnostic geometry\n"
            f"probes      {_n_used('mag_probes', n_pr):3d}/{n_pr} weighted\n"
            f"flux loops  {_n_used('flux_loops', n_fl):3d}/{n_fl} weighted\n"
            f"POINT chords {n_ch:2d}  (n_e-line + Faraday)\n"
            f"{Path(geometry.get('source', '')).parent.name}/"
            f"{Path(geometry.get('source', '')).name}",
            transform=ax_geo.transAxes, va="top", fontsize=8,
            family="monospace")

    hdr = Path(gfile_path).name
    perturb = result.get("ensemble", {}).get("perturb", [])
    fig.suptitle(f"EAST reconstruction  {hdr}   "
                 f"error bars: {result.get('ensemble', {}).get('n', '?')}-member "
                 f"MC over {'+'.join(perturb) or 'declared'} σ", fontsize=12)
    # build-time stamp (provenance): when this figure was generated
    fig.text(0.995, 0.006, f"built {build_time}", ha="right", va="bottom",
             fontsize=7, color="0.45", family="monospace")
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


def plot_current_components(loop_result: dict, out_path: str | Path, *,
                           dpi: int = 150, title=None, build_time=None) -> str:
    """Plot the self-consistent current decomposition on one figure.

    ``loop_result`` is the dict returned by
    ``oracles.loop.self_consistent`` (the kernel repository) — its ``["current"]`` carries
    ``psin`` and the ``j_ohm`` / ``j_bootstrap`` / ``j_total`` profiles (in
    ⟨j⟩=1 units), plus ``j_nbi`` when a beam backend was selected (K-20).  Draws
    each component and their sum J_total vs ψ_N.
    """
    import datetime as _dt
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if build_time is None:
        build_time = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(build_time, _dt.datetime):
        build_time = build_time.strftime("%Y-%m-%d %H:%M:%S")

    c = loop_result["current"]
    x = np.asarray(c["psin"], dtype=float)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.plot(x, c["j_ohm"], "-o", ms=4, color="tab:blue",
            label=r"$J_\mathrm{ohm}$ (Spitzer $\propto T_e^{1.5}$)")
    ax.plot(x, c["j_bootstrap"], "-s", ms=4, color="tab:red",
            label=r"$J_\mathrm{bootstrap}$ (NEO)")
    j_nbi = np.asarray(c.get("j_nbi") or [], dtype=float)
    total_label = r"$J_\mathrm{total}=J_\mathrm{ohm}+J_\mathrm{bootstrap}$"
    if j_nbi.size == x.size and np.any(j_nbi > 0.0):
        f_nbi = c.get("nbi_fraction")
        ax.plot(x, j_nbi, "-^", ms=4, color="tab:green",
                label=(r"$J_\mathrm{NBI}$ (METIS-class"
                       + (f", $f$={f_nbi:.3f})" if f_nbi else ")")))
        ax.fill_between(x, 0, j_nbi, color="tab:green", alpha=0.12)
        total_label += r"$+J_\mathrm{NBI}$"
    ax.plot(x, c["j_total"], "-", lw=2.2, color="0.2", label=total_label)
    ax.fill_between(x, 0, c["j_bootstrap"], color="tab:red", alpha=0.12)
    f = loop_result.get("bootstrap_fraction")
    r = loop_result.get("result", {})
    ax.set_xlabel(r"$\bar\psi$")
    ax.set_ylabel(r"current density  $J/\langle J\rangle$")
    ax.set_title(title or (f"EAST self-consistent current  "
                 f"(f_bs={f}, q0={r.get('q0', float('nan')):.3f}, "
                 f"{loop_result.get('n_iter', '?')} it)"), fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_ylim(bottom=0)
    fig.text(0.995, 0.005, f"built {build_time}", ha="right", va="bottom",
             fontsize=7, color="0.45", family="monospace")
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)
