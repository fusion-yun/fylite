"""MHD stability readings shaped as DD ``mhd_linear`` records (FR-EQ-026).

Every kernel-side stability reading — the L0 external-kink q limit, the L1
ballooning boundary, the surface-current oracle, an empirical scaling, the
n = 0 vertical mode — leaves fylite through this one module, so the
discipline below lives in one place and the physics modules stay free of any
DD shape.

The rules this module enforces, each as a refusal rather than a comment:

* **an energy-principle verdict is not a growth rate.**  L0 / L1 / the oracle
  deliver marginal stability and critical parameters, not gamma; their
  ``growthrate`` stays *absent*.  0 would read as neutrally stable.
  ``assemble_time_slice`` refuses an energy-principle ``kind`` that arrives
  with a finite ``growthrate`` — one record cannot show that mix-up, the
  assembly can.
* **our judged quantities stay out of DD physics fields.**  critical q*,
  alpha_c, beta/epsilon, stable-or-not ride in ``code.parameters``.
* **an empirical scaling is never dressed as a computation.**  It fills no
  DD field at all, only an information row carrying its ``source``.
* **the caveats travel with the record.**  L0 is a *q limit* and must not be
  called a beta limit; the surface-current oracle is optimistic and its q* is
  the cylindrical-equivalent safety factor.
* **ballooning has no single n**: ``n_phi`` is left empty unless given.
* **``ideal_flag`` is never guessed**: the vertical mode must say it.

Pure stdlib: only ``json`` and ``math`` are imported (checked on the syntax
tree by the tests, not by grepping this text).
"""
from __future__ import annotations

import json
import math

#: the DD 4.1.1 ``time_slice/toroidal_mode`` leaves a record may fill
DD_MODE_FIELDS = frozenset({"perturbation_type", "n_phi", "m_pol_dominant", "growthrate", "frequency"})
#: kinds that come from the energy principle — never a growth rate
ENERGY_PRINCIPLE_KINDS = frozenset({"q_limit", "ballooning_boundary", "surface_current_oracle"})


class RecordRefused(ValueError):
    """A reading that would break one of the rules above."""


def _source(source: str) -> str:
    if not isinstance(source, str) or not source.strip():
        raise RecordRefused("a record without a source is refused — name the book, section and equation")
    return source


def _finite(name: str, value: float) -> float:
    v = float(value)
    if not math.isfinite(v):
        raise RecordRefused(f"{name} = {value!r} is not finite")
    return v


def kink_record(m: int, n: int, q_lower: float, q_upper: float, wall_over_a: float, *, source: str) -> dict:
    """L0: the external-kink unstable band ``q_lower < q_a < q_upper`` — a **q limit**."""
    return {
        "kind": "q_limit",
        "mode": {"perturbation_type": {"name": "external_kink", "index": 0,
                                       "description": "ideal external kink, cylinder (L0)"},
                 "n_phi": int(n), "m_pol_dominant": float(m)},
        "parameters": {"q_lower": _finite("q_lower", q_lower), "q_upper": _finite("q_upper", q_upper),
                       "wall_over_a": float(wall_over_a), "source": _source(source),
                       "caveat": "q limit, not a beta limit"},
    }


def ballooning_record(shear: float, alpha_c: float, *, source: str, n_phi: int | None = None) -> dict:
    """L1: the s-alpha first-stability boundary.  ``n_phi`` stays empty (n >> 1 limit) unless given."""
    mode = {"perturbation_type": {"name": "ballooning", "index": 0,
                                  "description": "ideal ballooning, s-alpha, n >> 1 (L1)"}}
    if n_phi is not None:
        if not isinstance(n_phi, int) or isinstance(n_phi, bool) or n_phi <= 0:
            raise RecordRefused(f"n_phi = {n_phi!r}: a ballooning record takes a positive integer or nothing")
        mode["n_phi"] = n_phi
    return {"kind": "ballooning_boundary", "mode": mode,
            "parameters": {"shear": _finite("shear", shear), "alpha_c": _finite("alpha_c", alpha_c),
                           "source": _source(source)}}


def surface_current_record(q_crit: float, beta_over_eps_max: float, *, source: str) -> dict:
    """The analytic surface-current beta limit — an **oracle**, optimistic, with a cylindrical-equivalent q*."""
    return {"kind": "surface_current_oracle",
            "mode": {"perturbation_type": {"name": "ballooning_kink", "index": 0,
                                           "description": "surface-current model oracle"}, "n_phi": 1},
            "parameters": {"q_star_crit": _finite("q_star_crit", q_crit),
                           "beta_over_eps_max": _finite("beta_over_eps_max", beta_over_eps_max),
                           "source": _source(source),
                           "caveat": ["the model's numerical coefficient is optimistic (its own source says so)",
                                      "q* is the cylindrical-equivalent safety factor, not q_a or q95"]}}


def scaling_law_record(name: str, value: float, *, source: str) -> dict:
    """An empirical scaling (e.g. a Troyon-type beta_N): an information row, **no** DD computed field."""
    return {"kind": "scaling_law", "mode": None,
            "parameters": {"name": str(name), "value": _finite(name, value), "source": _source(source),
                           "caveat": "empirical scaling, not a computation"}}


def vertical_mode_record(growthrate: float, *, ideal_flag: int, regime: str) -> dict:
    """The n = 0 vertical mode.  ``ideal_flag`` is keyword-only with no default; a resistive-wall mode must say 0."""
    if ideal_flag not in (0, 1) or isinstance(ideal_flag, bool):
        raise RecordRefused(f"ideal_flag = {ideal_flag!r}: say 0 or 1 explicitly")
    if regime == "resistive_wall" and ideal_flag != 0:
        raise RecordRefused("a resistive-wall vertical mode is not ideal: ideal_flag must be 0")
    return {"kind": "vertical_mode", "ideal_flag": ideal_flag,
            "mode": {"perturbation_type": {"name": "vertical", "index": 0, "description": f"n = 0 rigid, {regime}"},
                     "n_phi": 0, "growthrate": _finite("growthrate", growthrate)},
            "parameters": {"regime": regime}}


def assemble_time_slice(records: list[dict], time: float) -> dict:
    """One ``time_slice`` plus the IDS-level ``code.parameters`` that carries our judged quantities."""
    modes, params, flags = [], [], set()
    for i, rec in enumerate(records):
        kind = rec.get("kind")
        mode = rec.get("mode")
        if mode is not None:
            extra = set(mode) - DD_MODE_FIELDS
            if extra:
                raise RecordRefused(f"record {i} ({kind}) writes {sorted(extra)} — not a DD toroidal_mode field")
            gr = mode.get("growthrate")
            if kind in ENERGY_PRINCIPLE_KINDS and gr is not None:
                raise RecordRefused(f"record {i}: an energy-principle kind ({kind}) carries growthrate = {gr!r}")
            modes.append(mode)
        elif kind != "scaling_law":
            raise RecordRefused(f"record {i} ({kind}) has no mode")
        if "ideal_flag" in rec:
            flags.add(rec["ideal_flag"])
        params.append({"kind": kind, **rec.get("parameters", {})})
    out = {"time_slice": [{"time": _finite("time", time), "toroidal_mode": modes}],
           "code": {"name": "fylite", "parameters": json.dumps(params, ensure_ascii=False)}}
    if len(flags) == 1:
        out["ideal_flag"] = flags.pop()
    elif len(flags) > 1:
        raise RecordRefused("records disagree on ideal_flag; split them into separate IDSs")
    return out
