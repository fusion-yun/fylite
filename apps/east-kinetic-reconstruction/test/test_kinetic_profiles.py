"""kinetic_profiles.py（剖面文件的装配）与 kinetic_recon.load_profiles（run --profiles 的读法），不载库。

剖面怎样变成压强行在内核（``src/door/case/kinetic/prof.rs``），测试在那边。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kinetic_profiles as KP  # noqa: E402
import kinetic_recon as K  # noqa: E402


def write(p: Path, text: str) -> str:
    p.write_text(text, encoding="utf-8")
    return str(p)


@pytest.fixture
def csvs(tmp_path):
    ts = write(tmp_path / "ts.csv", "t_s,Z_mm,Te_eV,err_upper_eV\n6.0583,100,1500,50\n6.0583,200,1200,40\n7.0583,100,900,30\n")
    refl = write(tmp_path / "refl.csv", "R_m,ne_1e19m-3\n2.2,6.0\n2.3,3.0\n")
    cx = write(tmp_path / "cx.csv", "rho_norm,Ti_keV,Ti_err95_keV\n0.1,1.3,0.196\n0.5,0.9,0.098\n")
    an = write(tmp_path / "an.csv", "R_m,Z_m,rho_fig\n1.9,0.1,0.15\n2.2,0.03,0.6\n")
    return tmp_path, ts, refl, cx, an


def test_a_profiles_file_is_built_in_si_from_csv_columns(csvs):
    d, ts, refl, cx, an = csvs
    f = str(d / "prof.json")
    KP.main(["new", f, "--source", "test", "--shot", "1", "--time", "6.3"])
    KP.main(["add", f, "--species", "te", "--csv", ts, "--where", "t_s=6.0583", "--coord", "rz", "--r", "=1.9",
             "--z", "Z_mm", "--z-scale", "1e-3", "--value", "Te_eV", "--sigma", "err_upper_eV", "--time", "6.0583"])
    KP.main(["add", f, "--species", "ne", "--csv", refl, "--coord", "rz", "--r", "R_m", "--z", "=0.03",
             "--value", "ne_1e19m-3", "--scale", "1e19", "--chords"])
    KP.main(["add", f, "--species", "ti", "--csv", cx, "--coord", "rho_anchored", "--rho", "rho_norm",
             "--value", "Ti_keV", "--scale", "1e3", "--sigma", "Ti_err95_keV", "--sigma-scale", "0.5102"])
    KP.main(["anchors", f, "--csv", an, "--r", "R_m", "--z", "Z_m", "--rho", "rho_fig"])
    doc = json.loads(Path(f).read_text(encoding="utf-8"))
    assert doc["@type"] == KP.TYPE
    sp = doc["profiles"]["species"]
    assert sp["te"]["value"] == [1500.0, 1200.0] and sp["te"]["z"] == pytest.approx([0.1, 0.2]) and sp["te"]["r"] == [1.9, 1.9]
    assert sp["ne"]["value"] == pytest.approx([6e19, 3e19]) and sp["ne"]["sigma_rel"] == 0.1 and sp["ne"]["chords"] is True
    assert sp["ti"]["sigma"] == pytest.approx([100.0, 50.0], rel=1e-3) and sp["ti"]["coord"] == "rho_anchored"
    assert doc["profiles"]["anchors"]["rho"] == [0.15, 0.6]
    #: run --profiles takes the whole document or the bare block; the measurement document's own block otherwise
    assert K.load_profiles(f)["species"]["te"]["value"] == [1500.0, 1200.0]
    bare = write(d / "bare.json", json.dumps(doc["profiles"]))
    assert K.load_profiles(bare)["species"]["ne"]["chords"] is True
    meas = write(d / "meas.json", json.dumps({"measurements": {}, "profiles": doc["profiles"]}))
    assert K.load_profiles(None, meas)["source"] == "test"
    assert K.load_profiles(None, write(d / "m2.json", json.dumps({"measurements": {}}))) is None


def test_bad_uses_are_refused(csvs):
    d, ts, refl, _, _ = csvs
    f = str(d / "prof.json")
    KP.main(["new", f, "--source", "test"])
    with pytest.raises(SystemExit):
        KP.main(["add", f, "--species", "te", "--csv", ts, "--coord", "rz", "--r", "=1.9", "--z", "Z_mm",
                 "--value", "Te_eV", "--chords"])
    with pytest.raises(SystemExit):
        KP.main(["add", f, "--species", "ne", "--csv", refl, "--coord", "rz", "--r", "R_m", "--value", "ne_1e19m-3"])
    with pytest.raises(SystemExit):
        KP.main(["add", f, "--species", "te", "--csv", ts, "--where", "t_s=9.9", "--coord", "rz", "--r", "=1.9",
                 "--z", "Z_mm", "--value", "Te_eV"])
    with pytest.raises(SystemExit):
        K.load_profiles(write(d / "no.json", json.dumps({"x": 1})))
