---
title: V-23 · ITER 被动导体回路：真空室环向电阻对文献；无等离子体时间常数补上超导回路屏蔽后对 CREATE 一致
---

# V-23 · ITER 被动导体回路：真空室环向电阻对文献；无等离子体时间常数补上超导回路屏蔽后对 CREATE 一致

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | ITER_D_22L4FE v1.0（CREATE）与 ITER_D_22FPWQ v4.0（真空室 DDD） · 22L4FE 表 4.1.a 与 §2.1 / 表 2.1.a–f（EFDA/03-1108 D2，2004-03-03）；22FPWQ 表 2.1-1 的环向 / 极向电阻 · ITER IDM Internal Use（只引数值，件不再分发） |
| **对象** | fylite: code/wall 经树门（ITER 卡片的 pf_passive，324 个 loop 自 fydoc 由 CC BY 原件离散；元件互感 · 电阻 · M dI/dt + R I = 0 的 L/R 本征模，每组另单解；每元 8×8 细丝）＋门自己的 `screen_coils`：把普通 pf_active 线圈作为零电阻回路消去（Schur 补），与裸谱并列给出 `tau_*_screened`） |
| **数据** | 见 §5 表（3 项） |
| **门** | `python/tests/test_benchmark_wall_iter.py::test_v23_the_vessel_toroidal_resistance_agrees_with_the_literature`；`python/tests/test_benchmark_wall_iter.py::test_v23_the_bare_time_constants_reproduce`；`python/tests/test_benchmark_wall_iter.py::test_v23_the_modes_are_the_ones_create_names`；`python/tests/test_benchmark_wall_iter.py::test_v23_screening_by_the_superconducting_circuits_closes_the_gap`；`python/tests/test_benchmark_wall_iter.py::test_v23_the_door_itself_now_yields_the_screened_spectrum`；`python/tests/test_benchmark_wall_iter.py::test_v23_the_doors_screened_tau_stays_in_the_band_against_create`；`python/tests/test_benchmark_wall_iter.py::test_v23_our_own_uncertainty_band_contains_creates_value`；`python/tests/test_benchmark_wall_iter.py::test_v23_neither_circuit_topology_nor_coil_geometry_changes_the_answer`；`python/tests/test_benchmark_wall_iter.py::test_v23_the_port_sets_are_recorded_but_flagged_as_over_modelled` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 复测 2026-09-16（本条写入时把门跑一遍）：成立——9 passed, 0 failed, 0 error, 0 skipped（python/tests/test_benchmark_wall_iter.py，2026-09-16 本机实测；门由 7 条扩到 9 条，新增两条守住内核 `screen_coils` 的读数） |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

**适用域**：ITER 卡片的被动集（自 CC BY 原件离散的 324 元，8×8 细丝）；无等离子体、纯 L/R 电路；屏蔽由门的 `screen_coils` 做（零电阻回路的 Schur 补，线圈自感取 8×8 细丝），记录侧另以解析圆环单丝独立自算一遍作交叉核对；端口按连续环建模（已知过度）；不含 3-D 端口结构、不含等离子体响应

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 真空室双壳并联的环向电阻对 ITER_D_22FPWQ 自报值（7.9 µΩ） | relative | 0.035 | measured_band | 两条独立算法：内核的逐元电阻，与直接自原件按极向条带并联的解析和——两者逐位相同 |
| 补上超导回路屏蔽后的 τ₁（VV + OTS）对 CREATE-NL 的 0.3623 s | relative | 0.08 | measured_band | ★这是一致性判据，但容差宽达 8 %：本仓自身因线圈自感取法的散布就有 ±7 %（见判据 3） |
| 本仓不确定度区间须**包含** CREATE 的 τ₁（0.3623 与 0.3705 s） |  | — | measured_band | 区间由线圈自感的三种取法给出：a = 0.25 m / a 自矩形单丝 / a 自矩形 3×3；★「一致」的诚实形式是「残差小于我方自身的不确定度」，不是「对上了」 |
| 屏蔽使均匀模电感下降的幅度（须 < 0.65 倍，即降幅 > 35 %） | absolute | 2.9152 uH | measured_band | 这一项才是解释本身：零电阻回路保磁通，压低真空室模的有效电感 |

## 2. 口径与说明

- ★★2026-09-16 /goal「… 导体壁等被动导体耦合」的 ITER 侧：此前 ITER 卡片的 `pf_passive` 为 None、十四个 vessel 单元无一带 `element`，`code/wall` 与 `code/vstab` 在这台机器上**看不到任何被动导体**
- ★V 类：参考侧是文献数值（两份 Internal Use 件），不是可回放的运行件
- ★★★**本条首录时判「不可比」，同日据实测改判「补上屏蔽后一致」**。首录把差因归给「CREATE 侧有传导连接」，那是推测且已自证为错（n = 0 下径向连接不改变环向回路拓扑）；真因在同一份件的前一页——plasmaless 系统含零电阻超导回路，保磁通、屏蔽真空室模。两版都留在册里，因为错的那版曾被写出去过
- ★不去凑 τ：把 η 或几何调到对上 0.3623 s 会毁掉已经成立的电阻一致性；主报值也不取对得最准的那一档（a = 0.25 m，−0.44 %），而取取法最自然的一档（−5.66 %）
- 纳入类别（参考数据）：public

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| 真空室环向电阻对文献 | 双壳并联 7.6272 µΩ 对 ITER_D_22FPWQ 的 7.9 µΩ（-3.45 %）；内壳 16.3459 · 外壳 14.2996 µΩ。★比书页原有的 8.98 µΩ 粗估更接近真值 | 成立 |  |
| 裸回路的时间常数（读数：高 57 %，保留在册） | 不含线圈时 VV 双壳 τ₁ 0.5689 s、加 OTS 0.5834 / 0.3049 s，对 CREATE 的 0.3623 / 0.2385 s（NL）高约 57 %。这个数**不删**：它是「不含超导回路」这一口径下的正确答案，也是下面那条解释的出发点 | 未判（读数） | 口径是对得上的：CREATE 按模式形状点名两个常数，本条实测 k=0 均匀度 1.0000、k=1 上下反对称度 −0.9045，且恰为最慢的两个本征模 |
| 五条候选解释逐一证伪（含本会话自己先提错的那一条） | ①离散粒度：135+151 → 57+50（CREATE 自己的元数）→ 28+25，τ₁ 只动 < 0.5 %（0.568922 → 0.569345 → 0.571403）；②增厚壳：照 CREATE 的 60 → 150 mm 配 η_eq 1.90 µΩ·m 重算，τ₁ **升** 5 %（0.5689 → 0.5977），方向相反；③电阻率：ρ/t 为 12.67（CREATE）对 13.33（本仓），差 5 % 且方向相反；④模式定义：见上条，是同一对模式；★⑤**传导连接——这是本会话先提出、随即自证为错的一条**：对 n = 0 环向涡流，各环本就只有互感耦合，内外壳之间的径向连接只让电流在两壳间重分配，而那已被并联电阻算进；把两壳强制短接得到的正是已在求解的均匀模。该说法一度写进本登记册、plan 与内核笔记，此次一并订正 | 成立 | 记下它，是因为它曾被当作结论写出去过；错的不是方向感，是没有先问「n=0 下传导连接改变什么」 |
| ★真因：CREATE 的 plasmaless 系统含零电阻超导回路，屏蔽了真空室模 | 22L4FE 第 2 页明写「All resistances (in SC coils, voltage amplifiers, connections) are **neglected**」，而其 L₀ / R₀ 装着十一条 PF/CS 回路。零电阻回路保磁通，故以 Schur 补消去线圈：L_eff = M_vv − M_vc M_cc⁻¹ M_cv。均匀模电感 5.0657 → 2.9152 µH（−42 %），τ₁ 0.5834 → 0.3418 s，对 CREATE-NL 的 0.3623 s 差 -5.66 % | 成立 | 互感用 Maxwell 共轴圆环公式自算，先对内核的 M 验过：非对角相对差中位 −0.0094 %、p95 0.168 %，L_uniform 5.0632 对 5.0657 µH——不是靠公式凑出来的 |
| ★屏蔽已进内核：门直接给出 `tau_*_screened`（2026-09-16） | `code/wall` 加设定 `screen_coils`（默认关闭），由内核做同一步 Schur 消去。VV + OTS 上门给 0.342187 s、VV 双壳 0.331931 s，消去 12 个线圈元；与本记录侧独立自算的 0.341790 s 差 +0.116 %。对 CREATE-NL 的 0.3623 s 差 -5.55 % | 成立 | ★这一条是本记录成立的前提之一：屏蔽此前只在记录侧算，内核漂了不会有任何东西红；现在门的值才是读数，记录侧自算降为独立交叉核对，两者由门 `test_v23_the_door_itself_now_yields_the_screened_spectrum` 守住（容差 0.5 %）；两侧的线圈自感取法不同（内核 8×8 细丝 / 记录侧解析圆环单丝），故这是**吻合**、不是同一次计算；默认关闭：B-17 · B-19 · B-20 是立在裸回路上的带，默认屏蔽会挪走已入册的答案 |
| 残差小于本仓自身的不确定度（这才是「一致」的诚实形式） | 线圈自感的三种取法给出 τ₁ 区间 [0.3257, 0.3717] s（a = 0.25 m / a 自矩形单丝 / a 自矩形 3×3），跨度约 14 %；CREATE 的 0.3623 与 0.3705 s **都落在区间内**。主报值取 a 自矩形单丝（与内核 rect_of 的 a_eq 约定一致）= 0.3418 s | 成立 | ★不报 a = 0.25 m 那一档的 −0.44 %：它对得最准，但取法最随意，拿它当主结论是挑数 |
| 回路拓扑与线圈几何都不影响结论（两条候选一并排除） | 十二条独立线圈与表 2.1.b–f 的十一条真实回路给出**逐位相同**的 L_uniform 2.9226 µH、τ₁ 0.3418 s（τ₂ 仅第四位差）——屏蔽由 M_vc M_cc⁻¹ M_cv 决定，回路只是基变换；线圈几何用卡片的 2ACJT3 v3.1 给 0.3418 s、用 22L4FE 自己的表 2.1.a 给 0.3395 s，差 0.7 % | 成立 |  |
| 端口组是本仓的建模过度（读数，且不供对比用） | 三组端口内壳按**连续环**建模，而实物是 18 个约 5° 宽（环向占空比约 25 %）。加入后 R_parallel 由 7.5376 降到 6.1033 µΩ，裸 τ₁ 冲到 0.8840 s。本条如实记录该组读数，但任何对比都不应当用它 | 未判（读数） | 改正方向：按占空比折算等效环向电阻，或把端口建成不闭合段——两者都需要 33NHXN / 22L4FE 未给的环向信息 |
| 复测 2026-09-16（本条写入时把门跑一遍） | 9 passed, 0 failed, 0 error, 0 skipped（python/tests/test_benchmark_wall_iter.py，2026-09-16 本机实测；门由 7 条扩到 9 条，新增两条守住内核 `screen_coils` 的读数） | 成立 | 本条是新立记录，registry 里此前没有可沿用的复测条，故由 `--reruns` 给出本次实测。；同批另跑：EAST 卡片 28 passed / 195 s，ITER 卡片 11 passed / 40 s，合计 39 门全过、零 skip。；内核侧同批：`cargo test wall_tests` 7 passed（含屏蔽的闭式验证与「默认关闭逐位不变」两条回归）。 |

## 4. 不可比的部分

- 参考侧是两份 ITER IDM Internal Use 件里的**数值**，不是可回放的运行件；公开读者无法复算参考侧。
- 端口组按**连续环**建模，实物是 18 个约 5° 宽（环向占空比约 25 %）：该组读数已记，但不供任何对比使用。
- 被动集本身来自 CC BY 原件的**离散**：段数即原件点数（不细分），元的角度按内核 efund 两分支约定写。
- 屏蔽由门的 `screen_coils` 做（零电阻回路的 Schur 补，线圈自感取 8×8 细丝）；记录侧另用 Maxwell 共轴圆环互感 + 解析圆环自感独立自算一遍作交叉核对，两者差 +0.12 %。CREATE 用的是有限元。本仓因线圈自感取法的散布达 ±7 %，**大于**与 CREATE 的残差——所以判词是「在本仓不确定度内一致」，不是「吻合」。
- 等离子体响应完全不在本条内：CREATE 表 4.1.a 的 γ 与稳定裕度是可变形线性化响应，本条只取它那两列无等离子体时间常数。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |
| docs/benchmark/readings/wall_iter.json | — | public |
| fydoc facts/device/iter/abox/static/now/pf_passive.jsonld | — | public |
| dist/facts/device/iter.jsonld | — | public |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_PUBLIC
FYLITE_DEVICE_DIR=dist/facts/device/iter FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \
  uv run --no-project --with numpy --with scipy --with pytest \
  python -m pytest python/tests/test_benchmark_wall_iter.py
# 读数重写：见该门抬头（code/wall 逐组跑，屏蔽用 screen_coils=1；落 docs/benchmark/readings/wall_iter.json）
```

## 6. 结论

两项都成立，但第二项走过一次弯路，两版都留在册里。**电阻侧**：真空室双壳并联环向电阻 7.6272 µΩ 对 ITER_D_22FPWQ 的 7.9 µΩ，差 −3.45 %，由两条独立算法逐位复核，且比书页原有的 8.98 µΩ 粗估更接近真值。**时间常数侧**：裸回路给 τ₁ 0.5834 s，比 CREATE 的 0.3623 s 高 57 %；四条候选解释（离散粒度 · 增厚壳 · 电阻率 · 模式定义）逐一实测证伪后，本会话先提出「CREATE 侧有传导连接」——**随即自证为错**：n = 0 环向涡流下各环本就只有互感耦合，径向连接只在两壳间重分配电流，而那已被并联电阻算进。真因在同一份件的前一页：22L4FE 第 2 页写明「All resistances (in SC coils, voltage amplifiers, connections) are neglected」，其 plasmaless 矩阵装着十一条 PF/CS 回路，而**零电阻回路保磁通、屏蔽真空室模**。以 Schur 补消去线圈后均匀模电感 5.0657 → 2.9152 µH（−42 %），τ₁ 0.5834 → 0.3418 s，对 CREATE-NL 差 −5.66 %，且本仓因线圈自感取法的区间 [0.3257, 0.3717] s **包含** CREATE 的 0.3623 与 0.3705。另测两条不影响结论：回路拓扑（12 独立线圈与 11 条真实回路逐位相同）与线圈几何来源（卡片 0.3418 s 对 22L4FE 自己的 0.3395 s）。★不去凑 τ，也不取对得最准的 a = 0.25 m 那一档（−0.44 %）当主结论。
