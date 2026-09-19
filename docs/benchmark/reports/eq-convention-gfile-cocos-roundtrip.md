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
- **跑在内核**：`fylite_kernel@e05a90fd06fe`（新鲜度 **current**）
- **记录版本**：1.24　**评审**：草稿　**日期**：2026-09-16

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

- 首次入册 2026-09-16　末次修订 2026-09-19　版本 1.24　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-16 | Claude Opus 5 (1M context) | 首次入册：eq-convention 的第一条记录，四条判据全过，数值取自当日实测读数 |
| 1.2 | 2026-09-17 | Claude Opus 5 (1M context) | 内核同日两次换代后的全册重验（原 1.1 与 1.2 两条，2026-09-18 合并——第二条当时误抄了第一条的摘要）：①`301a962b` → `ac8c0f5c`，`FR-EQ-002/008/010/011` 与 0D 三项入内核（内核仓 `3ea79df`），fylite 侧 110 道、内核侧 656 项全通过；②`ac8c0f5c` → `eb8c9022`，ETS 五型边界、燃烧→密度的接线、时间收敛阶入内核（内核仓 `acd1628`），165 道门禁全过、660 项既有内核测试一项没动。★两次本条的判据与数值都**未改口径**。 |
| 1.3 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-TR-001` 通道描述子入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **667 项全通过**，fylite 侧 2562 项通过。★fylite 侧另有 37 项失败，**逐项核过与本册无关**：30 项是这台检出没建 `rust/fy` 可执行，4 项是本次一并重生成的生成件，3 项（`psi_points` 无参数面等）在本次改动**之前**就是红的。 |
| 1.4 | 2026-09-17 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-014` 线圈受力入内核，新门 `code/forces`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2762 项通过。★这一批内核改动是**纯增量**（新函数、新门），没有改动任何既有路径；接口摘要因加了一行 `CASE_CODES` 而变，修订号不动。 |
| 1.5 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`NR-EQ-001` 的通量规统一入内核，ABI 154 → 155）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **671 项全通过**，公开仓侧 2783 项通过。★这一批改动会移动 `code/discharge` 的 ρ 与无 q 剖面时文档梯子的 q（见 `eq-convention-ladder-flux-gauge`）；本条的数**不在那两条路径上**，故未变。 |
| 1.6 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-013` MXH 拟合 · `NR-EQ-003` 后验协方差 · `FR-EQ-016` 补三处入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **675 项全通过**，公开仓侧 2809 项通过。★这一批内核改动是**纯增量**（新函数、既有门加字段与可选设定），接口摘要与 `CASE_CODES` 均未动。 |
| 1.7 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-017` 理想外扭曲模的 q 极限入内核——内核里第一段理想 MHD 稳定性）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **680 项全通过**，公开仓侧 2821 项通过。★这一批内核改动是**纯增量**（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.8 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-018` 气球模第一稳定边界入内核）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **685 项全通过**，公开仓侧 2828 项通过。★纯增量（`stability.rs` 新增函数，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.9 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（`FR-EQ-021` 表面电流模型 β 极限、`FR-EQ-025` 共形映射入内核；并救回五条失声的内核门）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **709 项全通过**（新锚 19 条 + 救回 5 条）。★纯增量（`stability.rs` 新增函数、新模块 `conformal.rs`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.10 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（L2 本体入内核：`variational.rs` · `fluid.rs` · `vacuum.rs` · `highbeta.rs`，`FR-EQ-019/020/022/023/024`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **753 项全通过**（新锚 44 条）。★纯增量（新模块与 `stability.rs` 新增 `surface_current_wall_factor`，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.11 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（全 δW 支柱位形一级入内核：`screwpinch.rs`，`FR-EQ-027` · `028`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **773 项全通过**（新锚 20 条）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.12 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.13 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.14 | 2026-09-18 | Claude Opus 5 (1M context) | 合并重复的变更条目：1.1 与 1.2 是同日两次内核换代，第二条误抄了第一条的摘要；合并成一条（沿用 1.2），两次换代各自写明。★本条的判据与数值未动。 |
| 1.15 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.16 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.17 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.18 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.19 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.20 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.21 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.22 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.23 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`915ed1249591`：自由边界缺省换成边规则——`FR-EQ-001`，用户裁定「边规则为缺省」；无位置控制器的设计锚在上一次解、残差读线圈自己的场、末尾撤锚——用户裁定「做正经的修」；逆解线性核的合成场回收锚——`FR-EQ-005`）。内核侧 **cargo test 823 过、0 失败、35 忽略**。★`code/forward` 与无位置控制器的 `code/discharge` 缺省数值随之动；ITER 的 c4 路径与其余入口逐位不变，节点规则以 `edge_fraction = 0` 留作对照。 ★本条的判据与数值**未改口径**。 |
| 1.24 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`e05a90fd06fe`：`code/rf_ray` 的说明照实——吸收与伴随 ECCD 已实现；HCD 对 METIS 的测试打印登记读数（新域 `tr-sources`）；其间合入 VEQ 定边界求解（`code/fixed_boundary` 的 `method = veq`，缺省 `grid` 逐位不变）。内核侧：`fyo` 7 · `heating` 60 · `rfray` 61 全过。★没有一处缺省数值变动。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@e05a90fd06fe`（库 `sha256:19f2501e8437587d71fc7642cbcfc9aa63c7ebf2a5d89e7a4b92dec2f788c223`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

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
