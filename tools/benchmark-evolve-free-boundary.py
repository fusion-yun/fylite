#!/usr/bin/env python3
"""Free-boundary evolution coupled to the PF circuits and the passive structure, on EAST (register record V-21).

★★2026-09-15 (/goal「完善磁平衡相关计算功能 … pf 导体线圈，导体壁等被动导体耦合」).  `code/evolve_free_boundary` marches
the PF channels (voltage or current drive) and the passive set by implicit Euler on M dI/dt + R I + d(psi_plasma)/dt = V,
the free-boundary equilibrium coupled INSIDE each solve (the circuits answer the plasma's current round by round) with
the boundary cells carrying their fraction of the current.  There is no second code on this page: these are
VERIFICATION readings — identities the march must keep on the real EAST card and a real equilibrium, where the kernel's
unit tests only have a small analytic machine.

* wall decay: no plasma, channels held, the inner shell started in `code/wall`'s slowest mode — it must stay in that
  mode and decay by implicit Euler's factor (1 + dt / tau_1)^-k on `code/wall`'s own tau_1.
* flux freezing: KEFIT's magnetics-only answer at 4.041 s (its coil currents, its p'/FF'), no resistance, no voltage,
  Ip ramped 2 % over three 2 ms steps — the flux every conductor links, M I + psi_plasma, must not move.
* drive reproduction: the same ramp with resistance and a voltage drive; a current-driven march handed that march's
  channel currents must give back its shell currents.
* forward edge rule: `code/forward` on the B-14 slices with the node rule (default) and with `edge_fraction`, against
  KEFIT's map — does the settled floor become a converged answer, and does the comparison move.

Subcommand: ``readings --out DIR``.  Environment: ``$FYDOC_ORACLE``, ``$FYLITE_DEVICE_DIR``, a kernel with
``code/evolve_free_boundary`` (``FYLITE_KERNEL_LIB``).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CASE23 = "FYDOC-CASE-23-east-137985-efit-east"
READINGS = "evolve_free_boundary_east137985.json"
N_CH = 12
#: ★all three passive groups, not the inner shell alone: an implicit step on a vertically unstable plasma needs gamma dt < 1,
#: and with the inner shell alone the rigid gamma is ~709 s^-1 (B-18) — measured 2026-09-15 at 2 ms steps (gamma dt ~ 1.4):
#: the column left its equilibrium in the first step (Z -0.57 m) and a current-driven rerun found the mirrored branch.
#: With the three groups gamma is ~4 s^-1 (B-18), gamma dt ~ 0.01.
PASSIVE = "inner_shell,outer_shell,passive_plates"
RAMP = {"steps": 3, "dt_s": 2e-3, "ip_rise": 0.02}
DRIVE_EXTRA = 0.05


def _tool(module: str, fname: str):
    spec = importlib.util.spec_from_file_location(module, ROOT / "tools" / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def kefit_inputs(bme, g, a) -> tuple[float, np.ndarray, dict]:
    """KEFIT's coil currents, Ip and p'/FF' (table tier, gauge divided out as B-14 does)."""
    ref = bme.kefit_map(g)
    s = ref["gauge_factor"]
    x = np.linspace(0.0, 1.0, len(g["pprime"]))
    eqp = {"time_slice": {"profiles_1d": {"psi_norm": x, "dpressure_dpsi": np.asarray(g["pprime"], float) / s,
                                          "f_df_dpsi": np.asarray(g["ffprim"], float) / s}}}
    return float(ref["ip"]), np.asarray(a["ccbrsp"], float)[:N_CH], eqp


def wall_decay(wv, dev) -> dict:
    facts, f, _ = wv.door("code/wall", {"passive": PASSIVE, "nu": 8, "nv": 8, "responses": 0}, {"device": dev})
    n = int(facts["n_elements"])
    tau, mode = facts["tau_1"], f["modes"].reshape(-1, n)[0]
    nt = 6
    dt = tau / 10.0
    t = np.arange(nt) * dt
    ef, ev, notes = wv.door("code/evolve_free_boundary", {"passive": PASSIVE, "drive": "current"},
                            {"device": dev, "pulse": {"fylite:time": t, "fylite:channel_aturns": np.zeros((nt, N_CH)),
                                                      "fylite:passive_current": mode}})
    cur = ev["currents"].reshape(nt, N_CH + n)[:, N_CH:]
    want = mode[None, :] * (1.0 + dt / tau) ** -np.arange(nt)[:, None]
    return {"tau_1_s": tau, "dt_s": dt, "steps": nt - 1, "elements": n,
            "max_rel_deviation": float(np.max(np.abs(cur - want)) / np.max(np.abs(mode))), "notes": notes}


def march(wv, dev, eqp, ip0: float, cc: np.ndarray, settings: dict, drive: str, volts=None, aturns=None) -> dict:
    nt = RAMP["steps"] + 1
    t = np.arange(nt) * RAMP["dt_s"]
    ip = ip0 * (1.0 + RAMP["ip_rise"] * np.arange(nt) / (nt - 1))
    pulse = {"fylite:time": t, "fylite:ip": ip}
    inputs = {"device": dev, "equilibrium": eqp, "pulse": pulse}
    if drive == "voltage":
        pulse["fylite:channel_volts"] = volts
        inputs["discharge"] = {"fylite:channel_aturns": cc}
    else:
        pulse["fylite:channel_aturns"] = aturns
    t0 = time.time()
    facts, f, notes = wv.door("code/evolve_free_boundary", {"passive": PASSIVE, "drive": drive, **settings}, inputs)
    n = int(facts["n_channels"] + facts["n_passive"])
    return {"facts": facts, "seconds": round(time.time() - t0, 1), "notes": notes, "nt": nt, "n": n,
            "currents": f["currents"].reshape(nt, n), "plasma_flux": f["plasma_flux"].reshape(nt, n),
            "m": f["m"].reshape(n, n), "fields": f}


def track(r: dict) -> dict:
    f = r["fields"]
    keep = ("gs_state", "gs_residual", "picard_iterations", "picard_change", "circuit_residual", "ip", "zc", "axis_r", "axis_z", "fb_amp")
    out = {k: [float(v) for v in f[k]] for k in keep}
    out["passive_max_A"] = [float(v) for v in np.abs(r["currents"][:, N_CH:]).max(axis=1)]
    out["facts"] = r["facts"]
    out["seconds"] = r["seconds"]
    out["notes"] = r["notes"]
    return out


def flux_freezing(wv, dev, eqp, ip0, cc) -> dict:
    r = march(wv, dev, eqp, ip0, cc, {"eta_scale": 0.0}, "voltage", volts=np.zeros((RAMP["steps"] + 1, N_CH)))
    linked = r["currents"] @ r["m"].T + r["plasma_flux"]
    drift = float(np.max(np.abs(linked - linked[0])))
    moved = float(np.max(np.abs(r["plasma_flux"][-1] - r["plasma_flux"][0])))
    return {"linked_flux_drift_Wb": drift, "plasma_flux_moved_Wb": moved, "drift_over_moved": drift / moved, **track(r)}


def channel_resistance(wv, dev, cc) -> np.ndarray:
    """The channels' resistance per turn² [ohm] as the door assembles it (a no-plasma call: M and R only)."""
    _, f, _ = wv.door("code/evolve_free_boundary", {"passive": PASSIVE},
                      {"device": dev, "pulse": {"fylite:time": np.array([0.0, 1e-3]), "fylite:channel_volts": np.zeros((2, N_CH))},
                       "discharge": {"fylite:channel_aturns": cc}})
    return np.asarray(f["r"], float)[:N_CH]


def drive_reproduction(wv, dev, eqp, ip0, cc) -> dict:
    """★The drive HOLDS KEFIT's coil currents (V = R I0 per turn) and adds DRIVE_EXTRA of it — a drive a coil circuit
    could be given, not a flat voltage the channels relax against on their own L/R."""
    nt = RAMP["steps"] + 1
    r_ch = channel_resistance(wv, dev, cc)
    volts = np.tile(r_ch * cc * (1.0 + DRIVE_EXTRA), (nt, 1))
    rv = march(wv, dev, eqp, ip0, cc, {}, "voltage", volts=volts)
    rc = march(wv, dev, eqp, ip0, cc, {}, "current", aturns=rv["currents"][:, :N_CH])
    pv, pc = rv["currents"][:, N_CH:], rc["currents"][:, N_CH:]
    return {"drive_extra": DRIVE_EXTRA, "volts_per_turn": [float(v) for v in volts[0]],
            "channel_change_rel_max": float(np.max(np.abs(rv["currents"][-1, :N_CH] / cc - 1.0))),
            "shell_max_A": float(np.abs(pv).max()), "shell_rel_max": float(np.abs(pc - pv).max() / np.abs(pv).max()),
            "voltage": track(rv), "current": track(rc)}


def forward_edge(bme, dev, case: Path) -> dict:
    from fylite.io import geqdsk
    members = bme.tar_members(case / bme.KEFIT_TAR)
    out = {}
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for name in bme.FORWARD_CASES:
            itime = name[1:5]
            pre = f"kefit_raw_east137985/rejected/{name}/"
            (tmp / "g").write_bytes(members[f"{pre}g{bme.SHOT}.0{itime}"])
            (tmp / "a").write_bytes(members[f"{pre}a{bme.SHOT}.0{itime}"])
            g, a = geqdsk.read_geqdsk(tmp / "g"), geqdsk.read_afile(tmp / "a", arrays=True)
            ref = bme.kefit_map(g)
            ip0, cc, eqp = kefit_inputs(bme, g, a)
            inputs = {"device": dev, "discharge": {"fylite:channel_aturns": cc, "fylite:ip": np.array([ip0])}, "equilibrium": eqp}
            out[name] = {}
            for tag, st in (("node", {}), ("edge", {"edge_fraction": 1.0, "max_iter": 12000.0})):
                t0 = time.time()
                facts, fields, _ = bme.door("code/forward", st, inputs)
                out[name][tag] = {"seconds": round(time.time() - t0, 1),
                                  **{k: facts[k] for k in ("converged", "settled", "iterations", "residual", "bnd_kind", "axis_r", "axis_z", "fb_amp")},
                                  "compare": bme.compare_maps(ref, bme.fylite_map(facts, fields))}
    return out


def readings(case: Path) -> dict:
    wv = _tool("benchmark_wall_vstab", "benchmark-wall-vstab.py")
    bme = _tool("benchmark_equilibrium", "benchmark-equilibrium.py")
    dev = wv.east_card()
    g, a, gsha = wv.kefit_slice(case)
    ip0, cc, eqp = kefit_inputs(bme, g, a)
    lib = os.environ.get("FYLITE_KERNEL_LIB")
    env = {"kernel_lib_sha256": hashlib.sha256(Path(lib).read_bytes()).hexdigest() if lib else None}
    return {"reference": "none (verification identities); equilibrium and coil currents from KEFIT t4041_mag (CASE-23 kefit_raw_east137985.tar.gz)",
            "kefit_g_sha256": gsha, "environment": env, "passive": PASSIVE, "ramp": RAMP,
            "wall_decay": wall_decay(wv, dev),
            "flux_freezing": flux_freezing(wv, dev, eqp, ip0, cc),
            "drive_reproduction": drive_reproduction(wv, dev, eqp, ip0, cc),
            "forward_edge": forward_edge(bme, dev, case)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("readings")
    r.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    case = Path(os.environ["FYDOC_ORACLE"]) / CASE23
    out = readings(case)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / READINGS).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("wall_decay", "flux_freezing")}, indent=1, default=float)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
