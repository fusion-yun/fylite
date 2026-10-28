#!/usr/bin/env python3
"""FyLite standalone EQ delivery host (stdlib only; never builds kernel source)."""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import http.server
import json
import math
import os
from pathlib import Path
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid

SOURCE = next((p for p in Path(__file__).resolve().parents
               if (p / "kernel.lock.json").is_file() or (p / "delivery/eq").is_dir()),
              Path(__file__).resolve().parents[1])
PAYLOAD = SOURCE / "delivery/eq" if (SOURCE / "delivery/eq").is_dir() else SOURCE
LOCK_PATH = SOURCE / "releases/kernel-rc3.lock.json" if (SOURCE / "releases").is_dir() else SOURCE / "kernel.lock.json"


def read(path):
    def reject(value):
        raise ValueError(f"nonfinite JSON value: {value}")
    return json.loads(Path(path).read_text(), parse_constant=reject)


def write(path, value, exclusive=False):
    path = Path(path)
    raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if exclusive:
        with path.open("x") as stream:
            stream.write(raw)
    else:
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temporary.write_text(raw)
        os.replace(temporary, path)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def personal(path, roots):
    p = Path(path).expanduser()
    if not p.is_absolute():
        raise ValueError("选择服务器上的个人绝对路径")
    p = p.resolve()
    if inside(p, "/project") or inside(p, "/data/project") or inside(p, PAYLOAD):
        raise ValueError("个人算例和运行不能写入公共project或发布目录")
    if not any(inside(p, root) and p != Path(root).expanduser().resolve() for root in roots):
        raise ValueError("目标必须位于启动时声明的个人目录内")
    ancestor = p
    while not ancestor.exists():
        ancestor = ancestor.parent
    if ancestor.stat().st_uid != os.getuid():
        raise ValueError("目标已有祖先目录不属于当前运行用户")
    return p


def parameters(value):
    if not isinstance(value, dict) or set(value) != {"nr"}:
        raise ValueError("B0只接受nr，未知或缺失字段必须修正")
    if type(value["nr"]) is not int or value["nr"] not in (33, 65, 129):
        raise ValueError("nr必须为33、65或129")
    return value


def extract(archive, destination):
    """Extract regular files first, then bounded relative symlinks; no device files."""
    destination = Path(destination).resolve()
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for m in members:
            path = destination / m.name
            if m.name.startswith("/") or not inside(path, destination):
                raise ValueError(f"archive path escapes destination: {m.name}")
            if not (m.isfile() or m.isdir() or m.issym()):
                raise ValueError(f"unsupported archive entry: {m.name}")
            if m.issym() and (Path(m.linkname).is_absolute() or not inside(path.parent / m.linkname, destination)):
                raise ValueError(f"archive link escapes destination: {m.name}")
        for m in members:
            path = destination / m.name
            if m.issym():
                continue
            if any(p.is_symlink() for p in path.parents if p != destination.parent):
                raise ValueError("archive entry traverses a symlink")
            if m.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(m) as src, path.open("xb") as out:
                    shutil.copyfileobj(src, out)
                path.chmod(m.mode & 0o755)
        for m in members:
            if m.issym():
                path = destination / m.name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(m.linkname)
        for m in members:
            if not inside(destination / m.name, destination):
                raise ValueError("archive symlink chain escapes destination")


def import_artifacts(archive, target, lock):
    archive, target = Path(archive), Path(target).resolve()
    if target.exists():
        raise ValueError("制品目标已存在；请使用新版本目录")
    if digest(archive) != lock["archive"]["sha256"]:
        raise ValueError("发布包SHA256不匹配，拒绝加载或安装")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".fylite-import-", dir=target.parent) as temp:
        stage = Path(temp)
        extract(archive, stage / "upstream")
        files = [p for p in (stage / "upstream").rglob("*") if p.is_file() and not p.is_symlink()]
        hashes = {digest(p): p for p in files}
        assets = {a["name"]: a for a in lock["assets"]}
        lib = stage / "lib"
        lib.mkdir()
        selected = {}
        for upstream, name in [("libfylite.so", "libfylite_kernel.so"), ("libsp_full.so", "libsp.so"),
                               ("fy-0.0.1-alpha-rc3-linux-x86_64", "fy")]:
            sha = assets[upstream]["sha256"]
            if sha not in hashes:
                raise ValueError(f"发布包缺少匹配SHA的{upstream}")
            shutil.copy2(hashes[sha], lib / name)
            selected[name] = {"upstream_asset": upstream, "sha256": sha}
        (lib / "fy").chmod(0o755)
        (lib / "libfylite_kernel.so.0").symlink_to("libfylite_kernel.so")
        (lib / "libsp.so.0").symlink_to("libsp.so")
        write(stage / "artifacts.json", {"schema": "fylite.artifacts/1", "tag": lock["tag"],
              "archive_sha256": digest(archive), "libraries": selected,
              "data_variant": "full (explicitly installed as libsp.so)", "runtime_validated": False})
        write(stage / "kernel.lock.json", lock)
        # Retain upstream metadata and licences with their original directory structure.
        os.rename(stage, target)
    return read(target / "artifacts.json")


def fetch_artifacts(target, lock):
    """Use an authenticated gh when present; otherwise try the public asset URL."""
    with tempfile.TemporaryDirectory(prefix="fylite-download-") as tmp:
        archive = Path(tmp) / lock["archive"]["name"]
        gh = shutil.which("gh")
        if gh:
            subprocess.run([gh, "release", "download", lock["tag"], "--repo", lock["repository"],
                            "--pattern", archive.name, "--dir", tmp], check=True, timeout=180)
        else:
            try:
                with urllib.request.urlopen(lock["archive"]["url"], timeout=30) as src, archive.open("xb") as out:
                    shutil.copyfileobj(src, out)
            except OSError as exc:
                raise ValueError("发布包无法直接下载；私有Release需已登录gh，或先下载原生包后用import-artifacts。源码标签归档不替代原生包。") from exc
        return import_artifacts(archive, target, lock)


def verify_artifacts(root, lock):
    root = Path(root).resolve()
    identities = read(root / "artifacts.json")
    if identities.get("tag") != lock["tag"] or identities.get("archive_sha256") != lock["archive"]["sha256"]:
        raise ValueError("制品身份与当前锁文件不匹配")
    expected = {a["name"]: a["sha256"] for a in lock["assets"]}
    if set(identities.get("libraries", {})) != {"libfylite_kernel.so", "libsp.so", "fy"}:
        raise ValueError("制品清单必须同时包含内核、完整数据层和CLI")
    for name, record in identities["libraries"].items():
        relative = "bin/fy" if name == "fy" and (root / "release-manifest.json").is_file() else "lib/" + name
        if record["sha256"] != expected[record["upstream_asset"]] or digest(root / relative) != record["sha256"]:
            raise ValueError(f"制品哈希不匹配: {name}")
    return identities


class Kernel:
    def __init__(self, root, lock):
        self.identity = verify_artifacts(root, lock)
        self.lib = ctypes.CDLL(str(Path(root).resolve() / "lib/libfylite_kernel.so"))
        abi = self.lib.fylite_rs_abi_version
        abi.restype = ctypes.c_uint32
        if abi() != lock["abi"]:
            raise ValueError("内核ABI与锁文件不匹配")
        version = self.lib.fylite_rs_kernel_version
        version.argtypes = [ctypes.c_char_p, ctypes.c_uint64]
        version.restype = ctypes.c_uint64
        buf = ctypes.create_string_buffer(64)
        n = version(buf, len(buf))
        if n > len(buf) or buf.raw[:n].decode() != lock["kernel_version"]:
            raise ValueError("内核版本与锁文件不匹配")
        self.call = self.lib.fylite_rs_fyo_json
        self.call.argtypes = [ctypes.c_char_p, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_uint64,
                              ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint64)]
        self.call.restype = ctypes.c_int32
        self.release = self.lib.fylite_rs_free
        self.release.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        self.release.restype = None
        self.identity = {**self.identity, "abi": lock["abi"], "kernel_version": lock["kernel_version"],
                         "runtime_validated": True, "validation_scope": "native hash, ABI and version loading only"}

    def run(self, plan):
        code, raw = b"code/fixed_boundary", json.dumps(plan, allow_nan=False).encode()
        output, length = ctypes.c_void_p(), ctypes.c_uint64()
        status = self.call(code, len(code), raw, len(raw), ctypes.byref(output), ctypes.byref(length))
        try:
            value = json.loads(ctypes.string_at(output, length.value)) if output.value else {}
        finally:
            if output.value:
                self.release(output, length.value)
        if status != 0 or "refusal" in value:
            raise ValueError(f"内核拒绝或失败({status}): {value}")
        return value


def solovev(nr):
    """Analytic full-turn-Wb source and psi=0 contour; no experimental inputs."""
    r0, e1, e3, b0 = 1.8, 1., 1., 2.
    e2 = (4 * e1 * r0**2 / 1.7**2 - e3) / r0**2
    pc = e1 * (2.25**2 - r0**2)**2
    def psi(r, z):
        return pc - e1 * (r*r - r0*r0)**2 - e2*r*r*z*z - e3*z*z
    rs, zs = [], []
    for i in range(720):
        c, s = math.cos(2*math.pi*i/720), math.sin(2*math.pi*i/720)
        lo, hi = 0., 1.5
        for _ in range(80):
            mid = (lo+hi)/2
            if psi(r0+mid*c, mid*s) > 0:
                lo = mid
            else:
                hi = mid
        rs.append(r0+(lo+hi)*c/2)
        zs.append((lo+hi)*s/2)
    pp = (8*e1+2*e2)/(4*math.pi**2 * (4e-7*math.pi))
    ff = 2*e3/(4*math.pi**2)
    plan = {"settings": {"nr": nr, "nz": nr}, "inputs": {"equilibrium": {
        "vacuum_toroidal_field": {"r0": [r0], "b0": [b0]}, "time_slice": {
            "boundary": {"outline": {"r": rs, "z": zs}},
            "profiles_1d": {"psi_norm": [0., 1.], "dpressure_dpsi": [pp, pp], "f_df_dpsi": [ff, ff]}}}}}
    q0 = math.sqrt((r0*b0)**2+2*ff*pc)*math.pi/(r0*math.sqrt(4*e1*r0*r0*(e2*r0*r0+e3)))
    return plan, {"psi_axis_Wb": pc, "q0": q0, "p_axis_Pa": pp*pc,
                  "formula": "psi=pc-e1*(R^2-R0^2)^2-e2*R^2*Z^2-e3*Z^2", "e2": e2}


def run_case(case_path, artifact_root, run_path, lock):
    case = read(case_path)
    if case.get("case_id") != "EQ-B0-SOLOVEV":
        raise ValueError("此版本尚只实现EQ-B0-SOLOVEV；不能静默替换案例")
    pars = parameters(case["parameters"])
    run = Path(run_path).resolve()
    run.mkdir(parents=True, exist_ok=True)
    write(run / "started.json", {"started_at": time.time()}, exclusive=True)
    status = {"execution": "failed", "numerical": "not_assessed", "physical": "not_assessed"}
    write(run / "status.json", {**status, "execution": "running"})
    try:
        write(run / "case.snapshot.json", case)
        plan, analytic = solovev(pars["nr"])
        write(run / "input.json", plan)
        write(run / "analytic.json", analytic)
        kernel = Kernel(artifact_root, lock)
        write(run / "identity.json", kernel.identity)
        record = kernel.run(plan)
        write(run / "result.json", record)
        facts = {k: v["value"] for k, v in record.get("facts", {}).items()}
        converged = facts.get("converged") == 1
        status.update(execution="completed", numerical="converged" if converged else "not_converged",
                      physical="not_assessed (B0 integration; B1 gates pending)", facts=facts,
                      input_sha256=digest(run / "input.json"), result_sha256=digest(run / "result.json"))
    except Exception as exc:
        status["error"] = str(exc)
    status["ended_at"] = time.time()
    write(run / "status.json", status)
    return status


def save_case(destination, value, roots):
    if not isinstance(value, dict) or set(value) != {"case_id", "parameters"} or value["case_id"] != "EQ-B0-SOLOVEV":
        raise ValueError("未知案例或保存字段")
    parameters(value["parameters"])
    dest = personal(destination, roots)
    dest.parent.mkdir(parents=True, exist_ok=True)
    value = {**value, "origin": {"case_id": value["case_id"], "release": "v0.0.1-alpha-rc3",
                                 "kernel_tag": "v0.0.1-alpha-rc3"}}
    write(dest, value, exclusive=True)
    return str(dest)


def process_identity(pid):
    try:
        proc = Path(f"/proc/{pid}")
        stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        if proc.stat().st_uid != os.getuid() or stat[0] == "Z":
            return None
        return {"start_ticks": stat[19], "group": stat[2], "command": (proc / "cmdline").read_bytes()}
    except (OSError, IndexError):
        return None


def submit(case_path, artifact_root, roots, partition="parallel31", account="liuxj", backend="direct"):
    case_path = personal(case_path, roots)
    case = read(case_path)
    if case.get("case_id") != "EQ-B0-SOLOVEV":
        raise ValueError("不支持的案例")
    parameters(case["parameters"])
    verify_artifacts(artifact_root, read(LOCK_PATH))
    run = case_path.parent / "runs" / (time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10])
    personal(run, roots).mkdir(parents=True, exist_ok=False)
    write(run / "case.snapshot.json", case)
    write(run / "status.json", {"execution": "submitting", "numerical": "not_assessed", "physical": "not_assessed"})
    command = [sys.executable, str(Path(__file__).resolve()), "run", "--case", str(run / "case.snapshot.json"),
               "--artifacts", str(Path(artifact_root).resolve()), "--output", str(run)]
    if backend == "direct":
        token = uuid.uuid4().hex
        command += ["--run-token", token]
        try:
            with (run / "stdout.log").open("xb") as out, (run / "stderr.log").open("xb") as err:
                proc = subprocess.Popen(command, cwd=run, stdout=out, stderr=err,
                                        start_new_session=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            identity = process_identity(proc.pid)
            write(run / "job.json", {"backend": "direct", "pid": proc.pid, "run_token": token,
                  "start_ticks": identity["start_ticks"] if identity else None,
                  "run": str(run), "case": str(case_path), "command": command})
            def collect():
                code = proc.wait()
                status = read(run / "status.json")
                if status["execution"] in ("submitting", "running"):
                    status.update(execution="cancelled" if (run / "cancel-requested.json").exists() else "failed",
                                  error=f"worker exited {code} before writing final status")
                status["process_exit_code"] = code
                write(run / "status.json", status)
            threading.Thread(target=collect, daemon=True).start()
            return {"backend": "direct", "run_id": run.name, "pid": proc.pid, "run": str(run)}
        except Exception as exc:
            write(run / "status.json", {"execution": "submit_failed", "error": str(exc),
                  "numerical": "not_assessed", "physical": "not_assessed"})
            raise
    if backend != "slurm":
        raise ValueError("unknown execution backend")
    args = ["sbatch", "--parsable", "--partition", partition, "--account", account,
            "--cpus-per-task=1", "--mem=4G", "--time=00:15:00", "--chdir", str(run),
            "--output", str(run / "stdout.log"), "--error", str(run / "stderr.log"), "--wrap", shlex.join(command)]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30, check=True)
        job_id = proc.stdout.strip().split(";")[0]
        if not job_id.isdigit():
            raise ValueError("sbatch返回了不可识别的作业号")
        write(run / "job.json", {"job_id": job_id, "run": str(run), "case": str(case_path), "command": command})
        # Worker may start immediately; do not overwrite its running/completed status.
        return {"job_id": job_id, "run": str(run)}
    except Exception as exc:
        write(run / "status.json", {"execution": "submit_failed", "error": str(exc), "numerical": "not_assessed", "physical": "not_assessed"})
        raise


def job_status(run, roots, cancel=False):
    run = personal(run, roots)
    job = read(run / "job.json")
    if job.get("backend") == "direct":
        status = read(run / "status.json")
        identity = process_identity(job["pid"])
        same = bool(identity and identity["start_ticks"] == job["start_ticks"]
                    and identity["group"] == str(job["pid"])
                    and job["run_token"].encode() in identity["command"].split(b"\0"))
        terminal = status["execution"] in ("completed", "failed", "cancelled", "submit_failed")
        if cancel:
            if not terminal and same:
                write(run / "cancel-requested.json", {"requested_at": time.time()})
                os.killpg(job["pid"], signal.SIGTERM)
                status.update(execution="cancelled", numerical="not_assessed", physical="not_assessed")
                write(run / "status.json", status)
                return {"cancel_requested": True, "run": str(run)}
            return {"cancel_requested": False, "reason": "worker is no longer running", "run": str(run)}
        if not terminal and not same:
            status.update(execution="failed", error="worker is no longer running; inspect stdout/stderr")
            write(run / "status.json", status)
        return {**status, "backend": "direct", "run": str(run), "run_id": run.name}
    job_id = job["job_id"]
    if not str(job_id).isdigit():
        raise ValueError("invalid job id")
    status = read(run / "status.json")
    if cancel:
        subprocess.run(["scancel", str(job_id)], check=True, capture_output=True, timeout=15)
        return {"cancel_requested": True, "job_id": job_id}
    try:
        proc = subprocess.run(["sacct", "-n", "-X", "-j", str(job_id), "--format=State,ExitCode", "--parsable2"],
                              capture_output=True, text=True, timeout=15, check=True)
        status["scheduler"] = proc.stdout.strip() or "accounting_pending"
    except (OSError, subprocess.SubprocessError) as exc:
        status["scheduler"] = "unknown"
        status["scheduler_error"] = str(exc)
    status.update(job_id=job_id, run=str(run))
    return status


def verify_install(root):
    root = Path(root).resolve()
    manifest = read(root / "release-manifest.json")
    for name, sha in manifest["files"].items():
        path = root / name
        if not inside(path, root) or digest(path) != sha:
            raise ValueError(f"安装文件缺失或校验失败: {name}")
    kernel = Kernel(root, read(root / "kernel.lock.json"))
    data = ctypes.CDLL(str(root / "lib/libsp.so"))
    version = data.sp_version
    version.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    version.restype = ctypes.c_uint64
    n = version(None, 0)
    buf = ctypes.create_string_buffer(n)
    version(buf, n)
    return {"verified": True, "version": manifest["version"], "files": len(manifest["files"]),
            "kernel_abi": kernel.identity["abi"], "libsp_version": buf.raw.decode().rstrip("\0"),
            "execution_default": manifest["execution_default"], "physical": "not_experimentally_qualified"}


def publish_demo(run, output, lock):
    status = read(run / "status.json")
    identity = read(run / "identity.json")
    case = read(run / "case.snapshot.json")
    if status["execution"] != "completed" or status["numerical"] != "converged":
        raise ValueError("demo必须来自实际完成并收敛的运行")
    if case["case_id"] != "EQ-B0-SOLOVEV" or parameters(case["parameters"])["nr"] != 65:
        raise ValueError("首批示范必须匹配发布case的65²默认参数")
    expected = next(a["sha256"] for a in lock["assets"] if a["name"] == "libfylite.so")
    if identity["libraries"]["libfylite_kernel.so"]["sha256"] != expected:
        raise ValueError("示范内核与发布版本不一致")
    for name in ("input", "result"):
        if digest(run / f"{name}.json") != status[f"{name}_sha256"]:
            raise ValueError(f"示范{name}哈希不匹配")
    demo = output / "demo/EQ-B0-SOLOVEV"
    result = demo / "result"
    result.mkdir(parents=True)
    for name in ("case.snapshot.json", "input.json", "result.json", "analytic.json", "status.json", "identity.json"):
        shutil.copy2(run / name, result / name)
    write(demo / "evidence.json", {"source_run": str(run), "input_sha256": status["input_sha256"],
          "result_sha256": status["result_sha256"], "kernel_sha256": expected,
          "execution": "completed", "numerical": "converged", "physical": "not_experimentally_qualified"})
    source = output / "docs/templates"
    for name in ("index.html", "LEARNING-GUIDE.zh-CN.html", "USAGE.zh-CN.html"):
        text = (source / name).read_text()
        payload = {"result": read(run / "result.json"), "status": status, "analytic": read(run / "analytic.json")}
        text = text.replace("__DEMO_JSON__", json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c"))
        (demo / name).write_text(text)
    # Templates are build-time source, not extra installed user documents.
    shutil.rmtree(source)
    catalog = read(output / "cases/catalogue.json")
    catalog["cases"][0].update(status="native_synthetic_pass", demo="demo/EQ-B0-SOLOVEV/index.html",
                                physical="not_experimentally_qualified")
    write(output / "cases/catalogue.json", catalog)
    definition = read(output / "cases/EQ-B0-SOLOVEV/case.json")
    definition.update(numerical_status="converged", physical_status="not_experimentally_qualified",
                      demo="demo/EQ-B0-SOLOVEV/index.html")
    write(output / "cases/EQ-B0-SOLOVEV/case.json", definition)


def package(output, artifact_root, lock, demo_run=None):
    verify_artifacts(artifact_root, lock)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(PAYLOAD, output, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
    for name in ("apps/fixed-boundary", "server", "bin", "docs/upstream", "licenses", "tests"):
        (output / name).mkdir(parents=True, exist_ok=True)
    shutil.copy2(__file__, output / "apps/fixed-boundary/eq_delivery.py")
    shutil.copytree(Path(artifact_root) / "lib", output / "lib", ignore=shutil.ignore_patterns("fy"), symlinks=True)
    shutil.copy2(Path(artifact_root) / "lib/fy", output / "bin/fy")
    for path in (Path(artifact_root) / "upstream").rglob("*"):
        if path.is_file() and "licenses" in path.parts:
            shutil.copy2(path, output / "licenses" / path.name)
        elif path.is_file() and path.name in ("MANIFEST.json", "VALIDATION.json", "SHA256SUMS", "abi.json", "README.md"):
            shutil.copy2(path, output / "docs/upstream" / path.name)
    for entry, action in (("fylite-eq", None), ("fylite-eq-verify", "verify-install")):
        program = ('#!/usr/bin/env python3\nimport os,sys,runpy\nfrom pathlib import Path\n'
                   'root=Path(__file__).resolve().parents[1]\nos.environ["FYLITE_EQ_ROOT"]=str(root)\n'
                   'sys.dont_write_bytecode=True\n')
        if action:
            program += f'sys.argv=[sys.argv[0],"{action}",*sys.argv[1:]]\n'
        program += 'runpy.run_path(str(root/"apps/fixed-boundary/eq_delivery.py"),run_name="__main__")\n'
        (output / "bin" / entry).write_text(program)
        (output / "bin" / entry).chmod(0o755)
    (output / "server/eq_server.py").write_text(
        'from pathlib import Path\nimport runpy,sys\nroot=Path(__file__).resolve().parents[1]\n'
        'sys.dont_write_bytecode=True\nsys.argv=[sys.argv[0],"serve",*sys.argv[1:]]\n'
        'runpy.run_path(str(root/"apps/fixed-boundary/eq_delivery.py"),run_name="__main__")\n')
    (output / "tests/verify_install.py").write_text(
        'from pathlib import Path\nimport subprocess,sys\n'
        'raise SystemExit(subprocess.call([str(Path(__file__).resolve().parents[1]/"bin/fylite-eq-verify")]))\n')
    acceptance_script = SOURCE / "tests/accept_eq_install.py"
    if acceptance_script.is_file():
        shutil.copy2(acceptance_script, output / "tests/accept_eq_install.py")
    workflow_test = SOURCE / "tests/accept_workflow_94048.py"
    if workflow_test.is_file():
        shutil.copy2(workflow_test, output / "tests/accept_workflow_94048.py")
    if demo_run:
        publish_demo(Path(demo_run), output, lock)
    case_dir = output / "cases/EQ-B0-SOLOVEV"
    write(case_dir / "data-manifest.json", {"schema": "fylite.case-data/1", "source_kind": "analytic",
          "experimental_data": False, "external_inputs": [],
          "generator": {"file": "apps/fixed-boundary/eq_delivery.py", "sha256": digest(__file__), "entry": "solovev"},
          "runtime_input": "each personal run freezes its actual input.json",
          "units": {"R": "m", "Z": "m", "psi": "full-turn Wb", "pressure": "Pa"}})
    definition = read(case_dir / "case.json")
    definition.update(parameters_schema="parameters.schema.json", data_manifest="data-manifest.json",
                      acceptance="acceptance.json")
    write(case_dir / "case.json", definition)
    acceptance = read(case_dir / "acceptance.json")
    acceptance.pop("web_and_slurm", None)
    acceptance.update(execution_backend="direct", browser_acceptance="separate visual walkthrough required",
                      slurm="not used under current user instruction")
    write(case_dir / "acceptance.json", acceptance)
    shutil.copy2(Path(artifact_root) / "artifacts.json", output / "artifacts.json")
    write(output / "kernel.lock.json", lock)
    write(output / "release-manifest.json", {"schema": "fylite.release/1", "version": "v0.0.1-alpha-rc3",
          "kernel_tag": lock["tag"], "execution_default": "direct",
          "validated_scope": "synthetic fixed-boundary native solve" if demo_run else "candidate without validated demo",
          "source_files": {"apps/fixed-boundary/eq_delivery.py": digest(__file__)},
          "files": {str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    return {"output": str(output)}


def serve(artifact_root, roots, port, backend="direct"):
    """One Unix user on localhost, accessed via SSH tunnel; not a multi-user service."""
    token = secrets.token_urlsafe(32)
    sys.path.insert(0, str(PAYLOAD / "apps/workflow"))
    import workflow
    import archive_v3
    def workflow_route(method, route, body, query):
        if route.startswith("archive-"):
            return archive_v3.dispatch(workflow, method, route, body, Path(artifact_root), roots, query)
        return workflow.dispatch(method, route, body, Path(artifact_root), roots, query)
    class Handler(http.server.BaseHTTPRequestHandler):
        def reply(self, data, code=200):
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            try:
                url = urllib.parse.urlsplit(self.path)
                if url.path in ("/", "/index.html", "/fylite", "/fylite/eq"):
                    destination = "/fylite/eq/" if url.path == "/fylite/eq" else "/fylite/"
                    self.send_response(302)
                    self.send_header("Location", destination)
                    self.end_headers()
                    return
                if url.path in ("/fylite/", "/fylite/index.html"):
                    file = PAYLOAD / "portal/index.html"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(file.read_bytes())
                    return
                if url.path.startswith("/fylite/eq/"):
                    url = url._replace(path=url.path[len("/fylite/eq"):])
                if url.path in ("/", "/index.html"):
                    raw = (PAYLOAD / "index.html").read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(raw)
                elif url.path.startswith("/api/workflow/"):
                    self.reply(workflow_route("GET", url.path[len("/api/workflow/"):], None, urllib.parse.parse_qs(url.query)))
                elif url.path == "/api/info":
                    ready, reason = True, None
                    try:
                        verify_artifacts(artifact_root, read(LOCK_PATH))
                    except (OSError, ValueError, KeyError) as exc:
                        ready, reason = False, str(exc)
                    self.reply({"token": token, "artifact_ready": ready, "reason": reason,
                                "backend": backend,
                                "personal_roots": [str(Path(r).expanduser()) for r in roots],
                                "case": read(PAYLOAD / "cases/EQ-B0-SOLOVEV/case.json"),
                                "scope": "single_user_localhost; native/physics validation pending"})
                elif url.path == "/api/status":
                    self.reply(job_status(urllib.parse.parse_qs(url.query)["run"][0], roots))
                elif url.path == "/api/result":
                    run = personal(urllib.parse.parse_qs(url.query)["run"][0], roots)
                    self.reply({"status": job_status(run, roots), "result": read(run / "result.json") if (run / "result.json").is_file() else None,
                                "analytic": read(run / "analytic.json") if (run / "analytic.json").is_file() else None})
                elif url.path == "/workflow.html" or url.path.startswith(("/ui/", "/demo/", "/docs/", "/cases/")):
                    file = (PAYLOAD / urllib.parse.unquote(url.path).lstrip("/")).resolve()
                    if not inside(file, PAYLOAD) or file.suffix not in (".html", ".js", ".css", ".json") or not file.is_file():
                        return self.reply({"error": "unknown resource"}, 404)
                    self.send_response(200)
                    self.send_header("Content-Type", {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                                     ".css": "text/css; charset=utf-8", ".json": "application/json"}[file.suffix])
                    self.end_headers()
                    self.wfile.write(file.read_bytes())
                else:
                    self.reply({"error": "unknown route"}, 404)
            except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
                self.reply({"error": str(exc)}, 400)

        def do_POST(self):
            try:
                if not secrets.compare_digest(self.headers.get("X-FyLite-Token", ""), token):
                    return self.reply({"error": "请从当前页面重新加载会话"}, 403)
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size < 16384:
                    raise ValueError("invalid request size")
                value = json.loads(self.rfile.read(size))
                route = urllib.parse.urlsplit(self.path).path
                if route.startswith("/fylite/eq/"):
                    route = route[len("/fylite/eq"):]
                if route.startswith("/api/workflow/"):
                    self.reply(workflow_route("POST", route[len("/api/workflow/"):], value, {}))
                elif route == "/api/save":
                    self.reply({"path": save_case(value["path"], value["case"], roots)})
                elif route == "/api/open":
                    self.reply(read(personal(value["path"], roots)))
                elif route == "/api/submit":
                    self.reply(submit(value["path"], artifact_root, roots, backend=backend))
                elif route == "/api/cancel":
                    self.reply(job_status(value["run"], roots, cancel=True))
                else:
                    self.reply({"error": "unknown route"}, 404)
            except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError) as exc:
                self.reply({"error": str(exc)}, 400)

        def log_message(self, format, *args):
            # Do not log query strings containing personal paths or session headers.
            pass
    print(f"FyLite EQ: http://127.0.0.1:{port}/fylite/; EQ: /fylite/eq/; single Unix user; SSH tunnel required", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sp = p.add_subparsers(dest="action", required=True)
    imp = sp.add_parser("import-artifacts")
    imp.add_argument("--archive", required=True)
    imp.add_argument("--output", required=True)
    fetch = sp.add_parser("fetch-artifacts")
    fetch.add_argument("--output", required=True)
    for command in ("probe", "run", "package", "serve", "verify-install"):
        sub = sp.add_parser(command)
        sub.add_argument("--artifacts", default=str(SOURCE))
        if command == "run":
            sub.add_argument("--case", required=True)
            sub.add_argument("--output", required=True)
            sub.add_argument("--run-token")
        if command == "package":
            sub.add_argument("--output", required=True)
            sub.add_argument("--demo-run")
        if command == "serve":
            sub.add_argument("--port", type=int, default=8765)
            sub.add_argument("--personal-root", action="append", required=True)
            sub.add_argument("--backend", choices=("direct", "slurm"), default="direct")
    a = p.parse_args(argv)
    lock = read(LOCK_PATH)
    if a.action == "import-artifacts":
        result = import_artifacts(a.archive, a.output, lock)
    elif a.action == "fetch-artifacts":
        result = fetch_artifacts(a.output, lock)
    elif a.action == "probe":
        result = Kernel(a.artifacts, lock).identity
    elif a.action == "verify-install":
        result = verify_install(a.artifacts)
    elif a.action == "run":
        result = run_case(a.case, a.artifacts, a.output, lock)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["execution"] == "completed" and result["numerical"] == "converged" else 2
    elif a.action == "package":
        result = package(a.output, a.artifacts, lock, a.demo_run)
    else:
        serve(a.artifacts, a.personal_root, a.port, a.backend)
        return 0
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
