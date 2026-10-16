"""``kinetic_config.validation`` reports the sawtooth q=1 check of the main tier, without the library or a server.

The analysis itself (crash times from SXR, the ECE inversion radius, the per-tier q=1 verdicts, tier Q's readings) is the
kernel's now (``code/kinetic``, ``src/door/case/kinetic/q.rs``) and is tested there; the ``sawtooth`` block
below is in the shape the kernel's ``attach`` writes.

Run:  python3 test/test_sawtooth.py"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import kinetic_config as C  # noqa: E402


def result():
    return {"tiers": {"M": {"status": "ok"}, "D": {"status": "ok"}, "P": {"status": "skipped"}},
            "sawtooth": {"status": "ok", "tol_m": 0.025, "crashes": {"n": 24},
                         "inversion": {"r_inv": 1.9951, "r_inv_stat": 0.015, "r_inv_sys": 0.02, "z": 0.0},
                         "tiers": {"M": {"verdict": "fail", "why": "有锯齿，这一档却没有 q=1 面", "q1_psin": []},
                                   "D": {"verdict": "pass", "why": "R_q=1 − R_inv = +4 mm", "r_q1_lfs": 1.9991,
                                         "dr_m": 0.004}}}}


class Validation(unittest.TestCase):
    def test_validation_reports_main_tier(self):
        chk = [c for c in C.validation(result(), ["sawtooth_q1"])["checks"] if c["id"] == "sawtooth_q1"][0]
        self.assertEqual(chk["tier"], "D")
        self.assertEqual(chk["by_tier"], {"M": "fail", "D": "pass"})
        self.assertEqual(chk["verdict"], "pass")
        self.assertEqual((chk["r_inv"], chk["dr_m"], chk["tol_m"], chk["n_crashes"]), (1.9951, 0.004, 0.025, 24))

    def test_without_a_sawtooth_block_it_is_unevaluated(self):
        res = result()
        del res["sawtooth"]
        chk = C.validation(res, ["sawtooth_q1"])["checks"][0]
        self.assertEqual(chk["verdict"], "unevaluated")


if __name__ == "__main__":
    unittest.main()
