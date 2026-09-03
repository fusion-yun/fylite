"""闸子：数据层的文档面（`fylite.io.fydoc` ↔ `rust/fylite_engine`）。

★★三条判据，各守一条契约：

1. **路径表一份**：`rust/fylite_engine/src/eqdsk_fyo.rs` 里抄的 `EQUILIBRIUM_SLOTS`
   与内核生成的 `_fyo_interface.TABLES["EQUILIBRIUM"]` 逐行相同——两份拼写只有在
   被对拍时才算一份契约（`abox-mds-bind.py` 抬头那条教训）。这一条**不需要**库
   构建好，读源码就判。
2. **fyo HDF5 两侧互读**：Python `fyo.write` 写的 `.h5` 数据层读得回、逐数相同；
   数据层写的 `.h5` `fyo.read` 读得回。
3. **g-file 经 IMAS 布局走一圈数不变**：g-file → netCDF（IMAS 布局）→ 读回 → g-file，
   `psirz` 逐位相同，限制器经 `wall` IDS 回来。
"""
from __future__ import annotations

import pathlib
import re

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUNDLED = ROOT / "rust" / "fylite_engine" / "testdata" / "g_synthetic.geqdsk"
RS = ROOT / "rust" / "fylite_engine" / "src" / "eqdsk_fyo.rs"


def test_the_equilibrium_slot_table_is_the_kernels():
    from fylite import _fyo_interface as iface
    src = RS.read_text()
    m = re.search(r"pub const EQUILIBRIUM_SLOTS: \[\(&str, &str\); \d+\] = \[(.*?)\];", src, re.S)
    assert m, "EQUILIBRIUM_SLOTS not found in eqdsk_fyo.rs"
    rows = re.findall(r'\("([a-z_0-9]+)",\s*"([^"]+)"\)', m.group(1))
    rust = {k: p for k, p in rows}
    kernel = {k: v["path"] for k, v in iface.TABLES["EQUILIBRIUM"]["slots"].items()}
    assert rust == kernel


@pytest.fixture(scope="module")
def fydoc():
    from fylite import kernel
    if kernel.load_data() is None:
        pytest.skip("libfylite_engine.so not built (rust/build.sh)")
    from fylite.io import fydoc as m
    return m


def test_detect_reads_the_content_not_the_name(fydoc, tmp_path):
    p = tmp_path / "anything.txt"
    p.write_text(BUNDLED.read_text())
    assert fydoc.detect(p) == ("geqdsk", "fyo")
    j = tmp_path / "doc.bin"
    j.write_text('{"@type": "fyo:equilibrium"}')
    assert fydoc.detect(j) == ("json", "fyo")


def test_fyo_hdf5_written_by_python_is_read_by_the_data_layer(fydoc, tmp_path):
    from fylite import fyo
    h5py = pytest.importorskip("h5py")
    _ = h5py
    doc = fyo.equilibrium(fyo.geqdsk.read_geqdsk(BUNDLED), check_convention=False)
    p = tmp_path / "py.h5"
    fyo.write(doc, p)
    assert fydoc.detect(p) == ("hdf5", "fyo")
    b = fydoc.read(p)
    assert b.keys == ["equilibrium"]
    psi = b.array("equilibrium/time_slice/0/profiles_2d/0/psi")
    ref = np.asarray(fyo.get(doc, "EQUILIBRIUM", "psi_2d"), float)
    assert psi.shape == ref.shape
    assert np.array_equal(psi, ref)
    assert b.get("equilibrium/@type") == "fyo:equilibrium"
    assert b.array("equilibrium/fylite:limiter/r").shape == (len(doc["fylite:limiter"]["r"]),)
    #: and back: the data layer's HDF5 is fyo.read's
    q = tmp_path / "rs.h5"
    b.write(q)
    again = fyo.read(q)
    assert np.array_equal(np.asarray(fyo.get(again, "EQUILIBRIUM", "psi_2d"), float), ref)
    assert again["@type"] == "fyo:equilibrium"
    assert isinstance(again["time_slice"], list)


def test_a_gfile_survives_the_imas_layout(fydoc, tmp_path):
    from fylite.io import geqdsk
    b = fydoc.read(BUNDLED)
    nc = tmp_path / "eq.nc"
    note = b.write(nc, layout="imas")
    assert "synthesized wall" in note
    assert fydoc.detect(nc) == ("netcdf", "imas")
    back = fydoc.read(nc)
    assert sorted(back.keys) == ["equilibrium", "wall"]
    g = geqdsk.read_geqdsk(BUNDLED)
    psi = back.array("equilibrium/time_slice/0/profiles_2d/0/psi")
    assert psi.shape == (g["nw"], g["nh"])
    assert np.array_equal(psi.T.ravel(), np.asarray(g["psirz"], float))
    lim = back.array("wall/description_2d/0/limiter/unit/0/outline/r")
    assert np.array_equal(lim, np.asarray(g["rlim"], float))
    #: IMAS HDF5 is a directory
    d = tmp_path / "entry"
    b.write(d, layout="imas")
    assert (d / "master.h5").is_file() and (d / "equilibrium.h5").is_file()
    assert fydoc.detect(d) == ("imas-hdf5", "imas")
    back2 = fydoc.read(d)
    assert np.array_equal(back2.array("equilibrium/time_slice/0/profiles_1d/f"), np.asarray(g["fpol"], float))


def test_merge_and_set(fydoc, tmp_path):
    a = fydoc.read(BUNDLED)
    b = fydoc.Bundle.from_dict({"@context": {}, "@type": "fyo:equilibrium",
                                "vacuum_toroidal_field": {"r0": 9.0}, "fylite:x": [1.0, 2.0]})
    a.merge(b)
    assert a.get("equilibrium/vacuum_toroidal_field/r0") == 9.0
    assert a.array("equilibrium/fylite:x").tolist() == [1.0, 2.0]
    a.set("equilibrium/time_slice/0/global_quantities/ip", 123.0)
    a.set("wall/description_2d/0/limiter/unit/0/outline/r", np.array([1.0, 2.0, 3.0]))
    assert a.get("equilibrium/time_slice/0/global_quantities/ip") == 123.0
    assert sorted(a.keys) == ["equilibrium", "wall"]
    out = tmp_path / "m.jsonld"
    a.write(out)
    d = fydoc.read(out).to_dict()
    assert set(d) == {"equilibrium", "wall"}


def test_assemble_reads_yaml_sources_keys_the_merge_by_name_and_selects(fydoc, tmp_path):
    (tmp_path / "pcs.yaml").write_text(
        "_ids: magnetics\nb_field_pol_probe:\n- name: PCBPV1T\n  position:\n  - r: 1.29\n    z: 0.0\n"
        "  toroidal_angle: 90.0\n- name: PCBPV2T\n  position:\n  - r: 1.29\n    z: 0.248\n  toroidal_angle: 90.0\n"
        "flux_loop:\n- name: PCFL1\n  position:\n  - r: 1.0\n    z: 0.5\n")
    (tmp_path / "calib.yaml").write_text(
        "_ids: magnetics\nb_field_pol_probe:\n- name: PCBPV2T\n  field:\n    data: [0.1, 0.2]\n"
        "- name: PCBPV1T\n  field:\n    data: [0.3, 0.4]\n")
    (tmp_path / "asm.yaml").write_text(
        "$source:\n  geo: file:pcs.yaml\n  cal: file:calib.yaml\nparams:\n  shot: 138569\n  time: [4.0, 5.0]\n"
        "merge: [geo, cal]\n")
    assert fydoc.detect(tmp_path / "pcs.yaml") == ("yaml", "fyo")
    b, fails = fydoc.assemble(tmp_path / "asm.yaml", select=["magnetics/b_field_pol_probe/field",
                                                              "magnetics/b_field_pol_probe/position"])
    assert fails == []
    assert b.notes == []
    assert b.keys == ["magnetics"]
    #: aligned by name, not by position in the list
    assert b.get("magnetics/b_field_pol_probe/0/name") == "PCBPV1T"
    assert b.array("magnetics/b_field_pol_probe/0/field/data").tolist() == [0.3, 0.4]
    assert b.get("magnetics/b_field_pol_probe/1/position/0/z") == 0.248
    assert b.get("magnetics/b_field_pol_probe/0/toroidal_angle", None) is None
    assert b.get("magnetics/flux_loop", None) is None
    assert b.get("magnetics/fylite:assembly/params/time/stop") == 5.0
    #: overrides: a point in time, a shot
    b2, _ = fydoc.assemble(tmp_path / "asm.yaml", shot=7, time=4.5, max_points=100)
    assert b2.get("magnetics/fylite:assembly/shot") == 7
    assert b2.get("magnetics/fylite:assembly/params/time") == 4.5
    assert b2.get("magnetics/fylite:assembly/params/max_points") == 100
    assert b2.get("magnetics/flux_loop/0/name") == "PCFL1"


def test_fetch_flattens_a_machine_manifest(fydoc, tmp_path):
    (tmp_path / "static").mkdir()
    (tmp_path / "bind").mkdir()
    (tmp_path / "static" / "pcs.yaml").write_text("_ids: magnetics\nb_field_pol_probe:\n- name: P1\n  toroidal_angle: 90.0\n")
    (tmp_path / "bind" / "magnetics.yaml").write_text(
        "$source:\n  pcs_east: mdsplus://127.0.0.1/mdsplus/~t?shot={shot}&tree_name=pcs_east\n_ids: magnetics\n"
        "b_field_pol_probe:\n- id: '0'\n  field:\n    data:\n      $link: pcs_east:DATA(\\PCBPV1T)\n")
    (tmp_path / "machine.yaml").write_text(
        "device: EAST\nepochs:\n  - id: legacy\n    valid_shots: [0, null]\n    static: static\n    ids:\n"
        "      magnetics: \"@provider\"\nproviders:\n  magnetics:\n    default: pcs\n    available:\n"
        "      pcs: { backend: static, path: static/pcs.yaml }\nbindings:\n  mdsplus:\n    root: bind\n"
        "    ids:\n      magnetics: magnetics.yaml\n")
    #: no MDSplus server on this port: the binding is a named failure, the geometry still arrives
    b, fails = fydoc.fetch(tmp_path / "machine.yaml", "magnetics", shot=138569, time=(4.0, 5.0),
                           host="127.0.0.1", port=1, timeout_ms=500)
    assert b.get("magnetics/b_field_pol_probe/0/name") == "P1"
    assert b.get("magnetics/fylite:assembly/device") == "EAST"
    assert b.get("magnetics/fylite:assembly/params/time/start") == 4.0
    assert any("cannot connect" in f for f in fails), fails
