"""Time-dependent parameters for the 1.5-D line — a thin host-side layer.

A ``core_march`` driver has to say how a power, a boundary value or a
density target moves through a discharge.  The 0-D line already has a
shape for that — the kernel's four-phase trapezoid
(``code/waveform`` since T-4 第二十二刀; the flat ``zerod_waveform`` is oracle-only) — but it is a SHAPE, parameterised
by four phase times, and the 1.5-D line needs the other thing: an
arbitrary series a caller states point by point, one per quantity, each on
its own time axis.

★★**This layer does NOT re-implement the trapezoid, and must not.**  The
phase boundaries decide what a run IS — they appear in the ramp rates, in
the flux budget and in the label a slice is reported under — and the
kernel is their single source across hosts.  :func:`from_phases` builds a
:class:`Waveform` BY CALLING it, so a trapezoid described here and a
trapezoid on the 0-D page are the same numbers rather than two spellings.

★It stays in the host, not the kernel, on purpose: the kernel's stated
architecture is that closures and source terms arrive from the host
(``transport.rs``: *"what arrives here is a measurement or another code's
answer"*).  A time axis is the same kind of thing.  Nothing here touches
the ABI.

The two interpolation modes are TORAX's (``interpolated_param.py``):

``"linear"``
    piecewise linear between the stated points — for a quantity that
    ramps, like a heating power or a density target.
``"step"``
    the value of the most recent point at or before ``t`` — for a
    quantity that is switched, like a valve or a controller set-point.
    ★A ramp is the WRONG default for a switched quantity: it invents a
    half-open valve for the whole interval between two settings.

Outside the stated range both modes CLAMP to the end values, and say so:
a waveform is a statement about a window, and extrapolating a heating
power past the last point the user gave is inventing a discharge.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import kernel

__all__ = ["MODES", "Waveform", "WaveformSet", "constant", "from_phases"]

MODES = ("linear", "step")


@dataclass(frozen=True)
class Waveform:
    """One quantity's value against time.

    ``t`` strictly increasing [s]; ``v`` the same length.  A single point
    is legal and means a constant — that is what a caller who has one
    number should be able to say without inventing a second time.
    """

    t: np.ndarray
    v: np.ndarray
    mode: str = "linear"
    name: str = ""

    def __post_init__(self):
        t = np.atleast_1d(np.asarray(self.t, float))
        v = np.atleast_1d(np.asarray(self.v, float))
        object.__setattr__(self, "t", t)
        object.__setattr__(self, "v", v)
        who = f"{self.name}: " if self.name else ""
        if self.mode not in MODES:
            raise ValueError(f"{who}mode must be one of {MODES}, "
                             f"not {self.mode!r}")
        if t.size != v.size:
            raise ValueError(f"{who}{t.size} times against {v.size} values")
        if t.size == 0:
            raise ValueError(f"{who}a waveform needs at least one point")
        if t.size > 1 and not np.all(np.diff(t) > 0):
            #: ★refused rather than sorted: a caller whose times are out of
            #: order has a different bug than the one sorting would hide,
            #: and a duplicated time is an ambiguity no rule resolves.
            raise ValueError(f"{who}times must be strictly increasing")
        if not np.all(np.isfinite(t)) or not np.all(np.isfinite(v)):
            raise ValueError(f"{who}times and values must be finite")

    @property
    def window(self) -> tuple[float, float]:
        """The interval the caller actually stated."""
        return float(self.t[0]), float(self.t[-1])

    def at(self, t):
        """The value at ``t`` [s], clamped to :attr:`window` outside it."""
        q = np.atleast_1d(np.asarray(t, float))
        if self.t.size == 1:
            out = np.full(q.shape, float(self.v[0]))
        elif self.mode == "linear":
            #: ★the KERNEL's interpolation, not numpy's — the same routine
            #: every profile in this package is resampled with, so a
            #: waveform and a profile agree about what "between" means.
            out = np.asarray(kernel.interp(q, self.t, self.v), float)
        else:
            idx = np.searchsorted(self.t, q, side="right") - 1
            out = self.v[np.clip(idx, 0, self.t.size - 1)]
        lo, hi = self.window
        out = np.where(q <= lo, self.v[0], out)
        out = np.where(q >= hi, self.v[-1], out)
        return out if np.ndim(t) else float(out[0])

    def outside_window(self, t) -> bool:
        """Whether any of ``t`` falls outside what the caller stated.

        ★Clamping is the behaviour and this is how a driver finds out it
        happened.  A run that silently held the last power for another
        five seconds is a different discharge.
        """
        lo, hi = self.window
        q = np.atleast_1d(np.asarray(t, float))
        return bool(np.any(q < lo) or np.any(q > hi))


def constant(value: float, *, name: str = "") -> Waveform:
    """A quantity that does not move — one point, stated once."""
    return Waveform(np.array([0.0]), np.array([float(value)]), name=name)


def from_phases(phases, *, which: str, flat: float = 0.0,
                start: float = 0.0, end: float = 0.0,
                n: int = 401, name: str = "") -> Waveform:
    """A :class:`Waveform` sampled from the KERNEL's four-phase trapezoid.

    ``phases`` is ``(t_breakdown, t_rampup_end, t_flattop_end, t_end)`` and
    ``which`` is one of :data:`fylite.kernel.WAVEFORMS`.

    ★★This exists so that the 0-D shape and a 1.5-D waveform are the same
    numbers.  The trapezoid is NOT reimplemented here — it is called, and
    the samples are its answer.  ``n`` is a sampling density, not a model:
    the phase corners are included exactly, so a linear waveform through
    these points reproduces the trapezoid on the corners no matter what
    ``n`` is.
    """
    ph = np.asarray(phases, float).ravel()
    if ph.size != 4:
        raise ValueError("phases must be 4: t_breakdown, t_rampup_end, "
                         "t_flattop_end, t_end")
    #: the corners, plus a uniform fill — the corners must be ON the axis
    #: or a linear reading of the samples rounds them off
    grid = np.unique(np.concatenate([ph, np.linspace(ph[0], ph[-1], int(n))]))
    #: ★T-4 第二十二刀 (2026-09-06): through `code/waveform` — the same
    #: `zerod::…` shapes, chosen by the index `which` names in
    #: :data:`fylite.kernel.WAVEFORMS`; the flat entry is oracle-only now
    try:
        code = kernel.WAVEFORMS.index(which)
    except ValueError:
        raise kernel.KernelError(f"unknown waveform {which!r}; "
                                 f"have {list(kernel.WAVEFORMS)}") from None
    from ..io import fydoc
    rec = fydoc.complete("code/waveform", {
        "settings": {"which": float(code), "flat": float(flat),
                     "start": float(start), "end": float(end)},
        "inputs": {"discharge": {"fylite:wave_phases": ph, "fylite:wave_t": grid}}})
    val = np.asarray(rec["fields"]["value"]["data"], float)
    return Waveform(grid, np.asarray(val, float), mode="linear",
                    name=name or which)


@dataclass
class WaveformSet:
    """A named bundle — ``{"p_nbi": Waveform, "n_e_sep": Waveform, ...}``.

    ``at(t)`` returns ``{name: value}``, which is the shape a driver wants
    at the top of a step.
    """

    waves: dict = field(default_factory=dict)

    def __setitem__(self, name: str, wave):
        if not isinstance(wave, Waveform):
            raise TypeError(f"{name}: expected a Waveform, got "
                            f"{type(wave).__name__}")
        self.waves[name] = wave

    def __getitem__(self, name: str) -> Waveform:
        return self.waves[name]

    def __contains__(self, name: str) -> bool:
        return name in self.waves

    def __len__(self) -> int:
        return len(self.waves)

    def at(self, t) -> dict:
        return {name: w.at(t) for name, w in self.waves.items()}

    def outside_window(self, t) -> list:
        """Which members are being read outside the window they stated."""
        return [name for name, w in self.waves.items() if w.outside_window(t)]

    def window(self) -> tuple[float, float]:
        """The interval EVERY member covers — the intersection, not the
        union.  ★A driver that ran to the union would be reading clamped
        values from some members while others were still being stated."""
        if not self.waves:
            raise ValueError("an empty set has no window")
        los, his = zip(*(w.window for w in self.waves.values()))
        return max(los), min(his)
