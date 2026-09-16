"""新册 `docs/benchmark/` 的入册闸：一条记录必须自带它以后可复算所需的东西。

★★**为什么要有这道闸**：旧册（`docs/benchmark-legacy/`，2026-09-16 退役）实测 52 条记录里
`FR-*` / `NR-*` **零命中**——没有一条说得出自己在验哪条需求，于是"覆盖够不够"只能靠人
逐条比对需求表，而人每次比出来的答案都不一样。同一批毛病还有：`scenario` 指针 30/52、
数据指针全带 sha256 的 40/52、索引手写漏掉最后一条记录。**这些都不是疏忽，是没有闸。**

本闸把新册 README〈一条记录必须自带的五样〉变成可执行判据。记录为零时它照样有意义：
它守的是"进来的每一条都合格"，不是"已经进来了多少条"。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BM = ROOT / "docs" / "benchmark"
ID_RE = re.compile(r"^(EQ|TR)-\d{3}-[a-z0-9-]+$")
KINDS = {"verification", "benchmark", "validation"}
VERDICTS = {"pass", "fail", "inconclusive", "unevaluated"}


def records() -> list[tuple[str, dict]]:
    return [(p.name, json.loads(p.read_text(encoding="utf-8")))
            for p in sorted((BM / "records").glob("*.jsonld"))]


@pytest.fixture(scope="module")
def requirement_ids() -> set[str]:
    d = json.loads((BM / "requirements.jsonld").read_text(encoding="utf-8"))
    return {r["id"] for r in d["requirement"]}


def test_the_requirement_tree_is_present_and_sane(requirement_ids):
    """★需求树是本册的组织轴；它缺了，`coverage.md` 就无从谈起。"""
    assert len(requirement_ids) >= 50, len(requirement_ids)
    d = json.loads((BM / "requirements.jsonld").read_text(encoding="utf-8"))
    for r in d["requirement"]:
        assert r["level"] in ("MUST", "SHOULD", "MAY"), r
        assert r["title"], r
        assert r["srs"] in ("FYTOK-SRS-03", "FYTOK-SRS-04"), r
    #: 需求树是**快照**，真源在 fytok 仓——这一条写在文件里，读者不必猜
    assert "快照" in json.dumps(d, ensure_ascii=False)


@pytest.mark.parametrize("name,rec", records() or [pytest.param("<none>", None, marks=pytest.mark.skip(
    reason="新册尚无记录：本闸守的是「进来的每一条都合格」，不是「已经进来了多少条」"))])
def test_a_record_carries_the_five_things(name, rec, requirement_ids):
    """README〈一条记录必须自带的五样〉，逐条可执行。"""
    assert ID_RE.match(rec["id"].split("/")[-1]), f"{name}: id 不合 <域>-<需求号>-<短名>"
    assert rec.get("comparison_kind") in KINDS, name
    assert rec.get("overall_verdict") in VERDICTS, name

    #: 五之五：需求。缺它的记录不收——一条不知道自己在验什么的记录，回答不了"覆盖够不够"
    reqs = rec.get("requirement")
    assert reqs, f"{name}: 没有 `requirement[]`"
    unknown = [r for r in reqs if r not in requirement_ids]
    assert not unknown, f"{name}: 引用了需求树里没有的号 {unknown}"

    #: 五之一 / 五之三：输入与口径
    assert rec.get("criteria"), f"{name}: 没有判据"
    assert rec.get("validity_domain"), f"{name}: 没有适用域（口径）"
    #: 五之四：不可比的部分
    assert rec.get("caveat"), f"{name}: 没有 caveat（不可比的部分）"

    #: 五之二：出处——每个数据指针都要带 sha256。旧册只有 40/52 做到
    for x in rec.get("run", {}).get("has_input", []):
        assert x.get("storage_uri"), f"{name}: 数据项没有 storage_uri"
        assert x.get("checksum", "").startswith("sha256:"), \
            f"{name}: {x.get('storage_uri')} 没有 sha256"


@pytest.mark.parametrize("name,rec", records() or [pytest.param("<none>", None, marks=pytest.mark.skip(
    reason="新册尚无记录"))])
def test_every_gate_a_record_names_actually_exists(name, rec):
    """★记录声明的门必须真的在。

    2026-09-16 实测过反例：V-23 的门从 7 条扩到 9 条，而记录里仍只声明 7 条——新增的两条
    判据没有挂在任何门上，内核漂了也不会红。那种缺口靠读代码发现不了，靠这条能。
    """
    for g in rec.get("run", {}).get("realizes", []):
        target = g["name"]
        path, _, test = target.partition("::")
        f = ROOT / path
        assert f.is_file(), f"{name}: 门文件不存在 {path}"
        if test:
            assert re.search(rf"def {re.escape(test)}\b", f.read_text(encoding="utf-8")), \
                f"{name}: {path} 里没有 {test}"


def test_the_generated_files_are_current():
    """★`coverage.md` / `index.jsonld` 是生成件。手维护的索引一定会漂——旧册的
    `reports/README.md` 漏掉最后一条记录，就是因为它跟记录不同源。"""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "benchmark-coverage.py"), "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout


def test_the_retired_register_is_not_tracked():
    """★旧册 2026-09-16 移出版本控制（用户裁定），磁盘留一份仅供查阅。

    它若重新进库，站点会同时渲染两套互相矛盾的编号体系。"""
    r = subprocess.run(["git", "ls-files", "docs/benchmark-legacy"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.stdout.strip() == "", "docs/benchmark-legacy 重新进了版本控制"
