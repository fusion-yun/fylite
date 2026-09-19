---
title: "源项：加热与电流驱动"
---

# 源项：加热与电流驱动

*输运 (Transport) · 本域答：NBI · EC · LH · IC 的功率落在哪、驱动多少电流——每一族的功率账闭不闭合，沉积与驱动效率对着另一个码或测量差多少。*

输运方程右边的源，大半来自外部加热与电流驱动：中性束（NBI）、电子回旋波（EC）、低杂波（LH）、
离子回旋波（IC）。每一族回答两件事——**功率落在哪一层磁面**、**驱动多少非感应电流**——而这两件
都进了剖面，剖面又回头改沉积。这一章 2026-09-19 从「闭包插件面」分出来单立：此前册里判
`FR-TR-004` 的两条记录都只证**接线**（能量账、沉积积分），物理本身一条对拍也没有登记。

★**这一域的判据分两路，而且不能互相顶替。**

一路是**功率账**：注入的功率等于被吸收的、穿透出去的、首轨损失的之和；沉积剖面对体积的积分等于
被吸收的那一份。这是自证，不需要参考码，所以可以要到机器精度——上游 `FYTOK-SRS-04` 的源族表
写的就是「逐项闭合为可测不变量」，`NR-TR-001` 写的是「源沉积积分必须闭合到注入额定值」。
★但它**只抓账错**，抓不住物理错：一个把所有功率都放在轴上的模型，账一样闭合。

另一路是**对照**：沉积位置与驱动效率对着另一个独立实现的码或测量。这一路容差宽（两套独立实现，
差百分之几是常态），而且**参考本身不是真值**——本域的 METIS 对照尤其如此，METIS 自己用的就是拟合式。
所以这一路记带与散布，读法是「两家描述的是不是同一个等离子体」，不是「谁对」。

各族现在站在哪里：

- **EC**——最硬的一族。`code/rf_ray` 对 TORAY-GA 在 CFEDR 20 MA 设计点上**自己的输入与输出都在盘上**的
  那一次运行（fydoc CASE-21）：射线在同一磁面上差 0.4 mm、偏振支由数据读出、N∥ 到 1.5e-4、驱动电流
  每瓦 1.046 倍。伴随 ECCD 另对 METIS 认证库 30 行（比值 0.03–0.64，中位 0.35——比 METIS 的 Giruzzi 拟合
  低，但对数相关 0.976，趋势同）。
- **IC**——对 METIS 的七格（共振层、少数离子四料、电子/快离子分配、剖面形状、闭合）加 FWCD 对测量。
  ★**IC 没有 `code/` 门**：内核有这一族，公开仓的门够不着，所以它的判据全在内核仓的 Rust 单测里，
  本仓 CI 跑不到——照实记在那条记录的缺口里。
- **NBI、LH**——只有功率账。★**沉积与驱动效率没有登记的外部参照**：本机没有 RABBIT / NUBEAM 之类的
  束码输出，LH 也没有另一个码在同一算例上的答案（METIS 认证库里带 LH 的行被故意排除，因为 METIS 在那些行上
  乘了一个 LH/EC 协同因子，本码不建模它）。这是本域**最大的空白**，不是排版。

★参考侧的出处：TORAY 那份冻结件（`cfedr_toray_20ma.txt`）标着 `release: internal`、取自受限语料，
只存在于私有内核仓；本册的读数只记比较量（偏差、比值、TORAY 的几个标量），不转存它的剖面与射线。

<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->

### 判据（抄自 `FYTOK-SRS-04` v0.11）

:::{note} 这一节是**抄录**，不是引用
上游 `FYTOK-SRS-04` 标着 `distribution: internal`——本册的读者打不开它。一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。

抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
:::

**`FR-TR-004` · 源项插件族与 exp / imp 契约** — MUST · 验证方法：检查 + 测试

> （FR-TR-003/004）插件按名分派；统一前端共享；沉积积分闭合

### 本域的记录

| 记录 | 类 | 判决 | 参考 | 版本 | 评审 | 正本 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`tr-sources-ec-toray-cfedr`](../../reports/tr-sources-ec-toray-cfedr.md) | 对拍 | 成立 | TORAY-GA | 1.0 | 草稿 | [jsonld](../../records/tr-sources-ec-toray-cfedr.jsonld) |
| [`tr-sources-eccd-metis`](../../reports/tr-sources-eccd-metis.md) | 对拍 | 成立 | METIS | 1.0 | 草稿 | [jsonld](../../records/tr-sources-eccd-metis.jsonld) |
| [`tr-sources-icrh-metis`](../../reports/tr-sources-icrh-metis.md) | 对拍 | 成立 | METIS · FWCD 测量（JFT-2M · DIII-D · Tore-Supra，METIS fitetafwcd.m 所回归的表） | 1.0 | 草稿 | [jsonld](../../records/tr-sources-icrh-metis.jsonld) |
| [`tr-sources-power-closure`](../../reports/tr-sources-power-closure.md) | 验证 | 成立 | 抄录的判据：「P_inj = P_abs + P_shine + P_orbit 逐项闭合为可测不变量」（源族表）·「源沉积积分必须闭合到注入额定值」（NR-TR-001） | 1.0 | 草稿 | [jsonld](../../records/tr-sources-power-closure.jsonld) |

### 覆盖它的记录在别的域

★这几条本域需求由**别处**的记录答了——同一份证据同时回答两条需求时，它只能挂在一个域下。上面的记录表列的是「属于本域的记录」，所以这里点名说清它在哪。

| 需求 | 覆盖它的记录 | 它属于哪一域 |
| :--- | :--- | :--- |
| `FR-TR-004` | [`tr-closure-15d-source-switches`](../../reports/tr-closure-15d-source-switches.md) | tr-closure |
| `FR-TR-004` | [`tr-closure-dt-burn-astra`](../../reports/tr-closure-dt-burn-astra.md) | tr-closure |

### 缺口

本域没有 MUST 级空缺。

<!-- END GENERATED -->
