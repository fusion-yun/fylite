"""The derived equilibrium metrics the register records read (`docs/benchmark/readings/*_metrics.json`), from the raw
readings in fydoc CASE-23 `corpus/benchmark/`.

★2026-09-19: these four files were derived by hand when the records were written; no generator was committed, so a
re-run of the raw readings (the edge rule becoming `code/forward`'s default, FR-EQ-001) had nothing to re-derive them
with.  This is that generator.  It was checked against the hand-derived files on the raw readings they came from.

Subcommand: ``metrics [--case DIR] [--out DIR]``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
FWD = "corpus/benchmark/forward_kefit_east137985.json"
EVO = "corpus/benchmark/evolve_free_boundary_east137985.json"
INV = "corpus/benchmark/inverse_shape_east137985.json"


def sha(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def src(case: Path, rel: str) -> dict:
    return {"case": CASE, "path": rel, "checksum": sha(case / rel)}


def _cmp(c: dict) -> dict:
    return {"axis_mm": math.hypot(c["dR_axis_mm"], c["dZ_axis_mm"])}


def forward_kefit(case: Path, archive_sha: str) -> dict:
    raw = json.loads((case / FWD).read_text(encoding="utf-8"))
    slices = {}
    for name, c in raw["cases"].items():
        cm, fy = c["compare"], c["fylite"]
        slices[name] = {"time_s": c["time_s"], **_cmp(cm),
                        **{k: cm[k] for k in ("psin_rms_inside", "psin_max_inside", "n_nodes_inside", "span_rel", "ip_rel",
                                              "boundary_median_mm", "boundary_max_mm", "xpoint_dist_mm") if k in cm},
                        "fylite_settled": fy["settled"], "fylite_converged": fy["converged"], "fylite_residual": fy["residual"]}
    return {"what": "B-14 派生指标：fylite 前向解对 KEFIT 的答案，EAST #137985 四个切片",
            "reference": raw["reference"], "archive_sha256": archive_sha, "source": src(case, FWD),
            "door_settings": raw["door_settings"], "slices": slices}


def forward_edge(case: Path) -> dict:
    raw = json.loads((case / EVO).read_text(encoding="utf-8"))["forward_edge"]
    out = {}
    for name, rules in raw.items():
        out[name] = {}
        for rule, r in rules.items():
            cm = r["compare"]
            out[name][rule] = {"converged": r["converged"], "settled": r["settled"], "residual": r["residual"],
                               "iterations": r["iterations"], "seconds": r["seconds"], "fb_amp_A": r["fb_amp"],
                               "psin_rms_inside": cm["psin_rms_inside"], "psin_max_inside": cm["psin_max_inside"],
                               **_cmp(cm), "boundary_median_mm": cm.get("boundary_median_mm"),
                               "xpoint_dist_mm": cm.get("xpoint_dist_mm")}
    return {"what": "eq-forward 派生指标：node / edge 两种边界规则，各自对 KEFIT 的图", "source": src(case, EVO), "slices": out}


def evolve(case: Path) -> dict:
    raw = json.loads((case / EVO).read_text(encoding="utf-8"))
    ff, dr = raw["flux_freezing"], raw["drive_reproduction"]
    return {"what": "eq-evolve 派生指标（原始读数为实验类，见 source 指针）", "source": src(case, EVO),
            "wall_decay": {"max_rel_deviation": raw["wall_decay"]["max_rel_deviation"]},
            "flux_freezing": {"drift_over_moved": ff["drift_over_moved"],
                              "max_circuit_residual": max(abs(v) for v in ff["circuit_residual"]),
                              "gs_state_after_start": sorted(set(ff["gs_state"][1:])), "fb_held": ff["facts"].get("fb_held", 0.0)},
            "drive_reproduction": {"shell_rel_max": dr["shell_rel_max"],
                                   "voltage_max_circuit_residual": max(abs(v) for v in dr["voltage"]["circuit_residual"]),
                                   "current_max_circuit_residual": max(abs(v) for v in dr["current"]["circuit_residual"]),
                                   "gs_state_voltage": sorted(set(dr["voltage"]["gs_state"][1:])),
                                   "gs_state_current": sorted(set(dr["current"]["gs_state"][1:]))},
            "forward_edge": {}}


def inverse(case: Path) -> dict:
    raw = json.loads((case / INV).read_text(encoding="utf-8"))
    cur = raw["currents"]
    ns = {k: {**{q: v["compare"][q] for q in ("psin_rms_inside", "psin_max_inside", "boundary_median_mm", "boundary_max_mm",
                                               "xpoint_dist_mm") if q in v["compare"]}, **_cmp(v["compare"])}
          for k, v in raw["null_space"].items()}
    return {"what": "B-21 派生指标：fylite 静态逆解对 FreeGSNKE 的记录逆解，目标是 KEFIT 的边界",
            "reference": raw["reference"], "source": src(case, INV),
            "inputs": {k: raw["inputs"][k] for k in ("g_file", "g_sha256", "a_file", "a_sha256", "ip_A", "target_points",
                                                      "gauge_factor", "settings", "target_segment_median_mm")},
            "fair_window": raw["fair_window"], "boundary_vs_target": raw["boundary_vs_target"],
            "currents_rms_kAt": {k: cur[k] for k in ("fylite_vs_kefit_rms_kAt", "freegsnke_vs_kefit_rms_kAt",
                                                     "fylite_vs_freegsnke_rms_kAt", "fylite_vs_freegsnke_max_kAt")},
            "n_circuits": len(cur["fylite"]), "null_space_forward": ns,
            "design_facts": raw["design"]["facts"], "design_notes": raw["design"]["notes"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("metrics")
    m.add_argument("--case", type=Path, default=Path(os.environ.get("FYDOC_ORACLE", ROOT.parent / "fydoc" / "cases")) / CASE)
    m.add_argument("--out", type=Path, default=ROOT / "docs" / "benchmark" / "readings")
    a = ap.parse_args()
    old = json.loads((a.out / "forward_kefit_metrics.json").read_text(encoding="utf-8"))
    files = {"forward_kefit_metrics.json": forward_kefit(a.case, old["archive_sha256"]),
             "forward_edge_rule_metrics.json": forward_edge(a.case),
             "evolve_free_boundary_metrics.json": evolve(a.case),
             "inverse_shape_freegsnke_metrics.json": inverse(a.case)}
    a.out.mkdir(parents=True, exist_ok=True)
    for name, d in files.items():
        (a.out / name).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
