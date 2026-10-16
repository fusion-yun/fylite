# vv-gold-numbers — V&V 金标数字表（海报"验证与确认"栏的数据源）

〔海报挂点〕NFEC2026 海报（fydoc `FYD-PAPER-03`）"验证与确认（V&V）"栏——
把散文式"10⁻⁵～10⁻¹⁰ 量级"替换为**可追溯的逐模块数字**。评审裁定：不写清
"什么量、什么范数、对什么参考、在哪个算例"，量级声明等于没说。

## 目的

写一个离线汇总脚本，从既有测试/夹具/交付产物中**收集（不重新宣称）**各模块
的实测偏差，产出一张 markdown 表：

| 模块 | 量 | 参考 | 范数/口径 | 算例 | 偏差 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| NEO DKE | 新经典通量/自举流 | GACODE NEO | 逐字段相对偏差 | oracle 夹具 | （实测填入） |
| TGLF | 线性谱/QL 通量 | GACODE TGLF | 逐字段相对偏差 | oracle 夹具 | （实测填入） |
| 自举流交叉核验 | jpar_dke vs Redl-2021 | NEO 自评系数 | 峰值相对差 | #137985 loop | ≈数 %（Sauter-1999 高 ≈30%，见 demo/README） |
| GS 求解 | 全局量 q0/q95/li/βp | 解析平衡 / 参考 g-file | 相对偏差 | synthetic + #137985 | （实测填入） |
| g-file 读写 | a-file 标量 | 字节级锚点 | 逐位 | a137985.04000 | 0（tsaisq 2.90 锚） |
| 0D | 能量记账 | METIS 认证基线 | 平顶段相对差 | fywork CASE-07 | （c3 跑出后填入） |

## 运行草案

```bash
PYTHONPATH=python python demo/vv-gold-numbers/harvest.py --out vv_table.md
# 数据源：tests/oracles/ 夹具、examples/scripts/summary_137985_loop.json、
# c3/c4 的产物。脚本只读不跑重物理；缺的格子留空并注明出处待补，禁止填估计值。
```

## 海报用法

表格不直接整表上墙（版面有限），V&V 栏每行一个模块引用表中数字；
本表全文放入 fydoc 条目目录作为溯源附件。

## 诚实边界

- 每个数字必须能指回一次真实运行（测试日志/产物文件），脚本输出带来源列；
- verification（对参考实现）与 validation（对实验）分列，不混写。

## 数据（已收录）

`case.fyo.jsonld` 为 fyo-typed 清单。数据源为仓内夹具与兄弟算例产物（清单列明）；
产物 `vv_table.md` 每个数字带来源列。
