---
title: "V&V 登记册 (The V&V Register)"
---

# `benchmark/` — 公开 V&V 登记册

这里回答一个问题：**fylite 对着外部答案量过什么，各自量到多少。**

源码不公开，所以「我们测过了」这句话本身没有分量——能替代它的只有**可复算的记录**：
输入是什么、参考是谁、判据是什么、量到多少、哪一部分不可比。

The kernel's source is not published, so "we tested it" carries no weight on
its own. What replaces it is a **recomputable record**: the inputs, the
reference, the criterion, the measured number, and the part that is not
comparable.

:::{warning}
★★★**本册 2026-09-16 重起**（用户裁定）。上一本在 `docs/benchmark-legacy/`：
**已移出版本控制**，磁盘留一份仅供查阅，不再维护、不入站点、不接受新记录。

★**目录名沿用，语义已变**。十余处跨仓引用（`FYL-SDD-01/-02/-07/-08/-09` ·
`FYL-CONOPS-00` · 内核 `docs/cases/registry.jsonld` · fydoc `FYDOC-CASE-23` 页）
硬编码着 `docs/benchmark/`，沿用原名是为了不打断它们——但它们指向的**是这本新册**。
旧册的记录编号（`B-01`..`V-23`）是上一套体系，与本册不通用；各章散文里点到它们时，
一律标着「已退役、仅存盘」，那是**历史证据**，不是本册的记录。

★旧册退役的代价，如实记：已发布站点的 54 个报告 URL 失效；随它一并退役的还有
物理校验册（`benchmark/physics/` 8 页）与仓根 `BENCHMARK.md`。**判据库本身没有退役**
——`fylite.engine.physics` 的判据仍由 `python/tests/test_physics_checks.py` 等门守着，
只是不再产出一本给人读的册子。
:::

## 为什么重起：旧册的记录追溯不到需求

实测旧册 52 条记录里，`FR-*` / `NR-*` **零命中**——没有一条说得出"我在验哪条需求"。
于是"覆盖够不够"只能靠人工比对需求表，而人工比对每次给的答案都不一样。派生的毛病
（真源两处、索引手写漏条、`scenario` 30/52、sha256 40/52）都是同一个缺失的下游。

## 组织轴：物理专题，两级

本册按**物理专题**组织，分两级——一级三组，二级十六章，每章一页：

| 组 | 章 | 上游 | 答什么 |
| :--- | ---: | :--- | :--- |
| [平衡 (Equilibrium)](domains/eq/forward.md) | 6 | `FYTOK-SRS-03` · fyeq | 磁面在哪里，算得准不准 |
| [MHD 稳定性 (Stability)](domains/mhd/vertical.md) | 4 | `FYTOK-SRS-03` · fyeq | 这个位形稳不稳 |
| [输运 (Transport)](domains/tr/equations.md) | 6 | `FYTOK-SRS-04` · fytrans | 剖面怎么演化，闭包对不对 |

★**MHD 稳定性单列一组，虽然它在 SRS 里属 fyeq**。它是三十七条 EQ 需求里的十八条，
篇幅与另两组相当，而它问的是另一个问题：位形稳不稳，不是平衡算不算得准。
组件归属记在 [`meta/domains.jsonld`](meta/domains.jsonld) 每组的 `component` / `srs` 上，追溯不丢。

★★**需求号不是轴，是记录的属性。** 上一版设计按 `FR-EQ-*` / `NR-TR-*` 编址，那有一处
致命伤：上游两份 SRS 都标着 `distribution: internal`，本册的读者**打不开它们**。
本册开篇立的规矩是「源码不公开，所以『我们测过了』没有分量」——同一条逻辑打在引用上：
**需求不公开，那么『本条覆盖 FR-EQ-016』对读者同样没有分量，它只是一个不可解的记号。**
所以本册改为按读者读得懂的专题组织，而把需求号降为每条记录的 `requirement[]` 字段。

## 判据：抄录，不是引用

判据来自上游 SRS 自己的〈验证基准〉与〈验证矩阵〉，**逐字抄进本册**，落在
[`meta/transcript.jsonld`](meta/transcript.jsonld)，由各章的生成块渲染出来。

★**抄录的代价是漂，所以配了一道闸**：抄录件记下每份源的版本号与 sha256
（现记 `FYTOK-SRS-03` v0.43 · `FYTOK-SRS-04` v0.11，两份都还是 `status: WD`）。
源一变，`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。
**手抄一次然后忘掉，比引用更坏——引用至少永远指向最新版。**

★上游没给判据的需求，本册**照实标出来**（现有 1 条：`FR-TR-014` 0D 存量守恒，
SRS-04 的验证矩阵里没有它的行）。没有判据就无从验起——那是上游的缺口，遮住它等于替它掩过。

## 三类对比：由「参考是什么」决定

| 类 | 问的是 | 参考是什么 | 容差取法 |
| :--- | :--- | :--- | :--- |
| **verification** 验证 | 这段代码算的是不是它声称的那个函数 | 同一函数的另一实现，或解析解 | 机器精度 |
| **benchmark** 对拍 | 两套**不同模型**在同一状态上给的数差多少 | 另一个码的一次运行 | 实测后定带 |
| **validation** 确认 | 模型对不对得上**实验或权威参考算例** | 实验数据 / 机构参考算例 | 物理带，取参考自报精度 |

★**一条记录属于哪一类，由「参考是什么」决定，不由做得多认真决定。** 把对拍说成验证
是最常见的夸大：两套模型吻合到 1 % 不等于移植正确——两个错误也能互相抵消。

★类别写在记录的 `comparison_kind` 字段里，**不编进编号**。旧册的 `B-` / `C-` / `V-` 前缀
把类别编进了标识，于是一条记录改类就要改号。

## 编号：按域编址

`<域id>-<短名>`，例如 `eq-forward-solovev` · `mhd-vertical-rigid-wall` · `tr-paradigm-flux-matching`。
域 id 取自 [`meta/domains.jsonld`](meta/domains.jsonld)（`eq-forward` · `mhd-deltaw` · `tr-closure` …）。

## 一条记录必须自带的六样

前四样承自旧册（那部分是对的），第五、第六样是本册新加的：

1. **输入** ——不是只有答案。读者要能看出「问的是什么问题」；
2. **出处** ——上游包名、版本、文件名与 **sha256**；一次运行还要记日期；
3. **口径** ——单位、坐标标签、符号约定（COCOS），以及**径向标签**（`ρ` 还是 Miller `r`）；
4. **不可比的部分** ——参考解了哪几道方程、哪些量是**喂进去的**而不是算出来的；
5. ★**需求** ——`requirement[]` 列出它验的需求号。**缺这一项的记录不收**，因为
   一条不知道自己在验什么的记录，无法回答"覆盖够不够"；
6. ★★**追溯** ——`provenance`：记录版本、末次修订、**评审人与评审结论**、**逐条变更**，
   外加 `run.kernel`——**这次验证跑在哪个内核上**。

★★**第六样是本册与旧册最大的差别，理由是一条记录会被改判。** 上一册的 `V-23` 就改判过
两次：先把 τ 的差归给导电接头，查明后改为超导线圈屏蔽。改判是记录制度**在起作用**的证据，
不是它的污点——所以改判本身必须留在册里，而不是把旧结论悄悄覆盖掉。
`change[]` 记的就是这个。

★`run.kernel` 是给[状态页](status.md)用的：一条记录成立过，不等于它现在还成立。
内核换了，它量的那个数就可能已经不是现在算出来的那个了。

模板见 [`records/TEMPLATE.jsonld`](records/TEMPLATE.jsonld)，逐条闸子在
`python/tests/test_benchmark_register.py`。

## 三张生成件，各答一个问题

★**它们不是同一张表的三种排版**：

| 页 | 只答 | 谁写 |
| :--- | :--- | :--- |
| 各域章页 `<组>/<域>.md` | 这一域**对着谁量到多少** | 散文手写 + 生成块 |
| [`coverage.md`](coverage.md) | **够不够**（需求 × 记录，空行即缺口） | ★生成 |
| [`status.md`](status.md) | 这些记录**还作不作数**（版本 / 评审 / 内核 / 新鲜度） | ★生成 |

## 目录

★★**目录的分界就是「谁读它」**，不靠扩展名去猜：册子根上是**给人读**的书（导言 + 两张
生成件 + 三组十六章，也正是入 `myst.yml` 的那些）；数据在三个各有一职的目录里。

```
docs/benchmark/
├── README.md                  ← 你在读的这页
├── coverage.md · status.md    ← 两张生成件
├── domains/                   ← 三组十六章，一章一页散文（`eq/` `mhd/` `tr/`）
├── reports/                   ← 逐条报告：一条记录一份，★由记录生成
├── figures/                   ← 余量图：一条记录一张，★由记录生成
├── summary/                   ← 收敛说明：一轮一页，手写
├── records/                   ← 记录：一条一个文件（正本）
├── readings/                  ← 读数：门与工具的产出
└── meta/                      ← 轴、抄录件、词表、索引、基准内核
```

| 路径 | 装什么 | 谁写 |
| :--- | :--- | :--- |
| `domains/<组>/<域>.md` | 十六章：这一域对着谁量到多少 | 散文手写 + 生成块 |
| `coverage.md` | 需求 × 记录，空行即缺口 | ★生成 |
| `status.md` | 版本 / 评审 / 内核 / 新鲜度 | ★生成 |
| `reports/<ID>.md` | 逐条报告：固定六节，一条记录一份 | ★生成 |
| `figures/<ID>-headroom.svg` | 余量图：每条判据离它的带还有多远 | ★生成 |
| `summary/<日期>-<组>.md` | 收敛说明：一轮做了什么、收敛到什么 | 人 |
| `records/<ID>.jsonld` | 一条记录一个文件（**正本**） | 人 + 工具 |
| `records/TEMPLATE.jsonld` | 记录模板：六样必备项逐条注明 | 人 |
| `readings/<名>.json` | 读数。★**按写它的那道门 / 工具命名**（`wall_iter.json`），不按记录号——写它的工具比记录先在 | 门或工具产出 |
| `meta/domains.jsonld` | 域树：一级 3 组 / 二级 16 章 | 人 |
| `meta/requirements.jsonld` | 需求树快照（57 条），每条标着它落在哪一章 | 自 SRS 抽取 |
| `meta/transcript.jsonld` | 判据**抄录件** + 源版本与 sha256 | ★生成 |
| `meta/kernel.json` | 基准内核指纹（新鲜度以它为准） | ★`--bump-kernel` |
| `meta/index.jsonld` | 薄索引 | ★生成 |
| `meta/context.jsonld` | fyo / spo 词汇 | 承自旧册 + 新项 |

★**一条记录一个文件**，不再是一份 481 KB 的 `registry.jsonld`：那样改一条记录的 diff
会扫全库、并发改必冲突。

★★**这张表里没有的目录，盘上也没有。** `records/retired/`（退役记录）**首次需要时再建**——
一个声明了却不存在的目录，读者按它去找只会扑空，而「声明与实际不符」正是旧册烂掉的方式之一
（它的 `reports/README.md` 漏掉最后一条记录，同一个病）。这一条由
`test_the_tree_on_disk_is_the_tree_the_readme_declares` 两个方向都守着。

## 逐条报告与收敛说明：两样东西，两种写法

★★2026-09-16 用户裁定「records 逐条配以测试报告且收入 myst」「benchmark 开目录收敛说明散文」。

**`reports/<ID>.md` 由记录生成，不手写。** 一条记录一份，章节固定六节、次序不可变
（摘要 · 问的是什么 · 判据与量到多少 · 不可比的部分 · 追溯 · 复算），体例承自
[运行报告模板](../reference/report-template.md) 的规矩：读过一份就读过了所有份，
而第一节必须能让人决定要不要往下读。

★**为什么必须生成**：手写的报告会与记录漂开——改一条记录的 finding 而忘了改它的报告，
读者就会在同一件事上读到两个数。**正本是 `records/<ID>.jsonld`，报告只是它的可读面。**
报告页挂在它所属的**域章**下面（书的轴是域）；漏挂 toc 由入册闸抓。

**`summary/<日期>-<组>.md` 由人写。** 它交代一轮工作**收敛到了什么**——哪些话站得住、
哪些不站、下一轮从哪儿接。★它是**快照，不是正本**，半衰期很短：下一轮补一页，
**不改写上一页**。记录才是正本，而记录带着自己的变更史。

★**生成件不手改**。`coverage.md` 手写过一次就会漏——旧册的 `reports/README.md`
漏掉最后一条记录，正是因为它是手维护的索引。

## 现在是什么状态

**本册尚无记录**，十六章的缺口栏与 [`coverage.md`](coverage.md) 上的空行如实摆着。
这不是过渡态的尴尬，是重起的应有之义：**闸子先立，记录后进。**
每一条进来的记录都要过 `python/tests/test_benchmark_register.py` 那几条判据，
而不是进来之后再补手续。

```bash
python tools/benchmark-transcribe.py --check   # 上游 SRS 动了没有
python tools/benchmark-book.py --check         # 生成件是不是最新的
python tools/benchmark-book.py --ci            # 有过期或不成立的记录就退 1
```
