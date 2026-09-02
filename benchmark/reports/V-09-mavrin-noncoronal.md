---
title: V-09 · Mavrin-2017 非日冕电荷态与冷却率，以及 L_INT 求积
---

# V-09 · Mavrin-2017 非日冕电荷态与冷却率，以及 L_INT 求积

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | TORAX（collisional_radiative_models + physics/radiation，非日冕档） · git:b4d40633（TORAX 1.4.3） · Apache-2.0 |
| **对象** | fylite: rust/fylite/src/edge.rs + edge_tables.rs + fylite.kernel.edge_* |
| **算例** | `scenario/mavrin-noncoronal-grid`（Mavrin-2017 非日冕拟合的自变量网格） |
| **数据** | 见 §5 表（3 项，纳入类别 private-artefact、public） |
| **门** | `$FYLITE_KERNEL/tests/test_edge_noncoronal.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——8 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 平均电荷态（8 核素 × 16 温度 × 7 个 n_e·τ） | relative | 1e-09 | machine_precision |  |
| 冷却率 L_z（同一网格） | relative | 1e-09 | machine_precision |  |
| L_INT（18 个区间，分辨率 100 随记录） | relative | 1e-09 | machine_precision |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/rust/fylite/src/edge.rs`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★这条**不是** `sources.rs::adas_cooling` 的第二种拼写：那是**日冕平衡**冷却率（只是 T_e 的函数，假定电荷态分布已经稳定），本条是**非日冕**（还取残留参数 n_e·τ）。在偏滤器里电荷态通常没稳定，两者在正好要问的条件下差若干数量级。两者并存、各自注明是哪一个。
- ★★移植时抓到并修掉一个缺陷：区间检索写成了「数**小于等于** T_e 的边界」，上游 `searchsorted` 数的是**严格小于**。两者只在温度**恰好落在边界上**时不同——记录里 896 点中 119 点，冷却率最劣 **4.8 倍**。★而 `L_INT` 在带着这个缺陷时仍然只差 1e-3，因为它的对数网格大多错过边界：积分看着没事，底下的速率却差五倍。所以速率是**逐点**把关，不只经它的积分。
- ★三处截断是**模型的一部分**而非它的护栏，都是上游的：T_e 截进每个核素自己的拟合区间（三阶多项式外插不是小误差）、n_e·τ 在日冕极限 1e19 处**饱和**而非外插、表里没有的核素辐射**零**（上游对边缘重杂质的建模陈述——钨在边缘对 Z_eff 与稀释的贡献远小于它在芯部的，那由另一个模型回答）。
- ★两张表**不共用温度单位**：电荷态表是 eV、冷却率表是 keV。同一篇论文、同一个模型里的两套单位，原样保留，单位写进常量名——静默归一会让某核素的区间边界挪一千倍而每个系数看着都对。
- ★氦的冷却率表比其余七个**少一个边界**，补齐用 `+inf`（检索永不选中）与 `NaN`（读错就毒化答案而不是悄悄换个数）。
- ★`L_INT` 的 `resolution` 是**答案的一部分**不是质量旋钮：对数网格上的梯形，上游调用方用 100 点；悄悄用更多点就不是在复现它声称复现的那个模型。
- ★这条只说「我们和它算得一样」，不说「该信它」：Mavrin 拟合本身没有在本条里对任何实验或第三方原子数据做确认。
- （场景）★没有装置、没有几何、没有输运：这是一族已发表的多项式，网格是它的自变量空间。用它做 validation 是范畴错误。
- （场景）★网格**刻意跨过退化的角**：n_e·τ = 1e19 恰好（Y=0，多项式里每个 Y 项消失）、1e20（上游**截断**而非外插）、以及每个核素拟合范围两端之外的温度（上游也逐核素截断）。
- （场景）★★还刻意压在**区间边界**上（10/20/50/100/200/500/1000 eV）——检索的 side 写错只在那里显形，网格避开它们就会漏掉一个 4.8 倍的缺陷。
- （场景）上游可重取（github.com/google-deepmind/torax，Apache-2.0），所以存的是数值 + 出处 + 复现配方，不 vendor 源码。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 平均电荷态，最劣相对 | 2.206e-14 |  | 成立 |  |
| 冷却率，最劣相对 | 6.556e-14 |  | 成立 |  |
| L_INT，最劣相对 | 6.742e-15 |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_edge_noncoronal.py | 8 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDATA_ORACLE/torax/mavrin_noncoronal.json | sha256:a0109ea8f28fe11d55e0759f3816f5b032de6b9cfbc1766dd63941c35a9a54ba | public | 85471 B |
| $FYDATA_ORACLE/torax/record_mavrin_noncoronal.py | sha256:eb62bcae601f671a491245ea017a31d129a5080b522c5a815f3f5a38a31941f1 | public | 7978 B |
| $FYLITE_KERNEL/rust/tools/gen_mavrin_tables.py | sha256:b404e1732b190cd66894ab23d3851757c59b291f53c412e289699bb029eaabb2 | private-artefact | 8496 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDATA_ORACLE` 是 fydata 仓的 `oracle/` 树，本仓与内核仓都以 `tests/data -> …/fydata/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydata/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_edge_noncoronal.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
