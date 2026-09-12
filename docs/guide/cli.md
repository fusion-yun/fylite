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

## 跑一次算例

一条线（`analysis` · `model` · `design` · `control`）选出缺省场景，场景的**模板**给出
参数表，`--preset` 从算例语料里取一份具名计划盖上去：

```bash
fy run model --preset zerod-iter-15ma -o rec/
```

产物落在 `rec/`：合成好的计划、记录，以及每个输出端口一份数据集。实测（2026-09-07，
本仓检出）：

```console
$ fy run model --preset zerod-iter-15ma -o rec/ --quiet
$ ls rec/
core_profiles.fyo.jsonld  entry.fyo.jsonld  plan.jsonld  record.jsonld  summary.fyo.jsonld
```

逐条可跑的命令行与它们各自的产物，见[典型算例](../examples/index.md)每一章的
〈命令行〉一节。

:::{warning}
**装置类算例今天从命令行跑不起来**，两个原因各自独立，都实测于 2026-09-07：

1. **本仓没有任何装置的清单文档**。`facts/device/<id>/` 里只有 `rights.json`；
   `abox/device.jsonld` 在 fydoc。所以 `--device east` 会说
   「has the entry but no abox/device.jsonld … described by a card, not by a manifest」。
   把带清单的语料根前置（`FY_FACTS_PATH=…/facts`）可以解决这一条。
2. ~~拿到清单也还不够：那一族 code 只经树门到达，而 `fy run` 走扁平门。~~
   **2026-09-07 已修**：`fy run` 现在走**树门**（`fylite_rs_fyo_tree`），与浏览器和
   Python 侧同一扇。`code/breakdown` · `code/discharge` · `code/reconstruction` 等
   十八个吃整份文档的 code 从此在命令行上到得了——见
   [装置信息](../examples/device/device.md)那一章，EAST 的通道图就是这么补全的。
   ★三档已走通的算例（0-D · 输运 · 演化）在两扇门下**每一份产出文档逐字节相同**，
   换门没有换数。

★`fy list scenarios` 的 `today` 一列量的是**内核门认不认这个 code**。它与
「`fy run` 跑不跑得完」自 2026-09-07 起重新对齐，但仍不是同一件事：一个 code 到得了，
不等于这一档的输入齐了（装置清单、测量、必需参数各自另说）。
:::

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

★它是**唯一不受上面两条限制**的一档：合成与解析都在本层，不进内核，所以装置类算例
也能先用 `--dry-run` 看清楚。实测（前置一个带清单的语料根）：

```console
$ FY_FACTS_PATH=…/facts fy run analysis --device east shot=137985 time=4.0 \
      --only-magnetic --dry-run
analysis · reconstruction  ->  code/reconstruction   (template …, 46 parameters declared)
  device   east from …/facts  -> (would assemble from …/facts/device/east/abox/device.jsonld)
  record   records/20260907T060647Z-reconstruction  (not written: --dry-run)

  parameter            value                  from
  basis                "delivered"            template:reconstruction
  maxit                800                    template:reconstruction
  kin                  false                  cli:switch only_magnetic
  neon                 false                  cli:switch only_magnetic
  …
  input device         (would assemble from …/device.jsonld)   device:east@…/facts
  input measurements   (not fetched)          would fetch: device=east shot=137985 time=4.0
                                              ids=[magnetics, pf_active, tf] via the manifest's own server
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

## 记录目录里有什么

一次跑完的目录是**自足**的：计划、记录，加每个输出端口一份数据集。缺省
`--format jsonld`：

```console
$ fy run model --preset transport-iter-15ma -o rec/ --quiet
$ ls rec/
core_profiles.fyo.jsonld  core_transport.fyo.jsonld  entry.fyo.jsonld
equilibrium.fyo.jsonld    plan.jsonld                record.jsonld
```

`--format imas-hdf5` 改写成**一个 IMAS 数据入口**——`imas/master.h5` 加每个 IDS 一个
文件，`master.h5` 用外部链接指向它们：

```console
$ fy run model --preset evolve-iter-15ma -o rec/ --quiet     # 这份预设自己就绑 imas-hdf5
$ find rec -type f | sort
rec/entry.fyo.jsonld       rec/imas/core_transport.h5  rec/imas/master.h5   rec/record.jsonld
rec/imas/core_profiles.h5  rec/imas/equilibrium.h5     rec/imas/summary.h5  rec/plan.jsonld
```

★`entry.fyo.jsonld` **不在** `imas/` 里，两种格式下都留在记录目录顶层：它是内核原始
条目块（`@type: fyo:entry`），寻址不到任何 IDS，DD 里没有它的位置。写入方按名把它**放到
一边**，并在记录里以 `ld+json` 登记——数据入口只装 IDS。
（2026-09-07 之前写入方是**拒绝**它：`--format imas-hdf5` 因此在每个 code 上都中途失败，
IDS 文件已落盘而 `record.jsonld` 未写，留下一个没有标签的碎片。）

每份数据集在 `record.jsonld` 里都有一条产出端口绑定，带 `storage_uri` 与 `sha256`；
记录怎么读见[结果怎么读](reading-results.md)。

## 接着上一次跑

一次多步运行的记录带着**它收尾时的状态**（`fylite:state`：内核声明的交接标量，加
产出文档的指针）。把那个记录目录交给 `--resume-from`，下一次就从那里接着走：

```console
$ fy run docs/examples/evolve/evolve-default.jsonld nsteps=20 -o rec/a
$ fy run docs/examples/evolve/evolve-default.jsonld nsteps=20 --resume-from rec/a -o rec/b
```

★**判据**：`nsteps=40` 一次跑完，与 `20` 加续 `20`，在这条算例上**逐位相同**
（闸子 `python/tests/test_resume.py`）。

★**范围要说清**：`code/evolve` 的三条滞后量（`psi_prev` / `sigma_prev` /
`exch_prev`）今天**交不过去**——内核从 `evolve/fylite:*` 读它们，却写在自己的原始
条目块里，而中间层只把声明过的表里的槽压进扁平树（`FYL-DESIGN-16` F-2 / G-8）。
所以续跑时 `lag_reset` 会被打开（内核自己的词：「状态被重映射，首步不加欧姆项」），
命令行上说一句，计划里留痕。常数闭合下它们是死的（故逐位）；开了新经典闭合，
同一个比法 Te 差 **61 %**——那不是这条命令的缺陷，是 G-8 的大小，在册。

★写它的内核与手边这一份不是同一份字节时**按名拒绝**（K-7 / S-6）；
`--allow-kernel-drift` 显式放行，并把这件事写进新记录。

Python 那一端**读**同一个子树：

```python
from fylite.engine import resume
st = resume.carried("rec/a")        # settings · documents · step · t · lag_reset
resume.kernel_of("rec/a")           # 写它的内核指纹（K-7）
```

★★**只读**：`cases.run` 没有 `resume=`。交接单里的名字是**内核声明的**参数，而
`fylite.scenario` 那些入口收的是**它们自己的**一套——实测 `evolve` 的 39 个参数与
交接单的 10 个标量一个都不重合。装配层、原始入口、Python 入口是**三套**命名，而
code 那一层没有一处声明它收什么（`FYL-REPORT-07` C-28）。所以续跑走上面那条命令行，
它经文档门，名字是内核的。

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
没有网络的机器上照样答得出来。九条逐条实测（2026-09-07）全部返回 0。

:::{note}
**装置信息编在二进制里。** `fy list facts --roots` 会列出两条根：检出的暂存语料
（自可执行文件位置上溯探得的 `dist/facts/`）与编进这份二进制的那一份——**两条都打
`<buildin>`**，后面各带一句是哪一种。★2026-09-08 用户裁定：**构建期的路径不出现在
输出里**——它说的是构建这份二进制的那台机器的目录布局，读者既打不开也不该看见。
落在内置根里的文件因此写成 `<buildin>/device/east.jsonld`：**哪一份**仍然说得出。
`--facts` / `$FY_FACTS_PATH` 给进来的根照打（`$HOME` 收成 `~`）——回显它，是在回答
「我给的那个根生效了吗」。`--json` 那一面不受这条影响：机器要的是能直接打开的路径。

```console
$ ./fy list facts --roots
1. <buildin>   (检出暂存区，盘上的那一份)
2. <buildin>   (7 条，编在这份二进制里)
$ ./fy list devices | tail -1
facts: <buildin>
```

把二进制拷到检出之外，第一条就没有了。

★**内部版也只带六台**（best · cfedr · cfetr · iter · jt60sa · west），实测。判据在
`tools/facts-publish.py`：**没有页面文档就不发**——本仓 `facts/device/<id>/` 里只有
`rights.json`，清单文档在 fydoc，所以那七台（含 EAST）在任何版别里都发不出去。
「内部版含 EAST」这条裁定要落地，缺的是把清单文档带进发布物，不是版别开关。
:::

## 换一份数据的格式，或取一发炮

数据层是一条命令词底下的七条子命令（`info` · `dump` · `convert` · `merge` ·
`assemble` · `fetch` · `tables`，另有组级 `--facts PATH`）：

```bash
fy data info    shot.h5                        # 这是什么文件
fy data convert g063982.04800 shot.nc --layout imas    # imas-python 打得开
fy data merge   machine.h5 shot.nc -o all.jsonld       # 后者覆盖前者
fy data fetch   --device east --ids magnetics \
                --shot 138569 --time 4:5 -o east.json  # 取一发炮的磁测量
```

它能读哪些源、两种布局分别是什么、`--time` 怎么写、为什么 MDSplus 是只读的——
参考篇的[数据层](../reference/data-layer.md)一页讲完。

★★**`convert` 的产物是文件，它打印的那几行是诊断，走 stderr。**「写了什么、
哪些量没进去、哪几支是算出来或改名来的」都在那里；`fy data convert … > out.txt`
里因此**什么也没有**，要留报告就重定向 stderr（`2> report.txt`）。
`info` · `dump` · `tables` 答的是问题本身，走 stdout，管道接得上。

★★**`list` 的每一种形都认 `--json`**——清单形与点名形都认
（`fy list devices --json` 与 `fy list devices east --json` 都答 JSON）。
2026-09-07 之前点名形静默忽略它：声明了却不生效，调用方拿到的是给人看的排版
而退出码 0。现在由 `python/tests/test_list_json.py` 逐形守着。

★`fy run` 在给了 `shot=` 而语料里没有那一片时会**自己**去取（取回的文档先落进记录
目录，于是同一次分析可以离线重放）。要它永不联网，给 `--offline` 或设
`$FYLITE_OFFLINE=1`。

## 起浏览器演示

```bash
fy app                                   # 找一个空闲端口，起服务，开浏览器
fy app --port 8123 --no-open             # 只伺服
fy app --page data --device east --lang en --mdsip 127.0.0.1:8000
```
