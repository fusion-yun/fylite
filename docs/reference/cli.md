---
title: 命令行 (Command Line Reference)
---

# 命令行

命令行只有一个可执行文件：**`fy`**（`bash rust/build.sh --exe` 出，落在
`rust/fylite_runtime/target/release/fy`）。本页是它的全表。要按任务走一遍，看用户指南的
[命令行怎么用](../guide/cli.md)。

:::{important}
**Python 包没有命令行**（2026-09-04 用户裁定）：没有 `fylite` 控制台脚本，没有
`python -m fylite`，也没有 argparse 那一层。
:::

## 一份定义，两个宿主

命令行的**定义**只有一处：`python/fylite/_cli.json`（`FYL-DESIGN-15`）。

| 宿主 | 是什么 | 怎么用这份定义 |
| :--- | :--- | :--- |
| `fy` | **唯一的可执行文件**（Rust） | 编译期纳入它，建出自己的解析器 |
| 浏览器页面 | 静态站点 | 它的 `hosts.app.params` 就是页面的启动参数 |

★这份文件从前有第三个读者——Python 的 argparse 建造者——它与那一层一起撤了；闸子
`test_cli_spec.py` 现在钉的就是「没有第三个宿主的残留」。

## 四条命令

```bash
fy --help
fy app  [--port N] [--no-open] [--mdsip HOST:PORT] [--mds-user NAME]
        [--page P] [--device D] [--lang L] [--theme T] [--app-dir DIR]
fy data info|dump|convert|merge|assemble|fetch|tables … [--facts PATH]
fy run  <line> [<scenario>] | <plan.jsonld>... [key=value ...] [options]
fy list devices|experiments|scenarios|presets|facts|kernel|lines … [--facts PATH] [--cases PATH]
```

一个词一个动词：起页面 · 搬数据 · 算 · 看。不带命令词时它跑 `app`，所以双击仍然可用。

:::{note}
**为什么只有一个可执行文件。** 2026-09-03 之前还有 `fylite-data` 与 `fylite-case` 两个
二进制，各十行，做的就是把命令词前置到自己的命令行再调用同一份代码——那一次前置由
调用方给就够了。名字换过两次：`fylite-app` → `fylite` → **`fy`**（2026-09-04）；中间那
一次与 Python 控制台脚本同名，`$PATH` 上找到的会是那个脚本自己、于是无限 fork。
:::

(fylite-cli-run)=
## `fy run` —— 一次日常建模或分析

```bash
fy run <line> [<scenario>] [selectors] [key=value ...] [options]
fy run <plan.jsonld>...     [selectors] [key=value ...] [options]
```

两种位置参数形，一条路：**场景形**由线（`analysis` / `model` / `design` / `control`）
选出缺省场景，场景选出模板；**计划文件形**（从前的 `fy case run`）把给出的计划按序
合成，模板由合成后计划的 code 末段反查。含 `/` 或以 `.json` / `.jsonld` / `.yaml`
结尾的位置参数当路径，否则当名字。

### 参数：四种写法，一个意思

| 写法 | 等价于 | 说明 |
| :--- | :--- | :--- |
| `key=value` | `--key=value` | 裸写法；名字若与固定选项同名（`shot` · `time`），**固定选项优先** |
| `--key=value` | `key=value` | — |
| `--key` | `key=true` | 只对布尔参数合法 |
| `--no-key` | `key=false` | 同上 |

名字里 `-` 与 `_` 等价。**值要用 `=`**：`--key value`（空格）不是参数写法，那个值会被
当成位置参数。

:::{important}
**装置信息随发行版走**（2026-09-05 用户裁定）。三种制品各自带着按许可筛过的那几台
装置描述：可执行文件**编在二进制里**，轮装在 `fylite/_facts/`，站点发在 `facts/` 下。
所以一份发行版**盘上没有语料也答得出** `fy list devices` 与 `fy run --device`。
`--facts` / `$FY_FACTS_PATH` 是**前置**：把自己的根排在自带的那一份之前，从不替换它。
`fy list facts --roots` 会把自带的那一档打成一行 `<bundled>`，并说它带了几条。

★同日另一条：**仓顶不再有 `facts/` 目录**。在检出里拖回来的语料落在 `dist/facts/`
（构建暂存区），`app/facts` 那条符号链接一并撤除。
:::

参数**不在** `_cli.json` 里：它属于场景，而场景是数据。名字、类型、缺省与取值范围来自
**场景模板**（`docs/examples/scenario/<name>.jsonld`，随可执行文件内嵌，可被语料路径上
的同名文件覆盖）。未知的名字在第二段解析里按名拒绝并给出最接近的三个。

### 固定选项

| 选项 | 作用 |
| :--- | :--- |
| `--device ID` | 装置：facts 里的名字或一份清单路径。整份装置文档绑到 `device` 端口，并补上模板声明的装置缺省 |
| `--shot N` / `--time T` | 炮号与时刻；与 `shot=N` / `time=T` 同一个参数。时间记法 `4.5`（点）/ `4:5`（窗）/ `4,4.5,5`（表） |
| `--preset NAME` | 语料里的具名计划，叠在模板与装置之上 |
| `--plan FILE` | 显式计划（可重复，按序） |
| `--input FILE` | 绑到模板声明的**主输入端口** |
| `--bind PORT=FILE` | 绑其余端口（可重复） |
| `--code IRI` | 一份计划带多个 code 时选一个 |
| `--cases PATH` / `--facts PATH` | 语料根**前置**（可重复）——排在自带的那一份之前，不替换它 |
| `-o, --record DIR` | 记录目录；缺省 `$FYLITE_RUN_DIR/<戳>-<场景>/` |
| `--format F` | `jsonld` / `hdf5` / `netcdf` / `imas-hdf5` |
| `--kernel PATH` | 内核 `.so` |
| `--mdsip HOST[:PORT]` / `--mds-user NAME` / `--timeout-ms MS` | 取数阶段的连接 |
| `--offline` | 取数阶段禁止开套接字（也可 `$FYLITE_OFFLINE=1`） |
| `--dry-run` | 合成并打印计划与来源表，不取数、不装内核、不写文件 |
| `--json` | 与 `--dry-run` 合用打计划；单独用把记录连数据集内联打到 stdout |
| `--quiet` | 不打进度 |

### 合成次序

自低到高，后者覆盖前者，每个值在 `plan.jsonld` 里带一条 `fylite:from`：

1. **模板缺省** `template:<场景>`
2. **装置** `device:<id>@<root>`——模板的 `from_device` 表按 fyo 路径取值；取不到就不设
3. **预设** `preset:<路径>`
4. **`--plan`** `plan:<路径>`，按序
5. **命令行** `cli`；开关展开记 `cli:switch <名>`，且**低于**同一行上显式给的参数
6. **端口绑定** `cli:input` / `cli:bind` / `resolved:<来源>`

### 测量文档三级解析

给了 `--input` 就用它；否则给了 `shot=` 就在 facts 的 `experiment/<装置>/<炮>` 里找
最近的一片（容差 1 ms，超出**不取邻片**）；再否则去取数，取回的文档**先落进记录目录**
再绑端口——于是同一次分析可以离线重放。`--offline` 下第三级不存在。

### 记录目录与退出码

```text
rec/
  plan.jsonld              合成好的计划，每个参数带 fylite:from
  device.fyo.jsonld        装出来的装置文档（给了 --device 且它有清单时）
  measurements.fyo.jsonld  第三级取回的测量
  record.jsonld            spo:ComputationRecord；run_state · fylite:refusal_stage
  <ids>.fyo.jsonld         产出的数据集
```

| 退出码 | 含义 | 记录 |
| ---: | :--- | :--- |
| 0 | 跑完 | 全套 |
| 1 | 合成之后的拒绝，`fylite:refusal_stage` ∈ `compose` / `device` / `measurements` / `kernel` | 有（`run_state: rejected`） |
| 2 | 语法：未知选项、未知参数、类型不符、范围外 | 无 |

(fylite-cli-list)=
## `fy list` —— 有什么可用

七条子命令，一类语料一条；给名字就把那一条打全。**只读**：不合成、不取数、不写记录、
不开套接字。

| 子命令 | 打什么 |
| :--- | :--- |
| `devices [<id>...]` | facts 的装置：由哪个根供（`<bundled>` = 编在这份二进制里）、卡片还是清单、许可账在不在；给名字打年代、逐 IDS 的提供者与缺省 |
| `experiments [<machine> [<shot>]]` | 语料里的炮与片数；给到炮号打逐片的时刻表 |
| `scenarios [<name>...] [--line L]` | 场景：线、code、今天门认不认、参数个数；给名字打参数表全表、开关与端口 |
| `presets [<name>...] [--line L] [--scenario S]` | 语料里的具名计划；给名字打那份计划文档 |
| `facts [<domain>] [--roots]` | 两条搜索路径：facts 与算例语料，逐条说是谁供的；自带的那一档打成 `<bundled>` 并报条数 |
| `kernel` | 内核认哪些 code、哪些 entry、各自的声明块 |
| `lines` | 四条线与各自的缺省场景 |

组级选项 `--facts PATH` · `--cases PATH` · `--kernel PATH` · `--json`。

★`scenarios` 的「今天」一列装内核来答；**装不上不是错**，那一列改说目录里记的判定，
其余照打。

## `fy data` —— 数据层

七条子命令：`info` / `dump` / `convert` / `merge` / `assemble` / `fetch` / `tables`，
外加组级选项 `--facts PATH`。它能读哪些源、写哪两种布局、`--time` 怎么写、为什么
MDSplus 只读——**单开一页**：[数据层](data-layer.md)。

(fylite-cli-migration)=
## 从前的 `case` 今天怎么写

`case` 与 `data facts` 已撤（`FYL-DESIGN-17` E-23 / E-24）。旧词**按名拒绝并指出去处**，
而不是静默转发——转发会让两个词长期并存，而那正是这次合并要消掉的东西。

| 从前 | 今天 |
| :--- | :--- |
| `fy case describe` | `fy list kernel` |
| `fy case plan P… --set k=v` | `fy run P… k=v --dry-run` |
| `fy case run P… --set k=v -o DIR` | `fy run P… k=v -o DIR` |
| `fy case json P…` | `fy run P… --json` |
| `fy data facts [域]` | `fy list facts [域]` |

★`--set` 整个撤了：`key=value` 就是它，只是多了模板校验。Rust 库模块 `crate::case`
（合成器）**留着**——撤的是命令词，不是合成器。

Python 侧同一道门是 `fylite.io.fydoc.case_json(plan, base=…)`：一份
`fyo:ScenarioSpecification` 进，一份 `spo:ComputationRecord` 出。

## 算例语料与 V&V 登记册

```python
from fylite.engine import cases
cases.catalogue()          # 列出语料里的算例
cases.load("zerod-iter-15ma")
cases.run("zerod-iter-15ma")
from fylite.engine import benchmark as bm
bm.records(); bm.problems(rec, d); bm.run("V-09")   # 公开 V&V 登记册
```

逐族示例见[典型算例](../examples/index.md)那一篇。

## 相关

- [命令行怎么用](../guide/cli.md) —— 按任务走的那一遍
- [数据层](data-layer.md) —— `fy data` 七条子命令详解
- [API 速查](api.md) —— Python 的入口地图
- 设计集 `FYL-DESIGN-15`（一份规格几个宿主）· `FYL-DESIGN-17`（`run` 与 `list` 的详细设计）
