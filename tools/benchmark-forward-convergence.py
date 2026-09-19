"""The free-boundary forward solve on EAST #137985 (FR-EQ-001): what the upstream criterion asks — the Ip-constrained
solve converges, Ip to rel 1e-6, the convergence setting echoed — on the DEFAULT path, and the two boundary rules
against an independent code.

★Why an independent code: KEFIT's map is a reconstruction, and measured here it is NOT the forward solution of its
own currents and profiles — FreeGSNKE on exactly those inputs lands 0.0156 in psi_N from it.  So "which rule is
closer to KEFIT" never judged a rule.  FreeGSNKE's recorded forward solve (fydoc CASE-23 `corpus/freegsnke`, Lao85
profiles fitted to KEFIT's p' / FF' to 1e-9, KEFIT's twelve coil currents) is the third answer on t = 4.041 s.

Subcommand: ``reading [--out DIR]``.  Needs the runtime library, CASE-23 and the EAST deck ($FYLITE_DEVICE_DIR).
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import tarfile
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FGS = "corpus/freegsnke/freegsnke_vstab_east137985.tar.gz"
FGS_EQ = "freegsnke_vstab_east137985/fgs_equilibrium.npz"
FGS_JSON = "freegsnke_vstab_east137985/freegsnke.json"
#: the echo the criterion asks for: every knob of the convergence, as the door states it
ECHO = ("tol", "max_iter", "edge_fraction", "relax", "fb_gain", "ip_target")
RULES = {"default": {}, "node": {"edge_fraction": 0.0}}


def _tool(module: str, fname: str):
    spec = importlib.util.spec_from_file_location(module, ROOT / "tools" / fname)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def case_dir() -> Path:
    return Path(os.environ.get("FYDOC_ORACLE", ROOT.parent / "fydoc" / "cases")) / "FYDOC-CASE-23-east-137985-efit-east"


def pn_on(ref: dict, m: dict, ins: np.ndarray) -> np.ndarray:
    """m's psi_N at ref's nodes inside ref's boundary (bicubic)."""
    from scipy.interpolate import RectBivariateSpline
    pn = (m["psi"] - m["psi_axis"]) / (m["psi_bnd"] - m["psi_axis"])
    rr, zz = np.meshgrid(ref["rg"], ref["zg"], indexing="ij")
    return RectBivariateSpline(m["rg"], m["zg"], pn, kx=3, ky=3).ev(rr[ins], zz[ins])


def reading() -> dict:
    from fylite.io import geqdsk
    bme = _tool("bme", "benchmark-equilibrium.py")
    bef = _tool("bef", "benchmark-evolve-free-boundary.py")
    case = case_dir()
    members = bme.tar_members(case / bme.KEFIT_TAR)
    dev = bme.east_card()
    with tarfile.open(case / FGS) as tf:
        z = np.load(io.BytesIO(tf.extractfile(FGS_EQ).read()))
        fgs_meta = json.load(tf.extractfile(FGS_JSON))["eq"]
    fgs, fgs_inv = (bme.kefit_map({k.split("__", 1)[1]: (z[k].item() if z[k].shape == () else z[k])
                                   for k in z.files if k.startswith(tag + "__")}) for tag in ("fwd", "inv"))
    slices = {}
    for name in bme.FORWARD_CASES:
        itime = name[1:5]
        pre = f"kefit_raw_east137985/rejected/{name}/"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "g").write_bytes(members[f"{pre}g{bme.SHOT}.0{itime}"])
            (Path(d) / "a").write_bytes(members[f"{pre}a{bme.SHOT}.0{itime}"])
            g, a = geqdsk.read_geqdsk(Path(d) / "g"), geqdsk.read_afile(Path(d) / "a", arrays=True)
        ref = bme.kefit_map(g)
        ins = bme.inside(ref["boundary"], ref["rg"], ref["zg"])
        ip0, cc, eqp = bef.kefit_inputs(bme, g, a)
        inputs = {"device": dev, "discharge": {"fylite:channel_aturns": cc, "fylite:ip": np.array([ip0])},
                  "equilibrium": eqp}
        row = {"ip_target_A": ip0}
        maps = {"kefit": ref}
        for rule, st in RULES.items():
            t0 = time.time()
            facts, fields, notes = bme.door("code/forward", st, inputs)
            m = bme.fylite_map(facts, fields)
            maps[rule] = m
            row[rule] = {"seconds": round(time.time() - t0, 2),
                         **{k: float(facts[k]) for k in ("converged", "settled", "iterations", "residual", "fb_amp", "ip")},
                         "ip_rel": float(facts["ip"]) / ip0 - 1.0,
                         "echo": {k: float(facts[k]) for k in ECHO if k in facts},
                         "rule_note": next((n for n in notes if n.startswith("boundary rule")), None)}
        if name == "t4041_mag":
            #: FreeGSNKE's forward solve, and its inverse (coils nudged 0.37 kA.t): the spread of the reference's own
            #: two answers on this slice is the scale an agreement with it is read against
            maps["freegsnke"] = fgs
            maps["freegsnke_inverse"] = fgs_inv
        pn = {k: pn_on(ref, m, ins) for k, m in maps.items()}
        row["psin_rms_vs_kefit"] = {k: float(np.sqrt(np.mean((pn[k] - pn["kefit"]) ** 2))) for k in pn if k != "kefit"}
        if "freegsnke" in pn:
            row["psin_rms_vs_freegsnke"] = {k: float(np.sqrt(np.mean((pn[k] - pn["freegsnke"]) ** 2)))
                                            for k in pn if k != "freegsnke"}
            row["axis_z_m"] = {k: float(m["axis"][1]) for k, m in maps.items()}
        slices[name] = row
    return {"what": "EAST #137985 自由边界正解（code/forward）：缺省路径（边规则）的收敛与 Ip 约束、收敛设置回显；两种边界规则对 KEFIT 与对独立代码 FreeGSNKE",
            "freegsnke": {"archive": FGS, "slice": "t4041_mag",
                          **{k: fgs_meta[k] for k in ("profile_fit", "forward")}},
            "slices": slices}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reading")
    r.add_argument("--out", type=Path, default=ROOT / "docs" / "benchmark" / "readings")
    a = ap.parse_args()
    res = reading()
    (a.out / "forward_convergence_east137985.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n",
                                                               encoding="utf-8")
    for n, row in res["slices"].items():
        print(n, "default conv", row["default"]["converged"], "res %.1e" % row["default"]["residual"],
              "it", int(row["default"]["iterations"]), "ip_rel %.1e" % row["default"]["ip_rel"],
              "| node settled", row["node"]["settled"], "fb %.0f" % row["node"]["fb_amp"],
              "| vs FGS", row.get("psin_rms_vs_freegsnke"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
