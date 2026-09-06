"""Per-channel source assembly (SI) for the transport core (FYL-DESIGN-03 P0).

The physics formulas all exist already and are NOT re-transcribed here:
radiation / exchange are the kernel's (`sources.rs`, CGS with eV
temperatures — the flux-match target side keeps using them directly), the
collision rates in :mod:`fylite.scenario.model.mapping`, and the heating profiles come from
the actuator modules (:mod:`fylite.scenario.model.nbi` / :mod:`fylite.scenario.model.lh`)
already in absolute W/m³.  What was missing for the time-dependent core
(the kernel's ``transport_step``, reached through :mod:`fylite.kernel`) is
only this thin layer:

* SI wrappers over the CGS formula tier (m⁻³ / eV / T / m in, W/m³ out);
* the NRL parallel Spitzer resistivity for the formula-tier Ohmic channel;
* the **channel grammar** — :func:`build_channel_descriptors` parses a
  declared variable set (``["ion/D/density_thermal", "electrons/temperature",
  "psi"]``) into one :class:`ChannelDescriptor` per solvable channel, carrying
  the by-name keys the source and coefficient containers are read with.  The
  paths key plain nested dicts here, not IDS nodes; the grammar is kept
  IDENTICAL to fytrans (rev ``6b14d6ef``, ``fytrans/channels.py``, MIT, same
  authorship) so a declaration round-trips between the two hosts, and
  ``tests/test_channels.py`` compares them whenever fytrans is importable.
  Structural roles stay out of named channels: electron density is the
  quasi-neutrality closure (declaring it is an error), and the psi
  current-diffusion channel is driven by an explicit switch.  The grammar
  decides nothing about physics — the finite-volume numerics are the
  kernel's (``rust/fylite/src/transport.rs``).
* :class:`SourceSet` — the per-channel accumulator keyed by that grammar,
  with the volume-integral ledger that is the P0 power-balance self-check
  (couplings enter both sides in one call, so the books cannot half-close).

EAST posture per the design: a measured P_rad profile, when available, outranks
the formula tier — ``add()`` it directly instead of calling the formulas.
"""
from __future__ import annotations

import dataclasses
import enum

import numpy as np

from ... import kernel
from . import mapping

__all__ = ["ChannelKind", "ChannelDescriptor", "build_channel_descriptors",
           "exchange_si", "radiation_si", "sync_si", "spitzer_eta",
           "alpha_si", "ohmic_si", "SourceSet", "solve_te_ti", "solve_density",
           "quasi_neutral_ne", "solve_psi", "solve_momentum", "solve_core"]

# --------------------------------------------------------------------------- #
# channel grammar
# --------------------------------------------------------------------------- #
class ChannelKind(enum.Enum):
    """通道类别（决定容量权/度量权构造与求解器内的分派）。"""

    DENSITY = "density"          # 粒子道（逐非杂质离子）
    TEMPERATURE = "temperature"  # 热道（逐离子 + 电子）
    CURRENT = "current"          # psi 电流扩散（结构性，由 solve_current_diffusion 驱动）
    MOMENTUM = "momentum"        # 环向动量道（solve_momentum；ω 为未知量）


@dataclasses.dataclass(frozen=True)
class ChannelDescriptor:
    """单条可解通道的按名装配信息（路径为平实嵌套 dict 的键，语法与 fytrans 同形）。"""

    path: str
    """变量声明路径 = BC 键，如 ``"ion/D/density_thermal"`` / ``"psi"``。"""

    kind: ChannelKind
    """通道类别（权构造与求解分派按此进行）。"""

    species: str
    """物种句柄：``"ion"`` / ``"electrons"``（``psi`` 道为 ``""``）。"""

    label: str | None
    """离子名（``species == "ion"`` 时，如 ``"D"``）；其余 ``None``。"""

    state_path: str
    """剖面容器下的态路径（读 prev / 写 next），如 ``"ion/D/density_thermal"``。"""

    coeff_prefix: str | None
    """输运系数前缀（``{prefix}/d`` 扩散、``{prefix}/v`` pinch）。"""

    source_path: str | None
    """显式源路径（``S_exp``）；隐式汇取 ``{source_path}_implicit``。"""

    @property
    def coeff_path(self) -> str | None:
        """扩散系数求和路径。"""
        return None if self.coeff_prefix is None else f"{self.coeff_prefix}/d"

    @property
    def pinch_path(self) -> str | None:
        """pinch（对流）系数求和路径。"""
        return None if self.coeff_prefix is None else f"{self.coeff_prefix}/v"

    @property
    def source_implicit_path(self) -> str | None:
        """隐式线性汇路径（``S = S_exp − S_imp·y``，缺省 0）。"""
        return None if self.source_path is None else f"{self.source_path}_implicit"


_DENSITY_FIELDS = ("density_thermal", "density")
_MOMENTUM_FIELDS = ("momentum_tor",)


def _parse_variable(path: str) -> ChannelDescriptor:
    """单条声明路径 → 描述子；不可解析/结构性冲突路径 fail-loud。"""
    parts = str(path).split("/")
    match parts:
        case ["psi"]:
            return ChannelDescriptor(path=path, kind=ChannelKind.CURRENT, species="",
                                     label=None, state_path="grid/psi",
                                     coeff_prefix=None, source_path=None)
        case ["ion", label, field] if field in _DENSITY_FIELDS:
            return ChannelDescriptor(path=path, kind=ChannelKind.DENSITY, species="ion",
                                     label=label,
                                     state_path=f"ion/{label}/density_thermal",
                                     coeff_prefix=f"ion/{label}/particles",
                                     source_path=f"ion/{label}/particles")
        case ["ion", label, "temperature"]:
            return ChannelDescriptor(path=path, kind=ChannelKind.TEMPERATURE,
                                     species="ion", label=label,
                                     state_path=f"ion/{label}/temperature",
                                     coeff_prefix=f"ion/{label}/energy",
                                     source_path=f"ion/{label}/energy")
        case ["ion", label, field] if field in _MOMENTUM_FIELDS:
            return ChannelDescriptor(path=path, kind=ChannelKind.MOMENTUM, species="ion",
                                     label=label, state_path=f"ion/{label}/{field}",
                                     coeff_prefix=f"ion/{label}/momentum_tor",
                                     source_path=f"ion/{label}/momentum_tor")
        case ["electrons", field] if field in _DENSITY_FIELDS:
            raise ValueError(
                f"variable {path!r}: electron density is the quasi-neutrality closure "
                f"(structural), not a solvable named channel"
            )
        case ["electrons", "temperature"]:
            return ChannelDescriptor(path=path, kind=ChannelKind.TEMPERATURE,
                                     species="electrons", label=None,
                                     state_path="electrons/temperature",
                                     coeff_prefix="electrons/energy",
                                     source_path="electrons/energy")
        case _:
            raise ValueError(
                f"unrecognized transport variable {path!r} (expected "
                f"'ion/<label>/density_thermal', 'ion/<label>/temperature', "
                f"'ion/<label>/momentum_tor', 'electrons/temperature' or 'psi')"
            )


def build_channel_descriptors(variables: list) -> list[ChannelDescriptor]:
    """变量集声明 → 描述子列表（保持声明顺序；重复声明 fail-loud）。"""
    descriptors: list[ChannelDescriptor] = []
    seen: set[str] = set()
    for path in variables or []:
        desc = _parse_variable(path)
        if desc.state_path in seen:
            raise ValueError(f"duplicate transport variable declaration: {path!r}")
        seen.add(desc.state_path)
        descriptors.append(desc)
    return descriptors


# --------------------------------------------------------------------------- #
# SI source tier
# --------------------------------------------------------------------------- #
_ERG_CM3_TO_W_M3 = 0.1   # 1 erg cm⁻³ s⁻¹ = 0.1 W m⁻³
_M3_TO_CM3 = 1e-6        # 1 m⁻³ = 1e-6 cm⁻³


def _ion_arrays(ions):
    ni = [np.asarray(ion["ni"], float) * _M3_TO_CM3 for ion in ions]
    z = [float(ion["z"]) for ion in ions]
    mass = [float(ion["a"]) * mapping.MP for ion in ions]
    names = [str(ion.get("name", "")) for ion in ions]
    return ni, z, mass, names


def exchange_si(ne, te, ti, ions):
    """Collisional e→i exchange power density [W/m³], **positive to ions**.

    ``ions``: per-ion dicts with ``z`` (charge number), ``a`` (mass, amu) and
    ``ni`` (m⁻³).  ``ne`` m⁻³, ``te``/``ti`` eV (common ion temperature — the
    fytrans two-temperature model).  Formula tier: `mapping.collision_rates`
    ``nu_exch`` × `kernel.exchange_power`."""
    ne_cgs = np.asarray(ne, float) * _M3_TO_CM3
    te = np.asarray(te, float)
    ti = np.asarray(ti, float)
    ni, z, mass, _ = _ion_arrays(ions)
    rates = mapping.collision_rates(ne_cgs, te, ni, [ti] * len(z), mass, z)
    s_cgs = kernel.exchange_power(rates["nu_exch"], ne_cgs, te, ti)
    return s_cgs * _ERG_CM3_TO_W_M3


def radiation_si(ne, te, ions) -> dict:
    """Bremsstrahlung + line radiation [W/m³] (`kernel.rad_ion` in SI).

    ``ions`` need ``name`` (ADAS species — unknown names contribute zero line
    radiation, upstream's behaviour), ``z`` and ``ni``.  Returns
    ``{"brem", "line", "total"}``; only ``total`` is the ADAS value, the split
    is bookkeeping."""
    ne_cgs = np.asarray(ne, float) * _M3_TO_CM3
    ni, z, _, names = _ion_arrays(ions)
    out = kernel.rad_ion(np.asarray(te, float), ne_cgs, ni, z, names)
    return {k: v * _ERG_CM3_TO_W_M3 for k, v in out.items()}


def alpha_si(ne, te, ti, ions=None, *, dt_fraction: float = 0.5,
             zeff: float = 1.0) -> dict:
    """D-T alpha heating [W/m³] and its e/i split (``kernel.alpha_heating``).

    ``te``/``ti`` in eV, as everywhere on this side; the kernel takes T_i in
    keV and the conversion happens here, which is what this layer is for.
    ``ions`` (as elsewhere: ``z``, ``a``, ``ni``) supplies the field-ion sum
    ``Σ n_j Z_j²/(n_e A_j)`` that sets the alpha's critical energy; omit it
    and the sum is a pure-deuterium plasma's.

    Returns ``{"total", "electrons", "ions", "e_crit"}`` — the keys the
    :class:`SourceSet` channels want, plus the critical energy for a caller
    that wants to see where the split came from.

    ★The channel is the kernel's assembly of its own Bosch-Hale reactivity
    and its own Stix partition, gated by the 0-D tier's alpha power rather
    than by an oracle: there is no D-T case in this repository.
    """
    ne = np.asarray(ne, float)
    zsum = 0.5
    if ions:
        ni, z, mass, _ = _ion_arrays(ions)
        #: `_ion_arrays` returns CGS densities and masses in kg; the sum is
        #: dimensionless, so it is built from the ratios and neither unit
        #: survives into it
        zsum = float(np.sum([np.mean(n_ * zz ** 2
                                     / np.maximum(ne * _M3_TO_CM3, 1e-30)
                                     / (m_ / mapping.MP))
                             for n_, zz, m_ in zip(ni, z, mass)]))
    out = kernel.alpha_heating(ne=ne, te=np.asarray(te, float),
                               ti_kev=np.asarray(ti, float) * 1e-3,
                               dt_fraction=dt_fraction, zeff=zeff,
                               zsum=max(zsum, 1e-6))
    return {"total": out["p_total"], "electrons": out["p_e"],
            "ions": out["p_i"], "e_crit": out["e_crit"]}


#: Rosenbluth 壁反射系数，同步辐射公式用。
#: ★★2026-09-01：这是 `scenario/model/sources.py` 整个模块最后剩下的东西。那个模块
#: 曾是辐射功率 / 电子—离子交换 / 体积分的 SI 面（`tgyro_source.f90` /
#: `tgyro_rad.f90` / `tgyro_volume_int.f90` 的移植），**那些物理现在都是内核的**
#: （`sources.rs`，经 `fylite.kernel`），SI 包装在本模块。一个模块活着只为托一个常数，
#: 就该把常数交给它唯一的读者——常数搬过来，模块退休。
#: ★★另有一处**同名遮蔽**要留意：本模块多个函数有 `sources: SourceSet` 形参，
#: 与那个模块重名。`sources.total(...)` 一直是形参；只有这里的 `SYNC_REFLECTION`
#: 曾是模块。两者同名共处，是把「模块只剩一个常数」拖了这么久没人察觉的原因之一。
SYNC_REFLECTION = 0.8


def sync_si(ne, te, b_t, *, minor_radius, aspect_ratio,
            reflection=SYNC_REFLECTION):
    """Synchrotron radiation [W/m³] (`kernel.rad_sync` in SI: ``b_t`` [T] the
    local toroidal field — NOT B_unit — ``minor_radius`` [m], R/a)."""
    #: ★no ``abs`` here: the field MAGNITUDE is the kernel's convention and
    #: it already takes it.  Stating it on both sides is how a sign
    #: convention ends up meaning two things.
    s_cgs = kernel.rad_sync(
        np.asarray(te, float), np.asarray(ne, float) * _M3_TO_CM3,
        np.asarray(b_t, float) * 1e4,
        aspect_ratio=aspect_ratio, a_cm=float(minor_radius) * 1e2,
        reflection=reflection)
    return s_cgs * _ERG_CM3_TO_W_M3


def spitzer_eta(te, zeff=1.0, lnlam=17.0):
    """Parallel Spitzer resistivity [Ω·m] — NRL formulary,
    ``η_∥ = 0.51 η_⊥`` with ``η_⊥ = 1.03e-2 Z lnΛ Te^-1.5`` Ω·cm (Te in eV;
    corrected at ABI v111, T-A18 — the 0.51 used to be missing and the ohmic
    power was high by about a factor of two).  The formula tier of the
    Ohmic channel; the trapped-particle (neoclassical) correction is a
    documented refinement, not silently folded in."""
    out = kernel.spitzer_eta(te, zeff, lnlam)
    return out.reshape(np.shape(te)) if np.shape(te) else float(out[0])


def ohmic_si(j_par, eta):
    """Ohmic heating ``η j_∥²`` [W/m³] (to electrons); ``j_par`` [A/m²].

    The kernel's — it is one multiply, which is exactly why it kept being
    written at call sites, and the ohmic channel's two halves (this and
    :func:`spitzer_eta`) belong in one host or its neoclassical refinement
    can be applied to one of them only."""
    return kernel.ohmic_power(eta, j_par)


class SourceSet:
    """Per-channel source accumulator on a common ρ grid.

    ``add(path, label, s)`` registers a contribution (W/m³ for energy channels,
    m⁻³ s⁻¹ for particle ones) under a channel path in the fytrans grammar —
    the same keys :func:`build_channel_descriptors` produces
    (``"electrons/energy"``, ``"ion/D/energy"``, ``"ion/D/particles"``).
    ``total(path)`` is what the solver's ``source=`` argument consumes (after
    the assembly layer normalizes by the channel capacity); ``integrated()`` is
    the volume-integral ledger ``∫ s V' dρ`` [W] per (path, label) — the
    power-balance self-check of the P0 exit criterion.
    """

    def __init__(self, rho, vprime):
        self.rho = np.asarray(rho, float)
        self.vprime = np.asarray(vprime, float)
        if self.rho.shape != self.vprime.shape:
            raise ValueError("rho and vprime MUST share a shape")
        self._entries: list[tuple[str, str, np.ndarray]] = []

    def add(self, path: str, label: str, s) -> None:
        s = np.broadcast_to(np.asarray(s, float), self.rho.shape).copy()
        if not np.isfinite(s).all():
            raise ValueError(f"source {label!r} on {path!r} has non-finite values")
        self._entries.append((str(path), str(label), s))

    def add_exchange(self, s_exch, *, ion_path: str,
                     electron_path: str = "electrons/energy",
                     label: str = "exchange") -> None:
        """Register e↔i exchange on both channels at once (+ions, −electrons) —
        a coupling can never appear on one side only."""
        s = np.asarray(s_exch, float)
        self.add(ion_path, label, s)
        self.add(electron_path, label, -s)

    @property
    def paths(self) -> list[str]:
        seen: dict[str, None] = {}
        for path, _, _ in self._entries:
            seen.setdefault(path)
        return list(seen)

    def total(self, path: str) -> np.ndarray:
        out = np.zeros_like(self.rho)
        for p, _, s in self._entries:
            if p == path:
                out += s
        return out

    def volume_integral(self, s) -> float:
        """``∫ s V' dρ`` over the whole grid (trapezoid — the PDE grid is dense,
        unlike the sparse flux-match grid where a volume integral applies).

        The kernel's weighted trapezoid, so the ledger and the solver's
        source use the same rule on the same grid."""
        return float(kernel.volume_int(s, self.vprime, self.rho,
                                       mode="weighted")[-1])

    def integrated(self) -> dict[tuple[str, str], float]:
        """Volume-integrated ledger per (path, label) [W or 1/s]."""
        return {(p, lbl): self.volume_integral(s) for p, lbl, s in self._entries}

    def report(self) -> str:
        """Human-readable power-balance table per channel."""
        lines = []
        for path in self.paths:
            lines.append(f"{path}:")
            subtotal = 0.0
            for p, lbl, s in self._entries:
                if p == path:
                    w = self.volume_integral(s)
                    subtotal += w
                    lines.append(f"  {lbl:<16s} {w:+12.4e}")
            lines.append(f"  {'TOTAL':<16s} {subtotal:+12.4e}")
        return "\n".join(lines)


def solve_te_ti(
    rho,
    *,
    vprime,
    gm3,
    ne,
    ni,
    te,
    ti,
    chi,
    sources: SourceSet | None = None,
    ions=None,
    dt: float,
    max_outer: int = 500,
    tol_steady: float = 1e-9,
    n_coupling: int = 2,
    edge_te: float | None = None,
    edge_ti: float | None = None,
    electron_path: str = "electrons/energy",
    ion_path: str = "ion/D/energy",
    d_pc: float = 0.0,
    tol: float = 1e-10,
    max_inner: int = 60,
) -> dict:
    r"""Two-temperature (Te/Ti) evolution — the fytrans heat channels on plain
    arrays (FYL-DESIGN-03 P2, density locked per the design's deliberate
    deviation ②).

    The equation per species, in the fytrans conservation form on the physical
    ρ grid (``rho`` [m] — or any monotone flux label, as long as ``vprime`` =
    dV/dρ [m²] and ``gm3`` = ⟨|∇ρ|²⟩ are metrics of the SAME label):

        (3/2) ∂(V' n T)/∂t + ∂q/∂ρ = V' Q,
        q = −V' ⟨|∇ρ|²⟩ n χ ∂T/∂ρ

    mapped onto the kernel's two-weight FVM operator
    (the kernel's ``transport_step``, oracle-only since T-4 第八刀) with capacity C = (3/2) V' n,
    flux metric M = V' ⟨|∇ρ|²⟩ n, D = χ [m²/s] and
    C·S = V'·Q (T in eV, Q in W/m³).

    ``chi(rho, te, ti) -> (chi_e, chi_i)`` is the closure hook — analytic, or
    a TGLF+NEO adapter; it is re-evaluated every coupling iteration and held
    fixed inside each channel's inner Picard — the kernel's ``given`` closure,
    which is the loop a closure this expensive belongs to (``d_pc`` stabilizes
    a stiff one).
    ``sources`` carries every NON-exchange contribution per channel (W/m³);
    the collisional e↔i exchange is NOT taken from it — it depends on Te−Ti
    and is recomputed each coupling iteration from ``ions`` (omit ``ions`` to
    run the channels uncoupled).  Backward-Euler marching to steady, Dirichlet
    edges pinned at the initial profiles unless ``edge_te``/``edge_ti`` say
    otherwise.

    Returns ``{te, ti, outer_steps, steady, delta, s_exchange}``.
    """

    rho = np.asarray(rho, float)
    te = np.broadcast_to(np.asarray(te, float), rho.shape)
    ti = np.broadcast_to(np.asarray(ti, float), rho.shape)
    #: ne/ni are broadcast HERE and not left to the kernel face, because the
    #: exchange closure below reads them too — and `exchange_si` builds a
    #: per-ion CGS block that a bare scalar cannot be zipped against
    ne = np.broadcast_to(np.asarray(ne, float), rho.shape)
    ni = np.broadcast_to(np.asarray(ni, float), rho.shape)
    zero = np.zeros_like(rho)

    #: ★★The MARCH is the kernel's now — the Picard count, which state each
    #: pass advances from, the steady test and the non-finite stop.  What
    #: stays here is the callback: `chi` is a caller's callable (a TGLF+NEO
    #: evaluation is not something the kernel can call) and the exchange is
    #: an SI unit conversion around two kernel entries.
    #:
    #: ★It used to be the ONE channel whose outer loop lived on this side —
    #: `solve_density` and `solve_psi` had theirs in the kernel already — so
    #: the steady test existed twice, and the two were not obviously the
    #: same rule until they were put side by side.  They are literally one
    #: function now (`transport::steady_delta`).
    def closure(rho_k, te_k, ti_k):
        chi_e, chi_i = chi(rho_k, te_k, ti_k)
        s_exch = (exchange_si(ne, te_k, ti_k, ions) if ions is not None
                  else zero)
        return chi_e, chi_i, s_exch

    return kernel.two_temperature_march(
        rho, te, ti, ne=ne, ni=ni, vprime=vprime, gm3=gm3,
        q_e=(sources.total(electron_path) if sources is not None else zero),
        q_i=(sources.total(ion_path) if sources is not None else zero),
        closure=closure, dt=dt,
        edge_te=float(te[-1] if edge_te is None else edge_te),
        edge_ti=float(ti[-1] if edge_ti is None else edge_ti),
        max_outer=max_outer, tol_steady=tol_steady, n_coupling=n_coupling,
        d_pc=d_pc, tol=tol, max_inner=max_inner)


def solve_density(
    rho,
    *,
    vprime,
    gm3,
    n,
    d,
    v=0.0,
    source=0.0,
    dt: float,
    max_outer: int = 500,
    tol_steady: float = 1e-9,
    edge_n: float | None = None,
    d_pc: float = 0.0,
    tol: float = 1e-10,
    max_inner: int = 60,
) -> dict:
    r"""Particle channel (FYL-DESIGN-03 P3b) — the fytrans DENSITY weights on
    plain arrays:

        ∂(V' n)/∂t + ∂Γ/∂ρ = V' S,
        Γ = V' ⟨|∇ρ|²⟩ (−D ∂n/∂ρ + v·n)

    i.e. capacity C = V', flux metric M = V' ⟨|∇ρ|²⟩, and C·S_solver = V'·S so
    the solver source is the volumetric ``source`` [m⁻³ s⁻¹] itself.  ``d``
    [m²/s] and pinch ``v`` [m/s] may be arrays or callables ``f(rho, n)``,
    re-evaluated once per OUTER step and frozen inside the Picard loop: a
    gradient-driven particle closure is stiff the same way the heat one is,
    and it iterates in the same place — ``d_pc`` conditions the step either
    way.
    Density stays a per-ion quantity; electron density is the quasi-neutrality
    closure ``n_e = Σ z_s n_s`` and deliberately NOT a solvable channel here
    (the fytrans structural rule, enforced by the channel grammar).

    Backward-Euler marching to steady; Dirichlet edge pinned at the initial
    profile unless ``edge_n`` says otherwise.
    Returns ``{n, outer_steps, steady, delta}``.
    """

    rho = np.asarray(rho, float)
    n = np.asarray(n, float)
    #: ★the weights, the march and the steady test are the kernel's; what
    #: stays is the ONE thing this layer knows — where the edge is pinned
    #: when the caller did not say.
    edge = float(n[-1] if edge_n is None else edge_n)
    out = kernel.solve_density(rho, n, vprime=vprime, gm3=gm3, d=d, v=v,
                               source=source, dt=dt, edge=edge,
                               max_outer=max_outer, tol_steady=tol_steady,
                               d_pc=d_pc, tol=tol, max_inner=max_inner)
    return out


def quasi_neutral_ne(ions) -> np.ndarray:
    """Electron density from quasi-neutrality, ``n_e = Σ z_s n_s`` — the
    structural closure (never a solved channel).

    The kernel's; what stays here is reading ``z``/``ni`` out of the ion
    dicts, which is this layer's subject."""
    return kernel.quasi_neutral_ne([ion["z"] for ion in ions],
                                   [ion["ni"] for ion in ions])


def solve_psi(
    rho,
    *,
    vprime,
    gm2,
    fpol,
    b0,
    sigma_par,
    j_ni=0.0,
    psi,
    dt: float,
    n_steps: int = 1,
    edge_rate: float = 0.0,
    edge_psi: float | None = None,
    tol: float = 1e-11,
    max_inner: int = 30,
) -> dict:
    r"""Current diffusion — the fytrans ψ channel on plain arrays (P3b).

    The equation (fytrans module docstring, COCOS 17, full-turn ψ [Wb],
    Ḃ0-compression off — the fylite tier assumes a static vacuum field):

        σ_∥ ∂ψ/∂t = F²/(μ0 B0 ρ) ∂/∂ρ [ V'⟨|∇ρ|²/R²⟩/(4π² F) ∂ψ/∂ρ ]
                     − V'/(2πρ) · j_ni

    mapped, after multiplying by μ0 B0 ρ/F² (upstream's standardized form),
    onto the two-weight operator with capacity C = σ μ0 B0 ρ_safe/F², metric
    M = V'⟨|∇ρ|²/R²⟩/(4π²F), D = 1 and C·S = −μ0 B0 V' j_ni/(2π F²).

    Upstream regularizations transcribed as-is: ``rho_safe = max(ρ, h/4)`` in
    the capacity; near-axis V' rebuilt ∝ ρ and gm2 held constant over the two
    innermost nodes (the FSA ladder's axis extrapolation steps otherwise ring
    ψ by O(10%)); σ floored at 1 S/m; the solved ψ made monotone (repair
    beyond 1e-6 of the span is reported in the result, not silent).

    **Caller contract on ``j_ni``** (upstream's, load-bearing): the
    non-inductive current only — bootstrap + driven.  The Ohmic j = σE is the
    unknown of this equation; folding it into ``j_ni`` pins the lagged σE
    pattern into ψ and hollows the current profile within tens of steps.

    Edge drive: ``edge_psi`` pins ψ_b (default: its initial value); a nonzero
    ``edge_rate`` [Wb/s] advances ψ_b each step — dψ_b/dt is the (full-turn)
    boundary loop voltage, sign per COCOS 17 left to the caller's bookkeeping.

    Returns ``{psi, q, repaired [Wb], steps}`` with q = 2π B0 ρ/(∂ψ/∂ρ)
    (clipped to [0.05, 100] as upstream — flat-spot spikes poison downstream
    splines).
    """

    rho = np.asarray(rho, float)
    psi = np.asarray(psi, float)
    #: ★everything the docstring calls a regularisation is the kernel's
    #: now — rho_safe, the near-axis V'/gm2 rebuild, the sigma floor, the
    #: monotone repair and its reported size, and the q clip.  They are not
    #: taste: each is there because something rings without it, and a second
    #: host would have to be told all five.
    edge = float(psi[-1] if edge_psi is None else edge_psi)
    return kernel.solve_psi(rho, psi, vprime=vprime, gm2=gm2, fpol=fpol,
                            b0=b0, sigma_par=sigma_par, j_ni=j_ni, dt=dt,
                            n_steps=n_steps, edge_psi=edge,
                            edge_rate=edge_rate, tol=tol,
                            max_inner=max_inner)


#: ★``chi_from_flux`` was a bare forward to the kernel — its algebra moved to the kernel entry.


def solve_momentum(
    rho,
    omega,
    *,
    vprime,
    gm3,
    r2,
    ni,
    mass: float,
    chi_phi,
    torque=0.0,
    dt: float,
    edge: float | None = None,
    max_outer: int = 500,
    tol_steady: float = 1e-9,
    d_pc: float = 0.0,
    tol: float = 1e-10,
    max_inner: int = 60,
) -> dict:
    r"""Toroidal rotation — the momentum channel the grammar could declare
    and nothing could solve (P5).

    The equation, in the same conservation form the other channels use:

        ∂(V' n m ⟨R²⟩ ω)/∂t + ∂Π/∂ρ = V' T,
        Π = −V' ⟨|∇ρ|²⟩ n m ⟨R²⟩ χ_φ ∂ω/∂ρ

    so the capacity is ``C = V' n m ⟨R²⟩``, the flux metric
    ``M = V'⟨|∇ρ|²⟩ n m ⟨R²⟩`` and the source rate ``T/(n m ⟨R²⟩)``.
    Everything is SI: ω is an angular frequency [rad/s] and ``torque`` a
    torque density [J/m³] — there is no eV bridge here, which is the one
    place this differs from the heat channels beyond the 3/2.

    ★The declaration spells the channel ``ion/<label>/momentum_tor`` and the
    unknown here is ω.  They are the same channel in two variables —
    ``momentum_tor = n m ⟨R²⟩ ω`` — and ω is the one the diffusive form is
    written in (the flux carries ∂ω/∂ρ), so it is the one solved.

    ★★``chi_phi`` is PRESCRIBED here, and as of 2026-08-29 there is a
    closure that can produce one:
    :func:`fylite.scenario.model.closure.momentum_chi_phi` turns the
    port's toroidal stress — verified against upstream's own
    ``out.tglf.gbflux`` to 2.3e-5 with rotation on — into an effective
    diffusivity, given a rotation profile WITH SHEAR.  On a flat profile
    it still refuses, because there the stress is the residual stress: a
    torque, which belongs in ``torque=`` and not in a diffusivity.  A
    caller with its own ``chi_phi`` — measured, scaled, or from another
    code — still passes it here.  The numerics — the march, the steady
    rule, the non-finite stop — are the kernel's.
    """
    rho = np.asarray(rho, float)
    omega = np.broadcast_to(np.asarray(omega, float), rho.shape)
    return kernel.solve_momentum(
        rho, omega, vprime=vprime, gm3=gm3, r2=r2, dens=ni, mass=mass,
        chi_phi=chi_phi, torque=torque, dt=dt,
        edge=float(omega[-1] if edge is None else edge), max_outer=max_outer,
        tol_steady=tol_steady, d_pc=d_pc, tol=tol, max_inner=max_inner)


def solve_core(
    rho,
    *,
    vprime,
    vprime_old=None,
    gm3,
    ne=None,
    te,
    ti,
    chi=None,
    heat: bool = True,
    sources: SourceSet | None = None,
    ions=None,
    particles=None,
    current=None,
    psi=0.0,
    gm2=1.0,
    fpol=1.0,
    b0: float = 1.0,
    b0_dot: float = 0.0,
    dt: float,
    dt_target: float = 0.0,
    dt_min: float = 0.0,
    dt_max: float = 0.0,
    max_outer: int = 500,
    tol_steady: float = 1e-9,
    n_coupling: int = 2,
    edge_te: float | None = None,
    edge_ti: float | None = None,
    edge_ni=None,
    edge_psi: float | None = None,
    edge_psi_rate: float = 0.0,
    electron_path: str = "electrons/energy",
    ion_path: str = "ion/D/energy",
    d_pc: float = 0.0,
    tol: float = 1e-10,
    max_inner: int = 60,
) -> dict:
    r"""Every core channel on ONE time step — the kernel's core march.

    :func:`solve_te_ti`, :func:`solve_density` and :func:`solve_psi` each own
    a time step, so a caller that wants more than one of them has to
    interleave them: three advances from three different states, in an
    operator-splitting order that is a contract nobody wrote down.  That
    split is not neutral — the heat capacity is ``(3/2)V'n``, so a density
    channel moving beside the temperatures moves the very weight they are
    solved with, and a Te advanced on the new ``n`` alone creates
    ``(3/2)V'T·dn`` of energy every step.

    Here every switched-on channel advances from the same old state on the
    same ``dt``, the closure is iterated over all of them together, and the
    heat pair carries the density's motion.  The steady test is one rule
    over every ACTIVE channel.

    Hooks, all optional and all evaluated per coupling pass:

    ``chi(rho, te, ti) -> (chi_e, chi_i)``
        the heat closure, as in :func:`solve_te_ti`.
    ``particles(state) -> (d_n, v_n)``
        switches the density channel ON; without it the densities are held.

        ★★**There is no fuelling model in this package** — no pellet, no gas
        puff, no beam particle source — so ``s_n`` (through ``sources``) is
        whatever the caller measured or got from another code, and zero is
        a legitimate answer meaning "redistribution only".  That is the
        design's own deliberate deviation ② ("粒子源无可信 EAST 模型"), and
        it is a posture rather than an omission: a fuelling model written
        here would have neither a credible form for this device nor any
        oracle to check it against, which is the same reason the
        alpha-heating channel was refused until its two halves could be
        assembled from pieces already pinned.  The provenance of every
        transport result says so, so a number copied into a slide carries
        it.
    ``current(state) -> (sigma_par, j_ni)``
        switches the ψ channel ON.  ``j_ni`` is the NON-inductive current
        only — the caller contract :func:`solve_psi` documents.

    ``heat`` switches the temperature pair OFF when it is ``False``, and
    ``chi`` may then be omitted.

        ★★It exists for ONE caller and not for convenience: the stationary
        outer loop (T-C14 步 4) drives the ψ channel to steady state **on
        profiles a flux match has just solved**, and a heat channel running
        beside it would be a second, differently obtained answer to the
        question the Newton machine had just answered.  The kernel has
        always carried the flag; this layer simply did not pass it on —
        which is why the browser could express that march and this package
        could not.

    ★The two coefficient hooks take the whole ``state``
    (``{rho, te, ti, ne, psi}``) and not a chosen few of its arrays: a
    particle diffusivity depends on the temperatures as much as on the
    density, and a hook that cannot see them has to be handed them by a
    caller who then owns the consistency.  ``chi`` keeps its
    ``(rho, te, ti)`` shape because that is the contract every heat-channel
    driver in this package already speaks.

    ``vprime_old`` is the metric the profiles arrived on when the caller
    re-traced it between rounds — the ``dV'/dt`` term, carried across this
    call's first step; ``b0_dot`` [T/s] adds the label drift.  Both default
    off, and a caller that does not move its metric gets the arithmetic it
    got before they existed.

    ``ions`` — the same list :func:`solve_te_ti` takes (``z``, ``a``,
    ``ni``) — is now TWO things at once, which is the point: it recomputes
    the collisional exchange every pass, AND it is the set of density
    channels.  ★★The electron density is then not an input at all: it is
    ``Σ Z_s n_s``, rebuilt whenever the ions move.  That is the channel
    grammar's own rule ("electron density is the quasi-neutrality closure,
    structural, not a solvable named channel") and it is what lets an
    impurity transport differently from the main ion — which a single
    ``n_e`` channel with a fixed dilution could not express.

    ★With the density channel OFF, ``ions`` is only the exchange list and
    ``ne`` is the prescribed (locked) electron density — bit for bit what
    :func:`solve_te_ti` does.  With it ON, ``ions`` is the channel set and
    an ``ne`` beside it is refused rather than silently resolved.

    Returns the kernel's result dict — ``{te, ti, ne, psi, q, s_exchange,
    outer_steps, steady, delta, psi_repaired}``.
    """
    rho = np.asarray(rho, float)
    shape = rho.shape
    te = np.broadcast_to(np.asarray(te, float), shape)
    ti = np.broadcast_to(np.asarray(ti, float), shape)
    #: ★★What `ions` MEANS depends on whether the density channel is on,
    #: and the two meanings are kept apart rather than merged:
    #:
    #:  * density OFF — `ions` is the exchange partner list and nothing
    #:    else; `n_e` is prescribed, and the heat pair is weighted by it on
    #:    both sides, which is bit-for-bit what `solve_te_ti` did.
    #:  * density ON — `ions` is the set of CHANNELS, and `n_e` is not an
    #:    input at all: it is `sum_s Z_s n_s`.  An `ne` passed beside them
    #:    is a second, silently different plasma, so it is refused.
    if particles is not None:
        if ions is None:
            raise ValueError(
                "solve_core: the density channel evolves the ions, so it "
                "needs `ions`; `ne` is quasi-neutrality's answer and not an "
                "input")
        if ne is not None:
            raise ValueError(
                "solve_core: give ions OR ne, not both — with the density "
                "channel on the electron density is quasi-neutrality's "
                "answer and an ne passed beside it is a second, silently "
                "different plasma")
        z = [float(ion["z"]) for ion in ions]
        ni = [np.broadcast_to(np.asarray(ion["ni"], float), shape)
              for ion in ions]
    else:
        if ne is None:
            raise ValueError(
                "solve_core: needs `ne` when the density channel is off")
        z = [1.0]
        ni = [np.broadcast_to(np.asarray(ne, float), shape)]
    ni_block = np.concatenate([np.asarray(v, float) for v in ni])
    zero = np.zeros_like(rho)

    if heat and chi is None:
        raise ValueError(
            "solve_core: the heat channel needs `chi`; pass heat=False to "
            "march without it")

    def closure(state):
        #: ★with the heat pair off there is no χ to ask for, and asking for
        #: one anyway would make a caller supply a closure for a channel
        #: that is not running — which is how a prescribed χ quietly becomes
        #: part of a result nobody solved with it.
        out = {}
        if heat:
            chi_e, chi_i = chi(state["rho"], state["te"], state["ti"])
            out["chi_e"], out["chi_i"] = chi_e, chi_i
        #: ★the exchange is recomputed HERE and not taken from the source
        #: set, for the reason `solve_te_ti` states: it depends on Te − Ti
        #: and so changes with every pass
        #: ★the exchange is a term in the HEAT pair's equations, so with
        #: that pair off it is not merely unused — there is nothing for it
        #: to be a term in.
        if ions is not None and heat:
            #: ★★the exchange is evaluated at the densities the march is
            #: ACTUALLY at — each species' own channel, straight out of the
            #: state — WHEN those channels are the ones evolving.  With the
            #: density channel off the composition is what the caller said
            #: it was and the state carries no per-ion densities to read.
            if particles is not None:
                block = np.asarray(state["ni"], float).reshape(len(ions), -1)
                ions_now = [{**ion, "ni": block[k]}
                            for k, ion in enumerate(ions)]
            else:
                ions_now = ions
            out["s_exchange"] = exchange_si(state["ne"], state["te"],
                                            state["ti"], ions_now)
        if particles is not None:
            d_n, v_n = particles(state)
            out["d_n"], out["v_n"] = d_n, v_n
        if current is not None:
            sigma_par, j_ni = current(state)
            out["sigma_par"], out["j_ni"] = sigma_par, j_ni
        return out

    return kernel.core_march(
        rho, te=te, ti=ti, ni=ni_block, z=z, psi=psi,
        vprime=vprime, vprime_old=vprime_old, gm3=gm3, gm2=gm2, fpol=fpol,
        b0=b0, b0_dot=b0_dot,
        q_e=(sources.total(electron_path) if sources is not None else zero),
        q_i=(sources.total(ion_path) if sources is not None else zero),
        #: ★one source block per ion.  A `SourceSet` is keyed by the
        #: channel path, so the per-ion particle sources come out under
        #: their own names — and a species the caller did not fuel gets
        #: zeros rather than the main ion's source.
        s_n=(np.concatenate([
            sources.total(f"ion/{ion.get('name', k)}/particles")
            if sources is not None else zero
            for k, ion in enumerate(ions or [{}])])
             if particles is not None else zero),
        closure=closure, dt=dt, dt_target=dt_target,
        dt_min=dt_min, dt_max=dt_max,
        edge_te=float(te[-1] if edge_te is None else edge_te),
        edge_ti=float(ti[-1] if edge_ti is None else edge_ti),
        edge_ni=edge_ni,
        edge_psi=float(np.broadcast_to(np.asarray(psi, float), shape)[-1]
                       if edge_psi is None else edge_psi),
        edge_psi_rate=edge_psi_rate, heat=heat,
        density=particles is not None, current=current is not None,
        max_outer=max_outer, tol_steady=tol_steady, n_coupling=n_coupling,
        d_pc=d_pc, tol=tol, max_inner=max_inner)
