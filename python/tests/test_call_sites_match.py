"""Every in-package call must fit the signature it is calling.

★★Why this exists.  ``scenario/analysis/loop.py`` binds the reconstruction
entry as a module-level alias::

    from .recon_rs import reconstruct as _efit_run

and then calls it as ``_efit_run(shot, time_s, kind="east", out=workdir,
server=server, **run_kw)`` — two positionals and three keywords that
``reconstruct(meas, *, table_dir, ...)`` does not have.  It raises
``TypeError`` on contact.  ``self_consistent`` is described in its own module
as the kinetic-EFIT outer loop that has been in this repo the longest, and it
cannot execute its first statement.

★And the suite could not see it, because **three** test modules
(``test_loop``, ``test_lh``, ``test_inwant_weight``) each
``monkeypatch.setattr(m, "_efit_run", fake_run)``.  Mocking the seam is
right — those cases are about the loop's mechanics, not about running a real
solve — but it means the seam itself is asserted by nothing.  A stub is a
statement about what the callee accepts, and nothing was checking that
statement against the callee.

This costs a fraction of a second, needs no machine data and no kernel, and
would have caught it: bind each call site's literal arguments against the
imported callable's real signature.
"""
from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

import fylite

PKG = Path(fylite.__file__).resolve().parent


#: ★Known-broken call sites, each with what has to happen before it can go.
#: This list may only SHRINK — a new entry means a new defect, and the point
#: of naming them here rather than skipping the file is that the count is
#: visible.
KNOWN_BROKEN: dict[str, str] = {
    #: ★★EMPTY, and it is worth saying what left.  For months this held
    #: ``scenario/analysis/loop.py:_efit_run`` — the self-consistent kinetic
    #: loop calling the reconstruction with the signature of the EFIT driver
    #: that left with LICENSE 3.1.  It was NOT a rewiring: the loop states
    #: its current prior as a flux-surface-AVERAGED target (EFIT's
    #: ``KZEROJ``/``SIZEROJ``/``VZEROJ`` at ``RZEROJ = 0``) and
    #: ``reconstruct`` took only ``current_source=``, a per-interior-cell
    #: SOURCE.  A target the fit is pulled toward and a source imposed on
    #: the solve are different statements, so converting one into the other
    #: silently would have changed what the loop computes — which is why
    #: this entry said "that is a decision, not a repair".
    #:
    #: The decision was taken (2026-08-25): the FSA target went INTO THE
    #: KERNEL as constraint rows of its own (``inverse::fsa_current_row``,
    #: ABI v113's ``gs_inverse_solve_fsa``), and the loop now hands the
    #: kernel the same physics it always stated.
    #:
    #: A waiver here may only SHRINK.  It has reached zero; the next entry
    #: is a new defect and should be argued for on its own.
}


def _package_of(path: Path) -> str:
    """The package a relative import in ``path`` is resolved against.

    ★For ``__init__.py`` that is the module ITSELF, not its parent — a
    ``from . import x`` inside a package's ``__init__`` means that package.
    Getting this off by one resolves every relative import in the four
    ``__init__`` modules to the wrong place, where it simply fails to
    resolve and the calls go unchecked — silently, which is the failure this
    file is about.
    """
    rel = path.relative_to(PKG)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    else:
        parts = parts[:-1]
    return ".".join(["fylite", *parts])


def _module_name(path: Path) -> str:
    rel = path.relative_to(PKG).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join(["fylite", *parts]) if parts else "fylite"


def _alias_map(node: ast.ImportFrom, pkg: str) -> dict[str, str]:
    """``{local name: dotted target}`` for one ``from X import y``.

    Both spellings count: ``from .mod import fn`` binds a function, and
    ``from . import mod`` binds a MODULE whose attributes are then called —
    the second is how most of this package calls itself.
    """
    if node.level:
        base = pkg.rsplit(".", node.level - 1)[0] if node.level > 1 else pkg
        if node.module:
            base = f"{base}.{node.module}"
    else:
        base = node.module or ""
    if not base.startswith("fylite"):
        return {}
    return {a.asname or a.name: f"{base}:{a.name}"
            for a in node.names if a.name != "*"}


#: statement kinds that open a new binding scope: a name imported inside one
#: is not visible outside it, and names imported outside it ARE visible in.
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _split_scope(stmts):
    """``(nodes of this scope, nested scope nodes)``.

    A nested ``def`` belongs to its parent as a *statement* — its decorators
    and default arguments are evaluated there — while its BODY is a scope of
    its own and is walked separately, with whatever the parent had bound.
    """
    here, nested, stack = [], [], list(stmts)
    while stack:
        n = stack.pop()
        if isinstance(n, _SCOPES):
            nested.append(n)
            stack.extend(n.decorator_list)
            stack.extend(getattr(n, "bases", ()))
            args = getattr(n, "args", None)
            if args is not None:
                stack.extend(d for d in args.defaults if d is not None)
                stack.extend(d for d in args.kw_defaults if d is not None)
            continue
        here.append(n)
        stack.extend(ast.iter_child_nodes(n))
    return here, nested


def _scope_calls(stmts, aliases: dict[str, str], pkg: str):
    """Yield ``(call, aliases)`` for every call in this scope, then recurse
    into the scopes nested in it.

    ★★Why scopes at all, when the first version read module level only.  This
    package's mechanical core imports its physics INSIDE the handler that uses
    it — ``engine/cli.py`` and ``engine/serve.py`` say so in their own module
    docstrings ("physics entry points are imported inside the handlers so this
    module's import surface stays stdlib"), and ``engine/provenance.py`` does
    the same with numpy to keep DE-COMP-03's stdlib-only invariant.  A scan
    that saw only module-level imports therefore could not see a single call
    the engine makes into the rest of the package — and that is exactly where
    the defect was: ``fylite run`` and the MCP ``fylite_run`` tool BOTH called
    ``recon_rs.reconstruct`` with the signature of the EFIT driver that left
    with LICENSE 3.1, in all four input modes, and this file walked past them
    while waiving the one module-level instance of the same mistake.
    """
    here_nodes, nested = _split_scope(stmts)
    here = dict(aliases)
    for n in here_nodes:
        if isinstance(n, ast.ImportFrom):
            here.update(_alias_map(n, pkg))
    for n in here_nodes:
        if isinstance(n, ast.Call):
            yield n, here
    for fn in nested:
        yield from _scope_calls(fn.body, here, pkg)


def _resolve(target: str):
    mod, _, name = target.partition(":")
    try:
        return getattr(importlib.import_module(mod), name)
    except Exception:                            # noqa: BLE001 — not our subject
        return None


SOURCES = sorted(PKG.rglob("*.py"))
assert SOURCES, "no package modules found"


def _scan(src: Path, *, pkg: str | None = None,
          rel: str | None = None) -> list[tuple[str, str]]:
    """``[(alias, message)]`` for every call in ``src`` that cannot bind.

    ``pkg`` / ``rel`` let the same scan run over a file that is NOT a package
    module (``tools/*.py``): those use absolute imports, so there is no
    package to resolve relative ones against.
    """
    tree = ast.parse(src.read_text(encoding="utf-8"))
    local = {n.name for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    #: a file outside the package has no importable module name, so a call to
    #: a function defined in it cannot be resolved by import — only its calls
    #: into fylite are checkable.
    here = _module_name(src) if rel is None else None
    rel = rel if rel is not None else str(src.relative_to(PKG))
    bad: list[tuple[str, str]] = []
    for node, aliases in _scope_calls(
            tree.body, {}, pkg if pkg is not None else _package_of(src)):
        #: two call shapes resolve to something this package owns: a bare
        #: alias (`_efit_run(...)`, from `import x as _efit_run`) and an
        #: attribute on an imported MODULE (`stability.plasma_filaments(...)`).
        #: Only handling the first would cover the one defect that prompted
        #: this file and almost nothing else — most calls here are the second.
        if isinstance(node.func, ast.Name):
            label = node.func.id
            #: an imported alias, else a function defined in THIS module.
            #: ★Local calls were missed by the first version and that was not
            #: academic: `recon_rs.run_series` calls its own `reconstruct`
            #: with the vanished EFIT driver's signature, and the scan walked
            #: straight past it because the name is not an import.
            target = aliases.get(label) or (
                f"{here}:{label}" if here and label in local else None)
        elif (isinstance(node.func, ast.Attribute)
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id in aliases):
            base = _resolve(aliases[node.func.value.id])
            if not inspect.ismodule(base):
                continue
            label = f"{node.func.value.id}.{node.func.attr}"
            target = f"{base.__name__}:{node.func.attr}"
        else:
            continue
        if target is None:
            continue
        fn = _resolve(target)
        if fn is None or not callable(fn) or inspect.isclass(fn):
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue

        #: a `*args` at the call site makes the positional count unknowable,
        #: so only the keywords are checkable there.
        star = any(isinstance(a, ast.Starred) for a in node.args)
        n_pos = len(node.args)
        kwargs = [k.arg for k in node.keywords if k.arg is not None]
        takes_kw = any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values())
        takes_var = any(p.kind is p.VAR_POSITIONAL
                        for p in sig.parameters.values())
        positional = [p for p in sig.parameters.values()
                      if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]

        if not star and not takes_var and n_pos > len(positional):
            bad.append((node.func.id,
                        f"{rel}:{node.lineno} {node.func.id}() takes at most "
                        f"{len(positional)} positional arg(s), called with "
                        f"{n_pos}  [{target}]"))
        if not takes_kw:
            unknown = [k for k in kwargs if k not in sig.parameters]
            if unknown:
                bad.append((node.func.id,
                            f"{rel}:{node.lineno} {node.func.id}() has no "
                            f"parameter(s) {unknown}  [{target}]"))
    return bad


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: str(p.relative_to(PKG)))
def test_calls_fit_the_signature_they_call(src: Path):
    rel = str(src.relative_to(PKG))
    unexpected = [m for alias, m in _scan(src)
                  if f"{rel}:{alias}" not in KNOWN_BROKEN]
    assert not unexpected, (
        "call sites that do not fit the signature they call:\n  "
        + "\n  ".join(unexpected))


def test_every_waiver_was_actually_exercised():
    """★★A waiver for something the scan no longer FINDS is the dangerous
    kind: it reads as "known issue, tracked" while the scan has quietly
    stopped looking — a broken detector and a green suite.  That is the same
    failure this file exists to catch, one level up.

    ★It rescans rather than reading what the parametrised cases accumulated.
    Sharing state would make this pass or fail on TEST ORDER — green in a
    full run, red when someone runs this case alone — and a gate that depends
    on how it was invoked is not a gate.
    """
    found = {f"{src.relative_to(PKG)}:{alias}"
             for src in SOURCES for alias, _ in _scan(src)}
    missed = sorted(set(KNOWN_BROKEN) - found)
    assert not missed, (
        f"waived but not detected by the scan: {missed}\n"
        "Either the defect is fixed (drop the waiver) or the detector "
        "stopped seeing it (fix the detector).")


def test_a_waived_entry_is_not_advertised_as_a_tool():
    """★★The two registers have to agree.  ``loop:self_consistent`` is waived
    here as a DESIGN question — and the manifest that names it was reflected
    onto the tool face regardless, so a model could select
    ``fylite_kinetic_reconstruction`` and get the same ``TypeError`` the
    waiver is about.  A capability may be published while it cannot run; it
    may not be ADVERTISED as callable.  When the design question is settled
    and the waiver goes, this test is what tells you to flip the flag back.
    """
    import json as _json
    manifest = (PKG / "_manifest" / "kinetic_reconstruction.jsonld")
    doc = _json.loads(manifest.read_text())
    waived = "scenario/analysis/loop.py:_efit_run" in KNOWN_BROKEN
    executable = doc.get("fylite:executable") is not False
    assert waived != executable, (
        "kinetic_reconstruction: the call-site waiver and the manifest's "
        f"`fylite:executable` disagree (waived={waived}, "
        f"executable={executable})")
    if not executable:
        assert doc.get("fylite:executable_note"), (
            "a capability declared non-executable must say why, where a "
            "caller looks")


def test_the_seam_the_last_waiver_covered_is_sound():
    """★The waiver that left, kept as the property it was hiding.

    ``loop._efit_run`` must be the SHOT/TIME door (the loop starts from a
    shot and a time), and the reconstruction must take the flux-surface-
    averaged current target the loop states — the design question that kept
    this seam broken, settled IN THE KERNEL rather than papered over in the
    call.
    """
    from fylite.scenario.analysis import loop
    from fylite.scenario.analysis.recon_rs import reconstruct, reconstruct_shot
    assert loop._efit_run is reconstruct_shot, (
        "`_efit_run` is not the shot/time door any more — re-check what this "
        "loop starts from")
    assert "current_fsa" in inspect.signature(reconstruct).parameters, (
        "`reconstruct` lost its FSA-current constraint; the loop's prior has "
        "nowhere to go and this seam is broken again")
    assert not KNOWN_BROKEN, (
        f"a call-site waiver is back: {sorted(KNOWN_BROKEN)} — the register "
        "may only shrink, so a new entry needs its own argument")


# --------------------------------------------------------------------------- #
# tools/ — the same defect family, outside the package
# --------------------------------------------------------------------------- #
#
# ★★``tools/make_synthetic_case.py`` — the generator of the fixture the whole
# suite is anchored on — said ``from fylite import appsession, kernel as K,
# rustlib`` and called ``appsession._format_geqdsk``.  Both names had moved out
# from under it (the loader is ``fylite.kernel``; the g-file writer went to
# ``fylite.io.geqdsk``, beside its reader), so the script raised ``ImportError``
# on line 33 and the fixture could not be regenerated.  Nothing noticed,
# because the scan above walks the PACKAGE and this is a script.
#
# A script that regenerates a committed fixture is not a lesser artefact than
# a module: if it stops working, the fixture becomes unreproducible and the
# thing it anchors becomes a number nobody can re-derive.

TOOLS = sorted((PKG.parents[1] / "tools").glob("*.py"))


#: ★Names a tool imports that are NOT there, each with what has to happen
#: before it can go.  Same discipline as ``KNOWN_BROKEN``: this list may only
#: SHRINK, and a waiver that stops being detected is itself a failure.
#: ★★2026-09-01 清空：唯一一条豁免（``tools/make-east-inputs.py`` 对
#: ``fylite.circuits`` 的引用）随 ``tools/`` 整棵移出本仓而失去对象。豁免表的纪律是
#: **只许缩小**，而「被豁免的东西扫不到了」本身就是失败——这道闸抓的正是这个：
#: 它在此刻红了一次，说的就是「你豁免的那件事已经不在这里了」。清空即结清。
#: ★留下空表而不是删掉机制：下一条豁免仍要走同一条纪律。
KNOWN_MISSING: dict[str, str] = {}


def _missing_names(src: Path) -> list[tuple[str, str]]:
    """``[(key, message)]`` for every ``from fylite… import x`` in *src* that
    names something which is not there."""
    out = []
    for node in ast.walk(ast.parse(src.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.ImportFrom) or node.level:
            continue
        mod_name = node.module or ""
        if not mod_name.startswith("fylite"):
            continue
        try:
            mod = importlib.import_module(mod_name)
        except Exception:                        # noqa: BLE001 — not our subject
            continue
        for a in node.names:
            if a.name == "*" or hasattr(mod, a.name):
                continue
            try:                                 # a submodule, not an attribute
                importlib.import_module(f"{mod_name}.{a.name}")
            except Exception:                    # noqa: BLE001
                out.append((f"{mod_name}.{a.name}",
                            f"{src.name}:{node.lineno} {mod_name} has no "
                            f"{a.name!r}"))
    return out


@pytest.mark.parametrize("src", TOOLS, ids=lambda p: f"tools/{p.name}")
def test_tools_import_names_that_exist(src: Path):
    """Every ``from fylite… import x`` in a tool names something that is
    there.  Static: no tool is executed, and a module that cannot be imported
    at all (an optional dependency) is skipped rather than blamed."""
    unexpected = [m for key, m in _missing_names(src)
                  if f"tools/{src.name}:{key}" not in KNOWN_MISSING]
    assert not unexpected, "\n  ".join(
        ["names that are not there:"] + unexpected)


def test_every_missing_name_waiver_is_still_missing():
    """★A waiver that quietly starts passing keeps a fixed defect on the books
    and hides the next one behind it."""
    found = {f"tools/{src.name}:{key}"
             for src in TOOLS for key, _ in _missing_names(src)}
    stale = sorted(set(KNOWN_MISSING) - found)
    assert not stale, (
        f"waived but no longer missing: {stale} — drop the waiver, or fix the "
        "detector if it stopped looking.")


def test_a_waived_import_degrades_rather_than_killing_its_tool():
    """★★A waiver describes how far the damage goes, and that description has
    to be true.

    ``tools/make-east-inputs.py`` waives ``fylite.circuits`` with「this
    branch raises rather than running」— and the import sat ABOVE the guard,
    so calling ``passive_from`` raised ``ImportError`` and the whole tool
    died on ``main``'s fourth statement.  The gates above are static (no tool
    is executed), so nothing noticed: the waiver was checked, its SCOPE was
    not.

    This runs the waived function.  It must come back with the degraded
    answer its own message promises, not raise.
    """
    import importlib.util

    src = PKG.parents[1] / "tools" / "make-east-inputs.py"
    if not src.is_file():
        pytest.skip("tools/ 已移出本仓；这条闸跟着它走的那个豁免一起结清了")
    spec = importlib.util.spec_from_file_location("_east_inputs", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    got = mod.passive_from(PKG.parents[1] / "machine_desc/east", {})
    assert isinstance(got, list), (
        "the waived branch no longer degrades — if `circuits` came back, "
        "drop the waiver; if it changed shape, this gate needs to know")


@pytest.mark.parametrize("src", TOOLS, ids=lambda p: f"tools/{p.name}")
def test_tool_calls_fit_the_signature_they_call(src: Path):
    rel = f"tools/{src.name}"
    unexpected = [m for alias, m in _scan(src, pkg="", rel=rel)
                  if f"{rel}:{alias}" not in KNOWN_BROKEN]
    assert not unexpected, (
        "call sites that do not fit the signature they call:\n  "
        + "\n  ".join(unexpected))
