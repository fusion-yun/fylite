# TODO — 当前任务列表（短期记忆）

★★**与 `PLAN.md` 的分工是项目设定（2026-09-12 用户裁定）**：`PLAN.md` 是**规划与长期记忆**
（每条任务的由来 · 依据 · 落地读数 · 状态；**行只改状态、不删除**）；**本文件只列还开着的那些**，
一条一行，说**下一步做什么**。一条做完就**改 `PLAN.md` 对应行的状态，并把它从本文件删掉** ——
落地记录留在 `PLAN.md`，不留在这里。

- 每条的**事实与依据在 `PLAN.md` 的同号行**，本文件不重复，两处不一致时以 `PLAN.md` 为准。
- **归属是硬约束**：标 `fyo` / `fydata` / `fydoc` 的条目按各该仓的治理落地，列在这里只为知道本仓在等什么。
- 三组的意思：**可做** = 不等人不等件，现在就能动手；**待裁** = 等用户一句口径；
  **阻塞** = 缺仓外材料，或被他仓条目卡住。

---

## 一、可做（5，不等人不等件）

| 号 | 归属 | 下一步做什么 |
| :--- | :--- | :--- |
| **K-2** | kernel · fydoc | **第一批已落**（2026-09-13，接口修订 4 → 5：电阻率 → `coil/resistance` · IC → `pf_active/coil` + `function` · 供电 → `pf_active/supply`；内核 / 公开仓待提交）。**下一步 = 第二批**：解算盒四边与网格数六条 → 计划设置，随 O-5 B 批做。★另查一处测得的差异：文档的 Guo IC 上 `test_control` 执行器滞后判据不成立（过冲 2.49 ξ₀ 对 TokSys 4.73，激进增益不再更糟），判据现自带 TokSys IC —— 弄清是几何还是判据本身 |
| **F-30** | kernel | 全文已齐（2026-09-13 Karney–Fisch 1979 · Fisch 1987 · Ignat 1994 期刊版均入库）：**LH-②** 电子 Landau 吸收按内核 `lh-raytracing.md` §4.3 已定的设计动手，判据用摘录里的局地点表 |
| **F-31** | kernel | 余下只有**弱相对论极化**一项，Krivenski–Orefice 1983 与 Shkarofsky 1966 期刊版在库：按原文动手 |
| **F-1** | fylite · kernel | H-19 已关（2026-09-13，整圈 Wb · ABI 154）：`code/discharge` 把一维 p′/FF′（及 q 所需的 F）按整圈 Wb 写进声明的槽，再重跑两步算例看第二步是否过 `profiles_1d/q`；余下 10 条判据随之可评 |
| **O-5** | kernel · fylite | **第一批（A+C，19 条）已迁**（2026-09-13，接口修订 2 → 3）。**下一步 = B 类 18 条**：`r_minor`/`r_major` ← `r_inboard`/`r_outboard`（产出要写两列）· `z_magnetic` ← `geometric_axis/z` · `dvolume_dpsi_norm` ← `dvolume_dpsi` · 限制器 ← `wall` 的 limiter outline · `ion_density`/`impurity_density` ← `ion[]/density` + `label` · 线圈与器壁 `a1`/`a2` ← `oblique/alpha`·`beta`（**deg → rad**）· `resistivity_uohm_m` ← `resistivity`（**μΩ·m → Ω·m**）· `tf b0` ← `b_field_tor_vacuum_r ÷ r0` · EC 两角 ← `steering_angle_*` · LH `max_power` ← 工程限值集。★单位换算是**会错**的那一类改动，每处要自带判据 |

〔2026-09-12〕**本组曾空过**（当日 F-16 · F-34 · H-10 会话半 · F-1 门 · H-15 两项做完后），随后用户裁定「fylite 不作为本体前缀」，开出上面这一条 O-5。原记：F-16 · F-34 · H-10（会话文档那一半）· F-1（门）· H-15（1.4 与 1.2 的算法）当日做完并推送，各自的落地读数在 `PLAN.md` 同号行。余下的每一条都在**等一句裁定**或**缺仓外材料** —— 见下两组。★**裁定的杠杆最大的是 `H-19`**（p′/FF′ 的规范）：它一句话解开 F-1 余下的十条判据、`code/discharge` 的一维剖面、以及两步算例那条链。

## 二、待裁（5 行 · 6 个号，等用户一句口径）

| 号 | 归属 | 要裁的是什么 |
| :--- | :--- | :--- |
| **F-2** | fylite | 生成件里手写段活不过下一次 `--write`：三个候选落点（算例声明的 `caveat` · 本册子 RUN 页 · 渲染器认锚点）先定一个 |
| **F-9** | fylite · fydoc | `code/breakdown` 缺供电电流上限：EAST 已由 K-2 带 DD `pf_active/supply`；ITER 等其余装置补在装置描述侧（A-Box 没有），还是算例侧绑 `i_max_aturn` |
| **F-12** | fylite | `B-01` 的参考侧要不要改在 FUSE 1.1.5 上重跑（现有结论建立在已遗弃的 0.7.0 冻结答案上）|
| **G-3** · **G-4** | fylite | **记录由谁产**：把运行时的 `record()` 在页面上镜像一份，还是判定记录只由宿主产、页面只存宿主交来的那一份 —— 同时决定 `run_state` 的 `cancelled` 谁产、断点仓存什么 |
| **H-1** | kernel · fylite | 落点已裁并落地（`fylite_kernel/docs/cases/plans/kinetic-reconstruction.fyo.jsonld`，2026-09-13）；**余一句口径**：外环收敛判据取哪一个——草图 `dq0_rel < 0.01`×6 · 页面自举份额相对变化 < 0.01×4 · 旧 loop `\|Δq₀\| < 0.02`×8（`PLAN.md` H-1） |

## 三、阻塞（15 行 · 16 个号，缺件或等他仓）

| 号 | 归属 | 缺什么 |
| :--- | :--- | :--- |
| **H-15**（2.3） | fylite · fydoc | MSE 的 Er 修正：装置卷宗里**没有 MSE 几何**（`-12` G-4），也没有绑定表，所以既做不出行也量不了 —— 与 H-16 同一个缺口 |
| **H-10** | fylite | **会话文档那一半已完成**（闸 `validate-setting-is-the-document.mjs`，141 个档位）；计划文档落点 2026-09-13 已定（H-1），余下「写回**计划**文档」卡在运行时 / 页面还不读 `has_step` 形的计划（H-2） |
| 台基 **B** · **C** | kernel | EPED 自己的判据原文（B 的外环、C 的真 P-B 都要它）|
| **K-3** | kernel · fydata | 要 A-Box 的 `transport/*` 逐槽读数才判得动 |
| **E-2** | 需数据访问 | 本炮的加热 / 驱动 / 杂质 / 输运只在 MDSplus（`202.127.204.12`）|
| **E-6** | fydoc | 16 组 reviewer 与联系方式（**不可编造**，闸子红是正确结果）|
| **E-7** | 需数据访问 | 那份 g-file 不在任何仓里（两个平衡储能差 4.00 倍，无从判哪份对）|
| **F-8** | 可发信 | 向作者索取 GENE 那批次的 ν* 与逐半径 Miller 参数 —— 阻塞里唯一只差一封信的 |
| **F-14** | fylite | 该炮的线平均道比值（判 c4 落在 3–6.67× 的六片算不算条纹跳），依赖 **E-2** |
| **F-19** | fydoc | 七台自带装置的线圈电流上限（铭牌值）；EAST 现有的是 TokSys 的**供电**端子限值（K-2 进 `pf_active/supply`），不是线圈铭牌 |
| **F-20** | fylite · fydoc | 第二台带实测放电的真机（现在只有 EAST #137985）|
| **F-21** | kernel | 第二个构建环境（跨环境 wasm 字节不可复现，本会话无从复现）|
| **F-28** | kernel | 缺一个**可复算的束宽参照件**（B 类）。全文不再是缺口：Poli 2018（TORBEAM 2.0）与 Prater 2008（EC 基准）期刊版 2026-09-13 入库，接受稿退役 |
| **G-5** | fyo | `../spo` 检出不在（`check_conformance.py` 退 0 才准提交 schema）|
| **G-6** | kernel · fylite | 依赖 **G-5**；`coverage/` 的 `covers` 边要人逐条判断，`availability/` 的 286 格要装置卡片在场 |
