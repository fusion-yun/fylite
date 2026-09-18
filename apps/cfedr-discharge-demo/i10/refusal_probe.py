"""Locate the -23 refusal of the I-10 ramp-down from the snapshot just before it (ledger I-10 / I-21).

The refused 10 ms step is many kernel sub-calls (the exchange cap is ~0.6 ms there): restore the
session, replay the session's own sub-step loop (`_resume` with the time left) until the kernel
refuses, print that sub-call and the last accepted state, then retry that exact request with one
physics switch changed at a time.

Usage: python refusal_probe.py SNAPSHOT.json REPLAY.json
"""
from __future__ import annotations

import json
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pcs_replay_drive import commands_at  # noqa: E402

from fylite.engine import session as S  # noqa: E402
from fylite.io import fydoc  # noqa: E402


def state_line(rec):
    fc = rec["facts"]
    cp = rec["fields"]["core_profiles"]["profiles_1d"]
    te = np.asarray(cp["electrons"]["temperature"]["data"], float)
    ti = np.asarray(cp["t_i_average"]["data"], float)
    ne = np.asarray(cp["electrons"]["density"]["data"], float)
    val = lambda k: fc[k]["value"] if k in fc else float("nan")  # noqa: E731
    return (f"t_end {val('t_end'):.6f} · dt_next {val('dt_next'):.3e} · Te0 {te[0]:.0f} eV · Te edge {te[-1]:.1f} eV · "
            f"Te min {te.min():.1f} eV @ {int(te.argmin())} · Ti0 {ti[0]:.0f} eV · Ti min {ti.min():.1f} eV · ne0 {ne[0]:.3e} · "
            f"ne min {ne.min():.3e} · lh_phase_out {val('lh_phase_out')} · capped {val('dt_capped')}")


def attempt(label, st, inp):
    try:
        rec = fydoc.complete("code/evolve", {"settings": st, "inputs": inp})
    except fydoc.Refused as e:
        ref = (e.record or {}).get("refusal", {})
        print(f"[{label}] REFUSED {e.code}: {ref.get('message', '')[:300]}")
        for n in ((e.record or {}).get("notes") or [])[-5:]:
            print(f"      note: {str(n)[:300]}")
        return None
    print(f"[{label}] ok · {state_line(rec)}")
    return rec


def main():
    snap_path, replay_path = sys.argv[1:3]
    snap = json.load(open(snap_path))
    nodes = json.load(open(replay_path))["nodes"]
    s = S.Session.from_snapshot(snap)
    t0 = s.t_start + s.k_next * S.STEP_S
    target = s.t_start + (s.k_next + 1) * S.STEP_S
    cmd, rphase = commands_at(nodes, t0)
    print(f"snapshot at k {s.k_next} · step {t0:.2f} -> {target:.2f} s · replay phase {rphase} · command {cmd}")
    base = dict(s.plan["settings"], dttarget=0.0, nsteps=1.0, globals=1.0)
    base.update(s._commands_to_settings(cmd))
    rec = s.prev
    print("  state at the snapshot:", state_line(rec))
    for j in range(S.Session.MAX_SUBSTEPS):
        left = target - float(rec["facts"]["t_end"]["value"])
        if left <= 1e-12:
            print(f"the step completed after {j} sub-calls — no refusal reproduced")
            return
        st, inp = s._resume(base, rec, left)
        try:
            nxt = fydoc.complete("code/evolve", {"settings": st, "inputs": inp})
        except fydoc.Refused as e:
            print(f"sub-call {j} REFUSED ({e.code}) with {left:.3e} s left of the step")
            print("  last accepted:", state_line(rec))
            for n in ((e.record or {}).get("notes") or [])[-8:]:
                print(f"      note: {str(n)[:300]}")
            break
        rec = nxt
        if j % 5 == 0:
            print(f"  sub-call {j} ok · {state_line(rec)}")
    else:
        print("no refusal within MAX_SUBSTEPS")
        return
    variants = [
        ("baseline again", {}, []),
        ("conductivity spitzer", {"conductivity": "spitzer"}, []),
        ("conductivity sauter", {"conductivity": "sauter"}, []),
        ("trapped_fraction eps", {"trapped_fraction": "eps"}, []),
        ("L-H model off", {}, ["lh_model"]),
        ("density channel off", {"ch-density": 0.0}, ["pinch_shape"]),
        ("current channel off", {"ch-current": 0.0, "ohmic": 0.0, "bootstrap": 0.0}, []),
        ("species composition off", {}, ["composition", "match_impurity"]),
        ("chi scaling off", {}, ["chi_scaling"]),
        ("half the step", {"dt_start": st["dt_start"] * 0.5}, []),
    ]
    for label, extra, drop in variants:
        v = {k: val for k, val in st.items() if k not in drop}
        v.update(extra)
        attempt(label, v, inp)


if __name__ == "__main__":
    main()
