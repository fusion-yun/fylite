# port-parity — 移植保真：NEO / TGLF 对参考实现的 parity 图

〔海报挂点〕NFEC2026 海报（fydoc `FYD-PAPER-03`）**新增小图**，支撑创新点栏
"物理模块依据公开文献与开源代码、以 AI 辅助方式构建"的可信度——主张移植保真
就必须给 parity 证据，这是评审指出的主张-证据缺口。

## 目的

把仓内已有的金标校验数据画成一幅 parity 散点图（x = 参考实现，y = fylite 移植，
对角线 ±容差带）：

- **NEO**：漂移动理学求解对 GACODE NEO 参考的端到端一致性（既有测试记录
  1e-14…3e-10 量级）；数据源 = `tests/oracles/` 夹具 + 对应测试的实测偏差。
- **TGLF**：Rust 移植对 GACODE TGLF 参考夹具的逐字段/逐通量校验；
  数据源 = oracle 夹具（623 个）中 TGLF 族。

## 运行草案

```bash
# 全离线。脚本遍历 oracle 夹具，重算 fylite 侧，收集 (ref, ours) 对：
PYTHONPATH=python python demo/port-parity/collect_parity.py \
    --families neo,tglf --out parity.json
python demo/port-parity/plot_parity.py parity.json parity.png
```

（两个脚本待写；核心即测试套件已跑通的比较，抽出数据而非断言。）

## 输出规格

- 单面板 log-log parity 散点，NEO / TGLF 两色，对角线 + 相对偏差直方图内嵌；
  图幅可半宽（11.5 cm），字号等效 ≥14 pt。
- 图内标注每族的点数与最大相对偏差。

## 诚实边界

- parity 对象是**参考实现**（GACODE），不是实验——这属 verification，不是 validation；
- TGLF 若存在已知偏差项（NOTICE / 遗留项清单载明），在图注列出而不是从散点里剔除；
- 白盒移植的来源与许可（Apache-2.0，NOTICE）在海报方法栏交代。

## 数据

`case.fyo.jsonld` 为 fyo-typed 清单。

★**输入口原先指错了地方。** `tests/oracles/` 放的是参考**实现**（6 个模块）；
冻结的参考**答案**在 `tests/data/oracle/`（14 个条目 328 条记录），由 `fylite._oracle`
经 `$FY_ORACLE_STORE` 解析。清单已改指后者。

产物 `parity.json` / `parity.png` 跑出后落盘于此。
