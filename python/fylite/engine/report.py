"""The report face: one recorded run -> one MyST document.

统一的报告/图表模板（学术体例，MyST markdown）。The template IS the section
constant below — ``docs/reference/report-template.md`` states the same order
in prose, and ``test_report.py`` holds the two together, the same way the
CLI spec and its handlers are held together.

体例（and why each rule is a rule, not taste):

* **Sections in a fixed order** (:data:`SECTIONS`): 摘要 → 方法 → 结果 →
  验收 → 复现性.  A reader of one fylite report has read them all.
* **{table} captions ABOVE, {figure} captions BELOW** — the academic
  convention, and the one the docs book already follows; anchors are
  ``tbl-*`` / ``fig-*``.
* **Summaries, never bulk arrays.**  The report carries every array as its
  ``fylite:ArraySummary`` row (shape/dtype/min/max/mean/sha256) — the 正本
  stays ``arrays.npz``, named by hash in §复现性.  A report that inlined
  the numbers would become a second, ungated copy of the result.
* **验收 is quoted, not re-judged.**  The four states
  (pass/conditional/fail/unevaluated) and every ``tbd`` reason come from
  ``acceptance.json`` verbatim — the report is a projection of the record,
  not a fresh verdict (宁可拒绝不给假数 applies to prose too).
* **Figures degrade honestly.**  matplotlib is optional everywhere else in
  this package; here too.  Absent, the report SAYS the figures were
  omitted and why, rather than failing or silently thinning.

★stdlib-only at import (numpy/matplotlib lazily, inside the figure path) —
the same discipline as the rest of ``engine/``.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import handles

#: The template: section titles, in order.  ``docs/reference/report-template.md``
#: is the normative prose of the SAME list; ``test_report.py`` diffs the two.
SECTIONS = ("摘要", "方法", "结果", "验收", "复现性")

#: acceptance states, in the order the table lists them (record's own words)
_STATE_ZH = {"pass": "通过", "conditional": "有条件", "fail": "未通过",
             "unevaluated": "未评估"}


# --------------------------------------------------------------------------- #
# gathering: everything comes from the run directory, or is refused by name
# --------------------------------------------------------------------------- #
def _load(run: str | Path) -> tuple[Path, dict, dict, dict]:
    """Resolve a run id or directory -> (dir, manifest, result, acceptance).

    ★Refusal, not an empty report: a run that is not there, or is missing
    its manifest, has nothing this template may faithfully present.
    """
    p = Path(run)
    if p.is_dir():
        run_dir = p
    else:
        try:
            run_dir = handles.find_run(str(run))
        except LookupError as e:
            raise SystemExit(f"fylite report: {e}") from None
    man = run_dir / "manifest.json"
    if not man.is_file():
        raise SystemExit(
            f"fylite report: {run_dir} has no manifest.json — not a recorded "
            "run directory, and a report without the record would be prose "
            "about nothing")
    manifest = json.loads(man.read_text())
    result = {}
    if (run_dir / "result.json").is_file():
        result = json.loads((run_dir / "result.json").read_text())
    acceptance = manifest.get("acceptance", {})
    if (run_dir / "acceptance.json").is_file():
        acceptance = json.loads((run_dir / "acceptance.json").read_text())
    return run_dir, manifest, result, acceptance


def _summaries(result: dict) -> tuple[list[tuple[str, dict]], list[tuple[str, object]]]:
    """Split a result into (ArraySummary rows, scalar rows), stable order."""
    arrays, scalars = [], []
    for key, val in result.items():
        if isinstance(val, dict) and val.get("@type") == "fylite:ArraySummary":
            arrays.append((key, val))
        elif isinstance(val, (int, float, str, bool)) and key not in (
                "run", "run_dir"):
            scalars.append((key, val))
    return arrays, scalars


# --------------------------------------------------------------------------- #
# figures: 1-D arrays against a recognised abscissa; vector output; honest
# omission when the renderer is not installed
# --------------------------------------------------------------------------- #
def _figures(run_dir: Path, out_dir: Path, arrays: list[tuple[str, dict]]
             ) -> tuple[list[tuple[str, str, str]], str | None]:
    """Render SVG figures for the 1-D arrays -> (name, relpath, caption)[].

    Second element of the return: the reason nothing was rendered, or None.
    """
    npz = run_dir / "arrays.npz"
    if not npz.is_file():
        return [], "运行未落 arrays.npz，无数组可画"
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return [], ("matplotlib 不可用——图形省略；数组以 §结果 的摘要表呈现，"
                    "正本在 arrays.npz（§复现性 按哈希点名）")
    import numpy as np
    data = {k: np.asarray(v) for k, v in np.load(npz).items()}
    #: abscissae, by convention of the capability faces: `t` for traces,
    #: `rho` for profiles.  A 1-D array matching neither is still REPORTED
    #: (in the table) — just not plotted against a guessed axis.
    axes = [(k, data[k]) for k in ("t", "rho")
            if k in data and data[k].ndim == 1]
    figs: list[tuple[str, str, str]] = []
    fig_dir = out_dir / "figures"
    for name, _summary in arrays:
        y = data.get(name)
        if y is None or y.ndim != 1:
            continue
        against = next((ax for ax in axes
                        if ax[0] != name and len(ax[1]) == len(y)), None)
        if against is None:
            continue
        xname, x = against
        fig_dir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(4.8, 3.0))
        ax.plot(x, y, lw=1.2)
        ax.set_xlabel(xname)
        ax.set_ylabel(name)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = fig_dir / f"{name}.svg"
        fig.savefig(path)
        plt.close(fig)
        figs.append((name, f"figures/{path.name}",
                     f"{name} 对 {xname}（{len(y)} 点；正本 arrays.npz）"))
    if not figs:
        return [], "结果中没有可对 t/rho 作图的一维数组"
    return figs, None


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _md_escape(v) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def _num(v) -> str:
    if v is None:
        return "—"      #: a summary that refused a statistic stays refused
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def render(run: str | Path, *, figures: bool = True,
           out_dir: str | Path | None = None) -> str:
    """The report, as a MyST markdown string.

    ``out_dir`` is where figure files land (default: the run directory) and
    what figure paths in the text are relative to.
    """
    run_dir, manifest, result, acceptance = _load(run)
    out = Path(out_dir) if out_dir is not None else run_dir
    cfg = manifest.get("config", {})
    tool = cfg.get("tool") or cfg.get("entry") or "?"
    run_id = run_dir.name
    session = run_dir.parent.name
    arrays, scalars = _summaries(result)
    figs: list[tuple[str, str, str]] = []
    fig_note: str | None = None
    if figures:
        figs, fig_note = _figures(run_dir, out, arrays)
    else:
        fig_note = "按请求省略（--no-figures）"

    code = manifest.get("code", {})
    env = manifest.get("environment", {})
    libs = env.get("libraries", {})
    overall = acceptance.get("state", "unevaluated")
    crit = acceptance.get("criteria", [])

    L: list[str] = []
    w = L.append
    # ---- frontmatter: a generated artifact says so; no 控制信息 block ------
    w("---")
    w(f"title: 运行报告：{tool} — {run_id}")
    w(f"subtitle: 会话 {session} · fylite 生成件（正本为运行目录，本报告是其投影）")
    w(f"date: {manifest.get('created', '')}")
    w("---")
    w("")
    # ---- 摘要 --------------------------------------------------------------
    w("## 摘要")
    w("")
    kern = next(iter(libs.values()), {})
    w(f"本报告呈现一次 `{tool}` 运行（run `{run_id}`，会话 `{session}`）。"
      f"入口 `{cfg.get('entry', '?')}`，参数 {len(cfg.get('arguments', {}))} 项，"
      f"落盘工件 {len(manifest.get('artifacts', []))} 件；"
      f"验收总状态：**{_STATE_ZH.get(overall, overall)}**（`{overall}`）。"
      f"代码修订 `{code.get('rev', '?')}`"
      + ("（工作树有未提交改动）" if code.get("dirty") else "")
      + (f"，内核 `{kern.get('sha256', '')[:12]}…`" if kern else "")
      + "。数组一律以摘要呈现，正本见 §复现性。")
    w("")
    # ---- 方法 --------------------------------------------------------------
    w("## 方法")
    w("")
    w(f"- 工具：`{tool}`；入口：`{cfg.get('entry', '?')}`")
    w(f"- 会话账本：`{run_dir.parent / 'ledger.jsonld'}`")
    w("")
    args = cfg.get("arguments", {})
    if args:
        w(":::{table} 表 1：调用参数（记录原文）")
        w(":label: tbl-args")
        w("")
        w("| 参数 | 值 |")
        w("| :--- | :--- |")
        for k, v in args.items():
            w(f"| `{k}` | `{_md_escape(json.dumps(v, ensure_ascii=False))}` |")
        w(":::")
    else:
        w("本次调用没有除默认值以外的参数。")
    w("")
    inputs = manifest.get("inputs", {})
    if inputs:
        w("输入（按摘要/句柄，非复制）：")
        w("")
        for k, v in inputs.items():
            w(f"- `{k}`: `{_md_escape(json.dumps(v, ensure_ascii=False))[:120]}`")
        w("")
    # ---- 结果 --------------------------------------------------------------
    w("## 结果")
    w("")
    if arrays:
        w(":::{table} 表 2：结果量摘要（数组正本在 arrays.npz，此处仅摘要）")
        w(":label: tbl-results")
        w("")
        w("| 量 | 形状 | dtype | min | max | mean | sha256（前 12 位） |")
        w("| :--- | :--- | :--- | ---: | ---: | ---: | :--- |")
        for name, s in arrays:
            w(f"| `{name}` | {'×'.join(map(str, s.get('shape', [])))} "
              f"| {s.get('dtype', '?')} | {_num(s.get('min'))} "
              f"| {_num(s.get('max'))} | {_num(s.get('mean'))} "
              f"| `{str(s.get('sha256', ''))[:12]}` |")
        w(":::")
        w("")
    if scalars:
        w(":::{table} 表 3：标量结果")
        w(":label: tbl-scalars")
        w("")
        w("| 量 | 值 |")
        w("| :--- | :--- |")
        for name, v in scalars:
            w(f"| `{name}` | `{_md_escape(v)}` |")
        w(":::")
        w("")
    if not arrays and not scalars:
        w("结果记录中没有可摘要的量——见运行目录中的 `result.json` 原文。")
        w("")
    for i, (name, rel, caption) in enumerate(figs, 1):
        w(f":::{{figure}} {rel}")
        w(f":label: fig-{name.replace('_', '-')}")
        w(f":alt: {name}")
        w("")
        w(f"图 {i}：{caption}")
        w(":::")
        w("")
    if fig_note:
        w(f"> 图形说明：{fig_note}。")
        w("")
    # ---- 验收 --------------------------------------------------------------
    w("## 验收")
    w("")
    w(f"总状态：**{_STATE_ZH.get(overall, overall)}**（`{overall}`）。"
      "以下逐条引自运行记录（`acceptance.json`），本报告不重新评判。")
    w("")
    if crit:
        w(":::{table} 表 4：验收判据（记录原文；四态 pass/conditional/fail/unevaluated）")
        w(":label: tbl-acceptance")
        w("")
        w("| 判据 | 实测值 | 状态 | 说明 |")
        w("| :--- | :--- | :--- | :--- |")
        for c in crit:
            note = c.get("tbd") or c.get("note") or ""
            val = c.get("value")
            w(f"| `{c.get('name', '?')}` "
              f"| {('—' if val is None else _num(val))} "
              f"| {_STATE_ZH.get(c.get('state'), c.get('state'))}"
              f"（`{c.get('state')}`） | {_md_escape(note) or '—'} |")
        w(":::")
    else:
        w("该运行未声明任何验收判据（区别于「未评估」：连判据都没有）。")
    w("")
    # ---- 复现性 ------------------------------------------------------------
    w("## 复现性")
    w("")
    w(f"- 代码修订：`{code.get('rev', '?')}`"
      + ("（**dirty**——工作树含未提交改动，本报告如实记之）"
         if code.get("dirty") else ""))
    for lname, lib in libs.items():
        w(f"- 内核 `{lname}`：sha256 `{lib.get('sha256', '?')}`")
    w(f"- 环境：Python {env.get('python', '?')}，numpy {env.get('numpy', '?')}，"
      f"{env.get('platform', '?')}")
    w("")
    arts = manifest.get("artifacts", [])
    if arts:
        w(":::{table} 表 5：落盘工件（正本；报告只引不含）")
        w(":label: tbl-artifacts")
        w("")
        w("| 文件 | 字节 | sha256 |")
        w("| :--- | ---: | :--- |")
        for a in arts:
            w(f"| `{a.get('name')}` | {a.get('bytes', '?')} "
              f"| `{a.get('sha256', '?')}` |")
        w(":::")
        w("")
    w("重放本会话（版本漂移默认拒绝，见 `fylite replay --help`）：")
    w("")
    w("```bash")
    w(f"fylite replay {run_dir.parent / 'ledger.jsonld'}")
    w("```")
    w("")
    return "\n".join(L)


def write(run: str | Path, *, out: str | Path | None = None,
          figures: bool = True) -> Path:
    """Render and write ``report.md`` (default: into the run directory)."""
    run_dir, *_ = _load(run)
    dest = Path(out) if out is not None else run_dir / "report.md"
    if dest.is_dir():
        dest = dest / "report.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = render(run, figures=figures, out_dir=dest.parent)
    dest.write_text(text, encoding="utf-8")
    return dest
