"""What still speaks TGLF/NEO on the production path, and what no longer does.

★★This file exists because "NEO no longer builds a deck" was, until it was
written, a claim in a changelog.  A claim like that decays silently: the call
comes back in a refactor, every test still passes, and the only trace is a
sentence someone wrote once.

The production path is ``fyo.turbulent_transport`` -> ``closure.kernel_chi``.
Both of its channels now run on the Rust kernel:

* **NEO** — ``kernel.neo_sauter``, measured at 5.8e-15 against the recorded
  library before the switch.  ``mapping.neo_inputs`` must have NO caller
  here.
* **TGLF** — ``gyrofluid.fluxes_kernel``.  ``mapping.tglf_inputs`` still has
  one caller, and that is not a deck in the sense this file was written to
  police: it is how the PORT is addressed, since the port's argument names
  are ``input.tglf``'s.  What must not come back is the REPLAY.

★★★What this file used to assert, and why it changed.  The TGLF channel was
``tglf.run_isolated`` — a replay keyed by a JSON digest of the deck, backed
by recordings from a libtglf that left with LICENSE 3.2.  So the package's
top-level turbulence door answered only for surfaces that vanished library
had been recorded on, and for every other equilibrium raised
``OracleMissing`` where a flux belonged.  This file said the port could not
take over because it requires ``WIDTH`` and libtglf bisected for it.

That was true about the WIDTH and wrong about the conclusion.  A width the
port cannot find is a missing INPUT, and an input is something a caller can
state; ``kernel_chi`` and ``fyo.turbulent_transport`` now require ``width=``
and the channel is the kernel.  The replay is a test fixture, which is what
it always was.

So the assertions here are now symmetric: neither channel may reach a
recorded answer, and the hook must return finite diffusivities for an
equilibrium nothing was ever recorded on — which is the whole of what the
old skip was hiding.
"""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

import fylite

PKG = Path(fylite.__file__).resolve().parent
CLOSURE = PKG / "scenario" / "model" / "closure.py"


def _calls(path: Path, dotted: str):
    """Line numbers where ``a.b(...)`` is called, docstrings excluded."""
    mod, _, attr = dotted.partition(".")
    tree = ast.parse(path.read_text())
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == attr
            and isinstance(n.func.value, ast.Name) and n.func.value.id == mod]


def test_the_closure_never_builds_a_neo_deck():
    """★NEO's deck left the production path when its channel moved to the
    port.  If this fails, the closure is back on the recorded library — and
    the recordings are keyed by a deck, so it will look like it works.
    """
    hits = _calls(CLOSURE, "mapping.neo_inputs")
    assert not hits, (
        f"closure.py builds a NEO deck again at line(s) {hits}. The NEO "
        "channel runs on the kernel port (kernel.neo_sauter, vintage=4); a "
        "deck here means it has gone back to the frozen replay.")


def test_the_closure_replays_no_recorded_answer():
    """★★The invariant that replaced "exactly one TGLF deck".

    That count was 1 because the TGLF channel was a replay and the deck was
    its lookup key.  It is 1 today for an unrelated reason — the port takes
    ``input.tglf`` names — so the count no longer distinguishes the two
    states it was written to distinguish.  What does is the REPLAY itself:
    no entry of the recorded store may be reachable from the production
    closure.

    ★A recorded answer here does not fail loudly.  It answers, correctly,
    for exactly the surfaces someone once recorded, and raises
    ``OracleMissing`` for every other equilibrium — which reads as a missing
    build rather than as a model that is not there.
    """
    replays = ("tglf_mod.run_inputs", "tglf_mod.run_isolated",
               "tglf_mod.run", "_oracle.cached")
    hits = {name: _calls(CLOSURE, name) for name in replays}
    found = {k: v for k, v in hits.items() if v}
    assert not found, (
        f"closure.py reaches the recorded store again: {found}. Both "
        "channels run on the kernel (gyrofluid.fluxes_kernel, "
        "kernel.neo_sauter); a replay here answers only for surfaces that "
        "happen to have been recorded and raises OracleMissing for the "
        "rest.")

    src = CLOSURE.read_text()
    assert "_oracle" not in src, (
        "closure.py names fylite._oracle — the production path does not "
        "read recorded answers.")


def test_the_fyo_face_carries_no_upstream_vocabulary():
    """★The public face is fyo, and stays that way.

    ``fyo.turbulent_transport`` takes an fyo equilibrium and profiles and
    returns an ``fyo:core_transport`` document.  A TGLF or NEO deck name
    appearing in its signature or its returned keys would mean the upstream
    vocabulary had leaked out to callers.
    """
    from fylite import _deck_names

    src = (PKG / "fyo.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "turbulent_transport")
    body = "\n".join(src.splitlines()[fn.lineno - 1:fn.end_lineno])

    upstream = set()
    for name in dir(_deck_names):
        if name.isupper():
            upstream |= set(getattr(_deck_names, name))
    #: short, common tokens would false-positive on ordinary text
    leaked = sorted(w for w in upstream
                    if len(w) > 3 and f'"{w}"' in body)
    assert not leaked, (
        f"fyo.turbulent_transport names upstream deck fields {leaked} — the "
        "fyo face is meant to be the boundary, so the vocabulary belongs "
        "behind it.")


# --------------------------------------------------------------------------- #
# ...and it is WIRED.  The cases above read the source; this one runs it.
# --------------------------------------------------------------------------- #
_GFILE = Path(fylite.__file__).resolve().parents[2] / \
    "tests/data/synthetic/g_synthetic.geqdsk"

_PSIN = np.linspace(0.0, 1.0, 101)
_NE = 4e19 * (1 - 0.8 * _PSIN ** 2)                 # m^-3
_TE = 2200.0 * (1 - 0.9 * _PSIN ** 2) + 120.0       # eV
_TI = 1600.0 * (1 - 0.9 * _PSIN ** 2) + 120.0

#: The mode width these cases evaluate at.  ★A test fixture, not a
#: recommended value: the port solves at the width it is given and nothing
#: in this repository searches for one, so every caller states an operating
#: point.  1.65 is the width the ported flux tests use
#: (``test_tglf_rust.DECK``), which keeps this file's number and theirs the
#: same number rather than two independently chosen ones.
_WIDTH = 1.65


def _chi_hook():
    """The closure hook on the BUNDLED synthetic equilibrium."""
    from fylite import fyo, kernel
    from fylite.scenario.model import closure
    tm = fyo.transport_metrics(_GFILE, n_surfaces=41, edge=0.95)
    (rho, psin_grid), (gm3,) = kernel.with_axis_node(
        zero=(tm["rho"], tm["psin"]), repeat=(tm["gm3"],))
    chi = closure.kernel_chi(
        _GFILE, psin=[0.3, 0.5, 0.7], psin_prof=_PSIN, ne=_NE,
        gm3_at=lambda r: float(np.interp(r, rho, gm3)), zeff=1.8,
        width=_WIDTH)
    return chi, rho, psin_grid


def test_the_closure_reaches_its_solvers():
    """★★The production TGLF/NEO path is WIRED — the cheap half of the
    claim, and the half that was false.

    ``closure.py`` carried ``from . import neo as neo_mod``, a name the
    ``neo`` -> ``neoclassical`` rename left bound to nothing.  It was read by
    nothing, so it looked dead; it was still executed, so every caller of
    ``kernel_chi`` — and therefore ``fyo.turbulent_transport``, the package's
    top-level turbulence door — raised ``ImportError`` on contact.

    ★And the reason no test said so: the only case that called this function
    was marked ``@``, for an EAST discharge this
    distribution does not carry.  It never needed that discharge — its body
    uses the bundled synthetic g-file and nothing else.  A permanently-true
    skip predicate is a deleted test, and this one had been deleted for as
    long as the marker had been on it.

    So this case takes no marker.  ★★And it no longer tolerates anything.
    It used to return early on ``OracleMissing`` — "reached the TGLF seam,
    everything this test is about ran" — and that early return was taken on
    EVERY run, because nothing was ever recorded for the synthetic
    surfaces.  So the half of the claim after the seam, which is the half
    that produces the diffusivities, was never executed here.  With the
    TGLF channel on the port there is no seam and no record to miss: the
    hook returns numbers or the test fails.
    """
    chi, rho, psin_grid = _chi_hook()
    te = np.interp(psin_grid, _PSIN, _TE)
    ti = np.interp(psin_grid, _PSIN, _TI)
    chi_e, chi_i = chi(rho, te, ti)
    assert chi_e.shape == rho.shape and chi_i.shape == rho.shape
    assert np.all(np.isfinite(chi_e)) and np.all(np.isfinite(chi_i))
    #: the guard band the closure clips to, and NOT everywhere at its floor:
    #: a channel that returned zero flux would clip to `chi_floor` on every
    #: node and still be finite.
    assert np.all(chi_e >= 0.05) and np.all(chi_e <= 50.0)
    assert np.all(chi_i >= 0.05) and np.all(chi_i <= 50.0)
    assert chi_e.max() > 0.05 * 1.01 and chi_i.max() > 0.05 * 1.01


# --------------------------------------------------------------------------- #
# ...and the operating point is the CALLER's, at both layers.
# --------------------------------------------------------------------------- #
def test_the_mode_width_has_no_default_at_either_layer():
    """★★``width`` is required, and stays required.

    libtglf bisected for the mode width; the port solves at the width it is
    handed and nothing in this repository searches for one.  So a default
    here would not be a convenience — it would be this package choosing the
    operating point of every TGLF solve of every march, on the caller's
    behalf, with no way for the caller to know it had been chosen.

    A default is exactly the kind of thing that gets added to make a call
    site shorter, so the absence is pinned rather than described.
    """
    import inspect

    from fylite import fyo
    from fylite.scenario.model import closure

    #: ★`kernel_coefficients` joins the list the day it exists: it is the
    #: factory `kernel_chi` now delegates to, so a default added there
    #: would reach every caller of both.
    for fn in (fyo.turbulent_transport, closure.kernel_chi,
               closure.kernel_coefficients):
        par = inspect.signature(fn).parameters["width"]
        assert par.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{fn.__qualname__}: width must be keyword-only")
        assert par.default is inspect.Parameter.empty, (
            f"{fn.__qualname__}: width has acquired the default "
            f"{par.default!r}. There is no width to default to — the "
            "library that searched for one is gone and the port does not.")


def test_the_width_reaches_the_solver():
    """★A required parameter that changes nothing is worse than a default:
    it asks the caller for a number and then ignores it.
    """
    chi, rho, psin_grid = _chi_hook()
    te = np.interp(psin_grid, _PSIN, _TE)
    ti = np.interp(psin_grid, _PSIN, _TI)
    base = chi(rho, te, ti)[1]

    from fylite import fyo, kernel
    from fylite.scenario.model import closure
    tm = fyo.transport_metrics(_GFILE, n_surfaces=41, edge=0.95)
    (r2, _), (gm3,) = kernel.with_axis_node(
        zero=(tm["rho"], tm["psin"]), repeat=(tm["gm3"],))
    other = closure.kernel_chi(
        _GFILE, psin=[0.3, 0.5, 0.7], psin_prof=_PSIN, ne=_NE,
        gm3_at=lambda r: float(np.interp(r, r2, gm3)), zeff=1.8,
        width=_WIDTH * 0.6)(rho, te, ti)[1]

    assert np.max(np.abs(other - base)) > 1e-6 * np.max(np.abs(base)), (
        "the mode width does not reach the solver: two widths gave the "
        "same diffusivities")


# --------------------------------------------------------------------------- #
# ...and the package keeps no deck writer it does not use.
# --------------------------------------------------------------------------- #
def test_the_package_hosts_no_mapper_only_its_tests_call():
    """★★A deck writer with only test callers is a test's deck writer.

    ``mapping.neo_inputs`` and ``mapping.derive`` sat in the package with no
    caller in it — six and five test callers respectively — and
    ``mapping.coulomb_log`` had none at all.  They looked like production
    surface because of where they lived, and one of them was even being held
    up as a live consumer of a generated table
    (``test_deck_names_have_one_source``, which pinned the dead
    ``gacode._VECTOR_KEYS``).

    ★They also answer the "converge the deck maps into the kernel" question
    differently and better: the kernel already had the arithmetic
    (``kernel.neo_local``), and what stayed in Python was the NAMING.  A name
    table nothing in production reads does not need porting; it needs to
    leave.
    """
    import ast
    from pathlib import Path

    import fylite

    pkg = Path(fylite.__file__).resolve().parent
    mapping_src = pkg / "scenario" / "model" / "mapping.py"
    defined = {n.name for n in ast.parse(mapping_src.read_text()).body
               if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")}
    used = set()
    for src in pkg.rglob("*.py"):
        if src == mapping_src:
            continue
        for node in ast.walk(ast.parse(src.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute):
                used.add(node.attr)
            elif isinstance(node, ast.Name):
                used.add(node.id)
    orphans = sorted(defined - used)
    assert not orphans, (
        f"fylite.scenario.model.mapping exports {orphans} that nothing in the "
        "package calls.  If the tests want them, they belong in "
        "tests/oracles/; if nobody does, they belong nowhere.")
