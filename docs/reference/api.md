---
title: API 速查 (API Reference)
---

# API 速查

## 入口在哪

:::{important}
**没有 `fylite.run(...)` 这个函数。** `fylite.run` 是一个**模块**，里面只剩
`forward_equilibrium`（EFIT 的录得参考读取器）与 `KefitRunError`；旧文档里的
`fylite.run(shot, t)` 一律调不通。今天的入口分三层：**能力**在
`fylite.scenario`，**物理**在 `fylite.kernel`，**数据**在 `fylite.fyo` 与 `fylite.io`。
:::

`fylite` 顶层是**惰性**的（PEP 562）：`import fylite` 不拉起 numpy，也不拉起任何子模块，
`fylite.<子模块>` 首次触碰时才装载。

```python
from fylite import scenario as S     # 九个能力工具（下表）
from fylite import kernel as K       # C-ABI：GS 正/反解、磁面、GEO/NEO/TGLF、输运核
from fylite import fyo, io, device   # 文档层 / 别人的格式 / 机器
```

## 九个能力工具

四条场景线，**同一批工具 id 在浏览器、notebook 与 CLI 上同名**
（注册表即 `fylite.scenario.TOOLS`，逐条带 `provenance`：它是哪条上游需求的**降档**、
**在哪里不等价**）。

| 线 | 工具 | 入口 |
| :--- | :--- | :--- |
| `design` 放电设计 | `discharge` · `breakdown` · `feasible` · `zerod` | `S.design.*` |
| `control` 控制仿真 | `vstab` · `coupled` | `S.control.*` |
| `model` 物理建模 | `zerod` · `transport` · `coupled` · `tglf` · `discharge` · `reconstruction` | `S.model.*` |
| `analysis` 实验分析 | `reconstruction` · `zerod` | `S.analysis.*` |

一个工具**只实现一次**，服务几条线就在几条线上列名。另有两个不在注册表里的函数：
`S.analysis.profit`（剖面拟合，GCV 定阶）与各线的 `gaps()`（这条线**没建**的能力，
按 `○` 列出，而不是给一个返回零的函数）。

```python
z = S.model.zerod()                      # 0-D 放电，规定剖面
t = S.model.transport(power=4.0)         # 一步 1.5-D 芯部输运
f = S.analysis.profit(x, y, sigma_frac=0.05)
r = S.analysis.reconstruction(meas, pressure=f)   # 磁测量 + 动理学压强
```

## 模块地图

| 模块 | 用途 |
| :--- | :--- |
| `kernel` | C-ABI 面：`gs_free_solve` / `gs_inverse_solve`、`trace_surface` 磁面追踪、GEO / NEO / TGLF 端口、`core_march` 输运核；装载器与 ABI 守卫也在这里 |
| `fyo` | fyo 语义文档层：`equilibrium`（g-file→文档，`as_equilibrium` 是唯一的门）、`reconstruction`、`Ladder` 一次描迹（输运度量 + Miller 形状，同一批面）、`read` / `write`（JSON-LD / HDF5） |
| `device` | **机器**：①牌在哪（`$FYLITE_DEVICE_DIR`，缺则抛 `MachineDataMissing`）②牌说什么（几何 / 通道图 / 被动集，文档优先、deck 兜底）③**导体做什么**（互感 / 电阻矩阵、网格响应与磁通折叠、通道空间电路矩阵、回路推进）④**视线做什么**（弦几何与沿磁通图的线积分） |
| `io.geqdsk` | g/a-file 读写，以及 g 文件蕴含的 `(R, Z)` 网格与 ψ_N 图 |
| `io.est2` | est2 基底约化（窗口均值、漂移、POINT），在线 MDSplus 与离线 HDF5 转储共用的**唯一**一条约化 |
| `io.mds` | EAST MDSplus 取数（`efit_east` 树 → 测量字典、Thomson / 逆磁） |
| `io.kfile` | EFIT k-file 组装与 namelist 解析（`&IN1`/`&INWANT`/`&INS` 分组、MSE、压强、曲率行） |
| `io.gacode` | GACODE `input.gacode` 剖面 + 几何包 |
| `io.efund` | efund deck 格式（`east_geom.txt`）——**不是数据源**：盒与线圈匝数在装置文档里，读 deck 只为**核对**文档 |
| `appsession` | 浏览器会话文档（`fylite:AppSession/1`）的另一端：读回页面导出的输入与输出 |
| `engine` | 执行体与交付引擎、JSON-LD 制品清单、CLI 与协议面（**导入期纯 stdlib**） |
| `run` | `forward_equilibrium`——EFIT 的**录得参考读取器**（`tests/data/oracle/`），不是求解器 |
| `plot` | 通量图与单图重构渲染（需 `matplotlib`） |
| `engine.casereport` | **算例报告**：计划 + 记录 → 呈现规格 → MyST + 手写 SVG（不需要 matplotlib）；见[算例报告](case-report.md) |
| `scenario.cases` | 算例语料：`catalogue` / `load` / `settings` / `plan` / `run`，以及按名拒绝的 `REFUSALS` |
| `scenario.benchmark` | 公开 V&V 登记册：`records` / `load` / `problems` / `gate_plan` / `run` |
| `scenario.model.*` | `assembly`（含时芯部推进 `solve_core`）· `closure` · `neoclassical` · `gyrofluid`（TGLF）· `nbi` · `lh` · `sources` · `mapping`（剖面→NEO/TGLF 输入的 GACODE 归一） |
| `scenario.analysis.*` | `recon_rs`（重构行）· `loop`（自洽外环）· `tomography` · `selfcal` · `moments` |
| `scenario.control.*` | `stability`（n=0 垂直模）· `vertical`（线性化对象与反馈回路）· `evolution`（电压驱动自由边界演化） |
| `scenario.design.*` | `shape`（形状观测量与响应矩阵）· `pulse`（前馈轨迹、通道限值、带界最小二乘） |

★`scenario.model.neoclassical` 是**全部**新经典自举流的一处：`neo` 与 `redl` 两个
`current_source` 后端都在这里，算的是同一个 DD 量（`core_sources` `bootstrap_current`，
index 13）、同一份内核文件。一次 NEO 调用同时返回三支电流，**选哪一支是 `key=` 不是模型**
（`solver="neo", key="jpar_sauter_2021"`）。
★`scenario.model.gyrofluid` 是 TGLF 那一个——同级 `__init__` 里有名为 `tglf` 的能力函数，
**同名模块会被它遮住**。

## CLI

十一个子命令。安装后 `fylite` 与 `python -m fylite` 是同一个入口。

| 子命令 | 做什么 |
| :--- | :--- |
| `cases` | **算例语料与 V&V 登记册**（下节） |
| `report` | 把一次**已记录的运行**渲染成 MyST 报告（[模板](report-template.md)） |
| `describe` | 能力目录（JSON-LD）：制品清单、工作流、数据制品 |
| `manifest` | 核对 / 重封 / 导出 JSON-LD 制品清单 |
| `replay` | 按账本重放一次运行 |
| `whence` | 一个结果量的来处（哪次运行、哪个入口、哪份输入） |
| `alias` | 句柄别名 |
| `serve` | 目录 + 入口调用，JSON-RPC 2.0 over stdio（实验） |
| `mcp` | MCP stdio 服务器：精选工具 + 由清单反射出的工具 |
| `plot` | `fylite plot g137985.04000 -o flux.png`（需 matplotlib） |
| `run` | 一次平衡反演——★**跑不动**：它按输入模式组装 k-file 再调 `libefit.so`，而那个库不在本分发里 |

### `fylite cases` —— 两份语料，一个动词

```bash
fylite cases                        # 列出 cases/ 的 25 条算例
fylite cases <id>                   # 打印那份计划（fyo:ScenarioSpecification）
fylite cases --check                # 结构检查（词汇只有 fyo / spo，无孤儿文件）
fylite cases --plan  <id>           # 只映射不跑：控件 -> 入口字段的完整账
fylite cases --run   <id> [--predict]
fylite cases --report <id> [--from DIR] [--out DIR] [--presentation SPEC] [--lang zh|en]

fylite cases --benchmark            # 公开 V&V 登记册（benchmark/）：类 · 结论 · 复测 · 纳入类别
fylite cases --benchmark <ID>       # 一条 fyo:ComparisonRecord
fylite cases --benchmark --check
FYLITE_KERNEL=../fylite_kernel fylite cases --benchmark --run V-09   # 该记录的私仓门
```

用法与逐族示例见用户指南的[算例语料](../guide/cases.md)与其后五章。

### `fylite-case` —— 不经 Python 的那条路

数据层的可执行件，直通内核单入口 `fylite_rs_fyo`：

```bash
fylite-case describe
fylite-case plan <plan.jsonld>... [--set k=v]... [--bind port=path]...
fylite-case run  <plan.jsonld>... --record DIR [--format jsonld|hdf5|netcdf|imas-hdf5]
fylite-case json <plan.jsonld>...        # 一份计划进，一份记录出（stdout）
```

多份计划按序合成（后者覆盖前者）。★`--format imas-hdf5`（或计划自己在输出端口上要
`fyo:ImasHdf5Format`）写出**一个 IMAS 数据入口**：`imas/master.h5` + 逐 IDS 的 `<ids>.h5`。

Python 侧同一道门是 `fylite.io.fydoc.case_json(plan, base=…)`：一份 `fyo:ScenarioSpecification`
进，一份 `spo:ComputationRecord` 出（产出数据集内联在端口上），被拒绝的算例也**回记录**
（`run_state: rejected`，内核的话在 `comment` 里）而不是抛异常。
