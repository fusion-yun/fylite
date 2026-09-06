"""线二 · 控制仿真 (S-9) — vstab.

★This is the weakest line, and saying so is part of the line.  What exists
is a STATIC criterion: the rigid n=0 vertical mode's stiffness, its ideal
limit and the resistive-wall growth rate.  What does not exist is the flight
simulator upstream asks for (``S9-FR-CTRL-1`` position feedback and
``S9-FR-CTRL-4`` measurement / actuation delay), and it is deliberately not
stubbed here: a ``flight_simulator()`` that returned zeros would read as a
capability.  :func:`gaps` says what is missing and what each item is waiting
on, so the absence is legible from inside the package.

The physics is the kernel's four stability entries; this module assembles the
plasma filaments, the passive set and the coil state, and reads the regime
off the same quantities the kernel returns.
"""
from __future__ import annotations

import numpy as np

from . import stability
from ..design import _device as _resolve_device
from .. import provenance

__all__ = ["vstab", "gaps"]


def vstab(eq: dict | str, *, coil_aturns: list, device=None,
          passive_groups=("inner_shell",), coarsen: int = 2,
          vessel_scale: float = 1.0, eta_scale: float = 1.0,
          mass: float = 0.0) -> dict:
    """Rigid n=0 vertical stability of a reconstructed equilibrium.

    ``eq`` is an ``fyo:equilibrium`` document (or a g-file at the door),
    ``coil_aturns`` the twelve BRSP channel values.
    ``vessel_scale`` moves the wall toward or away from the axis and
    ``eta_scale`` scales its resistivity — the two discriminators, and the
    reason they are arguments rather than constants is that a stability
    answer that cannot be pushed is an answer nobody can check.

    ★The regime is taken from ``VerticalStability`` (the kernel repository's oracle tree since T-4 第十一刀)
    as it comes — it is read there off the two STIFFNESSES, not off the
    growth rate, because the ideal-unstable regime has no finite gamma to
    read and a classification keyed on gamma would mislabel exactly the case
    that matters most.  Re-deriving it here would be a second classifier to
    keep in step with the first.
    """
    dev = _resolve_device(device)
    #: ★No table directory travels down this line any more.  The machine is
    #: resolved once, further down, by `device.conductor_set` — and while a
    #: path was still being threaded here, defaulting it to the configured
    #: deck made every call look like an explicit override and shut the fyo
    #: document out of this line.
    vs = stability.vertical_mode(
        eq, coil_aturns=np.asarray(coil_aturns, float),
        device=dev, passive_groups=tuple(passive_groups), coarsen=coarsen,
        vessel_scale=vessel_scale, eta_scale=eta_scale, mass=mass)
    gamma = float(vs.growth_rate)
    return {"stiffness": float(vs.stiffness),
            "ideal_stiffness": float(vs.ideal_stiffness),
            "growth_rate": gamma, "regime": vs.regime,
            "margin": float(vs.margin), "stable": bool(vs.stable),
            "growth_time": (1.0 / gamma if np.isfinite(gamma) and gamma > 0
                            else float("nan")),
            "vessel_scale": float(vessel_scale),
            "eta_scale": float(eta_scale),
            "provenance": provenance("vstab", regime=vs.regime)}


def gaps() -> tuple[dict, ...]:
    """What this line does NOT have, and what each item waits on.

    ★Kept as data rather than prose because it is checked: the scenario gate
    asserts that every ``○`` row of FYL-DESIGN-07 §8 on this line appears
    here.  A capability that quietly disappears from the ledger is how an
    unbuilt thing starts reading as a built one.
    """
    return (
        {"fr": "S9-FR-CTRL-1", "what": "位置 / 形状反馈闭环（最小飞行模拟器）",
         "blocked_on": "rust/fylite/src/control.rs 今天只有两行模块注释；"
                       "闭环小信号模型仍只在 python/fylite/control.py"},
        {"fr": "S9-FR-CTRL-4", "what": "测量与致动时延在环",
         "blocked_on": "同上。上游明记 as-built 增益标定是在「无显式时延」"
                       "前提下做的，引用增益值必须携带该前提"},
        {"fr": "S9-FR-EVO-2", "what": "电压驱动的自由边界推进",
         "blocked_on": "fylite_rs_evolve_circuits 已在内核且 Python 已绑定，"
                       "但 model.coupled 驱动的是压强、线圈电流固定——"
                       "这一格是 ◐ 不是 ●"},
    )
