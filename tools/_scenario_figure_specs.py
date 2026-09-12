"""Figure specs for the scenario chapters (read by make-scenario-figures.py).

One entry per chapter of FYL-DESIGN-25..33.  Node kinds: doc (an input
document) · code (a step with a kernel code) · off (a step with no code
today) · loop (a fyo:ScenarioLoop) · crit (an acceptance / comparison record).
Edge kinds: data · model · back · gate.  Facts here come from the kernel's
declaration face (35 codes), the scenario templates and the Python tool
register; a stage whose code the kernel does not declare is drawn `off`.
"""

SPECS = {}

# ---------------------------------------------------------------- A2 series --
SPECS["series"] = {
 "flow": {"title": "逐片重构（时间序列）", "height": 560,
  "nodes": [
   {"id": "dev", "kind": "doc", "col": 0, "y": 110, "title": "装置文档", "lines": ["`fyo:DeviceDescription`"]},
   {"id": "meas", "kind": "doc", "col": 0, "y": 190, "title": "磁测量（多片）", "lines": ["`magnetics · pf_active · tf`", "时刻列表 t₁..t_N"]},
   {"id": "slice", "kind": "code", "col": 1, "y": 120, "title": "每片：一次反演", "lines": ["`code/reconstruction`", "同一份设定，逐片换测量", "片间不插值（-12 P-23）"], "crit": "每片各自：GS 残差 · χ²"},
   {"id": "queue", "kind": "loop", "col": 2, "y": 130, "title": "队列", "lines": ["`宿主逐片串行`", "步预算 = 片数", "取消落在片界"]},
   {"id": "series", "kind": "code", "col": 3, "y": 120, "title": "汇总为时序", "lines": ["`code/series`（门今天不认）", "q₀ · q₉₅ · l_i · β_p 对 t", "逐片记录 → 一份时序文档"], "crit": "无合成判据：逐片判据照录"},
   {"id": "cmp", "kind": "crit", "col": 4, "y": 120, "title": "对照", "lines": ["交付 EFIT 时序", "`ComparisonRecord`", "逐片一行"]},
  ],
  "edges": [
   {"from": "dev", "to": "slice"}, {"from": "meas", "to": "slice"},
   {"from": "slice", "to": "queue"}, {"from": "queue", "to": "series"},
   {"from": "queue", "to": "slice", "kind": "back", "fs": "t", "ts": "t", "path": "M630,130 C630,80 365,80 365,120", "label": "下一片（同设定）", "lx": 430, "ly": 74},
   {"from": "series", "to": "cmp", "kind": "gate", "label": "逐片对照", "ly": 150},
  ],
  "legend": ["批处理不是场景：它是围着反演栏的一条队列（宿主机制），命令行上就是 series 或一个 shell 循环（FYL-DESIGN-17 E-8）。",
             "series 的模板在（8 参数），内核门今天不认 code/series（-23 G-1 重测）；页面的时间序列栏可跑。"]},
 "page": {"title": "逐片重构", "shell": "实验分析 · 逐片重构（时间序列）", "context": "east · #137985 · 3.5–4.5 s · 11 片",
  "actions": ["运行全部", "单片", "从此片重跑", "断点", "取消"], "action_note": "取消落在片界；已算的片完整可用",
  "panels": [
   {"x": 16, "y": 124, "w": 400, "h": 300, "title": "片表 · 状态从逐片记录读", "items": [
     ("table", "", ["t [s]     状态         χ²      q₀     q₉₅", "3.500    succeeded   11.2   0.78   3.08", "3.600    succeeded   11.9   0.79   3.07", "3.700    succeeded   12.4   0.79   3.06", "3.800    running      —      —      —", "3.900    —            —      —      —", "…        —            —      —      —"]),
     ("badge", "当前片", "run", "running"), ("text", "同一份设定 · 逐片换测量 · 片间不插值")]},
   {"x": 432, "y": 124, "w": 792, "h": 300, "title": "时序 · 逐片标量对 t（已算片实心，未算片空）", "items": [
     ("plot", "t [s]  ·  蓝 q₀ · 绿 q₉₅ · 红虚 交付 EFIT", [("c1", [(0.05,0.3),(0.2,0.35),(0.35,0.36),(0.5,0.38)]), ("c2", [(0.05,0.7),(0.2,0.68),(0.35,0.66),(0.5,0.66)]), ("c3", [(0.05,0.32),(0.5,0.4),(0.95,0.42)])], 190)]},
   {"x": 16, "y": 440, "w": 600, "h": 300, "title": "所选片 · 逐道残差（-12 逐道残差表）", "items": [
     ("table", "", ["通道        实测      前向      σ       r/σ", "flux_loop_01  0.412   0.409   0.004   0.7", "flux_loop_02  0.398   0.391   0.004   1.8", "probe_07     -0.121  -0.126   0.003   1.6", "point_ne      2.1e19  2.0e19  1e18    1.0"]),
     ("text", "点一片 → 这一片的残差表与截面；页面不判，判据来自那一片的记录")]},
   {"x": 632, "y": 440, "w": 592, "h": 300, "title": "片的截面（所选片）", "items": [("text", "极向截面：ψ 等值线 · LCFS · 限制器 · 磁轴（记录里的 profiles_2d/psi）"), ("plot", "R [m] × Z [m]（示意）", [("c1", [(0.3,0.5),(0.4,0.8),(0.6,0.85),(0.75,0.5),(0.6,0.15),(0.4,0.2),(0.3,0.5)])], 170)]},
  ], "note": "★概念图：数值示意；片表的状态列 = 各片记录的 run_state，页面无私有状态。"}}

# ------------------------------------------------------------ A3 interpretive --
SPECS["interpretive"] = {
 "flow": {"title": "解释性分析（给 T 反求 χ · 0-D 放电账）", "height": 560,
  "nodes": [
   {"id": "prof", "kind": "doc", "col": 0, "y": 110, "title": "实测剖面", "lines": ["`core_profiles`（Tₑ · nₑ · Tᵢ）", "来自 A1 的 pressure 文档或导入"]},
   {"id": "eq", "kind": "doc", "col": 0, "y": 200, "title": "平衡（重构解）", "lines": ["`equilibrium`", "A1 阶段 3 的记录"]},
   {"id": "wave", "kind": "doc", "col": 0, "y": 290, "title": "放电波形", "lines": ["`Ip · P_aux · nₑ 对 t`", "语料切片或 mdsip"]},
   {"id": "src", "kind": "code", "col": 1, "y": 120, "title": "源项装配", "lines": ["`code/beam · code/rf_ray`", "`ADAS 辐射 · 欧姆 · α`", "在给定剖面上算沉积"], "crit": "守恒账：Σ源 = 输运 + 储能变化"},
   {"id": "interp", "kind": "code", "col": 2, "y": 120, "title": "功率平衡反演", "lines": ["`code/interpretive`", "同一条能量方程反着解", "给 T 反求 χ_e · χ_i"], "crit": "χ 非负 · 边界处不发散"},
   {"id": "zerod", "kind": "code", "col": 2, "y": 300, "title": "0-D 放电账", "lines": ["`code/zerod`", "规定剖面：W · τ_E · H98 对 t", "P_fus · Q · V_loop"], "crit": "H 因子与定标对照"},
   {"id": "cmp", "kind": "crit", "col": 3, "y": 150, "title": "对照", "lines": ["χ 对新经典 / TGLF 档（M2）", "`ComparisonRecord`", "「反常 / 新经典」判读"]},
  ],
  "edges": [
   {"from": "prof", "to": "src"}, {"from": "eq", "to": "src"}, {"from": "src", "to": "interp"},
   {"from": "wave", "to": "zerod"}, {"from": "eq", "to": "zerod", "path": "M194,229 C300,229 420,330 530,330", "kind": "data"},
   {"from": "interp", "to": "cmp", "kind": "gate"}, {"from": "zerod", "to": "cmp", "kind": "gate", "path": "M760,330 C900,330 950,220 1060,200"},
  ],
  "legend": ["与 M2（定态输运）是同一条能量方程的两个方向（FYL-DESIGN-10 P-28）：M2 给 χ 求 T，本章给 T 求 χ；符号同、方向反，页面上必须分得开。",
             "zerod 在 analysis 线上是「解释性 0-D」（FYTOK S8-FR-INF-2 ◐）；在 design 线上是「方案 0-D」（D1）——同一 code，两种用法，两章各说各的输入。"]},
 "page": {"title": "解释性分析", "shell": "实验分析 · 解释性分析", "context": "east · #137985 · 4.0 s · 剖面来自 A1 记录",
  "panels": [
   {"x": 16, "y": 124, "w": 400, "h": 616, "title": "输入与档位", "items": [
     ("badge", "剖面文档", "ok", "x+run://A1/pressure"), ("badge", "平衡文档", "ok", "x+run://A1/s3"),
     ("chips", "源项", ["beam", "rf_ray", "ADAS", "α"], 0), ("chips", "反演量", ["χ_e", "χ_i", "D"], 0),
     ("slider", "边界 ρ", 0.85, "ρ_b 0.9"), ("slider", "平滑", 0.3, "λ 0.3"),
     ("text", "L2 改档位 = 改计划；L3 绑自己的剖面文档"),
     ("warn", "告警（记录 caveat）：Tᵢ 取声明的形状，n_i = n_e，无快离子；", "内部剖面不可定量使用（reference/fidelity）")]},
   {"x": 432, "y": 124, "w": 792, "h": 300, "title": "χ 剖面 · 反演解对新经典档（对照来自记录）", "items": [
     ("plot", "ρ  ·  蓝 χ_e 反演 · 绿 χ_neo · 红虚 χ_TGLF（M2 档）", [("c1", [(0.05,0.4),(0.3,0.45),(0.6,0.6),(0.9,0.9)]), ("c2", [(0.05,0.1),(0.5,0.12),(0.9,0.2)]), ("c3", [(0.05,0.3),(0.5,0.5),(0.9,0.85)])], 190)]},
   {"x": 432, "y": 440, "w": 792, "h": 300, "title": "功率账 · 逐项（守恒行来自记录 summary）", "items": [
     ("table", "", ["项            [MW]    出处", "P_ohm         0.42    code/interpretive", "P_beam        1.10    code/beam", "P_rad        -0.35    ADAS", "dW/dt         0.05    core_profiles", "P_cond        1.22    余项 = 反演出的 χ 所载", "守恒残差      2e-3    summary/balance"]),
     ("text", "判定块是一等产物（P-5）：残差与阈值的比较在记录里，页面照录")]},
  ], "note": "★概念图。code/interpretive 在内核声明面（35 code）里，本页面的栏今天在建模页（反演栏）——本章把它归到 analysis 线。"}}

# ----------------------------------------------------------- M1 equilibrium --
SPECS["equilibrium"] = {
 "flow": {"title": "平衡正解与位形（给电流与位形求 ψ 与度规）", "height": 600,
  "nodes": [
   {"id": "dev", "kind": "doc", "col": 0, "y": 110, "title": "装置文档", "lines": ["`pf_active · wall · tf`"]},
   {"id": "prof", "kind": "doc", "col": 0, "y": 190, "title": "剖面假设", "lines": ["`p′(ψ) · FF′(ψ)` 或 β_p · l_i", "抛物 / 给定剖面"]},
   {"id": "shape", "kind": "doc", "col": 0, "y": 280, "title": "目标位形或线圈电流", "lines": ["Miller 参数 / 轮廓点", "或 `pf_active` 电流"]},
   {"id": "fwd", "kind": "code", "col": 1, "y": 120, "title": "正解", "lines": ["`code/forward`（自由边界）", "`code/steady_equilibrium`（固定边界）", "Picard · 边界由线圈电流定"], "crit": "GS 残差 < ε · 轴 / X 点定位"},
   {"id": "metric", "kind": "code", "col": 2, "y": 120, "title": "度规与磁面", "lines": ["`code/ladder` 描迹 → 逐面度规", "`code/metric · code/li3`", "`code/xpoints · code/outlines`"], "crit": "gm 系数守恒检验（体积 · 通量）"},
   {"id": "hand", "kind": "crit", "col": 3, "y": 120, "title": "交出去的工件", "lines": ["`equilibrium` 文档（P-21）", "→ M2 定态输运的度规", "→ D2 的起点 · A1 的阶段 0 对照"]},
   {"id": "cocos", "kind": "code", "col": 2, "y": 300, "title": "约定与往返", "lines": ["`code/cocos`（COCOS 判定）", "g-file 往返（登记册 V-15）", "`code/shape`（形状标量）"], "crit": "往返逐位 · COCOS 自报"},
  ],
  "edges": [
   {"from": "dev", "to": "fwd"}, {"from": "prof", "to": "fwd"}, {"from": "shape", "to": "fwd"},
   {"from": "fwd", "to": "metric"}, {"from": "metric", "to": "hand"},
   {"from": "fwd", "to": "cocos", "fs": "b", "ts": "l", "path": "M365,250 C365,330 450,330 530,330"},
   {"from": "cocos", "to": "hand", "kind": "gate", "path": "M760,330 C900,330 950,220 1060,200", "label": "对照：CHEASE 固定边界（B-10）", "lx": 790, "ly": 360},
  ],
  "legend": ["FYL-DESIGN-10 P-20：边界与度规是一条栏，不是一个下拉菜单——今天建模页没有这条栏（-10 G-11 未落），能力散在 forward / steady_equilibrium / ladder / metric 五个 code 里。",
             "自由边界正解的边界由线圈电流决定；D2（位形与线圈电流）是它的反问题。两章共用同一个正解器（FYL-DESIGN-09 D-6）。"]},
 "page": {"title": "平衡正解与位形", "shell": "物理建模 · 平衡正解与位形", "context": "ITER · 15 MA · 固定 / 自由边界",
  "panels": [
   {"x": 16, "y": 124, "w": 400, "h": 616, "title": "输入 · 剖面与边界", "items": [
     ("chips", "边界", ["固定", "自由"], 1), ("chips", "剖面", ["抛物", "给定", "β_p · l_i"], 0),
     ("slider", "I_p [MA]", 0.75, "15.0"), ("slider", "β_p", 0.4, "0.65"), ("slider", "l_i", 0.5, "0.85"),
     ("slider", "κ", 0.6, "1.85"), ("slider", "δ", 0.5, "0.45"),
     ("badge", "装置文档", "ok", "iter · pf_active 12"),
     ("text", "L1：选装置与预设；L2：改剖面档与形状；L3：绑自己的线圈电流文档")]},
   {"x": 432, "y": 124, "w": 480, "h": 616, "title": "极向截面 · ψ 等值线 · LCFS · X 点 · 线圈", "items": [
     ("plot", "R [m] × Z [m]（示意）", [("c1", [(0.3,0.5),(0.38,0.85),(0.6,0.9),(0.78,0.5),(0.62,0.12),(0.42,0.1),(0.3,0.5)]), ("c2", [(0.34,0.5),(0.42,0.75),(0.6,0.8),(0.72,0.5),(0.6,0.2),(0.44,0.2),(0.34,0.5)])], 440)]},
   {"x": 928, "y": 124, "w": 296, "h": 616, "title": "读数 · 每个数带出处", "items": [
     ("table", "", ["q₀        1.02   summary", "q₉₅       3.1    summary", "l_i(3)    0.85   code/li3", "β_N       1.8    summary", "R_axis    6.42   equilibrium", "GS 残差   3e-6   notes", "COCOS     11     code/cocos"]),
     ("badge", "记录", "ok", "succeeded"),
     ("text", "「交给输运」→ 命名工件（P-21），不是总线")]},
  ], "note": "★概念图。今天建模页无此栏（-10 G-11）；正解能力在 code/forward · steady_equilibrium · ladder · metric 里，页面走 code/forward。"}}

# -------------------------------------------------------------- M2 transport --
SPECS["transport"] = {
 "flow": {"title": "定态输运与闭包（给 χ 求 T）", "height": 600,
  "nodes": [
   {"id": "eq", "kind": "doc", "col": 0, "y": 110, "title": "平衡 / 度规", "lines": ["`equilibrium`（M1 的工件）", "或 Miller 标量装配"]},
   {"id": "src", "kind": "doc", "col": 0, "y": 200, "title": "源项", "lines": ["`core_sources`", "beam · rf · ADAS · α（表或 code）"]},
   {"id": "bc", "kind": "doc", "col": 0, "y": 290, "title": "边界条件", "lines": ["ρ_b 处 Tₑ · Tᵢ · nₑ", "台基档（EPED 代理）可选"]},
   {"id": "closure", "kind": "code", "col": 1, "y": 120, "title": "闭包（档位）", "lines": ["`constant · stiff · neoclassical`", "`turbulence`（TGLF，扩展面）", "`code/bootstrap · code/transport`"], "crit": "档位是参数，不是插件（原则 2）"},
   {"id": "solve", "kind": "code", "col": 2, "y": 120, "title": "定态解", "lines": ["`code/transport`", "θ-隐式有限体积 · Picard", "刚性闭包内迭代 2–28 次"], "crit": "内层：残差 < ε · 迭代上限"},
   {"id": "fm", "kind": "loop", "col": 3, "y": 130, "title": "通量匹配", "lines": ["`flux match（外环）`", "χ 冻结 · 目标通量", "TGYRO 型"]},
   {"id": "couple", "kind": "loop", "col": 3, "y": 300, "title": "平衡交替", "lines": ["`couple（可选）`", "每轮解一次平衡", "在新度规上弛豫"]},
   {"id": "out", "kind": "crit", "col": 4, "y": 120, "title": "产物与对照", "lines": ["`core_profiles`", "`core_transport`", "对 JINTRAC / TGYRO 列"]},
  ],
  "edges": [
   {"from": "eq", "to": "closure"}, {"from": "src", "to": "closure"}, {"from": "bc", "to": "closure", "path": "M194,319 C330,319 440,200 530,200", "ts": "l"},
   {"from": "closure", "to": "solve"}, {"from": "solve", "to": "fm"},
   {"from": "fm", "to": "solve", "kind": "back", "fs": "b", "ts": "b", "path": "M910,230 C910,280 645,280 645,236", "label": "未匹配：更新 χ 冻结值", "lx": 660, "ly": 292},
   {"from": "solve", "to": "couple", "kind": "model", "fs": "b", "ts": "l", "path": "M645,236 C645,350 700,350 810,350"},
   {"from": "couple", "to": "closure", "kind": "back", "fs": "t", "ts": "b", "path": "M910,300 C910,260 365,300 365,236", "label": "新度规 → 重装配", "lx": 560, "ly": 330},
   {"from": "fm", "to": "out", "kind": "gate"},
  ],
  "legend": ["coupled 与 tglf 不设独立模板：前者是 evolve / transport 的 couple 参数，后者是闭包的一档（FYL-DESIGN-17 E-8）。本章把两者放回它们所属的环。",
             "与 A3（解释性分析）是同一条能量方程的两个方向（-10 P-28）；与 M3 的差别只在有没有时间轴（-10 P-19）。"]},
 "page": {"title": "定态输运与闭包", "shell": "物理建模 · 定态输运", "context": "ITER 15 MA · transport-iter-15ma · 闭包 stiff",
  "panels": [
   {"x": 16, "y": 124, "w": 400, "h": 616, "title": "闭包与边界 · 141 个控件由词表生成（-18 U-1）", "items": [
     ("chips", "闭包", ["constant", "stiff", "neo", "TGLF"], 1), ("chips", "源", ["表", "beam", "rf_ray"], 0),
     ("slider", "χ₀ [m²/s]", 0.4, "0.55"), ("slider", "临界梯度", 0.5, "R/L_T 6"), ("slider", "ρ_b", 0.85, "0.9"),
     ("slider", "Tₑ,b [keV]", 0.3, "3.0"), ("badge", "度规", "ok", "x+run://M1/equilibrium"),
     ("text", "外环：通量匹配 on/off · 平衡交替 couple on/off"),
     ("warn", "换成 TGLF 档：一次求值 ~10² ms，内环 28 次 → 交互档超预算，", "页面按 P-15 转 worker，进度按步实测")]},
   {"x": 432, "y": 124, "w": 792, "h": 300, "title": "剖面 · Tₑ / Tᵢ 对 ρ（蓝 解 · 绿 参照列 JINTRAC · 灰 起点）", "items": [
     ("plot", "ρ_tor_norm", [("c1", [(0.02,0.95),(0.3,0.85),(0.6,0.6),(0.9,0.25),(0.98,0.12)]), ("c2", [(0.02,0.9),(0.3,0.83),(0.6,0.62),(0.9,0.27),(0.98,0.12)]), ("c3", [(0.02,0.7),(0.5,0.5),(0.98,0.12)])], 190)]},
   {"x": 432, "y": 440, "w": 792, "h": 300, "title": "收敛与通量匹配 · 逐轮（读数来自记录）", "items": [
     ("plot", "轮  ·  蓝 残差(log) · 绿 |通量失配|", [("c1", [(0.05,0.95),(0.3,0.6),(0.55,0.3),(0.8,0.1)]), ("c2", [(0.05,0.8),(0.3,0.5),(0.55,0.28),(0.8,0.12)])], 150),
     ("text", "Picard 6 轮 · 最差残差 8.1e-3 · converged: true（判定在记录）")]},
  ], "note": "★概念图。数值示意；控件名取自 transport 模板词表（19 参数）与 evolve 的闭包档。"}}

# ---------------------------------------------------------------- M3 evolve --
SPECS["evolve"] = {
 "flow": {"title": "含时演化与仿真推进（一条时间轴，两档保真度）", "height": 640,
  "nodes": [
   {"id": "start", "kind": "doc", "col": 0, "y": 110, "title": "起点", "lines": ["`equilibrium`", "`+ core_profiles`", "或 Miller · 抛物剖面"]},
   {"id": "act", "kind": "doc", "col": 0, "y": 220, "title": "执行器波形", "lines": ["`Ip · P_aux · nₑ · 燃料`", "对 t，或滑块（改未来）"]},
   {"id": "zerod", "kind": "code", "col": 1, "y": 120, "title": "0-D 档", "lines": ["`code/zerod`", "集总能量 · 粒子 · 磁通账", "V_loop · P_fus · Q 对 t"], "crit": "磁通预算：能维持多久（D-17）"},
   {"id": "march", "kind": "code", "col": 1, "y": 300, "title": "1.5-D 档", "lines": ["`code/evolve`（entry evolve_heat）", "热 · 密度 · 动量 · 电流通道", "锯齿 · 台基 · 闭包档"], "crit": "每步：能量账 1e-13 · dt 上限"},
   {"id": "step", "kind": "loop", "col": 2, "y": 200, "w": 260, "title": "步", "lines": ["`步预算（U-8）`", "断点 = 记录（fylite:state）", "取消落在步界 · 每步一片"]},
   {"id": "couple", "kind": "code", "col": 3, "y": 120, "title": "平衡交替（couple）", "lines": ["`code/refit · code/steady_current`", "每 k 步解一次平衡", "新度规回到推进"], "crit": "Δψ · Δq 相对变化"},
   {"id": "rec", "kind": "crit", "col": 4, "y": 120, "title": "记录", "lines": ["`spo:ComputationRecord`", "`fylite:state`", "40 ≡ 20 + 续 20 逐位"]},
   {"id": "sim", "kind": "off", "col": 3, "y": 340, "title": "仿真档（交互 cadence）", "lines": ["页面滑块改未来 · 过去不重算（D-12）", "同一推进，不是第二条路径（D-15）"]},
  ],
  "edges": [
   {"from": "start", "to": "zerod"}, {"from": "start", "to": "march", "path": "M194,154 C230,154 240,357 250,357"},
   {"from": "act", "to": "zerod", "path": "M194,255 C220,255 230,177 250,177"}, {"from": "act", "to": "march", "path": "M194,255 C230,255 240,357 250,357"},
   {"from": "zerod", "to": "step", "path": "M480,177 C505,177 505,268 530,268"},
   {"from": "march", "to": "step", "path": "M480,357 C505,357 505,268 530,268"},
   {"from": "step", "to": "couple", "kind": "model", "path": "M660,200 C660,160 780,160 810,177"},
   {"from": "couple", "to": "march", "kind": "back", "path": "M925,120 C925,88 505,88 505,120 L505,345 C505,357 495,357 480,357", "label": "新度规回到推进（回边）", "lx": 250, "ly": 292},
   {"from": "couple", "to": "rec"},
   {"from": "step", "to": "sim", "kind": "model", "path": "M660,336 C660,378 700,378 810,378"},
   {"from": "sim", "to": "step", "kind": "back", "path": "M925,340 C925,300 820,290 792,272", "label": "滑块 → 下一步的输入", "lx": 830, "ly": 310},
  ],
  "legend": ["一个应用只有一条时间轴（-10 P-19）：建模页的含时演化栏收敛进放电设计页的仿真模式，保真度是一个开关（-09 D-22）——0-D 与 1.5-D 是同一条时间轴上的两档。",
             "sim 不设模板：交互推进是浏览器的档位不是批式动作；批式是 evolve（114 参数 · 19 份预设）。断点即记录：40 步 ≡ 20 + 续 20（FYL-REPORT-07 §9.1）。"]},
 "page": {"title": "含时演化与仿真推进", "shell": "放电设计 · 仿真 · 1.5-D 档", "context": "ITER · evolve-iter-15ma · t = 3.20 / 8.00 s",
  "actions": ["运行到此", "单步", "从此重跑", "断点", "取消"], "action_note": "走廊右缘就是现在；滑块改未来，过去不重算（D-12）",
  "panels": [
   {"x": 16, "y": 124, "w": 400, "h": 616, "title": "执行器（自当下生效）与档位", "items": [
     ("chips", "保真度", ["0-D", "1.5-D"], 1), ("chips", "闭包", ["constant", "stiff", "neo", "TGLF"], 2),
     ("slider", "P_aux [MW]", 0.55, "33"), ("slider", "nₑ [1e19]", 0.5, "10.1"), ("slider", "燃料", 0.6, "D-T 50/50"),
     ("slider", "dt [ms]", 0.3, "20"), ("chips", "通道", ["热", "密度", "动量", "电流"], 0),
     ("badge", "断点", "ok", "步 160 · 记录已存"), ("text", "L1 按运行；L2 改档位与波形；L3 绑外部沉积表（NUBEAM 产物）")]},
   {"x": 432, "y": 124, "w": 792, "h": 300, "title": "走廊 · 0-D 标量对 t（右缘 = 现在）", "items": [
     ("plot", "t [s]  ·  蓝 W_th · 绿 P_fus · 红虚 磁通预算余量", [("c1", [(0.0,0.1),(0.2,0.5),(0.4,0.8),(0.55,0.85)]), ("c2", [(0.0,0.02),(0.2,0.3),(0.4,0.7),(0.55,0.75)]), ("c3", [(0.0,1.0),(0.55,0.6),(0.95,0.05)])], 190)]},
   {"x": 432, "y": 440, "w": 792, "h": 300, "title": "现在这一片 · 剖面与截面（解过的片实心，插值片空心，D-8）", "items": [
     ("plot", "ρ  ·  Tₑ · Tᵢ · nₑ（示意）", [("c1", [(0.02,0.95),(0.5,0.7),(0.98,0.1)]), ("c2", [(0.02,0.9),(0.5,0.66),(0.98,0.1)]), ("c3", [(0.02,0.6),(0.5,0.55),(0.98,0.2)])], 150),
     ("text", "每步一份记录片；能量账 1e-13 写在 notes；couple 每 10 步重解平衡")]},
  ], "note": "★概念图。含时演化栏搬进放电设计页这一步今天未落（-10 G-11）；图画的是目标态。"}}

# ------------------------------------------------------------- D1 scoping --
SPECS["scoping"] = {
 "flow": {"title": "放电方案：0-D 工况与可行域", "height": 560,
  "nodes": [
   {"id": "dev", "kind": "doc", "col": 0, "y": 110, "title": "装置文档", "lines": ["`R · a · B₀ · 线圈上限`", "供电与磁通预算"]},
   {"id": "goal", "kind": "doc", "col": 0, "y": 200, "title": "目标", "lines": ["Ip · 平顶时长 · P_aux", "Q 或 P_fus 目标"]},
   {"id": "zerod", "kind": "code", "col": 1, "y": 120, "title": "0-D 工况", "lines": ["`code/zerod`（33 参数）", "相位表 · 梯形波形单源（D-3）", "W · τ_E · H98 · V_loop · Q"], "crit": "定标对照 · 密度极限 · β 极限"},
   {"id": "scan", "kind": "loop", "col": 2, "y": 130, "title": "扫描", "lines": ["`feasible（无模板）`", "二维参数格 · 每格一解", "逐格报出卡住的通道"]},
   {"id": "feas", "kind": "crit", "col": 3, "y": 120, "title": "可行域", "lines": ["每格：可行 / 卡在哪一路", "`ComparisonRecord` 逐格一行", "判据只有一处（P-7）"]},
   {"id": "hand", "kind": "crit", "col": 4, "y": 120, "title": "交给 D2 / M3", "lines": ["选定工况 → 位形与线圈（D2）", "→ 时间推进（M3）"]},
  ],
  "edges": [
   {"from": "dev", "to": "zerod"}, {"from": "goal", "to": "zerod"}, {"from": "zerod", "to": "scan"},
   {"from": "scan", "to": "zerod", "kind": "back", "fs": "b", "ts": "b", "path": "M630,230 C630,290 365,290 365,236", "label": "下一格（换一对参数）", "lx": 420, "ly": 302},
   {"from": "scan", "to": "feas", "kind": "gate"}, {"from": "feas", "to": "hand"},
  ],
  "legend": ["zerod 有两种用法：这里是「方案 0-D」（S10-FR-ENG-1 · S7-FR-PULSE-1/2），A3 里是「解释性 0-D」（S8-FR-INF-2）。同一 code、两种输入，各在各章。",
             "feasible 不设模板：扫描轴的参数词表要先立（-17 P2-c）；Python 有 design.feasible（S11-FR-OPT-4 ●），页面无栏。"]},
 "page": {"title": "放电方案", "shell": "放电设计 · 配置 · 0-D 工况", "context": "ITER · zerod-iter-15ma",
  "panels": [
   {"x": 16, "y": 124, "w": 400, "h": 616, "title": "工况（33 参数，词表生成）", "items": [
     ("slider", "I_p [MA]", 0.75, "15"), ("slider", "平顶 [s]", 0.5, "400"), ("slider", "P_aux [MW]", 0.55, "50"),
     ("slider", "nₑ/n_GW", 0.7, "0.85"), ("slider", "H98", 0.5, "1.0"), ("chips", "相位", ["上升", "平顶", "下降"], 1),
     ("chips", "扫描轴", ["Ip × nₑ", "P_aux × H98"], 0), ("text", "L1 选预设；L2 改工况；L3 定义扫描轴（先立词表）")]},
   {"x": 432, "y": 124, "w": 792, "h": 300, "title": "0-D 轨迹 · 相位表来自内核（D-3）", "items": [
     ("plot", "t [s]  ·  蓝 I_p · 绿 P_fus · 红虚 V_loop", [("c1", [(0.0,0.05),(0.15,0.8),(0.8,0.8),(0.95,0.1)]), ("c2", [(0.0,0.0),(0.2,0.2),(0.4,0.7),(0.8,0.7),(0.95,0.05)]), ("c3", [(0.0,0.9),(0.15,0.4),(0.8,0.2),(0.95,0.5)])], 190)]},
   {"x": 432, "y": 440, "w": 792, "h": 300, "title": "可行域 · Ip × nₑ 每格一解，卡住的通道逐格报出", "items": [
     ("table", "", ["nₑ/n_GW ↓  Ip →   12 MA   13.5   15    16.5", "0.6            ✓      ✓      ✓     磁通", "0.8            ✓      ✓      ✓     磁通", "1.0            密度   密度   密度   密度"]),
     ("text", "判定块是一等产物（P-5）：每格的「卡在哪一路」来自记录的 refusal.stage / caveat")]},
  ], "note": "★概念图。可行域扫描今天无栏无语料（-17 P2-c）；图是目标态。"}}

# --------------------------------------------------------------- D2 configure --
SPECS["configure"] = {
 "flow": {"title": "位形 · 线圈电流 · 击穿场零 · 电源尺寸（一个时刻）", "height": 600,
  "nodes": [
   {"id": "dev", "kind": "doc", "col": 0, "y": 110, "title": "装置文档", "lines": ["`pf_active · wall · tf`", "线圈上限（铭牌，F-19 缺）"]},
   {"id": "tgt", "kind": "doc", "col": 0, "y": 200, "title": "目标位形", "lines": ["Miller / 轮廓点 / X 点", "或 A1 的重构边界"]},
   {"id": "case", "kind": "doc", "col": 0, "y": 290, "title": "工况（D1）", "lines": ["Ip · β_p · l_i", "或 0-D 记录的一片"]},
   {"id": "inv", "kind": "code", "col": 1, "y": 120, "title": "静态线圈反解", "lines": ["`code/discharge`（23 参数）", "自由边界 G-S 内环", "岭回归外环 → PF 电流"], "crit": "形状误差 · 电流限值逐通道"},
   {"id": "null", "kind": "code", "col": 1, "y": 300, "title": "击穿场零", "lines": ["`code/breakdown`（17 参数）", "真空场零 + Townsend 判据", "逐通道工程限值"], "crit": "B_null · 连接长度 · E_tor 阈"},
   {"id": "supply", "kind": "off", "col": 2, "y": 120, "title": "电源尺寸（pfwave）", "lines": ["读本栏输入 → 电流 · 电压", "门今天不认 code/pfwave", "浏览器侧合成（无 Python 入口）"]},
   {"id": "vs", "kind": "code", "col": 2, "y": 300, "title": "垂直稳定裕度", "lines": ["`entry vstab`（无 case code）", "k · k_ideal · γ", "见 C1"], "crit": "裕度 > 0"},
   {"id": "out", "kind": "crit", "col": 3, "y": 120, "title": "一个时刻的配置", "lines": ["`equilibrium + pf_active 电流`", "判定块：可行 / 卡在哪一路", "→ D3 的路点 · M3 的起点"]},
  ],
  "edges": [
   {"from": "dev", "to": "inv"}, {"from": "tgt", "to": "inv"}, {"from": "case", "to": "inv", "path": "M194,319 C230,319 240,200 250,200"},
   {"from": "dev", "to": "null", "path": "M194,139 C230,139 240,340 250,340"},
   {"from": "inv", "to": "supply"}, {"from": "inv", "to": "vs", "kind": "model", "fs": "b", "ts": "l", "path": "M365,236 C365,340 450,340 530,340"},
   {"from": "supply", "to": "out"}, {"from": "null", "to": "out", "kind": "gate", "path": "M480,360 C700,360 760,230 810,200", "label": "判定合流", "lx": 600, "ly": 375},
   {"from": "vs", "to": "out", "kind": "gate", "path": "M760,360 C790,360 790,230 810,220"},
  ],
  "legend": ["breakdown 同时挂在 design 与 control 线：场零设计是配置问题（本章），击穿动力学与上升段归 C1。pfwave 重复 discharge 的输入（实测按下不跑设计栏给出逐位相同的数）——它是电源尺寸，不是第二个场景。",
             "平顶段的 PF 电流是 LCFS 锁定下反馈回路的稳态解（-09 D-6）；这里解的是一个时刻。整条脉冲见 D3。"]},
 "page": {"title": "位形与线圈电流", "shell": "放电设计 · 配置 · 位形与线圈电流", "context": "ITER · discharge-iter · t = 平顶",
  "actions": ["求解", "击穿场零", "电源尺寸", "断点", "取消"], "action_note": "配置模式：一个时刻一个解（-09 D-18）",
  "panels": [
   {"x": 16, "y": 124, "w": 400, "h": 616, "title": "目标位形与工况", "items": [
     ("slider", "R₀ [m]", 0.5, "6.2"), ("slider", "a [m]", 0.5, "2.0"), ("slider", "κ", 0.6, "1.85"), ("slider", "δ", 0.5, "0.45"),
     ("chips", "X 点", ["下单零", "双零"], 0), ("slider", "I_p [MA]", 0.75, "15"), ("slider", "β_p", 0.4, "0.65"),
     ("badge", "装置", "ok", "iter · 12 PF · 6 CS"), ("text", "L2：把手改 LCFS（-18 U-12 试改，可撤销）；L3：绑外部位形")]},
   {"x": 432, "y": 124, "w": 480, "h": 616, "title": "极向截面 · 目标 vs 解出的 LCFS · 线圈电流色标 · 场零", "items": [
     ("plot", "R × Z（示意）· 蓝 解 · 绿 目标 · 红虚 击穿场零区", [("c1", [(0.3,0.5),(0.38,0.85),(0.6,0.9),(0.78,0.5),(0.62,0.12),(0.42,0.1),(0.3,0.5)]), ("c2", [(0.31,0.5),(0.39,0.84),(0.6,0.89),(0.77,0.5),(0.62,0.13),(0.42,0.11),(0.31,0.5)]), ("c3", [(0.5,0.45),(0.55,0.55),(0.5,0.62),(0.45,0.55),(0.5,0.45)])], 440)]},
   {"x": 928, "y": 124, "w": 296, "h": 616, "title": "判定块（P-5）· 逐通道", "items": [
     ("table", "", ["线圈    I [kA]   上限   状态", "CS1U    -12.3    45     ✓", "CS2U    -38.9    45     ✓", "PF1      41.2    48     ✓", "PF3      -6.1    48     ✓", "PF6      44.9    48     ★ 93 %"]),
     ("badge", "形状误差", "ok", "2.1 mm rms"), ("badge", "场零", "ok", "B_null 1.8 mT"), ("badge", "垂直裕度", "run", "计算中"),
     ("text", "「卡在哪一路」来自记录，页面照录")]},
  ], "note": "★概念图。电源尺寸与线圈铭牌上限（F-19）今天缺件，判定列相应标「未评估」。"}}

# ------------------------------------------------------------------ D3 pulse --
SPECS["pulse"] = {
 "flow": {"title": "整脉冲前馈设计（路点序列 → 逐通道电流与电压）", "height": 600,
  "nodes": [
   {"id": "script", "kind": "doc", "col": 0, "y": 110, "title": "脉冲脚本", "lines": ["相位 · Ip(t) · 位形轨迹", "路点表（一个时刻一个 D2）"]},
   {"id": "dev", "kind": "doc", "col": 0, "y": 200, "title": "装置文档", "lines": ["`pf_active` 电路 · 电阻 · 互感", "电压上限"]},
   {"id": "wp", "kind": "loop", "col": 1, "y": 130, "title": "逐路点", "lines": ["`每路点一次 D2`", "解过的片 vs 插值片（D-8）", "分得清"]},
   {"id": "ff", "kind": "code", "col": 2, "y": 120, "title": "前馈电压", "lines": ["`code/waveform · code/pulse`", "电路方程 L dI/dt + RI = V", "上升沿 / 下降沿各自（D-4 · D-5）"], "crit": "电压上限逐通道 · 磁通预算"},
   {"id": "flat", "kind": "code", "col": 2, "y": 300, "title": "平顶：LCFS 锁定", "lines": ["`code/steady_current`", "PF 电流随等离子体状态（D-6）", "形状反馈的稳态解"], "crit": "过期的是线性化，不是电流（D-7）"},
   {"id": "out", "kind": "crit", "col": 3, "y": 120, "title": "逐通道波形", "lines": ["`pulse` 文档：I(t) · V(t) 每线圈", "0-D 标量走廊", "→ M3 的执行器波形"]},
   {"id": "check", "kind": "crit", "col": 4, "y": 120, "title": "校验", "lines": ["对 GSPulse 型参考", "`ComparisonRecord`", "供电 / 电压 / 磁通三账"]},
  ],
  "edges": [
   {"from": "script", "to": "wp"}, {"from": "dev", "to": "ff", "path": "M194,229 C300,229 420,185 530,185"},
   {"from": "wp", "to": "ff"}, {"from": "wp", "to": "flat", "kind": "model", "fs": "b", "ts": "l", "path": "M350,230 C350,340 450,340 530,340"},
   {"from": "flat", "to": "ff", "kind": "back", "fs": "t", "ts": "b", "path": "M645,300 C645,270 645,270 645,236", "label": "平顶电流作前馈的边界", "lx": 655, "ly": 272},
   {"from": "ff", "to": "out"}, {"from": "out", "to": "check", "kind": "gate"},
  ],
  "legend": ["pulse 不设模板：整脉冲前馈设计今天没有 code IRI（语料 pulse-iter 用 code/pfwave）——内核声明面里有 code/pulse 与 code/waveform，模板要一个真实的 code（-17 P2-c）。",
             "本章是 D2 的序列（BROWSER_ONLY_BARS：pulse 重复 discharge 答的问题，按路点排开）；下降沿是一等公民，不是上升沿取负（-09 D-5）。"]},
 "page": {"title": "整脉冲前馈设计", "shell": "放电设计 · 设计 · 整条脉冲", "context": "ITER · pulse-iter · 上升 60 s · 平顶 400 s · 下降 90 s",
  "actions": ["设计", "解此片", "全部重解", "断点", "取消"], "action_note": "播放头选片；解过的片实心，插值片空心（D-8）",
  "panels": [
   {"x": 16, "y": 124, "w": 400, "h": 616, "title": "脉冲脚本（D-1：一份脚本，多个视图）", "items": [
     ("table", "", ["路点   t [s]   Ip [MA]  κ     δ     解", "1      0       0.5      1.3   0.1   ✓", "2      30      7.5      1.6   0.3   ✓", "3      60      15.0     1.85  0.45  ✓", "4      460     15.0     1.85  0.45  ✓", "5      550     0.5      1.3   0.1   ○"]),
     ("chips", "PF 驱动", ["形状反馈", "前馈电压"], 1), ("slider", "V 上限 [kV]", 0.5, "1.5"),
     ("text", "L2：改路点与相位；L3：导出脚本 / 绑外部轨迹")]},
   {"x": 432, "y": 124, "w": 792, "h": 300, "title": "走廊 · Ip · 位形轨迹 · 播放头", "items": [
     ("plot", "t [s]  ·  蓝 I_p · 绿 κ · 红虚 磁通消耗", [("c1", [(0.0,0.05),(0.12,0.8),(0.82,0.8),(0.97,0.05)]), ("c2", [(0.0,0.2),(0.12,0.7),(0.82,0.7),(0.97,0.2)]), ("c3", [(0.0,0.0),(0.12,0.3),(0.82,0.85),(0.97,0.9)])], 190)]},
   {"x": 432, "y": 440, "w": 792, "h": 300, "title": "逐通道电流与电压 · 上限带（-09 D-4）", "items": [
     ("plot", "t [s]  ·  蓝 I_CS1 · 绿 V_CS1 · 红虚 上限", [("c1", [(0.0,0.9),(0.12,0.5),(0.82,0.1),(0.97,0.3)]), ("c2", [(0.0,0.5),(0.12,0.2),(0.2,0.5),(0.82,0.5),(0.9,0.8),(0.97,0.5)]), ("c3", [(0.0,0.95),(0.97,0.95)])], 150),
     ("text", "电压超限的片标红并说明是哪一路（P-5 · P-6 拒绝优于外推）")]},
  ], "note": "★概念图。设计模式今天在页面上可用（浏览器专有栏 pulse），命令行无模板（-17 P2-c）。"}}

# ------------------------------------------------------------- C1 vertical --
SPECS["vertical"] = {
 "flow": {"title": "垂直稳定与位置控制（裕度 → 反馈 → 闭环演化）", "height": 600,
  "nodes": [
   {"id": "eq", "kind": "doc", "col": 0, "y": 110, "title": "平衡与线圈", "lines": ["`equilibrium`（D2 或 A1）", "`pf_active · pf_passive`（真空室）"]},
   {"id": "ctrl", "kind": "doc", "col": 0, "y": 200, "title": "控制律", "lines": ["PD 增益 · 观测器", "作用于集总模型"]},
   {"id": "vstab", "kind": "code", "col": 1, "y": 120, "title": "n=0 垂直模", "lines": ["`entry vstab`（无 case code）", "刚体：k · k_ideal · γ（电阻壁）", "刚性滤丝配方"], "crit": "裕度 k/k_ideal · γ τ_wall"},
   {"id": "resp", "kind": "code", "col": 1, "y": 300, "title": "形状响应矩阵", "lines": ["`code/vessel · code/coilshare`", "∂(形状)/∂(I_coil)", "线性化（过期的是它，D-7）"], "crit": "条件数"},
   {"id": "fb", "kind": "off", "col": 2, "y": 120, "title": "垂直反馈回路", "lines": ["`vertical`（无模板）", "闭环：Z 观测 → 电压", "guide〈垂直反馈回路〉"]},
   {"id": "evo", "kind": "off", "col": 2, "y": 300, "title": "电压驱动的位形演化", "lines": ["`evolution`（无模板）", "电路 + 平衡逐步", "guide〈电压驱动的位形演化〉"]},
   {"id": "loop", "kind": "loop", "col": 3, "y": 200, "title": "闭环", "lines": ["`逐步：观测 → 律 → 电压`", "步预算 · 断点在步界", "取消落在步界"]},
   {"id": "out", "kind": "crit", "col": 4, "y": 120, "title": "判定与记录", "lines": ["稳定 / 失控 · 何时", "Z(t) · V(t) 轨迹", "`ComparisonRecord` 对 TokSys（B-04）"]},
  ],
  "edges": [
   {"from": "eq", "to": "vstab"}, {"from": "eq", "to": "resp", "path": "M194,139 C230,139 240,340 250,340"},
   {"from": "ctrl", "to": "fb", "path": "M194,229 C330,229 440,185 530,185"},
   {"from": "vstab", "to": "fb"}, {"from": "resp", "to": "evo"},
   {"from": "fb", "to": "loop"}, {"from": "evo", "to": "loop", "path": "M760,340 C790,340 790,270 810,260"},
   {"from": "loop", "to": "fb", "kind": "back", "fs": "t", "ts": "r", "path": "M910,200 C910,150 800,150 760,170", "label": "下一步", "lx": 820, "ly": 146},
   {"from": "loop", "to": "out", "kind": "gate"},
  ],
  "legend": ["vstab · vertical · evolution 三个「无模板」并成一章：实际工作里它们是一条链——先判裕度，再设计反馈，再闭环演化。vstab 有内核 entry 无 case code（-17 P2-c）。",
             "breakdown 的击穿动力学与上升段属 D2（场零设计）与本章之间；本章只收上升段之后的位置控制。"]},
 "page": {"title": "垂直稳定与位置控制", "shell": "控制仿真 · 垂直稳定与位置控制", "context": "ITER · 平顶平衡来自 D2",
  "actions": ["评估裕度", "闭环运行", "单步", "断点", "取消"], "action_note": "取消落在步界；已跑的步完整可用",
  "panels": [
   {"x": 16, "y": 124, "w": 400, "h": 616, "title": "平衡 · 真空室 · 控制律", "items": [
     ("badge", "平衡", "ok", "x+run://D2/equilibrium"), ("badge", "真空室", "stale", "pf_passive 缺（A-15）"),
     ("slider", "K_p", 0.4, "1.2"), ("slider", "K_d [ms]", 0.5, "8"), ("slider", "观测噪声", 0.2, "0.5 mm"),
     ("chips", "控制律", ["PD", "观测器"], 0), ("slider", "dt [ms]", 0.3, "0.5"),
     ("text", "L2 改增益；L3 绑自己的控制律（外部产物：增益表）")]},
   {"x": 432, "y": 124, "w": 792, "h": 300, "title": "裕度 · k / k_ideal · γ（读数来自记录）", "items": [
     ("table", "", ["量           值        判据", "k            0.62      —", "k_ideal      0.71      —", "k / k_ideal  0.87      < 1 稳定（裕度 13 %）", "γ [1/s]      120       γ τ_wall = 2.4"]),
     ("badge", "判定", "ok", "stable")]},
   {"x": 432, "y": 440, "w": 792, "h": 300, "title": "闭环 · Z(t) 与线圈电压（示意）", "items": [
     ("plot", "t [ms]  ·  蓝 Z 位移 · 绿 V_VS · 红虚 电压上限", [("c1", [(0.0,0.5),(0.1,0.9),(0.3,0.35),(0.5,0.58),(0.7,0.48),(0.95,0.5)]), ("c2", [(0.0,0.5),(0.1,0.1),(0.3,0.75),(0.5,0.4),(0.7,0.55),(0.95,0.5)]), ("c3", [(0.0,0.95),(0.95,0.95)])], 150),
     ("text", "失控的一步标红并停在步界（P-8：失败不得留着上一次的答案）")]},
  ], "note": "★概念图。今天页面无此栏、命令行无模板；Python 有 control.vstab（S9-FR-EVO-1 ◐）。图是目标态。"}}
