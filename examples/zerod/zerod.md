---
title: 典型算例 · 0-D 放电 (Worked Example · 0-D Discharge)
---

# 0-D 放电：功率平衡与时间轨迹

**问的是**：一发放电从击穿到熄灭，电流、密度、温度按给定的波形走，各路功率怎么记账，
聚变功率有多少。**不问**剖面怎么解出来——剖面在这一档是**规定**的（`tier: prescribed`），
不是算出来的。

算例 `zerod-iter-15ma`：ITER 15 MA 感应燃烧，装置牌 `iter`。

## 跑它

```bash
export FYLITE_DEVICE_DIR=~/fylite-decks/iter    # 装置牌见「安装与环境」：从 A-Box 拖回
```

```python
from fylite.engine import cases
cases.run("zerod-iter-15ma")
```

```text
zerod-iter-15ma  bar=zerod -> fylite_zerod  [device iter]
  run r-20260902-190603  (~/.cache/fylite/runs/…)
  fields: 21 mapped, 11 sub-capability, 0 shared, 1 ui
  note: law/h_factor/m_eff/w0 are mapped but engaged only with --predict
  acceptance: unevaluated  converged=unevaluated
```

三件事值得停一下：

- **21 项进了入口，11 项归了子能力。** 那 11 项是蒙特卡洛 UQ（`uq*`）、平衡侧视图
  （`eqauto` / `dl` / `du` / `pfscale`）与磁通账本（`phiavail`）的旋钮——基准运行
  不读它们，所以不跑它们**不算失真**。
- **`converged=unevaluated` 不是不合格**：缺省这一档**规定**剖面、不解能量平衡，
  没有可收敛的东西。要它有，加 `--predict`（下节）。
- **`law` / `hfac` / `meff` / `w0` 已映射但未启用**——它们是预测档的约束定标参数。
  声明「映射了但这一档不读」，比悄悄丢掉诚实。

## 命令行

同一份计划，命令行走一遍——`fy` 是本仓唯一的命令行（Python 包没有）：

```bash
fy run model --preset zerod-iter-15ma -o rec/
```

实测（2026-09-07，本仓检出 · ABI 152），`run_state: succeeded`，`rec/` 里：

| 文件 | 端口 | 字节 |
| :--- | :--- | ---: |
| `plan.jsonld` | 合成好的计划（六层的结果） | 9 057 |
| `record.jsonld` | 记录：状态、用时、内核哈希、每个产出端口的数据集 | 10 790 |
| `summary.fyo.jsonld` | `summary` | 25 716 |
| `core_profiles.fyo.jsonld` | `core_profiles` | 581 421 |
| `entry.fyo.jsonld` | `entry`（内核原始条目块，不寻址 IDS） | 4 995 |

★这一档**不需要装置清单**（0-D 的几何是标量），所以命令行上不必给 `--device`，
也不受〈命令行〉指南里那条「装置类算例跑不起来」的限制。

## Python 入口

```python
from fylite import scenario as S

z = S.model.zerod()          # 缺省：规定剖面
sorted(z)
# ['ip', 'ne', 'p_alpha', 'p_fus', 'p_inj', 'phase', 'provenance', 'q',
#  'rho', 't', 'te', 'ti', 'tier', 'v_loop', 'volume']
```

缺省（一台小机器，不是 ITER）跑出来的量级：

| 量 | 形状 | 值 |
| :--- | :--- | ---: |
| `ip` 等离子体电流 | (120,) | 0 → 4.0e5 A |
| `te` 电子温度 | (120, 41) | 0.0015 → 3 keV |
| `ne` 电子密度 | (120, 41) | 4e16 → 4e19 m⁻³ |
| `p_fus` 聚变功率 | (120,) | 峰值 1893.28 W |
| `p_alpha` α 功率 | (120,) | 峰值 381.12 W |
| `volume` 体积 | 标量 | 13.3106 m³ |
| `tier` | 字符串 | `prescribed` |

`phase` 是一条与时间等长的**相位标签**（`breakdown` / `rampup` / `flattop` /
`rampdown`），不是数——报告与页面按它给时间轴上色。

:::{note}
**`q` 在缺省档是 NaN，这是有意的。** 安全因子要几何才定得出来；不给装置就没有几何，
于是这一列**声明为缺**而不是填一个看着合理的数。给了装置牌（如上面的 `iter`）它才有值。
:::

## 两档：规定与预测

```python
z0 = S.model.zerod()                                    # 甲 · 规定
z1 = S.model.zerod(predict=True, law="ipb98y2", h_factor=1.0, m_eff=2.5)
z1["tier"]                                              # 'predicted'
```

| | 甲 · 规定 `prescribed` | 乙 · 预测 `predicted` |
| :--- | :--- | :--- |
| 温度密度 | **按波形给定** | 由能量平衡**解出** |
| 约束时标 | 不用 | 定标律 `law` × `h_factor`（`K.TAU_LAWS`） |
| 回答得了 | 各路功率的记账、聚变产额 | 「这套加热撑不撑得起这个温度」 |
| 回答不了 | 上面那一列 | 剖面形状（仍是规定的） |

预测档是 `cases.run("zerod-iter-15ma", predict=True)`。★**两档不是精度差别，是问题
差别**：甲问「给定这条轨迹，功率怎么记账」，乙问「这条轨迹自洽吗」。把甲的数当成乙的
答案，是这一层最常见的误读。

## 报告

```python
from fylite.engine import casereport, cases
casereport.render(cases.run("zerod-iter-15ma"), out="out/zerod")
```

八张图，全部由规格按「量对自身坐标」推出，无一处猜坐标轴：

| 图 | 画的是 |
| :-- | :--- |
| 1–2 | 剖面：`electrons/density`、`electrons/temperature` 与 `t_i_average` 对 `rho_tor_norm` |
| 3–4 | 迹线：`ip`、`v_loop` 对 `time` |
| 5 | `fusion_gain` 对 `time` |
| 6 | 功率三条同框：`fusion/power`、`fusion/neutron_power_total`、`heating_current_drive/power_additional` |
| 7–8 | 轴上量：`magnetic_axis/n_e`、`magnetic_axis/t_e` |

★第 6 张把**单位相同**的三条放进同一张图，是规格的分组规则（同坐标 + 同单位 = 一张
图），不是人挑的。换句话说：加一路同单位的功率进记录，它会自己出现在那张图上。


## 这一层有什么、没有什么

★★本节的每个数都来自 2026-09-16 当日实跑，逐条记在校验册的
`tr-pedestal-zerod-bookkeeping-metis`
与 `tr-closure-dt-burn-astra`。

**有的**：`p_fus` · `p_alpha` · `p_inj` · `v_loop` · `ip` 的逐时刻迹，以及 `ne` / `te` / `ti`
在归一 `rho` 上的剖面。喂 ITER 15 MA 那一档，平顶实测 `p_fus` 335 MW、`p_alpha` 67.5 MW、
`p_inj` 33 MW。

**没有的，逐条记明**：

- **不输出热能 W**。而 W 是 0D 最基本的记账量，也是能量约束定律的左边——METIS 的同一张
  认证表给 `wth_J`，这一侧没有对应项。
- **没有加料与抽气的控件**。`dt_fraction` 只定成分，定不了源；于是「存量守恒（加料/抽气/衰变）」
  这条需求在 0D 这一层**无从验起**。
- **没有台基**。边界台基区在 0D 里不存在，它要 1.5D 的 `evolve`（见[演化](../evolve/evolve.md)）。
- **α 功率不分电子 / 离子道**。ASTRA 的同一工作点给出轴上 0.585 / 0.415 的分配，
  这一侧只有总量——而这一分配决定 Te 与 Ti 各被加热多少，对 1.5D 是必需项。

★这几条不是「还没做」，是**做不了**：判据已经立在校验册里，等内核补上入口。

## 两处口径，踩过才记得

**体积用的是 $2\pi^2 R a^2 \kappa$**，逐位如此。喂 METIS 自己的 $R/a/\kappa$ 时，
它比 METIS 的体积高 **2.79 %**，而且四个工作点散布只有 $10^{-4}$ 量级——
★**是公式差，不是噪声**，所以一次可修。它会直接传给存量账：存量 = 密度 × 体积。

**`te_flattop` 收 keV，不是 eV。** 这一条是实测踩出来的：拿 METIS 的 `tem_eV` 直接喂进去，
轴温差了 271 倍。★**单位不对齐时，量出来的是口径差，不是实现差**——这是本仓所有跨码比较的
第一条规矩。

## 剖面是喂进去的，不是算出来的

0D 的 `ne` / `te` / `ti` 剖面由**峰化因子**生成：你给体平均，它按固定的峰化铺成剖面。
所以把它的轴值与另一个码的轴值相比，比的是**峰化约定**，不是算法——实测 ne 轴值恒偏 −26.5 %
（四点几乎不变，因为峰化是固定输入），而 Te 轴值偏 −68 % 到 −73 %（在动，因为对面的剖面
形状随工作点变）。

★要让轴值可判，得喂**剖面**而不是体平均——那是 1.5D 的事。

## 边界

- 剖面在两档里都是**规定形状**（峰化因子给定），0-D 不解输运方程——要剖面演化见
  [含时演化](../evolve/evolve.md)。
- 聚变功率用 Bosch–Hale ⟨σv⟩，杂质辐射按 `zeff` 与所选杂质的冷却率；**没有**边界/偏滤器模型。
- 相位由 `t_ru` / `t_ft` / `t_end` 三个时刻切分，梯形波形由内核单源给出
  （`K.zerod_waveform`），浏览器与 Python 读的是同一条。

<!-- BEGIN GENERATED: tools/examples-book.py —— 勿手改 -->

## 本章的文件

点文件名即得原文。计划可以原样跑、原样改（`fy run <文件>`），脚本用 `python <文件>`；目录、上下文与场景模板是给计划引用的，不单独跑。

| 文件 | id | 标题 |
| :--- | :--- | :--- |
| [`zerod-iter-15ma.jsonld`](zerod-iter-15ma.jsonld) | `cases/zerod-iter-15ma` | ITER 15 MA 感应燃烧（0D 功率平衡） |

<!-- END GENERATED -->
