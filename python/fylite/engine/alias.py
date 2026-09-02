"""A-5 — a readable name for a run, BESIDE its id and never instead of it.

★★Run ids are second-stamped (``r-20260826-233442``) because they have to be
unique and mintable without asking anybody.  They are also unreadable, and a
session with a dozen of them is a list nobody can hold in their head.  So a
run may be given a name — ``iter-burn@v1`` — and the register maps that name
to the id.

★What this deliberately does NOT do is replace the id.  A handle stays
``fylite://<run-id>/<port>``: the id is what the ledger's edges are drawn
between, what a manifest records, and what :mod:`fylite.engine.whence`
resolves back to.  An alias is a second way to SAY a run, and a second way to
say something must never become a second thing to keep in step — so the
register stores one direction (name → id) and everything else keeps reading
the id.

Two rules, and they are the whole of A-5's criterion:

* **A conflict is an error.**  Re-pointing a name that is already taken at a
  different run raises.  A register that silently re-pointed would make
  ``iter-burn@v1`` mean one run in a note and another in a script — the exact
  failure a readable name is supposed to prevent.
* **An anonymous run is not registered.**  A name is given deliberately or
  not at all; there is no derived-from-something default.  A register that
  filled itself would be a list of names nobody chose, and a name nobody
  chose is not more readable than an id.

The version suffix is the register's, not the caller's: ask for ``iter-burn``
and get ``iter-burn@v1``, ask again for a different run and get ``@v2``.  A
caller that names a run twice by the same name means the second one is a new
version of the same thing, which is the case the suffix exists for.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import handles

__all__ = ["REGISTER", "NAME_RE", "register", "resolve", "listing",
           "AliasError"]

#: where the register lives — one file per run root, beside the sessions
REGISTER = "aliases.json"

#: ★a name is lower-case letters, digits and dashes.  Narrow on purpose: the
#: alias appears in shell commands and in prose, and a name needing quotes is
#: not the readable thing this exists to provide.  ★`@` is excluded so a name
#: can never contain its own version separator.
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

_VERSIONED = re.compile(r"^(?P<name>[a-z][a-z0-9-]{0,63})@v(?P<v>[1-9]\d*)$")


class AliasError(ValueError):
    """A name that cannot be registered, or a conflict."""


def _path(root=None) -> Path:
    return (Path(root) if root else handles.runs_root()) / REGISTER


def _load(root=None) -> dict:
    p = _path(root)
    if not p.is_file():
        return {}
    try:
        got = json.loads(p.read_text())
    except Exception as e:                       # noqa: BLE001
        raise AliasError(f"{p} is not readable as a register: {e}") from e
    return got if isinstance(got, dict) else {}


def register(run_id: str, name: str, *, root=None) -> str:
    """Give ``run_id`` the readable name ``name``; return ``name@vN``.

    Raises :class:`AliasError` for a name that is not registrable, and for a
    version that is already taken by a different run.
    """
    if name is None or not str(name).strip():
        raise AliasError(
            "a run is named deliberately or not at all — there is no derived "
            "default, because a name nobody chose is not more readable than "
            "the id it replaces")
    name = str(name).strip()
    if _VERSIONED.match(name):
        raise AliasError(
            f"give the NAME ({name.split('@')[0]!r}); the version is the "
            "register's to assign, so that asking twice means a second "
            "version rather than a silent overwrite")
    if not NAME_RE.match(name):
        raise AliasError(
            f"{name!r} is not a usable alias: lower-case letters, digits and "
            "dashes, starting with a letter, at most 64 characters — a name "
            "that needs quoting in a shell is not the readable thing an "
            "alias is for")
    #: ★the run must EXIST.  A register that accepted a name for a run that
    #: is not there would hand out a readable name that resolves to nothing,
    #: and the reader would find that out at the point of use.
    handles.find_run(run_id)

    reg = _load(root)
    versions = reg.setdefault(name, {})
    for tag, rid in sorted(versions.items()):
        if rid == run_id:
            return f"{name}@{tag}"               # idempotent, not a conflict
    tag = f"v{len(versions) + 1}"
    #: ★reachable, not defensive: a register with a GAP (a hand edit, a
    #: half-merge) computes a next tag that is already in use, and `name@vN`
    #: is immutable — a register that silently re-pointed would make one
    #: alias mean one run in a note and another in a script.
    if tag in versions:
        raise AliasError(
            f"{name}@{tag} is already taken by {versions[tag]}; an alias "
            "never changes what it points at")
    versions[tag] = run_id
    p = _path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(reg, indent=1, sort_keys=True) + "\n")
    return f"{name}@{tag}"


def resolve(alias: str, *, root=None) -> str:
    """``name@vN`` -> run id.  A bare ``name`` resolves to its LATEST version.

    ★The bare form is a convenience with a stated rule, not a guess: it means
    "the newest thing called that".  Anything wanting a fixed target says the
    version, and the ledger and the manifests only ever hold ids.
    """
    reg = _load(root)
    m = _VERSIONED.match(str(alias))
    if m:
        versions = reg.get(m.group("name")) or {}
        rid = versions.get("v" + m.group("v"))
        if rid is None:
            raise AliasError(f"no run registered as {alias!r}")
        return rid
    versions = reg.get(str(alias)) or {}
    if not versions:
        raise AliasError(
            f"no run registered as {alias!r} — names are given with "
            "`register`, never derived")
    newest = max(versions, key=lambda t: int(t[1:]))
    return versions[newest]


def listing(*, root=None) -> dict:
    """``{name@vN: run id}`` for every registered alias, sorted."""
    reg = _load(root)
    return {f"{name}@{tag}": rid
            for name in sorted(reg)
            for tag, rid in sorted(reg[name].items(),
                                   key=lambda kv: int(kv[0][1:]))}
