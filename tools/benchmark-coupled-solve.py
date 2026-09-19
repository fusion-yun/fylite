"""The reading behind `tr-paradigm-coupled-block-adr` (FR-TR-006): the coupled whole-system solve
(the default since the user's 2026-09-19 ruling) against the old sequential pair, on the same case.

`evolve-iter-15ma` run twice through the public entry — coupled (default) and ``sequential=True`` —
with each step's coupling passes and the change its last pass made.  The kernel-side numbers (the
block solver against a dense solve, the implicit exchange's books and relaxation, the fixed-point
residual of a coupled step) are pinned by the kernel tests named in the reading; they are copied here
as the record's figures, not recomputed.

Subcommand: ``reading``.  Needs the runtime library.
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
READING = ROOT / "docs" / "benchmark" / "readings" / "coupled_block_solve.json"

#: the kernel tests' own `[register]` figures (`cargo test -- --nocapture`), 2026-09-19
KERNEL = {
    "block_solver": {"test": "transport::tests::the_block_thomas_solve_is_the_dense_solve_and_reduces_to_thomas",
                     "vs_dense_band": 1e-13, "k1_is_thomas_bitwise": True},
    "no_exchange_is_sequential": {"test": "transport::tests::the_implicit_pair_without_exchange_is_the_sequential_pair",
                                  "bitwise": True},
    "implicit_exchange": {"test": "transport::tests::the_implicit_exchange_closes_the_books_and_needs_no_dt_cap",
                          "books_worst": 8.99e-16, "nu_per_s": 1e3, "dt_s": 1e-2, "dt_over_explicit_cap": 40.0,
                          "gap_before_eV": 2000.0, "gap_after_eV": 95.238, "backward_euler_gap_eV": 2000.0 / 21.0,
                          "explicit_same_dt_flips_sign": True},
    "fixed_point": {"test": "transport::tests::the_coupled_step_is_the_implicit_solution_of_every_channel",
                    "passes": 15, "last_change": 9.9e-13, "residual_coupled": 1.7e-13,
                    "residual_sequential_two_passes": 2.2e-2},
}


def summary(r: dict) -> dict:
    cp = np.asarray(r["coupling_passes"], float)
    cd = np.asarray(r["coupling_delta"], float)
    return {"p_alpha_last_W": float(np.ravel(r["p_alpha"])[-1]),
            "te_axis_last_eV": float(np.ravel(r["te_axis"])[-1]),
            "balance_worst": float(r["balance_worst"]), "steps": int(r["steps"]),
            "passes_min": int(cp.min()), "passes_median": float(np.median(cp)), "passes_max": int(cp.max()),
            "last_change_max": float(cd.max()), "steps_unconverged": int((cd > 1e-9).sum())}


def reading() -> dict:
    from fylite.engine import cases
    from fylite.scenario import model as M
    base = dict(cases.plan("evolve-iter-15ma")["arguments"])
    coupled = summary(M.evolve(**base))
    sequential = summary(M.evolve(**base, sequential=True))
    return {"what": "FR-TR-006：耦合整体求解（缺省）对旧的顺序对，同一算例；内核侧的四个数由所列内核测试钉住",
            "case": "evolve-iter-15ma",
            "coupled": coupled, "sequential": sequential,
            "coupled_vs_sequential": {
                "p_alpha_rel": coupled["p_alpha_last_W"] / sequential["p_alpha_last_W"] - 1.0,
                "te_axis_rel": coupled["te_axis_last_eV"] / sequential["te_axis_last_eV"] - 1.0},
            "kernel": KERNEL}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_subparsers(dest="cmd", required=True).add_parser("reading")
    ap.parse_args()
    r = reading()
    READING.write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", READING.name, json.dumps(r["coupled_vs_sequential"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
