"""Fixtures and skip policy shared by the Python-tier tests.

★★2026-09-02：本文件与 ``pytest.ini`` 从**仓根**下移到 ``python/``.  它们当初
在仓根，是因为有两棵测试树（2026-08-22）：``python/tests`` —— Python 档：装配、
IO、协议/CLI 面、注册表、ABI 编组；以及仓根 ``tests`` —— 物理数值档：oracle
对拍与数值断言。下面那套机器 deck、离线算例、以及「本发行物不带机器数据，所以
SKIP 并点名缺的是哪个文件」的政策**两棵树都要**，而 conftest 只对自己目录以下
生效 ⇒ 唯一能同时服务两棵树的位置就是它们的共同祖先，仓根。

★那个理由已经消失：物理数值档连同它的 ``oracles/`` 已收敛进 fylite_kernel，
本仓只剩 ``python/tests`` 一档，共同祖先就是 ``python/``。导入路径来自
``pytest.ini`` 的 ``pythonpath``，现在是 ``.``（相对 rootdir ``python/``），
不再是 ``python``；调用口径见那份文件的抬头。
"""
import os
from pathlib import Path

import pytest

# ★★2026-09-01：参考样本包（`$KEFIT_REFERENCE_BUNDLE`）连同
# `_paths.reference_bundle()` 一起移除——它指向一份 ASIPP **不可再分发**的内部包，
# 而包内没有任何调用者。这里的 SAMPLES / MFILE / GREF 是它的三个派生路径，
# 随之退休；读它们的测试已经不在本仓。留成 None 而不是删名字：万一还有读者，
# 它会在使用处得到一个明确的 None，而不是 NameError。
_BUNDLE = None
SAMPLES = MFILE = GREF = None
_HINT = ("the ASIPP reference sample bundle is not part of this distribution")


@pytest.fixture(scope="session", autouse=True)
def _isolated_cache(tmp_path_factory):
    """Point the Green's-table cache at a session-temporary directory."""
    d = tmp_path_factory.mktemp("greens_cache")
    old = os.environ.get("KEFIT_CACHE_DIR")
    os.environ["KEFIT_CACHE_DIR"] = str(d)
    yield d
    if old is None:
        os.environ.pop("KEFIT_CACHE_DIR", None)
    else:
        os.environ["KEFIT_CACHE_DIR"] = old


@pytest.fixture(scope="session", autouse=True)
def _isolated_run_root(tmp_path_factory):
    """Point the RUN root at a session-temporary directory.

    ★Same reason as the cache above, one consequence sharper: a test that
    delivers a run would otherwise write into the developer's own
    ``~/.cache/fylite/runs`` — and handles resolve by SEARCHING that root, so
    a stray run from a test would be visible to (and findable by) real work.
    """
    d = tmp_path_factory.mktemp("run_root")
    old = os.environ.get("FYLITE_RUN_DIR")
    os.environ["FYLITE_RUN_DIR"] = str(d)
    yield d
    if old is None:
        os.environ.pop("FYLITE_RUN_DIR", None)
    else:
        os.environ["FYLITE_RUN_DIR"] = old


@pytest.fixture(scope="session")
def mfile():
    if MFILE is None or not MFILE.exists():
        pytest.skip(f"reference m-file missing: {MFILE or _HINT}")
    return MFILE


@pytest.fixture(scope="session")
def gref():
    if GREF is None or not GREF.exists():
        pytest.skip(f"reference g-file missing: {GREF or _HINT}")
    return GREF


def has_mds_server() -> bool:
    """★2026-09-04：曾叫 `has_local_mds`，看的是 `KEFIT_MDS_ROOT` 下有没有本地树、
    装没装站点的 `MDSplus` 包。两样都退役了：在线路径走中间层的 mdsip 客户端，
    本包不 import `MDSplus`，本地树模式随之撤销。今天这道门只问一件事——有没有
    人指了一台 mdsip 服务器。"""
    return bool(os.environ.get("KEFIT_MDS_SERVER"))



# --------------------------------------------------------------------------- #
# machine data
# --------------------------------------------------------------------------- #
# ★This distribution ships no device description (see `fylite.device`), so
# every test that needs a machine says so and skips when none is configured.
#
# ★★2026-09-13 (user ruling, `machine_desc` retired): TWO inputs, found two ways.
#   * `$FYLITE_DEVICE_DIR` — the machine's FIT INPUTS (efund / Green-table decks,
#     k-file defaults; for EAST the kernel checkout's `tests/data/east/`).
#   * the device CARD — generated from fydoc's A-Box into the facts corpus
#     (`dist/facts/device/<id>/<id>_device.yaml`) and resolved by `fylite.device`
#     through the facts search path when the directory carries none.
# Shot data (the #137985 reference discharge, the FYDOC-CASE-22 answers) is the
# PRIVATE kernel checkout's, read where it lies through `$FYLITE_KERNEL`
# (:func:`kernel_fixture`) — never a copy in this public repository.
from fylite import device as _device  # noqa: E402
from fylite.engine.cases import CorpusMissing as _CorpusMissing  # noqa: E402

#: ★★2026-09-01：`machine_desc/` 已不在本仓（装置描述的所有权不在本项目）。
#: 这里曾在仓内自动认领一份 deck；现在**只认 $FYLITE_DEVICE_DIR**，没有就按下面
#: 的 `requires_machine` 点名跳过。★不再回退到猜路径：猜错的那一份和没有那一份，
#: 在报错里长得一模一样，而前者更难查。

#: ★★2026-09-13 (user ruling: est2 removed at every layer): the EAST fit inputs
#: (`$FYLITE_DEVICE_DIR` = the kernel checkout's `tests/data/east/`) and the #137985
#: shot data (FYDOC-CASE-22, the reference discharge) are est2 records and move to the
#: kernel's `archive/` (mirroring the path: `archive/tests/data/...`).  A public reader
#: SKIPS naming the file and :data:`EST2_REMOVED` ONLY when the file is gone from its
#: old path AND its archived copy exists — a broken checkout (absent, nothing archived)
#: keeps its old outcome and never reads as "archived".  Library code keeps raising
#: `MachineDataMissing`; only tests and fixtures skip.
EST2_REMOVED = ("est2 removed (2026-09-13): FYDOC-CASE-22 and the EAST fit inputs "
                "archived; an efit_east #137985 case will replace them")
#: …and a record that is STILL at its old path but is est2-ordered: no device of any
#: measurement chain pairs with it any more (not "archived" — it is not, yet).
EST2_UNPAIRED = ("est2 removed (2026-09-13): the est2 device array is gone, so this est2 "
                 "record pairs with no measurement chain; an efit_east #137985 case will "
                 "replace it")


def _archived_copy(p) -> Path | None:
    """The mirrored archive copy of a kernel ``tests/data/...`` path that is ABSENT, if one
    exists (``<checkout>/archive/tests/data/...``); ``None`` otherwise."""
    p = Path(str(p)).expanduser()
    if p.exists():
        return None
    s = p.as_posix()
    i = s.find("/tests/data/")
    if i < 0:
        return None
    a = Path(s[:i]) / "archive" / s[i + 1:]
    return a if a.exists() else None


def _archived_reason_in(msg: str) -> bool:
    """Some absolute path named in ``msg`` is absent and archived."""
    import re
    return any(_archived_copy(m.rstrip(".,;:)'\"`")) is not None
               for m in re.findall(r"(/[^\s'\"`]+)", msg))


#: the EAST fit inputs, relative to the kernel checkout (what `$FYLITE_DEVICE_DIR` names)
KERNEL_DEVICE_DIR = "tests/data/east"


def _device_dir_absent() -> str | None:
    """The EAST fit-input directory is gone: the reason, naming it, with
    :data:`EST2_REMOVED` when its archived copy exists — ``$FYLITE_DEVICE_DIR`` set to a
    path that is no directory, or (unset) ``$FYLITE_KERNEL/tests/data/east`` archived."""
    raw = os.environ.get(_device.DEVICE_ENV)
    if raw:
        if Path(raw).expanduser().is_dir():
            return None
        tail = f" — {EST2_REMOVED}" if _archived_copy(raw) is not None else ""
        return f"${_device.DEVICE_ENV}={raw} is not a directory{tail}"
    kernel = os.environ.get("FYLITE_KERNEL")
    if kernel:
        p = Path(kernel).expanduser() / KERNEL_DEVICE_DIR
        if _archived_copy(p) is not None:
            return (f"${_device.DEVICE_ENV} is not set and {p} is absent "
                    f"(${'FYLITE_KERNEL'}={kernel}) — {EST2_REMOVED}")
    return None


def _machine_skip_reason(msg: str | None = None) -> str:
    """A machine-data skip reason: the input named, plus :data:`EST2_REMOVED` when a
    missing input it names (or the device directory) was archived by the est2 removal."""
    absent = _device_dir_absent()
    base = msg or (absent or f"no machine description: set ${_device.DEVICE_ENV} to a "
                   "directory holding the device deck")
    if EST2_REMOVED in base:
        return base
    archived = _archived_reason_in(base) or (absent is not None and EST2_REMOVED in absent)
    return f"{base} — {EST2_REMOVED}" if archived else base


requires_machine = pytest.mark.skipif(
    not _device.configured(),
    reason=_machine_skip_reason())


@pytest.fixture(scope="session")
def machine_dir():
    """The configured device directory, or skip."""
    if not _device.configured():
        pytest.skip(_device_dir_absent() or f"set ${_device.DEVICE_ENV} to run this")
    return _device.data_dir()


def machine_tables():
    """The device deck directory, or SKIP.

    ★Tests reach for the deck through this ONE call rather than composing a
    path under `python/fylite/_data`, which is where it used to live.  A
    literal path would come back as `FileNotFoundError` — a failure that
    reads like a broken test rather than like a distribution that ships no
    machine data on purpose.

    ★``allow_module_level`` is the point: several modules need the deck to
    build their module-level constants, so the skip has to be able to happen
    at import.  Marking those modules by hand instead was tried and goes
    stale the moment a test starts reaching one module deeper.
    """
    if not _device.configured():
        pytest.skip(_machine_skip_reason(), allow_module_level=True)
    return _device.data_dir()


def machine_device_file(name: str = "east_device.yaml"):
    """One file from the device deck, or SKIP (see :func:`machine_tables`).

    A card name (``<id>_device.yaml``) the deck directory does not carry
    resolves through the facts search path (``fylite.device.deck_path``)."""
    machine_tables()
    try:
        return _device.deck_path(name)
    except _device.MachineDataMissing as exc:
        pytest.skip(_machine_skip_reason(str(exc)), allow_module_level=True)


#: ★The reference discharge is a SECOND missing input, and a different one:
#: `fylite.device` covers the device deck, but the g/a files of a real shot
#: are an EFIT reconstruction that this distribution does not carry either.
#: A test that reaches for them raises `FileNotFoundError` from deep inside
#: pathlib, which reads like a broken test rather than like an input nobody
#: supplied — so it is turned into the same kind of skip, and ONLY for these
#: files: any other missing path still fails.
_REF_NAMES = ("g137985", "a137985", "summary_137985")


def _is_reference_case(exc: OSError) -> bool:
    name = Path(getattr(exc, "filename", "") or "").name
    return any(name.startswith(p) for p in _REF_NAMES)


def _is_machine_data(exc: OSError) -> bool:
    """Whether the missing file lives under the machine-data directory.

    ★★The policy is "this distribution ships no machine data, so a test that
    reaches for it SKIPS with the missing file named", and it was carried by
    one exception type raised in one place (``device.MachineDataMissing``).
    That covers everything reached THROUGH ``fylite.device`` and nothing
    else: ``test_circuits`` hands a deck path to
    ``device.vessel_response_tables`` and the plain ``open`` inside it
    raised ``FileNotFoundError`` for ``rv6565.ddd`` — a bare failure, for
    exactly the reason its own comment said it would skip for.  It looked
    covered because the module carried a mark that switched it off outright.

    So the rule is the DIRECTORY, which is what "machine data" means here.
    """
    root = _device.data_dir() if _device.configured() else None
    if root is None:
        return False
    try:
        return Path(root).resolve() in Path(
            getattr(exc, "filename", "") or "").resolve().parents
    except (OSError, ValueError):        # pragma: no cover
        return False


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    """Same policy during FIXTURE setup.

    ★A fixture that reaches for the deck raised during setup, which
    `pytest_runtest_call` never sees — so one module reported an ERROR while
    its siblings skipped, for the same missing input.  Covering both phases
    is what makes "no machine data" a single, uniform outcome.
    """
    try:
        return (yield)
    except _device.MachineDataMissing as exc:
        pytest.skip(_machine_skip_reason(str(exc)))
    except _CorpusMissing as exc:
        #: ★★语料搬过三次：出本仓、回仓根 `cases/`、2026-09-04 收进 `docs/examples/`
        #: （一个例子一个目录，散文与 scenario 同住）。这条
        #: 救援路径**留着**：语料是仓数据、不进轮，装了轮而没有检出的调用者仍会
        #: 撞上它。而
        #: `engine.cases` 找不到语料时抛的是 **`SystemExit`**——那是它 CLI 面的
        #: 错误路径（「run from a checkout or pass --dir」），对库调用者是个
        #: 意外形状：pytest 把它当致命错误，五个模块因此报 ERROR 而不是 skip。
        #: ★这里只认**那一条**消息，不是见 SystemExit 就救：一个真的调了
        #: `sys.exit()` 的缺陷仍然照红。判据与上面「缺装置数据」的那条同形——
        #: 缺输入是跳过并点名，缺实现才是失败。
        pytest.skip("找不到算例语料（`docs/examples/`）；"
                    "要跑这条，把语料检出后用 --dir 指过去")
    except FileNotFoundError as exc:
        if _is_machine_data(exc):
            pytest.skip(_machine_skip_reason(
                f"needs machine data ({Path(exc.filename).name}), "
                "which this distribution does not carry"))
        if not _is_reference_case(exc):
            raise
        #: ★the old wording said「drop the g/a files into examples/scripts/」—
        #: following it turned test_examples_are_fyo red, because shot data
        #: under examples/ is exactly what that gate walks the working tree
        #: to refuse.  The sanctioned home is the machine-data side.
        pytest.skip(_machine_skip_reason(
            f"needs the EAST reference discharge ({exc.filename}), "
            "which this distribution does not carry; it is the private "
            "kernel checkout's FYDOC-CASE-22 mirror, read through "
            "$FYLITE_KERNEL (never copied into this repository)"))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """A test that asks for machine data this distribution does not ship is
    SKIPPED, with the reason naming the missing input.

    ★Not a blanket rescue: only `MachineDataMissing` is caught, and it is
    raised in exactly one place (`fylite.device`).  Any other error still
    fails.  The alternative — marking each such test by hand — was tried and
    goes stale the moment a test starts reaching one module deeper.
    """
    try:
        return (yield)
    except _device.MachineDataMissing as exc:
        pytest.skip(_machine_skip_reason(str(exc)))
    except _CorpusMissing as exc:
        #: 与 setup 钩子同一条政策：缺语料是跳过并点名，不是失败。两个阶段都覆盖，
        #: 是为了让「语料不在」只有一种结局——此前它在一处是 ERROR、另一处是 skip。
        pytest.skip("找不到算例语料（`docs/examples/`）；"
                    "把语料检出后用 --dir 指过去即可跑这条")
    except FileNotFoundError as exc:
        if _is_machine_data(exc):
            pytest.skip(_machine_skip_reason(
                f"needs machine data ({Path(exc.filename).name}), "
                "which this distribution does not carry"))
        if not _is_reference_case(exc):
            raise
        #: ★the old wording said「drop the g/a files into examples/scripts/」—
        #: following it turned test_examples_are_fyo red, because shot data
        #: under examples/ is exactly what that gate walks the working tree
        #: to refuse.  The sanctioned home is the machine-data side.
        pytest.skip(_machine_skip_reason(
            f"needs the EAST reference discharge ({exc.filename}), "
            "which this distribution does not carry; it is the private "
            "kernel checkout's FYDOC-CASE-22 mirror, read through "
            "$FYLITE_KERNEL (never copied into this repository)"))


#: ★★★``requires_reference_case`` stood here — a ``skipif`` on
#: ``examples/scripts/g137985.04000``, carried by 27 test functions and 4
#: module-level ``pytestmark`` lists.  It is gone, and what it was hiding is
#: worth writing down.
#:
#: **Its predicate named a file no test in the tree uses.**  The reference
#: discharge that IS in the repository is ``g137985_loop.04000``, under
#: ``examples/east137985-recon-figure/data/`` and
#: ``examples/recon-to-transport/data/`` — a different name in a different
#: directory.  So the mark was permanently true, which is to say those 27
#: tests were deleted.
#:
#: **And they do not need a discharge.**  Every one of them reads the
#: bundled SYNTHETIC equilibrium (``data/synthetic/g_synthetic.geqdsk``) or
#: the device document.  Removing the mark: 17 pass — they had simply been
#: switched off — and 10 fail, because they were calibrated to the real
#: discharge before their module was repointed at the synthetic one and the
#: pinned numbers were never redone.  Those 10 are ``xfail(strict=True)``
#: now, each stating that; a strict xfail cannot be permanently true in
#: silence, because the day one starts passing the run goes red.
#:
#: **The mechanism that works is below and was already there.**
#: :func:`pytest_runtest_setup` / :func:`pytest_runtest_call` turn a genuine
#: reach for missing machine data into a skip whose reason names the file
#: that is actually absent.  The docstring on the second one says why a
#: by-hand mark was the wrong shape — "it goes stale the moment a test
#: starts reaching one module deeper" — which is exactly what happened,
#: measured.


#: The bundled offline case (#137985 @ 4.0 s), as fyo/JSON-LD documents.
#:
#: ★★These names used to be ``examples/scripts/g137985_loop.04000`` and
#: ``a137985_loop.04000`` — a path that did not exist, so every test that used
#: them skipped silently.  They became documents (``tools/case-to-fyo.py``)
#: beside the deck; ★★2026-09-13 (user ruling, `machine_desc` retired) the
#: answers moved to fydoc's case book FYDOC-CASE-22, mirrored in the PRIVATE
#: kernel checkout — so they are read there, through ``$FYLITE_KERNEL``, and a
#: checkout without it SKIPS with the variable and the file named.
CASE_SHOT, CASE_ITIME_MS = 137985, 4000

#: the kernel CHECKOUT (not the library) — declared in ``_environment.json``
KERNEL_ENV = "FYLITE_KERNEL"
#: the FYDOC-CASE-22 mirror, relative to the kernel checkout
CASE_MIRROR = "tests/data/FYDOC-CASE-22-east-137985-efit/corpus"
#: the #137985 reference discharge / slice series, relative to the kernel checkout
REFERENCE_DISCHARGE = "tests/data/east/reference_discharge_137985.fyo.jsonld"


def kernel_fixture(rel: str) -> Path:
    """A file in the PRIVATE kernel checkout, or SKIP naming what is missing.

    ★One resolver for every shot-data consumer: the rule (which variable, which
    relative path) is what drifts, and a test that spells it itself is the test
    that goes on reading a retired path.  ``allow_module_level`` so a module
    that builds constants from it skips at import instead of erroring.
    """
    root = os.environ.get(KERNEL_ENV)
    if not root:
        pytest.skip(f"needs the private kernel checkout: ${KERNEL_ENV} is not set "
                    f"({rel} lives only there)", allow_module_level=True)
    p = Path(root).expanduser() / rel
    if not p.is_file():
        tail = f" — {EST2_REMOVED}" if _archived_copy(p) is not None else ""
        pytest.skip(f"needs {rel} from the private kernel checkout: {p} is absent "
                    f"(${KERNEL_ENV}={root}){tail}", allow_module_level=True)
    return p


def reference_discharge() -> dict:
    """The #137985 reference discharge (``fylite:reference_discharge``) from the
    kernel fixture, or SKIP."""
    import json
    doc = json.loads(kernel_fixture(REFERENCE_DISCHARGE).read_text(encoding="utf-8"))
    return doc["fylite:reference_discharge"]


def case_document(kind: str, shot: int = CASE_SHOT,
                  itime_ms: int = CASE_ITIME_MS) -> Path:
    """One of the case's fyo documents — ``kind`` is ``"case"`` (the measurement
    set), ``"equilibrium"`` or ``"oracle"`` — from the kernel's FYDOC-CASE-22
    mirror, or SKIP naming the file and the variable."""
    return kernel_fixture(f"{CASE_MIRROR}/{kind}_east{shot}_{itime_ms}ms.fyo.jsonld")


def east_measurements(shot: int = CASE_SHOT, itime_ms: int = CASE_ITIME_MS,
                      *, fwtmp2_zero: bool = True) -> dict:
    """The delivered #137985 @ 4.0 s magnetic measurement set.

    ★Nine test modules built this dict by hand from the a-file, five
    identical lines each.  The five fields ARE a measurement set, so they
    come from the measurement document now and the assembly happens once.

    ``fwtmp2_zero`` is the loops-only benchmark's fit control (``FWTMP2=0``,
    gap K-4) — a CHOICE about the fit, not a measurement, which is why it is
    an argument here and is not in the document.
    """
    import numpy as np

    from fylite import fyo as _fyo

    path = case_document("case", shot, itime_ms)
    doc = _fyo.read(path)
    #: ★★2026-09-13 (measurement-chain ruling): the READ is resolved in the chain the
    #: document itself declares (`measurement_chain`).  The FYDOC-CASE-22 record is the
    #: est2 array (79 probes + 35 loops, `fylite:channel_basis: est2`) and declares no
    #: chain — no device of any chain pairs with it, so it SKIPS by name (seam kept for the
    #: efit_east #137985 case that replaces it; once the record is archived,
    #: :func:`kernel_fixture` skips first with :data:`EST2_REMOVED`).  Only numbers leave
    #: the block; a caller that then needs the chain's GEOMETRY binds it itself
    #: (:func:`device_selected`).
    chain = doc.get(_device.CHAIN_KEY)
    if chain is None:
        pytest.skip(f"{path} declares no {_device.CHAIN_KEY} "
                    f"(fylite:channel_basis: {doc.get('fylite:channel_basis')!r}) — {EST2_UNPAIRED}")
    with device_selected(measurement_chain=chain):
        meas = _fyo.as_measurements(doc, itime_ms / 1000.0)
    meas.update(shot=int(shot), itime_ms=int(itime_ms))
    if fwtmp2_zero:
        meas["fwtmp2"] = [0.0] * len(np.asarray(meas["expmp2"]))
    return meas


# --------------------------------------------------------------------------- #
# the device RESOLVED for the data a test holds
# --------------------------------------------------------------------------- #
#: ★★2026-09-13 (user rulings R-S1 / R-S2 and the measurement-chain ruling): the static
#: EAST card is the NO-SHOT resolution — magnetics provider ``east_new`` (chain ``east``,
#: 79 HBPH probes + 75 loops).  Data recorded in another measurement chain is never read
#: against that one, so a test holding such data STATES its chain and binds the card
#: resolved for it through the runtime's rule (``fylite.device.document``) — never a
#: hand-picked file and never a named provider:
#:
#: * :data:`EFIT_TREE` — the processed ``efit_east`` tree (chain ``efit_east``: provider
#:   ``efit``, 76 probes + 35 loops, EXPMPI order): measurement sets built on the bound
#:   device's ``NPROBE`` / ``NSILOP``.
#:
#: There is no est2 selection any more (est2 removed at every layer).
EFIT_TREE = {"measurement_chain": "efit_east"}

from contextlib import contextmanager as _contextmanager  # noqa: E402


@_contextmanager
def device_selected(**selection):
    """Within the block ``fylite.device``'s derived names come from the configured
    card resolved for ``selection`` (``shot`` / ``measurement_chain``); yields that
    document.

    ★The previous binding — ``_DERIVED`` and every published name — is put back
    whichever way the block exits (the restore contract of ``device.bound``), so a
    test outside the block never observes the selection.
    """
    doc = _device.document(**selection)
    ns = vars(_device)
    saved = _device._DERIVED
    saved_names = {k: ns[k] for k in _device._DERIVED_NAMES if k in ns}
    for k in saved_names:
        del ns[k]
    _device._DERIVED = None
    try:
        _device.use_device(doc)
        yield doc
    finally:
        for k in _device._DERIVED_NAMES:
            ns.pop(k, None)
        ns.update(saved_names)
        _device._DERIVED = saved


@pytest.fixture
def efit_tree_device():
    """The card resolved for the ``efit_east`` tree (:data:`EFIT_TREE`), bound for one test."""
    with device_selected(**EFIT_TREE) as doc:
        yield doc


def east_equilibrium(shot: int = CASE_SHOT,
                     itime_ms: int = CASE_ITIME_MS) -> dict:
    """The delivered equilibrium as an ``fyo:equilibrium`` document.

    ★A document, not a g-file dict: every model entry that takes an
    equilibrium takes it through ``fyo.as_equilibrium``, so a consumer that
    wanted ``g["rmaxis"]`` was reaching around the layer rather than through
    it.  ``fyo.axis_of`` / ``ip_of`` / ``psi_map_of`` are the readers.
    """
    from fylite import fyo as _fyo
    return _fyo.read(case_document("equilibrium", shot, itime_ms))


# --------------------------------------------------------------------------- #
# the kernel
# --------------------------------------------------------------------------- #
# ★★**内核不在场 = 缺输入，不是缺实现** —— 与上面那套装置 deck 的政策同一条理由
# （`CorpusMissing` 那一条也是）。本仓是**公开**仓，内核（`libfylite_kernel.so`）
# 在私有仓里按 `rust/build.sh` 装进 `python/fylite/_lib/`；一个公开检出里它本来
# 就不在。此前这一档在那种检出里**红 108 条**，而红的不是「代码坏了」，是「输入
# 不在」——两件事在报告里长得一模一样，于是谁也不看它了。
#
# ★★转换是**有条件的**，这是它可以存在的唯一理由：只有当内核库文件**确实不在
# 盘上**时，才把这一条记成 skip。内核在场时什么都不转换——所以它不可能盖住一个
# 真的内核缺陷，而那正是「自动把失败改判成跳过」这种机制通常该被拒绝的原因。
from fylite import kernel as _kernel  # noqa: E402


def kernel_present() -> bool:
    """内核库在不在盘上（不加载它——加载会把一个坏库读成异常，那是另一件事）。"""
    try:
        return _kernel._lib_path().exists()
    except Exception:                                              # noqa: BLE001
        return False


#: 新写的测试用它显式声明「这条要内核」，比让下面的钩子事后改判清楚。
requires_kernel = pytest.mark.skipif(
    not kernel_present(),
    reason=(f"no kernel: {_kernel._lib_path()} is absent — it is built from the "
            "private kernel repository (rust/build.sh) and does not ship here"))

#: 内核不在场时，这些话就是「输入不在」的说法：前两句是 `fylite.kernel` 与数据层
#: 自己说的，第三句是**调用方没接住**那个 `None`（`load()` 缺席时给 None，随后
#: 一个 `fylite_rs_*` 属性取在了 NoneType 上）——同一件事的第三种长相。
_KERNEL_ABSENT_SAYS = (
    "the kernel is not available",
    "no kernel library with the fyo door",
    "'NoneType' object has no attribute 'fylite_rs_",
)

#: ★★**第二份库**（`FYL-REPORT-07` C-10 / R-6）。README 说「缺内核的检出照常收集，
#: 需要内核的按名跳过」——而实测里缺的常常不是内核，是**中间层**
#: （`libfylite_runtime.so`：格式 · 装配 · 计划→内核→记录）。它由本仓的
#: `rust/build.sh` 建，与内核那份由内核仓建，两条来路、一个目录；干净容器里内核建得
#: 起来而中间层要系统的 libhdf5 / libnetcdf，于是「有内核、没数据层」是一个**常态**，
#: 不是一种意外。那次实测：73 失败 / 10 错误，44 处是同一句话。
#: 政策与上面那条逐字相同：**库不在盘上**时才转换，在场时什么都不做。
_DATA_ABSENT_SAYS = ("the data library is not built",)


def data_lib_present() -> bool:
    """中间层库在不在盘上（不加载它，同 :func:`kernel_present` 的理由）。"""
    try:
        from fylite._paths import DATA_LIB
        return Path(DATA_LIB).exists()
    except Exception:                                              # noqa: BLE001
        return False


requires_data_lib = pytest.mark.skipif(
    not data_lib_present(),
    reason="no data library: run `bash rust/build.sh` (needs libhdf5 / libnetcdf, "
           "or `--static`)")

#: 判据语料（`tests/data` → fydoc 的 `cases/`，一条符号链接）。它是**私有**的，
#: README 已经写明公开检出里没有它。政策与内核那条同一条：不在场 = 缺输入。
STORE = Path(__file__).resolve().parents[1] / "tests" / "data"


def store_present() -> bool:
    return STORE.is_dir()


#: 装置牌（2026-09-13 起由 A-Box 生成进 facts 语料 `dist/facts/device/<id>/`，
#: 不进版本库）；语料目录里点名了装置的算例因此在没建语料的检出里跑不动。
#: 政策同上：不在场 = 缺输入。★问 facts 搜索路径，不猜检出路径。
def device_corpus_present() -> bool:
    from fylite import facts as _facts
    return any((r / "device").is_dir() for r in _facts.roots())


requires_store = pytest.mark.skipif(
    not store_present(),
    reason=(f"no reference store: {STORE} is absent — it is a symlink to "
            "fydata's private oracle/ tree and does not ship here"))


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """**输入不在场**导致的失败 → skip（点名），其余原样。

    四条，各自条件成立时才转换：内核库不在盘上、**中间层库不在盘上**、判据语料
    不在盘上、装置牌不在盘上。所以它们在场时，这个钩子什么都不做——它盖不住一个
    真的缺陷。
    """
    outcome = yield
    report = outcome.get_result()
    if report.outcome != "failed":
        return
    text = str(getattr(call, "excinfo", None) and call.excinfo.value) or report.longreprtext
    why = None
    if not kernel_present() and any(s in text for s in _KERNEL_ABSENT_SAYS):
        why = ("the kernel is absent in this checkout "
               "(it is built from the private kernel repository)")
    elif not data_lib_present() and any(s in text for s in _DATA_ABSENT_SAYS):
        why = ("the data library is absent in this checkout "
               "(`bash rust/build.sh` builds it; it needs libhdf5 / libnetcdf, "
               "or pass --static)")
    elif not store_present() and ("tests/data" in text or str(STORE) in text):
        why = (f"the reference store is absent in this checkout ({STORE} is a "
               "symlink to fydata's private oracle/ tree)")
    elif not device_corpus_present() and "no device/" in text:
        why = ("no device corpus on the facts path (the cards are generated from "
               "the A-Box by tools/abox-to-facts.py into dist/facts/device/)")
    if why is None:
        return
    report.outcome = "skipped"
    #: pytest 的 skip 三元组：(文件, 行, 理由)
    report.longrepr = (str(item.fspath), item.location[1] or 0,
                       f"Skipped: {why}; the failure was: "
                       + text.strip().splitlines()[0][:200])


def east_case(shot: int = CASE_SHOT, itime_ms: int = CASE_ITIME_MS) -> dict:
    """The bundled offline case: measurements and equilibrium from the kernel's
    FYDOC-CASE-22 mirror, the device from the configured card.

    ★This used to be ``fylite.widgets.load_case``; the panels are gone and
    the loader was only ever test/example glue, so it lives with the tests.
    Needs the machine deck — SKIPs otherwise, and the reason names the file.
    """
    import tempfile

    import numpy as np

    tables = machine_tables()
    root = Path(__file__).resolve().parent
    dev = _device.load_device(_device.card_path())
    meas = east_measurements(shot, itime_ms)
    return {"root": root, "tables": tables, "device": dev,
            "eq": east_equilibrium(shot, itime_ms),
            "meas": meas, "aturns": np.asarray(meas["brsp"], float),
            #: ★``"wpf2018"``, the table SET NAME — not ``str(tables)``, the
            #: deck DIRECTORY, which is what stood here.  The two are
            #: different arguments to the same keyword: a name selects a
            #: bundled Green set, a path is taken as the set itself, and the
            #: deck directory is not one ("missing table files: ec6565.ddd,
            #: rfcoil.ddd, ep6565.ddd").  It never showed because no test
            #: that uses ``solve`` could reach it; every other call site in
            #: the tree already says ``tables="wpf2018"``.
            "solve": {"preset": "gui_v5", "tables": "wpf2018"},
            "out": tempfile.mkdtemp(prefix="fylite_case_")}
