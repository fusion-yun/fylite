"""xpoint_balance on an analytic field with two known saddles (stdlib only, no library needed).

    psi(R, Z) = (R - Rx)^2 - k (Z^2 - Zx^2)^2 + eps Z

At eps = 0 the saddles sit exactly at (Rx, +-Zx) with psi = 0; eps tilts them: psi(Rx, +-Zx) ~ +-eps Zx (to first order),
so the upper-minus-lower psi_N gap is ~ 2 eps Zx / (psi_bnd - psi_axis).  Run:  python3 test/test_xpoint.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kinetic_recon as K  # noqa: E402

RX, ZX, KK = 1.60, 0.76, 4.0


def field(eps: float, n: int = 65):
    gr = [1.2 + 1.6 * i / (n - 1) for i in range(n)]
    gz = [-1.4 + 2.8 * j / (n - 1) for j in range(n)]
    psi = [[(r - RX) ** 2 - KK * (z * z - ZX * ZX) ** 2 + eps * z for z in gz] for r in gr]
    return {"grid_r": gr, "grid_z": gz, "psi": psi}


def exact(eps: float, side: float) -> tuple[float, float]:
    """saddle of the analytic field on one side: solve dpsi/dZ = -4k Z (Z^2 - Zx^2) + eps = 0 near side*Zx (Newton)."""
    z = side * ZX
    for _ in range(50):
        f = -4 * KK * z * (z * z - ZX * ZX) + eps
        df = -4 * KK * (3 * z * z - ZX * ZX)
        z -= f / df
    return z, -KK * (z * z - ZX * ZX) ** 2 + eps * z


class XpointBalance(unittest.TestCase):
    AXIS = -1.0          #: psi_axis below both saddles; psi_bnd set on the saddle that should be "on the separatrix"

    def check(self, eps, psi_bnd, want_cfg):
        x = K.xpoint_balance(field(eps), self.AXIS, psi_bnd)
        for side, key in ((1.0, "upper"), (-1.0, "lower")):
            z, v = exact(eps, side)
            self.assertAlmostEqual(x[key]["r"], RX, delta=2e-3, msg=key)
            self.assertAlmostEqual(x[key]["z"], z, delta=3e-3, msg=key)
            self.assertAlmostEqual(x[key]["psin"], (v - self.AXIS) / (psi_bnd - self.AXIS), delta=2e-3, msg=key)
            self.assertTrue(x[key]["saddle"])
        self.assertEqual(x["config"], want_cfg)
        return x

    def test_double_null(self):
        _, v = exact(0.0, 1.0)
        self.check(0.0, v, "DN")

    def test_lower_single_null(self):            #: eps > 0 lifts the upper saddle: the lower one is on the separatrix
        _, v = exact(0.05, -1.0)
        x = self.check(0.05, v, "LSN")
        self.assertGreater(x["dpsin"], K.XPT_DN_TOL)

    def test_upper_single_null(self):
        _, v = exact(-0.05, 1.0)
        x = self.check(-0.05, v, "USN")
        self.assertLess(x["dpsin"], -K.XPT_DN_TOL)

    def test_limited(self):                      #: boundary flux well inside both saddles: neither X point bounds the plasma
        _, v = exact(0.0, 1.0)
        self.check(0.0, v - 0.2 * (v - self.AXIS), "LIM")

    def test_coarse_grid(self):                  #: 33^2 (the coarse scan grid) still locates both saddles
        x = K.xpoint_balance(field(0.0, 33), self.AXIS, exact(0.0, 1.0)[1])
        self.assertAlmostEqual(x["upper"]["z"], ZX, delta=1e-2)
        self.assertAlmostEqual(x["lower"]["z"], -ZX, delta=1e-2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
