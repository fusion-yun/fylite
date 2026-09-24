"""PCS adaptive-step planning probe on the CFEDR fuelled case (code/evolve through the public door).

M1  kernel calls per 10 ms step through the session (patched session counts them)
M2  10 resumed one-step calls of 10 ms vs one call of 10 steps of 10 ms: wall and end state
M3  one call with the kernel's controller free to grow dt (dttarget 0.2 s) over ~2 s: dt taken,
    exchange cap, wall, end state vs the fixed 10 ms reference CSV
M4  resume on the BOUND ladder (geometry = ladder, the record's own ladder rows) vs the g-file trace

Usage: python step_probe.py PLAN.json REFERENCE.csv
"""
from __future__ import annotations

import csv
import json
import sys
import time

import numpy as np

from fylite.engine import session as S
from fylite.io import fydoc

ALPHA = 3.518 / 17.589


def fact(rec, k, default=float("nan")):
    return float(rec["facts"][k]["value"]) if k in rec["facts"] else default


def summary(rec):
    F = rec["fields"]
    pa = (F.get("summary", {}).get("fusion", {}).get("power", {}).get("value", {}) or {}).get("data") or []
    cp = F["core_profiles"]["profiles_1d"]
    return {"t": fact(rec, "t_end"), "p_fus_mw": (float(pa[-1]) / ALPHA / 1e6) if len(pa) else fact(rec, "p_fus") / 1e6,
            "w_th_mj": fact(rec, "w_th") / 1e6, "te0_kev": float(cp["electrons"]["temperature"]["data"][0]) / 1e3}


def main():
    plan_path, ref_path = sys.argv[1:3]
    plan = json.load(open(plan_path))
    ref = {round(float(r["t"]), 2): r for r in csv.DictReader(open(ref_path))}

    # ---- M1: calls per 10 ms step through the session ----------------------------------------
    sid = S.open_session(plan, ec_sources=[0], t_start=0.0, require_lcfs_after=1e9)["session"]
    calls, walls = [], []
    for k in range(20):
        out = S.step_session(sid, k, {"ip": 15e6, "p_ec": [102e6]})
        calls.append(out["calls"])
        walls.append(out["wall_ms"])
    sess = S.sessions[sid]
    rec10 = sess.prev
    summ = S.close_session(sid)
    print(f"M1 session 20 × 10 ms: calls per step {sorted(set(calls))} · wall p50 {np.median(walls):.0f} ms · "
          f"kernel_calls {summ['kernel_calls']} · dt_capped {fact(rec10, 'dt_capped')} · dt_next {fact(rec10, 'dt_next'):.4g} s")

    base = dict(plan["settings"], globals=1.0, source_power_0=102e6)

    # ---- M2: one call of 10 steps vs 10 calls of one step ----------------------------------------
    st = dict(base, dt=0.01, nsteps=10.0, dttarget=0.0)
    c = time.perf_counter()
    one = fydoc.complete("code/evolve", {"settings": st, "inputs": plan["inputs"]})
    w_one = (time.perf_counter() - c) * 1e3
    a = summary(one)
    print(f"M2 one call × 10 steps: wall {w_one:.0f} ms · t {a['t']:.4f} · P_fus {a['p_fus_mw']:.1f} MW · W_th {a['w_th_mj']:.1f} MJ · "
          f"(10 session calls at ~{np.median(walls):.0f} ms each ≈ {10 * np.median(walls):.0f} ms; session state at 0.10 s P_fus via M1 run)")

    # ---- M3: controller free to grow dt ------------------------------------------------------------
    for target in (0.05, 0.2):
        st = dict(base, dt=0.01, nsteps=200.0, dttarget=target)
        c = time.perf_counter()
        rec = fydoc.complete("code/evolve", {"settings": st, "inputs": plan["inputs"]})
        w = (time.perf_counter() - c) * 1e3
        dts = np.asarray((rec["fields"].get("dt_used") or {}).get("data") or [], float)
        s3 = summary(rec)
        t_end = s3["t"]
        ref_row = ref.get(round(65.0 + round(t_end / 0.01) * 0.01, 2))
        cmp = ""
        if ref_row:
            cmp = (f" · ref@{65 + t_end:.2f}s P_fus {float(ref_row['p_fus']) / 1e6:.1f} MW W_th {float(ref_row['w_th']) / 1e6:.1f} MJ "
                   f"Te0 {float(ref_row['te0']) / 1e3:.2f} keV")
        print(f"M3 dttarget {target}: {len(dts)} steps to t {t_end:.3f} s · dt min/median/max {dts.min() if len(dts) else float('nan'):.4g}/"
              f"{np.median(dts) if len(dts) else float('nan'):.4g}/{dts.max() if len(dts) else float('nan'):.4g} s · capped {fact(rec, 'dt_capped')} · "
              f"wall {w:.0f} ms ({w / max(t_end, 1e-9) / 100:.1f} ms per 10 ms simulated) · P_fus {s3['p_fus_mw']:.1f} MW · "
              f"W_th {s3['w_th_mj']:.1f} MJ · Te0 {s3['te0_kev']:.2f} keV{cmp}")

    # ---- M4: resume on the bound ladder -------------------------------------------------------------
    eq_rows = rec10["fields"].get("equilibrium")
    if eq_rows is None:
        print("M4: the record carries no equilibrium ladder rows — nothing to bind")
        return
    st, inp = S.Session(plan, ec_sources=[0])._resume(dict(base, dttarget=0.0, nsteps=1.0), rec10, 0.01)
    for geo, label in (("gfile", "g-file trace"), ("ladder", "bound ladder")):
        s4 = dict(st, geometry=geo)
        i4 = dict(inp)
        if geo == "ladder":
            i4["equilibrium"] = {k: v for k, v in eq_rows.items()}
        c = time.perf_counter()
        try:
            r4 = fydoc.complete("code/evolve", {"settings": s4, "inputs": i4})
            w4 = (time.perf_counter() - c) * 1e3
            s = summary(r4)
            print(f"M4 {label}: wall {w4:.0f} ms · t {s['t']:.4f} · P_fus {s['p_fus_mw']:.2f} MW · W_th {s['w_th_mj']:.2f} MJ · Te0 {s['te0_kev']:.3f} keV")
        except Exception as e:  # a refusal is the reading
            print(f"M4 {label}: refused after {(time.perf_counter() - c) * 1e3:.0f} ms — {str(e)[:300]}")


if __name__ == "__main__":
    main()
