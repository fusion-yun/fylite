---
title: "mhd-deltaw-delivery-records"
---

# MHD 判读的交付层：**每一条禁令都是一次拒绝，每一次拒绝都被证伪过**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-deltaw-delivery-records.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [全 delta-W、V5 基准与阻性壁模](../domains/mhd/deltaw.md)　|　记录正本：`records/mhd-deltaw-delivery-records.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：MHD 判读的交付层：**每一条禁令都是一次拒绝，每一次拒绝都被证伪过**
- **参考**：IMAS DD 4.1.1 `mhd_linear` 与 SRS 的四条口径纪律
- **验的需求**：`FR-EQ-026`
- **跑在内核**：`fylite_kernel@0f7e5af3b3cf`（新鲜度 **current**）
- **记录版本**：1.10　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：2026-09-18 新写：只产 `dict`，纯标准库；造形集中在这一个模块，物理模块不认得 DD

**参考**：IMAS DD 4.1.1 `mhd_linear` 与 SRS 的四条口径纪律

> DD 字段集取本仓自带的 IDS 表 `rust/fylite_runtime/ids/mhd_linear.tsv`；纪律见 FR-EQ-026 (a)–(d)。

**口径与适用域**：

> DD 4.1.1 `mhd_linear` 的 `time_slice/toroidal_mode` 与 IDS 级 `code.parameters` / `ideal_flag`；**不改变任何物理判读**。

## 判据与量到多少

:::{figure} ../figures/mhd-deltaw-delivery-records-headroom.svg
:alt: mhd-deltaw-delivery-records 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| L0/L1/oracle 的 `growthrate` 一律为空；装配处拦下「能量原理类 kind 却带有限 growthrate」 | — | reference_self_reported | 三类能量原理记录都没有 growthrate；装配处拦下填了 0 的那条（0 会被读成中性稳定），竖直模照常带 | **成立** |
| 本仓侧判读量只在 `parameters`、DD 字段不越界 | — | reference_self_reported | 判读量进 `code.parameters`（JSON）；往 mode 里塞一个 `q_crit` 被按名拒绝；DD 字段集由测试从 IDS 表逐项核对 | **成立** |
| L0 标 `q_limit` 且注明禁称 β 极限；表面电流记录自带 optimistic / 柱等价告诫 | — | reference_self_reported | L0 的 caveat 写着 not a beta limit；表面电流记录的 caveat 同时含 optimistic 与 cylindrical-equivalent | **成立** |
| 气球模 `n_phi` 缺省留空（显式给才填、非正即拒） | — | reference_self_reported | 缺省无 `n_phi`；给 20 即填；0 / −3 / 2.5 / True 全拒 | **成立** |
| `source` 为空即拒（oracle 与标度两处）；经验标度不填任何 DD 计算字段 + 非有限值拒收 | — | reference_self_reported | 空串与全空白的 source 在 oracle 与标度两处都拒；标度记录 toroidal_mode 为空；NaN / inf 拒 | **成立** |
| `ideal_flag` 不替调用方猜（阻性壁竖直模须显式 0） | — | reference_self_reported | `ideal_flag` 仅限关键字、无缺省——不给即 TypeError；阻性壁给 1 被拒；给 True 被拒 | **成立** |
| 自包含用语法树查 import | — | reference_self_reported | 语法树上的 import 恰为 `__future__` · `json` · `math` | **成立** |

**语法树上的 import 恰为 `__future__` · `json` · `math`**

- ★模块说明文字里提到别的包名——按文本 grep 会被自己的注释绊倒，所以查语法树。

## 不可比的部分

- ★★**判决成立**：七格全过。这一层只解决**造形与口径**；各判读量的可信度仍由各自的记录（`FR-EQ-017` · `018` · `021` · `016`）承担。
- ★门在本仓（`python/tests/test_mhd_records.py`），CI 跑得到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-19　版本 1.10　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-026` 判**成立**。新模块 `fylite.mhd_records`：能量原理类不带 growthrate、装配处拦下混用、判读量只进 code.parameters、告诫随记录走、n_phi 缺省留空、ideal_flag 不猜、语法树查 import。11 道门都在本仓。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（环几何全 δW 入内核：`toroidal.rs`，`screwpinch.rs` 增阻性壁模；`FR-EQ-029` · `030` · `031`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **787 项全通过**（新锚 14 条，另 5 条 V5 门在 --release 下全过）。★纯增量（新模块，没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（动量通道闭合补三处：`solve_momentum` 加 pinch、`code/evolve` 收 `chi_turb_phi` · `v_phi`、扩展门 `code/turbulence` 按 `momentum_flux` 出 χ_φ、`core_transport` 挂 `momentum_phi/{d,v}`；`FR-TR-008`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过。★只加槽（接口摘要 `80f1dacaccb1d6db` → `1ee10b0ae6f30088`，修订号不动）：新输入都是可选的、`momentum_flux` 缺省关，既有调用逐位不变。 |
| 1.3 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.4 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.5 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 热能计稀释入内核：`zerod::ion_fraction`，`code/zerod` 收可选设定 `z_imp` / `z_imp2` / `r_imp2`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **805 项全通过**（新锚 4 条）。★不给 `z_imp` 时 n_i = n_e，逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.6 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（平衡 / MHD 三条判据补齐入内核：`highbeta::surface_energy_book`、`code/vstab` 新报 `k_identity_filaments`，另加 conformal / stability 的锚；`FR-EQ-024` · `025` · `016`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **809 项全通过**（新锚 4 条）。★缺省路径逐位不变，接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.7 | 2026-09-19 | Claude Opus 5 (1M context) | 内核换代后的全册重验（线圈表面场收敛入内核：`electromagnetics::surface_field_converged`、`loop_field`，`code/forces` 的 `b_surface` 改用面积分；`FR-EQ-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **812 项全通过**。★只动了 `b_surface`，受力与其余门逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 |
| 1.8 | 2026-09-19 | Claude Opus 5 | 内核指纹改按 git 提交（用户 2026-09-19 裁定「kernel fingerprint 按 git 走」）：`run.kernel` 由库的 sha256 换成内核仓提交 `51d34102a406`（本条上一次重验所跑的库就建自这个提交），原 sha256 留作 `library_sha256`。★判据、数值与判决都未动。 |
| 1.9 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`94ca1a29d6ed`：α 份额取 3.52/17.59 · Post 式 α 分配 · EPED1-NN 金标 · 0D 体平均的形状权重 / 可绑 dV/dρ；`FR-TR-004` · `009` · `014` b）。内核侧 **cargo test 817 过、0 失败、35 忽略**。★缺省路径除 α 份额外逐位不变；接口摘要、`CASE_CODES`、ABI 均未动。 ★本条的判据与数值**未改口径**。 |
| 1.10 | 2026-09-19 | Claude Opus 5 | 内核换代后的全册重验：内核换代（`0f7e5af3b3cf`：1.5-D 各通道耦合整体求解成为缺省——`FR-TR-006`，用户裁定「决定要整体求解」；Te/Ti 块系统、交换隐式，遍数迭代到收敛，α · 辐射 · 欧姆在步内重算）。内核侧 **cargo test 822 过、0 失败、35 忽略**。★`code/evolve` 的缺省数值随之动（ITER 15 MA 上 P_α +1.6 %）；其余入口逐位不变，旧路径以 `sequential` 留作对照。 ★本条的判据与数值**未改口径**。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@0f7e5af3b3cf`（库 `sha256:ac8204aa49349cc0ac53b3b5f9d7b91630ce4d69380fc7aa37034c89ce54dfe8`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/mhd_records_delivery.json`    `sha256:b04433371602f37bda3a9574b720d2840bc9e28b3bd40f7fe31f4f7d31faf2b1`    模块、DD 字段集、能量原理类、导入清单

**守它的门**：

- `python/tests/test_mhd_records.py::test_energy_principle_records_have_no_growthrate` —— 第一格
- `python/tests/test_mhd_records.py::test_the_assembly_catches_an_energy_principle_record_with_a_growthrate` —— ★第一格：装配处拦下
- `python/tests/test_mhd_records.py::test_judged_quantities_ride_in_code_parameters_not_in_dd_fields` —— 第二格
- `python/tests/test_mhd_records.py::test_the_dd_field_set_is_the_ids_tables_own` —— 第二格：字段集对 IDS 表
- `python/tests/test_mhd_records.py::test_l0_is_a_q_limit_and_says_so` —— 第三格
- `python/tests/test_mhd_records.py::test_the_surface_current_record_carries_its_own_caveats` —— 第三格
- `python/tests/test_mhd_records.py::test_ballooning_leaves_n_phi_empty_unless_given` —— 第四格
- `python/tests/test_mhd_records.py::test_an_empty_source_is_refused_for_the_oracle_and_the_scaling` —— 第五格
- `python/tests/test_mhd_records.py::test_a_scaling_fills_no_dd_field_and_refuses_non_finite` —— 第五格
- `python/tests/test_mhd_records.py::test_ideal_flag_is_never_guessed` —— 第六格
- `python/tests/test_mhd_records.py::test_the_module_imports_only_json_and_math_on_the_syntax_tree` —— 第七格

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
