"""ShotCache (FYL-REPORT-11 O-1a): a batch's per-slice pulls share one remembering mdsip session.

A fake session stands in for mdsip: the cache must make each distinct read once, open a tree only on a
miss, hand out copies (a caller's edits cannot reach the next slice), remember an error as well as an
answer, and resolve the device once per (device, shot, chain)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kinetic_recon as K  # noqa: E402


class FakeMds:
    def __init__(self, log):
        self.log, self.tree = log, None

    def open_tree(self, tree, shot):
        self.log.append(("open", tree, shot))
        self.tree = tree

    def read(self, verb, node, sub=None):
        self.log.append(("read", self.tree, verb, node))
        if node == r"\MISSING":
            raise K.KernelError("no such node")
        return [1.0, 2.0, 3.0, 4.0], [2, 2]

    def close(self):
        self.log.append(("close",))


class FakeLib:
    def __init__(self):
        self.log, self.devices = [], 0

    def mds_open(self, host, port, timeout_s):
        self.log.append(("connect", host, port))
        return FakeMds(self.log)

    def device(self, device_id, shot, chain):
        self.devices += 1
        return {"id": device_id, "shot": shot}, {"r": 1}


class ShotCacheTest(unittest.TestCase):
    def test_each_read_is_made_once_and_handed_out_as_a_copy(self):
        lib = FakeLib()
        c = K.ShotCache(lib)
        for _ in range(3):                                   # three slices
            s = c.mds_open("h", 8000, 10.0)
            s.open_tree("ts_east", 1)
            v, dims = s.read("data", r"\TE")
            v.append(99.0)                                   # a caller's edit …
            s.close()
        self.assertEqual(c.mds_open("h", 8000, 10.0).read("data", r"\TE")[0], [1.0, 2.0, 3.0, 4.0])  # … stays its own
        self.assertEqual([e for e in lib.log if e[0] == "connect"], [("connect", "h", 8000)])
        self.assertEqual([e for e in lib.log if e[0] == "read"], [("read", "ts_east", "data", r"\TE")])
        self.assertEqual([e for e in lib.log if e[0] == "open"], [("open", "ts_east", 1)])

    def test_rows_split_by_the_fast_axis_like_the_real_session(self):
        s = K.ShotCache(FakeLib()).mds_open("h", 1, 1.0)
        s.open_tree("t", 1)
        self.assertEqual(s.rows(r"\X"), [[1.0, 2.0], [3.0, 4.0]])

    def test_an_error_is_remembered_and_raised_again(self):
        lib = FakeLib()
        s = K.ShotCache(lib).mds_open("h", 1, 1.0)
        s.open_tree("t", 1)
        for _ in range(2):
            with self.assertRaises(K.KernelError):
                s.read("data", r"\MISSING")
        self.assertEqual(len([e for e in lib.log if e[0] == "read"]), 1)

    def test_another_tree_is_opened_when_a_read_needs_it(self):
        lib = FakeLib()
        s = K.ShotCache(lib).mds_open("h", 1, 1.0)
        s.open_tree("a", 1); s.read("data", r"\X")
        s.open_tree("b", 1); s.read("data", r"\X")
        s.open_tree("a", 1); s.read("data", r"\X")        # remembered: no reopen, no read
        self.assertEqual([e for e in lib.log if e[0] == "open"], [("open", "a", 1), ("open", "b", 1)])

    def test_the_device_is_resolved_once_and_copied(self):
        lib = FakeLib()
        c = K.ShotCache(lib)
        d1, _ = c.device("east", 5, "east")
        d1["id"] = "changed"
        d2, _ = c.device("east", 5, "east")
        self.assertEqual((lib.devices, d2["id"]), (1, "east"))

    def test_close_closes_the_real_sessions(self):
        lib = FakeLib()
        c = K.ShotCache(lib)
        c.mds_open("h", 1, 1.0).close()                      # a pull's close is a no-op
        self.assertNotIn(("close",), lib.log)
        c.close()
        self.assertIn(("close",), lib.log)


if __name__ == "__main__":
    unittest.main()
