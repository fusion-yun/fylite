#!/usr/bin/env python3
"""Export one admitted fydoc case as ONE fyo/JSON-LD scenario `fy` can re-run.

Knows the two CFEDR cases (`CASES`): FYDOC-CASE-21 (20 MA, with TORAY's own
namelist) and FYDOC-CASE-20 (15 MA, EC power from the summary's `ech` line).

★What this is.  A `fyo:ScenarioSpecification` whose inputs are INLINE documents
(equilibrium · core_profiles · core_sources · ec_launchers, built from the case's
own files) and whose process is an ordered list of steps (`has_occurrent_part`):

    ladder  ->  (steady_current, steady_equilibrium) x rounds  ->  rf_ray

Each step names its code, its parameters and its ports; the runtime's stepped
runner (`fylite_runtime::case::run_steps`, reached by `fy run <file>` and by
`fylite.io.fydoc.case_json`) chains them: a bare `{id: "<step>/<ids>"}` binding
names an earlier step's document, `fylite:carry_forward` hands every produced
IDS on.  One file, no side files, nothing to resolve.

★★What this is NOT.  The case's values are `release: internal` (fydoc's gate):
this script READS them from a fydoc checkout named on the command line and
WRITES the scenario where `-o` says — into the caller's workspace, never into
this repository.  Every source file is sha256-checked against the case's
`case.yaml` before a number is taken from it, so the export is reproducible
against a registered body and refuses a changed one.  The scenario records the
paths and checksums it was built from (provenance), which is how a body under
`cases/` is reached: path + sha256, never a link.

Numbers that are not in the files are not invented:
  * the EC branch (O/X) is not declared by any TORAY input; `--mode` states it,
    and the default `O` is the branch the kernel's oracle gate identified from
    TORAY's own output on this case (fylite_kernel
    `tests/test_cfedr_toray_oracle.py`, 2026-09-11) — recorded as such;
  * the launched power is TORAY's namelist `POWINC` (6e13, and TORAY's own
    `delpwr` starts at that sum over its 30 rays); read as erg/s it is 6 MW,
    a tenth of ONETWO's `inone` `rfpow(4)` = 60 MW that the summary's `ech`
    line delivers (59.94 MW).  The factor sits between two machine-written
    files and is NOT resolved here; the summary total is recorded beside the
    beam.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import re
import sys

import numpy as np

CASE_DEFAULT = "FYDOC-CASE-21-cfedr-hmode-20ma"
#: the admitted CFEDR cases this exporter knows: the files under each case's
#: `corpus/` it reads (every one sha256-checked against `case.yaml`).  CASE-20
#: delivers no `toray.in`: its EC power is the summary's `ech` line.
CASES = {
    "FYDOC-CASE-21-cfedr-hmode-20ma": {
        "state": "CFEDR_260114/ONETWO/FILES/statefile_3.000000E+01.nc",
        "echin": "CFEDR_260114/ONETWO/FILES/toray_inputs/echin",
        "nml": "CFEDR_260114/ONETWO/FILES/auxFILES/toray.in",
        "summary": "CFEDR_260114/ONETWO/FILES/summary",
        "mode_note": "the branch fylite_kernel tests/test_cfedr_toray_oracle.py identified from TORAY's own |N| on this case (2026-09-11)",
    },
    "FYDOC-CASE-20-cfedr-hmode-15ma": {
        "state": "H model 15MA 20240522/statefile_1.200000E+01.nc",
        "echin": "H model 15MA 20240522/toray_inputs/echin",
        "nml": None,
        "summary": "H model 15MA 20240522/summary",
        "mode_note": "the branch fylite_kernel tests/test_cfedr_ec_against_the_delivery.py inferred from echin's slot 7, "
                     "the X branch not absorbing at all on this equilibrium (2026-09-11)",
    },
}
FYO = "https://fusion-yun.github.io/fyo/latest/"
SPO = "https://w3id.org/spo/"


# --------------------------------------------------------------------------- #
# the sources, checked before they are read
# --------------------------------------------------------------------------- #

def sha_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registered_shas(case_dir: pathlib.Path) -> dict[str, str]:
    """`case.yaml` keys its checksums by the path under `corpus/` — quoted
    (CASE-21) or bare (CASE-20, whose paths carry spaces but no colon)."""
    text = (case_dir / "case.yaml").read_text(encoding="utf-8")
    out = {m.group(1): m.group(2) for m in re.finditer(r'^\s*"([^"]+)":\s*([0-9a-f]{64})\s*$', text, re.M)}
    out.update({m.group(1).strip(): m.group(2)
                for m in re.finditer(r'^\s{4}([^"#\n][^:\n]*):\s*([0-9a-f]{64})\s*$', text, re.M)})
    return out


def checked_sources(case_dir: pathlib.Path) -> dict[str, tuple[pathlib.Path, str]]:
    files = CASES.get(case_dir.name)
    if files is None:
        sys.exit(f"{case_dir.name}: not one of the cases this exporter knows ({', '.join(CASES)})")
    reg = registered_shas(case_dir)
    out = {}
    for key, rel in files.items():
        if key == "mode_note" or rel is None:
            continue
        path = case_dir / "corpus" / rel
        if not path.is_file():
            sys.exit(f"missing: {path}")
        want = reg.get(rel)
        if want is None:
            sys.exit(f"{rel}: case.yaml registers no sha256 — an unregistered body is not exported")
        got = sha_of(path)
        if got != want:
            sys.exit(f"{rel}: sha256 {got} differs from the registered {want} — refusing")
        out[key] = (path, got)
    return out


def toks(text: str) -> list[float]:
    """Fortran list-directed reals, including `1.0E+00-2.0E+00` run together."""
    return [float(x) for x in re.sub(r"(?<=[0-9])-", " -", text).split()]


def namelist(text: str) -> dict[str, float]:
    out = {}
    for line in text.splitlines():
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([-+0-9.eEdD]+)\s*,?\s*$", line)
        if m:
            out[m.group(1).lower()] = float(m.group(2).replace("d", "e").replace("D", "e"))
    return out


def summary_ech(text: str) -> tuple[float, float] | None:
    """The last `ech <I_A> <P_W> ...` row of ONETWO's summary (current, power)."""
    rows = [l.split() for l in text.splitlines() if l.strip().startswith("ech ")]
    if not rows:
        return None
    r = max(rows, key=lambda r: float(r[2]))
    return float(r[1]), float(r[2])


# --------------------------------------------------------------------------- #
# the documents
# --------------------------------------------------------------------------- #

def f64s(a) -> list[float]:
    return [float(x) for x in np.asarray(a, float).ravel()]


def equilibrium(d, levels: list[float]) -> dict:
    v = lambda k: np.asarray(d.variables[k][:], float)
    one = lambda k: float(v(k))
    nr, nz = v("rmhdgrid").size, v("zmhdgrid").size
    psi = v("psi")                                   # stored (nz, nr)
    assert psi.shape == (nz, nr), psi.shape
    #: ONETWO's per-surface tables run edge -> axis (`psivalnpsi[0]` is the
    #: boundary); the door reads F on a uniform psi_N grid axis -> edge
    f = v("fpsinpsi")[::-1]
    q = v("qpsinpsi")[::-1]
    return {
        "@type": "fyo:equilibrium",
        "time": [one("time")],
        "vacuum_toroidal_field": {"r0": one("rmajor"), "b0": one("btor")},
        "time_slice": {
            "global_quantities": {
                "ip": one("tot_cur"),
                "psi_axis": one("psiaxis"), "psi_boundary": one("psibdry"),
                "magnetic_axis": {"r": one("rma"), "z": one("zma")},
            },
            "profiles_1d": {"f": f64s(f), "q": f64s(q)},
            "profiles_2d": {"grid": {"dim1": f64s(v("rmhdgrid")), "dim2": f64s(v("zmhdgrid"))},
                            "psi": [f64s(row) for row in psi.T]},      # [i_r][i_z]
            "boundary": {"outline": {"r": f64s(v("rplasbdry")), "z": f64s(v("zplasbdry"))}},
        },
        "fylite:limiter": {"r": f64s(v("rlimiter")), "z": f64s(v("zlimiter"))},
        "fylite:ladder_levels": levels,
        #: ONETWO's statefile flux is Wb per radian; said, because the door's
        #: default gauge would otherwise be its own (per radian too — but a
        #: statement beats a default)
        "fylite:psi_convention": "Wb per radian (ONETWO statefile `psir_grid`, `psi`)",
    }


def state(d, idx: np.ndarray, psin: np.ndarray) -> dict:
    """The frozen state on the rows the ladder is traced on (full-turn psi)."""
    v = lambda k: np.asarray(d.variables[k][:], float)
    ni = v("enion").sum(axis=0)
    return {
        "@type": "fyo:core_profiles",
        "time": [float(v("time"))],
        "profiles_1d": {
            "grid": {"fylite:psi_norm": f64s(psin[idx]), "psi": f64s(2.0 * math.pi * v("psir_grid")[idx])},
            "electrons": {"density": f64s(v("ene")[idx]), "temperature": f64s(1.0e3 * v("Te")[idx])},
            "t_i_average": f64s(1.0e3 * v("Ti")[idx]),
            "zeff": f64s(v("zeff")[idx]),
            "fylite:ion_density": f64s(ni[idx]),
        },
    }


def profiles_full(d, psin: np.ndarray) -> dict:
    """The same profiles on ONETWO's whole grid (axis included) — what a ray reads."""
    v = lambda k: np.asarray(d.variables[k][:], float)
    return {
        "@type": "fyo:core_profiles",
        "time": [float(v("time"))],
        "profiles_1d": {
            "grid": {"fylite:psi_norm": f64s(psin)},
            "electrons": {"density": f64s(v("ene")), "temperature": f64s(1.0e3 * v("Te"))},
            "zeff": f64s(v("zeff")),
        },
    }


def sources(d, psin: np.ndarray) -> dict:
    """ONETWO's RF current on its own psi_N grid; the door resamples it onto
    each round's ladder (a profile carrying its grid is interpolated)."""
    v = lambda k: np.asarray(d.variables[k][:], float)
    return {
        "@type": "fyo:core_sources",
        "time": [float(v("time"))],
        "source": [{
            "identifier": {"name": "ec"},
            "profiles_1d": {"grid": {"fylite:psi_norm": f64s(psin)}, "j_parallel": f64s(v("currf"))},
        }],
    }


def kernel_angles(angrid1_deg: float, angrid2_deg: float) -> tuple[float, float]:
    """TORAY's two launch angles in the kernel's two.

    The convention was established from data, not a manual (fylite_kernel
    `tests/test_cfedr_toray_oracle.py`): `angrid1` is the polar angle of the
    wave vector from +z, `angrid2` its azimuth from R-hat toward phi-hat, at a
    launcher placed at y = 0.  The kernel builds its direction as
    `[-cos(pol)cos(tor), -sin(tor), -sin(pol)cos(tor)]`; inverting is arithmetic.
    """
    a1, a2 = math.radians(angrid1_deg), math.radians(angrid2_deg)
    d = (math.sin(a1) * math.cos(a2), math.sin(a1) * math.sin(a2), math.cos(a1))
    tor = math.asin(max(-1.0, min(1.0, -d[1])))
    ct = math.cos(tor)
    pol = math.atan2(-d[2] / ct, -d[0] / ct)
    return pol, tor


def launchers(head: list[float], nml: dict[str, float], mode: float, mode_source: str,
              ech_total: tuple[float, float] | None) -> dict:
    """`echin`'s header slots, decoded by the oracle gate (0-based): 5 frequency
    [Hz], 7 R [cm], 8 Z [cm], 9 angrid1 [deg], 10 angrid2 [deg]."""
    pol, tor = kernel_angles(head[9], head[10])
    powinc = nml.get("powinc") if nml is not None else None
    if powinc is not None:
        power, power_source = 1.0e-7 * powinc, "toray.in POWINC x 1e-7 (erg/s -> W)"   # see the header on the factor 10
    elif ech_total is not None:
        power, power_source = ech_total[1], "the summary's `ech` line (no toray.in in this delivery)"
    else:
        sys.exit("no launched EC power: neither toray.in nor a summary `ech` line")
    beam = {
        "name": "EC",
        "frequency": {"data": head[5]},
        "power_launched": {"data": power},
        "fylite:power_source": power_source,
        "launching_position": {"r": 0.01 * head[7], "z": 0.01 * head[8]},
        "fylite:angle_pol": pol, "fylite:angle_tor": tor,
        "fylite:mode": mode,
        "fylite:angle_source": "echin header slots 10/11 (angrid1, angrid2), converted by the "
                               "convention derived in fylite_kernel tests/test_cfedr_toray_oracle.py",
        "fylite:mode_source": mode_source,
    }
    doc = {"@type": "fyo:ec_launchers", "time": [0.0], "beam": [beam]}
    if ech_total is not None:
        doc["fylite:summary_ech"] = {
            "current_a": ech_total[0], "power_w": ech_total[1],
            "comment": "ONETWO summary's `ech` total for the run (the largest `ech` row); the beam's "
                       "power_launched says where its own number came from (fylite:power_source).",
        }
    return doc


# --------------------------------------------------------------------------- #
# the steps
# --------------------------------------------------------------------------- #

def params(code: str, **kv) -> list[dict]:
    return [{"sets_parameter": f"{code}#{k}", "literal_value": v} for k, v in kv.items()]


def port(name: str, bound) -> dict:
    return {"binds_port": {"port_name": name, "port_direction": "input"}, "bound_to": bound}


def step(sid: str, code: str, parameters: list[dict], inputs: list[dict], carry: bool = False,
         comment: str | None = None) -> dict:
    s = {"id": sid, "type": "fyo:ScenarioSpecification", "prescribes_code": {"id": code},
         "parameters": parameters, "inputs": inputs}
    if carry:
        s["fylite:carry_forward"] = True
    if comment:
        s["comment"] = comment
    return s


def build(case_dir: pathlib.Path, *, rounds: int, mode: str, n_theta: int,
          psin_min: float, psin_max: float) -> dict:
    import netCDF4
    src = checked_sources(case_dir)
    d = netCDF4.Dataset(str(src["state"][0]))
    v = lambda k: np.asarray(d.variables[k][:], float)
    pa, pb = float(v("psiaxis")), float(v("psibdry"))
    psin = np.clip((v("psir_grid") - pa) / (pb - pa), 0.0, 1.0)
    idx = np.nonzero((psin >= psin_min) & (psin <= psin_max))[0]
    if idx.size < 4:
        sys.exit(f"only {idx.size} rows in psi_N [{psin_min}, {psin_max}]")
    levels = f64s(psin[idx])
    #: the state carries ONETWO's axis row too: the ladder door prepends the
    #: axis node (`axis_node = 1`), and the current channel reads state and
    #: ladder row for row
    if psin[0] != 0.0:
        sys.exit(f"the statefile's first row is psi_N {psin[0]}, not the axis")
    idx = np.concatenate(([0], idx))
    a_minor = float(np.max(v("rminavnpsi")))
    ne, n_he = v("ene"), v("enion")[2]
    ash = float(n_he[0] / ne[0])

    head = toks(src["echin"][0].read_text())[:16]
    nml = namelist(src["nml"][0].read_text()) if "nml" in src else None
    ech = summary_ech(src["summary"][0].read_text(errors="replace"))
    mode_value = {"O": 1.0, "X": -1.0}[mode]
    mode_source = "--mode " + mode + ": " + (CASES[case_dir.name]["mode_note"] if mode == "O" else "stated by the caller")

    eq_doc = equilibrium(d, levels)
    state_doc = state(d, idx, psin)
    cs_doc = sources(d, psin)
    full_doc = profiles_full(d, psin)
    ecl_doc = launchers(head, nml, mode_value, mode_source, ech)

    stationary = dict(a=a_minor, r0=float(v("rmajor")), b0=float(v("btor")), ip_a=float(v("tot_cur")),
                      first=1.0, composition="species", match_impurity="Ar", conductivity="redl",
                      trapped_fraction="miller", sources="table", bootstrap=1.0, alpha=1.0,
                      ash_fraction=ash, n_coupling=1.0, remap="rho_norm", n_theta=float(n_theta),
                      #: measured 2026-09-11 on this map: without the edge taper the box
                      #: re-solve refuses ("the plasma grew to the box border") even on the
                      #: map's own recovered source; with 0.05 the zero test solves
                      #: (residual 1e-9, max|dpsi| 0.116 of the span, I_p raw 18.24 of 20.04 MA)
                      box_edge_taper=0.05)

    steps = [step("ladder", "code/ladder", params("code/ladder", n_theta=float(n_theta), axis_node=1.0),
                  [port("equilibrium", eq_doc)],
                  comment=f"ONETWO's psi map traced on the state's own psi_N rows in [{psin_min}, {psin_max}] "
                          f"({idx.size - 1} of {psin.size}), the axis node prepended")]
    for r in range(1, rounds + 1):
        inputs = [port("core_profiles", state_doc), port("core_sources", cs_doc)] if r == 1 else []
        steps.append(step(f"current-{r}", "code/steady_current", params("code/steady_current", **stationary),
                          inputs, carry=True,
                          comment="the stationary round's current half on the ladder carried forward"
                                  + (" (the state and the RF table enter here)" if r == 1 else "")))
        steps.append(step(f"equilibrium-{r}", "code/steady_equilibrium",
                          params("code/steady_equilibrium", source="inversion", **stationary), [], carry=True,
                          comment="the map re-solved on the round's pressure and inverted FF', "
                                  "the ladder re-traced, the state remapped on rho_norm"))
    last_eq = f"equilibrium-{rounds}" if rounds > 0 else "ladder"
    steps.append(step("rf-ray", "code/rf_ray", params("code/rf_ray", deposit=1.0),
                      [port("equilibrium", {"id": f"{last_eq}/equilibrium"}),
                       port("core_profiles", full_doc), port("ec_launchers", ecl_doc)],
                      comment="TORAY's launch traced on the converged map; ONETWO's whole-grid profiles"))

    return {
        "@context": {
            "fyo": FYO, "spo": SPO, "fylite": "urn:fylite:",
            "dcterms": "http://purl.org/dc/terms/", "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "id": "@id", "type": "@type",
            "comment": "rdfs:comment", "title": "rdfs:label",
            "prescribes_code": "spo:prescribes_code",
            "parameters": {"@id": "spo:has_parameter_setting", "@container": "@list"},
            "sets_parameter": {"@id": "spo:sets_parameter", "@type": "@id"},
            "literal_value": {"@id": "spo:literal_value", "@type": "@json"},
            "inputs": {"@id": "spo:has_port_binding", "@container": "@set"},
            "binds_port": "spo:binds_port", "port_name": "spo:port_name",
            "port_direction": "spo:port_direction", "bound_to": "spo:bound_to",
            "has_occurrent_part": {"@id": "spo:has_occurrent_part", "@container": "@list"},
        },
        "id": f"scenario/{case_dir.name}",
        "type": "fyo:ScenarioSpecification",
        "title": f"{case_dir.name}: ONETWO's design point re-run as ladder -> {rounds} stationary round(s) -> EC ray",
        "dcterms:source": [{"fylite:path": f"cases/{case_dir.name}/corpus/{CASES[case_dir.name][k]}", "fylite:sha256": sha}
                           for k, (_, sha) in src.items()],
        "dcterms:rights": "release: internal — the values are the case's; keep this file under the same gate",
        "fylite:generator": "fylite tools/export-case-scenario.py",
        "fylite:export": {"rounds": rounds, "mode": mode, "n_theta": n_theta,
                          "psin_min": psin_min, "psin_max": psin_max, "rows": int(idx.size)},
        "has_occurrent_part": steps,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fydoc", type=pathlib.Path, default=os.environ.get("FYDOC_ORACLE"),
                    help="a fydoc checkout (default: $FYDOC_ORACLE)")
    ap.add_argument("--case", default=CASE_DEFAULT, help="the case directory under cases/")
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True, help="where the scenario is written")
    ap.add_argument("--rounds", type=int, default=6, help="stationary rounds (current + equilibrium)")
    ap.add_argument("--mode", choices=("O", "X"), default="O", help="the EC branch (see the header)")
    ap.add_argument("--n-theta", type=int, default=181)
    ap.add_argument("--psin-min", type=float, default=0.02)
    ap.add_argument("--psin-max", type=float, default=0.995)
    a = ap.parse_args()
    if a.fydoc is None:
        sys.exit("no fydoc checkout: pass --fydoc or set $FYDOC_ORACLE")
    case_dir = pathlib.Path(a.fydoc) / "cases" / a.case
    if not (case_dir / "case.yaml").is_file():
        sys.exit(f"not a case directory: {case_dir}")
    doc = build(case_dir, rounds=a.rounds, mode=a.mode, n_theta=a.n_theta,
                psin_min=a.psin_min, psin_max=a.psin_max)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {a.out} ({a.out.stat().st_size} bytes, {len(doc['has_occurrent_part'])} steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
