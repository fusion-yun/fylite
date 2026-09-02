"""The scenario corpus, runnable: case config -> Python entry, field by field.

★S-2（`FYL-REPORT-03` §10.3 / `TODO` §1.4）：盘上的 case 是**页面控件值**的会话
文档；本模块把每个 bar 的控件词表映射到对应 Python 入口的参数——**包括页面 JS
的合成层**（0-D 的相位网格规则、输运的 Miller 度规组装）——并经工具面
（``serve.call_mcp_tool``）运行，使每次校验都留下清单、验收与账本，
``fylite report`` 可呈现。

**The accounting is the deliverable.**  Every config key of every case is
classified, and the gate (``test_case_runs.py``) refuses an unclassified key:

* ``map``     — consumed by the Python entry (with its unit conversion);
* ``sub``     — engaged only by a named worker-side sub-capability of the
  same bar (Monte-Carlo UQ, the flux account, the turbulent outer loop…);
  running the base case without them is faithful because the base run on the
  page does not read them either;
* ``shared``  — the design page's shared plasma scalars, exported with every
  bar on that page but not consumed by this bar's call;
* ``ui``      — display state (a slider position, a fold).

**Refusals are by name** (宁可拒绝，不给假数).  A bar whose knob vocabulary has
no Python counterpart is refused with the reason, not approximated:

* ``pulse`` / ``profile`` / ``series`` / ``batch`` / ``interp`` — browser-only
  by declaration (:data:`..BROWSER_ONLY_BARS`);
* ``evolve`` — refused PER CASE rather than per bar since 2026-08-26: the
  bar's time loop is the kernel's now (`evolve_heat`), so a case inside that
  entry's declared scope runs, and one outside it is refused with the
  FEATURE named (:data:`_EVOLVE_UNSUNK` plus the four scope tests).  That
  table is the remaining work list — measured on the corpus: **11 of 13**
  cases run since the pedestal was sunk (2026-08-26), and the last two want
  the device / g-file geometry tiers with the current channel and the
  sawtooth.
* ``reconstruction`` — ``analysis.reconstruction`` exists, but the case
  freezes the SYNTHETIC-TWIN generator's knobs, and that generator (measured
  probes/loops from a twin equilibrium plus seeded noise) lives in
  ``worker.js`` with no Python counterpart.

★页面合成层的单源原则：凡内核已单源的（梯形波形 ``K.zerod_waveform``、Miller 边界
``target_boundary``、面元度规 ``K.geo_surface``）经内核走；本模块只**复刻页面的
组装规则**（网格尺寸、源形状、初值形状），并逐条注明出处行为准。
"""
from __future__ import annotations

import json
import math
from contextlib import contextmanager
from pathlib import Path

from . import BROWSER_ONLY_BARS, TOOLS

# --------------------------------------------------------------------------- #
# the corpus on disk
# --------------------------------------------------------------------------- #
class CorpusMissing(Exception):
    """语料不在场 —— **缺输入，不是缺实现**。

    ★★2026-09-01：这里原本直接抛 `SystemExit`。那是 CLI 面的正确形状（`fylite
    cases` 该以非零码退出并把话说清楚），但对**库调用者**是个意外形状：
    `SystemExit` 继承自 `BaseException`，寻常的 `except Exception` 接不住，
    pytest 把它当致命错误——语料移出本仓那天，五个模块因此报 ERROR 而不是 skip，
    而且有一处在 fixture 里退化成裸 `AssertionError`，与真缺陷再也分不开。

    ★★它是普通 `Exception`，不是 `SystemExit` 的子类——第一版试过后者（想让 CLI
    行为一字不变），**不成立**：`SystemExit` 是 `BaseException`，pytest/pluggy 的
    hook wrapper 接不住它，五个 setup 阶段的错误照旧，而且在 fixture 里退化成裸
    `AssertionError`。库抛库的异常，退出码是 CLI 的事——`engine.cli` 在 `cli_main`
    收口处把它翻成一行说明加非零码。
    """



def corpus_dir(explicit=None) -> Path:
    """The `cases/` corpus — repo data, not wheel data; absent → refuse.

    ★An empty listing would read as「没有算例」, which is a different fact
    from「语料不在」— same posture as the machine decks.

    ★★2026-09-02 语料**搬了两次，落在仓根 `cases/`**（用户裁定）。它在内核仓的
    `cases/` 里待到分仓之后——而它的消费者（本模块、`fylite cases`、进轮的
    CLI）全在公开仓，于是「开箱即断」：`fylite cases` 在本仓找不到语料，要显式
    `--dir` 指到另一个仓去。搬过来，并从 `docs/` 提到仓根：它是**语料**，不是
    文档的一章——`docs/` 那一版的理由（「与 V&V 登记册同处」）已随登记册留在内核
    仓而作废。
    ★**V&V 登记册的机器半边没有跟过来**（`registry.jsonld` 与 `scenarios/` 仍在
    内核仓）：它的 `account` 字段有 11 处指向 `docs/note/benchmark/` 的散文报告，
    而那些在**私有**仓——把它搬进公开仓，等于让公开读者去解析一批他打不开的路径。
    ★仍然 **`app/` 里没有任何东西读它**：浏览器那份副本 2026-09-01 撤除，所以只有
    一份语料，没有需要保持同步的发布子集。
    """
    here = Path(__file__).resolve().parents[3]
    roots = ([Path(explicit)] if explicit else
             #: 仓根优先；`docs/cases` 作为旧位置仍认，免得别处的检出一换就断。
             [Path("cases"), here / "cases",
              Path("docs/cases"), here / "docs" / "cases"])
    for r in roots:
        if (r / "catalogue.jsonld").is_file():
            return r
    raise CorpusMissing(
        "fylite cases: no corpus found (looked for catalogue.jsonld in "
        + ", ".join(str(r) for r in roots)
        + ") — the scenario corpus is repository data and does not ship "
          "with the wheel; run from a checkout or pass --dir")


def _deck_root() -> Path:
    """Where the machine decks live — ``machine_desc/`` at the checkout root.

    ★★NOT ``corpus_dir().parent``, which is what this was.  That spelling was
    right only while the corpus sat at the repo root, and it broke silently
    the day the corpus moved into ``docs/`` (2026-09-01): the decks were then
    looked for at ``docs/machine_desc/`` and every device-bound case refused
    by name.  The decks and the corpus are two independent trees; deriving
    one's location from the other's is a coupling neither of them declares.
    """
    here = Path(__file__).resolve().parents[3] / "machine_desc"
    return here if here.is_dir() else Path("machine_desc")


#: ★★THE CATALOGUE'S OWN VOCABULARY, and where it went.
#:
#: ``fylite:cases`` (the entry list) and, per entry, ``fylite:case_id`` /
#: ``fylite:document`` / ``fylite:bar`` / ``fylite:order`` /
#: ``fylite:initial`` / ``fylite:device``, plus ``fylite:case`` (the
#: descriptive block inside a case document, carrying ``fylite:name`` and
#: ``fylite:name_en``).
#:
#: These used to be listed in ``python/fylite/_fyo_vocab.json``, the SHARED
#: vocabulary, whose entry criterion is 「more than one host writes it」 — the
#: browser read the catalogue to build its menus, this module reads it to run
#: the corpus.  The browser stopped reading it on 2026-09-01 (the case menus
#: went with the corpus's move under ``docs/``), so they are single-host terms
#: now and left that list by its own rule: a term one host writes cannot
#: disagree with itself, and keeping it there would have made the criterion
#: mean nothing.  ★They are still the catalogue's contract, and
#: ``fylite cases --check`` is still what enforces it — that is why they are
#: written down here rather than only in a commit message.
#:
#: ``fylite:device`` names a machine DECK, resolved by :func:`_deck_root`
#: (``machine_desc/`` at the checkout root) and NOT relative to this corpus.
#:
#: ★``fylite:initial`` HAS CHANGED MEANING and the data was left alone.  It
#: used to mark the one case a bar applied on a reader's first visit; nothing
#: applies anything on a visit any more.  What it still marks — and what
#: ``fylite cases --check`` still enforces, at most one per bar — is the bar's
#: designated STARTING case, which is what ``fylite cases`` prints as
#: ``*initial``.  The rule outlived its original consumer because「哪一份是这条
#: 栏的起点」 is a fact about the corpus, not about a browser.


def catalogue(d: Path | None = None) -> list[dict]:
    d = corpus_dir() if d is None else Path(d)
    doc = json.loads((d / "catalogue.jsonld").read_text(encoding="utf-8"))
    return list(doc["fylite:cases"])


def load(case_id: str, d: Path | None = None) -> tuple[dict, dict]:
    """catalogue entry + case document for ``case_id`` — or refuse by name."""
    d = corpus_dir() if d is None else Path(d)
    for e in catalogue(d):
        if e.get("fylite:case_id") == case_id:
            doc = json.loads((d / e["fylite:document"]).read_text(
                encoding="utf-8"))
            return e, doc
    raise SystemExit(f"fylite cases: no case {case_id!r} in {d}")


# --------------------------------------------------------------------------- #
# shared classification helpers
# --------------------------------------------------------------------------- #
#: the design page's shared plasma scalars — exported with every bar of that
#: page, consumed by the page's figures and by OTHER bars' calls
_DESIGN_SHARED = "design 页共享等离子体标量：随每个 bar 导出，本 bar 的调用不消费"


class Accounting:
    """Every key lands in exactly one bin, with the reason."""

    def __init__(self, cfg: dict):
        self.pending = dict(cfg)
        self.mapped: dict[str, str] = {}
        self.sub: dict[str, str] = {}
        self.shared: dict[str, str] = {}
        self.ui: dict[str, str] = {}
        self.notes: list[str] = []

    def take(self, key, dest: str):
        v = self.pending.pop(key)
        self.mapped[key] = dest
        return v

    def _bin(self, bag, keys, reason):
        for k in keys:
            if k in self.pending:
                self.pending.pop(k)
                bag[k] = reason

    def as_sub(self, keys, reason):
        self._bin(self.sub, keys, reason)

    def as_shared(self, keys, reason=_DESIGN_SHARED):
        self._bin(self.shared, keys, reason)

    def as_ui(self, keys, reason="display state"):
        self._bin(self.ui, keys, reason)

    def summary(self) -> dict:
        return {"mapped": dict(self.mapped), "sub": dict(self.sub),
                "shared": dict(self.shared), "ui": dict(self.ui),
                "unclassified": sorted(self.pending), "notes": self.notes}


# --------------------------------------------------------------------------- #
# zerod — design page, `DESIGN.bar('zerod')`
# --------------------------------------------------------------------------- #
#: the page's time-grid rule (scenario-design.js: NT_MIN/NT_MAX/PTS_PER_PHASE)
_NT_MIN, _NT_MAX, _PTS_PER_PHASE = 120, 1200, 20


def _zerod_grid(ph: dict) -> int:
    """`gridSize()` verbatim: enough points to resolve the shortest phase."""
    span = ph["t_end"] - ph["t_breakdown"]
    lens = [ph["t_rampup_end"] - ph["t_breakdown"],
            ph["t_flattop_end"] - ph["t_rampup_end"],
            ph["t_end"] - ph["t_flattop_end"]]
    short = min([d for d in lens if d > 0], default=0.0)
    if not (span > 0 and short > 0):
        return _NT_MIN
    return max(_NT_MIN, min(_NT_MAX, math.ceil(_PTS_PER_PHASE * span / short) + 1))


def _zerod_args(cfg: dict, acct: Accounting, *, predict: bool) -> dict:
    ph = {"t_breakdown": 0.0,
          "t_rampup_end": float(acct.take("t_rampup_end", "phases")),
          "t_flattop_end": float(acct.take("t_flattop_end", "phases")),
          "t_end": float(acct.take("t_end", "phases"))}
    nt = _zerod_grid(ph)
    args: dict = {
        "phases": ph,
        #: the page's own grid, spelled as data — the trapezoid itself is the
        #: kernel's (`K.zerod_waveform`), single-sourced across hosts
        "time": [ph["t_breakdown"]
                 + (ph["t_end"] - ph["t_breakdown"]) * i / (nt - 1)
                 for i in range(nt)],
        "n_rho": 41,                       # page NR = 41 == entry default
        "ip_flattop": acct.take("ip", "ip_flattop") * 1e3,      # kA -> A
        "ne_flattop": acct.take("ne", "ne_flattop") * 1e19,     # 1e19 m^-3
        "te_flattop": float(acct.take("te", "te_flattop")),     # keV
        "ti_over_te": float(acct.take("tite", "ti_over_te")),
        "peaking_n": float(acct.take("pn", "peaking_n")),
        "peaking_t": float(acct.take("pt", "peaking_t")),
        "r0": float(acct.take("r0", "r0")),
        "a": float(acct.take("a", "a")),
        "kappa": float(acct.take("kappa", "kappa")),
        "zeff": float(acct.take("zeff", "zeff")),
        "dt_fraction": float(acct.take("dtf", "dt_fraction")),
        "nbi": {"power_w": acct.take("pnbi", "nbi.power_w") * 1e6,  # MW -> W
                "t_on": float(acct.take("t_on", "nbi.t_on")),
                "t_off": float(acct.take("t_off", "nbi.t_off"))},
    }
    #: edge_frac 0.05 / li 0.9 are page constants == the entry's defaults
    #: (`par` array positions 3 and 8); nothing to carry.
    law_idx = int(acct.take("tau_law", "law (predict)"))
    from .. import kernel as K
    args["law"] = K.TAU_LAWS[law_idx]
    args["h_factor"] = float(acct.take("hfac", "h_factor (predict)"))
    args["m_eff"] = float(acct.take("meff", "m_eff (predict)"))
    args["w0"] = acct.take("w0", "w0 (predict)") * 1e6           # MW -> W
    args["predict"] = bool(predict)
    if not predict:
        acct.notes.append("law/h_factor/m_eff/w0 are mapped but engaged only "
                          "with --predict (the page's tier-B button)")
    acct.as_sub(["uqon", "uqn", "uqsne", "uqste", "uqsip", "uqseed"],
                "Monte-Carlo UQ — the worker's `zerodmc`, a sub-capability "
                "with no Python entry")
    acct.as_sub(["eqauto", "dl", "du", "pfscale"],
                "the bar's equilibrium side-view (worker `solve` at the "
                "slice) — a different call of the same bar")
    acct.as_sub(["phiavail"],
                "the poloidal-flux account (worker `zerodflux`)")
    acct.as_ui(["slice"], "the time-slice slider position")
    return args


# --------------------------------------------------------------------------- #
# transport — model page, `MODEL.bar('transport')`
# --------------------------------------------------------------------------- #
#: page closure indices (scenario-model.js `solve()` / kernel TRANSPORT_MODELS)
_CLOSURES = {0: "constant", 1: "stiff", 2: "neoclassical"}


def _transport_args(cfg: dict, acct: Accounting) -> dict:
    import numpy as np
    from .. import kernel as K

    cl = int(acct.take("closure", "closure"))
    if cl == 3:
        raise SystemExit(
            "case closure 3 (turbulent) is the worker's `transport_turb` "
            "OUTER LOOP — a page-side Picard iteration over TGLF calls with "
            "no Python entry; refused rather than approximated")
    if cl == 2:
        #: honest limit, stated not silently narrowed: the neoclassical
        #: closure needs the page's physical-surface blocks (`neoBlocks`),
        #: whose assembly this module has not transcribed yet
        raise SystemExit(
            "case closure 2 (neoclassical) needs the page's per-surface "
            "physical blocks (`neoBlocks`); not transcribed yet — refused "
            "rather than run with the wrong closure")

    n = int(acct.take("n", "rho grid size"))
    a = float(acct.take("amin", "rho grid span [m]"))
    x = np.linspace(0.0, a, n)
    rb = x / x[-1] if x[-1] > 0 else x

    #: `metrics()` verbatim: parabolic q from 1 to q95, Miller surface per
    #: point through the kernel's own `geo_surface` (scale-covariant: metres
    #: in, dV/dr in m^2 out), ntheta = 201 as the page passes
    qa = float(acct.take("q95", "metric q(r) edge"))
    rmaj = acct.take("rmaj", "metric R0 (as R0/a)") * a
    kappa = float(acct.take("kappa", "metric kappa"))
    delta = float(acct.take("delta", "metric delta"))
    vp = np.zeros(n)
    gr = np.ones(n)
    for i in range(1, n):
        q = 1.0 + (qa - 1.0) * rb[i] ** 2
        shear = rb[i] * (2.0 * (qa - 1.0) * rb[i]) / q
        g = K.geo_surface(rmin_over_a=x[i], rmaj_over_a=rmaj, q=q,
                          shear=shear, kappa=kappa, s_kappa=0.0,
                          delta=delta, s_delta=0.0, ntheta=201)
        vp[i] = g["volume_prime"] if "volume_prime" in g else g["volumePrime"]
        gr[i] = g["fsa_grad_r2"] if "fsa_grad_r2" in g else g["fsaGradR2"]
    gr[0] = gr[1] if n > 1 else 1.0

    p0 = float(acct.take("power", "source amplitude"))
    w = float(acct.take("width", "source width"))
    edge = float(acct.take("edge", "edge_value"))
    args = {
        "rho": x.tolist(),
        "vprime": vp.tolist(),
        "metric": (vp * gr).tolist(),
        "source": (p0 * np.exp(-((rb / w) ** 2))).tolist(),
        "y_init": (edge + 2.0 * (1.0 - rb ** 2)).tolist(),
        "edge_value": edge,
        "closure": _CLOSURES[cl],
        "chi0": float(acct.take("chi0", "chi0")),
        "velocity": [float(cfg["pinch"])] * n,
        "d_pc": float(acct.take("dpc", "d_pc")),
        #: dt = inf / theta = 1 / p1 = 0.25 / p2 = 1.75: page constants ==
        #: entry defaults
    }
    acct.take("pinch", "velocity (uniform)")
    acct.as_sub(["bunit", "ne0", "nepeak"],
                "consumed only by the neoclassical / turbulent closures' "
                "physical-surface blocks (closure >= 2)")
    acct.as_sub(["turb-nrad", "turb-nky", "turb-outer"],
                "the turbulent outer loop (worker `transport_turb`)")
    return args


# --------------------------------------------------------------------------- #
# breakdown — design page, `DESIGN.bar('breakdown')`
# --------------------------------------------------------------------------- #
def _breakdown_args(cfg: dict, acct: Accounting) -> dict:
    args = {
        "r0": float(acct.take("nullr", "r0 (null centre)")),
        "z0": float(acct.take("nullz", "z0 (null centre)")),
        "radius": float(acct.take("radius", "radius")),
        "b_tol": acct.take("btol", "b_tol") * 1e-3,          # mT -> T
        "weight_null": float(acct.take("wnull", "weight_null")),
        "weight_flux": float(acct.take("wflux", "weight_flux")),
        "limits": bool(acct.take("uselimits", "limits")),
    }
    if bool(acct.take("usefluxTarget", "flux_target gate")):
        args["flux_target"] = float(acct.take("flux", "flux_target"))
    else:
        acct.as_ui(["flux"], "flux slider inert while usefluxTarget is off")
    args["i_max_aturn"] = acct.take("imax", "i_max_aturn (uniform)") * 1e3
    if bool(acct.take("usexref", "x_ref gate")):
        raise SystemExit(
            "usexref wants the machine's reference coil currents "
            "(`M.reference.aturns`); wiring that read is not done — refused "
            "rather than solved without the bias the case asked for")
    #: lam 1e-12 / nRing / nTheta: page constants; lam == entry default,
    #: the ring/theta counts are the null-grid resolution inside the entry
    acct.as_shared(["ip", "r0", "a", "kappa", "du", "dl"])
    return args


# --------------------------------------------------------------------------- #
# discharge — design page, `DESIGN.bar('discharge')`
# --------------------------------------------------------------------------- #
def _discharge_args(cfg: dict, acct: Accounting) -> dict:
    target = {
        "r0": float(acct.take("r0", "target.r0")),
        "a": float(acct.take("a", "target.a")),
        "kappa": float(acct.take("kappa", "target.kappa")),
        "delta_upper": float(acct.take("du", "target.delta_upper")),
        "delta_lower": float(acct.take("dl", "target.delta_lower")),
        "z0": float(acct.take("z0", "target.z0")),
    }
    prof = acct.take("profsrc", "profile source")
    if prof != "analytic":
        raise SystemExit(
            f"profsrc {prof!r} wants the machine's delivered reference "
            "profile tables; only the analytic family is mapped — refused "
            "rather than swapped")
    start = acct.take("startmode", "start mode")
    if start != "auto":
        raise SystemExit(
            f"startmode {start!r} means the page's CURRENT slider state is "
            "the start — state a case does not carry; only 'auto' "
            "(a designed start, `start_state`) is mappable")
    args: dict = {
        "target": target,
        "ip": acct.take("ip", "ip") * 1e3,                    # kA -> A
        "beta0": float(acct.take("beta0", "beta0")),
        "emp": float(acct.take("emp", "emp")),
        "enp": float(acct.take("enp", "enp")),
        "gamma": float(acct.take("gamma", "gamma")),
        "passes": int(acct.take("passes", "passes")),
        #: aturns0 omitted == the page's startmode 'auto': the entry designs
        #: its own start (`start_state`), the same linear isoflux solve the
        #: worker's `start` command runs
        #: n_points 24 / the anneal schedule: page constants == entry default
        "max_iter": 600, "relax": 0.3,   # the page's `solve:` block, verbatim
    }
    icap = acct.take("icap", "i_max (uniform)")
    if icap > 0:
        args["i_max"] = icap * 1e3
    else:
        acct.notes.append("icap 0 == no per-channel cap (page currentCap())")
    if bool(acct.take("usex", "xpoint gate")):
        args["xpoint"] = (float(acct.take("xr", "xpoint.r")),
                          float(acct.take("xz", "xpoint.z")))
        args["x_weight"] = 1.0            # page xWeight = usex ? 1 : 0
        acct.as_sub(["xr2", "xz2"],
                    "the SECOND null of the page's null set (T-D18); the "
                    "entry takes one xpoint")
    else:
        acct.as_ui(["xr", "xz", "xr2", "xz2"],
                   "x-point sliders inert while usex is off")
    #: `class` selects limiter/divertor DRAWING and which nulls are offered;
    #: the call itself is decided by usex/xpoint
    acct.as_ui(["class"], "boundary-class toggle (drives usex/x sliders)")
    acct.as_ui(["showref", "wide"], "figure options")
    return args


# --------------------------------------------------------------------------- #
# evolve — model page, `MODEL.bar('evolve')`
# --------------------------------------------------------------------------- #
#: What the kernel's `evolve_heat` entry covers, and therefore what a case may
#: ask for.  ★Each row is a REFUSAL REASON, keyed by the config switch that
#: turns it on: a case that asks for one is refused BY NAME with the feature
#: named, never run with the feature silently dropped.  The batch that sinks
#: a feature deletes its row here — so this table IS the remaining work list,
#: and `fylite cases --plan` prints it per case.
#: What ``evolve_heat`` does NOT carry — READ FROM THE KERNEL'S OWN
#: DECLARATION (`fyo.rs`, `@fyo-block ENTRY_SCOPE`), never kept here.
#:
#: ★★It used to be a literal in this file, and the browser had the same
#: judgement spread across a dozen `if (sp.…)` in its own march.  Two hosts
#: deciding「在范围内吗」from two lists agree until the day a capability
#: sinks and only one list is edited — and then one host runs a discharge
#: the other refuses, under the same case name.  The ENTRY knows what it
#: does not carry, so it is the entry that says so.
#:
#: ★The kernel's table is the whole scope ledger; this dict is the
#: `unsunk` rows of it, which is what a refusal is written from.
def _scope_rows():
    from .. import _fyo_interface as _FI

    return _FI.BLOCKS["ENTRY_SCOPE"]


_EVOLVE_UNSUNK = {r["key"]: r["gloss"] for r in _scope_rows()
                  if r["units"] == "unsunk"}

#: the rows the entry needs turned ON — the same table, the other verdict
_EVOLVE_REQUIRED = {r["key"]: r["gloss"] for r in _scope_rows()
                    if r["units"] == "required"}


def _evolve_args(cfg: dict, acct: Accounting) -> dict:
    from .. import _deck_names as _D

    #: ★the scope test comes FIRST and is exhaustive before anything is
    #: mapped: a case half-mapped and then refused would have spent its
    #: budget describing a run that is not going to happen, and — worse —
    #: an unmapped switch left in `pending` reads as「未归类」rather than
    #: as「这个能力还没沉下来」.
    #: ★`closure` and `couple` are declared `unsunk` like the rest, but they
    #: are not booleans: a closure of 0 and a couple of 0 are IN scope.  The
    #: declaration says WHICH controls decide the scope; what counts as
    #: 「on」 for a numeric control is this host's reading of its own corpus,
    #: and it is written out rather than left to `truthy`.
    numeric = {"closure", "couple"}
    missing = [why for key, why in _EVOLVE_UNSUNK.items()
               if key not in numeric and cfg.get(key)]
    closure = str(cfg.get("closure", "0"))
    if closure != "0":
        missing.append(f"closure {closure} — {_EVOLVE_UNSUNK['closure']}")
    #: ★★S-2c 批四 — the traced tiers are sunk (`model._evolve_on_a_ladder`),
    #: but a case cannot CARRY the equilibrium: device and experimental decks
    #: stay out of this repository by rule, so the corpus holds controls and
    #: not data.  What is refused here is therefore not the capability but
    #: the missing FILE, and the two say different things to a reader — the
    #: first is「等下一批」, the second is「把那份件给我」.
    geom = cfg.get("geometry")
    if geom not in ("miller", "device", "gfile"):
        missing.append(f"the {geom!r} geometry tier (miller / device / gfile "
                       "are sunk)")
    elif geom != "miller":
        missing.append(
            f"the {geom!r} tier's equilibrium — the tier itself is sunk, but "
            "this case carries controls and not data (device and shot decks "
            "stay out of this repository).  Import the reference file and "
            "pass it as `equilibrium=`")
    if cfg.get("couple"):
        missing.append(f"{_EVOLVE_UNSUNK['couple']} (couple > 0)")
    for key, why in _EVOLVE_REQUIRED.items():
        if not cfg.get(key):
            missing.append(why)
    if missing:
        raise SystemExit(
            "this case is outside the sunk scope of `evolve_heat`; it needs "
            + "; ".join(sorted(missing))
            + ".  Those live in the browser loop until their own batch sinks "
              "them (TODO §1.4 S-2c) — refused rather than run without them, "
              "which would be a different discharge under this case's name")

    a = float(acct.take("amin", "a [m]"))
    args: dict = {
        "n_rho": int(acct.take("nlev", "n_rho")),
        "a": a,
        "r0": acct.take("rmaj", "r0 (slider is R0/a)") * a,
        "kappa": float(acct.take("kappa", "kappa")),
        "delta": float(acct.take("delta", "delta")),
        "q95": float(acct.take("q95", "q95")),
        "b0": float(acct.take("bunit", "b0")),
        "te_axis": acct.take("te0", "te_axis") * 1e3,          # keV -> eV
        "ti_axis": acct.take("ti0", "ti_axis") * 1e3,
        "ne_axis": acct.take("ne0", "ne_axis") * 1e19,
        "edge_te": acct.take("edgete", "edge_te") * 1e3,
        "edge_ti": acct.take("edgeti", "edge_ti") * 1e3,
        "edge_ne": acct.take("edgene", "edge_ne") * 1e19,
        "peaking_t": float(acct.take("peakt", "peaking_t")),
        "peaking_n": float(acct.take("peakn", "peaking_n")),
        "chi0": float(acct.take("chi0", "chi0")),
        "chi_ratio": float(acct.take("chiratio", "chi_ratio")),
        "d_pc": float(acct.take("dpc", "d_pc")),
        "p_e": acct.take("pe", "p_e") * 1e6,                   # MW -> W
        "p_i": acct.take("pi", "p_i") * 1e6,
        "dep_centre": float(acct.take("dep", "dep_centre")),
        "dep_width": float(acct.take("depw", "dep_width")),
        "dt": float(acct.take("dt", "dt")),
        "n_steps": int(acct.take("nsteps", "n_steps")),
        "dt_target": float(acct.take("dttarget", "dt_target")),
        "brem": bool(acct.take("brem", "brem")),
        "alpha": bool(acct.take("alpha", "alpha")),
        "dt_fraction": float(acct.take("dtfrac", "dt_fraction")),
        "zeff": float(acct.take("zeff", "zeff")),
        "pedestal": bool(acct.take("pedestal", "pedestal")),
        #: ★read ONLY by the pedestal on this tier (beta_N's denominator).
        #: ★★It stays PRESCRIBED even now that the current channel is sunk
        #: (2026-08-27, S-2c 批二): the channel solves psi from the
        #: prescribed q, it does not solve TO a requested I_p — the thing
        #: that would make `ip` a target is the I_p feedback (`ipctl`), and
        #: that is still in the browser loop.  So this is a statement about
        #: the discharge, and the reason is the controller, not the channel.
        "ip": acct.take("ip", "ip (pedestal beta_N only)") * 1e3,  # kA -> A
    }

    #: ★★S-2c 批二 — the current channel, and its two drives.
    #: `ohmic` / `bootstrap` are read ONLY when the channel is on, which is
    #: what the page does (`worker.js`: `if (ctx.channels.current &&
    #: sp.ohmic)`).  Forwarding them regardless would turn `evolve-default`
    #: — which declares `ohmic: true` beside `ch-current: false` — from a
    #: case that RUNS into a case that is refused, on the strength of a
    #: switch the page itself ignores.  They are classified as inert below
    #: instead, the same posture as the beam's knobs while the beam is off.
    current = bool(acct.take("ch-current", "current"))
    args["current"] = current
    if current:
        args.update(ohmic=bool(acct.take("ohmic", "ohmic")),
                    bootstrap=bool(acct.take("bootstrap", "bootstrap")),
                    v_loop=float(acct.take("vloop", "v_loop")))

    #: ★★S-2c 批三 — the sawtooth, on the same rule: the trigger is
    #: `q(0) < 1` and `q` is a RESULT only on the current channel, so the
    #: page keeps it behind `channels.current` (`worker.js`'s `evSawtooth`
    #: returns null without it) and so does this.  `sawmix` rides along only
    #: when the crash is on, for the reason the drives do.
    sawtooth = bool(acct.take("sawtooth", "sawtooth")) and current
    args["sawtooth"] = sawtooth
    if sawtooth:
        args["saw_mix"] = float(acct.take("sawmix", "saw_mix"))

    #: ★★S-2c 批五 — the prescribed driven current.  Read only with the
    #: channel, the same posture as the other drives, and the page agrees
    #: (`worker.js` adds it inside the `channels.current` block).  ★The
    #: slider is in kA and the entry takes amperes: one conversion, here.
    i_cd = float(acct.take("icd", "i_cd (slider is kA)")) * 1e3 if current \
        else 0.0
    if i_cd:
        args["i_cd"] = i_cd
    #: ★★S-2c 批五 — 「以参考剖面为初值」.  The FILE is not here: device and
    #: experimental decks stay out of this repository, so the corpus carries
    #: the switch and the caller carries the table.  `useref` therefore says
    #: 「this case wants a reference」, and a plan that mapped it to nothing
    #: would let a run start on the CONTROLS while claiming the reference.
    if acct.take("useref", "useref (needs a reference table)"):
        args["_needs_reference"] = True
    species = str(acct.take("species", "impurity") or "")
    conc = acct.take("cimp", "imp_conc (slider is per cent)") / 100.0
    if species and conc > 0:
        if species not in _D.ADAS_Z:
            raise SystemExit(
                f"impurity {species!r} is not in the kernel's ADAS table "
                f"({', '.join(sorted(_D.ADAS_Z))})")
        args.update(impurity=species, imp_conc=conc,
                    imp_z=_D.ADAS_Z[species])
    elif species or conc:
        acct.notes.append(
            f"impurity {species!r} at {conc:.4g} — one of the two is zero, so "
            "no impurity radiates (the page behaves the same way)")

    #: the switches that ARE off: classified, because「declared and off」 and
    #: 「not looked at」 are different facts and only the first is safe
    acct.as_sub(sorted(_EVOLVE_UNSUNK), "declared and OFF in this case; the "
                "capability is not sunk yet (see _EVOLVE_UNSUNK)")
    acct.as_sub(["geometry", "closure", "couple", "icd", "ch-heat"],
                "the scope test above read these directly")
    acct.as_sub(
        ["beampower", "beamenergy", "beamrtan", "beamz", "beamwidth",
         "beamdir", "beamstop", "beamf1", "beamf2", "beamf3", "beamshells",
         "beamorbit"], "the NBI executor's knobs (inert while `beam` is off)")
    acct.as_sub(
        ["lhpower1", "lhnpar1lo", "lhnpar1hi", "lhpower2", "lhnpar2lo",
         "lhnpar2hi", "lhuplo", "lhuphi", "lhetacd", "lhxi", "lhwidth",
         "lhshells"], "the LH executor's knobs (inert while `lh` is off)")
    acct.as_sub(
        ["waveramp", "waveflat", "waveend", "wavestart", "waveend2",
         "wavepower", "wavevloop", "wavefuel", "waveip"],
        "the waveform driver's knobs (inert while `wave` is off)")
    if not sawtooth:
        keys = ["sawmix"] if current else ["sawtooth", "sawmix"]
        acct.as_sub(keys, "the sawtooth (inert: it is off, or the current "
                          "channel that makes q a result is)")
    acct.as_sub(["ipkp", "ipki"], "the I_p controller's gains (inert)")
    acct.as_sub(
        ["turbevery", "turbnrad", "turbnky", "turbrelax", "fmiter", "fmtol",
         "fmdx", "fmdxmax", "fmrhomin", "fmouter", "fmotol", "fmorlx",
         "degp", "degf"],
        "the turbulent / flux-match closures' budgets (inert on closure 0)")
    acct.as_sub(["dchi", "pinch", "dchiz", "pinchz", "zfuel", "fuel"],
                "the density channel's transport and fuelling (channel off)")
    if not current:
        #: ★the page ignores these three without the channel, so they are
        #: INERT here rather than unmapped — 「declared and ignored, exactly
        #: as the page ignores it」 is a different fact from 「not looked
        #: at」, and only the first is safe to leave in a passing plan
        acct.as_sub(["vloop", "ohmic", "bootstrap"],
                    "the current channel's drives (inert while the channel "
                    "is off, as on the page)")
    acct.as_sub(["freeiter", "couplefixed", "relax", "edgepsin"],
                "the equilibrium side (geometry prescribed on this tier)")
    acct.as_sub(["torque", "prandtl"], "the momentum channel's two numbers")
    return args


# --------------------------------------------------------------------------- #
# the registry, the plan, the run
# --------------------------------------------------------------------------- #
_BUILDERS = {"zerod": _zerod_args, "transport": _transport_args,
             "breakdown": _breakdown_args, "discharge": _discharge_args,
             "evolve": _evolve_args}

#: why each un-runnable bar is refused — BY NAME, so the gate can require a
#: reason for every bar the corpus carries
REFUSALS = {
    **{bar: f"browser-only by declaration: {why}"
       for bar, why in BROWSER_ONLY_BARS.items()},
    "reconstruction": (
        "`analysis.reconstruction` exists, but the case freezes the "
        "SYNTHETIC-TWIN generator's knobs, and that generator (twin "
        "measurements plus seeded noise) lives in worker.js with no Python "
        "counterpart."),
}


def args_for(bar: str, cfg: dict, *, predict: bool = False,
             acct: "Accounting | None" = None) -> dict:
    """Map ONE bar's control values to its Python entry's arguments.

    ★★This is `plan`'s middle, made reachable on its own, and the reason is
    a second caller with the same question: `app/tests/validate-evolve.mjs`
    compares the browser's march against a Python re-run, and the config it
    holds is the one the page EXPORTED — the same shape a shipped case is
    (`FySession.collect`, `fylite:config`).  Before this, that gate carried
    its own hand-written translation of the page's controls, so a unit or a
    default could be right in the corpus and wrong in the gate, or the other
    way round, with nothing to say so.  One mapper, two callers.

    Raises ``SystemExit`` with the missing capability NAMED when the config
    is outside the entry's sunk scope — a caller that cannot run this
    configuration should say which capability is absent, not fall back to
    something else.

    Returns the arguments only; use :func:`plan` when the accounting is
    wanted too — it passes its own ``acct`` in, so there is one call to the
    builder and not two code paths that could answer differently.
    """
    if bar in REFUSALS:
        raise SystemExit(f"bar {bar!r} is not runnable from Python — "
                         f"{REFUSALS[bar]}")
    if bar not in _BUILDERS:
        raise SystemExit(f"bar {bar!r} has no mapping and no registered "
                         "refusal — that is a gap in scenario/cases.py")
    if acct is None:
        acct = Accounting({k: v for k, v in cfg.items() if ":" not in k})
    kw = {"predict": predict} if bar == "zerod" else {}
    return _BUILDERS[bar](cfg, acct, **kw)


def plan(case_id: str, d=None, *, predict: bool = False) -> dict:
    """The mapping for one case: tool, arguments, and the full accounting.

    Refuses — by name, with the reason — a case whose bar has no faithful
    Python mapping.  Never drops a key silently: unclassified keys survive
    into ``accounting["unclassified"]`` for the gate to catch.
    """
    entry, doc = load(case_id, d)
    bar = entry["fylite:bar"]
    if bar in REFUSALS:
        raise SystemExit(f"fylite cases --run {case_id}: bar {bar!r} is not "
                         f"runnable from Python — {REFUSALS[bar]}")
    if bar not in _BUILDERS:
        raise SystemExit(f"fylite cases --run {case_id}: bar {bar!r} has no "
                         "mapping and no registered refusal — that is a gap "
                         "in scenario/cases.py, not in the case")
    cfg = doc.get("fylite:config", {})
    #: ★the accounting is assembled HERE because `plan` owes it to its caller
    #: and `args_for` does not — but it is HANDED DOWN rather than rebuilt, so
    #: the corpus and the browser gate go through ONE call to the builder
    acct = Accounting({k: v for k, v in cfg.items() if ":" not in k})
    args = args_for(bar, cfg, predict=predict, acct=acct)
    tool = next(t for t, spec in TOOLS.items() if spec["bar"] == bar)
    return {"case_id": case_id, "bar": bar, "tool": tool,
            "device": entry.get("fylite:device"),
            "arguments": args, "accounting": acct.summary()}


@contextmanager
def _device_env(device: str | None):
    """Point the machine door at the checkout deck the catalogue names.

    ★Through :func:`fylite.device.bound`, not a bare env override: the
    device-derived constants are resolved once per process and PUBLISHED as
    module globals, so an env var alone would leave a previously-resolved
    machine's numbers in place — the run would solve the wrong tokamak with
    a clean conscience.  `bound` swaps them with a restore contract.
    """
    if not device:
        yield
        return
    deck = _deck_root() / device
    if not deck.is_dir():
        raise SystemExit(f"catalogue names device {device!r} but "
                         f"{deck} is not a directory")
    from .. import device as _device_mod
    with _device_mod.bound(deck):
        yield


def run(case_id: str, d=None, *, predict: bool = False) -> dict:
    """Map and RUN one case through the tool face.

    Through ``serve.call_mcp_tool`` deliberately: the run then leaves the
    same manifest / acceptance / ledger every other recorded call leaves,
    and ``fylite report`` can present it.  Bulk arrays travel inline here
    (the mapping IS the caller), so the record notes them as digests — such
    a node is honest about not being replayable.
    """
    p = plan(case_id, d, predict=predict)
    from ..engine import serve
    with _device_env(p["device"]):
        out = serve.call_mcp_tool(f"fylite_{p['tool']}", p["arguments"])
    if out.get("isError"):
        raise SystemExit(f"fylite cases --run {case_id}: the run failed — "
                         + out["content"][0]["text"])
    result = json.loads(out["content"][0]["text"])
    return {**p, "run": result.get("run"), "run_dir": result.get("run_dir"),
            "result_keys": sorted(result)}
