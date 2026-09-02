"""QLKNN_7_11 — the composition layer over the QuaLiKiz neural surrogate.

The network is ONE multilayer perceptron, ``10 -> 133x5 -> 8``, that
answers all eight targets at once; :mod:`fylite.nn` evaluates it
(``nn_tables/qlknn_7_11.npz``) and this module turns its targets into
fluxes.  Upstream is Google DeepMind's `fusion_surrogates
<https://github.com/google-deepmind/fusion_surrogates>`_ — software
Apache-2.0, weights and metadata CC-BY 4.0 — trained by combining the
QLKNN11D and QLKNN7D-edge datasets and based on the QLKNN10D model of van
de Plassche et al., Phys. Plasmas 27 022310 (2020).  **Cite
doi:10.1063/1.5134126 when quoting a number this produces.**

★It replaced the twenty-net ``qlknn-hyper`` set on 2026-08-30.  What that
bought, and what it cost, are both worth stating:

* the composition collapsed from upstream Fortran's nine-step ritual
  (clip → evaluate 20 nets → clip leading → multiply → stability-clip →
  clip output → merge modes) to ONE multiplication, :data:`FLUX_MAP`
  below, because the net emits leading fluxes and ratios directly;
* the training set gained **the edge** (QLKNN7D-edge).  qlknn-hyper was
  core-only, and its answers past the pedestal top were extrapolation;
* the input basis changed: ``Zeff`` is gone, and dilution now enters
  through ``Ani`` and ``normni`` (:data:`INPUT_NAMES`).  A caller that
  fed the old nine cannot feed these ten by renaming;
* the ``dfe`` diffusivity nets are gone with it, so this module reports a
  particle FLUX and no D/V split.  That is not a loss of capability: the
  effective-D/V decomposition is caller-side arithmetic over the flux and
  the density gradient (TORAX does exactly that — ``DV_effective`` versus
  ``Dscaled`` in ``quasilinear_transport_model.py``), and doing it here
  would freeze one of the two conventions for every caller.

★The composition stays HERE rather than in the kernel because it is
caller-side arithmetic over a surrogate's outputs, the same posture the
twenty-net module took.  The kernel holds the MLP and nothing else.
"""
from __future__ import annotations

import numpy as np

from ... import nn

__all__ = ["MODEL", "INPUT_NAMES", "TARGET_NAMES", "FLUX_MAP",
           "QlknnChannelUnavailable", "FluxSet",
           "available", "targets", "flux_from_targets", "fluxes"]

#: the surrogate as it is named in `nn_tables/`
MODEL = "qlknn_7_11"

#: input order, upstream's own ``config.input_names``.  ``LogNuStar`` is a
#: LOGARITHM on arrival (the caller hands over log10 of the normalised
#: collisionality), and ``normni`` is n_i/n_e — the dilution that the
#: retired nine-input basis carried as ``Zeff``.
INPUT_NAMES = ("Ati", "Ate", "Ane", "Ani", "q", "smag", "x", "Ti_Te",
               "LogNuStar", "normni")

#: output order, upstream's own ``config.target_names``.  These are NOT
#: fluxes: five of them are RATIOS to a leading flux, which is what
#: :data:`FLUX_MAP` exists to undo.
TARGET_NAMES = ("itgleading", "itgqediv", "temleading", "temqidiv",
                "tempfediv", "etgleading", "itgpfediv", "gamma_max")

#: ``flux -> (target, denominator or None)``, transcribed from upstream's
#: own ``config.flux_map``.
#:
#: ★★**Every leading flux is clipped at zero, in BOTH branches**
#: (``fusion_surrogates/qlknn/qlknn_model.py``, ``get_flux_from_targets``):
#: a ratio flux is ``target * max(denominator, 0)`` and a leading flux is
#: ``max(target, 0)`` outright.  A first version of this module clipped
#: only the denominator — the comment "we clip the leading flux to 0" sits
#: above the ratio branch and the `else` that does the same to the leading
#: flux itself is four lines further down.  It made no difference on the
#: 25 upstream test vectors, all of which have positive leading fluxes,
#: and showed up the moment a real discharge was replayed: below the ITG
#: threshold near the axis the raw target is NEGATIVE, and an unclipped
#: leading flux is a negative heat flux, i.e. transport running up the
#: gradient.
FLUX_MAP = {
    "efiITG": ("itgleading", None),
    "efeITG": ("itgqediv", "itgleading"),
    "pfeITG": ("itgpfediv", "itgleading"),
    "efeTEM": ("temleading", None),
    "efiTEM": ("temqidiv", "temleading"),
    "pfeTEM": ("tempfediv", "temleading"),
    "efeETG": ("etgleading", None),
    "gamma_max": ("gamma_max", None),
}


class QlknnChannelUnavailable(NotImplementedError):
    """Asked for a transport channel QLKNN does not produce.

    ★Refused rather than returned as zero: a channel that transports
    nothing still converges, still reports that it did, and reads in the
    output exactly like a channel that was solved.
    """


#: what a caller may reasonably ask for and QLKNN cannot answer, with the
#: reason it cannot — the message is the point of the refusal
_UNAVAILABLE = {
    "exchange": (
        "QLKNN has no turbulent-exchange target: the eight are the leading "
        "fluxes, their ratios and a growth rate, and there is nothing to "
        "sum for an exchange term"),
    "growthrate": (
        "QLKNN carries no ky spectrum: it is trained on QuaLiKiz's "
        "integrated fluxes, and its one growth-rate target is the maximum "
        "over ion-scale ky, not a spectrum.  Ask for 'gamma_max'"),
    "frequency": (
        "QLKNN carries no ky spectrum, so it has no mode frequency; the "
        "network is trained on fluxes, not on eigenvalues"),
    "momentum": (
        "QLKNN has no momentum-stress target.  The Victor rule scales "
        "fluxes WITH a rotation input, which is not the same thing as "
        "predicting a momentum flux, and it is not ported here either"),
    "diffusivity": (
        "QLKNN_7_11 predicts a particle FLUX, not a D/V decomposition: the "
        "two `dfe` nets of the retired qlknn-hyper set have no counterpart "
        "here.  Effective D and V follow from 'particle' and the density "
        "gradient, which is the caller's convention to choose"),
}


class FluxSet(dict):
    """What :func:`fluxes` returns: the channels QLKNN produces, and a
    LOUD refusal for the ones it does not.

    ``fs["exchange"]`` raises :class:`QlknnChannelUnavailable` with the
    reason rather than ``KeyError`` — a caller that reaches for a channel
    by the name its TGLF sibling uses should be told why QLKNN has no such
    thing, not left to infer it from an absence.  ``.get()`` still returns
    ``None``, which is the right answer for a caller that is asking.
    """

    def __missing__(self, key):
        why = _UNAVAILABLE.get(key)
        if why is None:
            raise KeyError(key)
        raise QlknnChannelUnavailable(f"{key}: {why}")


def available() -> bool:
    """Whether the surrogate is reachable through :mod:`fylite.nn`."""
    return MODEL in set(nn.available())


def _as_matrix(inputs) -> np.ndarray:
    """``(n_rho, 10)`` from an array or a mapping in :data:`INPUT_NAMES`."""
    if isinstance(inputs, dict):
        missing = [n for n in INPUT_NAMES if n not in inputs]
        if missing:
            raise KeyError(f"QLKNN inputs missing: {', '.join(missing)}")
        cols = [np.atleast_1d(np.asarray(inputs[n], float))
                for n in INPUT_NAMES]
        n = {c.size for c in cols}
        if len(n) != 1:
            raise ValueError(f"QLKNN inputs have unequal lengths: {sorted(n)}")
        return np.stack(cols, axis=1)
    x = np.atleast_2d(np.asarray(inputs, float))
    if x.shape[1] != len(INPUT_NAMES):
        raise ValueError(f"QLKNN wants {len(INPUT_NAMES)} inputs in "
                         f"{INPUT_NAMES} order, got {x.shape[1]}")
    return x


def _clip_to_box(x: np.ndarray, margin: float) -> np.ndarray:
    """TORAX's ``clip_inputs`` (``qlknn_transport_model.py``), on the
    surrogate's own training box.

    ★Off by default here, as it is upstream and in TORAX: clipping turns
    an extrapolation into a silently plausible number, and
    :meth:`fylite.nn.Surrogate.outside_training_box` is the reporting path
    this repository prefers.  The knob exists because a transport loop
    that must not diverge sometimes needs it.
    """
    lo, hi = nn.load(MODEL).xbounds.T
    lo = lo + np.where(np.isfinite(lo), np.abs(lo) * (1.0 - margin), 0.0)
    hi = hi - np.where(np.isfinite(hi), np.abs(hi) * (1.0 - margin), 0.0)
    return np.clip(x, lo, hi)


def targets(inputs, *, clip_inputs: bool = False,
            clip_margin: float = 0.95) -> np.ndarray:
    """``(n_rho, 8)`` raw targets in :data:`TARGET_NAMES` order."""
    x = _as_matrix(inputs)
    if clip_inputs:
        x = _clip_to_box(x, clip_margin)
    model = nn.load(MODEL)
    out = np.empty((x.shape[0], len(TARGET_NAMES)))
    for i, row in enumerate(x):
        out[i], _ = model(row)
    return out


def flux_from_targets(t: np.ndarray, name: str) -> np.ndarray:
    """One flux out of the target matrix, by :data:`FLUX_MAP`.

    ★A leading flux is clipped at zero and a ratio flux is multiplied by a
    clipped leading flux — see :data:`FLUX_MAP` for why both halves of that
    matter.
    """
    target, denominator = FLUX_MAP[name]
    col = np.asarray(t, float)[:, TARGET_NAMES.index(target)]
    if denominator is None:
        return np.clip(col, 0.0, None)
    lead = np.asarray(t, float)[:, TARGET_NAMES.index(denominator)]
    return col * np.clip(lead, 0.0, None)


def fluxes(inputs, *, include_itg: bool = True, include_tem: bool = True,
           include_etg: bool = True, etg_correction: float = 1.0,
           **kw) -> FluxSet:
    """The turbulent fluxes QLKNN_7_11 predicts, as a :class:`FluxSet`.

    ``inputs`` is ``(n_rho, 10)`` in :data:`INPUT_NAMES` order, or a
    mapping of those names to equal-length arrays.

    Returns, in QuaLiKiz gyro-Bohm units (NOT TGLF's):

    ``energy``
        ``(2, n_rho)`` — electron then ion, each summed over the mode
        families that are switched on.
    ``particle``
        ``(1, n_rho)`` — the ELECTRON particle flux, and only it.  ★The
        row count is 1 rather than 2 on purpose: QLKNN predicts no ion
        particle flux, and padding the array to the species count with a
        zero row is the failure this module refuses to make.  The ion flux
        follows from quasineutrality, which is the caller's composition to
        choose.
    ``gamma_max``
        ``(n_rho,)`` — the maximum ion-scale growth rate.  A growth rate,
        not a flux, and not a spectrum.
    ``efeETG_GB``
        ``(n_rho,)`` — the ETG electron energy flux on its own, BEFORE
        ``etg_correction``, which is the piece a caller most often wants
        to inspect or switch off.

    ``include_itg`` / ``include_tem`` / ``include_etg`` zero a mode family,
    as TORAX's ``include_ITG``/``include_TEM``/``include_ETG`` do.

    ``etg_correction`` scales the ETG electron heat flux.  ★It defaults to
    **1.0 — the network's own answer** — where TORAX defaults to 1/3.
    That factor is a physics adjustment inherited from QLKNN10D practice,
    and applying it silently to a differently-trained network would be a
    number this repository did not measure.  Pass ``1/3`` to reproduce
    TORAX.

    Anything else a TGLF caller might reach for — ``exchange``,
    ``growthrate``, ``frequency``, ``momentum``, ``diffusivity`` — raises
    :class:`QlknnChannelUnavailable` naming the reason.
    """
    t = targets(inputs, **kw)
    itg = float(bool(include_itg))
    tem = float(bool(include_tem))
    etg = float(bool(include_etg))

    efe_etg = flux_from_targets(t, "efeETG")
    efe = (itg * flux_from_targets(t, "efeITG")
           + tem * flux_from_targets(t, "efeTEM")
           + etg * etg_correction * efe_etg)
    efi = (itg * flux_from_targets(t, "efiITG")
           + tem * flux_from_targets(t, "efiTEM"))
    pfe = (itg * flux_from_targets(t, "pfeITG")
           + tem * flux_from_targets(t, "pfeTEM"))
    return FluxSet({
        "energy": np.vstack([efe, efi]),
        "particle": np.vstack([pfe]),
        "gamma_max": flux_from_targets(t, "gamma_max"),
        "efeETG_GB": efe_etg,
    })
