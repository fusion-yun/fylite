---
title: 命令行 (Using the Command Line)
---

# 命令行

装上包就有一条命令：`fylite`。它把本仓的能力按**任务**分成十四条动词——跑一次反演、
出一份报告、转一份数据、起一个服务。本章按你可能想做的事走一遍；逐条参数的全表在
参考篇的[命令行](../reference/cli.md)。

```bash
pip install fylite
fylite --help
python -m fylite --help     # 同一个入口，装在别处时用得上
```

## 先看看它能做什么

```bash
fylite describe            # 能力目录（JSON-LD）：入口、各要什么、各给什么
fylite describe --text     # 同一份，人读的排版，含环境变量面
fylite cases               # 算例语料：25 条计划文档
```

`describe` 出的是**机器可读**的那一份——把 fylite 接进别的工具（含 AI 工具链）时读的
就是它。要把 fylite 接成一个服务，`fylite serve`（JSON-RPC 2.0 over stdio）与
`fylite mcp`（MCP stdio 服务器）各是一条；两者都**不依赖内核**。

## 跑一条算例，出一份报告

语料里的每条算例都是一份计划文档，可列、可查、可跑、可出报告：

```bash
fylite cases zerod-iter-15ma          # 打印那份计划
fylite cases --plan zerod-iter-15ma   # 只映射不跑：控件 → 入口字段的完整账
fylite cases --run  zerod-iter-15ma
fylite cases --report zerod-iter-15ma --out report/ --lang zh
```

★`--plan` 与 `--run` 之间那一步值得单独用一次：它把「页面上的一个控件」摊成「入口的
哪个字段」，跑之前就能看出映射对不对。逐族的完整走法见[典型算例](../examples/index.md)。

## 一次平衡反演

```bash
fylite run --east --shot 70754 --time 3.5     # 从 MDSplus 取测量
fylite run --input meas.jsonld --time 4.0 --out out/   # 从一份测量文档
fylite plot g137985.04000 -o flux.png        # 一份 g-file 的磁面图
```

判据、约束与结果怎么读，见[平衡反演](reconstruction.md)与[结果怎么读](reading-results.md)。

## 换一份数据的格式，或取一发炮

数据层是一条命令词底下的七条子命令：

```bash
fylite data info    shot.h5                        # 这是什么文件
fylite data convert g063982.04800 shot.nc --layout imas    # imas-python 打得开
fylite data merge   machine.h5 shot.nc -o all.jsonld       # 后者覆盖前者
fylite data fetch   --machine machine.yaml --ids magnetics \
                    --shot 138569 --time 4:5 -o east.json  # 取一发炮的磁测量
```

它能读哪些源、两种布局分别是什么、`--time` 怎么写、为什么 MDSplus 是只读的——
参考篇的[数据层](../reference/data-layer.md)一页讲完。

## 不经 Python 跑一个算例

`fylite case` 直通内核：一份 fyo 计划进，一份 fyo 记录出。

```bash
fylite case run plan.jsonld --record rec/ --format jsonld
fylite case json plan.jsonld            # 记录直接打到 stdout
```

★跑不成也**回一份记录**（`run_state: rejected`，缺什么写在 `comment` 里），而不是抛一个
异常：一份跑不了的计划必须说出它缺什么。

## 起浏览器演示

```bash
fylite app                                   # 找一个空闲端口，起服务，开浏览器
fylite app --port 8123 --no-open             # 只伺服
fylite app --page data --device east --lang en --mdsip 127.0.0.1:8000
```

页面上的能力见[浏览器演示](browser-app.md)。

## 一次运行之后：溯源与命名

一次运行留下的是一条底账，不是一堆散落的文件：

```bash
fylite report  <run> --out report/    # 把一次运行渲染成 MyST 报告
fylite whence  flux.png               # 这个文件是哪次运行产的，那次运行从哪来
fylite alias   <run> baseline@v1      # 给一次运行起个人记得住的名字
fylite replay  <ledger>               # 按底账把一次会话重跑一遍
fylite manifest [--seal]              # 核对（或重封）制品清单
```

★`whence` 的**退出码就是判词**：一个追不到运行的文件以非零退出——「找不到」是流水线
必须能据以行动的结果，不是一行要人去读的字。

## 三条命令是转交出去的

`app` / `data` / `case` 的实现在一个 Rust 可执行文件里，Python 侧**不重写第二份**：
它找到随包带的那个可执行文件（或 `--bin-dir`、`$PATH`），把命令词放回最前面，
其余的字原样交过去。没找到时它**按名说明要构建哪一个**并以退出码 2 结束，而不是
退化成一个能力更少的实现。

所以 `fylite data --help` 与 `fylite data --help` 读到的是同一份用法——两边由同一个
定义文件建出，不是两份文字碰巧一致。

:::{note}
**只有一个可执行文件。** 2026-09-03 起 `fylite-data` / `fylite-case` 两个二进制已经撤掉，
它们做的事（把命令词前置）由调用方给就够了。今天：一条 Python 命令 `fylite`，一个
Rust 可执行文件 `fylite`，两者用法同源。
:::
