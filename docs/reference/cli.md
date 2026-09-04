---
title: 命令行 (Command Line Reference)
---

# 命令行

装上包就有 `fylite`；`python -m fylite` 是同一个入口。本页是**全表**——每条命令、它属于
哪一类、由谁承载。要按任务走一遍，看用户指南的[命令行怎么用](../guide/cli.md)。

## 一份定义，三个宿主

命令行的**定义**只有一处：`python/fylite/_cli.json`（`FYL-DESIGN-15`）。

| 宿主 | 是什么 | 怎么用这份定义 |
| :--- | :--- | :--- |
| `fylite` | Python 控制台脚本 | 运行期读它，建出 argparse |
| `fylite` | **唯一的可执行文件**（Rust） | 编译期纳入它，建出自己的解析器 |
| 浏览器页面 | 静态站点 | 它的 `hosts.app.params` 就是页面的启动参数 |

所以 `fylite app --help` 与 `fylite --help` 读到的是同一份用法，只是排版不同——不是
两份文字碰巧一致。只属一个宿主的参数在定义里标了 `hosts`：`--bin-dir` 只有 Python 有，
`--app-dir`（伺服一棵活目录，开发用）只有 Rust 有。

## 十四条命令

```bash
fylite --help
# —— Python 宿主自己实现的（十一条）——
fylite run --east --shot 70754 --time 3.5     # 一次平衡反演（Rust inverse）
fylite plot g137985.04000 -o flux.png         # 渲染 g-file 的磁面图
fylite describe [--text]                      # 能力目录（JSON-LD）；--text 含环境变量面
fylite cases [ID] [--check|--plan|--run]      # 算例语料（与 --benchmark 的 V&V 登记册）
fylite cases --report ID [--from REC] [--lang en]   # 算例报告：MyST + SVG
fylite manifest [--seal]                      # 核对 / 重封制品清单
fylite replay LEDGER · report RUN · whence FILE · alias RUN NAME
fylite serve                                  # JSON-RPC 2.0 over stdio
fylite mcp                                    # MCP stdio 服务器
# —— 那个可执行文件承载、Python 逐字委托的（三条）——
fylite app  [--port N] [--no-open] [--mdsip HOST:PORT] [--page P] [--device D] [--lang L] [--theme T]
fylite data info|dump|convert|merge|assemble|fetch|tables …
fylite case describe|plan|run|json …
```

★`run` 走 Rust inverse（`engine.serve.run_reconstruction`）；EFIT 血统的驱动与
`libefit.so` 不在本分发里。★`describe` / `manifest` / `serve` / `mcp` 四条**不依赖内核**，
`fylite.engine` 导入期是纯 stdlib 的。

### 委托：三条命令，一个可执行文件

`app` / `data` / `case` 在 Python 里**不重写第二份实现**：`fylite` 找到那个可执行文件
（`--bin-dir` → 包内 `_bin/` → `$PATH`），**把命令词放回最前面**，其余的字原样交过去。
找不到时它按名说明要构建什么并**退出 2**——不退化成一个能力更少的 Python 实现。

:::{note}
**为什么只有一个可执行文件。** 2026-09-03 之前还有 `fylite-data` 与 `fylite-case` 两个
二进制。它们各十行，做的就是把 `data` / `case` 前置到自己的命令行再调用同一份代码——
而那一次前置由调用方给就够了。于是它们撤掉，`fylite` 成为唯一的可执行文件：
不带子命令时它跑 `app`（起服务、开浏览器），所以双击仍然可用；带命令词时它就是那条命令。

```bash
fylite data info shot.h5        # 经 Python 宿主
fylite data info shot.h5    # 直接调那个可执行文件——同一份代码
```
:::

## `fylite cases` —— 两份语料，一个动词

```bash
fylite cases                        # 列出 cases/ 的 25 条算例
fylite cases <id>                   # 打印那份计划（fyo:ScenarioSpecification）
fylite cases --check                # 结构检查（词汇只有 fyo / spo，无孤儿文件）
fylite cases --plan  <id>           # 只映射不跑：控件 -> 入口字段的完整账
fylite cases --run   <id> [--predict]
fylite cases --report <id> [--from DIR] [--out DIR] [--presentation SPEC] [--lang zh|en]

fylite cases --benchmark            # 公开 V&V 登记册：类 · 结论 · 复测 · 纳入类别
fylite cases --benchmark <ID>       # 一条 fyo:ComparisonRecord
fylite cases --benchmark --check
FYLITE_KERNEL=../fylite_kernel fylite cases --benchmark --run V-09   # 该记录的私仓门
```

逐族示例见[典型算例](../examples/index.md)那一篇。

## `fylite data` —— 数据层

七条子命令：`info` / `dump` / `convert` / `merge` / `assemble` / `fetch` / `tables`。
它能读哪些源、写哪两种布局、`--time` 怎么写、为什么 MDSplus 只读——**单开一页**：
[数据层](data-layer.md)。

## `fylite case` —— 一份计划进，一份记录出

直通内核单入口 `fylite_rs_fyo`，不经 Python 装配：

```bash
fylite case describe
fylite case plan <plan.jsonld>... [--set k=v]... [--bind port=path]...
fylite case run  <plan.jsonld>... --record DIR [--format jsonld|hdf5|netcdf|imas-hdf5]
fylite case json <plan.jsonld>...        # 一份计划进，一份记录出（stdout）
```

多份计划按序合成（后者覆盖前者，`--set` / `--bind` 最后）。★`--format imas-hdf5`
（或计划自己在输出端口上要 `fyo:ImasHdf5Format`）写出**一个 IMAS 数据入口**：
`imas/master.h5` + 逐 IDS 的 `<ids>.h5`。

★**跑不成的算例也回一份记录**（`run_state: rejected`，内核的话在 `comment` 里），
不是抛一个异常：一份跑不了的计划必须说出它缺什么。

Python 侧同一道门是 `fylite.io.fydoc.case_json(plan, base=…)`：一份
`fyo:ScenarioSpecification` 进，一份 `spo:ComputationRecord` 出，产出数据集内联在端口上。

## 相关

- [命令行怎么用](../guide/cli.md) —— 按任务走的那一遍
- [数据层](data-layer.md) —— `fylite data` 七条子命令详解
- [API 速查](api.md) —— Python 的入口地图
- 设计集 `FYL-DESIGN-15` —— 一份规格三个宿主，以及每条裁定的理由
