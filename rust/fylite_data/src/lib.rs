//! fylite 的数据层 —— **取数与格式，不做物理**。
//!
//! ★★为什么它不在内核里。内核那本自己写着：*the kernel computes numbers; the
//! hosts put them into documents*（`fyo.rs`），并且点名装置描述是「内核唯一不读
//! 的文档」，理由是「在算数的那层做宿主已经在做的活」（FYL-SDD-01 DE-COMP-02）。
//! 一个网络协议编解码器按同一条判据也是宿主的活。2026-09-02 实测下来，内核库
//! 除了 `mdsip` 之外**已经**是装置中立、格式中立的：装置名在代码里零处（130 处
//! 提及全在注释与测试），没有任何文件格式解析器。所以搬走 `mdsip` 之后，那条
//! 判据在内核里就没有例外了。
//!
//! ★★为什么源码公开，而内核不公开。这里是**协议与格式**，不是物理 IP。公开它
//! 既不损内核那条私有边界，又让「一份实现」成立：Python 与桌面查看器用同一份，
//! 不再各写一个。本仓从前有两份 g-file 读入（`python/fylite/io/geqdsk.py` 752 行
//! 与 `app/assets/geqdsk.js` 286 行）与两份 mdsip 客户端——那正是这一层要收掉的。
//!
//! ## 它做什么（2026-09-02 起）
//!
//! **不同数据源 ↔ fyo 文档**，以及多个数据源的合并与装配。一棵中立的文档树
//! （[`document`]）居中，每种格式只写「到它」与「从它」：
//!
//! | 数据源 | 读 | 写 | 布局 |
//! | --- | :-: | :-: | --- |
//! | MDSplus（mdsip，[`mdsip`] + [`mdsbind`]） | ✓ | ✗（只读由构造保证） | 绑定表 → fyo；按炮号与时间（点 / 窗 / 点列）在服务端切片 |
//! | fydata 的 A-Box（YAML，[`yaml`]） | ✓ | ✗ | fyo（装置几何、绑定文档、装置清单） |
//! | EFIT a-file（[`afile`]） | ✓ | ✗ | fyo |
//! | EFIT g-file（[`geqdsk`] + [`eqdsk_fyo`]） | ✓ | ✓ | fyo |
//! | JSON / JSON-LD（[`json`]） | ✓ | ✓ | fyo · IMAS DD |
//! | HDF5（[`hdf5`]） | ✓ | ✓ | fyo · IMAS（imas-core 5 的 HDF5 后端） |
//! | netCDF（[`netcdf`]） | ✓ | ✓ | fyo · IMAS（imas-python 的 netCDF 后端） |
//!
//! 「fyo 布局」是本仓的文档（JSON-LD 语义键 + DD 键名 + `fylite:` 本地词，
//! [`fyodoc`]）；「IMAS 布局」是 imas-python / imas-core **原样读得回**的形——
//! 判据是 `verify/imas_roundtrip.py`：数据层写的它们读、它们写的数据层读，逐叶子相同。
//! 两种 IMAS 布局都要 DD 的结构（种类、维数、坐标声明），那张表由
//! `tools/dd-ids-table.py` 从 DD 的 `IDSDef.xml` 生成进 [`ids_tables`]、由 [`ids_meta`]
//! 读——netCDF 的维度名推导是 imas-python `nc_metadata.py` 的逐条移植。
//!
//! 文件类型**看内容识别**（[`detect`]），[`io`] 统一分派，[`assembly`] 按一份
//! JSON-LD / YAML 装配多个数据源（或从 fydata 的装置清单 `machine.yaml` 摊出
//! 「几何 + 绑定」，`fetch`），[`c_api`] 把这些交给 Python（`fylite.io.fydoc`），
//! `src/bin/data` 是命令行 `fylite-data`。
//!
//! ## 制品，一份源
//!
//! | 制品 | 给谁 | 带 mdsip 吗 | 带 HDF5 / netCDF 吗 |
//! | --- | --- | --- | --- |
//! | `libfylite_data.so` | Python（`ctypes`，与内核库同一种取法） | 是 | 是（链 C 库） |
//! | `fylite-data` | 命令行 | 是 | 是 |
//! | `fylite-app` | 单文件桌面查看器 | 是 | 是 |
//! | `fylite_data.wasm` | 浏览器 | **否**（用户裁定；浏览器打不开裸 TCP） | **否**（`--no-default-features`：g-file 与 JSON） |

#![allow(dead_code)]

//: ★g-file 是**格式**，不是传输：它在 wasm 上也成立，所以不挂在 `mdsip` 特性下。
//: 这也正是数据层 wasm 将来装的东西——浏览器不取 MDSplus，但它要读 g-file。
pub mod geqdsk;

//: 文档树与 JSON(-LD) 编解码：零依赖，wasm 同样成立。
pub mod document;
pub mod json;
pub mod yaml;

//: IMAS DD 的结构表（生成物）与它的读者——两种 IMAS 布局的元数据。
#[allow(clippy::all)]
pub mod ids_tables;
pub mod ids_meta;

//: 内核的 fyo 面（生成物：`fylite_kernel/rust/build.sh`）：槽位 ↔ 文档路径、
//: 场景条目的块、条目次序——数据层把内核按路径交回的场翻成文档时走的那张表。
pub mod fyo_interface;

//: SHA-256：`spo:Concretization` 的校验和（零依赖，见文件抬头）。
pub mod checksum;

//: fyo 文档的约定，与两种文本格式到它的转换（wasm 同样成立）。
pub mod fyodoc;
pub mod eqdsk_fyo;
pub mod afile;
pub mod tensor;
pub mod detect;
pub mod io;

#[cfg(feature = "hdf5")]
pub mod hdf5;
#[cfg(feature = "netcdf")]
pub mod netcdf;

#[cfg(feature = "mdsip")]
pub mod mdsip;

#[cfg(feature = "mdsip")]
pub mod c_api;

//: ★★一个 CASE 的输入 / 输出半边（FYL-REPORT-06 一份结构进、一份结构出）：
//: 读并组合 `fyo:ScenarioSpecification`，经数据层解析绑定的输入，把**结构**交给
//: 内核（`fylite_rs_case_*`，运行期 dlopen——内核源码不公开，本 crate 公开，
//: 不能以 crate 依赖相连），再把运行写回一份 `spo:ComputationRecord` 与产出的
//: fyo 数据集。原生专用：要 dlopen、要读盘。
#[cfg(not(target_arch = "wasm32"))]
pub mod kernel;
//: the JSON door: one plan text in, one record text out (`fylite_data_case_json`)
#[cfg(not(target_arch = "wasm32"))]
pub mod case_api;
#[cfg(not(target_arch = "wasm32"))]
pub mod case;

//: MDSplus 绑定表与多源装配：都要走 mdsip 客户端，所以与它同一个特性门。
#[cfg(feature = "mdsip")]
pub mod mdsbind;
#[cfg(feature = "mdsip")]
pub mod assembly;
