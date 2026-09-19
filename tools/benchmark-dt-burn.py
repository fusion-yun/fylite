"""The DT-burn reading behind `tr-closure-dt-burn-astra` (FR-TR-004): the `fylite` and `compare`
blocks of `docs/benchmark/readings/dt_burn_astra_metrics.json`, regenerated from the public entry.

★2026-09-19: the reading was written by a one-off script (no generator was committed), and the
α-share fix (`E_ALPHA_FRACTION` 0.2013 → 3.52/17.59) moved its α numbers.  The fusion power does
not depend on the share, so this regenerates it to the bit — which is the evidence that this is
the call the reading was taken with.  The `astra` and `profiles` blocks come from ASTRA's table
and the prescribed profiles and are left as they are; `astra` is re-derived and checked.

Subcommand: ``reading``.  Needs the runtime library and CASE-01's corpus.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
READING = ROOT / "docs" / "benchmark" / "readings" / "dt_burn_astra_metrics.json"
CORPUS = pathlib.Path(os.environ.get("FYDOC_ORACLE", ROOT.parent / "fydoc" / "cases")) \
    / "FYDOC-CASE-01-astra" / "corpus" / "iter15ma_astra_burn.csv"
#: the flat-top instant the reading takes
T_S = 1.0


def astra_axis() -> dict:
    rows = list(csv.DictReader(line for line in CORPUS.open() if not line.startswith("#")))
    a = rows[0]
    return {"n_points": len(rows), "ne0_m3": float(a["ne_1e19"]) * 1e19, "te0_keV": float(a["te_kev"]),
            "ti0_keV": float(a["ti_kev"]), "p_alpha0_MW_m3": float(a["p_alpha_mw_m3"])}


def reading() -> dict:
    from fylite.engine import cases
    from fylite.scenario import model as M
    old = json.loads(READING.read_text(encoding="utf-8"))
    ax = astra_axis()
    for k, v in ax.items():
        assert old["astra"][k] == v, (k, old["astra"][k], v)
    args = cases.plan("zerod-iter-15ma")["arguments"]
    r = M.zerod(**args)
    t = np.asarray(r["t"], float)
    i = int(np.argmin(abs(t - T_S)))
    p_fus, p_alpha = float(np.asarray(r["p_fus"])[i]), float(np.asarray(r["p_alpha"])[i])
    share = p_alpha / p_fus
    fy = {"t_s": float(t[i]), "p_fus_MW": p_fus / 1e6, "p_alpha_MW": p_alpha / 1e6,
          "p_inj_MW": float(np.asarray(r["p_inj"])[i]) / 1e6, "alpha_share": share,
          "ne0_m3": float(args["ne_flattop"]), "te0_keV": float(args["te_flattop"]),
          "ti0_keV": float(args["te_flattop"]) * float(args["ti_over_te"]), "n_steps": int(t.size)}
    cmp = dict(old["compare"])
    cmp.update({"alpha_share_vs_q_values": share / (3.52 / 17.59) - 1.0,
                "alpha_share_vs_3p5_over_17p6": share / (3.5 / 17.6) - 1.0,
                "P_alpha_rel_vs_astra_circular": fy["p_alpha_MW"] / old["astra"]["P_alpha_volume_MW_circular"] - 1.0,
                "te0_rel": fy["te0_keV"] / ax["te0_keV"] - 1.0, "ti0_rel": fy["ti0_keV"] / ax["ti0_keV"] - 1.0,
                "ne0_rel": fy["ne0_m3"] / ax["ne0_m3"] - 1.0})
    return {**old, "fylite": fy, "compare": cmp}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_subparsers(dest="cmd", required=True).add_parser("reading")
    ap.parse_args()
    new = reading()
    READING.write_text(json.dumps(new, ensure_ascii=False) + "\n", encoding="utf-8")   #: one line, as it was written
    print("wrote", READING.name, {k: new["compare"][k] for k in ("alpha_share_vs_q_values", "alpha_share_vs_3p5_over_17p6")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
