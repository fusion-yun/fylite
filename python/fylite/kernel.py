"""The Python face of the Rust kernel — typed wrappers, zero assembly.

★Why this module exists (FYL-DESIGN-08 §1).  The kernel exports 61 C ABI
entries.  The browser reaches 46 of them; Python reached 33, and the gap was
not capability but ACCESS: a 0-D evaluation, a flux-surface trace, a bounded
least-squares and a profile fit were all in the kernel, already used by
``app/assets/fylite.js``, while ``python/fylite`` computed the same physics a
second time in numpy / scipy.  A duplicate implementation nobody can call the
alternative to is a duplicate that never gets compared — which is exactly what
happened: ``transport.py`` and ``transport.rs`` are the same discretisation
twice over, and no gate has ever put them side by side.

What belongs here: marshalling (contiguity, sizes, output buffers), error
codes turned into exceptions, and the field names the kernel documents.
What does NOT belong here: any decision a physicist would recognise as a
choice — those live either in the kernel (physics, numerics) or in the
assembly layer above (which surfaces, which channels, which waveform).

Every entry raises :class:`KernelError` on a negative return code rather
than handing back a plausible-looking array: the failure modes this
repository keeps paying for are the quiet ones.

This module is also the LOADER.  The shared library is resolved once per
process and cached — the negative result too, since dlopen attempts are not
free and the answer cannot change within a process; ``$FY_KERNEL_LIB``
overrides the bundled path.  ★It used to say "same override pattern as
``FY_TGLF_EXEC`` / ``FY_MDSPLUS_ROOT``" — **neither of those is read
anywhere**; they were a pattern this line invoked and no code implemented.
The environment this package actually reads is declared in
``fylite/_environment.json`` and gated against the source both ways.  A
library that loads but speaks an ABI version
other than :data:`ABI_VERSION` (generated into ``_abi.py`` by
``rust/build.sh``) is refused loudly rather than run against mismatched
signatures.  Each C entry's ctypes signature is registered with
:func:`_sig` immediately above the wrapper that calls it, so a signature
and its marshalling sit together; ``load()`` applies the whole registry.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

import numpy as np

from . import _deck_names
from . import _fyo_interface
from ._paths import KERNEL_LIB

__all__ = [
    "KernelError", "KernelBackendError", "ABI_VERSION",
    "load", "available", "require", "Grid", "grid_of",
    "dt_reactivity", "bgb_chi", "neutrals_mc",
    "nn_ensemble", "nn_weight_count",
    "zerod_volume", "zerod_evaluate", "zerod_predict",
    "zerod_waveform", "zerod_phase_labels", "WAVEFORMS", "PHASE_NAMES",
    "zerod_profile", "zerod_fusion_power", "zerod_loop_voltage",
    "zerod_limits", "zerod_flux_budget", "zerod_stored_energy",
    "zerod_averages", "strike_points", "wall_clearance",
    "start_currents", "fill_filaments", "feedforward_voltages",
    "TRANSPORT_MODELS", "transport_step", "interpretive_channel",
    "trace_surface", "contour", "shape_metrics", "enclosed_volume",
    "direct_integrals", "gradient",
    "shell_sum", "li3", "q_profile", "profile_shape_fit", "sample", "ray_level",
    "redl_coefficients", "redl_bootstrap", "trapped_fraction_eps",
    "lh_accessibility", "lh_resonance", "lh_shape", "lh_efficiency",
    "lh_normalize", "LH_EFFICIENCY_MODELS", "first_orbit_loss",
    "field_ion_sum", "beam_footprint", "fill_gaps",
    "BEAM_STOPPING_MODELS", "IMPURITY_FORMS", "beam_stopping",
    "beam_slowing", "beam_energy_partition", "beam_shielding",
    "beam_current_integral", "beam_current",
    "beam_deposit_ray",
    "pchip", "svd", "svd_solve", "besselj", "bessel_zeros",
    "tomography_basis",
    "QUADRATURE_RULES", "chord_samples", "psin_along", "quadrature",
    "chord_mask", "line_integral", "chord_reduce", "pinhole_angles",
    "current_centroid",
    "ideal_stiffness", "dispersion_root", "vertical_plant", "vertical_loop",
    "inside_polygon", "f_from_coefficients", "probe_response",
    "step_circuits", "resistances", "evolve_circuits",
    "element_flux", "filament_flux", "channel_matrices",
    "table_ratio_check",
    "ellipke", "mutual_filaments", "mutual_outer", "element_filaments",
    "mutual_matrix", "grid_response", "element_response",
    "element_probe_response",
    "coupling_gradient", "vertical_stiffness",
    "plasma_filaments",
    "spitzer_eta", "spitzer_eta_perp", "eped1nn",
    "ICRH_MINORITY", "ICRH_GAS", "ICRH_REFUSALS", "IcrhRefused",
    "icrh_resonance", "icrh_minority", "icrh_profile", "icrh_fwcd",
    "EDGE_SPECIES", "NE_TAU_CORONAL_LIMIT", "edge_noncoronal",
    "edge_l_int", "LENGYEL_GEOMETRY_KEYS", "LENGYEL_DEFAULTS",
    "lengyel_closed", "LENGYEL_SOL_KEYS", "LENGYEL_SOL_DEFAULTS",
    "LENGYEL_STATE_KEYS", "lengyel_two_point", "lengyel_z_eff",
    "LENGYEL_OUTCOMES", "lengyel_inverse", "lengyel_forward",
    "reintegrate", "flux_residual", "flux_match_step", "flux_match_backoff",
    "flux_match", "FluxMatchError",
    "adas_id", "adas_species", "adas_cooling", "rad_ion", "rad_sync",
    "exchange_power", "volume_int",
    "target_flux",
    "SURFACE_KEYS", "surface_block", "collision_rates", "surface_derived",
    "tglf_local", "neo_local", "TGLF_SPECIES_ROWS", "field_sign",
    "neo_geo14", "NEO_SAUTER_SLOTS", "HIRSHMAN_SIGMAR_VINTAGE",
    "TGLF_DECK_SPECIES",
    "miller_boundary", "analytic_shape", "b_field", "analytic_current",
    "sample_grid",
    "tglf_units", "tglf_presets", "tglf_linear", "tglf_matrices",
    "tglf_kygrid", "tglf_flux", "tglf_dlnpdr", "TGLF_PRESET_ERRORS",
    "neo_sauter", "dke_solve", "neo_gyrobohm",
    "SAUTER_1999", "REDL_2021",
    "ridge_lstsq", "bounded_lstsq", "profile_fit", "profile_sample",
    "null_disc", "channel_field", "breakdown_design",
    "geo_surface", "GEO_SHAPE_KEYS", "GEO_SCALARS",
    "gs_fixed_box",
    "boundary_flux", "harmonic_interior", "gs_free_solve",
    #: T-D6′ — the same solve on a tabulated (delivered) p'/FF' shape
    "gs_free_solve_tab", "FREE_SOLVE_TAB_KEYS",
    "gs_inverse_solve",
    #: T-A5 — the same solve with the coil currents FITTED
    "gs_inverse_solve_coils", "INVERSE_COIL_KEYS",
    "INVERSE_KEYS", "INVERSE_FSA_KEYS",
    "FREE_SOLVE_KEYS",
    "ohmic_power", "quasi_neutral_ne", "b_unit_from_rho",
    "ion_dilution", "with_axis_node",
    "shape_observables", "two_temperature_step", "two_temperature_march",
    "deltastar_apply", "core_march", "label_drift", "momentum_weights", "solve_momentum",
    "scenario", "scenario_layout", "SCENARIO_ENTRIES",
    "d_from_flux", "gyrobohm_gamma", "alpha_heating",
    "alpha_fast_ions", "q_crossing",
    "sawtooth_crash",
    "solve_density",
    "tglf_flux_searched", "tomography_rows", "chi_from_flux", "gyrobohm_q", "shell_area",
    "neo_current_unit",
    "equilibrium_ladder", "METRIC_ROW", "MILLER_ROW",
    "resample_uniform", "to_uniform_extrap", "interp", "x_points", "lh_deposit", "flux_jacobian", "shell_table", "beam_deposit",
    "fast_ion_pressure",
    "selfcal_single", "selfcal_slices",
    "factor_dispersion", "neo_surface_inputs", "M_ELECTRON_OVER_MD",
    "NEO_SPECIES_ROWS",
    "redl_drive", "redl_surface_inputs", "REDL_INPUT_ROWS",
    "gfile_profile",
    "solve_psi",
    "bound_deriv", "gyrobohm", "bundle_derive", "BUNDLE_ROWS",
    "GYROBOHM_ROWS", "MXH_HARMONICS",
    "design_null",
]


class KernelError(RuntimeError):
    """The kernel cannot be provided (absent / ABI mismatch), or a kernel
    entry refused the call (negative return code)."""


#: Former name of :class:`KernelError`, kept for ``pytest.raises`` callers.
KernelBackendError = KernelError

#: The ABI version the built library speaks, GENERATED by rust/build.sh
#: from c_api.rs.  It used to be a hand-maintained constant and drifted from
#: the Rust side twice in one day — each time the loud loader refused the
#: library and every Rust-backed test failed at load.  Generating it removes
#: the possibility rather than the symptom.
try:
    from ._abi import ABI_VERSION
except ImportError:  # not built yet
    ABI_VERSION = None

#: The upstream deck NAME ORDERS, generated from the kernel beside the code
#: that makes those numbers (`rust/build.sh`, marker `@deck-names`).  A host
#: speaks fyo; only the port speaks NEO or TGLF, so these names have exactly
#: one source and it is that port.  Same reason `ABI_VERSION` is generated.
try:
    from ._deck_names import (NEO_DECK_GEOMETRY, NEO_DECK_SCALARS,
                              NEO_DECK_SPECIES, NEO_SAUTER_SLOTS,
                              TGLF_DECK_GEOMETRY,
                              TGLF_DECK_SPECIES,
                              PHASE_NAMES as _PHASE_NAMES,
                              WAVEFORM_NAMES as _WAVEFORM_NAMES,
                              TAU_LAW_NAMES as _TAU_LAW_NAMES,
                              LH_EFFICIENCY_MODEL_NAMES
                              as _LH_EFFICIENCY_MODEL_NAMES)
except ImportError:  # not built yet
    NEO_DECK_GEOMETRY = NEO_DECK_SCALARS = NEO_DECK_SPECIES = ()
    NEO_SAUTER_SLOTS = ()
    TGLF_DECK_GEOMETRY = TGLF_DECK_SPECIES = ()
    _PHASE_NAMES = _WAVEFORM_NAMES = _TAU_LAW_NAMES = ()
    _LH_EFFICIENCY_MODEL_NAMES = ()

_ENV_LIB = "FY_KERNEL_LIB"

# ctypes shorthands used by the `_sig` declarations below
_ARR = np.ctypeslib.ndpointer(np.float64, flags="C_CONTIGUOUS")
#: int32 array — the log10 mask a surrogate carries is integral, and
#: marshalling it as f64 would let a 0.5 through as a truthy flag
_IARR = np.ctypeslib.ndpointer(np.int32, flags="C_CONTIGUOUS")
_U64, _I32, _F64, _VOID = (ctypes.c_uint64, ctypes.c_int32, ctypes.c_double,
                           ctypes.c_void_p)
_SIX = [_ARR] * 6

#: entry name -> (argtypes, restype); filled by `_sig` at import time,
#: applied to the library by `load()`.
_SIGNATURES: dict[str, tuple[list, object]] = {}


def _sig(name: str, argtypes, restype) -> None:
    """Register the ctypes signature of one C entry (applied in `load()`)."""
    _SIGNATURES[name] = (list(argtypes), restype)


def _lib_path() -> Path:
    override = os.environ.get(_ENV_LIB)
    return Path(override).expanduser() if override else KERNEL_LIB


# Cache: None = not tried yet; (lib_or_None,) = tried (a 1-tuple so a failed
# probe is cached too).
_cache: tuple[ctypes.CDLL | None] | None = None


def load() -> ctypes.CDLL | None:
    """The Rust core, or ``None`` if the library is absent.  Cached.

    Raises :class:`KernelError` only for a *present but incompatible*
    library — absence is reported, incompatibility is refused.
    """
    global _cache
    if _cache is not None:
        return _cache[0]
    path = _lib_path()
    if not path.exists():
        _cache = (None,)
        return None
    lib = ctypes.CDLL(str(path))
    lib.fylite_rs_abi_version.restype = ctypes.c_uint32
    lib.fylite_rs_abi_version.argtypes = []
    got = int(lib.fylite_rs_abi_version())
    if ABI_VERSION is None:
        # _abi.py is generated by rust/build.sh and committed alongside
        # the library it describes, so a missing one means a tree that
        # has never been built.  Refuse rather than accept whatever the
        # library claims — an unchecked ABI is the thing this guard is
        # for.
        raise KernelError(
            f"{path} speaks ABI v{got} but python/fylite/_abi.py is "
            "missing — run rust/build.sh")
    if got != ABI_VERSION:
        # Do not cache: the operator may swap the library file to fix this.
        raise KernelError(
            f"{path} speaks ABI v{got}, this fylite expects v{ABI_VERSION} — "
            f"rebuild it (rust/build.sh) or unset ${_ENV_LIB}")
    lib.fylite_rs_ping.restype = ctypes.c_double
    lib.fylite_rs_ping.argtypes = [ctypes.c_double]
    for name, (argtypes, restype) in _SIGNATURES.items():
        fn = getattr(lib, name)
        fn.argtypes = argtypes
        fn.restype = restype
    _cache = (lib,)
    return lib


def available() -> bool:
    """True iff the Rust core loads and matches the expected ABI."""
    return load() is not None


def require() -> ctypes.CDLL:
    """The loaded library, or a loud error — the one host.

    ★Not a silent fallback.  Every consumer of this module used to have its
    own numpy path to fall back to; that is precisely the arrangement this
    module exists to end, so "kernel absent" is an error rather than an
    invitation to compute the physics somewhere else (FYL-DESIGN-08 D-4′).
    """
    lib = load()
    if lib is None:
        raise KernelError(
            f"the kernel is not available: {_lib_path()} is absent — build "
            "it with rust/build.sh.  It is the only host of physics and "
            "numerics (FYL-DESIGN-08 D-4′), so there is nothing to fall "
            "back to.")
    return lib


def _f(a) -> np.ndarray:
    return np.ascontiguousarray(np.asarray(a, dtype=float))


# --------------------------------------------------------------------------- #
# grid convention
# --------------------------------------------------------------------------- #
class Grid:
    """The kernel's rectangular grid: origin, spacing, counts.

    ★The array convention is ``psi[i, j]`` with ``i`` over R and ``j`` over
    Z — i.e. shape ``(nr, nz)``, R-major — the same layout
    :func:`~fylite.kernel.gs_free_solve` returns, so a solved field goes
    straight back in without a transpose.  (A transposed field does not
    raise; it traces a plausible surface of the wrong plasma.)

    ★★The FLUX convention is the app's: **full flux [Wb], axis a MAXIMUM**.
    The kernel's ray tracer walks outward while ``psi > level``, so an
    EFIT g-file's ``psirz`` (per-radian, axis a minimum) must be converted
    — ``psi = -2 pi * psirz`` — before it comes in.  Handing it over raw
    does NOT raise: every ray stops at the first step, the trace comes back
    with the full point count, and the surface integrals are zero.  That is
    what a wrong sign looks like here, and it is why
    :mod:`fylite.fyo` converts once, in one place.
    """

    __slots__ = ("r0", "z0", "dr", "dz", "nr", "nz")

    def __init__(self, r0, z0, dr, dz, nr, nz):
        self.r0, self.z0 = float(r0), float(z0)
        self.dr, self.dz = float(dr), float(dz)
        self.nr, self.nz = int(nr), int(nz)

    @property
    def args(self) -> tuple:
        return (self.r0, self.z0, self.dr, self.dz, self.nr, self.nz)

    def __repr__(self) -> str:                       # pragma: no cover - repr
        return (f"Grid(r0={self.r0}, z0={self.z0}, dr={self.dr}, "
                f"dz={self.dz}, nr={self.nr}, nz={self.nz})")


def grid_of(rg, zg) -> Grid:
    """Grid from the R / Z coordinate vectors, checking they are uniform.

    A non-uniform vector is refused: the kernel's grid is defined by an
    origin and a spacing, so passing a stretched mesh would silently
    evaluate everything at the wrong place.
    """
    rg, zg = _f(rg), _f(zg)
    for name, v in (("R", rg), ("Z", zg)):
        if v.size < 2:
            raise KernelError(f"{name} axis needs at least two points")
        d = np.diff(v)
        if not np.allclose(d, d[0], rtol=1e-9, atol=0.0):
            raise KernelError(f"{name} axis is not uniform — the kernel grid "
                              "is (origin, spacing, count)")
    return Grid(rg[0], zg[0], rg[1] - rg[0], zg[1] - zg[0], rg.size, zg.size)


# --------------------------------------------------------------------------- #
# 0-D discharge (zerod.rs)
# --------------------------------------------------------------------------- #
_sig("fylite_rs_dt_reactivity", [_F64], _F64)
def dt_reactivity(ti_kev):
    """Bosch-Hale <sigma v> for D-T [m³/s]; 0 outside 0.2-100 keV."""
    lib = require()
    t = np.atleast_1d(_f(ti_kev))
    out = np.array([lib.fylite_rs_dt_reactivity(float(x)) for x in t])
    return out if np.ndim(ti_kev) else float(out[0])


_sig("fylite_rs_nn_weight_count", [_U64] * 5, ctypes.c_uint64)
def nn_weight_count(n_in, n_hidden, n_hidden_layers, n_blocks, n_out) -> int:
    """How many f64 ONE member of this shape occupies (nn.rs).

    The loader checks an exported model against this rather than against a
    count it recomputes itself — a loader agreeing with its own arithmetic
    would not catch a truncated export.
    """
    return int(require().fylite_rs_nn_weight_count(
        int(n_in), int(n_hidden), int(n_hidden_layers), int(n_blocks),
        int(n_out)))


_sig("fylite_rs_nn_ensemble",
     [_U64] * 5 + [_I32, _U64, _ARR, _IARR, _ARR, _IARR, _U64]
     + [_ARR] * 4
     + [_ARR, _U64] + [_ARR] * 3, _I32)
def nn_ensemble(surrogate, x):
    """Evaluate a vendor-external surrogate — ``(mean, spread)``.

    ★No weights are compiled into the kernel: ``surrogate`` is a
    :class:`fylite.nn.Surrogate` the host loaded from
    ``$FYLITE_NN_DIR``, and its arrays are handed across the ABI for this
    one call.  ``x`` is in the model's own ``xnames`` order.  ``spread``
    is the ensemble members' sample standard deviation — what the ensemble
    can say about its own scatter, not a physics uncertainty.
    """
    lib = require()
    x = np.ascontiguousarray(_f(x))
    if x.size != surrogate.n_in:
        raise KernelError(f"nn_ensemble: {surrogate.name} takes "
                          f"{surrogate.n_in} inputs, got {x.size}")
    mean = np.empty(surrogate.n_out)
    spread = np.empty(surrogate.n_out)
    #: ★the activation code is a WIRE FORMAT shared with `nn.rs`, and it is
    #: read from the one table rather than spelled again here — this line
    #: used to carry its own copy, which is the copy that actually reached
    #: the ABI while `nn.ACT_CODES` only validated.
    from .nn import ACT_CODES

    act = ACT_CODES[surrogate.activation]
    rc = lib.fylite_rs_nn_ensemble(
        surrogate.n_in, surrogate.n_hidden, surrogate.n_hidden_layers,
        surrogate.n_blocks, surrogate.n_out, act, surrogate.n_members,
        surrogate.weights, surrogate.log10_mask,
        surrogate.x_shift, surrogate.x_abs, surrogate.x_shift.size,
        surrogate.xm, surrogate.xs, surrogate.ym,
        surrogate.ys, surrogate.powerlaw, surrogate.powerlaw.size,
        x, mean, spread)
    if rc == -3:
        bad = [surrogate.xnames[i] for i in range(surrogate.n_in)
               if surrogate.log10_mask[i] and x[i] <= 0]
        raise KernelError(
            f"nn_ensemble: {bad} are fed as log10 by this model and are not "
            f"positive — the network was never trained on that")
    if rc != 0:
        raise KernelError(f"fylite_rs_nn_ensemble returned {rc}")
    return mean, spread


_sig("fylite_rs_bgb_chi",
     [_ARR, _ARR, _ARR, _ARR, _U64] + [_F64] * 5 + [_ARR, _ARR], _I32)
def bgb_chi(rho, te_ev, ne, q, *, b0, alphas=None):
    """Mixed Bohm/gyro-Bohm closure (bgb.rs) — ``(chi_e, chi_i)`` [m²/s].

    ★``rho`` must be the flux label the transport solve uses: the frozen
    Bohm coefficients were measured against JINTRAC 101612's recorded
    per-face Bohm column in ITS flux label (±0.5 % flat); the same formula
    read against the midplane radius is 30-40 % off at the edge.  ``te_ev``
    in eV.  ``alphas`` = (e_bohm, e_gb, i_bohm, i_gb); None (or any
    non-finite entry) selects the module's frozen constants — the Bohm
    pair measured, the gyro-Bohm pair literature values (that channel has
    no oracle in 101612: its recorded column is identically zero).
    """
    lib = require()
    rho, te_ev, ne, q = (np.ascontiguousarray(_f(v))
                         for v in (rho, te_ev, ne, q))
    n = rho.size
    if not (te_ev.size == ne.size == q.size == n):
        raise KernelError("bgb_chi: profile lengths disagree")
    a = [float("nan")] * 4 if alphas is None else [float(v) for v in alphas]
    chi_e = np.empty(n)
    chi_i = np.empty(n)
    rc = lib.fylite_rs_bgb_chi(rho, te_ev, ne, q, n, float(b0),
                               a[0], a[1], a[2], a[3], chi_e, chi_i)
    if rc != 0:
        raise KernelError(f"fylite_rs_bgb_chi returned {rc}")
    return chi_e, chi_i


_sig("fylite_rs_neutrals_mc",
     [_ARR, _ARR, _ARR, _ARR, _ARR, _U64] + [_F64] * 4 + [_U64, _U64]
     + [_ARR] * 5 + [_ARR], _I32)
def neutrals_mc(r_edges, ne, te_ev, ti_ev, ni, *, mass_amu=2.0, e0_ev=3.0,
                e_loss_ev=13.6, albedo=0.0, n_particles=200_000, seed=1):
    """1-D cylindrical Monte-Carlo neutral transport (neutrals.rs).

    ``r_edges``: n+1 shell edges [m]; plasma fields per shell (eV, m⁻³).
    Deterministic in ``seed``.  Every tally is PER UNIT SOURCE (one
    atom/s into the unit-length cylinder): scale by the physical influx
    — that number is the caller's, not the kernel's.  Returns a dict with
    ``n0`` [m⁻³], ``s_ion`` [m⁻³ s⁻¹], ``q_cx_i``/``q_ion_i``/``q_ion_e``
    [W m⁻³] (each per unit source), ``ionized``/``escaped`` fractions
    (their sum is exactly 1) and ``mean_cx``.
    """
    lib = require()
    r_edges, ne, te_ev, ti_ev, ni = (np.ascontiguousarray(_f(v))
                                     for v in (r_edges, ne, te_ev, ti_ev,
                                               ni))
    n = ne.size
    if r_edges.size != n + 1 or not (te_ev.size == ti_ev.size == ni.size
                                     == n):
        raise KernelError("neutrals_mc: r_edges must have n+1 entries and "
                          "the plasma fields n each")
    outs = [np.empty(n) for _ in range(5)]
    out3 = np.empty(3)
    rc = lib.fylite_rs_neutrals_mc(r_edges, ne, te_ev, ti_ev, ni, n,
                                   float(mass_amu), float(e0_ev),
                                   float(e_loss_ev), float(albedo),
                                   int(n_particles), int(seed), *outs,
                                   out3)
    if rc != 0:
        raise KernelError(f"fylite_rs_neutrals_mc returned {rc}")
    return {"n0": outs[0], "s_ion": outs[1], "q_cx_i": outs[2],
            "q_ion_i": outs[3], "q_ion_e": outs[4],
            "ionized": float(out3[0]), "escaped": float(out3[1]),
            "mean_cx": float(out3[2])}


_sig("fylite_rs_zerod_volume", [_F64, _F64, _F64], _F64)
def zerod_volume(r0, a, kappa) -> float:
    """Ellipsoidal plasma volume ``2 pi² R0 a² kappa`` [m³]."""
    return float(require().fylite_rs_zerod_volume(float(r0), float(a),
                                                  float(kappa)))


#: Order of the ten scalars ``zerod_evaluate`` / ``zerod_predict`` take.
#:
#: ★★From the GENERATED block declaration, and it had to be: this tuple's
#: ORDER is the wire format, and it was spelled in THREE places — here, and
#: twice as ``par[0]..par[9]`` in ``c_api.rs``.  Reorder any one of them and
#: every caller silently asks for a different discharge, because the array
#: is the right length and full of plausible numbers.  The file said as
#: much about a different table ten lines below, and this one stayed
#: hand-kept anyway.
ZEROD_PARAMS = tuple(row["key"] for row in
                     _fyo_interface.BLOCKS["ZEROD_PARAMS"])


def _zerod_par(params: dict) -> np.ndarray:
    missing = [k for k in ZEROD_PARAMS if k not in params]
    if missing:
        raise KernelError(f"zerod parameters missing: {missing}")
    return _f([params[k] for k in ZEROD_PARAMS])


#: What `zerod_waveform` can build; the index IS the ABI code, so append,
#: never reorder.
#: ★From the GENERATED table.  The INDEX is the wire format — the host
#: looks a name up and sends its position — so a tuple spelled here is a
#: contract kept in step with `zerod.rs` by hand.  Reorder either side and
#: every caller silently asks for a different waveform: the array that
#: comes back is the right length and full of plausible numbers.
WAVEFORMS = _WAVEFORM_NAMES

#: The phase names `zerod_waveform("phase", ...)` indexes into — the
#: kernel's own `zerod::PHASE_NAMES`, which it has always declared.
PHASE_NAMES = _PHASE_NAMES


_sig("fylite_rs_zerod_waveform", [_ARR, _ARR, _U64, ctypes.c_uint32, _F64, _F64, _F64, _ARR], _I32)
def zerod_waveform(phases, t, which: str, *, flat: float = 0.0,
                   start: float = 0.0, end: float = 0.0):
    """The discharge's shape in time — the kernel's.

    ``phases`` is ``(t_breakdown, t_rampup_end, t_flattop_end, t_end)``.
    ``which``: ``"trapezoid"`` (uses ``flat``/``start``/``end``),
    ``"ip"``/``"ne"``/``"te"`` (the centre waveform, only ``flat``),
    ``"actuator"`` (``flat`` = power, ``start``/``end`` = on/off times), or
    ``"phase"`` (the phase INDEX of each sample — see :data:`PHASE_NAMES`).

    ★★These decide what the run IS: the phase boundaries appear in the ramp
    rates, in the flux budget and in the label a slice is reported under.
    They read like plotting helpers and they are not — a second spelling of
    them is a second discharge wearing the same name, and both the Python
    layer and the browser page had one.
    """
    lib = require()
    try:
        code = WAVEFORMS.index(which)
    except ValueError:
        raise KernelError(f"unknown waveform {which!r}; "
                          f"have {list(WAVEFORMS)}") from None
    ph = _f(np.asarray(phases, float).ravel())
    if ph.size != 4:
        raise KernelError("phases must be 4: t_breakdown, t_rampup_end, "
                          "t_flattop_end, t_end")
    t_a = _f(np.atleast_1d(t))
    out = np.empty(t_a.size)
    rc = lib.fylite_rs_zerod_waveform(ph, t_a, t_a.size, code, float(flat),
                                      float(start), float(end), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_zerod_waveform returned {rc}")
    return out


def zerod_phase_labels(phases, t) -> list:
    """The phase NAME of each sample — :func:`zerod_waveform` with the
    spelling applied."""
    idx = zerod_waveform(phases, t, "phase").astype(int)
    return [PHASE_NAMES[i] for i in idx]


_sig("fylite_rs_zerod_profile", [_ARR, _U64, _F64, _F64, _F64, _ARR], _I32)
def zerod_profile(rho, centre: float, *, peaking: float = 1.5,
                  edge_frac: float = 0.05):
    """The prescribed radial shape ``(1 - rho²)^peaking`` with a finite
    edge, scaled to an on-axis value."""
    lib = require()
    r = _f(np.atleast_1d(rho))
    out = np.empty(r.size)
    rc = lib.fylite_rs_zerod_profile(r, r.size, float(centre),
                                     float(peaking), float(edge_frac), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_zerod_profile returned {rc}")
    return out


_sig("fylite_rs_zerod_fusion_power", ([_ARR] * 3 + [_U64, _F64, _F64, _ARR]), _I32)
def zerod_fusion_power(rho, ne, ti_kev, volume: float, *,
                       dt_fraction: float = 0.5):
    """D-T fusion power [W] and the alpha share, from prescribed profiles."""
    lib = require()
    r, n, t = (_f(np.atleast_1d(a)) for a in (rho, ne, ti_kev))
    out = np.empty(2)
    rc = lib.fylite_rs_zerod_fusion_power(r, n, t, r.size, float(volume),
                                          float(dt_fraction), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_zerod_fusion_power returned {rc}")
    return float(out[0]), float(out[1])


_sig("fylite_rs_zerod_loop_voltage", [_F64] * 8 + [_ARR], _I32)
def zerod_loop_voltage(ip: float, te_kev_avg: float, r0: float, a: float,
                       kappa: float, *, zeff: float = 1.8, li: float = 0.9,
                       dip_dt: float = 0.0):
    """``(V_loop, R_p, L_p)`` — Spitzer-like resistivity with a
    trapped-particle correction, plus the inductive term."""
    lib = require()
    out = np.empty(3)
    rc = lib.fylite_rs_zerod_loop_voltage(
        float(ip), float(te_kev_avg), float(r0), float(a), float(kappa),
        float(zeff), float(li), float(dip_dt), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_zerod_loop_voltage returned {rc}")
    return float(out[0]), float(out[1]), float(out[2])


_sig("fylite_rs_zerod_limits", [_F64] * 8 + [_ARR], _I32)
def zerod_limits(ip: float, r0: float, a: float, kappa: float, bt: float,
                 *, ne_bar: float, w_th: float, volume: float) -> dict:
    """The operating point's dimensionless standing.

    ``ne_bar`` is the LINE-averaged density — the average the Greenwald
    ratio is defined against; a central value here reads a peaked profile
    as further from the limit than it is (:func:`zerod_averages` returns
    both).  ``w_th`` is thermal and ``volume`` is the caller's, because
    which volume convention is meant is a question this layer must not
    answer silently.

    Returns ``{n_greenwald, f_greenwald, q_cyl, p_avg, b_pol, beta_t,
    beta_p, beta_n, f_troyon}``.  ``f_troyon`` is beta_N over the published
    Troyon no-wall coefficient 2.8 — a reference mark, not a limit this
    layer can compute.
    """
    lib = require()
    out = np.empty(9)
    rc = lib.fylite_rs_zerod_limits(
        float(ip), float(r0), float(a), float(kappa), float(bt),
        float(ne_bar), float(w_th), float(volume), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_zerod_limits returned {rc}")
    keys = ("n_greenwald", "f_greenwald", "q_cyl", "p_avg", "b_pol",
            "beta_t", "beta_p", "beta_n", "f_troyon")
    return dict(zip(keys, (float(v) for v in out)))


_sig("fylite_rs_zerod_flux_budget",
     [_ARR] * 3 + [_U64, _ARR] + [_F64] * 5 + [_ARR], _I32)
def zerod_flux_budget(t, v_loop, ip, phases, *, r0: float, a: float,
                      li: float = 0.9, c_ejima: float = 0.45,
                      phi_avail: float = 0.0) -> dict:
    """The poloidal-flux account of a pulse [Wb].

    ``phases`` is ``[t_breakdown, t_rampup_end, t_flattop_end, t_end]``.
    ``phi_avail`` is the swing the machine can deliver; 0 leaves
    ``t_sustain`` at ``None`` — a machine that has not stated its swing
    must read as unknown rather than as generous.
    """
    lib = require()
    tv, vv, iv = _f(t), _f(v_loop), _f(ip)
    if not (tv.size == vv.size == iv.size):
        raise KernelError("t, v_loop and ip must be the same length")
    out = np.empty(7)
    rc = lib.fylite_rs_zerod_flux_budget(
        tv, vv, iv, tv.size, _f(phases), float(r0), float(a), float(li),
        float(c_ejima), float(phi_avail), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_zerod_flux_budget returned {rc}")
    keys = ("phi_ind", "phi_res_ramp", "phi_ramp", "phi_consumed",
            "v_flattop", "l_p")
    res = dict(zip(keys, (float(v) for v in out[:6])))
    res["t_sustain"] = None if out[6] < 0 else float(out[6])
    return res


_sig("fylite_rs_zerod_stored_energy", [_ARR] * 4 + [_U64, _F64], _F64)
def zerod_stored_energy(rho, ne, te_kev, ti_kev, volume: float) -> float:
    """Thermal stored energy [J] of prescribed profiles."""
    lib = require()
    r, n, te, ti = _f(rho), _f(ne), _f(te_kev), _f(ti_kev)
    if not (r.size == n.size == te.size == ti.size):
        raise KernelError("rho, ne, te and ti must be the same length")
    w = lib.fylite_rs_zerod_stored_energy(r, n, te, ti, r.size, float(volume))
    if not np.isfinite(w):
        raise KernelError("fylite_rs_zerod_stored_energy refused the call")
    return float(w)


_sig("fylite_rs_zerod_averages", [_ARR, _ARR, _U64, _ARR], _I32)
def zerod_averages(rho, f) -> dict:
    """``{line, volume}`` — the two averages this layer distinguishes.

    Both, always: the Greenwald ratio takes the LINE average and the stored
    energy the volume one, and which is meant is exactly the question that
    gets answered wrongly.
    """
    lib = require()
    r, v = _f(rho), _f(f)
    if r.size != v.size:
        raise KernelError("rho and f must be the same length")
    out = np.empty(2)
    rc = lib.fylite_rs_zerod_averages(r, v, r.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_zerod_averages returned {rc}")
    return {"line": float(out[0]), "volume": float(out[1])}


_sig("fylite_rs_strike_points",
     [_F64] * 4 + [_U64, _U64, _ARR, _F64, _ARR, _ARR, _U64, _U64, _ARR], _I32)
def strike_points(grid, psi, psi_bnd: float, wall_r, wall_z,
                  max_n: int = 16):
    """Where the boundary surface meets the wall — ``(n, 2)`` of ``(R, Z)``.

    ★A diverted configuration is a TOPOLOGY, not a shape, and this is the
    observable that says which one you have: a limiter plasma touches the
    wall on its own boundary, a diverted one lands its legs somewhere the
    boundary never goes.  A limiter-bounded field legitimately returns one
    or two points; the caller distinguishes the cases by the boundary kind
    the solve already reports, not by counting these.
    """
    lib = require()
    g = grid if isinstance(grid, Grid) else grid_of(*grid)
    p = _f(np.asarray(psi))
    wr, wz = _f(np.atleast_1d(wall_r)), _f(np.atleast_1d(wall_z))
    out = np.empty(2 * int(max_n))
    n = lib.fylite_rs_strike_points(
        g.r0, g.z0, g.dr, g.dz, g.nr, g.nz, p.ravel(), float(psi_bnd),
        wr, wz, wr.size, int(max_n), out)
    if n < 0:
        raise KernelError(f"fylite_rs_strike_points returned {n}")
    return out[:2 * n].reshape(-1, 2)


_sig("fylite_rs_wall_clearance", [_ARR, _ARR, _U64, _ARR, _ARR, _U64, _ARR],
     _I32)
def wall_clearance(bnd_r, bnd_z, wall_r, wall_z) -> dict:
    """``{gap, r, z}`` — the smallest boundary-to-wall distance [m] and
    where on the boundary it occurs.  Measured to the wall POLYLINE, not to
    its vertices: a coarse wall description would otherwise report a gap up
    to half a segment too large, which is the wrong sign of error for a
    clearance."""
    lib = require()
    br, bz = _f(np.atleast_1d(bnd_r)), _f(np.atleast_1d(bnd_z))
    wr, wz = _f(np.atleast_1d(wall_r)), _f(np.atleast_1d(wall_z))
    out = np.empty(3)
    rc = lib.fylite_rs_wall_clearance(br, bz, br.size, wr, wz, wr.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_wall_clearance returned {rc}")
    return {"gap": float(out[0]), "r": float(out[1]), "z": float(out[2])}


_sig("fylite_rs_fill_filaments", [_ARR, _ARR, _U64, _F64, _U64, _F64, _ARR],
     _I32)
def fill_filaments(bnd_r, bnd_z, ip: float, *, n_ring: int = 4,
                   peaking: float = 1.0):
    """Fill a boundary with current filaments — ``(n, 3)`` of ``(R, Z, A)``.

    A START model and nothing more: no equilibrium is in it, which is why
    the weighting is an argument rather than a hidden choice.
    """
    lib = require()
    br, bz = _f(np.atleast_1d(bnd_r)), _f(np.atleast_1d(bnd_z))
    out = np.empty(3 * br.size * int(n_ring))
    n = lib.fylite_rs_fill_filaments(br, bz, br.size, float(ip),
                                     int(n_ring), float(peaking), out)
    if n < 0:
        raise KernelError(f"fylite_rs_fill_filaments returned {n}")
    return out[:3 * n].reshape(-1, 3)


_sig("fylite_rs_start_currents",
     ([_ARR] * 6 + [_U64, _ARR, _U64] + [_ARR] * 2 + [_U64] + [_ARR] * 3
      + [_U64] + [_F64] * 2 + [ctypes.c_uint32] + [_F64] * 3 + [_VOID]
      + [_U64] * 2 + [_ARR] * 3), _I32)
def start_currents(elements, weights, bnd_r, bnd_z, filaments, *,
                   x_point=None, x_weight: float = 1.0, length: float = 1.0,
                   lam: float = 1e-3, i_max=None, nu: int = 3,
                   nv: int = 3) -> dict:
    """The channel currents that make ``bnd`` an isoflux contour.

    The state a shape anneal is entitled to BEGIN from — :func:`~fylite.
    scenario.design.discharge` refuses a zero start for exactly this
    reason.  It is not an equilibrium: force balance is nowhere in it, and
    what comes back beside the currents (``psi_rms``, ``b_x``) says how
    well the request could be met at all, before an equilibrium is paid
    for.

    ``elements`` is the coil element list, ``weights`` the
    ``(n_channel, n_element)`` map, ``filaments`` an ``(n, 3)`` cloud of
    ``(R, Z, A)`` (see :func:`fill_filaments`).  With ``x_point`` given the
    X point gets THREE rows — its own isoflux row plus ``B_r = B_z = 0`` —
    because a null pinned at a different flux level is not a divertor.
    """
    lib = require()
    ea = [_f(np.atleast_1d(x)) for x in elements]
    ne = ea[0].size
    w_map = np.atleast_2d(np.asarray(weights, float))
    if w_map.shape[1] != ne:
        raise KernelError(f"weights has {w_map.shape[1]} columns, expected "
                          f"{ne} (one per element)")
    nch = w_map.shape[0]
    wt = _f(w_map.T)
    br, bz = _f(np.atleast_1d(bnd_r)), _f(np.atleast_1d(bnd_z))
    fil = np.atleast_2d(np.asarray(filaments, float))
    if fil.shape[1] != 3:
        raise KernelError("filaments must be (n, 3) of (R, Z, amps)")
    fr, fz, fa = _f(fil[:, 0]), _f(fil[:, 1]), _f(fil[:, 2])
    i_max_a = None if i_max is None else _f(np.atleast_1d(i_max))
    out, flags, stats = np.empty(nch), np.empty(nch), np.empty(4)
    rc = lib.fylite_rs_start_currents(
        *ea, ne, wt.ravel(), nch, br, bz, br.size, fr, fz, fa, fr.size,
        0.0 if x_point is None else float(x_point[0]),
        0.0 if x_point is None else float(x_point[1]),
        0 if x_point is None else 1, float(x_weight), float(length),
        float(lam), None if i_max_a is None else i_max_a.ctypes.data,
        int(nu), int(nv), out, flags, stats)
    if rc != 0:
        raise KernelError(f"fylite_rs_start_currents returned {rc}")
    return {"aturns": out, "psi_rms": float(stats[0]),
            "b_x": None if stats[1] < 0 else float(stats[1]),
            "psi_x_offset": float(stats[2]),
            "at_bound": np.flatnonzero(flags == 1.0)}


_sig("fylite_rs_feedforward_voltages",
     [_ARR, _ARR, _U64, _U64, _ARR, _U64, _ARR, _ARR, _ARR], _I32)
def feedforward_voltages(m, r, n_ch: int, t, x) -> dict:
    """The channel voltages a PRESCRIBED current trajectory needs.

    The exact inverse of :func:`evolve_circuits` — same implicit Euler,
    same interval-end sample — so a design made here and checked there
    agrees to solver precision rather than to a tolerance.  ``x`` is
    ``(n_t, n_ch)``; returns ``{v, y}`` with ``v`` the per-channel voltages
    and ``y`` the passive currents they induce.
    """
    lib = require()
    mm, rr = _f(np.asarray(m)), _f(np.atleast_1d(r))
    n = rr.size
    tv = _f(np.atleast_1d(t))
    xx = _f(np.atleast_2d(x))
    if xx.shape != (tv.size, int(n_ch)):
        raise KernelError(f"x is {xx.shape}, expected {(tv.size, int(n_ch))}")
    v = np.empty(tv.size * int(n_ch))
    y = np.empty(tv.size * (n - int(n_ch)))
    rc = lib.fylite_rs_feedforward_voltages(
        mm.ravel(), rr, n, int(n_ch), tv, tv.size, xx.ravel(), v, y)
    if rc != 0:
        raise KernelError(f"fylite_rs_feedforward_voltages returned {rc}")
    return {"v": v.reshape(tv.size, int(n_ch)),
            "y": y.reshape(tv.size, n - int(n_ch))}


_sig("fylite_rs_zerod_evaluate", ([_ARR] * 5 + [_U64, _ARR, _U64] + [_ARR] * 4), _I32)
def zerod_evaluate(t, ip, ne0, te0, p_inj, rho, params: dict) -> dict:
    """One pass over a prescribed discharge (kernel ``zerod::evaluate``).

    Returns the four traces (``v_loop``, ``p_fus``, ``p_alpha``, ``q``), the
    three prescribed profiles as ``(nt, nr)`` arrays, and the volume used.
    """
    lib = require()
    t, ip, ne0, te0, p_inj, rho = (_f(t), _f(ip), _f(ne0), _f(te0),
                                   _f(p_inj), _f(rho))
    nt, nr = t.size, rho.size
    scal = np.empty(4 * nt)
    prof = np.empty(3 * nt * nr)
    vol = np.empty(1)
    rc = lib.fylite_rs_zerod_evaluate(t, ip, ne0, te0, p_inj, nt, rho, nr,
                                      _zerod_par(params), scal, prof, vol)
    if rc != 0:
        raise KernelError(f"fylite_rs_zerod_evaluate returned {rc}")
    s = scal.reshape(4, nt)
    p = prof.reshape(3, nt, nr)
    return {"v_loop": s[0], "p_fus": s[1], "p_alpha": s[2], "q": s[3],
            "ne": p[0], "te": p[1], "ti": p[2], "volume": float(vol[0])}


#: The confinement scalings ``zerod_predict`` accepts, by kernel index.
#: An unknown name is refused here and an unknown index is refused by the
#: kernel — neither side defaults to a law the caller did not ask for.
#: The scaling laws `TauLaw::from_index` decodes, in index order.
TAU_LAWS = _TAU_LAW_NAMES


_sig("fylite_rs_zerod_predict", ([_ARR] * 4 + [_U64, _ARR, _U64] + [_ARR] * 2 + [_ARR, _ARR]), _I32)
def zerod_predict(t, ip, ne0, p_aux, rho, params: dict, *,
                  law: str = "ipb98y2", h_factor: float = 1.0,
                  m_eff: float = 2.5, bt: float = 0.0, w0: float = 0.0) -> dict:
    """Energy-balance prediction (kernel ``zerod::predict``).

    ★A different KIND of answer from :func:`zerod_evaluate`: there the
    stored energy is the user's own profile read back, here it is solved
    from ``dW/dt = P_heat - W/tau_E``.  The two must not be shown side by
    side unlabelled — nothing in the numbers distinguishes them.
    """
    lib = require()
    try:
        idx = TAU_LAWS.index(law)
    except ValueError:
        raise KernelError(f"unknown confinement scaling {law!r}; have "
                          f"{list(TAU_LAWS)}") from None
    t, ip, ne0, p_aux, rho = _f(t), _f(ip), _f(ne0), _f(p_aux), _f(rho)
    nt = t.size
    pred = _f([idx, h_factor, m_eff, bt, w0])
    scal = np.empty(8 * nt)
    vol = np.empty(1)
    rc = lib.fylite_rs_zerod_predict(t, ip, ne0, p_aux, nt, rho, rho.size,
                                     _zerod_par(params), pred, scal, vol)
    if rc != 0:
        raise KernelError(f"fylite_rs_zerod_predict returned {rc}")
    s = scal.reshape(8, nt)
    #: ``balance`` is the sum-of-terms residual, NOT integrator-vs-budget:
    #: the kernel's integrator is exact, so that difference is identically
    #: zero and would test nothing.
    return {"w_th": s[0], "tau_e": s[1], "te0": s[2], "p_ohm": s[3],
            "p_alpha": s[4], "p_heat": s[5], "p_lh": s[6], "balance": s[7],
            "volume": float(vol[0])}


# --------------------------------------------------------------------------- #
# 1.5-D transport step (transport.rs)
# --------------------------------------------------------------------------- #
#: The closures ``transport_step`` accepts.  ★They are not four settings of
#: one model: 0 and 1 are prescribed, 2 evaluates Chang-Hinton INSIDE the
#: Picard loop (freezing it on the entry temperature converges just as
#: smoothly onto a different equation's answer), and 3 takes a chi the caller
#: computed — which is how a turbulent closure is said to belong to the OUTER
#: loop rather than pretended into the inner one.
TRANSPORT_MODELS = {"constant": 0, "stiff": 1, "neoclassical": 2, "given": 3}


# the 1.5D transport step.  `model` 2 carries the neoclassical closure,
# whose five extra blocks are null for models 0 and 1 — declared as
# `c_void_p` so `None` is a legal argument rather than an ndarray that
# has to be conjured for a model that ignores it.
_sig("fylite_rs_transport_step", ( [_ARR, _ARR, _U64, _ARR, _ARR, _ARR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, _I32] + [_F64] * 3 + [_F64] * 7 + [_U64] + [ctypes.c_void_p] * 2 + [_U64] + [ctypes.c_void_p] * 3 + [_ARR, _ARR]), _I32)
def transport_step(x, y_old, *, vprime, source, velocity=None,
                   capacity=None, metric=None, capacity_old=None,
                   model="constant",
                   p0: float = 1.0, p1: float = 0.0, p2: float = 0.0,
                   dt: float = float("inf"), theta: float = 1.0,
                   edge_value: float | None = None, relax: float = 1.0,
                   relax_coeff: float = 1.0, d_pc: float = 0.0,
                   tol: float = 1e-10,
                   max_inner: int = 200, neo=None, chi_given=None) -> dict:
    """One theta-implicit finite-volume step of the 1.5-D transport equation.

    ``neo`` (model 2 only) is ``{"surf": (20n,), "ion": (6*nion*n,),
    "nion": int, "scal5": (5,), "chigb": (n,) or None}``; ``chi_given``
    (model 3 only) is the per-point diffusivity, held fixed for the whole
    solve.

    ``capacity_old`` is the capacity at the START of the step — the
    ``dV'/dt`` term, and the one piece of the standard 1.5-D form this
    operator could not express.  ``None`` (the default) is "the capacity did
    not move", and is the same arithmetic bit for bit; the companion half,
    the label's own motion, is a convection and rides in ``velocity``
    (:func:`label_drift` builds it).

    ``d_pc`` is the Pereverzev–Corrigan coefficient: it conditions a stiff
    closure's Picard loop and leaves the converged profile alone (the two
    artificial terms cancel discretely at the iterate, which the kernel's
    own gate asserts rather than assumes).

    ``dt = inf`` with ``theta = 1`` is the steady solve.  Returns the new
    profile plus the inner-iteration count, the converged flag and the
    residual — a step that stopped at ``max_inner`` says so rather than
    handing back where it happened to be.
    """
    lib = require()
    x, y_old = _f(x), _f(y_old)
    n = x.size
    m = TRANSPORT_MODELS.get(model, model)
    if m not in TRANSPORT_MODELS.values():
        raise KernelError(f"unknown closure {model!r}; have "
                          f"{sorted(TRANSPORT_MODELS)}")
    vp = _f(vprime)
    vel = np.zeros(n) if velocity is None else _f(velocity)
    src = _f(source)
    cap = None if capacity is None else _f(capacity)
    met = None if metric is None else _f(metric)
    cap_old = None if capacity_old is None else _f(capacity_old)
    if m == 2 and neo is None:
        raise KernelError("closure 'neoclassical' needs the neo blocks")
    if m == 3 and chi_given is None:
        raise KernelError("closure 'given' needs chi_given")
    surf = ion = scal = chigb = None
    nion = 0
    if neo is not None:
        surf, ion = _f(neo["surf"]), _f(neo["ion"])
        nion = int(neo.get("nion", 1))
        scal = _f(neo["scal5"])
        chigb = None if neo.get("chigb") is None else _f(neo["chigb"])
    chi = None if chi_given is None else _f(chi_given)
    out = np.empty(n)
    info = np.empty(3)
    rc = lib.fylite_rs_transport_step(
        x, y_old, n, vp, vel, src,
        None if cap is None else cap.ctypes.data,
        None if met is None else met.ctypes.data,
        None if cap_old is None else cap_old.ctypes.data,
        int(m), float(p0), float(p1), float(p2), float(dt), float(theta),
        float("nan") if edge_value is None else float(edge_value),
        float(relax), float(relax_coeff), float(d_pc),
        float(tol), int(max_inner),
        None if surf is None else surf.ctypes.data,
        None if ion is None else ion.ctypes.data, nion,
        None if scal is None else scal.ctypes.data,
        None if chigb is None else chigb.ctypes.data,
        None if chi is None else chi.ctypes.data,
        out, info)
    if rc != 0:
        raise KernelError(
            f"fylite_rs_transport_step returned {rc}"
            + (" — the neoclassical map refused a surface, which during an "
               "iteration means the temperature there reached zero or below"
               if rc == -20 else ""))
    return {"y": out, "inner_iterations": int(info[0]),
            "converged": bool(info[1]), "residual": float(info[2])}


_sig("fylite_rs_interpretive_channel", ( [_ARR] * 7 + [_U64, _F64] + [_ARR] * 4), _I32)
def interpretive_channel(rho, *, vprime, gm7, gm3, density, temperature,
                         source_density, grad_floor: float = 1e-3) -> dict:
    """Analysis-mode inversion of one channel's power balance.

    The other direction of :func:`transport_step`: measured profiles and
    source densities in, the experimental heat flux ``q_pb`` [W/m²], the
    cumulative power [W], and the effective diffusivity [m²/s] out.

    ★``gm7`` (⟨|∇ρ|⟩) carries the flux and ``gm3`` (⟨|∇ρ|²⟩) the conduction
    law — upstream's convention, so a profile produced by a χ₀ conduction
    solve inverts to ``χ₀/gm7``.  Points whose gradient is below
    ``grad_floor`` times the profile's characteristic gradient come back
    ``NaN`` with ``valid = False``.
    """
    lib = require()
    rho = _f(rho)
    n = rho.size
    args = [_f(a) for a in (vprime, gm7, gm3, density, temperature,
                            source_density)]
    for a in args:
        if a.size != n:
            raise KernelError("every profile must be as long as rho")
    q_pb, power, chi, valid = (np.empty(n) for _ in range(4))
    rc = lib.fylite_rs_interpretive_channel(rho, *args, n, float(grad_floor),
                                            q_pb, power, chi, valid)
    if rc != 0:
        raise KernelError(f"fylite_rs_interpretive_channel returned {rc}")
    return {"q_pb": q_pb, "power_cum": power, "chi_eff": chi,
            "valid": valid.astype(bool)}


# --------------------------------------------------------------------------- #
# flux-surface geometry (surfaces.rs)
# --------------------------------------------------------------------------- #
_sig("fylite_rs_trace_surface", ([_F64] * 4 + [_U64, _U64, _ARR] + [_F64] * 3 + [_ARR, _ARR, _U64, _U64, _ARR, _ARR]), _I32)
def trace_surface(grid: Grid, psi, level, *, axis, limiter, n_theta: int = 181):
    """Ray-trace one flux surface and integrate over it.

    ``axis`` is ``(R, Z)`` of the magnetic axis, ``limiter`` a pair of
    arrays.  Returns the polygon plus the surface integrals the transport
    metrics are built from — ``gq``, ``perimeter``, ``dl_over_grad``,
    ``dv_dpsi``, ``volume``.  They come from the SAME traced polygon,
    which is the point: a second contouring library would give a second
    polygon, and the integrals would then disagree for reasons no test
    could attribute.
    """
    lib = require()
    psi = _f(psi)
    if psi.shape != (grid.nr, grid.nz):
        raise KernelError(f"psi has shape {psi.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    lr, lz = _f(limiter[0]), _f(limiter[1])
    rz = np.empty(2 * int(n_theta))
    info = np.empty(6)
    rc = lib.fylite_rs_trace_surface(*grid.args, psi.ravel(), float(level),
                                     float(axis[0]), float(axis[1]),
                                     lr, lz, lr.size, int(n_theta), rz, info)
    if rc < 0:
        raise KernelError(f"fylite_rs_trace_surface returned {rc}")
    poly = rz[:2 * rc].reshape(rc, 2)
    return {"poly": poly, "n": int(rc), "gq": info[1], "perimeter": info[2],
            "dl_over_grad": info[3], "dv_dpsi": info[4], "volume": info[5]}


_sig("fylite_rs_gradient", [_ARR, _ARR, _U64, _I32, _F64, _ARR], _I32)
def gradient(y, x, *, log: bool = False, floor: float | None = None):
    """``dy/dx``, or the normalised inverse scale length ``-d ln y/dx``.

    ★Here rather than in each caller because the END RULE is a choice: a
    one-sided first-order end against a second-order interior is one
    convention among several, and two modules choosing differently produce
    profiles that differ only at the axis — where a transport solve is most
    sensitive and least checkable.

    ``floor`` (log only) says what a non-positive value means: a number
    clamps to it, ``None`` yields ``NaN`` there.
    """
    lib = require()
    y, x = _f(y), _f(x)
    if y.size != x.size:
        raise KernelError("y and x must be the same length")
    out = np.empty(y.size)
    rc = lib.fylite_rs_gradient(y, x, y.size, 1 if log else 0,
                                float("nan") if floor is None else float(floor),
                                out)
    if rc != 0:
        raise KernelError(f"fylite_rs_gradient returned {rc}")
    return out


_sig("fylite_rs_beam_deposit", ( [_F64] * 4 + [_U64, _U64, _ARR] + [_F64] * 5 + [_U64, _U64, _U64, _F64] + [_ARR] * 3 + [_U64, _ARR, _U64] + [_F64] * 2 + [ctypes.c_uint32] * 2 + [_F64] * 5 + [_ARR, _ARR]), _I32)
def beam_deposit(grid: Grid, psin2d, *, tangency_radius: float,
                 z_height: float, width_r: float, width_z: float,
                 direction: float, n_width_r: int, n_width_z: int,
                 n_samples: int, r_start: float, psin_prof, ne, te,
                 psin_edges, mass: float, energy: float,
                 model: str = "janev", impurity_form: str = "exp",
                 **imp) -> dict:
    """One energy component of one beam over its finite cross-section.

    ★★The footprint's rays, their geometry, the profile evaluation at the
    ray's OWN samples, the attenuation and the binning — one call.  Each of
    those was a decision (``pitch(R) = R_tan/R`` exactly rather than by
    finite difference; which nodes and weights sample the width; where the
    profile is read), and each lived in a different host.

    Returns ``{absorbed, pitch_weighted, shinethrough}`` per ψ_N shell.
    """
    lib = require()
    f = _f(psin2d)
    if f.shape != (grid.nr, grid.nz):
        raise KernelError(f"psin2d has shape {f.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    pp, ne_a = _f(psin_prof), _f(ne)
    te_a, ed = _f(te), _f(psin_edges)
    n_shell = ed.size - 1
    out, shine = np.empty(2 * n_shell), np.empty(1)
    ii = _imp5(**imp)
    rc = lib.fylite_rs_beam_deposit(
        *grid.args, f.ravel(), float(tangency_radius), float(z_height),
        float(width_r), float(width_z), float(direction), int(n_width_r),
        int(n_width_z), int(n_samples), float(r_start), pp, ne_a, te_a,
        pp.size, ed, n_shell, float(mass), float(energy),
        BEAM_STOPPING_MODELS[model], IMPURITY_FORMS[impurity_form],
        *(float(v) for v in ii), out, shine)
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_deposit returned {rc}")
    return {"absorbed": out[:n_shell], "pitch_weighted": out[n_shell:],
            "shinethrough": float(shine[0])}


_sig("fylite_rs_shell_table", ([_F64] * 4 + [_U64, _U64, _ARR] + [_F64] * 2 + [_ARR, _ARR, _U64, _ARR, _U64, _U64, _ARR]), _I32)
def shell_table(grid: Grid, psin2d, *, axis, limiter, levels,
                n_theta: int = 181) -> dict:
    """The shell table a deposition model bins into: enclosed volume and
    mid-surface geometry on a ψ_N EDGE grid.

    Returns ``{volume, dvolume, rminor, rmajor, kappa}``.  ★The tracing, the
    gap repair and the ``V(0) = 0`` convention are the kernel's: a level that
    fails to trace leaves a gap, and how each quantity may be repaired
    (volume and minor radius cannot decrease outward; major radius and
    elongation have no such rule) is a statement about the quantity, not a
    detail of the loop.
    """
    lib = require()
    f = _f(psin2d)
    if f.shape != (grid.nr, grid.nz):
        raise KernelError(f"psin2d has shape {f.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    lr, lz = _f(np.atleast_1d(limiter[0])), _f(np.atleast_1d(limiter[1]))
    lv = _f(np.atleast_1d(levels))
    out = np.empty(4 * lv.size)
    rc = lib.fylite_rs_shell_table(*grid.args, f.ravel(), float(axis[0]),
                                   float(axis[1]), lr, lz, lr.size, lv,
                                   lv.size, int(n_theta), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_shell_table returned {rc}")
    n = lv.size
    vol = out[:n].copy()
    return {"volume": vol, "dvolume": np.diff(vol),
            "rminor": out[n:2 * n].copy(), "rmajor": out[2 * n:3 * n].copy(),
            "kappa": out[3 * n:].copy()}


_sig("fylite_rs_flux_jacobian", (_ARR, _U64, _ARR, _U64, _F64, _ARR), _I32)
def flux_jacobian(f0, perturbed, *, dx: float, n_evolve: int):
    """The finite-difference Jacobian of a flux match, from evaluations the
    CALLER made (``perturbed[ip]`` = the vector with channel ``ip`` moved by
    ``dx`` at every radius).

    ★The index pattern — which difference lands in which entry — is the
    whole content of "one evaluation per channel, exact for a local model",
    so it lives here rather than in the loop that calls the models.
    """
    lib = require()
    a = _f(f0)
    b = _f(np.ascontiguousarray(perturbed, dtype=float))
    out = np.empty(a.size * a.size)
    rc = lib.fylite_rs_flux_jacobian(a, a.size, b.ravel(), int(n_evolve),
                                     float(dx), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_flux_jacobian returned {rc}")
    return out.reshape(a.size, a.size)


_sig("fylite_rs_lh_deposit", ([_ARR] * 6 + [_U64] + [_ARR] * 3 + [_U64] + [_F64] * 4 + [ctypes.c_uint32] + [_ARR] * 3), _I32)
def lh_deposit(psin_c, *, dvol, rmaj, ne, te, f_pol, bands, powers,
               eta_cd: float, r0: float, xi: float = 3.0,
               width_floor: float = 0.05, cd_model: str = "fisch") -> dict:
    """The whole lower-hybrid deposition chain on a shell grid.

    ``bands`` is one ``(n_par_lo, n_par_hi)`` per launcher — the EFFECTIVE
    band, up-shift already applied — and ``powers`` the absorbed power [W].

    ★★One entry rather than six calls in a loop: which surfaces the wave can
    reach, where each band end resonates, and what the spread between those
    ends means for ``sigma_j`` are decisions that only make sense together.
    Assembled in the caller they were six chances for a host to differ.

    Returns ``{psin, j_lh, sigma_j, p_dep, n_acc, i_lau, res_lo, res_hi,
    i_lh, ne_bar}``; ``res_*`` carry NaN where a band end resonates nowhere,
    which is a result and not an error.
    """
    lib = require()
    ps = _f(psin_c)
    n = ps.size
    dv, rm, ne_a, te_a, fp = (_f(np.broadcast_to(np.atleast_1d(x), (n,)))
                              for x in (dvol, rmaj, ne, te, f_pol))
    b = np.atleast_2d(np.asarray(bands, float))
    lo, hi = _f(b[:, 0]), _f(b[:, 1])
    pw = _f(np.broadcast_to(np.atleast_1d(np.asarray(powers, float)),
                            lo.shape))
    try:
        code = LH_EFFICIENCY_MODELS.index(cd_model)
    except ValueError:
        raise KernelError(f"unknown LH efficiency model {cd_model!r}; "
                          f"have {list(LH_EFFICIENCY_MODELS)}") from None
    fields = np.empty(4 * n)
    per = np.empty(3 * lo.size)
    scal = np.empty(2)
    rc = lib.fylite_rs_lh_deposit(ps, dv, rm, ne_a, te_a, fp, n, lo, hi, pw,
                                  lo.size, float(eta_cd), float(r0),
                                  float(xi), float(width_floor), code,
                                  fields, per, scal)
    if rc != 0:
        raise KernelError(f"fylite_rs_lh_deposit returned {rc}")
    nl = lo.size
    return {"psin": ps, "j_lh": fields[:n], "sigma_j": fields[n:2 * n],
            "p_dep": fields[2 * n:3 * n], "n_acc": fields[3 * n:],
            "i_lau": per[:nl], "res_lo": per[nl:2 * nl],
            "res_hi": per[2 * nl:], "i_lh": float(scal[0]),
            "ne_bar": float(scal[1])}


_sig("fylite_rs_x_points", ([_F64] * 4 + [_U64, _U64, _ARR] + [_F64] * 6 + [_ARR, _U64]), _I32)
def x_points(grid: Grid, psi, *, psi_axis: float, psi_bnd: float, axis,
             psin_window: float = 0.15, min_axis_dist: float = 0.25,
             max_out: int = 8) -> list[dict]:
    """The ψ map's saddle points — the X-points, ranked and de-duplicated.

    ``psi`` is the FULL flux on the grid, R-major.  Returns at most two dicts
    ``{r, z, psin, grad}``, nearest ψ_N = 1 first; an empty list means the
    configuration is limited as far as the grid resolution can tell.

    ★All of the policy (Hessian test, the ``|∇ψ|`` local-minimum test, the
    ψ_N window, the axis distance, the discarded over-long Newton step, the
    two-cell dedup) is the kernel's.  It used to be numpy inside the
    PLOTTING module, so "is this discharge diverted" depended on which
    module you asked.
    """
    lib = require()
    psi = _f(psi)
    if psi.shape != (grid.nr, grid.nz):
        raise KernelError(f"psi has shape {psi.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    out = np.empty(4 * int(max_out))
    n = lib.fylite_rs_x_points(grid.r0, grid.z0, grid.dr, grid.dz, grid.nr,
                               grid.nz, psi.ravel(), float(psi_axis),
                               float(psi_bnd), float(axis[0]), float(axis[1]),
                               float(psin_window), float(min_axis_dist),
                               out, int(max_out))
    if n < 0:
        raise KernelError(f"fylite_rs_x_points returned {n}")
    rows = out[:4 * n].reshape(n, 4)
    return [{"r": float(a), "z": float(b), "psin": float(c), "grad": float(d)}
            for a, b, c, d in rows]


_sig("fylite_rs_interp", (_ARR, _U64, _ARR, _ARR, _U64, _ARR), _I32)
def interp(x, xp, yp):
    """Piecewise-linear interpolation — ``numpy.interp``'s semantics, one host.

    Ends clamp to the end values.  ★This exists so the package has ONE
    interpolation: the end rule and the interior spelling are conventions,
    and two call sites choosing differently produce profiles that agree in
    the middle and differ exactly where a profile is read hardest (the axis
    and the edge).  Bit-identical to the ``numpy.interp`` it replaces.

    Scalar in, scalar out — the shape of ``x`` comes back.
    """
    lib = require()
    xa = np.asarray(x, dtype=float)
    xf, xps, yps = _f(np.atleast_1d(xa)), _f(xp), _f(yp)
    if yps.size != xps.size:
        raise KernelError("interp: xp and yp must be the same length")
    out = np.empty(xf.size)
    rc = lib.fylite_rs_interp(xf, xf.size, xps, yps, xps.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_interp returned {rc}")
    return out.reshape(xa.shape) if xa.ndim else out[0]


_sig("fylite_rs_resample_uniform", (_ARR, _U64, _ARR, _U64), _I32)
def resample_uniform(src, n: int):
    """A uniformly-sampled profile onto ``n`` uniform points of the same span."""
    lib = require()
    src = _f(src)
    out = np.empty(int(n))
    rc = lib.fylite_rs_resample_uniform(src, src.size, out, out.size)
    if rc != 0:
        raise KernelError(f"fylite_rs_resample_uniform returned {rc}")
    return out


_sig("fylite_rs_to_uniform_extrap", (_ARR, _ARR, _U64, _ARR, _U64), _I32)
def to_uniform_extrap(x, y, n: int):
    """A profile on an arbitrary increasing grid onto ``n`` uniform points of
    ``[0, 1]``, **extrapolated** past both ends.

    ★Not :func:`interp` with a flag: the caller has a profile traced over an
    interior window (a browser session traces ``q`` over roughly
    [0.06, 0.995] — the axis contour degenerates and the separatrix is
    singular) and needs it on all of [0, 1].  Clamping there writes a FLAT
    profile across the axis, i.e. zero shear where the shear is largest.
    """
    lib = require()
    x, y = _f(x), _f(y)
    out = np.empty(int(n))
    rc = lib.fylite_rs_to_uniform_extrap(x, y, x.size, out, out.size)
    if rc != 0:
        raise KernelError(f"fylite_rs_to_uniform_extrap returned {rc}")
    return out


_sig("fylite_rs_q_profile", ([_F64] * 4 + [_U64, _U64, _ARR] + [_F64] * 4 + [_ARR, _ARR, _U64] + [_ARR, _ARR, _U64] + [_U64, _U64] + [_F64, _F64] + [_ARR, _ARR]), _I32)
def q_profile(grid: Grid, psi, *, psi_axis: float, psi_bnd: float, axis,
              limiter, f_x, f_val, n_q: int = 12, n_theta: int = 181,
              x_lo: float = 0.02, x_hi: float = 0.95) -> dict:
    """Safety factor on a ladder of traced surfaces.

    ``f_x``/``f_val`` give F on the normalised flux label (a profile rather
    than a callback: a callback cannot cross the ABI, and every caller has a
    profile anyway).  ``q0`` is a linear extrapolation to the axis from the
    innermost traced pair and ``q95`` an interpolation at 0.95 — both are
    CONVENTIONS, stated by the kernel so two callers do not produce two
    incomparable q0s; they come back NaN when fewer than two surfaces
    traced.
    """
    lib = require()
    psi = _f(psi)
    if psi.shape != (grid.nr, grid.nz):
        raise KernelError(f"psi has shape {psi.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    lr, lz = _f(limiter[0]), _f(limiter[1])
    fx, fv = _f(f_x), _f(f_val)
    out = np.empty(2 * int(n_q))
    info = np.empty(3)
    rc = lib.fylite_rs_q_profile(*grid.args, psi.ravel(), float(psi_axis),
                                 float(psi_bnd), float(axis[0]),
                                 float(axis[1]), lr, lz, lr.size,
                                 fx, fv, fx.size, int(n_q), int(n_theta),
                                 float(x_lo), float(x_hi), out, info)
    if rc < 0:
        raise KernelError(f"fylite_rs_q_profile returned {rc}")
    n = int(info[0])
    return {"x": out[:n].copy(), "q": out[int(n_q):int(n_q) + n].copy(),
            "q0": float(info[1]), "q95": float(info[2])}


# --------------------------------------------------------------------------- #
# the neutral beam (beams.rs)
# --------------------------------------------------------------------------- #
#: The two stopping models, and the two readings of the impurity fits.
BEAM_STOPPING_MODELS = {"janev": 0, "metis": 1}
IMPURITY_FORMS = {"exp": 0, "metis": 1}


def _imp5(n_he=0.0, n_imp=0.0, z_imp=6.0, n_imp2=0.0, z_imp2=18.0):
    return _f([n_he, n_imp, z_imp, n_imp2, z_imp2])


_sig("fylite_rs_lh_accessibility", [_ARR, _ARR, _U64, _F64, _F64, _ARR], _I32)
def lh_accessibility(ne, b_tot, *, n_parallel: float = 2.0,
                     xi: float = 3.0) -> dict:
    """The slow-wave accessibility limit and the Landau-resonant temperature.

    ``n_par_accessible`` is ``ω_pe/ω_ce + √(1+(ω_pe/ω_ce)²)``: a launcher
    below it at a surface cannot deliver power there, which is why high
    density and low field push LH deposition outward.  ``t_resonant`` is
    where that ``n_parallel`` meets the electron tail.
    """
    lib = require()
    ne_a = _f(np.atleast_1d(ne))
    b_a = _f(np.broadcast_to(np.atleast_1d(b_tot), ne_a.shape))
    out = np.empty(2 * ne_a.size)
    rc = lib.fylite_rs_lh_accessibility(ne_a, b_a, ne_a.size,
                                        float(n_parallel), float(xi), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_lh_accessibility returned {rc}")
    rows = out.reshape(-1, 2)
    return {"n_par_accessible": rows[:, 0].copy(),
            "t_resonant": float(rows[0, 1])}


_sig("fylite_rs_lh_resonance", [_ARR, _ARR, _U64, _F64, _F64, _F64, _ARR, ctypes.c_void_p], _I32)
def lh_resonance(psin, te, *, n_parallel: float, xi: float = 3.0,
                 width: float = 0.0) -> dict:
    """Where ``T_e`` crosses the Landau-resonant temperature, and the shape
    deposited there.

    ``{"psin": None}`` when the wave finds no resonant surface — ★a real
    outcome (too cold for that ``n_∥``, so a single-pass model deposits
    nothing), not an error.  With a monotone ``T_e`` the crossing is unique;
    otherwise the OUTERMOST one is taken, because the wave meets it first.
    """
    lib = require()
    p, t = _f(psin), _f(np.broadcast_to(np.asarray(te, float), np.shape(psin)))
    out_p = np.empty(1)
    shape = np.empty(p.size)
    rc = lib.fylite_rs_lh_resonance(p, t, p.size, float(n_parallel),
                                    float(xi), float(width), out_p,
                                    shape.ctypes.data if width > 0 else None)
    if rc < 0:
        raise KernelError(f"fylite_rs_lh_resonance returned {rc}")
    if rc == 0:
        return {"psin": None, "shape": None}
    return {"psin": float(out_p[0]),
            "shape": shape if width > 0 else None}


#: Current-drive efficiency models `lh_efficiency` accepts; the index IS
#: the ABI code, so append, never reorder.
#: The models `lh_efficiency`'s `cd_model` argument indexes into.
LH_EFFICIENCY_MODELS = _LH_EFFICIENCY_MODEL_NAMES


_sig("fylite_rs_lh_efficiency", [_ARR, _ARR, _U64, ctypes.c_uint32, _ARR], _I32)
def lh_efficiency(ne, te, *, model: str = "fisch"):
    """The local current-drive efficiency WEIGHT of a lower-hybrid wave.

    ``"fisch"`` is ``T_e/n_e`` — the scaling behind ``η_CD ∝ T_e/n_e``,
    applied as the shape that redistributes a launcher's total current
    across the resonant layer.

    ★It takes a model NAME rather than being the one weight there is: this
    is the point in the LH chain where a different CD model changes the
    answer, and a kernel admitting only one makes that choice invisible to
    whoever is living with it.
    """
    lib = require()
    try:
        code = LH_EFFICIENCY_MODELS.index(model)
    except ValueError:
        raise KernelError(f"unknown LH efficiency model {model!r}; "
                          f"have {list(LH_EFFICIENCY_MODELS)}") from None
    ne_a = _f(np.atleast_1d(ne))
    te_a = _f(np.broadcast_to(np.atleast_1d(te), ne_a.shape))
    out = np.empty(ne_a.size)
    rc = lib.fylite_rs_lh_efficiency(ne_a, te_a, ne_a.size, code, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_lh_efficiency returned {rc}")
    return out


_sig("fylite_rs_lh_normalize", [_ARR, _ARR, _U64, _ARR], _I32)
def lh_normalize(w, area):
    """``w / Σ(w·area)`` — a weight turned into a current-density profile
    carrying unit total current.

    Returns ``None`` when the weight integrates to nothing: "no current
    here" is a legitimate answer for a wave that never resonated, and only
    the caller can say what to do about it.
    """
    lib = require()
    w_a = _f(np.atleast_1d(w))
    a_a = _f(np.broadcast_to(np.atleast_1d(area), w_a.shape))
    out = np.empty(w_a.size)
    rc = lib.fylite_rs_lh_normalize(w_a, a_a, w_a.size, out)
    if rc == -5:
        return None
    if rc != 0:
        raise KernelError(f"fylite_rs_lh_normalize returned {rc}")
    return out


_sig("fylite_rs_field_ion_sum", [_ARR, _U64] + [_F64] * 4 + [_ARR], _I32)
def field_ion_sum(zeff, *, main_mass: float = 2.0, main_charge: float = 1.0,
                  imp_charge: float = 6.0, imp_mass: float = 12.0):
    """``Σ_j n_j Z_j²/(n_e A_j)`` — the field-ion sum :func:`beam_slowing`
    takes as ``zsum``.

    Quasineutrality and the Z_eff definition fix the two densities.  ★This
    is a closure, not bookkeeping: ``E_c ∝ zsum^(2/3)``, so assembling
    ``zsum`` another way is choosing a different critical energy without
    saying so.
    """
    lib = require()
    z = _f(np.atleast_1d(zeff))
    out = np.empty(z.size)
    rc = lib.fylite_rs_field_ion_sum(z, z.size, float(main_mass),
                                     float(main_charge), float(imp_charge),
                                     float(imp_mass), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_field_ion_sum returned {rc}")
    return out


#: the node count comes BACK through a pointer: a degenerate axis
#: collapses to one node, so n_r*n_z is an upper bound, not the answer
_sig("fylite_rs_beam_footprint", [_U64, _F64, _U64, _F64, _ARR, ctypes.POINTER(_U64)], _I32)
def beam_footprint(n_r: int, half_r: float, n_z: int, half_z: float):
    """The quadrature nodes sampling a beam's finite cross-section.

    Returns ``[(dr, dz, weight), ...]`` over a uniform rectangular footprint.
    ★A quadrature RULE is numerics: which nodes and which weights decides
    how much of a narrow beam's edge is seen at all.  A degenerate axis
    (``n ≤ 1`` or zero half-width) collapses to the centre node.
    """
    lib = require()
    cap = 3 * max(int(n_r), 1) * max(int(n_z), 1)
    out = np.empty(cap)
    got = ctypes.c_uint64(0)
    rc = lib.fylite_rs_beam_footprint(int(n_r), float(half_r), int(n_z),
                                      float(half_z), out,
                                      ctypes.byref(got))
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_footprint returned {rc}")
    rows = out[:3 * int(got.value)].reshape(-1, 3)
    return [(float(a), float(b), float(w)) for a, b, w in rows]


_sig("fylite_rs_fill_gaps", [_ARR, _U64, _I32, _I32, _F64, _ARR], _I32)
def fill_gaps(v, *, monotone: bool = False, default=None):
    """Repair the non-finite entries of a sampled table.

    A contour can fail on one level while its neighbours succeed; the gap is
    filled by linear interpolation IN INDEX and the ends clamp to the
    nearest good value.  ``monotone=True`` then takes the running maximum —
    right for a quantity that cannot decrease outward (a minor radius, an
    enclosed volume), wrong for anything else, hence a flag.

    Every entry non-finite raises unless ``default`` says what to put there.
    """
    lib = require()
    a = _f(np.atleast_1d(v))
    out = np.empty(a.size)
    rc = lib.fylite_rs_fill_gaps(a, a.size, 1 if monotone else 0,
                                 0 if default is None else 1,
                                 0.0 if default is None else float(default),
                                 out)
    if rc == -5:
        raise KernelError("fill_gaps: every entry is non-finite and no "
                          "default was given — there is nothing to "
                          "interpolate from")
    if rc != 0:
        raise KernelError(f"fylite_rs_fill_gaps returned {rc}")
    return out


_sig("fylite_rs_lh_shape", [_ARR, _U64, _F64, _F64, _ARR], _I32)
def lh_shape(psin, centre: float, width: float):
    """A normalised deposition shape on ψ_N (sums to 1).

    The shape is a MODELLING choice — a single-pass damping layer of finite
    width — normalised so the power it distributes is the power the launcher
    absorbed, whatever the grid.
    """
    lib = require()
    p = _f(psin)
    out = np.empty(p.size)
    rc = lib.fylite_rs_lh_shape(p, p.size, float(centre), float(width), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_lh_shape returned {rc}")
    return out


_sig("fylite_rs_first_orbit_loss", ([_ARR] * 3 + [_U64] + [_F64] * 6 + [_I32, _ARR]), _I32)
def first_orbit_loss(rmin, rmaj, q, *, a_edge: float, b0: float, r0: float,
                     mass: float, charge: float, energy: float,
                     counter: bool):
    """The first-orbit-loss mask of a newly born fast ion.

    ★Counter-injection only: a co-injected ion drifts INWARD, so the same
    arithmetic would invent a loss that does not happen.  ``counter=False``
    returns an all-False mask.
    """
    lib = require()
    rm = _f(np.atleast_1d(rmin))
    rj = _f(np.broadcast_to(np.atleast_1d(rmaj), rm.shape))
    q_a = _f(np.broadcast_to(np.atleast_1d(q), rm.shape))
    out = np.empty(rm.size)
    rc = lib.fylite_rs_first_orbit_loss(rm, rj, q_a, rm.size, float(a_edge),
                                        float(b0), float(r0), float(mass),
                                        float(charge), float(energy),
                                        1 if counter else 0, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_first_orbit_loss returned {rc}")
    return out != 0.0


_sig("fylite_rs_beam_stopping", ([_F64] * 2 + [_ARR, _ARR, ctypes.c_void_p, _U64, _I32, _ARR, _I32, _I32, _ARR]), _I32)
def beam_stopping(mass: float, energy: float, ne, te, *, ni=None,
                  model: str = "janev", cross_section: bool = False,
                  impurity_form: str = "exp", **imp):
    """Beam stopping: the cross-section [m²] or the inverse mean free path.

    ``model="janev"`` is the impurity-aware 1989 fit (EAST's carbon and
    tungsten make that term matter); ``"metis"`` is the three-channel sum
    blended with METIS's power law.  ``impurity_form`` selects how the
    impurity polynomials are read — see the kernel's note on the one place
    this port departs from its source.
    """
    lib = require()
    if model not in BEAM_STOPPING_MODELS:
        raise KernelError(f"unknown stopping model {model!r}")
    if impurity_form not in IMPURITY_FORMS:
        raise KernelError(f"unknown impurity form {impurity_form!r}")
    ne_a = _f(np.atleast_1d(ne))
    te_a = _f(np.broadcast_to(np.atleast_1d(te), ne_a.shape))
    ni_a = None if ni is None else _f(np.broadcast_to(np.atleast_1d(ni),
                                                      ne_a.shape))
    out = np.empty(ne_a.size)
    rc = lib.fylite_rs_beam_stopping(
        float(mass), float(energy), ne_a, te_a,
        None if ni_a is None else ni_a.ctypes.data, ne_a.size,
        BEAM_STOPPING_MODELS[model], _imp5(**imp),
        IMPURITY_FORMS[impurity_form], 0 if cross_section else 1, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_stopping returned {rc}")
    return out


_sig("fylite_rs_beam_slowing", ([_ARR] * 4 + [_U64, _F64, _F64, _ARR]), _I32)
def beam_slowing(te, ne, *, mass: float = 2.0, zeff=1.0, zsum,
                 e_beam: float) -> dict:
    """Stix slowing-down parameters, plus the ion power fraction and τ_eff.

    ``zsum`` is ``Σ_j n_j Z_j²/(n_e A_j)`` — the field-ion sum that sets the
    critical energy.
    """
    lib = require()
    te_a = _f(np.atleast_1d(te))
    ne_a = _f(np.broadcast_to(np.atleast_1d(ne), te_a.shape))
    z_a = _f(np.broadcast_to(np.atleast_1d(zeff), te_a.shape))
    zs_a = _f(np.broadcast_to(np.atleast_1d(zsum), te_a.shape))
    out = np.empty(6 * te_a.size)
    rc = lib.fylite_rs_beam_slowing(te_a, ne_a, z_a, zs_a, te_a.size,
                                    float(mass), float(e_beam), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_slowing returned {rc}")
    rows = out.reshape(-1, 6)
    keys = ("e_crit", "e_gamma", "tau_s", "ln_lambda", "ion_fraction",
            "tau_eff")
    return {k: rows[:, i].copy() for i, k in enumerate(keys)}


_sig("fylite_rs_beam_energy_partition", [_ARR, _ARR, _ARR, _U64, _ARR], _I32)
def beam_energy_partition(e_crit, tau_s, *, e_beam) -> dict:
    """The ion power fraction and ``τ_eff`` from a critical energy and a
    slowing time.

    ★Separate from :func:`beam_slowing` because a caller often has these two
    in hand — from a measurement, a scan or another model — and making it
    invent a plasma state that reproduces them would be an inversion nobody
    asked for.
    """
    lib = require()
    ec, ts, eb = (_f(a) for a in np.broadcast_arrays(
        np.atleast_1d(np.asarray(e_crit, float)),
        np.atleast_1d(np.asarray(tau_s, float)),
        np.atleast_1d(np.asarray(e_beam, float))))
    out = np.empty(2 * ec.size)
    rc = lib.fylite_rs_beam_energy_partition(ec, ts, eb, ec.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_energy_partition returned {rc}")
    rows = out.reshape(-1, 2)
    return {"ion_fraction": rows[:, 0].copy(), "tau_eff": rows[:, 1].copy()}


_sig("fylite_rs_beam_shielding", [_ARR, _ARR, _U64, _ARR], _I32)
def beam_shielding(ft, zeff) -> dict:
    """The back-EMF shielding function ``G`` and the surviving current
    fraction ``1 − (1−G)/Z_eff``."""
    lib = require()
    ft_a = _f(np.atleast_1d(ft))
    z_a = _f(np.broadcast_to(np.atleast_1d(zeff), ft_a.shape))
    out = np.empty(2 * ft_a.size)
    rc = lib.fylite_rs_beam_shielding(ft_a, z_a, ft_a.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_shielding returned {rc}")
    rows = out.reshape(-1, 2)
    return {"g": rows[:, 0].copy(), "factor": rows[:, 1].copy()}


_sig("fylite_rs_beam_current_integral", [_ARR, _ARR, _ARR, _U64, _U64, _ARR], _I32)
def beam_current_integral(v0, vc, vg, *, n_step: int = 101) -> dict:
    """The Start-Cordey beam-current velocity integral and its exponent."""
    lib = require()
    v0_a = _f(np.atleast_1d(v0))
    vc_a = _f(np.broadcast_to(np.atleast_1d(vc), v0_a.shape))
    vg_a = _f(np.broadcast_to(np.atleast_1d(vg), v0_a.shape))
    out = np.empty(2 * v0_a.size)
    rc = lib.fylite_rs_beam_current_integral(v0_a, vc_a, vg_a, v0_a.size,
                                             int(n_step), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_current_integral returned {rc}")
    rows = out.reshape(-1, 2)
    return {"integral": rows[:, 0].copy(), "ev": rows[:, 1].copy()}


_sig("fylite_rs_beam_current", ([_ARR] * 8 + [_U64] + [_F64] * 3 + [_U64, _ARR]), _I32)
def beam_current(p_dep, pitch, *, e_crit, e_gamma, tau_s, rmin, rmaj,
                 shield, energy: float, mass: float,
                 multiplier: float = 1.0, n_step: int = 101):
    """The beam-driven current density [A/m²] of one energy component.

    ★``shield`` (the bulk's electron return current) and the beam ions' own
    trapping are DIFFERENT suppressions, and this applies both — so a caller
    cannot apply one and believe it applied the other.  The trapping step is
    smoothed in pitch because a hard threshold makes ``j_NBI`` jump between
    adjacent shells, which reads as structure no experiment has.
    """
    lib = require()
    args = [_f(a) for a in (p_dep, pitch, e_crit, e_gamma, tau_s, rmin, rmaj,
                            shield)]
    n = args[0].size
    if any(a.size != n for a in args):
        raise KernelError("every per-shell array must be the same length")
    out = np.empty(n)
    rc = lib.fylite_rs_beam_current(*args, n, float(energy), float(mass),
                                    float(multiplier), int(n_step), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_current returned {rc}")
    return out


_sig("fylite_rs_beam_deposit_ray", ([_ARR, _ARR, _U64, _F64, _ARR, _ARR, _ARR, _U64] + [_F64] * 2 + [_I32, _ARR, _I32] + [_ARR] * 3), _I32)
def beam_deposit_ray(psin, pitch, ds: float, *, ne_s, te_s, psin_edges,
                     mass: float, energy: float, model: str = "janev",
                     impurity_form: str = "exp", **imp) -> dict:
    """Attenuate one energy component along one ray, binned into ψ_N shells.

    ``ne_s``/``te_s`` are the profiles AT THE RAY'S OWN SAMPLES — ★not a
    table: the caller has already evaluated its profile to get them, and
    re-sampling would add an interpolation error (about 1 % on a 24-point
    ladder) to a quantity that was exact.

    Returns the absorbed fraction and the absorption-weighted pitch SUM per
    shell, plus the shine-through — ★``absorbed.sum() + shinethrough`` is 1
    to round-off, which is the only cheap check this model has.
    """
    lib = require()
    p, pt = _f(psin), _f(pitch)
    ne_a, te_a, ed = _f(ne_s), _f(te_s), _f(psin_edges)
    n_shell = ed.size - 1
    absorbed, pw, shine = np.empty(n_shell), np.empty(n_shell), np.empty(1)
    rc = lib.fylite_rs_beam_deposit_ray(
        p, pt, p.size, float(ds), ne_a, te_a,
        ed, n_shell, float(mass), float(energy),
        BEAM_STOPPING_MODELS[model], _imp5(**imp),
        IMPURITY_FORMS[impurity_form], absorbed, pw, shine)
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_deposit_ray returned {rc}")
    return {"absorbed": absorbed, "pitch_weighted": pw,
            "shinethrough": float(shine[0])}


# --------------------------------------------------------------------------- #
# the SVD, and the basis a chord tomography inverts on
# --------------------------------------------------------------------------- #
_sig("fylite_rs_pchip", [_ARR, _ARR, _U64, _ARR, _U64, _ARR], _I32)
def pchip(x, y, xq):
    """Monotone cubic (PCHIP) interpolation — Fritsch-Carlson.

    ★The kernel's, because the alternative in this repository was "pchip
    when scipy is installed, LINEAR when not", and a linear interpolant has
    a staircase derivative — which is the one property a profile fitter
    exists to provide.  Outside the range the end cubics extrapolate.
    """
    lib = require()
    x_a, y_a, q = _f(x), _f(y), _f(np.atleast_1d(xq))
    out = np.empty(q.size)
    rc = lib.fylite_rs_pchip(x_a, y_a, x_a.size, q, q.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_pchip returned {rc}"
                          + (" — x must be strictly increasing" if rc == -5
                             else ""))
    return out.reshape(np.shape(xq)) if np.shape(xq) else out


_sig("fylite_rs_svd", [_ARR, _U64, _U64, _ARR, _ARR, _ARR], _I32)
def svd(a) -> tuple:
    """Thin SVD of a real matrix: ``(u, s, vt)``.

    Same shapes as ``numpy.linalg.svd(..., full_matrices=False)``; singular
    values descending.  ★A WIDE matrix is transposed here rather than in
    each caller — the kernel entry takes ``m ≥ n`` because one-sided Jacobi
    works on columns, and `A = U S V^T` transposes to `A^T = V S U^T`, so
    the swap is exact rather than a second factorisation.
    """
    lib = require()
    a_a = _f(np.atleast_2d(a))
    m, n = a_a.shape
    if m < n:
        u_t, s_, vt_t = svd(a_a.T)
        return vt_t.T, s_, u_t.T
    u, s_, vt = np.empty(m * n), np.empty(n), np.empty(n * n)
    rc = lib.fylite_rs_svd(a_a.ravel(), m, n, u, s_, vt)
    if rc != 0:
        raise KernelError(f"fylite_rs_svd returned {rc}")
    return u.reshape(m, n), s_, vt.reshape(n, n)


_sig("fylite_rs_svd_solve", [_ARR, _ARR, _U64, _U64, _F64, ctypes.c_int64, _ARR, ctypes.c_void_p, _ARR], _I32)
def svd_solve(a, b, *, rcond: float = 1e-3, n_singular=None) -> dict:
    """Least squares by TRUNCATED SVD.

    ★The truncation is the regularisation, and how much was kept comes back
    with the answer: an under-determined view geometry has to be visible, or
    a solve that inverted a singular value of 1e-14 returns a beautiful
    reconstruction of the noise.
    """
    lib = require()
    a_a, b_a = _f(np.atleast_2d(a)), _f(b)
    m, n = a_a.shape
    if b_a.size != m:
        raise KernelError(f"A has {m} rows for {b_a.size} values")
    x, sv, info = np.empty(n), np.empty(n), np.empty(2)
    rc = lib.fylite_rs_svd_solve(a_a.ravel(), b_a, m, n, float(rcond),
                                 -1 if n_singular is None else int(n_singular),
                                 x, sv.ctypes.data, info)
    if rc != 0:
        raise KernelError(f"fylite_rs_svd_solve returned {rc}")
    return {"x": x, "n_singular": int(info[0]), "condition": float(info[1]),
            "singular_values": sv}


_sig("fylite_rs_besselj", [_U64, _ARR, _U64, _ARR], _I32)
def besselj(m: int, x):
    """``J_m(x)`` for integer ``m ≥ 0`` — the kernel's, so a tomography basis
    is the same basis in every host."""
    lib = require()
    x_a = _f(np.atleast_1d(x))
    out = np.empty(x_a.size)
    rc = lib.fylite_rs_besselj(int(m), x_a, x_a.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_besselj returned {rc}")
    return out.reshape(np.shape(x)) if np.shape(x) else out


_sig("fylite_rs_bessel_zeros", [_U64, _U64, _ARR], _I32)
def bessel_zeros(m: int, n: int):
    """The first ``n`` positive zeros of ``J_m``.

    They are what makes the tomography basis vanish at the boundary: mode
    ``l`` is ``J_m(z_{m,l} ψ_N)``, so an emissivity expanded on it is zero
    at ψ_N = 1 by construction rather than by fitting.
    """
    lib = require()
    out = np.empty(int(n))
    rc = lib.fylite_rs_bessel_zeros(int(m), int(n), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_bessel_zeros returned {rc}")
    return out


_sig("fylite_rs_tomography_basis", [_ARR, _ARR, _U64, _U64, _U64, _ARR], _I32)
def tomography_basis(psin, theta, *, m_max: int = 1, l_max: int = 4):
    """The Fourier-Bessel basis on ``(ψ_N, θ)``: ``(n_points, n_basis)``.

    Column order: ``(m=0, l=1..L)``, then for each ``m ≥ 1`` the cosine
    block followed by the sine block.  ★The truncation is the regulariser —
    a low-order expansion cannot fit noise it has no freedom for.
    """
    lib = require()
    p = _f(np.atleast_1d(psin))
    t = _f(np.broadcast_to(np.atleast_1d(theta), p.shape))
    nb = int(l_max) + 2 * int(m_max) * int(l_max)
    out = np.empty(p.size * nb)
    rc = lib.fylite_rs_tomography_basis(p, t, p.size, int(m_max), int(l_max),
                                        out)
    if rc < 0:
        raise KernelError(f"fylite_rs_tomography_basis returned {rc}")
    return out.reshape(p.size, rc)


# --------------------------------------------------------------------------- #
# chords and the magnetics moment fit (diagnostics.rs)
# --------------------------------------------------------------------------- #
#: The quadrature rules a chord integral may use.
QUADRATURE_RULES = {"simpson": 0, "trapezoid": 1, "midpoint": 2}


_sig("fylite_rs_chord_samples", [_ARR, _ARR, _F64, _U64, _ARR, _ARR, _ARR], _I32)
def chord_samples(origin, direction, length: float, n: int = 601) -> dict:
    """Sample a straight 3-D sight line; returns cylindrical ``(r, z)`` + ``ds``.

    ``direction`` is normalised internally, so ``ds`` is a true path step and
    an integral built on it is per metre of sight line.
    """
    lib = require()
    o3, d3 = _f(np.reshape(origin, 3)), _f(np.reshape(direction, 3))
    r, z, ds = np.empty(n), np.empty(n), np.empty(1)
    rc = lib.fylite_rs_chord_samples(o3, d3, float(length), int(n), r, z, ds)
    if rc != 0:
        raise KernelError(f"fylite_rs_chord_samples returned {rc}")
    return {"r": r, "z": z, "ds": float(ds[0])}


_sig("fylite_rs_psin_along", ([_F64] * 4 + [_U64] * 2 + [_ARR, _ARR, _ARR, _U64, _ARR]), _I32)
def psin_along(grid: Grid, psin2d, r, z):
    """ψ_N at scattered points, ``+inf`` outside the grid.

    ★``+inf`` rather than NaN or a clamp: an off-grid sample is then vacuum
    without a special case, and ``psin <= 1`` selects the confined region
    directly.
    """
    lib = require()
    psin2d = _f(psin2d)
    if psin2d.shape != (grid.nr, grid.nz):
        raise KernelError(f"psin2d has shape {psin2d.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    r_a = _f(np.atleast_1d(r))
    z_a = _f(np.broadcast_to(np.atleast_1d(z), r_a.shape))
    out = np.empty(r_a.size)
    rc = lib.fylite_rs_psin_along(*grid.args, psin2d.ravel(), r_a, z_a,
                                  r_a.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_psin_along returned {rc}")
    return out


_sig("fylite_rs_quadrature", [_ARR, _U64, _F64, _I32, _ARR], _I32)
def quadrature(values, ds: float, *, rule: str = "simpson") -> float:
    """``∫ f ds`` over uniform samples — Simpson, trapezoid or midpoint.

    Simpson falls back to the trapezoid on a final odd interval rather than
    dropping it, which would quietly shorten the chord.
    """
    lib = require()
    if rule not in QUADRATURE_RULES:
        raise KernelError(f"unknown quadrature rule {rule!r}; have "
                          f"{sorted(QUADRATURE_RULES)}")
    v = _f(values)
    out = np.empty(1)
    rc = lib.fylite_rs_quadrature(v, v.size, float(ds),
                                  QUADRATURE_RULES[rule], out)
    if rc != 0:
        raise KernelError(f"fylite_rs_quadrature returned {rc}")
    return float(out[0])


_sig("fylite_rs_chord_mask", [_ARR, _ARR, _ARR, _U64, _F64, _ARR, _ARR, _U64, _ARR], _I32)
def chord_mask(psin, r, z, *, psin_max: float = 1.0, boundary=None):
    """Which samples of a chord count as plasma — a boolean array.

    On the grid (``ψ_N`` finite), within ``psin_max``, and inside the
    boundary polygon when one is given.

    ★★``ψ_N ≤ 1`` is not a containment test: ψ over the full grid box is not
    monotonic outside the plasma — the field coils put structure there — so
    a chord far above the plasma still finds samples below 1.  Without a
    ``boundary`` this filters on ψ_N alone, which is a CAVEAT the caller
    accepts, not a default that is fine.
    """
    lib = require()
    p, r_a, z_a = _f(psin), _f(r), _f(z)
    if boundary is None:
        br = bz = np.zeros(0)
    else:
        br, bz = _f(boundary[0]), _f(boundary[1])
    out = np.empty(p.size)
    rc = lib.fylite_rs_chord_mask(p, r_a, z_a, p.size,
                                  float("inf") if psin_max is None
                                  else float(psin_max),
                                  br, bz, br.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_chord_mask returned {rc}")
    return out != 0.0


_sig("fylite_rs_line_integral", ([_ARR] * 3 + [_U64, _F64, _ARR, _U64, _F64, _ARR, _ARR, _U64, _F64, _I32, _ARR, _ARR]), _I32)
def line_integral(psin, r, z, ds: float, *, f_val, f_max_psin: float = 1.0,
                  boundary=None, psin_max: float = 1.0,
                  rule: str = "simpson") -> dict:
    """``∫ f(ψ_N) ds`` along a sampled chord, with ``f`` as a PROFILE.

    ``f_val`` is sampled uniformly on ψ_N ∈ [0, ``f_max_psin``].  Without a
    ``boundary`` the integral is filtered on ψ_N alone — ★which is a caveat,
    not a default: ψ_N ≤ 1 is not a containment test.
    """
    lib = require()
    if rule not in QUADRATURE_RULES:
        raise KernelError(f"unknown quadrature rule {rule!r}")
    p, r_a, z_a, fv = _f(psin), _f(r), _f(z), _f(f_val)
    if boundary is None:
        br = bz = np.zeros(0)
    else:
        br, bz = _f(boundary[0]), _f(boundary[1])
    out, info = np.empty(1), np.empty(3)
    rc = lib.fylite_rs_line_integral(
        p, r_a, z_a, p.size, float(ds), fv, fv.size, float(f_max_psin),
        br, bz, br.size,
        float("inf") if psin_max is None else float(psin_max),
        QUADRATURE_RULES[rule], out, info)
    if rc != 0:
        raise KernelError(f"fylite_rs_line_integral returned {rc}")
    return {"value": float(out[0]), "path_length": float(info[0]),
            "n_inside": int(info[1]), "psin_min": float(info[2])}



_sig("fylite_rs_chord_reduce", ([_ARR] * 4 + [_U64, _F64, _ARR, _ARR, _U64, _F64, _I32, _ARR, _ARR]), _I32)
def chord_reduce(values, psin, r, z, ds: float, *, boundary=None,
                 psin_max: float = 1.0, rule: str = "simpson") -> dict:
    """``∫ f ds`` along a chord whose ``f`` the CALLER evaluated.

    The twin of :func:`line_integral` for a host whose ``f`` is a callback
    and therefore cannot cross the ABI.  Everything else — which samples
    count, the quadrature, and the three numbers that say whether the
    answer can be trusted — is decided kernel-side, so the two entries
    cannot disagree about where the plasma was.

    ★``values`` is read only where the mask says plasma; what a caller left
    outside does not reach the integral.
    """
    lib = require()
    if rule not in QUADRATURE_RULES:
        raise KernelError(f"unknown quadrature rule {rule!r}; have "
                          f"{sorted(QUADRATURE_RULES)}")
    v, p = _f(values), _f(psin)
    r_a, z_a = _f(r), _f(z)
    if not (v.size == p.size == r_a.size == z_a.size):
        raise KernelError(
            f"values {v.size}, psin {p.size}, r {r_a.size}, z {z_a.size} "
            "must all be the same length")
    if boundary is None:
        br = bz = np.zeros(0)
    else:
        br, bz = _f(boundary[0]), _f(boundary[1])
    out, info = np.empty(1), np.empty(3)
    rc = lib.fylite_rs_chord_reduce(
        v, p, r_a, z_a, p.size, float(ds), br, bz, br.size,
        float("inf") if psin_max is None else float(psin_max),
        QUADRATURE_RULES[rule], out, info)
    if rc != 0:
        raise KernelError(f"fylite_rs_chord_reduce returned {rc}")
    return {"value": float(out[0]), "path_length": float(info[0]),
            "n_inside": int(info[1]), "psin_min": float(info[2])}


_sig("fylite_rs_pinhole_angles", [_F64, _F64, _F64, _U64, _ARR], _I32)
def pinhole_angles(view_angle: float, *, focal_length: float, pitch: float,
                   n_channels: int):
    """A pinhole camera's fan of sight-line angles [rad], detector order.

    ``θᵢ = atan((n/2 − i + 0.5)·pitch/focal_length) + view_angle + π``.

    ★The ``+π`` is the whole content of the formula and it is not a
    convention to leave to the caller: it turns "where the detector sits
    behind the aperture" into "where the ray goes into the machine".  Drop
    it and every chord integral comes back zero — which reads as a camera
    that sees no plasma, not as a sign error.
    """
    lib = require()
    n = int(n_channels)
    out = np.empty(max(n, 1))
    rc = lib.fylite_rs_pinhole_angles(float(view_angle),
                                      float(focal_length), float(pitch), n,
                                      out)
    if rc != 0:
        raise KernelError(f"fylite_rs_pinhole_angles returned {rc}")
    return out[:n]

_sig("fylite_rs_current_centroid", ([_ARR] * 5 + [_U64] + [_F64] * 3 + [_ARR]), _I32)
def current_centroid(probe_r, probe_z, angle_rad, b_plasma, weight, *,
                     ip: float, guess) -> dict:
    """Fit one current filament to the plasma-only probe field.

    ★The anchor a magnetics-only reconstruction cannot find for itself: the
    loops leave the vertical position nearly free (measured, ~45 mm off in Z
    while the axis R is already good to 0.6 mm), and reading it from an EFIT
    a-file would make the answer depend on the code being replaced.
    """
    lib = require()
    args = [_f(a) for a in (probe_r, probe_z, angle_rad, b_plasma, weight)]
    n = args[0].size
    out = np.empty(3)
    rc = lib.fylite_rs_current_centroid(*args, n, float(ip),
                                        float(guess[0]), float(guess[1]), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_current_centroid returned {rc}")
    return {"r": float(out[0]), "z": float(out[1]), "residual": float(out[2])}


# --------------------------------------------------------------------------- #
# the electromagnetic tier (electromagnetics.rs / evolution.rs / stability.rs)
# --------------------------------------------------------------------------- #
_sig("fylite_rs_ideal_stiffness", [_ARR, _ARR, _U64, _F64, _ARR], _I32)
def ideal_stiffness(inductance, coupling_gradient, *, ip: float) -> float:
    """The ideal-wall vertical stiffness ``Ip² Gᵀ M⁻¹ G`` [N/m].

    ★The REGIME BOUNDARY: below it the mode is resistive-wall and
    :func:`vertical_plant` applies; at or above it the plant is
    ideal-unstable and that function refuses.  Askable on its own so a
    caller does not have to trigger the refusal to find out where it is.
    """
    lib = require()
    g = _f(coupling_gradient)
    n = g.size
    m = _f(np.reshape(inductance, (n, n)))
    out = np.empty(1)
    rc = lib.fylite_rs_ideal_stiffness(g, m.ravel(), n, float(ip), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_ideal_stiffness returned {rc}")
    return float(out[0])


_sig("fylite_rs_dispersion_root", [_ARR, _ARR, _ARR, _U64, _F64, _F64, _F64, _F64, _ARR], _I32)
def dispersion_root(coupling_gradient, inductance, resistance, *, ip: float,
                    stiffness: float, mass: float = 0.0,
                    gamma_max: float = 1.0e6):
    """The vertical growth rate: the root of
    ``k = γ Ip² Gᵀ (γM + R)⁻¹ G`` (+ ``m γ²`` when a mass is given).

    Returns ``None`` when there is no root below ``gamma_max`` — the
    ideal-unstable branch.  ★That is a REGIME, not a failure, so it comes
    back as a value the caller classifies rather than as an exception or as
    a very large number that looks like an answer.
    """
    lib = require()
    g = _f(coupling_gradient)
    n = g.size
    m = _f(np.reshape(inductance, (n, n)))
    r = _f(np.atleast_1d(resistance))
    out = np.empty(1)
    rc = lib.fylite_rs_dispersion_root(g, m.ravel(), r, n, float(ip),
                                       float(stiffness), float(mass),
                                       float(gamma_max), out)
    if rc == 1:
        return None
    if rc != 0:
        raise KernelError(f"fylite_rs_dispersion_root returned {rc}")
    return float(out[0])


_sig("fylite_rs_vertical_plant", ([_ARR] * 3 + [_U64, _F64, _F64] + [_ARR] * 4), _I32)
def vertical_plant(inductance, resistance, coupling_gradient, *, ip: float,
                   stiffness: float) -> dict:
    """The linearised vertical plant: the rank-one plasma elimination.

    The plasma is massless on this timescale, so ``k ξ + Ip Gᵀ δI = 0`` is
    algebraic and folds into ``M* = M − (Ip²/k) G Gᵀ`` with
    ``ξ = −(Ip/k) Gᵀ δI``.  Returns ``M*``, ``C_xi``, the open-loop growth
    rate (largest eigenvalue of ``−M*⁻¹R``), the ideal stiffness, and the
    unstable ``mode`` normalised so ``C_xi · mode = 1``.

    ★The growth rate here MUST agree with
    :func:`fylite.scenario.control.stability.vertical_growth_rate`'s dispersion root: the two
    are related by Sherman-Morrison, so agreement checks the wiring rather
    than restating one formula.
    """
    lib = require()
    r_a, g_a = _f(resistance), _f(coupling_gradient)
    n = r_a.size
    m = _f(np.reshape(inductance, (n, n)))
    ms, cx, md = (np.empty(n * n), np.empty(n), np.empty(n))
    info = np.empty(2)
    rc = lib.fylite_rs_vertical_plant(m.ravel(), r_a, g_a, n, float(ip),
                                      float(stiffness), ms, cx, md, info)
    if rc != 0:
        raise KernelError(
            "fylite_rs_vertical_plant: the massless elimination does not "
            "apply — either the solve failed or k >= k_ideal, which is the "
            "IDEAL-unstable regime where this formulation would report a "
            "comfortable negative growth rate for the worst case there is; "
            "read stability.vertical_growth_rate's verdict instead"
            if rc == -6 else f"fylite_rs_vertical_plant returned {rc}")
    return {"m_star": ms.reshape(n, n), "c_xi": cx, "mode": md,
            "gamma_openloop": float(info[0]), "k_ideal": float(info[1])}


_sig("fylite_rs_vertical_loop", ( [_ARR] * 4 + [_U64] + [_F64] * 5 + [_ARR, _ARR, _U64, _I32] + [ctypes.c_void_p] * 2 + [_U64, ctypes.c_void_p] + [_F64] * 2 + [_ARR] * 4), _I32)
def vertical_loop(plant: dict, resistance, *, t_end: float, dt: float,
                  kp: float, kd: float, xi0: float, direction, b_act,
                  loops_c=None, loops_p=None, noise=None,
                  v_max: float | None = None,
                  actuator_tau: float | None = None) -> dict:
    """One closed-loop run: implicit-Euler plant, PD with a one-step delay.

    ★The measurement delay is not an implementation detail — a PD law on a
    resistive vertical mode stabilises only if it acts faster than the mode
    grows, and a controller reading the current step would hide the failure
    a real digital loop has.

    ``loops_c``/``loops_p`` switch on the flux-loop observer; ``noise`` is
    the measurement noise the CALLER draws (a random number generator is
    not physics, and passing the draws in keeps a run reproducible from
    either host).  ``kp = kd = 0`` is the broken-loop control run.
    """
    lib = require()
    ms = _f(plant["m_star"])
    cx, md, r_a = _f(plant["c_xi"]), _f(plant["mode"]), _f(resistance)
    n = cx.size
    dirv = _f(np.atleast_1d(direction))
    n_act = dirv.size
    ba = _f(np.reshape(b_act, (n, n_act)))
    observer = loops_c is not None and loops_p is not None
    if observer:
        lc, lp = _f(loops_c), _f(loops_p)
        n_loops = lp.size
    else:
        lc = lp = None
        n_loops = 0
    nstep = int(round(t_end / dt))
    ns = None if noise is None or not observer else _f(
        np.reshape(noise, (nstep + 1, n_loops)))
    t, xi, u = (np.empty(nstep + 1) for _ in range(3))
    state = np.empty(n)
    rc = lib.fylite_rs_vertical_loop(
        ms.ravel(), r_a, cx, md, n, float(t_end), float(dt), float(kp),
        float(kd), float(xi0), dirv, ba.ravel(), n_act,
        1 if observer else 0,
        None if lc is None else lc.ctypes.data,
        None if lp is None else lp.ctypes.data, n_loops,
        None if ns is None else ns.ctypes.data,
        float("nan") if v_max is None else float(v_max),
        float("nan") if actuator_tau is None else float(actuator_tau),
        t, xi, u, state)
    if rc < 0:
        raise KernelError(f"fylite_rs_vertical_loop returned {rc}")
    return {"t": t, "xi": xi, "u": u, "state_final": state}


_sig("fylite_rs_inside_polygon", [_ARR, _ARR, _U64, _ARR, _ARR, _U64, _ARR], _I32)
def inside_polygon(r, z, poly_r, poly_z):
    """Even-odd point-in-polygon — the same rule the plasma mask uses.

    Here so that "is this cell in the plasma" has ONE answer, boundary
    cases included.  Returns a boolean array shaped like ``r``.
    """
    lib = require()
    r_a, z_a = np.atleast_1d(np.asarray(r, float)), np.atleast_1d(np.asarray(z, float))
    shape = r_a.shape
    r_f, z_f = _f(r_a.ravel()), _f(z_a.ravel())
    pr, pz = _f(poly_r), _f(poly_z)
    out = np.empty(r_f.size)
    rc = lib.fylite_rs_inside_polygon(r_f, z_f, r_f.size, pr, pz, pr.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_inside_polygon returned {rc}")
    return out.reshape(shape) != 0.0


_sig("fylite_rs_f_from_coefficients", [_ARR, _U64, _ARR, _U64, _F64, _F64, _ARR], _I32)
def f_from_coefficients(cff, x, *, span_pr: float, f_edge: float):
    """``F(x)`` from fitted ``FF'`` coefficients, integrated analytically.

    ★Not the same entry as the sampled ``f_profile``: that one trapezoids a
    sampled ``FF'`` (what a g-file carries); this is the closed form of the
    inverse solve's edge-zeroed basis (what a fit produces).  Putting a
    fit's coefficients through a quadrature adds a discretisation error to
    a quantity that has none.
    """
    lib = require()
    c, x_a = _f(np.atleast_1d(cff)), _f(np.atleast_1d(x))
    out = np.empty(x_a.size)
    rc = lib.fylite_rs_f_from_coefficients(c, c.size, x_a, x_a.size,
                                           float(span_pr), float(f_edge), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_f_from_coefficients returned {rc}")
    return out.reshape(np.shape(x)) if np.shape(x) else float(out[0])


_sig("fylite_rs_probe_response", [_ARR, _U64, _ARR, _U64, _ARR, _ARR, _ARR, _U64, _ARR], _I32)
def probe_response(grid_r, grid_z, probe_r, probe_z, angle_rad):
    """Magnetic-probe Green's rows: ``(n_probe, nr, nz)`` in T per amp.

    Row ``p`` is ``B_R cos(a_p) + B_Z sin(a_p)`` from a unit toroidal
    current in each cell — the probe analogue of the flux-loop rows, so a
    reconstruction can take probes as CONSTRAINTS rather than only
    predicting them afterwards.

    ★The projection onto the probe's own angle is the whole difference from
    a loop row, and a wrong angle convention does not raise: the fit
    converges on a plasma tilted to match.

    ★★**These rows are PLASMA-ONLY, and a raw probe reading is not.**  A
    measured probe sees the plasma and the coils together, while a deck's
    loop readings usually arrive with the coil term already subtracted.
    Handing the full field to a plasma-only row asks the plasma current to
    reproduce the coil field as well, and the fit obliges — measured on
    EAST: li(3) 2.665 → 3.42, q0 0.495 → 0.345, with a converged solve and
    a smooth ψ map.  Subtract the coils' field at the probe first.
    """
    lib = require()
    gr, gz = _f(grid_r), _f(grid_z)
    pr, pz = _f(np.atleast_1d(probe_r)), _f(np.atleast_1d(probe_z))
    ang = _f(np.broadcast_to(np.atleast_1d(angle_rad), pr.shape))
    out = np.empty(pr.size * gr.size * gz.size)
    rc = lib.fylite_rs_probe_response(gr, gr.size, gz, gz.size, pr, pz, ang,
                                      pr.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_probe_response returned {rc}")
    return out.reshape(pr.size, gr.size, gz.size)


_sig("fylite_rs_step_circuits", ([_ARR] * 4 + [_U64, _F64, ctypes.c_void_p, _ARR]), _I32)
def step_circuits(inductance, resistance, currents_prev, voltages, dt,
                  dpsi_plasma=None):
    """One implicit-Euler circuit step.

    ``(M/dt + diag(R)) I⁺ = M/dt I + V − dψ_plasma/dt``.  Cholesky with one
    step of iterative refinement — the vessel-coupled system is conditioned
    around 1e8 and a plain solve sits outside the design's band.
    """
    lib = require()
    m = _f(inductance)
    r, i0, v = _f(resistance), _f(currents_prev), _f(voltages)
    n = i0.size
    if m.shape != (n, n):
        raise KernelError(f"inductance must be ({n},{n}), got {m.shape}")
    dp = None if dpsi_plasma is None else _f(
        np.broadcast_to(np.asarray(dpsi_plasma, float), (n,)))
    out = np.empty(n)
    rc = lib.fylite_rs_step_circuits(m.ravel(), r, i0, v, n, float(dt),
                                     None if dp is None else dp.ctypes.data,
                                     out)
    if rc != 0:
        raise KernelError(f"fylite_rs_step_circuits returned {rc}")
    return out


_sig("fylite_rs_resistances", ([_ARR] * 3 + [ctypes.c_void_p, _U64, _ARR]), _I32)
def resistances(r, area, eta, turns=None):
    """Element resistances [Ω]: ``η 2πr/area``, ×N² when wound.

    ``eta`` in Ω·m (a device deck quotes μΩ·m — convert where the deck is
    read).  With ``turns`` the resistance is referred to AMPERE-TURNS, the
    state variable this package uses throughout.
    """
    lib = require()
    r_a, a_a = _f(r), _f(area)
    e_a = _f(np.broadcast_to(np.asarray(eta, float), r_a.shape))
    t_a = None if turns is None else _f(
        np.broadcast_to(np.asarray(turns, float), r_a.shape))
    out = np.empty(r_a.size)
    rc = lib.fylite_rs_resistances(r_a, a_a, e_a,
                                   None if t_a is None else t_a.ctypes.data,
                                   r_a.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_resistances returned {rc}")
    return out


# --------------------------------------------------------------------------- #
# Conductor electromagnetics (the L1 group).
#
# ★These entries existed before this module did, and their callers reached
# past it — the old `circuits.py`, `stability.py` and `breakdown.py` each held their
# own ctypes call plus a numpy twin behind an "if the library is here"
# branch.  That arrangement predates D-4′: it was written when the Rust core
# was optional, and the twins are exactly the second implementations the
# rule forbids.  The twins now live in `tests/oracles/em.py`, where
# they are what they always really were — an independent reference the
# gates measure this face against.
# --------------------------------------------------------------------------- #
_sig("fylite_rs_ellipke", [_ARR, _U64, _ARR, _ARR], _I32)
def ellipke(m):
    """Complete elliptic integrals ``K(m)``, ``E(m)`` by the AGM."""
    lib = require()
    m_a = _f(np.atleast_1d(m))
    #: ★a ValueError, not a KernelError: the kernel did not refuse — the
    #: ARGUMENT is out of the function's domain, which is the caller's
    #: mistake and the exception type its callers already catch.
    if np.any((m_a < 0) | (m_a >= 1.0)):
        raise ValueError("ellipke: m must be in [0, 1)")
    k, e = np.empty(m_a.size), np.empty(m_a.size)
    rc = lib.fylite_rs_ellipke(m_a, m_a.size, k, e)
    if rc != 0:
        raise KernelError(f"fylite_rs_ellipke returned {rc}")
    #: reshape to the CALLER's shape, `()` included: a scalar in gives a
    #: 0-d array out, which `float(...)` accepts where a 1-element 1-d array
    #: no longer does (numpy 2).
    shape = np.shape(m)
    return k.reshape(shape), e.reshape(shape)


_sig("fylite_rs_mutual_filaments", [_ARR, _ARR, _ARR, _ARR, _U64, _ARR], _I32)
def mutual_filaments(r1, z1, r2, z2):
    """Mutual inductance [H] between coaxial circular filaments, elementwise.

    The four inputs broadcast against each other, as the numpy this replaces
    did; the kernel sees the broadcast result.
    """
    lib = require()
    a, b, c, d = np.broadcast_arrays(*(np.asarray(x, float)
                                       for x in (r1, z1, r2, z2)))
    flat = [_f(x.ravel()) for x in (a, b, c, d)]
    out = np.empty(a.size)
    rc = lib.fylite_rs_mutual_filaments(*flat, a.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_mutual_filaments returned {rc}")
    return out.reshape(a.shape)


_sig("fylite_rs_mutual_outer", [_ARR, _ARR, _U64, _ARR, _ARR, _U64, _ARR], _I32)
def mutual_outer(a_r, a_z, b_r, b_z):
    """``M[i, j]`` between two filament sets — the outer-product shape,
    served without materialising the broadcast."""
    lib = require()
    ar, az = _f(np.atleast_1d(a_r)), _f(np.atleast_1d(a_z))
    br, bz = _f(np.atleast_1d(b_r)), _f(np.atleast_1d(b_z))
    out = np.empty((ar.size, br.size))
    rc = lib.fylite_rs_mutual_outer(ar, az, ar.size, br, bz, br.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_mutual_outer returned {rc}")
    return out


_sig("fylite_rs_element_filaments", [_F64, _F64, _F64, _F64, _F64, _F64, _U64, _U64, _ARR, _ARR], _I32)
def element_filaments(r, z, w, h, a=0.0, a2=90.0, *, nu: int = 4,
                      nv: int = 4):
    """Subdivide one conductor element into ``nu × nv`` filaments."""
    lib = require()
    n = int(nu) * int(nv)
    rf, zf = np.empty(n), np.empty(n)
    rc = lib.fylite_rs_element_filaments(float(r), float(z), float(w),
                                         float(h), float(a), float(a2),
                                         int(nu), int(nv), rf, zf)
    if rc != 0:
        raise KernelError(f"fylite_rs_element_filaments returned {rc}")
    return rf, zf


_sig("fylite_rs_mutual_matrix_self", [*_SIX, _U64, _U64, _U64, _ARR], _I32)
_sig("fylite_rs_mutual_matrix_cross", [*_SIX, _U64, *_SIX, _U64, _U64, _U64, _ARR], _I32)
_sig("fylite_rs_scale_by_turns", (_ARR, _U64, _U64, ctypes.c_void_p, ctypes.c_void_p), _I32)
def mutual_matrix(elems, other=None, *, nu: int = 4, nv: int = 4,
                  turns_a=None, turns_b=None):
    """Mutual-inductance matrix [H] between element sets.

    ``elems``/``other`` are six parallel arrays ``(r, z, w, h, a, a2)`` — the
    C-ABI layout, so this face does not need to know the caller's element
    type.  With ``other`` omitted the symmetric self-set matrix is returned,
    its diagonal the filament-averaged self inductance.

    ``turns_a``/``turns_b`` scale the result into TURN space; with ``other``
    omitted, ``turns_a`` alone applies to both sides (so the diagonal comes
    out with its ``N²``).
    """
    lib = require()
    ea = [_f(np.atleast_1d(x)) for x in elems]
    na = ea[0].size
    if other is None:
        out = np.empty((na, na))
        rc = lib.fylite_rs_mutual_matrix_self(*ea, na, int(nu), int(nv), out)
        nb = na
    else:
        eb = [_f(np.atleast_1d(x)) for x in other]
        nb = eb[0].size
        out = np.empty((na, nb))
        rc = lib.fylite_rs_mutual_matrix_cross(*ea, na, *eb, nb,
                                               int(nu), int(nv), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_mutual_matrix returned {rc}")
    if turns_a is not None or turns_b is not None:
        #: ★★A turn count enters an inductance ONCE PER SIDE, which is why a
        #: self-set matrix comes out squared on its diagonal and no caller
        #: writes that square by hand.  Getting it wrong yields a plausible
        #: L/R time that is wrong by exactly the winding.
        ta = None if turns_a is None else _f(np.broadcast_to(
            np.atleast_1d(np.asarray(turns_a, float)), (na,)))
        tb = turns_b if turns_b is not None else (
            turns_a if other is None else None)
        tb = None if tb is None else _f(np.broadcast_to(
            np.atleast_1d(np.asarray(tb, float)), (nb,)))
        rc = lib.fylite_rs_scale_by_turns(
            out.ravel(), na, nb,
            #: NULL on a side means "already per turn there"; the entry is
            #: declared `c_void_p`, so a pointer or None is what it takes
            None if ta is None else ta.ctypes.data,
            None if tb is None else tb.ctypes.data)
        if rc != 0:
            raise KernelError(f"fylite_rs_scale_by_turns returned {rc}")
    return out


_sig("fylite_rs_channel_weights", (_ARR, _ARR, _ARR, _U64, _U64, _U64, _ARR), _I32)
def channel_weights(channels, n_elements: int):
    """The ``(n_channel, n_element)`` map from ``[(element, weight), ...]``
    per channel.

    ★The index order is the whole content: this map was once rebuilt inline
    at three call sites — a grid fold, a point response, a circuit assembly —
    and ONE of the three was transposed relative to the others.  A transposed
    weight matrix is not a crash; it is a different machine.
    """
    lib = require()
    ch, el, wt = [], [], []
    for c, combo in enumerate(channels):
        for j, weight in combo:
            ch.append(float(c))
            el.append(float(j))
            wt.append(float(weight))
    n_ch = len(channels)
    out = np.empty(n_ch * int(n_elements))
    rc = lib.fylite_rs_channel_weights(_f(ch), _f(el), _f(wt), len(ch),
                                       n_ch, int(n_elements), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_channel_weights returned {rc}")
    return out.reshape(n_ch, int(n_elements))


_sig("fylite_rs_channel_fold", (_ARR, _ARR, _U64, _U64, _ARR), _I32)
def channel_fold(weights, channel_aturns):
    """Fold channel ampere-turns onto the elements they drive (``Wᵀ x``).

    A RELABELLING — which deck element a supply drives, and in what split —
    applied in ONE place and in one direction.
    """
    lib = require()
    w = _f(np.ascontiguousarray(weights, dtype=float))
    x = _f(np.atleast_1d(np.asarray(channel_aturns, float)))
    n_ch, n_el = w.shape
    if x.size != n_ch:
        raise KernelError(f"channel_fold: {x.size} ampere-turns against "
                          f"{n_ch} channels")
    out = np.empty(n_el)
    rc = lib.fylite_rs_channel_fold(w.ravel(), x, n_ch, n_el, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_channel_fold returned {rc}")
    return out


_sig("fylite_rs_grid_response", [*_SIX, _U64, _ARR, _U64, _ARR, _U64, _U64, _U64, _ARR], _I32)
def grid_response(elems, grid_r, grid_z, *, nu: int = 4, nv: int = 4):
    """ψ response [Wb/A] of each element on grid nodes → ``(n_elem, nr, nz)``."""
    lib = require()
    ea = [_f(np.atleast_1d(x)) for x in elems]
    gr, gz = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    out = np.empty((ea[0].size, gr.size, gz.size))
    rc = lib.fylite_rs_grid_response(*ea, ea[0].size, gr, gr.size, gz,
                                     gz.size, int(nu), int(nv), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_grid_response returned {rc}")
    return out


_sig("fylite_rs_element_response", [*_SIX, _U64, _ARR, _ARR, _U64, _U64, _U64, _ARR, _ARR, _ARR], _I32)
def element_response(elems, r, z, *, nu: int = 3, nv: int = 3):
    """Per-element ``(ψ, B_r, B_z)`` at scattered points.

    Three ``(n_points, n_elements)`` arrays in Wb/A-turn and T/A-turn — the
    ampere-TURN normalisation this package uses throughout, so no caller
    carries a turn table.
    """
    lib = require()
    ea = [_f(np.atleast_1d(x)) for x in elems]
    ne = ea[0].size
    r_a, z_a = _f(np.atleast_1d(r).ravel()), _f(np.atleast_1d(z).ravel())
    if r_a.size != z_a.size:
        raise KernelError("R and Z point vectors must be the same length")
    psi = np.empty((ne, r_a.size))
    br = np.empty((ne, r_a.size))
    bz = np.empty((ne, r_a.size))
    rc = lib.fylite_rs_element_response(*ea, ne, r_a, z_a, r_a.size,
                                        int(nu), int(nv), psi, br, bz)
    if rc != 0:
        raise KernelError(f"fylite_rs_element_response returned {rc}")
    return psi.T, br.T, bz.T


_sig("fylite_rs_element_probe_response", ([_ARR] * 6 + [_U64] + [_ARR] * 3 + [_U64, _U64, _U64, _ARR]), _I32)
def element_probe_response(elems, probe_r, probe_z, angle_rad, *,
                           nu: int = 3, nv: int = 3):
    """What each magnetic probe READS from each conductor element:
    ``(n_probe, n_element)`` in T per ampere-turn.

    ★The projection ``B_R cos(a) + B_Z sin(a)`` is the kernel's, not the
    caller's.  A probe's angle convention is physics — which way the sensor
    points decides the SIGN of what it reads — and a wrong convention does
    not raise: a fit converges on a plasma tilted to match.  It used to be
    written out next to each caller, each with its own finite-difference
    step, which is two conventions waiting to differ.

    Companion to :func:`probe_response`, which answers the same question for
    a GRID CELL rather than a conductor.
    """
    lib = require()
    ea = [_f(np.atleast_1d(x)) for x in elems]
    ne = ea[0].size
    pr, pz = _f(np.atleast_1d(probe_r)), _f(np.atleast_1d(probe_z))
    ang = _f(np.broadcast_to(np.atleast_1d(angle_rad), pr.shape))
    if pz.size != pr.size:
        raise ValueError("probe R and Z must be the same length")
    out = np.empty((pr.size, ne))
    rc = lib.fylite_rs_element_probe_response(*ea, ne, pr, pz, ang, pr.size,
                                              int(nu), int(nv), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_element_probe_response returned {rc}")
    return out


_sig("fylite_rs_coupling_gradient", [_ARR, _ARR, _ARR, _U64, _ARR, _ARR, _ARR, _U64, _ARR], _I32)
def coupling_gradient(plasma, loops):
    """``G_k = dM_pk/dZ_p`` [Wb/A/m], plasma-current-weighted (rigid shift).

    ``plasma`` is ``(r, z, amps)`` and ``loops`` ``(r, z, turns)``.
    """
    lib = require()
    pr, pz, pa = (_f(np.atleast_1d(x)) for x in plasma)
    lr, lz, lt = (_f(np.atleast_1d(x)) for x in loops)
    if float(np.sum(pa)) == 0.0:                 # a domain error, see ellipke
        raise ValueError("total plasma current must be non-zero")
    out = np.empty(lr.size)
    rc = lib.fylite_rs_coupling_gradient(pr, pz, pa, pr.size, lr, lz, lt,
                                         lr.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_coupling_gradient returned {rc}")
    return out


_sig("fylite_rs_vertical_stiffness", [_ARR, _ARR, _ARR, _U64, _ARR, _ARR, _ARR, _ARR, _U64, _F64, _ARR], _I32)
def vertical_stiffness(plasma, loops, currents, *, step: float = 1.0e-3):
    """External-field stiffness ``k = Σ a_i d²ψ_ext/dZ²`` [N/m]; ``k > 0``
    destabilising."""
    lib = require()
    pr, pz, pa = (_f(np.atleast_1d(x)) for x in plasma)
    lr, lz, lt = (_f(np.atleast_1d(x)) for x in loops)
    cur = _f(np.atleast_1d(currents))
    if cur.size != lr.size:                      # domain errors, see ellipke
        raise ValueError(f"currents length {cur.size} != loops {lr.size}")
    if not step > 0.0:
        raise ValueError(f"step must be positive (got {step!r})")
    out = np.empty(1)
    rc = lib.fylite_rs_vertical_stiffness(pr, pz, pa, pr.size, lr, lz, lt,
                                          cur, lr.size, float(step), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_vertical_stiffness returned {rc}")
    return float(out[0])


# `psi_plasma` is declared `c_void_p` so `None` is a legal argument:
# the trajectory without a plasma back-reaction is the same entry with
# the term switched off, not a second one
_sig("fylite_rs_evolve_circuits", [_ARR, _ARR, _U64, _ARR, _U64, _ARR, _ARR, ctypes.c_void_p, _ARR], _I32)
def evolve_circuits(inductance, resistance, currents0, time, voltages,
                    psi_plasma=None):
    """Voltage-driven circuit trajectory → ``(n_time, n_loops)``.

    The implicit step over ``[t_k, t_k+1]`` consumes the interval-END sample
    ``voltages[k+1]``; ``time`` may be non-uniform but must increase.
    ``psi_plasma`` — ``(n_time, n_loops)`` when given — enters as its
    per-step INCREMENT, on the same interval-end convention.

    ★★The plasma back-reaction is a switch on this entry, not a second
    trajectory.  It used to be the one case the kernel would not take, so a
    caller that had ψ_plasma looped over ``step_circuits`` in Python
    instead — the same advance assembled a second way, with nothing
    comparing the two.

    ★This entry re-forms and re-factorises ``M/dt + diag(R)`` at every
    step, as it must on a non-uniform time grid; it does not reuse one
    factorisation across a uniform one.  Said here because the comment this
    replaced claimed the opposite, and a reader choosing between this and
    :func:`step_circuits` on cost would have been choosing on a fiction.
    """
    lib = require()
    m = _f(np.asarray(inductance, float))
    r = _f(np.asarray(resistance, float))
    i0 = _f(np.atleast_1d(currents0))
    t = _f(np.atleast_1d(time))
    v = _f(np.asarray(voltages, float))
    psi = None if psi_plasma is None else _f(np.asarray(psi_plasma, float))
    #: ★★Every buffer the ABI will READ is sized here, because this is the
    #: only layer that knows how much it will read.  `fylite_rs_evolve_
    #: circuits` takes `nt` and `n` and then takes `nt*n` doubles from
    #: `volts` on trust: a short array is not a refused call, it is a heap
    #: OVERREAD — silent, and surfacing later somewhere unrelated (this repo
    #: has had one, 104 bytes, which aborted two test files away).  The
    #: `voltages` half of this used to be checked in one Python caller
    #: instead, so every other host reached the entry unchecked.
    if t.ndim != 1 or t.size < 2:
        raise KernelError(f"time must be 1-D with >= 2 samples, got {t.shape}")
    if m.shape != (i0.size, i0.size):
        raise KernelError(f"inductance must be ({i0.size},{i0.size}), "
                          f"got {m.shape}")
    if r.size != i0.size:
        raise KernelError(f"{r.size} resistances for {i0.size} loops")
    if v.shape != (t.size, i0.size):
        raise KernelError(f"voltages has shape {v.shape}, expected "
                          f"{(t.size, i0.size)}")
    if psi is not None and psi.shape != (t.size, i0.size):
        raise KernelError(f"psi_plasma has shape {psi.shape}, expected "
                          f"{(t.size, i0.size)}")
    out = np.empty((t.size, i0.size))
    rc = lib.fylite_rs_evolve_circuits(
        m, r, i0.size, t, t.size, v, i0,
        None if psi is None else psi.ctypes.data, out)
    if rc == -2:
        raise KernelError(
            "the time grid must be strictly increasing.  A non-increasing "
            "one does not fail on its own: M/dt + diag(R) with dt < 0 stays "
            "positive definite whenever R dominates, so the solve succeeds "
            "and the trajectory it returns runs backwards")
    if rc != 0:
        raise KernelError(f"fylite_rs_evolve_circuits returned {rc}")
    return out


_sig("fylite_rs_element_flux", [*_SIX, _U64, _ARR, _ARR, _U64, _ARR, _U64, _U64, _U64, _ARR], _I32)
def element_flux(elems, amps, grid_r, grid_z, *, nu: int = 4, nv: int = 4):
    """Total ψ [Wb] on the grid from ``amps`` ampere-turns per element.

    ``elems`` is the six parallel arrays ``(r, z, w, h, a, a2)``.  Returns
    ``(nr, nz)``.

    ★Not :func:`grid_response` followed by a contraction: that materialises
    an ``(nelem, nr, nz)`` tensor to produce one ``(nr, nz)`` field, and it
    leaves the fold — where a sign or a per-radian convention gets applied
    twice — at the call site.
    """
    lib = require()
    ea = [_f(np.atleast_1d(x)) for x in elems]
    a = _f(np.atleast_1d(amps))
    gr, gz = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    if a.size != ea[0].size:
        raise KernelError(f"amps has {a.size} entries, expected "
                          f"{ea[0].size} (one per element)")
    out = np.empty((gr.size, gz.size))
    rc = lib.fylite_rs_element_flux(*ea, ea[0].size, a, gr, gr.size, gz,
                                    gz.size, int(nu), int(nv), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_element_flux returned {rc}")
    return out


_sig("fylite_rs_filament_flux", [_ARR, _ARR, _ARR, _U64, _ARR, _U64, _ARR, _U64, _ARR], _I32)
def filament_flux(fil_r, fil_z, amps, grid_r, grid_z):
    """Total ψ [Wb] on the grid from a cloud of current FILAMENTS.

    The element-free twin of :func:`element_flux`, for a current
    distribution that is already a point cloud (a plasma discretised into
    filaments).  Returns ``(nr, nz)``.
    """
    lib = require()
    fr, fz = _f(np.atleast_1d(fil_r)), _f(np.atleast_1d(fil_z))
    a = _f(np.atleast_1d(amps))
    gr, gz = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    if fz.size != fr.size or a.size != fr.size:
        raise KernelError(
            f"filament arrays disagree: r {fr.size}, z {fz.size}, "
            f"amps {a.size}")
    out = np.empty((gr.size, gz.size))
    rc = lib.fylite_rs_filament_flux(fr, fz, a, fr.size, gr, gr.size, gz,
                                     gz.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_filament_flux returned {rc}")
    return out


_sig("fylite_rs_channel_matrices", [*_SIX, _U64, *_SIX, _U64, _ARR, _U64, _ARR, _ARR, _U64, _U64, _ARR, _ARR], _I32)
def channel_matrices(coils, vessel, weights, *, eta_coil, eta_vessel,
                     nu: int = 4, nv: int = 4):
    """``(M, R)`` in AMPERE-TURN channel space — channels then vessel.

    ``coils``/``vessel`` are the six parallel arrays; ``weights`` is the
    ``(n_channel, n_element)`` map of how a channel's ampere-turns split
    across the elements it drives; ``eta_*`` are per element in **Ω·m** (a
    device deck quotes μΩ·m — convert where the deck is read).

    ★The weight enters the inductance once and the resistance SQUARED:
    in ampere-turn space the loop equation carries only per-turn geometric
    quantities, so ``M_ch = W M₁ Wᵀ`` while ``R_ch = Σ_j w_j² R₁_j``.
    Dropping the square gives a plausible L/R time that is wrong by the
    split.
    """
    lib = require()
    ca = [_f(np.atleast_1d(x)) for x in coils]
    va = [_f(np.atleast_1d(x)) for x in vessel]
    n_el, n_vs = ca[0].size, va[0].size
    w = _f(np.atleast_2d(weights))
    if w.shape[1] != n_el:
        raise KernelError(f"weights has {w.shape[1]} columns, expected "
                          f"{n_el} (one per coil element)")
    n_ch = w.shape[0]
    ec = _f(np.broadcast_to(np.asarray(eta_coil, float), (n_el,)))
    ev = _f(np.broadcast_to(np.asarray(eta_vessel, float), (n_vs,)))
    n = n_ch + n_vs
    m, r = np.empty((n, n)), np.empty(n)
    rc = lib.fylite_rs_channel_matrices(*ca, n_el, *va, n_vs, w.ravel(),
                                        n_ch, ec, ev, int(nu), int(nv), m, r)
    if rc != 0:
        raise KernelError(f"fylite_rs_channel_matrices returned {rc}")
    return m, r


_sig("fylite_rs_table_ratio_check", ([_ARR] * 2 + [_ARR, _U64, _ARR, _U64] + [_ARR] * 4 + [_U64, _ARR, _ARR]), _I32)
def table_ratio_check(table, mine, grid_r, grid_z, elems) -> dict:
    """The two-path acceptance: how a recomputed psi response compares with
    a device's own Green table, per conductor segment.

    ``table`` and ``mine`` are both ``(n_seg, nr, nz)``; ``elems`` is the
    six-parallel-array element layout (only ``r, z, w, h`` are read).
    Returns ``{per_segment, ratio_median, ratio_min, ratio_max}``.

    ★Grid nodes within ``2·max(w, h)`` of a segment are DROPPED before the
    ratio is taken: near its own conductor the response depends on how
    finely the element was filamented, and the table's filamentisation is
    not this code's — those nodes measure a discretisation difference, not
    the agreement being checked.  ★★And it is a MEDIAN: what the check must
    survive is a stray near-field node the mask did not catch, and one of
    those moves a mean by more than the whole tolerance.
    """
    lib = require()
    tab, m = _f(table), _f(mine)
    gr, gz = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    ea = [_f(np.atleast_1d(x)) for x in elems]
    n_seg = ea[0].size
    want = (n_seg, gr.size, gz.size)
    if tab.shape != want or m.shape != want:
        raise KernelError(f"table {tab.shape} and computed {m.shape} must "
                          f"both be {want}")
    out, out3 = np.empty(n_seg), np.empty(3)
    rc = lib.fylite_rs_table_ratio_check(tab.ravel(), m.ravel(), gr, gr.size,
                                         gz, gz.size, ea[0], ea[1], ea[2],
                                         ea[3], n_seg, out, out3)
    if rc != 0:
        raise KernelError(f"fylite_rs_table_ratio_check returned {rc}")
    return {"per_segment": out, "ratio_median": float(out3[0]),
            "ratio_min": float(out3[1]), "ratio_max": float(out3[2])}


_sig("fylite_rs_plasma_filaments", ([_F64] * 4 + [_U64] * 2 + [_ARR] + [_F64] * 2 + [_ARR, _U64, _ARR, _U64, _ARR, _ARR, _U64] + [_F64, _U64, _U64] + [_ARR] * 3), _I32)
def plasma_filaments(grid: Grid, psi, *, psi_axis: float, psi_bnd: float,
                     pprime, ffprim, boundary, ip: float,
                     coarsen: int = 2) -> tuple:
    """A rigid filament set ``(r, z, amps)`` from an equilibrium's profiles.

    ``j_φ = R p′ + FF′/(μ₀R)`` on the cells inside the boundary, rescaled so
    the sum reproduces ``ip`` exactly — a percent there is two percent on a
    growth rate, which is quadratic in the current.
    """
    lib = require()
    psi = _f(psi)
    if psi.shape != (grid.nr, grid.nz):
        raise KernelError(f"psi has shape {psi.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    pp, ff = _f(pprime), _f(ffprim)
    br, bz = _f(boundary[0]), _f(boundary[1])
    c = max(int(coarsen), 1)
    cap = ((grid.nr + c - 1) // c) * ((grid.nz + c - 1) // c)
    out_r, out_z, out_a = (np.empty(cap) for _ in range(3))
    rc = lib.fylite_rs_plasma_filaments(
        *grid.args, psi.ravel(), float(psi_axis), float(psi_bnd),
        pp, pp.size, ff, ff.size, br, bz, br.size, float(ip), c, cap,
        out_r, out_z, out_a)
    if rc < 0:
        raise KernelError(f"fylite_rs_plasma_filaments returned {rc}")
    return out_r[:rc].copy(), out_z[:rc].copy(), out_a[:rc].copy()


_sig("fylite_rs_spitzer_eta", [_ARR] * 3 + [_U64, _ARR], _I32)
def spitzer_eta(te_ev, zeff=1.0, lnlam=17.0):
    """Parallel Spitzer resistivity [Ω·m] — the NRL formula tier,
    ``η_∥ = 0.51 η_⊥`` (Spitzer & Härm, ``γ(Z=1) = 0.51``).

    ★Corrected at ABI v111 (T-A18): through v110 this returned the NRL
    PERPENDICULAR coefficient under the parallel name, and the ohmic power
    computed through it was high by ``1/0.51``.  The perpendicular value is
    :func:`spitzer_eta_perp`; ``spitzer_eta / spitzer_eta_perp == 0.51``
    per point, pinned by tests on both hosts.

    The trapped-particle correction is a separate model, not folded in.
    """
    lib = require()
    te = _f(np.atleast_1d(te_ev))
    z = _f(np.broadcast_to(np.asarray(zeff, float), te.shape))
    l = _f(np.broadcast_to(np.asarray(lnlam, float), te.shape))
    out = np.empty(te.size)
    rc = lib.fylite_rs_spitzer_eta(te, z, l, te.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_spitzer_eta returned {rc}")
    return out


_sig("fylite_rs_eped1nn", [_F64] * 10 + [_ARR], _I32)
def eped1nn(*, a, betan, bt, delta, ip, kappa, mass, neped, r, zeffped):
    """The EPED1-NN pedestal surrogate (T-M4): H-mode pedestal height and
    width from ten scalars.

    Units are EPED's own: ``a``/``r`` [m], ``betan`` the GLOBAL normalized
    beta, ``bt`` [T], ``delta`` the (effective) triangularity, ``ip`` [MA],
    ``kappa``, ``mass`` [amu], ``neped`` [1e19 m⁻³], ``zeffped``.

    Returns a dict: ``p_ped`` (9, Pa) and ``width`` (9, ψ_N) in the order
    (dmagGH, dmagG, dmagH) × (sol0..2) — **index 0 is the standard EPED1
    prediction** — plus ``extrapolation`` (worst normalized distance
    outside the training box, 0 = inside) and ``worst_input`` (its index).
    Out-of-box inputs are answered with the distance reported, as the
    upstream model warns rather than refuses.

    Sources: Snyder et al. Phys. Plasmas 16 056118 (2009) / NF 51 103016
    (2011); Meneghini et al. NF 57 086034 (2017); weights from EPEDNN.jl
    (Apache-2.0), sha256-pinned in the kernel.
    """
    lib = require()
    out = np.empty(20)
    rc = lib.fylite_rs_eped1nn(
        float(a), float(betan), float(bt), float(delta), float(ip),
        float(kappa), float(mass), float(neped), float(r), float(zeffped),
        out)
    if rc != 0:
        raise KernelError(f"fylite_rs_eped1nn returned {rc}")
    return {"p_ped": out[:9].copy(), "width": out[9:18].copy(),
            "extrapolation": float(out[18]), "worst_input": int(out[19])}


_sig("fylite_rs_spitzer_eta_perp", [_ARR] * 3 + [_U64, _ARR], _I32)
def spitzer_eta_perp(te_ev, zeff=1.0, lnlam=17.0):
    """PERPENDICULAR Spitzer resistivity [Ω·m] — the NRL coefficient as
    printed, ``1.03e-2 Z lnΛ Te^-1.5`` Ω·cm (T-A18).

    The value :func:`spitzer_eta` returned through ABI v110 under the
    parallel name — exported so the correction is a checkable relation
    (ratio ≡ 0.51) rather than a silent renumbering.
    """
    lib = require()
    te = _f(np.atleast_1d(te_ev))
    z = _f(np.broadcast_to(np.asarray(zeff, float), te.shape))
    l = _f(np.broadcast_to(np.asarray(lnlam, float), te.shape))
    out = np.empty(te.size)
    rc = lib.fylite_rs_spitzer_eta_perp(te, z, l, te.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_spitzer_eta_perp returned {rc}")
    return out


# --------------------------------------------------------------------------- #
# flux matching (transport.rs)
# --------------------------------------------------------------------------- #
_sig("fylite_rs_reintegrate", [_ARR, _ARR, _U64, _F64, _I32, _ARR], _I32)
def reintegrate(gradient, r, anchor: float, *, log: bool = True):
    """A profile from its gradient, integrated INWARD from the edge.

    That direction is the boundary condition of a flux-matching solve: the
    pedestal top is pinned and everything inside follows from the gradients
    being solved for.  ``log`` takes the ``-d ln x/dr`` convention.
    """
    lib = require()
    g, x = _f(gradient), _f(r)
    out = np.empty(g.size)
    rc = lib.fylite_rs_reintegrate(g, x, g.size, float(anchor),
                                   1 if log else 0, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_reintegrate returned {rc}")
    return out


_sig("fylite_rs_flux_residual", [_ARR, _ARR, _U64, _I32, _ARR], _I32)
def flux_residual(f, g, *, method: int = 3):
    """Per-point flux-match residual: ``|f-g|`` (2) or ``(f-g)²`` (3)."""
    lib = require()
    f_a, g_a = _f(f), _f(g)
    out = np.empty(f_a.size)
    rc = lib.fylite_rs_flux_residual(f_a, g_a, f_a.size, int(method), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_flux_residual returned {rc}"
                          + (" — method must be 2 or 3" if rc == -7 else ""))
    return out


_sig("fylite_rs_flux_match_step", [_ARR] * 5 + [_U64, _F64, _ARR], _I32)
def flux_match_step(jf, jg, f, g, relax, *, dx_max: float = 1.0):
    """The clamped Newton step of a flux match.

    ★The TARGET Jacobian is in the matrix: raising a gradient changes the
    profile and therefore the sources, so a step from the flux Jacobian
    alone systematically overshoots.  A singular matrix raises — it means
    the model flux is insensitive to one of the gradients, which is a
    statement about the physics.
    """
    lib = require()
    f_a, g_a, rl = _f(f), _f(g), _f(relax)
    n = f_a.size
    jf_a, jg_a = _f(np.reshape(jf, (n, n))), _f(np.reshape(jg, (n, n)))
    out = np.empty(n)
    rc = lib.fylite_rs_flux_match_step(jf_a.ravel(), jg_a.ravel(), f_a, g_a,
                                       rl, n, float(dx_max), out)
    if rc != 0:
        raise KernelError(
            "fylite_rs_flux_match_step: the Newton matrix is singular — the "
            "model flux is insensitive to at least one gradient here"
            if rc == -6 else f"fylite_rs_flux_match_step returned {rc}")
    return out


_sig("fylite_rs_flux_match_backoff", ([_ARR] * 6 + [_U64, _F64] + [_ARR] * 2), _I32)
def flux_match_backoff(x0, x_try, step, res0, res, relax, *,
                       relax_factor: float = 2.0) -> dict:
    """The per-point relaxation backoff of a flux match.

    Where the residual ROSE the component is reverted and its relaxation
    cut; where it has already been cut three times the point is thrown
    TWICE as far instead, on the theory that it is stuck rather than
    overshooting.  Returns ``{"x", "relax", "reevaluate"}``.
    """
    lib = require()
    args = [_f(a) for a in (x0, x_try, step, res0, res, relax)]
    n = args[0].size
    ox, orl = np.empty(n), np.empty(n)
    rc = lib.fylite_rs_flux_match_backoff(*args, n, float(relax_factor),
                                          ox, orl)
    if rc < 0:
        raise KernelError(f"fylite_rs_flux_match_backoff returned {rc}")
    return {"x": ox, "relax": orl, "reevaluate": bool(rc)}


class FluxMatchError(KernelError):
    """A flux match that could not proceed (singular Newton system, or a
    shape the channel-fastest layout cannot carry)."""


_sig("fylite_rs_flux_match_state_len", [_U64, _U64], _U64)
_sig("fylite_rs_flux_match_init",
     [_ARR] + [_U64] * 2 + [_F64] * 3 + [_U64, _I32, _F64, _ARR, _U64], _I32)
_sig("fylite_rs_flux_match_next", [_ARR, _U64, _ARR, _ARR, _U64, _ARR], _I32)
_sig("fylite_rs_flux_match_result", [_ARR, _U64, _U64] + [_ARR] * 5, _I32)
def flux_match(x0, evaluate, *, n_evolve: int = 1, dx: float = 0.05,
               dx_max: float = 1.0, relax_factor: float = 2.0,
               iterations: int = 8, method: int = 3, tol=None,
               callback=None) -> dict:
    """Newton flux match in gradient space — the steady-state solve.

    ``x0`` is the initial gradient vector, laid out CHANNEL-FASTEST
    (``[ch0@r1, ch1@r1, …, ch0@r2, …]`` — upstream's ``evolve_indx``
    order); ``evaluate(x)`` returns ``(flux, target)`` at that point.
    Returns ``{"x", "flux", "target", "residual", "iterations",
    "converged"}``.

    ★★The loop is the KERNEL's, and this is its pump.  A flux evaluation
    costs seconds and belongs where the caller can cache or replay it, so
    the models stay a Python callback — but a callback is a reason to
    evaluate ``f`` here, not a reason to decide anything else here.  Which
    point to probe next, how the Jacobian is assembled, the clamp, the
    backoff and the convergence test are all on the other side, and the
    machine is resumed from a buffer this function holds.

    ★Both models are evaluated at the SAME point on every request.  The
    Python loop this replaced ran the flux over all probe points and then
    the target over the same points, so a STATEFUL callback saw a different
    call order; every number is identical, and one request per point is
    what a real driver wants, since it holds one surface state.

    ``tol`` (on the max residual) is optional: without it the loop runs the
    full ``iterations``, as upstream does — and reports ``converged``
    False, because nobody asked.  ``callback(iteration, result)`` fires at
    each iteration boundary.
    """
    lib = require()
    x = _f(np.atleast_1d(x0))
    p_max = x.size
    nstate = int(lib.fylite_rs_flux_match_state_len(p_max, int(n_evolve)))
    state = np.zeros(nstate)
    rc = lib.fylite_rs_flux_match_init(
        x, p_max, int(n_evolve), float(dx), float(dx_max),
        float(relax_factor), int(iterations), int(method),
        float("nan") if tol is None else float(tol), state, nstate)
    if rc != 0:
        raise FluxMatchError(_FLUX_MATCH_ERRORS.get(
            rc, f"fylite_rs_flux_match_init returned {rc}"))

    def result() -> dict:
        xo, fo, go, ro = (np.empty(p_max) for _ in range(4))
        info = np.empty(3)
        code = lib.fylite_rs_flux_match_result(state, nstate, p_max, xo, fo,
                                               go, ro, info)
        if code != 0:
            raise FluxMatchError(
                f"fylite_rs_flux_match_result returned {code}")
        return {"x": xo, "flux": fo, "target": go, "residual": ro,
                "iterations": int(info[0]), "converged": bool(info[1])}

    #: the machine hands back the point to evaluate; the very first one is
    #: `x0` itself, which `init` has already written into the state
    x_next = x.copy()
    f, g = (_f(v) for v in evaluate(x_next))
    while True:
        req = lib.fylite_rs_flux_match_next(state, nstate, f, g, p_max,
                                            x_next)
        if req < 0:
            raise FluxMatchError(_FLUX_MATCH_ERRORS.get(
                req, f"fylite_rs_flux_match_next returned {req}"))
        if req == 0:
            return result()
        if req == 2:
            res = result()
            if callback is not None:
                callback(res["iterations"], res)
            f, g = _f(res["flux"]), _f(res["target"])
            continue
        f, g = (_f(v) for v in evaluate(x_next.copy()))


#: What the flux-match machine refuses, and why.
_FLUX_MATCH_ERRORS = {
    -2: ("flux_match: p_max must be a positive multiple of n_evolve and dx "
         "must be non-zero — the gradient vector is channel-fastest, so a "
         "channel is x[ip::n_evolve] and a ragged length has no channels"),
    -3: "flux_match: residual method must be 2 or 3",
    -6: ("flux_match: the Newton matrix is singular — the model flux is "
         "insensitive to at least one gradient here, which is a statement "
         "about the physics rather than a numerical nuisance"),
}


# --------------------------------------------------------------------------- #
# source terms and their integrals (sources.rs)
# --------------------------------------------------------------------------- #
_sig("fylite_rs_adas_id", [ctypes.c_char_p, _U64], _I32)
def adas_id(name: str) -> int:
    """The kernel's index for an ADAS species, or −1 for an unknown one.

    ★−1 is worth checking rather than ignoring: an unknown species radiates
    ZERO line power downstream (upstream's behaviour), so a typo in a
    species name yields a plasma with no impurity radiation rather than a
    complaint.
    """
    lib = require()
    b = str(name).encode()
    return int(lib.fylite_rs_adas_id(b, len(b)))


_sig("fylite_rs_adas_species_count", [], _I32)
_sig("fylite_rs_adas_species_name", [_U64, ctypes.c_char_p, _U64], _I32)
def adas_species() -> list[str]:
    """The species the kernel's ADAS table carries, in its own order."""
    lib = require()
    n = int(lib.fylite_rs_adas_species_count())
    out = []
    for i in range(n):
        buf = ctypes.create_string_buffer(16)
        ln = int(lib.fylite_rs_adas_species_name(i, buf, len(buf)))
        if ln < 0:
            raise KernelError(f"fylite_rs_adas_species_name({i}) → {ln}")
        out.append(buf.raw[:ln].decode())
    return out


_sig("fylite_rs_adas_cooling", [_I32, _ARR, _U64, _ARR], _I32)
def adas_cooling(name, te_kev):
    """The ADAS cooling rate ``Lz`` [erg cm³/s] of one species.

    Clamped outside the fit domain [0.05, 50] keV rather than
    extrapolated — upstream's rule, and worth knowing when a pedestal foot
    is fed in.  An unknown species radiates zero.
    """
    lib = require()
    te = _f(np.atleast_1d(te_kev))
    out = np.empty(te.size)
    rc = lib.fylite_rs_adas_cooling(adas_id(name), te, te.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_adas_cooling returned {rc}")
    return out


_sig("fylite_rs_rad_ion", ([_ARR, _ARR, _U64, _ARR, _ARR, np.ctypeslib.ndpointer( dtype=np.int32, flags="C_CONTIGUOUS"), _U64] + [_ARR] * 3), _I32)
def rad_ion(te_ev, ne_cgs, ni_cgs, z, names) -> dict:
    """Bremsstrahlung + ADAS line radiation [erg/cm³/s].

    Returns ``{"brem", "line", "total"}``.

    ★The split is not physical — ``brem`` is the approximate NRL formula and
    ``line`` is what remains of the ADAS total; only the sum is the ADAS
    value.  Upstream is explicit about this, and it matters the moment one
    channel is quoted on its own.
    """
    lib = require()
    te, ne = _f(np.atleast_1d(te_ev)), _f(np.atleast_1d(ne_cgs))
    n = te.size
    z_a = _f(np.atleast_1d(z))
    nion = z_a.size
    ni = _f(np.broadcast_to(np.asarray(ni_cgs, float).reshape(nion, -1),
                            (nion, n)))
    ids = np.ascontiguousarray([adas_id(nm) for nm in names], dtype=np.int32)
    brem, line, total = (np.empty(n) for _ in range(3))
    rc = lib.fylite_rs_rad_ion(te, ne, n, ni.ravel(), z_a, ids, nion,
                               brem, line, total)
    if rc != 0:
        raise KernelError(f"fylite_rs_rad_ion returned {rc}")
    return {"brem": brem, "line": line, "total": total}


_sig("fylite_rs_rad_sync", [_ARR, _ARR, _ARR, _U64, _F64, _F64, _F64, _ARR], _I32)
def rad_sync(te_ev, ne_cgs, b_ref_g, *, aspect_ratio: float, a_cm: float,
             reflection: float = 0.8):
    """Synchrotron radiation [erg/cm³/s] (Trubnikov).

    ``b_ref_g`` is the TOROIDAL field at the surface, not ``B_unit`` — the
    term goes as ``B⁴``.  (Upstream feeds it ``expro_bt0``.)
    """
    lib = require()
    te, ne = _f(np.atleast_1d(te_ev)), _f(np.atleast_1d(ne_cgs))
    b = _f(np.broadcast_to(np.atleast_1d(b_ref_g), te.shape))
    out = np.empty(te.size)
    rc = lib.fylite_rs_rad_sync(te, ne, b, te.size, float(aspect_ratio),
                                float(a_cm), float(reflection), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_rad_sync returned {rc}")
    return out


_sig("fylite_rs_exchange_power", [_ARR] * 4 + [_U64, _ARR], _I32)
def exchange_power(nu_exch, ne_cgs, te_ev, ti_ev):
    """Classical e-i exchange [erg/cm³/s], positive INTO THE IONS.

    ``1.5 n_e k (T_e - T_i) nu_exch``; the coefficient comes from
    :func:`collision_rates`.

    ★In a Te/Ti two-channel solve this is the DOMINANT coupling — it is what
    stops the two channels being independent one-dimensional problems.
    """
    lib = require()
    args = [_f(np.atleast_1d(a)) for a in (nu_exch, ne_cgs, te_ev, ti_ev)]
    n = max(a.size for a in args)
    args = [_f(np.broadcast_to(a, (n,))) for a in args]
    out = np.empty(n)
    rc = lib.fylite_rs_exchange_power(*args, n, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_exchange_power returned {rc}")
    return out


_sig("fylite_rs_volume_int", [_ARR, _ARR, _ARR, _U64, _I32, _ARR], _I32)
def volume_int(s, weight, x, *, mode: str = "sparse"):
    """A volume integral of a source density.

    ``mode="sparse"`` is upstream's quadratic quadrature on a flux-matching
    mesh (``x = r``, ``weight = V'``); ``mode="volume"`` is the trapezoid in
    VOLUME on the full experimental mesh (``x = V``, weight ignored);
    ``mode="weighted"`` is the trapezoid ``∫ s w dx`` a DENSE PDE grid wants.
    ★The first two are not interchangeable — swapping them reproduces
    neither code's numbers.
    """
    lib = require()
    modes = {"sparse": 0, "volume": 1, "weighted": 2}
    if mode not in modes:
        raise KernelError(f"unknown integrator {mode!r}; have {sorted(modes)}")
    s_a, x_a = _f(s), _f(x)
    w = _f(np.broadcast_to(np.asarray(1.0 if weight is None else weight,
                                      float), s_a.shape))
    out = np.empty(s_a.size)
    rc = lib.fylite_rs_volume_int(s_a, w, x_a, s_a.size, modes[mode], out)
    if rc != 0:
        raise KernelError(f"fylite_rs_volume_int returned {rc}"
                          + (" — the sparse quadrature needs three radii"
                             if rc == -5 else ""))
    return out


_sig("fylite_rs_target_flux", [_ARR] * 3 + [_U64, _ARR], _I32)
def target_flux(power, volp, unit):
    """An integrated power as a gyro-Bohm-normalised target flux.

    Index 0 is zero by construction: no volume enclosed, nothing to carry.
    """
    lib = require()
    p, v, u = _f(power), _f(volp), _f(np.broadcast_to(unit, np.shape(volp)))
    out = np.empty(p.size)
    rc = lib.fylite_rs_target_flux(p, v, u, p.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_target_flux returned {rc}")
    return out


#: The 20-float surface block three kernel entries share, in order.  ★It is
#: a LAYOUT, not a dict: the kernel reads it positionally, so a caller that
#: builds it by hand and gets one column wrong hands over a different
#: plasma without anything raising.  Build it here.
SURFACE_KEYS = ("a", "rmin", "rmaj", "zmag", "drmaj", "dzmag", "q", "shear",
                "kappa", "s_kappa", "delta", "s_delta", "zeta", "s_zeta",
                "b_unit", "te", "ne", "dlnnedr", "dlntedr")


def surface_block(st: dict) -> np.ndarray:
    """The 20-float surface block from a surface state, **in SI**.

    Lengths [m], ``b_unit`` [T], ``ne`` [m^-3], ``te`` [eV], log-gradients
    [1/m].  The kernel converts to the TGYRO port's CGS behind the ABI
    (``c_api.rs::surface_from_block``), once for all three entries that take
    this block, rather than each caller doing it on the way in.
    """
    return _f([float(st[k]) for k in SURFACE_KEYS] + [0.0])


def _ion_columns(ions):
    cols = {k: _f([float(i[k]) for i in ions])
            for k in ("z", "mass", "ni", "ti", "dlnnidr", "dlntidr")}
    cols["therm"] = _f([1.0 if i.get("therm", True) else 0.0 for i in ions])
    return cols


_sig("fylite_rs_collision_rates", ([_ARR, _ARR, _U64] + [_ARR] * 5 + [_U64] + [_ARR] * 4), _I32)
def collision_rates(ne, te, ni, ti, mass, z, therm=None) -> dict:
    """Collision frequencies over a PROFILE, plus the exchange rate.

    CGS with eV temperatures.  ``ni``/``ti`` are per ion, each as long as
    ``ne``; ``therm`` (per ion, default all True) gates the EXCHANGE sum
    only — a fast-ion population is not in equilibrium with the electrons.

    Returns ``{"nue", "nui", "nu_exch", "loglam"}``, with ``nui`` shaped
    ``(n_ion, n)`` and the rest ``(n,)``; scalars in, scalars out.
    """
    lib = require()
    scalar = np.ndim(ne) == 0
    ne_a, te_a = _f(np.atleast_1d(ne)), _f(np.atleast_1d(te))
    n = ne_a.size
    z_a, m_a = _f(np.atleast_1d(z)), _f(np.atleast_1d(mass))
    nion = z_a.size
    ni_a = _f(np.broadcast_to(np.asarray(ni, float).reshape(nion, -1), (nion, n)))
    ti_a = _f(np.broadcast_to(np.asarray(ti, float).reshape(nion, -1), (nion, n)))
    th = (_f(np.ones(nion)) if therm is None
          else _f([1.0 if t else 0.0 for t in np.atleast_1d(therm)]))
    nue, exch, loglam = (np.empty(n) for _ in range(3))
    nui = np.empty(nion * n)
    rc = lib.fylite_rs_collision_rates(ne_a, te_a, n, ni_a.ravel(),
                                       ti_a.ravel(), m_a, z_a, th, nion,
                                       nue, nui, exch, loglam)
    if rc != 0:
        raise KernelError(f"fylite_rs_collision_rates returned {rc}")
    nui = nui.reshape(nion, n)
    if scalar:
        return {"nue": float(nue[0]), "nui": nui[:, 0].copy(),
                "nu_exch": float(exch[0]), "loglam": float(loglam[0])}
    return {"nue": nue, "nui": nui, "nu_exch": exch, "loglam": loglam}


_sig("fylite_rs_surface_derived", ([_ARR] + [_F64] * 2 + [_ARR] * 7 + [_U64] + [_F64] * 2 + [_ARR, _ARR]), _I32)
def surface_derived(st: dict, *, pext: float = 0.0,
                    dpext: float = 0.0) -> dict:
    """One surface's derived state, **in SI** — sound speed, rates, pressure,
    betas.

    ``c_s``/``rho_s`` [m/s], [m]; ``pr`` [Pa]; ``dlnpdr`` [1/m]; ``nue``,
    ``nui``, ``nu_exch`` [1/s]; the betas dimensionless.

    Assembled in the kernel so every downstream map is a lookup: these
    quantities cross normalisation boundaries (``beta`` is referenced to
    ``B_unit``, the pressure is the TOTAL one), and a second assembly is a
    second chance to cross one wrongly with nothing raising.
    """
    lib = require()
    cols = _ion_columns(st["ions"])
    nion = cols["z"].size
    out, nui = np.empty(8), np.empty(nion)
    rc = lib.fylite_rs_surface_derived(
        surface_block(st), float(st["signb"]), float(st["signq"]),
        cols["z"], cols["mass"], cols["ni"], cols["ti"], cols["dlnnidr"],
        cols["dlntidr"], cols["therm"], nion, float(pext), float(dpext),
        out, nui)
    if rc != 0:
        raise KernelError(f"fylite_rs_surface_derived returned {rc}")
    keys = ("c_s", "rho_s", "nue", "nu_exch", "pr", "beta_unit",
            "betae_unit", "dlnpdr")
    d = {k: float(out[i]) for i, k in enumerate(keys)}
    d["nui"] = nui
    return d


#: What `tglf_local` returns per species, electrons first — the same six
#: fields, in the same order, as `neo_local`'s block.  ★They are NOT the
#: same numbers: TGLF's temperature norm is the electrons', NEO's is the
#: first ion's, and NEO forces quasineutrality where TGLF does not.
TGLF_SPECIES_ROWS = tuple(n.lower() for n in _deck_names.TGLF_DECK_SPECIES)

#: What `neo_local` / `neo_inputs` return per species, electrons first.
#: ★Its own name beside the TGLF one, because a consumer that wants "NEO's
#: species row order" was spelling the six names out — `closure.py` did, and
#: so did `neo_inputs` twenty lines from the table it could have read.
NEO_SPECIES_ROWS = tuple(n.lower() for n in _deck_names.NEO_DECK_SPECIES)


_sig("fylite_rs_tglf_local", ([_ARR] + [_F64] * 4 + [_ARR] * 6 + [_U64] + [_F64] * 2 + [_I32, _ARR, _ARR]), _I32)
def tglf_local(st: dict, *, betae_scale: float = 1.0, nu_scale: float = 1.0,
               rotation: bool = False) -> dict:
    """The derived half of ``input.tglf`` — everything that is not a rename.

    The names are a lookup table and stay with the caller; these numbers
    cross normalisation boundaries (``BETAE`` against ``B_unit``, ``XNUE``
    in units of ``a/c_s``, ``Q_PRIME``/``P_PRIME`` with the total-pressure
    beta) and do not.

    The species table comes back too, under :data:`TGLF_SPECIES_ROWS`, as
    ``(n_ion + 1)``-long arrays with the electrons first.  ★It is here
    rather than with the name table because it is the half of the classic
    trap that used to be assembled by hand: TGLF references temperature to
    the ELECTRONS and NEO to the FIRST ION, the two tables are otherwise
    the same six fields over the same species, and neither map raises when
    it is handed the other one's norms.
    """
    lib = require()
    cols = _ion_columns(st["ions"])
    ns = cols["z"].size + 1
    out, sp = np.empty(27), np.empty(6 * ns)
    rc = lib.fylite_rs_tglf_local(
        surface_block(st), float(st["signb"]), float(st["signq"]),
        float(st.get("w0", 0.0)), float(st.get("w0p", 0.0)),
        cols["z"], cols["mass"], cols["ni"], cols["ti"], cols["dlnnidr"],
        cols["dlntidr"], cols["z"].size, float(betae_scale), float(nu_scale),
        1 if rotation else 0, out, sp)
    if rc != 0:
        raise KernelError(f"fylite_rs_tglf_local returned {rc}")
    keys = ("sign_bt", "sign_it", "debye", "betae", "xnue", "q_abs",
            "q_prime", "p_prime", "alpha_sa", "vexb_shear", "vpar_shear",
            "vpar")
    d = {k: float(out[i]) for i, k in enumerate(keys)}
    #: ★the geometry block, already in TGLF's units (lengths over `a`,
    #: `Q_SA` unsigned).  It comes back NAMED because `/a` is a
    #: normalisation, and a host that reproduces an upstream
    #: normalisation is the host that gets one of them wrong.
    d["geometry"] = dict(zip(TGLF_DECK_GEOMETRY,
                             (float(v) for v in out[12:27])))
    d.update({k: sp[i * ns:(i + 1) * ns].copy()
              for i, k in enumerate(TGLF_SPECIES_ROWS)})
    return d


_sig("fylite_rs_miller_boundary", [_F64] * 6 + [_U64, _ARR, _ARR], _I32)
def miller_boundary(*, r0: float, a: float, kappa: float = 1.0,
                    delta_upper: float = 0.0, delta_lower: float = 0.0,
                    z0: float = 0.0, n: int = 121):
    """The Miller-like parametric boundary, as an ``(n, 2)`` array of points.

    ★Triangularity is taken PER HALF — ``delta_upper`` on ``0 < theta < pi``,
    ``delta_lower`` elsewhere.  A single averaged delta draws a boundary a
    diverted machine does not have.

    ★★This parametrisation had THREE hosts: here, the design layer's
    ``target_boundary``, and a hand-written ``FyPhys.millerBoundary`` in the
    browser.  The browser delegates to the kernel for every function that
    has an export and hand-writes the ones that do not — so the missing
    export was the cause of the other two, not an unrelated omission.
    """
    lib = require()
    n = int(n)
    orr, ozz = np.empty(n), np.empty(n)
    rc = lib.fylite_rs_miller_boundary(
        float(r0), float(z0), float(a), float(kappa), float(delta_upper),
        float(delta_lower), n, orr, ozz)
    if rc != 0:
        raise KernelError(f"fylite_rs_miller_boundary returned {rc}")
    return np.column_stack([orr, ozz])


_sig("fylite_rs_analytic_shape", [_F64] * 4 + [_ARR, _ARR, _U64, _ARR], _I32)
def analytic_shape(r, x, *, beta0: float, emp: float, enp: float,
                   r0: float):
    """The analytic current shape ``(beta0 r/r0 + (1-beta0) r0/r)(1-x^emp)^enp``.

    Zero wherever the base has gone non-positive.  Vectorised over
    ``(r, x)``: the browser twin evaluated it once per grid node, and a
    scalar entry would pay an ABI crossing per node to remove a duplicate.
    """
    lib = require()
    r_a, x_a = _f(np.atleast_1d(r)), _f(np.atleast_1d(x))
    if r_a.size != x_a.size:
        raise KernelError("analytic_shape: r and x differ in length")
    out = np.empty(r_a.size)
    rc = lib.fylite_rs_analytic_shape(float(beta0), float(emp), float(enp),
                                      float(r0), r_a, x_a, r_a.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_analytic_shape returned {rc}")
    return out


def _grid6(g):
    """``(r0, z0, dr, dz, nr, nz)`` from a :class:`Grid` or a plain dict.

    ★Both, because the two callers hold different things: the design layer
    carries the kernel's own ``Grid``, the browser hands over a JS object
    flattened to a dict.  One reader here beats each entry choosing.
    """
    get = (lambda k: g[k]) if isinstance(g, dict) else (lambda k: getattr(g, k))
    return (float(get("r0")), float(get("z0")), float(get("dr")),
            float(get("dz")), int(get("nr")), int(get("nz")))


_sig("fylite_rs_sample_grid", [_F64] * 4 + [_U64] * 2 + [_ARR] * 3 + [_U64, _ARR], _I32)
def sample_grid(grid, f, r, z):
    """Bilinear read of a grid field at each ``(r, z)``.

    ★Out of the grid is **NaN, not a clamped edge value** — a caller that
    clamps reads the boundary node for every point beyond it, which looks
    like a field that flattens outside the vessel rather than one that was
    never measured there.  (:func:`psin_along` answers ``+inf`` instead; a
    different question, and it says so.)
    """
    lib = require()
    r_a, z_a = _f(np.atleast_1d(r)), _f(np.atleast_1d(z))
    if r_a.size != z_a.size:
        raise KernelError("sample_grid: r and z differ in length")
    out = np.empty(r_a.size)
    rc = lib.fylite_rs_sample_grid(*_grid6(grid), _f(f).ravel(), r_a, z_a,
                                   r_a.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_sample_grid returned {rc}")
    return out


_sig("fylite_rs_b_field", [_F64] * 4 + [_U64] * 2 + [_ARR] * 3 + [_U64, _ARR, _ARR], _I32)
def b_field(grid, psi, r, z):
    """Poloidal field from a psi map: ``(B_r, B_z)`` at each ``(r, z)``.

    ``B_r = -(dpsi/dz)/(2 pi r)``, ``B_z = (dpsi/dr)/(2 pi r)``, central
    differences taken at HALF the smaller cell size.  ★That step is part of
    the answer, not an implementation detail — which is why one host owns
    it rather than each caller choosing its own.
    """
    lib = require()
    r_a, z_a = _f(np.atleast_1d(r)), _f(np.atleast_1d(z))
    if r_a.size != z_a.size:
        raise KernelError("b_field: r and z differ in length")
    psi_a = _f(psi)
    obr, obz = np.empty(r_a.size), np.empty(r_a.size)
    rc = lib.fylite_rs_b_field(*_grid6(grid), psi_a.ravel(), r_a, z_a,
                               r_a.size, obr, obz)
    if rc != 0:
        raise KernelError(f"fylite_rs_b_field returned {rc}")
    return obr, obz


_sig("fylite_rs_analytic_current", [_ARR] + [_U64] * 2 + [_ARR] + [_F64] * 2 + [_ARR] + [_F64] * 7 + [_ARR], _I32)
def analytic_current(psi, r_of, mask, *, grid: dict, psi_axis: float,
                     psi_bnd: float, jc: float, beta0: float, emp: float,
                     enp: float, r0: float):
    """The analytic current over the interior cells, as ``(nr-2, nz-2)``.

    ``mask`` is a plasma mask over the grid — ★the ``plasma_mask_lim``
    this named is gone; build one from the limiter with
    :func:`fylite.device.psin_map`.  The
    normalised flux is CLAMPED to ``[0, 1]`` before the shape is evaluated;
    without that the outer cells raise a negative base to a fractional power
    and the whole distribution goes NaN at once.
    """
    lib = require()
    _, _, gdr, gdz, nr, nz = _grid6(grid)
    ncell = (nr - 2) * (nz - 2)
    #: non-zero means set — the convention `plasma_mask_lim` hands back
    m = _f(np.asarray(mask).ravel())
    if m.size != ncell:
        raise KernelError(f"analytic_current: mask is {m.size}, want {ncell}")
    out = np.empty(ncell)
    rc = lib.fylite_rs_analytic_current(
        _f(psi).ravel(), nr, nz, _f(r_of), gdr, gdz,
        m, float(psi_axis), float(psi_bnd), float(jc),
        float(beta0), float(emp), float(enp), float(r0), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_analytic_current returned {rc}")
    return out.reshape(nr - 2, nz - 2)


_sig("fylite_rs_field_sign", [_F64, _ARR], _I32)
def field_sign(torfluxa: float) -> float:
    """Which way ``B_t`` points, read off the signed toroidal flux.

    ★``sign(torfluxa)`` is the obvious spelling and it differs at exactly
    one input: this returns ``+1`` for a zero flux, where ``sign`` returns
    ``0``.  ``0`` is not an orientation — the GEO solve refuses a surface
    whose ``signb`` vanishes — and the bundle a caller holds alongside it
    was built with ``+1``.  One host, so the dict cannot disagree with
    itself.
    """
    lib = require()
    out = np.empty(1)
    rc = lib.fylite_rs_field_sign(float(torfluxa), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_field_sign returned {rc}")
    return float(out[0])


# --------------------------------------------------------------------------- #
# The TGLF port's own entries, and NEO's.
#
# ★These marshallings used to live in `fylite/tglf.py` and `fylite/neo.py`,
# which also declared their `argtypes` inline at each call site — the same
# defect `rusteq` carried: a second marshalling of one entry, in a layer
# whose job is reading a deck.  What stays on the caller's side is the DECK
# GRAMMAR (which name means which slot, and what a missing one defaults to);
# what arrives here is packed arrays.
# --------------------------------------------------------------------------- #

def _species_arrays(species, n: int):
    """The six-or-eight parallel species arrays, each truncated to ``n``."""
    return [_f(np.asarray(v, float).ravel()[:n]) for v in species]


#: ★The TGLF port's five entries are declared HERE, not inline in `tglf.py`
#: at each call site (five `argtypes` assignments re-run on every call, in a
#: layer whose job is reading a deck).  Declaring the Rust ABI is this
#: module's job — see the `dke_coll` note at the end of the file.
_sig("fylite_rs_tglf_units", [_ARR] + [_F64] * 4 + [_ARR], _I32)
def tglf_units(miller14, *, p_prime: float, q_prime: float, width: float,
               theta_trapped: float = 0.7) -> dict:
    """``{R_UNIT, Q_UNIT, B_UNIT, FT}`` of one flux surface.

    ★The caller does not have to supply these, and asking it to was a
    defect rather than a convenience: the geometry stage computes all
    four, so requiring them invited a mismatch between the numbers used to
    BUILD the matrix and the ones used to SCALE it.
    """
    lib = require()
    m = _f(np.reshape(miller14, 14))
    out = np.empty(4)
    rc = lib.fylite_rs_tglf_units(m, float(p_prime), float(q_prime),
                                  float(width), float(theta_trapped), out)
    if rc < 0:
        raise KernelError(f"fylite_rs_tglf_units returned {rc}")
    return dict(zip(("R_UNIT", "Q_UNIT", "B_UNIT", "FT"),
                    (float(v) for v in out)))


#: What `tglf_presets` refuses, and why (the messages a deck reader repeats).
TGLF_PRESET_ERRORS = {
    -51: "SAT_RULE must be 0, 1, 2 or 3",
    -52: ("NBASIS_MAX must be even and at least 2: libtglf validates this "
          "input and silently substitutes another value rather than "
          "running what was asked for"),
    -53: ("VPAR_MODEL must be 0: libtglf never transfers this input to the "
          "solver (tglf_inout.f90 calls it a deprecated switch and the "
          "assignment is commented out), so its non-zero branches cannot "
          "be reached there and a comparison would be against a different "
          "model"),
}


_sig("fylite_rs_tglf_presets", [_I32, _I32, _I32, _ARR], _I32)
def tglf_presets(*, sat_rule: int, nbasis_max: int,
                 vpar_model: int = 0) -> dict:
    """``{XNU_MODEL, WDIA_TRAPPED}`` as libtglf actually sets them, and the
    two deck validations that go with them.

    ★``USE_PRESETS`` is hardcoded ``.TRUE.`` upstream — a local variable,
    not an input — and it OVERWRITES ``xnu_model_in`` from ``sat_rule_in``.
    So a caller's ``XNU_MODEL`` is discarded by the library, and deriving
    the pair anywhere but here is how a port stops matching the library it
    is a port of.  ★★An odd ``NBASIS_MAX`` and a non-zero ``VPAR_MODEL``
    are REFUSED rather than silently corrected, because the library's own
    silence there produces a plausible growth rate it never computes
    (measured 68 % at NBASIS 3, 0.68 % at VPAR_MODEL 2).
    """
    lib = require()
    out = np.empty(2)
    rc = lib.fylite_rs_tglf_presets(int(sat_rule), int(nbasis_max),
                                    int(vpar_model), out)
    if rc != 0:
        raise KernelError(TGLF_PRESET_ERRORS.get(
            rc, f"fylite_rs_tglf_presets returned {rc}"))
    return {"XNU_MODEL": int(out[0]), "WDIA_TRAPPED": float(out[1])}


#: `tglf_linear`'s one error worth naming on this side.
TGLF_BPAR_WITHOUT_BPER = -39


_sig("fylite_rs_tglf_linear", [_ARR] * 10 + [_U64] * 4 + [_ARR], _I32)
def tglf_linear(miller18, scal25, species, *, ns: int, nbasis: int,
                nxgrid: int = 16, nmodes: int = 2) -> dict:
    """One linear TGLF solve — ``{growthrate, frequency}``, most unstable
    first.

    ``species`` is the eight parallel arrays ``(ZS, MASS, AS, TAUS, RLNS,
    RLTS, VPAR, VPAR_SHEAR)``.  The port covers the configurations the
    kernel documents; every other branch REFUSES rather than returning a
    quietly reduced answer.
    """
    lib = require()
    m = _f(np.reshape(miller18, 18))
    sc = _f(np.reshape(scal25, 25))
    arrs = _species_arrays(species, ns)
    if len(arrs) != 8:
        raise KernelError(f"tglf_linear needs 8 species arrays, got "
                          f"{len(arrs)}")
    out = np.empty(2 * int(nmodes))
    rc = lib.fylite_rs_tglf_linear(m, sc, *arrs, ns, int(nbasis),
                                   int(nxgrid), int(nmodes), out)
    if rc == TGLF_BPAR_WITHOUT_BPER:
        #: ★USE_BPAR without USE_BPER is a silent NO-OP in libtglf: it runs
        #: and returns the electrostatic answer, with a dispersion matrix
        #: bit-identical to both-flags-off.  Refused rather than
        #: reproduced — handing back an electrostatic growth rate under a
        #: USE_BPAR deck is the failure mode this and the preset guards
        #: all share.
        raise KernelError(
            "USE_BPAR requires USE_BPER: libtglf accepts the combination "
            "but ignores USE_BPAR entirely, returning the electrostatic "
            "result; set USE_BPER as well, or drop USE_BPAR to ask for "
            "the electrostatic case deliberately")
    if rc < 0:
        raise KernelError(f"fylite_rs_tglf_linear returned {rc}")
    got = out[:2 * rc]
    return {"growthrate": list(got[0::2]), "frequency": list(got[1::2])}


_sig("fylite_rs_tglf_matrices", ([_ARR] * 10 + [_U64] * 3 + [_I32, ctypes.c_void_p, ctypes.c_void_p, _U64]), _I32)
def tglf_matrices(miller18, scal25, species, *, ns: int, nbasis: int,
                  nxgrid: int = 16) -> dict:
    """The ``A`` and ``B`` matrices of one linear solve — ``{rust, n}``.

    The assembly exposed independently of the eigensolve, so "is the
    MATRIX wrong or is the SOLVE wrong" stays two questions.
    """
    lib = require()
    m = _f(np.reshape(miller18, 18))
    sc = _f(np.reshape(scal25, 25))
    arrs = _species_arrays(species, ns)
    n = lib.fylite_rs_tglf_matrices(m, sc, *arrs, ns, int(nbasis),
                                    int(nxgrid), 0, None, None, 0)
    if n < 0:
        raise KernelError(f"fylite_rs_tglf_matrices sizing returned {n}")

    def one(which):
        re, im = np.empty(n * n), np.empty(n * n)
        rc = lib.fylite_rs_tglf_matrices(
            m, sc, *arrs, ns, int(nbasis), int(nxgrid), which,
            re.ctypes.data, im.ctypes.data, n)
        if rc < 0:
            raise KernelError(f"fylite_rs_tglf_matrices returned {rc}")
        return (re + 1j * im).reshape(n, n)

    return {"rust": (one(0), one(1)), "n": n}


_sig("fylite_rs_tglf_dlnpdr", [_ARR] * 4 + [_U64, _F64, _F64, _ARR], _I32)
def tglf_dlnpdr(species, *, ns: int, rmaj: float,
                rlnp_cutoff: float = 18.0) -> float:
    """The normalised pressure-gradient scale ``dlnpdr`` — ``species`` is
    ``(AS, TAUS, RLNS, RLTS)``.

    ★Clamped at BOTH ends by the model — never below 4, never above
    ``rlnp_cutoff`` — and the lower clamp is part of the model rather than
    a guard: a flat-pressure case really does reach it.  It sets
    SAT_RULE 2's overall normalisation, so a caller deriving it beside the
    flux call is a second version of a clamped model constant.
    """
    lib = require()
    arrs = _species_arrays(species, ns)
    if len(arrs) != 4:
        raise KernelError(f"tglf_dlnpdr needs 4 species arrays, got "
                          f"{len(arrs)}")
    out = np.empty(1)
    rc = lib.fylite_rs_tglf_dlnpdr(*arrs, ns, float(rmaj),
                                   float(rlnp_cutoff), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_tglf_dlnpdr returned {rc}")
    return float(out[0])


_sig("fylite_rs_tglf_kygrid",
     ([_ARR] * 4 + [_U64, _I32, _U64] + [_F64] * 2 + [_I32, _U64, _ARR]), _I32)
def tglf_kygrid(species, *, ns: int, kygrid_model: int = 1, nky: int = 12,
                ky: float = 0.3, ky_factor: float = 1.0,
                use_ave_ion_grid: bool = False,
                max_n: int = 128) -> dict:
    """The ky spectrum a ``KYGRID_MODEL`` implies, and its gyroradii.

    ``species`` is ``(ZS, MASS, AS, TAUS)``.  ★Model 1 — the default — is
    nine linear points to ``k_θ ρ_ion = 0.9`` followed by ``NKY``
    LOGARITHMIC points out to ``k_θ ρ_e = 0.4``, which is not a grid
    anyone writes down by hand; that is why it is an entry rather than a
    caller's table.

    ★★``use_ave_ion_grid`` decides WHICH ion sets ``ρ_ion``, and its
    default is upstream's: **False**, meaning the FIRST ion alone.  True
    is the charge-weighted average over ions above a tenth of the
    electron charge density.  The two coincide whenever there is one ion,
    or when every impurity is below that cut — which is why this was
    ported as the average only, and went unnoticed until upstream's
    kinetic-carbon case (``rho_ion`` 0.644949 against 1.0, every ky out
    by 1.55).  ★``ρ_ion`` feeds the SATURATION as well as the grid.
    """
    lib = require()
    arrs = _species_arrays(species, ns)
    if len(arrs) != 4:
        raise KernelError(f"tglf_kygrid needs 4 species arrays, got "
                          f"{len(arrs)}")
    out = np.empty(2 * int(max_n) + 2)
    rc = lib.fylite_rs_tglf_kygrid(*arrs, ns, int(kygrid_model), int(nky),
                                   float(ky), float(ky_factor),
                                   int(bool(use_ave_ion_grid)), int(max_n),
                                   out)
    if rc < 0:
        raise KernelError(f"fylite_rs_tglf_kygrid returned {rc}")
    return {"ky": list(out[:rc]), "dky": list(out[max_n:max_n + rc]),
            "rho_ion": float(out[2 * max_n]),
            "rho_e": float(out[2 * max_n + 1])}


_sig("fylite_rs_tglf_flux", ([_ARR] * 11 + [_U64, _ARR] + [_U64] * 3 + [_I32, _ARR]), _I32)
def tglf_flux(miller18, scal32, geom4, species, ky, *, ns: int, nbasis: int,
              nxgrid: int = 16, sat_rule: int = 1) -> dict:
    """The whole quasilinear chain: a linear solve per ``ky``, the
    zonal-flow saturation, and ``flux = intensity × weight`` integrated
    over the spectrum.
    """
    lib = require()
    m = _f(np.reshape(miller18, 18))
    sc = _f(np.reshape(scal32, 32))
    gm = _f(np.reshape(geom4, 4))
    arrs = _species_arrays(species, ns)
    ky_a = _f(np.atleast_1d(ky))
    out = np.empty(3 * ns + 2 * ky_a.size)
    rc = lib.fylite_rs_tglf_flux(m, sc, gm, *arrs, ns, ky_a, ky_a.size,
                                 int(nbasis), int(nxgrid), int(sat_rule),
                                 out)
    if rc < 0:
        raise KernelError(f"fylite_rs_tglf_flux returned {rc}")
    return {"particle": list(out[:ns]), "energy": list(out[ns:2 * ns]),
            "exchange": list(out[2 * ns:3 * ns]),
            "growthrate": list(out[3 * ns::2]),
            "frequency": list(out[3 * ns + 1::2])}


_sig("fylite_rs_tglf_flux_searched",
     ([_ARR] * 11 + [_U64, _ARR] + [_U64] * 3 + [_I32, _ARR, _ARR]), _I32)
def tglf_flux_searched(miller18, scal32, geom4, species, ky, *, ns: int,
                       nbasis: int, nxgrid: int = 16, sat_rule: int = 1,
                       width_min: float = 0.3, nwidth: int = 21,
                       use_bisection: bool = True,
                       nbasis_min: int = 2, nmodes: int = 1) -> dict:
    """:func:`tglf_flux` with the mode width SEARCHED at every ``ky``.

    Returns the two stress channels as well — ``stress_tor`` is the
    turbulent TOROIDAL momentum flux, the drive a momentum channel needs.

    The deck's ``WIDTH`` becomes the upper bound of a log-uniform scan
    down to ``width_min``; the scan runs at ``nbasis_min`` and, for
    saturation rules 2 and 3, with the magnetic branches off, exactly as
    upstream's own search does.  ``nwidth=0`` turns the search OFF (run at
    the deck's width), which is how a caller asks for several modes
    without also asking for a search; ``nmodes`` is upstream's ``NMODES``
    — its own default is 2, this port's is 1 (see the flux docs).  ★The trapped fraction is re-derived at
    every probe width inside the kernel — ``FT`` is width-weighted, so a
    scan that carried the caller's value would be searching one plasma
    and reporting another.
    """
    lib = require()
    m = _f(np.reshape(miller18, 18))
    sc = _f(np.reshape(scal32, 32))
    gm = _f(np.reshape(geom4, 4))
    arrs = _species_arrays(species, ns)
    ky_a = _f(np.atleast_1d(ky))
    search = _f(np.array([float(width_min), float(nwidth),
                          1.0 if use_bisection else 0.0, float(nbasis_min),
                          float(nmodes)]))
    out = np.empty(5 * ns + 2 * ky_a.size)
    rc = lib.fylite_rs_tglf_flux_searched(m, sc, gm, *arrs, ns, ky_a,
                                          ky_a.size, int(nbasis),
                                          int(nxgrid), int(sat_rule),
                                          search, out)
    if rc < 0:
        raise KernelError(f"fylite_rs_tglf_flux_searched returned {rc}")
    return {"particle": list(out[:ns]), "energy": list(out[ns:2 * ns]),
            "exchange": list(out[2 * ns:3 * ns]),
            "stress_tor": list(out[3 * ns:4 * ns]),
            "stress_par": list(out[4 * ns:5 * ns]),
            "growthrate": list(out[5 * ns::2]),
            "frequency": list(out[5 * ns + 1::2])}


_sig("fylite_rs_neo_gyrobohm", [_F64] * 3 + [_ARR], _I32)
def neo_gyrobohm(dens_1, temp_1, rho_star) -> dict:
    """NEO's OWN gyro-Bohm normalisers — ``{pflux, eflux, mflux}``.

    ★Not :func:`gyrobohm`, which is the electron-referenced set a flux
    MATCH happens in.  These are the reference set NEO returns its fluxes
    in, so dividing by them is the step that makes a NEO number and a TGLF
    number comparable at all — and the three exponents are the whole
    content, which is why they are not written down twice.
    """
    lib = require()
    out = np.empty(3)
    rc = lib.fylite_rs_neo_gyrobohm(float(dens_1), float(temp_1),
                                    float(rho_star), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_neo_gyrobohm returned {rc}")
    return {"pflux": float(out[0]), "eflux": float(out[1]),
            "mflux": float(out[2])}


def neo_current_unit(*, ne: float, ti1: float, b_unit: float) -> float:
    """NEO's normaliser for the CURRENT it returns [A·T/m²].

    ``<j·B> = jpar_neo * neo_current_unit(...)``, and the DD's
    ``core_sources`` ``j_parallel`` is that over ``B0``.

    SI in: ``ne`` [m⁻³] is NEO's density norm (the ELECTRONS'), ``ti1`` [eV]
    its temperature norm (the FIRST ION's — the two norms are different and
    swapping them rescales the answer with nothing raising), ``b_unit`` [T].

    ★★The flux normalisers (:func:`neo_gyrobohm`) were exported and this one
    was not, so a host holding NEO's ``jpar`` had nothing to multiply by —
    and :func:`fylite.fyo.neoclassical_source` put the NORMALISED number
    into an IMAS field whose unit is A/m², beside a second backend that put
    A/m² there.  Eight orders apart, chosen by a keyword.

    ★``jpar`` is exactly LINEAR in ``rho_star``, so a caller using this unit
    must hand the solve the physical ``rho_s/a``.  :func:`neo_local`'s
    default of 1e-3 is for callers that only want a shape; with this unit it
    is a current wrong by the ratio, which on a typical surface is a factor
    of three and looks entirely ordinary.
    """
    lib = require()
    fn = lib.fylite_rs_neo_current_unit
    fn.restype = ctypes.c_double
    fn.argtypes = [_F64, _F64, _F64]
    return float(fn(float(ne), float(ti1), float(b_unit)))


#: The `neo_sauter` coefficient vintages.
SAUTER_1999, REDL_2021 = 0, 1

#: `neo_sauter`'s vintage for the Hirshman-Sigmar analytic fluxes.  It
#: returns `pflux` then `eflux`, `ns` each — a different shape from the
#: current vintages, which is why it has a name here rather than a 4.
HIRSHMAN_SIGMAR_VINTAGE = 4


# the trailing i32 before `out` is the coefficient vintage
# (0 = Sauter 1999, 1 = Redl 2021)
def neo_geo14(geometry: dict, *, n_theta: int = 17):
    """``geo14`` for :func:`neo_sauter` / :func:`dke_solve`, in the SLOT order.

    ★★Built from :data:`NEO_SAUTER_SLOTS`, never by hand.  That block shares
    its vocabulary with the NEO deck and differs in sequence — ``Q`` and
    ``SHEAR`` are slots 2 and 3 here and 4 and 5 in the deck.  Packing a deck
    in the block's place produced fluxes 200x out, and it read as a physics
    disagreement rather than a transposition: every value finite, ordered and
    plausible.

    ``geometry`` is what :func:`neo_local` returns under that key (deck
    names); missing slots are zero, and ``N_THETA`` comes from the argument
    because it is a resolution knob rather than geometry.
    """
    g = dict(geometry)
    g.setdefault("N_THETA", float(n_theta))
    return _f([float(g.get(name, 0.0)) for name in NEO_SAUTER_SLOTS])


_sig("fylite_rs_neo_sauter", ([_ARR] * 6 + [_U64, _ARR] + [_F64] * 4 + [_I32, _I32, _I32, _ARR]), _I32)
def neo_sauter(species, geo14, *, nu_1: float, rho_star: float = 0.001,
               dphi0dr: float = 0.0, epar0: float = 0.0, ipccw: int = -1,
               btccw: int = -1, vintage: int = SAUTER_1999):
    """NEO's ANALYTIC neoclassical currents on one surface — six values
    ``[jpar, jtor, kpar, uparB, ftrap, i_div_psip]``.

    ``vintage`` picks the coefficient set: :data:`SAUTER_1999` or
    :data:`REDL_2021` (NEO's ``compute_Sauter_mod``).  ★The two are
    separate solves of the same geometry, which is what makes comparing
    them apples-to-apples.
    """
    lib = require()
    arrs = _species_arrays(species, len(np.asarray(species[0]).ravel()))
    ns = arrs[0].size
    g = _f(np.reshape(geo14, 14))
    out = np.empty(6)
    rc = lib.fylite_rs_neo_sauter(*arrs, ns, g, float(nu_1),
                                  float(rho_star), float(dphi0dr),
                                  float(epar0), int(ipccw), int(btccw),
                                  int(vintage), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_neo_sauter returned {rc}")
    return out


# the drift-kinetic solve: species arrays, 13 Miller parameters, the
# three grid sizes, then nu_1 / rho_star / dphi0dr / epar0
_sig("fylite_rs_dke_solve", ([_ARR] * 6 + [_U64, _ARR] + [_U64] * 3 + [_F64] * 4 + [_ARR, _U64]), _I32)
def dke_solve(species, geo13, *, n_energy: int, n_xi: int, n_theta: int,
              nu_1: float, rho_star: float = 0.001, dphi0dr: float = 0.0,
              epar0: float = 0.0) -> dict:
    """NEO's DRIFT-KINETIC solve on one surface.

    Returns ``{jpar_dke, jtor_dke, pflux, eflux, vpol_th0, vtor_th0}`` —
    the per-species flux and flow moments alongside the two currents.
    """
    lib = require()
    arrs = _species_arrays(species, len(np.asarray(species[0]).ravel()))
    ns = arrs[0].size
    g = _f(np.reshape(geo13, 13))
    out = np.empty(2 + 4 * ns)
    rc = lib.fylite_rs_dke_solve(*arrs, ns, g, int(n_energy), int(n_xi),
                                 int(n_theta), float(nu_1), float(rho_star),
                                 float(dphi0dr), float(epar0), out,
                                 out.size)
    if rc != 0:
        raise KernelError(f"fylite_rs_dke_solve returned {rc}")
    per = {k: list(out[2 + i * ns:2 + (i + 1) * ns])
           for i, k in enumerate(("pflux", "eflux", "vpol_th0", "vtor_th0"))}
    return {"jpar_dke": float(out[0]), "jtor_dke": float(out[1]), **per}


_sig("fylite_rs_neo_inputs", ([_ARR] + [_F64] * 4 + [_ARR] * 6 + [_U64, _ARR]), _I32)
def neo_local(st: dict, *, rho_star: float = 0.001) -> dict:
    """One surface's NEO species block, ``nu_1``, the two orientations and
    the rotation pair.

    ★NEO normalises temperature to the FIRST ION's, density to the
    electrons', mass to deuterium.  Getting any of the three wrong rescales
    every NEO output and nothing raises — which is why the normalisation is
    the kernel's and this returns numbers rather than a recipe.
    """
    lib = require()
    cols = _ion_columns(st["ions"])
    nion = cols["z"].size
    ns = nion + 1
    out = np.empty(6 * ns + 18)
    rc = lib.fylite_rs_neo_inputs(
        surface_block(st), float(st["signb"]), float(st["signq"]),
        float(st.get("w0", 0.0)), float(st.get("w0p", 0.0)),
        cols["z"], cols["mass"], cols["ni"], cols["ti"], cols["dlnnidr"],
        cols["dlntidr"], nion, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_neo_inputs returned {rc}")
    #: ★from the generated table, lowercased — not spelled again.  The
    #: block is unpacked BY POSITION out of one flat buffer below, so
    #: this tuple is a positional contract and a copy of it is a place
    #: for two names to swap with nothing able to notice.
    names = NEO_SPECIES_ROWS
    d = {k: out[i * ns:(i + 1) * ns].copy() for i, k in enumerate(names)}
    d.update(nu_1=float(out[6 * ns]), ipccw=float(out[6 * ns + 1]),
             btccw=float(out[6 * ns + 2]),
             omega_rot=float(out[6 * ns + 3]),
             omega_rot_deriv=float(out[6 * ns + 4]))
    #: ★the geometry block, already in NEO's units (lengths over `a`, `q`
    #: unsigned).  It comes back from the kernel rather than being rebuilt
    #: here because `/a` and `abs(q)` are normalisations, and the host that
    #: reproduces a normalisation is the host that gets one of them wrong —
    #: `NU_1` was 58x to 80x out for exactly that reason.
    d["geometry"] = dict(zip(NEO_DECK_GEOMETRY,
                             (float(v) for v in out[6 * ns + 5:6 * ns + 18])))
    return d


_sig("fylite_rs_trapped_fraction_eps", [_ARR, _U64, _ARR], _I32)
def trapped_fraction_eps(eps):
    """Effective trapped fraction from the inverse aspect ratio (Lin-Liu &
    Miller 1995).

    The circular-geometry closed form, NOT the trapped fraction averaged
    from a real |B| over a real surface — the solver path computes that one
    and the two are different quantities.
    """
    lib = require()
    eps = _f(np.atleast_1d(eps))
    out = np.empty(eps.size)
    rc = lib.fylite_rs_trapped_fraction_eps(eps, eps.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_trapped_fraction_eps returned {rc}")
    return out


_sig("fylite_rs_redl_coefficients", [_ARR] * 4 + [_U64, _ARR], _I32)
def redl_coefficients(ft, zeff, nu_e_star=0.0, nu_i_star=0.0) -> dict:
    r"""Redl-2021 ``L31``/``L32``/``L34``/``alpha`` (the analytic model).

    ★Not what the NEO-lineage solver branch computes: the two differ in
    ``L34`` off the collisionless axis (4.1 % at ν\* = 0.1, 15.7 % at
    ν\* = 1).  Both live in ``neoclassical.rs``, named apart, with the note
    that says which upstream each follows.
    """
    ft, zeff, nue, nui = np.broadcast_arrays(
        *[np.asarray(a, float) for a in (ft, zeff, nu_e_star, nu_i_star)])
    shape = ft.shape
    ft, zeff, nue, nui = (_f(a).ravel() for a in (ft, zeff, nue, nui))
    lib = require()
    out = np.empty(4 * ft.size)
    rc = lib.fylite_rs_redl_coefficients(ft, zeff, nue, nui, ft.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_redl_coefficients returned {rc}")
    rows = out.reshape(-1, 4)
    keys = ("L31", "L32", "L34", "alpha")
    return {k: rows[:, i].reshape(shape) if shape else float(rows[0, i])
            for i, k in enumerate(keys)}


# the analytic Redl-2021 bootstrap model (NOT the solver's branch —
# see the note in neoclassical.rs on the two L34s)
_sig("fylite_rs_redl_bootstrap", ([_U64] + [_ARR] * 10 + [_F64] * 3 + [_I32, _ARR]), _I32)
def redl_bootstrap(*, eps, q_abs, ne, te, ti, ni, zeff, p_th, i_psi, psi_bar,
                   r_maj: float, b0: float, z_ion: float = 1.0,
                   collisionless: bool = False) -> dict:
    """The Redl-2021 analytic bootstrap profile on a caller-chosen ladder.

    Every profile is per surface; ``psi_bar`` is ψ PER RADIAN [Wb/rad], the
    normalisation the coefficients are written in.  Returns ``j_bs``
    (``|⟨j·B⟩|/B0`` [A/m²]) plus the coefficients, ``ft`` and the
    collisionalities it used — so a caller can see what drove the answer
    rather than only the answer.
    """
    lib = require()
    args = [_f(a) for a in (eps, q_abs, ne, te, ti, ni, zeff, p_th, i_psi,
                            psi_bar)]
    n = args[0].size
    if any(a.size != n for a in args):
        raise KernelError("every profile must be the same length")
    out = np.empty(8 * n)
    rc = lib.fylite_rs_redl_bootstrap(n, *args, float(r_maj), float(b0),
                                      float(z_ion), 1 if collisionless else 0,
                                      out)
    if rc != 0:
        raise KernelError(f"fylite_rs_redl_bootstrap returned {rc}")
    rows = out.reshape(n, 8)
    keys = ("j_bs", "L31", "L32", "L34", "alpha", "ft", "nu_e_star",
            "nu_i_star")
    return {k: rows[:, i].copy() for i, k in enumerate(keys)}


_sig("fylite_rs_li3", ([_F64] * 4 + [_U64] * 2 + [_ARR] + [_F64] * 4 + [_ARR]), _I32)
def li3(grid: Grid, psi, *, psi_axis: float, psi_bnd: float, ip: float,
        r0: float) -> float:
    """Internal inductance ``li(3)`` from the ψ map (FULL flux [Wb]).

    No contouring: the plasma is the cells with 0 ≤ ψ_N ≤ 1.  That is the
    point of having it beside the traced ladder — the two answers to "where
    is the plasma" fail differently.
    """
    lib = require()
    psi = _f(psi)
    if psi.shape != (grid.nr, grid.nz):
        raise KernelError(f"psi has shape {psi.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    out = np.empty(1)
    rc = lib.fylite_rs_li3(*grid.args, psi.ravel(), float(psi_axis),
                           float(psi_bnd), float(ip), float(r0), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_li3 returned {rc}")
    return float(out[0])


_sig("fylite_rs_profile_shape_fit", [_ARR, _ARR, _U64, _ARR], _I32)
def profile_shape_fit(x, y) -> dict:
    """Fit the analytic family ``(1 − x^a)^b`` to a normalised profile.

    Returns ``{"a", "b", "residual"}``.  Raises when the iteration does not
    settle: a shape outside the family must not come back as the nearest
    member of it.
    """
    lib = require()
    x, y = _f(x), _f(y)
    if x.size != y.size:
        raise KernelError("x and y must be the same length")
    out = np.empty(3)
    rc = lib.fylite_rs_profile_shape_fit(x, y, x.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_profile_shape_fit returned {rc}"
                          + (" — the fit did not settle" if rc == -2 else ""))
    return {"a": float(out[0]), "b": float(out[1]), "residual": float(out[2])}


_sig("fylite_rs_gfile_profile", [_ARR, _ARR, _U64, _F64, _ARR], _I32)
def gfile_profile(pprime, ffprim, *, rcentr: float) -> dict:
    """This code's analytic profile parameters, extracted from an EFIT
    forward g-file: ``{beta0, emp, enp, shape_residual}``.

    ★The amplitude is an IDENTITY, not a calibration: the R-weight split
    is the same in both codes — ``beta_eff`` from ``μ₀R₀²p′/FF′`` equals
    EFIT's BETAP0 to machine precision at every x and every scan point.
    The whole difference between the codes was always the SHAPE.

    ★★The shape is an EXTRACTION, not an approximation: a g-file's profile
    is exactly of the family ``(1-xᵃ)ᵇ`` (residual ~1e-9), with ``b`` the
    k-file EMP and ``a`` drifting with ``(betap0, emp, enp)`` in a way that
    resisted a closed form — so it is fitted per case rather than
    tabulated.  Raises when the fit does not settle or the profile carries
    no on-axis normalisation: a shape that is not of the family must not
    come back as the nearest member of it.
    """
    lib = require()
    pp, ff = _f(np.atleast_1d(pprime)), _f(np.atleast_1d(ffprim))
    if ff.size != pp.size:
        raise KernelError(f"pprime has {pp.size} points, ffprim {ff.size}")
    out = np.empty(4)
    rc = lib.fylite_rs_gfile_profile(pp, ff, pp.size, float(rcentr), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_gfile_profile returned {rc}")
    return {"beta0": float(out[0]), "emp": float(out[1]),
            "enp": float(out[2]), "shape_residual": float(out[3])}


_sig("fylite_rs_sample", ([_F64] * 4 + [_U64] * 2 + [_ARR, _ARR, _ARR, _U64, _I32, _ARR]), _I32)
def sample(grid: Grid, f, r, z, *, gradient_magnitude: bool = False):
    """Bilinear samples of a grid field (NaN outside the box).

    ``gradient_magnitude`` samples ``|∇f|`` on the kernel's half-cell
    stencil — the same one every flux-surface average uses.
    """
    lib = require()
    f = _f(f)
    if f.shape != (grid.nr, grid.nz):
        raise KernelError(f"field has shape {f.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    r, z = _f(np.atleast_1d(r)), _f(np.atleast_1d(z))
    if r.size != z.size:
        raise KernelError("r and z must be the same length")
    out = np.empty(r.size)
    rc = lib.fylite_rs_sample(*grid.args, f.ravel(), r, z, r.size,
                              1 if gradient_magnitude else 0, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_sample returned {rc}")
    return out


_sig("fylite_rs_ray_level", ([_F64] * 4 + [_U64] * 2 + [_ARR] + [_F64] * 6 + [_U64, _ARR]), _I32)
def ray_level(grid: Grid, f, level, *, start, direction, span: float,
              n_step: int = 400) -> float:
    """Distance from ``start`` along ``direction`` to the ``level`` set.

    NaN when the ray leaves the box without crossing.  ★A gap, an isoflux
    distance and a boundary point at a given angle are all this one
    question; each caller answering it on its own stencil is how a boundary
    comes to move differently in two places on the same equilibrium.
    """
    lib = require()
    f = _f(f)
    if f.shape != (grid.nr, grid.nz):
        raise KernelError(f"field has shape {f.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    out = np.empty(1)
    rc = lib.fylite_rs_ray_level(*grid.args, f.ravel(), float(level),
                                 float(start[0]), float(start[1]),
                                 float(direction[0]), float(direction[1]),
                                 float(span), int(n_step), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_ray_level returned {rc}")
    return float(out[0])


_sig("fylite_rs_direct_integrals", ( [_F64] * 4 + [_U64] * 2 + [_ARR, _ARR, _U64, _ARR, _ARR, _U64, _ARR, _U64, _ARR, _ARR]), _I32)
def direct_integrals(grid: Grid, psin2d, *, f_table, boundary=None,
                     levels) -> dict:
    """``V(ψ_N)`` and ``Φ(ψ_N)`` by grid quadrature — the independent second
    path to what :func:`equilibrium_ladder` integrates along contours.

    ``boundary`` is ``(r, z)`` of the last closed surface; without it the
    containment test is skipped, which is only safe well inside it.
    """
    lib = require()
    psin2d = _f(psin2d)
    if psin2d.shape != (grid.nr, grid.nz):
        raise KernelError(f"psin2d has shape {psin2d.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    fp, lv = _f(f_table), _f(levels)
    if boundary is None:
        br = bz = np.zeros(0)
    else:
        br, bz = _f(boundary[0]), _f(boundary[1])
    v, phi = np.empty(lv.size), np.empty(lv.size)
    rc = lib.fylite_rs_direct_integrals(
        *grid.args, psin2d.ravel(), fp, fp.size, br, bz, br.size,
        lv, lv.size, v, phi)
    if rc != 0:
        raise KernelError(f"fylite_rs_direct_integrals returned {rc}")
    return {"volume": v, "phi": phi}


_sig("fylite_rs_contour", [_F64, _F64, _F64, _F64, _U64, _U64, _ARR, _F64, _U64, _ARR], _I32)
def contour(grid: Grid, f, level, *, max_seg: int = 4096) -> np.ndarray:
    """Marching-squares contour segments of ``f`` at ``level``.

    Returns ``(n, 4)`` — one row per segment, ``[r1, z1, r2, z2]``.  Segment
    soup, not an ordered polygon: ordering is a decision (which branch, which
    direction) and :func:`trace_surface` is the entry that makes it.
    """
    lib = require()
    f = _f(f)
    if f.shape != (grid.nr, grid.nz):
        raise KernelError(f"field has shape {f.shape}, expected "
                          f"{(grid.nr, grid.nz)} (R-major)")
    out = np.empty(4 * int(max_seg))
    rc = lib.fylite_rs_contour(*grid.args, f.ravel(), float(level),
                               int(max_seg), out)
    if rc < 0:
        raise KernelError(f"fylite_rs_contour returned {rc}")
    return out[:4 * rc].reshape(rc, 4)


_sig("fylite_rs_shape_metrics", [_ARR, _U64, _ARR], _I32)
def shape_metrics(poly) -> dict:
    """``R0 / Z0 / a / kappa / delta_upper / delta_lower`` of a boundary.

    ★Triangularity per half.  A single delta cannot describe most diverted
    shapes and averaging the two draws a boundary the machine does not have.

    ★``z0`` is the boundary's vertical CENTRE, and it is not the magnetic
    axis height: the two differ by the Shafranov shift, and a design that
    compared a requested Z0 against an axis position would be reading a
    drift where there is none (and missing one where there is).
    """
    lib = require()
    p = _f(poly)
    if p.ndim != 2 or p.shape[1] != 2:
        raise KernelError("polygon must be (n, 2) of (R, Z)")
    out = np.empty(6)
    rc = lib.fylite_rs_shape_metrics(p.ravel(), p.shape[0], out)
    if rc != 0:
        raise KernelError(f"fylite_rs_shape_metrics returned {rc}")
    return {"r0": out[0], "a": out[1], "kappa": out[2],
            "delta_upper": out[3], "delta_lower": out[4], "z0": out[5]}


_sig("fylite_rs_enclosed_volume", [_ARR, _U64, _ARR], _I32)
def enclosed_volume(poly) -> float:
    """Volume [m³] the boundary polygon encloses (Pappus on the centroid)."""
    lib = require()
    p = _f(poly)
    out = np.empty(1)
    rc = lib.fylite_rs_enclosed_volume(p.ravel(), p.shape[0], out)
    if rc != 0:
        raise KernelError(f"fylite_rs_enclosed_volume returned {rc}")
    return float(out[0])


# --------------------------------------------------------------------------- #
# least squares (linalg.rs)
# --------------------------------------------------------------------------- #
_sig("fylite_rs_ridge_lstsq", [_ARR, _ARR, _ARR, _U64, _U64, _ARR, _ARR], _I32)
def ridge_lstsq(a, b, w, lam) -> np.ndarray:
    """Weighted ridge least squares; raises if the normal matrix is not PD.

    ``lam`` is per-column, so the caller can regularise channels differently
    — and a non-positive-definite system is an error, not a fallback that
    answers anyway.
    """
    lib = require()
    a, b, w, lam = _f(a), _f(b), _f(w), _f(lam)
    nrow, ncol = a.shape
    out = np.empty(ncol)
    rc = lib.fylite_rs_ridge_lstsq(a.ravel(), b, w, nrow, ncol, lam, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_ridge_lstsq returned {rc}")
    return out


#: `lo`/`hi` are optional in the ABI (both or neither), so they are
#: declared as void pointers: `None` is then a legal argument instead of
#: a box the caller has to invent for an unbounded solve.
_sig("fylite_rs_bounded_lstsq", [_ARR, _ARR, _U64, _U64, _VOID, _VOID, _U64, _F64, _ARR], _I32)
def bounded_lstsq(a, b, lo=None, hi=None, *, n_iter: int = 4000,
                  tol: float = 1e-12):
    """Box-constrained least squares.  Returns ``(x, iterations)``.

    Both bounds or neither — a one-sided box is a different problem and
    guessing which side was meant is not this layer's business.
    """
    lib = require()
    a, b = _f(a), _f(b)
    nrow, ncol = a.shape
    if (lo is None) != (hi is None):
        raise KernelError("give both bounds or neither")
    lo_a = None if lo is None else _f(lo)
    hi_a = None if hi is None else _f(hi)
    out = np.empty(ncol)
    rc = lib.fylite_rs_bounded_lstsq(
        a.ravel(), b, nrow, ncol,
        None if lo_a is None else lo_a.ctypes.data,
        None if hi_a is None else hi_a.ctypes.data,
        int(n_iter), float(tol), out)
    if rc < 0:
        raise KernelError(f"fylite_rs_bounded_lstsq returned {rc}")
    return out, int(rc)


# --------------------------------------------------------------------------- #
# profile fitting (fitting.rs)
# --------------------------------------------------------------------------- #
_sig("fylite_rs_profile_fit", [_ARR, _ARR, _ARR, _U64, _U64, _ARR, _ARR, _ARR], _I32)
def profile_fit(x, y, sigma, *, max_order: int = 6) -> dict:
    """Shifted-Legendre profile fit with GCV order selection.

    Returns the chosen coefficients and order, the GCV sweep over every
    order tried, and the fit statistics.  ★The GCV score measures IN-SAMPLE
    prediction only: it says nothing about the extrapolated edge, which is
    where a profile fit is most often read and least constrained.
    """
    lib = require()
    x, y, sg = _f(x), _f(y), _f(sigma)
    mo = int(max_order)
    coef = np.empty(mo + 1)
    sweep = np.empty(mo + 1)
    info = np.empty(3)
    rc = lib.fylite_rs_profile_fit(x, y, sg, x.size, mo, coef, sweep, info)
    if rc < 0:
        raise KernelError(f"fylite_rs_profile_fit returned {rc}")
    return {"coef": coef[:int(info[0]) + 1], "order": int(info[0]),
            "gcv_sweep": sweep, "rss": float(info[1]),
            "chi2_per_dof": float(info[2])}


_sig("fylite_rs_profile_sample", [_ARR, _U64, _ARR, _U64, _ARR], _I32)
def profile_sample(coef, x) -> np.ndarray:
    """Evaluate a :func:`profile_fit` coefficient vector at ``x``."""
    lib = require()
    coef, x = _f(coef), _f(x)
    out = np.empty(x.size)
    rc = lib.fylite_rs_profile_sample(coef, coef.size, x, x.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_profile_sample returned {rc}")
    return out


# --------------------------------------------------------------------------- #
# breakdown null design (breakdown.rs)
# --------------------------------------------------------------------------- #
#: The order `bundle_derive` writes its 21 scalar rows in.
BUNDLE_ROWS = ("b_unit", "s", "drmaj", "dzmag", "skappa", "sdelta", "szeta",
               "dlnnedr", "dlntedr", "w0p", "volp", "vol", "surf",
               "ave_grad_r", "grad_r0", "bp2", "bt2", "bt0", "bp0",
               "cs", "rhos")
#: ...and the six gyro-Bohm rows that follow them.
GYROBOHM_ROWS = ("rho_star", "chi_gb", "gamma_gb", "q_gb", "pi_gb", "s_gb")
#: The MXH harmonics `bundle_derive` takes and shears, in row order.
MXH_HARMONICS = ("cos0", "cos1", "cos2", "cos3", "cos4", "cos5", "cos6",
                 "sin3", "sin4", "sin5", "sin6")


#: Electron mass in units of the deuteron mass — the ratio NEO's species
#: list is written in.
M_ELECTRON_OVER_MD = 2.724437e-4


_sig("fylite_rs_redl_drive", [_ARR] * 5 + [_U64, _F64, _F64, _ARR], _I32)
def redl_drive(ne, te, ni, ti, psin, *, psi_axis: float, psi_bnd: float):
    """What drives the Redl bootstrap: ``(p_thermal [Pa], psi_bar)``.

    ★★``p = (n_e T_e + n_i T_i) e`` keeps the pressure GRADIENT, the
    collisionality and the L-coefficients on ONE profile set.  A
    reconstruction's own ``pres`` is the other choice and is not equivalent:
    a magnetics-only fit routinely returns a non-physical outer pressure,
    and flooring it would zero ``dP/dψ`` over the whole outer half —
    deleting the dominant ``L31·∇p`` term and moving the ``j_bs`` peak
    inward.  That case is raised by the caller, never floored, which is why
    only the kinetic form is built here.

    ★``psi_bar`` is flux PER RADIAN, which is what the coefficients are
    written in; the per-turn value scales every gradient term by 2π.
    """
    lib = require()
    a = [_f(np.atleast_1d(x)) for x in (ne, te, ni, ti, psin)]
    n = a[0].size
    out = np.empty(2 * n)
    rc = lib.fylite_rs_redl_drive(*a, n, float(psi_axis), float(psi_bnd), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_redl_drive returned {rc}")
    return out[:n].copy(), out[n:].copy()



#: What `redl_surface_inputs` writes, one row of `n_surface` each.
REDL_INPUT_ROWS = ("eps", "q_abs", "ne", "te", "ti", "ni", "zeff",
                   "i_psi", "p_gfile")


# the mapping half of the analytic bootstrap: profiles + surfaces ->
# the eight per-surface rows, floors and clips included.  `ti`/`ni` are
# `c_void_p` so "not given" is a null rather than a conjured array
_sig("fylite_rs_redl_surface_inputs", ( [_ARR] * 4 + [_U64] + [_ARR] * 3 + [ctypes.c_void_p] * 2 + [_ARR, _U64, _ARR, _U64, ctypes.c_void_p, _U64, _ARR]), _I32)
def redl_surface_inputs(psin_surface, r_minor, r_maj, q, *, psin_prof, ne,
                        te, ti=None, ni=None, zeff, f_table,
                        p_table=None) -> dict:
    """The analytic bootstrap's per-surface inputs — the mapping layer.

    Profiles given on their own ψ_N grid are put onto the surface ladder and
    the model's floors and clips are applied.  Returns the eight arrays of
    :data:`REDL_INPUT_ROWS`.

    ★★Every floor here is a physics statement, and they are in the kernel
    because this is the layer whose errors do not raise — a mis-floored
    temperature comes back as a bootstrap current, not as an exception:
    ``Tₑ``/``Tᵢ`` are floored at 10 eV BEFORE the interpolation (flooring
    after would let a blend dip below it again, and the collisionality
    divides by ``T²``); ``ε`` is clipped to ``[1e-4, 0.99]``, where the
    trapped fraction is singular at the top end and meaningless at the
    bottom; ``|q|`` is floored at 1e-3 because a reconstruction's on-axis q
    can pass through zero; ``Z_eff`` is clipped to ``[1, 10]``, the range
    the 2021 fits were made over.  ``ni=None`` is quasineutral at
    ``nₑ/max(Z_eff, 1)``.

    ``f_table`` is ``|F| = |R B_t|`` on a uniform ψ_N grid over ``[0, 1]``,
    the way a g-file carries it.  ``p_table`` is the reconstruction's own
    pressure on the same grid; it rides the SAME resampling as every other
    profile here (that was the last place two of these rows could disagree
    about a surface) and comes back as ``p_gfile``, **unvalidated** — a
    non-physical pressure is the caller's to REFUSE, since flooring it
    would zero ``dP/dψ`` over the outer half and delete the dominant L31
    term.  Omitted, the row is zeros.
    """
    lib = require()
    ps, rm = _f(np.atleast_1d(psin_surface)), _f(np.atleast_1d(r_minor))
    rj, qq = _f(np.atleast_1d(r_maj)), _f(np.atleast_1d(q))
    pp = _f(np.atleast_1d(psin_prof))
    ne_a, te_a = _f(np.atleast_1d(ne)), _f(np.atleast_1d(te))
    ze = _f(np.broadcast_to(np.asarray(zeff, float), pp.shape))
    ft = _f(np.atleast_1d(f_table))
    ti_a = None if ti is None else _f(np.atleast_1d(ti))
    ni_a = None if ni is None else _f(np.atleast_1d(ni))
    pt = None if p_table is None else _f(np.atleast_1d(p_table))
    ns = ps.size
    out = np.empty(9 * ns)
    rc = lib.fylite_rs_redl_surface_inputs(
        ps, rm, rj, qq, ns, pp, ne_a, te_a,
        None if ti_a is None else ti_a.ctypes.data,
        None if ni_a is None else ni_a.ctypes.data,
        ze, pp.size, ft, ft.size,
        None if pt is None else pt.ctypes.data,
        0 if pt is None else pt.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_redl_surface_inputs returned {rc}")
    return dict(zip(REDL_INPUT_ROWS, out.reshape(9, ns)))

_sig("fylite_rs_neo_surface_inputs", ([_ARR, _ARR, _U64] + [_ARR] * 3 + [_VOID, _U64, _F64, _ARR]), _I32)
def neo_surface_inputs(psin_surface, r_over_a, *, psin_prof, ne, te, ti=None,
                       zeff: float = 1.0):
    """The per-surface species state NEO takes — ``(n_surface, 7)`` as
    ``[dens_i, temp_i, dens_e, temp_e, dlnndr, dlntdr_i, dlntdr_e]``.

    ★NO CALLER in this package as of 2026-08-21.  It was the builder behind
    ``neoclassical.surface_inputs`` until that moved onto the calibrated
    per-surface path (this normalises every profile TO THE FIRST SURFACE and
    supplies no collisionality, which is a shape and not a current).  The
    entry is kept because the Rust side is still exported and the conventions
    below are the documentation of what NEO reads — but nothing exercises it,
    so treat it as unproven until something does.

    ★★Three conventions travel with it, each a physics statement rather
    than bookkeeping: densities and temperatures are normalised TO THE
    FIRST SURFACE (NEO cares about ratios and gradients, and normalising to
    a different surface silently rescales every collisionality); the
    gradients are a-normalised logarithmic ones and a non-positive density
    or temperature has NO scale length — left non-finite and zeroed rather
    than floored, because a floor hands the local solver a large FINITE
    gradient and it will use it; and the single ion is quasineutral at
    ``n_i = n_e/Z_eff``.
    """
    lib = require()
    ps, ra = _f(np.atleast_1d(psin_surface)), _f(np.atleast_1d(r_over_a))
    pp, ne_a, te_a = (_f(np.atleast_1d(x)) for x in (psin_prof, ne, te))
    ti_a = None if ti is None else _f(np.atleast_1d(ti))
    out = np.empty(7 * ps.size)
    rc = lib.fylite_rs_neo_surface_inputs(
        ps, ra, ps.size, pp, ne_a, te_a,
        None if ti_a is None else ti_a.ctypes.data, pp.size, float(zeff),
        out)
    if rc != 0:
        raise KernelError(f"fylite_rs_neo_surface_inputs returned {rc}")
    return out.reshape(ps.size, 7)


#: The Miller row layout `equilibrium_ladder` writes, in ABI order.
MILLER_ROW = ("psin", "r", "rmaj", "zmag", "q", "shear", "shift", "kappa",
              "s_kappa", "delta", "s_delta", "zeta", "s_zeta", "s_zmag")

#: ...and the metric row layout beside it.
METRIC_ROW = ("psin", "rho", "volume", "vprime", "gm3", "gm7", "gm2", "q",
              "fpol", "dv_dpsin")


_sig("fylite_rs_equilibrium_ladder", ([_F64] * 4 + [_U64, _U64, _ARR] + [_F64] * 2 + [_ARR, _ARR, _U64, _ARR, _U64, _ARR, _U64, _ARR, _U64] + [_F64] * 3 + [_U64, _ARR, _ARR]), _I32)
def equilibrium_ladder(grid: Grid, psin2d, *, axis, limiter, levels,
                       q_table, f_table, dpsi: float, b0: float,
                       a_minor: float, n_theta: int = 181) -> dict:
    """One equilibrium's whole ladder: the transport metrics AND the local
    Miller shape, from ONE traced surface set.

    ★★They used to be two calls that traced the same map at the same levels
    and each kept its own ladder — two chances to describe a different
    plasma.  They were even reached with different DEFAULT level sets (41
    surfaces on [0.02, 0.95] against 24 on [0.1, 0.95]), so a caller holding
    both held a metric and a shape for surfaces that were not the same
    surfaces.  Here a level is on the ladder only if it yields BOTH an
    integral and a shape.

    Returns ``{"metrics": {...arrays...}, "miller": [{...}, ...]}``.
    """
    lib = require()
    f = _f(psin2d)
    if f.shape != (grid.nr, grid.nz):
        raise KernelError(f"psin2d has shape {f.shape}, expected "
                          f"{(grid.nr, grid.nz)}")
    lr, lz = _f(np.atleast_1d(limiter[0])), _f(np.atleast_1d(limiter[1]))
    lv = _f(np.atleast_1d(levels))
    q, ft = _f(np.atleast_1d(q_table)), _f(np.atleast_1d(f_table))
    om = np.empty(10 * lv.size)
    ok = np.empty(14 * lv.size)
    n = lib.fylite_rs_equilibrium_ladder(
        grid.r0, grid.z0, grid.dr, grid.dz, grid.nr, grid.nz, f.ravel(),
        float(axis[0]), float(axis[1]), lr, lz, lr.size, lv, lv.size,
        q, q.size, ft, ft.size, float(dpsi), float(b0), float(a_minor),
        int(n_theta), om, ok)
    if n <= 0:
        raise KernelError(f"fylite_rs_equilibrium_ladder returned {n}")
    mrows = om[:10 * n].reshape(n, 10)
    krows = ok[:14 * n].reshape(n, 14)
    return {
        "metrics": {k: mrows[:, i].copy()
                    for i, k in enumerate(METRIC_ROW)},
        "miller": [dict(zip(MILLER_ROW, (float(v) for v in row)))
                   for row in krows],
    }


_sig("fylite_rs_shell_sum", [_ARR, _ARR, _U64, _ARR], _I32)
def shell_sum(values, weights) -> float:
    """``Σ vᵢ wᵢ`` — the shell-table quadrature: a density over the shell
    volumes (``weights = dV``) or a current density over the shell areas
    (``weights = dS``, :func:`shell_area`).

    ★A dot product, and deliberately an ABI entry anyway: P_abs, I_NBI and
    W_fast are closed by the same rule as P_LH and I_LH inside
    :func:`lh_deposit`, and DE-COMP-02 wants that rule in one place rather
    than one ``np.sum`` per total on this side.
    """
    lib = require()
    v, w = _f(np.atleast_1d(values)), _f(np.atleast_1d(weights))
    if v.size != w.size:
        raise KernelError(f"shell_sum: {v.size} values against {w.size} weights")
    out = np.empty(1)
    rc = lib.fylite_rs_shell_sum(v, w, v.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_shell_sum returned {rc}")
    return float(out[0])


_sig("fylite_rs_shell_area", [_ARR, _ARR, _U64, _VOID, _VOID, _ARR], _I32)
def shell_area(dvol, rmaj, *, p_dep=None, tau_eff=None):
    """The flux-surface AREA element that goes with a shell volume:
    ``dS = dV/(2πR)``.

    ★★A surface of revolution has ``dV = 2πR dS``, so a current density
    integrates to a current with THIS weight and no other.  It looks like a
    line of bookkeeping and it is the difference between an ampere and an
    ampere per metre — and it was written out separately in the beam module
    and the wave module, which is two chances to write it differently.

    See :func:`fast_ion_pressure` for the other half of this ABI entry.
    """
    lib = require()
    dv, rj = _f(np.atleast_1d(dvol)), _f(np.atleast_1d(rmaj))
    n = dv.size
    both = p_dep is not None and tau_eff is not None
    pd = _f(np.atleast_1d(p_dep)) if both else None
    te = _f(np.atleast_1d(tau_eff)) if both else None
    out = np.empty(3 * n if both else n)
    rc = lib.fylite_rs_shell_area(dv, rj, n,
                                  None if pd is None else pd.ctypes.data,
                                  None if te is None else te.ctypes.data,
                                  out)
    if rc != 0:
        raise KernelError(f"fylite_rs_shell_area returned {rc}")
    if not both:
        return out[:n].copy()
    return out[:n].copy(), out[n:2 * n].copy(), out[2 * n:].copy()


def fast_ion_pressure(p_dep, tau_eff, rmaj=None):
    """Fast-ion energy density and pressure: ``W = P·τ_eff/2``,
    ``p = (2/3)W``.

    ★The 2/3 is the ISOTROPIC closure — ``W = (3/2)p`` holds for an
    isotropic distribution and a tangential beam is not one.  The scalar
    this returns is what the pressure channel adds to ``p_thermal``; the
    anisotropy it does not carry is a stated limitation of THIS ENTRY.

    ★It is no longer a limitation of the beam model, and this sentence used
    to say it was: ``scenario.model.nbi.deposit`` carries the split since
    T-M12 (the pitch-preserving drag closure) and reports
    ``anisotropy = {"p_par", "p_perp"}`` beside the trace third.  What still
    takes only the trace is the Grad-Shafranov source, which is what this
    entry feeds.
    """
    pd = _f(np.atleast_1d(p_dep))
    te = _f(np.broadcast_to(np.atleast_1d(tau_eff), pd.shape))
    #: `rmaj` only feeds the area half of the shared entry; ones keep it
    #: finite and its result unused
    ones = np.ones_like(pd)
    _, w, p = shell_area(ones, ones if rmaj is None else rmaj,
                         p_dep=pd, tau_eff=te)
    return w, p


_sig("fylite_rs_fast_ion_pressure_split", [_ARR, _ARR, _ARR, _U64, _ARR], _I32)
def fast_ion_pressure_split(p_dep, tau_eff, pitch):
    """Fast-ion pressure split into the parallel/perpendicular branches by
    the birth pitch (T-M12): ``W = P·τ_eff/2``, ``p_par = 2Wξ²``,
    ``p_perp = W(1−ξ²)``.

    ★The PITCH-PRESERVING drag closure: Coulomb drag above the critical
    energy changes the speed, not the pitch.  Two identities close it —
    ``p_par/2 + p_perp == W`` exactly, and the trace third
    ``(p_par + 2p_perp)/3`` equals :func:`fast_ion_pressure`'s isotropic
    scalar, so the split moves nothing in the scalar channel.  Returns
    ``(W, p_par, p_perp)``.
    """
    lib = require()
    pd = _f(np.atleast_1d(p_dep))
    te = _f(np.broadcast_to(np.atleast_1d(tau_eff), pd.shape))
    xi = _f(np.broadcast_to(np.atleast_1d(pitch), pd.shape))
    out = np.empty(3 * pd.size)
    rc = lib.fylite_rs_fast_ion_pressure_split(pd, te, xi, pd.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_fast_ion_pressure_split returned {rc}")
    n = pd.size
    return out[:n].copy(), out[n:2 * n].copy(), out[2 * n:].copy()


_sig("fylite_rs_beam_torque", [_ARR, _ARR, _ARR, _U64, _F64, _F64, _ARR], _I32)
def beam_torque(p_dep, pitch, rmaj, *, energy, mass):
    """Toroidal torque density of the beam's PROMPT momentum input (T-M12):
    ``τ_φ = p_dep·(2/v_b)·ξ·R`` with ``v_b = √(2eE/m)`` the birth speed of
    THIS energy component.

    ★Per component, because ``v_b`` differs per energy fraction — call once
    per component with that component's own ``p_dep`` and ``pitch`` and sum.
    ``energy`` in eV, ``mass`` in amu; the sign is the pitch's.
    """
    lib = require()
    pd = _f(np.atleast_1d(p_dep))
    xi = _f(np.broadcast_to(np.atleast_1d(pitch), pd.shape))
    rj = _f(np.broadcast_to(np.atleast_1d(rmaj), pd.shape))
    out = np.empty(pd.size)
    rc = lib.fylite_rs_beam_torque(pd, xi, rj, pd.size,
                                   float(energy), float(mass), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_beam_torque returned {rc}")
    return out


_sig("fylite_rs_chi_from_flux", ([_ARR] * 4 + [_U64] + [_F64] * 6 + [_ARR]), _I32)
def chi_from_flux(flux, dens, grad_t, gm3, *, floor: float = 1e-30):
    """A model flux → the effective diffusivity the PDE closure takes.

    ``flux`` is per unit V′-area [W/m²] — the currency the flux-match line
    works in (TGYRO's ``eflux·Q_GB`` equals ``P/V'``).  The PDE's conduction
    law carries ``P/V' = ⟨|∇ρ|²⟩ n χ e |∂T/∂ρ|``, so
    ``χ = flux / (⟨|∇ρ|²⟩ n e |∂T/∂ρ|)`` — the same algebra as the
    interpretive inversion, but from a MODEL flux at the current iterate
    rather than the power-balance flux of measured profiles.  ★The DENOMINATOR is floored, not the result: a flat iterate
    has no resolvable χ, and saying so as a very large number is honest
    where clamping would quietly invent a closure.  Clipping χ is the
    closure's own business (it owns the stiffness guard) — two decisions
    that look alike and belong to different layers.
    """
    lib = require()
    shape = np.shape(np.broadcast_arrays(*(np.asarray(x, float) for x in
                                           (flux, dens, grad_t, gm3)))[0])
    a = [_f(np.broadcast_to(np.asarray(x, float), shape).ravel())
         for x in (flux, dens, grad_t, gm3)]
    n = a[0].size
    out = np.empty(n + 1)
    rc = lib.fylite_rs_chi_from_flux(*a, n, float(floor), 0.0, 0.0, 0.0,
                                     0.0, 0.0, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_chi_from_flux returned {rc}")
    res = out[:n].reshape(shape)
    return res if shape else float(res)


_sig("fylite_rs_d_from_flux", ([_ARR] * 3 + [_U64, _F64, _ARR]), _I32)
def d_from_flux(flux, grad_n, gm3, *, floor: float = 1e-30):
    """A model PARTICLE flux → the effective diffusivity the density channel
    takes.

    ``flux`` is per unit V′-area [1/(m²·s)] — the same currency
    :func:`chi_from_flux` takes its energy flux in.  The density channel's
    law carries ``Γ/V' = ⟨|∇ρ|²⟩ D |∂n/∂ρ|``, so
    ``D = flux / (⟨|∇ρ|²⟩ |∂n/∂ρ|)``.

    ★The difference from :func:`chi_from_flux` is the whole of it: **no
    density and no elementary charge** in the denominator, because this flux
    counts particles and not their energy.  Confusing the two is a factor of
    ``n·e`` ≈ 1e19 — which is at least loud.

    ★★It is an EFFECTIVE diffusivity: one flux cannot be split into a
    diffusion and a pinch, and this does not pretend to.
    """
    lib = require()
    shape = np.shape(np.broadcast_arrays(*(np.asarray(x, float) for x in
                                           (flux, grad_n, gm3)))[0])
    a = [_f(np.broadcast_to(np.asarray(x, float), shape).ravel())
         for x in (flux, grad_n, gm3)]
    n = a[0].size
    out = np.empty(n)
    rc = lib.fylite_rs_d_from_flux(*a, n, float(floor), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_d_from_flux returned {rc}")
    res = out.reshape(shape)
    return res if shape else float(res)


def gyrobohm_q(*, ne: float, te: float, c_s: float, rho_s: float,
               a: float) -> float:
    """The gyro-Bohm energy-flux unit of one surface [W/m²].

    SI in: ``ne`` [m^-3], ``te`` [eV], ``c_s`` [m/s], ``rho_s``/``a`` [m].

    ★The bridge between what the turbulence models return (dimensionless)
    and what a transport equation takes: getting the ``ρ_s/a`` power wrong
    is a plausible flux that is wrong by a gyroradius squared.  ★★And it
    took ``ne_cgs``/``c_s`` in CGS while the answer came out in W/m², so a
    caller reading the return type had no way to guess the arguments were a
    different unit system — the surface state it would naturally reach for
    is the one this now takes.
    """
    lib = require()
    one = _f(np.ones(1))
    out = np.empty(2)
    rc = lib.fylite_rs_chi_from_flux(one, one, one, one, 1, 1e-30,
                                     float(ne), float(te), float(c_s),
                                     float(rho_s), float(a), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_chi_from_flux returned {rc}")
    return float(out[1])


# --------------------------------------------------------------------------- #
# The SCENARIO face: named quantities, one symbol
#
# ★★The flat entries above stay — they are the kernel's own vocabulary, one
# function per numerical claim, and nothing here replaces them.  What this
# adds beside them is the altitude a scenario is asked at: `scenario("zerod",
# params={...}, inputs={...})`, where every argument is a NAME and its
# position in the packed block comes from the kernel's own declaration
# (`rust/fylite/src/fyo.rs`, generated into `_fyo_interface.py`).
#
# ★One symbol serves every entry, so appending an entry moves no signature.
# --------------------------------------------------------------------------- #
_ARRU = np.ctypeslib.ndpointer(np.uint64, flags="C_CONTIGUOUS")

#: Entry name -> its wire index.  The INDEX crosses the ABI, so the
#: generated list is append-only.
SCENARIO_ENTRIES = _fyo_interface.ENTRIES

#: What the scenario face refuses, and why — four codes because they send a
#: reader to four different places.
_SCENARIO_ERRORS = {
    -20: "scenario: no such entry",
    -21: "scenario: the entry does not take those dimensions",
    -22: "scenario: a block is not the length the declaration gives it",
    -23: ("scenario: the entry refused the request — a statement about the "
          "plasma, not the arithmetic"),
}


def _shape_size(shape: str, dims: dict) -> int:
    """One declared shape: ``1``, a dimension, ``a*b`` or ``a+1``.

    ★The same five-line grammar the kernel and the browser parse.  It is
    small on purpose: a declaration two hosts must agree about should not
    need a format library to read.
    """
    def one(name: str) -> int:
        name = name.strip()
        if name.isdigit():
            return int(name)
        if name not in dims:
            raise KernelError(f"scenario: shape {shape!r} names dimension "
                              f"{name!r}, which this entry does not declare "
                              f"(has {sorted(dims)})")
        return int(dims[name])

    if "*" in shape:
        a, b = shape.split("*", 1)
        return one(a) * one(b)
    if "+" in shape:
        a, b = shape.split("+", 1)
        return one(a) + one(b)
    return one(shape)


def scenario_layout(entry: str, dims: dict) -> dict:
    """``{block: {key: (offset, length)}}`` for one entry at these dims."""
    spec = _fyo_interface.ENTRY_BLOCKS.get(entry)
    if spec is None:
        raise KernelError(f"scenario: no entry {entry!r}; have "
                          f"{list(SCENARIO_ENTRIES)}")
    out = {}
    for role in ("params", "input", "out"):
        at, rows = 0, {}
        for row in _fyo_interface.BLOCKS[spec[role]]:
            n = _shape_size(row["shape"], dims)
            rows[row["key"]] = (at, n)
            at += n
        out[role] = rows
    return out


_sig("fylite_rs_scenario",
     [ctypes.c_uint32, _ARR, _U64, _ARR, _U64, _ARRU, _U64, _ARR, _U64], _I32)
_sig("fylite_rs_scenario_sizes",
     [ctypes.c_uint32, _ARRU, _U64, _ARR], _I32)
def scenario(entry: str, *, params: dict | None = None,
             inputs: dict | None = None, **dims) -> dict:
    """Run one scenario entry by NAME, with named arguments.

    ``scenario("zerod", params={...}, inputs={...}, nt=..., nr=...)``.
    Every key is a row of the entry's declared block, and the result comes
    back the same way — a scalar row as a float, everything else as an
    array of its declared length.

    ★A row the caller does not supply is zero, which is a legitimate
    request for most of them; a row that is not declared is a REFUSAL, with
    the block's keys named, because a silently ignored argument is how a
    caller ends up believing it asked for something it did not.
    """
    lib = require()
    spec = _fyo_interface.ENTRY_BLOCKS.get(entry)
    if spec is None:
        raise KernelError(f"scenario: no entry {entry!r}; have "
                          f"{list(SCENARIO_ENTRIES)}")
    order = list(spec["dims"])
    missing = [d for d in order if d not in dims]
    if missing:
        raise KernelError(f"scenario {entry!r} needs dimensions {missing}")
    extra = [d for d in dims if d not in order]
    if extra:
        raise KernelError(f"scenario {entry!r} takes {order}, not {extra}")
    layout = scenario_layout(entry, dims)

    def pack(role: str, given: dict) -> np.ndarray:
        rows = layout[role]
        unknown = [k for k in given if k not in rows]
        if unknown:
            raise KernelError(
                f"scenario {entry!r}: {role} has no {unknown}; it takes "
                f"{list(rows)} (declared in rust/fylite/src/fyo.rs)")
        total = sum(n for _, n in rows.values())
        buf = np.zeros(total)
        for key, (at, n) in rows.items():
            if key not in given:
                continue
            v = np.asarray(given[key], float).ravel()
            if v.size == 1 and n > 1:
                v = np.full(n, float(v[0]))
            if v.size != n:
                raise KernelError(
                    f"scenario {entry!r}: {role}/{key} is declared "
                    f"{n} long and got {v.size}")
            buf[at:at + n] = v
        return _f(buf)

    p = pack("params", dict(params or {}))
    i = pack("input", dict(inputs or {}))
    dv = np.ascontiguousarray([int(dims[d]) for d in order], dtype=np.uint64)
    n_out = sum(n for _, n in layout["out"].values())
    out = np.zeros(n_out)
    #: ★the kernel's own sizes, asked for and compared: it walks the same
    #: declaration this host just walked, so a mismatch means the generated
    #: table and the library are not the same generation
    sizes = np.empty(3)
    idx = SCENARIO_ENTRIES.index(entry)
    rc = lib.fylite_rs_scenario_sizes(idx, dv, dv.size, sizes)
    if rc != 0:
        raise KernelError(_SCENARIO_ERRORS.get(
            rc, f"fylite_rs_scenario_sizes returned {rc}"))
    if [int(v) for v in sizes] != [p.size, i.size, n_out]:
        raise KernelError(
            f"scenario {entry!r}: the kernel sizes its blocks "
            f"{[int(v) for v in sizes]} and this host sizes them "
            f"{[p.size, i.size, n_out]} — _fyo_interface.py and the built "
            "library are different generations; run rust/build.sh")
    rc = lib.fylite_rs_scenario(idx, p, p.size, i, i.size, dv, dv.size,
                                out, out.size)
    if rc != 0:
        raise KernelError(_SCENARIO_ERRORS.get(
            rc, f"fylite_rs_scenario returned {rc}"))
    #: ★★A row comes back as a scalar because its DECLARATION says `"1"`,
    #: never because its length happened to be one.  This read `n == 1`,
    #: which made the shape of the result depend on the DATA: an entry run
    #: at `nt = 1` handed back its per-step traces as bare floats, and every
    #: caller that sliced them (`out["t"][:steps]`) died with 「'float'
    #: object is not subscriptable」 on exactly the smallest case anyone
    #: would reach for while debugging.  A declared shape is a contract; a
    #: contract that changes with the numbers is not one.
    shape_of = {row["key"]: row["shape"]
                for row in _fyo_interface.BLOCKS[spec["out"]]}
    got = {}
    for key, (at, n) in layout["out"].items():
        got[key] = (float(out[at]) if shape_of[key].strip() == "1"
                    else out[at:at + n].copy())
    return got


_sig("fylite_rs_q_crossing", [_ARR, _ARR, _U64, _F64, _ARR], _I32)
def q_crossing(rho, q, *, q_crit: float = 1.0):
    """The innermost radius where ``q`` crosses ``q_crit``, or ``None``.

    ★``None`` is the answer for a discharge that is not sawtoothing, and a
    caller has to be able to act on it — so it is not a radius of zero.
    """
    lib = require()
    r, qq = _f(rho), _f(q)
    out = np.empty(1)
    rc = lib.fylite_rs_q_crossing(r, qq, r.size, float(q_crit), out)
    if rc == -5:
        return None
    if rc != 0:
        raise KernelError(f"fylite_rs_q_crossing returned {rc}")
    return float(out[0])


_sig("fylite_rs_sawtooth_crash",
     [_ARR] * 4 + [_U64, _U64, _F64, _F64, _ARR], _I32)
def sawtooth_crash(rho, *, vprime, psi, b0: float, profiles, r_mix: float):
    """One sawtooth crash: mix ``profiles`` inside ``r_mix``, q → 1 there.

    Returns ``{profiles, psi, q, psi_moved, i_mix}``.  Each profile is
    flattened conserving ``∫V'y dρ`` over the mixed region — the integral
    the plasma actually keeps — and everything outside is untouched.

    ★★A MIXING model, not Kadomtsev and not Porcelli: no helicity pairing,
    no fast-ion stabilisation, and the trigger is ``q(0) < q_crit`` alone.
    ``r_mix`` has no default for the same reason TGLF's ``width`` has none.
    """
    lib = require()
    r = _f(rho)
    n = r.size
    rows = [np.broadcast_to(np.asarray(p, float), (n,)) for p in profiles]
    block = _f(np.concatenate(rows)) if rows else _f(np.empty(0))
    out = np.empty(len(rows) * n + 2 * n + 2)
    rc = lib.fylite_rs_sawtooth_crash(r, _f(vprime), _f(psi), block, n,
                                      len(rows), float(b0), float(r_mix),
                                      out)
    if rc != 0:
        raise KernelError(
            "sawtooth_crash: the mixing radius must sit on the grid and "
            "cover at least two cells, and every profile must be as long "
            f"as rho (kernel returned {rc})")
    m = len(rows) * n
    return {"profiles": [out[j * n:(j + 1) * n].copy()
                         for j in range(len(rows))],
            "psi": out[m:m + n].copy(), "q": out[m + n:m + 2 * n].copy(),
            "psi_moved": float(out[m + 2 * n]),
            "i_mix": int(out[m + 2 * n + 1])}


_sig("fylite_rs_alpha_heating", [_ARR] * 3 + [_U64] + [_F64] * 3 + [_ARR],
     _I32)
def alpha_heating(*, ne, te, ti_kev, dt_fraction: float = 0.5,
                  zeff: float = 1.0, zsum: float = 0.5) -> dict:
    """Alpha heating on a profile — power density and its e/i split.

    ``{p_total, p_e, p_i, e_crit}`` in W/m³ (``e_crit`` in eV).  ``ne``
    [m⁻³], ``te`` [eV], ``ti_kev`` [keV]; ``dt_fraction`` follows the 0-D
    tier (``n_D = n_T = dt_fraction·n_e``); ``zsum`` is the field-ion sum
    ``Σ n_j Z_j²/(n_e A_j)`` that sets the critical energy, as for the beam.

    ★★It is an ASSEMBLY of two things the kernel already pins — the
    Bosch-Hale reactivity and the Stix slowing-down partition — rather than
    a transcription of an upstream routine, because upstream's regression
    set carries no D-T.  Two gates: the cross-tier identity (the volume
    integral of ``p_total`` is :func:`zerod_fusion_power`'s alpha share on
    the same profiles) and, since 2026-08-22, an EXTERNAL one — ASTRA's
    ITER 15 MA burn case in ``tests/data/reference/``, which the kernel matches
    to 3 % point-by-point and 0.3 % in the integral.
    """
    lib = require()
    shape = np.shape(np.asarray(ne, float))
    a = [_f(np.broadcast_to(np.asarray(x, float), shape))
         for x in (ne, te, ti_kev)]
    n = a[0].size
    out = np.empty(4 * n)
    rc = lib.fylite_rs_alpha_heating(*a, n, float(dt_fraction), float(zeff),
                                     float(zsum), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_alpha_heating returned {rc}")
    return {"p_total": out[:n].copy(), "p_e": out[n:2 * n].copy(),
            "p_i": out[2 * n:3 * n].copy(), "e_crit": out[3 * n:].copy()}


_sig("fylite_rs_alpha_fast_ions", [_ARR] * 3 + [_U64] + [_F64] * 3 + [_ARR],
     _I32)
def alpha_fast_ions(*, ne, te, ti_kev, dt_fraction: float = 0.5,
                    zeff: float = 1.0, zsum: float = 0.5) -> dict:
    """The fast alphas the heating channel leaves behind.

    ``{rate, n_fast, p_fast, w_fast, tau_s, tau_res}``: the alpha birth
    rate [1/(m³·s)] — which in steady state IS the helium-ash particle
    source — the fast-alpha density [m⁻³], their pressure [Pa] and stored
    energy density [J/m³], and the slowing-down and residence times [s].
    Arguments are :func:`alpha_heating`'s, and ``rate·E_α`` is that
    function's ``p_total``.

    ★**Steady state, not fast-ion transport.**  ``n_fast = rate·tau_res``
    assumes the birth rate has been constant for longer than a slowing-down
    time; there is no radial transport of the fast alphas, no orbit width
    and no loss channel, so a ramp or a crash is outside it.

    ★★``tau_res`` is the birth-to-rest time ``(tau_s/3)·ln(1+(E_α/E_c)^1.5)``
    and NOT ``tau_s`` — and ``tau_s`` itself carries the alpha's ``1/Z_b²``,
    which is a factor 4 the hydrogenic beam never sees.  Both land within
    2 % of ASTRA's ITER 15 MA burn case (``tests/data/reference/``); either slip
    puts them 40 % or 4× out.
    """
    lib = require()
    shape = np.shape(np.asarray(ne, float))
    a = [_f(np.broadcast_to(np.asarray(x, float), shape))
         for x in (ne, te, ti_kev)]
    n = a[0].size
    out = np.empty(6 * n)
    rc = lib.fylite_rs_alpha_fast_ions(*a, n, float(dt_fraction), float(zeff),
                                       float(zsum), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_alpha_fast_ions returned {rc}")
    return {"rate": out[:n].copy(), "n_fast": out[n:2 * n].copy(),
            "p_fast": out[2 * n:3 * n].copy(),
            "w_fast": out[3 * n:4 * n].copy(),
            "tau_s": out[4 * n:5 * n].copy(),
            "tau_res": out[5 * n:].copy()}


_sig("fylite_rs_gyrobohm_gamma", [_F64] * 4, _F64)
def gyrobohm_gamma(*, ne: float, c_s: float, rho_s: float, a: float) -> float:
    """The gyro-Bohm PARTICLE-flux unit of one surface [1/(m²·s)].

    ``Γ_GB = n_e c_s (ρ_s/a)²`` — :func:`gyrobohm_q` with the energy
    ``e·T_e`` taken out, which is exactly what separates a particle flux
    from an energy one.  SI in: ``ne`` [m⁻³], ``c_s`` [m/s],
    ``rho_s``/``a`` [m].
    """
    lib = require()
    return float(lib.fylite_rs_gyrobohm_gamma(float(ne), float(c_s),
                                              float(rho_s), float(a)))


def gyrobohm_pi(*, ne: float, te: float, c_s: float, rho_s: float,
                a: float) -> float:
    """The gyro-Bohm TOROIDAL-STRESS unit of one surface [N/m].

    ``Π_GB = n_e T_e a (ρ_s/a)²`` — the normalisation upstream's
    ``out.tglf.gbflux`` momentum column carries, spelled the same way in
    ``tgyro_flux.f90`` and ``tgyro_profile_functions.f90``.

    ★Written as ``Q_GB · a / c_s`` rather than re-derived: the two differ
    by exactly that, and stating it as a relation means the ``ρ_s/a``
    power — the thing :func:`gyrobohm_q` warns about — is claimed in ONE
    place and cannot drift between the energy and momentum channels.

    SI in: ``ne`` [m⁻³], ``te`` [eV], ``c_s`` [m/s], ``rho_s``/``a`` [m].
    """
    return gyrobohm_q(ne=ne, te=te, c_s=c_s, rho_s=rho_s, a=a) * a / c_s


_sig("fylite_rs_selfcal_single", [_ARR, _ARR, _ARR, _U64, _F64, _ARR], _I32)
def selfcal_single(measured, computed, alive, *, tol: float = 0.15):
    """Per-channel factors from ONE slice: ``computed/measured`` against
    their median.  Returns ``(factors, keep, median)``.

    ★The median absorbs any global scale or unit offset, so only
    channel-RELATIVE inconsistency can reject a channel — a calibration
    that rejected on the absolute ratio would reject everything the moment
    someone changed a unit.
    """
    lib = require()
    m, c = _f(np.atleast_1d(measured)), _f(np.atleast_1d(computed))
    a = _f(np.asarray(alive, float).astype(float).ravel())
    n = m.size
    out = np.empty(2 * n + 1)
    rc = lib.fylite_rs_selfcal_single(m, c, a, n, float(tol), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_selfcal_single returned {rc}")
    return out[:n].copy(), out[n:2 * n] != 0.0, float(out[2 * n])


_sig("fylite_rs_selfcal_slices", [_ARR, _U64, _U64, _ARR, _ARR], _I32)
def selfcal_slices(ratio, alive):
    """Per-channel factor and its slice-to-slice scatter, from a
    ``(n_slice, n_channel)`` ratio array.

    Returns ``(factors, scatter, n_used)``.  ★``scatter`` is ``MAD/|median|``
    — the ROBUST spread of one channel's factor over slices, which is what
    says whether the factor behaves like an instrument property or like
    noise.  The per-channel factor is a median for the same reason; the
    statistic that decides whether any channel STANDS OUT is not
    (:func:`factor_dispersion`).
    """
    lib = require()
    r = _f(np.atleast_2d(np.asarray(ratio, float)))
    ns, nc = r.shape
    a = _f(np.asarray(alive, float).astype(float).ravel())
    out = np.empty(3 * nc)
    rc = lib.fylite_rs_selfcal_slices(r.ravel(), ns, nc, a, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_selfcal_slices returned {rc}")
    return (out[:nc].copy(), out[nc:2 * nc].copy(),
            out[2 * nc:].astype(int))


_sig("fylite_rs_factor_dispersion", [_ARR, _U64, _ARR], _I32)
def factor_dispersion(factors) -> float:
    """``max |f/median(f) − 1|`` over the finite entries.

    A global scale or unit error moves the median and leaves this at zero;
    only channel-RELATIVE inconsistency raises it, which is the quantity a
    per-channel calibration is trying to see.

    ★Deliberately NOT a robust spread.  MAD and IQR exist to suppress a
    minority of outliers, and here that minority IS the signal — a handful
    of miscalibrated channels among twenty.  ``MAD([1,1,2,1])`` is 0, which
    would report "nothing to see" about the one channel that is wrong.
    Robustness belongs in the per-channel factor (a median over slices), not
    in the statistic that decides whether any channel stands out at all.
    """
    lib = require()
    f = _f(np.atleast_1d(factors))
    out = np.empty(1)
    rc = lib.fylite_rs_factor_dispersion(f, f.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_factor_dispersion returned {rc}")
    return float(out[0])


_sig("fylite_rs_tomography_rows", ([_F64] * 4 + [_U64, _U64, _ARR, _ARR, _U64, _ARR, _ARR, _U64, _F64, _F64] + [_U64] * 4 + [_ARR]), _I32)
def tomography_rows(grid: Grid, psin2d, chords, *, boundary=None, axis,
                    m_max: int = 1, l_max: int = 4, n_samples: int = 601,
                    n_basis: int):
    """The tomography response matrix — row per chord, column per basis mode.

    ``chords`` is ``(n_chord, 7)`` as ``[ox, oy, oz, dx, dy, dz, length]``.

    ★★Three statements in one call, each of which has cost this repo on its
    own: ψ_N ≤ 1 is NOT a containment test (ψ is not monotone outside the
    plasma), the angle is the GEOMETRIC poloidal angle about the magnetic
    axis (the convention the basis was built in — measure it about the
    geometric centre and every odd mode rotates), and the integral is the
    midpoint rule the chord layer uses.  And the matrix belongs to the MAP:
    it is rebuilt when the equilibrium changes.
    """
    lib = require()
    p = _f(psin2d)
    if p.shape != (grid.nr, grid.nz):
        raise KernelError(f"psin2d has shape {p.shape}, expected "
                          f"{(grid.nr, grid.nz)}")
    ch = _f(np.asarray(chords, float).reshape(-1, 7))
    if boundary is None:
        br = bz = np.zeros(0)
    else:
        br, bz = _f(boundary[0]), _f(boundary[1])
    out = np.empty(ch.shape[0] * int(n_basis))
    rc = lib.fylite_rs_tomography_rows(
        grid.r0, grid.z0, grid.dr, grid.dz, grid.nr, grid.nz, p.ravel(),
        ch.ravel(), ch.shape[0], br, bz, br.size, float(axis[0]),
        float(axis[1]), int(m_max), int(l_max), int(n_samples),
        int(n_basis), out)
    if rc == -2:
        raise KernelError(
            "every chord missed the plasma — check the view geometry "
            "against the equilibrium (no sight line has samples inside the "
            "LCFS)")
    if rc != 0:
        raise KernelError(f"fylite_rs_tomography_rows returned {rc}")
    return out.reshape(ch.shape[0], int(n_basis))


_sig("fylite_rs_solve_density", ([_ARR] * 7 + [_U64, _F64, _F64, _U64] + [_F64] * 3 + [_U64, _ARR]), _I32)
def solve_density(rho, n_init, *, vprime, gm3, d, v=0.0, source=0.0,
                  dt: float, edge: float, max_outer: int = 500,
                  tol_steady: float = 1e-9, d_pc: float = 0.0,
                  tol: float = 1e-10, max_inner: int = 60) -> dict:
    """The particle channel, marched to steady — the kernel's.

    Capacity ``V'``, flux metric ``V'⟨|∇ρ|²⟩``, and the solver's source IS
    the volumetric one.  ★Density stays a PER-ION quantity: the electron
    density is the quasi-neutrality closure, not a solvable channel.
    """
    lib = require()
    shape = np.shape(np.asarray(rho, float))
    a = [_f(np.broadcast_to(np.asarray(x, float), shape))
         for x in (rho, n_init, vprime, gm3, d, v, source)]
    n = a[0].size
    out = np.empty(n + 3)
    rc = lib.fylite_rs_solve_density(*a, n, float(dt), float(edge),
                                     int(max_outer), float(tol_steady),
                                     float(d_pc), float(tol),
                                     int(max_inner), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_solve_density returned {rc}")
    return {"n": out[:n].copy(), "outer_steps": int(out[n]),
            "steady": bool(out[n + 1]), "delta": float(out[n + 2])}


_sig("fylite_rs_solve_psi", ([_ARR] * 7 + [_U64] + [_F64] * 2 + [_U64] + [_F64] * 3 + [_U64, _ARR]), _I32)
def solve_psi(rho, psi_init, *, vprime, gm2, fpol, b0: float, sigma_par,
              j_ni=0.0, dt: float, n_steps: int = 1, edge_psi: float,
              edge_rate: float = 0.0, tol: float = 1e-10,
              max_inner: int = 60) -> dict:
    """The current-diffusion channel — the kernel's.

    ★★Upstream's regularisations came with it, because each is there
    because something rings without it: ``rho_safe`` in the capacity, the
    near-axis ``V'``/``gm2`` rebuild (the FSA ladder's own axis
    extrapolation otherwise rings ψ by O(10 %)), the σ floor, and the
    monotone repair whose SIZE is reported rather than silently applied.

    ★``j_ni`` is the NON-INDUCTIVE current only.  The Ohmic ``j = σE`` is
    the unknown of this equation; folding it in pins the lagged ``σE``
    pattern into ψ and hollows the current profile within tens of steps.
    """
    lib = require()
    shape = np.shape(np.asarray(rho, float))
    a = [_f(np.broadcast_to(np.asarray(x, float), shape))
         for x in (rho, psi_init, vprime, gm2, fpol, sigma_par, j_ni)]
    n = a[0].size
    out = np.empty(2 * n + 1)
    rc = lib.fylite_rs_solve_psi(*a, n, float(b0), float(dt), int(n_steps),
                                 float(edge_psi), float(edge_rate),
                                 float(tol), int(max_inner), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_solve_psi returned {rc}")
    return {"psi": out[:n].copy(), "q": out[n:2 * n].copy(),
            "repaired": float(out[2 * n]), "steps": int(n_steps)}


_sig("fylite_rs_two_temperature_step", ([_ARR] * 12 + [_U64] + [_F64] * 5 + [_U64, _ARR]), _I32)
def two_temperature_step(rho, te_old, ti_old, *, ne, ni, vprime, gm3,
                         chi_e, chi_i, q_e, q_i, s_exchange, dt: float,
                         edge_te: float, edge_ti: float, d_pc: float = 0.0,
                         tol: float = 1e-10, max_inner: int = 60):
    """One coupled Te/Ti step — both channels, one exchange term.

    ★The FVM WEIGHTS are the kernel's: capacity ``(3/2)V'n``, flux metric
    ``V'⟨|∇ρ|²⟩n`` and a source RATE ``Q/((3/2)ne)`` with ``V'`` cancelled
    analytically — left uncancelled it is 0/0 at the axis, where ``V'``
    vanishes, i.e. a NaN in the one cell every profile is read at.

    ★The exchange is applied HERE, negative to electrons and positive to
    ions, rather than handed in per channel: it depends on ``Te − Ti``, and
    splitting it into two independent sources is how a coupled pair stops
    conserving the energy it exchanges.  ``chi_e``/``chi_i`` are this
    iteration's closure values — the closure itself stays with the caller,
    because a TGLF+NEO evaluation is not something the kernel can call.
    """
    lib = require()
    arrs = [_f(np.broadcast_to(np.asarray(a, float), np.shape(rho)))
            for a in (rho, te_old, ti_old, ne, ni, vprime, gm3, chi_e, chi_i,
                      q_e, q_i, s_exchange)]
    n = arrs[0].size
    out = np.empty(2 * n)
    rc = lib.fylite_rs_two_temperature_step(
        *arrs, n, float(dt), float(edge_te), float(edge_ti), float(d_pc),
        float(tol), int(max_inner), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_two_temperature_step returned {rc}")
    return out[:n].copy(), out[n:].copy()


_sig("fylite_rs_b_unit_from_rho", [_F64, _ARR, _ARR, _U64, _ARR], _I32)
def b_unit_from_rho(b0: float, rho, r):
    """``B_unit`` [T] along a ladder: ``|dΦ/dr|/(2πr)`` with ``Φ = πB₀ρ²``.

    ``rho`` is the toroidal-flux radius [m] and ``r`` the Miller minor
    radius [m] — different labels, and the derivative is against ``r``
    because that is the label TGLF and NEO are handed.

    ★★The single most consequential number the mapping layer produces, and
    nothing raises when it is wrong: ``BETAE`` is referenced to it rather
    than to the vacuum field, ``ρ_s`` scales with it, and the gyro-Bohm flux
    unit carries it squared.  Reaching for the vacuum ``B₀`` instead — they
    differ by a shaping factor of order one — gets fluxes wrong by a factor
    nothing else in the chain would flag.

    ★It is exact only in the INTERIOR: the derivative is one-sided at the
    ends, so the first and last nodes read an extrapolation.
    """
    lib = require()
    rho_a, r_a = _f(np.atleast_1d(rho)), _f(np.atleast_1d(r))
    if r_a.size != rho_a.size:
        raise KernelError(f"rho has {rho_a.size} points, r has {r_a.size}")
    out = np.empty(rho_a.size)
    rc = lib.fylite_rs_b_unit_from_rho(float(b0), rho_a, r_a, rho_a.size,
                                       out)
    if rc != 0:
        raise KernelError(f"fylite_rs_b_unit_from_rho returned {rc}")
    return out


_sig("fylite_rs_ion_dilution", [_ARR, _U64, _F64, _F64, _ARR], _I32)
def ion_dilution(ne, *, zeff: float, z_imp: float = 6.0):
    """Main-ion density from ``Z_eff`` — ``n_D = nₑ(Z_imp−Z_eff)/(Z_imp−1)``.

    Upstream's ``LOC_N_ION = 1`` posture: the impurity never becomes a
    kinetic species, it only removes electrons from the main ion.

    ★★A ``Z_eff`` the chosen impurity cannot represent is REFUSED, not
    floored — a floored main-ion density is a plasma with the wrong number
    of deuterons, and nothing downstream would say so.
    """
    lib = require()
    ne_a = _f(np.atleast_1d(ne))
    out = np.empty(ne_a.size)
    rc = lib.fylite_rs_ion_dilution(ne_a, ne_a.size, float(zeff),
                                    float(z_imp), out)
    if rc != 0:
        raise KernelError(
            f"zeff={zeff} is not representable with Z_imp={z_imp}"
            if rc == -2 else f"fylite_rs_ion_dilution returned {rc}")
    return out.reshape(np.shape(ne)) if np.shape(ne) else float(out[0])


_sig("fylite_rs_with_axis_node",
     [_ARR, _U64, _ARR, _U64, _U64, _ARR, _ARR], _I32)
def with_axis_node(*, zero, repeat=()):
    """Prepend an AXIS NODE to a metric ladder — the layout a 1.5-D
    transport grid runs on.  Returns ``(zero_tuple, repeat_tuple)``.

    The traced ladder deliberately excludes the axis (the contour
    degenerates there), so every PDE consumer has to add one, and the fill
    splits the quantities in two — the split IS the rule:

    * ``zero`` — the ones that really are zero there: the labels ``ρ`` and
      ``ψ_N`` (the axis is the origin of both) and ``V' = dV/dρ`` (a volume
      derivative vanishes at a point);
    * ★★``repeat`` — the flux-surface AVERAGES, which do not.
      ``⟨|∇ρ|²⟩``, ``⟨|∇ρ|²/R²⟩``, ``F`` and ``q`` all tend to finite
      limits, so the innermost traced value is the available extrapolation.
      Zeroing one kills the flux metric ``V'⟨|∇ρ|²⟩`` TWICE at the one node
      every profile is read at — the operator already handles ``V' = 0``
      there, and a second zero is a different equation, not a safer one.

    >>> (rho, vp, psin), (gm3,) = with_axis_node(
    ...     zero=(rho, vp, psin), repeat=(gm3,))          # doctest: +SKIP
    """
    lib = require()
    z = [_f(np.atleast_1d(v)) for v in zero]
    r = [_f(np.atleast_1d(v)) for v in repeat]
    if not z:
        raise KernelError("with_axis_node: `zero` cannot be empty — a "
                          "ladder always carries at least its own label")
    n = z[0].size
    if any(v.size != n for v in z + r):
        raise KernelError(
            f"ragged ladder: {[int(v.size) for v in z + r]} against {n}")
    zf = _f(np.concatenate(z)) if z else np.zeros(0)
    rf = _f(np.concatenate(r)) if r else np.zeros(0)
    zo, ro = np.empty(len(z) * (n + 1)), np.empty(len(r) * (n + 1))
    rc = lib.fylite_rs_with_axis_node(zf, len(z), rf, len(r), n, zo, ro)
    if rc != 0:
        raise KernelError(f"fylite_rs_with_axis_node returned {rc}")
    return (tuple(zo.reshape(len(z), n + 1)),
            tuple(ro.reshape(len(r), n + 1)) if r else ())


_sig("fylite_rs_ohmic_power", [_ARR, _ARR, _U64, _ARR], _I32)
def ohmic_power(eta, j_par):
    """Ohmic heating ``η j_∥²`` [W/m³], to the electrons.

    ★The other half of the ohmic channel, beside :func:`spitzer_eta`: the
    pair is one statement — THIS resistivity times THIS current — and a
    channel whose halves live in different hosts is one whose neoclassical
    refinement can be applied to one half only.
    """
    lib = require()
    shape = np.shape(np.asarray(eta, float) * np.asarray(j_par, float))
    e = _f(np.broadcast_to(np.asarray(eta, float), shape))
    j = _f(np.broadcast_to(np.asarray(j_par, float), shape))
    out = np.empty(e.size)
    rc = lib.fylite_rs_ohmic_power(e, j, e.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_ohmic_power returned {rc}")
    return out.reshape(shape) if shape else float(out[0])


_sig("fylite_rs_quasi_neutral_ne", [_ARR, _ARR, _U64, _U64, _ARR], _I32)
def quasi_neutral_ne(z, ni):
    """Electron density from quasi-neutrality, ``n_e = Σ_s z_s n_s``.

    ``z`` is one charge number per species; ``ni`` is ``(n_species,
    n_points)``.

    ★★A STRUCTURAL closure, not a solvable channel: the electron density is
    never evolved by the transport solver, it is whatever the ions require.
    Summing the densities without the charge weight is the mistake this
    exists to have one place for — it understates the electrons by exactly
    the impurity charge.
    """
    lib = require()
    z_a = _f(np.atleast_1d(z))
    ni_a = _f(np.atleast_2d(ni))
    if ni_a.shape[0] != z_a.size:
        raise KernelError(f"{z_a.size} charge numbers against "
                          f"{ni_a.shape[0]} density rows")
    out = np.empty(ni_a.shape[1])
    rc = lib.fylite_rs_quasi_neutral_ne(z_a, ni_a.ravel(), z_a.size,
                                        out.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_quasi_neutral_ne returned {rc}")
    return out


_sig("fylite_rs_two_temperature_state_len", [_U64], _U64)
_sig("fylite_rs_two_temperature_init",
     [_ARR] * 9 + [_U64, _F64, _U64, _F64, _U64] + [_F64] * 4
     + [_U64, _ARR, _U64], _I32)
_sig("fylite_rs_two_temperature_next",
     [_ARR, _U64] + [_ARR] * 3 + [_U64, _ARR, _ARR], _I32)
_sig("fylite_rs_two_temperature_result",
     [_ARR, _U64, _U64] + [_ARR] * 4, _I32)
def two_temperature_march(rho, te, ti, *, ne, ni, vprime, gm3, q_e, q_i,
                          closure, dt: float, edge_te: float,
                          edge_ti: float, max_outer: int = 500,
                          tol_steady: float = 1e-9, n_coupling: int = 2,
                          d_pc: float = 0.0, tol: float = 1e-10,
                          max_inner: int = 60) -> dict:
    """The Te/Ti pair marched to steady — the outer loop of the heat channels.

    ``closure(rho, te, ti)`` returns ``(chi_e, chi_i, s_exchange)`` at that
    state: the diffusivities [m²/s] and the collisional e→i power density
    [W/m³], **positive to ions**.  Returns ``{te, ti, outer_steps, steady,
    delta, s_exchange}``.

    ★★The march is the KERNEL's and this is its pump.  ``closure`` stays a
    Python callable because a TGLF+NEO evaluation is not something the
    kernel can call — but that is a reason to evaluate χ here, not a reason
    to decide anything else here.  How many Picard passes the closure gets,
    which state each pass advances FROM, the steady test and the
    non-finite stop are all on the other side.

    ★The exchange rides with the closure rather than with the fixed source
    set because it depends on ``Te − Ti`` and so changes every pass; the
    kernel applies it in one place, negative to electrons and positive to
    ions.
    """
    lib = require()
    shape = np.shape(np.asarray(rho, float))
    arrs = [_f(np.broadcast_to(np.asarray(a, float), shape))
            for a in (rho, te, ti, ne, ni, vprime, gm3, q_e, q_i)]
    n = arrs[0].size
    nstate = int(lib.fylite_rs_two_temperature_state_len(n))
    state = np.zeros(nstate)
    rc = lib.fylite_rs_two_temperature_init(
        *arrs, n, float(dt), int(max_outer), float(tol_steady),
        int(n_coupling), float(edge_te), float(edge_ti), float(d_pc),
        float(tol), int(max_inner), state, nstate)
    if rc != 0:
        raise KernelError(_TWO_TEMP_ERRORS.get(
            rc, f"fylite_rs_two_temperature_init returned {rc}"))

    te_at, ti_at = arrs[1].copy(), arrs[2].copy()
    while True:
        chi_e, chi_i, s_exch = closure(arrs[0], te_at, ti_at)
        ce = _f(np.broadcast_to(np.asarray(chi_e, float), shape))
        ci = _f(np.broadcast_to(np.asarray(chi_i, float), shape))
        sx = _f(np.broadcast_to(np.asarray(s_exch, float), shape))
        req = lib.fylite_rs_two_temperature_next(state, nstate, ce, ci, sx,
                                                 n, te_at, ti_at)
        if req < 0:
            raise KernelError(_TWO_TEMP_ERRORS.get(
                req, f"fylite_rs_two_temperature_next returned {req}"))
        if req == 0:
            break

    te_o, ti_o, sx_o = (np.empty(n) for _ in range(3))
    info = np.empty(3)
    rc = lib.fylite_rs_two_temperature_result(state, nstate, n, te_o, ti_o,
                                              sx_o, info)
    if rc != 0:
        raise KernelError(f"fylite_rs_two_temperature_result returned {rc}")
    return {"te": te_o, "ti": ti_o, "outer_steps": int(info[0]),
            "steady": bool(info[1]), "delta": float(info[2]),
            "s_exchange": sx_o}


#: What the two-temperature march refuses, and why.
_TWO_TEMP_ERRORS = {
    -2: ("two_temperature_march: every profile must be the same length as "
         "rho, and rho needs at least two points"),
    -8: ("two_temperature_march: the FVM step failed — check the metrics "
         "(V', <|grad rho|^2>) and the densities for zeros"),
}

_sig("fylite_rs_label_drift", [_ARR, _U64, _F64, _F64, _ARR], _I32)
def label_drift(rho, *, b0: float, b0_dot: float):
    """``rho_dot|_Φ = −(ρ/2)(Ḃ₀/B₀)`` — how fast a FIXED surface's label moves.

    The ``B₀``-ramp half of the moving-metric pair.  A caller carries the
    term by adding ``−rho_dot`` to :func:`transport_step`'s ``velocity``
    (the operator already carries convections); the other half, ``dV'/dt``,
    is ``capacity_old``.

    ★``b0_dot = 0`` returns zeros — the term is a dead path by
    construction, not by a caller remembering not to pass it.
    """
    lib = require()
    r = _f(rho)
    out = np.empty(r.size)
    rc = lib.fylite_rs_label_drift(r, r.size, float(b0), float(b0_dot), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_label_drift returned {rc}")
    return out


_sig("fylite_rs_momentum_weights", [_ARR] * 5 + [_U64, _F64, _ARR], _I32)
def momentum_weights(*, vprime, dens, gm3, r2, mass: float, torque) -> dict:
    """The momentum channel's FVM weights — capacity, flux metric, source rate.

    ``C = V' n m ⟨R²⟩``, ``M = V'⟨|∇ρ|²⟩ n m ⟨R²⟩``, ``S = T/(n m ⟨R²⟩)``.
    ω is an angular frequency [rad/s] and ``torque`` a torque density
    [J/m³], so this is SI throughout — the one place it differs from the
    heat weights beyond the 3/2.
    """
    lib = require()
    shape = np.shape(np.asarray(vprime, float))
    a = [_f(np.broadcast_to(np.asarray(x, float), shape))
         for x in (vprime, dens, gm3, r2, torque)]
    n = a[0].size
    out = np.empty(3 * n)
    rc = lib.fylite_rs_momentum_weights(*a, n, float(mass), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_momentum_weights returned {rc}")
    return {"capacity": out[:n].copy(), "metric": out[n:2 * n].copy(),
            "source_rate": out[2 * n:].copy()}


_sig("fylite_rs_solve_momentum",
     [_ARR] * 8 + [_U64] + [_F64] * 3 + [_U64] + [_F64] * 3 + [_U64, _ARR],
     _I32)
def solve_momentum(rho, omega_init, *, vprime, gm3, r2, dens, mass: float,
                   chi_phi, torque=0.0, dt: float, edge: float,
                   max_outer: int = 500, tol_steady: float = 1e-9,
                   d_pc: float = 0.0, tol: float = 1e-10,
                   max_inner: int = 60) -> dict:
    """The toroidal-momentum channel, marched to steady — the kernel's.

    The same shape as :func:`solve_density`, with the momentum weights:
    a prescribed ``chi_phi`` (a momentum diffusivity is a TGLF output, not
    something this layer produces), backward Euler, the shared steady rule.
    """
    lib = require()
    shape = np.shape(np.asarray(rho, float))
    a = [_f(np.broadcast_to(np.asarray(x, float), shape))
         for x in (rho, omega_init, vprime, gm3, r2, dens, chi_phi, torque)]
    n = a[0].size
    out = np.empty(n + 3)
    rc = lib.fylite_rs_solve_momentum(*a, n, float(mass), float(dt),
                                      float(edge), int(max_outer),
                                      float(tol_steady), float(d_pc),
                                      float(tol), int(max_inner), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_solve_momentum returned {rc}")
    return {"omega": out[:n].copy(), "outer_steps": int(out[n]),
            "steady": bool(out[n + 1]), "delta": float(out[n + 2])}


#: What the core march refuses, and why.
_CORE_MARCH_ERRORS = {
    -2: ("core_march: every profile must be the same length as rho, rho "
         "needs at least three points, and at least one channel must be on"),
    -8: ("core_march: a channel's FVM step failed — check the metrics "
         "(V', <|grad rho|^2>, <|grad rho|^2/R^2>, F) and the densities "
         "for zeros"),
}

_sig("fylite_rs_core_march_state_len", [_U64, _U64], _U64)
#: ★The argument ORDER here is the Rust signature's, not a tidier one.  A
#: C call reads its arguments by position, and on this ABI integers and
#: floats travel in different register files — so a declaration that merely
#: has the right TYPES in the wrong order can still return a plausible
#: answer, which is the worst way for a marshalling bug to present.
_sig("fylite_rs_core_march_init",
     [_ARR] * 14 + [ctypes.c_void_p]
     + [_U64, _U64, _F64, _F64, _F64, _F64, _F64, _F64, _U64, _F64, _U64]
     + [_F64] * 6 + [_U64] + [_I32] * 3 + [_ARR, _U64], _I32)
_sig("fylite_rs_core_march_next",
     [_ARR, _U64] + [_ARR] * 7 + [_U64, _U64] + [_ARR] * 5, _I32)
_sig("fylite_rs_core_march_result",
     [_ARR, _U64, _U64, _U64] + [_ARR] * 8, _I32)
def core_march(rho, *, te, ti, ni, z=(1.0,), edge_ni=None, psi=0.0,
               vprime, vprime_old=None, gm3, gm2=1.0, fpol=1.0,
               b0: float = 1.0, b0_dot: float = 0.0, q_e=0.0, q_i=0.0,
               s_n=0.0, closure, dt: float, dt_target: float = 0.0,
               dt_min: float = 0.0, dt_max: float = 0.0,
               edge_te: float, edge_ti: float, edge_psi: float = 0.0,
               edge_psi_rate: float = 0.0, heat: bool = True,
               density: bool = False, current: bool = False,
               max_outer: int = 500, tol_steady: float = 1e-9,
               n_coupling: int = 2, d_pc: float = 0.0, tol: float = 1e-10,
               max_inner: int = 60) -> dict:
    """Every core channel marched on ONE time step — the kernel's.

    ``closure(state) -> dict`` is evaluated at the state the march reports
    and returns whichever of ``chi_e``, ``chi_i``, ``s_exchange``, ``d_n``,
    ``v_n``, ``sigma_par``, ``j_ni`` the switched-on channels need (anything
    omitted is zero).  ``state`` is ``{rho, te, ti, ne, psi}``.

    ★★Why this exists rather than three calls in a row: the heat capacity is
    ``(3/2)V'n``, so a density channel moving beside the temperatures moves
    the very weight they are solved with.  Here every channel advances from
    the same old state on the same ``dt``, the closure is iterated over all
    of them together, and the heat pair carries the density's motion — a
    Te-then-n split cannot express that and creates ``(3/2)V'T dn`` of
    energy per step.  The steady test is one rule over every ACTIVE channel.

    ``vprime_old`` is the metric the state ARRIVED on, when a caller
    re-traced it between rounds: the volume change is carried across the
    march's first outer step (``dV'/dt``) and the metric is then the one
    being marched on.  ``b0_dot`` [T/s] adds the label's own drift
    (:func:`label_drift`) to every channel's convection.  Both default off
    and are dead paths when they are.

    ★★``ni`` is ion-major (``n_ion × n``), ``z`` one charge per species and
    ``edge_ni`` one Dirichlet edge per species; ``s_n`` and the closure's
    ``d_n`` / ``v_n`` follow the same layout.  **The electron density is not
    a channel**: it is ``Σ Z_s n_s``, rebuilt whenever the ions move, which
    is the channel grammar's own rule and what lets an impurity transport
    differently from the main ion.

    ``dt_target`` switches the step-size controller ON: after each
    accepted outer step ``dt`` moves toward the step size that would have
    produced that relative change, clamped to ``[dt_min, dt_max]`` and by
    at most a factor of two either way.  ★It also turns a class of death
    into a slowdown — a non-finite state throws the step away, halves
    ``dt`` and retakes it — and zero (the default) is no controller at all
    rather than a gentle one.  The result reports the ``dt`` the march
    ended on and how many steps were retaken.

    ★The geometry does not move WITHIN a march — an evolving equilibrium
    arrives as new metrics on the next call, which is the scenario layer's
    alternation and not a moving frame.

    Returns ``{te, ti, ni, ne, psi, q, s_exchange, outer_steps, steady,
    delta, psi_repaired}``.
    """
    lib = require()
    shape = np.shape(np.asarray(rho, float))

    def arr(x):
        return _f(np.broadcast_to(np.asarray(x, float), shape))

    n = np.size(np.asarray(rho, float))
    zz = _f(np.atleast_1d(np.asarray(z, float)))
    n_ion = zz.size

    def ion_arr(x, fill):
        """An ion-major block, from a scalar, one profile, or the block."""
        v = np.asarray(fill if x is None else x, float)
        if v.size == n_ion * n:
            return _f(v.ravel())
        #: ★one profile for every species is a legal thing to MEAN, and so
        #: is a scalar; anything else is a caller who thinks the layout is
        #: something it is not, and gets told so here rather than at a
        #: numpy broadcast three frames down
        if v.size not in (1, n):
            raise KernelError(
                f"core_march: expected an ion-major block of {n_ion}x{n} "
                f"(or one profile of {n}, or a scalar), got {v.size}")
        return _f(np.tile(np.broadcast_to(v, shape), n_ion).ravel())

    a = [arr(x) for x in (rho, te, ti)]
    ni_b = ion_arr(ni, 0.0)
    edges = _f(np.broadcast_to(np.asarray(
        [np.asarray(ni, float).ravel()[(k + 1) * n - 1] for k in range(n_ion)]
        if edge_ni is None else np.atleast_1d(np.asarray(edge_ni, float)),
        float), (n_ion,)))
    a += [ni_b, zz, edges]
    a += [arr(x) for x in (psi, vprime, gm3, gm2, fpol, q_e, q_i)]
    a.append(ion_arr(s_n, 0.0))
    vp_old = None if vprime_old is None else arr(vprime_old)
    nstate = int(lib.fylite_rs_core_march_state_len(n, n_ion))
    state = np.zeros(nstate)
    rc = lib.fylite_rs_core_march_init(
        *a, None if vp_old is None else vp_old.ctypes.data,
        n, n_ion, float(b0), float(b0_dot), float(dt), float(dt_target),
        float(dt_min), float(dt_max), int(max_outer), float(tol_steady),
        int(n_coupling), float(edge_te), float(edge_ti),
        float(edge_psi), float(edge_psi_rate), float(d_pc), float(tol),
        int(max_inner), int(bool(heat)), int(bool(density)),
        int(bool(current)), state, nstate)
    if rc != 0:
        raise KernelError(_CORE_MARCH_ERRORS.get(
            rc, f"fylite_rs_core_march_init returned {rc}"))

    ne0 = np.zeros(n)
    for k in range(n_ion):
        ne0 += zz[k] * ni_b[k * n:(k + 1) * n]
    at = {"rho": a[0], "te": a[1].copy(), "ti": a[2].copy(),
          "ni": ni_b.copy(), "ne": ne0, "psi": _f(np.asarray(
              np.broadcast_to(np.asarray(psi, float), shape), float)).copy()}
    zero = np.zeros(n)
    while True:
        got = closure(at)
        c = [_f(np.broadcast_to(np.asarray(got.get(k, zero), float), shape))
             for k in ("chi_e", "chi_i", "s_exchange")]
        c += [ion_arr(got.get(k), 0.0) for k in ("d_n", "v_n")]
        c += [_f(np.broadcast_to(np.asarray(got.get(k, zero), float), shape))
              for k in ("sigma_par", "j_ni")]
        req = lib.fylite_rs_core_march_next(state, nstate, *c, n, n_ion,
                                            at["te"], at["ti"], at["ni"],
                                            at["ne"], at["psi"])
        if req < 0:
            raise KernelError(_CORE_MARCH_ERRORS.get(
                req, f"fylite_rs_core_march_next returned {req}"))
        if req == 0:
            break

    te_o, ti_o = np.empty(n), np.empty(n)
    ni_o = np.empty(n_ion * n)
    ne_o, psi_o, q_o, sx_o = (np.empty(n) for _ in range(4))
    info = np.empty(6)
    rc = lib.fylite_rs_core_march_result(state, nstate, n, n_ion, te_o, ti_o,
                                         ni_o, ne_o, psi_o, q_o, sx_o, info)
    if rc != 0:
        raise KernelError(f"fylite_rs_core_march_result returned {rc}")
    return {"te": te_o, "ti": ti_o,
            "ni": ni_o.reshape(n_ion, n) if n_ion > 1 else ni_o,
            "ne": ne_o, "psi": psi_o, "q": q_o,
            "s_exchange": sx_o, "outer_steps": int(info[0]),
            "steady": bool(info[1]), "delta": float(info[2]),
            "psi_repaired": float(info[3]), "dt": float(info[4]),
            "retries": int(info[5])}




_sig("fylite_rs_shape_observables", ([_F64] * 4 + [_U64, _U64, _ARR, _F64, _ARR, _U64, _ARR, _U64, _ARR, _U64] + [_F64] * 3 + [_ARR]), _I32)
def shape_observables(grid: Grid, psi, psi_bnd: float, *, gaps=(),
                      isoflux=(), angles=(), axis, angle_span: float = 1.2):
    """The observable vector a shape controller measures — the kernel's.

    ``gaps`` are ``(r0, z0, dr, dz)``, ``isoflux`` ``(r, z)``, ``angles``
    degrees from the magnetic axis.  The vector ends with the axis itself.

    ★★The isoflux conversion is the part worth naming: a flux error is in
    webers and a controller acts in metres, so it is divided by ``|∇ψ|``
    measured on a 1 mm stencil at the point.  A different stencil — or none
    — still gives a number that moves the right way, just scaled by
    something that varies over the boundary.
    """
    lib = require()
    f = _f(psi)
    if f.shape != (grid.nr, grid.nz):
        raise KernelError(f"psi has shape {f.shape}, expected "
                          f"{(grid.nr, grid.nz)}")
    gp = _f(np.asarray(gaps, float).reshape(-1, 4))
    iso = _f(np.asarray(isoflux, float).reshape(-1, 2))
    an = _f(np.atleast_1d(np.asarray(angles, float)).ravel())
    n = gp.shape[0] + iso.shape[0] + 2 * an.size + 2
    out = np.empty(n)
    rc = lib.fylite_rs_shape_observables(
        grid.r0, grid.z0, grid.dr, grid.dz, grid.nr, grid.nz, f.ravel(),
        float(psi_bnd), gp.ravel(), gp.shape[0], iso.ravel(), iso.shape[0],
        an, an.size, float(axis[0]), float(axis[1]), float(angle_span), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_shape_observables returned {rc}")
    return out


#: The MXH shape harmonics `geo_surface` accepts, in the order GEO stores
#: them: each name is followed by its radial shear `s_<name>`.
GEO_SHAPE_KEYS = (
    "cos0", "s_cos0", "cos1", "s_cos1", "cos2", "s_cos2", "cos3", "s_cos3",
    "cos4", "s_cos4", "cos5", "s_cos5", "cos6", "s_cos6",
    "sin3", "s_sin3", "sin4", "s_sin4", "sin5", "s_sin5", "sin6", "s_sin6",
)

#: The scalars `geo_surface` returns, in the order the ABI writes them.
GEO_SCALARS = ("f", "ffprime", "fsa_bp2", "fsa_bt2", "fsa_grad_r",
               "fsa_grad_r2", "grad_r0", "surf", "volume", "volume_prime",
               "bt0", "bp0")


_sig("fylite_rs_boundary_flux", [_ARR, _U64, _ARR, _U64, _ARR, _ARR, _ARR, _U64, _F64, _ARR], _I32)
def boundary_flux(grid_r, grid_z, psi, *, limiter_r, limiter_z,
                  sign_axis: float = 1.0) -> float:
    """The PHYSICAL boundary flux of a converged field [Wb].

    One rule for limited and diverted plasmas: the bottleneck-connectivity
    boundary.  ★On a diverted field it reads the X-point boundary that an
    in-loop max-flux rule misjudges as a too-tight limiter contact — the
    q95 root cause this repo chased once.
    """
    lib = require()
    rg, zg = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    lr, lz = _f(np.atleast_1d(limiter_r)), _f(np.atleast_1d(limiter_z))
    out = np.empty(1)
    rc = lib.fylite_rs_boundary_flux(rg, rg.size, zg, zg.size, _f(psi),
                                     lr, lz, lr.size, float(sign_axis), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_boundary_flux returned {rc}")
    return float(out[0])


_sig("fylite_rs_deltastar_apply", [_ARR, _U64, _ARR, _U64, _ARR, _ARR], _I32)
def deltastar_apply(grid_r, grid_z, psi):
    """Δ*ψ on the kernel's own stencil — the OPERATOR, not the solve.

    ``Δ* = R ∂/∂R (1/R ∂/∂R) + ∂²/∂Z²``, applied at interior points; the
    border comes back as zeros (the stencil is not defined there).

    ★It is here for T-C22.  The repo declares COCOS 17, and the check that
    needs neither the COCOS table nor anyone's memory is the kernel's own
    written equation on a real equilibrium:
    ``Δ*ψ = −μ0 R² p'(ψ) − F F'(ψ)``.  Re-writing the stencil in this host
    to get the left-hand side would have been a second spelling of the very
    operator under test.
    """
    rg = _f(np.asarray(grid_r, float).ravel())
    zg = _f(np.asarray(grid_z, float).ravel())
    p = _f(np.ascontiguousarray(np.asarray(psi, float)))
    if p.size != rg.size * zg.size:
        raise KernelError(
            f"psi is {p.size} long; the grid is {rg.size}x{zg.size}")
    out = np.zeros(p.size)
    rc = require().fylite_rs_deltastar_apply(rg, rg.size, zg, zg.size,
                                             p.ravel(), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_deltastar_apply returned {rc}")
    return out.reshape(rg.size, zg.size)


_sig("fylite_rs_deltastar_solve", [_ARR, _U64, _ARR, _U64, _ARR, _ARR], _I32)
def harmonic_interior(grid_r, grid_z, field):
    """Keep the border, replace the interior with the solution of
    ``Δ*ψ = 0``.

    ★A true external (vacuum) field is source-free on any region holding no
    conductors, so the non-harmonic content of an EXTRACTED vacuum is
    extraction noise (plasma-filament quantisation).  This projects it out
    without touching the real field — provided the interior really holds no
    sources: vessel currents inside the grid would be smeared.
    """
    lib = require()
    rg, zg = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    psi = _f(np.array(field, dtype=float, copy=True))
    rhs = np.zeros_like(psi)
    rc = lib.fylite_rs_deltastar_solve(rg, rg.size, zg, zg.size, psi, rhs)
    if rc != 0:
        raise KernelError(f"fylite_rs_deltastar_solve returned {rc}")
    return psi


#: ★the FSA-current entry: the plain inverse's argument list plus
#: `(xj, vzeroj, wj, n_j)`.  Registered beside the entry it extends, and
#: reached through the SAME Python door — `gs_inverse_solve` dispatches on
#: whether a current constraint was given, so there is one function here
#: and not two that differ by three arguments.
_sig("fylite_rs_gs_inverse_solve_fsa", [_ARR, _U64, _ARR, _U64, _ARR, _ARR, _ARR, _ARR, _U64, _F64, _U64, _U64, _F64, _ARR, _ARR, _U64, _ARR, _ARR, _ARR, _U64, _ARR, _U64, _ARR, _ARR, _ARR, _U64, _F64, _U64, _F64, _F64, _F64, _F64, _U64, _ARR, _ARR, _ARR], _I32)
_sig("fylite_rs_gs_inverse_solve", [ _ARR, _U64, _ARR, _U64, _ARR, _ARR, _ARR, _ARR, _U64, _F64, _U64, _U64, _F64, _ARR, _ARR, _U64, _ARR, _ARR, _ARR, _U64, _ARR, _U64, _F64, _U64, _F64, _F64, _F64, _F64, _U64, _ARR, _ARR, _ARR], _I32)
def gs_inverse_solve(grid_r, grid_z, psi_ext, *, loops_m, meas, weights,
                     meas_scale: float, npp: int, nff: int, ip: float,
                     limiter_r, limiter_z, pressure_x=None,
                     pressure_meas=None, pressure_weights=None,
                     j_prescribed=None, current_x=None,
                     current_shape=None, current_weights=None,
                     relax: float = 0.3,
                     max_iter: int = 600, tol: float = 1e-9,
                     fb_gain: float = 8.0, zc_anchor=None, rc_anchor=None,
                     warmup: int = 0) -> dict:
    """One inverse Grad-Shafranov solve: fit ``npp + nff`` polynomial
    ``p′``/``FF′`` coefficients to flux-loop measurements under the ``Ip``
    constraint.

    Returns :data:`INVERSE_KEYS` plus ``psi``, ``coefficients`` and
    ``iterations`` — :data:`INVERSE_FSA_KEYS` (one more slot named) when a
    current constraint was given.  ``pressure_*`` add the kinetic constraint
    rows, ``j_prescribed`` the per-interior-cell neoclassical current, and
    ``current_*`` the flux-surface-averaged current SHAPE; each is optional
    and omitted means "that constraint is off", not "that constraint is
    zero".

    ``current_x`` / ``current_shape`` / ``current_weights`` are one row
    each: a normalised flux label, the value ``⟨j_φ/R⟩/⟨1/R⟩`` is asked to
    take there RELATIVE to its own mean over the same surfaces, and the
    row's weight.  ★The constraint is homogeneous on purpose — it states a
    shape and nothing about magnitude, which stays entirely with the ``Ip``
    equality.  ``fsa_rows_used`` reports how many of those rows reached the
    fit; a surface that could not be traced (the magnetic axis, where the
    contour degenerates to a point) carries none.

    ★This was the last entry a module outside this one still called
    directly, with its own buffers and its own return-code check.  The
    inverse solve is the most argument-heavy entry in the ABI, which is
    precisely why its marshalling should exist once.
    """
    lib = require()
    rg, zg = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    lr, lz = _f(np.atleast_1d(limiter_r)), _f(np.atleast_1d(limiter_z))
    b, w = _f(np.atleast_1d(meas)), _f(np.atleast_1d(weights))
    if w.size != b.size:
        raise KernelError(f"{b.size} measurements against {w.size} weights")
    have_p = pressure_x is not None
    xp = _f(np.atleast_1d(pressure_x)) if have_p else np.zeros(1)
    pm = _f(np.atleast_1d(pressure_meas)) if have_p else np.zeros(1)
    pw = _f(np.atleast_1d(pressure_weights)) if have_p else np.zeros(1)
    if have_p and not (xp.size == pm.size == pw.size):
        raise KernelError(
            f"pressure rows disagree: x {xp.size}, meas {pm.size}, "
            f"weights {pw.size}")
    ncell = (rg.size - 2) * (zg.size - 2)
    if j_prescribed is None:
        jp = np.zeros(1)
    else:
        jp = _f(np.atleast_1d(j_prescribed))
        if jp.size != ncell:
            raise KernelError(
                f"j_prescribed has {jp.size} cells, expected {ncell} = "
                "(nr-2)*(nz-2) — it is per INTERIOR cell, matching the "
                "solver's own mask")
    #: ★the FSA-current block, same optional-triple convention as the
    #: pressure one: all three or none, and the lengths must agree — a
    #: shape without the surfaces it is a shape ON is not a constraint.
    have_j = current_x is not None
    if have_j != (current_shape is not None):
        raise KernelError("current_x and current_shape go together: a shape "
                          "without the surfaces it is a shape ON constrains "
                          "nothing")
    if have_j:
        xj = _f(np.atleast_1d(current_x))
        vz = _f(np.atleast_1d(current_shape))
        wj = (np.ones_like(xj) if current_weights is None
              else _f(np.atleast_1d(current_weights)))
        if not (xj.size == vz.size == wj.size):
            raise KernelError(
                f"current_x/current_shape/current_weights have sizes "
                f"{xj.size}/{vz.size}/{wj.size} — they are one row each")
    else:
        xj = vz = wj = _f(np.zeros(1))

    psi = np.empty((rg.size, zg.size))
    coefs, out = np.empty(int(npp) + int(nff)), np.empty(12)
    common = (rg, rg.size, zg, zg.size, _f(psi_ext), _f(loops_m), b, w,
              b.size, float(meas_scale), int(npp), int(nff), float(ip),
              lr, lz, lr.size, xp, pm, pw, xp.size if have_p else 0,
              jp, jp.size if j_prescribed is not None else 0)
    tail = (float(relax), int(max_iter), float(tol), float(fb_gain),
            float("nan") if zc_anchor is None else float(zc_anchor),
            float("nan") if rc_anchor is None else float(rc_anchor),
            int(warmup), psi, coefs, out)
    if have_j:
        name = "fylite_rs_gs_inverse_solve_fsa"
        it = lib.fylite_rs_gs_inverse_solve_fsa(
            *common, xj, vz, wj, xj.size, *tail)
    else:
        name = "fylite_rs_gs_inverse_solve"
        it = lib.fylite_rs_gs_inverse_solve(*common, *tail)
    if it <= 0:
        raise KernelError(f"{name} returned {it}")
    res = dict(zip(INVERSE_FSA_KEYS if have_j else INVERSE_KEYS, out))
    res.pop("_", None)
    res.update(psi=psi, coefficients=coefs, iterations=int(it))
    if have_j:
        #: ★how many rows REACHED the fit, not how many were asked for: a
        #: surface that could not be traced carries none, and a caller
        #: reading the fit as if all of them held would be reading a
        #: constraint that was never imposed.
        res["fsa_rows_used"] = int(res["fsa_rows_used"])
    return res


#: What `gs_free_solve` writes, in the order the ABI packs them.
#: ★v108 (T-M16): slot 11 — reserved padding since the entry existed — now
#: carries the solver's own verdict: 1 = converged (residual within `tol`
#: AND the plasma mask unchanged for consecutive rounds), 2 = settled (the
#: answer stopped moving but mask quantisation jitter floors the residual
#: above `tol` — a steady-state reading, not a met tolerance), 0 = neither.
FREE_SOLVE_KEYS = ("psi_axis", "psi_bnd", "axis_r", "axis_z", "ip",
                   "residual", "bnd_kind", "xpt_r", "xpt_z", "fb_amp",
                   "zc", "verdict")

#: What the INVERSE entry's `out12` carries — its own tuple, for the reason
#: `INVERSE_COIL_KEYS` has one: the free solve packs an X-point into slots
#: 7-8 and the inverse packs the feedback amplitude into 7.
#:
#: ★★This tuple is a FIX, not just an addition.  `gs_inverse_solve` used to
#: name its buffer with `FREE_SOLVE_KEYS`, so `res["xpt_r"]` carried the
#: feedback amplitude and `res["fb_amp"]` carried a hard 0.0 — a delivered
#: reconstruction reported `fb_amp: 0.0` on every shot, and the number was
#: never anything else.  The mislabel was known and written down beside
#: `INVERSE_COIL_KEYS` (「is how res["xpt_r"] came to mean fb_amp on this
#: entry's older sibling」) and left standing; it survived because a SHARED
#: tuple cannot be checked against two different write orders — the row-order
#: checker was verifying it against `gs_free_solve`, where it is correct.
#: ★slots 10-11 carry the RADIAL feedback's amplitude and the CONDIN
#: truncation's kept-mode count, on all three inverse entries.  `fb_amp_r`
#: went unreported for the whole life of these entries — three comments in
#: this tree named that as a defect before it was fixed — and `trunc_keep`
#: is what makes a higher-order basis's failure legible: it dies upstream of
#: the boundary rule, in how many directions the fit was allowed to move.
INVERSE_KEYS = ("psi_axis", "psi_bnd", "axis_r", "axis_z", "ip",
                "residual", "bnd_kind", "fb_amp", "_", "_",
                "fb_amp_r", "trunc_keep")

#: :data:`INVERSE_KEYS` with slot 8 — the first the base entry leaves as
#: padding — carrying how many FSA-current rows REACHED the fit.  Same
#: vocabulary, one more slot filled: the constrained and unconstrained calls
#: must not answer to two different sets of names.
INVERSE_FSA_KEYS = ("psi_axis", "psi_bnd", "axis_r", "axis_z", "ip",
                    "residual", "bnd_kind", "fb_amp", "fsa_rows_used",
                    "_", "fb_amp_r", "trunc_keep")

#: What `gs_free_solve_tab` writes: the free solve's slots plus the mask
#: cells that changed on the last round (NaN when only one round ran) and
#: the final Ip normalisation `j_c` (actual p' = j_c · p'_table).
FREE_SOLVE_TAB_KEYS = ("psi_axis", "psi_bnd", "axis_r", "axis_z", "ip",
                       "residual", "bnd_kind", "xpt_r", "xpt_z", "fb_amp",
                       "zc", "verdict", "mask_delta", "jc")


_sig("fylite_rs_gs_free_solve", [_ARR, _U64, _ARR, _U64, _ARR, _F64, _F64, _F64, _F64, _F64, _ARR, _ARR, _U64, _F64, _F64, _U64, _F64, _F64, _F64, _F64, _VOID, _ARR, _ARR], _I32)
def gs_free_solve(grid_r, grid_z, psi_ext, *, ip: float, limiter_r,
                  limiter_z, beta0: float = 0.55, emp: float = 1.0,
                  enp: float = 1.0, r0: float = 1.75, relax: float = 0.3,
                  max_iter: int = 600, tol: float = 1e-9,
                  fb_gain: float = 8.0, zc_anchor=None,
                  rc_anchor=None, psi_init=None) -> dict:
    """One free-boundary Grad-Shafranov solve.

    ``zc_anchor`` is a measured current-centroid Z [m] (EFIT's ``zcurrt``):
    given, the vertical feedback holds the centroid THERE rather than
    self-anchoring, and ``fb_amp`` reports what that cost.

    ``psi_init`` warm-starts the iterate.  It matters for one caller and
    matters a great deal there: a boundary DESIGN's coil field has to
    cancel the plasma's own flux variation over the requested boundary, so
    it has a minimum where the plasma belongs — and the axis search on
    iteration zero, which sees only the coils, then locks onto a maximum
    out by the coils and every later pass is self-consistently wrong.
    Passing the field the design was made with (coils plus its filament
    cloud) puts the axis where the design put it.

    Raises rather than returning a non-converged field — ★a GS solve that
    ran out of iterations is not a weaker answer, it is a different object.
    """
    lib = require()
    rg, zg = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    lr, lz = _f(np.atleast_1d(limiter_r)), _f(np.atleast_1d(limiter_z))
    psi = np.empty((rg.size, zg.size))
    init_a = None if psi_init is None else _f(np.ascontiguousarray(psi_init))
    out = np.empty(12)
    it = lib.fylite_rs_gs_free_solve(
        rg, rg.size, zg, zg.size, _f(psi_ext), float(beta0), float(emp),
        float(enp), float(r0), float(ip), lr, lz, lr.size, 1.0,
        float(relax), int(max_iter), float(tol), float(fb_gain),
        float("nan") if zc_anchor is None else float(zc_anchor),
        float("nan") if rc_anchor is None else float(rc_anchor),
        #: optional pointer, the same way every other optional array on this
        #: boundary is passed: a null, not an empty array
        None if init_a is None else init_a.ctypes.data, psi, out)
    if it <= 0:
        raise KernelError(f"fylite_rs_gs_free_solve returned {it}")
    res = dict(zip(FREE_SOLVE_KEYS, out))
    res.update(psi=psi, iterations=int(it),
               #: the kernel's own verdict (T-M16) — `residual <= tol`
               #: computed here would miss the mask half of the state
               converged=res["verdict"] == 1.0,
               settled=res["verdict"] == 2.0)
    return res


_sig("fylite_rs_gs_free_solve_tab",
     [_ARR, _U64, _ARR, _U64, _ARR, _ARR, _ARR, _ARR, _U64, _F64, _ARR,
      _ARR, _U64, _F64, _F64, _U64, _F64, _F64, _F64, _F64, _VOID, _ARR,
      _ARR], _I32)
def gs_free_solve_tab(grid_r, grid_z, psi_ext, *, x, pprime, ffprime,
                      ip: float, limiter_r, limiter_z, relax: float = 0.3,
                      max_iter: int = 600, tol: float = 1e-9,
                      fb_gain: float = 8.0, zc_anchor=None,
                      rc_anchor=None, psi_init=None) -> dict:
    """The free-boundary solve on a TABULATED p'/FF' pair used as a shape
    (T-D6′).

    ``x`` (ascending in [0, 1]), ``pprime``, ``ffprime`` sample the
    delivered profiles; the table is normalised to ``ip`` every round, so
    its GAUGE — per-radian vs full flux, overall sign, any constant
    factor — divides out and only the relative radial structure survives,
    including a sign reversal (the delivered EAST #137985 profiles cross
    zero at psi_N ≈ 0.82, which no analytic-family member can represent).

    Everything else exactly as :func:`gs_free_solve`; the returned dict
    additionally carries ``mask_delta`` — mask cells changed on the last
    round (NaN when only one round ran).
    """
    lib = require()
    rg, zg = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    lr, lz = _f(np.atleast_1d(limiter_r)), _f(np.atleast_1d(limiter_z))
    xa = _f(np.atleast_1d(x))
    pa, fa = _f(np.atleast_1d(pprime)), _f(np.atleast_1d(ffprime))
    if not (xa.size == pa.size == fa.size):
        raise KernelError("x, pprime, ffprime must be the same length")
    psi = np.empty((rg.size, zg.size))
    init_a = None if psi_init is None else _f(np.ascontiguousarray(psi_init))
    out = np.empty(14)
    it = lib.fylite_rs_gs_free_solve_tab(
        rg, rg.size, zg, zg.size, _f(psi_ext), xa, pa, fa, xa.size,
        float(ip), lr, lz, lr.size, 1.0, float(relax), int(max_iter),
        float(tol), float(fb_gain),
        float("nan") if zc_anchor is None else float(zc_anchor),
        float("nan") if rc_anchor is None else float(rc_anchor),
        None if init_a is None else init_a.ctypes.data, psi, out)
    if it <= 0:
        raise KernelError(f"fylite_rs_gs_free_solve_tab returned {it}")
    res = dict(zip(FREE_SOLVE_TAB_KEYS, out))
    res.update(psi=psi, iterations=int(it),
               converged=res["verdict"] == 1.0,
               settled=res["verdict"] == 2.0)
    return res


#: ★ADDED 2026-08-23 (T-M7).  The boxed fixed-boundary solve — the axis
#: searched only where the plasma already is, the plasma taken by
#: connectivity.  `fylite_rs_gs_fixed_solve` next door searches the whole
#: rectangle and takes the threshold set `0 <= psibar < 1`, which is right
#: on a machine grid and wrong on a box cut around one plasma.
_sig("fylite_rs_gs_fixed_box",
     ([_ARR, _U64, _ARR, _U64] + [_F64] * 2 + [_ARR] + [_F64] * 4
      + [_VOID, _VOID, _U64, _VOID, _U64, _ARR, _U64, _F64, _ARR, _U64,
         _F64, _F64, _U64, _F64, _U64, _F64, _ARR]), _I32)
#: ★T-M17: the same solve under an I_p constraint — one extra f64 (the
#: target) before the out buffer, out8 instead of out6
_sig("fylite_rs_gs_fixed_box_ip",
     ([_ARR, _U64, _ARR, _U64] + [_F64] * 2 + [_ARR] + [_F64] * 4
      + [_VOID, _VOID, _U64, _VOID, _U64, _ARR, _U64, _F64, _ARR, _U64,
         _F64, _F64, _U64, _F64, _U64, _F64, _F64, _ARR]), _I32)
def gs_fixed_box(grid_r, grid_z, psi, *, psi_boundary: float,
                 sign_axis: float, seed_r: float, seed_z: float,
                 pprime, ffprime, x=None, pprime_scale: float = 1.0,
                 ffprime_scale: float = 1.0,
                 limiter_r=None, limiter_z=None, dr=None, dz=None,
                 gauge: float = 1.0, dilate: int = 2, relax: float = 0.5,
                 max_iter: int = 300, tol: float = 1e-9,
                 ip_target: float | None = None) -> dict:
    """Fixed-boundary Picard on a SUB-BOX (`equilibrium::solve_fixed_box`).

    ``psi`` carries the Dirichlet border in; the solved field comes back in
    the returned dict rather than in place.

    ★Two rules that are not ``fylite_rs_gs_fixed_solve``'s.  The axis is the
    extremum of ``sign_axis * psi`` inside a dilation of the PREVIOUS
    iterate's plasma, seeded at ``(seed_r, seed_z)`` — "the axis is a
    continuous object; it does not teleport" — and the plasma is what is
    CONNECTED to it above ``psi_boundary``, not the threshold set.  On a box
    cut tightly around one plasma the whole-rectangle rule takes a corner
    (measured on EAST: the axis sits 0.774 Wb above ``psi_b`` while the
    box's own outboard corner sits 0.916 Wb below it) and the threshold set
    becomes an annulus outside the separatrix.

    ★The profiles are ``dp/dpsibar`` [Pa] and ``d(F^2/2)/dpsibar``
    [T^2 m^2] — per NORMALISED flux — as monomial coefficients, or as values
    on ``x`` when that is given.  ``gauge`` is how many radians of psi one
    unit of ``psi`` holds: ``2*pi`` for total flux [Wb], ``1`` per radian.

    ``dr``/``dz`` default to the box's own node spacing; pass the PARENT
    grid's when the box is a window on a larger one and the two must agree
    to the last bit.

    Raises :class:`KernelError` on a refusal, naming which one: the seed is
    not an interior node, the plasma reached the box border, the dilation
    held no interior node, or the flux span collapsed.
    """
    lib = require()
    rg, zg = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    p = _f(np.asarray(psi, float)).copy()
    if p.size != rg.size * zg.size:
        raise KernelError(f"psi holds {p.size} values, expected "
                          f"{rg.size} x {zg.size}")
    pp, ffp = _f(np.atleast_1d(pprime)), _f(np.atleast_1d(ffprime))
    xs = None if x is None else _f(np.atleast_1d(x))
    lr = None if limiter_r is None else _f(np.atleast_1d(limiter_r))
    lz = None if limiter_z is None else _f(np.atleast_1d(limiter_z))
    nlim = 0 if lr is None else lr.size
    out = np.empty(8)
    head = [rg, rg.size, zg, zg.size,
            float(rg[1] - rg[0]) if dr is None else float(dr),
            float(zg[1] - zg[0]) if dz is None else float(dz),
            p, float(psi_boundary), float(sign_axis), float(seed_r),
            float(seed_z),
            None if lr is None else lr.ctypes.data,
            None if lz is None else lz.ctypes.data, nlim,
            None if xs is None else xs.ctypes.data,
            0 if xs is None else xs.size,
            pp, pp.size, float(pprime_scale), ffp, ffp.size,
            float(ffprime_scale),
            float(gauge), int(dilate), float(relax), int(max_iter),
            float(tol)]
    #: ★T-M17: a finite target routes through the CONSTRAINED entry — the
    #: FF' constant is solved each iterate so I_p lands on the target (the
    #: current the Dirichlet border was computed for); see the c_api note.
    if ip_target is None:
        it = lib.fylite_rs_gs_fixed_box(*head, out)
    else:
        it = lib.fylite_rs_gs_fixed_box_ip(*head, float(ip_target), out)
    if it < 0:
        why = {-3: "the seed is not an interior node of the box",
               -4: "the plasma reached the box border",
               -5: "the axis search found no interior node",
               -6: "the flux span collapsed"}.get(
                   it, f"code {it}")
        raise KernelError(f"fylite_rs_gs_fixed_box refused: {why}")
    return {"psi": p.reshape(rg.size, zg.size), "psi_axis": float(out[0]),
            "axis_r": float(out[1]), "axis_z": float(out[2]),
            "ip": float(out[3]), "residual": float(out[4]),
            "span": float(out[5]), "iterations": int(it),
            #: what the constraint did (zeros when no target was given):
            #: the FF' constant it solved and the unshifted current
            "ff_shift": float(out[6]) if ip_target is not None else 0.0,
            "ip_raw": float(out[7]) if ip_target is not None
                      else float(out[3])}


_sig("fylite_rs_geo_surface", [_F64] * 14 + [_ARR, _U64, _ARR], _I32)
_sig("fylite_rs_geo_surface_r2", [_F64] * 14 + [_ARR, _U64, _ARR], _I32)
_sig("fylite_rs_geo_surface_gm2", [_F64] * 14 + [_ARR, _U64, _ARR], _I32)
def geo_surface(*, rmin_over_a, rmaj_over_a, q, shear, drmaj=0.0,
                zmag=0.0, dzmag=0.0, kappa=1.0, s_kappa=0.0,
                delta=0.0, s_delta=0.0, zeta=0.0, s_zeta=0.0,
                shape=None, signb=1.0, ntheta: int = 1001) -> dict:
    """Flux-surface averages of one local Miller/MXH surface — GACODE's GEO.

    Returns ``{f, ffprime, fsa_bp2, fsa_bt2, fsa_grad_r, fsa_grad_r2,
    grad_r0, surf, volume, volume_prime, bt0, bp0, fsa_r2,
    fsa_grad_r2_over_r2}``: ``f = R·B_t``,
    ``volume_prime = dV/dr``, and ``bt0``/``bp0`` the fields at ``θ = 0``
    **normalised to B_unit** (multiply by it for tesla).

    ★``bt0`` is what the synchrotron formula wants — ``f/R0`` is not the
    same thing and is ~20 % away from it.

    ★★This is a PURE FUNCTION, and that is a difference from the library it
    was translated from: libgeo carried the MXH harmonics in module state,
    so its binding had to re-set all twenty-two on every call or a surface
    would inherit the previous one's.  Nothing here can.
    """
    lib = require()
    unknown = set(shape or ()) - set(GEO_SHAPE_KEYS)
    if unknown:
        raise KernelError(f"unknown shape harmonic(s) {sorted(unknown)}; "
                          f"expected a subset of {GEO_SHAPE_KEYS}")
    coef = _f(np.array([float((shape or {}).get(k, 0.0))
                        for k in GEO_SHAPE_KEYS]))
    out = np.empty(16)
    rc = lib.fylite_rs_geo_surface_gm2(
        float(signb), float(rmin_over_a), float(rmaj_over_a), float(drmaj),
        float(zmag), float(dzmag), float(q), float(shear), float(kappa),
        float(s_kappa), float(delta), float(s_delta), float(zeta),
        float(s_zeta), coef, int(ntheta), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_geo_surface_gm2 returned {rc}")
    res = dict(zip(GEO_SCALARS, (float(v) for v in out[:len(GEO_SCALARS)])))
    #: ★``fsa_r2`` = ``<R^2>`` (T-M8), in the units ``rmin``/``rmaj`` went in
    #: as; ``fsa_grad_r2_over_r2`` = ``<|grad r|^2/R^2>`` = IMAS ``gm2``, the
    #: current channel's own weight (S-2c), in their inverse square.  Both
    #: ride on the widest of the three geo entries rather than on
    #: ``..._geo_surface``, whose 14-slot out-buffer is part of its frozen
    #: contract; all three call the same ``geometry::solve``.  They are
    #: appended to the dict rather than added to ``GEO_SCALARS``, because
    #: that tuple is the ABI's slot ORDER for the OLDEST entry.
    #:
    #: ★★``gm2`` is a column and not a derivation: it is NOT
    #: ``fsa_grad_r2 / fsa_r2`` (the average of a ratio is not the ratio of
    #: the averages — 5 % apart on a circle at R0/a = 6), so a host that
    #: divided one by the other would write a wrong current-diffusion
    #: coefficient whose only symptom is a wrong q.
    res["fsa_r2"] = float(out[14])
    res["fsa_grad_r2_over_r2"] = float(out[15])
    return res


_sig("fylite_rs_bound_deriv", [_ARR, _ARR, _U64, _ARR], _I32)
def bound_deriv(f, r):
    """``df/dr`` by the derivative of the 3-point Lagrange polynomial.

    ★NOT :func:`numpy.gradient`: that is a 2-point centred difference in the
    interior and a FIRST-order one-sided difference at the ends — exactly
    where ``b_unit`` and the shear parameters are most sensitive.
    """
    lib = require()
    f_a, r_a = _f(np.atleast_1d(f)), _f(np.atleast_1d(r))
    out = np.empty(r_a.size)
    rc = lib.fylite_rs_bound_deriv(f_a, r_a, r_a.size, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_bound_deriv returned {rc}")
    return out


_sig("fylite_rs_gyrobohm", [_ARR, _ARR, _ARR, _U64, _F64, _ARR], _I32)
def gyrobohm(te_kev, ne_1e19, b_unit, a: float) -> dict:
    """The gyro-Bohm units a flux comparison happens in.

    ★``a`` is the minor radius of the LAST closed surface, not of the
    outermost solved one — getting that wrong scales ``chi_gb`` by a/a′ and
    ``q_gb`` by its square.
    """
    lib = require()
    te, ne, bu = (_f(np.atleast_1d(x)) for x in (te_kev, ne_1e19, b_unit))
    out = np.empty(8 * te.size)
    rc = lib.fylite_rs_gyrobohm(te, ne, bu, te.size, float(a), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_gyrobohm returned {rc}")
    rows = out.reshape(8, -1)
    return dict(zip(("cs", "rhos") + GYROBOHM_ROWS, [r.copy() for r in rows]))


_sig("fylite_rs_bundle_derive", [_ARR, _U64, _ARR, _ARR, _U64, _ARR, _F64, _U64] + [_ARR] * 4, _I32)
def bundle_derive(prof: dict, *, ni, ti, mxh=None, torfluxa: float,
                  ntheta: int = 1001) -> dict:
    """Derived geometry + gyro-Bohm units from a profile set — the kernel's.

    ``prof`` carries ``rmin rmaj q rho zmag kappa delta zeta ne te w0`` on
    one radial grid; ``ni``/``ti`` are ``(n_ion, n_rad)``; ``mxh`` is the
    optional extended-harmonic set keyed by :data:`MXH_HARMONICS`.

    ★A port of GACODE's ``expro_compute_derived``: same formulas, the same
    three-point derivative, and the flux-surface metrics from GEO.  The axis
    is degenerate for GEO — V and V′ vanish there — so the metrics that do
    not vanish are extrapolated from their two neighbours rather than
    evaluated on a surface with no interior.
    """
    lib = require()
    keys = ("rmin", "rmaj", "q", "rho", "zmag", "kappa", "delta", "zeta",
            "ne", "te", "w0")
    n = np.size(prof["rmin"])
    rows = []
    for k in keys:
        v = prof.get(k)
        if v is None:
            v = np.ones(n) if k == "kappa" else np.zeros(n)
        rows.append(np.broadcast_to(np.asarray(v, float), (n,)))
    p_a = _f(np.ascontiguousarray(np.stack(rows)))
    ni_a = _f(np.atleast_2d(np.asarray(ni, float)))
    ti_a = _f(np.broadcast_to(np.atleast_2d(np.asarray(ti, float)),
                              ni_a.shape))
    n_ion = ni_a.shape[0]
    mxh = mxh or {}
    mx = _f(np.stack([np.broadcast_to(np.asarray(mxh.get(h, 0.0), float), (n,))
                      for h in MXH_HARMONICS]))
    out = np.empty(21 * n)
    gb = np.empty(6 * n)
    ion = np.empty(2 * n_ion * n)
    shear = np.empty(11 * n)
    rc = lib.fylite_rs_bundle_derive(p_a.ravel(), n, ni_a.ravel(),
                                     ti_a.ravel(), n_ion, mx.ravel(),
                                     float(torfluxa), int(ntheta),
                                     out, gb, ion, shear)
    if rc != 0:
        raise KernelError(f"fylite_rs_bundle_derive returned {rc}")
    res = {k: v.copy() for k, v in zip(BUNDLE_ROWS, out.reshape(21, n))}
    res.update({k: v.copy() for k, v in zip(GYROBOHM_ROWS, gb.reshape(6, n))})
    ion = ion.reshape(2, n_ion, n)
    res["dlnnidr"] = ion[0].copy()
    res["dlntidr"] = ion[1].copy()
    res.update({f"shape_s{h}": v.copy()
                for h, v in zip(MXH_HARMONICS, shear.reshape(11, n))})
    return res


_sig("fylite_rs_null_disc", [_F64] * 3 + [_U64, _U64, _ARR, _ARR], _I32)
def null_disc(r0: float, z0: float, radius: float, *, n_ring: int = 4,
              n_theta: int = 16):
    """The disc a field null is JUDGED on: centre, then concentric rings.

    ★Part of the design, not a plotting detail: "|B| below a few mT" means
    nothing without "over what region", and the radius and the two counts
    are exactly what fixes that region.
    """
    lib = require()
    n = 1 + int(n_ring) * int(n_theta)
    r, z = np.empty(n), np.empty(n)
    rc = lib.fylite_rs_null_disc(float(r0), float(z0), float(radius),
                                 int(n_ring), int(n_theta), r, z)
    if rc != 0:
        raise KernelError(f"fylite_rs_null_disc returned {rc}")
    return r, z


_sig("fylite_rs_channel_field", ([_ARR] * 6 + [_U64, _ARR, _U64] + [_ARR, _ARR, _U64, _U64, _U64] + [_ARR] * 3), _I32)
def channel_field(elems, weights, pr, pz, *, nu: int = 3, nv: int = 3):
    """Per-CHANNEL ``(psi, B_r, B_z)`` at points — ``(npts, nch)`` each.

    ``elems`` is the six-array conductor layout, ``weights`` the
    ``(n_channel, n_element)`` map.  Two of EAST's twelve channels drive a
    PAIR of deck elements, which is why folding is a matrix and not a
    relabelling.

    ★★The map is ``(n_channel, n_element)`` HERE, as it is at every other
    host-side entry that takes it (:func:`channel_weights` produces that
    shape, :func:`channel_fold` and :func:`channel_matrices` consume it).
    The wire format for THIS entry is the transpose, and that transpose
    happens on the marshalling line below — where a wire format belongs.  It
    used to be the caller's, which is how one package came to hold both
    orientations of one map with nothing naming which was which: a
    transposed weight matrix does not raise, it is a different machine.
    """
    lib = require()
    ea = [_f(np.atleast_1d(x)) for x in elems]
    ne = ea[0].size
    w_map = np.atleast_2d(np.asarray(weights, float))
    if w_map.shape[1] != ne:
        raise KernelError(f"weights has {w_map.shape[1]} columns, expected "
                          f"{ne} (one per element); the map is "
                          f"(n_channel, n_element)")
    nch = w_map.shape[0]
    wt = _f(w_map.T)
    r_a, z_a = _f(np.atleast_1d(pr).ravel()), _f(np.atleast_1d(pz).ravel())
    npts = r_a.size
    psi, br, bz = (np.empty(npts * nch) for _ in range(3))
    rc = lib.fylite_rs_channel_field(*ea, ne, wt.ravel(), nch, r_a, z_a,
                                     npts, int(nu), int(nv), psi, br, bz)
    if rc != 0:
        raise KernelError(f"fylite_rs_channel_field returned {rc}")
    return (psi.reshape(npts, nch), br.reshape(npts, nch),
            bz.reshape(npts, nch))


_sig("fylite_rs_breakdown_design", ([_ARR] * 6 + [_U64, _ARR, _U64] + [_F64] * 3 + [_U64, _U64] + [_F64] * 5 + [_VOID, _VOID] + [_U64, _U64] + [_ARR] * 3 + [_VOID]), _I32)
def breakdown_design(elems, weights, *, r0: float, z0: float = 0.0,
                     radius: float = 0.3, n_ring: int = 4, n_theta: int = 16,
                     b_tol: float = 2.0e-3, flux_target=None,
                     weight_null: float = 1.0, weight_flux: float = 1.0,
                     lam: float = 1e-12, x_ref=None, i_max=None,
                     nu: int = 3, nv: int = 3, disc: bool = True) -> dict:
    """A whole field-null design, from the conductor geometry.

    Samples the judging disc, evaluates the coils' response on it, folds it
    onto channels, assembles the scaled rows, solves under the per-channel
    box, and reports what the answer ACHIEVES: ``b_max``/``b_rms``/
    ``b_centre`` over the disc and the flux delivered at its centre.

    ★★The whole chain is one call because it is one statement.  The disc
    says over what region, the row scaling says what "at tolerance" means in
    two different units, the box says what the supplies can do, and
    ``b_max`` is the criterion the answer is judged by.  Split across hosts,
    each half looks right and the design is wrong in the seam — this repo
    measured a browser page 3e-2 from the native answer while both of its
    borrowed halves were exact.
    """
    lib = require()
    ea = [_f(np.atleast_1d(x)) for x in elems]
    ne = ea[0].size
    #: ★``weights`` is the ``(n_channel, n_element)`` map, as at every other
    #: host-side entry; the wire format is its transpose (see
    #: :func:`channel_field`, which this shares a Rust fold with)
    w_map = np.atleast_2d(np.asarray(weights, float))
    if w_map.shape[1] != ne:
        raise KernelError(f"weights has {w_map.shape[1]} columns, expected "
                          f"{ne} (one per element); the map is "
                          f"(n_channel, n_element)")
    nch = w_map.shape[0]
    wt = _f(w_map.T)
    x_ref_a = None if x_ref is None else _f(np.atleast_1d(x_ref))
    i_max_a = None if i_max is None else _f(np.atleast_1d(i_max))
    out, flags, stats = np.empty(nch), np.empty(nch), np.empty(4)
    npts = 1 + int(n_ring) * int(n_theta)
    disc_a = np.empty(3 * npts) if disc else None
    rc = lib.fylite_rs_breakdown_design(
        *ea, ne, wt.ravel(), nch, float(r0), float(z0), float(radius),
        int(n_ring), int(n_theta), float(b_tol),
        float("nan") if flux_target is None else float(flux_target),
        float(weight_null), float(weight_flux), float(lam),
        None if x_ref_a is None else x_ref_a.ctypes.data,
        None if i_max_a is None else i_max_a.ctypes.data,
        int(nu), int(nv), out, flags, stats,
        None if disc_a is None else disc_a.ctypes.data)
    if rc == -3:
        raise KernelError(
            "breakdown design did not converge: the box-constrained solve "
            "ran out of iterations, so these currents are the last step of "
            "a descent rather than a design.  Loosen the box, raise lambda, "
            "or ask for a weaker null.")
    if rc < 0:
        raise KernelError(f"fylite_rs_breakdown_design returned {rc}")
    res = {"aturns": out, "flags": flags.astype(int), "iterations": int(rc),
           "b_max": float(stats[0]), "b_rms": float(stats[1]),
           "b_centre": float(stats[2]), "flux_Wb": float(stats[3]),
           "at_bound": np.flatnonzero(flags == 1).tolist(),
           "over": np.flatnonzero(flags == 2).tolist()}
    if disc_a is not None:
        rows = disc_a.reshape(-1, 3)
        res["disc"] = (rows[:, 0].copy(), rows[:, 1].copy())
        res["b_pol"] = rows[:, 2].copy()
    return res


_sig("fylite_rs_design_null", ([_ARR] * 3 + [_U64, _U64] + [_F64] * 5 + [_VOID, _VOID, _ARR, _ARR]), _I32)
def design_null(br, bz, psi, *, b_tol: float, flux_target=None,
                weight_null: float = 1.0, weight_flux: float = 1.0,
                lam: float = 1e-12, x_ref=None, i_max=None) -> dict:
    """Least-squares coil currents for a field null, with an optional
    required flux and an optional per-channel current box.

    ``br`` / ``bz`` are ``(nch, npts)`` per-ampere-turn responses over the
    null disc, ``psi`` the ``(nch,)`` response at the null centre.

    ★The row scaling is the whole design and it lives in the kernel: the
    null rows carry teslas (~1e-3) and the flux row webers (~1e-1), so left
    raw the flux term swamps the null and the "design" comes back as a
    uniform field.  ``flags`` reports which channels sit on their bound (1)
    or over it (2) — an infeasible design must say WHICH limit stopped it.
    """
    lib = require()
    br, bz, psi = _f(br), _f(bz), _f(psi)
    nch, npts = br.shape
    x_ref_a = None if x_ref is None else _f(x_ref)
    i_max_a = None if i_max is None else _f(i_max)
    out = np.empty(nch)
    flags = np.empty(nch)
    rc = lib.fylite_rs_design_null(
        br.ravel(), bz.ravel(), psi, nch, npts, float(b_tol),
        float("nan") if flux_target is None else float(flux_target),
        float(weight_null), float(weight_flux), float(lam),
        None if x_ref_a is None else x_ref_a.ctypes.data,
        None if i_max_a is None else i_max_a.ctypes.data,
        out, flags)
    if rc == -3:
        #: ★the last iterate IS in `out`, and it is not a minimum — a
        #: caller comparing two such points (two hosts, two rounding paths)
        #: is comparing two arbitrary places on the same descent.  Measured
        #: on the EAST deck: at the old 4000-step cap a binding design sat
        #: 4.3x above its converged objective, silently.
        raise KernelError(
            "design_null ran out of iterations: the box-constrained solve "
            "did not converge, so the currents it produced are the last "
            "step of a descent rather than a design.  Loosen the box, raise "
            "lambda, or ask for a weaker null.")
    if rc < 0:
        raise KernelError(f"fylite_rs_design_null returned {rc}")
    return {"aturns": out, "flags": flags.astype(int), "iterations": int(rc),
            "at_bound": np.flatnonzero(flags == 1).tolist(),
            "over": np.flatnonzero(flags == 2).tolist()}


# --------------------------------------------------------------------------- #
# Raw entries reached only by tests (no wrapper here): declared so that
# `load()` / `require()` hand back a library whose signatures are complete,
# and a test calling `lib.fylite_rs_xxx(...)` directly never marshals an
# undeclared count as a bare 32-bit int.
# --------------------------------------------------------------------------- #
_sig("fylite_rs_gs_fixed_solve", [_ARR, _U64, _ARR, _U64, _ARR, _F64, _ARR, _U64, _ARR, _U64, _F64, _U64, _F64, _ARR], _I32)
_sig("fylite_rs_eigen", [_ARR, _ARR, _U64, _I32, _ARR, _ARR, _ARR, _ARR], _I32)
# the closure's own chi profile, so a caller can draw what it solved
# with instead of rebuilding the chain
_sig("fylite_rs_neo_chi", [_ARR, _ARR, _U64, _ARR, _ARR, _U64, _ARR, ctypes.c_void_p, _F64, _ARR], _I32)
#: ★the collision operator, declared HERE rather than in the test that
#: first needed it.  It used to be declared inside a test helper, so a
#: second test calling this entry only worked when that helper had run
#: first — an order dependency invisible while both ran, and it surfaced
#: the moment the helper stopped executing its body.  Declaring the Rust
#: ABI is this module's job; this repository already paid once for
#: leaving a count undeclared (a bare Python int marshalled 32-bit,
#: giving a 9 PB allocation).
_sig("fylite_rs_dke_coll", ([_U64] * 3 + [_I32] + [_ARR] * 5 + [_U64, _ARR, _U64]), _I32)


# --------------------------------------------------------------------------- #
# T-A5 · the inverse solve with the coil currents as OBSERVATIONS
#
# ★One contiguous block, appended, so three branches editing this file at
# once do not collide in the middle of it.  Nothing above is changed:
# `gs_inverse_solve` still reaches `fylite_rs_gs_inverse_solve` and still
# returns exactly the numbers it returned.
# --------------------------------------------------------------------------- #

#: What the coil entry's `out12` carries.  ★Its own tuple rather than
#: `FREE_SOLVE_KEYS`: the free solve packs an X-point into slots 7-8 and the
#: inverse packs the feedback amplitude and the coil diagnostics there, and
#: borrowing the free solve's names for the inverse's slots is how
#: `res["xpt_r"]` came to mean「fb_amp」on this entry's older sibling.
INVERSE_COIL_KEYS = ("psi_axis", "psi_bnd", "axis_r", "axis_z", "ip",
                     "residual", "bnd_kind", "fb_amp", "coil_pull",
                     #: two reserved slots, named `_` like every other slot
                     #: the kernel fills with a literal — the row-order
                     #: checker reads that spelling as「padding」
                     #: ★slots 10-11 are now filled, with the same two
                     #: names the other two inverse entries use.
                     "coil_fitted", "fb_amp_r", "trunc_keep")

_sig("fylite_rs_gs_inverse_solve_coils", [_ARR, _U64, _ARR, _U64, _ARR, _ARR, _ARR, _ARR, _U64, _F64, _U64, _U64, _F64, _ARR, _ARR, _U64, _ARR, _ARR, _ARR, _U64, _ARR, _U64, _ARR, _ARR, _ARR, _ARR, _U64, _F64, _F64, _U64, _F64, _F64, _F64, _F64, _U64, _ARR, _ARR, _ARR, _ARR], _I32)
def gs_inverse_solve_coils(grid_r, grid_z, psi_ext, *, loops_m, meas,
                           weights, meas_scale: float, npp: int, nff: int,
                           ip: float, limiter_r, limiter_z,
                           coil_psi, coil_rows, coil_currents, coil_sigma,
                           meas_sigma: float = 1.0, pressure_x=None, pressure_meas=None,
                           pressure_weights=None, j_prescribed=None,
                           relax: float = 0.3, max_iter: int = 600,
                           tol: float = 1e-9, fb_gain: float = 8.0,
                           zc_anchor=None, rc_anchor=None,
                           warmup: int = 0) -> dict:
    """:func:`gs_inverse_solve`, with the coil currents FITTED rather than
    taken as exactly known.

    ``coil_psi`` is ``(nch, nr*nz)`` full flux [Wb] per unit channel
    current, ``coil_rows`` is ``(n_rows, nch)`` in each measurement row's
    OWN units (no ``meas_scale`` is applied to them), ``coil_currents`` the
    supplied channel values and ``coil_sigma`` the prior width on each.
    A channel whose sigma is ``<= 0`` or non-finite is held exactly, so a
    partly-metered coil set needs no second code path.

    ``meas_sigma`` is what a measurement weight of ``1.0`` stands for, in
    the measurement rows' own units.  It is REQUIRED to be right, not
    optional: every deck here ships flux-loop weights that are a 0/1 mask,
    which asserts ``sigma_loop = 1 Wb/rad``, and against that assertion the
    fit leaves the coils where it found them.  Pass ``1.0`` only when the
    weights really are ``1/sigma``.

    ``psi_ext`` and ``meas`` are what they always were — the field and the
    channel readings AT ``coil_currents``.  The fit solves for the
    correction on top of them, which is why this entry can be handed the
    same inputs the plain one takes.

    Returns :data:`INVERSE_COIL_KEYS` plus ``psi``, ``coefficients``,
    ``iterations`` and ``coil_fit`` (the fitted absolute currents).
    """
    lib = require()
    rg, zg = _f(np.atleast_1d(grid_r)), _f(np.atleast_1d(grid_z))
    lr, lz = _f(np.atleast_1d(limiter_r)), _f(np.atleast_1d(limiter_z))
    b, w = _f(np.atleast_1d(meas)), _f(np.atleast_1d(weights))
    if w.size != b.size:
        raise KernelError(f"{b.size} measurements against {w.size} weights")
    have_p = pressure_x is not None
    xp = _f(np.atleast_1d(pressure_x)) if have_p else np.zeros(1)
    pm = _f(np.atleast_1d(pressure_meas)) if have_p else np.zeros(1)
    pw = _f(np.atleast_1d(pressure_weights)) if have_p else np.zeros(1)
    if have_p and not (xp.size == pm.size == pw.size):
        raise KernelError(
            f"pressure rows disagree: x {xp.size}, meas {pm.size}, "
            f"weights {pw.size}")
    ncell = (rg.size - 2) * (zg.size - 2)
    if j_prescribed is None:
        jp = np.zeros(1)
    else:
        jp = _f(np.atleast_1d(j_prescribed))
        if jp.size != ncell:
            raise KernelError(
                f"j_prescribed has {jp.size} cells, expected {ncell}")
    i0 = _f(np.atleast_1d(coil_currents))
    sig = _f(np.atleast_1d(coil_sigma))
    nch = i0.size
    if sig.size != nch:
        raise KernelError(f"{nch} coil currents against {sig.size} sigmas")
    cpsi = _f(np.ascontiguousarray(coil_psi).reshape(-1))
    crow = _f(np.ascontiguousarray(coil_rows).reshape(-1))
    #: ★checked HERE as well as in Rust: a caller that transposed the row
    #: block gets a size error rather than a plausible fit on the wrong
    #: channel assignment whenever `n_rows` happens to equal `nch`.
    if cpsi.size != nch * rg.size * zg.size:
        raise KernelError(
            f"coil_psi has {cpsi.size} entries, expected "
            f"{nch} x {rg.size * zg.size} = (nch, nr*nz)")
    if crow.size != nch * b.size:
        raise KernelError(
            f"coil_rows has {crow.size} entries, expected "
            f"{b.size} x {nch} = (n_rows, nch)")
    psi = np.empty((rg.size, zg.size))
    coefs, out = np.empty(int(npp) + int(nff)), np.empty(12)
    cout = np.empty(max(nch, 1))
    it = lib.fylite_rs_gs_inverse_solve_coils(
        rg, rg.size, zg, zg.size, _f(psi_ext), _f(loops_m), b, w, b.size,
        float(meas_scale), int(npp), int(nff), float(ip), lr, lz, lr.size,
        xp, pm, pw, xp.size if have_p else 0,
        jp, jp.size if j_prescribed is not None else 0,
        cpsi, crow, i0, sig, nch, float(meas_sigma),
        float(relax), int(max_iter), float(tol), float(fb_gain),
        float("nan") if zc_anchor is None else float(zc_anchor),
        float("nan") if rc_anchor is None else float(rc_anchor),
        int(warmup), psi, coefs, cout, out)
    if it <= 0:
        raise KernelError(f"fylite_rs_gs_inverse_solve_coils returned {it}")
    res = dict(zip(INVERSE_COIL_KEYS, out))
    res.update(psi=psi, coefficients=coefs, iterations=int(it),
               coil_fit=cout[:nch])
    return res


# ===== T-A9: the bootstrap / ohmic / fitted-current closure ================
#
# ★★The two quantities a kinetic reconstruction has to add and could not.
# The analytic bootstrap family returns ``⟨j·B⟩``; an equilibrium
# reconstruction returns ``⟨j_φ⟩``.  Those are different quantities on the
# same surface, so "bootstrap + ohmic = fitted current" was not an
# approximation anyone declined to make — it was arithmetic nobody had.

_sig("fylite_rs_surface_fsa",
     ([_F64] * 4 + [_U64] * 2 + [_ARR, _ARR, _U64] + [_F64] * 2 + [_ARR]), _I32)
def surface_fsa(grid: Grid, psi, poly, *, psi_scale: float,
                f_psi: float) -> dict:
    """Flux-surface averages of one ALREADY-TRACED surface.

    ``poly`` is the outline :func:`trace_surface` returned, ``(n, 2)`` or
    interleaved.  ``psi_scale`` multiplies ``psi`` to get **Wb per radian**
    (1.0 when it already is, ``1/(2π)`` for a full-flux map) — an argument
    rather than a convention, because ``B_pol = |∇ψ|/R`` holds only in the
    per-radian gauge and the wrong one gives a smooth, plausible ``⟨B²⟩``
    that is 39 times too large.

    Returns ``r_inv``, ``r_inv2``, ``b_pol2``, ``b_tor2``, ``b2`` and
    ``dv_dpsi``.
    """
    lib = require()
    psi = _f(psi)
    if psi.shape != (grid.nr, grid.nz):
        raise KernelError(f"psi must be {grid.nr} x {grid.nz}")
    pv = _f(np.asarray(poly, dtype=float).reshape(-1))
    if pv.size % 2:
        raise KernelError("poly must be pairs of (r, z)")
    out = np.empty(6)
    rc = lib.fylite_rs_surface_fsa(
        grid.r0, grid.z0, grid.dr, grid.dz, grid.nr, grid.nz,
        psi.reshape(-1), pv, pv.size // 2, float(psi_scale), float(f_psi),
        out)
    if rc != 0:
        raise KernelError(f"fylite_rs_surface_fsa returned {rc}")
    keys = ("r_inv", "r_inv2", "b_pol2", "b_tor2", "b2", "dv_dpsi")
    return dict(zip(keys, (float(v) for v in out)))


_sig("fylite_rs_jparb_jphi", ([_U64] + [_ARR] * 6 + [_I32, _ARR]), _I32)
def jparb_jphi(*, b2_avg, btor2_avg, f_psi, rinv_avg, dpdpsi, j_in,
               to_toroidal: bool = True) -> dict:
    """``⟨j·B⟩`` ↔ ``⟨j_φ/R⟩/⟨1/R⟩`` per surface — the exact G-S identity.

    ★``dpdpsi`` is the DIAMAGNETIC term and it belongs to the TOTAL, not to
    either channel: pass zeros when converting the bootstrap or the ohmic
    part alone, or the same pressure gradient is counted once per curve and
    the parts stop summing to the whole.

    Returns ``j`` and the ``ratio`` = ``⟨B_tor²⟩/⟨B²⟩`` it used; a surface
    the conversion cannot support comes back as NaN rather than as a zero.
    """
    lib = require()
    args = [_f(a) for a in (b2_avg, btor2_avg, f_psi, rinv_avg, dpdpsi,
                            j_in)]
    n = args[0].size
    if any(a.size != n for a in args):
        raise KernelError("every profile must be the same length")
    out = np.empty(2 * n)
    rc = lib.fylite_rs_jparb_jphi(n, *args, 1 if to_toroidal else 0, out)
    if rc < 0:
        raise KernelError(f"fylite_rs_jparb_jphi returned {rc}")
    rows = out.reshape(n, 2)
    return {"j": rows[:, 0].copy(), "ratio": rows[:, 1].copy(),
            "converted": int(rc)}


_sig("fylite_rs_sigma_neo",
     ([_U64] + [_ARR] * 7 + [_F64] * 2 + [_I32] * 2 + [_ARR]), _I32)
def sigma_neo(*, eps, q_abs, ne, te, ti, ni, zeff, r_maj: float,
              z_ion: float = 1.0, vintage: int = 1,
              collisionless: bool = False) -> dict:
    """Neoclassical parallel conductivity on a ladder, SI [S/m].

    The half of the ohmic channel :func:`spitzer_eta` names as "another
    model" and did not have: ``σ_neo = σ_Sp F33``, with ``F33`` the trapping
    factor both Sauter vintages apply inside their own solve.

    ``vintage``: 0 = Sauter 1999, 1 = Redl 2021 — an unknown one is refused,
    never defaulted.  Measured against the drift-kinetic branch at
    ``f_t = 0.57``: 2021 within 0.3 %, 1999 low by 2.2–6.7 %.

    ★``σ_Sp`` here is Sauter's, which is NOT ``1/spitzer_eta``: that entry
    carries the NRL PERPENDICULAR coefficient and the two differ by 1/0.51.

    Returns ``sigma_neo``, ``sigma_spitzer``, ``f33``, ``ft`` and
    ``nu_e_star``.
    """
    lib = require()
    args = [_f(a) for a in (eps, q_abs, ne, te, ti, ni, zeff)]
    n = args[0].size
    if any(a.size != n for a in args):
        raise KernelError("every profile must be the same length")
    out = np.empty(5 * n)
    rc = lib.fylite_rs_sigma_neo(n, *args, float(r_maj), float(z_ion),
                                 int(vintage), 1 if collisionless else 0,
                                 out)
    if rc < 0:
        raise KernelError(f"fylite_rs_sigma_neo returned {rc}")
    rows = out.reshape(n, 5)
    keys = ("sigma_neo", "sigma_spitzer", "f33", "ft", "nu_e_star")
    return {k: rows[:, i].copy() for i, k in enumerate(keys)}


# --------------------------------------------------------------------------- #
# ICRH — the 1b wiring (`docs/note/icrh-ecrh-gap.md`)
# --------------------------------------------------------------------------- #
#: ★★The physics has been in `heating.rs` since the 1a batch, with seven
#: criteria measured against METIS, and until 2026-08-30 it had **no C export
#: at all** — the model existed and no host could call it.  These four
#: entries are that wiring; nothing under them is new physics.

#: the `minority` and `gas` codes the ABI block carries, spelled here so a
#: caller writes a NAME and the integer stays an implementation detail
ICRH_MINORITY = ("H", "D", "T", "He3", "He4")
ICRH_GAS = ("H", "D", "DT", "He")

#: the refusals `heating::IcrhRefused` crosses as negative codes, with the
#: reason each one means.  ★They are DISTINCT on purpose: "the antenna is
#: tuned off the machine" and "you did not give me a minority concentration"
#: are different conversations with the caller.
ICRH_REFUSALS = {
    -10: ("minority concentration missing: it is a scenario choice (a few "
          "per cent for a hydrogen minority, order one for second-harmonic "
          "tritium) that moves the answer through the whole chain, and the "
          "kernel will not invent one"),
    -11: "not a plasma: a frequency, field or geometry that cannot describe one",
    -12: ("this machine ripples and the model does not carry the loss it "
          "causes — set ripple=False to say the loss is accounted elsewhere"),
    -13: ("no resonance in the plasma at any harmonic this model considers.  "
          "★A RESULT, not a failure: an antenna tuned off the machine heats "
          "nothing, and a zero would read as 'the model found no coupling'"),
}


class IcrhRefused(KernelError):
    """The ICRH model declined to answer, and said why.

    ★A distinct type because these are not bugs: they are the model
    reporting that the question was not one it can answer, and a caller
    scanning a scenario over frequency will meet ``-13`` legitimately.
    """

    def __init__(self, code: int):
        self.code = int(code)
        super().__init__(ICRH_REFUSALS.get(
            self.code, f"ICRH refused with code {code}"))


def _icrh_setup_block(*, frequency, n_phi, c_min, minority="H", gas="D",
                      iso=0.0, fact=1.0, loss_fraction=0.0, ripple=False):
    try:
        m = ICRH_MINORITY.index(minority)
    except ValueError:
        raise KernelError(f"minority must be one of {ICRH_MINORITY}, "
                          f"not {minority!r}") from None
    try:
        g = ICRH_GAS.index(gas)
    except ValueError:
        raise KernelError(f"gas must be one of {ICRH_GAS}, "
                          f"not {gas!r}") from None
    return _f([float(frequency), float(n_phi), float(c_min), float(m),
               float(g), float(iso), float(fact), float(loss_fraction),
               1.0 if ripple else 0.0])


def _icrh_geometry_block(*, r0, a, kappa, b0, shift=0.0, q0=1.0, q_min=1.0,
                         q_a=3.0, volume=0.0, area_pol=0.0):
    return _f([float(r0), float(a), float(kappa), float(b0), float(shift),
               float(q0), float(q_min), float(q_a), float(volume),
               float(area_pol)])


_sig("fylite_rs_icrh_resonance", [_ARR, _ARR, _ARR], _I32)
_sig("fylite_rs_icrh_minority", [_ARR, _ARR, _ARR, _F64, _ARR], _I32)
_sig("fylite_rs_icrh_profile",
     [_ARR, _ARR, _U64, _F64, _F64, _F64, _F64, _ARR], _I32)
_sig("fylite_rs_icrh_fwcd",
     [_F64, _F64, ctypes.c_uint32, _F64, _F64, _F64, _I32, _ARR], _I32)

_ICRH_LAYER_KEYS = ("r_res", "x_res", "harmonic", "b_res", "offset")
_ICRH_HEAT_KEYS = ("p_el", "p_ion", "w_fast", "e_mean", "t_eff", "e_crit",
                   "e_gamma", "tau_s", "volume_fraction", "n_minority")


def icrh_resonance(*, setup: dict, geometry: dict) -> dict:
    """Where an ICRF antenna resonates: ``{r_res, x_res, harmonic, b_res,
    offset}``.

    ``setup`` takes ``frequency`` [Hz], ``n_phi``, ``c_min`` and optionally
    ``minority`` / ``gas`` / ``iso`` / ``fact`` / ``loss_fraction`` /
    ``ripple``; ``geometry`` takes ``r0``, ``a``, ``kappa``, ``b0`` and
    optionally ``shift`` / ``q0`` / ``q_min`` / ``q_a`` / ``volume`` /
    ``area_pol``.  Lengths [m], field [T].
    """
    lib = require()
    out = np.empty(5)
    rc = lib.fylite_rs_icrh_resonance(_icrh_setup_block(**setup),
                                      _icrh_geometry_block(**geometry), out)
    if rc in ICRH_REFUSALS:
        raise IcrhRefused(rc)
    if rc != 0:
        raise KernelError(f"fylite_rs_icrh_resonance returned {rc}")
    res = dict(zip(_ICRH_LAYER_KEYS, out))
    res["harmonic"] = int(res["harmonic"])
    return res


def icrh_minority(*, setup: dict, geometry: dict, local: dict,
                  power_w: float) -> dict:
    """The minority-heating answer: the electron/ion power split, the
    fast-ion content, and the layer it was computed on.

    ``local`` takes ``te``/``ti`` [eV], ``ne`` [m^-3], ``n_background``
    [m^-3] (the species the minority slows down on), ``n_helium`` [m^-3]
    (read only for a helium minority) and ``zeff``.

    ★The layer comes back WITH the heating rather than being re-derived by
    the caller: two derivations can disagree and only one of them is the
    one the power split was computed on.
    """
    lib = require()
    loc = _f([float(local["te"]), float(local["ti"]), float(local["ne"]),
              float(local.get("n_background", local["ne"])),
              float(local.get("n_helium", 0.0)), float(local["zeff"])])
    out = np.empty(15)
    rc = lib.fylite_rs_icrh_minority(_icrh_setup_block(**setup),
                                     _icrh_geometry_block(**geometry), loc,
                                     float(power_w), out)
    if rc in ICRH_REFUSALS:
        raise IcrhRefused(rc)
    if rc != 0:
        raise KernelError(f"fylite_rs_icrh_minority returned {rc}")
    res = dict(zip(_ICRH_HEAT_KEYS, out[:10]))
    res["layer"] = dict(zip(_ICRH_LAYER_KEYS, out[10:]))
    res["layer"]["harmonic"] = int(res["layer"]["harmonic"])
    return res


def icrh_profile(x, vpr, *, x_res: float, width: float, p_total: float,
                 p_ion: float) -> dict:
    """The deposition profile — a Gaussian on the resonance layer, split
    into its ion and electron shares and normalised on the caller's ``V'``.

    Returns ``{p_total, p_ion, p_el}`` [W/m^3], each on ``x``.
    """
    lib = require()
    xs, v = _f(np.asarray(x, float).ravel()), _f(np.asarray(vpr, float).ravel())
    n = xs.size
    if v.size != n:
        raise KernelError(f"x has {n} points and vpr has {v.size}")
    out = np.empty(3 * n)
    rc = lib.fylite_rs_icrh_profile(xs, v, n, float(x_res), float(width),
                                    float(p_total), float(p_ion), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_icrh_profile returned {rc}")
    return {"p_total": out[:n].copy(), "p_ion": out[n:2 * n].copy(),
            "p_el": out[2 * n:].copy()}


def icrh_fwcd(*, te0_ev: float, zeff: float, model: int = 0,
              power_w: float = 0.0, ne0: float = 0.0, r0: float = 0.0,
              direction: int = 1) -> dict:
    """Fast-wave current drive: ``{eta, current_a}``."""
    lib = require()
    out = np.empty(2)
    rc = lib.fylite_rs_icrh_fwcd(float(te0_ev), float(zeff), int(model),
                                 float(power_w), float(ne0), float(r0),
                                 int(direction), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_icrh_fwcd returned {rc}")
    return {"eta": float(out[0]), "current_a": float(out[1])}


# --------------------------------------------------------------------------- #
# Edge atomic data — Mavrin-2017 NON-coronal (TX-4, the data layer)
# --------------------------------------------------------------------------- #
#: ★★NOT a second spelling of :func:`rad_ion`'s coronal cooling rate.  The
#: coronal one is a function of `T_e` alone and assumes the charge state
#: distribution has settled; in a divertor it usually has not.  The
#: non-coronal rate takes the residence parameter `n_e*tau` as well, and the
#: two differ by orders of magnitude exactly where an edge model is asked.
#: Both are kept and each says which it is.

#: the species these fits carry.  ★`He3`/`He4` alias to `He` — same electron
#: shell — and anything else radiates ZERO, which is upstream's own
#: modelling statement about heavy impurities at the EDGE (tungsten's edge
#: contribution is negligible beside its core one, which a different model
#: answers) rather than a silent failure.
EDGE_SPECIES = ("He", "Li", "Be", "C", "N", "O", "Ne", "Ar")

#: above this residence parameter the plasma is CORONAL and the fit
#: SATURATES rather than extrapolating [m^-3 s]
NE_TAU_CORONAL_LIMIT = 1.0e19

_sig("fylite_rs_edge_noncoronal",
     [ctypes.c_char_p, _U64, _ARR, _U64, _F64, _ARR], _I32)
_sig("fylite_rs_edge_l_int",
     [ctypes.c_char_p, _U64, _F64, _F64, _F64, _U64, _ARR], _I32)


def edge_noncoronal(symbol: str, t_e_ev, *, ne_tau: float) -> dict:
    """Non-coronal mean charge state and cooling rate.

    ``t_e_ev`` [eV], ``ne_tau`` [m^-3 s].  Returns
    ``{mean_charge_state, cooling_rate}`` [dimensionless], [W m^3], each on
    ``t_e_ev``.

    ★Three clippings are part of the MODEL, not guards on it: ``T_e`` into
    the species' own fit range (a third-order polynomial extrapolated is
    not a small error), ``ne_tau`` at the coronal limit, and an unknown
    species to zero.
    """
    lib = require()
    t = _f(np.atleast_1d(np.asarray(t_e_ev, float)).ravel())
    n = t.size
    b = str(symbol).encode()
    out = np.empty(2 * n)
    rc = lib.fylite_rs_edge_noncoronal(b, len(b), t, n, float(ne_tau), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_edge_noncoronal returned {rc}")
    return {"mean_charge_state": out[:n].copy(),
            "cooling_rate": out[n:].copy()}


def edge_l_int(symbol: str, *, start_ev: float, stop_ev: float,
               ne_tau: float, resolution: int) -> float:
    """``L_INT = ∫ L_z sqrt(T_e) dT_e`` [eV^1.5 W m^3] — the integrated
    cooling rate the extended Lengyel model consumes.

    ★★``resolution`` is PART OF THE ANSWER and has no default: this is a
    trapezoid on a log-spaced grid, and upstream's own callers use 100
    points.  A caller that quietly used more would not reproduce the model
    it claims to reproduce — it would reproduce a better-integrated cousin
    of it.
    """
    lib = require()
    b = str(symbol).encode()
    out = np.empty(1)
    rc = lib.fylite_rs_edge_l_int(b, len(b), float(start_ev), float(stop_ev),
                                  float(ne_tau), int(resolution), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_edge_l_int returned {rc}")
    return float(out[0])


#: the 13 columns `fylite_rs_lengyel_closed` reads, in order
LENGYEL_GEOMETRY_KEYS = (
    "major_radius", "minor_radius", "elongation_psi95",
    "triangularity_psi95", "magnetic_field_on_axis", "plasma_current",
    "separatrix_electron_density", "power_crossing_separatrix",
    "average_ion_mass", "mean_ion_charge_state",
    "ratio_bpol_omp_to_bpol_avg", "fraction_of_P_SOL_to_divertor",
    "T_i_T_e_ratio_separatrix",
)

#: upstream's defaults for the three that are model settings rather than
#: machine facts (`extended_lengyel_defaults`)
LENGYEL_DEFAULTS = {
    "ratio_bpol_omp_to_bpol_avg": 4.0 / 3.0,
    "fraction_of_P_SOL_to_divertor": 2.0 / 3.0,
    "T_i_T_e_ratio_separatrix": 1.0,
}

_LENGYEL_CLOSED_KEYS = ("shaping_factor", "b_pol_avg",
                        "cylindrical_safety_factor", "fieldline_pitch_at_omp",
                        "kappa_e", "alpha_t", "q_parallel")

_sig("fylite_rs_lengyel_closed", [_ARR, _F64, _F64, _ARR], _I32)


def lengyel_closed(geometry: dict, *, t_e_separatrix_ev: float,
                   z_eff_separatrix: float) -> dict:
    """The extended Lengyel model's closed forms — the half that does not
    iterate.

    ``geometry`` takes :data:`LENGYEL_GEOMETRY_KEYS`; the last three have
    upstream defaults in :data:`LENGYEL_DEFAULTS`.  Returns the separatrix
    geometry, ``kappa_e`` [W/(m eV^3.5)], ``alpha_t`` and ``q_parallel``
    [W/m^2].

    ★★``t_e_separatrix_ev`` is in **eV**.  The model's own
    ``T_e_separatrix`` output is in keV while its ``T_e_target`` is in eV —
    upstream's arrangement, which is why the unit is in this argument's
    name rather than left to a docstring a caller may not read.
    """
    lib = require()
    kw = {**LENGYEL_DEFAULTS, **geometry}
    missing = [k for k in LENGYEL_GEOMETRY_KEYS if k not in kw]
    if missing:
        raise KernelError(f"lengyel geometry missing: {', '.join(missing)}")
    block = _f([float(kw[k]) for k in LENGYEL_GEOMETRY_KEYS])
    out = np.empty(7)
    rc = lib.fylite_rs_lengyel_closed(block, float(t_e_separatrix_ev),
                                      float(z_eff_separatrix), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_lengyel_closed returned {rc}")
    return dict(zip(_LENGYEL_CLOSED_KEYS, out))


#: the 14 columns `fylite_rs_lengyel_two_point` reads, in order
LENGYEL_SOL_KEYS = (
    "connection_length_divertor", "connection_length_target",
    "SOL_conduction_fraction", "divertor_broadening_factor",
    "separatrix_electron_density", "average_ion_mass",
    "sheath_heat_transmission_factor", "toroidal_flux_expansion",
    "mach_separatrix", "mach_target", "n_e_n_i_ratio_separatrix",
    "n_e_n_i_ratio_target", "T_i_T_e_ratio_separatrix",
    "T_i_T_e_ratio_target",
)

#: upstream's defaults for the ones that are model settings rather than
#: machine facts (`extended_lengyel_defaults`)
LENGYEL_SOL_DEFAULTS = {
    "SOL_conduction_fraction": 1.0,
    "divertor_broadening_factor": 3.0,
    "sheath_heat_transmission_factor": 8.0,
    "toroidal_flux_expansion": 1.0,
    "mach_separatrix": 0.0,
    "mach_target": 1.0,
    "n_e_n_i_ratio_separatrix": 1.0,
    "n_e_n_i_ratio_target": 1.0,
    "T_i_T_e_ratio_separatrix": 1.0,
    "T_i_T_e_ratio_target": 1.0,
}

#: the five numbers that ARE the extended Lengyel state
LENGYEL_STATE_KEYS = ("q_parallel", "alpha_t", "kappa_e", "c_z_prefactor",
                      "T_e_target_eV")

_LENGYEL_TWO_POINT_KEYS = (
    "electron_temp_at_cc_interface", "divertor_entrance_electron_temp",
    "T_e_separatrix_eV", "separatrix_total_pressure", "required_power_loss",
    "parallel_heat_flux_at_target", "parallel_heat_flux_at_cc_interface",
)

_sig("fylite_rs_lengyel_two_point", [_ARR, _ARR, _ARR], _I32)
_sig("fylite_rs_lengyel_z_eff",
     [_F64, _F64, _F64, ctypes.c_char_p, _ARRU, _ARR, _U64, _ARR], _I32)


def lengyel_two_point(params: dict, state: dict) -> dict:
    """The two-point model's derived properties at a state you supply.

    ``params`` takes :data:`LENGYEL_SOL_KEYS` (model settings default from
    :data:`LENGYEL_SOL_DEFAULTS`); ``state`` takes
    :data:`LENGYEL_STATE_KEYS`.

    ★★These are PURE FUNCTIONS of the state, which is what makes them
    checkable before any solver exists: the whole state is five numbers, so
    a port can be held to upstream's derived values at a converged state it
    did not have to find for itself.

    ★``T_e_separatrix_eV`` comes back in **eV** — the model's internal unit.
    Its top-level output of that name is in keV while ``T_e_target`` stays
    in eV, and converting here would put two meanings behind one name.
    """
    lib = require()
    kw = {**LENGYEL_SOL_DEFAULTS, **params}
    missing = [k for k in LENGYEL_SOL_KEYS if k not in kw]
    if missing:
        raise KernelError(f"lengyel params missing: {', '.join(missing)}")
    missing = [k for k in LENGYEL_STATE_KEYS if k not in state]
    if missing:
        raise KernelError(f"lengyel state missing: {', '.join(missing)}")
    p = _f([float(kw[k]) for k in LENGYEL_SOL_KEYS])
    s = _f([float(state[k]) for k in LENGYEL_STATE_KEYS])
    out = np.empty(7)
    rc = lib.fylite_rs_lengyel_two_point(p, s, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_lengyel_two_point returned {rc}")
    return dict(zip(_LENGYEL_TWO_POINT_KEYS, out))


def lengyel_z_eff(impurities: dict, *, t_e_ev: float, ne_tau: float,
                  z_i: float = 1.0) -> float:
    """``Z_eff`` from a background ion and ``{symbol: concentration}``.

    Each impurity's mean charge state comes from the Mavrin non-coronal fit
    at ``t_e_ev`` [eV] and ``ne_tau`` [m^-3 s]; quasineutrality closes the
    background density.

    ★A species the fits do not carry contributes NOTHING — the same
    modelling statement :func:`edge_noncoronal` makes, and it must not
    quietly change ``Z_eff`` either.
    """
    lib = require()
    names = list(impurities)
    blob = "".join(names).encode()
    lens = np.ascontiguousarray([len(n.encode()) for n in names], np.uint64)
    conc = _f([float(impurities[n]) for n in names])
    out = np.empty(1)
    rc = lib.fylite_rs_lengyel_z_eff(float(t_e_ev), float(ne_tau), float(z_i),
                                     blob, lens, conc, len(names), out)
    if rc != 0:
        raise KernelError(f"fylite_rs_lengyel_z_eff returned {rc}")
    return float(out[0])


#: how `fylite_rs_lengyel_inverse` reports why the model declined
LENGYEL_OUTCOMES = ("SUCCESS", "C_Z_PREFACTOR_NEGATIVE",
                    "Q_CC_SQUARED_NEGATIVE")

#: upstream's fixed-point iteration count and initial guesses
LENGYEL_FIXED_POINT_ITERATIONS = 25
LENGYEL_NE_TAU = 5e16

_LENGYEL_INVERSE_KEYS = ("q_parallel", "alpha_t", "kappa_e", "c_z_prefactor",
                         "T_e_target_eV", "T_e_separatrix_eV",
                         "Z_eff_separatrix", "divertor_Z_eff")

_sig("fylite_rs_lengyel_inverse",
     [_ARR, _ARR, _F64, _F64, _F64, _U64,
      ctypes.c_char_p, _ARRU, _ARR, _U64,
      ctypes.c_char_p, _ARRU, _ARR, _U64, _ARR], _I32)


def _impurity_block(mapping: dict):
    names = list(mapping)
    blob = "".join(names).encode()
    lens = np.ascontiguousarray([len(n.encode()) for n in names], np.uint64)
    vals = _f([float(mapping[n]) for n in names])
    return blob, lens, vals, len(names)


def lengyel_forward(*, geometry: dict, params: dict,
                    fixed_impurity_concentrations: dict,
                    ne_tau: float = LENGYEL_NE_TAU,
                    main_ion_charge: float = 1.0,
                    iterations: int = LENGYEL_FIXED_POINT_ITERATIONS) -> dict:
    """The extended Lengyel FORWARD solve — the interpretive question.

    Given the impurity concentrations, the target temperature they produce.

    ★★**The harder root.**  One set of inputs can admit several solutions;
    this fixed point finds the one its initial guess leads to.  Upstream's
    full model carries a multistart and a ``multiple_roots_found`` flag for
    that reason, and neither is ported — a caller who needs to know whether
    another root exists does not learn it here.

    ★``Q_CC_SQUARED_NEGATIVE`` is a RESULT: so much power has been radiated
    that the target temperature would be negative, which is full
    detachment.  The temperature is clipped to a small positive value so
    the loop does not propagate a NaN, and the outcome is where the fact
    lives.
    """
    return lengyel_inverse(
        geometry=geometry, params=params, t_e_target_ev=-1.0,
        seed_impurity_weights={},
        fixed_impurity_concentrations=fixed_impurity_concentrations,
        ne_tau=ne_tau, main_ion_charge=main_ion_charge,
        iterations=iterations)


def lengyel_inverse(*, geometry: dict, params: dict, t_e_target_ev: float,
                    seed_impurity_weights: dict,
                    fixed_impurity_concentrations: dict | None = None,
                    ne_tau: float = LENGYEL_NE_TAU,
                    main_ion_charge: float = 1.0,
                    iterations: int = LENGYEL_FIXED_POINT_ITERATIONS) -> dict:
    """The extended Lengyel INVERSE solve — the design question.

    Given a target electron temperature at the sheath entrance [eV], the
    seeded impurity concentration that reaches it.  ``geometry`` takes
    :data:`LENGYEL_GEOMETRY_KEYS` and ``params`` :data:`LENGYEL_SOL_KEYS`;
    seeded species arrive as WEIGHTS (multiplied by the solved prefactor)
    and fixed ones as concentrations.

    Returns the converged state, the separatrix temperature [eV], both
    ``Z_eff`` values, and ``outcome``.

    ★★``outcome`` is a RESULT, not an error.  ``C_Z_PREFACTOR_NEGATIVE``
    means the plasma is already below the target with no seeding at all —
    reaching it would need "negative impurities" — and the concentration is
    clipped to zero while the outcome still says what happened.  A caller
    that read only the number would see "no seeding needed" and miss that
    the target is unreachable.

    ★``iterations`` is upstream's fixed count, not a convergence test:
    "converged" here means "ran the stated number of passes", which is the
    claim a port has to reproduce.
    """
    lib = require()
    kw_g = {**LENGYEL_DEFAULTS, **geometry}
    kw_p = {**LENGYEL_SOL_DEFAULTS, **params}
    for keys, kw, what in ((LENGYEL_GEOMETRY_KEYS, kw_g, "geometry"),
                           (LENGYEL_SOL_KEYS, kw_p, "params")):
        missing = [k for k in keys if k not in kw]
        if missing:
            raise KernelError(f"lengyel {what} missing: {', '.join(missing)}")
    g = _f([float(kw_g[k]) for k in LENGYEL_GEOMETRY_KEYS])
    p = _f([float(kw_p[k]) for k in LENGYEL_SOL_KEYS])
    s_blob, s_lens, s_vals, n_s = _impurity_block(seed_impurity_weights)
    f_blob, f_lens, f_vals, n_f = _impurity_block(
        fixed_impurity_concentrations or {})
    out = np.empty(9)
    rc = lib.fylite_rs_lengyel_inverse(
        g, p, float(t_e_target_ev), float(ne_tau), float(main_ion_charge),
        int(iterations), s_blob, s_lens, s_vals, n_s,
        f_blob, f_lens, f_vals, n_f, out)
    if rc != 0:
        raise KernelError(f"fylite_rs_lengyel_inverse returned {rc}")
    res = dict(zip(_LENGYEL_INVERSE_KEYS, out[:8]))
    res["outcome"] = LENGYEL_OUTCOMES[int(out[8])]
    res["seed_impurity_concentrations"] = {
        name: res["c_z_prefactor"] * float(weight)
        for name, weight in seed_impurity_weights.items()}
    return res


# --------------------------------------------------------------------------- #
# the device data plane — mdsip (FYL-DESIGN-06, ABI v124)
#
# ★★2026-09-02.  Until now this package read MDSplus through `fylite.io.mds`,
# a client of its own, while the kernel carried a second one that only the
# desktop viewer used.  Two implementations of one protocol, spelling the same
# `\EFIT_EAST::TOP…` nodes separately — the shape this project has been bitten
# by three times (the device description came out with a different WALL on the
# two sides; `zerod`'s parameter order was spelled in three places).  These
# bindings are the half that lets this side reach the kernel's client.
#
# ★The read-only guard is not relaxed anywhere in here.  `read()` takes a verb
# code, a node path and integers; the kernel assembles the TDI text and refuses
# a "node" that is a language rather than a path.  There is no call that takes
# an expression, on this side or that one.
# --------------------------------------------------------------------------- #

_BYTES = ctypes.POINTER(ctypes.c_uint8)
_I64ARR = np.ctypeslib.ndpointer(np.int64, flags="C_CONTIGUOUS")
_ARRU64 = np.ctypeslib.ndpointer(np.uint64, flags="C_CONTIGUOUS")

_sig("fylite_rs_mds_open", [_BYTES, _U64, ctypes.c_uint16, _BYTES, _U64, _I32,
                            ctypes.POINTER(_VOID), _BYTES, _U64], _I32)
_sig("fylite_rs_mds_open_tree", [_VOID, _BYTES, _U64, ctypes.c_int64], _I32)
_sig("fylite_rs_mds_read", [_VOID, _I32, _BYTES, _U64, _I64ARR, _U64, _I32,
                            ctypes.POINTER(ctypes.c_uint64)], _I32)
_sig("fylite_rs_mds_last_f64", [_VOID, _ARR, _U64], _I32)
_sig("fylite_rs_mds_last_dims", [_VOID, _ARRU64, _U64,
                                 ctypes.POINTER(ctypes.c_uint64)], _I32)
_sig("fylite_rs_mds_last_error", [_VOID, _BYTES, _U64], ctypes.c_int64)
_sig("fylite_rs_mds_close", [_VOID], None)


def _b(text: str):
    """`str` -> `(uint8*, len)`.  ★Bytes and a length, not a NUL-terminated
    `char*`: this ABI has no C-string contract anywhere else."""
    raw = text.encode("utf-8")
    buf = (ctypes.c_uint8 * max(len(raw), 1)).from_buffer_copy(raw + b"\0")
    return ctypes.cast(buf, _BYTES), len(raw), buf


class MdsSession:
    """A read-only mdsip session, held by the kernel.

    ★It is a context manager because the handle is a `Box` on the other side:
    losing the reference without `close()` leaks the socket, and there is no
    finaliser that can be trusted to run.

        with MdsSession("127.0.0.1", 8000) as s:
            s.open_tree("efit_east", 70754)
            v = s.read("data", r"\\PLASMA", [7])
    """

    def __init__(self, host: str, port: int, *, user: str | None = None,
                 timeout_ms: int = 10_000):
        lib = require()
        h = _VOID()
        err = (ctypes.c_uint8 * 512)()
        hb, hn, _k1 = _b(host)
        ub, un, _k2 = _b(user or os.environ.get("USER") or "fylite")
        rc = lib.fylite_rs_mds_open(hb, hn, int(port), ub, un, int(timeout_ms),
                                    ctypes.byref(h),
                                    ctypes.cast(err, _BYTES), len(err))
        if rc != 0:
            why = bytes(err).split(b"\0", 1)[0].decode("utf-8", "replace")
            raise KernelError(f"mdsip open {host}:{port} failed ({rc}): {why}")
        self._h = h
        self._lib = lib

    #: verb spelling -> wire code.  ★Imported, not spelled: the mapping is
    #: generated from `mdsip.rs` into `_mds_request.py` precisely so this line
    #: cannot be the place it drifts.
    @staticmethod
    def _verb(name: str) -> int:
        from ._mds_request import VERBS
        if name not in VERBS:
            raise KernelError(f"unknown mds verb {name!r} (have {sorted(VERBS)})")
        return VERBS[name]

    def _fail(self, what: str, rc: int):
        n = self._lib.fylite_rs_mds_last_error(self._h, None, 0)
        buf = (ctypes.c_uint8 * max(int(n), 1))()
        self._lib.fylite_rs_mds_last_error(self._h, ctypes.cast(buf, _BYTES),
                                           len(buf))
        why = bytes(buf)[:max(int(n), 0)].decode("utf-8", "replace")
        raise KernelError(f"{what} returned {rc}: {why}")

    def open_tree(self, tree: str, shot: int) -> None:
        tb, tn, _k = _b(tree)
        rc = self._lib.fylite_rs_mds_open_tree(self._h, tb, tn, int(shot))
        if rc != 0:
            self._fail(f"open_tree({tree!r}, {shot})", rc)

    def read(self, verb: str, node: str, subscript=None, *, inside: bool = False):
        """One A-Box binding -> `(values, dims)`.

        `subscript` items are integers, or ``None`` for ``*``.  ★``None`` and
        not the sentinel itself: `i64::MIN` is the wire encoding, and a caller
        writing it out is a caller who can typo it.
        """
        from ._mds_request import ALL
        items = [] if not subscript else [ALL if i is None else int(i)
                                          for i in subscript]
        sub = np.asarray(items, dtype=np.int64)
        nb, nn, _k = _b(node)
        n = ctypes.c_uint64()
        rc = self._lib.fylite_rs_mds_read(
            self._h, self._verb(verb), nb, nn, sub, len(items),
            1 if inside else 0, ctypes.byref(n))
        if rc != 0:
            self._fail(f"read({verb!r}, {node!r})", rc)
        out = np.empty(int(n.value), dtype=np.float64)
        rc = self._lib.fylite_rs_mds_last_f64(self._h, out, out.size)
        if rc != 0:
            self._fail("last_f64", rc)
        nd = ctypes.c_uint64()
        self._lib.fylite_rs_mds_last_dims(self._h, np.empty(0, np.uint64), 0,
                                          ctypes.byref(nd))
        dims = np.empty(int(nd.value), dtype=np.uint64)
        if dims.size:
            self._lib.fylite_rs_mds_last_dims(self._h, dims, dims.size,
                                              ctypes.byref(nd))
        return out, tuple(int(d) for d in dims)

    def close(self) -> None:
        if getattr(self, "_h", None) is not None:
            self._lib.fylite_rs_mds_close(self._h)
            self._h = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
