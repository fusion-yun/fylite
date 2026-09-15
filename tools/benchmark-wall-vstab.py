#!/usr/bin/env python3
"""Conducting-wall and vertical-instability benchmarks against FreeGSNKE (register records B-17 · B-18).

★★2026-09-15 用户「补全导体壁，垂直不稳定性算例」.  The reference is FreeGSNKE (LGPL-3; `third_party/freegsnke-main`
with freegs4e 0.13.1 from PyPI, numpy 1.26.4 — the local freegs4e 0.3.0 lacks the Machine API and 0.14 shadows
FreeGSNKE's `Jtor`), built on the SAME EAST device card this checkout resolves: the 90 passive elements (inner shell 40,
outer shell 40, passive plates 10) as polygons in efund's parallelogram (a shear: w, h the horizontal / vertical
extents), the 12 PF channels and their element map, KEFIT's coil currents.  FreeGSNKE's side is a recorded run
(`corpus/freegsnke/freegsnke_vstab_east137985.tar.gz` in FYDOC-CASE-23: its scripts, its JSON and arrays); it is not
rerun here — its linearisation takes 10–20 min.  This tool recomputes fylite's side through the tree door and compares.

* B-17 (the wall as a circuit): `code/wall` on the card (nu = nv = 16 filaments per element) against FreeGSNKE's passive
  normal modes (fine polygons): the longest L/R time of each group alone and of all three, the passive inductance
  matrix element by element, the resistances.
* B-18 (vertical instability): `code/vstab` (`circuit: passive`, coarsen 1, nu = nv = 8) on FreeGSNKE's own converged
  inverse equilibrium of #137985 t = 4.041 s against FreeGSNKE's RIGID dispersion from its own matrices (M, R, the
  coupling gradient, the active-coil destabilising force k, I_p): gamma, k, k_ideal, margin.  Readings beside it:
  fylite on KEFIT's equilibrium, and FreeGSNKE's DEFORMABLE growth rate (its linearised Jacobian — a physics the rigid
  model does not have).

Subcommands: ``readings --out DIR`` (fylite side, compared) · ``pack SRC DEST`` (the FreeGSNKE run directory into the
deterministic archive + index).  Environment: ``$FYDOC_ORACLE``, ``$FYLITE_DEVICE_DIR``, a kernel with ``code/wall``.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CASE23 = "FYDOC-CASE-23-east-137985-efit-east"
ARCHIVE = "corpus/freegsnke/freegsnke_vstab_east137985.tar.gz"
PREFIX = "freegsnke_vstab_east137985"
READINGS = "wall_vstab_east137985.json"
GROUPS = ("inner_shell", "outer_shell", "passive_plates")
SLICES = {"inner_shell": slice(0, 40), "outer_shell": slice(40, 80), "passive_plates": slice(80, 90)}
#: FreeGSNKE orders its coils actives first: the 12 PF channels, then the 90 passive elements
N_ACTIVE = 12
WALL_NU = 16
VS_DISC = {"coarsen": 1.0, "nu": 8.0, "nv": 8.0}
PACK_FILES = ("freegsnke_side.py", "geom.py", "run_all.sh", "freegsnke.json", "fgs_modes.npz", "fgs_equilibrium.npz",
              "fgs_vs_all.npz", "fgs_vs_inner_shell.npz")


def _bme():
    spec = importlib.util.spec_from_file_location("benchmark_equilibrium", ROOT / "tools" / "benchmark-equilibrium.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def archive(case: Path) -> dict[str, bytes]:
    with tarfile.open(case / ARCHIVE, "r:gz") as tf:
        return {m.name.split("/", 1)[1]: tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}


def npz(data: bytes):
    return np.load(io.BytesIO(data))


def rel_stats(a, b) -> dict:
    """a against the reference b, element by element (symmetric matrices)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    off = ~np.eye(a.shape[0], dtype=bool)
    d, o = np.abs(np.diag(a) / np.diag(b) - 1), np.abs(a[off] / b[off] - 1)
    return {"diag_rel_median": float(np.median(d)), "diag_rel_max": float(d.max()), "offdiag_rel_median": float(np.median(o)),
            "offdiag_rel_p95": float(np.percentile(o, 95)), "frobenius_rel": float(np.linalg.norm(a - b) / np.linalg.norm(b))}


def door(code: str, settings: dict, inputs: dict):
    from fylite.io import fydoc
    rec = fydoc.complete(code, {"settings": settings, "inputs": inputs})
    return ({k: float(v["value"]) for k, v in rec["facts"].items()},
            {k: np.asarray(v["data"], float) for k, v in rec["fields"].items()}, list(rec.get("notes") or []))


def east_card() -> dict:
    from fylite import device
    return device.document(shot=137985, measurement_chain="east")


def kefit_slice(case: Path):
    from fylite.io import geqdsk
    bme = _bme()
    pre = "kefit_raw_east137985/rejected/t4041_mag/"
    with tarfile.open(case / bme.KEFIT_TAR, "r:gz") as tf:
        gb, ab = tf.extractfile(pre + "g137985.04041").read(), tf.extractfile(pre + "a137985.04041").read()
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "g").write_bytes(gb)
        (Path(d) / "a").write_bytes(ab)
        return geqdsk.read_geqdsk(Path(d) / "g"), geqdsk.read_afile(Path(d) / "a", arrays=True), bme.sha(gb)


def freegsnke_inverse_equilibrium(z) -> tuple[dict, np.ndarray]:
    """FreeGSNKE's converged inverse equilibrium as a g-file dict (its own coil currents beside it)."""
    keys = ("rdim", "zdim", "rcentr", "rleft", "zmid", "rmaxis", "zmaxis", "simag", "sibry", "bcentr", "current",
            "fpol", "pres", "ffprim", "pprime", "psirz", "qpsi", "rbbbs", "zbbbs", "rlim", "zlim")
    gd = {k: (z[f"inv__{k}"].item() if z[f"inv__{k}"].ndim == 0 else z[f"inv__{k}"]) for k in keys}
    gd["nw"], gd["nh"] = int(z["inv__nw"]), int(z["inv__nh"])
    gd["nbbbs"], gd["limitr"] = len(gd["rbbbs"]), len(gd["rlim"])
    return gd, np.asarray(z["inv__aturns"], float)


def vstab(dev, eqdoc, aturns, passive: str, **disc) -> dict:
    s = {"circuit": "passive", "passive": passive, "ic": 0.0}
    s.update({k: float(v) for k, v in disc.items()})
    facts, _, _ = door("code/vstab", s, {"device": dev, "equilibrium": eqdoc, "discharge": {"fylite:channel_aturns": np.asarray(aturns, float)}})
    return {k: facts[k] for k in ("gamma", "k", "k_ideal", "margin", "ip")}


def readings(case: Path) -> dict:
    from fylite import fyo
    arch = archive(case)
    fj = json.loads(arch["freegsnke.json"])
    modes = npz(arch["fgs_modes.npz"])
    dev = east_card()
    out = {"reference": f"FreeGSNKE recorded run ({ARCHIVE} in {CASE23})", "freegsnke_environment": fj["environment"],
           "wall": {}, "vstab": {}}

    # ---- B-17: the wall as a circuit
    facts, f, notes = door("code/wall", {"passive": ",".join(GROUPS), "nu": WALL_NU, "nv": WALL_NU}, {"device": dev})
    n = int(facts["n_elements"])
    m, r = f["m"].reshape(n, n), f["r"]
    fm, fr = modes["M/poly_fine/efit"][N_ACTIVE:, N_ACTIVE:], modes["R/poly_fine/efit"][N_ACTIVE:]
    fylite_tau = {"all": float(f["tau"][0])}
    fylite_tau.update({g: float(t) for g, t in zip(GROUPS, f["group_tau"])})
    fgs_modes = fj["modes"]["poly_fine/efit"]
    wall = {"settings": {"nu": WALL_NU, "nv": WALL_NU}, "n_elements": n, "notes": notes, "sets": {}}
    for sname in GROUPS + ("all",):
        sl = SLICES.get(sname, slice(0, n))
        ref_tau = float(fgs_modes[sname]["tau_s_top10"][0])
        wall["sets"][sname] = {"fylite_tau1_s": fylite_tau[sname], "freegsnke_tau1_s": ref_tau,
                               "tau1_rel": fylite_tau[sname] / ref_tau - 1.0,
                               "M": rel_stats(m[sl, sl], fm[sl, sl]),
                               "R_rel_median": float(np.median(r[sl] / fr[sl] - 1.0)),
                               "R_rel_absmax": float(np.max(np.abs(r[sl] / fr[sl] - 1.0)))}
    wall["fylite_tau_s_top5"] = [float(v) for v in f["tau"][:5]]
    out["wall"] = wall

    # ---- B-18: vertical instability on FreeGSNKE's own equilibrium, and on KEFIT's
    z = npz(arch["fgs_equilibrium.npz"])
    gd, at_fgs = freegsnke_inverse_equilibrium(z)
    eq_fgs = fyo.as_equilibrium(gd)
    g, a, gsha = kefit_slice(case)
    eq_kefit, at_kefit = fyo.as_equilibrium(g), np.asarray(a["ccbrsp"], float)[:12]
    out["vstab"] = {"kefit_g_sha256": gsha, "settings": VS_DISC, "sets": {}}
    for sname in ("inner_shell", "all"):
        spec = ",".join(GROUPS) if sname == "all" else sname
        fy_fgs = vstab(dev, eq_fgs, at_fgs, spec, **VS_DISC)
        fy_kefit = vstab(dev, eq_kefit, at_kefit, spec, **VS_DISC)
        rig = fj["vs"][sname]["rigid_from_freegsnke_matrices"]
        dfm = fj["vs"][sname]["deformable_const_Ip_frozen_actives"]
        out["vstab"]["sets"][sname] = {
            "fylite_on_freegsnke_eq": fy_fgs, "fylite_on_kefit_eq": fy_kefit,
            "freegsnke_rigid": {"gamma": rig["gamma_per_s"], "k": rig["k_actives_destab_force"], "k_ideal": rig["k_ideal"], "margin": rig["margin"]},
            "freegsnke_deformable": {"gamma": dfm["gamma_per_s"][0], "margin": dfm["stability_margin"][0]},
            "compare": {"gamma_rel": fy_fgs["gamma"] / rig["gamma_per_s"] - 1.0, "k_rel": fy_fgs["k"] / rig["k_actives_destab_force"] - 1.0,
                        "k_ideal_rel": fy_fgs["k_ideal"] / rig["k_ideal"] - 1.0, "margin_abs": fy_fgs["margin"] - rig["margin"]},
            "readings": {"deformable_over_rigid_gamma": dfm["gamma_per_s"][0] / rig["gamma_per_s"],
                         "fylite_kefit_over_freegsnke_eq_gamma": fy_kefit["gamma"] / fy_fgs["gamma"]}}
    eqs = fj["vs"]["all"]["equilibrium"]
    out["vstab"]["freegsnke_equilibrium"] = {"kind": fj["vs"]["all"]["equilibrium_used"], "axis_R": eqs["axis_R"], "axis_Z": eqs["axis_Z"],
                                             "kappa": eqs["boundary"]["kappa"], "boundary_dist_to_kefit_mm": eqs["boundary_dist_to_kefit_mm"]}
    return out


def pack(src: Path, dest: Path) -> None:
    bme = _bme()
    members = [(f"{PREFIX}/{name}", (src / name).read_bytes()) for name in PACK_FILES]
    data = bme.pack(members)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    index = {"@context": {"fylite": "urn:fylite:"}, "@type": "fylite:ArchiveIndex", "fylite:archive": dest.name,
             "fylite:sha256": bme.sha(data),
             "fylite:members": [{"path": p, "bytes": len(b), "sha256": bme.sha(b)} for p, b in members]}
    dest.with_name(dest.name.replace(".tar.gz", ".index.json")).write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("readings")
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--case", type=Path)
    b = sub.add_parser("pack")
    b.add_argument("src", type=Path)
    b.add_argument("dest", type=Path)
    args = ap.parse_args()
    if args.cmd == "pack":
        pack(args.src, args.dest)
        return 0
    case = args.case or Path(os.environ["FYDOC_ORACLE"]) / CASE23
    res = readings(case)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / READINGS).write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1, default=float)[:5000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
