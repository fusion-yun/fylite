"""动理学反演的输入文件（``fylite:KineticReconInput``）→ 档 X。

一份 JSON，把 KEFIT 一次动理学反演要手改的东西（``third_party/kefit_bundle`` 的流程、``KEFIT_wuxm`` 的 settinglib.m）
收成一处，逐项可关：

1. 诊断逐道置信度 c（磁通环 · 磁探针 · POINT 法拉第 / 线密度 · Thomson）：σ_eff = σ / c，c = 0 即关掉这道，缺省 1。
   与 EFIT 的 FWT 同义（FWT 乘在 1/σ 上）。
2. 边界台基：p′（可选 FF′）多一个 sech² 台基基函数，位置 x、宽 w 给定，幅值自由（KEDGEP · PE_PSIN · PE_WIDTH）。
3. 预设 q0：一行 1/q0 的约束（FWTQA · QVFIT），σ 给在 q0 上。
4. p′ / FF′ 的基：多项式阶数（KPPCUR · KFFCUR）、张力样条（KPPFNC = 6：结点 · 张力）、或直接给定剖面（不拟合）。
5. 电流项：NEO 自举电流 j_bs（内核 ``code/bootstrap``，Redl）与外加电流 j_ext(ψ_N)；每项可当「给定电流」（进 GS 的
   j_pre，拟合只管其余）或当「电流密度约束」（KZEROJ · SIZEROJ · VZEROJ：边缘几处 ⟨J⟩ = j_bs + j_ohm + j_ext）。
   外环：解 → 在解上算 j_bs → 再解，直到 I_bs 与 q0 不再动（ONETWO ↔ EFIT 的来回，这里在一个进程里）。

★★2026-09-26 起档 X 在内核里（``code/kinetic`` 的 ``x.rs``，用户裁定「收敛动理学平衡重构进 rust 内核」）：本文件只管
这份文件本身——缺省键、查错、由测量文档生成模板、读盘；``reconstruct(..., kinetic_input=d)`` 把规范化的文件整份交给内核，
POINT 逐弦置信度（原 ``apply_point``）、拟合设定、电流项与外环都在那边做。

用法：
    kinetic_input.py template PULL.json -o input.json        # 由 pull 的测量文档生成一份缺省输入（各道 c = 1）
    kinetic_input.py run input.json -o result.json           # 跑 M（+K）+ X；结果与 run -o 同一种文档，多一档 X
    kinetic_input.py serve --root DIR                        # 本机回环服务：页面上编辑、保存、运行（见 README §4.7）
"""
from __future__ import annotations

import argparse
import copy
import http.server
import json
import os
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kinetic_recon as K  # noqa: E402

TYPE = "fylite:KineticReconInput"

#: 缺省输入（除 data 与逐道表以外的全部键；template 再按测量文档填上逐道表）
DEFAULTS = {
    "@type": TYPE, "version": 1,
    "data": {"file": None, "time_s": None, "thomson_file": None},
    "magnetics": {"loops": {}, "probes": {}},
    "point": {"on": True, "faraday": [], "density": []},
    "pressure": {"on": True, "source": "thomson", "thomson": [], "profile": {"psin": [], "p": [], "sigma": []},
                 "sigma_floor": 0.05, "psin_max": 0.98, "fast_frac": 0.0, "on_tier": "M"},
    "pedestal": {"on": False, "x": 0.95, "w": 0.03, "ffprime": False},
    "q0": {"on": False, "target": 1.0, "sigma": 0.02},
    "basis": {"pprime": {"mode": "poly", "n": 1, "edge_zero": True, "knots": [0.0, 0.5, 0.9, 1.0], "tension": 1.0,
                         "psin": [], "value": []},
              "ffprime": {"mode": "poly", "n": 2, "edge_zero": True, "knots": [0.0, 0.5, 0.9, 1.0], "tension": 1.0,
                          "psin": [], "value": []}},
    "currents": {"passes": 4, "tol": 0.01, "relax": 0.5,
                 "bootstrap": {"on": False, "use": "constraint", "x": [0.9, 0.925, 0.95, 0.97, 0.99], "weight": 1.0,
                               "zeff": 2.0, "tite": 1.0, "profiles": "thomson", "given": {"psin": [], "ne": [], "te": []}},
                 "external": {"on": False, "use": "source", "psin": [0.0, 0.3, 0.6, 1.0], "j": [1.0, 1.0, 0.2, 0.0],
                              "total_A": 0.0, "x": [], "weight": 1.0}},
    "ip": {"on": False, "sigma_A": 2000.0},
    "curv": 0.0,
    #: 求解器：warm_start = auto（选了样条 / 台基 / 给定剖面时先解普通多项式再从它接着解）· true · false；
    #: condin = 截断的特征值比（空 = 内核缺省 1e8）
    "solver": {"warm_start": "auto", "condin": None},
}


# ================================================================================================ the document

def _merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = {k: copy.deepcopy(v) for k, v in base.items()}
        for k, v in over.items():
            out[k] = _merge(base.get(k), v) if k in base else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def normalize(doc: dict) -> dict:
    """缺省键补齐 + 查错；错的输入拒（写错的键不静默地不起作用）。"""
    if doc.get("@type") not in (None, TYPE):
        raise SystemExit(f"不是动理学反演的输入文件（@type = {doc.get('@type')!r}，要 {TYPE}）")
    unknown = [k for k in doc if k not in DEFAULTS]
    if unknown:
        raise SystemExit(f"输入文件里有不认识的键 {unknown}（认的：{sorted(DEFAULTS)}）")
    d = _merge(DEFAULTS, doc)
    ws = d["solver"]["warm_start"]                      #: 页面的下拉框给字符串
    d["solver"]["warm_start"] = {"true": True, "false": False}.get(ws, ws) if isinstance(ws, str) else ws
    bad = []
    if d["pressure"]["source"] not in ("thomson", "profile", "kfile"):
        bad.append("pressure.source ∈ thomson | profile | kfile")
    if d["pressure"]["on_tier"] not in ("M", "K"):
        bad.append("pressure.on_tier ∈ M | K")
    for w in ("pprime", "ffprime"):
        b = d["basis"][w]
        if b["mode"] not in ("poly", "spline", "fixed"):
            bad.append(f"basis.{w}.mode ∈ poly | spline | fixed")
        if b["mode"] == "poly" and not (1 <= int(b["n"]) <= 6):
            bad.append(f"basis.{w}.n ∈ 1…6")
        if b["mode"] == "spline" and (len(b["knots"]) < 3 or sorted(b["knots"]) != list(b["knots"])):
            bad.append(f"basis.{w}.knots：至少 3 个、递增")
        if b["mode"] == "fixed" and (len(b["psin"]) < 2 or len(b["psin"]) != len(b["value"])):
            bad.append(f"basis.{w}：fixed 要 psin 与 value 等长（≥ 2 点）")
    for k in ("bootstrap", "external"):
        if d["currents"][k]["use"] not in ("source", "constraint"):
            bad.append(f"currents.{k}.use ∈ source | constraint")
    ex = d["currents"]["external"]
    if ex["on"] and (len(ex["psin"]) < 2 or len(ex["psin"]) != len(ex["j"])):
        bad.append("currents.external：psin 与 j 等长（≥ 2 点）")
    if d["solver"]["warm_start"] not in ("auto", True, False):
        bad.append("solver.warm_start ∈ auto | true | false")
    if d["solver"]["condin"] is not None and not float(d["solver"]["condin"]) > 1:
        bad.append("solver.condin > 1（或空）")
    if d["q0"]["on"] and not d["q0"]["sigma"] > 0:
        bad.append("q0.sigma > 0")
    pr = d["pressure"]["profile"]
    if d["pressure"]["on"] and d["pressure"]["source"] == "profile" and (
            len(pr["psin"]) < 3 or not len(pr["psin"]) == len(pr["p"]) == len(pr["sigma"])):
        bad.append("pressure.profile：psin · p · sigma 等长（≥ 3 点）")
    if bad:
        raise SystemExit("输入文件不成立：" + "；".join(bad))
    return d


def template(pull_path: str, lib: "K.Lib | None" = None) -> dict:
    """由 pull 的测量文档生成一份缺省输入：逐道表按装置事实的道名列全、c = 1。"""
    meas, th, _ = K.load_input(pull_path, None, None)
    lib = lib or K.Lib(K.DEFAULT_LIB)
    card, _ = lib.device("east", int(meas["shot"]), meas.get("measurement_chain", "east"))
    mag = card["magnetics"]
    loops = [K._name(x) for x in K._aos(mag.get("flux_loop"))][:len(meas["coils"])]
    probes = [K._name(x) for x in K._aos(mag.get("b_field_pol_probe"))][:len(meas["expmp2"])]
    d = copy.deepcopy(DEFAULTS)
    d["data"] = {"file": os.path.relpath(pull_path, os.getcwd()), "time_s": meas.get("time_s"), "thomson_file": None}
    d["magnetics"]["loops"] = {n: 1.0 for n in loops if n}
    d["magnetics"]["probes"] = {n: 1.0 for n in dict.fromkeys(probes) if n}
    npt = len((meas.get("point") or {}).get("bpolar") or [])
    d["point"]["faraday"], d["point"]["density"] = [1.0] * npt, [1.0] * npt
    d["point"]["on"] = npt > 0
    d["pressure"]["thomson"] = [1.0] * len((th or {}).get("te") or [])
    if th is None:
        d["pressure"]["on"] = bool(meas.get("kinetic_pressure"))
        d["pressure"]["source"] = "kfile"
    return d


def load(path: str) -> tuple[dict, dict, dict | None, dict]:
    """(规范化的输入, 测量, Thomson, 出处)；数据文件路径相对输入文件所在目录。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    d = normalize(raw)
    base = Path(path).resolve().parent
    f = d["data"]["file"]
    if not f:
        raise SystemExit("输入文件没有 data.file（pull 的测量文档）")
    fp = Path(f) if Path(f).is_absolute() else base / f
    tf = d["data"].get("thomson_file")
    tp = None if not tf else str(Path(tf) if Path(tf).is_absolute() else base / tf)
    meas, th, origin = K.load_input(str(fp), d["data"].get("time_s"), tp)
    origin["input_file"] = Path(path).name
    return d, meas, th, origin


def log(msg: str) -> None:
    K.log(msg)


# ================================================================================================ run · serve

def run_file(path: str, lib: "K.Lib | None" = None, **opts) -> dict:
    d, meas, th, origin = load(path)
    return K.reconstruct(meas, th, lib=lib, origin=origin, kinetic_input=d, **opts)


def cmd_template(a) -> int:
    d = template(a.pull, K.Lib(Path(a.lib)) if a.lib else None)
    Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"-> {a.out}")
    return 0


def cmd_run(a) -> int:
    out = run_file(a.input, K.Lib(Path(a.lib)) if a.lib else None, jobs=a.jobs)
    Path(a.out).write_text(json.dumps(K.strict_json(out), ensure_ascii=False, separators=(",", ":")) + "\n",
                           encoding="utf-8")
    log(f"-> {a.out} ({out['seconds']} s)")
    x = out["tiers"].get("X") or {}
    return 0 if x.get("status") == "ok" else 1


class _Handler(http.server.SimpleHTTPRequestHandler):
    """回环服务：静态页（本目录）+ 工作目录下的输入 / 结果文件 + /api/*。只听 127.0.0.1。"""
    root: Path = Path(".")
    lock = threading.Lock()

    def __init__(self, *args, **kw):
        super().__init__(*args, directory=str(HERE), **kw)

    def log_message(self, fmt, *args):
        pass

    def _json(self, code: int, obj) -> None:
        body = json.dumps(K.strict_json(obj), ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _safe(self, name: str) -> Path:
        p = (self.root / name).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise PermissionError(name)
        return p

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/files"):
            files = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*.json") if p.is_file())
            return self._json(200, {"files": files})
        if self.path.startswith("/api/file?name="):
            from urllib.parse import unquote
            try:
                p = self._safe(unquote(self.path.split("=", 1)[1]))
                return self._json(200, json.loads(p.read_text(encoding="utf-8")))
            except Exception as e:                       # noqa: BLE001
                return self._json(404, {"error": str(e)})
        if self.path.startswith("/api/template?pull="):
            from urllib.parse import unquote
            try:
                d = template(str(self._safe(unquote(self.path.split("=", 1)[1]))))
                d["data"]["file"] = os.path.relpath(self._safe(d["data"]["file"]) if not Path(d["data"]["file"]).is_absolute()
                                                    else d["data"]["file"], self.root)
                return self._json(200, d)
            except Exception as e:                       # noqa: BLE001
                return self._json(400, {"error": str(e)})
        if self.path in ("/", ""):
            self.path = "/kinetic_recon.html"
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        try:
            if self.path == "/api/save":
                p = self._safe(body["name"])
                p.write_text(json.dumps(normalize(body["input"]), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                return self._json(200, {"saved": str(p.relative_to(self.root.resolve()))})
            if self.path == "/api/run":
                p = self._safe(body["name"])
                p.write_text(json.dumps(normalize(body["input"]), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                with self.lock:                          #: 一次一个：内核库进程内单例
                    t0 = time.time()
                    out = run_file(str(p))
                res = p.with_name(p.stem + ".result.json")
                res.write_text(json.dumps(K.strict_json(out), ensure_ascii=False, separators=(",", ":")) + "\n",
                               encoding="utf-8")
                out["result_file"] = str(res.relative_to(self.root.resolve()))
                log(f"serve: ran {p.name} in {time.time() - t0:.1f} s -> {res.name}")
                return self._json(200, out)
        except PermissionError as e:
            return self._json(403, {"error": f"不在 --root 之下：{e}"})
        except SystemExit as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:                           # noqa: BLE001
            return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        return self._json(404, {"error": self.path})


def cmd_serve(a) -> int:
    _Handler.root = Path(a.root).resolve()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), _Handler)
    log(f"serving {HERE / 'kinetic_recon.html'} + {_Handler.root} on http://127.0.0.1:{a.port}/ (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kinetic_input.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--lib", help="libfylite_runtime.so 的路径（缺省与 kinetic_recon.py 同目录；内核在它旁边）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template", help="由 pull 的测量文档生成一份缺省输入文件（各道置信度 1）")
    t.add_argument("pull")
    t.add_argument("-o", "--out", required=True)
    r = sub.add_parser("run", help="输入文件 → 结果 JSON（档 M、K 与 X）")
    r.add_argument("input")
    r.add_argument("--jobs", type=int, default=K.JOBS)
    r.add_argument("-o", "--out", required=True)
    s = sub.add_parser("serve", help="本机回环服务：页面上编辑 · 保存 · 运行输入文件")
    s.add_argument("--root", default=".", help="输入 / 测量 / 结果文件所在目录（只读写它下面的文件）")
    s.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    return {"template": cmd_template, "run": cmd_run, "serve": cmd_serve}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
