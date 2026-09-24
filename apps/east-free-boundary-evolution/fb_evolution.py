#!/usr/bin/env python3
"""EAST 自由边界平衡演化（PF/IC 线圈电流给定 · 被动结构电流给定或感应自洽）。

四条命令::

    python fb_evolution.py prepare DATA_DIR -o in/case.json              # 读 g/a/mat → 一份输入文档
    python fb_evolution.py initial in/case.json -o out/initial.json      # 校验 1：t0 的初始平衡 vs g/a 文件
    python fb_evolution.py run in/case.json --passive induced -o out/run_induced.json [--gfile-dir DIR]
    python fb_evolution.py compare out/run_*.json -o out/compare.json     # 各模式之间、与 EFIT 参考迹之间

``--passive`` 三种：

* ``zero``       —— 全部被动丝作为**给定电流恒为零**的导体（等于「没有被动电流」），仍报告各丝处的磁通；
* ``prescribed`` —— 各丝电流由 ``--passive-file`` 给出（时间序列，按时刻线性插值）；
* ``induced``    —— 各丝电流由回路方程 R_k I_k + dΨ_k/dt = 0 自洽算出（Ψ_k 含等离子体、PF、IC 与其余各丝的互感）。

★★独立发行：只用 Python 标准库（ctypes · json · math · struct · zlib）与**一个** ``libfylite.so``——不 import
fylite 的 Python 包，也不要 numpy。物理计算全部经库里内核的文档门 ``fylite_runtime_case_tree_json``：

* ``code/evolve_free_boundary`` —— 线圈（电流驱动）与被动结构（隐式欧拉回路方程）同步推进，每一步重解自由边界平衡，
  等离子体在每个导体处的磁通反馈进回路（内核 PCS 同一套互感与格林函数）；
* ``code/forward``  —— t0 处的单次自由边界解（找「虚拟线圈对不出力」的竖直位置）；
* ``code/summary``  —— 每一步的边界、形状、q 剖面、压强与 F；
* ``code/wall``     —— 被动丝回路的 L/R 本征时间（选步长的依据）。

要求的库：内核带 ``code/evolve_free_boundary`` 的 ``keep_psi`` 与 ``zc_anchor`` 两个 opt-in 设定（2026-09-22），
并编进了 EAST 装置事实（内部版构建）。库在哪：缺省是本文件旁边的 ``libfylite.so``；``--lib`` 显式给另一份。

★★实验数据与结果不入仓：数据目录、输出路径都由调用方给。
"""
from __future__ import annotations

import argparse
import bisect
import ctypes
import datetime
import json
import math
import re
import struct
import sys
import time
import zlib
from pathlib import Path

def _finite(o):
    """NaN / ±inf → None, recursively: the output must be STRICT JSON (browsers' JSON.parse, jq and the
    page reject a bare NaN).  A missing value — e.g. the X-point on a step that has none — is null."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finite(v) for v in o]
    return o


def _write_json(path, obj, indent=None) -> None:
    Path(path).write_text(json.dumps(_finite(obj), indent=indent, allow_nan=False), encoding="utf-8")


HERE = Path(__file__).resolve().parent
APP = "east-free-boundary-evolution"
VERSION = "0.1.0"
DEFAULT_LIB = HERE / "libfylite.so"
MU0 = 4e-7 * math.pi
TWO_PI = 2.0 * math.pi
_U8P = ctypes.POINTER(ctypes.c_uint8)

#: 说明.txt：pf 的 16 列 —— 1~14 = PF1~14，15、16 = IC1、IC2，单匝电流 [A/turn]
MAGDATA_COILS = [f"PF{i}" for i in range(1, 15)] + ["IC1", "IC2"]
#: 被动丝条带厚度由电阻反推时假定的电阻率 [Ω·m]（不锈钢，与装置事实 pf_passive/vessel 同值）。
#: 它只决定条带的截面（→ 自感的对数项）；电阻本身逐丝取 VVres，与这个数无关（见 README §4）。
RHO_SS = 0.74e-6
#: 相邻两丝间距大于它就断开成两条轮廓 [m]（要比一条轮廓内的最大间距大、比双层壁的壁间距小；--contour-gap 可改）
CONTOUR_GAP = 0.195

SOLVE = {"relax": 0.1, "tol": 1e-9, "max_iter": 12000, "fb_gain": 8.0}


def log(msg: str) -> None:
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


class KernelError(RuntimeError):
    """库返回了负的状态码（不是物理上的拒绝）。"""


class Refused(RuntimeError):
    """内核按名拒绝了这次请求（记录里的 refusal）。"""


def flat(v) -> list:
    """嵌套列表（按 dims 嵌套的字段）摊平成一维。"""
    if not isinstance(v, list):
        return [v]
    out = []
    for x in v:
        if isinstance(x, list):
            out.extend(flat(x))
        else:
            out.append(x)
    return out


# =========================================================================== #
# 库
# =========================================================================== #
class Lib:
    """``libfylite.so`` 的三扇门：内核文档门、装置事实、g-file 读者。

    ★与 ``apps/east-kinetic-reconstruction/kinetic_recon.py`` 的 ``Lib`` 同形（少了 mdsip）。照 ``apps/README.md``
    「拷走即可运行」的规矩抄一份小的，而不 import 那个 2000 多行的兄弟脚本：两个场景各自可以单独拷走。"""

    def __init__(self, path: Path):
        if not Path(path).is_file():
            raise SystemExit(f"找不到 {path}：把 libfylite.so 放在 {HERE} 下，或用 --lib 指一份（README §7）")
        self.path = Path(path)
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

    def door(self, code: str, settings: dict, inputs: dict):
        """一份请求进、一份记录出：(facts{key: 数}, fields{key: 值}, notes)。"""
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
            raise Refused(f"{code}: the kernel refused ({ref.get('code', rc)}): {ref.get('message', text[:300])}")
        fa = {k: v["value"] for k, v in (rec.get("facts") or {}).items() if isinstance(v.get("value"), (int, float))}
        fi: dict = {}

        def walk(node, path):
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
        return {k: info.get(k) for k in ("kernel_version", "built", "sha256") if k in info}

    def device(self, device_id: str, shot: int, chain: str) -> dict:
        """这一炮、这条测量链上的装置文档（编进库里的事实 + 运行时的解析规则）。"""
        d, i = b"device", device_id.encode()
        doc = self._ask(self.lib.fylite_runtime_facts_doc, d, len(d), i, len(i))
        res = self._ask(self.lib.fylite_runtime_facts_resolution, d, len(d), i, len(i))
        if not isinstance(doc, str) or not doc or not isinstance(res, str) or not res:
            have = self._ask(self.lib.fylite_runtime_facts_ids, d, len(d))
            raise SystemExit(f"这份 libfylite.so 没有编进装置 {device_id!r}（它有：{have}）——要的是含 EAST 的内部版构建")
        q = json.dumps({"shot": int(shot), "measurement_chain": chain, "strict": False}).encode()
        c, r = doc.encode(), res.encode()
        text = self._ask(self.lib.fylite_runtime_device_resolve, c, len(c), r, len(r), q, len(q), b"document", 8)
        if not isinstance(text, str):
            raise KernelError(f"fylite_runtime_device_resolve 失败（{text}）")
        out = json.loads(text)
        if "error" in out:
            raise SystemExit(f"装置解析：{out['error']}")
        return out["document"]

    def gfile(self, text: str) -> dict:
        """G-EQDSK 文本 → 内核 ``GFile`` 的 JSON（``fylite_runtime_gfile_json``，与页面同一个读者）。"""
        fn = getattr(self.lib, "fylite_runtime_gfile_json", None)
        if fn is None:
            raise SystemExit("这份 libfylite.so 没有 fylite_runtime_gfile_json（abi_gfile 特性）")
        fn.argtypes = [ctypes.c_char_p, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint64]
        fn.restype = ctypes.c_int64
        b = text.encode()
        n = fn(b, len(b), None, 0)
        if n < 0 and n != -2:
            raise KernelError(f"fylite_runtime_gfile_json 返回 {n}")
        cap = max(int(n), 4096)
        buf = ctypes.create_string_buffer(cap)
        got = fn(b, len(b), buf, cap)
        if got == -2 or n == -2:
            raise SystemExit(f"g-file 读不动：{buf.raw[:400].decode('utf-8', 'replace').rstrip(chr(0))}")
        return json.loads(buf.raw[:got].decode("utf-8"))


# =========================================================================== #
# 读者：MAT v5 · A-EQDSK · G-EQDSK
# =========================================================================== #
_MI = {1: "b", 2: "B", 3: "h", 4: "H", 5: "i", 6: "I", 7: "f", 9: "d", 12: "q", 13: "Q"}


def _mat_elements(b, p=0, end=None):
    end = len(b) if end is None else end
    while p + 8 <= end:
        t, n = struct.unpack_from("<II", b, p)
        if t >> 16:                       #: small data element：n 个字节就在标签的后半
            n, t = t >> 16, t & 0xFFFF
            yield t, b[p + 4:p + 4 + n]
            p += 8
            continue
        yield t, b[p + 8:p + 8 + n]
        p += 8 + n + ((8 - n % 8) % 8 if t != 15 else 0)


def _mat_numbers(t, raw):
    f = _MI[t]
    return list(struct.unpack("<%d%s" % (len(raw) // struct.calcsize(f), f), raw))


def _mat_matrix(body):
    sub = list(_mat_elements(body))
    flags, dims, name = sub[0][1], _mat_numbers(*sub[1]), sub[2][1].decode("latin-1")
    word = struct.unpack_from("<I", flags)[0]
    cls = word & 0xFF
    if cls not in (6, 7, 8, 9, 10, 11, 12, 13, 14, 15) or (word >> 11) & 1:
        return name, None                 #: 不是实数数值数组（复数 / 结构体 / 元胞 / 稀疏）：跳过
    v = [float(x) for x in _mat_numbers(*sub[3])]
    if len(dims) != 2:
        return name, v
    nr, nc = dims
    if nr == 1 or nc == 1:
        return name, v
    return name, [[v[j * nr + i] for j in range(nc)] for i in range(nr)]   #: MATLAB 列主序 → 行的列表


def read_mat5(path) -> dict:
    """MATLAB v5 .mat（只用标准库）：miCOMPRESSED 包着的或裸的 miMATRIX，实数数值类。
    返回 {名字: 一维列表 | 行的列表}。v7.3（HDF5）不认，按名拒绝。"""
    b = Path(path).read_bytes()
    if b[:19].startswith(b"MATLAB 7.3"):
        raise SystemExit(f"{path}：MATLAB v7.3（HDF5）格式本工具不读——请存成 -v7 或更早")
    out = {}
    for t, body in _mat_elements(b, 128):
        if t == 15:
            body = zlib.decompress(body)
            for t2, body2 in _mat_elements(body):
                if t2 == 14:
                    k, v = _mat_matrix(body2)
                    if v is not None:
                        out[k] = v
        elif t == 14:
            k, v = _mat_matrix(body)
            if v is not None:
                out[k] = v
    return out


_FNUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][-+]?\d+)?")


def read_afile(path) -> dict:
    """A-EQDSK 的标量（EFIT ``write_a`` 的固定次序；随 ``mco2v`` / ``mco2r`` 变长的四段按第 4 行给的数跳过），
    外加线圈电流 ``ccbrsp``（紧跟在 ``nsilop magpri nfcoil nesum`` 一行之后的环、探针段后面）。
    长度 cm、体积 cm³ 换成 m / m³。★与 kinetic_recon.read_afile 同一段次序（feat/ekr-ref-cases）。"""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    k = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith("*"))
    head = lines[k].split()
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
    out = {"time_s": float(head[1]) / 1e3, "q0": a.get("qqmagx"), "q95": a.get("qpsib"), "li": a.get("ali"),
           "betap": a.get("betap"), "w_mhd": a.get("wplasm"),
           "volume": a["vout"] * 1e-6 if "vout" in a else None,
           "axis_r": a["rmagx"] / 100 if "rmagx" in a else None, "axis_z": a["zmagx"] / 100 if "zmagx" in a else None,
           "ip": a.get("cpasma"), "ip_measured": a.get("pasmat"), "kappa": a.get("eout"), "b0": a.get("bcentr"),
           "chi2": a.get("tsaisq")}
    #: ccbrsp：找「nsilop magpri nfcoil nesum」这一行（四个整数），其后 nsilop + magpri 个数是环与探针，再 nfcoil 个是线圈
    for j in range(k + 1, len(lines)):
        w = lines[j].split()
        if len(w) == 4 and all(re.fullmatch(r"\d+", x) for x in w):
            nsilop, magpri, nfcoil = int(w[0]), int(w[1]), int(w[2])
            rest = [float(x.replace("D", "E")) for x in _FNUM.findall("\n".join(lines[j + 1:]))]
            out["ccbrsp"] = rest[nsilop + magpri:nsilop + magpri + nfcoil]
            break
    return out


def read_gfile(lib: Lib, path) -> dict:
    """G-EQDSK → dict：内核读者的 JSON，外加 R、Z 网格与 ``psi[i][j]``（i 沿 R）与头行里的炮号 / 时刻。"""
    g = lib.gfile(Path(path).read_text(encoding="utf-8", errors="replace"))
    nw, nh = int(g["nw"]), int(g["nh"])
    g["grid_r"] = [g["rleft"] + g["rdim"] * i / (nw - 1) for i in range(nw)]
    g["grid_z"] = [g["zmid"] - 0.5 * g["zdim"] + g["zdim"] * j / (nh - 1) for j in range(nh)]
    ps = g["psirz"]                       #: G-EQDSK 的 psirz：nh 行、每行 nw 个（R 快变）
    g["psi"] = [[ps[j * nw + i] for j in range(nh)] for i in range(nw)]
    m = re.search(r"#\s*(\d+)\s+(\d+)", g.get("header") or "")
    g["shot"] = int(m.group(1)) if m else None
    g["time_s"] = int(m.group(2)) / 1e3 if m else None
    g["boundary"] = [[r, z] for r, z in zip(g["rbbbs"], g["zbbbs"]) if r > 0.0]
    return g


# =========================================================================== #
# 小工具：插值 · 网格上的 ψ
# =========================================================================== #
def interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    k = bisect.bisect_right(xs, x) - 1
    t = (x - xs[k]) / (xs[k + 1] - xs[k])
    return ys[k] + t * (ys[k + 1] - ys[k])


def mean(v):
    v = [x for x in v if x is not None and x == x]
    return sum(v) / len(v) if v else float("nan")


class Map:
    """规则网格上的 ψ：双线性取值与中心差分的梯度（梯度在节点上先算好再双线性插）。"""

    def __init__(self, r, z, psi):
        self.r, self.z, self.psi = r, z, psi
        self.nr, self.nz = len(r), len(z)
        self.dr, self.dz = r[1] - r[0], z[1] - z[0]
        nr, nz = self.nr, self.nz
        self.gr = [[0.0] * nz for _ in range(nr)]
        self.gz = [[0.0] * nz for _ in range(nr)]
        for i in range(nr):
            i0, i1 = max(i - 1, 0), min(i + 1, nr - 1)
            for j in range(nz):
                j0, j1 = max(j - 1, 0), min(j + 1, nz - 1)
                self.gr[i][j] = (psi[i1][j] - psi[i0][j]) / ((i1 - i0) * self.dr)
                self.gz[i][j] = (psi[i][j1] - psi[i][j0]) / ((j1 - j0) * self.dz)

    def _cell(self, r, z):
        fi = min(max((r - self.r[0]) / self.dr, 0.0), self.nr - 1.000001)
        fj = min(max((z - self.z[0]) / self.dz, 0.0), self.nz - 1.000001)
        i, j = int(fi), int(fj)
        return i, j, fi - i, fj - j

    def _bil(self, a, i, j, u, v):
        return ((1 - u) * (1 - v) * a[i][j] + u * (1 - v) * a[i + 1][j]
                + (1 - u) * v * a[i][j + 1] + u * v * a[i + 1][j + 1])

    def at(self, r, z):
        i, j, u, v = self._cell(r, z)
        return self._bil(self.psi, i, j, u, v)

    def grad(self, r, z):
        i, j, u, v = self._cell(r, z)
        return self._bil(self.gr, i, j, u, v), self._bil(self.gz, i, j, u, v)


def _crossings(poly, z):
    """闭合折线与水平线 Z = z 的交点 R（升序）——扫描线的内外判定用。"""
    xs = []
    n = len(poly)
    for k in range(n):
        (r1, z1), (r2, z2) = poly[k], poly[(k + 1) % n]
        if (z1 > z) != (z2 > z):
            xs.append(r1 + (z - z1) * (r2 - r1) / (z2 - z1))
    xs.sort()
    return xs


def _inside(poly, r, z) -> bool:
    xs = _crossings(poly, z)
    return bisect.bisect_right(xs, r) % 2 == 1


def map_integrals(mp: Map, psi_axis, psi_bnd, bnd, psin_1d, pres_1d, per_rad=1.0, sub=3) -> dict:
    """同一把尺量任何一份平衡（kinetic_recon.map_integrals 的做法，扫描线提速）：
    B_p = |∇ψ|/(R·per_rad)；B_pa = ∮B_p dl / L_p；β_p = 2μ₀⟨p⟩_V/B_pa²；l_i(1) = ⟨B_p²⟩_V/B_pa²；
    l_i(3) = 2∫B_p² dV/(μ₀² I_p² R_geo)；I_p = ∮B_p dl/μ₀；W = 3/2∫p dV。``per_rad``：图上的 ψ 除以它才是 Wb/rad。"""
    dr, dz = mp.dr, mp.dz
    vol = w = bp2 = 0.0
    zs = [mp.z[0] + (j + (b + 0.5) / sub - 0.5) * dz for j in range(mp.nz) for b in range(sub)]
    rs = [mp.r[0] + (i + (a + 0.5) / sub - 0.5) * dr for i in range(mp.nr) for a in range(sub)]
    da = abs(dr * dz) / sub ** 2
    span = psi_bnd - psi_axis
    for z in zs:
        xs = _crossings(bnd, z)
        if len(xs) < 2:
            continue
        for q in range(0, len(xs) - 1, 2):
            lo, hi = xs[q], xs[q + 1]
            a0 = bisect.bisect_left(rs, lo)
            a1 = bisect.bisect_right(rs, hi)
            for r in rs[a0:a1]:
                dv = TWO_PI * r * da
                x = min(max((mp.at(r, z) - psi_axis) / span, 0.0), 1.0)
                gR, gZ = mp.grad(r, z)
                b = math.hypot(gR, gZ) / (r * per_rad)
                vol += dv
                w += 1.5 * interp(x, psin_1d, pres_1d) * dv
                bp2 += b * b * dv
    circ = lp = 0.0
    n = len(bnd)
    for k in range(n):
        p, q = bnd[k], bnd[(k + 1) % n]
        dl = math.hypot(q[0] - p[0], q[1] - p[1])
        rm, zm = 0.5 * (p[0] + q[0]), 0.5 * (p[1] + q[1])
        gR, gZ = mp.grad(rm, zm)
        lp += dl
        circ += math.hypot(gR, gZ) / (rm * per_rad) * dl
    bpa = circ / lp
    rgeo = 0.5 * (max(p[0] for p in bnd) + min(p[0] for p in bnd))
    ip = circ / MU0
    return {"volume_m3": vol, "w_mhd_J": w, "betap": 2 * MU0 * (w / 1.5 / vol) / bpa ** 2,
            "li1": bp2 / vol / bpa ** 2, "li3": 2 * bp2 / (MU0 ** 2 * ip ** 2 * rgeo), "ip_ampere_A": ip,
            "r_geo_m": rgeo, "bp_a_T": bpa}


def same_ruler(mp: Map, psi_axis, psi_bnd, bnd, psin_1d, pres_1d, ip_ref) -> dict:
    """``map_integrals``，ψ 图的单位（Wb/rad 还是 Wb）由安培环路还原的 I_p 与 ``ip_ref`` 之比在 1 与 2π 里取对得上的那个。"""
    it = map_integrals(mp, psi_axis, psi_bnd, bnd, psin_1d, pres_1d)
    ratio = it["ip_ampere_A"] / abs(ip_ref)
    per_rad = min((1.0, TWO_PI), key=lambda c: abs(ratio / c - 1.0))
    if per_rad != 1.0:
        it = map_integrals(mp, psi_axis, psi_bnd, bnd, psin_1d, pres_1d, per_rad)
    it["ip_ratio"] = it["ip_ampere_A"] / abs(ip_ref)
    it["psi_map_unit"] = "Wb" if per_rad != 1.0 else "Wb/rad"
    return it


def _seg_dist(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - u * dx, p[1] - a[1] - u * dy)


def boundary_distance(a, b) -> dict:
    """两条闭合边界之间：a 的每个点到 b 这条折线的最近距离（再反过来），取最大与平均 [m]。"""
    def one_way(p, q):
        d = [min(_seg_dist(x, q[i], q[(i + 1) % len(q)]) for i in range(len(q))) for x in p]
        return max(d), mean(d)
    ab, ba = one_way(a, b), one_way(b, a)
    return {"max_m": max(ab[0], ba[0]), "mean_m": 0.5 * (ab[1] + ba[1])}


def psin_difference(ours: Map, oa, ob, obnd, theirs: Map, ta, tb, tbnd) -> dict:
    """ψ_N 图之差：我们的网格点里两条边界都在内的那些，把对方的 ψ_N 双线性插过来相减。"""
    d = []
    for i, r in enumerate(ours.r):
        for j, z in enumerate(ours.z):
            if not (theirs.r[0] <= r <= theirs.r[-1] and theirs.z[0] <= z <= theirs.z[-1]):
                continue
            if _inside(obnd, r, z) and _inside(tbnd, r, z):
                d.append((ours.psi[i][j] - oa) / (ob - oa) - (theirs.at(r, z) - ta) / (tb - ta))
    if not d:
        return {"n_points": 0}
    return {"n_points": len(d), "rms": math.sqrt(mean([x * x for x in d])), "max_abs": max(abs(x) for x in d),
            "mean": mean(d)}


# =========================================================================== #
# 圆环丝的磁场（虚拟线圈对的等效径向场用）
# =========================================================================== #
def _ellipke(m):
    """第一、二类完全椭圆积分 K(m)、E(m)（AGM）。"""
    a, b, s, p = 1.0, math.sqrt(max(1.0 - m, 1e-300)), 1.0 - 0.5 * m, 1.0
    c = 0.5 * m ** 0.5 if m > 0 else 0.0
    s = 1.0 - 0.5 * m
    p = 0.5
    for _ in range(40):
        an, bn = 0.5 * (a + b), math.sqrt(a * b)
        c = 0.5 * (a - b)
        p *= 2.0
        s -= p * c * c
        a, b = an, bn
        if abs(c) < 1e-15:
            break
    k = math.pi / (2.0 * a)
    return k, k * s


def loop_br(rc, zc, r, z):
    """半径 rc、高 zc、1 A 的圆环在 (r, z) 处的 B_R [T/A]。"""
    dz = z - zc
    q = (rc + r) ** 2 + dz * dz
    m = 4.0 * rc * r / q
    k, e = _ellipke(m)
    return MU0 / (2.0 * math.pi) * dz / (r * math.sqrt(q)) * (-k + (rc * rc + r * r + dz * dz) / ((rc - r) ** 2 + dz * dz) * e)


def pair_br(grid_r, grid_z, r, z):
    """内核虚拟竖直线圈对（`equilibrium` 里的 fb_pat：R = 网格中点、Z = ±(z_max + 半高)，+1 A 在上、−1 A 在下）
    在 (r, z) 处每安培的 B_R [T/A]。★位置照内核那段代码；`fb_amp × 它` 就是那对线圈在轴上补的径向场。"""
    r_fb = 0.5 * (grid_r[0] + grid_r[-1])
    z_fb = grid_z[-1] + 0.5 * (grid_z[-1] - grid_z[0])
    return loop_br(r_fb, z_fb, r, z) - loop_br(r_fb, -z_fb, r, z)


# =========================================================================== #
# 装置：线圈通道 · IC · 被动丝
# =========================================================================== #
def _coil_elements(dev: dict):
    """装置文档里线圈的平铺元素序：[(线圈名, 匝数, 是否快控)]——与内核 device_coils 的平铺同序（快控线圈另记）。"""
    out = []
    for c in dev["pf_active"]["coil"]:
        fast = any((f or {}).get("name") == "b_field_fb" for f in (c.get("function") or []))
        for e in c["element"]:
            out.append((c["name"], float(e.get("turns_with_sign") or c.get("turns") or 1.0), fast))
    return out


def channel_table(dev: dict, with_ic: bool = True) -> list:
    """通道表：每个通道 {name, elements: [(线圈名, 匝数, 权)]}，12 个 PF 通道按装置的 ``pf_channel_elements``，
    再接 IC1、IC2 各一个单元素通道（``with_ic``）。通道的安匝 = Σ 元素匝数 × 该线圈的实测单匝电流。"""
    els = [e for e in _coil_elements(dev) if not e[2]]
    chans = []
    for row in dev["pf_channel_elements"]:
        members = [(els[int(m["element"])][0], els[int(m["element"])][1], float(m["weight"])) for m in row]
        chans.append({"name": "+".join(m[0] for m in members), "elements": members})
    if with_ic:
        for c in dev["pf_active"]["coil"]:
            if c["name"] in ("IC1", "IC2"):
                n = float(c["element"][0].get("turns_with_sign") or 1.0)
                chans.append({"name": c["name"], "elements": [(c["name"], n, 1.0)]})
    return chans


def channel_aturns(chans: list, per_turn: dict) -> list:
    return [sum(n * per_turn[name] for name, n, _w in ch["elements"]) for ch in chans]


def filament_contours(r, z, gap=CONTOUR_GAP):
    """按文件里的次序把丝串成轮廓：相邻间距 > gap 就断开；首尾距离 ≤ gap 的轮廓是闭合的。"""
    segs, cur = [], [0]
    for i in range(1, len(r)):
        if math.hypot(r[i] - r[i - 1], z[i] - z[i - 1]) > gap:
            segs.append(cur)
            cur = [i]
        else:
            cur.append(i)
    segs.append(cur)
    return [(s, len(s) > 2 and math.hypot(r[s[0]] - r[s[-1]], z[s[0]] - z[s[-1]]) <= gap) for s in segs]


def filament_strips(r, z, res, rho=RHO_SS, gap=CONTOUR_GAP):
    """每根丝 → 一条沿壁的平行四边形截面（内核的 EFIT 平行四边形约定 [r, z, w, h, a1, a2]）。

    长 ℓ = 到前后两丝距离之半的和（端点丝取到唯一邻丝的距离），方向 = 前后两丝连线；厚 t = 2πrρ/(R_k ℓ)，
    使截面积 ℓt 在电阻率 ρ 下给出**恰好** VVres 的 R_k（内核的元件电阻 = ρ·2πr/(w·h)，w·h = ℓt）。
    陡（45°–135°）的用 a2 剪切（a1 = 0），平的用 a1 剪切（a2 = 90°）。"""
    rows, info = [None] * len(r), [None] * len(r)
    for seg, closed in filament_contours(r, z, gap):
        m = len(seg)
        for k, i in enumerate(seg):
            prev = seg[k - 1] if (k > 0 or closed) else None
            nxt = seg[(k + 1) % m] if (k < m - 1 or closed) else None
            if prev is not None and nxt is not None:
                tr, tz = r[nxt] - r[prev], z[nxt] - z[prev]
                ell = 0.5 * (math.hypot(r[i] - r[prev], z[i] - z[prev]) + math.hypot(r[nxt] - r[i], z[nxt] - z[i]))
            elif prev is not None or nxt is not None:
                j = prev if prev is not None else nxt
                tr, tz = r[j] - r[i], z[j] - z[i]
                ell = math.hypot(tr, tz)
            else:                                 #: 孤立的一根：取 1 cm 见方
                tr, tz, ell = 0.0, 1.0, 0.01
            th = math.degrees(math.atan2(tz, tr)) % 180.0
            t = TWO_PI * r[i] * rho / (res[i] * ell)
            if 45.0 <= th <= 135.0:
                s = math.sin(math.radians(th))
                w, h, a1, a2 = t / s, ell * s, 0.0, th
            else:
                a = th if th < 45.0 else th - 180.0
                c = math.cos(math.radians(a))
                w, h, a1, a2 = ell * c, t / c, a, 90.0
            rows[i] = [r[i], z[i], w, h, a1, a2]
            info[i] = {"length_m": ell, "thickness_m": t, "angle_deg": th}
    return rows, info


def build_device(dev0: dict, case: dict, mode: str, *, ic_rz=None) -> tuple[dict, dict]:
    """装置文档的一份拷贝，改三处：

    * IC1 / IC2：去掉 ``function: b_field_fb``（内核的线圈读者跳过快控线圈），各接成一个单元素通道；
      ``ic_rz`` 给了就改它们的中心 (R, ±Z)。
    * ``mode = induced``：全部丝进 ``pf_passive/efb_vv``（电阻率 ρ，截面由 VVres 反推 → 电阻逐丝等于 VVres）；
    * ``mode = zero | prescribed``：全部丝进 ``pf_active`` 当单匝线圈、各一个通道（电流给定）。
    返回 (装置, 布局 {n_pfic, fil_index, channels})。"""
    dev = json.loads(json.dumps(dev0))
    coils = dev["pf_active"]["coil"]
    for c in coils:
        if c["name"] in ("IC1", "IC2"):
            c.pop("function", None)
            if ic_rz:
                g = c["element"][0]["geometry"]["rectangle"]
                g["r"] = float(ic_rz[0])
                g["z"] = abs(float(ic_rz[1])) * (1.0 if c["name"] == "IC1" else -1.0)
    names = [c["name"] for c in coils for _ in c["element"]]
    rows = list(dev["pf_channel_elements"])
    for ic in ("IC1", "IC2"):
        rows.append([{"element": names.index(ic), "weight": 1.0}])
    vv = case["filaments"]
    strips, _ = filament_strips(vv["r"], vv["z"], vv["resistance"], case["assumptions"]["rho_ohm_m"],
                                case["assumptions"]["contour_gap_m"])
    n_pfic = len(rows)
    if mode == "induced":
        dev.setdefault("pf_passive", {})
        dev["pf_passive"] = dict(dev["pf_passive"])
        dev["pf_passive"]["efb_vv"] = {"resistivity_uohm_m": case["assumptions"]["rho_ohm_m"] * 1e6, "element": strips}
        fil = list(range(n_pfic, n_pfic + len(strips)))
    else:
        base = len(names)
        for k, s in enumerate(strips):
            coils.append({"name": f"VV{k + 1:03d}", "element": [{
                "geometry": {"rectangle": {"r": s[0], "z": s[1], "width": s[2], "height": s[3]}},
                "fylite:a1": s[4], "fylite:a2": s[5], "turns_with_sign": 1.0}],
                "resistance": vv["resistance"][k]})
            rows.append([{"element": base + k, "weight": 1.0}])
        fil = list(range(n_pfic, n_pfic + len(strips)))
    dev["pf_channel_elements"] = rows
    return dev, {"n_pfic": n_pfic, "fil_index": fil}


def geometry_block(dev0: dict, shot: int, chain: str, ic_rz=None, case: dict | None = None, ic_figure=None) -> dict:
    """截面要画的几何，全部取这一炮、这条测量链解析出的装置文档（与交给内核的是同一份），不补任何尺寸：

    * ``pf_coils``：PF 线圈的元素（名字、所属通道、中心 r/z、宽 dr、高 dz、匝数、平行四边形角 a1/a2）；
      通道名与 ``run`` 输出的 ``channels.names`` 同序同名（PF7+PF9、PF8+PF10 两个元素同一个通道）；
    * ``ic_coils``：IC1 / IC2 **这一次实际用的**位置（``position_from`` = ``facts`` 或 ``--ic-rz``），另记装置事实的原位置；
      ``ic_figure``（``geometry --ic-figure-rz``）只作记录（``figure_rz``，未用）；
    * ``limiter``：装置事实里的限制器轮廓；
    * ``filament_contours``：给了 ``case`` 才有（丝的坐标来自数据，不来自事实）。"""
    chans = channel_table(dev0, with_ic=True)
    where = {}
    for ci, ch in enumerate(chans):
        for name, _n, w in ch["elements"]:
            where.setdefault(name, []).append((ci, ch["name"], w))
    pa = dev0["pf_active"]
    pf, ic = [], []
    for c in pa["coil"]:
        fast = c["name"] in ("IC1", "IC2")
        for e in c["element"]:
            rect = (e.get("geometry") or {}).get("rectangle") or {}
            ci, cname, _w = (where.get(c["name"]) or [(None, None, None)])[0]
            row = {"name": c["name"], "r": rect.get("r"), "z": rect.get("z"), "dr": rect.get("width"), "dz": rect.get("height"),
                   "turns": e.get("turns_with_sign", c.get("turns")), "a1": e.get("fylite:a1"), "a2": e.get("fylite:a2"),
                   "channel": cname, "channel_index": ci}
            if fast:
                row["facts_rz"] = [row["r"], row["z"]]
                row["position_from"] = "facts"
                if ic_rz:
                    row["r"] = float(ic_rz[0])
                    row["z"] = abs(float(ic_rz[1])) * (1.0 if c["name"] == "IC1" else -1.0)
                    row["position_from"] = "--ic-rz"
                if ic_figure:
                    row["figure_rz"] = [float(ic_figure[0]), abs(float(ic_figure[1])) * (1.0 if c["name"] == "IC1" else -1.0)]
                ic.append(row)
            else:
                pf.append(row)
    lim = None
    for d2 in ((dev0.get("wall") or {}).get("description_2d") or []):
        for u in ((d2.get("limiter") or {}).get("unit") or []):
            o = u.get("outline") or {}
            if o.get("r") and o.get("z"):
                lim = {"r": o["r"], "z": o["z"], "unit": u.get("name")}
                break
        if lim:
            break
    out = {
        "source": {"device": dev0.get("@id"), "basis": dev0.get("_basis"), "shot": int(shot), "measurement_chain": chain,
                   "valid_shots": dev0.get("_valid_shots"), "pf_active": pa.get("fylite:source"),
                   "wall": (dev0.get("wall") or {}).get("fylite:source")},
        "pf_coils": pf, "ic_coils": ic, "limiter": lim,
        "channels": [ch["name"] for ch in chans],
    }
    if ic_figure:
        out["ic_figure_note"] = "figure_rz：调用方给的数据附图位置，只作记录；这一次用的是 r/z（position_from）"
    if case:
        f = case["filaments"]
        out["filament_contours"] = [[sg[0], sg[-1], c] for sg, c in filament_contours(f["r"], f["z"], case["assumptions"]["contour_gap_m"])]
    return out


# =========================================================================== #
# prepare：数据目录 → 一份输入文档
# =========================================================================== #
def cmd_prepare(a) -> None:
    d = Path(a.data_dir)
    lib = Lib(Path(a.lib))
    gpath = Path(a.gfile) if a.gfile else next(iter(sorted(d.glob("g*.*"))), None)
    if gpath is None:
        raise SystemExit(f"{d} 里没有 g-file")
    apath = Path(a.afile) if a.afile else d / ("a" + gpath.name[1:])
    g = read_gfile(lib, gpath)
    af = read_afile(apath) if apath.is_file() else None
    mdp = next(iter(sorted(d.glob(a.magdata))), None)
    if mdp is None:
        raise SystemExit(f"{d} 里没有 {a.magdata}")
    a.magdata = mdp.name
    md = read_mat5(mdp)
    vvp = read_mat5(d / a.vv_position)
    vres = read_mat5(d / a.vv_res)
    for k in ("pf", "ip", "t"):
        if k not in md:
            raise SystemExit(f"{a.magdata} 里没有变量 {k}")
    pf = md["pf"]
    if not pf or len(pf[0]) != len(MAGDATA_COILS):
        raise SystemExit(f"pf 应是 [nt, {len(MAGDATA_COILS)}]（PF1–14 · IC1–2），得到 {len(pf)} × {len(pf[0]) if pf else 0}")
    rv, zv = vvp.get("r_vv"), vvp.get("z_vv")
    rk = next(iter(v for k, v in vres.items() if isinstance(v, list)), None)
    if not (rv and zv and rk and len(rv) == len(zv) == len(rk)):
        raise SystemExit("vv_position / VVres 的长度对不上")
    nw = int(g["nw"])
    x = [i / (nw - 1) for i in range(nw)]
    t0 = g["time_s"] if g["time_s"] is not None else (af or {}).get("time_s")
    case = {
        "@type": "fylite:EastFreeBoundaryCase", "app": APP, "version": VERSION,
        "shot": g["shot"], "device": "east",
        "sources": {"gfile": gpath.name, "afile": apath.name if af else None, "magdata": a.magdata,
                    "vv_position": a.vv_position, "vv_res": a.vv_res},
        #: ★magdata 的 t 从 0 起：约定它是相对 g-file 时刻的偏移（校验：ip[0] 与 a-file 的实测 Ip 一致）
        "time_origin_s": t0,
        "magdata": {"t": md["t"], "ip": md["ip"], "pf": pf, "columns": MAGDATA_COILS,
                    "betap": md.get("betap"), "li": md.get("li")},
        "gfile": {k: g[k] for k in ("header", "nw", "nh", "rdim", "zdim", "rcentr", "rleft", "zmid", "rmaxis",
                                    "zmaxis", "simag", "sibry", "bcentr", "current", "fpol", "pres", "ffprim",
                                    "pprime", "qpsi", "rbbbs", "zbbbs", "rlim", "zlim", "psirz", "time_s")},
        "afile": af,
        "profile": {"psi_norm": x, "dpressure_dpsi": g["pprime"], "f_df_dpsi": g["ffprim"]},
        "filaments": {"r": rv, "z": zv, "resistance": rk},
        "assumptions": {"rho_ohm_m": a.rho * 1e-6, "contour_gap_m": a.contour_gap},
    }
    case["geometry"] = geometry_block(lib.device("east", g["shot"], "east"), g["shot"], "east", None, case)
    ipm = (af or {}).get("ip_measured")
    case["checks"] = {"ip0_magdata_A": md["ip"][0], "ip_measured_afile_A": ipm,
                      "ip0_rel_diff": (md["ip"][0] / ipm - 1.0) if ipm else None}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    _write_json(a.output, case)
    log(f"prepare: #{g['shot']} t0 = {t0} s · magdata {len(md['t'])} 点 {md['t'][0]}–{md['t'][-1]} s · "
        f"{len(rv)} 根被动丝 → {a.output}")


# =========================================================================== #
# 求解：t0 的单次解 · 演化
# =========================================================================== #
def eq_inputs(case: dict, psi_warm=None, profile=None) -> dict:
    p = profile or case["profile"]
    ts = {"profiles_1d": {"psi_norm": p["psi_norm"], "dpressure_dpsi": p["dpressure_dpsi"], "f_df_dpsi": p["f_df_dpsi"]}}
    if psi_warm is not None:
        ts["profiles_2d"] = {"psi": psi_warm}
    return {"time_slice": ts}


def box_settings(a) -> dict:
    return {"nw": a.grid, "nh": a.grid} if getattr(a, "grid", None) else {}


def per_turn_at(case: dict, k: int, frac: float = 0.0, k1: int | None = None) -> dict:
    """magdata 第 k 行（frac > 0 时向 k1 行线性插值）→ {线圈名: 单匝电流 [A/turn]}。"""
    row = case["magdata"]["pf"][k]
    if frac and k1 is not None:
        r1 = case["magdata"]["pf"][k1]
        row = [x + frac * (y - x) for x, y in zip(row, r1)]
    return dict(zip(case["magdata"]["columns"], row))


def forward_at(lib, dev, case, aturns, ip, zc, a, psi_warm=None, profile=None):
    s = dict(SOLVE, ip=ip, zc_anchor=zc, relax=a.relax, max_iter=a.max_iter, tol=a.tol, **box_settings(a))
    return lib.door("code/forward", s, {"device": dev, "equilibrium": eq_inputs(case, psi_warm, profile),
                                        "discharge": {"fylite:channel_aturns": aturns}})


def free_zc(lib, dev, case, aturns, ip, a, lo=-0.05, hi=0.05, profile=None) -> tuple[float, dict]:
    """t0 处「虚拟竖直线圈对不出力」的电流中心高度：对 ``zc_anchor`` 二分 ``fb_amp = 0``（先粗扫找变号）。

    ★为什么要找：实测线圈电流给出的平衡在竖直方向是不稳定的，不钉位置的自由边界迭代在电流自己的平衡附近
    ±1 cm 来回跳、不收敛（README §5.1）；钉在「对不出力」的那个高度，得到的就是这组电流自己的平衡。"""
    grid = [lo + (hi - lo) * k / 10 for k in range(11)]
    vals = []
    for z in grid:
        try:
            fa, _, _ = forward_at(lib, dev, case, aturns, ip, z, a, profile=profile)
            vals.append((z, fa["fb_amp"], fa))
        except Refused:
            continue
    br = next(((p, q) for p, q in zip(vals, vals[1:]) if (p[1] > 0) != (q[1] > 0)), None)
    if br is None:
        best = min(vals, key=lambda v: abs(v[1]))
        return best[0], {"bracketed": False, "fb_amp": best[1], "scan": [[v[0], v[1]] for v in vals]}
    (z0, f0, _), (z1, f1, _) = br
    for _ in range(14):
        zm = 0.5 * (z0 + z1)
        fa, _, _ = forward_at(lib, dev, case, aturns, ip, zm, a, profile=profile)
        if (fa["fb_amp"] > 0) == (f0 > 0):
            z0, f0 = zm, fa["fb_amp"]
        else:
            z1, f1 = zm, fa["fb_amp"]
    z = z0 - f0 * (z1 - z0) / (f1 - f0) if f1 != f0 else 0.5 * (z0 + z1)
    return z, {"bracketed": True, "fb_amp_bracket": [f0, f1], "scan": [[v[0], v[1]] for v in vals]}


def march_times(case: dict, a) -> tuple[list, list]:
    """演化的时刻：magdata 在 [t_start, t_end] 内每隔 ``stride`` 个点取一个，每段再等分成 ``substeps`` 步。
    返回 (t 列表, 每一时刻的 (k, frac, k1))。"""
    t = case["magdata"]["t"]
    ks = [k for k in range(len(t)) if a.t_start - 1e-12 <= t[k] <= a.t_end + 1e-12][::a.stride]
    if len(ks) < 2:
        raise SystemExit(f"[{a.t_start}, {a.t_end}] 里 magdata 不足两个点")
    times, where = [t[ks[0]]], [(ks[0], 0.0, None)]
    for k0, k1 in zip(ks, ks[1:]):
        for s in range(1, a.substeps + 1):
            f = s / a.substeps
            times.append(t[k0] + f * (t[k1] - t[k0]))
            where.append((k1, 0.0, None) if s == a.substeps else (k0, f, k1))
    return times, where


def load_prescribed(path: str, times: list, n_fil: int) -> list:
    """给定的被动丝电流：JSON {"t": [...], "current": [[n_fil] × nt]}（或本工具 run 的输出，取其 sources.current_A）。
    按时刻线性插值到演化的时刻上；范围外取端值。"""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if "sources" in d and "current_A" in d["sources"]:
        tt, cc = d["time"], d["sources"]["current_A"]
    else:
        tt, cc = d["t"], d["current"]
    if any(len(row) != n_fil for row in cc):
        raise SystemExit(f"{path}：每一行应有 {n_fil} 个电流")
    out = []
    for t in times:
        out.append([interp(t, tt, [row[i] for row in cc]) for i in range(n_fil)])
    return out


def run_march(lib, case, dev, lay, times, where, a, mode, zc, passive0=None, prescribed=None, profile=None):
    """一次 ``code/evolve_free_boundary``（电流驱动 · 内耦合 · 钉竖直位置 · 每步留 ψ）。"""
    chans = channel_table(dev, with_ic=True)[:lay["n_pfic"]]
    at = []
    for m, (k, f, k1) in enumerate(where):
        row = channel_aturns(chans, per_turn_at(case, k, f, k1))
        if mode != "induced":
            row = row + (list(prescribed[m]) if prescribed is not None else [0.0] * len(lay["fil_index"]))
        at.append(row)
    ip = []
    for (k, f, k1) in where:
        v = case["magdata"]["ip"][k]
        if f and k1 is not None:
            v += f * (case["magdata"]["ip"][k1] - v)
        ip.append(v)
    st = dict(SOLVE, drive="current", passive="efb_vv" if mode == "induced" else "none", keep_psi=1,
              relax=a.relax, max_iter=a.max_iter, tol=a.tol, **box_settings(a))
    if zc is not None:
        st["zc_anchor"] = zc
    else:
        st.pop("fb_gain")
    pulse = {"fylite:time": times, "fylite:channel_aturns": at, "fylite:ip": ip}
    if mode == "induced" and passive0 is not None:
        pulse["fylite:passive_current"] = passive0
    t0 = time.time()
    fa, fi, notes = lib.door("code/evolve_free_boundary", st,
                             {"device": dev, "equilibrium": eq_inputs(case, profile=profile), "pulse": pulse})
    return {"facts": fa, "fields": fi, "notes": notes, "seconds": time.time() - t0, "aturns": at, "ip": ip,
            "settings": st}


# =========================================================================== #
# 每一步的后处理：边界 · q · 剖面（code/summary）+ 同尺积分 + 丝处磁通
# =========================================================================== #
def f_edge_of(case) -> float:
    g = case["gfile"]
    return g["bcentr"] * g["rcentr"]


def summarize(lib, dev, case, grid_r, grid_z, psi_flat, facts: dict, a, profile=None) -> dict:
    """一步的平衡 → code/summary 的边界 · 形状 · q · p · F，再加同尺积分。"""
    nr, nz = len(grid_r), len(grid_z)
    p = profile or case["profile"]
    eq = {"time_slice": {
        "profiles_2d": {"psi": psi_flat},
        "global_quantities": {"psi_axis": facts["psi_axis"], "psi_boundary": facts["psi_bnd"], "ip": facts["ip"],
                              "magnetic_axis": {"r": facts["axis_r"], "z": facts["axis_z"]}},
        "profiles_1d": {"psi_norm": p["psi_norm"], "dpressure_dpsi": p["dpressure_dpsi"], "f_df_dpsi": p["f_df_dpsi"]}}}
    st = {"jc": facts["jc"], "f_edge": f_edge_of(case), "r_centre": case["gfile"]["rcentr"], "inset": 1e-3,
          "n_boundary": 181, "n_q": 41, "x_lo": 0.02, "x_hi": 0.995, "n_segments": 0, **box_settings(a)}
    sf, sfi, _ = lib.door("code/summary", st, {"device": dev, "equilibrium": eq})
    lc = flat(sfi["lcfs"])
    bnd = [[lc[2 * i], lc[2 * i + 1]] for i in range(len(lc) // 2)]
    psi = [[psi_flat[i * nz + j] for j in range(nz)] for i in range(nr)]
    mp = Map(grid_r, grid_z, psi)
    it = same_ruler(mp, facts["psi_axis"], facts["psi_bnd"], bnd, flat(sfi["psin_1d"]), flat(sfi["pres"]), facts["ip"])
    shape = flat(sfi["shape"])
    xp = flat(sfi.get("xpts") or [])
    return {"boundary": bnd, "map": mp, "q_x": flat(sfi.get("q_x") or []), "q": [abs(v) for v in flat(sfi.get("q") or [])],
            "q0": abs(sf.get("q0", float("nan"))), "q95": abs(sf.get("q95", float("nan"))),
            "li3_summary": sf.get("li3"), "psin_1d": flat(sfi["psin_1d"]), "pres": flat(sfi["pres"]),
            "fpol": flat(sfi.get("fpol") or []), "pprime": flat(sfi["pprime"]), "ffprim": flat(sfi["ffprim"]),
            "shape": {"r0": shape[0], "a": shape[1], "kappa": shape[2], "delta_upper": shape[3],
                      "delta_lower": shape[4], "z0": shape[5]},
            "xpoints": [xp[4 * i:4 * i + 4] for i in range(len(xp) // 4)], "integrals": it}


def write_gfile(path: Path, case, s: dict, facts: dict, grid_r, grid_z, sigma: float, t_abs: float, ip: float, lim) -> None:
    """一步写成 G-EQDSK（ψ 取输入 g-file 的约定：Wb/rad、符号 ``sigma``；p′、FF′ 由 p、F²/2 对 ψ 差分）。"""
    nw, nh = len(grid_r), len(grid_z)
    x = [i / (nw - 1) for i in range(nw)]
    sim, sib = sigma * facts["psi_axis"] / TWO_PI, sigma * facts["psi_bnd"] / TWO_PI
    pres = [interp(v, s["psin_1d"], s["pres"]) for v in x]
    fpol = [interp(v, s["psin_1d"], s["fpol"]) for v in x] if s["fpol"] else [f_edge_of(case)] * nw
    dpsi = (sib - sim) / (nw - 1)

    def deriv(y):
        return [((y[min(i + 1, nw - 1)] - y[max(i - 1, 0)]) / ((min(i + 1, nw - 1) - max(i - 1, 0)) * dpsi)) for i in range(nw)]
    pprime = deriv(pres)
    ffprim = deriv([0.5 * f * f for f in fpol])
    qpsi = [interp(v, s["q_x"], s["q"]) for v in x] if s["q"] else [0.0] * nw
    mp = s["map"]
    psirz = [sigma * mp.psi[i][j] / TWO_PI for j in range(nh) for i in range(nw)]
    bnd = s["boundary"]
    rdim, zdim = grid_r[-1] - grid_r[0], grid_z[-1] - grid_z[0]
    zmid = 0.5 * (grid_z[0] + grid_z[-1])
    g = case["gfile"]

    def block(vals):
        out = []
        for i in range(0, len(vals), 5):
            out.append("".join(f"{v:16.9E}" for v in vals[i:i + 5]))
        return "\n".join(out) + "\n"
    head = f"  FYLITE  fbevo  #{case['shot']:6d}  {int(round(t_abs * 1000)):5d}ms"
    txt = f"{head:<48s}{3:4d}{nw:4d}{nh:4d}\n"
    txt += block([rdim, zdim, g["rcentr"], grid_r[0], zmid])
    txt += block([facts["axis_r"], facts["axis_z"], sim, sib, g["bcentr"]])
    txt += block([ip, sim, 0.0, facts["axis_r"], 0.0])
    txt += block([facts["axis_z"], 0.0, sib, 0.0, 0.0])
    txt += block(fpol) + block(pres) + block(ffprim) + block(pprime) + block(psirz) + block(qpsi)
    txt += f"{len(bnd):5d}{len(lim):5d}\n"
    txt += block([v for p in bnd for v in p]) + block([v for p in lim for v in p])
    path.write_text(txt, encoding="ascii")


# =========================================================================== #
# initial：校验 1
# =========================================================================== #
def reference(case: dict) -> dict:
    """输入 g-file（+ a-file）按同一把尺量出来的一份「对方」。"""
    g = case["gfile"]
    nw, nh = g["nw"], g["nh"]
    r = [g["rleft"] + g["rdim"] * i / (nw - 1) for i in range(nw)]
    z = [g["zmid"] - 0.5 * g["zdim"] + g["zdim"] * j / (nh - 1) for j in range(nh)]
    psi = [[g["psirz"][j * nw + i] for j in range(nh)] for i in range(nw)]
    mp = Map(r, z, psi)
    bnd = [[a, b] for a, b in zip(g["rbbbs"], g["zbbbs"]) if a > 0]
    x = [i / (nw - 1) for i in range(nw)]
    it = same_ruler(mp, g["simag"], g["sibry"], bnd, x, g["pres"], g["current"])
    return {"map": mp, "boundary": bnd, "psi_axis": g["simag"], "psi_bnd": g["sibry"],
            "axis": [g["rmaxis"], g["zmaxis"]], "q95": interp(0.95, x, [abs(v) for v in g["qpsi"]]),
            "q0": abs(g["qpsi"][0]), "integrals": it, "afile": case.get("afile")}


def compare_equilibria(ours: dict, facts: dict, theirs: dict) -> dict:
    it, jt = ours["integrals"], theirs["integrals"]
    af = theirs.get("afile") or {}
    return {
        "axis_ours_m": [facts["axis_r"], facts["axis_z"]], "axis_ref_m": theirs["axis"],
        "axis_distance_m": math.hypot(facts["axis_r"] - theirs["axis"][0], facts["axis_z"] - theirs["axis"][1]),
        "boundary_distance": boundary_distance(ours["boundary"], theirs["boundary"]),
        "psin_map_difference": psin_difference(ours["map"], facts["psi_axis"], facts["psi_bnd"], ours["boundary"],
                                               theirs["map"], theirs["psi_axis"], theirs["psi_bnd"], theirs["boundary"]),
        "q95": {"ours": ours["q95"], "ref_gfile": theirs["q95"], "ref_afile": af.get("q95")},
        "q0": {"ours": ours["q0"], "ref_gfile": theirs["q0"], "ref_afile": af.get("q0")},
        "li1_same_ruler": {"ours": it["li1"], "ref": jt["li1"]},
        "li3_same_ruler": {"ours": it["li3"], "ref": jt["li3"]},
        "li_afile": af.get("li"),
        "betap_same_ruler": {"ours": it["betap"], "ref": jt["betap"]}, "betap_afile": af.get("betap"),
        "w_mhd_J": {"ours": it["w_mhd_J"], "ref": jt["w_mhd_J"], "afile": af.get("w_mhd")},
        "volume_m3": {"ours": it["volume_m3"], "ref": jt["volume_m3"], "afile": af.get("volume")},
        "kappa": {"ours": ours["shape"]["kappa"], "afile": af.get("kappa")},
        "ip_ampere_loop_A": {"ours": it["ip_ampere_A"], "ref": jt["ip_ampere_A"]},
    }


def cmd_initial(a) -> None:
    case = json.loads(Path(a.case).read_text(encoding="utf-8"))
    lib = Lib(Path(a.lib))
    dev0 = lib.device("east", case["shot"], "east")
    dev, lay = build_device(dev0, case, "zero", ic_rz=a.ic_rz)
    chans = channel_table(dev, with_ic=True)[:lay["n_pfic"]]
    nfil = len(lay["fil_index"])
    theirs = reference(case)
    out = {"@type": "fylite:EastFreeBoundaryInitial", "app": APP, "version": VERSION, "kernel": lib.linked_kernel(),
           "shot": case["shot"], "time_s": case["time_origin_s"], "variants": {}}
    variants = [("magdata", channel_aturns(chans, per_turn_at(case, 0)), case["magdata"]["ip"][0])]
    af = case.get("afile") or {}
    if af.get("ccbrsp") and len(af["ccbrsp"]) >= 12:
        #: 诊断：EFIT 自己拟合的 12 路线圈安匝（BRSP 序 = 装置通道序），IC 取 magdata；Ip 取 EFIT 的 cpasma
        ic = channel_aturns(chans, per_turn_at(case, 0))[12:]
        variants.append(("afile_ccbrsp", list(af["ccbrsp"][:12]) + ic, af.get("ip") or case["magdata"]["ip"][0]))
    for name, at, ip in variants:
        at_full = at + [0.0] * nfil
        zc, how = free_zc(lib, dev, case, at_full, ip, a)
        fa, fi, notes = forward_at(lib, dev, case, at_full, ip, zc, a)
        gr, gz = flat(fi["grid_r"]), flat(fi["grid_z"])
        s = summarize(lib, dev, case, gr, gz, flat(fi["psi"]), fa, a)
        cmpd = compare_equilibria(s, fa, theirs)
        br_pair = fa["fb_amp"] * pair_br(gr, gz, fa["axis_r"], fa["axis_z"])
        out["variants"][name] = {
            "channel_aturns": at, "channels": [c["name"] for c in chans], "ip_A": ip,
            "zc_free_m": zc, "zc_search": how,
            "solve": {k: fa.get(k) for k in ("converged", "iterations", "residual", "fb_amp", "zc", "bnd_kind",
                                             "xpt_r", "xpt_z", "psi_axis", "psi_bnd", "jc")},
            "pair_br_at_axis_T": br_pair, "compare": cmpd, "shape": s["shape"],
            "boundary": s["boundary"], "notes": notes}
        log(f"initial[{name}]: zc_free = {zc:+.4f} m · 轴 ({fa['axis_r']:.4f}, {fa['axis_z']:+.4f}) vs "
            f"({theirs['axis'][0]:.4f}, {theirs['axis'][1]:+.4f}) · 边界差 max {cmpd['boundary_distance']['max_m'] * 100:.1f} cm · "
            f"ψN rms {cmpd['psin_map_difference'].get('rms', float('nan')):.3f} · q95 {s['q95']:.2f}/{theirs['q95']:.2f} · "
            f"li1 {s['integrals']['li1']:.3f}/{theirs['integrals']['li1']:.3f} · βp {s['integrals']['betap']:.3f}/"
            f"{theirs['integrals']['betap']:.3f}")
    ref = theirs["integrals"]
    out["reference"] = {"axis": theirs["axis"], "q95": theirs["q95"], "q0": theirs["q0"], "integrals": ref,
                        "afile": case.get("afile"), "boundary": theirs["boundary"]}
    out["limiter"] = {"r": case["gfile"]["rlim"], "z": case["gfile"]["zlim"]}      #: 结果页画截面用
    out["geometry"] = geometry_block(dev0, case["shot"], "east", a.ic_rz, case)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    _write_json(a.output, out, indent=1)


# =========================================================================== #
# run：演化
# =========================================================================== #
def ramp_currents(fr: dict, lay: dict, res: list, n_fit: int) -> list:
    """「稳态斜坡」起始电流：零被动电流的一段短演化给出各丝处的磁通 Ψ_k(t)（线圈 + 等离子体），
    用前 ``n_fit`` 个点的最小二乘斜率，I_k = −(dΨ_k/dt)/R_k——匀速变化下被动电流的稳态解（丝间互感项 M dI/dt → 0）。"""
    fi = fr["fields"]
    n = int(fr["facts"]["n_channels"] + fr["facts"]["n_passive"])
    nt = len(flat(fi["time"]))
    m = flat(fi["m"])
    cur = flat(fi["currents"])
    pfl = flat(fi["plasma_flux"])
    t = flat(fi["time"])[:n_fit]
    out = []
    for q, i in enumerate(lay["fil_index"]):
        psi = []
        for k in range(min(n_fit, nt)):
            own = sum(m[i * n + j] * cur[k * n + j] for j in range(n) if j != i)
            psi.append(own + pfl[k * n + i])
        tm, pm = mean(t), mean(psi)
        slope = sum((a - tm) * (b - pm) for a, b in zip(t, psi)) / sum((a - tm) ** 2 for a in t)
        out.append(-slope / res[q])
    return out


def profile_family(base: dict, kappa: float, gamma: float) -> dict:
    """g-file 剖面形状的两参数族：p′ → h·p′_g，FF′ → κ·h·FF′_g，h(ψ_N) = exp(γ(1 − ψ_N))。
    κ 调 FF′ 对 p′ 的比（κ 降 → β_p 升；κ < 0 即反磁的 FF′，β_p 才能越过「电流全由 p′ 承载」的上限），
    γ > 0 把电流往轴上收（→ l_i 升）、γ < 0 往外推。整体标度由内核按 I_p 定。"""
    h = [math.exp(gamma * (1.0 - x)) for x in base["psi_norm"]]
    return {"psi_norm": base["psi_norm"], "dpressure_dpsi": [v * w for v, w in zip(base["dpressure_dpsi"], h)],
            "f_df_dpsi": [kappa * v * w for v, w in zip(base["f_df_dpsi"], h)], "kappa": kappa, "gamma": gamma}


def trace_at(case: dict, name: str, k: int, f: float = 0.0, k1=None):
    """magdata 的 EFIT 参考迹（betap / li）在第 k 点（向 k1 插值）；NaN 取最近的有值点。"""
    tr = case["magdata"].get(name)
    if not tr:
        return None

    def val(i):
        if tr[i] == tr[i]:
            return tr[i]
        for d in range(1, len(tr)):
            for j in (i - d, i + d):
                if 0 <= j < len(tr) and tr[j] == tr[j]:
                    return tr[j]
        return None
    v = val(k)
    return v + f * (val(k1) - v) if (f and k1 is not None) else v


def fit_profile(lib, fdev, case, aturns, ip, zc, target, start, a) -> tuple[dict, dict]:
    """在给定电流（含被动丝，作通道）下找 (κ, γ) 使同尺 (β_p, l_i(1)) = target：有限差分牛顿，
    最多 8 步、|Δβ_p|, |Δl_i| < 0.005 即停；达不到就留最好的一步并记下残差。返回 (剖面, 记录)。"""
    base = case["profile"]

    def ev(kp, g):
        prof = profile_family(base, kp, g)
        try:
            fa, fi, _ = forward_at(lib, fdev, case, aturns, ip, zc, a, profile=prof)
            s = summarize(lib, fdev, case, flat(fi["grid_r"]), flat(fi["grid_z"]), flat(fi["psi"]), fa, a, profile=prof)
        except (Refused, KernelError, KeyError):
            return None
        return s["integrals"]["betap"], s["integrals"]["li1"]
    kp, g = start
    hist, best = [], None
    for it in range(8):
        v = ev(kp, g)
        if v is None:
            break
        bp, li = v
        err = math.hypot(bp - target[0], li - target[1])
        hist.append([kp, g, bp, li])
        if best is None or err < best[0]:
            best = (err, kp, g, bp, li)
        e = (bp - target[0], li - target[1])
        if abs(e[0]) < 0.005 and abs(e[1]) < 0.005:
            break
        d = 0.03
        v1, v2 = ev(kp + d, g), ev(kp, g + d)
        if v1 is None or v2 is None:
            break
        jm = [[(v1[0] - bp) / d, (v2[0] - bp) / d], [(v1[1] - li) / d, (v2[1] - li) / d]]
        det = jm[0][0] * jm[1][1] - jm[0][1] * jm[1][0]
        if abs(det) < 1e-12:
            break
        dk = -(jm[1][1] * e[0] - jm[0][1] * e[1]) / det
        dg = -(-jm[1][0] * e[0] + jm[0][0] * e[1]) / det
        step = max(abs(dk) / 0.4, abs(dg) / 1.0, 1.0)            #: 限步：κ 每步 ≤ 0.4、γ ≤ 1
        kp = min(max(kp + dk / step, -3.0), 3.0)
        g = min(max(g + dg / step, -3.0), 8.0)
    if best is None:
        raise Refused(f"profile fit: no solvable profile near kappa {start[0]}, gamma {start[1]}")
    _, kp, g, bp, li = best
    return profile_family(base, kp, g), {"target": list(target), "history": hist, "kappa": kp, "gamma": g,
                                         "betap": bp, "li1": li}


def merge_marches(parts: list) -> dict:
    """分段演化的记录接成一份：后一段的第一个时刻就是前一段的最后一个时刻，丢掉重复的那一个。"""
    first = parts[0]
    n = int(first["facts"]["n_channels"] + first["facts"]["n_passive"])
    gr, gz = flat(first["fields"]["grid_r"]), flat(first["fields"]["grid_z"])
    plane = len(gr) * len(gz)
    keys = ("ip", "axis_r", "axis_z", "zc", "psi_axis", "psi_boundary", "fb_amp", "gs_state", "gs_residual",
            "picard_iterations", "jc", "bnd_kind", "xpt_r", "xpt_z", "circuit_residual")
    out = {"rows": {k: [] for k in keys}, "psi_t": [], "currents": [], "plasma_flux": [], "aturns": [], "ip_target": [],
           "profile_index": [], "n": n, "m": flat(first["fields"]["m"]), "grid_r": gr, "grid_z": gz, "plane": plane,
           "seconds": 0.0, "notes": [], "facts": [], "settings": first["settings"]}
    for si, r in enumerate(parts):
        fi = r["fields"]
        nt = len(flat(fi["time"]))
        skip = 0 if si == 0 else 1
        for k in keys:
            out["rows"][k].extend(flat(fi[k])[skip:])
        out["psi_t"].extend(flat(fi["psi_t"])[skip * plane:])
        out["currents"].extend(flat(fi["currents"])[skip * n:])
        out["plasma_flux"].extend(flat(fi["plasma_flux"])[skip * n:])
        out["aturns"].extend(r["aturns"][skip:])
        out["ip_target"].extend(r["ip"][skip:])
        out["profile_index"].extend([si] * (nt - skip))
        out["seconds"] += r["seconds"]
        out["notes"].extend(n_ for n_ in r["notes"] if n_ not in out["notes"])
        out["facts"].append(r["facts"])
    return out


def cmd_run(a) -> None:
    case = json.loads(Path(a.case).read_text(encoding="utf-8"))
    lib = Lib(Path(a.lib))
    dev0 = lib.device("east", case["shot"], "east")
    mode = a.passive
    dev, lay = build_device(dev0, case, mode, ic_rz=a.ic_rz)
    fdev, flay = build_device(dev0, case, "zero", ic_rz=a.ic_rz)   #: t0 的单次解与剖面拟合都在「丝当线圈」的装置上
    fchans = channel_table(fdev)[:flay["n_pfic"]]
    nfil = len(lay["fil_index"])
    res = case["filaments"]["resistance"]
    times, where = march_times(case, a)
    nt = len(times)
    prescribed = load_prescribed(a.passive_file, times, nfil) if mode == "prescribed" else None
    notes_app = []
    ip_at = lambda k, f, k1: case["magdata"]["ip"][k] + (f * (case["magdata"]["ip"][k1] - case["magdata"]["ip"][k])  # noqa: E731
                                                         if (f and k1 is not None) else 0.0)

    # ---- 被动丝的起始电流 ----
    passive0 = [0.0] * nfil
    if mode == "induced" and a.passive_init == "ramp":
        n_fit = max(3, int(round(a.ramp_window / max(times[1] - times[0], 1e-9))) + 1)
        log(f"run[{mode}]: 斜坡起始电流——先跑 {n_fit} 步零被动电流的短演化取 dΨ/dt")
        at_z = channel_aturns(fchans, per_turn_at(case, 0)) + [0.0] * nfil
        zc0, _ = free_zc(lib, fdev, case, at_z, case["magdata"]["ip"][0], a)
        fr = run_march(lib, case, fdev, flay, times[:n_fit], where[:n_fit], a, "zero", zc0)
        passive0 = ramp_currents(fr, flay, res, n_fit)
        notes_app.append(f"passive_init = ramp: I_k(t0) = -(dPsi_k/dt)/R_k from a {n_fit}-point zero-passive march "
                         f"(sum I = {sum(passive0):.0f} A, max |I| = {max(abs(v) for v in passive0):.0f} A)")
    elif mode == "prescribed":
        passive0 = list(prescribed[0])

    # ---- 剖面：固定形状（缺省）或按 EFIT 参考迹的变化分段重定 ----
    seg_n = nt - 1 if a.profile == "fixed" else max(1, int(round(a.segment / max(times[1] - times[0], 1e-9))))
    bounds = list(range(0, nt - 1, seg_n)) + [nt - 1]
    ref = reference(case)["integrals"] if a.profile == "efit-trend" else None

    # ---- 竖直位置 ----
    at0 = channel_aturns(fchans, per_turn_at(case, 0)) + list(passive0)
    prof0, fit0 = case["profile"], None
    zc = None
    if a.zc_anchor not in ("none", "auto"):
        zc = float(a.zc_anchor)
    if a.profile == "efit-trend":
        #: t0 的目标就是输入 g-file 自己（同尺）；之后跟 magdata 的 EFIT 迹的**变化量**走
        z_guess = zc if zc is not None else free_zc(lib, fdev, case, at0, case["magdata"]["ip"][0], a)[0]
        prof0, fit0 = fit_profile(lib, fdev, case, at0, case["magdata"]["ip"][0], z_guess,
                                  (ref["betap"], ref["li1"]), (1.0, 0.0), a)
        log(f"run[{mode}]: t0 剖面 κ = {fit0['kappa']:.3f} γ = {fit0['gamma']:+.3f} → βp {fit0['betap']:.3f} li1 {fit0['li1']:.3f}")
    if a.zc_anchor == "auto":
        zc, how = free_zc(lib, fdev, case, at0, case["magdata"]["ip"][0], a, profile=prof0)
        log(f"run[{mode}]: t0 处线圈对不出力的电流中心 zc = {zc:+.5f} m（{'夹住' if how['bracketed'] else '未夹住'}）")

    # ---- 演化（分段：fixed 只有一段） ----
    log(f"run[{mode}]: code/evolve_free_boundary · {nt} 个时刻 {times[0]:.3f}–{times[-1]:.3f} s · "
        f"dt = {(times[1] - times[0]) * 1e3:.2f} ms · {len(bounds) - 1} 段")
    parts, profiles, fits = [], [], []
    carried = list(passive0)
    for si, (i0, i1) in enumerate(zip(bounds, bounds[1:])):
        if a.profile == "efit-trend":
            if si == 0:
                prof, fit = prof0, fit0
            else:
                k, f, k1 = where[i0]
                tgt = (ref["betap"] + trace_at(case, "betap", k, f, k1) - trace_at(case, "betap", 0),
                       ref["li1"] + trace_at(case, "li", k, f, k1) - trace_at(case, "li", 0))
                pres_now = list(prescribed[i0]) if prescribed is not None else carried
                at_k = channel_aturns(fchans, per_turn_at(case, k, f, k1)) + (pres_now if mode != "zero" else [0.0] * nfil)
                prof, fit = fit_profile(lib, fdev, case, at_k, ip_at(k, f, k1), zc, tgt,
                                        (fits[-1]["kappa"], fits[-1]["gamma"]), a)
            fits.append(fit)
        else:
            prof = case["profile"]
        seg_args = dict(passive0=carried if mode == "induced" else None,
                        prescribed=prescribed[i0:i1 + 1] if prescribed is not None else None)
        try:
            r = run_march(lib, case, dev, lay, times[i0:i1 + 1], where[i0:i1 + 1], a, mode, zc, profile=prof, **seg_args)
        except Refused as e:
            if si == 0 or a.profile == "fixed":
                raise
            #: 拟合出的形状在演化门里起步解不出（多见于很尖的 γ）：退回上一段的形状，记下来
            notes_app.append(f"segment {si + 1} (t = {times[i0]:.3f} s): the fitted profile was refused by the march "
                             f"({str(e)[-80:]}); the previous segment's profile is kept")
            log(f"run[{mode}]: 段 {si + 1} 拟合的剖面被门拒绝，沿用上一段的")
            prof = profiles[-1]
            if fits:
                fits[-1] = dict(fits[-1], fallback=True)
            try:
                r = run_march(lib, case, dev, lay, times[i0:i1 + 1], where[i0:i1 + 1], a, mode, zc, profile=prof,
                              **seg_args)
            except Refused as e2:
                #: 上一段的形状也走不下去：演化停在这一段的起点，已算的照常写出
                notes_app.append(f"march stopped at t = {times[i0]:.3f} s: {str(e2)[-120:]}")
                log(f"run[{mode}]: 上一段的剖面也走不下去——演化停在 t = {times[i0]:.3f} s，写出已算的部分")
                if fits:
                    fits.pop()
                break
        if a.profile != "fixed" and si > 0:
            #: 分段时的守门：一段里有既没收敛也没定住的步，或磁轴一步跳了 5 cm 以上（形状族走到电流几乎相消的地方时
            #: 平衡换了一个分支），这一段不要，演化停在它的起点
            gs = flat(r["fields"]["gs_state"])
            ar, az = flat(r["fields"]["axis_r"]), flat(r["fields"]["axis_z"])
            jump = max(math.hypot(ar[q + 1] - ar[q], az[q + 1] - az[q]) for q in range(len(ar) - 1))
            if min(gs) < 1.0 or jump > 0.05:            #: gs_state：2 收敛 · 1 定住（settled）· 0 都不是
                notes_app.append(f"march stopped at t = {times[i0]:.3f} s: segment {si + 1} left the branch "
                                 f"(min gs_state {min(gs):.0f}, axis jump {jump * 100:.1f} cm in one step)")
                log(f"run[{mode}]: 段 {si + 1} 离开了平衡分支（轴一步跳 {jump * 100:.1f} cm）——演化停在 t = {times[i0]:.3f} s")
                if fits:
                    fits.pop()
                break
        profiles.append(prof)
        parts.append(r)
        if mode == "induced":
            n = int(r["facts"]["n_channels"] + r["facts"]["n_passive"])
            cur = flat(r["fields"]["currents"])
            last = len(flat(r["fields"]["time"])) - 1
            carried = [cur[last * n + i] for i in lay["fil_index"]]
        if len(bounds) > 2:
            log(f"run[{mode}]: 段 {si + 1}/{len(bounds) - 1} t = {times[i0]:.3f}–{times[i1]:.3f} s"
                + (f" · κ {fits[-1]['kappa']:.3f} γ {fits[-1]['gamma']:+.3f} → βp {fits[-1]['betap']:.3f}/"
                   f"{fits[-1]['target'][0]:.3f} li1 {fits[-1]['li1']:.3f}/{fits[-1]['target'][1]:.3f}" if fits else ""))
    mm = merge_marches(parts)
    seg_t = [[times[i0], times[i1]] for i0, i1 in zip(bounds, bounds[1:])][:len(parts)]
    nt = len(mm["rows"]["ip"])                     #: 演化中途停下时只有前一部分
    times, where = times[:nt], where[:nt]
    log(f"run[{mode}]: 门共用了 {mm['seconds']:.1f} s · gs_unconverged "
        f"{sum(f.get('gs_unconverged', 0) for f in mm['facts']):.0f} · max circuit residual "
        f"{max(f.get('max_circuit_residual', 0) for f in mm['facts']):.1e}")
    n, plane = mm["n"], mm["plane"]
    gr, gz = mm["grid_r"], mm["grid_z"]
    nr, nz = len(gr), len(gz)
    psi_t, m, cur, pfl, row = mm["psi_t"], mm["m"], mm["currents"], mm["plasma_flux"], mm["rows"]
    sigma = math.copysign(1.0, (case["gfile"]["simag"] - case["gfile"]["sibry"]) / (row["psi_axis"][0] - row["psi_boundary"][0]))
    lim = [[x, y] for x, y in zip(case["gfile"]["rlim"], case["gfile"]["zlim"])]
    gdir = Path(a.gfile_dir) if a.gfile_dir else None
    if gdir:
        gdir.mkdir(parents=True, exist_ok=True)
    t_origin = case["time_origin_s"] or 0.0
    series = {k: [] for k in ("q0", "q95", "li1", "li3", "li3_summary", "betap", "w_mhd_J", "volume_m3", "kappa",
                              "delta_upper", "delta_lower", "r_geo_m", "a_minor_m", "ip_ampere_loop_A",
                              "pair_br_at_axis_T", "efit_li", "efit_betap", "passive_total_A")}
    boundaries, src = [], {k: [] for k in ("psi_total_Wb", "psi_external_Wb", "psi_plasma_Wb", "psi_gfile_Wb_per_rad",
                                           "current_A")}
    t_post = time.time()
    for k in range(nt):
        facts = {"psi_axis": row["psi_axis"][k], "psi_bnd": row["psi_boundary"][k], "ip": row["ip"][k],
                 "axis_r": row["axis_r"][k], "axis_z": row["axis_z"][k], "jc": row["jc"][k]}
        s = summarize(lib, dev, case, gr, gz, psi_t[k * plane:(k + 1) * plane], facts, a,
                      profile=profiles[mm["profile_index"][k]])
        it = s["integrals"]
        for key, v in (("q0", s["q0"]), ("q95", s["q95"]), ("li1", it["li1"]), ("li3", it["li3"]),
                       ("li3_summary", s["li3_summary"]), ("betap", it["betap"]), ("w_mhd_J", it["w_mhd_J"]),
                       ("volume_m3", it["volume_m3"]), ("kappa", s["shape"]["kappa"]),
                       ("delta_upper", s["shape"]["delta_upper"]), ("delta_lower", s["shape"]["delta_lower"]),
                       ("r_geo_m", s["shape"]["r0"]), ("a_minor_m", s["shape"]["a"]),
                       ("ip_ampere_loop_A", it["ip_ampere_A"]),
                       ("pair_br_at_axis_T", row["fb_amp"][k] * pair_br(gr, gz, facts["axis_r"], facts["axis_z"]))):
            series[key].append(v)
        kk, f, k1 = where[k]
        series["efit_li"].append(trace_at(case, "li", kk, f, k1))
        series["efit_betap"].append(trace_at(case, "betap", kk, f, k1))
        boundaries.append([[round(p[0], 5), round(p[1], 5)] for p in s["boundary"]])
        tot, ext, pla, cfil = [], [], [], []
        for i in lay["fil_index"]:
            lin = sum(m[i * n + j] * cur[k * n + j] for j in range(n))
            tot.append(lin + pfl[k * n + i])
            ext.append(lin - m[i * n + i] * cur[k * n + i] + pfl[k * n + i])
            pla.append(pfl[k * n + i])
            cfil.append(cur[k * n + i])
        src["psi_total_Wb"].append(tot)
        src["psi_external_Wb"].append(ext)
        src["psi_plasma_Wb"].append(pla)
        src["psi_gfile_Wb_per_rad"].append([sigma * v / TWO_PI for v in tot])
        src["current_A"].append(cfil)
        series["passive_total_A"].append(sum(cfil))
        if gdir and (k % a.gfile_every == 0 or k == nt - 1):
            write_gfile(gdir / f"g{case['shot']:06d}.{int(round((t_origin + times[k]) * 1000)):05d}_{k:04d}",
                        case, s, facts, gr, gz, sigma, t_origin + times[k], row["ip"][k], lim)
        if k % 100 == 0:
            log(f"run[{mode}]: 后处理 {k}/{nt}（{time.time() - t_post:.0f} s）")
    out = {
        "@type": "fylite:EastFreeBoundaryEvolution", "app": APP, "version": VERSION, "kernel": lib.linked_kernel(),
        "shot": case["shot"], "time_origin_s": t_origin, "passive": mode,
        "options": {"passive_init": a.passive_init if mode == "induced" else None, "passive_file": a.passive_file,
                    "zc_anchor": zc, "stride": a.stride, "substeps": a.substeps, "relax": a.relax,
                    "grid": [nr, nz], "ic_rz": a.ic_rz, "profile": a.profile,
                    "segment_s": a.segment if a.profile != "fixed" else None},
        "door": {"code": "code/evolve_free_boundary", "settings": mm["settings"], "seconds": mm["seconds"],
                 "facts": mm["facts"][0] if len(mm["facts"]) == 1 else mm["facts"], "notes": mm["notes"] + notes_app},
        "profile_fits": [{k: v for k, v in f.items()} for f in fits] if fits else None,
        "profile_segments": seg_t,
        "passive_init_A": passive0 if mode == "induced" else None,
        "sigma_gfile": sigma, "time": times, "time_abs": [t_origin + t for t in times],
        "ip_target_A": mm["ip_target"],
        "scalars": {**{k: row[k] for k in row}, **series},
        "boundary": boundaries,
        "channels": {"names": [c["name"] for c in channel_table(dev)[:lay["n_pfic"]]],
                     "aturns": [x[:lay["n_pfic"]] for x in mm["aturns"]]},
        "sources": {"r": case["filaments"]["r"], "z": case["filaments"]["z"], "resistance_ohm": res,
                    #: 丝串成的轮廓 [首, 尾, 是否闭合]（与 wall 输出同一条规则），结果页按轮廓分组画
                    "contours": [[sg[0], sg[-1], c] for sg, c in filament_contours(
                        case["filaments"]["r"], case["filaments"]["z"], case["assumptions"]["contour_gap_m"])], **src},
        "limiter": {"r": case["gfile"]["rlim"], "z": case["gfile"]["zlim"]},
        "geometry": geometry_block(dev0, case["shot"], "east", a.ic_rz, case),
        "grid": {"r": gr, "z": gz},
        "psi_last_Wb": psi_t[(nt - 1) * plane:],
    }
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    _write_json(a.output, out)
    log(f"run[{mode}]: → {a.output}（后处理 {time.time() - t_post:.0f} s）")


# =========================================================================== #
# wall：被动丝回路的 L/R 时间
# =========================================================================== #
def cmd_wall(a) -> None:
    case = json.loads(Path(a.case).read_text(encoding="utf-8"))
    lib = Lib(Path(a.lib))
    dev, _ = build_device(lib.device("east", case["shot"], "east"), case, "induced")
    fa, fi, _ = lib.door("code/wall", {"passive": "efb_vv", "nu": 8, "nv": 8, "responses": 0}, {"device": dev})
    r = flat(fi["r"])
    res = case["filaments"]["resistance"]
    _, info = filament_strips(case["filaments"]["r"], case["filaments"]["z"], res,
                              case["assumptions"]["rho_ohm_m"], case["assumptions"]["contour_gap_m"])
    tau = flat(fi["tau"])
    out = {"tau_s": tau[:10], "n_elements": fa.get("n_elements"),
           "resistance_max_rel_error": max(abs(x / y - 1.0) for x, y in zip(r, res)),
           "parallel_resistance_ohm": 1.0 / sum(1.0 / x for x in res),
           "thickness_m": [min(v["thickness_m"] for v in info), max(v["thickness_m"] for v in info)],
           "contours": [[s[0], s[-1], c] for s, c in filament_contours(case["filaments"]["r"], case["filaments"]["z"],
                                                                         case["assumptions"]["contour_gap_m"])]}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    _write_json(a.output, out, indent=1)
    log(f"wall: τ1..3 = {', '.join(f'{v * 1e3:.1f}' for v in tau[:3])} ms · 并联电阻 {out['parallel_resistance_ohm'] * 1e6:.1f} μΩ")


# =========================================================================== #
# compare：模式之间、与 EFIT 参考迹之间
# =========================================================================== #
def cmd_compare(a) -> None:
    runs = {}
    for p in a.runs:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        runs[Path(p).stem] = d
    out = {"@type": "fylite:EastFreeBoundaryComparison", "app": APP, "version": VERSION, "runs": {}, "pairs": {}}
    for name, d in runs.items():
        s = d["scalars"]
        ok = [k for k in range(len(d["time"])) if s["efit_li"][k] is not None]
        rel = lambda key, ref: [s[key][k] - s[ref][k] for k in ok if s[ref][k] is not None]   # noqa: E731
        dli, dbp = rel("li1", "efit_li"), rel("betap", "efit_betap")
        cur = d["sources"]["current_A"]
        out["runs"][name] = {
            "n": len(d["time"]), "t": [d["time"][0], d["time"][-1]],
            "axis_r": [min(s["axis_r"]), max(s["axis_r"])], "axis_z": [min(s["axis_z"]), max(s["axis_z"])],
            "li1": [s["li1"][0], s["li1"][-1]], "betap": [s["betap"][0], s["betap"][-1]],
            "q95": [s["q95"][0], s["q95"][-1]],
            "li1_minus_efit": {"rms": math.sqrt(mean([x * x for x in dli])) if dli else None,
                               "first": dli[0] if dli else None, "last": dli[-1] if dli else None},
            "betap_minus_efit": {"rms": math.sqrt(mean([x * x for x in dbp])) if dbp else None,
                                 "first": dbp[0] if dbp else None, "last": dbp[-1] if dbp else None},
            "fb_over_ip_max": max(abs(f / i) for f, i in zip(s["fb_amp"], s["ip"])),
            "pair_br_at_axis_mT_max": 1e3 * max(abs(v) for v in s["pair_br_at_axis_T"]),
            "passive_total_A": [min(s["passive_total_A"]), max(s["passive_total_A"])],
            "passive_max_abs_A": max(max(abs(v) for v in row) for row in cur),
            "gs_unconverged": sum(f.get("gs_unconverged", 0) for f in (d["door"]["facts"] if isinstance(d["door"]["facts"], list)
                                                                       else [d["door"]["facts"]])),
            "door_seconds": d["door"]["seconds"]}
    names = list(runs)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            dx, dy = runs[x], runs[y]
            n = min(len(dx["time"]), len(dy["time"]))
            if any(abs(dx["time"][k] - dy["time"][k]) > 1e-9 for k in range(n)):
                continue
            sx, sy = dx["scalars"], dy["scalars"]
            dax = [math.hypot(sx["axis_r"][k] - sy["axis_r"][k], sx["axis_z"][k] - sy["axis_z"][k]) for k in range(n)]
            dbd = [boundary_distance(dx["boundary"][k], dy["boundary"][k])["max_m"] for k in range(0, n, max(1, n // 40))]
            dpsi = [max(abs(u - v) for u, v in zip(dx["sources"]["psi_total_Wb"][k], dy["sources"]["psi_total_Wb"][k]))
                    for k in range(n)]
            out["pairs"][f"{x} vs {y}"] = {
                "axis_shift_max_m": max(dax), "axis_shift_last_m": dax[-1],
                "boundary_distance_max_m": max(dbd),
                "li1_diff_max": max(abs(sx["li1"][k] - sy["li1"][k]) for k in range(n)),
                "betap_diff_max": max(abs(sx["betap"][k] - sy["betap"][k]) for k in range(n)),
                "q95_diff_max": max(abs(sx["q95"][k] - sy["q95"][k]) for k in range(n)),
                "source_flux_diff_max_Wb": max(dpsi)}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    _write_json(a.output, out, indent=1)
    for k, v in out["pairs"].items():
        log(f"compare {k}: 轴移 max {v['axis_shift_max_m'] * 100:.2f} cm · 边界 max {v['boundary_distance_max_m'] * 100:.2f} cm · "
            f"Δli1 {v['li1_diff_max']:.3f} · Δβp {v['betap_diff_max']:.3f}")


# =========================================================================== #
# geometry：只写截面几何（旧的输出也能画出线圈与限制器，不必重跑）
# =========================================================================== #
def cmd_geometry(a) -> None:
    lib = Lib(Path(a.lib))
    case = json.loads(Path(a.case).read_text(encoding="utf-8")) if a.case else None
    shot = a.shot if a.shot is not None else (case or {}).get("shot")
    if shot is None:
        raise SystemExit("geometry 要 --shot（或 --case）")
    geo = geometry_block(lib.device("east", shot, a.chain), shot, a.chain, a.ic_rz, case, a.ic_figure_rz)
    out = {"@type": "fylite:EastFreeBoundaryGeometry", "app": APP, "version": VERSION, "kernel": lib.linked_kernel(),
           "shot": int(shot), "geometry": geo}
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    _write_json(a.output, out, indent=1)
    ic = "; ".join(f"{c['name']} ({c['r']}, {c['z']}) ← {c['position_from']}" for c in geo["ic_coils"])
    log(f"geometry: #{shot} · {len(geo['pf_coils'])} 个 PF 元素 · IC {ic} · 限制器 "
        f"{len(geo['limiter']['r']) if geo['limiter'] else 0} 点 → {a.output}")


# =========================================================================== #
# CLI
# =========================================================================== #
def _ic_rz(s):
    if not s:
        return None
    r, z = (float(x) for x in s.split(","))
    return [r, z]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="fb_evolution.py", description=__doc__.splitlines()[0])
    ap.add_argument("--lib", default=str(DEFAULT_LIB), help="libfylite.so（缺省：本文件旁边那一份）")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("prepare", help="数据目录 → 输入文档")
    p.add_argument("data_dir")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--gfile")
    p.add_argument("--afile")
    p.add_argument("--magdata", default="*_magdata.mat", help="文件名或通配（缺省 *_magdata.mat）")
    p.add_argument("--vv-position", default="vv_position.mat")
    p.add_argument("--vv-res", default="VVres.mat")
    p.add_argument("--rho", type=float, default=RHO_SS * 1e6,
                   help="由电阻反推丝截面时假定的电阻率 [μΩ·m]（只影响自感的截面项，电阻逐丝取 VVres）")
    p.add_argument("--contour-gap", type=float, default=CONTOUR_GAP, help="相邻丝间距大于它就断开轮廓 [m]")
    p.set_defaults(fn=cmd_prepare)

    def solver_opts(q):
        q.add_argument("--relax", type=float, default=SOLVE["relax"])
        q.add_argument("--tol", type=float, default=SOLVE["tol"])
        q.add_argument("--max-iter", type=int, default=SOLVE["max_iter"])
        q.add_argument("--grid", type=int, default=None, help="盒上的网格 N×N（缺省：装置的 65×65）")
        q.add_argument("--ic-rz", type=_ic_rz, default=None, help="IC 线圈中心 'R,Z'（上 +Z、下 −Z；缺省：装置事实）")

    p = sp.add_parser("initial", help="校验 1：t0 的初始平衡 vs 输入 g/a 文件")
    p.add_argument("case")
    p.add_argument("-o", "--output", required=True)
    solver_opts(p)
    p.set_defaults(fn=cmd_initial)

    p = sp.add_parser("run", help="自由边界演化")
    p.add_argument("case")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--passive", choices=("zero", "prescribed", "induced"), default="induced")
    p.add_argument("--passive-file", help="prescribed：被动丝电流的时间序列（JSON）")
    p.add_argument("--passive-init", choices=("zero", "ramp"), default="ramp",
                   help="induced：t0 的被动丝电流（缺省 ramp = 匀速变化下的稳态解）")
    p.add_argument("--ramp-window", type=float, default=0.02, help="ramp 起始电流取斜率的时间窗 [s]")
    p.add_argument("--zc-anchor", default="auto", help="auto（t0 处线圈对不出力的高度）| none | 一个数 [m]")
    p.add_argument("--t-start", type=float, default=0.0)
    p.add_argument("--t-end", type=float, default=1e9)
    p.add_argument("--stride", type=int, default=1, help="magdata 每隔几个点取一个")
    p.add_argument("--substeps", type=int, default=1, help="相邻两个取用点之间再细分几步（线性插值）")
    p.add_argument("--profile", choices=("fixed", "efit-trend"), default="fixed",
                   help="p′/FF′ 随时间：fixed = g-file 形状不变、按 I_p 标度（缺省）；efit-trend = 分段重定形状，"
                        "使同尺 β_p、l_i(1) 跟 magdata EFIT 迹相对 t0 的变化")
    p.add_argument("--segment", type=float, default=0.02, help="efit-trend 的分段长 [s]")
    p.add_argument("--gfile-dir", help="每步写一份 G-EQDSK 到这个目录")
    p.add_argument("--gfile-every", type=int, default=1)
    solver_opts(p)
    p.set_defaults(fn=cmd_run)

    p = sp.add_parser("wall", help="被动丝回路的 L/R 本征时间")
    p.add_argument("case")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(fn=cmd_wall)

    p = sp.add_parser("geometry", help="只写截面几何（PF / IC 线圈、限制器、丝的轮廓），取自装置事实")
    p.add_argument("--shot", type=int, default=None, help="炮号（缺省取 --case 的）")
    p.add_argument("--case", help="prepare 的 case.json：给了就连丝的轮廓一起写")
    p.add_argument("--chain", default="east", help="测量链（缺省 east）")
    p.add_argument("--ic-rz", type=_ic_rz, default=None, help="与 run 用的同一个 --ic-rz（缺省：装置事实）")
    p.add_argument("--ic-figure-rz", type=_ic_rz, default=None, help="数据附图上的 IC 位置 'R,Z'：只作记录，不用")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(fn=cmd_geometry)

    p = sp.add_parser("compare", help="几次 run 之间与 EFIT 参考迹的比较")
    p.add_argument("runs", nargs="+")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(fn=cmd_compare)

    a = ap.parse_args(argv)
    if a.cmd == "run" and a.passive == "prescribed" and not a.passive_file:
        ap.error("--passive prescribed 要 --passive-file")
    a.fn(a)


if __name__ == "__main__":
    main()
