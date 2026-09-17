---
title: "eq-forward-chease-solovev"
---

# 同一道 Solov'ev 定边界题：fylite 129^2 对 CHEASE NS=NT=80

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-forward-chease-solovev.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [前向自由边界与 Green 响应核](../domains/eq/forward.md)　|　记录正本：`records/eq-forward-chease-solovev.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：同一道 Solov'ev 定边界题：fylite 129^2 对 CHEASE NS=NT=80
- **参考**：CHEASE
- **验的需求**：`FR-EQ-001`
- **跑在内核**：`sha256:340bef300ef0fad4…`（新鲜度 **current**）
- **记录版本**：1.3　**评审**：草稿　**日期**：2026-09-16

## 问的是什么

**被量的**：内核门 code/fixed_boundary，129x129 网格

**参考**：CHEASE（本机构建，NS = NT = 80）

> ★CHEASE 解的是同一道方程，按「同一函数的另一实现」本可归**验证**；这里归**对拍**，理由是容差取的是**实测带**而不是机器精度——两边都带离散误差，谁都不是真值。分类由「参考是什么 + 容差怎么取」决定，不由做得多认真决定。

**口径与适用域**：

> Solov'ev 定边界解析平衡：R0 = 1.8 m · B0 = 2.0 T · e2 = 1.07544 · Ip(闭式) = 3451548 A · q0(闭式) = 0.8348157；边界轮廓 720 点，psi 口径「g-file per radian, axis minimum」（即每弧度、以轴为极小）。比较落在轮廓**内**的 18805 个网格点上（「深内点」）。★径向标签为 psi_N（归一极向磁通），不是 rho；容差与它绑定。★本条是**定边界**：FR-EQ-001 判据里「自由边界 Ip 约束收敛 rel 1e-6」那一档不在本条，由 eq-forward 的另一条记录覆盖（现缺，见本域缺口栏）。 CHEASE 侧为 NS = NT = 80，输出经 EQDSK_COCOS_02.OUT 读回，★两侧在同一 psi 口径与同一 COCOS 下比较（口径不对齐时比出来的是约定差，不是实现差）。

## 判据与量到多少

:::{figure} ../figures/eq-forward-chease-solovev-headroom.svg
:alt: eq-forward-chease-solovev 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 深内点 psi_N 两码之差（RMS） | 1.12e-05 | measured_band | RMS 1.119e-05 · max 0.0001122 | **成立** |
| q 剖面 psi_N∈[0.1,0.9] 的相对差（RMS） | 0.000231 | measured_band | q[0.1,0.9] RMS 0.0002303 · max 0.0005635 · q95 -3.549e-05 | **成立** |
| CHEASE 自身对闭式解的偏差（本条的旁证锚） | 3.91e-06 | measured_band | psi_N RMS 3.907e-06 · 轴 1.75e-06 mm · Ip 9.36e-10 · q0 3.56e-06 | **成立** |

**`CHEASE 自身对闭式解的偏差（本条的旁证锚）`** — ★没有这一锚，两码之差说明不了任何事：差可能全是对方的。

**CHEASE 对闭式解——这条对拍之所以可读的前提**

- ★★**这一条是本记录里最有用的一行**：CHEASE 的 q0 对闭式解只差 3.56e-06，而 fylite 129^2 差 -1.97e-05。于是两码 q0 之差 -2.33e-05 **归属明确**——是 fylite 的收敛，不是基准或口径的问题。没有这一锚，同一个数只能读成「两码有分歧」。

## 不可比的部分

- ★**对拍不是验证**：两套实现吻合到 1e-5 不证明谁对——两个错误也能互相抵消。本条的价值全靠 criterion/3 那一锚（CHEASE 自己对闭式解的偏差）撑着；主判据在 eq-forward-solovev-fixed-boundary。
- ★**CHEASE 的 NS/NT 是它的收敛旋钮**：换一档 NS，这里每个数都会变。所以带是「在 NS=NT=80 这一档上实测的」，不是 CHEASE 的固有精度。
- ★CHEASE 侧的输入 EXPEQ 由本仓写出，p' 与 TT' 的符号与归一是**在本次运行里量出来的**，不是假定的——符号错时 CHEASE 不收敛，这一点本身是一条弱自证。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-17　版本 1.3　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：与验证记录同源，单列以免把对拍与验证混在一条里 |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:340bef300ef0fad494ef3c248b75a08dc464c6a3d145f8f0df2b8cf2208736c8`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/solovev_fixed_boundary.json`    `sha256:32c17f7511b7745a7b32604cb8ed1042f7f9c3487c1093c6be48fb35b97e752d`    与验证记录同一份读数、同一次运行——两条记录因此逐位可互校。

**守它的门**：

- `python/tests/test_benchmark_fixed_boundary.py::test_v19_chease_on_the_same_contour` —— 守 CHEASE 侧对闭式解的带；CHEASE 未构建时按名 skip

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
