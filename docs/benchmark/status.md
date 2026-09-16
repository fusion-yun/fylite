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

- 记录 (records)：**1** 条
- 判决 (verdict)：成立 0 · 不成立 **0** · 未判 1 · 未评估 0
- 新鲜度 (freshness)：当前 1 · **过期 0** · 未知 0
- 评审 (review)：已评审 0 · 草稿 1 · 已被取代 0

## 按域 (by domain)

| 组 | 域 | 需求 | 覆盖 | 记录 | 成立 | 不成立 | 过期 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 平衡 (Equilibrium) | [前向自由边界与 Green 响应核](eq/forward.md) | 4 | 0 | 0 | 0 | 0 | 0 |
| 平衡 (Equilibrium) | [磁面几何、全局量与形状表示](eq/surface.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| 平衡 (Equilibrium) | [演化自由边界与涡流电路](eq/evolve.md) | 1 | 0 | 0 | 0 | 0 | 0 |
| 平衡 (Equilibrium) | [静态逆解：形状到线圈电流](eq/inverse.md) | 1 | 0 | 0 | 0 | 0 | 0 |
| 平衡 (Equilibrium) | [测量重构与约束阶梯](eq/reconstruct.md) | 8 | 0 | 0 | 0 | 0 | 0 |
| 平衡 (Equilibrium) | [约定与口径：COCOS 与插件接入](eq/convention.md) | 2 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [竖直稳定性、线圈受力与电磁线性模型](mhd/vertical.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [解析判据阶梯：外扭曲模 q 极限与气球模第一稳定边界](mhd/analytic.md) | 2 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [能量原理变分内核 L2](mhd/energy.md) | 7 | 0 | 0 | 0 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [全 delta-W、V5 基准与阻性壁模](mhd/deltaw.md) | 6 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [方程组求解与边界条件](tr/equations.md) | 2 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [闭包插件面：输运系数与源项](tr/closure.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [求解范式：刚性稳定化与稳态通量匹配](tr/paradigm.md) | 4 | 1 | 1 | 0 | 0 | 0 |
| 输运 (Transport) | [台基、锯齿与 0D 存量](tr/pedestal.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [双模、平衡耦合与代理栈](tr/coupling.md) | 3 | 0 | 0 | 0 | 0 | 0 |
| 输运 (Transport) | [守恒、金标 parity 与口径](tr/conservation.md) | 5 | 0 | 0 | 0 | 0 | 0 |

## 记录明细 (records)

| 记录 | 域 | 类 | 判决 | 版本 | 末次修订 | 评审 | 跑在内核 | 新鲜度 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `tr-paradigm-pereverzev` | tr-paradigm | 验证 | 未判（读数） | 1.0 | 2026-09-16 | 草稿 | `sha256:e0e1b16cf000…` | current |

## 接 CI/CD (wiring this into CI)

本页与它背后的记录是为流水线准备的，接法只有三条命令：

```bash
python tools/benchmark-transcribe.py --check   # 上游 SRS 动了没有（动了就重抽判据）
python tools/benchmark-book.py --check         # 生成件是不是最新的
python tools/benchmark-book.py --ci            # 有过期或不成立的记录就退 1
```

★**内核变更怎么触发重验**：内核换了之后跑 `--bump-kernel` 更新 `kernel.json`，所有记在旧内核上的记录当场转 `stale`；`--ci` 退 1 并列出**每条过期记录该重跑的那道门**（记录的 `run.realizes` 里点名的 pytest 目标），流水线照着跑一遍，重跑后把新的内核指纹与读数写回记录、记一条 `change`、退回 0。

★退出码：`0` 全部当前且成立；`1` 有过期或不成立；`2` 前提不在（如抄录件的源不在此检出）。
