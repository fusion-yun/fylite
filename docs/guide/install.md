---
title: 安装与环境 (Install & Environment)
---

# 安装与环境

## 依赖姿态

**硬依赖只有 `numpy`。** 其余全部可选，且缺失时**抛错并给出安装行**，不静默降级：

| extra | 内容 | 何时需要 |
| :--- | :--- | :--- |
| `yaml` | `PyYAML` | YAML 形式的输入/装置文件 |
| `plot` | `matplotlib` | `fylite.plot` 磁面图渲染、`fylite plot` 子命令 |
| `mds` | （站点安装的 `MDSplus`，不在 PyPI） | 从 MDSplus 树取数 |

```bash
cd python && pip install -e '.[plot,yaml]'    # 或按需
```

## 分发面（alpha 期）

★包里带的是**预编译**的内核（`_lib/libfylite_kernel.so`），pip 不在装的时候编译它。
所以轮带**平台 tag**，alpha 期的公开面是 **Linux x86-64 一个**：别的平台在装的
时候就被拒绝，而不是装完之后在第一次内核调用时报错。

```bash
bash tools/build-wheel.sh          # 出轮：平台 tag 由 .so 自己的 glibc 下限推出
```

该脚本只出 wheel、不出 sdist——sdist 会让别的平台的 pip 拿去「构建」，得到的仍是
这一份 Linux `.so`，正是 tag 要挡住的那件事。浏览器一路（`app/`）跑的是同一个内核
的 WebAssembly 版本，**没有平台限制**。

发行版本只有一处来源：仓根的 `VERSION`（`pyproject.toml` 经符号链接动态读取）。
内核版本与 ABI 号是另外两个量，分别由 `fylite.kernel.ABI_VERSION` 与站点的
`FyVersion` 报出。

★`pyproject.toml` 在 `python/` 而不在仓根，故安装要先进那一层：仓根不是一个 Python
工程，它同时是一棵 Rust crate、一个静态站点、一本 MyST 书和一个包，四者里只有一个由
pip 构建。

交互面板不再随 Python 包提供：放电设计与动理学重构的交互页在浏览器端（`app/`），
Python 侧只保留内核、装配层与绘图。

## 免安装运行

唯一的二进制是**预编译入仓**的，硬依赖又只有 numpy，故不装也能跑：

```bash
PYTHONPATH=python python -c "import fylite; print(fylite.__version__)"
```

需要装置的入口另需一个装置目录——本仓的 EAST 卷宗在 `machine_desc/east/`（见 `machine_desc/README.md`）：

```bash
export FYLITE_DEVICE_DIR=$PWD/machine_desc/east
```

★不设它不会静默降级：`fylite.device` 抛 `MachineDataMissing` 并当场说明缺的是什么。
不需要机器的那一半（内核、0D、输运步、局域 TGLF/NEO、剖面拟合）零配置即可用。

## 唯一的共享库

| | |
| :--- | :--- |
| 文件 | `python/fylite/_lib/libfylite_kernel.so`——**C-ABI cdylib，可重入、无全局态** |
| 来源 | `bash rust/build.sh`，单棵 cargo crate（`rust/fylite/`）；无 MPI |
| 分发 | 预编译入仓，由 `python/pyproject.toml` 的 `package-data` 随轮子走；**pip 不编译它** |
| 系统库 | `ldd` 只有 `libgcc_s.so.1`、`libm.so.6`、`libc.so.6` 加动态链接器——**没有 gfortran，没有 lapack/blas** |
| 调用 | **进程内** ctypes，装载器即 `fylite.kernel`；`$FY_RUST_LIB` 覆盖随包路径 |

:::{note}
ABI 版本只有一个源头——`rust/fylite/src/c_api.rs` 的 `ABI_VERSION`——由 `build.sh`
**生成**进 `python/fylite/_abi.py`；装载器见到版本不符的库**大声拒绝**，而不是拿不匹配
的签名去调。两边手工保持一致的做法曾在一天之内漂了两次。
:::

重建需要 Rust 工具链：

```bash
bash rust/build.sh                # -> rust/fylite/target/release/libfylite_kernel.so，并装进 python/fylite/_lib/
bash rust/build.sh --no-install   # 只编译，不安装
```

## WebAssembly 制品

同一份 `c_api.rs` 另编一套 wasm：

```bash
bash rust/build.sh --wasm-check
```

产物出 `rust/wasm/dist/`，按 cargo feature 拆成**三份**：`fylite_rs.wasm`（core——平衡 /
重构 / 电路 / 0D，页面启动即取）、`fylite_tglf.wasm` 与 `fylite_dke.wasm`（NEO 漂移动理学），
后两份**按需取**。页面实际加载的是入仓的同名副本 `app/assets/*.wasm`（与 `dist/` 逐字节
相同）；Python 侧一份都不加载。

★这个目标**始终要能编过**，哪怕某一份并不发布：某个依赖引进 `std::fs` 或线程会立刻让它
变红，而那正是"单核双宿主"最先失守的地方。制品的尺寸、导出面与哈希底账见
实测笔记 `docs/note/app-provenance.md`。

(fortran-artifacts)=
## Fortran 制品去哪了

早先的文档、论文与 changelog 会提到随包的 `libefit.so` / `libneo.so` / `libgeo.so` /
`libtglf.so`、Green 表生成器 `efund_east`、`_data/green*/` 表集与 `_data/ldd-manifest.txt`。
**它们不在本分发里**：EFIT 一系（求解器、efund 生成器、表，以及它们的**全部录得输出**）
按 LICENSE 3.1 整体移除；`libneo` / `libgeo` / `libtglf` 三个 GACODE 绑定库连同围着它们写
的 ctypes 绑定按 3.2 移除。两个编号的确切所指由仓根 `NOTICE` 自己定义（那份 licence 文件
本身是纯 Apache-2.0，并无此二节——`NOTICE` 把散在源码里的二十七处引用一次性定清）。
`python/fylite/_bin/`、`_data/` 与 `fortran/` 三个目录**都不存在**，`_lib/` 里只有一个
`libfylite_kernel.so`。

留下来的不是库，是**答案**：

| | |
| :--- | :--- |
| 位置 | `tests/data/oracle/`（`$FY_ORACLE_STORE` 可覆盖），**625 条记录、15 个入口目录、9.7 MB** |
| 读者 | `python/fylite/_oracle.py`；布局 `<入口>/<输入摘要 24 位十六进制>.json` |
| 内容 | 每条**连输入一并存**——故可重新推导，读的人也看得出当初问的是哪道题 |
| 构件 | g-file 正文这类大件内容寻址、整条流压缩为该入口的 `artifacts.xz`（实测 5.9×；逐条压只有 3.9×） |
| 模式 | `$FY_ORACLE`：`replay`（缺省）/ `record`（要有参考实现，见下） |

按入口分：**EFIT 正解 297 条**、NEO 自举与漂移动理学（`neo.*` / `neo_analytic*` /
`dke_*`）209 条、磁面几何（`geo.flux_surface`）105 条、TGLF 输入映射
（`tglf.run_inputs`）14 条。
★它不在 `python/tests/` 下，也不进轮子：`fylite.run.forward_equilibrium`、
`scenario.model.neoclassical` 与 `gyrofluid` 三个**已发布**模块在运行期读它，放在测试树
里就意味着包只在带测试的检出里能用。store 自身的规矩见
[`tests/data/oracle/README.md`](https://github.com/fusion-yun/fylite/blob/develop/tests/data/oracle/README.md)。

:::{important}
**`efit.forward_equilibrium` 有 297 条录得答案，但没有求解器。** `fylite.run.forward_equilibrium`
是这些答案的**读取器**：录过的输入照旧算得出来（`tests/test_shape.py` 就跑在这条路上），
没录过的抛 `OracleMissing`。★答案是经 `fylite._port`（`$FY_ORACLE_PORT` 指向的
`fylite_port` 检出，另一套许可下的另一个仓）在子进程里录下的——**跨过来的是 JSON，落进本仓的
是冻结的答案**；不设那个变量时 `record` 模式抛错，含义与从前一致。

要做一次**新的**自由边界正解，走 `fylite.kernel.gs_free_solve`：本仓自己的 GS，在
`rust/fylite/src/equilibrium.rs` / `inverse.rs`。
:::

:::{warning}
**未命中是错误，不是回退。** replay 模式下没录过的输入直接抛 `OracleMissing`，既不现算
也不返回近邻。这正是冻结 oracle 的全部价值：**它不能朝着自己要评判的东西漂移**。一个会
悄悄退化成近似查找的 store，等于拿移植版去评判移植版自己。
:::
