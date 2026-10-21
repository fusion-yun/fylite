#!/usr/bin/env python3
"""Exercise a real installed native EQ package over localhost HTTP; no Slurm."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--personal-root", required=True)
    ap.add_argument("--record", required=True)
    args = ap.parse_args()
    root, personal, record = [Path(v).resolve() for v in (args.root, args.personal_root, args.record)]
    record.mkdir(parents=True, exist_ok=False)
    # Explicitly selected test account's private calculation directory.
    personal.mkdir(parents=True, exist_ok=True)
    baseline = {str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()}
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log = (record / "server.log").open("xb")
    proc = subprocess.Popen([str(root / "bin/fylite-eq"), "serve", "--personal-root", str(personal),
                             "--backend", "direct", "--port", str(port)], cwd=personal,
                            stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    checks = []
    def fetch(path):
        with urllib.request.urlopen(base + path, timeout=10) as response:
            return response.read()
    def post(path, body, token):
        req = urllib.request.Request(base + path, json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "X-FyLite-Token": token})
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)
    try:
        for _ in range(120):
            try:
                info = json.loads(fetch("/fylite/eq/api/info"))
                break
            except urllib.error.URLError:
                if proc.poll() is not None:
                    raise RuntimeError("server exited; inspect server.log")
                time.sleep(.1)
        else:
            raise RuntimeError("server readiness timeout")
        assert info["artifact_ready"] and info["backend"] == "direct"
        checks.append("installed identity ready; direct backend")
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
            def handle_starttag(self, tag, attrs):
                for key, value in attrs:
                    if key in ("src", "href") and value:
                        self.links.append(value)
        todo, seen = ["/fylite/", "/fylite/eq/index.html"], set()
        while todo:
            path = todo.pop()
            if path in seen:
                continue
            seen.add(path)
            raw = fetch(path)
            if path.endswith((".html", "/")):
                parser = Links()
                parser.feed(raw.decode())
                for link in parser.links:
                    if link.startswith(("#", "http:", "https:")):
                        continue
                    full = urllib.parse.urlsplit(urllib.parse.urljoin(base + path, link))
                    todo.append(full.path)
        checks.append(f"{len(seen)} linked pages/resources available")
        target = personal / "case.json"
        config = {"case_id": "EQ-B0-SOLOVEV", "parameters": {"nr": 33}}
        post("/fylite/eq/api/save", {"path": str(target), "case": config}, info["token"])
        assert post("/fylite/eq/api/open", {"path": str(target)}, info["token"])["parameters"] == {"nr": 33}
        submitted = post("/fylite/eq/api/submit", {"path": str(target)}, info["token"])
        assert submitted["backend"] == "direct" and "job_id" not in submitted
        run = Path(submitted["run"])
        for _ in range(900):
            answer = json.loads(fetch("/fylite/eq/api/result?run=" + urllib.parse.quote(str(run))))
            if answer["status"]["execution"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(.1)
        else:
            raise RuntimeError("native execution timeout")
        assert answer["status"]["execution"] == "completed", answer["status"]
        assert answer["status"]["numerical"] == "converged"
        assert len(answer["result"]["fields"]["grid_r"]["data"]) == 33
        snapshot = json.loads((run / "case.snapshot.json").read_text())
        assert snapshot["parameters"]["nr"] == 33
        assert sha(run / "result.json") == answer["status"]["result_sha256"]
        assert sha(run / "input.json") == answer["status"]["input_sha256"]
        checks.append("personal save/open -> nr33 direct native solve -> status/result/SHA")
        assert not post("/fylite/eq/api/cancel", {"run": str(run)}, info["token"])["cancel_requested"]
        after = {str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()}
        assert baseline == after
        checks.append("installed package and public cases/demo unchanged")
        receipt = {"passed": True, "root": str(root), "personal_case": str(target), "run": str(run),
                   "checks": checks, "execution": "direct", "browser_visual_acceptance": "not_run",
                   "experimental_qualification": "not_granted"}
        (record / "acceptance.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(receipt, ensure_ascii=False))
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        log.close()


if __name__ == "__main__":
    main()
