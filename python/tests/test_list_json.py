"""`fy list … --json` —— **每一种形**都答机器可读的那一份。

★★这道闸的由来是一个具体的缺陷（2026-09-07 实测）：`--json` 在 `fy list` 的用法里
声明为「machine-readable answer」，而**点名一台机器**时它被静默忽略——
`fy list devices iter --json` 打的是给人看的排版，退出码 0。声明了却不生效比没有更坏：
调用方拿到的是排版，而没有任何迹象说它不是 JSON。

★所以判据不是「某几条命令答 JSON」，而是**声明了这个参数的每一种形**都答 JSON：
清单形与点名形各查一遍。往 `list` 里加一个子命令，加不加进下面这张表都会被
`test_every_list_subcommand_is_covered` 抓住。

★没有产物就跳过（源码检出里没有它是常态，`bash rust/build.sh --exe` 之后才有），
与 `test_run_behaviour.py` 同一条规矩。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FY = REPO / "rust" / "fylite_runtime" / "target" / "release" / "fy"


@pytest.fixture(scope="module", autouse=True)
def _built():
    if not FY.is_file():
        pytest.skip(f"no built executable ({FY.relative_to(REPO)}) — bash rust/build.sh --exe")


def run(*argv: str) -> subprocess.CompletedProcess:
    #: ★空的搜索路径：问的是**命令行自己**，不是某台机器的语料在不在。装置描述
    #: 编译在二进制里（2026-09-05 裁定），所以清空之后 `list devices` 照样答得出。
    env = {"PATH": "/usr/bin:/bin", "FY_FACTS_PATH": "", "FY_CASES_PATH": ""}
    return subprocess.run([str(FY), *argv], capture_output=True, text=True,
                          timeout=120, cwd=str(REPO), env=env)


def _json(*argv: str):
    r = run("list", *argv, "--json")
    assert r.returncode == 0, f"`fy list {' '.join(argv)} --json` 失败：{r.stderr}"
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:  # noqa: PERF203 — the message is the point
        pytest.fail(f"`fy list {' '.join(argv)} --json` 没有答 JSON："
                    f"{e}\n前 200 字：{r.stdout[:200]!r}")


#: 每一种形一行：`(参数, 期望的形状)`。`list` 是清单形，`map` 是点名形。
#: ★点名形的名字从**清单形自己**取，不写死——写死的那天，语料一换闸子就红，
#: 而红的原因与它要查的事无关。
FORMS: list[tuple[str, ...]] = [
    ("devices",),
    ("experiments",),
    ("scenarios",),
    ("presets",),
    ("facts",),
    ("kernel",),
    ("lines",),
]


@pytest.mark.parametrize("form", FORMS, ids=lambda f: " ".join(f))
def test_the_listing_form_answers_json(form):
    got = _json(*form)
    assert isinstance(got, (list, dict)), f"{form}: 答的不是一个 JSON 值"


def test_naming_one_device_answers_json_too():
    """★这就是 2026-09-07 那个缺陷本身。"""
    listed = _json("devices")
    if not listed:
        pytest.skip("这份构建里没有装置条目")
    ident = listed[0]["id"]
    one = _json("devices", ident)
    assert isinstance(one, dict) and one["id"] == ident
    #: 点名形答的**至少**是清单形那几个字段说的同一件事
    assert one["root"] == listed[0]["root"]
    assert bool(one["card"]) == listed[0]["card"]
    assert bool(one["manifest"]) == listed[0]["manifest"]
    assert bool(one["rights"]) == listed[0]["rights"]


def test_naming_one_scenario_answers_json_too():
    listed = _json("scenarios")
    named = [s for s in listed if s.get("template")]
    if not named:
        pytest.skip("这份构建里没有带模板的场景")
    one = _json("scenarios", named[0]["name"])
    assert one["name"] == named[0]["name"]
    assert one["code"] == named[0]["code"]
    assert len(one["parameters"]) == named[0]["parameters"], (
        "点名形数出来的参数个数与清单形那一列对不上")
    for p in one["parameters"]:
        assert set(p) == {"name", "key", "kind", "choices", "min", "max",
                          "from_device", "note"}


def test_every_list_subcommand_is_covered():
    """★闸子的前提：`list` 多一个子命令而这里没跟上时，这条会说出来。

    子命令表从 `fy list --help` 自己读 —— 与实现同一个源，不是这里抄一份。
    """
    help_text = run("list", "--help").stdout
    body = help_text.split("commands:", 1)[1].split("arguments:", 1)[0]
    declared = {line.split()[0] for line in body.splitlines() if line.strip()}
    covered = {f[0] for f in FORMS}
    assert declared == covered, (
        f"`fy list` 的子命令与这张表对不上：只在命令行里 {sorted(declared - covered)}，"
        f"只在表里 {sorted(covered - declared)}")


def test_the_flag_is_declared_where_it_is_honoured():
    """★声明与生效要在同一层。`--json` 写在 `fy list` 的参数里，所以每一种形都得认它。"""
    assert "--json" in run("list", "--help").stdout
