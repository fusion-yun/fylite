"""QLKNN as a transport closure — the surrogate tier of the 1.5-D loop.

:mod:`fylite.scenario.model.qlknn` evaluates the network and composes its
targets into fluxes.  This module is the other half: it turns a traced
equilibrium and a set of profiles into the ten inputs QLKNN wants, and the
fluxes back into the ``chi`` / ``D`` a ``core_march`` closure must return.
:func:`qlknn_coefficients` has the same shape as
:func:`fylite.scenario.model.closure.kernel_coefficients` — ``{"chi": hook,
"particles": hook}``, hooks of ``(rho, te, ti[, ne_g])`` — so a driver can
take either without knowing which.

★★**Why this is a separate module from ``closure``, and must stay one.**
The two closures do not share a normalisation.  TGLF's mapping is built on
``a`` and ``B_unit``; QuaLiKiz normalises its LOGARITHMIC GRADIENTS on
``R_maj``, its GYRO-BOHM FLUX on ``a``, and its gyro-Bohm diffusivity on
``B_0`` — the vacuum field — and on ``T_i``.  Four reference quantities
differ, not one of the differences raises, and every one of them is a
tens-of-percent error in a number that still looks like a diffusivity.

★**What IS shared, on purpose**: the last step.  The gyro-Bohm fluxes are
converted to SI and handed to the same :func:`fylite.kernel.chi_from_flux`
and :func:`fylite.kernel.d_from_flux` the TGLF path uses, with the same
``gm3`` and the same kernel gradient rule.  So whatever convention
``core_march`` consumes, both tiers meet it identically — the alternative,
writing the diffusivity out directly here, would have made the two tiers
agree only in a circular plasma.

The recipe is TORAX's, read off ``qualikiz_based_transport_model.py`` and
``quasilinear_transport_model.py`` (Apache-2.0) and cited below; the
definitions underneath are QuaLiKiz's.

## The units, derived rather than asserted

TORAX never forms a flux: it writes the diffusivity directly as

```text
chi = (R_maj/a) * q_GB / (R_maj/L_T) * chi_GB
```

Since ``R_maj/L_T = -R_maj (dT/dr)/T``, that is ``chi = q_GB chi_GB T /
(-a dT/dr)``, and with ``Q = -n chi dT/dr`` the flux unit falls out:

```text
Q_SI  = n_e * q_GB  * chi_GB * T / a      [W/m^2]
Gam_SI= n_e * pf_GB * chi_GB     / a      [1/(m^2 s)]
```

The particle line is TORAX's own (``pfe * n_e * chiGB /
gyrobohm_flux_reference_length``), which is what pins ``a`` rather than
``R_maj`` as the flux length; the heat line is the same algebra with a
temperature in it.
"""
from __future__ import annotations

import numpy as np

from ... import fyo, kernel, nn
from . import qlknn

__all__ = ["Q_E", "M_E", "M_AMU", "EPSILON_0", "MU_0", "MAX_NU_STAR",
           "EPSILON_NN", "log_lambda_ei", "nu_star", "chi_gb", "alpha_mhd",
           "corrected_shear", "qlknn_inputs", "qlknn_coefficients"]

#: CODATA, spelled here rather than imported so the constants a published
#: fit was written with sit beside it
Q_E = 1.602176634e-19
M_E = 9.1093837015e-31
M_AMU = 1.66053906660e-27
EPSILON_0 = 8.8541878128e-12
MU_0 = 1.25663706212e-6

#: TORAX caps nu* before taking its logarithm, "to mitigate unreliable
#: transport predictions at high collisionality"
#: (``qualikiz_based_transport_model.py``).  It is a NUMBER applied where
#: the network would otherwise extrapolate, so it is named, not inlined.
MAX_NU_STAR = 1.0e3

#: ★★The inverse aspect ratio the QLKNN models were TRAINED at
#: (``qlknn_transport_model.py``'s ``_EPSILON_NN``).  The normalised radius
#: ``x`` is not a pure geometry label to these networks: at a fixed
#: training ``epsilon`` it also carries the TRAPPED-ELECTRON FRACTION, so a
#: machine with a different aspect ratio must hand over a rescaled ``x``
#: (``x * eps_edge / EPSILON_NN``) or the network reads the wrong trapped
#: fraction at every radius.  TORAX applies this to EVERY QLKNN model, not
#: only the legacy one.
EPSILON_NN = 1.0 / 3.0


def log_lambda_ei(te_ev, ne):
    """Coulomb logarithm, electron-ion
    (``collisions.calculate_log_lambda_ei``).  ``te_ev`` [eV], ``ne`` [m^-3].
    """
    return (31.3 - 0.5 * np.log(np.asarray(ne, float))
            + np.log(np.asarray(te_ev, float)))


def nu_star(*, te_ev, ne, z_eff, q, rmaj, epsilon):
    """Electron collisionality normalised by the bounce frequency
    (``collisions.calc_nu_star``) — the ninth QLKNN input before its log.

    ``tau_e`` is Wesson 3rd ed. p729 for a Z=1 plasma scaled by ``Z_eff``;
    the bounce time is ``q R / (eps^1.5 sqrt(T_e/m_e))``.

    ★★This follows TORAX **including where TORAX is not the textbook**: the
    thermal speed is written without the factor of two under the root.  The
    weights were trained against whatever QuaLiKiz's own definition
    produced, so a "corrected" collisionality would be a different input
    than the one the network saw — the fidelity being reproduced here is to
    the model, not to a formulary.
    """
    te_ev = np.asarray(te_ev, float)
    ne = np.asarray(ne, float)
    te_j = te_ev * Q_E
    lam = log_lambda_ei(te_ev, ne)
    log_tau_e = (np.log(12 * np.pi**1.5 / (ne * lam))
                 - 4 * np.log(Q_E)
                 + 0.5 * np.log(M_E / 2.0)
                 + 2 * np.log(EPSILON_0)
                 + 1.5 * np.log(te_j))
    nu_e = np.asarray(z_eff, float) / np.exp(log_tau_e)
    eps = np.clip(np.asarray(epsilon, float), 1e-12, None)
    tau_bounce = (np.asarray(q, float) * np.asarray(rmaj, float)
                  / (eps**1.5 * np.sqrt(te_j / M_E)))
    return nu_e * tau_bounce


def chi_gb(*, ti_ev, b0, a_minor, mass_amu: float = 2.0):
    """QuaLiKiz's gyro-Bohm diffusivity [m²/s]
    (``quasilinear_transport_model.calculate_chiGB``).

    ★``T_i`` and ``B_0`` — not ``T_e``, not ``B_unit``.  ``a_minor`` is the
    length even though the gradients are normalised on ``R_maj``.
    """
    return (np.sqrt(mass_amu * M_AMU) / (float(b0) * Q_E) ** 2
            * (np.asarray(ti_ev, float) * Q_E) ** 1.5 / float(a_minor))


def alpha_mhd(*, q, b0, te_kev, ne, ti_kev, ni, n_impurity,
              lref_over_lte, lref_over_lne, lref_over_lti, lref_over_lni):
    """The MHD ballooning parameter `alpha = L_ref q^2 beta'`
    (``quasilinear_transport_model.calculate_alpha``).

    ★It is what the shear correction below subtracts, and it is NOT a
    small number in a hot core: at the ITER-hybrid mid-radius it reaches
    order one, which is the same size as the shear itself.
    """
    factor = 2.0 * (Q_E * 1e3) / (float(b0) ** 2) * MU_0 * np.asarray(q, float) ** 2
    return factor * (
        np.asarray(te_kev, float) * np.asarray(ne, float)
        * (np.asarray(lref_over_lte, float) + np.asarray(lref_over_lne, float))
        + np.asarray(ni, float) * np.asarray(ti_kev, float)
        * (np.asarray(lref_over_lti, float) + np.asarray(lref_over_lni, float))
        + np.asarray(n_impurity, float) * np.asarray(ti_kev, float)
        * (np.asarray(lref_over_lti, float) + np.asarray(lref_over_lni, float)))


def corrected_shear(smag, q, alpha, *, smag_alpha_correction: bool = True,
                    q_sawtooth_proxy: bool = True,
                    avoid_big_negative_s: bool = True):
    """TORAX's three corrections to the shear the network is asked about.

    Returns ``(smag, q)`` — the sawtooth proxy moves both.

    ★★**Without these the transport in a real discharge is not merely
    inaccurate, it is qualitatively wrong.**  Replaying TORAX's ITER-hybrid
    evolution through the uncorrected closure put `chi_i` on its floor
    (0.05 m^2/s) across the whole confinement region, because a shear that
    has not had `alpha/2` removed from it sits below the ITG threshold
    almost everywhere.  With the corrections the median `chi_i` over the
    same 511 points is 0.96 against TORAX's 1.19.  That is a benchmark
    finding, not a tuning: the corrections are part of how the QLKNN model
    is USED, and a port that evaluates the network faithfully and omits
    them answers a different question correctly.

    ★They default ON because that is what TORAX defaults to and what the
    published QLKNN workflow assumes.  Each is separable so a caller can
    ask what a particular one is worth.
    """
    smag = np.array(smag, float)
    q = np.array(q, float)
    alpha = np.asarray(alpha, float)
    if smag_alpha_correction:
        #: van Mulders NF 2021: the Shafranov shift stabilises, and it
        #: enters the surrogate as a shifted shear rather than as its own
        #: input — the network has no `alpha` column
        smag = smag - alpha / 2.0
    if q_sawtooth_proxy:
        #: ★a very basic proxy, upstream's own words: inside q = 1 the
        #: sawtooth is assumed to hold the profile, so the network is asked
        #: about a flat-ish q = 1 surface instead of the real one
        inside = q < 1.0
        smag = np.where(inside, 0.1, smag)
        q = np.where(inside, 1.0, q)
    if avoid_big_negative_s:
        #: strongly reversed shear is outside the training set, and the
        #: network extrapolates there rather than refusing
        smag = np.where(smag - alpha < -0.2, alpha - 0.2, smag)
    return smag, q


def qlknn_inputs(states, *, zeff, x, ni_over_ne, dlnnidr, dlntidr,
                 smag=None, q=None):
    """``(n_surface, 10)`` in :data:`qlknn.INPUT_NAMES` order, from the same
    ``mapping.surface_state`` dicts the TGLF path consumes.

    ``x`` — the normalised radius the network is to be evaluated at,
    ALREADY rescaled by :data:`EPSILON_NN` (see
    :func:`qlknn_coefficients`); ``ni_over_ne``, ``dlnnidr``, ``dlntidr`` —
    the MAIN ION's, per surface.

    ★A ``surface_state``'s log-gradients are ``-dln y/dr`` [1/m] in
    upstream's sign, which is already QuaLiKiz's; the whole conversion is
    the multiplication by ``R_maj``.
    """
    rows = []
    for i, st in enumerate(states):
        rmaj = float(st["rmaj"])
        ion = st["ions"][0]
        nus = nu_star(te_ev=st["te"], ne=st["ne"], z_eff=zeff,
                      q=abs(float(st["q"])), rmaj=rmaj,
                      epsilon=float(st["rmin"]) / rmaj if rmaj else 0.0)
        rows.append([
            rmaj * float(dlntidr[i]),          # Ati = -R dlnT_i/dr
            rmaj * float(st["dlntedr"]),       # Ate
            rmaj * float(st["dlnnedr"]),       # Ane
            rmaj * float(dlnnidr[i]),          # Ani
            abs(float(st["q"])) if q is None else float(q[i]),
            float(st["s"]) if smag is None else float(smag[i]),
            float(x[i]),
            float(ion["ti"]) / float(st["te"]),
            float(np.log10(min(float(nus), MAX_NU_STAR))),
            float(ni_over_ne[i]),
        ])
    return np.asarray(rows, float)


def qlknn_coefficients(eq, *, psin, psin_prof, ne, gm3_at,
                       zeff: float = 1.6, z_imp: int = 6,
                       ion_mix: str = "dilution",
                       include_itg: bool = True, include_tem: bool = True,
                       include_etg: bool = True, etg_correction: float = 1.0,
                       clip_inputs: bool = False, clip_margin: float = 0.95,
                       smag_alpha_correction: bool = True,
                       q_sawtooth_proxy: bool = True,
                       avoid_big_negative_s: bool = True,
                       chi_floor: float = 0.05, chi_cap: float = 50.0,
                       d_floor: float = 0.02, d_cap: float = 20.0,
                       mass_main_amu: float = 2.0):
    """``{"chi": hook, "particles": hook}`` — the QLKNN tier of the closure.

    Drop-in for :func:`closure.kernel_coefficients` at the call site: the
    hooks take ``(rho, te, ti)`` and ``(rho, te, ti, ne_g)`` and return the
    same pairs on the same grid, with the same stiffness clipping.

    ★★**What this tier is, and what it is NOT.**  It is a SPEED tier — one
    network evaluation per surface where the TGLF path solves a full
    quasilinear spectrum — at **QuaLiKiz's** fidelity, not TGLF's.  Two
    things the TGLF path has and this one deliberately does not:

    * **no neoclassical term.**  ``closure`` adds NEO's Hirshman-Sigmar
      branch into every channel; QLKNN is a turbulence surrogate, and
      adding a neoclassical flux computed in a different normalisation is
      exactly the category error this module is arranged to prevent.  A
      caller that needs it must add it, in QuaLiKiz's gyro-Bohm, on
      purpose.
    * **no fast-ion effect.**  The ten inputs have no place for a
      non-thermal pressure, so the ``p_fast`` route that reaches TGLF
      through ``beta_unit`` (see ``closure.surface_states``) has no
      counterpart here.  TORAX patches this with a separate stabilisation
      network; that is not ported, and the absence is stated rather than
      papered over.

    ``outside_box`` on the returned dict is a per-surface report of inputs
    outside the training box — collected, never silently clipped.
    ``clip_inputs`` is TORAX's opt-in clamp and defaults off, as upstream.
    """
    from . import closure as _closure       # local: circular at module level

    psin = np.asarray(psin, float)
    psin_prof = np.asarray(psin_prof, float)
    if not qlknn.available():
        raise nn.NNDataMissing(
            f"{qlknn.MODEL} is not reachable — export it with "
            "rust/tools/export_qlknn_7_11.py")

    #: ★ONE trace for the life of the hook, exactly as `kernel_coefficients`
    #: does: the dense ladder carries the requested surfaces, so rho at a
    #: surface is read rather than interpolated.
    lad = fyo.Ladder.with_surfaces(eq, psin)
    rho_k = lad.rho[lad.index_of(psin)]
    (rho_full, psin_full), _ = kernel.with_axis_node(zero=(lad.rho, lad.psin))
    a_minor = lad.a_minor
    b0 = abs(float(lad.b0))
    #: the inverse aspect ratio AT THE EDGE — TORAX takes `epsilon[-1]`,
    #: the last point of its grid, not a local one
    rmaj_edge = float(lad.miller[-1]["rmaj"]) * a_minor
    eps_edge = a_minor / rmaj_edge if rmaj_edge else EPSILON_NN
    model = nn.load(qlknn.MODEL)

    def coefficients(rho, te, ti, ne_g=None):
        rho = np.asarray(rho, float)
        psin_of_rho = kernel.interp(rho, rho_full, psin_full)
        te_p = kernel.interp(psin_prof, psin_of_rho, te)
        ti_p = kernel.interp(psin_prof, psin_of_rho, ti)
        ne_p = (np.asarray(ne, float) if ne_g is None else
                kernel.interp(psin_prof, psin_of_rho, np.asarray(ne_g, float)))
        states = _closure.surface_states(
            lad, psin=psin, psin_prof=psin_prof, ne=ne_p, te=te_p, ti=ti_p,
            zeff=zeff, z_imp=z_imp, ion_mix=ion_mix)

        #: ★★``x`` is rescaled by the edge inverse aspect ratio over the
        #: one the networks were trained at — TORAX's own step, and NOT a
        #: cosmetic one: at fixed training ``epsilon`` the normalised
        #: radius also carries the trapped-electron fraction, so a machine
        #: with a different aspect ratio evaluated at a raw ``r/a`` is
        #: being asked about the wrong trapped population at every radius.
        x = np.array([float(st["rmin"]) / a_minor
                      for st in states]) * eps_edge / EPSILON_NN
        ne_s = np.array([float(st["ne"]) for st in states])
        te_s = np.array([float(st["te"]) for st in states])
        ti_s = np.array([float(st["ions"][0]["ti"]) for st in states])
        ni_s = np.array([float(st["ions"][0]["ni"]) for st in states])
        dlnnidr = np.array([float(st["ions"][0]["dlnnidr"]) for st in states])
        dlntidr = np.array([float(st["ions"][0]["dlntidr"]) for st in states])

        #: ★★the three shear corrections TORAX applies before it asks the
        #: network anything.  Without them a real discharge comes back with
        #: `chi_i` on its floor across the whole confinement region — see
        #: `corrected_shear` for the measurement.
        rmaj_s = np.array([float(st["rmaj"]) for st in states])
        n_imp_s = np.array([sum(float(i["ni"]) for i in st["ions"][1:])
                            for st in states])
        alpha = alpha_mhd(
            q=np.array([abs(float(st["q"])) for st in states]), b0=b0,
            te_kev=te_s * 1e-3, ne=ne_s, ti_kev=ti_s * 1e-3, ni=ni_s,
            n_impurity=n_imp_s,
            lref_over_lte=rmaj_s * np.array([float(st["dlntedr"])
                                             for st in states]),
            lref_over_lne=rmaj_s * np.array([float(st["dlnnedr"])
                                             for st in states]),
            lref_over_lti=rmaj_s * dlntidr, lref_over_lni=rmaj_s * dlnnidr)
        smag_c, q_c = corrected_shear(
            [float(st["s"]) for st in states],
            [abs(float(st["q"])) for st in states], alpha,
            smag_alpha_correction=smag_alpha_correction,
            q_sawtooth_proxy=q_sawtooth_proxy,
            avoid_big_negative_s=avoid_big_negative_s)

        xin = qlknn_inputs(states, zeff=zeff, x=x, ni_over_ne=ni_s / ne_s,
                           dlnnidr=dlnnidr, dlntidr=dlntidr,
                           smag=smag_c, q=q_c)
        fs = qlknn.fluxes(xin, include_itg=include_itg,
                          include_tem=include_tem, include_etg=include_etg,
                          etg_correction=etg_correction,
                          clip_inputs=clip_inputs, clip_margin=clip_margin)

        #: the gyro-Bohm -> SI conversion derived in the module docstring
        cgb = chi_gb(ti_ev=ti_s, b0=b0, a_minor=a_minor,
                     mass_amu=mass_main_amu)
        q_e_si = ne_s * fs["energy"][0] * cgb * (te_s * Q_E) / a_minor
        q_i_si = ne_s * fs["energy"][1] * cgb * (ti_s * Q_E) / a_minor
        gam_si = ne_s * fs["particle"][0] * cgb / a_minor

        #: the density and the gradients ON the transport grid, by the
        #: kernel's own end rule — the same choice `kernel_coefficients`
        #: makes, and for the same reason: a closure differentiated by a
        #: different rule than the solver is a different closure at the two
        #: nodes where the rules differ.
        ne_rho = (np.asarray(ne_g, float) if ne_g is not None else
                  kernel.interp(psin_of_rho, psin_prof, np.asarray(ne, float)))
        grad_ne = kernel.gradient(ne_rho, rho)
        grad_te = kernel.gradient(np.asarray(te, float), rho)
        grad_ti = kernel.gradient(np.asarray(ti, float), rho)

        chi_e_k = np.empty(len(states))
        chi_i_k = np.empty(len(states))
        d_n_k = np.empty(len(states))
        for i in range(len(states)):
            r = float(rho_k[i])
            g3 = (gm3_at(r) if callable(gm3_at) else
                  float(kernel.interp(r, rho, np.broadcast_to(
                      np.asarray(gm3_at, float), rho.shape))))
            n_si = float(kernel.interp(r, rho, ne_rho))
            chi_e_k[i] = kernel.chi_from_flux(
                q_e_si[i], n_si, float(kernel.interp(r, rho, grad_te)), g3)
            chi_i_k[i] = kernel.chi_from_flux(
                q_i_si[i], n_si, float(kernel.interp(r, rho, grad_ti)), g3)
            d_n_k[i] = kernel.d_from_flux(
                gam_si[i], float(kernel.interp(r, rho, grad_ne)), g3)

        out = {
            "chi_e": kernel.interp(rho, rho_k,
                                   np.clip(chi_e_k, chi_floor, chi_cap)),
            "chi_i": kernel.interp(rho, rho_k,
                                   np.clip(chi_i_k, chi_floor, chi_cap)),
            "d_n": kernel.interp(rho, rho_k,
                                 np.clip(d_n_k, d_floor, d_cap)),
            "gamma_max": kernel.interp(rho, rho_k, fs["gamma_max"]),
            "inputs": xin,
            "chi_gb": cgb,
            "alpha_mhd": alpha,
            "outside_box": [model.outside_training_box(row) for row in xin],
        }
        return out

    cache = {}

    def _memo(rho, te, ti, ne_g=None):
        rho = np.asarray(rho, float)
        key = (rho.tobytes(), np.asarray(te, float).tobytes(),
               np.asarray(ti, float).tobytes(),
               None if ne_g is None else np.asarray(ne_g, float).tobytes())
        if cache.get("key") != key:
            cache["key"] = key
            cache["out"] = coefficients(rho, te, ti, ne_g)
        return cache["out"]

    def chi(rho, te, ti):
        out = _memo(rho, te, ti)
        return out["chi_e"], out["chi_i"]

    def particles(rho, te, ti, ne_g=None):
        out = _memo(rho, te, ti, ne_g)
        #: ★D only, and V left to the caller.  QLKNN gives ONE particle
        #: flux; splitting it into a diffusion and a pinch needs a
        #: convention, and TORAX ships two that disagree (`DV_effective`
        #: solves both from the flux and the gradient, `Dscaled` fixes
        #: `D = chi_e` and puts the remainder in `V`).  Choosing one here
        #: would hide it inside a closure; the density channel takes `D`.
        return out["d_n"]

    return {"chi": chi, "particles": particles, "detail": _memo}
