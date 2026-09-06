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
| `kernel` | C-ABI 面：装载器、ABI 守卫、文档门 `scenario` / `fydoc.complete`，与仍在接口上的原语；物理算子（求解器 · 磁面追踪 · GEO / NEO / TGLF 端口 · 输运核）经门到达，扁平入口自 2026-09-05 起逐刀退出接口（`docs/note/kernel-public-seam.md`） |
| `fyo` | fyo 语义文档层：`equilibrium`（g-file→文档，`as_equilibrium` 是唯一的门）、`reconstruction`、`Ladder` 一次描迹（输运度量 + Miller 形状，同一批面）、`read` / `write`（JSON-LD 在本层；`.h5` 交给中间层 `io.fydoc`，2026-09-04 起） |
| `device` | **机器**：①牌在哪（`$FYLITE_DEVICE_DIR`，缺则抛 `MachineDataMissing`）②牌说什么（几何 / 通道图 / 被动集，文档优先、deck 兜底）③**导体做什么**（互感 / 电阻矩阵、网格响应与磁通折叠、通道空间电路矩阵、回路推进）④**视线做什么**（弦几何与沿磁通图的线积分） |
| `io.geqdsk` | g/a-file 读写，以及 g 文件蕴含的 `(R, Z)` 网格与 ψ_N 图 |
| `io.est2` | est2 基底约化（窗口均值、漂移、POINT），在线 mdsip 与离线 HDF5 转储共用的**唯一**一条约化 |
| `io.mds` | EAST MDSplus 取数（`efit_east` 树 → 测量字典、Thomson / 逆磁）。★传输走中间层的 mdsip 客户端（`kernel.MdsSession`），本包不 import 站点的 `MDSplus` 包（2026-09-04） |
| `io.fydoc` | **数据层**的 Python 面（`libfylite_runtime.so`，`rust/fylite_runtime/`）：按内容识别文件类型，不同数据源 ↔ fyo 文档的读写与合并；MDSplus 只读、HDF5 / netCDF 的 fyo 与 IMAS 两种布局都在这一层 |
| `io.gacode` | GACODE `input.gacode` 剖面 + 几何包 |
| `io.efund` | efund deck 格式（`east_geom.txt`）——**不是数据源**：盒与线圈匝数在装置文档里，读 deck 只为**核对**文档 |
| `appsession` | 浏览器会话文档（`fylite:AppSession/1`）的另一端：读回页面导出的输入与输出 |
| `engine` | 执行体与交付引擎、JSON-LD 制品清单、CLI 与协议面（**导入期纯 stdlib**） |
| `run` | `forward_equilibrium`——EFIT 的**录得参考读取器**（`tests/data/FYDOC-CASE-03-frozen-libs/corpus/`），不是求解器 |
| `plot` | 通量图与单图重构渲染（需 `matplotlib`） |
| `engine.casereport` | **算例报告**：计划 + 记录 → 呈现规格 → MyST + 手写 SVG（不需要 matplotlib）；见[算例报告](case-report.md) |
| `engine.cases` | 算例语料：`catalogue` / `load` / `settings` / `plan` / `run`，以及按名拒绝的 `REFUSALS` |
| `engine.benchmark` | 公开 V&V 登记册：`records` / `load` / `problems` / `gate_plan` / `run` |
| `scenario.model.*` | `assembly`（含时芯部推进 `solve_core`）· `closure` · `neoclassical` · `gyrofluid`（TGLF）· `nbi` · `lh` · `sources` · `mapping`（剖面→NEO/TGLF 输入的 GACODE 归一） |
| `scenario.analysis.*` | `recon_rs`（重构行）· `loop`（自洽外环）· `tomography` · `selfcal` · `moments` |
| `scenario.control.*` | `stability`（n=0 垂直模）· `vertical`（线性化对象与反馈回路）· `evolution`（电压驱动自由边界演化） |
| `scenario.design.*` | `shape`（形状观测量与响应矩阵）· `pulse`（前馈轨迹、通道限值、带界最小二乘） |

★`scenario.model.neoclassical` **已迁出本包**（T-4 第十五刀 · 第十八刀，2026-09-06）：`neo` 与 `redl` 两个
`current_source` 后端连同外环一起在内核仓的神谕树 `tests/oracles/{neoclassical,redl}.py`，算的仍是同一个 DD 量
（`core_sources` `bootstrap_current`，index 13）、同一份内核文件；页面与 Python 的自举闭合走 `code/transport` 门。
★`scenario.model.gyrofluid` 是 TGLF 那一个——同级 `__init__` 里有名为 `tglf` 的能力函数，
**同名模块会被它遮住**。

★**这些入口背后是哪条方程**：`scenario` 与 `kernel` 只是装配与 C 边界，物理在 Rust 内核里，
逐模块写在[物理与数值](../physics/00-overview.md)十五章——方程、假设、参数域、数值格式、
一手出处与验证锚点，模块到章节的映射见[内核](kernels.md)的模块地图。

## 命令行

★★2026-09-04 起 **Python 侧没有命令行**：`fylite` 控制台脚本、`python -m fylite` 与
`engine/cli.py` 一并撤除，本页上的这些入口就是全部的用法。机器上那一条命令行是
Rust 的 `fy`，全表另开一页：[命令行](cli.md)（`app` / `data` / `case` 三条），
其中数据层那一条再单开一页：[数据层](data-layer.md)。

命令行的**定义**仍只有 `python/fylite/_cli.json` 一处，`fy` 在编译期纳入它——从前
Python 也由它建 argparse，那第三个读者随该层一起走了。
