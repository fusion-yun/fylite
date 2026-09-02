"""fylite — a tokamak equilibrium / transport / turbulence kernel.

A Rust core does the physics and the numerics; this package converts what a
machine or another code wrote into fyo-semantic documents, hands their arrays
to the kernel, and puts the answers back on disk.  ``numpy`` is the only hard
dependency, and the kernel ships pre-built
(:mod:`fylite.kernel`, ``python/fylite/_lib/libfylite.so``).

Where to start:

:mod:`fylite.fyo`
    the document layer — ``equilibrium``, ``core_profiles``, the source and
    transport faces, and ``read``/``write``.  Almost every entry below takes
    an ``fyo:equilibrium`` document, or a g-file at the door.
:mod:`fylite.kernel`
    the C-ABI surface: the Grad-Shafranov solves, surface tracing, the GEO /
    NEO / TGLF ports, the transport core.
:mod:`fylite.scenario`
    ``model`` (0-D, transport, TGLF/NEO closures, beams, LH),
    ``analysis`` (reconstruction, the self-consistent loop, tomography),
    ``control`` and ``design``.
:mod:`fylite.io`
    other people's formats: g-files, ``input.gacode``, k-files, MDSplus.
:mod:`fylite.device`
    the machine description, which this distribution does not carry — point
    ``$FYLITE_DEVICE_DIR`` at one.  Everything that needs no machine works
    with no configuration.

★★This docstring said "Python wrapper for the ported EAST KEFIT/EFIT
executable" and "the whole API is a single entry point, :func:`fylite.run`",
then described that entry's "fork-per-call ``run_efit``" and "typed ``.so``
ABI".  None of it is true: the EFIT lineage left (see ``NOTICE``),
``fylite.run`` is a module rather than a callable and reads recorded answers
the store does not contain, and the package's subject is now the kernel and
the document layer.  It is the first thing a reader — or a tool reading only
the module header — sees, so it was the most expensive stale docstring in
the tree.

:mod:`fylite.engine` doubles as this repo's **architecture-validation case**:
it is the reference implementation of SpModel's ``ExecutionBody`` protocol
(SPM-ADR-111 / SPM-ADR-112) for a non-reentrant native library, and it
validates that protocol — see ``engine.PROTOCOL`` and
``python/tests/test_protocol_conformance.py`` — while importing nothing from
the sp / fy ecosystem, so this port stays installable on its own.
"""
from __future__ import annotations

#: ★★Everything below is LAZY (PEP 562).  The names are the same and
#: ``fylite.scenario`` still works on first touch; what changed is that
#: touching none of them costs nothing.
#:
#: This block used to be eager — ``from . import device, engine, io,
#: kernel``, then ``.device``, ``.run``, then ``. import scenario`` — and
#: that made FYL-SDD-01 DE-COMP-03's invariant ("``fylite.engine``'s
#: top-level imports are stdlib only; numpy and heavy dependencies are
#: imported lazily inside functions") unobservable: importing ANY submodule
#: runs this file first, so ``import fylite.engine`` loaded numpy and nine
#: ``fylite.scenario.*`` modules no matter how careful the engine was.  An
#: invariant nothing can witness is not an invariant.
#:
#: ★★The ORDER used to be load-bearing — ``.run`` had to be imported
#: before ``.scenario`` — and it is not any more, because the CYCLE is
#: gone.  ``run`` re-exported two PRIVATE helpers from
#: ``scenario.analysis.recon_rs`` while ``recon_rs`` imported
#: ``KefitRunError`` back out of ``run``; the first half had no caller in
#: the package at all (see ``run.py``), so cutting it left one direction
#: and no ordering rule to encode here.
_SUBMODULES = ("device", "engine", "io", "kernel", "run", "scenario")

#: ★:data:`_SUBMODULES` is what this package's front page NAMES — what
#: ``__dir__`` advertises and what the docstring above walks a reader
#: through.  It is not the set that can be reached: :func:`__getattr__`
#: imports any submodule on demand.

#: ``exported name -> (submodule, attribute)``
_ATTRS = {
    "device_geometry": ("device", "device_geometry"),
    "KefitRunError": ("run", "KefitRunError"),
    "forward_equilibrium": ("run", "forward_equilibrium"),
}


def __getattr__(name: str):
    import importlib

    if name in _ATTRS:
        sub, attr = _ATTRS[name]
        value = getattr(__getattr__(sub), attr)
        globals()[name] = value
        return value
    #: ★ANY submodule, not just :data:`_SUBMODULES`.  Eagerly, `import
    #: fylite` pulled in most of the package transitively, so
    #: `fylite.fyo` and friends answered as attributes whether or not this
    #: file named them.  Importing on demand keeps that true instead of
    #: turning a working access into an `AttributeError` for the modules
    #: that happened to ride along.
    if not name.startswith("__"):
        try:
            mod = importlib.import_module(f".{name}", __name__)
        except ModuleNotFoundError:
            pass
        else:
            globals()[name] = mod
            return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted({*globals(), *_SUBMODULES, *_ATTRS})


#: ★One source for the release version: the installed distribution's own
#: metadata, which setuptools fills from the repository's `VERSION` file
#: (`pyproject.toml`'s dynamic version).  It was a hand-kept literal here and
#: it drifted — `0.1.0` against `VERSION`'s `0.0.1-alpha` — which would have
#: put two release identities on one body of code the day a second
#: distribution channel opened.
#:
#: In-tree (not installed) there is no metadata, so the `VERSION` file is read
#: directly; both paths are stdlib, and neither is allowed to raise — a
#: package that cannot import because it cannot name itself would be a poor
#: trade for a string that is only ever displayed.
def _release_version() -> str:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("fylite")
    except PackageNotFoundError:
        pass
    from pathlib import Path
    for candidate in (Path(__file__).resolve().parents[1] / "VERSION",
                      Path(__file__).resolve().parents[2] / "VERSION"):
        try:
            return candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return "unknown"


__version__ = _release_version()
__all__ = ["run", "device_geometry", "scenario"]
