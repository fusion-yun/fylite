"""锯齿反转半径的**取数**（ECE · SXR 窗）——判读在内核里。

★★2026-09-26 起崩塌检测、ΔTₑ(R) 与 R_inv、每档的 q=1 面判读（``sawtooth`` 块）和档 Q（反转半径作 q=1 面约束）都在内核的
``code/kinetic`` 里（``src/door/case/kinetic/q.rs``，用户裁定「收敛动理学平衡重构进 rust 内核」）；本文件只剩
取数：``pull_sawtooth`` 把 t ± 0.3 s 的 ECE（``hrs_east:\\TE_HRS``）与中心 SXR 弦（缺省 ``east:\\SXR23U``）读进测量文档的
``measurements.sawtooth`` 块，内核按那一块判读。方法与判读表见 README §3.10。"""
from __future__ import annotations

import math

SAW_HALF_S = 0.3          #: 取数窗：t ± 0.3 s
SXR_BIN_S = 1e-4          #: SXR 分箱 0.1 ms
#: 装置文档还没有 SXR 绑定时的缺省触发弦（#164437 实测：250 kHz，−7…10 s）
SXR_DEFAULT = {"tree": "east", "node": "\\SXR23U", "scale": 1.0, "units": "a.u.",
               "from": "应用缺省（装置文档还没有 soft_x_rays 绑定）"}


def _fin(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


# ================================================================================================ fetch
def _signal(doc: dict, ids: str, key: str):
    return ((doc.get(ids) or {}).get("fylite:signal") or {}).get(key)


def read_sawtooth(s, doc: dict, shot: int, t: float, half: float = SAW_HALF_S) -> dict:
    """在一条已开的 mdsip 会话上读 ECE 整阵与 SXR 触发弦的 t ± half 窗（SXR 分箱到 0.1 ms）。
    返回 {window_s, ece: {t, te [[逐道]], r, z, source} | {why}, sxr: {t, v, dt_raw, source} | {why}}。"""
    out = {"window_s": [round(t - half, 6), round(t + half, 6)]}
    te_s, r_s, z_s = _signal(doc, "ece", "te"), _signal(doc, "ece", "r"), _signal(doc, "ece", "z")
    if not (te_s and r_s):
        out["ece"] = {"why": "装置文档没有 ECE 绑定"}
    else:
        try:
            s.tree = None
            s.open_tree(te_s["tree"], shot)
            v, dims = s.read("data", te_s["node"])
            tb = s.read("dim_of", te_s["node"])[0]
            r = s.read("data", r_s["node"])[0]
            z = s.read("data", z_s["node"])[0] if z_s else [0.0] * len(r)
            nch = len(r)
            if len(dims) == 2 and dims[0] != nch and dims[1] == nch:
                raise RuntimeError(f"ECE 整阵的维 {dims} 与道数 {nch} 对不上")
            idx = [i for i in range(min(len(tb), len(v) // max(nch, 1))) if abs(tb[i] - t) <= half]
            sc = te_s.get("scale", 1.0)
            out["ece"] = {"t": [round(tb[i], 6) for i in idx],
                          "te": [[round(v[i * nch + k] * sc, 2) for k in range(nch)] for i in idx],
                          "r": [round(x, 5) for x in r], "z": [round(x, 5) for x in z],
                          "source": {"tree": te_s["tree"], "node": te_s["node"], "r": r_s["node"],
                                     "z": z_s["node"] if z_s else None, "n_channels": nch}}
        except Exception as e:                           # noqa: BLE001 — 取不到只记下
            out["ece"] = {"why": f"读 ECE 失败：{type(e).__name__}: {e}"[:300]}
    sx = _signal(doc, "soft_x_rays", "sawtooth_trigger") or SXR_DEFAULT
    try:
        s.tree = None
        s.open_tree(sx["tree"], shot)
        v = s.read("data", sx["node"])[0]
        tb = s.read("dim_of", sx["node"])[0]
        n = min(len(v), len(tb))
        i0 = next((i for i in range(n) if tb[i] >= t - half), n)
        i1 = next((i for i in range(i0, n) if tb[i] > t + half), n)
        dt = (tb[min(i0 + 1000, n - 1)] - tb[i0]) / max(min(1000, n - 1 - i0), 1) if n > i0 + 1 else float("nan")
        nb = max(int(round(SXR_BIN_S / dt)), 1) if _fin(dt) and dt > 0 else 1
        tt, vv = [], []
        for j in range(i0, i1 - nb + 1, nb):
            tt.append(round(sum(tb[j:j + nb]) / nb, 7))
            vv.append(round(sum(v[j:j + nb]) / nb * sx.get("scale", 1.0), 6))
        out["sxr"] = {"t": tt, "v": vv, "dt_raw": dt,
                      "source": {k: sx.get(k) for k in ("tree", "node", "from") if sx.get(k)}}
    except Exception as e:                               # noqa: BLE001
        out["sxr"] = {"why": f"读 SXR 失败：{type(e).__name__}: {e}"[:300]}
    return out


def pull_sawtooth(lib, shot: int, t: float, chain: str, server, timeout_s: float) -> dict:
    """``pull`` 与配置运行用：自己开一条 mdsip 会话读 :func:`read_sawtooth`。"""
    import kinetic_recon as K
    doc, _ = lib.device("east", shot, chain)
    host, port = K.server_of(server)
    s = lib.mds_open(host, port, timeout_s)
    try:
        return read_sawtooth(s, doc, shot, t)
    finally:
        s.close()
