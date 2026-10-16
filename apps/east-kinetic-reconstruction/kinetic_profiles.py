#!/usr/bin/env python3
"""动理学剖面文件（``fylite:KineticProfiles``）：档 P 的另一种压强来源——Tₑ · nₑ · T_i（· v_tor）各自来自自己的诊断、
在自己的坐标上给（README §2.4d）。本脚本只用标准库，把 CSV 列装成这份文件：

    kinetic_profiles.py new  prof.json --source "…" --time 6.3
    kinetic_profiles.py add  prof.json --species te --csv ts.csv --where t_s=6.058272 --coord rz \\
                             --r =1.9 --z Z_mm --z-scale 1e-3 --value Te_eV --sigma err_upper_eV --time 6.058
    kinetic_profiles.py add  prof.json --species ne --csv refl.csv --coord rz --r R_m --z =0.03 \\
                             --value ne_1e19m-3 --scale 1e19 --sigma-rel 0.1 --chords
    kinetic_profiles.py add  prof.json --species ti --csv cvi.csv --coord rho_anchored --rho rho_norm \\
                             --value Ti_keV --scale 1e3 --sigma Ti_err95_keV --sigma-scale 0.5102
    kinetic_profiles.py anchors prof.json --csv anchors.csv --r R_m --z Z_m --rho rho
    kinetic_profiles.py show prof.json

列名照 CSV 表头；``=数`` 是常数列（整条诊断同一 R 或 Z）。单位一律换成 SI：eV · m⁻³ · m/s · m（``--scale`` ·
``--r-scale`` · ``--z-scale``）；σ 同乘 ``--scale`` 再乘 ``--sigma-scale``（95 % 置信区间 → 1σ：1/1.96）。
坐标：``rz``（内核逐遍在当前平衡上映）· ``psin`` · ``sqrt_psin`` · ``rho_tor`` · ``rho_anchored``（别家代码发布的 ρ，
经同一来源的锚点 (R, Z, ρ) 映到本平衡）。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

TYPE = "fylite:KineticProfiles"
SPECIES = ("te", "ne", "ti", "vt")
COORDS = ("rz", "psin", "sqrt_psin", "rho_tor", "rho_anchored")
#: 各物种的 SI 单位（文件里的数都是这个单位）
UNITS = {"te": "eV", "ne": "m^-3", "ti": "eV", "vt": "m/s"}


def read_csv(path: str, where: list[str]) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for w in where or []:
        k, _, v = w.partition("=")
        if not rows or k not in rows[0]:
            raise SystemExit(f"--where {w}：{path} 没有列 {k!r}")
        rows = [r for r in rows if abs(float(r[k]) - float(v)) <= 1e-9 * max(1.0, abs(float(v)))]
    if not rows:
        raise SystemExit(f"{path}：按 --where 筛完一行不剩")
    return rows


def column(rows: list[dict], spec: str | None, scale: float, what: str, path: str) -> list[float] | None:
    """``spec`` = 列名，或 ``=数``（常数列）。"""
    if spec is None:
        return None
    if spec.startswith("="):
        return [float(spec[1:]) * scale] * len(rows)
    if spec not in rows[0]:
        raise SystemExit(f"--{what} {spec}：{path} 的列是 {list(rows[0])}")
    return [float(r[spec]) * scale for r in rows]


def load(path: str) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("@type") != TYPE:
        raise SystemExit(f"{path}：不是 {TYPE}（先 new）")
    return d


def save(path: str, d: dict) -> None:
    Path(path).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_new(a) -> int:
    d = {"@type": TYPE, "version": 1, "shot": a.shot, "time_s": a.time,
         "profiles": {"source": a.source, "ni_over_ne": a.ni_over_ne, "ti_over_te": a.ti_over_te,
                      "ion_mass_amu": a.ion_mass, "species": {}, "anchors": None}}
    save(a.file, d)
    return 0


def cmd_add(a) -> int:
    d = load(a.file)
    rows = read_csv(a.csv, a.where)
    sp = {"coord": a.coord, "value": column(rows, a.value, a.scale, "value", a.csv), "units": UNITS[a.species]}
    if a.coord == "rz":
        if a.r is None or a.z is None:
            raise SystemExit("--coord rz 要 --r 与 --z")
        sp["r"] = column(rows, a.r, a.r_scale, "r", a.csv)
        sp["z"] = column(rows, a.z, a.z_scale, "z", a.csv)
    else:
        if a.rho is None:
            raise SystemExit(f"--coord {a.coord} 要 --rho")
        sp["rho"] = column(rows, a.rho, 1.0, "rho", a.csv)
    if a.sigma is not None:
        sp["sigma"] = column(rows, a.sigma, a.scale * a.sigma_scale, "sigma", a.csv)
    else:
        sp["sigma_rel"] = a.sigma_rel
    if a.chords:
        if a.species != "ne":
            raise SystemExit("--chords 只对 ne（POINT 线密度作 nₑ 拟合的行）")
        sp["chords"] = True
    sp["time_s"] = a.time
    sp["source"] = {"text": a.source, "file": Path(a.csv).name, "where": a.where or []}
    d["profiles"]["species"][a.species] = sp
    save(a.file, d)
    print(f"{a.species}: {len(sp['value'])} 点（{a.coord}）", file=sys.stderr)
    return 0


def cmd_anchors(a) -> int:
    d = load(a.file)
    rows = read_csv(a.csv, a.where)
    an = d["profiles"].get("anchors") or {"r": [], "z": [], "rho": [], "source": []}
    r, z, rho = (column(rows, a.r, a.r_scale, "r", a.csv), column(rows, a.z, a.z_scale, "z", a.csv),
                 column(rows, a.rho, 1.0, "rho", a.csv))
    an["r"] += r
    an["z"] += z
    an["rho"] += rho
    an["source"] = list(an.get("source") or []) + [{"text": a.source, "file": Path(a.csv).name, "n": len(rho)}]
    d["profiles"]["anchors"] = an
    save(a.file, d)
    print(f"锚点：+{len(rho)}，共 {len(an['rho'])}", file=sys.stderr)
    return 0


def cmd_show(a) -> int:
    d = load(a.file)
    p = d["profiles"]
    print(f"#{d.get('shot')} @ {d.get('time_s')} s — {p.get('source')}")
    for k, s in p["species"].items():
        v = s["value"]
        pos = "R,Z" if s["coord"] == "rz" else "rho"
        sig = "sigma" if "sigma" in s else f"sigma_rel {s.get('sigma_rel')}"
        print(f"  {k}: {len(v)} 点 · {s['coord']} ({pos}) · {min(v):.4g}..{max(v):.4g} {s.get('units')} · {sig}"
              f"{' · +POINT' if s.get('chords') else ''} · t {s.get('time_s')}")
    an = p.get("anchors")
    if an:
        print(f"  anchors: {len(an['rho'])} 对 (R, Z, ρ)")
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="新建一份剖面文件")
    n.add_argument("file")
    n.add_argument("--source", required=True, help="这组剖面从哪来（写进文件与结果）")
    n.add_argument("--shot", type=int)
    n.add_argument("--time", type=float, help="所求时刻 [s]")
    n.add_argument("--ni-over-ne", type=float, default=1.0, help="n_i / nₑ（缺省 1，声明；无 Z_eff 剖面）")
    n.add_argument("--ti-over-te", type=float, default=1.0, help="没给 T_i 时 T_i = 它 × Tₑ（缺省 1，声明）")
    n.add_argument("--ion-mass", type=float, default=2.014, help="主离子质量 [amu]（M² 用；缺省氘）")
    for name, h in (("add", "加一个物种（同名覆盖）"), ("anchors", "加锚点 (R, Z, ρ)：rho_anchored 的物种经它们映到本平衡")):
        s = sub.add_parser(name, help=h)
        s.add_argument("file")
        s.add_argument("--csv", required=True)
        s.add_argument("--where", action="append", metavar="COL=V", help="只取这一列等于 V 的行（可重复）")
        s.add_argument("--r", help="R 列（或 =常数）")
        s.add_argument("--z", help="Z 列（或 =常数）")
        s.add_argument("--rho", help="ρ 列")
        s.add_argument("--r-scale", type=float, default=1.0, help="R 乘它成 m")
        s.add_argument("--z-scale", type=float, default=1.0, help="Z 乘它成 m")
        s.add_argument("--source", default=None, help="这一组从哪来")
        if name == "add":
            s.add_argument("--species", required=True, choices=SPECIES)
            s.add_argument("--coord", required=True, choices=COORDS)
            s.add_argument("--value", required=True, help="值的列")
            s.add_argument("--scale", type=float, default=1.0, help="值（与 σ）乘它成 SI")
            s.add_argument("--sigma", help="σ 的列（绝对值；乘 --scale 与 --sigma-scale）")
            s.add_argument("--sigma-scale", type=float, default=1.0, help="σ 再乘它（95 %% CI → 1σ：0.5102）")
            s.add_argument("--sigma-rel", type=float, default=0.1, help="没有 σ 列时：σ = 它 × |值|（缺省 0.1，声明）")
            s.add_argument("--chords", action="store_true", help="nₑ：POINT 线密度也作拟合的行（档 P 叠在 K 上时）")
            s.add_argument("--time", type=float, help="这一诊断的时刻 [s]（与所求时刻不同时写上）")
    s = sub.add_parser("show", help="看一份剖面文件")
    s.add_argument("file")
    return ap


def main(argv=None) -> int:
    a = parser().parse_args(argv)
    if a.cmd == "anchors" and (a.r is None or a.z is None or a.rho is None):
        raise SystemExit("anchors 要 --r --z --rho")
    return {"new": cmd_new, "add": cmd_add, "anchors": cmd_anchors, "show": cmd_show}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
