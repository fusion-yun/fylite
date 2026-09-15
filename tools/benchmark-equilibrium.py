#!/usr/bin/env python3
"""Equilibrium benchmarks run from the PUBLIC side: fylite's solvers (through the tree door) against KEFIT.

★★2026-09-15 用户裁定：废弃 libefit 对标，直接对标 KEFIT；平衡相关的 benchmark 由本仓补全、不动内核仓。
So every fylite number here comes through ``fylite.io.fydoc.complete`` (the one door the shipped library opens), and
every reference number is a KEFIT run — the local build of the third-party ``kefit_reference_bundle`` (build recipe in
FYDOC-CASE-23 ``corpus/kefit/kefit_build_recipe.json``).  No efit_east tree value enters a solve (ruling 2026-09-15).

    forward-kefit   B-14: the free-boundary FORWARD solve.  KEFIT's converged raw-tree answers (CASE-23
                    ``kefit_raw_east137985.tar.gz``, variant ``rejected``, the runs without error flags) hand fylite's
                    ``code/forward`` their fitted coil ampere-turns (a-file CCBRSP), their p'(psi_N) / FF'(psi_N)
                    (g-file PPRIME / FFPRIM) and Ip; the two equilibria are then compared on KEFIT's own 65 x 65 grid
                    (the same box as the EAST card's).  Same currents, same profiles: what is left is the GS solve.
    twin            V-18 / B-15: reconstruction with a KNOWN answer.  ``code/forward``'s analytic family with
                    e_mp = e_np = 1 (p' and FF' linear, zero at the edge — inside both codes' bases) on #137985's
                    measured coil currents and Ip at 4.041 s gives the truth; its loops (plasma part + the coils'
                    share from ``code/coilshare``) and probes are the measurements.  fylite ``code/reconstruction``
                    (npp = nff = 1, vertical set-point scanned) and, with ``--kefit-exe``, KEFIT (KPPCUR = KFFCUR = 2,
                    pcurbd = fcurbd = 1, green2022_pcs geometry by a position + angle slot map) reconstruct it.
    pack            deterministic tar.gz + sha256 index of a run directory (for the fydoc case corpus).

The readings land in ``<out>/`` as JSON; ``python/tests/test_benchmark_equilibrium.py`` replays them.

Environment: ``FYLITE_DEVICE_DIR`` (the EAST card), ``FYLITE_KERNEL_LIB``, ``FYDOC_ORACLE`` (the fydoc ``cases/`` tree),
``KEFIT_BUNDLE`` (the reference bundle, for the KEFIT runs only).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

SHOT = 137985
CASE23 = "FYDOC-CASE-23-east-137985-efit-east"
KEFIT_TAR = "corpus/kefit/kefit_raw_east137985.tar.gz"
RAW_SLICES = "corpus/raw/raw_slices_east137985.json"
#: the KEFIT raw-tree runs that finished without an error flag (CASE-23 #R-raw-trees, variant `rejected`)
FORWARD_CASES = ("t4041_mag", "t4944_mag", "t5976_mag", "t5976_primary")
TWO_PI = 2.0 * np.pi
SERROR = 0.05
#: KEFIT's sigma floors (efitdu.f data_input: sigma = max(serror |value|, bit), vbit = 1) — the loop bit is GUI_v5's
#: efit/2016/psibit.txt / 2 pi per loop; the probe bit is the median of efit/2016/bitmp2.txt (see CASE-23 #R-raw-trees)
PROBE_BIT = 7.52541e-4
BITFC = [50.0 * n for n in (140, 140, 140, 244, 64, 32)] * 2
ZC_SCAN = [round(-0.030 + 0.004 * k, 3) for k in range(16)]
RECON = {"npp": 1, "nff": 1, "relax": 0.3, "max_iter": 4000, "tol": 1e-8, "fb_gain": 8.0, "warmup": 40,
         "n_profile": 201, "n_q": 20, "n_theta": 121, "x_lo": 0.06, "x_hi": 0.995}
TRUTH = {"beta0": 0.4, "emp": 1.0, "enp": 1.0}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def case_dir(explicit: str | None) -> Path:
    root = Path(explicit or os.environ.get("FYDOC_ORACLE") or "")
    d = root / CASE23 if (root / CASE23).is_dir() else root
    if not (d / "case.yaml").is_file():
        raise SystemExit(f"no {CASE23} under {root!s} (set FYDOC_ORACLE to the fydoc cases/ tree)")
    return d


def tar_members(path: Path) -> dict[str, bytes]:
    with tarfile.open(path, "r:gz") as tf:
        return {m.name: tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}


def pack(members: list[tuple[str, bytes]]) -> bytes:
    """Byte-deterministic tar.gz: fixed member metadata, gzip mtime 0."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for name, data in sorted(members):
            ti = tarfile.TarInfo(name)
            ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = len(data), 0, 0o644, 0, 0, "", ""
            tf.addfile(ti, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, filename="") as gz:
        gz.write(raw.getvalue())
    return out.getvalue()


# ------------------------------------------------------------------------------------------------ geometry helpers

def seg_dist(p: np.ndarray, poly: np.ndarray) -> float:
    a0, a1 = poly[:-1], poly[1:]
    ab = a1 - a0
    t = np.clip(((p - a0) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-30), 0.0, 1.0)
    return float(np.min(np.hypot(*(a0 + t[:, None] * ab - p).T)))


def closed_contour(rg, zg, psin: np.ndarray, level: float, axis: tuple[float, float]) -> np.ndarray | None:
    """The level-set line that encloses the axis (psin indexed [R, Z])."""
    import contourpy
    from matplotlib.path import Path as MPath
    lines = contourpy.contour_generator(rg, zg, psin.T).lines(level)
    enclosing = [L for L in lines if len(L) > 8 and MPath(L).contains_point(axis)]
    return max(enclosing, key=len) if enclosing else None


def inside(poly: np.ndarray, rg, zg) -> np.ndarray:
    from matplotlib.path import Path as MPath
    R, Z = np.meshgrid(rg, zg, indexing="ij")
    return MPath(poly).contains_points(np.c_[R.ravel(), Z.ravel()]).reshape(R.shape)


def saddles(rg, zg, psi: np.ndarray, box=(1.35, 2.45, -1.15, 1.15)) -> list[tuple[float, float]]:
    """X points of a psi map [R, Z]: |grad psi| minima with a negative Hessian determinant."""
    from scipy.interpolate import RectBivariateSpline
    from scipy.optimize import minimize
    sp = RectBivariateSpline(rg, zg, psi)
    g = lambda v: np.asarray(sp(v[0], v[1], dx=1, grid=False) ** 2 + sp(v[0], v[1], dy=1, grid=False) ** 2).item()  # noqa: E731
    scale = float(np.ptp(psi)) ** 2
    found: list[tuple[float, float]] = []
    for r0 in np.linspace(box[0], box[1], 10):
        for z0 in np.linspace(box[2], box[3], 14):
            res = minimize(g, [r0, z0], method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-16, "maxiter": 500})
            r, z = res.x
            if not (box[0] <= r <= box[1] and box[2] <= z <= box[3]) or res.fun > 1e-10 * scale:
                continue
            h = np.asarray(sp(r, z, dx=2, grid=False) * sp(r, z, dy=2, grid=False) - sp(r, z, dx=1, dy=1, grid=False) ** 2).item()
            if h < 0 and all(np.hypot(r - a, z - b) > 0.02 for a, b in found):
                found.append((float(r), float(z)))
    return found


def compare_maps(ref: dict, got: dict) -> dict:
    """Two equilibria on one grid: ref / got = {rg, zg, psi[R,Z], psi_axis, psi_bnd, axis, boundary (N x 2), ip}."""
    assert np.allclose(ref["rg"], got["rg"]) and np.allclose(ref["zg"], got["zg"]), "the two maps are on different grids"
    pn_r = (ref["psi"] - ref["psi_axis"]) / (ref["psi_bnd"] - ref["psi_axis"])
    pn_g = (got["psi"] - got["psi_axis"]) / (got["psi_bnd"] - got["psi_axis"])
    ins = inside(ref["boundary"], ref["rg"], ref["zg"])
    d = (pn_g - pn_r)[ins]
    out = {"dR_axis_mm": 1e3 * (got["axis"][0] - ref["axis"][0]), "dZ_axis_mm": 1e3 * (got["axis"][1] - ref["axis"][1]),
           "psin_rms_inside": float(np.sqrt(np.mean(d ** 2))), "psin_max_inside": float(np.abs(d).max()),
           "n_nodes_inside": int(ins.sum()),
           "span_rel": float((got["psi_bnd"] - got["psi_axis"]) / (ref["psi_bnd"] - ref["psi_axis"]) - 1.0),
           "ip_rel": float(got["ip"] / ref["ip"] - 1.0)}
    line = closed_contour(got["rg"], got["zg"], pn_g, 1.0 - 1e-6, got["axis"])
    if line is not None:
        seg = np.array([seg_dist(p, line) for p in ref["boundary"][:-1]])
        out.update(boundary_median_mm=1e3 * float(np.median(seg)), boundary_max_mm=1e3 * float(seg.max()))
    xr, xg = saddles(ref["rg"], ref["zg"], ref["psi"]), saddles(got["rg"], got["zg"], got["psi"])
    if xr and xg:
        pairs = [(np.hypot(a[0] - b[0], a[1] - b[1]), a, b) for a in xr for b in xg]
        dmin, a, b = min(pairs, key=lambda t: t[0])
        #: the X point that bounds the plasma: the reference saddle nearest to its own boundary
        xb = min(xr, key=lambda s: min(np.hypot(*(ref["boundary"] - np.array(s)).T)))
        nb = min(xg, key=lambda s: np.hypot(s[0] - xb[0], s[1] - xb[1]))
        out.update(xpoint_ref=list(xb), xpoint_got=list(nb), xpoint_dist_mm=1e3 * float(np.hypot(nb[0] - xb[0], nb[1] - xb[1])))
    return out


# ------------------------------------------------------------------------------------------------ fylite through the door

def door(code: str, settings: dict, inputs: dict) -> tuple[dict, dict, list]:
    from fylite.io import fydoc
    rec = fydoc.complete(code, {"settings": settings, "inputs": inputs})
    facts = {k: v["value"] for k, v in rec["facts"].items()}
    fields = {k: np.asarray(v["data"], float) for k, v in rec["fields"].items()}
    return facts, fields, list(rec.get("notes") or [])


def east_card() -> dict:
    from fylite import device
    return device.document(shot=SHOT, measurement_chain="east")


def fylite_map(facts: dict, fields: dict, boundary=None) -> dict:
    rg, zg = fields["grid_r"], fields["grid_z"]
    psi = fields["psi"].reshape(len(rg), len(zg))
    m = {"rg": rg, "zg": zg, "psi": psi, "psi_axis": facts["psi_axis"], "psi_bnd": facts["psi_bnd"],
         "axis": (facts["axis_r"], facts["axis_z"]), "ip": facts["ip"]}
    if boundary is None:
        pn = (psi - m["psi_axis"]) / (m["psi_bnd"] - m["psi_axis"])
        boundary = closed_contour(rg, zg, pn, 1.0 - 1e-6, m["axis"])
    m["boundary"] = boundary
    return m


def kefit_map(g: dict) -> dict:
    """A KEFIT g-file in fylite's gauge: full flux, axis maximum (psi_fy = -2 pi psi_tree, measured below)."""
    from fylite.io import geqdsk
    r, z, _ = geqdsk.grid(g)
    r, z = np.asarray(r, float).ravel(), np.asarray(z, float).ravel()
    psi = np.asarray(g["psirz"], float).reshape(len(z), len(r)).T
    s = -TWO_PI if g["sibry"] > g["simag"] else TWO_PI
    return {"rg": r, "zg": z, "psi": s * psi, "psi_axis": s * g["simag"], "psi_bnd": s * g["sibry"],
            "axis": (g["rmaxis"], g["zmaxis"]), "ip": abs(g["current"]),
            "boundary": np.c_[np.asarray(g["rbbbs"], float), np.asarray(g["zbbbs"], float)], "gauge_factor": s}


# ------------------------------------------------------------------------------------------------ B-14

def forward_kefit(case: Path, out: Path) -> dict:
    from fylite.io import geqdsk
    idx = json.loads((case / KEFIT_TAR.replace(".tar.gz", ".index.json")).read_text(encoding="utf-8"))
    mem_sha = {m["path"]: m["sha256"] for m in idx["fylite:members"]}
    members = tar_members(case / KEFIT_TAR)
    tmp = out / "_kefit_inputs"
    tmp.mkdir(parents=True, exist_ok=True)
    dev = east_card()
    result = {"reference": "KEFIT raw-tree runs (CASE-23 kefit_raw_east137985.tar.gz, variant rejected)",
              "archive_sha256": idx["fylite:sha256"], "door_settings": "code/forward defaults (relax 0.3, max_iter 600, tol 1e-9, fb_gain 8)",
              "cases": {}}
    for name in FORWARD_CASES:
        itime = name[1:5]
        pre = f"kefit_raw_east137985/rejected/{name}/"
        gname, aname = f"{pre}g{SHOT}.0{itime}", f"{pre}a{SHOT}.0{itime}"
        (tmp / "g").write_bytes(members[gname])
        (tmp / "a").write_bytes(members[aname])
        g = geqdsk.read_geqdsk(tmp / "g")
        a = geqdsk.read_afile(tmp / "a", arrays=True)
        ref = kefit_map(g)
        s = ref["gauge_factor"]
        x = np.linspace(0.0, 1.0, len(g["pprime"]))
        inputs = {"device": dev,
                  "discharge": {"fylite:channel_aturns": np.asarray(a["ccbrsp"], float)[:12], "fylite:ip": np.array([ref["ip"]])},
                  "equilibrium": {"time_slice": {"profiles_1d": {"psi_norm": x,
                                                                 "dpressure_dpsi": np.asarray(g["pprime"], float) / s,
                                                                 "f_df_dpsi": np.asarray(g["ffprim"], float) / s}}}}
        t0 = time.time()
        facts, fields, notes = door("code/forward", {}, inputs)
        got = fylite_map(facts, fields)
        cmpd = compare_maps(ref, got)
        result["cases"][name] = {
            "time_s": int(itime) / 1000.0,
            "inputs": {"g_file": gname, "g_sha256": mem_sha[gname], "a_file": aname, "a_sha256": mem_sha[aname],
                       "coil_aturns": [float(v) for v in np.asarray(a["ccbrsp"], float)[:12]], "ip_A": ref["ip"],
                       "profile_points": int(len(x)), "gauge_factor": s},
            "kefit": {"axis": list(ref["axis"]), "psi_span_Wb": ref["psi_bnd"] - ref["psi_axis"], "q0": float(g["qpsi"][0]),
                      "chi2_afile": float(a.get("tsaisq", float("nan")))},
            "fylite": {k: facts[k] for k in ("converged", "settled", "iterations", "residual", "bnd_kind", "axis_r", "axis_z",
                                             "psi_axis", "psi_bnd", "xpt_r", "xpt_z", "zc", "fb_amp", "ip")},
            "notes": notes, "seconds": round(time.time() - t0, 2), "compare": cmpd}
        print(f"B-14 {name}: axis {cmpd['dR_axis_mm']:+.2f}/{cmpd['dZ_axis_mm']:+.2f} mm · span {100 * cmpd['span_rel']:+.3f} % · "
              f"psiN rms {100 * cmpd['psin_rms_inside']:.2f} % · boundary {cmpd.get('boundary_median_mm', float('nan')):.2f}/"
              f"{cmpd.get('boundary_max_mm', float('nan')):.2f} mm · X {cmpd.get('xpoint_dist_mm', float('nan')):.1f} mm · "
              f"converged {facts['converged']:.0f} settled {facts['settled']:.0f} it {facts['iterations']:.0f}")
    shutil.rmtree(tmp)
    (out / "forward_kefit_east137985.json").write_text(json.dumps(result, indent=1, default=float) + "\n", encoding="utf-8")
    return result


# ------------------------------------------------------------------------------------------------ V-18 / B-15

def twin_truth(case: Path) -> tuple[dict, dict, dict, dict]:
    raw = json.loads((case / RAW_SLICES).read_text(encoding="utf-8"))["fylite:slices"]["4.041"]
    dev = east_card()
    aturns = np.asarray(raw["brsp"], float)
    ip = float(raw["plasma"])
    r0 = float(dev["tf"]["r0"])
    b_tor = abs(raw["tf"]["f_vac_Tm"]) / r0
    settings = dict(TRUTH, r0=r0, b_tor=b_tor, n_profile=201, n_q=20, n_theta=121, x_lo=0.06, x_hi=0.995)
    facts, fields, notes = door("code/forward", settings, {"device": dev,
                                                           "discharge": {"fylite:channel_aturns": aturns, "fylite:ip": np.array([ip])}})
    _, share, _ = door("code/coilshare", {"nu_loops": 8, "nu_probes": 3, "grid_psi": 1, "nu_grid": 4},
                       {"device": dev, "discharge": {"fylite:channel_aturns": aturns}})
    meas = {"flux_loop": fields["loop_model"] + share["loop_coil"], "probe_field": fields["probe_field"],
            "loop_plasma": fields["loop_model"], "loop_coil": share["loop_coil"], "probe_coil": share["probe_coil"],
            "psi_ext": share["psi_ext"], "aturns": aturns, "ip": ip, "b_tor": b_tor}
    truth = {"settings": settings, "facts": facts, "notes": notes,
             "map": fylite_map(facts, fields), "q_x": fields["q_x"], "q": fields["q"],
             "pprime": fields["pprime"], "ffprim": fields["ffprim"], "psin_1d": fields["psin_1d"]}
    return truth, meas, dev, raw


def sigma_weights(meas: dict) -> tuple[np.ndarray, np.ndarray]:
    loops, probes = np.abs(meas["flux_loop"]), np.abs(meas["probe_field"])
    lw = 1.0 / np.maximum(SERROR * loops, 5e-4)
    pw = 1.0 / np.maximum(SERROR * probes, PROBE_BIT)
    return lw, pw


def twin_fylite(truth: dict, meas: dict, dev: dict) -> dict:
    lw, pw = sigma_weights(meas)
    disc = {"fylite:channel_aturns": meas["aturns"], "fylite:ip": np.array([meas["ip"]]), "fylite:b_tor": np.array([meas["b_tor"]]),
            "fylite:flux_loop": meas["flux_loop"], "fylite:loop_weight": lw,
            "fylite:probe_field": meas["probe_field"], "fylite:probe_weight": pw}
    scan, best = [], None
    for zc in ZC_SCAN:
        try:
            facts, fields, notes = door("code/reconstruction", dict(RECON, zc_anchor=zc), {"device": dev, "discharge": disc})
        except Exception as e:  # noqa: BLE001 — a set-point that does not solve is a reading
            scan.append({"zc_m": zc, "error": str(e)[:160]})
            continue
        rl = lw * (fields["loop_model"] + meas["loop_coil"] - meas["flux_loop"])
        rp = pw * (fields["probe_model"] - meas["probe_field"])
        chi2 = float(np.sum(rl ** 2) + np.sum(rp ** 2))
        scan.append({"zc_m": zc, "chi2": chi2, "converged": bool(facts["converged"]), "q0": facts["q0"]})
        if facts["converged"] and (best is None or chi2 < best[0]):
            best = (chi2, zc, facts, fields)
    if best is None:
        return {"zc_scan": scan, "error": "no set-point converged"}
    chi2, zc, facts, fields = best
    bnd = fields["boundary"].reshape(-1, 2) if "boundary" in fields else None
    got = fylite_map(facts, fields, bnd)
    cmpd = compare_maps(truth["map"], got)
    return {"zc_scan": scan, "zc_anchor_m": zc, "chi2": chi2,
            "facts": {k: facts[k] for k in ("converged", "iterations", "residual", "q0", "q95", "li3", "axis_r", "axis_z", "ip")},
            "q0_rel": facts["q0"] / truth["facts"]["q0"] - 1.0, "q95_rel": facts["q95"] / truth["facts"]["q95"] - 1.0,
            "coefficients": [float(v) for v in fields["coefficients"]], "compare": cmpd}


def kefit_namelist(meas: dict, smap: list, limiter: tuple, psibit: np.ndarray) -> str:
    fmt = lambda vals, f: "".join(f % v for v in vals)  # noqa: E731
    exp76 = [meas["probe_field"][i] if i is not None else 0.0 for i in smap]
    fwt76 = [1.0 if i is not None else 0.0 for i in smap]
    fl_b = np.asarray(meas["flux_loop"], float)[35:70]
    lr, lz = limiter
    L = ["&IN1", f"ISHOT ={SHOT}", "ITIME=04041", "RCENTR=1.8", "iplcout=1", f"BTOR={-meas['b_tor'] * 1.75 / 1.8:1.4f}",
         "ivesel=0", "IFITVS=0", "fitdelz=T", f"PLASMA={meas['ip']:12.2f}", "",
         "EXPMP2=", fmt(exp76, "%18.8f"), "coils=", fmt(fl_b, "%18.8f"), "psibit=", fmt(psibit, "%12.5f"),
         "fwtsi=", " ".join(["1"] * 35), "bitmpi=", fmt([PROBE_BIT] * len(smap), "%12.6f"),
         "fwtmp2=", " ".join("%.1f" % v for v in fwt76), "bitip  =40000 ", "FWTCUR  =  1",
         f"limitr  = {len(lr)}", "xlim  = ", fmt(lr, "%12.5f"), "ylim  = ", fmt(lz, "%12.5f"),
         "BRSP  = ", fmt(meas["aturns"], "%18.4f"), "bitfc  =" + fmt(BITFC, "%18.5f"), "FWTFC =12*0.3 ",
         "itek =5 ", "mxiter=-50 ", f"serror={SERROR} ", " error=1e-4 ", " errmin=1e-4", " kersil=1",
         " kcalpa  = 1 ", " calpa =  ", "1.0 1.0 1.0", " xalpa= 0", " kcgama=1", " cgama=  0.1 0.1 0.1 ", " xgama=  0",
         " KFFCUR  = ", "2", " KPPCUR  = ", "2", " pcurbd  = 1.0", " fcurbd  = 1.0", "NEXTRA  = 5", "relax  =0.5",
         " fwtqa  =0", " qvfit  =0.9", "/"]
    return "\n".join(L) + "\n"


def twin_kefit(truth: dict, meas: dict, dev: dict, exe: Path, bundle: Path, out: Path) -> dict:
    from fylite.io import geqdsk
    tables76, pol2 = bundle / "green2022_pcs", bundle / "green2018_wpf_64" / "pol2.est"
    dprobe = (tables76 / "dprobe.dat").read_text(encoding="latin-1")

    def arr(key):
        m = re.search(r"\b" + key + r"\s*=\s*(.*?)(?=\b[A-Za-z_][A-Za-z0-9_]*\s*=|/|\Z)", dprobe, re.S | re.I)
        vals: list[float] = []
        for n, rv, v in re.findall(r"(\d+)\*([-+]?[\d.]+(?:[eEdD][-+]?\d+)?)|([-+]?[\d.]+(?:[eEdD][-+]?\d+)?)", m.group(1)):
            vals += [float(rv)] * int(n) if n else [float(v)]
        return np.array(vals)
    probes = dev["magnetics"]["b_field_pol_probe"]
    pr = np.array([[p["position"][0]["r"], p["position"][0]["z"]] for p in probes])
    pa = np.degrees([p["poloidal_angle"] for p in probes])
    smap = []
    for x, y, ang in zip(arr("XMP2"), arr("YMP2"), arr("AMP2")):
        hit = [i for i in np.where((np.hypot(pr[:, 0] - x, pr[:, 1] - y) < 1e-3) & (np.abs((pa - ang + 180) % 360 - 180) < 0.1))[0]
               if i not in range(74, 79)]
        smap.append(int(hit[0]) if len(hit) == 1 else None)
    psibit = np.abs(np.loadtxt(bundle / "efit" / "2016" / "psibit.txt")) / TWO_PI
    lim = (truth["map"]["limiter_r"], truth["map"]["limiter_z"]) if "limiter_r" in truth["map"] else None
    if lim[0] is None:
        raise SystemExit("the truth map carries no limiter")
    d = out / "kefit_twin" / "t4041_twin"
    if d.exists():
        shutil.rmtree(d)
    (d / "tables").mkdir(parents=True)
    for p in tables76.iterdir():
        if p.is_file() and p.name != "pol2.est":
            (d / "tables" / p.name).symlink_to(p)
    (d / "tables" / "pol2.est").symlink_to(pol2)
    text = kefit_namelist(meas, smap, lim, psibit)
    (d / "temp").write_text(text, encoding="utf-8")
    p = subprocess.run([str(exe)], cwd=d, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
    (d / "run.log").write_text(p.stdout + p.stderr, encoding="utf-8")
    (d / "run.rc").write_text(f"rc={p.returncode}\n", encoding="utf-8")
    (d / "slot_map.json").write_text(json.dumps({"kefit76_slot_to_card_slot": smap}) + "\n", encoding="utf-8")
    shutil.rmtree(d / "tables")
    gs = sorted(d.glob(f"g{SHOT}.*"))
    problems = sorted(set(re.findall(r"(Problem in \w+|Error #\s*\d+)", p.stdout + p.stderr +
                                     ((d / "errfil.out").read_text(encoding="latin-1") if (d / "errfil.out").exists() else ""))))
    if not gs:
        return {"g_file": False, "problems": problems}
    g = geqdsk.read_geqdsk(gs[0])
    ref = kefit_map(g)
    cmpd = compare_maps(truth["map"], {**ref, "boundary": ref["boundary"]})
    q = np.asarray(g["qpsi"], float)
    xq = np.linspace(0, 1, len(q))
    return {"g_file": True, "problems": problems, "unmatched_kefit_slots": [j for j, i in enumerate(smap) if i is None],
            "q0": float(q[0]), "q95": float(np.interp(0.95, xq, q)),
            "q0_rel": float(q[0]) / truth["facts"]["q0"] - 1.0, "q95_rel": float(np.interp(0.95, xq, q)) / truth["facts"]["q95"] - 1.0,
            "ip_A": abs(float(g["current"])), "compare": cmpd}


def twin(case: Path, out: Path, exe: Path | None, bundle: Path | None) -> dict:
    truth, meas, dev, raw = twin_truth(case)
    truth["map"]["limiter_r"], truth["map"]["limiter_z"] = None, None
    lim_f = door("code/forward", dict(truth["settings"]), {"device": dev, "discharge": {
        "fylite:channel_aturns": meas["aturns"], "fylite:ip": np.array([meas["ip"]])}})[1]
    truth["map"]["limiter_r"], truth["map"]["limiter_z"] = lim_f["limiter_r"], lim_f["limiter_z"]
    f = truth["facts"]
    print(f"twin truth: axis ({f['axis_r']:.4f}, {f['axis_z']:+.4f}) q0 {f['q0']:.3f} q95 {f['q95']:.3f} "
          f"converged {f['converged']:.0f} it {f['iterations']:.0f}")
    fy = twin_fylite(truth, meas, dev)
    c = fy.get("compare", {})
    print(f"V-18 fylite: zc {fy.get('zc_anchor_m')} chi2 {fy.get('chi2', float('nan')):.3g} q0 {fy.get('q0_rel', float('nan')) * 100:+.2f} % "
          f"axis {c.get('dR_axis_mm', float('nan')):+.2f}/{c.get('dZ_axis_mm', float('nan')):+.2f} mm psiN {100 * c.get('psin_rms_inside', float('nan')):.3f} %")
    kef = None
    if exe is not None:
        kef = twin_kefit(truth, meas, dev, exe, bundle, out)
        c = kef.get("compare", {})
        print(f"B-15 KEFIT: {kef.get('problems')} q0 {kef.get('q0_rel', float('nan')) * 100:+.2f} % "
              f"axis {c.get('dR_axis_mm', float('nan')):+.2f}/{c.get('dZ_axis_mm', float('nan')):+.2f} mm psiN {100 * c.get('psin_rms_inside', float('nan')):.3f} %")
    rec = {"truth": {"settings": truth["settings"], "facts": {k: f[k] for k in ("converged", "settled", "iterations", "residual", "axis_r",
                                                                                 "axis_z", "psi_axis", "psi_bnd", "q0", "q95", "ip", "zc")},
                     "coil_aturns_source": "CASE-23 raw/raw_slices_east137985.json 4.041 s brsp (east tree PF1P..PF12P x turns)",
                     "ip_source": "same slice, pcs_east \\PCRL01", "b_tor_source": "same slice, F_vac / tf.r0"},
           "measurements": {"flux_loop": meas["flux_loop"].tolist(), "probe_field": meas["probe_field"].tolist(),
                            "n_loops": int(len(meas["flux_loop"])), "n_probes": int(len(meas["probe_field"]))},
           "fylite": fy, "kefit": kef}
    (out / "twin_east137985.json").write_text(json.dumps(rec, indent=1, default=float) + "\n", encoding="utf-8")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("forward-kefit")
    a1.add_argument("--case")
    a1.add_argument("--out", required=True, type=Path)
    a2 = sub.add_parser("twin")
    a2.add_argument("--case")
    a2.add_argument("--out", required=True, type=Path)
    a2.add_argument("--kefit-exe", type=Path)
    a2.add_argument("--kefit-bundle", type=Path, default=Path(os.environ.get("KEFIT_BUNDLE", ROOT.parent / "third_party" / "kefit_reference_bundle")))
    a3 = sub.add_parser("pack")
    a3.add_argument("src", type=Path)
    a3.add_argument("dest", type=Path)
    a3.add_argument("--prefix", required=True)
    a = ap.parse_args()
    if a.cmd == "forward-kefit":
        a.out.mkdir(parents=True, exist_ok=True)
        forward_kefit(case_dir(a.case), a.out)
    elif a.cmd == "twin":
        a.out.mkdir(parents=True, exist_ok=True)
        twin(case_dir(a.case), a.out, a.kefit_exe, a.kefit_bundle)
    elif a.cmd == "pack":
        members = [(f"{a.prefix}/{p.relative_to(a.src)}", p.read_bytes()) for p in sorted(a.src.rglob("*"))
                   if p.is_file() and not p.is_symlink()]
        blob = pack(members)
        a.dest.write_bytes(blob)
        index = {"@context": {"fylite": "urn:fylite:"}, "@type": "fylite:ArchiveIndex", "fylite:archive": a.dest.name,
                 "fylite:sha256": sha(blob), "fylite:members": [{"path": n, "bytes": len(b), "sha256": sha(b)} for n, b in members]}
        a.dest.with_name(a.dest.name.replace(".tar.gz", ".index.json")).write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
        print(f"packed {len(members)} members -> {a.dest} ({sha(blob)[:16]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
