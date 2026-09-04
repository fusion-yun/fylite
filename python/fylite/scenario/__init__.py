"""The four scenario lines, on the Python side (FYL-DESIGN-08).

★★**本包现在只剩装配**（2026-09-04，`FYL-DESIGN-16` 分期第 1 步）。四个不做装配的模块
搬去了 :mod:`fylite.engine` —— ``cases``（算例语料的目录与计划）· ``benchmark``（公开 V&V
登记册）· ``physics``（一份产出的自洽判据册）· ``suite``（判据套的执行与落账）。它们的内核
调用合计**三处**，做的是语料、登记与校验，那是宿主机械而不是场景装配；``physics`` 甚至本来
就在引 :mod:`fylite.engine.provenance` 的四态判决。这一步不删任何能力，它划的是边界：
**留在这里的，正是 K-3 之后要搬进内核并从此消失的那些行**。


``app/`` was ten pages organised by METHOD until FYL-DESIGN-07 v0.5 folded
them into **four purpose lines**.  ``python/fylite`` is still in the state
``app/`` left: forty-odd flat modules, each complete in itself and therefore
each closed.  This package is the same convergence on this side — the same
four lines, the same ten tool ids, so a capability is called the same thing
in the browser, in a notebook and in the CLI.

    design    放电设计     discharge · breakdown · feasible
    control   控制仿真     vstab
    model     物理建模     zerod · transport · coupled · tglf
    analysis  实验分析     reconstruction

**What converges is the entrance, not the physics.**  No method module is
merged or deleted; a tool function assembles inputs, calls the kernel or the
method module, and returns a plain dict.  Two rules make that a discipline
rather than an intention, and both are gated in ``python/tests/test_scenario.py``:

* **D-4′** — nothing here computes physics or numerics.  ``scipy`` and
  ``contourpy`` may not be imported from this package at all; what a
  physicist would recognise as a choice belongs in the kernel.
* **D-2** — every tool states which upstream FR it is a REDUCED tier of and
  where it is not equivalent, once, here, in :data:`TOOLS` — and every
  result carries that statement in its ``provenance`` key rather than
  leaving the caller to remember it.

★The verdict column below is not this package's opinion.  It mirrors
FYL-DESIGN-07 §8 row for row, and the test parses that table out of the
markdown and compares.  Neither register may drift from the document, and a
tool that is not built stays ``○`` here rather than acquiring a function
that returns zeros.

★★This used to say「the same oracle ``app/tests/validate-lines.mjs`` uses for
the browser」— and it has not been true since that gate was replaced by
``validate-site.mjs``, which DROPPED the row-by-row comparison on purpose:
the "lines" model is withdrawn, so making two files agree about requirement
rows was checking bookkeeping rather than the app.  The §8 comparison is now
this side's alone, and saying otherwise pointed a reader at a file that is
not there.
"""
from __future__ import annotations

from types import MappingProxyType

__all__ = ["LINES", "TOOLS", "BROWSER_ONLY_BARS", "line_of", "tools_of", "provenance",
           "coverage", "analysis", "control", "design", "model"]


# --------------------------------------------------------------------------- #
# the register
# --------------------------------------------------------------------------- #
#: One entry per tool.  ``owner`` is the line whose module carries it (a tool
#: serving two lines is listed on both but implemented once — the same rule
#: that keeps one copy of the markup in ``app/``).  ``fr`` is the upstream
#: requirement it is a reduced tier of; ``scope`` says what it answers;
#: ``caveat`` says where it is NOT equivalent to that requirement.
#:
#: ★★``bar`` is THE BROWSER'S NAME FOR THE SAME CAPABILITY — the id it
#: registers with (``DESIGN.bar('zerod', …)`` in ``app/assets/scenario-*.js``)
#: — or ``None`` when the browser does not offer it at all.  It exists because
#: the two hosts do NOT agree name for name, and the disagreement had gone
#: invisible: ``coupled`` is the browser's ``evolve``, one capability under two
#: names, which is exactly what this register was written to stop.  Renaming
#: either side is not free (the bar id is on sixty element ids, the i18n keys,
#: the case catalogue's ``fylite:bar`` and every reader's
#: ``localStorage`` key), so the correspondence is DECLARED and gated instead
#: of assumed — see ``test_the_tool_set_matches_the_browsers``.
#:
#: ★``bar: None`` is a statement about the browser, and each one has a reason
#: readable at the other end: ``feasible`` is withdrawn by name in
#: ``scenario-design.js``'s own header ("a scan OVER the breakdown problem,
#: and the question it answers has no caller on this page yet"); ``vstab``
#: survives as a generated fyo ENTRY (``fyo-interface.js``) with no bar to
#: press; ``tglf`` is not a bar but a MODE inside two of them (the worker's
#: ``transport_turb``).
_TOOLS: dict[str, dict] = {
    "discharge": {
        "bar": "discharge", "owner": "design", "entry": "design.discharge",
        "fr": ("S11-FR-INV-1", "S7-FR-EQ-1/2/3"),
        "scope": "静态线圈反解：目标形状 → 线圈电流（自由边界 G-S 内环 + 岭回归外环）",
        "caveat": "每一步是收敛到 tol 的静态解，不含惯性与演化；"
                  "退火从上一轮出发而非从最好一轮出发，故 history 可能非单调",
    },
    "breakdown": {
        "bar": "breakdown", "owner": "design", "entry": "design.breakdown",
        "fr": ("S10-FR-LIM-1/2",),
        "scope": "击穿前的纯真空场零设计 + 逐通道工程限值，不可行时报出卡在哪一路",
        "caveat": "限值由使用者填（非机器数据）；纯真空，无等离子体、无 G-S",
    },
    "feasible": {
        "bar": None, "owner": "design", "entry": "design.feasible",
        "fr": ("S11-FR-OPT-4",),
        "scope": "二维参数扫描的可行域：每格点一次静态零场解，逐格点报出卡住的通道",
        "caveat": "「可行」＝存在一个满足限值的静态解，不是「这台机器能这么运行」",
    },
    "vstab": {
        "bar": None, "owner": "control", "entry": "control.vstab",
        "fr": ("S9-FR-EVO-1",),
        "scope": "刚体 n=0 垂直模：刚度 k、理想上限 k_ideal、电阻壁增长率 γ",
        "caveat": "刚体约化模型且是静态判据——回答「稳不稳」，不回答"
                  "「形状在闭环里怎么变」，也不把状态推进下去",
    },
    "zerod": {
        "bar": "zerod", "owner": "model", "entry": "model.zerod",
        "fr": ("S10-FR-ENG-1", "S7-FR-PULSE-1/2", "S10-FR-DRV-1"),
        "scope": "规定剖面的 0-D 放电：Ip / V_loop / P_fus / Q 的时间轨迹",
        "caveat": "n_e、T_e、T_i 是规定的输入不是结果；Q 因此不是预言。"
                  "predict 档解的是能量平衡，与 evaluate 档不是同一种答案",
    },
    "transport": {
        "bar": "transport", "owner": "model", "entry": "model.transport",
        "fr": ("S7-FR-TR-1..5",),
        "scope": "固定几何 1.5D 芯部输运：θ-隐式有限体积推进 Te/Ti",
        "caveat": "几何固定、无平衡反馈；闭包是约化档（常数 χ / 刚性 / 中子）；"
                  "★粒子源由调用方给定——本包不含加料模型（打丸 / 充气 / 束流"
                  "燃料），密度道的源是实测或外部模型的输入，不是本包的产物",
    },
    "coupled": {
        #: ★★2026-08-26: `coupled` GAVE THE BAR UP to `evolve`, and the
        #: reason is the finding that ruling came out of.  The browser's
        #: 含时演化 bar is a time-marching executor; `coupled` is the STATIC
        #: tier of the same picture — it alternates a steady transport solve
        #: with an equilibrium solve, which is what that bar does in its
        #: `couple` rounds and not what the bar IS.  One bar carrying two
        #: Python capabilities is the truth here, and the register says it by
        #: giving the bar to the one that marches and pointing this one at it
        #: rather than by letting two entries claim one id.
        "bar": None, "owner": "model", "entry": "model.coupled",
        "fr": ("S7-FR-LOOP-1",),
        "scope": "平衡—输运自洽交替：每轮解一次平衡、在解出的度规上弛豫剖面",
        "caveat": "两次平衡之间的东西没有被解；到轮数上限即止并如实报 settled",
    },
    "evolve": {
        "bar": "evolve",
        #: ★★the DECLARED kernel entry at this tool's core (A-7).  The tool is
        #: not the entry: `model.evolve` assembles the Miller metric and the
        #: initial profiles here and then hands the loop to the kernel.  What
        #: this key says is which single kernel symbol carries the sunk half,
        #: so `engine.crosshost` can run THAT on both builds and compare.
        #: ★It is absent from every other tool on purpose: `zerod` /
        #: `transport` exist as declared entries and the browser calls them
        #: that way, but these Python tools reach the same kernel code through
        #: the flat exports — claiming a core they do not go through would
        #: make a cross-host report about a path this tool never takes.
        "kernel_entry": "evolve_heat", "owner": "model", "entry": "model.evolve",
        "fr": ("S7-FR-TR-1..5",),
        "scope": "含时演化：固定 Miller 几何上按时间推进热通道（Te/Ti 对 + 碰撞交换），"
                 "源为辅热沉积 + ADAS 辐射 + 处方档 D-T alpha",
        "caveat": "★循环在内核（`evolve_heat` 场景条目），本层只做装配——"
                  "但范围也因此**只有内核条目声明的那些**：常数闭包、热通道一条。"
                  "密度 / 电流 / 动量通道、基座、锯齿、束流、波、演化平衡都不在，"
                  "逐条由 `fylite cases --plan` 按算例点名；几何是处方的 Miller，"
                  "q 是处方抛物线而非电流扩散的结果",
    },
    "tglf": {
        "bar": None, "owner": "model", "entry": "model.tglf",
        "fr": ("S7-FR-TR-5",),
        "scope": "局域线性稳定性与准线性通量（TGLF 移植面）",
        "caveat": "γ 是线性增长率不是输运通量；WIDTH 必须由调用方给出——"
                  "libtglf 会二分搜索模宽，移植面不会，也不替调用方猜一个",
    },
    "reconstruction": {
        "bar": "reconstruction", "owner": "analysis", "entry": "analysis.reconstruction",
        "fr": ("S8-FR-RECON-1", "S8-FR-OP-2"),
        "scope": "磁测量（+ 动理学压强）平衡重构",
        "caveat": "磁测量单独约束不住内部剖面；正向算子只有磁通环与探针一支，"
                  "弦积分族缺席",
    },
    #: ★没有 `profit` 这一格了：2026-08-19 剖面拟合**页**退役
    #: （FYL-DESIGN-07 文首注）。拟合本身没有消失——`analysis.profit` 与内核
    #: `profile_shape_fit` 都在，重构页仍以「压强剖面 (fyo JSON)」导入接收它的
    #: 产物。变的是这条边的起点在仓外，不是这条边被删掉。
    #: ★★这条注释原来还说「TOOLS 记的是浏览器与 Python 共有的工具集」——
    #: **那句已经不成立**：九件里有四件浏览器没有，浏览器另有五条功能栏不是这里的
    #: 工具。共有的那部分现在由每条 `bar` 声明，剩下的两边各自登记（`bar: None`
    #: 与 `BROWSER_ONLY_BARS`），闸子两个方向都查。
}
TOOLS = MappingProxyType({k: MappingProxyType(v) for k, v in _TOOLS.items()})

#: Browser 功能栏 that are NOT tools in this register, each with the reason —
#: the other half of the same statement `bar` makes, so a divergence has to be
#: argued for in one place or the other rather than simply appearing.
#:
#: ★This register may GROW (the browser is allowed new bars) but an entry may
#: not sit here while a tool also claims the bar: that would be one capability
#: declared twice, which is the thing being prevented.
_BROWSER_ONLY_BARS: dict[str, str] = {
    "pulse": "a SEQUENCE of static designs over waypoints (worker `pulse`): "
             "it repeats what `discharge` answers rather than answering "
             "something else, and no Python entry composes it",
    "profile": "profile fitting — `analysis.profit` and the kernel's "
               "`profile_shape_fit` are both here, but the fitting PAGE was "
               "retired on 2026-08-19 and the tool left this register with "
               "it (see the note above); the bar outlived the tool entry",
    "series": "a run of time slices (worker `recon_series`).  Python has it "
              "as `recon_rs.run_series`, a function rather than a registered "
              "tool — the same capability at a different granularity, which "
              "is why it is named here and not silently absent",
    "batch": "a QUEUE around the reconstruction bar (it claims that bar's "
             "handlers while it runs); browser plumbing, not a capability",
    "interp": "profile interpolation onto the kernel's grid — a utility the "
              "marching bars need, with no standalone Python entry",
    #: ★★2026-09-01 补登两个：设计页上长出来的，此前这个注册表不知道它们，
    #: 而闸子（`test_scenario.test_the_tool_set_matches_the_browsers`）正是为
    #: 「浏览器长了栏而这边不吭声」写的——它红了一次，说的就是这件事。
    "pfwave": "PF supply sizing over the design bar's target controls — it "
              "reads that bar's inputs and returns currents and volts for the "
              "supplies (measured: pressing it without running the design bar "
              "gives bit-identical numbers, i.e. it composes that bar's inputs "
              "rather than answering something new).  Browser-side sizing, no "
              "standalone Python entry",
    "sim": "the interactive time march on the design page — sliders (dt, rate, "
           "Ip, a, kappa, delta, P_aux, n_e, H) over the 0-D and equilibrium "
           "handlers already registered.  A composition of `zerod` and "
           "`discharge` at interactive cadence, not a capability of its own; "
           "Python composes the same pieces through `scenario.model`",
}
BROWSER_ONLY_BARS = MappingProxyType(_BROWSER_ONLY_BARS)

#: The four lines.  ``frs`` mirrors FYL-DESIGN-07 §8 row for row: ``id`` the
#: requirement, ``v`` the verdict glyph, ``at`` the tool it landed on (None
#: when none), ``why`` the reason code for a ``—``.
_LINES: dict[str, dict] = {
    "design": {
        "title": "放电设计", "srs": "FYTOK-SRS-12 v0.7",
        "tools": ("discharge", "breakdown", "feasible", "zerod"),
        "frs": (
            ("S11-FR-INV-1", "●", "discharge", None),
            ("S11-FR-OPT-4", "●", "feasible", None),
            ("S11-FR-OPT-1/2", "—", None, "D-3"),
            ("S11-FR-OPT-3", "—", None, "D-3"),
            ("S11-FR-ENG-1", "—", None, "DEP04"),
            ("S10-FR-ENG-1", "●", "zerod", None),
            ("S10-FR-ENG-2", "○", None, None),
            ("S10-FR-DRV-1", "◐", "zerod", None),
            ("S10-FR-DRV-2", "○", None, None),
            ("S10-FR-LIM-1/2", "●", "breakdown", None),
        ),
    },
    "control": {
        "title": "控制仿真", "srs": "FYTOK-SRS-09 v0.3",
        "tools": ("vstab", "coupled"),
        "frs": (
            ("S9-FR-EVO-1", "◐", "vstab", None),
            ("S9-FR-EVO-2", "◐", "coupled", None),
            ("S9-FR-CTRL-1", "○", None, None),
            ("S9-FR-CTRL-4", "○", None, None),
            ("S9-FR-CTRL-2", "—", None, "D-3"),
            ("S9-FR-PS-1/2", "—", None, "UPSTREAM"),
        ),
    },
    "model": {
        "title": "物理建模", "srs": "FYTOK-SRS-07 v0.4",
        "tools": ("discharge", "reconstruction", "zerod", "transport",
                  "coupled", "evolve", "tglf"),
        "frs": (
            ("S7-FR-EQ-1/2/3", "●", "discharge", None),
            ("S7-FR-PULSE-1/2", "●", "zerod", None),
            ("S7-FR-PULSE-3/4", "—", None, "SCOPE"),
            ("S7-FR-TR-1..5", "●", "transport", None),
            ("S7-FR-LOOP-1", "●", "coupled", None),
        ),
    },
    "analysis": {
        "title": "实验分析", "srs": "FYTOK-SRS-08 v0.1",
        "tools": ("reconstruction", "zerod"),
        "frs": (
            ("S8-FR-RECON-1", "●", "reconstruction", None),
            ("S8-FR-OP-2", "◐", "reconstruction", None),
            ("S8-FR-OP-4", "—", None, "RETIRED"),
            ("S8-FR-OP-3", "—", None, "DATA"),
            ("S8-FR-INF-1", "—", None, "D-3"),
            ("S8-FR-INF-2", "◐", "zerod", None),
        ),
    },
}
LINES = MappingProxyType({k: MappingProxyType(v) for k, v in _LINES.items()})


def line_of(tool: str) -> tuple[str, ...]:
    """Every line a tool serves — membership, not ownership.

    A tool belongs to as many lines as it serves (0-D serves both machine
    design and physics modelling) and says a different thing on each, which
    is why the reduced-tier note is keyed by tool and the verdict by
    (line, FR).
    """
    if tool not in TOOLS:
        raise KeyError(f"unknown tool {tool!r}; have {sorted(TOOLS)}")
    return tuple(k for k, v in LINES.items() if tool in v["tools"])


def tools_of(line: str) -> tuple[str, ...]:
    if line not in LINES:
        raise KeyError(f"unknown line {line!r}; have {sorted(LINES)}")
    return tuple(LINES[line]["tools"])


def provenance(tool: str, **extra) -> dict:
    """The D-2 statement that travels with a result.

    Carrying it in the result rather than in the caller's memory is the
    point: a number that has been copied into a slide has left every place
    the caveat was written down except this one.
    """
    t = TOOLS[tool] if tool in TOOLS else None
    if t is None:
        raise KeyError(f"unknown tool {tool!r}; have {sorted(TOOLS)}")
    from .. import kernel
    out = {"tool": tool, "lines": line_of(tool), "fr": tuple(t["fr"]),
           "scope": t["scope"], "caveat": t["caveat"],
           "kernel_abi": kernel.ABI_VERSION}
    out.update(extra)
    return out


def coverage() -> tuple[dict, ...]:
    """The whole §8 table as rows — line, FR, verdict, where it landed."""
    rows = []
    for lid, L in LINES.items():
        for fr, v, at, why in L["frs"]:
            rows.append({"line": lid, "fr": fr, "verdict": v,
                         "at": at, "why": why})
    return tuple(rows)


from . import analysis, control, design, model  # noqa: E402,F401
