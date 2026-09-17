---
title: "eq-inverse-iter-reference-separatrix"
---

# ITER 参考分离面上的静态逆解：设计自身的闭合，以及它买不起的那部分形状

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-inverse-iter-reference-separatrix.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [静态逆解：形状到线圈电流](../domains/eq/inverse.md)　|　记录正本：`records/eq-inverse-iter-reference-separatrix.jsonld`*

## 摘要

- **类**：验证　**判决**：**未判（读数）**
- **量的是**：ITER 参考分离面上的静态逆解：设计自身的闭合，以及它买不起的那部分形状
- **参考**：ITER 参考分离面（装置牌上的数字化曲线）
- **验的需求**：`FR-EQ-005`
- **跑在内核**：`sha256:ac8c0f5cdc4e6019…`（新鲜度 **current**）
- **记录版本**：1.2　**评审**：草稿　**日期**：2026-09-17

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-17 仍记名保留（用户裁定「保留负面结果」）：达成 kappa 1.7941 比目标低 2.98 %、delta_lower 低 10.21 %，判据 1 %——**这一条是真结论**，不是判法问题：把 kappa 顶上去的设置（enp 0.5）要 37.5 MA·t 且永不收敛。所需 30.6 MA·t 仍无额定可比（牌上缺 pf_active/supply）。★收敛那一条已于 1.1 版改为读数——原判 fail 是我自立的标准，不是缺陷。
:::

## 问的是什么

**被量的**：内核门 code/inverse_shape，经 tools/benchmark-equilibrium.py inverse-shape-iter；129x129 网格，16 轮退火

**参考**：ITER 参考分离面（装置牌上的数字化曲线）（dist/facts/device/iter.jsonld）

> ★★**这是被要求的目标曲线，不是一份独立的平衡答案。** 于是本条量的是**闭合**（要来的线圈电流，真产生出它声称的那条分离面吗），不是**正确性**（这条分离面本身对不对）。两者差别很大，别读混。★读数自己写着：none (no ITER equilibrium is reachable: TEQ / TOSCA are `$ITER_SCENARIO_ROOT` pointers, FreeGSNKE has no ITER machine)

**口径与适用域**：

> ITER 装置牌 dist/facts/device/iter.jsonld；限制器为注入的 METIS 壁（fydoc facts/device/iter/abox/providers/wall/metis.jsonld (injected as the limiter unit `metis_wall`)）。Ip = 1.5e+07 A · beta0 = 0.6 · emp = 2.0 · nu = 3.0 · n_points = 24 · 网格 129x129 · 退火 16 轮 · 位置控制 c4。★形状量（kappa / delta / a / r0）按本仓的形状拟合定义，与 Miller 参数化的同名量不必逐一相等；比较双方都取本记录的这一套定义。★emp = 2 是**最后一个仍收敛的设置**：emp = 3 的 shape_error 略好（0.0269），但耗尽 600 轮预算停在残差 0.019。

## 判据与量到多少

:::{figure} ../figures/eq-inverse-iter-reference-separatrix-headroom.svg
:alt: eq-inverse-iter-reference-separatrix 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 设计分离面对目标曲线的逐点距离（中位数） | 15.5 | measured_band | 中位 15.37 mm · p95 69.81 mm · max 123.2 mm（181 点） | **成立** |
| 线圈电流峰值（是否落在机器能给的范围内） | 30.7 | measured_band | 峰值 30.61 MA·t · limits_held = False | **未判（读数）** |
| 逆解的收敛状态（读数，不判） | 1 | measured_band | converged = 0（settled = 1，残差 0.000965，78 次迭代 / 16 轮） | **未判（读数）** |
| 达成的形状对目标形状（kappa 与 delta_lower） | 0.01 | measured_band | kappa 1.7941 对目标 1.8492（低 2.98 %）· delta_lower 0.4878 对目标 0.5432（低 10.21 %） | **不成立** |
| 目标曲线自身的缺陷（记在册里，不在脚注里） | — | — | X 点处开口 322.5 mm，需从角点 [5.15, -3.4] 闭合；目标点 248 个，分段中位 66.67 mm | **未判（读数）** |

**`设计分离面对目标曲线的逐点距离（中位数）`** — 单位 mm；防劣化带

**`线圈电流峰值（是否落在机器能给的范围内）`** — ★★单位 MA·t。**这一条量的不是精度，是可实现性。** 带画在实测上只是防劣化——真正的判据（供电额定）**牌上没有**，所以这一条判不了。

**`逆解的收敛状态（读数，不判）`** — ★★**1.1 版撤回了这条判据的裁断力**，理由是它当初没有依据：门自己的停机规则是 `settled`，工具侧实测「退火在 16 轮饱和」（加预算不改善），而**没有任何需求写着逆解必须报 `converged = 1`**。1.0 版据此判 fail，是拿一条我自立的标准去判。★同一现象在 EAST 那条（`eq-inverse-freegsnke-east137985`）里被记作读数——**同一件事两种判决，说明错的是判法，不是数**。两条现已一致。★这不是放宽容差保过关：容差一格没动，撤的是一条无依据的**裁断**。

**`达成的形状对目标形状（kappa 与 delta_lower）`** — ★1 % 是对一条**被要求的**形状的合理期待：它是输入，不是待测量。

**分离面对目标曲线的闭合**

- ★中位 15 mm 而 max 123 mm：偏差**不是均匀分布**的，尾部集中在 X 点角附近——那正是目标曲线自己有缺陷的地方（见下一条）。只报中位数会把这件事藏起来。

**★线圈电流 —— **未判**：没有上限可比**

- ★★**退火是无界的**：pf_active carries no supply rating on this card (ITER-FEAT 2000's dev:currentMax belongs to a different coil set — 12 of 12 circles differ from base), so the anneal runs unbounded
- ★于是「设计成功了」这句话缺一个前提：没有人知道这组电流这台机器给不给得出。**一个买得起与否未知的设计，不能记成成立。**

**收敛状态（读数，不判）—— 且这是**跨算例的共性****

- ★★**1.0 版判 fail 是错的判法，1.1 版改正**：门自己的停机规则是 `settled`，工具侧实测「退火在 16 轮饱和」，而没有任何需求要求 `converged = 1`。**拿一条自立的标准去判，判出来的不是缺陷，是标准。**
- ★★**同一现象在 EAST 那条也在**（`eq-inverse-freegsnke-east137985`，残差 1.67e-03）——两个独立算例、两台机器。**跨算例的共性值得先查，但它是一个待解释的现象，不是一条已证的缺陷。**
- ★残差 9.65e-04 本身很小；「不再动」与「足够小」是两件事，这一点仍然成立——所以记读数，不记成立。

**★达成的形状 —— **不成立**：买不起的那部分**

- ★★**这是本条最有信息量的一行**：在每一组还能让电流保持物理的设置下，kappa 都比目标低约 3 %，delta_lower 低约 10 %。
- ★已实测过的反例：剖面指数 enp = 0.5 能把 kappa 顶到 1.834（各变体里最接近目标），代价是要 37.5 MA·t 且**永不收敛**——给它四倍轮数，残差反而从 0.12 升到 0.32。所以那不是预算不够，是那个设置本身不稳。
- ★记 fail 而不是放宽到 4 %：**形状差多少是结论，不是待调的容差**。

**目标曲线自身的缺陷（记在册里，不在脚注里）**

- ★牌上那条数字化参考曲线在 X 点是**开口**的，本次运行把它从角点闭合。闭合方式会改变那一带的逐点距离——上面 max 123 mm 落在这一带，两件事要一起读。

## 不可比的部分

- ★★**本条没有外部参考。** ITER 的 TEQ / TOSCA 平衡是指向未设 `$ITER_SCENARIO_ROOT` 的指针，FreeGSNKE 不带 ITER 机器——所以这里不存在「另一个码的答案」可比。量的是设计自身的闭合，这一点决定了本条能声称什么、不能声称什么。
- ★**哪些量是喂进去的**：目标分离面、Ip、beta0、剖面指数、壁，全是**输入**。算出来的只有线圈电流与它们产生的那条分离面。把目标形状的「接近」当成物理正确性的证据，是这一域最容易犯的夸大。
- ★**整体判 inconclusive 而不是 fail 或 pass**：闭合带过了（criterion/1），收敛与形状两条不成立（criterion/3、4），电流一条**判不了**（criterion/2，牌上没有额定）。有一条判不了，整体就不该给一个干脆的判决。
- ★2026-09-16 用户裁定「不改内核，保留负面结果」：以上三条负面结论原样留册，容差不放宽。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-17　版本 1.2　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-inverse 的第一条记录，数值取自盘上读数；整体判 inconclusive，三条负面结论按用户裁定保留 |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | ★撤回「收敛」那条判据的裁断力——它当初没有依据，且与 EAST 那条记录对同一现象的判法不一致；改为读数，两条一致。★形状那条**仍判 fail**：它是真结论，不动。 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:ac8c0f5cdc4e601951da0b1ad26a58616571913de15e1bd089065e8a94dc0e7a`　—— 须设 `$FYLITE_KERNEL_LIB` 指向带该门的构建，并设 `$FYLITE_DEVICE_DIR` 指向 ITER 牌所在目录

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/inverse_shape_iter.json`    `sha256:16a2a565a3c22574d7e63761fb697f537f003a5103f14c4aec11449cd6c24570`    读数：目标曲线与其缺陷、设置、设计结果、逐点距离、十二路线圈电流。★由 `tools/benchmark-equilibrium.py inverse-shape-iter --out docs/benchmark/readings` 产出。

**守它的门**：

- `python/tests/test_benchmark_inverse_shape_iter.py::test_v22_the_designed_separatrix_stays_in_the_band`
- `python/tests/test_benchmark_inverse_shape_iter.py::test_v22_the_design_does_not_buy_shape_with_current_the_machine_lacks`
- `python/tests/test_benchmark_inverse_shape_iter.py::test_v22_the_target_curve_is_recorded_with_its_defects`
- `python/tests/test_benchmark_inverse_shape_iter.py::test_v22_the_design_reproduces_its_recorded_readings`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
