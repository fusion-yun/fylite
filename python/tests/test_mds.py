"""Verification 2: direct EAST MDSplus input (through the engine's mdsip client).

Current, honestly-documented status (2026-07-21, shot 70754 @ 3.5 s):
  - measurement fetch works (76 probes / 35 loops / 12 coils / Ip / BTOR
    via FPOL fallback);
  - the FULL-weight magnetic fit FAILS in the boundary tracer
    ("** Problem in BOUND **", fitted current collapses by iteration 2) —
    the probe response tables are the weak link (approximate efund tables,
    see gnubuild/EFUND.md);
  - the flux-loop-only fit (FWTMP2 = 0) converges with credible global
    quantities (Ip within 0.4%, psi_bry within 1e-3 of efit_east).
"""
import pytest

import fylite
from conftest import has_mds_server

pytestmark = pytest.mark.skipif(
    not has_mds_server(), reason="no mdsip server named (KEFIT_MDS_SERVER)")


@pytest.fixture(scope="module")
def meas():
    from fylite.io import mds
    return mds.fetch_measurements(70754, 3.5)


def test_fetch_shapes_and_scales(meas):
    assert len(meas["expmp2"]) == 76
    assert len(meas["coils"]) == 35
    assert len(meas["brsp"]) == 12
    assert meas["sample_time_s"] == pytest.approx(3.5, abs=0.05)
    assert 4.5e5 < meas["plasma"] < 5.5e5           # 0.5 MA-class shot
    # FCCURT is A-turns: 1e5-1e6-scale entries must be present
    assert max(abs(v) for v in meas["brsp"]) > 1e5
    assert meas["btor"] == pytest.approx(-1.9, abs=0.1)  # FPOL-edge fallback




