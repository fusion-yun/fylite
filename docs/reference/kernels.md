---
title: 内核 (The Kernel)
---

# 内核

物理与数值只有一个宿主：**一棵 Rust crate**（`rust/fylite/`，30 份源文件、约 5.3 万行、
558 条 `#[test]`）。它编成一份 C-ABI 共享库给 Python，编成三份 `.wasm` 给浏览器；两条
路出自同一个 `c_api.rs`。

无 Fortran、无 MPI、无 LAPACK、无任何系统数值库。crate 的依赖只有一个，且是可选的
（`rayon`，多线程特性）；`ldd` 的结果是 `libgcc_s` / `libm` / `libc` 加动态链接器。

## 模块地图

| 层 | 模块 |
| :--- | :--- |
| 数值底座、电磁 | `kernels.rs` `linalg.rs` `electromagnetics.rs` |
| 平衡（正解 / 反解）与磁面 | `equilibrium.rs` `inverse.rs` `surfaces.rs` `geometry.rs` |
| 输运、0-D、演化、源项 | `transport.rs` `zerod.rs` `evolution.rs` `sources.rs` `heating.rs` |
| 新经典、湍流与闭包表 | `neoclassical.rs` `dke.rs` `gyrofluid.rs` `closure_tables.rs` `flr_tables.rs` |
| 稳定性、控制、脉冲、击穿 | `stability.rs` `control.rs` `pulse.rs` `breakdown.rs` |
| 拟合、诊断、剖面归一 | `fitting.rs` `diagnostics.rs` `mapping.rs` |
| 文档层、场景、数据面 | `fyo.rs` `scenario.rs` `bundle.rs` `mdsip.rs` |
| 唯一的 C 边界 | `c_api.rs` |

Python 侧不复写其中任何一段离散化或闭式：装配、装置接线、编排、绘图与溯源在
`python/fylite`，物理在这里（`fylite.scenario` 连 `scipy` / `contourpy` 都不许 import，
这条由 `python/tests/test_scenario.py` 把门）。

## C-ABI 与装载

| | |
| :--- | :--- |
| 制品 | `python/fylite/_lib/libfylite_kernel.so`——**可重入、无全局态**，2.8 MB |
| 入口 | 导出 **216 个** `fylite_rs_*` C 函数 |
| 构建 | `bash rust/build.sh`（单棵 cargo crate；`--no-install` 只编译） |
| 分发 | 预编译入仓，随 `python/pyproject.toml` 的 `package-data` 走；**pip 不编译它** |
| 调用 | **进程内** ctypes，装载器即 `fylite.kernel`；`$FY_RUST_LIB` 覆盖随包路径 |

:::{note}
ABI 版本只有一个源头——`rust/fylite/src/c_api.rs` 的 `ABI_VERSION`——由 `build.sh`
**生成**进 `python/fylite/_abi.py` 与 `rust/wasm/abi.json`。装载器见到版本不符的库
**大声拒绝**，而不是拿不匹配的签名去调；两边手工保持一致的做法曾在一天之内漂了两次。
:::

每个 C 入口的 ctypes 签名就写在调用它的包装函数上方，`load()` 一次性登记；任何负返回码
抬成 `KernelError`，**不返回一个看着合理的数组**。

## WebAssembly

同一份 `c_api.rs` 按 cargo feature 另编三份（`bash rust/build.sh --wasm-check`）：

| 制品 | feature | 函数导出 | 何时取 |
| :--- | :--- | ---: | :--- |
| `fylite_rs.wasm` | `core` | 201 | 页面启动即取（平衡 / 重构 / 电路 / 0-D / 输运） |
| `fylite_tglf.wasm` | `tglf` | 12 | 按需 |
| `fylite_dke.wasm` | `dke` | 11 | 按需（NEO 漂移动理学） |

浏览器构建走 `--no-default-features`：线程（`parallel`）与装置数据面（`mdsip`）都不进
——**页面没有套接字可开**，而结果与多线程档**逐位相同**（每个元素独立计算、同一套算术）。
页面加载的是入仓副本 `app/assets/*.wasm`，与 `rust/wasm/dist/` 逐字节相同；Python 侧一份
都不加载。制品尺寸、导出面与哈希底账见实测笔记 `docs/note/app-provenance.md`。

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
