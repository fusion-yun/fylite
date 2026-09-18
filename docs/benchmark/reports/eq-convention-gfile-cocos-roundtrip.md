---
title: "eq-convention-gfile-cocos-roundtrip"
---

# g-file 口径：读—写—再读是不动点，量出的 COCOS 不动，两套读者逐位一致

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/eq-convention-gfile-cocos-roundtrip.jsonld`，本页只是它的可读面。 -->

*平衡 (Equilibrium) · [约定与口径：COCOS 与插件接入](../domains/eq/convention.md)　|　记录正本：`records/eq-convention-gfile-cocos-roundtrip.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：g-file 口径：读—写—再读是不动点，量出的 COCOS 不动，两套读者逐位一致
- **参考**：恒等式：写之后再读，必须回到原处 · 同一读取函数的另一实现（Python 定宽参照读者 ↔ Rust 数据层读者）
- **验的需求**：`NR-EQ-001` · `NR-EQ-006`
- **跑在内核**：`sha256:c5b0d8699709dea9…`（新鲜度 **current**）
- **记录版本**：1.9　**评审**：草稿　**日期**：2026-09-16

## 问的是什么

**被量的**：`fylite.io.geqdsk` 的读写与 `measure_cocos`，以及内核数据层的 `kernel.read_gfile`

**参考**：恒等式：写之后再读，必须回到原处

> ★**参考是它自己**——往返是一条恒等式，不是一份外部答案。所以容差取**机器精度**，不取物理带：物理带会把「写入端换了一个数」这类偏差整个盖住。

**参考**：同一读取函数的另一实现（Python 定宽参照读者 ↔ Rust 数据层读者）

> ★两份实现读的是**同一串十进制文本**，所以判据是**逐位相同**而不是「近似」。任何一位差都说明有一侧切错了位置——那不是容差问题。

**口径与适用域**：

> 两份语料各答一问：**仓内合成件**（`rust/fylite_runtime/testdata/g_synthetic.geqdsk`，65x65，构造已知、永远在场）与**一份真炮**（EAST #70754 @ 5000 ms，129x129，来自 fydoc 算例书 FYDOC-CASE-19）。★真炮件里有合成件挑不出的东西：列宽、负号吃空格、老写法。只用合成件会把这些漏掉。★比较落在 g-file 的 25 个数值字段 / 13 个标量 + 10 个数组上；COCOS 由 `measure_cocos` 在**文件自己的边界多边形之内**量出。

## 判据与量到多少

:::{figure} ../figures/eq-convention-gfile-cocos-roundtrip-headroom.svg
:alt: eq-convention-gfile-cocos-roundtrip 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 往返后每个数值字段的最劣相对偏差 | 1e-09 | machine_precision | 合成件 0（25 个字段）· EAST #70754 0（25 个字段）——两者皆为**精确零** | **成立** |
| 头一行经一次往返是否逐字不变 | 0 | machine_precision | 合成件不变 · EAST 不变（`EFITD    08/02/2006    # 70754  5000ms           3 129 129`） | **成立** |
| 量出来的 COCOS 口径是否因往返而变 | 0 | machine_precision | 两份件的口径均不变；EAST 侧量到 psi_axis=minimum · sign_ip=+1 · sign_b0=+1 · sign_q=+1 · dpsi, per radian（残差 0.07288，次优解差 11.5 倍） | **成立** |
| 两套读者对同一份件的每个标量与数组元素 | 0 | machine_precision | 合成件 13 标量 + 10 数组 / 4922 个元素逐位相同；EAST #70754 13 标量 + 10 数组 / 17600 个元素逐位相同；差异字段：无 | **成立** |

**`头一行经一次往返是否逐字不变`** — ★★**单独判，不并进上一条。** g-file 没有版本号，头一行是它唯一的自述（谁写的、哪一炮、哪一时刻）。并成一条的话，「25 个字段全对」会把它盖住——而 2026-09-08 那次唯一的缺陷恰恰只在这一行（写入端把 `idum` 写死成 0）。

**`量出来的 COCOS 口径是否因往返而变`** — ★COCOS 是**量出来**的（`measure_cocos`），不是读标签读来的；标签是离散值，判等不判带。

**`两套读者对同一份件的每个标量与数组元素`** — 逐位相同，不是近似

**往返：每个数值字段**

- ★偏差是 0 而不是「小于 1e-9」：往返走的是同一串十进制文本，本就该逐位回来。若哪天它变成 1e-12，那不是「仍然很好」，是写入端开始重新格式化数字了。

**往返：头一行**

- ★这一条是 2026-09-08 唯一失手的地方，修在 `format_geqdsk`。它留在册上不是纪念，是因为**写入端最容易再犯的就是这一处**。

**往返：量出的 COCOS**

- ★**裕度 11.5 倍值得记**：它说明这次判读不是在两个口径之间勉强择一，而是次优解差了一个数量级。裕度小的时候，同一条「口径不变」的判据含金量完全不同。

## 不可比的部分

- ★★**本条不判任何物理**。它问的是「本仓的读与写互为逆」「两套读者读出同一串数」，不是「这份 g-file 的平衡对不对」。口径对齐是**跨码比较的前置条件**，不是结论——别的记录引本条，是为了说明它们的数放在一起可比。
- ★**真炮件是实验类指针**：它住在 fydoc 检出里（本仓不带真炮 g-file），读数里记的是绝对路径 + sha256。换一台机器要设 ``$FYDOC_DIR``；够不到时门按名 skip，**不拿合成件顶替**——顶替会让这条判据在缺了一半语料时仍显示绿色。
- ★**往返闭合不保证写出去的文件对别的码可读**。它只保证本仓自洽。对外部 EFIT/CHEASE 读者的可读性是另一件事，本域尚无记录。

## 追溯

- 首次入册 2026-09-16　末次修订 2026-09-18　版本 1.9　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-convention 的第一条记录，四条判据全过，数值取自当日实测读数 |
| 1.1 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-002/008/010/011` 与 0D 三项入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：fylite 侧 110 道、内核侧 656 项全通过。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:c5b0d8699709dea9f7e7b27b20f55bdbf2bf790944da28ddafafa4c4fa82f957`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/gfile_cocos_roundtrip.json`    `sha256:b70a56cdcd2540f2d34c26f6f83f96ac0284d9e65f463af491d51c2370f215d4`    本条的读数：两份语料 × （往返 / COCOS / 两读者）
- `rust/fylite_runtime/testdata/g_synthetic.geqdsk`    `sha256:36abf675b548df8316e6073debf9631180a8651348deb6cf544df0c2894ad3c9`    仓内合成件
- `/mnt/SandBox/salmon/workspace/fydoc/cases/FYDOC-CASE-19-east-efit/corpus/g070754.05000`    `sha256:a9a39446a2e767f1c40700a25b0969edc8b480a8d6e09bdb9404b04d2b2e6342`    真炮件（实验类，指针 + sha256；在 fydoc 检出里，设 `$FYDOC_DIR` 指过去）

**守它的门**：

- `python/tests/test_gfile_roundtrip.py::test_every_number_survives_the_round_trip`
- `python/tests/test_gfile_roundtrip.py::test_the_first_line_is_an_invariant`
- `python/tests/test_gfile_roundtrip.py::test_the_cocos_measurement_does_not_move`
- `python/tests/test_gfile_equivalence.py::test_the_two_readers_agree_on_every_number`
- `python/tests/test_gfile_equivalence.py::test_the_header_survives_verbatim`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
