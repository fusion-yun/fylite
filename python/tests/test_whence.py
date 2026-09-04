"""A-4 — a file, traced back to the run that made it.

★★The register went one way: a run writes a manifest naming its artefacts,
and nothing could take an artefact and get back to the run.  That gap is felt
exactly when it matters — somebody has a `result.json` in a directory, or a
deck a colleague forwarded, and the question is「这是哪次跑出来的、喂给它的是
什么」.

★The lookup is BY CONTENT and these gates hold that, because it is the whole
difference between an answer and a guess: reading the path would "resolve" a
file that had been copied into the wrong place and would fail on one that was
renamed.  The path is only a hint that saves a sweep.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from fylite.engine import whence as W


@pytest.fixture()
def a_run(tmp_path, monkeypatch):
    monkeypatch.setenv("FYLITE_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("FYLITE_SESSION", "wh")
    from fylite.engine import cases
    r = cases.run("evolve-default")
    return tmp_path, Path(r["run_dir"])


def test_an_artifact_in_place_names_its_run_and_its_lineage(a_run):
    root, rd = a_run
    rec = W.whence(rd / "result.json", root=root)
    assert rec["found"], rec
    assert rec["run"] == rd.name and rec["session"] == "wh"
    assert rec["tool"] == "fylite_evolve"
    assert rec["artifact"] == "result.json"
    #: the one line A-4 asks for, with the run, the tool and the code rev on it
    assert rd.name in rec["line"] and "fylite_evolve" in rec["line"]
    assert rec["code"] and rec["code"] in rec["line"]
    #: ★A-3's host travels with it, so a line says which build produced the file
    assert rec["host"] == "native"


def test_a_copied_and_renamed_artifact_still_resolves(a_run, tmp_path):
    """★★The point of hashing rather than reading the path.  A file that has
    been sent on, renamed, and stripped of its directory is exactly the file
    somebody needs this command for."""
    root, rd = a_run
    away = tmp_path / "elsewhere"
    away.mkdir()
    out = away / "somebody-sent-me-this.json"
    shutil.copy(rd / "result.json", out)
    rec = W.whence(out, root=root)
    assert rec["found"], rec
    assert rec["run"] == rd.name
    #: the artefact is named by what the RUN called it, not by the copy's name
    assert rec["artifact"] == "result.json"


def test_a_modified_artifact_is_not_found_and_that_is_the_answer(a_run,
                                                                 tmp_path):
    """★Not a near-miss, not the run it used to belong to.  Once the bytes
    change it is no longer the artefact that run produced, and saying so is
    the honest result — a lookup that answered anyway would attach a run's
    provenance to numbers that run never wrote."""
    root, rd = a_run
    out = tmp_path / "bent.json"
    raw = (rd / "result.json").read_bytes()
    out.write_bytes(raw[:-1] + b"  ")
    rec = W.whence(out, root=root)
    assert not rec["found"]
    assert rec["line"] and "these bytes" in rec["line"]
    #: ★and it still tells the caller what it hashed, so the miss is checkable
    assert rec["sha256"] and rec["sha256"] != W.whence(rd / "result.json",
                                                       root=root)["sha256"]


def test_a_file_dropped_into_a_run_directory_is_not_adopted_by_it(a_run):
    """★★The path is a HINT, never the answer.  A file sitting inside a run
    directory that the run did not write must not inherit its provenance —
    that is the failure mode a path-based lookup has and a content-based one
    does not."""
    root, rd = a_run
    stray = rd / "result.json.bak"
    stray.write_text('{"not": "an artefact of this run"}')
    rec = W.whence(stray, root=root)
    assert not rec["found"], rec


def test_the_lineage_names_the_upstream_run(tmp_path, monkeypatch):
    """★★The other half of「一行谱系」: not just which run, but what fed it.

    ★The chain is BUILT here — one call handed the other's handle — rather
    than hoped for in whatever the corpus happens to record.  The first
    version of this gate skipped itself when no chain turned up, and the
    skip hid a real defect: `_lineage` was reading `source`/`target` while
    `ledger.record` writes `source_node`/`target_node`, so `upstream` was
    always empty and every assertion about its shape still passed.
    """
    import json as _json

    from fylite.engine import handles, serve

    monkeypatch.setenv(handles.RUN_ENV, str(tmp_path / "runs"))
    monkeypatch.setenv(handles.SESSION_ENV, "s-whence")

    def call(name, args):
        r = serve.call_mcp_tool(name, args)
        assert r["isError"] is False, r["content"][0]["text"]
        return _json.loads(r["content"][0]["text"])

    a = call("fylite_zerod", {})
    b = call("fylite_transport", {"power": 4.0,
                                  "y_init": {"$ref": a["te"]["ref"]}})
    root = tmp_path / "runs"
    downstream = W.whence(root / "s-whence" / b["run"] / "result.json",
                          root=root)
    assert downstream["found"], downstream
    assert downstream["upstream"] == [a["run"]], downstream
    assert a["run"] in downstream["line"]

    #: ★and the run at the head of the chain says it has none, rather than
    #: silently reporting the same empty list a broken reader would
    upstream = W.whence(root / "s-whence" / a["run"] / "result.json",
                        root=root)
    assert upstream["found"] and upstream["upstream"] == []
    assert "no upstream run" in upstream["line"]


def test_a_run_root_that_does_not_exist_says_so(tmp_path):
    """★A missing root is a different answer from a missing file, and the
    two must not read the same: one means「没记过」, the other means「记过，
    但不是这份」."""
    f = tmp_path / "x.json"
    f.write_text("{}")
    rec = W.whence(f, root=tmp_path / "no-such-root")
    assert not rec["found"]
    assert "not a run root" in rec["note"]


def test_a_file_that_is_not_there_raises_rather_than_reporting_not_found():
    """★A path that does not exist is the CALLER's mistake, and it must not
    come back looking like「这份产物没有出处」."""
    with pytest.raises(FileNotFoundError):
        W.whence("/definitely/not/here.json")


