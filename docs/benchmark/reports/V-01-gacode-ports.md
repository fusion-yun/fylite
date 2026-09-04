---
title: V-01 · GACODE 三个白盒端口对它们翻译自的 Fortran
---

# V-01 · GACODE 三个白盒端口对它们翻译自的 Fortran

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | GACODE · rev 6357db306 · Apache-2.0 |
| **对象** | fylite: gyrofluid.rs (TGLF) / neoclassical.rs + dke.rs (NEO) / geometry.rs (GEO) |
| **算例** | `scenario/gacode-regression`（GACODE 自带回归算例（局部通量面）） |
| **数据** | 见 §5 表（6 项，纳入类别 public、public-derived、restricted-derived） |
| **门** | `$FYLITE_KERNEL/tests/test_tglf_vs_fortran.py`；`$FYLITE_KERNEL/tests/test_neo.py`；`$FYLITE_KERNEL/tests/test_neo_analytic_rust.py`；`$FYLITE_KERNEL/tests/test_rust_kernels.py`；`$FYLITE_KERNEL/tests/test_tglf_momentum.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：不成立——92 passed, 2 failed, 0 error, 0 skipped, 2 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 上游发布算例的逐字段答案 | relative | 1e-09 | machine_precision |  |
| 真实放电 deck 的电子能流（外半区 x>=0.55） | relative | 0.07 | measured_band |  |
| 真实 deck 的主离子环向应力（对 out.tglf.gbflux） | relative | 0.0002 | measured_band |  |
| 开旋转剪切后的环向应力（VPAR_SHEAR = 0.1 / 0.3） | relative | 0.001 | measured_band |  |
| 上游自带旋转回归算例 tglf06（GA 标准算例＋VPAR_SHEAR=1）逐通道逐种 | relative | 0.001 | measured_band |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/port-oracle-examples.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （场景）★局部算例没有装置、没有时间演化：它固定一个面的状态，问湍流/新经典/几何的答案。用它做 validation 是范畴错误。
- （场景）上游可重取（gafusion/gacode，Apache-2.0），所以这一档的参考数据存的是指针与版本，不是本体。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 上游算例逐字段 | 记录级 |  | 成立 |  |
| 真实 deck 外半区能流（谱积分层面） | 0.01-0.07 |  | 成立 | ★2026-08-29 当日两转：先因逐 ky 增长率只有 3/17 吻合而降为「逐模未验证」，同日查出根因是 Debye 屏蔽未接线（第四处移植缺陷），接上后 17/17 增长率吻合 1e-3、能流收进 ~1 %，本档升回「谱积分与逐模均已验证」。经过见报告 4 |
| 近边缘面 (x<=0.45) | 数量级 |  | 部分 | 能流本身小三个量级；Fortran 自己换 ky 网格也差 57 倍——运行点的性质，不是转换的 |
| 主离子环向应力，七面中模全吻合的五面 | 1.0000 |  | 成立 | ★★改判 2026-08-29：此前记的「mflux 是上游从不赋值的输出」是错的（grep 假象，--include=*.f90 匹配不到 tglf_run.F90，其 211/237 行注释 Pi_i/Pi_GB 正是在赋它）。真因是**跨饱和规则比较**：参照夹具 tglf_momentum_jintrac.json 录在 SAT_RULE=0/GYRO（其 eflux=34.393 自证，标准件在缺省下逐位复现），而测量跑在 SAT_RULE=2/CGYRO。同一个坑当天已在能流上踩过一次。设置对齐后：对 out.tglf.gbflux 七面五面逐位吻合，并由逐 ky sum_flux_spectrum 求和互证到 1e-7；★out.tglf.gbflux 列序 = pflux \| eflux \| mflux \| expwd（tglf.f90:83-86）；第四列是交换功率不是平行应力 |
| 主离子环向应力，x = 0.354 / 0.455 | -0.36 / -0.20 |  | 部分 | 近临界取根，不是应力：17 个 ky 里只有 2-3 个与上游不同且 γ≈0.01-0.02（谱峰 0.6），其余到机器精度；而 x=0.455 上这两个 ky 扛着 101 % 的总应力（谱近抵消 1.49×） |
| 开旋转剪切的环向应力（三面 × 两个剪切强度） | 2.3e-5 |  | 成立 | ★第五处移植缺陷的判据：solve_ky_modes 曾把原始 inp.species 交给 write_all_rows，旋转驱动丢了 sign_It 与 ave_c_tor_par(1,1)/Rmaj。所有已录 deck 的 VPAR_SHEAR 都是 0，故对既有判据全不可见；修前 -0.92 到 -0.94（反号且低 6-8 %） |
| tglf06（GA 标准算例＋平行速度剪切），规则 1 与 2，粒子/能量/环向应力 × 两个种 | 1.0000 |  | 成立 | ★公开命名算例（GA standard case），非本仓持有的某炮；算例自身 SAT_RULE=0 未移植，故规则在两边都显式写出——正是上一条改判说的那个坑 |
| 带 E×B 剪切的环向应力（VEXB_SHEAR=0.2，对上游、规则对齐） | 12.4x / 6.0x（规则 1 / 2）；再加 VPAR=0.4 时 0.081x / 0.109x |  | 不成立 | ★第六处移植缺陷 T-C33：上游谱移 E×B 模型是双趟（tglf_TM.f90:65-76），本征模自带 kx0 位移；本仓 spectral_shift() 在线性解之后才算、只喂饱和强度，kx0 从不回到 solve_ky_modes。同一批运行里能流只差 ~6 %——E×B 残余应力就是模结构里的对称破缺；★缺口已钉成实测闸子而非放宽的容差 |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_tglf_vs_fortran.py | 5 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_neo.py | 4 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_neo_analytic_rust.py | 40 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| $FYLITE_KERNEL/tests/test_rust_kernels.py | 30 过 / 2 败 / 0 错 / 0 跳 / 2 陈旧 | AssertionError: 410k-pair mutual took 27.5 ms (gate: 10 ms) \| AssertionError: 90-segment mutual_matrix took 66.8 ms |
| $FYLITE_KERNEL/tests/test_tglf_momentum.py | 13 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**不成立**（`re-run: assertion failed`）。

- tests/test_rust_kernels.py: AssertionError: 410k-pair mutual took 27.5 ms (gate: 10 ms) | AssertionError: 90-segment mutual_matrix took 66.8 ms

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/tglf/ga-std/ | sha256-manifest:90b57c908535c8d6a3dae673dbcad67c5b7512868247b0591d236f786be251ca | public | 5 files, 3782 B |
| $FYDOC_ORACLE/tgyro/treg01/ | sha256-manifest:17375200f98368c7c3197b53bc4ace7f5db6f94df23eaad670366281d84ddbe6 | public | 24 files, 81461 B |
| $FYDOC_ORACLE/frozen-libs/ | sha256-manifest:1e75b0c9e861cdff925e832bf0586d5acf6a00f54773795ba9894a62b46048ce | public-derived | 862 files, 13941886 B |
| $FYDOC_ORACLE/tglf/jintrac-102530/gbflux_jintrac.json | sha256:741a370a215b5dc2c6eff0f1e8e10e98add1d6a301279c3eddf1b2201ac56e46 | restricted-derived | 4238 B |
| $FYDOC_ORACLE/tglf/ga-standard-rotating.json | sha256:565c8d7395b18d028cb84632874ddbfdf6d971c9556c282c836b06d93d8f265b | public-derived | 4655 B |
| $FYDOC_ORACLE/waltz2007-momentum/table_I_and_tglf.json | sha256:b335eff4beda0b5e2d3d8cc602d73e60c1b7d73ca02f1c002757b792d2a12557 | public | 3504 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_tglf_vs_fortran.py tests/test_neo.py tests/test_neo_analytic_rust.py tests/test_rust_kernels.py tests/test_tglf_momentum.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：不成立。只回答本条自己那一类（V 验证）的问题，不外推。
