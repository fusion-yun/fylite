---
title: 验证状态 (Verification status)
---

# 验证状态 (Verification status)

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。 -->

这一页只答一个问题：**这些记录还作不作数。** 一条记录成立过，不等于它现在还成立——内核换了，它量的那个数就可能已经不是现在算出来的那个了。★所以每条记录记着它**跑在哪个内核上**，这一页拿它与基准内核比：不一致即 `stale`，等着重跑。

## 基准内核 (reference kernel)

- `libfylite` **sha256:301a962b8dc580f4…**
- 声明于 (recorded)：2026-09-17

:::{warning} ★★指纹锁在**字节**上，而内核的构建不是逐字节可复现的
2026-09-16 实测：源码与上一次提交**完全相同**，重建出的 `libfylite.so` 指纹却从`9c8e319b…` 变成 `301a962b…`——内嵌的路径 / 时间戳之类在动。**而它的答案逐位相同**（同一道 Solov'ev 三档 q0 完全一致）。

★于是「过期」会在**什么都没变**的重建后整批误报。这是本册当前最该修的一处机制问题：钥匙该锁在**行为**上（例如一组判据算例的答案摘要），不是锁在字节上。在那之前，读 `stale` 时要记得它可能只是重建过。
:::

:::{note} 为什么基准是一份**声明件**，不是本机当场算的指纹
本页入库并受 `--check` 守。它若嵌入跑命令那台机器的内核指纹，换一台机器门就红——而那不是任何人的错。基准记在 `kernel.json` 里，**有意更新**：内核一换就改它，于是所有记在旧内核上的记录当场转 `stale`，CI 据此重跑。
:::

## 总览 (overview)

- 记录 (records)：**18** 条
- 判决 (verdict)：成立 12 · 不成立 **1** · 未判 5 · 未评估 0
- 新鲜度 (freshness)：当前 18 · **过期 0** · 未知 0
- 评审 (review)：已评审 0 · 草稿 18 · 已被取代 0

## 已裁定保留的缺口 (retained open defects)

★★这些记录判 **fail**，而且**有意留着**——不是没人管，是量化清楚之后裁定先不改。

★**它们与「新冒出来的失败」分开计**：`--ci` 对前者退 3、对后者退 1。若两者混在一个退出码里，红就成了常态，而常态的红没有人看——真正新出的失败会被它盖住。

### [`eq-forward-boundary-rule-vs-kefit`](reports/eq-forward-boundary-rule-vs-kefit.md)

2026-09-16 记名读数（非缺陷但未定）：edge 规则收敛而离 KEFIT 更远，node 规则不收敛却更近；两者差在虚拟对是否带电流。判它需要独立于两者的真值，这道题上没有。用户裁定「保留负面结果」，本条以 inconclusive 原样留册。

### [`eq-forward-green-response-shared`](reports/eq-forward-green-response-shared.md)

2026-09-17 ★★**求积阶数不由任何机制共享**：`coilshare` 两个设置项（默认 4 / 3）与重构侧一个设置项（默认 8）加一处硬编码（3）。配错的代价已量到 2.8e-04（环）/ 4.0e-03（探针），与孪生回路的残差同量级，而不会有任何报警。★要么让两侧读同一份响应（抄录说的 `ResponseCache`），要么至少让门禁盯住这两组默认值不走散。

### [`eq-inverse-iter-reference-separatrix`](reports/eq-inverse-iter-reference-separatrix.md)

2026-09-17 仍记名保留（用户裁定「保留负面结果」）：达成 kappa 1.7941 比目标低 2.98 %、delta_lower 低 10.21 %，判据 1 %——**这一条是真结论**，不是判法问题：把 kappa 顶上去的设置（enp 0.5）要 37.5 MA·t 且永不收敛。所需 30.6 MA·t 仍无额定可比（牌上缺 pf_active/supply）。★收敛那一条已于 1.1 版改为读数——原判 fail 是我自立的标准，不是缺陷。

### [`eq-reconstruct-twin-observable-space`](reports/eq-reconstruct-twin-observable-space.md)

2026-09-17 ★**那三道探针的成因仍未定**（0.30 / 0.33 / 0.53 sigma，而环一族中位 0.031）。★★**一个假说已经实测否掉**：不是 p' / FF' 基张不出真值。真值用 emp = enp = 1（两者随 psi_N 线性），重构只拟合 2 个系数，看着像基不够；但把阶数抬上去**反而更坏**——(npp, nff) 从 (1,1) 到 (2,2)，chi2 0.8514 → 4.599、q0 偏差 -1.19e-03 → -3.15e-01（读数 `twin_basis_order.json`）。★这是经典的病态：磁测量管不住多出来的自由度，多给就往数据管不着的方向跑。★**因此剩下的候选是探针一侧的建模或几何**，未查。

### [`tr-closure-15d-source-switches`](reports/tr-closure-15d-source-switches.md)

2026-09-16 记名保留（用户裁定「内核欠缺的功能也保留」）：驱动电流三道 `j_bs` / `j_cd` / `j_lh` 在所有变体里恒为零，**驱动源项这一块验不了**。三个产出名字都在，缺的是喂给它们的输入——下一步是造一个带 CD 波源的算例，而不是删掉这条判据。★另记：本条尚无守它的门，与 tr-closure-dt-burn-astra、tr-pedestal-zerod-bookkeeping-metis 同。

### [`tr-closure-dt-burn-astra`](reports/tr-closure-dt-burn-astra.md)

2026-09-16 记名保留两处（用户裁定「不改内核，保留负面结果」「内核欠缺的功能也保留」）：〔一〕α 份额偏 +1.23 %，而分支比是常数、本该到舍入——干净的可判偏差，等内核查；〔二〕`code/zerod` **不给 α 的电子/离子分配**，ASTRA 给（轴上 0.585 / 0.414），这一项对 1.5D 演化是必需的，判据已立、等内核补。★另记：本条尚无守它的门，需补一道 pytest。

### [`tr-pedestal-zerod-bookkeeping-metis`](reports/tr-pedestal-zerod-bookkeeping-metis.md)

2026-09-16 记名保留（用户裁定「不改内核，保留负面结果」「内核欠缺的功能也保留」）：〔一〕0D 体积恰为 2π²Ra²κ，比 METIS 高 -2.87 %，四点散布仅 1.3e-04——**公式差，一次可修**；这条偏差直接传给 0D 存量账。〔二〕0D 不输出热能 W、没有加料/抽气控件、没有台基，于是 FR-TR-014 的存量守恒在这一层无从验起。判据都已立，等内核补入口。

## 按域 (by domain)

| 组 | 域 | 需求 | 覆盖 | 记录 | 成立 | 不成立 | 过期 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 平衡 (Equilibrium) | [前向自由边界与 Green 响应核](domains/eq/forward.md) | 4 | 4 | 6 | 5 | 0 | 0 |
| 平衡 (Equilibrium) | [磁面几何、全局量与形状表示](domains/eq/surface.md) | 3 | 2 | 1 | 1 | 0 | 0 |
| 平衡 (Equilibrium) | [演化自由边界与涡流电路](domains/eq/evolve.md) | 1 | 1 | 1 | 1 | 0 | 0 |
| 平衡 (Equilibrium) | [静态逆解：形状到线圈电流](domains/eq/inverse.md) | 1 | 1 | 2 | 1 | 0 | 0 |
| 平衡 (Equilibrium) | [测量重构与约束阶梯](domains/eq/reconstruct.md) | 8 | 2 | 3 | 3 | 0 | 0 |
| 平衡 (Equilibrium) | [约定与口径：COCOS 与插件接入](domains/eq/convention.md) | 2 | 2 | 1 | 1 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [竖直稳定性、线圈受力与电磁线性模型](domains/mhd/vertical.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [解析判据阶梯：外扭曲模 q 极限与气球模第一稳定边界](domains/mhd/analytic.md) | 2 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [能量原理变分内核 L2](domains/mhd/energy.md) | 7 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [全 delta-W、V5 基准与阻性壁模](domains/mhd/deltaw.md) | 6 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [方程组求解与边界条件](domains/tr/equations.md) | 2 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [闭包插件面：输运系数与源项](domains/tr/closure.md) | 3 | 1 | 2 | 0 | 0 | 0 |
| 输运 (Transport) | [求解范式：刚性稳定化与稳态通量匹配](domains/tr/paradigm.md) | 4 | 1 | 1 | 0 | 0 | 0 |
| 输运 (Transport) | [台基、锯齿与 0D 存量](domains/tr/pedestal.md) | 3 | 1 | 1 | 0 | 1 | 0 |
| 输运 (Transport) | [双模、平衡耦合与代理栈](domains/tr/coupling.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [守恒、金标 parity 与口径](domains/tr/conservation.md) | 5 | 0 | 0 | 0 | 0 | 0 |

## 记录明细 (records)

| 记录 | 域 | 类 | 判决 | 版本 | 末次修订 | 评审 | 跑在内核 | 新鲜度 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`eq-convention-gfile-cocos-roundtrip`](reports/eq-convention-gfile-cocos-roundtrip.md) | eq-convention | 验证 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-evolve-analytic-circuit-limits`](reports/eq-evolve-analytic-circuit-limits.md) | eq-evolve | 验证 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-forward-boundary-rule-vs-kefit`](reports/eq-forward-boundary-rule-vs-kefit.md) | eq-forward | 对拍 | 未判（读数） | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-forward-chease-solovev`](reports/eq-forward-chease-solovev.md) | eq-forward | 对拍 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-forward-green-response-shared`](reports/eq-forward-green-response-shared.md) | eq-forward | 验证 | 成立 | 1.0 | 2026-09-17 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-forward-kefit-east137985`](reports/eq-forward-kefit-east137985.md) | eq-forward | 对拍 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-forward-self-contained-core`](reports/eq-forward-self-contained-core.md) | eq-forward | 验证 | 成立 | 1.0 | 2026-09-17 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-forward-solovev-fixed-boundary`](reports/eq-forward-solovev-fixed-boundary.md) | eq-forward | 验证 | 成立 | 1.1 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-inverse-freegsnke-east137985`](reports/eq-inverse-freegsnke-east137985.md) | eq-inverse | 对拍 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-inverse-iter-reference-separatrix`](reports/eq-inverse-iter-reference-separatrix.md) | eq-inverse | 验证 | 未判（读数） | 1.1 | 2026-09-17 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-reconstruct-kefit-twin`](reports/eq-reconstruct-kefit-twin.md) | eq-reconstruct | 对拍 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-reconstruct-twin-observable-space`](reports/eq-reconstruct-twin-observable-space.md) | eq-reconstruct | 验证 | 成立 | 1.2 | 2026-09-17 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-reconstruct-twin-truth-recovery`](reports/eq-reconstruct-twin-truth-recovery.md) | eq-reconstruct | 验证 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`eq-surface-chease-fixed-boundary-east`](reports/eq-surface-chease-fixed-boundary-east.md) | eq-surface | 对拍 | 成立 | 1.1 | 2026-09-17 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`tr-closure-15d-source-switches`](reports/tr-closure-15d-source-switches.md) | tr-closure | 验证 | 未判（读数） | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`tr-closure-dt-burn-astra`](reports/tr-closure-dt-burn-astra.md) | tr-closure | 对拍 | 未判（读数） | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`tr-paradigm-pereverzev`](reports/tr-paradigm-pereverzev.md) | tr-paradigm | 验证 | 未判（读数） | 1.1 | 2026-09-17 | 草稿 | `sha256:301a962b8dc5…` | current |
| [`tr-pedestal-zerod-bookkeeping-metis`](reports/tr-pedestal-zerod-bookkeeping-metis.md) | tr-pedestal | 对拍 | 不成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:301a962b8dc5…` | current |

## 接 CI/CD (wiring this into CI)

本页与它背后的记录是为流水线准备的，接法只有三条命令：

```bash
python tools/benchmark-transcribe.py --check   # 上游 SRS 动了没有（动了就重抽判据）
python tools/benchmark-book.py --check         # 生成件是不是最新的
python tools/benchmark-book.py --ci            # 有过期或不成立的记录就退 1
```

★**内核变更怎么触发重验**：内核换了之后跑 `--bump-kernel` 更新 `kernel.json`，所有记在旧内核上的记录当场转 `stale`；`--ci` 退 1 并列出**每条过期记录该重跑的那道门**（记录的 `run.realizes` 里点名的 pytest 目标），流水线照着跑一遍，重跑后把新的内核指纹与读数写回记录、记一条 `change`、退回 0。

★★**退出码分四档**，因为「要处理」与「已知道」不是一回事：

| 码 | 意思 | 流水线该做什么 |
| :--- | :--- | :--- |
| `0` | 全部当前且成立 | 放行 |
| `1` | 有**过期**（内核换了，必须重验）或**未裁定**的不成立 | 拦下 |
| `3` | 只剩记名的缺口：**已裁定保留的不成立**（`◇`），或挂在**成立**记录上的缺口（`◆`） | 自己决定；缺口与理由都印在上面 |
| `2` | 前提不在（如抄录件的源不在此检出） | 按环境问题处理，不是判决 |

★**为什么 3 要与 1 分开**：一条量化清楚、归属明确、有人裁定保留的缺口，留在册上是**有用**的；但它若也让流水线红，红就成了常态，而常态的红没有人看——真正新出现的失败会被它盖住。要把一条 fail 挪进这一档，得在记录的 `provenance.open_defect` 里写明**谁、何时、为什么**保留；一个布尔挡不住下一个人把它当成陈年噪声删掉。

★★**`◆` 那一类 2026-09-17 才开始报**，此前 `--ci` 只从**判决为不成立**的记录里收缺口，于是「判决成立、但记着一处已知窟窿」的那些，本页印着、流水线一条不报——同一件事两个口径。★这一类恰恰更该报：一条 fail 自己会喊，而一条「成立，但有个洞」没有别的东西替它说话。补上当天就露出 4 条此前一直看不见的（`eq-forward-boundary-rule-vs-kefit` · `eq-inverse-iter-reference-separatrix` · `tr-closure-15d-source-switches` · `tr-closure-dt-burn-astra`）。
