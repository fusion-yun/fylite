"""`CONTRIBUTORS.md` is an address, a licence file, and half of a pair.

★★Why this exists.  Three different things depend on this one file, and each
of them breaks **silently** when it drifts:

1. **SECURITY.md sends people here for an address.**  Strip the addresses (or
   the section heading they live under) and the security-report path dead-ends
   at a file that still reads fine.
2. **It ships.**  `pyproject.toml` lists it in `license-files`, so a copy goes
   out inside every wheel — which puts it under SECURITY.md's published-artifact
   rule: no operator-internal address, no builder home path.
3. **`fylite_kernel/NOTICE` points at it** ("Contributors are listed in
   CONTRIBUTORS.md") and that repository carries its own copy.  Two copies of
   one list is two chances to be wrong about who maintains this.

★Measured 2026-09-02, and the reason for the rewrite this gate accompanies:
the file said "licensed under the Apache License 2.0 (see `LICENSE` and
`NOTICE`)" while **`NOTICE` had been removed from this repository** (095374f) —
a licence pointer into nothing, in a file that goes out in the wheel.  Nothing
failed, because nothing was looking.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "CONTRIBUTORS.md"

#: `- Zhi YU (ASIPP) — <yuzhi@ipp.ac.cn>`
_ENTRY = re.compile(r"^-\s+(?P<name>[^(]+?)\s*\((?P<org>[^)]+)\)\s*[—-]\s*"
                    r"<(?P<mail>[^@<>\s]+@[^@<>\s]+\.[a-z]+)>\s*$", re.M)
#: a Markdown link to a path in this tree (not a URL, not a mailto, not an anchor)
_LINK = re.compile(r"\]\((?!https?:|mailto:|#)([^)\s#]+)\)")


@pytest.fixture(scope="module")
def text() -> str:
    assert FILE.is_file(), "CONTRIBUTORS.md is gone; SECURITY.md points at it"
    return FILE.read_text(encoding="utf-8")


def _maintainers(body: str) -> list[tuple[str, str, str]]:
    """The entries under the maintainers heading, in file order."""
    m = re.search(r"^##\s+.*Maintainers\s*$(.*?)(?=^##\s|\Z)", body, re.M | re.S)
    return _ENTRY.findall(m.group(1)) if m else []


def test_the_security_contact_resolves_to_an_address(text):
    """★The coupling SECURITY.md declares, checked from this end.

    It says 「发邮件给维护者（见 CONTRIBUTORS.md）」 — that sentence is only
    true while this file still has a section a reader can find and an address
    they can write to."""
    sec = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "CONTRIBUTORS.md" in sec, \
        "SECURITY.md no longer sends reporters here — one of the two moved"
    people = _maintainers(text)
    assert people, ("no maintainer entry parsed under the maintainers heading; "
                    "SECURITY.md's report path ends here, so an empty or "
                    "reshaped list is a broken security contact, not a typo")
    for name, org, mail in people:
        assert "  " not in name, f"{name!r} carries a doubled space"
        assert name.strip() == name and org.strip() == org


def test_it_carries_nothing_a_published_file_must_not(text):
    """★It goes out in the wheel (`license-files`), so the rule SECURITY.md
    states for published artifacts applies to it verbatim."""
    #: a dotted quad whose four parts are all valid octets.  A four-part
    #: version string would trip this too — that is the intended trade: this
    #: file has no reason to carry either, and a false positive costs one line
    #: of prose while a missed address costs a published operator address.
    ips = [s for s in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text)
           if all(int(part) < 256 for part in s.split("."))]
    assert not ips, f"an IPv4 literal in a file that ships: {ips}"
    homes = re.findall(r"/home/[A-Za-z0-9_.-]+/", text)
    assert not homes, f"a builder home path in a file that ships: {homes}"


def test_every_path_it_names_is_in_this_checkout(text):
    """★★The exact defect that prompted the rewrite: `see LICENSE and NOTICE`
    where NOTICE had left the repository.  A licence file may **describe** a
    document that lives elsewhere — this one does, at length — but it may not
    LINK to it as though a reader could open it here."""
    missing = [t for t in _LINK.findall(text) if not (ROOT / t).exists()]
    assert not missing, (
        f"CONTRIBUTORS.md links to paths this checkout does not have: {missing}. "
        "If the file legitimately lives elsewhere (NOTICE does — it stays with "
        "the kernel sources), say where in prose instead of linking to it.")


def test_the_claim_that_it_ships_is_still_true(text):
    """★It tells the reader it goes out in the wheel and is therefore held to
    the published-artifact rule.  Two things make that true, and both are
    somewhere else: the `license-files` entry, and the symlink that puts it
    inside the project directory where setuptools can resolve that entry."""
    proj = ROOT / "python"
    toml = (proj / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"^license-files\s*=\s*\[(.*?)\]", toml, re.M | re.S)
    assert m and "CONTRIBUTORS.md" in m.group(1), \
        "license-files no longer lists CONTRIBUTORS.md — it stopped shipping"
    link = proj / "CONTRIBUTORS.md"
    assert link.is_symlink() and (link.resolve() == FILE.resolve()), \
        ("python/CONTRIBUTORS.md must be a symlink to the repo-root file — "
         "setuptools resolves license-files only inside the project directory, "
         "and a second real copy is a second thing to keep true")


#: ★the kernel checkout is optional here (its sources are a separate repo).
#: Probing and skipping by name is the rule this tier already follows for the
#: NOTICE and the app provenance ledger: absence gets declared, not assumed.
def _kernel() -> Path | None:
    cands = ([Path(os.environ["FYLITE_KERNEL"])] if os.environ.get("FYLITE_KERNEL")
             else [ROOT.parent / "fylite_kernel", ROOT.parent / "fylite_dev"])
    for c in cands:
        if (c / "CONTRIBUTORS.md").is_file():
            return c
    return None


def test_the_kernel_copy_names_the_same_people(text):
    """★★Two copies, one list.  `fylite_kernel/NOTICE` says "Contributors are
    listed in CONTRIBUTORS.md", so the two files answer the same question in
    two trees — and a maintainer added, removed or re-addressed in one of them
    only is a file that lies.

    ★What is compared is the LIST and the copyright sentence, **not the whole
    file**: the pointer sections legitimately differ, because NOTICE is present
    in one tree and absent from the other, and only the public tree has
    SECURITY.md and the issue templates.  Byte-equality here would force one of
    the two copies to describe files it does not have."""
    k = _kernel()
    if k is None:
        pytest.skip("no fylite_kernel checkout found; set $FYLITE_KERNEL to one "
                    "to compare the two CONTRIBUTORS.md")
    other = (k / "CONTRIBUTORS.md").read_text(encoding="utf-8")
    assert _maintainers(text) == _maintainers(other), {
        "here": _maintainers(text), str(k): _maintainers(other)}
    here, there = (re.search(r"fylite is developed by[^.]+\.", b, re.S)
                   for b in (text, other))
    assert here and there, "the English copyright sentence changed shape"
    norm = lambda s: " ".join(s.group(0).split())
    assert norm(here) == norm(there), {"here": norm(here), str(k): norm(there)}
