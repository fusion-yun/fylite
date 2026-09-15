"""EAST channel contract as a declarative table (device.EAST_CHANNEL_MAP +
the generic engine applier) — behavior-parity pins for the tableization.

The forward parse and the ``to_fyo`` inverse are driven by ONE table, so this
file pins exactly the semantics the old procedural code had: channel-count
enforcement, fallback chains, the units branch, malformed-signal faults, and
the bidirectional round-trip.
"""
from __future__ import annotations

import copy

import pytest

from conftest import requires_machine
from fylite import device, engine, fyo
from fylite.fyo import MeasurementInputError

measurements_from_dict = fyo.as_measurements   # the plain-dict door
to_fyo = fyo.measurements

#: ★The device-derived names (device.NSILOP, device.NPROBE, device.EAST_CHANNEL_MAP, …) are read
#: through the module at USE time, not imported at module level: this
#: distribution ships no device description, so importing them here would
#: make the whole file uncollectable rather than skippable.
pytestmark = requires_machine


def _good() -> dict:
    return {"magnetics": {"flux_loop": [{"flux": 0.1}] * device.NSILOP,
                          "b_field_pol_probe": [{"field": 0.01}] * device.NPROBE,
                          "ip": [4.0e5]},
            "pf_active": {"coil": [{"current": 1000.0}] * device.NFCOIL},
            "tf": {"b_field_tor_vacuum_r": -3.15},
            "coil_current_units": "A.turns"}


def test_table_covers_all_flat_targets():
    assert [e["target"] for e in device.EAST_CHANNEL_MAP] == [
        "coils", "expmp2", "plasma", "btor", "brsp"]


def test_forward_parse():
    m = measurements_from_dict(_good(), 3.5)
    assert m["plasma"] == 4.0e5
    assert m["btor"] == pytest.approx(-3.15 / device.RCENTR)
    assert len(m["coils"]) == device.NSILOP and len(m["expmp2"]) == device.NPROBE
    assert m["brsp"] == [1000.0] * device.NFCOIL          # A.turns passthrough
    assert m["coil_current_units"] == "A.turns"


def test_default_units_apply_the_turnfc_vector():
    d = _good()
    del d["coil_current_units"]
    m = measurements_from_dict(d, 3.5)
    assert m["coil_current_units"] == "A"
    assert m["brsp"] != [1000.0] * device.NFCOIL          # multiplied per channel


def test_top_level_scalar_fallbacks():
    d = _good()
    del d["tf"]
    d["magnetics"] = dict(d["magnetics"])
    del d["magnetics"]["ip"]
    d["ip"], d["btor"] = 3.3e5, -2.0
    m = measurements_from_dict(d, 3.5)
    assert m["plasma"] == 3.3e5 and m["btor"] == -2.0


@pytest.mark.parametrize("mutate, want", [
    (lambda d: d["magnetics"].__setitem__("flux_loop", []), "needs exactly"),
    (lambda d: d["magnetics"].pop("b_field_pol_probe"), "needs exactly"),
    (lambda d: d["magnetics"].__setitem__("ip", []), "no plasma current"),
    (lambda d: d.pop("tf"), "no toroidal field"),
    (lambda d: d.__setitem__("coil_current_units", "kA"),
     "coil_current_units"),
    (lambda d: d["magnetics"]["flux_loop"][3].pop("flux"), "missing signal"),
])
def test_negative_paths_raise_imas_input_error(mutate, want):
    bad = copy.deepcopy(_good())
    mutate(bad)
    with pytest.raises(MeasurementInputError, match=want):
        measurements_from_dict(bad, 3.5)


def test_one_table_drives_both_directions():
    m = measurements_from_dict(_good(), 3.5)
    doc = to_fyo(m)
    assert doc["magnetics"]["@type"] == "fyo:magnetics"
    assert doc["tf"]["b_field_tor_vacuum_r"] == pytest.approx(-3.15)
    back = measurements_from_dict(
        {k: v for k, v in doc.items() if not k.startswith(("@", "fylite:"))},
        3.5)
    for key in ("plasma", "btor", "brsp", "coils", "expmp2"):
        assert back[key] == pytest.approx(m[key])


def test_a_timed_signal_is_interpolated_not_a_name_error():
    """★``signal_at``'s array-with-time-base branch called ``kernel.interp``
    in a module that never imported ``kernel``: every timed signal raised
    ``NameError``.  The shipped documents carry per-slice scalars, so the one
    branch that exists FOR time-resolved input was the one nothing exercised.
    """
    sig = {"data": [0.0, 10.0, 20.0], "time": [0.0, 1.0, 2.0]}
    assert engine.signal_at(sig, 0.5, "probe") == pytest.approx(5.0)
    assert engine.signal_at(sig, 2.0, "probe") == pytest.approx(20.0)
