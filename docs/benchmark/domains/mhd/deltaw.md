---
title: "全 delta-W、V5 基准与阻性壁模"
---

# 全 delta-W、V5 基准与阻性壁模

*MHD 稳定性 (MHD Stability) · 本域答：三项齐全的 delta-W 对着国际 V5 基准的五码带落不落得进去；阻性壁模窗口在哪。*

三项齐全的 $\delta W$，对着国际 V5 基准。这一章与上一章的区别是：★**这里没有自证可用了**，
判据只能是"落不落进别人的带里"。

V5 是多码基准，五个码各给一个数，形成一条带。落进带里算通过——但这句话要说得准确：
**落进带里不证明算对了，只证明没有明显算错。** 带宽本身是那五个码之间的分歧，它既包含
数值误差，也包含模型差。所以这一域的记录 `comparison_kind` 是 `benchmark`（对拍）而不是
`verification`（验证），容差取的是**实测带**而不是机器精度。这个区分不是文字游戏：
把对拍说成验证，是本册最想防住的那种夸大。

阻性壁模是这一章的收口。理想壁分支与无壁分支之间那段窗口，转换点应当正好落在解析带边上——
这给了这一章少有的一条硬锚。壁越近 $\gamma$ 越小则是结构性单调，抓的是接线而不是精度。

★记录在这一域尤其要写清**不可比的部分**：参考的五个码各自解了哪几道方程、边界条件取在哪、
真空区怎么处理。V5 的带看起来是一个区间，实际上是五个不完全相同的问题的答案摞在一起。
不写清这一层，"落在带内"这句话就不可复算。

★上一册在这一域**没有记录**。同前，是真空白。

### 全 δW 支的柱位形一级：螺旋箍缩与动能归一（2026-09-18）

`FR-EQ-026`、`027`、`028` 入册，判**成立**。这三条还是**验证**（`verification`）：柱位形有解析锚可对，
五码带要到下面的环几何（`029`–`031`）才用得上。

**完整 δW（027）。** Newcomb (1960) 的 $f,g$ 两式都实现，逐点只差舍入（1.6e-13；剖面带解析导数进来，
所以不是上游那种「随网格二阶消失」）。★★绝对尺换了一条路：原文 Eq. (9) 的 Λ 与 (15)–(17) 只在分部积分后相等，
拿它作见证——**它当场抓到我初版把 Eq. (9) 的分母多作用了一项**，差 3.5 倍；照原文排版改后 2.1e-15。
Suydam 两路（α 由 (32a) 两式、(33) 的恒等式）都到 1e-15 量级。

**ω²（028）。** Newcomb (8) 的极小化前形式，(ξ, u, v) 实变量，真空以 $I_m/K_m$ 精确标量势作边界项。
θ-pinch 的慢谱底与 Alfvén 簇按 h² 收敛；与 δW 核的边缘同点到 2e-12；★★真空标量势复现 `FR-EQ-017` 的带边
1.0 / 1.0625（0.9984 / 1.0605）——**这是全 δW 支与 L0 唯一不依赖外部数据的连接点**。★窗口闭合：同一 $q_a$，
把真空换成无压强等离子体，冻结约束让共振面成了理想壁，−2e-2 变成 −4e-17。**真空不是无压强等离子体。**

★★**锁死，本章最大的一处实测收获**：SRS 规定「线性元 ξ × 逐单元常值 u、v」。约束项按 4 点 Gauss 积分时，
两个常数满足不了单元内处处成立的两条约束——刚性位形（$R/a=100$）上带边从 1.20 才慢慢爬到 1.01，ω² 只一阶收敛。
**约束项改取单元中点**后，两条约束在中点上恰能满足，离散能量就是 Eq. (14) 的 Gauss 积分：带边 100 单元即 0.99998，
ω² 比回到 3.95 / 3.99。

**交付层（026）。** `fylite.mhd_records`：能量原理的结论不是增长率（`growthrate` 留空、装配处拦下混用）、
判读量只进 `code.parameters`、告诫随记录走、`n_phi` 缺省留空、`ideal_flag` 不猜——每条禁令都是一次拒绝，
每次拒绝都在本仓的门里被证伪过。
详见 [`mhd-deltaw-screw-pinch`](../../reports/mhd-deltaw-screw-pinch.md) ·
[`mhd-deltaw-normal-modes`](../../reports/mhd-deltaw-normal-modes.md) ·
[`mhd-deltaw-delivery-records`](../../reports/mhd-deltaw-delivery-records.md)。

### 环几何：Chance 1978 Table I 全八行（2026-09-18）

`FR-EQ-029`、`030`、`031` 入册，判**成立**。这三条是**对拍**（`benchmark`）：落进五码带只说明没有明显算错。

| 行 | 本仓 | 三码（KERNER / PEST / ERATO） |
| :--- | ---: | :--- |
| 定形 $q_0=0.3$, $n=2$ | **0.4314** | 0.413 / 0.427 / 0.431 |
| 定形 $q_0=0.7$, $n=2$ | **0.1199** | 0.118 / 0.119 / 0.120 |
| 无壁 $q_0=1.2$, $n=1$ | **0.758** | — / 0.75 / 0.78 |
| 无壁 $q_0=2.0$, $n=1$ | **0.673** | — / 0.68 / 0.75 |
| 无壁 $q_0=0.6$, $n=2$ | **1.377** | — / 1.31 / 1.40 |
| 无壁 $q_0=1.0$, $n=2$ | **1.065** | — / 1.03 / 1.07 |
| $\Lambda=2$ $q_0=1.791$, $n=1$ | **0.2041** | 0.202 / 0.204 / — |
| $\Lambda=2$ $q_0=2.2387$, $n=1$ | **0.5058** | 0.504 / 0.506 / — |

**平衡与坐标。** Solov'ev 在 Kerner 坐标下**全解析**：$X=(1+2\varepsilon\rho\cos\vartheta)^{1/2}$，二维 Jacobian
$D=E\varepsilon^2\rho/X^2$，于是 $q(\rho)=q_0\langle(1+2\varepsilon\rho\cos\vartheta)^{-3/2}\rangle$、直场线角 θ* 由同一权的
Fourier 系数谱给出。J × B = ∇p 到 5e-16。★印值 $q(s)$ 比这里低 0.12 %，**六行同一比值**——是印表的求法之差。

**离散。** `FR-EQ-028` 的教训直接推广：ξ^ρ 线性元，另两分量逐单元常值（它们在 Q 与 ∇·ξ 里不带 ρ 导数），
能量取单元中点。★两个照实记的坑：**混叠**（极向点数不到 4M 时增长率跳到 1.0，现已按名拒绝）与**伪模**
（径向单元对谐波宽度不够时出一个 0.22 的假本征值——「加谐波」必须配「加径向单元」）。
柱极限对 F2 柱码 1 %。

**真空。** 环 Green 函数 $Q_{n-1/2}$ 取椭圆积分闭式、一步递推。★外 NtD **没走** SRS 记的 Kress 分裂边界元，
走**基本解法**：源点在等离子体内，解逐点满足方程与衰减，没有奇异积分可写错；判官是同一条柱锚（7.5e-5）。
★MFS 的坑：源点数随网格加倍时条件数爆掉（增长率跳到 2000）——已与等离子体网格脱钩。
有壁用环隙 MFS（壁外另一组源点），柱锚 3e-5。

**阻性壁模（031 乙，柱位形）。** Freidberg (11.169)/(11.170)：窗口三段的转换点 0.998 / 1.480 / 2.000
对解析带边 1 / 1.48225 / 2；γτ_w 随壁移近单调降。★★(f, g) 分部形式与 Eq. (8) 口径差一个边界项 $[S\xi^2]_a$——
拿掉它，δW_∞ 在不稳带内被**静默地**错判为正；这一条钉成了测试。★环几何 RWM 本仓未做。
详见 [`mhd-deltaw-toroidal-fixed-boundary`](../../reports/mhd-deltaw-toroidal-fixed-boundary.md) ·
[`mhd-deltaw-toroidal-free-boundary`](../../reports/mhd-deltaw-toroidal-free-boundary.md) ·
[`mhd-deltaw-wall-and-rwm`](../../reports/mhd-deltaw-wall-and-rwm.md)。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-03` v0.43）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-03` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`FR-EQ-026` · MHD 判读的交付层** — MUST · 验证方法：检查 + 测试

> ★三条禁令**逐条证伪**：L0/L1/oracle 的 `growthrate` 一律为空 · ★★**装配处拦下**「能量原理类 `kind` 却带有限 `growthrate`」 · 本仓侧判读量只在 `parameters`、DD 字段不越界 · L0 标 `q_limit` 且注明**禁称 β 极限** · 气球模 `n_phi` **缺省留空**（显式给才填、非正即拒）· ★表面电流记录**自带** optimistic/柱等价告诫 · `source` 为空即拒（oracle 与标度两处）· ★经验标度**不填任何 DD 计算字段** + 非有限值拒收 · `ideal_flag` **不替调用方猜**（阻性壁竖直模须显式 0）· ★自包含用**语法树**查 import（查原文会被本模块自己的说明文字绊倒——初稿即如此）

**`FR-EQ-027` · 完整 $\delta W$：螺旋箍缩（V5 的第一级）** — MUST · 验证方法：检查 + 测试

> ★★**$g$ 两式互证**（场形式 vs 压强形式，仅在平衡关系下相等；符号计算差恒为零、数值二阶收敛至 2.6e-7）· ★★**绝对尺**（SymPy 精确符号 $f,g$ + 高精度求积，$\delta W$ 二阶收敛至 $10^{-9}$，误差比 $\simeq4$）· ★**Suydam 两条独立路**（$\alpha$ 由 Eq. (32a) 两侧分别算相符 $10^{-6}$；Eq. (33) 左端恒等于 $(\alpha+4\beta)B^2/(8B_\theta^2)$）· 无剪切时判据退化为 $\dv*{P}{r}>0$ **且有非空对照** · $f\ge0$ 且奇异面上恰为零 · 纯轴向场必稳（带非空对照）· 本征值符号与最优试探函数的 $\delta W$ 同号 · ★**非平衡的 $\dv*{P}{r}$ / $r=0$ 网格 / $m=k=0$ / 未知 form / 非整数 $m$ 一律 fail-loud**

**`FR-EQ-028` · 动能归一与 $\omega^2$（全 $\delta W$ 支 F2）** — MUST · 验证方法：检查 + 测试

> ★★**转录符号闭合**（Eq. 8–10 对 $(u,v)$ 逐点极小化恰得已签核 $f,g$ + 零拉氏量，$S$ 恰为 Eq. 17 分部积分项，极小点 $\nabla\cdot\boldsymbol\xi=0$ 且 $\zeta=\zeta_0$——无自由参数）· ★★**θ-pinch 解析谱**（慢连续谱底 rel $1.4\times10^{-8}$ · Alfvén 簇 $6\times10^{-7}$）· ★**边缘同点**（Suydam 家族 $c^*\approx0.316$ 两侧同判；连续谱地板随网格收敛）· ★★**解析带边复现**（真空标量势边界项：有壁 1.0625 / 无壁 1.0 两支均 $<0.01$）· ★★**窗口闭合对照**（同一 $q_a$：真空强不稳 vs 等离子体填充只剩地板，差 $>10^2$）· 真空系数三独立核（$ka\to0$ 闭式 $10^{-9}$ · 壁贴边发散 · 单调）· $\omega^2\propto1/\rho$ 精确 · γ 无关边缘 · $\mathbf M$ 正定 $\mathbf A$ 对称 · 二阶收敛（比 4.1）· 负压强/非正 γ/坏 ρ fail-loud

**`FR-EQ-029` · 环几何全 $\delta W$：定形边界 V5（全 $\delta W$ 支 F3 第一段）** — MUST · 验证方法：检查 + 测试

> ★平衡转录三重自证（GS 解析恒等 · $q(0)$ 回收 · $q(a)$ 对印值 0.5224）· ★★柱极限交叉验证（Chance §4A 对 F2 柱码，15% 内）· ★★**V5 定形边界两行**（$q_0=0.3$: **0.4206** 落五码带 [0.413,0.431] **带内**；$q_0=0.7$: **0.1146** 对 [0.118,0.120] 差 2.9%；判据含**自下单调收敛**）· 取向守卫内置断言 · 非单调/越界网格 fail-loud

**`FR-EQ-030` · 环几何真空标量势与无壁 V5（全 $\delta W$ 支 F3 收口段）** — MUST · 验证方法：检查 + 测试

> ★$Q_{\pm1/2}$ 闭式自证 · ★柱极限 NtD 锚 1%（曾抓住 Kress 分裂系数错写=静默一阶污染）· ★★自由边界柱锚 O(ε) 收敛（11.8%→4.2%）· ★★**V5 无壁四行**（0.7077/0.6048/1.3153/1.0205，距最近码 5.4%/7.8%/0.4%/0.9%，容差 15%）· 两支分离

**`FR-EQ-031` · 理想壁分支与薄壁阻性壁模（E-3 第一级）** — MUST · 验证方法：检查 + 测试

> ★环隙 Bessel 锚 <1%（符号唯一选出）· ★★**Λ=2 两行**（0.1943/−3.8% · 0.4928/−2.2% ⇒ **Table I 全八行**）· ★★RWM 窗口三段转换点＝解析带边（rwm↔ideal 二分对 1.48225 差 <0.01）· 壁越近 γ 越小 · 几何因子精确/近似互证 · $(r\xi'/\xi)_a$ 壁无关逐位 · 三支排序 ω²(Λ=1)≥ω²(Λ)≥ω²(∞) · 守卫（Λε≥1/2 / 厚壁 / m=0 / 域内共振）fail-loud

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`mhd-deltaw-delivery-records`](../../reports/mhd-deltaw-delivery-records.md) | 验证 | 成立 | IMAS DD 4.1.1 `mhd_linear` 与 SRS 的四条口径纪律 | 1.1 | 草稿 | [jsonld](../../records/mhd-deltaw-delivery-records.jsonld) |
| [`mhd-deltaw-normal-modes`](../../reports/mhd-deltaw-normal-modes.md) | 验证 | 成立 | Newcomb (1960) Eqs. (6)–(10)；均匀 θ-pinch 的解析谱；FR-EQ-017 的解析带边 | 1.1 | 草稿 | [jsonld](../../records/mhd-deltaw-normal-modes.jsonld) |
| [`mhd-deltaw-screw-pinch`](../../reports/mhd-deltaw-screw-pinch.md) | 验证 | 成立 | Newcomb, *Hydromagnetic stability of a diffuse linear pinch*, Ann. Phys. **10**, 232 (1960) | 1.1 | 草稿 | [jsonld](../../records/mhd-deltaw-screw-pinch.jsonld) |
| [`mhd-deltaw-toroidal-fixed-boundary`](../../reports/mhd-deltaw-toroidal-fixed-boundary.md) | 对拍 | 成立 | Chance et al., *Comparative numerical studies of ideal MHD instabilities*, J. Comput. Phys. 28, 1 (1978), Table I | 1.0 | 草稿 | [jsonld](../../records/mhd-deltaw-toroidal-fixed-boundary.jsonld) |
| [`mhd-deltaw-toroidal-free-boundary`](../../reports/mhd-deltaw-toroidal-free-boundary.md) | 对拍 | 成立 | Chance et al., *Comparative numerical studies of ideal MHD instabilities*, J. Comput. Phys. 28, 1 (1978), Table I | 1.0 | 草稿 | [jsonld](../../records/mhd-deltaw-toroidal-free-boundary.jsonld) |
| [`mhd-deltaw-wall-and-rwm`](../../reports/mhd-deltaw-wall-and-rwm.md) | 对拍 | 成立 | Chance 1978 Table I 的 Λ = 2 两行；Freidberg (2014) §11.5 Eqs. (11.148)–(11.150)、(11.169)–(11.170) | 1.0 | 草稿 | [jsonld](../../records/mhd-deltaw-wall-and-rwm.jsonld) |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
