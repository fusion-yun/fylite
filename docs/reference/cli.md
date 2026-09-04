---
title: 命令行 (Command Line Reference)
---

# 命令行

命令行只有一个可执行文件：**`fy`**（`bash rust/build.sh --exe` 出，落在
`rust/fylite_runtime/target/release/fy`）。本页是它的全表。要按任务走一遍，看用户指南的
[命令行怎么用](../guide/cli.md)。

:::{important}
**Python 包没有命令行**（2026-09-04 用户裁定）：没有 `fylite` 控制台脚本，没有
`python -m fylite`，也没有 argparse 那一层。从前由它承载的十一条动词是**库调用**，
逐条对照见[用户指南](../guide/cli.md#从前的十一条动词今天怎么写)。
:::

## 一份定义，两个宿主

命令行的**定义**只有一处：`python/fylite/_cli.json`（`FYL-DESIGN-15`）。

| 宿主 | 是什么 | 怎么用这份定义 |
| :--- | :--- | :--- |
| `fy` | **唯一的可执行文件**（Rust） | 编译期纳入它，建出自己的解析器 |
| 浏览器页面 | 静态站点 | 它的 `hosts.app.params` 就是页面的启动参数 |

★这份文件从前有第三个读者——Python 的 argparse 建造者——它与那一层一起撤了；文件里
只属它的十一条命令、`hosts: ["python"]` 标记与 `--bin-dir` 也一并撤除，闸子
`test_cli_spec.py` 现在钉的就是「没有第三个宿主的残留」。

## 三条命令

```bash
fy --help
fy app  [--port N] [--no-open] [--mdsip HOST:PORT] [--mds-user NAME]
        [--page P] [--device D] [--lang L] [--theme T] [--app-dir DIR]
fy data info|dump|convert|merge|assemble|fetch|tables|facts … [--facts PATH]
fy case describe|plan|run|json … [--facts PATH]
```

不带命令词时它跑 `app`（起服务、开浏览器），所以双击仍然可用。

:::{note}
**为什么只有一个可执行文件。** 2026-09-03 之前还有 `fylite-data` 与 `fylite-case` 两个
二进制。它们各十行，做的就是把 `data` / `case` 前置到自己的命令行再调用同一份代码——
而那一次前置由调用方给就够了。于是它们撤掉。名字换过两次：`fylite-app` → `fylite` →
**`fy`**（2026-09-04）；中间那一次与 Python 控制台脚本同名，`$PATH` 上找到的会是那个
脚本自己、于是无限 fork——两个名字分开之后，那条失败方式在源头上没有了。
:::

## `fy data` —— 数据层

八条子命令：`info` / `dump` / `convert` / `merge` / `assemble` / `fetch` / `tables` / `facts`，
外加组级选项 `--facts PATH`（`case` 亦同）。
它能读哪些源、写哪两种布局、`--time` 怎么写、为什么 MDSplus 只读——**单开一页**：
[数据层](data-layer.md)。

## `fy case` —— 一份计划进，一份记录出

直通内核单入口 `fylite_rs_fyo`，不经 Python 装配：

```bash
fy case describe [--kernel PATH]
fy case plan <plan.jsonld>... [--set k=v]... [--bind port=path]... [--code NAME]
fy case run  <plan.jsonld>... --record DIR [--format jsonld|hdf5|netcdf|imas-hdf5]
             [--code NAME] [--kernel PATH] [--quiet]
fy case json <plan.jsonld>... [--kernel PATH]   # 一份计划进，一份记录出（stdout）
```

`--kernel` 显式指一份内核 `.so`（缺省按 `$FYLITE_KERNEL_LIB` 与包内 `_lib/` 找），
`--code NAME` 在一份计划带多个代码时选一个，`--quiet` 只留记录本身。

多份计划按序合成（后者覆盖前者，`--set` / `--bind` 最后）。★`--format imas-hdf5`
（或计划自己在输出端口上要 `fyo:ImasHdf5Format`）写出**一个 IMAS 数据入口**：
`imas/master.h5` + 逐 IDS 的 `<ids>.h5`。

★**跑不成的算例也回一份记录**（`run_state: rejected`，内核的话在 `comment` 里），
不是抛一个异常：一份跑不了的计划必须说出它缺什么。

Python 侧同一道门是 `fylite.io.fydoc.case_json(plan, base=…)`：一份
`fyo:ScenarioSpecification` 进，一份 `spo:ComputationRecord` 出，产出数据集内联在端口上。

## 算例语料与 V&V 登记册

从前是 `fylite cases …` 一条动词，今天是库：

```python
from fylite.engine import cases
cases.catalogue()          # 列出 cases/ 的算例
cases.load("zerod-iter-15ma")
cases.run("zerod-iter-15ma")
from fylite.engine import benchmark as bm
bm.records(); bm.problems(rec, d); bm.run("V-09")   # 公开 V&V 登记册
```

逐族示例见[典型算例](../examples/index.md)那一篇。

## 相关

- [命令行怎么用](../guide/cli.md) —— 按任务走的那一遍，以及十一条动词的库对照表
- [数据层](data-layer.md) —— `fy data` 八条子命令详解
- [API 速查](api.md) —— Python 的入口地图
- 设计集 `FYL-DESIGN-15` —— 一份规格几个宿主，以及每条裁定的理由
