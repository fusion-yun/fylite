"""`fy list` 的表：`from` 那一列写**路径**，底下一行写生效的搜索路径。

★★这个文件改过两回，两回都是同一件事的两面：

  2026-09-08 上午——`from` 那一列对着十三行打同一段 `/home/<user>/…/dist/facts`。
  改成编号 + 图例；这个文件当时钉的是「一个根只印一次」。
  2026-09-08 下午——用户裁定**编号不传达任何信息**，改回路径，另加一行
  `$PATH` 形的搜索路径（内置那一档写 `<buildin>`，排最前）。

所以「印几次」不再是判据，钉在这里的是**剩下那两条仍然成立的**：
`from` 是路径不是编号（读者不必再去查别处），以及**家目录不出现在输出里**
（贴出来的日志不带用户名）。制品里禁开发机路径是同一条规矩的另一半。

★没有产物就跳过（源码检出里没有它是常态，`bash rust/build.sh --exe` 之后才有），
与 `test_list_json.py` 同一条规矩。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FY = REPO / "rust" / "fylite_runtime" / "target" / "release" / "fy"
STAGED = REPO / "dist" / "facts" / "device"
BUILTIN = "<buildin>"


@pytest.fixture(scope="module", autouse=True)
def _built():
    if not FY.is_file():
        pytest.skip(f"no built executable ({FY.relative_to(REPO)}) — bash rust/build.sh --exe")
    if not STAGED.is_dir():
        pytest.skip("no staged corpus (dist/facts) — python3 tools/abox-to-facts.py --all")


@pytest.fixture(scope="module")
def corpus(tmp_path_factory) -> Path:
    """两台机器的一个小语料，落在 `$HOME` 之外——`from` 那一列因此打**绝对**路径，
    可以逐字比。"""
    root = tmp_path_factory.mktemp("facts") / "facts"
    (root / "device").mkdir(parents=True)
    picked = 0
    for d in sorted(STAGED.iterdir()):
        if d.is_dir() and (STAGED / f"{d.name}.jsonld").is_file():
            shutil.copytree(d, root / "device" / d.name)
            shutil.copy(STAGED / f"{d.name}.jsonld", root / "device")
            picked += 1
        if picked == 2:
            break
    if picked < 2:
        pytest.skip("staged corpus carries fewer than two documented devices")
    return root


def run(corpus: Path, *argv: str, home: str = "/nonexistent") -> str:
    env = {"PATH": "/usr/bin:/bin", "HOME": home,
           "FY_FACTS_PATH": str(corpus), "FY_CASES_PATH": ""}
    r = subprocess.run([str(FY), *argv], capture_output=True, text=True,
                       timeout=120, cwd=str(REPO), env=env)
    assert r.returncode == 0, f"`fy {' '.join(argv)}` 失败：{r.stderr}"
    return r.stdout


def rows(out: str) -> list[str]:
    #: ★表 = 表头之后到第一个空行为止。不按列匹配——列改过两回了
    #: （`described` → `description` / `licence` / `ids`，`kind` 加了又撤），
    #: 而按内容匹配的那一版把页脚「13 devices; …」也认成了一行。
    lines = out.splitlines()
    head = next(i for i, l in enumerate(lines) if l.startswith("device "))
    out_rows = []
    for l in lines[head + 1:]:
        if not l.strip():
            break
        out_rows.append(l)
    return out_rows


def test_from_is_a_path_not_a_number(corpus: Path):
    """`from` 那一格自己就答得出「哪个根」，不必再去查一张图例。

    ★判据把两处对起来：列里那一格必须是**底下那行搜索路径上的一个**。分开查的话，
    某一天列里印一个不在搜索路径上的根，两处各自都还“对”。"""
    out = run(corpus, "list", "devices")
    got = rows(out)
    assert len(got) >= 2, f"表里没有行：\n{out}"
    on_path = set(search_path(out))
    assert str(corpus) in on_path, f"临时语料没上搜索路径：\n{out}"
    for l in got:
        tail = l.split()[-1]
        assert not tail.isdigit(), f"`from` 又成了编号：{l!r}"
        assert tail in on_path, f"`from` 不是搜索路径上的根：{l!r}"


def search_path(out: str) -> list[str]:
    """底下那一行 `facts: a:b:c` 拆成根。"""
    line = next(l for l in out.splitlines() if l.startswith("facts: "))
    return line[len("facts: "):].split(":")


def test_the_search_path_line_is_path_shaped(corpus: Path):
    """底下那一行是 `$PATH` 的样子：冒号分隔，内置那一档排最前。"""
    parts = search_path(run(corpus, "list", "devices"))
    assert str(corpus) in parts, parts
    #: ★这份二进制带不带内置语料是构建期的事（`--no-facts` 就不带），
    #: 所以判据是「带了就排第一」，不是「一定带」。
    if BUILTIN in parts:
        assert parts[0] == BUILTIN, parts


def test_a_home_relative_root_is_written_with_a_tilde(corpus: Path):
    """家目录那一截收成 `~` —— 贴出来的日志因此不带用户名。"""
    out = run(corpus, "list", "devices", home=str(corpus.parent))
    assert f"~/{corpus.name}" in out, out
    assert str(corpus.parent) not in out, out
