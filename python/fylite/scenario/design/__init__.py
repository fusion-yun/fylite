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


def start_state(*, target: dict, ip: float,
                n_points: int = 24, n_ring: int = 4, peaking: float = 1.0,
                xpoint=None, x_weight: float = 1.0, lam: float = 1e-3,
                i_max=None) -> dict:
    """The machine state a shape anneal is entitled to BEGIN from.

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

    What comes back beside the currents says how well the request could be
    met at all — ``psi_rms`` is the RMS spread of the total flux over the
    boundary points, ``b_x`` the field magnitude left at the X point — so a
    hopeless target is visible before an equilibrium is paid for.

    ``psi_seed`` is the field the design was made with, on the solver's
    grid; :func:`discharge` hands it to the first solve, whose axis search
    would otherwise take the coil field's own maximum (out by the coils,
    because a design's coil field must cancel the plasma's flux variation
    over the boundary and therefore has a MINIMUM where the plasma belongs).
    """
    cond = _conductors()
    rg, zg = _grid_axes()
    bnd = target_boundary(n=n_points, **target)
    fil = K.fill_filaments(bnd[:, 0], bnd[:, 1], float(ip), n_ring=n_ring,
                           peaking=peaking)
    els = cond["coils"]
    elements = (np.array([e.r for e in els]), np.array([e.z for e in els]),
                np.array([e.w for e in els]), np.array([e.h for e in els]),
                np.array([getattr(e, "a1", 0.0) for e in els]),
                np.array([getattr(e, "a2", 90.0) for e in els]))
    d = K.start_currents(
        elements, cond["weights"], bnd[:, 0], bnd[:, 1], fil,
        x_point=None if not (x_weight > 0.0 and xpoint is not None)
                else (float(xpoint[0]), float(xpoint[1])),
        x_weight=float(x_weight),
        length=2.0 * np.pi * float(target["r0"]) * float(target["a"]),
        lam=float(lam), i_max=i_max, nu=4, nv=4)
    psi_seed = (_device_mod.psi_from_channels(cond, rg, zg, d["aturns"])
                + K.filament_flux(fil[:, 0], fil[:, 1], fil[:, 2], rg, zg))
    return {"aturns": d["aturns"], "psi_rms": d["psi_rms"],
            "b_x": d["b_x"], "psi_x_offset": d["psi_x_offset"],
            "at_bound": d["at_bound"], "psi_seed": psi_seed,
            #: ★under the DISCHARGE tool's registry entry: `start_state` is
            #: not a registered tool, and `provenance('start_state')` raised
            #: KeyError on the first run that ever took the aturns0=None
            #: path — the designed-start branch had no caller until the case
            #: corpus (S-2) exercised it.
            "provenance": provenance("discharge", stage="start_state",
                                     n_points=n_points, n_ring=n_ring)}


def discharge(*, target: dict, ip: float,
              aturns0=None, beta0: float = 0.55, emp: float = 1.0,
              enp: float = 1.0, n_points: int = 24, passes: int = ANNEAL_PASSES,
              schedule=None, gamma: float = ANNEAL_GAMMA,
              xpoint=None, x_weight: float = 0.0, limiter=None,
              i_max=None, **solve_kw) -> dict:
    """Static coil inverse: drive the boundary toward ``target``.

    ``target`` is the Miller description (``r0``, ``a``, ``kappa``,
    ``delta_upper``, ``delta_lower``).  Each pass alternates a free-boundary
    solve with one ridge least-squares correction that flattens psi along the
    requested boundary points, annealing the ridge weight down ``schedule``.
    An optional X-point adds two field rows at ``x_weight``.

    ★The anneal travels from the LAST pass, not from the best one.  Rolling
    a regression back was tried in the browser twin and measurably hurts: the
    good basin usually lies past a worse intermediate state.  ``history`` is
    therefore not required to be monotone, and ``pass`` says which pass the
    returned currents came from — a run that never improves ends at pass 0
    and says so.

    A pass whose solve fails is recorded in ``history`` with its error and
    ends the anneal; it is not dropped, because "the search stopped here" and
    "the search finished" are different outcomes.
    """
    cond = _conductors()
    rg, zg = _grid_axes()
    grid = K.grid_of(rg, zg)
    lim_r, lim_z = _limiter(limiter)
    schedule = anneal_schedule(passes) if schedule is None else tuple(schedule)

    bnd = target_boundary(n=n_points, **target)
    pr, pz = bnd[:, 0].copy(), bnd[:, 1].copy()
    use_x = x_weight > 0.0 and xpoint is not None
    if use_x:
        pr = np.append(pr, float(xpoint[0]))
        pz = np.append(pz, float(xpoint[1]))
    g_psi, g_br, g_bz = _device_mod.channel_response(cond, pr, pz)
    n_b, n_ch = len(bnd), g_psi.shape[1]

    #: The ridge scale comes from the response itself.  lambda has the units
    #: of a squared column norm, so a fixed number would mean something
    #: different on every machine and every point set.
    dpsi_col = g_psi[1:n_b, :] - g_psi[0, :]
    g_scale = float(np.sqrt(np.sum(dpsi_col ** 2) / max(dpsi_col.size, 1)))
    #: Tesla row -> Weber row, so the X-point rows can share one weight with
    #: the flux rows instead of carrying a unit accident as a "trade-off".
    length = 2.0 * np.pi * float(target["r0"]) * float(target["a"])

    warm = None
    if aturns0 is None:
        #: ★★No default, and no zeros — but no refusal either, now that a
        #: start can be DESIGNED.  This anneal is a LOCAL method: it
        #: linearises the boundary's response about the equilibrium it is
        #: standing on, so it needs a machine state that has a plasma.  From
        #: zero currents the first solve returns a degenerate column (a =
        #: 0.019 m, measured) and the second fails outright, which is why
        #: this used to raise.  :func:`start_state` answers the question the
        #: refusal was pointing at: one linear isoflux solve for the coil
        #: currents that make the requested boundary a flux contour of
        #: plasma-plus-coils.  It is not an equilibrium — force balance is
        #: nowhere in it — it is the state this anneal is entitled to begin
        #: from, and the browser twin begins from the same one.
        warm = start_state(target=target, ip=ip,
                           n_points=n_points, xpoint=xpoint,
                           x_weight=x_weight, i_max=i_max)
        chan = np.asarray(warm["aturns"], float)
    else:
        chan = np.asarray(aturns0, float).copy()
    prof = dict(beta0=beta0, emp=emp, enp=enp, r0=float(target["r0"]))

    def solve(x, psi_init=None, anchor=False):
        psi_ext = _device_mod.psi_from_channels(cond, rg, zg, x)
        #: ★the anchors, and why only the FIRST solve of a designed start
        #: gets them.  The fixed-current Picard map has no radial restoring
        #: force of its own, so a vertical field a few percent off — which
        #: is what a design made against a filament cloud gives, the cloud
        #: not being the profile the solver will impose — sends the column
        #: outward, and it shrinks as it goes (measured from a designed EAST
        #: start: a = 0.45 m at three iterations, 0.03 m at three hundred).
        #: Left on for every pass they would hold the shape with virtual
        #: currents instead of with the coils; ``fb_amp`` is reported either
        #: way, so the bias cannot pass unseen.
        extra = {}
        if anchor:
            extra = {"rc_anchor": float(target["r0"]),
                     "zc_anchor": float(target.get("z0", 0.0))}
        return K.gs_free_solve(rg, zg, psi_ext, ip=ip, limiter_r=lim_r,
                               limiter_z=lim_z, psi_init=psi_init,
                               **prof, **extra, **solve_kw)

    def measure(res):
        tr = K.trace_surface(grid, res["psi"], res["psi_bnd"],
                             axis=(res["axis_r"], res["axis_z"]),
                             limiter=(lim_r, lim_z))
        return K.shape_metrics(tr["poly"]), tr

    def error(sm):
        #: ★SIX terms, not five.  The vertical placement is part of the
        #: request — ``target_boundary`` takes a ``z0`` — and was absent
        #: from the objective, so a pass whose boundary had drifted most
        #: of a metre off the requested midplane could be selected as the
        #: best one and returned as the design.  Z0 is normalised by the
        #: minor radius, the same length R0 is normalised by.  The browser
        #: twin carries the same six.
        a = float(target["a"])
        kap = float(target.get("kappa", 1.0))
        z0 = float(target.get("z0", 0.0))
        return float(np.sqrt((
            ((sm["r0"] - float(target["r0"])) / a) ** 2
            + ((sm["z0"] - z0) / a) ** 2
            + ((sm["a"] - a) / a) ** 2
            + ((sm["kappa"] - kap) / kap) ** 2
            + (sm["delta_upper"] - float(target.get("delta_upper", 0.0))) ** 2
            + (sm["delta_lower"] - float(target.get("delta_lower", 0.0))) ** 2)
            / 6.0))

    def correction(res, alpha):
        #: ★THREE X-point rows, not two.  ``B_r = B_z = 0`` pins a null
        #: somewhere in the machine and never says the null must sit ON the
        #: requested boundary; a null at a different flux level is not a
        #: divertor, and both hosts produced exactly that — X-point rows on,
        #: boundary still classified limiter.  ``psi(X) = psi(P_0)`` is the
        #: row that asks for the topology.
        rows = (n_b - 1) + (3 if use_x else 0)
        a = np.zeros((rows, n_ch))
        b = np.zeros(rows)
        w = np.zeros(rows)
        #: one read for every boundary point, not one call per point
        psin_b = K.sample_grid(grid, res["psi"], pr[:n_b], pz[:n_b])
        for j in range(1, n_b):
            a[j - 1] = g_psi[j] - g_psi[0]
            b[j - 1] = -(psin_b[j] - psin_b[0])
            w[j - 1] = 1.0
        if use_x:
            fbr, fbz = K.b_field(grid, res["psi"], [pr[-1]], [pz[-1]])
            br, bz = float(fbr[0]), float(fbz[0])
            psi_x = float(K.sample_grid(grid, res["psi"], [pr[-1]],
                                        [pz[-1]])[0])
            a[n_b - 1] = g_psi[-1] - g_psi[0]
            a[n_b] = g_br[-1] * length
            a[n_b + 1] = g_bz[-1] * length
            b[n_b - 1] = -(psi_x - psin_b[0])
            b[n_b] = -br * length
            b[n_b + 1] = -bz * length
            w[n_b - 1] = w[n_b] = w[n_b + 1] = float(x_weight)
        return K.ridge_lstsq(a, b, w, np.full(n_ch, alpha * g_scale))

    res = solve(chan, psi_init=warm["psi_seed"] if warm else None,
                anchor=warm is not None)
    sm, tr = measure(res)
    best = {"chan": chan.copy(), "res": res, "shape": sm, "trace": tr,
            "err": error(sm), "pass": 0}
    history = [{"pass": 0, "alpha": None, "err": best["err"], "shape": sm,
                "residual": float(res["residual"])}]

    for p, alpha in enumerate(schedule, start=1):
        try:
            #: ★a pass that LOSES the plasma is not "a worse intermediate
            #: state to travel from" — it is a dead end whose linearisation
            #: means nothing.  The fixed-current Picard map has no radial
            #: restoring force, so an overlong step tips the column into a
            #: radial escape (measured from the EAST reference start once
            #: pass 0 solved diverted: the full step walked out to a
            #: 0.03 m column at R = 2.34 over 400 rounds, and the HALF
            #: step from the same base reached err 0.051).  So a collapsed
            #: pass — minor radius under a quarter of the requested one —
            #: is retried from its base at half the step, up to three
            #: halvings, and the retreat is in the history.
            gam, halved = gamma, 0
            while True:
                nxt = chan + gam * correction(res, float(alpha))
                #: later passes warm-start from the field in hand and
                #: carry no anchor: from here the coils have to hold the
                #: shape themselves
                r2 = solve(nxt, psi_init=res["psi"])
                sm, tr = measure(r2)
                collapsed = (not np.isfinite(sm["a"])
                             or sm["a"] < 0.25 * float(target["a"]))
                if not collapsed or halved >= 3:
                    break
                gam *= 0.5
                halved += 1
            res = r2
        except Exception as exc:                     # noqa: BLE001 - reported
            history.append({"pass": p, "alpha": float(alpha), "err": None,
                            "error": str(exc)})
            break
        chan = nxt
        err = error(sm)
        entry = {"pass": p, "alpha": float(alpha), "err": err,
                 "shape": sm, "residual": float(res["residual"])}
        if halved:
            entry["step_halvings"] = halved
        history.append(entry)
        if err < best["err"]:
            best = {"chan": chan.copy(), "res": res, "shape": sm,
                    "trace": tr, "err": err, "pass": p}

    return {"aturns": best["chan"], "shape": best["shape"],
            "start": None if warm is None
                     else {k: v for k, v in warm.items() if k != "psi_seed"},
            "shape_error": best["err"], "pass": best["pass"],
            "target_boundary": bnd, "boundary": best["trace"]["poly"],
            "equilibrium": _summary(best["res"]), "history": history,
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
def _grid_axes():
    """The computational box, from the deck that defines it."""
    box = _device_mod.grid_box()
    return box["rgrid"], box["zgrid"]


def _limiter(limiter):
    if limiter is not None:
        return np.asarray(limiter[0], float), np.asarray(limiter[1], float)
    return (np.asarray(_device_mod.XLIM, float),
            np.asarray(_device_mod.YLIM, float))


#: ★``_sample`` and ``_b_field`` used to live here.  The comment on the
#: first one drew the line itself — "indexing, not physics; the moment it
#: needs a derivative it becomes physics and moves (the kernel already has
#: ``surfaces::b_field``)" — and named ``_b_field`` right below it as that
#: boundary being approached.  It had already been crossed: ``_b_field``
#: WAS the derivative, built on a private bilinear read that the browser
#: and ``surfaces.rs`` each had their own copy of.  Both are
#: :func:`fylite.kernel.sample_grid` and :func:`fylite.kernel.b_field` now.


def _summary(res: dict) -> dict:
    out = {k: float(res[k]) for k in
           ("psi_axis", "psi_bnd", "axis_r", "axis_z", "ip", "residual",
            "fb_amp", "zc")}
    out["iterations"] = int(res["iterations"])
    out["psi"] = res["psi"]
    return out


def _channel_name(device: dict, c: int) -> str:
    """The machine's own name for a channel, so a blocked design names the
    coil an operator knows rather than an index this package invented."""
    coils = (device or {}).get("pf_active", {}).get("coil") or []
    for coil in coils:
        if int(coil.get("efit_index", -1)) == int(c):
            return str(coil.get("name", f"ch{c}"))
    return f"ch{c}"
