# EAST 自由边界平衡演化（PF/IC 电流给定 · 被动结构电流给定或感应自洽）

给一份初始平衡（G-EQDSK，附 A-EQDSK 更好）、此后各时刻的等离子体电流 $I_p(t)$ 与 PF / IC 线圈的实测单匝电流，
按时间推进**自由边界平衡**；再把一组点状电流源（真空室、被动板等被动结构，给坐标与电阻）放进来，
算它们对位形演化的影响，并报告**每个电流源处的极向磁通**。

一个文件 `fb_evolution.py`，只用 Python 标准库（≥ 3.8）与一份 `libfylite.so`；所有物理计算经库里内核的文档门。

```bash
python fb_evolution.py prepare DATA_DIR -o in/case.json                 # g/a/mat → 一份输入文档
python fb_evolution.py wall    in/case.json -o out/wall.json            # 被动丝回路的 L/R 时间（选步长）
python fb_evolution.py geometry --case in/case.json -o out/geometry.json # 截面几何：PF / IC 线圈、限制器（装置事实）
python fb_evolution.py initial in/case.json -o out/initial.json         # 校验：t0 的初始平衡 vs g/a 文件
python fb_evolution.py run     in/case.json --passive zero       -o out/run_zero.json    --gfile-dir out/g_zero
python fb_evolution.py run     in/case.json --passive induced    -o out/run_induced.json --gfile-dir out/g_induced
python fb_evolution.py run     in/case.json --passive prescribed --passive-file I.json -o out/run_prescribed.json
python fb_evolution.py compare out/run_*.json -o out/compare.json
# 双击 fb_evolution.html → 把 out/run_*.json（可几份一起）、initial.json、compare.json 拖进去（见 §十）
```

★实验数据与结果**不入仓**：数据目录、输出路径都由调用方给（`.gitignore` 兜住 `in/ out/ log/`）。

---

## 一 · 要回答的两个问题

1. **给定电流的位形演化**：初始平衡 + 之后每个时刻的 $I_p$、14 个 PF 线圈与 2 个快控线圈（IC1、IC2）的单匝电流
   → 每个时刻的自由边界平衡（ψ(R,Z)、边界、磁轴、q、$l_i$、$\beta_p$）。
2. **加入被动结构**：`vv_position` 给出的每个点当作一根环向电流丝（被动结构），`VVres` 给出每根丝的环向电阻。
   输出含被动结构影响的平衡演化，以及**每根丝处的极向磁通**。

数据说明里说被动结构电流是「给定」的输入，但数据里**没有**被动电流的时间序列——只有位置与电阻。
所以本工具两种都做：

| `--passive` | 被动丝电流 | 用途 |
| :--- | :--- | :--- |
| `zero` | 恒为零（给定） | 「没有被动电流」的基准；丝仍在，报告各丝处的磁通 |
| `prescribed` | 由 `--passive-file` 给定的时间序列 | 调用方有被动电流（测量或别的代码算的）时用 |
| `induced` | 回路方程自洽算出 | 数据里有电阻、没有电流时唯一有物理依据的做法 |

---

## 二 · 物理模型

### 2.1 自由边界平衡

每个时刻解 Grad–Shafranov 方程

$$\Delta^*\psi = -\mu_0 R\, j_\phi,\qquad j_\phi = \lambda\left(R\,p'(\psi_N) + \frac{FF'(\psi_N)}{\mu_0 R}\right),$$

$\lambda$ 每一轮由 $\int j_\phi\,dA = I_p(t)$ 定。ψ 在计算盒上 = 等离子体电流的磁通（盒边界由自由空间格林函数给）
\+ 外部导体的磁通

$$\psi_\mathrm{ext}(R,Z) = \sum_c G_c(R,Z)\, I_c + \sum_k G_k(R,Z)\, I_k ,$$

$c$ 走线圈通道（安匝，按通道的元素权重摊到各线圈元素，元素再分成 4×4 根细丝取格林函数平均），$k$ 走被动丝。
边界格子按磁通所占份额带电流（内核的「边规则」），于是逐步差分的等离子体磁通没有网格量化的抖动。

### 2.2 被动丝的回路方程（`induced`）

每根丝是一个独立的环向回路：

$$R_k I_k + \frac{d\Psi_k}{dt} = 0,\qquad
\Psi_k = \sum_{j\in\text{丝}} M_{kj} I_j + \sum_{c\in\text{线圈}} M_{kc} I_c + \Psi^{\mathrm{p}}_k ,$$

$M$ 是丝与丝、丝与线圈元素之间的互感（各自截面分成 8×8 根细丝平均；对角是自感），$\Psi^\mathrm{p}_k$ 是等离子体电流在丝 $k$
处的磁通——与构造 $\psi_\mathrm{ext}$ 的**同一套**格林响应反过来读（互易），所以耦合与外场不是两种约定。
时间上用隐式欧拉：

$$\left(\frac{M_{vv}}{\Delta t} + R\right) I^{n+1} = \frac{M_{vv}}{\Delta t} I^{n}
 - \frac{M_{vc}\,(I_c^{n+1} - I_c^{n})}{\Delta t} - \frac{\Psi^{\mathrm{p},n+1} - \Psi^{\mathrm{p},n}}{\Delta t}.$$

$\Psi^{\mathrm{p},n+1}$ 取决于这一步的平衡，而平衡又取决于丝电流：内核在**同一次**自由边界迭代里每一轮都重算一次回路
（「内耦合」），所以壁在等离子体找平衡的过程中就回应它的移动。线圈通道是电流驱动（给定），它们的电阻不进方程。

### 2.3 竖直位置

实测线圈电流的**回放**没有竖直控制：真实的竖直控制就在实测的快控线圈电流里，但它是对真实等离子体调的，
对模型里的等离子体只是一个固定的外场。于是：

* 不钉位置时，模型的自由边界迭代在这组电流自己的（竖直不稳定的）平衡附近上下跳，不收敛；
* 多个壁时间之后，等离子体会在模型里漂向真空室。

本工具用内核的**虚拟竖直线圈对**（盒外一对反向圆环）把电流中心 $Z_c$ 钉在 $Z_\mathrm{anchor}$（比例保持：
$I_\mathrm{fb} = -g\,|I_p|\,(Z_c - Z_\mathrm{anchor})$，$g = 8$）。缺省的 $Z_\mathrm{anchor}$ 是 t0 处**线圈对不出力**的高度
（对 $Z_\mathrm{anchor}$ 二分 $I_\mathrm{fb}=0$），即 t0 的平衡是这组电流自己的平衡；之后线圈对的电流就是
「给定电流在这个高度留下的竖直力缺口」——模型与真实竖直控制之间的差。输出里报成两样：$I_\mathrm{fb}/I_p$，
与线圈对在磁轴处补的径向场 $B_{R,\mathrm{fb}}$（线圈对的几何取内核的那一对）。

### 2.4 剖面随时间怎么变（假设，可选）

| `--profile` | 做法 | 为什么 |
| :--- | :--- | :--- |
| `fixed`（缺省） | $p'(\psi_N)$ 与 $FF'(\psi_N)$ 的**形状**取初始 g-file、整段不变，幅度每步按 $I_p(t)$ 重定 | 数据里没有剖面演化的任何信息；这是唯一不引入额外输入的做法。$\beta_p$、$l_i$ 于是只随几何变 |
| `efit-trend` | 每 `--segment` 秒一段，段首重定形状 $p' \to h\,p'_g$、$FF' \to \kappa\,h\,FF'_g$、$h = e^{\gamma(1-\psi_N)}$（$\kappa<0$ 即反磁的 $FF'$，$\beta_p$ 才能越过电流全由 $p'$ 承载时的上限），使同尺 $\beta_p$、$l_i(1)$ 等于 t0 的 g-file 值加上 magdata 的 EFIT 迹相对 t0 的**变化量** | 让 $\beta_p + l_i/2$（径向力平衡）跟着参考走，看剖面假设对位形的影响有多大。★EFIT 迹是 EFIT 的结果，不是测量；段首形状跳变产生的感应电动势不进回路方程 |

---

## 三 · 流程与内核的门

| 命令 | 做什么 | 门 |
| :--- | :--- | :--- |
| `prepare` | 读 g-file（库里的读者）、a-file、三个 `.mat`（标准库读 MAT v5）→ `case.json` | `fylite_runtime_gfile_json` |
| `wall` | 被动丝回路 $M\,\dot I + R I = 0$ 的本征时间 $\tau_k$、电阻复核 | `code/wall` |
| `initial` | t0：二分找线圈对不出力的 $Z_c$ → 一次自由边界解 → 与 g/a 文件同尺比较；另用 a-file 里 EFIT 拟合的线圈电流再解一次作诊断 | `code/forward` · `code/summary` |
| `run` | 整段一次（`efit-trend` 分段）电流驱动演化，每步留 ψ；逐步后处理 | `code/evolve_free_boundary` · `code/summary` |
| `compare` | 各次 run 之间（磁轴移动、边界距离、$l_i$ 与 $\beta_p$ 之差、丝处磁通之差）与 EFIT 参考迹之间 | —— |

`run` 用到内核 `code/evolve_free_boundary` 的两个 opt-in 设定（缺省关、逐位不变）：`keep_psi = 1` 让门留下每一步的
ψ 图与电流标度 `jc`，`zc_anchor` 把每次解的虚拟线圈对钉在给定高度。

**同一把尺**：$\beta_p$、$l_i$、$W$、$V$ 对任何一份平衡（本工具的、输入 g-file 的）都用同一段积分量：

$$\beta_p = \frac{2\mu_0\langle p\rangle_V}{\bar B_{pa}^2},\quad l_i(1) = \frac{\langle B_p^2\rangle_V}{\bar B_{pa}^2},\quad
l_i(3) = \frac{2\int B_p^2\,dV}{\mu_0^2 I_p^2 R_\mathrm{geo}},\quad \bar B_{pa} = \frac{\oint B_p\,dl}{\oint dl},\quad
W = \tfrac32\int p\,dV ,$$

$B_p = |\nabla\psi|/R$（ψ 为 Wb/rad；图是 Wb 还是 Wb/rad 由安培环路 $\oint B_p\,dl/\mu_0$ 与 $I_p$ 之比判）。
$q$、边界、形状取自 `code/summary`（$F$ 的边值 $= B_0R_0$ 取输入 g-file 的 `bcentr·rcentr`，即假定环向场线圈电流不变）。

---

## 四 · 线圈与被动丝的映射

**PF**：装置事实里的 12 个 PF 通道（EFIT 的 BRSP 次序：PF1 PF3 PF5 PF7+9 PF11 PF13 PF2 PF4 PF6 PF8+10 PF12 PF14；
PF7+9、PF8+10 各是一对串联线圈）。通道的安匝

$$A_c = \sum_{j\in c} N_j\, I_{\mathrm{coil}(j)},$$

$N_j$ 是元素匝数，$I$ 是 magdata 该线圈那一列的单匝电流——串联的两个线圈各用各自那一列（两列本应相等，实测略有出入，
这样取等于按匝数加权平均）。这与反演链把罗氏线圈读数乘匝数得 BRSP 安匝是同一个约定。

**IC**：装置事实里 IC1 / IC2 带 `function = b_field_fb`，内核的线圈读者会跳过它们；本工具在交给内核的装置文档里
去掉这一标记，各接成一个单元素通道（安匝 = 匝数 × 单匝电流）。几何取装置事实；`--ic-rz R,Z` 可改
（数据附的几何示意图与装置事实的 IC 位置不完全一致，见 §八）。

**被动丝**：按文件次序把点串成轮廓（相邻间距大于 `--contour-gap` 就断开，首尾够近的轮廓闭合）。每根丝是一条沿壁的
平行四边形截面：长 $\ell_k$ = 到前后两丝距离之半的和，方向 = 前后两丝连线，厚

$$t_k = \frac{2\pi R_k\,\rho}{\mathcal R_k\,\ell_k},$$

$\mathcal R_k$ 是 `VVres` 的第 $k$ 个值。于是内核的元件电阻 $\rho\,2\pi R_k/(\ell_k t_k)$ **逐丝恰好等于** $\mathcal R_k$
（`wall` 命令复核这一条）；$\rho$（缺省 0.74 μΩ·m，不锈钢，`prepare --rho` 可改）只决定截面的形状，进自感的对数项，
不进电阻。★由此也读出 `VVres` 的含义：每根丝（一段壁）的**环向回路电阻** [Ω]——按 0.74 μΩ·m 反推出来的厚度落在
毫米级、与真空室壁厚同量级（`wall` 输出 `thickness_m`），支持这个读法。

- `induced`：全部丝进 `pf_passive/efb_vv` 一组（电阻率 $\rho$），电流由回路方程算；
- `zero` / `prescribed`：全部丝当成单匝线圈、各一个通道，电流给定（`zero` 恒零）。

---

## 五 · 输入与输出

**数据目录**（`prepare`）：`g*.*`（G-EQDSK）、同名 `a*.*`（可缺）、`*_magdata.mat`（`pf` [nt, 16]、`ip`、`t`、
`betap`、`li`）、`vv_position.mat`（`r_vv`、`z_vv` [m]）、`VVres.mat`（电阻 [Ω]）。magdata 的 `t` 从 0 起：约定为相对
g-file 时刻的偏移（`prepare` 记下 `ip[0]` 与 a-file 实测 $I_p$ 之差作核对）。

**`--passive-file`**（`prescribed`）：JSON `{"t": [...], "current": [[每根丝的电流 A] × nt]}`，或本工具一次 `run` 的输出
（取其 `sources.current_A`——例如把 `induced` 的结果当给定电流回放，应当逐步复现 `induced`）。按时刻线性插值。

**`run` 的输出 JSON**：

| 键 | 内容 |
| :--- | :--- |
| `time` · `time_abs` | 相对 / 绝对时刻 [s] |
| `scalars` | 每步：`ip` · `axis_r/z` · `zc` · `psi_axis/psi_boundary` [Wb] · `q0` · `q95` · `li1` · `li3` · `betap` · `w_mhd_J` · `volume_m3` · `kappa` · `delta_upper/lower` · `r_geo_m` · `a_minor_m` · `fb_amp` · `pair_br_at_axis_T` · `bnd_kind` · `xpt_r/z` · `gs_state`（2 = 收敛）· `circuit_residual` · `passive_total_A` · `efit_li` · `efit_betap`（参考迹） |
| `boundary` | 每步的最外闭合磁面 [[R, Z], …] |
| `sources` | 每根丝：`r` · `z` · `resistance_ohm`；丝串成的轮廓 `contours` = [[首, 尾, 是否闭合], …]（与 `wall` 同一条规则）；每步（[步][丝]）：`current_A`、`psi_total_Wb`、`psi_external_Wb`、`psi_plasma_Wb`、`psi_gfile_Wb_per_rad` |
| `limiter` | 输入 g-file 的限制器 `{r, z}` [m]（结果页画截面用） |
| `grid` · `psi_last_Wb` | 计算盒的 `r`、`z` [m]；**最后一步**的 ψ 图 [Wb]，平铺为 `psi[i·nz + j]`（i 走 R、j 走 Z）——逐步的图不进 JSON，用 `--gfile-dir` |
| `channels` | 14 个通道（12 PF + IC1 + IC2）的名字与每步安匝 |
| `geometry` | 截面几何，取装置事实（见下） |
| `door` | 门的设定、事实与说明（收敛计数、线圈对是否撑着等） |

`initial` 的输出另带 `reference.boundary`（g-file 的 `rbbbs`/`zbbbs`）与 `limiter`；两样都是结果页画 t₀ 截面用的
（2026-09-22 之前写出的 `run` / `initial` 没有这几个键：结果页改从一起拖入的 `in/case.json` 取，也没有就照说缺）。
★没有 X 点的步（限制器位形里的一部分）`xpt_r/z` 没有值：现在的输出是严格 JSON、写成 `null`；更早的文件里是裸 `NaN`，结果页读时照样换成 `null`。

**`geometry` 块**（`run` · `initial` · `prepare` 的输出都带；`geometry` 命令单独写一份）——截面要画的几何，全部取这一炮、这条测量链
解析出的**装置文档**（与交给内核的是同一份），不补任何尺寸：

| 键 | 内容 |
| :--- | :--- |
| `source` | 装置文档的 `@id`、`_basis`、炮号、测量链、适用炮号范围、PF 与壁两份事实页的出处 |
| `pf_coils` | PF 线圈的每个元素：`name` · `channel`（与 `channels.names` 同名，PF7+PF9、PF8+PF10 两个元素同一通道）· `channel_index` · 中心 `r`、`z`，宽 `dr`、高 `dz` [m] · `turns` · 平行四边形角 `a1`、`a2` |
| `ic_coils` | IC1 / IC2：**这一次实际用的** `r`、`z`（`position_from` = `facts` 或 `--ic-rz`）、`facts_rz`（装置事实的原位置）、`dr`、`dz`、`turns`；`geometry --ic-figure-rz R,Z` 另记 `figure_rz`（数据附图上的位置，只作记录、不用） |
| `limiter` | 装置事实里的限制器轮廓 `{r, z}` |
| `channels` | 通道名（与 `run` 的 `channels.names` 同序） |
| `filament_contours` | 给了 case 才有：丝串成的轮廓 [[首, 尾, 是否闭合], …] |

```bash
python fb_evolution.py geometry --shot 115672 [--chain east] [--ic-rz R,Z] [--ic-figure-rz R,Z] [--case in/case.json] -o out/geometry.json
```

写的是 `@type: fylite:EastFreeBoundaryGeometry`、只含这一块——2026-09-22 之前写出的 run / initial 没有 `geometry`，
把它和那些文件一起拖进结果页，就不必为了画线圈重跑演化。`--ic-rz` 要与那几次 run 用的一致（run 的 `options.ic_rz` 在页面里优先）。

丝处磁通的三种：$\Psi^\mathrm{tot}_k = \sum_j M_{kj}I_j + \Psi^\mathrm{p}_k$（丝 $k$ 截面平均的磁链，Wb，含它自己电流的
自感项）；$\Psi^\mathrm{ext}_k$ = 去掉自感项 $M_{kk}I_k$；$\Psi^\mathrm{p}_k$ = 只有等离子体的。`psi_gfile_Wb_per_rad`
$=\sigma\,\Psi^\mathrm{tot}_k/2\pi$，$\sigma = \pm1$ 取成与输入 g-file 同一符号约定，可以与 g-file 的 `psirz` 直接比。

**`--gfile-dir`**：每 `--gfile-every` 步一份 G-EQDSK（内核的 65×65 盒；ψ 为 Wb/rad、与输入 g-file 同号；`pres`、`fpol`、`qpsi`
来自 `code/summary`，`pprime`、`ffprim` 由 $p$、$F^2/2$ 对 ψ 差分；边界、限制器照写）。

---

## 六 · 选项

| 选项 | 缺省 | 说明 |
| :--- | :--- | :--- |
| `--passive` | `induced` | `zero` · `prescribed` · `induced` |
| `--passive-init` | `ramp` | `induced` 在 t0 的丝电流：`zero`，或 `ramp` = 匀速变化下的稳态解 $I_k = -\dot\Psi_k/\mathcal R_k$（先跑 `--ramp-window` 秒零被动电流的短演化取斜率）。从零起步会多出一段约 $3\tau_1$ 的暂态 |
| `--zc-anchor` | `auto` | `auto`（t0 处线圈对不出力的高度）· 一个数 [m] · `none`（不钉，见 §2.3） |
| `--profile` · `--segment` | `fixed` · 0.02 | 见 §2.4 |
| `--t-start` · `--t-end` · `--stride` · `--substeps` | 全段 · 1 · 1 | 取 magdata 的哪一段、每隔几点、每段再细分几步（线性插值）。步长的依据：`wall` 给的 $\tau_k$；隐式欧拉对 $\tau \gg \Delta t$ 的模式准确 |
| `--relax` · `--tol` · `--max-iter` · `--grid` | 0.1 · 1e-9 · 12000 · 装置的 65 | 自由边界迭代；0.1 比内核缺省 0.3 稳 |
| `--ic-rz` | 装置事实 | IC 线圈中心 `R,Z`（上 +Z、下 −Z） |
| `--gfile-dir` · `--gfile-every` | —— · 1 | 逐步写 G-EQDSK |

---

## 七 · 库

要一份 `libfylite.so`：

* 内核带 `code/evolve_free_boundary` 的 `keep_psi` 与 `zc_anchor`（内核仓 2026-09-22 起；更早的库上 `run` 会因为记录里没有
  `psi_t` 而报错）；
* **内部版**构建（编进了 EAST 的装置事实：线圈、通道映射、限制器、计算盒）。公开版没有 EAST，`Lib.device` 会按名报出库里有哪些装置。

缺省找本文件旁边的 `libfylite.so`（一个位置，不搜索）；`--lib` 显式给另一份。取法：本仓 `bash rust/build.sh`
（`FYLITE_KERNEL=` 指向带上述设定的内核检出）后在 `python/fylite/_lib/` 下。

---

## 八 · 局限与没做到的

- **竖直控制是虚拟的**（§2.3）：线圈对的电流是结果的一部分，读作「给定电流与模型之间的竖直力缺口」；它大，说明
  那一段模型与实际不自洽（线圈电流测量、线圈与壁的几何、剖面假设、t0 的被动电流都可能是原因）。
- **剖面是假设**（§2.4）：`fixed` 下 $\beta_p$、$l_i$ 不跟实验走；`efit-trend` 跟的是 EFIT 的结果，且只有两个自由度。
  与 EFIT 迹的一致只是自洽性检查，不是真值。
  `efit-trend` 的形状族在 $\beta_p$ 升高时靠加大反磁的 $FF'$ 实现，到一定程度 $R\,p'$ 与 $FF'/\mu_0R$ 两项在截面上几乎相消，
  内核按名拒绝（归一化的总电流接近零）；这时先退回上一段的形状，再不行演化就停在那一段的起点，已算的部分照常写出（`door.notes` 记下）。
  分段时另有守门：一段里有既没收敛也没定住的步、或磁轴一步跳 5 cm 以上（平衡换了分支），这一段丢掉、演化停在它的起点。
- **t0 的被动电流**不知道：`zero` 与 `ramp` 是两种假设；a-file 里没有被动电流可以对。
- **IC 线圈几何**：装置事实与数据附图的位置不完全一致；缺省用装置事实，`--ic-rz` 可以换。输出的 `geometry.ic_coils` 记着这一次用的是哪个；
  `geometry --ic-figure-rz` 可把附图位置一并记下（只作记录），结果页把它画成虚框。
- **被动丝截面**是由电阻与假定的 $\rho$ 反推的条带；截面只进自感的对数项。丝之间的「空隙」按条带相接处理。
- **没有做**：被动结构电流作为未知量拟合（需要磁测量）；非轴对称的涡流路径；环向场线圈电流的变化；
  等离子体电阻与环电压（$I_p$ 是给定的）。
- 数据说明原本把这个任务交给另一套代码；这里是 fylite 自己内核的实现，输出格式按本工具的约定。

---

## 九 · 测试

```bash
python3 -m pytest apps/east-free-boundary-evolution/test -q
# 结果页：把页面脚本在极小 DOM 垫片里真跑一遍，喂输出目录里的文件（结果不入仓，所以要调用方给）
node apps/east-free-boundary-evolution/test/smoke.mjs apps/east-free-boundary-evolution/fb_evolution.html \
    OUT/run_zero.json OUT/run_induced.json OUT/run_prescribed.json OUT/run_induced_init0.json \
    OUT/run_induced_efit-trend.json OUT/initial.json OUT/compare.json OUT/geometry.json [IN/case.json OUT/wall.json]
```

页面检查按每个文件的 `@type` 走各自的断言（演化页逐步走：截面、十二张时间迹、被动丝、热图、步导航与键盘；初始态页；比较页），
给了两份以上 run 时另查叠加与「主 − 叠加」的差；比较页上页面自己算的磁轴移动与边界距离要与 `compare` 写下的逐位对上；
最后把全部文件当一次拖入再载一遍，并查按名拒收。垫片只认 HTML 里真有的 id，页内目录与各节一一对上。

只用合成数据：MAT v5 读者（压缩与不压缩）、丝的轮廓与条带（电阻逐丝复现）、通道安匝的折算、同尺积分（圆截面环的
体积与安培环路）、边界距离、虚拟线圈对的场；库在（本目录或 `$FYLITE_APP_LIB`）就再测一次 G-EQDSK 写出 → 库的读者读回。

---

## 十 · 结果页 `fb_evolution.html`

单个 HTML 文件，不加载任何外部资源、不上传（与 `east-kinetic-reconstruction/kinetic_recon.html` 同一套画法）。
**双击打开** → 「结果」页签 → 「导入结果 JSON」（可多选），或把输出目录里的几份文件**一起拖进页面**。
「原理与过程」页签不要结果也能读：算例、式 (1)–(10)（GS、外部磁通、回路方程 $R_k I_k + \dot\Psi_k = 0$ 与隐式欧拉、
三种丝处磁通、虚拟线圈对 $I_\mathrm{fb} = -g|I_p|(Z_c - Z_\mathrm{anchor})$、`efit-trend` 的形状族、同尺积分、通道安匝、条带厚度）与本页怎么读。

按 `@type` 分页，别的一律按名拒收（说出它是什么、本页收哪几种）：

| 文件 | `@type` | 页 |
| :--- | :--- | :--- |
| `run_*.json` | `fylite:EastFreeBoundaryEvolution` | **演化**（可几份叠加） |
| `initial.json` | `fylite:EastFreeBoundaryInitial` | **初始态** |
| `compare.json` | `fylite:EastFreeBoundaryComparison` | **比较** |
| `geometry.json` | `fylite:EastFreeBoundaryGeometry` | 辅助：装置事实里的 PF / IC 线圈、限制器（旧的 run / initial 没有 `geometry` 块时用） |
| `in/case.json` | `fylite:EastFreeBoundaryCase` | 辅助：g-file 边界、限制器（g-file 的）、轮廓断开距离 |
| `wall.json` | 没有；按形状认（`tau_s` + `contours`） | 辅助：丝回路最慢的 10 个 L/R 时间 $\tau_k$、并联电阻、条带厚度 |

**演化页**

- **步**：滑条、◀ ▶、键盘 ← →（Shift 一次 10 步，Home / End 到两端）、点任一张时间迹跳到那一时刻、「播放」。
  状态行：$t - t_0$ 与绝对时刻、$I_p$ 对目标、限制器 / X 点位形、GS 状态（收敛 · 定住 · 都不是）与残差、迭代数、
  $I_\mathrm{fb}/I_p$、$B_{R,\mathrm{fb}}$、$\sum I_k$、$\max|I_k|$、$l_i(1)$、$\beta_p$、$q_{95}$。
- **截面**（等比例，量程含线圈）：PF 线圈（事实的 $dR \times dZ$ 矩形，按所属通道这一步的安匝着色，色标与丝的分开）、
  IC 线圈（金框，位置取这一次实际用的；附图位置有记录时画成金色虚框、标「未用」）、限制器、计算盒、158 根丝按轮廓连起来并按这一步的电流着色（发散色标，零 = 底色，量程 = 整段最大 $|I|$，
  各步可比）、这一步的边界与之前各步的淡迹、磁轴与整段轨迹、X 点。ψ 等值线**只在最后一步**画（`psi_last_Wb`），
  其余各步照说。线圈与限制器取 `geometry` 块（结果文件的 → 拖入的 `geometry.json`；限制器再退到 g-file 的）；都没有就不画，
  并写明缺什么、用哪条命令补。
- **时间迹**（十二张）：$I_p$ 对目标与安培环路复核；磁轴 $R$；磁轴 $Z$ 与 $Z_c$ 对 $Z_\mathrm{anchor}$；$I_\mathrm{fb}/I_p$（±1 % = 门的 `fb_tol`）
  与 $B_{R,\mathrm{fb}}$——标明是建模缺口；$\sum I_k$ 与 $\max|I_k|$；GS 残差（没收敛的步打点）与迭代数；$l_i(1)$、$\beta_p$ 对 EFIT 迹
  （`efit-trend` 的分段画竖线）；$q_{95}$ 与 $q_0$。限制器位形的时段涂浅灰。
- **被动丝**：这一步每根丝的电流与 $\Psi^\mathrm{tot}$ · $\Psi^\mathrm{ext}$ · $\Psi^\mathrm{p}$（横轴丝序号，轮廓分界标出，纵轴量程固定为整段）；
  时间 × 丝的电流热图（至多 160 列、6 档、同色相邻格合并，纯 SVG）。另有 14 个线圈通道的安匝、`wall.json` 的 $\tau_k$ 与轮廓表、
  `options` · `kernel` · `door`（设定、事实、说明）原样。
- **叠加**：载入第二份 run 自动叠上（「主」「叠加」两排按钮可换）。叠加的那份用第二种颜色画进截面、时间迹与被动丝图，
  另出「主 − 叠加」卡：磁轴移动（$|\Delta|$、$\Delta R$、$\Delta Z$）、边界距离（max · mean，与 `compare` 同一个定义）、
  $\max_k|\Delta\Psi^\mathrm{tot}_k|$、$\Delta\sum I_k$。两份按**时刻**对齐：步长不同（如 `check_dt1ms` 的 1 ms 对 2 ms）时只比对得上的时刻，并写明对上几步。

**初始态页**：各个解（magdata 实测线圈电流 · a-file 的 EFIT 线圈电流）与参考 g-file 的边界叠画；逐项对照表（$I_p$、磁轴与距离、
边界距离、$\psi_N$ 图之差、$q_0$、$q_{95}$、同尺 $l_i(1)$ · $l_i(3)$ · $\beta_p$、$W$、$V$、$\kappa$、$Z_\mathrm{anchor}$、线圈对残余、收敛）；
$Z_\mathrm{anchor}$ 的二分扫描。

**比较页**：`compare` 的每一对（磁轴移动 max / 末步、边界距离、$\Delta l_i$、$\Delta\beta_p$、$\Delta q_{95}$、丝处磁通差），认出
「同一个解」的对（`prescribed` 回放 `induced`）；各 run 的摘要。`compare` 只留最大值——两份 run 也载入时，「看差」画差随时间、
「叠加到演化页」直接叠上；缺哪份就写缺哪份。

**大小与速度**：一份 run 约 8 MB，只解析一次（node 里 `JSON.parse` 约 0.05 s，连预算与首画约 0.25 s），逐步要用的量在载入时算好；换步只重画截面、
被动丝两张图与各图的时间光标（光标画在叠层里，曲线与热图不重画）。一对 run 的边界距离约 100 个时刻、各 $181^2$ 次段距，只算一次。

