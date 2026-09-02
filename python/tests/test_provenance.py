"""K-17 — run manifest, four-state acceptance, versioned non-overwrite delivery."""
import json

from fylite import engine as pv


def test_digest_is_order_stable():
    a = {"x": [1, 2, 3], "y": {"b": 2, "a": 1}}
    b = {"y": {"a": 1, "b": 2}, "x": [1, 2, 3]}
    assert pv.digest(a) == pv.digest(b)
    assert pv.digest(a) != pv.digest({"x": [1, 2, 4]})


def test_sha256_file_roundtrip(tmp_path):
    p = tmp_path / "g.txt"
    p.write_bytes(b"hello")
    assert pv.sha256_file(p) == pv.sha256_file(p)
    assert pv.sha256_file(tmp_path / "missing") is None


def test_acceptance_four_states():
    assert pv.acceptance({"terror": 0.01, "converged": True})["state"] == pv.PASS
    assert pv.acceptance({"terror": 0.05, "converged": True})["state"] == pv.CONDITIONAL
    assert pv.acceptance({"terror": 0.5, "converged": True})["state"] == pv.FAIL
    # converged False fails even with a good terror
    assert pv.acceptance({"terror": 0.01, "converged": False})["state"] == pv.FAIL
    # no metrics at all -> unevaluated
    assert pv.acceptance({})["state"] == pv.UNEVALUATED


def test_acceptance_overrides_thresholds():
    v = pv.acceptance({"terror": 0.05}, {"terror": {"pass": 0.1, "warn": 0.2},
                                         "require_converged": False})
    assert v["state"] == pv.PASS


def test_reserve_dir_versions_non_overwriting(tmp_path):
    base = tmp_path / "run"
    d1 = pv.reserve_dir(base)
    (d1 / "g.txt").write_text("first")
    d2 = pv.reserve_dir(base)                     # base now non-empty -> -v2
    assert d1 == base and d2 == base.with_name("run-v2")
    (d2 / "g.txt").write_text("second")
    d3 = pv.reserve_dir(base)
    assert d3 == base.with_name("run-v3")
    # overwrite=True reuses the exact base
    assert pv.reserve_dir(base, overwrite=True) == base


def test_deliver_writes_manifest_and_copies(tmp_path):
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "g137985.04000").write_text("PSI GRID ...")
    (wd / "a137985.04000").write_text("betap li ...")
    result = {"gfile": str(wd / "g137985.04000"), "workdir": str(wd),
              "terror": 0.02, "converged": True}
    dec = [pv.record_decision("YuZhi", "ban-channel", "sign-flip probe 12",
                              channel=12)]
    out = pv.deliver(result, tmp_path / "delivery",
                     config={"shot": 137985, "point": True},
                     inputs={"measurements": {"ip": 4e5}}, decisions=dec)
    dest = out["dir"]
    man = json.loads((tmp_path / "delivery" / "manifest.json").read_text())
    assert man["code"]["rev"]
    assert man["environment"]["python"]
    assert "measurements" in man["inputs"]
    names = {a["name"] for a in man["artifacts"]}
    assert "g137985.04000" in names and "a137985.04000" in names
    assert all(a["sha256"] for a in man["artifacts"])
    assert man["decisions"][0]["actor"] == "YuZhi"
    assert out["acceptance"]["state"] == pv.PASS
    assert (tmp_path / "delivery" / "acceptance.json").is_file()
    assert dest == str(tmp_path / "delivery")


def test_deliver_twice_does_not_clobber(tmp_path):
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "g1.000").write_text("g")
    result = {"gfile": str(wd / "g1.000"), "workdir": str(wd)}
    a = pv.deliver(result, tmp_path / "d")
    b = pv.deliver(result, tmp_path / "d")
    assert a["dir"] != b["dir"]                   # second delivery -> d-v2
    assert (tmp_path / "d" / "manifest.json").is_file()
    assert (tmp_path / "d-v2" / "manifest.json").is_file()
