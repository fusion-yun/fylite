---
title: C-04 · ICRH / ECCD，对 METIS 认证参考表
---

# C-04 · ICRH / ECCD，对 METIS 认证参考表

| | |
| :--- | :--- |
| **类** | **C 确认** |
| **参考** | METIS |
| **对象** | fylite: heating.rs |
| **算例** | —（无场景：局部或解析） |
| **数据** | 见 §5 表（1 项，纳入类别 public-derived） |
| **门** | `$FYLITE_KERNEL/rust/fylite/src/heating.rs` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——57 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 认证表逐例 | relative | — | reference_stated |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/icrh-ecrh-gap.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （无）

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 17 例 | 见 account |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/rust/fylite/src/heating.rs | 57 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/reference/metis_cert_hcd.csv | sha256:344a7584194c5541da74c7b5089b9ba9db8b17ca5d178f177c95a41c9a20690a | public-derived | 46105 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `oracle/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest 
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（C 确认）的问题，不外推。
