#!/usr/bin/env python3
"""批量跑物理校验：预设算例 → 逐条判据 → 记录 · 报告 · 统计表。

    python tools/benchmark-run.py                      # 跑一遍，只把统计表打到屏幕上
    python tools/benchmark-run.py --write              # 并写进 benchmark/physics/ 与 BENCHMARK.md
    python tools/benchmark-run.py --only zerod-iter-15ma
    python tools/benchmark-run.py --from records/      # 不跑，读已经跑出来的记录来判
    python tools/benchmark-run.py --json               # 机器读的一份（不写盘）

★★**这个工具不判物理，也不产生数**：判据册在 `fylite.scenario.physics`，取产出与
落文档在 `fylite.scenario.suite`，这里只做三件事——挑哪几条、把库产出的文档写到
盘上的哪里、以什么退出码收场。理由与本仓其它 `tools/` 一样：一个既算数又写盘的
脚本，两年后没人敢改它的输出格式。

★**没有内核也能跑**：`--from` 那条路只读**已经跑出来的记录**（`fylite case run`
写的 `record.jsonld`），因此在公开检出里成立。现跑那条路要 `libfylite_kernel.so`，
不在场就**按名拒绝**，统计表把这些条目记成「未评估」并写明缺的是哪一件——不拿
任何别的算法顶上（宁可拒绝，不给假数）。

退出码：判据有 `fail` → 1；`--strict` 下「一条也没评上」也算 1；其余 0。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from fylite.scenario import physics as ph          # noqa: E402
from fylite.scenario import suite as sc            # noqa: E402

#: 写盘的四样（相对仓根），一处声明——`--write` 与 `--check` 读同一张表
OUT_SUMMARY_JSON = "benchmark/physics/summary.jsonld"
OUT_SUMMARY_MD = "benchmark/physics/SUMMARY.md"
OUT_TOP_MD = "BENCHMARK.md"


def summary_document(batch: dict) -> dict:
    """一批的统计，落成一份机器可读的文档（词汇与逐条记录同一套）。"""
    st = batch["statistics"]
    return {
        "@context": ["context.jsonld", {"@base": "../../"}],
        "id": "benchmark/physics/summary",
        "type": "spo:InformationContentEntity",
        "title": {"zh": "物理校验批的统计", "en": "Statistics of the physics-check batch"},
        "abstract": {
            "zh": "一次批量运行的统计：逐算例判决、逐检查判决、评了几条与未评估几条。"
                  "★「未评估」单列而不并进「通过」——一批全未评估的结果，统计表必须"
                  "一眼看得出来。逐条的记录在同目录的 <算例>.jsonld，散文报告在 <算例>.md。",
            "en": "Per-case and per-check verdicts of one batch, with the unevaluated "
                  "rows counted separately from the passing ones."},
        "recorded": batch["recorded"],
        "has_part": [
            {"id": f"physics/{r['entry']}", "title": r.get("title") or r["entry"],
             "scenario": r.get("case"), "overall_verdict": r["state"],
             "quality_state": r["summary"]["counts"],
             "comment": r.get("refused") or (r.get("provenance") or {}).get("comment", "")}
            for r in batch["entries"]],
        "quality_state": {
            "entries": st["entries"], "refused": st["refused"],
            "by_entry": st["by_entry"], "by_check": st["by_check"], "by_kind": st["by_kind"],
            "checks_total": st["checks_total"], "checks_evaluated": st["checks_evaluated"],
            "failed": st["failed"]},
    }


def write_batch(batch: dict, out_dir: Path, root: Path) -> list[Path]:
    """把一批写进 `benchmark/physics/`（逐条 + 统计）与仓根 `BENCHMARK.md`。"""
    written: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for row in batch["entries"]:
        rep = out_dir / f"{row['entry']}.md"
        doc = sc.record_document(row, report_uri=f"benchmark/physics/{rep.name}",
                                 recorded=batch["recorded"])
        jf = out_dir / f"{row['entry']}.jsonld"
        jf.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rep.write_text(sc.render_report(row, recorded=batch["recorded"]), encoding="utf-8")
        written += [jf, rep]
    sj = root / OUT_SUMMARY_JSON
    sj.write_text(json.dumps(summary_document(batch), ensure_ascii=False, indent=2) + "\n",
                  encoding="utf-8")
    sm = root / OUT_SUMMARY_MD
    sm.write_text(sc.render_summary(batch, title="物理校验批：统计"), encoding="utf-8")
    top = root / OUT_TOP_MD
    top.write_text(sc.render_summary(batch, title="fylite 物理校验 (Physics checks)", top=True),
                   encoding="utf-8")
    return written + [sj, sm, top]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="benchmark-run.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", action="append", default=[], metavar="ID",
                   help="只跑这一条（算例 id 或 cases/<id>），可给多次")
    p.add_argument("--dir", metavar="DIR", help="校验册所在目录（默认 benchmark/physics）")
    p.add_argument("--corpus", metavar="DIR", help="算例语料目录（默认 cases/）")
    p.add_argument("--from", dest="from_dir", metavar="DIR",
                   help="读已经跑出来的记录来判（目录本身是一次运行，或按算例名分子目录）"
                        "——这条路不需要内核")
    p.add_argument("--kernel", metavar="LIB", help="libfylite_kernel.so 的路径（默认按环境找）")
    p.add_argument("--write", action="store_true", help="把记录、报告与统计写进仓库")
    p.add_argument("--json", action="store_true", help="把整批以 JSON 打到 stdout")
    p.add_argument("--strict", action="store_true",
                   help="一条也没评上时也以非零码退出（CI 里用来盯住「批次悄悄空了」）")
    a = p.parse_args(argv)

    try:
        d = sc.suite_dir(a.dir)
    except Exception as exc:                                        # noqa: BLE001
        print(f"benchmark-run: {exc}", file=sys.stderr)
        return 2
    batch = sc.run_suite(a.only or None, d=d, from_dir=a.from_dir, corpus=a.corpus,
                         kernel_lib=a.kernel)
    if not batch["entries"]:
        print(f"benchmark-run: nothing selected (--only {a.only})", file=sys.stderr)
        return 2

    if a.json:
        #: ★记录本身不进这一份（它可能有几十兆的数组）：进的是判决与统计
        thin = {"recorded": batch["recorded"], "statistics": batch["statistics"],
                "entries": [{k: v for k, v in r.items() if k != "record"}
                            for r in batch["entries"]]}
        print(json.dumps(thin, ensure_ascii=False, indent=2))
    else:
        print(sc.render_summary(batch, title="物理校验批：统计"))

    if a.write:
        for f in write_batch(batch, Path(d).resolve(), ROOT):
            rel = f.resolve()
            print(f"wrote {rel.relative_to(ROOT) if rel.is_relative_to(ROOT) else rel}",
                  file=sys.stderr)

    st = batch["statistics"]
    if st["failed"]:
        print(f"benchmark-run: {st['failed']} check(s) failed", file=sys.stderr)
        return 1
    if a.strict and st["checks_evaluated"] == 0:
        print("benchmark-run: nothing was evaluated (--strict) — "
              "no kernel and no recorded run?", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
