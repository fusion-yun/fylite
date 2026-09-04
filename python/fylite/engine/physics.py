"""物理校验 —— 对一次产出，逐条量它是否满足**定律、定义与声明的期望**。

★★这一层回答的问题，与既有的两样都不同，混起来会让读者高估其中任何一样：

* :func:`fylite.engine.provenance.acceptance` 问的是「这个数**在数值上**可不可信」
  ——拟合残差、收敛旗标，逐能力一套阈值；
* 公开 V&V 登记册（``benchmark/registry.jsonld``、:mod:`.benchmark`）问的是
  「对着**外部答案**量到多少」——参考是另一个码或解析解，判据随参考走；
* **本模块**问的是「这份产出**自洽吗**」——温度是不是正的、ψ 端点对不对得上
  自己的全局量、二维平衡满不满足它自己声称在解的那道方程。参考不在外部，
  在物理定律与文档自己的定义里。

三者都需要，谁也替不了谁：一次跑得又快又收敛的解可以是负温度的；一条与另一个
码吻合到 1 % 的曲线可以违反 Grad–Shafranov（两处错互相抵消）。

一条检查由三样刻画，**这三样决定读者该怎么读它的结论**：

| ``kind`` | 参考是什么 | 不满足意味着 |
| :--- | :--- | :--- |
| ``law`` | 物理定律本身（正性、有限性、GS 方程） | 产出不是一个物理态——这是缺陷 |
| ``definition`` | 文档自己的定义（ψ 端点、V′>0、β_N 的式子） | 文档内部不自洽，或口径与本模块声明的不同 |
| ``expectation`` | **算例声明的**期望（上下界、准稳态） | 这一炮没落在声明的窗口里，不一定是缺陷 |

四态判决与 :mod:`fylite.engine.provenance` 同一套（``pass`` / ``conditional`` /
``fail`` / ``unevaluated``），且**读不到就是 ``unevaluated`` 并点名缺了哪一个量**
——绝不拿缺省值顶上（宁可拒绝，不给假数）。

★量一律经内核自己的槽表读（``fylite.fyo.get`` + ``_fyo_interface.TABLES``），
不在本文件里手写 fyo 路径：路径是内核声明的，抄一遍就是第二份会漂的契约。

★依赖只有 numpy（D-4′：本包不引 scipy / contourpy）。有限差分、多边形内外判定、
一维插值都是几行，写在这里比引一个依赖诚实。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

#: ★:mod:`fylite.fyo` pulls numpy, so it is read inside :meth:`_Reader.raw`
#: rather than at module scope — ``fylite.engine`` is stdlib-pure at import
#: time (gated by ``tests/test_engine_imports_only_stdlib.py``).

#: 四态，与 :mod:`fylite.engine.provenance` 同一套拼写（那边是 K-17 的正本；
#: 这里按名字引，不另起一套词）。
from .provenance import CONDITIONAL, FAIL, PASS, UNEVALUATED

__all__ = ["CHECKS", "Check", "Result", "evaluate", "summarize", "check_ids",
           "PASS", "CONDITIONAL", "FAIL", "UNEVALUATED"]

#: 真空磁导率与元电荷（CODATA 2018；内核用同样的定义域常数）。★写在这里是因为
#: 本模块要在**没有内核**的检出里也能跑（离线评一份已记录的产出）。
MU0 = 4.0e-7 * 3.141592653589793
E_CHARGE = 1.602176634e-19

#: 判决顺序，最坏者胜（与 provenance 的 `_ORDER` 同义）。
_ORDER = {FAIL: 3, CONDITIONAL: 2, PASS: 1, UNEVALUATED: 0}


# --------------------------------------------------------------------------- #
# 一条检查
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Check:
    """一条物理校验：读什么、算什么、按什么判。

    ``reads`` 是 ``(表, 槽)`` 对，**用来在跑之前就说清这条检查需要什么**——
    :func:`plan` 据此回答「这份产出能评哪几条、不能评哪几条、缺哪个量」。
    """

    id: str
    kind: str                      # law | definition | expectation
    title: str                     # 一句话：量的是什么
    formula: str                   # 判据的式子，照着能复算
    reads: tuple[tuple[str, str], ...]
    #: 相对判据的默认容差；``None`` = 由算例声明（``expectation`` 多是这种）
    tolerance: float | None
    #: 容差的来路，与公开登记册同一组词
    basis: str                     # machine_precision | measured_band | reference_stated
    #: 本条检查**假设了什么**——不满足假设时结论无效，逐条写出来
    assumes: tuple[str, ...] = ()
    fn: Callable[..., "Result | None"] | None = None


@dataclass
class Result:
    """一条检查量到的：数、判决、以及说清楚的一句话。"""

    check: str
    kind: str
    state: str
    #: 量到的偏差（相对判据下是相对值；计数判据下是个数）
    measured: float | None = None
    unit: str = "1"
    tolerance: float | None = None
    basis: str = ""
    detail: str = ""
    #: 读不到时缺的是哪个量——``unevaluated`` 必须点名
    missing: tuple[str, ...] = ()
    caveat: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = {"check": self.check, "kind": self.kind, "state": self.state,
             "measured": self.measured, "unit": self.unit,
             "tolerance": self.tolerance, "basis": self.basis,
             "detail": self.detail}
        if self.missing:
            d["missing"] = list(self.missing)
        if self.caveat:
            d["caveat"] = list(self.caveat)
        if self.extra:
            d["extra"] = self.extra
        return d


# --------------------------------------------------------------------------- #
# 读数：只经槽表
# --------------------------------------------------------------------------- #
#: 文档的 fyo 类型 → 本模块认的端口名。产出记录里一个端口一份文档
#: （``spo:PortBinding`` 的 ``bound_to``），端口名就是 IDS 名。
_BLOCK_DOC = {"EQUILIBRIUM": "equilibrium", "LADDER": "equilibrium",
              "CORE_PROFILES": "core_profiles", "CORE_SOURCES": "core_sources",
              "CORE_TRANSPORT": "core_transport", "SUMMARY": "summary",
              "MAGNETICS": "magnetics", "PF_ACTIVE": "pf_active", "TF": "tf",
              "DEVICE": "device"}


class Reader:
    """一次评测的读数面：``(表, 槽) → 数组``，缺席记账而不是抛。

    ★缺席**被记下来**（:attr:`missing`），因为「这条检查评不了」与「这条检查
    没通过」是两个事实，报告里必须分得开。
    """

    def __init__(self, datasets: Mapping[str, dict]):
        self.datasets = dict(datasets)
        self.missing: list[str] = []

    def doc(self, block: str) -> dict | None:
        return self.datasets.get(_BLOCK_DOC.get(block, block.lower()))

    def raw(self, block: str, slot: str):
        from .. import fyo as _fyo
        #: ★槽名不在表里 = 声明写错了（算例点了一个内核不产的量），与「文档里
        #: 没有这个量」是两个事实，都记为缺席但话不同——绝不让它抛穿一条检查
        table = _fyo.TABLES.get(block)
        if table is None or slot not in table["slots"]:
            self.missing.append(f"{block}/{slot} (not a declared slot)")
            return None
        d = self.doc(block)
        if d is None:
            self.missing.append(f"{_BLOCK_DOC.get(block, block.lower())} (document)")
            return None
        v = _fyo.get(d, block, slot, None)
        if v is None:
            self.missing.append(f"{block}/{slot}")
        return v

    def arr(self, block: str, slot: str):
        """一个槽读成 ``numpy`` 一维（或多维）数组；缺席给 ``None``。"""
        import numpy as np
        v = self.raw(block, slot)
        if v is None:
            return None
        a = np.asarray(v, dtype=float)
        return a if a.size else None

    def scalar(self, block: str, slot: str):
        import numpy as np
        v = self.raw(block, slot)
        if v is None:
            return None
        a = np.asarray(v, dtype=float).ravel()
        return float(a[0]) if a.size else None


def _rel(a, b) -> float:
    """相对差 |a−b| / max(|a|,|b|,tiny) —— 两边都可能是零时不放大。"""
    import numpy as np
    a, b = np.asarray(a, float), np.asarray(b, float)
    scale = np.maximum(np.maximum(np.abs(a), np.abs(b)), 1e-300)
    return float(np.max(np.abs(a - b) / scale))


def _verdict(measured: float | None, tol: float | None, *, warn: float = 3.0) -> str:
    """量到的对着容差判：``≤tol`` 过，``≤warn·tol`` 有条件，其余不过。"""
    import numpy as np
    if measured is None or not np.isfinite(measured):
        return UNEVALUATED
    if tol is None:
        return UNEVALUATED
    if measured <= tol:
        return PASS
    if measured <= warn * tol:
        return CONDITIONAL
    return FAIL


def _finite_mask(a):
    import numpy as np
    return np.isfinite(np.asarray(a, float))


# --------------------------------------------------------------------------- #
# 定律：产出得是一个物理态
# --------------------------------------------------------------------------- #
def _c_finite(r: Reader, opt: dict) -> Result:
    """每一个产出的数组都得是有限的。NaN 不是一个状态。"""
    import numpy as np
    bad: list[str] = []
    total = 0

    def walk(node, path):
        nonlocal total
        if isinstance(node, dict):
            for k, v in node.items():
                if k.startswith("@") or k in ("comment", "caveat"):
                    continue
                walk(v, f"{path}/{k}")
        elif isinstance(node, list):
            if node and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in node):
                a = np.asarray(node, float)
                total += a.size
                n = int((~np.isfinite(a)).sum())
                if n:
                    bad.append(f"{path} ({n}/{a.size})")
            else:
                for i, v in enumerate(node):
                    walk(v, f"{path}/{i}")
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            total += 1
            if not np.isfinite(float(node)):
                bad.append(path)

    for port, doc in r.datasets.items():
        walk(doc, port)
    if not total:
        return Result("finite", "law", UNEVALUATED, missing=("no numeric leaf in any dataset",),
                      detail="产出里没有数值叶子")
    n_bad = len(bad)
    return Result("finite", "law", PASS if n_bad == 0 else FAIL, measured=float(n_bad),
                  unit="count", tolerance=0.0, basis="machine_precision",
                  detail=(f"{total} 个数值全部有限" if not n_bad else
                          f"{n_bad} 处非有限：" + "；".join(bad[:5])))


def _positive(r: Reader, opt: dict, cid: str, pairs: Sequence[tuple[str, str]], what: str) -> Result:
    import numpy as np
    worst = None
    where = ""
    seen = []
    for block, slot in pairs:
        a = r.arr(block, slot)
        if a is None:
            continue
        a = a[np.isfinite(a)]
        if not a.size:
            continue
        seen.append(f"{block}/{slot}")
        m = float(a.min())
        if worst is None or m < worst:
            worst, where = m, f"{block}/{slot}"
    if worst is None:
        return Result(cid, "law", UNEVALUATED, missing=tuple(f"{b}/{s}" for b, s in pairs),
                      detail=f"产出里没有{what}")
    return Result(cid, "law", PASS if worst > 0 else FAIL, measured=worst, unit="(as stored)",
                  tolerance=0.0, basis="machine_precision",
                  detail=f"最小值 {worst:.6g}（{where}）；读了 {', '.join(seen)}")


def _c_positive_temperature(r: Reader, opt: dict) -> Result:
    """绝对温度为正 —— 一条定律，不是一个偏好。"""
    return _positive(r, opt, "positive-temperature",
                     [("CORE_PROFILES", "te"), ("CORE_PROFILES", "ti"),
                      ("SUMMARY", "te_axis"), ("SUMMARY", "ti_axis")], "温度")


def _c_positive_density(r: Reader, opt: dict) -> Result:
    """粒子数密度为正。"""
    return _positive(r, opt, "positive-density",
                     [("CORE_PROFILES", "ne"), ("CORE_PROFILES", "ni"),
                      ("SUMMARY", "ne_axis")], "密度")


def _c_grad_shafranov(r: Reader, opt: dict) -> Result:
    """二维平衡满足 Grad–Shafranov：``Δ*ψ = −μ₀R²p′(ψ) − f f′(ψ)``。

    ★这是平衡产出唯一一条**定律级**检查：它量的不是「与谁吻合」，而是这份 ψ
    是不是它自己那对源函数（``dpressure_dpsi`` / ``f_df_dpsi``）的解。差分算子
    ``Δ* = ∂_RR − (1/R)∂_R + ∂_ZZ`` 用二阶中心差分，只在**边界内**且离网格边
    一格以上的点上取（边界外 ψ 不由这对源函数决定）。

    ★★符号约定：本仓的 ψ 是**每弧度**的（`fyo.equilibrium` 的 `convention`）。
    两种符号都算一遍，取残差小的那一支并**写明是哪一支**——一份用另一套 COCOS
    写出来的文档，得到的是一条注记，而不是一个假的「不满足定律」。
    """
    import numpy as np
    psi2d = r.arr("EQUILIBRIUM", "psi_2d")
    gr = r.arr("EQUILIBRIUM", "grid_r")
    gz = r.arr("EQUILIBRIUM", "grid_z")
    psi1d = r.arr("EQUILIBRIUM", "psi_1d")
    pprime = r.arr("EQUILIBRIUM", "dpressure_dpsi")
    ffprime = r.arr("EQUILIBRIUM", "f_df_dpsi")
    if any(x is None for x in (psi2d, gr, gz, psi1d, pprime, ffprime)):
        return Result("grad-shafranov", "law", UNEVALUATED, missing=tuple(r.missing[-4:]),
                      detail="缺二维 ψ 或它的源函数（p′ / ff′），这条评不了")
    if psi2d.ndim != 2 or psi2d.shape != (gr.size, gz.size):
        return Result("grad-shafranov", "law", UNEVALUATED,
                      missing=("psi_2d shape",),
                      detail=f"ψ 的形状 {psi2d.shape} 与网格 ({gr.size}, {gz.size}) 对不上")
    if gr.size < 5 or gz.size < 5:
        return Result("grad-shafranov", "law", UNEVALUATED, missing=("grid too small",),
                      detail="网格小于 5×5，二阶差分没有内点")

    dR = float(gr[1] - gr[0])
    dZ = float(gz[1] - gz[0])
    R = gr[1:-1][:, None]
    #: Δ*ψ = ψ_RR − ψ_R/R + ψ_ZZ，二阶中心差分
    psi_RR = (psi2d[2:, 1:-1] - 2 * psi2d[1:-1, 1:-1] + psi2d[:-2, 1:-1]) / dR ** 2
    psi_R = (psi2d[2:, 1:-1] - psi2d[:-2, 1:-1]) / (2 * dR)
    psi_ZZ = (psi2d[1:-1, 2:] - 2 * psi2d[1:-1, 1:-1] + psi2d[1:-1, :-2]) / dZ ** 2
    delta_star = psi_RR - psi_R / R + psi_ZZ

    #: 源项在 ψ(R, Z) 处取值——一维源函数按 ψ 插值（ψ 网格可能递减）
    inner = psi2d[1:-1, 1:-1]
    order = np.argsort(psi1d)
    xp = psi1d[order]
    pp = np.interp(inner, xp, pprime[order])
    ffp = np.interp(inner, xp, ffprime[order])
    rhs = -MU0 * (R ** 2) * pp - ffp

    #: 只在边界内取点；没有边界就取 ψ 在 [ψ_axis, ψ_bnd] 之间的点
    mask = np.ones_like(inner, dtype=bool)
    br = r.arr("EQUILIBRIUM", "boundary_r")
    bz = r.arr("EQUILIBRIUM", "boundary_z")
    how = "边界外形内"
    if br is not None and bz is not None and br.size >= 3:
        RR, ZZ = np.meshgrid(gr[1:-1], gz[1:-1], indexing="ij")
        mask = _inside(RR, ZZ, br, bz)
    else:
        lo, hi = float(min(psi1d[0], psi1d[-1])), float(max(psi1d[0], psi1d[-1]))
        mask = (inner >= lo) & (inner <= hi)
        how = "ψ ∈ [ψ_axis, ψ_bnd]"
    mask &= np.isfinite(delta_star) & np.isfinite(rhs)
    n = int(mask.sum())
    if n < 16:
        return Result("grad-shafranov", "law", UNEVALUATED, missing=("interior points",),
                      detail=f"{how}内只有 {n} 个内点，不足以量残差")

    scale = float(np.sqrt(np.mean(np.maximum(delta_star[mask] ** 2, rhs[mask] ** 2))))
    scale = max(scale, 1e-300)
    res_plus = float(np.sqrt(np.mean((delta_star[mask] - rhs[mask]) ** 2))) / scale
    res_minus = float(np.sqrt(np.mean((delta_star[mask] + rhs[mask]) ** 2))) / scale
    flipped = res_minus < res_plus
    measured = min(res_plus, res_minus)
    tol = float(opt.get("tolerance", 0.02))
    caveat = ()
    if flipped:
        caveat = ("残差在 `Δ*ψ = +μ₀R²p′ + ff′` 一支上更小：这份文档的 ψ 或源函数"
                  "符号与本仓约定（每弧度、`Δ*ψ = −μ₀R²p′ − ff′`）相反，先核对 COCOS",)
    return Result("grad-shafranov", "law", _verdict(measured, tol), measured=measured,
                  tolerance=tol, basis="measured_band",
                  detail=(f"{n} 个内点（{how}）上 ‖Δ*ψ − RHS‖/‖·‖ = {measured:.3e}"
                          f"（另一符号支 {max(res_plus, res_minus):.3e}）"),
                  caveat=caveat, extra={"points": n, "dR": dR, "dZ": dZ})


def _outside_by(R, Z, br, bz):
    """每个点越出多边形多远（在内为 0）—— 点到边的最短距离，numpy 向量化。

    ★用距离而不是纯内外判定：正落在边上的点，射线穿越法给的答案是随机的，而
    「正落在限制器上」在物理上是**贴着**，不是越界。
    """
    import numpy as np
    R = np.asarray(R, float)
    Z = np.asarray(Z, float)
    br = np.asarray(br, float)
    bz = np.asarray(bz, float)
    if br[0] != br[-1] or bz[0] != bz[-1]:
        br, bz = np.append(br, br[0]), np.append(bz, bz[0])
    p1r, p1z = br[:-1], bz[:-1]
    p2r, p2z = br[1:], bz[1:]
    dr, dz = p2r - p1r, p2z - p1z
    L2 = np.maximum(dr ** 2 + dz ** 2, 1e-300)
    t = ((R[..., None] - p1r) * dr + (Z[..., None] - p1z) * dz) / L2
    t = np.clip(t, 0.0, 1.0)
    d = np.hypot(R[..., None] - (p1r + t * dr), Z[..., None] - (p1z + t * dz))
    dist = d.min(axis=-1)
    return np.where(_inside(R, Z, br, bz), 0.0, dist)


def _inside(R, Z, br, bz):
    """点在闭多边形内 —— 射线穿越法，numpy 向量化（scipy 不进本包）。"""
    import numpy as np
    br = np.asarray(br, float)
    bz = np.asarray(bz, float)
    if br[0] != br[-1] or bz[0] != bz[-1]:
        br = np.append(br, br[0])
        bz = np.append(bz, bz[0])
    inside = np.zeros(R.shape, dtype=bool)
    for i in range(br.size - 1):
        r1, z1, r2, z2 = br[i], bz[i], br[i + 1], bz[i + 1]
        if z1 == z2:
            continue
        crosses = (z1 > Z) != (z2 > Z)
        with np.errstate(divide="ignore", invalid="ignore"):
            r_at = r1 + (Z - z1) * (r2 - r1) / (z2 - z1)
        inside ^= crosses & (R < r_at)
    return inside


# --------------------------------------------------------------------------- #
# 定义：文档跟自己对得上
# --------------------------------------------------------------------------- #
def _c_grid_monotone(r: Reader, opt: dict) -> Result:
    """网格与时间轴单调递增，归一化网格落在 [0, 1]。"""
    import numpy as np
    checked, bad = [], []
    for block, slot, lo, hi in (("CORE_PROFILES", "rho_norm", 0.0, 1.0),
                                ("CORE_PROFILES", "psin", 0.0, 1.0),
                                ("LADDER", "psin", 0.0, 1.0),
                                ("CORE_PROFILES", "time", None, None),
                                ("SUMMARY", "time", None, None),
                                ("EQUILIBRIUM", "time", None, None)):
        a = r.arr(block, slot)
        if a is None or a.size < 2:
            continue
        checked.append(f"{block}/{slot}")
        d = np.diff(a)
        if not np.all(d > 0):
            bad.append(f"{block}/{slot} 有 {int((d <= 0).sum())} 处不递增")
        if lo is not None and (a.min() < lo - 1e-9 or a.max() > hi + 1e-9):
            bad.append(f"{block}/{slot} 越出 [{lo}, {hi}]（{a.min():.4g}…{a.max():.4g}）")
    if not checked:
        return Result("grid-monotone", "definition", UNEVALUATED,
                      missing=("no grid or time axis",), detail="产出里没有网格或时间轴")
    return Result("grid-monotone", "definition", PASS if not bad else FAIL,
                  measured=float(len(bad)), unit="count", tolerance=0.0,
                  basis="machine_precision",
                  detail=("；".join(bad) if bad else f"{len(checked)} 条轴单调：{', '.join(checked)}"))


def _c_psi_endpoints(r: Reader, opt: dict) -> Result:
    """一维 ψ 的两端就是全局量里的 ψ_axis 与 ψ_boundary —— 定义，不是巧合。"""
    psi1d = r.arr("EQUILIBRIUM", "psi_1d")
    pa = r.scalar("EQUILIBRIUM", "psi_axis")
    pb = r.scalar("EQUILIBRIUM", "psi_boundary")
    if psi1d is None or pa is None or pb is None or psi1d.size < 2:
        return Result("psi-endpoints", "definition", UNEVALUATED,
                      missing=("EQUILIBRIUM/psi_1d", "EQUILIBRIUM/psi_axis",
                               "EQUILIBRIUM/psi_boundary"),
                      detail="缺一维 ψ 或它的两个全局端点")
    span = max(abs(pb - pa), 1e-300)
    d0 = abs(float(psi1d[0]) - pa) / span
    d1 = abs(float(psi1d[-1]) - pb) / span
    measured = max(d0, d1)
    tol = float(opt.get("tolerance", 1e-6))
    return Result("psi-endpoints", "definition", _verdict(measured, tol), measured=measured,
                  tolerance=tol, basis="machine_precision",
                  detail=f"两端相对 ψ 跨度差 {d0:.3e} / {d1:.3e}")


def _c_volume_monotone(r: Reader, opt: dict) -> Result:
    """封闭磁面的体积随 ρ 单调增，且 ``V′ = dV/dρ > 0`` —— 几何定义。"""
    import numpy as np
    v = r.arr("LADDER", "volume")
    vp = r.arr("LADDER", "vprime")
    if v is None and vp is None:
        return Result("volume-monotone", "definition", UNEVALUATED,
                      missing=("LADDER/volume", "LADDER/vprime"), detail="梯子上没有体积")
    bad = []
    if v is not None and v.size > 1:
        d = np.diff(v)
        if not np.all(d >= 0):
            bad.append(f"volume 有 {int((d < 0).sum())} 处下降")
        if float(v.min()) < 0:
            bad.append(f"volume 有负值（{v.min():.4g}）")
    if vp is not None and vp.size:
        #: 轴上 V′ = 0 是解析的，所以只看内部点
        inner = vp[1:]
        if inner.size and float(inner.min()) <= 0:
            bad.append(f"V′ 在轴外有非正值（{float(inner.min()):.4g}）")
    return Result("volume-monotone", "definition", PASS if not bad else FAIL,
                  measured=float(len(bad)), unit="count", tolerance=0.0,
                  basis="machine_precision",
                  detail="；".join(bad) if bad else "体积单调、V′ 在轴外为正")


def _c_boundary_closed(r: Reader, opt: dict) -> Result:
    """最外闭合磁面是**闭合**的，且落在限制器内 —— 几何定义。

    ★★闭合按**采样步长**量，不按小半径：一条等值线是按点采出来的，首末两点差得
    比一个采样步还小就已经是闭合的（g-file 的 `rbbbs` 重不重复首点是写文件那边的
    习惯，不是物理）。按小半径量会把「采样密度」误判成「开口」——本仓的合成件
    正好踩在这上面（首末差 1.5 cm，而步长 1.7 cm）。

    ★★限制器内外用**距离**判，不用纯粹的内外判定：合成件的限制器是边界包围盒
    的外接矩形，于是有一半的边界极值点**正落在边上**，射线穿越法对这种点是随机的。
    「越界」因此定义为「越出限制器多于 tol × 小半径」。
    """
    import numpy as np
    br = r.arr("EQUILIBRIUM", "boundary_r")
    bz = r.arr("EQUILIBRIUM", "boundary_z")
    if br is None or bz is None or br.size < 3:
        return Result("boundary-closed", "definition", UNEVALUATED,
                      missing=("EQUILIBRIUM/boundary_r", "EQUILIBRIUM/boundary_z"),
                      detail="产出里没有边界外形")
    a = 0.5 * (float(br.max()) - float(br.min()))
    gap_m = float(np.hypot(br[0] - br[-1], bz[0] - bz[-1]))
    step = float(np.median(np.hypot(np.diff(br), np.diff(bz)))) if br.size > 2 else gap_m
    measured = gap_m / max(step, 1e-300)
    tol = float(opt.get("tolerance", 1.5))
    notes = [f"首末点间距 {gap_m:.4g} m = {measured:.3g} 个采样步"
             f"（步长中位数 {step:.4g} m，小半径 {a:.4g} m）"]
    state = _verdict(measured, tol)
    lr = r.arr("EQUILIBRIUM", "limiter_r")
    lz = r.arr("EQUILIBRIUM", "limiter_z")
    if lr is not None and lz is not None and lr.size >= 3:
        out_by = _outside_by(br, bz, lr, lz)
        slack = float(opt.get("limiter_tolerance", 0.02)) * max(a, 1e-300)
        n_out = int((out_by > slack).sum())
        notes.append(f"越出限制器多于 {slack:.4g} m 的边界点 {n_out}/{br.size}"
                     f"（最深 {float(out_by.max()):.4g} m）")
        if n_out:
            state = FAIL
    else:
        notes.append("没有限制器外形，只量了闭合性")
    return Result("boundary-closed", "definition", state, measured=measured, unit="sampling steps",
                  tolerance=tol, basis="measured_band", detail="；".join(notes),
                  extra={"gap_m": gap_m, "step_m": step, "minor_radius_m": a})


def _c_pressure_consistency(r: Reader, opt: dict) -> Result:
    """平衡的压强对得上剖面的 ``p = e(n_e T_e + n_i T_i)``。

    ★假设写在 ``assumes`` 里，且**结论只在假设成立时有意义**：热压强、单一等效
    离子、无快离子压强。平衡里带快粒子压强的算例，这条会给出一个正的偏差——
    那是口径差别，不是缺陷，所以判据取 ``measured_band``。
    """
    import numpy as np
    p_eq = r.arr("EQUILIBRIUM", "pressure")
    x_eq = r.arr("LADDER", "psin")
    ne = r.arr("CORE_PROFILES", "ne")
    te = r.arr("CORE_PROFILES", "te")
    ti = r.arr("CORE_PROFILES", "ti")
    ni = r.arr("CORE_PROFILES", "ni")
    x_cp = r.arr("CORE_PROFILES", "psin")
    if p_eq is None or ne is None or te is None:
        return Result("pressure-consistency", "definition", UNEVALUATED,
                      missing=("EQUILIBRIUM/pressure", "CORE_PROFILES/ne", "CORE_PROFILES/te"),
                      detail="缺平衡压强或电子剖面")
    caveat = []
    if ni is None:
        ni = ne
        caveat.append("没有 `ion_density`，按准中性取 n_i = n_e")
    if ti is None:
        ti = te
        caveat.append("没有 `t_i_average`，按 T_i = T_e")
    p_kin = E_CHARGE * (ne * te + ni * ti)
    if x_eq is not None and x_cp is not None and x_eq.size == p_eq.size and x_cp.size == p_kin.size:
        order = np.argsort(x_cp)
        p_kin = np.interp(x_eq, x_cp[order], p_kin[order])
    elif p_kin.size != p_eq.size:
        return Result("pressure-consistency", "definition", UNEVALUATED,
                      missing=("LADDER/psin", "CORE_PROFILES/psin"),
                      detail=f"两侧网格长度不同（{p_eq.size} vs {p_kin.size}）且没有共同横坐标")
    scale = max(float(np.max(np.abs(p_eq))), float(np.max(np.abs(p_kin))), 1e-300)
    measured = float(np.max(np.abs(p_eq - p_kin))) / scale
    tol = float(opt.get("tolerance", 0.05))
    return Result("pressure-consistency", "definition", _verdict(measured, tol),
                  measured=measured, tolerance=tol, basis="measured_band",
                  detail=f"最大相对差 {measured:.3e}（对 max|p| = {scale:.4g} Pa 归一）",
                  caveat=tuple(caveat))


def _c_energy_balance(r: Reader, opt: dict) -> Result:
    """``W_th/τ_E + dW_th/dt = P_heat`` —— τ_E 的定义式，逐时刻量残差。

    ★口径**可由算例声明**（``p_heat_terms``）：缺省取 ``p_ohm + p_aux + p_alpha
    − p_rad``。取哪几项是一个约定；本模块把约定写进结论里，而不是假装没有约定。
    """
    import numpy as np
    w = r.arr("SUMMARY", "w_th")
    tau = r.arr("SUMMARY", "tau_e")
    if w is None or tau is None:
        return Result("energy-balance", "definition", UNEVALUATED,
                      missing=("SUMMARY/w_th", "SUMMARY/tau_e"), detail="缺热能或能量约束时间")
    terms = opt.get("p_heat_terms") or ["p_ohm", "p_aux", "p_alpha", "-p_rad"]
    p = np.zeros_like(w)
    used, absent = [], []
    for t in terms:
        sign, name = (-1.0, t[1:]) if t.startswith("-") else (1.0, t)
        a = r.arr("SUMMARY", name)
        if a is None or a.shape != w.shape:
            absent.append(name)
            continue
        p = p + sign * a
        used.append(t)
    if not used:
        return Result("energy-balance", "definition", UNEVALUATED,
                      missing=tuple(f"SUMMARY/{a}" for a in absent),
                      detail="一项加热功率都读不到")
    dw = r.arr("SUMMARY", "dw_dt")
    if dw is None or dw.shape != w.shape:
        dw = np.zeros_like(w)
        note = "没有 dW/dt，按准稳态取 0"
    else:
        note = "含 dW/dt"
    ok = np.isfinite(w) & np.isfinite(tau) & np.isfinite(p) & (tau > 0) & (np.abs(p) > 0)
    if not ok.any():
        return Result("energy-balance", "definition", UNEVALUATED,
                      missing=("SUMMARY/tau_e > 0",),
                      detail="没有 τ_E > 0 且 P_heat ≠ 0 的时刻")
    resid = np.abs(w[ok] / tau[ok] + dw[ok] - p[ok]) / np.abs(p[ok])
    measured = float(np.median(resid))
    tol = float(opt.get("tolerance", 0.05))
    caveat = (f"口径：P_heat = {' '.join(used)}；{note}",)
    if absent:
        caveat = caveat + (f"未计入（读不到）：{', '.join(absent)}",)
    return Result("energy-balance", "definition", _verdict(measured, tol), measured=measured,
                  tolerance=tol, basis="measured_band",
                  detail=f"{int(ok.sum())} 个时刻的相对残差中位数 {measured:.3e}，最大 {float(resid.max()):.3e}",
                  caveat=caveat)


def _minor_radius(r: Reader):
    """小半径：优先取边界外形的 (R_max − R_min)/2，其次算例声明的 ``a_m``。"""
    br = r.arr("EQUILIBRIUM", "boundary_r")
    if br is not None and br.size >= 3:
        return 0.5 * (float(br.max()) - float(br.min())), "边界外形"
    return None, ""


def _volume_average(r: Reader, y):
    """按 ``dV`` 的体积平均；没有体积梯子时给 ``None``（不拿算术平均冒充）。"""
    import numpy as np
    v = r.arr("LADDER", "volume")
    if v is None or y is None or v.size != np.asarray(y).size or v.size < 2:
        return None
    y = np.asarray(y, float)
    return float(np.trapezoid(y, v) / (v[-1] - v[0])) if hasattr(np, "trapezoid") \
        else float(np.trapz(y, v) / (v[-1] - v[0]))


def _c_greenwald(r: Reader, opt: dict) -> Result:
    """记下的 Greenwald 分数对得上它的定义 ``n̄_e / n_G``，``n_G = I_p[MA]/(πa²)``。"""
    import numpy as np
    rec = r.arr("SUMMARY", "greenwald")
    ip = r.arr("SUMMARY", "ip")
    ne = r.arr("CORE_PROFILES", "ne")
    if rec is None or ip is None or ne is None:
        return Result("greenwald-definition", "definition", UNEVALUATED,
                      missing=("SUMMARY/greenwald", "SUMMARY/ip", "CORE_PROFILES/ne"),
                      detail="缺记下的 Greenwald 分数、I_p 或密度剖面")
    a, how = _minor_radius(r)
    if a is None or a <= 0:
        return Result("greenwald-definition", "definition", UNEVALUATED,
                      missing=("EQUILIBRIUM/boundary_r",),
                      detail="没有边界外形，取不到小半径")
    n_bar = _volume_average(r, ne)
    caveat = []
    if n_bar is None:
        n_bar = float(np.mean(ne))
        caveat.append("没有体积梯子，n̄_e 取剖面的算术平均——与线平均口径可能差几个百分点")
    else:
        caveat.append("n̄_e 取体积平均（记录若用线平均，会有几个百分点的口径差）")
    ip_ma = float(np.abs(ip).max()) / 1e6
    n_g = ip_ma / (np.pi * a ** 2) * 1e20
    expect = n_bar / n_g if n_g > 0 else None
    got = float(np.abs(rec).max())
    if expect is None:
        return Result("greenwald-definition", "definition", UNEVALUATED,
                      missing=("SUMMARY/ip > 0",), detail="I_p 为零，n_G 无定义")
    measured = _rel(got, expect)
    tol = float(opt.get("tolerance", 0.15))
    return Result("greenwald-definition", "definition", _verdict(measured, tol),
                  measured=measured, tolerance=tol, basis="measured_band",
                  detail=(f"记下 {got:.4g}，按定义 {expect:.4g}"
                          f"（a = {a:.4g} m（{how}），I_p = {ip_ma:.4g} MA，"
                          f"n_G = {n_g:.4g} m^-3），相对差 {measured:.3e}"),
                  caveat=tuple(caveat))


def _c_beta_normalized(r: Reader, opt: dict) -> Result:
    """记下的 β_N 对得上 ``β_N = β_t[%]·a·B₀/I_p[MA]``，``β_t = 2μ₀⟨p⟩/B₀²``。"""
    import numpy as np
    rec = r.arr("SUMMARY", "beta_n")
    ip = r.arr("SUMMARY", "ip")
    b0 = r.scalar("EQUILIBRIUM", "b0")
    p_eq = r.arr("EQUILIBRIUM", "pressure")
    if rec is None or ip is None or b0 is None or p_eq is None:
        return Result("beta-normalized-definition", "definition", UNEVALUATED,
                      missing=("SUMMARY/beta_n", "SUMMARY/ip", "EQUILIBRIUM/b0",
                               "EQUILIBRIUM/pressure"),
                      detail="缺 β_N、I_p、B₀ 或压强剖面")
    a, how = _minor_radius(r)
    p_avg = _volume_average(r, p_eq)
    if a is None or p_avg is None:
        return Result("beta-normalized-definition", "definition", UNEVALUATED,
                      missing=("EQUILIBRIUM/boundary_r", "LADDER/volume"),
                      detail="没有小半径或体积梯子，⟨p⟩ 与 a 取不到")
    ip_ma = float(np.abs(ip).max()) / 1e6
    beta_t = 2 * MU0 * p_avg / (b0 ** 2)
    expect = beta_t * 100.0 * a * abs(b0) / ip_ma if ip_ma > 0 else None
    if expect is None:
        return Result("beta-normalized-definition", "definition", UNEVALUATED,
                      missing=("SUMMARY/ip > 0",), detail="I_p 为零，β_N 无定义")
    got = float(np.abs(rec).max())
    measured = _rel(got, expect)
    tol = float(opt.get("tolerance", 0.15))
    return Result("beta-normalized-definition", "definition", _verdict(measured, tol),
                  measured=measured, tolerance=tol, basis="measured_band",
                  detail=(f"记下 {got:.4g}，按定义 {expect:.4g}"
                          f"（⟨p⟩ = {p_avg:.4g} Pa 体积平均，a = {a:.4g} m（{how}），"
                          f"B₀ = {b0:.4g} T，I_p = {ip_ma:.4g} MA），相对差 {measured:.3e}"),
                  caveat=("⟨p⟩ 取平衡压强的体积平均（热压强口径）；记录若用热能推出的 β，"
                          "含快离子时会有口径差",))


# --------------------------------------------------------------------------- #
# 期望：算例自己声明的窗口
# --------------------------------------------------------------------------- #
def _c_q_order(r: Reader, opt: dict) -> Result:
    """``|q95| > |q_axis|`` —— 单调 q 的常规位形该有的次序。

    ★这是**期望**不是定律：反剪切位形正当地违反它。算例不声明就不判。
    """
    import numpy as np
    q0 = r.arr("SUMMARY", "q_axis")
    q95 = r.arr("SUMMARY", "q95")
    if q0 is None or q95 is None:
        qp = r.arr("CORE_PROFILES", "q")
        if qp is None or qp.size < 2:
            return Result("q-order", "expectation", UNEVALUATED,
                          missing=("SUMMARY/q_axis", "SUMMARY/q95", "CORE_PROFILES/q"),
                          detail="没有 q")
        q0, q95 = qp[:1], qp[-1:]
    n = min(q0.size, q95.size)
    bad = int(np.sum(np.abs(q95[:n]) <= np.abs(q0[:n])))
    return Result("q-order", "expectation", PASS if bad == 0 else CONDITIONAL,
                  measured=float(bad), unit="count", tolerance=0.0, basis="reference_stated",
                  detail=(f"{n} 个时刻里 {bad} 个 |q95| ≤ |q_axis|"
                          + ("" if bad == 0 else "——反剪切位形会正当地这样，请对着算例判读")))


def _c_steady_state(r: Reader, opt: dict) -> Result:
    """准稳态：内核记的 ``steady_change`` 在算例声明的窗口内。"""
    import numpy as np
    sc = r.arr("SUMMARY", "steady_change")
    if sc is None:
        return Result("steady-state", "expectation", UNEVALUATED,
                      missing=("SUMMARY/steady_change",), detail="记录里没有 steady_change")
    tol = opt.get("tolerance")
    measured = float(np.abs(sc[np.isfinite(sc)]).max()) if np.isfinite(sc).any() else None
    if tol is None:
        return Result("steady-state", "expectation", UNEVALUATED, measured=measured,
                      basis="reference_stated",
                      detail=f"量到 {measured:.3e}，但算例没有声明窗口（`tolerance`），不判"
                             if measured is not None else "没有有限值")
    return Result("steady-state", "expectation", _verdict(measured, float(tol)),
                  measured=measured, tolerance=float(tol), basis="reference_stated",
                  detail=f"最大 |steady_change| = {measured:.3e}")


def _c_declared_bounds(r: Reader, opt: dict) -> Result:
    """算例声明的上下界：``[{quantity: "SUMMARY/beta_n", maximum: 4.0}, …]``
    （``min`` / ``max`` 的拼写也认）。

    ★这是把「这一炮该落在哪」写进算例的地方——运行限（Greenwald 分数、β_N、
    q95、密度）不是定律，是这个场景的判据，所以它们由算例带、由这里量。
    """
    import numpy as np
    bounds = opt.get("bounds") or []
    if not bounds:
        return Result("declared-bounds", "expectation", UNEVALUATED,
                      missing=("bounds",), detail="算例没有声明上下界")
    rows, bad, unread = [], 0, []
    for b in bounds:
        q = str(b.get("quantity", ""))
        block, _, slot = q.partition("/")
        a = r.arr(block, slot) if block and slot else None
        if a is None or not np.isfinite(a).any():
            unread.append(q)
            continue
        finite = a[np.isfinite(a)]
        lo, hi = b.get("min"), b.get("max")
        v_lo, v_hi = float(finite.min()), float(finite.max())
        ok = True
        if lo is not None and v_lo < float(lo):
            ok = False
        if hi is not None and v_hi > float(hi):
            ok = False
        bad += 0 if ok else 1
        rows.append(f"{q} ∈ [{v_lo:.4g}, {v_hi:.4g}]"
                    f"{'' if ok else ' ✗ 越界'}"
                    f"（界：{'' if lo is None else f'≥{lo} '}{'' if hi is None else f'≤{hi}'}）")
    if not rows:
        return Result("declared-bounds", "expectation", UNEVALUATED, missing=tuple(unread),
                      detail="声明的量一个也读不到：" + ", ".join(unread))
    state = PASS if bad == 0 else FAIL
    return Result("declared-bounds", "expectation", state, measured=float(bad), unit="count",
                  tolerance=0.0, basis="reference_stated", detail="；".join(rows),
                  missing=tuple(unread),
                  caveat=(f"{len(unread)} 个声明的量读不到：{', '.join(unread)}",) if unread else ())


# --------------------------------------------------------------------------- #
# 册子
# --------------------------------------------------------------------------- #
CHECKS: dict[str, Check] = {c.id: c for c in [
    Check("finite", "law", "产出的每个数都是有限的",
          "∀x ∈ datasets: isfinite(x)", (), 0.0, "machine_precision",
          ("NaN / Inf 不是一个物理态，也不是「还没算」——后者应当缺席而不是写成 NaN",),
          _c_finite),
    Check("positive-temperature", "law", "绝对温度为正",
          "min(T_e, T_i) > 0", (("CORE_PROFILES", "te"), ("CORE_PROFILES", "ti"),
                                ("SUMMARY", "te_axis"), ("SUMMARY", "ti_axis")),
          0.0, "machine_precision", (), _c_positive_temperature),
    Check("positive-density", "law", "粒子数密度为正",
          "min(n_e, n_i) > 0", (("CORE_PROFILES", "ne"), ("CORE_PROFILES", "ni"),
                                ("SUMMARY", "ne_axis")),
          0.0, "machine_precision", (), _c_positive_density),
    Check("grad-shafranov", "law", "二维平衡满足 Grad–Shafranov 方程",
          "Δ*ψ = −μ₀R²·dp/dψ − f·df/dψ，Δ* = ∂_RR − (1/R)∂_R + ∂_ZZ",
          (("EQUILIBRIUM", "psi_2d"), ("EQUILIBRIUM", "grid_r"), ("EQUILIBRIUM", "grid_z"),
           ("EQUILIBRIUM", "psi_1d"), ("EQUILIBRIUM", "dpressure_dpsi"),
           ("EQUILIBRIUM", "f_df_dpsi")),
          0.02, "measured_band",
          ("二阶中心差分，残差按 ‖Δ*ψ‖ 与 ‖RHS‖ 的均方根归一——网格越粗，截断误差越大",
           "只在边界内、离网格边一格以上的点上取",
           "ψ 每弧度、`Δ*ψ = −μ₀R²p′ − ff′`；相反符号支更小时给注记而不是判负"),
          _c_grad_shafranov),
    Check("grid-monotone", "definition", "网格与时间轴单调，归一化网格在 [0, 1]",
          "diff(x) > 0；0 ≤ ρ_norm, ψ_norm ≤ 1",
          (("CORE_PROFILES", "rho_norm"), ("CORE_PROFILES", "psin"), ("LADDER", "psin"),
           ("SUMMARY", "time")),
          0.0, "machine_precision", (), _c_grid_monotone),
    Check("psi-endpoints", "definition", "一维 ψ 的两端就是 ψ_axis 与 ψ_boundary",
          "|ψ₁ᴰ[0] − ψ_axis| / |ψ_bnd − ψ_axis| ≤ tol，另一端同",
          (("EQUILIBRIUM", "psi_1d"), ("EQUILIBRIUM", "psi_axis"),
           ("EQUILIBRIUM", "psi_boundary")),
          1e-6, "machine_precision", (), _c_psi_endpoints),
    Check("volume-monotone", "definition", "体积随 ρ 单调增，V′ 在轴外为正",
          "diff(V) ≥ 0；V′[1:] > 0", (("LADDER", "volume"), ("LADDER", "vprime")),
          0.0, "machine_precision", ("轴上 V′ = 0 是解析的，所以只看内部点",),
          _c_volume_monotone),
    Check("boundary-closed", "definition", "最外闭合磁面闭合，且在限制器内",
          "|X[0] − X[-1]| / median|ΔX| ≤ tol（tol = 1.5 个采样步）；"
          "越出限制器的深度 ≤ limiter_tolerance × a",
          (("EQUILIBRIUM", "boundary_r"), ("EQUILIBRIUM", "boundary_z"),
           ("EQUILIBRIUM", "limiter_r"), ("EQUILIBRIUM", "limiter_z")),
          1.5, "measured_band",
          ("闭合按采样步量而不按小半径：等值线是采出来的，首末差一个采样步之内就是闭合的",
           "越界按距离量：正落在限制器上的点是「贴着」，不是越界（射线法对这种点是随机的）",
           "没有限制器时只量闭合性，并在结论里说明"),
          _c_boundary_closed),
    Check("pressure-consistency", "definition", "平衡压强对得上剖面的动理压强",
          "max|p_eq − e(n_e T_e + n_i T_i)| / max|p| ≤ tol",
          (("EQUILIBRIUM", "pressure"), ("CORE_PROFILES", "ne"), ("CORE_PROFILES", "te"),
           ("CORE_PROFILES", "ti"), ("CORE_PROFILES", "ni"), ("LADDER", "psin")),
          0.05, "measured_band",
          ("热压强、单一等效离子、无快离子压强；带快粒子的算例会有正的口径差",
           "两侧网格不同时按 ψ_norm 插值，缺共同横坐标就不评"),
          _c_pressure_consistency),
    Check("energy-balance", "definition", "能量约束时间的定义式逐时刻成立",
          "|W_th/τ_E + dW_th/dt − P_heat| / |P_heat| ≤ tol（中位数）",
          (("SUMMARY", "w_th"), ("SUMMARY", "tau_e"), ("SUMMARY", "dw_dt"),
           ("SUMMARY", "p_ohm"), ("SUMMARY", "p_aux"), ("SUMMARY", "p_alpha"),
           ("SUMMARY", "p_rad")),
          0.05, "measured_band",
          ("P_heat 取哪几项是约定：缺省 p_ohm + p_aux + p_alpha − p_rad，可由算例声明",),
          _c_energy_balance),
    Check("greenwald-definition", "definition", "记下的 Greenwald 分数对得上定义",
          "f_G = n̄_e / n_G，n_G[m⁻³] = 10²⁰·I_p[MA]/(π a²[m²])",
          (("SUMMARY", "greenwald"), ("SUMMARY", "ip"), ("CORE_PROFILES", "ne"),
           ("EQUILIBRIUM", "boundary_r"), ("LADDER", "volume")),
          0.15, "measured_band",
          ("n̄_e 取体积平均；记录若用线平均会有几个百分点的口径差",
           "a 取边界外形的 (R_max − R_min)/2"),
          _c_greenwald),
    Check("beta-normalized-definition", "definition", "记下的 β_N 对得上定义",
          "β_N = 100·β_t·a·B₀/I_p[MA]，β_t = 2μ₀⟨p⟩/B₀²",
          (("SUMMARY", "beta_n"), ("SUMMARY", "ip"), ("EQUILIBRIUM", "b0"),
           ("EQUILIBRIUM", "pressure"), ("LADDER", "volume")),
          0.15, "measured_band",
          ("⟨p⟩ 是平衡压强的体积平均（热压强口径）",), _c_beta_normalized),
    Check("q-order", "expectation", "|q95| > |q_axis|（单调 q 的常规位形）",
          "|q95| > |q_axis| 逐时刻", (("SUMMARY", "q_axis"), ("SUMMARY", "q95"),
                                      ("CORE_PROFILES", "q")),
          None, "reference_stated", ("反剪切位形正当地违反它——违反给 conditional 而不是 fail",),
          _c_q_order),
    Check("steady-state", "expectation", "准稳态窗口：steady_change 在声明的界内",
          "max|steady_change| ≤ 算例声明的 tolerance", (("SUMMARY", "steady_change"),),
          None, "reference_stated", ("算例不声明就不判（unevaluated）",), _c_steady_state),
    Check("declared-bounds", "expectation", "算例声明的运行界（β_N、f_G、q95…）",
          "min/max(quantity) 落在算例声明的 [min, max] 内", (),
          None, "reference_stated",
          ("运行限不是定律，是这个场景的判据，所以由算例带",), _c_declared_bounds),
]}

#: 默认跑哪些：定律与定义**全跑**（它们不需要算例声明什么），期望里只跑
#: 算例点名的（``declared-bounds`` / ``steady-state`` 没有声明就是 unevaluated）。
DEFAULT_CHECKS = tuple(c.id for c in CHECKS.values() if c.kind in ("law", "definition"))


def check_ids(kind: str | None = None) -> list[str]:
    return [c.id for c in CHECKS.values() if kind is None or c.kind == kind]


def plan(datasets: Mapping[str, dict], *, only: Sequence[str] | None = None) -> list[dict]:
    """跑之前就说：哪几条能评、哪几条缺什么 —— 不跑一遍不知道是不诚实的。"""
    ids = list(only) if only else list(CHECKS)
    out = []
    for cid in ids:
        c = CHECKS[cid]
        r = Reader(datasets)
        missing = [f"{b}/{s}" for b, s in c.reads if r.raw(b, s) is None]
        out.append({"check": cid, "kind": c.kind, "title": c.title,
                    "evaluable": not missing or len(missing) < len(c.reads),
                    "missing": missing})
    return out


def evaluate(datasets: Mapping[str, dict], *, only: Sequence[str] | None = None,
             options: Mapping[str, Mapping] | None = None) -> list[dict]:
    """把册子上的检查逐条量到这份产出上。

    ``datasets`` 是 ``{端口名: fyo 文档}``（一次运行记录的产出，见
    :func:`fylite.engine.suite.datasets_of`）。``options`` 逐条给参数
    （``tolerance``、``bounds``、``p_heat_terms``…），算例声明什么就传什么。
    """
    ids = list(only) if only else list(CHECKS)
    opts = dict(options or {})
    out: list[dict] = []
    for cid in ids:
        c = CHECKS.get(cid)
        if c is None:
            out.append(Result(cid, "unknown", UNEVALUATED,
                              detail=f"册子上没有这条检查（有的是：{', '.join(CHECKS)}）").as_dict())
            continue
        opt = dict(opts.get(cid) or {})
        if "tolerance" not in opt and c.tolerance is not None:
            opt["tolerance"] = c.tolerance
        reader = Reader(datasets)
        try:
            res = c.fn(reader, opt)
        except Exception as exc:                                   # noqa: BLE001
            #: ★一条检查自己炸了是**这条**的事实，不是整批的：记下来接着量下一条
            res = Result(cid, c.kind, UNEVALUATED,
                         detail=f"检查抛了 {type(exc).__name__}: {exc}")
        if res is None:
            res = Result(cid, c.kind, UNEVALUATED, detail="没有结论")
        d = res.as_dict()
        d.setdefault("title", c.title)
        d["formula"] = c.formula
        if c.assumes:
            d["assumes"] = list(c.assumes)
        out.append(d)
    return out


def summarize(results: Sequence[Mapping]) -> dict:
    """一批结论的统计：逐态计数 + 总判决（最坏者胜）。"""
    counts = {PASS: 0, CONDITIONAL: 0, FAIL: 0, UNEVALUATED: 0}
    for r in results:
        counts[r.get("state", UNEVALUATED)] = counts.get(r.get("state", UNEVALUATED), 0) + 1
    overall = UNEVALUATED
    if results:
        overall = max((r.get("state", UNEVALUATED) for r in results),
                      key=lambda s: _ORDER.get(s, 0))
    #: 全部 unevaluated 与「评了且都过」是两个事实
    return {"overall": overall, "counts": counts, "evaluated": len(results) - counts[UNEVALUATED],
            "total": len(results)}
