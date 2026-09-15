#!/usr/bin/env python3
"""Fixed-boundary equilibrium benchmarks (register V-19 · B-16): fylite ``code/fixed_boundary`` against a closed form,
CHEASE, and KEFIT's map.

★★2026-09-15 (用户「补全 fixed-boundary 情景」): until the kernel's ``code/fixed_boundary`` door no fixed-boundary
benchmark could make fylite SOLVE — ``B-10`` read a GS residual off CHEASE's output (now ``V-16``).  The problem every code
is handed here is the same: an outline held as psi = const, p'(psi_N) and FF'(psi_N), and (for CHEASE, whose
normalisation needs it) the current inside the outline.

Subcommands
-----------
``solovev --out DIR``
    V-19: the Solov'ev contour psi = pc - e1 (R^2 - r0^2)^2 - e2 R^2 Z^2 - e3 Z^2 (elongation 1.7, outboard edge 2.25 m),
    constant p' and FF'.  fylite at 33² / 65² / 129² and CHEASE (EXPEQ, NSURF = 6) against the closed form: psi_N inside,
    the axis, the flux span, I_p by Ampere's law on the exact contour, q on axis by the local expansion.
``east --out DIR``
    B-16: EAST #137985 t = 4.041 s — KEFIT's magnetics-only raw-tree run (FYDOC-CASE-23, variant rejected, ``t4041_mag``):
    its psi_N = 0.995 surface (360 rays from its axis on a bicubic spline of its map, first crossing), its p'/FF' on that
    surface's psi_N (101 points, linear in KEFIT's 65), F at 0.995 for the edge field, and the current inside by Ampere's
    law on its map.  fylite (65², 129²) · CHEASE (NS = NT = 40, 80) · KEFIT's own free-boundary map inside the surface.

Conventions (measured on the Solov'ev case, recorded in its readings): fylite takes p', FF' per full-turn Wb in the
axis-maximum orientation; CHEASE's EXPEQ takes ``-mu0 R0^2 / B0 * 2 pi p'`` and ``-2 pi FF' / B0`` on sqrt(psi_N), the
boundary in units of R0EXP, T = 1 at the edge (B0EXP = F_edge / R0EXP) and CURRT = mu0 I_p / (R0EXP B0EXP) with NCSCAL = 2.

Environment: ``$FYLITE_KERNEL_LIB`` with ``code/fixed_boundary``; ``$CHEASE_EXE`` (default the local third_party build);
``$FYDOC_ORACLE`` for ``east``.  EAST inputs and CHEASE's EAST outputs are written to ``--out`` only (experiment class:
they go to the fydoc case, never into this repository).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MU0 = 4e-7 * np.pi
TWO_PI = 2.0 * np.pi
CHEASE = Path(os.environ.get("CHEASE_EXE", str(ROOT.parent / "third_party/chease/src-f90/chease")))
CONDA_LIB = Path.home() / ".claude-science/conda/envs/r/lib"
CASE23 = "FYDOC-CASE-23-east-137985-efit-east"
EAST_MEMBER = "kefit_raw_east137985/rejected/t4041_mag/g137985.04041"
EDGE = 0.995
NRAY = 360
Q_POINTS = np.linspace(0.1, 0.9, 9)


def _bme():
    spec = importlib.util.spec_from_file_location("benchmark_equilibrium", ROOT / "tools" / "benchmark-equilibrium.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------------ the Solov'ev contour

class Solovev:
    """psi = pc - e1 (R^2 - r0^2)^2 - e2 R^2 Z^2 - e3 Z^2 (full-turn Wb, axis maximum), psi = 0 on its contour."""
    r0, e1, e3, b0 = 1.8, 1.0, 1.0, 2.0

    def __init__(self):
        self.e2 = (4 * self.e1 * self.r0 ** 2 / 1.7 ** 2 - self.e3) / self.r0 ** 2
        self.pc = self.e1 * (2.25 ** 2 - self.r0 ** 2) ** 2
        self.pp = (8 * self.e1 + 2 * self.e2) / (4 * np.pi ** 2 * MU0)
        self.ff = 2 * self.e3 / (4 * np.pi ** 2)

    def psi(self, r, z):
        return self.pc - self.e1 * (r * r - self.r0 ** 2) ** 2 - self.e2 * r * r * z * z - self.e3 * z * z

    def grad(self, r, z):
        return (-4 * self.e1 * r * (r * r - self.r0 ** 2) - 2 * self.e2 * r * z * z, -2 * self.e2 * r * r * z - 2 * self.e3 * z)

    def outline(self, n: int):
        th = TWO_PI * np.arange(n) / n
        lo, hi = np.zeros(n), np.full(n, 1.5)
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            ins = self.psi(self.r0 + mid * np.cos(th), mid * np.sin(th)) > 0
            lo, hi = np.where(ins, mid, lo), np.where(ins, hi, mid)
        t = 0.5 * (lo + hi)
        return self.r0 + t * np.cos(th), t * np.sin(th)

    def ip(self) -> float:
        r, z = self.outline(20000)
        rm, zm = 0.5 * (r + np.roll(r, -1)), 0.5 * (z + np.roll(z, -1))
        gr, gz = self.grad(rm, zm)
        dl = np.hypot(np.roll(r, -1) - r, np.roll(z, -1) - z)
        return float(np.sum(np.hypot(gr, gz) / (TWO_PI * rm) * dl) / MU0)

    def q0(self) -> float:
        a, b = 4 * self.e1 * self.r0 ** 2, self.e2 * self.r0 ** 2 + self.e3
        f0 = np.sqrt((self.r0 * self.b0) ** 2 + 2 * self.ff * self.pc)
        return float(f0 * np.pi / (self.r0 * np.sqrt(a * b)))

    def problem(self) -> dict:
        r, z = self.outline(720)
        return {"r": r, "z": z, "x": np.array([0.0, 1.0]), "pp": np.array([self.pp, self.pp]), "ff": np.array([self.ff, self.ff]),
                "r0": self.r0, "f_edge": self.r0 * self.b0, "ip_inside": self.ip()}

    def side(self) -> dict:
        return {"psin": lambda rr, zz: 1.0 - self.psi(rr, zz) / self.pc, "axis": (self.r0, 0.0), "span": -self.pc,
                "ip": self.ip(), "q0": self.q0(), "q_of": None}


# ------------------------------------------------------------------------------------------------ the three solvers

def fylite_side(prob: dict, n: int) -> dict:
    from scipy.interpolate import RectBivariateSpline
    from fylite.io import fydoc
    plan = {"settings": {"nr": n, "nz": n},
            "inputs": {"equilibrium": {"time_slice": {"boundary": {"outline": {"r": prob["r"], "z": prob["z"]}},
                                                      "profiles_1d": {"psi_norm": prob["x"], "dpressure_dpsi": prob["pp"],
                                                                      "f_df_dpsi": prob["ff"]}},
                                       "vacuum_toroidal_field": {"r0": np.array(prob["r0"]),
                                                                 "b0": np.array(prob["f_edge"] / prob["r0"])}}}}
    rec = fydoc.complete("code/fixed_boundary", plan)
    f = {k: float(v["value"]) for k, v in rec["facts"].items()}
    F = {k: np.asarray(v["data"], float) for k, v in rec["fields"].items()}
    rg, zg = F["grid_r"], F["grid_z"]
    psi = F["psi"].reshape(len(rg), len(zg))
    sp = RectBivariateSpline(rg, zg, psi, kx=3, ky=3)
    qx, qq = F["q_x"], F["q"]
    return {"psin": lambda rr, zz: 1.0 - sp(rr, zz, grid=False) / f["psi_axis"], "axis": (f["axis_r"], f["axis_z"]),
            "span": -f["psi_axis"], "ip": f["ip"], "q0": f["q0"], "q_of": lambda xx: np.interp(xx, qx, np.abs(qq)),
            "facts": {k: f[k] for k in ("ip", "psi_axis", "axis_r", "axis_z", "q0", "q95", "iterations", "converged", "residual",
                                        "gap_rms", "gap_max", "kept", "condition", "beta_p", "p_axis", "volume")},
            "notes": list(rec.get("notes") or []), "grid": [len(rg), len(zg)],
            "nodes": {"rg": rg, "zg": zg, "psi": psi, "fraction": F["fraction"].reshape(len(rg), len(zg)), "psi_axis": f["psi_axis"]}}


def chease_inputs(prob: dict, ns: int, npsi: int, title: str) -> tuple[str, str]:
    r0, b0 = prob["r0"], prob["f_edge"] / prob["r0"]
    s = np.sqrt(prob["x"]) if len(prob["x"]) > 2 else np.linspace(0.0, 1.0, 101)
    pp = np.interp(s ** 2, prob["x"], prob["pp"])
    ff = np.interp(s ** 2, prob["x"], prob["ff"])
    zc = 0.5 * (prob["z"].max() + prob["z"].min())
    aspct = (prob["r"].max() - prob["r"].min()) / (prob["r"].max() + prob["r"].min())
    lines = [f"{aspct:.10e}", f"{zc / r0:.10e}", "0.0", f"{len(prob['r'])}"]
    lines += [f"{a / r0:.12e} {b / r0:.12e}" for a, b in zip(prob["r"], prob["z"])]
    lines += [f"{len(s)} 4", "1"] + [f"{v:.12e}" for v in s]
    lines += [f"{v:.12e}" for v in -MU0 * r0 ** 2 / b0 * TWO_PI * pp] + [f"{v:.12e}" for v in -TWO_PI * ff / b0]
    currt = MU0 * prob["ip_inside"] / (r0 * b0)
    nl = (f"*** {title}\n &EQDATA\n NSURF=6, NEQDSK=0, NPPFUN=4, NFUNC=4, NSTTP=1, NFUNRHO=0,\n"
          f" NCSCAL=2, CURRT={currt:.12e}, NTMF0=0, R0EXP={r0}, B0EXP={b0:.12e}, SIGNB0XP=1, SIGNIPXP=1,\n"
          f" NS={ns}, NT={ns}, NPSI={npsi}, NCHI={npsi}, NISO={npsi}, NRBOX=129, NZBOX=129,\n"
          f" TENSBND=0., TENSPROF=0., RELAX=0., NDIAGOP=1, NIDEAL=6, NPLOT=0, NVERBOSE=1, EPSLON=1.0E-10,\n"
          f" CPRESS=1., PSISCL=1., NBAL=0, NOPT=0, NPROPT=1, NBSEXPQ=0, ASPCT={aspct:.10e},\n /\n")
    return "\n".join(lines) + "\n", nl


def chease_run(prob: dict, work: Path, ns: int, title: str) -> dict[str, bytes]:
    work.mkdir(parents=True, exist_ok=True)
    expeq, nl = chease_inputs(prob, ns, int(2.5 * ns), title)
    (work / "EXPEQ").write_text(expeq)
    (work / "chease_namelist").write_text(nl)
    shutil.copy(CHEASE, work / "chease")
    env = dict(os.environ)
    if CONDA_LIB.is_dir():
        env["LD_LIBRARY_PATH"] = f"{CONDA_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
    p = subprocess.run([str(work / "chease")], cwd=work, capture_output=True, text=True, timeout=900, env=env)
    out = work / "EQDSK_COCOS_02.OUT"
    if not out.is_file():
        raise RuntimeError(f"CHEASE wrote no EQDSK (rc {p.returncode}): {p.stdout[-500:]}")
    return {"EXPEQ": expeq.encode(), "chease_namelist": nl.encode(), "EQDSK_COCOS_02.OUT": out.read_bytes()}


def gfile_side(gbytes: bytes, level_frac: float = 1.0) -> dict:
    """A g-file (CHEASE's or KEFIT's) as a side: psi_N' = psi_N / level_frac, so 1 falls on the held surface."""
    from scipy.interpolate import RectBivariateSpline
    from scipy.optimize import minimize
    from fylite.io import geqdsk
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "g").write_bytes(gbytes)
        g = geqdsk.read_geqdsk(Path(d) / "g")
    m = _bme().kefit_map(g)
    sp = RectBivariateSpline(m["rg"], m["zg"], m["psi"], kx=3, ky=3)
    ax = minimize(lambda v: -sp(v[0], v[1], grid=False).item(), m["axis"], method="Nelder-Mead",
                  options={"xatol": 1e-9, "fatol": 1e-14}).x
    pa = np.asarray(sp(ax[0], ax[1], grid=False)).item()
    level = pa + level_frac * (m["psi_bnd"] - pa)
    qx = np.linspace(0.0, 1.0, len(g["qpsi"]))
    qv = np.abs(np.asarray(g["qpsi"], float))
    return {"psin": lambda rr, zz: (sp(rr, zz, grid=False) - pa) / (level - pa), "axis": (float(ax[0]), float(ax[1])),
            "span": level - pa, "ip": abs(float(g["current"])), "q0": float(qv[0]),
            "q_of": lambda xx: np.interp(level_frac * np.asarray(xx), qx, qv), "g": g, "map": m, "sp": sp, "psi_axis": pa, "level": level}


def compare(ref: dict, got: dict, prob: dict) -> dict:
    """got against ref on a 121 x 201 lattice over the held outline (points inside it)."""
    from matplotlib.path import Path as MPath
    R, Z = np.meshgrid(np.linspace(prob["r"].min(), prob["r"].max(), 121), np.linspace(prob["z"].min(), prob["z"].max(), 201), indexing="ij")
    ins = MPath(np.c_[prob["r"], prob["z"]]).contains_points(np.c_[R.ravel(), Z.ravel()])
    rr, zz = R.ravel()[ins], Z.ravel()[ins]
    d = got["psin"](rr, zz) - ref["psin"](rr, zz)
    out = {"psin_rms": float(np.sqrt(np.mean(d ** 2))), "psin_max": float(np.abs(d).max()), "n_points": int(ins.sum()),
           "axis_mm": 1e3 * float(np.hypot(got["axis"][0] - ref["axis"][0], got["axis"][1] - ref["axis"][1])),
           "span_rel": float(got["span"] / ref["span"] - 1.0), "ip_rel": float(got["ip"] / ref["ip"] - 1.0),
           "q0_rel": float(got["q0"] / ref["q0"] - 1.0)}
    if ref.get("q_of") is not None and got.get("q_of") is not None:
        qa, qb = ref["q_of"](Q_POINTS), got["q_of"](Q_POINTS)
        out.update(q_rel_rms_01_09=float(np.sqrt(np.mean((qb / qa - 1.0) ** 2))),
                   q_rel_max_01_09=float(np.abs(qb / qa - 1.0).max()),
                   q95_rel=float(got["q_of"](0.95) / ref["q_of"](0.95) - 1.0))
    return out


def node_error(sol: Solovev, side: dict) -> float:
    """max |psi - psi_exact| / pc on the nodes whose cell is wholly inside the contour (the kernel gate's own measure)."""
    n = side["nodes"]
    R, Z = np.meshgrid(n["rg"], n["zg"], indexing="ij")
    full = n["fraction"] == 1.0
    return float(np.abs(n["psi"] - sol.psi(R, Z))[full].max() / sol.pc)


def pack_runs(runs: dict[str, dict[str, bytes]], prefix: str) -> bytes:
    members = [(f"{prefix}/{run}/{name}", data) for run in sorted(runs) for name, data in sorted(runs[run].items())]
    return _bme().pack(members)


# ------------------------------------------------------------------------------------------------ V-19

def solovev(out: Path, with_chease: bool = True) -> dict:
    sol = Solovev()
    prob = sol.problem()
    exact = sol.side()
    res = {"problem": {"r0": sol.r0, "e1": sol.e1, "e2": sol.e2, "e3": sol.e3, "pc_Wb": sol.pc, "b0": sol.b0,
                       "pprime_Pa_per_Wb": sol.pp, "ffprime_T2m2_per_Wb": sol.ff, "outline_points": len(prob["r"]),
                       "ip_ampere_A": exact["ip"], "q0_closed_form": exact["q0"]},
           "fylite": {}, "chease": {}}
    for n in (33, 65, 129):
        s = fylite_side(prob, n)
        res["fylite"][f"n{n}"] = {"facts": s["facts"], "notes": s["notes"], "node_error": node_error(sol, s), "compare": compare(exact, s, prob)}
    res["fylite"]["node_error_ratio_65_129"] = res["fylite"]["n65"]["node_error"] / res["fylite"]["n129"]["node_error"]
    if with_chease:
        runs = {}
        with tempfile.TemporaryDirectory() as d:
            for ns in (40, 80):
                runs[f"ns{ns}"] = chease_run(prob, Path(d) / f"ns{ns}", ns, "Solov'ev fixed boundary (V-19)")
                c = gfile_side(runs[f"ns{ns}"]["EQDSK_COCOS_02.OUT"])
                res["chease"][f"ns{ns}"] = {"compare": compare(exact, c, prob), "psi_units": "g-file per radian, axis minimum"}
        f129 = fylite_side(prob, 129)
        c80 = gfile_side(runs["ns80"]["EQDSK_COCOS_02.OUT"])
        res["fylite_129_vs_chease_ns80"] = compare(c80, f129, prob)
    (out / "solovev_fixed_boundary.json").write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    return res


# ------------------------------------------------------------------------------------------------ B-16

def east_problem(case: Path) -> tuple[dict, bytes]:
    bme = _bme()
    with tarfile.open(case / bme.KEFIT_TAR, "r:gz") as tf:
        gbytes = tf.extractfile(EAST_MEMBER).read()
    k = gfile_side(gbytes)
    g, sp, ax, pa = k["g"], k["sp"], k["axis"], k["psi_axis"]
    level = pa + EDGE * (k["map"]["psi_bnd"] - pa)
    th = TWO_PI * np.arange(NRAY) / NRAY
    #: the FIRST crossing along each ray (a ray past the X point re-enters psi > level in the private flux)
    steps = np.arange(0.0, 1.2, 0.002)
    vals = sp(ax[0] + steps[None, :] * np.cos(th)[:, None], ax[1] + steps[None, :] * np.sin(th)[:, None], grid=False)
    first = np.argmax(vals <= level, axis=1)
    if np.any(first == 0):
        raise RuntimeError("a ray from KEFIT's axis never crosses the 0.995 level")
    lo, hi = steps[first - 1], steps[first]
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        ins = sp(ax[0] + mid * np.cos(th), ax[1] + mid * np.sin(th), grid=False) > level
        lo, hi = np.where(ins, mid, lo), np.where(ins, hi, mid)
    t = 0.5 * (lo + hi)
    br, bz = ax[0] + t * np.cos(th), ax[1] + t * np.sin(th)
    rm, zm = 0.5 * (br + np.roll(br, -1)), 0.5 * (bz + np.roll(bz, -1))
    gr, gz = sp(rm, zm, dx=1, grid=False), sp(rm, zm, dy=1, grid=False)
    dl = np.hypot(np.roll(br, -1) - br, np.roll(bz, -1) - bz)
    ip_in = float(np.sum(np.hypot(gr, gz) / (TWO_PI * rm) * dl) / MU0)
    s = k["map"]["gauge_factor"]
    x = np.linspace(0.0, 1.0, len(g["pprime"]))
    xt = np.linspace(0.0, 1.0, 101)
    prob = {"r": br, "z": bz, "x": xt, "pp": np.interp(EDGE * xt, x, np.asarray(g["pprime"], float) / s),
            "ff": np.interp(EDGE * xt, x, np.asarray(g["ffprim"], float) / s), "r0": float(g["rcentr"]),
            "f_edge": abs(float(np.interp(EDGE, x, np.asarray(g["fpol"], float)))), "ip_inside": ip_in}
    return prob, gbytes


def east(case: Path, out: Path) -> dict:
    bme = _bme()
    prob, gbytes = east_problem(case)
    kef = gfile_side(gbytes, EDGE)
    res = {"reference": f"KEFIT raw-tree run {EAST_MEMBER} (CASE-23 {bme.KEFIT_TAR}); held surface psi_N = {EDGE}",
           "inputs": {"g_sha256": bme.sha(gbytes), "edge_psin": EDGE, "rays": NRAY, "r0_m": prob["r0"], "f_edge_Tm": prob["f_edge"],
                      "ip_inside_A": prob["ip_inside"], "ip_kefit_total_A": abs(float(kef["g"]["current"])),
                      "profile_points": len(prob["x"])},
           "fylite": {}, "chease": {}, "compare": {}}
    sides = {"kefit": kef}
    for n in (65, 129):
        sides[f"fylite_{n}"] = s = fylite_side(prob, n)
        res["fylite"][f"n{n}"] = {"facts": s["facts"], "notes": s["notes"]}
    runs = {}
    with tempfile.TemporaryDirectory() as d:
        for ns in (40, 80):
            runs[f"ns{ns}"] = chease_run(prob, Path(d) / f"ns{ns}", ns, f"EAST 137985 t4041_mag psi_N {EDGE} fixed boundary (B-16)")
            sides[f"chease_{ns}"] = gfile_side(runs[f"ns{ns}"]["EQDSK_COCOS_02.OUT"])
            res["chease"][f"ns{ns}"] = {"q0": sides[f"chease_{ns}"]["q0"], "ip": sides[f"chease_{ns}"]["ip"]}
    for ref, got in [("chease_80", "fylite_129"), ("chease_80", "fylite_65"), ("chease_80", "chease_40"), ("fylite_129", "fylite_65"),
                     ("kefit", "fylite_129"), ("kefit", "chease_80")]:
        res["compare"][f"{got}_vs_{ref}"] = compare(sides[ref], sides[got], prob)
    tar = pack_runs(runs, "chease_fixed_boundary_east137985")
    (out / "chease_fixed_boundary_east137985.tar.gz").write_bytes(tar)
    res["chease_archive_sha256"] = bme.sha(tar)
    (out / "fixed_boundary_east137985.json").write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("solovev")
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--no-chease", action="store_true")
    b = sub.add_parser("east")
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--case", type=Path, help=f"the {CASE23} directory (default $FYDOC_ORACLE/{CASE23})")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.cmd == "solovev":
        res = solovev(args.out, not args.no_chease)
    else:
        case = args.case or Path(os.environ["FYDOC_ORACLE"]) / CASE23
        res = east(case, args.out)
    print(json.dumps(res, indent=1, default=float)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
