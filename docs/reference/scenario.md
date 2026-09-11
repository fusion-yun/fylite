---
title: 一份完整算例 (A Complete Scenario · `scenario.fyo.jsonld`)
---

# 一份完整算例

**一个运行点不是一个文件。** 平衡与它的输运梯子、剖面、源项、天线表、以及跑出来的汇总，
六份文档合起来才是一份算例。这一页说清**它们各自是什么、哪些槽带 DD 的名字、哪些带本仓自己的名字**，
以及**真实算例需要而声明里根本没有的那些量**。

机读的一份在 [`scenario.fyo.jsonld`](scenario.fyo.jsonld)，由 `tools/make-scenario-jsonld.py`
**生成**——每一条路径、单位与秩都读自 `python/fylite/_fyo_interface.py`（它自己又由内核的声明表
在构建时生成）。**一份契约的手抄件不是契约**：抄对一次，然后在任何一侧一动就错。
判据 `python/tests/test_scenario_jsonld.py` 重生成并逐字节比对。

## 六份文档 (The Six Documents)

:::{table} 一份完整算例的构成（2026-09-11 实测自接口件；`fylite:` 计数是带本仓词表前缀的槽数）。
:name: tbl-scenario-docs
:align: left

| 表 | fyo 类型 | 槽数 | 其中 `fylite:` | 它是什么 |
| :--- | :--- | ---: | ---: | :--- |
| `EQUILIBRIUM` | `fyo:equilibrium` | 24 | 5 | 场：ψ 图、F 表、边界、限制器、轴与全局量 |
| `LADDER` | `fyo:equilibrium` | 24 | 13 | 输运跑在其上的**磁面梯子**：ρ、V′、度规、形状与剪切 |
| `CORE_PROFILES` | `fyo:core_profiles` | 13 | 3 | $n_e$ · $T_e$ · $T_i$ · $Z_{\rm eff}$ · 离子与杂质密度 · 转动 |
| `CORE_SOURCES` | `fyo:core_sources` | 5 | 1 | 电子 / 离子功率密度与平行电流密度 |
| `EC_LAUNCHERS` | `fyo:ec_launchers` | 8 | 3 | 每束：位置 · 两个指向角 · 频率 · 模式 · 功率 |
| `SUMMARY` | `fyo:summary` | 23 | 1 | 跑出来的：$I_p$ · $W_{\rm th}$ · $\beta_N$ · $Q$ · 各路功率 |
:::

★**`EQUILIBRIUM` 与 `LADDER` 同类型而分两表，是因为它们分别可选**：射线追踪要图不要梯子，
通量匹配要梯子不要图。合成一表会逼着每个读者都带上它不需要的一半。

★★**`fylite:` 那一列是尺子，不是瑕疵。** 带本仓前缀的槽是 IMAS DD **没有**对应位置的量
（归一通量坐标、梯子的度规、发射角的约定、模式的「支」）。规矩是单向的：**共享词表里的词必须
永远带 `fylite:` 前缀**（判据 `test_fyo_vocabulary`）——裸写会宣称一个它没有的出处，而读者
按前缀去找就什么也找不到，**不报错，只是静静丢一段**。梯子 13/24 最高，那是实情：
磁面度规几乎整套都不在 DD 里。

## 声明之外的那些量 (What Has No Slot at All)

CFEDR 一类的算例按名带**六个物种**（e · D · T · He · Ar · 快 α），而声明里只有
`ion_density` 与 `impurity_density` 两槽。于是内核把它们写成 `species/n_D` 这样的**裸路径**——
**既不在表里，也不在共享词表里**。这类量列在 `scenario.fyo.jsonld` 的 `fylite:unmapped` 段，
八条，逐条写明今天写在哪里：

| 路径 | 是什么 |
| :--- | :--- |
| `species/n_D` · `n_T` · `n_He` · `n_Ar` · `n_He_fast` | 五个离子物种的密度 |
| `species/z_Ar` | 氩的平均电荷态 $Z(T_e)$——是**剖面**，不是常数 |
| `species/w_fast_alpha` | 快 α 的储能密度 [J/m³]——快成分没有温度，等效麦氏温度由它建 |
| `pedestal` | EPED 的台基解（顶位置 · 宽 · 高）——今天作门上的设置走，不是一份文档 |

★**写下来是因为不写下来就会被重新发现**：一个没有声明位置的量，下一个读者只能从代码里
猜它叫什么。这八条同时是本体侧的待办口径（公开仓 `TODO.md` 的 `O-1` 与 `O-4`）。

## 绑定：`FYDOC-CASE-20` (Binding)

`scenario.fyo.jsonld` 末尾的 `fylite:binding` 段把上面六份文档**绑到一份真实算例**上：
CFEDR 常规 H 模 15 MA、集成建模 V1（ONETWO V5.8.2，$t = 12$ s）。

★★★**它只带路径与 `sha256`，一个数值也不带。** 该算例的语料分级为 `internal`——设计方未发表的
运行件——所以**值留在 `fydoc` 的发布闸之下**，本仓按**路径 + `sha256`** 抵达它，与那本书自己的
规矩一致。一份哈希让持有副本的人能**核验**，不会让任何人**得到**。六条源件各自写明它喂哪几份文档：

| 源件（`fydoc` 的 `cases/FYDOC-CASE-20-…/corpus/` 之下） | 喂哪几份 |
| :--- | :--- |
| `…/statefile_1.200000E+01.nc` | 平衡 · 剖面 · 源项 · 汇总 |
| `…/HCD_profiles_from_statefile.nml` | 源项（EC / IC 各路的沉积与电流） |
| `…/toray_inputs/echin` | 天线表（发射位置 · 两角 · 频率） |
| `…/toray_inputs/psiin` | 平衡（TORAY 读的那一份 ψ 图） |
| `…/gfile_efit` | 平衡（★包里的**第二份**平衡，与上一行不是同一次求解） |
| `…/EPED/peddata` | 台基（`fylite:pedestal`，见上节） |

★`gfile_efit` 单列一行是有理由的：它与 statefile 的 ψ 图**不是同一个解**（逐点差到 2 % 跨度、
磁轴差 7.91 mm），交付包里两份平衡并存。**本仓的复现链读的是 statefile 那一份。**
