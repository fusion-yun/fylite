# TODO — 仓级开放任务台账

登记 2026-09-06，**E 组 2026-09-08 重写；同日晚二次清理**（收官批：`B-08` · `B-10` · `C-11` · `C-10` 落地，`G-14` 修掉）；
**同日 D 组续做**（EAST 标准算例：E-7 · E-8 立项，E-2 清单短一截，新 `F-14`）；
**2026-09-10 E 组增 `F-15`..`F-23`**（起始设计岭缺省一役量到的九条：两条未决的求解器行为、三处闸子长期红或根本没在跑、两处数据缺口、一处构建不可复现、一处路径残留）。本表收**本仓及其上下游**当前未完成的事项——之所以合在一处，是因为它们
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
**动理学面有了实测的量而仍不可用**。★★2026-09-08 该条目自己往前走了一步：fydoc 仓里那份
「待删」的 mdsip 录音（F-13）**含本炮交付 EFIT 的标量**，据此量出**本炮有两个互不相容的
平衡**——交付 EFIT 的储能 187.1 kJ 对 g-file 转换件的 46.7 kJ，**差 4.00 倍**（详见该条目 §五）。

| 编号 | 归属 | 事项 | 依据 |
| :--- | :--- | :--- | :--- |
| **E-2** | 需数据访问 | 加热 / 驱动 / 杂质 / 输运的本炮数据只在 MDSplus（`202.127.204.12`）。★**2026-09-08 清单短了一截**：本炮的 `\WMHD` · `\BETAP` · `\LI` · `\PCRL01` · `\VP1` · `\DFSDEV` 与 EFIT `MEASUREMENTS` 已在 fydoc 的录音里（`\PCRL01` / `\VP1` / `\DFSDEV` 只有抽稀后的 253–463 点）。**加热 / 驱动 / 杂质 / 输运一支未录**，故不关闭 | 条目 §五.1 · §七 |
| **E-3** | fydoc · 待 fyo | Thomson 的不确定度只能标 `fylite:` 前缀（60 处）——被 B 组 O-2 卡住 | 条目 §八 |
| **E-7** | 需数据访问 | **本炮两个平衡互不相容**：交付 EFIT（录音）与 deck 储能差 **4.00 倍**、$\beta_p$ 差 4.45 倍，而 deck 自己 GS 闭合到 0.59 %。挡路的是**那份 g-file 不在任何仓里**（只有 sha256），其 `RUN_TYPE` 与名字里的 `loop` 读不到；`FYDOC-CASE-19` 收的三份 EAST g-file 没有本炮的。★★**对本仓的意义要说准**：受影响的是 **`B-06`**（`plan/R/east-137985`）而**不是** `V-15`（后者是 g-file 读写往返的恒等式，与压强内容无关）。`B-06` 的参照侧是 `oracle_east137985_4000ms`，而该 oracle 自陈其约束是「磁测 + `kprfit=1` 直接压强 65 点」——那 65 点正是 deck 的压强列。**故 `B-06` 作为「本仓能否复现这次重建」仍然成立**（它比的是同一个答案），**不**支持「本仓重建出了这一炮真实的平衡」这句更强的话 | 条目 §五.5 |
| **E-4** | 须语料裁定 | 自洽五面态是**计算产物**不是测量；`dev:result` 现有七个取值没有一个是为它准备的。**这是本条目自己走不过去的那一步** | 条目 §五 |
| ~~**E-5**~~ | fydoc | **已关闭 2026-09-08**（那一步已走）：逐片 12 道 PF 通流实测（fydoc `facts/tools/pf_drift.py`，纯标准库、只读）——最静段 **4.0–5.0 s**（总 3.17 %/s · 方向 1.17 deg/s），**4000 ms 落在其起点**，故重建选片不必改；全平顶方向仅转 7.91°，而逐道看 c1 降 50.9 %——两种读法量的不是同一件事，条目已并记。**「任一片都不是严格稳态」不变** | 条目 §二 |
| **E-6** | fydoc | `check_cases.py` 报 **28 处 / 19 组**不满足（其中 **14 组** reviewer 联系方式待补）。**既存项**，2026-09-08 再经 `git stash -u` 复核确认改动前完全相同。★当日走过 24/12 → 26/13 → **28/14** 三档：先是 `FYDOC-CASE-04`（FUSE）跑出答案、按该组**自己写的**规矩 `review.status` 由 `not-required` 改判 `pending`；再是 `FYDOC-CASE-19-east-efit` 立组（F-11），其 `reviewer` / `contact` 按同一条规矩记 `[TBD]`。**两次都不是新缺陷，是同一条规矩对新落账的东西生效** | fydoc `tools/check_cases.py` |

## E. 本仓（`fylite`）与内核（`fylite_kernel`）

★2026-09-08 更新。**此前这一节写着「本轮未在本仓留下未完成项」**——那句话在 09-06 成立，
当日的验证定序册第三轮与第三方源码盘点之后不再成立。下表是本仓／内核自己的活，
**不依赖上下游任何一条**。

| 编号 | 归属 | 事项 | 依据 |
| :--- | :--- | :--- | :--- |
| **F-1** | fylite | **`discharge-iter` 的门**。物理校验册 88 条现只评了 24，做了它可评条数才会动。要两件事一起做：`run_json` 走树门，**且**算例把装置文档绑成输入 | RUN-2026-09-08 §四 · §六.3 |
| **F-2** | fylite | **生成件里的手写段没有活路**。手写归因活不过下一次 `--write`，**而且不会有任何东西报错**——这是它比「写错了」更坏的地方。三个候选落点（判据册算例声明的 `caveat` · 本册子的 RUN 页 · 渲染器认一个锚点）**要先定**，才好写第二段 | RUN-2026-09-08 F-24 |
| ~~**F-3**~~ | kernel | **已关闭 2026-09-08**（用户裁定：**Rust 侧重写**）：26 条里 **11 条已重写**——层析 6 + 自标定方法学 3 落 `diagnostics.rs`，装配层编排 3 落 `transport.rs`；`cargo test --lib` 459 → **470 passed**，并做过变异检验（把基的 `clamp(0.0,1.0)` 改 `0.9`，边界那条当场判负）。★**剩下 15 条不是「没写」而是「本 crate 没有那个主体」**：UKAEA 网络 8（模块不在任何树里，许可那两条早已捞回）· 层析的重建质量 5（要反演求解器，本 crate 只导出基与行）· `source_set` 台账报表 1。逐条落位见 `tests/PHYSICS-MIGRATION.md` 该节 | `tests/PHYSICS-MIGRATION.md` 退役表 |
| ~~**F-4**~~ | fylite | **已关闭 2026-09-08**：专用 `Pkg.develop` 环境跑通 `FUSE.test_case(Val(:ITER_time), dd)`（FUSE 1.1.5 / IMAS 7.3.0，437.7 s，**61 个时刻**，`evolve_error: null`），答案收进 fydoc `FYDOC-CASE-04-fuse/corpus/1.1.5/`。`B-08` 随之判 pass。★捕获脚本加 `FUSE_TEST_CASE` 门——与 0.7.0 那份**出自同一个读取器**；★走不通的一条路已记在语料 README：把写盘的 `dd` 读回来归约，`json2imas` 在留空的二维字段上抛 `MethodError` | plan.jsonld `B-08` · 内核 `180dd93` |
| ~~**F-5**~~ | fylite | **已关闭 2026-09-08**：CHEASE 本机构建成功并自行重跑 `ntcase=2`（不读冻结产物），`B-10` 判 pass（GS 残差 5.257e-02，带 8e-2）。★该条的主要产出不是那个数，是一个读法——**加密盒子不是收敛检验**（101×65 → 401×257 残差不降反升；改内部网格才降 2.1 倍） | plan.jsonld `B-10` |
| ~~**F-6**~~ | fylite | **已关闭 2026-09-08**：映射逐项落实，`C-11` 判 pass——离子热通量系统偏低 **−42…−53 %**、电子热通量最差 **+131 % 恰在阈值**、八点全在训练箱内（门里第一条就判这个）。★留痕的那一项：算例是「红/蓝氢」示踪设置（两支同位素氢 + Be + C）而网络只模一个有效主离子，**Be 那一支在低梯度端比氢两支合计还大**——所以离子那一栏的差里含着**成分折叠**，不全是代理误差 | plan.jsonld `C-11` |
| ~~**F-7**~~ | — | ~~`B-09`：要不要自跑 DINA 当参考~~ **作废（登记当日）**：DINA 的参考答案就在 `~/workspace/data/ITER Scenario/`，不需要自跑，那次许可/清净室裁定也就不必做了。★留着这一行是因为它示范了一件事——**这条待办从提出到作废不到一小时，而它提出的依据是台账里一句写着「未取回」的旧备注**。备注记的是写它那天的状态 | SURVEY-2026-09-08 §一 · §四 |
| **F-8** | 可发信 | **`C-08` 向作者索取 GENE 那批次的 ν* 与逐半径 Miller 参数**（或那次 JINTRAC 模拟的对应量）。这是六条阻塞里**唯一一条只差一封信**的 | plan.jsonld `C-08` |
| **F-9** | fylite · fydoc | **`code/breakdown` 仍跑不出结果，但挡路的换了一件事**。G-14 修掉后 ITER 与 EAST 过了几何这一关，卡在下一句：「the device gives no supply current limit (`power_supply/current_limit_kA`) and the plan binds no `i_max_aturn`」。两条路：装置描述补上供电限值（是**数据缺口**，ITER 的 A-Box 里没有；EAST 的手工牌里有 `current_limit_kA: 14.5`），或算例侧绑一个 `i_max_aturn`。**先定这一条走哪边**，再谈把 breakdown 接进定序册 | 2026-09-08 实测（`fy run design breakdown --device iter --facts <fydoc>/facts`）|
| **F-10** | fydoc | **生成的装置清单指向不存在的路径**。`abox2jsonld.py` 把每份件搬位（剥 `tree_root`）并改名（`.yaml`→`.jsonld`），却把清单里的 `providers[].path` **原样抄过来**——于是 `best` / `cfetr` / `cfedr` 的清单指着 `fyo/latest/providers/pf_active/base.yaml`，书里没有这个文件，解析不到线圈；`west` 更是**一个 provider 都没声明**。四台因此在 `code/breakdown` 上报「the document carries no `pf_active/coil`」。★ITER 之所以能过，是因为**它那份清单是为书手写的**（`path: providers/pf_active/base.jsonld`）——不是生成器做对了 | 2026-09-08 实测（四台逐台跑）|
| ~~**F-11**~~ | fydoc | **已关闭 2026-09-08**（fydoc `9eb7657`）：三份 EAST g-file 收进算例书 `FYDOC-CASE-19-east-efit`（`corpus/` 与 `case.yaml` 同址、`checksums` 逐件在册、`payload: in`），本仓的门与登记册指针随之改指。★★查证时发现比「指针脆」更要紧的一层：2026-09-04 的裁定删 `corpus/experiment/` 时写明这批件**不可重取**、「只剩 git 历史与未跟踪的 `todelete/`」，而同日一次**讲文档规则**的提交把 `todelete/` 顺带跟踪了进来、提交信息一字未提——于是一批不可重取的件被一个名叫「待删」的目录持有着。★迁入**不等于放行**：`release: internal` 不变，review 待具名 | 登记册 `V-15` 的 `has_input` |
| **F-13** | fydoc | **`todelete/` 余下的部分未判**：`east/mdsip-137985.json`（一次 mdsip 会话的逐帧录音，fylite 的浏览器门经 `FYLITE_MDS_FIXTURE` 读它）是**测量**不是重建产物，按分工归实验层 / `fydata` 的 A-Box；另有 `todelete/device/{east,iter}` 与 `todelete/facts/`。★F-11 只搬了它该搬的那一份，**没有顺手替其余的决定归属**。★★**2026-09-08 这一条的分量变了**：那份录音不是只给浏览器门当夹具的——它是本炮**交付 EFIT 标量在整个生态里的唯一一份**（E-7 全靠它），且**含五炮**（137984 · 137985 · 137986 · 165704 · 165705）而文件名只写了一炮。一份这样的件住在名叫「待删」的目录里 | 2026-09-08 迁址时并记 · 同日实测 |
| **F-14** | fylite | **POINT 的条纹清洗判据只设下界**。`python/fylite/io/est2.py` 的 `good = (a_ne is not None) and (abs(a_ne) > floor)`（`floor = gate * median`），注释自陈的理由是「丢了条纹的弦会塌到中位数的一小部分」——**这对塌下去成立，对跳上去不成立**，而条纹跳是整数倍相位跳，两个方向都会发生。EAST #137985 实测：**c4 在 9 片中的 6 片上超同片存活中位数 3 倍以上**（最高 **166 倍**），每一片都带着 `weight_nel = 1.0` **交给重建**；c11 另在 1.0–2.0 s 三片上超 7–20 倍。★★同一支工具的第二条口径：弦中位数与干涉仪自己的线平均道 `\DFSDEV` 的比值在九片上走了 **45 倍**（0.03 → 1.34）——弦长不变，故不是几何；1.0–2.0 s 那三片的 POINT 归约实际在读噪声。★**重建选的 4000 ms 落在比值正常的那一段**（0.87–1.34），故本仓现有结论不受影响——但判据的形状是错的 | fydoc `facts/tools/point_chords.py`（2026-09-08 实测）|
| **F-12** | fylite | **`B-01` 的参考侧要不要改在 FUSE 1.1.5 上重跑**（该条现有结论建立在已遗弃的 0.7.0 冻结答案上，其 `status_note` 自陈这一问「仍未裁定」）。★2026-09-08 起**成本变了**：跑 1.1.5 所需的 Julia 环境已经在本机建好（F-4 的副产物），此前挡它的正是这一件 | 登记册 `B-01` status_note · SURVEY-2026-09-08 §一 |

| **F-15** | kernel | **起始设计的岭调过 2e-1 之后，退火一趟都不接受**。`code/discharge` `stage=anneal` 的 `pass` 事实报 **0** —— 八趟里没有一趟比没动过的起始设计更好，即退火一步没走；交出来的 κ=1.146（要的 1.389）、磁轴离实测轴 **102 mm**（EAST 小半径 0.44 m）。换 8 / 16 / 24 趟、`anneal_hi` 0.10 / 0.03 / 0.01 六种排程，`shape_error` **逐位相同**（0.14660），故不是排程敏感。λ≤1.5e-1 时正常下降（最优趟 6–8，`shape_error` 0.035–0.053）。★两解未分辨：接受规则只收「比历史最优更好」而步长降不到排程下限以下〔推测〕，或该电流水平附近确无更好的点。**这条定着岭缺省的上界** | `fylite_kernel` `tests/test_start_against_the_machine.py`（2026-09-08 实测） |
| **F-16** | fylite | **装置档自由边界解不收敛，且不随预算单调**。`validate-worker-interp-device`，EAST，缺省 λ=1e-1：`free.residual` 400 步 5.6e-3、1200 步 6.8e-3（`settled: true`，423 步停）、4000 步 **6.1e-2**。**不随预算单调下降**，故不是步数不够。λ=3e-1 上同一条是 5.8e-2。★最早 λ=1e-3 时的 4.9e-8 **不可比**——那份属于一个塌成 2 cm 的位形（a_minor 0.0195 m 对要的 0.357 m），几乎没有东西要收敛 | `app/tests/validate-worker-interp-device.mjs`（2026-09-08 实测） |
| **F-17** | kernel | **五个测试模块自 T-4 迁移起就收集不了**，因此一直没在跑：`test_assembly`（取 `fylite.scenario.model.sources`）· `test_nn_tglfnn_ukaea`（`…model.tglfnn_ukaea`）· `test_point`（`fylite.io.kfile`）· `test_selfcal`（`fylite.scenario.analysis.selfcal`）· `test_tomography`（`…analysis.tomography`）——都是那一串刀把公共仓模块收进 `tests/oracles/` 之后没有回指的残留。★**红着的闸子有人看得见，收集不了的没有**：此前每一次「全量通过」的读数都不含这五个模块 | 2026-09-08 `--collect-only` 实测 |
| **F-18** | fylite | **node 闸子五道长期红**：`validate-flux-match` · `validate-guide` · `validate-q` · `validate-worker-vertical` · `validate-zerod`。逐道未定性（缺数据 / 夹具过期 / 真错，三者未分）。已知一处细节：`validate-worker-vertical` 的失败是 `design` 答案里 `vertical: null`——闸子要一个垂直位移判据，门没给 | 2026-09-08 全量扫描 |
| **F-19** | fydoc | **装置文档不声明线圈工程限值**。七台自带装置的 `pf_active.coil` 无一带电流上限。后果：起始设计的真机闸只能拿 EAST #137985 **那一炮自己用到的**最大通道电流当界——那是**演示过的值**不是铭牌值，机器可能能交更多，也可能那一炮本就贴着限值。★与 **F-9** 是同一条数据缺口的两处露头（F-9 缺的是 `power_supply/current_limit_kA`，本条缺的是逐线圈的匝安上限）。★没有出处应留 `[TBD]`，不填估值 | `fylite_kernel` `tests/test_start_against_the_machine.py` 的判据取法（2026-09-08） |
| **F-20** | fylite · fydoc | **真机参照只有 EAST 一台**。起始设计岭缺省的物理判据全落在 #137985 一炮上——它是两仓里唯一带实测放电的机器（实测 LCFS · Ip · BRSP · 交付平衡）。其余六台只能拿合成目标（限制器包围盒 ×0.6，κ=1.6）扫，证据强度低一档：同一组 λ 扫下来 **ITER 在 3e-1 上反而最好，WEST 全平，CFETR 每个 λ 都不稳**——即 **F-15 那道坎在别的机器上没出现** | 2026-09-08 逐台实测 |
| **F-21** | kernel | **wasm 构建跨环境不可复现**。同一份源码，开发容器构建得 core 1 810 792 字节 / `55d8876d…`，另一台得 1 765 754 / `dca90b0c…`；**`kernel_ext` 也变**（615 886 → 615 110）而其源码那一役一字未动——差异因此锁在**构建环境**不在源码。两侧 rustc 均 1.94.1；容器内部可复现（同源多次构建逐位相同）。后果：`docs/note/app-provenance.md` 二进制表在两台机器之间来回改，`test_bundled_artifacts` 谁重建谁红（**2026-09-10 合并 develop 时又冲突一次**） | 2026-09-08/10 两侧实测 |
| **F-22** | kernel | **EAST 手工卡片仍写着构建机的绝对路径**。`9091776` 把 `/home/salmon/workspace/fydata/abox/experiment/east/137985` 从 `machine_desc/east/east_device.yaml` 改成了 `fydata:abox/…`，**同一字符串仍在 `machine_desc/east/fylite_device_east.json` 里**；而 EAST 的 facts 卡是从后者派生的（`tools/abox-to-facts.py` 自陈 EAST「手工卡片保持原样」），故它照旧出现在 `dist/facts/device/east.jsonld` | 2026-09-08 `grep` 实测 |
| **F-23** | kernel | **内核仓 pytest 长期红 9 条**（排除 F-17 那五个收集不了的模块）：`test_nn_surrogate` 4 · `test_benchmark_registry` 1 · `test_circuits` 1 · `test_jintrac_flattop` 1 · `test_loop` 1 · `test_tglf_selfconsistent` 1。全量读数 **9 failed / 1199 passed / 46 skipped / 9 xfailed**。★用「撤掉当役改动、重编、重跑」核过**是既有的**。★逐条未定性；〔推测〕`test_nn_surrogate` 那四条与权重不随仓发行是同一条线 | 2026-09-08 全量扫描 · 同日 stash 对照 |
| ~~**F-24**~~ | fylite · kernel | **T-C36：`ohm` 是差商，却按行进量比较**——`test_crosshost_replay` 的两条判据 2026-09-10 起红，而**它们自己的报错说错了原因**（写「a disagreement about the step」）。实测：**行进量全在机器精度上**（`te` 6.1e-16 · `ti` 1.2e-16 · `psi` 3.2e-16 · `q` 3.7e-15），只有 `ohm` 6.75e-12 与 `p_ohm` 2.9e-13 差四个量级。`ohm` 不是行进出来的：`scenario.rs` 用 `E_par = ratio*(psi[k]-prev[k])/dt` 现算，而本变体上 |psi| 33.35 对 |psi−prev| 中位 1.45e-4，**相消因子 1.07e5（最差节点 1.51e5）**；3.2e-16 × 1.51e5 = **4.8e-11 上界住了那 6.75e-12**。★所以这是**比较口径的范畴错误**，与 `ENTRY_OUT_KIND` 里 `noise` 那一行点明的是同一类；但 `ohm` **不是** `noise`（它是物理加热密度，「两边都小」不是它的判据），所以缺的是一个**新的 kind**：由状态行**差商**出来的实数行，判据是「不超过该状态行自己的一致度乘以相消因子」。落点在内核 `fyo::ENTRY_OUT_KIND` 与本仓 `engine/crosshost.py::compare`，**不是那个数字**。★★**故意留红**：放宽带宽正是该文件自己的说明禁止的（「a band chosen to swallow 6.2e-13 would agree with any future disagreement up to that size, including a real one」），而「多大的放大是可接受的」是**裁定**不是测量。机制已定，待裁的是那个上限★★★**同日追加的第二件，比第一件更要紧**：这条判据**没有任何东西核对两侧制品是否同源**。`compare()` 的 `environment` 记了 native 侧每个库的 `sha256`，wasm 侧**只记路径**（`{"host": "wasm", "artifact": str(WASM)}`，`crosshost.py:226`）。于是**一份过期的 wasm 读起来与一条真实的物理分歧完全一样**——而这正是一个会自我印证的假阳性：判据红了，报错说两个宿主不一致，而它们确实不一致，只是因为它们是两次不同的构建。★这不是假想：本轮为修自举 NaN 重建内核之后，native `.so`（17:51）与 wasm（14:06）**当场不同源**；上面那份相消诊断之所以站得住，是因为量之前**我手工比过两者的 sha256**并排除了版本偏差——**而判据自己不做这一步**。落点：`compare()` 记 wasm 的 `sha256`，并在两侧 ABI/构建戳不一致时**先按不同源拒绝**，而不是把差异算进 `worst` 交给带宽。★这一条**独立于**第一件，且应当先做：不先钉住同源，那个放大上限无论定成多少都在量一件说不清的事。★★**已做（2026-09-10 同日）**：省源台账补进两份 `.so` 的 sha256（此前只记两份 `.wasm`，于是只重建 `.so` 而不补 `--wasm-check`，台账与盘上 wasm 仍一致、闸子照样绿）；`test_bundled_artifacts` 连 `.so` 一起核（改一字节当场红）；`crosshost.compare()` 的记录补上 wasm 的 `sha256` 与字节数；`test_crosshost_replay` 三条比浮点的判据**在比之前**先对台账核同源，不同源就**跳过并说明**（实测：改 wasm 一字节，八条全部跳过并写明「NOT one build」，而不是报 `ohm` 分歧）。**余下待裁的只剩放大上限这一件。** ★★★**已裁定并关闭（2026-09-10，用户：选项 C）**：上限不是一个选定的带宽，而是**这一次运算自己的误差传播上限** `bound = C · reldiff(src) · max_k |src_k|/|src_k−prev_k|`，`C = 4`（因子取在最坏节点上，不逐节点取；C 明写为 `DIFFERENCED_C`，不藏在容差里）。**放大因子在两个宿主上各算一次，要求相差 ≤ 10 %、取较大者** —— 若两侧对**步长本身**有分歧（那才是真缺陷），因子就会分开，只信一侧的因子恰好会把最该抓的那种情形洗掉。实测：`ohm` 落在上限的 **0.023**，两侧因子相同（2.306e5），判词 `same`；注入检验 **1e-10 通过 / 1e-9 被拒**，即上限在 **~3e-10** 咬合，比它所解释的放大量紧三个数量级。落地：`fyo::ENTRY_OUT_KIND` 增两行 `differenced:psi,psi_prev_out`（14 → 16 行，`INTERFACE_DIGEST` 随之更新而 **`INTERFACE_REVISION` 不动**——只增不改，旧读者落到 `real` 路径即今日行为）；`crosshost.compare()` 认这个 kind 并新增 `differenced` 记录。公开侧 `test_crosshost_replay`：**14 通过 / 11 跳过**，两条有意的红转绿。记录见内核 `docs/note/cfedr-15ma-reproduction.md` §6.2 | 2026-09-10 实测（`crosshost.py:226`；native 17:51 对 wasm 14:06）|

| **F-25** | kernel | **取向已能推导，但 `signb`/`signq` 仍是 C ABI 的入参**（`c_api.rs:974` · `5212` · `5246`，缺省 +1）。D5 结案后（内核 `docs/note/cfedr-15ma-reproduction.md` §6.1）取向由 `mapping::orientation` 从带号数据按 COCOS 17 推出，于是这两个入参**同时存在两条真源**：宿主给的字面量，与从平衡推出的值。★现状不红只是因为仓内每个宿主都不再给它们；**契约面上它们仍然可被覆盖，而覆盖一个可推导量没有判据能拦**。待裁的是「还要不要留作入参」——留（则需一条判据核对宿主给的与推出的一致，不一致即拒）或撤（则动 ABI 契约，要走版本）。★★顺带一层：本炮之所以查得清，是因为上游把符号也交给预设——`profiles_gen` 三处 `abs()` 丢弃原件符号，而承载取向的 `kccw_*` 在 statefile 里缺席（实测计数 0），落到 DIII-D 缺省。**「入参」这个形状本身就是上游的形状**，所以这一裁定不是本仓的小事 | 2026-09-10 D5 结案时并记（§6.1 末） |
| **F-26** | kernel | **`test_evolve_fluxmatch_code` 的夹具在问一个没定义的问题**。它把**一次运行的压强**与**另一次运行的通量**配在一起，同时把自举打开；于是判据在核一个不自洽的态。实测：`bootstrap = 0` 时该轮返回 `ip` = **8.0000e5**（即请求值，五位吻合），说明求解路径本身是通的，**红的是夹具的口径不是代码**。待裁的是**这条判据应该断言什么**——（a）自举关、断言 `ip` 回到请求值（现已实测成立，但那就不再检验自举）；（b）两侧取同一次运行，自举开、断言自洽 `ip`；（c）退役该夹具，另立一条。★不擅自选：改判据的断言等于改它保护的东西 | 2026-09-10 实测（`bootstrap = 0` 对照） |

★**本仓能自己做完**的现在是 F-1 / F-2 / F-12 / **F-14** / **F-16** / **F-18**（F-4 · F-5 · F-6 已关）；内核侧自己能做完的是 **F-15** / **F-17** / **F-21** / **F-22** / **F-23**（F-17 只差改 import）；F-9 要先定走哪边；F-8 要对外联系；F-10 / F-13 / **F-19** 归 fydoc（F-3 · F-11 已关），**F-20** 要第二台机器的实测放电；**F-25 · F-26 都在等一次裁定，不等测量**，登记在此只为让本仓知道自己在等什么。

★★那四条 `planned`（`C-06` TEQ · `C-07` TOSCA · `B-09` DINA · `C-10` TRANSMAK）**当日全部执行完毕**，
均判 pass；它们本就不在上表里——**执行是定序册的活，不是本表的活**。本表只收「不做就没人做」的事；
判决与排期的唯一生成源仍是 `docs/benchmark/plan/plan.jsonld`（2026-09-08 晚：**通过 34 · 阻塞 1**，
登记册 35 条 · 17 场景，当日复测 34/34 全过）。

〔仍然成立〕本仓在 A–D 那条链上的位置是**消费方**：E-2 到位则 EAST 标准算例可用于本仓的
对拍与回归；E-4 裁定后计算态才有身份可入库。

★★**2026-09-08 加一句**：E-7 提醒的是**同一个消费方位置上一件更细的事**——本仓从上游取来的
「参照答案」可以既是**忠实转录**又**不是这一炮**。`B-06` 的参照侧就是这样：oracle 忠实地复现了
那份 g-file，而那份 g-file 与本炮交付 EFIT 差 4 倍。**「转录对了」与「转录的是对的东西」是两问**，
本仓的登记册此前只问了前一问。

---

## 记法

- 条目**只登记事实与依据**，不写结论；带〔推测〕的判断保留标记。
- 归属为他仓者，本表**不得**作为在本仓改动的依据。
- 关闭一条时写明**关闭日期与依据**（如 E-1：2026-09-06，逐片 `magnetics/ip` 实测）。
