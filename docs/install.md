---
title: 安装与环境 (Install & Environment)
---

# 安装与环境

## 依赖姿态

**硬依赖只有 `numpy`。** 其余全部可选，且缺失时**抛错并给出安装行**，不静默降级：

| extra | 内容 | 何时需要 |
| :--- | :--- | :--- |
| `yaml` | `PyYAML` | YAML 形式的输入/装置文件 |
| `plot` | `matplotlib` | `fylite.plot` 磁面图渲染 |
| `hdf5` | `h5py` | 只有 est2 离线转储（`io.est2.measurements_from_est2_hdf5`）还读它；fyo 文档的 `.h5` 走中间层，不需要 |

★**从 MDSplus 取数不需要任何 extra**：mdsip 客户端在中间层
`libfylite.so` 里，`io.mds` / `io.est2` 的在线路径经它取数，不依赖站点的 `MDSplus`
python 包。

```bash
cd python && pip install -e '.[plot,yaml]'    # 或按需
```

## 分发面（alpha 期）

fylite 以**三种形态**到达使用者，三者装的是同一份页面、同一版内核制品。
下表第二、三行是同一份字节的两种伺服方式——静态站点没有服务端组件，动态是同一份页面由
本机进程伺服并多答一组只读 `/api/*`：

| 形态 | 给谁 | 怎么得到 | 计算在哪 |
| :--- | :--- | :--- | :--- |
| **单一可执行文件** `fy` | 离线、或没有 Python 的人（尤其 Windows） | `bash tools/build-app-exe.sh`；双击即开浏览器 | 页面里的 wasm；`case` 子命令用原生内核 |
| **静态网页** | 联网的人，零安装 | `bash tools/build-site.sh` 出一个目录，放到任何静态主机 | 页面里的 wasm，加载后离线可用 |
| **动态网页** | 要读 MDSplus 的人 | 同一份页面由 `fy`（= `fy app`）伺服，多答 `/api/*` | 页面里的 wasm |
| **Python 包**（wheel） | 写脚本、LLM 宿主、集成方 | `bash tools/build-wheel.sh` | 原生内核 |

命令行来自同一个定义文件 `python/fylite/_cli.json`，而**可执行文件只有一个**：`fy`
（`app` / `data` / `case`）。★**wheel 不带可执行文件、Python 侧也没有
命令行**：装上包得到的是一个库，`fy` 由 `bash rust/build.sh --exe` 出、装到 `$PATH` 上。

★包里带的是**预编译**的 `_lib/libfylite.so`（内核 + 中间层一个库），pip 不在装的时候编译它。
所以轮带**平台 tag**，alpha 期的公开面是 **Linux x86-64 一个**：别的平台在装的
时候就被拒绝，而不是装完之后在第一次内核调用时报错。

```bash
bash tools/build-wheel.sh          # 出轮：平台 tag 由 .so 自己的 glibc 下限推出
```

该脚本只出 wheel、不出 sdist——sdist 会让别的平台的 pip 拿去「构建」，得到的仍是
这一份 Linux `.so`，正是 tag 要挡住的那件事。浏览器一路（`ui/`）跑的是同一个内核
的 WebAssembly 版本，**没有平台限制**。

发行版本只有一处来源：仓根的 `VERSION`（`pyproject.toml` 经符号链接动态读取）。
内核版本与 ABI 号是另外两个量，分别由 `fylite.kernel.ABI_VERSION` 与站点的
`FyVersion` 报出。

★`pyproject.toml` 在 `python/` 而不在仓根，故安装要先进那一层：仓根不是一个 Python
工程，它同时是一棵 Rust crate、一个静态站点、一本 MyST 书和一个包，四者里只有一个由
pip 构建。

交互面板不随 Python 包提供：放电设计与动理学重构的交互页在浏览器端（`ui/`），
Python 侧只保留内核、装配层与绘图。

## 免安装运行

唯一的二进制是**预编译入仓**的，硬依赖又只有 numpy，故不装也能跑：

```bash
PYTHONPATH=python python -c "import fylite; print(fylite.__version__)"
```

需要装置的入口另需一个**装置目录**。

:::{important}
**本仓没有 `machine_desc/`**——不是「不进版本库」，是这个目录**不存在**。
一份装置牌若同时在仓里和 A-Box 里，两个真值源里错的那个不会报错，它只会让某台机器安静地
用上另一份描述。所以牌的真值源只有一个：私有 `fydata` / `fydoc` 仓的 A-Box
（`abox/device/tokamak/<id>/`）。

装置目录由你自己**在任意位置**生成，再让 `$FYLITE_DEVICE_DIR` 指过去：

```bash
python tools/abox-to-machine-desc.py --source <fydata 或 fydoc 检出> --list
python tools/abox-to-machine-desc.py --source <检出> -o ~/fylite-decks --all
export FYLITE_DEVICE_DIR=~/fylite-decks/iter
```

★★**拖回来不是等价替换。** 实测：拖回的 ITER 牌**没有** `pf_active/supply` 供电条目，于是
`scenario.design.pulse.channel_limits` 会按路径报错；壁面轮廓的写法也从 `points` 换成
`r` / `z` 两个数组。拖回之后要复核读它的那几处——见[放电设计](../examples/design/design.md)那一章
里怎么显式给限值。

★★**EAST 那张牌拖不回来。** 它是**手工维护**的，且严格富于上游（est2 79 探针基底、
拟合控制块、被动集、电源参数、EFIT deck 件都不是 A-Box 里的东西），工具因此拒绝生成它。
它只在**内核仓的历史**里：

```bash
git -C <fylite_kernel 检出> archive b4dce77^ machine_desc/east | tar -x -C ~/fylite-decks --strip-components=1
export FYLITE_DEVICE_DIR=~/fylite-decks/east
```

★A-Box 里**有** EAST 的实验切片（`abox/experiment/east/137985/slice_*.fyo.jsonld`），
但那是**另一次约化**：实测同一时刻的 I_p 为 400 940 A，而那张手工牌里是 393 460 A（差 1.9 %），
反演在它上面不收敛（内核 −105100）。**它不是那份算例文档的替代品**，见
[诊断分析：平衡反演](../examples/reconstruction/reconstruction.md)。
:::

```bash
export FYLITE_DEVICE_DIR=~/fylite-decks/east         # 或 …/iter
```

★不设它不会静默降级：`fylite.device` 抛 `MachineDataMissing` 并当场说明缺的是什么。
不需要机器的那一半（内核、0D、输运步、局域 TGLF/NEO、剖面拟合）零配置即可用。

## 一个共享库 `libfylite.so`

★★★**2026-09-16 起 `_lib/` 里只有一个 `.so`**（用户裁定）。内核仓从此**只出静态链接库**
（内核检出 `dist/kernel-lib/libfylite_kernel.a`），本仓的 `rust/build.sh` 把它与中间层
`fylite_runtime` 链成同一个动态库；从前的 `libfylite_kernel.so` /
`libfylite_kernel_ext.so` / `libfylite_runtime.so` 三份没有了。

| | `libfylite.so` |
| :--- | :--- |
| 文件 | `_lib/libfylite.so.<版本>`，加 `.so.<主版本>` 与 `.so` 两级符号链接（Linux 惯例） |
| 里面有什么 | **内核**（`fylite_rs_*` 57 个 + `fylite_ext_*` 2 个：GS 正逆解、磁面、输运核、NEO / TGLF）与**中间层**（`fylite_runtime_*` 41 个：mdsip、g/a-file、HDF5 / netCDF、计划→内核→记录） |
| 源码在哪 | 内核在**私有仓 `fylite_kernel`**（本仓不带内核源码，只收它编好的 `.a`）；中间层在本仓 `rust/fylite_runtime/`，**源码公开** |
| 谁构建 | 本仓 `bash rust/build.sh`（先在内核仓跑它的 `rust/build.sh`，归档落在**内核检出自己的** `dist/kernel-lib/`；本仓按 `$FYLITE_KERNEL` 去取。★2026-09-20 用户裁定「不留 rust/kernel-lib」：内核不再往本仓推副本，本仓也没有回退副本——一条永远可能陈旧的路径比没有更坏） |
| 系统库 | `libhdf5` 与 `libnetcdf`（`--static` 可从源码编进），加 `libgcc_s` / `libm` / `libc`。★这是合库的代价：从前光要内核的读者不必装这两个 C 库，今天要装——或者用 `--static` 出一份自带的 |
| 覆盖 | `$FY_KERNEL_LIB`（内核面）· `$FY_RUNTIME_LIB`（中间层面），两个都指同一个文件 |

它是 **C-ABI cdylib、可重入、无全局态**，由 **进程内 ctypes** 调用（装载器
`fylite.kernel` 与 `fylite.io.fydoc` 各取自己那一面），**预编译入仓**并由
`python/pyproject.toml` 的 `package-data` 随轮子走——**pip 不编译它**。
★两代并存时新名字优先，旧的三个名字仍然认得（`fylite/_paths.py::_lib`），
所以一份还没重建的检出不会在 import 时死掉。

:::{note}
ABI 版本只有一个源头——内核的 `c_api.rs`——由内核仓的 `build.sh` **生成**进
`python/fylite/_abi.py`；装载器见到版本不符的库**大声拒绝**，而不是拿不匹配的签名去调。
:::

重建数据层需要 Rust 工具链（内核要另一个检出）：

```bash
bash rust/build.sh                # -> python/fylite/_lib/libfylite.so（内核 + 中间层）
bash rust/build.sh --exe          # 另建那个可执行文件 fylite -> python/fylite/_bin/
bash rust/build.sh --no-install   # 只编译，不安装
bash rust/build.sh --static       # HDF5 / netCDF 从源码静态编进（给没装那两个 C 库的机器）
```

## WebAssembly 制品

浏览器端跑的是内核的 wasm 版本，都在 `ui/assets/`。★**DKE 与 TGLF
合为一份扩展**；两份内核 wasm 的名字与导出面都没动，变的是**谁链出它们**——
2026-09-16 起由本仓的空壳包 `rust/fylite_kernel_wasm/` 链内核检出的
`dist/kernel-lib/libfylite_kernel-wasm32.a`（同一份归档，两个导出面）：

| 文件 | 出自 | 内容 | 何时取 |
| :--- | :--- | :--- | :--- |
| `fylite_rs.wasm` | 本仓 `rust/fylite_kernel_wasm`（`FY_WASM_FACE=core`） | core——平衡 / 重构 / 电路 / 0-D | 页面启动即取 |
| `fylite_kernel_ext.wasm` | 本仓 `rust/fylite_kernel_wasm`（`FY_WASM_FACE=ext`） | 扩展——TGLF 回旋朗道流体 + NEO 漂移动理学 | 按需 |
| `fylite_web.wasm` | 本仓 `rust/fylite_runtime` | 页面真读的那两扇门：装置事实与 g-file | 页面启动即取 |

★**没有单独的 `fylite_tglf.wasm` / `fylite_dke.wasm`**。
`ui/assets/fylite.js` 只有一个扩展载入口，取的是 `fylite_kernel_ext.wasm`。

★上表写的是**逻辑名**。磁盘上（以及站点上）真正的文件带版本后缀——
`fylite_rs.wasm.0.0.1`，加 `.wasm.0` 与 `.wasm` 两级符号链接，与 `_lib/` 里的三个
`.so` 同一条规矩（Linux 动态链接库的习惯）。页面按版本名取。

它们与原生 `.so` **出自同一份 `c_api.rs`**（内核仓），所以浏览器里得到的数与脚本里
得到的数是同一个数——这一点由跨宿主门在每次改动时校验（`fylite.engine.crosshost`），
不靠承诺。构建它们要内核检出；本仓只带入库的副本，Python 侧一份都不加载。

(fortran-artifacts)=
## 本分发不含的 Fortran 制品

论文与外部文档里会出现 `libefit.so` / `libneo.so` / `libgeo.so` /
`libtglf.so`、Green 表生成器 `efund_east`、`_data/green*/` 表集与 `_data/ldd-manifest.txt`。
**它们不在本分发里**：EFIT 一系（求解器、efund 生成器、表，以及它们的**全部录得输出**）
按 LICENSE 3.1 整体不含；`libneo` / `libgeo` / `libtglf` 三个 GACODE 绑定库连同围着它们写
的 ctypes 绑定按 3.2 不含。两个编号的确切所指由仓根 `NOTICE` 自己定义（那份 licence 文件
本身是纯 Apache-2.0，并无此二节——`NOTICE` 把散在源码里的二十七处引用一次性定清）。
`_data/` 与 `fortran/` 两个目录**都不存在**；`_lib/` 里今天是上面那两个 `.so`，
`python/fylite/_bin/` 里是那**一个**可执行文件（构建过才有，见上）。

★★**冻结的答案也不在这里**。oracle store——
录得的 EFIT 正解、NEO 与磁面几何的参考值——是这些求解器的**输出**，与求解器同罪，不随本分发；
也没有 `fylite._oracle`、`fylite._port` 与它们的四个环境变量（`$FY_ORACLE` / `$FY_ORACLE_STORE` /
`$FY_ORACLE_PORT` / `$KEFIT_REFERENCE_BUNDLE`）。

于是 `fylite.run.forward_equilibrium` 今天**对任何输入都抛 `KefitRunError`**，并说明
为什么：求解器不在本分发里，它的录得答案也不在。签名保留，是为了调用方在**调用处**
拿到一个有理由的失败，而不是在属性查找处拿一个 `NameError`。

★要做一次**新的**自由边界正解，走 `code/forward` 门（`fydoc.complete`）——那是本仓自己的 GS，
且它**说自己是谁**：把 EFIT 的名字安到另一个求解器的数上，比抛错更糟。

★公开 V&V 登记册里指向参考文件的那些指针，写的是 `$FYDOC_ORACLE/…`（私有 `fydoc` 仓的
`oracle/` 树）。那是一个**符号地址**：本包没有任何代码路径读它，登记册每条自带 sha256，
所以绑上的 store 可以**被校验**，不能被顶替。
