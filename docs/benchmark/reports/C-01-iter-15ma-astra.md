---
title: C-01 · ITER 15 MA 感应燃烧，对 ITER Organization 的参考算例
---

# C-01 · ITER 15 MA 感应燃烧，对 ITER Organization 的参考算例

| | |
| :--- | :--- |
| **类** | **C 确认** |
| **参考** | CORSICA / ASTRA · ITER 参考算例 2010-04-07 批次 |
| **对象** | fylite: 含时演化栏（浏览器侧） |
| **算例** | `scenario/iter-15ma-flattop`（ITER 15 MA 感应燃烧，平顶段） |
| **数据** | 见 §5 表（1 项，纳入类别 restricted） |
| **门** | `app/tests/validate-iter-benchmark.mjs` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：未评估——0 passed, 0 failed, 0 error, 0 skipped, 1 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 剖面与全局量 | relative | — | reference_stated |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/iter-15ma-benchmark.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （场景）★这是一个准稳态窗口：参考自己的 T_e(0) 在 16 s 内只走 −5.2 %，「什么都不做」的全剖面 RMS 就是 4.07 %。任何模型跑完若不比这条线好，它什么也没说。
- （场景）参考侧只解电流与电子温度两条方程；T_i 与 n_e 是给定的（见各 record 的 prescribes）。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 闸子 28 项 | 全绿 |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| app/tests/validate-iter-benchmark.mjs | 0 过 / 0 败 / 0 错 / 0 跳 / 1 陈旧 | page.evaluate: TypeError: Cannot set properties of null (setting 'value') |

结论：**未评估**（`re-run: gate stale (names an entry the assembly layer no longer has)`）。

- $FYLITE_PUBLIC/app/tests/validate-iter-benchmark.mjs: page.evaluate: TypeError: Cannot set properties of null (setting 'value')

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/astra/iter15ma_astra_burn.csv | sha256:6dc1c70b94ef31c8ae8513522e847fdba47495ed64425a44306bd43adb5f326e | restricted | 20703 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest app/tests/validate-iter-benchmark.mjs
```

## 6. 结论

登记册：成立。复测 2026-09-02：未评估。只回答本条自己那一类（C 确认）的问题，不外推。
