"""The guide's worked examples must name things that exist.

★A user guide rots in one specific way: it keeps naming a case, a flag or an
entry that has since been renamed or retired, and nothing fails — the prose
still reads fine.  Measured on this repository more than once (`examples/`,
`machine_desc/`, `fylite.run(...)`, and the 0-D mapper's own `t_rampup_end`).

What is gated here is only what CAN be gated cheaply and exactly:

* every ``cases/<id>`` the worked-example chapters name is in the catalogue;
* every ``fylite cases --flag`` they show is declared in the CLI spec;
* every ``S.<line>.<tool>`` they call exists on the scenario package, and the
  keywords shown in a call are real keywords of that entry;
* the paths they tell a reader to run from are the paths the repository has.

★It does NOT gate the numbers.  Those come from a run, and a gate that
re-ran every example would be a second, slower copy of the case tier — what
keeps them honest is that each chapter says which host and date produced
them, and `fylite cases --report` reproduces them on demand.
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "guide"
#: the chapters this gate owns — the worked examples and their entry page
CHAPTERS = ("cases.md", "example-zerod.md", "example-transport.md",
            "example-evolve.md", "example-design.md", "example-reconstruction.md")


@pytest.fixture(scope="module")
def text() -> dict[str, str]:
    missing = [c for c in CHAPTERS if not (GUIDE / c).is_file()]
    assert not missing, f"the guide lost a worked-example chapter: {missing}"
    return {c: (GUIDE / c).read_text(encoding="utf-8") for c in CHAPTERS}


@pytest.fixture(scope="module")
def catalogue() -> set[str]:
    cat = ROOT / "cases" / "catalogue.jsonld"
    if not cat.is_file():
        pytest.skip("the scenario corpus is not in this checkout")
    doc = json.loads(cat.read_text(encoding="utf-8"))
    return {str(m.get("id", "")).rsplit("/", 1)[-1] for m in doc.get("has_part") or []}


def test_every_case_the_guide_names_is_in_the_catalogue(text, catalogue):
    """★Both spellings: `fylite cases --run <id>` and `cases/<id>.jsonld`."""
    named: dict[str, set[str]] = {}
    for chapter, body in text.items():
        ids = set(re.findall(r"fylite cases (?:--\w+ )*([a-z0-9-]+)\b", body))
        ids |= set(re.findall(r"cases/([a-z0-9-]+)\.jsonld", body))
        ids -= {"--run", "--report", "--plan", "--check", "--benchmark", "context", "catalogue"}
        named[chapter] = ids
    unknown = {c: sorted(ids - catalogue) for c, ids in named.items() if ids - catalogue}
    assert not unknown, {"named by the guide, not in the catalogue": unknown,
                         "catalogue has": sorted(catalogue)}
    assert named["cases.md"], "the corpus chapter names no case at all"


def test_every_cases_flag_the_guide_shows_is_declared(text):
    spec = json.loads((ROOT / "python" / "fylite" / "_cli.json").read_text(encoding="utf-8"))
    cmd = next(c for c in spec["commands"] if c["name"] == "cases")
    declared = {f for a in cmd["args"] for f in a["flags"]}
    shown = set()
    for body in text.values():
        shown |= set(re.findall(r"fylite cases ((?:--[\w-]+ ?)+)", body))
    flags = {f for group in shown for f in group.split() if f.startswith("--")}
    assert flags, "the worked examples show no CLI flag at all"
    assert flags <= declared, {"shown but not declared": sorted(flags - declared),
                               "declared": sorted(declared)}


def test_every_scenario_entry_the_guide_calls_exists_with_the_keywords_shown(text):
    """★The failure this catches is the one measured while writing these
    chapters: `S.design.discharge(shape=…, device=…)` reads perfectly and is
    wrong in two keywords at once (the entry takes `target=`, and `device=`
    falls through `**solve_kw` into the kernel call, which rejects it)."""
    from fylite import scenario as S

    calls: list[tuple[str, str, str, str]] = []
    for chapter, body in text.items():
        for m in re.finditer(r"\bS\.(\w+)\.(\w+)\(([^)]*)\)", body, re.S):
            calls.append((chapter, m.group(1), m.group(2), m.group(3)))
    assert calls, "the worked examples call no scenario entry"
    bad = []
    for chapter, line, tool, args in calls:
        fn = getattr(getattr(S, line, None), tool, None)
        if fn is None or not callable(fn):
            bad.append(f"{chapter}: S.{line}.{tool} does not exist")
            continue
        sig = inspect.signature(fn)
        params = sig.parameters
        takes_kw = any(p.kind is p.VAR_KEYWORD for p in params.values())
        given = set(re.findall(r"(\w+)\s*=", args))
        #: ① a keyword the entry does not have.  An entry with `**kw` legitimately
        #: FORWARDS unknown keywords, so it is exempt from this half — which is
        #: exactly why ② exists.
        if not takes_kw:
            for kw in given - set(params):
                bad.append(f"{chapter}: S.{line}.{tool} has no keyword {kw!r} "
                           f"(it takes {sorted(params)})")
        #: ② every REQUIRED keyword is supplied.  This is the half that catches
        #: the mistake measured while writing these chapters:
        #: `S.design.discharge(shape=…, ip=…)` — `shape` sailed through
        #: `**solve_kw` while the required `target` was simply missing, and the
        #: call died in the kernel with an unrelated message.
        required = {n for n, q in params.items()
                    if q.default is q.empty and q.kind is q.KEYWORD_ONLY}
        #: `…` in a chapter means「其余从略」, so an elided call is not judged
        if "…" not in args and "..." not in args:
            for kw in sorted(required - given):
                bad.append(f"{chapter}: S.{line}.{tool} needs keyword {kw!r}, "
                           f"and the call shown does not pass it")
    assert not bad, bad


def test_the_guide_does_not_promise_paths_the_checkout_lacks(text):
    """★`machine_desc/` and `examples/` are both gitignored-or-gone; a chapter
    may TELL a reader how to obtain them (that is the point of the install
    chapter) but must not read as though they were already there."""
    for chapter, body in text.items():
        for path in re.findall(r"`(examples/[\w./-]+)`", body):
            assert False, f"{chapter} names {path}, and examples/ was removed"
    #: machine_desc is allowed — every mention that USES it must be under an
    #: export line or point at the install chapter, which the corpus chapter does
    users = [c for c, b in text.items() if "machine_desc/" in b]
    for c in users:
        b = text[c]
        assert ("FYLITE_DEVICE_DIR" in b or "install.md" in b), (
            f"{c} reads machine_desc/ without saying where it comes from")


def test_each_chapter_states_what_its_family_cannot_answer(text):
    """★The section this repository refuses to publish an example without: a
    worked example that only shows what works teaches the reader to over-read
    it.  Every chapter carries a 「边界」 section (or, for the corpus chapter,
    the refusals table)."""
    for chapter, body in text.items():
        if chapter == "cases.md":
            assert "拒绝" in body, "the corpus chapter drops the refusals"
            continue
        assert re.search(r"^## .*边界", body, re.M), f"{chapter} has no 边界 section"
