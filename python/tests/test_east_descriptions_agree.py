"""EAST is described twice on the facts path, and the two must agree.

★★**Where the two now come from (2026-09-13, machine_desc retired by user
ruling).**  `device/east/east_device.yaml` is what Python reads
(`device.load_device`); `device/east.jsonld` is what the browser imports
(`FyoDevice.fromFyo`) and what `facts.rs` embeds.  Both are written by
`tools/abox-to-facts.py` from fydoc's A-Box — the JSON is derived from the
YAML (`write_document`).  One generator does not make the gate redundant: the
derivation reshapes (flattens channels, renames the channel map, moves the
vacuum field, drops alternative limiters), and a reshaping that changes the
machine is exactly what this compares.  Read from the first root on the facts
search path (`fylite.facts.roots()`; a checkout's staged `dist/facts/`).

★★**Why this exists (history).**  Until 2026-09-13 the two were the
hand-maintained `machine_desc/east/east_device.yaml` and
`fylite_device_east.json`, maintained by different hands — the JSON's
ancestry is a browser export.  Nothing had ever compared them.

That is the shape this directory's README says it eliminated once already:
`dprobe.dat` and the device document described one machine twice until the
deck stopped being a second source.  The browser's copy never converged,
because it is on the other side of a language boundary.

★What this file does NOT do is force the two into one shape.  They are
deliberately different VIEWS — the YAML lists 12 PCS/EFIT channels with
their conductor elements nested, the JSON lists the 14 conductor elements
flat with a channel map beside them.  Both are legitimate; a machine has
channels and it has conductors.  What must agree is the MACHINE: the same
rectangles, the same channel map, the same probes and loops in the same
places, and — the one that bit — the same wall.

Ledger for the split: `docs/note/machine-desc-to-app-and-rust.md`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fylite import facts as _facts


def _pair_paths() -> tuple[Path | None, Path | None]:
    """The first facts root carrying BOTH EAST forms (never one from each root)."""
    for root in _facts.roots():
        y, j = root / "device" / "east" / "east_device.yaml", root / "device" / "east.jsonld"
        if y.is_file() and j.is_file():
            return y, j
    return None, None


YAML_DOC, JSON_DOC = _pair_paths()

pytestmark = pytest.mark.skipif(
    YAML_DOC is None,
    reason="EAST is not on the facts search path in both forms "
           "(run `python3 tools/abox-to-facts.py --all`)")


@pytest.fixture(scope="module")
def pair():
    import yaml
    return (yaml.safe_load(YAML_DOC.read_text(encoding="utf-8")),
            json.loads(JSON_DOC.read_text(encoding="utf-8")))


def _rect(el: dict) -> tuple:
    r = el["geometry"]["rectangle"]
    return (r["r"], r["z"], r["width"], r["height"],
            el.get("fylite:a1", 0.0), el.get("fylite:a2", 90.0))


def _yaml_elements(y: dict) -> list[tuple]:
    """The 16 conductor rectangles (14 PF + IC1/IC2), flattened out of the channels.

    ★Flattened, not `element[0]`: two channels drive a SERIES PAIR and carry
    two elements each.  Reading only the first is how a comparison concludes
    "12 against 14" and reports a difference that is not there.
    """
    return [_rect(e) for c in y["pf_active"]["coil"] for e in c["element"]]


def test_the_conductor_rectangles_are_the_same_sixteen(pair):
    """★The rectangles are what both hosts hand the kernel — Python through
    `device.conductor_geometry`, the browser through `FyoDevice.fromFyo` —
    and the kernel computes every mutual inductance from them.  A machine
    that differs here is a different machine, silently.

    ★16 since K-2 (2026-09-13): the 14 PF elements plus the fast IC1/IC2
    coils (`function` b_field_fb).  This asserted 14 against a card that had
    already grown to 16, and nobody saw it because the module skipped."""
    y, j = pair
    got = _yaml_elements(y)
    want = [_rect(c["element"][0]) for c in j["pf_active"]["coil"]]
    assert len(got) == len(want) == 16, (len(got), len(want))
    assert got == want


def test_the_channel_map_is_the_same_map(pair):
    """Which elements a PCS channel drives, and with what weight.

    ★This is the E-14 fit's own output and has no DD spelling — it rides as
    `pf_channel_elements` in the YAML and `fylite:channel_map` in the JSON.
    Two hand-maintained copies of a fitted 14-number result is exactly the
    thing that drifts without anyone able to notice.
    """
    y, j = pair
    a = [[(t["element"], round(float(t["weight"]), 9)) for t in ch]
         for ch in y["pf_channel_elements"]]
    b = [[(int(i), round(float(w), 9)) for i, w in ch]
         for ch in j["fylite:channel_map"]]
    assert a == b


def test_the_magnetic_probes_are_in_the_same_places(pair):
    y, j = pair
    a = [(c["name"], c["position"][0]["r"], c["position"][0]["z"])
         for c in y["magnetics"]["b_field_pol_probe"]]
    b = [(c.get("name"), c["position"][0]["r"], c["position"][0]["z"])
         for c in j["magnetics"]["b_field_pol_probe"]]
    assert len(a) == len(b) == 38
    assert a == b


def test_the_flux_loops_are_in_the_same_places(pair):
    """★POSITIONS only — the names are a separate case below.

    ★★2026-09-13 (R-S1 / R-S2 + the measurement-chain ruling): both forms are the NO-SHOT
    resolution, whose magnetics provider is ``pcs`` (chain ``pcs_east``, 35 loops; user ruling
    2026-09-14 — before it ``east_new``, 75 loops).  The
    other chains' loop sets are not in either file as written; they are what each form
    RESOLVES to, so one is compared resolved — both forms, one resolution document, the
    runtime's rule: the ``east`` chain at #137985 (``east_new``, 75 loops; the ``efit_east``
    chain compared here until it left the device book, user ruling 2026-09-15).
    """
    east_137985 = {"measurement_chain": "east", "shot": 137985}
    from fylite import device

    def places(doc):
        return [(c["position"][0]["r"], c["position"][0]["z"])
                for c in doc["magnetics"]["flux_loop"]]

    y, j = pair
    assert y["magnetics"]["fylite:provider"] == j["magnetics"]["fylite:provider"] == "pcs"
    assert len(places(y)) == len(places(j)) == 35
    assert places(y) == places(j)
    res = device.resolution_of(YAML_DOC)
    ye = device.resolve_document(y, res, form="card", **east_137985)["document"]
    je = device.resolve_document(j, res, form="document", **east_137985)["document"]
    assert ye["magnetics"]["measurement_chain"] == je["magnetics"]["measurement_chain"] == "east"
    assert len(places(ye)) == len(places(je)) == 75
    assert places(ye) == places(je)


def test_the_flux_loops_carry_the_same_names(pair):
    """★★The names are the MDSplus node names (`device.FLUX_LOOP_NODES`
    reads them to fetch the shot), so the YAML's are the machine's.  The
    JSON's were display labels — all 35 differed (`FL1B` against `FL1`), so
    a reader keyed by name found nothing in common between two descriptions
    of the same 35 loops.
    """
    y, j = pair
    a = [c["name"] for c in y["magnetics"]["flux_loop"]]
    b = [c.get("name") for c in j["magnetics"]["flux_loop"]]
    assert a == b


def _limiter_units(doc: dict) -> list[tuple]:
    """Every limiter contour a document carries, named.

    ★One indexing for both sides: `wall.description_2d` is the DD's array in
    each of them now (`@fyo-table DEVICE`).  It was a mapping on the Python
    side, which is why this helper used to need to know which file it was
    looking at.
    """
    d2 = doc["wall"]["description_2d"][0]
    out = []
    for u in d2["limiter"]["unit"]:
        o = u["outline"]
        out.append((u.get("name"), tuple(o["r"]), tuple(o["z"])))
    return out


def test_both_descriptions_run_east_on_the_same_wall(pair):
    """★★★The one that was not cosmetic.

    The YAML carries two limiter contours and names them: the operational one
    (`base` since 2026-09-13, when the est2 GUI-v5 60-point `efit_w_pf` contour
    was removed) and `m-file` (the validation-era 48-point one, inner R ~ 1.30 m).
    `device.LIMITER_OPERATIONAL` selects the first; choosing another contour
    moves a limited boundary (measured once on #70754 between the GUI-v5 and
    m-file contours: psi_bry **-0.393 -> -0.415**).

    The JSON carried ONE unnamed 48-point contour — the m-file one.  So the
    browser and Python were limiting the plasma on different walls, and the
    difference had already been measured in this repository by someone who
    did not know the two files disagreed.

    ★The browser gets the OPERATIONAL contour and only that.  `fromFyo`
    concatenates every limiter unit it is given, which is right for a wall
    stored in pieces (ITER's First Wall + Divertor) and catastrophic for two
    ALTERNATIVE contours — it would weld a 60-point wall to a 48-point one.
    So an alternative contour must not travel in a browser document at all;
    the YAML keeps both because Python selects by name.
    """
    from fylite import device
    y, j = pair
    yu = {n: (r, z) for n, r, z in _limiter_units(y)}
    ju = _limiter_units(j)
    assert device.LIMITER_OPERATIONAL in yu, sorted(yu)
    assert len(ju) == 1, (
        f"the browser document carries {len(ju)} limiter units; `fromFyo` "
        f"concatenates them, so it must carry exactly the operational one")
    name, r, z = ju[0]
    assert name == device.LIMITER_OPERATIONAL, (
        f"the browser runs EAST on {name!r} while Python defaults to "
        f"{device.LIMITER_OPERATIONAL!r} — the two are different walls")
    assert (r, z) == yu[device.LIMITER_OPERATIONAL]


def test_the_vacuum_field_reference_agrees(pair):
    """`tf.r0` against `machine.r_centre` — the same nominal geometric centre.

    ★`b0` is deliberately NOT compared: the browser dialect requires a
    device-level `tf.b0`, and EAST does not have one — its toroidal field is
    a per-shot measurement (`data_source.mdsplus.btor_node`, `\\focs_it`).
    The JSON's 1.8 T is a nominal value for a page that must draw something;
    the YAML is right not to carry it as a machine constant.
    """
    y, j = pair
    #: ★★2026-09-13 (user ruling): tf.r0 <- machine.r_centre, the value fydoc records
    #: as `dev:rCentre`; the other recorded radii (tf page 1.7, the other g-file)
    #: sit in provenance as recorded-not-used.  Both forms must carry the used one.
    used = y["provenance"]["reference_radii"]["used"]["value"]
    assert float(j["tf"]["r0"]) == float(y["tf"]["r0"]) == float(y["machine"]["r_centre"]) == used


def test_the_grid_box_agrees(pair):
    """★The BOX, not the resolution.  `nr`/`nz` are a property of the
    calculation and live only in the browser document; the box is the
    machine's."""
    y, j = pair
    g, b = y["machine"]["default_grid"], j["fylite:grid"]
    assert (b["rmin"], b["rmax"], b["zmin"], b["zmax"]) == (
        g["r_min"], g["r_max"], g["z_min"], g["z_max"])


def test_the_lower_hybrid_launchers_are_the_same_two(pair):
    """★T-M15: the LH systems were Python-side only until 2026-08-24.

    ★What is compared is the four DECLARED fields (`@fyo-table DEVICE`), in
    order — a launcher's identity is its band, and two systems listed in the
    other order would hand the 2.45 GHz band to the 4.6 GHz launcher.  ★The
    MDSplus node names and the port letter beside them in the YAML are NOT
    compared and NOT carried: the browser cannot reach MDSplus
    (FYL-DESIGN-06), so they are a Python-side fact rather than a
    disagreement.
    """
    y, j = pair

    def rows(doc):
        return [(str(a["name"]), float(a["frequency"]),
                 float(a["fylite:max_power"]),
                 tuple(float(x) for x in a["fylite:n_parallel"]))
                for a in (doc.get("lh_antennas") or {}).get("antenna") or []]

    a, b = rows(y), rows(j)
    assert len(a) == len(b) == 2, (len(a), len(b))
    assert a == b


# --------------------------------------------------------------------------- #
# the open question this comparison surfaced                                  #
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(strict=True, reason=(
    "OPEN, needs a fact about EAST's PCS numbering that neither file states. "
    "Within `east_device.yaml`, a channel's `turns` (operational "
    "`gui_v5_pf_channels.turn`, channel order) and the elements nested "
    "under it (the BRSP circuit) disagree for 8 of 12 channels: channel 4 "
    "(BRSP_04) carries `turns: 140` and TWO elements (PF7 + PF9, 44 + 204 = "
    "248 turns), while channel 7 carries `turns: 248` and ONE element (a "
    "140-turn CS coil). The "
    "names+turns are self-consistent (six 140s, two 248s, two 60s, two 32s) "
    "and `device.turnfc()` reproduces the deck's TURNFC exactly; the elements "
    "are self-consistent with `pf_channel_elements` and with the browser's "
    "`fylite:channel_map`. So one of the two attachments is off by a "
    "permutation, and which one cannot be settled from inside this "
    "repository: it turns on whether the PCS Rogowski named PF4P sits on the "
    "lower CS coil or on the upper series pair. Until that is answered, "
    "`device.PF_TURNS[k]` must not be read as 'channel k's turns' — "
    "`turnfc()` and `io.raw` pair it with the same index throughout, which "
    "is why nothing has failed."))
def test_each_channels_turns_match_the_elements_nested_under_it(pair):
    """A channel's total turns is the sum of its elements' turns."""
    y, _ = pair
    bad = []
    for c in y["pf_active"]["coil"]:
        if c.get("function"):            #: fast coils carry no PCS channel turns
            continue
        total = sum(int(e["turns_with_sign"]) for e in c["element"])
        if total != int(c["turns"]):
            names = [e["fylite:name"] for e in c["element"]]
            bad.append(f"{c['name']}: turns={c['turns']} but element(s) "
                       f"{names} sum to {total}")
    assert not bad, "\n  ".join(bad)
