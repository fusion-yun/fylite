---
title: "eq-evolve-analytic-circuit-limits"
---

# 演化自由边界的解析极限：壳模按壁时间衰减、理想导体守住磁通、驱动逐步复现

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-evolve-analytic-circuit-limits.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [演化自由边界与涡流电路](../domains/eq/evolve.md)　|　记录正本：`records/eq-evolve-analytic-circuit-limits.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：演化自由边界的解析极限：壳模按壁时间衰减、理想导体守住磁通、驱动逐步复现
- **参考**：纯电路问题的解析解（壳模衰减 e^(-t/tau_w) · 理想导体磁通冻结）
- **验的需求**：`FR-EQ-004`
- **跑在内核**：`sha256:e0e1b16cf0004c12…`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-16

## 问的是什么

**被量的**：内核门 code/evolve_free_boundary，经 tools/benchmark-evolve-free-boundary.py；EAST 牌

**参考**：纯电路问题的解析解（壳模衰减 e^(-t/tau_w) · 理想导体磁通冻结）

> ★★**参考是解析解，不是另一个码**——所以这是验证，容差取舍入级而不是物理带。★这两条恒等式的妙处在于它们**不需要等离子体**：把等离子体拿掉，剩下的电路问题有闭式解，接线错了当场就现形。带等离子体之后没有解析解可依，那一层由别的记录（对拍类）担。

**口径与适用域**：

> EAST 装置牌（`dist/facts/device/east`）；演化经内核门 `code/evolve_free_boundary`。★两条恒等式跑在**纯电路极限**上（壳模衰减、理想导体），这一档没有等离子体；驱动复现与回路残差跑在带等离子体爬升的耦合步上。★时间轴与壁时间 tau_w 由装置牌的被动结构定：换一张牌，这些数会变，判据的形式不变。

## 判据与量到多少

:::{figure} ../figures/eq-evolve-analytic-circuit-limits-headroom.svg
:alt: eq-evolve-analytic-circuit-limits 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 壳模衰减对解析 e^(-t/tau_w) 的最劣相对偏差 | 1e-12 | machine_precision | 最劣相对偏差 8.44e-15（判据 1e-12，余量约 119 倍） | **成立** |
| 理想导体的磁通漂移 / 它被移动的量 | 1e-10 | machine_precision | 漂移/移动量 2.17e-13（判据 1e-10）· 回路残差 2.19e-13 | **成立** |
| 回路方程的最大残差（磁通冻结 / 电压驱动 / 电流驱动 三档） | 1e-09 | machine_precision | 冻结 2.19e-13 · 电压驱动 1.78e-13 · 电流驱动 5.93e-16（判据 1e-09） | **成立** |
| 电压驱动与电流驱动两条路复现同一段壳电流的最劣相对差 | 4.51e-09 | measured_band | 4.50014e-09 对判据 4.51e-09 | **成立** |
| 每一耦合步都是电流自身的一个已收敛平衡 | 2 | machine_precision | gs_state 起步之后恒为 [2.0]（冻结）· 电压 [2.0] · 电流 [2.0]；fb_held = 0 | **成立** |

**`壳模衰减对解析 e^(-t/tau_w) 的最劣相对偏差`** — ★带 1e-12 已是实测值（~1e-15）的千倍：恒等式在舍入以内成立，带只是防劣化的护栏。

**`理想导体的磁通漂移 / 它被移动的量`** — ★分母取「被移动的量」而不是磁通本身：等离子体不爬升时分子分母同为零，拿磁通作分母会让这条判据在什么都没发生时也显示完美。

**`回路方程的最大残差（磁通冻结 / 电压驱动 / 电流驱动 三档）`** — 解到自由边界解自身的容差 1e-9

**`电压驱动与电流驱动两条路复现同一段壳电流的最劣相对差`** — ★这是一条**交叉检验**：同一段演化用两种驱动方式走，应当到同一处。

**`每一耦合步都是电流自身的一个已收敛平衡`** — ★gs_state == 2 且 fb_held == 0：演化不是「解一次然后外推」，每步都真的解了。这一条没有数值容差可言，但它守的东西比任何一条带都重要。

**壳模衰减对解析解**

- ★量级是 1e-15：这已是双精度舍入，不是「算得准」，是**恒等式成立**。

**★驱动复现 —— 成立，但**余量只剩 0.2 %****

- ★★**这是本条里唯一贴着带跑的一档**。带是按实测值三位有效数字向上取整定的（登记册的定带规则），所以「贴着」有一半是定带方式造成的——但后果是真的：**任何一点漂移都会把它顶出去**。
- ★记在这里而不是等它某天变红：一条余量 0.2 % 的判据，与一条余量千倍的判据，在表上看起来都是绿的，但它们说的不是一件事。

## 不可比的部分

- ★★**本条只覆盖解析可判的那一层**。FR-EQ-004 的完整内容还包括带等离子体的轨迹对不对，而那一层**没有解析解**——只能对着另一个码的一次运行量，那属于对拍，不属于本条。eq-evolve 目前**没有**这样一条对拍记录，是本域的记名缺口。
- ★**哪些量是喂进去的**：装置牌的被动结构与电阻、驱动波形、等离子体电流的爬升曲线，全是输入。算出来的是各回路电流与它们产生的磁通演化。
- ★驱动复现那一档余量 0.2 %，见其 finding 的 caveat——绿，但不是宽裕的绿。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-16　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-evolve 的第一条记录，五条判据全过；驱动复现余量仅 0.2 % 记为 finding 的 caveat |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:e0e1b16cf0004c128eaaaff81c3d9c36d8a971ce024b2b411c6d7ea5be165ced`　—— 须设 `$FYLITE_KERNEL_LIB` 指向带该门的构建，`$FYLITE_DEVICE_DIR` 指向 EAST 牌

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/evolve_free_boundary_metrics.json`    `sha256:b6dd33c95c7e41eee18ea665b2a0b336c132b6219e158ce88bc2ab701c0767a8`    本条的派生指标读数（当日实跑）
- `FYDOC-CASE-23-east-137985-efit-east/corpus/benchmark/evolve_free_boundary_east137985.json`    `sha256:3ed068ab61d9d59ec67ad727513015301f471fa440e8be9656d5584e4d44fe1a`    ★原始读数是**实验类**，留在 fydoc 算例库里，公开册只记指针 + sha256（设 `$FYDOC_ORACLE` 指过去）

**守它的门**：

- `python/tests/test_benchmark_evolve_free_boundary.py::test_v21_a_shell_mode_decays_on_the_wall_time`
- `python/tests/test_benchmark_evolve_free_boundary.py::test_v21_a_perfect_conductor_keeps_its_flux_while_the_plasma_ramps`
- `python/tests/test_benchmark_evolve_free_boundary.py::test_v21_current_drive_reproduces_the_voltage_march`
- `python/tests/test_benchmark_evolve_free_boundary.py::test_the_readings_are_the_registered_ones`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
