"""Read rules on the pull path (fydoc `bindings.mdsplus.read_rules`, 2026-09-25): no server, synthetic series.

The data layer (libsp `resolve_device`) resolves EAST for a shot and marks the covering `sign` / `drop` rules on the loops by name
(fyo `reading_sign_factor` · `excluded_channel`; `K.read_mark` also reads the runtime's `fylite:sign` · `fylite:drop`); the app
multiplies the reduced loop reading by the sign, records the applied rules in the measurement document (`read_rules`), and gives a dropped
loop zero weight (the kernel's case setup in `code/kinetic`; `inputs.excluded` with the rule id).  #164437 is covered (17 FL*B loops × −1, FL33B · FL35B
dropped); #159932 — the last shot of the old polarity — is not.

Needs libfylite_kernel.so + libsp.so next to kinetic_recon.py (or $EKR_LIB = the kernel library) and EAST device facts with the
FL*B rules (kinetic_recon.py's `facts/`, or $SP_FACTS_PATH).
Run:  python3 test/test_read_rules.py"""
import math
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import kinetic_recon as K  # noqa: E402

LIB = Path(os.environ.get("EKR_LIB") or K.DEFAULT_LIB)
SIGN, DROP = "magnetics-fl-b-polarity-159941", "magnetics-fl-b-unusable-159941"
PDROP, PGEO = "magnetics-probes-unusable-159941", "magnetics-probes-geometry-159941"
FIVE = {"HBPU3T", "HBPU9T", "HBPD1T", "HBPD1N", "HBPD9T"}
SEVENTEEN = {"FL1B", "FL3B", "FL6B", "FL8B", "FL9B", "FL12B", "FL13B", "FL15B", "FL17B", "FL18B",
             "FL21B", "FL23B", "FL24B", "FL27B", "FL28B", "FL30B", "FL32B"}


def _series(names):
    """Every loop reads 2π (1 Wb/rad after the reduction) at t > 0; FL35B is absent; everything else is small and present."""
    tb = [round(-7.0 + 1e-3 * k, 6) for k in range(10001)]
    loops = set(names["loops"])

    def get(leaf, where):
        key = leaf.lstrip("\\")
        if key == "FL35B":
            return None
        if key in loops:
            return [2.0 * math.pi if t > 0 else 0.0 for t in tb], tb
        if key.lower() == "pcrl01":
            return [4.0e5] * len(tb), tb
        return [1.0e-3] * len(tb), tb
    return get


@unittest.skipUnless(LIB.exists(), f"no {LIB}")
class ReadRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = K.Lib(LIB)
        cls.doc, cls.res = cls.lib.device("east", 164437, "east")
        cls.names = K.device_names(cls.doc, cls.res)
        if not {r.get("id") for r in cls.names["read_rules"]} >= {SIGN, DROP}:
            raise unittest.SkipTest("these EAST facts predate the FL*B read rules")

    def test_names_carry_sign_and_drop_by_name(self):
        n = self.names
        self.assertEqual({nm for nm, s in zip(n["loops"], n["loop_sign"]) if s < 0}, SEVENTEEN)
        self.assertEqual({nm for nm, d in zip(n["loops"], n["loop_drop"]) if d}, {"FL33B", "FL35B"})

    def test_the_old_polarity_shot_has_no_rule(self):
        n = K.device_names(*self.lib.device("east", 159932, "east"))
        self.assertTrue(all(s == 1.0 for s in n["loop_sign"]) and not any(n["loop_drop"]))
        self.assertEqual(n["read_rules"], [])

    def test_reduction_flips_and_records(self):
        n = dict(self.names, point_ne=[], point_fr=[])
        meas = K.reduce_series(_series(n), 164437, 2.0, n, source="synthetic")
        by = dict(zip(n["loops"], meas["coils"]))
        for nm in SEVENTEEN:
            self.assertAlmostEqual(by[nm], -1.0, places=9, msg=nm)
        self.assertAlmostEqual(by["FL1A"], 1.0, places=9)
        self.assertAlmostEqual(by["FL2B"], 1.0, places=9)
        self.assertEqual(by["FL35B"], 0.0)               #: absent and dropped: not a missing required node
        self.assertTrue({SIGN, DROP} <= {r["id"] for r in meas["read_rules"]})
        self.__class__.meas = meas

    def test_zz_case_gives_dropped_loops_no_weight(self):
        """The kernel's case setup (``code/kinetic``, 2026-09-26): dropped loops and probes are excluded with the rule id
        and carry no weight in tier M's channel table."""
        if not hasattr(self, "meas"):
            self.test_reduction_flips_and_records()
        meas = dict(self.meas, tf={"f_vac_Tm": 4.46})
        res = K.reconstruct(meas, None, lib=self.lib, tiers="M", max_rounds=1, physics_check=False, jobs=4)
        exc = res["inputs"]["excluded"]
        why = {e["name"]: e["why"] for e in exc if e["kind"] == "loop"}
        self.assertEqual(why, {"FL33B": f"read rule {DROP}", "FL35B": f"read rule {DROP}"})
        ch = res["tiers"]["M"].get("channels") or {}
        for c in ch.get("loops") or []:
            if c["name"] in ("FL33B", "FL35B"):
                self.assertFalse(c["used"], c["name"])
        if PDROP in {r["id"] for r in meas["read_rules"]}:
            pwhy = {e["name"]: e["why"] for e in exc if e["kind"] == "probe" and e["why"].startswith("read rule")}
            self.assertEqual(pwhy, {nm: f"read rule {PDROP}" for nm in FIVE})
            for c in ch.get("probes") or []:
                if c["name"] in FIVE:
                    self.assertFalse(c["used"], c["name"])

    def test_zz_geometry_reaches_the_coil_share(self):
        """The coil-share door reads the resolved document: only the two replaced probes' rows move."""
        import copy
        if PGEO not in {r["id"] for r in self.names["read_rules"]}:
            self.skipTest("these EAST facts predate the probe geometry rule")
        orig = copy.deepcopy(self.doc)
        for p in orig["magnetics"]["b_field_pol_probe"]:
            was = next((p.pop(k) for k in K.READ_MARKS["geometry_was"] if k in p), None)
            if was:
                p.update(was)

        def share(doc):
            _, s, _ = self.lib.door("code/coilshare", {"nu_loops": 8, "nu_probes": 3, "grid_psi": 1, "nu_grid": 4},
                                    {"device": doc, "discharge": {"fylite:channel_aturns": [1.0e5] * 12}})
            return s["probe_coil"]
        a, b = share(self.doc), share(orig)
        names = [p["name"] for p in self.doc["magnetics"]["b_field_pol_probe"]]
        self.assertEqual({names[i] for i in range(len(names)) if a[i] != b[i]}, {"HBPU5T", "HBPU7T"})


if __name__ == "__main__":
    unittest.main()
