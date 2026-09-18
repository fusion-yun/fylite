"""Animate the assembled CFEDR discharge (GIF, Pillow): cross-section · strip charts · profiles.

Usage: python render_gif.py DISCHARGE.json OUT.gif [FPS]
"""
from __future__ import annotations

import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

GROUND, SURFACE, INK, INK2, MUTED, GRID = "#F3F5F7", "#FCFCFB", "#111820", "#4E5966", "#8A95A1", "#DDE2E7"
TE, TI, NE = "#2A78D6", "#EB6834", "#1BAF7A"
COPPER, WALL = "#A86B32", "#5B6570"
FLUX = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf"]
SEGMENTS = [(0.0, 62.0, "ramp-up"), (62.0, 152.0, "flat top"), (6146.0, 6210.0, "ramp-down")]
PHASE_TINT = {"ramp-up": "#E8EEF4", "flat top": "#EEF1EA", "ramp-down": "#F4ECE8"}

TARGET, MODEL, CMD = "#4A3AA7", "#2A78D6", "#4E5966"
plt.rcParams.update({"font.family": ["DejaVu Sans"], "font.size": 8, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "axes.linewidth": 0.8})


def main():
    path, out = sys.argv[1:3]
    fps = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0
    D = json.load(open(path))
    tr = D["traces"]
    t = np.array(tr["t"], float)
    arr = lambda k: np.array([np.nan if v is None else v for v in tr[k]], float)  # noqa: E731
    if D["meta"].get("uniform_dt"):
        #: uniform frames (uniform_json.py): every `stride`-th, so the speed stays constant
        stride = int(sys.argv[4]) if len(sys.argv) > 4 else 1
        frames = D["frames"][::stride]
    else:
        frames = [f for f in D["frames"] if (f["t"] <= 60 and abs(f["t"] % 1.0) < 1e-6) or (60 < f["t"] <= 150 and abs(f["t"] % 6.0) < 1e-6)
                  or f["t"] in (3000.0, 6000.0) or (f["t"] >= 6150 and abs(f["t"] % 1.0) < 1e-6)]
    rho = np.array(D["rho"], float)
    #: profile axes to the data (the 0-D tier stayed under 32 keV / 18e19; the 1.5-D ramp-up does not)
    peak = lambda key: max((v for f in frames for v in f[key] if v is not None), default=1.0)  # noqa: E731
    t_top = max(32.0, 1.08 * max(peak("te"), peak("ti")))
    n_top = max(18.0, 1.08 * peak("ne"))

    fig = plt.figure(figsize=(12.0, 6.75), dpi=80, facecolor=GROUND)
    gs = GridSpec(6, 4, figure=fig, width_ratios=[4.2, 3.0, 1.6, 3.0], height_ratios=[1, 1, 1, 1, 0.42, 2.2],
                  left=0.045, right=0.985, top=0.855, bottom=0.075, wspace=0.08, hspace=0.38)
    ax_x = fig.add_subplot(gs[:, 0])
    rows = [("ip_ma", "Ip  MA", CMD), ("p_aux_mw", "P_aux  MW", CMD), ("p_fus_mw", "P_fus  MW", MODEL), ("w_th_mj", "W_th  MJ", MODEL)]
    strip = [[fig.add_subplot(gs[r, c]) for c in (1, 2, 3)] for r in range(4)]
    ax_te = fig.add_subplot(gs[5, 1:3])
    ax_ne = fig.add_subplot(gs[5, 3])
    title = fig.text(0.035, 0.955, "", fontsize=13, color=INK, fontweight="bold")
    sub = fig.text(0.035, 0.918, "", fontsize=8.5, color=INK2)
    clock = fig.text(0.985, 0.945, "", fontsize=15, color=INK, ha="right", family=["DejaVu Sans Mono"])
    fig.text(0.47, 0.89, "— replay command", fontsize=7.5, color=CMD)
    one_five = D["meta"].get("model") == "1.5-D"
    fig.text(0.60, 0.89, "— 1.5-D transport (replay windows)" if one_five else "— 0-D whole-discharge model",
             fontsize=7.5, color=MODEL)
    if D.get("session"):
        fig.text(0.78, 0.89, "— 1.5-D session (flat-top window)", fontsize=7.5, color=TI)
    fig.text(0.035, 0.89, "— solved LCFS   - - target LCFS   ■ PF coil |I|/Imax", fontsize=7.5, color=INK2)

    # static strip charts
    cursors = []
    for r, (key, label, col) in enumerate(rows):
        y = arr(key)
        top = np.nanmax(y)
        if D.get("session") and key in D["session"]:
            top = max(top, np.nanmax([v for v in D["session"][key] if v is not None]))
        ymax = top * 1.12 if top > 0 else 1.0
        row_c = []
        for c, (a, b, name) in enumerate(SEGMENTS):
            ax = strip[r][c]
            ax.set_facecolor(SURFACE)
            m = (t >= a) & (t <= b)
            ax.plot(t[m], y[m], color=col, lw=1.4)
            if key == "p_fus_mw" and D.get("session") and name == "flat top":
                s = D["session"]
                ax.plot(s["t"], s["p_fus_mw"], color=TI, lw=1.4)
            if key == "w_th_mj" and D.get("session") and name == "flat top":
                s = D["session"]
                ax.plot(s["t"], s["w_th_mj"], color=TI, lw=1.4)
            ax.set_xlim(a, b)
            ax.set_ylim(0, ymax)
            ax.grid(axis="y", color=GRID, lw=0.5)
            ax.tick_params(length=2, labelsize=7)
            if c > 0:
                ax.set_yticklabels([])
            if r < 3:
                ax.set_xticklabels([])
            if r == 0:
                ax.set_title(name, fontsize=8, color=INK2, loc="left")
            if c == 0:
                ax.set_ylabel(label, fontsize=7.5)
            row_c.append(ax.axvline(np.nan, color=INK, lw=0.8))
        cursors.append(row_c)
    strip[3][1].set_xlabel("t  s", fontsize=7.5)

    def miller(s):
        th = np.linspace(0, 2 * np.pi, 121)
        d = np.where(np.sin(th) >= 0, s["delta_upper"], s["delta_lower"])
        return s["r0"] + s["a"] * np.cos(th + np.arcsin(np.clip(d, -0.99, 0.99)) * np.sin(th)), s["kappa"] * s["a"] * np.sin(th)

    def draw(fi):
        f = frames[fi]
        e = D["equilibria"][f["eq"]]
        ax_x.cla()
        ax_x.set_facecolor(SURFACE)
        for c_ in D["coils"]:
            k = D["coils"].index(c_)
            ratio = 0.0
            if e.get("ok") and k < len(e["aturns_ma"]) and c_["i_max_aturn"]:
                ratio = min(1.0, abs(e["aturns_ma"][k] or 0.0) * 1e6 / c_["i_max_aturn"])
            for rc in c_["rects"]:
                ax_x.add_patch(Rectangle((rc["r"] - rc["w"] / 2, rc["z"] - rc["h"] / 2), rc["w"], rc["h"],
                                         facecolor=COPPER, alpha=0.15 + 0.85 * ratio, edgecolor=COPPER, lw=0.8))
        lim = D["limiter"]
        ax_x.plot(lim["r"] + lim["r"][:1], lim["z"] + lim["z"][:1], color=WALL, lw=1.4)
        if e.get("ok"):
            for ln in e["outside"]:
                ax_x.plot(ln["r"], ln["z"], color=MUTED, lw=0.5, ls=(0, (2, 2)))
            for ln in e["inside"]:
                ax_x.plot(ln["r"], ln["z"], color=FLUX[min(8, int(round(ln["level"] * 10)) - 1)], lw=0.8)
            mr, mz = miller(e["asked"])
            ax_x.plot(mr, mz, color=TARGET, lw=1.2, ls=(0, (4, 2)))
            ax_x.plot(e["lcfs"]["r"] + e["lcfs"]["r"][:1], e["lcfs"]["z"] + e["lcfs"]["z"][:1], color=INK, lw=1.8)
            ax_x.plot(*e["axis"], marker="+", color=INK, ms=7)
            if e["xpt"]:
                ax_x.plot(*e["xpt"], marker="x", color=INK, ms=6, mew=1.5)
            state = "diverted" if e["diverted"] else "limited"
            ax_x.text(0.03, 0.02, f"eq t = {e['t']:g} s · {state} · gap rms {e['gap_rms']:.2f} m\n"
                                  f"R0 {e['got']['r0']:.2f} (asked {e['asked']['r0']:.2f}) · κ {e['got']['kappa']:.2f} "
                                  f"(asked {e['asked']['kappa']:.2f})", transform=ax_x.transAxes, fontsize=7, color=INK2)
        ax_x.set_xlim(0.8, 16.2)
        ax_x.set_ylim(-11.2, 11.2)
        ax_x.set_aspect("equal")
        ax_x.set_xlabel("R  m", fontsize=7.5)
        ax_x.set_ylabel("Z  m", fontsize=7.5)
        ax_x.tick_params(length=2, labelsize=7)

        for r in range(4):
            for c, (a, b, _) in enumerate(SEGMENTS):
                x = f["t"] if a <= f["t"] <= b else np.nan
                cursors[r][c].set_xdata([x, x])
        ax_te.cla()
        ax_te.set_facecolor(SURFACE)
        ax_te.plot(rho, f["te"], color=TE, lw=1.8, label="T_e")
        ax_te.plot(rho, f["ti"], color=TI, lw=1.8, label="T_i")
        ax_te.set_xlim(0, 1)
        ax_te.set_ylim(0, t_top)
        ax_te.set_xlabel("ρ_tor,norm", fontsize=7.5)
        ax_te.set_ylabel("T  keV", fontsize=7.5)
        ax_te.grid(color=GRID, lw=0.5)
        ax_te.legend(frameon=False, fontsize=7, loc="upper center", ncol=2)
        ax_te.tick_params(length=2, labelsize=7)
        ax_ne.cla()
        ax_ne.set_facecolor(SURFACE)
        ax_ne.plot(rho, f["ne"], color=NE, lw=1.8)
        ax_ne.set_xlim(0, 1)
        ax_ne.set_ylim(0, n_top)
        ax_ne.set_xlabel("ρ_tor,norm", fontsize=7.5)
        ax_ne.set_ylabel("n_e  1e19 m^-3", fontsize=7.5)
        ax_ne.grid(color=GRID, lw=0.5)
        ax_ne.tick_params(length=2, labelsize=7)
        i = f["i"]
        title.set_text(f"CFEDR d2025 · modelled discharge · {f['phase']}")
        sub.set_text(f"Ip {tr['ip_ma'][i]:.2f} MA · P_aux {tr['p_aux_mw'][i]:.0f} MW · n̄e {tr['ne_bar_19'][i]:.2f}e19 m⁻³ · "
                     f"T_e0 {tr['te0_kev'][i]:.1f} keV · P_fus {tr['p_fus_mw'][i]:.0f} MW · β_N {tr['beta_n'][i]:.2f}")
        clock.set_text(f"t = {f['t']:.1f} s")
        return []

    anim = FuncAnimation(fig, draw, frames=len(frames), blit=False)
    if out.lower().endswith(".mp4"):
        #: H.264 / yuv420p plays everywhere; ffmpeg from $FFMPEG (e.g. imageio-ffmpeg's static binary)
        import os
        from matplotlib.animation import FFMpegWriter
        if os.environ.get("FFMPEG"):
            plt.rcParams["animation.ffmpeg_path"] = os.environ["FFMPEG"]
        anim.save(out, dpi=160, writer=FFMpegWriter(fps=fps, codec="libx264", bitrate=4000,
                                                    extra_args=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]))
    else:
        anim.save(out, writer=PillowWriter(fps=fps))
    print(f"{out}: {len(frames)} frames at {fps:g} fps")


if __name__ == "__main__":
    main()
