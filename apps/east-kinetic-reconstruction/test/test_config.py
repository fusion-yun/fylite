"""Config file v2 and the batch command line (``kinetic_config.py``), without the library or a server.

* merge order and key origins: default → file → per-slice override → ``--set`` → shorthand flag; derived keys (a basis preset
  sets the orders) are marked ``derived:``.
* unknown keys are refused by name (file, ``--set``, per-slice override); impossible combinations are refused before running
  (exit code 2): J without P, fixed-p without a given p′, ``ladder.x = false`` with presets, a changed ``data.window_ms`` …
* the slice grammar: ``6.72`` · ``6.3,6.72`` · ``t0:t1:dt`` · ``at-thomson`` / ``at-efit`` (+ window).
* v1 input files (kinetic_input.py) load: ``pedestal`` · ``q0`` move under ``presets``; tier-X details land in ``tier_x``.
* the plan: tier S and the q=1 preset are *not executed* with a reason; J / q₀ preset go to tier X; nothing silently dropped.
* ``run <config> --dry-run`` / ``--print-config`` through ``kinetic_recon.main`` need no library; a measurement doc still takes
  the old ``run`` path.
* ``validation`` on a synthetic result; the page's ``cfgDefault()`` equals ``DEFAULTS`` (needs node; skipped without it).

Run:  python3 test/test_config.py"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import kinetic_config as KC  # noqa: E402
import kinetic_input as KI  # noqa: E402
import kinetic_recon as K  # noqa: E402

PULL = {"@type": "fylite:KineticReconMeasurements", "shot": 1, "time_s": 2.0,
        "measurements": {"shot": 1, "time_s": 2.0, "plasma": 5e5}, "thomson": None}


def cfg_file(d: dict, tmp: Path, name="k.json") -> Path:
    (tmp / "pull.json").write_text(json.dumps(PULL))
    doc = {"@type": KC.TYPE, "version": 2, "data": {"file": "pull.json"}}
    for k, v in d.items():
        KC.setp(doc, k, v)
    p = tmp / name
    p.write_text(json.dumps(doc))
    return p


class Merge(unittest.TestCase):
    def test_origins(self):
        cfg, org = KC.resolve({"data": {"shot": 7}, "basis": {"preset": "kin-3-2"}},
                              ["pressure.psin_max=0.95", "presets.core.q0.mode=prior"], {"run.jobs": 3})
        self.assertEqual(org["data.shot"], "file")
        self.assertEqual(org["pressure.psin_max"], "set")
        self.assertEqual(cfg["pressure.psin_max".split(".")[0]]["psin_max"], 0.95)
        self.assertEqual(org["run.jobs"], "flag")
        self.assertEqual(org["point.dead_sigma"], "default")
        self.assertEqual((cfg["basis"]["npp"], cfg["basis"]["nff"]), (3, 2))
        self.assertTrue(org["basis.npp"].startswith("derived:"))

    def test_set_values(self):
        self.assertEqual(KC.parse_value("0.5"), 0.5)
        self.assertIs(KC.parse_value("true"), True)
        self.assertIsNone(KC.parse_value("null"))
        self.assertEqual(KC.parse_value("[1,2]"), [1, 2])
        self.assertEqual(KC.parse_value("kin-3-2"), "kin-3-2")
        cfg, _ = KC.resolve({"data": {"shot": 1}}, ["magnetics.loops.FL1B=0.5"])
        self.assertEqual(cfg["magnetics"]["loops"], {"FL1B": 0.5})

    def test_unknown_keys(self):
        for doc, sets in (({"data": {"shot": 1}, "bogus": 1}, []), ({"data": {"shot": 1, "shto": 2}}, []),
                          ({"data": {"shot": 1}}, ["presets.core.q9=1"]), ({"data": {"shot": 1}}, ["presets=1"])):
            with self.assertRaises(KC.ConfigError) as e:
                KC.resolve(doc, sets)
            self.assertEqual(e.exception.code, 2)

    def test_rejections(self):
        bad = [{"ladder": {"tiers": ["M", "J"]}},                                   # J without P
               {"basis": {"preset": "fixed-p"}},                                    # no given p′
               {"ladder": {"x": False}, "presets": {"pedestal": {"on": True}}},     # preset needs X
               {"data": {"window_ms": 20}},
               {"ladder": {"tiers": ["M", "Z"]}},
               {"currents": {"bootstrap": {"formula": "sauter"}}},
               {"presets": {"core": {"q0": {"mode": "prior", "sigma": 0}}}}]
        for d in bad:
            d = dict(d, data=dict(d.get("data") or {}, shot=1))
            with self.assertRaises(KC.ConfigError, msg=str(d)):
                KC.resolve(d)
        with self.assertRaises(KC.ConfigError):
            KC.resolve({})                                                          # no data at all
        cfg, _ = KC.resolve({"data": {"shot": 1}, "ladder": {"tiers": ["J", "P", "k"]}})
        self.assertEqual(cfg["ladder"]["tiers"], ["M", "K", "P", "J"])              # fixed order, M always


class Slices(unittest.TestCase):
    def test_grammar(self):
        self.assertEqual(KC.parse_slices("6.72")["times_s"], [6.72])
        self.assertEqual(KC.parse_slices("6.3,6.72")["times_s"], [6.3, 6.72])
        r = KC.parse_slices("3:4:0.5")
        self.assertEqual(KC.range_times(r["range"]), [3.0, 3.5, 4.0])
        a = KC.parse_slices("at-thomson", "3:8")
        self.assertEqual((a["align"], a["window"]), ("thomson", [3.0, 8.0]))
        for s, w in (("at-efit", None), ("3:2:0.1", None), ("x", None), ("at-thomson", "8:3")):
            with self.assertRaises(KC.ConfigError):
                KC.parse_slices(s, w)

    def test_override(self):
        cfg, org = KC.resolve({"data": {"shot": 1}, "slices": {"times_s": [6.3, 6.72],
                                                               "overrides": {"6720": {"presets.core.q0.mode": "prior"}}}})
        s1, o1, d1 = KC.slice_config(cfg, org, 6.72)
        s0, _, d0 = KC.slice_config(cfg, org, 6.3)
        self.assertEqual(s1["presets"]["core"]["q0"]["mode"], "prior")
        self.assertEqual(o1["presets.core.q0.mode"], "override:6.72")
        self.assertEqual(d0, {})
        self.assertNotEqual(KC.fingerprint(s0), KC.fingerprint(s1))
        s0b = dict(s0, run=dict(s0["run"], jobs=99))
        self.assertEqual(KC.fingerprint(s0), KC.fingerprint(s0b))                  # jobs do not change the answer
        cfg["slices"]["overrides"] = {"6.72": {"nope.x": 1}}
        with self.assertRaises(KC.ConfigError):
            KC.slice_config(cfg, org, 6.72)


class V1(unittest.TestCase):
    def test_migrate(self):
        v1 = json.loads(json.dumps(KI.DEFAULTS))
        v1["data"] = {"file": "pull.json", "time_s": 4.041, "thomson_file": None}
        v1["pedestal"] = {"on": True, "x": 0.93, "w": 0.04, "ffprime": True}
        v1["q0"] = {"on": True, "target": 0.95, "sigma": 0.03}
        v1["currents"]["bootstrap"]["on"] = True
        cfg, org = KC.resolve(v1)
        self.assertEqual(cfg["presets"]["pedestal"], {"on": True, "x": 0.93, "w": 0.04, "ffprime": True, "p_ped": None, "te_sep_eV": None})
        self.assertEqual(cfg["presets"]["core"]["q0"]["mode"], "prior")
        self.assertEqual(cfg["slices"]["times_s"], [4.041])
        self.assertIs(cfg["ladder"]["x"], True)
        self.assertIn("J", cfg["ladder"]["tiers"])
        self.assertIn("basis", cfg["tier_x"])
        x = KC.x_input(cfg)                                                          # round-trips through KI.normalize
        self.assertTrue(x["pedestal"]["on"] and x["q0"]["on"] and x["currents"]["bootstrap"]["on"])


class Plan(unittest.TestCase):
    def test_not_executed(self):
        cfg, _ = KC.resolve({"data": {"shot": 1}, "ladder": {"tiers": ["M", "K", "P", "S", "J"]},
                             "presets": {"core": {"q0": {"mode": "hard"}, "q1": {"on": True}}},
                             "mse": {"channels": {"MSE1": 1}}})
        pl = KC.plan(cfg)
        keys = {x["key"] for x in pl["not_executed"]}
        self.assertTrue({"ladder.tiers.S", "presets.core.q1.on", "presets.core.q0.mode", "mse.channels"} <= keys)
        self.assertTrue(pl["x"])
        self.assertIn("J", pl["executed"])
        self.assertEqual(pl["run_options"]["tiers"], "MKP")
        for k in pl["run_options"]:                                                  # every key is a real run option
            self.assertIn(k, vars(K.run_options()))

    def test_basis_floor_warning(self):
        cfg, _ = KC.resolve({"data": {"shot": 1}, "ladder": {"tiers": ["M"]}, "basis": {"preset": "kin-3-2"}})
        self.assertTrue(KC.plan(cfg)["warnings"])


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = K.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_dry_run(self):
        p = cfg_file({"ladder.tiers": ["M", "K", "P", "S"]}, self.tmp)
        rc, out, _ = self.main(["run", str(p), "--dry-run", "-o", str(self.tmp / "out")])
        self.assertEqual(rc, 0)
        self.assertIn("2.0000 s", out)
        self.assertIn("ladder.tiers.S", out)
        self.assertFalse((self.tmp / "out").exists())                               # dry-run writes nothing

    def test_print_config(self):
        p = cfg_file({}, self.tmp)
        rc, out, _ = self.main(["run", str(p), "--print-config", "--set", "pressure.psin_max=0.9", "--tiers", "M,K"])
        self.assertEqual(rc, 0)
        d = json.loads(out)
        self.assertEqual(d["config"]["pressure"]["psin_max"], 0.9)
        self.assertEqual(d["origin"]["ladder.tiers"], "flag")

    def test_rejected_exit_2(self):
        p = cfg_file({}, self.tmp)
        self.assertEqual(self.main(["run", str(p), "--dry-run", "--set", "no.such=1"])[0], 2)
        self.assertEqual(self.main(["run", str(p), "--dry-run", "--slices", "9.9"])[0], 2)   # not in data.file

    def test_old_run_path_untouched(self):
        (self.tmp / "pull.json").write_text(json.dumps(PULL))
        self.assertIsNone(KC.route(["run", str(self.tmp / "pull.json"), "-o", "x.json"]))
        self.assertIsNone(KC.route(["--lib", "x.so", "compare", "r.json", "-o", "c.json"]))

    def test_init_without_lib(self):
        out = self.tmp / "k.json"
        rc, _, _ = self.main(["--lib", str(self.tmp / "none.so"), "init", "--shot", "5", "--time", "1.5", "--no-channels", "-o", str(out)])
        self.assertEqual(rc, 0)
        d = json.loads(out.read_text())
        self.assertEqual((d["data"]["shot"], d["slices"]["times_s"]), (5, [1.5]))
        self.assertEqual(set(d), set(KC.DEFAULTS))


class Validation(unittest.TestCase):
    def test_verdicts(self):
        sr = lambda bp, li: {"physics_check": {"passed": True, "failed": [], "same_ruler": {"betap": bp, "li1": li, "w_mhd_J": 2.5e5}}}
        res = {"shot": 1, "time_s": 2.0, "inputs": {"w_dia_J": 2.4e5},
               "tiers": {"M": dict(status="ok", **sr(0.7, 1.0)), "K": dict(status="ok", **sr(0.68, 1.04)),
                         "D": dict(status="ok", on="K", **sr(0.66, 1.18))}}
        v = {c["id"]: c for c in KC.validation(res, KC.CHECKS)["checks"]}
        self.assertEqual(v["physics"]["verdict"], "pass")
        self.assertEqual(v["cross_tier"]["verdict"], "reading")
        self.assertAlmostEqual(v["cross_tier"]["spread"], 0.05, places=6)                # 1.20 · 1.20 · 1.25
        self.assertEqual(v["wdia"]["verdict"], "inconclusive")                     # D used W_dia
        self.assertEqual(v["sawtooth_q1"]["verdict"], "unevaluated")


class PageDefaults(unittest.TestCase):
    def test_page_matches(self):
        node = shutil.which("node") or os.path.expanduser("~/.local/opt/node/bin/node")
        if not Path(node).exists():
            self.skipTest("no node")
        html = (HERE / "kinetic_ladder.html").read_text(encoding="utf-8")
        i = html.index("function cfgDefault()")
        j = html.index("\n}\n", i) + 3
        js = html[i:j] + "\nprocess.stdout.write(JSON.stringify(cfgDefault()));"
        out = subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out), KC.DEFAULTS)


if __name__ == "__main__":
    unittest.main()
