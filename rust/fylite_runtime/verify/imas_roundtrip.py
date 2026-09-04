#!/usr/bin/env python3
"""IMAS 互操作的对拍：数据层写的文件 imas-python / imas-core 读得回来，反之亦然。

    python rust/fylite_runtime/verify/imas_roundtrip.py [--bin target/release/fy] [--keep]

★不进 `cargo test`：要 imas-python（`pip install "imas-python[netcdf]" imas-core`），
那是一个带 DD 的大包，装不装是用户的事。但**这一份判据才是「兼容 imas-python」这句话
的全部含义**——单元测试只能判「与我读到的参考文件同形」，这里判的是「它们的读者认」。

做四件事：

1. 用 imas-python 造一份参考数据（equilibrium / core_profiles / wall / magnetics，
   含参差的时间片与稀疏叶子），写成 IMAS netCDF 与 IMAS HDF5；
2. 数据层读它们、转成 fyo JSON，逐叶子与 imas-python 内存里的值比；
3. 数据层把 fyo JSON 写回 IMAS netCDF 与 IMAS HDF5；
4. imas-python / imas-core 读回数据层写的文件，逐叶子比。

"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent


def build_reference(fac):
    eq = fac.equilibrium()
    eq.ids_properties.homogeneous_time = 1
    eq.ids_properties.comment = "fylite_runtime reference"
    eq.time = np.array([1.0, 2.0])
    eq.vacuum_toroidal_field.r0 = 1.75
    eq.vacuum_toroidal_field.b0 = np.array([1.8, 1.79])
    eq.time_slice.resize(2)
    for i, ts in enumerate(eq.time_slice):
        ts.time = eq.time[i]
        ts.global_quantities.ip = 4.0e5 + i
        ts.global_quantities.magnetic_axis.r = 1.9
        ts.profiles_1d.psi = np.linspace(0, 1, 5 + i)
        ts.profiles_1d.f = np.linspace(3, 3.1, 5 + i)
        ts.profiles_1d.q = np.linspace(1, 4, 5 + i)
        ts.boundary.outline.r = np.array([1.4, 2.2, 1.8])
        ts.boundary.outline.z = np.array([0.0, 0.0, 0.8])
        ts.profiles_2d.resize(1)
        p2 = ts.profiles_2d[0]
        p2.grid_type.index = 1
        p2.grid_type.name = "rectangular"
        p2.grid.dim1 = np.linspace(1.2, 2.8, 4)
        p2.grid.dim2 = np.linspace(-1.0, 1.0, 3)
        p2.psi = np.arange(12.0).reshape(4, 3) * (i + 1)
    cp = fac.core_profiles()
    cp.ids_properties.homogeneous_time = 1
    cp.time = np.array([1.0, 2.0])
    cp.profiles_1d.resize(2)
    for i, p in enumerate(cp.profiles_1d):
        p.grid.rho_tor_norm = np.linspace(0, 1, 4)
        p.grid.psi = np.linspace(0, 2, 4)
        p.electrons.temperature = np.linspace(2000, 100, 4)
        p.electrons.density = np.linspace(5e19, 1e19, 4)
        p.ion.resize(1)
        p.ion[0].name = "D"
        p.ion[0].temperature = np.linspace(1500, 90, 4)
    wall = fac.wall()
    wall.ids_properties.homogeneous_time = 2
    wall.description_2d.resize(1)
    wall.description_2d[0].type.index = 0
    wall.description_2d[0].limiter.unit.resize(2)
    wall.description_2d[0].limiter.unit[0].name = "main"
    wall.description_2d[0].limiter.unit[0].outline.r = np.array([1.3, 2.3, 2.3, 1.3])
    wall.description_2d[0].limiter.unit[0].outline.z = np.array([-1.0, -1.0, 1.0, 1.0])
    wall.description_2d[0].limiter.unit[1].name = "second"
    wall.description_2d[0].limiter.unit[1].outline.r = np.array([1.35, 2.25])
    wall.description_2d[0].limiter.unit[1].outline.z = np.array([-0.9, -0.9])
    mag = fac.magnetics()
    mag.ids_properties.homogeneous_time = 1
    mag.time = np.array([0.5, 1.5, 2.5])
    mag.flux_loop.resize(2)
    for i, fl in enumerate(mag.flux_loop):
        fl.name = f"FL{i+1}"
        fl.position.resize(1)
        fl.position[0].r = 1.0 + i
        fl.position[0].z = 0.1 * i
        fl.flux.data = np.array([0.1, 0.2, 0.3]) * (i + 1)
        fl.flux.time = mag.time
    return [eq, cp, wall, mag]


def leaves_of(ids):
    """{path: value} of every filled leaf, imas-python side."""
    import imas
    out = {}
    for node in imas.util.tree_iter(ids, leaf_only=True):
        if not node.has_value:
            continue
        v = node.value
        if isinstance(v, np.ndarray):
            v = v.tolist()
        out[node._path] = v
    return out


def leaves_of_fyo(doc):
    """{path: value} of every leaf of a fyo JSON document (DD keys only)."""
    out = {}

    def walk(n, p):
        if isinstance(n, dict):
            for k, v in n.items():
                if k.startswith("@") or ":" in k:
                    continue
                walk(v, f"{p}/{k}" if p else k)
        elif isinstance(n, list) and n and isinstance(n[0], dict):
            for i, v in enumerate(n):
                walk(v, f"{p}[{i}]")
        else:
            out[p] = n
    walk(doc, "")
    return out


def compare(name, a: dict, b: dict) -> int:
    bad = 0
    for k, v in a.items():
        if k not in b:
            print(f"  [{name}] missing on the other side: {k}")
            bad += 1
            continue
        w = b[k]
        if isinstance(v, str) or isinstance(w, str):
            if str(v) != str(w):
                print(f"  [{name}] {k}: {v!r} != {w!r}")
                bad += 1
        else:
            try:
                if not np.allclose(np.asarray(v, float), np.asarray(w, float), rtol=1e-12, atol=0):
                    print(f"  [{name}] {k}: values differ")
                    bad += 1
            except (ValueError, TypeError):
                if np.shape(v) != np.shape(w):
                    print(f"  [{name}] {k}: shape {np.shape(v)} != {np.shape(w)}")
                    bad += 1
    extra = set(b) - set(a)
    if extra:
        print(f"  [{name}] {len(extra)} extra leaf/leaves on the other side: {sorted(extra)[:5]}")
        bad += len(extra)
    return bad


def run(bin_path, *args):
    """One `fylite data …` call.

    ★The `data` word is supplied here.  There is ONE executable (2026-09-03);
    it dispatches on the command word, and its no-word default is `app` —
    so omitting the word would start a web server instead of converting a
    file, and would do it without an error.
    """
    argv = [bin_path, "data", *args]
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit(f"{' '.join(argv)} failed ({r.returncode})")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=str(ROOT / "target" / "release" / "fy"))
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--dd", default="4.1.1")
    args = ap.parse_args()
    import imas
    fac = imas.IDSFactory(args.dd)
    work = pathlib.Path(tempfile.mkdtemp(prefix="fylite_runtime_verify_"))
    print(f"work dir {work}")
    ref = build_reference(fac)
    expected = {ids.metadata.name: leaves_of(ids) for ids in ref}
    # ignore what imas-python fills in on put (version_put)
    for d in expected.values():
        for k in [k for k in d if k.startswith("ids_properties/version_put")]:
            d.pop(k)
    with imas.DBEntry(str(work / "ref.nc"), "w", dd_version=args.dd) as db:
        for ids in ref:
            db.put(ids)
    with imas.DBEntry(f"imas:hdf5?path={work / 'ref_h5'}", "w", dd_version=args.dd) as db:
        for ids in ref:
            db.put(ids)
    bad = 0
    # ---- 2. Rust reads imas-python's files
    for src in ("ref.nc", "ref_h5"):
        r = run(args.bin, "dump", str(work / src))
        got = json.loads(r.stdout)
        docs = got if "@type" not in got else {"only": got}
        for key, doc in docs.items():
            ids = doc["@type"].split(":")[1]
            mine = leaves_of_fyo(doc)
            for k in [k for k in mine if k.startswith("ids_properties/version_put")]:
                mine.pop(k)
            n = compare(f"rust reads {src}:{ids}", expected[ids], mine)
            print(f"rust reads {src}:{ids}: {len(mine)} leaves, {n} mismatch(es)")
            bad += n
    # ---- 3/4. Rust writes, imas-python reads
    run(args.bin, "convert", str(work / "ref.nc"), str(work / "fyo.json"))
    run(args.bin, "convert", str(work / "fyo.json"), str(work / "rust.nc"), "--layout", "imas")
    run(args.bin, "convert", str(work / "fyo.json"), str(work / "rust_h5"), "--layout", "imas", "--to", "imas-hdf5")
    for uri in (str(work / "rust.nc"), f"imas:hdf5?path={work / 'rust_h5'}"):
        with imas.DBEntry(uri, "r") as db:
            for ids in ref:
                name = ids.metadata.name
                back = db.get(name)
                got = leaves_of(back)
                for k in [k for k in got if k.startswith("ids_properties/version_put")]:
                    got.pop(k)
                n = compare(f"imas reads {uri}:{name}", expected[name], got)
                print(f"imas-python reads {uri.split('=')[-1]}:{name}: {len(got)} leaves, {n} mismatch(es)")
                bad += n
    # ---- 5. imas-python validates the netCDF file explicitly
    from imas.backends.netcdf.nc_validate import validate_netcdf_file
    try:
        validate_netcdf_file(str(work / "rust.nc"))
        print("imas-python nc_validate: ok")
    except Exception as e:  # noqa: BLE001
        print(f"imas-python nc_validate: FAILED {e}")
        bad += 1
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    print("RESULT", "ok" if bad == 0 else f"{bad} problem(s)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
