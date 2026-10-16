# zerod-metis — 0D 全放电时序：fylite 与 METIS 实测对拍

〔海报挂点〕NFEC2026 海报（fydoc `FYD-PAPER-03`）图 5——**替换现用的手绘示意图
`fig4_zerod.png`（印刷前必须替换，示意曲线不得上墙）**。

## 目的

用 fylite 0D 线（`S.model.zerod`，FYL-DESIGN-05）跑一条全放电时序
（爬升—平顶—下降），与 METIS 参考在同一图上对拍 Ip / W_th / ⟨Te⟩ 三道时序。

## 参考数据

METIS 认证基线已在 fywork CASE-07 落盘：
`~/workspace/fywork/cases/CASE-07-zerod-fast-integrated-modeling/baselines/metis_cert_regression.json`
（t11/t12 认证臂产物，十三个 target 全绿）。第一步先做字段映射核对：
基线中的量名 / 归一 / 时间轴与 fylite `zerod` 输出逐项对上，对不上的量不画。

## 运行草案

```python
from fylite import scenario as S
r = S.model.zerod(ip_flattop=..., te_flattop=..., ...)  # 参数取自 METIS 基线同情景
# r["tier"] 必须记录在图注：prescribed 层的 Q 是用户输入的算术，不是预测
```

## 输出规格

- 三面板（Ip / W_th / ⟨Te⟩ vs t），fylite 实线、METIS 虚线，差异带或
  逐段偏差百分数标注；图幅 23.5 cm，字号等效 ≥14 pt。
- caption 必须含：METIS 版本 / 情景标识、fylite `tier`（prescribed 或 predicted）、
  平顶段一致性百分数。

## 诚实边界

- prescribed 层对拍验证的是**能量/粒子记账与时序装配**，不是输运预测能力——
  caption 不得写成"预测与 METIS 一致"；
- 若情景参数无法与 METIS 基线严格同源（同 Ip 波形、同加热波形），先对齐再画图，
  不做"形状相似"式对比。

## 数据

`case.fyo.jsonld` 为 fyo-typed 清单。`data/metis_cert_regression.fyo.jsonld` 为对标
基线（自 fywork CASE-07 `baselines/` 复制，sha256 记录在清单中**并由门禁核对**）。

★**五个算例里只有这一份数据留在 `examples/`**：它是建模算例（ITER / DIII-D-like
情景），不含装置几何、不含实验放电，所以可以随仓发布。其余算例的输入都是 EAST
的实测/重构数据，已移出 `examples/`（#137985 的交付件 2026-09-13 起在 `tests/data/FYDOC-CASE-22-east-137985-efit/`；同日随「彻底移除 est2」归档到 `archive/tests/data/FYDOC-CASE-22-east-137985-efit/`）。原文件是裸 JSON，现加了
`@context`/`@type`/溯源三段——载荷逐字未动。

fylite 侧运行产物（`zerod_run.json` 含 tier 标注）跑出后落盘于此。
