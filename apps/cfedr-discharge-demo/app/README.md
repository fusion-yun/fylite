# CFEDR 堆芯模型工具与工作台（`app/`）

单文件的放电推演工具 `cfedr_core_model.py` 与单文件网页 `cfedr_studio.html`，加上跑一炮所需
的三份输入和 fylite 的动态库。**物理不在这里**——工具自己不算任何物理量，全部经 `libfylite.so`
交给 fylite 内核，它只做名表转换、控制反馈与装配。

★**目录自成一体**：工况 · 装置卡 · 波形 · 库都在这里，脚本内没有绝对路径，也不引用目录之外的
文件；下面的命令均在本目录内执行。

| 文件 | 是什么 |
| :--- | :--- |
| `cfedr_core_model.py` | 模型工具（单文件）：按名表 dict 进出，物理经 `libfylite.so` 交给内核 |
| `cfedr_studio.html` | 波形工作台（单文件，双击即开）：编控制波形与磁面出输入 JSON；导入输出 JSON 看时序 · 位形 · 剖面，导出单片 JSON 或 g-file |
| `state_init.json` | **初始状态**（`--state`）：40 s 交接态 + 物理设置（χ 表 · 沉积表 · g-file 度规） |
| `device_cfedr.json` | **装置描述**（`--device`，缺省的 isoflux 档必需）：线圈几何与额定安匝 · 第一壁 · TF |
| `waveform_studio.json` | **控制波形**：页面「导出控制波形」的 31 个名表节点 |
| `libfylite.so` | fylite 的动态库（一个真文件，无版本后缀链接）：内核（物理）与中间层（格式 · 装配）在同一个库里 |

**产物不入库**：结束状态与完整时序都是可再生的，照〈命令行〉跑一遍就有。

**目录之外只需要 Python 3.10+**，而且只用标准库——工具自己就 `ctypes` / `json` / `math` 几个，
没有 numpy，也没有别的第三方包。（网页那两道检查要 node。）

★**库只在一处**：脚本旁边的 `libfylite.so`，文件名固定。脚本不搜索上层目录、不读环境变量、
不认第二个名字——「到别处找库」一旦找错**不会报错**，它会静默地用另一份库完成整炮计算，而这种
错误只在读数上露一点。要换库，就替换这个文件。

★**这份库不链 HDF5 / netCDF**（公开仓 `bash rust/build.sh --no-io`）：`ldd` 只列出 `libgcc_s` /
`libm` / `libc`，拷到未装依赖的机器上也能跑。代价是读写 HDF5 / netCDF 的那条路径（IMAS 条目）
会得到一条按名拒绝（`built without the hdf5 feature`），而不是符号缺失。本 demo 全程走 JSON。

算这份结果的内核是哪一份，写在输出的 `meta.kernel_version` / `kernel_abi` / `kernel_built` /
`kernel_sha256` 里，页面页首显示。

---

## 一、物理：包含什么

物理全部由内核的 `code/evolve`（输运）与 `code/discharge`（自由边界平衡）给出。具体开了哪些，
由状态文件 `state_init.json` 的 `plan.settings`（61 项）决定——下表逐条列出**当前这份算例**的取值，
改这份文件即改物理。

### 输运（`code/evolve`）

| 项 | 设置键 = 值 | 说明 |
| :--- | :--- | :--- |
| **三个输运通道** | `ch-heat` `ch-density` `ch-current` = 1 | 热（T_e · T_i 两温）· 粒子（n_e）· 电流扩散（ψ）同时演化 |
| **热输运系数** | `chi_scaling = ipb98`，`chi0 = 1`，`chi_scale_*` | χ 的**幅值锚在 IPB98(y,2) 约束定标**上：按参考 I_p 15 MA · n̄_e 9.92e19 · P_loss 408 MW · W 801 MJ 标定，比例增益 `chi_scale_kp = 3`、时间常数 `chi_scale_tau = 1 s`。★**剖面形状是给定的，不是湍流模型解出来的**（`closure = 0`，未接 TGLF / 神经网络闭合） |
| **粒子输运** | `d_over_chi = 0.1`，`pinch = −0.02`，`pinch_shape = linear` | 粒子扩散系数取 χ 的 0.1 倍；内向箍缩速度随 ρ 线性 |
| **边界条件** | `edge_psin = 0.98`，`edgete` / `edgeti` / `edgene` | 三个通道在 ψ_N = 0.98 面上取 Dirichlet（值随状态走；密度边界另可由 `edge_ne_ref` 随指令缩放） |
| **台基** | `pedestal = 0` | **不含台基模型**（EPED 一类）：边界值就是上面那三个 Dirichlet |
| **L-H 阈值** | `lh_model = martin08` | Martin 2008 定标判相位；输出 `extra.lh_phase` |
| **径向网格** | `n_surfaces = 51` | 51 个磁面；剖面点数由起步那一步的 `n_roh` 定 |

### 源与汇

| 项 | 设置键 = 值 | 说明 |
| :--- | :--- | :--- |
| **α 加热** | `alpha = 1`，`ash_fraction = 0.03` | D-T 聚变 α 加热，含快 α 压强；氦灰份额 3 % |
| **辅助加热** | `sources = table`，`dep = 0`，`depw = 0.35` | 沉积由**给定的高斯表**描述（中心 ρ = 0，宽 0.35），ECRH 与 ICRF 两路功率合并后整体缩放这张表 |
| **欧姆加热** | `ohmic = 1` | |
| **轫致辐射** | `brem = 1` | |
| **同步辐射** | `synchrotron = 1` | |
| **杂质辐射** | `composition = species`，`match_impurity = Ar`，`zeff = 1.8` | 氩作配平杂质，配到 Z_eff = 1.8（固定，不演化）；线辐射走 ADAS |
| **加料** | `fuel_rate = 8.22e20 s⁻¹`，`fuel_centre = 0.7`，`fuel_width = 0.2`，`gas_rate = 0` | **弹丸**加料（高斯源，峰在 ρ = 0.7）；气体加料置零。`ne_bar` 指令调的就是这个速率 |

### 电流与平衡

| 项 | 设置键 = 值 | 说明 |
| :--- | :--- | :--- |
| **自举电流** | `bootstrap = 1` | |
| **新经典电导率** | `conductivity = redl` | Redl 定标 |
| **俘获份额** | `trapped_fraction = miller` | Miller 几何 |
| **I_p 反馈** | `ipctl = 1`，`ip_kp = ip_ki = 1`，`vloop = 0.02 V` | 由边界圈电压把 I_p 拉到指令值 |
| **度规来源** | `geometry = gfile` | 位形以平衡文档（g-file 形状）给出；缺省的 isoflux 档每次重解后替换它 |
| **自由边界平衡** | `code/discharge`：`relax = 0.1` · `position_control = c4` · `seed = target` · `tol = 1e-7` | 见〈二、算法〉 |

### 记账

`globals` · `particle_books` · `reference` · `state` = 1：全局量、粒子账、参考量、状态随记录输出，
输出名表与 `extra.*` 的读数由它们来。

## 物理：不包含什么

* **无 NBI、无 LHW**：CFEDR 没有中性束与低杂波，名表里这两路**必须为 0**，非零即按名拒绝
  （建模它们需要束能量 · 注入几何 / 频率 · n∥ 谱 · 天线位置，都不存在）。
* **无湍流闭合**：χ 是给定形状 + IPB98 锚定幅值，不是 TGLF / 回旋动理学解。
* **无台基模型**、**无 ELM**、**无锯齿**。
* **无壁与真空室涡流模型**（平衡是逐时刻的静态解，不含涡流回路）。
* **Z_eff 固定**，杂质不随放电演化。
* **无主动抽气**：密度只能加，不能主动抽。
* **ECRH 与 ICRF 不分谱**：两路合并后整体缩放同一张沉积表。

---

## 二、算法

### 时间推进

一次 `step` = 一个内核工况（`code/evolve`），从状态所记的时刻推进到 `control["time"]`。
内核内部按**自适应物理步长**走（上限 `dt_max`，缺省 25 ms），宿主只给窗口两端。
时间格式是后向欧拉；输运方程的非线性（闭合 · 快 α · 组分）由内核的耦合 Picard 迭代收敛。

整炮就是把 `step` 放进循环（`run_discharge`），控制节拍由 `--dt` 给，平顶段可换粗节拍 `--dt-flat`。

### 自由边界平衡

八个控制点同时作 `code/discharge` 的**目标曲线**（`fylite:target_r/z`）与 **isoflux 控制条件**
（`fylite:control_r/z/w`）；线圈额定取装置卡，位置控制 **C4**（电流形心设定点），`seed = target`，
欠松弛 `relax = 0.1`，收敛判据 `tol = 1e-7`。

解出的 ψ(R,Z) 与网格 · 边界轮廓 · 磁轴 · ψ_axis / ψ_bnd · 限制器 · **q 与 F** 换进 `code/evolve`
的位形。★`q` 与 `F` **由内核算**（`code/discharge` 拿到 `b0` 后按磁面几何给出，F 取真空值 R₀B₀）：
新位形下工况自带的那一份并不自洽。

**代价**：一次解约 **3.5 s**；控制点移动超过 `boundary_tol` [m] 或 I_p 变化超过 5 % 才重解，
整炮约 83 次。★**平顶段一次也不重解**——八点不动、I_p 不变，燃烧段用的是 t ≈ 150 s 定下的那份
冻结位形。`extra.eq_solve_s` 在这些步上是缓存的回显，**逐步累加会把位形开销高估约五倍**。

### 两档度规：isoflux（缺省）与 `--fixed-shape`

| 档 | 适用 | 位形怎么来 | 代价 |
| :--- | :--- | :--- | :--- |
| **isoflux**（缺省） | **整条波形**——上升 · 平顶 · 下降 | 八点作 LCFS 控制点，按上面的阈值重解 | 每次约 3.5 s；需要 `--device` |
| `--fixed-shape` | **只有平顶**（位形本来不变） | 工况自带的 g-file 度规，整段冻结 | 快；八点只作几何比对（`dfsdev`） |

★**整条波形只能走 isoflux 档**：位形随 I_p 与形状指令一路在变，拿平顶那张冻结的度规去算爬升段
就是错的，而且**错得看不出来**——输出里的等高线一动不动，读数却照常给。固定位形档里指令位形
一旦离工况那条 LCFS 超过 0.25 m，模型会在 stderr 说一句并指向 isoflux。

★固定位形档给了 `--device` 也能出线圈电流：对那条固定 LCFS 解一次自由边界，**只取安匝**写进输出
（位形 · 度规 · 剖面一概不动，读数与不给装置卡时逐位相同），I_p 变过 5 % 才重解——整炮约八次，
平顶零次。答的是「这一炮需要多大的 PF 电流」，不是「位形怎么随电流走」。

**两档的读数不是一回事**：同一时刻 40.5 s，固定位形档 P_fus 33.1 MW，isoflux 档 27.7 MW。
位形换了，输运的答案就换。

### 密度：名表中的一路控制

`P_fus ∝ n²⟨σv⟩`，密度不控就达不到燃烧点：只用工况自带的恒定加料率跑整炮，平顶密度掉到
4×10¹⁹ 量级、**P_fus 停在 54 MW**。实机上密度本就是独立一路回路（设定值弦平均 n̄_e，执行器气体 /
弹丸），CFEDR 文献给的场景规格也正是 n̄_e(t)。因此 `ne_bar` 与 I_p、四路加热并列于名表，
缺省即生效，并派生两条控制：

| 名表项 / 选项 | 作用 |
| :--- | :--- |
| `ne_bar` [m⁻³] | 弹丸加料率按「窗末平均 n_e / 目标」比例调，限幅 `fuel_max_factor`（缺省 4）× 工况加料率 |
| `edge_ne_ref=(edge, n̄_e)` · CLI `--edge-ne-ref` | 边界密度按指令线平均密度同比缩放 |

**三条须一并阅读的限制**（这一路是控制，不是预测）：

* 平顶读数是**在给定 n̄_e 之下**得到的——密度这一维是指令，不是模型的独立预测。
* 一个指令驱动**两个执行量**（加料率的动态反馈 + 边界密度的静态同比缩放）；后者是无记忆的线性
  外推，换标定就换结果。
* **加料执行器在燃烧段一直饱和**：isoflux 档整炮 383 步里 332 步顶在限幅
  4 × 8.22×10²⁰ = 3.29×10²¹ s⁻¹ 上。燃烧段密度实际由边界缩放维持，弹丸这一环处于开环。
  实现 / 指令之比：首步 1.092 · 爬升段最低 0.638 · 150 s 处 0.979 · 末步 1.260。

### 通量规：内部 COCOS 17，导出 g-file 按 GEQDSK

内部（内核记录 · 状态 · 时序 · 输出里的 ψ 帧与 `psi_axis` / `psi_bnd`）一律**整匝 Wb、轴上取极大**，
文件里写作 `meta.psi_convention = "full_flux_Wb_axis_max"`。GEQDSK 的 ψ 是**每弧度**，所以页面导出
g-file 时把 ψ 图与 `simag` / `sibry` 一并除以 2π（由它们差分出来的 p′ / FF′ 因此自动落在每弧度上；
F · p · q 与规范无关，不动）。

★**规范必须由出图的那一侧声明**：读文档的缺省是「不声明 = 每弧度」，把整匝的跨度当每弧度用
不会报错，只会让 q 整条偏 2π。所以 `code/discharge` 的记录自报 `cocos`，宿主原样转写进
`fylite:psi_convention`，谁也不猜。当前整炮（383 步，40.5 → 6171.5 s）q 全程在带内：
**q₀ 1.39–3.28 · q95 3.92–4.91**。

★**输出里的二维 ψ 一律按内核的规范写**：每步把 ψ 图仿射拉到内核演化出来的那条一维 ψ 的两端。
两档各有各的理由——固定位形档的平衡文档是冻结的，端值停在起步那一刻；isoflux 档每步是新解出来
的一张图，绝对磁通由求解器的规范定。仿射变换不动 ψ_N（等高线位置照旧），动的是**绝对磁通**，
于是同一份文件里的 ψ 图与剖面说的是同一套数。

---

## 三、功能列表

* **一步推进**：`step(state, control)`——状态 + 控制名表 → 新状态 + 输出名表。
* **整炮推进**：`run_discharge(...)`——按控制波形走完上升 · 平顶 · 下降，中途被拒不抛出，记在
  `summary["stopped"]` 里，已走完的步照常返回。
* **断点续跑**：状态就是一份纯 JSON dict，存盘即断点。实测 40 → 44 s 连续跑完，与 40 → 42 s
  存断点再续到 44 s，结果**逐位相同**。
* **自由边界平衡**：`solve_equilibrium(points, ip, device)` 可单独调用。
* **位形快照**：`equilibrium_snapshot(plan)` 取当前推进所用位形的一帧（ψ 图 · 磁轴 · LCFS · X 点）。
* **定常剖面**：`steady_profile(state)`。
* **形状工具**：`miller_boundary(node)` 按 Miller 参数（R₀ · Z₀ · a · κ · δ · ζ）采控制点。
* **上游格式当场转**：`code/evolve` **工况** → 状态；**PCS 回放** → 控制波形。四类文件**按内容
  分辨**，给错格按名拒绝并说清楚。
* **文件读写**：`write_output` / `write_waveform` / `read_waveform` / `save_state` / `load_state`。
* **网页工作台**：编波形与磁面出输入 JSON；导入输出 JSON 看相位 · 位形 · 读数 · 剖面 · 时序 ·
  PF 波形；导出整份 / 当前片 JSON / 当前片 g-file。

---

## 四、Python API

在本目录里起 Python 即可 `import cfedr_core_model as M`。

### 函数一览

| 函数 | 签名（要点） | 做什么 |
| :--- | :--- | :--- |
| `step` | `(state, control, *, dt_max=0.025, max_calls=400, boundary_mode="isoflux", device=None, boundary_tol=0.02, fuel_gain=1.0, fuel_max_factor=4.0, edge_ne_ref=None, psi_stride=1, deliver_profile=False, warm_start=False, lift_exch_cap=False) -> (state, out)` | **最小完整调用**：推进一步 |
| `run_discharge` | `(plan, nodes, t0, t1, dt=0.5, *, dt_max=0.025, dt_flat=None, dt_max_flat=None, flat_span=(150.,6150.), series_path=None, boundary_mode="isoflux", device=None, boundary_tol=0.02, density=True, edge_ne_ref=None, fuel_gain=1.0, fuel_max_factor=4.0, psi_stride=1, psi_dedup=False, deliver_profile=False, warm_start=False, lift_exch_cap_flat=False, state=None, log=print) -> dict` | 整炮；返回 `{"times","outputs","controls","state","summary"}` |
| `init_state` | `(plan, t0=None) -> dict` | 工况 / 状态文件 → 状态 dict |
| `guess_state` | `(nodes, device=None, template=None, log=print) -> dict` | 没有起步态时按模板猜一个 |
| `save_state` / `load_state` | `(path, state)` / `(path) -> dict` | 断点存 / 读 |
| `load_waveform` | `(path) -> (nodes, kind)` | 按内容认：节点表或 PCS 回放 |
| `load_device` | `(path) -> dict` | 装置卡 |
| `controls_at` | `(nodes, t) -> dict` | 节点表在 t 处**线性展开**成控制名表 |
| `nodes_from_replay` | `(replay_nodes) -> list` | PCS 回放节点 → 名表节点 |
| `miller_boundary` | `(node, n=8) -> [[R,Z],…]` | Miller 参数采 isoflux 控制点 |
| `solve_equilibrium` | `(points, ip, device, *, settings=None, pf_current=None, delivered=None) -> (eq_doc, facts, wall_s)` | 单独解一次自由边界 |
| `equilibrium_snapshot` | `(plan, facts=None, *, stride=1, bnd_points=160, psi_ends=None) -> dict` | 当前位形的一帧 |
| `steady_profile` | `(state) -> dict \| None` | 定常剖面 |
| `write_output` | `(path, times, outs, meta=None, psi_dedup=False) -> str` | 写完整时序 |
| `write_waveform` / `read_waveform` | `(path, nodes, meta=None)` / `(path) -> list` | 控制波形读写 |
| `device_meta` | `(plan) -> dict` | 装置元信息 |
| `kernel` | `() -> Kernel` | 库的 JSON 门（单例） |

**异常三类**：控制不合法（时间倒流 · NBI/LHW 非零 · 边界不闭合）抛 `ValueError`；内核拒绝这一步
抛 `Refused`；库或门本身出错抛 `KernelError`。整炮循环捕获这三类，即为「停在这一步」。

### 走一步

```python
import json
import cfedr_core_model as M

state = M.init_state("state_init.json", t0=40.0)
ctl = {"time": 40.5, "Ip": 10.125e6,
       "ECRH": 20e6, "ICRF": 0.0, "NBI": 0.0, "LHW": 0.0,
       "ne_bar": 3.8e19}
state, out = M.step(state, ctl)

out["P_fusion"] / 1e6      # 33.1  MW
out["betan"]               # 0.56
out["q"][0]                # 1.69   轴上 q
len(out["Te"])             # 52     剖面点数 = 工况自带的网格
```

继续推进只需把返回的 `state` 传回去——**状态就是这份 dict**，存盘即断点：

```python
state, out = M.step(state, dict(ctl, time=41.0, Ip=10.25e6, ne_bar=3.9e19))
json.dump(state, open("break.json", "w"))      # 下次 M.step(json.load(...), …) 接着走
```

### 自由边界档

```python
device = json.load(open("device_cfedr.json"))
pts = [[10.32, 0.0], [8.73, 3.29], [6.48, 4.66], [5.58, 3.29],
       [5.42, 0.0], [5.56, -3.29], [6.44, -4.66], [8.70, -3.29]]
state, out = M.step(state, dict(ctl, boundary=pts),
                    boundary_mode="isoflux", device=device, boundary_tol=0.05)
out["dfsdev"], out["pf_current"]      # 边界间隙 rms 与解出的线圈安匝
out["extra"]["shape_error"], out["extra"]["diverted"]
```

### 整炮

```python
nodes, kind = M.load_waveform("waveform_studio.json")
r = M.run_discharge("state_init.json", nodes, t0=40.0, t1=150.0,
                    dt=0.5, dt_flat=50.0, edge_ne_ref=(5.474e19, 1.139e20))
M.write_output("run.json", r["times"], r["outputs"])
r["summary"]        # {"t0":…, "t1":…, "steps":…, "stopped": None 或 "… 停下：…"}
r["state"]          # 演化完成的状态，可直接作下一段的 state=
```

### 几点须知

* **只收 dict**：名表是名字表，不是位置表。不提供「按 index 顺序的一串数」与 dict 的互转——
  一份数据两种写法，位置一错就是**静默错位**。
* **不给 `boundary` 时 `dfsdev` 为 NaN**（没有指令曲线可比，宿主不编造数值）。
* `n_roh`（剖面点数）**只在起步那一步生效**，中途更改按名拒绝。★与工况自带点数不同时，起步剖面
  （连同 χ 表等落在同一张径向网格上的输入）按 ρ 归一后线性重采，而**重采本身会改变起步态**：
  实测首步 P_fus 29.1 MW（52 点，不重采）· 37.1 MW（41 点）· 37.7 MW（81 点）——不同 `n_roh`
  的结果不应直接并列比较。
* `warm_start=True`（CLI `--warm-start`）**缺省关，不要随手打开**。它把上一步解出的线圈安匝作
  下一步的起点，单步快 6–18 倍，但会把爬升段带到**另一个平衡**：而燃烧段位形是冻结的，那份度规
  一路喂进新经典自举公式，**自举电流从 7.3 MA 跑到 36 MA**（等离子体总共 10.1 MA），
  **q₀ 从 2.46 塌到 0.17**，而且整炮**反而更慢**（2998 s 对 872 s）。

---

## 五、输入 / 输出名表

### 输入名表（`control`）

| 键 | 单位 | 是什么 |
| :--- | :--- | :--- |
| `time` | s | 本次推进的**终点**（内核的 `t_stop`）：必须在当前时刻之后 |
| `Ip` | A | 设置 `ip`；I_p 反馈环开时由它调边界圈电压 |
| `ECRH` · `ICRF` | W | 两路**合并**后整体缩放沉积表 |
| `NBI` · `LHW` | W | **必须为 0**（CFEDR 无此两路），非零即拒 |
| `ne_bar` | m⁻³ | 线平均密度指令：非零即开密度反馈；0 = 不控密度 |
| `n_roh` | 1 | 剖面点数：只在起步那一步作数 |
| `boundary` = `[[R,Z],…]` | m | LCFS 的 isoflux 控制点（缺省 8 点，3–24 可改） |
| `pf_current` | A·turns | PF 线圈电流（整匝安匝）：给了就作 isoflux 解的通道起始安匝 |

### 输出名表（`out`）：28 条

**12 个 0-D 量**：`P_fusion` [W] · `betat` [%] · `betan` · `betap` · `li` · `dfsdev` [m] ·
`vloop` [V] · `wmhd` [J] · `ne_bar_cmd` / `ne_bar` [m⁻³] · `fuel_rate` [s⁻¹] · `n_coil`

**15 条剖面**（每步一条，nt × n）：`rho_tor_norm` · `Te` [eV] · `Ti` [eV] · `Ne` [m⁻³] · `q` ·
`p_fus` / `p_aux` / `p_ohm` / `p_rad` [W·m⁻³] · `pressure` [Pa] · `p_fast_alpha` [Pa] ·
`j_bs` / `j_cd` [A·m⁻²] · `fpol` [T·m] · `psi_norm`

**1 组线圈**：`pf_current` [A·turns]（nt × m）与 `coil_names`

**`extra.*`**：名表之外、同一次调用就有的量——W_th · W_fast · Q · H98 · f_GW · I_bs · τ_E ·
L-H 相位 · P_rad · P_sep · 本步内核调用数 · `ip_cmd` / `p_aux_cmd` / `fuel_rate_next` ·
`shape_error` · `boundary_gap_max` · `coil_limit_ratio` · `n_at_coil_limit` · `diverted` ·
`eq_solve_s`。

### 来路：每一条由谁给出

★★★**宿主不计算任何物理量**：上表每一条，要么是门给出的事实 / 剖面，要么是自由边界解的结果，
要么是回显指令。门未给出时整条不写（0-D 量为 NaN），宿主**不**以 e(n_eT_e + n_iT_i) 之类补足
——那将是第二套物理实现。

| 来路 | 有哪些 |
| :--- | :--- |
| `kernel` 门直接给 | `P_fusion` · `betat` · `betan` · `betap` · `li` · `vloop` · `wmhd` · `ne_bar` · `fuel_rate` · 全部 15 条剖面 |
| `solver` 自由边界解给 | isoflux 档的 `dfsdev` 与 `pf_current` |
| `check` 宿主做的几何比对 | 固定位形档的 `dfsdev`（指令八点到工况 LCFS 的距离 rms） |
| `echo` 回显指令 | `ne_bar_cmd` · `n_coil` · 固定位形档未给装置卡时的 `pf_current` |

每个量的来路随输出走在 `meta.provenance` 里（页面在每张图下标出来），口径在 `meta.provenance_note`。
`meta.*` 另带 `r0` · `b0` · `limiter_r` / `limiter_z`——有了它们，一份输出文件**自带**写一份
g-file 所需的全部量。

**一条内核侧判据**（内核仓 `cargo test`
`the_two_power_densities_integrate_to_the_powers_the_step_reports`）：`p_fus_dens` 的体积积分
× α 份额必须等于本步的 `p_alpha`，`p_aux_dens` 的体积积分必须等于本步的 `p_aux`。宿主侧旁证：
t = 60 s 这一步，内核给出的 P_fus(ρ) 峰值 **1.650 MW·m⁻³**，与按 Bosch–Hale 独立计算的 1.651
之比为 **1.0000**，0-D P_fus 两者同为 476.6 MW。

---

## 六、命令行

**一次调用做的事**：给**装置卡 · 状态 · 控制波形**，从状态所记的时刻往后演化一段，写出**演化完成
的状态**；要整段过程，另加 `--series`。

```bash
PY=python3          # 任何 3.10+ 解释器（只用标准库）

# ① 整条波形：初始状态 + 波形 → 结束状态 + 完整时序（缺省 isoflux 档）
$PY cfedr_core_model.py --device device_cfedr.json \
    --state state_init.json --waveform waveform_studio.json --t1 6209 \
    --dt-flat 50 --boundary-tol 0.05 --edge-ne-ref 5.474e19 1.139e20 --psi-stride 2 \
    --out state_end.json --series run_full.json

# ② 断在平顶，再从它接着跑
$PY cfedr_core_model.py --device device_cfedr.json \
    --state state_init.json --waveform waveform_studio.json --t1 150 \
    --boundary-tol 0.05 --edge-ne-ref 5.474e19 1.139e20 --psi-stride 2 \
    --out state_flattop.json --series run_rampup.json

# ③ 只跑平顶：位形本来不变，可用固定位形档（快，不解自由边界）
$PY cfedr_core_model.py --device device_cfedr.json --fixed-shape \
    --state state_flattop.json --waveform waveform_studio.json --duration 600 \
    --out state_600.json --series run_flat.json

# ④ 不给起步态：按模板猜一个（模板 = 脚本旁边的 state_init.json）
$PY cfedr_core_model.py --device device_cfedr.json \
    --waveform waveform_studio.json --t0 60 --duration 10 --out state_guess.json
```

**进出与四类文件一一对上**：进是 `--device` 装置描述 · `--state` 状态 · `--waveform` 控制波形；
出是 `--out` 状态（缺省产物）· `--series` 完整时序（可选）· `--write-waveform` 这次用的节点表
（可选）。时间窗给一个就够：`--duration` 或 `--t1`，起点取状态所记的时刻。

**其余开关只调行为，不改进出**：

| 开关 | 作用 |
| :--- | :--- |
| `--dt` · `--dt-flat` | 控制节拍；平顶段可用粗节拍 |
| `--dt-max` · `--dt-max-flat` | 内核物理步长上限（全程 / 平顶段） |
| `--boundary-tol` | 位形重解阈值 [m] |
| `--psi-stride` · `--psi-dedup` | ψ 网格抽样 / 相同帧合并存一次 |
| `--edge-ne-ref` · `--fuel-gain` · `--fuel-max-factor` · `--no-density` | 密度反馈的标定 · 增益 · 限幅 · 关闭 |
| `--lift-exch-cap-flat` | 平顶段解除内核的交换上限 |
| `--fixed-shape` | 换固定位形档 |
| `--eq-max-iter` | 自由边界求解的轮数封顶 |
| `--warm-start` | 位形热起步（缺省关，见〈四〉须知） |
| `--deliver-profile` | 把演化态反算的 p′/FF′ 投送给求解器 |

★**旧名按名拒绝并指路，不做静默别名**：`--plan` → `--state`（工况就是还没推进过的状态）·
`--replay` / `--input` → `--waveform` · `--save-state` → `--out` · `--isoflux` 已是缺省 ·
`--cold-start` 已是缺省。

---

## 七、四类文件

| 类 | 里面是什么 | 哪一格 |
| :--- | :--- | :--- |
| **装置描述** | 线圈几何与额定安匝 · 第一壁 · TF——描述机器，不描述这一炮 | `--device` |
| **状态**（单一时间片） | 起步态 + 物理设置：某时刻的剖面与位形、χ 表 / 沉积表 / 度规，加上一次的内核记录与控制器状态 | `--state` 进 · `--out` 出 |
| **控制波形** | 名表节点表（十几个顶点）+ 展开规则 `meta.interp = "linear"` | `--waveform` |
| **完整时序** | 整炮每一步的输出名表 · 剖面 · PF 电流 · 逐片位形 · `meta.*` | `--series`（出） |

**命名规则** `<类>_<限定词>.json`，类在前：`device_` · `state_` · `waveform_` · `run_`。

**四类靠内容分辨，不看文件名**：有 `pf_active` / `tf` 是装置；有 `t` 与 `plan` 是状态；有 `time`
与 `Ip` 是波形；有 `time` 与 `Te` 是时序。给错格按名拒绝并说清楚——例如
`run_full.json 是完整时序，这一格要的是控制波形`。

四类互不重叠：状态里没有读数，波形里没有结果，时序里没有能续跑的内核记录，装置里没有这一炮的
任何东西。页面的「导出当前片 JSON」是第四类的一个切片，**不是**状态文件——它接不上 `--state`。

### 字节形状：扁平 JSON

只有 JSON 一种格式：一层键 → 嵌套列表；非有限值写作 `null`（`JSON.parse` 不接受 NaN），
读回还原为 NaN。

```python
import json, numpy as np
run = json.load(open("run.json"))
te = np.array(run["Te"])          # (nt, n)
t  = np.array(run["time"])        # (nt,)
```

**控制波形就是折线**：节点之间**每条通道都线性展开**（`controls_at`），四路加热也不例外——
零阶保持会把「60 s 10 MW → 65 s 82 MW」画成一级台阶，而页面上画的是折线；两处用同一条规则，
一份输入才对得上一份输出。整炮 17 个节点约 6 KB。

**二维 ψ**（只在输出里）：**逐帧一份**，`psi_index[i] = i`——每个时间片都带位形——`psi`（帧）·
`psi_index` · `psi_r` / `psi_z` · `axis_r` / `axis_z` · `psi_axis` / `psi_bnd` · `bnd_r` / `bnd_z` ·
`xpt_r` / `xpt_z`（限制器位形为 NaN）· `diverted`。

★**两档的原生网格不同**：固定位形档是工况的 129 × 129（`--psi-stride 2` → 65 × 65），
isoflux 档是求解器的 65 × 65（stride 4 → 17 × 17，stride 2 → 33 × 33）。等高线要好看就把
isoflux 档调到 2 或 1，代价是文件按平方涨。

★**抽样过的 ψ 重放不逐位相同**：stride 2 写出的输入重放时 P_fus 相差 0.02 %–0.4 %；需要逐位
重放用 `--psi-stride 1`，或走断点（`--state`，实测逐位相同）。

---

## 八、限制与已知偏差

**只作读数，不要外推。**

* **两档只有 isoflux 适用于整条波形**；`--fixed-shape` 只适用于平顶。
* **八个控制点是相当粗的目标**：平顶那组八点解出的 `shape_error` 为 0.04–0.09，间隙 rms
  0.12–0.28 m。
* **两边的电流剖面不是同一份**：平顶段自由边界解给 Δψ = −101.8 Wb · q₀ = 0.97，而演化出来的
  ψ 跨度 68.3 Wb · q₀ = 1.5–2.5——**差 48 %**，差在峰度（l_i）上：求解器的电流剖面来自它自带的
  解析 j_φ 族，与演化出来的那一份无关。`--deliver-profile`（投送 p′/FF′，走
  `code/steady_equilibrium`）**更远**：差 54 %、求解器 q₀ 掉到 0.77。根子不在接线——同一条 ψ 在
  一维梯子上按 q = 2πB₀ρ/(dψ/dρ) 读出来是 1.3–2.5，拿去盒内重解得到 0.895，因为梯子的 ρ(ψ_N)
  来自**上一张**位形。要合成一套，得在每个时间片上把 `code/steady_current` ↔
  `code/steady_equilibrium` 迭到不动点——耦合求解器的改法，不在这一版里。页面在 q₀ 越出 0.5–4
  时标红说明。
* **加料执行器是弹丸**（高斯源）：`ne_bar` 只调速率，气体加料置零，无主动抽气。
* **ECRH / ICRF 只能合并**；NBI / LHW 不建模。
* **下降段末端会被内核拒绝**（-23，种类态不收敛）：isoflux 档 383 步走到 6171.5 s，固定位形档
  379 步走到 6169.5 s。机制是下降段切 RF 后 L 模局部辐射塌缩。已走完的步照常写出，停在哪里记在
  `summary.stopped` 里。
* **两段接力与一次跑完不是同一条数值路径**（第二段从状态重启），读数差在 0.1 MW 量级。
* 其余物理边界见〈一、物理：不包含什么〉。

### 当前整炮读数（缺省 isoflux 档）

40.5 → 6171.5 s，383 步。150 s 处：P_fus **1552.3 MW** · β_N 2.67 · W_MHD 900 MJ
（热 812 + 快 α 88）。

计算耗时分两项（分项各自实测，端到端墙钟另含写盘等宿主开销）：**位形 292.5 s**
（83 次自由边界解，均 3.52 s）+ **输运约 61 s**。

固定位形档（`--fixed-shape`，只适用于平顶）：379 步走到 6169.5 s，150 s 处 P_fus **1245.9 MW** ·
β_N 2.56 · W_MHD 826 MJ。两档差在度规——位形每步重解 vs 整段冻结，不是同一个问题的两个答案。

---

## 九、工作台页面

`cfedr_studio.html` 是**单个文件**，双击即开：默认算例内置，放电数据由工具栏的「导入输出 JSON」
读 `--series` 写出的那份。页首常驻警示「仅为 demo 演示，不可做设计参考」，右上角是明暗风格开关
（自动 / 浅 / 深）。

**预设波形**取算例的逐时刻平衡序列：**31 个节点**——上升 0–60 s（1 · 3 · 5 · 7.5 · 10 · 13 · 17 ·
20 · 25 · 30 · 35 · 40 · 45 · 50 · 55 s）· 平顶 60–6150 s（65 · 100 · 150 s）· 下降 6150–6210 s，
两处 0-D ↔ 1.5-D 交接在 40 s 与 6170 s。每个节点自带 **Miller 参数**（R₀ · a · κ · δ，δ 取上三角
形变，ζ 与 Z₀ 为 0），控制点由这组参数按等 θ 采样得到。

### 输入页

工具栏：导入 · 导出 · 复制 · **撤销 / 重做**（`↶ ↷` 或 Ctrl/⌘+Z、Ctrl/⌘+Shift+Z，最多 60 步）·
采样节拍。下面竖排三块：

* **控制波形**：拖圆点改值与时刻 · 空白处双击新增节点 · 双击圆点删除节点；时间轴按节点自动折断。
* **控制量节点**：表格逐项编辑。
* **磁面**（左看右编）——右栏 **Miller 参数波形**是编磁面的**唯一**入口：R₀ · a · κ · δ 四条曲线
  对时间，与控制波形同一套手势；改完立刻按参数采出这一时刻的八个 isoflux 点，左栏截面当场跟着变。
  δ 限在 ±0.95 · κ ≥ 0.2 · a ≥ 0.05 · R₀ ≥ 0.5。另有**按曲线重采样**与**轨迹拉直**两个数据操作。
  左栏 **isoflux 控制点**只看不编：细线是每个控制点的轨迹，大圆点与十字是当前时刻那组点与磁轴。
  ★**这张图上没有手柄**——同一份数据两种拖法只会带来歧义，尤其这一炮的轨迹是去程 + 回程且首尾
  重合，在上面指认某一时刻的点从来不可靠；页面检出首尾重合时会把这句写在图下。
  截面上不画 PF 线圈，输入页也不编线圈电流：这一档的线圈电流是模型解出来的。

★**小截面按内容定框**：`viewBox` 每次渲染按真正画出来的东西（第一壁 · 所有节点的控制点 · 磁轴）
算包围盒，留一成余白，长宽比封顶 1 : 1.55（横向补宽、内容居中，不拉伸不裁切）。截面里的线宽、
点半径、虚线节距都按框宽算，换框不会变成「一根头发」或「一条带子」。

### 输出页

工具栏：导入 · 导出整份 / 当前片 JSON / 当前片 g-file · 播放 · 时间条。排版沿用算例报告页的
看图区：工具栏 → 相位芯片 → 截面 ∥ 读数 + 温度 / 密度剖面 → 时序信号 → PF 波形 → 其余一维通道。

* **相位芯片**：时序梗概排成一行（相位取自输入侧算例节点），点击跳到该时刻，当前段高亮。
* **位形**（左）：ψ_N 等值线 · LCFS · O 点 · X 点，线圈按本时刻电流着色（红正蓝负、满额定描红边）。
* **读数 + 剖面**（右）：0-D 读数格与两张常驻剖面图（T_e · T_i 一格，n_e 一格）。
* **时序信号**：0-D 时序整排在下，每张图下标出这个量的**来路**。
* **PF 线圈波形**：所有线圈一张图。
* **其余一维剖面**：按 `meta.profiles` 勾选作图——输出名表增加一行，页面即多出一格。
* **g-file 导出**：剖面由 `psi_norm` 插值到均匀 ψ 网格，p′ 与 FF′ 由中心差分给出；写出的文件
  可被 fylite 自身的 `read_gfile` 读回。
