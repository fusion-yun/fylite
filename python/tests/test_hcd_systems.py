"""The ICRH / ECRH vocabulary: the actuator, the two device blocks, and the
frozen METIS table that a future deposition model will be judged by.

★**No physics here, and that is the point of this file.**  `FEATURE.md` §3.4
says this package has no ICRH or ECRH deposition model, and it still does not
(`docs/note/icrh-ecrh-gap.md` says what would have to land, and
what would judge it).  What landed is the part that was wrong TODAY: a
discharge with ICRF power had no name to declare it under, and the machine's
two cyclotron systems were absent from the device document while their power
signals were being read by name elsewhere.

So the assertions below are about NAMES, LEVELS and ABSENCES — including the
absences, which is the unusual one: the tests refuse a launch geometry that
the machine description does not have.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from conftest import requires_machine
from fylite import device
from fylite import scenario as S

#: The frozen table, beside the ASTRA one it is modelled on.
TABLE = (Path(__file__).resolve().parents[2]
         / "tests" / "data" / "reference" / "metis_cert_hcd.csv")


# --------------------------------------------------------------------------- #
# The actuator
# --------------------------------------------------------------------------- #
def test_the_four_heating_systems_each_have_their_own_waveform():
    """★The defect this closes: before `ic`, an ICRF discharge had to be
    declared as `nbi` or `lh` to reach `p_inj` at all — the TOTAL came out
    right and the ATTRIBUTION came out wrong, which is the one error a total
    cannot show."""
    scn = S.model.Scenario(phases=S.model.Phases(0.0, 1.0, 8.0, 10.0))
    systems = [f for f in scn.__dataclass_fields__
               if isinstance(getattr(scn, f), S.model.Waveform)]
    assert systems == ["nbi", "ic", "ec", "lh"]
    assert scn.ic.power_w == 0.0


def test_ic_power_reaches_the_zero_d_total_like_the_other_three():
    ph = S.model.Phases(0.0, 1.0, 8.0, 10.0)
    base = dict(phases=ph, ip_flattop=1e6, ne_flattop=1e20, te_flattop=5.0)
    w = S.model.Waveform(2.0e6, 1.0, 8.0)
    quiet = S.model.evaluate(S.model.Scenario(**base))
    for which in ("nbi", "ic", "ec", "lh"):
        loud = S.model.evaluate(S.model.Scenario(**base, **{which: w}))
        m = int(np.argmin(np.abs(loud["t"] - 4.5)))
        assert loud["p_inj"][m] - quiet["p_inj"][m] == 2.0e6, which
    #: ★and they ADD — four systems at once is four systems' power, which is
    #: what says `ic` was inserted into the sum rather than replacing a term
    all_four = S.model.evaluate(S.model.Scenario(
        **base, nbi=w, ic=w, ec=w, lh=w))
    m = int(np.argmin(np.abs(all_four["t"] - 4.5)))
    assert all_four["p_inj"][m] == 8.0e6


# --------------------------------------------------------------------------- #
# The device blocks
# --------------------------------------------------------------------------- #
#: ★★2026-09-13 (user ruling, `machine_desc` retired): the card is built from fydoc's
#: A-Box, and the ICRF level / port letters / source power / frequency range have no
#: production reader and are NOT carried (so nothing here asserts them).  What the
#: A-Box does carry is asserted as fydoc states it.
@requires_machine
def test_the_icrf_entries_are_named_as_the_a_box_names_them():
    """Two antennas and eight transmitters, named as fydoc's `ic_antenna` page
    names them.  ★Which of them are antennas and which transmitters (the
    double-counting hazard) is NOT in the A-Box, so no level is asserted."""
    names = [s["name"] for s in device.ICRH_SYSTEMS]
    assert names == ["ICRFI", "ICRFB"] + [f"ICRF{i}" for i in range(1, 9)]


@requires_machine
def test_the_ec_beams_carry_frequency_and_mode_as_numbers():
    """★`140e9` in YAML 1.1 parses as a STRING (the exponent needs a sign) —
    a type drift `float()` still accepts, so it never raises.  The lower-
    hybrid table was written in decimal for this reason; so is this one."""
    assert len(device.ECRH_SYSTEMS) == 4
    for b in device.ECRH_SYSTEMS:
        assert isinstance(b["frequency"], float)
        assert b["frequency"] == 140e9
        #: ★the value fydoc's A-Box carries (`ec_launchers` beam `mode` = 1, O-mode,
        #: from the imas/3 eastwiki table).  fydoc RECORDS A DIVERGENCE on this field:
        #: xu2025ech §1 says the heating uses the X2 mode.  Asserted as the A-Box
        #: states it — a change here is an upstream re-ruling, not a fix in this repo.
        assert b["mode"] == 1
        assert b["max_power"] == 1.0e6


@requires_machine
def test_the_document_does_not_invent_what_the_machine_description_lacks():
    """★★The unusual assertion, and the one worth keeping: the A-Box's EAST
    description has NO per-shot ICRF frequency and NO EC launch position or
    steering angle.  Those two are exactly what fixes the resonance layer and
    the deposition location, so inventing them here would put a made-up number
    where a model will look for a real one.  This test fails the day someone
    quietly fills them in."""
    dev = device.document()
    ic, ec = dev["ic_antennas"], dev["ec_launchers"]
    for a in ic["antenna"]:
        assert "frequency" not in a, a["name"]
        assert not {"r", "z", "phi"} & set(a), a["name"]
    for b in ec["beam"]:
        assert "launching_position" not in b, b["name"]
        assert not {"steering_angle_pol", "steering_angle_tor"} & set(b), \
            b["name"]
    #: the RANGE of what the launcher can be steered to is a capability and is
    #: carried — as prose, verbatim from the eastwiki entry fydoc's `ec_launchers`
    #: page quotes in its provenance comment
    assert "±25" in ec["fylite:steering_range_note"]


# --------------------------------------------------------------------------- #
# The frozen METIS table
# --------------------------------------------------------------------------- #
def _table():
    text = TABLE.read_text(encoding="utf-8")
    head = [l for l in text.splitlines() if l.startswith("#")]
    body = [l for l in text.splitlines()
            if l and not l.startswith("#")]
    cols = body[0].split(",")
    rows = [dict(zip(cols, l.split(","))) for l in body[1:]]
    return head, cols, rows


def test_the_metis_table_is_whole():
    head, cols, rows = _table()
    assert rows, "the reference table is empty"
    for r in rows:
        assert len(r) == len(cols)
    #: the sha256 of every archive read is in the header, so a regeneration
    #: that silently read a different suite is detectable
    listed = re.findall(r"^#   (\S+\.mat)\s+([0-9a-f]{64})", "\n".join(head),
                        re.M)
    assert listed
    assert {n[:-4] for n, _ in listed} == {r["case"] for r in rows}


def test_the_metis_table_carries_what_an_icrh_port_will_be_judged_by():
    """The columns stage 1 needs, present and populated on the ICRH rows."""
    _, _, rows = _table()
    icrh = [r for r in rows if float(r["picrh"] or 0) > 1e4]
    assert len(icrh) >= 20
    for r in icrh:
        for k in ("mino", "freq_mhz", "cmin", "rres", "xres", "pel_icrh",
                  "pion_icrh", "ecrit_icrh", "taus_icrh", "esup_icrh",
                  "b0", "R", "a", "d0", "nem", "tem"):
            assert r[k] != "", (r["case"], k)
        assert r["mino"] in ("H", "T")
        #: the split is METIS's own and must add up to what it absorbed
        total = float(r["pel_icrh"]) + float(r["pion_icrh"])
        assert abs(total - float(r["picrh_th"])) < 0.02 * float(r["picrh_th"])


def test_the_layer_columns_are_present_and_are_marked_as_derived():
    """★The five `*_res` columns are NOT read out of METIS's answers — it
    does not save them.  The extraction tool computes them from its saved
    profiles with `z0icrh.m`'s own deposition weighting.  A reader who takes
    them for upstream's own output would be over-trusting them, so the file
    says which they are and this keeps that sentence there."""
    head, _, rows = _table()
    for r in rows:
        for k in ("te_res", "ne_res", "ti_res"):
            assert r[k] != "", (r["case"], k)
    joined = "\n".join(head)
    assert "derived by the extraction tool" in joined


def test_the_steady_flag_exists_and_is_not_everything():
    """★★The trap this column guards: METIS ran with `transitoire = 1`, so
    `pel_icrh` is an ODE over the whole history, not a function of the
    slice's state.  A steady-state port may only be judged on `steady = 1`
    rows.  If every row were steady the column would be decoration — it is
    not: some are 0, and they are 0 for a reason."""
    head, _, rows = _table()
    flags = [r["steady"] for r in rows]
    assert set(flags) == {"0", "1"}
    assert 0 < flags.count("0") < len(flags)
    #: and the file says so where a reader will hit it before the numbers
    assert any("transitoire" in l for l in head)


def test_the_table_states_what_it_cannot_settle():
    """★The EC deposition LOCATION is not in evidence here: in METIS `xece`
    is a request.  A reader who takes `xeccd` for a prediction is the failure
    this header line is written against."""
    head, _, _ = _table()
    joined = "\n".join(head)
    assert "xece is a request" in joined
    assert "not redistributed" in joined or "NOT redistributed" in joined
