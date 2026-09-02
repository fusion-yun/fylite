---
title: V-07 · TGYRO 映射层：整份 localdump 全键对照扩到六个算例（treg01..05 + iter01，28 个半径）
---

# V-07 · TGYRO 映射层：整份 localdump 全键对照扩到六个算例（treg01..05 + iter01，28 个半径）

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | GACODE / TGYRO · rev 6357db306 · Apache-2.0 |
| **对象** | fylite: scenario.model.mapping.tglf_inputs（tgyro_tglf_map.f90）+ oracles.gacode_derived.neo_inputs（tgyro_neo_map.f90） |
| **算例** | `scenario/gacode-regression`（GACODE 自带回归算例（局部通量面）） |
| **数据** | 见 §5 表（5 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_tgyro_cases.py` |
| **登记册结论** | 部分（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——88 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| out.tglf.localdump / out.neo.localdump 中两侧都有的每一个键（不是手挑表），每个算例的 revision 与 mxh 从它自己的 input.tgyro.gen 读出 | relative | 2e-05 | reference_stated | localdump 打六位有效数字，这就是容差的来源；★门里一个求解器设置都没有手写：径向网格、离子数、TGLF revision/MXH、密度演化规则、NEO 分辨率全部解析自 .gen——手写的六算例设置表只在写下它的那天与 deck 一致 |
| 映射未发出的每一个开关：本仓缺省必须等于 TGYRO 的取值（含 iter01 关旋转后的 VEXB_SHEAR/VPAR_i/VPAR_SHEAR_i） | absolute | 0.0 | machine_precision |  |
| treg03/04 的 P_PRIME_LOC 与 ALPHA_SA：本仓自洽值乘上 dlnpdr(第2趟)/dlnpdr(第3趟) 后是否逐位复现 dump | relative | 2e-05 | reference_stated | ★这不是放宽的容差，是更强的判据：把上游的滞后解释掉之后仍要求打印位数级一致 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/benchmark/reports/V-07-tgyro-cases.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （判据）localdump 打六位有效数字，这就是容差的来源
- （判据）★门里一个求解器设置都没有手写：径向网格、离子数、TGLF revision/MXH、密度演化规则、NEO 分辨率全部解析自 .gen——手写的六算例设置表只在写下它的那天与 deck 一致
- （判据）★这不是放宽的容差，是更强的判据：把上游的滞后解释掉之后仍要求打印位数级一致
- （场景）★局部算例没有装置、没有时间演化：它固定一个面的状态，问湍流/新经典/几何的答案。用它做 validation 是范畴错误。
- （场景）上游可重取（gafusion/gacode，Apache-2.0），所以这一档的参考数据存的是指针与版本，不是本体。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 六个算例 28 个半径，TGLF + NEO 全键对照 | TGLF 共享键 78(treg01)/86(treg02-05)/85(iter01)，NEO 40/46/52；最大偏差 4.3e-6 |  | 成立 | ★偏差全部低于六位有效数字的打印下限；iter01 八个半径 r/a=0.1..0.8，treg 四个 r/a=0.2..0.65；★真正判别的是 treg03/04：不复刻三趟 quasigrad，AS_2 在 r/a=0.2 会是 0.957 而非 1.088（差 12 %），RLNS_2 会是 0.981 而非 0.730（差 34 %） |
| 「未发出的键 = 缺省相同」断言 | 六例 28 个半径零分歧 |  | 成立 |  |
| TGYRO 交给 TGLF 的压强梯度落后一趟 profile_set（上游行为，非移植缺陷） | dlnpdr(2)/dlnpdr(3) = 1.1400 / 1.0795 / 1.0310 / 1.0000（r/a = 0.20/0.35/0.50/0.65） |  | 部分 | ★★deck 与自己不自洽：种梯度来自 tgyro_flux_vector 的那趟 quasigrad，dlnpdr 来自上一趟 profile_functions，而 profile_functions 不会再跑第二次；★只在某个种走准中性规则（TGYRO_DEN_METHOD_i = -1）时发作，所以 treg01/02/05 与 iter01 都看不见；★正确读法不是「映射差 14 %」而是「逐位复现 TGYRO 就等于复现一处滞后」；需要上游那个数的调用方可经 surface_state(dpext=...) 自己喂 |
| 取件器的样条边界条件（本仓缺陷，尚未修） | Q_PRIME_LOC 3.3e-4 / OMEGA_ROT_DERIV 1.0e-4（iter01 r/a=0.1），改自然样条后归零 |  | 不成立 | ★★GACODE cub_spline 是自然样条（c(1)=c(n)=0），test_mapping.py 的取件器用的是 scipy 缺省的 not-a-knot；两者在内区一致、向两端发散，所以 r/a≥0.2 的 treg01 从未看见；★test_tgyro_cases.py::_spline 已用 bc_type="natural"；test_mapping.py 本次未动——它不会因此变红，但它做的不是上游做的事 |
| treg05 在映射层上的增量 | 0 —— 与 treg02 的 localdump 四个半径逐字节相同 |  | 部分 | ★迭代方法/LOC_DX/LOC_RELAX 都是求解器循环设置，碰不到初始剖面状态；以门的形式记着（可证伪）而不是写成一句话；★采集偏差：方法 2 拒绝 RELAX_ITERATIONS=0，其 =1 的 dump 落在已更新剖面上，故冻结的 deck 把方法强制为 1 |
| treg04 的 DKE 分支在 deck 里的足迹 | 一个键：SIM_MODEL 0 → 2 |  | 部分 | ★treg03/treg04 的 out.neo.localdump 其余部分逐字节相同，out.tglf.localdump 整份相同——本条只证明映射选对了分支，分支算得对不对是 V-04 的判据；读成「经 TGYRO 验证了 DKE 求解器」是夸大 |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_tgyro_cases.py | 88 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDATA_ORACLE/tgyro_treg02/ | sha256-manifest:2f34a5c22646a3b870880dda57ac04e926289acc17fabd860939184bc2b91a10 | public | 31 files, 42295 B |
| $FYDATA_ORACLE/tgyro_treg03/ | sha256-manifest:ed9132169d911c92ffdc53b344112ff15f6f93f4613d6443688724f0f5b44d40 | public | 31 files, 42712 B |
| $FYDATA_ORACLE/tgyro_treg04/ | sha256-manifest:f5b672749dc0c1dc289d96abc9f3ba333a9243d48a691faf18a66e14a0a95127 | public | 31 files, 41917 B |
| $FYDATA_ORACLE/tgyro_treg05/ | sha256-manifest:a38a291b2b5a17a0c22a50ab1da697ec594d18b51c8fcac0485eda75ba7afd48 | public | 31 files, 42149 B |
| $FYDATA_ORACLE/tgyro_iter01/ | sha256-manifest:3631addadb05de4f096beb29874f0407cfa116bd80318b4ea57eafc8c3abe0c3 | public | 43 files, 137151 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDATA_ORACLE` 是 fydata 仓的 `oracle/` 树，本仓与内核仓都以 `tests/data -> …/fydata/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydata/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_tgyro_cases.py
```

## 6. 结论

登记册：部分。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
