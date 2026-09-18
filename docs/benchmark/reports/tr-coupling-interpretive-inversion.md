---
title: "tr-coupling-interpretive-inversion"
---

# 解释性反演核：**接口早已成文，往返按 h² 收敛到 3.8e-5——此前只是没有入册**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-coupling-interpretive-inversion.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [双模、平衡耦合与代理栈](../domains/tr/coupling.md)　|　记录正本：`records/tr-coupling-interpretive-inversion.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：解释性反演核：**接口早已成文，往返按 h² 收敛到 3.8e-5——此前只是没有入册**
- **参考**：SRS-04 Eq. (eq-srs04-interp) 与本仓的预测性导热求解
- **验的需求**：`FR-TR-011`
- **跑在内核**：`sha256:94645111a7e2eb3f…`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：功率平衡反演：由剖面与源项反演实验通量 q_PB 与有效输运系数 χ_eff；平直剖面按名屏蔽

**参考**：SRS-04 Eq. (eq-srs04-interp) 与本仓的预测性导热求解

> 闭式：常源下 P(ρ)、q_PB 解析可知；往返：以常数 χ₀ 预测求解出的剖面反演回去，χ_eff·gm7 应为 χ₀。

**口径与适用域**：

> 稳态功率平衡（无 dT/dt 项）、单一热通道；几何取 Miller / 解析 / g-file 追踪 / 调用方给定的梯子。

## 判据与量到多少

:::{figure} ../figures/tr-coupling-interpretive-inversion-headroom.svg
:alt: tr-coupling-interpretive-inversion 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 反演核接口成文（路线 [TBD]） | — | reference_self_reported | 闭式：累积功率 1e-6、q_PB 1e-9，平直剖面全部屏蔽；往返（常数 χ₀ 预测 → 反演）χ_eff·gm7 对 χ₀：61 · 121 · 241 · 481 点 2.1e-3 · 5.7e-4 · 1.5e-4 · 3.8e-5（比 3.7 · 3.8 · 3.9）；门 `code/interpretive` 与它替换的配方在五档几何上逐位（1e-12） | **成立** |

**★接口成文：核 · C ABI · 文档门三层都在，式子与约定写在核的文档注释里；★往返按 h² 收敛**

- ★★**这条早就实现了，只是没入册**：`interpretive_channel`、C ABI 导出与 `code/interpretive` 门都在内核仓，测试也在（kernel 仓 Python 门）。本册一直把它记作空缺，是因为没有记录，不是因为没有实现。
- ★约定照实记：通量取 gm7 = ⟨|∇ρ|⟩ 的面积，导热律取 gm3 = ⟨|∇ρ|²⟩，所以 χ₀ 的预测解反演回来是 **χ₀/gm7** 而不是 χ₀——上游的约定，门里钉着，谁也不许把一个度规「修」成另一个。
- ★★**顺带查出并修掉一处 kernel 仓自己的红门**：g-file 档的参照梯子自 `12e603b`（通量规统一成整圈 Wb）起把每弧度的 dpsi 喂给整圈的 `equilibrium_ladder`，参照的 ρ 小 √(2π)，门恒红——门对、参照过期。`cargo test` 跑不到 kernel 仓的 Python 门，所以那次没看见；同批还有 `test_ladder_code` 四道，一并修。
- ★不在本条：dT/dt 项（SRS 标 [TBD]）、粒子通道反演（只有 `d_from_flux` 的换算）、工作流编排（归 fyanalysis）。

## 不可比的部分

- ★★**判决成立**：判据是「接口成文」（检查），本条另给了往返的二阶收敛作数值证据。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-18　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-TR-011` 判**成立**。反演核（`interpretive_channel` · C ABI · `code/interpretive`）早已在内核仓，本册缺的只是记录。往返按 h² 收敛到 3.8e-5（新钉成门）。★顺带修掉 kernel 仓自 12e603b 起恒红的 5 道门（参照梯子喂了每弧度 dpsi，ρ 小 √(2π)）。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:94645111a7e2eb3ff131ac2163078d5200afba5cbe6bc6bcf2537f466ad153fc`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/interpretive_inversion.json`    `sha256:bcfe1e5ed3deed99937723335f10b3ae5d4c09ed334bd711b71d6432c499f9e4`    接口、闭式、往返收敛、门的对位、通量规修复

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/transport.rs::tests::the_interpretive_inversion_matches_its_closed_form_and_masks_flat_profiles` —— 闭式与平直屏蔽
- `$FYLITE_KERNEL/tests/test_transport_core.py::test_interpretive_inverts_a_known_conduction_solve` —— 往返（2 %）
- `$FYLITE_KERNEL/tests/test_transport_core.py::test_the_round_trip_converges_at_second_order` —— ★往返的二阶收敛
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_the_miller_tier_with_deposition_only_is_the_same_to_the_bit` —— 门的对位：Miller
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_every_source_on_is_the_same_to_the_bit` —— 门的对位：全源
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_without_an_ion_temperature_ti_is_te_and_the_note_says_so` —— 无 Ti
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_the_gfile_tier_is_the_traced_ladder` —— ★g-file 档（本次修复通量规）
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_a_bound_ladder_is_taken_as_given` —— 给定梯子
- `$FYLITE_KERNEL/tests/test_interpretive_code.py::test_refusals_name_the_thing` —— 拒绝

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
