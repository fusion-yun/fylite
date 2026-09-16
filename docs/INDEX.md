---
title: fylite 文档 (fylite Documentation)
---

# fylite 文档

fylite 是一个**自足的托卡马克平衡—输运—湍流内核**：一套 Grad-Shafranov 正逆解、
一步 1.5 维芯部输运、新经典与回旋朗道流体闭包，以及一条平衡重构链，写成**一个可
重入的 Rust 内核**；Python 层做装配与编排，浏览器端跑的是同一个内核编译出的
WebAssembly。三种发布形态跑的是同一份算术。

本书**一本四篇**。它们回答四个不同的问题，顺序就是读者一路问下去的顺序。

★★**本仓 `docs/` 只放读者面的文档**：公开仓 `docs/` 不出现开发文档与内部报告。下面三样因此在别的仓：

* **设计集**（`FYL-CONOPS-00` · `FYL-SRS-01` · `FYL-SDD-01` · `FYL-DESIGN-NN`）在 fylite_kernel `docs/design/`——它是开发文档；
* **报告**（`FYL-REPORT-07`）在 fylite_kernel `docs/report/`——评估研究是内部报告，`FYL-REPORT-NN` 这条编号序只有一处登记册；
* **物理与数值**（十五章 + `references.bib`）在 fydoc `physics/`——它**不是**开发文档，放在那里的理由是另一条：它写的是方程的出处、参数域的来历与对齐容差，那是 fydoc 「真实数据与事实的源头」那一职守下的东西。

跨仓引用一律写成**仓限定的行内代码**（形如 fylite_kernel `docs/design/INDEX.md`）；跨仓相对链接两侧都解析不了，**不要写**。

| 篇 | 回答什么 | 读者 |
| :--- | :--- | :--- |
| [用户指南](guide/index.md) | **怎么用**，以及**结果怎么读** | 拿它算东西的人 |
| [典型算例](examples/index.md) | 一条**从头到尾能照抄**的路径，五族各一章 | 要立刻跑出一个结果的人 |
| [参考](reference/fidelity.md) | 一个数**能不能用**：保真度边界、内核清单、调用面与命令行、判据与报告体例 | 要判断一个结果可不可信的人 |
| [校验册](benchmark/README.md) | 它**量过什么、量到多少**：按物理专题两级组织的对拍登记册（平衡 · MHD 稳定性 · 输运，十六章），配[需求覆盖表](benchmark/coverage.md)与[验证状态页](benchmark/status.md) | 要看证据而不是结论的人 |

★**先读哪一篇**：没用过就从[用户指南](guide/index.md)进；想直接照抄一条完整路径，去
[典型算例](examples/index.md)；手里已经有一个数、想知道它可不可信，去
[保真度边界](reference/fidelity.md)；要 Python 入口去 [API](reference/api.md)、
要命令行去[命令行](reference/cli.md)。
★要追到**方程与文献**，去 fydoc `physics/00-overview.md`；要知道**它为什么长这样**
（含接页面要读的 `FYL-SDD-01`），去 fylite_kernel `docs/design/INDEX.md`。

## 两样在本书之外的东西（都在本仓，但不是章）

它们在仓里，但**不是本书的章**——各有各的理由，不是遗漏：

- `app/` 的**浏览器演示** —— 那是**产品**，不是本书的一章。讲它的
  说明页在书里（[浏览器演示](guide/browser-app.md)），链接给的是已发布站点的地址。
- `NOTICE` —— 逐文件的移植出处与修改说明，随 Rust 内核源码留在 `fylite_kernel`，
  打轮时装入分发件。可读的全表见本书的[致谢](ACKNOWLEDGEMENTS.md)。

★`docs/benchmark/` 的**机器读的那一半**（`meta/` 下的 `domains.jsonld` ·
`requirements.jsonld` · `transcript.jsonld` · `index.jsonld` · `kernel.json`，外加 `records/` 与 `readings/`）不入 toc：
它们按路径被门禁、CI 与语料的 `account` 字段引用，要的是稳定路径而不是章节号。
散文那一半入册，就是上表的「校验册」。

★★**2026-09-16 校验册重起**（用户裁定）：上一本连同它的物理校验册与定序册移到
`docs/benchmark-legacy/`，**已移出版本控制**、不入 toc，磁盘留一份仅供查阅。
新册按**物理专题两级**组织——一级三组（平衡 · MHD 稳定性 · 输运），二级十六章，每章一页散文。

★★**需求号不是轴，是记录的属性**：上游两份 SRS 都标着 `distribution: internal`，本册的
读者打不开它们，于是「本条覆盖 `FR-EQ-016`」对他们只是一个不可解的记号。判据因此是
**抄录**进来的（`transcript.jsonld`，逐字抄自 SRS 的〈验证基准〉与〈验证矩阵〉，连带源的
版本与 sha256——源一变，闸子就红）。追溯没有丢：每条记录仍声明 `requirement[]`，
[覆盖表](benchmark/coverage.md)由此逐条反查，**没有记录覆盖的需求显示为空行**。

★另有一张[验证状态页](benchmark/status.md)答的是**另一个问题**：这些记录还作不作数。
每条记录记着它跑在哪个内核上，内核一换就整批转 `stale`，CI 据此重跑。
旧册的记录编号（`B-01`..`V-23`）与新册不通用。

## 文档编号与引用

本书四篇按**文件名**引用即可——**本书里没有按 `document_id` 指认的文档**：那些（`FYL-CONOPS-00`
· `FYL-SRS-01` · `FYL-SDD-01` · `FYL-DESIGN-NN` · `FYL-REPORT-NN`）都在 fylite_kernel，
路径经那边的 `docs/design/INDEX.md` 与 `docs/report/INDEX.md` 解析。要引它们就写仓限定的
行内代码，**不要在本仓硬编码跨仓路径，也不要写跨仓相对链接**。

## 构建

```bash
cd docs && myst build --html     # 全书
myst start                       # 本地预览
myst build --strict              # 把警告当错误
```

★**一本书，一个目录源**：`docs/myst.yml` 的 `toc` 是唯一的目录。若分成几本
各自带 `myst.yml` 的书挂成一个站点，站点根上就没有页面，本页无处可放。`guide/public.yml` 不是第二个目录——它点名的是「哪几篇随浏览器演示公开
发布」，另由 `tools/build-guide.sh` 读。
