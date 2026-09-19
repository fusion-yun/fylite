---
title: "eq-forward-free-boundary-convergence"
---

# 自由边界正解：缺省路径 Ip 约束收敛（残差 < 1e-9，Ip 到 2e-15），收敛设置逐项回显——EAST #137985 三个纯磁测切片

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-forward-free-boundary-convergence.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [前向自由边界与 Green 响应核](../domains/eq/forward.md)　|　记录正本：`records/eq-forward-free-boundary-convergence.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：自由边界正解：缺省路径 Ip 约束收敛（残差 < 1e-9，Ip 到 2e-15），收敛设置逐项回显——EAST #137985 三个纯磁测切片
- **参考**：抄录的判据：「自由边界 Ip 约束收敛 rel 1e-6；收敛参数显式回显」
- **验的需求**：`FR-EQ-001`
- **跑在内核**：`fylite_kernel@915ed1249591`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-19

## 问的是什么

**被量的**：KEFIT 的线圈电流、p′/FF′ 表与 Ip

**参考**：抄录的判据：「自由边界 Ip 约束收敛 rel 1e-6；收敛参数显式回显」

> ★判据本身不要外部代码：收敛与 Ip 约束是解的自证，回显是门的输出。

**口径与适用域**：

> EAST #137985 KEFIT 的三个纯磁测切片（4.041 / 4.944 / 5.976 s），线圈电流取 a 文件 CCBRSP、p′/FF′ 取 g 文件；129² 网格。★判据的另一半（定边界 Solov'ev 深内点 < 5e-4）由 `eq-forward-solovev-fixed-boundary` 判。

## 判据与量到多少

:::{figure} ../figures/eq-forward-free-boundary-convergence-headroom.svg
:alt: eq-forward-free-boundary-convergence 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| Ip 对目标的相对差 | 1e-06 | reference_self_reported | t4041_mag 1.1e-15 · t4944_mag 2.0e-15 · t5976_mag -1.1e-16 | **成立** |
| 收敛：converged = 1 且残差 ≤ 回显的 tol | — | reference_self_reported | t4041_mag 收敛 753 次 残差 9.87e-10 虚拟对 -50 A · t4944_mag 收敛 785 次 残差 9.92e-10 虚拟对 -44 A · t5976_mag 收敛 764 次 残差 9.54e-10 虚拟对 -33 A。★t5976_primary（POINT 约束剖面）：边规则 3000 次残差 6.2e-03、节点规则也不收敛 | **成立** |
| 收敛参数回显：tol · max_iter · 迭代次数 · 残差 · 边界规则 · 松弛 · 反馈增益 · Ip 目标 | — | reference_self_reported | 每片的事实里都带 edge_fraction, fb_gain, ip_target, max_iter, relax, tol，另有 iterations · residual · converged；notes 写明「boundary rule: edge (the boundary cells carry their fraction of the current)」 | **成立** |

**`Ip 对目标的相对差`** — ★抄录原文 rel 1e-6，逐字。

**Ip：三片最劣 2.0e-15**

- ★Ip 由每轮的 j_c 归一化施加（p′ 与 FF′ 同乘一个数），所以它在每一轮都精确——判据要的「约束收敛」其实是第二格：场收敛了，约束始终在。

**收敛：三片残差 ≤ 1e-9，753–785 次**

- ★★判的是**缺省路径**：2026-09-19 用户裁定边规则为缺省（节点规则在这几片上从不收敛——`settled` 于 1.3e-3–3.7e-3，且靠 10–14 kA 的虚构竖直电流）。
- ★★t5976_primary 不收敛，照记而不藏：同一组 KEFIT 线圈电流配上 POINT 约束的高 li 剖面（li 1.37，纯磁测 1.09），正问题要虚拟对给 80–240 kA（Ip 的 20–60 %）才立得住——在 relax 0.1 或反馈增益加倍下都不收敛；KEFIT 自己那一片也只松收敛（err 9.3e-4）。这组输入在线圈能撑住的范围内没有近处的平衡，不是求解器的缺陷；B-14 也一直把这一片记在带外。

**回显：八项齐全、规则按名**

- ★2026-09-19 补上的是 edge_fraction · relax · fb_gain · ip_target 四项（此前只回显 tol 与 max_iter，规则只在 notes 里）。

## 不可比的部分

- ★本条补的是 FR-EQ-001 抄录判据的自由边界那一半——此前册里没有一条记录判它。

## 追溯

- 首次入册 2026-09-19　末次修订 2026-09-19　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-19 | Claude Opus 5 | 新立（/goal「close FR-EQ-001/005」）：FR-EQ-001 抄录判据的自由边界一半——缺省路径（边规则，用户裁定）Ip 约束收敛、收敛设置回显。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@915ed1249591`（库 `sha256:02975458f9f5425ca8c01674bb6070f754ac752edce0e143aec07fccee0ee7c2`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/forward_convergence_east137985.json`    `sha256:b85776186d192a9eca810fea56d0ace56b245392f7f402b9a46b90bdfdb4051c`    逐片收敛、Ip、回显（tools/benchmark-forward-convergence.py 生成）
- `tools/benchmark-forward-convergence.py`    `sha256:9a260a32ea9ed1623ca13858f27ffedc7b77bf18969a86fab653c6b3c1e6ae0f`    读数生成器
- `FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_raw_east137985.tar.gz`    `sha256:001d33a06fdc39da3cf15a0240484f182cf0c85e832bf7802894e8c63aca0258`    KEFIT 原件（输入：电流与剖面），指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_equilibrium.py::test_fr_eq_001_the_default_forward_solve_converges_on_ip_and_echoes_its_setting` —— ★三格：公开入口重跑，逐位对上读数
- `$FYLITE_KERNEL/rust/fylite/src/equilibrium.rs::free_boundary_tests::the_edge_rule_converges_and_moves_continuously` —— 内核：边规则收敛、Ip 到 1e-12

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
