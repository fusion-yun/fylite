#!/usr/bin/env python3
"""新册的生成器：从 `records/` 与 `requirements.jsonld` 写出 `coverage.md` 与 `index.jsonld`。

★★**为什么覆盖表必须由机器写**：旧册的 `reports/README.md` 是手维护的索引，结果最后
一条记录进册时它没跟上——查得到记录、查不到索引。索引与记录不同源，就一定会漂。

★**没有记录覆盖的需求显示为空行，不省略。** 一张只列"做过什么"的表回答不了"够不够"；
空行才是缺口本身。MUST 级的空行单独计数——那是硬缺口。

用法：
    python tools/benchmark-coverage.py            # 写 coverage.md + index.jsonld
    python tools/benchmark-coverage.py --check    # 只核对是否最新（CI / 门用），不写盘
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BM = ROOT / "docs" / "benchmark"
KIND_ZH = {"verification": "验证", "benchmark": "对拍", "validation": "确认"}
VERDICT_ZH = {"pass": "成立", "fail": "不成立", "inconclusive": "未判（读数）", "unevaluated": "未评估"}


def load_records() -> list[dict]:
    """`records/*.jsonld`（不含 `retired/`）——一条记录一个文件。"""
    out = []
    for p in sorted((BM / "records").glob("*.jsonld")):
        d = json.loads(p.read_text(encoding="utf-8"))
        d["_file"] = p.name
        out.append(d)
    return out


def load_requirements() -> list[dict]:
    return json.loads((BM / "requirements.jsonld").read_text(encoding="utf-8"))["requirement"]


def build(reqs: list[dict], recs: list[dict]) -> tuple[str, dict]:
    by_req: dict[str, list[dict]] = {r["id"]: [] for r in reqs}
    orphan: list[tuple[str, str]] = []
    for rec in recs:
        for rid in rec.get("requirement") or []:
            if rid in by_req:
                by_req[rid].append(rec)
            else:
                #: ★记录引了一个需求树里没有的号——不静默忽略：要么 SRS 改了要重抽，
                #: 要么记录写错了号，两种都得有人看见。
                orphan.append((rec.get("id", rec["_file"]), rid))

    total = len(reqs)
    covered = sum(1 for v in by_req.values() if v)
    must_open = [r for r in reqs if r["level"] == "MUST" and not by_req[r["id"]]]

    L = ["---", "title: 需求覆盖 (Requirement coverage)", "---", "",
         "# 需求覆盖 (Requirement coverage)", "",
         "<!-- ★生成件，勿手改：`python tools/benchmark-coverage.py`。"
         "手维护的索引一定会与记录漂开——旧册的 reports/README.md 就是这么漏掉最后一条的。 -->", "",
         f"- 生成于 (recorded)：{datetime.date.today().isoformat()}",
         f"- 需求 (requirements)：**{total}** 条，其中 **MUST {sum(1 for r in reqs if r['level']=='MUST')}** 条",
         f"- 已有记录覆盖 (covered)：**{covered}** 条（{100*covered//total if total else 0} %）",
         f"- ★**MUST 级空缺 (open MUST)：{len(must_open)} 条**", ""]

    if orphan:
        L += ["", ":::{warning}", "★**记录引用了需求树里没有的号**——SRS 改了要重抽 "
              "`requirements.jsonld`，或记录写错了号：", ""]
        L += [f"- `{who}` → `{rid}`" for who, rid in orphan]
        L += ["", ":::", ""]

    for dom, name in (("EQ", "fyeq 平衡求解器 · `FYTOK-SRS-03`"), ("TR", "fytrans 输运求解器 · `FYTOK-SRS-04`")):
        rows = [r for r in reqs if r["domain"] == dom]
        L += [f"## {name}", "",
              "| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判词 |",
              "| :--- | :--- | :--- | :--- | :--- | :--- |"]
        for r in rows:
            hits = by_req[r["id"]]
            if not hits:
                #: 空行就是缺口，照写
                L.append(f"| `{r['id']}` | {r['level'] or '—'} | {r['title'] or '—'} | — | — | — |")
                continue
            for i, rec in enumerate(hits):
                rid_cell = f"`{r['id']}`" if i == 0 else ""
                lvl_cell = (r["level"] or "—") if i == 0 else ""
                ttl_cell = (r["title"] or "—") if i == 0 else ""
                kind = KIND_ZH.get(rec.get("comparison_kind", ""), rec.get("comparison_kind", "—"))
                verdict = VERDICT_ZH.get(rec.get("overall_verdict", ""), rec.get("overall_verdict", "—"))
                L.append(f"| {rid_cell} | {lvl_cell} | {ttl_cell} | "
                         f"[`{rec['id']}`](records/{rec['_file']}) | {kind} | {verdict} |")
        L += [""]

    if must_open:
        L += ["## MUST 级空缺 (open MUST requirements)", "",
              "★这些是**硬缺口**：SRS 写的是「必须」，而本册没有任何记录覆盖它们。", "",
              "| 需求 | 标题 | 上游 |", "| :--- | :--- | :--- |"]
        L += [f"| `{r['id']}` | {r['title'] or '—'} | {r.get('upstream') or '—'} |" for r in must_open]
        L += [""]

    index = {"@context": "context.jsonld", "id": "benchmark/index",
             "type": "spo:InformationContentEntity",
             "title": {"zh": "本册记录索引", "en": "Index of records"},
             "recorded": datetime.date.today().isoformat(),
             "statistics": {"requirements": total, "covered": covered,
                            "open_must": len(must_open), "records": len(recs)},
             "record": [{"id": r["id"], "file": f"records/{r['_file']}",
                         "title": r.get("title"), "comparison_kind": r.get("comparison_kind"),
                         "overall_verdict": r.get("overall_verdict"),
                         "requirement": r.get("requirement") or []} for r in recs]}
    return "\n".join(L) + "\n", index


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="只核对生成件是否最新，不写盘")
    a = ap.parse_args()
    md, index = build(load_requirements(), load_records())
    js = json.dumps(index, ensure_ascii=False, indent=1) + "\n"
    pmd, pjs = BM / "coverage.md", BM / "index.jsonld"
    if a.check:
        stale = [p.name for p, want in ((pmd, md), (pjs, js))
                 if not p.is_file() or p.read_text(encoding="utf-8") != want]
        if stale:
            print("stale (re-run `python tools/benchmark-coverage.py`):", ", ".join(stale), file=sys.stderr)
            return 1
        print("coverage.md / index.jsonld are current")
        return 0
    pmd.write_text(md, encoding="utf-8")
    pjs.write_text(js, encoding="utf-8")
    s = index["statistics"]
    print(f"wrote {pmd.name} + {pjs.name}: {s['records']} records, "
          f"{s['covered']}/{s['requirements']} requirements covered, {s['open_must']} open MUST")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
