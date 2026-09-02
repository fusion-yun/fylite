---
title: 典型算例 · 含时演化 (Worked Example · Time Evolution)
---

# 含时演化：多通道随时间推进

**问的是**：剖面随时间怎么走——电子与离子的能量通道（可选密度与电流通道）一起推进，
源随状态更新，α 加热点不点得起来。这是唯一一档解**带热容**的能量平衡，因此也是唯一
一档报得出 `W_th` / `τ_E` / `β_N` / `Q` 的。

算例 `evolve-iter-15ma`：ITER 15 MA 感应燃烧，**解析几何、自足**——不需要任何外部文件。

## 跑它

```bash
fylite cases --run evolve-iter-15ma
```

```text
evolve-iter-15ma  bar=evolve -> fylite_evolve
  fields: 36 mapped, 78 sub-capability, 0 shared, 0 ui
  acceptance: pass  balance_worst=pass, dt_capped=pass, ped_extrapolation=pass, settled=unevaluated
```

**78 项归了子能力**，比映射的还多——那是这条栏在页面上带的四个控制面板（台基、锯齿、
杂质、电流道…）里、基准运行不读的那些。逐条有名有姓，`fylite cases --plan evolve-iter-15ma`
可以全部列出来。

## 它算出了什么

400 步走到 8 s（`t` 0.02 … 8 s）：

| 量 | 形状 | 范围 |
| :--- | :--- | :--- |
| `te` 末态电子温度剖面 | 31 | 3000 … **23341.8 eV**（轴上 23.3 keV） |
| `ti` 末态离子温度剖面 | 31 | 3000 … 21676.9 eV |
| `ne` 密度剖面 | 31 | 7e19 … 1e20 m⁻³ |
| `te_axis` 轴温迹线 | 400 | 8086.78 → 23341.8 eV |
| `p_alpha` α 功率迹线 | 400 | 1.169e7 → **7.453e7 W**（74.5 MW） |
| `beta_n` 迹线 | 400 | 0.948 … 1.767 |
| `steps` / `geometry` | | 400 / `miller` |

**三条验收都过：**

- `balance_worst = 1.18e-13`——每一步的能量平衡残差最坏值。这是**守恒判据**，不是物理
  判据：它说离散格式没有漏掉能量，不说这个 χ 对。
- `dt_capped = 0`——没有一步被稳定性上限截短（截短了不算错，但说明步长给大了）。
- `ped_extrapolation = 0`——没有一处台基外推越界。
- `settled = unevaluated`——8 s 之内它**没打算**走到定态，所以这条判据没有主语。

★**`j_bs` 与 `q` 全是零，因为电流道关着**（这条算例的 `ch-current = false`）。零不是
「自举流为零」这个物理结论，是「这一次没解这条通道」。报告照印，不替它补。

## Python 入口

```python
from fylite import scenario as S

e = S.model.evolve(
    a=2.0, r0=6.2, b0=5.3, kappa=1.86, delta=0.48, q95=3.0,
    te_axis=8000.0, ti_axis=8000.0, ne_axis=1.0e20,
    edge_te=300.0, edge_ti=300.0, edge_ne=3.0e19,
    p_e=20e6, p_i=20e6, alpha=True,
    n_steps=40, dt=0.01, dt_target=0.05)

e["te"][0], e["ti"][0]        # 8478.99, 8356.64  （40 步之后的轴温）
sorted(e)[:8]
# ['balance', 'balance_worst', 'beta_n', 'dt_capped', 'dt_used', 'geometry', 'gm3', 'j_bs']
```

要打开更多通道：`ch_density=True`（密度道）、`ch_current=True`（电流道，随之给出
`j_bs` / `q` / `psi`）、`sawtooth=True`（锯齿混合）、`pedestal=True`（台基）。

## 交付成 IMAS 数据入口

这条算例的计划**自己声明**了产出格式：四个输出端口都要 `fyo:ImasHdf5Format`。所以

```bash
fylite case run cases/evolve-iter-15ma.jsonld --record out/iter15ma
```

写出的不是逐 IDS 的 JSON-LD，而是**一个 IMAS 数据入口**——`out/iter15ma/imas/master.h5`
加 `core_profiles.h5` / `equilibrium.h5` / `summary.h5` / `core_transport.h5`，imas-core 的
HDF5 后端布局。用 h5py 直接读回：

```python
import h5py
with h5py.File("out/iter15ma/imas/core_profiles.h5") as f:
    te = f["core_profiles/profiles_1d[]/electrons/temperature"][:]
te.max()        # 23341.8 eV — 与上表同一个数
```

★**格式是计划说的，不是命令行说的。** 命令行的 `--format` 只在计划没声明时兜底；
一份计划要 IMAS，任何人在任何机器上跑它都得到 IMAS。

## 报告

```bash
fylite cases --report evolve-iter-15ma --out out/report
```

九张图：剖面三张（对 `rho_tor`）、迹线五张（对 `time`）、**极向截面一张**。截面画得出来，
是因为这一档把推进**实际所用**的边界轮廓与磁轴写进了 `equilibrium` 记录——视图**绑**那份
几何，不从四个形状标量重推一份（重推出来的会像，但不是同一个东西）。

## 边界

- 解析（Miller）几何档不解平衡：形状与场是**输入**。要几何与剖面交替更新，换几何档
  （绑一份平衡梯子或导入 g 文件）。
- 台基是**内部边界条件**，不是台基模型：它规定 ρ_ped 处的值，不预言台基高度。
- 无边界/偏滤器耦合；杂质按给定浓度与冷却率进辐射项，不输运。
- 与 JINTRAC / TORAX 的逐点对拍见公开登记册（`benchmark/`）的 B-02 / B-05 记录——
  那里写着**哪些量是喂进去的**，这一节的数不能当成对拍结论读。
