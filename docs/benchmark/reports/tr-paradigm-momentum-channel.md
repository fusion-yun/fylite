---
title: "tr-paradigm-momentum-channel"
---

# 环向动量通道：**闭合补齐了三处——pinch、TGLF 的动量通量、DD 4 的名字**；pinch 对闭式二阶收敛

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-paradigm-momentum-channel.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [求解范式：刚性稳定化与稳态通量匹配](../domains/tr/paradigm.md)　|　记录正本：`records/tr-paradigm-momentum-channel.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：环向动量通道：**闭合补齐了三处——pinch、TGLF 的动量通量、DD 4 的名字**；pinch 对闭式二阶收敛
- **参考**：FYTOK-SRS-04 `FR-TR-008` 判据「动量通道设计成文」与 pinch 方程的闭式解
- **验的需求**：`FR-TR-008`
- **跑在内核**：`sha256:a7a86a75fc27ac15…`（新鲜度 **current**）
- **记录版本**：1.2　**评审**：草稿　**日期**：2026-09-18

## 问的是什么

**被量的**：Π = M(−χ_φ ω′ + v_φ ω) 走 ETS 正则形式上名为 `momentum` 的通道描述子；χ_φ 取 Prandtl 闭合或宿主绑定的湍流值，v_φ 为 pinch

**参考**：FYTOK-SRS-04 `FR-TR-008` 判据「动量通道设计成文」与 pinch 方程的闭式解

> 常系数 χ、v、T 下 ω = C e^{kx} + (T/v)x + Tχ/v²（k = v/χ），边值定 C。

**口径与适用域**：

> 单一离子动量通道，环向转动频率 ω；χ_φ 取 Prandtl 闭合或宿主绑定的湍流值；pinch 由调用方给。

## 判据与量到多少

:::{figure} ../figures/tr-paradigm-momentum-channel-headroom.svg
:alt: tr-paradigm-momentum-channel 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 动量通道设计成文（路线 [TBD]） | — | reference_self_reported | pinch 闭式：33 · 65 · 129 点误差比落在 (3.5, 4.5)；无 pinch 与全零 pinch 逐位相等；门上 v_φ = −2 m/s 把轴上 ω 从 27 452.7 抬到 34 245.2 rad/s；缺省 Prandtl 闭合 momentum_phi/d = max(0.7 χ_i, 1e-6) 逐位；TGLF 的 χ_φ/χ_i 在 0.15 < x < 0.85 中位 0.415（0.022 … 0.506） | **成立** |

**★设计成文且落地：方程 · 描述子 · 门 · DD 名四层都在；★pinch 对闭式二阶收敛，TGLF 给出的 Prandtl 数 O(1)**

- ★★**本条之前有三处缺口，本批补上**：动量方程没有对流（pinch）项；TGLF 的动量通量算了但进不了 march（march 只认 `prandtl·χ_i`）；`core_transport` 上没有动量通道的名字。见内核仓 `app-provenance.md` 2026-09-18 其八。
- ★**名字照 DD 4.1.1 写 `momentum_phi`**，不是 SRS 判据里的 `momentum_tor`——后者是 DD 3 的拼法，DD 4 把 toroidal 统一改成了 phi。SRS 说的「`momentum_tor` 声明可解析、求解 fail-loud」在 fylite 这里不适用：通道是实装的，不是占位。
- ★**χ_φ 的归一是推出来的，不是抄来的**：`χ_φ = χ_GB|Π/Π_GB| / ((R/a)|vpar_shear|(n_i m_i)/(n_e m_ref))`，Π_GB = n_e T_e a(ρ_s/a)²。判它的是 Prandtl 数落在 O(1)——漏一个 R/a 或密度质量因子会差出这个因子，但这**不是**对另一个码的对拍。
- ★**`momentum_flux` 缺省关**：把平行剪切喂给 TGLF 会连热通量一起动，缺省若开，湍流档带转动的逐位对拍与页面对拍就断了。要湍流 χ_φ 得显式开。
- ★不在本条：剩余应力 / 内禀转动（pinch 剖面要调用方给；TGLF 的对流与扩散部分没有拆开）；湍流 χ_φ 进 march 的方式与 χ_turb 相同——宿主按块把扩展门的答案绑进 `code/evolve`，门内不调 TGLF。

## 不可比的部分

- ★★**判决成立**：判据是「设计成文」（检查），本条另给了 pinch 的二阶收敛与门上的行为作数值证据。
- ★门在内核仓，本仓 CI 跑不到。

## 追溯

- 首次入册 2026-09-18　末次修订 2026-09-18　版本 1.2　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-18 | Claude Opus 5 (1M context) | 首次入册：`FR-TR-008` 判**成立**。补齐三处缺口：`solve_momentum` 加 pinch（对闭式二阶）；`code/evolve` 收 `chi_turb_phi` · `v_phi`，扩展门 `code/turbulence` 按 `momentum_flux`（缺省关）把 TGLF 的离子环向应力换成 χ_φ（Prandtl 数中位 0.415）；输出挂 DD 4 的 `momentum_phi/{d,v}`。 |
| 1.1 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（表面电流模型有壁不稳带 `FR-EQ-021(g)` 与共形基解析导数链 `FR-EQ-025(e)` 入内核，另摘掉六处重复的 `#[test]`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **792 项全通过**（去重后既有 782 + 新锚 10）。★纯增量（没开门），接口摘要与 `CASE_CODES` 均未动。 |
| 1.2 | 2026-09-18 | Claude Opus 5 (1M context) | 内核换代后的全册重验（0D 体积带三角度入内核：`zerod::plasma_volume`，`code/zerod` 收可选设定 `delta`；`FR-TR-014`）。★本条的判据与数值**未改口径**；重验的证据是门禁在新内核上跑过：内核侧 **801 项全通过**（新锚 5 条）。★`delta` 缺省 0 时体积逐位是原来的椭圆，接口摘要、`CASE_CODES`、ABI 均未动。 |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:a7a86a75fc27ac155dcfb3ed1c1d752729aef8fea9573a9218444ae2c442b4a0`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/momentum_channel.json`    `sha256:b4ff0d7bb93f00e9c9b48ad87c5c4e49de7c5788dded7443e2e960a37e9ad7d3`    接口、pinch 闭式、门上行为、TGLF Prandtl 数、缺省对拍

**守它的门**：

- `$FYLITE_KERNEL/rust/fylite/src/transport.rs::tests::a_momentum_pinch_lands_on_its_closed_form_at_second_order` —— ★pinch 闭式二阶；None ≡ 零 pinch；向内 pinch 抬轴；长度错拒绝
- `$FYLITE_KERNEL/rust/fylite/src/transport.rs::tests::a_torqued_momentum_channel_lands_on_its_closed_form` —— 无 pinch 的闭式
- `$FYLITE_KERNEL/tests/test_momentum_channel_code.py::test_the_prandtl_closure_is_published_on_the_dd4_names` —— DD 4 名 · Prandtl 缺省
- `$FYLITE_KERNEL/tests/test_momentum_channel_code.py::test_an_inward_pinch_raises_the_axis_rotation` —— 门上 pinch
- `$FYLITE_KERNEL/tests/test_momentum_channel_code.py::test_a_given_turbulent_chi_phi_replaces_the_prandtl_closure` —— 湍流 χ_φ 取代 Prandtl
- `$FYLITE_KERNEL/tests/test_momentum_channel_code.py::test_the_momentum_closure_inputs_are_refused_without_the_channel` —— 拒绝
- `$FYLITE_KERNEL/tests/test_momentum_channel_code.py::test_the_turbulence_door_turns_the_toroidal_stress_into_chi_phi_on_request` —— ★TGLF 动量通量 → χ_φ；无转动拒绝
- `$FYLITE_KERNEL/tests/test_evolve_turbulent_code.py::test_the_turbulent_tier_with_rotation_equals_the_loop_to_the_bit` —— 缺省关时逐位不变

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
