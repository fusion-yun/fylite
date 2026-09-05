"""The bundled binaries must speak the ABI this package expects.

★★Why this exists: at 2026-08-19 the repository's committed
``python/fylite/_lib/libfylite_kernel.so`` spoke **ABI 62** while its own generated
``_abi.py`` said **66**.  Four ABI bumps had landed with the rebuilt library
left in the working tree, so a fresh clone refused to load the very library
it ships — every kernel call raising ``KernelError`` — while every
developer's checkout was fine, because theirs had been rebuilt in place.

That is the worst shape a defect can have: invisible exactly where the work
happens, and total everywhere else.  The gate below is cheap and fires in
the one place it needs to.

★★2026-09-02：制品不再随仓走（`.gitignore` 抬头写了为什么），于是「已提交的那份
是不是构建出来的那份」这个问题连主语都没有了。ABI 一致性那几道不受影响——它们问的
是**磁盘上这一份**与 `_abi.py` 是否对得上，而磁盘上那一份仍然必须在。
换方向留下的那道闸见 `test_the_binaries_are_not_in_the_repository`。
"""
from __future__ import annotations

import ctypes
import json
import re
import subprocess
from pathlib import Path

import pytest

from fylite import _abi
from fylite._paths import KERNEL_LIB

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(not KERNEL_LIB.exists(),
                                reason="libfylite_kernel.so not built "
                                       "(rust/build.sh)")


def _abi_of(path: Path) -> int:
    lib = ctypes.CDLL(str(path))
    lib.fylite_rs_abi_version.restype = ctypes.c_uint32
    return int(lib.fylite_rs_abi_version())


def test_the_bundled_library_speaks_the_abi_this_package_expects():
    assert _abi_of(KERNEL_LIB) == _abi.ABI_VERSION



def test_the_binaries_are_not_in_the_repository():
    """★★★2026-09-02 裁定反转：**制品不随仓走，只在打包发布时才装进去。**

    在此之前这里有两道相反的闸——「已提交的那份是不是构建出来的那份」，针对
    `libfylite_kernel.so` 与三个 `.wasm` 各一道。它们防的是一种真实事故（2026-08-19：
    已提交的 `.so` 说 ABI 62、而同仓生成的 `_abi.py` 说 66，四次 bump 的重建都留在
    工作树里没提交，于是**新克隆拒绝加载它自己带的库**，而每个开发者的检出都好好的）。

    那道闸的主题随裁定一起消失了：没有「已提交的那份」，就无从问它是不是构建出来的。
    ★但**裁定本身需要一道闸**，否则一次顺手的 `git add -A` 就能把它推翻，而且推翻得
    悄无声息——二进制进了 git 不会有任何一步报错，只会让历史每次重建胖 2.7 MB。
    所以这道闸问反过来的问题：**它们有没有被误提交。**

    ★这道闸不问「磁盘上有没有」。本地必须有（wheel 的 package-data 装的就是它，
    页面 fetch 的就是那三个 `.wasm`），只是不该被跟踪；`.gitignore` 顶上那段写的
    是同一件事，这里是它的执行者。
    """
    #: ★★`*.so.*` / `*.wasm.*` 是**这道闸的一半**（2026-09-05）。制品从这天起按
    #: Linux 的习惯带版本后缀（`tools/soname.sh`）：真文件叫 `fylite_rs.wasm.0.0.1`，
    #: 扩展名不再在末尾，上面那两条 pathspec 一个都匹配不到。漏了这两条，这道闸
    #: 会对一棵已经把五份二进制提交进去的树答绿——而它存在的全部理由就是不让那件事
    #: 悄无声息地发生。`.gitignore` 抬头那两行是同一次改动的另一半。
    p = subprocess.run(["git", "ls-files", "--",
                        "*.so", "*.wasm", "*.so.*", "*.wasm.*"],
                       cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:                       # not a work tree: nothing to say
        pytest.skip("not a git work tree")
    tracked = [ln for ln in p.stdout.splitlines() if ln.strip()]
    assert tracked == [], (
        "构建产物被提交进仓了：\n  " + "\n  ".join(tracked) + "\n"
        "本仓不跟踪 .so / .wasm（见 .gitignore 抬头）——它们走发布通道："
        "wheel 的 package-data、Releases 附件、站点同步。"
        "撤法：git rm --cached <路径>（文件留在磁盘上，构建与页面照常）。")


def test_the_wasm_artifacts_carry_the_same_abi():
    """The browser refuses on a mismatch too, and its three artifacts have to
    land in the same commit as the ABI.

    ★★2026-08-26: the JS constant this used to read is GONE.  It was
    `var ABI_EXPECT = 113;`, hand-kept, and editing it was a manual step on
    every bump — the failure mode being precisely the one two lines up in
    this file (a binary committed against another declaration).  `fylite.js`
    now reads `FyVersion.abi` out of the GENERATED `assets/version.js`, so
    what is checkable here is that the generated files agree; that the
    binding really reads them is `test_deck_names_have_one_source.py`'s.
    """
    #: ★2026-09-01：`rust/wasm/abi.json` 在内核仓；构建时它被**装进本仓**
    #: `app/assets/abi.json`（见 kernel 的 rust/build.sh）。读装进来的那份，本仓自足。
    meta = json.loads((ROOT / "app/assets/abi.json").read_text())
    assert meta["abi_version"] == _abi.ABI_VERSION
    js = (ROOT / "app/assets/version.js").read_text()
    line = next(l for l in js.splitlines() if "abi:" in l)
    got = int(line.split("abi:")[1].split(",")[0].strip().rstrip("};"))
    assert got == _abi.ABI_VERSION, (
        f"assets/version.js says abi {got}, the kernel says "
        f"{_abi.ABI_VERSION} — run rust/build.sh")


def test_the_generated_prose_pages_carry_the_current_abi():
    """★★The SIX prose pages are generated artefacts too, and they print the
    ABI in their footer.

    `tools/make-app-pages.mjs` bakes `interface <abi>` into
    `index` / `features` / `credits`, each in two languages, and commits them
    — so an ABI bump that does not re-run the generator ships six pages
    telling every reader the wrong interface version.  That is not
    hypothetical: the v113 -> v114 bump did exactly this, and it was found
    only because a browser gate happened to be runnable that day.

    ★This gate is here rather than in `validate-site.mjs` (which already
    checks it) because this tier ALWAYS runs: the same bump also broke four
    node harnesses, and both holes existed for the same reason — a generated
    file's readers were not enumerated from the tree.  A gate nobody runs on
    the day of the bump is not a gate on the bump.
    """
    pages = sorted((ROOT / "app").glob("*.html"))
    #: only the GENERATED prose pages carry the footer; the scenario pages
    #: get theirs injected at run time by `site.js`
    carriers = [q for q in pages if "class=\"ver\"" in q.read_text(encoding="utf-8")]
    assert len(carriers) == 6, [q.name for q in carriers]
    #: ★EVERY number on that line, not「至少有一个对的」.  The footer says the
    #: interface version TWICE — once in the `title` attribute (always
    #: English) and once in the visible text (the page's own language) — and
    #: a check satisfied by one occurrence passes a page whose two halves
    #: disagree.  ★Written after the first version of this gate did exactly
    #: that: a deliberately corrupted page passed it.
    stale = []
    for q in carriers:
        txt = q.read_text(encoding="utf-8")
        line = next(l for l in txt.splitlines() if 'class="ver"' in l)
        #: both spellings the generator emits, in either language
        got = [int(v) for v in
               re.findall(r"(?:interface|接口)\s+(\d+)", line)]
        if len(got) != 2 or any(v != _abi.ABI_VERSION for v in got):
            stale.append(f"{q.name}: {got} in {line.strip()[:100]}")
    assert not stale, (
        "these generated pages print an ABI that is not the kernel's "
        f"({_abi.ABI_VERSION}), or do not print it twice — run "
        "`node tools/make-app-pages.mjs`:\n  " + "\n  ".join(stale))


#: The two artifacts the pages fetch — one per native `.so` (2026-09-05 用户裁定:
#: dke 与 tglf 合为 `kernel_ext`).  ★It was three until that ruling; the third
#: (`fylite_dke.wasm`) was built and shipped in all three release forms while
#: **nothing loaded it** — `app/assets/fylite.js` has no dke entry point.
WASM = ("fylite_rs", "fylite_kernel_ext")

#: ★2026-09-01：底账随 `docs/note/` 留在 fylite_kernel。探测得到就核，探不到就点名
#: 跳过——一条永远红的判据与没有判据是同一件事，而且更吵。
def _ledger_path():
    import os
    cands = ([Path(os.environ["FYLITE_KERNEL"])] if os.environ.get("FYLITE_KERNEL")
             else [ROOT.parent / "fylite_kernel", ROOT.parent / "fylite_dev"])
    for c in cands:
        q = c / "docs/note/app-provenance.md"
        if q.is_file():
            return q
    return None


LEDGER = _ledger_path()


def test_the_provenance_ledger_records_the_wasm_that_is_here():
    """★★The release ledger is what says WHICH kernel the published demo
    carries, and it had drifted 48 ABI versions.

    It recorded two artifacts at ABI v47 — 318 638 and 395 682 bytes — while
    the tree held three at v95, one of which (``fylite_dke.wasm``) it had
    never heard of.  Nothing noticed because the only thing that read it was
    ``publish-app.yml``, which is manual-only and currently held back on
    purpose; and that step could not have noticed either, because it read
    ``docs/note/app-provenance.md`` while the file is under
    ``docs/note/`` — so under ``set -euo pipefail`` it died on a
    missing file, and its "no sha256 recorded" branch was unreachable.  The
    publish gate had never run.

    ★A record only a disabled workflow reads is a record nobody reads.  It is
    checked here, in the default tier, on every commit — which is also where
    it will now fail the moment somebody rebuilds the wasm without
    refreshing it, i.e. exactly when the drift starts rather than 48
    versions later.
    """
    import hashlib
    if LEDGER is None:
        pytest.skip("底账 docs/note/app-provenance.md 在 fylite_kernel；"
                    "设 $FYLITE_KERNEL 指向一份检出即可核对")
    text = LEDGER.read_text(encoding="utf-8")
    missing = []
    for name in WASM:
        path = ROOT / "app/assets" / f"{name}.wasm"
        if not path.exists():
            missing.append(f"{name}.wasm is not in app/assets")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in text:
            missing.append(f"{name}.wasm sha256 {digest} is not in the ledger")
    assert not missing, (
        "the provenance ledger does not describe the artifacts in this tree:\n  "
        + "\n  ".join(missing)
        + f"\n\nRefresh the 二进制 table in {LEDGER} — "
          "`publish-app.yml` refuses to publish on a mismatch, so a stale "
          "ledger blocks a release rather than mis-describing one.")


def test_the_publish_workflow_reads_the_ledger_where_it_is():
    """★The bug under the bug.  A gate that points at the wrong path does not
    report "wrong path" — it reports whatever the shell does with a missing
    file, and here that was an early exit that looked like any other
    infrastructure failure."""
    wf = ROOT / ".github/workflows/publish-app.yml"
    if not wf.exists():
        pytest.skip("no publish workflow in this tree")
    text = wf.read_text(encoding="utf-8")
    #: the ASSIGNMENT, not any mention: the file's comments name the old
    #: path deliberately, to record what the bug was
    ledger = [l.split("=", 1)[1].strip() for l in text.splitlines()
              if l.strip().startswith("ledger=")]
    assert ledger == ["src/docs/note/app-provenance.md"], (
        f"publish-app.yml reads the ledger from {ledger}, and it lives at "
        "docs/note/app-provenance.md")
