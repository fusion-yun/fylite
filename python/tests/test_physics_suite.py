"""闸子：物理校验批（`fylite.scenario.suite` + `tools/benchmark-run.py`）。

★★这份闸子守的是**批次的诚实**，不是物理（物理在 `test_physics_checks.py`）：

1. 盘上那份 `benchmark/physics/suite.jsonld` 结构站得住——每条声明点的算例文件
   在检出里、点的判据在册子里、点的量是内核产得出的（与 `fylite cases --physics
   --check` **同一个函数**，两处不会各说各话）；
2. 「没有产出可判」与「判过了没通过」在统计表里**分得开**——一批全未评估的
   结果不能显示成「零个失败」；
3. 一份已经跑出来的记录，在**没有内核**的检出里也判得动（`--from` 那条路）；
4. 工具写出来的四样（逐条记录、逐条报告、统计、仓根摘要）落在说好的地方。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from fylite import fyo
from fylite.scenario import physics as ph
from fylite.scenario import suite as sc

from test_physics_checks import bundle, summary_doc          # noqa: E402  (同目录的构造件)

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "benchmark" / "physics" / "suite.jsonld"

pytestmark = pytest.mark.skipif(not SUITE.is_file(),
                                reason="benchmark/physics/suite.jsonld not in this checkout")


@pytest.fixture(scope="module")
def d():
    return sc.suite_dir()


def _record(datasets: dict, *, run_state="succeeded") -> dict:
    """一份记录的形，与 `fylite-case run` 写的同一套（`rust/fylite_data/src/case.rs`）。"""
    return {"id": "run/test", "type": "spo:ComputationRecord", "run_state": run_state,
            "inputs": [{"type": "spo:PortBinding",
                        "binds_port": {"type": "spo:Port", "port_name": port,
                                       "port_direction": "output"},
                        "bound_to": doc}
                       for port, doc in datasets.items()]}


# --------------------------------------------------------------------------- #
# 盘上那份声明
# --------------------------------------------------------------------------- #
def test_the_shipped_suite_is_structurally_sound(d):
    doc = sc.load_suite(d)
    bad = {}
    for part in doc["has_part"]:
        why = sc.problems(part, d)
        if why:
            bad[part.get("id")] = why
    assert not bad, json.dumps(bad, ensure_ascii=False, indent=1)
    assert len(doc["has_part"]) >= 5


def test_every_entry_keeps_the_laws_and_definitions_whatever_it_declares(d):
    for e in sc.entries(d):
        assert set(ph.DEFAULT_CHECKS) <= set(e["checks"]), e["id"]
        #: 声明的期望都带上了参数，否则它只会是一条 unevaluated
        for cid, opt in e["options"].items():
            if ph.CHECKS[cid].kind == "expectation":
                assert opt.get("bounds") or opt.get("tolerance") is not None, (e["id"], cid)
        assert e["case"] or e["products"], e["id"]


def test_a_criterion_that_names_an_unknown_check_is_a_problem(d):
    bad = {"id": "physics/x", "title": "x", "scenario": "cases/evolve-default",
           "concretized_as": [{"storage_uri": "cases/evolve-default.jsonld"}],
           "criteria": [{"quantity_label": "no-such-check", "tolerance_basis": "measured_band"}]}
    why = sc.problems(bad, d)
    assert any("不在判据册里" in x for x in why), why

    bounds = {"id": "physics/y", "title": "y", "scenario": "cases/evolve-default",
              "concretized_as": [{"storage_uri": "cases/evolve-default.jsonld"}],
              "criteria": [{"quantity_label": "declared-bounds", "tolerance_basis": "reference_stated",
                            "bounds": [{"quantity": "SUMMARY/not_a_slot", "maximum": 1.0}]}]}
    assert any("内核不产的量" in x for x in sc.problems(bounds, d))

    homeless = {"id": "physics/z", "title": "z"}
    assert any("既没有 scenario" in x for x in sc.problems(homeless, d))


# --------------------------------------------------------------------------- #
# 判一份记录：不需要内核
# --------------------------------------------------------------------------- #
def test_a_recorded_run_is_judged_without_a_kernel(tmp_path):
    b = bundle()
    b["summary"] = summary_doc()
    (tmp_path / "record.jsonld").write_text(
        json.dumps(_record(b), ensure_ascii=False), encoding="utf-8")
    e = {"id": "t", "case": "cases/x", "checks": list(ph.DEFAULT_CHECKS),
         "options": {}, "caveat": []}
    row = sc.run_entry(e, from_dir=tmp_path)
    assert row["state"] == ph.PASS, [r for r in row["results"] if r["state"] != ph.PASS]
    assert sorted(row["datasets"]) == ["core_profiles", "equilibrium", "summary"]
    assert row["provenance"]["source"] == "recorded"
    states = {r["check"]: r["state"] for r in row["results"]}
    assert states["grad-shafranov"] == ph.PASS
    assert states["energy-balance"] == ph.PASS


def test_a_rejected_run_is_unevaluated_with_the_kernels_sentence(tmp_path):
    b = bundle()
    rec = _record(b, run_state="rejected")
    rec["comment"] = ["refused: the pedestal is not sunk on this tier"]
    (tmp_path / "record.jsonld").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    row = sc.run_entry({"id": "t", "case": "cases/x", "checks": list(ph.DEFAULT_CHECKS),
                        "options": {}}, from_dir=tmp_path)
    assert row["state"] == ph.UNEVALUATED
    assert "pedestal" in row["refused"]


def test_a_missing_recorded_run_is_refused_by_name_not_run_live(tmp_path, d):
    batch = sc.run_suite(["evolve-default"], d=d, from_dir=tmp_path)
    row = batch["entries"][0]
    assert row["state"] == ph.UNEVALUATED
    assert "no recorded run" in row["refused"]
    #: ★没有悄悄改走现跑那条路：理由里说的是「这个目录下没有它的记录」
    assert "kernel" not in row["refused"]


def test_a_record_dir_is_found_by_entry_or_case_name(tmp_path):
    (tmp_path / "evolve-default").mkdir()
    (tmp_path / "evolve-default" / "record.jsonld").write_text("{}", encoding="utf-8")
    e = {"id": "evolve-default", "case": "cases/evolve-default"}
    assert sc.record_dir_for(tmp_path, e) == tmp_path / "evolve-default"
    assert sc.record_dir_for(tmp_path, {"id": "other", "case": "cases/other"}) is None
    (tmp_path / "record.jsonld").write_text("{}", encoding="utf-8")
    assert sc.record_dir_for(tmp_path, {"id": "other", "case": "cases/other"}) == tmp_path


# --------------------------------------------------------------------------- #
# 判一份盘上的产出
# --------------------------------------------------------------------------- #
def test_the_product_path_judges_a_file_on_disk(d):
    """★这一条在没有内核的检出里也该跑得动——否则整册只剩「未评估」。"""
    from fylite import kernel
    if kernel.load_data() is None:
        pytest.skip("libfylite_data.so not built (rust/build.sh)")
    e = sc.entry("equilibrium-gfile", d)
    row = sc.run_entry(e)
    assert row["state"] == ph.PASS, row.get("refused") or row["results"]
    states = {r["check"]: r for r in row["results"]}
    gs = states["grad-shafranov"]
    assert gs["state"] == ph.PASS and gs["measured"] < 1e-3, gs
    #: 没有剖面的产出，剖面那几条是「未评估」并点名——不是「通过」
    assert states["positive-temperature"]["state"] == ph.UNEVALUATED
    assert states["positive-temperature"]["missing"]


# --------------------------------------------------------------------------- #
# 统计与文档
# --------------------------------------------------------------------------- #
def test_statistics_keep_unevaluated_apart_from_passing():
    rows = [{"entry": "a", "state": ph.PASS, "summary": ph.summarize([]),
             "results": [{"check": "finite", "kind": "law", "state": ph.PASS},
                         {"check": "grad-shafranov", "kind": "law", "state": ph.UNEVALUATED}]},
            {"entry": "b", "state": ph.UNEVALUATED, "refused": "no kernel",
             "summary": ph.summarize([]), "results": []}]
    st = sc.statistics(rows)
    assert st["entries"] == 2 and st["refused"] == 1
    assert st["checks_total"] == 2 and st["checks_evaluated"] == 1 and st["failed"] == 0
    assert st["by_entry"][ph.UNEVALUATED] == 1
    assert st["by_check"]["grad-shafranov"][ph.UNEVALUATED] == 1


def test_the_record_document_and_the_report_quote_the_verdicts(tmp_path):
    b = bundle()
    b["summary"] = summary_doc()
    (tmp_path / "record.jsonld").write_text(json.dumps(_record(b), ensure_ascii=False),
                                            encoding="utf-8")
    e = sc.entries()[0] | {"checks": ["grad-shafranov", "positive-temperature"], "options": {}}
    row = sc.run_entry(e, from_dir=tmp_path)
    doc = sc.record_document(row, report_uri="benchmark/physics/x.md", recorded="2026-09-02")
    assert doc["type"] == "fyo:ComparisonRecord"
    assert doc["overall_verdict"] == row["state"]
    assert [f["verdict"] for f in doc["findings"]] == [r["state"] for r in row["results"]]
    assert [c["quantity_label"] for c in doc["criteria"]] == [r["check"] for r in row["results"]]
    #: ★判决用四态，与 provenance 的验收同一套（登记册的三态没有「有条件」）
    assert set(f["verdict"] for f in doc["findings"]) <= set(sc.STATE_ZH)
    md = sc.render_report(row, recorded="2026-09-02")
    assert "Grad–Shafranov" in md or "grad-shafranov" in md
    assert "Δ*ψ" in md                      # 判据的式子照录
    assert "通过" in md


def test_the_tool_writes_the_register_and_the_top_summary(tmp_path):
    spec = importlib.util.spec_from_file_location("bench_run", ROOT / "tools" / "benchmark-run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    b = bundle()
    b["summary"] = summary_doc()
    batch = {"recorded": "2026-09-02", "entries": [
        {"entry": "demo", "case": "cases/demo", "title": "demo", "state": ph.PASS,
         "datasets": ["equilibrium"], "record_id": "run/demo",
         "provenance": {"source": "recorded", "comment": "read"},
         "results": ph.evaluate(b, only=["grad-shafranov", "finite"]),
         "summary": ph.summarize(ph.evaluate(b, only=["grad-shafranov", "finite"])),
         "caveat": []}]}
    batch["statistics"] = sc.statistics(batch["entries"])
    out = tmp_path / "benchmark" / "physics"
    (tmp_path / "benchmark" / "physics").mkdir(parents=True)
    written = mod.write_batch(batch, out, tmp_path)
    names = {p.name for p in written}
    assert {"demo.jsonld", "demo.md", "summary.jsonld", "SUMMARY.md", "BENCHMARK.md"} <= names
    top = (tmp_path / "BENCHMARK.md").read_text(encoding="utf-8")
    assert "物理校验" in top and "demo" in top
    summary = json.loads((out / "summary.jsonld").read_text(encoding="utf-8"))
    assert summary["quality_state"]["checks_total"] == 2
    assert summary["has_part"][0]["overall_verdict"] == ph.PASS


def test_the_tool_exits_non_zero_only_on_a_real_failure(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("bench_run2", ROOT / "tools" / "benchmark-run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    #: 一批全「未评估」：退 0（这是检出的事实），但 --strict 下退 1
    fake = {"recorded": "2026-09-02",
            "entries": [{"entry": "a", "state": ph.UNEVALUATED, "refused": "no kernel",
                         "results": [], "summary": ph.summarize([]), "caveat": []}]}
    fake["statistics"] = sc.statistics(fake["entries"])
    monkeypatch.setattr(mod.sc, "run_suite", lambda *a, **k: fake)
    assert mod.main([]) == 0
    assert mod.main(["--strict"]) == 1
    #: 一条真的没过：退 1
    failing = {"recorded": "2026-09-02",
               "entries": [{"entry": "a", "state": ph.FAIL, "results": [
                   {"check": "finite", "kind": "law", "state": ph.FAIL}],
                   "summary": ph.summarize([{"state": ph.FAIL}]), "caveat": []}]}
    failing["statistics"] = sc.statistics(failing["entries"])
    monkeypatch.setattr(mod.sc, "run_suite", lambda *a, **k: failing)
    assert mod.main([]) == 1


def test_the_committed_summary_matches_the_suite(d):
    """仓里那份统计与声明对得上 —— 生成件与它的输入不该错开一个版本。"""
    s = d / "summary.jsonld"
    if not s.is_file():
        pytest.skip("summary.jsonld has not been written yet (tools/benchmark-run.py --write)")
    doc = json.loads(s.read_text(encoding="utf-8"))
    ids = {p["id"].rsplit("/", 1)[-1] for p in doc["has_part"]}
    assert ids == {e["id"] for e in sc.entries(d)}
    assert doc["quality_state"]["entries"] == len(sc.entries(d))
    for name in ("SUMMARY.md", "README.md"):
        assert (d / name).is_file(), name
    assert (ROOT / "BENCHMARK.md").is_file()


def test_the_reference_page_lists_every_check_in_the_register():
    """文档书里那一页与册子不许错开 —— 一条新检查没写进文档，这里就红。"""
    page = ROOT / "docs" / "reference" / "benchmark.md"
    if not page.is_file():
        pytest.skip("docs/reference/benchmark.md not in this checkout")
    text = page.read_text(encoding="utf-8")
    missing = [cid for cid in ph.CHECKS if f"`{cid}`" not in text]
    assert not missing, f"这几条检查没写进 docs/reference/benchmark.md：{missing}"
    #: 反过来也拦：文档列了一条册子上没有的（改名后忘了改文档）
    import re
    listed = set(re.findall(r"^\| `([a-z-]+)` \|", text, re.M))
    assert listed <= set(ph.CHECKS), f"文档列了册子上没有的检查：{sorted(listed - set(ph.CHECKS))}"
