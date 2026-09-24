"""Free-boundary equilibrium sequence along the CFEDR d2025 replay (code/discharge + C4).

Each sample time takes the replay's Miller LCFS and Ip, interpolated linearly per parameter between
nodes (the replay file's own `interpolation` rule), and solves under position control C4 with the
card's coil ratings (F-9).  Output: one .npz per sample + index.json (per-slice `wall_s`, `warm`).

Cold (the default): every slice designs its own start (seed "target").  `--warm`: a slice starts from
the PREVIOUS successful slice — its coil currents bound as `discharge/fylite:channel_aturns` and its
box flux as `discharge/fylite:psi_warm`, setting `warm = 1`, seed "flux_max" (the door reads
`psi_warm` only under that seed; under "target" it would be ignored).  The anneal still runs its
passes (`--warm-passes` to change that).  A warm slice the door refuses is solved again cold (both
attempts in its `wall_s`); a slice after a refused one, and a slice more than `--warm-max-gap`
seconds after the previous one (the replay's phase jumps), is solved cold.

Usage: python eq_sequence.py DEVICE.json REPLAY.json OUT_DIR [--warm [--warm-max-gap S] [--warm-seed SEED] [--warm-passes N]]
"""
from __future__ import annotations

import argparse
import bisect
import json
import time
from pathlib import Path

import numpy as np

from fylite.io import fydoc

TIMES = ([1, 3, 5, 7.5, 10, 13, 17, 20, 25, 30, 35, 40, 45, 50, 55, 60]       # ramp-up
         + [65, 100, 150]                                                    # flat top / burn
         + [6150, 6155, 6160, 6165, 6170, 6180, 6193, 6200, 6205, 6209])     # ramp-down
KEYS = ("r0", "a", "kappa", "delta_upper", "delta_lower", "z0")


def interp_node(nodes, t):
    ts = [n["t"] for n in nodes]
    k = max(0, bisect.bisect_right(ts, t) - 1)
    a, b = nodes[k], nodes[min(k + 1, len(nodes) - 1)]
    la, lb = a.get("lcfs") or {}, (b.get("lcfs") or a.get("lcfs") or {})
    u = 0.0 if b["t"] == a["t"] else (t - a["t"]) / (b["t"] - a["t"])
    lin = lambda x, y: x + (y - x) * u  # noqa: E731
    shape = {k2: lin(float(la.get(k2, 0.0)), float(lb.get(k2, la.get(k2, 0.0)))) for k2 in KEYS}
    return {"t": t, "phase": a["phase"], "ip": lin(a["ip"], b["ip"]), "ne_bar": lin(a["ne_bar"], b["ne_bar"]),
            "configuration": la.get("configuration"), "synthetic": "synthetic" in (a.get("flags") or []),
            **shape}


def field(rec, path):
    node = rec["fields"]
    for part in path.split("/"):
        node = node[part]
    return np.asarray(node["data"], float)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("device"); ap.add_argument("replay"); ap.add_argument("out")
    ap.add_argument("--warm", action="store_true", help="start each slice from the previous slice's solution")
    ap.add_argument("--warm-max-gap", type=float, default=float("inf"),
                    help="solve cold when the previous slice is more than this many seconds back")
    ap.add_argument("--warm-seed", default="flux_max", choices=("flux_max", "target"),
                    help="seed rule for warm slices (flux_max: from psi_warm; target: currents only)")
    ap.add_argument("--warm-passes", type=int, default=None,
                    help="anneal passes on warm slices (default: the door's own, 8)")
    a = ap.parse_args()
    dev_path, replay_path, out = a.device, a.replay, a.out
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    dev = json.load(open(dev_path))
    nodes = json.load(open(replay_path))["nodes"]
    #: ★the card's coil ratings bound on the plan explicitly: the Python door rides the public runtime,
    #: whose embedded kernel may predate F-9 (card read by default) — measured: coil_limits 0 unbound
    ratings = [float(c["fylite:i_max_aturn"]) for c in dev["pf_active"]["coil"]
               if not any((f or {}).get("name") == "b_field_fb" for f in (c.get("function") or []))]
    index = []
    prev = None  #: (t, aturns, box psi) of the last successful slice — the warm hand-over

    def solve(n, hand_over):
        st = {k2: n[k2] for k2 in KEYS}
        st.update(ip=n["ip"], relax=0.1, position_control="c4", seed="target")
        disc = {"fylite:i_max_aturn": ratings}
        if hand_over:
            st.update(warm=1, seed=a.warm_seed)
            if a.warm_passes is not None:
                st["passes"] = a.warm_passes
            disc["fylite:channel_aturns"], disc["fylite:psi_warm"] = hand_over
        return fydoc.complete("code/discharge", {"settings": st, "inputs": {"device": dev, "discharge": disc}})

    for t in TIMES:
        n = interp_node(nodes, float(t))
        warm = bool(a.warm and prev is not None and float(t) - prev[0] <= a.warm_max_gap)
        extra = {}
        clock = time.time()
        try:
            rec = solve(n, prev[1:] if warm else None)
        except Exception as e:
            if not warm:  # a refusal is a reading, kept in the index; the next slice starts cold
                index.append({**n, "ok": False, "warm": False, "error": str(e)[:300], "wall_s": time.time() - clock})
                print(f"t {t}: REFUSED {str(e)[:160]}", flush=True)
                prev = None
                continue
            #: a refused warm slice is solved again cold; both attempts count in its wall time
            extra = {"warm_refused": str(e)[:300], "warm_wall_s": time.time() - clock}
            print(f"t {t}: warm REFUSED, retrying cold · {str(e)[:120]}", flush=True)
            warm = False
            try:
                rec = solve(n, None)
            except Exception as e2:
                index.append({**n, "ok": False, "warm": False, **extra, "error": str(e2)[:300],
                              "wall_s": time.time() - clock})
                print(f"t {t}: REFUSED {str(e2)[:160]}", flush=True)
                prev = None
                continue
        wall = time.time() - clock
        prev = (float(t), field(rec, "aturns").tolist(), field(rec, "psi").ravel().tolist())
        fc = {k2: v["value"] for k2, v in rec["facts"].items()}
        eq = "equilibrium/time_slice/"
        np.savez_compressed(
            out / f"eq_{t:08.2f}.npz",
            psi=field(rec, eq + "profiles_2d/psi"), r=field(rec, eq + "profiles_2d/grid/dim1"),
            z=field(rec, eq + "profiles_2d/grid/dim2"),
            bnd_r=field(rec, eq + "boundary/outline/r"), bnd_z=field(rec, eq + "boundary/outline/z"),
            lim_r=field(rec, "equilibrium/fylite:limiter/r"), lim_z=field(rec, "equilibrium/fylite:limiter/z"),
            aturns=field(rec, "aturns"))
        index.append({**n, "ok": True, "warm": warm, **extra, "wall_s": wall, "facts": fc})
        print(f"t {t}: Ip {n['ip']/1e6:.2f} MA · bnd_kind {fc.get('bnd_kind')} · gap {fc.get('boundary_gap_rms'):.3f} m · "
              f"R0 {fc.get('shape_r0'):.3f} · kappa {fc.get('shape_kappa'):.3f} · {wall:.1f} s{' warm' if warm else ''}", flush=True)
        json.dump(index, open(out / "index.json", "w"), indent=1)
    json.dump(index, open(out / "index.json", "w"), indent=1)
    done = [r for r in index if r["ok"]]
    print(f"{len(done)}/{len(index)} solved · {sum(r['warm'] for r in index)} warm · "
          f"total {sum(r['wall_s'] for r in index):.1f} s", flush=True)


if __name__ == "__main__":
    main()
