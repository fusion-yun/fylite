"""Consumer host tests. These do NOT substitute for running the released native library."""
import ctypes
import importlib.util
import io
import json
import socket
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eq_delivery", ROOT / "tools/eq_delivery.py")
eq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eq)


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.personal = self.root / "personal"
        self.personal.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def archive(self, entries):
        archive = self.root / "native.tar.gz"
        with tarfile.open(archive, "w:gz") as out:
            for name, value in entries:
                item = tarfile.TarInfo(name)
                if isinstance(value, tuple):
                    item.type, item.linkname = tarfile.SYMTYPE, value[0]
                    out.addfile(item)
                else:
                    item.size = len(value)
                    out.addfile(item, io.BytesIO(value))
        return archive

    def fixture(self):
        names = ["libfylite.so", "libsp_full.so", "fy-0.0.1-alpha-rc3-linux-x86_64"]
        contents = [b"test-kernel-not-a-real-library", b"test-data", b"test-cli"]
        archive = self.archive(list(zip(names, contents)))
        lock = {"tag": "test", "archive": {"sha256": eq.digest(archive)},
                "assets": [{"name": n, "sha256": eq.hashlib.sha256(v).hexdigest()} for n, v in zip(names, contents)]}
        return archive, lock

    def test_import_uses_digests_and_records_full_data_variant(self):
        archive, lock = self.fixture()
        target = self.root / "artifacts"
        eq.import_artifacts(archive, target, lock)
        identity = eq.verify_artifacts(target, lock)
        self.assertIn("full", identity["data_variant"])
        self.assertEqual((target / "lib/libsp.so.0").resolve(), target / "lib/libsp.so")
        with self.assertRaises(ValueError):
            eq.import_artifacts(archive, target, lock)

    def test_wrong_archive_hash_creates_no_install(self):
        archive, lock = self.fixture()
        lock["archive"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            eq.import_artifacts(archive, self.root / "bad", lock)
        self.assertFalse((self.root / "bad").exists())

    def test_installed_library_tampering_is_rejected(self):
        archive, lock = self.fixture()
        target = self.root / "artifacts"
        eq.import_artifacts(archive, target, lock)
        (target / "lib/libsp.so").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            eq.verify_artifacts(target, lock)

    def test_missing_library_identity_cannot_pass_verification(self):
        archive, lock = self.fixture()
        target = self.root / "artifacts"
        eq.import_artifacts(archive, target, lock)
        meta = eq.read(target / "artifacts.json")
        meta["libraries"] = {}
        eq.write(target / "artifacts.json", meta)
        with self.assertRaises(ValueError):
            eq.verify_artifacts(target, lock)

    def test_tar_traversal_and_absolute_links_rejected(self):
        for entries in [[("../escaped", b"x")], [("link", ("/etc/passwd",))]]:
            archive = self.archive(entries)
            with self.assertRaises(ValueError):
                eq.extract(archive, self.root / "extract")
        self.assertFalse((self.root / "escaped").exists())

    def test_save_is_personal_exclusive_and_preserves_public_case(self):
        public = ROOT / "delivery/eq/cases/EQ-B0-SOLOVEV/case.json"
        before = public.read_bytes()
        cfg = {"case_id": "EQ-B0-SOLOVEV", "parameters": {"nr": 33}}
        target = self.personal / "example/case.json"
        eq.save_case(target, cfg, [self.personal])
        self.assertEqual(eq.read(target)["parameters"], {"nr": 33})
        with self.assertRaises(FileExistsError):
            eq.save_case(target, cfg, [self.personal])
        self.assertEqual(before, public.read_bytes())

    def test_public_outside_and_symlink_targets_refused(self):
        for target in ["/project/FyLite/test.json", "/data/project/FyLite/test.json", str(self.root / "outside.json")]:
            with self.assertRaises(ValueError):
                eq.personal(target, [self.personal])
        (self.personal / "link").symlink_to(self.root)
        with self.assertRaises(ValueError):
            eq.personal(self.personal / "link/escape.json", [self.personal])

    def test_parameter_errors_never_clamped(self):
        for value in [{"nr": 34}, {"nr": True}, {"nr": 65.}, {"nr": 65, "q0": 1}, {}]:
            with self.assertRaises(ValueError):
                eq.parameters(value)

    def test_solovev_boundary_has_analytic_zero_flux_and_no_q_prior(self):
        plan, truth = eq.solovev(33)
        boundary = plan["inputs"]["equilibrium"]["time_slice"]["boundary"]["outline"]
        residuals = [truth["psi_axis_Wb"]-(r*r-1.8**2)**2-truth["e2"]*r*r*z*z-z*z
                     for r, z in zip(boundary["r"], boundary["z"])]
        self.assertLess(max(abs(v) for v in residuals), 1e-12)
        self.assertNotIn("q0", plan["settings"])
        self.assertGreater(truth["q0"], 0)

    def test_missing_native_library_retains_failed_run_not_success(self):
        case = self.personal / "case.json"
        eq.write(case, {"case_id": "EQ-B0-SOLOVEV", "parameters": {"nr": 33}})
        run = self.personal / "runs/failed"
        status = eq.run_case(case, self.root / "missing", run, {"tag": "test"})
        self.assertEqual(status["execution"], "failed")
        self.assertEqual(status["physical"], "not_assessed")
        self.assertTrue((run / "input.json").is_file())
        self.assertTrue((run / "status.json").is_file())
        self.assertFalse((run / "result.json").exists())

    def test_sbatch_failure_recorded_without_fabricated_job(self):
        archive, lock = self.fixture()
        art = self.root / "artifacts"
        eq.import_artifacts(archive, art, lock)
        case = self.personal / "case.json"
        eq.save_case(case, {"case_id": "EQ-B0-SOLOVEV", "parameters": {"nr": 33}}, [self.personal])
        with patch.object(eq, "read", side_effect=lambda p: lock if Path(p) == eq.LOCK_PATH else json.loads(Path(p).read_text())), \
                patch.object(eq.subprocess, "run", side_effect=FileNotFoundError("sbatch unavailable")):
            with self.assertRaises(FileNotFoundError):
                eq.submit(case, art, [self.personal], backend="slurm")
        runs = list((self.personal / "runs").iterdir())
        self.assertEqual(eq.read(runs[0] / "status.json")["execution"], "submit_failed")
        self.assertFalse((runs[0] / "job.json").exists())

    def test_scheduler_query_failure_keeps_worker_status(self):
        run = self.personal / "runs/a"
        run.mkdir(parents=True)
        eq.write(run / "job.json", {"job_id": "123"})
        eq.write(run / "status.json", {"execution": "completed", "numerical": "converged", "physical": "not_assessed"})
        with patch.object(eq.subprocess, "run", side_effect=FileNotFoundError("sacct unavailable")):
            result = eq.job_status(run, [self.personal])
        self.assertEqual(result["execution"], "completed")
        self.assertEqual(result["scheduler"], "unknown")

    def test_packaging_is_explicit_and_relocatable_without_dev_source(self):
        archive, lock = self.fixture()
        art, output = self.root / "artifacts", self.root / "release/eq"
        eq.import_artifacts(archive, art, lock)
        payload = self.root / "payload-with-cache"
        shutil.copytree(eq.PAYLOAD, payload)
        cache = payload / "apps/workflow/__pycache__"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "stale.pyc").write_bytes(b"test cache")
        (payload / "loose.pyo").write_bytes(b"test cache")
        with patch.object(eq, "PAYLOAD", payload):
            eq.package(output, art, lock)
        self.assertFalse(list(output.rglob("__pycache__")))
        self.assertFalse(list(output.rglob("*.pyc")))
        self.assertFalse(list(output.rglob("*.pyo")))
        self.assertTrue((output / "server/eq_server.py").is_file())
        self.assertTrue((output / "apps/fixed-boundary/eq_delivery.py").is_file())
        self.assertTrue((output / "bin/fy").is_file())
        self.assertTrue((output / "cases/EQ-B0-SOLOVEV/data-manifest.json").is_file())
        generator = eq.read(output / "cases/EQ-B0-SOLOVEV/data-manifest.json")["generator"]
        self.assertEqual(eq.digest(output / generator["file"]), generator["sha256"])
        self.assertTrue((output / "index.html").is_file())
        self.assertFalse((output / "fylite_dev").exists())
        manifest = eq.read(output / "release-manifest.json")
        for name, sha in manifest["files"].items():
            self.assertEqual(eq.digest(output / name), sha)
        proc = subprocess.run([sys.executable, str(output / "bin/fylite-eq"), "--help"],
                              cwd=self.root, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_default_direct_worker_records_failure_without_using_slurm(self):
        archive, lock = self.fixture()
        art = self.root / "artifacts"
        eq.import_artifacts(archive, art, lock)
        case = self.personal / "case.json"
        eq.save_case(case, {"case_id": "EQ-B0-SOLOVEV", "parameters": {"nr": 33}}, [self.personal])
        original = eq.read
        with patch.object(eq, "read", side_effect=lambda p: lock if Path(p) == eq.LOCK_PATH else original(p)), \
                patch.object(eq.subprocess, "run", side_effect=AssertionError("Slurm must not be invoked")):
            response = eq.submit(case, art, [self.personal])
            self.assertEqual(response["backend"], "direct")
            self.assertNotIn("job_id", response)
            for _ in range(100):
                status = original(Path(response["run"]) / "status.json")
                if status["execution"] == "failed" and "process_exit_code" in status:
                    break
                time.sleep(.02)
        self.assertEqual(status["execution"], "failed")
        self.assertTrue((Path(response["run"]) / "stderr.log").is_file())

    def test_direct_cancel_only_targets_recorded_worker_process(self):
        run = self.personal / "runs/cancel"
        run.mkdir(parents=True)
        token = "test-worker-token"
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)", token], start_new_session=True)
        try:
            identity = eq.process_identity(proc.pid)
            eq.write(run / "job.json", {"backend": "direct", "pid": proc.pid,
                     "start_ticks": identity["start_ticks"], "run_token": token})
            eq.write(run / "status.json", {"execution": "running"})
            with patch.object(eq.subprocess, "run", side_effect=AssertionError("No scheduler command allowed")):
                self.assertTrue(eq.job_status(run, [self.personal], cancel=True)["cancel_requested"])
            proc.wait(timeout=5)
            self.assertEqual(eq.read(run / "status.json")["execution"], "cancelled")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_http_personal_save_and_missing_artifact_refusal(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        proc = subprocess.Popen([sys.executable, str(ROOT / "tools/eq_delivery.py"), "serve",
                                 "--artifacts", str(self.root / "missing"), "--personal-root", str(self.personal),
                                 "--port", str(port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        base = f"http://127.0.0.1:{port}"
        try:
            info = None
            for _ in range(60):
                try:
                    with urllib.request.urlopen(base + "/api/info", timeout=1) as response:
                        info = json.load(response)
                    break
                except urllib.error.URLError:
                    if proc.poll() is not None:
                        self.fail(proc.communicate()[1].decode())
                    time.sleep(.05)
            self.assertIsNotNone(info)
            self.assertFalse(info["artifact_ready"])
            for path, expected in (("/fylite/", "认识 FyLite"), ("/fylite/eq/", "理解输入"),
                                   ("/fylite/eq/docs/USAGE.zh-CN.html", "使用方法")):
                with urllib.request.urlopen(base + path) as response:
                    self.assertIn(expected, response.read().decode())
            with urllib.request.urlopen(base + "/fylite/eq") as response:
                self.assertTrue(response.url.endswith("/fylite/eq/"))
            with urllib.request.urlopen(base + "/fylite/eq/api/info") as response:
                self.assertEqual(json.load(response)["token"], info["token"])

            def request(path, body, token):
                req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json", "X-FyLite-Token": token})
                try:
                    with urllib.request.urlopen(req) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as exc:
                    return exc.code, json.load(exc)
            body = {"path": str(self.personal / "sample/case.json"),
                    "case": {"case_id": "EQ-B0-SOLOVEV", "parameters": {"nr": 33}}}
            self.assertEqual(request("/api/save", body, "incorrect")[0], 403)
            self.assertEqual(request("/fylite/eq/api/save", body, info["token"])[0], 200)
            self.assertEqual(request("/api/save", body, info["token"])[0], 400)
            self.assertEqual(request("/api/submit", {"path": body["path"]}, info["token"])[0], 400)
            self.assertFalse((self.personal / "sample/runs").exists())
            self.assertEqual(request("/api/open", [], info["token"])[0], 400)
        finally:
            proc.terminate()
            proc.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
