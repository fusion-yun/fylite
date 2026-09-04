"""`fy run` 的行为，对着**构建出来的产物**问，而不是对着源码。

`FYL-DESIGN-17` §14 列了七条门禁；其中五条问的是静态的东西（规格、模板、目录），
由 `test_cli_spec.py` 与 `test_scenario_templates.py` 各自答了。剩下两条只有跑起来才
答得出，就是本文件：

* **门禁 ①（等价式）** —— 场景形 `fy run <线> <场景> k=v` 与计划文件形
  `fy run <那份模板> k=v` 产出**同一份计划**。这一条是 E-21 的可执行形：两种写法
  若各自合成，某一天它们会不一样，而先发现的是拿着两份记录对不上的那个人。
* **门禁 ⑤（离线）** —— `--offline` 下解析不到测量时**按名拒绝**（`refusal.stage:
  measurements`），而不是 panic、也不是连出去。

另加三条同样只有产物答得出的：退役词指路、开关展开的**值**、以及 `--dry-run`
一个字节都不写。

★没有产物就跳过（源码检出里没有它是常态，`bash rust/build.sh --exe` 之后才有），
与 `test_cli_docs_match_the_artifact.py` 同一条规矩。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FY = REPO / "rust" / "fylite_runtime" / "target" / "release" / "fy"
SCENARIO = REPO / "docs" / "examples" / "scenario"


@pytest.fixture(scope="module", autouse=True)
def _built():
    if not FY.is_file():
        pytest.skip(f"no built executable ({FY.relative_to(REPO)}) — bash rust/build.sh --exe")


def run(*argv: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    #: ★空的搜索路径：本文件问的是**命令行自己**的行为，不是某台机器的语料在不在。
    #: 不清掉的话，跑这套闸子的人各自的 $FY_FACTS_PATH 会让同一条断言时真时假。
    env = {"PATH": "/usr/bin:/bin", "FY_FACTS_PATH": "", "FY_CASES_PATH": ""}
    return subprocess.run([str(FY), *argv], capture_output=True, text=True,
                          timeout=120, cwd=str(cwd or REPO), env=env)


def _plan(*argv: str) -> dict:
    r = run(*argv, "--dry-run", "--json")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _without_provenance(plan: dict) -> dict:
    """The plan minus `fylite:from` — the one field the two forms may differ in."""
    out = json.loads(json.dumps(plan))
    for p in out.get("parameters", []):
        p.pop("fylite:from", None)
    return out


def test_the_two_positional_forms_compose_the_same_plan():
    """Gate ①: a line and a scenario, or the template itself — one plan.

    They differ in exactly one field, and it is the field that RECORDS the
    difference: `fylite:from` says `template:transport` on one side and the
    template's path on the other.  Everything a kernel would see is identical.
    """
    by_name = _plan("run", "model", "transport", "chi0=0.4")
    by_path = _plan("run", str(SCENARIO / "transport.jsonld"), "chi0=0.4")
    assert _without_provenance(by_name) == _without_provenance(by_path)
    #: and the provenance itself is present and says which form it was
    froms = {p["sets_parameter"].split("#")[1]: p.get("fylite:from")
             for p in by_name["parameters"]}
    assert froms["chi0"] == "cli"


def test_offline_refuses_by_name_instead_of_reaching_for_a_socket():
    """Gate ⑤: `--offline` with nothing to resolve is a named refusal, exit 1."""
    r = run("run", "analysis", "profile", "shot=1", "--offline")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "[measurements]" in r.stderr, r.stderr
    #: the refusal says what it TRIED — three tiers, each with its own reason
    assert "--input was not given" in r.stderr
    assert "offline" in r.stderr


def test_a_retired_word_names_its_replacement():
    for argv, expect in [
        (["case", "run", "plan.jsonld"], "run <the same plans>"),
        (["case", "describe"], "list kernel"),
        (["data", "facts"], "list facts"),
    ]:
        r = run(*argv)
        assert r.returncode == 2, (argv, r.stdout, r.stderr)
        assert "is retired" in r.stderr and expect in r.stderr, (argv, r.stderr)


def test_a_switch_sets_the_values_the_page_ships():
    """E-18, measured: `--only-magnetic` is the analysis page's `mag` preset.

    ★The values are not this gate's invention either — they and the template's
    both come from `app/assets/scenario-analysis.js`.  What is checked here is
    that the command line APPLIES them, and marks where they came from.
    """
    plan = _plan("run", "analysis", "reconstruction", "--only-magnetic")
    got = {p["sets_parameter"].split("#")[1]: (p["literal_value"], p.get("fylite:from"))
           for p in plan["parameters"]}
    for name in ("kin", "neon", "probefit", "pointfit", "farfit", "vesselfit"):
        assert got[name] == (False, "cli:switch only_magnetic"), (name, got.get(name))
    #: a parameter given explicitly beats the switch, whichever order they are written
    plan = _plan("run", "analysis", "reconstruction", "--only-magnetic", "kin=true")
    got = {p["sets_parameter"].split("#")[1]: (p["literal_value"], p.get("fylite:from"))
           for p in plan["parameters"]}
    assert got["kin"] == (True, "cli")
    assert got["neon"] == (False, "cli:switch only_magnetic")


def test_a_dry_run_writes_nothing_at_all(tmp_path):
    """E-19: `--dry-run` says what would happen; it may not leave anything behind."""
    r = run("run", "model", "transport", "chi0=0.4", "--dry-run", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert list(tmp_path.iterdir()) == [], "a dry run left files in the working directory"


def test_an_unknown_parameter_is_refused_by_name_with_no_record(tmp_path):
    r = run("run", "model", "transport", "chi_zero=0.4", "-o", str(tmp_path / "rec"), cwd=tmp_path)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "takes no parameter" in r.stderr
    assert not (tmp_path / "rec").exists(), "a syntax refusal must not write a record"
