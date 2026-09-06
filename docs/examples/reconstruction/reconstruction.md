---
title: 典型算例 · 诊断分析：平衡反演 (Worked Example · Equilibrium Reconstruction)
---

# 诊断分析：平衡反演

**问的是**：给定一发真实放电的磁测量，位形是什么。**不问**该给多少线圈电流——那是
[放电设计](../design/design.md)的反解。两者方向相反：反演的输入是**测量**，输出是位形；
反解的输入是**要的位形**，输出是电流。

本章用 EAST #137985 @ 4.0 s：这也是公开登记册里 **B-06** 记录的那一发。

:::{important}
语料里的 `reconstruction-default` **跑不了**，`cases.run()` 会点名拒绝：那条算例
冻的是**合成孪生生成器**的旋钮（由测量孪生平衡加种子噪声造测量），而那个生成器只在
浏览器的 `worker.js` 里，Python 侧没有对应物。真实测量走的是下面这条路。
:::

## 一 · 测量文档进来

```bash
export FYLITE_DEVICE_DIR=~/fylite-decks/east    # 见「安装与环境」：EAST 牌取自内核仓历史
```

```python
from fylite import fyo

meas = fyo.as_measurements("$FYLITE_DEVICE_DIR/case_east137985_4000ms.fyo.jsonld", 4.0)
sorted(meas)      # ['basis', 'brsp', 'btor', 'coils', 'expmp2', 'plasma', 'time_s']
```

★**这一步就是通道契约**：通道数、次序与单位在这里一次性判定，之后不再有第二处解释。
`basis` 说的是这批测量按哪套基底约化（EAST 的 `est2` 79 探针基底就在这里定名），
`time_s` 是它选中的时刻。测量来源是 MDSplus 还是离线转储，进到这一层之后**不再区分**。

## 二 · 反演

```python
from fylite import scenario as S

r = S.analysis.reconstruction(meas)
```

| 量 | 值 |
| :--- | ---: |
| `ip` | 393459.44 A |
| `rmaxis` / `zmaxis` 磁轴 | 1.8318933 / −0.0189550 m |
| `q0` / `q95` | 0.428272 / 3.700739 |
| `psi_axis` / `psi_bry` | 4.2147042 / 3.0540809 |
| `residual` | 3.427e-7 |
| `iterations` | 800 |
| `nw` × `nh` 网格 | 65 × 65 |
| `npp` / `nff` / `trunc_keep` | 1 / 2 / 3（基函数阶数与截断保留数） |
| `kinetic` | `False`（纯磁反演，未加动理学压强约束） |

同目录里有**另一个码的离线答案**，可以直接对照：

```python
import json
oracle = json.load(open("$FYLITE_DEVICE_DIR/oracle_east137985_4000ms.fyo.jsonld"))
oracle["time_slice"][0]["global_quantities"]["magnetic_axis"]
# {'r': 1.83552056, 'z': -0.0888684195}
```

**逐项差**：ΔR = −3.6 mm，ΔZ = **+69.9 mm**。

:::{caution}
**那 70 mm 不是噪声，是本仓已经归因过的一件事。** 它几乎是纯**共模**——把参考自己的
约束集与虚拟电流（竖直锚点）算进来之后才对得上。完整的账、它值多少 σ、以及打开径向
锚点之后磁轴收到 5.1 / 6.5 mm 的那一组数，写在公开登记册的记录 **B-06** 里。
**不要拿本节这一组数当作「fylite 与 EFIT 差 70 mm」的结论**——本节跑的是不带锚点的
缺省调用，B-06 跑的是带锚点的那一档（`S.analysis.reconstruction(meas, rc_anchor=…,
zc_anchor=…)`：把电流质心的径向 / 竖直位置作为**一条观测行**加进拟合，而不是事后平移）。
:::

## 三 · 加动理学约束

```python
import numpy as np
f = S.analysis.profit(x, y, sigma_frac=0.05)          # 剖面拟合，阶数由 GCV 选
r = S.analysis.reconstruction(meas, pressure=f)       # 磁测量 + 动理学压强
r["kinetic"]                                          # True
```

★**`kinetic` 是一个如实的标签**：它说这一次到底有没有吃到压强约束。它不承诺精度提高——
一条不确定度设得过紧的压强剖面会把解拉偏，而这个标签让读者看得见那一步发生过。

## 四 · 结果怎么落地

```python
from fylite import fyo
eq = fyo.reconstruction(r)                 # -> fyo/JSON-LD 平衡文档
fyo.write(eq, "out/east137985_4000ms.fyo.jsonld")
fyo.as_geqdsk(eq, header="fylite east 137985 4000")   # 要 g 文件时才出门
```

★**g 文件只在门口**。包内一律传文档；`as_geqdsk` / `as_equilibrium` 是它进出的唯一两道门。
产出的平衡文档可以直接喂给[含时演化](../evolve/evolve.md)（作几何梯子）或
[稳定性](../../guide/stability-and-control.md)（作 n=0 分析的对象）。

## 五 · 时间序列

单个时刻之外，`recon_rs.run_series` 按时间片跑一串：

```python
from fylite.scenario.analysis import recon_rs
rows = recon_rs.run_series(shot=137985, times=[3.0, 3.5, 4.0, 4.5], device=dev)
```

★它是**函数不是注册工具**——同一能力的另一个粒度。语料里的 `series-default` 是浏览器
那一栏的会话文档，`--run` 同样按名拒绝。

## 边界

- 反演解的是 Grad-Shafranov 的**自由边界逆问题**，基函数阶数（`npp` / `nff`）与截断
  （`trunc_keep`）是**输入**：它们决定解能表示什么，报出来是为了让读者知道解的自由度。
- 磁探针与磁通环的响应由**装置牌的导体几何现算**（`code/reconstruction` · `code/coilshare`），
  不读 Green 表——所以换机器只换牌。
- `q0` 这类轴上量对基函数阶数敏感；B-06 里有一整段专门讲这个缺口怎么收窄的。
- 本仓不带 EFIT 求解器（`libefit.so` 随许可离开），反演入口因此**跑不动**；
  与它的对照只能引 B-06 冻结下来的那份离线答案。
