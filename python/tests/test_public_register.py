"""The public V&V register must describe what it points at — and nothing it cannot.

★A public register is worth exactly what its worst unverifiable entry is
worth.  Three things rot on their own here: a record whose report or scenario
is gone, a pointer with no checksum and no reason, and a private path leaking
into a page a public reader cannot open.  This gate holds those.  It does NOT
check the measured numbers — those live in the gates the records name, which
run in the kernel checkout; duplicating them here would be the second copy the
register exists to avoid.

★★The structural checks are ONE function (`engine.benchmark.problems`),
shared with `fylite cases --benchmark --check`, so the CLI and this gate
cannot disagree about what a sound record is.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fylite.engine import benchmark as bm

ROOT = Path(__file__).resolve().parents[2]
BM = ROOT / "benchmark"
REGISTRY = BM / "registry.jsonld"

pytestmark = pytest.mark.skipif(not REGISTRY.is_file(),
                                reason="benchmark/registry.jsonld not in this checkout")


@pytest.fixture(scope="module")
def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_every_record_is_sound(registry):
    bad = {}
    for r in registry["@graph"]:
        p = bm.problems(r, BM)
        if p:
            bad[bm.short_id(r)] = p
    assert not bad, bad


def test_the_register_is_not_empty_and_ids_are_unique(registry):
    ids = [bm.short_id(r) for r in registry["@graph"]]
    assert ids, "an empty register is a register that admits nothing — say so in README instead"
    assert len(ids) == len(set(ids)), ids


def test_every_scenario_document_is_named_by_a_record(registry):
    defined = {}
    for p in sorted((BM / "scenarios").glob("*.jsonld")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        defined[doc["id"]] = p.name
    used = {r["scenario"] for r in registry["@graph"] if r.get("scenario")}
    assert not (used - set(defined)), sorted(used - set(defined))
    assert not (set(defined) - used), sorted(set(defined) - used)


def test_every_report_on_disk_is_named_by_a_record(registry):
    named = {r["report"]["storage_uri"] for r in registry["@graph"] if r.get("report")}
    on_disk = {f"reports/{p.name}" for p in (BM / "reports").glob("*.md")
               if p.name not in ("README.md", "TEMPLATE.md")}
    assert on_disk == named, {"on disk, unnamed": sorted(on_disk - named),
                              "named, gone": sorted(named - on_disk)}


def test_the_index_lists_exactly_what_the_register_holds(registry):
    text = (BM / "reports" / "README.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| ([VBC]-\d\d) \|", text, re.M))
    held = {bm.short_id(r) for r in registry["@graph"]}
    assert listed == held, {"index only": sorted(listed - held), "register only": sorted(held - listed)}
    m = re.search(r"(\d+) 条记录，(\d+) 个场景", text)
    assert m, "the index no longer opens with a「N 条记录，M 个场景」count"
    n_scn = len({r["scenario"] for r in registry["@graph"] if r.get("scenario")})
    assert (int(m.group(1)), int(m.group(2))) == (len(held), n_scn)


def test_every_context_term_used_is_declared(registry):
    ctx = json.loads((BM / "context.jsonld").read_text(encoding="utf-8"))
    declared = set(ctx["@context"]) | {"@graph", "@context"}
    seen = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                seen.add(k)
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk({k: v for k, v in registry.items() if k != "@context"})
    for p in sorted((BM / "scenarios").glob("*.jsonld")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        walk({k: v for k, v in doc.items() if k != "@context"})
    assert seen <= declared, sorted(seen - declared)


def test_the_register_stays_neutral_about_who_is_being_tested():
    """`fylite` may appear in the DATA (it is what is under test) and never in
    the SCHEMA or in a scenario — a second code adopting these records should
    need a new `compared_subject`, not a new context."""
    assert "fylite" not in (BM / "context.jsonld").read_text(encoding="utf-8").lower()
    for p in sorted((BM / "scenarios").glob("*.jsonld")):
        assert "fylite" not in p.read_text(encoding="utf-8").lower(), p.name


def test_no_pointer_names_a_private_checkout_by_an_absolute_path(registry):
    """★A public reader gets `$FYLITE_KERNEL/…` and `$FYDATA_ORACLE/…` — variables
    they bind themselves — never `/home/<someone>/…`."""
    text = REGISTRY.read_text(encoding="utf-8")
    assert not re.search(r'"storage_uri": "/', text)
    assert not re.search(r"/home/[a-z]", text)


def test_the_cli_lists_and_checks_the_register(capsys):
    from fylite.engine import cli as m
    import argparse
    ns = argparse.Namespace(benchmark=True, dir=None, name=None, check=True, as_json=False,
                            plan=False, run_case=False, kernel=None)
    rc = m._cli_cases(ns, None)
    out = capsys.readouterr().out
    assert rc == 0, out
    ns.check = False
    ns.as_json = True
    assert m._cli_cases(ns, None) == 0
    got = json.loads(capsys.readouterr().out)
    assert [r["record_id"] for r in got["records"]] == [
        bm.short_id(r) for r in json.loads(REGISTRY.read_text(encoding="utf-8"))["@graph"]]


def test_running_a_record_without_a_kernel_checkout_is_refused_by_name(monkeypatch, capsys):
    monkeypatch.delenv(bm.KERNEL_ENV, raising=False)
    rid = bm.short_id(bm.graph(BM)[0])
    r = bm.run(rid, BM)
    assert r["returncode"] is None
    assert "refused" in r["summary"] and bm.KERNEL_ENV in r["summary"], r
