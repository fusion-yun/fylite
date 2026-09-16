---
title: 验证状态 (Verification status)
---

# 验证状态 (Verification status)

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。 -->

这一页只答一个问题：**这些记录还作不作数。** 一条记录成立过，不等于它现在还成立——内核换了，它量的那个数就可能已经不是现在算出来的那个了。★所以每条记录记着它**跑在哪个内核上**，这一页拿它与基准内核比：不一致即 `stale`，等着重跑。

## 基准内核 (reference kernel)

- `libfylite` **sha256:e0e1b16cf0004c12…**
- 声明于 (recorded)：2026-09-16

:::{note} 为什么基准是一份**声明件**，不是本机当场算的指纹
本页入库并受 `--check` 守。它若嵌入跑命令那台机器的内核指纹，换一台机器门就红——而那不是任何人的错。基准记在 `kernel.json` 里，**有意更新**：内核一换就改它，于是所有记在旧内核上的记录当场转 `stale`，CI 据此重跑。
:::

## 总览 (overview)

- 记录 (records)：**13** 条
- 判决 (verdict)：成立 8 · 不成立 **1** · 未判 4 · 未评估 0
- 新鲜度 (freshness)：当前 13 · **过期 0** · 未知 0
- 评审 (review)：已评审 0 · 草稿 13 · 已被取代 0

## 已裁定保留的缺口 (retained open defects)

★★这些记录判 **fail**，而且**有意留着**——不是没人管，是量化清楚之后裁定先不改。

★**它们与「新冒出来的失败」分开计**：`--ci` 对前者退 3、对后者退 1。若两者混在一个退出码里，红就成了常态，而常态的红没有人看——真正新出的失败会被它盖住。

### [`eq-forward-boundary-rule-vs-kefit`](reports/eq-forward-boundary-rule-vs-kefit.md)

2026-09-16 记名读数（非缺陷但未定）：edge 规则收敛而离 KEFIT 更远，node 规则不收敛却更近；两者差在虚拟对是否带电流。判它需要独立于两者的真值，这道题上没有。用户裁定「保留负面结果」，本条以 inconclusive 原样留册。

### [`eq-forward-solovev-fixed-boundary`](reports/eq-forward-solovev-fixed-boundary.md)

2026-09-16 用户裁定「不改内核，保留负面结果」：q0 对闭式解差 -0.00326，判据 1e-4（画在同题上 CHEASE 达到的 3.56e-06 放宽约 28 倍）。缺口归属已查明在 fylite 侧，内核本轮不动——记录挂 fail 等它改，容差不放宽。

### [`eq-inverse-iter-reference-separatrix`](reports/eq-inverse-iter-reference-separatrix.md)

2026-09-16 用户裁定「不改内核，保留负面结果」：逆解 settled 而未 converged；达成 kappa 1.7941 比目标低 2.98 %，delta_lower 低 10.21 %；所需 30.6 MA·t 无额定可比（牌上缺 pf_active/supply）。三条原样留册，容差不放宽；牌补上供电额定后电流那一条才判得了。

### [`tr-closure-dt-burn-astra`](reports/tr-closure-dt-burn-astra.md)

2026-09-16 记名保留两处（用户裁定「不改内核，保留负面结果」「内核欠缺的功能也保留」）：〔一〕α 份额偏 +1.23 %，而分支比是常数、本该到舍入——干净的可判偏差，等内核查；〔二〕`code/zerod` **不给 α 的电子/离子分配**，ASTRA 给（轴上 0.585 / 0.414），这一项对 1.5D 演化是必需的，判据已立、等内核补。★另记：本条尚无守它的门，需补一道 pytest。

## 按域 (by domain)

| 组 | 域 | 需求 | 覆盖 | 记录 | 成立 | 不成立 | 过期 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 平衡 (Equilibrium) | [前向自由边界与 Green 响应核](domains/eq/forward.md) | 4 | 2 | 4 | 2 | 1 | 0 |
| 平衡 (Equilibrium) | [磁面几何、全局量与形状表示](domains/eq/surface.md) | 3 | 2 | 1 | 1 | 0 | 0 |
| 平衡 (Equilibrium) | [演化自由边界与涡流电路](domains/eq/evolve.md) | 1 | 1 | 1 | 1 | 0 | 0 |
| 平衡 (Equilibrium) | [静态逆解：形状到线圈电流](domains/eq/inverse.md) | 1 | 1 | 2 | 1 | 0 | 0 |
| 平衡 (Equilibrium) | [测量重构与约束阶梯](domains/eq/reconstruct.md) | 8 | 1 | 2 | 2 | 0 | 0 |
| 平衡 (Equilibrium) | [约定与口径：COCOS 与插件接入](domains/eq/convention.md) | 2 | 2 | 1 | 1 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [竖直稳定性、线圈受力与电磁线性模型](domains/mhd/vertical.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [解析判据阶梯：外扭曲模 q 极限与气球模第一稳定边界](domains/mhd/analytic.md) | 2 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [能量原理变分内核 L2](domains/mhd/energy.md) | 7 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [全 delta-W、V5 基准与阻性壁模](domains/mhd/deltaw.md) | 6 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [方程组求解与边界条件](domains/tr/equations.md) | 2 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [闭包插件面：输运系数与源项](domains/tr/closure.md) | 3 | 1 | 1 | 0 | 0 | 0 |
| 输运 (Transport) | [求解范式：刚性稳定化与稳态通量匹配](domains/tr/paradigm.md) | 4 | 1 | 1 | 0 | 0 | 0 |
| 输运 (Transport) | [台基、锯齿与 0D 存量](domains/tr/pedestal.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [双模、平衡耦合与代理栈](domains/tr/coupling.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [守恒、金标 parity 与口径](domains/tr/conservation.md) | 5 | 0 | 0 | 0 | 0 | 0 |

## 记录明细 (records)

| 记录 | 域 | 类 | 判决 | 版本 | 末次修订 | 评审 | 跑在内核 | 新鲜度 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`eq-convention-gfile-cocos-roundtrip`](reports/eq-convention-gfile-cocos-roundtrip.md) | eq-convention | 验证 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-evolve-analytic-circuit-limits`](reports/eq-evolve-analytic-circuit-limits.md) | eq-evolve | 验证 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-forward-boundary-rule-vs-kefit`](reports/eq-forward-boundary-rule-vs-kefit.md) | eq-forward | 对拍 | 未判（读数） | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-forward-chease-solovev`](reports/eq-forward-chease-solovev.md) | eq-forward | 对拍 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-forward-kefit-east137985`](reports/eq-forward-kefit-east137985.md) | eq-forward | 对拍 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-forward-solovev-fixed-boundary`](reports/eq-forward-solovev-fixed-boundary.md) | eq-forward | 验证 | 不成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-inverse-freegsnke-east137985`](reports/eq-inverse-freegsnke-east137985.md) | eq-inverse | 对拍 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-inverse-iter-reference-separatrix`](reports/eq-inverse-iter-reference-separatrix.md) | eq-inverse | 验证 | 未判（读数） | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-reconstruct-kefit-twin`](reports/eq-reconstruct-kefit-twin.md) | eq-reconstruct | 对拍 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-reconstruct-twin-truth-recovery`](reports/eq-reconstruct-twin-truth-recovery.md) | eq-reconstruct | 验证 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`eq-surface-chease-fixed-boundary-east`](reports/eq-surface-chease-fixed-boundary-east.md) | eq-surface | 对拍 | 成立 | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`tr-closure-dt-burn-astra`](reports/tr-closure-dt-burn-astra.md) | tr-closure | 对拍 | 未判（读数） | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |
| [`tr-paradigm-pereverzev`](reports/tr-paradigm-pereverzev.md) | tr-paradigm | 验证 | 未判（读数） | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |

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
| `3` | 只剩**已裁定保留**的缺口 | 自己决定；缺口与理由都印在上面 |
| `2` | 前提不在（如抄录件的源不在此检出） | 按环境问题处理，不是判决 |

★**为什么 3 要与 1 分开**：一条量化清楚、归属明确、有人裁定保留的缺口，留在册上是**有用**的；但它若也让流水线红，红就成了常态，而常态的红没有人看——真正新出现的失败会被它盖住。要把一条 fail 挪进这一档，得在记录的 `provenance.open_defect` 里写明**谁、何时、为什么**保留；一个布尔挡不住下一个人把它当成陈年噪声删掉。
