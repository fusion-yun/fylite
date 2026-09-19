"""Heating and current drive (FR-TR-004 · NR-TR-001): the readings of the `tr-sources` records.

Three subcommands, each writing one reading into ``docs/benchmark/readings``:

``closure``  — every family's power account, through the tree doors: `code/beam` (NBI: P_inj = P_abs + P_shine +
               P_orbit, and the deposited profile's volume integral = P_abs), `code/wave` (LH: the deposited profile's
               volume integral = P_deposited, launched − reflected = absorbed) on EAST #137985 t = 4.041 s (CASE-23), and
               `code/rf_ray` (EC: launched = absorbed + left + not traced, the shells = absorbed) on CFEDR 20 MA.
``toray``    — `code/rf_ray` against TORAY-GA's own answer on CFEDR 20 MA (fydoc CASE-21, frozen by the kernel's
               `rust/tools/gen_cfedr_toray_reference.py`): the branch, the ray on matched flux surfaces, N∥, the
               deposition peak and the driven current per watt.  ★Clean room: TORAY's DATA, never its source.
``kernel``   — the kernel's METIS comparisons (ICRH, ECCD) and the ICRH profile closure: their `[register]` lines,
               parsed from ``cargo test -- --nocapture`` (ICRH has no `code/` door; these gates live in the kernel).

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


def write(name: str, d: dict) -> None:
    (READINGS / name).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", name)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("closure")
    sub.add_parser("toray")
    k = sub.add_parser("kernel")
    k.add_argument("log", type=Path, help="output of the kernel's `cargo test -- --nocapture` on the HCD tests")
    a = ap.parse_args()
    if a.cmd == "closure":
        write("hcd_power_closure.json", closure())
    elif a.cmd == "toray":
        write("ec_toray_cfedr20ma.json", toray())
    else:
        write("hcd_metis_kernel.json", kernel_readings(a.log))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
