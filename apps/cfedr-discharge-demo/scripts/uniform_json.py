"""Resample the assembled discharge's frames onto a uniform time grid (constant playback speed).

The assembly's frames are keyframes wherever a profile was recorded (every 0.5 s in the ramps, every 2 s or a
window apart on the flat top), so stepping through them plays the discharge at a speed that changes by segment.
This writes frames every DT seconds of discharge time inside each displayed segment (ramp-up · flat-top
window · ramp-down; the steady flat top between them stays broken off, as on the time axis):

* profiles T_e / T_i / n_e — linear in time between the two keyframes around the frame, never across a segment
  boundary (outside the keyframes' span the nearest keyframe is held);
* the equilibrium — the latest solved one of the same phase at or before the frame time (equilibria are solved
  samples, not a field to interpolate), else the nearest solved one;
* ``i`` — the trace sample nearest the frame time (the page and the animation read their headline values there).

Usage: python uniform_json.py DISCHARGE.json DT OUT.json
"""
from __future__ import annotations

import bisect
import json
import sys
from pathlib import Path

SEGMENTS = [(0.0, 62.0), (62.0, 152.0), (6146.0, 6210.0)]


def phase_of(t):
    return "ramp-up" if t < 60.0 else ("flat top" if t < 6150.0 else "ramp-down")


def lerp_list(a, b, w):
    out = []
    for x, y in zip(a, b):
        if x is None or y is None:
            out.append(x if w < 0.5 else y)
        else:
            out.append(float(f"{x + (y - x) * w:.3g}"))
    return out


def main():
    src, dt, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    D = json.loads(Path(src).read_text())
    keys = sorted(D["frames"], key=lambda f: f["t"])
    tt = D["traces"]["t"]
    eqs = D["equilibria"]
    eq_ok = [k for k, e in enumerate(eqs) if e["ok"]]
    frames = []
    for a, b in SEGMENTS:
        seg = [f for f in keys if a <= f["t"] <= b]
        if not seg:
            continue
        kt = [f["t"] for f in seg]
        lo, hi = kt[0], kt[-1]
        n = int(round((hi - lo) / dt))
        for j in range(n + 1):
            t = round(lo + j * dt, 6)
            if t > hi + 1e-9:
                break
            k = bisect.bisect_right(kt, t) - 1
            if k >= len(seg) - 1:
                f0 = f1 = seg[-1]
                w = 0.0
            else:
                f0, f1 = seg[max(k, 0)], seg[max(k, 0) + 1]
                w = 0.0 if f1["t"] == f0["t"] else min(max((t - f0["t"]) / (f1["t"] - f0["t"]), 0.0), 1.0)
            same = [q for q in eq_ok if eqs[q]["phase"] == phase_of(t)]
            before = [q for q in same if eqs[q]["t"] <= t + 1e-9]
            k_eq = before[-1] if before else min(same or eq_ok, key=lambda q: abs(eqs[q]["t"] - t))
            i = bisect.bisect_left(tt, t)
            i = min(range(max(i - 1, 0), min(i + 1, len(tt) - 1) + 1), key=lambda q: abs(tt[q] - t))
            frame = {"t": t, "i": i, "eq": k_eq, "phase": phase_of(t),
                     "te": lerp_list(f0["te"], f1["te"], w), "ti": lerp_list(f0["ti"], f1["ti"], w),
                     "ne": lerp_list(f0["ne"], f1["ne"], w)}
            #: the nearer keyframe's labels (0-D keyframes carry no L-H phase)
            near = f0 if w < 0.5 else f1
            for key in ("lh", "tier"):
                if near.get(key) is not None:
                    frame[key] = near[key]
            frames.append(frame)
    D["frames"] = frames
    D["meta"]["uniform_dt"] = dt
    D["meta"]["keyframes"] = len(keys)
    Path(out).write_text(json.dumps(D, separators=(",", ":")))
    print(f"{out}: {len(keys)} keyframes -> {len(frames)} frames every {dt:g} s · {Path(out).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
