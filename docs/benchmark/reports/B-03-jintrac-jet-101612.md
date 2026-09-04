---
title: B-03 · JINTRAC 作业 101612（JET #58894，JETTO+EIRENE）
---

# B-03 · JINTRAC 作业 101612（JET #58894，JETTO+EIRENE）

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | JINTRAC · 37.1.0-patched6 · EURATOM-ITER 34664 |
| **对象** | fylite: 1.5-D 输运算子（规定 chi 档）；TGLF 闭包 |
| **算例** | `scenario/jet-58894-lmode`（JET #58894，短窗口、芯边耦合） |
| **数据** | 见 §5 表（1 项，纳入类别 restricted） |
| **门** | `$FYLITE_KERNEL/tests/test_jintrac_case04_replay.py` |
| **登记册结论** | 部分（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——4 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| T_e 全剖面 | rms | 0.09 | measured_band |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/jintrac-case04-101612-reproduction.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★TGLF 那一臂的失败是模型面差异不是移植缺陷：参考用 Weiland(77 %)+Bohm(23 %)+EIRENE 中性，本仓三样都没有
- 声明的近似：算子无对流热项；chi(t) 只有 3 片线性内插；度规用 (SURF/DVEQ)^2 替 <|grad rho|^2>
- （场景）★这窗口是动的：0.2 s 内 T_e(0) +31 %、规定的 T_i(0) −20 %，零假设 41.5 %。在这里赢零假设是有意义的。
- （场景）参考侧带 EIRENE 中性粒子回路：电子能道的中性项只占 0.5 %，但离子道 CX 占 24 %、粒子道电离源超 NBI 35 倍——所以 T_e 可比，n_e / T_i 的预测离开中性模型免谈。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 零假设 | 0.415 | baseline | 未评估 |  |
| 记录 chi_e 回放（jsp XE） | 0.0667 |  | 成立 |  |
| 解释性 chi(t)（功率平衡含 dW/dt） | 0.0813 |  | 成立 |  |
| 常数 chi = 1.84 | 0.236 |  | 不成立 |  |
| 本仓 TGLF 自洽 | 0.345 | fail-model-face | 不成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_jintrac_case04_replay.py | 4 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-09-jintrac/runJINTRAC_101612/ | sha256-manifest:9f6aff9952c96cc31f4f35f747a2bb8f35eb72bc1268a3da135b18afc33f0f47 | restricted | 124 files, 26113662 B, 106 broken symlinks not hashed |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_jintrac_case04_replay.py
```

## 6. 结论

登记册：部分。复测 2026-09-02：成立。只回答本条自己那一类（B 对拍）的问题，不外推。
