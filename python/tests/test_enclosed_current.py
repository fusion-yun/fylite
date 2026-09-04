"""`fyo.enclosed_plasma_current` — the「从 ψ 读 I_p」primitive (TODO T-C16).

★★WHY THIS FILE EXISTS.  Two open items need one quantity: the flux-matching
outer loop's steady-current step needs it to CHECK against the requested
`I_p` (T-C14 判据〔六〕), and the `I_p` controller needs it as its FEEDBACK
(T-C16).  Neither host had it.

What is judged here is the two things that can be wrong silently:

  the CONSTANT.  `I = V' <|grad rho|^2/R^2> (dpsi/drho) / (2 pi mu0)` is read
  off the kernel's own current-diffusion metric.  A 2*pi slip anywhere in
  that chain is invisible in a profile SHAPE and lands the answer a factor
  6 or 38 out, so the identification is pinned against a g-file that states
  its own current.

  the RESOLUTION STABILITY of the derivative.  A one-sided second-order end
  stencil is not stable on a packed ladder (measured; see the module's own
  note), and「换个面数就换个答案」 is the failure a single-resolution test
  cannot see.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fylite import fyo

ROOT = Path(__file__).resolve().parents[2]
GFILE = ROOT / "tests/data/FYDOC-CASE-12-synthetic/corpus/g_synthetic.geqdsk"

#: the current this g-file states in its own header [A]
GFILE_IP = 700_000.0

#: ★NOT a tolerance on「对不对」 but the ladder's own accuracy, stated as a
#: band rather than hidden: the reading sits 3.2 % below the header current
#: at every resolution, which is the quadrature (V′ 0.7 %, gm2 1.1 % — the
#: module's own note) and not a missing piece of current.  A gate that
#: allowed anything from 0.9 to 1.1 would pass a 2 % constant error too.
BAND = (0.960, 0.975)

pytestmark = pytest.mark.skipif(not GFILE.exists(),
                                reason="bundled synthetic g-file not present")


def _edge_ratio(n_surfaces: int) -> float:
    tm = fyo.transport_metrics(GFILE, n_surfaces=n_surfaces, edge=0.99)
    i = fyo.enclosed_plasma_current(tm["rho"], tm["vprime"], tm["gm2"],
                                    tm["psi"])
    return float(i[-1]) / GFILE_IP


def test_constant_is_identified_not_fitted():
    """The other candidates are out by 2*pi factors, so 1/(2 pi mu0) is named."""
    tm = fyo.transport_metrics(GFILE, n_surfaces=201, edge=0.99)
    rho = np.asarray(tm["rho"], float)
    base = (np.asarray(tm["vprime"], float) * np.asarray(tm["gm2"], float)
            * fyo.nonuniform_gradient(np.asarray(tm["psi"], float), rho))
    mu0 = fyo.MU0
    got = float((base / (2.0 * np.pi * mu0))[-1]) / GFILE_IP
    assert BAND[0] <= got <= BAND[1], got
    #: ★the near misses, so a future edit that "fixes" the 3 % by moving the
    #: constant has to explain why these three stop being wrong
    assert float((base / mu0)[-1]) / GFILE_IP > 5.0
    assert float((base / (4.0 * np.pi**2 * mu0))[-1]) / GFILE_IP < 0.2
    assert float((base * 2.0 * np.pi / mu0)[-1]) / GFILE_IP > 30.0


@pytest.mark.parametrize("n_surfaces", [81, 201, 401])
def test_edge_reading_is_resolution_stable(n_surfaces):
    """★Five-fold in surface count must not move the answer."""
    assert BAND[0] <= _edge_ratio(n_surfaces) <= BAND[1]


def test_edge_reading_does_not_drift_with_resolution():
    """★★And not just「都在带内」: the three must agree with EACH OTHER."""
    ratios = [_edge_ratio(n) for n in (81, 201, 401)]
    spread = max(ratios) - min(ratios)
    assert spread < 2e-3, ratios


def test_gradient_is_the_standard_stencil():
    """The hand-written derivative IS `numpy.gradient` — a free cross-check.

    ★Written out rather than delegated so the browser host can carry the
    same six lines; this asserts that writing it out did not change it.
    """
    tm = fyo.transport_metrics(GFILE, n_surfaces=201, edge=0.99)
    x = np.asarray(tm["rho"], float)
    f = np.asarray(tm["psi"], float)
    assert np.allclose(fyo.nonuniform_gradient(f, x), np.gradient(f, x),
                       rtol=1e-12, atol=0.0)


def test_shape_checks_refuse_rather_than_broadcast():
    tm = fyo.transport_metrics(GFILE, n_surfaces=41, edge=0.99)
    with pytest.raises(ValueError):
        fyo.enclosed_plasma_current(tm["rho"][:-1], tm["vprime"], tm["gm2"],
                                    tm["psi"])
    with pytest.raises(ValueError):
        fyo.enclosed_plasma_current([0.0, 1.0], [1.0, 1.0], [1.0, 1.0],
                                    [0.0, 1.0])
