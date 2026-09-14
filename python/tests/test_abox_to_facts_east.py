"""EAST built from the A-Box (``tools/abox-to-facts.py``, ``build("east")``)
against the retired hand card (kernel ``machine_desc/east/east_device.yaml`` at
``71c7cef``, read from git once the file is gone).

P2a/P2b of the machine_desc retirement (user rulings 2026-09-13): EAST is now
built only this way.  Group by group: counts, names and order exact; numbers to
``rel 1e-9`` unless the table below says otherwise.  Skips (with the reason)
when fydoc or the kernel card is not reachable.

★★★The supply-pairing gate is the reason this module exists: the kernel
(``case.rs`` breakdown) and ``pulse.channel_limits`` index ``pf_active/supply``
by ELEMENT position and only check the length, and fydoc lists its 14 supplies
in fydoc numbering.  A mis-ordered list passes the length check and mis-pairs
every voltage limit past the third element — so ``supply[i]`` is asserted to
belong to element ``i`` BY CENTRE, and to equal the card's order and values.

Intentional differences from the card (asserted where assertable)
=================================================================

Rows that P1 (fydoc, 2026-09-13) made EQUAL to the card are gone from this
table and asserted as equal below: PF channel ``turns`` + ``efit_index``
(``gui_v5_pf_channels``) and ``bit_error`` (``efit_w_pf_channel_fit.bitfc``), LH
``max_power``/``n_parallel`` and EC ``max_power`` (``dev:powerMax`` /
``dev:nParallelRange``), EC ``mode``, POINT ``laser_wavelength``,
``machine.fylite:b0`` (``tf.b0``) and the ``m-file`` limiter (provider
``m093060``).  What is left is intentional, a ruling, or a divergence fydoc
itself names.

★★2026-09-13 (user ruling: est2 removed at every layer): the retired card's
magnetics probes / loops and its operational limiter were the est2 array
(``efit_w_pf``: 79 probes + 35 loops with per-channel weight / bit_error, the
GUI-v5 60-point contour).  That provider is gone, so the build is the manifest
default (magnetics ``east_new`` in chain ``east``, wall ``base``) and those rows
are no longer compared; ``magnetics.pcs``, the ``m-file`` contour and the vessel
still are.

====================================  ===========================================  ==========================
card field                            build                                        why / waits on
====================================  ===========================================  ==========================
reference_discharge / slices(_prov.)  not carried                                  experiment data (ruling)
data_source.mdsplus.server            absent (``fylite:absent.server``)            deployment setting (ruling)
data_source.mdsplus.ip_node ``\\ipm``  absent; default binding is ``\\PCRL01`` in    shot-reading key: node not
                                      pcs_east, main-tree node not chosen upstream chosen upstream (ruling)
btor_node ``\\focs_it``                ``\\FOCS_IT`` (read rule, current era)        MDSplus is case-blind
magnetics.pcs positions               A-Box G-07 correction: 12/38 probes differ   card is stale; A-Box wins
magnetics.pcs count/note              not carried (``len`` is the count)           no reader
pf_active coil (channel) names        ``BRSP_01..12`` (circuit names)              PCS names PF1P.. not upstream
channel ``bit_error``                 equal BY LIST POSITION; fydoc states bitfc   DIVERGENT: fcoil order vs
                                      in EFIT fcoil order (``fylite:bit_error_note``) channel position (card too)
channel/element ``resistance``        recomputed η·Σ2πrN²/(wh) on deck geometry    ruling 2026-09-13
element centres r/z                   yu 5-6 figures; card rounded (abs 5e-5)      card print rounding
element ``fylite:name`` (6 CS coils)  fydoc (base) numbering, PF1/3/5 up, 2/4/6    fydoc CS numbering (ruling)
                                      down; card deck names PF1/2/3 up, 4/5/6 down
element ``fylite:deck_row``           not carried                                  no reader
pf_active count / note                not carried                                  no reader
supply description                    fydoc text                                   prose
limiter outline                       abs 1e-5 (A-Box vs card max 5e-6)            card print rounding
limiter unit extras (provenance/      ``fylite:operational``/``provider``/upstream  prose
count/operational_note)               name only
pf_passive a2 = 0 segments            abs 1e-9 as well as rel 1e-9                 relative test on zero
pf_passive count / shell / notes      not carried                                  no reader
lh/ic/ec port, nodes; ic level,       not carried                                  no production reader (ruling)
source_power, frequency_range, ports
ec ``mode`` 1                         equal — ★fydoc marks it ``divergent`` (O=1   DIVERGENT upstream (X2
                                      in imas/3 vs the paper's X2 heating)          heating per xu2025ech)
interferometer names ``point_n1``     binding node ``POINT_N1``                    case only
first_point.r 2.5                     equal, from PROGRAM_SIDE (upstream 0.0 is a  program-side (GUI_v5 :658):
                                      symbolic endpoint; second_point r 3.0 kept)  the cast origin, outboard
polarimeter names ``point_f1``        binding node ``POINT_F1`` (fydoc binding     case only
                                      added 2026-09-14)
polarimeter baseline -0.9 / 0.01      equal, from PROGRAM_SIDE                     program-side (GUI_v5 :388)
operational efit_w_pf_channel_fit /   not repeated in ``operational`` (carried on  one statement per fact
gui_v5_pf_channels                    the channels; ``fylite:carried_on_channels``)
solver_dims / default_grid box /      PROGRAM_SIDE table in the generator          program-side (ruling)
faraday_constant / fylite:ui
====================================  ===========================================  ==========================
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "abox-to-facts.py"


def _tool():
    spec = importlib.util.spec_from_file_location("abox_to_facts", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


A2F = _tool()
FYDOC = Path(os.environ.get("FYDOC") or A2F.FYDOC)


#: the kernel commit whose card the gap map and this module compare against
#: (K-2 batch 1); read from git when the retired file is gone from the worktree
CARD_REV = "71c7cef"
CARD_PATH = "machine_desc/east/east_device.yaml"


def _retired_card() -> str | None:
    """The retired card's TEXT, for comparison ONLY — it is no source of anything.

    ★Its own lookup, not the generator's: the generator no longer knows where a
    kernel checkout is (machine_desc retired, user ruling 2026-09-13).  The file
    is being deleted from the kernel worktree, so a missing file falls back to
    ``git show CARD_REV:CARD_PATH`` — the comparison is against that fixed card.
    """
    import subprocess
    env = os.environ.get("FYLITE_KERNEL") or os.environ.get("FYLITE_KERNEL_REPO")
    for k in ([Path(env)] if env else []) + [ROOT.parent / "fylite_kernel"]:
        card = k / CARD_PATH
        if card.is_file():
            return card.read_text(encoding="utf-8")
        if (k / ".git").exists():
            r = subprocess.run(["git", "-C", str(k), "show", f"{CARD_REV}:{CARD_PATH}"],
                               capture_output=True, text=True)
            if r.returncode == 0 and r.stdout:
                return r.stdout
    return None


CARD = _retired_card()

pytestmark = [
    pytest.mark.skipif(not (A2F.device_root(FYDOC) / "east").is_dir(),
                       reason=f"no fydoc EAST A-Box under {FYDOC} (set $FYDOC)"),
    pytest.mark.skipif(CARD is None,
                       reason=f"no kernel checkout with {CARD_PATH} in its worktree or at "
                              f"{CARD_REV} (set $FYLITE_KERNEL)"),
]

REL = 1e-9


@pytest.fixture(scope="module")
def doc():
    #: ★★2026-09-13 (measurement-chain ruling, est2 removed): the manifest defaults —
    #: magnetics `east_new` (chain `east`), wall `base`; no provider is named
    return A2F.build_east_from_abox(FYDOC)


@pytest.fixture(scope="module")
def card():
    import yaml
    return yaml.safe_load(CARD)


@pytest.fixture(scope="module")
def base():
    dev_dir = A2F.device_root(FYDOC) / "east"
    manifest, _ = A2F._manifest(dev_dir)
    return A2F._load(A2F._provider_file(dev_dir, manifest, "pf_active", "base"))


def _num(a, b, *, abs_=0.0):
    assert a == pytest.approx(b, rel=REL, abs=abs_), (a, b)


def _elements(coils):
    return [e for c in coils for e in c["element"]]


def _rect(e):
    return e["geometry"]["rectangle"]


def _base_by_centre(base, rect):
    hits = [c for c in base["coil"]
            if abs(c["element"][0]["geometry"]["rectangle"]["r"] - rect["r"]) < 1e-4
            and abs(c["element"][0]["geometry"]["rectangle"]["z"] - rect["z"]) < 1e-4]
    assert len(hits) == 1, rect
    return hits[0]


# --------------------------------------------------------------------------- #
# pf_active                                                                   #
# --------------------------------------------------------------------------- #
def test_pf_grouping_counts_and_geometry(doc, card):
    got, want = doc["pf_active"]["coil"], card["pf_active"]["coil"]
    assert len(got) == len(want) == 14
    assert [len(c["element"]) for c in got] == [len(c["element"]) for c in want]
    ge, we = _elements(got), _elements(want)
    assert len(ge) == len(we) == 16
    for g, w in zip(ge, we):
        gr, wr = _rect(g), _rect(w)
        _num(gr["r"], wr["r"], abs_=5e-5)          # card centres print-rounded
        _num(gr["z"], wr["z"], abs_=5e-5)
        _num(gr["width"], wr["width"])
        _num(gr["height"], wr["height"])
        _num(g["turns_with_sign"], w["turns_with_sign"])
        assert (g["fylite:a1"], g["fylite:a2"]) == (w["fylite:a1"], w["fylite:a2"])
    assert [c["name"] for c in got[:12]] == [f"BRSP_{i:02d}" for i in range(1, 13)]
    assert [c["name"] for c in got[12:]] == ["IC1", "IC2"] == [c["name"] for c in want[12:]]


def test_element_names_are_fydoc_numbering(doc, card, base):
    """Six CS coils are named differently by deck and fydoc; the rest agree."""
    for g, w in zip(_elements(doc["pf_active"]["coil"]), _elements(card["pf_active"]["coil"])):
        assert g["fylite:name"] == _base_by_centre(base, _rect(g))["name"]
        if abs(_rect(g)["r"] - 0.62866) > 1e-4:     # not a CS coil
            assert g["fylite:name"] == w["fylite:name"]


def test_ic_coils_are_fast_coils(doc, card):
    got = {c["name"]: c for c in doc["pf_active"]["coil"]}
    for name in ("IC1", "IC2"):
        want = next(c for c in card["pf_active"]["coil"] if c["name"] == name)
        assert got[name]["function"] == want["function"]
        assert [f["name"] for f in got[name]["function"]] == ["b_field_fb"]
        assert _rect(got[name]["element"][0]) == _rect(want["element"][0])
        _num(got[name]["resistance"], want["resistance"])
    assert not any(c.get("function") for c in doc["pf_active"]["coil"][:12])


def test_supply_i_drives_element_i_by_centre(doc, card, base):
    """★★★The pairing gate (K-2 owner): not a length check."""
    supply = doc["pf_active"]["supply"]
    pf_elements = _elements([c for c in doc["pf_active"]["coil"] if not c.get("function")])
    assert len(supply) == len(pf_elements) == 14
    base_supply = {s["name"]: s for s in base["supply"]}
    for i, (s, e) in enumerate(zip(supply, pf_elements)):
        owner = _base_by_centre(base, _rect(e))
        assert s["name"] == f"PS_{owner['name']}", (i, s["name"], owner["name"])
        assert s == base_supply[s["name"]]
    #: and the card's order and values
    want = card["pf_active"]["supply"]
    assert [s["name"] for s in supply] == [s["name"] for s in want] == [
        "PS_PF1", "PS_PF3", "PS_PF5", "PS_PF7", "PS_PF9", "PS_PF11", "PS_PF13",
        "PS_PF2", "PS_PF4", "PS_PF6", "PS_PF8", "PS_PF10", "PS_PF12", "PS_PF14"]
    for s, w in zip(supply, want):
        for key in ("current_limit_max", "voltage_limit_max", "time_constant"):
            _num(s[key], w[key])


def test_circuit_is_remapped_by_centre(doc, card):
    assert doc["pf_channel_elements"] == card["pf_channel_elements"]
    flat = _elements(doc["pf_active"]["coil"])
    names = [[flat[t["element"]]["fylite:name"] for t in row] for row in doc["pf_channel_elements"]]
    assert names[3] == ["PF7", "PF9"]            # BRSP_04 — not PF4+PF5 (fydoc list order)
    assert names[9] == ["PF8", "PF10"]           # BRSP_10
    #: each channel's elements are exactly that channel coil's elements
    k = 0
    for c, row in zip(doc["pf_active"]["coil"], doc["pf_channel_elements"]):
        assert [t["element"] for t in row] == list(range(k, k + len(c["element"])))
        k += len(c["element"])


def _r_model(coil, eta_uohm_m=0.017):
    return eta_uohm_m * 1e-6 * sum(
        2 * math.pi * _rect(e)["r"] * e["turns_with_sign"] ** 2 / (_rect(e)["width"] * _rect(e)["height"])
        for e in coil["element"])


def test_resistance_is_recomputed_on_the_carried_geometry(doc, card, base):
    """Ruling 2026-09-13: R = η·Σ2πrN²/(wh) on the deck cross-sections, η from base."""
    from fylite import device
    assert device.coil_resistivity_uohm_m(doc) == 0.017
    assert device.coil_resistivity_uohm_m(card) == 0.017
    assert "recomputed" in doc["pf_active"]["fylite:resistance_note"].lower()
    base_r = {c["name"]: c["resistance"] for c in base["coil"]}
    for g, w in zip(doc["pf_active"]["coil"], card["pf_active"]["coil"]):
        assert g["name"][-3:] == w["name"][-3:] or g["name"].startswith("BRSP")
        if g.get("function"):                       # K-2: the provider's R, its own geometry
            assert g["resistance"] == base_r[g["name"]]
            assert f"{g['resistance']:.6g}" == f"{w['resistance']:.6g}"
            continue
        _num(g["resistance"], _r_model(g))
        #: the card printed the same formula on ITS rectangles to six figures …
        assert f"{_r_model(w):.6g}" == f"{w['resistance']:.6g}"
        same_rects = all(_rect(a) == _rect(b) for a, b in zip(g["element"], w["element"]))
        if same_rects:
            assert f"{g['resistance']:.6g}" == f"{w['resistance']:.6g}"
        else:
            #: … and 4 channels (PF7/9, PF8/10, PF11, PF12) sit on centres the card
            #: print-rounded (≤3e-5 m), which moves R by ≤1e-5 relative
            assert g["resistance"] == pytest.approx(w["resistance"], rel=2e-5)


# --------------------------------------------------------------------------- #
# magnetics / wall / pf_passive                                               #
# --------------------------------------------------------------------------- #
def test_magnetics_pcs_family_and_the_default_group(doc, card):
    """★2026-09-13 (est2 removed): the card's probe / loop arrays were the est2 array and
    are not compared any more.  What stays comparable is the PCS family (provider-independent)
    — and the default group itself says its chain and declares the per-channel fit absent."""
    mag = doc["magnetics"]
    assert (mag["fylite:provider"], mag["measurement_chain"]) == ("east_new", "east")
    assert mag["fylite:source"].endswith("providers/magnetics/east_new.jsonld")
    assert (len(mag["b_field_pol_probe"]), len(mag["flux_loop"])) == (79, 75)
    assert not any("weight" in c or "bit_error" in c for c in (*mag["b_field_pol_probe"], *mag["flux_loop"]))
    assert {"weight", "bit_error"} <= set(mag["fylite:absent"])
    assert "fylite:channel_fit_source" not in mag
    gp, wp = mag["pcs"]["b_field_pol_probe"], card["magnetics"]["pcs"]["b_field_pol_probe"]
    assert [p["name"] for p in gp] == [p["name"] for p in wp]
    same = sum(1 for g, w in zip(gp, wp)
               if g["position"] == pytest.approx(w["position"], abs=1e-9)
               and g["angle"] == pytest.approx(w["angle"], abs=1e-9))
    assert same == 26                              # 12 carry the A-Box G-07 correction


def test_wall(doc, card):
    gu = doc["wall"]["description_2d"][0]["limiter"]["unit"]
    wu = card["wall"]["description_2d"][0]["limiter"]["unit"]
    #: the manifest default (operational, `base` since the est2 contour was removed) first,
    #: then the m093060 provider under the name the readers select by (`recon_rs` defaults
    #: to "m-file").  The card's operational contour was the est2 `efit_w_pf` one — not compared.
    assert [u["name"] for u in gu] == ["base", "m-file"]
    assert [u["name"] for u in wu] == ["efit_w_pf", "m-file"]
    assert [u["fylite:provider"] for u in gu] == ["base", "m093060"]
    for g, w, n in ((gu[1], wu[1], 48),):
        for k in ("r", "z"):
            assert len(g["outline"][k]) == len(w["outline"][k]) == n
            for a, b in zip(g["outline"][k], w["outline"][k]):
                assert a == pytest.approx(b, abs=1e-5)
    gv = doc["wall"]["description_2d"][0]["vessel"]["unit"]
    wv = card["wall"]["description_2d"][0]["vessel"]["unit"]
    assert len(gv) == len(wv) == 40
    for g, w in zip(gv, wv):
        ge, we = g["element"][0], w["element"][0]
        for k in ("r", "z", "width", "height"):
            _num(_rect(ge)[k], _rect(we)[k], abs_=1e-9)
        for k in ("fylite:a1", "fylite:a2"):
            _num(ge[k], we[k], abs_=1e-9)


def test_pf_passive(doc, card):
    got, want = doc["pf_passive"], card["pf_passive"]
    for group, n in (("outer_shell", 40), ("passive_plates", 10)):
        assert len(got[group]["element"]) == len(want[group]["element"]) == n
        for g, w in zip(got[group]["element"], want[group]["element"]):
            assert len(g) == len(w) == 6
            for a, b in zip(g, w):
                _num(a, b, abs_=1e-9)
    for group in ("vessel", "outer_shell", "passive_plates"):
        _num(got[group]["resistivity_uohm_m"], want[group]["resistivity_uohm_m"])
    _num(doc["fylite:vessel_resistivity_uohm_m"], card["fylite:vessel_resistivity_uohm_m"])


# --------------------------------------------------------------------------- #
# operational / POINT / H&CD / data_source / program side                     #
# --------------------------------------------------------------------------- #
def test_operational(doc, card):
    got, want = doc["operational"], card["operational"]
    assert got["probe_gate"] == want["probe_gate"]
    for nl in ("gui_v5_fig", "point_density_fit", "fit_control"):
        assert list(got[nl]) == list(want[nl])
        assert got[nl] == want[nl]


def test_point_chords(doc, card):
    for ids in ("interferometer", "polarimeter"):
        got, want = doc[ids]["channel"], card[ids]["channel"]
        assert len(got) == len(want) == 11
        for g, w in zip(got, want):
            _num(g["line_of_sight"]["first_point"]["z"], w["line_of_sight"]["first_point"]["z"],
                 abs_=1e-12)
            _num(g["line_of_sight"]["theta"], w["line_of_sight"]["theta"], abs_=1e-12)
            #: the cast origin (program-side, GUI_v5 :658) — outboard of the plasma, or
            #: `code/chords` drops the outboard edge
            _num(g["line_of_sight"]["first_point"]["r"], w["line_of_sight"]["first_point"]["r"],
                 abs_=1e-12)
    assert [c["name"].casefold() for c in doc["interferometer"]["channel"]] == \
        [c["name"].casefold() for c in card["interferometer"]["channel"]]
    #: node names from the fydoc bindings, paired by chord number (N<k> and F<k> on the same chord)
    assert [c["name"] for c in doc["interferometer"]["channel"]] == [f"POINT_N{i}" for i in range(1, 12)]
    assert [c["name"] for c in doc["polarimeter"]["channel"]] == [f"POINT_F{i}" for i in range(1, 12)]
    assert [c["name"].casefold() for c in doc["polarimeter"]["channel"]] == \
        [c["name"].casefold() for c in card["polarimeter"]["channel"]]
    _num(doc["polarimeter"]["faraday_constant"], card["polarimeter"]["faraday_constant"])
    _num(doc["interferometer"]["laser_wavelength"], card["interferometer"]["laser_wavelength"])
    #: program-side (PROGRAM_SIDE['point_baseline']), equal to the retired card's
    assert doc["polarimeter"]["baseline"] == card["polarimeter"]["baseline"]
    assert "fylite:absent" not in doc["polarimeter"]


def test_hcd(doc, card):
    for ids, key, optional in (("lh_antennas", "antenna", ("fylite:max_power", "fylite:n_parallel")),
                               ("ic_antennas", "antenna", ()),
                               ("ec_launchers", "beam", ("mode", "fylite:max_power"))):
        got, want = doc[ids][key], card[ids][key]
        assert [a["name"] for a in got] == [a["name"] for a in want]
        for g, w in zip(got, want):
            if "frequency" in w:
                _num(g["frequency"], w["frequency"])
            for opt in optional:                  #: ★P1: all carried now
                assert g[opt] == pytest.approx(w[opt], rel=REL), (ids, opt)
            #: no production reader (ruling): not carried
            assert not {"level", "fylite:port", "fylite:nodes"} & set(g)
        assert not {"fylite:port", "fylite:ports", "fylite:source_power",
                    "fylite:frequency_range"} & set(doc[ids])
        assert "fylite:absent" not in doc[ids]


def test_pf_channel_fit_settings(doc, card):
    """`turns` / `efit_index` equal per channel; `bit_error` equal BY POSITION.

    ★Named divergence: fydoc states bitfc in EFIT fcoil order, the card (and
    this document) carry it by list position — the note says so.
    """
    got = [c for c in doc["pf_active"]["coil"] if not c.get("function")]
    want = [c for c in card["pf_active"]["coil"] if not c.get("function")]
    assert len(got) == len(want) == 12
    for g, w in zip(got, want):
        for key in ("turns", "efit_index"):
            assert g[key] == w[key], (g["name"], key)
        _num(g["bit_error"], w["bit_error"])
    assert "fcoil order" in doc["pf_active"]["fylite:bit_error_note"]
    assert "fylite:absent" not in doc["pf_active"]
    carried = doc["operational"]["fylite:carried_on_channels"]
    assert set(carried) == {"efit_w_pf_channel_fit", "gui_v5_pf_channels"}
    assert not set(carried) & set(doc["operational"])


def _published_docs() -> dict:
    """The PUBLISHED EAST document(s) readers load: the facts-path `east.jsonld`
    and, when the runtime has facts compiled in, the embedded copy."""
    from fylite import facts
    out = {}
    for root in facts.roots():
        p = root / "device" / "east.jsonld"
        if p.is_file():
            out[str(p)] = json.loads(p.read_text(encoding="utf-8"))
            break
    try:
        text = facts.bundled_doc("device", "east")
    except Exception:           # a build without the runtime library
        text = None
    if text:
        out["facts.rs (bundled)"] = json.loads(text)
    return out


def test_the_published_document_keeps_fast_coils_and_the_channel_map():
    """★★The gate that was missing (2026-09-13): everything above checked
    `build()`'s IN-MEMORY document, while readers load the DERIVED `east.jsonld`
    (`write_document` → `pf_flatten` / `channel_map`), which dropped IC1/IC2's
    `function` and the `pf_channel_elements` rows — the start design then solved
    16 channels.  Asserted on what is published, with the readers' own tests."""
    from fylite import device
    docs = _published_docs()
    if not docs:
        pytest.skip("no published EAST document on the facts path (run abox-to-facts --all)")
    for where, pub in docs.items():
        coils = pub["pf_active"]["coil"]
        fast = [c["name"] for c in coils if device.is_fast_coil(c)]
        assert fast == ["IC1", "IC2"], (where, fast)
        pf_elements = sum(len(c["element"]) for c in coils if not device.is_fast_coil(c))
        assert pf_elements == 14, where
        rows = pub.get("pf_channel_elements")
        assert isinstance(rows, list) and len(rows) == 12, where
        #: `case.rs::device_coils` refuses an index outside the non-fast elements
        assert sorted(t["element"] for row in rows for t in row) == list(range(14)), where
        assert [[[t["element"], t["weight"]] for t in row] for row in rows] == \
            pub["fylite:channel_map"], where
        #: and the Python reader sees the same 12 channels
        device.use_device(pub)
        try:
            assert len(device.pf_channel_map()) == 12, where
        finally:
            for k in list(device.__dict__):
                if k in device._DERIVED_NAMES:
                    device.__dict__.pop(k, None)
            device._DERIVED = None


def test_vacuum_field_and_reference_radius(doc, card):
    _num(doc["machine"]["fylite:b0"], card["machine"]["fylite:b0"])
    #: user ruling 2026-09-13: tf.r0 <- machine.r_centre (the card's convention),
    #: the other recorded radii kept in provenance with the reason they are unused
    assert doc["tf"]["r0"] == doc["machine"]["r_centre"] == card["machine"]["r_centre"] == 1.75
    radii = doc["provenance"]["reference_radii"]
    assert radii["used"]["source"].endswith("tf.jsonld dev:rCentre")
    assert set(radii["used"]["for"]) == {"machine.r_centre", "tf.r0"}
    unused = {r["value"]: r for r in radii["recorded_not_used"]}
    assert set(unused) == {1.7, 1.79999995}, sorted(unused)
    assert unused[1.7]["source"].endswith("tf.jsonld r0")
    assert all(r["why"] for r in radii["recorded_not_used"])


def test_data_source(doc, card):
    got, want = doc["data_source"]["mdsplus"], card["data_source"]["mdsplus"]
    assert got["tree"] == want["tree"]
    assert got["pcs_tree"] == want["pcs_tree"]
    assert got["btor_node"].casefold() == want["btor_node"].casefold()
    assert "server" not in got and "server" in got["fylite:absent"]
    assert "ip_node" in got or "ip_node" in got["fylite:absent"]


def test_no_address_and_no_experiment_data(doc):
    text = json.dumps(doc, ensure_ascii=False)
    assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text), "an IP address in the document"
    for key in ("fylite:reference_discharge", "fylite:slices", "fylite:slices_provenance"):
        assert key not in doc


def test_the_reader_derives_the_built_document(doc, card, monkeypatch):
    """No server / main-tree Ip / POINT wavelength+baseline: loads, refuses at use by name."""
    from fylite import device
    got = device._derive(doc)
    assert "MDS_SERVER" not in got and "MDS_TREE" in got and "POINT_NE_NODES" in got
    #: P1 fills fydoc while this runs: each name is present exactly when its field is
    carried = {"POINT_LASER_LAMBDA": "laser_wavelength" in doc["interferometer"],
               "POINT_BASELINE_S": "baseline" in doc["polarimeter"],
               "MDS_IP": "ip_node" in doc["data_source"]["mdsplus"],
               "LH_SYSTEMS": all("fylite:max_power" in a and "fylite:n_parallel" in a
                                 for a in doc["lh_antennas"]["antenna"]),
               "ECRH_SYSTEMS": all("mode" in b and "fylite:max_power" in b
                                   for b in doc["ec_launchers"]["beam"])}
    for name, has in carried.items():
        assert (name in got) == has, name
    missing = [n for n, has in carried.items() if not has]
    assert device._derive(card)["MDS_SERVER"] == card["data_source"]["mdsplus"]["server"]
    monkeypatch.setattr(device, "_DERIVED", None)
    for env in (device.MDSIP_ENV, "KEFIT_MDS_SERVER"):
        monkeypatch.delenv(env, raising=False)
    device.use_device(doc)
    try:
        assert device.mdsip_server() is None
        assert device.mdsip_server("h:1") == "h:1"
        for name in missing:                      # refused at use, naming the field
            with pytest.raises(device.MachineDataMissing,
                               match=re.escape(device._MISSING_WHERE[name].split()[0])):
                getattr(device, name)
        from fylite.io import mds
        with pytest.raises(mds.MdsError, match="FYLITE_MDSIP_SERVER"):
            mds._server()
    finally:
        for k in got:
            device.__dict__.pop(k, None)
        monkeypatch.setattr(device, "_DERIVED", None)


def test_program_side(doc, card):
    for key in ("nw", "nh", "nfcoil"):
        assert doc["solver_dims"][key] == card["solver_dims"][key]
    #: ★2026-09-13: probe / loop counts are the resolved magnetics group's, not solver_dims'
    assert not {"nsilop", "nprobe"} & set(doc["solver_dims"])
    for key in ("r_min", "r_max", "z_min", "z_max"):
        assert doc["machine"]["default_grid"][key] == card["machine"]["default_grid"][key]
    assert doc["fylite:ui"] == card["fylite:ui"]
    for g in A2F.REQUIRED:
        assert g in doc
    assert all(math.isfinite(v) for v in doc["machine"].values() if isinstance(v, float))
