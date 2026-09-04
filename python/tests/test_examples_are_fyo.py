"""``examples/`` carries SPECS and fyo documents — never a solver deck.

★**Why a machine check and not a line in the README.**  The rule this file
enforces was already the repository's stated policy: ``README.md`` says the
distribution contains "no experimental data" and "no EFIT-lineage code or
recorded output", and ``machine_desc/README.md`` draws the line between what the
package publishes and what it merely takes as input.  ``examples/`` had
223 KB of data in it anyway, 204 KB (91.6 %) of which was byte-identical to
the private ``fylite_port`` tree — a converged g-file (twice), its a-file and
its run summary.  Nobody put them there in defiance of the policy; the policy
simply had no way to notice.

So the three checks below are the policy, executable:

  1. no file under ``examples/`` is named like a solver deck or a shot;
  2. every data file under ``examples/`` parses as JSON-LD and says what it is;
  3. every ``storage_uri`` in every case manifest either resolves in the tree
     or declares the environment variable it is resolved through.

★Check 3 is the one that keeps the first two honest.  Deleting the decks is
easy; the failure mode is a case that still NEEDS them and now names a path
nobody can resolve — which is exactly what the tests inherited from
``examples/scripts/g137985_loop.04000``, a literal path that had not existed
in this repository at all.  A case must be able to say "my input is not in
this tree, here is how you point at it".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


#: ★★★空语料时 pytest 仍会为 `parametrize([])` 造一个「跳过」用例，并拿一个
#: 占位值来问它的 id——id 函数若在那上面抛异常，整个模块就**收集失败**。
#: 而「收集失败」与「语料不在」是两回事：后者本模块已经用 skipif 说清楚了，
#: 前者会让人以为判据坏了。所以 id 函数对拿不准的值给个名字，不抛。
def _pid(p, sep="/") -> str:
    return f"{p.parent.name}{sep}{p.name}" if isinstance(p, Path) else "no-corpus"



ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"

#: Files that are code or prose, not data.  Everything else under
#: ``examples/`` has to be a document.
_NOT_DATA = {".py", ".md", ".ipynb", ".txt", ".gitignore"}

#: ★A solver deck by its NAME, which is how these files arrive: ``g<shot>``,
#: ``a<shot>``, ``summary_<shot>``, or the ``.0<itime_ms>`` suffix EFIT gives
#: its output.  Naming is enough here and content sniffing is not needed: a
#: g-file that arrived under some other name still fails check 2, because it
#: is not JSON.
_DECK = re.compile(r"(^[gam]\d{6})|(^summary_\d{6})|(\.0\d{4}$)")


def _tracked() -> list[Path]:
    """Everything under ``examples/``, excluding run output.

    ★Walked rather than asked of git: the check has to hold for a working
    tree, not only for what someone remembered to commit.  A g-file dropped
    in for one afternoon's debugging is exactly the case that later gets
    committed by accident.
    """
    return [p for p in sorted(EXAMPLES.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts]


#: ★★2026-09-01：`examples/` 随算例语料一起移出本仓（在 fylite_kernel）。
#: 这道闸走工作树拒绝「实验炮文件出现在 examples/ 下」——树不在，它就无事可判。
pytestmark = pytest.mark.skipif(
    not (ROOT / "examples").is_dir(),
    reason="examples/ 已移出本仓（在 fylite_kernel）；这道闸随它走")


def test_no_solver_deck_or_shot_file_lives_under_examples():
    """★This found four files when it was written: two copies of
    ``g137985_loop.04000`` (99,970 B each), ``a137985_loop.04000`` and
    ``summary_137985_loop.json`` — all byte-identical to ``fylite_port``,
    which is proprietary and whose repository must stay private."""
    bad = [p.relative_to(ROOT) for p in _tracked() if _DECK.search(p.name)]
    assert not bad, (
        "solver decks / shot files under examples/: "
        + ", ".join(map(str, bad))
        + ".  A case's SPEC lives here; the shot's own numbers are machine "
          "data and live behind $FYLITE_DEVICE_DIR (tools/case-to-fyo.py "
          "converts a delivered g/a pair into the documents that go there).")


def test_every_data_file_under_examples_is_a_semantic_document():
    """JSON is not enough: a document has to say what it is.

    ``summary_137985_loop.json`` was valid JSON and carried no ``@context``
    and no ``@type`` — so a reader could parse every number in it and learn
    nothing about which quantity, which units, or which run.
    """
    for p in _tracked():
        if p.suffix in _NOT_DATA:
            continue
        assert p.suffix in (".json", ".jsonld"), \
            f"{p.relative_to(ROOT)}: not a document (expected .json/.jsonld)"
        doc = json.loads(p.read_text())
        assert "@context" in doc, f"{p.relative_to(ROOT)}: no @context"
        assert "@type" in doc, f"{p.relative_to(ROOT)}: no @type"
        assert doc["@context"].get("fyo") == \
            "https://fusion-yun.github.io/fyo/latest/", \
            f"{p.relative_to(ROOT)}: wrong or missing fyo IRI"


def _cases() -> list[Path]:
    return sorted(EXAMPLES.glob("*/case.fyo.jsonld"))


def test_there_are_case_manifests_to_check():
    """A guard on the guards: an empty glob passes every parametrised check
    below and reads as green."""
    assert len(_cases()) >= 5


@pytest.mark.parametrize("case", _cases(), ids=lambda p: _pid(p).split("/")[0])
def test_case_manifest_is_well_formed(case: Path):
    doc = json.loads(case.read_text())
    assert doc["@id"] == f"fylite:examples/{case.parent.name}"
    assert doc["@context"]["fyo"] == "https://fusion-yun.github.io/fyo/latest/"
    assert doc["@context"]["fylite"] == "urn:fylite:"
    ports = doc["fylite:ports"]
    assert ports["in"] and ports["out"]
    for side in ("in", "out"):
        for port in ports[side]:
            assert port["port_id"] and port["label"]
            assert str(port["data_type"]).startswith(("fyo:", "sp:")), \
                f"{case.parent.name}/{port['port_id']}: {port['data_type']}"
    assert doc.get("fylite:notes"), f"{case.parent.name}: no honest boundary"


@pytest.mark.parametrize("case", _cases(), ids=lambda p: _pid(p).split("/")[0])
def test_every_input_uri_resolves_or_declares_how_to_resolve_it(case: Path):
    """An input is EITHER in the tree beside the case OR names its variable.

    ★The third possibility — a path that is neither — is the one that has to
    be impossible, because it does not fail: ``conftest.east_case`` pointed
    at ``examples/scripts/g137985_loop.04000`` for months and every test that
    needed it SKIPPED, quietly, with a reason that named a real-sounding
    file.
    """
    doc = json.loads(case.read_text())
    for port in doc["fylite:ports"]["in"]:
        uri = port["storage_uri"]
        if uri.startswith("$"):
            var = port.get("fylite:external")
            assert var, f"{case.parent.name}/{port['port_id']}: $-uri with no " \
                        f"fylite:external naming the variable"
            assert uri.startswith(f"${var}"), \
                f"{case.parent.name}/{port['port_id']}: {uri} vs ${var}"
            continue
        if "://" in uri:                      # a service, not a file
            assert port.get("fylite:external"), \
                f"{case.parent.name}/{port['port_id']}: {uri} names no variable"
            continue
        target = (case.parent / uri).resolve()
        assert target.exists(), \
            f"{case.parent.name}/{port['port_id']}: {uri} resolves to nothing"


@pytest.mark.parametrize("case", _cases(), ids=lambda p: _pid(p).split("/")[0])
def test_declared_hashes_match_the_files_they_name(case: Path):
    """A hash that is not checked is decoration.

    ★The old manifests declared ``storage_hash`` for three files and nothing
    ever compared them — including for the two copies of the same g-file,
    which is precisely where a declared hash would have earned its place.
    """
    import hashlib
    doc = json.loads(case.read_text())
    for port in doc["fylite:ports"]["in"] + doc["fylite:ports"]["out"]:
        want = port.get("storage_hash")
        if not want:
            continue
        p = case.parent / port["storage_uri"]
        assert p.is_file(), f"{case.parent.name}: hashed file {p} is absent"
        got = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
        assert got == want, f"{case.parent.name}/{port['port_id']}: {got} != {want}"
