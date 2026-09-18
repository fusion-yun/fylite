"""Write the CFEDR d2025 1.5-D reproduction as an IMAS data entry (HDF5 backend, DD 4.1.1).

IDSs (occurrence 0):
  equilibrium   free-boundary solves along the replay (code/discharge + C4) — as write_imas.py
  pf_active     the card's PF coils and the solved coil currents — as write_imas.py
  core_profiles 1.5-D transport (code/evolve through fylite.engine.pcs_replay): T_e, T_i, n_e at every window end
                on the march's own rho_tor ladder, stitched at T_SPLIT (ramp-up run below, flat-top run from it)
  summary       the replay's 10 ms rows (ramps) / 1 s rows (flat top): Ip command, P_aux, line-averaged n_e
                command, P_fus, W_th (kernel per-step trace), axis T_e / T_i, beta_N, P_rad, v_loop
Flux convention: the kernel's full-turn flux [Wb], COCOS 17.

Usage: python write_imas15.py EQ_DIR DEVICE.json RAMPUP.csv FLAT.csv RHO_SNAPSHOT.json T_SPLIT OUT_DIR
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import imas
import numpy as np


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return math.nan
    return v


def main():
    eq_dir, dev_path, ramp_csv, flat_csv, snap_path = (Path(a) for a in sys.argv[1:6])
    t_split = float(sys.argv[6])
    out_dir = Path(sys.argv[7])
    out_dir.mkdir(parents=True, exist_ok=True)
    index = [e for e in json.load(open(eq_dir / "index.json")) if e.get("ok")]
    dev = json.load(open(dev_path))
    coils = [c for c in dev["pf_active"]["coil"]
             if not any((f or {}).get("name") == "b_field_fb" for f in (c.get("function") or []))]
    rows = [r for r in csv.DictReader(open(ramp_csv)) if float(r["t"]) < t_split - 1e-9] + \
           [r for r in csv.DictReader(open(flat_csv)) if float(r["t"]) >= t_split - 1e-9]
    profs = [p for p in map(json.loads, open(str(ramp_csv) + ".profiles.jsonl")) if p["t"] < t_split - 1e-9] + \
            [p for p in map(json.loads, open(str(flat_csv) + ".profiles.jsonl")) if p["t"] >= t_split - 1e-9]
    snap = json.loads(snap_path.read_text())
    rho_tor = np.asarray(snap["prev"]["fields"]["core_profiles"]["profiles_1d"]["grid"]["rho_tor"]["data"], float)

    uri = f"imas:hdf5?path={out_dir}"
    with imas.DBEntry(uri, "w", dd_version="4.1.1") as db:
        f = db.factory

        # ---- equilibrium ------------------------------------------------------------------
        eq = f.equilibrium()
        eq.ids_properties.homogeneous_time = 1
        eq.ids_properties.comment = ("CFEDR d2025 replay: free-boundary equilibria by fylite code/discharge, "
                                     "position control C4, card coil ratings; full-turn flux [Wb], COCOS 17")
        eq.code.name = "fylite code/discharge"
        eq.time = np.array([e["t"] for e in index], float)
        eq.vacuum_toroidal_field.r0 = 7.8
        eq.vacuum_toroidal_field.b0 = np.full(len(index), 6.3)
        eq.time_slice.resize(len(index))
        coil_currents = []
        for i, e in enumerate(index):
            d = np.load(eq_dir / f"eq_{e['t']:08.2f}.npz")
            fc = e["facts"]
            ts = eq.time_slice[i]
            ts.time = e["t"]
            ts.global_quantities.ip = e["ip"]
            ts.global_quantities.psi_axis = fc["psi_axis"]
            ts.global_quantities.psi_boundary = fc["psi_bnd"]
            ts.global_quantities.magnetic_axis.r = fc["axis_r"]
            ts.global_quantities.magnetic_axis.z = fc["axis_z"]
            ts.boundary.type = int(fc["bnd_kind"])
            ts.boundary.outline.r = d["bnd_r"]
            ts.boundary.outline.z = d["bnd_z"]
            ts.boundary.geometric_axis.r = fc["shape_r0"]
            ts.boundary.geometric_axis.z = fc["shape_z0"]
            ts.boundary.minor_radius = fc["shape_a"]
            ts.boundary.elongation = fc["shape_kappa"]
            ts.boundary.triangularity_upper = fc["shape_delta_upper"]
            ts.boundary.triangularity_lower = fc["shape_delta_lower"]
            #: DD 4.1.1 keeps critical points in contour_tree.node (1 saddle · 2 maximum)
            crit = [(2, fc["axis_r"], fc["axis_z"], fc["psi_axis"])]
            if int(fc["bnd_kind"]) == 1 and np.isfinite(fc.get("xpt_r", np.nan)):
                crit.append((1, fc["xpt_r"], fc["xpt_z"], fc["psi_bnd"]))
            ts.contour_tree.node.resize(len(crit))
            for j, (kind, cr, cz, cpsi) in enumerate(crit):
                node = ts.contour_tree.node[j]
                node.critical_type = kind
                node.r = cr
                node.z = cz
                node.psi = cpsi
            ts.profiles_2d.resize(1)
            p2 = ts.profiles_2d[0]
            p2.grid_type.index = 1
            p2.grid_type.name = "rectangular"
            p2.grid.dim1 = d["r"]
            p2.grid.dim2 = d["z"]
            p2.psi = d["psi"]
            coil_currents.append(d["aturns"])
        db.put(eq)

        # ---- pf_active ------------------------------------------------------------------------
        pf = f.pf_active()
        pf.ids_properties.homogeneous_time = 1
        pf.ids_properties.comment = "CFEDR card PF coils; current per turn = solved channel A·turns / coil turns"
        pf.time = eq.time
        pf.coil.resize(len(coils))
        at = np.array(coil_currents)
        for k, c in enumerate(coils):
            pc = pf.coil[k]
            pc.name = c.get("name", "")
            turns = sum(abs(float(el.get("turns_with_sign", 1.0))) for el in c.get("element", [])) or 1.0
            pc.element.resize(len(c.get("element", [])))
            for j, el in enumerate(c.get("element", [])):
                rect = el["geometry"]["rectangle"]
                pe = pc.element[j]
                pe.turns_with_sign = float(el.get("turns_with_sign", 1.0))
                pe.geometry.geometry_type = 2
                pe.geometry.rectangle.r = float(rect["r"])
                pe.geometry.rectangle.z = float(rect["z"])
                pe.geometry.rectangle.width = float(rect["width"])
                pe.geometry.rectangle.height = float(rect["height"])
            if k < at.shape[1]:
                pc.current.data = at[:, k] / turns
        db.put(pf)

        # ---- core_profiles (1.5-D, window ends) -----------------------------------------------------
        cp = f.core_profiles()
        cp.ids_properties.homogeneous_time = 1
        cp.ids_properties.comment = (
            f"fylite 1.5-D transport (code/evolve via fylite.engine.pcs_replay, adaptive windows, ledger I-20/I-21); "
            f"profiles at window ends; ramp-up run (0-D start state on the CASE-20 case) below {t_split:g} s, "
            f"calibrated CASE-20 fuelled case from {t_split:g} s — the state is discontinuous at the stitch")
        cp.code.name = "fylite engine.pcs_replay + code/evolve"
        tp = np.array([p["t"] for p in profs], float)
        cp.time = tp
        rho_n = rho_tor / rho_tor[-1]
        cp.profiles_1d.resize(len(profs))
        for i, p in enumerate(profs):
            q = cp.profiles_1d[i]
            q.time = p["t"]
            q.grid.rho_tor_norm = rho_n
            q.grid.rho_tor = rho_tor
            q.electrons.temperature = np.asarray(p["te"], float)
            q.electrons.density = np.asarray(p["ne"], float)
            q.t_i_average = np.asarray(p["ti"], float)
        db.put(cp)

        # ---- summary (10 ms / 1 s rows) -------------------------------------------------------------
        col = lambda k: np.array([num(r.get(k)) for r in rows], float)  # noqa: E731
        sm = f.summary()
        sm.ids_properties.homogeneous_time = 1
        sm.ids_properties.comment = (
            f"fylite replay rows: 10 ms in the ramps, 1 s on the flat top (interpolated flag in the CSV); stitched at "
            f"{t_split:g} s; W_th from the kernel's per-step trace; P_fus = alpha power / (3.518/17.589)")
        sm.code.name = "fylite engine.pcs_replay + code/evolve"
        sm.time = col("t")
        sm.global_quantities.ip.value = col("ip_cmd")
        sm.global_quantities.energy_thermal.value = col("w_th")
        sm.global_quantities.beta_tor_norm.value = col("beta_n")
        sm.global_quantities.power_radiated.value = col("p_rad")
        sm.global_quantities.v_loop.value = col("v_loop")
        sm.fusion.power.value = col("p_fus")
        sm.heating_current_drive.power_additional.value = col("rf_cmd")
        sm.local.magnetic_axis.t_e.value = col("te0")
        sm.local.magnetic_axis.t_i_average.value = col("ti0")
        sm.line_average.n_e.value = col("ne_bar_cmd")
        db.put(sm)
    print(f"written {uri}: equilibrium {len(index)} · pf_active {len(coils)} coils · core_profiles {len(profs)} "
          f"· summary {len(rows)} rows ({rows[0]['t']} → {rows[-1]['t']} s)")


if __name__ == "__main__":
    main()
