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

★★独立发行：只用 Python 标准库（ctypes · json · math）与**两份库**（内核 ``libfylite_kernel.so`` · 数据层
``libsp.so``，各自的版本号）——不 import fylite 的 Python 包，也不要 numpy。两份库里有三样本应用要的东西：

* 内核的文档门 ``fylite_rs_fyo_json``——每一次物理计算（线圈份额、反演、弦积分、剖面拟合）；
* 数据层（``libsp``，``sp_call``）的装置事实（``facts``）与解析规则（``resolve_device``）——EAST 在这一炮、这条
  测量链上的装置描述，从 facts 目录读：本文件旁边的 ``facts/``，或 ``$FY_FACTS_PATH``（EAST 的装置事实不公开，
  自己放进来）；
* 数据层的 mdsip 读（``mds_read_many``）——取数；与 g-file 读者（``read`` 带 ``raw``）。

``pull`` 从原始树（``east`` 测量链：磁探针 · 磁通环 · PF 罗氏线圈 · Ip · TF 线圈电流 · POINT
11 弦）与 ``ts_east``（芯部 Thomson）取一个时刻，归约成一份测量文档。``run`` 也收
B-06 那份原始树归约件（``raw_slices_*.json``，按 ``--time`` 取最近一片）或 ``pull`` 的输出；
Thomson 可另给 ``--thomson``（``pull --thomson-only`` 的输出）。

约束阶梯（三档，档不同、能声称的东西不同；读数不可跨档比）：

    M   磁测量：环 + 探针 + Ip + 实测 PF 电流；竖直设定点扫描取 chi2 极小；坏道由拟合自己剔
    K   M + POINT：先在 M 的平衡上前向算 11 弦（零假设），再把法拉第角作行加进拟合，逐轮重建行
    P   + Thomson 压强点（实空间 R, Z，逐点实测 sigma），自洽外环逐遍把测点重映到 psi_N
    D   K（或 M）+ 实测逆磁储能只定压强标度（Thomson 不可用时 P 的替代；假定各向同性热压；--tiers 点名才跑）

★★实验数据不入仓：测量文档、结果 JSON 都写在调用方给的路径；服务器地址在写出的文件里
一律记作 ``mds.invalid``。

库在哪：缺省是本文件旁边的 ``libfylite_kernel.so``，数据层 ``libsp.so`` 在它旁边（一个位置，不搜索）；``--lib`` 显式给另一份内核（数据层仍在它旁边）。
取数另要 ``$FYLITE_MDSIP_SERVER=主机:端口``（或 ``--server``）。
"""
from __future__ import annotations

import argparse
import bisect
import concurrent.futures
import copy
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
#: ★★两份库、各自的版本号，放在同一处：内核 ``libfylite_kernel.so``（物理，文档门）与数据层 ``libsp.so``（spdata：
#: 装置事实 · 解析 · mdsip · g-file）。2026-09-26..27 数据层是 ``libfylite_runtime.so``。
KERNEL_LIB_NAME = "libfylite_kernel.so"
SP_LIB_NAME = "libsp.so"
DEFAULT_LIB = HERE / KERNEL_LIB_NAME

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
E_CHARGE = 1.602176634e-19

SETTINGS = {"npp": 2, "nff": 2, "relax": 0.3, "max_iter": 4000, "tol": 1e-8, "fb_gain": 8.0, "warmup": 40,
            "n_profile": 201, "n_q": 20, "n_theta": 121, "x_lo": 0.06, "x_hi": 0.995}
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
#: 同时交给几个工作进程（``--jobs``；1 = 串行，与旧版逐位相同）。每个工作进程自己载一份库（ctypes 句柄
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


# ================================================================================================ libfylite_kernel.so · libsp.so

class KernelError(RuntimeError):
    """库或它的门本身出错（不是物理上的拒绝）。"""


class Refused(RuntimeError):
    """内核按名拒绝了这一次计算（``record['refusal']``）。"""


_U8P = ctypes.POINTER(ctypes.c_uint8)


def _bytes(text: str):
    raw = text.encode("utf-8")
    buf = (ctypes.c_uint8 * max(len(raw), 1)).from_buffer_copy(raw + b"\0")
    return ctypes.cast(buf, _U8P), len(raw), buf


def kernel_identity(kpath: Path) -> dict:
    """算这些数的**内核是哪一份**，问内核库自己：版本（``fylite_rs_kernel_version``，内核自己的版本号）·
    ABI · 文件的 sha256。★2026-09-26 起内核与中间层是两份库、各自的版本号；中间层不再链内核，
    所以这一格不能再问中间层（``fylite_runtime_linked_kernel`` 在那里答空）。取不到的格留空，不编。"""
    import hashlib
    out: dict = {"lib": kpath.name}
    try:
        out["sha256"] = hashlib.sha256(Path(kpath).resolve().read_bytes()).hexdigest()
        k = ctypes.CDLL(str(kpath))
        k.fylite_rs_abi_version.restype = ctypes.c_uint32
        out["abi"] = int(k.fylite_rs_abi_version())
        fn = getattr(k, "fylite_rs_kernel_version", None)
        if fn is not None:
            fn.restype = ctypes.c_uint64
            fn.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
            buf = ctypes.create_string_buffer(64)
            n = int(fn(buf, 64))
            out["kernel_version"] = buf.raw[: min(n, 64)].decode("utf-8", "replace")
    except (OSError, AttributeError):
        pass
    return out


class Lib:
    """两份库的三扇门：内核文档门、装置事实（数据层）、mdsip 读（数据层）。``path`` 是内核 ``libfylite_kernel.so``；
    数据层 ``libsp.so`` 在它旁边。"""

    def __init__(self, path: Path):
        path = Path(path)
        if path.is_dir():
            path = path / KERNEL_LIB_NAME
        self.kernel_path = path
        self.path = path.parent / SP_LIB_NAME
        for p in (path, self.path):
            if not p.is_file():
                raise SystemExit(f"找不到 {p}：把 libfylite_kernel.so 与 libsp.so 放在 {HERE} 下，"
                                 "或用 --lib 指内核那一份（数据层在它旁边；取法见 README〈八 · 库与分发〉）")
        k = ctypes.CDLL(str(path))
        fn = getattr(k, "fylite_rs_fyo_json", None)
        if fn is None:
            raise SystemExit(f"{path.name} 没有文档门 fylite_rs_fyo_json（内核 ABI 161 之前的构建）——换一份新构建的库")
        fn.argtypes = [ctypes.c_char_p, ctypes.c_uint64] * 2 + [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint64)]
        fn.restype = ctypes.c_int32
        k.fylite_rs_free.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        k.fylite_rs_free.restype = None
        self._k = k
        self.door_name = "fylite_rs_fyo_json"
        L = ctypes.CDLL(str(self.path))
        L.sp_call.argtypes = [_U8P, ctypes.c_uint64, _U8P, ctypes.c_uint64]
        L.sp_call.restype = ctypes.c_void_p
        L.sp_result_status.argtypes = [ctypes.c_void_p]
        L.sp_result_status.restype = ctypes.c_int32
        for n in ("sp_result_json", "sp_result_error"):
            getattr(L, n).argtypes = [ctypes.c_void_p, _U8P, ctypes.c_uint64]
            getattr(L, n).restype = ctypes.c_uint64
        L.sp_result_array_count.argtypes = [ctypes.c_void_p]
        L.sp_result_array_count.restype = ctypes.c_uint32
        L.sp_result_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, _U8P, ctypes.c_uint64]
        L.sp_result_array.restype = ctypes.c_uint64
        L.sp_result_free.argtypes = [ctypes.c_void_p]
        L.sp_version.argtypes = [_U8P, ctypes.c_uint64]
        L.sp_version.restype = ctypes.c_uint64
        self.lib = L
        #: facts：本文件旁边的 ``facts/``（有就用）；否则由数据层按 ``$FY_FACTS_PATH`` / ``$SP_FACTS_PATH`` 找
        self.facts = [str(HERE / "facts")] if (HERE / "facts").is_dir() else None

    # ---- 数据层：一次调用（``sp_call``；大数组经旁路回来，放回原处成列表） ----
    @staticmethod
    def _text(fn, h) -> str:
        n = fn(h, None, 0)
        buf = (ctypes.c_uint8 * max(int(n), 1))()
        fn(h, ctypes.cast(buf, _U8P), n)
        return bytes(buf)[:int(n)].decode("utf-8", "replace")

    def call(self, op: str, req: dict):
        """数据层的一次调用 → 答案（数组放回成嵌套列表）。失败：请求本身不对 / 操作失败都抛 :class:`KernelError`。"""
        import struct
        if self.facts is not None and "facts" not in req:
            req = dict(req, facts=self.facts)
        ob, on, _k1 = _bytes(op)
        rb, rn, _k2 = _bytes(json.dumps(req, allow_nan=True))
        h = self.lib.sp_call(ob, on, rb, rn)
        try:
            st = int(self.lib.sp_result_status(h))
            if st != 0:
                raise KernelError(f"libsp {op}: {self._text(self.lib.sp_result_error, h)}")
            ans = json.loads(self._text(self.lib.sp_result_json, h) or "null")
            blobs = []
            for k in range(int(self.lib.sp_result_array_count(h))):
                size = int(self.lib.sp_result_array(h, k, None, 0))
                buf = (ctypes.c_uint8 * max(size, 1))()
                self.lib.sp_result_array(h, k, ctypes.cast(buf, _U8P), size)
                blobs.append(bytes(buf)[:size])
        finally:
            self.lib.sp_result_free(h)

        def back(n):
            if isinstance(n, dict):
                if "@array" in n and "dtype" in n and "shape" in n:
                    raw = blobs[int(n["@array"])]
                    flat = list(struct.unpack(f"<{len(raw) // 8}{'d' if n['dtype'] == 'f64' else 'q'}", raw))
                    shape = [int(d) for d in n["shape"]]
                    for d in reversed(shape[1:]):
                        flat = [flat[i:i + d] for i in range(0, len(flat), d)]
                    return flat
                return {k: back(v) for k, v in n.items()}
            if isinstance(n, list):
                return [back(v) for v in n]
            return n
        return back(ans) if blobs else ans

    # ---- 内核文档门 ----
    def _case(self, code: str, plan: dict) -> tuple[int, str]:
        """一次文档门：(返回码, 记录或拒绝的 JSON 文本)。返回码：0 记录 · 1 拒绝 · 负数 出错。"""
        cb = code.encode()
        jb = json.dumps(plan, allow_nan=True).encode()
        out, n = ctypes.c_void_p(), ctypes.c_uint64(0)
        rc = self._k.fylite_rs_fyo_json(cb, len(cb), jb, len(jb), ctypes.byref(out), ctypes.byref(n))
        try:
            text = ctypes.string_at(out, n.value).decode("utf-8", "replace") if out.value and n.value else ""
        finally:
            if out.value and n.value:
                self._k.fylite_rs_free(out, n)
        return int(rc), text

    def door(self, code: str, settings: dict, inputs: dict):
        """一份请求进、一份记录出：(facts{key: 数}, fields{key: 列表}, notes)。"""
        rc, text = self._case(code, {"settings": settings, "inputs": inputs})
        if rc < 0:
            raise KernelError(f"{code}: {self.door_name} 返回 {rc}：{text[:300]}")
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

    def kinetic(self, inputs: dict) -> tuple[dict, list]:
        """``code/kinetic``：整条约束阶梯在内核里跑，一份计划进、一份结果记录出 → (记录, 日志行)。
        内核按名拒绝（缺 TF、认不出的开关、输入文件里认不出的道 …）即 ``SystemExit``——与这些检查还在本应用里时同一种失败。"""
        rc, text = self._case("code/kinetic", {"settings": {}, "inputs": inputs})
        if rc < 0:
            raise KernelError(f"code/kinetic: {self.door_name} 返回 {rc}：{text[:300]}")
        rec = json.loads(text) if text else {}
        if rc == 1:
            ref = rec.get("refusal") or {}
            msg = str(ref.get("message", text[:300]))
            if "no code `kinetic`" in msg or "no code `code/kinetic`" in msg:
                raise SystemExit(f"{self.path.name} 没有 code/kinetic（2026-09-26 之前的库）——换一份新构建的库")
            raise SystemExit(msg)
        if "record" not in rec:
            raise KernelError("code/kinetic 没有交回 record（库太旧？）")
        return rec["record"], list(rec.get("notes") or [])

    def linked_kernel(self) -> dict:
        """算这些数的内核：问内核库自己（:func:`kernel_identity`）。"""
        return kernel_identity(self.kernel_path)

    def runtime_version(self) -> str | None:
        """数据层自己的版本号（``sp_version``：``<版本>+<提交>``；与内核的相互独立）。"""
        n = self.lib.sp_version(None, 0)
        buf = (ctypes.c_uint8 * max(int(n), 1))()
        self.lib.sp_version(ctypes.cast(buf, _U8P), n)
        return bytes(buf)[:int(n)].decode("utf-8", "replace")

    # ---- g-file：数据层的 G-EQDSK 读者（``read`` 带 ``raw``：与内核的 ``GFile`` 同样的字段） ----
    def gfile(self, text: str) -> dict:
        """一份 G-EQDSK 文本 → 字典（键名同内核的 ``GFile``：nw · nh · rdim … · psirz 平铺 · rbbbs …）。"""
        try:
            g = self.call("read", {"input": {"text": text, "format": "geqdsk"}, "raw": True})
        except KernelError as e:
            raise SystemExit(f"g-file 读不进来：{e}")
        return {k: (flat(v) if isinstance(v, list) else v) for k, v in g.items()}

    # ---- 装置：数据层的事实 + 解析规则 ----
    def device(self, device_id: str, shot: int, chain: str) -> tuple[dict, dict]:
        """(这一炮、这条测量链上的装置文档, 解析文档)。"""
        try:
            card = self.call("facts", {"doc": ["device", device_id]})
            res = self.call("facts", {"resolution": ["device", device_id]})
        except KernelError as e:
            try:
                have = self.call("facts", {"list": "device"}).get("ids")
            except KernelError:
                have = []
            raise SystemExit(f"facts 里没有装置 {device_id!r} 的卡片与解析文档（有：{have}）——把 EAST 的装置事实放进 "
                             f"{HERE / 'facts'}，或 export FY_FACTS_PATH=…（{e}）")
        try:
            out = self.call("resolve_device", {"card": card, "resolution": res, "shot": int(shot),
                                               "measurement_chain": chain, "strict": False, "form": "document"})
        except KernelError as e:
            raise SystemExit(f"装置解析：{e}")
        return out["document"], res

    # ---- mdsip：数据层的批量读 ----
    def mds_read_many(self, server: str, items: list, *, parallel: int = 8, timeout_s: float = 10.0) -> list:
        """一批只读 mdsip 读：每项 ``{tree, shot, verb, node, [index]}`` → ``{"value": …}`` 或 ``{"error": …}``；
        一个节点不在不会让整批失败。"""
        ans = self.call("mds_read_many", {"server": server, "items": items, "parallel": int(parallel),
                                          "user": os.environ.get("USER") or "fylite",
                                          "timeout_ms": int(timeout_s * 1000)})
        return ans["items"]

    def mds_open(self, host: str, port: int, timeout_s: float) -> "Mds":
        return Mds(self, host, port, timeout_s)


def flat(v) -> list:
    """嵌套列表 → 行主序的一维列表。"""
    if not isinstance(v, list):
        return [v]
    out = []
    for x in v:
        out.extend(flat(x)) if isinstance(x, list) else out.append(x)
    return out


def dims_of(v) -> list:
    """嵌套列表的形状，按线上约定**最快变化的轴在前**。"""
    shape = []
    while isinstance(v, list):
        shape.append(len(v))
        v = v[0] if v else None
    return list(reversed(shape))


class Mds:
    """一条只读 mdsip「会话」：服务器 · 树 · 炮号，逐个节点读（数据层的 ``mds_read_many``，每次一项；多项时用
    :meth:`Lib.mds_read_many` 成批读）。调用无状态——每一读都带上本会话记下的树与炮号，``close`` 无可放。"""

    def __init__(self, lib: Lib, host: str, port: int, timeout_s: float):
        self.lib, self.server, self.timeout_s = lib, f"{host}:{int(port)}", timeout_s
        self.tree, self.shot = None, None

    def open_tree(self, tree: str, shot: int) -> None:
        self.tree, self.shot = tree, int(shot)

    #: 下标里的「整条轴」（``*``）
    ALL = -(2 ** 63)

    def read(self, verb: str, node: str, sub=None):
        """(一维值, dims)；dims 按线上约定**最快变化的轴在前**。``sub``：对**值**取的整数下标
        （``data(\\X)[*,*,k]``；每一维一个整数或 ``Mds.ALL``）——大数组只取一片时用，节点路径与下标之外不拼任何 TDI。"""
        if self.tree is None:
            raise KernelError(f"read({verb!r}, {node!r})：还没有 open_tree")
        item = {"tree": self.tree, "shot": self.shot, "verb": verb, "node": node}
        if sub:
            item["index"] = ["*" if int(x) == self.ALL else int(x) for x in sub]
        (got,) = self.lib.mds_read_many(self.server, [item], parallel=1, timeout_s=self.timeout_s)
        if "error" in got:
            raise KernelError(f"read({verb!r}, {node!r}) returned an error: {got['error']}")
        v = got["value"]
        return [float(x) for x in flat(v)], dims_of(v)

    def rows(self, node: str) -> list:
        """二维节点按行（慢轴）取出：a[i][j]。★线上 dims 快轴在前，所以行长是 dims[0]。"""
        v, dims = self.read("data", node)
        if len(dims) < 2:
            return v
        w = dims[0]
        return [v[i * w:(i + 1) * w] for i in range(len(v) // w)]

    def close(self) -> None:
        pass


class _CachedMds:
    """One mdsip session shared by a whole batch that **remembers every answer** (``ShotCache``).

    Same interface as :class:`Mds` (``open_tree`` · ``read`` · ``rows`` · ``close``), so the pull functions run on
    it unchanged. ``open_tree`` only records which tree is wanted; the real one is opened on the first read that
    misses. A read's answer — or its ``KernelError`` — is kept by (tree, shot, verb, node, subscript), and a caller
    gets a copy, so what it does with the lists cannot leak into the next slice. ``close`` is a no-op: the session
    lives as long as the cache (FYL-REPORT-11 O-1a)."""

    def __init__(self, real: "Mds"):
        self.real, self.tree, self._shot, self._opened, self.memo = real, None, None, None, {}

    def open_tree(self, tree: str, shot: int) -> None:
        self.tree, self._shot = tree, int(shot)

    def read(self, verb: str, node: str, sub=None):
        key = (self.tree, self._shot, verb, node, tuple(int(x) for x in (sub or ())))
        if key not in self.memo:
            try:
                if self._opened != (self.tree, self._shot):
                    self.real.open_tree(self.tree, self._shot)
                    self._opened = (self.tree, self._shot)
                self.memo[key] = self.real.read(verb, node, sub)
            except KernelError as e:
                self._opened = None
                self.memo[key] = e
        got = self.memo[key]
        if isinstance(got, KernelError):
            raise got
        return list(got[0]), list(got[1])

    rows = Mds.rows

    def close(self) -> None:
        pass


class ShotCache:
    """Stands in for :class:`Lib` in the per-slice pulls of a batch (W_dia · sawtooth · Thomson): one shared,
    remembering mdsip session per server, and the device document resolved once per (device, shot, chain).

    ★★Why (FYL-REPORT-11 O-1a): a batch used to open a fresh session for each of those three pulls on every slice
    and re-read the same whole-shot arrays each time — about half of a slice's wall time on #164437. Every call the
    pulls make is the same call as before, answered from the first time it was made, so the measurement documents
    (and the records) are unchanged; only the repeat reads are gone. Everything else is :class:`Lib`'s."""

    def __init__(self, lib: "Lib"):
        self.lib, self.sessions, self.devices = lib, {}, {}

    def __getattr__(self, name):
        return getattr(self.lib, name)

    def device(self, device_id: str, shot: int, chain: str):
        key = (device_id, int(shot), chain)
        if key not in self.devices:
            self.devices[key] = self.lib.device(device_id, shot, chain)
        return copy.deepcopy(self.devices[key])

    def mds_open(self, host: str, port: int, timeout_s: float) -> _CachedMds:
        key = (host, int(port))
        if key not in self.sessions:
            self.sessions[key] = _CachedMds(self.lib.mds_open(host, port, timeout_s))
        return self.sessions[key]

    def close(self) -> None:
        for s in self.sessions.values():
            s.real.close()
        self.sessions.clear()


def server_of(spec: str | None) -> tuple[str, int]:
    s = spec or os.environ.get("FYLITE_MDSIP_SERVER")
    if not s or ":" not in s:
        raise SystemExit("取数要 mdsip 服务器：--server 主机:端口，或 export FYLITE_MDSIP_SERVER=主机:端口")
    h, p = s.rsplit(":", 1)
    return h, int(p)


# ================================================================================================ device names
#: ★★数据层标在各道上的取数规则（libsp ``resolve_device``；fyo FYO-ADR-17 的词），与中间层写过的旧拼法——读一个发布周期。
READ_MARKS = {"sign": ("fyo:reading_sign_factor", "fylite:sign"), "drop": ("fyo:excluded_channel", "fylite:drop"),
              "read_rule": ("fyo:applied_read_rule", "fylite:read_rule"),
              "geometry_was": ("fyo:original_geometry", "fylite:geometry_was"),
              "geometry_source": ("fyo:geometry_source", "fylite:geometry_source")}
#: fyo 的取数规则算子（``fyo:read_rule_operator/<名>``，SP-9 PR-5）→ 测量文档一直用的 op 名
_OP_NAMES = {"sign": "sign", "exclude_channel": "drop", "replace_geometry": "geometry"}


def _rule_value(k: str, v):
    """一个 ``ReadRuleApplication`` 字段换成测量文档自己的写法：算子 IRI 换成 op 名（``sign`` · ``drop`` ·
    ``geometry``，别的用 fyo 的名），开区间 ``[first]``（fyo KD-1）写回 ``[first, None]``。"""
    if k == "rule_operation" and isinstance(v, str):
        name = v.rsplit("/", 1)[-1]
        return _OP_NAMES.get(name, name)
    if k == "applied_shot_range" and isinstance(v, list) and len(v) == 1:
        return [v[0], None]
    return v


_RULE_FIELDS = {"read_rule_id": "id", "addressed_dataset": "ids", "rule_operation": "op",
                "reading_sign_factor": "factor", "addressed_quantity": "quantity", "rule_status": "status",
                "matched_channel": "channels", "absent_channel": "absent", "channel_without_data": "no_data",
                "applied_to_source": "source", "applied_shot_range": "applies_shots"}


def read_mark(c, name: str, default=None):
    """一道上的取数规则标记（``sign`` · ``drop`` · ``read_rule`` · ``geometry_was`` · ``geometry_source``），两种拼法都认。"""
    if not isinstance(c, dict):
        return default
    return next((c[k] for k in READ_MARKS[name] if k in c), default)


def _authored_deg(q):
    """书里写的角（fyo ``QuantityValue``）换成度：QUDT ``DEG`` 原样，``RAD`` 换算；没有单位是旧形（度）；别的单位不认（``None``）。"""
    if not isinstance(q, dict) or q.get("numeric_value") is None:
        return None
    v, u = q["numeric_value"], str(q.get("has_unit") or "")
    tail = u.rsplit("/", 1)[-1].rsplit(":", 1)[-1].upper()
    return v if tail in ("", "DEG") else math.degrees(v) if tail == "RAD" else None


def _geometry_values(g: dict) -> dict:
    """一道替换几何（fyo ``ChannelGeometryRecord``）→ 测量文档里的形：``r · z · poloidal_angle · poloidal_angle_deg ·
    source``；``poloidal_angle_deg`` 取书里写的原数（fyo ``authored_poloidal_angle``，按它的单位换成度）。"""
    pos = (g.get("position") or [{}])[0]
    e = {"r": pos.get("r"), "z": pos.get("z"), "poloidal_angle": g.get("poloidal_angle")}
    deg = _authored_deg(g.get("authored_poloidal_angle"))
    if deg is not None:
        e["poloidal_angle_deg"] = deg
    if "geometry_source" in g:
        e["source"] = g["geometry_source"]
    return e


def read_rules(doc: dict) -> list:
    """解析后的装置文档施加过的取数规则，逐条写成**测量文档**的形（``{id, ids, op, factor, quantity, applies_shots,
    status, channels, absent, no_data, source, values}``）——测量文档（含冻结的奇偶件）照旧是这个形。数据层按 fyo
    ``ReadRuleApplication`` 记（``provenance/fyo:provider_resolution/read_rule_application``）；旧的 ``read_rules`` 也认。"""
    prov = doc.get("provenance") or {}
    rec = prov.get("fyo:provider_resolution") or prov.get("fylite:resolution") or {}
    out = []
    for r in rec.get("read_rule_application") or []:
        m = {}
        for k, v in r.items():
            if k in _RULE_FIELDS:
                m[_RULE_FIELDS[k]] = _rule_value(k, v)
            elif k == "replacement_geometry":
                m["values"] = {g.get("channel_name"): _geometry_values(g) for g in v or []}
            elif not k.startswith("@"):
                m[k] = v
        out.append(m)
    out.extend(dict(r) for r in rec.get("read_rules") or [] if isinstance(r, dict))
    return out


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
    #: spdata SP-9 PR-6（fyo FYO-ADR-20）起解析文档是 T-Box 形：``embedded_manifest.measurement_chain_definition[]``
    #: （``chain_id`` · ``chain_kind`` · ``tree_name``）；旧形 ``manifest.measurement_chains`` 仍认
    man = resolution.get("embedded_manifest") or resolution.get("manifest") or {}
    if isinstance(man.get("measurement_chain_definition"), list):
        table = {c.get("chain_id"): {"kind": c.get("chain_kind"), "tree": c.get("tree_name")}
                 for c in man["measurement_chain_definition"] if isinstance(c, dict)}
    else:
        table = man.get("measurement_chains") or {}
    tree = (table.get(chain) or {}).get("tree")
    if not tree:
        raise SystemExit(f"测量链 {chain!r} 在解析文档里没有 tree（有：{sorted(table)}）")
    #: PF 通道：编进库里的文档形把线圈摊开了，通道那一层的事实（读哪个罗氏线圈节点、读数乘多少匝、
    #: 在拟合里排第几）记在 `pf_active/fylite:channel`；卡片形则直接写在通道线圈上。两种都认。
    coils = pf.get("fylite:channel") or [c for c in _aos(pf, "coil") if not _is_fast_coil(c)]
    need = [k for k in ("turns", "efit_index") if not all(k in c for c in coils)]
    if not coils or need:
        raise SystemExit(f"这份装置文档没有 PF 通道的 {need or '条目'}——取 PF 电流要它们；"
                         "要一份带 pf_active/fylite:channel 的 EAST 装置卡片（tools/abox-to-facts.py east，2026-09-18 之后）")
    mds = (doc.get("data_source") or {}).get("mdsplus") or {}
    itf, pol = doc.get("interferometer") or {}, doc.get("polarimeter") or {}
    gui = (doc.get("operational") or {}).get("gui_v5_fig") or {}
    probes = _aos(mag.get("b_field_pol_probe"))
    loops = _aos(mag.get("flux_loop"))
    #: ★取数规则（装置书 ``bindings.mdsplus.read_rules``，2026-09-25）：按炮解析的装置文档把覆盖本炮的
    #: ``sign`` / ``drop`` 规则**按道名**标在环上（``fylite:sign`` · ``fylite:drop`` · ``fylite:read_rule``，
    #: 运行时 ``read_rules.rs``），逐条记录在 ``provenance/fylite:resolution/read_rules``。归约时乘上符号，
    #: 丢弃的环在拟合里权为 0（``Case``）。
    rules = [r for r in read_rules(doc) if r.get("op") in ("sign", "drop", "geometry")]
    return {
        "chain": chain, "tree": tree, "pcs_tree": mds.get("pcs_tree"), "ip_node": mds.get("ip_node"),
        "loops": [c["name"] for c in loops],
        "loop_sign": [float(read_mark(c, "sign", 1.0)) for c in loops],
        "loop_drop": [bool(read_mark(c, "drop")) for c in loops],
        "read_rules": rules,
        "probes": [c["name"] for c in probes],
        "probe_weights": ([float(c["weight"]) for c in probes]
                          if probes and all(isinstance(c, dict) and "weight" in c for c in probes) else None),
        "probe_drop": [bool(read_mark(c, "drop")) for c in probes],
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

    #: 取数规则：环读数乘上它的符号（``fylite:sign``）；丢弃的环照读（不在也不算缺），拟合里权为 0（``Case``）
    sign = names.get("loop_sign") or [1.0] * len(names["loops"])
    drop = names.get("loop_drop") or [False] * len(names["loops"])
    coils = []
    for i, nd in enumerate(names["loops"]):
        v = avg(nd, tree, 1.0 / (2.0 * math.pi), required=not drop[i])
        coils.append(0.0 if v is None else v * sign[i])
    expmp2, fwtmp2 = [], []
    pdrop = names.get("probe_drop") or [False] * len(names["probes"])
    for i, nd in enumerate(names["probes"]):
        v = avg(nd, tree, required=False)
        expmp2.append(0.0 if v is None else v)
        #: 取数规则 drop 的探针：照读，权为 0（``Case`` 另记进 ``excluded``）
        fwtmp2.append(0.0 if (v is None or pdrop[i]) else (names["probe_weights"][i] if names["probe_weights"] else 1.0))
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
            "probe_weight_rule": "device" if names["probe_weights"] else "unit", "source": source,
            #: 施加了哪几条取数规则（逐条：id · op · factor · 道名）；没有覆盖本炮的规则时为空表
            "read_rules": [dict(r) for r in names.get("read_rules") or []]}

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


#: mdsip sessions a whole-shot magnetics prefetch reads over (``$EKR_FETCH_WORKERS``): 8 measured best on the EAST
#: server (#164437, 190 nodes: 1 → 60.6 s · 4 → 33.7 s · 8 → 26.9 s · 16 → 40.5 s)
FETCH_WORKERS = 8


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
        self.lib, self.host, self.port, self.timeout_s = lib, host, port, timeout_s
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

    def prefetch(self, point: bool = False, workers: int | None = None) -> None:
        """把归约可能读的节点全读进缓存：环 · 探针 · PF · Ip（+ PCS 树的回退 Ip）· TF（+ 旧炮的 ``btor_node``）；
        ``point`` 时另读 POINT 的弦（每条几百万个采样——档 M 用不到，``series`` 不读）。
        ★★``workers`` 条会话**并行**读（缺省 ``FETCH_WORKERS``，``$EKR_FETCH_WORKERS`` 改；1 = 原来的单会话逐个读）。
        各会话各读一份节点，答案按与 ``get`` 相同的键进同一个缓存，所以缓存的内容与逐个读的逐位相同，只是快
        （FYL-REPORT-11 O-1：#164437 连 POINT 190 个节点 60.6 s → 8 路 26.9 s；16 路反而 40.5 s，服务器那一端先饱和）。"""
        n = self.names
        todo = [(nd, n["tree"]) for nd in n["loops"] + n["probes"] + n["pf_nodes"] + [n["ip_node"]] if nd]
        if n["pcs_tree"]:
            todo.append((r"\pcrl01", n["pcs_tree"]))
        todo.append((TF_NODE, n["tree"]))
        if point:
            todo += [(nd, n["tree"]) for nd in list(n["point_ne"] or []) + list(n["point_fr"] or [])]
        w = int(os.environ.get("EKR_FETCH_WORKERS") or workers or FETCH_WORKERS)
        todo = [(nd, where) for nd, where in todo if (where, nd if nd.startswith("\\") else "\\" + nd) not in self.cache]
        if w > 1 and len(todo) > 1:
            self._fetch_parallel(todo, min(w, len(todo)))
        else:
            for nd, where in todo:
                self.get(nd, where)
        if self.get(TF_NODE, n["tree"]) is None and self.mds.get("btor_node"):
            self.get(self.mds["btor_node"], n["tree"])

    def _fetch_parallel(self, todo: list, w: int) -> None:
        """``todo`` 一批读完（数据层的 ``mds_read_many``，``w`` 条连接并行），答案进 ``self.cache``。"""
        t0 = time.time()
        items, keys = [], []
        for nd, where in todo:
            key = (where, nd if nd.startswith("\\") else "\\" + nd)
            keys.append(key)
            for verb in ("data", "dim_of"):
                items.append({"tree": where, "shot": int(self.shot), "verb": verb, "node": key[1]})
        got = self.lib.mds_read_many(f"{self.host}:{int(self.port)}", items, parallel=w, timeout_s=self.timeout_s)
        for n, key in enumerate(keys):
            d, t = got[2 * n], got[2 * n + 1]
            #: 节点不在：是数据，不是故障（同 ``get``）
            self.cache[key] = None if ("error" in d or "error" in t) else (
                [float(x) for x in flat(d["value"])], [float(x) for x in flat(t["value"])])
        self.fetch_s += time.time() - t0

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
        #: ★prefetch in parallel, then reduce: the same nodes, the same answers (the class's own guarantee), faster
        src.prefetch(point=True)
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
        if doc["measurements"] is not None:              #: 实测逆磁储能（档 D 用；compare 同一个 ±10 ms 窗）
            try:
                wd, wsrc = pull_w_dia(lib, a.shot, a.time, a.chain, a.server, a.timeout)
                doc["measurements"].update(w_dia_J=wd, w_dia_source=wsrc)
                log(f"W_dia: {'—' if wd is None else f'{wd / 1e3:.1f} kJ'} ({wsrc.get('node', wsrc.get('why'))})")
            except Exception as e:                       # noqa: BLE001 — 取不到只记下，不影响磁测量
                doc["errors"]["w_dia"] = sanitize(str(e))[:200]
                log(f"W_dia FAILED: {doc['errors']['w_dia']}")
        if doc["measurements"] is not None and not a.no_sawtooth:   #: 锯齿校验用：ECE 整阵 + SXR 触发弦的 t ± 0.3 s 窗
            import kinetic_sawtooth
            t0 = time.time()
            try:
                saw = kinetic_sawtooth.pull_sawtooth(lib, a.shot, a.time, a.chain, a.server, a.timeout)
                doc["measurements"]["sawtooth"] = saw
                log(f"sawtooth window: ECE {len((saw.get('ece') or {}).get('t') or [])} × {len((saw.get('ece') or {}).get('r') or [])}"
                    f"{' (' + saw['ece']['why'] + ')' if 'why' in (saw.get('ece') or {}) else ''}, "
                    f"SXR {len((saw.get('sxr') or {}).get('t') or [])} bins"
                    f"{' (' + saw['sxr']['why'] + ')' if 'why' in (saw.get('sxr') or {}) else ''} ({time.time() - t0:.1f} s)")
            except Exception as e:                       # noqa: BLE001
                doc["errors"]["sawtooth"] = sanitize(str(e))[:300]
                log(f"sawtooth FAILED: {doc['errors']['sawtooth']}")
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
        raise SystemExit("装置文档里没有 equilibrium/fylite:signal（这份装置卡片早于 fydoc 的平衡绑定）——"
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
        w_dia = None
        try:
            w_dia = read_w_dia(s, doc, shot, t, signals)[0]
        except KernelError as err:
            errors["w_dia"] = sanitize(str(err))[:200]
    finally:
        s.close()
    return w_dia


#: 实测逆磁储能取 ±10 ms 均值（compare · pull · 档 D 同一个窗）
W_DIA_HALF_S = 0.010


def read_w_dia(s: "Mds", doc: dict, shot: int, t: float, signals: str | None = None) -> tuple:
    """实测逆磁储能（装置文档 magnetics/fylite:signal 的 w_dia，或 ``signals`` 节点名表里的）在 t ± 10 ms 的均值 × scale。
    返回 (W_dia [J] 或 None, 出处 {tree, node, window_s, n_samples})；节点名缺 / 窗里没数 / 整条为零 → None。
    树打不开、节点读不出抛 ``KernelError``（调用方记进取不到）。"""
    m = ((doc.get("magnetics") or {}).get("fylite:signal") or {}).get("w_dia") or (
        json.loads(Path(signals).read_text(encoding="utf-8")).get("magnetics", {}).get("fylite:signal", {})
        .get("w_dia") if signals else None)
    if not m:
        return None, {"why": "装置文档没有 w_dia 节点名"}
    s.tree = None
    s.open_tree(m["tree"], shot)
    v, tbw = s.read("data", m["node"])[0], s.read("dim_of", m["node"])[0]
    sel = [v[i] for i in range(min(len(v), len(tbw))) if abs(tbw[i] - t) <= W_DIA_HALF_S]
    src = {"tree": m["tree"], "node": m["node"], "window_s": _r([t - W_DIA_HALF_S, t + W_DIA_HALF_S], 9), "n_samples": len(sel)}
    if not (sel and any(v)):
        return None, dict(src, why="窗里没有采样，或整条为零")
    return mean(sel) * m.get("scale", 1.0), src


def pull_w_dia(lib: "Lib", shot: int, t: float, chain: str, server, timeout_s: float) -> tuple:
    """``pull`` 用：自己开一条 mdsip 会话读 ``read_w_dia``（装置文档按炮、测量链解析）。"""
    doc, _ = lib.device("east", shot, chain)
    host, port = server_of(server)
    s = lib.mds_open(host, port, timeout_s)
    try:
        return read_w_dia(s, doc, shot, t)
    finally:
        s.close()


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
           "unavailable": errors, "measured": {"w_dia_J": w_dia, **({"w_dia_in_result_J": (res.get("inputs") or {})["w_dia_J"]}
                                                    if (res.get("inputs") or {}).get("w_dia_J") is not None else {})},
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
    wr = (out.get("measured") or {}).get("w_dia_in_result_J")
    print(f"  实测逆磁储能 W_dia：{f(None if wd is None else wd / 1e3, 1)} kJ"
          + ("" if wr is None else f"（结果里档 D 用的 {wr / 1e3:.1f} kJ；档 D 假定各向同性热压、只定压强标度）"))
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


def load_profiles(path: str | None, input_path: str | None = None) -> dict | None:
    """动理学剖面（``fylite:KineticProfiles``，README §2.4d）：``--profiles`` 给的文件，否则测量文档自带的 ``profiles`` 块。
    文件可以是整份文档（有 ``profiles`` 键）或裸的 ``{species: …}``。没有就 ``None``（档 P 照旧走 Thomson / k-file）。"""
    for src in (path, input_path):
        if not src:
            continue
        d = json.loads(Path(src).read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("profiles"), dict):
            return d["profiles"]
        if src == path:
            if not (isinstance(d, dict) and isinstance(d.get("species"), dict)):
                raise SystemExit(f"{src}：不是动理学剖面文件（没有 species 块，见 README §2.4d）")
            return d
    return None


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




MU0 = 4e-7 * math.pi














# ================================================================================================ ladder annotation






# ================================================================================================ physics check












# ================================================================================================ parallel doors













# ================================================================================================ tiers













def _eq_doc(fa, fi):
    return {"time_slice": {"profiles_2d": {"psi": fi["psi"]},
                           "global_quantities": {"psi_axis": [fa["psi_axis"]], "psi_boundary": [fa["psi_bnd"]]}}}




































# ================================================================================================ tier D
#: ★档 D（2026-09-25）：Thomson 不能用（#164437：n_e 未标定、读成负的）时档 P 做不成，档 M / K 的几何与 q 对、储能却比
#: 实测逆磁储能高 18–27 %。档 D 把**一个标量**——实测逆磁储能 W_dia——当压强的标度约束：取底档（K 跑了取 K，否则 M）的
#: p(ψ_N)，乘 λ 使同尺 W = 3/2∫p dV（``map_integrals``，compare 的同一把尺）等于 W_dia，作 ψ_N 均匀格上的压强行
#: （``fylite:pressure`` + ``fylite:pressure_x``，同档 P 的 ψ_N 路）进反演；解出的平衡改了 V(ψ) 与 p，外环再标定、再解，
#: 直到相邻两遍的 W 差 < tol × W_dia 或跑满遍数。
#: ★行的 σ：所有行共用一个绝对 σ = σ_rel × ‖p_行‖₂（缺省 σ_rel = 1 %，2026-09-25 用户裁定「用 W_dia 作压强约束」：
#: 10 % 时一个标量敌不过 ~150 道磁测量，#164437 6.72 s 上 W 只由 308 降到 300 kJ、等于没约束；1 % 时 W 收到 W_dia，
#: q0 · q95 · β_p · 边界与 MSE 约束的平衡一致，代价是磁 χ² 增大——结果里照记）。这样整组行对「把目标整体
#: 乘 μ」的 χ² 恰为 (μ − 1)² / σ_rel²——合起来只相当于**一个** σ_rel 的标度测量，不是 N 个独立测点，不钉形状。
#: ★假定：W_dia 量的是垂直能量 3/2∫p_⊥ dV；没有快离子与各向异性的信息，本档当作各向同性的热压 W = 3/2∫p dV 用。
#: 只约束压强的标度、不约束形状（形状取自底档、逐遍沿用解出的）。它是 Thomson 不可用时档 P 的替代；P 能跑时以 P 为准。
WDIA_SIGMA = 0.01
WDIA_PASSES = 6
WDIA_TOL = 0.01
#: 档 D 外环的阻尼 α：整步来回振荡后 λ 改按 W̃ ← W̃^(1−α)·W^α 定；1 = 不阻尼
WDIA_RELAX = 1.0










# ================================================================================================ run





def add_scan_args(p, default: str) -> None:
    p.add_argument("--scan", choices=("full", "coarse"), default=default,
                   help="档 M 竖直设定点扫描：full 全部在 65² 上解；coarse 先在粗网格上扫、只把最好的几个在 65² 上复核"
                        f"（缺省 {default}）")
    p.add_argument("--scan-grid", type=int, default=33, help="coarse 的粗网格边长（缺省 33）")
    p.add_argument("--scan-top", type=int, default=4, help="coarse 在 65² 上复核几个设定点（缺省 4）")
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
        if k not in vars(a) or k in ("cmd", "lib", "input", "out", "time", "thomson", "profiles"):
            raise TypeError(f"run_options: no such option {k!r} (see `kinetic_recon.py run --help`)")
        setattr(a, k, v)
    return a


#: ``run`` 的开关里交给内核的那些（其余是本应用自己的：库路径、输入输出文件、时刻）
KERNEL_OPTIONS = ("anderson", "curv", "dead_sigma", "efit_fit", "efit_override", "efit_parts", "fvac", "jobs",
                  "kinetic_passes", "kinetic_tol", "loops", "max_rounds", "nff", "nk", "npp", "p_fast_frac", "p_on",
                  "p_basis", "p_knots", "p_tension", "p_edge", "per_round", "phys_bounds", "physics_check", "physics_select", "point_off", "psin_max", "reject_sigma",
                  "scan", "scan_grid", "scan_top", "sigma_floor", "sigma_scales", "thomson_clean", "thomson_clean_opts",
                  "thomson_clip", "tiers", "wdia", "wdia_passes", "wdia_relax", "wdia_sigma", "wdia_tol")


def reconstruct(meas: dict, thomson: dict | None = None, *, lib: "Lib | None" = None, origin: dict | None = None,
                kinetic_input: dict | None = None, kernel_options: dict | None = None, profiles: dict | None = None,
                **options) -> dict:
    """``run`` 的进程内形：平坦测量字典（``pull_magnetics`` 的返回值 = 测量文档的 ``measurements`` 块）
    + 可选的 Thomson 块（``pull_thomson`` 的返回值）→ 结果字典（与 ``run -o`` 写出的 JSON 同一份，见 README §4.4）。
    ``options`` 同 :func:`run_options`；``lib`` 缺省载本文件旁的 ``libfylite_kernel.so``（数据层 ``libsp.so`` 在它旁边）。
    ★★2026-09-26 起整条约束阶梯在**内核**里（``code/kinetic``，用户裁定「收敛动理学平衡重构进 rust 内核」）：本函数只装
    一份计划（装置文档 · 测量 · Thomson · 开关 · 输入文件）交给库，再添上本应用自己的几行（何时跑的、哪份库、数据从哪来）。
    档 M 一个设定点都不收敛时不抛：``tiers["M"]["status"] == "error"``（K / P 不跑）；K、P 的失败同样记在各自的 ``status`` 里。
    物理校验（缺省开，``physics_check=False`` 关）没过的档 ``status == "unphysical"``，数照留（README §3.9）。
    ``profiles``：动理学剖面（Tₑ · nₑ · T_i · v_tor 各自的诊断与坐标，README §2.4d）→ 档 P 由它们构压强，优先于 Thomson。
    ``kinetic_input``：规范化过的输入文件（``kinetic_input.normalize``）→ 档 X。``kernel_options``：``run`` 没有的内核开关
    （``zc_scan`` · ``readmit`` · ``warm_rejected`` · ``warm_readmitted`` · ``keep_solve``，``wei2026`` 的逐片热启动用）。"""
    a = run_options(**options)
    lib = lib or Lib(DEFAULT_LIB)
    origin = dict(origin or {"kind": "in-process"})
    shot, t = int(meas["shot"]), float(meas["time_s"])
    chain = meas.get("measurement_chain", "east")
    card, _ = lib.device("east", shot, chain)
    t0 = time.time()
    opts = dict({k: getattr(a, k) for k in KERNEL_OPTIONS}, **(kernel_options or {}))
    inputs = {"device": card, "measurements": meas, "options": opts}
    if thomson is not None:
        inputs["thomson"] = thomson
    if kinetic_input is not None:
        inputs["kinetic_input"] = kinetic_input
    if profiles is not None:
        inputs["profiles"] = profiles
    rec, notes = lib.kinetic(inputs)
    for line in notes:
        log(line)
    k = lib.linked_kernel()
    out = {"@type": rec.pop("@type", "fylite:KineticReconResult"), "app": APP, "version": VERSION,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "shot": rec.pop("shot", shot), "time_s": rec.pop("time_s", t),
           "measurement_chain": rec.pop("measurement_chain", chain), "origin": origin,
           "source": sanitize(meas.get("source")),
           "fylite": {"version": k.get("kernel_version") or k.get("version"), "kernel_abi": k.get("abi"),
                      "runtime_version": lib.runtime_version(), "library": lib.path.name, "kernel_built": k.get("built"), "kernel_sha256": k.get("sha256"),
                      "rustc": (k.get("toolchain") or {}).get("rustc")}}
    out.update(rec)
    out["seconds"] = round(time.time() - t0, 1)
    return out


def cmd_run(a) -> int:
    meas, th, origin = load_input(a.input, a.time, a.thomson)
    opts = {k: v for k, v in vars(a).items() if k not in ("cmd", "lib", "input", "out", "time", "thomson", "profiles")}
    prof = load_profiles(a.profiles, a.input)
    if prof is not None:
        origin["profiles"] = Path(a.profiles).name if a.profiles else "input"
        log(f"动理学剖面：{', '.join(sorted(prof.get('species') or {}))} → 档 P 由剖面构压强（不用 Thomson 块）")
    out = reconstruct(meas, th, lib=Lib(Path(a.lib) if a.lib else DEFAULT_LIB), origin=origin, profiles=prof, **opts)
    m_view = out["tiers"]["M"]
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    cv = out.get("fylite:convergence") or {}
    if cv.get("status") == "not_converged":
        mv = cv.get("moves") or {}
        log(f"★★外环未收敛（档 {cv.get('tier')}，{cv.get('reason')}）：末遍移动 ψ_N {mv.get('psin')} · "
            f"j_bs {mv.get('j_bs')} · p_fast {mv.get('p_fast')}——交出的是末遍，不自洽")
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
    out["_physics"] = {k: v for k, v in (res.get("physics_check") or {}).items() if k in ("bounds", "note")}
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
    return series_slice(_SERIES_WORKER["lib"], *args)


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
    phys = next((s_.get("_physics") for s_ in slices if s_.get("_physics")), None) or {}
    for s_ in slices:
        s_.pop("_limiter", None)
        s_.pop("_physics", None)
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
           "physics_check": ({"enabled": True, "select": bool(ro.physics_select), "bounds": phys.get("bounds"),
                              "note": (phys.get("note") or "") + "序列：unphysical 的片数照留、照画，不进 summary 的均值 / rms（summary.unphysical 记几片、哪几条）。"}
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
    ap.add_argument("--lib", help=f"libfylite_kernel.so 的路径，数据层 libsp.so 在它旁边（缺省 {DEFAULT_LIB.name}，与本文件同目录）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull", help="取数：原始树 + Thomson → 测量文档")
    p.add_argument("--shot", type=int, required=True)
    p.add_argument("--time", type=float, required=True, help="时刻 [s]")
    p.add_argument("--chain", default="east", help="测量链（缺省 east）")
    p.add_argument("--server", help="mdsip 服务器 主机:端口（缺省 $FYLITE_MDSIP_SERVER）")
    p.add_argument("--timeout", type=float, default=120.0, help="mdsip 读超时 [s]（east 树打开可能要一分钟）")
    p.add_argument("--no-thomson", action="store_true")
    p.add_argument("--thomson-only", action="store_true", help="只取 Thomson（与已有的磁测量件配合用）")
    p.add_argument("--no-sawtooth", action="store_true", help="不取锯齿校验用的 ECE 与 SXR 窗（缺省取：t ± 0.3 s）")
    p.add_argument("--ts-max-dt", type=float, default=TS_MAX_DT,
                   help=f"Thomson 脉冲离 --time 最远几秒还收（缺省 {TS_MAX_DT}；更远就拒，不当这一片的测量）")
    p.add_argument("-o", "--out", required=True)
    sub.add_parser("init", help="配置文件 v2：写一份全部缺省键的配置（kinetic_recon.py init --help）", add_help=False)
    sub.add_parser("validate", help="配置文件 v2：重写 out/<炮号> 每片的 validation.json（validate --help）", add_help=False)
    r = sub.add_parser("run", help="反演：测量文档 → 结果 JSON；给配置文件（fylite:KineticReconInput）则按片 × 阶梯批量跑"
                                   "（run <配置> --help）")
    r.add_argument("input", help="pull 的输出 · 原始树归约件 raw_slices_*.json · 或裸测量字典")
    r.add_argument("--time", type=float, help="归约件里取哪一片（取最近）")
    r.add_argument("--thomson", help="另给的 Thomson（pull --thomson-only 的输出）")
    r.add_argument("--profiles", help="动理学剖面文件（kinetic_profiles.py 生成；Tₑ · nₑ · T_i · v_tor 各自的诊断与坐标）："
                                      "档 P 由它们构压强，不用 Thomson 块（README §2.4d）")
    r.add_argument("--tiers", default="MKP", help="跑哪几档（缺省 MKP；M 总是跑；D = 逆磁储能定压强标度，Q = 锯齿反转半径定 q=1 面，点名才跑）")
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
    r.add_argument("--p-basis", choices=("auto", "spline", "spline_p", "poly"), default="auto",
                   help="档 P（--profiles）的 p′ · FF′ 基：auto / spline（缺省：两者张力样条 → 拒则 p′ 样条 + FF′ 多项式 → "
                        "再拒则多项式，逐级记明）· spline_p（只 p′ 样条）· poly（README §2.4d）")
    r.add_argument("--p-knots", type=lambda s: [float(x) for x in s.split(",")], default=[0.0, 0.5, 1.0],
                   metavar="0,0.5,1", help="样条结点（ψ_N，0 起 1 止，缺省 0,0.5,1——五结点在 #164437 上都被内核拒）")
    r.add_argument("--p-tension", type=float, default=10.0, help="样条张力（按平均结点间距标定，缺省 10）")
    r.add_argument("--p-edge", choices=("free", "zero"), default="free", help="样条在 ψ_N = 1 处：free（缺省）· zero")
    r.add_argument("--p-on", choices=("M", "K"), default="M",
                   help="档 P 叠在哪一档上：M（缺省，外环照常）· K（叠 POINT 行；外环在那一档不重映，只跑一遍）")
    add_phys_args(r)
    r.add_argument("--wdia", type=float, default=None, metavar="J",
                   help="档 D 用的实测逆磁储能 [J]（缺省取测量文档的 measurements.w_dia_J，pull 时取的 ±10 ms 均值）")
    r.add_argument("--wdia-sigma", type=float, default=WDIA_SIGMA,
                   help=f"W_dia 的相对不确定度：档 D 全部压强行合起来的标度 σ（缺省 {WDIA_SIGMA:g}）")
    r.add_argument("--wdia-passes", type=int, default=WDIA_PASSES, help=f"档 D 外环最多几遍（缺省 {WDIA_PASSES}）")
    r.add_argument("--wdia-tol", type=float, default=WDIA_TOL,
                   help=f"档 D 外环停止：相邻两遍同尺 W 之差 < tol × W_dia（缺省 {WDIA_TOL:g}）")
    r.add_argument("--wdia-relax", type=float, default=WDIA_RELAX, metavar="ALPHA",
                   help=f"档 D 外环的阻尼 α ∈ (0, 1]：整步来回振荡（ΔW 变号且缩不到一半）起，λ = W_dia / W̃，"
                        f"W̃ ← W̃^(1−α)·W^α；自行收敛的外环不受影响，收敛点不动（缺省 {WDIA_RELAX:g} = 不阻尼）")
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
    import kinetic_config                                #: 配置文件 v2：init · validate · run <配置>（kinetic_config.py）
    routed = kinetic_config.route(sys.argv[1:] if argv is None else argv)
    if routed is not None:
        return routed
    a = _parser().parse_args(argv)
    return {"pull": cmd_pull, "kfile": cmd_kfile, "run": cmd_run, "compare": cmd_compare, "series": cmd_series}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
