---
title: "eq-reconstruct-mse-shelved"
---

# MSE 全形响应行与内部约束行几何门控：**用户裁定搁置**——内核里没有 MSE，被门控的东西还不存在

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-reconstruct-mse-shelved.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [测量重构与约束阶梯](../domains/eq/reconstruct.md)　|　记录正本：`records/eq-reconstruct-mse-shelved.jsonld`*

## 摘要

- **类**：验证　**判决**：**未评估**
- **量的是**：MSE 全形响应行与内部约束行几何门控：**用户裁定搁置**——内核里没有 MSE，被门控的东西还不存在
- **参考**：FYTOK-SRS 判据（FR-EQ-007..009 共用一行，抄在 domains/eq/reconstruct.md）
- **验的需求**：`FR-EQ-007` · `FR-EQ-009`
- **跑在内核**：`fylite_kernel@915ed1249591`（新鲜度 **current**）
- **记录版本**：1.4　**评审**：草稿　**日期**：2026-09-19

:::{warning} 这是一条**已裁定保留**的缺口

用户 2026-09-17 裁定「搁置 MSE」：`FR-EQ-007` · `FR-EQ-009` 不实现，直到用户重启。前提（内核无 MSE）由门钉住。
:::

## 问的是什么

**被量的**：MSE 响应行不在其中

**参考**：FYTOK-SRS 判据（FR-EQ-007..009 共用一行，抄在 domains/eq/reconstruct.md）

> A₃ 乘 B_R；中平面 MSE 点的 B_r 列上下对称恒零，测点须偏中平面方可辨

**口径与适用域**：

> fylite 内核与重建门（2026-09-19）。

## 判据与量到多少

:::{figure} ../figures/eq-reconstruct-mse-shelved-headroom.svg
:alt: eq-reconstruct-mse-shelved 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| MSE 全形响应行与几何门控（FR-EQ-007 · 009） | — | reference_self_reported | 未评。内核与 Python 侧 MSE 零实现；判据不是「门控没做对」，是被门控的东西还不存在，要从响应行写起。 | **未评估** |
| 搁置的前提：内核里没有 MSE 响应行 | — | reference_self_reported | `fylite_kernel/rust/fylite/src/*.rs` 全文搜 `\bmse\b` · `motional` · `pitch_angle`：零命中 | **成立** |

**★MSE —— **未评**：用户 2026-09-17 裁定搁置**

- ★★**「包内零标定数值」是必然，不只是政策**：`AAnGAM(n=[1:7])` 是逐机器的几何修正系数，由 EFIT 自己在 input mode 5 跑出来写进 k-file（fydoc `third_party/efit-annex.md` L918）——包内推不出来，只能由调用方给。
- ★`docs/guide/constraints.md` 说「`kfile.mse_namelist()` 已处理此事」，全仓搜不到这个函数——文档超前于代码。

**搁置的前提成立：内核源码里没有 MSE / motional / pitch_angle**

- ★这道门守的是裁定的**前提**：一旦有人往内核加了 MSE，它就红——那时这条裁定该重看，而不是被悄悄绕过。

## 不可比的部分

- ★★**这是一条裁定记录，不是一次测量**：`FR-EQ-007` / `009` 经用户 2026-09-17 裁定搁置。入册是为了让它在覆盖表上显示为「已裁定」而不是空行——空行的意思是「没人管」，这两条是「决定了先不做」。
- ★重启时先读 A₃ ↔ B_R 那条系数约定与 AAnGAM 由 EFIT 生成这两件事（见 finding）。

## 追溯

- 首次入册 2026-09-19　末次修订 2026-09-19　版本 1.4　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-19 | Claude Opus 5 (1M context) | 首次入册：把用户「搁置 MSE」的裁定落成记录（判 unevaluated，open_defect 写明谁、何时、为什么），并以一道门钉住它的前提——内核里没有 MSE 响应行。 |
| 1.1 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.2 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.3 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.4 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@915ed1249591`（库 `sha256:02975458f9f5425ca8c01674bb6070f754ac752edce0e143aec07fccee0ee7c2`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**守它的门**：

- `python/tests/test_benchmark_mse_shelved.py::test_the_kernel_still_has_no_mse_response_row` —— 搁置的前提

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
