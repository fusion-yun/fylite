"""新册 `docs/benchmark/` 的入册闸：一条记录必须自带它以后可复算所需的东西。

★★**为什么要有这道闸**：旧册（`docs/benchmark-legacy/`，2026-09-16 退役）实测 52 条记录里
`FR-*` / `NR-*` **零命中**——没有一条说得出自己在验哪条需求，于是"覆盖够不够"只能靠人
逐条比对需求表，而人每次比出来的答案都不一样。同一批毛病还有：`scenario` 指针 30/52、
数据指针全带 sha256 的 40/52、索引手写漏掉最后一条记录。**这些都不是疏忽，是没有闸。**

本闸把新册 README〈一条记录必须自带的六样〉变成可执行判据。记录为零时它照样有意义：
它守的是"进来的每一条都合格"，不是"已经进来了多少条"。

★本册按**物理专题两级**组织（一级 3 组 / 二级 16 章），需求号降为记录的属性——所以这里
除了守记录，还守**轴本身**：域树是否覆盖全部需求、每一章是否真的在盘上且入了 toc、
判据抄录件是否还跟得上上游 SRS。轴烂了，记录再合格也拼不出一本能读的册子。
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
#: ★机器读的那一半住在 `meta/`：轴（域树 / 需求树）、判据抄录件、词表、薄索引与基准内核。
#: 给人读的那一半（README + 两张生成件 + 三组十六章）留在册子根上——目录本身就把
#: 「谁读它」说清楚，不必靠扩展名去猜。
META = BM / "meta"
KINDS = {"verification", "benchmark", "validation"}
VERDICTS = {"pass", "fail", "inconclusive", "unevaluated"}
REVIEW = {"draft", "reviewed", "superseded"}
BEGIN = "<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->"
END = "<!-- END GENERATED -->"


def read(name: str) -> dict:
    return json.loads((META / name).read_text(encoding="utf-8"))


def records() -> list[tuple[str, dict]]:
    return [(p.name, json.loads(p.read_text(encoding="utf-8")))
            for p in sorted((BM / "records").glob("*.jsonld")) if p.name != "TEMPLATE.jsonld"]


def flat_domains() -> list[tuple[dict, dict]]:
    return [(g, d) for g in read("domains.jsonld")["group"] for d in g["domain"]]


@pytest.fixture(scope="module")
def requirement_ids() -> set[str]:
    return {r["id"] for r in read("requirements.jsonld")["requirement"]}


@pytest.fixture(scope="module")
def domain_ids() -> set[str]:
    return {d["id"] for _, d in flat_domains()}


# ─────────────────────────────────────────────────────────────── 轴

def test_the_requirement_tree_is_present_and_sane(requirement_ids):
    """★需求树是记录的追溯目标；它缺了，`coverage.md` 就无从谈起。"""
    assert len(requirement_ids) >= 50, len(requirement_ids)
    d = read("requirements.jsonld")
    for r in d["requirement"]:
        assert r["level"] in ("MUST", "SHOULD", "MAY"), r
        assert r["title"], r
        assert r["srs"] in ("FYTOK-SRS-03", "FYTOK-SRS-04"), r
    #: 需求树是**快照**，真源在 fytok 仓——这一条写在文件里，读者不必猜
    assert "快照" in json.dumps(d, ensure_ascii=False)


def test_the_domain_tree_partitions_every_requirement(requirement_ids):
    """★★域树是本册的轴：每条需求**恰好**落在一章里。

    落两处，读者会在两章看到同一条判据而不知道以哪一处为准；一处不落，那条需求就从
    册子上消失了——而消失的缺口不会有人发现。两种都得红。
    """
    seen: dict[str, str] = {}
    dup: list[tuple[str, str, str]] = []
    for _, d in flat_domains():
        for rid in d["requirement"]:
            if rid in seen:
                dup.append((rid, seen[rid], d["id"]))
            seen[rid] = d["id"]
    assert not dup, f"同一条需求落在两章里：{dup}"
    assert seen.keys() == requirement_ids, {
        "域树漏了": sorted(requirement_ids - seen.keys()),
        "域树多了": sorted(seen.keys() - requirement_ids),
    }


def test_every_chapter_exists_and_carries_its_generated_block():
    """★每一章都要在盘上，且带生成块的标记——没有标记，生成器无处落笔。"""
    for _, d in flat_domains():
        p = BM / d["path"]
        assert p.is_file(), f"章页不在盘上：{d['path']}"
        text = p.read_text(encoding="utf-8")
        assert BEGIN in text and END in text, f"{d['path']} 没有生成块标记"
        #: ★标记之外必须有手写散文。一章只有生成块，等于把「按专题散文阐述」做成了表格
        prose = text.split(BEGIN)[0]
        assert len(prose) > 400, f"{d['path']} 的手写散文太短（{len(prose)} 字符）"


def test_every_chapter_is_in_the_book():
    """★★写了而没入 toc 的章，等于没写。

    2026-09-16 实测过这条的反面：上一版把整册从 `myst.yml` 摘出去，站点上什么都不剩，
    而仓里的文件一个不少——盘上有、书里没有，光看目录看不出来。
    """
    toc = (ROOT / "docs" / "myst.yml").read_text(encoding="utf-8")
    for _, d in flat_domains():
        assert f"benchmark/{d['path']}" in toc, f"{d['path']} 没有入 docs/myst.yml"


# ────────────────────────────────────────────────────────── 判据抄录件

def test_the_transcript_records_which_version_it_copied_from():
    """★★抄录必须记下**抄的是哪一版**，否则它三个月后就是一份无法追责的转述。

    本册抄录而不引用，是因为上游 SRS 是 `distribution: internal`——公开册的读者打不开它。
    但抄录会漂，而两份源都还是 `status: WD`。所以每份源记版本号与 sha256。
    """
    t = read("transcript.jsonld")
    assert t["source"], "抄录件没有记源"
    for s in t["source"]:
        assert s["checksum"].startswith("sha256:"), s
        assert s["version"] and s["version"] != "?", s
        assert s.get("distribution") == "internal", s
    assert t["criterion_row"], "抄录件一行判据都没有"


def test_the_transcript_is_still_current_with_the_upstream_srs():
    """★源在场时，抄录件必须跟得上；源不在场时，明说盘上这份抄的是哪一版。

    ★**这不是一条可以静默 skip 的闸。** 源不在本检出是**正常**的（SRS 在另一个仓），
    但"跳过"与"通过"不是一回事：跳过时也要把抄录件记的版本报出来，让读日志的人看得见
    它有多旧。
    """
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "benchmark-transcribe.py"), "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode == 2:
        pytest.skip((r.stderr or r.stdout).strip())
    assert r.returncode == 0, r.stderr or r.stdout


# ─────────────────────────────────────────────────────────────── 记录

@pytest.mark.parametrize("name,rec", records() or [pytest.param("<none>", None, marks=pytest.mark.skip(
    reason="新册尚无记录：本闸守的是「进来的每一条都合格」，不是「已经进来了多少条」"))])
def test_a_record_carries_the_six_things(name, rec, requirement_ids, domain_ids):
    """README〈一条记录必须自带的六样〉，逐条可执行。"""
    slug = rec["id"].split("/")[-1]
    dom = rec.get("domain")
    assert dom in domain_ids, f"{name}: `domain` 不是域树里的域（{dom}）"
    assert slug.startswith(dom + "-") and re.fullmatch(r"[a-z0-9-]+", slug), \
        f"{name}: id 不合 <域id>-<短名>：{slug}"
    assert rec.get("comparison_kind") in KINDS, name
    assert rec.get("overall_verdict") in VERDICTS, name

    #: 六之五：需求。缺它的记录不收——一条不知道自己在验什么的记录，回答不了"覆盖够不够"
    reqs = rec.get("requirement")
    assert reqs, f"{name}: 没有 `requirement[]`"
    unknown = [r for r in reqs if r not in requirement_ids]
    assert not unknown, f"{name}: 引用了需求树里没有的号 {unknown}"

    #: 六之一 / 六之三：输入与口径
    assert rec.get("criteria"), f"{name}: 没有判据"
    assert rec.get("validity_domain"), f"{name}: 没有适用域（口径）"
    #: 六之四：不可比的部分
    assert rec.get("caveat"), f"{name}: 没有 caveat（不可比的部分）"

    #: 六之二：出处——每个数据指针都要带 sha256。旧册只有 40/52 做到
    for x in rec.get("run", {}).get("has_input", []):
        assert x.get("storage_uri"), f"{name}: 数据项没有 storage_uri"
        assert x.get("checksum", "").startswith("sha256:"), \
            f"{name}: {x.get('storage_uri')} 没有 sha256"


@pytest.mark.parametrize("name,rec", records() or [pytest.param("<none>", None, marks=pytest.mark.skip(
    reason="新册尚无记录"))])
def test_a_record_carries_its_provenance(name, rec):
    """★★六之六：追溯——版本、变更、评审，以及它跑在哪个内核上。

    **理由是一条记录会被改判。** 旧册的 `V-23` 改判过两次（τ 的差先归给导电接头，查明后
    改为超导线圈屏蔽）。改判是记录制度**在起作用**的证据，不是它的污点——所以改判本身
    必须留在册里，而不是把旧结论悄悄覆盖掉。一份只有末态、没有变更史的记录，读者无从
    判断它是"一直如此"还是"上周刚翻过案"。
    """
    p = rec.get("provenance")
    assert p, f"{name}: 没有 `provenance`"
    assert re.fullmatch(r"\d+\.\d+", str(p.get("record_version", ""))), \
        f"{name}: `record_version` 不合 <主>.<次>"
    assert p.get("recorded"), f"{name}: 没有 `recorded`（首次入册日期）"
    assert p.get("review_status") in REVIEW, f"{name}: `review_status` 不合法"

    chg = p.get("change")
    assert chg, f"{name}: 没有 `change[]`（逐条变更）"
    for c in chg:
        assert c.get("record_version") and c.get("date") and c.get("summary"), f"{name}: 变更条目不全 {c}"
    #: ★变更史的末条必须就是当前版本，否则这份史是断的
    assert str(chg[-1]["record_version"]) == str(p["record_version"]), \
        f"{name}: `change[]` 末条 {chg[-1]['record_version']} 不是当前版本 {p['record_version']}"

    #: ★已评审的记录必须点得出评审人；草稿不强求——但那就别声称已评审
    if p["review_status"] == "reviewed":
        rv = p.get("reviewer")
        assert rv, f"{name}: 声称已评审却没有 `reviewer[]`"
        for x in rv:
            assert x.get("name") and x.get("date") and x.get("verdict"), f"{name}: 评审条目不全 {x}"

    #: ★这次验证跑在哪个内核上——状态页据此判新鲜度。没有它，一条记录永远显示 unknown
    k = (rec.get("run") or {}).get("kernel") or {}
    assert k.get("checksum", "").startswith("sha256:"), \
        f"{name}: `run.kernel.checksum` 缺失——没有它就判不了这条记录过没过期"


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


# ───────────────────────────────────────────────────────────── 生成件

def test_the_generated_pages_are_current():
    """★`coverage.md` / `status.md` / `index.jsonld` 与各章的生成块都是生成件。

    手维护的索引一定会漂——旧册的 `reports/README.md` 漏掉最后一条记录，就是因为它跟
    记录不同源。
    """
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "benchmark-book.py"), "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout


def test_the_reference_kernel_is_declared():
    """★★新鲜度的基准是一份**声明件**，不是本机当场算的指纹。

    本页入库并受 `--check` 守；它若嵌入跑命令那台机器的内核指纹，换一台机器门就红，
    而那不是任何人的错。基准记在 `kernel.json` 里，内核一换就有意更新它——于是所有记在
    旧内核上的记录当场转 `stale`，CI 据此重跑。这就是「随内核变更自动验证」的接口。
    """
    k = json.loads((META / "kernel.json").read_text(encoding="utf-8"))
    assert k.get("checksum", "").startswith("sha256:"), k
    assert k.get("recorded"), k


def test_every_record_has_a_report_and_the_book_lists_it():
    """★★2026-09-16 用户裁定「records 逐条配以测试报告且收入 myst」，两头都守。

    **生成了而没入 toc，等于没生成**——站点上看不到它，而仓里文件一个不少，光看目录发现不了。
    这与「域章没入 toc」是同一个病，本册 2026-09-16 已经栽过一次（整册被摘出 myst.yml）。

    ★另一头也要守：**盘上多出来的报告**（记录已删而报告还在）同样是错的。一份没有正本的
    报告是最坏的一种文档——它看起来权威，却没有任何东西保证它还成立。
    """
    toc = (ROOT / "docs" / "myst.yml").read_text(encoding="utf-8")
    want = {name.removesuffix(".jsonld") for name, _ in records()}
    have = {p.stem for p in (BM / "reports").glob("*.md")} if (BM / "reports").is_dir() else set()

    assert want <= have, f"这些记录没有报告页：{sorted(want - have)}"
    assert have <= want, f"这些报告页没有对应的记录（正本已不在）：{sorted(have - want)}"
    for r in sorted(want):
        assert f"benchmark/reports/{r}.md" in toc, f"报告 {r}.md 没有入 docs/myst.yml"


def test_the_round_summaries_are_in_the_book():
    """★收敛说明是**手写**的散文（一轮一页），所以它不会被生成器补上——漏挂 toc 没人会发现。

    ★它与报告的分工写在 README 里：报告是记录的可读面（生成、随记录动），
    收敛说明是一轮工作的快照（手写、不改写上一页）。
    """
    d = BM / "summary"
    if not d.is_dir():
        pytest.skip("尚无收敛说明")
    toc = (ROOT / "docs" / "myst.yml").read_text(encoding="utf-8")
    pages = sorted(p.name for p in d.glob("*.md"))
    assert pages, "summary/ 在盘上却是空的——空目录就是一个声明了却不存在的东西"
    for name in pages:
        assert f"benchmark/summary/{name}" in toc, f"收敛说明 {name} 没有入 docs/myst.yml"


def test_the_tree_on_disk_is_the_tree_the_readme_declares():
    """★★声明的目录与盘上的目录必须一致——两个方向都要。

    **这是旧册烂掉的方式之一**：它的 `reports/README.md` 是手维护的索引，漏掉了最后一条
    记录；同一个病的另一面是**声明了却不存在的目录**——读者按 README 去找，扑空，然后
    再也不信这张表。所以这里两头都守：

      · 盘上有的目录，README 里必须提到（否则读者遇到一个没人解释的目录）；
      · README 里写的 `meta/…` 路径，盘上必须真的有（否则读者按图索骥扑空）。

    ★册子根上**只放给人读的书**（README + 两张生成件 + 三组十六章的目录）。机器读的那一半
    住在 `meta/` / `records/` / `readings/`——目录本身就把「谁读它」说清楚，不必靠扩展名猜。
    """
    readme = (BM / "README.md").read_text(encoding="utf-8")

    #: 一、册子根上不得散着数据文件
    loose = sorted(p.name for p in BM.iterdir() if p.is_file() and p.suffix in (".json", ".jsonld"))
    assert not loose, f"这些数据文件散在册子根上，该进 meta/：{loose}"

    #: 二、根上的 .md 只有书的那三页（章页在 <组>/ 下）
    top_md = sorted(p.name for p in BM.iterdir() if p.suffix == ".md")
    assert top_md == ["README.md", "coverage.md", "status.md"], top_md

    #: 三、盘上每个目录都要在 README 的**树状图**里露过面
    #: ★★2026-09-16 收紧过一次：原先只查 `f"{d}/" in readme`，于是 `domains/` 靠着表格里
    #: 那行 `meta/domains.jsonld` 的子串**蒙混过关**——当时树状图写的还是 `eq/ · mhd/ · tr/`，
    #: 早就不对了，闸子却是绿的。**一条能被子串蒙过的断言，等于没有这条断言。**
    #: 现在只在树状图那一段里找，且要求它是行首的那个条目。
    tree = readme.split("```")[1] if "```" in readme else ""
    for d in sorted(p.name for p in BM.iterdir() if p.is_dir()):
        assert re.search(rf"^[├└]── {re.escape(d)}/", tree, re.M), \
            f"目录 {d}/ 在盘上却没在 README 的树状图里"

    #: 四、README 写的 meta/ 路径都要真的在
    for ref in sorted(set(re.findall(r"`(meta/[A-Za-z0-9_.-]+)`", readme))):
        assert (BM / ref).is_file(), f"README 声明了 {ref}，盘上没有"

    #: 五、meta/ 六件缺一不可——少任何一件，生成器或闸子当场就不成立
    want = {"context.jsonld", "domains.jsonld", "requirements.jsonld",
            "transcript.jsonld", "index.jsonld", "kernel.json"}
    assert want <= {p.name for p in META.iterdir()}, sorted(want - {p.name for p in META.iterdir()})


def test_the_retired_register_is_not_tracked():
    """★旧册 2026-09-16 移出版本控制（用户裁定），磁盘留一份仅供查阅。

    它若重新进库，站点会同时渲染两套互相矛盾的编号体系。"""
    r = subprocess.run(["git", "ls-files", "docs/benchmark-legacy"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.stdout.strip() == "", "docs/benchmark-legacy 重新进了版本控制"
