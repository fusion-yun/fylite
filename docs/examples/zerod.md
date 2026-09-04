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

## 边界

- 剖面在两档里都是**规定形状**（峰化因子给定），0-D 不解输运方程——要剖面演化见
  [含时演化](evolve.md)。
- 聚变功率用 Bosch–Hale ⟨σv⟩，杂质辐射按 `zeff` 与所选杂质的冷却率；**没有**边界/偏滤器模型。
- 相位由 `t_ru` / `t_ft` / `t_end` 三个时刻切分，梯形波形由内核单源给出
  （`K.zerod_waveform`），浏览器与 Python 读的是同一条。
