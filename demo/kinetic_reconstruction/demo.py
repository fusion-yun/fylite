#!/usr/bin/env python3
"""One-file native CLI and local HTTP host. Rust performs every inverse solve."""
import argparse, ctypes, hashlib, json, math, time, uuid, threading
import bisect, concurrent.futures, copy, itertools, operator, os, re, sys

from pathlib import Path
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
ROOT = Path(__file__).resolve().parent
LIB_SHA = '84d31c8d19aae055810f32d38d896e1a2b00ef6f25b73bea619bb9f8c1454be2'
TABLES = ['input/tables/ec129129.ddd', 'input/tables/ep129129.ddd', 'input/tables/rfcoil.ddd']
# Data host consolidated from apps/east-kinetic-reconstruction/kinetic_recon.py.
APP = "east-kinetic-reconstruction"
VERSION = "0.3.1"
#: ★★两份库、各自的版本号，放在同一处：内核 ``libfylite_kernel.so``（物理，文档门）与数据层 ``libsp.so``（spdata：
#: 装置事实 · 解析 · mdsip · g-file）。2026-09-26..27 数据层是 ``libfylite_runtime.so``。
KERNEL_LIB_NAME = "libfylite.so"
SP_LIB_NAME = "libsp.so"
DEFAULT_LIB = ROOT / KERNEL_LIB_NAME

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
                raise ValueError(f"找不到 {p}：把 libfylite_kernel.so 与 libsp.so 放在 {ROOT} 下，"
                                 "或用 --lib 指内核那一份（数据层在它旁边；取法见 README〈八 · 库与分发〉）")
        k = ctypes.CDLL(str(path))
        fn = getattr(k, "fylite_rs_fyo_json", None)
        if fn is None:
            raise ValueError(f"{path.name} 没有文档门 fylite_rs_fyo_json（内核 ABI 161 之前的构建）——换一份新构建的库")
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
        self.facts = [str(ROOT / "facts")] if (ROOT / "facts").is_dir() else None

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
                raise ValueError(f"{self.path.name} 没有 code/kinetic（2026-09-26 之前的库）——换一份新构建的库")
            raise ValueError(msg)
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
            raise ValueError(f"g-file 读不进来：{e}")
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
            raise ValueError(f"facts 里没有装置 {device_id!r} 的卡片与解析文档（有：{have}）——把 EAST 的装置事实放进 "
                             f"{ROOT / 'facts'}，或 export FY_FACTS_PATH=…（{e}）")
        try:
            out = self.call("resolve_device", {"card": card, "resolution": res, "shot": int(shot),
                                               "measurement_chain": chain, "strict": False, "form": "document"})
        except KernelError as e:
            raise ValueError(f"装置解析：{e}")
        return out["document"], res

    # ---- mdsip：数据层的批量读 ----
    def mds_read_many(self, server: str, items: list, *, parallel: int = 8, timeout_s: float = 10.0) -> list:
        """一批只读 mdsip 读：每项 ``{tree, shot, verb, node, [index]}`` → ``{"value": …}`` 或 ``{"error": …}``；
        一个节点不在不会让整批失败。"""
        ans = self.call("mds_read_many", {"server": server, "items": items, "parallel": int(parallel),
                                          "user": os.environ.get("FYLITE_MDS_USER") or os.environ.get("USER") or "fylite",
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
    s = spec or os.environ.get("FYLITE_MDSIP_SERVER") or "202.127.204.12:8000"
    if not s or ":" not in s:
        raise ValueError("取数要 mdsip 服务器：--server 主机:端口，或 export FYLITE_MDSIP_SERVER=主机:端口")
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
        raise ValueError(f"测量链 {chain!r} 在解析文档里没有 tree（有：{sorted(table)}）")
    #: PF 通道：编进库里的文档形把线圈摊开了，通道那一层的事实（读哪个罗氏线圈节点、读数乘多少匝、
    #: 在拟合里排第几）记在 `pf_active/fylite:channel`；卡片形则直接写在通道线圈上。两种都认。
    coils = pf.get("fylite:channel") or [c for c in _aos(pf, "coil") if not _is_fast_coil(c)]
    need = [k for k in ("turns", "efit_index") if not all(k in c for c in coils)]
    if not coils or need:
        raise ValueError(f"这份装置文档没有 PF 通道的 {need or '条目'}——取 PF 电流要它们；"
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
            raise ValueError(f"{leaf}: no samples within the requested time window")
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



def geometry_from_efit(r,z,w,h,a=0.,a2=90.):
    values=(r,z,w,h,a,a2)
    if any(not math.isfinite(v) for v in values) or w<=0 or h<=0:
        raise ValueError('EFIT geometry requires finite coordinates/angles and positive extents')
    # Match kernels::element_filaments, including its original branch and
    # small-sine rule. AF2 is inactive in the AF1 shear branch.
    if a!=0:
        u=(w,w*math.tan(a*math.pi/180));v=(0.,h)
    elif a2!=90:
        c,s=math.cos(a2*math.pi/180),math.sin(a2*math.pi/180)
        u=(w,0.);v=(h*(0. if abs(s)<1e-6 else c/s),h)
    else:u=(w,0.);v=(0.,h)
    if not all(math.isfinite(x) for x in (*u,*v)):
        raise ValueError('EFIT geometry produces a nonfinite edge')
    if u[1]==0 and v[0]==0:
        return dict(geometry_type=2,rectangle=dict(r=r,z=z,width=w,height=h))
    return dict(geometry_type=3,oblique=dict(r=r-.5*(u[0]+v[0]),z=z-.5*(u[1]+v[1]),
        length_alpha=math.hypot(*u),length_beta=math.hypot(*v),
        alpha=math.atan2(u[1],u[0]),beta=math.atan2(-v[0],v[1])))


def stage_geometry(document,unit_angles='reject'):
    device=copy.deepcopy(document);changes=[]
    def elements(parent,path):
        inherited={k:parent[k] for k in ('fylite:a1','fylite:a2') if k in parent}
        if inherited and unit_angles!='inherit':
            raise ValueError(path+': unit angles require explicit unit_angles=inherit; old consumers disagreed')
        for index,element in enumerate(parent.get('element',[])):
            geometry=element.get('geometry',{})
            angles={k:element.get(k,inherited.get(k,d)) for k,d in [('fylite:a1',0.),('fylite:a2',90.)]}
            old=geometry.get('rectangle')
            if old is None:
                if any(k in element for k in angles) or inherited:
                    raise ValueError(path+': legacy angles require the original rectangle coordinates')
                continue
            if 'oblique' in geometry:raise ValueError(path+': ambiguous rectangle and oblique')
            new=geometry_from_efit(*(old[k] for k in ('r','z','width','height')),angles['fylite:a1'],angles['fylite:a2'])
            # Preserve unrelated geometry attributes and element metadata.
            extras={k:v for k,v in geometry.items() if k not in ('rectangle','geometry_type')}
            element['geometry']={**extras,**new}
            for k in angles:element.pop(k,None)
            changes.append(dict(path=path+f'/element/{index}',source_rectangle=old,source_angles=angles,
                unit_angles_inherited=bool(inherited),geometry_type=new['geometry_type'],
                AF2_inactive_in_original_kernel=angles['fylite:a1']!=0 and angles['fylite:a2']!=90))
        for k in inherited:parent.pop(k)
    for i,coil in enumerate(device.get('pf_active',{}).get('coil',[])):elements(coil,f'pf_active/coil/{i}')
    slices=device.get('wall',{}).get('description_2d',[])
    if isinstance(slices,dict):slices=[slices]
    for i,slice in enumerate(slices):
        for j,unit in enumerate(slice.get('vessel',{}).get('unit',[])):elements(unit,f'wall/description_2d/{i}/vessel/unit/{j}')
    return device,changes



def finite_nonnegative(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(label+': require a finite nonnegative number')
    return float(value)


def stage_material(document, materialize_model='none'):
    if materialize_model not in ('none', 'wall', 'pulse'):
        raise ValueError('materialize_model must be none, wall or pulse')
    device = copy.deepcopy(document); changes = []
    slices = device.get('wall', {}).get('description_2d', [])
    if isinstance(slices, dict): slices = [slices]
    global_eta = device.get('fylite:vessel_resistivity_uohm_m')
    group_eta = device.get('pf_passive', {}).get('vessel', {}).get('resistivity_uohm_m')
    for si, section in enumerate(slices):
        for ui, unit in enumerate(section.get('vessel', {}).get('unit', [])):
            unit_path = f'wall/description_2d/{si}/vessel/unit/{ui}'
            old_unit = unit.get('fylite:resistivity_uohm_m')
            choices = [(old_unit, unit_path+'/fylite:resistivity_uohm_m')]
            if materialize_model == 'wall':
                choices = [(group_eta, 'pf_passive/vessel/resistivity_uohm_m'), (global_eta, 'fylite:vessel_resistivity_uohm_m')]
            elif materialize_model == 'pulse':
                choices += [(global_eta, 'fylite:vessel_resistivity_uohm_m'), (group_eta, 'pf_passive/vessel/resistivity_uohm_m')]
            selected = next(((value, path) for value, path in choices if value is not None), None)
            if old_unit is not None:
                finite_nonnegative(old_unit, unit_path+'/fylite:resistivity_uohm_m')
                if not unit.get('element'): raise ValueError(unit_path+': legacy unit material has no elements to carry it')
                if selected is None: raise ValueError(unit_path+': old unit value was ignored by this model; no effective fallback to materialize')
            for ei, element in enumerate(unit.get('element', [])):
                path = unit_path+f'/element/{ei}/resistivity'
                existing = element.get('resistivity')
                if existing is not None: finite_nonnegative(existing, path)
                if selected is None: continue
                eta, source = selected; eta = finite_nonnegative(eta, source); rho = eta * 1e-6
                if eta > 0 and rho == 0: raise ValueError(source+': conversion underflows to an ideal conductor')
                if not math.isfinite(rho * 1e6): raise ValueError(source+': converted value overflows circuit units')
                if existing is not None and existing != rho:
                    raise ValueError(path+': conflicting existing DD material; choose a new input explicitly')
                element['resistivity'] = rho
                changes.append(dict(path=path, source_path=source, source_uohm_m=eta, value_ohm_m=rho,
                    original_unit_uohm_m=old_unit, model_materialization=materialize_model != 'none'))
            # No read-side alias: remove the retired field from the staged copy.
            unit.pop('fylite:resistivity_uohm_m', None)
    return device, changes



OLD='fylite:vessel_resistivity_uohm_m'
NEW='vessel_resistivity'
def scalar(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label+': require a finite nonnegative number')
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError(label+': not representable') from error
    if not math.isfinite(value) or value < 0:
        raise ValueError(label+': require a finite nonnegative number')
    return value


def stage_vessel_plan(request):
    result = copy.deepcopy(request)
    settings = result.setdefault('settings', {})
    device = result.get('inputs', {}).get('device', {})
    if not isinstance(settings, dict) or not isinstance(device, dict):
        raise ValueError('settings and inputs/device must be maps')
    changes = []
    existing = settings.get(NEW)
    if NEW in settings:
        existing = scalar(existing, 'settings/'+NEW)
        if not math.isfinite(existing*1e6):
            raise ValueError('settings/'+NEW+': overflows circuit units')
    if OLD not in device:
        return result, changes
    eta = scalar(device[OLD], 'inputs/device/'+OLD)
    rho = eta*1e-6
    if eta > 0 and rho == 0:
        raise ValueError(OLD+': conversion underflows to an ideal conductor')
    if existing is not None and existing != rho:
        raise ValueError('settings/'+NEW+': conflicting existing plan fallback')
    settings[NEW] = rho
    device.pop(OLD)
    changes.append(dict(source_path='inputs/device/'+OLD, source_uohm_m=eta,
                        path='settings/'+NEW, value_ohm_m=rho,
                        independently_measured_element_material=False))
    return result, changes



def stage_passive_plan(request):
    result = copy.deepcopy(request)
    inputs = result.setdefault('inputs', {})
    device = inputs.get('device', {})
    old = device.get('pf_passive', {})
    if not isinstance(old, (dict, list)):
        raise ValueError('device/pf_passive must be a group map or DD loop list')
    model = inputs.get('passive_model', {'@type': 'spo:InformationContentEntity', 'model_format': 1, 'groups': []})
    if not isinstance(model, dict) or model.get('model_format') != 1 or isinstance(model.get('model_format'), bool) or not isinstance(model.get('groups'), list):
        raise ValueError('passive_model requires model_format=1 and a groups list')
    names = [g.get('name') if isinstance(g, dict) else None for g in model['groups']]
    if any(not isinstance(n, str) or not n or n != n.strip() or ',' in n or n == 'inner_shell' for n in names) or len(names) != len(set(names)):
        raise ValueError('passive_model groups require unique nonempty canonical names')
    changes = []
    for name, group in list(old.items()) if isinstance(old, dict) else []:
        if not isinstance(group, dict) or not any(k in group for k in ('resistivity_uohm_m', 'element')):
            continue
        if not name or name != name.strip() or ',' in name or name == 'inner_shell':
            raise ValueError('legacy passive group needs an explicit canonical name: '+name)
        if name in names:
            raise ValueError('conflicting existing passive_model group: '+name)
        new = dict(name=name)
        if 'resistivity_uohm_m' in group:
            eta = scalar(group['resistivity_uohm_m'], 'pf_passive/'+name+'/resistivity_uohm_m')
            rho = eta*1e-6
            if eta > 0 and rho == 0 or not math.isfinite(rho*1e6):
                raise ValueError('pf_passive/'+name+': material conversion is not representable')
            new['resistivity'] = rho
        if 'element' in group:
            rows = group['element']
            if not isinstance(rows, list):
                raise ValueError('pf_passive/'+name+'/element must be a six-column row list')
            elements = []
            for i, row in enumerate(rows):
                if not isinstance(row, list) or len(row) != 6 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in row):
                    raise ValueError(f'pf_passive/{name}/element/{i}: require six numeric EFIT coordinates')
                elements.append(dict(geometry=geometry_from_efit(*row)))
            new['elements'] = elements
        extras = {k: v for k, v in group.items() if k not in ('resistivity_uohm_m', 'element')}
        if extras:
            new['source_metadata'] = extras
        model['groups'].append(new);names.append(name);old.pop(name)
        changes.append(dict(source_path='inputs/device/pf_passive/'+name, source_group=group,
                            target_group=new, independently_measured_element_material=False))
    if changes:
        inputs['passive_model'] = model
        if not old:
            device.pop('pf_passive', None)
    return result, changes



RECIPES = ('preset', 'M', 'MK', 'MP', 'MKP')
SP_VERSION = '0.1.0+01d4861b'

def data_host():
    host = Lib(ROOT/'libfylite.so')
    if host.runtime_version().strip() != SP_VERSION:
        raise ValueError('MDSplus 需要 libsp.version 固定的 '+SP_VERSION)
    return host

def workflow_validate(config):
    w = config.get('workflow', {})
    recipe = w.get('recipe', 'preset')
    if recipe not in RECIPES: raise ValueError('未知诊断配方')
    if recipe == 'preset': return
    inp = w.get('inputs', {})
    if not isinstance(inp.get('device'), dict) or not isinstance(inp.get('measurements'), dict):
        raise ValueError('请先读取 MDSplus，或导入含 device / measurements 的诊断输入')
    m = inp['measurements']
    for name in ('brsp', 'coils', 'expmp2', 'fwtmp2'):
        if not isinstance(m.get(name), list) or not m[name]:raise ValueError('磁测量缺少 '+name)
    if 'K' in recipe:
        point=m.get('point') or {}
        npoint=len(point.get('bpolar') or [])
        if npoint and any(len(point.get(k) or [])!=npoint for k in ('bnel','fwtnel','fwtpol')):raise ValueError('POINT 观测和通道权重须等长')
        if not point.get('bpolar') or not any(v>0 for v in point.get('fwtpol',[])):
            raise ValueError('所选配方需要有效 POINT 法拉第角及通道权重')
    if 'P' in recipe:
        th=inp.get('thomson') or {}; n=len(th.get('te',[]))
        if n<2 or any(len(th.get(k) or [])!=n for k in ('r','z','ne','te_err','ne_err')):
            raise ValueError('汤姆逊配方需要等长 R/Z/Te/ne 和逐点 Te/ne 误差数组')
        if any(v<=0 for k in ('te_err','ne_err') for v in th[k]):raise ValueError('汤姆逊误差必须为正')

def pull_diagnostics(spec):
    recipe=spec.get('recipe','M')
    if recipe not in RECIPES[1:]:raise ValueError('MDSplus 请选择 M/MK/MP/MKP')
    shot=int(spec['shot']); t=float(spec['time_s'])
    if shot<=0 or not math.isfinite(t):raise ValueError('炮号须为正整数，时间为有限秒数')
    server=spec.get('server') or os.environ.get('FYLITE_MDSIP_SERVER') or '202.127.204.12:8000'
    if ':' not in server:server+=':8000'
    timeout=float(spec.get('timeout_s',10))
    if not 0<timeout<=60:raise ValueError('连接超时须为 (0,60] 秒')
    host=data_host(); chain=spec.get('measurement_chain','east')
    src=MagneticsSource(host,shot,chain,server,timeout)
    try:
        src.prefetch(point='K' in recipe,workers=8)
        meas=src.at(t,point='K' in recipe); card=src.doc
    finally:src.close()
    inp={'device':card,'measurements':meas,'options':{'tiers':recipe,'p_on':'K' if 'K' in recipe else 'M'}}
    if 'P' in recipe:inp['thomson']=pull_thomson(host,shot,t,server,timeout,float(spec.get('ts_max_dt_s',.5)))
    w={'recipe':recipe,'inputs':inp,'source':{'kind':'mdsplus','shot':shot,'time_s':t,'measurement_chain':chain,'libsp_version':SP_VERSION,'loop_input_units':'Wb/rad','created_utc':datetime.now(timezone.utc).isoformat()}}
    workflow_validate({'workflow':w})
    path=ROOT/'output'/('pull-'+uuid.uuid4().hex+'.json');path.parent.mkdir(exist_ok=True);save(path,w)
    return {'workflow':w,'input_url':'/output/'+path.name}

def solve_diagnostics(config,output):
    workflow_validate(config); output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise FileExistsError('输出已存在：'+str(output))
    config=copy.deepcopy(config);w=config['workflow'];inp=w['inputs'];recipe=w['recipe']
    opts=inp.setdefault('options',{});opts['tiers']=recipe;opts['p_on']='K' if 'K' in recipe else 'M'
    opts['keep_solve']=['M','K'];opts['efit_fit']='off'
    # Never substitute cached ONETWO pressure for requested TS or pure magnetic modes.
    if 'P' not in recipe:inp.pop('thomson',None);inp.pop('profiles',None)
    if 'K' not in recipe:inp['measurements'].pop('point',None)
    inp['measurements'].pop('kinetic_pressure',None);inp.pop('kinetic_input',None)
    grid=inp['device'].get('fylite:grid',{})
    aliases={'r_min':'rmin','r_max':'rmax','z_min':'zmin','z_max':'zmax','nw':'nr','nh':'nz'}
    default={'rmin':1.2,'rmax':2.8,'zmin':-1.4,'zmax':1.4,'nr':65,'nz':65}
    settings=w.setdefault('settings',{})
    for key,alias in aliases.items():settings.setdefault(key,grid.get(alias,default[alias]))
    inp['device'],geom=stage_geometry(inp['device'],'inherit')
    inp['device'],material=stage_material(inp['device'])
    staged,vessel=stage_vessel_plan({'inputs':inp,'settings':settings})
    staged,passive=stage_passive_plan(staged)
    inp=staged['inputs'];w['inputs']=inp;w['settings']=staged['settings']
    staging={'geometry':geom,'material':material,'vessel':vessel,'passive':passive}
    if any(staging.values()):
        if 'staging' in w:staging['input_staging']=w['staging']
        w['staging']=staging
    else:w.setdefault('staging',staging)
    stem=output.with_suffix('');save(str(stem)+'.input.json',config)
    if digest(ROOT/'libfylite.so')!=LIB_SHA:raise ValueError('动态库 SHA256 不符')
    host=data_host();start=time.perf_counter();status,text=host._case('code/kinetic',{'settings':w.get('settings',{}),'inputs':inp})
    if status:save(str(stem)+'.error.json',{'status':status,'message':text});raise RuntimeError(text)
    def finite_record(value):
        if isinstance(value,dict):return {k:finite_record(v) for k,v in value.items()}
        if isinstance(value,list):return [finite_record(v) for v in value]
        if isinstance(value,float) and not math.isfinite(value):return None
        return value
    result=finite_record(json.loads(text)['record']);result['workflow_recipe']=recipe
    # Ladder failure remains a saved result, never a silent downgrade to M.
    result['converged']=all(result.get('tiers',{}).get(k,{}).get('status')=='ok' and bool(result['tiers'][k].get('facts',{}).get('converged')) for k in recipe)
    if recipe!='M':result['converged']=result['converged'] and result.get('fylite:convergence',{}).get('status')=='converged'
    save(output,result)
    identity={'created_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'elapsed_s':time.perf_counter()-start,'library_sha256':LIB_SHA,'libsp_version':host.runtime_version(),'libsp_sha256':digest(ROOT/'libsp.so'),'input_sha256':digest(str(stem)+'.input.json'),'output_sha256':digest(output),'recipe':recipe,'converged':result['converged'],'flux_convention':'psi: COCOS17 whole Wb; diagnostic loops: legacy Wb/rad, plotted ×2π'}
    save(str(stem)+'.identity.json',identity);return result,identity

def ladder_charts(result,config,identity):
    return {'kind':'diagnostic_ladder','shot':result.get('shot'),'time_s':result.get('time_s'),'recipe':result['workflow_recipe'],'converged':result['converged'],'tiers':result['tiers'],'outer_convergence':result.get('fylite:convergence',{}),'quality_warnings':[{'tier':name,'reasons':tier.get('certificate',{}).get('cleaning_reasons',[])} for name,tier in result['tiers'].items() if tier.get('certificate',{}).get('cleaning_suspect')],'measurements':config['workflow']['inputs']['measurements'],'thomson':config['workflow']['inputs'].get('thomson'),'thomson_points':result.get('thomson_points'),'identity':identity or {},'source':config['workflow'].get('source',{'kind':'local'}),'scope':'剖面不确定度仅显示内核实际导出的项；未导出的完整重构置信区间不补造。'}

def load(path): return json.loads(Path(path).read_text())
def save(path, value): Path(path).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n')
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def validate(config):
    json.dumps(config, allow_nan=False)
    workflow_validate(config)
    provenance=config.get('pressure_provenance')
    if provenance is not None:
        source=provenance.get('source','')
        if not isinstance(source,str) or not source.startswith(('data:','model:')) or not source.split(':',1)[-1].strip() or 'derived-from-reconstruction' in source:raise ValueError('压力来源须独立于本次反演，且声明data:/model:引用')
    for name in [config['pf_table'], config['plasma_table'], config['initial_pf']['coil_table'], config['initial_pf']['plasma_table'], config['measurement_template']['magnetic']['coil_table']]:
        if name not in TABLES: raise ValueError('响应表标识必须来自随包提供的三份 input/tables 文件')
    if not 1 <= config['max_iterations'] <= 1000: raise ValueError('迭代上限须为 1～1000')
    if not 0 < config['relax'] <= 1 or not 0 < config['tolerance'] < 1: raise ValueError('松弛系数须为 (0,1]，容差须为 (0,1)')
    m=config['measurement_template']; sizes=[(m['magnetic'],'loop_observed',35),(m['magnetic'],'loop_weights',35),(m['magnetic'],'probe_observed',76),(m['magnetic'],'probe_weights',76),(m['global'],'pf_observed',12),(m['global'],'pf_weights',12)]
    for obj,key,n in sizes:
        if len(obj[key])!=n: raise ValueError(f'{key} 须有 {n} 项；探针后40项是原案例补零槽')
        if any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in obj[key]): raise ValueError(f'{key} 包含非有限数值')
    p=m['pressure']; n=len(p['observed'])
    if n<2 or any(len(p[k])!=n for k in ['coordinates','sigma','weights']): raise ValueError('压力坐标、读数、sigma、权重须等长')
    if any(x<=0 for x in p['sigma']): raise ValueError('压力 sigma 必须为正')
    if any(x<0 for x in m['magnetic']['loop_weights']+m['magnetic']['probe_weights']+m['global']['pf_weights']+p['weights']): raise ValueError('拟合权重须非负，0 表示不使用')
    return config

def apply_pressure(config,preset):
    if preset.get('schema')!='fylite/pressure-preset/1':raise ValueError('压力文件 schema 须为 fylite/pressure-preset/1')
    source=preset.get('source','')
    if not isinstance(source,str) or not source.startswith(('data:','model:')) or not source.split(':',1)[-1].strip() or 'derived-from-reconstruction' in source:raise ValueError('压力必须标明独立 data:/model: 来源，不能来自本次反演输出')
    arrays=[preset.get(k) for k in ['psi_N','pressure_Pa','sigma_Pa']]
    if any(not isinstance(a,list) for a in arrays):raise ValueError('压力须提供 psi_N、pressure_Pa、sigma_Pa 数组')
    n=len(arrays[0])
    if not 2<=n<=1000 or any(len(a)!=n for a in arrays):raise ValueError('压力数组须等长，包含2～1000点')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for a in arrays for v in a):raise ValueError('压力文件包含非有限值')
    xs,values,sigma=arrays
    if xs[0]<0 or xs[-1]>1 or any(b<=a for a,b in zip(xs,xs[1:])):raise ValueError('psi_N 必须严格递增并在[0,1]内')
    if any(v<0 for v in values) or any(v<=0 for v in sigma):raise ValueError('压力须非负，sigma须为正；不自动补造误差')
    weights=preset.get('fit_weights',[1.0]*n)
    if not isinstance(weights,list) or len(weights)!=n or any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in weights):raise ValueError('fit_weights须等长、有限且非负')
    config=json.loads(json.dumps(config,allow_nan=False));p=config['measurement_template']['pressure'];p.update(coordinates=[-x for x in xs],observed=values,sigma=sigma,weights=weights)
    config['pressure_provenance']={k:preset[k] for k in ['schema','source','label','time_s','provenance'] if k in preset};return config

def solve(config, output):
    if config.get("workflow",{}).get("recipe","preset") != "preset":return solve_diagnostics(config,output)
    config=json.loads(json.dumps(config,allow_nan=False));m=config['measurement_template']
    for target,values in [('loop_observed',m['magnetic']['loop_observed']),('loop_weights',m['magnetic']['loop_weights']),('pf_observed',m['global']['pf_observed']),('pf_weights',m['global']['pf_weights'])]:config['initial_pf'][target]=list(values)
    config['initial']['target_ip']=m['global']['ip_observed'];config['measurement_template']['fsa']['measured_ip']=m['global']['ip_observed']
    original=load(ROOT/'input/pressure_onetwo.json');p=m['pressure']
    same=(p['observed']==original['pressure_Pa'] and p['sigma']==original['sigma_Pa'] and [abs(x) for x in p['coordinates']]==original['psi_N'])
    pv=config.get('pressure_provenance',{})
    if not pv or (pv.get('source')==original['source'] and not same):
        config['pressure_provenance']={k:original[k] for k in ['schema','source','label','time_s','provenance']} if same else {'source':'model:user-edited-pressure','label':'用户编辑压力约束'}
    validate(config); output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise FileExistsError(f'输出已存在，请使用新路径：{output}')
    stem=output.with_suffix(''); input_path=Path(str(stem)+'.input.json'); save(input_path,config)
    libpath=ROOT/'libfylite.so'
    if digest(libpath)!=LIB_SHA: raise ValueError('动态库 SHA256 与已验证版本不符')
    tables={n:(ROOT/n).read_bytes().hex() for n in TABLES}
    body=json.dumps({'settings':{},'inputs':{'native_reconstruction':{'config':config,'input_flux_convention':'legacy_wb_per_radian','bound_green_tables':tables}}},allow_nan=False).encode()
    lib=ctypes.CDLL(str(libpath)); lib.fylite_rs_fyo_json.argtypes=[ctypes.c_void_p,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_uint64,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_uint64)];lib.fylite_rs_fyo_json.restype=ctypes.c_int32;lib.fylite_rs_free.argtypes=[ctypes.c_void_p,ctypes.c_uint64];lib.fylite_rs_free.restype=None
    pointer=ctypes.c_void_p();length=ctypes.c_uint64();start=time.perf_counter();status=lib.fylite_rs_fyo_json(b'code/kinetic',12,body,len(body),ctypes.byref(pointer),ctypes.byref(length))
    try: text=ctypes.string_at(pointer,length.value).decode() if pointer.value else ''
    finally:
        if pointer.value: lib.fylite_rs_free(pointer,length.value)
    if status: save(Path(str(stem)+'.error.json'),{'status':status,'message':text});raise RuntimeError(text)
    result=json.loads(text)['record'];save(output,result)
    identity={'created_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'elapsed_s':time.perf_counter()-start,'library_sha256':LIB_SHA,'input_sha256':digest(input_path),'output_sha256':digest(output),'tables_sha256':{n:digest(ROOT/n) for n in TABLES},'flux_convention':result['flux_convention'],'converged':result['converged']};save(Path(str(stem)+'.identity.json'),identity)
    return result,identity

def chart_data(result,config,identity=None):
    if "workflow_recipe" in result:return ladder_charts(result,config,identity)
    # Visualization only: piecewise-linear contours of the saved flux map.
    state=result['result'];g=state['geometry'];a=g['axis'];rr=[1.2+1.6*i/128 for i in range(129)];zz=[-1.4+2.8*j/128 for j in range(129)]
    pn=[(a['source_stopping_flux']-v)/(a['source_stopping_flux']-g['boundary_flux']) for v in state['field']]
    def inside(x,y):
        answer=False
        for p,q in zip(g['contour'],g['contour'][1:]):
            if (p[1]>y)!=(q[1]>y) and x<(q[0]-p[0])*(y-p[1])/(q[1]-p[1])+p[0]:answer=not answer
        return answer
    mask=[inside(x,y) for x in rr for y in zz];surfaces=[]
    for level in [.1,.2,.3,.4,.5,.6,.7,.8,.9]:
        paths=[]
        for i in range(128):
            for j in range(128):
                ids=[i*129+j,(i+1)*129+j,(i+1)*129+j+1,i*129+j+1]
                if not all(mask[k] for k in ids):continue
                xy=[[rr[i],zz[j]],[rr[i+1],zz[j]],[rr[i+1],zz[j+1]],[rr[i],zz[j+1]]];hits=[]
                for u,v in [(0,1),(1,2),(2,3),(3,0)]:
                    f,h=pn[ids[u]],pn[ids[v]]
                    if (f<level)!=(h<level):
                        t=(level-f)/(h-f);hits.append([xy[u][0]+t*(xy[v][0]-xy[u][0]),xy[u][1]+t*(xy[v][1]-xy[u][1])])
                if len(hits)==2:paths.append(hits)
                elif len(hits)==4:
                    if (sum(pn[k] for k in ids)/4<level)==(pn[ids[0]]<level):paths.extend([[hits[0],hits[1]],[hits[2],hits[3]]])
                    else:paths.extend([[hits[0],hits[3]],[hits[1],hits[2]]])
        surfaces.append({'level':level,'paths':paths})
    reference=load(ROOT/'input/reference.json');ref=reference['geqdsk'];bands=state.get('conditional_bands',{}).get('profiles',[]) if state.get('conditional_bands') else []
    return {'converged':result['converged'],'last':result['history'][-1],'history':result['history'],'surfaces':surfaces,'boundary':g['contour'],'limiter':config['initial']['limiter'],'axis':[a['r'],a['z']],'profiles':result['exports']['pressure_F']['profiles'],'q':result['exports']['q']['profiles'],'bands':bands,'diagnostics':result['exports']['diagnostics']['diagnostics'],'pf':state['solution'][:12],'pf_observed':config['measurement_template']['global']['pf_observed'],'pf_weights':config['measurement_template']['global']['pf_weights'],'pressure_provenance':config.get('pressure_provenance',{'source':'data:archived-ONETWO-EAST-94048','label':'ONETWO 存档压力','time_s':6.510}),'pressure_input':config['measurement_template']['pressure'],'reference':{'boundary':list(zip(ref['rbbbs'],ref['zbbbs'])),'pressure':ref['pres'],'F':ref['fpol'],'q':ref['qpsi'],'pf':reference['pf_current_ka_turns'],'diagnostics':reference['diagnostics'],'M':load(ROOT/'input/M_baseline.json')},'identity':identity or {},'band_kind':config.get('conditional_covariance','objective'),'scope':'固定磁面几何的条件误差带，不是完整重构置信区间。'}

def bundle(result_path=None):
    result_path=Path(result_path) if result_path else ROOT/'output/baseline.json'
    config=load(result_path.with_suffix('.input.json'));result=load(result_path);identity=load(result_path.with_suffix('.identity.json'));
    if identity['output_sha256']!=digest(result_path) or identity['input_sha256']!=digest(result_path.with_suffix('.input.json')):raise ValueError('输入/输出与运行身份不一致，拒绝重绘')
    import base64
    return {'config':config,'charts':chart_data(result,config,identity),'pressure_preset':load(ROOT/'input/pressure_onetwo.json'),'diagnostic_default':load(ROOT/'input/diagnostics_local.json'),'logo':'data:image/png;base64,'+base64.b64encode((ROOT/'input/fytok_logo.png').read_bytes()).decode()}
def build_html(result_path=None):
    template=(ROOT/'index.html').read_text();data=json.dumps(bundle(result_path),ensure_ascii=False,allow_nan=False).replace('<','\\u003c');import re
    template=re.sub(r'(<script id="data" type="application/json">).*?(</script>)',lambda m:m[1]+data+m[2],template,flags=re.S)
    (ROOT/'index.html').write_text(template)
JOBS={};LOCK=threading.Lock();BUSY=False
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def response(self,status,value):
        body=json.dumps(value,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path=='/api/health':return self.response(200,{'ready':True,'library_sha256':digest(ROOT/'libfylite.so')})
        if self.path.startswith('/api/jobs/'):
            with LOCK:job=JOBS.get(self.path.rsplit('/',1)[-1]);value=dict(job) if job else None
            return self.response(200,value) if value else self.response(404,{'error':'未知运行'})
        return super().do_GET()
    def do_POST(self):
        global BUSY
        if self.path not in ('/api/run','/api/mds/pull'):return self.response(404,{'error':'未知接口'})
        if self.headers.get('Origin') not in [None,'http://'+self.headers.get('Host','')]:return self.response(403,{'error':'请从本地服务页面提交'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<2_000_000:raise ValueError('输入须小于2MB')
            submitted=json.loads(self.rfile.read(n))
            if self.path=='/api/mds/pull':return self.response(200,pull_diagnostics(submitted))
            config=validate(submitted)
            with LOCK:
                if BUSY:return self.response(409,{'error':'已有反演正在执行'})
                BUSY=True;key=uuid.uuid4().hex;JOBS[key]={'state':'running','started_utc':datetime.now(timezone.utc).isoformat()}
            def work():
                global BUSY
                path=ROOT/'output'/('run-'+key+'.json')
                try:
                    result,identity=solve(config,path);chart=chart_data(result,load(path.with_suffix(".input.json")),identity);save(path.with_suffix('.charts.json'),chart);job={'state':'done','charts':chart,'config':load(path.with_suffix('.input.json')),'result_url':'/output/'+path.name,'input_url':'/output/'+path.with_suffix('.input.json').name,'identity_url':'/output/'+path.with_suffix('.identity.json').name}
                except Exception as error:job={'state':'error','error':str(error)}
                with LOCK:JOBS[key]=job;BUSY=False
            threading.Thread(target=work,daemon=True).start();return self.response(202,{'id':key})
        except Exception as error:return self.response(400,{'error':str(error)})

def main():
    p=argparse.ArgumentParser(description='统一libfylite动理学反演：命令行或本地HTML服务');g=p.add_mutually_exclusive_group(required=True);g.add_argument('--run',metavar='CONFIG');g.add_argument('--serve',action='store_true');g.add_argument('--build-html',action='store_true');g.add_argument('--pull',action='store_true');p.add_argument('--recipe',choices=RECIPES);p.add_argument('--diagnostics',help='导入诊断工作流JSON或标准settings/inputs请求');p.add_argument('--shot',type=int);p.add_argument('--time',type=float,help='时间 / s');p.add_argument('--server');p.add_argument('--out',default=None);p.add_argument('--pressure',metavar='PRESET',help='导入独立压力约束JSON（含误差和来源）');p.add_argument('--port',type=int,default=8765);args=p.parse_args()
    if args.pull:

        if args.out and Path(args.out).exists():raise FileExistsError('输出已存在：'+args.out)
        pulled=pull_diagnostics({'recipe':args.recipe or 'M','shot':args.shot,'time_s':args.time,'server':args.server})
        if args.out:
            Path(args.out).parent.mkdir(parents=True,exist_ok=True);save(args.out,pulled['workflow'])
        print(pulled['input_url']);return 0
    if args.run:
        output=Path(args.out) if args.out else ROOT/'output'/('cli-'+uuid.uuid4().hex+'.json');config=load(args.run);config=apply_pressure(config,load(args.pressure)) if args.pressure else config;
        if args.diagnostics:
            d=load(args.diagnostics);config['workflow']=d if 'recipe' in d else {'recipe':args.recipe or 'M','inputs':d['inputs'],'settings':d.get('settings',{})}
        if args.recipe:config.setdefault('workflow',{})['recipe']=args.recipe
        r,i=solve(config,output);print(json.dumps({'output':str(output.resolve()),'converged':r['converged'],'iterations':r['history'][-1]['iteration'] if 'history' in r else {k:v.get('facts',{}).get('iterations') for k,v in r.get('tiers',{}).items()},'elapsed_s':i['elapsed_s']},ensure_ascii=False));return 0 if r['converged'] else 2
    if args.build_html:build_html(args.out);print(ROOT/'index.html');return 0
    print(f'打开 http://127.0.0.1:{args.port} ，Ctrl+C 停止服务',flush=True);ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:print(f'错误：{error}');raise SystemExit(1)
