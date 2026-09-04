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
