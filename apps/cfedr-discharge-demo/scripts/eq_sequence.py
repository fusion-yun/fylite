"""Free-boundary equilibrium sequence along the CFEDR d2025 replay (code/discharge + C4).

Each sample time takes the replay's Miller LCFS and Ip, interpolated linearly per parameter between
nodes (the replay file's own `interpolation` rule), and solves once, cold, under position control
C4 with the card's coil ratings (F-9).  Output: one .npz per sample + index.json.

Usage: python eq_sequence.py DEVICE.json REPLAY.json OUT_DIR
"""
from __future__ import annotations

import bisect
import json
import sys
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
    dev_path, replay_path, out = sys.argv[1:4]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    dev = json.load(open(dev_path))
    nodes = json.load(open(replay_path))["nodes"]
    #: ★the card's coil ratings bound on the plan explicitly: the Python door rides the public runtime,
    #: whose embedded kernel may predate F-9 (card read by default) — measured: coil_limits 0 unbound
    ratings = [float(c["fylite:i_max_aturn"]) for c in dev["pf_active"]["coil"]
               if not any((f or {}).get("name") == "b_field_fb" for f in (c.get("function") or []))]
    index = []
    for t in TIMES:
        n = interp_node(nodes, float(t))
        st = {k2: n[k2] for k2 in KEYS}
        st.update(ip=n["ip"], relax=0.1, position_control="c4", seed="target")
        clock = time.time()
        try:
            rec = fydoc.complete("code/discharge", {"settings": st, "inputs": {
                "device": dev, "discharge": {"fylite:i_max_aturn": ratings}}})
        except Exception as e:  # a refusal is a reading, kept in the index
            index.append({**n, "ok": False, "error": str(e)[:300], "wall_s": time.time() - clock})
            print(f"t {t}: REFUSED {str(e)[:160]}", flush=True)
            continue
        wall = time.time() - clock
        fc = {k2: v["value"] for k2, v in rec["facts"].items()}
        eq = "equilibrium/time_slice/"
        np.savez_compressed(
            out / f"eq_{t:08.2f}.npz",
            psi=field(rec, eq + "profiles_2d/psi"), r=field(rec, eq + "profiles_2d/grid/dim1"),
            z=field(rec, eq + "profiles_2d/grid/dim2"),
            bnd_r=field(rec, eq + "boundary/outline/r"), bnd_z=field(rec, eq + "boundary/outline/z"),
            lim_r=field(rec, "equilibrium/fylite:limiter/r"), lim_z=field(rec, "equilibrium/fylite:limiter/z"),
            aturns=field(rec, "aturns"))
        index.append({**n, "ok": True, "wall_s": wall, "facts": fc})
        print(f"t {t}: Ip {n['ip']/1e6:.2f} MA · bnd_kind {fc.get('bnd_kind')} · gap {fc.get('boundary_gap_rms'):.3f} m · "
              f"R0 {fc.get('shape_r0'):.3f} · kappa {fc.get('shape_kappa'):.3f} · {wall:.1f} s", flush=True)
        json.dump(index, open(out / "index.json", "w"), indent=1)
    json.dump(index, open(out / "index.json", "w"), indent=1)


if __name__ == "__main__":
    main()
