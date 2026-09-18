"""剖面的数值件：光滑样条 · 非线性最小二乘 · 稳健清洗 · 台基拟合（只用 Python 标准库）。

本文件是 ``kinetic_recon.py`` 的伴随模块，同样只依赖标准库——本应用不要 numpy 的约束不破。
方法照 Wei et al. 2026（AIP Advances 16, 085007）第 II 节，逐条的出处写在各函数的文档串里。
"""
from __future__ import annotations

import bisect
import math

# ================================================================================================ linear algebra


def solve_dense(a: list, b: list) -> list:
    """稠密线性方程 a·x = b（部分主元高斯消去）；a 是 n×n 的行列表，不改调用方的数据。"""
    n = len(b)
    m = [list(row) + [b[i]] for i, row in enumerate(a)]
    for k in range(n):
        p = max(range(k, n), key=lambda i: abs(m[i][k]))
        if m[p][k] == 0.0:
            raise ZeroDivisionError("singular matrix")
        m[k], m[p] = m[p], m[k]
        piv = m[k][k]
        rk = m[k]
        for i in range(k + 1, n):
            f = m[i][k] / piv
            if f:
                ri = m[i]
                for j in range(k, n + 1):
                    ri[j] -= f * rk[j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / m[i][i]
    return x


def solve_banded_spd(bands: list, rhs: list) -> list:
    """对称正定带状方程：``bands[k][i]`` = A[i][i+k]（k = 0…p），Cholesky（LDLᵀ）带内分解。"""
    n = len(rhs)
    p = len(bands) - 1
    # 带状下三角 L（单位对角）与对角 D
    L = [[0.0] * n for _ in range(p + 1)]  # L[k][i] = L[i+k][i]
    D = [0.0] * n
    for j in range(n):
        s = bands[0][j]
        for k in range(1, min(p, j) + 1):
            s -= L[k][j - k] ** 2 * D[j - k]
        D[j] = s
        for k in range(1, min(p, n - 1 - j) + 1):
            i = j + k
            s = bands[k][j]
            for m in range(1, min(p - k, j) + 1):
                s -= L[k + m][j - m] * L[m][j - m] * D[j - m]
            L[k][j] = s / D[j]
    z = list(rhs)
    for i in range(n):
        for k in range(1, min(p, i) + 1):
            z[i] -= L[k][i - k] * z[i - k]
    x = [z[i] / D[i] for i in range(n)]
    for i in range(n - 1, -1, -1):
        for k in range(1, min(p, n - 1 - i) + 1):
            x[i] -= L[k][i] * x[i + k]
    return x


# ================================================================================================ smoothing spline


class Spline:
    """自然三次样条：节点 ``x``、节点值 ``g``、节点二阶导 ``c``（两端为零）。"""

    def __init__(self, x: list, g: list, c: list):
        self.x, self.g, self.c = x, g, c

    def _seg(self, t: float) -> int:
        j = bisect.bisect_right(self.x, t) - 1
        return min(max(j, 0), len(self.x) - 2)

    def __call__(self, t: float) -> float:
        x, g, c = self.x, self.g, self.c
        if t <= x[0]:  # 自然样条两端线性外推
            return g[0] + self.d1(x[0]) * (t - x[0])
        if t >= x[-1]:
            return g[-1] + self.d1(x[-1]) * (t - x[-1])
        j = self._seg(t)
        h = x[j + 1] - x[j]
        a, b = (x[j + 1] - t) / h, (t - x[j]) / h
        return a * g[j] + b * g[j + 1] + ((a ** 3 - a) * c[j] + (b ** 3 - b) * c[j + 1]) * h * h / 6.0

    def d1(self, t: float) -> float:
        x, g, c = self.x, self.g, self.c
        t = min(max(t, x[0]), x[-1])
        j = self._seg(t)
        h = x[j + 1] - x[j]
        a, b = (x[j + 1] - t) / h, (t - x[j]) / h
        return (g[j + 1] - g[j]) / h + ((1 - 3 * a * a) * c[j] + (3 * b * b - 1) * c[j + 1]) * h / 6.0


def merge_ties(x: list, y: list, w: list, tol: float = 1e-9):
    """按 x 排序并合并（近）重合的横坐标：权重和、加权平均值。"""
    order = sorted(range(len(x)), key=lambda i: x[i])
    xs, ys, ws = [], [], []
    for i in order:
        if xs and x[i] - xs[-1] <= tol:
            wt = ws[-1] + w[i]
            ys[-1] = (ys[-1] * ws[-1] + y[i] * w[i]) / wt if wt > 0 else ys[-1]
            ws[-1] = wt
        else:
            xs.append(x[i]), ys.append(y[i]), ws.append(w[i])
    return xs, ys, ws


def smoothing_spline(x: list, y: list, w: list | None, lam: float) -> Spline:
    """加权自然三次光滑样条（Reinsch 算法）：min Σ wᵢ(yᵢ − g(xᵢ))² + λ∫g''²。

    x 须严格递增（先过 :func:`merge_ties`）。λ → 0 插值，λ → ∞ 退化为加权直线。
    """
    n = len(x)
    if w is None:
        w = [1.0] * n
    if n < 3:
        if n == 2:
            return Spline(list(x), list(y), [0.0, 0.0])
        return Spline([x[0], x[0] + 1.0], [y[0], y[0]], [0.0, 0.0])
    h = [x[i + 1] - x[i] for i in range(n - 1)]
    m = n - 2
    # Q（n × m）的三条对角：列 j 的非零在行 j, j+1, j+2
    q0 = [1.0 / h[j] for j in range(m)]
    q1 = [-1.0 / h[j] - 1.0 / h[j + 1] for j in range(m)]
    q2 = [1.0 / h[j + 1] for j in range(m)]
    winv = [1.0 / wi if wi > 0 else 1e30 for wi in w]
    # A = R + λ Qᵀ W⁻¹ Q ：对称五对角
    b0 = [0.0] * m
    b1 = [0.0] * m
    b2 = [0.0] * m
    for j in range(m):
        b0[j] = (h[j] + h[j + 1]) / 3.0 + lam * (q0[j] ** 2 * winv[j] + q1[j] ** 2 * winv[j + 1] + q2[j] ** 2 * winv[j + 2])
        if j + 1 < m:
            b1[j] = h[j + 1] / 6.0 + lam * (q1[j] * q0[j + 1] * winv[j + 1] + q2[j] * q1[j + 1] * winv[j + 2])
        if j + 2 < m:
            b2[j] = lam * q2[j] * q0[j + 2] * winv[j + 2]
    qty = [q0[j] * y[j] + q1[j] * y[j + 1] + q2[j] * y[j + 2] for j in range(m)]
    gam = solve_banded_spd([b0, b1, b2], qty)
    qg = [0.0] * n
    for j in range(m):
        qg[j] += q0[j] * gam[j]
        qg[j + 1] += q1[j] * gam[j]
        qg[j + 2] += q2[j] * gam[j]
    g = [y[i] - lam * winv[i] * qg[i] for i in range(n)]
    return Spline(list(x), g, [0.0] + gam + [0.0])


# ================================================================================================ nonlinear least squares


def levenberg_marquardt(f, p0: list, x: list, y: list, w: list | None = None, *, lo=None, hi=None,
                        max_iter: int = 200, tol: float = 1e-10):
    """min Σ wᵢ (yᵢ − f(xᵢ, p))²，数值雅可比，参数盒约束（投影）。返回 (p, chi2)。"""
    n, k = len(x), len(p0)
    w = w or [1.0] * n
    lo = lo or [-math.inf] * k
    hi = hi or [math.inf] * k
    clip = lambda p: [min(max(v, lo[i]), hi[i]) for i, v in enumerate(p)]  # noqa: E731
    p = clip(list(p0))

    def chi2(p):
        return sum(wi * (yi - f(xi, p)) ** 2 for xi, yi, wi in zip(x, y, w))

    c = chi2(p)
    mu = 1e-3
    for _ in range(max_iter):
        r = [yi - f(xi, p) for xi, yi in zip(x, y)]
        jac = []
        for j in range(k):
            dp = 1e-6 * max(abs(p[j]), 1e-6)
            pp = list(p)
            pp[j] += dp
            jac.append([(f(xi, pp) - (yi - ri)) / dp for xi, yi, ri in zip(x, y, r)])
        jtj = [[sum(w[i] * jac[a][i] * jac[b][i] for i in range(n)) for b in range(k)] for a in range(k)]
        jtr = [sum(w[i] * jac[a][i] * r[i] for i in range(n)) for a in range(k)]
        improved = False
        while mu < 1e12:
            m = [[jtj[a][b] + (mu * jtj[a][a] if a == b else 0.0) for b in range(k)] for a in range(k)]
            for a in range(k):
                if m[a][a] == 0.0:
                    m[a][a] = mu
            try:
                dpv = solve_dense(m, jtr)
            except ZeroDivisionError:
                mu *= 10
                continue
            pn = clip([p[j] + dpv[j] for j in range(k)])
            cn = chi2(pn)
            if cn < c:
                done = (c - cn) <= tol * max(c, 1e-300)
                p, c, mu, improved = pn, cn, max(mu / 10, 1e-12), True
                break
            mu *= 10
        if not improved or done:
            break
    return p, c


# ================================================================================================ robust cleaning
#: 文献没公布的数（Wei 2026 §II.B 只给了方法与选参判据 score = 0.5 F1 + 0.3 recall + 0.2 precision）——
#: 这里取规格书的建议缺省，逐一记在结果 JSON 里；★它们不是文献的数。
#: ★k_low · α_low 按文献图 1 的**剔除样式**定（不按 NRMSE 调）：#63948 6.022 s 取 (2.0, 0.5) 剔 ρ 0.09 · 0.11 · 0.22 ·
#: 0.49 · 0.78 · 0.94，与文献 5.98 s 标出的 0.07 · 0.2 · 0.45 · 0.5 · 0.67 · 0.8 · ~0.97 同一组 TS 道；(3.0, 0.7) 只剔 4 个、
#: 轴附近孤立的低点留下（4.422 s 的 T_e NRMSE 因此 0.16）。高侧没有文献样例可对，保持 (3.0, 1.3)。
CLEAN_DEFAULTS = {"w_s": 7, "s0_frac": 0.02, "k_low": 2.0, "k_high": 3.0, "alpha_low": 0.5, "alpha_high": 1.3,
                  "inner_iter": 6, "max_frac": 0.3, "lam": 3e-4, "tukey_c": 4.685, "mirror": True}


def _median(v: list) -> float:
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def robust_reference(x: list, y: list, *, lam: float, inner_iter: int = 6, tukey_c: float = 4.685,
                     w0: list | None = None, mirror: bool = False) -> list:
    """全局参照曲线（文献式 (2) 的 y_ref）：光滑样条 + 自适应权重迭代 ``inner_iter`` 次（Tukey 双权），不加单调先验。

    横坐标归一到 [0, 1]、纵坐标归一到极差，λ 因此与数据量纲无关。返回各点处的 y_ref。
    """
    if mirror and x[0] > 0:
        #: 对 ρ = 0 偶延拓（轴上斜率为零，文献对拟合的要求，用在参照曲线上）：轴端不再是自由端，
        #: 两个相邻的低点拉不动它（#63948 5.02 s 实测：不延拓时每剔一点、轴端参照就塌 0.4–0.5 keV）
        n0 = len(x)
        xm, ym = [-v for v in reversed(x)] + list(x), list(reversed(y)) + list(y)
        wm = (list(reversed(w0)) + list(w0)) if w0 else None
        #: 横坐标按数据跨度归一：延拓后跨度约翻倍，三次光滑样条的罚随跨度³ 变，λ 除以 (跨度比)³ 保持同样的硬度
        ratio = (xm[-1] - xm[0]) / ((x[-1] - x[0]) or 1.0)
        return robust_reference(xm, ym, lam=lam / ratio ** 3, inner_iter=inner_iter, tukey_c=tukey_c, w0=wm)[n0:]
    n = len(x)
    x0, span = x[0], (x[-1] - x[0]) or 1.0
    yr = (max(y) - min(y)) or 1.0
    xs = [(xi - x0) / span for xi in x]
    ys = [yi / yr for yi in y]
    base = list(w0) if w0 else [1.0] * n
    #: 起步权重取自 5 点滑动中位的残差：TS 的掉点常两两相邻（#63948 5.02 s 轴附近 0.18 · 0.15 keV 夹在 2–4.6 keV
    #: 之间），等权起步时芯部近乎双峰，Tukey 迭代会把**高**点当离群、参照塌到 2.1 keV；滑动中位不受两个相邻坏点左右。
    rmed = [_median(ys[max(0, i - 2):i + 3]) for i in range(n)]
    r0 = [a - b for a, b in zip(ys, rmed)]
    mad0 = 1.4826 * _median([abs(v - _median(r0)) for v in r0]) or 1e-12
    w = [bi * max(1e-4, (max(0.0, 1 - (ri / (tukey_c * mad0)) ** 2)) ** 2) for bi, ri in zip(base, r0)]
    ref = ys
    for _ in range(inner_iter):
        s = smoothing_spline(xs, ys, w, lam)
        ref = [s(t) for t in xs]
        r = [a - b for a, b in zip(ys, ref)]
        mad = 1.4826 * _median([abs(v - _median(r)) for v in r]) or 1e-12
        w = [bi * max(1e-4, (max(0.0, 1 - (ri / (tukey_c * mad)) ** 2)) ** 2) for bi, ri in zip(base, r)]  # 下限：零权会让五对角奇异
    return [v * yr for v in ref]


def clean_profile(x: list, y: list, opts: dict | None = None) -> dict:
    """文献 §II.B 的局部稳健离群判别，一次剔一个（式 (2)–(7)）。

    x 须严格递增。返回 ``{"keep": [bool], "removed": [(index, score, side)], "params": ...}``。
    """
    o = dict(CLEAN_DEFAULTS, **(opts or {}))
    n = len(x)
    keep = [True] * n
    removed = []
    h = int(o["w_s"]) // 2
    max_remove = max(1, math.ceil(o["max_frac"] * n))
    while len(removed) < max_remove:
        idx = [i for i in range(n) if keep[i]]
        if len(idx) < 5:
            break
        xs, ys = [x[i] for i in idx], [y[i] for i in idx]
        ref = robust_reference(xs, ys, lam=o["lam"], inner_iter=o["inner_iter"], tukey_c=o["tukey_c"],
                               mirror=bool(o.get("mirror")))
        r = [a - b for a, b in zip(ys, ref)]
        s0 = o["s0_frac"] * ((max(ys) - min(ys)) or 1.0)
        best = None
        for k in range(1, len(idx) - 1):  # 边界点不剔
            nb = [r[j] for j in range(max(0, k - h), min(len(idx), k + h + 1)) if j != k]
            med = _median(nb)
            sig = 1.4826 * _median([abs(v - med) for v in nb])
            s = r[k] / max(sig, s0)
            ylin = ys[k - 1] + (ys[k + 1] - ys[k - 1]) * (xs[k] - xs[k - 1]) / (xs[k + 1] - xs[k - 1])
            side = None
            if s < -o["k_low"] and ys[k] < o["alpha_low"] * ylin:
                side = "low"
            elif s > o["k_high"] and ys[k] > o["alpha_high"] * ylin:
                side = "high"
            if side and (best is None or abs(s) > abs(best[1])):
                best = (idx[k], s, side)
        if best is None:
            break
        keep[best[0]] = False
        removed.append(best)
    return {"keep": keep, "removed": removed, "params": o}


# ================================================================================================ profile fit


def mtanh(z: float, a: float, b: float) -> float:
    """Groebner 修正双曲正切：((1 + a z) eᶻ − (1 − b z) e⁻ᶻ) / (eᶻ + e⁻ᶻ)（文献式 (9) 的写法）。"""
    if z > 30:
        return 1 + a * z
    if z < -30:
        return -(1 - b * z)
    ep, em = math.exp(z), math.exp(-z)
    return ((1 + a * z) * ep - (1 - b * z) * em) / (ep + em)


class Pedestal:
    """f(ρ) = B + A·mtanh(z; α, β)，z = 2(x_sym − ρ)/w（文献式 (9)，补上 B：台基高 = A + B）。"""

    def __init__(self, A, B, xsym, w, alpha=0.0, beta=0.0):
        self.A, self.B, self.xsym, self.w, self.alpha, self.beta = A, B, xsym, w, alpha, beta

    def __call__(self, r: float) -> float:
        return self.B + self.A * mtanh(2 * (self.xsym - r) / self.w, self.alpha, self.beta)

    def d1(self, r: float, h: float = 1e-6) -> float:
        return (self(r + h) - self(r - h)) / (2 * h)

    def as_dict(self):
        return {k: getattr(self, k) for k in ("A", "B", "xsym", "w", "alpha", "beta")}


GCV_GRID = [10 ** (-6 + 0.25 * k) for k in range(17)]   #: 1e-6 … 1e-2（归一坐标下的 λ）；下限不让反射计那种
#: 已经反演光滑过的剖面被插值穿过（#63948 5.02 s 实测：无下限时 GCV 取 1.8e-7，n_e 的 NRMSE 0.003——那是插值，不是拟合）


def axis_spline(x: list, y: list, w: list | None, lam) -> Spline:
    """芯部 / L 模样条：数据对 ρ = 0 作偶延拓（轴上一阶导为零，文献的「左端光滑模块」），λ 按归一纵坐标。

    ``lam = "gcv"``：λ 由广义交叉验证定（文献没给光滑度；GCV 让数据自己定，不向文献的 NRMSE 调）。
    """
    if lam == "gcv":
        lam = gcv_lambda(x, y, w)
    w = w or [1.0] * len(x)
    xs = [-v for v in reversed(x)] + list(x)
    ys = list(reversed(y)) + list(y)
    ws = list(reversed(w)) + list(w)
    xs, ys, ws = merge_ties(xs, ys, ws)
    yr = (max(ys) - min(ys)) or 1.0
    span = (xs[-1] - xs[0]) or 1.0
    s = smoothing_spline([v / span for v in xs], [v / yr for v in ys], ws, lam)
    return _Scaled(s, span, yr)


def gcv_lambda(x: list, y: list, w: list | None) -> float:
    """GCV(λ) = n·RSS / (n − tr A)²，在 ``GCV_GRID`` 上取极小；tr A 按「扰动第 i 点（与它的镜像）看拟合值变多少」逐点求。"""
    n = len(x)
    if n < 6:
        return 1e-4
    best = None
    for lam in GCV_GRID:
        s = axis_spline(x, y, w, lam)
        fit = [s(v) for v in x]
        rss = sum((a - b) ** 2 for a, b in zip(y, fit))
        tr = 0.0
        eps = ((max(y) - min(y)) or 1.0) * 1e-3
        for i in range(n):
            yp = list(y)
            yp[i] += eps
            tr += (axis_spline(x, yp, w, lam)(x[i]) - fit[i]) / eps
        g = n * rss / max(n - tr, 1e-9) ** 2
        if best is None or g < best[0]:
            best = (g, lam)
    return best[1]


class _Scaled:
    def __init__(self, s, span, yr):
        self.s, self.span, self.yr = s, span, yr

    def __call__(self, r):
        return self.yr * self.s(r / self.span)

    def d1(self, r):
        return self.yr * self.s.d1(r / self.span) / self.span


FIT_DEFAULTS = {"rho_s": 0.8, "lam_core": "gcv", "lam_l": "gcv", "ped_from": 0.75, "rho_e_lo": 0.82, "rho_e_hi": 0.96,
                "n_out": 101, "join_weight": 4.0}


class Profile:
    """分段剖面：ρ < ρ_s 芯部样条，[ρ_s, ρ_e] 斜率积分过渡（式 (11)），ρ > ρ_e mtanh 台基。"""

    def __init__(self, core, ped=None, rho_s=None, rho_e=None, delta=0.0):
        self.core, self.ped, self.rho_s, self.rho_e, self.delta = core, ped, rho_s, rho_e, delta
        if ped is not None:
            self.fs, self.ss, self.se = core(rho_s), core.d1(rho_s), ped.d1(rho_e)

    def __call__(self, r: float) -> float:
        if self.ped is None or r < self.rho_s:
            return self.core(r)
        if r > self.rho_e:
            return self.ped(r)
        u = r - self.rho_s
        L = self.rho_e - self.rho_s
        # 式 (11) 的闭式；★δ 项是本应用补的：让过渡段在 ρ_e 处的值也接上台基（文献只保证斜率）
        return self.fs + self.ss * u + (self.se - self.ss) * u * u / (2 * L) + self.delta * (u / L) ** 2


def fit_profile(x: list, y: list, w: list | None = None, *, mode: str = "H", y_sep: float | None = None,
                opts: dict | None = None) -> dict:
    """文献 §II.C：L 模全段样条；H 模芯部样条 + mtanh 台基 + 斜率积分过渡。

    ``y_sep``：分界面上钉住的值（T_e 取 50 eV）；None 则台基的 B 自由（n_e 以最靠边的点作低值参照）。
    """
    o = dict(FIT_DEFAULTS, **(opts or {}))
    w = w or [1.0] * len(x)
    if mode == "L":
        prof = Profile(axis_spline(x, y, w, o["lam_l"]))
        return {"profile": prof, "mode": "L"}
    rho_s = o["rho_s"]
    # 1) 台基形：外区数据（+ 分界面值）做一次 mtanh 全参数拟合，定形状参数 w · x_sym · α
    xo = [xi for xi in x if xi >= o["ped_from"]]
    yo = [yi for xi, yi in zip(x, y) if xi >= o["ped_from"]]
    wo = [wi for xi, wi in zip(x, w) if xi >= o["ped_from"]]
    if len(xo) < 4:
        return fit_profile(x, y, w, mode="L", opts=o) | {"mode": "L", "fallback": "too few pedestal points"}
    if y_sep is not None:
        xo, yo, wo = xo + [1.0], yo + [y_sep], wo + [max(wo) * 4]
    top0 = sum(wi * yi for xi, yi, wi in zip(xo, yo, wo) if xi <= 0.9) / max(
        1e-30, sum(wi for xi, wi in zip(xo, wo) if xi <= 0.9))  # 台基顶的加权平均初值
    lo_y = min(yo)
    f5 = lambda r, p: Pedestal(p[0], p[1], p[2], p[3], p[4])(r)  # noqa: E731
    lo5, hi5 = [0, -abs(top0), 0.80, 0.01, -0.5], [10 * abs(top0) + 1e-9, abs(top0), 1.05, 0.25, 2.0]
    #: 多起点：单一起点（x_sym 0.95、宽 0.05）在台基膝部靠里的剖面上落进 A = 0 的平线局部极小
    #: （#63948 5.022 s 的 n_e 实测：膝在 ρ ≈ 0.8），先 α = 0 定位置与宽度，再放开 α
    best = None
    for xs0 in (0.85, 0.9, 0.95, 1.0):
        for w0 in (0.03, 0.08, 0.15):
            p0 = [(top0 - lo_y) / 2, (top0 + lo_y) / 2, xs0, w0, 0.0]
            p4, c4 = levenberg_marquardt(f5, p0, xo, yo, wo, lo=lo5[:4] + [0.0], hi=hi5[:4] + [0.0])
            if best is None or c4 < best[1]:
                best = (p4, c4)
    p5, _ = levenberg_marquardt(f5, best[0], xo, yo, wo, lo=lo5, hi=hi5)
    A, B, xsym, wid, alpha = p5
    core = axis_spline([xi for xi in x if xi <= o["rho_s"] + 0.05], [yi for xi, yi in zip(x, y) if xi <= o["rho_s"] + 0.05],
                       [wi for xi, wi in zip(x, w) if xi <= o["rho_s"] + 0.05], o["lam_core"])
    # 2) 形状（x_sym · w · α）固定，非线性最小二乘只调台基的幅度 A 与台基段起点 ρ_e（文献：「台基顶高与台基段起点」）。
    #    残差 = 合成剖面（芯部 · 式 (11) 过渡 · 台基）在 ρ ≥ ρ_s 各测点上的偏差 + ρ_e 处台基与芯部的值、斜率失配。
    #    ★以「ρ_e 处的顶值」作参数时，ρ_e 落在 x_sym 外侧 mtanh 变号、A 发散（#63948 5.022 s 的 n_e 实测）——故直接用 A。
    def ped_of(q):
        amp, _ = q
        pd = Pedestal(amp, B, xsym, wid, alpha)
        if y_sep is not None:  # 分界面值钉住：B 随 A 重解
            pd.B = y_sep - amp * mtanh(2 * (xsym - 1.0) / wid, alpha, 0.0)
        return pd

    def composite(q):
        pd = ped_of(q)
        tmp = Profile(core, pd, rho_s, q[1])
        L = q[1] - rho_s
        tmp.delta = pd(q[1]) - (tmp.fs + (tmp.ss + tmp.se) * L / 2)
        return pd, tmp

    xp = [xi for xi in x if xi >= rho_s]
    yp = [yi for xi, yi in zip(x, y) if xi >= rho_s]
    wp = [wi for xi, wi in zip(x, w) if xi >= rho_s]
    jw = o["join_weight"] * (sum(wp) / len(wp) if wp else 1.0)
    npts = len(xp)
    cache = {}

    def model(i, q):
        key = (q[0], q[1])
        if key not in cache:
            cache.clear()
            cache[key] = composite(q)
        pd, prof_q = cache[key]
        if i < npts:
            return prof_q(xp[i])
        if i == npts:
            return pd(q[1]) - core(q[1])
        return (pd.d1(q[1]) - core.d1(q[1])) * 0.05  # 斜率乘一个 Δρ 量纲，与值同尺度

    xi_idx = list(range(npts + 2))
    yi_tgt = yp + [0.0, 0.0]
    wi_all = wp + [jw, jw]
    best_q = None
    for re0 in (0.84, 0.88, 0.92):
        qq, cq = levenberg_marquardt(model, [A, re0], xi_idx, yi_tgt, wi_all,
                                     lo=[0.0, max(o["rho_e_lo"], rho_s + 0.02)], hi=[10 * abs(A) + abs(top0) + 1e-9, o["rho_e_hi"]])
        if best_q is None or cq < best_q[1]:
            best_q = (qq, cq)
    q = best_q[0]
    ped, prof = composite(q)
    rho_e = q[1]
    delta = prof.delta
    return {"profile": prof, "mode": "H", "rho_e": rho_e, "pedestal": ped.as_dict(), "join_delta": delta}


def nrmse(x: list, y: list, f) -> float:
    """文献式 (14)：sqrt(mean((y − f)²)) / (max y − min y)，只算清洗后留下的测点。"""
    if not x:
        return float("nan")
    r = math.sqrt(sum((yi - f(xi)) ** 2 for xi, yi in zip(x, y)) / len(x))
    span = max(y) - min(y)
    return r / span if span > 0 else float("nan")
