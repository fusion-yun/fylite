"""The generated EAST card carries every POINT reduction setting (2026-09-14 gate).

★What this closes.  After the hand-maintained card was retired (user ruling
2026-09-13) the EAST card is generated from fydoc's A-Box, and two things the
POINT reduction (`fylite.io.raw.reduce_series(read_point=True)`) needs went
missing without any test noticing:

* ``polarimeter.baseline`` (``POINT_BASELINE_S`` / ``POINT_BASELINE_TOL``) — the
  pre-shot offset window.  Program-side, so it now comes from the generator's
  ``PROGRAM_SIDE['east']['point_baseline']``.  Absent, every POINT read was
  refused by name.
* the polarimeter MDSplus node names.  With no binding the Faraday chords were
  named ``POINT1..11`` (upstream channel names, not nodes).  A live read then
  got nothing for all 11 chords and the Faraday constraint came out as zeros,
  with no error.  fydoc now binds ``\\POINT_F<k>``.

So the gate checks that the names derive, that the node names are nodes, and
that an offline reduction over synthetic series gives back what was put in.
★Synthetic series only: no discharge reading belongs in this repository.
"""

from __future__ import annotations

import math
import pathlib
import re

import numpy as np
import pytest

from fylite import device as D
from fylite import facts as F

ROOT = pathlib.Path(__file__).resolve().parents[2]
CARD = ROOT / "dist" / "facts" / "device" / "east" / "east_device.yaml"
#: chain -> shot to resolve on (None: no shot).  ★efit_east has only closed-range providers
#: (efit_green2015 [70745, 70754], efit_green2022_pcs [137985, 137985]), so a no-shot
#: resolution there is a refused gap; it is asked on its verified shot #137985.
CHAINS = {"pcs_east": None, "east": None, "efit_east": 137985}
#: every POINT_* name the reader derives, read off the reader (not a copy of its list)
POINT_NAMES = sorted(n for n in D._DERIVED_NAMES if n.startswith("POINT_"))


@pytest.fixture(scope="module")
def card() -> dict:
    if not CARD.is_file():
        pytest.skip(f"no {CARD.relative_to(ROOT)} (python3 tools/abox-to-facts.py east)")
    return D.load_device(CARD)


def _missing(derived: dict) -> list[str]:
    return [n for n in POINT_NAMES if derived.get(n) is None]


def test_the_reader_names_the_settings_this_gate_is_about():
    assert {"POINT_BASELINE_S", "POINT_BASELINE_TOL", "POINT_WINDOW_MS", "POINT_FARADAY_C",
            "POINT_LASER_LAMBDA", "POINT_NE_NODES", "POINT_FR_NODES", "POINT_NCHORD"} <= set(POINT_NAMES)


def test_the_generated_card_derives_every_point_name(card):
    assert not _missing(D._derive(card)), "the generated EAST card leaves POINT names underived"


@pytest.mark.parametrize("chain", CHAINS)
def test_every_measurement_chain_derives_every_point_name(chain):
    lib = F._lib()
    if lib is None or not hasattr(lib, "fylite_runtime_device_resolve"):
        pytest.skip("libfylite_runtime.so without fylite_runtime_device_resolve (bash rust/build.sh)")
    #: no name: the configured card ($FYLITE_DEVICE_DIR), resolved in that chain
    shot = CHAINS[chain]
    doc = D.document(measurement_chain=chain) if shot is None else D.document(measurement_chain=chain, shot=shot)
    assert doc["magnetics"].get(D.CHAIN_KEY) == chain
    assert not _missing(D._derive(doc)), f"chain {chain}: POINT names underived"


def test_point_nodes_are_node_names_paired_by_chord(card):
    got = D._derive(card)
    ne, fr = got["POINT_NE_NODES"], got["POINT_FR_NODES"]
    assert len(ne) == len(fr) == got["POINT_NCHORD"]
    k_ne = [int(re.fullmatch(r"POINT_N(\d+)", n).group(1)) for n in ne]
    k_fr = [int(re.fullmatch(r"POINT_F(\d+)", n).group(1)) for n in fr]
    assert k_ne == k_fr == list(range(1, len(ne) + 1))


def test_an_offline_point_reduction_returns_what_it_was_given(card):
    """Synthetic series through the shared reduction: offset removed, window averaged,
    Faraday angle scaled by the card's own constants, every chord active."""
    from fylite.io import raw

    names = D._derive(card)
    t = np.round(np.arange(-1.0, 3.0, 1e-3), 6)
    nch = names["POINT_NCHORD"]
    ne_val = {f"POINT_N{k}": 3.0 + 0.05 * k for k in range(1, nch + 1)}
    fr_val = {f"POINT_F{k}": 0.5 + 0.1 * k for k in range(1, nch + 1)}
    offset = 7.0                                    # a pre-shot level the baseline must remove

    def get(leaf, tree):
        key = leaf.lstrip("\\").upper()
        if key in ne_val or key in fr_val:
            v = ne_val.get(key, fr_val.get(key))
            return offset + np.where(t > 0, v, 0.0), t
        if key == "PCRL01":
            return np.full_like(t, 4.0e5), t
        return np.full_like(t, 1.0e-3), t          # magnetics / PF / Bt: present, unremarkable

    meas = raw.reduce_series(get, 1, 2.0, device_doc=card, read_point=True)
    pt = meas["point"]
    assert pt["n_chord"] == nch and pt["kpol"] == 1.0
    assert pt["n_ne_active"] == nch and pt["n_fr_active"] == nch and pt["fringe_dropped"] == []
    c_far = names["POINT_FARADAY_C"] * names["POINT_LASER_LAMBDA"] ** 2
    for k in range(1, nch + 1):
        assert math.isclose(pt["bnel"][k - 1], ne_val[f"POINT_N{k}"], rel_tol=1e-12)
        want = fr_val[f"POINT_F{k}"] / c_far / 2.0 * math.pi / 180.0 / 1e19
        assert math.isclose(pt["bpolar"][k - 1], want, rel_tol=1e-12)
