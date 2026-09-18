"""Build a ramp-up start case document for the CFEDR discharge reproduction (goal: 重现放电过程).

Start at T0 from the calibrated 0-D whole-discharge run (code/zerod, zerod_cal.npz): its T_e / T_i / n_e
profiles at T0 mapped onto the CASE-20 case's own reference rho grid by normalised radius, the axis and
edge values from them, Ip from the replay.  ★The geometry stays the CASE-20 flat-top g-file (the analytic
Miller tier would need the RF tables and the given chi re-gridded onto its ladder); li / q / bootstrap
at low Ip are therefore DEGRADED — the evolving shape is carried by the free-boundary equilibrium
sequence instead.  Fuelling starts from the case's rate scaled by the replay's density at T0.

Usage: python rampup_plan.py PLAN.json ZEROD.npz REPLAY.json T0 OUT.json
"""
from __future__ import annotations

import json
import sys

import numpy as np


def main():
    plan_path, zerod_path, replay_path, t0, out = sys.argv[1:6]
    t0 = float(t0)
    plan = json.load(open(plan_path))
    z = np.load(zerod_path)
    nodes = json.load(open(replay_path))["nodes"]
    ts = [n["t"] for n in nodes]
    ip = float(np.interp(t0, ts, [n["ip"] for n in nodes]))
    ne_bar = float(np.interp(t0, ts, [n["ne_bar"] for n in nodes]))
    ne_bar_ft = float(np.interp(65.0, ts, [n["ne_bar"] for n in nodes]))
    i = int(np.argmin(abs(z["time"] - t0)))
    rn = z["core_profiles__profiles_1d__grid__rho_tor_norm"][i]
    prof = {k: z[f"core_profiles__profiles_1d__{p}"][i] for k, p in
            (("te", "electrons__temperature"), ("ti", "t_i_average"), ("ne", "electrons__density"))}
    cp = json.loads(json.dumps(plan["inputs"]["core_profiles"]))
    rho = np.asarray(cp["profiles_1d"]["grid"]["rho_tor"], float)
    x = rho / rho[-1]
    te, ti, ne = (np.interp(x, rn, prof[k]) for k in ("te", "ti", "ne"))
    cp["profiles_1d"]["electrons"]["temperature"] = te.tolist()
    cp["profiles_1d"]["electrons"]["density"] = ne.tolist()
    cp["profiles_1d"]["t_i_average"] = ti.tolist()
    st = dict(plan["settings"])
    st.update(ip=ip / 1e3, te0=float(te[0]) / 1e3, ti0=float(ti[0]) / 1e3, ne0=float(ne[0]) / 1e19,
              edgete=float(te[-1]) / 1e3, edgeti=float(ti[-1]) / 1e3, edgene=float(ne[-1]) / 1e19,
              reference=1.0, t_start=t0,
              fuel_rate=float(plan["settings"].get("fuel_rate", 0.0)) * ne_bar / ne_bar_ft)
    out_plan = {"settings": st, "inputs": dict(plan["inputs"], core_profiles=cp)}
    json.dump(out_plan, open(out, "w"))
    print(f"ramp-up start at {t0} s: Ip {ip / 1e6:.2f} MA · Te0 {te[0]:.0f} eV · Ti0 {ti[0]:.0f} eV · ne0 {ne[0]:.3e} · "
          f"edge Te {te[-1]:.0f} eV · fuel {st['fuel_rate']:.3e} /s -> {out}")


if __name__ == "__main__":
    main()
