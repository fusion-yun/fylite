"""Assemble the discharge JSON: 0-D tier outside [T_HAND, T_BACK], continuous 1.5-D transport inside it.

Why the hand-overs (2026-09-14/15): the 1.5-D march runs on the CASE-20 flat-top geometry (1539 m^3).  The
free-boundary sequence gives the plasma 30 % of that volume at 1 s and 70 % at 30 s; only from the diverted
40 s point (I_p 10 MA) is it within ~10 %.  The ramp-down mirrors it: below 10 MA (6170 s) the volume falls back
to 81-31 % and the configuration returns to the limiter, and every 1.5-D ramp-down branch was refused there.
So 1 -> T_HAND and T_BACK -> end keep the literature-calibrated 0-D tier (code/zerod); T_HAND -> T_BACK is ONE
1.5-D march started from the 0-D state at T_HAND.

Keeps the previous assembly's equilibria, coils, limiter and grid.  0-D keyframes are re-gridded onto the
1.5-D rho ladder.  Output frames are keyframes; run uniform_json.py afterwards for constant playback speed.

Usage: python assemble_hybrid.py ZEROD_DISCHARGE.json RUN15.csv RHO_SNAPSHOT.json T_HAND OUT.json [T_BACK]
"""
from __future__ import annotations

import bisect
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

A_MINOR = 2.45
KEYS = ("t", "ip_ma", "p_aux_mw", "ne_bar_19", "f_gw", "te0_kev", "ti0_kev", "p_fus_mw", "q", "w_th_mj",
        "beta_n", "v_loop", "p_lh_mw", "p_heat_mw", "p_rad_mw", "lh", "tier")


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def r4(v, nd=4):
    return None if v is None else float(f"{v:.{nd}g}")


def phase_of(t):
    return "ramp-up" if t < 60.0 else ("flat top" if t < 6150.0 else "ramp-down")


def main():
    zd_path, run_csv, snap_path, t_hand, out = sys.argv[1:6]
    t_hand = float(t_hand)
    t_back = float(sys.argv[6]) if len(sys.argv) > 6 else math.inf
    D = json.loads(Path(zd_path).read_text())
    Z = D["traces"]
    tite = D["meta"]["zerod_settings"].get("tite", 0.8)
    snap = json.loads(Path(snap_path).read_text())
    rho_t = snap["prev"]["fields"]["core_profiles"]["profiles_1d"]["grid"]["rho_tor"]["data"]
    rho = [round(x / rho_t[-1], 4) for x in rho_t]
    inside = lambda t: t_hand - 1e-9 <= t < t_back - 1e-9  # noqa: E731

    tr = {k: [] for k in KEYS}

    def add_zerod(i):
        t = Z["t"][i]
        for k in KEYS:
            if k == "t":
                tr[k].append(t)
            elif k == "tier":
                tr[k].append("0d")
            elif k == "ti0_kev":
                te = Z["te0_kev"][i]
                tr[k].append(None if te is None else r4(te * tite))
            else:
                tr[k].append(Z[k][i] if k in Z else None)

    for i, t in enumerate(Z["t"]):
        if t < t_hand - 1e-9:
            add_zerod(i)

    rows = [r for r in csv.DictReader(open(run_csv)) if inside(float(r["t"]))]
    thin, last_t = [], -1e9
    for r in rows:
        t = float(r["t"])
        gap = 0.05 if (t < 70.0 or t > 6145.0) else 10.0
        if t - last_t >= gap - 1e-9 or r is rows[-1]:
            thin.append(r)
            last_t = t
    g = lambda r, k, s=1.0: (None if num(r.get(k)) is None else num(r[k]) / s)  # noqa: E731
    for r in thin:
        ip, pa, ne, pf = g(r, "ip_cmd", 1e6), g(r, "rf_cmd", 1e6), g(r, "ne_bar_cmd"), g(r, "p_fus", 1e6)
        tr["t"].append(round(float(r["t"]), 3))
        tr["ip_ma"].append(r4(ip))
        tr["p_aux_mw"].append(r4(pa))
        tr["ne_bar_19"].append(r4(None if ne is None else ne / 1e19))
        tr["f_gw"].append(r4(None if not (ne and ip) else (ne / 1e20) / (ip / (math.pi * A_MINOR ** 2))))
        tr["te0_kev"].append(r4(g(r, "te0", 1e3)))
        tr["ti0_kev"].append(r4(g(r, "ti0", 1e3)))
        tr["p_fus_mw"].append(r4(pf))
        tr["q"].append(r4(None if not (pf is not None and pa) else pf / pa))
        tr["w_th_mj"].append(r4(g(r, "w_th", 1e6)))
        tr["beta_n"].append(r4(g(r, "beta_n")))
        tr["v_loop"].append(r4(g(r, "v_loop")))
        tr["p_lh_mw"].append(r4(g(r, "p_lh", 1e6)))
        tr["p_heat_mw"].append(r4(g(r, "p_sep", 1e6)))
        tr["p_rad_mw"].append(r4(g(r, "p_rad", 1e6)))
        tr["lh"].append(g(r, "lh_phase"))
        tr["tier"].append("1.5d")

    for i, t in enumerate(Z["t"]):
        if t >= t_back - 1e-9:
            add_zerod(i)

    zr = np.asarray(D["rho"], float)
    tt = tr["t"]
    eqs = D["equilibria"]
    eq_ok = [k for k, e in enumerate(eqs) if e["ok"]]

    def eq_for(t):
        same = [q for q in eq_ok if eqs[q]["phase"] == phase_of(t)]
        before = [q for q in same if eqs[q]["t"] <= t + 1e-9]
        return before[-1] if before else min(same or eq_ok, key=lambda q: abs(eqs[q]["t"] - t))

    def idx(t):
        i = bisect.bisect_left(tt, t)
        return min(range(max(i - 1, 0), min(i + 1, len(tt) - 1) + 1), key=lambda q: abs(tt[q] - t))

    regrid = lambda a: [r4(float(v), 3) for v in np.interp(rho, zr, np.asarray([np.nan if x is None else x for x in a], float))]  # noqa: E731
    frames = []
    for f in D["frames"]:
        if not inside(f["t"]):
            frames.append({"t": f["t"], "i": idx(f["t"]), "eq": eq_for(f["t"]), "phase": phase_of(f["t"]), "tier": "0d",
                           "te": regrid(f["te"]), "ti": regrid(f["ti"]), "ne": regrid(f["ne"])})
    for p in map(json.loads, open(run_csv + ".profiles.jsonl")):
        if not inside(p["t"]) or any(abs(f["t"] - p["t"]) < 1e-9 for f in frames):
            continue
        frames.append({"t": p["t"], "i": idx(p["t"]), "eq": eq_for(p["t"]), "phase": phase_of(p["t"]), "tier": "1.5d",
                       "lh": p.get("phase"), "te": [r4(x / 1e3, 3) for x in p["te"]],
                       "ti": [r4(x / 1e3, 3) for x in p["ti"]], "ne": [r4(x / 1e19, 3) for x in p["ne"]]})
    frames.sort(key=lambda f: f["t"])

    back = "" if math.isinf(t_back) else f"; from {t_back:g} s (I_p 10 MA, back below ~87 % of the flat-top volume) the 0-D tier again"
    D["traces"], D["rho"], D["frames"], D["session"] = tr, rho, frames, None
    D["meta"]["tiers"]["traces_profiles"] = (
        f"0-D tier (code/zerod, IPB98(y,2) tier B, parametric profiles) 1 -> {t_hand:g} s; from {t_hand:g} s one "
        f"continuous 1.5-D transport march (code/evolve through fylite.engine.pcs_replay: adaptive windows, "
        f"per-step traces, snapshots) started from the 0-D state — current-consistent flux, I_p feedback loop, "
        f"IPB98 anchor seeded from the calibrated flat top, Z_eff 1.8, edge density following the replay's line density{back}")
    D["meta"]["tiers"]["session"] = None
    D["meta"]["model"] = "1.5-D"
    D["meta"]["t_hand"] = t_hand
    D["meta"]["t_split"] = t_hand
    D["meta"]["t_back"] = None if math.isinf(t_back) else t_back
    D["meta"]["t_last"] = tt[-1]
    Path(out).write_text(json.dumps(D, separators=(",", ":")))
    n0 = sum(1 for x in tr["tier"] if x == "0d")
    print(f"{out}: {len(tt)} trace points ({n0} 0-D) to {tt[-1]:g} s · {len(frames)} keyframes · rho {len(rho)} · "
          f"{Path(out).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
