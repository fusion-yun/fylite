"""PCS I-10 pilot: march the CFEDR replay through the public session layer, 10 ms a step.

Inputs: the core chain's first-block case document (kernel `PCS_PLAN_DUMP`) and the kernel's
`docs/cases/pcs/cfedr-d2025-replay.json`.  Commands per step: Ip linear between nodes; the RF
systems (EC groups + IC) held from a node until the next and SUMMED onto the one CASE-20
deposition table (`source_power_0`) — the case binds one aggregate RF table, not one per system.
Geometry stays the case's (CASE-20 flat top); density follows the march's own channel.

Usage: python pcs_replay_drive.py PLAN.json REPLAY.json T_FROM T_TO OUT.csv
"""
from __future__ import annotations

import bisect
import csv
import json
import sys

from fylite.engine import session as S


def commands_at(nodes, t):
    ts = [n["t"] for n in nodes]
    k = max(0, bisect.bisect_right(ts, t) - 1)
    a = nodes[k]
    b = nodes[min(k + 1, len(nodes) - 1)]
    if b["t"] > a["t"]:
        ip = a["ip"] + (b["ip"] - a["ip"]) * (t - a["t"]) / (b["t"] - a["t"])
    else:
        ip = a["ip"]
    rf = sum(float(v) for v in (a.get("p_ec") or {}).values()) + float(a.get("p_ic") or 0.0)
    return {"ip": ip, "p_ec": [rf], "synthetic": "synthetic" in (a.get("flags") or [])}, a["phase"]


def main():
    plan_path, replay_path, t_from, t_to, out_path = sys.argv[1:6]
    t_from, t_to = float(t_from), float(t_to)
    plan = json.load(open(plan_path))
    nodes = json.load(open(replay_path))["nodes"]
    sid = S.open_session(plan, ec_sources=[0], t_start=t_from, require_lcfs_after=1e9)["session"]
    n_steps = int(round((t_to - t_from) / S.STEP_S))
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["k", "t", "replay_phase", "ip_cmd", "rf_cmd", "p_fus", "w_th", "te0", "ne0", "ne_mean",
                    "phase", "rejected", "reason", "wall_ms"])
        for k in range(n_steps):
            cmd, rphase = commands_at(nodes, t_from + k * S.STEP_S)
            out = S.step_session(sid, k, cmd)
            ne = out.get("ne") or []
            #: ne_mean is the plain mean over the radial nodes — not volume-weighted, a trend read only
            w.writerow([k, out.get("t"), rphase, cmd["ip"], cmd["p_ec"][0], out.get("p_fus"), out.get("w_th"),
                        out.get("te0"), ne[0] if ne else None, sum(ne) / len(ne) if ne else None,
                        (out.get("flags") or {}).get("phase"), (out.get("flags") or {}).get("rejected"),
                        out.get("reason"), round(out["wall_ms"], 3)])
            fh.flush()
            if k % 50 == 0:
                print(f"k {k} t {out.get('t')} p_fus {out.get('p_fus')} wall {out['wall_ms']:.1f} ms "
                      f"rejected {(out.get('flags') or {}).get('rejected')} {out.get('reason') or ''}", flush=True)
    print(json.dumps(S.close_session(sid)))


if __name__ == "__main__":
    main()
