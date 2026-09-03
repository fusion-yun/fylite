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
DOCS = ROOT / "docs"
#: ★★2026-09-03 the worked examples became a PART of their own (`docs/examples/`,
#: lifted out of `docs/guide/`), and the `example-` filename prefix went with the
#: move — the directory says it.  So the chapter names below are the new ones and
#: `cases.md` is now `examples/index.md`.
EXAMPLES = DOCS / "examples"
GUIDE = DOCS / "guide"
#: the worked examples and their entry page — the chapters that must carry a
#: 「边界」 section and that this gate reads for runnable calls
CHAPTERS = ("examples/index.md", "examples/zerod.md", "examples/transport.md",
            "examples/evolve.md", "examples/design.md", "examples/reconstruction.md")
#: ★the path rules below apply to BOTH parts, not just the worked examples: the
#: rot they catch (a retired tree named as though it were there) is exactly what
#: the older topic chapters had, and gating only the worked examples would have
#: let them keep it.  Names are stored as they are read below — `guide/x.md` and
#: `examples/x.md` both exist (`reconstruction.md`), so a bare basename would
#: collapse two chapters into one.
BOOK = tuple(sorted([f"examples/{p.name}" for p in EXAMPLES.glob("*.md")]
                    + [f"guide/{p.name}" for p in GUIDE.glob("*.md")]))


@pytest.fixture(scope="module")
def text() -> dict[str, str]:
    missing = [c for c in CHAPTERS if not (DOCS / c).is_file()]
    assert not missing, f"the examples part lost a chapter: {missing}"
    return {c: (DOCS / c).read_text(encoding="utf-8") for c in BOOK}


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
    assert named["examples/index.md"], "the corpus chapter names no case at all"


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


def test_no_chapter_promises_a_retired_path(text):
    """★★`machine_desc/` is ABOLISHED (2026-09-02) and `examples/` is deleted.

    A chapter may still NAME either — saying where a retired thing went is the
    honest thing to do, and the install chapter has to.  What it may not do is
    read as though the path were there: a `machine_desc/east/…` in a code block
    is an instruction, and following it gets a reader nothing.

    So the rule is about SPELLING, not about mentioning: a retired path inside
    backticks (a literal a reader would type or open) fails unless the same line
    marks it as retired.  Device files are spelled `$FYLITE_DEVICE_DIR/…` now.
    """
    RETIRED = ("machine_desc/", "examples/")
    #: ★★`docs/examples/` is the BOOK's worked-examples part (2026-09-03), a live
    #: path that merely ends in the name of a retired one — the repo-root
    #: `examples/` tree.  Substring matching cannot tell them apart, so the live
    #: spelling is named here.  Without this the rule fires on every correct
    #: reference to the new part, which is the failure mode that makes a gate get
    #: switched off rather than obeyed.
    LIVE = ("docs/examples/",)
    MARKS = ("废弃", "退役", "已删除", "不存在", "历史", "test_machine_desc",
             "b4dce77", "不在本仓", "archive")
    bad = []
    for chapter, body in text.items():
        for n, line in enumerate(body.splitlines(), 1):
            for lit in re.findall(r"`([^`\n]+)`", line):
                #: strip the live spellings first, then ask about what is left
                probe = lit
                for live in LIVE:
                    probe = probe.replace(live, "")
                if not any(r in probe for r in RETIRED):
                    continue
                if any(m in line for m in MARKS):
                    continue
                bad.append(f"{chapter}:{n} spells `{lit}` as a live path")
        #: and outside backticks, a bare export line is just as much an instruction
        for n, line in enumerate(body.splitlines(), 1):
            if "FYLITE_DEVICE_DIR=" in line and "machine_desc/" in line:
                bad.append(f"{chapter}:{n} points $FYLITE_DEVICE_DIR at the retired tree")
    assert not bad, bad


def test_each_chapter_states_what_its_family_cannot_answer(text):
    """★The section this repository refuses to publish an example without: a
    worked example that only shows what works teaches the reader to over-read
    it.  Every chapter carries a 「边界」 section (or, for the corpus chapter,
    the refusals table)."""
    for chapter in CHAPTERS:
        body = text[chapter]
        if chapter == "examples/index.md":
            assert "拒绝" in body, "the corpus chapter drops the refusals"
            continue
        assert re.search(r"^## .*边界", body, re.M), f"{chapter} has no 边界 section"
