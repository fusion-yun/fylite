"""线一 · 放电设计 (S-11 / S-10) — discharge · breakdown · feasible.

The inner problem is an equilibrium inverse: given a shape, find the coil
currents.  The outer problem is a scan: many cheap static solves and one
feasibility picture.  ★What the outer layer owes the user is not a verdict
but an ATTRIBUTION — upstream writes "locatable" as a MUST for a reason: an
infeasible answer that does not say which limit stopped it leaves nothing to
do except give up.

Nothing here computes physics.  The field of a conductor, the least-squares
solves, the Grad-Shafranov solve and the shape metrics of a boundary are all
the kernel's (FYL-DESIGN-08 D-4′); this module decides which points to ask
about and what to do with the answers.
"""
from __future__ import annotations

import numpy as np

from ... import kernel as K
from . import pulse
from ... import device as _device_mod
from .. import provenance

__all__ = ["target_boundary", "start_state", "discharge",
           "breakdown", "feasible", "loop_voltage"]

#: ★The device description is CONFIGURATION, not package data (see
#: :mod:`fylite.device`): this distribution ships no machine description.
#: Every entry point below resolves it WHEN THE CALL HAPPENS, so importing
#: this module — and using every tool that needs no machine — works with
#: nothing configured.
#:
#: ★★They no longer take a ``table_dir``.  It named the Green-table
#: directory, the last of which was read out of the reconstruction path
#: (``rfcoil.ddd``); on this line it had ALREADY stopped being read when the
#: geometry became the document's, so what it did here was advertise a
#: second place the machine could come from while silently ignoring it.
#: ``device=`` stays: that is a device DOCUMENT a caller already holds — an
#: object, not a path to a competing description.


def _conductors():
    """The machine's conductors for a call — the document's, always.

    ★★It used to take a deck path and pass ``None`` THROUGH rather than
    resolve it to ``device.data_dir()``, because an eagerly-resolved default
    is indistinguishable from an explicit override: with a path always
    arriving, :func:`fylite.device.conductor_geometry`'s "the fyo document
    wins when it carries rectangles" never fired, and a machine edited in the
    browser and exported was silently read from its deck instead.  The
    parameter is gone now, which is the same guarantee with nothing left to
    get wrong.
    """
    return _device_mod.conductor_set()


def _device(device=None):
    if device is not None:
        return device
    from ... import device
    return device.document()


def target_boundary(*, r0: float, a: float, kappa: float = 1.0,
                    delta_upper: float = 0.0, delta_lower: float = 0.0,
                    z0: float = 0.0, n: int = 24) -> np.ndarray:
    """The boundary the user is ASKING for, as ``(n, 2)`` points.

    ★A specification, not a model — but that is a statement about what the
    NUMBERS MEAN, not about who computes them.  DE-COMP-02 asks only whether
    a quantity has a second host, and this parametrisation had THREE: this
    function, ``surfaces::miller_boundary``, and a hand-written
    ``FyPhys.millerBoundary`` in the browser.  Calling the output a
    specification rather than a prediction does not make theta -> (R, Z) a
    different map.  The kernel's now.

    Triangularity is per half — a single delta cannot describe most diverted
    shapes, and averaging the two draws a boundary the machine does not
    have.
    """
    return K.miller_boundary(r0=r0, a=a, kappa=kappa,
                                 delta_upper=delta_upper,
                                 delta_lower=delta_lower, z0=z0, n=n)


#: The ridge anneal, stiff -> loose: the first passes stay near the starting
#: machine state, the last ones are free enough to reach the target.  ★These
#: are the browser page's own numbers (``app/assets/scenario-design.js``), not
#: fresh ones — the schedule is a tuned property of this problem, and a
#: second set of constants would make the two hosts two different searches.
ANNEAL_HI, ANNEAL_LO, ANNEAL_PASSES, ANNEAL_GAMMA = 0.10, 0.005, 8, 0.4


def anneal_schedule(passes: int = ANNEAL_PASSES) -> tuple[float, ...]:
    """Geometric ridge schedule from :data:`ANNEAL_HI` to :data:`ANNEAL_LO`."""
    n = max(int(passes), 1)
    return tuple(ANNEAL_HI * (ANNEAL_LO / ANNEAL_HI) ** (i / max(1, n - 1))
                 for i in range(n))


def _start_settings(target: dict, ip: float, *, n_points: int, xpoint, x_weight: float) -> dict:
    """The plan's scalar settings for `code/discharge` — the target, the current,
    the point count, and the null when one is asked for."""
    s = {"r0": float(target["r0"]), "a": float(target["a"]),
         "kappa": float(target.get("kappa", 1.0)),
         "delta_upper": float(target.get("delta_upper", 0.0)),
         "delta_lower": float(target.get("delta_lower", 0.0)),
         "z0": float(target.get("z0", 0.0)),
         "ip": float(ip), "n_points": float(n_points),
         #: Python's response quadrature was 3 x 3 where the page's is 4 x 4;
         #: the kernel takes one and this face keeps its own number, so a
         #: design made here reproduces the one made here before the move
         "nu": 3.0}
    if x_weight > 0.0 and xpoint is not None:
        s.update(x_r=float(xpoint[0]), x_z=float(xpoint[1]), x_weight=float(x_weight))
    return s


def _complete(settings: dict, discharge: dict, *, device=None) -> dict:
    from ...io import fydoc
    inputs = {"device": _device(device)}
    if discharge:
        inputs["discharge"] = discharge
    return fydoc.complete("code/discharge", {"settings": settings, "inputs": inputs})


def _fact(rec: dict, key: str) -> float:
    return float(rec["facts"][key]["value"])


def _arr(rec: dict, key: str) -> np.ndarray:
    return np.asarray(rec["fields"][key]["data"], float)


def _start_of(rec: dict) -> dict:
    """The start design as :func:`start_state` reports it, read off the record."""
    flags = _arr(rec, "start_at_bound")
    b_x = _fact(rec, "start_b_x")
    return {"aturns": _arr(rec, "start_aturns"), "psi_rms": _fact(rec, "start_psi_rms"),
            "b_x": None if not np.isfinite(b_x) or b_x < 0 else b_x,
            "psi_x_offset": _fact(rec, "start_psi_x_offset"),
            "at_bound": np.flatnonzero(flags == 1.0)}


def start_state(*, target: dict, ip: float,
                n_points: int = 24, n_ring: int = 4, peaking: float = 1.0,
                xpoint=None, x_weight: float = 1.0, lam: float = 1e-3,
                i_max=None, device=None) -> dict:
    """The machine state a shape anneal is entitled to BEGIN from — BY THE KERNEL.

    One linear isoflux solve for the channel currents that make ``target``
    a flux contour of plasma-plus-coils, with the plasma modelled as a
    filament cloud filling the requested boundary.

    ★It is **not an equilibrium**: force balance is nowhere in it, and the
    current distribution is the cloud's rather than the one a
    Grad-Shafranov solve will impose.  What it is for is stated in
    :func:`discharge`: that anneal linearises about the equilibrium it is
    standing on, so it needs a machine state with a plasma of roughly the
    right size in roughly the right place, and there is no such thing at
    zero current.

    ★★2026-09-05 (FYL-DESIGN-16 K-3, the third tool to sink): this used to
    read the conductors and the box off the device, fill the cloud, call the
    kernel's linear solve and fold the seed field itself — the recipe was
    this host's, and the page held a second copy.  It is
    ``case.rs::discharge_case`` (``stage: start``) now; this function builds
    the PLAN and reads the RECORD back into the dict its callers know.
    ``psi_seed`` is the field the design was made with, on the solver's
    grid.
    """
    settings = _start_settings(target, ip, n_points=n_points, xpoint=xpoint, x_weight=x_weight)
    settings.update(stage="start", n_ring=float(n_ring), peaking=float(peaking), lam=float(lam))
    discharge = {}
    if i_max is not None:
        discharge["fylite:i_max_aturn"] = np.atleast_1d(np.asarray(i_max, float))
    rec = _complete(settings, discharge, device=device)
    out = _start_of(rec)
    out["psi_seed"] = _arr(rec, "psi_seed")
    #: ★under the DISCHARGE tool's registry entry: `start_state` is not a
    #: registered tool
    out["provenance"] = provenance("discharge", stage="start_state",
                                   n_points=n_points, n_ring=n_ring)
    return out


def discharge(*, target: dict, ip: float,
              aturns0=None, beta0: float = 0.55, emp: float = 1.0,
              enp: float = 1.0, n_points: int = 24, passes: int = ANNEAL_PASSES,
              schedule=None, gamma: float = ANNEAL_GAMMA,
              xpoint=None, x_weight: float = 0.0, limiter=None,
              i_max=None, device=None, **solve_kw) -> dict:
    """Static coil inverse: drive the boundary toward ``target`` — BY THE KERNEL.

    ``target`` is the Miller description (``r0``, ``a``, ``kappa``,
    ``delta_upper``, ``delta_lower``).  Each pass alternates a free-boundary
    solve with one ridge least-squares correction that flattens psi along the
    requested boundary points, annealing the ridge weight down ``schedule``.
    An optional X-point adds three field rows at ``x_weight``.

    ★The anneal travels from the LAST pass, not from the best one.  Rolling
    a regression back was tried in the browser twin and measurably hurts: the
    good basin usually lies past a worse intermediate state.  ``history`` is
    therefore not required to be monotone, and ``pass`` says which pass the
    returned currents came from — a run that never improves ends at pass 0
    and says so.

    A pass whose solve fails is recorded in ``history`` with its error and
    ends the anneal; it is not dropped, because "the search stopped here" and
    "the search finished" are different outcomes.

    ★★2026-09-05 (FYL-DESIGN-16 K-3): the recipe — target points, response
    rows, ridge scale, the designed start, the collapse-and-halve rule, the
    best-of selection — is ``case.rs::discharge_case`` now, one copy for
    this host and the page.  This function builds the PLAN and reads the
    RECORD back into the dict its callers know.  ``limiter`` names the
    wall unit by its DD ``name`` (the document's first when not given);
    ``solve_kw`` are the solver knobs (``relax`` · ``max_iter`` · ``tol`` ·
    ``fb_gain``).
    """
    known = {"relax", "max_iter", "tol", "fb_gain"}
    bad = set(solve_kw) - known
    if bad:
        raise TypeError(f"discharge() got unexpected solver settings {sorted(bad)}; "
                        f"the kernel takes {sorted(known)}")
    settings = _start_settings(target, ip, n_points=n_points, xpoint=xpoint, x_weight=x_weight)
    settings.update(beta0=float(beta0), emp=float(emp), enp=float(enp), gamma=float(gamma),
                    passes=float(passes), anneal_hi=ANNEAL_HI, anneal_lo=ANNEAL_LO)
    settings.update({k: float(v) for k, v in solve_kw.items()})
    if limiter is not None:
        settings["limiter"] = str(limiter)
    discharge_in = {}
    if aturns0 is not None:
        discharge_in["fylite:channel_aturns"] = np.asarray(aturns0, float)
    if schedule is not None:
        discharge_in["fylite:anneal_schedule"] = np.asarray(tuple(schedule), float)
    if i_max is not None:
        discharge_in["fylite:i_max_aturn"] = np.atleast_1d(np.asarray(i_max, float))
    rec = _complete(settings, discharge_in, device=device)

    shape_keys = ("r0", "z0", "a", "kappa", "delta_upper", "delta_lower")
    h_pass, h_alpha = _arr(rec, "history_pass"), _arr(rec, "history_alpha")
    h_err, h_res = _arr(rec, "history_err"), _arr(rec, "history_residual")
    h_halve, h_shape = _arr(rec, "history_halvings"), _arr(rec, "history_shape")
    notes = list(rec.get("notes", []))
    history = []
    for i in range(h_pass.size):
        if not np.isfinite(h_err[i]):
            #: the pass that stopped the search: its reason is the record's note
            history.append({"pass": int(h_pass[i]), "alpha": float(h_alpha[i]), "err": None,
                            "error": next((n for n in notes if n.startswith(f"pass {int(h_pass[i])}:")),
                                          "the pass failed")})
            break
        entry = {"pass": int(h_pass[i]), "alpha": None if i == 0 else float(h_alpha[i]),
                 "err": float(h_err[i]),
                 "shape": dict(zip(shape_keys, (float(v) for v in h_shape[i]))),
                 "residual": float(h_res[i])}
        if h_halve[i]:
            entry["step_halvings"] = int(h_halve[i])
        history.append(entry)
    equilibrium = {k: _fact(rec, k) for k in
                   ("psi_axis", "psi_bnd", "axis_r", "axis_z", "ip", "residual", "fb_amp", "zc")}
    equilibrium["iterations"] = int(_fact(rec, "iterations"))
    equilibrium["psi"] = _arr(rec, "psi")
    return {"aturns": _arr(rec, "aturns"),
            "shape": {k: _fact(rec, "shape_" + k) for k in shape_keys},
            "start": _start_of(rec) if _fact(rec, "designed_start") else None,
            "shape_error": _fact(rec, "shape_error"), "pass": int(_fact(rec, "pass")),
            "target_boundary": _arr(rec, "target_boundary"),
            "boundary": _arr(rec, "boundary"),
            "equilibrium": equilibrium, "history": history,
            "provenance": provenance("discharge", passes=len(history) - 1)}


def _deck_channels(cond):
    """The coil geometry and the channel map, as the kernel takes them.

    ★★It used to BUILD the weight matrix — a fourth inline copy of a map
    whose index direction is its entire content, and this one was written
    in the opposite orientation from the other three.  It also reached
    across a module line for ``circuits._element_arrays``, a private name in
    a module that no longer exists (it is `device` §3 now).
    Both are :mod:`fylite.device`'s now: ``conductor_set`` carries the one
    map, ``element_arrays`` the one marshalling shape.
    """
    return _device_mod.element_arrays(cond["coils"]), cond["weights"]


def loop_voltage(aturns_series, time, *, r0: float,
                 z0: float = 0.0) -> np.ndarray:
    """``V_loop = -dψ/dt`` at the null, from a current trajectory [V].

    The flux per ampere-turn is the kernel's, and so is the derivative —
    ★for its END RULE: a one-sided first-order end against a second-order
    interior is a choice, and the loop voltage at t = 0 is exactly where a
    breakdown design is read.
    """
    elems, w = _deck_channels(_conductors())
    psi_c = K.channel_field(elems, w, [r0], [z0])[0].ravel()
    x = np.atleast_2d(np.asarray(aturns_series, float))
    return -K.gradient(x @ psi_c, np.asarray(time, float))


def breakdown(*, r0: float, z0: float = 0.0, radius: float = 0.3,
              flux_target: float | None = None,
              device=None, b_tol: float = 2.0e-3, flux_tol: float = 0.1,
              weight_null: float = 1.0, weight_flux: float = 1.0,
              lam: float = 1e-12, limits: bool = True, i_max_aturn=None,
              x_ref=None) -> dict:
    """Design the vacuum field null for breakdown — BY THE KERNEL, from the device document.

    ★★2026-09-05 (FYL-DESIGN-16 K-3, the second tool to sink): this function
    used to read the deck's coils and channel map, fold the supply ratings
    into per-channel limits (``pulse.channel_limits``), call the one kernel
    export that does the design, and read the verdict off the numbers.  The
    design was already the kernel's; the limits and the verdict were this
    host's — and the pulse-design page held a second copy of both.  They are
    ``case.rs::breakdown_case`` now.  This function builds the PLAN (the
    device document, the disc, the tolerances, the optional overrides) and
    reads the RECORD back into the dict its callers know.

    Vacuum only — no Grad–Shafranov solve at all, which is what makes this
    the cheapest capability in the package.  When the design does not work
    the answer says WHICH channels are at or over their limit, and whether
    what failed was the null or the flux; a bare "infeasible" has no next
    move in it.

    ★★``feasible`` requires BOTH the null and the requested flux: minimising
    |B| with no flux requirement has the trivial solution "switch everything
    off", and a tight current box drives the design straight into it
    (measured: a 500 A-turn cap gives a beautiful null while delivering
    0.002 Wb of a 3 Wb request).  The kernel judges on both.
    """
    from ...io import fydoc
    dev = _device(device)
    settings = {"r0": float(r0), "z0": float(z0), "radius": float(radius),
                "b_tol": float(b_tol), "flux_tol": float(flux_tol),
                "weight_null": float(weight_null), "weight_flux": float(weight_flux),
                "lam": float(lam), "limits": 1.0 if limits else 0.0}
    if flux_target is not None:
        settings["flux_target"] = float(flux_target)
    discharge = {}
    if i_max_aturn is not None:
        discharge["fylite:i_max_aturn"] = np.atleast_1d(np.asarray(i_max_aturn, float))
    if x_ref is not None:
        discharge["fylite:x_ref"] = np.atleast_1d(np.asarray(x_ref, float))
    inputs = {"device": dev}
    if discharge:
        inputs["discharge"] = discharge
    rec = fydoc.complete("code/breakdown", {"settings": settings, "inputs": inputs})
    f = lambda k: float(rec["facts"][k]["value"])  # noqa: E731
    arr = lambda k: np.asarray(rec["fields"][k]["data"], float)  # noqa: E731
    imax = arr("i_max_aturn")
    at_bound = [int(i) for i in arr("at_bound")]
    over = [int(i) for i in arr("over")]
    reason = (None, "channel_limit", "flux_not_met_at_channel_limits",
              "flux_not_met", "null_not_met")[int(f("reason_code"))]
    flux_error = f("flux_error")
    binding = sorted(set(at_bound) | set(over))
    aturns = arr("aturns")
    return {
        "aturns": aturns, "iterations": int(f("iterations")),
        "converged": bool(f("converged")),
        "b_max": f("b_max"), "b_rms": f("b_rms"), "b_centre": f("b_centre"),
        "flux_Wb": f("flux"),
        "at_bound": at_bound, "over": over,
        "b_tol": float(b_tol), "i_max_aturn": imax,
        "limits_enforced": bool(f("limits_enforced")),
        "flux_target_Wb": flux_target,
        "null_ok": bool(f("null_ok")),
        "flux_error": (None if flux_target is None or np.isnan(flux_error) else flux_error),
        "channels_over_current": list(over), "channels_at_bound": list(at_bound),
        "flux_ok": bool(f("flux_ok")),
        "feasible": bool(f("feasible")), "reason": reason,
        "blocked_by": [{"channel": int(c), "name": _channel_name(dev, c),
                        "aturn": float(aturns[c]), "limit_aturn": float(imax[c]),
                        "over": bool(c in over)} for c in binding],
        "provenance": provenance("breakdown", reason=reason),
    }


def feasible(*, axis1: dict, axis2: dict, r0: float, z0: float = 0.0,
             device=None, **null_kw) -> dict:
    """Two-dimensional feasibility scan over the null design.

    ``axis1`` / ``axis2`` are ``{"name": <breakdown keyword>, "values":
    [...]}``.  Every grid point is one independent static solve — which is
    why this is a scan and not an optimiser: there is nothing to schedule.

    ★The map records per point not merely feasible / infeasible but the
    binding channel: "stopped at PF3's current limit" is the answer with a
    next move in it.  ``feasible`` here means "a static solve exists that
    meets the limits", NOT "the machine can run this way".
    """
    dev = _device(device)
    v1 = np.asarray(axis1["values"], float)
    v2 = np.asarray(axis2["values"], float)
    ok = np.zeros((v1.size, v2.size), dtype=bool)
    b_max = np.empty((v1.size, v2.size))
    blocked: list[list] = []
    for i, a in enumerate(v1):
        row = []
        for j, b in enumerate(v2):
            kw = dict(null_kw)
            kw[axis1["name"]] = float(a)
            kw[axis2["name"]] = float(b)
            d = breakdown(r0=r0, z0=z0, device=dev, **kw)
            ok[i, j] = d["feasible"]
            b_max[i, j] = d["b_max"]
            row.append([e["name"] for e in d["blocked_by"]])
        blocked.append(row)
    return {"axis1": {"name": axis1["name"], "values": v1},
            "axis2": {"name": axis2["name"], "values": v2},
            "feasible": ok, "b_max": b_max, "blocked_by": blocked,
            "n_feasible": int(ok.sum()), "n_points": int(ok.size),
            "provenance": provenance("feasible")}


# --------------------------------------------------------------------------- #
# assembly helpers
# --------------------------------------------------------------------------- #
#: ★``_summary`` used to live here too — the solve's twelve numbers were this
#: host's to fold.  They are the kernel's record now.


def _channel_name(device: dict, c: int) -> str:
    """The machine's own name for a channel, so a blocked design names the
    coil an operator knows rather than an index this package invented."""
    coils = (device or {}).get("pf_active", {}).get("coil") or []
    for coil in coils:
        if int(coil.get("efit_index", -1)) == int(c):
            return str(coil.get("name", f"ch{c}"))
    return f"ch{c}"
