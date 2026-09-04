---
title: V-04 · 上游 GACODE 自带的回归套件（TGLF 九例 / NEO 21 例）
---

# V-04 · 上游 GACODE 自带的回归套件（TGLF 九例 / NEO 21 例）

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | GACODE · rev 6357db306 · Apache-2.0 |
| **对象** | fylite: gyrofluid.rs (TGLF) / neoclassical.rs + dke.rs (NEO) |
| **算例** | `scenario/gacode-regression`（GACODE 自带回归算例（局部通量面）） |
| **数据** | 见 §5 表（2 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_gacode_regression.py` |
| **登记册结论** | 部分（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——42 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| TGLF 逐 ky 增长率与频率谱（21 点） | relative | 1e-09 | machine_precision |  |
| TGLF 粒子流 / 能流 / 交换（规则 1、2） | relative | 0.0001 | reference_stated | out.tglf.gbflux 只打五位有效数字，这就是容差的来源 |
| TGLF ky 网格 | relative | 1e-12 | machine_precision | 它是每个通量数的输入，不是结果 |
| NEO ⟨j∥B⟩ / Γ / Q / Sauter（Miller 对齐后） | relative | 1e-06 | reference_stated | out.neo.transport 打八位有效数字 |
| 饱和规则 3 的饱和幅值（声明式缺口） | relative | 0.75 | measured_band | 带是用来看漂移的，不判对错；FEATURE §3.2 已声明 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/docs/note/benchmark/reports/V-04-gacode-regression-suite.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- （判据）out.tglf.gbflux 只打五位有效数字，这就是容差的来源
- （判据）它是每个通量数的输入，不是结果
- （判据）out.neo.transport 打八位有效数字
- （判据）带是用来看漂移的，不判对错；FEATURE §3.2 已声明
- （场景）★局部算例没有装置、没有时间演化：它固定一个面的状态，问湍流/新经典/几何的答案。用它做 validation 是范畴错误。
- （场景）上游可重取（gafusion/gacode，Apache-2.0），所以这一档的参考数据存的是指针与版本，不是本体。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| tglf01/02/06/08，规则 1 与 2，粒子+能流 × 两个种 | 6.2e-06 … 2.1e-05 |  | 成立 |  |
| 同上，逐 ky 增长率与频率（21 点） | 1.0e-13 … 4.6e-13（γ）/ 1.1e-13 … 2.1e-12（freq） |  | 成立 | 谱跨 ky 0.1–24.2 并在 ky≈0.9 换支（频率变号），两侧在同一点换 |
| 交换道（expwd），四例 × 两规则 | 3.5e-05 |  | 成立 | ★★第八处移植缺陷**已修**（2026-08-29 同日）：修前 7.4–34 %。上游 freq_QL 是 tglf_LS.f90:444 的本征值 xi*(rr+xi*ri)，配 gamma_out=rr / freq_out=-ri，即 freq + i·gamma；本仓传 gamma − i·freq（= −i 倍）后又乘 xi，两次旋转相消。两处各改一行；★判定不靠读源码：由粒子道权重定出的 R = a·Re[C]/\|φ\|²，两侧各自反解在 tglf01 上 42 个 (ky, 种) 点吻合 1.9e-11；★藏住的原因：全仓从无任何判据比过这一道，而它在两种实现里都种间等大反号（电荷中性，缺旋转照样成立） |
| NEO reg08/reg12 + EQUILIBRIUM_MODEL=2（圆截面与成形，两种与三种含 Z=6 碳） | 1.7e-08 … 2.6e-08 |  | 成立 | ★几何模型两侧都说 Miller。按出厂 deck（EQUILIBRIUM_MODEL=0）跑，端口对 ⟨j∥B⟩ 是恒定的 1.43 %——两种与三种同一个 1.43 %、Sauter 同一个 1.40 %，这是几何因子的指纹，不是端口的；21 例里 19 例在本机逐位复现出厂 out.neo.prec |
| tglf07 kinetic carbon（USE_AVE_ION_GRID，**已修**） | 规则 1 通量 2.1e-05、ky 网格逐位相同、增长率 6.2e-11 |  | 成立 | ★★第七处移植缺陷**已修**（2026-08-29 同日，ABI v117→v118）：修前 rho_ion 0.644949 对 1.0、整张 ky 网格错 1.55 倍、能流差 79 %。上游 tglf_startup.f90:180 在缺省（.false.）下把 rho_ion 覆盖为**第一个离子**的 sqrt(m·τ)/z，本仓 gyroradii() 恒取电荷加权平均，全仓无该键槽位；★藏住的原因：两支只在「有第二个离子越过 10 % 电荷门且 sqrt(m·τ)/z 与第一个不同」时才分开，而 tests/data 里每一份三种 deck 的杂质都在门下。杂质扫描确认机理：Z=2 任意浓度精确 / Z=6 在 1 % 精确 / 两个一样的碳精确 / Z=1.5 差 3.8 %——判别量是**平均动没动**，不是电荷；★rho_ion 同时喂**饱和层**，不只是网格；★顺带：gyroradii 的零总电荷从静默回落 1.0 改成拒绝（-39）——上游那里是 tglf_error |
| tglf04 Waltz E×B 淬灭规则（**已修**） | 增长率 1.4e-13；规则 2 通量 1.4e-5 / 1.7e-5 |  | 成立 | ★★第九处移植缺陷**已修**（2026-08-29）：修前增长率恒高 **0.0300000000**（21 个 ky 同一个数）= 0.3·√κ·ALPHA_QUENCH·VEXB_SHEAR。`get_gamma_net`（tglf_LS.f90:615-627）已移植，且**施加在线性解内部**——上游在任何下游看到之前就淬灭 `gamma_out`，所以**模宽搜索也搜被淬灭的谱**；★`quench_growth_rates` 是另一件事（SAT1 的带状流混合），其形参叫 `gamma_net` 正是因为它期待这一步已经发生；★该标志此前只被处理了**两个角色中的一个**（只用来关谱移模型）——比未知键更坏，因为 deck 看起来是被支持的。`tests/test_tglf_rust.py` 里有一条测试当时把这个半处理**断言成了正确行为**，已改写 |
| tglf09 有限 β（USE_BPER，QL 权重的场指标 j=2，**已修**） | 规则 1 粒子/能量/交换全部 1.00000（最差 5.7e-6） |  | 成立 | ★★第十处移植缺陷**已修**（2026-08-29）：修前通量短 9.9–17.5 %。上游 QL 权重带**场指标**、通量是它们之和（tglf_LS.f90:983-990）；本仓此前只在**应力**上有该指标（动量线补的），粒子/能量/交换三道都没有；★定位当时就很干净故一处即可修：增长率 8.7e-14 精确（电磁**线性解**本来就对）、逐 ky 对上游 field-1 块 3.8e-11 精确（在的那份精确）、只有积分后短；★`j=3`（B_par）同批从源码补上但**未验证**——上游九个回归 deck 里没有 USE_BPAR 的；其形状特意反常（只有粒子与交换、无能量，用 1.5p_tot−0.5p_par），已在源码注释里点名 |
| tglf05 谱移 E×B（T-C33，已知未关） | 环向应力 −2.9e-08 对上游 −6.9734（规则 1） |  | 不成立 | ★该算例 VPAR_SHEAR=0，全部环向应力就是 E×B 对称破缺，故这是 T-C33 最干净的一次量测：不是差一个倍数，是结构性的零；同批粒子 4.8e-04、能流 1.6e-02（规则 2 上 4.3e-02 / 6.0e-02），已钉为实测闸子不放宽；★增长率 1e-13 恰恰因为本仓线性解从不见剪切，它对上的是上游的第一趟 |
| 饱和规则 3（NMODES=1，声明式缺口） | 粒子 60.6–61.2 % / 能流 40.3–42.4 %，增长率 4.6e-13 | declared-gap | 未评估 | 分歧整个在饱和幅值里，正是 FEATURE §3.2 声明的位置（几何权重只对一支加） |
| tglf03 s-α 几何 | 增长率 1.19 / 能流 57 % | out-of-scope | 未评估 | ★出局，但是被**静默改写**的：全仓 GEOMETRY_FLAG 只在 mapping.py:175 出现一次且写死为 1，没有任何地方从 deck 读它。fluxes_rust 会拒绝扛不住的 UNITS 与未移植的饱和规则，唯独几何放行——这一点单独留了一道门；上游自己拒绝该 deck 的规则 2/3 |
| 规则 2 在两种粒子上精确、在三种上差几个百分点（**线索，未定性**） | tglf01 规则 2 = 1.0e-05；tglf07 规则 2 = 5.3e-02（同一 deck 规则 1 = 2.1e-05） |  | 部分 | ★模是同一批（增长率 6.2e-11），dlnpdr 两侧同为 12.0 到十位；偏差**按种且符号混杂**（电子粒子 −5.3 %、主离子 +2.3 %、碳 −0.5 %），那是逐 ky 强度误差积分后的样子，不是公共饱和因子的样子；★★可能与 V-01 里 JINTRAC（也是三种）长期挂着的规则 2 带（0.1–5 %）**是同一件事**。若是，那条带就有了成因而不只是容差。已钉成对照闸子，供下一个人从正确的形状起步 |
| ★★SAT_RULE 2 的余量：**次主模取根**（根因已定位） | 主模逐 ky 精确（2.4e-12 / 4.1e-12 / 2.7e-14）；次主模 tglf07 4.0e-2、tglf09 1.0；tglf09 mode-2 增长率 ky[0] 上游 0.72876 对本仓 0.04359 |  | 部分 | ★★★2026-08-30 定位到底：**不在强度公式、不在几何、不在 QL 权重**。逐 ky 对 out.tglf.field_spectrum 时主模处处精确而次主模不精确，再对 out.tglf.eigenvalue_spectrum 显示**我们把一个根滤掉了**；★根因=**FILTER 门限**：本仓在 ky=0.1 处 max_freq = 2.0×0.1×1.0 = 0.2，恰好卡在 mode-1 的 \|freq\|=0.166 与 mode-2 的 0.273 之间；上游需 ≥1.364。滤波机理两侧相同（tglf_eigensolver.f90:2918），差的是累加值——本仓停在种子 2\|wdh\|/R_unit，逐种项没超过它而上游超过了；★tglf05（旋转）已于同日经谱移阻尼收口，不再属于这条；★诊断钩 FY_DUMP_FILTER 已留在 gyrofluid.rs 里（逐 ky 打出门限） |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_gacode_regression.py | 42 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/FYDOC-CASE-05-gacode/tglf.json | sha256:0c1a0c61ccabb7c80971b3b66d59065d222e1821db1ab93ddf3c0d1677701789 | public | 93406 B |
| $FYDOC_ORACLE/FYDOC-CASE-05-gacode/neo.json | sha256:d1e51dbd7825766d4ae028dee03860509229012d268f2d86b98828f57148dd4e | public | 35720 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `cases/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/cases` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/cases tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_gacode_regression.py
```

## 6. 结论

登记册：部分。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
