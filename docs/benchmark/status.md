---
title: 验证状态 (Verification status)
---

# 验证状态 (Verification status)

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。 -->

这一页只答一个问题：**这些记录还作不作数。** 一条记录成立过，不等于它现在还成立——内核换了，它量的那个数就可能已经不是现在算出来的那个了。★所以每条记录记着它**跑在哪个内核上**，这一页拿它与基准内核比：不一致即 `stale`，等着重跑。

## 基准内核 (reference kernel)

- **`fylite_kernel@94ca1a29d6ed`**（内核仓的 git 提交）
- 声明于 (recorded)：2026-09-19

:::{note} ★指纹锁在**内核仓的 git 提交**上（用户 2026-09-19 裁定），不再锁在库的字节上
此前锁在 `libfylite.so` 的 sha256 上，而构建不是逐字节可复现的——2026-09-16 实测源码一字未改、重建出的库指纹就变了（答案逐位相同），「过期」会在什么都没变的重建后整批误报。提交号锁的是**源码**：`--bump-kernel` 读内核仓的 HEAD，`rust/` 下有未提交改动时拒绝。

★它不锁中间层：`libfylite.so` 里还有公开仓的 `fylite_runtime`，那一层的改动随公开仓自己的提交走。每条记录另把当时的库 sha256 留作参考（`library_sha256`），只记不判。
:::

:::{note} 为什么基准是一份**声明件**，不是本机当场算的指纹
本页入库并受 `--check` 守。它若嵌入跑命令那台机器的内核指纹，换一台机器门就红——而那不是任何人的错。基准记在 `kernel.json` 里，**有意更新**：内核一换就改它，于是所有记在旧内核上的记录当场转 `stale`，CI 据此重跑。
:::

## 总览 (overview)

- 记录 (records)：**57** 条
- 判决 (verdict)：成立 53 · 不成立 **0** · 未判 3 · 未评估 1
- 新鲜度 (freshness)：当前 57 · **过期 0** · 未知 0
- 评审 (review)：已评审 0 · 草稿 57 · 已被取代 0

## 已裁定保留的缺口 (retained open defects)

★★这些记录判 **fail**，而且**有意留着**——不是没人管，是量化清楚之后裁定先不改。

★**它们与「新冒出来的失败」分开计**：`--ci` 对前者退 3、对后者退 1。若两者混在一个退出码里，红就成了常态，而常态的红没有人看——真正新出的失败会被它盖住。

### [`eq-forward-boundary-rule-vs-kefit`](reports/eq-forward-boundary-rule-vs-kefit.md)

2026-09-16 记名读数（非缺陷但未定）：edge 规则收敛而离 KEFIT 更远，node 规则不收敛却更近；两者差在虚拟对是否带电流。判它需要独立于两者的真值，这道题上没有。用户裁定「保留负面结果」，本条以 inconclusive 原样留册。

### [`eq-forward-green-response-shared`](reports/eq-forward-green-response-shared.md)

2026-09-17 ★**剩下的那一处**：两扇门是两次独立调用，调用方**显式**传不同的求积阶数时仍会分开，跨调用的一致性没有东西强制（代价量过：环 2.8e-04 / 探针 4.0e-03）。★缓解已到位——默认值共享、两边都回显所用阶数，于是这件事查得到；**但查得到不等于不会发生**，补一道跨门的门禁才算真收口。

### [`eq-inverse-iter-reference-separatrix`](reports/eq-inverse-iter-reference-separatrix.md)

用户裁定「不改内核，保留负面结果」（本会话，ITER 这一例点名在内）：ITER 参考分离面在这台机器的线圈额定内**买不到**——无界设计要 PF1 1.14 倍、PF6 1.28 倍的 DINA 额定，形状仍差（kappa −3 %、delta_lower −10 %）；在额定内重解守住额定、分离面 11.8 mm，但不再收敛（残差 0.072）。**这是设计本身的结论，不是实现的缺陷**：同一需求 `FR-EQ-005` 的 FreeGSNKE 对拍记录判成立。

### [`eq-reconstruct-curvature-prior`](reports/eq-reconstruct-curvature-prior.md)

2026-09-17 ★★**lambda 的响应非单调**：1e-3 / 1e-2 有效，**0.1 处解崩掉**（不收敛，q0 +9.28e+00），1 与 10 又收敛但精度差。可用窗口因此很窄，而「窄」这件事本身没有被解释——怀疑是罚行与截断 SVD 保留秩的相互作用，未查。★在查清之前，**把 lambda 当成必须 A/B 扫出来的量**，不要抄。

### [`eq-reconstruct-mse-shelved`](reports/eq-reconstruct-mse-shelved.md)

用户 2026-09-17 裁定「搁置 MSE」：`FR-EQ-007` · `FR-EQ-009` 不实现，直到用户重启。前提（内核无 MSE）由门钉住。

### [`eq-reconstruct-twin-observable-space`](reports/eq-reconstruct-twin-observable-space.md)

2026-09-17 ★**那三道探针的成因仍未定**（0.30 / 0.33 / 0.53 sigma，而环一族中位 0.031）。★★**一个假说已经实测否掉**：不是 p' / FF' 基张不出真值。真值用 emp = enp = 1（两者随 psi_N 线性），重构只拟合 2 个系数，看着像基不够；但把阶数抬上去**反而更坏**——(npp, nff) 从 (1,1) 到 (2,2)，chi2 0.8514 → 4.599、q0 偏差 -1.19e-03 → -3.15e-01（读数 `twin_basis_order.json`）。★这是经典的病态：磁测量管不住多出来的自由度，多给就往数据管不着的方向跑。★**因此剩下的候选是探针一侧的建模或几何**，未查。

### [`tr-closure-plugin-dispatch`](reports/tr-closure-plugin-dispatch.md)

2026-09-17 ★★2026-09-18 **门已补上**（三道）：分派若退化成「总是走 constant」，现在当场变红——两个跑通闭包的解平方和逐位对读数。★另：「统一前端」只在**两个**闭包上验过，要验满需给另三个各配一组输入。

### [`tr-conservation-fyo-dd-contract`](reports/tr-conservation-fyo-dd-contract.md)

2026-09-17 ★第二格（摘要闸）的门在**内核仓的构建脚本**里，本仓 CI 跑不到——与 `tr-pedestal-sawtooth-kadomtsev` 同一处代价。★第三格是翻译差（LinkML vs JSON Schema），不是缺陷，但也**没有被消解**：要真答上游那一格，得有人决定 fylite 是否引入 LinkML，那是个设计决定不是测量。

### [`tr-conservation-time-order`](reports/tr-conservation-time-order.md)

2026-09-17 ★**空间收敛阶仍未量**：Richardson 隔离掉了空间误差，那是它能干净量时间阶的理由，也是它答不了空间阶的理由。★另：金标 parity（FUSE.jl / TORAX）那一半缺的是外部码在同一算例上的输出，属语料。★门在内核仓，本仓 CI 跑不到。

### [`tr-coupling-equilibrium-outer-loop`](reports/tr-coupling-equilibrium-outer-loop.md)

2026-09-17 ★门在内核仓、且要跑 261 秒，本仓 CI 跑不到它。★另：两半对 q 的分歧**向内变大**（0.20 % → 1.00 % → 3.40 %），看着像「芯部梯子最难对齐」，但**没有去查**是不是这个原因。

### [`tr-coupling-nn-weights-external`](reports/tr-coupling-nn-weights-external.md)

2026-09-17 ★★2026-09-18 **门已补上**（四道：内核常量权重表扫描 · 包外与打包声明 · 检出找得到自己的模型 · 缺模型按名拒绝）。★★**补门时查出一个真 bug**：`fylite.nn` 的 `BUILTIN_DIR` 指着 09-01 就改名掉的 `nn_tables/`，干净检出里 `nn.available()` 返回 `[]`，`models/README.md` 自己的示例跑不通——这条路此前一道测试都没有。已修（一行，`models/README.md` 09-08 那条注记改了指针，漏了这一处）。★另：第四格「逐位对拍」缺的是导出侧在 `.npz` 里写下参考输入输出，也没做。

### [`tr-paradigm-coupled-block-adr`](reports/tr-paradigm-coupled-block-adr.md)

2026-09-17 ★**等上游裁 ADR**。在那之前本条无判据可判，而 fylite 这一侧**没有欠账**：现有的耦合对自洽（交换账 9.6e-14），只是它不是一个全通道的隐式块。★若最终裁定要块解，要动的是四个求解器的组织方式——与 `FR-TR-002` 的架构缺口同一层。

### [`tr-paradigm-flux-match-vs-pde`](reports/tr-paradigm-flux-match-vs-pde.md)

2026-09-17 ★门在内核仓，本仓 CI 跑不到（虽然它只要 0.01 s）。★另：收敛是**一阶**，因为 PDE 的 D 取单侧差分的梯度而通量重构用中心差分。**没有去改它**——那是实现的既有精度，改它是另一件事，且要重新验所有依赖它的记录。

### [`tr-pedestal-sawtooth-kadomtsev`](reports/tr-pedestal-sawtooth-kadomtsev.md)

2026-09-17 ★**门在内核仓，不在本仓**：本条的两道门是 Rust 单测，而本册其余各条的门都是 fylite 侧的 pytest。CI 只跑后者，于是这条记录的新鲜度**不会**被本仓的流水线守住。★补法有二：在 fylite 侧把锯齿经 `code/evolve` 跑出来量一遍，或让 CI 也跑内核仓的测试。两者都没做。

## 按域 (by domain)

| 组 | 域 | 需求 | 覆盖 | 记录 | 成立 | 不成立 | 过期 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 平衡 (Equilibrium) | [前向自由边界与 Green 响应核](domains/eq/forward.md) | 4 | 4 | 6 | 5 | 0 | 0 |
| 平衡 (Equilibrium) | [磁面几何、全局量与形状表示](domains/eq/surface.md) | 3 | 3 | 2 | 2 | 0 | 0 |
| 平衡 (Equilibrium) | [演化自由边界与涡流电路](domains/eq/evolve.md) | 1 | 1 | 1 | 1 | 0 | 0 |
| 平衡 (Equilibrium) | [静态逆解：形状到线圈电流](domains/eq/inverse.md) | 1 | 1 | 2 | 1 | 0 | 0 |
| 平衡 (Equilibrium) | [测量重构与约束阶梯](domains/eq/reconstruct.md) | 8 | 8 | 8 | 7 | 0 | 0 |
| 平衡 (Equilibrium) | [约定与口径：COCOS 与插件接入](domains/eq/convention.md) | 2 | 2 | 2 | 2 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [竖直稳定性、线圈受力与电磁线性模型](domains/mhd/vertical.md) | 3 | 3 | 3 | 3 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [解析判据阶梯：外扭曲模 q 极限与气球模第一稳定边界](domains/mhd/analytic.md) | 2 | 2 | 2 | 2 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [能量原理变分内核 L2](domains/mhd/energy.md) | 7 | 7 | 7 | 7 | 0 | 0 |
| MHD 稳定性 (MHD Stability) | [全 delta-W、V5 基准与阻性壁模](domains/mhd/deltaw.md) | 6 | 6 | 6 | 6 | 0 | 0 |
| 输运 (Transport) | [方程组求解与边界条件](domains/tr/equations.md) | 2 | 2 | 2 | 2 | 0 | 0 |
| 输运 (Transport) | [闭包插件面：输运系数与源项](domains/tr/closure.md) | 3 | 3 | 4 | 4 | 0 | 0 |
| 输运 (Transport) | [求解范式：刚性稳定化与稳态通量匹配](domains/tr/paradigm.md) | 4 | 4 | 4 | 3 | 0 | 0 |
| 输运 (Transport) | [台基、锯齿与 0D 存量](domains/tr/pedestal.md) | 3 | 3 | 3 | 3 | 0 | 0 |
| 输运 (Transport) | [双模、平衡耦合与代理栈](domains/tr/coupling.md) | 3 | 3 | 3 | 3 | 0 | 0 |
| 输运 (Transport) | [守恒、金标 parity 与口径](domains/tr/conservation.md) | 5 | 2 | 2 | 2 | 0 | 0 |

## 记录明细 (records)

| 记录 | 域 | 类 | 判决 | 版本 | 末次修订 | 评审 | 跑在内核 | 新鲜度 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [`eq-convention-gfile-cocos-roundtrip`](reports/eq-convention-gfile-cocos-roundtrip.md) | eq-convention | 验证 | 成立 | 1.21 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-convention-ladder-flux-gauge`](reports/eq-convention-ladder-flux-gauge.md) | eq-convention | 验证 | 成立 | 1.15 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-evolve-analytic-circuit-limits`](reports/eq-evolve-analytic-circuit-limits.md) | eq-evolve | 验证 | 成立 | 1.21 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-forward-boundary-rule-vs-kefit`](reports/eq-forward-boundary-rule-vs-kefit.md) | eq-forward | 对拍 | 未判（读数） | 1.21 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-forward-chease-solovev`](reports/eq-forward-chease-solovev.md) | eq-forward | 对拍 | 成立 | 1.21 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-forward-green-response-shared`](reports/eq-forward-green-response-shared.md) | eq-forward | 验证 | 成立 | 2.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-forward-kefit-east137985`](reports/eq-forward-kefit-east137985.md) | eq-forward | 对拍 | 成立 | 1.21 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-forward-self-contained-core`](reports/eq-forward-self-contained-core.md) | eq-forward | 验证 | 成立 | 1.22 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-forward-solovev-fixed-boundary`](reports/eq-forward-solovev-fixed-boundary.md) | eq-forward | 验证 | 成立 | 1.22 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-inverse-freegsnke-east137985`](reports/eq-inverse-freegsnke-east137985.md) | eq-inverse | 对拍 | 成立 | 1.21 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-inverse-iter-reference-separatrix`](reports/eq-inverse-iter-reference-separatrix.md) | eq-inverse | 验证 | 未判（读数） | 1.23 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-reconstruct-curvature-prior`](reports/eq-reconstruct-curvature-prior.md) | eq-reconstruct | 验证 | 成立 | 1.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-reconstruct-fast-ion-pressure`](reports/eq-reconstruct-fast-ion-pressure.md) | eq-reconstruct | 验证 | 成立 | 1.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-reconstruct-kefit-twin`](reports/eq-reconstruct-kefit-twin.md) | eq-reconstruct | 对拍 | 成立 | 1.21 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-reconstruct-kinetic-outer`](reports/eq-reconstruct-kinetic-outer.md) | eq-reconstruct | 验证 | 成立 | 1.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-reconstruct-mse-shelved`](reports/eq-reconstruct-mse-shelved.md) | eq-reconstruct | 验证 | 未评估 | 1.2 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-reconstruct-posterior-bands`](reports/eq-reconstruct-posterior-bands.md) | eq-reconstruct | 验证 | 成立 | 1.14 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-reconstruct-twin-observable-space`](reports/eq-reconstruct-twin-observable-space.md) | eq-reconstruct | 验证 | 成立 | 1.21 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-reconstruct-twin-truth-recovery`](reports/eq-reconstruct-twin-truth-recovery.md) | eq-reconstruct | 验证 | 成立 | 1.21 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-surface-chease-fixed-boundary-east`](reports/eq-surface-chease-fixed-boundary-east.md) | eq-surface | 对拍 | 成立 | 1.22 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`eq-surface-mxh-gfile-fit`](reports/eq-surface-mxh-gfile-fit.md) | eq-surface | 验证 | 成立 | 1.16 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-analytic-ballooning-first-stability`](reports/mhd-analytic-ballooning-first-stability.md) | mhd-analytic | 验证 | 成立 | 1.12 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-analytic-external-kink-qlimit`](reports/mhd-analytic-external-kink-qlimit.md) | mhd-analytic | 验证 | 成立 | 1.13 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-deltaw-delivery-records`](reports/mhd-deltaw-delivery-records.md) | mhd-deltaw | 验证 | 成立 | 1.9 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-deltaw-normal-modes`](reports/mhd-deltaw-normal-modes.md) | mhd-deltaw | 验证 | 成立 | 1.9 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-deltaw-screw-pinch`](reports/mhd-deltaw-screw-pinch.md) | mhd-deltaw | 验证 | 成立 | 1.9 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-deltaw-toroidal-fixed-boundary`](reports/mhd-deltaw-toroidal-fixed-boundary.md) | mhd-deltaw | 对拍 | 成立 | 1.8 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-deltaw-toroidal-free-boundary`](reports/mhd-deltaw-toroidal-free-boundary.md) | mhd-deltaw | 对拍 | 成立 | 1.8 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-deltaw-wall-and-rwm`](reports/mhd-deltaw-wall-and-rwm.md) | mhd-deltaw | 对拍 | 成立 | 1.8 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-energy-conformal-map`](reports/mhd-energy-conformal-map.md) | mhd-energy | 验证 | 成立 | 1.11 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-energy-coupled-assembly`](reports/mhd-energy-coupled-assembly.md) | mhd-energy | 验证 | 成立 | 1.10 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-energy-fluid-high-beta`](reports/mhd-energy-fluid-high-beta.md) | mhd-energy | 验证 | 成立 | 1.10 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-energy-surface-current-beta-limit`](reports/mhd-energy-surface-current-beta-limit.md) | mhd-energy | 验证 | 成立 | 1.13 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-energy-three-term-assembly`](reports/mhd-energy-three-term-assembly.md) | mhd-energy | 验证 | 成立 | 1.10 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-energy-vacuum-general-shape`](reports/mhd-energy-vacuum-general-shape.md) | mhd-energy | 验证 | 成立 | 1.10 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-energy-variational-cylinder`](reports/mhd-energy-variational-cylinder.md) | mhd-energy | 验证 | 成立 | 1.10 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-vertical-coil-forces-analytic`](reports/mhd-vertical-coil-forces-analytic.md) | mhd-vertical | 验证 | 成立 | 1.18 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-vertical-freegsnke-east137985`](reports/mhd-vertical-freegsnke-east137985.md) | mhd-vertical | 确认 | 成立 | 2.15 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`mhd-vertical-lti-export`](reports/mhd-vertical-lti-export.md) | mhd-vertical | 验证 | 成立 | 1.8 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-closure-15d-source-switches`](reports/tr-closure-15d-source-switches.md) | tr-closure | 验证 | 成立 | 1.22 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-closure-dt-burn-astra`](reports/tr-closure-dt-burn-astra.md) | tr-closure | 对拍 | 成立 | 1.23 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-closure-lazy-plugin-resolution`](reports/tr-closure-lazy-plugin-resolution.md) | tr-closure | 验证 | 成立 | 1.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-closure-plugin-dispatch`](reports/tr-closure-plugin-dispatch.md) | tr-closure | 验证 | 成立 | 1.20 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-conservation-fyo-dd-contract`](reports/tr-conservation-fyo-dd-contract.md) | tr-conservation | 验证 | 成立 | 1.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-conservation-time-order`](reports/tr-conservation-time-order.md) | tr-conservation | 验证 | 成立 | 1.18 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-coupling-equilibrium-outer-loop`](reports/tr-coupling-equilibrium-outer-loop.md) | tr-coupling | 验证 | 成立 | 1.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-coupling-interpretive-inversion`](reports/tr-coupling-interpretive-inversion.md) | tr-coupling | 验证 | 成立 | 1.9 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-coupling-nn-weights-external`](reports/tr-coupling-nn-weights-external.md) | tr-coupling | 验证 | 成立 | 1.20 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-equations-boundary-family`](reports/tr-equations-boundary-family.md) | tr-equations | 验证 | 成立 | 3.17 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-equations-channel-descriptor`](reports/tr-equations-channel-descriptor.md) | tr-equations | 验证 | 成立 | 1.17 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-paradigm-coupled-block-adr`](reports/tr-paradigm-coupled-block-adr.md) | tr-paradigm | 验证 | 未判（读数） | 1.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-paradigm-flux-match-vs-pde`](reports/tr-paradigm-flux-match-vs-pde.md) | tr-paradigm | 验证 | 成立 | 1.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-paradigm-momentum-channel`](reports/tr-paradigm-momentum-channel.md) | tr-paradigm | 验证 | 成立 | 1.7 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-paradigm-pereverzev`](reports/tr-paradigm-pereverzev.md) | tr-paradigm | 验证 | 成立 | 1.24 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-pedestal-eped-feedback`](reports/tr-pedestal-eped-feedback.md) | tr-pedestal | 验证 | 成立 | 1.0 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-pedestal-sawtooth-kadomtsev`](reports/tr-pedestal-sawtooth-kadomtsev.md) | tr-pedestal | 验证 | 成立 | 1.19 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |
| [`tr-pedestal-zerod-bookkeeping-metis`](reports/tr-pedestal-zerod-bookkeeping-metis.md) | tr-pedestal | 对拍 | 成立 | 1.25 | 2026-09-19 | 草稿 | `fylite_kernel@94ca1a29d6ed` | current |

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
