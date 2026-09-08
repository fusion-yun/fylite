# TODO — 仓级开放任务台账

登记 2026-09-06，**E 组 2026-09-08 重写；同日晚二次清理**（收官批：`B-08` · `B-10` · `C-11` · `C-10` 落地，`G-14` 修掉）。本表收**本仓及其上下游**当前未完成的事项——之所以合在一处，是因为它们
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
| ~~**D-1**~~ | fydata | **已关闭 2026-09-08**：`check_abox_shape.py` 新增 **S8** 收 `abox/amns/`（记法同装置树，`_ids` 认根类）。开核当次报 **1 处**——`charge_state` 挂在 `amns_data` 顶层，而 DD 放在 `process[]/charge_state[]` 之下；**未改数**，转为 fydata G-12（重铸属转换器的活） | fydata README G-1 |
| ~~**D-3**~~ | fydata | **已关闭 2026-09-08**（`fydata 0e114a1`）：**S10 的 147 处「该是数组的槽写成单个结构」**——`coil.element` 110（七份 pf_active）· `flux_loop.position` 35 · `time_slice.profiles_2d` 1 · `coil.conductor.cross_section` 1。T-Box 记 multivalued、DD 记 `1...N`，而 A-Box 写的是一个结构，于是**十三台装置一台也跑不动 `code/breakdown`**（内核按 DD 读 `pf_active/coil/0/element/0`）。★逐行改不走 load/dump（件是手工维护、头注释里有「盲目重跑会把 deg→rad 打回去」的警告）：每处只改块的第一个子键那一行，其后逐字节不变；判据是改前改后 `yaml.safe_load` **语义相同**。S10 147 → 0 | fydata `check_abox_shape.py` S10 · 本仓 `C-10` |
| ~~**D-2**~~ | fydata | **已关闭 2026-09-08**：新增 **S9**。★按字面实现的第一版**是错的**——「值域是类⇒必须写结构」报 173 处，而标量简写是通行记法。改判两条：简写的**类型**要配得上值域类；**同一棵树内**不得两种写法混用（跨树不算）。各抓到一件真事：EAST `ec_launchers` 的 `frequency: 140E9` 被 PyYAML 读成**字符串**（YAML 1.1 浮点正则要小数点+带号指数），四束皆是，已改 `1.4e+11`；`Wall2dLimiter.type` 装置树内混用整数与字符串，未改数（口径裁定，fydata G-13） | fydata G-11 |

## D. EAST 标准算例（`fydoc` `facts/experiment/east/137985/`）

现状：电流平顶已核（2.5 s 起 400.36 kA ± 0.27 %，4000 ms 在其内，E-1 已关闭）；磁测面成立，
**动理学面不成立**。

| 编号 | 归属 | 事项 | 依据 |
| :--- | :--- | :--- | :--- |
| **E-2** | 需数据访问 | 加热 / 驱动 / 杂质 / 输运的本炮数据只在 MDSplus（`202.127.204.12`）。oracle 自述其档次"NOT the delivered EFIT↔NEO kinetic loop, whose POINT / Thomson-n_e channels and bootstrap feedback **exist only on MDSplus**" | 条目 §一.2 |
| **E-3** | fydoc · 待 fyo | Thomson 的不确定度只能标 `fylite:` 前缀（60 处）——被 B 组 O-2 卡住 | 条目 §五 |
| **E-4** | 须语料裁定 | 自洽五面态是**计算产物**不是测量；`dev:result` 现有七个取值没有一个是为它准备的。**这是本条目自己走不过去的那一步** | 条目 §五 |
| ~~**E-5**~~ | fydoc | **已关闭 2026-09-08**（那一步已走）：逐片 12 道 PF 通流实测（fydoc `facts/tools/pf_drift.py`，纯标准库、只读）——最静段 **4.0–5.0 s**（总 3.17 %/s · 方向 1.17 deg/s），**4000 ms 落在其起点**，故重建选片不必改；全平顶方向仅转 7.91°，而逐道看 c1 降 50.9 %——两种读法量的不是同一件事，条目已并记。**「任一片都不是严格稳态」不变** | 条目 §二 |
| **E-6** | fydoc | `check_cases.py` 报 **26 处 / 18 组**不满足（其中 **13 组** reviewer 联系方式待补）。**既存项**，2026-09-06 经 `git stash` 复核确认改动前完全相同。★2026-09-08 由 24/12 变 26/13：`FYDOC-CASE-04`（FUSE）当日跑出答案，按该组**自己写的**规矩 `review.status` 由 `not-required` 改判 `pending`——不是新缺陷，是一条规矩对自己生效 | fydoc `tools/check_cases.py` |

## E. 本仓（`fylite`）与内核（`fylite_kernel`）

★2026-09-08 更新。**此前这一节写着「本轮未在本仓留下未完成项」**——那句话在 09-06 成立，
当日的验证定序册第三轮与第三方源码盘点之后不再成立。下表是本仓／内核自己的活，
**不依赖上下游任何一条**。

| 编号 | 归属 | 事项 | 依据 |
| :--- | :--- | :--- | :--- |
| **F-1** | fylite | **`discharge-iter` 的门**。物理校验册 88 条现只评了 24，做了它可评条数才会动。要两件事一起做：`run_json` 走树门，**且**算例把装置文档绑成输入 | RUN-2026-09-08 §四 · §六.3 |
| **F-2** | fylite | **生成件里的手写段没有活路**。手写归因活不过下一次 `--write`，**而且不会有任何东西报错**——这是它比「写错了」更坏的地方。三个候选落点（判据册算例声明的 `caveat` · 本册子的 RUN 页 · 渲染器认一个锚点）**要先定**，才好写第二段 | RUN-2026-09-08 F-24 |
| **F-3** | kernel | **F-19 退役丢掉的 26 条判据要不要在门那一侧重写**：层析 11 · UKAEA 网络 8 · 装配层编排 4 · 自标定方法学 3。★这是一次**新排期**，不是那次退役的余项；不排也行，但别让后来的人以为从来没有过 | `tests/PHYSICS-MIGRATION.md` 退役表 |
| ~~**F-4**~~ | fylite | **已关闭 2026-09-08**：专用 `Pkg.develop` 环境跑通 `FUSE.test_case(Val(:ITER_time), dd)`（FUSE 1.1.5 / IMAS 7.3.0，437.7 s，**61 个时刻**，`evolve_error: null`），答案收进 fydoc `FYDOC-CASE-04-fuse/corpus/1.1.5/`。`B-08` 随之判 pass。★捕获脚本加 `FUSE_TEST_CASE` 门——与 0.7.0 那份**出自同一个读取器**；★走不通的一条路已记在语料 README：把写盘的 `dd` 读回来归约，`json2imas` 在留空的二维字段上抛 `MethodError` | plan.jsonld `B-08` · 内核 `180dd93` |
| ~~**F-5**~~ | fylite | **已关闭 2026-09-08**：CHEASE 本机构建成功并自行重跑 `ntcase=2`（不读冻结产物），`B-10` 判 pass（GS 残差 5.257e-02，带 8e-2）。★该条的主要产出不是那个数，是一个读法——**加密盒子不是收敛检验**（101×65 → 401×257 残差不降反升；改内部网格才降 2.1 倍） | plan.jsonld `B-10` |
| ~~**F-6**~~ | fylite | **已关闭 2026-09-08**：映射逐项落实，`C-11` 判 pass——离子热通量系统偏低 **−42…−53 %**、电子热通量最差 **+131 % 恰在阈值**、八点全在训练箱内（门里第一条就判这个）。★留痕的那一项：算例是「红/蓝氢」示踪设置（两支同位素氢 + Be + C）而网络只模一个有效主离子，**Be 那一支在低梯度端比氢两支合计还大**——所以离子那一栏的差里含着**成分折叠**，不全是代理误差 | plan.jsonld `C-11` |
| ~~**F-7**~~ | — | ~~`B-09`：要不要自跑 DINA 当参考~~ **作废（登记当日）**：DINA 的参考答案就在 `~/workspace/data/ITER Scenario/`，不需要自跑，那次许可/清净室裁定也就不必做了。★留着这一行是因为它示范了一件事——**这条待办从提出到作废不到一小时，而它提出的依据是台账里一句写着「未取回」的旧备注**。备注记的是写它那天的状态 | SURVEY-2026-09-08 §一 · §四 |
| **F-8** | 可发信 | **`C-08` 向作者索取 GENE 那批次的 ν* 与逐半径 Miller 参数**（或那次 JINTRAC 模拟的对应量）。这是六条阻塞里**唯一一条只差一封信**的 | plan.jsonld `C-08` |
| **F-9** | fylite · fydoc | **`code/breakdown` 仍跑不出结果，但挡路的换了一件事**。G-14 修掉后 ITER 与 EAST 过了几何这一关，卡在下一句：「the device gives no supply current limit (`power_supply/current_limit_kA`) and the plan binds no `i_max_aturn`」。两条路：装置描述补上供电限值（是**数据缺口**，ITER 的 A-Box 里没有；EAST 的手工牌里有 `current_limit_kA: 14.5`），或算例侧绑一个 `i_max_aturn`。**先定这一条走哪边**，再谈把 breakdown 接进定序册 | 2026-09-08 实测（`fy run design breakdown --device iter --facts <fydoc>/facts`）|
| **F-10** | fydoc | **生成的装置清单指向不存在的路径**。`abox2jsonld.py` 把每份件搬位（剥 `tree_root`）并改名（`.yaml`→`.jsonld`），却把清单里的 `providers[].path` **原样抄过来**——于是 `best` / `cfetr` / `cfedr` 的清单指着 `fyo/latest/providers/pf_active/base.yaml`，书里没有这个文件，解析不到线圈；`west` 更是**一个 provider 都没声明**。四台因此在 `code/breakdown` 上报「the document carries no `pf_active/coil`」。★ITER 之所以能过，是因为**它那份清单是为书手写的**（`path: providers/pf_active/base.jsonld`）——不是生成器做对了 | 2026-09-08 实测（四台逐台跑）|
| ~~**F-11**~~ | fydoc | **已关闭 2026-09-08**（fydoc `9eb7657`）：三份 EAST g-file 收进算例书 `FYDOC-CASE-19-east-efit`（`corpus/` 与 `case.yaml` 同址、`checksums` 逐件在册、`payload: in`），本仓的门与登记册指针随之改指。★★查证时发现比「指针脆」更要紧的一层：2026-09-04 的裁定删 `corpus/experiment/` 时写明这批件**不可重取**、「只剩 git 历史与未跟踪的 `todelete/`」，而同日一次**讲文档规则**的提交把 `todelete/` 顺带跟踪了进来、提交信息一字未提——于是一批不可重取的件被一个名叫「待删」的目录持有着。★迁入**不等于放行**：`release: internal` 不变，review 待具名 | 登记册 `V-15` 的 `has_input` |
| **F-13** | fydoc | **`todelete/` 余下的部分未判**：`east/mdsip-137985.json`（一次 mdsip 会话的逐帧录音，fylite 的浏览器门经 `FYLITE_MDS_FIXTURE` 读它）是**测量**不是重建产物，按分工归实验层 / `fydata` 的 A-Box；另有 `todelete/device/{east,iter}` 与 `todelete/facts/`。★F-11 只搬了它该搬的那一份，**没有顺手替其余的决定归属** | 2026-09-08 迁址时并记 |
| **F-12** | fylite | **`B-01` 的参考侧要不要改在 FUSE 1.1.5 上重跑**（该条现有结论建立在已遗弃的 0.7.0 冻结答案上，其 `status_note` 自陈这一问「仍未裁定」）。★2026-09-08 起**成本变了**：跑 1.1.5 所需的 Julia 环境已经在本机建好（F-4 的副产物），此前挡它的正是这一件 | 登记册 `B-01` status_note · SURVEY-2026-09-08 §一 |

★**本仓能自己做完**的现在是 F-1 / F-2 / F-12（F-4 · F-5 · F-6 已关）；F-9 要先定走哪边；F-3 是排期问题；F-8 要对外联系；F-10 / F-13 归 fydoc（F-11 已关），登记在此只为让本仓知道自己在等什么。

★★那四条 `planned`（`C-06` TEQ · `C-07` TOSCA · `B-09` DINA · `C-10` TRANSMAK）**当日全部执行完毕**，
均判 pass；它们本就不在上表里——**执行是定序册的活，不是本表的活**。本表只收「不做就没人做」的事；
判决与排期的唯一生成源仍是 `docs/benchmark/plan/plan.jsonld`（2026-09-08 晚：**通过 34 · 阻塞 1**，
登记册 35 条 · 17 场景，当日复测 34/34 全过）。

〔仍然成立〕本仓在 A–D 那条链上的位置是**消费方**：E-2 到位则 EAST 标准算例可用于本仓的
对拍与回归；E-4 裁定后计算态才有身份可入库。

---

## 记法

- 条目**只登记事实与依据**，不写结论；带〔推测〕的判断保留标记。
- 归属为他仓者，本表**不得**作为在本仓改动的依据。
- 关闭一条时写明**关闭日期与依据**（如 E-1：2026-09-06，逐片 `magnetics/ip` 实测）。
