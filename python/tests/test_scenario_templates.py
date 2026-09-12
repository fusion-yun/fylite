"""``docs/examples/scenario/`` —— 场景模板与场景目录，两个方向都对账。

模板是 `fy run` 的**参数表**：它说这条场景收哪些名字、各是什么类型、哪些是开关。
它由 `tools/make-scenario-templates.py` 从语料生成（名字逐条取自语料自己的
`code/<x>#<名>` IRI），所以本文件钉的不是「写得对不对」，而是**三处不会各自漂**：

1. 生成物与生成器一致（改了语料或 overlay 就得重跑）；
2. 词表 ⊇ 语料实际用到的名字，且每条预设用到的名字模板都认得——否则 `fy run`
   会把一条**跑得起来的**预设按名拒绝；
3. 目录（`lines.jsonld`）覆盖每一个模板，且不设模板的场景在**数据里**给出理由
   （`FYL-DESIGN-17` E-8：不能让散文说存在、命令行说没有）。

★还有一条只能在这里查的：模板**不得**声明与 `fy run` 固定选项同名的参数（E-12 ④）。
固定选项名优先，所以一个叫 `device` 的场景参数永远收不到值——而那是静默的。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
CORPUS = REPO / "docs" / "examples"
SCENARIO = CORPUS / "scenario"
TOOL = REPO / "tools" / "make-scenario-templates.py"
SPEC = json.loads((REPO / "python" / "fylite" / "_cli.json").read_text(encoding="utf-8"))


def _load(name: str) -> dict:
    return json.loads((SCENARIO / f"{name}.jsonld").read_text(encoding="utf-8"))


TEMPLATES = sorted(p.stem for p in SCENARIO.glob("*.jsonld") if p.stem != "lines")
INDEX = _load("lines")


def test_there_are_templates_to_check():
    #: a glob that matches nothing passes everything under it
    assert TEMPLATES, "docs/examples/scenario/ carries no templates"
    assert (SCENARIO / "lines.jsonld").is_file()


def test_the_generated_files_are_current():
    """Re-run the generator; a diff means the corpus moved and these did not."""
    r = subprocess.run([sys.executable, str(TOOL), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout


@pytest.mark.parametrize("name", TEMPLATES)
def test_a_template_declares_its_code_its_line_and_its_parameters(name):
    t = _load(name)
    assert t["prescribes_code"]["id"] == f"code/{name}"
    assert t["type"] == "fyo:ScenarioSpecification", "a template IS a plan, so `run` composes it"
    assert t["fylite:lines"], f"{name} serves no line"
    vocab = t["fylite:vocabulary"]
    assert vocab, f"{name} declares no parameters"
    for key, d in vocab.items():
        assert d["type"] in {"bool", "int", "float", "str", "choice", "time"}, (key, d)
        if d["type"] == "choice":
            assert d.get("choices"), f"{name}.{key} is a choice with no choices"
    #: `-` and `_` are the same character to the parser (E-12 ③), so two names
    #: that differ only by them are one name that silently wins
    keys = [k.replace("-", "_") for k in vocab]
    assert len(set(keys)) == len(keys), f"{name}: two parameters differ only by - / _"


@pytest.mark.parametrize("name", TEMPLATES)
def test_the_vocabulary_covers_every_name_the_corpus_sets(name):
    """A preset the corpus ships must not be refused by name."""
    vocab = set(_load(name)["fylite:vocabulary"])
    used: set[str] = set()
    for f in sorted(CORPUS.glob("*/*.jsonld")):
        if f.parent.name == "scenario":
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        if doc.get("prescribes_code", {}).get("id") != f"code/{name}":
            continue
        for p in doc.get("parameters", []):
            iri = p.get("sets_parameter", "")
            if "#" in iri:
                used.add(iri.split("#", 1)[1])
    assert used <= vocab, f"{name}: the corpus sets {sorted(used - vocab)}, the template does not declare them"


@pytest.mark.parametrize("name", TEMPLATES)
def test_a_switch_expands_to_booleans_the_template_knows(name):
    t = _load(name)
    vocab = t["fylite:vocabulary"]
    for switch, sets in t.get("fylite:switches", {}).items():
        assert sets, f"{name}.{switch} expands to nothing"
        for k, v in sets.items():
            assert k in vocab, f"{name}.{switch} sets `{k}`, which is not in the vocabulary"
            assert vocab[k]["type"] == "bool", f"{name}.{switch} sets the non-boolean `{k}`"
            assert isinstance(v, bool), f"{name}.{switch}.{k} is not a boolean"
        assert switch not in vocab, f"{name}: `{switch}` is both a switch and a parameter"


@pytest.mark.parametrize("name", TEMPLATES)
def test_no_parameter_shadows_a_fixed_option(name):
    """E-12 ④: the fixed option wins, so a shadowed parameter never gets a value."""
    run = next(c for c in SPEC["commands"] if c["name"] == "run")
    fixed = {f.lstrip("-").replace("-", "_") for a in run["args"] for f in a["flags"]}
    t = _load(name)
    names = set(t["fylite:vocabulary"]) | set(t.get("fylite:switches", {}))
    clash = {n for n in names if n.replace("-", "_") in fixed}
    #: the common parameters are the deliberate exception: `shot` / `time` ARE
    #: the fixed options, and the template says it takes them, not that it
    #: declares them
    assert not clash, f"{name}: {sorted(clash)} would be swallowed by the fixed option of the same name"


def test_the_catalogue_covers_every_template_and_states_a_reason_otherwise():
    rows = {r["name"]: r for r in INDEX["fylite:scenarios"]}
    for name in TEMPLATES:
        assert name in rows, f"{name} has a template and is not in the catalogue"
        assert rows[name]["template"] is True
        assert rows[name]["code"] == f"code/{name}"
    for name, row in rows.items():
        if row["template"]:
            assert name in TEMPLATES, f"the catalogue claims a template for {name} and there is none"
        else:
            #: E-8: a scenario the documents name, with no template, states why
            #: in the DATA — a reader must not have to find it in prose
            assert row.get("reason"), f"{name} has no template and no reason"


def test_every_line_has_a_default_scenario_that_exists():
    lines = INDEX["fylite:lines"]
    assert set(lines) == {"analysis", "model", "design", "control"}
    for name, line in lines.items():
        default = line["default"]
        assert default in TEMPLATES, f"the {name} line defaults to {default}, which has no template"
        assert name in _load(default)["fylite:lines"], (
            f"the {name} line defaults to {default}, which does not serve that line")


def test_a_templated_scenario_is_either_runnable_or_says_why_not():
    """Gate ② of FYL-DESIGN-17: the catalogue may not advertise what the door refuses."""
    door = set()
    src = (REPO / "rust" / "fylite_runtime" / "src" / "fyo_interface.rs").read_text(encoding="utf-8")
    block = src.split('Block { name: "CASE_CODES"', 1)
    if len(block) == 2:
        for line in block[1].split("] },", 1)[0].splitlines():
            if 'Row { key: "' in line:
                door.add("code/" + line.split('Row { key: "', 1)[1].split('"', 1)[0])
    if not door:
        pytest.skip("no rust checkout to read CASE_CODES from")
    for row in INDEX["fylite:scenarios"]:
        if not row["template"]:
            continue
        runs = row["code"] in door
        assert row["runnable"] == runs, (
            f"{row['name']}: the catalogue says runnable={row['runnable']} and the kernel door "
            f"says {runs} — re-run tools/make-scenario-templates.py")
        if not runs:
            assert row.get("reason"), f"{row['name']} is not runnable and gives no reason"


# --- C-28: the template's names against the code layer's declared face ------
#
# ★★**Three namings, and until 2026-09-12 only two of them were written down.**
# A template's `fylite:vocabulary` is the names the CORPUS uses (the page's
# controls: `btol` · `wflux` · `usefluxTarget`).  A raw entry's `*_PARAMS` is
# the names that entry's packed block uses.  The layer in between — what a
# `code/<x>` DOOR reads — declared nothing, which is `FYL-REPORT-07`'s C-28 and
# `-16` K-2.  It now does: `rust/build.sh` derives it from the door bodies and
# every local helper they reach, and generates it into all four hosts
# (`_fyo_interface.CODE_PARAMS` here).
#
# ★What this section does NOT do is demand the two lists agree.  They are
# different layers and the corpus name legitimately differs from the setting
# (`btol` → `b_tol`, `wflux` → `weight_flux`).  Two hosts once FILTERED one
# list by the other, and both times values were dropped in silence.  So the
# pins here are: the declaration exists and is non-empty where the door reads
# anything, every template's code is one the kernel carries or is recorded as
# one it does not, and the measured overlap does not go DOWN — that last one
# turns a naming drift into a red test instead of a silent rename.
from fylite import _fyo_interface as _FI  # noqa: E402


#: measured 2026-09-12, `code/<x>` door surface ∩ template vocabulary.  A
#: template whose code the kernel does not carry has no row here at all.
OVERLAP = {"breakdown": 2, "discharge": 10, "evolve": 37, "reconstruction": 2,
           "transport": 16, "zerod": 20}
#: templates whose `prescribes_code` is in NO kernel door (`fy list scenarios`
#: says so per code: "the kernel door does not carry this code").  Recorded
#: rather than skipped: a template for a code nothing completes is a fact a
#: reader needs, and if one of these gains a door the pin turns red and this
#: table is where the answer goes.
NO_DOOR = {"pfwave", "profile", "series"}


def test_the_code_layer_declares_a_parameter_face_at_all():
    """C-28's remedy: every code the kernel carries declares its settings."""
    assert _FI.CODE_PARAMS, "the kernel declares no code parameter face"
    #: a door that reads nothing is allowed and named; anything else must read
    #: something, or the derivation lost that door
    empty = sorted(c for c, v in _FI.CODE_PARAMS.items() if not v["parameters"])
    assert empty == ["adas_species", "channels", "cocos", "shape"], empty
    for code, v in _FI.CODE_PARAMS.items():
        assert v["door"], code
        for key, row in v["parameters"].items():
            assert row["type"] in ("float", "boolean", "string"), (code, key, row)
            assert row["via"], (code, key)


@pytest.mark.parametrize("name", TEMPLATES)
def test_every_template_names_a_code_the_kernel_carries_or_is_recorded(name):
    code = _load(name)["prescribes_code"]["id"].split("/")[-1]
    if name in NO_DOOR:
        assert code not in _FI.CODE_PARAMS, (
            f"{name} gained a kernel door — take it out of NO_DOOR and give it "
            f"an OVERLAP row")
        return
    assert code in _FI.CODE_PARAMS, (
        f"{name} prescribes code/{code}, which no kernel door completes; if that "
        f"is intended, list it in NO_DOOR")


@pytest.mark.parametrize("name", sorted(OVERLAP))
def test_the_template_and_the_door_still_share_the_names_they_shared(name):
    """The overlap may grow, never shrink.

    ★A rename on either side (`chi0` → `chi_0` in the door, say) is exactly
    the silent drift this catches: nothing else in either repo compares the
    two namings, and a `fy run` would simply stop passing that value.
    """
    vocab = set(_load(name)["fylite:vocabulary"])
    door = set(_FI.CODE_PARAMS[name]["parameters"])
    shared = vocab & door
    assert len(shared) >= OVERLAP[name], (
        f"code/{name}: the template and the door now share {len(shared)} names, "
        f"down from {OVERLAP[name]}; lost {sorted((vocab & door) ^ shared)} "
        f"— a rename on one side is silent, so this is the place it shows")
