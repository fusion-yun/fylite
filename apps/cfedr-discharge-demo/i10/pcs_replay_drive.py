"""PCS I-10 driver: march the CFEDR replay through the public session layer, 10 ms a step.

Inputs: the core chain's first-block case document (kernel `PCS_PLAN_DUMP`) and the kernel's
`docs/cases/pcs/cfedr-d2025-replay.json`.  Commands per step: Ip linear between nodes; the RF
systems (EC groups + IC) held from a node until the next and SUMMED onto the one CASE-20
deposition table (`source_power_0`) — the case binds one aggregate RF table, not one per system.
Geometry stays the case's (CASE-20 flat top); density follows the march's own channel.

★Snapshots (ledger I-21, first cut): every SNAP_EVERY steps a session snapshot goes into a ring of
SNAP_RING (the newest also written to <out>.snap_latest.json); on the first kernel refusal the state
just before the refused step is written to <out>.snap_before_refusal.json; the drive stops after
MAX_REJECTED consecutive rejections.  Restart from a snapshot with a 6th argument (its path).

Usage: python pcs_replay_drive.py PLAN.json REPLAY.json T_FROM T_TO OUT.csv [SNAPSHOT.json]
"""
from __future__ import annotations

import bisect
import collections
import csv
import json
import sys

from fylite.engine import session as S

SNAP_EVERY = 100
SNAP_RING = 5
MAX_REJECTED = 20


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
    base = out_path[:-4] if out_path.endswith(".csv") else out_path
    nodes = json.load(open(replay_path))["nodes"]
    if len(sys.argv) > 6:
        opened = S.restore_session(json.load(open(sys.argv[6])))
        sid, k0 = opened["session"], opened["k_next"]
        t_start = opened["t_start"]
        print(f"restored from {sys.argv[6]} at k {k0} (t {t_start + k0 * S.STEP_S:.2f} s)", flush=True)
    else:
        plan = json.load(open(plan_path))
        sid, k0, t_start = S.open_session(plan, ec_sources=[0], t_start=t_from, require_lcfs_after=1e9)["session"], 0, t_from
    n_end = int(round((t_to - t_start) / S.STEP_S))
    ring = collections.deque(maxlen=SNAP_RING)
    wrote_refusal = False
    streak = 0
    with open(out_path, "a" if k0 else "w", newline="") as fh:
        w = csv.writer(fh)
        if not k0:
            w.writerow(["k", "t", "replay_phase", "ip_cmd", "rf_cmd", "p_fus", "w_th", "te0", "ne0", "ne_mean",
                        "phase", "rejected", "kernel_code", "reason", "calls", "wall_ms"])
        k = k0
        while k < n_end:
            sess = S.sessions[sid]
            if (k - k0) % SNAP_EVERY == 0:
                ring.append(sess.snapshot())
                json.dump(ring[-1], open(base + ".snap_latest.json", "w"))
            cmd, rphase = commands_at(nodes, t_start + k * S.STEP_S)
            out = S.step_session(sid, k, cmd)
            flags = out.get("flags") or {}
            ne = out.get("ne") or []
            w.writerow([k, out.get("t"), rphase, cmd["ip"], cmd["p_ec"][0], out.get("p_fus"), out.get("w_th"),
                        out.get("te0"), ne[0] if ne else None, sum(ne) / len(ne) if ne else None,
                        flags.get("phase"), flags.get("rejected"), out.get("kernel_code"), out.get("reason"),
                        out.get("calls"), round(out["wall_ms"], 3)])
            fh.flush()
            if flags.get("rejected"):
                streak += 1
                if out.get("kernel_code") is not None and not wrote_refusal:
                    #: the session did not advance: its snapshot now IS the state before the refused step
                    json.dump(sess.snapshot(), open(base + ".snap_before_refusal.json", "w"))
                    wrote_refusal = True
                    print(f"k {k} t {t_start + (k + 1) * S.STEP_S:.2f}: kernel refused — snapshot before the refusal written; "
                          f"{out.get('reason')}", flush=True)
                if streak >= MAX_REJECTED:
                    print(f"stopping: {streak} consecutive rejections (last: {out.get('reason')})", flush=True)
                    break
                continue  # a rejected step does not advance k
            streak = 0
            if k % 50 == 0:
                print(f"k {k} t {out.get('t')} p_fus {out.get('p_fus')} wall {out['wall_ms']:.1f} ms", flush=True)
            k += 1
    print(json.dumps(S.close_session(sid)))


if __name__ == "__main__":
    main()
