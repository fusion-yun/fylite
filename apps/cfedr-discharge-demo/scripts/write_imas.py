"""Write the CFEDR d2025 discharge modelling output as an IMAS data entry (HDF5 backend, DD 4.1.1).

IDSs (occurrence 0 unless noted):
  equilibrium   free-boundary solves along the replay (code/discharge + C4): psi(R,Z), LCFS, X point,
                axis, ψ_axis / ψ_boundary, Ip, shape (geometric axis, minor radius, elongation, triangularities)
  pf_active     the card's 15 PF coils (rectangles, turns) and the solved coil currents per equilibrium time
  core_profiles 0-D whole-discharge tier (code/zerod, parametric profiles): T_e, T_i, n_e on rho_tor_norm
  summary       0-D traces (Ip, v_loop, W_th, beta_N, P_fus, neutron power, Q, P_aux, axis T_e / n_e)
  summary #1    1.5-D session window on the CASE-20 case (P_fus, W_th, axis T_e), when the CSV is given
  dataset_description  provenance
Flux convention: the kernel's full-turn flux [Wb], COCOS 17 (as the kernel's own equilibrium document).

Usage: python write_imas.py EQ_DIR ZEROD.npz DEVICE.json OUT_DIR [SESSION.csv]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import imas
import numpy as np


def main():
    eq_dir, zerod_path, dev_path, out_dir = (Path(a) for a in sys.argv[1:5])
    session_csv = Path(sys.argv[5]) if len(sys.argv) > 5 else None
    out_dir.mkdir(parents=True, exist_ok=True)
    index = [e for e in json.load(open(eq_dir / "index.json")) if e.get("ok")]
    z = np.load(zerod_path, allow_pickle=False)
    dev = json.load(open(dev_path))
    coils = [c for c in dev["pf_active"]["coil"]
             if not any((f or {}).get("name") == "b_field_fb" for f in (c.get("function") or []))]

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
            #: DD 4.1.1 keeps critical points in contour_tree.node (0 minimum · 1 saddle · 2 maximum):
            #: the axis is the kernel flux's maximum; the X point, when it bounds the plasma, a saddle at ψ_b
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
        at = np.array(coil_currents)  # (nt, n_ch) A·turns, channel order = card coil order
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

        # ---- core_profiles (0-D tier) -----------------------------------------------------------
        cp = f.core_profiles()
        cp.ids_properties.homogeneous_time = 1
        cp.ids_properties.comment = ("fylite code/zerod, prescribed tier driven by the predicted axis T_e "
                                     "(IPB98(y,2) tier B) and the replay's Ip / density / auxiliary power; "
                                     "parametric profile shapes — not a transport solution")
        cp.code.name = "fylite code/zerod"
        t0 = z["core_profiles__time"]
        cp.time = t0
        cp.global_quantities.ip = z["ip_cmd"]
        rho = z["core_profiles__profiles_1d__grid__rho_tor_norm"]
        te = z["core_profiles__profiles_1d__electrons__temperature"]
        ne = z["core_profiles__profiles_1d__electrons__density"]
        ti = z["core_profiles__profiles_1d__t_i_average"]
        cp.profiles_1d.resize(len(t0))
        for i in range(len(t0)):
            p = cp.profiles_1d[i]
            p.time = t0[i]
            p.grid.rho_tor_norm = rho[i]
            p.electrons.temperature = te[i]
            p.electrons.density = ne[i]
            p.t_i_average = ti[i]
        db.put(cp)

        # ---- summary (0-D traces) ------------------------------------------------------------------
        sm = f.summary()
        sm.ids_properties.homogeneous_time = 1
        sm.ids_properties.comment = "fylite code/zerod traces over the CFEDR d2025 replay"
        sm.code.name = "fylite code/zerod"
        sm.time = z["summary__time"]
        sm.global_quantities.ip.value = z["summary__global_quantities__ip__value"]
        sm.global_quantities.v_loop.value = z["summary__global_quantities__v_loop__value"]
        sm.global_quantities.fusion_gain.value = z["summary__global_quantities__fusion_gain__value"]
        sm.global_quantities.energy_thermal.value = z["criteria_w_th"]
        sm.global_quantities.beta_tor_norm.value = z["criteria_beta_n"]
        sm.global_quantities.beta_pol.value = z["criteria_beta_p"]
        #: total fusion power from the door's own `p_fus` — its summary/fusion/power row carries the alpha
        #: power (≈ p_fus / 4.97 measured, equal to prediction_p_alpha), not the DD's fusion power
        sm.fusion.power.value = z["p_fus"]
        sm.fusion.neutron_power_total.value = z["summary__fusion__neutron_power_total__value"]
        sm.heating_current_drive.power_additional.value = z["summary__heating_current_drive__power_additional__value"]
        sm.local.magnetic_axis.t_e.value = z["summary__local__magnetic_axis__t_e__value"]
        sm.local.magnetic_axis.n_e.value = z["summary__local__magnetic_axis__n_e__value"]
        sm.line_average.n_e.value = z["criteria_ne_bar"]
        db.put(sm)

        # ---- summary #1 (1.5-D session window) ------------------------------------------------------------
        if session_csv is not None and session_csv.exists():
            rows = [r for r in csv.DictReader(open(session_csv)) if r["rejected"] != "True"]
            s1 = f.summary()
            s1.ids_properties.homogeneous_time = 1
            s1.ids_properties.comment = ("fylite 1.5-D session (code/evolve per 10 ms, CASE-20 case, I-9 fuelling, "
                                         "L-H martin08) on the replay's burn window")
            s1.code.name = "fylite engine.session + code/evolve"
            s1.time = np.array([float(r["t"]) for r in rows])
            s1.global_quantities.ip.value = np.array([float(r["ip_cmd"]) for r in rows])
            s1.fusion.power.value = np.array([float(r["p_fus"]) for r in rows])
            s1.global_quantities.energy_thermal.value = np.array([float(r["w_th"]) for r in rows])
            s1.local.magnetic_axis.t_e.value = np.array([float(r["te0"]) for r in rows])
            s1.heating_current_drive.power_additional.value = np.array([float(r["rf_cmd"]) for r in rows])
            db.put(s1, 1)

        #: DD 4.1.1 has no dataset_description IDS: the entry's provenance rides each IDS's
        #: ids_properties.comment above (CFEDR d2025 replay DRAFT v0.1, ramp-down nodes synthetic,
        #: a modelled discharge, not a design-authority result)
    print(f"written {uri}: equilibrium {len(index)} slices · pf_active {len(coils)} coils · "
          f"core_profiles {len(t0)} · summary {len(z['summary__time'])}"
          + (" · summary#1 session" if session_csv is not None and session_csv.exists() else ""))


if __name__ == "__main__":
    main()
