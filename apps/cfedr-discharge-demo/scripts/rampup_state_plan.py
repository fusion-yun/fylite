"""Ramp-up start case with a CURRENT-CONSISTENT flux and the I_p loop on (goal: 补全 1.5-D 放电演化).

The first ramp-up case (rampup_plan.py) started the march on the CASE-20 flat-top g-file flux: its current
profile encloses 15 MA while the command is 0.25 MA, so q95 read 5.6 and l_i(3) ~2400 at t = 1 s, and with the
I_p loop off the boundary loop voltage sat at 0.02 V — no Ohmic heating on the ramp.  This writes a case that
binds the start state EXACTLY (`state = 1`) on the march's own 52-surface ladder:

* T_e / T_i / n_e — the ramp-up case's own start (the 0-D profiles, read back from a zero-step call);
* psi — the flat-top flux about its axis value, scaled by I_p(start) / I_p(flat top), so the enclosed current
  is the commanded one (the shape — hence l_i — is still the flat-top one [approximation]);
* `ipctl = 1` with gains `ip_kp` / `ip_ki`: the loop drives the boundary loop voltage to follow the command.

Usage: python rampup_state_plan.py RAMPUP_PLAN.json OUT.json [IP_KP] [IP_KI] [IP_FLAT_A]
"""
from __future__ import annotations

import json
import sys

import numpy as np

from fylite.io import fydoc


def main():
    src, out = sys.argv[1], sys.argv[2]
    kp = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    ki = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    ip_flat = float(sys.argv[5]) if len(sys.argv) > 5 else 15.0e6
    plan = json.load(open(src))
    st = dict(plan["settings"], nsteps=1.0, dttarget=0.0, globals=1.0, t_stop=float(plan["settings"]["t_start"]) + 1e-9)
    rec = fydoc.complete("code/evolve", {"settings": st, "inputs": plan["inputs"]})
    F = rec["fields"]
    cp = F["core_profiles"]["profiles_1d"]
    psi = np.asarray(F["psi"]["data"], float)
    ip0 = float(plan["settings"]["ip"]) * 1e3  # the case's `ip` is in kA
    #: ★the loop calibrates its ratio on the FIRST call, against that call's target — the first window's END
    #: command, not the start's.  Scaling the flux to that target leaves only the ladder bias in the ratio.
    ip_cal = float(sys.argv[6]) if len(sys.argv) > 6 else ip0
    f = ip_cal / ip_flat
    psi_s = psi[0] + (psi - psi[0]) * f
    prof = {
        "grid": {"rho_tor": cp["grid"]["rho_tor"]["data"], "psi": psi_s.tolist()},
        "electrons": {"temperature": cp["electrons"]["temperature"]["data"],
                      "density": cp["electrons"]["density"]["data"]},
        "t_i_average": cp["t_i_average"]["data"],
    }
    if "fylite:ion_density" in cp:
        prof["fylite:ion_density"] = cp["fylite:ion_density"]["data"]
    inputs = dict(plan["inputs"], core_profiles={"profiles_1d": prof})
    settings = dict(plan["settings"], state=1.0, ipctl=1.0, ip_kp=kp, ip_ki=ki)
    json.dump({"settings": settings, "inputs": inputs}, open(out, "w"))
    print(f"{out}: psi scaled by {f:.4g} (I_p {ip0 / 1e6:.3g} MA of {ip_flat / 1e6:.3g}) · ladder {len(psi)} · "
          f"ipctl kp {kp:g} ki {ki:g} · Te0 {prof['electrons']['temperature'][0]:.0f} eV")


if __name__ == "__main__":
    main()
