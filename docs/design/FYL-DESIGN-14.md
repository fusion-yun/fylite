---
document_id: FYL-DESIGN-14
title: "数据层：数据源 ↔ fyo (The Data Layer — Data Sources ↔ fyo)"
shortname: fylite-data-layer
version: "0.1"
date: 2026-09-02
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Code
created: 2026-09-02T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-02T00:00:00Z
  by: FyLite Maintainers
  change: 'v0.1 初稿：`rust/fylite_data/` 从「mdsip 编解码 + g-file」长成完整的数据层——
    不同数据源与 fyo 文档的读写转换、多数据源合并、按 JSON-LD 装配。只读 MDSplus /
    a-file；读写 JSON / g-file / HDF5 / netCDF，各带 fyo 与 IMAS DD 两种布局，IMAS 布局
    以 imas-python / imas-core 的读回为判据（`verify/imas_roundtrip.py`）。文件类型看
    内容识别。裁定 L-1..L-9。'
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-data-layer

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-14` |
| 文档名称 (Title) | 数据层：数据源 ↔ fyo (The Data Layer — Data Sources ↔ fyo) |
| 短名 / Slug | `fylite-data-layer` |
| 版本 (Version) | v0.1 |
| 发布日期 (Date of Issue) | 2026-09-02 |
| 信息分类 (Information Class) | Description (ISO/IEC/IEEE 15289 Annex A) |
| 适用标准 (Standard Reference) | — |
| 生命周期阶段 (Lifecycle Phase) | development (ISO/IEC/IEEE 15288) |
| 规范性 (Normative) | No (信息性) |
| 生命周期状态 (Status) | Working Draft |
| 责任团队 (Information Owner) | FyLite Maintainers |
| 贡献者 (Contributors) | FyLite Maintainers (Writing - original draft) |
| AI 辅助 (AI Assistance) | Claude Code |
| 受众 (Audience) | fylite developers / integrators reading or writing IMAS data |
| 分发范围 (Distribution) | public |
| 安全分级 (Security Classification) | public |
| 上游输入 (Upstream Inputs) | `FYL-SDD-01` DE-COMP-02（内核只算数）· `FYL-DESIGN-06`（归档；mdsip 只读客户端）· IMAS DD 4.1.1 结构 · imas-python `imas/backends/netcdf/` · IMAS-Core `src/hdf5/` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 承接 `FYL-DESIGN-06`（归档）的 mdsip 部分 |
:::

(fylite-data-layer-intro)=
# 数据层 (The Data Layer)

〔一句话〕**内核只算数，数据归这一层**：`rust/fylite_data/`（源码公开）把不同数据源读成
fyo 文档、把 fyo 文档写成别的格式，合并多个数据源，并按一份 JSON-LD 装配它们。
物理一行没有。

〔为什么〕`FYL-SDD-01` DE-COMP-02 与内核 `fyo.rs` 的抬头一起划了这条线：
*the kernel computes numbers; the hosts put them into documents*。2026-09-02 把 mdsip
从内核搬到本仓时，这一层只有协议编解码与 g-file；本篇写它长成什么样，以及每一条
选择的理由。

(fylite-data-layer-scope)=
# 范围 (Scope)

| 数据源 | 读 | 写 | 布局 | 模块 |
| :--- | :-: | :-: | :--- | :--- |
| MDSplus（mdsip） | ✓ | ✗ | 绑定表 → fyo | `mdsip` `mdsbind` |
| EFIT a-file | ✓ | ✗ | fyo | `afile` |
| EFIT g-file | ✓ | ✓ | fyo | `geqdsk` `eqdsk_fyo` |
| JSON / JSON-LD | ✓ | ✓ | fyo · IMAS DD | `json` `fyodoc` |
| HDF5 | ✓ | ✓ | fyo · IMAS | `hdf5` |
| netCDF | ✓ | ✓ | fyo · IMAS | `netcdf` |

「fyo 布局」＝本仓的文档（`@context` `@id` `@type` + DD 键名 + `fylite:` 本地词，
`python/fylite/fyo.py`）。「IMAS 布局」＝ imas-python / imas-core **原样读得回**的形。
多源合并（`document::Node::merge`）与装配（`assembly`）作用在同一棵树上。

(fylite-data-layer-decisions)=
# 裁定 (Decisions)

**L-1 一棵中立的树，每种格式只写两条路。** `document::Node`（插入有序映射 · 结构数组
列表 · 带形状的数值/字符串数组 · 标量）居中；N 种格式是 2N 条转换而不是 N²。
合并与装配只在树上做一次。

**L-2 文件类型看内容，扩展名只作备选。** g-file 没有扩展名（`g063982.04800`）、IMAS
HDF5 是一个目录、netCDF-4 本身就是 HDF5（同一魔数）。判据：目录含 `master.h5` →
IMAS 数据项；HDF5 魔数（允许在 user block 之后）且根有 `_NCProperties` → netCDF-4，
否则 HDF5；`CDF\x01/2/5` → 经典 netCDF；首字符 `{`/`[` → JSON；`*<数>` 头行 → a-file；
头一行两个正整数收尾且次行五个数 → g-file。

**L-3 IMAS 兼容的含义是「它们的读者认」，判据是对拍不是描述。**
`verify/imas_roundtrip.py`：imas-python 造参考数据 → 写 IMAS netCDF 与 IMAS HDF5 →
本层读、逐叶子比 → 本层写回两种 → imas-python / imas-core 读回、逐叶子比 →
imas-python `nc_validate` 过。单元测试里的期望值（维名、坐标、块大小、填充值）全部
**从 imas-python 写出的文件里读出来**，不是推的。

**L-4 IMAS 布局的元数据从 DD 的 `IDSDef.xml` 生成，不从 fyo 的 schema。** imas-python
读回时逐变量核对维名（`nc2ids.py::_validate_variable`），维名由 DD 的坐标声明推出
（`nc_metadata.py`：`1...N` 生一维、`../grid/dim1` 共维、`alternative_coordinate1` 并维、
齐次时间并成 `time`）。fyo 的 `dd_coordinate*` 注记是 XSD 相对写法、且不带
`alternative_coordinate1` / `coordinate*_same_as`——正是决定维名的两样。所以
`tools/dd-ids-table.py` 从 imas-python 读的同一份 XML 生成 `ids/<ids>.tsv`（82 个 IDS，
1.6 MB，只有路径 / 种类 / 维数 / 单位 / 坐标——**DD 的文字一个字不抄**，fyo `CLAUDE.md`
的 CC BY-ND 规则），`ids_meta.rs` 是 `nc_metadata.py` 的逐条移植。表是提交进仓的
生成物；fyo 那侧的语义（类型、`fylite:` 词表）不在表里，也不需要在。

**L-5 HDF5 的数据轴是转置，不是反形状。** imas-core 按 Fortran 序存数据轴
（`dims[i+AOSRank] = size[dim-i-1]`）：`(4, 3)` 的 numpy 数组在盘上是 `(3, 4)` 且
`d[j][i] = a[i][j]`（imas-core 5.7.2 写、h5py 读，实测）。所以每个元素经转置进盒子、
读回再转回来。把 `dims` 反过来而字节不动，读出来的是静默转置了的 ψ——与 mdsip
「最快变维在前」同一形状的错，本仓在转置上已经吃过一次。

**L-6 张量化写一次，两种 IMAS 布局共用。** 结构数组的一族叶子压成「AoS 轴 + 数据轴」
的盒子，元素真实形状另存（HDF5 `_SHAPE` / netCDF `:shape`），元素个数另存（`AOS_SHAPE` /
维长与 `:shape`）。两种布局只在轴序、填充值（`-9e40` · `-999999999` vs netCDF 缺省
`9.969e36` · `-2147483647`）与稀疏判据上不同，压与解压在 `tensor.rs` 各一份。

**L-7 fyo → DD 是一次归一化，且报告丢了什么。** 语义键与 `fylite:` 词丢掉、DD 不认的
路径丢掉——**记在报告里**（`DdReport`），命令行与 Python 都转述；DD 说一维而文档给标量
的提成一元数组（`vacuum_toroidal_field/b0`）；缺 `homogeneous_time` 与根 `time` 的从
时间片合成。限制器随平衡走（`fylite:limiter`），写 IMAS 布局时束里没有 `wall` 就从它
合成一份——DD 里它的家在那里。

**L-8 MDSplus 只读由构造保证，装配不放松它。** `assembly` 的 `$link` 表达式经
`mdsbind::decompose`（`tools/abox-mds-bind.py::decompose` 的移植：由外到内剥倍率、
下标、动词、括号内下标）分解成「动词 + 节点路径 + 整数」才交给 `mdsip::Client::read`；
分解不了的（下标读另一个节点、未知动词、`getenv(...)`）列在失败里，不猜、不发。
`fylite/mds-bind/1` 扁平表与 A-Box 的 `$source`/`$link` 文档都认。

**L-9 两个 C 库，特性门控，wasm 不带。** HDF5 的文件格式与 netCDF-4 的方言自己写一份
能与 imas-python 互读的实现是一个季度的活、且是第三实现；目标是逐字兼容，所以链
`libhdf5` / `libnetcdf`（`hdf5-metno` / `netcdf` crate），缺省动态链接系统库，
`--static` 从源码编进。`--no-default-features` 是 wasm 那档：g-file 与 JSON，零依赖。

(fylite-data-layer-faces)=
# 面 (Faces)

| 面 | 在哪 | 给谁 |
| :--- | :--- | :--- |
| Rust API | `io::{detect, read, write, merge_paths}` · `assembly::assemble_file` | 本仓的 Rust 宿主 |
| C ABI | `c_api.rs` `fylite_data_{read, read_text, write, detect, bundle_*, doc_*, assemble}` | Python（`fylite.io.fydoc`） |
| 命令行 | `fylite-data info / dump / convert / merge / assemble / tables` | 人与脚本 |
| Python | `fylite.io.fydoc.{read, write, detect, assemble, Bundle}` | 本仓的 Python 宿主 |

取值路径 `"<ids>[_<occ>]/a/b/c"`：头一段是 IDS，其余是文档路径；不带索引的名字段落到
结构数组的第 0 个——与内核 `fyo.rs` 的 `@fyo-table` 同一条规则。

(fylite-data-layer-gaps)=
# 缺口 (Gaps)

| 编号 | 缺口 | 状态 |
| :--- | :--- | :--- |
| G-1 | 复数叶子（DD `CPX_*`）不写 IMAS 布局（拒绝而不是猜） | 开 |
| G-2 | netCDF 字符串变量不带 `_FillValue`（`netcdf` crate 没有公开的 `nc_def_var_fill` 字符串入口；imas-python 读法不变） | 开 |
| G-3 | 时间切片操作（imas-core 的 `put_slice` / `get_slice`）不做；整份 put/get | 开 |
| G-4 | a-file 的 X 点 / 打击点：DD 4.1.1 `boundary` 下无槽，只留在 `fylite:afile` 原始块 | 开 |
| G-5 | wasm 目标未在 CI 构建（本机无 `wasm32-unknown-unknown`）；`--no-default-features` 的原生构建是代理判据 | 开 |
| G-6 | 活的 MDSplus 对拍：绑定表解析经照本宣科的传输判过，未对真服务器跑 | 开 |
