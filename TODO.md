# TODO — 仓级开放任务台账

登记 2026-09-06。本表收**本仓及其上下游**当前未完成的事项——之所以合在一处，是因为它们
多数是同一条链上的：内核声明面 → fyo 本体 → fydata A-Box → fydoc 事实层 → 本仓消费。
分散在五个仓的开放项各自成立，但**谁被谁卡住**只有并排看才看得见。

**归属列是硬约束**：标 `fyo` / `fydata` / `fydoc` 的条目**须按各该仓的治理落地**，不在本仓
改；登记在此只为让本仓知道自己在等什么。标 `kernel` 的是 `fylite_kernel`，标 `fylite` 的
才是本仓自己的活。

---

## A. 内核声明面（`fylite_kernel`）

证据：`fyo` 仓 `FYO-REPORT-05` v0.5（2026-09-06，对内核检出 `08d0c0b` 实测）。三条都**不会
让任何脚本非零退出**——这正是它们至今还在的原因。

| 编号 | 归属 | 事项 | 依据 |
| :--- | :--- | :--- | :--- |
| **K-1** | kernel | 6 条裸路径的叶在 DD 中不存在：`core_transport/…/profiles_1d/grid/rho_tor`（该层只有 `grid_d`/`grid_v`/`grid_flux`）· 4 条 `wall/…/vessel/unit/element/geometry/rectangle/*`（`vessel_2d_element` 只有 `outline`）· `tf/b0`（`tf` 只有 `r0` 与 `b_field_phi_vacuum_r`）。另 1 条秩与 DD 坐标不符：`equilibrium/vacuum_toroidal_field/b0` 声明 `0d`，而 DD 记 `coordinate1: /time` | FYO-REPORT-05 O-1 · O-8 |
| **K-2** | kernel | 16 条裸路径的首段不是任何 IDS（`machine` · `solver_dims` · `pf_active_circuits` · `ic_coil` · `power_supply`）——DD 检出的 84 个 IDS 目录里一个都没有。同批的 `pf_passive/fylite:group/…` 规矩带了前缀，故**很可能是 `fylite:` 前缀漏写**〔推测〕 | FYO-REPORT-05 O-2 |
| **K-3** | kernel | `fyo.rs` 与 A-Box 对同一批量用了两个节名：A-Box 的 `transport/fylite:rho` · `transport/fylite:y` 对应 `fyo.rs` 的 `transport_inputs` 表。A-Box 用到的 118 条文档路径中 116 条两侧一致，只此 2 条不一致 | FYO-REPORT-05 O-9 |
| **K-4** | kernel · fyo | 单位书写法两侧未约定：12 处不同（9 处斜杠 vs 点-幂语法，3 处符号/角度约定 `amu`↔`u`、`1`↔`e`、`rad/s`↔`s^-1`），**量纲不符 0 处**。量表路径起点有两种约定（IDS 根 / 数组元素）且只写在散文里，机器可读的表不携带 | FYO-REPORT-05 O-5 · O-7 |

★ K-1 / K-2 / K-4 的"应改成什么"含〔推测〕成分，**不应据报告直接改写**——报告只出证据。

## B. 本体侧（`fyo`）

| 编号 | 归属 | 事项 | 依据 |
| :--- | :--- | :--- | :--- |
| **O-1** | fyo | 四张内核自有表（`discharge` 48 · `transport_inputs` 10 · `uq` 5 · `pulse` 4，共 67 行、全部规矩带 `fylite:` 前缀）与五条**承重**缺名（23 条程序间交接路径中占 5 条，尤以跨四 IDS 复发的 `fylite:psi_norm`）是对 `fyo:` 命名空间的提案，待裁定接纳与否 | FYO-REPORT-05 O-3 · O-4 · 须 `FYO-ADR-*` |
| **O-2** | fyo | 测量不确定度无本体承载：spo 有 `UncertaintyStatement`（`standard_uncertainty` + `uncertainty_origin`，正为此而设），但 **fyo 无任何槽指向它**。直接后果见 D 组 E-3 | fydata G-10 · 须 `FYO-ADR-*` |
| **O-3** | fyo | `wall` 单套二维描述（**用户裁定 2026-08-31**，非缺陷）的代价已量化：670 个带嵌套 `dd_path` 的类中恰 6 个不能沿属性树走到自己的路径，全在此一 IDS；`maxOccurs="3"` 压成一套。已由 `check_omega` 规则 (e) 设门（`UNREACHABLE_BY_RULING`，第 7 个出现即失败）。**仅在认为该代价过高时重开裁定** | FYO-REPORT-05 O-6 |

## C. A-Box 侧（`fydata`）

| 编号 | 归属 | 事项 | 依据 |
| :--- | :--- | :--- | :--- |
| **D-1** | fydata | G-1 只**半闭**：`check_abox_shape.py` 的 S7 已覆盖 `abox/experiment/`，但 `abox/amns/` 仍不受任何核对 | fydata README G-1 |
| **D-2** | fydata | S7 只核**键名**：一个 T-Box 值域是 `{data, time, unit}` 的槽写成裸标量能过关（如 `tf.b_field_phi_vacuum_r: 3.15`）。该值经核是对的，但那是人验的不是门验的 | fydata G-11 |

## D. EAST 标准算例（`fydoc` `facts/experiment/east/137985/`）

现状：电流平顶已核（2.5 s 起 400.36 kA ± 0.27 %，4000 ms 在其内，E-1 已关闭）；磁测面成立，
**动理学面不成立**。

| 编号 | 归属 | 事项 | 依据 |
| :--- | :--- | :--- | :--- |
| **E-2** | 需数据访问 | 加热 / 驱动 / 杂质 / 输运的本炮数据只在 MDSplus（`202.127.204.12`）。oracle 自述其档次"NOT the delivered EFIT↔NEO kinetic loop, whose POINT / Thomson-n_e channels and bootstrap feedback **exist only on MDSplus**" | 条目 §一.2 |
| **E-3** | fydoc · 待 fyo | Thomson 的不确定度只能标 `fylite:` 前缀（60 处）——被 B 组 O-2 卡住 | 条目 §五 |
| **E-4** | 须语料裁定 | 自洽五面态是**计算产物**不是测量；`dev:result` 现有七个取值没有一个是为它准备的。**这是本条目自己走不过去的那一步** | 条目 §五 |
| **E-5** | fydoc | 电流平顶 ≠ 稳态：PF 通流在平顶期内漂移逾一半（第 1 道 2.5 s 436 → 7.0 s 214 kA·turns）。按"位形不变"读，本炮**任何一片都不是稳态**。可自走一步：逐道算九片的漂移速率，给"哪一段最接近稳态"一个量化答案——不需要新数据也不需要裁定 | 条目 §二 |
| **E-6** | fydoc | `check_cases.py` 报 24 处 / 18 组不满足（其中 12 组 reviewer 联系方式待补）。**既存项**，2026-09-06 经 `git stash` 复核确认改动前完全相同 | fydoc `tools/check_cases.py` |

## E. 本仓（`fylite`）

〔已确立〕本轮（2026-09-06）**未在本仓留下未完成项**——上列各条的落点都在上下游。
本仓在这条链上的位置是**消费方**：E-2 到位则 EAST 标准算例可用于本仓的对拍与回归；
E-4 裁定后计算态才有身份可入库。

---

## 记法

- 条目**只登记事实与依据**，不写结论；带〔推测〕的判断保留标记。
- 归属为他仓者，本表**不得**作为在本仓改动的依据。
- 关闭一条时写明**关闭日期与依据**（如 E-1：2026-09-06，逐片 `magnetics/ip` 实测）。
