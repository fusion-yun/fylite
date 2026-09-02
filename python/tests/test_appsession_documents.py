"""The browser session's exit: session JSON → fyo document → disk.

★Conversion claims only — nothing here is physics.  What they guard is the
part that has bitten this package before: an index order, a gauge flip, and
a second writer that drifts from the first.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from fylite import appsession, fyo

TWO_PI = 2.0 * math.pi
NW, NH = 9, 7


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    r = np.linspace(1.2, 2.4, NW)
    z = np.linspace(-0.8, 0.8, NH)
    #: app layout is [i*nh + j] with i the R index — deliberately NOT square,
    #: so an index-order slip cannot reshape its way out
    psi = np.add.outer((r - 1.8) ** 2, z ** 2)
    doc = {
        "@type": appsession.TYPE, "@id": "fylite:session/test",
        "fylite:psi_convention": appsession.APP_CONVENTION,
        "fylite:created": "2026-08-20", "fylite:page": "recon",
        "fylite:config": {"shot": 137985, "time": 4.0},
        "fylite:result": {
            "equilibrium": {"time_slice": [{
                "global_quantities": {
                    "magnetic_axis": {"r": 1.8, "z": 0.0},
                    "psi_axis": 0.9, "psi_boundary": 0.1, "ip": 4.2e5},
                "profiles_2d": [{"grid": {"dim1": list(r), "dim2": list(z)},
                                 "psi": list(psi.ravel())}],
                "profiles_1d": {
                    "pressure": [3.0, 2.0, 1.0],
                    "dpressure_dpsi": [-1.0, -2.0, -3.0],
                    "f_df_dpsi": [0.5, 0.2, 0.1], "f": [3.6, 3.5, 3.4],
                    "fylite:q_psi_norm": [0.06, 0.5, 0.995],
                    "q": [0.9, 1.8, 4.2]},
                "boundary": {"outline": {"r": [1.4, 2.2, 1.8],
                                         "z": [0.0, 0.0, 0.5]}}}]},
            "pf_active": {"coil": [{"name": "PF1", "current": {"data": [1.0, 2.0]}},
                                   {"name": "PF2", "current": {"data": [3.0, 4.0]}}]},
            "magnetics": {"flux_loop": [
                {"flux": {"data": [0.1]}, "fylite:reconstructed": 0.11,
                 "fylite:weight": 1.0}]},
        }}
    p = tmp_path_factory.mktemp("sess") / "s.json"
    p.write_text(json.dumps(doc))
    return appsession.load(p), psi


def test_the_gauge_flips_once_and_the_map_arrives_transposed(session):
    doc, psi = session
    g = appsession.to_geqdsk(doc)
    #: the page carries full flux [Wb] with the axis at the MAXIMUM; a g-file
    #: wants Wb/rad with the axis at the minimum — one flip, here
    assert g["simag"] == -0.9 / TWO_PI and g["sibry"] == -0.1 / TWO_PI
    assert np.array_equal(np.asarray(g["psirz"], float).reshape(NH, NW),
                          (-psi / TWO_PI).T)


def test_q_is_extrapolated_to_the_axis_and_the_boundary(session):
    doc, _ = session
    g = appsession.to_geqdsk(doc)
    q = np.asarray(g["qpsi"], float)
    assert q.size == NW
    #: the page traced q on [0.06, 0.995]; a CLAMP would put q(0) = q(0.06)
    #: and hand the g-file zero shear across the axis
    assert q[0] < 0.9 and q[-1] > 4.2


def test_the_session_becomes_one_fyo_document(session):
    doc, _ = session
    d = appsession.to_document(doc)
    assert d["@type"] == "fyo:equilibrium"
    assert d["fylite:session_type"] == appsession.TYPE
    assert d["fylite:config"]["shot"] == 137985
    assert d["fylite:psi_convention"] == appsession.APP_CONVENTION
    assert d["pf_active"]["fylite:name"] == ["PF1", "PF2"]
    assert d["magnetics"]["flux"].shape == (1, 1)


def test_a_configuration_only_session_is_a_document_not_an_error(session):
    doc, _ = session
    cfg = {k: v for k, v in doc.items() if k != "fylite:result"}
    d = appsession.to_document(cfg)
    assert d["@type"] == appsession.TYPE and "time_slice" not in d
    assert d["fylite:config"]["time"] == 4.0


def test_the_hdf5_exit_is_the_document_writer(session, tmp_path):
    pytest.importorskip("h5py")
    doc, _ = session
    back = fyo.read(appsession.to_hdf5(doc, tmp_path / "s.h5"))
    d = appsession.to_document(doc)
    assert back["@type"] == "fyo:equilibrium"
    assert np.array_equal(
        np.asarray(back["time_slice"][0]["profiles_2d"][0]["psi"], float),
        d["time_slice"][0]["profiles_2d"][0]["psi"])
    assert np.array_equal(np.asarray(back["pf_active"]["current"], float),
                          d["pf_active"]["current"])
