"""Re-assemble the discharge JSON from the 1.5-D reproduction (ledger I-20 / I-21 replay driver).

Keeps the previous assembly's equilibria, coils, limiter and grid; replaces the 0-D traces and profiles
with the 1.5-D ones, stitched at T_SPLIT: the ramp-up run below it, the flat-top / ramp-down run from it.

Usage: python assemble15.py OLD_DISCHARGE.json RAMPUP.csv FLAT.csv RHO_SNAPSHOT.json T_SPLIT OUT.json
"""
from __future__ import annotations

import bisect
import csv
import json
import math
import sys
from pathlib import Path

A_MINOR = 2.45  # flat-top minor radius [m] (the replay's Miller target), for the Greenwald fraction


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
    old, ramp_csv, flat_csv, snap_path, t_split, out = sys.argv[1:7]
    t_split = float(t_split)
    #: optional MID.csv MID_END: a denser run of the same case over [T_SPLIT, MID_END) (short windows, so a
    #: profile every window end) — rows and profiles there come from it, the flat-top run's from MID_END on
    mid_csv, mid_end = (sys.argv[7], float(sys.argv[8])) if len(sys.argv) > 8 else (None, t_split)
    D = json.loads(Path(old).read_text())

    def rows_of(path, keep):
        return [r for r in csv.DictReader(open(path)) if keep(float(r["t"]))]

    rows = rows_of(ramp_csv, lambda t: t < t_split - 1e-9)
    if mid_csv:
        rows += rows_of(mid_csv, lambda t: t_split - 1e-9 <= t < mid_end - 1e-9)
    rows += rows_of(flat_csv, lambda t: t >= mid_end - 1e-9)
    # thin: ramps every 50 ms, the flat top every 10 s (the flat-top CSV already holds 1 s rows)
    thin, last_t = [], -1e9
    for r in rows:
        t = float(r["t"])
        gap = 0.05 if (t < 70.0 or t > 6145.0) else 10.0
        if t - last_t >= gap - 1e-9 or r is rows[-1]:
            thin.append(r)
            last_t = t
    g = lambda r, k, s=1.0: (None if num(r.get(k)) is None else num(r[k]) / s)  # noqa: E731
    tr = {k: [] for k in ("t", "ip_ma", "p_aux_mw", "ne_bar_19", "f_gw", "te0_kev", "ti0_kev", "p_fus_mw", "q",
                          "w_th_mj", "beta_n", "v_loop", "p_lh_mw", "p_heat_mw", "p_rad_mw", "lh")}
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

    snap = json.loads(Path(snap_path).read_text())
    rho_t = snap["prev"]["fields"]["core_profiles"]["profiles_1d"]["grid"]["rho_tor"]["data"]
    rho = [round(x / rho_t[-1], 4) for x in rho_t]

    def prof_of(path, keep):
        return [p for p in map(json.loads, open(path)) if keep(p["t"])]

    profs = prof_of(ramp_csv + ".profiles.jsonl", lambda t: t < t_split - 1e-9)
    if mid_csv:
        profs += prof_of(mid_csv + ".profiles.jsonl", lambda t: t_split - 1e-9 <= t < mid_end - 1e-9)
    profs += prof_of(flat_csv + ".profiles.jsonl", lambda t: t >= mid_end - 1e-9)
    pt = [p["t"] for p in profs]
    tt = tr["t"]
    eqs = D["equilibria"]
    eq_ok = [k for k, e in enumerate(eqs) if e["ok"]]
    want = sorted(set([round(0.5 * k, 2) for k in range(3, 120)] + list(range(60, 151, 2)) +
                      list(range(500, 6150, 500)) + [round(6150 + 0.5 * k, 2) for k in range(0, 120)]))
    frames = []
    for tw in want:
        j = bisect.bisect_left(pt, tw - 1e-9)
        cand = [k for k in (j - 1, j) if 0 <= k < len(profs)]
        if not cand:
            continue
        k = min(cand, key=lambda q: abs(pt[q] - tw))
        tol = 0.26 if (tw < 65.0 or tw > 6150.0) else 25.0
        if abs(pt[k] - tw) > tol or any(f["t"] == pt[k] for f in frames):
            continue
        p = profs[k]
        i = min(max(bisect.bisect_left(tt, p["t"] - 1e-9), 0), len(tt) - 1)
        same = [q for q in eq_ok if eqs[q]["phase"] == phase_of(p["t"])]
        before = [q for q in same if eqs[q]["t"] <= p["t"] + 1e-9]
        k_eq = before[-1] if before else min(same or eq_ok, key=lambda q: abs(eqs[q]["t"] - p["t"]))
        frames.append({"t": p["t"], "i": i, "eq": k_eq, "phase": phase_of(p["t"]), "lh": p.get("phase"),
                       "te": [r4(x / 1e3, 3) for x in p["te"]], "ti": [r4(x / 1e3, 3) for x in p["ti"]],
                       "ne": [r4(x / 1e19, 3) for x in p["ne"]]})

    D["traces"], D["rho"], D["frames"], D["session"] = tr, rho, frames, None
    D["meta"]["tiers"]["traces_profiles"] = (
        f"1.5-D transport (fylite code/evolve through fylite.engine.pcs_replay: adaptive windows, per-step traces, "
        f"snapshots; ledger I-20 / I-21): ramp-up 1 → {t_split:g} s from a 0-D start state on the CASE-20 case "
        f"(own IPB98(y,2) anchor, density feedback on the replay's line density); flat top and ramp-down "
        f"{t_split:g} s → end from the calibrated CASE-20 fuelled case (I-9 fuelling, L-H martin08)")
    D["meta"]["tiers"]["session"] = None
    D["meta"]["model"] = "1.5-D"
    D["meta"]["t_split"] = t_split
    D["meta"]["t_last"] = tt[-1]
    Path(out).write_text(json.dumps(D, separators=(",", ":")))
    print(f"{out}: {len(tt)} trace points to {tt[-1]:g} s · {len(frames)} frames · rho {len(rho)} · "
          f"{Path(out).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
