---
title: 算例语料 (The Case Corpus)
---

# 算例语料：一份计划、一次运行、一份报告

本书后面五章各讲一族**典型算例**。它们不是为文档现编的片段——每一条都在仓里
`cases/` 下有一份**计划文档**，可以原样跑、原样改、原样发给别人。这一章讲那条链子
本身：计划长什么样、怎么跑、结果落在哪、怎么变成一份可读的报告。

## 三份文档，三件事

| 文档 | 是什么 | 谁写 |
| :--- | :--- | :--- |
| **计划** `cases/<id>.jsonld` | `fyo:ScenarioSpecification`（上游 `spo:ComputationPlan`）：要跑哪个代码、参数取什么值、输入从哪来、产出往哪去 | 人（或页面导出） |
| **记录** `record.jsonld` | `spo:ComputationRecord`：跑完之后的事实——状态、用时、内核哈希、每个产出端口上的数据集 | 内核与数据层 |
| **呈现规格** `presentation.jsonld` | `spo:PresentationSpecification`：这份记录**怎么画**——哪些面板、哪些视图、每条序列绑记录里的哪个量 | 渲染器（或人，见[算例报告](../reference/case-report.md)） |

★**三者分开不是分层癖好。** 计划里没有答案，记录里没有主张，规格里没有数字。所以
换一份规格不会改变结论，重跑一次不会改写计划，而报告永远是记录的**投影**——它不能
比记录多说一个字。

## 四个动词

```bash
fylite cases                      # 列出语料：25 条，各自的能力栏、装置、名字
fylite cases zerod-iter-15ma      # 打印那份计划（JSON-LD 原文）
fylite cases --check              # 结构检查：每条目录项都在盘上、无孤儿文件、词汇只有 fyo / spo
fylite cases --plan  <id>         # 只映射不跑：计划的每个控件落到 Python 入口的哪个字段
fylite cases --run   <id>         # 跑，并留下清单 / 验收 / 账本
fylite cases --report <id>        # 跑，并渲染成 MyST + SVG 报告
```

`--plan` 是读者最该先按的那个键。它把**语料的控件词表**逐条分类，一个都不许漏：

```text
$ fylite cases --plan zerod-iter-15ma
{ "case_id": "zerod-iter-15ma", "bar": "zerod", "tool": "zerod", "device": "iter",
  "accounting": { "mapped": {...21 项...}, "sub": {...11 项...}, "ui": {"slice": ...} } }
```

四类去处，**没有第五类**：

- `mapped`——喂给 Python 入口的字段（连同单位换算）；
- `sub`——只有某个**具名的子能力**才会读它（蒙特卡洛 UQ、通量账本、湍流外环…），
  不跑那个子能力时基准运行**不读它**，所以照跑不算失真；
- `shared`——设计页上几条栏共用的等离子体标量，本栏不消费；
- `ui`——显示状态（滑块位置、折叠）。

★**一个没被分类的键会让 `--run` 报错**（`python/tests/test_case_runs.py` 把这条钉死）。
静默丢弃一个控件，是这一层最该防的失败方式：跑出来的数看着像那个算例，其实不是。

## 跑一次留下什么

```text
$ fylite cases --run transport-iter-15ma
transport-iter-15ma  bar=transport -> fylite_transport
  run r-20260902-190432  (/root/.cache/fylite/runs/s-…/r-20260902-190432)
  fields: 13 mapped, 6 sub-capability, 0 shared, 0 ui
  acceptance: pass  converged=pass, settled=pass
  report: fylite report r-20260902-190432
```

运行目录里是清单（`manifest.json`）、结果（`result.json`，数组只存**摘要**：形状 /
dtype / min / max / mean / sha256，正本在 `arrays.npz`）、验收（`acceptance.json`）与
账本。`$FYLITE_RUN_DIR` 决定它落在哪，缺省是 `~/.cache/fylite/runs/`。

★**验收是运行自己报的，不是报告重判的。** 四态 `pass / conditional / fail /
unevaluated`——上面那条 `settled=pass` 是判据说话，而 0-D 那条 `converged=unevaluated`
是它**没有**这条判据可评，不是它不合格。

## 变成一份报告

```bash
fylite cases --report evolve-iter-15ma --out out/
```

出来的是一整个目录：`report.md`（MyST，五节：摘要 · 方法 · 结果 · 验收 · 复现性）、
`figures/fig-NN.svg`（折线图与极向截面，**不需要 matplotlib**）、`presentation.jsonld`
（画它所依据的规格）、`record.jsonld` 与 `plan.jsonld`。同一份记录也能在浏览器里画：
打开 `app/pages/report.html` 选中这几个文件，或 `report.html?src=<地址>`——两端**同一条
规则**推出同一份规格，由 `app/tests/validate-report.mjs` 逐字段盯着。

体例与规则见参考书的[算例报告](../reference/case-report.md)。

## 不经 Python 的那条路

计划文档也能直接交给数据层的可执行件，走内核的单入口 `fylite_rs_fyo`：

```bash
fylite-case plan cases/evolve-iter-15ma.jsonld          # 只解析与合成，不跑
fylite-case run  cases/evolve-iter-15ma.jsonld --record out/
fylite-case run  cases/evolve-iter-15ma.jsonld --record out/ --format imas-hdf5
fylite-case json cases/evolve-default.jsonld            # 一份计划进，一份记录出（stdout）
```

多份计划按序合成（后者覆盖前者），再叠 `--set k=v` / `--bind 端口=路径`。★
`--format imas-hdf5`（或计划自己在输出端口上要 `fyo:ImasHdf5Format`）写出的是**一个
IMAS 数据入口**：`imas/master.h5` 加逐 IDS 的 `<ids>.h5`，imas-core 的 HDF5 后端布局。

Python 侧同一道门：

```python
from fylite.io import fydoc
record = fydoc.case_json(json.load(open("cases/evolve-default.jsonld")), base="cases")
record["run_state"]        # 'succeeded'
```

## 被拒绝的算例，与拒绝的理由

语料里有几条**跑不了**，`--run` 会**点名拒绝**而不是给一个近似答案：

| 算例 | 为什么 |
| :--- | :--- |
| `pulse-iter` · `profile-default` · `series-default` | 浏览器专属的功能栏（`pfwave` / `profile` / `series`）：它们是别的栏的**组合或队列**，Python 侧没有独立入口 |
| `reconstruction-default` | `analysis.reconstruction` 在，但这条算例冻的是**合成孪生生成器**的旋钮，而那个生成器只在 `worker.js` 里 |
| `evolve-jintrac-*` | 参考运行是第三方产物（受限），本仓跑不动；它们是**对拍记录的输入侧说明**，不是可执行算例 |

★**宁可拒绝，不给假数**（拒绝逐条带理由，见 `fylite.scenario.cases.REFUSALS`）。想跑
反演，走[诊断分析：平衡反演](example-reconstruction.md)那一章的 Python 入口。

## 五族典型算例

| 章 | 算例 | 问的是 |
| :--- | :--- | :--- |
| [0-D 放电](example-zerod.md) | `zerod-iter-15ma` | 一发放电的功率平衡与时间轨迹 |
| [1.5-D 芯部输运](example-transport.md) | `transport-iter-15ma` | 给定度规与 χ，剖面长什么样 |
| [含时演化](example-evolve.md) | `evolve-iter-15ma` | 剖面随时间怎么走，能不能点燃 |
| [放电设计](example-design.md) | `breakdown-iter` · `discharge-iter` | 线圈电流该给多少，才有这个位形 |
| [诊断分析：平衡反演](example-reconstruction.md) | EAST #137985 @ 4 s | 给定测量，位形是什么 |
