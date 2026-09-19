"""Heating and current drive (FR-TR-004 · NR-TR-001): the readings of the `tr-sources` records.

Subcommands, each writing one reading into ``docs/benchmark/readings``:

``closure``  — every family's power account, through the tree doors: `code/beam` (NBI: P_inj = P_abs + P_shine +
               P_orbit, and the deposited profile's volume integral = P_abs), `code/wave` (LH: the deposited profile's
               volume integral = P_deposited, launched − reflected = absorbed) on EAST #137985 t = 4.041 s (CASE-23), and
               `code/rf_ray` (EC: launched = absorbed + left + not traced, the shells = absorbed) on CFEDR 20 MA.
``toray``    — `code/rf_ray` against TORAY-GA's own answer on CFEDR 20 MA (fydoc CASE-21, frozen by the kernel's
               `rust/tools/gen_cfedr_toray_reference.py`): the branch, the ray on matched flux surfaces, N∥, the
               deposition peak and the driven current per watt.  ★Clean room: TORAY's DATA, never its source.
``kernel``   — the kernel's METIS comparisons (ICRH, ECCD) and the ICRH profile closure: their `[register]` lines,
               parsed from ``cargo test -- --nocapture``.
``icrh``     — `code/icrh` (the ICRH door, 2026-09-19) re-run on METIS's certification rows (fydoc CASE-10): the layer,
               the minority tail, the electron / ion split and the profile, each row through the door.
``nbi``      — `code/beam` against NUBEAM (TRANSP `nubeam_comp_exec` DIII-D test: plasma state in, NUBEAM's state out).
``lh``       — `code/wave` against GENRAY (EAST #71230 at 4.8 s, 2.45 GHz, four rays; the BORAY repository's data).

★Clean room: NUBEAM / GENRAY are read through their DATA (netCDF, run log, g-file), never their source.

★The TORAY reference is internal (`release: internal`, derived from a restricted corpus) and stays in the kernel
repository: this tool reads it from ``$FYLITE_KERNEL`` and writes only comparison scalars, never its profiles.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
READINGS = ROOT / "docs" / "benchmark" / "readings"
TORAY_REF = "rust/fylite/testdata/reference/cfedr_toray_20ma.txt"
#: the surfaces the two rays are compared ON — matched psi_N, not matched index: TORAY's trajectory starts at the
#: plasma entry and ours at the launcher, so "the first point" is two different places
SURFACES = (0.9, 0.7, 0.5, 0.35, 0.25)


def _tool(module: str, fname: str):
    spec = importlib.util.spec_from_file_location(module, ROOT / "tools" / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def complete(code: str, request: dict) -> dict:
    from fylite.io import fydoc
    return fydoc.complete(code, request)


def facts(rec: dict) -> dict:
    return {k: float(v["value"]) for k, v in rec["facts"].items()}


def field(rec: dict, k: str) -> np.ndarray:
    return np.asarray(rec["fields"][k]["data"], float)


def kernel_dir() -> Path:
    k = os.environ.get("FYLITE_KERNEL")
    if not k:
        raise FileNotFoundError("set $FYLITE_KERNEL to a fylite_kernel checkout (the TORAY reference lives there)")
    return Path(k)


# --- EAST #137985 t = 4.041 s: the equilibrium the NBI and LH accounts run on ------------------------------------

def east_doc() -> dict:
    from fylite import fyo
    from fylite.io import geqdsk
    bme = _tool("bme", "benchmark-equilibrium.py")
    case = Path(os.environ.get("FYDOC_ORACLE", ROOT.parent / "fydoc" / "cases")) / "FYDOC-CASE-23-east-137985-efit-east"
    members = bme.tar_members(case / bme.KEFIT_TAR)
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "g").write_bytes(members["kefit_raw_east137985/all_probes/t4041_mag/g137985.04041"])
        return fyo.equilibrium(geqdsk.read_geqdsk(Path(d) / "g"))


def east_profiles(n: int = 41) -> dict:
    """★Stated profiles, not measured ones: the account is an identity, so the plasma only has to be plausible."""
    x = np.linspace(0.0, 1.0, n)
    return {"profiles_1d": {"grid": {"psi_norm": x},
                            "electrons": {"density": 4.0e19 * (1.0 - 0.8 * x ** 2),
                                          "temperature": 2500.0 * (1.0 - 0.9 * x ** 2) + 50.0},
                            "zeff": 1.5 + 1.0 * x ** 2}}


#: EAST-like beams: a co beam with three energy components, and a counter beam near the edge so the first-orbit
#: loss is not zero — the account must close with all three sinks carrying power
NBI = [{"name": "co", "energy": 6.5e4, "power": 2.0e6, "rtan": 1.26, "z": 0.0, "dir": 1.0, "fr": (0.7, 0.2, 0.1)},
       {"name": "ctr", "energy": 8.0e4, "power": 1.5e6, "rtan": 1.60, "z": 0.05, "dir": -1.0, "fr": (0.8, 0.15, 0.05)}]
#: EAST-like LH: 4.6 GHz and 2.45 GHz, one with reflected power
LH = [{"name": "LH1", "frequency": 4.6e9, "power": 1.5e6, "reflected": 1.0e5, "band": (1.8, 2.4)},
      {"name": "LH2", "frequency": 2.45e9, "power": 0.8e6, "reflected": 0.0, "band": (2.0, 2.6)}]


def nbi_closure(doc: dict) -> dict:
    units = [{"name": b["name"], "energy": {"data": b["energy"]}, "power_launched": {"data": b["power"]},
              "beam_power_fraction": {"data": np.asarray(b["fr"], float)}, "species": {"a": 2.0, "z_n": 1.0},
              "beamlets_group": [{"tangency_radius": b["rtan"], "position": {"z": b["z"]}, "direction": b["dir"],
                                  "width_horizontal": 0.10, "width_vertical": 0.10}]} for b in NBI]
    rec = complete("code/beam", {"settings": {"stopping_model": "metis"},
                                 "inputs": {"equilibrium": doc, "core_profiles": east_profiles(), "nbi": {"unit": units}}})
    f = facts(rec)
    p_inj, p_abs = f["p_injected"], f["p_absorbed"]
    shine, orbit = f["shinethrough"] * p_inj, f["orbit_loss_fraction"] * p_inj
    dep = float(np.sum(field(rec, "p_dep") * field(rec, "dvolume")))
    declared = sum(b["power"] for b in NBI)
    return {"door": "code/beam", "beams": [{k: b[k] for k in ("name", "energy", "power", "rtan", "dir", "fr")} for b in NBI],
            "p_declared_W": declared, "p_injected_W": p_inj, "p_absorbed_W": p_abs, "p_shine_W": shine, "p_orbit_W": orbit,
            "per_beam_absorbed_W": field(rec, "beam_absorbed").tolist(),
            "injected_vs_declared_rel": abs(p_inj / declared - 1.0),
            "closure_rel": abs((p_abs + shine + orbit) / p_inj - 1.0),
            "profile_integral_rel": abs(dep / p_abs - 1.0),
            "i_nbi_A": f["i_nbi"]}


def lh_closure(doc: dict) -> dict:
    ants = [{"name": a["name"], "frequency": a["frequency"],
             "power_launched": {"data": a["power"] + a["reflected"]}, "power_reflected": {"data": a["reflected"]},
             "fylite:n_parallel_min": a["band"][0], "fylite:n_parallel_max": a["band"][1]} for a in LH]
    rec = complete("code/wave", {"settings": {"eta_cd": 1.0e19, "upshift_min": 1.5, "upshift_max": 2.5},
                                 "inputs": {"equilibrium": doc, "core_profiles": east_profiles(),
                                            "lh_antennas": {"antenna": ants}}})
    f = facts(rec)
    src = rec["fields"]["core_sources"]["source"]["0"]["profiles_1d"]
    p_prof = np.asarray(src["electrons"]["energy"]["data"], float)
    dv = field(rec, "dvolume")
    coupled = sum(a["power"] for a in LH)
    return {"door": "code/wave", "antennas": [{k: a[k] for k in ("name", "frequency", "power", "reflected", "band")} for a in LH],
            "deposited": f["deposited"], "p_coupled_W": coupled, "p_absorbed_W": f["p_absorbed"],
            "p_deposited_W": f["p_deposited"], "i_lh_A": f["i_lh"],
            "absorbed_vs_coupled_rel": abs(f["p_absorbed"] / coupled - 1.0),
            "profile_integral_rel": abs(float(np.sum(p_prof * dv)) / f["p_deposited"] - 1.0),
            "per_launcher_sum_rel": abs(float(field(rec, "launcher_power").sum()) / f["p_absorbed"] - 1.0)}


# --- CFEDR 20 MA: TORAY's own run (fydoc CASE-21) ---------------------------------------------------------------

def toray_ref() -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for line in (kernel_dir() / TORAY_REF).read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        p = line.split()
        v = np.array([float(x) for x in p[2:]], float)
        assert v.size == int(p[1]), p[0]
        out[p[0]] = v
    return out


def one(ref, key: str) -> float:
    return float(ref[key][0])


def our_angles(ref) -> tuple[float, float]:
    """The launch direction (launcher -> TORAY's first ray point) in the kernel's convention
    `[-cos(pol)cos(tor), -sin(tor), -sin(pol)cos(tor)]` — inverted by arithmetic, as the kernel's oracle test does."""
    lp = np.array([one(ref, "x0"), one(ref, "y0"), one(ref, "z0")])
    phi = ref["ray0_wphi"][0]
    p0 = np.array([ref["ray0_wr"][0] * math.cos(phi), ref["ray0_wr"][0] * math.sin(phi), ref["ray0_wz"][0]])
    d = (p0 - lp) / np.linalg.norm(p0 - lp)
    tor = math.asin(max(-1.0, min(1.0, -d[1])))
    ct = math.cos(tor)
    return math.atan2(-d[2] / ct, -d[0] / ct), tor


def cfedr_doc(ref) -> dict:
    nr, nz = int(one(ref, "nr")), int(one(ref, "nz"))
    return {"time_slice": {
        "global_quantities": {"psi_axis": one(ref, "simag"), "psi_boundary": one(ref, "sibry"), "ip": one(ref, "tot_cur"),
                              "magnetic_axis": {"r": one(ref, "rmaxis"), "z": one(ref, "zmaxis")}},
        "profiles_1d": {"f": ref["fpol"]},
        "profiles_2d": {"grid": {"dim1": ref["grid_r"], "dim2": ref["grid_z"]}, "psi": ref["psi_rz"].reshape(nr, nz)},
        "boundary": {"outline": {"r": ref["boundary_r"], "z": ref["boundary_z"]}}},
        "vacuum_toroidal_field": {"r0": one(ref, "rcentr"), "b0": one(ref, "bcentr")}}


def cfedr_plan(ref, doc, *, mode: float, **settings) -> dict:
    pol, tor = our_angles(ref)
    beam = {"name": "EC", "frequency": {"data": one(ref, "freqcy")},
            "power_launched": {"data": 1.0e-7 * one(ref, "nml_powinc")},
            "launching_position": {"r": 0.01 * one(ref, "x0"), "z": 0.01 * one(ref, "z0")},
            "fylite:angle_pol": pol, "fylite:angle_tor": tor, "mode": mode}
    cp = {"profiles_1d": {"grid": {"psi_norm": ref["xbouni"]},
                          "electrons": {"density": 1.0e6 * ref["xene"], "temperature": 1.0e3 * ref["xete"]}}}
    return {"settings": {k: float(v) for k, v in settings.items()},
            "inputs": {"equilibrium": doc, "core_profiles": cp, "ec_launchers": {"beam": [beam]}}}


def rays(rec) -> np.ndarray:
    d = rec["dims"]
    a = field(rec, "rays").reshape(int(d["n_point"]), int(d["n_col"]))
    return a[a[:, 0] == 0][:, 1:]


def inbound(psin, value, at) -> np.ndarray:
    k = int(np.argmin(psin)) + 1
    x, y = psin[:k][::-1], value[:k][::-1]
    keep = np.concatenate(([True], np.diff(x) > 0))
    return np.interp(np.asarray(at, float), x[keep], y[keep])


def toray_path(ref):
    return (ref["ray0_spsi"] ** 2, np.hypot(ref["ray0_wnpar"], ref["ray0_wnper"]), ref["ray0_wnpar"],
            0.01 * ref["ray0_wr"], 0.01 * ref["ray0_wz"])


def toray() -> dict:
    ref = toray_ref()
    doc = cfedr_doc(ref)
    psin_t, n_t, npar_t, r_t, z_t = toray_path(ref)
    #: the branch is READ OFF the data (|N| on matched surfaces), not chosen to match
    branch = {}
    for name, m in (("O", 1.0), ("X", -1.0)):
        rec = complete("code/rf_ray", cfedr_plan(ref, doc, mode=m))
        if int(facts(rec)["n_traced"]) == 1:
            p = rays(rec)
            branch[name] = (m, float(np.max(np.abs(inbound(p[:, 6], p[:, 5], SURFACES) / inbound(psin_t, n_t, SURFACES) - 1.0))))
    best = min(branch, key=lambda k: branch[k][1])
    mode = branch[best][0]
    pts = rays(complete("code/rf_ray", cfedr_plan(ref, doc, mode=mode)))
    s_, r, z, _phi, npar, _n, psin = pts.T
    dr = np.abs(inbound(psin, r, SURFACES) - inbound(psin_t, r_t, SURFACES))
    dz = np.abs(inbound(psin, z, SURFACES) - inbound(psin_t, z_t, SURFACES))
    npar_rel = np.abs(inbound(psin, npar, SURFACES) / inbound(psin_t, npar_t, SURFACES) - 1.0)
    rec = complete("code/rf_ray", cfedr_plan(ref, doc, mode=mode, deposit=1.0))
    f = facts(rec)
    shells = field(rec, "power_shell").ravel()
    e = field(rec, "shell_edges")
    centres = 0.5 * (e[1:] + e[:-1])
    k = int(np.argmax(ref["weecrh"]))
    peak_t = float(np.interp(float(ref["xmrho"][k]), ref["xrho"], ref["xbouni"]))
    peak_o = float(centres[int(np.argmax(shells))])
    zeff = float(np.interp(float(ref["xmrho"][k]), ref["xrho"], ref["xzeff"]))
    fc = facts(complete("code/rf_ray", cfedr_plan(ref, doc, mode=mode, deposit=1.0, current_drive=1.0, zeff=zeff)))
    ipw_o, ipw_t = fc["current_driven"] / fc["power_launched"], float(ref["tidept"][-1])
    return {"what": "EC：code/rf_ray 对 TORAY-GA 自己的答案，CFEDR 20 MA（fydoc CASE-21；参考冻结于内核仓 "
                    f"{TORAY_REF}，内部件——本读数只记比较量）",
            "reference": {"code": "TORAY-GA", "case": "FYDOC-CASE-21-cfedr-hmode-20ma", "frozen": TORAY_REF},
            "surfaces_psin": list(SURFACES),
            "branch": {"identified": best, "n_abs_rel_worst": {k: v[1] for k, v in branch.items()}},
            "ray": {"dr_mm_max": 1e3 * float(dr.max()), "dz_mm_max": 1e3 * float(dz.max()),
                    "deepest_psin": float(psin.min()), "deepest_psin_toray": float(psin_t.min()),
                    "deepest_rel": abs(float(psin.min()) / float(psin_t.min()) - 1.0),
                    "npar_rel_max": float(npar_rel.max())},
            "deposition": {"absorbed_fraction": f["power_absorbed"] / f["power_launched"],
                           "absorbed_fraction_toray": float(ref["tpowde"][-1]),
                           "peak_psin": peak_o, "peak_psin_toray": peak_t, "peak_dpsin": abs(peak_o - peak_t),
                           "shell_width": float(np.median(np.diff(e)))},
            "current": {"zeff_at_peak": zeff, "a_per_w": ipw_o, "a_per_w_toray": ipw_t, "ratio": ipw_o / ipw_t}}


def ec_closure() -> dict:
    ref = toray_ref()
    doc = cfedr_doc(ref)
    #: the branch TORAY launched (O, identified in `toray`); the account holds on either
    rec = complete("code/rf_ray", cfedr_plan(ref, doc, mode=1.0, deposit=1.0))
    f = facts(rec)
    shells = field(rec, "power_shell").ravel()
    p_e, vol = field(rec, "p_e").ravel(), field(rec, "shell_volume").ravel()
    outside = float(field(rec, "absorption").ravel()[3])
    return {"door": "code/rf_ray", "case": "CFEDR 20 MA (FYDOC-CASE-21)",
            "p_launched_W": f["power_launched"], "p_absorbed_W": f["power_absorbed"], "p_left_W": f["power_left"],
            "p_not_traced_W": f["power_not_traced"], "p_outside_shells_W": outside,
            "closure_rel": abs((f["power_absorbed"] + f["power_left"] + f["power_not_traced"]) / f["power_launched"] - 1.0),
            #: the shells and what was absorbed beyond the last one are the absorbed power (`absorption` = [.., tau,
            #: fraction, outside], the kernel's own gate on this identity is 1e-9)
            "shells_plus_outside_rel": abs((float(shells.sum()) + outside) / f["power_absorbed"] - 1.0),
            #: the density is the shell power over the shell volume, and back
            "density_times_volume_rel": float(np.max(np.abs(p_e * vol - shells)) / shells.max())}


def closure() -> dict:
    doc = east_doc()
    return {"what": "加热与电流驱动的功率账（NR-TR-001 第三句：源沉积积分闭合到注入额定值；FR-TR-004 的源族表）："
                    "NBI · LH 在 EAST #137985 t = 4.041 s（CASE-23 KEFIT），EC 在 CFEDR 20 MA（CASE-21）；IC 见内核读数",
            "profiles": "stated (ne 4e19 (1 − 0.8 x²), Te 2.5 keV (1 − 0.9 x²) + 50 eV, Zeff 1.5 + x², x = psi_N)",
            "nbi": nbi_closure(doc), "lh": lh_closure(doc), "ec": ec_closure()}


# --- the kernel's own METIS comparisons -------------------------------------------------------------------------

def kernel_readings(log: Path) -> dict:
    text = log.read_text(encoding="utf-8", errors="replace")
    reg = {}
    for m in re.finditer(r"\[register\] (\w+) (.*)", text):
        toks = m.group(2).split()
        reg[m.group(1)] = {toks[i]: float(toks[i + 1]) for i in range(0, len(toks) - 1, 2)}
    band = re.search(r"ECCD band over (\d+) rows: ours/METIS min/median/max \(([^)]*)\); ours/Giruzzi \(([^)]*)\); "
                     r"log-log correlation with METIS ([\d.]+), with the fit ([\d.]+)", text)
    if band is None or not reg:
        raise SystemExit(f"{log}: no [register] lines / ECCD band line — run the kernel tests with --nocapture")
    lo, med, hi = (float(x) for x in band.group(2).split(","))
    glo, gmed, ghi = (float(x) for x in band.group(3).split(","))
    reg["eccd_adjoint"] = {"rows": float(band.group(1)), "ratio_min": lo, "ratio_median": med, "ratio_max": hi,
                           "vs_fit_min": glo, "vs_fit_median": gmed, "vs_fit_max": ghi,
                           "loglog_corr_metis": float(band.group(4)), "loglog_corr_fit": float(band.group(5))}
    return {"what": "内核仓 heating / rfray 的 METIS 对照与 ICRH 剖面闭合：`cargo test -- --nocapture` 打出的 [register] 行",
            "reference": {"code": "METIS", "table": "FYDOC-CASE-10-metis/corpus/metis_cert_hcd.csv",
                          "fwcd": "METIS fitetafwcd.m measurements (JFT-2M · DIII-D · Tore-Supra)"},
            "tests": {"icrh_layer": "heating::tests::the_resonance_layer_is_where_metis_puts_it",
                      "icrh_tail": "heating::tests::the_tail_is_built_from_metis_own_ingredients",
                      "icrh_split": "heating::tests::the_split_and_the_tail_land_in_metis_band",
                      "icrh_unsettled": "heating::tests::the_unsettled_rows_are_excluded_because_they_disagree_wildly",
                      "icrh_profile": "heating::tests::the_profile_shape_reproduces_the_one_metis_wrote",
                      "icrh_closure": "heating::tests::the_icrh_profile_is_a_gaussian_on_the_layer_that_carries_its_power",
                      "fwcd_measured": "heating::tests::the_fwcd_efficiency_reproduces_the_measurements_it_was_fitted_to",
                      "eccd_giruzzi": "heating::tests::the_eccd_efficiency_reproduces_metis_driven_current",
                      "eccd_adjoint": "rfray::tests::the_adjoint_eccd_sits_in_the_band_of_metis_and_its_giruzzi_fit"},
            "readings": dict(sorted(reg.items()))}


THIRD = Path(os.environ.get("FYLITE_THIRD_PARTY", ROOT.parent / "third_party"))
QE = 1.602176634e-19


# --- ICRH through its door, on METIS's certification rows ---------------------------------------------------------

METIS_HCD = "FYDOC-CASE-10-metis/corpus/metis_cert_hcd.csv"


def metis_icrh_rows() -> list[dict]:
    """The kernel test's own reading of the table (heating.rs `metis_rows`), row for row."""
    import csv
    path = Path(os.environ.get("FYDOC_ORACLE", ROOT.parent / "fydoc" / "cases")) / METIS_HCD
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    rows = []
    for r in csv.DictReader(lines):
        g = lambda k: float(r[k]) if r[k].strip() else float("nan")  # noqa: E731
        if not (g("picrh") > 1e4 and math.isfinite(g("rres"))):
            continue
        gas = {1: "H", 2: "D", 3: "DT"}.get(int(g("gaz")), "He")
        frac = {"H": max(g("n1m") - g("nDm") - g("nTm"), 1e13), "D": g("nDm"), "DT": g("nDm"), "He": g("nhem")}[gas]
        rows.append({"case": r["case"], "steady": r["steady"].strip() == "1", "ripple": g("rip") > 0.5,
                     "settings": {"frequency": g("freq_mhz") * 1e6, "n_phi": g("nphi"), "c_min": g("cmin"),
                                  "iso": g("iso"), "fact": g("fact_mino"), "loss_fraction": g("frloss_icrh"),
                                  "ripple": 1.0 if g("rip") > 0.5 else 0.0,
                                  "r0": g("R"), "a": g("a"), "kappa": g("K"), "b0": g("b0"), "shift": g("d0"),
                                  "q0": g("q0"), "q_min": g("qmin"), "q_a": g("qa"), "volume": g("vp"), "area_pol": g("sp"),
                                  "te": g("te_res"), "ti": g("ti_res"), "ne": g("ne_res"),
                                  "n_background": g("ne_res") * frac / g("nem"), "n_helium": g("nhe_res"), "zeff": g("zeff"),
                                  "p_launched": g("picrh"), "minority": r["mino"].strip(), "gas": gas},
                     "metis": {k: g(k) for k in ("rres", "xres", "harm", "nmino", "fracmino", "ecrit_icrh", "taus_icrh",
                                                 "pel_icrh", "esup_icrh", "picrh_x_peak", "picrh_width")}})
    return rows


def icrh() -> dict:
    rows = metis_icrh_rows()
    judged, refused = [], []
    for r in rows:
        try:
            rec = complete("code/icrh", {"settings": r["settings"], "inputs": {}})
        except Exception as e:  # noqa: BLE001 — a named refusal is the answer for the rippled machine
            refused.append({"case": r["case"], "ripple": r["ripple"], "refusal": str(e)[:160]})
            continue
        judged.append((r, facts(rec)))
    rel = lambda a, b: abs(a / b - 1.0)  # noqa: E731
    lay = [rel(f["r_res"], r["metis"]["rres"]) for r, f in judged]
    tail = {k: max(rel(f[fk], r["metis"][mk]) for r, f in judged)
            for k, fk, mk in (("n_min", "n_minority", "nmino"), ("fraction", "volume_fraction", "fracmino"),
                              ("e_crit", "e_crit", "ecrit_icrh"), ("tau_s", "tau_s", "taus_icrh"))}
    steady = [(r, f) for r, f in judged if r["steady"] and r["metis"]["pel_icrh"] > 0 and r["metis"]["esup_icrh"] > 0]
    unsettled = [f["p_el"] / r["metis"]["pel_icrh"] for r, f in judged if not r["steady"] and r["metis"]["pel_icrh"] > 0]
    prof = [(r, f) for r, f in judged if r["metis"]["picrh_width"] > 0 and r["metis"]["picrh_x_peak"] >= 0]
    pel = [f["p_el"] / r["metis"]["pel_icrh"] for r, f in steady]
    wf = [f["w_fast"] / r["metis"]["esup_icrh"] for r, f in steady]
    split = [abs(f["p_el"] + f["p_ion"] - f["p_absorbed"]) / f["p_absorbed"] for _, f in judged]
    return {"what": "ICRH：code/icrh 经门重跑 METIS 认证库的 ICRH 行（fydoc CASE-10），与内核测试同一读法、同一批行",
            "reference": {"code": "METIS", "table": METIS_HCD},
            "rows": {"icrh": len(rows), "through_the_door": len(judged), "refused": refused},
            "layer": {"rows": len(judged), "r_res_rel_max": max(lay), "r_res_rel_median": float(np.median(lay)),
                      "x_res_abs_max": max(abs(f["x_res"] - r["metis"]["xres"]) for r, f in judged),
                      "harmonic_mismatches": sum(f["harmonic"] != r["metis"]["harm"] for r, f in judged)},
            "tail": {"rows": len(judged), **{f"{k}_rel_max": v for k, v in tail.items()}},
            "split": {"rows": len(steady), "p_el_ratio_min": min(pel), "p_el_ratio_max": max(pel),
                      "w_fast_ratio_min": min(wf), "w_fast_ratio_max": max(wf), "closure_rel_max": max(split)},
            "unsettled": {"rows": len(unsettled), "p_el_ratio_min": min(unsettled), "p_el_ratio_max": max(unsettled)},
            "profile": {"rows": len(prof),
                        "peak_abs_max": max(abs(f["x_peak"] - r["metis"]["picrh_x_peak"]) for r, f in prof),
                        "width_rel_max": max(rel(f["volume_fraction"], r["metis"]["picrh_width"]) for r, f in prof)}}


# --- NBI against NUBEAM ---------------------------------------------------------------------------------------------

NUBEAM_DIR = "transp_2201/codesys/source/nubeam_comp_exec"


def _nc(ds, k) -> np.ndarray:
    return np.asarray(ds.variables[k][:], float)


def nubeam() -> dict:
    """NUBEAM's own answer on the DIII-D test (D3D 118419, t = 3.995 s): plasma state in, state out, and the run log.

    ★Its answer is a TRANSIENT: the log runs INIT then two 10 ms steps from no fast ions, and W_fast is still rising at
    6.2 MW.  What it can judge is where and how many beam ions are BORN (a prompt quantity); what the ions then do
    (heating split, current, stored energy) it answers 20 ms into their life, which a steady model does not."""
    import netCDF4
    ref = THIRD / NUBEAM_DIR
    a, b = netCDF4.Dataset(ref / "d3d_input_state.cdf"), netCDF4.Dataset(ref / "d3d_output_state.cdf")
    rho, vol = _nc(a, "rho_nbi"), _nc(a, "vol")
    dvol = np.diff(vol)
    psin_b = _nc(a, "psipol") / _nc(a, "psipol")[-1]
    psin_c = np.interp(0.5 * (rho[1:] + rho[:-1]), rho, psin_b)
    pbe, pbi, pbth, cur = _nc(b, "pbe"), _nc(b, "pbi"), _nc(b, "pbth"), _nc(b, "curbeam")
    nb, eperp, epll = _nc(b, "nbeami")[0], _nc(b, "eperp_beami")[0], _nc(b, "epll_beami")[0]
    sbedep, sbtherm = _nc(b, "sbedep"), _nc(b, "sbtherm")[0]
    power, kv = _nc(a, "power_nbi"), _nc(a, "kvolt_nbi")
    ff, fh = _nc(b, "frac_full"), _nc(b, "frac_half")
    ft = 1.0 - ff - fh
    steps = [tuple(float(x) for x in m) for m in re.findall(
        r"D_beam: N=\s*([\d.E+-]+) <<Eperp>>=\s*([\d.E+-]+) <<Epll>>=\s*([\d.E+-]+)", (ref / "d3d_test.msgs").read_text())]
    dt = 0.010
    w_steps = [n * (ep + el) * 1e3 * QE for n, ep, el in steps]
    dwdt, dndt = (w_steps[1] - w_steps[0]) / dt, (steps[1][0] - steps[0][0]) / dt
    #: ★NUBEAM's frac_* are read as neutral-ATOM current fractions ("fraction of beam current"); particle balance
    #: favours it (birth >= 9.64e20/s against 9.88e20/s this way, 1.21e21/s if they were power fractions)
    inv = ff + fh / 2 + ft / 3
    pfrac = np.stack([ff, fh / 2, ft / 3], 1) / inv[:, None]
    heat = pbe + pbi + pbth

    def centroid(p):
        return float(np.sum(psin_c * p) / np.sum(p))

    def half(p):
        c = np.concatenate(([0.0], np.cumsum(p))) / np.sum(p)
        return float(np.interp(0.5, c, psin_b))

    geo = {k: _nc(a, k) for k in ("sRtcen", "Lbsctan", "Zbsc", "b_halfwidth", "b_halfHeight", "b_Hdivergence",
                                  "b_Vdivergence", "b_Vfocal_length")}
    return {"a": a, "rho": rho, "psin_b": psin_b, "psin_c": psin_c, "dvol": dvol, "pfrac": pfrac, "power": power, "kv": kv,
            "geo": geo, "source_weight_step1": steps[0][0] / (dt * (dndt + float(sbtherm.sum()))),
            "out": {"p_injected_W": float(power.sum()), "beams_on": int(np.sum(power > 0)), "energy_keV": kv.tolist(),
                    "power_fractions": pfrac.round(4).tolist(),
                    "steps": len(steps), "dt_s": dt, "W_fast_J": w_steps, "dW_fast_dt_W": dwdt,
                    "birth_rate_lower_bound": dndt + float(sbtherm.sum()),
                    "loss_fraction_est": 1.0 - (float(heat.sum()) + dwdt) / float(power.sum()),
                    "Pe_W": float(pbe.sum()), "Pi_W": float(pbi.sum()), "Pth_W": float(pbth.sum()),
                    "Pe_fraction": float(pbe.sum() / heat.sum()), "I_nbi_A": float(cur.sum()),
                    "W_fast_profile_J": float(np.sum(nb * (eperp + epll) * 1e3 * QE * dvol)),
                    "birth_centroid_psin": centroid(sbedep), "birth_half_psin": half(sbedep),
                    "heat_half_psin": half(heat), "current_centroid_psin": centroid(cur),
                    "volume_m3": float(vol[-1])}}


def nubeam_equilibrium(nbm) -> dict:
    a = nbm["a"]
    x = np.linspace(0.0, 1.0, 41)
    sj, sb = float(_nc(a, "kccw_Jphi")), float(_nc(a, "kccw_Bphi"))
    return {"time_slice": {
        "global_quantities": {"psi_axis": 0.0, "psi_boundary": float(_nc(a, "psipol")[-1]), "ip": sj * float(_nc(a, "curt")[-1]),
                              "magnetic_axis": {"r": float(_nc(a, "R_axis")), "z": float(_nc(a, "Z_axis"))}},
        "profiles_1d": {"psi_norm": x, "q": np.interp(x, nbm["psin_b"], np.abs(_nc(a, "q_eq"))),
                        "f": sb * np.interp(x, nbm["psin_b"], _nc(a, "g_eq"))},
        "profiles_2d": {"grid": {"dim1": _nc(a, "R_grid"), "dim2": _nc(a, "Z_grid")}, "psi": _nc(a, "PsiRZ").T},
        "boundary": {"outline": {"r": _nc(a, "R_geo")[:, -1], "z": _nc(a, "Z_geo")[:, -1]}}},
        "vacuum_toroidal_field": {"r0": float(_nc(a, "R_axis")), "b0": sb * float(_nc(a, "B_axis_vac"))},
        "fylite:limiter": {"r": _nc(a, "rlim"), "z": _nc(a, "zlim")}}


def nubeam_profiles(nbm) -> dict:
    a = nbm["a"]
    x = np.concatenate(([0.0], nbm["psin_c"], [1.0]))
    ne, te, zeff = _nc(a, "ns")[0], _nc(a, "Ts")[0] * 1e3, _nc(a, "Zeff")
    return {"profiles_1d": {"grid": {"psi_norm": x},
                            "electrons": {"density": np.concatenate(([ne[0]], ne, [_nc(a, "ns_bdy")[0]])),
                                          "temperature": np.concatenate(([te[0]], te, [float(_nc(a, "Te_bdy")) * 1e3]))},
                            "zeff": np.concatenate(([zeff[0]], zeff, [zeff[-1]]))}}


def nubeam_units(nbm, n_w: int = 5) -> tuple[list, list]:
    """NUBEAM's source geometry as `code/beam` beamlets: the tangency radius |sRtcen|, the source height, and the rms
    size AT the tangency point (the source's half-width / sqrt(3) with the 1/e divergence over Lbsctan; vertically the
    source focused at b_Vfocal_length) laid on n_w equal-weight nodes of the same rms.  Aperture clipping is ignored."""
    g = nbm["geo"]
    units, conv = [], []
    node = lambda sig: sig * math.sqrt(3.0 * (n_w - 1) / (n_w + 1))  # noqa: E731
    for i, p in enumerate(nbm["power"]):
        if p <= 0:
            continue
        L = g["Lbsctan"][i]
        sh = math.hypot(g["b_halfwidth"][i] / math.sqrt(3), L * math.tan(math.radians(g["b_Hdivergence"][i])) / math.sqrt(2))
        gh = g["b_halfHeight"][i] * abs(1.0 - L / g["b_Vfocal_length"][i])
        sv = math.hypot(gh / math.sqrt(3), L * math.tan(math.radians(g["b_Vdivergence"][i])) / math.sqrt(2))
        units.append({"name": f"B_{i + 1:03d}", "energy": {"data": 1e3 * float(nbm["kv"][i])}, "power_launched": {"data": float(p)},
                      "beam_power_fraction": {"data": nbm["pfrac"][i]}, "species": {"a": 2.0, "z_n": 1.0},
                      #: co-current: kccw_Jphi = -1 and sRtcen < 0 are the same sense, and NUBEAM's curbeam is > 0
                      "beamlets_group": [{"tangency_radius": abs(float(g["sRtcen"][i])), "position": {"z": float(g["Zbsc"][i])},
                                          "direction": 1.0, "width_horizontal": node(sh), "width_vertical": node(sv)}]})
        conv.append({"beam": i + 1, "rtan_m": abs(float(g["sRtcen"][i])), "sigma_h_m": sh, "sigma_v_m": sv})
    return units, conv


def nbi_transient(nbm, rec, c, e) -> dict:
    """fylite's OWN ingredients (retained deposition per component and shell, E_c, tau_s) marched as a time-dependent
    Stix slowing-down with NUBEAM's source history (INIT, then two 10 ms steps) — so the 20 ms answers can be read side
    by side.  ★A reconstruction for READING, not a fylite model: no transport, no pitch scattering."""
    fld = lambda k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    ns = len(c)
    ret = fld("component_retained").reshape(-1, ns)
    cpw, cen, ec, ts = fld("component_power"), fld("component_energy"), fld("e_crit"), fld("tau_s")
    ti = np.interp(c, nbm["psin_c"], _nc(nbm["a"], "Ts")[1] * 1e3)
    s1, t_mid, t_end, dtau = nbm["source_weight_step1"], 0.010, 0.020, 2e-5
    tg = np.arange(0.0, t_end + 1e-12, dtau)
    t2 = tg[(tg >= t_mid)][::25]
    pe = pi = w20 = 0.0
    for ci in range(len(cpw)):
        E0 = cen[ci]
        for k in range(ns):
            sp = cpw[ci] * ret[ci, k]
            eth = max(1.5 * ti[k], 1.0)
            if sp <= 0 or E0 <= eth:
                continue
            sn = sp / (E0 * QE)
            a15, c15 = E0 ** 1.5, ec[k] ** 1.5
            tth = ts[k] / 3.0 * math.log((a15 + c15) / (eth ** 1.5 + c15))
            tau = np.arange(0.0, tth, dtau)
            E = np.maximum((a15 + c15) * np.exp(-3.0 * tau / ts[k]) - c15, 0.0) ** (2.0 / 3.0)
            pe_tau = 2.0 * E / ts[k] * sn * QE
            pi_tau = pe_tau * (ec[k] / np.maximum(E, 1e-9)) ** 1.5

            def at(t, prof):
                m = tau <= t
                return float(np.sum(np.where(t - tau[m] < t_mid, s1, 1.0) * prof[m]) * dtau)
            pe += np.mean([at(t, pe_tau) for t in t2])
            pi += np.mean([at(t, pi_tau) for t in t2])
            w20 += at(t_end, sn * E * QE)
    return {"Pe_W_step2": pe, "Pi_W_step2": pi, "W_fast_J_20ms": w20, "source_weight_step1": s1}


def nbi() -> dict:
    nbm = nubeam()
    eq, cp = nubeam_equilibrium(nbm), nubeam_profiles(nbm)
    units, conv = nubeam_units(nbm)

    def run(**settings):
        st = {"n_shells": 40.0, "n_width_r": 5.0, "n_width_z": 5.0, "n_samples": 1201.0, **settings}
        rec = complete("code/beam", {"settings": st, "inputs": {"equilibrium": eq, "core_profiles": cp, "nbi": {"unit": units}}})
        f = facts(rec)
        e = field(rec, "psin_edges")
        c = 0.5 * (e[1:] + e[:-1])
        comp = field(rec, "component_absorbed").reshape(-1, len(c))
        birth = np.sum(comp * (field(rec, "component_power") / (field(rec, "component_energy") * QE))[:, None], 0)
        src = rec["fields"]["core_sources"]["source"]["0"]["profiles_1d"]
        dv = field(rec, "dvolume")
        Pe = np.asarray(src["electrons"]["energy"]["data"], float) * dv
        Pi = np.asarray(src["total_ion_energy"]["data"], float) * dv
        cb = np.concatenate(([0.0], np.cumsum(birth))) / birth.sum()
        return rec, c, e, {"p_absorbed_W": f["p_absorbed"], "loss_fraction": f["shinethrough"] + f["orbit_loss_fraction"],
                           "birth_rate": float(birth.sum()), "birth_centroid_psin": float(np.sum(c * birth) / birth.sum()),
                           "birth_half_psin": float(np.interp(0.5, cb, e)), "Pe_fraction_steady": float(Pe.sum() / (Pe + Pi).sum()),
                           "I_nbi_steady_A": f["i_nbi"], "W_fast_steady_J": f["fast_energy"], "volume_m3": float(dv.sum())}
    rec, c, e, base = run(stopping_model="janev")
    tr = nbi_transient(nbm, rec, c, e)
    _, _, _, metis = run(stopping_model="metis")
    nC = _nc(nbm["a"], "ns")[3]
    nC_avg = float(np.sum(nC * nbm["dvol"]) / nbm["dvol"].sum())
    _, _, _, carbon = run(stopping_model="janev", z_imp=6.0, n_imp=nC_avg)
    nb = nbm["out"]
    return {"what": "NBI：code/beam 对 NUBEAM（TRANSP nubeam_comp_exec 的 DIII-D 测试例，D3D 118419 t = 3.995 s；只读数据）",
            "reference": {"code": "NUBEAM", "dir": NUBEAM_DIR, "note": "INIT + 2 × 10 ms: a transient, not a steady state"},
            "nubeam": nb, "geometry": conv,
            "fylite": {"janev": base, "metis": metis, "janev_carbon": {**carbon, "n_carbon_vol_avg": nC_avg}, "transient_janev": tr},
            "compare": {"birth_rate_rel": base["birth_rate"] / nb["birth_rate_lower_bound"] - 1.0,
                        "birth_centroid_dpsin": base["birth_centroid_psin"] - nb["birth_centroid_psin"],
                        "loss_fraction_d": base["loss_fraction"] - nb["loss_fraction_est"],
                        "volume_rel": base["volume_m3"] / nb["volume_m3"] - 1.0,
                        "W_fast_20ms_rel": tr["W_fast_J_20ms"] / nb["W_fast_profile_J"] - 1.0,
                        "Pe_20ms_rel": tr["Pe_W_step2"] / nb["Pe_W"] - 1.0,
                        "Pi_plus_th_20ms_rel": tr["Pi_W_step2"] / (nb["Pi_W"] + nb["Pth_W"]) - 1.0}}


# --- LH against GENRAY ----------------------------------------------------------------------------------------------

GENRAY_NC = "boray/eqdata/genray/EAST/lhw/east_lh_multiray.nc"
GENRAY_G = "boray/eqdata/genray/EAST/g071230.004800"
ME_C2_EV = 510998.95


def _moments(x, w) -> dict:
    w = np.clip(np.asarray(w, float), 0.0, None)
    c = float(np.sum(w * x) / np.sum(w))
    return {"centroid": c, "std": float(math.sqrt(np.sum(w * (x - c) ** 2) / np.sum(w)))}


def lh() -> dict:
    import netCDF4
    from fylite import fyo
    from fylite.io import geqdsk
    d = netCDF4.Dataset(THIRD / GENRAY_NC)
    v = lambda k: np.asarray(d[k][:], float)  # noqa: E731
    pf = float(v("psifactr"))
    #: ★indexrho = 4: rho = sqrt(psi_N / psifactr) — checked against the g-file at every ray point (2.5e-6)
    psin_c, psin_b = pf * v("rho_bin_center") ** 2, pf * v("rho_bin") ** 2
    spower, jpar, area = 1e-7 * v("spower"), 1e4 * v("s_cur_den_parallel"), 1e-4 * v("binarea")
    ne, te = 1e6 * v("densprof")[0], 1e3 * v("temprof")[0]
    p_inj, i_par = 1e-7 * float(v("power_inj_total")), float(v("parallel_cur_total"))
    n0 = float(np.mean([v("wnpar")[i, 0] for i in range(len(v("nrayelt")))]))
    gp = _moments(psin_c, spower)
    gj = _moments(psin_c, np.abs(jpar) * area)
    #: along GENRAY's own rays: the N∥ each watt is absorbed at, and v_ph / sqrt(2 T_e / m_e) there — the two numbers
    #: fylite's model takes as settings (the upshift and xi)
    dP, npar, tea = [], [], []
    for i, k in enumerate(v("nrayelt").astype(int)):
        P = 1e-7 * v("delpwr")[i, :k]
        dP.append(-np.diff(P))
        npar.append(0.5 * (v("wnpar")[i, 1:k] + v("wnpar")[i, :k - 1]))
        tea.append(1e3 * 0.5 * (v("ste")[i, 1:k] + v("ste")[i, :k - 1]))
    dP, npar, tea = map(np.concatenate, (dP, npar, tea))

    def q(val, p):
        o = np.argsort(val)
        return float(np.interp(p, np.cumsum(dP[o]) / dP.sum(), val[o]))
    xi_eff = np.sqrt(ME_C2_EV / (2.0 * tea)) / npar
    up = [q(npar, p) / n0 for p in (0.1, 0.5, 0.9)]
    doc = fyo.equilibrium(geqdsk.read_geqdsk(THIRD / GENRAY_G))
    x = np.append(psin_b, 1.0)
    cp = {"profiles_1d": {"grid": {"psi_norm": x}, "electrons": {"density": np.append(ne, ne[-1]), "temperature": np.append(te, te[-1])}}}

    def run(upshift=(1.0, 1.0), xi=3.0):
        rec = complete("code/wave", {"settings": {"eta_cd": 1.0e19, "upshift_min": upshift[0], "upshift_max": upshift[1],
                                                  "xi": xi, "n_shells": 50.0},
                                     "inputs": {"equilibrium": doc, "core_profiles": cp,
                                                "lh_antennas": {"antenna": [{"name": "EAST-LH-2.45", "frequency": float(v("freqcy")),
                                                                             "power_launched": {"data": p_inj}, "power_reflected": {"data": 0.0},
                                                                             "fylite:n_parallel_min": n0, "fylite:n_parallel_max": n0}]}}})
        f = facts(rec)
        e = field(rec, "psin_edges")
        c = 0.5 * (e[1:] + e[:-1])
        src = rec["fields"]["core_sources"]["source"]["0"]["profiles_1d"]
        pw = np.asarray(src["electrons"]["energy"]["data"], float) * field(rec, "dvolume")
        m = _moments(c, pw)
        return {"deposited": f["deposited"], "p_deposited_W": f["p_deposited"], "i_lh_A": f["i_lh"], "ne_bar": f["ne_bar"],
                "r0": f["r0"], "centroid_psin": m["centroid"], "std_psin": m["std"],
                "d_centroid_psin": m["centroid"] - gp["centroid"], "std_ratio": m["std"] / gp["std"],
                "deposited_rel": abs(f["p_deposited"] / p_inj - 1.0), "volume_m3": float(field(rec, "dvolume").sum())}
    default = run()
    upshifted = run(upshift=(up[0], up[2]))
    return {"what": "LH：code/wave 对 GENRAY v10.13（EAST #71230 4.8 s，2.45 GHz 四条射线；BORAY 仓的数据，BSD-3）",
            "reference": {"code": "GENRAY", "nc": GENRAY_NC, "gfile": GENRAY_G, "n_parallel_launch": n0,
                          "frequency_Hz": float(v("freqcy")), "psifactr": pf, "te0_eV": float(te[0]), "ne0_m3": float(ne[0])},
            "genray": {"p_injected_W": p_inj, "p_absorbed_W": 1e-7 * float(v("power_total")), "i_par_A": i_par,
                       "power_centroid_psin": gp["centroid"], "power_std_psin": gp["std"], "current_centroid_psin": gj["centroid"],
                       "upshift_q10_q50_q90": up, "xi_eff_q10_q50_q90": [q(xi_eff, p) for p in (0.1, 0.5, 0.9)],
                       "volume_m3": 1e-6 * float(v("voltot"))},
            "fylite": {"default": default, "genray_upshift": upshifted,
                       "eta_cd_implied_by_genray": abs(i_par) * default["ne_bar"] * default["r0"] / p_inj}}


def write(name: str, d: dict) -> None:
    (READINGS / name).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("closure")
    sub.add_parser("toray")
    for name in ("icrh", "nbi", "lh"):
        sub.add_parser(name)
    k = sub.add_parser("kernel")
    k.add_argument("log", type=Path, help="output of the kernel's `cargo test -- --nocapture` on the HCD tests")
    a = ap.parse_args()
    if a.cmd == "closure":
        write("hcd_power_closure.json", closure())
    elif a.cmd == "toray":
        write("ec_toray_cfedr20ma.json", toray())
    elif a.cmd == "icrh":
        write("icrh_metis_door.json", icrh())
    elif a.cmd == "nbi":
        write("nbi_nubeam_d3d.json", nbi())
    elif a.cmd == "lh":
        write("lh_genray_east71230.json", lh())
    else:
        write("hcd_metis_kernel.json", kernel_readings(a.log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
