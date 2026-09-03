---
document_id: FYL-DESIGN-14
title: "数据层：数据源 ↔ fyo (The Data Layer — Data Sources ↔ fyo)"
shortname: fylite-data-layer
version: "0.2"
date: 2026-09-02
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Code
created: 2026-09-02T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-02T12:00:00Z
  by: FyLite Maintainers
  change: 'v0.2：按炮号与时间取 MDSplus 切片——`params.time`（点 / 窗 / 点列）在时基上
    落成整数下标、服务端切片、`time_slice` 展开、`homogeneous_time` 收尾（L-10）；
    零依赖的 YAML 子集读者，Rust 侧直接读 fydata 的 A-Box（L-11）；装置清单
    `machine.yaml` 摊成装配（`fetch`）；结构数组按 `name` 对齐的合并；`select` 挑选。
    缺口 G-3 部分关闭，新增 G-7 / G-8。
    v0.1 初稿：`rust/fylite_engine/` 从「mdsip 编解码 + g-file」长成完整的数据层——
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
| 版本 (Version) | v0.2 |
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

★**crate 已改名**（2026-09-04，`FYL-DESIGN-16` N-1）：`rust/fylite_data/` → `rust/fylite_engine/`，制品
`libfylite_engine.so`，C 导出 `fylite_engine_*`。本篇讲的是这一层里**数据**那一半（格式、装配），
所以标题不改；下文的路径已随改名机械更新。

〔一句话〕**内核只算数，数据归这一层**：`rust/fylite_engine/`（源码公开）把不同数据源读成
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
| MDSplus（mdsip） | ✓ | ✗ | 绑定表 → fyo；按时间开窗 | `mdsip` `mdsbind` |
| fydata A-Box（YAML） | ✓ | ✗ | fyo | `yaml` |
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

**L-10 时间选择在绑定层落成整数，切片在服务端做。** 请求里的时间（一个点、一个窗
`[t0, t1]`、一列点；`params.time` / `--time 4:5`）不是 TDI 表达式：`mdsbind` 先读节点的
时基（`dim_of(node[, axis])`，按 (树, 炮, 节点, 轴) 缓存——一炮里一个节点只过网一次），在
时基上查出下标，再以 `Index::Range{start, stop, step}` / `Index::At` 发出
`data(\X)[i0:i1:step]`——整条信号不过网，`mdsip::Client` 仍只认「动词 + 节点 + 整数」
（L-8 不动）。时间轴在哪：没有下标的是一维信号（第 0 轴）；恰有一个 `*` 且无
`{time_slice}` 的取那一位（EFIT 的 `\X[i,*]` → `dim_of(\X,1)`）；`time_slice/*/…` 的绑定按
IDS 根 `time` 上选出的下标展开成若干时间片（没有根 `time` 时退到该节点 `{time_slice}`
那一轴的 `dim_of`，并记一条说明）；其余读整条并记说明——不猜。`DIM_OF(节点)` 就是时基，
从缓存里切；一个点是长度 1 的数组，与 DD 「随时间的数组」同形。收尾：各通道 `…/time`
相同 → `ids_properties/homogeneous_time = 1` 并补根 `time`，否则 0；`fylite:time_selection`
记下问的是什么。点不外推：窗里没有样本是失败，不是空数组。

**L-11 一个只认 fydata 方言的 YAML 读者，零依赖。** fydata 的装置 A-Box（`machine.yaml`、
`providers/*.yaml`、`bind/mdsplus/*.yaml`、`static/legacy/*.yaml`）全是 PyYAML 写出的
YAML：块式映射与序列、三种标量写法、少量单行流式 `{}` / `[]`——没有锚点、别名、标签、
多文档。`yaml.rs`（约五百行）只认这些，不认的**报错**而不是猜；标量按 YAML 1.1 断型
（`0123` 是八进制、`yes` 是真——与 PyYAML 同），只在浮点上更宽（`2.2e6` / `140E9` 按数读，
PyYAML 按 YAML 1.1 读成字符串；fydata 里有 6 处）。判据是对拍：`verify/yaml_gate.py`
拿 fydata 的 47 份文件比 `fylite data dump --raw` 与 `yaml.safe_load`，逐叶子相同。
于是装配文档的 `file:` 源可以直接指 fydata 的 YAML，装置清单 `machine.yaml` 可以摊成
装配（`assembly::from_manifest`：炮 → epoch，提供者 → 几何文件，绑定 → 绑定文档）——
Rust 侧不再等 Python 先投影成 JSON。

**L-12 结构数组按 `name` 对齐地合并。** 几何（`providers/magnetics/pcs.yaml`，按 `name`）
与测量（绑定文档，按 `id`）是两份不同来路的列表；合并时两边都带 `name` 的元素按值
对齐（次序不同也对得上），对不上的追加，任一边没有键的退回按下标——fydata 的绑定
文档没有 `name` 而次序与几何一致，所以缺省 `merge_key: name` 对它无害。`select`
（`ids` / `ids/子树`）在合并与覆盖层之后挑选，语义键、`ids_properties`、`time`、
`fylite:*` 与元素的 `name` / `identifier` 总是留着。

**L-9 两个 C 库，特性门控，wasm 不带。** HDF5 的文件格式与 netCDF-4 的方言自己写一份
能与 imas-python 互读的实现是一个季度的活、且是第三实现；目标是逐字兼容，所以链
`libhdf5` / `libnetcdf`（`hdf5-metno` / `netcdf` crate），缺省动态链接系统库，
`--static` 从源码编进。`--no-default-features` 是 wasm 那档：g-file 与 JSON，零依赖。

(fylite-data-layer-faces)=
# 面 (Faces)

| 面 | 在哪 | 给谁 |
| :--- | :--- | :--- |
| Rust API | `io::{detect, read, read_node, write, merge_paths}` · `assembly::{assemble_file, from_manifest}` · `mdsbind::{TimeSel, resolve, read_one}` | 本仓的 Rust 宿主 |
| C ABI | `c_api.rs` `fylite_engine_{read, read_text, write, detect, bundle_*, doc_*, assemble, fetch}` | Python（`fylite.io.fydoc`） |
| 命令行 | `fylite data info / dump / convert / merge / assemble / fetch / tables`（Python 宿主；`fylite-app data …` 是同一条，见 `FYL-DESIGN-15` C-8） | 人与脚本 |
| Python | `fylite.io.fydoc.{read, write, detect, assemble, fetch, Bundle}` | 本仓的 Python 宿主 |
| Python（经由） | `fylite.fyo.read` / `write` 的 `.h5` 分支、`fylite.io.mds` 与 `io.est2` 的在线路径（`kernel.MdsSession`）——★2026-09-04 起这三处**不再各有一份**（h5py 走树、站点 `MDSplus` 包），都交给本层；`io.imas_h5` / `io.jetto_bin` 两个零调用者的读者同批删除 | 本仓的 Python 宿主 |

一个请求就是一份装配文档（JSON 或 YAML），或一条 `fetch`：

```text
fylite data fetch --machine fydata/machine/tokamak/east/machine.yaml --ids magnetics \
                 --shot 138569 --time 4:5 --host mds.ipp.ac.cn -o east_138569_magnetics.json
```

= 清单里 `providers.magnetics.default`（`pcs`，几何 38 探针 / 35 磁通环）+
`bindings.mdsplus.ids.magnetics`（`magnetics_pcs.yaml`，`pcs_east` 树）→ 每个探针
`dim_of(\PCBPVnT)` 一次、`data(\PCBPVnT)[i0:i1]` 一次 → 一份 `fyo:magnetics`，
`b_field_pol_probe[n].field.{data, time}` 是 4～5 s 的切片，`position` 来自几何，
`fylite:assembly` 记炮号、时间窗与源。

取值路径 `"<ids>[_<occ>]/a/b/c"`：头一段是 IDS，其余是文档路径；不带索引的名字段落到
结构数组的第 0 个——与内核 `fyo.rs` 的 `@fyo-table` 同一条规则。

(fylite-data-layer-gaps)=
# 缺口 (Gaps)

| 编号 | 缺口 | 状态 |
| :--- | :--- | :--- |
| G-1 | 复数叶子（DD `CPX_*`）不写 IMAS 布局（拒绝而不是猜） | 开 |
| G-2 | netCDF 字符串变量不带 `_FillValue`（`netcdf` crate 没有公开的 `nc_def_var_fill` 字符串入口；imas-python 读法不变） | 开 |
| G-3 | 时间切片：读 MDSplus 按时间开窗已做（L-10）；文件侧 imas-core 的 `put_slice` / `get_slice` 不做，整份 put/get | 部分 |
| G-4 | a-file 的 X 点 / 打击点：DD 4.1.1 `boundary` 下无槽，只留在 `fylite:afile` 原始块 | 开 |
| G-5 | wasm 目标未在 CI 构建（本机无 `wasm32-unknown-unknown`）；`--no-default-features` 的原生构建是代理判据 | 开 |
| G-6 | 活的 MDSplus 对拍：绑定表解析与时间开窗经照本宣科的传输判过（发出的 TDI 文本逐条核对），未对真服务器跑 | 开 |
| G-7 | 一列点落在多维节点上时沿新的第 0 轴堆叠（记说明）；`Points` 逐点各一次往返，长列表该改成一次区间读再本地挑 | 开 |
| G-8 | 装置清单 `machine.yaml` 是起步草稿；`from_manifest` 只看 `epochs` / `providers` / `bindings.mdsplus` 三段，清单变形要跟着改 | 开 |
