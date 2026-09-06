"""RABBIT-class **fast** neutral-beam model (K-20) — beam deposition, fast-ion
pressure and beam-driven current, in pure Python.

Why a fast model and not a Monte-Carlo one: the self-consistent reconstruction
outer loop (``oracles/loop.py`` (the kernel repository)) re-evaluates the beam every round, so the
beam module has to cost milliseconds, not minutes.  That is the RABBIT tier
(Weiland et al., Nucl. Fusion 58 (2018) 082032): a **1-D beam-path attenuation**
plus an **orbit-averaged Stix slowing-down** plus an **electron-shielding
factor** — not NUBEAM/NFREYA guiding-centre Monte Carlo (the calibration oracle,
too slow in-loop) and not a Gaussian deposition placeholder (which distorts
under a density scan, exactly the scan the loop performs).

RABBIT itself is not obtainable (MPCDF-licensed source).  The physics here is
transcribed from **METIS** (CEA, CeCILL-C — the one redistributable code of this
class in the surveyed corpus), specifically ``zerod/z0nbipath.m`` (chord
attenuation), ``z0nbistop.m`` (Janev stopping cross-section), ``z0signbi.m``
(Riviere/Janev e-impact + i-impact + CX channels), ``zicd0.m`` (Stix critical
energy / slowing-down time / beam-driven current), ``zfract0.m`` (Wesson
ion/electron power split) and ``zsupra0.m`` (effective slowing time → fast-ion
stored energy).  Deliberate deviations from METIS, all documented at their use
site:

* **Quadrature.** METIS builds the chord from circle–line intersections against
  circular flux surfaces (``z0nbipath``); here the chord is marched on a fine
  path grid and ψ_N is looked up by bilinear interpolation of the g-file's own
  ``PSIRZ``.  Same physics, exact for arbitrary shaping, and it makes the
  off-midplane beam height a natural parameter rather than a profile remap.
* **Energy components.** METIS injects a single energy; EAST's positive-ion
  sources record full/half/third fractions (``NBI*E1/E2/E3``), which change the
  deposition depth materially, so the beam is a *sum over components*.
* **Larmor radius.** the exact ``ρ = √(2 A m_p E e)/(Z e B)`` rather than
  METIS's deuterium-calibrated constant.
* **Trapped fraction.** the kernel's ``trapped_fraction_eps`` (oracle-only since T-4 第十二刀) (Lin-Liu &
  Miller) rather than METIS's ``0.95√x`` fallback.

Outputs are **absolute** (W/m³, A/m², Pa) — the beam power is measured, unlike
the bootstrap magnitude the loop has to renormalize (K-9).  One call yields both
channels the reconstruction needs: ``j_nbi`` closes the current-channel prior
(the third way out of the FF′ internal-dipole degeneracy, D-2) and ``p_fast``
closes the pressure-channel loop (``p_total = p_thermal + p_fast``, with p_fast
carrying no direct instrument).

Known limitations, in order of importance:

* **Scalar Grad-Shafranov.**  The fast pressure is SPLIT into p_∥ / p_⊥ by the
  birth pitch (T-M12, the pitch-preserving drag closure — ``anisotropy`` in
  :func:`deposit`'s return carries both branches), but what enters the G-S
  source is still their trace third ``(p_∥ + 2p_⊥)/3`` — the anisotropic G-S
  equation itself is not in this tier.
* **First-orbit losses** follow METIS: banana/potato width against the boundary,
  applied for counter-injection only.  No ripple, no re-entrant orbits.
* **No CX / charge-exchange re-neutralization losses** beyond the stopping
  cross-section's CX channel, and no beam-beam or fast-ion-target stopping
  (METIS ``z0nbistopfast``, an option there, not ported).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
import numpy as np

from ... import kernel



class BeamError(ValueError):
    """A beam configuration that cannot be evaluated (bad geometry/energetics)."""


# --------------------------------------------------------------------------- #
# Beam configuration
# --------------------------------------------------------------------------- #
@dataclass
class Beam:
    """One neutral-beam ion source.

    ``energy`` is the **full** acceleration energy (eV) and ``power`` the
    injected neutral power (W) *after* the neutralizer — the quantity EAST
    records as ``\\PNBI{1L,1R,2L,2R}SOURCE`` (kW) in ``Analysis::NBI_EAST``.
    ``power_fractions`` splits that power between the full / half / third energy
    components (EAST's ``NBI*E1/E2/E3``, in that order, normalized here); the
    corresponding per-particle energies are ``E``, ``E/2``, ``E/3``.

    Geometry is the tangential-injection pair: ``tangency_radius`` (m, the
    perpendicular distance from the machine axis to the beam line) and
    ``z_height`` (m, the beam's height above the midplane).  ``direction`` is
    ``+1`` for co-current and ``-1`` for counter-current injection.  ``width_r``
    / ``width_z`` are the beam's half-widths (m); the chord is sampled over them
    so a finite beam is not treated as a pencil.

    ``mass`` / ``charge`` are the beam-ion mass and charge numbers (deuterium by
    default).
    """

    energy: float
    power: float
    tangency_radius: float
    z_height: float = 0.0
    direction: int = 1
    power_fractions: tuple[float, float, float] = (1.0, 0.0, 0.0)
    mass: float = 2.0
    charge: float = 1.0
    width_r: float = 0.10
    width_z: float = 0.10
    name: str = "nbi"

    def components(self) -> list[tuple[float, float]]:
        """``[(energy_eV, power_W), ...]`` for the full/half/third components.

        Zero-power components are dropped; the fractions are renormalized so the
        components always carry exactly ``power``.
        """
        fr = np.asarray(self.power_fractions, float)
        if fr.size != 3:
            raise BeamError("power_fractions must be (full, half, third)")
        fr = np.clip(fr, 0.0, None)
        tot = float(fr.sum())
        if tot <= 0.0:
            raise BeamError(f"beam {self.name!r}: power_fractions sum to zero")
        fr = fr / tot
        e0 = float(self.energy)
        if e0 <= 0.0:
            raise BeamError(f"beam {self.name!r}: energy must be positive")
        return [(e0 / k, float(self.power) * float(f))
                for k, f in zip((1.0, 2.0, 3.0), fr) if f > 0.0]


#: EAST's four neutral-beam ion sources (horizontal ports A & F; 50–80 keV,
#: 0–4 MW per beam line; deuterium).  Source names and the MDSplus nodes that
#: carry their power and energy fractions are recorded in the EAST signal
#: catalogue (``fydata`` ``east_signal_catalog.yaml`` → *Heating and CD Systems*
#: → *Neutral Beam Injection (NBI) System*).  The **tangency radii and beam
#: heights are `[TBD]`** — they are not in the catalogue and are not fabricated
#: here; :func:`east_beams` requires them from the caller.
EAST_NBI_SOURCES: tuple[dict, ...] = (
    {"name": "NBI1L", "power_node": r"\PNBI1LSOURCE",
     "fraction_nodes": (r"\NBI1LE1", r"\NBI1LE2", r"\NBI1LE3")},
    {"name": "NBI1R", "power_node": r"\PNBI1RSOURCE",
     "fraction_nodes": (r"\NBI1RE1", r"\NBI1RE2", r"\NBI1RE3")},
    {"name": "NBI2L", "power_node": r"\PNBI2LSOURCE",
     "fraction_nodes": (r"\NBI2LE1", r"\NBI2LE2", r"\NBI2LE3")},
    {"name": "NBI2R", "power_node": r"\PNBI2RSOURCE",
     "fraction_nodes": (r"\NBI2RE1", r"\NBI2RE2", r"\NBI2RE3")},
)


def east_beams(power_w, energy_ev, tangency_radius, *, z_height=0.0,
               power_fractions=None, direction=1, mass: float = 2.0,
               names=None) -> list[Beam]:
    """Build EAST's beam list from per-source power / energy / geometry.

    Scalars broadcast over the four sources; sequences are taken per source in
    :data:`EAST_NBI_SOURCES` order (NBI1L, NBI1R, NBI2L, NBI2R).  Sources with
    ``power_w <= 0`` are dropped.  ``tangency_radius`` has no catalogue value
    and must be supplied — see :data:`EAST_NBI_SOURCES`.
    """
    src = EAST_NBI_SOURCES if names is None else [
        s for s in EAST_NBI_SOURCES if s["name"] in set(names)]
    n = len(src)

    def _b(v, default=None):
        if v is None:
            v = default
        arr = np.atleast_1d(np.asarray(v, float))
        if arr.size == 1:
            return np.full(n, float(arr[0]))
        if arr.size != n:
            raise BeamError(f"expected 1 or {n} values, got {arr.size}")
        return arr.astype(float)

    pw, en = _b(power_w), _b(energy_ev)
    rt, zh = _b(tangency_radius), _b(z_height, 0.0)
    dr = _b(direction, 1)
    if power_fractions is None:
        pf = np.tile((1.0, 0.0, 0.0), (n, 1))
    else:
        pf = np.atleast_2d(np.asarray(power_fractions, float))
        if pf.shape == (3,) or pf.shape == (1, 3):
            pf = np.tile(pf.reshape(3), (n, 1))
        if pf.shape != (n, 3):
            raise BeamError(f"power_fractions must be (3,) or ({n}, 3)")
    return [Beam(energy=float(en[i]), power=float(pw[i]),
                 tangency_radius=float(rt[i]), z_height=float(zh[i]),
                 direction=int(np.sign(dr[i]) or 1),
                 power_fractions=tuple(pf[i]), mass=mass, name=src[i]["name"])
            for i in range(n) if pw[i] > 0.0]


# --------------------------------------------------------------------------- #
# Atomic physics — beam stopping
# --------------------------------------------------------------------------- #
#: ★★The Janev/Boley/Post (1989) beam-stopping coefficients used to be
#: transcribed HERE as well — `_S1` (12 hydrogenic) and `_SZ` (4 impurities
#: x 12).  Sixty-four numbers, byte-for-byte equal to `heating.rs`'s `S1`
#: and `SZ`, and **called by nothing**: the fit moved into the kernel and
#: its coefficients stayed behind.
#:
#: A dead table is not harmless.  It is indistinguishable from a live one at
#: a glance, so the next person to correct the fit corrects one of the two —
#: and there is no test that can fail, because nothing evaluates this copy.
#: The stopping cross-section is `kernel.stopping_cross_section`; the
#: coefficients live with it, once.


def _shaped(out, *inputs):
    """Give the caller back the SHAPE it asked with.

    The kernel is vectorised and always answers with a 1-D array; a scalar
    in must give a scalar out, or every ``float(...)`` at a call site becomes
    a deprecation warning and then an error.
    """
    shape = np.shape(np.broadcast_arrays(*inputs)[0]) if len(inputs) > 1 \
        else np.shape(inputs[0])
    return out.reshape(shape) if shape else float(out[0])


# --------------------------------------------------------------------------- #
# Slowing-down physics (Stix)
# --------------------------------------------------------------------------- #
#: ★``coulomb_log`` was here — ``_shaped(kernel.beam_slowing(...)
#: ["ln_lambda"], ne, te)`` — and it had NO caller, in this package or in
#: the tests.  The kernel entry is ``kernel.beam_slowing``, which every
#: live consumer already calls for the rest of the dict it returns; the
#: wrapper existed to pull one field out of it for a caller that never
#: arrived.  The identical five-line forward was removed from
#: ``mapping.py`` for the same reason one batch earlier.
#:
#: It survived that sweep because nothing distinguishes "public API" from
#: "leftover" in this module: it has no ``__all__``, so a name with no
#: caller looks exactly like a name a user might import.  What it did have
#: was a mention in ``test_no_bare_kernel_aliases``'s keeper list, where it
#: was an EXAMPLE of a wrapper that earns its keep — which is how a dead
#: name came to be pinned by a passing test.

def field_ion_sum(zeff, *, main_mass=2.0, main_charge=1.0,
                  imp_charge=6.0, imp_mass=12.0) -> np.ndarray:
    """``Σ_j n_j Z_j² / (n_e A_j)`` for a main ion + one impurity at given Z_eff.

    Quasineutrality and the Z_eff definition fix the two densities:
    ``n_i/n_e = (Z_imp − Z_eff)/(Z_imp − Z_i)`` and
    ``n_z/n_e = (Z_eff − Z_i)/(Z_imp(Z_imp − Z_i))`` (per unit main charge).
    Defaults are a deuterium plasma with carbon as the impurity, which for a
    pure D plasma gives the textbook ``E_c ≈ 18.6 T_e``.  The kernel's — it
    is a closure, not bookkeeping: ``E_c ∝ zsum^(2/3)``, so assembling this
    another way chooses a different critical energy without saying so.
    """
    return _shaped(kernel.field_ion_sum(zeff, main_mass=main_mass,
                                       main_charge=main_charge,
                                       imp_charge=imp_charge,
                                       imp_mass=imp_mass), zeff)


def slowing_down(te, ne, *, mass=2.0, zeff=1.0, zsum=None) -> dict:
    """Stix slowing-down parameters of a beam ion in a thermal plasma.

    ``te`` (eV), ``ne`` (m⁻³), ``mass`` the beam-ion mass number, ``zeff``
    the effective charge.  ``zsum`` is ``Σ_j n_j Z_j²/(n_e A_j)`` — the
    field-ion sum that sets the critical energy; when omitted it is built by
    :func:`field_ion_sum` from ``zeff`` for a main ion of mass ``mass`` plus
    carbon.

    Returns ``{e_crit, e_gamma, tau_s, ln_lambda}`` — the kernel's
    (METIS ``zicd0.m``; ``e_crit`` floored at 30 eV as there).
    """
    shape = np.shape(np.broadcast_arrays(te, ne)[0])
    if zsum is None:
        zsum = field_ion_sum(np.broadcast_to(np.asarray(zeff, float), shape)
                             if shape else zeff, main_mass=float(mass))
    out = kernel.beam_slowing(te, ne, mass=mass, zeff=zeff, zsum=zsum,
                              e_beam=1.0)
    return {k: (out[k].reshape(shape) if shape else float(out[k][0]))
            for k in ("e_crit", "e_gamma", "tau_s", "ln_lambda")}


def ion_power_fraction(e_crit, e_beam) -> np.ndarray:
    """Fraction of the beam power that ends up on the **ions** (Wesson,
    *Tokamaks* 2nd ed. p. 227; METIS ``zfract0.m``) — the kernel's."""
    ec, eb = np.broadcast_arrays(np.asarray(e_crit, float),
                                 np.asarray(e_beam, float))
    out = kernel.beam_energy_partition(ec, np.ones_like(ec),
                                       e_beam=eb)["ion_fraction"]
    return _shaped(out, ec)


def effective_slowing_time(tau_s, e_beam, e_crit, *, mass=2.0) -> np.ndarray:
    """Energy-weighted slowing time ``τ_eff`` (s) — the one that sets the
    fast-ion stored energy, ``W_fast = P_dep·τ_eff/2`` (METIS ``zsupra0.m``,
    D. Moreau's all-energies form).  The kernel's."""
    del mass                     # τ_eff depends on the velocity ratio only
    ts, ec, eb = np.broadcast_arrays(np.asarray(tau_s, float),
                                     np.asarray(e_crit, float),
                                     np.asarray(e_beam, float))
    out = kernel.beam_energy_partition(ec, ts, e_beam=eb)["tau_eff"]
    return _shaped(out, ts)


#: ★``electron_shielding`` and ``shielding_factor`` were here — the ``"g"``
#: and ``"factor"`` fields of ``kernel.beam_shielding``, shaped for a caller.
#: Both left with their last callers: the first with ``coulomb_log`` (no
#: caller anywhere), the second when the deposition sank into ``code/beam``
#: (2026-09-05), which computes both inside the kernel and reports them as
#: ``shielding`` / ``shielding_g`` on the record.
# --------------------------------------------------------------------------- #
# Flux-surface table + chord geometry
# --------------------------------------------------------------------------- #
def deposit(eq, ne, te, beams, *, psin_prof=None, ti=None, zeff=1.0,
            n_shells: int = 24, stopping_model: str = "janev",
            n_samples: int = 601, n_width_r: int = 3, n_width_z: int = 3,
            current_multiplier: float = 1.0, orbit_losses: bool = True,
            zsum=None, stop_kw: dict | None = None) -> dict:
    """Beam deposition, fast-ion pressure and beam-driven current — BY THE
    KERNEL (``code/beam``).

    ``eq`` an ``fyo:equilibrium`` document (or a g-file at the door); ``ne``
    (m⁻³) and ``te`` (eV) profiles on ``psin_prof`` (default a uniform ψ_N grid
    of their length); ``beams`` one :class:`Beam` or a list.  ``zsum`` is the
    field-ion sum ``Σ n_j Z_j²/(n_e A_j)`` if the plasma composition is known
    (see :func:`slowing_down`).

    ★★2026-09-05 (FYL-DESIGN-16 K-3, the eleventh tool to sink).  The whole
    assembly — the shell table on the psi map, the profiles at the shell
    centres, the trapped fraction and the shielding, then per beam and per
    energy component the deposition · first-orbit-loss mask · slowing-down ·
    electron/ion split · fast-ion pressure and its pitch split · torque ·
    driven current — is ``case.rs::beam_case`` now, one recipe for this face
    and for the page; the kernel repository's ``test_beam_code.py`` holds
    the door to the old recipe bit for bit.  What stays here is the plan:
    the beams as the DD's ``nbi`` units, the profiles on their ψ_N grid.

    Returns a dict on the shell-centre grid ``psin``:
    ``p_dep`` / ``p_e`` / ``p_i``
        absorbed power density and its electron / ion split (W/m³).
    ``p_fast``
        isotropic fast-ion pressure ``⅔ · p_dep·τ_eff/2`` (Pa) — the
        ``p_total = p_thermal + p_fast`` term that no instrument measures.
    ``j_nbi``
        beam-driven current density (A/m²), shielding and trapping included;
        signed by the injection direction.
    ``i_nbi`` / ``p_absorbed`` / ``p_injected``
        the driven current (A) and powers (W) integrated over the plasma.
    ``shinethrough`` / ``orbit_loss_fraction``
        power fractions lost through the far wall and to first-orbit losses.
    ``fast_energy``
        fast-ion stored energy ``W_fast = ∫ (3/2) p_fast dV`` (J).
    ``e_crit`` / ``tau_s`` / ``tau_eff`` / ``pitch`` / ``shielding`` / ``ft``
        the per-shell intermediates, so a caller can audit the chain.
    ``p_fast_par`` / ``p_fast_perp``
        the fast pressure split by the birth pitch (T-M12, pitch-preserving
        drag closure): ``p_∥ = 2Wξ²``, ``p_⊥ = W(1−ξ²)``; ``p_∥/2 + p_⊥ = W``
        and ``(p_∥ + 2p_⊥)/3 = p_fast`` hold to round-off.
    ``torque_nbi`` / ``torque_total``
        the beam's prompt toroidal torque density ``τ_φ = p_dep·(2/v_b)·ξ·R``
        per shell (N·m/m³), summed over components, and its volume integral
        (N·m).
    ``anisotropy``
        the branch dict ``{"p_par", "p_perp"}``.
    ``per_beam``
        the same power/current summary per source, for attribution.
    """
    from ... import fyo
    from ...io import fydoc
    doc = fyo.as_equilibrium(eq)
    if isinstance(beams, Beam):
        beams = [beams]
    beams = list(beams)
    if not beams:
        raise BeamError("deposit: no beams")
    stop_kw = dict(stop_kw or {})
    ne = np.asarray(ne, float)
    te = np.asarray(te, float)
    if psin_prof is None:
        psin_prof = np.linspace(0.0, 1.0, ne.size)
    psin_prof = np.asarray(psin_prof, float)
    for b in beams:
        b.components()                       # the configuration's own refusals
    settings = {"n_shells": float(n_shells), "stopping_model": str(stopping_model),
                "n_samples": float(n_samples), "n_width_r": float(n_width_r),
                "n_width_z": float(n_width_z), "current_multiplier": float(current_multiplier),
                "orbit_losses": float(bool(orbit_losses)),
                "impurity_form": str(stop_kw.pop("impurity_form", "exp"))}
    settings.update({k: float(v) for k, v in stop_kw.items()})
    if zsum is not None:
        settings["zsum"] = float(zsum)
    cp = {"grid": {"fylite:psi_norm": psin_prof},
          "electrons": {"density": ne, "temperature": te}}
    if ti is not None:
        cp["t_i_average"] = np.asarray(ti, float)
    if np.isscalar(zeff):
        settings["zeff"] = float(zeff)
    else:
        cp["zeff"] = np.asarray(zeff, float)
    units = [{"name": b.name, "energy": {"data": float(b.energy)},
              "power_launched": {"data": float(b.power)},
              "beam_power_fraction": {"data": np.asarray(b.power_fractions, float)},
              "species": {"a": float(b.mass), "z_n": float(b.charge)},
              "beamlets_group": [{"tangency_radius": float(b.tangency_radius),
                                  "position": {"z": float(b.z_height)},
                                  "direction": float(b.direction),
                                  "width_horizontal": float(b.width_r),
                                  "width_vertical": float(b.width_z)}]}
             for b in beams]
    try:
        rec = fydoc.complete("code/beam", {"settings": settings,
                                           "inputs": {"equilibrium": doc, "core_profiles": {"profiles_1d": cp},
                                                      "nbi": {"unit": units}}})
    except fydoc.Refused as e:
        raise BeamError(f"nbi: {e}") from e
    F = rec["fields"]
    arr = lambda k: np.asarray(F[k]["data"], float)  # noqa: E731
    fact = lambda k: float(rec["facts"][k]["value"])  # noqa: E731
    src = F["core_sources"]["source"]["0"]["profiles_1d"]
    p_par, p_perp = arr("p_fast_par"), arr("p_fast_perp")
    per_beam = [{"name": b.name, "power": float(b.power), "absorbed": float(a), "shinethrough": float(sh),
                 "orbit_loss": float(ol), "i_nbi": float(cur)}
                for b, a, sh, ol, cur in zip(beams, arr("beam_absorbed"), arr("beam_shinethrough"),
                                             arr("beam_orbit_loss"), arr("beam_current"))]
    return {
        "psin": np.asarray(src["grid"]["fylite:psi_norm"]["data"], float),
        "psin_edges": arr("psin_edges"), "dvolume": arr("dvolume"),
        "p_dep": arr("p_dep"), "p_e": np.asarray(src["electrons"]["energy"]["data"], float),
        "p_i": np.asarray(src["total_ion_energy"]["data"], float),
        "p_fast": arr("p_fast"), "j_nbi": np.asarray(src["j_parallel"]["data"], float),
        "pitch": arr("pitch"), "i_nbi": fact("i_nbi"), "p_absorbed": fact("p_absorbed"),
        "p_injected": fact("p_injected"), "shinethrough": fact("shinethrough"),
        "orbit_loss_fraction": fact("orbit_loss_fraction"), "fast_energy": fact("fast_energy"),
        "e_crit": arr("e_crit"), "tau_s": arr("tau_s"), "tau_eff": arr("tau_eff"),
        "shielding": arr("shielding"), "ft": arr("ft"), "eps": arr("eps"),
        "stopping_model": stopping_model,
        "p_fast_par": p_par, "p_fast_perp": p_perp,
        "torque_nbi": arr("torque"), "torque_total": fact("torque_total"),
        "anisotropy": {"p_par": p_par, "p_perp": p_perp},
        "per_beam": per_beam,
        "notes": list(rec.get("notes", [])),
    }


# --------------------------------------------------------------------------- #
# Beam-source model (K-18/K-20 named it a "beam_source" backend; the
# registry is retired — FYL-SDD-01 DE-LOG-03, and the family's other member
# was a null object) — an adapter over this module's deposition model.
# --------------------------------------------------------------------------- #

from typing import Protocol as _Protocol
from typing import runtime_checkable as _runtime_checkable


@_runtime_checkable
class BeamSource(_Protocol):
    """A neutral-beam backend: the *external* forcing the bootstrap does not
    cover.

    ``deposit(...)`` returns the profile dict of :func:`fylite.scenario.model.nbi.deposit`
    — crucially both channels the reconstruction needs, ``j_nbi`` (A/m²) for
    the current constraint and ``p_fast`` (Pa) for
    ``p_total = p_thermal + p_fast`` — or ``None`` when no beam is configured,
    which leaves the loop's behaviour exactly as it was before beams existed.
    """

    name: str

    def deposit(self, *, eq, ne, te, psin_prof, beams=None, **kw): ...


#: ★``NoBeam`` was here — ``name = "none"``, ``deposit(...) -> None`` — and
#: it was the family's DEFAULT.  It was indistinguishable from
#: :class:`MetisBeam`: the real backend's first line is ``if not beams:
#: return None``, so ``beam_backend="none"`` and ``beam_backend="metis"``
#: return the same ``None`` object whenever no beam is configured, which is
#: every call the null object existed to serve.  A null member for a
#: condition the real member already handles is a second way to say
#: ``beams=None``, and the two could disagree.
#:
#: What it cost besides: passing ``beams=`` and forgetting
#: ``beam_backend="metis"`` silently computed no beam at all.  The family
#: now has one member and is the default, so a configured beam deposits.

class MetisBeam:
    """METIS-derived RABBIT-class fast beam model (this module, K-20).

    Beam-path attenuation + Stix slowing-down + electron shielding;
    milliseconds per call, so it can live inside the outer loop.  Needs
    ``beams`` — a :class:`Beam` or a list (see :func:`east_beams`)."""

    name = "metis"

    def __init__(self, **nbi_kw):
        self._kw = nbi_kw

    def deposit(self, *, eq, ne, te, psin_prof, beams=None, **kw):
        if not beams:
            return None
        return deposit(eq, ne, te, beams, psin_prof=psin_prof,
                       **{**self._kw, **kw})
