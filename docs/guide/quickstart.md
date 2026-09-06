---
title: 快速上手 (Quick Start)
---

# 快速上手

下面每段都可直接粘贴运行，**全部离线**。除最后一节外都不需要装置；用到装置的两段先按
[安装与环境](install.md)把装置牌从 A-Box 拖出来（仓内 `machine_desc/` 已废弃），再指一次：

```bash
export FYLITE_DEVICE_DIR=~/fylite-decks/east    # 见「安装与环境」：EAST 牌取自内核仓历史
```

★想直接看**完整的、可跑的**算例（0-D / 1.5-D / 演化 / 放电设计 / 平衡反演各一族），
从[算例语料](../examples/index.md)那一章进去——那里每一条都在 `cases/` 有一份计划文档。

:::{important}
**入口不是 `fylite.run(...)`。** 那是一个模块，不是函数；能力工具在 `fylite.scenario`，
物理在 `fylite.kernel`，文档在 `fylite.fyo`。完整地图见 [API 速查](../reference/api.md)。
:::

## 零配置的那一半

不需要机器的一半——0-D 放电、一步输运、剖面拟合、局域 TGLF/NEO——不必设任何环境变量：

```python
from fylite import scenario as S

z = S.model.zerod()                       # 0-D 放电（规定剖面）：t/ip/q/ne/te/p_fus/phase
t = S.model.transport(power=4.0)          # 一步 1.5-D 芯部输运：rho/y/converged/residual
f = S.analysis.profit(x, y, sigma_frac=0.05)   # 剖面拟合，阶数由 GCV 选
```

每个返回值都是普通 dict，且都带一个 `provenance` 键：它是哪条上游需求的**降档**、
**在哪里不等价**——不必记在读者脑子里。

## 读一份交付的平衡

装置卷宗里带着 EAST #137985 @ 4 s 的交付重构，形态是 fyo / JSON-LD 文档：

```python
from fylite import fyo

eq = fyo.read("$FYLITE_DEVICE_DIR/equilibrium_east137985_4000ms.fyo.jsonld")
fyo.ip_of(eq), fyo.axis_of(eq)      # 393459.508 A, (1.83076, -0.07500)
```

★**g-file 只在门口。** `fyo.as_equilibrium` 是 g-file 进入包内的唯一一道门，进来之后包内
一律传文档；`fylite.io.geqdsk` 仍可直接读写 g/a 文件，那是给外部格式用的。

## 垂直稳定性

```python
import json, numpy as np
from fylite import device, fyo
from fylite import scenario as S

eq   = fyo.read("$FYLITE_DEVICE_DIR/equilibrium_east137985_4000ms.fyo.jsonld")
case = json.load(open("$FYLITE_DEVICE_DIR/case_east137985_4000ms.fyo.jsonld"))
aturns = np.array([c["current"] for c in case["pf_active"]["coil"]])   # A·总匝
dev  = device.load_device("$FYLITE_DEVICE_DIR/east_device.yaml")

v = S.control.vstab(eq, coil_aturns=aturns, device=dev,
                    passive_groups=("inner_shell", "outer_shell", "passive_plates"))
v["regime"], v["growth_rate"], v["margin"]    # resistive-wall  12.6393  0.68557
```

★**报 γ 必须同时报所用的被动导体集**：只用内壳会把 γ 高估 270 倍（见
[稳定性与控制](stability-and-control.md)）。导体几何、电阻率与线圈匝数全部取自
`east_device.yaml`，互感与电阻由内核门 `code/pulse` · `code/vstab` 在文档上算（Python 的 `device.mutual_matrix` / `device.resistance_vector` 自 2026-09-06 归内核仓测试树）
按几何**现算**——没有 Green 表参与。

## 一次反演

测量文档经**同一道通道契约**进来（通道数、次序、单位在这里一次性判定）：

```python
from fylite import fyo
meas = fyo.as_measurements("$FYLITE_DEVICE_DIR/case_east137985_4000ms.fyo.jsonld", 4.0)
# -> plasma / btor / brsp / coils / expmp2 / basis / time_s
```

:::{note}
**这一步不需要 Green 表。** `S.analysis.reconstruction(meas)` 扣磁通环上线圈份额用的那张
表（EFIT 的 `rsilfc`）曾经必须从 `rfcoil.ddd` 读，而本仓不带它；现在它由装置文档的导体
几何现算（`code/reconstruction` 门内），与浏览器反演页同一条路。**装置信息统一由
`$FYLITE_DEVICE_DIR` 指向的装置文档出**，指到哪台机器就是哪台。详见
[平衡反演](reconstruction.md)。
:::

## 命令行与协议面

★★2026-09-04 起 **Python 包没有命令行**（用户裁定）：`fylite` 控制台脚本与
`python -m fylite` 都不再有，装上它得到的是一个库。命令行只剩一个可执行文件：

```bash
bash rust/build.sh --exe       # -> rust/fylite_runtime/target/release/fy
fy --help                      # 三条命令：app / data / case（定义在 python/fylite/_cli.json）
fy app                         # 起本机服务、开浏览器
fy data info x.h5              # 数据层
```

协议面与目录改从库里起：

```python
from fylite.engine import manifest_catalog          # 能力目录（JSON-LD）
from fylite.engine.serve import mcp_stdio, serve_stdio   # MCP / JSON-RPC，都走 stdio
from fylite.engine import cases                     # 算例语料：catalogue() / load() / run()
```

按任务走一遍见[命令行](cli.md)那一章（末节是十一条旧动词的逐条库对照），逐条参数见
参考篇的[命令行](../reference/cli.md)。

★反演走 Rust inverse（EFIT 血统的驱动与 `libefit.so` 不在本分发里）；能力目录、清单校验
与两个 stdio 服务都不依赖内核，`fylite.engine` 导入期是纯 stdlib 的。

## 走查

★**七本 notebook 已不在本仓**，`examples/notebooks/` 不存在；2026-09-02 起仓根的
`examples/` 整个目录也已删除。（书里那一篇「典型算例」住在 `docs/examples/`，与它同名
而无关。）它的位置被两样东西接替，各自更硬：

- **`cases/`** —— 25 条算例的计划文档（`fyo:ScenarioSpecification`），
  `fylite.engine.cases` 可列（`catalogue()`）、可查（`load()`）、可跑（`run()`）、
  可出报告（`engine.casereport.render()`）。本书的[典型算例](../examples/index.md)五章就走这条路。
- **`docs/benchmark/`** —— 公开 V&V 登记册：对着外部答案量过什么、量到多少、哪条门钉住它。

浏览器上的同一批能力（含**装置数据**页：浏览 EAST MDSplus、指定炮号、取回信号，以及
**算例报告**页：把一份记录画成报告）见[浏览器演示](browser-app.md)。
