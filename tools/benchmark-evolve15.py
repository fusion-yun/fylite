"""The 1.5D evolve readings behind `tr-closure-15d-source-switches` (FR-TR-004) and
`tr-pedestal-eped-feedback` (FR-TR-009), regenerated from the public entry.

★2026-09-19: these readings were written by one-off scripts (no generator was committed), and the
α-fraction fix moved every α power in them by −0.59 %.  This is that generator, so a reading can
be reproduced instead of trusted.

Subcommand: ``readings --out DIR``.  Needs the runtime library and the `evolve-iter-15ma` case.
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: the variants the switch sweep opens one at a time on top of the case's baseline
SWITCHES = {"pedestal": {"pedestal": True}, "current": {"current": True}, "sawtooth": {"sawtooth": True},
            "density": {"density": True}, "dt_target": {"dt_target": 0.02}}
SERIES = ("p_alpha", "p_aux", "p_aux_beam", "p_aux_lh", "p_ohm", "p_rad", "j_bs", "j_cd", "j_lh", "t_ped",
          "balance", "te", "ti", "ne", "q", "psi", "v_loop_used", "ip_psi", "chi_neo", "zeff", "ni")
SCALARS = ("ped_extrapolation", "saw_count", "settled", "dt_fraction_used", "balance_worst", "te_axis")
#: ★FR-TR-004: the driven currents need their SOURCES — the switch sweep's `current` variant opens the
#: channel but feeds it nothing, which is why all three read zero there
DRIVEN = {"bootstrap": {"current": True, "bootstrap": True},
          "i_cd_1MA": {"current": True, "i_cd": 1.0e6},
          "i_cd_2MA": {"current": True, "i_cd": 2.0e6}}
#: ★FR-TR-009: the pedestal feedback marched long enough to settle, with the alpha heating OFF —
#: with it on (and a constant chi) this case runs away thermally, so there is no fixed point to reach
PEDESTAL_MARCH = {"pedestal": True, "alpha": False, "dt": 0.2, "n_steps": 1000}


def _last(v) -> float:
    return float(np.ravel(np.asarray(v, float))[-1])


def _absmax(v) -> float:
    a = np.ravel(np.asarray(v, float))
    return float(np.max(np.abs(a))) if a.size else 0.0


def _opt(v) -> float | None:
    """A counter the march may not report (absent, or an empty array): None, not a made-up zero."""
    a = np.ravel(np.asarray(v, float)) if v is not None else np.array([])
    return float(a[-1]) if a.size else None


def _final(v) -> list[float]:
    """The last profile: `evolve` returns the final one (1-D), a trace would be (t, rho)."""
    a = np.asarray(v, float)
    return [float(x) for x in (a[-1] if a.ndim > 1 else a)]


def base_case() -> dict:
    from fylite.engine import cases
    return dict(cases.plan("evolve-iter-15ma")["arguments"])


def summary(r: dict) -> dict:
    out = {k: {"last": _last(r[k]), "absmax": _absmax(r[k])} for k in SERIES if k in r}
    for k in SCALARS:
        if k in r:
            out[k] = _absmax(r[k]) if k == "balance_worst" else _last(r[k])
    return out


def switch_sweep(M, base: dict) -> dict:
    runs = {"baseline": M.evolve(**base)}
    variants = {"baseline": summary(runs["baseline"])}
    for name, ov in SWITCHES.items():
        try:
            runs[name] = M.evolve(**{**base, **ov})
            variants[name] = summary(runs[name])
        except Exception as e:  # noqa: BLE001 — a refusal is itself the reading
            variants[name] = {"why": f"{type(e).__name__}: {e}"}
    b = variants["baseline"]
    changed = {}
    for name, v in variants.items():
        if name == "baseline" or "why" in v:
            continue
        moved = {}
        for k in SERIES + ("te_axis", "balance_worst"):
            if k not in v or k not in b:
                continue
            bb, vv = (b[k]["absmax"], v[k]["absmax"]) if isinstance(b[k], dict) else (b[k], v[k])
            if vv != bb:
                moved[k] = {"baseline": bb, "variant": vv, "rel": (vv - bb) / max(abs(bb), 1e-300)}
        changed[name] = moved
    return {"what": "1.5D 演化：逐个开关是否真的进了装配（源项 / 台基 / 驱动 / 锯齿 / 加料 / DT）",
            "baseline_controls": {k: base.get(k) for k in ("pedestal", "current", "ipctl", "sawtooth", "heat", "closure",
                                                           "density", "dt_target", "impurity", "brem", "quasi")},
            "variants": variants, "changed_vs_baseline": changed}


def sources_pedestal(M, base: dict) -> dict:
    r = M.evolve(**base)
    ser = lambda k: {"last": _last(r[k]), "max": _absmax(r[k]), "n": int(np.size(r[k]))}  # noqa: E731
    return {"what": "1.5D 演化（`code/evolve`，algo evolve-iter-15ma）：源项逐项、台基、能量平衡",
            "grid": {"n_rho": int(base["n_rho"]), "n_steps": int(base["n_steps"]), "t_end_s": _last(r["t"])},
            "sources_W": {k: ser(k) for k in ("p_alpha", "p_aux", "p_aux_beam", "p_aux_lh", "p_ohm", "p_rad")},
            "currents_A": {k: ser(k) for k in ("j_bs", "j_cd", "j_lh")},
            "pedestal": {"t_ped": {"last": _last(r["t_ped"]), "min": float(np.min(r["t_ped"])), "max": _absmax(r["t_ped"])},
                         "ped_extrapolation": _last(r["ped_extrapolation"])},
            "balance": {"balance": {"last": _last(r["balance"]), "worst": _absmax(r["balance"])},
                        "balance_worst": _absmax(r["balance_worst"]), "settled": _last(r["settled"]),
                        "rounds": _opt(r.get("rounds")), "steps": _last(r["steps"]), "free_solves": _opt(r.get("free_solves")),
                        "saw_count": _last(r["saw_count"]),
                        "saw_refused": {"last": _last(r["saw_refused"]), "worst": _absmax(r["saw_refused"])},
                        "dt_fraction_used": _last(r["dt_fraction_used"]), "dt_capped": _last(r["dt_capped"]),
                        "turb_evals": _opt(r.get("turb_evals"))},
            "profiles": {"rho": [float(v) for v in r["rho"]], "te_eV": _final(r["te"]),
                         "ti_eV": _final(r["ti"]), "ne_m3": _final(r["ne"]),
                         "q": _final(r["q"]), "te_init_eV": _final(r["te_init"])},
            "notes": list(r.get("notes") or [])}


def driven_currents(M, base: dict) -> dict:
    """Each driven-current channel with its source switched on; the prescribed CD's deposition integral."""
    out = {}
    for name, ov in DRIVEN.items():
        r = M.evolve(**{**base, **ov})
        rho, vp = np.asarray(r["rho"], float), np.asarray(r["vprime"], float)
        row = {k: _absmax(r[k]) for k in ("j_bs", "j_cd", "j_lh")}
        row["balance_worst"] = _absmax(r["balance_worst"])
        if "i_cd" in ov:
            j = np.asarray(r["j_cd"], float)
            j = j[-1] if j.ndim > 1 else j
            #: I = ∫ j dA,  dA = V'(ρ) dρ / (2π R0) — the same area element the kernel deposits on
            got = float(np.trapezoid(j * vp / (2.0 * np.pi * float(base["r0"])), rho))
            row["i_cd_requested_A"] = float(ov["i_cd"])
            row["i_cd_integrated_A"] = got
            row["i_cd_rel_error"] = got / float(ov["i_cd"]) - 1.0
        out[name] = row
    return {"what": "驱动电流三道各开自己的源：自举（bootstrap）· 给定 CD（i_cd，沉积积分闭合）；"
                    "束与 LH 的执行器由内核仓 tests/test_evolve_executors_code.py 在 EAST g-file 上逐位对上 code/beam / code/wave",
            "runs": out}


def pedestal_feedback(M, base: dict) -> dict:
    """The EPED1-NN pedestal inside the march, marched until it settles (alpha off)."""
    out = {}
    for alpha in (False, True):
        r = M.evolve(**{**base, **{**PEDESTAL_MARCH, "alpha": alpha}})
        tp = np.asarray(r["t_ped"], float)
        step = np.abs(np.diff(tp)) / tp[1:]
        out["alpha_off" if not alpha else "alpha_on"] = {
            "t_end_s": _last(r["t"]), "t_ped_first_eV": float(tp[0]), "t_ped_mid_eV": float(tp[len(tp) // 2]),
            "t_ped_last_eV": float(tp[-1]), "rel_step_mid": float(step[len(step) // 2]), "rel_step_last": float(step[-1]),
            "te_axis_last_eV": _last(r["te_axis"]), "ped_extrapolation": _last(r["ped_extrapolation"])}
    return {"what": "台基反馈（EPED1-NN 每步定下一步的边界，滞后一步）推到收敛", "march": PEDESTAL_MARCH, "runs": out}


def readings() -> dict[str, dict]:
    from fylite.scenario import model as M
    base = base_case()
    return {"evolve15_switch_sweep.json": switch_sweep(M, base),
            "evolve15_sources_pedestal.json": sources_pedestal(M, base),
            "evolve15_driven_currents.json": driven_currents(M, base),
            "pedestal_eped_feedback.json": pedestal_feedback(M, base)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("readings")
    a.add_argument("--out", type=pathlib.Path, default=ROOT / "docs" / "benchmark" / "readings")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, res in readings().items():
        (args.out / name).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float) + "\n", encoding="utf-8")
        print("wrote", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
