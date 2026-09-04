"""算例语料的结构不变式（`docs/examples/`：一个例子一个目录）。

★★2026-09-04：这条闸子从 `test_cli_spec.py` 搬来，同批把被它调用的那个函数从
`engine/cli.py` 搬进 `engine/cases.py`。它从前只经命令行的 `fylite cases --check`
到达，而那一层随「Python 侧无命令行」的裁定撤除——**检查本身不是命令行的**：
目录与盘上文件互指、每份计划的类型 / id / 能力栏 / 参数写法、以及退役词汇不再出现，
是语料自己的不变式，命令行只是曾经的一个调用方。
"""
from __future__ import annotations

import pytest

from fylite.engine import cases


def test_the_corpus_is_structurally_sound():
    try:
        found = cases.problems()
    except cases.CorpusMissing as exc:          # off a wheel install
        pytest.skip(str(exc))
    assert found == [], "\n  ".join(["语料有结构问题："] + found)


def test_the_catalogue_and_the_files_name_each_other():
    """★两个方向都要：目录点名的文件在盘上，盘上的文件被目录点名。

    单向检查会漏掉「孤儿文件」——一份谁也没引的计划文档，它跑不到、也不会有人发现
    它跑不到。
    """
    try:
        listed = cases.catalogue()
    except cases.CorpusMissing as exc:
        pytest.skip(str(exc))
    assert listed, "the catalogue lists nothing"
    for e in listed:
        assert e["case_id"] and e["file"], e
        assert (cases.corpus_dir() / e["file"]).is_file(), e
    named = {e["file"] for e in listed}
    on_disk = {p.name for p in cases.corpus_dir().glob("*.jsonld")} - cases._NOT_CASES
    assert on_disk - named == set(), f"orphan files: {sorted(on_disk - named)}"
