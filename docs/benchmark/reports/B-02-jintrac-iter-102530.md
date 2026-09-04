---
title: B-02 · JINTRAC 作业 102530（ITER 15 MA 平顶段）
---

# B-02 · JINTRAC 作业 102530（ITER 15 MA 平顶段）

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | JINTRAC · 37.1.0-patched6 · EURATOM-ITER 34664 |
| **对象** | fylite: 1.5-D 输运推进 + 电流道；TGLF 闭包 |
| **算例** | `scenario/iter-15ma-flattop`（ITER 15 MA 感应燃烧，平顶段） |
| **数据** | 见 §5 表（1 项，纳入类别 restricted） |
| **门** | `$FYLITE_KERNEL/tests/test_jintrac_flattop.py`；`$FYLITE_KERNEL/tests/test_tglf_fluxmatch.py`；`$FYLITE_KERNEL/tests/test_tglf_wrapper_convention.py`；`$FYLITE_KERNEL/tests/test_tglf_selfconsistent.py` |
| **登记册结论** | 部分（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——18 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| T_e 全剖面 | rms | — | measured_band |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/jintrac-flattop-reproduction.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★参考的 T_i / n_e 是喂进去的，本仓的是预测——两个数不是同一类东西，对照只剩 T_e 一道
- 预测行进与零假设统计打平（5.20 对 4.07）：准稳态窗口上这是该指标能到的地方，不藏
- （场景）★这是一个准稳态窗口：参考自己的 T_e(0) 在 16 s 内只走 −5.2 %，「什么都不做」的全剖面 RMS 就是 4.07 %。任何模型跑完若不比这条线好，它什么也没说。
- （场景）参考侧只解电流与电子温度两条方程；T_i 与 n_e 是给定的（见各 record 的 prescribes）。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 零假设（T_e 冻在 t0） | 0.0407 | baseline | 未评估 |  |
| 常数 chi（读参考体平均） | 0.068 | worse-than-null | 不成立 |  |
| 冻结 TGLF 匹配剖面 | 0.0542 | worse-than-null | 不成立 |  |
| 自洽 TGLF 重估 | 0.052 | ties-null | 部分 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_jintrac_flattop.py | 14 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_tglf_fluxmatch.py | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_tglf_wrapper_convention.py | 2 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_tglf_selfconsistent.py | 1 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-09-jintrac/corpus/run15MA_TBM_13_imas2_0821_repeat_102530/imasdb/ | sha256-manifest:93f6c05131f554dae4165bb6e106882bf38976fd08f0b354dd65ad404564e220 | restricted | 7 files, 10531309 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_jintrac_flattop.py tests/test_tglf_fluxmatch.py tests/test_tglf_wrapper_convention.py tests/test_tglf_selfconsistent.py
```

## 6. 结论

登记册：部分。复测 2026-09-02：成立。只回答本条自己那一类（B 对拍）的问题，不外推。
