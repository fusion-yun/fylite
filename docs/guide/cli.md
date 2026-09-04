---
title: 命令行 (Using the Command Line)
---

# 命令行

命令行只有一个，它叫 **`fy`**，是本仓 Rust 中间层的产物：

```bash
bash rust/build.sh --exe          # -> rust/fylite_runtime/target/release/fy
fy --help
```

它承载四条命令词，各是一个动词：**`app`** 起浏览器演示、**`data`** 搬数据、
**`run`** 算一个算例、**`list`** 看有什么可用。不带命令词时它跑 `app`，所以双击也可用。
逐条参数的全表在参考篇的[命令行](../reference/cli.md)。

:::{important}
**Python 包没有命令行**（2026-09-04 用户裁定）。`pip install fylite` 装的是一个**库**：
没有 `fylite` 这条控制台脚本，没有 `python -m fylite`，也没有 `engine/cli.py` 那一层。
:::

:::{note}
**`case` 已经收进 `run`**（同日第二条裁定）。`fy run` 的位置参数既收线与场景，也收
计划文件，所以从前 `fy case run plan.jsonld` 那一行今天写作 `fy run plan.jsonld`——
同一个合成器、同一条门、同一份记录。旧词按名拒绝并指出去处，不会静默地跑成别的东西：

```console
$ fy case run plan.jsonld
fy: `case run` is retired — use `fy run <the same plans>`
```

逐条对照的迁移表在参考篇的[命令行](../reference/cli.md)。
:::

## 跑一次日常分析

一条线（`analysis` · `model` · `design` · `control`）选出缺省场景，场景的**模板**给出
参数表，装置与炮号由命令自己解析：

```bash
fy run analysis --device east shot=137985 time=4.0 --only-magnetic=true -o rec/
```

读作：在实验分析线上跑缺省场景（平衡反演），装置取 facts 语料里的 EAST，测量取
第 137985 发炮 4.0 s 那一片，`--only-magnetic` 这一个开关把六个拟合开关一起关掉。
产物落在 `rec/`：合成好的计划、用到的装置与测量文档、记录，以及每份数据集。

**参数就写在命令行上**，四种写法同义：

```bash
kin=false          --kin=false          --no-kin        # 布尔
chi0=0.4           --chi0=0.4                           # 数
basis=delivered    --basis=delivered                    # 字符串（模板限定取值时按名校验）
```

名字里的 `-` 与 `_` 是同一个字符，所以 `--only-magnetic` 与 `only_magnetic=true`
是同一件事。**值要用 `=`**：`--chi0 0.4` 中间的空格会让 `0.4` 被当成第二个场景名。

参数**不在**这份命令行规格里，它属于场景（一份模板文档）。敲错了当场按名拒绝，
并给出最接近的几个名字：

```console
$ fy run model transport chi_zero=0.4
fy run: transport: `transport` takes no parameter "chi_zero=0.4" — `fy list scenarios transport` prints the whole table
```

## 先看一眼会发生什么

`--dry-run` 合成计划并把每个值**从哪来**逐行打出来，然后停下：不取数、不装内核、
不写任何文件。

```console
$ fy run analysis --device east shot=137985 time=4.0 --only-magnetic --dry-run
analysis · reconstruction  ->  code/reconstruction   (template …, 46 parameters declared)

  parameter            value                  from
  basis                "delivered"            template:reconstruction
  maxit                800                    template:reconstruction
  kin                  false                  cli:switch only_magnetic
  …
  input measurements   …/slice_04000ms.fyo.jsonld   resolved:experiment/east/137985@… (t=4 s)
```

来源那一列是六层合成的次序：模板缺省 → 装置 → 预设 → `--plan` → 命令行 → 端口绑定，
后者盖前者。同一条命令行上**显式给的参数永远胜过开关展开的值**。

## 从一份计划跑

给路径就是计划文件形（从前的 `fy case run`）；多份按序合成，后者覆盖前者：

```bash
fy run docs/examples/transport/transport-iter-15ma.jsonld chi0=0.55 -o rec/
fy run base.jsonld override.jsonld --bind measurements=meas.json -o rec/
```

★跑不成也**回一份记录**（`run_state: rejected`），并写明是哪一步缺的：`compose` ·
`device` · `measurements` · `kernel`。退出码 0 跑完 / 1 拒绝（有记录）/ 2 语法错（无记录）。

## 有什么可用

```bash
fy list lines                     # 四条线与各自的缺省场景
fy list scenarios --line analysis # 这条线有哪些场景、今天能不能跑
fy list scenarios reconstruction  # 一条场景的参数表全表、开关、端口
fy list devices                   # facts 里有哪些装置，卡片还是清单，许可账在不在
fy list devices east              # 一台的全部：年代、逐 IDS 的提供者与缺省
fy list experiments east 137985   # 这发炮语料里有哪几片
fy list presets                   # 语料里的具名计划
fy list facts                     # 两条搜索路径：facts 与算例语料
fy list kernel                    # 内核认哪些 code、哪些 entry
```

`list` 是**只读**的：它不合成、不取数、不写记录，也不开套接字，所以在没有内核、
没有网络的机器上照样答得出来。

## 换一份数据的格式，或取一发炮

数据层是一条命令词底下的七条子命令（另有组级 `--facts PATH`）：

```bash
fy data info    shot.h5                        # 这是什么文件
fy data convert g063982.04800 shot.nc --layout imas    # imas-python 打得开
fy data merge   machine.h5 shot.nc -o all.jsonld       # 后者覆盖前者
fy data fetch   --device east --ids magnetics \
                --shot 138569 --time 4:5 -o east.json  # 取一发炮的磁测量
```

它能读哪些源、两种布局分别是什么、`--time` 怎么写、为什么 MDSplus 是只读的——
参考篇的[数据层](../reference/data-layer.md)一页讲完。

★`fy run` 在给了 `shot=` 而语料里没有那一片时会**自己**去取（取回的文档先落进记录
目录，于是同一次分析可以离线重放）。要它永不联网，给 `--offline` 或设
`$FYLITE_OFFLINE=1`。

## 起浏览器演示

```bash
fy app                                   # 找一个空闲端口，起服务，开浏览器
fy app --port 8123 --no-open             # 只伺服
fy app --page data --device east --lang en --mdsip 127.0.0.1:8000
```
