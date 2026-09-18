# CFEDR 堆芯模型工具与工作台（`app/`）

本目录放的是可运行的部分、它的输入，以及整炮跑出来的产物：单文件模型工具、单文件网页、
跑一炮所需的三份输入、fylite 的动态库，加上两档整炮的输出 · 控制波形 · 断点。
★**目录自成一体**：工况 · 回放 · 装置卡 · 库都在这里，脚本内没有绝对路径，也不引用目录之外
的文件；下面的命令均在本目录内执行。

| 文件 | 是什么 |
| :--- | :--- |
| `cfedr_core_model.py` | 模型工具（单文件）：按名表 dict 进出，物理经 `libfylite.so` 交给 fylite 内核 |
| `cfedr_studio.html` | 波形工作台（单文件，双击即开）：编控制波形与磁面出输入 JSON；导入输出 JSON 看时序 · 位形 · 剖面，导出单片 JSON 或 g-file |
| `state_init.json` | **初始状态**（`--state`）：40 s 交接态 + 物理设置（χ 表 · 沉积表 · g-file 度规）——由算例工况 `repro-1p5d/continuous/plan_40C.json` 转来 |
| `device_cfedr.json` | **装置描述**（`--device`，**缺省的 isoflux 档必需**）：线圈几何与额定安匝 · 第一壁 · TF |
| `waveform_studio.json` | **页面导出的控制波形**：31 个名表节点（页面「导出控制波形」的产物，也就是内置默认算例那一份） |
| `libfylite.so` | fylite 的动态库（一个真文件，无版本后缀链接）：**内核（物理）与中间层（格式 · 装配）在同一个库里**，且是**不链 HDF5 / netCDF 的那一档**（公开仓 `bash rust/build.sh --no-io`） |

★**只留必需**：目录里只有工具 · 库 · **跑一炮的三样输入**（装置描述 · 初始状态 · 控制波形）。
**产物不入库**——状态与时序都是可再生的，照下面「用法」两条命令跑一遍就有；两段跑完约 7 MB，
留在这里只会让目录背着可再生的字节。isoflux 档同理，命令在用法一节里。

**JSON 的命名规则**：`<类>_<限定词>.json`，全小写下划线，**类在前**——`device_` 装置描述 ·
`state_` 状态 · `waveform_` 控制波形 · `run_` 完整时序，正好是那四类；限定词说是哪一份
（`init` 初始 · `check` / `isoflux` 两档 · `d2025` 那一炮 · `preset` 页面预设）。于是 `ls` 按类
成组，一眼看得出手里这份该进哪一格。

这几份输入是从别处**转来或拷来**的：`state_init.json` ← 算例的
`repro-1p5d/continuous/plan_40C.json`（工况转状态）· `waveform_studio.json` ← 页面「导出控制波形」
（其节点源自内核仓的 PCS 回放 `docs/cases/pcs/cfedr-d2025-replay.json` 与报告页的平衡序列）·
`device_cfedr.json` ← 公开仓
`dist/facts/device/cfedr/cfedr_device.yaml`（YAML 转 JSON）。源件更新后需手动重转一次：
换来的是「整目录拷走即可运行」，而且目录里**只有那四类文件**。

**目录之外只剩一样**：**Python 3.10+**，而且**只用标准库**——工具自己就
`import ctypes / json / math` 几个，没有 numpy，也没有别的第三方包。（网页那两道检查要 node。）

★**库只在一处**：脚本旁边的 `libfylite.so`，文件名固定。脚本不搜索上层目录、不读环境变量、
不认第二个名字——「到别处找库」一旦找错**不会报错**，它会静默地用另一份库完成整炮计算，
而这种错误只在读数上露一点。要换库，就替换这个文件。

★**这份库没有外部 C 依赖**：`ldd` 只列出 `libgcc_s` / `libm` / `libc`，因此拷到一台未装依赖的
机器上也能运行，无需安装 libhdf5 / libnetcdf，也无需设置 `LD_LIBRARY_PATH`。代价是它
**不能读写 HDF5 / netCDF 文件**（IMAS 条目那条路径）：调用时会得到一条按名拒绝
（`built without the hdf5 feature`），而不是符号缺失。本 demo 全程走 JSON，用不到该路径。
实测：全功能 8.94 MiB（要 `libnetcdf.so.19` + `libhdf5_serial.so.103`）→ 这一档 8.19 MiB，
**导出面一字不差**（100 个，59 个内核入口全在），同一段算例读数**逐位相同**。

★**重建这份库才需要两个仓**（`fylite_kernel` 出静态归档、`fylite` 链成一个 `.so`，
`bash rust/build.sh --no-io`）——跑这份 demo 不需要，库已经在这里。

---

## 一、模型工具

### 两个入口

| 入口 | 函数 | 做什么 |
| :--- | :--- | :--- |
| 一步 | `step(state, control) -> (state, out)` | 当前等离子体状态 + 下一时刻的控制参数（输入名表 dict）→ 下一时刻的状态与输出名表 dict |
| 整炮 | `run_discharge(plan, nodes, t0, t1, dt, …)` | 循环调用 `step`，按回放指令走完上升 · 平顶 · 下降 |

状态是纯 JSON（`{"t", "plan", "record", …}`），可整份存盘、下次继续——**断点**就是这份 dict：
`--save-state` 存（跑完或中途被拒都会存），`--state` 续（`--t0` 可省，取断点时刻）。
实测：40 → 44 s 连续跑完，与 40 → 42 s 存断点再续到 44 s，结果**逐位相同**。

**只收 dict**：名表是一张名字表，不是位置表。进程内走 `step(state, control_dict)`，文件走
`write_waveform` / `read_waveform` / `write_output` 的扁平 dict。

算这份结果的内核是哪一份，写在输出的 `meta.kernel_version` / `kernel_abi` / `kernel_built` /
`kernel_sha256` 里，页面页首显示。

### 名表：两张表

**dict 的键就是名表**（进程内 `step(state, control)`，文件走扁平 dict），进出各一张。点数不单列：
`len(boundary)` 即控制点数，剖面长度即 `n_roh`——同一份信息不记两处。

#### 输入名表（`control`）

| 键 | 单位 | 是什么 |
| :--- | :--- | :--- |
| `time` | s | 本次推进的**终点**（内核的 `t_stop`）：必须在 `state` 当前时刻之后。文件里的列名也是 `time` |
| `Ip` | A | 设置 `ip`；工况开了 I_p 反馈环时由它调边界圈电压 |
| `ECRH` · `ICRF` | W | 两路**合并**后整体缩放工况那张沉积表（要分谱沉积得另给两张表） |
| `NBI` · `LHW` | W | **必须为 0**：CFEDR 无中性束、无低杂波（没有束能量 · 注入几何 / 频率 · n∥ 谱 · 天线位置），非零即拒 |
| `ne_bar` | m⁻³ | **线平均密度指令**：非零就开密度反馈（见 §密度）；0 = 不控密度 |
| `n_roh` | 1 | **剖面点数**（径向分辨率）：只在**起步**那一步作数，工况自带的剖面按它线性重采；中途改按名拒绝 |
| `boundary` = `[[R, Z], …]` | m | LCFS 的 **isoflux 控制点**（缺省 8 点，3–24 可改，见 §isoflux） |
| `pf_current` | A·turns | **PF 线圈电流**（整匝安匝，与装置卡 `i_max_aturn` 同口径）：给了就作 isoflux 解的通道起始安匝 |

★`n_roh` 与工况自带的点数不同时，起步剖面（连同 χ 表等落在同一张径向网格上的输入）按 ρ
归一后**线性重采**。重采本身会改变起步态：实测首步 P_fus 29.1 MW（52 点，工况原网格，不重采）·
37.1 MW（41 点）· 37.7 MW（81 点）——不同 `n_roh` 的结果不应直接并列比较。

#### 输出名表（`out`）

一张表覆盖全部：0-D 量每步一个数，剖面每步一条（nt × n），线圈电流每步一组（nt × m）。
页面的一维视图按输出文件里的 `meta.profiles` 动态生成——这张表增加一行，页面即多出一格。

| 键 | 形状 | 单位 | 来路 |
| :--- | :--- | :--- | :--- |
| `P_fusion` | 0-D | W | 内核事实 `p_fus`（门没报就是 NaN——宿主不补） |
| `betat` | 0-D | % | 内核的 `beta_t`（比值）× 100 |
| `betan` · `betap` · `li` | 0-D | 1 | `beta_n_tot`（含快 α）· `beta_pol` · `li3` |
| `dfsdev` | 0-D | m | isoflux 档取内核的 `dfsdev`（求解器的边界间隙 rms）；固定位形档是指令点到所用 LCFS 的距离 rms（几何比对） |
| `vloop` | 0-D | V | `v_loop_end` |
| `wmhd` | 0-D | J | `w_th + w_fast` |
| `ne_bar_cmd` / `ne_bar` | 0-D | m⁻³ | 密度的**设定值 / 实现值**（实现值取内核的 `ne_line` = ∫n dρ / ρ_max） |
| `fuel_rate` | 0-D | s⁻¹ | **执行器**：内核报的 `fuel_rate_used`（本步真正生效的加料率） |
| `n_coil` | 0-D | 1 | 线圈路数（回显） |
| `rho_tor_norm` | 剖面 | 1 | 归一环向通量半径，其余剖面共用的横轴 |
| `Te` · `Ti` · `Ne` | 剖面 | eV · eV · m⁻³ | `core_profiles` 的电子温度 · 离子温度 · 电子密度 |
| `q` | 剖面 | 1 | 安全因子 |
| `p_fus` | 剖面 | W·m⁻³ | 聚变功率密度 `p_fus_dens`（α 功率按 E_α/E_fus 还原成总聚变功率） |
| `p_aux` | 剖面 | W·m⁻³ | 辅助加热沉积密度 `p_aux_dens`（这一步电子与离子两路之和） |
| `p_ohm` | 剖面 | W·m⁻³ | 欧姆加热密度 |
| `p_rad` | 剖面 | W·m⁻³ | 辐射功率密度（`rad_adas + rad_sync`） |
| `pressure` | 剖面 | Pa | 热压强（`profiles_1d/pressure_thermal`） |
| `p_fast_alpha` | 剖面 | Pa | 快 α 压强 |
| `j_bs` · `j_cd` | 剖面 | A·m⁻² | 自举电流密度 · 驱动电流密度 |
| `fpol` | 剖面 | T·m | 极向流函数 F = R·B_φ |
| `psi_norm` | 剖面 | 1 | 归一磁通（写 g-file 时插值要它） |
| `pf_current` · `coil_names` | 线圈 | A·turns | isoflux 档是每步自由边界解出的安匝；固定位形档给了 `--device` 就按工况那条固定 LCFS 解一组（I_p 变过 5 % 才重解），不给则回显输入 |
| `extra.*` | 0-D | — | 名表之外、同一次调用就有的量：W_th · W_fast · Q · H98 · f_GW · I_bs · τ_E · L-H 相位 · P_rad · P_sep · 本步内核调用数 · `ip_cmd` / `p_aux_cmd` · `fuel_rate_next` |

#### 来路：每一条由谁给出

★★★**宿主不计算任何物理量**：上表每一条，要么是门给出的事实 / 剖面，要么是自由边界解的结果，
要么是回显指令。聚变与辅助加热的功率密度取内核的 `p_fus_dens` / `p_aux_dens`，热压强取
`pressure_thermal`——门未给出时整条不写，宿主**不**以 e(n_eT_e + n_iT_i) 之类补足（那将是第二套
物理实现）。0-D 量同理：门未报则为 NaN。

内核那两条功率密度由一条判据约束（内核仓 `cargo test`
`the_two_power_densities_integrate_to_the_powers_the_step_reports`）：`p_fus_dens` 的体积积分
× α 份额必须等于本步的 `p_alpha`，`p_aux_dens` 的体积积分必须等于本步的 `p_aux`。宿主侧的旁证：
t = 60 s 这一步，内核给出的 P_fus(ρ) 峰值 **1.650 MW·m⁻³**，与按 Bosch–Hale 独立计算的 1.651
之比为 **1.0000**，0-D P_fus 两者同为 476.6 MW。

**每个量的来路**随输出走在 `meta.provenance` 里（页面在每张图下标出来）：

| 来路 | 有哪些 |
| :--- | :--- |
| `kernel` 门直接给 | `P_fusion` · `betat` · `betan` · `betap` · `li` · `vloop` · `wmhd` · `ne_bar` · `fuel_rate` · `rho_tor_norm` · `Te` / `Ti` / `Ne` · `q` · `p_fus` · `p_aux` · `p_ohm` · `p_rad` · `pressure` · `p_fast_alpha` · `j_bs` · `j_cd` · `fpol` · `psi_norm` |
| `solver` 自由边界解给 | isoflux 档的 `dfsdev` 与 `pf_current` |
| `check` 宿主做的几何比对 | 固定位形档的 `dfsdev`（指令八点到工况 LCFS 的距离 rms——门里没有目标曲线可比） |
| `echo` 回显指令 | `ne_bar_cmd` · `n_coil` · 固定位形档**未给装置卡**时的 `pf_current` |

各条的口径写在 `meta.provenance_note` 里。`meta.*` 另带 `r0` · `b0` · `limiter_r` /
`limiter_z`——有了它们，一份输出文件**自带**写一份 g-file 所需的全部量。

### 密度：名表中的一路控制

`P_fus ∝ n²⟨σv⟩`，密度不加控制就达不到燃烧点：仅用工况自带的恒定加料率跑整炮，平顶密度降到
4×10¹⁹ 量级，**P_fus 停在 54 MW**。实机上密度本就是独立的一路回路（设定值为弦平均 n̄_e，
执行器为气体 / 弹丸），CFEDR 文献给出的场景规格也正是 n̄_e(t)。因此 `ne_bar` 与 I_p、四路加热
并列于名表，缺省即生效，并派生出两条控制：

| 名表项 / 选项 | 作用 |
| :--- | :--- |
| `ne_bar`（名表第 7 项）[m⁻³] | 弹丸加料率按「窗末平均 n_e / 目标」比例调，限幅 4 × 工况加料率 |
| `edge_ne_ref=(edge, n̄_e)` · CLI `--edge-ne-ref` | 边界密度按指令线平均密度同比缩放（密度通道的边界是状态末点的 Dirichlet） |
 
**复现核对**（固定位形档，40 → 150 s，`--edge-ne-ref 5.474e19 1.139e20`）：150 s 得
P_fus **1245.9 MW** · β_N 2.56 · W_MHD 826 MJ（热 765 + 快 α 61），与分窗驱动的参考运行一致。
那一档整炮 379 步，走到 6169.5 s 被内核拒绝（下降段末端的种类状态不收敛）；产物不留在目录里，
加 `--fixed-shape` 再跑一遍即得。★**缺省的 isoflux 档是另一组读数**（目录里的 `run_full.json`
就是它）：381 步、走到 6170.5 s 被同一条拒绝挡下，150 s 得 P_fus **1649.9 MW** · β_N 3.14 ·
W_MHD 929 MJ。两档差在度规——位形每步重解 vs 整段冻结，不是同一个问题的两个答案。

**三条需一并阅读的限制**（这一路是控制，不是预测）：

* 平顶那组读数是**在给定 n̄_e 之下**得到的——密度这一维是指令，并非模型独立预测。
* 一个指令驱动**两个执行量**（加料率的动态反馈 + 边界密度的静态同比缩放）；后者是无记忆的
  线性外推，更换标定会改变结果。
* **加料执行器在燃烧段一直饱和**：isoflux 档整炮 381 步里 **335 步**顶在限幅
  4 × 8.22×10²⁰ = 3.29×10²¹ s⁻¹ 上（固定位形档是 379 步里 329 步，自 55 s 起）。即燃烧段的密度
  实际由边界缩放维持，弹丸这一环处于开环。实现 / 指令之比：首步 1.092 · 爬升段最低 0.638 ·
  150 s 处 0.979 · 末步 1.260（下降段相反：指令掉得比密度快）——模型中没有主动抽气这条路径。

### 两档：isoflux（缺省）与固定位形（只在平顶）

**整条波形的演化只能走 isoflux 档**——位形随 I_p 与形状指令一路在变，拿平顶那张冻结的度规去算
爬升段就是错的，而且**错得看不出来**：输出里的等高线一动不动，读数却照常给。所以：

| 档 | 何时用 | 位形怎么来 | 代价 |
| :--- | :--- | :--- | :--- |
| **isoflux**（缺省） | **整条波形**——上升 · 平顶 · 下降 | 八点作 LCFS 控制点，点动过 `--boundary-tol` 或 I_p 变过 5 % 就重解一次自由边界 | 每次解 **8–14 s**；需要 `--device` |
| `--fixed-shape` | **只有平顶那一段**（位形本来就不变） | 工况自带的 g-file 度规，整段冻结 | 快；八点只作检查（`dfsdev` 是几何比对） |

★固定位形档里，指令位形一旦离工况那条 LCFS 超过 0.25 m，模型会在 stderr 说一句并指向 isoflux。
★旧的 `--isoflux` 开关按名拒绝（它已是缺省）。

### isoflux 控制点：八点如何进入求解

`step(..., boundary_mode="isoflux", device=<装置卡 dict>, boundary_tol=0.02)`：

1. 这组点同时作为 `code/discharge` 的**目标曲线**（`fylite:target_r/z`）与 **isoflux 控制条件**
   （`fylite:control_r/z/w`）；线圈额定取装置卡，位置控制 C4，`seed = target`。
2. 解出的 ψ(R,Z) 与网格 · 边界轮廓 · 磁轴 · ψ_axis / ψ_bnd · 限制器 · **q 与 F** 换进
   `code/evolve` 的位形。
3. `dfsdev` 取求解器自己的边界间隙 rms；`out["extra"]` 里另有 `shape_error` · `boundary_gap_max` ·
   `coil_limit_ratio` · `n_at_coil_limit` · `diverted` · `eq_solve_s`。

★**固定位形档也能给出线圈电流**：给 `--device` 时，对工况那条固定 LCFS 解一次自由边界，只取
安匝写进输出（位形、度规、剖面一概不动，读数与不给装置卡时逐位相同），I_p 变过 5 % 才重解——
整炮约八次，平顶零次。要的是「这一炮需要多大的 PF 电流」，而不是「位形怎么随电流走」。

**代价与近似**（均为实测读数，不要据此外推）：

* 一次自由边界解约需 **7–13 s**；控制点移动超过 `boundary_tol` [m]，或 I_p 变化超过 0.05 MA，才重解。
* 八个点是**相当粗的目标**：实测平顶那组八点解出的 `shape_error` 为 0.04–0.09，间隙 rms 为 0.12–0.28 m。
* 位形改变，输运结果随之改变：同一时刻 40.5 s，固定位形 P_fus 33.1 MW，isoflux 位形 27.7 MW。
* ★★**q 已经落回常识带**（2026-09-17）。此前这一档输出的 q 整条大 2π（整炮 150 s 处 q₀ = 10.41），
  病根是 **ψ 的通量规没人声明**：求解器给出的 ψ 是整匝 Wb（COCOS 17），而读文档那一侧的缺省是
  「不声明 = 每弧度」（g-file 的规）。于是梯子的 Φ = 2π·Δψ·∫q dψ_N 大 2π、环向通量半径
  ρ_tor = √(Φ/(πB₀)) 大 √(2π)（实测边上 6.78 m，而这台机器 a = 2.16 m，不可能），而输运的
  q = 2πB₀ρ/(dψ/dρ) ∝ ρ²，于是**整条大 2π**。现在记录自己报 COCOS 号、宿主原样转给下一道门：
  ρ_tor,边 2.71 m（边界几何独立估计 2.81 m）· q₀ 1.34 · q95 3.80，对得上求解器自己那条 q（q₀ 1.28）。
  整炮（381 步，40.5 → 6170.5 s）**全程在带内**：q₀ 1.33–2.99 · q95 3.58–4.92。
* ★**两边的电流剖面仍不是同一份**（同日量的，留作读数）。平顶段自由边界解给 Δψ = −101.8 Wb ·
  q₀ = 0.97，而演化出来的 ψ 跨度 68.3 Wb · q₀ = 1.5–2.5——**差 48 %**，差在峰度（l_i）上：
  求解器的电流剖面来自它自带的解析 j_φ 族，与演化出来的那一份无关。试过把演化态反算的 p′/FF′
  投送给它（`--deliver-profile`，走 `code/steady_equilibrium`），**更远**：差 54 %、求解器 q₀ 掉到
  0.77。根子不在接线——同一条 ψ 在一维梯子上按 q = 2πB₀ρ/(dψ/dρ) 读出来是 1.3–2.5，而拿去盒内
  重解得到的是 0.895，因为梯子的 ρ(ψ_N) 来自**上一张**位形。要合成一套，得在每个时间片上把
  `code/steady_current` ↔ `code/steady_equilibrium` 迭到不动点（内核对定常态就是这么做的，
  约十轮收敛）——耦合求解器的改法，不在这一版里。页面在 q₀ 越出 0.5–4 时会标红说明。

### 限制（只作读数，不要外推）

* 缺省的 isoflux 档每步按控制点重解自由边界并替换度规；`--fixed-shape` 用工况自带的 g-file 度规，位形整段冻结——**只适用于平顶**。
* 加料执行器是**弹丸**（本工况的高斯源）：`ne_bar` 只调节其速率，气体加料置零。
* ECRH / ICRF 只能合并；NBI / LHW 不建模。
* 其余物理边界（无壁模型 · 无 ELM / 锯齿 · 给定 χ + IPB98 锚 · 固定 Z_eff 等）见
  算例的报告页（`reports/cfedr-report.html`）「物理模型清单」一节。

### 全过程：从页面到读数

这条链跑一遍就得到全部产物（目录里不留，因为都可再生）：

1. **页面编波形** —— 打开 `cfedr_studio.html`，在控制波形与 Miller 参数波形上改，按「导出控制波形」
   得到 `waveform_studio.json`（31 个节点，5.9 KB）。页面上同时给出下一步要贴的整条命令。
2. **凑齐三样输入** —— 装置描述 `device_cfedr.json` · 起步状态 `state_init.json` · 刚导出的波形。
   没有起步状态也能跑：不给 `--state` 时按模板猜一个，并在 stderr 说明换了哪几样。
3. **跑整条波形** —— 40 → 6209 s 一条命令，**缺省 isoflux 档**：位形每步按八点重解，上升段与
   下降段一路在变，平顶用 50 s 粗节拍。出**结束状态** `state_end.json` 与完整时序 `run_full.json`。
   下降段末端内核拒绝时记在 `summary.stopped` 里，已经走完的那些步照常写出。
4. **要中间态就断在那里** —— 例如 `--t1 150` 出平顶段状态，再拿它当 `--state` 接着跑；两段接力
   与一次跑完不是同一条数值路径（第二段从状态重启），读数差在 0.1 MW 量级。
5. **回页面看** —— 「导入输出 JSON」读 `run_full.json`：相位芯片 · 截面 ·
   读数 · 剖面 · 时序 · PF 波形；要单个时刻就导出那一片的 JSON 或 g-file。

★两档的读数**不是一回事**：同一条波形、同一段时间，固定位形档（`--fixed-shape`）150 s 处
P_fus 1245.8 MW · β_N 2.56 · q₀ 2.22，而缺省的 isoflux 档给 2070 MW · 3.43 · 10.41——位形换了，
输运的答案就换。整条波形只有 isoflux 档算得对；那个 q₀ 仍受 ψ 规范那条老问题影响，见上。

### 用法：命令行

**一次调用做的事**：给**装置卡 · 状态 · 控制波形**，从状态所记的时刻往后演化一段，写出
**演化完成的状态**；要整段过程，另加 `--series`。进出各归其位——状态进、状态出，波形驱动，
时序是可选的旁记。

```bash
PY=python3          # 任何 3.10+ 解释器（只用标准库）；本目录的库没有外部 C 依赖

# ① 整条波形：初始状态 + 页面导出的波形 → 结束状态 + 完整时序
#    缺省就是 isoflux：位形每步按八点重解（约 8–14 s 一次，整炮一小时上下）
$PY cfedr_core_model.py --device device_cfedr.json \
    --state state_init.json --waveform waveform_studio.json --t1 6209 \
    --dt-flat 50 --boundary-tol 0.05 --edge-ne-ref 5.474e19 1.139e20 --psi-stride 2 \
    --out state_end.json --series run_full.json

# ② 要中间态：断在平顶，再从它接着跑
$PY cfedr_core_model.py --device device_cfedr.json \
    --state state_init.json --waveform waveform_studio.json --t1 150 \
    --boundary-tol 0.05 --edge-ne-ref 5.474e19 1.139e20 --psi-stride 2 \
    --out state_flattop.json --series run_rampup.json

# 不给起步态：按模板猜一个（模板 = 脚本旁边的 state_init.json，只换时刻 · I_p · 密度标度 · 位形）
$PY cfedr_core_model.py --device device_cfedr.json \
    --waveform waveform_studio.json --t0 60 --duration 10 --out state_guess.json

# 只跑平顶那一段：位形本来不变，可以用固定位形档（快，不解自由边界）
$PY cfedr_core_model.py --device device_cfedr.json --fixed-shape \
    --state state_flattop.json --waveform waveform_studio.json --duration 600 \
    --out state_600.json --series run_flat.json

# 缺省就是 isoflux；下面这条与①②等价，只是把重解阈值写出来
$PY cfedr_core_model.py --device device_cfedr.json --boundary-tol 0.05 \
    --state state_init.json --waveform waveform_studio.json --t1 6209 \
    --dt-flat 50 --edge-ne-ref 5.474e19 1.139e20 --psi-stride 4 \
    --out state_iso.json --series run_iso.json --write-waveform waveform_iso.json

# 短段：从任一状态往后推 60 s（`--duration` 与 `--t1` 二选一）
$PY cfedr_core_model.py --device device_cfedr.json \
    --state state_flattop.json --waveform waveform_studio.json --duration 60 \
    --out state_next.json --series run_next.json
```

进出就这几格，与那四类一一对上：**进**是 `--device` 装置描述 · `--state` 状态 · `--waveform`
控制波形；**出**是 `--out` 演化完成的状态（缺省产物）· `--series` 完整时序（可选）·
`--write-waveform` 这次用的节点表（可选）。时间窗给一个就够：`--duration` 演化时长，或 `--t1`
终止时刻；起点取状态所记的时刻。给错类会按名拒绝，例如
`run_full.json 是完整时序，这一格要的是控制波形`。

★ 旧名**按名拒绝**并指路，不做静默别名：`--plan` → `--state`（工况就是还没推进过的状态）·
`--replay` → `--waveform`（PCS 回放读进来当场转）· `--input` → `--waveform` ·
`--save-state` → `--out`（缺省产物就是状态）。

其余开关只调行为、不改进出——控制节拍（`--dt` · `--dt-flat`）· ψ 网格抽样（`--psi-stride`）·
密度反馈的标定与限幅（`--edge-ne-ref` · `--fuel-gain` · `--fuel-max-factor` · `--no-density`）·
重解阈值（`--boundary-tol`）· 内核物理步长上限（`--dt-max`）——逐条见 `--help`，含义见上文各节。

#### 在 Python 中走一步

`step` 是这个工具的**最小完整调用**：一次调用对应一个内核工况，从 `state` 记录的时刻推进到
`control["time"]`。整炮即是将其置于循环中——`run_discharge` 正是该循环。

```python
import json
import cfedr_core_model as M                   # 在本目录里起 Python

state = M.init_state("state_init.json", t0=40.0)     # 起步状态
ctl = {"time": 40.5, "Ip": 10.125e6,               # 下一时刻的控制（输入名表）
       "ECRH": 20e6, "ICRF": 0.0, "NBI": 0.0, "LHW": 0.0,
       "ne_bar": 3.8e19}
state, out = M.step(state, ctl)

out["P_fusion"] / 1e6      # 33.1  MW
out["betan"]               # 0.56
out["q"][0]                # 1.69   轴上 q（剖面第一格）
len(out["Te"])             # 52     剖面点数 = 工况自带的网格
```

实测（上面这段原样运行）：首步 **P_fus 33.1 MW · β_N 0.56 · q₀ 1.69**；再推进一步到 41.0 s
得 **38.4 MW · β_t 0.372 % · n̄_e 3.93×10¹⁹ m⁻³ · Γ_fuel 8.22×10²⁰ s⁻¹**。

继续推进只需把返回的 `state` 传回去——**状态就是这份 dict**，存盘即断点：

```python
state, out = M.step(state, dict(ctl, time=41.0, Ip=10.25e6, ne_bar=3.9e19))
json.dump(state, open("break.json", "w"))      # 断点：下次 M.step(json.load(...), …) 接着走
```

几点须知：

* **不给 `boundary` 时 `dfsdev` 为 NaN**（没有指令曲线可比，宿主不编造数值）；给出八点才有读数。
* `n_roh`（剖面点数）**只在起步那一步生效**，中途更改会被按名拒绝（换网格需重映，属另一件事）。
* 自由边界档需要装置卡，八个点作 isoflux 控制点：

  ```python
  device = json.load(open("device_cfedr.json"))
  pts = [[10.32, 0.0], [8.73, 3.29], [6.48, 4.66], [5.58, 3.29],
         [5.42, 0.0], [5.56, -3.29], [6.44, -4.66], [8.70, -3.29]]
  state, out = M.step(state, dict(ctl, boundary=pts),
                      boundary_mode="isoflux", device=device, boundary_tol=0.05)
  out["dfsdev"], out["pf_current"]             # 边界间隙 rms 与解出来的线圈安匝
  ```
* 抛出的异常分三类：控制不合法（时间倒流 · NBI/LHW 非零 · 边界不闭合）抛 `ValueError`；内核
  拒绝这一步抛 `Refused`；库或门本身出错抛 `KernelError`。整炮循环捕获这三类，即为「停在这一步」。

整炮同样可以在 Python 中执行，不必经由命令行：

```python
nodes, kind = M.load_waveform("waveform_studio.json")   # 按内容认（这份是节点表；PCS 回放也收）
r = M.run_discharge("state_init.json", nodes, t0=40.0, t1=150.0,
                    dt=0.5, dt_flat=50.0, edge_ne_ref=(5.474e19, 1.139e20))
M.write_output("run.json", r["times"], r["outputs"])
r["summary"]        # {"t0": 40.0, "t1": 150.0, "steps": …, "stopped": None}
```

### 文件只有四类

| 类 | 文件 | 里面是什么 | 哪一格 |
| :--- | :--- | :--- | :--- |
| **装置描述** | `device_cfedr.json` | 线圈几何与额定安匝 · 第一壁 · TF——描述机器，不描述这一炮 | `--device` |
| **状态**（单一时间片） | `state_init.json`（目录里只留这一份初始态；平顶 / 结束态跑出来才有） | **起步态 + 物理设置**：某时刻的剖面与位形、χ 表 / 沉积表 / 度规这些设置，加上一次的内核记录与控制器状态 | `--state` 进 · `--out` 出 |
| **控制波形** | `waveform_studio.json`（页面导出；PCS 回放也可直接给 `--waveform`，读进来当场转） | **名表节点表**（十几个顶点）+ 展开规则 `meta.interp = "linear"` | `--waveform` |
| **完整时序** | 跑出来才有（`--series`），目录里不留 | 整炮每一步的输出名表 · 剖面 · PF 电流 · 逐片位形 · `meta.*` | `--series`（出） |

**四类靠内容分辨，不看文件名**（名字可以随手改，内容不会）：有 `pf_active` / `tf` 是装置；有
`t` 与 `plan` 是状态；有 `time` 与 `Ip` 是波形；有 `time` 与 `Te` 是时序。给错格会按名拒绝并说
清楚——例如 `run_full.json 是完整时序，这一格要的是控制波形`。

★**上游那两种形状读进来当场转**，并在 stderr 说一句：`code/evolve` **工况** → 状态（它就是还没
推进过的状态，`init_state` 只是包一层）· **PCS 回放** → 控制波形（节点逐条转成名表节点）。
**写出去的永远是这四类**——本目录里的 `state_init.json` 就是这么从算例工况转出来的，
`waveform_studio.json` 则是页面导出的；原来的工况与回放文件不再留在这里。

四类互不重叠：状态里没有读数，波形里没有结果，时序里没有能续跑的内核记录，装置里没有这一炮的
任何东西。页面的「导出当前片 JSON」属于第四类的一个切片（某一时刻的读数），**不是**状态文件——
它接不上 `--state`。

### 四类文件的字节形状：扁平 JSON

**只有 JSON 一种格式**：一层键 → 嵌套列表；非有限值在文件中写作 `null`（`JSON.parse` 不接受
NaN），读回时还原为 NaN。：

```python
import json, numpy as np
run = json.load(open("run.json"))
te = np.array(run["Te"])          # (nt, n)
t  = np.array(run["time"])        # (nt,)
```

**输出**（`--out run.json`）：`time`（nt）· 输出名表里的 0-D 量（各 nt）· 十五条剖面
（nt × n）· `pf_current`（nt × m）· `coil_names`（m）· ψ 组 · `extra.*` · `meta.*`。

**控制波形**（`--waveform wave.json`，或 `--write-waveform` 由回放 / 页面写出）：**节点表**——`time` 与名表
里其余标量项（`Ip` · `NBI` · `ECRH` · `ICRF` · `LHW` · `ne_bar` · `n_roh`，各 N 个节点）·
`boundary_r` / `boundary_z`（N × 控制点数）· `pf_current`（N × m）· `phase`（N，回放的相位名，
不进名表，页面拿它做相位芯片）· `meta.form = "nodes"` · `meta.interp = "linear"` · `meta.*`。

★**波形就是折线**：节点之间**每条通道都线性展开**（`controls_at`），四路加热也不例外——
零阶保持会把「60 s 10 MW → 65 s 82 MW」画成一级台阶，而页面上画的、读者看到的都是折线；
两处用同一条规则，一份输入才对得上一份输出。整炮 17 个节点约 6 KB——比逐步采样小两个量级，
而且「顶点在哪」一眼看得见。

★★**输出里的二维 ψ 一律按内核的规范写**：每步把 ψ 图仿射拉到内核演化出来的那条一维 ψ 的两端。
两档各有各的理由——固定位形档那份平衡文档是**冻结**的，端值停在起步那一刻（实测 150 s 处文档说
轴上 −22.99 Wb，内核演化出来的是 −141.44 Wb，差 118 Wb）；isoflux 档每步都是**新解出来的一张图**，
它的绝对磁通由求解器的规范定，与内核演化出来的那条 ψ 差一百多 Wb。仿射变换不动 ψ_N
（等高线位置照旧），动的是**绝对磁通**——于是同一份文件里的 ψ 图与剖面说的是同一套数。

★★**通量规：内部 COCOS 17，导出的 g-file 按 GEQDSK**。内部（内核的记录、这里的状态与时序、
输出里的 ψ 帧与 `psi_axis` / `psi_bnd`）一律**整匝 Wb、轴上取极大**，文件里写作
`meta.psi_convention = "full_flux_Wb_axis_max"`；而 GEQDSK 的 ψ 是**每弧度**，所以页面导出
g-file 时把 ψ 图与 `simag` / `sibry` 一并除以 2π（由它们差分出来的 p′ / FF′ 因此自动落在
每弧度上；F · p · q 与规范无关，不动；符号照原样——g-file 两种符号野外都有，而 `simag` /
`sibry` 就写在文件里，读者据此自己判）。★**规范必须由出图的那一侧声明**：读文档的缺省是
「不声明 = 每弧度」，把整匝的跨度当每弧度用不会报错，只会让 q 整条偏 2π——那正是上面
「q 落回常识带」那一条的病根。所以 `code/discharge` 的记录报 `cocos`，宿主原样转写进
`fylite:psi_convention`，谁也不猜。

★ψ 网格的粗细由 `--psi-stride` 定，而**两档的原生网格不同**：固定位形档是工况的 129 × 129
（stride 2 → 65 × 65），isoflux 档是求解器的 65 × 65（stride 4 → 17 × 17，stride 2 → 33 × 33）。
等高线要好看就把 isoflux 档的 stride 调到 2 或 1，代价是文件按平方涨。

**二维 ψ**（只在输出里）：**逐帧一份**，`psi_index[i] = i`——每个时间片都带位形——`psi`（帧）· `psi_index`（逐片指向帧）· `psi_r` /
`psi_z` · `axis_r` / `axis_z` · `psi_axis` / `psi_bnd` · `bnd_r` / `bnd_z` · `xpt_r` / `xpt_z`
（限制器位形为 NaN）· `diverted`。`--psi-stride 2` 把 129 × 129 抽成 65 × 65。
★`meta.psi_convention = "full_flux_Wb_axis_max"` 是**这些帧的通量规**：整匝 Wb、轴上取极大。算 ψ_N
用不着它，算 q / B_p 用得着（g-file 的规是每弧度，差 2π），所以它写在文件里而不是让人猜。
★**缺省逐帧写**：读的人不必先解索引，单独切一片出来也自带位形（页面的「导出当前片 JSON」与
g-file 都直接拿得到）。`--psi-dedup` 才把相同的帧合并存一次——固定位形档整炮只有一帧，文件小
五倍上下（实测 6 步 · stride 2：逐帧 0.53 MB，去重 0.18 MB），那是**省字节的选项**，不是缺省。
输入中带 ψ 时直接作为推进的位形，因此一份输入既是指令波形，也是可重放的位形序列。
★**抽样过的 ψ 重放不逐位相同**：stride 2 写出的输入重放时，P_fus 与原运行相差 0.02 %–0.4 %；
需要逐位重放则用 `--psi-stride 1`，或走断点（`--state`，实测逐位相同）。

---

## 二、工作台页面

**预设波形**取报告页那份算例的逐时刻平衡序列：**31 个节点**——
上升 0–60 s（1 · 3 · 5 · 7.5 · 10 · 13 · 17 · 20 · 25 · 30 · 35 · 40 · 45 · 50 · 55 s）·
平顶 60–6150 s（65 · 100 · 150 s）· 下降 6150–6210 s，两处 0-D ↔ 1.5-D 交接在 40 s 与 6170 s。
每个节点自带 **Miller 参数**（R₀ · a · κ · δ 即该炮解平衡时**给定的那组形状**，δ 取上三角形变，
ζ 与 Z₀ 为 0），控制点由这组参数按等 θ 采样得到——因此「Miller 参数演化」打开即是这一炮实际
走过的位形。I_p 与形状逐节点给定，四路加热按回放零阶保持，n̄_e 在回放节点之间线性插值。

**小截面按内容定框**：`viewBox` 每次渲染时按真正画出来的东西（第一壁 · 所有节点的控制点 · 磁轴）
算包围盒，留一成余白，并把长宽比封顶在 1 : 1.55（横向补宽、内容居中，不拉伸不裁切）。从前写死
一个能装下最外圈线圈的大框，而输入页这张不画线圈，位形只占中间一小团；现在同样的高度，位形大了
近一倍。输出页那张画线圈，框把线圈也算进去。截面里的线宽、点半径、虚线节距都按框宽算，换框不会
变成"一根头发"或"一条带子"。

`cfedr_studio.html` 是**单个文件**，双击即可打开：默认算例内置，放电数据由工具栏的「导入输出 JSON」
读模型 `--out` 写出来的那份输出 JSON。页首常驻警示「仅为 demo 演示，不可做设计参考」，
右上角是明暗风格开关（自动 / 浅 / 深）。

**输入页**（工具栏在上：导入 · 导出 · 复制 · **撤销 / 重做** · 采样节拍；下面竖排三块）

* **控制波形**：拖动圆点改值与时刻 · 空白处双击新增节点 · 双击圆点删除节点；时间轴按节点自动折断。
* **控制量节点**：表格逐项编辑。
* **磁面**（左看右编，两栏并排）——右栏 **Miller 参数波形**是编磁面的**唯一**入口：R₀ · a · κ · δ 四条曲线对时间，
  **与控制波形同一套手势**——拖圆点改那一时刻的参数、点竖线选时刻；改完立刻按参数采出这一时刻的
  八个 isoflux 点，左栏那张截面当场跟着变。δ 限在 ±0.95 · κ ≥ 0.2 · a ≥ 0.05 · R₀ ≥ 0.5。
  另有两个数据操作：**按曲线重采样**（把这一时刻的点放回它自己那条拟合曲线）与**轨迹拉直**
  （每条轨迹变成直线：中间各节点 = 起止两端按节点序线性插值）。
  左栏 **isoflux 控制点**（只看不编）：细线是每个控制点的**轨迹**（同一序号的点在各时刻之间连成的
  线段），大圆点与十字是**当前时刻**那一组点与磁轴。**这张图上没有手柄**——同一份数据两种拖法只会
  带来歧义，尤其这一炮的轨迹是**去程 + 回程**（上升段张开、下降段收回）且首尾重合，每个控制点看
  起来有两支几乎平行的线，在上面指认某一时刻的点从来不可靠。页面检出首尾重合时会把这句写在图下。
  截面上**不画 PF 线圈**，输入页也**不编线圈电流**：这一档的线圈电流是模型解出来的（固定位形档给了
  装置卡就解一组，isoflux 档每步解），看它去输出页那张位形图（按本时刻电流着色）与 PF 波形图。
  读进来的波形若自带 `pf_current`，仍原样带着走，页面只是不提供那一格编辑。
* **撤销 / 重做**（在页顶工具栏）：`↶ ↷` 或 Ctrl/⌘+Z、Ctrl/⌘+Shift+Z，最多 60 步；波形 · 节点表 · 磁面进同一条历史。

**输出页**（工具栏在上：导入 · 导出整份 / 当前片 JSON / 当前片 g-file · 播放 · 时间条）

★★排版**沿用算例报告页的看图区**：工具栏 → 相位芯片 → 截面 ∥ 读数 + 温度 / 密度剖面 →
时序信号 → PF 波形 → 其余一维通道。两处查看同一炮时，骨架一致。

* **相位芯片**：这一炮的时序梗概排成一行（相位取自**输入侧算例节点**，输出文件中没有这一项），
  点击即跳到该时刻；当前所处的一段高亮。
* **位形**（左）：ψ_N 等值线 · LCFS · O 点 · X 点，线圈按**本时刻电流**着色（红正蓝负、满额定描红边）。
* **读数 + 温度 / 密度剖面**（右）：0-D 读数格与两张常驻剖面图（T_e · T_i 一格，n_e 一格）。
* **时序信号**：0-D 时序整排在下（名字带符号：P_fus · W_MHD · β_N · β_t · β_p · l_i(3) ·
  V_loop · n̄_e · Γ_fuel …），每张图下标出这个量的**来路**。
* **PF 线圈波形**：所有线圈一张图。
* **其余一维剖面**：按 `meta.profiles` 勾选作图（温度与密度已在上方常驻，此栏不再重复）。
* **g-file 导出**：剖面由 `psi_norm` 插值到均匀 ψ 网格，p′ 与 FF′ 由中心差分给出；写出的文件
  可被 fylite 自身的 `read_gfile` 读回。

 
