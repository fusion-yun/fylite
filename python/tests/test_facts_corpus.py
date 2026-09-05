"""`facts/` 是拖回来的参考数据，而每一条都带着一份**许可账**——这里守那份账。

★★**为什么这道闸子存在。** 2026-09-04 起本仓的构建分两种：**内部版**带全部装置，
**公开版**不带 EAST（它是一次真实放电 #137985 的实测读数，属运行方），也不带上游
逐 IDS 明写 `redistributable: false` 的那些（ITER 的 `tf` / `pf_active`，权属方是
ITER Organization——那不是本仓能给的授权）。

这条分界一旦只活在某个人的记忆里，它的失败方式是**静默的**：一次公开构建多带了一台
机器，没有任何东西会红，而错误在制品发出去之后才可能被发现，且发现者不是我们。所以
判据落成文件（`facts/device/<id>/rights.json`）、问答面落成一条命令
（`tools/facts-publish.py --flavour public --list`），本模块守它们一致。

★`facts/` 是 gitignored 的**拖回输入**：没有它时本模块整体跳过（skip 不是 pass，
理由与 `test_machine_desc.py` 同一条）。有它时，下列每一条都必须成立。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
#: ★★2026-09-05 用户裁定：**仓顶已无 `facts/`**。拖回来的语料落在 `dist/facts/`
#: （构建暂存区），本模块随之改问那里——问错地方的表现不是红，是**整模块跳过**，
#: 而跳过看起来和「这台机器上没拖语料」一模一样。
FACTS = ROOT / "dist" / "facts"
#: 今天只有 device 一域有内容；amns / experiment 进来时本模块按域走，不必改。
DEVICES = FACTS / "device"
TOOL = ROOT / "tools" / "facts-publish.py"

pytestmark = pytest.mark.skipif(
    not DEVICES.is_dir(),
    reason="没有 dist/facts/device/ —— 它是拖回的输入（tools/abox-to-facts.py --all）",
)


def _pulled() -> list[pathlib.Path]:
    #: ★★2026-09-04 实测：`pytestmark` 的 skipif 挡不住这一步。`@parametrize` 在
    #: **收集期**求值，早于任何 skip 判定，所以 `facts/` 不在时这里抛
    #: `FileNotFoundError`，**整轮 pytest 收集失败**——一个可选的本地输入不在场，
    #: 打断的却是全部 1700 多条闸子。缺输入的结局只能是跳过并点名（`conftest.py`
    #: 那条政策的原话），所以这里先问目录在不在。
    if not DEVICES.is_dir():
        return []
    return sorted(d for d in DEVICES.iterdir() if d.is_dir())


def _rights(d: pathlib.Path) -> dict:
    return json.loads((d / "rights.json").read_text(encoding="utf-8"))


def test_there_is_something_to_check():
    """★空目录会让下面每一条断言都成立——先证明它不空。"""
    assert _pulled(), "devices/ 在，但一台机器都没有"


def test_every_published_document_is_json_a_browser_can_parse():
    """页面 `fetch` 的那一份必须是**严格 JSON**：不许 NaN / Infinity。

    ★★2026-09-05 实测的一次真事故。WEST 的壁面轮廓 `Baffle` 末点 r/z 都是 NaN
    （上游 MATLAB 定长数组的补位），`json.dumps` 缺省把它写成裸 `NaN`——而 **JSON 没有
    这个词**。`app/assets/devices.js` 的 `r.json()` 当场抛 `SyntaxError`，于是这一台
    在浏览器里整份读不出来；而三种制品（站点 · 可执行文件 · 轮）**全部**带着它发了
    出去，构建从头到尾是绿的。

    ★闸子问的是**发布出去的那一份**（`facts/<域>/<id>.jsonld`），不是卡片：卡片是
    YAML，`.nan` 在那里是合法的；出问题的是**换语法那一步**。产出方
    （`tools/abox-to-facts.py` 的 `finite()`）今天要么摘掉成对轮廓的末位补位、要么按名
    拒绝，本条钉的是那一步真的做了。
    """
    docs = sorted(FACTS.glob("*/*.jsonld"))
    if not docs:
        pytest.skip("搜索路径上没有发布出去的文档")

    def strict(c):
        raise ValueError(c)

    bad = []
    for f in docs:
        try:
            json.loads(f.read_text(encoding="utf-8"), parse_constant=strict)
        except ValueError as e:
            bad.append(f"{f.relative_to(FACTS)}: {e}")
    assert not bad, (
        "这些发布出去的文档不是严格 JSON，浏览器读不出来：\n  " + "\n  ".join(bad))


@pytest.mark.parametrize("dev", [d.name for d in _pulled()] or ["<none>"])
def test_every_device_carries_a_rights_ledger(dev: str):
    """一份没有许可账的装置描述，下一个人无从判断它能不能发出去。

    ★所以账是**必需**的，且必须回答两个问题：进不进内部版、进不进公开版。
    没有账与账说「不行」在这里是同一个答案（都不发），但它们不是同一件事——
    前者是缺陷，由本条抓。
    """
    if dev == "<none>":
        pytest.skip("no devices")
    p = DEVICES / dev / "rights.json"
    assert p.is_file(), f"{dev}: 没有 rights.json —— 拖回工具没写，或它是手工放进来的"
    r = json.loads(p.read_text(encoding="utf-8"))
    for key in ("device", "source", "declared", "internal", "public", "ruling"):
        assert key in r, f"{dev}: rights.json 缺 {key}"
    assert r["device"] == dev
    assert isinstance(r["public"], bool) and isinstance(r["internal"], bool)
    assert r["ruling"], f"{dev}: 裁定一栏是空的——那等于没有判据"


def test_east_is_internal_only():
    """用户裁定 2026-09-04：**公开版不含 EAST 装置数据**。

    ★单独一条，不并进上面那条参数化：它是这次分界的**起因**，而一条起因该被
    直接断言，不该只作为某张表里的一行被顺带覆盖。
    """
    p = DEVICES / "east" / "rights.json"
    if not p.is_file():
        pytest.skip("EAST 未拖回")
    r = json.loads(p.read_text(encoding="utf-8"))
    assert r["public"] is False, "EAST 进了公开版——裁定说它不该进"
    assert r["internal"] is True, "EAST 也不该被挡在内部版之外"
    assert "#137985" in r["ruling"] or "放电" in r["ruling"], \
        "裁定一栏没说 EAST 为什么只进内部版——理由是账的一半"


def test_third_party_blocks_are_carried_through():
    """上游逐 IDS 明写 `redistributable: false` 的，公开版不带。

    ★这一条与本仓的裁定**无关**：ITER 的 `tf` / `pf_active` 权属方是 ITER
    Organization，本仓再怎么裁定也给不了那个授权。所以它不写在 `INTERNAL_ONLY`
    那张表里，而是从 A-Box 自己的声明读出来——**上游说的话，本仓不改写**。
    """
    p = DEVICES / "iter" / "rights.json"
    if not p.is_file():
        pytest.skip("ITER 未拖回")
    r = json.loads(p.read_text(encoding="utf-8"))
    assert set(r["public_excluded_ids"]) >= {"tf", "pf_active"}, (
        "ITER 的 tf / pf_active 上游写着 redistributable=false，"
        f"而公开版的排除表是 {r['public_excluded_ids']}")


def _ask(flavour: str) -> list[str]:
    out = subprocess.run([sys.executable, str(TOOL), "--flavour", flavour, "--list"],
                         capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        pytest.skip(f"发布计划问不出来（{out.stderr.strip()[:80]}）")
    #: 问答面按 `<域>/<id>` 作答；本模块只看 device 那一域。
    return [ln.split("/", 1)[1].strip() for ln in out.stdout.splitlines()
            if ln.strip().startswith("device/")]


def test_the_question_face_agrees_with_the_ledgers():
    """构建脚本问的那条命令，与账本说的必须是同一件事。

    ★★两个真源就是没有真源：如果 `--publishable` 自己判一遍许可、而 `rights.json`
    另判一遍，某一天它们会给出不同的答案，且**先发现的人是拿到制品的那个**。
    """
    pub, internal = _ask("public"), _ask("internal")
    have = {d.name for d in _pulled()}
    for dev in sorted(have):
        r = _rights(DEVICES / dev)
        if dev in internal or dev in pub:
            assert r["internal"], f"{dev}: 命令说它进得了构建，账说进不了"
        if r["public"] and dev in internal:
            assert dev in pub, f"{dev}: 账说公开版可带，命令没列它"
        if not r["public"]:
            assert dev not in pub, f"{dev}: 账说只进内部版，命令却把它列进了公开版"
    assert set(pub) <= set(internal), "公开版带了内部版没有的机器"


def test_nothing_internal_only_reaches_a_public_artifact():
    """★这道闸子真正的用处：**发出去的东西**里不得有只进内部版的机器。

    ★★判的是**发布者**，不是源树。2026-09-04 起 `app/facts/device` 是指向
    `facts/device/` 的符号链接（单一数据源），所以源树里当然什么都有——那是对的，本机
    开发要用 EAST。会不会发出去，取决于两个发布者：静态站点与桌面可执行文件，
    而它们都问同一个问题面 `tools/facts-publish.py`。这里就问那个面。
    """
    internal_only = {d.name for d in _pulled() if not _rights(d)["public"]}
    if not internal_only:
        pytest.skip("没有只进内部版的机器")
    r = subprocess.run([sys.executable, str(TOOL), "--flavour", "public", "--list"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    shipped = {ln.split("/", 1)[1].strip() for ln in r.stdout.splitlines()
               if ln.strip().startswith("device/")}
    leaked = sorted(internal_only & shipped)
    assert not leaked, (
        f"这些机器只进内部版，公开版的发布计划却带着它们：{leaked}")


def test_the_embed_table_carries_no_device_document():
    """内嵌资源表里**一台装置也没有**——那份重复已经撤掉，且不许回来。

    ★★2026-09-05 用户裁定：**页面也走中间层 wasm，撤掉 `facts.jsonld`**。
    在此之前同一批 432 KB 在一个可执行文件里装两遍：一遍在这张表里（给页面的
    HTTP 面 `include_bytes!`），一遍在 `facts.rs` 里（给命令行）。两份字节、两条
    通路，而**没有任何东西保证它们描述同一批机器**——目录说有七台、文件只有六台，
    这种事不会有任何东西红。

    今天页面经 `fylite_runtime.wasm` 读那唯一一份，所以这张表里不该再有装置文档。
    本条守的是**那份重复不回来**：它一旦回来，回来的方式是有人给生成器加回一段
    「按发布规则逐台加进来」，而那一段看起来完全合理。

    ★这条**从前是反过来的**（「表要与缺省版的发布计划一致」）。方向换了，因为表里
    该有的东西换了；再往前它拿 `devices/<id>.jsonld` 匹配，而路径 2026-09-04 起是
    `facts/device/<id>.jsonld`，于是那一版**恒真、从未生效**。
    """
    table = ROOT / "rust" / "fylite_runtime" / "src" / "bin" / "app" / "assets.rs"
    if not table.is_file():
        pytest.skip("no assets.rs")
    text = table.read_text(encoding="utf-8")
    leaked = [ln.strip() for ln in text.splitlines() if '"facts/' in ln]
    assert not leaked, (
        "内嵌资源表里又有 facts 文档了——那是 2026-09-05 撤掉的那一份重复：\n  "
        + "\n  ".join(leaked[:5]))


def test_the_compiled_in_tier_is_the_default_flavour():
    """编进 `libfylite_runtime.so` 的那几台 = 缺省版别的发布计划。

    ★★这是许可闸的**可执行形**。装置文档从 2026-09-05 起只有一个制品
    （`facts.rs`，由 `.so` 与 `.wasm` 各编进去），所以「发出去的是哪几台」这个问题
    今天只有一处答案可查——就是这里。编多了一台，命令行、页面、轮**同时**多一台，
    而三处都不会红。

    ★读的是**装着的那份 `.so`**，不是源码：源码里那张表是空的（`build.rs` 在
    `$OUT_DIR` 里生成它），所以只有问运行时才问得到真话。
    """
    from fylite import facts as _f
    have = {d.name for d in _pulled()}
    if not have:
        pytest.skip("没拖语料")
    if _f.bundled_count() == 0:
        pytest.skip("这份 .so 没编装置信息（bash rust/build.sh）")
    r = subprocess.run([sys.executable, str(TOOL), "--flavour", "internal", "--list"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    planned = {ln.split("/", 1)[1].strip() for ln in r.stdout.splitlines()
               if ln.strip().startswith("device/")} & have
    built = {n for n in _f.bundled_ids("device") if n != "catalogue"} & have
    assert built == planned, (
        f"编进 .so 的与缺省（internal）发布计划不一致：多了 {sorted(built - planned)}，"
        f"少了 {sorted(planned - built)}。重跑 `bash rust/build.sh --internal`。")


# --------------------------------------------------------------------------- #
# 多源：搜索路径、优先级、以及**不跨根拼**                                      #
# --------------------------------------------------------------------------- #
def _make_root(tmp, ident="east", note="override", with_rights=True):
    d = tmp / "device"
    (d / ident).mkdir(parents=True, exist_ok=True)
    (d / f"{ident}.jsonld").write_text(
        json.dumps({"@type": "fylite:DeviceDescription/1",
                    "fylite:device_id": ident, "note": note}), encoding="utf-8")
    if with_rights:
        (d / ident / "rights.json").write_text(
            json.dumps({"device": ident, "internal": True, "public": True,
                        "ruling": note}), encoding="utf-8")
    return tmp


def test_the_first_root_wins_the_whole_entry(tmp_path):
    """★★优先级的单位是**条目**，不是值。

    两个根都描述 EAST，而它们描述得不一样（一个带参考放电，另一个线圈几何更新）。
    取第一个根的文档、却取第二个根的许可账——或者反过来——会造出一台**没人运行的
    机器**，而且不报错。所以文档、卡片、许可账三样必须同根。
    """
    from fylite import facts

    hi = _make_root(tmp_path / "hi", note="HIGH")
    try:
        facts.use([hi])
        e = facts.find("device", "east")
        assert e is not None and e.root == hi
        assert "HIGH" in e.document.read_text(encoding="utf-8")
        #: 许可账必须来自**同一个**根
        assert e.rights_path is not None
        assert e.rights_path.parent.parent.parent == hi
        assert facts.rights("device", "east")["ruling"] == "HIGH"
    finally:
        facts.use(None)


def test_a_lower_root_still_contributes_what_the_higher_one_lacks(tmp_path):
    """★并集，逐条决胜——低优先级的根补上高优先级没有的那些，不补它有的。"""
    from fylite import facts

    hi = _make_root(tmp_path / "hi", ident="onlyhere", note="HIGH")
    try:
        facts.use([hi, FACTS])
        ids = {e.ident: e.root for e in facts.entries("device")}
        assert ids.get("onlyhere") == hi, "高优先级独有的那台没进并集"
        if (FACTS / "device" / "iter.jsonld").is_file():
            assert ids.get("iter") == FACTS, "低优先级该供的那台没供上"
    finally:
        facts.use(None)


def test_an_entry_with_no_ledger_is_not_publishable(tmp_path):
    """★没有许可账 = 不发。与「账说不行」同一个答案，理由同一条：默认必须是「不能」。"""
    from fylite import facts

    hi = _make_root(tmp_path / "hi", ident="unledgered", with_rights=False)
    try:
        facts.use([hi])
        assert facts.find("device", "unledgered") is not None
        assert facts.rights("device", "unledgered") is None
        r = subprocess.run([sys.executable, str(TOOL), "--facts", str(hi),
                            "--flavour", "internal", "--list"],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        assert "device/unledgered" not in r.stdout, \
            "没有账的条目进了发布计划"
        assert "unledgered" in r.stderr, "拒绝了，却没说是哪一条、为什么"
    finally:
        facts.use(None)


def test_a_named_root_that_is_not_there_is_named(tmp_path):
    """★路径给错了要当场说。

    等到某个条目找不到时才报「没有这台机器」，会把「路径写错了」说成「语料里没有
    它」——两句话指向完全不同的处置。
    """
    from fylite import facts

    missing = tmp_path / "nope"
    try:
        facts.use([missing])
        bad = facts.problems()
        assert bad and str(missing) in bad[0]
    finally:
        facts.use(None)


def _exe():
    """The built executable, or a skip — it is a build product, not a source."""
    #: ★★2026-09-04 只有一个地方可找：`fy` 是 `rust/build.sh --exe` 的产物，
    #: 而 Python 包**不再带**一份（用户裁定；`FYL-DESIGN-15` R-4/R-5）。
    p = ROOT / "rust" / "fylite_runtime" / "target" / "release" / "fy"
    if p.is_file():
        return p
    import shutil
    found = shutil.which("fy")
    if found:
        return pathlib.Path(found)
    pytest.skip("no `fy` executable built (bash rust/build.sh --exe)")


def test_the_two_resolvers_agree(tmp_path):
    """★★搜索路径有**两份实现**，这条把它们钉在一起。

    Rust 那份（`fylite_runtime::facts`）是命令行走的，Python 这份
    （`fylite.facts`）是包里调用走的——与 `_cli.json` 的三个解析器同一姿态：
    一份规则、多处建出、一道闸子比对。两处各判一遍优先级，某天它们会给出不同的
    答案，而**先发现的人是拿到制品的那个**。

    比的是最容易分头出错的那件事：**每一条由哪个根供出**。
    """
    from fylite import facts

    hi = _make_root(tmp_path / "hi", ident="east", note="HIGH")
    _make_root(tmp_path / "hi", ident="onlyhigh", note="HIGH")
    exe = _exe()

    #: ★★2026-09-04：这一问搬去了 `list`（`FYL-DESIGN-17` E-24：发现面只有一处）。
    #: 本闸子比的是**两个解析器**，不是命令词——搬家不改它问的东西，只改怎么问。
    r = subprocess.run([str(exe), "list", "facts", "--facts", str(hi), "device"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    rust = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            rust[parts[0]] = pathlib.Path(parts[1]).resolve()

    try:
        facts.use([hi])
        py = {e.ident: e.root.resolve() for e in facts.entries("device")}
    finally:
        facts.use(None)

    assert py, "the Python resolver found nothing to compare"
    assert set(py) == set(rust), (
        "the two resolvers disagree about WHICH entries exist:\n"
        f"  python only: {sorted(set(py) - set(rust))}\n"
        f"  rust only  : {sorted(set(rust) - set(py))}")
    differ = {k: (py[k], rust[k]) for k in py if py[k] != rust[k]}
    assert not differ, (
        "the two resolvers disagree about WHICH ROOT supplies an entry — "
        f"that is the answer a record has to be able to name: {differ}")
