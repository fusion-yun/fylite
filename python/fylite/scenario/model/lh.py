"""Analytic lower-hybrid current drive (K-20) — the LH branch of ``j_CD``.

EAST is a long-pulse LHCD machine: with no ``j_LH`` term the self-consistent
outer loop attributes that driven current to the ohmic or bootstrap channel and
biases ``q(ψ)``.  This module supplies the term analytically, at the same
fidelity tier as :mod:`fylite.scenario.model.nbi` — a documented physics chain rather than a
ray-tracing/Fokker-Planck code (LSC, GENRAY/CQL3D), which is out of scope here.

The chain, and where each piece comes from:

* **Accessibility** — a slow wave reaches a surface only where
  ``n_∥ > n_∥,acc = ω_pe/ω_ce + sqrt(1 + ω_pe²/ω_ce²)`` (the standard
  lower-hybrid accessibility condition).  Surfaces failing it get no power.
* **Damping location** — the wave damps by electron Landau damping where its
  parallel phase velocity meets the resonant tail, ``c/n_∥ ≈ ξ v_th,e`` with
  ``v_th,e = sqrt(2 T_e/m_e)`` and ``ξ ≈ 3`` (damping turns on around 2.5–3.5).
  That fixes a **resonant temperature** ``T_res = m_e c²/(2 ξ² n_∥²)`` and hence a
  radius, wherever ``T_e(ψ)`` crosses it.
* **Deposition width and its uncertainty** — the launcher does not emit one
  ``n_∥`` but a band, and multi-pass propagation up-shifts it.  Evaluating the
  resonance at both ends of the band gives a *radial interval*, which this module
  reports as the deposition width **and** as the per-surface ``sigma_j``.  The
  uncertainty is therefore derived from the machine's own launcher spectrum, not
  assumed.
* **Magnitude** — from the measured absorbed power via the current-drive
  efficiency ``η_CD ≡ n̄_e R₀ I_LH / P_abs`` (Fisch's figure of merit), with the
  local weighting ``j/p ∝ T_e/n_e`` that Fisch-type theory gives.  ``eta_cd`` is
  **required from the caller** — the coefficient is machine- and
  scenario-calibrated and is not fabricated here (same discipline as
  :func:`fylite.scenario.model.nbi.east_beams` and its tangency radii).

**How the result may be used.** ``j_lh`` is delivered as a *result channel*.  It
must **not** be folded into the loop's ``VZEROJ`` target as a fixed forcing term:
the deposition location is the least certain of the four wave sources, so the
term belongs in the fit as a soft prior with a radial σ — and EFIT's FSA-current
channel takes only one scalar weight for the whole block (``FWTXXJ``; see
EFIT 的 ``&INWANT`` 键集，本发行版不再带), so a radial σ is not expressible there
yet.  Until it is, use ``j_lh``/``sigma_j`` for attribution and diagnosis.

Limitations, stated rather than hidden: single-pass Landau resonance (no ray
tracing, no explicit up-shift model beyond the launcher band), no ion damping, no
electron-trapping correction to the efficiency, no LH-induced fast-electron
pressure, and the antenna's poloidal position is unknown (`[TBD]`, see
:data:`fylite.device.LH_SYSTEMS`), so the deposition is treated as a flux
function.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
import numpy as np

from ... import kernel
from .nbi import _surface_table

#: Electron rest energy in eV.
#:
#: ★It is NOT used by this module — every number here comes from the kernel,
#: which has its own `ME_C2_EV`.  It is kept, and kept public, because
#: `test_lh.py` builds its expected `resonant_te_ev` from it: that is the
#: one place the kernel's constant is checked against an independently
#: written value rather than against itself.  Delete it as "unused" and the
#: check goes with it, silently.  (`E_CHARGE` and `C_LIGHT` sat beside it
#: with no such job and have been removed.)
ME_C2_EV = 510998.95

#: ★★``EAST_LH_SYSTEMS`` was here: a tuple of dicts carrying EAST's two LH
#: systems — frequencies, nameplate powers, ``n_∥`` bands, ports and MDSplus
#: node names — as the DEFAULT ARGUMENT of :func:`east_launchers`.  A machine
#: description in a function signature, in a package whose README opens with
#: "No machine description".
#:
#: It moved into the device document on 2026-08-21
#: (``lh_antennas.antenna``, read as :data:`fylite.device.LH_SYSTEMS`), where
#: the POINT interferometer's channels and node names already live.  A caller
#: with no device deck now gets :class:`fylite.device.MachineDataMissing`
#: rather than EAST's numbers.
#:
#: ★The machine-neutrality scan did not catch it: it looks for nine SPECIFIC
#: literals that leaked out of ``_east_device.py`` once, so it can only
#: re-find that leak.  ``PLHI1`` was never on the list.

class LHError(ValueError):
    """A launcher configuration or plasma state that cannot be evaluated."""


@dataclass
class Launcher:
    """One LH launcher: frequency, absorbed power, and its ``n_∥`` band.

    ``power_w`` is the **absorbed** power (injected − reflected), because that is
    what drives current; ``n_parallel`` is the band ``(min, max)`` the launcher
    emits, which sets both the deposition width and its uncertainty.
    """
    name: str
    frequency: float                       # Hz
    power_w: float                         # W, absorbed
    n_parallel: tuple[float, float]

    def __post_init__(self) -> None:
        lo, hi = (float(self.n_parallel[0]), float(self.n_parallel[1]))
        if not 0.0 < lo <= hi:
            raise LHError(f"{self.name}: bad n_parallel band {self.n_parallel}")
        if self.power_w < 0.0:
            raise LHError(f"{self.name}: negative absorbed power {self.power_w}")
        self.n_parallel = (lo, hi)

    @property
    def n_parallel_mid(self) -> float:
        return 0.5 * (self.n_parallel[0] + self.n_parallel[1])


def east_launchers(injected_w, *, reflected_w=0.0, systems=None):
    """Build EAST :class:`Launcher` objects from measured powers.

    ``injected_w``/``reflected_w`` are scalars or per-system sequences in **W**
    (the MDSplus nodes carry kW — convert before calling).  Systems with no
    absorbed power are dropped, so a shot that ran only the 4.6 GHz system needs
    no special casing.  Powers above a system's nameplate maximum raise.

    ``systems`` defaults to the DEVICE DOCUMENT's ``lh_antennas.antenna``
    (:data:`fylite.device.LH_SYSTEMS`).  ★It used to default to a literal
    tuple in this module, so this function answered for EAST whether or not a
    machine description was present; now a caller without one is told so.
    """
    if systems is None:
        from ... import device
        systems = device.LH_SYSTEMS
    n = len(systems)
    inj = np.broadcast_to(np.asarray(injected_w, float), (n,))
    ref = np.broadcast_to(np.asarray(reflected_w, float), (n,))
    out = []
    for spec, pi, pr in zip(systems, inj, ref):
        if pi > spec["max_power"] * 1.001:
            raise LHError(f"{spec['name']}: injected {pi/1e6:.2f} MW exceeds the "
                          f"{spec['max_power']/1e6:.1f} MW nameplate maximum")
        absorbed = float(pi) - float(pr)
        if absorbed <= 0.0:
            continue
        out.append(Launcher(name=spec["name"], frequency=spec["frequency"],
                            power_w=absorbed, n_parallel=spec["n_parallel"]))
    return out


# --------------------------------------------------------------------------- #
# Wave physics
# --------------------------------------------------------------------------- #
def resonant_te_ev(n_parallel, xi: float = 3.0) -> np.ndarray:
    """Electron temperature at which Landau damping resonates for ``n_∥``.

    ``c/n_∥ = ξ v_th,e`` with ``v_th,e = sqrt(2T_e/m_e)`` gives
    ``T_res = m_e c² / (2 ξ² n_∥²)``.  Larger ``n_∥`` (or a stronger
    up-shift) resonates at *lower* temperature, i.e. further out.  The
    kernel's."""
    n = np.atleast_1d(np.asarray(n_parallel, float))
    out = np.array([kernel.lh_accessibility([1e19], [2.0], n_parallel=float(v),
                                            xi=xi)["t_resonant"] for v in n])
    return out.reshape(np.shape(n_parallel)) if np.shape(n_parallel) \
        else float(out[0])


def _effective_band(band, upshift) -> tuple[float, float]:
    """Launched ``n_∥`` band scaled by the up-shift (scalar or ``(min, max)``).

    A range widens the band, so the deposition width and ``sigma_j`` grow with
    the up-shift uncertainty rather than ignoring it."""
    lo, hi = float(band[0]), float(band[1])
    if np.isscalar(upshift):
        u_lo = u_hi = float(upshift)
    else:
        u_lo, u_hi = float(upshift[0]), float(upshift[1])
    if not 0.0 < u_lo <= u_hi:
        raise LHError(f"bad upshift {upshift!r} — need 0 < min <= max")
    return (lo * u_lo, hi * u_hi)


#: ★``_gaussian`` stood here — a three-line deposition profile with no
#: caller in the package or the tests.  The kernel's ``lh_deposit`` places
#: the drive; this was the shape the Python side used before it did.


# --------------------------------------------------------------------------- #
# Deposition + driven current
# --------------------------------------------------------------------------- #
def deposit(eq, ne, te, launchers, *, eta_cd, psin_prof=None, xi: float = 3.0,
            upshift=1.0, n_shells: int = 24,
            width_floor: float = 0.05,
            cd_model: str = "fisch") -> dict | None:
    """LH power deposition and driven current on a ψ_N grid.

    ``eq`` an ``fyo:equilibrium`` document (or a g-file at the door); ``ne``
    (m⁻³) / ``te`` (eV) on ``psin_prof``;
    ``launchers`` one :class:`Launcher` or a list (see :func:`east_launchers`).

    ``upshift`` scales the launched ``n_∥`` band to the value that actually damps.
    It matters more than any other input: EAST's launchers emit ``n_∥ ≈ 1.8–2.4``,
    which by :func:`resonant_te_ev` resonates at **4.8–8.8 keV** — above the
    plasma — so a strict single-pass model (``upshift=1.0``, the default) finds no
    resonant surface and deposits nothing.  Real LHCD damps after multi-pass
    propagation up-shifts ``n_∥``; passing a factor (or a ``(min, max)`` range,
    which *widens* the effective band and therefore ``sigma_j``) states that
    assumption explicitly instead of burying it.  A range is the honest form: the
    up-shift factor is itself poorly known, and it dominates the deposition
    location — the very reason K-20 requires this term to enter a fit softly.

    ``eta_cd`` is the current-drive figure of merit ``n̄_e R₀ I_LH / P_abs`` in
    **A W⁻¹ m⁻²** — required, not defaulted: it is the calibrated coefficient of
    this model (EAST LHCD values are of order ``1e19``; the ledger tracks it as
    ``[TBD]`` pending a shot-matched calibration).  ``xi`` is the Landau
    resonance multiple ``v_∥/v_th,e``.

    ``cd_model`` names the local current-drive weighting the kernel applies
    inside the resonant layer (``"fisch"`` = ``T_e/n_e``, the default and
    the only one so far).  ★It is an argument rather than a line of
    arithmetic here because it is the one place in this chain where a
    different CD model changes the answer.

    Returns ``None`` when no launcher deposits (no absorbed power, or no
    accessible resonant surface) — a result, not a failure.  Otherwise a dict on
    the shell-centre grid ``psin``:

    ``j_lh`` / ``sigma_j``
        driven current density (A/m²) and its per-surface uncertainty, the latter
        the spread between the two ends of each launcher's ``n_∥`` band.
    ``p_dep``
        absorbed power density (W/m³).
    ``i_lh`` / ``p_absorbed``
        driven current (A) and absorbed power (W), integrated over the plasma.
    ``n_parallel_accessible`` / ``resonance``
        the accessibility limit per surface and, per launcher, where the band
        resonates — the two things to look at when the profile surprises you.
    ``per_launcher``
        the same summary per system, for attribution.
    """
    from ... import fyo
    doc = fyo.as_equilibrium(eq)
    if isinstance(launchers, Launcher):
        launchers = [launchers]
    launchers = [l for l in launchers if l.power_w > 0.0]
    if not launchers:
        return None
    if eta_cd is None:
        raise LHError(
            "deposit: eta_cd is required — the LH current-drive efficiency "
            "n_e R0 I/P is a calibrated coefficient (order 1e19 A/W/m^2 for "
            "EAST LHCD) and is not defaulted here")

    ne = np.asarray(ne, float)
    te = np.maximum(np.asarray(te, float), 1.0)
    if psin_prof is None:
        psin_prof = np.linspace(0.0, 1.0, len(ne))
    psin_prof = np.asarray(psin_prof, float)

    edges = np.linspace(0.0, 1.0, int(n_shells) + 1)
    psin_c = 0.5 * (edges[:-1] + edges[1:])
    table = _surface_table(doc, edges)
    dvol = np.maximum(table["dvolume"], 1e-9)
    rmaj_c = 0.5 * (table["rmajor"][:-1] + table["rmajor"][1:])
    ne_c = kernel.interp(psin_c, psin_prof, ne)
    te_c = kernel.interp(psin_c, psin_prof, te)
    #: |F(ψ)| per shell; the kernel reads |B| ~ F/R off it (the toroidal
    #: field dominates accessibility, B_t >> B_p), together with dS = dV/2πR
    fpol = np.abs(fyo.profile_of(doc, "f"))
    f_c = kernel.interp(psin_c, np.linspace(0.0, 1.0, len(fpol)), fpol)

    r0 = fyo.field_of(doc)[0] or fyo.axis_of(doc)[0] or 1.75
    ne_bar = float(np.average(ne_c, weights=dvol))

    #: ★★The whole per-launcher chain is ONE kernel call
    #: (:func:`fylite.kernel.lh_deposit`): resonance at both band ends, the
    #: accessibility gate, the damping layer, the CD weighting, the
    #: normalisation, and the sigma envelope.  It used to be this loop, six
    #: kernel calls deep, with the arithmetic between them here — which made
    #: the chain, not its pieces, the thing that could differ between hosts.
    bands = [_effective_band(l.n_parallel, upshift) for l in launchers]
    dep = kernel.lh_deposit(psin_c, dvol=dvol, rmaj=rmaj_c, ne=ne_c, te=te_c,
                            f_pol=f_c, bands=bands,
                            powers=[l.power_w for l in launchers],
                            eta_cd=float(eta_cd), r0=r0, xi=xi,
                            width_floor=width_floor, cd_model=cd_model)
    j_lh, sigma_j, p_dep = dep["j_lh"], dep["sigma_j"], dep["p_dep"]
    n_acc = dep["n_acc"]

    per_launcher = []
    for k, lau in enumerate(launchers):
        res = {tag: (None if np.isnan(v) else float(v)) for tag, v in
               (("lo", dep["res_lo"][k]), ("hi", dep["res_hi"][k]))}
        per_launcher.append({
            "name": lau.name, "frequency": lau.frequency,
            "p_absorbed": lau.power_w, "n_parallel": lau.n_parallel,
            "n_parallel_effective": bands[k], "resonance_psin": res,
            "i_lh": float(dep["i_lau"][k]),
            "t_resonant_ev": {t: float(resonant_te_ev(n, xi)) for t, n in
                              (("lo", bands[k][0]), ("hi", bands[k][1]))}})

    return {
        # False == the launchers had power but nothing resonated/was accessible.
        # The diagnostics below say why (compare t_resonant_ev with max(te), and
        # n_parallel_effective with n_parallel_accessible) — far more useful than
        # returning None at this point.
        "deposited": bool(np.any(j_lh)),
        "psin": psin_c, "psin_edges": edges, "dvolume": dvol,
        "j_lh": j_lh, "sigma_j": sigma_j, "p_dep": p_dep,
        "i_lh": dep["i_lh"],
        "p_absorbed": float(sum(l.power_w for l in launchers)),
        "n_parallel_accessible": n_acc,
        "eta_cd": float(eta_cd), "xi": float(xi),
        "per_launcher": per_launcher,
    }


# --------------------------------------------------------------------------- #
# Wave-source model (K-18/K-20 named it a "wave_source" backend; the
# registry is retired — FYL-SDD-01 DE-LOG-03, and the family's other member
# was a null object) — an adapter over this module's LH drive model.
# --------------------------------------------------------------------------- #

from typing import Protocol as _Protocol
from typing import runtime_checkable as _runtime_checkable


@_runtime_checkable
class WaveSource(_Protocol):
    """An RF current-drive backend — lower hybrid above all.

    Distinct from :class:`fylite.scenario.model.nbi.BeamSource` because a wave deposits power
    and drives current without leaving a fast-ion pressure to add to
    ``p_total``, and because its **deposition location** is the uncertain
    part: ``drive(...)`` therefore returns ``sigma_j`` beside ``j_lh`` (see
    :func:`fylite.scenario.model.lh.deposit`), or ``None`` when nothing is configured.
    """

    name: str

    def drive(self, *, eq, ne, te, psin_prof, launchers=None, **kw): ...


#: ★``NoWave`` was here and went with :class:`fylite.scenario.model.nbi`'s
#: ``NoBeam``, for the same reason: :class:`LHAnalytic` opens ``if not
#: launchers: return None``, so the null member and the real one returned
#: the same ``None`` on every call the null member existed for.

class LHAnalytic:
    """Fisch-type analytic lower-hybrid current drive (this module).

    Needs ``launchers`` (a :class:`Launcher` or list — see
    :func:`east_launchers`) and an ``eta_cd``; both are the caller's, since
    the absorbed power is measured and the efficiency is calibrated."""

    name = "lh_analytic"

    def __init__(self, **lh_kw):
        self._kw = lh_kw

    def drive(self, *, eq, ne, te, psin_prof, launchers=None, **kw):
        if not launchers:
            return None
        return deposit(eq, ne, te, launchers, psin_prof=psin_prof,
                       **{**self._kw, **kw})
