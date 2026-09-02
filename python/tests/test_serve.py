"""``fylite serve`` — the JSON-RPC 2.0 stdio face (SP-REPORT-15 T-1.6).

Drives :func:`fylite.engine.handle_rpc_request` in-process (it is pure), the
:func:`fylite.engine.serve_stdio` line loop through StringIO, and one real subprocess
through the CLI.  Also pins the T-1.4 wiring facts: ``run()`` infers the
``imas`` mode for ``.jsonld`` input and funnels it through the semantic
interpreter.
"""
from __future__ import annotations

import json
import io
import subprocess
import sys

import numpy as np
import pytest

from fylite import engine, fyo
from fylite.scenario.analysis.recon_rs import _infer_kind


def _req(method, params=None, rid=1):
    r = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        r["params"] = params
    return r


# --------------------------------------------------------------------------- #
# handle_request
# --------------------------------------------------------------------------- #

def test_describe_returns_the_catalog():
    resp = engine.handle_rpc_request(_req("fylite.describe"))
    assert resp["id"] == 1
    assert resp["result"] == engine.manifest_catalog()


def test_manifest_by_name_and_unknown_name():
    ok = engine.handle_rpc_request(_req("fylite.manifest", {"name": "efit"}))
    assert ok["result"]["@id"] == "fylite:efit"
    bad = engine.handle_rpc_request(_req("fylite.manifest", {"name": "nope"}))
    assert bad["error"]["code"] == -32602
    assert "efit" in bad["error"]["data"]["known"]


def test_unknown_method_and_invalid_request():
    assert engine.handle_rpc_request(_req("fylite.nope"))["error"]["code"] == -32601
    assert engine.handle_rpc_request({"id": 1})["error"]["code"] == -32600
    bad_params = engine.handle_rpc_request(
        {"jsonrpc": "2.0", "id": 1, "method": "fylite.describe", "params": []})
    assert bad_params["error"]["code"] == -32602


def test_invoke_calls_a_fylite_entry():
    resp = engine.handle_rpc_request(_req(
        "fylite.invoke",
        {"entry": "fylite.engine:strip_semantic",
         "kwargs": {"obj": {"@id": "x", "a": 1}}}))
    assert resp["result"] == {"a": 1}


def test_invoke_rejects_non_fylite_entries():
    resp = engine.handle_rpc_request(_req(
        "fylite.invoke", {"entry": "os:system", "kwargs": {}}))
    assert resp["error"]["code"] == -32602


def test_invoke_failure_becomes_a_typed_fault():
    resp = engine.handle_rpc_request(_req(
        "fylite.invoke",
        {"entry": "fylite.fyo:as_measurements",
         "kwargs": {"obj": 42, "time_s": 0.0}}))
    assert resp["error"]["code"] == -32000
    assert resp["error"]["data"]["type"] == "TypeError"


def test_results_are_json_sanitized():
    out = engine.json_sanitize({"a": np.float64(1.5), "b": np.arange(3),
                           "c": {1: object()}})
    assert out["a"] == 1.5 and out["b"] == [0, 1, 2]
    assert isinstance(out["c"]["1"], str)
    json.dumps(out)  # must not raise


# --------------------------------------------------------------------------- #
# line loop + subprocess
# --------------------------------------------------------------------------- #

def test_main_serves_lines_and_reports_parse_errors():
    lines = "\n".join([
        json.dumps(_req("fylite.describe")),
        "not json",
        json.dumps(_req("fylite.manifest", {"name": "neo"}, rid=2)),
    ]) + "\n"
    out = io.StringIO()
    assert engine.serve_stdio(stdin=io.StringIO(lines), stdout=out) == 0
    r1, r2, r3 = [json.loads(x) for x in out.getvalue().splitlines()]
    assert r1["result"]["@id"] == "fylite:catalog"
    assert r2["error"]["code"] == -32700
    assert r3["result"]["@id"] == "fylite:neo"


def test_cli_serve_subprocess_round_trip():
    proc = subprocess.run(
        [sys.executable, "-m", "fylite", "serve"],
        input=json.dumps(_req("fylite.describe")) + "\n",
        capture_output=True, text=True, timeout=120,
        env={"PYTHONPATH": "python", "PATH": "/usr/bin:/bin"},
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]))
    assert proc.returncode == 0, proc.stderr
    resp = json.loads(proc.stdout.splitlines()[0])
    assert resp["result"]["@id"] == "fylite:catalog"


# --------------------------------------------------------------------------- #
# T-1.4 wiring facts
# --------------------------------------------------------------------------- #

def test_run_infers_imas_mode_for_jsonld():
    assert _infer_kind("meas.jsonld") == "imas"
    assert _infer_kind("meas.json") == "imas"
    assert _infer_kind("meas.yaml") == "imas"


def test_semantic_file_loads_like_a_plain_one(tmp_path):
    from fylite.device import NFCOIL, NPROBE, NSILOP
    meas = {"plasma": 4.0e5, "btor": -1.8,
            "brsp": [1.0] * NFCOIL, "coils": [0.1] * NSILOP,
            "expmp2": [0.01] * NPROBE, "source": "t", "time_s": 2.0,
            "coil_current_units": "A.turns"}
    p = tmp_path / "meas.jsonld"
    p.write_text(json.dumps(fyo.measurements(meas)))
    back = fyo.as_measurements(str(p), 2.0)
    assert back["plasma"] == pytest.approx(meas["plasma"])
    assert back["brsp"] == pytest.approx(meas["brsp"])
    assert back["source"].startswith("imas:")
