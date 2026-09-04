---
document_id: FYL-DESIGN-14
title: "中间层的数据半边：数据源 ↔ fyo (The Data Half of the Middle Layer — Data Sources ↔ fyo)"
shortname: fylite-data-layer
version: "1.5"
date: 2026-09-04
language: bilingual
contributors:
  - name: FyLite Maintainers
    roles: Writing - original draft
ai_assistance:
  - Claude Code
created: 2026-09-02T00:00:00Z by FyLite Maintainers
modified:
  date: 2026-09-04T00:00:00Z
  by: FyLite Maintainers
  change: |-
    v1.5 该选项由 `--machine` **改名为 `--device`**（用户裁定）：它收的主用法是 facts 上的
    装置名，`--machine` 读起来像在要一个文件。旧名不再受理，但**报错会说出新名字**
    （`unknown option "--machine" — renamed to --device`）——「你打错了」与「它改名了」
    指向的处置不同，一句 `unknown option` 把两者说成一样。
    v1.4 `--machine`（当时的名字）收**装置名**：`fy data fetch --machine east` 解析走与其它条目同一条
    facts 搜索路径（`--facts` > `$FY_FACTS_PATH` > 检出的 `facts/` > 自带的 `_facts/`），落到
    `facts/device/<名>/machine.yaml`。写死路径做不到「一处换语料」——漏改的那条命令行**照常
    成功**，用旧那份跑完不报错。清单路径仍先看且照收；带分隔符或带后缀的**不**退回按名字找，
    故打错的路径报「没有这个文件」，不报成「语料里没有这台机器」。闸子 `cli::data::tests`（6 条）。
    v1.3 记一处可观察的后果（实测）：imas-python 读回本层写的 IMAS netCDF 会对每个变量印
    「documentation differs from the DD」——我们不带 `documentation` 属性，而 DD 有正文；
    `nc_validate` 仍 PASS。抄 DD 的文字能消警告，而 L-4 的许可规则正禁止那样做。
    v1.2 新增裁定 **L-13（搬家表）** 并据此**关闭 G-10**：`limiter` / `vessel` 自 IDS 顶层落进
    `description_2d[0]`，三条判据（源在 · 目标有 · 源在 DD 里没有）保证幂等；搬家记进
    `DdReport.relocated` 并由命令行转述。实测同一份 EAST 源：`wall.h5` 3 548 → 71 344 字节。
    v1.1 新增缺口 G-10（实测 2026-09-04）：`wall` 转 IMAS 布局出空 IDS——源把 `limiter` / `vessel`
    放在顶层而 DD 的家在 `description_2d[]` 之下，归一化据实丢弃（有报告，不静默），但产物是空件。
    同一次导出 pf_active / tf / magnetics 内容齐全。
    v1.0 全文整理（用户「优化重写整个设计文档」，2026-09-04）。标题改为「中间层的数据
    半边」：这个 crate 2026-09-04 已定名 `fylite_runtime` 并定位为**中间层**（`FYL-DESIGN-16`
    N-1），本篇写的是它六项职责里的前两项——格式读写与多源装配；另外四项（计划与门、
    后端选择、命令行、伺服）在 `-16` 与 `-15`。改名的沿革收成一句；裁定 L-1..L-12 按号
    重排（原文 L-9 落在 L-12 之后）；「面」表按 2026-09-04 as-built 重写（Python 侧 `.h5`
    与 mdsip 在线路径已经由本层承载，两个零调用者的读者已删）；示例命令里的外部 A-Box
    路径中性化。缺口 G-5（wasm 目标）改为「随 `-16` W-1 落地」——它已从缺口变成裁定。
    · v0.2 按炮号与时间取 MDSplus 切片（L-10）；零依赖 YAML 子集读者直读 A-Box（L-11）；
    `machine.yaml` 摊成装配；结构数组按 `name` 对齐合并（L-12）；缺口 G-7 / G-8。
    · v0.1 初稿：从「mdsip 编解码 + g-file」长成完整的数据层；裁定 L-1..L-9。
---

:::{dropdown} 文档控制信息 (Document Control Information)
:name: doc-control-fylite-data-layer

| 字段 | 内容 |
| :--- | :--- |
| 文档标识 (Document ID) | `FYL-DESIGN-14` |
| 文档名称 (Title) | 中间层的数据半边：数据源 ↔ fyo (The Data Half of the Middle Layer — Data Sources ↔ fyo) |
| 短名 / Slug | `fylite-data-layer` |
| 版本 (Version) | v1.3 |
| 发布日期 (Date of Issue) | 2026-09-04 |
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
| 上游输入 (Upstream Inputs) | `FYL-SDD-01` DE-COMP-09（中间层）/ DE-COMP-02（内核只算数）· `FYL-DESIGN-16`（中间层的定位与命名）· `FYL-DESIGN-06`（内核仓归档；mdsip 只读客户端）· IMAS DD 4.1.1 结构 · imas-python `imas/backends/netcdf/` · IMAS-Core `src/hdf5/` |
| 批准 (Approval) | — |
| 取代关系 (Supersedes / Superseded by) | 承接 `FYL-DESIGN-06`（归档）的 mdsip 部分 |
:::

(fylite-data-layer-intro)=
# 数据半边 (The Data Half)

〔一句话〕**内核只算数，数据归中间层**：`rust/fylite_runtime/`（源码公开）把不同数据源
读成 fyo 文档、把 fyo 文档写成别的格式，合并多个数据源，并按一份 JSON-LD / YAML 装配
它们。物理一行没有。

〔本篇在中间层里的位置〕这个 crate 是四层里的**中间层**（`FYL-DESIGN-16` N-1，
2026-09-04 定名；此前叫 `fylite_data`，当日中途一度叫 `fylite_engine`，因与 Python 包
`fylite.engine` 撞词而再改）。它做六件事，本篇只写头两件：①格式读写与转换、②多源
装配。③计划合成与门、④内核的选择在 `FYL-DESIGN-16`；⑤命令行、⑥伺服在
`FYL-DESIGN-15`。★它与 `python/fylite/engine/` 是**共用一个词根的两个不同组件**：
真重叠只有四项（命令行解析——有意的两份 · 内核装载 · 计划→内核→记录 · g-file ↔
`fyo:equilibrium`），重心互不相交。

〔为什么〕`FYL-SDD-01` DE-COMP-02 与内核 `fyo.rs` 的抬头一起划了这条线：*the kernel
computes numbers; the hosts put them into documents*。2026-09-02 把 mdsip 从内核搬到本仓时，
这一层只有协议编解码与 g-file；本篇写它长成什么样，以及每一条选择的理由。

(fylite-data-layer-scope)=
# 范围 (Scope)

| 数据源 | 读 | 写 | 布局 | 模块 |
| :--- | :-: | :-: | :--- | :--- |
| MDSplus（mdsip） | ✓ | ✗ | 绑定表 → fyo；按时间开窗 | `mdsip` `mdsbind` |
| 装置 A-Box（YAML） | ✓ | ✗ | fyo | `yaml` |
| EFIT a-file | ✓ | ✗ | fyo | `afile` |
| EFIT g-file | ✓ | ✓ | fyo | `geqdsk` `eqdsk_fyo` |
| JSON / JSON-LD | ✓ | ✓ | fyo · IMAS DD | `json` `fyodoc` |
| HDF5 | ✓ | ✓ | fyo · IMAS | `hdf5` |
| netCDF | ✓ | ✓ | fyo · IMAS | `netcdf` |

「fyo 布局」＝本仓的文档（`@context` `@id` `@type` + DD 键名 + `fylite:` 本地词，
`python/fylite/fyo.py`）。「IMAS 布局」＝ imas-python / imas-core **原样读得回**的形。
多源合并（`document::Node::merge`）与装配（`assembly`）作用在同一棵树上。

〔已确立〕树类型 `document::Node`：`Null` · `Bool` · `Int` · `Float` · `Str` ·
`Array{shape, F64|I64|Str}` · `List` · `Map`（插入有序）。★它也是 `FYL-DESIGN-16` 扁平树
要跨过 C ABI 交给内核的那个类型——编码器 / 解码器落在本层，是这一层的第七件事，
本篇不展开。

(fylite-data-layer-decisions)=
# 裁定 L-1..L-12 (Decisions)

**L-1 一棵中立的树，每种格式只写两条路。** `document::Node` 居中；N 种格式是 2N 条转换
而不是 N²。合并与装配只在树上做一次。

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
1.6 MB，只有路径 / 种类 / 维数 / 单位 / 坐标——**DD 的文字一个字不抄**，fyo 本体仓的
CC BY-ND 规则），`ids_meta.rs` 是 `nc_metadata.py` 的逐条移植。表是提交进仓的生成物。

★★**这条许可裁定在读者那里是看得见的，记下来免得有人「修」它。** 实测 2026-09-04：
imas-python 读回本层写的 IMAS netCDF 时，对每一个变量各印一条
`WARNING Documentation of variable X differs from the DD`——因为我们的变量只带
`units` / `coordinates` / `_FillValue`，**根本没有 `documentation` 属性**，而 DD 那边有正文。
`nc_validate` 仍然 **PASS**，imas-python 也照常把整棵树读回来，所以这不是缺陷，是
「一个字不抄」在输出上的影子。**把 DD 的说明文字抄进来就能消掉这些警告，而那正是这条
规则禁止的事。**

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
`mdsbind::decompose`（A-Box 投影工具 `tools/abox-mds-bind.py::decompose` 的移植：由外到
内剥倍率、下标、动词、括号内下标）分解成「动词 + 节点路径 + 整数」才交给
`mdsip::Client::read`；分解不了的（下标读另一个节点、未知动词、`getenv(...)`）列在
失败里，不猜、不发。`fylite/mds-bind/1` 扁平表与 A-Box 的 `$source`/`$link` 文档都认。

**L-13 同一个量在 fyo 与 DD 里挂的地方不同时，按一张**表**搬家，不按规则猜。**
★★实测 2026-09-04：EAST 的 `wall` 文档把 `limiter` 与 `vessel` 挂在 IDS 顶层，而 DD 4.1.1
的家在 `wall/description_2d[]/` 之下。L-7 的归一化据实把顶层那两支当作「DD 不认的路径」
丢掉——**丢得是响的**（报告逐条点名），但产物是一份只剩 `ids_properties` 的空 `wall`。
**一份空的 IDS 比一个错误更坏：它看着像结果。**

搬家表（`fyodoc::RELOCATIONS`）逐条写明「哪个 IDS、文档里在哪、DD 里的家在哪」，
今天两条，都是 `wall`。每条搬之前核三件事：**源路径在文档里在**、**目标路径在 DD 里有**、
**源路径在 DD 里没有**——三条缺一即不搬。第三条是幂等的保证：一份已经是 DD 形的文档
再归一化一次不会被搬第二层（闸子里正着反着各判一次）。

★**为什么是表不是规则。**「顶层的键若在某个中间层下面找得到同名的就搬过去」听着通用，
实则是猜：DD 里同名而不同义的路径不止一处，猜错会把一支数据搬到一个**看着合理**的错
地方，而且照样不报错。表是有据的、可数的、可核的；规则不是。

★搬家进 `DdReport.relocated` 并由命令行转述（`relocated ["limiter -> description_2d/limiter", …]`）：
一支数据换了挂点，读者从产物上看不出它原来在哪，所以那句话必须由工具说出来。

**L-9 两个 C 库，特性门控，wasm 不带。** HDF5 的文件格式与 netCDF-4 的方言自己写一份
能与 imas-python 互读的实现是一个季度的活、且是第三实现；目标是逐字兼容，所以链
`libhdf5` / `libnetcdf`（`hdf5-metno` / `netcdf` crate），缺省动态链接系统库，
`--static` 从源码编进。`--no-default-features` 是 wasm 那档：g-file 与 JSON / YAML，
零依赖（`FYL-DESIGN-16` H-4 写明 wasm 上的中间层带什么）。

**L-10 时间选择在绑定层落成整数，切片在服务端做。** 请求里的时间（一个点、一个窗
`[t0, t1]`、一列点；`params.time` / `--time 4:5`）不是 TDI 表达式：`mdsbind` 先读节点的
时基（`dim_of(node[, axis])`，按 (树, 炮, 节点, 轴) 缓存——一炮里一个节点只过网一次），在
时基上查出下标，再以 `Index::Range{start, stop, step}` / `Index::At` 发出
`data(\X)[i0:i1:step]`——整条信号不过网，`mdsip::Client` 仍只认「动词 + 节点 + 整数」
（L-8 不动）。时间轴在哪：没有下标的是一维信号（第 0 轴）；恰有一个 `*` 且无
`{time_slice}` 的取那一位（EFIT 的 `\X[i,*]` → `dim_of(\X,1)`）；`time_slice/*/…` 的绑定按
IDS 根 `time` 上选出的下标展开成若干时间片（没有根 `time` 时退到该节点 `{time_slice}`
那一轴的 `dim_of`，并记一条说明）；其余读整条并记说明——不猜。收尾：各通道 `…/time`
相同 → `ids_properties/homogeneous_time = 1` 并补根 `time`，否则 0；`fylite:time_selection`
记下问的是什么。点不外推：窗里没有样本是失败，不是空数组。

**L-11 一个只认 A-Box 方言的 YAML 读者，零依赖。** 装置 A-Box（`machine.yaml`、
`providers/*.yaml`、`bind/mdsplus/*.yaml`、`static/legacy/*.yaml`）全是 PyYAML 写出的
YAML：块式映射与序列、三种标量写法、少量单行流式 `{}` / `[]`——没有锚点、别名、标签、
多文档。`yaml.rs`（约五百行）只认这些，不认的**报错**而不是猜；标量按 YAML 1.1 断型
（`0123` 是八进制、`yes` 是真——与 PyYAML 同），只在浮点上更宽（`2.2e6` / `140E9` 按数读，
PyYAML 按 YAML 1.1 读成字符串；A-Box 里有 6 处）。判据是对拍：`verify/yaml_gate.py`
拿 A-Box 的 47 份文件比 `fylite data dump --raw` 与 `yaml.safe_load`，逐叶子相同。
于是装配文档的 `file:` 源可以直接指 A-Box 的 YAML，装置清单 `machine.yaml` 可以摊成
装配（`assembly::from_manifest`：炮 → epoch，提供者 → 几何文件，绑定 → 绑定文档）——
Rust 侧不再等 Python 先投影成 JSON。★这正是 `FYL-DESIGN-16` K-8「装置自 A-Box 经
中间层进内核」的落点。

**L-12 结构数组按 `name` 对齐地合并。** 几何（`providers/magnetics/pcs.yaml`，按 `name`）
与测量（绑定文档，按 `id`）是两份不同来路的列表；合并时两边都带 `name` 的元素按值
对齐（次序不同也对得上），对不上的追加，任一边没有键的退回按下标——A-Box 的绑定
文档没有 `name` 而次序与几何一致，所以缺省 `merge_key: name` 对它无害。`select`
（`ids` / `ids/子树`）在合并与覆盖层之后挑选，语义键、`ids_properties`、`time`、
`fylite:*` 与元素的 `name` / `identifier` 总是留着。

(fylite-data-layer-faces)=
# 面 (Faces, as-built 2026-09-04)

| 面 | 在哪 | 给谁 |
| :--- | :--- | :--- |
| Rust API | `io::{detect, read, read_node, read_as, write, merge_paths}` · `assembly::{parse, assemble, assemble_file, from_manifest, select}` · `mdsbind::{parse_table, decompose, table_from_abox, …}` | 本仓的 Rust 宿主（命令行、伺服、`case.rs`） |
| C ABI | `c_api.rs` 的 31 个 `fylite_runtime_*`：`read` / `read_text` / `write` / `detect` · `bundle_*` · `doc_*` · `gfile_*` · `mds_*` · `assemble` / `fetch` · `case_*` | Python（`fylite.io.fydoc`） |
| 命令行 | `fylite data info / dump / convert / merge / assemble / fetch / tables`（Python 宿主逐字委托；`fylite data …` 是同一条，`FYL-DESIGN-15` C-8） | 人与脚本 |
| Python | `fylite.io.fydoc.{read, write, detect, assemble, fetch, Bundle}` | 本仓的 Python 宿主 |
| Python（经由） | `fylite.fyo.read` / `write` 的 `.h5` 分支、`appsession.to_hdf5`、`fylite.io.mds` 与 `io.est2` 的在线路径（`kernel.MdsSession`）——2026-09-04 起这些**不再各有一份**（h5py 走树、站点 `MDSplus` 包），都交给本层；`io.imas_h5` / `io.jetto_bin` 两个零调用者的读者同批删除 | 本仓的 Python 宿主 |

一个请求就是一份装配文档（JSON 或 YAML），或一条 `fetch`：

```text
fy data fetch --device east --ids magnetics \
              --shot 138569 --time 4:5 --host <mdsip 主机> -o east_138569_magnetics.json
```

= 清单里 `providers.magnetics.default`（`pcs`，几何 38 探针 / 35 磁通环）+
`bindings.mdsplus.ids.magnetics`（`magnetics_pcs.yaml`，`pcs_east` 树）→ 每个探针
`dim_of(\PCBPVnT)` 一次、`data(\PCBPVnT)[i0:i1]` 一次 → 一份 `fyo:magnetics`，
`b_field_pol_probe[n].field.{data, time}` 是 4～5 s 的切片，`position` 来自几何，
`fylite:assembly` 记炮号、时间窗与源。

取值路径 `"<ids>[_<occ>]/a/b/c"`：头一段是 IDS，其余是文档路径；不带索引的名字段落到
结构数组的第 0 个——与内核 `fyo.rs` 的 `@fyo-table` 同一条规则。★这条「按路径取」
只在中间层里走树；交给内核的是整份文档（`FYL-DESIGN-16` K-8），内核不收路径。

(fylite-data-layer-gaps)=
# 缺口 (Gaps)

| 编号 | 缺口 | 状态 |
| :--- | :--- | :--- |
| G-1 | 复数叶子（DD `CPX_*`）不写 IMAS 布局（拒绝而不是猜） | 开 |
| G-2 | netCDF 字符串变量不带 `_FillValue`（`netcdf` crate 没有公开的 `nc_def_var_fill` 字符串入口；imas-python 读法不变） | 开 |
| G-3 | 时间切片：读 MDSplus 按时间开窗已做（L-10）；文件侧 imas-core 的 `put_slice` / `get_slice` 不做，整份 put/get | 部分 |
| G-4 | a-file 的 X 点 / 打击点：DD 4.1.1 `boundary` 下无槽，只留在 `fylite:afile` 原始块 | 开 |
| G-5 | wasm 目标未在 CI 构建（本机无 `wasm32-unknown-unknown`）；`--no-default-features` 的原生构建是代理判据 | 已由缺口升为裁定：`FYL-DESIGN-16` H-4 / 分期 W-1 要构建 `fylite_runtime.wasm`，随之关 |
| G-6 | 活的 MDSplus 对拍：绑定表解析与时间开窗经照本宣科的传输判过（发出的 TDI 文本逐条核对），未对真服务器跑 | 开 |
| G-7 | 一列点落在多维节点上时沿新的第 0 轴堆叠（记说明）；`Points` 逐点各一次往返，长列表该改成一次区间读再本地挑 | 开 |
| G-8 | 装置清单 `machine.yaml` 是起步草稿；`from_manifest` 只看 `epochs` / `providers` / `bindings.mdsplus` 三段，清单变形要跟着改 | 开 |
| G-9 | 与 SpData 重叠语义（`$link` 分解、`merge_key`、时间开窗）的对齐代价未量（`FYL-DESIGN-16` D-1 / G-6：本层是 SpData 的一个 profile） | 开；`-16` 分期 P3 前先量 |
| ~~G-10~~ | ~~`wall` 转 IMAS 布局出的是一份空 IDS~~ | **已关（2026-09-04）**：新增 L-13 的搬家表，`limiter` / `vessel` 落进 `description_2d[0]`。实测同一份 EAST 源：`wall.h5` 3 548 → **71 344 字节**，限制器 64 点轮廓（r ∈ [1.331, 2.35] m）与真空室内外环各 40 点都在 DD 的路径上；闸子 `fyodoc::tests::wall_limiter_and_vessel_move_under_description_2d` |
