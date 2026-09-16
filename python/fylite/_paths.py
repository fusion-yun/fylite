"""Bundled-asset locations and machine constants for fylite."""
from __future__ import annotations

import os
from pathlib import Path

PKG = Path(__file__).resolve().parent
#: ``_lib/`` holds the callable solver (shared library, ctypes); it carries no
#: machine data.  ★★2026-09-04 ``BIN_DIR`` (``_bin/``) went with the user's
#: ruling that **this package ships no executable**: the one there is is built
#: by ``rust/build.sh --exe`` as ``fy`` and found on ``$PATH``
#: (``engine.cli._find_exe``).  Nothing here read ``BIN_DIR`` anyway — the
#: lookup always spelled the directory itself.
LIB_DIR = PKG / "_lib"


def _lib(logical: str, *legacy: str) -> Path:
    """The shared library ``logical`` names — versioned or not.

    ★★★2026-09-16 用户裁定「在 fylite 仓与 fylite_runtime 一起打包进……动态链接库
    libfylite.so」：本目录从此**只有一个 `.so`**，内核（物理）与中间层（格式 · 装配）
    在同一个文件里。``legacy`` 是**上一代的三个名字**（``libfylite_kernel.so`` /
    ``_ext.so`` / ``libfylite_runtime.so``）——一个按旧规矩装好的检出或轮子仍然能跑，
    而不是在 import 时以「找不到内核」失败。新名字优先；两代都在就用新的。

    ★★2026-09-05: the build installs shared objects the way Linux does
    (``tools/soname.sh``) — ``libfylite_kernel.so.0.0.1`` is the real file
    and ``libfylite_kernel.so.0`` / ``libfylite_kernel.so`` are symlinks to
    it.  In a source checkout the plain name resolves and nothing here has
    to think; ★**a wheel has no symlinks**, so what arrives on an installed
    package is the versioned file alone (see ``pyproject.toml``'s
    ``package-data``, which packages exactly that one).  Asking for the
    plain name there would find nothing, and the failure would read
    「找不到内核」 on a package that is carrying it.

    So: the plain name if it is there, else the highest version present.
    ★Highest rather than 「the only one」: the installer directory is a
    staging target that holds one version at a time, but nothing in a wheel
    or a container image enforces that, and picking arbitrarily out of two
    would make「哪一份在跑」a question again.
    """
    plain = LIB_DIR / logical
    if plain.exists():
        return plain

    def key(p: Path) -> tuple:
        #: sort by numeric components, so ``.so.0.0.10`` beats ``.so.0.0.9``
        return tuple(int(x) if x.isdigit() else -1
                     for x in p.name[len(logical) + 1:].split("."))

    found = sorted(LIB_DIR.glob(logical + ".*"), key=key)
    if found:
        return found[-1]
    for old in legacy:
        alt = _lib(old)
        if alt.exists():
            return alt
    #: ★缺席时仍然返回**那个不带版本的路径**，不是 None：调用方的报错文案说的是
    #: 「找不到 libfylite.so」，而那正是读者要去构建的那个名字。
    return plain
#: ★No bundled device deck: this distribution ships none (see
#: :mod:`fylite.device`).  ``DATA_DIR`` is resolved from
#: ``$FYLITE_DEVICE_DIR`` on first ACCESS, through this module's
#: ``__getattr__``, so importing anything still works with nothing configured
#: and the failure, when it comes, names the missing input.
#:
#: ★★There was a ``_DEVICE_FILES`` table of deck filenames here —
#: ``GEOM_FILE`` / ``DPROBE`` / ``FITWEIGHT`` / ``LIMITER_JSON`` /
#: ``KFILE_DEFAULTS``.  Nothing ever read one of those names: every actual
#: reader called ``device.deck_path("<literal>")``, so the table was a second
#: spelling of five filenames with no consumers, and ``FITWEIGHT`` named a
#: file this package never opened at all.  What each of them WAS is now
#: either the fyo device document (the box and the coil turns) or a reader in
#: :mod:`fylite.io` (``east_geom.txt`` for the audit, the k-file namelist
#: defaults, the m-file limiter).  A registry of filenames is not a layer.

#: The kernel: a C-ABI cdylib built by ``rust/build.sh``, re-entrant with no
#: global state, called in-process.  ★★It was the ONLY library this package
#: loaded until 2026-09-02, when the data plane became a library of its own
#: (``DATA_LIB`` below): physics on one side, taking numbers off a machine on
#: the other.  The four that used to stand beside it — ``libefit.so``,
#: ``libneo.so``, ``libgeo.so``, ``libtglf.so`` — left with LICENSE 3.1/3.2
#: along with every binding to them, and their constants have gone with the
#: loader that turned a missing one into a diagnostic.  What survives of
#: those libraries is a set of RECORDINGS (``tests/data/FYDOC-CASE-03-frozen-libs``,
#: replayed from ``tests/oracles/``), and a recording needs no path.
#: ★★★2026-09-16 用户裁定：**一个 `.so`**。私有仓 fylite_kernel 从此只出静态归档
#: （`libfylite_kernel.a`），本仓 `rust/build.sh` 把它与中间层 `fylite_runtime` 链成
#: 同一个 `libfylite.so.<版本>`（+ `.so.<主版本>` + `.so` 两级符号链接，
#: `tools/soname.sh`）。于是下面三个常量**指的是同一个文件**——保留三个名字是因为
#: 三处调用方问的是三件不同的事（物理核 · 扩展面 · 中间层），而「它们碰巧同住一个
#: 库」是装配的事实，不该逼每个调用方都知道。
#:
#: ★★沿革：2026-09-02 数据层从内核里分出来成第二份 `.so`；2026-09-04 内核又分核心与
#: 扩展两份；今天三份合一。分的理由（谁属于哪一层）仍然成立，它们仍是三个 crate、
#: 三个符号前缀（`fylite_rs_*` · `fylite_ext_*` · `fylite_runtime_*`，同进程不撞名）；
#: 变的只是**装出去的文件数**。每个常量的第二个参数是上一代的名字，见 `_lib`。
KERNEL_LIB = _lib("libfylite.so", "libfylite_kernel.so")
#: ★扩展面（TGLF · DKE）。从前它可以**缺席**（纯 CLI 的发行不带那一份 `.so`），
#: 缺席时那 15 个入口按名拒绝而不是 AttributeError。今天它与核心在同一个文件里，
#: 于是缺席只剩一种形式：整个 `libfylite.so` 不在。那条按名拒绝的路仍留着——
#: 旧检出（真有两份 `.so`）走的正是它。
KERNEL_EXT_LIB = _lib("libfylite.so", "libfylite_kernel_ext.so")

#: 中间层：mdsip 编解码 · g-file · 文档树 · 计划→内核→记录。
DATA_LIB = _lib("libfylite.so", "libfylite_runtime.so")

#: ★★2026-09-01 移除：`$KEFIT_REFERENCE_BUNDLE` 与 `reference_bundle()`。
#: 那是一个指向 ASIPP **不可再分发**参考包（`kefit_reference_bundle`，致谢里的
#: 定性是「内部、未授权、不再分发」）的配置钩子。包内**零调用者**——唯一行使它的
#: 是一条断言「必须显式给、绝不猜」的测试，也就是说它守着的是一条没有人走的路。
#: 本仓公开之后，留着它等于对外声称这里提供通往那个包的入口。要用请自行取得，
#: 并在自己的代码里解析路径。

# Machine facts and compile-time dimensions moved to the device config
# (`_data/east_device.yaml`, surfaced by `device`): this module is about
# **paths**, and the code layer carries no machine constants.

#: ★no `cache_dir()` here any more: it named the directory the Green-table
#: GENERATOR wrote into, and both the generator and the cache-management
#: subcommand are gone.  The deck is read where it lies.


def __getattr__(name: str):
    """``DATA_DIR`` — the configured device directory, resolved when asked for.

    ★An unknown name is still an ``AttributeError``: this resolves one name,
    not a catch-all that turns every typo into a machine-data error.
    """
    if name == "DATA_DIR":
        from . import device
        return device.data_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
