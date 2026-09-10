---
title: B-09 · DINA 的 ITER 含时场景：爬升段的电阻环电压
---

# B-09 · DINA 的 ITER 含时场景：爬升段的电阻环电压

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | DINA · ITER 含时参考场景 XA8GXS_v1_1 · restricted（ITER IDM Internal Use） |
| **对象** | fylite: 0-D 的 Spitzer + 新经典电阻（`loop_voltage_ohmic`，本仓自己的实现，测试里不重抄公式） |
| **算例** | `scenario/iter-dina-pulse`（ITER 15 MA 感应脉冲的全程（DINA：电流爬升 / 平顶 / 下降）） |
| **数据** | 见 §5 表（1 项，纳入类别 restricted） |
| **门** | `python/tests/test_dina_ramp.py::test_the_reference_really_covers_the_ramp`；`python/tests/test_dina_ramp.py::test_the_resistive_loop_voltage_agrees_through_the_ramp`；`python/tests/test_dina_ramp.py::test_the_flat_top_is_excluded_and_this_is_why` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——3 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 爬升段的电阻环电压（对 DINA 的电导率体积分） | relative | 0.4 | measured_band | 实测 0.66..1.00 即最劣 −34 %，加一档余量。带说的是 0-D 的 Spitzer + 新经典电阻距 DINA 的电导率体积分有多远 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在该组算例书随件的 README（`$FYLITE_KERNEL/tests/data/FYDOC-CASE-02-dina/FYDOC-CASE-02-dina.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （判据）实测 0.66..1.00 即最劣 −34 %，加一档余量。带说的是 0-D 的 Spitzer + 新经典电阻距 DINA 的电导率体积分有多远
- （场景）★★★**`Vloop` 是同名不同量**：DINA 随件的参数说明写明它给的是**电导率的体积分**（纯电阻项），感应那一半另记（`D(PSI)res` · `Cejima`）。按字面比一个含 `Lp dIp/dt` 的环电压会得 6–8 倍——那是口径不符，不是模型差。这是场景的性质，任何在它上面立的判据都要先摆平这一条。
- （场景）★★**平顶段不可判**：平顶电流大半非感应（自举约 4 MA 加 NBI/EC 驱动）。把整个 I_p 当欧姆电流的模型在那一段实测比值 3.8，且**它就该很大**。
- （场景）★语料是 ITER IDM 件（Internal Use），在本机 `data/ITER Scenario/` 之下。

## 3. 量到的（图）

:::{figure} ../figures/B-09-band.svg
:alt: B-09 量到的数对它被判的判据
:width: 100%

**结果对标准**：每一条量到的数画在它被判的那条带上，竖线是判据本身，条越短余量越大。判定栏只说「成立」，这张图说**差多少**。
:::


## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 爬升段四个时刻 | 比值 1.00 / 0.73 / 0.66 / 0.78（t = 18 / 33 / 48 / 60 s），最劣偏低 34 %（带 40 %） |  | 成立 |  |
| ★★同名不同量，先摆平再比 | 首轮按字面比 `Vloop` 得 6–8 倍 |  | 不成立 | DINA 随件的参数说明写明其 `Vloop` 是**电导率的体积分**（电阻项），感应那一半另记（`D(PSI)res` · `Cejima`），而本仓 `loop_voltage_ohmic` 给的是 `Ip·Rp + Lp·dIp/dt`——在 0.2151 MA/s 上 `Lp dIp/dt` 约 2.6 V，正是那 6–8 倍的大头；**照字面比会把一次口径不符写成一次模型缺陷** |
| ★★温度时序被排除了，且方向相反 | 本仓爬升段 ⟨Te⟩ 2.15 keV 对 DINA 1.01 keV |  | 成立 | η ∝ Te^{-1.5}，更高的 Te 本该让电阻项**更小**。所以那 6–8 倍不可能由剖面时序解释——这一步是把「像是原因的东西」排掉，才轮到感应项 |
| ★★平顶段不判 | 实测比值 3.8 |  | 部分 | DINA 平顶电流大半非感应（自举约 4 MA 加 NBI/EC 驱动），本仓 0-D 把整个 I_p 当欧姆电流。门里有一条断言钉住「它就该很大」——免得哪天判据悄悄放宽把平顶收进来 |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| python/tests/test_dina_ramp.py::test_the_reference_really_covers_the_ramp | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_dina_ramp.py::test_the_resistive_loop_voltage_agrees_through_the_ramp | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_dina_ramp.py::test_the_flat_top_is_excluded_and_this_is_why | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $ITER_SCENARIO_ROOT/DINA…XA8GXS_v1_1 | — | restricted |  |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest python/tests/test_dina_ramp.py::test_the_reference_really_covers_the_ramp python/tests/test_dina_ramp.py::test_the_resistive_loop_voltage_agrees_through_the_ramp python/tests/test_dina_ramp.py::test_the_flat_top_is_excluded_and_this_is_why
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（B 对拍）的问题，不外推。
