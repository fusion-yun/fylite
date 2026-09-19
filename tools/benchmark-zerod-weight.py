"""The 0-D volume weight against METIS (`FR-TR-014` b) — the `w_th_weighted` block of
`docs/benchmark/readings/zerod_metis_attribution.json`, regenerated from the public entry.

★2026-09-19: after dilution the like-for-like W_th was left −2.4…−3.4 % off METIS, and the cause
was the 0-D average's circular weight `2 rho drho` against METIS's own `vpr`.  `code/zerod` now
takes a volume weight three ways, and this runs all three on METIS's own 21-point grid:

* ``circular`` — nothing set, the old weight (to the bit);
* ``shaped``   — nested D surfaces, `kappa_axis` / `shift_axis` = METIS's own κ(x = 0) and
  Shafranov shift `d0` (read from the certification archive when ``--metis`` is given, else the
  values the reading already records);
* ``bound``    — METIS's own `vpr` bound as `equilibrium/.../dvolume_drho_tor`.

Each converts METIS's volume averages <ne>, <Te> into the axis values the 0-D slots take under
ITS OWN weight — converting with one weight and averaging with another counts the weight twice.

Subcommand: ``reading [--metis DIR]``.  Needs the runtime library and CASE-10's corpus.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
READINGS = ROOT / "docs" / "benchmark" / "readings"
CORPUS = pathlib.Path(os.environ.get("FYDOC_ORACLE", ROOT.parent / "fydoc" / "cases")) \
    / "FYDOC-CASE-10-metis" / "corpus" / "metis_cert_zerod.csv"
N = 21
#: METIS's impurity mix on the ITER certification cases (C 6 + Ar 18 at 0.06)
MIX = {"z_imp": 6.0, "z_imp2": 18.0, "r_imp2": 0.06}


def metis_rows() -> dict:
    rows = [r for r in csv.reader(line for line in CORPUS.open() if not line.startswith("#"))]
    return {(r[0], round(float(r[1]), 4)): dict(zip(rows[0], r)) for r in rows[1:]}


def shaped_vprime(x, r0, a, kappa, delta, kappa_axis, shift_axis):
    """The kernel's `zerod::shaped_vprime`, for the axis conversion only (the door computes its own)."""
    u = np.linspace(0.0, 2.0 * np.pi, 257)[:-1]
    out = []
    for xi in x:
        dx = delta * xi
        t, dt = np.arcsin(dx), delta / np.sqrt(1.0 - dx * dx)
        kx, dk = kappa_axis + (kappa - kappa_axis) * xi * xi, 2.0 * (kappa - kappa_axis) * xi
        rc, drc = r0 + shift_axis * (1.0 - xi * xi), -2.0 * shift_axis * xi
        arg = u + t * np.sin(u)
        r = rc + a * xi * np.cos(arg)
        r_x = drc + a * np.cos(arg) - a * xi * np.sin(arg) * dt * np.sin(u)
        r_u = -a * xi * np.sin(arg) * (1.0 + t * np.cos(u))
        z_x, z_u = (kx + xi * dk) * a * np.sin(u), kx * a * xi * np.cos(u)
        out.append(np.sum(2.0 * np.pi * r * np.abs(r_x * z_u - z_x * r_u)) * (u[1] - u[0]))
    return np.array(out)


def metis_shape(metis: pathlib.Path, case: str, ts: float) -> tuple[float, float]:
    import scipy.io as sio
    post = sio.loadmat(metis / f"{case}.mat", squeeze_me=True, struct_as_record=False)["post"]
    tp = np.asarray(post.profil0d.temps, float).ravel()
    tz = np.asarray(post.z0dinput.cons.temps, float).ravel()
    kx0 = float(np.asarray(post.profil0d.kx)[int(np.argmin(abs(tp - ts)))][0])
    d0 = float(np.asarray(post.zerod.d0, float).ravel()[int(np.argmin(abs(tz - ts)))])
    return kx0, d0


def run_point(p: dict, overrides: dict, c: dict, variant: str, shape: tuple[float, float]) -> dict:
    """One door call: the axis values converted under `variant`'s weight, W_th against METIS's."""
    from fylite.io import fydoc
    from fylite.scenario.model import Phases, Scenario, _zerod_plan
    x = np.linspace(0.0, 1.0, N)
    f, ts = p["fit"], float(p["t_s"])
    vpr = np.array([float(c[f"vpr_{i:02d}"]) for i in range(N)])
    r0, a, k, dl = (float(c[q]) for q in ("R_m", "a_m", "kappa_geo", "delta_geo"))
    w = {"circular": 2.0 * x, "bound": vpr, "shaped": shaped_vprime(x, r0, a, k, dl, *shape)}[variant]
    prof = lambda pk: f["edge_frac"] + (1.0 - f["edge_frac"]) * (1.0 - x ** 2) ** pk  # noqa: E731
    avg = lambda g: np.trapezoid(g * w, x) / np.trapezoid(w, x)  # noqa: E731
    fed = {"ne_axis": float(c["nem_m3"]) / avg(prof(f["peaking_n"])),
           "te_axis_keV": float(c["tem_eV"]) / 1e3 / avg(prof(f["peaking_t"]))}
    o = dict(overrides)
    o.update(ne_flattop=fed["ne_axis"], te_flattop=fed["te_axis_keV"], peaking_n=f["peaking_n"], peaking_t=f["peaking_t"],
             edge_frac=f["edge_frac"], ti_over_te=f["ti_over_te"], zeff=p["diluted"]["zeff"], **MIX)
    ph = Phases(t_breakdown=0.0, t_rampup_end=1.0, t_flattop_end=ts + 10.0, t_end=ts + 20.0)
    plan = _zerod_plan(Scenario(**o, phases=ph), np.array([0.0, ts]), N)
    if variant == "shaped":
        plan["settings"].update(kappa_axis=shape[0], shift_axis=shape[1])
    if variant == "bound":
        plan["inputs"]["equilibrium"] = {"time_slice": [{"profiles_1d": {"dvolume_drho_tor": vpr}}]}
    rec = fydoc.complete("code/zerod", plan)
    w_th = float(np.ravel(rec["fields"]["summary"]["global_quantities"]["energy_thermal"]["value"]["data"])[-1])
    wm = float(c["wth_J"])
    return {"w_rel": (w_th - wm) / wm, "fed": fed}


def reading(metis: pathlib.Path | None) -> dict:
    att = json.loads((READINGS / "zerod_metis_attribution.json").read_text(encoding="utf-8"))
    over = {(q["case"], round(q["t_s"], 4)): q["overrides"]
            for q in json.loads((READINGS / "zerod_metis_metrics.json").read_text(encoding="utf-8"))["points"]}
    old = {(q["case"], round(q["t_s"], 4)): q for q in (att.get("w_th_weighted") or {}).get("points", [])}
    rows = metis_rows()
    pts = []
    for p in att["w_th_like_for_like"]["points"]:
        key = (p["case"], round(p["t_s"], 4))
        if metis is not None:
            shape = metis_shape(metis, p["case"], float(p["t_s"]))
        else:
            s = old[key]["shape"]
            shape = (s["kappa_axis"], s["shift_axis_m"])
        row = {"case": p["case"], "t_s": p["t_s"], "n_rho": N,
               "shape": {"kappa_axis": shape[0], "shift_axis_m": shape[1],
                         "source": "METIS post.profil0d.kx(:, 1) · post.zerod.d0 (certification archive)"}}
        for v in ("circular", "shaped", "bound"):
            row[v] = run_point(p, over[key], rows[key], v, shape)
        pts.append(row)
        print(p["case"][:26], p["t_s"], "  ".join(f"{v} {row[v]['w_rel']:+.4f}" for v in ("circular", "shaped", "bound")))
    att["w_th_weighted"] = {
        "_comment": ("2026-09-19 FR-TR-014 b：0D 体平均的权重三种取法（METIS 自己的 21 点网格、计稀释、约定对齐，"
                     "轴值按各自的权重从 METIS 体平均换算）——circular 即 2ρ（旧）；shaped 为嵌套 D 形面，κ(0) 与 Shafranov 位移取 "
                     "METIS 自己的；bound 为绑 METIS 自己的 vpr。★bound 的剩余就是幂律剖面形状一项。"
                     "生成：tools/benchmark-zerod-weight.py reading"),
        "points": pts}
    return att


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reading")
    r.add_argument("--metis", type=pathlib.Path, default=None,
                   help="METIS certification/metis directory (the .mat archives); else reuse the recorded shape")
    args = ap.parse_args()
    att = reading(args.metis)
    (READINGS / "zerod_metis_attribution.json").write_text(json.dumps(att, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote zerod_metis_attribution.json (w_th_weighted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
