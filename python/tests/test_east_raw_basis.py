"""What the RAW channel basis costs on the shot this repository ships (T-A20).

★★**Why this exists.**  The analysis page offers two channel bases for the
flux loops: the *delivered* reconstruction's own channel values (another code's
answer, coil share already removed) and the *raw* est2 reading, which is the
TOTAL flux and from which this page subtracts the coil share with its own
response.  The ledger recorded the raw basis as "does not reconstruct on the
bundled shot", and the working hypothesis was that ``aturns`` and
``loopMeasTotal`` had come from two different reductions.

Both halves turned out to be wrong, and this gate pins what is true instead:

  * The two blocks are ONE record.  ``tools/est2-dump-to-device.py`` writes
    ``loopMeasTotal`` from ``m['coils']`` and ``aturns`` from ``m['brsp']``
    inside a single slice block, so a source mismatch is not available as an
    explanation.
  * The raw basis DOES fit this shot with the coils held exact (measured in
    the browser: residual 5.15e-5, weighted χ² 8.60e-4, against the delivered
    basis's 1.98e-8 / 4.55e-4).  What diverges is adding an unknown — fitting
    the coils (outer iteration 78) or the vessel (137), which is what the
    「爬升段」 preset turns on.
  * The reason is the arithmetic this file measures: at the loops the coil
    share is ~3× the plasma signal, and this page's subtraction lands ~5 % of
    that signal away from the delivered channel values, in both directions.
    Held exact, that 5 % goes into the residual and the fit stands; set free,
    twelve nearly-degenerate coil currents try to absorb it and the normal
    equations go singular.

★So this is a gate on the DECK, not on a fit: it is the quantitative claim the
page's basis note now makes, and a note whose numbers nothing checks is a
number that rots.  ★It asserts BANDS, not values: the point is the order of
magnitude and the sign structure, and a gate pinned to the last digit would
fail on any legitimate re-reduction of the same shot.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESC = ROOT / "machine_desc" / "east"
JSON_DOC = DESC / "fylite_device_east.json"
YAML_DOC = DESC / "east_device.yaml"

pytestmark = pytest.mark.skipif(
    not (JSON_DOC.is_file() and YAML_DOC.is_file()),
    reason="EAST is not described in this tree")


@pytest.fixture(scope="module")
def shot():
    """The reference discharge, and this page's own coil share at its loops."""
    import yaml
    from fylite import device

    doc = json.loads(JSON_DOC.read_text(encoding="utf-8"))
    ref = doc["fylite:reference_discharge"]
    cs = device.conductor_set(
        document=yaml.safe_load(YAML_DOC.read_text(encoding="utf-8")))
    #: channel currents (A-turns, the BRSP state) onto the elements
    elements = np.asarray(cs["weights"], float).T @ np.asarray(ref["aturns"], float)
    loops = [p["position"][0] for p in doc["magnetics"]["flux_loop"]]
    psi, _br, _bz = device.point_response(
        cs["coils"],
        np.array([p["r"] for p in loops], float),
        np.array([p["z"] for p in loops], float), nu=4, nv=4)
    #: ★the loop channel is Wb PER RADIAN — the same convention the page's
    #: `loopCoilFlux` applies to the kernel's full-flux response
    share = (np.asarray(psi, float) @ elements) / (2 * np.pi)
    return {
        "total": np.asarray(ref["loopMeasTotal"], float),
        "delivered": np.asarray(ref["loopMeas"], float),
        "weight": np.asarray(ref["loopWeights"], float),
        "share": share,
        "provenance": ref.get("fylite:channel_provenance") or {},
    }


def test_the_coil_share_dominates_the_loop_reading(shot):
    """★The subtraction is a difference of LARGE numbers.

    This is the whole difficulty of the raw basis in one number: what the
    loops see is mostly the coils, and the plasma is the small remainder.
    """
    m = shot["weight"] > 0
    coil = float(np.sqrt(np.mean(shot["share"][m] ** 2)))
    plasma = float(np.sqrt(np.mean(shot["delivered"][m] ** 2)))
    assert 2.0 < coil / plasma < 5.0, (coil, plasma, coil / plasma)


def test_this_pages_subtraction_lands_a_few_percent_off_the_delivered_values(shot):
    """``total − our coil share`` vs the delivered channel values.

    ★Not a bug in either: the delivered values were produced by another code
    with its own response tables (``rfcoil.ddd``, which this repository does
    not ship) and its own idea of what else to remove.  What matters is the
    SIZE of the disagreement relative to the plasma signal, because that is
    what a fit has to absorb.
    """
    m = shot["weight"] > 0
    d = (shot["total"] - shot["share"] - shot["delivered"])[m]
    plasma = float(np.sqrt(np.mean(shot["delivered"][m] ** 2)))
    rel_rms = float(np.sqrt(np.mean(d ** 2))) / plasma
    assert 0.02 < rel_rms < 0.10, rel_rms
    #: ★AND IT IS NOT AN OFFSET.  A constant would be absorbed by the fit's
    #: own freedom; a disagreement that changes sign channel to channel is a
    #: shape the solution has to carry as residual.
    assert (d > 0).any() and (d < 0).any(), d
    assert abs(float(np.mean(d))) < 0.6 * float(np.sqrt(np.mean(d ** 2))), (
        "the disagreement is mostly a constant offset — the note explains a "
        "shape, and that would be a different statement")


def test_the_two_blocks_are_one_record_not_two_reductions(shot):
    """★The hypothesis this replaced, closed in the data itself.

    The deck states where the raw loop totals came from; the coil currents
    ride in the same slice block written by the same tool.  A gate cannot
    prove provenance, but it can refuse a deck that quietly grows a SECOND
    statement about where one of them came from.
    """
    prov = shot["provenance"]
    assert "loopMeasTotal" in prov, sorted(prov)
    assert "est2" in prov["loopMeasTotal"], prov["loopMeasTotal"]
    #: if a future deck really does take the coils from somewhere else, it
    #: has to say so here — and this gate is then the thing that fails
    assert "aturns" not in prov, (
        "the deck now claims a separate source for the coil currents; the "
        "basis note and T-A20's answer both rest on there being one record")
