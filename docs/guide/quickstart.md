---
title: 快速上手 (Quick Start)
---

# 快速上手

下面每段都可直接粘贴运行，**全部离线**。除最后一节外都不需要装置：用到装置的两段先指
一次装置目录（见[安装与环境](install.md)）：

```bash
export FYLITE_DEVICE_DIR=$PWD/machine_desc/east
```

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

eq = fyo.read("machine_desc/east/equilibrium_east137985_4000ms.fyo.jsonld")
fyo.ip_of(eq), fyo.axis_of(eq)      # 393459.508 A, (1.83076, -0.07500)
```

★**g-file 只在门口。** `fyo.as_equilibrium` 是 g-file 进入包内的唯一一道门，进来之后包内
一律传文档；`fylite.io.geqdsk` 仍可直接读写 g/a 文件，那是给外部格式用的。

## 垂直稳定性

```python
import json, numpy as np
from fylite import device, fyo
from fylite import scenario as S

eq   = fyo.read("machine_desc/east/equilibrium_east137985_4000ms.fyo.jsonld")
case = json.load(open("machine_desc/east/case_east137985_4000ms.fyo.jsonld"))
aturns = np.array([c["current"] for c in case["pf_active"]["coil"]])   # A·总匝
dev  = device.load_device("machine_desc/east/east_device.yaml")

v = S.control.vstab(eq, coil_aturns=aturns, device=dev,
                    passive_groups=("inner_shell", "outer_shell", "passive_plates"))
v["regime"], v["growth_rate"], v["margin"]    # resistive-wall  12.6393  0.68557
```

★**报 γ 必须同时报所用的被动导体集**：只用内壳会把 γ 高估 270 倍（见
[稳定性与控制](stability-and-control.md)）。导体几何、电阻率与线圈匝数全部取自
`east_device.yaml`，互感与电阻由 `device.mutual_matrix` / `device.resistance_vector`
按几何**现算**——没有 Green 表参与。

## 一次反演

测量文档经**同一道通道契约**进来（通道数、次序、单位在这里一次性判定）：

```python
from fylite import fyo
meas = fyo.as_measurements("machine_desc/east/case_east137985_4000ms.fyo.jsonld", 4.0)
# -> plasma / btor / brsp / coils / expmp2 / basis / time_s
```

:::{note}
**这一步不需要 Green 表。** `S.analysis.reconstruction(meas)` 扣磁通环上线圈份额用的那张
表（EFIT 的 `rsilfc`）曾经必须从 `rfcoil.ddd` 读，而本仓不带它；现在它由装置文档的导体
几何现算（`recon_rs.coil_loop_rows`），与浏览器反演页同一条路。**装置信息统一由
`machine_desc/<装置>/` 的装置文档出**，指到哪台机器就是哪台。详见
[平衡反演](reconstruction.md)。
:::

## 命令行与协议面

```bash
python -m fylite --help        # 十四条命令，定义在 python/fylite/_cli.json（FYL-DESIGN-15）
python -m fylite describe      # 能力目录（JSON-LD）：制品清单、工作流、数据制品
python -m fylite mcp           # 作为 MCP stdio 服务器跑起来
python -m fylite app           # 起本机服务、开浏览器 —— 委托给单一可执行文件 fylite-app
python -m fylite data info x.h5   # 数据层（= fylite-data）；`case …`（= fylite-case）同理
```

★`run` 走 Rust inverse（EFIT 血统的驱动与 `libefit.so` 不在本分发里）；
`describe` / `manifest` / `serve` / `mcp` 四个不依赖内核，`engine` 导入期是纯 stdlib 的。
`app` / `data` / `case` 三条由 Rust 可执行文件承载，Python 侧把命令词原样交过去——同一个
定义文件，`fylite app --help` 与 `fylite-app --help` 同源。

## 走查

★**七本 notebook 已不在本仓**，`examples/notebooks/` 不存在。现在 `examples/` 下是
NFEC2026 海报的五个算例目录（`east137985-recon-figure` / `recon-to-transport` /
`zerod-metis` / `port-parity` / `vv-gold-numbers`），每个目录**只发布规格**：一份
`case.fyo.jsonld` 加一份 README，载明目的、运行方式、输出规格与诚实边界。算例的数据在
装置目录一侧（`$FYLITE_DEVICE_DIR`），不入库——这条由
`python/tests/test_examples_are_fyo.py` 机检。清单见 `examples/README.md`。

浏览器上的同一批能力（含**装置数据**页：浏览 EAST MDSplus、指定炮号、取回信号）见
[浏览器演示](browser-app.md)。
