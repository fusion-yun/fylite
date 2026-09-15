---
title: 输入模式 (Input Modes)
---

# 输入模式

:::{important}
**没有单一的 `fylite.run(...)` 入口。** 下表的五种输入源各有自己的门，而**通道契约只有一处**：`fylite.fyo.as_measurements` 把任何一种
输入压成同一个扁平测量字典（`plasma` / `btor` / `brsp` / `coils` / `expmp2` / `basis`），
通道数、次序与单位在那里一次性判定。
:::

:::{table} 五种输入源，以及各自的门。
:name: tbl-input-modes
| 源 | 入口 | 探针基 |
| :--- | :--- | :--- |
| est2 / GUI_v5 的 live `east` 树（79 探针） | `io.est2.reduce_est2`（在线 MDSplus 与离线 HDF5 转储共用**同一条**约化） | est2（`green2018_wpf_64`） |
| 处理级 `efit_east` 树（76 探针） | **拒绝**（用户裁定 2026-09-15：该树只作对拍比较数据，不作反演输入） | — |
| IMAS 形式的 magnetics 文件（JSON/YAML） | `fyo.as_measurements(path, time_s)` | 由文档声明的 `fylite:channel_basis` 定 |
| fyo / JSON-LD 测量文档 | 同上——语义文档与普通 IMAS dict 走同一道契约 | 同上 |
| 现成的 `&IN1` k-file | **没有入口** | — |
:::

★从 EFIT 侧进来的路**一条也没有**：处理级 `efit_east` 树按 2026-09-15 用户裁定只作对拍比较数据（`io.mds.efit_reference` 读它的答案），
k-file 既不读也不写；反演输入走原始 `east` / `pcs_east` 树（`io.raw`）。

★**扁平字典自带 `basis`**：下游要挑权重掩膜、限制器或表集时不必按 `len(expmp2)` 反推
——那正是「各自假设一次」的来路。

## 通道序：两套探针基不可混用

**这是最容易静默出错的地方。** 两条路的探针道数与 Green 表都不同：

- **est2 / GUI_v5**：79 道，表集 `green2018_wpf_64`；
- **efit_east / IMAS**：76 道，表集 `green2012`。

混用不会报错，只会给出错的结果。基由**文档自己声明**（`fylite:channel_basis`）或按通道数
判定，判不出属于任何已知基时**当场抛错**，而不是产出一份没人读得了的文档。

## 线圈电流：A·总匝，不是端子电流

`BRSP` 的每一路是**安培·总匝**。这条契约有两个后果：

1. 从 MDSplus 取数时，`io.est2` 走每路 Rogowski 的节点名 × 匝数（`PF_NODES` ×
   `PF_TURNS`）再按 EFIT 线圈序重排（`PF_EFIT_ORDER`）——★这三样是**装置文档的字段**，
   不是模块常量：匝数与文档同源，换一台机器就换一份。而 `efit_east` 树的 `FCCURT`
   **本身就已是 A·匝且已按 BRSP 序**——两条路各有其映射，不必一致。
2. 电路层（`fylite.device` §3）以 A·总匝为态，故**每匝空间的回路方程
   $U/N = M_1\dot x + R_1 x$ 不需要匝数表**。

:::{tip}
`a-file` 的 `ccbrsp` 是**拟合后**的线圈电流，不是输入（与同炮 `FCCURT` 中位差
3.5%）。做映射或口径裁决时**须用 `FCCURT` 作权威**。
:::

## 装置数据的单一读点

全部 EAST 装置常量（限制器、线圈匝数、逐道误差地板、运营掩码、MDSplus 节点名、
拟合控制、被动结构几何与电阻率、电源额定）都在
`$FYLITE_DEVICE_DIR/east_device.yaml`（目录由 `$FYLITE_DEVICE_DIR` 指定），经
`device.load_device()` 读取。
**代码层是装置中立的**：没有硬编码的机器常量。

## 65×65 是 deck 的分辨率，不是内核的

本仓不带 libefit、efund 与 Green 表（LICENSE 3.1，见
[本分发不含的 Fortran 制品](#fortran-artifacts)）。

- **内核不限分辨率。** `code/forward` 收的是两条**任意长度**的网格坐标数组
  （`grid_r` / `grid_z`），`kernel.Grid` 也只是 `(r0, z0, dr, dz, nr, nz)`；
- `$FYLITE_DEVICE_DIR/east_device.yaml` 的 `solver_dims`（`nw=nh=65`）是**装置文档的声明**，
  由 `device.verify_solver_dims` 对装置目录里独立的 efund deck（`east_geom.txt`）核验——
  两边不一致要 fail loud，而不是让两套数字各自漂移；
- 磁通环与探针的**响应行**不查表，由内核按给定网格现算
  （`kernel.mutual_outer` / `kernel.probe_response`）；线圈→环的那一行（EFIT 的 `rsilfc`）也是现算
  （`code/reconstruction` 门内的线圈→回路行），线圈→探针同样是算的
  （`code/coilshare` · `code/reconstruction` 门内的探针响应）。**装置信息只有一个出处：`$FYLITE_DEVICE_DIR/` 下的装置
  文档**；`device.coil_response_tables` / `vessel_response_tables` 只有"拿别人的表和几何对一遍"
  这一个用途（`device.vessel_table_check`，在内核仓测试树 `tests/oracles/em_kernel.py`），活路上没有调用者（闸子
  `python/tests/test_one_machine_source.py`）。

:::{warning}
沿用 65×65 的理由：交付的 g-file、`solver_dims` 与两套探针基都按
这个盒标定，**换盒即换口径**——本仓没有重生成表的工具，对不上的时候没有第二条路
可以自证。
:::
