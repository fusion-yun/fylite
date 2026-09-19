#!/usr/bin/env python3
"""Coil forces and conductor surface field on the shipped machine card (register record `FR-EQ-014`).

★★2026-09-17：`code/forces` 在**真装置卡**上的读数。判据的三条解析锚（单环自感环向力 ·
双环互感力 dM/dz · 环心场 mu0 I / 2R）是内核仓的 Rust 单测——它们不需要装置卡，也不该等一张卡。
这一支问的是另一件事：**那些锚在一台真机器上仍然成立吗**，以及这台机器的数字是多大。

系统 F_z 合力为零是牛顿第三定律：12 路线圈、真实安匝、没有等离子体，竖直力必须逐对抵消。
★这条**不是收敛判据**——不成立就是符号或配对错了，所以门卡在机器精度上，不卡一个工程容差。

Subcommand: ``readings --out DIR``.  Environment: ``$FYDOC_ORACLE``, ``$FYLITE_DEVICE_DIR``,
a kernel with ``code/forces``.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CASE23 = "FYDOC-CASE-23-east-137985-efit-east"
READINGS = "coil_forces_east137985.json"
#: 判据的细丝档：与 `code/wall` 同一个默认，并扫一档确认收敛
NU_SWEEP = (4, 8, 16)


def _wv():
    """The wall/vstab tool carries the card loader and the KEFIT slice — reuse, do not re-write."""
    spec = importlib.util.spec_from_file_location(
        "benchmark_wall_vstab", ROOT / "tools" / "benchmark-wall-vstab.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def readings(case: Path) -> dict:
    from fylite.io import fydoc
    wv = _wv()
    dev = wv.east_card()
    g, a, gsha = wv.kefit_slice(case)
    aturns = np.asarray(a["ccbrsp"], float)[:12]

    def run(nu: int) -> dict:
        rec = fydoc.complete("code/forces", {"settings": {"nu": float(nu), "nv": float(nu)},
                                             "inputs": {"device": dev,
                                                        "discharge": {"fylite:channel_aturns": aturns}}})
        f = {k: float(v["value"]) for k, v in rec["facts"].items()}
        fl = wv._flat_fields(rec["fields"])
        return {"facts": f, "fields": {k: np.asarray(v, float) for k, v in fl.items()},
                "notes": list(rec.get("notes") or [])}

    out = {"kefit_g_sha256": gsha, "channel_aturns_MA_turn": (aturns / 1.0e6).tolist(),
           "filament_sweep": {}, "reference": "no external reference: the analytic anchors are kernel-side unit tests"}
    base = None
    for nu in NU_SWEEP:
        r = run(nu)
        f = r["facts"]
        if nu == 8:
            base = r
        #: ★合力相对最大单件——绝对牛顿数在不同细丝档下会变，比值不该变
        out["filament_sweep"][str(nu)] = {
            "f_z_net_N": f["f_z_net"], "f_z_absmax_N": f["f_z_absmax"],
            "f_z_net_over_absmax": f["f_z_net"] / f["f_z_absmax"] if f["f_z_absmax"] else None,
            "f_r_total_N": f["f_r_total"], "f_r_absmax_N": f["f_r_absmax"],
            "b_surface_max_T": f["b_surface_max"],
            "hoop_outward_count": f["hoop_outward_count"], "energised_count": f["energised_count"]}

    assert base is not None
    fl, f = base["fields"], base["facts"]
    live = np.abs(fl["element_aturns"]) > 0.0
    order = np.argsort(-np.abs(fl["f_z"]))
    out["at_nu_8"] = {
        "n_elements": int(f["n_elements"]), "n_channels": int(f["n_channels"]),
        "notes": base["notes"],
        "worst_elements": [
            {"element": int(i), "r_m": float(fl["element_r"][i]), "z_m": float(fl["element_z"][i]),
             "aturns_MA": float(fl["element_aturns"][i] / 1.0e6),
             "f_r_MN": float(fl["f_r"][i] / 1.0e6), "f_r_hoop_MN": float(fl["f_r_hoop"][i] / 1.0e6),
             "f_z_MN": float(fl["f_z"][i] / 1.0e6),
             "b_surface_T": float(fl["b_surface"][i])}
            for i in order[:6]],
        #: ★★环向项与**净**径向力是两件事，并排放着：环向项按 I^2 走、永远向外；
        #: 来自其余线圈的互吸按 I_a I_b 走，于是弱励磁的外侧线圈被内侧那摞拉进去，
        #: **净**径向力向内。只给净值的读者会把这读成缺陷。
        "hoop_outward_everywhere": bool(np.all(fl["f_r_hoop"][live] > 0.0)),
        "net_f_r_inward": [
            {"element": int(i), "r_m": float(fl["element_r"][i]),
             "aturns_MA": float(fl["element_aturns"][i] / 1.0e6),
             "f_r_MN": float(fl["f_r"][i] / 1.0e6),
             "f_r_hoop_MN": float(fl["f_r_hoop"][i] / 1.0e6)}
            for i in np.flatnonzero(fl["f_r"] < 0.0)],
        "b_surface_T": {"max": float(np.max(fl["b_surface"])), "median": float(np.median(fl["b_surface"]))}}

    #: ★★细丝档的收敛：合力比值该一直在机器精度上；表面场 2026-09-19 起自场是面积分（内核
    #: `surface_field_converged`），剩下的散布只来自其他线圈的细丝离散
    bs = [out["filament_sweep"][str(n)]["b_surface_max_T"] for n in NU_SWEEP]
    out["convergence"] = {
        "f_z_net_over_absmax": [out["filament_sweep"][str(n)]["f_z_net_over_absmax"] for n in NU_SWEEP],
        "b_surface_max_T": bs,
        "b_surface_spread_rel": (max(bs) - min(bs)) / max(bs)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("readings")
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--case", type=Path)
    args = ap.parse_args()
    case = args.case or Path(os.environ["FYDOC_ORACLE"]) / CASE23
    res = readings(case)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / READINGS).write_text(json.dumps(res, indent=1, default=float) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1, default=float)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
