---
title: V-05 · 环向动量流的宇称对称性定理（Peeters 2011 §2）
---

# V-05 · 环向动量流的宇称对称性定理（Peeters 2011 §2）

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | gyrokinetic parity symmetry (Peeters et al., Nucl. Fusion 51, 094027 (2011) §2; Peeters, Angioni & Strintzi, PRL 98, 265003 (2007)) · analytic · published |
| **对象** | fylite: gyrofluid.rs 的环向应力准线性权重 |
| **算例** | `scenario/ga-standard-rotating`（GA 标准算例，Miller 几何，带平行速度剪切） |
| **数据** | 见 §5 表（1 项，纳入类别 public-derived） |
| **门** | `$FYLITE_KERNEL/tests/test_tglf_momentum.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——13 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 五个条件同时满足时的 \|stress_tor\|/Q_i（ρ* 最低阶、Ω=0、∇Ω=0、无 E×B 剪切、上下对称） | relative | 1e-08 | machine_precision |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/benchmark/reports/V-01-gacode-ports.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （场景）★没有装置、没有时间演化、没有平衡求解：局部几何与梯度是给定的，不是从剖面推出来的。用它做 validation 之外的推广是范畴错误。
- （场景）★★**饱和规则必须两边都写明，不能有一边靠缺省**。算例自己的设置是 SAT_RULE = 0，本仓这一支不带；记录在案的量是 SAT_RULE 1 与 2 下测的，UNITS 随预设（规则 2 → CGYRO）。算例自带的 SAT_RULE 0 答案存为**出处**而不是判据。这一条是写出来的教训：同一个陷阱在能量道与动量道各犯过一次，第二次花了三轮才归因。
- （场景）★V-05 用它时把驱动**全部关掉**并断言上下对称（ZMAJ_LOC/DZMAJDX_LOC/ZETA_LOC/S_ZETA_LOC 全零），因为宇称定理只在那个条件下成立——那是同一组几何参数的**另一个**用法，不是同一次运行。
- （场景）★剪切 1.0 比本仓 JINTRAC 各 deck 高一个量级，所以它探到的是动量道的量级而不是它的小扰动行为。
- （场景）上游可重取（GACODE `6357db306`，Apache-2.0），deck 存的是 `input.tglf.gen`——每个值都由上游自己解析定下，没有在这里猜任何缺省。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| GA 标准算例，全部驱动关闭，上下对称 | 2.7e-10 |  | 成立 | ★★本记录**不依赖任何参照代码**——它是模型自身的对称性，等离子体就是自己的参照。本通道其余每一条判据都要对着某个东西比，而那些比较里至少有一次比错了对象；★定理要求上下对称：门里先断言 ZMAJ_LOC/DZMAJDX_LOC/ZETA_LOC/S_ZETA_LOC 全为零，否则定理不适用、非零反而是对的 |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_tglf_momentum.py | 13 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/tglf/ga-standard-rotating.json | sha256:565c8d7395b18d028cb84632874ddbfdf6d971c9556c282c836b06d93d8f265b | public-derived | 4655 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_tglf_momentum.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
