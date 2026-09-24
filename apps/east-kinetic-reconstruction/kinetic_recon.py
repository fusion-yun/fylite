#!/usr/bin/env python3
"""EAST 实验数据动理学平衡反演：原始测量 → 约束阶梯 M / K / P → 一份结果 JSON（页面读它）。

五条命令::

    python kinetic_recon.py pull --shot 137985 --time 4.041 -o meas.json      # 取数（mdsip）
    python kinetic_recon.py kfile k052340.03150 -o meas.json                   # 或：从 EFIT k-file 读（同输入）
    python kinetic_recon.py run  meas.json -o result.json                      # 反演三档
    python kinetic_recon.py compare result.json -o compare.json                # 与装置自己的 EFIT 对拍
    python kinetic_recon.py compare result.json --gfile g.x --afile a.x -o c.json   # 或与本地 g-file 对拍
    python kinetic_recon.py series --shot 137985 --t0 3 --t1 8 -o series.json  # 一段时间：档 M 逐时刻 ↔ 离线 EFIT

进程内的同一件事：``reconstruct(meas, thomson, **开关)`` · ``compare(result, refs=…)`` ·
``series(shot, t0, t1, **开关)`` · ``kfile_measurements(lib, path)``（README §5）。

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
VERSION = "0.3.1"
DEFAULT_LIB = HERE / "libfylite.so"

#: sigma = max(SERROR·|读数|, 位下限)——KEFIT / EFIT 的 data_input 约定（B-06 §7.1 两个代码同用）
SERROR = 0.05
LOOP_FLOOR = 5e-4          #: Wb/rad
PROBE_FLOOR = 7.52541e-4   #: T（KEFIT efit/2016/bitmp2.txt 的中位）
#: POINT 的 sigma：KEFIT GUI 缺省（B-06 §2.2）
SIGPOL, SIGNEL = 0.05, 0.3
TF_NODE = r"\TOP.T2:TFP"
TF_TURNS = 130 * 16        #: EAST TF：16 线圈 × 130 匝（B-06 §7.1）
#: Thomson 脉冲离所求时刻最远多少还算「这一片的测量」。#81481 只存 6 幅、离 5.3 s 最近的在 5.517 s（0.217 s），
#: 所以不能取得很紧；0.5 s 之外的就不是这一片了（#63948 上曾取回一个 45 s 之外的脉冲而不报）。`pull --ts-max-dt` 可改。
TS_MAX_DT = 0.5
DRIFT_WINDOW = (-6.9, -6.1)  #: 炮前线性漂移的拟合窗 [s]
WINDOW_MS = 5.0              #: 磁测量窗口均值的半宽 [ms]
FRINGE_GATE = 0.15           #: POINT 干涉条纹闸
POINT_NEL_MIN = 0.1          #: POINT 在用弦的线密度最大值低于它 [1e19 m⁻²] = 节点只有噪声，档 K 不跑
E_CHARGE = 1.602176634e-19

SETTINGS = {"npp": 2, "nff": 2, "relax": 0.3, "max_iter": 4000, "tol": 1e-8, "fb_gain": 8.0, "warmup": 40,
            "n_profile": 201, "n_q": 20, "n_theta": 121, "x_lo": 0.06, "x_hi": 0.995}
ZC_SCAN = [round(-0.030 + 0.004 * k, 3) for k in range(16)]
#: 竖直设定点扫描的做法（``--scan``）。``full``：每轮每个设定点都在 65² 上冷启动解，取收敛者中 chi2 最小的。
#: ``coarse``：每轮先把全部设定点在 ``grid``² 的粗网格上解一遍、按粗 chi2 排序，只把最好的 ``top`` 个在 65² 上冷启动
#: 复核，再从其中最好的往两侧邻点走（65²），直到两侧都不更好；粗网格上收敛的不到 ``min_converged``（份额），或复核的
#: 无一收敛，这一轮退回全扫。粗网格只用来排序——报出的解与剔道依据总是 65² 上的冷启动解。
#: ★门槛与 top=4 是在 12 片上量出来的：top=3、不走邻点、不设门槛时 12 片里 3 片的答案与全扫不同（README §3.3）。
SCAN_FULL = {"mode": "full"}
SCAN_COARSE = {"mode": "coarse", "grid": 33, "top": 4, "min_converged": 0.5}
#: 档 M 反演外迭代的 Anderson 混合深度（``--anderson``；内核 ``code/reconstruction`` 的 ``anderson``，0 = 纯 Picard）。
#: 只加速日程之后的 Picard 尾巴，终点是同一个不动点（内核 docs/note/gs-anderson.md）；粗扫的粗网格、65² 复核与全扫
#: 三种调用都带它。只用在档 M——K / P 的反演照旧（没有在它们上面验过）。0 时不写这个键，与旧库逐位相同。
#: ★缺省曾是 10（24 片上与 0 逐片比过）；2026-09-19（晚）起缺省改走 Newton–Krylov（``NEWTON_KRYLOV``），这里缺省 0。
#: 理由见 README §3.2（逐片的复核记录在 git 历史里的旧版 README）。
ANDERSON = 0
#: 档 M 反演外迭代的 Newton–Krylov（JFNK）深度（``--nk``；内核 ``code/reconstruction`` 的 ``newton_krylov``，0 = 不用）。
#: 同 Anderson 一样只在日程之后介入、失败即回卷成纯 Picard（不会多出拒绝）；但它能让纯 Picard 解不出（被拒 / 跑满
#: max_iter）的设定点收敛——这些点会进入扫描比较，终点可能因此移动（内核 docs/note/gs-newton-krylov-von-hagenow.md）。
#: 与 ``anderson`` 同时给时 Newton 先上，它连败 4 次才交给 Anderson。0 时不写这个键。
#: ★缺省 10 是在同样 24 片 + #63948 全炮 35 片上与纯 Picard、``anderson 10`` 三方逐片比过之后定的：终点与纯 Picard
#: 22 / 24 片、33 / 35 片相同（不同的片都是它救活了纯 Picard 解不出的设定点），三者里最快（README §3.2）。
NEWTON_KRYLOV = 10
#: 一轮里互相独立的反演调用（粗扫的全部粗网格点、65² 复核的前几名、邻点的两侧、热启动的 5 点扫、全扫的 16 点）
#: 同时交给几个工作进程（``--jobs``；1 = 串行，与旧版逐位相同）。每个工作进程自己载一份 libfylite.so（ctypes 句柄
#: 不能跨进程传）：传过去的是请求（code + settings + inputs），传回来的是门的记录（或拒绝）。门是确定的、单线程的，
#: 结果按串行的次序归并——读数、选中的解、剔道与串行**逐位相同**（README §3.3 · §6.1）。
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
                             "（取法见 README〈八 · 库与分发〉）")
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

    # ---- g-file：库里的 G-EQDSK 读者（``fylite_runtime_gfile_json``，页面读 g-file 走的也是它） ----
    def gfile(self, text: str) -> dict:
        """一份 G-EQDSK 文本 → 字典（键名同内核的 ``GFile``：nw · nh · rdim … · psirz 平铺 · rbbbs …）。"""
        fn = getattr(self.lib, "fylite_runtime_gfile_json", None)
        if fn is None:
            raise SystemExit(f"{self.path.name} 没有 g-file 读者（fylite_runtime_gfile_json，abi_gfile 特性）——换一份新构建的库")
        fn.argtypes = [ctypes.c_char_p, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint64]
        fn.restype = ctypes.c_int64
        raw = text.encode("utf-8")
        n = fn(raw, len(raw), None, 0)
        if n == -2:                                      #: 读不动：原因写进缓冲（两段式问不出它的长度，给足）
            buf = ctypes.create_string_buffer(4096)
            fn(raw, len(raw), buf, 4096)
            raise SystemExit(f"g-file 读不进来：{buf.value.decode('utf-8', 'replace')}")
        if n < 0:
            raise KernelError(f"fylite_runtime_gfile_json 返回 {n}")
        buf = ctypes.create_string_buffer(max(int(n), 1))
        fn(raw, len(raw), buf, int(n))
        return json.loads(buf.raw[:int(n)].decode("utf-8", "replace"))

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

    #: 下标里的「整条轴」（``*``）：库的 ABI 常量（c_api.rs ``mds_abi::ALL`` = i64::MIN）
    ALL = -(2 ** 63)

    def read(self, verb: str, node: str, sub=None):
        """(一维值, dims)；dims 按线上约定**最快变化的轴在前**。``sub``：对**值**取的整数下标
        （``data(\\X)[*,*,k]``；每一维一个整数或 ``Mds.ALL``）——大数组只取一片时用，节点路径与下标之外不拼任何 TDI。"""
        nb, nn, _k = _bytes(node)
        n = ctypes.c_uint64()
        idx = [int(x) for x in (sub or [])]
        sub = (ctypes.c_int64 * max(len(idx), 1))(*idx)
        rc = self.L.fylite_runtime_mds_read(self.h, self.VERBS[verb], nb, nn, sub, len(idx), 0, ctypes.byref(n))
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


_DRIFT: dict = {}


def _drift_fit(s, tb, n: int, b0: float, b1: float):
    """炮前漂移的直线 (a, b)（窗里不足 3 个采样时 None）。只由这条序列与漂移窗定、与所求时刻无关，所以按序列对象
    记一次：时间序列在每个时刻上归约时不再重拟（同一串数进同一个 ``linfit``，结果逐位相同）。"""
    key = (id(s), id(tb), n, b0, b1)
    got = _DRIFT.get(key)
    if got is not None and got[0] is s and got[1] is tb:
        return got[2]
    base = [k for k in _window(tb, n, 0.5 * (b0 + b1), 0.5 * (b1 - b0)) if b0 <= tb[k] <= b1]
    fit = linfit([tb[k] for k in base], [s[k] for k in base]) if len(base) > 2 else None
    _DRIFT[key] = (s, tb, fit)
    return fit


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
            fit = _drift_fit(s, tb, n, b0, b1)
            if fit is not None:
                a, b = fit
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


class MagneticsSource:
    """一炮的磁测量原始序列：**取**与**归约**分开。``get`` 按 (树, 节点) 记住读过的整条序列（每条只读一次）；
    ``at(t)`` 在一个时刻上归约成平坦测量字典（``reduce_series`` + TF）。``pull`` 取一个时刻（边归约边按需读，
    读的节点、次序与改动前相同）；``series`` 先 ``prefetch`` 整段要用的节点、关掉会话，再在每个时刻上 ``at``。
    ★归约只读缓存里的序列，不改它：同一个时刻，``prefetch`` 之后的 ``at`` 与单取一个时刻的 ``pull`` 逐字节相同。"""

    def __init__(self, lib: Lib, shot: int, chain: str, server, timeout_s: float):
        self.shot, self.chain = int(shot), chain
        self.doc, res = lib.device("east", shot, chain)
        self.names = device_names(self.doc, res)
        self.mds = (self.doc.get("data_source") or {}).get("mdsplus") or {}
        self.source = f"mdsplus:mds.invalid:{self.names['tree']}:{self.shot}"
        self.cache: dict = {}
        self.fetch_s = 0.0
        host, port = server_of(server)
        self.s = lib.mds_open(host, port, timeout_s)

    def get(self, leaf, where):
        nd = leaf if leaf.startswith("\\") else "\\" + leaf
        key = (where, nd)
        if key in self.cache:
            return self.cache[key]
        if self.s is None:
            raise RuntimeError(f"magnetics: {nd} ({where}) was not fetched before the session was closed")
        t0 = time.time()
        if where != self.s.tree:
            self.s.open_tree(where, self.shot)
        try:
            v, _ = self.s.read("data", nd)
            tb, _ = self.s.read("dim_of", nd)
            r = (v, tb)
        except KernelError:                              # 节点不在：是数据，不是故障
            r = None
        self.cache[key] = r
        self.fetch_s += time.time() - t0
        return r

    def prefetch(self, point: bool = False) -> None:
        """把归约可能读的节点全读进缓存：环 · 探针 · PF · Ip（+ PCS 树的回退 Ip）· TF（+ 旧炮的 ``btor_node``）；
        ``point`` 时另读 POINT 的弦（每条几百万个采样——档 M 用不到，``series`` 不读）。"""
        n = self.names
        for nd in n["loops"] + n["probes"] + n["pf_nodes"] + [n["ip_node"]]:
            if nd:
                self.get(nd, n["tree"])
        if n["pcs_tree"]:
            self.get(r"\pcrl01", n["pcs_tree"])
        if self.get(TF_NODE, n["tree"]) is None and self.mds.get("btor_node"):
            self.get(self.mds["btor_node"], n["tree"])
        if point:
            for nd in list(n["point_ne"] or []) + list(n["point_fr"] or []):
                self.get(nd, n["tree"])

    def at(self, t: float, point: bool = True) -> dict:
        """一个时刻的平坦测量字典（``pull_magnetics`` 的形）；``point=False`` 时不归约 POINT（没有 ``point`` 块）。"""
        names = self.names if point else dict(self.names, point_ne=[], point_fr=[])
        tf, tf_node = tf_series(self.get, self.names, self.mds, t)
        meas = reduce_series(self.get, self.shot, t, names, source=self.source)
        if tf is not None:
            v, tb = tf
            sel = [v[k] for k in range(min(len(v), len(tb))) if abs(tb[k] - t) <= 0.005]
            i_tf = mean(sel) if sel else v[min(range(len(tb)), key=lambda k: abs(tb[k] - t))]
            meas["tf"] = {"node": tf_node, "i_tf_A": i_tf, "turns_total": TF_TURNS, "f_vac_Tm": 2e-7 * TF_TURNS * i_tf}
        return meas

    def close(self) -> None:
        if self.s is not None:
            self.s.close()
            self.s = None


def pull_magnetics(lib: Lib, shot: int, t: float, chain: str, server, timeout_s: float) -> dict:
    """原始树 → 平坦测量字典，外加 TF 线圈电流算出的真空 F（B_T 节点自 #97286 起是伏特，B-06 §7.1）。
    一个时刻：``MagneticsSource`` 边归约边读（时间序列见 ``series``：先整段读一次，再逐时刻归约）。"""
    src = MagneticsSource(lib, shot, chain, server, timeout_s)
    try:
        return src.at(t)
    finally:
        src.close()


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


def pull_thomson(lib: Lib, shot: int, t: float, server, timeout_s: float, max_dt: float = TS_MAX_DT) -> dict:
    """芯部 Thomson 离 t 最近的一个脉冲（``ts_east``）+ TXCS 芯部 T_i0（``analysis``，±0.2 s 均值）。
    ★``\\TE_CORETS`` 一类二维节点的每一行是一个脉冲。时刻有**两种排布**（与 ``wei2026.thomson_series`` 同一判据）：
    行首是时刻（行长 = 道数 + 1，#81481 · #137985 一代），或没有时刻列、时基在 ``dim_of``（行长 = 道数，#63948 一代）。
    ★2026-09-20：此前只认第一种——#63948 上把第 0 道的 T_e 当成时刻，取回一个标着 50.0 s 的脉冲（离切片 45 s），
    档 P 的压强约束于是全错而不报。今天两种都判，判不出就拒；取到的脉冲离 t 超过 ``TS_MAX_DT`` 也拒。"""
    host, port = server_of(server)
    s = lib.mds_open(host, port, timeout_s)
    try:
        s.open_tree("ts_east", int(shot))
        te2, ne2 = s.rows(r"\TE_CORETS"), s.rows(r"\NE_CORETS")
        r, z = s.read("data", r"\R_CORETS")[0], s.read("data", r"\Z_CORETS")[0]
        nch, w = len(z), (len(te2[0]) if te2 else 0)
        if w == nch + 1:
            layout, c0 = "column0=time", 1
            times = [row[0] for row in te2]
        elif w == nch:
            layout, c0 = "no time column; dim_of", 0
            times = list(s.read("dim_of", r"\TE_CORETS")[0])
            if len(times) != len(te2):
                raise RuntimeError(f"Thomson: {len(te2)} profiles, dim_of has {len(times)} times")
        else:
            raise RuntimeError(f"Thomson: row length {w} fits neither {nch} channels nor {nch}+1")
        it = min(range(len(times)), key=lambda k: abs(times[k] - t))
        sample_t = times[it]
        if abs(sample_t - t) > max_dt:
            raise RuntimeError(f"Thomson: nearest pulse is at {sample_t:.4f} s, {abs(sample_t - t):.3f} s from the "
                               f"requested {t:.4f} s (limit {max_dt} s; pull --ts-max-dt) — not a measurement of this slice")
        te, ne = te2[it][c0:], ne2[it][c0:]
        te_err = ne_err = None
        try:
            teE, neE = s.rows(r"\TE_CORETSERR"), s.rows(r"\NE_CORETSERR")
            if len(teE) == len(te2) and len(neE) == len(ne2):
                te_err, ne_err = teE[it][c0:], neE[it][c0:]
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
    return {"shot": int(shot), "time_s": float(t), "sample_time_s": sample_t, "slice_index": it, "layout": layout,
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
            doc["thomson"] = pull_thomson(lib, a.shot, a.time, a.server, a.timeout, a.ts_max_dt)
            log(f"Thomson: {len(doc['thomson']['te'])} points at {doc['thomson']['sample_time_s']:.4f} s "
                f"({time.time() - t0:.1f} s)")
        except Exception as e:                           # noqa: BLE001
            doc["errors"]["thomson"] = sanitize(str(e))[:400]
            log(f"Thomson FAILED: {doc['errors']['thomson']}")
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"-> {a.out}")
    return 0 if (doc["measurements"] or doc["thomson"]) else 1


# ================================================================================================ k-file
#: 「同输入」：测量文档不从 MDSplus 取，而从一份 EFIT k-file（``&IN1`` 名单）读——对方那次拟合用的就是这些数。
#: ★道序：k-file 的 COILS / EXPMP2 / BRSP 是 EFIT 的道序。装置事实里 east 链旧命名代（≤ #97030，provider
#: ``base_tb``）记着「FL<i>B ↔ EFIT SILOPT[i−1]、HBP<i>T ↔ EXPMPI[i−1]」（按位），PF 通道的 ``efit_index`` 把罗氏线圈
#: 排成 EFIT 的 F 线圈序（``pull`` 的 ``brsp`` 本来就是这个序）。所以只在这一代上认：道名不是 FL1B…FL<n>B /
#: HBP1T…HBP<m>T 按位排的、或道数与 k-file 不等的，按名拒绝，不猜。

_NML_KEY = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\((\d+)\))?\s*=")


def _nml_value(tok: str):
    s = tok.strip()
    low = s.lower()
    if low in (".true.", ".t.", "t"):
        return True
    if low in (".false.", ".f.", "f"):
        return False
    if s[:1] in "'\"":
        return s.strip("'\"")
    try:
        v = float(s.replace("d", "e").replace("D", "e"))
    except ValueError:
        return s
    return int(v) if re.fullmatch(r"[-+]?\d+", s) else v


def parse_namelist(text: str) -> dict:
    """Fortran 名单（``&GROUP … /``）→ {GROUP: {KEY: 值或列表}}。认 ``n*v`` 重复、``.true.``、逗号或空白分隔、
    一行多个赋值、``KEY(i) =`` 起始下标。键一律大写。"""
    out: dict = {}
    for grp, body in re.findall(r"&(\w+)(.*?)(?:^\s*/|\n\s*/|/\s*$|&END)", text, re.S | re.M | re.I):
        g = out.setdefault(grp.upper(), {})
        parts = _NML_KEY.split(re.sub(r"!.*", "", body))
        for i in range(1, len(parts) - 2, 3):
            key, idx, raw = parts[i].upper(), parts[i + 1], parts[i + 2]
            vals: list = []
            for tok in re.split(r"[\s,]+", raw.strip()):
                if tok:
                    m = re.fullmatch(r"(\d+)\*(.+)", tok)
                    vals.extend([_nml_value(m.group(2))] * int(m.group(1)) if m else [_nml_value(tok)])
            if idx:
                cur = g.get(key, [])
                cur = cur if isinstance(cur, list) else [cur]
                k0 = int(idx) - 1
                cur += [None] * max(0, k0 + len(vals) - len(cur))
                cur[k0:k0 + len(vals)] = vals
                g[key] = cur
            else:
                g[key] = vals[0] if len(vals) == 1 else vals
    return out


def _as_list(v) -> list:
    return v if isinstance(v, list) else ([] if v is None else [v])


def kfile_channel_map(names: dict, n_coils: int, n_probes: int, n_brsp: int) -> None:
    """k-file 道序 → 本装置文档道序是否按位相同；不是就拒（SystemExit，说清为什么）。"""
    loops, probes = names["loops"], names["probes"]
    why = []
    if len(loops) != n_coils:
        why.append(f"k-file COILS 有 {n_coils} 个，装置文档的环有 {len(loops)} 个")
    elif loops != [f"FL{i + 1}B" for i in range(n_coils)]:
        why.append(f"环不是 FL1B…FL{n_coils}B 按位排（{loops[:3]}…）——EFIT 道序只在 east 链旧命名代（base_tb）上有据")
    if len(probes) != n_probes:
        why.append(f"k-file EXPMP2 有 {n_probes} 个，装置文档的探针有 {len(probes)} 个")
    elif probes != [f"HBP{i + 1}T" for i in range(n_probes)]:
        why.append(f"探针不是 HBP1T…HBP{n_probes}T 按位排（{probes[:3]}…）")
    if len(names["pf_order"]) != n_brsp:
        why.append(f"k-file BRSP 有 {n_brsp} 个，装置文档的 PF 通道有 {len(names['pf_order'])} 个")
    if why:
        raise SystemExit("k-file 的道序对不上这一炮的装置文档，不猜：" + "；".join(why))


def kfile_measurements(lib: Lib, path: str, *, chain: str = "east", weights: str = "mask",
                       point_from: str | None = None) -> dict:
    """k-file → 测量文档（与 ``pull`` 同形）。COILS [Wb/rad] · EXPMP2 [T] · BRSP [A·匝，EFIT F 线圈序] · PLASMA [A] ·
    BTOR×RCENTR → 真空 F；FWTMP2 = 0 的探针不用。``weights``：``mask`` = 只取 k-file 权的「用 / 不用」，数值用装置的
    探针权（与 ``pull`` 一样）；``kfile`` = 照搬 k-file 的 FWTMP2 数值。NPRESS 段（RPRESS < 0 即 −ψ_N，EFIT 约定）
    记成 ``kinetic_pressure``，档 P 把它当 ψ_N 上给定的压强行。``point_from``：一份 ``pull`` 的输出，取它的 POINT 块
    （k-file 里没有 POINT；档 K 要它）。k-file 里与本应用做法不同的设定逐条记进 ``kfile.differs``。"""
    nml = parse_namelist(Path(path).read_text(encoding="utf-8", errors="replace"))
    k = nml.get("IN1")
    if not k:
        raise SystemExit(f"{path}：没有 &IN1 名单——不是 EFIT k-file")
    shot, itime = int(k["ISHOT"]), int(k["ITIME"])
    coils, expmp2, brsp = (_as_list(k.get(x)) for x in ("COILS", "EXPMP2", "BRSP"))
    if not coils or not expmp2 or not brsp:
        raise SystemExit(f"{path}：COILS / EXPMP2 / BRSP 不全——这份 k-file 不带磁测量")
    doc, res = lib.device("east", shot, chain)
    names = device_names(doc, res)
    kfile_channel_map(names, len(coils), len(expmp2), len(brsp))
    kw = [float(v) for v in _as_list(k.get("FWTMP2"))] or [1.0] * len(expmp2)
    dev_w = names["probe_weights"] or [1.0] * len(expmp2)
    fwtmp2 = [(w if weights == "kfile" else dev_w[i]) if w > 0 else 0.0 for i, w in enumerate(kw)]
    fwtsi = [float(v) for v in _as_list(k.get("FWTSI"))] or [1.0] * len(coils)
    meas = {"shot": shot, "time_s": itime / 1e3, "itime_ms": itime, "plasma": abs(float(k["PLASMA"])),
            "brsp": [float(v) for v in brsp], "coils": [float(v) for v in coils], "expmp2": [float(v) for v in expmp2],
            "fwtmp2": fwtmp2, "fwtsi": fwtsi, "n_probe_active": sum(1 for v in fwtmp2 if v > 0),
            "measurement_chain": names["chain"], "probe_weight_rule": "kfile" if weights == "kfile" else "device∧kfile-mask",
            "source": f"kfile:{Path(path).name}"}
    if k.get("BTOR") is not None:
        rc = float(k.get("RCENTR") or doc["tf"]["r0"])
        meas["tf"] = {"node": f"k-file BTOR × RCENTR（{rc:g} m）", "f_vac_Tm": abs(float(k["BTOR"])) * rc}
    npress = int(k.get("NPRESS") or 0)
    if npress:
        rp = [float(v) for v in _as_list(k.get("RPRESS"))][:npress]
        pr = [float(v) for v in _as_list(k.get("PRESSR"))][:npress]
        sg = [float(v) for v in _as_list(k.get("SIGPRE"))][:npress]
        fw = [float(v) for v in _as_list(k.get("FWTPRE"))][:npress] or [1.0] * npress
        if rp and all(v <= 0 for v in rp) and len(pr) == len(sg) == len(rp):
            meas["kinetic_pressure"] = {"psin": [-v for v in rp], "pressr": pr, "sigpre": sg, "fwtpre": fw,
                                        "source": f"kfile:{Path(path).name} NPRESS/RPRESS<0/PRESSR/SIGPRE",
                                        "note": "EFIT 约定 RPRESS < 0 = −ψ_N：行钉在 ψ_N 上，不随平衡重映"}
        elif rp:
            meas["kinetic_pressure_refused"] = "RPRESS 有正值（实空间 R）——本应用只收 ψ_N 上给定的 k-file 压强"
    if point_from:
        pd = json.loads(Path(point_from).read_text(encoding="utf-8"))
        pm = (pd.get("measurements") or pd).get("point")
        if not pm:
            raise SystemExit(f"{point_from}：没有 POINT 块")
        if int(pd.get("shot", shot)) != shot:
            raise SystemExit(f"{point_from} 是 #{pd.get('shot')}，k-file 是 #{shot}")
        meas["point"] = pm
        meas["point_source"] = Path(point_from).name
    meas["efit_fit"] = kfile_fit(k, nml.get("INWANT") or {}, Path(path).name)
    meas["kfile"] = {"file": Path(path).name, "differs": kfile_differences(k, weights),
                     "unused_keys": sorted(x for x in k if x not in _KFILE_USED)}
    return meas


#: ★★k-file 的**拟合设定**（2026-09-22，内核 `code/reconstruction` 的 profile-fit 扩展）。EFIT 名单变量的含义取自公开的
#: 名单文档（efit-ai.gitlab.io/efit/namelist.html）；文档没说的换算是本应用的选择，逐条写在这里、也写进结果：
#:
#: * ``KPPFNC`` / ``KFFFNC`` = 6：张力样条（``PPKNT`` / ``FFKNT``、``PPTENS`` / ``FFTENS``）；文档说 ``PCURBD`` / ``FCURBD``
#:   「只管多项式（KPPFNC < 3）」，所以样条的边缘值是自由的。张力的标度（σ 乘 ψ_N 的方式）文档没说——内核按参考解
#:   自己的剖面定成 ``mean_interval``（σ = τ(n−1)/(x_n − x_1)，见内核 profile_basis）；``--efit-override`` 可换。
#:   3 / 4 / 5 / 7（「带第二约束」/「无约束」样条）文档没有说清，不搬（记 ``not_reproduced``）。
#: * ``KPPFNC`` / ``KFFFNC`` < 3：多项式，``KPPCUR`` 个系数；``PCURBD`` = 1 边缘为零（内核的 ``poly``），0 边缘自由（``poly_free``）。
#: * ``FWTQA`` / ``QVFIT``：磁轴 q 约束；FWTQA 的归一文档没说——**本应用取 σ_q = 1e-3 / FWTQA**（``EFIT_Q0_SIGMA``）。
#: * ``KZEROJ`` / ``RZEROJ`` / ``SIZEROJ`` / ``VZEROJ``：RZEROJ = 0 → ⟨J/R⟩/⟨1/R⟩ ÷ (Ip/Area) = VZEROJ（内核 ``fsa_norm =
#:   ip_area``）；RZEROJ > 0 → (R, ψ_N) 处的 J_φ（内核 ``jlocal``）；RZEROJ < 0（分离面上 J = 0）不搬。权 = ``FWTXXJ``
#:   （文档缺省 1，名义上是 Ip/Area 单位里的 1/σ）。
#: * ``KCALPA`` / ``KCGAMA``：样条结点参数 (值, ψ_N 二阶导) 上的线性约束，行即 CALPA / CGAMA，右端 XALPA / XGAMA；
#:   文档说这些系数「按名义权 1 放大缩小」——名义权在 EFIT 内部的单位里、文档没说；**本应用取内核解算器单位里的
#:   权 ``EFIT_LINCON_WEIGHT``**，照实记为「语义搬了、权没搬」。
#: * ``FWTCUR``：Ip 作带误差的测量（内核 ``ip_sigma``）；σ 的定法文档没说——**本应用取 σ_Ip = SERROR·|PLASMA| / FWTCUR**。
EFIT_Q0_SIGMA = 1e-3
EFIT_LINCON_WEIGHT = 1.0
EFIT_PARTS = ("basis", "q0", "j", "lincon", "ip")


def kfile_fit(k: dict, inwant: dict, name: str) -> dict:
    """k-file 的拟合设定 → ``efit_fit`` 块（名单的原样摘录 + 本应用的换算；``run --efit-fit`` 把它交给内核）。"""
    fit: dict = {"source": f"kfile:{name}", "not_reproduced": []}
    for which, fnc, cur, bd, knt, tens, nk in (("pprime", "KPPFNC", "KPPCUR", "PCURBD", "PPKNT", "PPTENS", "KPPKNT"),
                                               ("ffprime", "KFFFNC", "KFFCUR", "FCURBD", "FFKNT", "FFTENS", "KFFKNT")):
        f = int(k.get(fnc) or 0)
        if f == 6:
            n = int(k.get(nk) or 0)
            knots = [float(v) for v in _as_list(k.get(knt))][:n or None]
            fit[which] = {"basis": "spline", "knots": knots, "tension": float(k.get(tens) or 0.0), "edge": "free",
                          "kfnc": f}
        elif f < 3:
            n = int(k.get(cur) or (3 if which == "pprime" else 1))
            edge_zero = float(k.get(bd, 1.0) or 0.0) >= 0.5
            fit[which] = {"basis": "poly" if edge_zero else "poly_free", "n": n, "kfnc": f}
        else:
            fit["not_reproduced"].append(f"{fnc} = {f}（名单文档没有说清这一种样条）：{which} 用本应用缺省的多项式")
    if float(k.get("FWTQA") or 0.0) > 0 and k.get("QVFIT") is not None:
        fit["q0"] = {"target": float(k["QVFIT"]), "fwtqa": float(k["FWTQA"]),
                     "weight": float(k["FWTQA"]) / EFIT_Q0_SIGMA}
    kz = int(k.get("KZEROJ") or inwant.get("KZEROJ") or 0)
    if kz > 0:
        def arr(key):
            v = inwant.get(key, k.get(key))
            return [float(x) for x in _as_list(v)][:kz]
        rz, sz, vz = arr("RZEROJ") or [0.0] * kz, arr("SIZEROJ"), arr("VZEROJ")
        fw = float(inwant.get("FWTXXJ", k.get("FWTXXJ", 1.0)))
        rz += [0.0] * (kz - len(rz))
        rows = [(r, s, v) for r, s, v in zip(rz, sz, vz)]
        fit["zeroj"] = {"fsa": {"x": [s for r, s, v in rows if r == 0.0], "value": [v for r, s, v in rows if r == 0.0]},
                        "local": {"r": [r for r, s, v in rows if r > 0.0], "x": [s for r, s, v in rows if r > 0.0],
                                  "value": [v for r, s, v in rows if r > 0.0]},
                        "weight": fw}
        if any(r < 0.0 for r in rz):
            fit["not_reproduced"].append("RZEROJ < 0（分离面上 J_t = 0）：不搬")
    for which, kc, cm, xv in (("pprime", "KCALPA", "CALPA", "XALPA"), ("ffprime", "KCGAMA", "CGAMA", "XGAMA")):
        n = int(k.get(kc) or 0)
        if n > 0:
            coefs = [float(v) for v in _as_list(k.get(cm))]
            rhs = [float(v) for v in _as_list(k.get(xv))][:n] or [0.0] * n
            #: 名单按 (系数, 约束) 列主序给 CALPA(i, j)；一行约束时就是原样的那串数
            per = len(coefs) // n if n else 0
            rows = [coefs[j * per:(j + 1) * per] for j in range(n)]
            if (fit.get(which) or {}).get("basis") == "spline":
                fit.setdefault("lincon", {})[which] = {"rows": rows, "rhs": rhs + [0.0] * (n - len(rhs)),
                                                        "weight": EFIT_LINCON_WEIGHT}
            else:
                fit["not_reproduced"].append(f"{kc} = {n}：多项式系数上的线性约束，本应用不搬")
    if float(k.get("FWTCUR") or 0.0) > 0:
        se = float(k.get("SERROR") or SERROR)
        fit["ip"] = {"fwtcur": float(k["FWTCUR"]), "serror": se,
                     "sigma": se * abs(float(k["PLASMA"])) / float(k["FWTCUR"])}
    return fit


def efit_request(fit: dict, parts: set, override: dict | None) -> tuple[dict, dict, dict]:
    """``efit_fit`` 块 → (内核设定, discharge 行, 记录)。``parts`` ⊆ ``EFIT_PARTS``；``override`` 是 ``--efit-override``
    的 JSON（键：``pprime`` / ``ffprime``（整块替换）· ``tension_scale`` · ``q0_weight`` · ``j_weight`` · ``lincon_weight``
    · ``ip_sigma``）。"""
    ov = dict(override or {})
    st: dict = {}
    disc: dict = {}
    rec = {"parts": sorted(parts), "override": ov, "source": fit.get("source"),
           "not_reproduced": list(fit.get("not_reproduced") or [])}
    if "basis" in parts:
        for which in ("pprime", "ffprime"):
            b = ov.get(which) or fit.get(which)
            if not b:
                continue
            if b["basis"] == "spline":
                st[f"{which}_basis"] = "spline"
                st[f"{which}_knots"] = " ".join(repr(float(v)) for v in b["knots"])
                st[f"{which}_tension"] = float(b.get("tension", 0.0))
                st[f"{which}_edge"] = b.get("edge", "free")
            else:
                st[f"{which}_basis"] = b["basis"]
                st["npp" if which == "pprime" else "nff"] = int(b["n"])
            rec[which] = b
        if any(v == "spline" for k_, v in st.items() if k_.endswith("_basis")):
            st["spline_tension_scale"] = ov.get("tension_scale", "mean_interval")
            rec["tension_scale"] = st["spline_tension_scale"]
    if "q0" in parts and fit.get("q0"):
        st["q0_target"] = fit["q0"]["target"]
        st["q0_weight"] = float(ov.get("q0_weight", fit["q0"]["weight"]))
        rec["q0"] = {"target": st["q0_target"], "weight": st["q0_weight"]}
    if "j" in parts and fit.get("zeroj"):
        zj = fit["zeroj"]
        w = float(ov.get("j_weight", zj["weight"]))
        if zj["fsa"]["x"]:
            st["fsa_norm"] = "ip_area"
            disc.update({"fylite:fsa_x": zj["fsa"]["x"], "fylite:fsa_shape": zj["fsa"]["value"],
                         "fylite:fsa_weight": [w] * len(zj["fsa"]["x"])})
        if zj["local"]["r"]:
            st.update(jlocal_r=" ".join(map(repr, zj["local"]["r"])), jlocal_x=" ".join(map(repr, zj["local"]["x"])),
                      jlocal_value=" ".join(map(repr, zj["local"]["value"])),
                      jlocal_weight=" ".join([repr(w)] * len(zj["local"]["r"])))
        rec["j"] = {"weight": w, "fsa_rows": len(zj["fsa"]["x"]), "local_rows": len(zj["local"]["r"])}
    if "lincon" in parts and fit.get("lincon"):
        for which, lc in fit["lincon"].items():
            if st.get(f"{which}_basis") != "spline":
                continue
            st[f"{which}_lincon"] = ";".join(" ".join(repr(v) for v in row) for row in lc["rows"])
            st[f"{which}_lincon_rhs"] = " ".join(repr(v) for v in lc["rhs"])
            st[f"{which}_lincon_weight"] = float(ov.get("lincon_weight", lc["weight"]))
            rec.setdefault("lincon", {})[which] = {"rows": lc["rows"], "weight": st[f"{which}_lincon_weight"]}
    if "ip" in parts and fit.get("ip"):
        st["ip_sigma"] = float(ov.get("ip_sigma", fit["ip"]["sigma"]))
        rec["ip_sigma"] = st["ip_sigma"]
    return st, disc, rec


#: k-file 里本应用读了的键（其余记进 ``unused_keys``，一眼看到哪些对方的设定没有搬过来）
_KFILE_USED = {"ISHOT", "ITIME", "PLASMA", "BTOR", "RCENTR", "COILS", "EXPMP2", "BRSP", "FWTMP2", "FWTSI", "NPRESS",
               "RPRESS", "PRESSR", "SIGPRE", "FWTPRE", "KPPFNC", "KFFFNC", "KPPCUR", "KFFCUR", "PCURBD", "FCURBD",
               "KPPKNT", "KFFKNT", "PPKNT", "FFKNT", "PPTENS", "FFTENS", "FWTQA", "QVFIT", "KZEROJ", "RZEROJ",
               "KCALPA", "CALPA", "XALPA", "KCGAMA", "CGAMA", "XGAMA", "FWTCUR", "SERROR"}


def kfile_differences(k: dict, weights: str) -> list:
    """k-file 的拟合设定与本应用做法的逐条对照（只记设定，不记测量）。"""
    d = []

    def add(what, theirs, ours, note=""):
        d.append({"what": what, "kfile": theirs, "ours": ours, "note": note})
    add("SERROR", k.get("SERROR"), SERROR, "σ = max(SERROR·|读数|, 位下限)")
    fs = _as_list(k.get("FWTSI"))
    add("FWTSI", sorted(set(fs)), "1/σ（FL*B 起步组 + 按残差回收）", "环权：k-file 的数值不搬，只搬 0 = 不用")
    add("FWTMP2", sorted(set(_as_list(k.get("FWTMP2")))),
        "k-file 数值" if weights == "kfile" else "装置探针权 × k-file 的用/不用", "探针权")
    add("FWTFC", sorted(set(_as_list(k.get("FWTFC")))), "PF 电流固定（不拟合）", "对方把一部分 PF 电流也当拟合量")
    add("KPPCUR/KFFCUR", [k.get("KPPCUR"), k.get("KFFCUR")], "run --npp / --nff（缺省 1 / 2）",
        "p′ / FF′ 基的阶数（KPPFNC/KFFFNC < 3 时由 efit_fit 搬）")
    add("KPPFNC/KFFFNC", [k.get("KPPFNC"), k.get("KFFFNC")], "run --efit-fit：张力样条（efit_fit.pprime / ffprime）",
        "6 = 带结点的张力样条（PPKNT/FFKNT），此时 KPPCUR/KFFCUR 不起作用；张力标度见 efit_fit")
    add("FWTQA/QVFIT", [k.get("FWTQA"), k.get("QVFIT")], f"run --efit-fit：磁轴 q 行，σ_q = {EFIT_Q0_SIGMA:g}/FWTQA",
        "FWTQA 的归一名单文档没说，σ_q 是本应用的选择")
    add("KZEROJ/SIZEROJ/VZEROJ", k.get("KZEROJ"), "run --efit-fit：⟨J/R⟩/⟨1/R⟩÷(Ip/Area) 行（RZEROJ = 0）",
        "边缘电流约束（ONETWO 给的）；权 FWTXXJ")
    add("KCGAMA/CGAMA/XGAMA", [k.get("KCGAMA"), k.get("CGAMA"), k.get("XGAMA")],
        f"run --efit-fit：样条结点参数上的线性行，权 {EFIT_LINCON_WEIGHT:g}（解算器单位）", "语义搬了，EFIT 的名义权单位没搬")
    add("FITDELZ", k.get("FITDELZ"), "竖直设定点扫描 zc", "竖直位置自由度")
    add("FWTCUR", k.get("FWTCUR"), "run --efit-fit：I_p 作带误差的测量，σ = SERROR·|PLASMA|/FWTCUR（efit_fit 外 I_p 是等式）", "")
    add("RELAX/ERROR/MXITER", [k.get("RELAX"), k.get("ERROR"), k.get("MXITER")],
        [SETTINGS["relax"], SETTINGS["tol"], SETTINGS["max_iter"]], "迭代设定")
    add("VLOOP", k.get("VLOOP"), "不用", "")
    return d


def cmd_kfile(a) -> int:
    lib = Lib(Path(a.lib) if a.lib else DEFAULT_LIB)
    meas = kfile_measurements(lib, a.kfile, chain=a.chain, weights=a.weights, point_from=a.point_from)
    doc = {"@type": "fylite:KineticReconMeasurements", "app": APP, "version": VERSION,
           "shot": meas["shot"], "time_s": meas["time_s"], "measurement_chain": meas["measurement_chain"],
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "comment": "由 EFIT k-file 读成（「同输入」）。实验数据：不入仓。",
           "measurements": meas, "thomson": None, "errors": {}}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False) + "\n", encoding="utf-8")
    kp = meas.get("kinetic_pressure")
    log(f"k-file #{meas['shot']} {meas['itime_ms']} ms: {len(meas['coils'])} loops, {len(meas['expmp2'])} probes "
        f"({meas['n_probe_active']} used), {len(meas['brsp'])} PF channels"
        + (f", {len(kp['psin'])} pressure rows on psi_N" if kp else "")
        + (", POINT from " + meas["point_source"] if meas.get("point") else ""))
    for x in meas["kfile"]["differs"]:
        log(f"  differs: {x['what']}: k-file {x['kfile']} | ours {x['ours']}")
    log(f"-> {a.out}")
    return 0


# ================================================================================================ compare
#: 与装置自己的平衡重建对拍（离线 EFIT · P-EFIT · 实时 EFIT）。★只作比较：那是另一个程序的答案，不进任何一档的反演。
#: 节点名不写在本文件里：取自装置文档 ``equilibrium/fylite:signal``（fydoc ``bind/mdsplus/equilibrium``，
#: ``tools/abox-to-facts.py`` 编出的 ``<源>_<量>`` 平名），库里的事实还没有这一组时用 ``--signals`` 另给一份。
MU0 = 4e-7 * math.pi
EQ_SOURCES = {"efit": "离线 EFIT", "pefit": "P-EFIT", "efitrt": "实时 EFIT", "kefit": "本机 KEFIT（同输入）"}
#: 逐片标量（整条 [time] 读回来取第 k 个）与各自的下标形状
EQ_SCALARS = ("q0", "q95", "li", "betap", "betan", "w_mhd", "axis_r", "axis_z", "psi_axis", "psi_bnd", "ip",
              "kappa", "volume", "b0")


def eq_signals(doc: dict, override_path: str | None) -> dict:
    """{量名: {tree, node, scale, units}}——装置文档的 ``equilibrium`` 组；``--signals`` 给的文件（整份装置文档，或
    ``{"equilibrium": {...}}`` / 裸的量表）逐项盖上去。"""
    sig = dict(((doc.get("equilibrium") or {}).get("fylite:signal")) or {})
    if override_path:
        o = json.loads(Path(override_path).read_text(encoding="utf-8"))
        o = o.get("equilibrium", o)
        sig.update(o.get("fylite:signal", o))
    if not sig:
        raise SystemExit("装置文档里没有 equilibrium/fylite:signal（这份 libfylite.so 编进的事实早于 fydoc 的平衡绑定）——"
                         "用 --signals 给一份 tools/abox-to-facts.py east 编出的 east.jsonld")
    return sig


class _EqReader:
    """一个来源（``efit`` / ``pefit`` / ``efitrt``）的节点读者：``series(q)`` 读整条（乘 scale），``slab(q, sub)`` 按下标读。"""

    def __init__(self, s: "Mds", sig: dict, src: str, shot: int):
        self.s, self.sig, self.src, self.shot = s, sig, src, int(shot)

    def one(self, q):
        m = self.sig.get(f"{self.src}_{q}")
        if not m:
            return None
        if self.s.tree != m["tree"]:
            self.s.tree = None
            self.s.open_tree(m["tree"], self.shot)
        return m

    def series(self, q):
        m = self.one(q)
        if m is None:
            return None
        try:
            v, _ = self.s.read("data", m["node"])
        except KernelError:
            return None
        return [x * m.get("scale", 1.0) for x in v]


def _eq_head(rd: _EqReader):
    """(时基, {量: 整条}, R, Z, nbdry 整条)——一个来源里按片不变的那几样。时基或网格取不到时抛 KernelError。"""
    tb = rd.series("time")
    if not tb:
        raise KernelError(f"{rd.src}: no time base")
    scal = {q: rd.series(q) for q in EQ_SCALARS}
    r, z = rd.series("r"), rd.series("z")
    if not r or not z:                                   #: 树在、网格节点没数（#115672 实测）：取不到，不是故障
        raise KernelError(f"{rd.src}: no R / Z grid in this tree")
    return tb, scal, r, z, rd.series("nbdry")


def _eq_slice(src: str, tree: str, tb, scal, r, z, nb, k: int, flat, dims, bd, qpsi, pres) -> dict:
    """一片的比较件（``fetch_equilibrium`` 的返回形）。``flat`` · ``bd`` · ``qpsi`` · ``pres`` 是第 k 片的 ψ · 边界 · q · p
    （单片按下标读来的，或整条读来再切的——两条路交到这里的是同一串数）。"""
    out = {"source": src, "label": EQ_SOURCES.get(src, src), "tree": tree,
           "slice_index": k, "n_slices": len(tb), "slice_time_s": tb[k], "scalars": {}, "empty": []}
    for q in EQ_SCALARS:
        v = scal[q]
        #: ★「在而全零」的槽（实时 EFIT 的 \\Q95 · \\PRES 在 #63948 上即是）按空槽记，不当成读数
        if v is None or len(v) != len(tb) or not any(v):
            out["empty"].append(q)
            continue
        out["scalars"][q] = v[k]
    #: ★离线 EFIT 树的 \\VOLUME 数值约 1e7：是 cm³（标签却写 m^3，fydoc 平衡绑定页记着）；另两棵树是 m³
    if out["scalars"].get("volume", 0.0) > 1e3:
        out["scalars"]["volume"] *= 1e-6
        out["volume_was_cm3"] = True
    nw, nh = len(r), len(z)
    if len(flat) != nw * nh:
        raise KernelError(f"{src}: PSIRZ slice has {len(flat)} values for a {nw}x{nh} grid (dims {dims})")
    npt = int(nb[k]) if nb and len(nb) == len(tb) else len(bd) // 2
    out["boundary"] = [[bd[2 * p], bd[2 * p + 1]] for p in range(min(npt, len(bd) // 2))
                       if bd[2 * p] > 0.0]
    orient_psi(out, flat, r, z)
    out["qpsi"], out["pres"] = qpsi, pres
    return out


def fetch_equilibrium(s: "Mds", sig: dict, src: str, shot: int, t: float) -> dict:
    """一个来源离 t 最近的一片：标量 + ψ(R,Z) + 边界 + q(ψ_N) · p(ψ_N)。树不在 / 节点没数时抛 KernelError。
    大数组（ψ · 边界 · q · p）只按下标取第 k 片；整段时间序列见 :class:`EquilibriumSeries`（整条读一次再切）。"""
    rd = _EqReader(s, sig, src, shot)
    tb, scal, r, z, nb = _eq_head(rd)
    k = min(range(len(tb)), key=lambda i: abs(tb[i] - t))
    flat, dims = s.read("data", rd.one("psirz")["node"], [Mds.ALL, Mds.ALL, k])
    bd, _bdims = s.read("data", rd.one("bdry")["node"], [Mds.ALL, Mds.ALL, k])
    prof = {}
    for q in ("qpsi", "pres"):
        m = rd.one(q)
        try:
            prof[q] = s.read("data", m["node"], [Mds.ALL, k])[0] if m else None
        except KernelError:
            prof[q] = None
    return _eq_slice(src, sig[f"{src}_time"]["tree"], tb, scal, r, z, nb, k, flat, dims, bd, prof["qpsi"], prof["pres"])


#: 一棵树的片数超过要用的片数的这么多倍（实时 EFIT / P-EFIT 每毫秒级一片），大数组就不整条读，只按下标取要的那几片
SPARSE_FACTOR = 4


class EquilibriumSeries:
    """一个来源的整段。构造时读一次按片不变的那几样（时基 · 标量 · 网格）；``load(ks)`` 读 ψ · 边界 · q · p：
    要的片占这棵树的片数不太少时，**整个数组**各读一次（``[..., 时间]``，线上快轴在前），否则（树的片数 > ``SPARSE_FACTOR``
    × 要的片数）只按下标把要的每一片读一次。``slice(k)`` 把第 k 片交给与 ``fetch_equilibrium`` 同一段 ``_eq_slice``——
    两种读法交过去的是同一串数（README §6.4 逐片核过）。"""

    def __init__(self, s: "Mds", sig: dict, src: str, shot: int):
        self.s, self.rd = s, _EqReader(s, sig, src, shot)
        self.src, self.tree = src, sig[f"{src}_time"]["tree"]
        self.tb, self.scal, self.r, self.z, self.nb = _eq_head(self.rd)
        self.arr: dict = {}
        self.slab: dict = {}
        self.mode = None

    def nearest(self, t: float) -> int:
        return min(range(len(self.tb)), key=lambda i: abs(self.tb[i] - t))

    def load(self, ks) -> None:
        """读要用的片（``ks``：片号的集合）的大数组；树不在 / ψ 或边界没数时抛 KernelError。"""
        ks = sorted(set(ks))
        self.mode = "slab" if len(self.tb) > SPARSE_FACTOR * max(1, len(ks)) else "whole"
        for q in ("psirz", "bdry", "qpsi", "pres"):
            m = self.rd.one(q)
            need = q in ("psirz", "bdry")
            if m is None:
                if need:
                    raise KernelError(f"{self.src}: no {q} node in the bindings")
                self.arr[q] = None
                continue
            sub = [Mds.ALL, Mds.ALL] if q in ("psirz", "bdry") else [Mds.ALL]
            try:
                if self.mode == "slab":
                    for k in ks:
                        self.slab.setdefault(k, {})[q] = self.s.read("data", m["node"], sub + [k])
                    continue
                v, dims = self.s.read("data", m["node"])
            except KernelError:
                if need:
                    raise
                self.arr[q] = None
                for k in ks:
                    self.slab.setdefault(k, {})[q] = None
                continue
            #: 最慢的轴（线上 dims 的最后一个）必须是时间，否则切不出片
            if not dims or dims[-1] != len(self.tb):
                raise KernelError(f"{self.src}: {m['node']} dims {dims} do not end in the {len(self.tb)} time slices")
            self.arr[q] = (v, dims, len(v) // dims[-1])

    def _cut(self, q, k):
        if self.mode == "slab":
            got = self.slab.get(k, {}).get(q)
            return (None, None) if got is None else got
        a = self.arr.get(q)
        if a is None:
            return None, None
        v, dims, per = a
        return v[k * per:(k + 1) * per], list(dims[:-1]) + [1]

    def slice(self, k: int) -> dict:
        flat, dims = self._cut("psirz", k)
        bd, _ = self._cut("bdry", k)
        qpsi, _ = self._cut("qpsi", k)
        pres, _ = self._cut("pres", k)
        return _eq_slice(self.src, self.tree, self.tb, self.scal, self.r, self.z, self.nb, k, flat, dims, bd, qpsi, pres)


def orient_psi(out: dict, flat: list, r: list, z: list) -> None:
    """平铺的 ψ → ``out['psi'][i][j]``（i 沿 R）。R 是快轴还是慢轴，nw == nh 时形状说不出来，轴处的 ψ 也分不出来
    （轴在图的正中，转置后还是它）。由边界定：边界点应落在同一条等 ψ 线上——取 ψ 在边界点上散得小的那种摆法，
    散度（按 |ψ_bnd − ψ_axis| 归一）记进 ``boundary_psin_spread`` 当自检。树与 g-file 走同一段。"""
    nw, nh = len(r), len(z)
    a = [[flat[i + nw * j] for j in range(nh)] for i in range(nw)]
    b = [[flat[j + nh * i] for j in range(nh)] for i in range(nw)] if nw == nh else None

    def spread(m):
        v = [psi_at({"grid_r": r, "grid_z": z, "psi": m}, p[0], p[1]) for p in out["boundary"]]
        mu = mean(v)
        return math.sqrt(mean([(x - mu) ** 2 for x in v]))

    sc = out["scalars"]
    psi = a
    if len(out["boundary"]) > 8:
        sa, sb = spread(a), (spread(b) if b is not None else float("inf"))
        psi = a if sa <= sb else b
        out["psirz_first_axis"] = "R" if psi is a else "Z"
        if "psi_axis" in sc and "psi_bnd" in sc:
            out["boundary_psin_spread"] = min(sa, sb) / abs(sc["psi_bnd"] - sc["psi_axis"])
    out.update(grid_r=r, grid_z=z, psi=psi)


#: ---- 本地参考平衡：G-EQDSK（+ 可选 A-EQDSK）。★只作比较，同上。
_FNUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][-+]?\d+)?")


def read_afile(path: str) -> dict:
    """A-EQDSK 的几个标量（EFIT ``write_a`` 的固定次序；长度随 ``mco2v`` / ``mco2r`` 变的四段按第 4 行给的数跳过）。
    长度单位 cm、体积 cm³ 的换成 m / m³。返回 {q0, q95, li, betap, w_mhd, volume, axis_r, axis_z, ip, kappa, …}。"""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    k = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith("*"))
    head = lines[k].split()
    #: '*' time jflag lflag limloc mco2v mco2r qmflag nlold nlnew
    mco2v, mco2r = int(head[5]), int(head[6])
    v = [float(x.replace("D", "E").replace("d", "e")) for x in _FNUM.findall("\n".join(lines[k + 1:]))]
    names = ["tsaisq", "rcencm", "bcentr", "pasmat", "cpasma", "rout", "zout", "aout", "eout", "doutu", "doutl",
             "vout", "rcurrt", "zcurrt", "qsta", "betat", "betap", "ali", "oleft", "oright", "otop", "obott",
             "qpsib", "vertn"]
    a = dict(zip(names, v))
    p = len(names) + 2 * mco2v + 2 * mco2r
    tail = ["shearb", "bpolav", "s1", "s2", "s3", "qout", "olefs", "orighs", "otops", "sibdry", "areao", "wplasm",
            "terror", "elongm", "qqmagx", "cdflux", "alpha", "rttt", "psiref", "xndnt", "rseps1", "zseps1", "rseps2",
            "zseps2", "sepexp", "obots", "btaxp", "btaxv", "aaq1", "aaq2", "aaq3", "seplim", "rmagx", "zmagx",
            "simagx", "taumhd", "betapd", "betatd", "wplasmd", "diamag"]
    a.update(zip(tail, v[p:p + len(tail)]))
    return {"time_s": float(head[1]) / 1e3, "q0": a.get("qqmagx"), "q95": a.get("qpsib"), "li": a.get("ali"),
            "betap": a.get("betap"), "betan": None, "w_mhd": a.get("wplasm"),
            "volume": a["vout"] * 1e-6 if "vout" in a else None,
            "axis_r": a["rmagx"] / 100 if "rmagx" in a else None, "axis_z": a["zmagx"] / 100 if "zmagx" in a else None,
            "ip": a.get("cpasma"), "kappa": a.get("eout"), "b0": a.get("bcentr"), "chi2": a.get("tsaisq")}


def read_reference(lib: "Lib", gfile: str, afile: str | None = None, label: str | None = None) -> dict:
    """本地 g-file（+ a-file）→ 与 :func:`fetch_equilibrium` 同形的一份「对方」：标量 · ψ(R,Z) · 边界 · q · p。
    g-file 由库里的读者读（与页面同一份）；ψ 的轴序照树的办法由边界判；ψ 是 Wb 还是 Wb/rad 由安培环路还原的 I_p
    与 g-file 自报的电流对（``compare`` 里）。a-file 给 l_i · β_p · W · V（g-file 里没有）。"""
    g = lib.gfile(Path(gfile).read_text(encoding="utf-8", errors="replace"))
    nw, nh = int(g["nw"]), int(g["nh"])
    r = [g["rleft"] + g["rdim"] * i / (nw - 1) for i in range(nw)]
    z = [g["zmid"] - 0.5 * g["zdim"] + g["zdim"] * j / (nh - 1) for j in range(nh)]
    m = re.search(r"#\s*(\d+)\s+(\d+)\s*(ms)?", g.get("header") or "")
    qpsi = list(g["qpsi"])
    xq = [i / (len(qpsi) - 1) for i in range(len(qpsi))]
    sc = {"q0": qpsi[0], "q95": interp(0.95, xq, qpsi), "psi_axis": g["simag"], "psi_bnd": g["sibry"],
          "axis_r": g["rmaxis"], "axis_z": g["zmaxis"], "ip": g["current"], "b0": g["bcentr"]}
    out = {"source": label or Path(gfile).name, "label": label or Path(gfile).name, "tree": f"file:{Path(gfile).name}",
           "file": Path(gfile).name, "header": (g.get("header") or "").strip(),
           "shot_in_file": int(m.group(1)) if m else None,
           "slice_time_s": int(m.group(2)) / 1e3 if m else None, "slice_index": None, "n_slices": None,
           "scalars": sc, "empty": [],
           "boundary": [[rb, zb] for rb, zb in zip(g["rbbbs"], g["zbbbs"]) if rb > 0.0],
           "qpsi": qpsi, "pres": list(g["pres"])}
    orient_psi(out, list(g["psirz"]), r, z)
    if afile:
        a = read_afile(afile)
        out["afile"] = Path(afile).name
        out["afile_scalars"] = a
        for q in ("li", "betap", "w_mhd", "volume", "kappa"):
            if a.get(q) is not None:
                sc[q] = a[q]
        if out["slice_time_s"] is None:
            out["slice_time_s"] = a["time_s"]
    for q in ("li", "betap", "w_mhd", "volume"):
        if q not in sc:
            out["empty"].append(q)
    return out


def _inside(poly: list, r: float, z: float) -> bool:
    n, c = len(poly), False
    for i in range(n):
        (r1, z1), (r2, z2) = poly[i], poly[(i + 1) % n]
        if (z1 > z) != (z2 > z) and r < r1 + (z - z1) * (r2 - r1) / (z2 - z1):
            c = not c
    return c


def _seg_dist(p, a, b) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - ax - u * dx, p[1] - ay - u * dy)


def boundary_distance(a: list, b: list) -> dict:
    """两条闭合边界之间的距离：a 的每个点到 b 这条折线的最近距离（再反过来），取最大与平均 [m]。"""
    def one_way(p, q):
        d = [min(_seg_dist(x, q[i], q[(i + 1) % len(q)]) for i in range(len(q))) for x in p]
        return max(d), mean(d)
    ab, ba = one_way(a, b), one_way(b, a)
    return {"max_m": max(ab[0], ba[0]), "mean_m": 0.5 * (ab[1] + ba[1])}


def map_integrals(eq: dict, psi_axis: float, psi_bnd: float, psin_1d, pres_1d, per_rad: float = 1.0) -> dict:
    """同一把尺量两边：由 ψ(R,Z) · 边界 · p(ψ_N) 在网格上积出 V · W = 3/2∫p dV · β_p · l_i。
    B_p = |∇ψ|/R（ψ 为 Wb/rad）；B_pa = ∮B_p dl / L_p（安培环路，不用任何一方报的 I_p）；
    β_p = 2μ₀⟨p⟩_V / B_pa²，l_i(1) = ⟨B_p²⟩_V / B_pa²，l_i(3) = 2∫B_p² dV / (μ₀² I_p² R_geo)，I_p = ∮B_p dl / μ₀。
    ``per_rad``：图上的 ψ 除以它才是 Wb/rad（图是 Wb 时给 2π）。"""
    gr, gz, psi, bnd = eq["grid_r"], eq["grid_z"], eq["psi"], eq["boundary"]
    dr, dz = gr[1] - gr[0], gz[1] - gz[0]
    fi = {"grid_r": gr, "grid_z": gz, "psi": psi}

    def bp(r, z):
        h = 0.25 * min(abs(dr), abs(dz))
        gR = (psi_at(fi, r + h, z) - psi_at(fi, r - h, z)) / (2 * h)
        gZ = (psi_at(fi, r, z + h) - psi_at(fi, r, z - h)) / (2 * h)
        return math.hypot(gR, gZ) / r / per_rad

    vol = w = bp2 = 0.0
    sub = 3                                           #: 每格 3×3 个子点：33² 的粗图上边界格才不至于整格进出
    for i in range(len(gr)):
        for j in range(len(gz)):
            for a in range(sub):
                for b in range(sub):
                    r = gr[i] + ((a + 0.5) / sub - 0.5) * dr
                    z = gz[j] + ((b + 0.5) / sub - 0.5) * dz
                    if not _inside(bnd, r, z):
                        continue
                    dv = 2 * math.pi * r * abs(dr * dz) / sub ** 2
                    x = min(max((psi_at(fi, r, z) - psi_axis) / (psi_bnd - psi_axis), 0.0), 1.0)
                    vol += dv
                    w += 1.5 * interp(x, psin_1d, pres_1d) * dv
                    bp2 += bp(r, z) ** 2 * dv
    circ = lp = 0.0
    for i in range(len(bnd)):
        p, q = bnd[i], bnd[(i + 1) % len(bnd)]
        dl = math.hypot(q[0] - p[0], q[1] - p[1])
        lp += dl
        circ += bp(0.5 * (p[0] + q[0]), 0.5 * (p[1] + q[1])) * dl
    bpa = circ / lp
    rgeo = 0.5 * (max(p[0] for p in bnd) + min(p[0] for p in bnd))
    ip = circ / MU0
    return {"volume_m3": vol, "w_mhd_J": w, "betap": 2 * MU0 * (w / 1.5 / vol) / bpa ** 2,
            "li1": bp2 / vol / bpa ** 2, "li3": 2 * bp2 / (MU0 ** 2 * ip ** 2 * rgeo), "ip_ampere_A": ip,
            "r_geo_m": rgeo}


def psin_difference(ours: dict, fa: dict, theirs: dict) -> dict | None:
    """ψ_N 图之差：在**我们的**网格点上、两条边界都在内的那些点，把对方的 ψ_N 双线性插过来相减。"""
    ta, tb = theirs["scalars"].get("psi_axis"), theirs["scalars"].get("psi_bnd")
    if ta is None or tb is None or not theirs.get("boundary"):
        return None
    fi_t = {"grid_r": theirs["grid_r"], "grid_z": theirs["grid_z"], "psi": theirs["psi"]}
    d = []
    for i, r in enumerate(ours["grid_r"]):
        for j, z in enumerate(ours["grid_z"]):
            if not (theirs["grid_r"][0] <= r <= theirs["grid_r"][-1] and theirs["grid_z"][0] <= z <= theirs["grid_z"][-1]):
                continue
            if _inside(ours["boundary"], r, z) and _inside(theirs["boundary"], r, z):
                mine = (fa["psi_axis"] - ours["psi"][i][j]) / (fa["psi_axis"] - fa["psi_bnd"])
                d.append(mine - (psi_at(fi_t, r, z) - ta) / (tb - ta))
    if not d:
        return None
    return {"n_points": len(d), "rms": math.sqrt(mean([x * x for x in d])), "max_abs": max(abs(x) for x in d),
            "mean": mean(d), "their_grid": [len(theirs["grid_r"]), len(theirs["grid_z"])]}


#: X 点平衡：两个 X 点的 ψ_N 差在它之内就算上下平衡的双零（DN），否则按哪个 X 点在分离面上记下单零 / 上单零。
#: 0.005 ≈ EAST 外中平面上 1–2 mm 的两条分离面间距（dRsep），与离线 EFIT 自己记 DN 的口径同量级。
XPT_DN_TOL = 0.005
#: 在哪里找 X 点：R 与 |Z| 的窗（EAST 偏滤器 X 点都在这里；窗外的鞍点不是等离子体边界的那一个）
XPT_WINDOW = {"r": (1.30, 1.90), "absz": (0.50, 1.05)}


def xpoint_balance(eq: dict, psi_axis: float, psi_bnd: float) -> dict | None:
    """上、下两个 X 点（ψ 图的鞍点）的位置与 ψ_N，以及上下平衡：``dpsin`` = ψ_N(上) − ψ_N(下)。
    ``config``：|dpsin| < ``XPT_DN_TOL`` 记 ``DN``；否则 ψ_N 小的那个 X 点在分离面上——下 X 点记 ``LSN``、上 X 点 ``USN``；
    两个 X 点都在分离面外（ψ_N > 1 + ``XPT_DN_TOL``）记 ``LIM``（限制器位形）。
    做法：窗内网格点上找 |∇ψ|² 最小的格点（中心差分），用该点 3×3 的二次模型（ψ_R · ψ_Z · ψ_RR · ψ_ZZ · ψ_RZ）
    解梯度为零的偏移（夹在一格之内），ψ 取二次模型在那里的值。纯标准库；网格 ``psi[i][j]``（i 沿 R、j 沿 Z），
    与本文件别处同一摆法，所以我们的图、树的图、本地 g-file 走同一段。"""
    gr, gz, psi = eq["grid_r"], eq["grid_z"], eq["psi"]
    if not psi or psi_bnd == psi_axis:
        return None
    dr, dz = gr[1] - gr[0], gz[1] - gz[0]
    nr, nz = len(gr), len(gz)
    out = {}
    for side, sgn in (("upper", 1.0), ("lower", -1.0)):
        best = None
        for i in range(1, nr - 1):
            if not XPT_WINDOW["r"][0] <= gr[i] <= XPT_WINDOW["r"][1]:
                continue
            for j in range(1, nz - 1):
                if not (sgn * gz[j] > 0 and XPT_WINDOW["absz"][0] <= abs(gz[j]) <= XPT_WINDOW["absz"][1]):
                    continue
                pr = (psi[i + 1][j] - psi[i - 1][j]) / (2 * dr)
                pz = (psi[i][j + 1] - psi[i][j - 1]) / (2 * dz)
                g2 = pr * pr + pz * pz
                if best is None or g2 < best[0]:
                    best = (g2, i, j)
        if best is None:
            return None
        _, i, j = best
        p0 = psi[i][j]
        pr = (psi[i + 1][j] - psi[i - 1][j]) / (2 * dr)
        pz = (psi[i][j + 1] - psi[i][j - 1]) / (2 * dz)
        prr = (psi[i + 1][j] - 2 * p0 + psi[i - 1][j]) / dr ** 2
        pzz = (psi[i][j + 1] - 2 * p0 + psi[i][j - 1]) / dz ** 2
        prz = (psi[i + 1][j + 1] - psi[i + 1][j - 1] - psi[i - 1][j + 1] + psi[i - 1][j - 1]) / (4 * dr * dz)
        det = prr * pzz - prz * prz
        if det < 0:                                        #: 鞍点：Hessian 行列式为负；解 H·δ = −∇ψ
            ddr = (-pr * pzz + pz * prz) / det
            ddz = (-pz * prr + pr * prz) / det
            ddr = max(-abs(dr), min(abs(dr), ddr))
            ddz = max(-abs(dz), min(abs(dz), ddz))
        else:                                              #: 格点附近不像鞍点：就取格点（照记）
            ddr = ddz = 0.0
        val = p0 + 0.5 * (pr * ddr + pz * ddz)
        out[side] = {"r": gr[i] + ddr, "z": gz[j] + ddz, "psin": (val - psi_axis) / (psi_bnd - psi_axis),
                     "saddle": det < 0}
    d = out["upper"]["psin"] - out["lower"]["psin"]
    out["dpsin"] = d
    out["config"] = "DN" if abs(d) < XPT_DN_TOL else ("LSN" if d > 0 else "USN")
    if min(out["upper"]["psin"], out["lower"]["psin"]) > 1.0 + XPT_DN_TOL:
        out["config"] = "LIM"                              #: 两个 X 点都在分离面外：边界由限制器定
    return out


def _tier_eq(tier: dict) -> tuple[dict, dict]:
    eq = {"grid_r": tier["grid"]["r"], "grid_z": tier["grid"]["z"], "psi": tier["psi"], "boundary": tier["boundary"]}
    return eq, tier["facts"]


def _fetch_trees(lib, doc, sig, srcs, shot, t, signals, server, timeout, theirs, errors):
    """装置的平衡树（离线 EFIT · P-EFIT · 实时 EFIT）各取离 t 最近的一片进 ``theirs``；取不到的记进 ``errors``。
    另取实测逆磁储能（返回它，取不到为 None）。"""
    host, port = server_of(server)
    s = lib.mds_open(host, port, timeout)
    try:
        for src in srcs:
            t0 = time.time()
            try:
                e = fetch_equilibrium(s, sig, src, shot, t)
            except KernelError as err:                  # 树不在 / 节点没数：是数据，不是故障
                errors[src] = sanitize(str(err))[:300]
                s.tree = None
                log(f"compare: {src} 取不到——{errors[src][:120]}")
                continue
            _their_integrals(e, False)
            theirs[src] = e
            log(f"compare: {src} 第 {e['slice_index']}/{e['n_slices']} 片 t = {e['slice_time_s']:.4f} s（{time.time() - t0:.1f} s）")
        #: 实测逆磁储能（装置文档 magnetics/fylite:signal 的 w_dia；树不在的炮记为取不到）：±10 ms 均值
        w_dia = None
        m = ((doc.get("magnetics") or {}).get("fylite:signal") or {}).get("w_dia") or (
            json.loads(Path(signals).read_text(encoding="utf-8")).get("magnetics", {}).get("fylite:signal", {})
            .get("w_dia") if signals else None)
        if m:
            try:
                s.tree = None
                s.open_tree(m["tree"], shot)
                v, tbw = s.read("data", m["node"])[0], s.read("dim_of", m["node"])[0]
                sel = [v[i] for i in range(min(len(v), len(tbw))) if abs(tbw[i] - t) <= 0.010]
                if sel and any(v):
                    w_dia = mean(sel) * m.get("scale", 1.0)
            except KernelError as err:
                errors["w_dia"] = sanitize(str(err))[:200]
    finally:
        s.close()
    return w_dia


def our_integrals(res: dict) -> dict:
    """结果里每一档带 ψ 图的解 → {档: {eq, fa, pr, int}}，``int`` 是同尺量出的 V · W · β_p · l_i · 安培环路 I_p。
    ★我们的 ψ 图是 Wb 还是 Wb/rad 不靠记忆：安培环路还原的 I_p 与这一档自己拟合的 I_p 对一下，
    取 1 与 2π 里对得上的那个（实测：结果 JSON 的 ψ 是 Wb，比值 6.28）。"""
    ours = {}
    for name, tier in (res.get("tiers") or {}).items():
        if tier.get("status") not in ("ok", "unphysical") or not tier.get("psi"):
            continue                                      #: unphysical 的档数照留、照比（比较表里另标）
        eq, fa = _tier_eq(tier)
        pr = tier["profiles"]
        it = _same_ruler(eq, fa["psi_axis"], fa["psi_bnd"], pr["psin"], pr["pres"], abs(fa["ip"]))
        ours[name] = {"eq": eq, "fa": fa, "pr": pr, "int": it}
    return ours


def _same_ruler(eq: dict, psi_axis: float, psi_bnd: float, psin_1d, pres_1d, ip_ref) -> dict:
    """``map_integrals``，ψ 图的单位（Wb/rad 或 Wb）由安培环路还原的 I_p 与 ``ip_ref`` 之比在 1 与 2π 里取对得上的那个；
    ``ip_ref`` 缺时按 Wb/rad。比值记进 ``ip_ratio``（换算之后应近 1——这一条就是 ψ 单位的自检）。"""
    it = map_integrals(eq, psi_axis, psi_bnd, psin_1d, pres_1d)
    per_rad = 1.0
    if ip_ref:
        ratio = it["ip_ampere_A"] / abs(ip_ref)
        per_rad = min((1.0, 2 * math.pi), key=lambda c: abs(ratio / c - 1.0))
        if per_rad != 1.0:
            it = map_integrals(eq, psi_axis, psi_bnd, psin_1d, pres_1d, per_rad)
        it["ip_ratio"] = it["ip_ampere_A"] / abs(ip_ref)
    it["psi_map_unit"] = "Wb" if per_rad != 1.0 else "Wb/rad"
    return it


def _their_integrals(e: dict, per_rad_check: bool) -> None:
    """对方一片的同尺积分（要 p(ψ_N) · ψ 两端值 · 边界）。本地 g-file 的 ψ 单位由它自报的电流核（``per_rad_check``）；
    树自述 V·s/rad，按 1 算、由输出末尾的同尺自检核。"""
    sc = e["scalars"]
    if e.get("pres") and not any(e["pres"]):
        e["empty"].append("pres")
    if e.get("pres") and "psi_axis" in sc and "psi_bnd" in sc and len(e["boundary"]) > 8:
        n = len(e["pres"])
        x = [i / (n - 1) for i in range(n)]
        e["int"] = (_same_ruler(e, sc["psi_axis"], sc["psi_bnd"], x, e["pres"], sc.get("ip")) if per_rad_check
                    else map_integrals(e, sc["psi_axis"], sc["psi_bnd"], x, e["pres"]))
        if "pres" in e["empty"]:
            e["int"]["w_mhd_J"] = e["int"]["betap"] = None


def compare_row(name: str, o: dict, src: str, e: dict, t: float) -> dict:
    """一档（``our_integrals`` 的一项）× 一个来源的一片 → 比较表的一行；成对的量是 [我们, 对方]。"""
    sc, ti = e["scalars"], e.get("int") or {}
    fa, oi = o["fa"], o["int"]
    bd = boundary_distance(o["eq"]["boundary"], e["boundary"]) if len(e["boundary"]) > 8 else None
    xo = xpoint_balance(o["eq"], fa["psi_axis"], fa["psi_bnd"])
    xe = (xpoint_balance(e, sc["psi_axis"], sc["psi_bnd"]) if e.get("psi") and "psi_axis" in sc and "psi_bnd" in sc
          else None)
    xp = lambda x, *k: None if x is None else (x[k[0]] if len(k) == 1 else x[k[0]][k[1]])  # noqa: E731
    return {
        #: X 点平衡（上 X 点 ψ_N − 下 X 点 ψ_N；DN / LSN / USN），两边同一段程序（``xpoint_balance``）
        "xpoint_dpsin": [xp(xo, "dpsin"), xp(xe, "dpsin")], "xpoint_config": [xp(xo, "config"), xp(xe, "config")],
        "xpoint_upper_psin": [xp(xo, "upper", "psin"), xp(xe, "upper", "psin")],
        "xpoint_lower_psin": [xp(xo, "lower", "psin"), xp(xe, "lower", "psin")],
        "tier": name, "source": src, "slice_time_s": e["slice_time_s"], "dt_s": e["slice_time_s"] - t,
        "q0": [fa.get("q0"), sc.get("q0")], "q95": [fa.get("q95"), sc.get("q95")],
        #: l_i：两边用同一把尺（map_integrals 的 l_i(1)）量，外加各自自报的（我们 li3，对方 \\LI）
        "li1_same_ruler": [oi["li1"], ti.get("li1")], "li_reported": [fa.get("li3"), sc.get("li")],
        "betap_same_ruler": [oi["betap"], ti.get("betap")], "betap_reported": [None, sc.get("betap")],
        "w_mhd_same_ruler_J": [oi["w_mhd_J"], ti.get("w_mhd_J")], "w_mhd_reported_J": [None, sc.get("w_mhd")],
        "volume_m3": [oi["volume_m3"], ti.get("volume_m3"), sc.get("volume")],
        "axis_r": [fa.get("axis_r"), sc.get("axis_r")], "axis_z": [fa.get("axis_z"), sc.get("axis_z")],
        "axis_distance_m": (math.hypot(fa["axis_r"] - sc["axis_r"], fa["axis_z"] - sc["axis_z"])
                            if "axis_r" in sc and "axis_z" in sc else None),
        "boundary_distance": bd, "psin_map_difference": psin_difference(o["eq"], fa, e)}


def compare(res: dict, *, lib: "Lib | None" = None, time_s: float | None = None, sources="efit,pefit,efitrt",
            signals: str | None = None, server: str | None = None, timeout: float = 120.0,
            result_name: str | None = None, refs: list | None = None) -> dict:
    """``compare`` 的进程内形：一份结果字典（``reconstruct`` 的返回值，或 ``run`` 写出的 JSON 读回来）↔ 装置自己的
    平衡重建离它最近的一片，和/或本地参考平衡文件。返回比较文档（``@type: fylite:KineticReconComparison``，与
    ``compare -o`` 写出的同一份；``rows`` 为空 = 一个来源都没取到）。
    ``sources``：逗号串或列表（空 = 不连 MDSplus）；有来源时要 mdsip 服务器（``server`` 或 ``$FYLITE_MDSIP_SERVER``）；
    ``signals``：节点名表文件的路径（同 ``--signals``）；``time_s`` 缺省取结果里的。
    ``refs``：本地参考 [{"gfile": 路径, "afile": 路径或 None, "label": 名或 None}, …]（同 ``--gfile/--afile/--label``）。"""
    lib = lib or Lib(DEFAULT_LIB)
    shot, t = int(res["shot"]), float(time_s if time_s is not None else res["time_s"])
    if not isinstance(sources, str):
        sources = ",".join(sources)
    srcs = [x for x in sources.split(",") if x]
    ours = our_integrals(res)
    if not ours:
        raise SystemExit(f"{result_name or '结果'}：没有一档带 ψ 图的解可比")
    theirs, errors, w_dia = {}, {}, None
    for ref in refs or []:
        e = read_reference(lib, ref["gfile"], ref.get("afile"), ref.get("label"))
        key = e["source"]
        while key in theirs:
            key += "'"
        e["source"] = key
        if e.get("shot_in_file") not in (None, shot):
            e["shot_mismatch"] = True
            log(f"compare: ★{e['file']} 写着 #{e['shot_in_file']}，结果是 #{shot}")
        if e["slice_time_s"] is None:
            e["slice_time_s"] = t
        _their_integrals(e, True)
        theirs[key] = e
        log(f"compare: {key}（本地文件，t = {e['slice_time_s']:.4f} s，ψ 边界散度 {e.get('boundary_psin_spread', float('nan')):.1e}）")
    if srcs:
        doc, _res = lib.device("east", shot, res.get("measurement_chain") or "east")
        sig = eq_signals(doc, signals)
        w_dia = _fetch_trees(lib, doc, sig, srcs, shot, t, signals, server, timeout, theirs, errors)
    rows = [compare_row(name, o, src, e, t) for src, e in theirs.items() for name, o in ours.items()]
    out = {"@type": "fylite:KineticReconComparison", "app": APP, "version": VERSION, "shot": shot, "time_s": t,
           "result": result_name,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "comment": "对拍：装置自己的平衡重建（树或本地参考文件）是另一个程序的答案，只作比较。含实验数据派生量：不入仓。服务器地址记作 mds.invalid。",
           "same_ruler": map_integrals.__doc__.strip(),
           "sources": {k: {x: v[x] for x in ("label", "tree", "slice_index", "n_slices", "slice_time_s", "scalars",
                                             "empty", "psirz_first_axis", "boundary_psin_spread", "file", "afile", "header", "shot_in_file",
                                             "shot_mismatch", "afile_scalars") if x in v} | {"integrals": v.get("int")}
                       for k, v in theirs.items()},
           "unavailable": errors, "measured": {"w_dia_J": w_dia},
           "ours": {k: {"facts": {x: v["fa"].get(x) for x in ("q0", "q95", "li3", "axis_r", "axis_z", "ip")},
                        "integrals": v["int"],
                        **({"status": "unphysical", "physics_failed": (res["tiers"][k].get("physics_check") or {}).get("failed")}
                           if res["tiers"][k].get("status") == "unphysical" else {})} for k, v in ours.items()},
           "rows": rows}
    return out


def cmd_compare(a) -> int:
    res = json.loads(Path(a.result).read_text(encoding="utf-8"))
    out = compare(res, lib=Lib(Path(a.lib) if a.lib else DEFAULT_LIB), time_s=a.time, sources=a.sources,
                  signals=a.signals, server=a.server, timeout=a.timeout, result_name=Path(a.result).name,
                  refs=a.refs or None)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print_comparison(out)
    log(f"-> {a.out}")
    return 0 if out["rows"] else 1


def print_comparison(out: dict) -> None:
    def f(x, n=3):
        return "—" if x is None else f"{x:.{n}f}"
    print(f"#{out['shot']}  t = {out['time_s']} s   ours | theirs（同尺 = 两边都由 ψ 图 + p(ψ_N) 用同一段程序积出）")
    for src, why in out["unavailable"].items():
        print(f"  {EQ_SOURCES.get(src, src)}：取不到（{why[:90]}）")
    hdr = ("tier", "source", "t_slice", "q0", "q95", "li(1) 同尺", "βp 同尺", "W 同尺 [kJ]", "轴距 [mm]",
           "边界 max/mean [mm]", "ΔψN rms/max", "X 点 ψN(上)−ψN(下) · 形位")
    print("  " + " | ".join(hdr))
    for k, v in (out.get("ours") or {}).items():
        if v.get("status") == "unphysical":
            print(f"  ★★档 {k} 物理校验没过（{', '.join(v.get('physics_failed') or [])}）：下面这一档的行只作诊断")
    for r in out["rows"]:
        bd, pm = r["boundary_distance"], r["psin_map_difference"]
        w = r["w_mhd_same_ruler_J"]
        print("  " + " | ".join([
            r["tier"], r["source"], f(r["slice_time_s"], 4),
            f"{f(r['q0'][0])} / {f(r['q0'][1])}", f"{f(r['q95'][0])} / {f(r['q95'][1])}",
            f"{f(r['li1_same_ruler'][0])} / {f(r['li1_same_ruler'][1])}",
            f"{f(r['betap_same_ruler'][0])} / {f(r['betap_same_ruler'][1])}",
            f"{f(w[0] / 1e3, 1)} / {f(None if w[1] is None else w[1] / 1e3, 1)}",
            f(None if r["axis_distance_m"] is None else r["axis_distance_m"] * 1e3, 1),
            "—" if bd is None else f"{bd['max_m'] * 1e3:.1f} / {bd['mean_m'] * 1e3:.1f}",
            "—" if pm is None else f"{pm['rms']:.4f} / {pm['max_abs']:.4f}",
            f"{f(r['xpoint_dpsin'][0], 4)} {r['xpoint_config'][0] or '—'} / {f(r['xpoint_dpsin'][1], 4)} {r['xpoint_config'][1] or '—'}"]))
    wd = (out.get("measured") or {}).get("w_dia_J")
    print(f"  实测逆磁储能 W_dia：{f(None if wd is None else wd / 1e3, 1)} kJ")
    print("  对方自报（AEQDSK）与同尺自检：")
    for src, e in out["sources"].items():
        sc, ti = e["scalars"], e.get("integrals") or {}
        print(f"    {src}: li {f(sc.get('li'))}（同尺 li1 {f(ti.get('li1'))} · li3 {f(ti.get('li3'))}）"
              f" · βp {f(sc.get('betap'))}（同尺 {f(ti.get('betap'))}）"
              f" · W {f(None if sc.get('w_mhd') is None else sc['w_mhd'] / 1e3, 1)} kJ"
              f"（同尺 {f(None if ti.get('w_mhd_J') is None else ti['w_mhd_J'] / 1e3, 1)}）"
              f" · V {f(sc.get('volume'))} m³（同尺 {f(ti.get('volume_m3'))}）"
              + (f" · 空槽 {','.join(e['empty'])}" if e.get("empty") else ""))
        if e.get("file"):
            print(f"      本地文件 {e['file']}" + (f" + {e['afile']}" if e.get("afile") else "")
                  + f" · ψ 图 {ti.get('psi_map_unit', '—')}（安培环路 I_p / 自报 I_p = {f(ti.get('ip_ratio'), 4)}）"
                  + f" · 边界上 ψ_N 散度 {e.get('boundary_psin_spread', float('nan')):.1e}"
                  + (" · ★炮号与结果不同" if e.get("shot_mismatch") else ""))


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
             "p_fast_max", "curv_p", "curv_f", "npp", "nff",
             #: 内核 profile-fit 扩展（只在 efit_fit 生效时出现）
             "pprime_basis", "ffprime_basis", "spline_tension_scale", "q0_target", "q0_weight", "q0_axis_row",
             "q0_minus_target", "jzero_rows", "jzero_rms", "jzero_max_abs", "jlocal_rows",
             "lincon_rows", "ip_sigma", "ip_measured")


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


# ================================================================================================ physics check
#: ★★物理校验（2026-09-22）：一档解出来、状态 ok，不等于物理上成立——#115672 7.95 s 之后档 M 解出负储能 W、q0 ≈ 0.1
#: 仍记 ok，下游会照单全收。每一档（M · K · P）解完都对这张表逐条过一遍；任一条不过，这一档**数照留**，状态改记
#: ``unphysical``（有别于 error / skipped），``physics_check.failed`` 列出没过的条目。
#: 界值一处定（这张表），每条带理由；``--phys-bounds 键=值,…`` 覆盖，``--no-physics-check`` 整个不做。
#: 储能 · β_p · l_i 用**同一把尺**（``map_integrals``：ψ 图 + 边界 + p(ψ_N) 在网格上积，与 compare / series 同一段程序），
#: 不用内核报的 li3（它把 LCFS 外 0 ≤ ψ_N ≤ 1 的格子也算进去——私有通量区等，见 README §7）。
PHYS_BOUNDS = {
    "w_min_J": {"value": 0.0, "kind": "physical",
                "why": "储能 W = 3/2∫p dV 必须为正：负 W 即拟合出的压强整体为负"},
    "betap_min": {"value": 0.0, "kind": "physical", "why": "β_p = 2μ₀⟨p⟩/B_pa² 必须为正（同 W）"},
    "betap_max": {"value": 5.0, "kind": "physical",
                  "why": "平衡极限 β_p ≲ R₀/a ≈ 1.85/0.45 ≈ 4（EAST）；高 β_p 放电实测 ≲ 3，取 5 留余量"},
    "p_neg_frac": {"value": 0.05, "kind": "physical",
                   "why": "p(ψ_N) 在 [0, 1] 上的最小值不得低于 −该份额 × 峰值：比压强行的相对 σ 下限（--sigma-floor 0.05）"
                          "还小的负值数据分辨不出，只当基函数的下冲；更深的负压强不是物理"},
    "q0_min": {"value": 0.3, "kind": "physical",
               "why": "q0 < 0.3 在托卡马克上没有观测过（锯齿把 q0 钳在 ≈ 0.7–1，MSE 实测最低 ≈ 0.6）"},
    "q0_max": {"value": 20.0, "kind": "physical", "why": "反剪切 / 电流空穴放电 q0 可到 10 上下，取 20 留余量"},
    "q95_min": {"value": 1.0, "kind": "physical", "why": "q95 ≤ 1 时外扭曲模必然失稳（Kruskal–Shafranov），放电不能维持"},
    "q_min": {"value": 0.0, "kind": "physical", "why": "q(ψ_N) 处处与 I_p · B_T 同号（本应用两者都取正），q ≤ 0 即剖面坏了"},
    "li_min": {"value": 0.3, "kind": "physical",
               "why": "内感 l_i(3)（同尺）：极端空心电流才低到 ≈ 0.4，取 0.3"},
    "li_max": {"value": 3.0, "kind": "physical", "why": "l_i(3) 极端峰化的放电 ≈ 2，取 3；更高是电流挤到磁轴上的坏解"},
    "limiter_tol_m": {"value": 0.01, "kind": "physical",
                      "why": "边界点可以贴着限制器（限制器位形），允许越出 1 cm（65² 网格间距 ≈ 2.5 cm 的插值误差量级）"},
    "psin_inside_tol": {"value": 0.02, "kind": "physical",
                        "why": "LCFS 内网格点的 ψ_N 应在 [0, 1]：低于 −容差 = 有比磁轴更极端的点（磁轴不是极值），"
                               "高于 1 + 容差 = 边界不是 ψ 的等值线；容差吸收双线性插值"},
    "ip_rel_tol": {"value": 0.05, "kind": "physical",
                   "why": "I_p 作等式约束时拟合值就是实测值；差过 5 % = 解没守住它"},
    "ip_sigma_mult": {"value": 5.0, "kind": "physical",
                      "why": "I_p 作带权测量（k-file 设定的 ip_sigma）时，差不超过这么多个 σ——与剔道阈 --reject-sigma 5 同一把尺"},
    "chi2_dof_max": {"value": 20.0, "kind": "statistical",
                     "why": "统计校验，不是物理：χ²/dof > 20 = 模型离数据几倍于误差棒，剔道也没救回来"},
}
#: 条目 id → 用到的界（页面按它画）；次序即报告次序
PHYS_CHECKS = ("w_positive", "betap_range", "p_nonnegative", "q0_range", "q95_min", "q_positive", "li3_range",
               "boundary_closed", "boundary_in_limiter", "axis_inside", "psi_sign", "axis_extremum", "ip_match",
               "chi2_dof", "base_tier")
PHYS_NOTE = ("物理校验：每档解完逐条核；任一条不过 → status = unphysical（数照留，failed 列出条目）。"
             "unphysical 有别于 error（没有解）与 skipped（没跑）。K / P 叠在哪一档上（K 在 M 上，P 在 on 那一档上），"
             "那一档 unphysical 时自己也记 unphysical（base_tier 条）——它们的设定点、ψ_N 映射都取自那一档。"
             "W · β_p · l_i(3) 用同尺积分（map_integrals），不用内核报的 li3。")


def phys_bounds(over) -> dict:
    """``PHYS_BOUNDS`` + 覆盖（``{"q0_min": 0.5}`` 或 ``"q0_min=0.5,chi2_dof_max=10"``）→ {键: {value, kind, why}}。"""
    out = {k: dict(v) for k, v in PHYS_BOUNDS.items()}
    if isinstance(over, str):
        pairs = [x.split("=", 1) for x in over.split(",") if x.strip()]
        if any(len(p) != 2 for p in pairs):
            raise SystemExit(f"--phys-bounds：要 键=值,…（得到 {over!r}）")
        over = {k.strip(): v for k, v in pairs}
    for k, v in (over or {}).items():
        if k not in out:
            raise SystemExit(f"--phys-bounds：不认识 {k!r}（可用 {', '.join(PHYS_BOUNDS)}）")
        try:
            out[k]["value"] = float(v)
        except (TypeError, ValueError):
            raise SystemExit(f"--phys-bounds：{k} 的值 {v!r} 不是数") from None
        out[k]["overridden"] = True
    return out


def _poly_area(p: list) -> float:
    return 0.5 * sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))


def physics_check(view: dict, *, ip_meas: float, limiter: dict | None, bounds: dict | None = None,
                  base: tuple | None = None) -> dict:
    """一档的视图（``tier_view`` 的返回值，或结果 JSON 里的一档）→ ``physics_check`` 块：
    {passed, failed: [id], checks: [{id, value, bound, pass, kind, why}], same_ruler}。
    ``ip_meas`` = 实测 |I_p| [A]；``limiter`` = {r: [...], z: [...]}（装置事实的限制器，None = 这条不核）；
    ``base`` = (这一档叠在的档名, 那一档的 status)——那一档 unphysical 则这一档的 base_tier 条不过。
    每条的 ``why`` 是一行中文：过了说量了什么，没过说为什么不物理。"""
    B = {k: v["value"] for k, v in (bounds or phys_bounds(None)).items()}
    fa, checks = view.get("facts") or {}, []

    def add(cid, value, bound, ok, why, kind="physical"):
        checks.append({"id": cid, "value": _rt(value) if isinstance(value, (float, list)) else value, "bound": bound,
                       "pass": None if ok is None else bool(ok), "kind": kind, "why": why})

    bnd = view.get("boundary") or []
    grid = view.get("grid") or {}
    pa, pb, ip = fa.get("psi_axis"), fa.get("psi_bnd"), fa.get("ip")
    it = None
    if len(bnd) >= 8 and fin(pa) and fin(pb) and pa != pb and fin(ip) and ip and view.get("psi"):
        try:
            eq = {"grid_r": grid["r"], "grid_z": grid["z"], "psi": view["psi"], "boundary": bnd}
            pr = view["profiles"]
            it = _same_ruler(eq, pa, pb, pr["psin"], pr["pres"], abs(ip))
        except (ZeroDivisionError, ValueError, KeyError, IndexError):
            it = None
    no_int = "同尺积分做不出（边界 / ψ 两端值 / I_p 缺或退化）"
    # ---- 储能 · β_p（同尺）
    w = it["w_mhd_J"] if it else None
    add("w_positive", w, f"> {B['w_min_J']:g} J", it is not None and w > B["w_min_J"],
        no_int if it is None else (f"同尺储能 W = {w / 1e3:.1f} kJ" if w > B["w_min_J"] else
                                   f"同尺储能 W = {w / 1e3:.1f} kJ ≤ {B['w_min_J']:g}：压强整体为负，不是物理解"))
    bp = it["betap"] if it else None
    okb = it is not None and B["betap_min"] < bp < B["betap_max"]
    add("betap_range", bp, [B["betap_min"], B["betap_max"]], okb,
        no_int if it is None else (f"同尺 β_p = {bp:.3f}" if okb else
                                   f"同尺 β_p = {bp:.3f} 不在 ({B['betap_min']:g}, {B['betap_max']:g}) 内"))
    # ---- 压强剖面 p(ψ_N) ≥ 0
    pres = [v for v in ((view.get("profiles") or {}).get("pres") or []) if fin(v)]
    if pres:
        pmin, pmax = min(pres), max(pres)
        lim = -B["p_neg_frac"] * max(pmax, 0.0)
        okp = pmax > 0 and pmin >= lim
        xs = (view.get("profiles") or {}).get("psin") or []
        at = xs[pres.index(pmin)] if len(xs) == len(pres) else None
        add("p_nonnegative", [pmin, pmax], f"min p ≥ −{B['p_neg_frac']:g} × max p", okp,
            (f"p(ψ_N) 最小 {pmin:.4g} Pa（峰值 {pmax:.4g} Pa）" + ("" if pmin >= 0 else "——下冲在分辨率以内"))
            if okp else f"p(ψ_N) 在 ψ_N ≈ {at if at is not None else '?'} 处低到 {pmin:.4g} Pa（峰值 {pmax:.4g} Pa）：负压强不是物理")
    else:
        add("p_nonnegative", None, f"min p ≥ −{B['p_neg_frac']:g} × max p", False, "结果里没有压强剖面")
    # ---- q
    q0, q95 = fa.get("q0"), fa.get("q95")
    okq = fin(q0) and B["q0_min"] <= q0 <= B["q0_max"]
    add("q0_range", q0, [B["q0_min"], B["q0_max"]], okq,
        f"q0 = {q0:.3f}" if okq else f"q0 = {q0 if q0 is None else round(q0, 4)} 不在 [{B['q0_min']:g}, {B['q0_max']:g}] 内")
    ok95 = fin(q95) and q95 > B["q95_min"]
    add("q95_min", q95, f"> {B['q95_min']:g}", ok95,
        f"q95 = {q95:.3f}" if ok95 else f"q95 = {q95} ≤ {B['q95_min']:g}：外扭曲模必然失稳")
    qs = [v for v in ((view.get("profiles") or {}).get("qpsi") or []) + ((view.get("q") or {}).get("q") or []) if fin(v)]
    qmin = min(qs) if qs else None
    okqp = qmin is not None and qmin > B["q_min"]
    add("q_positive", qmin, f"> {B['q_min']:g}", okqp,
        f"q(ψ_N) 最小 {qmin:.3f}" if okqp else ("结果里没有 q 剖面" if qmin is None else f"q(ψ_N) 最小 {qmin:.4g} ≤ {B['q_min']:g}"))
    # ---- l_i(3)（同尺）
    li = it["li3"] if it else None
    okl = it is not None and B["li_min"] <= li <= B["li_max"]
    add("li3_range", li, [B["li_min"], B["li_max"]], okl,
        no_int if it is None else (f"同尺 l_i(3) = {li:.3f}（内核报 {fa.get('li3', float('nan')):.3f}，口径不同）" if okl
                                   else f"同尺 l_i(3) = {li:.3f} 不在 [{B['li_min']:g}, {B['li_max']:g}] 内"))
    # ---- 边界：闭合 · 在限制器内 · 磁轴在内
    closed = False
    if len(bnd) >= 8:
        seg = sorted(math.hypot(bnd[i + 1][0] - bnd[i][0], bnd[i + 1][1] - bnd[i][1]) for i in range(len(bnd) - 1))
        gap = math.hypot(bnd[0][0] - bnd[-1][0], bnd[0][1] - bnd[-1][1])
        med = seg[len(seg) // 2]
        area = abs(_poly_area(bnd))
        closed = gap <= 3 * med + 1e-9 and area > 0.01
        add("boundary_closed", {"gap_m": _r(gap, 4), "median_segment_m": _r(med, 4), "area_m2": _r(area, 4)},
            "首尾间隙 ≤ 3 × 段长中位，面积 > 0.01 m²", closed,
            f"边界 {len(bnd)} 点，首尾间隙 {gap * 1e3:.1f} mm，截面积 {area:.3f} m²" if closed
            else f"边界不闭合或退化（{len(bnd)} 点，首尾间隙 {gap * 1e3:.1f} mm，截面积 {area:.3f} m²）")
    else:
        add("boundary_closed", len(bnd), "≥ 8 点", False, f"边界只有 {len(bnd)} 点")
    if limiter and limiter.get("r") and len(bnd) >= 8:
        lp = list(zip(limiter["r"], limiter["z"]))
        worst = 0.0
        for p in bnd:
            if not _inside(lp, p[0], p[1]):
                worst = max(worst, min(_seg_dist(p, lp[i], lp[(i + 1) % len(lp)]) for i in range(len(lp))))
        okl = worst <= B["limiter_tol_m"]
        add("boundary_in_limiter", _r(worst, 4), f"越出限制器 ≤ {B['limiter_tol_m']:g} m", okl,
            "边界全在限制器内" + (f"（最远贴出 {worst * 1e3:.1f} mm）" if worst > 0 else "") if okl
            else f"边界越出限制器 {worst * 1e3:.1f} mm：等离子体不能在真空室壁外")
    else:
        add("boundary_in_limiter", None, f"越出限制器 ≤ {B['limiter_tol_m']:g} m", None,
            "没有限制器（装置事实里缺）或边界退化：这条没核")
    ar, az = fa.get("axis_r"), fa.get("axis_z")
    oka = len(bnd) >= 8 and fin(ar) and fin(az) and _inside(bnd, ar, az)
    add("axis_inside", [ar, az], "磁轴在边界内", oka,
        f"磁轴 ({ar:.3f}, {az:+.3f}) m 在边界内" if oka else f"磁轴 ({ar}, {az}) 不在边界内")
    # ---- ψ 的次序：符号与电流方向 · 磁轴是极值
    oks = fin(pa) and fin(pb) and fin(ip) and (pb - pa) * ip < 0
    add("psi_sign", _r(pb - pa, 6) if fin(pa) and fin(pb) else None, "sign(ψ_bnd − ψ_axis) = −sign(I_p)（COCOS 17）", oks,
        (f"ψ 由磁轴 {pa:.4f} 降到边界 {pb:.4f} Wb，I_p > 0：与内核的 COCOS 17 一致" if oks else
         f"ψ_axis = {pa}、ψ_bnd = {pb}、I_p = {ip}：ψ 的走向与电流方向不合（COCOS 17 下 I_p > 0 时 ψ 由磁轴向外减）"))
    lo = hi = None
    if len(bnd) >= 8 and fin(pa) and fin(pb) and pa != pb and view.get("psi"):
        xs = [(pa - view["psi"][i][j]) / (pa - pb) for i, r in enumerate(grid["r"]) for j, z in enumerate(grid["z"])
              if _inside(bnd, r, z)]
        if xs:
            lo, hi = min(xs), max(xs)
    tol = B["psin_inside_tol"]
    oke = lo is not None and lo >= -tol and hi <= 1 + tol
    add("axis_extremum", None if lo is None else [lo, hi], f"LCFS 内 ψ_N ∈ [−{tol:g}, 1 + {tol:g}]", oke,
        (f"LCFS 内网格点 ψ_N ∈ [{lo:.3f}, {hi:.3f}]" if oke else
         "LCFS 内没有网格点" if lo is None else
         f"LCFS 内网格点 ψ_N ∈ [{lo:.3f}, {hi:.3f}]：" + ("有比磁轴更极端的点，磁轴不是 ψ 的极值" if lo < -tol
                                                        else "边界不是 ψ 的等值线")))
    # ---- I_p：同号、差在容差内
    sig = fa.get("ip_sigma")
    ipm = abs(float(ip_meas)) if fin(ip_meas) else None
    if fin(sig) and sig > 0:
        tol_ip, how = B["ip_sigma_mult"] * sig, f"≤ {B['ip_sigma_mult']:g} σ（σ = {sig:.4g} A，I_p 作带权测量）"
        ipm = abs(fa["ip_measured"]) if fin(fa.get("ip_measured")) else ipm
    else:
        tol_ip, how = (B["ip_rel_tol"] * ipm if ipm else None), f"≤ {B['ip_rel_tol'] * 100:g} % × |I_p 实测|"
    okip = fin(ip) and ipm is not None and ip > 0 and abs(ip - ipm) <= tol_ip
    add("ip_match", [ip, ipm], how, okip,
        (f"拟合 I_p {ip / 1e3:.1f} kA · 实测 {ipm / 1e3:.1f} kA（差 {(ip - ipm) / ipm * 100:+.2f} %"
         + (f"，{abs(ip - ipm) / sig:.2f} σ" if fin(sig) and sig > 0 else "") + "）" if okip else
         "没有实测 I_p 或拟合 I_p" if not (fin(ip) and ipm) else
         f"拟合 I_p {ip / 1e3:.1f} kA 与实测 |I_p| {ipm / 1e3:.1f} kA " + ("异号" if ip <= 0 else f"差 {(ip - ipm) / ipm * 100:+.2f} %，超容差")))
    # ---- χ²/dof（统计）
    c2 = fa.get("chi2_per_dof")
    okc = fin(c2) and c2 <= B["chi2_dof_max"]
    add("chi2_dof", c2, f"≤ {B['chi2_dof_max']:g}", okc,
        (f"χ²/dof = {c2:.3f}（统计校验）" if okc else f"χ²/dof = {c2} > {B['chi2_dof_max']:g}：统计上拟合不成立（不是物理判据）"),
        kind="statistical")
    if base is not None:
        name, st = base
        add("base_tier", st, f"档 {name} 物理", st != "unphysical",
            f"叠在档 {name} 上，档 {name} 过了" if st != "unphysical"
            else f"叠在档 {name} 上，档 {name} 物理校验没过：设定点与 ψ_N 映射都取自它")
    failed = [c["id"] for c in checks if c["pass"] is False]
    out = {"passed": not failed, "failed": failed, "checks": checks}
    if it is not None:
        out["same_ruler"] = {k: it[k] for k in ("w_mhd_J", "betap", "li1", "li3", "volume_m3", "ip_ampere_A", "r_geo_m")}
    return out


def apply_physics_check(out: dict, bounds: dict, select: bool) -> None:
    """``reconstruct`` 的结果（就地）：每个 status == ok 的档过 ``physics_check``；没过的改记 unphysical。
    顶层另写 ``physics_check``：{enabled, select, bounds（值 + 理由）, tiers: {档: status}, note}。次序 M → K → P，
    K / P 叠在哪一档上，那一档的状态（此刻已定）传进去。"""
    ipm = (out.get("inputs") or {}).get("ip")
    lim = (out.get("device") or {}).get("limiter")
    summary = {}
    for name in ("M", "K", "P", "X"):
        t = out["tiers"].get(name)
        if not t or t.get("status") != "ok":
            if t:
                summary[name] = t.get("status")
            continue
        on = "M" if name == "K" else (t.get("on") or "M") if name in ("P", "X") else None
        base = (on, (out["tiers"].get(on) or {}).get("status")) if on else None
        pc = physics_check(t, ip_meas=ipm, limiter=lim, bounds=bounds, base=base)
        t["physics_check"] = pc
        if not pc["passed"]:
            t["status"] = "unphysical"
            bad = [c for c in pc["checks"] if c["pass"] is False]
            log(f"{name}: ★★ UNPHYSICAL — " + "；".join(c["why"] for c in bad)
                + " — the numbers are kept but this tier is NOT a valid equilibrium")
        summary[name] = t["status"]
    out["physics_check"] = {"enabled": True, "select": bool(select), "bounds": bounds, "tiers": summary, "note": PHYS_NOTE}


class PhysSelect:
    """``--physics-select``：档 M 扫描里，收敛的设定点要过物理校验才能当选（χ² 最小者之中）。
    懒求值——只在一个候选的 χ² 比当前最好的还小时才核它（核一次 ≈ 1.5 s：同尺积分是纯 Python）。
    ``any`` 记这一轮收敛者中 χ² 最小的（不论物理与否），给「一个都不过」时的退路。
    ★只看 kind == physical 的条目：χ²/dof 是统计校验，剔道的前几轮坏道还在、χ² 本来就大——拿它挑设定点是循环论证
    （实测 #63948 · #137985 第 0 轮每个收敛点都因 χ²/dof 不过）。"""

    def __init__(self, c: "Case", bounds: dict):
        self.ipm, self.bounds = _r(c.meas["plasma"]), bounds
        self.any, self.evaluated, self.rejected, self.fallback = None, 0, 0, False

    def seen(self, cand) -> None:
        if self.any is None or cand[0] < self.any[0]:
            self.any = cand

    def ok(self, cand, entry: dict) -> bool:
        _, zc, fa, fi, _ = cand
        lim = {"r": _r(fi["limiter_r"], 5), "z": _r(fi["limiter_z"], 5)} if fi.get("limiter_r") else None
        pc = physics_check(tier_view(fa, fi, zc), ip_meas=self.ipm, limiter=lim, bounds=self.bounds)
        self.evaluated += 1
        bad = [c["id"] for c in pc["checks"] if c["pass"] is False and c["kind"] == "physical"]
        entry["physics"] = not bad
        if bad:
            self.rejected += 1
            entry["physics_failed"] = bad
        return not bad


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

    def __init__(self, lib: Lib, meas: dict, card: dict, loops: str, fvac: float | None = None):
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
        if fvac:                                         #: 调用方声明的真空 F（run --fvac）：压过测量文档里的
            self.b_tor, self.bt_from = abs(float(fvac)) / r0, f"声明的真空 F = {abs(float(fvac)):g} T·m（run --fvac）"
        elif "f_vac_Tm" in tf:
            self.b_tor, self.bt_from = abs(float(tf["f_vac_Tm"])) / r0, f"TF 线圈电流 {tf.get('node', '')}（F = μ₀NI/2π）"
        elif "btor" not in meas:
            raise SystemExit("测量文档里没有 TF 电流（旧炮的 east 树可能没有 TF 节点），也没有 btor——"
                             "用 run --fvac 声明真空 F = R·B_T [T·m]")
        else:
            self.b_tor, self.bt_from = abs(float(meas["btor"])), "归约件的 btor（B_T 节点，#97286 起单位存疑）"
        _, share, _ = lib.door("code/coilshare", {"nu_loops": 8, "nu_probes": 3, "grid_psi": 1, "nu_grid": 4},
                               {"device": card, "discharge": {"fylite:channel_aturns": self.brsp}})
        self.loop_coil, self.probe_coil, self.psi_ext = share["loop_coil"], share["probe_coil"], share["psi_ext"]
        #: 选道：探针 = 归约器判在用 − 名字重复的后几处槽。
        #: ★同名的槽树里只有一个节点，按名取数读到的是**第一处**那一道：EAST 新命名代的 HBPL1T–5T 在注册表里既是
        #: BP.H 组的槽 16–20、又是 BP.HBPLT 限制器组的槽 74–78，装置绑定（fydoc ``magnetics_east_new``）只把节点绑在
        #: 槽 16–20、槽 74–78 不带取值式。所以第一处照用，后几处（读的不是它们自己）不用。自检（#137985 4.0–4.3 s 档 M）：
        #: 用第一处的几何 χ²/dof 1.07 / 1.15 / 1.00，用第二处 1.25 / 1.28 / 1.15。2026-09-22 之前两处都不用——外侧上半的
        #: 五道探针白白丢掉。
        self.excluded = []
        fwt = [float(v) for v in meas["fwtmp2"]]
        seen: dict = {}
        for i, nm in enumerate(self.probe_names):
            seen.setdefault(nm, []).append(i)
        for nm, idx in seen.items():
            if nm and len(idx) > 1:
                for i in idx[1:]:
                    if fwt[i] > 0:
                        self.excluded.append({"kind": "probe", "index": i, "name": nm,
                                              "why": f"名字重复：树里只有一个节点，读的是槽 {idx[0]}（本槽无可区分节点）"})
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
        #: k-file 的 FWTSI = 0（kfile 命令写进 ``fwtsi``）：这个环对方没用，我们也不用、也不回收
        self.loop_off = {i for i, w in enumerate(meas.get("fwtsi") or []) if not float(w) > 0}
        for i in sorted(self.loop_off):
            if i < len(self.loop_start):
                self.loop_start[i] = 0.0
                self.excluded.append({"kind": "loop", "index": i, "name": self.loop_names[i], "why": "k-file FWTSI = 0"})
        self.loop_sigma = [max(SERROR * abs(v), LOOP_FLOOR) for v in self.coils]
        self.probe_sigma = [max(SERROR * abs(v), PROBE_FLOOR) for v in self.probes]
        self.probe_fwt = fwt
        self.loop_conf = [1.0] * len(self.coils)
        self.probe_conf = [1.0] * len(self.probes)
        self.lw = [s / sg for s, sg in zip(self.loop_start, self.loop_sigma)]
        self.pw = [f / sg if f > 0 else 0.0 for f, sg in zip(fwt, self.probe_sigma)]

    def apply_confidence(self, loops: dict | None, probes: dict | None) -> list:
        """逐道置信度 c（输入文件 ``magnetics.loops`` / ``probes``，键 = 道名或槽号）：σ_eff = σ / c，c = 0 即关掉这道
        （同 k-file 的 FWT = 0）；没写的道 c = 1。返回认不出的键（写错的道名不静默地不起作用）。"""
        unknown = []
        for which, table, names in (("loop", loops, self.loop_names), ("probe", probes, self.probe_names)):
            conf = self.loop_conf if which == "loop" else self.probe_conf
            for key, v in (table or {}).items():
                idx = [int(key)] if str(key).isdigit() else [i for i, n in enumerate(names) if n == key]
                idx = [i for i in idx if 0 <= i < len(names)]
                if not idx:
                    unknown.append(f"{which}:{key}")
                for i in idx:
                    conf[i] = max(float(v), 0.0)
        for i, cf in enumerate(self.loop_conf):
            if cf == 1.0:
                continue
            if cf <= 0.0:
                self.loop_off.add(i)
                self.loop_start[i] = 0.0
                self.excluded.append({"kind": "loop", "index": i, "name": self.loop_names[i], "why": "置信度 0（输入文件）"})
            else:
                self.loop_sigma[i] /= cf
        for i, cf in enumerate(self.probe_conf):
            if cf == 1.0:
                continue
            if cf <= 0.0:
                if self.probe_fwt[i] > 0:
                    self.excluded.append({"kind": "probe", "index": i, "name": self.probe_names[i], "why": "置信度 0（输入文件）"})
                self.probe_fwt[i] = 0.0
            else:
                self.probe_sigma[i] /= cf
        self.lw = [s / sg for s, sg in zip(self.loop_start, self.loop_sigma)]
        self.pw = [f / sg if f > 0 else 0.0 for f, sg in zip(self.probe_fwt, self.probe_sigma)]
        return unknown

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
           readmit: bool, scan: dict | None = None, sel: "PhysSelect | None" = None) -> tuple[dict, tuple | None]:
    """档 M：扫描 + 剔道几轮；``readmit`` 时把起步组之外、在收敛解上残差不超阈值的环收回来，再扫几轮。
    ``scan``：竖直设定点扫描的做法（``SCAN_FULL`` 缺省 / ``SCAN_COARSE``，见其注释）。"""
    scan = dict(SCAN_COARSE, **scan) if (scan or {}).get("mode") == "coarse" else dict(SCAN_FULL)
    rounds, rejected, readmitted = [], [], []
    best = _m_rounds(c, reject_sigma, max_rounds, per_round, settings, rounds, rejected, 0, scan, sel)
    if best is not None and readmit:
        _, _, _, fi, _ = best
        rl, _ = c.residuals(fi, all_channels=True)
        gone = {r["index"] for r in rejected if r["kind"] == "loop"}
        for i in range(len(c.coils)):
            if (c.lw[i] == 0 and c.loop_start[i] == 0 and i not in gone and i not in c.loop_off
                    and abs(rl[i]) <= reject_sigma):
                c.lw[i] = 1.0 / c.loop_sigma[i]
                readmitted.append({"kind": "loop", "index": i, "name": c.loop_names[i], "sigma": _r(rl[i], 3)})
        if readmitted:
            log(f"M readmit: {len(readmitted)} loop(s) predicted within {reject_sigma:g} sigma")
            fb0 = sel is not None and sel.fallback
            again = _m_rounds(c, reject_sigma, max_rounds, per_round, settings, rounds, rejected, len(rounds), scan, sel)
            if sel is not None and sel.fallback and not fb0:   #: 回收之后只剩不物理的解：与解不出同样退回
                again, sel.fallback = None, False
                log("M readmit: every converged set point after readmission is unphysical (--physics-select): reverted")
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
    if sel is not None:
        summary["physics_select"] = {"evaluated": sel.evaluated, "rejected": sel.rejected, "fallback": sel.fallback}
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


def _fine_scan(c: Case, settings: dict, zcs: list, scan: list, best, sel: "PhysSelect | None" = None):
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
        if fa["converged"]:
            cand = (chi2, zc, fa, fi, notes)
            if sel is not None:
                sel.seen(cand)
            if (best is None or chi2 < best[0]) and (sel is None or sel.ok(cand, scan[-1])):
                best = cand
    return best


def _coarse_scan(c: Case, settings: dict, how: dict, sel: "PhysSelect | None" = None):
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
        return coarse, fine, True, _fine_scan(c, settings, ZC_SCAN, fine, None, sel)
    top = [zc for _, zc in sorted(ranked)[: max(1, int(how["top"]))]]
    best = _fine_scan(c, settings, top, fine, None, sel)
    if best is None:                                     #: 粗排的前几名在 65² 上都不收敛（或都没过物理校验）：这一轮照全扫
        return coarse, fine, True, _fine_scan(c, settings, [zc for zc in ZC_SCAN if zc not in top], fine, None, sel)
    while True:                                          #: 65² 上从最好的点往两侧邻点走，直到两侧都不更好
        k, tried = ZC_SCAN.index(best[1]), {x["zc"] for x in fine}
        nxt = [ZC_SCAN[j] for j in (k - 1, k + 1) if 0 <= j < len(ZC_SCAN) and ZC_SCAN[j] not in tried]
        if not nxt:
            break
        was = best[1]
        best = _fine_scan(c, settings, nxt, fine, best, sel)
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


def _m_rounds(c: Case, reject_sigma, max_rounds, per_round, settings, rounds, rejected, rnd0, scan_opts=None,
              sel: "PhysSelect | None" = None):
    """One run of scan + reject rounds.  Returns the last round that converged; if a round after a
    rejection converges nothing, that rejection is undone (so the mask and the answer always agree).
    With ``sel`` (``--physics-select``) a candidate that fails the physics check counts as not converged:
    a round after a rejection whose every converged candidate is unphysical is undone the same way; only
    when the very first round has no physical candidate does it fall back to the smallest χ² (noted)."""
    how = dict(SCAN_COARSE, **(scan_opts or SCAN_FULL))
    #: 设定点少（热启动的 5 点扫）时粗排省不下什么：照全扫
    coarse_mode = how["mode"] == "coarse" and len(ZC_SCAN) > 2 * how["top"]
    last_good, last_batch = None, []
    for rnd in range(rnd0, rnd0 + max_rounds):
        scan, extra = [], {}
        if sel is not None:
            sel.any = None
        if coarse_mode:                                  #: ``scan`` 记 65² 的读数（页面按它数收敛），粗网格读数另记
            coarse, scan, fallback, best = _coarse_scan(c, settings, how, sel)
            extra = {"strategy": "coarse", "coarse": coarse, "fallback": fallback,
                     "coarse_converged": sum(1 for s in coarse if s.get("converged"))}
        else:
            best = _fine_scan(c, settings, ZC_SCAN, scan, None, sel)
            if how["mode"] == "coarse":
                extra = {"strategy": "full", "why": f"only {len(ZC_SCAN)} set points"}
        n_used = sum(1 for v in c.lw if v > 0) + sum(1 for v in c.pw if v > 0)
        if sel is not None:
            extra["physics_rejected"] = sum(1 for s in scan if s.get("physics") is False)
            if best is None and sel.any is not None:
                if last_good is None:                    #: 第一轮就一个都不过：退回 χ² 最小者（这一档会记 unphysical）
                    best, sel.fallback = sel.any, True
                    extra["physics_select"] = "fallback: no converged set point passes the physics check; smallest chi2 kept"
                    log(f"M round {rnd}: ★ --physics-select: no converged set point passes the physics check — "
                        "falling back to the smallest chi2 (this tier will be marked unphysical)")
                else:                                    #: 剔道之后收敛的全不物理：与「全不收敛」同样撤回这一批
                    extra["physics_select"] = "every converged set point unphysical: this round's rejections undone"
                    log(f"M round {rnd}: --physics-select: every converged set point is unphysical — "
                        f"undoing the {len(last_batch)} rejection(s) of the previous round and keeping its solution")
        if best is None:
            rounds.append({"round": rnd, "scan": scan, "converged": sum(1 for s in scan if s.get("converged")),
                           "n_used": n_used, **extra})
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
    #: ★节点在、读数近零（#52340 实测 2026-09-22：五弦线密度 ~4e16 m⁻²，是噪声不是等离子体）：不拿噪声当约束
    live = [abs(v) for v, w in zip(nel, fwtnel) if w > 0]
    if not live or max(live) < POINT_NEL_MIN:
        return {"status": "skipped", "why": f"POINT 线密度读数近零（最大 {max(live or [0.0]):.3g}e19 m⁻² < {POINT_NEL_MIN}e19）："
                                             "这一炮的 POINT 节点没有等离子体信号"}, None, None
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
                          ne_range=(1e18, 2e21), sigma_cap=2.0, zeff_dilution=1.0, conf: list | None = None) -> dict:
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
    #: 逐道置信度（输入文件 ``pressure.thomson``，按 Thomson 原始道序）：c = 0 关掉这道，其余 σ_eff = σ / c
    cf = [1.0] * n if conf is None else [max(float(conf[k]), 0.0) if k < len(conf) else 1.0 for k in range(n)]
    n_off = sum(1 for k in range(n) if ok[k] and cf[k] <= 0.0)
    idx = [k for k in range(n) if ok[k] and cf[k] > 0.0]
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
    sig = [sg / cf[k] for k, sg in zip(idx, sig)]
    return {"r": [r[k] for k in idx], "z": [z[k] for k in idx], "pressr": p, "sigpre": sig,
            "te": [te[k] for k in idx], "ne": [ne[k] for k in idx],
            "sigma_source": source, "n_points": len(idx), "n_dropped": n - len(idx) - n_off, "n_off": n_off,
            "index": idx, "conf": [cf[k] for k in idx],
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


#: 档 P 局部清洗对 ``wei_profiles.CLEAN_DEFAULTS`` 的覆盖。★``mirror`` 关：对 ρ = 0 的偶延拓预设磁轴定得准，而档 P 的
#: 测点是挂在**档 M**（纯磁测量）的平衡上的，磁轴可偏数厘米，轴两侧的测点折到 ρ 上会交错；#63948 5.022 s 实测：
#: 延拓开着时轴端参照塌到 2.1 keV（数据 4.1–4.6 keV），夹在中间的坏道（0.15 keV）因此不过尺度判据、留了下来。
P_CLEAN_OPTS = {"mirror": False}
CLEAN_MAX_FRAC = 0.3        #: 清洗剔掉的点超过候选点的这个份额 → 清洗可疑
CLEAN_CORE_PSIN = 0.5       #: 「芯部」= ψ_N 小于它
CLEAN_CORE_RUN = 3          #: 芯部连续（按 ψ_N 相邻）剔掉这么多个点 → 清洗可疑


def clean_local(x, te, ne, cand, opts: dict | None = None):
    """``wei_profiles.clean_profile``（Wei 2026 §II.B 的局部 MAD 清洗，与 ``wei2026.py`` 同一份代码）**分别**作用在
    T_e(ρ) 与 n_e(ρ) 上，ρ = √ψ_N；任一剖面判为离群的道整道不用。

    ★为什么不在 p 上做：坏道是**一个量**坏（TS 常见的是 T_e 拟谱失败、n_e 正常，或反过来），在那个量上它是孤立的、
    幅度大的离群；乘成 p 之后两个量的涨落叠在一起、局部尺度变粗，峰化剖面上 p ∝ n_e·T_e 的梯度又比单个量陡，
    「低于邻点连线的一半」这条趋势判据更容易被真梯度触发。文献也是逐量清洗。
    返回 (keep, dropped, params)；``dropped`` 每条记 index · 哪个量 · 哪一侧 · 局部标度分。
    """
    try:                                                 #: 伴随模块（同目录、同样只用标准库）；smooth 档不需要它
        import wei_profiles as W
    except ImportError:
        sys.path.insert(0, str(HERE))
        try:
            import wei_profiles as W
        except ImportError as e:
            raise RuntimeError("--thomson-clean local 要同目录的 wei_profiles.py（与本文件一起发行）；"
                               "没有它就用 --thomson-clean smooth") from e
    o = dict(P_CLEAN_OPTS, **(opts or {}))
    order = sorted((i for i, ok in enumerate(cand) if ok), key=lambda i: x[i])
    keep = list(cand)
    dropped = []
    if len(order) >= 5:
        xs = [math.sqrt(max(x[i], 0.0)) for i in order]
        for k in range(1, len(xs)):                      #: clean_profile 要严格递增；重合的横坐标错开一个可忽略的量
            if xs[k] <= xs[k - 1]:
                xs[k] = xs[k - 1] + 1e-9
        for name, y in (("T_e", te), ("n_e", ne)):
            res = W.clean_profile(xs, [y[i] for i in order], o)
            for k, score, side in res["removed"]:
                keep[order[k]] = False
                dropped.append({"index": order[k], "quantity": name, "side": side, "score": _r(score, 3)})
            if len(res["removed"]) >= max(1, math.ceil(res["params"]["max_frac"] * len(xs))):
                dropped.append({"index": None, "quantity": name, "hit_cap": True})
    return keep, dropped, dict(W.CLEAN_DEFAULTS, **o)


def cleaning_verdict(x, cand, keep) -> dict:
    """清洗自检：剔得太多、或把芯部连着剔掉一串，首先是**清洗错了**的征兆（其次才是这一脉冲整个不可用）
    （#63948 5.022 s 实测：全局光滑拟合把 7 个真实的芯部点当离群剔光，档 P 储能 13.8 kJ 对实测 W_dia 68 kJ）。"""
    order = sorted((i for i, ok in enumerate(cand) if ok), key=lambda i: x[i])
    n, n_rej = len(order), sum(1 for i in order if not keep[i])
    run = best = 0
    for i in order:
        run = run + 1 if (not keep[i] and x[i] < CLEAN_CORE_PSIN) else 0
        best = max(best, run)
    reasons = []
    if n and n_rej / n > CLEAN_MAX_FRAC:
        reasons.append(f"剔掉 {n_rej} / {n} 个候选点（{n_rej / n:.0%} > {CLEAN_MAX_FRAC:.0%}）")
    if best >= CLEAN_CORE_RUN:
        reasons.append(f"芯部（ψ_N < {CLEAN_CORE_PSIN}）连续剔掉 {best} 个相邻点（≥ {CLEAN_CORE_RUN}）")
    return {"n_candidates": n, "n_rejected": n_rej, "rejected_fraction": _r(n_rej / n, 4) if n else None,
            "longest_core_run": best, "max_fraction": CLEAN_MAX_FRAC, "core_psin": CLEAN_CORE_PSIN,
            "core_run_limit": CLEAN_CORE_RUN, "suspect": bool(reasons), "reasons": reasons}


def _p_solve(c: Case, st: dict, disc0: dict, rows: dict, scales: list):
    """档 P 的 σ 续延：依次按 ``scales`` 放宽压强行的 σ 进反演，取第一个不被拒的。返回 (fa, fi, notes, attempts)，
    全被拒时 fa 为 None。"""
    attempts = []
    for scale in scales:
        rows_s = dict(rows, **{"fylite:pressure_weight": [w / scale for w in rows["fylite:pressure_weight"]]})
        try:
            fa, fi, notes = c.lib.door("code/reconstruction", st, {"device": c.card, "discharge": dict(disc0, **rows_s)})
            attempts.append({"sigma_scale": scale, "ok": True})
            return fa, fi, notes, attempts
        except (Refused, KernelError) as e:              # 拒绝也是读数
            attempts.append({"sigma_scale": scale, "ok": False, "error": str(e)[-40:]})
    return None, None, None, attempts


def _p_base_disc(c: Case, base, kin) -> dict:
    """档 P 叠在 M 上（全测量档）还是叠在 K 上（行给定档 + POINT 法拉第行）。"""
    if kin is None:
        return c.full_disc()
    fa_k, fi_k, _ = base
    _, fi2 = chords(c, fa_k, fi_k, kin["nel"], kin["fwtnel"])
    return dict(c.rows_disc(), **faraday_extra(fi2, kin["bp"], kin["fwtpol"]))


def tier_p_psin(c: Case, base, kin, kp: dict, a, settings: dict, extra: dict | None = None,
                hold: dict | None = None) -> dict:
    """档 P 的另一种输入：压强已经给在 ψ_N 上（k-file 的 RPRESS < 0 · PRESSR · SIGPRE，EFIT 的约定）。行钉在 ψ_N 上、
    没有 (R, Z) 可重映，所以外环只一遍——这正是 EFIT 对 RPRESS < 0 的做法。σ 取 k-file 的 SIGPRE（续延同 Thomson 路）。
    ★k-file 的压强是**总**压强（ONETWO：热 + 快离子），原样进行，不扣快离子（``--p-fast-frac`` 在这条路上不用）。"""
    fa_b, fi_b, zc = base
    x, pres, sig = kp["psin"], kp["pressr"], kp["sigpre"]
    fw = kp.get("fwtpre") or [1.0] * len(x)
    ex = extra or {}
    if ex.get("conf") is not None:                       #: 逐行置信度：σ_eff = σ / c，c = 0 关掉
        cf = [max(float(v), 0.0) for v in ex["conf"]] + [1.0] * len(x)
        fw = [f * (1.0 if cf[i] > 0 else 0.0) for i, f in enumerate(fw)]
        sig = [sg / cf[i] if cf[i] > 0 else sg for i, sg in enumerate(sig)]
    use = [i for i in range(len(x)) if fw[i] > 0 and sig[i] > 0 and 0.0 <= x[i] < a.psin_max]
    if len(use) < 3:
        return {"status": "error", "error": f"k-file 压强只有 {len(use)} 行可用"}
    rows = {"fylite:pressure": [pres[i] for i in use], "fylite:pressure_x": [x[i] for i in use],
            "fylite:pressure_weight": [1.0 / sig[i] for i in use]}
    st = dict(settings, zc_anchor=zc, kinetic_passes=1, kinetic_tol=a.kinetic_tol, curv_p=a.curv, curv_f=a.curv)
    disc0 = _p_base_disc(c, base, kin)
    efit = None
    if "P" in efit_mode(a, c.meas):
        e_st, e_disc, efit = efit_request(c.meas["efit_fit"], efit_parts(a), a.efit_override)
        st.update(e_st)
        disc0 = dict(disc0, **e_disc)
        if a.nk:                                         #: I_p 作测量之后纯 Picard 在一格掩膜上来回（实测），JFNK 收得住
            st["newton_krylov"] = int(a.nk)
    st.update(ex.get("st") or {})
    disc0 = dict(disc0, **(ex.get("disc") or {}))
    fa, fi, notes, attempts = _p_solve(c, st, disc0, rows, a.sigma_scales)
    if hold is not None and fa is not None:
        hold.update(fa=fa, fi=fi, st=st, disc=dict(disc0, **rows))
    if efit and fa is not None and "pprime_basis" not in fa:
        #: ★2026-09-22 之前的内核不认这些键、也不报错——读数就是没有这些约束的解，说出来而不是冒充
        efit["ignored"] = True
        log("this libfylite.so ignores the k-file fit settings (kernel without feat/recon-spline-constraints): "
            "tier P ran without them")
    if fa is None:
        return {"status": "error", "error": "每一档 sigma 放宽都被拒", "attempts": attempts}
    scale = attempts[-1]["sigma_scale"]
    pts = []
    for i in range(len(x)):
        mv = interp(min(max(x[i], 0.0), 1.0), fi["psin_1d"], fi["pres"])
        used = i in use
        pts.append({"r": None, "z": None, "p": _r(pres[i], 5), "sigma": _r(sig[i], 4), "psin_initial": _r(x[i], 4),
                    "psin_final": _r(x[i], 4), "model_p": _r(mv, 5), "used": used,
                    "resid_sigma": _r((mv - pres[i]) / sig[i], 4) if used else None,
                    "resid_sigma_entered": _r((mv - pres[i]) / (sig[i] * scale), 4) if used else None,
                    "why": "" if used else (f"psi_N ≥ {a.psin_max}（不收）" if x[i] >= a.psin_max
                                            else "k-file FWTPRE = 0 / σ ≤ 0")})
    stacked = kin is not None
    log(f"P (psi_N rows): q0 {fa['q0']:.3f}, {len(use)} rows at sigma x {scale:g}, chi2_kin {fa.get('chi2_kin', float('nan')):.2f}")
    return tier_view(fa, fi, zc, {
        "label": "P · 磁" + (" + POINT" if stacked else "") + " + ψ_N 上给定的压强（k-file）",
        "constraints": ["磁（同 M）"] + (["POINT 法拉第行（同 K）"] if stacked else [])
                       + [f"ψ_N 上给定的压强行 × {len(use)}（k-file SIGPRE；总压强，不扣快离子）"]
                       + ([f"曲率正则 λ = {a.curv:g}"] if a.curv > 0 else [])
                       + (efit_constraints(efit) if efit else []) + list(ex.get("constraints") or []),
        "channels": c.channel_table(fi), "notes": list(notes or []),
        "certificate": {"chi2_per_dof": _r(fi.get("kinetic_pass_chi2_per_dof") or [], 5),
                        "map_shift": _r(fi.get("kinetic_pass_map_shift") or [], 4),
                        "best_pass": int(fa.get("kinetic_best_pass", 1)), "tol": a.kinetic_tol,
                        "rows_on": "psi_N (not remapped)"},
        "sigma_scale": scale, "attempts": attempts, "on": "K" if stacked else "M",
        "passes_note": "行钉在 ψ_N 上：没有 (R, Z) 可重映，只跑一遍",
        "pressure_rows": {"source": kp.get("source"), "note": kp.get("note"), "points": pts},
        **({"efit_fit": efit, "jzero_residual": _r(fi.get("jzero_residual") or [], 5),
            "lincon_residual": _r(fi.get("lincon_residual") or [], 6)} if efit else {}),
        #: 页面按 thomson.points 画压强点：同一份点，r / z 为空（剖面图照画，截面图上没有位置）
        "thomson": {"points": pts, "sample_time_s": None, "ti0": None, "te0": None, "ion_factor": None,
                    "n_dropped_quality": 0, "sigma_source": "k-file SIGPRE",
                    "assumptions": {"source": kp.get("source"), "rows": "psi_N, total pressure (ONETWO)"},
                    "psin_max": a.psin_max}})


def efit_mode(a, meas: dict) -> str:
    """``--efit-fit`` 解析成档名串：``auto`` = 测量文档带 ``efit_fit``（kfile 读出的）时 ``P``，否则不用。"""
    m = getattr(a, "efit_fit", "auto") or "auto"
    if m == "auto":
        return "P" if meas.get("efit_fit") else ""
    if m == "off":
        return ""
    if not meas.get("efit_fit"):
        raise SystemExit(f"--efit-fit {m}：测量文档里没有 efit_fit 块（只有 kfile 读出的测量文档带它）")
    return m


def efit_parts(a) -> set:
    parts = {x for x in (getattr(a, "efit_parts", None) or ",".join(EFIT_PARTS)).split(",") if x}
    bad = parts - set(EFIT_PARTS)
    if bad:
        raise SystemExit(f"--efit-parts：不认识 {sorted(bad)}（可用 {','.join(EFIT_PARTS)}）")
    return parts


def efit_constraints(rec: dict) -> list:
    out = []
    for which in ("pprime", "ffprime"):
        b = rec.get(which)
        if b:
            out.append(f"{which}：" + (f"张力样条 结点 {b['knots']} τ {b.get('tension', 0):g}（{rec.get('tension_scale')}）"
                                       if b["basis"] == "spline" else f"{b['basis']} × {b['n']}"))
    if rec.get("q0"):
        out.append(f"磁轴 q = {rec['q0']['target']:g}（权 {rec['q0']['weight']:g}）")
    if rec.get("j"):
        out.append(f"电流密度行 × {rec['j']['fsa_rows'] + rec['j']['local_rows']}（权 {rec['j']['weight']:g}）")
    if rec.get("lincon"):
        out.append("样条结点参数线性约束：" + "、".join(rec["lincon"]))
    if rec.get("ip_sigma"):
        out.append(f"I_p 作测量（σ {rec['ip_sigma']:.4g} A）")
    return out


def tier_p(c: Case, base, kin, th: dict, a, settings: dict, extra: dict | None = None,
           hold: dict | None = None) -> dict:
    """档 P：Thomson 压强点（R, Z，逐点实测 sigma）作动理学行，自洽外环逐遍重映 psi_N。
    ``extra``（输入文件的档 X 用）：``st`` / ``disc`` 并进内核设定与 discharge 行，``conf`` 是逐道置信度，
    ``constraints`` 追加到约束清单；``hold`` 收下解 (fa, fi)。"""
    fa_b, fi_b, zc = base
    ex = extra or {}
    p = pressure_from_thomson(th, sigma_floor=a.sigma_floor, conf=ex.get("conf"))
    r, z, pres, sig = p["r"], p["z"], p["pressr"], p["sigpre"]
    gr, gz = fi_b["grid_r"], fi_b["grid_z"]
    x0 = [psin_at(fa_b, fi_b, ri, zi) if (gr[0] <= ri <= gr[-1] and gz[0] <= zi <= gz[-1]) else float("nan")
          for ri, zi in zip(r, z)]
    inside = [fin(v) and 0.0 <= v < a.psin_max for v in x0]
    xs0 = [v if ok else 0.0 for v, ok in zip(x0, inside)]
    why: dict = {}
    if a.thomson_clean == "smooth":                      #: 旧法（2026-09-20 之前的缺省）：留着，为了能复现过去的读数
        keep, clipped = clip_profile(c.lib, xs0, pres, sig, inside, a.thomson_clip)
        why = {d["index"]: f"离光滑拟合 {d['sigma']} σ（剔）" for d in clipped}
        cleaning = {"cleaner": "smooth", "method": "global smooth fit of p(psi_N) (code/profile_fit, GCV order), "
                    "worst point beyond the threshold removed one at a time", "clip_sigma": a.thomson_clip}
    else:
        keep, clipped, params = clean_local(xs0, p["te"], p["ne"], inside, a.thomson_clean_opts)
        for d in clipped:
            if d["index"] is not None:
                why[d["index"]] = (why.get(d["index"], "") + "；" if d["index"] in why else "") + \
                    f"{d['quantity']} 局部离群（{'低' if d['side'] == 'low' else '高'}侧，标度分 {d['score']}；剔）"
        cleaning = {"cleaner": "local", "method": "wei_profiles.clean_profile (Wei 2026 sec. II.B local-MAD, one point at a "
                    "time) on T_e(rho) and n_e(rho) separately, rho = sqrt(psi_N); a channel flagged in either is dropped",
                    "params": params}
    cleaning["rejected"] = clipped
    cleaning.update(cleaning_verdict(xs0, inside, keep))
    points = [{"r": _r(ri, 5), "z": _r(zi, 5), "p": _r(pi, 5), "sigma": _r(si, 4), "te": _r(tei, 5), "ne": _r(nei, 5),
               "psin_initial": _r(xi, 4), "channel": p["index"][i], "conf": p["conf"][i],
               "used": bool(k), "why": (why.get(i) or ("" if ins else f"psi_N ≥ {a.psin_max}（不收）"))}
              for i, (ri, zi, pi, si, tei, nei, xi, k, ins) in enumerate(zip(r, z, pres, sig, p["te"], p["ne"], x0, keep, inside))]
    if cleaning["n_rejected"]:
        log(f"P: {cleaning['cleaner']} cleaning rejected {cleaning['n_rejected']} of {cleaning['n_candidates']} Thomson point(s)")
    if cleaning["suspect"]:
        log("P: ★★ CLEANING SUSPECT — " + "；".join(cleaning["reasons"]) + " — either the cleaner is wrong or this pulse is unusable; this tier's reading is not trustworthy")
    use = [i for i, k in enumerate(keep) if k]
    if len(use) < 3:
        return {"status": "error", "error": f"只有 {len(use)} 个 Thomson 点落在 psi_N < {a.psin_max} 内", "points": points,
                "cleaning": cleaning}
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
    disc0 = _p_base_disc(c, base, kin)
    st.update(ex.get("st") or {})
    disc0 = dict(disc0, **(ex.get("disc") or {}))
    #: ★★sigma 续延（实测 2026-09-18）：把档 M 自己的压强剖面原样当动理学行喂回去，sigma 取峰值 5 % 时
    #: 内核仍把等离子体拟丢，20 % 时一步收敛——求解器对紧约束行的稳健性上限。先按实测 sigma 进，
    #: 拒了就整体放宽，放宽倍数写进结果。
    fa, fi, notes, attempts = _p_solve(c, st, disc0, rows, a.sigma_scales)
    if fa is None:
        return {"status": "error", "error": "每一档 sigma 放宽都被拒", "attempts": attempts, "points": points,
                "cleaning": cleaning}
    sigma_scale = attempts[-1]["sigma_scale"]
    if hold is not None:
        hold.update(fa=fa, fi=fi, st=st, disc=dict(disc0, **rows))
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
                       + ([f"曲率正则 λ = {a.curv:g}"] if a.curv > 0 else []) + list(ex.get("constraints") or []),
        "channels": c.channel_table(fi),
        "notes": list(notes or []) + (["★★Thomson 清洗可疑（" + cleaning["cleaner"] + "）：" + "；".join(cleaning["reasons"])
                                       + "——要么清洗错了，要么这一脉冲本身不可用；哪一种这一档的读数都不可信，"
                                         "不能读成「数据里恰好有这么多坏道」。逐点核对（thomson.points 的 te · ne · why）"] if cleaning["suspect"] else []),
        "certificate": {"chi2_per_dof": _r(fi.get("kinetic_pass_chi2_per_dof") or [], 5),
                        "map_shift": _r(fi.get("kinetic_pass_map_shift") or [], 4),
                        "best_pass": int(fa.get("kinetic_best_pass", 1)), "tol": a.kinetic_tol,
                        "cleaner": cleaning["cleaner"], "cleaning_suspect": cleaning["suspect"],
                        "cleaning_reasons": cleaning["reasons"],
                        "cleaning_rejected_fraction": cleaning["rejected_fraction"],
                        "cleaning_longest_core_run": cleaning["longest_core_run"]},
        "sigma_scale": sigma_scale, "attempts": attempts, "on": "K" if stacked else "M",
        "passes_note": ("叠在 K 上：外环在行给定档不重映，只跑一遍" if stacked else ""),
        "thomson": {"points": points, "sample_time_s": th.get("sample_time_s"), "ti0": th.get("ti0"),
                    "te0": p.get("te0"), "ion_factor": p.get("ion_factor"), "n_dropped_quality": p.get("n_dropped"),
                    "sigma_source": p.get("sigma_source"), "assumptions": p.get("assumptions"),
                    "psin_max": a.psin_max, "cleaning": cleaning}})


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


def run_options(**overrides) -> argparse.Namespace:
    """``run`` 的全部开关：取命令行的缺省，再按关键字覆盖。键 = 开关名去掉 ``--``、``-`` 换 ``_``
    （``reject_sigma=4``、``tiers="MK"``、``sigma_scales=[1, 2]``、``point_off=[4, 7]`` …）；值是**解析后**的类型。
    不认识的键抛 ``TypeError``——写错的开关不静默地不起作用。"""
    a = _parser().parse_args(["run", "-", "-o", "-"])
    for k, v in overrides.items():
        if k not in vars(a) or k in ("cmd", "lib", "input", "out", "time", "thomson"):
            raise TypeError(f"run_options: no such option {k!r} (see `kinetic_recon.py run --help`)")
        setattr(a, k, v)
    return a


def reconstruct(meas: dict, thomson: dict | None = None, *, lib: "Lib | None" = None, origin: dict | None = None,
                kinetic_input: dict | None = None, **options) -> dict:
    """``run`` 的进程内形：平坦测量字典（``pull_magnetics`` 的返回值 = 测量文档的 ``measurements`` 块）
    + 可选的 Thomson 块（``pull_thomson`` 的返回值）→ 结果字典（与 ``run -o`` 写出的 JSON 同一份，见 README §4.4）。
    ``options`` 同 :func:`run_options`；``lib`` 缺省载本文件旁的 ``libfylite.so``。
    档 M 一个设定点都不收敛时不抛：``tiers["M"]["status"] == "error"``（K / P 不跑）；K、P 的失败同样记在各自的 ``status`` 里。
    物理校验（缺省开，``physics_check=False`` 关）没过的档 ``status == "unphysical"``，数照留（README §3.9）。"""
    kin_in = kinetic_input
    if kin_in is not None:                               #: 输入文件（kinetic_input.py）：逐道置信度 · 档 X 代替档 P
        import kinetic_input as KI
        options = dict(options, efit_fit="off", psin_max=kin_in["pressure"]["psin_max"],
                       sigma_floor=kin_in["pressure"]["sigma_floor"], p_fast_frac=kin_in["pressure"]["fast_frac"],
                       tiers="MK" if kin_in["point"]["on"] else "M")
        meas = KI.apply_point(meas, kin_in)
    a = run_options(**options)
    lib = lib or Lib(DEFAULT_LIB)
    set_jobs(a.jobs)
    th = thomson
    origin = dict(origin or {"kind": "in-process"})
    shot, t = int(meas["shot"]), float(meas["time_s"])
    chain = meas.get("measurement_chain", "east")
    card, _ = lib.device("east", shot, chain)
    t0 = time.time()
    c = Case(lib, meas, card, a.loops, a.fvac)
    conf_unknown = c.apply_confidence(kin_in["magnetics"]["loops"], kin_in["magnetics"]["probes"]) if kin_in else []
    if conf_unknown:
        raise SystemExit(f"输入文件的逐道置信度里有认不出的道：{conf_unknown}")
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
                        "thomson_clean": a.thomson_clean, "thomson_clean_opts": a.thomson_clean_opts,
                        "sigma_scales": a.sigma_scales, "curv": a.curv, "p_fast_frac": a.p_fast_frac,
                        "psin_max": a.psin_max, "fvac": a.fvac, "serror": SERROR, "loop_floor": LOOP_FLOOR, "probe_floor": PROBE_FLOOR,
                        "sigpol": SIGPOL, "signel": SIGNEL},
           "inputs": {"ip": _r(meas["plasma"]), "b_tor": _r(c.b_tor), "b_tor_from": c.bt_from, "r0": card["tf"]["r0"],
                      "pf_aturns": _r(c.brsp), "n_loops": len(c.coils), "n_probes": len(c.probes),
                      "excluded": c.excluded, "has_point": bool((meas.get("point") or {}).get("bpolar")),
                      "has_thomson": th is not None, "has_kinetic_pressure": bool(meas.get("kinetic_pressure")),
                      **({"kfile": meas["kfile"], "point_source": meas.get("point_source")} if meas.get("kfile") else {})},
           "device": {"limiter": None,
                      "loops": [{"name": n, "rz": rz} for n, rz in zip(c.loop_names, c.loop_rz)],
                      "probes": [{"name": n, "rz": rz} for n, rz in zip(c.probe_names, c.probe_rz)],
                      "chords": [{"name": _name(ch), "los": ch.get("line_of_sight")} for ch in _aos(card.get("polarimeter"))]},
           "tiers": {}}
    tiers = set(a.tiers.upper())
    emode = efit_mode(a, meas)
    if emode:
        out["settings"]["efit_fit"] = {"on": emode, "parts": sorted(efit_parts(a)), "override": a.efit_override}
    ms = m_settings(settings, a.anderson, a.nk)
    m_efit = None
    if "M" in emode:
        e_st, e_disc, m_efit = efit_request(meas["efit_fit"], efit_parts(a), a.efit_override)
        if e_disc:
            raise SystemExit("--efit-fit M：档 M 的扫描不带 discharge 行——电流密度行（j）只在档 P 上用；给 --efit-parts 去掉 j")
        ms = dict(ms, **e_st)
    bounds = phys_bounds(a.phys_bounds) if (a.physics_check or a.physics_select) else None
    sel = PhysSelect(c, bounds) if a.physics_select else None
    m_view, base_m = tier_m(c, a.reject_sigma, a.max_rounds, a.per_round, ms,
                            a.loops == "B+readmit", scan_from_args(a), sel)
    if m_efit and m_view.get("status") == "ok":
        if "pprime_basis" not in (base_m[0] if base_m else {}):
            m_efit["ignored"] = True
            log("this libfylite.so ignores the k-file fit settings (kernel without feat/recon-spline-constraints): "
                "tier M ran without them")
        m_view["efit_fit"] = m_efit
        m_view["constraints"] = list(m_view.get("constraints") or []) + efit_constraints(m_efit)
    close_jobs()                                         #: 并行只用在档 M 的扫描上；K / P 照旧串行
    out["tiers"]["M"] = m_view
    if base_m is not None:
        out["device"]["limiter"] = {"r": _r(base_m[1]["limiter_r"], 5), "z": _r(base_m[1]["limiter_z"], 5)}
    base_k, kin = None, None
    if "K" in tiers and base_m is not None:
        k_view, base_k, kin = tier_k(c, base_m, a.point_off, a.dead_sigma, settings)
        out["tiers"]["K"] = k_view
    if kin_in is not None and base_m is not None:
        out["tiers"]["X"] = KI.tier_x(c, base_m, base_k, kin, th, a, settings, kin_in)
    elif "P" in tiers and base_m is not None:
        kp = meas.get("kinetic_pressure")
        if th is None and kp:                            #: ψ_N 上给定的压强（kfile 命令读的 k-file NPRESS 段）
            use_k = base_k is not None and a.p_on == "K"
            out["tiers"]["P"] = tier_p_psin(c, base_k if use_k else base_m, kin if use_k else None, kp, a, settings)
        elif th is None:
            out["tiers"]["P"] = {"status": "skipped", "why": "没有 Thomson（pull 时没取到，或没给 --thomson）"}
        else:
            use_k = base_k is not None and a.p_on == "K"
            out["tiers"]["P"] = tier_p(c, base_k if use_k else base_m, kin if use_k else None, th, a, settings)
    if a.physics_check:
        apply_physics_check(out, bounds, a.physics_select)
    out["seconds"] = round(time.time() - t0, 1)
    return out


def cmd_run(a) -> int:
    meas, th, origin = load_input(a.input, a.time, a.thomson)
    opts = {k: v for k, v in vars(a).items() if k not in ("cmd", "lib", "input", "out", "time", "thomson")}
    out = reconstruct(meas, th, lib=Lib(Path(a.lib) if a.lib else DEFAULT_LIB), origin=origin, **opts)
    m_view = out["tiers"]["M"]
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    log(f"-> {a.out} ({Path(a.out).stat().st_size / 1e3:.0f} kB, {out['seconds']} s)")
    st = m_view.get("status")
    return 0 if st == "ok" else 3 if st == "unphysical" else 1


# ================================================================================================ series
#: 时间序列对拍：一炮 [t0, t1] 内逐时刻的**档 M**（只磁测量）反演 ↔ 装置自己的平衡重建（离线 EFIT，另可 P-EFIT ·
#: 实时 EFIT）。★对方是参考库（二级数据库），不是诊断：只作比较，不进拟合。
#: ★取数一次：磁测量 · PF · Ip · TF 的整条序列各读一次（``MagneticsSource.prefetch``），在每个时刻上归约；参考树的
#: 时基 · 标量 · ψ · 边界 · q · p 各读一次（``EquilibriumSeries``），逐片切。
#: ★每片独立：不从上一片热启动——每一片与同一时刻单独跑 ``run --tiers M`` 的档 M 逐字节相同（README §6.4）。
#: 热启动（沿用上一片的 Z_c、剔道）会改答案（``wei2026.py profiles`` 的 ``--workers`` 即是），这里不做。

#: ``run`` 里只作用在档 M 上的开关：``series`` 收同一组，原样交给 ``reconstruct``
SERIES_M_OPTS = ("npp", "nff", "loops", "reject_sigma", "max_rounds", "per_round", "scan", "scan_grid", "scan_top",
                 "anderson", "nk", "fvac", "physics_check", "phys_bounds", "physics_select")
#: 汇总表的量：(键, 我们那一侧, 对方那一侧)。q0 · q95 · 磁轴取各自报的；l_i · β_p · W · V 两边都用同一把尺
SERIES_PAIRS = (("q0", ("ours", "q0"), ("scalars", "q0")), ("q95", ("ours", "q95"), ("scalars", "q95")),
                ("li1", ("ours", "li1"), ("same_ruler", "li1")), ("li3", ("ours", "li3"), ("same_ruler", "li3")),
                ("betap", ("ours", "betap"), ("same_ruler", "betap")),
                ("w_mhd_J", ("ours", "w_mhd_J"), ("same_ruler", "w_mhd_J")),
                ("volume_m3", ("ours", "volume_m3"), ("same_ruler", "volume_m3")),
                ("axis_r", ("ours", "axis_r"), ("scalars", "axis_r")), ("axis_z", ("ours", "axis_z"), ("scalars", "axis_z")),
                #: X 点平衡：ψ_N(上 X 点) − ψ_N(下 X 点)（|·| < XPT_DN_TOL 为双零；正 = 下单零、负 = 上单零）
                ("xpt_dpsin", ("ours", "xpt_dpsin"), ("xpoint", "dpsin")))
SERIES_DIST = (("axis_distance_m", ("axis_distance_m",)), ("boundary_mean_m", ("boundary_distance", "mean_m")),
               ("boundary_max_m", ("boundary_distance", "max_m")), ("psin_rms", ("psin_map_difference", "rms")),
               ("psin_max_abs", ("psin_map_difference", "max_abs")))


def strict_json(x):
    """写 JSON 前：非有限数一律 ``null``（严格 JSON，没有裸 NaN / Infinity），元组变列表。"""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: strict_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [strict_json(v) for v in x]
    return x


def _rt(x, n=6):
    """结构里的浮点数截到 n 位有效数字（``_r`` 的整棵树版）；整数、布尔、串原样。"""
    if isinstance(x, bool) or x is None or isinstance(x, (int, str)):
        return x
    if isinstance(x, float):
        return _r(x, n)
    if isinstance(x, dict):
        return {k: _rt(v, n) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_rt(v, n) for v in x]
    return x


def _dig(d, path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d if fin(d) else None


def series_slice(lib: Lib, t: float, meas: dict | None, w_dia, refs: dict, opts: dict, keep_psi: bool = False,
                 results_dir: str | None = None, kefit: dict | None = None) -> dict:
    """一个时刻：档 M 反演（``reconstruct(..., tiers="M")``，与 ``run --tiers M`` 同一条路）+ 与每个来源那一片的比较。
    ``refs`` = {来源: ``_eq_slice`` 的一片，或 {"error": 原因}}。失败照记（``status: error`` + ``why``），不抛。"""
    t_start = time.time()
    out: dict = {"time_s": t, "status": "error"}
    if meas is None:
        out.update(why=refs.pop("_meas_error", "没有这一时刻的测量"), refs=_ref_entries(refs, t, None),
                   seconds=round(time.time() - t_start, 2))
        return out
    out["measured"] = {"ip_A": abs(float(meas["plasma"])), "w_dia_J": w_dia}
    try:
        res = reconstruct(meas, None, lib=lib, origin={"kind": "series", "time_s": t}, tiers="M", **opts)
    except (Exception, SystemExit) as e:                 # noqa: BLE001 —— 一片出错是一片的读数
        out.update(why=sanitize(f"{type(e).__name__}: {e}")[-300:], refs=_ref_entries(refs, t, None),
                   seconds=round(time.time() - t_start, 2))
        return out
    if results_dir:
        p = Path(results_dir) / f"result_{res['shot']}_{t:.6f}.json"
        p.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    M = res["tiers"]["M"]
    out["measured"]["b_tor_T"] = res["inputs"]["b_tor"]
    out["_limiter"] = res["device"].get("limiter")
    if M.get("status") not in ("ok", "unphysical"):
        out.update(why=M.get("error") or "档 M 没有解", rounds=len(M.get("rounds") or []),
                   refs=_ref_entries(refs, t, None), seconds=round(time.time() - t_start, 2))
        return out
    if kefit:                                            #: 本机 KEFIT：同一片、同一组测量、档 M 最后的掩码（README §6.6）
        refs["kefit"], out["kefit_run"] = kefit_slice(lib, t, meas, res, kefit)
    o = our_integrals(res)["M"]
    fa, it = M["facts"], o["int"]
    rounds = M.get("rounds") or []
    out["status"] = M["status"]                          #: ok · unphysical（数照留，汇总不收）
    if M.get("physics_check"):
        out["physics_check"] = {k: v for k, v in M["physics_check"].items() if k != "same_ruler"}
    if (M.get("scan") or {}).get("physics_select"):
        out["physics_select"] = M["scan"]["physics_select"]
    out["ours"] = {
        "q0": fa.get("q0"), "q95": fa.get("q95"), "li3_kernel": fa.get("li3"),
        "li1": it["li1"], "li3": it["li3"], "betap": it["betap"], "w_mhd_J": it["w_mhd_J"], "volume_m3": it["volume_m3"],
        "ip_fit_A": fa.get("ip"), "ip_ampere_A": it["ip_ampere_A"], "psi_map_unit": it.get("psi_map_unit"),
        "chi2_per_dof": fa.get("chi2_per_dof"), "zc_m": M.get("zc_anchor"), "axis_r": fa.get("axis_r"),
        "axis_z": fa.get("axis_z"), "converged": bool(fa.get("converged")), "iterations": fa.get("iterations"),
        "rounds": len(rounds), "n_used": rounds[-1].get("n_used") if rounds else None,
        "rejected": [{"kind": r["kind"], "name": r["name"], "sigma": r["sigma"], "round": r["round"]}
                     for r in M.get("rejected") or [] if not r.get("reverted")],
        "readmitted": [{"name": r["name"], "sigma": r["sigma"]} for r in M.get("readmitted") or [] if not r.get("reverted")]}
    xo = xpoint_balance(o["eq"], fa["psi_axis"], fa["psi_bnd"])
    if xo:
        out["ours"].update(xpt_dpsin=xo["dpsin"], xpt_config=xo["config"], xpt_upper=_rt(xo["upper"], 5),
                           xpt_lower=_rt(xo["lower"], 5))
    out["ours"]["n_rejected"] = len(out["ours"]["rejected"])
    out["ours"]["n_readmitted"] = len(out["ours"]["readmitted"])
    out["boundary"] = _r(M["boundary"], 5)
    if keep_psi:
        out["psi"] = {"r": M["grid"]["r"], "z": M["grid"]["z"], "psi": M["psi"], "unit": "Wb"}
    out["refs"] = _ref_entries(refs, t, o)
    out["seconds"] = round(time.time() - t_start, 2)
    return out


def kefit_slice(lib: Lib, t: float, meas: dict, res: dict, cfg: dict) -> tuple[dict, dict]:
    """一片交给本机 KEFIT（``kefit_compare`` 的名单写法与跑法），读回它的 g-file 当作一个参考来源 → (refs 的一项, 跑的记录)。
    KEFIT 解不出（没有 g-file）时 refs 的一项是 {error}，与树取不到同样记。"""
    import kefit_compare as KC                           #: 懒加载：不开 --kefit 时本文件不依赖它
    shot = int(res["shot"])
    st = res.get("settings") or {}
    text, rec = KC.namelist(shot, t, meas, res, cfg["smap"], cfg["loop_names"], (int(st.get("npp", 1)), int(st.get("nff", 2))),
                            cfg["fwtfc"])
    d = Path(cfg["workdir"]) / f"t{int(round(t * 1000)):05d}_{cfg['fwtfc']}"
    kr = KC.run_kefit(Path(cfg["exe"]), Path(cfg["tables"]), Path(cfg["pol2"]) if cfg.get("pol2") else None, d, text, shot, t)
    run = dict(kr, inputs=rec)
    if not kr.get("gfile"):
        return {"error": f"KEFIT 没有给出 g-file（rc {kr.get('rc')}；{d.name}/run.log）", "slice_time_s": t}, run
    try:
        e = read_reference(lib, str(d / kr["gfile"]), None, "kefit")
    except (KernelError, SystemExit, ValueError) as err:
        return {"error": sanitize(f"KEFIT g-file 读不了：{err}")[:200], "slice_time_s": t}, run
    e.update(slice_time_s=t, slice_index=None)
    if kr.get("reported"):                               #: KEFIT 自报的 W · β_p · l_i（日志的最后一行），页面画虚线
        e["scalars"].update(w_mhd=kr["reported"]["w_mhd_J"], betap=kr["reported"]["betap"], li=kr["reported"]["li"])
        e["empty"] = [q for q in e["empty"] if q not in ("w_mhd", "betap", "li")]
    return e, run


def _ref_entries(refs: dict, t: float, o: dict | None) -> dict:
    """每个来源那一片 → 序列里的 ``refs.<源>``：对方自报的量 · 同尺积分 · 边界；有我们的解（``o``）时另加两个解之间的距离。
    我们这一片失败时照样写（参考那一片在，页面照画它的迹与边界）。"""
    out = {}
    for src, e in refs.items():
        if src.startswith("_"):
            continue
        if "error" in e:
            out[src] = {"error": e["error"], "slice_time_s": e.get("slice_time_s")}
            continue
        try:
            e = dict(e, empty=list(e["empty"]))
            #: 本地 g-file（本机 KEFIT）的 ψ 单位由安培环路 I_p 对它自报的电流核（与 compare 的本地参考同一条）
            _their_integrals(e, str(e.get("tree") or "").startswith("file:"))
            row = compare_row("M", o, src, e, t) if o is not None else {}
        except Exception as err:                         # noqa: BLE001
            out[src] = {"error": sanitize(f"{type(err).__name__}: {err}")[-200:], "slice_time_s": e.get("slice_time_s")}
            continue
        ti = e.get("int") or {}
        out[src] = {
            "slice_time_s": e["slice_time_s"], "dt_s": e["slice_time_s"] - t, "slice_index": e["slice_index"],
            "scalars": e["scalars"], "empty": e["empty"],
            "same_ruler": {k: ti.get(k) for k in ("li1", "li3", "betap", "w_mhd_J", "volume_m3", "ip_ampere_A")},
            "axis_distance_m": row.get("axis_distance_m"), "boundary_distance": row.get("boundary_distance"),
            "psin_map_difference": row.get("psin_map_difference"), "boundary_psin_spread": e.get("boundary_psin_spread"),
            "boundary": _r(e["boundary"], 5)}
        xe = xpoint_balance(e, e["scalars"]["psi_axis"], e["scalars"]["psi_bnd"]) if (
            e.get("psi") and "psi_axis" in e["scalars"] and "psi_bnd" in e["scalars"]) else None
        if xe:
            out[src]["xpoint"] = {"dpsin": xe["dpsin"], "config": xe["config"], "upper": _rt(xe["upper"], 5),
                                  "lower": _rt(xe["lower"], 5)}
    return out


_SERIES_WORKER: dict = {}


def _series_init(path: str) -> None:
    _SERIES_WORKER["lib"] = Lib(Path(path))


def _series_job(args):
    try:
        return series_slice(_SERIES_WORKER["lib"], *args)
    finally:
        close_jobs()


def series_summary(slices: list, sources: list) -> dict:
    """逐来源、逐量的差（我们 − 对方）：n · 均值 · rms · 最大 |差| · 两边各自的均值 · 相对均差 · 差为正的份额 ·
    差随时间的斜率（线性最小二乘，每秒）——份额近 0 或 1、斜率小，就是跨时间的系统差，不是逐片的散布。"""
    ok = [s for s in slices if s.get("status") == "ok"]
    un = [s for s in slices if s.get("status") == "unphysical"]
    out = {"n_slices": len(slices), "n_ok": len(ok), "n_unphysical": len(un), "n_failed": len(slices) - len(ok) - len(un),
           "by_source": {}}
    if un:                                               #: unphysical 的片数照留，但不进下面的均值 / rms
        fired: dict = {}
        for s in un:
            for cid in (s.get("physics_check") or {}).get("failed") or []:
                fired[cid] = fired.get(cid, 0) + 1
        out["unphysical"] = {"excluded_from_stats": len(un), "times_s": [s["time_s"] for s in un], "checks_fired": fired}
    ipd = [(s["time_s"], s["ours"]["ip_fit_A"] - s["measured"]["ip_A"]) for s in ok
           if fin(s["ours"].get("ip_fit_A")) and fin(s["measured"].get("ip_A"))]
    if ipd:
        out["ip_fit_minus_measured_A"] = _stats(ipd)
    for src in sources:
        per: dict = {}
        for key, (sa, ka), (sb, kb) in SERIES_PAIRS:
            pts = []
            for s in ok:
                r = (s.get("refs") or {}).get(src) or {}
                a, b = s["ours"].get(ka), (r.get(sb) or {}).get(kb)
                if fin(a) and fin(b):
                    pts.append((s["time_s"], a - b, a, b))
            if pts:
                per[key] = _stats([(p[0], p[1]) for p in pts], ours=[p[2] for p in pts], theirs=[p[3] for p in pts])
        for key, path in SERIES_DIST:
            pts = [(s["time_s"], _dig((s.get("refs") or {}).get(src) or {}, path)) for s in ok]
            pts = [p for p in pts if p[1] is not None]
            if pts:
                v = [p[1] for p in pts]
                per[key] = {"n": len(v), "mean": mean(v), "rms": math.sqrt(mean([x * x for x in v])), "max": max(v)}
        cfg = [(s["ours"].get("xpt_config"), (((s.get("refs") or {}).get(src) or {}).get("xpoint") or {}).get("config"))
               for s in ok]
        cfg = [c for c in cfg if c[0] and c[1]]
        if cfg:                                          #: 形位（DN / LSN / USN）逐片对得上几片，与两边各自的计数
            count = lambda xs: {k: xs.count(k) for k in sorted(set(xs))}  # noqa: E731
            per["xpoint_config"] = {"n": len(cfg), "match": sum(1 for a, b in cfg if a == b),
                                    "ours": count([a for a, _ in cfg]), "theirs": count([b for _, b in cfg])}
        dts = [abs(((s.get("refs") or {}).get(src) or {}).get("dt_s")) for s in ok
               if fin(((s.get("refs") or {}).get(src) or {}).get("dt_s"))]
        if dts:
            per["abs_dt_s"] = {"n": len(dts), "mean": mean(dts), "max": max(dts)}
        out["by_source"][src] = per
    return out


def _stats(td: list, ours=None, theirs=None) -> dict:
    t, d = [x[0] for x in td], [x[1] for x in td]
    st = {"n": len(d), "mean_diff": mean(d), "rms_diff": math.sqrt(mean([x * x for x in d])),
          "max_abs_diff": max(abs(x) for x in d), "positive_fraction": sum(1 for x in d if x > 0) / len(d),
          "diff_slope_per_s": linfit(t, d)[0] if len(d) > 2 and max(t) > min(t) else None}
    if ours is not None:
        mo, mt = mean(ours), mean(theirs)
        st.update(mean_ours=mo, mean_theirs=mt, rel_mean_diff=(st["mean_diff"] / abs(mt)) if mt else None)
    return st


def series(shot: int, t0: float, t1: float, *, lib: "Lib | None" = None, dt: float | None = None, chain: str = "east",
           sources="efit", signals: str | None = None, server: str | None = None, timeout: float = 120.0,
           jobs: int = JOBS, inner_jobs: int = 1, keep_psi: bool = False, results_dir: str | None = None,
           kefit: dict | None = None, **options) -> dict:
    """``series`` 的进程内形 → 时间序列文档（``@type: fylite:KineticReconSeries``，与 ``series -o`` 写出的同一份）。
    ``dt`` 为 None = 时刻取离线 EFIT 自己在 [t0, t1] 内的片（``--at-efit``）；给了就用均匀网格、每个时刻比最近的那一片。
    ``jobs`` = 并行几个切片进程；``inner_jobs`` = 每片档 M 设定点并行几路（两者都不改答案）。
    ``options`` = ``run`` 的档 M 开关（``SERIES_M_OPTS``）。"""
    t_all = time.time()
    lib = lib or Lib(DEFAULT_LIB)
    bad = set(options) - set(SERIES_M_OPTS)
    if bad:
        raise TypeError(f"series: not a tier-M option: {sorted(bad)} (have {', '.join(SERIES_M_OPTS)})")
    if not t1 > t0:
        raise SystemExit(f"--t1 {t1} 不大于 --t0 {t0}")
    srcs = [x for x in (sources.split(",") if isinstance(sources, str) else list(sources)) if x]
    if dt is None and "efit" not in srcs:
        raise SystemExit("--at-efit 的时刻取自离线 EFIT：--sources 里要有 efit（或改用 --dt）")
    if dt is not None and not dt > 0:
        raise SystemExit(f"--dt {dt} 要 > 0")
    doc, _res = lib.device("east", shot, chain)
    sig = eq_signals(doc, signals) if srcs else {}
    kcfg = None
    if kefit:                                            #: --kefit：每片另跑本机 KEFIT（槽映射整炮定一次）
        import kefit_compare as KC
        bundle = Path(kefit.get("bundle") or KC.DEFAULT_BUNDLE)
        tables = Path(kefit.get("tables") or bundle / "green2022_pcs")
        exe = Path(kefit.get("exe") or KC.DEFAULT_EXE)
        if not exe.exists():
            raise SystemExit(f"--kefit：KEFIT 可执行文件不在 {exe}（--kefit-exe 或 $KEFIT_EXE）")
        if not (tables / "dprobe.dat").exists():
            raise SystemExit(f"--kefit：格林函数表不在 {tables}（--kefit-bundle 或 $KEFIT_BUNDLE）")
        smap = KC.slot_map(doc, tables)
        kcfg = {"exe": str(exe.resolve()), "tables": str(tables.resolve()), "pol2": str(bundle / "green2018_wpf_64" / "pol2.est"),
                "workdir": str(Path(kefit.get("workdir") or "kefit_runs").resolve()), "fwtfc": kefit.get("fwtfc") or "fixed",
                "smap": smap, "loop_names": [_name(x) for x in _aos(doc["magnetics"].get("flux_loop"))]}
        Path(kcfg["workdir"]).mkdir(parents=True, exist_ok=True)
        log(f"series: local KEFIT {exe.name} · {tables.name} · FWTFC {kcfg['fwtfc']} · "
            f"{sum(1 for i in smap if i is not None)}/{len(smap)} probe slots matched")
    # ---- 参考树：时基 · 标量 · 网格读一次 → 定时刻 → 大数组按要的片读一次；另读实测逆磁储能整条
    t_f = time.time()
    eqs, unavailable, wd = {}, {}, None
    host, port = server_of(server)
    s = lib.mds_open(host, port, timeout)
    try:
        for src in srcs:
            try:
                eqs[src] = EquilibriumSeries(s, sig, src, shot)
            except KernelError as err:                   # 树不在 / 节点没数：是数据，不是故障
                unavailable[src] = sanitize(str(err))[:300]
                s.tree = None
                log(f"series: {src} unavailable — {unavailable[src][:120]}")
        if dt is None and "efit" not in eqs:
            raise SystemExit(f"--at-efit：#{shot} 取不到离线 EFIT（{unavailable.get('efit', '?')}）——改用 --dt")
        if dt is None:
            times = [x for x in eqs["efit"].tb if t0 <= x <= t1]
            base = {"mode": "at-efit", "source": "efit", "note": "时刻就是离线 EFIT 的片：每个比较都在对方的片上，不插值"}
        else:
            n = int(math.floor((t1 - t0) / dt + 1e-9)) + 1
            times = [round(t0 + k * dt, 9) for k in range(n)]
            base = {"mode": "dt", "dt_s": dt, "note": "均匀网格：每个时刻与各来源最近的一片比，|Δt| 记在每片的 dt_s"}
        if not times:
            raise SystemExit(f"[{t0}, {t1}] 里一个时刻都没有" + ("（离线 EFIT 在这一段没有片）" if dt is None else ""))
        base["n"] = len(times)
        log(f"series: #{shot} {len(times)} time(s) in [{t0}, {t1}] s ({base['mode']})")
        for src in list(eqs):
            t_s = time.time()
            es = eqs[src]
            try:
                s.tree = None
                es.load({es.nearest(t) for t in times})
                log(f"series: {src} {len(es.tb)} slices, arrays read once ({es.mode}; {time.time() - t_s:.1f} s)")
            except KernelError as err:
                unavailable[src] = sanitize(str(err))[:300]
                del eqs[src]
                s.tree = None
                log(f"series: {src} unavailable — {unavailable[src][:120]}")
        m = ((doc.get("magnetics") or {}).get("fylite:signal") or {}).get("w_dia")
        if m:
            try:
                s.tree = None
                s.open_tree(m["tree"], shot)
                v, tbw = s.read("data", m["node"])[0], s.read("dim_of", m["node"])[0]
                if any(v):
                    wd = (v, tbw, m.get("scale", 1.0))
            except KernelError as err:
                unavailable["w_dia"] = sanitize(str(err))[:200]
    finally:
        s.close()
    fetch_refs_s = time.time() - t_f
    if dt is None and "efit" not in eqs:
        raise SystemExit(f"--at-efit：#{shot} 离线 EFIT 的 ψ / 边界取不到（{unavailable.get('efit', '?')}）——改用 --dt")
    # ---- 磁测量：整条读一次（不读 POINT），逐时刻归约
    t_m = time.time()
    msrc = MagneticsSource(lib, shot, chain, server, timeout)
    try:
        msrc.prefetch(point=False)
    finally:
        msrc.close()
    fetch_mag_s = time.time() - t_m
    log(f"series: magnetics / PF / Ip / TF read once: {len(msrc.cache)} signals, {fetch_mag_s:.1f} s")
    t_r = time.time()
    jobs_args, cut = [], {}
    for t in times:
        refs: dict = {}
        try:
            meas = msrc.at(t, point=False)
        except Exception as err:                         # noqa: BLE001
            meas = None
            refs["_meas_error"] = "measurements: " + sanitize(f"{type(err).__name__}: {err}")[-280:]
        for src, es in eqs.items():
            k = es.nearest(t)
            if (src, k) not in cut:
                try:
                    cut[(src, k)] = es.slice(k)
                except KernelError as err:
                    cut[(src, k)] = {"error": sanitize(str(err))[:200], "slice_time_s": es.tb[k]}
            refs[src] = dict(cut[(src, k)])
        w = None
        if wd is not None:
            v, tbw, sc = wd
            sel = [v[i] for i in _window(tbw, min(len(v), len(tbw)), t, 0.010) if abs(tbw[i] - t) <= 0.010]
            w = mean(sel) * sc if sel else None
        jobs_args.append((t, meas, w, refs, dict(options, jobs=inner_jobs), keep_psi, results_dir, kcfg))
    reduce_s = time.time() - t_r
    if results_dir:
        Path(results_dir).mkdir(parents=True, exist_ok=True)
    # ---- 逐片反演：各片互不依赖，进程池按时间次序归并（与串行逐片相同）
    t_p = time.time()
    nw = max(1, min(int(jobs), len(times)))
    if nw == 1:
        slices = []
        for i, args in enumerate(jobs_args):
            slices.append(series_slice(lib, *args))
            close_jobs()
            _series_log(i, len(times), slices[-1])
    else:
        with concurrent.futures.ProcessPoolExecutor(nw, mp_context=multiprocessing.get_context("fork"),
                                                    initializer=_series_init, initargs=(str(lib.path),)) as ex:
            futs = [ex.submit(_series_job, a) for a in jobs_args]
            done = 0
            for fu in concurrent.futures.as_completed(futs):
                done += 1
                _series_log(done - 1, len(times), fu.result())
            slices = [fu.result() for fu in futs]
    slices_s = time.time() - t_p
    limiter = next((s_.get("_limiter") for s_ in slices if s_.get("_limiter")), None)
    for s_ in slices:
        s_.pop("_limiter", None)
    k = lib.linked_kernel()
    per = [s_["seconds"] for s_ in slices if fin(s_.get("seconds"))]
    ro = run_options(**options)
    out = {"@type": "fylite:KineticReconSeries", "app": APP, "version": VERSION,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "comment": "时间序列：档 M（只磁测量）逐时刻反演与装置自己的平衡重建（参考库，只作比较，不进拟合）逐时刻比。"
                      "含实验数据派生量：不入仓。服务器地址记作 mds.invalid。",
           "shot": int(shot), "measurement_chain": chain, "interval_s": [t0, t1], "time_base": base,
           "times": times, "tier": "M",
           "settings": dict({k_: v for k_, v in vars(run_options(**options)).items() if k_ in SERIES_M_OPTS},
                            jobs=nw, inner_jobs=inner_jobs, sources=srcs, keep_psi=keep_psi, warm_start=False,
                            serror=SERROR, loop_floor=LOOP_FLOOR, probe_floor=PROBE_FLOOR, window_ms=WINDOW_MS,
                            drift_window_s=list(DRIFT_WINDOW)),
           "provenance": {"library": lib.path.name, "library_sha256": _sha256(lib.path),
                          "kernel": {"version": k.get("kernel_version") or k.get("version"), "abi": k.get("abi"),
                                     "built": k.get("built"), "sha256": k.get("sha256"),
                                     "rustc": (k.get("toolchain") or {}).get("rustc")},
                          "facts": {"source": (doc.get("provenance") or {}).get("source"),
                                    "generator": (doc.get("provenance") or {}).get("generator"),
                                    "basis": doc.get("_basis"),
                                    "document_sha256": _sha256_text(json.dumps(doc, sort_keys=True))},
                          "magnetics": msrc.source, "same_ruler": map_integrals.__doc__.strip()},
           "sources": dict({src: {"label": EQ_SOURCES.get(src, src), "tree": es.tree, "n_slices": len(es.tb),
                                  "slices_in_interval": sum(1 for x in es.tb if t0 <= x <= t1)} for src, es in eqs.items()},
                           **({"kefit": {"label": EQ_SOURCES["kefit"], "tree": "local:" + Path(kcfg["exe"]).name,
                                         "tables": Path(kcfg["tables"]).name, "fwtfc": kcfg["fwtfc"],
                                         "slots_matched": sum(1 for i in kcfg["smap"] if i is not None),
                                         "n_slices": len(times), "slices_in_interval": len(times),
                                         "note": "同一组原始测量、档 M 最后的掩码、同式误差、同基交给本机 KEFIT（README §6.6）；它是另一份实现，不是真值"}}
                              if kcfg else {})),
           "unavailable": unavailable,
           "physics_check": ({"enabled": True, "select": bool(ro.physics_select), "bounds": phys_bounds(ro.phys_bounds),
                              "note": PHYS_NOTE + "序列：unphysical 的片数照留、照画，不进 summary 的均值 / rms（summary.unphysical 记几片、哪几条）。"}
                             if ro.physics_check else {"enabled": False}),
           "device": {"limiter": limiter},
           "timing": {"fetch_references_s": round(fetch_refs_s, 1), "fetch_magnetics_s": round(fetch_mag_s, 1),
                      "reduce_s": round(reduce_s, 2), "slices_wall_s": round(slices_s, 1),
                      "slice_s": ({"mean": round(mean(per), 2), "min": min(per), "max": max(per), "sum": round(sum(per), 1)}
                                  if per else None),
                      "total_s": round(time.time() - t_all, 1)},
           "slices": _rt(slices),
           "summary": _rt(series_summary(slices, list(eqs) + (["kefit"] if kcfg else [])))}
    return strict_json(out)


def _series_log(i: int, n: int, s: dict) -> None:
    if s.get("status") in ("ok", "unphysical"):
        o = s["ours"]
        log(f"series [{i + 1}/{n}] t {s['time_s']:.4f} s: q0 {o['q0']:.3f} q95 {o['q95']:.3f} chi2/dof "
            f"{o['chi2_per_dof']:.3f} zc {o['zc_m'] * 1e3:+.0f} mm ({s['seconds']:.1f} s)"
            + ("" if s["status"] == "ok" else " ★★ UNPHYSICAL: " + ",".join((s.get("physics_check") or {}).get("failed") or [])))
    else:
        log(f"series [{i + 1}/{n}] t {s['time_s']:.4f} s: FAILED — {str(s.get('why'))[:120]}")


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def print_series(out: dict) -> None:
    def f(x, n=3):
        return "—" if x is None else f"{x:.{n}f}"
    su = out["summary"]
    tm = out["timing"]
    print(f"#{out['shot']}  [{out['interval_s'][0]}, {out['interval_s'][1]}] s · {out['time_base']['mode']} · "
          f"{su['n_ok']}/{su['n_slices']} slices ok · {su.get('n_unphysical', 0)} unphysical · {su['n_failed']} failed")
    if su.get("unphysical"):
        u = su["unphysical"]
        print(f"  ★★物理校验没过 {u['excluded_from_stats']} 片（不进下面的汇总）："
              + "、".join(f"{k} × {v}" for k, v in sorted(u["checks_fired"].items(), key=lambda kv: -kv[1])))
    print(f"  取数：参考树 {tm['fetch_references_s']} s · 磁测量 {tm['fetch_magnetics_s']} s · 归约 {tm['reduce_s']} s；"
          f"逐片 {tm['slices_wall_s']} s（{out['settings']['jobs']} 进程；每片 {f((tm['slice_s'] or {}).get('mean'), 1)} s）")
    for src, why in out["unavailable"].items():
        print(f"  {EQ_SOURCES.get(src, src)}：取不到（{why[:90]}）")
    ip = su.get("ip_fit_minus_measured_A")
    if ip:
        print(f"  拟合 Ip − 实测 Ip：均 {ip['mean_diff'] / 1e3:+.2f} kA · rms {ip['rms_diff'] / 1e3:.2f} kA")
    for src, per in su["by_source"].items():
        print(f"  ours − {src}：量 | n | 均差 | rms | 最大|差| | 我们均 | 对方均 | 差>0 份额 | 斜率/s")
        for key, st in per.items():
            if "mean_diff" in st:
                print(f"    {key} | {st['n']} | {st['mean_diff']:+.4g} | {st['rms_diff']:.4g} | {st['max_abs_diff']:.4g} | "
                      f"{st['mean_ours']:.4g} | {st['mean_theirs']:.4g} | {st['positive_fraction']:.2f} | "
                      f"{'—' if st['diff_slope_per_s'] is None else format(st['diff_slope_per_s'], '+.3g')}")
            elif key == "xpoint_config":
                print(f"    X 点形位 | {st['n']} | 逐片相同 {st['match']} | 我们 {st['ours']} | 对方 {st['theirs']}")
            elif "rms" in st:
                print(f"    {key} | {st['n']} | 均 {st['mean']:.4g} | rms {st['rms']:.4g} | 最大 {st['max']:.4g}")
            else:
                print(f"    {key} | {st['n']} | 均 {st['mean']:.4g} | 最大 {st['max']:.4g}")
    for s in out["slices"]:
        if s.get("status") == "unphysical":
            print(f"  ★★不物理 t {s['time_s']:.4f} s：{','.join((s.get('physics_check') or {}).get('failed') or [])}")
        elif s.get("status") != "ok":
            print(f"  ★失败 t {s['time_s']:.4f} s：{str(s.get('why'))[:120]}")


def cmd_series(a) -> int:
    opts = {k: getattr(a, k) for k in SERIES_M_OPTS}
    out = series(a.shot, a.t0, a.t1, lib=Lib(Path(a.lib) if a.lib else DEFAULT_LIB), dt=a.dt, chain=a.chain,
                 sources=a.sources, signals=a.signals, server=a.server, timeout=a.timeout, jobs=a.jobs,
                 inner_jobs=a.inner_jobs, keep_psi=a.keep_psi, results_dir=a.results_dir,
                 kefit=({"exe": a.kefit_exe, "bundle": a.kefit_bundle, "fwtfc": a.kefit_fwtfc, "workdir": a.kefit_workdir}
                        if a.kefit else None), **opts)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
                           encoding="utf-8")
    print_series(out)
    log(f"-> {a.out} ({Path(a.out).stat().st_size / 1e3:.0f} kB, {out['timing']['total_s']} s)")
    return 0 if out["summary"]["n_ok"] else 1


class _RefAction(argparse.Action):
    """``--gfile P [--afile P] [--label N]``，可重复：``--afile`` / ``--label`` 挂在它前面最近的那个 ``--gfile`` 上。"""

    def __call__(self, parser, ns, value, option_string=None):
        refs = list(getattr(ns, self.dest, None) or [])
        if option_string == "--gfile":
            refs.append({"gfile": value, "afile": None, "label": None})
        elif not refs:
            parser.error(f"{option_string} 要跟在一个 --gfile 之后")
        else:
            key = option_string.lstrip("-")
            if refs[-1][key] is not None:
                parser.error(f"一个 --gfile 只能有一个 {option_string}")
            refs[-1] = dict(refs[-1], **{key: value})
        setattr(ns, self.dest, refs)


def _parser() -> argparse.ArgumentParser:
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
    p.add_argument("--ts-max-dt", type=float, default=TS_MAX_DT,
                   help=f"Thomson 脉冲离 --time 最远几秒还收（缺省 {TS_MAX_DT}；更远就拒，不当这一片的测量）")
    p.add_argument("-o", "--out", required=True)
    r = sub.add_parser("run", help="反演：测量文档 → 结果 JSON")
    r.add_argument("input", help="pull 的输出 · 原始树归约件 raw_slices_*.json · 或裸测量字典")
    r.add_argument("--time", type=float, help="归约件里取哪一片（取最近）")
    r.add_argument("--thomson", help="另给的 Thomson（pull --thomson-only 的输出）")
    r.add_argument("--tiers", default="MKP", help="跑哪几档（缺省 MKP；M 总是跑）")
    add_tier_m_args(r)
    r.add_argument("--jobs", type=int, default=JOBS, metavar="N",
                   help=f"档 M 一轮里的独立反演同时跑几路（工作进程；1 = 串行；缺省 min(16, CPU 数) = {JOBS}）")
    r.add_argument("--point-off", type=lambda s: [int(x) for x in s.split(",") if x], default=[],
                   help="手动关掉的 POINT 弦（1 起，逗号分隔；B-06 主集为 4,7,8,11）")
    r.add_argument("--dead-sigma", type=float, default=8.0, help="零假设残差超过它的 POINT 行判为死道")
    r.add_argument("--kinetic-passes", type=int, default=6)
    r.add_argument("--kinetic-tol", type=float, default=1e-3)
    r.add_argument("--psin-max", type=float, default=0.98, help="Thomson 点只收 psi_N 小于它的（分离面附近不收）")
    r.add_argument("--sigma-floor", type=float, default=0.05, help="Thomson 压强 sigma 的相对下限")
    r.add_argument("--thomson-clean", choices=("local", "smooth"), default="local",
                   help="档 P 的 Thomson 清洗：local（缺省）= wei_profiles 的局部 MAD 清洗，T_e、n_e 分别做；"
                        "smooth = 旧法，对 p(psi_N) 的全局光滑拟合逐点剔（峰化剖面上会把芯部剔光，只为复现旧读数）")
    r.add_argument("--thomson-clean-opts", type=json.loads, default=None, metavar="JSON",
                   help="local 清洗的参数覆盖（键见 wei_profiles.CLEAN_DEFAULTS；档 P 缺省另关 mirror）")
    r.add_argument("--thomson-clip", type=float, default=4.0,
                   help="--thomson-clean smooth 的阈值：Thomson 点离光滑拟合超过它（sigma）就剔")
    r.add_argument("--sigma-scales", type=lambda s: [float(x) for x in s.split(",") if x],
                   default=[1, 1.5, 2, 3, 4, 6, 8], help="档 P 的 sigma 续延：依次试这些放宽倍数，取第一个收敛的")
    r.add_argument("--p-fast-frac", type=float, default=0.0, help="声明的快离子压强份额（缺省 0 = 不扣）")
    r.add_argument("--curv", type=float, default=0.0, help="p′ / FF′ 曲率正则权重（缺省 0 = 关）")
    add_fvac_arg(r)
    r.add_argument("--efit-fit", choices=("auto", "off", "P", "M", "MP"), default="auto",
                   help="k-file 的拟合设定（kfile 读出的 efit_fit：张力样条基 · 磁轴 q · 电流密度行 · 结点约束 · I_p 作测量）"
                        "用在哪几档：auto = 有 efit_fit 时档 P；off = 不用")
    r.add_argument("--efit-parts", default=",".join(EFIT_PARTS),
                   help=f"efit_fit 里用哪几样（逗号分隔，缺省全部：{','.join(EFIT_PARTS)}）")
    r.add_argument("--efit-override", type=json.loads, default=None, metavar="JSON",
                   help="换算的覆盖（键：pprime · ffprime 整块替换，tension_scale · q0_weight · j_weight · lincon_weight · ip_sigma）")
    r.add_argument("--p-on", choices=("M", "K"), default="M",
                   help="档 P 叠在哪一档上：M（缺省，外环照常）· K（叠 POINT 行；外环在那一档不重映，只跑一遍）")
    add_phys_args(r)
    r.add_argument("-o", "--out", required=True)
    k = sub.add_parser("kfile", help="同输入：EFIT k-file（&IN1）→ 测量文档（道序按装置事实对位，对不上就拒）")
    k.add_argument("kfile", help="EFIT k-file（名单 &IN1：COILS · EXPMP2 · BRSP · PLASMA · BTOR · NPRESS 段）")
    k.add_argument("--chain", default="east", help="测量链（缺省 east；k-file 道序只在其旧命名代上有据）")
    k.add_argument("--weights", choices=("mask", "kfile"), default="mask",
                   help="探针权：mask（缺省）= 只取 k-file FWTMP2 的用 / 不用，数值用装置的 · kfile = 照搬 FWTMP2 数值")
    k.add_argument("--point-from", metavar="FILE", help="取这份 pull 输出里的 POINT 块（k-file 里没有 POINT；档 K 要它）")
    k.add_argument("-o", "--out", required=True, help="测量文档路径")
    c = sub.add_parser("compare", help="对拍：结果 JSON ↔ 装置自己的平衡重建（离线 EFIT · P-EFIT · 实时 EFIT）离它最近的一片"
                                       "，和/或本地参考平衡文件（--gfile）")
    c.add_argument("result", help="run 的输出（带 ψ 图的结果 JSON）")
    c.add_argument("--time", type=float, help="对拍的时刻 [s]（缺省取结果里的 time_s）")
    c.add_argument("--sources", default="efit,pefit,efitrt",
                   help="比哪几个装置树来源（逗号分隔；树不在的那一个记为取不到；给空串 '' = 不连 MDSplus，只比 --gfile）")
    c.add_argument("--signals", help="节点名表：tools/abox-to-facts.py east 编出的 east.jsonld（库里的事实还没有 equilibrium 组时要给）")
    c.add_argument("--server", help="mdsip 服务器 主机:端口（缺省 $FYLITE_MDSIP_SERVER）")
    c.add_argument("--timeout", type=float, default=120.0)
    c.add_argument("--gfile", action=_RefAction, dest="refs", metavar="PATH",
                   help="本地参考平衡 G-EQDSK（可重复；每给一个就多比一个来源）")
    c.add_argument("--afile", action=_RefAction, dest="refs", metavar="PATH",
                   help="紧接的那个 --gfile 的 A-EQDSK（给 l_i · β_p · W · V；可省）")
    c.add_argument("--label", action=_RefAction, dest="refs", metavar="NAME",
                   help="紧接的那个 --gfile 在表里的名字（缺省文件名）")
    c.add_argument("-o", "--out", required=True, help="比较结果 JSON（含实验数据派生量：不入仓）")
    s = sub.add_parser("series", help="时间序列：[t0, t1] 内逐时刻的档 M 反演 ↔ 装置自己的平衡重建（离线 EFIT …）逐时刻比")
    s.add_argument("--shot", type=int, required=True)
    s.add_argument("--t0", type=float, required=True, help="区间起点 [s]")
    s.add_argument("--t1", type=float, required=True, help="区间终点 [s]")
    tb = s.add_mutually_exclusive_group()
    tb.add_argument("--at-efit", action="store_true",
                    help="时刻取离线 EFIT 自己在 [t0, t1] 内的片（缺省）：每个比较都在对方的片上，不插值")
    tb.add_argument("--dt", type=float, default=None, metavar="S",
                    help="改用均匀时间网格，步长 S 秒；每个时刻与各来源最近的一片比，|Δt| 记下")
    s.add_argument("--chain", default="east", help="测量链（缺省 east）")
    s.add_argument("--sources", default="efit",
                   help="与哪几个装置树来源比（逗号分隔：efit · pefit · efitrt；缺省 efit；--at-efit 要有 efit）")
    s.add_argument("--signals", help="节点名表（同 compare --signals）")
    s.add_argument("--server", help="mdsip 服务器 主机:端口（缺省 $FYLITE_MDSIP_SERVER）")
    s.add_argument("--timeout", type=float, default=120.0, help="mdsip 读超时 [s]")
    s.add_argument("--jobs", type=int, default=JOBS, metavar="N",
                   help=f"几片同时反演（切片进程数；1 = 串行，结果逐位相同；缺省 min(16, CPU 数) = {JOBS}，不超过片数）")
    s.add_argument("--inner-jobs", type=int, default=1, metavar="N",
                   help="每一片里档 M 设定点并行几路（同 run --jobs；缺省 1——片之间已经并行）")
    add_tier_m_args(s)
    add_fvac_arg(s)
    add_phys_args(s)
    s.add_argument("--kefit", action="store_true",
                   help="每片另跑本机 KEFIT（同一组测量、档 M 最后的掩码、同式误差、同基），作参考来源 kefit 进比较与页面（README §6.6）")
    s.add_argument("--kefit-exe", help="KEFIT 可执行文件（缺省 $KEFIT_EXE 或 ~/.local/opt/kefit/efitd6565d_76）")
    s.add_argument("--kefit-bundle", help="KEFIT 参考包（格林函数表 green2022_pcs 在里面；缺省 $KEFIT_BUNDLE）")
    s.add_argument("--kefit-fwtfc", choices=("fixed", "gui", "free"), default="fixed",
                   help="KEFIT 的 PF 电流：fixed（缺省，≈ 本应用的固定）· gui（0.3）· free（0）")
    s.add_argument("--kefit-workdir", default="kefit_runs", help="KEFIT 逐片的运行目录（名单、g / a / m 文件留在这里）")
    s.add_argument("--keep-psi", action="store_true", help="每片另存我们的 ψ(R,Z)（65²；缺省不存，文件小）")
    s.add_argument("--results-dir", metavar="DIR",
                   help="另把每一片完整的结果 JSON（与 run -o 同形，页面能单独打开）写进这个目录")
    s.add_argument("-o", "--out", required=True, help="时间序列 JSON（fylite:KineticReconSeries；含实验数据派生量：不入仓）")
    return ap


def add_tier_m_args(p) -> None:
    """档 M 的开关：``run`` 与 ``series`` 共用这一组（同名、同缺省）。"""
    #: ★缺省基 npp 1 / nff 2（2026-09-22 起；此前 2 / 2 取自 KEFIT GUI 的 KPPCUR / KFFCUR）：离线 EFIT（efit_east 树）
    #: 交付的 p′ 恰是 (1 − ψ_N)、FF′ 恰是边缘为零的二次式（#137985 逐片拟到 1e-16），即 KPPCUR 1 / KFFCUR 2、
    #: PCURBD = FCURBD = 1——与内核 ``poly`` 的 (x^k − x^n) 同一族。多出的一阶 p′ 是磁测量定不住的方向：
    #: 2 / 2 时 #137985 3–8 s 39 片里 32 片芯部压强为负、磁轴普遍偏内 5–7 cm（README §6.5）。``wei2026`` 用 ``SETTINGS`` 的 2 / 2，不变。
    p.add_argument("--npp", type=int, default=1)
    p.add_argument("--nff", type=int, default=2)
    p.add_argument("--loops", choices=("B+readmit", "B", "all"), default="B+readmit",
                   help="磁通环起步组：FL*B 组起步、收敛后按残差回收其余（缺省）· 只 B 组 · 全部")
    p.add_argument("--reject-sigma", type=float, default=5.0, help="档 M 剔道阈值 [sigma]")
    p.add_argument("--max-rounds", type=int, default=6)
    p.add_argument("--per-round", type=int, default=4)
    add_scan_args(p, "coarse")


def add_phys_args(p) -> None:
    """物理校验的开关：``run`` 与 ``series`` 共用（README §3.9）。"""
    p.add_argument("--no-physics-check", dest="physics_check", action="store_false",
                   help="不做物理校验（缺省做：每档解完核 W · β_p · p ≥ 0 · q · l_i · 边界 · ψ 次序 · I_p · χ²/dof，"
                        "没过的档记 unphysical）")
    p.add_argument("--phys-bounds", default=None, metavar="K=V,…",
                   help="物理校验界值的覆盖（键见 README §3.9 的表，如 q0_min=0.5,chi2_dof_max=10）")
    p.add_argument("--physics-select", action="store_true",
                   help="档 M 设定点扫描只在过了物理校验的收敛点里取 χ² 最小者（一个都不过时照旧取、记下）；缺省关")


def add_fvac_arg(p) -> None:
    p.add_argument("--fvac", type=float, default=None, metavar="TM",
                   help="声明真空 F = R·B_T [T·m]：压过测量文档里 TF 电流算出的（旧炮 east 树没有 TF 节点时要给；结果里记出处）")


def main(argv=None) -> int:
    a = _parser().parse_args(argv)
    return {"pull": cmd_pull, "kfile": cmd_kfile, "run": cmd_run, "compare": cmd_compare, "series": cmd_series}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
