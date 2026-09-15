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
import shutil
import subprocess
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


def _flat_fields(fields: dict, prefix: str = "") -> dict:
    """``fields[ids][path...] = {data, units}`` flattened to ``path -> array``.

    ★A door that also hands back a whole DOCUMENT (``code/discharge`` emits an
    ``equilibrium`` since 2026-09-12) nests its fields under the IDS name, so the
    flat ``v["data"]`` read raises KeyError on it; nested paths keep their
    ``ids/path`` spelling here and flat ones are unchanged.
    """
    out = {}
    for k, v in (fields or {}).items():
        if isinstance(v, dict) and "data" in v:
            out[f"{prefix}{k}"] = np.asarray(v["data"], float)
        elif isinstance(v, dict):
            out.update(_flat_fields(v, f"{prefix}{k}/"))
    return out


def door(code: str, settings: dict, inputs: dict):
    from fylite.io import fydoc
    rec = fydoc.complete(code, {"settings": settings, "inputs": inputs})
    return ({k: float(v["value"]) for k, v in rec["facts"].items()},
            _flat_fields(rec["fields"]), list(rec.get("notes") or []))


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


# ------------------------------------------------------------------------------------------------ against KEFIT / efund (B-19 · B-20)
#: ★★2026-09-15 用户「导体壁，垂直不稳定性，与 kefit 对拍」.  KEFIT itself computes no growth rate; what it carries for the
#: wall is efund's electromagnetics — the vessel Green tables (loops · probes · grid), the F-coil grid table, and (computed
#: but never written) the vessel mutual matrix from `flux()` (Gauss quadrature over each rectangle, `soleno`).  So the
#: reference is efund, BUILT HERE from the locked bundle's source into a scratch directory and run on the bundle's own EAST
#: deck: the rigid plant is assembled from ITS tables on KEFIT's equilibrium and compared with `code/vstab` on the same one.
#: Two patches, both recorded in the archive: the 40 vessel rows are read list-directed (seven rows of the deck sit off
#: the `6e12.6` columns — the shipped `rv6565.ddd` is what a column read makes of them), and `rvsvs` is written out.
EFUND_SRC = "green_2022_source/u/efundud6565.f"
EFUND_INCS = ("green_2022_source/u/exparm2.inc", "green_2022_source/u/comn.inc")
EFUND_DECK = "green_2022_source/run/mhdin.dat"
EFUND_PROBES = "green_2022_source/run/dprobe.dat"
SHIPPED_VESSEL_TABLE = "green2022_pcs/rv6565.ddd"
EFUND_ARCHIVE = "corpus/efund/efund_east137985.tar.gz"
EFUND_PREFIX = "efund_east137985"
KEFIT_READINGS = "wall_vstab_kefit_east137985.json"
SHIFT_M = 0.001
EFUND_RUNS = (("base", 0.0), ("zp", SHIFT_M), ("zm", -SHIFT_M))
MU0 = 4e-7 * np.pi
TWO_PI = 2.0 * np.pi


def efund_patch(text: str) -> str:
    old_read = ("      read (nin,10000) (rvs(i),zvs(i),wvs(i),hvs(i),avs(i),avs2(i),\n"
                "     .              i=1,nvesel)")
    new_read = ("      do i=1,nvesel\n"
                "        read (nin,*) rvs(i),zvs(i),wvs(i),hvs(i),avs(i),avs2(i)\n"
                "      enddo")
    old_dump = ("          rvsvs(j,i)=rvsvs(j,i)*0.5/pi\n"
                " 3300 continue")
    new_dump = old_dump + ("\n      open(unit=41,status='unknown',file='rvsvs.txt')\n"
                           "      do i=1,nvesel\n        do j=1,nvesel\n"
                           "          write(41,'(1pe25.17)') rvsvs(j,i)\n        enddo\n      enddo\n"
                           "      close(unit=41)")
    assert text.count(old_read) == 1 and text.count(old_dump) == 1, "efund source anchors moved"
    return text.replace(old_read, new_read).replace(old_dump, new_dump)


def efund_build(bundle: Path, work: Path) -> dict[str, bytes]:
    """Compile the patched efund and run it on the EAST deck and on the +-1 mm Z-shifted decks; the archive members."""
    import difflib
    bme = _bme()
    work.mkdir(parents=True, exist_ok=True)
    src = (bundle / EFUND_SRC).read_bytes().decode("latin-1")
    patched = efund_patch(src)
    (work / "efund_dump.f").write_bytes(patched.encode("latin-1"))
    for inc in EFUND_INCS:
        shutil.copy(bundle / inc, work / Path(inc).name)
    cmd = ["gfortran", "-O1", "-std=legacy", "-ffixed-line-length-none", "-fno-automatic", "-o", "efund_dump", "efund_dump.f"]
    b = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=900)
    if b.returncode != 0:
        raise RuntimeError(f"efund did not build: {b.stderr[-800:]}")
    version = subprocess.run(["gfortran", "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    deck = (bundle / EFUND_DECK).read_bytes()
    anchor = b" ZBOTTO=-1.40    ZTOP=1.40      IFCOIL=1"
    assert deck.count(anchor) == 1, "deck grid line moved"
    members = {"README.txt": (f"efund (KEFIT bundle {EFUND_SRC}) patched and built here: {' '.join(cmd)}\n{version}\n"
                              f"deck {EFUND_DECK} sha256 {bme.sha(deck)} · source sha256 {bme.sha(src.encode('latin-1'))}\n"
                              f"runs: base, zp (+{SHIFT_M} m), zm (-{SHIFT_M} m) — the grid shifted in Z, tables otherwise identical\n").encode(),
               "efund.patch": "".join(difflib.unified_diff(src.splitlines(True), patched.splitlines(True), EFUND_SRC, "efund_dump.f")).encode("latin-1")}
    for tag, dz in EFUND_RUNS:
        run = work / tag
        run.mkdir(exist_ok=True)
        text = deck if dz == 0.0 else deck.replace(anchor, f" ZBOTTO={-1.40 + dz:.6f}    ZTOP={1.40 + dz:.6f}      IFCOIL=1".encode())
        (run / "mhdin.dat").write_bytes(text)
        shutil.copy(bundle / EFUND_PROBES, run / "dprobe.dat")
        r = subprocess.run([str(work / "efund_dump")], cwd=run, capture_output=True, text=True, timeout=3000)
        if r.returncode != 0:
            raise RuntimeError(f"efund {tag} failed: {r.stderr[-600:]}")
        for name in ("rvesel.dat", "fcfcpc.dat", "rfcoil.dat", "rvsvs.txt"):
            members[f"{tag}/{name}"] = (run / name).read_bytes()
        if tag == "base":
            members["base/mhdin.dat"] = text
    members["shipped_rv6565.sha256"] = f"{bme.sha((bundle / SHIPPED_VESSEL_TABLE).read_bytes())}  {SHIPPED_VESSEL_TABLE}\n".encode()
    return members


def fortran_records(data: bytes) -> list[np.ndarray]:
    import struct
    out, pos = [], 0
    while pos < len(data):
        n = struct.unpack("<i", data[pos:pos + 4])[0]
        out.append(np.frombuffer(data[pos + 4:pos + 4 + n], "<f8"))
        pos += 8 + n
    return out


def efund_tables(members: dict[str, bytes], tag: str) -> dict:
    """Column-major Fortran arrays: gsilvs(nsilop, 40) · gmp2vs(magpr2, 40) · ggridvs(nwnh, 40) · rfcpc(nfcoil, nwnh)."""
    sil, mp2, grid = fortran_records(members[f"{tag}/rvesel.dat"])
    _, rfcpc = fortran_records(members[f"{tag}/fcfcpc.dat"])
    nv = 40
    return {"loops": sil.reshape(nv, -1), "probes": mp2.reshape(nv, -1), "grid": grid.reshape(nv, 65 * 65),
            "fc_grid": rfcpc.reshape(65 * 65, -1).T, "M": np.loadtxt(io.BytesIO(members[f"{tag}/rvsvs.txt"])).reshape(nv, nv).T * TWO_PI}


def deck_arrays(deck: str) -> dict:
    import re
    def arr(key):
        m = re.search(rf"\b{key}\s*=(.*?)(?=\b[A-Z][A-Z0-9_]*\s*=|\$END)", deck, re.S)
        out = []
        for t in re.split(r"[,\s]+", m.group(1).strip()) if m else []:
            if not t:
                continue
            if "*" in t:
                n, v = t.split("*")
                out += [float(v)] * int(n)
            else:
                out.append(float(t))
        return np.array(out)
    lines = deck.splitlines()
    end = max(i for i, l in enumerate(lines) if "$END" in l.upper() or l.strip() == "/")
    vessel = np.array([[float(x) for x in l.split()] for l in lines[end + 1:] if len(l.split()) == 6][-40:])
    return {"rsi": arr("RSI"), "zsi": arr("ZSI"), "xmp2": arr("XMP2"), "ymp2": arr("YMP2"), "amp2": arr("AMP2"),
            "fcid": arr("FCID").astype(int), "fcturn": arr("FCTURN"), "vessel": vessel}


def kefit_readings(case: Path, bundle: Path | None = None) -> dict:
    """fylite against the recorded efund runs: the wall element by element (B-19), the rigid plant on KEFIT's equilibrium (B-20)."""
    from matplotlib.path import Path as MPath
    from scipy import optimize
    from fylite import fyo
    with tarfile.open(case / EFUND_ARCHIVE, "r:gz") as tf:
        members = {m.name.split("/", 1)[1]: tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}
    base, zp, zm = (efund_tables(members, t) for t, _ in EFUND_RUNS)
    deck = deck_arrays(members["base/mhdin.dat"].decode("latin-1"))
    dev = east_card()
    out = {"reference": f"efund built from the KEFIT bundle ({EFUND_ARCHIVE} in {CASE23})",
           "efund_readme": members["README.txt"].decode().splitlines(), "wall": {}, "vstab": {}}

    # ---- B-19: the wall, element by element
    facts, f, _ = door("code/wall", {"passive": "inner_shell", "nu": 8, "nv": 8}, {"device": dev})
    el = np.c_[f["element_r"], f["element_z"]]
    order = [int(np.argmin(np.hypot(*(el - v[:2]).T))) for v in deck["vessel"]]
    mag = dev["magnetics"]
    pos = lambda l: l["position"][0] if isinstance(l["position"], list) else l["position"]  # noqa: E731
    lr = np.array([pos(l)["r"] for l in mag["flux_loop"]])
    lz = np.array([pos(l)["z"] for l in mag["flux_loop"]])
    lmap = [int(np.argmin(np.hypot(lr - r, lz - z))) for r, z in zip(deck["rsi"], deck["zsi"])]
    K = f["loops_psi"].reshape(40, -1)[order][:, lmap]
    rl = np.abs(K / base["loops"] - 1.0)
    G = f["grid_psi"].reshape(40, 65 * 65)[order]
    rg_ = np.abs(G / base["grid"] - 1.0)
    pr = np.array([pos(p)["r"] for p in mag["b_field_pol_probe"]])
    pz = np.array([pos(p)["z"] for p in mag["b_field_pol_probe"]])
    pa = np.degrees(np.array([p["poloidal_angle"] for p in mag["b_field_pol_probe"]]))
    pmap, pdist = [], []
    for x, y, a in zip(deck["xmp2"], deck["ymp2"], deck["amp2"]):
        d = np.hypot(pr - x, pz - y) + 1e-3 * np.abs(((pa - a) + 180) % 360 - 180)
        pmap.append(int(np.argmin(d)))
        pdist.append(float(d.min()))
    good = np.array(pdist) < 5e-3
    P = f["probes_b"].reshape(-1, 40)[:, order][pmap][good]
    Pe = base["probes"].T[good]
    rp = np.abs(P - Pe) / np.maximum(np.abs(Pe), 1e-12)
    worst_el = [float(rl[i].max()) for i in range(40)]
    _, f16, _ = door("code/wall", {"passive": "inner_shell", "nu": WALL_NU, "nv": WALL_NU, "responses": 0}, {"device": dev})
    M_k = f16["m"].reshape(40, 40)[np.ix_(order, order)]
    R_k = f16["r"][order]
    off = ~np.eye(40, dtype=bool)
    tk = np.sort(np.linalg.eigvals(np.linalg.solve(np.diag(R_k), M_k)).real)[::-1]
    te = np.sort(np.linalg.eigvals(np.linalg.solve(np.diag(R_k), base["M"])).real)[::-1]
    out["wall"] = {"elements": 40, "element_centre_match_m": float(max(np.hypot(*(el[o] - v[:2])) for o, v in zip(order, deck["vessel"]))),
                   "loops": {"n": len(lmap), "rel_median": float(np.median(rl)), "rel_p95": float(np.percentile(rl, 95)), "rel_max": float(rl.max())},
                   "grid": {"n": 65 * 65, "rel_median": float(np.median(rg_)), "rel_p95": float(np.percentile(rg_, 95)), "rel_max": float(rg_.max())},
                   "probes_reading": {"matched": int(good.sum()), "of": len(deck["xmp2"]), "rel_median": float(np.median(rp)), "rel_p95": float(np.percentile(rp, 95))},
                   "elements_loops_below_1e-3": int(sum(1 for v in worst_el if v < 1e-3)),
                   "M": {"diag_rel_median": float(np.median(np.abs(np.diag(M_k) / np.diag(base["M"]) - 1))),
                         "diag_rel_max": float(np.max(np.abs(np.diag(M_k) / np.diag(base["M"]) - 1))),
                         "offdiag_rel_median": float(np.median(np.abs(M_k[off] / base["M"][off] - 1))),
                         "offdiag_rel_p95": float(np.percentile(np.abs(M_k[off] / base["M"][off] - 1), 95)),
                         "efund_asymmetry": float(np.abs(base["M"] - base["M"].T).max() / np.abs(base["M"]).max())},
                   "tau_card_R_ms": {"fylite": [float(1e3 * v) for v in tk[:4]], "efund_M": [float(1e3 * v) for v in te[:4]], "tau1_rel": float(tk[0] / te[0] - 1)}}
    if bundle is not None:
        #: the shipped table (locked bundle, not in the archive): what the column read made of the deck, against this build's
        shipped = fortran_records((bundle / SHIPPED_VESSEL_TABLE).read_bytes())
        out["wall"]["shipped_vs_rebuilt"] = {"loops_rel_max": float(np.max(np.abs(shipped[0].reshape(40, -1) / base["loops"] - 1))),
                                             "grid_rel_max": float(np.max(np.abs(shipped[2].reshape(40, -1) / base["grid"] - 1)))}

    # ---- B-20: the rigid plant from efund's tables on KEFIT's equilibrium
    g, a, gsha = kefit_slice(case)
    rgk, zgk = np.linspace(g["rleft"], g["rleft"] + g["rdim"], g["nw"]), np.linspace(g["zmid"] - g["zdim"] / 2, g["zmid"] + g["zdim"] / 2, g["nh"])
    assert np.allclose(rgk, np.linspace(1.2, 2.8, 65)) and np.allclose(zgk, np.linspace(-1.4, 1.4, 65)), "KEFIT grid is not efund's"
    psi = np.asarray(g["psirz"], float).reshape(65, 65).T
    pn = (psi - g["simag"]) / (g["sibry"] - g["simag"])
    x = np.linspace(0, 1, len(g["pprime"]))
    Rm, Zm = np.meshgrid(rgk, zgk, indexing="ij")
    inside = MPath(np.c_[g["rbbbs"], g["zbbbs"]]).contains_points(np.c_[Rm.ravel(), Zm.ravel()]).reshape(Rm.shape) & (pn < 1)
    J = Rm * np.interp(pn, x, g["pprime"]) + np.interp(pn, x, g["ffprim"]) / (MU0 * Rm)
    ip = abs(float(g["current"]))
    I = np.where(inside, J, 0.0)
    I = (I / I.sum() * ip).ravel()
    cc = np.asarray(a["ccbrsp"], float)[:12]
    fc_at = cc[deck["fcid"] - 1] * deck["fcturn"]
    gv = TWO_PI * (zp["grid"] - zm["grid"]) / (2 * SHIFT_M) @ I / ip
    k_e = float(I @ (TWO_PI * (zp["fc_grid"] - 2 * base["fc_grid"] + zm["fc_grid"]) / SHIFT_M ** 2).T @ fc_at)

    def dispersion(M, Rr, gvec, ipv, k):
        kid = float(ipv * ipv * gvec @ np.linalg.solve(M, gvec))
        if k >= kid:
            return float("inf"), kid
        fn = lambda gm: gm * ipv * ipv * gvec @ np.linalg.solve(gm * M + np.diag(Rr), gvec) - k  # noqa: E731
        return float(optimize.brentq(fn, 1e-9, 1e7, xtol=1e-12, rtol=1e-13)), kid

    gam_e, kid_e = dispersion(base["M"], R_k, gv, ip, k_e)
    eqdoc = fyo.as_equilibrium(g)
    out["vstab"] = {"kefit_g_sha256": gsha, "plasma_nodes": int(inside.sum()), "shift_m": SHIFT_M,
                    "efund": {"gamma": gam_e, "k": k_e, "k_ideal": kid_e, "margin": kid_e / k_e - 1}, "fylite": {}}
    for tag, nu in (("fine", 8.0), ("finest", 16.0)):
        fc, ff, _ = door("code/vstab", {"circuit": "passive", "passive": "inner_shell", "ic": 0.0, "coarsen": 1.0, "nu": nu, "nv": nu},
                         {"device": dev, "equilibrium": eqdoc, "discharge": {"fylite:channel_aturns": cc}})
        gk = ff["g"][order]
        out["vstab"]["fylite"][tag] = {"gamma": fc["gamma"], "k": fc["k"], "k_ideal": fc["k_ideal"], "margin": fc["margin"],
                                       "compare": {"gamma_rel": fc["gamma"] / gam_e - 1, "k_rel": fc["k"] / k_e - 1,
                                                   "k_ideal_rel": fc["k_ideal"] / kid_e - 1, "margin_abs": fc["margin"] - (kid_e / k_e - 1),
                                                   "g_rel_median": float(np.median(np.abs(gk / gv - 1))), "g_rel_max": float(np.max(np.abs(gk / gv - 1)))}}
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
    c = sub.add_parser("efund-build", help="build and run efund from the KEFIT bundle; write the archive + index")
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--bundle", type=Path, default=Path(os.environ.get("KEFIT_REFERENCE_BUNDLE", str(ROOT.parent / "third_party/kefit_reference_bundle"))))
    e = sub.add_parser("kefit-readings", help="fylite against the recorded efund runs (B-19 · B-20)")
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--case", type=Path)
    e.add_argument("--bundle", type=Path, help="the KEFIT bundle, to also read the shipped vessel table against the rebuild")
    args = ap.parse_args()
    if args.cmd == "pack":
        pack(args.src, args.dest)
        return 0
    if args.cmd == "efund-build":
        bme = _bme()
        with tempfile.TemporaryDirectory() as d:
            members = efund_build(args.bundle, Path(d))
        data = bme.pack([(f"{EFUND_PREFIX}/{k}", v) for k, v in sorted(members.items())])
        dest = args.out / Path(EFUND_ARCHIVE).name
        args.out.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        index = {"@context": {"fylite": "urn:fylite:"}, "@type": "fylite:ArchiveIndex", "fylite:archive": dest.name, "fylite:sha256": bme.sha(data),
                 "fylite:members": [{"path": f"{EFUND_PREFIX}/{k}", "bytes": len(v), "sha256": bme.sha(v)} for k, v in sorted(members.items())]}
        dest.with_name(dest.name.replace(".tar.gz", ".index.json")).write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
        print(dest, bme.sha(data))
        return 0
    if args.cmd == "kefit-readings":
        case = args.case or Path(os.environ["FYDOC_ORACLE"]) / CASE23
        res = kefit_readings(case, args.bundle)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / KEFIT_READINGS).write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
        print(json.dumps(res, indent=1, default=float)[:6000])
        return 0
    case = args.case or Path(os.environ["FYDOC_ORACLE"]) / CASE23
    res = readings(case)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / READINGS).write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1, default=float)[:5000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
