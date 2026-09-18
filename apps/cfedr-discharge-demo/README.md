# CFEDR d2025 放电推演（建模结果）

:::{note}
**在 fylite 仓里（`apps/cfedr-discharge-demo/`）只收源与输入**：`app/` 的模型工具、工作台页面
与三份输入（`device_cfedr.json` · `state_init.json` · `waveform_studio.json`）、`test/` 两道页面检查、
`scripts/` 生成脚本与模板、`i10/` 的探针脚本与诊断记录。**不在仓里**的是下文提到的产物：
`app/libfylite.so`、`app/run_full.json` · `app/state_end.json`、`reports/`、`imas*/`、`repro-1p5d/`、
`discharge*.json`、`i10/` 的 CSV / 日志 / 快照与 `cfedr_evolve_plan_fuelled.json`、`cfedr-app.tar.gz`。

补回库（跑模型工具要它）：

```bash
bash rust/build.sh --no-io                    # 在 fylite 仓根；不链 HDF5 / netCDF 的那一档
cp rust/fylite_runtime/target/release/libfylite_runtime.so apps/cfedr-discharge-demo/app/libfylite.so
```

然后照 `app/README.md`〈用法〉跑一遍即得完整时序与结束状态；报告与 IMAS 条目照下文〈重新生成〉。
:::

**目录**：代码与页面各自成层，数据留在根上。

```
cfedr-discharge-demo/
├── app/       工具 · 工作台 · **跑一炮要的全部输入**（见 `app/README.md`）：
│              cfedr_core_model.py · cfedr_studio.html（单文件页面，双击即开）·
│              device_cfedr.json · state_init.json · waveform_studio.json ·
│              libfylite.so（产物不入库：状态与时序跑一遍就有）
├── test/      页面的两道 node 检查（初始化 + 逐个按钮点一遍），见 test/README.md
├── reports/   报告页与动画：cfedr-report.html · cfedr-discharge*.html / .mp4 / .gif
├── repro-1p5d/ · imas*/ · scripts/      复现运行、IMAS 条目、老脚本
└── discharge*.json · repro-1p5d/…                                          其余数据
```

模型与页面都在 `app/` 里，命令也在那里发（见 `app/README.md`）；页面直接打开
`app/cfedr_studio.html`，放电数据用它工具栏上的「导入输出 JSON」读模型 `--series` 跑出来的那份。

CFEDR d2025（15 MA 常规 H 模）沿 PCS 指令回放的建模结果：上升 0–60 s · 平顶 60–6150 s · 下降 6150–6210 s。
本目录是一次推演的产物，不是设计方结论。生成日期 2026-09-14。

## 文件

| 文件 | 内容 |
| :--- | :--- |
| `reports/cfedr-discharge.html` | 交互式页面（单文件、数据内嵌）：时间轴拖动 / 播放；时序信号（三段折断时间轴）、小截面与二维磁面（实现 LCFS · 目标 LCFS · ψ_N 等值线 · X 点 · 线圈电流着色）、形状对比、线圈电流 / 额定、Tₑ/Tᵢ 与 nₑ 剖面 |
| `reports/cfedr-discharge.mp4` · `reports/cfedr-discharge.gif` | 动画，**匀速**：每帧推进 0.25 s 放电时间（三段显示区间内；平顶 150 → 6150 s 稳态段与时间轴一样折断）；剖面在相邻关键帧之间按时间线性插值，平衡取同阶段不晚于该时刻的最近一次解。MP4 839 帧 24 fps（H.264 / yuv420p、1920×1080，放电 6 s / 视频 1 s）；GIF 取其每 3 帧、8 fps（同速）。图内标注为英文（渲染机无中文字体） |
| `discharge-uniform.json` | 页面与动画用的匀速帧（由 `discharge.json` 的 297 个关键帧经 `scripts/uniform_json.py` 插出） |
| `imas/` | IMAS 数据条目，HDF5 后端，DD 4.1.1（`imas:hdf5?path=…/imas`） |
| `discharge.json` | 页面与动画共用的汇总数据（等值线已预计算、剖面按帧抽样） |
| `scripts/` | 生成脚本（见下） |

## IMAS 条目

| IDS | 内容 |
| :--- | :--- |
| `equilibrium` | 29 个时刻的自由边界平衡：`profiles_2d[0]` ψ(R,Z)（65×65，整圈通量 Wb，COCOS 17）、`boundary`（轮廓、类型 0 限制器 / 1 偏滤器、几何轴、小半径、拉长比、上下三角形变）、`contour_tree.node`（磁轴 = 极大值；偏滤器时 X 点 = 鞍点，ψ = ψ_b）、`global_quantities`（Iₚ、ψ_axis、ψ_boundary、磁轴） |
| `pf_active` | 装置卡 15 个 PF 线圈（矩形、匝数）与各平衡时刻的线圈电流（每匝安培 = 通道安匝 / 匝数） |
| `core_profiles` | 0-D 全放电模型的 689 个时刻：Tₑ、Tᵢ、nₑ 在 ρ_tor,norm（41 点）上 |
| `summary`（occurrence 0） | 0-D 时序：Iₚ、v_loop、W_th、β_N、β_p、P_fus、中子功率、Q、P_aux、轴上 Tₑ / nₑ、线平均 nₑ |
| `summary`（occurrence 1） | 1.5-D 会话推进窗口（65 → 95 s，3000 个 10 ms 步）：P_fus、W_th、轴上 Tₑ、Iₚ 指令、RF 指令 |

读取示例：

```python
import imas
with imas.DBEntry("imas:hdf5?path=<算例根目录>/imas", "r") as db:
    eq = db.get("equilibrium")
    psi = eq.time_slice[15].profiles_2d[0].psi
```

## 模型层级

- **小截面 / 二维磁面**：fylite `code/discharge`，位置控制 C4（电流形心设定点），线圈额定上限取装置卡（104014 表 1），每个采样时刻冷解一次；目标 Miller 形状与 Iₚ 按回放文件逐参数线性插值。采样：上升 16 个、平顶 3 个、下降 10 个。
- **时序信号 / 一维剖面**：fylite `code/zerod` 三遍——① 以回放线平均密度求轴上密度；② tier B（IPB98(y,2)）预测轴上 Tₑ；③ 以预测 Tₑ 走规定档出剖面与判据。剖面是参数化形状，**不是输运解**。定标：Tᵢ/Tₑ = 0.80（CASE-20 轴上 23.0 / 28.7 keV），H 因子 0.91（使平顶 W_th ≈ CASE-20 的 807 MJ），Z_eff 取 CASE-20 工况，B₀ 6.3 T @ 7.8 m。回读：平顶 P_fus ≈ 2.01 GW、Q ≈ 19.7（CASE-20 为 1.51 GW）。
- **1.5-D 会话推进**：公开仓 `fylite.engine.session`（每 10 ms 一次 `code/evolve`），CASE-20 给定 LCFS 工况 + I-9 加料标定 + L-H martin08，自 65 s 起（该时刻加热 102 MW 与燃烧起步态相符）。结果：恒 H 模、P_fus 稳定在约 1.18 GW、W_th 748 MJ；每步墙钟 p50 295 ms · p99 362 ms · 最大 478 ms。

## 已知偏差与注意

- 平顶实现 R₀ 7.57 m，比目标 7.87 m 偏内约 0.3 m（C4 形心设定点未计 Shafranov 外移，见台账 I-14）；平顶 3 路线圈达额定上限。
- 上升 < 40 s 与下降 ≥ 6180 s 的低电流时刻给出限制器位形；上升 17–35 s 回放要求偏滤器位形而未得到。
- 下降段节点是回放文件自己标的合成节点；0 → 60 s 上升段没有 1.5-D 输运起步态，只有 0-D 层。
- 回放 60–65 s 只令 RF 20 MW，与 CASE-20 燃烧态不相符（1.5-D 从 60 s 起跑会塌，见台账 I-10）。
- **内核发现**：`code/zerod` 输出里的 `summary/fusion/power` 行实为 α 功率（= `prediction_p_alpha` ≈ P_fus / 4.97），总聚变功率在其 `p_fus` 字段；本条目的 `summary.fusion.power` 取 `p_fus`。
- **运行时发现**：公开仓 `libfylite_runtime.so`（09-14 10:13）内嵌的内核早于 F-9（`code/discharge` 缺省读卡片线圈额定），经 Python 调用时卡片额定不被读取；`scripts/eq_sequence.py` 因此在算例侧显式绑定 `fylite:i_max_aturn`。重建运行时后此绑定可去掉。

## 连续 1.5-D 放电演化与文献对照（2026-09-14，当前版本）

**报告页 `reports/cfedr-report.html`**：交互式放电查看器（取代视频：播放 / 暂停 / 逐帧 / 拖动时间轴，每帧 0.25 s 匀速；小截面与二维磁面、线圈电流着色、T_e / T_i 与 n_e 剖面、读数；点击时序图跳到该时刻）、时序小倍图（1.5-D · 0-D · 回放指令 · 文献值，悬停读数）、文献 0-D 放电方案时序对照、平顶运行点逐项对照（文献 · 本模型 150 s · 平顶末）、物理模型清单（包含 / 简化 / 未包含，可筛选）、近似与未涉及物理、数值方法、尝试过的方案、来源。

| 文件 | 内容 |
| :--- | :--- |
| `reports/cfedr-report.html` | 交互式报告（单文件，数据内嵌约 1.8 MB；放电查看器由 `discharge-1p5d.json` 的匀速帧驱动，不再引用视频） |
| `reports/cfedr-discharge-1p5d.mp4` | 连续演化动画，匀速 0.25 s / 帧，667 帧 24 fps，1920×1080 |
| `reports/cfedr-discharge-1p5d.html` · `discharge-1p5d.json` | 交互式放电查看页与其数据（300 个关键帧插成 667 个匀速帧） |
| `imas-1p5d-continuous/` | IMAS 条目（HDF5，DD 4.1.1）：平衡 · PF 线圈 · 连续 1.5-D 的窗端剖面与 10 ms / 1 s 行时序（40 → 6171.5 s） |
| `app/state_init.json` | **初始状态**（单一时间片，40 s）：`--state` 自它起跑。平顶 / 结束状态与完整时序都是**产物**，跑一遍就有，不留在库里 |
| `app/waveform_studio.json` | **控制波形**：页面「导出控制波形」的那 31 个节点（5.9 KB） |
| `app/cfedr_studio.html` | **波形工作台**（单文件）：输入页——节点表 + 可拖/可增删的波形图；磁面按 **Miller 参数**（R₀ · Z₀ · a · κ · δ · ζ）编时序，控制点数可改（缺省 8），控制点轨迹连线；生成 / 导出输入 JSON，或从输出里导入磁面演化。输出页——排版照报告页的看图区：工具栏 → 相位芯片 → 截面 ∥ 读数 + 温度 / 密度剖面 → 时序信号 → PF 线圈波形 → 其余一维通道（按 `meta.profiles` 勾选）；可导出整份 / 当前时间片 JSON / **当前片 g-file**。页首常驻「仅为 demo 演示，不可做设计参考」，右上角明暗风格开关 |
| `app/waveform_studio.json` | 页面「导出控制波形」的产物：CFEDR 15 MA 的 **31 个名表节点**（每个带 Miller 参数采出的八点），也就是页面内置默认算例那一份 |
| `app/cfedr_core_model.py` | **堆芯模型单文件工具**：按名表 dict 进出（`time` · Ip · NBI · ECRH · ICRF · LHW · n̄_e · n_roh · 控制点 · PF 电流 → P_fusion · β_t · β_N · β_p · l_i · dfsdev · V_loop · W_MHD · n̄_e 设定/实现 · 加料率 · 十五条剖面），物理经 `libfylite.so` 交给 fylite 内核。说明见 `app/README.md` |
| `repro-1p5d/continuous/` | 运行 CSV · 窗记录 · 剖面 · 摘要 · 两份工况（0-D 40 s 起步 · 状态起步）· 保留快照（150 s · 6150 s · 拒绝前 6171.5 s） |

**分层**：1 → 40 s 0-D 层（限制器期体积只有平顶的 31–70 %，固定位形 1.5-D 不成立）；**40 s 起一段连续 1.5-D**，自 0-D 40 s 状态起步：磁通按 I_p 缩放（电流一致）、I_p 反馈环开（k_p = k_i = 1）、IPB98 锚取平顶标定参考、Z_eff 1.8、边界密度随指令线平均密度。L 模爬升 → 60–65 s L→H → 约 80 s 燃烧 H 模 → 平顶恒 H（P_fus ≈ 1.25 GW、W_th ≈ 764 MJ、β_N 含快 α 2.56、H98 1.07）→ 下降段 6159.4 s H→L → **6170 s（I_p 10 MA）交回 0-D 层**（与 40 s 交接对称：I_p < 10 MA 后体积回落到平顶的 81–31 %、限制器位形）。

**下降段分叉扫描**（`repro-1p5d/rampdown/`，自 `before-node@6150` 快照、带当时加料控制器状态，`fylite.engine.pcs_replay --resume … --set … --fuel-state …`）：

| 分支 | 改动 | H→L | 被拒于 |
| :--- | :--- | ---: | ---: |
| V0 | 回放原指令（6155 s 切 IC、6170 s EC 82 → 10 MW） | 6159.4 s | 6171.5 s（与连续运行逐行同） |
| V1 | EC 82 MW 保持到 6193 s（`replay_rd_rfhold.json`） | 6159.4 s | 6193.5 s |
| V2 | `lh_off_factor` 0.8 → 0.5 | 6166.1 s | 6170.5 s |
| V3 | `d_over_chi` 0.1 → 0.3 | 6162.3 s | 6172.0 s |
| V4 | V1 + V2 + V3 | 6192.5 s | 6196.0 s（I_p 3.5 MA） |

每一支都在加热降到 10 MW 后半秒内被拒，且都已在 I_p < 10 MA 区间。可行顺序是先降密度、保 H 模、后降加热（V4）；回放的合成下降（先切加热、密度按 Greenwald 份额恒定降）在本模型里必然辐射塌缩。

重新生成（在平衡序列与 0-D 层之后）：

```bash
PYTHONPATH=fylite/python $PY scripts/rampup_plan.py plan_fuelled.json zerod_cal.npz $REPLAY 40 plan_zd_40.json
#   平顶锚与 Z_eff 1.8 写进 plan_zd_40.json 的 settings（chi_scale_* 取标定平顶快照，见 repro-1p5d/continuous/plan_zd_40_C.json）
PYTHONPATH=fylite/python $PY scripts/rampup_state_plan.py plan_zd_40_C.json plan_40C.json 1 1 15e6 10.125e6
PYTHONPATH=fylite/python $PY -m fylite.engine.pcs_replay plan_40C.json $REPLAY 40 150 r40C.csv \
    --window 5 --ramp-window 0.5 --dt-max 0.025 --edge-ne-ref 5.474159142171447 1.139e20
PYTHONPATH=fylite/python $PY -m fylite.engine.pcs_replay plan_40C.json $REPLAY 40 6209 r40C.csv \
    --resume r40C.csv.snapshots/end@150.00.json --window 50 --ramp-window 0.5 --dt-max 0.025 --flat-every 100 \
    --edge-ne-ref 5.474159142171447 1.139e20
$PY scripts/assemble_hybrid.py discharge.json r40C.csv r40C.csv.snapshots/end@150.00.json 40 keys.json
$PY scripts/uniform_json.py keys.json 0.25 discharge-1p5d.json
FFMPEG=… $PY scripts/render_gif.py discharge-1p5d.json cfedr-discharge-1p5d.mp4 24
$PY scripts/build_report.py scripts/report_template.html keys.json discharge.json r40C.csv \
    r40C.csv.snapshots/end@150.00.json r40C.csv.snapshots/before-node@6150.00.json cfedr-report.html
```

## 1.5-D 整炮重现（2026-09-14，台账 I-20 / I-21；已由上节取代，保留作对照）

时序信号与一维剖面改由 **1.5-D 输运**给出（`code/evolve` 经公开仓 `fylite.engine.pcs_replay` 分窗推进：一窗一次内核调用、自适应物理步长 ≤ 25 ms、10 ms 输出取内核逐步迹含 W_th、片界快照）。小截面 / 二维磁面仍是上面的自由边界平衡序列。

| 文件 | 内容 |
| :--- | :--- |
| `reports/cfedr-discharge-1p5d.html` · `reports/cfedr-discharge-1p5d.mp4` · `cfedr-discharge-1p5d.gif` | 同上三块内容，时序与剖面换成 1.5-D；匀速同上（MP4 659 帧 24 fps、1920×1080；GIF 每 3 帧 8 fps） |
| `discharge-1p5d.json` | 页面与动画的汇总数据（2 328 个迹点、217 个关键帧插成 659 个匀速帧、52 点 ρ）；65–152 s 的迹与剖面取窗长 1 s 的加密运行（`repro-1p5d/ftmid.*`，逐窗端有剖面） |
| `imas-1p5d/` | IMAS 条目（HDF5，DD 4.1.1）：`equilibrium` · `pf_active` 同上；`core_profiles` 283 个窗端剖面（march 自身 ρ_tor 梯子 52 点）；`summary` 14 262 行（爬升 / 下降 10 ms、平顶 1 s）：Iₚ 指令、P_aux、线平均 nₑ 指令、P_fus、W_th（逐步迹）、轴上 Tₑ / Tᵢ、β_N、P_rad、v_loop |
| `repro-1p5d/` | 两段运行的逐行 CSV、窗记录、剖面 JSONL、摘要、爬升起步工况，及保留快照（平顶 150 s 节点前 · 下降 6 171.5 s 拒绝前） |

**分段拼接（65 s）**：

- **上升 1 → 65 s**：冷起步态（0-D 模型 1 s 剖面映射到 CASE-20 固定位形，`scripts/rampup_plan.py`），IPB98 锚取首调自身态，按回放线平均密度做加料反馈。整炮这一次运行一路走到 6 199.5 s（340 窗、墙钟 233 s），但平顶物理不对（见下），只取其上升段。
- **平顶 + 下降 65 s → 6 171.5 s**：CASE-20 标定加料工况（I-10 口径），165 窗、244 359 物理步、**墙钟 136 s**（I-10 的 10 ms 定步长同段约数十小时量级）；平顶恒 H、P_fus ≈ 1 167 MW、W_th ≈ 744 MJ；燃烧 65–150 s 对 I-10 的 10 ms 基线：P_fus 最大差 0.64 %（稳态）/ 0.95 %（瞬态），W_th 0.004 % / 0.083 %，Tₑ₀ 0.003 %（瞬态首点 2.41 %）。
- **6 171.5 s 被内核拒绝**（-23，种类态不收敛）：与 I-10 定步长全程（6 172.99 s）同一处、同一机制（下降段切 RF 后 L 模局部辐射塌缩）；数据止于此。

**已知偏差**：

- 拼接处状态不连续（冷起步上升段在 65 s 的 W_th ≈ 1.39 GJ、Tₑ₀ ≈ 50 keV，标定工况 800 MJ / 28.7 keV）。
- 冷起步上升段偏热、偏稀：密度通道边界是状态末点的 Dirichlet，起步态边界 5.9e17 m⁻³ 被一路带着；让边界随指令密度升高后，爬升早期边界辐射塌缩（9.5 s 被拒）；IPB98 锚以 0.25 MA 首调态为参考外推过热、以平顶参考则过冷（5.5 s 被拒）；爬升段 V_loop 迹恒 0.02 V。冷起步 1.5-D 爬升需要边界模型与爬升段 Ip 控制参数（公开仓 PLAN I-20 行）。
- 平顶 L-H 在冷起步运行里颤振（P_sep ≈ P_LH），标定工况运行恒 H。

重新生成（在上面的平衡序列之后）：

```bash
# netcdf / hdf5 不在默认搜索路径时，先把它们所在目录放进 LD_LIBRARY_PATH
PY=python3                      # 装了 imas-python / h5py / matplotlib 的那个解释器
REPLAY=<内核仓>/docs/cases/pcs/cfedr-d2025-replay.json
PYTHONPATH=fylite/python $PY -m fylite.engine.pcs_replay repro-1p5d/plan_rampup_1s.json $REPLAY 1 6209 full2.csv \
    --window 50 --ramp-window 0.5 --dt-max 0.025 --flat-every 100
PYTHONPATH=fylite/python $PY -m fylite.engine.pcs_replay plan_fuelled.json $REPLAY 65 6209 ft2.csv \
    --window 50 --ramp-window 0.5 --dt-max 0.025 --flat-every 100
PYTHONPATH=fylite/python $PY -m fylite.engine.pcs_replay plan_fuelled.json $REPLAY 65 152 ftmid.csv \
    --window 1 --ramp-window 0.5 --dt-max 0.025
$PY scripts/assemble15.py discharge.json full2.csv ft2.csv ft2.csv.snapshots/before-node@150.00.json 65 keys-1p5d.json ftmid.csv 152
# 匀速：每帧 0.25 s 放电时间，关键帧之间按时间线性插值
$PY scripts/uniform_json.py keys-1p5d.json 0.25 discharge-1p5d.json
$PY scripts/build_page.py scripts/page_template.html discharge-1p5d.json cfedr-discharge-1p5d.html
# MP4：输出名以 .mp4 结尾即走 ffmpeg（H.264）；本机无系统 ffmpeg，取 imageio-ffmpeg 自带的静态二进制
FFMPEG=$(uv run --no-project --with imageio-ffmpeg python -c "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())") \
    $PY scripts/render_gif.py discharge-1p5d.json cfedr-discharge-1p5d.mp4 24
$PY scripts/render_gif.py discharge-1p5d.json cfedr-discharge-1p5d.gif 8 3     # 每 3 帧取 1，8 fps 与 MP4 同速
$PY scripts/write_imas15.py eq_lim app/device_cfedr.json full2.csv ft2.csv ft2.csv.snapshots/before-node@150.00.json 65 imas-1p5d
```

暂停 / 恢复：运行目录下建 `<out>.pause` 或给 `--pause-at T`，驱动在下一个窗界写 `pause@T.json` 快照后退出；`--resume <快照>` 接着走、输出追加（与不中断运行逐行相同，公开仓 `python/tests/test_pcs_replay.py`）。

## 重新生成

依赖：一个装了 imas-python 2.3.0 · imas_core 5.7.2 · h5py · matplotlib · Pillow 的 Python 环境、`fylite` 公开仓 `python/` 与其 `_lib`、CFEDR 装置卡 JSON（`app/device_cfedr.json`，由公开仓 `dist/facts/device/cfedr/cfedr_device.yaml` 转换）、内核导出的工况文档（内核芯部链 `PCS_PLAN_DUMP`，带 `PCS_DENSITY=1 PCS_DCHI=0.1 PCS_PINCH=-0.02 PCS_PINCH_SHAPE=linear PCS_FUEL=2.5e21 PCS_BOOKS=1 PCS_LH=1`）。

```bash
# netcdf / hdf5 不在默认搜索路径时，先把它们所在目录放进 LD_LIBRARY_PATH
PY=python3                      # 装了 imas-python / h5py / matplotlib 的那个解释器
REPLAY=<内核仓>/docs/cases/pcs/cfedr-d2025-replay.json
PYTHONPATH=fylite/python $PY scripts/eq_sequence.py app/device_cfedr.json $REPLAY eq_lim
PYTHONPATH=fylite/python $PY scripts/zerod_run.py plan_fuelled.json $REPLAY zerod_cal.npz '{"tite": 0.80, "hfac": 0.91}'
PYTHONPATH=fylite/python $PY scripts/pcs_replay_drive.py plan_fuelled.json $REPLAY 65 95 session.csv
$PY scripts/assemble.py eq_lim zerod_cal.npz app/device_cfedr.json session.csv discharge.json
$PY scripts/build_page.py scripts/page_template.html discharge.json cfedr-discharge.html
$PY scripts/render_gif.py discharge.json cfedr-discharge.gif 8
$PY scripts/write_imas.py eq_lim zerod_cal.npz app/device_cfedr.json imas session.csv
```
