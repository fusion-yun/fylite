"""kefit_compare's offline parts: the KEFIT slot map and the namelist writer (no server, no KEFIT run).

Needs the KEFIT reference bundle ($KEFIT_BUNDLE, default ../../../third_party/kefit_reference_bundle), libfylite.so next to
kinetic_recon.py, and — for the namelist test only — one stored slice result ($EKR_SLICE_RESULT: a `series --results-dir`
or `run` file) and the `pull` document of the same time ($EKR_SLICE_MEAS); experimental data, never in the repo.  Missing pieces skip, they do not fail.
Run:  python3 test/test_kefit_compare.py"""
import json
import os
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import kinetic_recon as K  # noqa: E402
import kefit_compare as KC  # noqa: E402

BUNDLE = Path(os.environ.get("KEFIT_BUNDLE", KC.DEFAULT_BUNDLE))
TABLES = BUNDLE / "green2022_pcs"
SLICE = os.environ.get("EKR_SLICE_RESULT")
MEAS = os.environ.get("EKR_SLICE_MEAS")                    #: the `pull` document of the same time


def _values(text: str, key: str) -> list:
    m = re.search(r"^" + key + r"\s*=\s*\n?(.*?)(?=^\S[^\n]*=|^/)", text, re.S | re.M | re.I)
    return re.findall(r"[-+]?\d+\.\d*(?:[eE][-+]?\d+)?", m.group(1)) if m else []


@unittest.skipUnless((TABLES / "dprobe.dat").exists() and K.DEFAULT_LIB.exists(), "KEFIT bundle or libfylite.so missing")
class SlotMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.card, _ = K.Lib(K.DEFAULT_LIB).device("east", 137985, "east")
        cls.smap = KC.slot_map(cls.card, TABLES)

    def test_counts(self):
        self.assertEqual(len(self.smap), 76)
        self.assertEqual(sum(1 for i in self.smap if i is not None), 74)

    def test_first_38_are_the_same_array(self):   #: green2022_pcs slots 0-37 = east_new slots 0-37, position and angle
        self.assertEqual(self.smap[:38], list(range(38)))

    def test_no_duplicate_name_slot(self):        #: slots 74-78 share names with 16-20 and read their node: never mapped
        self.assertFalse(set(self.smap) & set(range(74, 79)))


@unittest.skipUnless(SLICE and MEAS and Path(SLICE).exists() and Path(MEAS).exists() and (TABLES / "dprobe.dat").exists(),
                     "set $EKR_SLICE_RESULT and $EKR_SLICE_MEAS")
class Namelist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = json.loads(Path(SLICE).read_text(encoding="utf-8"))
        cls.card, _ = K.Lib(K.DEFAULT_LIB).device("east", int(cls.res["shot"]), "east")
        cls.smap = KC.slot_map(cls.card, TABLES)
        cls.loops = [K._name(x) for x in K._aos(cls.card["magnetics"]["flux_loop"])]
        cls.meas = json.loads(Path(MEAS).read_text(encoding="utf-8"))["measurements"]

    def text(self, mode="fixed"):
        return KC.namelist(int(self.res["shot"]), float(self.res["time_s"]), self.meas, self.res, self.smap, self.loops, (1, 2), mode)

    def test_counts_and_integers(self):
        t, rec = self.text()
        self.assertEqual(len(_values(t, "EXPMP2")), 76)
        self.assertEqual(len(_values(t, "coils")), 35)
        self.assertEqual(len(_values(t, "fwtmp2")), 76)
        self.assertRegex(t, r"KPPCUR  = \n1\n")        #: gfortran wants integers without ".0"
        self.assertRegex(t, r"KFFCUR  = \n2\n")
        self.assertEqual(rec["loops_used"], [c["name"] for c in self.res["tiers"]["M"]["channels"]["loops"]
                                             if c["used"] and re.fullmatch(r"FL\d+B", c["name"])])

    def test_every_key_written(self):             #: a stray comment once swallowed serror / error / errmin / kersil
        t, _ = self.text()
        for key in ("ISHOT", "ITIME", "BTOR", "PLASMA", "EXPMP2", "coils", "psibit", "fwtsi", "bitmpi", "fwtmp2", "FWTCUR",
                    "limitr", "xlim", "ylim", "BRSP", "bitfc", "FWTFC", "itek", "mxiter", "serror", "error", "errmin",
                    "kersil", "KFFCUR", "KPPCUR", "pcurbd", "fcurbd", "fitdelz"):
            self.assertRegex(t, r"(?m)^\s*" + key + r"\s*=", key)
        self.assertRegex(t, r"(?m)^\s*serror=0\.05\s*$")

    def test_slot_38_74_compensated(self):
        w = [float(v) for v in _values(self.text()[0], "fwtmp2")]
        self.assertTrue(all(v in (0.0, 1.0) for v in w[:37]))
        self.assertTrue(all(v in (0.0, 5.0) for v in w[37:74]))

    def test_fwtfc_modes(self):
        self.assertIn("FWTFC =12*100", self.text("fixed")[0])
        self.assertIn("FWTFC =12*0.3", self.text("gui")[0])
        self.assertIn("FWTFC =12*0 ", self.text("free")[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
