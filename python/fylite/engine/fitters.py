"""Profile representation — the interpolant a fitted 1-D profile is read
through, and its logarithmic gradient.

★★This was a pluggable BACKEND FAMILY, ``profile_fitter``, with two
members.  They were ``LinearFitter`` and ``PchipFitter``, and the whole of
the difference between them was the string ``"linear"`` or ``"pchip"``
handed to :class:`_Interp`, which dispatches to :func:`fylite.kernel.interp`
or :func:`fylite.kernel.pchip`.  Two classes, a ``ProfileFitter``
protocol, two registry entries and a family — for one argument that the
class below already took.

The registry stays where it earns its keep: a family whose members are
different MODELS.  Which interpolant reads a profile is not a model, it is
a ``kind``, and it is one now (:func:`fit`).
"""

from __future__ import annotations

import typing

#: The interpolants a profile can be read through, and what each costs.
#: ★``"linear"`` is the pre-K-18 default (``np.interp``), byte-identical.
#: ``"pchip"`` is the monotone cubic, and the reason to want it is the
#: DERIVATIVE: a linear interpolant's is a staircase, and ``dlnfdr`` below
#: is what a closure consumes.
KINDS = ("linear", "pchip")


@typing.runtime_checkable
class ProfileEvaluator(typing.Protocol):
    """A fitted 1-D profile: callable for the value, ``dlnfdr`` for the
    a-normalized logarithmic gradient ``-d(ln f)/d(r/a)`` downstream kernels consume."""

    def __call__(self, xq): ...
    def dlnfdr(self, xq): ...


class _Interp:
    """Evaluator over sample nodes ``(x, y)`` with a pluggable interpolant."""

    def __init__(self, x, y, kind: str):
        import numpy as np
        if kind not in KINDS:
            raise ValueError(f"profile kind must be one of {KINDS}, "
                             f"not {kind!r}")
        self._x = np.asarray(x, float)
        self._y = np.asarray(y, float)
        self._kind = kind
        #: ★no optional accelerator here any more.  It used to be "pchip
        #: when scipy is importable, LINEAR when not" — two different
        #: interpolants behind one name, and the difference is exactly what
        #: the fitter exists for: a linear interpolant's derivative is a
        #: staircase.  The kernel carries the monotone cubic, so the
        #: closure input does not depend on what happens to be installed.

    def __call__(self, xq):
        import numpy as np

        from .. import kernel
        q = np.asarray(xq, float)
        if self._kind == "pchip":
            return kernel.pchip(self._x, self._y, q)
        return kernel.interp(q, self._x, self._y)

    def dlnfdr(self, xq):
        # a-normalized log gradient on the query grid; matches the kernel's log-gradient
        import numpy as np

        from .. import kernel
        return kernel.gradient(self(xq), np.asarray(xq, float), log=True)


def fit(x, y, *, kind: str = "linear") -> ProfileEvaluator:
    """Read the samples ``(x, y)`` through one of :data:`KINDS`.

    ★The whole of the retired ``profile_fitter`` family, as the one
    argument it always was.  An unknown ``kind`` raises here rather than at
    the first evaluation.
    """
    return _Interp(x, y, kind)
