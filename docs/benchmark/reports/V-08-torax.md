---
title: V-08 · TORAX：同一份 QLKNN-10D 权重、同一篇 Bosch–Hale、同一篇 Redl-2021 的两个实现
---

# V-08 · TORAX：同一份 QLKNN-10D 权重、同一篇 Bosch–Hale、同一篇 Redl-2021 的两个实现

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | TORAX · git:b4d4063349dcab9241da6a7658a1a2083cf9b59d (TORAX_VERSION 1.4.3) · Apache-2.0 |
| **对象** | fylite: scenario.model.qlknn + nn.rs（QLKNN-10D）· kernel.dt_reactivity（zerod.rs）· kernel.redl_coefficients（neoclassical.rs:1060） |
| **算例** | —（无场景：局部或解析） |
| **数据** | 见 §5 表（1 项，纳入类别 public） |
| **门** | `$FYLITE_KERNEL/tests/test_torax_benchmark.py` |
| **登记册结论** | 部分（`assertion_state: accepted`） |
| **复测** | 2026-09-02：成立——4 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| QLKNN-10D 八个网的裸输出，320 点（训练盒内 / 盒外 / 稳定角 / 强驱动角四分区） | relative | 1e-09 | machine_precision | 一份权重的两个前向实现：TORAX 是 float64 JAX 的 flax MLP，本仓是 Rust 内核读 float32 .npz；★用量程归一而非逐点相对：数组过零且含大量恰零项，逐点比在 1e-14 量级的项上报出 1.7e-12，读不出东西 |
| clip_inputs 的边界盒算术（320×9），margin 0.95 | absolute | 0.0 | machine_precision | ★算例里有 48 点被刻意推到盒外 40%（每点三个分量），否则这条什么也没断言 |
| 组合层八列（主通量截零 + 除网相乘） | relative | 1e-09 | machine_precision |  |
| 组合层的零集：哪些点上通量恰为 0 | set_equality | 0.0 | machine_precision | ★★离散事实，没有容差可言。两个码可以在活点上吻合到 1e-15 而对『哪些点是活的』有分歧，任何范数都看不见 |
| Bosch–Hale D-T ⟨σv⟩，19 温度 0.2–50 keV | relative | 1e-09 | machine_precision | 同一篇 Bosch & Hale, Nucl. Fusion 32 (1992) 611, Table VII；★逐点相对是对的范数：⟨σv⟩ 跨十个数量级且不变号，绝对带只会考到热端 |
| Redl-2021 L31/L32/alpha，Z_eff ≥ 1.5 的全网格 | absolute | 1e-09 | machine_precision | ★f_trap 与两个 ν* 在两侧都是显式实参——陷落因子模型、库仑对数、碰撞率定义都进不来，分歧无处可藏 |
| Redl-2021 在 Z_eff = 1 的偏置，与 L34 的倍数 | absolute | 0.0 | measured_band | ★不是放宽的容差：钉的是已归因缺陷的实测大小，修好即变红——V-06 的先例，让处置在看得见数字时做 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYDOC_ORACLE/torax/README.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★★2026-08-30：本条原有的第三项（QLKNN-10D 逐网 + 组合 + 钳制盒，320 点，最劣 2.4e-15）已**退场**——两码都换了模型（TORAX 默认 qlknn_7_11_v1，fylite 退役二十网改用同一份 QLKNN_7_11 档案），比较对象不再是「两码之间」而是「两码各自对同一上游」，故并入 V-03，不在此重复记账。余下 Bosch–Hale 与 Redl 两项不变。
- （判据）一份权重的两个前向实现：TORAX 是 float64 JAX 的 flax MLP，本仓是 Rust 内核读 float32 .npz
- （判据）★用量程归一而非逐点相对：数组过零且含大量恰零项，逐点比在 1e-14 量级的项上报出 1.7e-12，读不出东西
- （判据）★算例里有 48 点被刻意推到盒外 40%（每点三个分量），否则这条什么也没断言
- （判据）★★离散事实，没有容差可言。两个码可以在活点上吻合到 1e-15 而对『哪些点是活的』有分歧，任何范数都看不见
- （判据）同一篇 Bosch & Hale, Nucl. Fusion 32 (1992) 611, Table VII
- （判据）★逐点相对是对的范数：⟨σv⟩ 跨十个数量级且不变号，绝对带只会考到热端
- （判据）★f_trap 与两个 ν* 在两侧都是显式实参——陷落因子模型、库仑对数、碰撞率定义都进不来，分歧无处可藏
- （判据）★不是放宽的容差：钉的是已归因缺陷的实测大小，修好即变红——V-06 的先例，让处置在看得见数字时做

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| QLKNN-10D 八网 × 320 点，最劣（比该网量程） | 2.433e-15 |  | 成立 | 分区无差别：盒内 2.4e-15 / 盒外 2.3e-15 / 稳定角 1.2e-15 / 强驱动角 1.8e-15 |
| clip_inputs 输入盒，320×9 最劣绝对 | 0.0 |  | 成立 |  |
| 组合层八列最劣；以及零集分歧数 | 2.433e-15；0 处分歧（ITG 道 243/320 恰零、TEM 道 263/320） |  | 成立 |  |
| 合并通道 efi_GB / efe_GB / pfe_GB 最劣 | 1.969e-15 |  | 成立 | ★★这是在 TORAX 的三个重标定旋钮全置 1 的前提下比的，而那不是 TORAX 的跑法：选 qlknn10D 会自动置 ITG_flux_ratio_correction=2.0 与 collisionality_multiplier=0.25，ETG_correction_factor 缺省 1/3（pydantic_model.py:127, :165-172）。拿本仓通量去比 TORAX 的一次仿真，电子热道会差 2 倍和 3 倍，而两边都按设计工作 |
| 本仓多做的两步在这套输入上的效果 | 输出盒 0.0（未触及，最大组合值 41.4 对界 300）；stability_clipping 0.0（构造性无操作） |  | 成立 | ★两者原因不同：一个是未达，一个是不可达——主通量截零已把那些列设成恰零 |
| Bosch–Hale ⟨σv⟩，19 点最劣相对 | 1.028e-14（T_i = 1.5 keV） |  | 成立 | 残差即 TORAX 在对数空间算再取指数的往返代价，本仓不走对数空间；★TORAX 的 pydantic 校验拒收 T > 50 keV，Bosch–Hale 自述 0.2–100 keV 有效区间的上半段取不到 |
| Redl L31/L32/alpha，Z_eff ≥ 1.5 全网格最劣绝对 | 8.9e-16 |  | 成立 | ★这是让下面两条缺陷『定位到行』的对照组：四个拟合里三个在整张网格上精确，所以缺陷不是『这篇论文移植得糙』 |
| Redl 在 Z_eff = 1：L31 / L32 / alpha 的偏置 | 1.8e-4 / 8.6e-5 / 2.7e-7；ν*=0 时 1.1e-16 / 2.7e-8 / 2.7e-7 |  | 不成立 | ★根因一行：rust/fylite/src/neoclassical.rs:1067 `let zm1 = (zeff - 1.0).max(1e-6);`——为保 sqrt(Z_eff−1) 的导数有限，代价是本仓永不求值 Z_eff=1 这个极限，纯氢被当成带痕量杂质；★两条进入路径：L31 只经带 ν* 因子的项，故无碰撞时精确；L32 的 zm1^1.1 与 alpha0 的线性 zm1 不带 ν*，所以『无碰撞纯氢』这个最干净的验证题本仓已经答的不是论文那道；偏置单向（总偏向更强的碰撞压低）。TORAX 取精确极限，自动微分的 NaN 另用自定义 JVP 处理（上游 3639e479） |
| Redl L34 与论文值（=L31）之比，Z_eff ≥ 1.5 最劣 | ν*=0: 1.000 · 0.1: 1.043 · 1: 1.204 · 3: 1.436 · 10: 1.889（最劣绝对差 0.195，系数量程 0.83） |  | 不成立 | ★★本仓的 Redl L34 不是 Redl 的 L34：论文式 (19) 就是一行 `L34 = L31`，而本仓（neoclassical.rs:1101）用式 (18) 的 f34t 过 f31 拟合——式 (18) 论文自己定义为 f_t,33^eff，即式 (17) 新经典电导率的有效陷落因子；★★代换来自 IMAS.jl，其源码在同一行自注 `# eq(18) from from A.Redl, et al. ; which is actually f33teff`；★★后果比『系数差 20%』更重：论文的 alpha 是在 L34=L31 前提下拟合的，目标是让乘积 L34·alpha 复现 NEO；而乘积正是 redl_bootstrap_point（neoclassical.rs:1121）乘在离子温度梯度上的因子。误差整个落在自举电流的离子温度梯度驱动项，随碰撞率单调增长——边缘最大；★本条推翻 2026-08-21 的裁定（neoclassical.py 模块头『本包指 IMAS.jl 支』）：sauter_redl 分支就是论文，此前记作『两个实现之差』的 4.1% / 15.7% 一直是缺陷本身。当时没看出来的原因文件自己写了——两支在无碰撞轴上逐位相同，而每条已发表极限检查都在那条轴上；处置留待裁定：改 L34=L31 会移动每一条已录自举答案，参照要重测。门已钉住量级 |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_torax_benchmark.py | 4 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYDOC_ORACLE/torax/ | sha256-manifest:37c13ef663e4f940274b2aa7647f982de32e1edcf5337f990650bb8ce40f3b4d | public | 13 files, 1948111 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDOC_ORACLE` 是 fydoc 仓的 `oracle/` 树（2026-09-04 前在 fydata），本仓与内核仓都以 `tests/data -> …/fydoc/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydoc/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_torax_benchmark.py
```

## 6. 结论

登记册：部分。复测 2026-09-02：成立。只回答本条自己那一类（V 验证）的问题，不外推。
