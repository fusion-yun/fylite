---
title: "tr-pedestal-eped-feedback"
---

# 台基反馈收敛到 EPED1-NN 目标；内核的 EPED1-NN 对 EPEDNN.jl 逐位（8.9e-16）

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-pedestal-eped-feedback.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [台基、锯齿与 0D 存量](../domains/tr/pedestal.md)　|　记录正本：`records/tr-pedestal-eped-feedback.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：台基反馈收敛到 EPED1-NN 目标；内核的 EPED1-NN 对 EPEDNN.jl 逐位（8.9e-16）
- **参考**：EPEDNN.jl · 反馈的不动点：下一步的 EPED-NN 目标等于本步的边界
- **验的需求**：`FR-TR-009`
- **跑在内核**：`fylite_kernel@94ca1a29d6ed`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-19

## 问的是什么

**被量的**：EPED1-NN（权重 `models/epednn.npz`）在 1.5D 演化里每步定下一步的台基边界

**参考**：EPEDNN.jl（third_party/FUSE/EPEDNN.jl（EPED1NNmodel.bson））

> ★金标：同一个 NN 在 Julia 的原实现上三台装置（ITER / DIII-D / CFEDR）的输出，`tools/benchmark-epednn-gold.jl` 打印到全精度，内核测试逐字嵌入

**参考**：反馈的不动点：下一步的 EPED-NN 目标等于本步的边界

> ★滞后一步的反馈，末步相对步长就是「边界离目标还有多远」——收敛判据不需要外部参考

**口径与适用域**：

> EPED1-NN 金标：三组手选输入，均在 NN 训练箱内。反馈：evolve-iter-15ma（ITER 15 MA，31 点 ρ 网格，定 χ），`pedestal=True`、`alpha=False`，dt 0.2 s × 1000 步。★不声称：别的输运闭包下的收敛速率；EPED1-NN 本身对 EPED 全模型的精度（那是 NN 训练的事）。

## 判据与量到多少

:::{figure} ../figures/tr-pedestal-eped-feedback-headroom.svg
:alt: tr-pedestal-eped-feedback 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| EPED1-NN 的台基压强与宽度对 EPEDNN.jl（三台装置 × 9 个解支） | 4e-15 | reference_self_reported | ITER · DIII-D · CFEDR 三组输入，各 9 个压强 [MPa] + 9 个宽度（GH / G / H × H / meta / superH），逐点相对差最劣 8.88e-16（判据 4e-15） | **成立** |
| 台基反馈末步的相对步长（= 边界对 EPED-NN 目标的相对差） | 1e-06 | measured_band | evolve-iter-15ma，`pedestal` 开、α 关，dt 0.2 s × 1000 步（到 t = 21.1 s）：台基温度 3353.8 → 3356.8 → 3357.3 eV（首 / 中 / 末），相对步长中途 9.8e-07、末步 6.9e-08（判据 1e-6）；外推度 0.0。★α 开那一档（读数，不判）：台基温度 3399.8 → 6099.2 eV 一路上涨、末步 5.5e-04，外推度 0.53，轴上 T_e 69087 eV | **成立** |

**`EPED1-NN 的台基压强与宽度对 EPEDNN.jl（三台装置 × 9 个解支）`** — ★抄录原文「金标 <4e-15 档 NN 对拍」，逐字照搬。

**`台基反馈末步的相对步长（= 边界对 EPED-NN 目标的相对差）`** — ★抄录原文只说「收敛到 EPED-NN 目标」没给数；取 1e-6——比台基温度任何一种测量精度都细三个量级，而一个不收敛的反馈会停在 1e-4 以上（α 开那一档即是）。

**EPED1-NN 对 EPEDNN.jl —— **成立**：27 个数最劣 8.9e-16**

- ★金标是 EPEDNN.jl 在同一份权重上的输出（Float64 打印到全精度），内核读 `models/epednn.npz`——两边是同一个网络、两份实现，比的是前向计算与输入归一化，不是训练。
- ★三台装置取得差得远（ITER 15 MA / DIII-D 1.2 MA / CFEDR），是为了让输入归一化的每一维都被动到：一个只在一台装置上对的实现，常常是把某一维的缩放写反了而恰好没动到它。

**★台基反馈收敛到 EPED-NN 目标 —— **成立**：末步 6.9e-08，NN 输入始终在训练箱内**

- ★★**为什么关 α**：本算例是定 χ（`closure='constant'`），开 α 就热失控——α 加热随温度涨、输运不随之涨，没有不动点可到，台基也就跟着一路涨。那不是反馈的毛病，是算例没有自限的输运；判收敛得在一个有不动点的配置上判。
- ★★**α 开那一档恰好演示了本域开篇那条警告**：状态被推出 EPED1-NN 的训练箱（外推度 0.53），而 NN 不报错、照样给一个数。内核把外推度作为产出报出来（`ped_extrapolation`），门钉住它必须大于零——一个不报错的外推，至少要被量出来。
- ★滞后一步：第 n 步用第 n−1 步状态的 EPED 目标作边界，所以末步步长就是「边界离目标多远」，不是另一个代理量。

## 不可比的部分

- ★★**两格都成立**：NN 对拍到舍入，反馈收敛到目标 1e-7 量级。★判据二的带是本条定的（抄录没给数），来历写在判据里。
- ★**哪些量是喂进去的**：几何、Ip、B_T、加热、边界密度是输入；EPED1-NN 的输入（β_N、κ、δ、n_ped、Z_eff）由演化状态每步现取，台基高度是算出来的。
- ★此前 FR-TR-009 挂在 `tr-closure-15d-source-switches` 上，那条只验「台基开关进了装配」（改变了 8 项产出），不验收敛也不验 NN——本条补上判据原文的两半。

## 追溯

- 首次入册 2026-09-19　末次修订 2026-09-19　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-19 | Claude Opus 5 | 新立（用户「close FR-TR-*」）：FR-TR-009 判据原文两半——EPED1-NN 对 EPEDNN.jl 金标（8.9e-16 对 4e-15）与台基反馈收敛到 EPED-NN 目标（α 关，末步 6.9e-08）。 内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@94ca1a29d6ed`（库 `sha256:d7bb2708e0594700521df0703ab6345fcb232511e39b652ff061c0ecd69d4119`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/pedestal_eped_feedback.json`    `sha256:c83626c29a059ada24dd35516aec8d4df4a4a5400f00433896153dfb0ff1c85a`    台基反馈两档（α 关 / 开）的首 / 中 / 末台基温度、步长与外推度；tools/benchmark-evolve15.py 生成
- `tools/benchmark-evolve15.py`    `sha256:172210dc9d62dde435d752f29b0fcacd15c17f9ee5d80003c7d65222499038d4`    读数生成器（`PEDESTAL_MARCH`）
- `tools/benchmark-epednn-gold.jl`    `sha256:4ee23f9f654636e3ecf42db6612f0a633e22ead5aff89415b03a58a7b880cb72`    ★金标生成脚本（EPEDNN.jl 上跑）
- `models/epednn.npz`    `sha256:4b637f73b6943cfd888d6f6abc2134a3123f580d131bb071c3def5b0c660d796`    EPED1-NN 权重（内核读它）
- `third_party/FUSE/EPEDNN.jl/src/EPEDNN.jl`    `sha256:42b9f1d78f705c8cdd1e13066cf4dd864a8487738b18b0b3eeeb585703b17a31`    ★参考实现源码，参考类指针

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/pedestal.rs::tests::eped1nn_is_epednn_jl_on_three_machines` —— ★第一格：27 个数 < 4e-15
- `python/tests/test_benchmark_transport_gates.py::test_the_pedestal_feedback_settles_on_the_eped_target` —— ★第二格：公开入口重跑，逐位对上读数；α 关末步 < 1e-6 且无外推，α 开外推 > 0

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
