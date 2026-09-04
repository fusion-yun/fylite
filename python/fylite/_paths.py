"""Bundled-asset locations and machine constants for fylite."""
from __future__ import annotations

import os
from pathlib import Path

PKG = Path(__file__).resolve().parent
#: ``_lib/`` holds the callable solver (shared library, ctypes); ``_bin/``
#: optional helper executables.  Neither carries machine data.
LIB_DIR = PKG / "_lib"
BIN_DIR = PKG / "_bin"
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
#: ★★2026-09-02 改名：`libfylite_kernel.so` -> `libfylite_kernel.so`。本目录从此有**两份**
#: `.so`，来路不同：内核（物理，私有仓 fylite_kernel 构建）与数据层（取数与格式，
#: 本仓 `rust/fylite_runtime/` 构建）。名字自带区分，好过靠读者记住哪一份是哪一层。
KERNEL_LIB = LIB_DIR / "libfylite_kernel.so"

#: 数据层：mdsip 编解码，后续收编 g-file / est2。★与内核**不同的符号前缀**
#: （`fylite_runtime_*` vs `fylite_rs_*`），所以同一个进程 load 两份不会撞名。
DATA_LIB = LIB_DIR / "libfylite_runtime.so"

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
