---
title: B-01 · FUSE 的 ITER 算例，四层
---

# B-01 · FUSE 的 ITER 算例，四层

| | |
| :--- | :--- |
| **类** | **B 对拍** |
| **参考** | FUSE · 0.7.0 · Apache-2.0 |
| **对象** | fylite: 台基代理 / 0-D 聚变通道 / 算例文档 / TGLF deck 装配 |
| **算例** | `scenario/iter-15ma-flattop`（ITER 15 MA 感应燃烧，平顶段） |
| **数据** | 见 §5 表（3 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_fuse_benchmark.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——9 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 台基九档解 | relative | 1e-09 | machine_precision | 两边同一份 EPEDNN BSON 权重，所以这一层其实是 verification |
| 0-D 聚变功率 | relative | — | measured_band |  |
| 位形与 deck 装配 | relative | — | measured_band |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/fuse-cases.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★chi 仍是规定的：本仓 chi0 标定自 ASTRA，从没为 FUSE 的任何机器重标过——所以「本仓输运复现 FUSE 剖面」这一问没有问，第 2 层刻意只比通道
- FUSE 侧 lump_ions=true：DT+Ne+He 并成 NS=3、等效 Z=8.67，逐种通道不可比
- （判据）两边同一份 EPEDNN BSON 权重，所以这一层其实是 verification
- （场景）★这是一个准稳态窗口：参考自己的 T_e(0) 在 16 s 内只走 −5.2 %，「什么都不做」的全剖面 RMS 就是 4.07 %。任何模型跑完若不比这条线好，它什么也没说。
- （场景）参考侧只解电流与电子温度两条方程；T_i 与 n_e 是给定的（见各 record 的 prescribes）。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 台基（压强/宽度） | 4.4e-16 |  | 成立 |  |
| P_fus 与 P_alpha（本仓 Bosch-Hale 在 FUSE 自己的成分与体积上） | 1.0009 |  | 成立 |  |
| 算例文档 vs 实跑位形 | kappa +0.32 % / delta +3.7 % / Ip +1.5 % |  | 成立 | Ip 那 1.5 % 不是错：ini 请求 15 MA，平衡解出 14.78 MA |
| TGLF deck 装配（七面） | 几何 0.5 % / 密度梯度 0.4 % / 成分逐位 |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_fuse_benchmark.py | 9 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/fuse/iter_eped.json | sha256:8d5ac6223a78883d6b1a9aadadd047d1c426beb474b7c22e440806f16b2cd2d1 | public | 1491 B |
| $FYDOC_ORACLE/fuse/iter_init.json | sha256:a46587315b482362dfcdba0b8797e9bd56f2da0e8506a5358aacb2123ecf80bc | public | 25616 B |
| $FYDOC_ORACLE/fuse/iter_tglf_decks.json | sha256:6215b409ddeb9bb2d0c9c9acf2bd55992d9d2bb92954f1a4726f2c38d1ab7d66 | public | 55840 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_fuse_benchmark.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（B 对拍）的问题，不外推。
