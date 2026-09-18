"""Assemble the discharge modelling output into one compact JSON for the animation and the page.

Usage: python assemble.py EQ_DIR ZEROD.npz DEVICE.json SESSION.csv OUT.json
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from device_geom import coils as card_coils  # noqa: E402

LEVELS_IN = [round(0.1 * k, 2) for k in range(1, 10)]
LEVELS_OUT = [1.08, 1.2, 1.4]


def r4(x, nd=4):
    """Round to `nd` significant digits for a compact JSON (NaN -> None)."""
    a = np.asarray(x, float)
    out = []
    for v in a.ravel():
        out.append(None if not np.isfinite(v) else float(f"{v:.{nd}g}"))
    return out


def contours(r, z, psin, levels):
    fig = plt.figure()
    cs = plt.contour(r, z, psin.T, levels=levels)
    lines = []
    for lev, segs in zip(cs.levels, cs.allsegs):
        for seg in segs:
            if len(seg) < 4:
                continue
            step = max(1, len(seg) // 120)
            pts = seg[::step]
            lines.append({"level": float(lev), "r": [round(float(p[0]), 3) for p in pts],
                          "z": [round(float(p[1]), 3) for p in pts]})
    plt.close(fig)
    return lines


def phase_of(t):
    return "ramp-up" if t < 60.0 else ("flat top" if t < 6150.0 else "ramp-down")


def main():
    eq_dir, zerod_path, dev_path, session_csv, out_path = sys.argv[1:6]
    eq_dir = Path(eq_dir)
    index = json.load(open(eq_dir / "index.json"))
    eqs = []
    lim = None
    grid = None
    for e in index:
        if not e.get("ok"):
            eqs.append({"t": e["t"], "ok": False, "error": e.get("error", "")[:200], "phase": phase_of(e["t"])})
            continue
        d = np.load(eq_dir / f"eq_{e['t']:08.2f}.npz")
        fc = e["facts"]
        r, z, psi = d["r"], d["z"], d["psi"]
        span = fc["psi_bnd"] - fc["psi_axis"]
        psin = (psi - fc["psi_axis"]) / span
        if lim is None:
            lim = {"r": r4(d["lim_r"]), "z": r4(d["lim_z"])}
            grid = {"rmin": float(r[0]), "rmax": float(r[-1]), "zmin": float(z[0]), "zmax": float(z[-1])}
        step = max(1, len(d["bnd_r"]) // 90)
        eqs.append({
            "t": e["t"], "ok": True, "phase": phase_of(e["t"]), "replay_phase": e["phase"],
            "ip": e["ip"], "asked": {k: round(e[k], 4) for k in ("r0", "a", "kappa", "delta_upper", "delta_lower")},
            "asked_config": e.get("configuration"), "synthetic": e.get("synthetic", False),
            "diverted": int(fc["bnd_kind"]) == 1,
            "got": {"r0": fc["shape_r0"], "a": fc["shape_a"], "kappa": fc["shape_kappa"],
                    "delta_upper": fc["shape_delta_upper"], "delta_lower": fc["shape_delta_lower"]},
            "gap_rms": fc["boundary_gap_rms"], "gap_max": fc["boundary_gap_max"],
            "axis": [fc["axis_r"], fc["axis_z"]],
            "xpt": [fc["xpt_r"], fc["xpt_z"]] if int(fc["bnd_kind"]) == 1 else None,
            "coil_ratio": fc["coil_limit_ratio"], "n_at_limit": fc["n_at_coil_limit"],
            "aturns_ma": r4(d["aturns"] / 1e6),
            "lcfs": {"r": r4(d["bnd_r"][::step]), "z": r4(d["bnd_z"][::step])},
            "inside": contours(r, z, psin, LEVELS_IN), "outside": contours(r, z, psin, LEVELS_OUT),
        })

    zd = np.load(zerod_path, allow_pickle=False)
    t = zd["time"]
    traces = {
        "t": r4(t, 7),
        "ip_ma": r4(zd["ip_cmd"] / 1e6), "p_aux_mw": r4(zd["p_aux_cmd"] / 1e6),
        "ne_bar_19": r4(zd["criteria_ne_bar"] / 1e19), "f_gw": r4(zd["criteria_f_greenwald"]),
        "te0_kev": r4(zd["summary__local__magnetic_axis__t_e__value"] / 1e3),
        #: the door's own `p_fus` field: total fusion power (its summary/fusion/power row reads ~1/5 of it)
        "p_fus_mw": r4(zd["p_fus"] / 1e6),
        "q": r4(zd["summary__global_quantities__fusion_gain__value"]),
        "w_th_mj": r4(zd["criteria_w_th"] / 1e6), "beta_n": r4(zd["criteria_beta_n"]),
        "v_loop": r4(zd["summary__global_quantities__v_loop__value"]),
        "p_lh_mw": r4(zd["criteria_p_lh"] / 1e6), "p_heat_mw": r4(zd["criteria_p_heat"] / 1e6),
    }
    rho = zd["core_profiles__profiles_1d__grid__rho_tor_norm"]
    te = zd["core_profiles__profiles_1d__electrons__temperature"]
    ti = zd["core_profiles__profiles_1d__t_i_average"]
    ne = zd["core_profiles__profiles_1d__electrons__density"]

    # frames: ramp-up every 0.5 s, flat top 60-150 s every 2 s then every 500 s, ramp-down every 0.5 s
    want = np.unique(np.concatenate([np.arange(0.5, 60.0, 0.5), np.arange(60.0, 150.01, 2.0),
                                     np.arange(500.0, 6150.0, 500.0), np.arange(6150.0, 6209.51, 0.5)]))
    eq_ok = [k for k, e in enumerate(eqs) if e["ok"]]
    frames = []
    for tw in want:
        i = int(np.argmin(abs(t - tw)))
        # the equilibrium shown: the latest solved one at or before this time within the same phase,
        # else the nearest solved one
        same = [k for k in eq_ok if eqs[k]["phase"] == phase_of(t[i])]
        before = [k for k in same if eqs[k]["t"] <= t[i] + 1e-9]
        k_eq = before[-1] if before else (min(same or eq_ok, key=lambda k: abs(eqs[k]["t"] - t[i])))
        frames.append({"t": float(t[i]), "i": i, "eq": k_eq, "phase": phase_of(t[i]),
                       "te": r4(te[i] / 1e3, 3), "ti": r4(ti[i] / 1e3, 3), "ne": r4(ne[i] / 1e19, 3)})

    session = None
    if Path(session_csv).exists():
        rows = [r for r in csv.DictReader(open(session_csv)) if r["rejected"] != "True"]
        rows = rows[::10] + rows[-1:]
        session = {"t": [float(r["t"]) for r in rows], "p_fus_mw": r4([float(r["p_fus"]) / 1e6 for r in rows]),
                   "w_th_mj": r4([float(r["w_th"]) / 1e6 for r in rows]),
                   "te0_kev": r4([float(r["te0"]) / 1e3 for r in rows])}

    base = json.loads(str(zd["base"]))
    out = {
        "meta": {
            "machine": "CFEDR", "design": "d2025 · 15 MA conventional H-mode",
            "replay": "fylite_kernel docs/cases/pcs/cfedr-d2025-replay.json (DRAFT v0.1; ramp-down nodes synthetic)",
            "b0": 6.3, "r_b0": 7.8,
            "tiers": {
                "equilibrium": "free-boundary per sample time: fylite code/discharge, position control C4, card coil ratings (104014 Table 1); Miller target + Ip from the replay",
                "traces_profiles": "0-D whole discharge: fylite code/zerod — tier B (IPB98(y,2)) predicts axis T_e, prescribed tier gives parametric profiles; Ip, line-averaged density, auxiliary power from the replay",
                "session": "1.5-D session on the CASE-20 case (code/evolve per 10 ms, I-9 fuelling, L-H martin08), burn window only",
            },
            "zerod_settings": base,
        },
        "grid": grid, "limiter": lim, "coils": card_coils(dev_path),
        "equilibria": eqs, "rho": r4(rho[0], 3), "traces": traces, "frames": frames, "session": session,
    }
    Path(out_path).write_text(json.dumps(out, separators=(",", ":")))
    print(f"{out_path}: {len(eqs)} equilibria ({len(eq_ok)} solved) · {len(frames)} frames · "
          f"{len(t)} trace points · {Path(out_path).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
