"""0-D whole-discharge run of the CFEDR d2025 replay (kernel `code/zerod`), three passes.

Waveforms are the replay's own, bound on one time base (dense in the ramps, sparse on the flat top):
Ip linear between nodes; auxiliary power = EC groups + IC (+ NBI + LH, zero here) held from a node to
the next; line-averaged density linear.  The door takes the AXIS density, so
  pass 0  evaluate with n_e,axis = n̄_e (placeholder T_e)       -> the door's own n̄_e / n_e,axis ratio
  pass 1  predict (tier B, IPB98(y,2)) with the rescaled axis density -> T_e0(t)
  pass 2  evaluate + criteria with T_e,axis = predicted T_e0     -> traces, criteria, 1-D profiles
Scalars: the flat-top shape (r0 7.87, a 2.45, kappa 1.90; the 0-D door takes one shape), B0 from the
CASE-20 equilibrium (6.3 T at 7.8 m, scaled to r0), Z_eff from the CASE-20 case document.

Usage: python zerod_run.py PLAN.json REPLAY.json OUT.npz
"""
from __future__ import annotations

import bisect
import json
import sys

import numpy as np

from fylite.io import fydoc

S = "summary/"
ROWS = {"ip": S + "global_quantities/ip/value", "ne_axis": S + "local/magnetic_axis/n_e/value",
        "te_axis": S + "local/magnetic_axis/t_e/value", "p_aux": S + "heating_current_drive/power_additional/value"}


def nested(flat: dict) -> dict:
    out: dict = {}
    for path, v in flat.items():
        node = out
        parts = path.split("/")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = v
    return out


def fields(rec, prefix=""):
    out = {}
    for k, v in rec.items():
        if isinstance(v, dict) and "data" in v:
            out[prefix + k] = np.asarray(v["data"], float)
        elif isinstance(v, dict):
            out.update(fields(v, prefix + k + "/"))
    return out


def main():
    plan_path, replay_path, out_path = sys.argv[1:4]
    plan = json.load(open(plan_path))
    nodes = json.load(open(replay_path))["nodes"]
    ts = np.array([n["t"] for n in nodes])
    time = np.unique(np.concatenate([np.arange(0.0, 60.0, 0.25), np.arange(60.0, 150.0, 1.0),
                                     np.arange(150.0, 6150.0, 50.0), np.arange(6150.0, 6209.51, 0.25)]))
    ip = np.interp(time, ts, [n["ip"] for n in nodes])
    ne_bar = np.interp(time, ts, [n["ne_bar"] for n in nodes])
    rf = [sum(float(v) for v in (n.get("p_ec") or {}).values()) + float(n.get("p_ic") or 0.0)
          + float(n.get("p_nbi") or 0.0) + float(n.get("p_lh") or 0.0) for n in nodes]
    p_aux = np.array([rf[max(0, bisect.bisect_right(list(ts), t) - 1)] for t in time])
    r0, b0_ref, r_ref = 7.87, 6.3, 7.8
    base = {"r0": r0, "a": 2.45, "kappa": 1.9, "bt": b0_ref * r_ref / r0, "zeff": float(plan["settings"]["zeff"])}
    #: optional overrides (a JSON object as the 4th argument), e.g. {"tite": 0.80, "hfac": 0.8}
    if len(sys.argv) > 4:
        base.update(json.loads(sys.argv[4]))

    def run(stage, extra, ne_axis, te_axis):
        wave = {"time": time, ROWS["ip"]: ip, ROWS["ne_axis"]: ne_axis, ROWS["p_aux"]: p_aux}
        if te_axis is not None:
            wave[ROWS["te_axis"]] = te_axis
        return fydoc.complete("code/zerod", {"settings": {**base, "stage": stage, **extra},
                                             "inputs": nested({"summary/" + k if k == "time" else k: v.tolist()
                                                               for k, v in wave.items()})})

    r0rec = run("evaluate", {"criteria": 1.0}, ne_bar, np.full_like(time, 1.0e3))
    f0 = fields(r0rec["fields"])
    ratio = np.where(f0["criteria_ne_bar"] > 0, ne_bar / np.maximum(f0["criteria_ne_bar"], 1.0), 1.0)
    ne_axis = ne_bar * ratio
    r1 = run("predict", {}, ne_axis, None)
    te0 = fields(r1["fields"])["prediction_te0"] * 1e3  # keV -> eV
    r2 = run("evaluate", {"criteria": 1.0, "predict": 1.0}, ne_axis, np.maximum(te0, 10.0))
    f2 = fields(r2["fields"])
    facts = {k: v["value"] for k, v in r2["facts"].items()}
    np.savez_compressed(out_path, time=time, ip_cmd=ip, ne_bar_cmd=ne_bar, p_aux_cmd=p_aux, ne_axis_cmd=ne_axis,
                        te_axis_used=te0, facts=json.dumps(facts), notes=json.dumps(r2.get("notes", [])),
                        base=json.dumps(base), **{k.replace("/", "__"): v for k, v in f2.items()})
    pf = f2.get("p_fus", f2.get("summary/fusion/power/value"))
    for t in (10, 30, 60, 100, 150, 3000, 6150, 6170, 6200):
        i = int(np.argmin(abs(time - t)))
        print(f"t {time[i]:7.1f} s · Ip {ip[i]/1e6:5.2f} MA · P_aux {p_aux[i]/1e6:5.1f} MW · n̄e {ne_bar[i]/1e19:5.2f}e19 · "
              f"Te0 {te0[i]/1e3:6.2f} keV · P_fus {pf[i]/1e6:7.1f} MW · W_th {f2['criteria_w_th'][i]/1e6:6.1f} MJ · "
              f"beta_N {f2['criteria_beta_n'][i]:.2f} · f_GW {f2['criteria_f_greenwald'][i]:.2f}")
    print("facts", facts)
    print("notes", r2.get("notes", [])[:5])


if __name__ == "__main__":
    main()
