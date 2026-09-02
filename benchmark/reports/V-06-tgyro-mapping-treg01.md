---
title: V-06 · TGYRO 映射层：整份 out.tglf.localdump 全键对照（treg01 四半径）
---

# V-06 · TGYRO 映射层：整份 out.tglf.localdump 全键对照（treg01 四半径）

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | GACODE / TGYRO · rev 6357db306 · Apache-2.0 |
| **对象** | fylite: scenario.model.mapping.tglf_inputs（tgyro_tglf_map.f90 的移植） |
| **算例** | `scenario/gacode-regression`（GACODE 自带回归算例（局部通量面）） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_mapping.py`；`$FYLITE_KERNEL/tests/test_flux_chain.py` |
| **登记册结论** | 部分（`assertion_state: accepted`） |
| **复测** | 2026-09-02：未评估——0 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 两侧都有的每一个 deck 键（不是手挑表），revision=3 + mxh=False | relative | 2e-05 | reference_stated | out.tglf.localdump 打六位有效数字，这就是容差的来源 |
| 映射未发出的每一个开关：本仓缺省必须等于 TGYRO 的取值 | absolute | 0.0 | machine_precision | ★一个不发出的键不是中立的，它是一句「缺省相同」的无声断言 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYDATA_ORACLE/tgyro_treg01/README.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （判据）out.tglf.localdump 打六位有效数字，这就是容差的来源
- （判据）★一个不发出的键不是中立的，它是一句「缺省相同」的无声断言
- （场景）★局部算例没有装置、没有时间演化：它固定一个面的状态，问湍流/新经典/几何的答案。用它做 validation 是范畴错误。
- （场景）上游可重取（gafusion/gacode，Apache-2.0），所以这一档的参考数据存的是指针与版本，不是本体。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| treg01 四个半径，全键对照 | 78 个共享键，0 分歧 |  | 成立 | ★需要 revision=3（treg01 的 TGYRO_TGLF_REVISION）与 mxh=False（其 input.tgyro.gen 写着 0 TGYRO_TGLF_MXH_FLAG） |
| 此前只被手挑表覆盖时漏掉的开关 | 3 个 |  | 不成立 | ★★USE_BPER（TGYRO T / 本仓缺省 F，生产路径跑静电）、USE_MHD_RULE（TGYRO F / 本仓 T，把漂移里的压强项清零）、USE_AVE_ION_GRID（TGYRO T / 本仓 F）；★根因不是漏三个键，是整张 TGYRO_TGLF_REVISION 预设表没移植——它被手写在 test_flux_chain.py 的 SAT2 字典里，**测试知道答案而生产不知道**。现已按 tgyro_tglf_map.f90 的 select case 原样落成 mapping.TGYRO_TGLF_REVISION |
| revision 3 预设对通量的代价（treg01 四半径，电子道） | r/a=0.20 粒子 5.45× / 能流 3.92×；0.35 2.37× / 0.64×；0.50 1.06× / 0.88×；0.65 1.19× / 1.03× |  | 部分 | ★核心处四五倍且修正在半径间变号——不是数值旋钮；★生产是否采用留 T-C34 裁定：打开会移动本仓每一个已录输运答案，参照要重测。闸子钉的是量级，好让决定在看得见数字时做 |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_mapping.py | 未执行 |  |
| $FYLITE_KERNEL/tests/test_flux_chain.py | 未执行 |  |

结论：**未评估**（`re-run: gate not executed`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDATA_ORACLE/tgyro_treg01/ | sha256-manifest:17375200f98368c7c3197b53bc4ace7f5db6f94df23eaad670366281d84ddbe6 | public | 24 files, 81461 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDATA_ORACLE` 是 fydata 仓的 `oracle/` 树，本仓与内核仓都以 `tests/data -> …/fydata/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydata/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_mapping.py tests/test_flux_chain.py
```

## 6. 结论

登记册：部分。复测 2026-09-02：未评估。只回答本条自己那一类（V 验证）的问题，不外推。
