---
title: 算例报告（计划 + 记录 → MyST + SVG / 页面）
---

# 算例报告

`fylite cases --report <case id>` 把**一份 fyo 计划**（`cases/<id>.jsonld`，`fyo:ScenarioSpecification`）
经数据层的 JSON 门跑成**一份 spo 记录**（`spo:ComputationRecord`，产出数据集内联在端口上），再经一份
**呈现规格**（`spo:PresentationSpecification`）渲染为 MyST markdown 与 SVG 图；`--from <record.jsonld | 目录>`
渲染 `fylite case run` 已写下的记录。`app/pages/report.html` 读同样的文件，在浏览器里画同样的图。

## 产物

| 文件 | 内容 |
| :--- | :--- |
| `report.md` | 五节（摘要 · 方法 · 结果 · 验收 · 复现性），与 [运行报告模板](report-template.md) 同序；表题在上（`{table}`），图题在下（`{figure}`） |
| `figures/fig-NN.svg` | 折线图（量对自身坐标）与极向截面；手写 SVG，无 matplotlib |
| `presentation.jsonld` | 渲染所依据的呈现规格——外供时照画，未供时按规则推出并写在这里 |
| `record.jsonld` | 记录本身（正本；报告是它的投影，不内联任何数组） |

## 规则（FYL-REPORT-06 §13）

- **P1** 规格只绑量（`<数据集 id>#<fyo 路径>`），不抄数。
- **P2** 横轴是量自身的坐标：容器（或祖先）的 `grid/rho_tor_norm` → `grid/rho_tor` → `grid/psi`，同长的 `time`，
  平衡的 `profiles_1d/rho_tor`；单位取记录端口上的清单行；无坐标的量入表不作图；单样本数组是读数。
- **P3 / P4** 状态与附注照录；无比较记录时验收「未评估」，`verdict` 视图按名拒绝。
- **极向截面**（`fyo:PoloidalSectionView`，FYO-ADR-09）在平衡记录带 `time_slice/boundary/outline/r|z` 时画
  （磁轴、限制器、`profiles_2d/psi` 等值线随有随画），否则按名拒绝、其余照渲染。

## 用法

```bash
fylite cases --report evolve-default                  # records/<run id>/report.md
fylite cases --report evolve-default --out out/ --lang en
fylite cases --report --from records/<run id>         # an existing record directory
fylite cases --report evolve-default --presentation my-views.jsonld   # draw by a supplied spec
```

浏览器：打开 `app/pages/report.html`，选择 `record.jsonld`（可连同 `plan.jsonld`、`presentation.jsonld`
与数据集文件），或 `report.html?src=<url>`。两端对同一份记录推出同一份规格
（`app/tests/validate-report.mjs` 逐字段比对）。
