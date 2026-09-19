---
title: "tr-sources-power-closure"
---

# 四族源的功率账：NBI 注入 = 吸收 + 穿透 + 首轨损失、LH 耦合 = 沉积、EC 发射 = 吸收 + 出逃 + 未追、IC 剖面 = 注入——四族都闭合到舍入

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-sources-power-closure.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [源项：加热与电流驱动](../domains/tr/sources.md)　|　记录正本：`records/tr-sources-power-closure.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：四族源的功率账：NBI 注入 = 吸收 + 穿透 + 首轨损失、LH 耦合 = 沉积、EC 发射 = 吸收 + 出逃 + 未追、IC 剖面 = 注入——四族都闭合到舍入
- **参考**：抄录的判据：「P_inj = P_abs + P_shine + P_orbit 逐项闭合为可测不变量」（源族表）·「源沉积积分必须闭合到注入额定值」（NR-TR-001）
- **验的需求**：`FR-TR-004` · `NR-TR-001`
- **跑在内核**：`fylite_kernel@e05a90fd06fe`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-19

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-19 ★IC 那一格的门在内核仓（没有 `code/` 门），本仓 CI 跑不到。★EC 那一格要内核检出（CFEDR 的冻结参考在那里）。
:::

## 问的是什么

**被量的**：NBI 与 LH 在 EAST #137985 t = 4.041 s 的 KEFIT 平衡上（CASE-23），EC 在 CFEDR 20 MA 上（CASE-21）；剖面为给定式

**参考**：抄录的判据：「P_inj = P_abs + P_shine + P_orbit 逐项闭合为可测不变量」（源族表）·「源沉积积分必须闭合到注入额定值」（NR-TR-001）

> ★判据是恒等式，不要参考码：账闭合是每一扇门对自己输出的自证。

**口径与适用域**：

> NBI：两束（同向 65 keV 2 MW 三分量、反向 80 keV 1.5 MW 近边），METIS 阻止本领；LH：4.6 GHz 1.5 MW（反射 0.1 MW）与 2.45 GHz 0.8 MW，eta_cd 1e19，upshift 1.5–2.5；二者都在 EAST #137985 t = 4.041 s KEFIT 平衡上、给定剖面（ne 4e19 (1 − 0.8 x²)，Te 2.5 keV (1 − 0.9 x²) + 50 eV，Zeff 1.5 + x²）。EC：CFEDR 20 MA、TORAY 那一束（O 支，deposit）。IC：内核测试的非平坦 V′ 与 4 / 3 MW。

## 判据与量到多少

:::{figure} ../figures/tr-sources-power-closure-headroom.svg
:alt: tr-sources-power-closure 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| NBI：注入 = 吸收 + 穿透 + 首轨损失；沉积剖面体积分 = 吸收 | 1e-12 | reference_self_reported | 注入 3500000 W = 吸收 3353009.5 + 穿透 87904.6 + 首轨损失 59085.9（相对 0.0e+00）；剖面体积分对吸收 0.0e+00；注入对声明 0.0e+00 | **成立** |
| LH：耦合（发射 − 反射）= 吸收 = 沉积 = ∫p dV，逐天线与总和 | 1e-12 | reference_self_reported | 耦合 2300000 W = 吸收 2300000 = 沉积 2300000；∫p dV 对沉积 0.0e+00；逐天线和 0.0e+00；驱动电流 572241 A | **成立** |
| EC：发射 = 吸收 + 出逃 + 未追；各壳 + 壳外 = 吸收；功率密度 × 壳体积 = 壳功率 | 1e-09 | reference_self_reported | 发射 6000000 W = 吸收 6000000.000000 + 出逃 3.5e-10 + 未追 0（相对 1.2e-14）；壳 + 壳外（0 W）对吸收 4.4e-16；p_e × V 对壳功率 1.1e-16 | **成立** |
| IC：剖面对体积分 = 给定功率（总量与离子份额） | 1e-12 | reference_self_reported | 总量 4.4e-16 · 离子份额 6.7e-16（内核测试打印，`hcd_metis_kernel.json`） | **成立** |

**`NBI：注入 = 吸收 + 穿透 + 首轨损失；沉积剖面体积分 = 吸收`** — ★两束都设成穿透与首轨损失**都带功率**（反向束近边）——某个汇为零时闭合，那个汇就没被验到。

**`EC：发射 = 吸收 + 出逃 + 未追；各壳 + 壳外 = 吸收；功率密度 × 壳体积 = 壳功率`** — ★1e-9 是内核自己这道门的带（沿射线的积分，舍入会累积）。

**`IC：剖面对体积分 = 给定功率（总量与离子份额）`** — ★IC 没有 `code/` 门：判的是内核函数，门是内核仓的 Rust 单测。

**NBI 闭合：0.0e+00；穿透 87905 W、首轨损失 59086 W**

- ★**恰为 0 是构造使然**：门把吸收定义为沉积剖面的壳和（`p_absorbed = shell_sum(p_dep, dV)`），穿透与首轨损失按分量记账——所以这一格守的是**构造**：哪天有人把某一项算在账外，它当场红。它不量数值误差。

**LH 闭合：0.0e+00（两天线、一路带反射）**

- ★同样是构造性的零。★LH 另有一种合法的「不闭合」：单程找不到共振时门报 `deposited = 0`、不沉积——那是可及性判据在起作用，内核门 `test_a_strict_single_pass_finds_no_resonance_and_says_so` 守它；本格的设置选在会沉积的一侧。

## 不可比的部分

- ★★**账闭合不证物理**：把全部功率放在轴上的模型，账一样闭合。沉积位置与驱动效率由本域另外三条判（EC 对 TORAY、ECCD 与 IC 对 METIS）；NBI 与 LH 的沉积与效率**没有外部参照**，是本域的空白。

## 追溯

- 首次入册 2026-09-19　末次修订 2026-09-19　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-19 | Claude Opus 5 | 新立（用户「fylite 建对应 benchmark」，新域 tr-sources）：四族源的功率账——NR-TR-001 第三句与源族表「逐项闭合」。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@e05a90fd06fe`（库 `sha256:19f2501e8437587d71fc7642cbcfc9aa63c7ebf2a5d89e7a4b92dec2f788c223`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/hcd_power_closure.json`    `sha256:a4458d8ba5dec2113fc3fa4421f41ba441f82800db1e70d9327b8b658d4c4709`    NBI · LH · EC 的账（tools/benchmark-hcd.py closure）
- `docs/benchmark/readings/hcd_metis_kernel.json`    `sha256:7adbbe36c3c0526570a9fcbbe7dfe55392765b3379ebcd0e51aa4127b657eff8`    IC 剖面闭合（内核 [register] 行）
- `tools/benchmark-hcd.py`    `sha256:4ace082c4d14898369f529f7e87a1c2e277a1e1dd1bb629cccd3cb5858bf8d28`    读数生成器（closure · toray · kernel 三个子命令）
- `FYDOC-CASE-23-east-137985-efit-east/corpus/kefit/kefit_raw_east137985.tar.gz`    `sha256:001d33a06fdc39da3cf15a0240484f182cf0c85e832bf7802894e8c63aca0258`    平衡（t4041_mag 的 g 文件），指针 + sha256

**守它的门**：

- `python/tests/test_benchmark_hcd.py::test_hcd_nbi_account_closes_with_all_three_sinks_carrying_power` —— 第一格
- `python/tests/test_benchmark_hcd.py::test_hcd_lh_account_closes` —— 第二格
- `python/tests/test_benchmark_hcd.py::test_hcd_ec_account_closes` —— 第三格
- `python/tests/test_benchmark_hcd.py::test_hcd_the_accounts_reproduce_their_reading`
- `$FYLITE_KERNEL/rust/fylite/src/heating.rs::tests::the_icrh_profile_is_a_gaussian_on_the_layer_that_carries_its_power` —— 第四格（内核仓）

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
