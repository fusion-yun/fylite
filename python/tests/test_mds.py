"""Verification 2: the efit_east measurement reader refuses (user ruling 2026-09-15).

★★「efit_east mdsplus tree 仅作为对拍比较数据，不应进入 facts/device，也不应作为建模或反演数据源」.  This file used to read
#70754 @ 3.5 s live through ``fylite.io.mds.fetch_measurements`` (EFIT's MEASUREMENTS record: 76 probes / 35 loops /
12 coils / Ip / BTOR) and check its shapes and scales for the reconstruction; that reader now refuses, so what is
gated here is the refusal itself — offline, no server needed.  The live readings of 2026-07-21 are in git history.
"""
import pytest

from fylite.io import mds


def test_the_efit_east_measurement_reader_refuses_by_the_ruling():
    with pytest.raises(mds.MdsError, match="comparison data only"):
        mds.fetch_measurements(70754, 3.5)
