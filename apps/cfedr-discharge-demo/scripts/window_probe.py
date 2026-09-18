"""Re-march one replay window from a kept snapshot, logging every kernel call (where a window stalls).

Usage: python window_probe.py SNAPSHOT.json REPLAY.json T1 [--fixed] [--max-calls N]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fylite.io import fydoc
from fylite.engine import session as S
from fylite.engine.pcs_replay import replay_commands


def main():
    snap_path, replay_path, t1 = sys.argv[1], sys.argv[2], float(sys.argv[3])
    fixed = "--fixed" in sys.argv
    max_calls = int(sys.argv[sys.argv.index("--max-calls") + 1]) if "--max-calls" in sys.argv else 60
    snap = json.loads(Path(snap_path).read_text())
    if "plan" not in snap:
        snap["plan"] = json.loads((Path(snap_path).parent / snap["plan_ref"]).read_text())
    sess = S.Session.from_snapshot(snap)
    nodes = json.loads(Path(replay_path).read_text())["nodes"]
    cmd, info = replay_commands(nodes, t1)
    fs = Path(snap_path).parent / "fuel_state.json"
    if fs.exists() and float(snap["plan"]["settings"].get("fuel_rate", 0.0)) > 0.0:
        cmd["pellet"] = [{"n_atoms": json.loads(fs.read_text())["fuel"] * S.STEP_S}]
        cmd["gas_rate"] = 0.0
    real = fydoc.complete
    n = [0]

    def logged(code, doc):
        n[0] += 1
        st = doc["settings"]
        c0 = time.perf_counter()
        try:
            rec = real(code, doc)
        except fydoc.Refused as exc:
            print(f"call {n[0]} t_start {st.get('t_start')} dt_start {st.get('dt_start')} REFUSED {exc}", flush=True)
            raise
        f = rec["facts"]
        g = lambda k: f.get(k, {}).get("value")  # noqa: E731
        dts = S.Session._field(rec, ("dt_used",))
        print(f"call {n[0]}: t {st.get('t_start'):.4f} -> {g('t_end'):.4f} steps {g('steps')} capped {g('dt_capped')} "
              f"dt_next {g('dt_next'):.3e} dt min {min(dts) if dts else float('nan'):.3e} "
              f"lh {g('lh_phase_out')} settled {g('settled')} wall {time.perf_counter() - c0:.2f} s", flush=True)
        if n[0] >= max_calls:
            raise SystemExit("max calls reached")
        return rec

    fydoc.complete = logged
    print(f"from t {sess.t_start + sess.k_next * S.STEP_S:.2f} to {t1} ({'fixed' if fixed else 'adaptive'}), phase {info['replay_phase']}",
          flush=True)
    dt_max = float(sys.argv[sys.argv.index("--dt-max") + 1]) if "--dt-max" in sys.argv else None
    win = sess.march_window(cmd, t1, adaptive=not fixed, dt_max=dt_max)
    print({k: win[k] for k in ("rejected", "calls", "kernel_steps", "events", "wall_ms") if k in win})


if __name__ == "__main__":
    main()
