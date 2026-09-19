---
title: "tr-sources-nbi-nubeam"
---

# NBI 对 NUBEAM（DIII-D 测试例，7 束 8.5 MW）：束离子的出生率差 +2.4 %、出生形心差 +0.037（psi_N）；NUBEAM 的答案是 20 ms 的暂态，加热分配与电流只记读数

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-sources-nbi-nubeam.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [源项：加热与电流驱动](../domains/tr/sources.md)　|　记录正本：`records/tr-sources-nbi-nubeam.jsonld`*

## 摘要

- **类**：对拍　**判决**：**成立**
- **量的是**：NBI 对 NUBEAM（DIII-D 测试例，7 束 8.5 MW）：束离子的出生率差 +2.4 %、出生形心差 +0.037（psi_N）；NUBEAM 的答案是 20 ms 的暂态，加热分配与电流只记读数
- **参考**：NUBEAM
- **验的需求**：`FR-TR-004`
- **跑在内核**：`fylite_kernel@b27d7145ab3e`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-19

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-19 ★参考是暂态（2 × 10 ms）：出生以后的加热分配、储能与电流只能记读数，要一个跑到稳态的 NUBEAM 答案才能判；本机无 NUBEAM 可执行件。
:::

## 问的是什么

**被量的**：NUBEAM 自己的等离子体态原样喂门：psi(R,Z)、q、g、边界、限制器、ne / Te / Zeff；束几何由其源参数换算（见 validity_domain）

**参考**：NUBEAM（TRANSP 22.01 源码树 nubeam_comp_exec 的 DIII-D 测试（D3D 118419，t = 3.995 s）：d3d_input_state.cdf → d3d_output_state.cdf，运行日志 d3d_test.msgs）

> ★**净室**：只读 NUBEAM 的数据文件（等离子体态、日志），从未读其源码。★★**它的答案是暂态**：日志为 INIT 后 2 × 10 ms，从零快离子起步，W_fast 仍以 6.2 MW 上升——束离子的**出生**（瞬时量）它判得了，出生以后的事（加热分配、电流、储能）它只答到 20 ms。

**口径与适用域**：

> DIII-D 118419 t = 3.995 s，7 束全开（81 / 74.8 / 75 / 75 / 75.1 / 75.2 / 60 keV，共 8.54 MW，氘）。平衡：PsiRZ（109²）、psi_axis 0 / psi_bdy = psipol[-1]、Ip = kccw_Jphi × curt、边界取 rho = 1 面、限制器 rlim / zlim。剖面：ns / Ts / Zeff 于 40 个区中心、按 psipol(rho) 映到 psi_N。束几何：切向半径 |sRtcen|、高度 Zbsc、同向；切点处的 rms 宽度 = 源半宽 / √3 ⊕ Lbsctan × tan(发散角)/√2（竖直按 b_Vfocal_length 聚焦），铺在 5 个等权节点上；孔径截断忽略。阻止本领 Janev、无杂质（基线）。

## 判据与量到多少

:::{figure} ../figures/tr-sources-nbi-nubeam-headroom.svg
:alt: tr-sources-nbi-nubeam 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 束离子出生率对 NUBEAM 的下界（dN/dt + 热化率） | 0.05 | measured_band | 本码 9.876e+20 /s、NUBEAM ≥ 9.645e+20 /s（dN/dt + 热化）；注入 8.54 MW（7 束，81 / 75 / 75 / 75 / 75 / 75 / 60 keV） | **成立** |
| 出生分布的功率形心（psi_N） | 0.07 | measured_band | 形心 psi_N：本码 0.349、NUBEAM 0.312（差 +0.037）；半功率半径 0.270 对 0.199（读数） | **成立** |
| 等离子体态读得对：门的壳体积和对 NUBEAM 的体积 | 0.005 | measured_band | 门的壳体积和 19.550 m³、NUBEAM 19.564 m³ | **成立** |
| 出生以后（读数，不判）：20 ms 的加热、储能与电流 | — | — | 损失份额：本码 0.0010（穿透 + 首轨）、NUBEAM 0.0313（含电荷交换与轨道，按 1 −（加热 + dW/dt）/ P 估）。以本码自己的沉积、E_c、tau_s 按 NUBEAM 的源历史重建 20 ms：W_fast 110 kJ 对 101（+9 %）、P_e 0.60 MW 对 0.65（-7 %）、P_i + P_th 0.69 对 1.40（-51 %）。本码定常：P_e 份额 0.30、I_NBI 212 kA、W_fast 331 kJ；NUBEAM 20 ms：P_e 份额 0.32、I_NBI 95.6 kA（未饱和） | **未判（读数）** |

**`束离子出生率对 NUBEAM 的下界（dN/dt + 热化率）`** — ★出生是瞬时的，不等慢化——这是暂态参考判得了的量。NUBEAM 另有电荷交换再电离的出生，本码不建模。

**`出生分布的功率形心（psi_N）`** — ★NUBEAM 的 `sbedep` 只含电离出生（占 64 %），电荷交换出生在更外面——所以两者之差有一个已知的方向。

**`等离子体态读得对：门的壳体积和对 NUBEAM 的体积`** — 防假通过：平衡换错了，下面两格会碰巧对上也说明不了什么。

**出生率 +2.4 %**

- ★NUBEAM 的 frac_full / frac_half 按**中性原子流份额**读（换成功率份额约 0.73 / 0.19 / 0.08）：粒子守恒支持这一读法（按功率份额读则注入原子率 1.21e21，高于 NUBEAM 的出生下界 25 %）。
- ★日志推得第一步的源权重只有 0.48（原因未明），读数把它照实用在暂态重建里。

**出生形心 0.349 对 0.312**

- ★★**对杂质敏感，照记**：同一出生若按门的单一标量碳密度（体平均 1.52e+18 m⁻³）加 Janev 杂质阻止，形心外移到 0.499——常数杂质密度高估了低密度边缘的阻止。基线不加杂质；METIS 阻止本领给 0.333。

**出生以后（读数，不判）：20 ms 的加热、储能与电流**

- ★★离子道差一倍、不判：NUBEAM 有有限轨道宽度、电荷交换与晕、反常快离子扩散（0.3 m²/s）、投掷角与能量散射，本码都没有；而 20 ms 的暂态里这些与「慢化还没到头」混在一起，分不开。要判定常的分配与电流，得有一个跑到稳态（≥ 200 ms）的 NUBEAM 答案——本机没有 NUBEAM 可执行件，造不出来。
- ★暂态重建是**读数用的**：它是本码的成分在 NUBEAM 的时间表上的 Stix 慢化积分（无输运、无投掷角散射），不是本码的一个模型。

## 不可比的部分

- ★★**对拍不是验证**：本码与 NUBEAM 在出生上一致，说明束在同一处以同一速率电离，不说明其后的物理对。
- ★参考侧不在本处重跑：NUBEAM 的两个态文件与日志即其全部答案。

## 追溯

- 首次入册 2026-09-19　末次修订 2026-09-19　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-19 | Claude Opus 5 | 新立（用户「建 NBI and LH，icrf benchmark」）：NBI 对 NUBEAM 的出生——此前 NBI 的沉积与驱动没有任何外部参照。 |

## 复算

**这次跑在**：

- 内核 `fylite_kernel@b27d7145ab3e`（库 `sha256:2851c58ae6777d4783fc0071cfc21526509617470a174159a38a47de0074f074`）　—— 与 `meta/kernel.json` 的基准内核提交一致——本记录记在当前内核上。

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/nbi_nubeam_d3d.json`    `sha256:b2faa8a5153364e14446de35a184a1998adf3f337febf423f9bdc65080b1ce90`    比较量（tools/benchmark-hcd.py nbi）
- `tools/benchmark-hcd.py`    `sha256:9fbebb10c8e0d65fe11cb0e298b0ab1631996865a0d2979ddd1e39cf62d784eb`    读数生成器（closure · toray · kernel 三个子命令）
- `third_party/transp_2201/codesys/source/nubeam_comp_exec/d3d_input_state.cdf`    `sha256:b17bfb5b58c950704ea98c1994ecdc60d73eac6cff052c91874b64a00b7f0a94`    NUBEAM 的输入态，指针 + sha256
- `third_party/transp_2201/codesys/source/nubeam_comp_exec/d3d_output_state.cdf`    `sha256:803da0c9acc6859794e00366c8f4c6f7c69f79580dad199808096d09b125bf8d`    NUBEAM 的输出态
- `third_party/transp_2201/codesys/source/nubeam_comp_exec/d3d_test.msgs`    `sha256:13bd17230598c5cea08c682f12d19cfccbaa2da1b0a5e77e38b892e2d4b00073`    运行日志（步长、步数、各步快离子数与平均能）

**守它的门**：

- `python/tests/test_benchmark_hcd.py::test_nbi_the_beam_ions_are_born_where_and_as_fast_as_nubeam_births_them` —— 第一、二格
- `python/tests/test_benchmark_hcd.py::test_nbi_the_plasma_state_is_read_as_nubeam_read_it` —— 第三格
- `python/tests/test_benchmark_hcd.py::test_nbi_reproduces_its_reading`

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
