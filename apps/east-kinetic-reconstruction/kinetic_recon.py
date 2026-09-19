#!/usr/bin/env python3
"""EAST 实验数据动理学平衡反演：原始测量 → 约束阶梯 M / K / P → 一份结果 JSON（页面读它）。

两条命令::

    python kinetic_recon.py pull --shot 137985 --time 4.041 -o meas.json      # 取数（mdsip）
    python kinetic_recon.py run  meas.json -o result.json                      # 反演三档

★★独立发行：只用 Python 标准库（ctypes · json · math）与**一个** ``libfylite.so``——不 import
fylite 的 Python 包，也不要 numpy。库里有三样本应用要的东西：

* 内核的文档门 ``fylite_runtime_case_tree_json``——每一次物理计算（线圈份额、反演、弦积分、剖面拟合）；
* 编进库里的装置事实 ``fylite_runtime_facts_*`` 与解析规则 ``fylite_runtime_device_resolve``——
  EAST 在这一炮、这条测量链上的装置描述，不读盘上的装置文件；
* mdsip 客户端 ``fylite_runtime_mds_*``——取数。

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

库在哪：缺省是本文件旁边的 ``libfylite.so``（一个位置，不搜索）；``--lib`` 显式给另一份。
取数另要 ``$FYLITE_MDSIP_SERVER=主机:端口``（或 ``--server``）。
"""
from __future__ import annotations

import argparse
import bisect
import concurrent.futures
import ctypes
import datetime
import itertools
import json
import math
import multiprocessing
import operator
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = "east-kinetic-reconstruction"
VERSION = "0.2.0"
DEFAULT_LIB = HERE / "libfylite.so"

#: sigma = max(SERROR·|读数|, 位下限)——KEFIT / EFIT 的 data_input 约定（B-06 §7.1 两个代码同用）
SERROR = 0.05
LOOP_FLOOR = 5e-4          #: Wb/rad
PROBE_FLOOR = 7.52541e-4   #: T（KEFIT efit/2016/bitmp2.txt 的中位）
#: POINT 的 sigma：KEFIT GUI 缺省（B-06 §2.2）
SIGPOL, SIGNEL = 0.05, 0.3
TF_NODE = r"\TOP.T2:TFP"
TF_TURNS = 130 * 16        #: EAST TF：16 线圈 × 130 匝（B-06 §7.1）
DRIFT_WINDOW = (-6.9, -6.1)  #: 炮前线性漂移的拟合窗 [s]
WINDOW_MS = 5.0              #: 磁测量窗口均值的半宽 [ms]
FRINGE_GATE = 0.15           #: POINT 干涉条纹闸
E_CHARGE = 1.602176634e-19

SETTINGS = {"npp": 2, "nff": 2, "relax": 0.3, "max_iter": 4000, "tol": 1e-8, "fb_gain": 8.0, "warmup": 40,
            "n_profile": 201, "n_q": 20, "n_theta": 121, "x_lo": 0.06, "x_hi": 0.995}
ZC_SCAN = [round(-0.030 + 0.004 * k, 3) for k in range(16)]
#: 竖直设定点扫描的做法（``--scan``）。``full``：每轮每个设定点都在 65² 上冷启动解，取收敛者中 chi2 最小的。
#: ``coarse``：每轮先把全部设定点在 ``grid``² 的粗网格上解一遍、按粗 chi2 排序，只把最好的 ``top`` 个在 65² 上冷启动
#: 复核，再从其中最好的往两侧邻点走（65²），直到两侧都不更好；粗网格上收敛的不到 ``min_converged``（份额），或复核的
#: 无一收敛，这一轮退回全扫。粗网格只用来排序——报出的解与剔道依据总是 65² 上的冷启动解。
#: ★门槛与 top=4 是在 12 片上量出来的：top=3、不走邻点、不设门槛时 12 片里 3 片的答案与全扫不同（见 README）。
SCAN_FULL = {"mode": "full"}
SCAN_COARSE = {"mode": "coarse", "grid": 33, "top": 4, "min_converged": 0.5}
#: 档 M 反演外迭代的 Anderson 混合深度（``--anderson``；内核 ``code/reconstruction`` 的 ``anderson``，0 = 纯 Picard）。
#: 只加速日程之后的 Picard 尾巴，终点是同一个不动点（内核 docs/note/gs-anderson.md）；粗扫的粗网格、65² 复核与全扫
#: 三种调用都带它。只用在档 M——K / P 的反演照旧（没有在它们上面验过）。0 时不写这个键，与旧库逐位相同。
#: ★缺省曾是 10（24 片上与 0 逐片比过）；2026-09-19（晚）起缺省改走 Newton–Krylov（``NEWTON_KRYLOV``），这里缺省 0。
#: 理由见 README〈加速器的复核：Newton–Krylov 对 Anderson〉。
ANDERSON = 0
#: 档 M 反演外迭代的 Newton–Krylov（JFNK）深度（``--nk``；内核 ``code/reconstruction`` 的 ``newton_krylov``，0 = 不用）。
#: 同 Anderson 一样只在日程之后介入、失败即回卷成纯 Picard（不会多出拒绝）；但它能让纯 Picard 解不出（被拒 / 跑满
#: max_iter）的设定点收敛——这些点会进入扫描比较，终点可能因此移动（内核 docs/note/gs-newton-krylov-von-hagenow.md）。
#: 与 ``anderson`` 同时给时 Newton 先上，它连败 4 次才交给 Anderson。0 时不写这个键。
#: ★缺省 10 是在同样 24 片 + #63948 全炮 35 片上与纯 Picard、``anderson 10`` 三方逐片比过之后定的：终点与纯 Picard
#: 22 / 24 片、33 / 35 片相同（不同的片都是它救活了纯 Picard 解不出的设定点），三者里最快（README〈加速器的复核〉）。
NEWTON_KRYLOV = 10
#: 一轮里互相独立的反演调用（粗扫的全部粗网格点、65² 复核的前几名、邻点的两侧、热启动的 5 点扫、全扫的 16 点）
#: 同时交给几个工作进程（``--jobs``；1 = 串行，与旧版逐位相同）。每个工作进程自己载一份 libfylite.so（ctypes 句柄
#: 不能跨进程传）：传过去的是请求（code + settings + inputs），传回来的是门的记录（或拒绝）。门是确定的、单线程的，
#: 结果按串行的次序归并——读数、选中的解、剔道与串行**逐位相同**（README〈并行〉有核对）。
JOBS = max(1, min(16, os.cpu_count() or 1))


def log(msg: str) -> None:
    print(f"[{APP}] {msg}", file=sys.stderr, flush=True)


def sanitize(text):
    """服务器地址不出门：``mdsplus:<host>:<port>:…`` → ``mdsplus:mds.invalid:…``。"""
    if not isinstance(text, str):
        return text
    return re.sub(r"(mdsplus:)[^:]+:\d+:", r"\1mds.invalid:", text)


# ================================================================================================ small numerics
#: numpy 不在依赖里；本应用的数值只有这几样，写在这里，一眼看得完。

def flat(x) -> list:
    """任意嵌套列表摊平成一维。"""
    if not isinstance(x, list):
        return [x]
    out = []
    for v in x:
        out.extend(flat(v)) if isinstance(v, list) else out.append(v)
    return out


def fin(v) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def median(v: list) -> float:
    s = sorted(v)
    n = len(s)
    if not n:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def mean(v: list) -> float:
    return sum(v) / len(v)


def interp(x: float, xp: list, fp: list) -> float:
    """numpy.interp 的一点版本：xp 递增，两端夹住。"""
    if x <= xp[0]:
        return fp[0]
    if x >= xp[-1]:
        return fp[-1]
    j = bisect.bisect_right(xp, x) - 1
    t = (x - xp[j]) / (xp[j + 1] - xp[j])
    return fp[j] + t * (fp[j + 1] - fp[j])


def linfit(x: list, y: list) -> tuple[float, float]:
    """一次最小二乘 y ≈ a·x + b（numpy.polyfit(x, y, 1) 的同一个解）。"""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    a = sxy / sxx if sxx else 0.0
    return a, my - a * mx


def _r(x, n=6):
    """JSON 里的数：有效数字截到 n 位，非有限写 null。"""
    if isinstance(x, (list, tuple)):
        return [_r(v, n) for v in x]
    if x is None:
        return None
    x = float(x)
    return float(f"{x:.{n}g}") if math.isfinite(x) else None


# ================================================================================================ libfylite.so

class KernelError(RuntimeError):
    """库或它的门本身出错（不是物理上的拒绝）。"""


class Refused(RuntimeError):
    """内核按名拒绝了这一次计算（``record['refusal']``）。"""


_U8P = ctypes.POINTER(ctypes.c_uint8)


def _bytes(text: str):
    raw = text.encode("utf-8")
    buf = (ctypes.c_uint8 * max(len(raw), 1)).from_buffer_copy(raw + b"\0")
    return ctypes.cast(buf, _U8P), len(raw), buf


class Lib:
    """``libfylite.so`` 的三扇门：内核文档门、装置事实、mdsip 客户端。"""

    def __init__(self, path: Path):
        if not path.is_file():
            raise SystemExit(f"找不到 {path}：把 libfylite.so 放在 {HERE} 下，或用 --lib 指一份"
                             "（取法见 README〈库〉一节）")
        self.path = path
        self.lib = ctypes.CDLL(str(path))
        L = self.lib
        L.fylite_runtime_case_tree_json.argtypes = [ctypes.c_char_p, ctypes.c_uint64] * 3 + [
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint64)]
        L.fylite_runtime_case_tree_json.restype = ctypes.c_int32
        L.fylite_runtime_case_free.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        L.fylite_runtime_case_free.restype = None
        for n in ("fylite_runtime_facts_ids", "fylite_runtime_facts_doc", "fylite_runtime_facts_resolution",
                  "fylite_runtime_device_resolve"):
            getattr(L, n).restype = ctypes.c_int64
        L.fylite_runtime_device_resolve.argtypes = [ctypes.c_char_p, ctypes.c_uint64] * 4 + [_U8P, ctypes.c_uint64]
        L.fylite_runtime_mds_open.argtypes = [_U8P, ctypes.c_uint64, ctypes.c_uint16, _U8P, ctypes.c_uint64,
                                              ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p), _U8P, ctypes.c_uint64]
        L.fylite_runtime_mds_open.restype = ctypes.c_int32
        L.fylite_runtime_mds_open_tree.argtypes = [ctypes.c_void_p, _U8P, ctypes.c_uint64, ctypes.c_int64]
        L.fylite_runtime_mds_open_tree.restype = ctypes.c_int32
        L.fylite_runtime_mds_read.argtypes = [ctypes.c_void_p, ctypes.c_int32, _U8P, ctypes.c_uint64,
                                              ctypes.POINTER(ctypes.c_int64), ctypes.c_uint64, ctypes.c_int32,
                                              ctypes.POINTER(ctypes.c_uint64)]
        L.fylite_runtime_mds_read.restype = ctypes.c_int32
        L.fylite_runtime_mds_last_f64.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double), ctypes.c_uint64]
        L.fylite_runtime_mds_last_f64.restype = ctypes.c_int32
        L.fylite_runtime_mds_last_dims.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint64,
                                                   ctypes.POINTER(ctypes.c_uint64)]
        L.fylite_runtime_mds_last_dims.restype = ctypes.c_int32
        L.fylite_runtime_mds_last_error.argtypes = [ctypes.c_void_p, _U8P, ctypes.c_uint64]
        L.fylite_runtime_mds_last_error.restype = ctypes.c_int64
        L.fylite_runtime_mds_close.argtypes = [ctypes.c_void_p]
        L.fylite_runtime_mds_close.restype = None

    # ---- 两段式读：先问长度，再给缓冲 ----
    @staticmethod
    def _ask(fn, *args):
        n = fn(*args, None, 0)
        if n < 0:
            return int(n)
        if n == 0:
            return ""
        buf = (ctypes.c_uint8 * int(n))()
        got = fn(*args, ctypes.cast(buf, _U8P), n)
        if got < 0:
            return int(got)
        return bytes(buf)[: min(int(got), int(n))].decode("utf-8", "replace")

    # ---- 内核文档门 ----
    def door(self, code: str, settings: dict, inputs: dict):
        """一份请求进、一份记录出：(facts{key: 数}, fields{key: 列表}, notes)。"""
        cb = code.encode()
        jb = json.dumps({"settings": settings, "inputs": inputs}, allow_nan=True).encode()
        out, n = ctypes.c_void_p(), ctypes.c_uint64(0)
        rc = self.lib.fylite_runtime_case_tree_json(cb, len(cb), jb, len(jb), b"", 0, ctypes.byref(out), ctypes.byref(n))
        try:
            text = ctypes.string_at(out, n.value).decode("utf-8", "replace") if out.value and n.value else ""
        finally:
            if out.value and n.value:
                self.lib.fylite_runtime_case_free(out, n)
        if rc < 0:
            raise KernelError(f"{code}: fylite_runtime_case_tree_json 返回 {rc}：{text[:300]}")
        rec = json.loads(text) if text else {}
        if rc == 1:
            ref = rec.get("refusal") or {}
            raise Refused(f"the kernel refused ({ref.get('code', rc)}): {ref.get('message', text[:300])}")
        fa = {k: v["value"] for k, v in (rec.get("facts") or {}).items() if isinstance(v.get("value"), (int, float))}
        fi: dict = {}

        def walk(node, path):                            #: 按 IDS 嵌套的字段摊平成 "ids/路径" 键；原始字段键不变
            for k, v in node.items():
                key = f"{path}/{k}" if path else k
                if isinstance(v, dict) and "data" in v:
                    fi[key] = v["data"]
                elif isinstance(v, dict):
                    walk(v, key)
        walk(rec.get("fields") or {}, "")
        return fa, fi, list(rec.get("notes") or [])

    def linked_kernel(self) -> dict:
        out, n = ctypes.c_void_p(), ctypes.c_uint64(0)
        fn = self.lib.fylite_runtime_linked_kernel
        fn.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint64)]
        fn.restype = ctypes.c_int32
        info = {}
        if fn(ctypes.byref(out), ctypes.byref(n)) == 0 and out.value and n.value:
            try:
                info = json.loads(ctypes.string_at(out, n.value).decode("utf-8", "replace")) or {}
            finally:
                self.lib.fylite_runtime_case_free(out, n)
        try:
            self.lib.fylite_rs_abi_version.restype = ctypes.c_uint32
            info["abi"] = int(self.lib.fylite_rs_abi_version())
        except AttributeError:
            pass
        return info

    # ---- 装置：编进库里的事实 + 运行时的解析规则 ----
    def device(self, device_id: str, shot: int, chain: str) -> tuple[dict, dict]:
        """(这一炮、这条测量链上的装置文档, 解析文档)。"""
        d, i = b"device", device_id.encode()
        doc = self._ask(self.lib.fylite_runtime_facts_doc, d, len(d), i, len(i))
        res = self._ask(self.lib.fylite_runtime_facts_resolution, d, len(d), i, len(i))
        if not isinstance(doc, str) or not doc or not isinstance(res, str) or not res:
            have = self._ask(self.lib.fylite_runtime_facts_ids, d, len(d))
            raise SystemExit(f"这份 libfylite.so 没有编进装置 {device_id!r}（它有：{have}）——"
                             "要的是含 EAST 的内部版构建")
        q = json.dumps({"shot": int(shot), "measurement_chain": chain, "strict": False}).encode()
        c, r = doc.encode(), res.encode()
        text = self._ask(self.lib.fylite_runtime_device_resolve, c, len(c), r, len(r), q, len(q), b"document", 8)
        if not isinstance(text, str):
            raise KernelError(f"fylite_runtime_device_resolve 失败（{text}）")
        out = json.loads(text)
        if "error" in out:
            raise SystemExit(f"装置解析：{out['error']}")
        return out["document"], json.loads(res)

    # ---- mdsip ----
    def mds_open(self, host: str, port: int, timeout_s: float) -> "Mds":
        return Mds(self, host, port, timeout_s)


class Mds:
    """一条只读 mdsip 会话（``fylite_runtime_mds_*``）。"""

    VERBS = {"raw": 0, "data": 1, "dim_of": 2}

    def __init__(self, lib: Lib, host: str, port: int, timeout_s: float):
        self.L = lib.lib
        h = ctypes.c_void_p()
        err = (ctypes.c_uint8 * 512)()
        hb, hn, _k1 = _bytes(host)
        ub, un, _k2 = _bytes(os.environ.get("USER") or "fylite")
        rc = self.L.fylite_runtime_mds_open(hb, hn, int(port), ub, un, int(timeout_s * 1000), ctypes.byref(h),
                                            ctypes.cast(err, _U8P), len(err))
        if rc != 0:
            why = bytes(err).split(b"\x00", 1)[0].decode("utf-8", "replace")
            raise KernelError(f"mdsip open failed ({rc}): {why}")
        self.h = h
        self.tree = None

    def _fail(self, what, rc):
        n = self.L.fylite_runtime_mds_last_error(self.h, None, 0)
        buf = (ctypes.c_uint8 * max(int(n), 1))()
        self.L.fylite_runtime_mds_last_error(self.h, ctypes.cast(buf, _U8P), len(buf))
        raise KernelError(f"{what} returned {rc}: {bytes(buf)[:max(int(n), 0)].decode('utf-8', 'replace')}")

    def open_tree(self, tree: str, shot: int) -> None:
        tb, tn, _k = _bytes(tree)
        rc = self.L.fylite_runtime_mds_open_tree(self.h, tb, tn, int(shot))
        if rc != 0:
            self._fail(f"open_tree({tree!r}, {shot})", rc)
        self.tree = tree

    def read(self, verb: str, node: str):
        """(一维值, dims)；dims 按线上约定**最快变化的轴在前**。"""
        nb, nn, _k = _bytes(node)
        n = ctypes.c_uint64()
        sub = (ctypes.c_int64 * 1)()
        rc = self.L.fylite_runtime_mds_read(self.h, self.VERBS[verb], nb, nn, sub, 0, 0, ctypes.byref(n))
        if rc != 0:
            self._fail(f"read({verb!r}, {node!r})", rc)
        out = (ctypes.c_double * max(int(n.value), 1))()
        rc = self.L.fylite_runtime_mds_last_f64(self.h, out, int(n.value))
        if rc != 0:
            self._fail("last_f64", rc)
        nd = ctypes.c_uint64()
        self.L.fylite_runtime_mds_last_dims(self.h, None, 0, ctypes.byref(nd))
        dims = []
        if nd.value:
            db = (ctypes.c_uint64 * int(nd.value))()
            self.L.fylite_runtime_mds_last_dims(self.h, db, int(nd.value), ctypes.byref(nd))
            dims = [int(v) for v in db]
        return list(out[: int(n.value)]), dims

    def rows(self, node: str) -> list:
        """二维节点按行（慢轴）取出：a[i][j]。★线上 dims 快轴在前，所以行长是 dims[0]。"""
        v, dims = self.read("data", node)
        if len(dims) < 2:
            return v
        w = dims[0]
        return [v[i * w:(i + 1) * w] for i in range(len(v) // w)]

    def close(self) -> None:
        if self.h is not None:
            self.L.fylite_runtime_mds_close(self.h)
            self.h = None


def server_of(spec: str | None) -> tuple[str, int]:
    s = spec or os.environ.get("FYLITE_MDSIP_SERVER")
    if not s or ":" not in s:
        raise SystemExit("取数要 mdsip 服务器：--server 主机:端口，或 export FYLITE_MDSIP_SERVER=主机:端口")
    h, p = s.rsplit(":", 1)
    return h, int(p)


# ================================================================================================ device names
#: 取数要的几样名字，从解析后的装置文档里取（与 fylite.device._derive 同一套规则，只取本应用用到的）。

def _aos(node, legacy: str = "channel") -> list:
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        seq = node.get(legacy)
        if isinstance(seq, list):
            return seq
        if isinstance(seq, dict):
            return [seq]
    return []


def _is_fast_coil(coil) -> bool:
    """快速竖直控制线圈（DD ``function`` = b_field_fb，EAST IC1/IC2）不在 12 路 PF 电路里。"""
    return isinstance(coil, dict) and any(isinstance(f, dict) and f.get("name") == "b_field_fb"
                                          for f in (coil.get("function") or ()))


def device_names(doc: dict, resolution: dict) -> dict:
    mag, pf = doc["magnetics"], doc["pf_active"]
    chain = mag.get("measurement_chain")
    table = (resolution.get("manifest") or {}).get("measurement_chains") or {}
    tree = (table.get(chain) or {}).get("tree")
    if not tree:
        raise SystemExit(f"测量链 {chain!r} 在解析文档里没有 tree（有：{sorted(table)}）")
    #: PF 通道：编进库里的文档形把线圈摊开了，通道那一层的事实（读哪个罗氏线圈节点、读数乘多少匝、
    #: 在拟合里排第几）记在 `pf_active/fylite:channel`；卡片形则直接写在通道线圈上。两种都认。
    coils = pf.get("fylite:channel") or [c for c in _aos(pf, "coil") if not _is_fast_coil(c)]
    need = [k for k in ("turns", "efit_index") if not all(k in c for c in coils)]
    if not coils or need:
        raise SystemExit(f"这份装置文档没有 PF 通道的 {need or '条目'}——取 PF 电流要它们；"
                         "要一份带 pf_active/fylite:channel 的 libfylite.so（2026-09-18 之后的构建）")
    mds = (doc.get("data_source") or {}).get("mdsplus") or {}
    itf, pol = doc.get("interferometer") or {}, doc.get("polarimeter") or {}
    gui = (doc.get("operational") or {}).get("gui_v5_fig") or {}
    probes = _aos(mag.get("b_field_pol_probe"))
    return {
        "chain": chain, "tree": tree, "pcs_tree": mds.get("pcs_tree"), "ip_node": mds.get("ip_node"),
        "loops": [c["name"] for c in _aos(mag.get("flux_loop"))],
        "probes": [c["name"] for c in probes],
        "probe_weights": ([float(c["weight"]) for c in probes]
                          if probes and all(isinstance(c, dict) and "weight" in c for c in probes) else None),
        "pf_nodes": [c.get("fylite:mds_node") or c["name"] for c in coils],
        "pf_turns": [int(c["turns"]) for c in coils],
        "pf_order": [int(c["efit_index"]) for c in coils],
        "point_ne": [c["name"] for c in _aos(itf)], "point_fr": [c["name"] for c in _aos(pol)],
        "point_c": float(pol["faraday_constant"]) if pol.get("faraday_constant") is not None else None,
        "point_lambda": float(itf["laser_wavelength"]) if itf.get("laser_wavelength") is not None else None,
        "point_base_s": (pol.get("baseline") or {}).get("centre_s"),
        "point_base_tol": (pol.get("baseline") or {}).get("tolerance_s"),
        "point_window_ms": float(gui["intev_pol"]) * 1e3 if "intev_pol" in gui else None,
    }


# ================================================================================================ pull

_MONOTONE: dict = {}


def _window(tb, n: int, centre: float, half: float) -> range:
    """``tb[:n]`` 里可能落在 ``|tb − centre| ≤ half`` 之内的下标（调用方再按原判据逐个筛，结果与全扫逐位相同）。
    POINT 一条弦 425 万个采样、每片 22 条：时基单调（数字化器的时基总是）时用二分只看窗口附近，不单调才全扫。
    单调与否按时基对象记一次（wei2026 各片共用同一份时序）。"""
    got = _MONOTONE.get(id(tb))
    if got is None or got[0] is not tb:
        got = (tb, all(map(operator.le, tb, itertools.islice(tb, 1, None))))
        _MONOTONE[id(tb)] = got
    if not got[1]:
        return range(n)
    pad = abs(half) * 2.0 + 1e-6                         #: 二分只求一个超集：边界上的浮点毛刺由调用方的原判据定
    return range(bisect.bisect_left(tb, centre - pad, 0, n), bisect.bisect_right(tb, centre + pad, 0, n))


def fringe_gate(mags: list, gate: float) -> list:
    """保留 ``gate·median ≤ |n_e,line| ≤ median/gate`` 的 POINT 弦（条纹跳变两个方向都可能）。"""
    mag = [abs(v) if v is not None else 0.0 for v in mags]
    if gate <= 0:
        return [m > 0 for m in mag]
    nz = [m for m in mag if m > 0]
    med = median(nz) if nz else 0.0
    lo, hi = gate * med, med / gate
    return [m > 0 and lo < m < hi for m in mag]


def reduce_series(get, shot: int, t: float, names: dict, *, source: str) -> dict:
    """原始序列 → 平坦测量字典。GUI_v5 的归约：|t − t₀| ≤ 5 ms 窗口均值，炮前线性漂移扣除；
    POINT 用它自己的窗、先减零偏，再过条纹闸。（与 fylite.io.raw.reduce_series 同一规则，
    本应用用不到的 ELM 相位选项没有搬。）"""
    tree, w = names["tree"], WINDOW_MS / 1000.0
    b0, b1 = DRIFT_WINDOW

    def avg(leaf, where, scale=1.0, required=True, drift=True):
        r = get(leaf, where)
        if r is None:
            if required:
                raise RuntimeError(f"raw reduce: required node {leaf} ({where}) absent")
            return None
        s, tb = r[0], r[1]
        n = min(len(s), len(tb))
        sel = [k for k in _window(tb, n, t, w) if abs(tb[k] - t) <= w]
        if not sel:
            sel = [min(range(n), key=lambda k: abs(tb[k] - t))]
        if drift:                                        #: 漂移只扣在要平均的那几个采样上（逐个与整条扣完再取相同）
            base = [k for k in _window(tb, n, 0.5 * (b0 + b1), 0.5 * (b1 - b0)) if b0 <= tb[k] <= b1]
            if len(base) > 2:
                a, b = linfit([tb[k] for k in base], [s[k] for k in base])
                return mean([s[k] - (a * tb[k] + b) for k in sel]) * scale
        return mean([s[k] for k in sel]) * scale

    coils = [avg(nd, tree, 1.0 / (2.0 * math.pi)) for nd in names["loops"]]
    expmp2, fwtmp2 = [], []
    for i, nd in enumerate(names["probes"]):
        v = avg(nd, tree, required=False)
        expmp2.append(0.0 if v is None else v)
        fwtmp2.append(0.0 if v is None else (names["probe_weights"][i] if names["probe_weights"] else 1.0))
    raw_pf = [avg(nd, tree, names["pf_turns"][i], drift=False) for i, nd in enumerate(names["pf_nodes"])]
    brsp = [raw_pf[i] for i in names["pf_order"]]
    plasma = avg(names["ip_node"], tree, 1000.0, required=False, drift=False) if names["ip_node"] else None
    if plasma is None or abs(plasma) < 5.0e4:
        pcrl = avg(r"\pcrl01", names["pcs_tree"], required=False, drift=False) if names["pcs_tree"] else None
        if pcrl is not None and abs(pcrl) > abs(plasma or 0.0):
            plasma = pcrl
    if plasma is None:
        raise RuntimeError(f"no plasma current for shot {shot}")
    meas = {"shot": int(shot), "time_s": float(t), "itime_ms": int(round(t * 1000)),
            "plasma": abs(plasma), "brsp": brsp, "coils": coils, "expmp2": expmp2, "fwtmp2": fwtmp2,
            "n_probe_active": sum(1 for v in fwtmp2 if v > 0), "measurement_chain": names["chain"],
            "probe_weight_rule": "device" if names["probe_weights"] else "unit", "source": source}

    if names["point_ne"] and names["point_window_ms"]:
        pw = names["point_window_ms"] / 1e3
        base_s, base_tol = names["point_base_s"], names["point_base_tol"]

        def chord(node):
            r = get(node, tree)
            if r is None:
                return None
            s, tb = r[0], r[1]
            n = min(len(s), len(tb))
            base = [s[k] for k in _window(tb, n, base_s, base_tol) if abs(tb[k] - base_s) < base_tol]
            off = mean(base) if base else 0.0
            sel = [k for k in _window(tb, n, t, pw) if abs(tb[k] - t) <= pw]
            if not sel:
                sel = [min(range(n), key=lambda k: abs(tb[k] - t))]
            return mean([s[k] - off for k in sel])

        ne_l = [chord(nd) for nd in names["point_ne"]]
        fr_l = [chord(nd) for nd in names["point_fr"]]
        kpol = -1.0 if (fr_l[0] is not None and fr_l[0] < 0) else 1.0
        c_far = names["point_c"] * names["point_lambda"] ** 2
        good_l = fringe_gate(ne_l, FRINGE_GATE)
        bnel, bpolar, fwtnel, fwtpol, dropped = [], [], [], [], []
        for i, (a_ne, b_fr, good) in enumerate(zip(ne_l, fr_l, good_l)):
            if a_ne is not None and not good:
                dropped.append(i + 1)
            bnel.append(abs(a_ne) if a_ne is not None else 0.0)
            fwtnel.append(1.0 if good else 0.0)
            bpolar.append((kpol * b_fr / c_far / 2.0 * math.pi / 180.0) / 1e19 if b_fr is not None else 0.0)
            fwtpol.append(1.0 if (good and b_fr is not None) else 0.0)
        meas["point"] = {"n_chord": len(names["point_ne"]), "kpol": kpol, "bnel": bnel, "bpolar": bpolar,
                         "fwtnel": fwtnel, "fwtpol": fwtpol, "n_ne_active": int(sum(fwtnel)),
                         "n_fr_active": int(sum(fwtpol)), "fringe_dropped": dropped}
    return meas


def pull_magnetics(lib: Lib, shot: int, t: float, chain: str, server, timeout_s: float) -> dict:
    """原始树 → 平坦测量字典，外加 TF 线圈电流算出的真空 F（B_T 节点自 #97286 起是伏特，B-06 §7.1）。"""
    doc, res = lib.device("east", shot, chain)
    names = device_names(doc, res)
    host, port = server_of(server)
    s = lib.mds_open(host, port, timeout_s)

    def get(leaf, where):
        nd = leaf if leaf.startswith("\\") else "\\" + leaf
        if where != s.tree:
            s.open_tree(where, int(shot))
        try:
            v, _ = s.read("data", nd)
            tb, _ = s.read("dim_of", nd)
            return v, tb
        except KernelError:                              # 节点不在：是数据，不是故障
            return None

    try:
        tf, tf_node = tf_series(get, names, (doc.get("data_source") or {}).get("mdsplus") or {}, t)
        meas = reduce_series(get, shot, t, names, source=f"mdsplus:mds.invalid:{names['tree']}:{shot}")
    finally:
        s.close()
    if tf is not None:
        v, tb = tf
        sel = [v[k] for k in range(min(len(v), len(tb))) if abs(tb[k] - t) <= 0.005]
        i_tf = mean(sel) if sel else v[min(range(len(tb)), key=lambda k: abs(tb[k] - t))]
        meas["tf"] = {"node": tf_node, "i_tf_A": i_tf, "turns_total": TF_TURNS, "f_vac_Tm": 2e-7 * TF_TURNS * i_tf}
    return meas


def tf_series(get, names: dict, mds: dict, t: float):
    """TF 线圈电流的序列与节点：先 ``TF_NODE``；旧炮没有它（#63948 · #81481 实测 2026-09-18：节点不在），退到装置文档
    的 ``btor_node``——只在它读来像 TF 电流时（|I| > 1 kA；#63948 上它读 −11.1 kA，#137985 上同一节点读 −4，
    那时 ``TF_NODE`` 在，用不到它）。"""
    tf = get(TF_NODE, names["tree"])
    if tf is not None:
        return tf, TF_NODE
    alt = mds.get("btor_node")
    if alt:
        r = get(alt, names["tree"])
        if r is not None:
            v, tb = r
            sel = [v[k] for k in range(min(len(v), len(tb))) if abs(tb[k] - t) <= 0.005]
            if sel and abs(mean(sel)) > 1e3:
                return r, alt
    return None, None


def pull_thomson(lib: Lib, shot: int, t: float, server, timeout_s: float) -> dict:
    """芯部 Thomson 离 t 最近的一个脉冲（``ts_east``）+ TXCS 芯部 T_i0（``analysis``，±0.2 s 均值）。
    ★``\\TE_CORETS`` 一类二维节点的每一行是一个脉冲、第 0 列是时刻。"""
    host, port = server_of(server)
    s = lib.mds_open(host, port, timeout_s)
    try:
        s.open_tree("ts_east", int(shot))
        te2, ne2 = s.rows(r"\TE_CORETS"), s.rows(r"\NE_CORETS")
        r, z = s.read("data", r"\R_CORETS")[0], s.read("data", r"\Z_CORETS")[0]
        it = min(range(len(te2)), key=lambda k: abs(te2[k][0] - t))
        sample_t = te2[it][0]
        te, ne = te2[it][1:], ne2[it][1:]
        te_err = ne_err = None
        try:
            teE, neE = s.rows(r"\TE_CORETSERR"), s.rows(r"\NE_CORETSERR")
            if len(teE) == len(te2) and len(neE) == len(ne2):
                te_err, ne_err = teE[it][1:], neE[it][1:]
        except KernelError:
            pass
        npts = min(len(te), len(ne), len(r), len(z))
        te, ne, r, z = te[:npts], ne[:npts], r[:npts], z[:npts]
        if te_err is not None:
            te_err, ne_err = te_err[:npts], ne_err[:npts]
        ti0 = None
        try:
            s.open_tree("analysis", int(shot))
            tiv, tit = s.read("data", r"\TI0_TXCS")[0], s.read("dim_of", r"\TI0_TXCS")[0]
            sel = [tiv[k] for k in range(min(len(tiv), len(tit))) if abs(tit[k] - sample_t) <= 0.2]
            ti0 = mean(sel) if sel else tiv[min(range(len(tit)), key=lambda k: abs(tit[k] - sample_t))]
        except KernelError:
            pass
    finally:
        s.close()
    return {"shot": int(shot), "time_s": float(t), "sample_time_s": sample_t, "slice_index": it,
            "r": r, "z": z, "te": te, "ne": ne, "te_err": te_err, "ne_err": ne_err, "ti0": ti0,
            "source": f"mdsplus:mds.invalid:ts_east:{shot}"}


def cmd_pull(a) -> int:
    lib = Lib(Path(a.lib) if a.lib else DEFAULT_LIB)
    doc = {"@type": "fylite:KineticReconMeasurements", "app": APP, "version": VERSION,
           "shot": a.shot, "time_s": a.time, "measurement_chain": a.chain,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "comment": "实验数据：不入仓。服务器地址记作 mds.invalid。",
           "measurements": None, "thomson": None, "errors": {}}
    if not a.thomson_only:
        t0 = time.time()
        try:
            doc["measurements"] = pull_magnetics(lib, a.shot, a.time, a.chain, a.server, a.timeout)
            log(f"magnetics + POINT: {time.time() - t0:.1f} s")
        except Exception as e:                           # noqa: BLE001 — 取不到就说取不到
            doc["errors"]["measurements"] = sanitize(str(e))[:400]
            log(f"magnetics FAILED: {doc['errors']['measurements']}")
    if not a.no_thomson:
        t0 = time.time()
        try:
            doc["thomson"] = pull_thomson(lib, a.shot, a.time, a.server, a.timeout)
            log(f"Thomson: {len(doc['thomson']['te'])} points at {doc['thomson']['sample_time_s']:.4f} s "
                f"({time.time() - t0:.1f} s)")
        except Exception as e:                           # noqa: BLE001
            doc["errors"]["thomson"] = sanitize(str(e))[:400]
            log(f"Thomson FAILED: {doc['errors']['thomson']}")
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")
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


# ================================================================================================ geometry helpers

def _name(x: dict) -> str:
    return str(x.get("name") or x.get("identifier") or "")


def _rz(x: dict):
    p = x.get("position")
    if isinstance(p, dict):
        r, z = p.get("r"), p.get("z")
    elif isinstance(p, list) and p:
        r, z = p[0].get("r"), p[0].get("z")
    else:
        return None
    r = r[0] if isinstance(r, list) else r
    z = z[0] if isinstance(z, list) else z
    return [float(r), float(z)] if r is not None and z is not None else None


def psi_at(fi: dict, r: float, z: float) -> float:
    gr, gz, psi = fi["grid_r"], fi["grid_z"], fi["psi"]
    i = min(max(bisect.bisect_left(gr, r) - 1, 0), len(gr) - 2)
    j = min(max(bisect.bisect_left(gz, z) - 1, 0), len(gz) - 2)
    a = (r - gr[i]) / (gr[i + 1] - gr[i])
    b = (z - gz[j]) / (gz[j + 1] - gz[j])
    return ((1 - a) * (1 - b) * psi[i][j] + a * (1 - b) * psi[i + 1][j]
            + (1 - a) * b * psi[i][j + 1] + a * b * psi[i + 1][j + 1])


def psin_at(fa: dict, fi: dict, r: float, z: float) -> float:
    return (fa["psi_axis"] - psi_at(fi, r, z)) / (fa["psi_axis"] - fa["psi_bnd"])


FACT_KEYS = ("q0", "q95", "li3", "axis_r", "axis_z", "ip", "psi_axis", "psi_bnd", "chi2", "chi2_mag", "chi2_kin",
             "chi2_per_dof", "dof", "worst_channel_sigma", "iterations", "residual", "converged", "kinetic_rows",
             "kinetic_passes_run", "kinetic_best_pass", "kinetic_best_chi2_per_dof", "kinetic_map_shift",
             "p_fast_max", "curv_p", "curv_f", "npp", "nff")


def tier_view(fa: dict, fi: dict, zc: float, extra: dict | None = None) -> dict:
    v = {"status": "ok", "zc_anchor": zc,
         "facts": {k: _r(fa[k]) for k in FACT_KEYS if k in fa},
         "grid": {"r": _r(fi["grid_r"]), "z": _r(fi["grid_z"])},
         "psi": _r(fi["psi"], 5),
         "boundary": _r(fi.get("boundary") or [], 5),
         "profiles": {"psin": _r(fi["psin_1d"], 5), "pres": _r(fi["pres"], 5), "pprime": _r(fi["pprime"], 5),
                      "ffprim": _r(fi["ffprim"], 5), "qpsi": _r(fi["qpsi"], 5),
                      "pprime_sigma": _r(fi.get("pprime_sigma") or [float("nan")] * len(fi["pprime"]), 5)},
         "q": {"x": _r(fi["q_x"], 5), "q": _r(fi["q"], 5)}}
    if extra:
        v.update(extra)
    return v


# ================================================================================================ parallel doors

_POOL: dict = {"jobs": 1, "ex": None, "pid": None, "lib": None}
_WORKER_LIB: dict = {}


def set_jobs(jobs: int) -> None:
    """档 M 一轮里的独立反演调用最多同时跑几路（1 = 串行）。已开的工作进程池在路数变时关掉重开。"""
    jobs = max(1, int(jobs))
    if jobs != _POOL["jobs"]:
        close_jobs()
    _POOL["jobs"] = jobs


def close_jobs() -> None:
    ex = _POOL["ex"]
    if ex is not None and _POOL["pid"] == os.getpid():
        ex.shutdown(wait=True)
    _POOL.update(ex=None, pid=None, lib=None)


def _door_worker_init(path: str) -> None:
    _WORKER_LIB["lib"] = Lib(Path(path))


def _door_worker(req):
    code, settings, inputs = req
    try:
        return _WORKER_LIB["lib"].door(code, settings, inputs)
    except (Refused, KernelError) as e:              #: 拒绝是读数：当作值传回，由调用方照串行的次序处理
        return e


def run_doors(lib: Lib, code: str, reqs: list) -> list:
    """一批互不依赖的门调用 [(settings, inputs), …] → 按原次序的 [(facts, fields, notes) 或 Refused/KernelError, …]。
    ``set_jobs`` > 1 且不止一个请求时交给工作进程池（fork；每个进程自己载库），否则就在本进程里逐个调。"""
    #: daemon 进程（mp.Pool 的工作进程）不许再开子进程：那里照串行
    if _POOL["jobs"] <= 1 or len(reqs) <= 1 or multiprocessing.current_process().daemon:
        out = []
        for settings, inputs in reqs:
            try:
                out.append(lib.door(code, settings, inputs))
            except (Refused, KernelError) as e:
                out.append(e)
        return out
    #: 池是本进程开的、载的是同一份库才复用（wei2026 的切片工作进程由 fork 而来，不能用父进程的池）
    if _POOL["ex"] is None or _POOL["pid"] != os.getpid() or _POOL["lib"] != str(lib.path):
        if _POOL["pid"] == os.getpid():
            close_jobs()
        _POOL.update(ex=concurrent.futures.ProcessPoolExecutor(
            _POOL["jobs"], mp_context=multiprocessing.get_context("fork"),
            initializer=_door_worker_init, initargs=(str(lib.path),)), pid=os.getpid(), lib=str(lib.path))
    return list(_POOL["ex"].map(_door_worker, [(code, s, i) for s, i in reqs]))


# ================================================================================================ tiers

class Case:
    """一个时刻的全部输入，以及三档共用的那几样（线圈份额、装置文档、权重）。"""

    def __init__(self, lib: Lib, meas: dict, card: dict, loops: str):
        self.lib, self.meas, self.card = lib, meas, card
        self.brsp = [float(v) for v in meas["brsp"]]
        self.coils = [float(v) for v in meas["coils"]]
        self.probes = [float(v) for v in meas["expmp2"]]
        mag = card["magnetics"]
        fl, bp = _aos(mag.get("flux_loop")), _aos(mag.get("b_field_pol_probe"))
        self.loop_names = [_name(x) for x in fl][:len(self.coils)]
        self.probe_names = [_name(x) for x in bp][:len(self.probes)]
        self.loop_rz = [_rz(x) for x in fl][:len(self.coils)]
        self.probe_rz = [_rz(x) for x in bp][:len(self.probes)]
        r0 = float(card["tf"]["r0"])
        tf = meas.get("tf") or {}
        if "f_vac_Tm" in tf:
            self.b_tor, self.bt_from = abs(float(tf["f_vac_Tm"])) / r0, f"TF 线圈电流 {tf.get('node', '')}（F = μ₀NI/2π）"
        else:
            self.b_tor, self.bt_from = abs(float(meas["btor"])), "归约件的 btor（B_T 节点，#97286 起单位存疑）"
        _, share, _ = lib.door("code/coilshare", {"nu_loops": 8, "nu_probes": 3, "grid_psi": 1, "nu_grid": 4},
                               {"device": card, "discharge": {"fylite:channel_aturns": self.brsp}})
        self.loop_coil, self.probe_coil, self.psi_ext = share["loop_coil"], share["probe_coil"], share["psi_ext"]
        #: 选道：探针 = 归约器判在用 − 名字重复的槽（没有独立节点）
        self.excluded = []
        fwt = [float(v) for v in meas["fwtmp2"]]
        seen: dict = {}
        for i, nm in enumerate(self.probe_names):
            seen.setdefault(nm, []).append(i)
        for nm, idx in seen.items():
            if nm and len(idx) > 1:
                for i in idx:
                    if fwt[i] > 0:
                        self.excluded.append({"kind": "probe", "index": i, "name": nm, "why": "名字重复：没有独立节点"})
                    fwt[i] = 0.0
        #: ★★起步环组（实测 2026-09-18，#137985 4.041 s）：75 个环全进，16 个竖直设定点一个都不收敛；
        #: 只用 FL*B 组起步则收敛。起步用 B 组，其余环在第一个收敛解上**按残差回收**（readmit）。
        self.loop_start = [1.0] * len(self.coils)
        if loops in ("B", "B+readmit"):
            self.loop_start = [1.0 if re.fullmatch(r"FL\d+B", nm or "") else 0.0 for nm in self.loop_names]
        #: ★旧炮（#63948 · #81481 一代）的排布只有 35 个 FL<n>A 环、没有 B 组：B 组规则一个环都选不到，
        #: 这时回退到全部环起步（记在结果里），不在没有环的情况下起步。
        self.loop_start_rule = "all" if loops == "all" else "FL*B"
        if not any(self.loop_start):
            self.loop_start = [1.0] * len(self.coils)
            self.loop_start_rule = "all（本排布没有 FL*B 组）"
        self.loop_sigma = [max(SERROR * abs(v), LOOP_FLOOR) for v in self.coils]
        self.probe_sigma = [max(SERROR * abs(v), PROBE_FLOOR) for v in self.probes]
        self.lw = [s / sg for s, sg in zip(self.loop_start, self.loop_sigma)]
        self.pw = [f / sg if f > 0 else 0.0 for f, sg in zip(fwt, self.probe_sigma)]

    def base_disc(self) -> dict:
        return {"fylite:channel_aturns": self.brsp, "fylite:ip": [float(self.meas["plasma"])],
                "fylite:b_tor": [self.b_tor], "fylite:loop_weight": self.lw, "fylite:probe_weight": self.pw}

    def full_disc(self) -> dict:
        return dict(self.base_disc(), **{"fylite:flux_loop": self.coils, "fylite:probe_field": self.probes})

    def rows_disc(self) -> dict:
        """行给定档：量值扣掉线圈份额，外场随行（POINT 的法拉第行只能走这一档）。"""
        return dict(self.base_disc(), **{"fylite:psi_ext": self.psi_ext,
                                         "fylite:loop_plasma": [m - c for m, c in zip(self.coils, self.loop_coil)],
                                         "fylite:probe_plasma": [m - c for m, c in zip(self.probes, self.probe_coil)]})

    def residuals(self, fi: dict, *, all_channels: bool = False):
        """(model − measured)/sigma per channel; weighted (0 for unused) unless ``all_channels``."""
        rl = [(lm + lc - m) / sg for lm, lc, m, sg in zip(fi["loop_model"], self.loop_coil, self.coils, self.loop_sigma)]
        rp = [(pm - m) / sg for pm, m, sg in zip(fi["probe_model"], self.probes, self.probe_sigma)]
        if all_channels:
            return rl, rp
        return ([v if w > 0 else 0.0 for v, w in zip(rl, self.lw)],
                [v if w > 0 else 0.0 for v, w in zip(rp, self.pw)])

    def channel_table(self, fi: dict) -> dict:
        rl, rp = self.residuals(fi, all_channels=True)
        return {"loops": [{"name": n, "rz": rz, "sigma": _r(v, 4), "used": w > 0}
                          for n, rz, v, w in zip(self.loop_names, self.loop_rz, rl, self.lw)],
                "probes": [{"name": n, "rz": rz, "sigma": _r(v, 4), "used": w > 0}
                           for n, rz, v, w in zip(self.probe_names, self.probe_rz, rp, self.pw)]}


def tier_m(c: Case, reject_sigma: float, max_rounds: int, per_round: int, settings: dict,
           readmit: bool, scan: dict | None = None) -> tuple[dict, tuple | None]:
    """档 M：扫描 + 剔道几轮；``readmit`` 时把起步组之外、在收敛解上残差不超阈值的环收回来，再扫几轮。
    ``scan``：竖直设定点扫描的做法（``SCAN_FULL`` 缺省 / ``SCAN_COARSE``，见其注释）。"""
    scan = dict(SCAN_COARSE, **scan) if (scan or {}).get("mode") == "coarse" else dict(SCAN_FULL)
    rounds, rejected, readmitted = [], [], []
    best = _m_rounds(c, reject_sigma, max_rounds, per_round, settings, rounds, rejected, 0, scan)
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
            again = _m_rounds(c, reject_sigma, max_rounds, per_round, settings, rounds, rejected, len(rounds), scan)
            if again is not None:
                best = again
            else:                                        #: 回收之后反而解不出：退回，照实记
                for r in readmitted:
                    c.lw[r["index"]] = 0.0
                readmitted = [dict(r, reverted=True) for r in readmitted]
    if best is None:
        return {"status": "error", "error": "没有一个竖直设定点收敛", "rounds": rounds, "rejected": rejected,
                "scan": scan}, None
    chi2, zc, fa, fi, notes = best
    summary = _scan_summary(scan, rounds, settings)
    if settings.get("anderson") and "anderson" not in fa:  #: 2026-09-19 之前的内核不认这个键，也不报错：照实记
        summary["anderson_ignored"] = True
        log("this libfylite.so ignores `anderson` (kernel before 2026-09-19): tier M ran pure Picard")
    if settings.get("newton_krylov") and "newton_krylov" not in fa:  #: 没有 JFNK 的内核同样不认、不报错：照实记
        summary["newton_krylov_ignored"] = True
        log("this libfylite.so ignores `newton_krylov` (kernel without feat/gs-newton-krylov): "
            "tier M ran without the Newton–Krylov accelerator")
    view = tier_view(fa, fi, zc, {"label": "M · 磁测量", "scan": summary,
                                  "rounds": rounds, "rejected": rejected,
                                  "readmitted": readmitted, "channels": c.channel_table(fi), "notes": notes,
                                  "constraints": ["磁通环", "磁探针", "Ip", "实测 PF 电流（固定）"]})
    return view, (fa, fi, zc)


def _fine_scan(c: Case, settings: dict, zcs: list, scan: list, best):
    """在 65²（``settings`` 本身的网格）上逐个设定点冷启动反演；读数记进 ``scan``，返回收敛者中 chi2 最小的。"""
    inputs = {"device": c.card, "discharge": c.full_disc()}
    got = run_doors(c.lib, "code/reconstruction", [(dict(settings, zc_anchor=zc), inputs) for zc in zcs])
    for zc, rec in zip(zcs, got):                        #: 各点互不依赖：可并行解，按原次序归并（与串行逐位相同）
        if isinstance(rec, Exception):                   #: 一个解不出的设定点也是读数
            scan.append({"zc": zc, "error": str(rec)[-60:]})
            continue
        fa, fi, notes = rec
        rl, rp = c.residuals(fi)
        chi2 = sum(v * v for v in rl) + sum(v * v for v in rp)
        scan.append({"zc": zc, "chi2": _r(chi2, 5), "q0": _r(fa["q0"], 4), "converged": bool(fa["converged"])})
        if fa["converged"] and (best is None or chi2 < best[0]):
            best = (chi2, zc, fa, fi, notes)
    return best


def _coarse_scan(c: Case, settings: dict, how: dict):
    """粗扫一轮（做法见 ``SCAN_COARSE`` 的注释）。返回 (粗网格读数, 65² 读数, 是否退回全扫, 最好的 65² 解)。"""
    n = int(how["grid"])
    coarse, ranked = [], []
    inputs = {"device": c.card, "discharge": c.full_disc()}
    got = run_doors(c.lib, "code/reconstruction", [(dict(settings, zc_anchor=zc, nw=n, nh=n), inputs) for zc in ZC_SCAN])
    for zc, rec in zip(ZC_SCAN, got):
        if isinstance(rec, Exception):
            coarse.append({"zc": zc, "error": str(rec)[-60:]})
            continue
        fa, fi, _ = rec
        rl, rp = c.residuals(fi)
        chi2 = sum(v * v for v in rl) + sum(v * v for v in rp)
        coarse.append({"zc": zc, "chi2": _r(chi2, 5), "q0": _r(fa["q0"], 4), "converged": bool(fa["converged"])})
        if fa["converged"]:
            ranked.append((chi2, zc))
    fine: list = []
    if len(ranked) < how["min_converged"] * len(ZC_SCAN):  #: 粗网格上收敛的太少，排序不可信：这一轮照全扫
        return coarse, fine, True, _fine_scan(c, settings, ZC_SCAN, fine, None)
    top = [zc for _, zc in sorted(ranked)[: max(1, int(how["top"]))]]
    best = _fine_scan(c, settings, top, fine, None)
    if best is None:                                     #: 粗排的前几名在 65² 上都不收敛：这一轮照全扫
        return coarse, fine, True, _fine_scan(c, settings, [zc for zc in ZC_SCAN if zc not in top], fine, None)
    while True:                                          #: 65² 上从最好的点往两侧邻点走，直到两侧都不更好
        k, tried = ZC_SCAN.index(best[1]), {x["zc"] for x in fine}
        nxt = [ZC_SCAN[j] for j in (k - 1, k + 1) if 0 <= j < len(ZC_SCAN) and ZC_SCAN[j] not in tried]
        if not nxt:
            break
        was = best[1]
        best = _fine_scan(c, settings, nxt, fine, best)
        if best[1] == was:
            break
    return coarse, fine, False, best


def _scan_summary(scan: dict, rounds: list, settings: dict) -> dict:
    """结果 JSON 里记下跑的是哪种扫法、加速器深度、并行路数，以及 65² / 粗网格各解了几次。"""
    out = dict(scan, anderson=int(settings.get("anderson", 0)), newton_krylov=int(settings.get("newton_krylov", 0)),
               jobs=_POOL["jobs"], solves_fine=sum(len(r.get("scan", [])) for r in rounds))
    if scan.get("mode") == "coarse":
        out.update(solves_coarse=sum(len(r.get("coarse", [])) for r in rounds),
                   fallback_rounds=[r["round"] for r in rounds if r.get("fallback")])
    return out


def _m_rounds(c: Case, reject_sigma, max_rounds, per_round, settings, rounds, rejected, rnd0, scan_opts=None):
    """One run of scan + reject rounds.  Returns the last round that converged; if a round after a
    rejection converges nothing, that rejection is undone (so the mask and the answer always agree)."""
    how = dict(SCAN_COARSE, **(scan_opts or SCAN_FULL))
    #: 设定点少（热启动的 5 点扫）时粗排省不下什么：照全扫
    coarse_mode = how["mode"] == "coarse" and len(ZC_SCAN) > 2 * how["top"]
    last_good, last_batch = None, []
    for rnd in range(rnd0, rnd0 + max_rounds):
        scan, extra = [], {}
        if coarse_mode:                                  #: ``scan`` 记 65² 的读数（页面按它数收敛），粗网格读数另记
            coarse, scan, fallback, best = _coarse_scan(c, settings, how)
            extra = {"strategy": "coarse", "coarse": coarse, "fallback": fallback,
                     "coarse_converged": sum(1 for s in coarse if s.get("converged"))}
        else:
            best = _fine_scan(c, settings, ZC_SCAN, scan, None)
            if how["mode"] == "coarse":
                extra = {"strategy": "full", "why": f"only {len(ZC_SCAN)} set points"}
        n_used = sum(1 for v in c.lw if v > 0) + sum(1 for v in c.pw if v > 0)
        if best is None:
            rounds.append({"round": rnd, "scan": scan, "converged": 0, "n_used": n_used, **extra})
            for r in last_batch:                         #: 这一批剔完反而解不出：撤回
                if r["kind"] == "loop":
                    c.lw[r["index"]] = 1.0 / c.loop_sigma[r["index"]]
                else:
                    c.pw[r["index"]] = 1.0 / c.probe_sigma[r["index"]]
                r["reverted"] = True
            break
        last_good, last_batch = best, []
        chi2, zc, fa, fi, _ = best
        rl, rp = c.residuals(fi)
        cand = sorted([(abs(v), "loop", i) for i, v in enumerate(rl) if abs(v) > reject_sigma]
                      + [(abs(v), "probe", i) for i, v in enumerate(rp) if abs(v) > reject_sigma], reverse=True)
        rounds.append({"round": rnd, "scan": scan, "converged": sum(1 for s in scan if s.get("converged")),
                       "n_used": n_used, "zc": zc, "chi2": _r(chi2, 5), "chi2_per_channel": _r(chi2 / n_used, 4),
                       "q0": _r(fa["q0"], 4), **extra})
        said = (f"coarse {extra['coarse_converged']}/{len(ZC_SCAN)}, fine {rounds[-1]['converged']}/{len(scan)}"
                + (" (fallback)" if extra["fallback"] else "") if "coarse" in extra else f"{rounds[-1]['converged']}/{len(ZC_SCAN)}")
        log(f"M round {rnd}: {said} converged, zc {zc * 1e3:+.0f} mm, "
            f"chi2/channel {chi2 / n_used:.2f}, q0 {fa['q0']:.3f}, {len(cand)} channel(s) > {reject_sigma:g} sigma")
        if not cand or rnd == rnd0 + max_rounds - 1:
            break                                        #: 最后一轮只量，不剔——剔了就没有对应的解了
        for v, kind, i in cand[:per_round]:
            names = c.loop_names if kind == "loop" else c.probe_names
            (c.lw if kind == "loop" else c.pw)[i] = 0.0
            rejected.append({"kind": kind, "index": int(i), "name": names[i], "sigma": _r(v, 3), "round": rnd})
            last_batch.append(rejected[-1])
    return last_good


def _eq_doc(fa, fi):
    return {"time_slice": {"profiles_2d": {"psi": fi["psi"]},
                           "global_quantities": {"psi_axis": [fa["psi_axis"]], "psi_boundary": [fa["psi_bnd"]]}}}


def point_arrays(meas: dict, off: list):
    p = meas["point"]
    nel, bp = [float(v) for v in p["bnel"]], [float(v) for v in p["bpolar"]]
    fwtnel, fwtpol = [float(v) for v in p["fwtnel"]], [float(v) for v in p["fwtpol"]]
    for k in off:
        if 1 <= k <= len(bp):
            fwtnel[k - 1] = fwtpol[k - 1] = 0.0
    return nel, bp, fwtnel, fwtpol


def chords(c: Case, fa, fi, nel, fwtnel):
    eq = _eq_doc(fa, fi)
    fit, _, _ = c.lib.door("code/chords", {"ne0": 3e19, "rows": 0},
                           {"device": c.card, "equilibrium": eq,
                            "discharge": {"fylite:chord_nel": [v * 1e19 for v in nel], "fylite:chord_nel_weight": fwtnel}})
    _, fi2, _ = c.lib.door("code/chords", {"ne0": fit["fit_ne0"], "peaking": fit["fit_peaking"], "rows": 1},
                           {"device": c.card, "equilibrium": eq,
                            "discharge": {"fylite:psi_ext": c.psi_ext, "fylite:current_cells": fi["current"]}})
    return fit, fi2


def point_resid(fi2, nel, bp, fwtnel, fwtpol):
    rb = [(m - b) / SIGPOL for m, b in zip(fi2["chord_bpolar"], bp)]
    rn = [(m - n) / math.sqrt(SIGNEL ** 2 + (0.03 * n) ** 2) for m, n in zip(fi2["chord_nel19"], nel)]

    def rms(r, w):
        u = [v * v for v, x in zip(r, w) if x > 0]
        return math.sqrt(sum(u) / len(u)) if u else float("nan")
    return rb, rn, rms(rb, fwtpol), rms(rn, fwtnel)


def faraday_extra(fi2, bp, fwtpol) -> dict:
    use = [i for i, w in enumerate(fwtpol) if w > 0]
    rows = fi2["faraday_rows"]
    return {"fylite:row_extra": flat([rows[i] for i in use]),
            "fylite:meas_extra": [(bp[i] - fi2["chord_coil"][i] / 1e19) * 1e19 for i in use],
            "fylite:weight_extra": [fwtpol[i] / (SIGPOL * 1e19) for i in use]}


def tier_k(c: Case, base, off: list, dead_sigma: float, settings: dict):
    """档 K：零假设（M 的平衡上前向 11 弦）→ 法拉第行进拟合，逐轮重建行至 |Δq0|/q0 < 1e-3。"""
    if not (c.meas.get("point") or {}).get("bpolar"):
        return {"status": "skipped", "why": "输入里没有 POINT 块"}, None, None
    fa_m, fi_m, zc = base
    nel, bp, fwtnel, fwtpol = point_arrays(c.meas, off)
    fit, fi2 = chords(c, fa_m, fi_m, nel, fwtnel)
    rb0, rn0, rbs0, rns0 = point_resid(fi2, nel, bp, fwtnel, fwtpol)
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
    passes = []
    try:
        fa, fi, _ = c.lib.door("code/reconstruction", st, {"device": c.card, "discharge": c.rows_disc()})
        for _ in range(6):
            _, fi2 = chords(c, fa, fi, nel, fwtnel)
            disc = dict(c.rows_disc(), **faraday_extra(fi2, bp, fwtpol))
            fa_n, fi_n, _ = c.lib.door("code/reconstruction", st, {"device": c.card, "discharge": disc})
            dq = abs(fa_n["q0"] - fa["q0"]) / max(abs(fa["q0"]), 1e-12)
            passes.append({"q0": _r(fa_n["q0"], 5), "dq0_rel": _r(dq, 3), "converged": bool(fa_n["converged"])})
            fa, fi = fa_n, fi_n
            if dq < 1e-3:
                break
    except (Refused, KernelError) as e:                  # 记下，不藏
        return {"status": "error", "error": str(e)[-300:], "null": null, "dead": dead, "passes": passes}, None, None
    fit2, fi2 = chords(c, fa, fi, nel, fwtnel)
    rb1, rn1, rbs1, rns1 = point_resid(fi2, nel, bp, fwtnel, fwtpol)
    log(f"K fitted: q0 {fa['q0']:.3f}, Faraday {rbs0:.3f} -> {rbs1:.3f} sigma, {len(passes)} pass(es)")
    chord_geo = [{"name": _name(ch), "los": ch.get("line_of_sight")} for ch in _aos(c.card.get("polarimeter"))]
    view = tier_view(fa, fi, zc, {
        "label": "K · 磁 + POINT", "constraints": ["磁（同 M）", f"POINT 法拉第行 × {sum(1 for w in fwtpol if w > 0)}"],
        "channels": c.channel_table(fi), "passes": passes, "settled": bool(passes and passes[-1]["dq0_rel"] < 1e-3),
        "point": {"measured_bpolar": _r(bp, 5), "measured_nel19": _r(nel, 5), "fwtpol": _r(fwtpol), "fwtnel": _r(fwtnel),
                  "off_by_user": off, "dead": dead, "null": null,
                  "fitted": {"ne0": _r(fit2["fit_ne0"]), "peaking": _r(fit2["fit_peaking"]), "faraday_rms": _r(rbs1, 4),
                             "density_rms": _r(rns1, 4), "faraday_sigma": _r(rb1, 4), "density_sigma": _r(rn1, 4),
                             "model_bpolar": _r(fi2["chord_bpolar"], 5), "model_nel19": _r(fi2["chord_nel19"], 5)},
                  "chords": chord_geo}})
    return view, (fa, fi, zc), {"nel": nel, "bp": bp, "fwtnel": fwtnel, "fwtpol": fwtpol}


def pressure_from_thomson(th: dict, *, sigma_floor: float, te_floor=50.0, te_ceiling=8000.0,
                          ne_range=(1e18, 2e21), sigma_cap=2.0, zeff_dilution=1.0) -> dict:
    """Thomson（+ TXCS）→ 压强点 p = e·n_e·T_e·(1 + dilution·T_i0/T_e0)，逐点 σ 由诊断自报的
    相对误差传播，相对下限 ``sigma_floor``、绝对下限 100 Pa。质量闸：50 eV < T_e < 8 keV，n_e 在量程内，
    自报误差可用。（与 fylite.io.mds.pressure_from_thomson 同一规则。）"""
    te, ne, r, z = th["te"], th["ne"], th["r"], th["z"]
    n = len(te)
    rel = None
    if th.get("te_err") is not None and th.get("ne_err") is not None:
        rel = []
        for k in range(n):
            a = abs(th["te_err"][k]) / te[k] if te[k] != 0 else float("nan")
            b = abs(th["ne_err"][k]) / ne[k] if ne[k] != 0 else float("nan")
            rel.append(math.sqrt(a * a + b * b))
    ok = [(te_floor < te[k] < te_ceiling) and (ne_range[0] < ne[k] < ne_range[1]) and fin(te[k]) and fin(ne[k])
          and (rel is None or (fin(rel[k]) and 0 < rel[k] <= sigma_cap)) for k in range(n)]
    idx = [k for k in range(n) if ok[k]]
    if not idx:
        raise RuntimeError("pressure_from_thomson: no Thomson point passed the quality gate")
    t_i0 = float(th.get("ti0") or 0.0)
    te0 = median(sorted(te[k] for k in idx)[-5:])
    ion = 1.0 + zeff_dilution * (t_i0 / te0 if te0 > 0 else 0.0)
    p = [E_CHARGE * ne[k] * te[k] * ion for k in idx]
    if rel is not None:
        sig = [max(max(rel[k], sigma_floor) * pk, 100.0) for k, pk in zip(idx, p)]
        source = "measured"
    else:
        sig = [max(0.2 * pk, 100.0) for pk in p]
        source = "flat_fraction"
    return {"r": [r[k] for k in idx], "z": [z[k] for k in idx], "pressr": p, "sigpre": sig,
            "sigma_source": source, "n_points": len(idx), "n_dropped": n - len(idx),
            "ti0": t_i0, "te0": te0, "ion_factor": ion,
            "assumptions": {"ti_shape": "Ti(x) = Ti0*Te(x)/Te0 (TXCS core value only; Te0 = median of top-5 accepted Te)",
                            "ni": f"ni = {zeff_dilution}*ne (no Zeff correction)",
                            "fast_ion": "fast-ion pressure NOT included",
                            "sigpre": (f"measured per-point sqrt((dne/ne)^2+(dTe/Te)^2), floor {sigma_floor}, "
                                       f"failed-channel cap {sigma_cap}" if source == "measured"
                                       else "flat 0.2 of p (no error nodes)")}}


def clip_profile(lib: Lib, x, p, sig, keep, clip: float, min_left: int = 6):
    """逐点剔离群：对 p(psi_N) 做一次带 GCV 定阶的光滑拟合（``code/profile_fit``），把离拟合最远、且超过
    ``clip`` 个 sigma 的那一点剔掉，重拟，直到没有这样的点。"""
    keep = list(keep)
    dropped = []
    while sum(keep) > min_left:
        idx = [i for i, k in enumerate(keep) if k]
        xs, ys, ss = [x[i] for i in idx], [p[i] for i in idx], [sig[i] for i in idx]
        fa, fi, _ = lib.door("code/profile_fit", {"max_order": 6.0, "n_curve": 2.0},
                             {"discharge": {"fylite:fit_x": xs, "fylite:fit_y": ys, "fylite:fit_sigma": ss,
                                            "fylite:fit_eval_x": xs}})
        r = [(y - f) / s for y, f, s in zip(ys, fi["eval"], ss)]
        j = max(range(len(r)), key=lambda k: abs(r[k]))
        if abs(r[j]) <= clip:
            break
        keep[idx[j]] = False
        dropped.append({"index": idx[j], "sigma": _r(r[j], 3), "order": int(fa.get("order", 0))})
    return keep, dropped


def tier_p(c: Case, base, kin, th: dict, a, settings: dict) -> dict:
    """档 P：Thomson 压强点（R, Z，逐点实测 sigma）作动理学行，自洽外环逐遍重映 psi_N。"""
    fa_b, fi_b, zc = base
    p = pressure_from_thomson(th, sigma_floor=a.sigma_floor)
    r, z, pres, sig = p["r"], p["z"], p["pressr"], p["sigpre"]
    gr, gz = fi_b["grid_r"], fi_b["grid_z"]
    x0 = [psin_at(fa_b, fi_b, ri, zi) if (gr[0] <= ri <= gr[-1] and gz[0] <= zi <= gz[-1]) else float("nan")
          for ri, zi in zip(r, z)]
    inside = [fin(v) and 0.0 <= v < a.psin_max for v in x0]
    keep, clipped = clip_profile(c.lib, [v if ok else 0.0 for v, ok in zip(x0, inside)], pres, sig, inside, a.thomson_clip)
    why = {d["index"]: f"离光滑拟合 {d['sigma']} σ（剔）" for d in clipped}
    points = [{"r": _r(ri, 5), "z": _r(zi, 5), "p": _r(pi, 5), "sigma": _r(si, 4), "psin_initial": _r(xi, 4),
               "used": bool(k), "why": (why.get(i) or ("" if ins else f"psi_N ≥ {a.psin_max}（不收）"))}
              for i, (ri, zi, pi, si, xi, k, ins) in enumerate(zip(r, z, pres, sig, x0, keep, inside))]
    if clipped:
        log(f"P: clipped {len(clipped)} Thomson point(s) beyond {a.thomson_clip:g} sigma of a smooth fit")
    use = [i for i, k in enumerate(keep) if k]
    if len(use) < 3:
        return {"status": "error", "error": f"只有 {len(use)} 个 Thomson 点落在 psi_N < {a.psin_max} 内", "points": points}
    rows = {"fylite:pressure": [pres[i] for i in use], "fylite:pressure_x": [x0[i] for i in use],
            "fylite:pressure_weight": [1.0 / sig[i] for i in use],
            "fylite:pressure_r": [r[i] for i in use], "fylite:pressure_z": [z[i] for i in use]}
    if a.p_fast_frac > 0:                                #: 声明的快离子份额：峰值热压的 f 倍 × (1 − x²)
        pk = max(pres[i] for i in use)
        rows["fylite:p_fast_profile"] = [a.p_fast_frac * pk * (1.0 - (k / 40) ** 2) for k in range(41)]
    stacked = kin is not None
    #: ★★叠在 K 上（行给定档）时外环不重映（实测 2026-09-18：逐遍 chi2/dof 在 47.5 与 2.72 之间来回跳、
    #: 映射移动每遍 0.994）。所以叠放时只跑一遍；要外环，就用缺省的「P 叠在 M 上」。
    passes = 1 if stacked else a.kinetic_passes
    st = dict(settings, zc_anchor=zc, kinetic_passes=passes, kinetic_tol=a.kinetic_tol, curv_p=a.curv, curv_f=a.curv)
    if stacked:
        fa_k, fi_k, _ = base
        _, fi2 = chords(c, fa_k, fi_k, kin["nel"], kin["fwtnel"])
        disc0 = dict(c.rows_disc(), **faraday_extra(fi2, kin["bp"], kin["fwtpol"]))
    else:
        disc0 = c.full_disc()
    #: ★★sigma 续延（实测 2026-09-18）：把档 M 自己的压强剖面原样当动理学行喂回去，sigma 取峰值 5 % 时
    #: 内核仍把等离子体拟丢，20 % 时一步收敛——求解器对紧约束行的稳健性上限。先按实测 sigma 进，
    #: 拒了就整体放宽，放宽倍数写进结果。
    fa = fi = notes = None
    attempts = []
    for scale in a.sigma_scales:
        rows_s = dict(rows, **{"fylite:pressure_weight": [w / scale for w in rows["fylite:pressure_weight"]]})
        try:
            fa, fi, notes = c.lib.door("code/reconstruction", st, {"device": c.card, "discharge": dict(disc0, **rows_s)})
            attempts.append({"sigma_scale": scale, "ok": True})
            break
        except (Refused, KernelError) as e:              # 拒绝也是读数
            attempts.append({"sigma_scale": scale, "ok": False, "error": str(e)[-40:]})
    if fa is None:
        return {"status": "error", "error": "每一档 sigma 放宽都被拒", "attempts": attempts, "points": points}
    sigma_scale = attempts[-1]["sigma_scale"]
    log(f"P: kinetic rows entered at sigma x {sigma_scale:g} ({len(attempts)} attempt(s))")
    xf = [psin_at(fa, fi, ri, zi) for ri, zi in zip(r, z)]
    for pt, xv in zip(points, xf):
        mv = interp(min(max(xv, 0.0), 1.0), fi["psin_1d"], fi["pres"])
        pt["psin_final"] = _r(xv, 4)
        pt["model_p"] = _r(mv, 5)
        pt["resid_sigma"] = _r((mv - pt["p"]) / pt["sigma"], 4) if pt["used"] else None
        pt["resid_sigma_entered"] = _r((mv - pt["p"]) / (pt["sigma"] * sigma_scale), 4) if pt["used"] else None
    log(f"P: q0 {fa['q0']:.3f}, {int(fa.get('kinetic_passes_run', 1))} pass(es), best {int(fa.get('kinetic_best_pass', 1))}, "
        f"map shift {fa.get('kinetic_map_shift', float('nan')):.2e}, chi2_kin {fa.get('chi2_kin', float('nan')):.2f}")
    return tier_view(fa, fi, zc, {
        "label": "P · 磁" + (" + POINT" if stacked else "") + " + Thomson 压强",
        "constraints": ["磁（同 M）"] + (["POINT 法拉第行（同 K）"] if stacked else [])
                       + [f"Thomson 压强点 × {len(use)}（逐点实测 σ）"]
                       + ([f"快离子份额 {a.p_fast_frac:g}（声明）"] if a.p_fast_frac > 0 else [])
                       + ([f"曲率正则 λ = {a.curv:g}"] if a.curv > 0 else []),
        "channels": c.channel_table(fi), "notes": notes,
        "certificate": {"chi2_per_dof": _r(fi.get("kinetic_pass_chi2_per_dof") or [], 5),
                        "map_shift": _r(fi.get("kinetic_pass_map_shift") or [], 4),
                        "best_pass": int(fa.get("kinetic_best_pass", 1)), "tol": a.kinetic_tol},
        "sigma_scale": sigma_scale, "attempts": attempts, "on": "K" if stacked else "M",
        "passes_note": ("叠在 K 上：外环在行给定档不重映，只跑一遍" if stacked else ""),
        "thomson": {"points": points, "sample_time_s": th.get("sample_time_s"), "ti0": th.get("ti0"),
                    "te0": p.get("te0"), "ion_factor": p.get("ion_factor"), "n_dropped_quality": p.get("n_dropped"),
                    "sigma_source": p.get("sigma_source"), "assumptions": p.get("assumptions"),
                    "psin_max": a.psin_max}})


# ================================================================================================ run

def scan_from_args(a) -> dict:
    """``--scan`` / ``--scan-grid`` / ``--scan-top`` → ``tier_m`` 的 ``scan``。"""
    if a.scan == "coarse":
        return dict(SCAN_COARSE, grid=a.scan_grid, top=a.scan_top)
    return dict(SCAN_FULL)


def m_settings(settings: dict, anderson: int, nk: int = 0) -> dict:
    """档 M 的反演设定：``anderson`` / ``nk`` > 0 时加上内核的 ``anderson`` / ``newton_krylov``；
    0 时不写这个键（与旧库逐位相同，旧库也认）。"""
    out = dict(settings)
    if anderson:
        out["anderson"] = int(anderson)
    if nk:
        out["newton_krylov"] = int(nk)
    return out


def add_scan_args(p, default: str) -> None:
    p.add_argument("--scan", choices=("full", "coarse"), default=default,
                   help="档 M 竖直设定点扫描：full 全部在 65² 上解；coarse 先在粗网格上扫、只把最好的几个在 65² 上复核"
                        f"（缺省 {default}）")
    p.add_argument("--scan-grid", type=int, default=SCAN_COARSE["grid"], help="coarse 的粗网格边长（缺省 33）")
    p.add_argument("--scan-top", type=int, default=SCAN_COARSE["top"], help="coarse 在 65² 上复核几个设定点（缺省 4）")
    p.add_argument("--anderson", type=int, default=ANDERSON, metavar="M",
                   help=f"档 M 反演外迭代的 Anderson 混合深度（0 = 不用；缺省 {ANDERSON}）")
    p.add_argument("--nk", type=int, default=NEWTON_KRYLOV, metavar="M",
                   help=f"档 M 反演外迭代的 Newton–Krylov（JFNK）深度（0 = 不用；缺省 {NEWTON_KRYLOV}）；"
                        "要带 newton_krylov 的内核，旧库会忽略它（结果里记 newton_krylov_ignored）")


def cmd_run(a) -> int:
    lib = Lib(Path(a.lib) if a.lib else DEFAULT_LIB)
    set_jobs(a.jobs)
    meas, th, origin = load_input(a.input, a.time, a.thomson)
    shot, t = int(meas["shot"]), float(meas["time_s"])
    chain = meas.get("measurement_chain", "east")
    card, _ = lib.device("east", shot, chain)
    t0 = time.time()
    c = Case(lib, meas, card, a.loops)
    settings = dict(SETTINGS, npp=a.npp, nff=a.nff)
    k = lib.linked_kernel()
    out = {"@type": "fylite:KineticReconResult", "app": APP, "version": VERSION,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "shot": shot, "time_s": t, "measurement_chain": chain, "origin": origin,
           "source": sanitize(meas.get("source")),
           "fylite": {"version": k.get("kernel_version") or k.get("version"), "kernel_abi": k.get("abi"),
                      "library": lib.path.name, "kernel_built": k.get("built"), "kernel_sha256": k.get("sha256"),
                      "rustc": (k.get("toolchain") or {}).get("rustc")},
           "settings": {"npp": a.npp, "nff": a.nff, "loops": a.loops, "loop_start_rule": c.loop_start_rule,
                        "reject_sigma": a.reject_sigma, "scan": scan_from_args(a), "anderson": a.anderson, "nk": a.nk,
                        "jobs": a.jobs,
                        "point_off": a.point_off, "p_on": a.p_on, "dead_sigma": a.dead_sigma,
                        "kinetic_passes": a.kinetic_passes, "kinetic_tol": a.kinetic_tol, "thomson_clip": a.thomson_clip,
                        "sigma_scales": a.sigma_scales, "curv": a.curv, "p_fast_frac": a.p_fast_frac,
                        "psin_max": a.psin_max, "serror": SERROR, "loop_floor": LOOP_FLOOR, "probe_floor": PROBE_FLOOR,
                        "sigpol": SIGPOL, "signel": SIGNEL},
           "inputs": {"ip": _r(meas["plasma"]), "b_tor": _r(c.b_tor), "b_tor_from": c.bt_from, "r0": card["tf"]["r0"],
                      "pf_aturns": _r(c.brsp), "n_loops": len(c.coils), "n_probes": len(c.probes),
                      "excluded": c.excluded, "has_point": bool((meas.get("point") or {}).get("bpolar")),
                      "has_thomson": th is not None},
           "device": {"limiter": None,
                      "loops": [{"name": n, "rz": rz} for n, rz in zip(c.loop_names, c.loop_rz)],
                      "probes": [{"name": n, "rz": rz} for n, rz in zip(c.probe_names, c.probe_rz)],
                      "chords": [{"name": _name(ch), "los": ch.get("line_of_sight")} for ch in _aos(card.get("polarimeter"))]},
           "tiers": {}}
    tiers = set(a.tiers.upper())
    m_view, base_m = tier_m(c, a.reject_sigma, a.max_rounds, a.per_round, m_settings(settings, a.anderson, a.nk),
                            a.loops == "B+readmit", scan_from_args(a))
    close_jobs()                                         #: 并行只用在档 M 的扫描上；K / P 照旧串行
    out["tiers"]["M"] = m_view
    if base_m is not None:
        out["device"]["limiter"] = {"r": _r(base_m[1]["limiter_r"], 5), "z": _r(base_m[1]["limiter_z"], 5)}
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
    ap.add_argument("--lib", help=f"libfylite.so 的路径（缺省 {DEFAULT_LIB.name}，与本文件同目录）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull", help="取数：原始树 + Thomson → 测量文档")
    p.add_argument("--shot", type=int, required=True)
    p.add_argument("--time", type=float, required=True, help="时刻 [s]")
    p.add_argument("--chain", default="east", help="测量链（缺省 east）")
    p.add_argument("--server", help="mdsip 服务器 主机:端口（缺省 $FYLITE_MDSIP_SERVER）")
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
    add_scan_args(r, "coarse")
    r.add_argument("--jobs", type=int, default=JOBS, metavar="N",
                   help=f"档 M 一轮里的独立反演同时跑几路（工作进程；1 = 串行；缺省 min(16, CPU 数) = {JOBS}）")
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
