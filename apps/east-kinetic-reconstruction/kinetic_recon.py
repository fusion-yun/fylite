#!/usr/bin/env python3
"""EAST 实验数据动理学平衡反演：原始测量 → 约束阶梯 M / K / P → 一份结果 JSON（页面读它）。

两条命令::

    python kinetic_recon.py pull --shot 137985 --time 4.041 -o meas.json      # 取数（mdsip）
    python kinetic_recon.py run  meas.json -o result.json                      # 反演三档

``pull`` 从原始树（``east`` 测量链：磁探针 · 磁通环 · PF 罗氏线圈 · Ip · TF 线圈电流 · POINT
11 弦）与 ``ts_east``（芯部 Thomson）取一个时刻，归约成一份测量文档。``run`` 也收
B-06 那份原始树归约件（``raw_slices_*.json``，按 ``--time`` 取最近一片）或 ``pull`` 的输出；
Thomson 可另给 ``--thomson``（``pull --thomson-only`` 的输出）。

约束阶梯（三档，档不同、能声称的东西不同；读数不可跨档比）：

    M   磁测量：环 + 探针 + Ip + 实测 PF 电流；竖直设定点扫描取 chi2 极小；坏道由拟合自己剔
    K   M + POINT：先在 M 的平衡上前向算 11 弦（零假设），再把法拉第角作行加进拟合，逐轮重建行
    P   + Thomson 压强点（实空间 R, Z，逐点实测 sigma），自洽外环逐遍把测点重映到 psi_N

★★实验数据不入仓：测量文档、结果 JSON 都写在调用方给的路径；服务器地址在写出的文件里
一律记作 ``mds.invalid``。

依赖：本仓 ``python/``（``fylite`` 包）与 numpy；fylite 的库（``python/fylite/_lib/``）与 EAST 装置牌
（``$FYLITE_DEVICE_DIR`` 或本仓 ``dist/facts``）。取数另要 ``$FYLITE_MDSIP_SERVER``。
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
#: 在本仓里跑时，fylite 包就在两级之上的 python/；装了 fylite 的环境里这一行不起作用
_REPO_PY = HERE.parents[1] / "python"
if (_REPO_PY / "fylite").is_dir() and str(_REPO_PY) not in sys.path:
    sys.path.insert(0, str(_REPO_PY))

import numpy as np  # noqa: E402

APP = "east-kinetic-reconstruction"
VERSION = "0.1.0"

#: sigma = max(SERROR·|读数|, 位下限)——KEFIT / EFIT 的 data_input 约定（B-06 §7.1 两个代码同用）
SERROR = 0.05
LOOP_FLOOR = 5e-4          #: Wb/rad
PROBE_FLOOR = 7.52541e-4   #: T（KEFIT efit/2016/bitmp2.txt 的中位，本仓 tools/benchmark-equilibrium.py 同值）
#: POINT 的 sigma：KEFIT GUI 缺省（B-06 §2.2）
SIGPOL, SIGNEL = 0.05, 0.3
TF_NODE = r"\TOP.T2:TFP"
TF_TURNS = 130 * 16        #: EAST TF：16 线圈 × 130 匝（B-06 §7.1；GUI_v5.m:332 保留的那个公式）

SETTINGS = {"npp": 2, "nff": 2, "relax": 0.3, "max_iter": 4000, "tol": 1e-8, "fb_gain": 8.0, "warmup": 40,
            "n_profile": 201, "n_q": 20, "n_theta": 121, "x_lo": 0.06, "x_hi": 0.995}
ZC_SCAN = [round(-0.030 + 0.004 * k, 3) for k in range(16)]


def log(msg: str) -> None:
    print(f"[{APP}] {msg}", file=sys.stderr, flush=True)


def sanitize(text):
    """服务器地址不出门：``mdsplus:<host>:<port>:…`` → ``mdsplus:mds.invalid:…``。"""
    if not isinstance(text, str):
        return text
    return re.sub(r"(mdsplus:)[^:]+:\d+:", r"\1mds.invalid:", text)


def door(code: str, settings: dict, inputs: dict):
    """fylite 的内核文档门：一份请求进、一份记录出。"""
    from fylite.io import fydoc
    rec = fydoc.complete(code, {"settings": settings, "inputs": inputs})
    fa = {k: v["value"] for k, v in rec["facts"].items() if isinstance(v.get("value"), (int, float))}
    fi = {k: np.asarray(v["data"], float) for k, v in rec["fields"].items()}
    return fa, fi, list(rec.get("notes") or [])


# ================================================================================================ pull

def _session(timeout_s: float):
    from fylite import kernel
    from fylite.io.mds import _server
    host, port = _server(None)
    return kernel.MdsSession(host, port, timeout_ms=int(timeout_s * 1000)), host, port


def pull_magnetics(shot: int, t: float, chain: str, timeout_s: float) -> dict:
    """原始树 → 平坦测量字典（``fylite.io.raw.reduce_series``，与 ``read_mds`` 同一归约），
    外加 TF 线圈电流算出的真空 F（``read_mds`` 的 B_T 节点自 #97286 起是伏特，B-06 §7.1）。"""
    from fylite import device, kernel
    from fylite.io import raw
    doc = device.document(shot=int(shot), measurement_chain=chain)
    tree = raw.chain_tree(chain)
    conn, host, port = _session(timeout_s)
    cur = {"tree": None}

    def get(leaf, where):
        nd = leaf if leaf.startswith("\\") else "\\" + leaf
        if where != cur["tree"]:
            conn.open_tree(where, int(shot))
            cur["tree"] = where
        try:
            s, _ = conn.read("data", nd)
            tb, _ = conn.read("dim_of", nd)
            return np.asarray(s, float), np.asarray(tb, float)
        except kernel.KernelError:                       # 节点不在：是数据，不是故障
            return None

    try:
        tf = get(TF_NODE, tree)
        meas = raw.reduce_series(get, shot, t, device_doc=doc, measurement_chain=chain, read_point=True,
                                 source=f"mdsplus:{host}:{port}:{tree}:{shot}", error=RuntimeError)
    finally:
        conn.close()
    if tf is not None:
        sel = np.abs(tf[1] - t) <= 0.005
        i_tf = float(np.mean(tf[0][sel])) if sel.any() else float(tf[0][np.argmin(np.abs(tf[1] - t))])
        meas["tf"] = {"node": TF_NODE, "i_tf_A": i_tf, "turns_total": TF_TURNS, "f_vac_Tm": 2e-7 * TF_TURNS * i_tf}
    meas["source"] = sanitize(meas.get("source"))
    return meas


def pull_thomson(shot: int, t: float) -> dict:
    from fylite.io import mds
    th = mds.fetch_thomson(int(shot), float(t))
    th["source"] = sanitize(th.get("source"))
    return th


def cmd_pull(a) -> int:
    doc = {"@type": "fylite:KineticReconMeasurements", "app": APP, "version": VERSION,
           "shot": a.shot, "time_s": a.time, "measurement_chain": a.chain,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "comment": "实验数据：不入仓。服务器地址记作 mds.invalid。",
           "measurements": None, "thomson": None, "errors": {}}
    if not a.thomson_only:
        t0 = time.time()
        try:
            doc["measurements"] = pull_magnetics(a.shot, a.time, a.chain, a.timeout)
            log(f"magnetics + POINT: {time.time() - t0:.1f} s")
        except Exception as e:                           # noqa: BLE001 — 取不到就说取不到
            doc["errors"]["measurements"] = sanitize(str(e))[:400]
            log(f"magnetics FAILED: {doc['errors']['measurements']}")
    if not a.no_thomson:
        t0 = time.time()
        try:
            doc["thomson"] = pull_thomson(a.shot, a.time)
            log(f"Thomson: {len(doc['thomson']['te'])} points at {doc['thomson']['sample_time_s']:.4f} s "
                f"({time.time() - t0:.1f} s)")
        except Exception as e:                           # noqa: BLE001
            doc["errors"]["thomson"] = sanitize(str(e))[:400]
            log(f"Thomson FAILED: {doc['errors']['thomson']}")
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    log(f"-> {a.out}")
    return 0 if (doc["measurements"] or doc["thomson"]) else 1


# ================================================================================================ input

def load_input(path: str, t: float | None, thomson_path: str | None) -> tuple[dict, dict | None, dict]:
    """(平坦测量字典, Thomson 或 None, 出处)。认三种形：``pull`` 的输出 · 原始树归约件 · 裸字典。"""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    th = None
    if "fylite:slices" in d:                             #: B-06 的原始树归约件：按时刻取最近一片
        keys = sorted(d["fylite:slices"], key=float)
        k = keys[0] if t is None else min(keys, key=lambda s: abs(float(s) - t))
        meas, origin = d["fylite:slices"][k], {"kind": "raw_slices", "slice": k}
    elif "measurements" in d or "thomson" in d:
        meas, th, origin = d.get("measurements"), d.get("thomson"), {"kind": "pull"}
    else:
        meas, origin = d, {"kind": "flat"}
    if thomson_path:
        tdoc = json.loads(Path(thomson_path).read_text(encoding="utf-8"))
        th = tdoc.get("thomson", tdoc) if isinstance(tdoc, dict) else None
    if not meas:
        raise SystemExit("输入里没有磁测量（pull 的 errors 里写着为什么）")
    origin["file"] = Path(path).name
    return meas, th, origin


# ================================================================================================ helpers

def _name(x: dict) -> str:
    return str(x.get("name") or x.get("identifier") or "")


def _rz(x: dict):
    p = x.get("position")
    if isinstance(p, dict):
        r, z = p.get("r"), p.get("z")
    elif isinstance(p, list) and p:
        q = p[0]
        r, z = q.get("r"), q.get("z")
    else:
        return None
    r = r[0] if isinstance(r, list) else r
    z = z[0] if isinstance(z, list) else z
    return [float(r), float(z)] if r is not None and z is not None else None


def psi_at(fi: dict, r: float, z: float) -> float:
    gr, gz = fi["grid_r"], fi["grid_z"]
    psi = fi["psi"].reshape(len(gr), len(gz))
    i = int(np.clip(np.searchsorted(gr, r) - 1, 0, len(gr) - 2))
    j = int(np.clip(np.searchsorted(gz, z) - 1, 0, len(gz) - 2))
    a = (r - gr[i]) / (gr[i + 1] - gr[i])
    b = (z - gz[j]) / (gz[j + 1] - gz[j])
    return float((1 - a) * (1 - b) * psi[i, j] + a * (1 - b) * psi[i + 1, j]
                 + (1 - a) * b * psi[i, j + 1] + a * b * psi[i + 1, j + 1])


def psin_at(fa: dict, fi: dict, r: float, z: float) -> float:
    return (fa["psi_axis"] - psi_at(fi, r, z)) / (fa["psi_axis"] - fa["psi_bnd"])


def _r(x, n=6):
    """JSON 里的数：有效数字截到 n 位，非有限写 null。"""
    if isinstance(x, (list, tuple, np.ndarray)):
        return [_r(v, n) for v in x]
    x = float(x)
    return float(f"{x:.{n}g}") if math.isfinite(x) else None


FACT_KEYS = ("q0", "q95", "li3", "axis_r", "axis_z", "ip", "psi_axis", "psi_bnd", "chi2", "chi2_mag", "chi2_kin",
             "chi2_per_dof", "dof", "worst_channel_sigma", "iterations", "residual", "converged", "kinetic_rows",
             "kinetic_passes_run", "kinetic_best_pass", "kinetic_best_chi2_per_dof", "kinetic_map_shift",
             "p_fast_max", "curv_p", "curv_f", "npp", "nff")


def tier_view(fa: dict, fi: dict, zc: float, extra: dict | None = None) -> dict:
    nr, nz = len(fi["grid_r"]), len(fi["grid_z"])
    v = {"status": "ok", "zc_anchor": zc,
         "facts": {k: _r(fa[k]) for k in FACT_KEYS if k in fa},
         "grid": {"r": _r(fi["grid_r"]), "z": _r(fi["grid_z"])},
         "psi": _r(fi["psi"].reshape(nr, nz), 5),
         "boundary": _r(fi["boundary"].reshape(-1, 2), 5) if "boundary" in fi else [],
         "profiles": {"psin": _r(fi["psin_1d"], 5), "pres": _r(fi["pres"], 5), "pprime": _r(fi["pprime"], 5),
                      "ffprim": _r(fi["ffprim"], 5), "qpsi": _r(fi["qpsi"], 5),
                      "pprime_sigma": _r(fi.get("pprime_sigma", np.full_like(fi["pprime"], np.nan)), 5)},
         "q": {"x": _r(fi["q_x"], 5), "q": _r(fi["q"], 5)}}
    if extra:
        v.update(extra)
    return v


# ================================================================================================ tiers

class Case:
    """一个时刻的全部输入，以及三档共用的那几样（线圈份额、装置牌、权重）。"""

    def __init__(self, meas: dict, card: dict, loops: str):
        self.meas, self.card = meas, card
        self.brsp = np.asarray(meas["brsp"], float)
        self.coils = np.asarray(meas["coils"], float)
        self.probes = np.asarray(meas["expmp2"], float)
        mag = card["magnetics"]
        self.loop_names = [_name(x) for x in mag.get("flux_loop", [])][:len(self.coils)]
        self.probe_names = [_name(x) for x in mag.get("b_field_pol_probe", [])][:len(self.probes)]
        self.loop_rz = [_rz(x) for x in mag.get("flux_loop", [])][:len(self.coils)]
        self.probe_rz = [_rz(x) for x in mag.get("b_field_pol_probe", [])][:len(self.probes)]
        r0 = float(card["tf"]["r0"])
        tf = meas.get("tf") or {}
        if "f_vac_Tm" in tf:
            self.b_tor, self.bt_from = abs(float(tf["f_vac_Tm"])) / r0, f"TF 线圈电流 {tf.get('node', '')}（F = μ₀NI/2π）"
        else:
            self.b_tor, self.bt_from = abs(float(meas["btor"])), "归约件的 btor（B_T 节点，#97286 起单位存疑）"
        _, share, _ = door("code/coilshare", {"nu_loops": 8, "nu_probes": 3, "grid_psi": 1, "nu_grid": 4},
                           {"device": card, "discharge": {"fylite:channel_aturns": self.brsp}})
        self.loop_coil, self.probe_coil, self.psi_ext = share["loop_coil"], share["probe_coil"], share["psi_ext"]
        #: 选道：探针 = 归约器判在用 − 名字重复的槽（没有独立节点）；环 = 全部或只 B 组
        self.excluded = []
        fwt = np.asarray(meas["fwtmp2"], float).copy()
        seen = {}
        for i, nm in enumerate(self.probe_names):
            seen.setdefault(nm, []).append(i)
        for nm, idx in seen.items():
            if nm and len(idx) > 1:
                for i in idx:
                    if fwt[i] > 0:
                        self.excluded.append({"kind": "probe", "index": i, "name": nm, "why": "名字重复：没有独立节点"})
                    fwt[i] = 0.0
        #: ★★起步环组（实测 2026-09-18，#137985 4.041 s）：75 个环全进，16 个竖直设定点一个都不收敛
        #: （等离子体在几十次外迭代里被拟合推出盒子）；只用 FL*B 组起步则 4/16 收敛，剔道之后 15/16。
        #: 所以起步用 B 组，其余环在第一个收敛解上**按残差回收**（readmit），而不是写死一张行表。
        self.loop_start = np.ones(len(self.coils))
        if loops in ("B", "B+readmit"):
            for i, nm in enumerate(self.loop_names):
                if not re.fullmatch(r"FL\d+B", nm or ""):
                    self.loop_start[i] = 0.0
        self.loop_sigma = np.maximum(SERROR * np.abs(self.coils), LOOP_FLOOR)
        self.probe_sigma = np.maximum(SERROR * np.abs(self.probes), PROBE_FLOOR)
        self.lw = self.loop_start / self.loop_sigma
        self.pw = np.where(fwt > 0, fwt / self.probe_sigma, 0.0)

    def base_disc(self) -> dict:
        return {"fylite:channel_aturns": self.brsp, "fylite:ip": np.array([float(self.meas["plasma"])]),
                "fylite:b_tor": np.array([self.b_tor]), "fylite:loop_weight": self.lw, "fylite:probe_weight": self.pw}

    def full_disc(self) -> dict:
        return dict(self.base_disc(), **{"fylite:flux_loop": self.coils, "fylite:probe_field": self.probes})

    def rows_disc(self) -> dict:
        """行给定档：量值扣掉线圈份额，外场随行（POINT 的法拉第行只能走这一档）。"""
        return dict(self.base_disc(), **{"fylite:psi_ext": self.psi_ext,
                                         "fylite:loop_plasma": self.coils - self.loop_coil,
                                         "fylite:probe_plasma": self.probes - self.probe_coil})

    def residuals(self, fi: dict, *, all_channels: bool = False):
        """(model − measured)/sigma per channel; weighted (0 for unused) unless ``all_channels``."""
        rl = (fi["loop_model"] + self.loop_coil - self.coils) / self.loop_sigma
        rp = (fi["probe_model"] - self.probes) / self.probe_sigma
        if all_channels:
            return rl, rp
        return rl * (self.lw > 0), rp * (self.pw > 0)

    def channel_table(self, fi: dict) -> dict:
        """Every channel with its residual — used or not, so a reader sees why one is out."""
        rl, rp = self.residuals(fi, all_channels=True)
        return {"loops": [{"name": n, "rz": rz, "sigma": _r(v, 4), "used": bool(w > 0)}
                          for n, rz, v, w in zip(self.loop_names, self.loop_rz, rl, self.lw)],
                "probes": [{"name": n, "rz": rz, "sigma": _r(v, 4), "used": bool(w > 0)}
                           for n, rz, v, w in zip(self.probe_names, self.probe_rz, rp, self.pw)]}


def tier_m(c: Case, reject_sigma: float, max_rounds: int, per_round: int, settings: dict,
           readmit: bool) -> tuple[dict, tuple | None]:
    """档 M：扫描 + 剔道几轮；``readmit`` 时把起步组之外、在收敛解上残差不超阈值的环收回来，再扫几轮。"""
    rounds, rejected, readmitted = [], [], []
    best = _m_rounds(c, reject_sigma, max_rounds, per_round, settings, rounds, rejected, 0)
    if best is not None and readmit:
        _, _, _, fi, _ = best
        rl, _ = c.residuals(fi, all_channels=True)
        gone = {r["index"] for r in rejected if r["kind"] == "loop"}
        for i in range(len(c.coils)):
            if c.lw[i] == 0 and c.loop_start[i] == 0 and i not in gone and abs(rl[i]) <= reject_sigma:
                c.lw[i] = 1.0 / c.loop_sigma[i]
                readmitted.append({"kind": "loop", "index": i, "name": c.loop_names[i], "sigma": _r(rl[i], 3)})
        if readmitted:
            log(f"M readmit: {len(readmitted)} loop(s) predicted within {reject_sigma:g} sigma")
            again = _m_rounds(c, reject_sigma, max_rounds, per_round, settings, rounds, rejected, len(rounds))
            if again is not None:
                best = again
            else:                                        #: 回收之后反而解不出：退回，照实记
                for r in readmitted:
                    c.lw[r["index"]] = 0.0
                readmitted = [dict(r, reverted=True) for r in readmitted]
    if best is None:
        return {"status": "error", "error": "没有一个竖直设定点收敛", "rounds": rounds, "rejected": rejected}, None
    chi2, zc, fa, fi, notes = best
    view = tier_view(fa, fi, zc, {"label": "M · 磁测量", "rounds": rounds, "rejected": rejected,
                                  "readmitted": readmitted, "channels": c.channel_table(fi), "notes": notes,
                                  "constraints": ["磁通环", "磁探针", "Ip", "实测 PF 电流（固定）"]})
    return view, (fa, fi, zc)


def _m_rounds(c: Case, reject_sigma, max_rounds, per_round, settings, rounds, rejected, rnd0):
    """One run of scan + reject rounds.  Returns the last round that converged; if a round after a
    rejection converges nothing, that rejection is undone (so the mask and the answer always agree)."""
    last_good, last_batch = None, []
    for rnd in range(rnd0, rnd0 + max_rounds):
        scan, best = [], None
        for zc in ZC_SCAN:
            try:
                fa, fi, notes = door("code/reconstruction", dict(settings, zc_anchor=zc),
                                     {"device": c.card, "discharge": c.full_disc()})
            except Exception as e:                       # noqa: BLE001 — 一个解不出的设定点也是读数
                scan.append({"zc": zc, "error": str(e)[-60:]})
                continue
            rl, rp = c.residuals(fi)
            chi2 = float((rl ** 2).sum() + (rp ** 2).sum())
            scan.append({"zc": zc, "chi2": _r(chi2, 5), "q0": _r(fa["q0"], 4), "converged": bool(fa["converged"])})
            if fa["converged"] and (best is None or chi2 < best[0]):
                best = (chi2, zc, fa, fi, notes)
        n_used = int((c.lw > 0).sum() + (c.pw > 0).sum())
        if best is None:
            rounds.append({"round": rnd, "scan": scan, "converged": 0, "n_used": n_used})
            for r in last_batch:                         #: 这一批剔完反而解不出：撤回
                (c.lw if r["kind"] == "loop" else c.pw)[r["index"]] = (
                    1.0 / (c.loop_sigma if r["kind"] == "loop" else c.probe_sigma)[r["index"]])
                r["reverted"] = True
            break
        last_good, last_batch = best, []
        chi2, zc, fa, fi, _ = best
        rl, rp = c.residuals(fi)
        cand = sorted([(abs(rl[i]), "loop", i) for i in np.where(np.abs(rl) > reject_sigma)[0]]
                      + [(abs(rp[i]), "probe", i) for i in np.where(np.abs(rp) > reject_sigma)[0]], reverse=True)
        rounds.append({"round": rnd, "scan": scan, "converged": sum(1 for s in scan if s.get("converged")),
                       "n_used": n_used, "zc": zc, "chi2": _r(chi2, 5), "chi2_per_channel": _r(chi2 / n_used, 4),
                       "q0": _r(fa["q0"], 4)})
        log(f"M round {rnd}: {rounds[-1]['converged']}/{len(ZC_SCAN)} converged, zc {zc * 1e3:+.0f} mm, "
            f"chi2/channel {chi2 / n_used:.2f}, q0 {fa['q0']:.3f}, {len(cand)} channel(s) > {reject_sigma:g} sigma")
        if not cand:
            break
        if rnd == rnd0 + max_rounds - 1:
            break                                        #: 最后一轮只量，不剔——剔了就没有对应的解了
        for v, kind, i in cand[:per_round]:
            names = c.loop_names if kind == "loop" else c.probe_names
            (c.lw if kind == "loop" else c.pw)[i] = 0.0
            rejected.append({"kind": kind, "index": int(i), "name": names[i], "sigma": _r(v, 3), "round": rnd})
            last_batch.append(rejected[-1])
    return last_good


def _eq_doc(fa, fi):
    return {"time_slice": {"profiles_2d": {"psi": fi["psi"]},
                           "global_quantities": {"psi_axis": np.array([fa["psi_axis"]]),
                                                 "psi_boundary": np.array([fa["psi_bnd"]])}}}


def point_arrays(meas: dict, off: list[int]):
    p = meas["point"]
    nel, bp = np.asarray(p["bnel"], float), np.asarray(p["bpolar"], float)
    fwtnel, fwtpol = np.asarray(p["fwtnel"], float).copy(), np.asarray(p["fwtpol"], float).copy()
    for k in off:
        if 1 <= k <= len(bp):
            fwtnel[k - 1] = fwtpol[k - 1] = 0.0
    return nel, bp, fwtnel, fwtpol


def chords(c: Case, fa, fi, nel, fwtnel):
    eq = _eq_doc(fa, fi)
    fit, _, _ = door("code/chords", {"ne0": 3e19, "rows": 0},
                     {"device": c.card, "equilibrium": eq,
                      "discharge": {"fylite:chord_nel": nel * 1e19, "fylite:chord_nel_weight": fwtnel}})
    fa2, fi2, _ = door("code/chords", {"ne0": fit["fit_ne0"], "peaking": fit["fit_peaking"], "rows": 1},
                       {"device": c.card, "equilibrium": eq,
                        "discharge": {"fylite:psi_ext": c.psi_ext, "fylite:current_cells": fi["current"]}})
    return fit, fi2


def point_resid(fi2, nel, bp, fwtnel, fwtpol):
    sn = np.sqrt(SIGNEL ** 2 + (0.03 * nel) ** 2)
    rb = (fi2["chord_bpolar"] - bp) / SIGPOL
    rn = (fi2["chord_nel19"] - nel) / sn
    rms = lambda r, w: float(np.sqrt(np.mean(r[w > 0] ** 2))) if (w > 0).any() else float("nan")  # noqa: E731
    return rb, rn, rms(rb, fwtpol), rms(rn, fwtnel)


def faraday_extra(c: Case, fi2, bp, fwtpol) -> dict:
    use = np.where(fwtpol > 0)[0]
    frows = fi2["faraday_rows"].reshape(len(bp), -1)[use]
    return {"fylite:row_extra": frows.ravel(),
            "fylite:meas_extra": (bp[use] - fi2["chord_coil"][use] / 1e19) * 1e19,
            "fylite:weight_extra": fwtpol[use] / (SIGPOL * 1e19)}


def tier_k(c: Case, base, off: list[int], dead_sigma: float, settings: dict) -> tuple[dict, tuple | None, dict | None]:
    """档 K：零假设（M 的平衡上前向 11 弦）→ 法拉第行进拟合，逐轮重建行至 |Δq0|/q0 < 1e-3。"""
    if not (c.meas.get("point") or {}).get("bpolar"):
        return {"status": "skipped", "why": "输入里没有 POINT 块"}, None, None
    fa_m, fi_m, zc = base
    nel, bp, fwtnel, fwtpol = point_arrays(c.meas, off)
    fit, fi2 = chords(c, fa_m, fi_m, nel, fwtnel)
    rb0, rn0, rbs0, rns0 = point_resid(fi2, nel, bp, fwtnel, fwtpol)
    #: 死道：零假设残差离谱（B-06：干涉死道 +22 sigma，法拉第死道 −10.9 sigma）
    dead = []
    for i in range(len(bp)):
        if fwtpol[i] > 0 and abs(rb0[i]) > dead_sigma:
            fwtpol[i] = 0.0
            dead.append({"chord": i + 1, "row": "faraday", "sigma": _r(rb0[i], 3)})
        if fwtnel[i] > 0 and abs(rn0[i]) > dead_sigma:
            fwtnel[i] = 0.0
            dead.append({"chord": i + 1, "row": "density", "sigma": _r(rn0[i], 3)})
    if dead:
        fit, fi2 = chords(c, fa_m, fi_m, nel, fwtnel)
        rb0, rn0, rbs0, rns0 = point_resid(fi2, nel, bp, fwtnel, fwtpol)
    null = {"ne0": _r(fit["fit_ne0"]), "peaking": _r(fit["fit_peaking"]), "faraday_rms": _r(rbs0, 4),
            "density_rms": _r(rns0, 4), "faraday_sigma": _r(rb0, 4), "density_sigma": _r(rn0, 4)}
    log(f"K null hypothesis: Faraday {rbs0:.3f} sigma, density {rns0:.3f} sigma, dead {[d['chord'] for d in dead]}")
    st = dict(settings, zc_anchor=zc)
    fa, fi = fa_m, fi_m
    passes = []
    try:
        #: 起点：行给定档上不带法拉第行的那一解（与 M 同一平衡，差在求解器容差内）
        fa, fi, _ = door("code/reconstruction", st, {"device": c.card, "discharge": c.rows_disc()})
        for _ in range(6):
            _, fi2 = chords(c, fa, fi, nel, fwtnel)
            disc = dict(c.rows_disc(), **faraday_extra(c, fi2, bp, fwtpol))
            fa_n, fi_n, notes = door("code/reconstruction", st, {"device": c.card, "discharge": disc})
            dq = abs(fa_n["q0"] - fa["q0"]) / max(abs(fa["q0"]), 1e-12)
            passes.append({"q0": _r(fa_n["q0"], 5), "dq0_rel": _r(dq, 3), "converged": bool(fa_n["converged"])})
            fa, fi = fa_n, fi_n
            if dq < 1e-3:
                break
    except Exception as e:                               # noqa: BLE001 — 记下，不藏
        return {"status": "error", "error": str(e)[-300:], "null": null, "dead": dead, "passes": passes}, None, None
    fit2, fi2 = chords(c, fa, fi, nel, fwtnel)
    rb1, rn1, rbs1, rns1 = point_resid(fi2, nel, bp, fwtnel, fwtpol)
    log(f"K fitted: q0 {fa['q0']:.3f}, Faraday {rbs0:.3f} -> {rbs1:.3f} sigma, {len(passes)} pass(es)")
    chord_geo = [{"name": _name(ch), "los": ch.get("line_of_sight")} for ch in (c.card.get("polarimeter") or {}).get("channel", [])]
    view = tier_view(fa, fi, zc, {
        "label": "K · 磁 + POINT", "constraints": ["磁（同 M）", f"POINT 法拉第行 × {int((fwtpol > 0).sum())}"],
        "channels": c.channel_table(fi), "passes": passes, "settled": bool(passes and passes[-1]["dq0_rel"] < 1e-3),
        "point": {"measured_bpolar": _r(bp, 5), "measured_nel19": _r(nel, 5), "fwtpol": _r(fwtpol), "fwtnel": _r(fwtnel),
                  "off_by_user": off, "dead": dead, "null": null,
                  "fitted": {"ne0": _r(fit2["fit_ne0"]), "peaking": _r(fit2["fit_peaking"]), "faraday_rms": _r(rbs1, 4),
                             "density_rms": _r(rns1, 4), "faraday_sigma": _r(rb1, 4), "density_sigma": _r(rn1, 4),
                             "model_bpolar": _r(fi2["chord_bpolar"], 5), "model_nel19": _r(fi2["chord_nel19"], 5)},
                  "chords": chord_geo}})
    return view, (fa, fi, zc), {"nel": nel, "bp": bp, "fwtnel": fwtnel, "fwtpol": fwtpol}


def thomson_points(th: dict, frac_floor: float):
    from fylite.io import mds
    p = mds.pressure_from_thomson(th, sigma_floor=frac_floor)
    return p


def clip_profile(x, p, sig, keep, clip: float, min_left: int = 6):
    """逐点剔离群：对 p(psi_N) 做一次带 GCV 定阶的光滑拟合（``code/profile_fit``），把离拟合最远、且超过
    ``clip`` 个 sigma 的那一点剔掉，重拟，直到没有这样的点。★与档 M 剔磁道同一姿态：由数据自己判，
    一次一个，理由写进结果。★实测（#137985 4.019 s）：Thomson 的 19 个点里有两点压强 118 kPa · 331 kPa，
    邻点 5–35 kPa、自报 sigma 只有 5–6 %——不剔，档 P 的求解直接把等离子体拟丢。"""
    from fylite import scenario as S
    keep = keep.copy()
    dropped = []
    while keep.sum() > min_left:
        idx = np.where(keep)[0]
        fit = S.analysis.profit(x[idx], p[idx], sigma=sig[idx], evaluate_at=x[idx])
        r = (p[idx] - np.asarray(fit["fit"], float)) / sig[idx]
        j = int(np.argmax(np.abs(r)))
        if abs(r[j]) <= clip:
            break
        keep[idx[j]] = False
        dropped.append({"index": int(idx[j]), "sigma": _r(r[j], 3), "order": int(fit["order"])})
    return keep, dropped


def tier_p(c: Case, base, kin, th: dict, a, settings: dict) -> dict:
    """档 P：Thomson 压强点（R, Z，逐点实测 sigma）作动理学行，自洽外环逐遍重映 psi_N。"""
    fa_b, fi_b, zc = base
    p = thomson_points(th, a.sigma_floor)
    r, z = np.asarray(p["r"], float), np.asarray(p["z"], float)
    pres, sig = np.asarray(p["pressr"], float), np.asarray(p["sigpre"], float)
    gr, gz = fi_b["grid_r"], fi_b["grid_z"]
    x0 = np.array([psin_at(fa_b, fi_b, ri, zi) if (gr[0] <= ri <= gr[-1] and gz[0] <= zi <= gz[-1]) else np.nan
                   for ri, zi in zip(r, z)])
    inside = np.isfinite(x0) & (x0 >= 0.0) & (x0 < a.psin_max)
    keep, clipped = clip_profile(np.where(inside, x0, 0.0), pres, sig, inside, a.thomson_clip)
    why = {d["index"]: f"离光滑拟合 {d['sigma']} σ（剔）" for d in clipped}
    points = [{"r": _r(ri, 5), "z": _r(zi, 5), "p": _r(pi, 5), "sigma": _r(si, 4), "psin_initial": _r(xi, 4),
               "used": bool(k), "why": (why.get(i) or ("" if ins else f"psi_N ≥ {a.psin_max}（不收）"))}
              for i, (ri, zi, pi, si, xi, k, ins) in enumerate(zip(r, z, pres, sig, x0, keep, inside))]
    if clipped:
        log(f"P: clipped {len(clipped)} Thomson point(s) beyond {a.thomson_clip:g} sigma of a smooth fit")
    if keep.sum() < 3:
        return {"status": "error", "error": f"只有 {int(keep.sum())} 个 Thomson 点落在 psi_N < {a.psin_max} 内", "points": points}
    rows = {"fylite:pressure": pres[keep], "fylite:pressure_x": x0[keep], "fylite:pressure_weight": 1.0 / sig[keep],
            "fylite:pressure_r": r[keep], "fylite:pressure_z": z[keep]}
    if a.p_fast_frac > 0:                                #: 声明的快离子份额：峰值热压的 f 倍 × (1 − x²)
        xg = np.linspace(0, 1, 41)
        rows["fylite:p_fast_profile"] = a.p_fast_frac * float(np.max(pres[keep])) * (1.0 - xg ** 2)
    stacked = kin is not None
    #: ★★叠在 K 上（行给定档）时外环不重映（实测 2026-09-18）：同一份输入，逐遍证书在 chi2/dof
    #: 47.5 与 2.72 之间来回跳、映射移动每遍都是 0.994——那一档的重映拿到的不是它该拿的磁面。
    #: 所以叠放时只跑一遍，并照实写进结果；要外环，就用缺省的「P 叠在 M 上」。
    passes = 1 if stacked else a.kinetic_passes
    st = dict(settings, zc_anchor=zc, kinetic_passes=passes, kinetic_tol=a.kinetic_tol,
              curv_p=a.curv, curv_f=a.curv)
    if stacked:
        fa_k, fi_k, _ = base
        _, fi2 = chords(c, fa_k, fi_k, kin["nel"], kin["fwtnel"])
        disc0 = dict(c.rows_disc(), **faraday_extra(c, fi2, kin["bp"], kin["fwtpol"]))
    else:
        disc0 = c.full_disc()
    #: ★★sigma 续延（实测 2026-09-18）：把档 M **自己的**压强剖面原样当动理学行喂回去——数据与解
    #: 完全自洽——sigma 取峰值 5 % 时内核仍把等离子体拟丢（外迭代刚过 warmup 即空掩码；relax /
    #: warmup / fb_gain 各调一档都一样），20 % 时一步收敛、chi2_kin ~ 2e-7。这是求解器对紧约束行的
    #: 稳健性上限，不是数据的问题。所以先按实测 sigma 进，拒了就整体放宽 sigma，**放宽倍数写进结果**。
    fa = fi = notes = None
    attempts = []
    for scale in a.sigma_scales:
        rows_s = dict(rows, **{"fylite:pressure_weight": rows["fylite:pressure_weight"] / scale})
        try:
            fa, fi, notes = door("code/reconstruction", st, {"device": c.card, "discharge": dict(disc0, **rows_s)})
            attempts.append({"sigma_scale": scale, "ok": True})
            break
        except Exception as e:                           # noqa: BLE001 — 拒绝也是读数
            attempts.append({"sigma_scale": scale, "ok": False, "error": str(e)[-40:]})
    if fa is None:
        return {"status": "error", "error": "每一档 sigma 放宽都被拒", "attempts": attempts, "points": points}
    sigma_scale = attempts[-1]["sigma_scale"]
    log(f"P: kinetic rows entered at sigma x {sigma_scale:g} ({len(attempts)} attempt(s))")
    xf = [psin_at(fa, fi, ri, zi) for ri, zi in zip(r, z)]
    model = np.interp(np.clip(xf, 0, 1), fi["psin_1d"], fi["pres"])
    for pt, xv, mv in zip(points, xf, model):
        pt["psin_final"] = _r(xv, 4)
        pt["model_p"] = _r(mv, 5)
        pt["resid_sigma"] = _r((mv - pt["p"]) / pt["sigma"], 4) if pt["used"] else None
        pt["resid_sigma_entered"] = _r((mv - pt["p"]) / (pt["sigma"] * sigma_scale), 4) if pt["used"] else None
    log(f"P: q0 {fa['q0']:.3f}, {int(fa.get('kinetic_passes_run', 1))} pass(es), best {int(fa.get('kinetic_best_pass', 1))}, "
        f"map shift {fa.get('kinetic_map_shift', float('nan')):.2e}, chi2_kin {fa.get('chi2_kin', float('nan')):.2f}")
    return tier_view(fa, fi, zc, {
        "label": "P · 磁" + (" + POINT" if stacked else "") + " + Thomson 压强",
        "constraints": ["磁（同 M）"] + (["POINT 法拉第行（同 K）"] if stacked else [])
                       + [f"Thomson 压强点 × {int(keep.sum())}（逐点实测 σ）"]
                       + ([f"快离子份额 {a.p_fast_frac:g}（声明）"] if a.p_fast_frac > 0 else [])
                       + ([f"曲率正则 λ = {a.curv:g}"] if a.curv > 0 else []),
        "channels": c.channel_table(fi), "notes": notes,
        "certificate": {"chi2_per_dof": _r(fi.get("kinetic_pass_chi2_per_dof", []), 5),
                        "map_shift": _r(fi.get("kinetic_pass_map_shift", []), 4),
                        "best_pass": int(fa.get("kinetic_best_pass", 1)), "tol": a.kinetic_tol},
        "sigma_scale": sigma_scale, "attempts": attempts, "on": "K" if stacked else "M",
        "passes_note": ("叠在 K 上：外环在行给定档不重映，只跑一遍" if stacked else ""),
        "thomson": {"points": points, "sample_time_s": th.get("sample_time_s"), "ti0": th.get("ti0"),
                    "te0": p.get("te0"), "ion_factor": p.get("ion_factor"), "n_dropped_quality": p.get("n_dropped"),
                    "sigma_source": p.get("sigma_source"), "assumptions": p.get("assumptions"),
                    "psin_max": a.psin_max}})


# ================================================================================================ run

def cmd_run(a) -> int:
    from fylite import device, kernel
    import fylite
    meas, th, origin = load_input(a.input, a.time, a.thomson)
    shot, t = int(meas["shot"]), float(meas["time_s"])
    chain = meas.get("measurement_chain", "east")
    card = device.document(shot=shot, measurement_chain=chain)
    t0 = time.time()
    c = Case(meas, card, a.loops)
    settings = dict(SETTINGS, npp=a.npp, nff=a.nff)
    out = {"@type": "fylite:KineticReconResult", "app": APP, "version": VERSION,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "shot": shot, "time_s": t, "measurement_chain": chain, "origin": origin,
           "source": sanitize(meas.get("source")),
           "fylite": {"version": getattr(fylite, "__version__", None), "kernel_abi": getattr(kernel, "ABI_VERSION", None)},
           "settings": {"npp": a.npp, "nff": a.nff, "loops": a.loops, "reject_sigma": a.reject_sigma,
                        "point_off": a.point_off, "p_on": a.p_on, "dead_sigma": a.dead_sigma, "kinetic_passes": a.kinetic_passes,
                        "kinetic_tol": a.kinetic_tol, "thomson_clip": a.thomson_clip, "sigma_scales": a.sigma_scales, "curv": a.curv, "p_fast_frac": a.p_fast_frac, "psin_max": a.psin_max,
                        "serror": SERROR, "loop_floor": LOOP_FLOOR, "probe_floor": PROBE_FLOOR,
                        "sigpol": SIGPOL, "signel": SIGNEL},
           "inputs": {"ip": _r(meas["plasma"]), "b_tor": _r(c.b_tor), "b_tor_from": c.bt_from, "r0": card["tf"]["r0"],
                      "pf_aturns": _r(c.brsp), "n_loops": len(c.coils), "n_probes": len(c.probes),
                      "excluded": c.excluded, "has_point": bool((meas.get("point") or {}).get("bpolar")),
                      "has_thomson": th is not None},
           "device": {"limiter": None,
                      "loops": [{"name": n, "rz": rz} for n, rz in zip(c.loop_names, c.loop_rz)],
                      "probes": [{"name": n, "rz": rz} for n, rz in zip(c.probe_names, c.probe_rz)],
                      "chords": [{"name": _name(ch), "los": ch.get("line_of_sight")}
                                 for ch in (card.get("polarimeter") or {}).get("channel", [])]},
           "tiers": {}}
    tiers = set(a.tiers.upper())
    m_view, base_m = tier_m(c, a.reject_sigma, a.max_rounds, a.per_round, settings, a.loops == "B+readmit")
    out["tiers"]["M"] = m_view
    if base_m is not None:
        fa, fi, _ = base_m
        out["device"]["limiter"] = {"r": _r(fi["limiter_r"], 5), "z": _r(fi["limiter_z"], 5)}
    base_k, kin = None, None
    if "K" in tiers and base_m is not None:
        k_view, base_k, kin = tier_k(c, base_m, a.point_off, a.dead_sigma, settings)
        out["tiers"]["K"] = k_view
    if "P" in tiers and base_m is not None:
        if th is None:
            out["tiers"]["P"] = {"status": "skipped", "why": "没有 Thomson（pull 时没取到，或没给 --thomson）"}
        else:
            use_k = base_k is not None and a.p_on == "K"
            out["tiers"]["P"] = tier_p(c, base_k if use_k else base_m, kin if use_k else None, th, a, settings)
    out["seconds"] = round(time.time() - t0, 1)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    log(f"-> {a.out} ({Path(a.out).stat().st_size / 1e3:.0f} kB, {out['seconds']} s)")
    return 0 if m_view.get("status") == "ok" else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kinetic_recon.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull", help="取数：原始树 + Thomson → 测量文档")
    p.add_argument("--shot", type=int, required=True)
    p.add_argument("--time", type=float, required=True, help="时刻 [s]")
    p.add_argument("--chain", default="east", help="测量链（缺省 east）")
    p.add_argument("--timeout", type=float, default=120.0, help="mdsip 读超时 [s]（east 树打开可能要一分钟）")
    p.add_argument("--no-thomson", action="store_true")
    p.add_argument("--thomson-only", action="store_true", help="只取 Thomson（与已有的磁测量件配合用）")
    p.add_argument("-o", "--out", required=True)
    r = sub.add_parser("run", help="反演：测量文档 → 结果 JSON")
    r.add_argument("input", help="pull 的输出 · 原始树归约件 raw_slices_*.json · 或裸测量字典")
    r.add_argument("--time", type=float, help="归约件里取哪一片（取最近）")
    r.add_argument("--thomson", help="另给的 Thomson（pull --thomson-only 的输出）")
    r.add_argument("--tiers", default="MKP", help="跑哪几档（缺省 MKP；M 总是跑）")
    r.add_argument("--npp", type=int, default=2)
    r.add_argument("--nff", type=int, default=2)
    r.add_argument("--loops", choices=("B+readmit", "B", "all"), default="B+readmit",
                   help="磁通环起步组：FL*B 组起步、收敛后按残差回收其余（缺省）· 只 B 组 · 全部")
    r.add_argument("--reject-sigma", type=float, default=5.0, help="档 M 剔道阈值 [sigma]")
    r.add_argument("--max-rounds", type=int, default=6)
    r.add_argument("--per-round", type=int, default=4)
    r.add_argument("--point-off", type=lambda s: [int(x) for x in s.split(",") if x], default=[],
                   help="手动关掉的 POINT 弦（1 起，逗号分隔；B-06 主集为 4,7,8,11）")
    r.add_argument("--dead-sigma", type=float, default=8.0, help="零假设残差超过它的 POINT 行判为死道")
    r.add_argument("--kinetic-passes", type=int, default=6)
    r.add_argument("--kinetic-tol", type=float, default=1e-3)
    r.add_argument("--psin-max", type=float, default=0.98, help="Thomson 点只收 psi_N 小于它的（分离面附近不收）")
    r.add_argument("--sigma-floor", type=float, default=0.05, help="Thomson 压强 sigma 的相对下限")
    r.add_argument("--thomson-clip", type=float, default=4.0, help="Thomson 点离光滑拟合超过它（sigma）就剔")
    r.add_argument("--sigma-scales", type=lambda s: [float(x) for x in s.split(",") if x],
                   default=[1, 1.5, 2, 3, 4, 6, 8], help="档 P 的 sigma 续延：依次试这些放宽倍数，取第一个收敛的")
    r.add_argument("--p-fast-frac", type=float, default=0.0, help="声明的快离子压强份额（缺省 0 = 不扣）")
    r.add_argument("--curv", type=float, default=0.0, help="p′ / FF′ 曲率正则权重（缺省 0 = 关）")
    r.add_argument("--p-on", choices=("M", "K"), default="M",
                   help="档 P 叠在哪一档上：M（缺省，外环照常）· K（叠 POINT 行；外环在那一档不重映，只跑一遍）")
    r.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    return cmd_pull(a) if a.cmd == "pull" else cmd_run(a)


if __name__ == "__main__":
    raise SystemExit(main())
