"""One reconstruction request, two tool faces, one door.

★★Why this file exists.  ``fylite run`` and the MCP ``fylite_run`` tool each
resolved the input mode themselves, and each resolved it into the signature of
the EFIT driver that left with LICENSE 3.1 (``kind=`` / ``out=`` / ``preset=``
on ``recon_rs.reconstruct``).  Both therefore raised ``TypeError`` on their
first statement — in all four modes, for every input — and the package's most
visible entry point was dead while the suite stayed green: the mode logic was
written inside a handler, the calls it made were resolved by a function-local
import, and ``test_call_sites_match`` read module-level imports only.

That detector now walks scopes, so the *signature* half is gated there.  This
file gates the half a signature cannot see: which door each mode goes through,
which options reach it, and that what comes back can be delivered as a deck.

★No solve runs here.  A magnetic reconstruction needs the Green RESPONSE
tables (``rfcoil.ddd`` / ``rv6565.ddd``), which this distribution does not
ship — so the seam is stubbed and the routing is what is asserted.  The
delivery test is not stubbed: it writes a real g-file from the synthetic
equilibrium and reads it back.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from fylite import engine, fyo
from fylite.engine import serve as _serve
from fylite.io import geqdsk
from fylite.scenario.analysis import recon_rs

REPO = Path(__file__).resolve().parents[2]
SYNTHETIC = REPO / "tests" / "data" / "synthetic" / "g_synthetic.geqdsk"


@pytest.fixture
def routed(monkeypatch):
    """Capture what the input door is called with, without solving."""
    seen = {}

    def fake(source, time_s=None, **kw):
        seen.update(source=source, time_s=time_s, **kw)
        return {"gfile": None, "q0": 1.0, "q95": 3.0, "shot": kw.get("shot"),
                "tables": "stub", "iterations": 3, "residual": 1e-10,
                "psi_axis": -0.1, "psi_bry": 0.0, "ip": 4.0e5, "bcentr": -1.8,
                "rmaxis": 1.85, "zmaxis": 0.0}

    monkeypatch.setattr(recon_rs, "reconstruct_input", fake)
    return seen


# --------------------------------------------------------------------------- #
# mode routing
# --------------------------------------------------------------------------- #

def test_a_document_goes_through_the_imas_door(routed):
    _serve.run_reconstruction({"input": "meas.jsonld", "time_s": 2.0,
                               "shot": 137985})
    assert routed["kind"] == "imas"
    assert routed["source"] == "meas.jsonld" and routed["time_s"] == 2.0
    assert routed["shot"] == 137985


def test_east_mode_carries_the_tree_options(routed):
    _serve.run_reconstruction({
        "east": True, "shot": 137985, "time_s": 4.0, "server": "host",
        "point": True, "point_sig": [0.1, 0.2], "point_window_ms": 30.0,
        "pressure": True, "pressure_sig": 0.2, "te_ceiling": 8000.0,
        "thomson_ne": True})
    assert routed["kind"] == "east" and routed["source"] == 137985
    assert routed["read_point"] and routed["read_pressure"]
    assert routed["read_thomson_ne"] and routed["server"] == "host"
    assert routed["point_opts"] == {"signel": 0.1, "sigpol": 0.2}
    assert routed["pressure_opts"] == {"sigpre_frac": 0.2,
                                       "te_ceiling": 8000.0}


def test_a_bare_shot_does_not_carry_tree_options(routed):
    #: ★the efit_east measurement nodes are not the est2 path: the POINT /
    #: pressure / Thomson options have no meaning there, and the router
    #: would reject them by name.  They are dropped here, not forwarded.
    _serve.run_reconstruction({"shot": 137985, "time_s": 4.0, "point": True,
                               "server": "host", "probes": False})
    assert routed["kind"] == "shot"
    assert "read_point" not in routed and "server" not in routed
    assert routed["probes"] is False


def test_options_left_unset_are_not_forwarded(routed):
    _serve.run_reconstruction({"east": True, "shot": 1, "time_s": 1.0})
    assert set(routed) == {"source", "time_s", "kind"}


def test_kfile_input_is_refused_with_the_reason():
    with pytest.raises(recon_rs.KefitRunError) as e:
        recon_rs.reconstruct_input("ready.kfile")
    msg = str(e.value)
    assert "LICENSE 3.1" in msg and "measurement" in msg


def test_an_unreadable_source_names_the_modes():
    with pytest.raises(ValueError) as e:
        recon_rs.reconstruct_input(3.5)
    assert "pass kind=" in str(e.value)


# --------------------------------------------------------------------------- #
# the two faces agree
# --------------------------------------------------------------------------- #

def test_the_curated_tool_schema_only_offers_options_that_reach_the_door():
    """Every property ``fylite_run`` advertises is one this face acts on."""
    tool = next(t for t in _serve.list_mcp_tools() if t["name"] == "fylite_run")
    offered = set(tool["input_schema"]["properties"])
    handled = set(_serve._RUN_DIRECT) | {"input", "east", "shot", "time_s",
                                         "point_sig", "pressure_sig",
                                         "te_ceiling", "out"}
    assert not offered - handled, (
        f"fylite_run advertises {sorted(offered - handled)}, which "
        "run_reconstruction ignores")


# --------------------------------------------------------------------------- #
# delivery — the half that is real
# --------------------------------------------------------------------------- #

def test_delivery_writes_a_deck_that_reads_back(tmp_path):
    g0 = geqdsk.read_geqdsk(SYNTHETIC)
    doc = fyo.equilibrium(g0, source="synthetic")
    path = Path(_serve.deliver_gfile(doc, tmp_path))
    assert path.name == "g_reconstruction.geqdsk"   # no shot/time to name it
    g1 = geqdsk.read_geqdsk(path)
    for k, v in g0.items():
        if k == "header":
            continue
        assert np.allclose(np.asarray(g1[k], float), np.asarray(v, float)), k


def test_a_slice_names_itself_by_shot_and_time():
    assert geqdsk.gfile_name(137985, 4.0) == "g137985.04000"
    assert geqdsk.gfile_name(93060, 1.001) == "g093060.01001"


def test_the_converter_refuses_to_resample(tmp_path):
    """★A profile on a different grid is a numerical choice, not a format
    detail — the converter says so instead of making it."""
    doc = fyo.equilibrium(geqdsk.read_geqdsk(SYNTHETIC), source="synthetic")
    fyo.put(doc, "EQUILIBRIUM", "q_1d", np.zeros(17))
    with pytest.raises(ValueError) as e:
        fyo.as_geqdsk(doc)
    assert "17 points" in str(e.value) and "nw=" in str(e.value)


def test_the_deck_transpose_survives_a_round_trip():
    """psi is ``[R, Z]`` in the document and ``[z, r]`` in the deck; a
    transpose that got lost would still produce a readable file."""
    g0 = geqdsk.read_geqdsk(SYNTHETIC)
    doc = fyo.equilibrium(g0, source="synthetic")
    psi2d = np.asarray(fyo.get(doc, "EQUILIBRIUM", "psi_2d"), float)
    g1 = fyo.as_geqdsk(doc)
    nw, nh = g0["nw"], g0["nh"]
    assert psi2d.shape == (nw, nh)
    assert np.allclose(np.asarray(g1["psirz"], float).reshape(nh, nw),
                       psi2d.T)


def test_the_mcp_run_tool_reports_a_failure_as_an_iserror_result(monkeypatch):
    def boom(opts):
        raise recon_rs.KefitRunError("no deck here")
    monkeypatch.setattr(_serve, "run_reconstruction", boom)
    result = _serve.call_mcp_tool("fylite_run", {"shot": 1, "time_s": 1.0})
    assert result["isError"] is True
    assert json.loads(result["content"][0]["text"])["error"] == "KefitRunError"
