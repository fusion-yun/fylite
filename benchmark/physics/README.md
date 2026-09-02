# `benchmark/physics/` — 物理校验册

这里回答一个问题：**fylite 的产出，自洽吗。**

一次跑得又快又收敛的解可以是负温度的；一条与另一个码吻合到 1 % 的曲线可以违反
Grad–Shafranov（两处错互相抵消）。所以除了「对着外部答案量到多少」（公开 V&V
登记册 [`../`](../)）之外，还要有人问：这份产出**满不满足定律、满不满足文档自己
的定义、落不落在算例声明的窗口里**。这一册存的就是这个，一条一条。

The other register asks what fylite was *measured against*; this one asks whether
what it produced is *self-consistent* — positivity, finiteness, Grad–Shafranov,
the documents' own definitions (ψ endpoints, V′, the τ_E / β_N / Greenwald
formulae), and the operating window each case declares.

## 三类判据，读法不同

| 类 | 参考是什么 | 不满足意味着 |
| :--- | :--- | :--- |
| **定律** law | 物理定律本身（正性、有限性、Grad–Shafranov） | 产出不是一个物理态——这是缺陷 |
| **定义** definition | 文档自己的定义（ψ 端点、V′>0、β_N 与 Greenwald 的式子、τ_E 的定义式） | 文档内部不自洽，或口径与册子声明的不同 |
| **期望** expectation | **算例声明的**窗口（上下界、准稳态） | 这一炮没落在声明的窗口外——不一定是缺陷 |

★判决是**四态**（`pass` / `conditional` / `fail` / `unevaluated`），与
`fylite.engine.provenance` 的验收同一套，比公开登记册的三态多一个「有条件」
（量到的落在 1–3 倍容差之间）。**「未评估」单列，永远不并进「通过」**：一批
全未评估的结果，统计表必须一眼看得出来。

## 目录里有什么

| | 装什么 | 谁读 |
| :--- | :--- | :--- |
| [`suite.jsonld`](suite.jsonld) | **预设算例与它们的判据**（手写）：跑哪个算例、按哪些容差与上下界判 | 两者 |
| `<算例>.jsonld` | 一条算例的判决，一份 `fyo:ComparisonRecord`（生成件） | 程序 |
| `<算例>.md` | 同一条的散文报告：逐条量到什么、按什么判、假设了什么（生成件） | 人 |
| [`summary.jsonld`](summary.jsonld) · [`SUMMARY.md`](SUMMARY.md) | 一批的统计（生成件） | 程序 / 人 |
| 仓根 [`../../BENCHMARK.md`](../../BENCHMARK.md) | 同一份统计，加一段「这是什么」（生成件） | 人 |
| [`context.jsonld`](context.jsonld) | JSON-LD `@context`：承公开登记册那一份，只补本册子多出来的几个词 | 程序 |

★**生成件不手改**：判据册在 `python/fylite/scenario/physics.py`，取产出与落文档在
`python/fylite/scenario/suite.py`，写盘在 `tools/benchmark-run.py`。改结论要改判据或
改算例声明，再重跑。

## 怎么跑

```bash
python tools/benchmark-run.py                     # 跑一遍，统计表打到屏幕
python tools/benchmark-run.py --write             # 并写进本目录与仓根 BENCHMARK.md
python tools/benchmark-run.py --from records/     # 不跑，判已经跑出来的记录
fylite cases --physics                            # 列出预设算例与它们的判据
fylite cases --physics --check                    # 结构检查（与 pytest 闸子同一函数）
fylite cases --physics --run equilibrium-gfile    # 跑一条，打印报告
```

★★**产出从哪来，只有三条路，都不许猜**：算例声明的**产出文件**（`product`，
一份 g-file 就是一份平衡产出）、**已经跑出来的记录**（`--from`）、或经数据层的
JSON 门**现跑**（要 `libfylite_kernel.so`）。内核不在场时第三条路**按名拒绝**，
那些条目记成「未评估」并写明缺的是哪一件——不拿任何别的算法顶上。所以公开检出里
这一册大半是「未评估」，那是**检出的事实**，不是判据的沉默。

## 一条声明长什么样

```jsonc
{
  "id": "physics/zerod-iter-15ma",
  "title": {"zh": "…"},
  "scenario": "cases/zerod-iter-15ma",              // 跑哪个算例
  "concretized_as": [{"storage_uri": "cases/zerod-iter-15ma.jsonld", …}],
  "criteria": [                                     // 定律与定义一律跑，这里只声明多出来的
    {"quantity_label": "energy-balance",            // 判据册里的一条
     "tolerance": {"numeric_value": 0.02},          // 这个场景的带
     "tolerance_basis": "measured_band"},
    {"quantity_label": "declared-bounds",           // 这一炮该落在哪
     "bounds": [{"quantity": "SUMMARY/greenwald", "maximum": 1.2}],
     "tolerance_basis": "reference_stated"}
  ]
}
```

判据册里现有的检查、它们各读哪些量、各假设了什么，见
[`docs/reference/benchmark.md`](../../docs/reference/benchmark.md)（文档书里的一页），
或 `python -c "from fylite.scenario import physics; print(physics.CHECKS.keys())"`。
