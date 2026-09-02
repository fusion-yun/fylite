"""预设算例的物理校验批 —— 算例进，记录出，逐条判，落成报告。

★★**一个算例，两份文档，三步**：``cases/`` 里的一份 ``fyo:ScenarioSpecification``
（问的是什么）→ 跑出一份 ``spo:ComputationRecord``（答的是什么，产出的 fyo 文档挂在
各输出端口上）→ 用 :mod:`.physics` 的册子逐条量它，落成一份 ``fyo:ComparisonRecord``
（判的是什么）。三份文档同一套 fyo / spo 词汇，谁也不吃掉谁：**算例不带结果，
记录不带判决，判决不改记录**。

★★**产出从哪来，只有两条路，都不许猜**：

* ``--from <记录目录>`` —— 读一份**已经跑出来**的记录（``fylite-case run`` 写的
  ``record.jsonld`` 或它的目录）。这条路不需要内核，因此在公开检出里也走得通；
* 现跑 —— 经数据层的 JSON 门（:func:`fylite.io.fydoc.case_json`）把算例交给内核。
  **内核不在场就按名拒绝**（`libfylite_kernel.so`），不退化成任何别的算法。

没有第三条路：一个「跑不了就估一个」的批次，产出的统计表比没有统计表更坏。

★★判据由**算例带**（``benchmark/physics/suite.jsonld`` 的 ``criteria``），不由本模块
临时决定：容差、上下界、准稳态窗口都是场景的性质。册子（:mod:`.physics`）只提供
**定律与定义**那一半，它们不需要谁来声明。

批次的统计落在 ``benchmark/physics/``：一算例一份记录 + 一份报告，外加一份
``summary.jsonld``（机器读）与 ``README.md`` / 仓根 ``BENCHMARK.md``（人读）。
写盘的是 ``tools/benchmark-run.py``；本模块只**产生文档**，不决定它们落在哪——
同一批结果因此既能进仓，也能在一次临时检查里只打印出来。
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from . import physics as ph
from .cases import CorpusMissing, corpus_dir

__all__ = ["suite_dir", "load_suite", "entries", "entry", "datasets_of",
           "evaluate_record", "obtain_record", "run_entry", "run_suite", "statistics",
           "record_document", "render_report", "render_summary", "record_dir_for",
           "problems"]

#: 一批的产物落在这里（相对仓根）
REGISTER = "benchmark/physics"
SUITE = "suite.jsonld"

#: 四态 → 一句中文，报告与摘要共用一份（两处各写一遍就会漂）
STATE_ZH = {ph.PASS: "通过", ph.CONDITIONAL: "有条件", ph.FAIL: "未通过",
            ph.UNEVALUATED: "未评估"}
KIND_ZH = {"law": "定律", "definition": "定义", "expectation": "期望"}


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def suite_dir(explicit=None) -> Path:
    """``benchmark/physics/`` —— 仓库数据，不随轮子走；不在场按名拒绝。"""
    here = _root()
    roots = [Path(explicit)] if explicit else [Path(REGISTER), here / REGISTER]
    for r in roots:
        if (r / SUITE).is_file():
            return r
    raise CorpusMissing(
        "fylite benchmark: no physics suite found (looked for " + SUITE + " in "
        + ", ".join(str(r) for r in roots)
        + ") — the suite is repository data and does not ship with the wheel; "
          "run from a checkout or pass --dir")


def load_suite(d: Path | None = None) -> dict:
    d = suite_dir() if d is None else Path(d)
    return json.loads((d / SUITE).read_text(encoding="utf-8"))


def _lang(v, lang="zh") -> str:
    if isinstance(v, dict):
        return str(v.get(lang) or v.get("en") or next(iter(v.values()), ""))
    return "" if v is None else str(v)


def entries(d: Path | None = None) -> list[dict]:
    """一条一条摊平：``{id, title, case, case_file, checks, options, caveat}``。

    ``checks`` 缺省是册子里的**定律与定义**（:data:`physics.DEFAULT_CHECKS`）加上
    算例点了名的期望条目——期望不声明就不跑，跑了也只会是 ``unevaluated``。
    """
    doc = load_suite(d)
    out = []
    for part in doc.get("has_part") or []:
        checks = list(part.get("checks") or [])
        options: dict[str, dict] = {}
        for c in part.get("criteria") or []:
            cid = str(c.get("quantity_label", ""))
            if not cid:
                continue
            opt = {k: v for k, v in c.items()
                   if k not in ("type", "quantity_label", "tolerance", "tolerance_basis",
                                "comment", "caveat", "id", "norm")}
            tol = (c.get("tolerance") or {}).get("numeric_value") if isinstance(c.get("tolerance"), dict) \
                else c.get("tolerance")
            if tol is not None:
                opt["tolerance"] = float(tol)
            options[cid] = {**options.get(cid, {}), **opt}
            if cid not in checks:
                checks.append(cid)
        if not checks:
            checks = list(ph.DEFAULT_CHECKS)
        else:
            #: 声明了几条期望，定律与定义照跑——它们不是可选项
            checks = list(dict.fromkeys(list(ph.DEFAULT_CHECKS) + checks))
        conc = (part.get("concretized_as") or [{}])[0].get("storage_uri")
        #: 一条算例可以直接点名**产出文件**（`bound_to` 的具体化）：那时不跑，
        #: 判的就是这些文件——见 :func:`record_from_products`
        products = [c.get("storage_uri") for c in (part.get("has_output") or [])
                    if c.get("storage_uri")]
        out.append({"id": str(part.get("id", "")).rsplit("/", 1)[-1],
                    "title": _lang(part.get("title")),
                    "abstract": _lang(part.get("abstract")),
                    "case": part.get("scenario"),
                    "case_file": conc,
                    "products": products,
                    "checks": checks,
                    "options": options,
                    "caveat": list(part.get("caveat") or [])})
    return out


def entry(entry_id: str, d: Path | None = None) -> dict:
    for e in entries(d):
        if e["id"] == entry_id or e["case"] == entry_id or (e["case"] or "").rsplit("/", 1)[-1] == entry_id:
            return e
    raise KeyError(entry_id)


def problems(part: Mapping, d: Path | None = None) -> list[str]:
    """一条声明**结构上**哪里不对（空 = 站得住）。

    ★与 :func:`fylite.scenario.benchmark.problems` 同一姿态：命令行的 ``--check``
    与闸子（``python/tests/test_physics_suite.py``）读**同一个函数**，两处因此
    不会对「什么算一条站得住的声明」给出不同答案。
    """
    d = suite_dir() if d is None else Path(d)
    root = d.parents[1] if d.name == "physics" else _root()
    out: list[str] = []
    pid = str(part.get("id", ""))
    if not pid.startswith("physics/"):
        out.append(f"id {pid!r} 不以 `physics/` 起头")
    if not _lang(part.get("title")):
        out.append("没有标题")
    scenario = part.get("scenario")
    products = [c.get("storage_uri") for c in (part.get("has_output") or []) if c.get("storage_uri")]
    if not scenario and not products:
        out.append("既没有 scenario（跑哪个算例）也没有 has_output（判哪份产出）")
    if scenario:
        conc = [c.get("storage_uri") for c in (part.get("concretized_as") or []) if c.get("storage_uri")]
        if not conc:
            out.append(f"scenario {scenario} 没有 concretized_as（承载它的文件）")
        for uri in conc:
            if not (root / uri).is_file():
                out.append(f"算例文件 {uri} 不在检出里")
    for uri in products:
        if not (root / uri).exists():
            out.append(f"产出文件 {uri} 不在检出里")
    for c in part.get("criteria") or []:
        cid = str(c.get("quantity_label", ""))
        if cid not in ph.CHECKS:
            out.append(f"criterion {cid!r} 不在判据册里（有的是：{', '.join(ph.CHECKS)}）")
            continue
        if c.get("tolerance_basis") not in ("machine_precision", "measured_band", "reference_stated"):
            out.append(f"criterion {cid!r} 没有 tolerance_basis")
        if ph.CHECKS[cid].kind == "expectation" and not (
                c.get("bounds") or c.get("tolerance") is not None):
            out.append(f"criterion {cid!r} 是期望类，却既没有 bounds 也没有 tolerance——判不出东西")
        for b in c.get("bounds") or []:
            q = str(b.get("quantity", ""))
            block, _, slot = q.partition("/")
            table = _fyo_tables().get(block)
            if table is None or slot not in table["slots"]:
                out.append(f"criterion {cid!r} 的界点了一个内核不产的量：{q!r}")
            if b.get("minimum", b.get("min")) is None and b.get("maximum", b.get("max")) is None:
                out.append(f"criterion {cid!r} 的界 {q!r} 既没有 minimum 也没有 maximum")
    return out


def _fyo_tables() -> Mapping:
    from .. import fyo as _fyo
    return _fyo.TABLES


# --------------------------------------------------------------------------- #
# 产出从哪来
# --------------------------------------------------------------------------- #
def datasets_of(record: Mapping) -> dict[str, dict]:
    """一份记录的输出端口 → ``{端口名: fyo 文档}``。

    ★经 :func:`fylite.engine.casereport._datasets` 读，与报告渲染同一个读法——
    「哪些端口算产出」这件事只在一处判断。
    """
    from ..engine import casereport
    return {port: doc for port, doc in casereport._datasets(dict(record))}


class Refused(Exception):
    """跑不了，且**理由有名字** —— 批次把它记成一行，不当成失败也不当成通过。"""


def record_from_products(paths: Sequence[str], *, base=None) -> tuple[dict, dict]:
    """把若干**产出文件**（g-file / JSON-LD / HDF5 / netCDF）包成一份记录的形。

    ★★为什么要这条路：物理校验量的是**产出**，而产出不一定来自本次运行——一份
    盘上的 g-file 就是一份平衡产出，它满不满足 Grad–Shafranov 与谁写的它无关。
    这条路让公开检出（没有内核）里也有真数据可判，而不是一册全是「未评估」。

    包出来的记录 ``run_state`` 是 ``succeeded``，但 ``executed_code`` 明写「不是一次
    运行」——读者不会把它当成一次可复算的计算记录。
    """
    from ..io import fydoc
    ports, cited = [], []
    for rel in paths:
        p = (Path(base) / rel) if base else (_root() / rel)
        if not p.is_file() and not p.is_dir():
            raise Refused(f"product {rel} is not in this checkout")
        bundle = fydoc.read(p)
        docs = bundle.to_dict()
        if "@type" in docs or "@id" in docs:          # 单份文档不套容器
            docs = {(bundle.keys or ["document"])[0]: docs}
        for ids, doc in docs.items():
            ports.append({"type": "spo:PortBinding",
                          "binds_port": {"type": "spo:Port", "port_name": ids,
                                         "port_direction": "output"},
                          "bound_to": doc})
        cited.append(str(p))
    rec = {"id": "product/" + "+".join(Path(c).name for c in cited),
           "type": "spo:ComputationRecord",
           "run_state": "succeeded",
           "executed_code": {"type": "spo:Code", "name": "—",
                             "comment": "这不是一次运行：产出是从盘上读来的文件"},
           "inputs": ports}
    return rec, {"source": "product", "products": cited,
                 "comment": "判的是盘上的产出文件（" + ", ".join(Path(c).name for c in cited)
                            + "），不是本批跑出来的"}


def obtain_record(e: Mapping, *, from_dir=None, corpus=None, kernel_lib=None,
                  base=None) -> tuple[dict, dict]:
    """取一份记录：读已有的（``from_dir``）、读产出文件（算例声明 ``product``），
    或经 JSON 门现跑。

    返回 ``(record, provenance)``；``provenance`` 说清这份记录**是怎么来的**
    （读盘还是现跑、算例文件与它的摘要、内核库路径），报告与记录都要转述它。
    """
    if not from_dir and e.get("products"):
        try:
            return record_from_products(e["products"], base=base)
        except Refused:
            raise
        except Exception as exc:                                    # noqa: BLE001
            raise Refused(f"the products could not be read: {type(exc).__name__}: {exc}") from exc
    if from_dir:
        from ..engine import casereport
        rec, _plan, d = casereport.load_record(from_dir)
        return rec, {"source": "recorded", "record_dir": str(d),
                     "comment": "读的是一份已经跑出来的记录，本批只做判决"}
    #: 现跑：算例文件 → JSON 门 → 记录
    cdir = Path(corpus) if corpus else corpus_dir()
    rel = e.get("case_file") or ((e.get("case") or "").rsplit("/", 1)[-1] + ".jsonld")
    plan_path = (Path(base) / rel) if base else (_root() / rel)
    if not plan_path.is_file():
        plan_path = cdir / Path(rel).name
    if not plan_path.is_file():
        raise Refused(f"case document {rel} is not in this checkout (looked in {cdir})")
    try:
        from ..io import fydoc
    except Exception as exc:                                        # noqa: BLE001
        raise Refused(f"the data layer is not importable: {exc}") from exc
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    try:
        rec = fydoc.case_json(plan, base=plan_path.parent, kernel_lib=kernel_lib)
    except Exception as exc:                                        # noqa: BLE001
        #: ★内核不在场是**最常见**的一种，说清楚它而不是「运行失败」
        raise Refused(f"the case could not be run: {type(exc).__name__}: {exc}") from exc
    return rec, {"source": "ran", "plan": str(plan_path),
                 "comment": "本批现跑了这个算例（数据层 JSON 门 + 内核）"}


# --------------------------------------------------------------------------- #
# 评一条
# --------------------------------------------------------------------------- #
def evaluate_record(record: Mapping, e: Mapping) -> dict:
    """一份记录 + 一条算例声明 → 逐条结论 + 统计。"""
    datasets = datasets_of(record)
    results = ph.evaluate(datasets, only=e.get("checks"), options=e.get("options"))
    summary = ph.summarize(results)
    return {"results": results, "summary": summary,
            "datasets": sorted(datasets), "run_state": record.get("run_state"),
            "record_id": record.get("id")}


def run_entry(e: Mapping, *, from_dir=None, corpus=None, kernel_lib=None,
              base=None) -> dict:
    """取产出、评判据 —— 一条算例的一整趟；拒绝也是一种结论，带理由。"""
    row = {"entry": e["id"], "case": e.get("case"), "title": e.get("title"),
           "caveat": list(e.get("caveat") or [])}
    try:
        record, prov = obtain_record(e, from_dir=from_dir, corpus=corpus,
                                     kernel_lib=kernel_lib, base=base)
    except (Refused, CorpusMissing, FileNotFoundError, ValueError) as exc:
        return {**row, "state": ph.UNEVALUATED, "refused": str(exc),
                "results": [], "summary": ph.summarize([]),
                "provenance": {"source": "refused"}}
    ev = evaluate_record(record, e)
    state = ev["summary"]["overall"]
    if record.get("run_state") == "rejected":
        #: 内核拒了这一炮：判决是「未评估」，理由照录，不拿检查的结论顶上
        return {**row, "state": ph.UNEVALUATED,
                "refused": "the kernel rejected the case: "
                           + "; ".join(str(c) for c in (record.get("comment") or []))[:400],
                "results": ev["results"], "summary": ev["summary"],
                "record": record, "provenance": prov}
    return {**row, "state": state, "results": ev["results"], "summary": ev["summary"],
            "datasets": ev["datasets"], "record": record, "provenance": prov,
            "record_id": ev["record_id"]}


def record_dir_for(from_dir, e: Mapping) -> Path | None:
    """``--from`` 指的目录里，哪一份记录是这条算例的。

    两种摆法都认：目录**本身**是一次运行（有 ``record.jsonld``，此时只该选一条
    算例），或目录下按算例名 / 算例 id 分了子目录。都对不上就给 ``None``——
    调用方据此把这条记成「没有产出可判」，而不是拿别人的记录顶上。
    """
    if from_dir is None:
        return None
    root = Path(from_dir)
    names = [e["id"], (e.get("case") or "").rsplit("/", 1)[-1],
             e["id"].rsplit("/", 1)[-1]]
    for n in names:
        if n and (root / n / "record.jsonld").is_file():
            return root / n
        if n and (root / f"{n}.jsonld").is_file():
            return root / f"{n}.jsonld"
    if (root / "record.jsonld").is_file():
        return root
    return None


def run_suite(ids: Sequence[str] | None = None, *, d=None, from_dir=None, corpus=None,
              kernel_lib=None, base=None) -> dict:
    """整批：逐条跑，逐条判，附一张统计表。

    ``from_dir`` 在场时**只读记录、不跑**：目录里找不到这条算例的记录，就记成
    「没有产出可判」并写明找过哪些名字——批次不会因此去现跑一个别的东西。
    """
    rows = []
    for e in entries(d):
        if ids and e["id"] not in ids and (e.get("case") or "") not in ids:
            continue
        src = None
        if from_dir is not None:
            src = record_dir_for(from_dir, e)
            if src is None:
                rows.append({"entry": e["id"], "case": e.get("case"), "title": e.get("title"),
                             "state": ph.UNEVALUATED, "results": [], "summary": ph.summarize([]),
                             "caveat": list(e.get("caveat") or []),
                             "provenance": {"source": "refused"},
                             "refused": f"no recorded run for this case under {from_dir}"})
                continue
        rows.append(run_entry(e, from_dir=src, corpus=corpus,
                              kernel_lib=kernel_lib, base=base))
    return {"entries": rows, "statistics": statistics(rows),
            "recorded": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")}


def statistics(rows: Iterable[Mapping]) -> dict:
    """一批的统计：逐算例判决计数、逐检查计数、逐类（定律/定义/期望）计数。

    ★「评了几条」与「过了几条」分开数：一批全是 ``unevaluated`` 的结论，统计表
    必须一眼看出来，而不是显示成 0 个失败。
    """
    rows = list(rows)
    by_entry = {s: 0 for s in STATE_ZH}
    by_check: dict[str, dict] = {}
    by_kind: dict[str, dict] = {}
    refused = 0
    for r in rows:
        by_entry[r.get("state", ph.UNEVALUATED)] = by_entry.get(r.get("state", ph.UNEVALUATED), 0) + 1
        if r.get("refused"):
            refused += 1
        for res in r.get("results") or []:
            st = res.get("state", ph.UNEVALUATED)
            c = by_check.setdefault(res["check"], {s: 0 for s in STATE_ZH})
            c[st] = c.get(st, 0) + 1
            k = by_kind.setdefault(res.get("kind", "?"), {s: 0 for s in STATE_ZH})
            k[st] = k.get(st, 0) + 1
    total_checks = sum(sum(v.values()) for v in by_check.values())
    evaluated = total_checks - sum(v[ph.UNEVALUATED] for v in by_check.values())
    return {"entries": len(rows), "refused": refused, "by_entry": by_entry,
            "by_check": by_check, "by_kind": by_kind,
            "checks_total": total_checks, "checks_evaluated": evaluated,
            "failed": sum(v[ph.FAIL] for v in by_check.values())}


# --------------------------------------------------------------------------- #
# 落成文档
# --------------------------------------------------------------------------- #
def _criterion(res: Mapping) -> dict:
    c = {"type": "fyo:AcceptanceCriterion", "quantity_label": res["check"],
         "norm": "relative" if res.get("unit") == "1" else str(res.get("unit") or "1"),
         "tolerance_basis": res.get("basis") or "reference_stated"}
    if res.get("tolerance") is not None:
        c["tolerance"] = {"type": "spo:QuantityValue", "numeric_value": res["tolerance"]}
    if res.get("assumes"):
        c["caveat"] = list(res["assumes"])
    return c


def _finding(res: Mapping) -> dict:
    f = {"type": "fyo:ComparisonFinding", "title": res.get("title") or res["check"],
         "deviation_literal": ("—" if res.get("measured") is None
                               else f"{res['measured']:.4g}"),
         "verdict": res.get("state", ph.UNEVALUATED),
         "comment": res.get("detail", "")}
    cav = list(res.get("caveat") or [])
    if res.get("missing"):
        cav.append("读不到：" + ", ".join(res["missing"]))
    if cav:
        f["caveat"] = cav
    return f


def record_document(row: Mapping, *, report_uri: str | None = None,
                    recorded: str | None = None) -> dict:
    """一条算例的判决，落成一份 ``fyo:ComparisonRecord``。

    ★参考是**定律与定义本身**（compared_reference），不是另一个码——这条记录因此
    与公开 V&V 登记册（`benchmark/registry.jsonld`）是**两个册子**：那边问「对着
    外部答案量到多少」，这边问「这份产出自洽吗」。判决用四态（`pass` /
    `conditional` / `fail` / `unevaluated`），与 :mod:`fylite.engine.provenance`
    同一套，比登记册的三态多一个「有条件」。
    """
    res = list(row.get("results") or [])
    doc = {
        "@context": ["context.jsonld", {"@base": "../../"}],
        "id": f"physics/{row['entry']}",
        "type": "fyo:ComparisonRecord",
        "comparison_kind": "verification",
        "title": row.get("title") or row["entry"],
        "recorded": recorded or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"),
        "scenario": row.get("case"),
        "compared_subject": {"type": "spo:Code", "name": "fylite",
                             "comment": "本次运行产出的 fyo 文档（记录见 run 段）"},
        "compared_reference": [{
            "type": "spo:InformationContentEntity",
            "name": "物理定律与文档自身的定义",
            "comment": "判据册在 `fylite.scenario.physics`：定律（正性、有限性、"
                       "Grad–Shafranov）、定义（ψ 端点、V′、β_N 与 Greenwald 的式子、"
                       "τ_E 的定义式）与算例声明的期望（上下界、准稳态窗口）"}],
        "criteria": [_criterion(r) for r in res],
        "findings": [_finding(r) for r in res],
        "assertion_state": "under_test",
        "overall_verdict": row.get("state", ph.UNEVALUATED),
        "run": {"type": "spo:ComputationRecord",
                "id": row.get("record_id"),
                "comment": [str(row.get("provenance", {}).get("comment", "")),
                            f"datasets: {', '.join(row.get('datasets') or []) or '—'}"]},
        "account": "docs/reference/FYL-REF-BENCHMARK.md",
    }
    if report_uri:
        doc["report"] = {"type": "spo:Concretization", "storage_uri": report_uri,
                         "format_iri": "https://www.iana.org/assignments/media-types/text/markdown"}
    caveats = list(row.get("caveat") or [])
    if row.get("refused"):
        caveats.append("本条没有产出可判：" + str(row["refused"]))
    if caveats:
        doc["caveat"] = caveats
    return doc


def render_report(row: Mapping, *, recorded: str | None = None) -> str:
    """一条算例的散文报告（Markdown）—— 逐条：量到什么、按什么判、假设了什么。"""
    st = row.get("state", ph.UNEVALUATED)
    w = [f"# {row.get('title') or row['entry']}", "",
         f"- 算例 (case)：`{row.get('case') or '—'}`",
         f"- 判决 (verdict)：**{STATE_ZH.get(st, st)}**（{st}）",
         f"- 产出 (datasets)：{', '.join(f'`{d}`' for d in row.get('datasets') or []) or '—'}",
         f"- 记录 (record)：`{row.get('record_id') or '—'}`",
         f"- 日期：{recorded or _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d')}", ""]
    prov = row.get("provenance") or {}
    if prov.get("comment"):
        w += [f"> {prov['comment']}", ""]
    if row.get("refused"):
        w += ["## 没有产出", "",
              f"本条**没有可判的产出**：{row['refused']}", "",
              "★这不是「通过」也不是「未通过」——判决是 `unevaluated`，"
              "统计表把它单列。", ""]
    res = list(row.get("results") or [])
    if res:
        w += ["## 逐条", "",
              "| 检查 | 类 | 判决 | 量到 | 容差 | 判据来路 |",
              "| :--- | :--- | :--- | ---: | ---: | :--- |"]
        for r in res:
            m = "—" if r.get("measured") is None else f"{r['measured']:.4g}"
            t = "—" if r.get("tolerance") is None else f"{r['tolerance']:.4g}"
            w.append(f"| `{r['check']}` | {KIND_ZH.get(r.get('kind'), r.get('kind'))} | "
                     f"{STATE_ZH.get(r.get('state'), r.get('state'))} | {m} | {t} | "
                     f"{r.get('basis') or '—'} |")
        w += ["", "## 每条说了什么", ""]
        for r in res:
            w.append(f"### `{r['check']}` — {r.get('title', '')}")
            w.append("")
            w.append(f"- 判据：`{r.get('formula', '')}`")
            w.append(f"- 结论：{STATE_ZH.get(r.get('state'), r.get('state'))}——{r.get('detail', '')}")
            for a in r.get("assumes") or []:
                w.append(f"- 假设：{a}")
            for c in r.get("caveat") or []:
                w.append(f"- 注记：{c}")
            if r.get("missing"):
                w.append(f"- 读不到：{', '.join(r['missing'])}")
            w.append("")
    for c in row.get("caveat") or []:
        w += [f"> 算例注记：{c}", ""]
    w += ["---", "",
          "本报告由 `tools/benchmark-run.py` 渲染（判据册 `fylite.scenario.physics`）；"
          "机器可读的一份在同名 `.jsonld` 里。", ""]
    return "\n".join(w)


def render_summary(batch: Mapping, *, title: str = "物理校验批", top: bool = False) -> str:
    """一批的统计报告（Markdown）：一算例一行 + 逐检查一行。

    ``top`` 给仓根 ``BENCHMARK.md`` 用：多一段「这是什么、怎么复算」。
    """
    st = batch["statistics"]
    rows = batch["entries"]
    rec = batch.get("recorded", "")
    w = [f"# {title}", ""]
    if top:
        w += ["〔一句话〕**预设算例跑一遍，逐条量它满不满足物理定律、文档自己的定义，"
              "和算例声明的期望**——统计表在这里，逐条报告在 "
              "[`benchmark/physics/`](benchmark/physics/)。", "",
              "这与公开 V&V 登记册（[`benchmark/`](benchmark/)）是**两个册子**，"
              "问题不同，别混着读：", "",
              "| 册子 | 问的是 | 参考是什么 |",
              "| :--- | :--- | :--- |",
              "| [`benchmark/registry.jsonld`](benchmark/registry.jsonld) | 对着**外部答案**量到多少 | 另一个码、解析解、实验 |",
              "| [`benchmark/physics/`](benchmark/physics/) （本表） | 这份产出**自洽吗** | 物理定律与文档自身的定义 |",
              ""]
    w += [f"- 日期 (recorded)：{rec}",
          f"- 算例 (cases)：{st['entries']}，其中没有产出可判的 {st['refused']}",
          f"- 检查 (checks)：{st['checks_total']} 条，评了 {st['checks_evaluated']} 条，"
          f"未通过 {st['failed']} 条", ""]
    counts = " · ".join(f"{STATE_ZH[k]} {v}" for k, v in st["by_entry"].items())
    w += [f"- 逐算例判决：{counts}", "", "## 逐算例", "",
          "| 算例 | 判决 | 通过 | 有条件 | 未通过 | 未评估 | 说明 |",
          "| :--- | :--- | ---: | ---: | ---: | ---: | :--- |"]
    for r in rows:
        c = r["summary"]["counts"]
        note = r.get("refused") or (r.get("provenance") or {}).get("comment", "")
        w.append(f"| `{r['entry']}` | {STATE_ZH.get(r['state'], r['state'])} | "
                 f"{c[ph.PASS]} | {c[ph.CONDITIONAL]} | {c[ph.FAIL]} | {c[ph.UNEVALUATED]} | "
                 f"{str(note)[:110]} |")
    w += ["", "## 逐检查", "",
          "| 检查 | 类 | 通过 | 有条件 | 未通过 | 未评估 |",
          "| :--- | :--- | ---: | ---: | ---: | ---: |"]
    for cid, c in st["by_check"].items():
        kind = ph.CHECKS[cid].kind if cid in ph.CHECKS else "?"
        w.append(f"| `{cid}` | {KIND_ZH.get(kind, kind)} | {c[ph.PASS]} | {c[ph.CONDITIONAL]} | "
                 f"{c[ph.FAIL]} | {c[ph.UNEVALUATED]} |")
    w += ["", "## 怎么复算", "", "```bash",
          "# 一条：读一份已经跑出来的记录，只做判决（不需要内核）",
          "python tools/benchmark-run.py --from records/<run> --only <entry>", "",
          "# 整批：现跑（需要 libfylite_kernel.so 与数据层 .so）",
          "python tools/benchmark-run.py --write", "```", "",
          "★没有内核的检出里，现跑那条路**按名拒绝**，统计表把它记成「未评估」"
          "并写明缺的是哪一件——不拿任何别的算法顶上。", ""]
    return "\n".join(w)
