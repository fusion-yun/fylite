---
title: "mhd-vertical-freegsnke-east137985"
---

# 竖直不稳定性对 FreeGSNKE：**对拍很干净，而域页点名的三个锚里两个够不着**

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/mhd-vertical-freegsnke-east137985.jsonld`，本页只是它的可读面。 -->

*MHD 稳定性 (MHD Stability) · [竖直稳定性、线圈受力与电磁线性模型](../domains/mhd/vertical.md)　|　记录正本：`records/mhd-vertical-freegsnke-east137985.jsonld`*

## 摘要

- **类**：确认　**判决**：**未判（读数）**
- **量的是**：竖直不稳定性对 FreeGSNKE：**对拍很干净，而域页点名的三个锚里两个够不着**
- **参考**：FreeGSNKE（freegs4e 0.13.1 / numpy 1.26.4） · 抄录的判据本身（解析锚）
- **验的需求**：`FR-EQ-016`
- **跑在内核**：`sha256:340bef300ef0fad4…`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-17

## 问的是什么

**被量的**：导体壁当电路解、刚体竖直位移的色散关系

**参考**：FreeGSNKE（freegs4e 0.13.1 / numpy 1.26.4）

> ★参照是一次**已录制的运行**（`corpus/freegsnke/freegsnke_vstab_east137985.tar.gz`，在 `FYDOC-CASE-23` 里），不是这里重跑的——它的线性化要 10–20 分钟。归档带着它自己的脚本、JSON 与数组，逐字节可校。★两边用**同一张 EAST 装置卡**：90 个被动元件（内壳 40 / 外壳 40 / 被动板 10）、12 路 PF 及其元件映射、KEFIT 的线圈电流。

**参考**：抄录的判据本身（解析锚）

> ★判据点名了**不需要任何外部码**的四条：耦合梯度对互感中心差分、刚度恒等式 $k = 2\pi I_p n B_z$、单回路闭式解 $\gamma=(1/\tau_w)k/(k_{\rm ideal}-k)$、$\gamma \propto R_w$。★★本域的行文把顺序说死了：「**先把锚钉牢，再去和别人对拍**」——本条照这个顺序查，结果是**对拍先成了，锚反而缺**。

**口径与适用域**：

> EAST #137985 t = 4.041 s，刚体位移、被动回路（`circuit: passive`、`ic: 0`、`coarsen: 1`、`nu = nv = 8`；壁的电路用 `nu = nv = 16`）。★**不判可形变分支**——fylite 这一侧没有它，参照那一侧有，差值作读数记着。★恒等式三格的「未评」只针对**这扇门当前的输入输出面**，不是说这些量算错了。

## 判据与量到多少

:::{figure} ../figures/mhd-vertical-freegsnke-east137985-headroom.svg
:alt: mhd-vertical-freegsnke-east137985 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 对 FreeGSNKE：壁的 L/R 时间、$\gamma$、$k$、$k_{\rm ideal}$ | 0.01 | analyst_declared | **壁当电路**（最长 L/R）：内壳 12.7508 / 12.7513 ms（−3.9e-05）· 外壳 13.0954 / 13.0988 ms（−2.6e-04）· 被动板 400.57 / 400.27 ms（+7.6e-04）· 全体 413.50 / 413.21 ms（+6.9e-04）；元件电阻中位相对差 3.3e-08、绝对最大 1.1e-02。★**竖直不稳**（FreeGSNKE 自己收敛的反解均衡上）：$\gamma$ +1.15e-03 · $k$ +2.99e-03 · $k_{\rm ideal}$ +7.5e-04 · 裕度差 −4.9e-03 | **成立** |
| $\gamma \propto R_w$（壁电阻线性缩放） | — | machine_precision | 被动电阻整体缩放 0.5 / 1 / 2 / 4 倍，$\gamma$ = 2.0856 / 4.1713 / 8.3426 / 16.6851 s⁻¹；$\gamma/\eta$ 四档的散布 **4.44e-16**（一个 ulp 量级） | **成立** |
| 壁越远 $\gamma$ 越大（结构性单调） | — | reference_self_reported | 被动元件绕磁轴径向外移 1.0 / 1.25 / 1.5 / 2.0 / 4.0 倍：$\gamma$ = 4.171 → 23.69 → **+∞（regime 2）** → +∞ → **按名拒绝**（「the passive inductance matrix is not positive definite」）。有限支上严格单调 | **成立** |
| 三档判读，且理想不稳 fail-loud | — | reference_self_reported | `regime_code` 定义为 0 稳 / 1 阻性壁 / 2 理想不稳。本次扫到 **1 与 2**：标称位形 regime 1（note「regime: resistive-wall」），壁外移 1.5 倍起 regime 2、$\gamma = +\infty$、note「regime: ideal-unstable」——**不是一个看着正常的大数**。★**第 0 档没走到**：把壁做成理想导体（`eta_scale = 0`）后 $\gamma$ 降到 8.7e-13，但判读仍是 1（阻性壁） | **成立** |
| 产物落 `mhd_linear` DD 形 | — | reference_self_reported | `python/fylite/_manifest/vstab.jsonld` 声明 `port_id: mhd_linear` / `data_type: fyo:mhd_linear`；`rust/fylite_runtime/ids/mhd_linear.tsv` 在 | **成立** |
| 刚度恒等式 $k = 2\pi I_p n B_z$ | 0.0001 | reference_self_reported | ★**未评**。恒等式里的 $B_z$ 与衰减指数 $n$ 指的是**外场**（PF 线圈产生的平衡竖直场），而 `code/vstab` 两样都不报。★★用总 $\psi$ 顶替是**错的，并且错得很响**：磁轴上 $\nabla\psi = 0$ 是定义，实测 $B_z(\text{轴}) = 4.32$ mT、$n = -368.6$，推出的 $k = -3.93\mathrm{e}6$ 对门给的 $2.12\mathrm{e}5$ **差 19.6 倍且反号** | **未评估** |
| 单回路闭式解 $\gamma = (1/\tau_w)\,k/(k_{\rm ideal}-k)$ | — | reference_self_reported | ★**未评**。`code/vstab` 的 `passive` 设置收的是**组名**（`inner_shell` / `outer_shell` / `passive_plates`），最小可解位形是 40 个元件的内壳；判据要的「单回路」这扇门表达不出来 | **未评估** |
| 耦合梯度 vs 互感的中心差分 | 1e-06 | reference_self_reported | ★**未评**。门吐出 `g`（等离子体—回路耦合梯度，90 维）、`m`（回路—回路互感 90×90）、`r`（电阻）与 814 根丝的位置电流，但**没有**等离子体—回路的互感本身——中心差分无从做起 | **未评估** |

**`对 FreeGSNKE：壁的 L/R 时间、$\gamma$、$k$、$k_{\rm ideal}$`** — ★1 % 是**本册自立**的口径，判据没给数：两边是两套独立的离散（fylite 的矩形丝 vs FreeGSNKE 的细多边形），差到百分之几都不奇怪。★实测全部好一个量级以上，所以这条口径松不松并不影响结论。

**★★对 FreeGSNKE：壁与增长率都在 1e-3 以内**

- ★★**两条只有并排才看得见的读数**：〔一〕FreeGSNKE 的**可形变** $\gamma$ 是刚体的 **2.165 倍**——那是刚体模型里没有的物理，不是谁算错了；本条对的是刚体对刚体。〔二〕fylite 在 KEFIT 的均衡上比在 FreeGSNKE 自己的均衡上低 **2.2 %**，而两个均衡的边界中位差 5.4 mm、最大 66.6 mm——**这个量级的均衡差就值 2 %，引用增长率时必须一并说明它站在哪个均衡上**。
- ★电阻的绝对最大相对差 1.1e-02 远大于中位 3.3e-08：差集中在少数元件上，看着像离散化边角而非系统偏置，**没有去查是哪几个**。

**★★$\gamma \propto R_w$：到机器精度**

- ★这条锚**不需要任何外部码**，却能抓住阻性壁支上大多数接线错误：把 $R$ 接错位置、或把 $\tau_w$ 从错的矩阵里取，比例立刻不成立。

**★壁越远长得越快，到理想阈值为止**

- ★★**先记一处我自己的判法错**：起初拿严格单调去套整条扫描，判出「不单调」——因为越过理想阈值之后 $\gamma$ 是 $+\infty$，而 `inf > inf` 为假。**那测出来的是判法的毛病，不是实现的**；改成只在有限支上判。留在这里是因为下一个写同类扫描的人会照样踩。
- ★最远那一档（4 倍）不是给出一个坏数，是**按名拒绝**——被动电感矩阵失去正定性。壁被移到那个位置之后几何本身已经不自洽，拒绝比算下去对。

**★三档里走到了两档；理想不稳确实喊得响**

- ★★**第 0 档没被证伪过，所以本条只说它「定义了」，不说它「对」**。$R = 0$ 时阻性壁模的 $\gamma$ 本就为零而非被镇定，报 1 是讲得通的；但「什么输入才让它报 0」这件事**没有测过**，而一个永远报不出 0 的实现会在本条每一格都过关。★补法很便宜：找一个真被镇定的位形（或直接查那一分支的判别式），没做。
- ★「fail-loud」这一格判成立是因为 $+\infty$ 与 `regime_code = 2` 与 note 三者同时出现；单看 $\gamma$ 是 $+\infty$ 也算响，但**三者一起**才让下游没法把它当成一个数用下去。

**★`mhd_linear` 载体在**

- ★这一格只查了**载体在不在**，没查往里写的字段对不对——那要一份 DD 侧的对照，本次没做。

**★★刚度恒等式 $k = 2\pi I_p n B_z$：**这扇门够不着****

- ★★**把这个错数留在册里是有意的**：它不是一次测量，是这条陷阱的证据。下一个想验这条恒等式的人，第一反应几乎一定是「从 g-file 的 $\psi$ 求 $B_z$」——而那条路在磁轴上必然退化。
- ★要真验它，需要门多报两样：外场的 $B_z$ 与其衰减指数 $n$（或者报出线圈场在磁轴处的取值，让调用方自己求 $n$）。**这是内核侧一次很小的增补**，不是新物理。

**★单回路闭式解：**配不出单回路****

- ★**不拿多元件的结果去套单回路闭式解**：那个式子里的 $\tau_w$ 是单一回路的 $L/R$，在 40 元件的壁上没有唯一对应物（取最长模是一种选择，而「一种选择」不是恒等式）。★要验它，门得允许**按元件**挑被动集，或者收一个合成的单元件装置卡。

**★耦合梯度对中心差分：**门吐了梯度，没吐互感****

- ★在 python 侧自己用椭圆积分重算那个互感是可以的，但那样比的是「内核的梯度」对「我写的互感」，**换了一个被测对象**。这一条更该落成内核仓的一道 Rust 单测：那里 $M$ 与 $\dd M/\dd z$ 都在手上。
- ★同一处代价与 `tr-pedestal-sawtooth-kadomtsev` 等条一样——门若落在内核仓，本仓 CI 守不住它。

## 不可比的部分

- ★★**判决是 inconclusive，而不是 pass**：八格里五格成立、三格未评，而未评的那三格恰是本域行文点名「先钉牢」的解析锚。对拍再干净也替不掉它们——**外部一致只说明两套实现同意，不说明它们同意的是对的**。
- ★★**同时它也不是 fail**：没有任何一格被证伪，对拍在 1e-3 量级，$\gamma \propto R_w$ 到机器精度。本条要说的是「差三个锚」，不是「算得不对」。
- ★三格未评各自的补法都已写在 finding 里，且都不是新物理：门多报外场 $B_z$ 与 $n$（第②格）· 门允许按元件挑被动集（第③格）· 内核仓补一道 Rust 单测（第①格）。
- ★`FR-EQ-014`（线圈受力与导体表面场）与 `FR-EQ-015`（电磁线性模型导出）同域仍空。本条不替它们声明。

## 追溯

- 首次入册 2026-09-17　末次修订 2026-09-17　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-17 | Claude Opus 5 (1M context) | 首次入册：`FR-EQ-016` 从空缺转为记录，判 **inconclusive**。对 FreeGSNKE 的壁与竖直不稳对拍干净（L/R 4e-05…8e-04，$\gamma$ 1.15e-03，$k$ 2.99e-03）；$\gamma \propto R_w$ 到 4.44e-16；壁外移单调并在 1.5 倍处转理想不稳、4 倍处按名拒绝；三档定义齐而第 0 档未走到。★**三个解析锚未评**（耦合梯度中心差分 · 刚度恒等式 · 单回路闭式解），各自差什么写在 finding 里。★另记一处**我自己的判法错**（拿严格单调去套含 $+\infty$ 的扫描）与一处**陷阱的实测**（从总 $\psi$ 求 $B_z$ 在磁轴上必然退化，$k$ 因此差 19.6 倍且反号） |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:340bef300ef0fad494ef3c248b75a08dc464c6a3d145f8f0df2b8cf2208736c8`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/wall_vstab_east137985.json`    `sha256:4f106103acdd250b9ef317073c447be7eb90f923adadac93f9eaad9c6ed46cc0`    对 FreeGSNKE：壁的 L/R 与互感、竖直不稳的 gamma/k/k_ideal/margin
- `docs/benchmark/readings/vstab_identities_east137985.json`    `sha256:04f09ee616261a144330bde2f0af47a830f2ffb6745c6d9717fc29d18f26f0a5`    内部核查：电阻缩放扫描、壁外移扫描、三档判读、载体、以及衰减指数那条陷阱的实测

**守它的门**：

- `python/tests/test_benchmark_mhd_vertical.py::test_the_growth_rate_is_proportional_to_the_wall_resistance` —— 第④格的门
- `python/tests/test_benchmark_mhd_vertical.py::test_a_wall_further_out_grows_faster_until_the_ideal_limit` —— 第⑥格的门
- `python/tests/test_benchmark_mhd_vertical.py::test_the_ideal_tier_is_loud_and_not_a_plausible_number` —— 第⑤格的 fail-loud 半边
- `python/tests/test_benchmark_mhd_vertical.py::test_the_linear_model_has_a_carrier_to_land_in` —— 第⑦格的门
- `python/tests/test_benchmark_mhd_vertical.py::test_the_wall_and_the_growth_rate_agree_with_freegsnke` —— 第⑧格的门（对 FreeGSNKE）
- `python/tests/test_benchmark_mhd_vertical.py::test_the_recorded_identity_readings_are_what_this_checkout_computes` —— ★守的是记录里的数不会悄悄过期
- `tools/benchmark-wall-vstab.py::identities` —— 读数的产出处（新写的子命令）

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
