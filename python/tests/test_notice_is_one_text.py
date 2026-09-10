"""三个界面同一份提示词——押在一起，而不是各自照做。

★★2026-09-08 用户裁定：*web ui / cli / python 三个界面统一提示词*。真源是
``python/fylite/_notice.json``；三个宿主各自渲染它：

* **浏览器** —— ``app/assets/lang-{zh,en}.js`` 的两个词条（页眉警示带）；
* **``fy``** —— ``rust/fylite_runtime/src/banner.rs``，编译期 ``include_str!``
  同一个文件；
* **本包** —— :mod:`fylite.notice`，导入时印一次。

★为什么值得一道闸子：三处**各自都还在说话**，所以走样了也不像坏了——而见过其中
一面的人会以为自己已经被告知。这道闸子问的正是「三面说的是不是同一句」。

★★Rust 那一面这里只查**它读的是不是同一个文件**（那一句 ``include_str!``）：
比对渲染结果要先有一份构建好的 ``fy``，而这个包在没有它的机器上也要能测。真正
跑起来的比对在 ``cargo test`` 那边（``banner::tests``）。
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

import fylite
from fylite import notice

REPO = Path(fylite.__file__).resolve().parents[2]
SPEC = json.loads((Path(fylite.__file__).with_name("_notice.json")).read_text(encoding="utf-8"))
LANGS = ("zh", "en")


def _catalogue(lang: str) -> dict:
    """``app/assets/lang-<lang>.js`` 的词条，够用就好：本文件只问两个键。

    ★不去跑那份 JS（要一个 JS 运行时），也不去解析整个对象字面量：按键抓那一行，
    抓不到就红——一个「什么也没抓到因而通过」的闸子是这仓最常点名的失败形状。
    """
    src = (REPO / "app" / "assets" / f"lang-{lang}.js").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^\s*'([\w.]+)':\s*'(.*)',\s*$", src, re.M):
        out[m.group(1)] = m.group(2)
    assert out, f"lang-{lang}.js: 一个词条也没抓到 —— 这个闸子的抓法过期了"
    return out


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("nid", [n["id"] for n in SPEC["notices"]])
def test_the_browser_says_what_the_notice_file_says(nid: str, lang: str):
    """页眉警示带的字，与真源逐字相同。"""
    n = next(x for x in SPEC["notices"] if x["id"] == nid)
    got = _catalogue(lang).get(n["i18n_key"])
    assert got == n[lang], (
        f"{n['i18n_key']} ({lang}): 浏览器说「{got}」，_notice.json 说「{n[lang]}」"
        " —— 三个界面就此各说各的")


@pytest.mark.parametrize("lang", LANGS)
def test_this_package_prints_exactly_those_sentences(lang: str):
    """本层渲染出来的几句，就是真源里该版别的那几句，且**次序相同**。"""
    for flavour in ("internal", "public"):
        want = [n[lang] for n in SPEC["notices"] if flavour in n["flavours"]]
        assert notice.notices(lang, flavour) == want
        body = notice.banner(lang, flavour)
        for s in want:
            assert s in body
        for n in SPEC["notices"]:
            if flavour not in n["flavours"]:
                assert n[lang] not in body, (
                    f"{flavour} 版印出了只属于别的版别的那一句：{n[lang]}")


def test_the_rust_host_reads_the_same_file():
    """``fy`` 是**编译期**读它的，所以这里查那一句 ``include_str!`` 指向哪。"""
    rs = (REPO / "rust" / "fylite_runtime" / "src" / "banner.rs").read_text(encoding="utf-8")
    m = re.search(r'include_str!\("([^"]+)"\)', rs)
    assert m, "banner.rs 里没有 include_str! —— 那一面的文本已经不是从真源来的了"
    target = (REPO / "rust" / "fylite_runtime" / "src" / m.group(1)).resolve()
    assert target == Path(fylite.__file__).with_name("_notice.json").resolve(), (
        f"banner.rs 读的是 {target}，不是这个包读的那一份")


def test_the_internal_only_notice_never_reaches_a_public_build():
    """★这一条是**限制**那一句的判据，两个方向都查。"""
    io = [n for n in SPEC["notices"] if "public" not in n["flavours"]]
    assert io, "_notice.json 里没有任何一条只属于内部版 —— 那条裁定不见了"
    for n in io:
        for lang in LANGS:
            assert n[lang] not in notice.banner(lang, "public")
            assert n[lang] in notice.banner(lang, "internal")


def test_nothing_is_printed_when_nobody_is_watching():
    """★★2026-09-08 用户裁定：*fy cli 交互时显示 banner*。两个会打印的宿主同一条
    规则，与 Rust 侧 ``banner::tests::nothing_is_printed_when_nobody_is_watching``
    是同一组判据：管道上一个字也不印（**包括提示词**——那条流上没有读者），有人
    看着时安静只收掉装饰。"""
    assert SPEC["show_when"] == "interactive"
    assert notice.decide(False, False) == notice.NOTHING
    assert notice.decide(False, True) == notice.NOTHING
    assert notice.decide(True, False) == notice.FULL
    assert notice.decide(True, True) == notice.NOTICES_ONLY


class _Stream(io.StringIO):
    def __init__(self, tty: bool):
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_the_printer_obeys_that_rule_and_force_overrides_it():
    """★闸子问的是**打印那一步**，不只是那个判定函数：`print_banner` 曾经无条件
    印，而把规则写进 `decide` 却忘了在打印处问它，是一个全绿的改动。"""
    piped, tty = _Stream(False), _Stream(True)
    notice.print_banner(piped)
    assert piped.getvalue() == ""
    notice.print_banner(tty)
    assert SPEC["wordmark"][0] in tty.getvalue()
    #: ★显式要它的调用方拿得到：`force` 就是「有人在看」的意思
    forced = _Stream(False)
    notice.print_banner(forced, force=True)
    assert SPEC["wordmark"][0] in forced.getvalue()


def test_a_stream_that_cannot_answer_isatty_is_treated_as_unwatched():
    """★问不出来就当没有人看着：默认不印比默认印安全——印错地方的招牌会混进别人
    的数据。（pytest 的捕获流、某些嵌入宿主都属这一类。）"""
    class Mute(io.StringIO):
        def isatty(self):
            raise ValueError("captured stream")

    m = Mute()
    notice.print_banner(m)
    assert m.getvalue() == ""


def test_quiet_drops_the_decoration_and_keeps_the_notices():
    """★安静关得掉招牌，关不掉提示词——与 Rust 侧同名的那条断言同一句话。"""
    loud = notice.banner("zh", "internal", quiet=False)
    quiet = notice.banner("zh", "internal", quiet=True)
    assert SPEC["spdx"] in loud and SPEC["spdx"] not in quiet
    assert SPEC["wordmark"][0] in loud and SPEC["wordmark"][0] not in quiet
    for s in notice.notices("zh", "internal"):
        assert s in quiet


def test_the_env_names_are_the_ones_the_notice_file_declares():
    """两处写着同一个名字（见 :mod:`fylite.notice` 抬头的理由），这里把它们钉住。"""
    assert notice.QUIET_ENV == SPEC["quiet_env"]
    assert notice.LANG_ENV == SPEC["lang_env"]


#: 命令行那一个二进制。★不构建它——这是 pytest，不是构建系统；没构建就跳过，
#: 而**跳过要说清跳过的是什么**（见下面 skip 的原话）。
_EXE = next((p for p in (REPO / "rust" / "fylite_runtime" / "target" / v / "fy"
                         for v in ("release", "debug")) if p.exists()), None)


def _run_on_a_terminal(args: list[str], env_extra: dict) -> str:
    """在一个**真 pty** 上跑 `fy`，把它写到 stderr 的东西收回来。

    ★★为什么非要 pty：这条闸子问的正是「终端上看得见吗」，而 `subprocess.PIPE`
    是管道——用管道去问这个问题，得到的答案永远是「看不见」，且它会**通过**，
    因为规则说管道上就不该印。一个用错工具的闸子在这里恰好是全绿的。
    """
    import os
    import pty
    import subprocess

    master, slave = pty.openpty()
    env = {**os.environ, **env_extra}
    proc = subprocess.Popen([str(_EXE), *args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=slave, env=env)
    os.close(slave)
    out = b""
    try:
        while True:
            try:
                chunk = os.read(master, 65536)
            except OSError:      # 子进程关掉了那一端：Linux 上是 EIO，不是 EOF
                break
            if not chunk:
                break
            out += chunk
    finally:
        os.close(master)
        proc.wait(timeout=30)
    return out.decode("utf-8", "replace")


@pytest.mark.skipif(_EXE is None,
                    reason="没有构建好的 fy：cargo build --release --features cli --bin fy"
                           "（这道门问的是那个二进制在终端上印不印，没有它就没什么可问的）")
@pytest.mark.parametrize("lang", LANGS)
def test_the_terminal_sees_the_banner(lang: str):
    """★★2026-09-08 用户裁定：*cli 终端需显示 banner*。端到端地问那个二进制。

    ★源码里的断言（`banner::decide`、本文件上面几条）问的是**规则**；这一条问的是
    **那份制品**——规则对而接线错（比如 `emit()` 没被 `main` 调到、或被挪到某个
    分支里）是一个源码级闸子看不见的失败，而看得见它的人是拿到二进制的那个。
    """
    out = _run_on_a_terminal(["list", "devices"], {"FY_LANG": lang})
    for n in SPEC["notices"]:
        if "internal" in n["flavours"]:
            assert n[lang] in out, f"终端上没有这一句：{n[lang]}\n收到的是：{out[:400]}"
    assert SPEC["wordmark"][0].strip() in out, "终端上没有招牌"


@pytest.mark.skipif(_EXE is None, reason="没有构建好的 fy")
def test_a_pipe_sees_nothing_from_that_same_binary():
    """★反面同样端到端：同一个二进制，stderr 是管道时一个字也不印。"""
    import subprocess

    r = subprocess.run([str(_EXE), "list", "devices"], capture_output=True, timeout=30)
    assert r.stderr == b"", f"管道上印了东西：{r.stderr[:200]!r}"


def test_an_undetermined_flavour_says_the_restriction_rather_than_hiding_it():
    """★读不出版别时兜底成 ``internal``：多说一句 vs 悄悄看起来可以外发。"""
    assert SPEC["default_flavour"] == "internal"
    assert notice.flavour() in ("internal", "public")
