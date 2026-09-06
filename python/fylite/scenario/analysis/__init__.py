"""线四 · 实验分析 / 反演 (S-8) — reconstruction · profit.

The middle of this line is connected and both ends are short.  What exists:
a magnetic reconstruction row that a kinetic pressure constraint can enter,
and a profile fit that produces that constraint.  What does not: an entry
for real shot data beyond the bundled case, and the chord-integral family of
forward operators.  :func:`gaps` says so, in the same form the control line
uses.

★The one sentence the reconstruction tool must keep saying: **magnetics
alone do not constrain the internal profiles.**  The kinetic constraint is
what makes the solution determinate, and a reconstruction run without it is
not a weaker version of the same answer — it is an answer to a different,
under-determined question.
"""
from __future__ import annotations

import numpy as np

from . import recon_rs
from .. import provenance

__all__ = ["reconstruction", "profit", "gaps"]

#: The marker a fitted profile carries when it came out of a reconstruction
#: rather than out of a measurement.  ★It exists so a reconstruction's own
#: pressure cannot be fed back in as though it were data — the one loop that
#: would make a fit look like a confirmation of itself.
DERIVED = "derived-from-reconstruction"


def reconstruction(meas: dict, *, npp: int = 1,
                   nff: int = 2, pressure=None, probes: bool = True,
                   probe_weights=None, probe_weight_scale: float = 1.0,
                   zc_anchor: float | None = None,
                   rc_anchor: float | None = None, **kw) -> dict:
    """One equilibrium reconstruction from measurements.

    ``meas`` is the flat measurement dict (``plasma``, ``brsp``, ``coils``,
    optionally ``expmp2``/``fwtmp2``).  ``pressure`` is the kinetic tier:
    ``{"x": psi_N, "p": [Pa], "sigma_frac": 0.05}`` — or the ``profit``
    result, whose provenance is then checked.

    ★A profile that came out of a reconstruction is REFUSED here rather than
    accepted as a measurement.  It is the one input that would make the fit
    a confirmation of itself, and refusing it is cheaper than explaining
    afterwards why chi² improved.
    """
    kwargs = dict(kw)
    if pressure is not None:
        prov = (pressure.get("provenance") or {}) if isinstance(pressure, dict) \
            else {}
        if prov.get("source") == DERIVED:
            raise ValueError(
                "this pressure profile came out of a reconstruction "
                f"({DERIVED}); feeding it back in as a measurement would "
                "make the fit a confirmation of itself")
        meas = dict(meas)
        meas["pressure"] = np.asarray(pressure["p"], float)
        kwargs["pressure_x"] = np.asarray(pressure["x"], float)
        if "sigma_frac" in pressure:
            kwargs["pressure_sigma_frac"] = float(pressure["sigma_frac"])
    res = recon_rs.reconstruct(meas, npp=npp, nff=nff,
                               probes=probes, probe_weights=probe_weights,
                               probe_weight_scale=probe_weight_scale,
                               zc_anchor=zc_anchor, rc_anchor=rc_anchor,
                               **kwargs)
    out = dict(res)
    out["kinetic"] = pressure is not None
    out["provenance"] = provenance(
        "reconstruction", kinetic=pressure is not None,
        basis={"npp": int(npp), "nff": int(nff)},
        note=("magnetics only — the internal profiles are not constrained "
              "by these data" if pressure is None else
              "magnetics + kinetic pressure rows"))
    return out


def _profit_provenance(*, order: int) -> dict:
    """The D-2 statement for a capability that is NOT a registered tool.

    ★`profit` was a tool; the profile-fitting PAGE retired on 2026-08-19
    (FYL-DESIGN-07 §8, `S8-FR-OP-4` ◐ → —), and `scenario.TOOLS` is the set
    the browser and Python share.  The fit itself did not go anywhere — the
    kernel does it and the reconstruction still accepts its product as a
    pressure profile — so the function stays and says, in the result it
    hands back, exactly what it is now: a Python-side fit that no longer
    claims a coverage row.  Silently reusing a retired tool's provenance
    would put a withdrawn claim on every fit.
    """
    from ... import kernel
    return {"tool": "profit", "lines": (), "fr": (),
            "scope": "剖面拟合：移位 Legendre 基 + GCV 定阶",
            "caveat": "GCV 只度量样本内；外推段无约束——拟合最常被读的地方"
                      "恰是它最不被约束的地方。"
                      "★浏览器侧的拟合页已退役（S8-FR-OP-4 记「明确不做」）："
                      "这是 Python 侧能力，不再是一条覆盖行",
            "kernel_abi": kernel.ABI_VERSION,
            "order": order, "basis": "shifted-Legendre",
            "gcv": "in-sample only"}


def profit(x, y, *, sigma=None, sigma_frac: float = 0.05,
           max_order: int = 6, evaluate_at=None) -> dict:
    """Fit a profile against its own error bars, with GCV order selection.

    ``sigma`` may be given per point; otherwise ``sigma_frac`` of each value
    is used, floored so a zero reading does not claim infinite weight.

    ★Two things the result says out loud, because both have burned this
    repository before: the GCV score measures IN-SAMPLE prediction only —
    it is silent about the extrapolated edge, where a profile fit is most
    often read — and the basis is shifted Legendre, not ``(1-x²)^k``, whose
    near-collinear columns square the condition number of the normal
    equations and put two "identical" fits 1e-3 apart.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if sigma is None:
        sig = np.maximum(np.abs(y) * float(sigma_frac),
                         float(sigma_frac) * max(np.max(np.abs(y)), 1e-30) * 1e-3)
    else:
        sig = np.asarray(sigma, float)
    xe = np.asarray(evaluate_at, float) if evaluate_at is not None else x
    #: ★T-4 第十三刀 (2026-09-06): the fit is `code/profile_fit`'s — the same
    #: GCV sweep and the same polynomial the profile bar's page gets; the
    #: reader's own points go in as `fylite:fit_eval_x` and come back as `eval`.
    #: The flat `profile_fit` / `profile_sample` entries are oracle-only now.
    from ...io import fydoc
    rec = fydoc.complete("code/profile_fit", {
        "settings": {"max_order": float(max_order), "n_curve": 2.0},
        "inputs": {"discharge": {"fylite:fit_x": x, "fylite:fit_y": y,
                                 "fylite:fit_sigma": sig, "fylite:fit_eval_x": xe}}})
    arr = lambda k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    fact = lambda k: rec["facts"][k]["value"]  # noqa: E731
    order = int(fact("order"))
    out = {"x": x, "y": y, "sigma": sig,
           "coef": arr("coef"), "order": order,
           "gcv_sweep": arr("gcv_sweep"), "rss": float(fact("rss")),
           "chi2_per_dof": float(fact("chi2_per_dof")),
           "x_eval": xe, "fit": arr("eval"),
           "extrapolated": bool(np.any(xe > x.max()) or np.any(xe < x.min())),
           "provenance": _profit_provenance(order=order)}
    return out


def gaps() -> tuple[dict, ...]:
    """What this line does NOT have, and what each item waits on."""
    return (
        {"fr": "S8-FR-OP-3", "what": "弦积分族正向算子（干涉 / SXR / 辐射热计）",
         "blocked_on": "属数据面而非算法面：每一支都要视线几何与该诊断的定标"
                       "数据，在有真数据要进来之前建它是空转（FYL-DESIGN-04 §6.6）"},
        {"fr": "S8-FR-INF-1", "what": "可换推断引擎",
         "blocked_on": "架构契约（D-3）：在本仓实现它只会得到一个没有第二个"
                       "实现的抽象层"},
        {"fr": "S8-FR-OP-2", "what": "磁族正向的其余分支（MSE / POINT 偏振仪）",
         "blocked_on": "今天只有磁通环与探针两支——这一格是 ◐"},
        #: ★`S8-FR-OP-4` 不在这里：它已由 ◐ 改记「明确不做」（RETIRED,
        #: FYL-DESIGN-07 §8）。gaps() 说的是**打算建而没建**的，把一条已经
        #: 裁掉的需求留在这里，读起来就成了「还欠着」。
    )
