---
title: 典型算例 · 含时演化 (Worked Example · Time Evolution)
---

# 含时演化：多通道随时间推进

**问的是**：剖面随时间怎么走——电子与离子的能量通道（可选密度与电流通道）一起推进，
源随状态更新，α 加热点不点得起来。这是唯一一档解**带热容**的能量平衡，因此也是唯一
一档报得出 `W_th` / `τ_E` / `β_N` / `Q` 的。

算例 `evolve-iter-15ma`：ITER 15 MA 感应燃烧，**解析几何、自足**——不需要任何外部文件。

## 跑它

```python
from fylite.engine import cases
cases.run("evolve-iter-15ma")
```

```text
evolve-iter-15ma  bar=evolve -> fylite_evolve
  fields: 36 mapped, 78 sub-capability, 0 shared, 0 ui
  acceptance: pass  balance_worst=pass, dt_capped=pass, ped_extrapolation=pass, settled=unevaluated
```

**78 项归了子能力**，比映射的还多——那是这条栏在页面上带的四个控制面板（台基、锯齿、
杂质、电流道…）里、基准运行不读的那些。逐条有名有姓，`cases.plan("evolve-iter-15ma")`
可以全部列出来。

## 命令行

```bash
fy run model --preset evolve-default    -o rec/     # 自足的一档
fy run model --preset evolve-iter-15ma  -o rec/     # ITER 15 MA
```

两档都实测跑完（2026-09-07，`run_state: succeeded`）。**产物形态不同，因为计划自己
说了要哪一种**：`evolve-default` 用缺省的 `jsonld`，而 `evolve-iter-15ma` 的四个输出
端口都绑 `fyo:ImasHdf5Format`，于是写成一个 IMAS 数据入口：

```console
$ find rec -type f | sort
rec/entry.fyo.jsonld       rec/imas/core_transport.h5  rec/imas/master.h5   rec/record.jsonld
rec/imas/core_profiles.h5  rec/imas/equilibrium.h5     rec/imas/summary.h5  rec/plan.jsonld
```

`master.h5` 用外部链接指向四个 IDS 文件。`entry.fyo.jsonld` 留在顶层——它是内核原始
条目块，DD 里没有它的位置，写入方按名把它放到一边（详见[命令行](../../docs/cli.md)
〈记录目录里有什么〉）。

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
fy run examples/evolve/evolve-iter-15ma.jsonld -o out/iter15ma
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

```python
from fylite.engine import casereport, cases
casereport.render(cases.run("evolve-iter-15ma"), out="out/report")
```

九张图：剖面三张（对 `rho_tor`）、迹线五张（对 `time`）、**极向截面一张**。截面画得出来，
是因为这一档把推进**实际所用**的边界轮廓与磁轴写进了 `equilibrium` 记录——视图**绑**那份
几何，不从四个形状标量重推一份（重推出来的会像，但不是同一个东西）。


## 源项与台基：哪些开关在，怎么打开

★★本节的每个数来自 2026-09-16 当日实跑，逐条记在校验册的
`tr-closure-15d-source-switches`。

`evolve-iter-15ma` **默认只开两个**：`heat`（加热）与 `brem`（轫致辐射）。
台基、驱动、锯齿、加料全是关的。★**这是算例的选择，不是内核的缺口**——
别把「本算例没有台基」读成「fylite 没有台基」。

| 控件 | 默认 | 打开之后 |
| :--- | :--- | :--- |
| `pedestal` | `False` | ★真的进装配：8 项产出改变，含 `t_ped` |
| `density` | `False` | ★真的进装配：9 项改变，含 `ne` / `ni`（**加料这一路在这里**） |
| `dt_target` | `0.0` | ★真的进装配：7 项改变（DT 成分调节） |
| `current` | `False` | ★真的进装配：`q` 从 0 变到 3.415、`psi` 变到 36.6 |
| `sawtooth` | `False` | **按名拒绝**：锯齿要电流道，它的触发是 $q(0) < 1$ |
| `ipctl` | `False` | **按名拒绝**：它要电流道才有 `psi` 可读 |

★★**两处拒绝是好事，所以记成成立**：它们不是默默给个数，而是点名说缺什么。
**一个安静地给出无意义结果的开关，比一个拒绝的开关危险得多。**

Python 入口（实跑过的那条）：

```python
from fylite.engine import cases, serve
import json

p = cases.plan("evolve-iter-15ma")
a = json.loads(json.dumps(p["arguments"]))     # 深拷贝，别改到 plan 自己
a["pedestal"] = True                            # 只改一个，其余逐位不变
out = serve.call_mcp_tool(f"fylite_{p['tool']}", a)
```

★命令行的等价形式走 `fy run model --preset evolve-iter-15ma`；本页只对上面这条 Python
路径背书，因为它是当日实跑的那条。

## 它守得住什么

**能量平衡闭到 $1.2\times10^{-13}$**，而且**在每个变体上都闭**——开了台基、开了加料、
改了 DT 成分之后照样。★**一个改了源项却仍然守恒的求解器，比一个守恒得好看但源项没接线的
求解器可信。**

## 驱动电流：三道都在，但这一档喂不出数

`j_bs`（自举）· `j_cd`（外部电流驱动）· `j_lh`（低杂波）——三个产出**名字都在**，
而实测它们在所有变体里恒为零，包括开了电流道之后。

★这不等于内核没有这三道，缺的是**喂给它们的输入**：本算例用 `closure='constant'`、
没有 CD 波源。所以「驱动源项」这一块在这一档**验不了**，判据已经立在校验册里，
下一步是造一个带 CD 源的算例把它喂起来——**而不是把判据删掉**。

## 边界

- 解析（Miller）几何档不解平衡：形状与场是**输入**。要几何与剖面交替更新，换几何档
  （绑一份平衡梯子或导入 g 文件）。
- 台基是**内部边界条件**，不是台基模型：它规定 ρ_ped 处的值，不预言台基高度。
- 无边界/偏滤器耦合；杂质按给定浓度与冷却率进辐射项，不输运。
- 与 JINTRAC / TORAX 的逐点对拍记录里写着**哪些量是喂进去的**，这一节的数不能当成对拍结论读。

<!-- BEGIN GENERATED: tools/examples-book.py —— 勿手改 -->

## 本章的文件

点文件名即得原文。计划可以原样跑、原样改（`fy run <文件>`），脚本用 `python <文件>`；目录、上下文与场景模板是给计划引用的，不单独跑。

| 文件 | id | 标题 |
| :--- | :--- | :--- |
| [`evolve-default.jsonld`](evolve-default.jsonld) | `cases/evolve-default` | 缺省（回到出厂设置） |
| [`evolve-east-hmode.jsonld`](evolve-east-hmode.jsonld) | `cases/evolve-east-hmode` | EAST 长脉冲（欧姆＋辅助加热，含电流道与锯齿） |
| [`evolve-fuse-arc.jsonld`](evolve-fuse-arc.jsonld) | `cases/evolve-fuse-arc` | FUSE · ARC（输入对照，不是 FUSE 的答案） |
| [`evolve-fuse-dtt.jsonld`](evolve-fuse-dtt.jsonld) | `cases/evolve-fuse-dtt` | FUSE · DTT（输入对照，不是 FUSE 的答案） |
| [`evolve-fuse-excite.jsonld`](evolve-fuse-excite.jsonld) | `cases/evolve-fuse-excite` | FUSE · EXCITE（输入对照，不是 FUSE 的答案） |
| [`evolve-fuse-fpp.jsonld`](evolve-fuse-fpp.jsonld) | `cases/evolve-fuse-fpp` | FUSE · FPP（输入对照，不是 FUSE 的答案） |
| [`evolve-fuse-iter.jsonld`](evolve-fuse-iter.jsonld) | `cases/evolve-fuse-iter` | FUSE · ITER（输入对照，不是 FUSE 的答案） |
| [`evolve-fuse-kdemo.jsonld`](evolve-fuse-kdemo.jsonld) | `cases/evolve-fuse-kdemo` | FUSE · K-DEMO（输入对照，不是 FUSE 的答案） |
| [`evolve-fuse-kstar.jsonld`](evolve-fuse-kstar.jsonld) | `cases/evolve-fuse-kstar` | FUSE · KSTAR（输入对照，不是 FUSE 的答案） |
| [`evolve-fuse-manta.jsonld`](evolve-fuse-manta.jsonld) | `cases/evolve-fuse-manta` | FUSE · MANTA（输入对照，不是 FUSE 的答案） |
| [`evolve-fuse-sparc.jsonld`](evolve-fuse-sparc.jsonld) | `cases/evolve-fuse-sparc` | FUSE · SPARC（输入对照，不是 FUSE 的答案） |
| [`evolve-iter-15ma-benchmark.jsonld`](evolve-iter-15ma-benchmark.jsonld) | `cases/evolve-iter-15ma-benchmark` | ITER 15 MA 对标（要先导入两份参考件） |
| [`evolve-iter-15ma.jsonld`](evolve-iter-15ma.jsonld) | `cases/evolve-iter-15ma` | ITER 15 MA 感应燃烧（解析几何，自足） |
| [`evolve-jintrac-iter-15ma-flattop.jsonld`](evolve-jintrac-iter-15ma-flattop.jsonld) | `cases/evolve-jintrac-iter-15ma-flattop` | JINTRAC 15 MA 平顶段 · ITER 作业 102530 · 83.51–99.83 s（参考数据在 fydoc） |
| [`evolve-jintrac-iter-15ma-rampup.jsonld`](evolve-jintrac-iter-15ma-rampup.jsonld) | `cases/evolve-jintrac-iter-15ma-rampup` | JINTRAC 15 MA L-mode case02 · ITER 电流爬升 13.9–66.5 s |
| [`evolve-jintrac-iter-5ma-lmode.jsonld`](evolve-jintrac-iter-5ma-lmode.jsonld) | `cases/evolve-jintrac-iter-5ma-lmode` | JINTRAC 5 MA L-mode · 芯—边耦合（本仓跑不动；源里也没跑完） |
| [`evolve-jintrac-jet-58894.jsonld`](evolve-jintrac-jet-58894.jsonld) | `cases/evolve-jintrac-jet-58894` | JINTRAC case04 · JET #58894（JETTO+EIRENE，本仓跑不动） |

<!-- END GENERATED -->
