"""A-5 — a readable name for a run, beside its id and never instead of it.

Run ids are second-stamped because they must be unique and mintable without
asking anybody; they are also unreadable.  An alias is a second way to SAY a
run — and these gates hold the line that makes that safe: a second way to say
something must never become a second thing to keep in step.
"""
from __future__ import annotations

import json

import pytest

from fylite.engine import alias as A
from fylite.engine import handles


@pytest.fixture()
def runs(tmp_path, monkeypatch):
    monkeypatch.setenv(handles.RUN_ENV, str(tmp_path / "runs"))
    monkeypatch.setenv(handles.SESSION_ENV, "s-alias")
    made = [handles.new_run(), handles.new_run()]
    return tmp_path / "runs", [p.name for p in made]


def test_a_name_gets_a_version_and_resolves_back(runs):
    root, (a, b) = runs
    assert A.register(a, "iter-burn") == "iter-burn@v1"
    assert A.resolve("iter-burn@v1") == a
    #: the bare form means「最新的那个」, a stated rule rather than a guess
    assert A.resolve("iter-burn") == a
    assert A.register(b, "iter-burn") == "iter-burn@v2"
    assert A.resolve("iter-burn@v1") == a
    assert A.resolve("iter-burn") == b


def test_naming_the_same_run_twice_is_idempotent_not_a_second_version(runs):
    """★Asking again for a name a run already has is not a new version of
    anything — it is the same statement made twice, and a register that
    minted `@v2` for it would make the version number mean「有人问了几次」."""
    root, (a, _) = runs
    assert A.register(a, "iter-burn") == "iter-burn@v1"
    assert A.register(a, "iter-burn") == "iter-burn@v1"
    assert list(A.listing()) == ["iter-burn@v1"]


def test_a_taken_version_pointing_elsewhere_is_a_conflict(runs):
    """★★A-5's first criterion.  `name@vN` is immutable once assigned: a
    register that silently re-pointed would make one alias mean one run in a
    note and another in a script — precisely the failure a readable name
    exists to prevent.  ★The case is reachable (a hand-edited or
    half-merged register), so it is built rather than assumed."""
    root, (a, _) = runs
    #: a register with a GAP, as a hand edit or a half-merge leaves it.  The
    #: existing entries need not be real runs — nothing looks them up — but
    #: the run being named must be, which is why `a` is used for that.
    (root / A.REGISTER).write_text(json.dumps(
        {"iter-burn": {"v1": "r-older-1", "v3": "r-older-2"}}))
    #: two versions present, so the next tag computes to v3 — already taken,
    #: by a different run
    with pytest.raises(A.AliasError, match="already taken"):
        A.register(a, "iter-burn")


def test_an_anonymous_run_is_not_registered(runs):
    """★★A-5's second criterion.  A name is given deliberately or not at
    all: there is no derived default, because a name nobody chose is not
    more readable than the id it stands for."""
    root, (a, _) = runs
    for bad in (None, "", "   "):
        with pytest.raises(A.AliasError, match="deliberately or not at all"):
            A.register(a, bad)
    assert not (root / A.REGISTER).exists(), "a refusal must write nothing"
    assert A.listing() == {}


@pytest.mark.parametrize("bad", ["Iter", "2fast", "has space", "wat?",
                                 "x" * 65, "with@sign"])
def test_a_name_that_is_not_readable_is_refused(runs, bad):
    """★The point is a name a person can type and read aloud; one that needs
    quoting in a shell is not that.  ★`@` is refused so a name can never
    contain its own version separator."""
    root, (a, _) = runs
    with pytest.raises(A.AliasError):
        A.register(a, bad)


def test_the_version_is_the_registers_to_assign(runs):
    """★A caller that could pick the version could overwrite one."""
    root, (a, _) = runs
    with pytest.raises(A.AliasError, match="register's to assign"):
        A.register(a, "iter-burn@v7")


def test_a_name_for_a_run_that_does_not_exist_is_refused(runs):
    """★Otherwise the register hands out a readable name that resolves to
    nothing, and the reader finds out at the point of use."""
    with pytest.raises(LookupError):
        A.register("r-not-a-run", "ghost")
    assert A.listing() == {}


def test_an_unregistered_name_says_so_rather_than_guessing(runs):
    with pytest.raises(A.AliasError, match="never derived"):
        A.resolve("nobody-named-this")


def test_the_id_wins_over_an_alias_of_the_same_spelling(runs, tmp_path,
                                                        monkeypatch):
    """★★The line that makes an alias safe: the ID IS THE IDENTITY.  A run
    whose id is present must resolve to it even if some alias happens to be
    spelled the same, or the ledger's edges and the register could disagree
    about what a name means."""
    root, (a, b) = runs
    #: give run `b` an alias spelled exactly like run `a`'s id — only
    #: possible because ids are not in the alias namespace, which is the
    #: point: the register must not be able to shadow one
    (root / A.REGISTER).write_text(json.dumps({"shadow": {"v1": b}}))
    assert handles.find_run(a).name == a
    #: and the alias still works under its own name
    assert handles.find_run("shadow@v1").name == b


def test_find_run_resolves_a_registered_name(runs):
    root, (a, _) = runs
    A.register(a, "iter-burn")
    assert handles.find_run("iter-burn@v1").name == a
    assert handles.find_run("iter-burn").name == a


def test_an_unknown_name_still_reports_the_run_root(runs):
    """★The failure has to say what was searched — a name that was never
    registered and a run root that was cleaned are different problems."""
    with pytest.raises(LookupError, match="never been registered|no run"):
        handles.find_run("no-such-thing")


