"""east-free-boundary-evolution 的冒烟测试——只用标准库与合成数据（不读任何 EAST 文件）。

    python3 -m pytest apps/east-free-boundary-evolution/test -q        # 或
    python3 apps/east-free-boundary-evolution/test/test_smoke.py

库（``libfylite.so``）在就多测一条 G-EQDSK 写出 → 库里的读者读回；不在就跳过那一条。
"""
from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import fb_evolution as fe  # noqa: E402


def _mat_v5(path: Path, arrays: dict, compress: bool) -> None:
    """写一份最小的 MATLAB v5（double 实数矩阵，列主序）——测读者用。"""
    def el(t, data):
        pad = (8 - len(data) % 8) % 8
        return struct.pack("<II", t, len(data)) + data + b"\0" * pad
    body = b""
    for name, rows in arrays.items():
        nr, nc = len(rows), len(rows[0])
        col = [rows[i][j] for j in range(nc) for i in range(nr)]
        m = (el(6, struct.pack("<II", 6, 0)) + el(5, struct.pack("<ii", nr, nc)) + el(1, name.encode())
             + el(9, struct.pack("<%dd" % len(col), *col)))
        mat = struct.pack("<II", 14, len(m)) + m
        body += (struct.pack("<II", 15, len(zlib.compress(mat))) + zlib.compress(mat)) if compress else mat
    head = b"MATLAB 5.0 MAT-file, synthetic".ljust(116, b" ") + b"\0" * 8 + struct.pack("<H", 0x0100) + b"IM"
    path.write_bytes(head + body)


class Readers(unittest.TestCase):
    def test_mat5_both_spellings(self):
        with tempfile.TemporaryDirectory() as d:
            for compress in (False, True):
                p = Path(d) / f"x{int(compress)}.mat"
                _mat_v5(p, {"pf": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], "t": [[0.0, 0.5, 1.0]]}, compress)
                got = fe.read_mat5(p)
                self.assertEqual(got["pf"], [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
                self.assertEqual(got["t"], [0.0, 0.5, 1.0])


class Geometry(unittest.TestCase):
    def ring(self, n, r0, a, z0=0.0):
        th = [2 * math.pi * k / n for k in range(n)]
        return [r0 + a * math.cos(t) for t in th], [z0 + a * math.sin(t) for t in th]

    def test_contours_and_strips(self):
        #: 一圈闭合（24 根，间距 ~0.13 m）+ 一段开口弧（6 根）
        r1, z1 = self.ring(24, 1.8, 0.5)
        r2 = [2.3 + 0.05 * k for k in range(6)]
        z2 = [0.9] * 6
        r, z = r1 + r2, z1 + z2
        res = [0.01 + 0.001 * k for k in range(len(r))]
        cs = fe.filament_contours(r, z)
        self.assertEqual([(s[0], s[-1], c) for s, c in cs], [(0, 23, True), (24, 29, False)])
        rows, info = fe.filament_strips(r, z, res)
        for i, (row, inf) in enumerate(zip(rows, info)):
            rr, zz, w, h, a1, a2 = row
            #: 内核的元件电阻 ρ·2πr/(w·h) 逐丝等于给定的 R（相对 1e-12）
            self.assertAlmostEqual(fe.RHO_SS * 2 * math.pi * rr / (w * h) / res[i], 1.0, places=12)
            self.assertAlmostEqual(w * h, inf["length_m"] * inf["thickness_m"], places=14)
            self.assertTrue(a1 == 0.0 or a2 == 90.0)
        #: 开口弧的丝水平：a1 剪切 0°、长度方向沿 R
        self.assertEqual(rows[26][4], 0.0)
        self.assertAlmostEqual(rows[26][2], 0.05, places=12)
        #: 圆上 θ = 0 处切向竖直：a2 = 90°、高 ≈ 弦长
        self.assertAlmostEqual(rows[0][5], 90.0, places=9)

    def test_channels_fold_turns(self):
        el = lambda r, z, n: {"geometry": {"rectangle": {"r": r, "z": z, "width": 0.1, "height": 0.1}},  # noqa: E731
                              "turns_with_sign": n}
        dev = {"pf_active": {"coil": [
            {"name": "PF1", "element": [el(0.6, 0.2, 140)]},
            {"name": "PF7", "element": [el(1.0, 1.7, 44)]},
            {"name": "PF9", "element": [el(1.1, 1.9, 204)]},
            {"name": "IC1", "element": [el(2.4, 0.6, 2)], "function": [{"name": "b_field_fb"}]},
            {"name": "IC2", "element": [el(2.4, -0.6, 2)], "function": [{"name": "b_field_fb"}]}]},
            "pf_channel_elements": [[{"element": 0, "weight": 1.0}],
                                    [{"element": 1, "weight": 44 / 248}, {"element": 2, "weight": 204 / 248}]]}
        ch = fe.channel_table(dev)
        self.assertEqual([c["name"] for c in ch], ["PF1", "PF7+PF9", "IC1", "IC2"])
        at = fe.channel_aturns(ch, {"PF1": -10.0, "PF7": 5.0, "PF9": 6.0, "IC1": 3.0, "IC2": -3.0})
        self.assertEqual(at, [-1400.0, 44 * 5.0 + 204 * 6.0, 6.0, -6.0])


class Integrals(unittest.TestCase):
    def test_circular_torus_volume_and_current(self):
        #: ψ = B0/2·((R−R0)² + Z²)（Wb/rad）：圆截面、B_p = B0·ρ/R；边界 ρ = a
        r0, a, b0 = 1.8, 0.4, 0.5
        gr = [1.2 + 1.2 * i / 96 for i in range(97)]
        gz = [-0.6 + 1.2 * j / 96 for j in range(97)]
        psi = [[0.5 * b0 * ((r - r0) ** 2 + z * z) for z in gz] for r in gr]
        mp = fe.Map(gr, gz, psi)
        n = 181
        bnd = [[r0 + a * math.cos(2 * math.pi * k / n), a * math.sin(2 * math.pi * k / n)] for k in range(n)]
        it = fe.map_integrals(mp, 0.0, 0.5 * b0 * a * a, bnd, [0.0, 1.0], [1e4, 0.0])
        vol = 2 * math.pi * r0 * math.pi * a * a
        self.assertAlmostEqual(it["volume_m3"] / vol, 1.0, delta=5e-3)
        #: ∮B_p dl = B0·a·∮dθ·a/R… 数值上与直接的环路积分比（容差 0.5 %：网格与折线离散）
        want = sum(b0 * a / (r0 + a * math.cos(t)) * a * (2 * math.pi / 720)
                   for t in [2 * math.pi * (k + 0.5) / 720 for k in range(720)]) / fe.MU0
        self.assertAlmostEqual(it["ip_ampere_A"] / want, 1.0, delta=5e-3)

    def test_boundary_distance_of_shifted_circle(self):
        c = [[math.cos(2 * math.pi * k / 64), math.sin(2 * math.pi * k / 64)] for k in range(64)]
        d = fe.boundary_distance(c, [[x + 0.01, y] for x, y in c])
        self.assertAlmostEqual(d["max_m"], 0.01, delta=2e-4)

    def test_pair_field_is_antisymmetric(self):
        gr, gz = [1.2, 2.8], [-1.4, 1.4]
        #: 上下两环（+1 A 在上、−1 A 在下）在中平面叠加：B_R 不为零，且对 Z 偶
        self.assertAlmostEqual(fe.pair_br(gr, gz, 1.9, 0.1), fe.pair_br(gr, gz, 1.9, -0.1), places=15)
        self.assertNotEqual(fe.pair_br(gr, gz, 1.9, 0.0), 0.0)


def _lib_path():
    p = Path(os.environ.get("FYLITE_APP_LIB") or (HERE.parent / "libfylite.so"))
    return p if p.is_file() else None


@unittest.skipIf(_lib_path() is None, "no libfylite.so next to the app (or $FYLITE_APP_LIB)")
class GfileRoundTrip(unittest.TestCase):
    def test_written_gfile_reads_back(self):
        lib = fe.Lib(_lib_path())
        nr = nz = 33
        gr = [1.2 + 1.6 * i / (nr - 1) for i in range(nr)]
        gz = [-1.4 + 2.8 * j / (nz - 1) for j in range(nz)]
        psi = [[-((r - 1.85) ** 2 + (z / 1.6) ** 2) for z in gz] for r in gr]
        s = {"psin_1d": [0.0, 1.0], "pres": [2e4, 0.0], "fpol": [-4.4, -4.5], "q_x": [0.0, 1.0], "q": [1.0, 4.0],
             "boundary": [[1.85 + 0.4 * math.cos(t), 0.6 * math.sin(t)] for t in [k * 0.1 for k in range(63)]],
             "map": fe.Map(gr, gz, psi)}
        case = {"shot": 1, "gfile": {"rcentr": 1.85, "bcentr": -2.4}}
        facts = {"psi_axis": 0.0, "psi_bnd": -0.16, "axis_r": 1.85, "axis_z": 0.0}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "g000001.01000"
            fe.write_gfile(p, case, s, facts, gr, gz, -1.0, 1.0, 4e5, [[1.3, -1.1], [2.4, -1.1], [2.4, 1.1], [1.3, 1.1]])
            g = fe.read_gfile(lib, p)
        self.assertEqual((g["nw"], g["nh"]), (nr, nz))
        self.assertAlmostEqual(g["current"], 4e5)
        self.assertAlmostEqual(g["simag"], 0.0)
        self.assertAlmostEqual(g["sibry"], 0.16 / (2 * math.pi), places=9)
        self.assertAlmostEqual(g["psi"][5][7], -psi[5][7] / (2 * math.pi), places=9)
        self.assertEqual(len(g["boundary"]), 63)


if __name__ == "__main__":
    unittest.main()
