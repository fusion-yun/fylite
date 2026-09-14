"""PCS 指令回放的分窗推进（台账 I-20 · I-21）：一窗一次内核调用、片界快照、可暂停可恢复。

★★为什么有这一层（2026-09-14 实测）：会话每 10 ms 一步 = 一次 ~295 ms 的内核调用，物理步 < 1 ms；
回放离线已知指令，于是按窗推进（:meth:`fylite.engine.session.Session.march_window`），窗内 10 ms 输出
取逐步迹插值。窗 = 时间片 = 快照点 = 暂停点。

规则（与 PLAN I-20 / I-21 细化同）：

* **切窗**：固定网格（``window``，爬升 / 下降段用 ``ramp_window``）并在每个回放节点处切开，
  使窗内的辅助功率不变；Ip 取窗末值（内核的 Ip 控制器跟随）。
* **快照**：每窗开始前一份入环形缓冲（``ring`` 份）；窗起点恰为回放节点的快照**永久保留**
  （``before-node``）；窗内出现 L-H 翻转 / 锯齿崩塌 / 内核拒绝时，把该窗起点快照提升保留
  （``before-event`` / ``before-refusal``）。工况文档按内容指纹只存一份。
* **事件重走**：自适应窗出事件 → 自窗起点快照以 10 ms 定步长重走该窗；定步长仍被拒 → 停，
  保留拒绝前快照（不静默跳过物理）。
* **密度反馈**：回放给线平均密度 ``ne_bar``；宿主按「窗末 n_e 平均 / 目标」调弹丸加料率
  （比例律，限幅），目标 = 起步时的 n_e 平均 × ne_bar(t) / ne_bar(t_起)。
* **暂停 / 恢复**：运行目录下出现 ``<out>.pause`` 即在下一个窗界写 ``pause`` 快照后退出；
  ``resume=<快照>`` 从该快照接着走（输出追加）。

``engine`` 导入时只用标准库：numpy 与内核都在调用时才装载。
"""
from __future__ import annotations

import bisect
import csv
import hashlib
import json
import time
from pathlib import Path

from . import session as S

__all__ = ["replay_commands", "window_edges", "march_replay"]

_ALPHA_SHARE = 3.518 / 17.589


def replay_commands(nodes: list, t: float) -> tuple[dict, dict]:
    """The replay's commands at ``t``: Ip / ne_bar linear between nodes, auxiliary power held from a node."""
    ts = [n["t"] for n in nodes]
    k = max(0, bisect.bisect_right(ts, t) - 1)
    a, b = nodes[k], nodes[min(k + 1, len(nodes) - 1)]
    u = 0.0 if b["t"] <= a["t"] else (t - a["t"]) / (b["t"] - a["t"])
    lin = lambda x, y: float(x) + (float(y) - float(x)) * min(max(u, 0.0), 1.0)  # noqa: E731
    rf = sum(float(v) for v in (a.get("p_ec") or {}).values()) + float(a.get("p_ic") or 0.0)
    info = {"replay_phase": a.get("phase"), "ne_bar": lin(a.get("ne_bar", 0.0), b.get("ne_bar", 0.0)),
            "synthetic": "synthetic" in (a.get("flags") or []), "node": k}
    return {"ip": lin(a["ip"], b["ip"]), "p_ec": [rf]}, info


def window_edges(nodes: list, t_from: float, t_to: float, window: float, ramp_window: float) -> list[float]:
    """Window edges on the 10 ms grid: a regular grid (shorter where Ip ramps) cut at every replay node."""
    step = S.STEP_S
    snap = lambda t: round(t / step) * step  # noqa: E731
    node_t = sorted(n["t"] for n in nodes if t_from < n["t"] < t_to)
    edges = [snap(t_from)]
    while edges[-1] < t_to - 1e-9:
        t = edges[-1]
        _, info = replay_commands(nodes, t)
        a = nodes[info["node"]]
        b = nodes[min(info["node"] + 1, len(nodes) - 1)]
        ramping = abs(float(b["ip"]) - float(a["ip"])) > 1.0 and b["t"] > a["t"]
        nxt = snap(min(t + (ramp_window if ramping else window), t_to))
        k = bisect.bisect_right(node_t, t + 1e-9)
        if k < len(node_t) and node_t[k] < nxt - 1e-9:
            nxt = snap(node_t[k])
        if nxt <= t + 1e-9:
            nxt = snap(t + step)
        edges.append(nxt)
    return edges


def _fingerprint(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def march_replay(plan: dict, nodes: list, t_from: float, t_to: float, out: str | Path, *,
                 window: float = 5.0, ramp_window: float = 0.5, adaptive: bool = True, dt_max: float | None = None,
                 ring: int = 5, density_feedback: bool = True, fuel_gain: float = 1.0, fuel_max_factor: float = 4.0,
                 resume: str | Path | None = None, pause_at: float | None = None, flat_every: int = 1,
                 rerun_max_flips: int = 4, fuel_max: float | None = None,
                 edge_ne_ref: tuple[float, float] | None = None, ec_sources=(0,), log=print) -> dict:
    """March ``nodes`` (the replay file's ``nodes``) from ``t_from`` to ``t_to``; outputs under ``out``."""
    import numpy as np  # noqa: F401  (the session's windows need it; import here keeps engine stdlib-pure)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    snap_dir = Path(str(out) + ".snapshots")
    snap_dir.mkdir(exist_ok=True)
    plan_id = _fingerprint(plan)
    plan_file = snap_dir / f"plan.{plan_id}.json"
    if not plan_file.exists():
        plan_file.write_text(json.dumps(plan))

    def save(sess: S.Session, tag: str) -> str:
        snap = sess.snapshot()
        snap.pop("plan", None)
        snap["plan_ref"] = plan_file.name
        name = f"{tag}@{snap['t']:.2f}.json"
        (snap_dir / name).write_text(json.dumps(snap))
        return name

    def load(path) -> S.Session:
        snap = json.loads(Path(path).read_text())
        if "plan" not in snap:
            snap["plan"] = json.loads((Path(path).parent / snap["plan_ref"]).read_text())
        return S.Session.from_snapshot(snap)

    if resume is not None:
        sess = load(resume)
        fuel_state = json.loads((snap_dir / "fuel_state.json").read_text()) if (snap_dir / "fuel_state.json").exists() else {}
        log(f"resumed from {resume} at t {sess.t_start + sess.k_next * S.STEP_S:.2f} s")
    else:
        sess = S.Session(plan, ec_sources=ec_sources, t_start=t_from, require_lcfs_after=1e9)
        fuel_state = {}
    fuel0 = float(plan["settings"].get("fuel_rate", 0.0))
    edgene0 = float(plan["settings"].get("edgene", 0.0))
    fuel = float(fuel_state.get("fuel", fuel0))
    ne_ref = fuel_state.get("ne_ref")
    t_ref_bar = fuel_state.get("ne_bar_ref")

    t_start_now = sess.t_start + sess.k_next * S.STEP_S
    edges = window_edges(nodes, t_start_now, t_to, window, ramp_window)
    node_times = {round(n["t"] / S.STEP_S) for n in nodes}
    fresh = resume is None
    f_out = open(out, "w" if fresh else "a", newline="")
    f_win = open(str(out) + ".windows.csv", "w" if fresh else "a", newline="")
    f_prof = open(str(out) + ".profiles.jsonl", "w" if fresh else "a")
    w_out, w_win = csv.writer(f_out), csv.writer(f_win)
    if fresh:
        w_out.writerow(["t", "replay_phase", "ip_cmd", "rf_cmd", "ne_bar_cmd", "fuel_rate", "p_fus", "w_th", "te0", "ti0",
                        "beta_n", "p_rad", "v_loop", "lh_phase", "p_sep", "p_lh", "interpolated"])
        w_win.writerow(["t_from", "t_to", "mode", "rerun", "calls", "kernel_steps", "wall_ms", "lh_flips", "sawtooth",
                        "rejected", "reason", "snapshot"])
    ring_buf: list[tuple[float, str | None, dict]] = []
    summary = {"windows": 0, "calls": 0, "kernel_steps": 0, "wall_ms": 0.0, "reruns": 0, "retained": [], "stopped": None}
    clock = time.perf_counter()
    try:
        for i in range(len(edges) - 1):
            t0, t1 = edges[i], edges[i + 1]
            if Path(str(out) + ".pause").exists() or (pause_at is not None and t0 >= pause_at - 1e-9):
                name = save(sess, "pause")
                summary["stopped"] = f"paused at {t0:.2f} s ({name})"
                summary["retained"].append(name)
                log(summary["stopped"])
                break
            cmd, info = replay_commands(nodes, t1)
            if edge_ne_ref is not None and edge_ne_ref[1] > 0.0:
                #: ★the edge density follows the commanded line density (edge = ref × n̄_e(t) / n̄_e,ref, never
                #: below the start case's own): a start case taken at 1 s carries a 6e17 edge, and held for
                #: the whole discharge it made the fuelled flat top peak three-fold on axis (2026-09-14)
                #: (the edge is the state's own last point — `Session.edge_ne` moves it on resume)
                sess.edge_ne = 1e19 * max(edgene0, edge_ne_ref[0] * info["ne_bar"] / edge_ne_ref[1])
            if density_feedback and fuel0 > 0.0:
                cmd["pellet"] = [{"n_atoms": fuel * S.STEP_S}]
                cmd["gas_rate"] = 0.0
            # snapshot before the window: kept for good at replay nodes, ring otherwise
            snap_mem = sess.snapshot()
            at_node = round(t0 / S.STEP_S) in node_times and i > 0
            kept = save(sess, "before-node") if at_node else None
            if kept:
                summary["retained"].append(kept)
            ring_buf.append((t0, kept, snap_mem))
            ring_buf[:] = ring_buf[-ring:]

            win = sess.march_window(cmd, t1, adaptive=adaptive, dt_max=dt_max)
            mode, rerun = ("adaptive" if adaptive else "fixed"), ""
            events = win.get("events") or {}
            #: ★an L-H dither (P_sep sitting on P_LH, hundreds of flips a window) is not an event a fixed step
            #: resolves better — it is the hysteresis model's own limit cycle, and re-running it at 10 ms only
            #: moves the flips; the adaptive window is kept and the row says so
            dither = events.get("lh_flips", 0) > rerun_max_flips
            if adaptive and dither and not win["rejected"]:
                rerun = "dither-kept"
            elif adaptive and (win["rejected"] or events.get("lh_flips") or events.get("sawtooth_crashes")):
                why = "refusal" if win["rejected"] else ("lh" if events.get("lh_flips") else "sawtooth")
                name = save(S.Session.from_snapshot(snap_mem), f"before-{'refusal' if win['rejected'] else 'event'}")
                summary["retained"].append(name)
                edge = sess.edge_ne
                sess = S.Session.from_snapshot(snap_mem)
                #: host-side controls are not part of the snapshot: the re-run keeps the window's edge
                sess.edge_ne = edge
                win = sess.march_window(cmd, t1, adaptive=False)
                mode, rerun = "fixed", why
                summary["reruns"] += 1
            if win["rejected"]:
                #: the adaptive attempt already kept the snapshot before this window (same state)
                name = next((r for r in reversed(summary["retained"]) if r.startswith(f"before-refusal@{t0:.2f}")), None)
                if name is None:
                    name = save(sess, "before-refusal")
                    summary["retained"].append(name)
                summary["stopped"] = f"refused in {t0:.2f}-{t1:.2f} s: {win.get('reason')} ({name})"
                w_win.writerow([t0, t1, mode, rerun, win["calls"], 0, round(win["wall_ms"], 1), 0, 0, True,
                                win.get("reason"), name])
                log(summary["stopped"])
                break
            series, end = win["outputs"], win["end"]
            ne_now = float(sum(end["ne"]) / len(end["ne"]))
            if ne_ref is None:
                ne_ref, t_ref_bar = ne_now, info["ne_bar"]
            if density_feedback and fuel0 > 0.0 and t_ref_bar:
                target = ne_ref * info["ne_bar"] / t_ref_bar
                cap = float(fuel_max) if fuel_max is not None else fuel_max_factor * fuel0
                fuel = min(max(fuel * (1.0 + fuel_gain * (target / ne_now - 1.0)), 0.0), cap)
            (snap_dir / "fuel_state.json").write_text(json.dumps({"fuel": fuel, "ne_ref": ne_ref, "ne_bar_ref": t_ref_bar}))
            n = len(series["t"])
            #: long (flat-top) windows write every `flat_every`-th 10 ms row and always the last; ramp windows
            #: write every row — a 6 000 s flat top at 10 ms would otherwise be 600 000 rows of a steady state
            every = max(1, int(flat_every)) if (t1 - t0) > ramp_window + 1e-9 else 1
            for j in range(n):
                if j % every and j != n - 1:
                    continue
                g = lambda k: (series.get(k) or [None] * n)[j]  # noqa: E731
                pa = g("p_alpha")
                w_out.writerow([round(series["t"][j], 6), info["replay_phase"], cmd["ip"], cmd["p_ec"][0], info["ne_bar"],
                                fuel if density_feedback else None, None if pa is None else pa / _ALPHA_SHARE, g("w_th"),
                                g("te0"), g("ti0"), g("beta_n"), g("p_rad"), g("v_loop"), g("lh_phase"), g("p_sep"),
                                g("p_lh"), j < n - 1])
            f_prof.write(json.dumps({"t": t1, "te": end["te"], "ti": end["ti"], "ne": end["ne"], "p_fus": end.get("p_fus"),
                                     "w_th": end.get("w_th"), "phase": (end.get("flags") or {}).get("phase")}) + "\n")
            w_win.writerow([t0, t1, mode, rerun, win["calls"], win["kernel_steps"], round(win["wall_ms"], 1),
                            events.get("lh_flips", 0), events.get("sawtooth_crashes", 0), False, "", kept or ""])
            f_out.flush(); f_win.flush(); f_prof.flush()  # noqa: E702
            summary["windows"] += 1
            summary["calls"] += win["calls"]
            summary["kernel_steps"] += win["kernel_steps"]
            summary["wall_ms"] += win["wall_ms"]
            if summary["windows"] % 20 == 0:
                log(f"t {t1:.2f} s · windows {summary['windows']} · calls {summary['calls']} · "
                    f"P_fus {end.get('p_fus', 0) / 1e6:.0f} MW · phase {(end.get('flags') or {}).get('phase')} · "
                    f"wall {(time.perf_counter() - clock):.0f} s")
        else:
            name = save(sess, "end")
            summary["retained"].append(name)
    finally:
        f_out.close(); f_win.close(); f_prof.close()  # noqa: E702
    summary["t_end"] = sess.t_start + sess.k_next * S.STEP_S
    summary["elapsed_s"] = time.perf_counter() - clock
    (Path(str(out) + ".summary.json")).write_text(json.dumps(summary, indent=1))
    return summary


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="March a PCS command replay through the session in windows (I-20 / I-21)")
    p.add_argument("plan"), p.add_argument("replay"), p.add_argument("t_from", type=float)
    p.add_argument("t_to", type=float), p.add_argument("out")
    p.add_argument("--window", type=float, default=5.0), p.add_argument("--ramp-window", type=float, default=0.5)
    p.add_argument("--fixed", action="store_true"), p.add_argument("--dt-max", type=float, default=None)
    p.add_argument("--no-density-feedback", action="store_true"), p.add_argument("--resume", default=None)
    p.add_argument("--pause-at", type=float, default=None)
    p.add_argument("--flat-every", type=int, default=1)
    p.add_argument("--rerun-max-flips", type=int, default=4)
    p.add_argument("--fuel-max", type=float, default=None, help="absolute fuelling cap [/s] (default 4 × the case's)")
    p.add_argument("--edge-ne-ref", type=float, nargs=2, default=None, metavar=("EDGENE", "NE_BAR"),
                   help="edge density [1e19] that goes with the replay line density NE_BAR [m^-3]")
    a = p.parse_args(argv)
    summary = march_replay(json.loads(Path(a.plan).read_text()), json.loads(Path(a.replay).read_text())["nodes"],
                           a.t_from, a.t_to, a.out, window=a.window, ramp_window=a.ramp_window, adaptive=not a.fixed,
                           dt_max=a.dt_max, density_feedback=not a.no_density_feedback, resume=a.resume,
                           pause_at=a.pause_at, flat_every=a.flat_every, rerun_max_flips=a.rerun_max_flips,
                           fuel_max=a.fuel_max, edge_ne_ref=a.edge_ne_ref)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
