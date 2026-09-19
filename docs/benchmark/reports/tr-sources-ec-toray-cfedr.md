---
title: "tr-sources-ec-toray-cfedr"
---

# EC 对 TORAY-GA（CFEDR 20 MA）：偏振支由数据读出，射线同面差 0.6 mm、N∥ 差 1.5e-04，沉积峰差 0.012（不到一壳），驱动电流每瓦 1.046 倍

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-sources-ec-toray-cfedr.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [源项：加热与电流驱动](../domains/tr/sources.md)　|　记录正本：`records/tr-sources-ec-toray-cfedr.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：EC 对 TORAY-GA（CFEDR 20 MA）：偏振支由数据读出，射线同面差 0.6 mm、N∥ 差 1.5e-04，沉积峰差 0.012（不到一壳），驱动电流每瓦 1.046 倍
- **参考**：TORAY-GA
- **验的需求**：`FR-TR-004`
- **跑在内核**：`fylite_kernel@b27d7145ab3e`（新鲜度 **current**）
- **记录版本**：1.1　**评审**：草稿　**日期**：2026-09-19

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-19 ★参考是内部件、只在内核仓：本条的门要 $FYLITE_KERNEL，没有内核检出的 CI 跳过它。
:::

## 问的是什么

**被量的**：TORAY 那一次运行的平衡（psiin，SI）、剖面（echin）与发射几何，原样喂进树门

**参考**：TORAY-GA（CFEDR H-mode 20 MA 设计点（fydoc CASE-21，OMFIT 树 CFEDR_260114）：输入 echin · psiin · toray.in 与输出 toray_*.nc 四件都在盘上）

> ★**净室**：读的是 TORAY 的数据文件，从未读它的源码。★冻结件 `cfedr_toray_20ma.txt`（内核仓 `rust/tools/gen_cfedr_toray_reference.py` 生成）标 `release: internal`、取自受限语料，只在私有内核仓；本记录只记比较量。

**口径与适用域**：

> CFEDR H-mode 20 MA 设计点，TORAY 那一束（频率、功率、发射位置与两角取自其 echin / toray.in，角度约定由发射点到射线首点的弦**推出**并由内核测试校验）；平衡取 psiin（SI），剖面取 echin 的 201 点。★只有这一束、这一个点。

## 判据与量到多少

:::{figure} ../figures/tr-sources-ec-toray-cfedr-headroom.svg
:alt: tr-sources-ec-toray-cfedr 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 偏振支：\|N\| 在两射线同过的五个磁面上对 TORAY 的最劣相对差（所认之支 < 1 %，另一支 > 5 %） | 0.01 | measured_band | 五个磁面 psi_N 0.90 / 0.70 / 0.50 / 0.35 / 0.25：O 支最劣 3.41e-05，X 支最劣 0.239 → TORAY 发的是本码所称的 O 支 | **成立** |
| 射线：同一 psi_N 面上的 (R, Z) 最劣差 | 5 | measured_band | 五个磁面上 \|ΔR\| ≤ 0.36 mm、\|ΔZ\| ≤ 0.64 mm（约 3.5 m 的路径） | **成立** |
| 最深 psi_N 与 N∥（同面）的相对差 | 0.01 | measured_band | 最深 psi_N：本码 0.1456、TORAY 0.1455（8.3e-04）；N∥ 同面最劣 1.51e-04 | **成立** |
| 沉积：峰位 psi_N 之差；吸收份额 > 0.5 | 0.05 | measured_band | 峰位 psi_N：本码 0.2100（壳宽 0.02）、TORAY 0.1983 → 差 0.0117；吸收份额 1.0000 对 0.9990 | **成立** |
| 驱动电流每入射瓦对 TORAY 的比 | 0.2 | measured_band | 本码 1.9910e-02 A/W、TORAY 1.9031e-02 A/W → 比 1.0462（Zeff 取 TORAY 在沉积峰处的 1.999） | **成立** |

**`偏振支：|N| 在两射线同过的五个磁面上对 TORAY 的最劣相对差（所认之支 < 1 %，另一支 > 5 %）`** — ★哪一支没有写在四件输入的任何一处——它是**量出来的**，而且两半都守：认出的那支要贴、另一支要分得开。

**`射线：同一 psi_N 面上的 (R, Z) 最劣差`** — 单位 mm。★比的是**同一磁面**，不是同一序号或弧长：TORAY 的轨迹从进入等离子体处起算，本码从发射器起算。

**`最深 psi_N 与 N∥（同面）的相对差`** — N∥ 另守 1e-3（它曾因极向场符号差 25 %，F-33 修后到 1.5e-4）。

**`沉积：峰位 psi_N 之差；吸收份额 > 0.5`** — ★本码的壳宽 0.02，0.05 是两壳半；TORAY 的峰在它自己的 rho 上，按它自己的 xrho / xbouni 映到 psi_N。

**`驱动电流每入射瓦对 TORAY 的比`** — 带 0.9–1.2：两套独立的伴随 ECCD 实现，B 类。

**最深 psi_N 0.1456 对 0.1455；N∥ 1.5e-04**

- ★N∥ 这一格是这个参照**抓出过**一个真缺陷的地方：2026-09-11 以前本码的极向场少了 sigma_Bp（COCOS 17 要 −1），N∥ 系统偏低 25 %；|N| 与射线位置都对，偏的是 N 与 B 的夹角。

**沉积峰 0.210 对 0.198；吸收 1.0000 对 0.9990**

- ★差 0.012 不到一个壳：这一格的分辨率是本码的壳宽，不是物理。

**驱动电流每瓦 1.046 倍**

- ★单束、单一设计点：这一格说两套伴随 ECCD 在一个点上差 4.6 %，不说它在别处也这么近——对 METIS 认证库的散布（0.03–0.64）见 `tr-sources-eccd-metis`。

## 不可比的部分

- ★★**对拍不是验证**：两个码在一个点上吻合，说明两家描述的是同一个等离子体，不说明任何一家对。
- ★参考侧不在本处重跑：TORAY 的输出是冻结件，sha256 记在其头部（nc · echin · psiin · nml · state）。

## 追溯

- 首次入册 2026-09-19　末次修订 2026-09-19　版本 1.1　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-19 | Claude Opus 5 | 新立（新域 tr-sources）：EC 射线、沉积与伴随 ECCD 对 TORAY-GA 自己的一次运行——内核仓 test_cfedr_toray_oracle.py 的对照在公开仓的门上重跑、登记。 |
| 1.1 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`b27d7145ab3e`：新门 `code/icrh`——ICRH 少数离子加热第一次经门可达，`CASE_CODES` 41 → 42，只加不改）。内核侧：`icrh_door` 2 · `fyo` 7 全过。★没有一处既有缺省数值变动。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@b27d7145ab3e`（库 `sha256:2851c58ae6777d4783fc0071cfc21526509617470a174159a38a47de0074f074`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/ec_toray_cfedr20ma.json`    `sha256:774e831fababbad4ca784c22cb37756b2f8cd4d51c3de3ff3f0219b4516a247c`    比较量（tools/benchmark-hcd.py toray）
- `tools/benchmark-hcd.py`    `sha256:4ace082c4d14898369f529f7e87a1c2e277a1e1dd1bb629cccd3cb5858bf8d28`    读数生成器（closure · toray · kernel 三个子命令）
- `fylite_kernel/rust/fylite/testdata/reference/cfedr_toray_20ma.txt`    `sha256:d234bfa48b6c78c94a276b304b063db312064aa31863457d6d54cb3eeb36c42a`    ★TORAY 冻结件，内部件，在内核仓；指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_hcd.py::test_ec_the_branch_is_read_off_torays_data` —— 第一格
- `python/tests/test_benchmark_hcd.py::test_ec_the_ray_follows_torays` —— 第二、三格
- `python/tests/test_benchmark_hcd.py::test_ec_deposition_and_current_against_torays` —— 第四、五格
- `python/tests/test_benchmark_hcd.py::test_ec_the_comparison_reproduces_its_reading`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
