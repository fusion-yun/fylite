"""The scenario corpus, runnable: case config -> Python entry, field by field.

★S-2（`FYL-REPORT-03` §10.3 / `TODO` §1.4）：盘上的 case 是**页面控件值**的会话
文档（★2026-09-02 起改写为 fyo/spo 的 `fyo:ScenarioSpecification`：控件值成为
`spo:has_parameter_setting` 的 JSON 字面量，bar 由 `prescribes_code` 的 IRI
`code/<bar>` 给出，装置牌由 `about_discharge.performed_on` 反向到的
`fyo:MachineDescription` 给出——见下方 :func:`settings` / :func:`bar_of` /
:func:`device_of`；`FYL-REPORT-06` B-7）；本模块把每个 bar 的控件词表映射到对应 Python 入口的参数——**包括页面 JS
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
  by declaration (:data:`fylite.scenario.BROWSER_ONLY_BARS`);
* ``reconstruction`` — ``analysis.reconstruction`` exists, but a case of that
  bar freezes the SYNTHETIC-TWIN generator's knobs, and that generator
  (measured probes/loops from a twin equilibrium plus seeded noise) lives in
  ``worker.js`` with no Python counterpart.
* ``evolve`` — refused PER CASE rather than per bar since 2026-08-26: the
  bar's time loop is the kernel's now (`evolve_heat`), so a case inside that
  entry's declared scope runs, and one outside it is refused with the
  FEATURE named (:data:`_EVOLVE_UNSUNK` plus the four scope tests).  That
  table is the remaining work list — measured on the corpus after the
  2026-09-04 convergence: **3 of 5** evolve cases run, and the two refusals
  are of DIFFERENT kinds — `evolve-east-hmode` wants the device tier's
  equilibrium (a FILE this repository does not carry, 「把那份件给我」) and
  `evolve-jintrac-iter-15ma-flattop` wants closure 3 (a CAPABILITY not yet
  sunk, 「等下一批」).

★★两条 bar 级的拒绝**留在表里而语料里没有对应算例**（2026-09-04）：那四条跑不了
的算例撤了，能力边界却没有变——它由 :data:`fylite.scenario.BROWSER_ONLY_BARS` 与
:data:`REFUSALS` **按名**声明，不靠一份跑不了的算例来记。写一条那样的算例进语料，
仍会被这里按名拒绝。

★页面合成层的单源原则：凡内核已单源的（梯形波形 ``K.zerod_waveform``、Miller 边界
``target_boundary``、面元度规 ``code/transport`` 的 Miller 档）经内核走；本模块只**复刻页面的
组装规则**（网格尺寸、源形状、初值形状），并逐条注明出处行为准。
"""
from __future__ import annotations

import json
import math
from contextlib import contextmanager
from pathlib import Path


def _browser_only_bars() -> dict:
    """The bars declared browser-only — from :mod:`fylite.scenario`, lazily."""
    from ..scenario import BROWSER_ONLY_BARS
    return BROWSER_ONLY_BARS

#: ★★``BROWSER_ONLY_BARS`` / ``TOOLS`` live in :mod:`fylite.scenario`, which
#: pulls numpy and the four assembly subpackages.  They are imported INSIDE the
#: two functions that use them, because ``fylite.engine`` is stdlib-pure at
#: import time (FYL-SDD-01 DE-COMP-03, gated by
#: ``tests/test_engine_imports_only_stdlib.py``) — and a corpus catalogue that
#: loaded the whole assembly layer just to be listed would breach that.

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



class RunFailed(Exception):
    """一次运行没跑成 —— **库抛库的异常**，退出码是 CLI 的事。

    ★★与 :class:`CorpusMissing` 同一条教训，同一处代价（那条抬头写着 2026-09-01
    的经过）：这里原本抛 `SystemExit`。它是 `BaseException`，寻常的
    `except Exception` 接不住；更要命的是**在 fixture 里**——pytest / pluggy 的
    hook wrapper 接不住它，于是退化成一个裸 `AssertionError`，五条测试报 ERROR
    而不是 skip，而报错里再也看不出原因是「内核不在场」。2026-09-02 实测复现：
    公开检出（无内核）跑 `test_whence.py`，正是这个形状。

    ★保留 `plan()` 那几处 `SystemExit`：它们是**参数不成立**（bar 不可跑、没有
    这个算例），是 CLI 面的拒绝，且已有测试按那个形状判。变的只有「跑了但没跑成」
    这一条——它是库调用者要接的。
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
    #: ★★★2026-09-04 用户裁定：**语料收进 `docs/examples/`，一个例子一个目录**
    #: （散文与它走的那几份 scenario 文件同住）。理由是那份散文与那份计划从来是
    #: 一件事的两半：读者读的那一章、与他照着跑的那份文档，此前隔着两棵树，
    #: 于是「改了计划忘了改章」是**没有任何一处会红**的失配。同住之后它是一次
    #: 编辑。★目录仍是**语料**（`catalogue.jsonld` 在 `docs/examples/` 根上），
    #: 只是它的每一项现在写成 `<章>/<文件>`。
    #: ★旧位置（仓根 `cases/`、更早的 `docs/cases/`）仍然认：别处的检出不该因为
    #: 一次搬家就断，而认错位置的代价只是多看两个目录。
    here = Path(__file__).resolve().parents[3]
    roots = ([Path(explicit)] if explicit else
             [Path("docs/examples"), here / "docs" / "examples",
              Path("cases"), here / "cases",
              Path("docs/cases"), here / "docs" / "cases"])
    for r in roots:
        if (r / "catalogue.jsonld").is_file():
            return r
    raise CorpusMissing(
        "the scenario corpus: no catalogue.jsonld found (looked in "
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


#: ★★THE CORPUS VOCABULARY IS fyo / spo (2026-09-02, `FYO-ADR-07` · `FYL-REPORT-06`
#: B-7 / K-5).  A case is one ``fyo:ScenarioSpecification`` (an ``spo:ComputationPlan``)
#: and the catalogue is an ICE whose ``has_part`` list names the plans in listing
#: order, each with the ``spo:Concretization`` (file) that carries it.  Where the
#: former private terms went:
#:
#: * ``fylite:cases[]`` / ``fylite:case_id`` / ``fylite:document`` / ``fylite:order``
#:   → ``has_part`` (ordered) · the plan's ``id`` (``cases/<case_id>``) ·
#:   ``concretized_as[].storage_uri``;
#: * ``fylite:page`` / ``fylite:bar`` → ``prescribes_code`` = ``spo:Code`` with the IRI
#:   ``code/<bar>`` (:func:`bar_of`), plus ``prescribed_task_kind`` (the fyo
#:   application-task class);
#: * ``fylite:config{name: value}`` → ``has_parameter_setting[]`` — one
#:   ``spo:ParameterSetting`` per control, ``sets_parameter`` = ``code/<bar>#<name>``,
#:   the value a JSON literal (``@type: @json``), so ``"0"`` and ``0`` stay distinct
#:   (:func:`settings`);
#: * ``fylite:device`` → ``about_discharge.performed_on`` (``fyo:Tokamak``) reverse-linked
#:   to the deck as a ``fyo:MachineDescription`` with id ``machine_desc/<deck>``
#:   (:func:`device_of`) — a case ABOUT a machine without a bound deck names the
#:   machine and no description;
#: * ``fylite:case{name, note}`` → ``rdfs:label`` / ``rdfs:comment`` language maps;
#:   ``needs`` → open ``spo:PortBinding`` (data the caller supplies) or ``spo:caveat``
#:   (a capability this code lacks); ``source`` / ``provenance`` →
#:   ``spo:generated_by_process``.
#:
#: ★``fylite:initial`` was DROPPED, not migrated: it marked the case a bar applied on a
#: reader's first visit, nothing applies anything on a visit any more (2026-09-01), and
#: fyo / spo have no term for「a menu's starting entry」— the listing order is the
#: only order the catalogue keeps.
#:
#: ``fylite cases --check`` enforces the contract, including K-5: no ``fylite:`` /
#: ``vv:`` token anywhere in a corpus document.


def _lang(v, lang="zh") -> str:
    """One string out of a language map (or a bare string)."""
    if isinstance(v, dict):
        return v.get(lang) or next((x for x in v.values() if x), "")
    return v or ""


def bar_of(doc: dict) -> str | None:
    """The bar a case prescribes: the last segment of its ``prescribes_code`` IRI."""
    code = doc.get("prescribes_code")
    cid = code.get("id", "") if isinstance(code, dict) else (code or "")
    return cid.rsplit("/", 1)[-1] or None


def device_of(doc: dict) -> str | None:
    """The machine DECK a case is bound to (``machine_desc/<deck>``), or None."""
    dis = doc.get("about_discharge") or {}
    tok = dis.get("performed_on") or {}
    desc = tok.get("described_by") or {}
    did = desc.get("id", "") if isinstance(desc, dict) else ""
    return did.rsplit("/", 1)[-1] or None


def settings(doc: dict) -> dict:
    """The control values of a case: ``{parameter name: JSON literal}``, in order."""
    out = {}
    for p in doc.get("parameters") or []:
        ref = p.get("sets_parameter", "")
        out[ref.rsplit("#", 1)[-1]] = p.get("literal_value")
    return out


def catalogue(d: Path | None = None) -> list[dict]:
    """The corpus listing: one entry per plan the catalogue names, in listing order.

    Each entry carries ``case_id`` / ``file`` from the catalogue and ``bar`` /
    ``device`` / ``task_kind`` / ``name`` from the document itself (``None`` where the
    document is absent or unreadable — ``fylite cases --check`` says which).
    """
    d = corpus_dir() if d is None else Path(d)
    cat = json.loads((d / "catalogue.jsonld").read_text(encoding="utf-8"))
    out = []
    for m in cat.get("has_part") or []:
        cid = str(m.get("id", "")).rsplit("/", 1)[-1]
        files = [c.get("storage_uri") for c in (m.get("concretized_as") or [])
                 if isinstance(c, dict) and c.get("storage_uri")]
        e = {"case_id": cid, "file": files[0] if files else None,
             "bar": None, "device": None, "task_kind": None, "name": ""}
        f = d / e["file"] if e["file"] else None
        if f is not None and f.is_file():
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                doc = None
            if isinstance(doc, dict):
                e.update(bar=bar_of(doc), device=device_of(doc),
                         task_kind=doc.get("prescribed_task_kind"),
                         name=_lang(doc.get("title")))
        out.append(e)
    return out


def load(case_id: str, d: Path | None = None) -> tuple[dict, dict]:
    """catalogue entry + case document for ``case_id`` — or refuse by name."""
    d = corpus_dir() if d is None else Path(d)
    for e in catalogue(d):
        if e["case_id"] == case_id:
            doc = json.loads((d / e["file"]).read_text(encoding="utf-8"))
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
        """One control -> one entry field, or a refusal that NAMES the control.

        ★A bare ``KeyError`` was what a stale mapper produced (2026-09-02:
        `_zerod_args` still spelled the entry's argument names, so every 0-D
        case died with `KeyError: 't_rampup_end'` and no reader could tell
        whether the case, the corpus or the mapper was wrong).  A mapping
        layer whose failure mode is a bare key name is a mapping layer that
        cannot be debugged from its own message.
        """
        if key not in self.pending:
            raise KeyError(
                f"the case carries no control {key!r} (wanted for {dest}); its "
                f"controls are: {', '.join(sorted(self.pending))} — control names "
                f"are the PAGE's, see app/assets/scenario-*.js CONTROLS")
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
    #: ★the control names are the PAGE's (`pulse_design-t_ru` / `-t_ft` / `-t_end`,
    #: `scenario-pulse_design.js` CONTROLS), not the entry's argument names.  This
    #: mapper spelled the ENTRY's names (`t_rampup_end` / `t_flattop_end` / `pnbi`)
    #: and every 0-D case therefore died in `take()` with a bare `KeyError` —
    #: measured 2026-09-02 on `zerod-iter-15ma`.
    ph = {"t_breakdown": 0.0,
          "t_rampup_end": float(acct.take("t_ru", "phases")),
          "t_flattop_end": float(acct.take("t_ft", "phases")),
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
        #: `paux` is the page's auxiliary power in MW (`scenario-pulse_design.js`:
        #: `var pAux = +$('paux').value * 1e6`), fed to the entry's NBI channel
        "nbi": {"power_w": acct.take("paux", "nbi.power_w") * 1e6,  # MW -> W
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

    #: `metrics()` — the parabolic q from 1 to q95 and one Miller surface per
    #: point, 201 theta — is the DOOR's own Miller tier now (T-4 第二十四刀,
    #: 2026-09-06): `model.transport` names the shape and `code/transport`
    #: builds V' and <|∇r|²> itself, the loop this function used to run on
    #: the flat `geo_surface` (the kernel's `test_transport_code.py` pins the
    #: two to the bit).  The five scalars are the bar's, as they were.
    qa = float(acct.take("q95", "metric q(r) edge"))
    rmaj = float(acct.take("rmaj", "metric R0 (as R0/a)"))
    kappa = float(acct.take("kappa", "metric kappa"))
    delta = float(acct.take("delta", "metric delta"))

    p0 = float(acct.take("power", "source amplitude"))
    w = float(acct.take("width", "source width"))
    edge = float(acct.take("edge", "edge_value"))
    args = {
        "rho": x.tolist(),
        "a": a, "rmaj": rmaj, "kappa": kappa, "delta": delta, "q95": qa,
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
    #: ★`closure` is declared `unsunk` like the rest, but it is not a
    #: boolean: a closure of 0 is IN scope (`couple` sank whole, 第二十刀).  The
    #: declaration says WHICH controls decide the scope; what counts as
    #: 「on」 for a numeric control is this host's reading of its own corpus,
    #: and it is written out rather than left to `truthy`.
    numeric = {"closure"}
    missing = [why for key, why in _EVOLVE_UNSUNK.items()
               if key not in numeric and cfg.get(key)]
    closure = str(cfg.get("closure", "0"))
    #: ★第十六刀: the neoclassical closure (2) is the entry's; 第十八刀: the
    #: turbulent one (3) too — the extension's door between blocks; 4 is not
    #: 第二十一刀: the flux-match tier (4) too — stages of the entry with the
    #: extension's chi between them; a closure the ledger does not know is refused
    if closure not in ("0", "2", "3", "4"):
        missing.append(f"closure {closure} is not one the entry knows (0 · 2 · 3 · 4)")
    #: ★★S-2c 批四 — the traced tiers are sunk (`case.rs::evolve`, the equilibrium document traced in the kernel),
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
    #: ★第十九·二十刀: the alternation (`couple > 0` on the device tier, the
    #: fixed-boundary refinement included) is the entry's — `code/refit` between
    #: blocks, `model.evolve(couple=…)`; it is a `sunk` row of the ledger now,
    #: and off the device tier the page reads `couple` as nothing at all
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
    #: ★`resume` sank on 2026-09-05 (the page's entry march runs the case one
    #: step per call and binds the lagged state back); a case runs whole, so
    #: the switch is inert here rather than out of scope
    acct.as_sub(["resume"], "a resumed state (sunk: the page's one-step-per-call march; a case runs whole, inert)")
    #: 第二十三刀: the heat pair is a switch of the entry (a density- or
    #: current-only march runs), no longer a `required` row of the ledger
    args["heat"] = bool(cfg.get("ch-heat", True))
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
    if not cfg.get("wave"):
        acct.as_sub(
            ["waveramp", "waveflat", "waveend", "wavestart", "waveend2",
             "wavepower", "wavevloop", "wavefuel", "waveip"],
            "the waveform driver's knobs (inert while `wave` is off)")
    if not sawtooth:
        keys = ["sawmix"] if current else ["sawtooth", "sawmix"]
        acct.as_sub(keys, "the sawtooth (inert: it is off, or the current "
                          "channel that makes q a result is)")
    if not cfg.get("ipctl"):
        acct.as_sub(["ipkp", "ipki"], "the I_p controller's gains (inert: the loop is off)")
    #: ★第十八刀 — the turbulent tier's cadence and budget ride along with
    #: closure 3 (`model.evolve(closure="turbulent", turb=…)`); inert otherwise
    if closure == "3":
        args["turb"] = dict(every=int(acct.take("turbevery", "TGLF cadence [steps]")),
                            n_rad=int(acct.take("turbnrad", "TGLF sampled radii")),
                            n_ky=int(acct.take("turbnky", "TGLF ky count")),
                            relax=float(acct.take("turbrelax", "TGLF relaxation")))
    elif closure != "4":
        acct.as_sub(["turbevery", "turbnrad", "turbnky", "turbrelax"],
                    "the turbulent closure's cadence and budget (inert: closure is not 3)")
    #: ★第二十一刀 — the flux-match tier's budgets ride along with closure 4
    #: (`model.evolve(closure="flux-match", fm=…)`); inert otherwise
    if closure == "4":
        args["fm"] = dict(n_rad=int(acct.take("turbnrad", "TGLF radii")), n_ky=int(acct.take("turbnky", "TGLF ky count")),
                          iter=int(acct.take("fmiter", "flux-match iterations")), tol=float(acct.take("fmtol", "flux-match tolerance")),
                          dx=float(acct.take("fmdx", "flux-match probe dx")), dx_max=float(acct.take("fmdxmax", "flux-match dx max")),
                          rho_min=float(acct.take("fmrhomin", "flux-match innermost radius")),
                          outer=int(acct.take("fmouter", "stationary rounds")), o_tol=float(acct.take("fmotol", "stationary tolerance")),
                          o_relax=float(acct.take("fmorlx", "stationary relaxation")))
        acct.as_sub(["turbevery", "turbrelax"], "the turbulent march's cadence and relaxation (inert: the flux-match tier does not march)")
        acct.as_sub(["degp", "degf"], "the fixed-boundary refinement's degrees (the equilibrium half is not on the Miller tier)")
    else:
        acct.as_sub(
            ["fmiter", "fmtol", "fmdx", "fmdxmax", "fmrhomin", "fmouter", "fmotol", "fmorlx",
             "degp", "degf"],
            "the flux-match closure's budgets (inert: closure is not 4)")
    #: ★★第十五刀 (2026-09-05) — the density channel, the impurity in the
    #: quasi-neutrality and the momentum channel are the entry's.  The
    #: sliders ride along only with their channel, the posture every other
    #: drive on this case takes; the page's `fuel` is in 1e20/s and the
    #: entry takes 1/s — one conversion, here.
    density = bool(acct.take("ch-density", "density"))
    args["density"] = density
    quasi = bool(acct.take("quasi", "quasi"))
    args["quasi"] = quasi
    if quasi and not species:
        raise SystemExit("`quasi` (the impurity in the quasi-neutrality) needs "
                         "a named impurity (`species`)")
    if density:
        args.update(d_over_chi=float(acct.take("dchi", "d_over_chi")),
                    pinch=float(acct.take("pinch", "pinch")),
                    fuel=float(acct.take("fuel", "fuel (slider is 1e20/s)")) * 1e20)
        if quasi:
            args.update(d_over_chi_z=float(acct.take("dchiz", "d_over_chi_z")),
                        pinch_z=float(acct.take("pinchz", "pinch_z")),
                        fuel_z=float(acct.take("zfuel", "fuel_z (slider is 1e20/s)")) * 1e20)
        else:
            acct.as_sub(["dchiz", "pinchz", "zfuel"],
                        "the impurity's transport and fuelling (inert: quasi is off)")
    else:
        acct.as_sub(["dchi", "pinch", "dchiz", "pinchz", "zfuel", "fuel"],
                    "the density channel's transport and fuelling (channel off)")
    momentum = bool(acct.take("ch-momentum", "momentum"))
    args["momentum"] = momentum
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
    if momentum:
        args.update(torque=float(acct.take("torque", "torque [N m]")),
                    prandtl=float(acct.take("prandtl", "prandtl")))
    else:
        acct.as_sub(["torque", "prandtl"], "the momentum channel's two numbers (channel off)")
    #: ★第十六刀 — the waveform, the I_p loop and the closure choice are the
    #: entry's.  The waveform's knobs ride along only when it is on; the
    #: controller needs the current channel (the page refuses the same way)
    args["closure"] = {"2": "neoclassical", "3": "turbulent", "4": "flux-match"}.get(closure, "constant")
    wave = bool(acct.take("wave", "wave"))
    if wave:
        args["wave"] = dict(
            ramp=float(acct.take("waveramp", "wave ramp end [s]")),
            flat=float(acct.take("waveflat", "wave flat-top end [s]")),
            end=float(acct.take("waveend", "wave end [s]")),
            start=float(acct.take("wavestart", "wave start fraction")),
            end2=float(acct.take("waveend2", "wave end fraction")),
            power=bool(acct.take("wavepower", "wave drives the powers")),
            vloop=bool(acct.take("wavevloop", "wave drives the loop voltage")),
            fuel=bool(acct.take("wavefuel", "wave drives the fuelling")),
            ip=bool(acct.take("waveip", "wave drives the I_p set point")))
    ipctl = bool(acct.take("ipctl", "ipctl"))
    if ipctl and not current:
        raise SystemExit("the I_p controller needs the current channel "
                         "(`ch-current`): it drives the boundary flux rate and "
                         "closes on the current read off psi")
    args["ipctl"] = ipctl
    if ipctl:
        args.update(ip_kp=float(acct.take("ipkp", "ip_kp")),
                    ip_ki=float(acct.take("ipki", "ip_ki")))
    #: ★第十七刀 — the two executors run inside `code/evolve` now, so their rows
    #: are `sunk` and no longer refused by the scope test; but a corpus case
    #: carries no `nbi` / `lh_antennas` DOCUMENT (the unit's geometry, the
    #: launchers' bands), and an executor without its document is a refusal
    #: by name, not a Gaussian under another name
    for key, doc in (("beam", "nbi"), ("lh", "lh_antennas")):
        if bool(acct.take(key, key)):
            raise SystemExit(f"case `{key}`: the executor runs inside code/evolve "
                             f"(第十七刀), but a corpus case carries no `{doc}` "
                             "document — write it and call model.evolve(nbi=… / "
                             "lh_antennas=…) directly")
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
       for bar, why in _browser_only_bars().items()},
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
                         "refusal — that is a gap in engine/cases.py")
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
    bar = entry["bar"]
    if bar in REFUSALS:
        raise SystemExit(f"fylite cases --run {case_id}: bar {bar!r} is not "
                         f"runnable from Python — {REFUSALS[bar]}")
    if bar not in _BUILDERS:
        raise SystemExit(f"fylite cases --run {case_id}: bar {bar!r} has no "
                         "mapping and no registered refusal — that is a gap "
                         "in engine/cases.py, not in the case")
    cfg = settings(doc)
    #: ★the accounting is assembled HERE because `plan` owes it to its caller
    #: and `args_for` does not — but it is HANDED DOWN rather than rebuilt, so
    #: the corpus and the browser gate go through ONE call to the builder
    acct = Accounting({k: v for k, v in cfg.items() if ":" not in k})
    args = args_for(bar, cfg, predict=predict, acct=acct)
    from ..scenario import TOOLS
    tool = next(t for t, spec in TOOLS.items() if spec["bar"] == bar)
    return {"case_id": case_id, "bar": bar, "tool": tool,
            "device": entry.get("device"),
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
        #: ★装置牌不在场 = **缺输入**（`machine_desc/` 按裁定不进版本库），
        #: 与语料不在场同一类，所以抛同一个异常：库调用者接得住，CLI 照旧翻译。
        raise CorpusMissing(f"catalogue names device {device!r} but "
                            f"{deck} is not a directory — device decks are "
                            "pulled on demand and are not in the repository")
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
        raise RunFailed(f"fylite cases --run {case_id}: the run failed — "
                        + out["content"][0]["text"])
    result = json.loads(out["content"][0]["text"])
    return {**p, "run": result.get("run"), "run_dir": result.get("run_dir"),
            "result_keys": sorted(result)}


#: Vocabularies retired from the corpus: a document still carrying one has not
#: been migrated (`fylite:` predates the fyo/spo convergence, `vv:` left with
#: the V&V register's own context).
_RETIRED_PREFIXES = ("fylite:", "vv:")

#: The corpus directory holds the catalogue and the shared ``@context`` beside
#: the cases.  Excepted BY NAME, not by pattern: an unrecognised ``.jsonld``
#: landing here is exactly the mistake :func:`problems` exists to catch.
_NOT_CASES = {"catalogue.jsonld", "context.jsonld"}

#: ★★2026-09-04：`scenario/` 住的不是算例，是**场景模板**——`fy run` 的参数表
#: （`FYL-DESIGN-17` E-11）。它形状上也是 `fyo:ScenarioSpecification`（模板就是一份
#: 把词表说全了的计划，于是 `fy run <模板>` 与 `fy run <线> <场景>` 走同一条合成），
#: 但它**不是这本目录登记的东西**：它自带目录 `scenario/lines.jsonld`，由
#: `tools/make-scenario-templates.py` 生成、由 `python/tests/test_scenario_templates.py`
#: 逐条对账。所以孤儿检查跳过这一棵——不跳的话，一份模板会被报成「谁也没引的计划」，
#: 而那句话是错的。★按**目录名**排除，与 `_NOT_CASES` 按文件名排除同一个姿态：
#: 落进 `docs/examples/` 别处的一份不认得的 `.jsonld` 仍然要被抓住。
_NOT_CASE_DIRS = {"scenario"}


def _case_problems(doc: dict, cid: str, bars: set) -> list[str]:
    """What is structurally wrong with ONE case document (empty = sound)."""
    out = []
    if doc.get("type") != "fyo:ScenarioSpecification":
        out.append(f"type is {doc.get('type')!r}, not fyo:ScenarioSpecification")
    if str(doc.get("id", "")).rsplit("/", 1)[-1] != cid:
        out.append(f"document id {doc.get('id')!r} does not name the catalogue entry")
    bar = bar_of(doc)
    if bar not in bars:
        out.append(f"prescribes_code names bar {bar!r}, which neither the tool "
                   "register nor the browser-only register knows")
    if not doc.get("prescribed_task_kind"):
        out.append("no prescribed_task_kind")
    if not _lang(doc.get("title")):
        out.append("no title")
    params = doc.get("parameters")
    if not params:
        out.append("no parameter settings")
    for p in params or []:
        ref = str(p.get("sets_parameter", ""))
        if not ref.startswith(f"code/{bar}#") or "literal_value" not in p:
            out.append(f"parameter setting {ref!r} is not `code/{bar}#<name>` "
                       "with a literal_value")
            break

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k.startswith(_RETIRED_PREFIXES):
                    yield k
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)
        elif isinstance(x, str) and any(t in x for t in _RETIRED_PREFIXES):
            yield x[:60]
    hits = list(walk(doc))
    if hits:
        out.append(f"retired vocabulary present ({len(hits)}): {hits[0]!r}")
    return out


def problems(d: Path | None = None) -> list[str]:
    """What is structurally wrong with the whole corpus (empty = sound).

    Catalogue ↔ disk in BOTH directions (a named document that is not there,
    a document nobody names), plus :func:`_case_problems` per document.

    ★★2026-09-04 这个函数从 `engine/cli.py` 搬来。它从前只经命令行的
    ``fylite cases --check`` 到达，而那一层随「Python 侧无命令行」的裁定撤除——
    **检查本身不是命令行的**，它是语料的一条不变式，所以它留在库里，
    调用方（闸子、脚本、别的宿主）直接调它。
    """
    d = corpus_dir(d)
    from ..scenario import BROWSER_ONLY_BARS, TOOLS
    bars = {t["bar"] for t in TOOLS.values() if t["bar"]} | set(BROWSER_ONLY_BARS)
    bad: list[str] = []
    #: ★一个例子一个目录之后，盘上的计划在 `<章>/` 里，孤儿检查要跟着下一层；
    #: 记的是**目录相对路径**，与目录里的 `storage_uri` 同形。
    on_disk = {
        str(p.relative_to(d).as_posix())
        for p in d.rglob("*.jsonld")
        if not set(p.relative_to(d).parts[:-1]) & _NOT_CASE_DIRS
    } - _NOT_CASES
    named: set[str] = set()
    for e in catalogue(d):
        cid, doc_name = e.get("case_id"), e.get("file")
        if not cid or not doc_name:
            bad.append(f"entry {cid or doc_name!r}: missing id/concretization")
            continue
        named.add(doc_name)
        f = d / doc_name
        if not f.is_file():
            bad.append(f"{cid}: names {doc_name}, which is not on disk")
            continue
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as exc:
            bad.append(f"{cid}: {doc_name} does not parse ({exc})")
            continue
        bad.extend(f"{cid}: {why}" for why in _case_problems(doc, cid, bars))
    bad.extend(f"orphan file not in the catalogue: {o}" for o in sorted(on_disk - named))
    return bad
