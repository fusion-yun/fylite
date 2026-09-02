"""Equilibrium reconstruction on the Rust backend — measurements in, a
reconstruction out (FYL-DESIGN-01 L4, the production path).

This is the piece the twin experiments were missing.  Until now the Rust
inverse (``fylite_rs_gs_inverse_solve``) had no caller in the package: every
measured result was produced by assembling the response matrix, the weights
and the anchors by hand in a test.  Everything that assembly did lives here,
once, behind the same measurement dict :func:`fylite.run.forward_equilibrium` takes.

What the assembly is (all of it Python-side by design §2 — the Rust core eats
arrays):

* the **grid** is read from the geometry deck that defines it
  (:func:`fylite.device.grid_box`), not from declared metadata that can
  drift away from it;
* ``psi_ext`` is the coil field on that grid, folded from the measured
  channel amp-turns through the device document's own conductor geometry
  (:func:`device.psi_from_channels`);
* the **response matrix** is the full-flux mutual of every flux loop to
  every grid node — the linear map from a grid current distribution to what
  the loops would read;
* the loops' **plasma-only** signal is the measurement minus the coils'
  own contribution at the loop positions — and that contribution is
  COMPUTED from the same conductor geometry (:func:`coil_loop_rows`), not
  read from a Green table;
* **pressure rows** enter when the measurement dict carries a pressure
  profile (the kinetic tier), and are re-assembled per iteration inside the
  solver because the flux span moves;
* the **anchors** (current-centroid R and Z) are the vertical/radial
  information the loops alone do not carry.  Pass them explicitly, or let
  :mod:`fylite.scenario.analysis.moments` derive them from the magnetic probes.

Accuracy, measured against the Fortran path on the bundled case (see
changelog.md, the kernel record): with both anchors and the form-mapped profile, axis Z to
0.1 mm, axis R to 4-7 mm, q0 +1%, q95 +2%, li +14% (the edge-zero basis's
form limit).  Without anchors the vertical position is free and the axis
lands ~45 mm off — the anchors are not a refinement, they carry information.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ... import device, kernel
from ...device import flux_loop_positions

#: kept as the name callers and the service layer already raise/catch

from ...io import est2

from ...io import mds
from ...run import KefitRunError  # noqa: F401

__all__ = ["reconstruct", "reconstruct_shot", "reconstruct_input",
           "fit_profiles",
           "response_matrix", "coil_loop_rows", "run_series", "KefitRunError"]


def response_matrix(rg, zg) -> np.ndarray:
    """Full-flux mutual of every flux loop to every grid node.

    Shape ``(n_loops, nr * nz)`` — the linear map from a grid current
    distribution [A per cell] to the flux [Wb] each loop would read.
    """
    rsi, zsi = flux_loop_positions()
    nr, nz = rg.size, zg.size
    #: ★the ``(n_loop, n_node)`` block of one mutual is
    #: :func:`fylite.kernel.mutual_outer`, in one call.  This used to be a
    #: Python loop over loops, each iteration broadcasting one loop position
    #: into a full grid-length array to feed an ELEMENTWISE entry — 35 copies
    #: of a constant, materialised, to compute an outer product the kernel
    #: answers without materialising either side.
    return np.ascontiguousarray(
        kernel.mutual_outer(rsi, zsi, np.repeat(rg, nz), np.tile(zg, nr)))


def probe_response(rg, zg) -> tuple:
    """Poloidal-field response of every probe to every grid node.

    Row *i* maps a grid current distribution [A per cell] to what probe *i*
    would read [T], along its own orientation:
    ``B = B_R cos(a) + B_Z sin(a)``.

    ★The rows are the kernel's (:func:`fylite.kernel.probe_response`).  This
    used to be a second implementation here — same construction (the field
    from the mutual's own definition, by a centred difference in the PROBE's
    position) but a different step: a hundredth of a cell, against the
    kernel's fixed 1e-4 m.  Two spellings of one Green's function, and they
    did not agree: 17 of 333 775 cells differed by more than 1e-3 relative,
    up to 2.2e-2, all of them within about a cell of a probe, where the
    derivative varies fastest and the larger step truncates sooner.

    ★★What that was worth, measured rather than argued: folding both row
    sets against the reference discharge's OWN current distribution
    (g137985, filaments from its j_phi) moves the predicted probe signal by
    3.1e-7 relative at worst, 7.5e-8 rms — because the cells that disagree
    sit outside the plasma, next to the probes, and carry no current.  The
    kernel's smaller step is the more accurate of the two, and it is also
    twelve times faster (0.27 s -> 0.02 s on the 65x65 deck).

    Returns ``(rows, angle_rad)``; ``rows`` has shape ``(n_probes, nr * nz)``.
    """
    from ...device import probe_geometry as _load_probe_geometry
    #: ★the fyo device document, not a ``dprobe.dat`` under a table
    #: directory.  The geometry is the machine's, not the Green table
    #: directory's — the deck there was a byte-identical copy of the device
    #: one, which is what made "which of the two is authoritative"
    #: answerable only by luck.
    geo = _load_probe_geometry()
    pr = np.asarray(geo["r"], float)
    pz = np.asarray(geo["z"], float)
    ang = np.deg2rad(np.asarray(geo["angle_deg"], float))
    rows = kernel.probe_response(rg, zg, pr, pz, ang)
    return np.ascontiguousarray(rows.reshape(pr.size, rg.size * zg.size)), ang


def coil_loop_rows(conductors=None, *, nu: int = 8, nv: int = 8) -> np.ndarray:
    """What each BRSP channel contributes at each flux loop —
    ``(n_loops, n_channels)`` in the loops' own EFIT convention
    [Wb/rad per ampere-turn].

    ★★This is EFIT's ``rsilfc``, and it used to be READ: ``rfcoil.ddd``
    under the Green-table directory, the last device fact this package took
    from a binary deck instead of from the device document.  It was also the
    one file this distribution ships no copy of, so the whole Python
    reconstruction path raised :class:`~fylite.device.MachineDataMissing`
    before it reached its first kernel call — and zeroing ``brsp`` did not
    get past it, because the read happened whether or not the currents were
    zero.  Machine facts now have ONE source, the device document, for the
    loop rows as for everything else.

    ★It was already computed twice elsewhere in this repository: by the wasm
    host (``app/assets/worker.js``, ``coilLoopRows``) and by the PROBE half
    of this very fit (:func:`fylite.scenario.analysis.moments.plasma_probe_field`,
    which removes the coils with ``probe_element_response @ el``).  One
    machine, one Green's function; only the loop half still went to a table.

    ★★Measured, not assumed — against the real deck, by two independent
    consumers (fywork CASE-09 G-01 first, then re-measured here): the
    computed table agrees with the frozen EAST ``rfcoil.ddd``
    to 7.7e-5 relative at ``nu=nv=8``, and the residual falls
    monotonically with quadrature order (4.88e-4 → 2.37e-4 → 1.51e-4 →
    9.13e-5 → 7.72e-5) — filamentisation and quadrature, not structure.  Per
    channel it is uniform (7.0e-6…7.7e-5), the two channels that drive a
    PAIR of elements included, which is what says the frozen
    ``pf_channel_elements`` map is the right one.  That is why ``nu=nv=8``
    is the default: it costs 1.2 ms on the 35-loop EAST deck (0.9 ms at
    4x4), once per reconstruction, against a fit that runs for seconds.

    ★★And what the SWITCH cost, measured end to end on the reference
    discharge (#137985 @ 4.0 s, deck rows vs these rows, everything else
    equal, on the converged kinetic configuration): Ip 1e-6 A, axis R
    0.14 mm, axis Z 0.05 mm, q95 0.05 %.  ★It is not zero, and it is not
    supposed to be — two filamentisations of the same conductor do not
    round the same way.  It is 3e-4 of the fit's own distance from the
    reference answer.

    ★The 1/2π is EFIT's loop convention — the same ``MEAS_SCALE`` the
    browser applies.  The kernel answers in full flux [Wb]; every loop
    number on this path is Wb/rad.  The deck's own table agreed: its median
    ratio to the computed full flux was 6.283148 against 2π = 6.283185.

    ``conductors`` is a :func:`fylite.device.conductor_set` mapping — pass
    the one the caller already resolved, so that the rows and the external
    flux cannot come from two different machines.
    """
    cond = device.conductor_set() if conductors is None else conductors
    rsi, zsi = flux_loop_positions()
    psi = np.asarray(
        device.channel_response(cond, rsi, zsi, nu=nu, nv=nv)[0], float)
    return np.ascontiguousarray(psi / (2.0 * np.pi))



#: ★★2026-09-01 自 `io/kfile.py` 迁入（那个模块已整体移除）。原来的
#: `load_limiter` 只是 `device.limiter_unit` 的一层形状适配加一张别名表，而
#: 本函数是它唯一的调用者——薄包装跨模块住着，只是给同一个东西添了第二个地址。
_LIMITER_ALIASES = {"default": "m-file", "m-file": "m-file", "mfile": "m-file",
                    "efit_w_pf": "efit_w_pf", "operational": "efit_w_pf",
                    "gui": "efit_w_pf", "wpf": "efit_w_pf"}


def _load_limiter(name: str | None = None) -> dict:
    """限制器轮廓 ``{limitr, xlim, ylim}``：显式 name -> ``$KEFIT_LIMITER`` -> 缺省。

    ★真源是**装置文档**（DD 把 ``wall.description_2d.limiter.unit`` 写成结构数组，
    而 EAST 确有两条随年代不同的内壁）。别名表只把人话映到 DD 的 ``name`` 上；
    别名之外的取值当作一份 JSON 文件的路径。
    """
    sel = name or os.environ.get("KEFIT_LIMITER")
    if sel and sel not in _LIMITER_ALIASES:
        return json.loads(Path(sel).read_text())
    u = device.limiter_unit(name=_LIMITER_ALIASES.get(sel or "default"))
    return {"limitr": int(u["count"]),
            "xlim": [float(v) for v in u["outline"]["r"]],
            "ylim": [float(v) for v in u["outline"]["z"]]}


def _limiter(name=None):
    """The limiter polygon, through the same selector the k-file writer uses
    (explicit name -> $KEFIT_LIMITER -> bundled default)."""
    lim = _load_limiter(name)
    return (np.ascontiguousarray(np.asarray(lim["xlim"], float)),
            np.ascontiguousarray(np.asarray(lim["ylim"], float)))


#: Points in the 1-D profiles a reconstruction carries.  ★65 because that is
#: what the bundled decks use; the profiles are analytic in the fit's basis,
#: so this is a sampling choice and not a resolution.
N_PROFILE = 65


def fit_profiles(coefs, *, npp: int, nff: int, span_perrad: float,
                 f_edge: float, n: int = N_PROFILE) -> dict:
    """The fit's 1-D profiles on ``n`` uniform ψ_N points.

    ``{psin, dpressure_dpsi, f_df_dpsi, pressure, f}`` — p′ and FF′ per radian
    of ψ, p in Pa (edge-zeroed), F in T·m.

    ★DD names, not the deck's ``pprime``/``ffprim``/``pres``/``fpol``.  This
    function is new and lives in ``scenario/``, where
    ``test_no_scenario_module_reads_a_gfile_key`` holds the line — it caught
    the first draft of this very function, which is what the gate is for.
    ``reconstruct`` translates to the result dict's EFIT spellings on the way
    out, and those are a wire contract, not this layer's vocabulary.

    ★★The bases are the SOLVE's own, read off ``inverse.rs``'s current
    construction rather than re-derived from the paper: it assembles
    ``j_phi = R p'(psi) + FF'(psi) / (mu0 R)`` out of ``r * (x^k - x^npp)``
    and ``(x^k - x^nff) / (mu0 r)``, so those ARE the two edge-zeroed bases
    and the coefficients need no rescaling.  ``pres`` is the antiderivative
    ``inverse.rs`` uses for its own kinetic-constraint rows
    (``pressure_row``), so a pressure-constrained solve and this profile
    cannot disagree about what the fit meant.

    ★Its own function, and not inline in :func:`reconstruct`, because a full
    solve needs the Green tables and this arithmetic does not — inline, the
    one part of the reconstruction that is pure algebra would only ever run
    on a host that carries a machine.  ``test_recon_profiles.py`` checks it
    against :func:`fylite.kernel.f_from_coefficients`, an independent path to
    the same F.
    """
    x = np.linspace(0.0, 1.0, int(n))
    cpp, cff = np.asarray(coefs[:npp], float), np.asarray(coefs[npp:], float)

    def edge_zero(c, top):
        out = np.zeros_like(x)
        for k, ck in enumerate(c):
            out += ck * (x ** k - x ** top)
        return out

    pres = np.zeros_like(x)
    for k, ck in enumerate(cpp):
        pres -= span_perrad * ck * ((1.0 - x ** (k + 1)) / (k + 1)
                                    - (1.0 - x ** (npp + 1)) / (npp + 1))
    return {"psin": x,
            "dpressure_dpsi": edge_zero(cpp, npp),
            "f_df_dpsi": edge_zero(cff, nff),
            "pressure": pres,
            "f": np.asarray(kernel.f_from_coefficients(
                cff, x, span_pr=span_perrad, f_edge=f_edge), float)}


def _fsa_field(spec: dict, key: str):
    """One required field of ``current_fsa``, named when it is missing.

    ★A bare ``spec[key]`` would raise ``KeyError: 'shape'`` — true, and one
    key at a time, which is exactly the shape of failure the tool face spent
    a batch removing.
    """
    try:
        return spec[key]
    except (KeyError, TypeError):
        raise TypeError(
            "current_fsa needs {'x': ψ_N surfaces, 'shape': j/<j> there} "
            "and optionally {'weights': one per surface}; got "
            f"{sorted(spec) if isinstance(spec, dict) else type(spec).__name__}"
        ) from None


def reconstruct(meas: dict, *, npp: int = 1, nff: int = 2,
                current_fsa=None, vessel_sigma: float | None = None,
                vessel_modes: int | None = None,
                zc_anchor: float | None = None,
                rc_anchor: float | None = None,
                pressure_x=None, pressure_sigma_frac: float = 0.05,
                probes: bool = True, probe_weights=None,
                probe_weight_scale: float = 1.0,
                current_source=None,
                limiter: str | None = None, relax: float = 0.3,
                max_iter: int = 800, tol: float = 1e-9,
                fb_gain: float = 8.0, warmup: int = 40) -> dict:
    """Reconstruct one equilibrium from measurements on the Rust backend.

    ``current_fsa`` imposes the FLUX-SURFACE-AVERAGED current constraint —
    ``{"x": ψ_N, "shape": j/⟨j⟩, "weights": …}``, EFIT's
    ``KZEROJ``/``SIZEROJ``/``VZEROJ`` at ``RZEROJ = 0``.  ★It is a SHAPE in
    units of its own mean, and that is the whole reason it can sit beside
    the Ip equality: the magnitude belongs to Ip, and one fit takes one
    statement about the total current.  The kernel rebuilds the rows on the
    surfaces the CURRENT field has, every Picard iteration; a surface that
    cannot be traced drops its row and the result reports how many held
    (``fsa_rows_used``).

    ★★``weights`` HAS A SCALE, and it is not 1.  The FSA rows are
    unnormalised current densities (entries ~1e5…1e6) while the flux-loop
    rows are mutual inductances (~1e-7), so a weight of 1 puts the FSA rows
    twelve orders above the magnetics in the normal equations — and that
    breaks the fit even when the constraint is ALREADY SATISFIED: measured
    on the reference discharge, feeding a converged fit its own FSA shape at
    ``weights=1`` moves the magnetic axis 231 mm.  The usable band measured
    there is **1e-7 … 1e-3**, saturating above 1e-7 (the constraint is
    effectively hard by then); ``1e-6`` is a reasonable place to start.
    ★This is a scale the caller cannot see and the face does not state; it
    is written here because the face had no caller and no test until B-06
    went looking (T-C43).

    ``meas`` is the same flat dict :func:`fylite.run.forward_equilibrium` consumes: at least
    ``plasma`` (Ip [A]), ``brsp`` (coil amp-turns) and ``coils`` (flux-loop
    readings, EFIT Wb/rad sign); ``expmp2``/``fwtmp2`` add the probe rows and
    ``pressure`` the kinetic tier.

    ``npp`` / ``nff`` are the REDUCED (edge-zero) basis orders, one less than
    the k-file's ``KPPCUR`` / ``KFFCUR``; the defaults match the bundled deck
    defaults (KPPCUR=2, KFFCUR=3).  Higher orders need the pressure rows to
    stay conditioned — magnetics alone leave them in a degenerate direction
    (measured).

    Returns a dict with the reconstruction (``psi`` in full flux [Wb] on the
    table grid) and the scalars the Fortran path reports under the same
    names, so the two are directly comparable.
    """
    #: ★loud up front, not at whichever kernel call happens to come first:
    #: this routine is a long chain of them and "no kernel" is one answer,
    #: not a dozen different ones depending on where the chain got to.
    kernel.require()

    box = device.grid_box()
    rg = np.ascontiguousarray(np.asarray(box["rgrid"], float))
    zg = np.ascontiguousarray(np.asarray(box["zgrid"], float))
    nr, nz = rg.size, zg.size

    #: ★ONE resolution of the machine for the whole fit.  The external flux
    #: and the loops' coil rows are the same Green's function contracted at
    #: two places, so they take the same conductor set — resolving twice is
    #: how one of them ends up describing a different machine than the other.
    cond = device.conductor_set()
    aturns = np.asarray(meas["brsp"], float)
    psi_ext = device.psi_from_channels(cond, rg, zg, aturns)

    lm = response_matrix(rg, zg)
    # loops see coils + plasma; the fit solves for the plasma part only
    rsilfc = coil_loop_rows(cond)
    b_loops = np.asarray(meas["coils"], float) - rsilfc @ aturns
    wts = np.asarray(device.FWTSI_MASK, float)
    if wts.size != b_loops.size:                      # pragma: no cover
        raise ValueError(f"{wts.size} loop weights for {b_loops.size} loops")

    # PROBE rows.  The loops constrain the plasma's total and its outboard
    # reach; the probes are what senses the current DISTRIBUTION, and EFIT
    # fits both.  Measured on the bundled case: loops alone leave the fit in
    # a degenerate direction (li off 2.4x), probes bring it back.
    #
    # The solver applies ONE measurement scale to every row (the loops' EFIT
    # Wb/rad convention, 1/2pi).  Probe rows are in tesla, so they are
    # pre-multiplied by 2pi here and come out of that scaling in their own
    # units — one visible factor instead of a second ABI parameter.
    if probes:
        prow, pang = probe_response(rg, zg)
        from . import moments
        b_pr, _, _, _, w_pr = moments.plasma_probe_field(
            meas, weights=probe_weights)
        n_pr = min(prow.shape[0], b_pr.size)
        if float(np.max(np.abs(w_pr[:n_pr]))) > 0.0:
            lm = np.vstack([lm, prow[:n_pr] * (2.0 * np.pi)])
            b_loops = np.concatenate([b_loops, b_pr[:n_pr]])
            wts = np.concatenate([wts, w_pr[:n_pr] * probe_weight_scale])
    lm = np.ascontiguousarray(lm)
    b_loops = np.ascontiguousarray(b_loops)
    wts = np.ascontiguousarray(wts)

    # optional pressure rows (kinetic tier)
    pres = meas.get("pressure")
    if pres is not None:
        pres = np.asarray(pres, float)
        xg = np.linspace(0.0, 1.0, pres.size)
        xp = np.ascontiguousarray(
            np.asarray(pressure_x, float) if pressure_x is not None
            else np.linspace(0.1, 0.9, 9))
        pmeas = np.ascontiguousarray(kernel.interp(xp, xg, pres))
        scale = pressure_sigma_frac * float(np.abs(pmeas).max() or 1.0)
        wp = np.ascontiguousarray(np.full(xp.size, 1.0 / scale))
    else:
        xp = pmeas = wp = np.zeros(1)

    # prescribed (neoclassical) current: bootstrap and any driven current
    # are known physics, so the fit is not asked to re-derive them.  The
    # array is per INTERIOR cell, matching the solver's mask.
    if current_source is None:
        j_pre = np.zeros(1)
    else:
        j_pre = np.ascontiguousarray(np.asarray(current_source, float))
        if j_pre.size != (nr - 2) * (nz - 2):
            raise ValueError(
                f"current_source has {j_pre.size} cells, expected "
                f"{(nr - 2) * (nz - 2)} = (nr-2)*(nz-2)")

    lr, lz = _limiter(limiter)

    #: ★★THE VESSEL, when a caller asks for it.  Eddy currents in the
    #: passive structure link the flux loops — the reference EFIT carries
    #: them through ``rv6565.ddd``'s ``rsilvs``, and this path had no vessel
    #: term at all.  Here they are FITTED, as forty channels of nominal zero
    #: current with a prior width in amps, through the kernel entry that
    #: already knows how to move a current from the right-hand side into the
    #: parameter vector.
    #:
    #: ★Both responses are COMPUTED from the device document's own passive
    #: geometry, exactly as the coil rows are (T-C37): a repository that
    #: ships no ``rv6565.ddd`` can still ask this question.
    #:
    #: ★★★And the answer, measured on the reference discharge (T-C43).
    #: 〔This comment used to say "the vessel buys very little, and
    #: saturates", quoting a scan that stopped at sigma_v = 10 kA — while
    #: the note it points at already ran to 30 kA, where the loop scatter
    #: halves (3.82 -> 2.02 sigma) and the vertical feedback the fit needs
    #: falls with it (69.9 -> 25.9 kA).  It does not saturate.〕
    #:
    #: ★★But what it buys there it buys by OVER-FITTING, and the shape of
    #: the fitted current says so: poloidal harmonics m <= 3 explain 10.6 %
    #: of it, neighbouring segments alternate at the kA level, and one
    #: segment reaches 17.4 kA.  Truncating the eddy distribution to the
    #: harmonics a passive structure can plausibly carry (``vessel_modes``)
    #: takes all of it away again — every truncation from m <= 0 to m <= 5
    #: leaves the scatter at 3.6…4.0 sigma and the feedback above 51 kA.
    #: ⇒ **the leftover residual is not a missing passive current**, and
    #: what it is instead is measured in ``tests/test_reconstruction.py``.
    coil_block = None
    if vessel_sigma is not None:
        ves = cond["vessel"]
        n_ves = len(ves)
        v_psi = np.ascontiguousarray(
            np.asarray(device.grid_response(ves, rg, zg), float)
            .reshape(n_ves, nr * nz))
        #: the rows are in each measurement row's OWN units — Wb/rad for a
        #: loop, tesla for a probe — and take no ``meas_scale``
        rsi_v, zsi_v = flux_loop_positions()
        v_rows = [np.asarray(device.point_response(ves, rsi_v, zsi_v)[0],
                             float) / (2.0 * np.pi)]
        if wts.size > v_rows[0].shape[0]:
            n_pr = wts.size - v_rows[0].shape[0]
            geo = device.probe_geometry()
            v_rows.append(np.asarray(device.probe_element_response(
                ves, np.asarray(geo["r"], float)[:n_pr],
                np.asarray(geo["z"], float)[:n_pr],
                np.deg2rad(np.asarray(geo["angle_deg"], float)[:n_pr])),
                float))
        v_rows_m = np.vstack(v_rows)
        if vessel_modes is not None:
            #: ★★★A FEW degrees of freedom instead of forty: channel 0 is
            #: the net current, then cos mθ and sin mθ up to
            #: ``vessel_modes``, with θ measured about the machine centre.
            #: A passive structure's eddy pattern is smooth in poloidal
            #: angle; forty free segments are not, and the 40-channel fit
            #: uses that freedom (above).  ``vessel_modes=0`` leaves only
            #: the net current; passing nothing leaves all forty free.
            #:
            #: ★★★AND THE ANSWER IS NO — this is a negative result kept in
            #: the tree because it excludes something.  Every truncation
            #: measured (m <= 0, 1, 2, 3, 5 at sigma_v = 10 kA) leaves the
            #: loop scatter at 3.6…4.0 sigma against 3.82 with no vessel at
            #: all, and the vertical feedback at 51…56 kA against 69.9.  The
            #: coherent up-down dipole the 40-channel fit contains (+15.9 kA
            #: above the midplane, -18.1 kA below) is real, and on its own
            #: it buys 3.82 -> 3.72 sigma.  ⇒ the 40-channel fit's 2.02 was
            #: the INCOHERENT part, i.e. over-fitting.
            zc_all = np.asarray([float(e.z) if hasattr(e, "z") else float(e[0].z)
                                 for e in ves], float)
            rc_all = np.asarray([float(e.r) if hasattr(e, "r") else float(e[0].r)
                                 for e in ves], float)
            th = np.arctan2(zc_all, rc_all - float(device.RCENTR))
            modes = [np.ones_like(th)]
            for m in range(1, int(vessel_modes) + 1):
                modes += [np.cos(m * th), np.sin(m * th)]
            f = np.asarray(modes, float)                    # (n_mode, n_ves)
            v_psi = np.ascontiguousarray(f @ v_psi)
            v_rows_m = np.ascontiguousarray(v_rows_m @ f.T)
            n_ves = f.shape[0]
        coil_block = dict(
            coil_psi=v_psi,
            coil_rows=np.ascontiguousarray(v_rows_m),
            coil_currents=np.zeros(n_ves),
            coil_sigma=np.full(n_ves, float(vessel_sigma)),
            #: ★what a measurement weight of 1.0 stands for.  The deck ships
            #: a 0/1 loop mask, which asserts one Wb/rad; the device
            #: document also ships the real per-loop sigma, and the prior's
            #: strength is meaningless against the wrong one.
            meas_sigma=float(np.median(np.asarray(device.PSIBIT, float))))

    #: ★the FSA rows and the fitted-conductor block are two different ABI
    #: entries, and only one of them can take a given solve.  Say so.
    if coil_block is not None and current_fsa is not None:
        raise TypeError(
            "vessel_sigma= and current_fsa= reach two different kernel "
            "entries (gs_inverse_solve_coils has no FSA-current rows); ask "
            "for one of them")
    fsa_kw = {} if current_fsa is None else dict(
        current_x=_fsa_field(current_fsa, "x"),
        current_shape=_fsa_field(current_fsa, "shape"),
        current_weights=current_fsa.get("weights"))

    #: ★the marshalling is :mod:`fylite.kernel`'s.  This was the last module
    #: outside it that still packed an ABI call itself, and the inverse
    #: solve is the most argument-heavy entry there is — which is exactly
    #: why its buffer sizing and its return-code check should exist once.
    #:
    #: ★★The two entries are written out, not selected into a variable, and
    #: that is not style.  `test_no_scenario_module_reads_a_gfile_key` finds
    #: the kernel's call SITE to decide which reads of ABI names are inside
    #: the boundary and which are a scenario module rummaging in a deck; a
    #: `solve = kernel.a if … else kernel.b` hides the site from it, and
    #: every legitimate unpacking below then reads as a violation.  Measured
    #: the moment the vessel block was added — the gate went red on five
    #: lines that had not changed.
    solve_kw = dict(
        loops_m=lm, meas=b_loops, weights=wts,
        #: loop convention: +full flux / 2 pi
        meas_scale=1.0 / (2.0 * np.pi), npp=npp, nff=nff,
        ip=float(meas["plasma"]), limiter_r=lr, limiter_z=lz,
        pressure_x=None if pres is None else xp,
        pressure_meas=None if pres is None else pmeas,
        pressure_weights=None if pres is None else wp,
        j_prescribed=None if j_pre.size <= 1 else j_pre,
        relax=relax, max_iter=max_iter, tol=tol, fb_gain=fb_gain,
        zc_anchor=zc_anchor, rc_anchor=rc_anchor, warmup=warmup)
    if coil_block is None:
        #: ★the FSA-current constraint (EFIT's KZEROJ/SIZEROJ/VZEROJ at
        #: RZEROJ = 0).  It is a SHAPE — `j/<j>` over the given surfaces —
        #: and the magnitude stays the Ip equality's; the kernel builds the
        #: rows on the surfaces the CURRENT field has, every iteration.
        #: ★★It and the vessel block are DIFFERENT ABI entries, so asking
        #: for both is refused above rather than silently dropping one.
        res = kernel.gs_inverse_solve(rg, zg, psi_ext, **fsa_kw, **solve_kw)
    else:
        res = kernel.gs_inverse_solve_coils(rg, zg, psi_ext, **coil_block,
                                            **solve_kw)
    psi, coefs, it = res["psi"], res["coefficients"], res["iterations"]
    fsa_rows_used = res.get("fsa_rows_used")

    psi_axis, psi_bnd = float(res["psi_axis"]), float(res["psi_bnd"])
    axis_r, axis_z = float(res["axis_r"]), float(res["axis_z"])
    ip = float(res["ip"])
    #: ★★THE MACHINE'S, not a literal.  This was ``meas.get("rcentr", 1.85)``
    #: — and the measurement dict has no ``rcentr`` key at all
    #: (:func:`fylite.fyo.as_measurements` does not write one), so the
    #: default ALWAYS fired and the reference radius of every reconstruction
    #: this package produced was 1.85 m.  EAST's is **1.75 m**, which the
    #: device document says and the reference discharge's own oracle
    #: document agrees with (``vacuum_toroidal_field.r0``).  It is not
    #: cosmetic: ``f_edge = |R₀B₀|`` sets F at the edge, F sets q, and every
    #: delivered ``q``/``fpol``/``rcentr`` was 5.7 % out because of it.
    #: ★It comes from the DOCUMENT and from nowhere else — not from the
    #: measurement dict either.  ``rcentr`` is an EFIT deck spelling, and a
    #: scenario module reading one away from the boundary is what
    #: ``test_no_scenario_module_reads_a_gfile_key`` exists to stop: the
    #: nominal geometric centre is a property of the MACHINE (the device
    #: document's ``machine.r_centre``, which says so and says where it came
    #: from), not of a slice's measurements.  A different machine states it
    #: in its own document.
    r0 = float(device.RCENTR)
    #: ★And B₀ is a MEASUREMENT, so a missing one is refused rather than
    #: guessed.  The old fallback was ``1.75 * 1.8`` — EAST's nominal
    #: vacuum field, written into a machine-neutral module, and it would
    #: have produced a full reconstruction with somebody else's toroidal
    #: field in it without a word.
    b0 = float(meas.get("btor", 0.0))
    if not b0:
        raise KefitRunError(
            "no toroidal field in the measurement set: F at the plasma edge "
            "is |R0 B0| and B0 is measured, not a property of the machine. "
            "Pass 'btor' (T at R0) with the measurements.")
    f_edge = abs(r0 * b0)
    #: ★★THE KERNEL'S SIGN.  ``span_pr`` is ``(psi_axis - psi_bnd)/2pi``
    #: everywhere below the ABI — `inverse.rs` computes exactly that for its
    #: pressure rows (`(psi_b - psi_a)/(-2pi)`), and it is what the closed
    #: form of F requires: d(F²)/dpsi = 2FF' integrates to
    #: ``F² = F_edge² + 2 span_pr A(x)`` only with the axis-minus-boundary
    #: span.  This line had it the other way round, so the two consumers of
    #: it both came out wrong in a way nothing raised: the reported pressure
    #: profile carried the WRONG SIGN (a delivered g-file with negative
    #: pressure — measured −1.065e4 Pa on axis where the fit's own kinetic
    #: rows had matched +1.07e4), and F — hence q — was integrated the wrong
    #: way along psi (F(0) 3.024 instead of 3.610 on the reference
    #: discharge).  ★It survived because the only test of this arithmetic
    #: compares `fit_profiles` against `f_from_coefficients` — and BOTH are
    #: handed this same number, so a sign error cancels inside the check.
    span_perrad = (psi_axis - psi_bnd) / (2.0 * np.pi)
    cff = coefs[npp:]

    def fpol_of_x(x):
        #: the kernel's closed form of the fit's edge-zeroed FF' basis —
        #: exact, where a quadrature would put a discretisation error into
        #: a quantity that has none
        return kernel.f_from_coefficients(cff, x, span_pr=span_perrad,
                                          f_edge=f_edge)

    #: F on the label the kernel reads it on.  A callback cannot cross the
    #: ABI and this profile is what the coefficients mean anyway.
    f_x = np.linspace(0.0, 1.0, 65)
    grid = kernel.grid_of(rg, zg)
    q = kernel.q_profile(grid, psi, psi_axis=psi_axis, psi_bnd=psi_bnd,
                         axis=(axis_r, axis_z), limiter=(lr, lz),
                         f_x=f_x, f_val=np.array([fpol_of_x(v) for v in f_x]),
                         n_q=12, x_lo=0.02, x_hi=0.95)
    li = kernel.li3(grid, psi, psi_axis=psi_axis, psi_bnd=psi_bnd,
                    ip=ip, r0=r0)

    #: ★★The 1-D profiles and the boundary, so the result is a whole
    #: equilibrium rather than a psi map with summary numbers beside it.
    #: Without them a caller holding this dict could not hand it to any model
    #: — `fyo.as_equilibrium` had nothing to build a document from — and the
    #: only bridge was to write a g-file and parse it back, through a fixed
    #: format with fewer digits than a float64.  `loop.py` did exactly that,
    #: twice per iteration.
    #:
    #: ★The basis is the SOLVE's own, read off `inverse.rs`'s current
    #: construction rather than reconstructed from the paper:
    #: `j_phi = R p'(psi) + FF'(psi)/(mu0 R)` is assembled there from
    #: `r * (x^k - x^npp)` and `(x^k - x^nff) / (mu0 r)`, so those ARE the
    #: two edge-zeroed bases and the coefficients need no rescaling.
    #: `test_recon_profiles.py` pins that reading against the kernel's own
    #: `f_from_coefficients` integral, which is an independent path to F.
    prof1d = fit_profiles(coefs, npp=npp, nff=nff,
                          span_perrad=span_perrad, f_edge=f_edge)
    xg1 = prof1d["psin"]
    #: ★q comes off the traced ladder, which spans [x_lo, x_hi] and not the
    #: full [0, 1].  `to_uniform_extrap` is the KERNEL's extrapolation of a
    #: profile traced over an interior range — the same rule that produced
    #: `q0` and `q95` above, rather than a second one invented here.
    qpsi = np.asarray(kernel.to_uniform_extrap(q["x"], q["q"], N_PROFILE), float)
    bnd = kernel.trace_surface(grid, psi, psi_bnd,
                               axis=(axis_r, axis_z), limiter=(lr, lz))
    bpoly = np.asarray(bnd["poly"], float)[:int(bnd["n"])]

    return {
        "backend": "rust", "result_source": "memory",
        "psi": psi, "rgrid": rg, "zgrid": zg,
        "psi_axis": psi_axis, "psi_bry": psi_bnd,
        "rmaxis": axis_r, "zmaxis": axis_z, "ip": ip,
        "q0": q["q0"], "q95": q["q95"], "q_profile": q, "ali": li,
        "coefs": coefs, "npp": npp, "nff": nff,
        "iterations": int(it), "residual": float(res["residual"]),
        #: ★★Whether the Picard loop reached the tolerance IT WAS ASKED FOR,
        #: stated by the code that knows both numbers.  It is here because
        #: the acceptance register needs a criterion this entry can actually
        #: meet: the shipped one scored `terror` and `chi_pressure`, two
        #: fields of the EFIT driver's result that left with the driver, so
        #: every delivered reconstruction came back `unevaluated` on both —
        #: diligent-looking, and scoring nothing.  ★A run that stopped at
        #: `max_iter` with a residual above `tol` is exactly the case a
        #: caller must not read as a settled fit.
        "converged": bool(float(res["residual"]) <= float(tol)),
        "bnd_kind": int(res["bnd_kind"]), "fb_amp": float(res["fb_amp"]),
        #: ★★the RADIAL feedback's amplitude, at last.  This module's own
        #: docstring called out its absence twice as a defect — "a quantity a
        #: solve puts into the answer and does not report is a quantity
        #: nobody can check" — while going on not to report it.  It is zero
        #: on the default path (the radial anchor is a row since
        #: 2026-08-31) and non-zero through `FY_ANCHOR_W=0`, which is
        #: exactly the comparison it is needed for.
        "fb_amp_r": float(res["fb_amp_r"]),
        #: ★how many directions the CONDIN truncation left the fit, out of
        #: `npp + nff + <fitted channels>`; -1 means no fit ran.
        "trunc_keep": int(res["trunc_keep"]),
        #: ★★the fitted vessel currents [A], when they were fitted.  A
        #: quantity a solve puts into the answer and does not report is a
        #: quantity nobody can check.  〔This comment used to add "this path
        #: already has one such — `fb_amp_r`, reported nowhere".  It is
        #: reported now, in the slot beside `fb_amp`.〕
        **({} if "coil_fit" not in res
           else {"vessel_current": np.asarray(res["coil_fit"], float)}),
        "rleft": float(rg[0]), "rdim": float(rg[-1] - rg[0]),
        "zmid": float(0.5 * (zg[0] + zg[-1])),
        "zdim": float(zg[-1] - zg[0]), "nw": nr, "nh": nz,
        #: ★WHERE THE MACHINE CAME FROM — one directory, because there is
        #: now one source.  This field used to be the Green-table directory
        #: (``tables``), which named a second place device facts could come
        #: from; the last read from one is gone, so what a result has to
        #: record is the device description it was fitted against.
        "device": str(device.data_dir()),
        #: ★None when no current constraint was asked for; a NUMBER when
        #: one was — and it is the number of rows that reached the fit, not
        #: the number requested.
        "fsa_rows_used": fsa_rows_used,
        #: the whole equilibrium: profiles on a uniform psi_N grid, and the
        #: boundary this solve actually settled on
        #: ★the result dict keeps EFIT's spellings — it is a wire contract
        #: (`engine.cli`, `engine.serve`) and renaming it is a separate,
        #: user-visible change.  `fyo.reconstruction` is where they stop.
        "psin_1d": xg1, "fpol": prof1d["f"], "pres": prof1d["pressure"],
        "ffprim": prof1d["f_df_dpsi"], "pprime": prof1d["dpressure_dpsi"],
        "qpsi": qpsi,
        "rbbbs": bpoly[:, 0], "zbbbs": bpoly[:, 1],
        "rcentr": r0, "bcentr": b0,
        "rlim": np.asarray(lr, float), "zlim": np.asarray(lz, float),
    }


#: ★``bootstrap_source`` was here: 134 lines putting NEO's bootstrap SHAPE on
#: the grid with a caller-supplied magnitude (``f_bs``).  Deleted 2026-08-21.
#:
#: It had NO CALLER and NO TEST, and the argument its docstring made for the
#: shape/magnitude split had just expired: "this package has never
#: denormalized NEO's absolute ``<j_par B>``" stopped being true when
#: :func:`fylite.kernel.neo_current_unit` landed and was checked against the
#: standard bootstrap-fraction estimate.  So what remained was untested,
#: unreachable code justified by a fact that no longer held — the shape of
#: thing that is kept out of politeness and then trusted by somebody.
#:
#: What replaces it, for a caller who wants a bootstrap current on a grid:
#: :func:`fylite.fyo.neoclassical_source` for the profile (in A/m², from any
#: of the four backends), handed to :func:`reconstruct`'s ``current_source=``,
#: which is the per-interior-cell array the solve actually takes.



# ---------------------------------------------------------------------------
# Orchestration over a scan
#
# ★★This came out of the deleted EFIT driver, and it belongs here rather than
# there.  Running a list of times, isolating a slice that blew up, keeping a
# structured per-slice report and resuming from a prior one — none of that is
# equilibrium solving.  It is ORCHESTRATION, which under the architecture the
# project settled on is Python's half of the split, while physics and numerics
# live in the kernel.  It went out with run.py only because that is where it
# happened to be written, and it comes back attached to the solver that
# survived.
# ---------------------------------------------------------------------------

def _slice_status(result: dict) -> tuple[str, dict]:
    """Reduce one slice's per-diagnostic status → (``ok``|``partial``, detail)."""
    diag = result.get("diagnostic_status") or {}
    bad = {n: s for n, s in diag.items() if s.get("status") != "ok"}
    return ("partial" if bad else "ok"), diag

def reconstruct_shot(shot: int, time_s: float, **kw) -> dict:
    """Reconstruct one EAST slice from the tree: measurements, then the solve.

    The shot/time door.  :func:`_east_measurements` assembles the slice and
    :func:`reconstruct` fits it; this composes the two and merges the
    measurement side's extras (``ne_profile``, ``diagnostic_status``, the
    POINT/pressure provenance) into the result, which is where every caller
    expects them.

    Keyword arguments are routed by name — the two signatures share none, so
    the split is unambiguous — and an unknown one RAISES rather than being
    dropped into either half.

    ★★Why it did not exist.  This was the EFIT driver's job, and the driver
    left with LICENSE 3.1; the two halves survived and nothing rejoined them.
    Both remaining callers went on calling the driver's signature —
    :func:`run_series` as ``reconstruct(shot, t, ...)`` and
    ``loop.self_consistent`` through its ``_efit_run`` alias — so both raised
    ``TypeError`` on their first statement.  Neither was noticed: the loop's
    three test modules all stub the seam, and `run_series`' own call was a
    module-LOCAL one, which `test_call_sites_match.py` did not look at until
    it was taught to.
    """
    import inspect
    meas_kw, rec_kw = {}, {}
    m_par = set(inspect.signature(_east_measurements).parameters)
    r_par = set(inspect.signature(reconstruct).parameters)
    for k, v in kw.items():
        if k in m_par:
            meas_kw[k] = v
        elif k in r_par:
            rec_kw[k] = v
        else:
            raise TypeError(
                f"reconstruct_shot() got an unexpected keyword argument {k!r}; "
                f"it routes to _east_measurements({sorted(m_par - {'shot', 'time_s'})}) "
                f"or reconstruct({sorted(r_par - {'meas'})})")
    meas, extra = _east_measurements(shot, time_s, **meas_kw)
    res = reconstruct(meas, **rec_kw)
    #: ★the measurement extras ride on the result, not beside it: a caller
    #: holding one dict should not need a second to find out which
    #: diagnostics fetched.
    return {**res, **extra, "shot": int(shot), "time_s": float(time_s)}


def reconstruct_input(source, time_s=None, *, kind=None, shot=None,
                      **kw) -> dict:
    """The INPUT door: whatever a caller has → one reconstruction.

    ``source`` is a measurement dict, a measurement FILE (IMAS-shaped JSON /
    YAML or a JSON-LD normal form), or a shot number; ``kind`` names the mode
    explicitly and defaults to :func:`_infer_kind`\'s reading of ``source``.
    Extra keywords are routed exactly as :func:`reconstruct_shot` routes them
    — to the measurement assembly or to the solve, by name, with an unknown
    one raising rather than being dropped.

    ★★Why a third door when there are already two.  ``reconstruct`` takes
    measurements and ``reconstruct_shot`` takes a shot and a time; what the
    CLI and the MCP tool have is neither — they have a *mode* the user chose
    (``--east`` / ``--input`` / a bare shot) and an argument whose meaning
    depends on it.  Both faces were resolving that mode themselves, and both
    resolved it into the signature of the EFIT driver that left with
    LICENSE 3.1 (``kind=`` / ``out=`` / ``preset=``), so **every** invocation
    of ``fylite run`` and of the ``fylite_run`` tool raised ``TypeError`` on
    its first statement, in all four modes.  Mode resolution is one thing,
    it belongs on the solver's side of the seam, and it belongs in ONE place
    — which is also the only way the call-site gate can see it.

    ★What this door does NOT do: write anything.  Delivery (a g-file, a
    figure, a run manifest) is the engine's half — ``fylite.fyo.as_geqdsk``
    plus ``fylite.io.geqdsk.write_geqdsk`` for the deck — so that the same
    result can be delivered in more than one shape without this function
    growing an opinion about which.
    """
    kind = kind or _infer_kind(source)

    #: ★★No ``tables()`` helper any more, and no table directory to resolve.
    #: It existed to defer the deck lookup per branch — the mode that
    #: refuses (``kfile``) must say why it refuses rather than report a
    #: missing deck — and that deferral is now the machine's own: every
    #: device fact is read on first use, inside the branch that solves.
    if kind == "measurements":
        res = reconstruct(source, **kw)
        stamp = {k: v for k, v in (("shot", shot), ("time_s", time_s))
                 if v is not None}
        return {**res, **stamp}

    if kind == "imas":
        if time_s is None:
            raise KefitRunError(
                "a measurement file is a time-resolved document: pass the "
                "time [s] to evaluate it at")
        from ... import fyo
        meas = fyo.as_measurements(source, float(time_s))
        res = reconstruct(meas, **kw)
        return {**res, "time_s": float(time_s),
                **({"shot": int(shot)} if shot is not None else {})}

    if kind == "east":
        n = int(source) if shot is None else int(shot)
        if time_s is None:
            raise KefitRunError("east mode needs a time [s]")
        return reconstruct_shot(n, float(time_s), **kw)

    if kind == "shot":
        n = int(source) if shot is None else int(shot)
        if time_s is None:
            raise KefitRunError("shot mode needs a time [s]")
        meas = mds.fetch_measurements(n, float(time_s))
        res = reconstruct(meas, **kw)
        return {**res, "shot": n, "time_s": float(time_s)}

    if kind == "kfile":
        #: ★A k-file is an EFIT NAMELIST — an input written for the solver
        #: that left with LICENSE 3.1.  This package can still WRITE one
        #: (an EFIT `&IN1` writer, for a host that has that solver — this
        #: distribution no longer carries one) and can
        #: parse its groups, but it has no reader that turns one back into a
        #: measurement set, so there is nothing here to hand the Rust
        #: inverse.  Saying so is the whole answer; guessing at the rows
        #: would produce a solve from measurements nobody supplied.
        raise KefitRunError(
            "k-file input is not available in this distribution: a k-file is "
            "the EFIT driver's namelist (LICENSE 3.1) and there is no reader "
            "that recovers a measurement set from one. Pass the measurements "
            "themselves — an IMAS-shaped or JSON-LD document (kind='imas'), "
            "a measurement dict, or a shot and a time.")

    raise KefitRunError(
        f"unknown input mode {kind!r}; expected one of 'measurements', "
        "'imas', 'east', 'shot'")


def run_series(shot: int, times, *, resume=None, keep_going: bool = True,
               require_diagnostics: bool = False, **kw) -> dict:
    """Multi-slice driver (K-6) with partial-success + stage recovery (K-16).

    Runs :func:`reconstruct_shot`(``shot``, t, ``**kw``) for each t in ``times``
    — ★it said ``run``, the EFIT driver's name, while the body has called
    ``reconstruct_shot`` since the shot/time door was rejoined — and collects
    the per-slice results plus aligned time-series of the key scalars (the GUI
    accumulates rmaxis/ip/q95/li/betap/chi2/... per slice and gates acceptance on
    its convergence measure).

    Partial success (K-16): each slice gets a structured **report** with a
    ``status`` — ``ok`` (all requested diagnostics fetched), ``partial`` (the
    fit ran but a diagnostic was missing/failed; ``require_diagnostics=False`` is
    the default here so one dead diagnostic never loses the slice), or ``failed``
    (the reconstruction itself raised — the error + traceback are retained).
    ``keep_going`` (default) isolates a failed slice; ``keep_going=False`` is
    fail-fast.  ``resume=`` takes a prior ``run_series`` result and **skips the
    slices it already completed** (status ``ok``/``partial``), re-running only the
    failed/missing ones — stage-level recovery over a scan.

    Output files: pass ``out=`` as usual — per-slice g/a-file names embed the
    time so one directory collects the whole scan.  For tight scans prefer
    passing ``tables=`` once (the Green set resolves from cache per call).
    """
    import traceback

    prior = {}
    if resume:
        for rep in resume.get("reports", []):
            if rep.get("status") in ("ok", "partial"):
                prior[round(float(rep["time_s"]), 6)] = rep

    results: list = []
    failed: list = []
    reports: list = []
    for t in times:
        t = float(t)
        key = round(t, 6)
        if key in prior:                              # resume: reuse completed slice
            rep = dict(prior[key], resumed=True)
            reports.append(rep)
            results.append(rep.get("result"))
            continue
        try:
            r = reconstruct_shot(shot, t,
                                require_diagnostics=require_diagnostics,
                                **kw)
            status, diag = _slice_status(r)
            results.append(r)
            reports.append({"time_s": t, "status": status, "result": r,
                            "diagnostic_status": diag})
        except Exception as e:                        # noqa: BLE001 — per-slice isolation
            if not keep_going:
                raise
            err = f"{type(e).__name__}: {e}"
            log = getattr(e, "log", None)
            rec = {"time_s": t, "error": err,
                   "traceback": traceback.format_exc().splitlines()[-8:],
                   "log_tail": (log.splitlines()[-8:] if isinstance(log, str) else None)}
            failed.append(rec)
            reports.append({"time_s": t, "status": "failed", "result": None,
                            **rec})
            results.append(None)
    keys = ("q0", "q95", "ip", "psi_bry", "rmaxis", "zmaxis", "chisq",
            "chi_pressure", "chi_nel", "betap", "ali", "wplasm", "terror")
    series = {k: [None if r is None else r.get(k) for r in results]
              for k in keys}
    counts = {s: sum(rep["status"] == s for rep in reports)
              for s in ("ok", "partial", "failed")}
    return {"shot": int(shot), "times": [float(t) for t in times],
            "results": results, "reports": reports, "series": series,
            "failed": failed, "n_ok": sum(r is not None for r in results),
            "n_partial": counts["partial"], "n_failed": counts["failed"]}


def _east_measurements(shot: int, time_s: float, *, server=None,
                       window_ms: float = 5.0, btor=None,
                       read_point: bool = False, point_opts=None,
                       point_window_ms=None, point_fringe_gate: float = 0.15,
                       read_pressure: bool = False, pressure_opts=None,
                       read_thomson_ne: bool = False,
                       thomson_ne_opts=None,
                       require_diagnostics: bool = True) -> tuple[dict, dict]:
    """Build one est2/GUI_v5 slice's measurement dict (+result extras).

    The GUI_v5 est2 path — self-contained, no fydata: 79 probes / 35 loops /
    12 PF straight from the `east` tree.  ``read_point`` adds the 11-chord
    POINT interferometry + Faraday internal-current constraint;
    ``read_pressure`` the Thomson+TXCS kprfit=1 pressure rows (assumptions
    declared in ``meas["pressure"]``); ``read_thomson_ne`` the Ts(ne)
    density-spline rows (needs POINT — the spline runs under KNELCUR=1).
    ★Shared by nothing any more: this said "the ``run`` east branch and
    ``east_kfile``", and neither exists — both left with the EFIT driver.
    :func:`reconstruct_shot` is the shot/time door now.

    ``require_diagnostics`` (default True) aborts on any requested diagnostic
    that fails to fetch — the strict behaviour.  Passing ``False`` (partial
    success, K-16) records each optional Thomson-based diagnostic's outcome in
    ``extra["diagnostic_status"]`` (``ok`` / ``missing`` / ``failed`` + reason /
    dropped-channel count) and proceeds with whatever fetched, so one dead
    diagnostic does not lose the whole slice.
    """
    #: ★there used to be a second probe family here (``probe_source="pcs"``,
    #: the already-calibrated PCS array mapped onto est2 slots).  The two
    #: readers it called have no definition in this distribution, so the
    #: branch could only raise `NameError` — an option that names a
    #: capability nobody can reach is worse than no option.
    meas = est2.read_east_mds(
        shot, time_s, server=server, window_ms=window_ms, btor=btor,
        read_point=read_point, point_window_ms=point_window_ms,
        point_fringe_gate=point_fringe_gate)
    extra: dict = {}
    status: dict = {}                                # per-diagnostic outcome (K-16)
    if read_point and point_opts:
        meas["point_opts"] = dict(point_opts)
    if read_point:
        if meas.get("point"):
            extra["point_chords"] = (meas["point"]["n_ne_active"],
                                     meas["point"]["n_fr_active"])
            status["point"] = {"status": "ok"}
        else:
            status["point"] = {"status": "missing", "reason": "no POINT chords"}
    if read_thomson_ne and not read_point:
        raise ValueError("thomson_ne=True needs point=True — the density "
                         "spline only runs in the POINT fit (KNELCUR=1)")

    def _optional(name: str, fn):
        """Run one optional-diagnostic builder; strict → raise, else record."""
        try:
            fn()
            status.setdefault(name, {"status": "ok"})
        except Exception as e:                       # noqa: BLE001 — partial-success path
            if require_diagnostics:
                raise
            status[name] = {"status": "failed",
                            "reason": f"{type(e).__name__}: {e}"}

    th = None
    if read_pressure or read_thomson_ne:
        def _fetch_th():
            nonlocal th
            th = mds.fetch_thomson(shot, time_s, server=server)
            extra["thomson_time_s"] = th["sample_time_s"]
        _optional("thomson", _fetch_th)

    if read_pressure and th is not None:
        def _build_pressure():
            meas["pressure"] = mds.pressure_from_thomson(th, **(pressure_opts or {}))
            extra["pressure_points"] = meas["pressure"]["n_points"]
            extra["pressure_dropped"] = meas["pressure"].get("n_dropped")
            extra["pressure_ion_factor"] = meas["pressure"]["ion_factor"]
            extra["pressure_sigma_source"] = meas["pressure"]["sigma_source"]
            extra["pressure_assumptions"] = meas["pressure"]["assumptions"]
        _optional("pressure", _build_pressure)
    elif read_pressure:
        status["pressure"] = {"status": "missing", "reason": "no Thomson fetch"}

    if read_thomson_ne and th is not None:
        def _build_thomson_ne():
            meas["thomson_ne"] = mds.thomson_ne_points(th, **(thomson_ne_opts or {}))
            extra["thomson_ne_points"] = meas["thomson_ne"]["n_points"]
            extra["thomson_ne_dropped"] = meas["thomson_ne"].get("n_dropped")
            extra["thomson_ne_sigma_source"] = meas["thomson_ne"]["sigma_source"]
        _optional("thomson_ne", _build_thomson_ne)
    elif read_thomson_ne:
        status["thomson_ne"] = {"status": "missing", "reason": "no Thomson fetch"}

    if status:
        extra["diagnostic_status"] = status
    return meas, extra


# ---------------------------------------------------------------------------
# ★Measurement assembly and per-probe self-calibration, back from the deleted
# driver for the same reason the scan orchestration was: neither is solving.
# Pulling the diagnostic signals a fit will see, and comparing a probe's
# forward-modelled reading against its measured one, are data assembly and
# analysis — Python's half of the split. They depend on nothing Fortran; they
# were deleted only for sharing a file with the solver.
# ---------------------------------------------------------------------------

def _diagnostic_signals(meas: dict, afile: dict, result: dict,
                        namelist: dict | None = None) -> dict:
    """Measured-vs-reconstructed signal per diagnostic family (for the report
    figure).  Pairs each measurement vector with its forward-model counterpart:
    flux loops (``coils`` vs a-file ``csilop``), magnetic probes (``expmp2`` vs
    ``cmpr2``, alive-masked by ``fwtmp2``), and — when POINT ran — Faraday
    (``bpolar`` vs ``faraday_forward``) and interferometry line density
    (``bnel`` vs ``nel_forward``).  Each family carries measured/computed arrays
    + an alive mask + a unit label; families with no forward output are omitted.

    ``namelist`` is the **effective** fit namelist handed to the solver.  The
    alive mask must be what the solver actually weighted, not what the data
    gate allowed: a run that sets ``FWTMP2=0`` (the loops-only benchmark) still
    has live probe *signals*, and reporting those as "used" would credit the fit
    with 21 constraints it never saw.  Any ``FWTMP2``/``FWTSI`` override
    therefore ANDs into the mask.
    """
    fam: dict = {}

    def _fwt(key):
        w = (namelist or {}).get(key)
        return None if w is None else [float(v) > 0 for v in np.atleast_1d(w)]

    def _and(a, b):
        if a is None:
            return b
        if b is None:
            return a
        n = min(len(a), len(b))
        return [bool(a[i] and b[i]) for i in range(n)]

    def _pair(key, measured, computed, unit, alive=None):
        if not measured or not computed:
            return
        n = min(len(measured), len(computed))
        fam[key] = {
            "measured": [float(v) for v in measured[:n]],
            "computed": [float(v) for v in computed[:n]],
            "alive": ([bool(a) for a in alive[:n]] if alive is not None
                      else [True] * n),
            "unit": unit}

    _pair("flux_loops", meas.get("coils"), afile.get("csilop"), "Wb/rad",
          alive=_fwt("FWTSI"))
    _pair("mag_probes", meas.get("expmp2"), afile.get("cmpr2"), "T",
          alive=_and([w > 0 for w in meas.get("fwtmp2", [])], _fwt("FWTMP2")))
    pt = meas.get("point") or {}
    _pair("faraday", pt.get("bpolar"), result.get("faraday_forward"),
          "deg/1e19")
    _pair("interferometry", pt.get("bnel"), result.get("nel_forward"),
          "1e19 m^-2")
    return fam

#: ★``_selfcal_factors`` sat here forwarding to `selfcal.factors_single`,
#: which was itself a forward to the kernel — a two-hop alias with no
#: caller left once the middle hop went.  Nothing referenced it.


#: ★Input dispatch: which run mode a caller's `source` argument implies.
#: Still happens — reconstruct() takes the same argument shapes the driver
#: did — so it belongs here rather than having gone with the driver.
def _infer_kind(source) -> str:
    """Guess the run mode from the ``source`` argument's shape."""
    if isinstance(source, dict):
        return "measurements"
    if isinstance(source, bool) or not isinstance(source, (int, str, Path)):
        raise ValueError(
            f"cannot infer an input mode from source={source!r}; pass kind= "
            "('measurements' / 'imas' / 'east' / 'shot')")
    if isinstance(source, int):
        return "east"
    return ("imas" if Path(source).suffix.lower()
            in (".json", ".jsonld", ".yaml", ".yml") else "kfile")
