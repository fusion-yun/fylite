#!/usr/bin/env python3
"""Write `docs/reference/scenario.fyo.jsonld` — what a complete scenario IS, in fyo.

★★**Why a generated document and not a hand-written one.** Every path, unit and
rank below is read out of `python/fylite/_fyo_interface.py`, which is itself
generated from the kernel's declaration tables at build time.  A hand-kept copy
of a contract is not a contract: it is right once and wrong the first time
either side moves.  The gate `python/tests/test_scenario_jsonld.py` regenerates
and compares.

★**What the document answers**, and it is three questions, not one:

 1. **Which documents a scenario comprises** — a run point is not one file: the
    equilibrium and its transport ladder, the profiles, the sources, the
    launchers, and the summary of what came out.
 2. **Which slots carry a DD name and which carry a `fylite:` one.** The second
    kind is the kernel's own vocabulary, used where the IMAS DD has no home for
    the quantity; counting them per document is the honest measure of how far
    the ontology reaches.
 3. **What a real scenario needs that has NO slot at all.** CFEDR-class runs
    carry six species by name; the declaration has `ion_density` and
    `impurity_density` and nothing per species, so the kernel writes bare
    `species/n_D`-style paths.  Those are listed as `fylite:unmapped` with where
    each one is written, because a gap that is not written down is a gap that
    gets rediscovered.

★★**No restricted numbers ride here.** The binding section names the source
files of `FYDOC-CASE-20` by PATH and `sha256` — the way this ecosystem reaches
restricted data — and carries no value from them.  The case's profiles, flux map
and sources stay in fydoc under its release gate; a hash lets a holder verify a
copy, it does not disclose one.

    python3 tools/make-scenario-jsonld.py [--fydoc /path/to/fydoc] [--check]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/reference/scenario.fyo.jsonld"
sys.path.insert(0, str(ROOT / "python"))

#: the documents a complete scenario comprises, in the order a reader builds them.
#: ★`EQUILIBRIUM` and `LADDER` are both `fyo:equilibrium`: the first is the field
#: (psi map, F, boundary), the second the flux-surface ladder the transport runs
#: on.  They are separate tables because they are separately optional — a ray
#: trace needs the map and no ladder, a flux match the ladder and no map.
SCENARIO = ["EQUILIBRIUM", "LADDER", "CORE_PROFILES", "CORE_SOURCES",
            "EC_LAUNCHERS", "SUMMARY"]

#: Quantities a CFEDR-class scenario carries that have NO declared slot, with
#: where the kernel writes them today.  ★This list is a CLAIM about usage, not a
#: derivation, so each entry says where to check it; the gate checks the other
#: half — that none of them has quietly acquired a slot since.
UNMAPPED = [
    ("species/n_D", "the deuterium density", "kernel rust/fylite_ext/src/cfedr_s4.rs (the six-species deck)"),
    ("species/n_T", "the tritium density", "same"),
    ("species/n_He", "the thermal helium (ash) density", "same"),
    ("species/n_Ar", "the argon density", "same"),
    ("species/n_He_fast", "the fast-alpha density", "same"),
    ("species/z_Ar", "argon's mean charge state Z(T_e)", "same — a PROFILE, not a constant"),
    ("species/w_fast_alpha", "the fast alphas' stored energy density [J/m^3]",
     "same — the fast population has no temperature, so an equivalent Maxwellian is built from it"),
    ("pedestal", "the EPED pedestal solution (top position, width, height)",
     "carried as settings on the transport door, not as a document"),
]


def interface():
    import fylite._fyo_interface as fi
    return fi


def case20_binding(fydoc: pathlib.Path | None):
    """`FYDOC-CASE-20`'s source files by path and sha256 — no values.

    Read from the case's own `case.yaml` so the manifest cannot drift from the
    record the case book keeps; absent fydoc, the binding is left out and the
    document says so rather than carrying a stale copy.
    """
    if fydoc is None:
        return None
    y = fydoc / "cases/FYDOC-CASE-20-cfedr-hmode-15ma/case.yaml"
    if not y.is_file():
        return None
    text = y.read_text(encoding="utf-8")
    sums = dict(re.findall(r'^\s*"?([^":\n]+)"?:\s*([0-9a-f]{64})\s*$', text, re.M))
    #: which document each source file feeds — the mapping this whole page is about
    feeds = {
        "H model 15MA 20240522/statefile_1.200000E+01.nc":
            ["fyo:equilibrium", "fyo:core_profiles", "fyo:core_sources", "fyo:summary"],
        "H model 15MA 20240522/HCD_profiles_from_statefile.nml": ["fyo:core_sources"],
        "H model 15MA 20240522/toray_inputs/echin": ["fyo:ec_launchers"],
        "H model 15MA 20240522/toray_inputs/psiin": ["fyo:equilibrium"],
        "H model 15MA 20240522/gfile_efit": ["fyo:equilibrium"],
        "H model 15MA 20240522/EPED/peddata": ["fylite:pedestal"],
    }
    out = []
    for rel, types in feeds.items():
        sha = sums.get(rel)
        out.append({"@id": f"fylite:corpus/FYDOC-CASE-20/{rel}",
                    "fylite:path": f"cases/FYDOC-CASE-20-cfedr-hmode-15ma/corpus/{rel}",
                    "fylite:sha256": sha,
                    "fylite:feeds": types,
                    "fylite:registered": sha is not None})
    return out


def build(fydoc: pathlib.Path | None) -> str:
    fi = interface()
    docs = []
    for table in SCENARIO:
        d = fi.TABLES[table]
        slots = []
        for key, v in d["slots"].items():
            slots.append({"fylite:key": key, "fylite:path": v["path"],
                          "fylite:units": v["units"], "fylite:rank": v["rank"],
                          "fylite:namespaced": "fylite:" in v["path"]})
        docs.append({
            "@id": f"fylite:scenario/document/{table.lower()}",
            "@type": d["type"],
            "fylite:table": table,
            "fylite:slot_count": len(slots),
            "fylite:namespaced_count": sum(1 for s in slots if s["fylite:namespaced"]),
            "fylite:slots": slots,
        })
    doc = {
        "@context": {
            "fyo": "https://fusion-yun.github.io/fyo/latest/",
            "fylite": "urn:fylite:",
            "dcterms": "http://purl.org/dc/terms/",
        },
        "@id": "fylite:scenario",
        "@type": "fylite:ScenarioShape",
        "dcterms:description":
            "The documents a complete scenario comprises, with every declared path, "
            "unit and rank, which of them carry a fylite: term rather than a DD name, "
            "and what a CFEDR-class run needs that has no slot at all.",
        "dcterms:source": "python/fylite/_fyo_interface.py (generated from the kernel's tables)",
        "fylite:interface_revision": fi.REVISION,
        "fylite:interface_digest": fi.DIGEST,
        "fylite:documents": docs,
        "fylite:unmapped": [
            {"fylite:path": p, "dcterms:description": what, "dcterms:source": where}
            for p, what, where in UNMAPPED
        ],
    }
    binding = case20_binding(fydoc)
    doc["fylite:binding"] = {
        "@id": "fylite:scenario/FYDOC-CASE-20",
        "dcterms:description":
            "CFEDR conventional H-mode 15 MA, integrated modelling V1 (ONETWO V5.8.2, t = 12 s). "
            "Restricted: the values live in fydoc under its release gate and are reached by "
            "path and sha256, never copied here.",
        "fylite:case": "FYDOC-CASE-20",
        "fylite:sources": binding if binding is not None else [],
        "fylite:sources_read": binding is not None,
    }
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fydoc", type=pathlib.Path, default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    fydoc = a.fydoc
    if fydoc is None:
        for c in (ROOT.parent / "fydoc",):
            if (c / "cases").is_dir():
                fydoc = c
    text = build(fydoc)
    if a.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("identical" if same else "DIFFERS")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
