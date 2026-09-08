"""启动 banner 与它上面的**提示词**——三个界面同一份文本。

★★2026-09-08 用户裁定：*python/cli 层添加启动 banner，参考 fytok 中 ASCII 排版
的 banner，包含版 header 提示词；提示词默认包含版本提醒；web ui / cli / python
三个界面统一提示词*。

于是这三样东西是**一份**：浏览器头条上的警示带、`fy` 启动时印的那几行、以及这个
包被导入时印的那几行。它们的真源是 :data:`SOURCE`（``python/fylite/_notice.json``），
三个宿主各自渲染：

===============  ==========================================================
浏览器            ``app/assets/lang-{zh,en}.js`` 的两个词条 —— 由
                 ``app/tests/validate-site.mjs`` 逐字押在本文件上
``fy``（Rust）    ``rust/fylite_runtime/src/banner.rs``，编译期 ``include_str!``
                 同一个 JSON
本模块            导入 ``fylite`` 时印一次
===============  ==========================================================

★为什么要押在一起。一句在一个界面上说、在另一个界面上不说的提示，比不说更糟：
**见过其中一面的人会以为自己已经被告知**。所以这里没有第二份文本，只有第二种排版。

★★**版别（flavour）决定说几句**。`alpha 版，用于概念验证` 每一版都说；
`仅限内部测试，请勿公开传播！` 只有内部版说。判据在 JSON 里逐条写着
（``flavours``），三个宿主各读同一条。版别本身在**编译期**定死
（``FYL-DESIGN-19`` A-14/A-18）：本层读 :mod:`fylite._flavour`——那是
``rust/build.sh`` 与 ``.so`` 同一次构建写下的生成物——读不到就按 ``internal``
作答，因为对一条**限制**而言，那才是安全的方向（多说一句 vs 悄悄看起来可以外发）。

★印到 **stderr**，不是 stdout：这个包的调用方会把 stdout 交给管道，而一个把
自己的招牌混进数据里的库是一个不能被脚本用的库。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

__all__ = ["SOURCE", "QUIET_ENV", "LANG_ENV", "spec", "flavour", "language",
           "notices", "banner", "print_banner", "decide",
           "NOTHING", "NOTICES_ONLY", "FULL"]

#: 真源。★与 ``_cli.json`` 同一姿态：一个被多个宿主各自读一遍的**数据**文件，
#: 而不是一段被抄了三遍的文本。
SOURCE = Path(__file__).with_name("_notice.json")

#: ★★这两个名字**在两处写着**，而且是有意的。真源是 `_notice.json`（`quiet_env` /
#: `lang_env`——`fy` 那一面从同一个文件读它们），但本层的环境面由一道**两向闸子**
#: 看着（`test_environment_table.py`：读了没声明、声明了没人读，两边都红），而那
#: 道闸子是 AST 扫描，只认得出字面量与模块常量。把名字藏进一个 `.get()` 调用里，
#: 闸子就两向都看不见这两个变量——一个「过得去而什么也没查」的闸子比没有闸子坏。
#: 两处相等由 `test_notice_is_one_text.py` 断言。
QUIET_ENV = "FY_NO_BANNER"
LANG_ENV = "FY_LANG"

_SPEC: dict | None = None
_EMITTED = False


def spec() -> dict:
    """The parsed ``_notice.json``（读一次，之后走缓存）。"""
    global _SPEC
    if _SPEC is None:
        _SPEC = json.loads(SOURCE.read_text(encoding="utf-8"))
    return _SPEC


def flavour() -> str:
    """这一份制品是哪一版：``"internal"`` / ``"public"``。

    读 :mod:`fylite._flavour`（``rust/build.sh`` 的生成物，与 ``.so`` 同一次
    构建）。读不到、或它说 ``none``（那一次构建没带装置信息），按 JSON 里的
    ``default_flavour`` 作答——**不猜 public**：见模块抬头。
    """
    default = spec().get("default_flavour", "internal")
    try:
        from ._flavour import FLAVOUR  # type: ignore[attr-defined]
    except Exception:
        return default
    return FLAVOUR if FLAVOUR in ("public", "internal") else default


def language(lang: str | None = None) -> str:
    """``"zh"`` 或 ``"en"``：显式给的 > ``$FY_LANG`` > 区域设置 > ``en``。"""
    for cand in (lang, os.environ.get(LANG_ENV)):
        if cand in ("zh", "en"):
            return cand
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(var, "").lower().startswith("zh"):
            return "zh"
    return "en"


def notices(lang: str | None = None, fl: str | None = None) -> list[str]:
    """这一版在这个语言下要说的几句，**按 JSON 里的次序**。

    次序是内容的一部分：先说这份东西成熟到什么程度，再说它能给谁看。
    """
    lang = language(lang)
    fl = fl or flavour()
    return [n[lang] for n in spec()["notices"] if fl in n["flavours"]]


def banner(lang: str | None = None, fl: str | None = None, *,
           version_line: str | None = None, quiet: bool | None = None) -> str:
    """整块 banner（不带末尾换行）。

    :param version_line: 这个宿主自己那一行；``None`` 时由本层拼（包版本 · 内核
        接口号 · 版别）。★三个宿主的**提示词**一字不差，**版本行**各说各的：
        它们是三个不同的制品，装作同一个才是说谎。
    :param quiet: ``True`` 只留提示词（招牌、许可、版本行都不印）。缺省看
        ``$FY_NO_BANNER``。★安静关得掉招牌，关不掉提示词。
    """
    s = spec()
    lang = language(lang)
    fl = fl or flavour()
    if quiet is None:
        quiet = _quiet_asked()
    lines: list[str] = []
    if not quiet:
        lines += list(s["wordmark"])
        lines.append(f"{s['spdx']} · {s['copyright']}")
        lines.append(version_line if version_line is not None else _version_line(lang, fl))
    lines += notices(lang, fl)
    rule = s["rule"] * s["rule_width"]
    return "\n".join([rule, *lines, rule])


def _version_line(lang: str, fl: str) -> str:
    #: ★读不出来就**不印那一格**，不印一个 `unknown`：一个假装知道的版本号比没有
    #: 版本号更难排障。源码检出里没装成包时就是这种情形。
    bits = []
    #: ★发行版本号**不在这里再求一次**：包自己已经有一处求法（`__init__` 的
    #: `_release_version()`，装上了读元数据、在树里读 `VERSION`），再写一遍就是
    #: 两处可以各自过期的实现。
    rel = getattr(sys.modules.get(__package__ or "fylite"), "__version__", None)
    if rel and rel != "unknown":
        bits.append(f"python {rel}")
    try:
        from ._abi import ABI_VERSION
        bits.append(("内核接口 " if lang == "zh" else "kernel interface ") + str(ABI_VERSION))
    except Exception:
        pass
    bits.append(f"{fl} 版" if lang == "zh" else f"{fl} build")
    return " · ".join(bits)


#: 印多少：一个字也不印 / 只印提示词 / 全印。★与 Rust 侧的 `banner::Show` 同一组。
NOTHING, NOTICES_ONLY, FULL = "nothing", "notices", "full"


def decide(interactive: bool, quiet: bool) -> str:
    """这一次要印多少——**有人看着**才印。

    ★★2026-09-08 用户裁定：*fy cli 交互时显示 banner*。两个会打印的宿主同一条
    规则：``stderr`` 是终端就印，是管道或日志就一个字也不印。banner 的读者是
    **人**，而 ``python x.py > out`` 那条流上没有人，只有噪声。
    ★代价说在明处：重定向进日志的内部版**不会**在日志里留下「仅限内部测试」那一
    句；提示词仍在页面头条、README 与制品的 NOTICE 上。
    ★``$FY_NO_BANNER`` 只在有人看着时起作用，且只收掉装饰：提示词是使用条件。
    """
    if not interactive:
        return NOTHING
    return NOTICES_ONLY if quiet else FULL


def _interactive(stream) -> bool:
    #: ★问不出来就当**没有人看着**：`isatty` 会在被换掉的流上抛（pytest 的捕获流、
    #: 某些嵌入宿主）。默认不印比默认印安全——印错地方的招牌会混进别人的数据。
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def print_banner(stream=None, *, force: bool = False, **kw) -> None:
    """印到 ``stderr``（或给定的流）。

    :param force: 不问交互与否，照印。★显式调用本函数**就是**那个「有人在看」的
        意思：调用方要的是这几行字，不是要它替自己判断。缺省仍按 :func:`decide`。
    """
    out = stream or sys.stderr
    show = FULL if force else decide(_interactive(out), _quiet_asked())
    if show == NOTHING:
        return
    kw.setdefault("quiet", show == NOTICES_ONLY)
    print(banner(**kw), file=out, flush=True)


def _quiet_asked() -> bool:
    return os.environ.get(QUIET_ENV, "") not in ("", "0")


def _emit_once() -> None:
    """导入 ``fylite`` 时调用一次。

    ★**一个进程一次**：`import fylite.scenario.model` 会把包的 ``__init__``
    跑一遍，而一个每次导入都印一遍招牌的库，在第一个 `reload` 之后就变成噪音。
    ★出了任何岔子都不许把导入弄砸：一句招牌值不了一个 ImportError。
    """
    global _EMITTED
    if _EMITTED:
        return
    _EMITTED = True
    try:
        print_banner()
    except Exception:
        pass
