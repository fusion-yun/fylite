---
title: 内核 (The Kernel)
---

# 内核

物理与数值只有一个宿主：**一棵 Rust crate**（36 份源文件、约 6.4 万行、650 条 `#[test]`，
2026-09-02 实测）。它编成一份 C-ABI 共享库给 Python，编成三份 `.wasm` 给浏览器；两条
路出自同一个 `c_api.rs`。

无 Fortran、无 MPI、无 LAPACK、无任何系统数值库。crate 的依赖只有一个，且是可选的
（`rayon`，多线程特性）；`ldd` 的结果是 `libgcc_s` / `libm` / `libc` 加动态链接器。

:::{important} 这棵 crate 不在本仓
2026-09-01 仓一分为二：**内核源码在私有仓 `fylite_kernel`**（`rust/fylite/`），本仓拿到的是
它的**制品**——`libfylite_kernel.so`、三个 `.wasm`，以及由内核构建脚本生成的 `_abi.py` /
`version.js` / `fyo-interface.*`。制品**不入库**，打包发布时才装进来。所以本章写的路径
（`rust/fylite/src/*.rs`）在内核仓里解析；本仓自己的 Rust 源码树只有一棵，是**数据层**
（`rust/fylite_data/`，见本页末），它不做物理。
:::

## 模块地图

每个模块**实际实现**的方程、假设、参数域与数值算法，逐条带一手出处，在参考书的
[物理与数值](../physics/00-overview.md)十五章里；下表第三列是模块到章节的映射。

| 层 | 模块 | 详述 |
| :--- | :--- | :--- |
| 数值底座 | `kernels.rs` `linalg.rs` | [01 数值内核](../physics/01-numerics.md) |
| 平衡正解 / 反解 | `equilibrium.rs` · `inverse.rs` | [02](../physics/02-equilibrium.md) · [03](../physics/03-reconstruction.md) |
| 磁面、局域几何与归一 | `surfaces.rs` `geometry.rs` `mapping.rs` `bundle.rs` | [04 几何与归一](../physics/04-geometry.md) |
| 芯部输运、0-D | `transport.rs` · `zerod.rs` | [05](../physics/05-transport.md) · [06](../physics/06-zerod.md) |
| 新经典 | `neoclassical.rs` `dke.rs` | [07 新经典](../physics/07-neoclassical.md) |
| 湍流与代理 | `gyrofluid.rs` `closure_tables.rs` `flr_tables.rs` `nn.rs` `bgb.rs` | [08 湍流](../physics/08-turbulence.md) |
| 加热与电流驱动、源项 | `heating.rs` · `sources.rs` | [09](../physics/09-heating.md) · [10](../physics/10-sources.md) |
| 边缘、中性粒子与台基 | `edge.rs` `edge_tables.rs` `neutrals.rs` `pedestal.rs` `pedestal_tables.rs` | [11 边缘与台基](../physics/11-edge.md) |
| 电磁、演化、稳定性、控制 | `electromagnetics.rs` `evolution.rs` `stability.rs` `control.rs` | [12 电磁与控制](../physics/12-electromagnetics.md) |
| 放电设计、击穿 | `pulse.rs` `breakdown.rs` | [13 放电设计与击穿](../physics/13-pulse-breakdown.md) |
| 拟合与诊断 | `fitting.rs` `diagnostics.rs` | [14 拟合与诊断](../physics/14-diagnostics.md) |
| 文档层与场景（非物理） | `fyo.rs` `scenario.rs` | — |
| 唯一的 C 边界 | `c_api.rs` | — |

★`mdsip.rs` 曾在这张表里，**2026-09-02 起不在**：取数是宿主的活，它随数据面搬去了
本仓的数据层（`rust/fylite_data/`）。内核自此装置中立、格式中立——它算数，别人把数
放进文档。

Python 侧不复写其中任何一段离散化或闭式：装配、装置接线、编排、绘图与溯源在
`python/fylite`，物理在这里（`fylite.scenario` 连 `scipy` / `contourpy` 都不许 import，
这条由 `python/tests/test_scenario.py` 把门）。

## C-ABI 与装载

| | |
| :--- | :--- |
| 制品 | `python/fylite/_lib/libfylite_kernel.so`——**可重入、无全局态**，约 2.7 MB（`strip = "symbols"` 之后，2026-09-01 实测） |
| 入口 | 导出 **249 个** `fylite_rs_*` C 函数（2026-09-02 实测） |
| 构建 | **内核仓**的 `bash rust/build.sh`（单棵 cargo crate；`--no-install` 只编译）——它把制品与生成物装进本仓 |
| 分发 | **不入库**：打包时装进 wheel，随 `python/pyproject.toml` 的 `package-data` 走；**pip 不编译它** |
| 调用 | **进程内** ctypes，装载器即 `fylite.kernel`；`$FY_KERNEL_LIB` 覆盖随包路径 |

:::{note}
ABI 版本只有一个源头——`rust/fylite/src/c_api.rs` 的 `ABI_VERSION`——由 `build.sh`
**生成**进 `python/fylite/_abi.py` 与 `rust/wasm/abi.json`。装载器见到版本不符的库
**大声拒绝**，而不是拿不匹配的签名去调；两边手工保持一致的做法曾在一天之内漂了两次。
:::

每个 C 入口的 ctypes 签名就写在调用它的包装函数上方，`load()` 一次性登记；任何负返回码
抬成 `KernelError`，**不返回一个看着合理的数组**。

## WebAssembly

同一份 `c_api.rs` 按 cargo feature 另编三份（`bash rust/build.sh --wasm-check`）：

| 制品 | feature | 函数导出 | 大小 | 何时取 |
| :--- | :--- | ---: | ---: | :--- |
| `fylite_rs.wasm` | `core` | 234 | 869 KiB | 页面启动即取（平衡 / 重构 / 电路 / 0-D / 输运） |
| `fylite_tglf.wasm` | `tglf` | 12 | 391 KiB | 按需 |
| `fylite_dke.wasm` | `dke` | 11 | 121 KiB | 按需（NEO 漂移动理学） |

（导出数与尺寸为 2026-09-02 对当日构建的实测。）浏览器构建走 `--no-default-features`：
线程（`parallel`）不进——**页面本就没有套接字可开**，而结果与多线程档**逐位相同**
（每个元素独立计算、同一套算术）。页面加载 `app/assets/*.wasm`，与内核仓
`rust/wasm/dist/` 的同名产物逐字节相同；**三份都不入库**，站点发布与单文件可执行体
在构建时各自装入。Python 侧一份都不加载。制品尺寸、导出面与哈希底账见实测笔记
`docs/note/app-provenance.md`。

★这个目标**始终要能编过**，哪怕某一份并不发布：某个依赖引进 `std::fs` 或线程会立刻让它
变红，而那正是「单核双宿主」最先失守的地方。

## 移植线与冻结的答案

新经典（`neoclassical.rs` / `dke.rs`）、湍流（`gyrofluid.rs`）与磁面几何（`geometry.rs`）
是 [GACODE](https://github.com/gafusion/gacode) 的**白箱翻译**，不是独立实现；逐文件的出处、
上游版本与**有意不同**之处在仓根 `NOTICE`。

判它们的不是断言，是**库还在时录下的答案**：

| | |
| :--- | :--- |
| 位置 | `tests/data/oracle/`（`$FY_ORACLE_STORE` 可覆盖），**15 个入口目录、625 条记录、9.7 MB** |
| 分组 | EFIT 正解 297 · NEO 自举与漂移动理学 209 · 磁面几何 105 · TGLF 输入映射 14 |
| 布局 | `<入口>/<输入摘要 24 位十六进制>.json`，每条**连输入一并存**；构件（g-file 正文）内容寻址、整条流压缩为 `artifacts.xz` |
| 读者 | `python/fylite/_oracle.py`；`$FY_ORACLE`：`replay`（缺省）/ `record` |

:::{warning}
**未命中是错误，不是回退。** replay 模式下没录过的输入直接抛 `OracleMissing`，既不现算
也不返回近邻。这正是冻结 oracle 的全部价值：**它不能朝着自己要评判的东西漂移**。
:::

## 第二棵 crate：数据层（本仓，源码公开）

内核只算数，**取数与格式归数据层**——`rust/fylite_data/`，本仓唯一的 Rust 源码树。
它与内核相反：源码公开，因为这里是协议编解码与文件格式，不是物理 IP。物理一行没有。

| | |
| :--- | :--- |
| 读 | MDSplus（mdsip 只读客户端，按炮号与时间在服务端切片）· EFIT a-file / g-file · JSON(-LD) · YAML 子集（fydata 的 A-Box）· HDF5 · netCDF |
| 写 | JSON(-LD) · g-file · HDF5 · netCDF，各带 **fyo** 与 **IMAS DD** 两种布局（IMAS 布局以 imas-python / imas-core 读得回为判据） |
| 制品 | `libfylite_data.so`（Python 经 ctypes 取，`fylite.io.fydoc`）· `fylite-app`（**唯一的可执行文件**，内嵌整个 `app/`，并承载 `app` / `data` / `case` 三条命令） |
| 命令行 | `src/cli/`——由 `python/fylite/_cli.json` **编译期**建出；与 Python 的 `fylite` 同一份定义（[API 速查](api.md)的 CLI 一节） |
| 设计正本 | `FYL-DESIGN-14`（数据层）· `FYL-DESIGN-15`（发布形态与统一命令行） |

★**浏览器那份不含 mdsip**：页面打不开裸 TCP，把它编进去只会增加体积与误解。

## 七棵 Fortran 树去哪了

早先的文档记的是七棵各自 `build.sh` 的 Fortran 源树（`efit` / `geo` / `neo` / `tglf` /
`gray` / `pencil` / `torbeam`）与它们编出的 `libefit.so` / `libgeo.so` / `libneo.so` /
`libtglf.so`。**本仓没有 `fortran/` 目录，`_lib/` 里只有一个 `libfylite_kernel.so`**：EFIT 一系
按 `NOTICE` 3.1 移除，三个 GACODE 绑定库按 3.2 移除，物理改由上表的 Rust 移植承担。
GRAY 移植另因许可受限**暂停**（clean-room 纪律：不读其物理源码）。原委与所留下的东西见
用户指南 `docs/guide/install.md` 的
「Fortran 制品去哪了」一节（`fortran-artifacts`）。★这里给的是**路径而不是链接**：
指南与参考自 2026-09-01 起是两本各自构建的书，跨书的锚点引用解析不了——一个解析不了的
`#anchor` 在页面上是一段不跳转的文字，看不出坏了。

★那一页的教训留下一条，与语言无关：**判一个移植对不对，要量一个有理论定值的中间量**
——vendored 内核最贵的失败型不是报错，是**静默出零**或在错单位下仍然线性、伪装成
「归一化亏损」。
