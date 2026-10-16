"""``kinetic_config.validation`` on an annotated ladder record, without the library or a server: the readings pass through
(verdict ``reading``) and the main tier's held-out set is reported.

The annotation itself (blocks along ``on``, held-out sets, χ²_mag and its ratio to tier M) is the kernel's now
(``code/kinetic``, ``src/door/case/kinetic/ladder.rs``) and is tested there; the record below is in the shape it
writes.

Run:  python3 test/test_ladder_annotate.py"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import kinetic_config as C  # noqa: E402


def result():
    held = [{"diag": d, "why": "…"} for d in ("point", "ece_sxr", "mirnov", "mse")]
    same = {"w_mhd_J": 2.5e5, "betap": 0.7, "li1": 1.0}
    tier = lambda ratio, **kw: dict({"status": "ok", "facts": {"q0": 1.0, "compat_mag_vs_M": ratio},  # noqa: E731
                                     "physics_check": {"passed": True, "same_ruler": same}}, **kw)
    return {"inputs": {"w_dia_J": 2.4e5, "has_point": True, "has_thomson": True},
            "tiers": {"M": tier(1.0), "P": tier(1.333, on="M", held_out=held),
                      "S": {"status": "skipped", "why": "no MSE rows"}}}


class Validation(unittest.TestCase):
    def test_validation_passes_readings_through(self):
        v = C.validation(result(), ["physics"])
        comp = [c for c in v["checks"] if c["id"] == "compat_mag"]
        self.assertEqual(len(comp), 1)
        self.assertEqual(comp[0]["verdict"], "reading")
        self.assertEqual(comp[0]["values"], {"M": 1.0, "P": 1.333})
        self.assertEqual(v["held_out"]["tier"], "P")
        self.assertIn("point", {h["diag"] for h in v["held_out"]["items"]})


if __name__ == "__main__":
    unittest.main()
