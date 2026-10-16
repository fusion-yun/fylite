"""配置文件 v2 与批量运行：一份配置（``fylite:KineticReconInput`` v2）→ 多片 × 约束阶梯的结果目录。

    python kinetic_recon.py init --shot 164437 --time 6.72 -o k164437.json
    python kinetic_recon.py run k164437.json [--tiers M,K,P,J] [--slices 6.3,6.72 | 3:8:0.1 | at-thomson --window 3:8]
                                             [--set 键=值 …] [--print-config] [--dry-run] [--jobs N] [--resume out/164437] -o out/
    python kinetic_recon.py validate out/164437 [--checks physics,cross_tier,wdia]

★一个键一个名：配置文件的键、``--set 键=值``、结果里写回的 ``config.resolved.json`` 用同一个点分路径（``presets.core.q0.mode``）；
``--tiers`` · ``--slices`` · ``--window`` · ``--jobs`` 只是这些键的简写。认不出的键按名拒；不成立的组合在跑之前拒（退出码 2）。
★合成次序（后者覆盖前者，每个键记下生效值来自哪一层）：缺省 → 配置文件 → 逐片覆盖（``slices.overrides``）→ ``--set`` → 简写开关。
★不静默地不起作用：配置里要了、今天做不了的项（MSE、q=1 面预设、台基高度……），逐片写进结果的 ``fylite:config.not_executed``，
带原因；档 S 记 ``skipped``；档 J 与预设在档 X（``kinetic_input.py``）里跑，结果里写明在哪一档执行。
★旧的输入文件（v1，``kinetic_input.py`` 的格式）照读：``pedestal`` · ``q0`` 搬到 ``presets`` 下，档 X 专有的细项放进 ``tier_x``。
"""
from __future__ import annotations

import concurrent.futures
import copy
import datetime
import hashlib
import json
import math
import multiprocessing
import os
import sys
import time
from pathlib import Path

import kinetic_recon as K

TYPE = "fylite:KineticReconInput"
BATCH_TYPE = "fylite:KineticReconBatch"
ORDER = ("M", "K", "P", "D", "Q", "S", "J")
#: 基的命名预设：(p′ 阶, FF′ 阶, 建议的最低档, 另要的)——与 kinetic_ladder.html 的 BASIS 同表
BASIS = {"efit-1-2": (1, 2, "M", None), "kefit-2-2": (2, 2, "K", None), "kin-3-2": (3, 2, "P", None),
         "kin-3-3-ped": (3, 3, "P", "pedestal"), "spline-4": (None, None, "S", "spline"), "fixed-p": (None, 2, "P", "fixed")}
CHECKS = ("physics", "cross_tier", "wdia", "sawtooth_q1", "ece_hfs_lfs")

#: ★缺省配置的唯一出处（kinetic_ladder.html 的 cfgDefault() 与它逐键相同；test_config.py 核对）
DEFAULTS = {
    "@type": TYPE, "version": 2,
    "data": {"device": "east", "shot": None, "chain": "east", "server": None, "window_ms": 10, "file": None, "thomson_file": None},
    "slices": {"times_s": [], "range": None, "align": "none", "window": None, "overrides": {}},
    "ladder": {"tiers": ["M", "K", "P"], "fallback": {"P": "D"}, "x": "auto"},
    "magnetics": {"loops_start": "B+readmit", "reject_sigma": 5.0, "loops": {}, "probes": {}},
    "point": {"on": True, "dead_sigma": 8.0},
    "pressure": {"source": "thomson", "sigma_floor": 0.05, "psin_max": 0.98, "fast_frac": 0.0,
                 "wdia": {"value_J": None, "sigma_rel": 0.01, "relax": 1.0}},
    "mse": {"channels": {}, "er_correction": "off"},
    "currents": {"bootstrap": {"role": "prior", "formula": "redl2021", "sigma_rel": None,
                               "x": [0.9, 0.925, 0.95, 0.97, 0.99], "zeff": 2.0, "tite": 1.0, "profiles": "fit"}},
    "presets": {"core": {"q0": {"mode": "free", "target": 1.0, "sigma": 0.05, "basis": "assumed"},
                         "q1": {"on": False, "from": "ece_inversion"}, "p0": {"on": False}, "flat_j": False},
                "pedestal": {"on": False, "x": 0.95, "w": 0.03, "ffprime": False, "p_ped": None, "te_sep_eV": None}},
    "basis": {"preset": "efit-1-2", "npp": 1, "nff": 2},
    "profiles": {"fit": "legendre-gcv"},
    "validation": {"checks": list(CHECKS), "bounds": {}},
    "reference": [],
    "run": {"jobs": 8, "scan": "coarse", "physics_select": False},
    "output": {"dir": "out", "keep_psi": True, "gfile": False},
    "tier_x": {},
}
#: 键下是任意名字的表（道名 · 时刻 · 界值 · 档 X 的细项）：往下不查名字，整块算一个叶子
OPEN = {"magnetics.loops", "magnetics.probes", "mse.channels", "slices.overrides", "validation.bounds", "tier_x",
        "ladder.fallback"}


class ConfigError(SystemExit):
    """配置不成立：退出码 2。"""

    def __init__(self, msg: str):
        super().__init__(2)
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


def log(msg: str) -> None:
    K.log(msg)


# ================================================================================================ keys · merge · origin

def leaves(d: dict, pre: str = "") -> dict:
    """{点分路径: 值}；``OPEN`` 里的键整块算一个叶子。"""
    out = {}
    for k, v in d.items():
        p = f"{pre}.{k}" if pre else k
        if isinstance(v, dict) and p not in OPEN:
            out.update(leaves(v, p))
        else:
            out[p] = v
    return out


def _known(path: str) -> bool:
    """路径在缺省树里（或落在一个 OPEN 表之下）。"""
    parts = path.split(".")
    for i in range(1, len(parts) + 1):
        if ".".join(parts[:i]) in OPEN:
            return True
    node = DEFAULTS
    for p in parts:
        if not isinstance(node, dict) or p not in node:
            return False
        node = node[p]
    return True


def getp(d: dict, path: str):
    for p in path.split("."):
        d = d[p]
    return d


def setp(d: dict, path: str, v) -> None:
    ks = path.split(".")
    for k in ks[:-1]:
        if not isinstance(d.get(k), dict):
            d[k] = {}
        d = d[k]
    d[ks[-1]] = v


def check_keys(doc: dict, where: str) -> None:
    bad = [p for p in leaves(doc) if not _known(p)]
    #: 叶子路径可能停在一个缺省里是 dict 的键上（给了标量）：同样拒
    bad += [p for p, v in leaves(doc).items() if _known(p) and p not in OPEN and not any(p.startswith(o + ".") for o in OPEN)
            and isinstance(_default_at(p), dict)]
    if bad:
        raise ConfigError(f"{where}：认不出的键 {sorted(set(bad))}（键表：kinetic_recon.py init 写出的文件，或 README §4.6）")


def _default_at(path: str):
    try:
        return getp(DEFAULTS, path)
    except (KeyError, TypeError):
        return None


def parse_value(text: str):
    """``--set`` 的值：能读成 JSON 就按 JSON（数 · true · null · [..]），否则是字符串。"""
    try:
        return json.loads(text)
    except ValueError:
        return text


def is_v1(doc: dict) -> bool:
    return doc.get("version") == 1 or ("version" not in doc and ("pedestal" in doc or "q0" in doc or "solver" in doc))


def migrate_v1(doc: dict) -> dict:
    """v1 输入文件（kinetic_input.py）→ v2。共有的键搬到 v2 的位置；档 X 专有的细项原样放进 ``tier_x``。"""
    import kinetic_input as KI
    d = KI.normalize(copy.deepcopy(doc))
    v2 = {"@type": TYPE, "version": 2, "ladder": {"tiers": ["M", "K"] if d["point"]["on"] else ["M"], "x": True},
          "data": {"file": d["data"]["file"], "thomson_file": d["data"].get("thomson_file")},
          "magnetics": {"loops": d["magnetics"]["loops"], "probes": d["magnetics"]["probes"]},
          "point": {"on": d["point"]["on"]},
          "pressure": {"source": d["pressure"]["source"], "sigma_floor": d["pressure"]["sigma_floor"],
                       "psin_max": d["pressure"]["psin_max"], "fast_frac": d["pressure"]["fast_frac"]},
          "presets": {"core": {"q0": {"mode": "prior" if d["q0"]["on"] else "free", "target": d["q0"]["target"],
                                      "sigma": d["q0"]["sigma"]}},
                      "pedestal": {k: d["pedestal"][k] for k in ("on", "x", "w", "ffprime")}}}
    if d["data"].get("time_s") is not None:
        v2["slices"] = {"times_s": [d["data"]["time_s"]]}
    pp, ff = d["basis"]["pprime"], d["basis"]["ffprime"]
    if pp["mode"] == "poly" and ff["mode"] == "poly":
        v2["basis"] = {"npp": int(pp["n"]), "nff": int(ff["n"]), "preset": preset_name(int(pp["n"]), int(ff["n"]))}
    bs = d["currents"]["bootstrap"]
    if bs["on"]:
        v2["ladder"]["tiers"].append("J")
        v2["currents"] = {"bootstrap": {"role": "constraint" if bs["use"] == "constraint" else "source", "x": bs["x"],
                                        "zeff": bs["zeff"], "tite": bs["tite"],
                                        "profiles": "given" if bs["profiles"] == "given" else "fit"}}
    #: 档 X 的细项：v1 里除上面搬走的以外全部原样（KI.normalize 在跑时再查一遍）
    v2["tier_x"] = {k: d[k] for k in ("basis", "currents", "ip", "curv", "solver")}
    v2["tier_x"]["point"] = {"faraday": d["point"]["faraday"], "density": d["point"]["density"]}
    v2["tier_x"]["pressure"] = {k: d["pressure"][k] for k in ("on", "thomson", "profile", "on_tier")}
    return v2


def preset_name(npp, nff) -> str:
    return next((k for k, v in BASIS.items() if v[0] == npp and v[1] == nff and v[3] is None), "custom")


def resolve(doc: dict | None, sets: list | None = None, flags: dict | None = None) -> tuple[dict, dict]:
    """(合成后的配置, {路径: 来源})。来源 ∈ default · file · set · flag（逐片覆盖在 ``slice_config`` 里另记）。"""
    doc = copy.deepcopy(doc or {})
    if doc.get("@type") not in (None, TYPE):
        raise ConfigError(f"不是动理学反演的配置（@type = {doc.get('@type')!r}，要 {TYPE}）")
    if is_v1(doc):
        doc = migrate_v1(doc)
    doc.pop("@type", None)
    doc.pop("version", None)
    check_keys(doc, "配置文件")
    cfg = copy.deepcopy(DEFAULTS)
    origin = {p: "default" for p in leaves(cfg)}
    for p, v in leaves(doc).items():
        setp(cfg, p, copy.deepcopy(v))
        origin[p] = "file"
    for item in sets or []:
        if "=" not in item:
            raise ConfigError(f"--set {item!r}：要写成 键=值")
        p, v = item.split("=", 1)
        p = p.strip()
        if not _known(p) or (isinstance(_default_at(p), dict) and p not in OPEN):
            raise ConfigError(f"--set {p}：认不出的键（键表：kinetic_recon.py init 写出的文件）")
        setp(cfg, p, parse_value(v))
        origin[p] = "set"
    for p, v in (flags or {}).items():
        setp(cfg, p, v)
        origin[p] = "flag"
    before = leaves(cfg)
    normalize(cfg)
    for p, v in leaves(cfg).items():                     #: 规范化推出来的值（基预设定的阶数、台基开关……）
        if before.get(p) != v and p != "ladder.tiers":
            origin[p] = f"derived:{origin.get(p, 'default')}"
    return cfg, origin


def normalize(cfg: dict) -> None:
    """规范化 + 查组合（不成立就 ConfigError）；改的是 cfg 本身。"""
    bad = []
    tiers = cfg["ladder"]["tiers"]
    if isinstance(tiers, str):
        tiers = [x for x in tiers.replace(",", "") if x.strip()]
    tiers = [str(x).upper() for x in tiers]
    unknown = [x for x in tiers if x not in ORDER]
    if unknown:
        bad.append(f"ladder.tiers 里认不出 {unknown}（档：{' '.join(ORDER)}）")
    cfg["ladder"]["tiers"] = [x for x in ORDER if x in tiers or x == "M"]
    tiers = cfg["ladder"]["tiers"]
    if cfg["ladder"]["fallback"] not in ({}, {"P": "D"}, None):
        bad.append("ladder.fallback ∈ {} | {\"P\": \"D\"}")
    cfg["ladder"]["fallback"] = cfg["ladder"]["fallback"] or {}
    if cfg["ladder"]["x"] not in ("auto", True, False):
        bad.append("ladder.x ∈ auto | true | false")
    b = cfg["basis"]
    if b["preset"] not in BASIS and b["preset"] != "custom":
        bad.append(f"basis.preset ∈ {' | '.join(BASIS)} | custom")
    elif b["preset"] in BASIS:
        npp, nff, _, extra = BASIS[b["preset"]]
        b["npp"] = npp if npp is not None else b["npp"]
        b["nff"] = nff if nff is not None else b["nff"]
        if extra == "pedestal":
            cfg["presets"]["pedestal"]["on"] = True
    for k in ("npp", "nff"):
        if not (isinstance(b[k], int) and 1 <= b[k] <= 6):
            bad.append(f"basis.{k} ∈ 1…6（整数）")
    if b["preset"] == "fixed-p" and not ((cfg["tier_x"].get("basis") or {}).get("pprime") or {}).get("psin"):
        bad.append("basis.preset = fixed-p 要给定 p′：tier_x.basis.pprime.psin / value")
    q0 = cfg["presets"]["core"]["q0"]
    if q0["mode"] not in ("free", "prior", "hard"):
        bad.append("presets.core.q0.mode ∈ free | prior | hard")
    if q0["mode"] != "free" and not (isinstance(q0["sigma"], (int, float)) and q0["sigma"] > 0):
        bad.append("presets.core.q0.sigma > 0")
    bs = cfg["currents"]["bootstrap"]
    if bs["role"] not in ("prior", "constraint", "source"):
        bad.append("currents.bootstrap.role ∈ prior | constraint | source")
    if bs["formula"] != "redl2021":
        bad.append("currents.bootstrap.formula：今天只有 redl2021（code/bootstrap 只此一档）")
    if bs["profiles"] not in ("fit", "given"):
        bad.append("currents.bootstrap.profiles ∈ fit | given")
    if "J" in tiers and "P" not in tiers and bs["profiles"] != "given" and cfg["ladder"]["x"] is not True:
        bad.append("档 J 要剖面形状：点名 P（或给 currents.bootstrap.profiles = given 与 tier_x.currents.bootstrap.given）；"
                   "D 只定压强标度，J 不叠在 D 上")
    if cfg["pressure"]["source"] not in ("thomson", "profile", "kfile"):
        bad.append("pressure.source ∈ thomson | profile | kfile")
    if cfg["magnetics"]["loops_start"] not in ("B+readmit", "B", "all"):
        bad.append("magnetics.loops_start ∈ B+readmit | B | all")
    if cfg["run"]["scan"] not in ("coarse", "full"):
        bad.append("run.scan ∈ coarse | full")
    if cfg["data"]["window_ms"] != 10:
        bad.append("data.window_ms 今天固定为 10（W_dia ±10 ms；磁测量 ±5 ms 是归约的常数），不能改")
    if cfg["slices"]["align"] not in ("none", "thomson", "efit"):
        bad.append("slices.align ∈ none | thomson | efit")
    unknown_checks = [c for c in cfg["validation"]["checks"] if c not in CHECKS]
    if unknown_checks:
        bad.append(f"validation.checks 里认不出 {unknown_checks}（{', '.join(CHECKS)}）")
    if cfg["ladder"]["x"] is False and needs_x(cfg):
        bad.append("ladder.x = false，但预设 / 档 J / 逐道置信度 / 样条或给定基 / 非 Thomson 的压强来源都要档 X 才跑得了")
    if cfg["data"]["file"] is None and cfg["data"]["shot"] is None:
        bad.append("没有数据：给 data.shot（经 mdsip 取数）或 data.file（pull 的测量文档）")
    if bad:
        raise ConfigError("配置不成立：" + "；".join(bad))


def needs_x(cfg: dict) -> bool:
    """这份配置要不要档 X（kinetic_input.py）：预设 · 档 J · 逐道置信度 · 样条 / 给定基 · 非 Thomson 压强 · tier_x 细项。"""
    pr = cfg["presets"]
    conf = any(float(v) != 1.0 for v in list(cfg["magnetics"]["loops"].values()) + list(cfg["magnetics"]["probes"].values()))
    return bool(pr["pedestal"]["on"] or pr["core"]["q0"]["mode"] != "free" or "J" in cfg["ladder"]["tiers"] or conf
                or cfg["basis"]["preset"] in ("spline-4", "fixed-p") or cfg["pressure"]["source"] != "thomson"
                or cfg["tier_x"])


# ================================================================================================ slices

def parse_slices(spec, window=None) -> dict:
    """``--slices`` 的写法 → ``slices`` 块的一部分：``6.72`` · ``6.3,6.72`` · ``t0:t1:dt`` · ``at-thomson`` / ``at-efit``
    （后两种要 ``--window t0:t1``，时刻在取数时从树里定）。"""
    s = str(spec).strip()
    if s in ("at-thomson", "at-efit"):
        w = parse_window(window)
        if w is None:
            raise ConfigError(f"--slices {s} 要 --window t0:t1")
        return {"align": s[3:], "window": w, "times_s": [], "range": None}
    if s.count(":") == 2:
        try:
            t0, t1, dt = (float(x) for x in s.split(":"))
        except ValueError:
            raise ConfigError(f"--slices {s!r}：t0:t1:dt 要三个数") from None
        if not (dt > 0 and t1 >= t0):
            raise ConfigError(f"--slices {s!r}：要 dt > 0、t1 ≥ t0")
        return {"align": "none", "range": [t0, t1, dt], "times_s": [], "window": None}
    try:
        ts = [float(x) for x in s.split(",") if x.strip()]
    except ValueError:
        raise ConfigError(f"--slices {s!r}：写法是 6.72 · 6.3,6.72 · t0:t1:dt · at-thomson · at-efit") from None
    if not ts:
        raise ConfigError("--slices 是空的")
    return {"align": "none", "times_s": ts, "range": None, "window": None}


def parse_window(w):
    if w is None:
        return None
    if isinstance(w, (list, tuple)) and len(w) == 2:
        return [float(w[0]), float(w[1])]
    try:
        a, b = (float(x) for x in str(w).split(":"))
    except ValueError:
        raise ConfigError(f"--window {w!r}：写成 t0:t1") from None
    if not b > a:
        raise ConfigError(f"--window {w!r}：t1 要大于 t0")
    return [a, b]


def range_times(r) -> list:
    t0, t1, dt = (float(x) for x in r)
    n = int(math.floor((t1 - t0) / dt + 1e-9)) + 1
    return [round(t0 + k * dt, 9) for k in range(n)]


def slice_times(cfg: dict, files: dict | None = None) -> list | None:
    """配置定下的时刻（排好、去重）；``align`` 要从树里定时刻时返回 None（取数时再定）。"""
    sl = cfg["slices"]
    if sl["align"] != "none":
        return None
    ts = [float(t) for t in sl["times_s"]]
    if sl["range"]:
        ts += range_times(sl["range"])
    if not ts and files:
        ts = sorted(files)
    return sorted({round(t, 6) for t in ts})


def slice_config(cfg: dict, origin: dict, t: float) -> tuple[dict, dict, dict]:
    """(这一片的配置, 来源, 与全局的差)：``slices.overrides`` 里时刻（键写 秒 或 ms 整数）匹配的那一块覆盖上去。"""
    ov = None
    for k, v in (cfg["slices"]["overrides"] or {}).items():
        try:
            tk = float(k)
        except ValueError:
            raise ConfigError(f"slices.overrides 的键 {k!r} 不是时刻") from None
        if tk > 50:                                      #: 写成 ms 整数（6720）
            tk /= 1000.0
        if abs(tk - t) < 5e-4:
            ov = v
    if not ov:
        return cfg, origin, {}
    sc = copy.deepcopy(cfg)
    so = dict(origin)
    diff = {}
    for p, v in (ov.items() if all("." in k or not isinstance(v, dict) for k, v in ov.items()) else leaves(ov).items()):
        if not _known(p) or p.startswith("slices"):
            raise ConfigError(f"slices.overrides[{t}]：认不出的键 {p}（或覆盖 slices 本身）")
        setp(sc, p, copy.deepcopy(v))
        so[p] = f"override:{t:g}"
        diff[p] = v
    normalize(sc)
    return sc, so, diff


def fingerprint(scfg: dict) -> str:
    """这一片的配置指纹（不含 slices · output · validation · reference：它们不改反演的答案）。"""
    core = {k: v for k, v in scfg.items() if k not in ("slices", "output", "validation", "reference")}
    core["run"] = {k: v for k, v in scfg["run"].items() if k != "jobs"}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


# ================================================================================================ plan

def run_options(scfg: dict, jobs: int | None = None) -> dict:
    """这一片 → ``kinetic_recon.reconstruct`` 的关键字（``run_options`` 的键）。"""
    t = scfg["ladder"]["tiers"]
    tiers = "M" + ("K" if "K" in t and scfg["point"]["on"] else "") + ("P" if "P" in t else "") + ("D" if "D" in t else "") + ("Q" if "Q" in t else "")
    o = {"tiers": tiers, "npp": scfg["basis"]["npp"], "nff": scfg["basis"]["nff"],
         "loops": scfg["magnetics"]["loops_start"], "reject_sigma": float(scfg["magnetics"]["reject_sigma"]),
         "dead_sigma": float(scfg["point"]["dead_sigma"]), "psin_max": float(scfg["pressure"]["psin_max"]),
         "sigma_floor": float(scfg["pressure"]["sigma_floor"]), "p_fast_frac": float(scfg["pressure"]["fast_frac"]),
         "wdia_sigma": float(scfg["pressure"]["wdia"]["sigma_rel"]), "wdia_relax": float(scfg["pressure"]["wdia"]["relax"]),
         "scan": scfg["run"]["scan"],
         "physics_select": bool(scfg["run"]["physics_select"]), "jobs": int(jobs or scfg["run"]["jobs"])}
    if scfg["pressure"]["wdia"]["value_J"] is not None:
        o["wdia"] = float(scfg["pressure"]["wdia"]["value_J"])
    if scfg["validation"]["bounds"]:
        o["phys_bounds"] = ",".join(f"{k}={v}" for k, v in scfg["validation"]["bounds"].items())
    return o


def x_input(scfg: dict, with_bootstrap: bool = True, pressure_ok: bool = True) -> dict:
    """这一片 → 档 X 的 v1 输入（kinetic_input.py 的格式；``data`` 不用，测量直接交给 reconstruct）。"""
    import kinetic_input as KI
    tx = copy.deepcopy(scfg["tier_x"])
    d = KI._merge(KI.DEFAULTS, {k: v for k, v in tx.items() if k not in ("point", "pressure")})
    d["point"]["on"] = bool(scfg["point"]["on"] and "K" in scfg["ladder"]["tiers"])
    for k in ("faraday", "density"):
        d["point"][k] = (tx.get("point") or {}).get(k, [])
    d["pressure"] = KI._merge(d["pressure"], tx.get("pressure") or {})
    d["pressure"].update(source=scfg["pressure"]["source"], sigma_floor=scfg["pressure"]["sigma_floor"],
                         psin_max=scfg["pressure"]["psin_max"], fast_frac=scfg["pressure"]["fast_frac"])
    if not pressure_ok:                                  #: Thomson 不可用（档 P 没跑成）：档 X 不收压强行
        d["pressure"]["on"] = False
    d["magnetics"] = {"loops": scfg["magnetics"]["loops"], "probes": scfg["magnetics"]["probes"]}
    pd = scfg["presets"]["pedestal"]
    d["pedestal"] = {"on": bool(pd["on"]), "x": pd["x"], "w": pd["w"], "ffprime": bool(pd["ffprime"])}
    q0 = scfg["presets"]["core"]["q0"]
    d["q0"] = {"on": q0["mode"] != "free", "target": q0["target"], "sigma": q0["sigma"]}
    pre = scfg["basis"]["preset"]
    if pre == "spline-4":
        for w in ("pprime", "ffprime"):
            d["basis"][w].update(mode="spline", knots=[0.0, 0.5, 0.9, 1.0], tension=1.0)
    elif pre == "fixed-p":
        d["basis"]["pprime"]["mode"] = "fixed"
        d["basis"]["ffprime"].update(mode="poly", n=scfg["basis"]["nff"])
    elif not (tx.get("basis")):
        d["basis"]["pprime"].update(mode="poly", n=scfg["basis"]["npp"])
        d["basis"]["ffprime"].update(mode="poly", n=scfg["basis"]["nff"])
    bs = scfg["currents"]["bootstrap"]
    b1 = d["currents"]["bootstrap"]
    b1["on"] = bool(with_bootstrap and "J" in scfg["ladder"]["tiers"])
    if b1["on"]:
        b1.update(use="source" if bs["role"] == "source" else "constraint", x=bs["x"], zeff=bs["zeff"], tite=bs["tite"],
                  profiles="given" if bs["profiles"] == "given" else "thomson")
    d["data"] = {"file": None, "time_s": None, "thomson_file": None}
    return KI.normalize(d)


def plan(scfg: dict) -> dict:
    """这一片要跑什么、在哪一档跑、什么今天做不了（带原因）。不碰数据，不要库。"""
    t = scfg["ladder"]["tiers"]
    opts = run_options(scfg)
    run_x = scfg["ladder"]["x"] is True or (scfg["ladder"]["x"] == "auto" and needs_x(scfg))
    executed, notx = {}, []

    def no(key, why):
        notx.append({"key": key, "why": why})

    executed["M"] = "档 M（磁测量）"
    if "K" in t:
        executed["K"] = "档 K（+ POINT 法拉第）" if scfg["point"]["on"] else None
        if not scfg["point"]["on"]:
            no("ladder.tiers.K", "point.on = false：档 K 不跑")
    if "P" in t:
        executed["P"] = "档 P（+ Thomson 压强）" + ("；跑不成而有 W_dia 时档 D 顶替" if scfg["ladder"]["fallback"] else "")
    if "D" in t:
        executed["D"] = "档 D（W_dia 定压强标度）"
    if "Q" in t:
        executed["Q"] = "档 Q（锯齿反转半径定 q=1 面：一行 q=1 面内电流，叠在 K 上，K 没跑成则 M）"
    if "S" in t:
        no("ladder.tiers.S", "内核没有 MSE 行族：档 S 记 skipped（带 MSE 的 EFIT 只能作对照：reference）")
    if "J" in t:
        executed["J"] = ("档 X：自举电流（Redl-2021）" + ("作给定电流" if scfg["currents"]["bootstrap"]["role"] == "source"
                                                        else "按边缘 ⟨J⟩ 约束行") + "；档 J 本身记 skipped（先验块还没有）")
        if scfg["currents"]["bootstrap"]["role"] == "prior":
            no("currents.bootstrap.role", "prior（带 σ 的先验块）还没有：按约束行（constraint）跑")
    if scfg["currents"]["bootstrap"]["sigma_rel"] is not None:
        no("currents.bootstrap.sigma_rel", "自举电流的 σ 还没有模型：约束行按 weight 1")
    pr = scfg["presets"]
    if pr["core"]["q0"]["mode"] != "free":
        executed["presets.core.q0"] = f"档 X：q₀ 目标 {pr['core']['q0']['target']} ± {pr['core']['q0']['sigma']}（一行约束）"
        if pr["core"]["q0"]["mode"] == "hard":
            no("presets.core.q0.mode", "hard（第二条等式）还没有：按 prior 跑，依据 assumed")
    if pr["pedestal"]["on"]:
        executed["presets.pedestal"] = f"档 X：sech² 台基基 x {pr['pedestal']['x']} · w {pr['pedestal']['w']}"
    for key, on, why in (("presets.core.q1.on", pr["core"]["q1"]["on"], "q=1 面约束行没有 code（还要 ECE / SXR 反转半径）"),
                         ("presets.core.p0.on", pr["core"]["p0"]["on"], "芯部 p(0) 约束行没有 code"),
                         ("presets.core.flat_j", pr["core"]["flat_j"], "q=1 面内电流展平没有 code"),
                         ("presets.pedestal.p_ped", pr["pedestal"]["p_ped"] is not None, "台基高度约束行没有 code"),
                         ("presets.pedestal.te_sep_eV", pr["pedestal"]["te_sep_eV"] is not None, "分离面 Tₑ 对齐没有 code"),
                         ("mse.channels", bool(scfg["mse"]["channels"]), "内核没有 MSE 行族"),
                         ("mse.er_correction", scfg["mse"]["er_correction"] != "off", "内核没有 MSE 行族"),
                         ("profiles.fit", scfg["profiles"]["fit"] != "legendre-gcv", "档 P 直接收逐点压强；剖面拟合预设只在档 X 的自举剖面上有 Legendre-GCV 一种"),
                         ("output.gfile", scfg["output"]["gfile"], "应用今天不写 g-file")):
        if on:
            no(key, why)
    conf = [n for n, v in list(scfg["magnetics"]["loops"].items()) + list(scfg["magnetics"]["probes"].items()) if float(v) != 1.0]
    if conf:
        executed["magnetics.confidence"] = f"档 X：{len(conf)} 道置信度 ≠ 1（阶梯 M · K · P 按缺省权）"
    if scfg["basis"]["preset"] in ("spline-4", "fixed-p"):
        executed["basis.preset"] = f"档 X：{scfg['basis']['preset']}（阶梯 M · K · P 用 poly {scfg['basis']['npp']} / {scfg['basis']['nff']}）"
    if scfg["pressure"]["source"] != "thomson":
        executed["pressure.source"] = f"档 X：压强来源 {scfg['pressure']['source']}（阶梯的档 P 只收 Thomson）"
    top = max(("MKPDQSJ".index(x) for x in t), default=0)
    mn = BASIS.get(scfg["basis"]["preset"], (None, None, "M", None))[2]
    warn = []
    if "MKPDQSJ".index(mn) > top:
        warn.append(f"基 {scfg['basis']['preset']} 的建议最低档是 {mn}，所开的最高档是 {'MKPDQSJ'[top]}：多出的系数定不住（照跑）")
    return {"tiers": t, "run_options": opts, "x": run_x, "executed": {k: v for k, v in executed.items() if v},
            "not_executed": notx, "warnings": warn}


# ================================================================================================ data

class Data:
    """一炮的测量：离线（``data.file``：一份或几份 pull 的测量文档）或经 mdsip（磁测量整段读一次、逐片归约）。"""

    def __init__(self, cfg: dict, base: Path, lib=None, timeout: float = 120.0):
        self.cfg, self.lib, self.timeout = cfg, lib, timeout
        self.files: dict = {}
        self.msrc = None
        self.shot_cache = None
        f = cfg["data"]["file"]
        if f:
            for p in ([f] if isinstance(f, str) else list(f)):
                fp = Path(p) if Path(p).is_absolute() else base / p
                if not fp.exists():
                    raise ConfigError(f"data.file {p}：文件不在（相对配置文件所在目录）")
                th_f = cfg["data"]["thomson_file"]
                tp = None if not th_f else str(Path(th_f) if Path(th_f).is_absolute() else base / th_f)
                meas, th, origin = K.load_input(str(fp), None, tp)
                if cfg["data"]["shot"] is not None and int(meas["shot"]) != int(cfg["data"]["shot"]):
                    raise ConfigError(f"data.file {p} 是 #{meas['shot']}，配置写的是 #{cfg['data']['shot']}")
                self.files[round(float(meas["time_s"]), 6)] = (meas, th, origin)
            shots = {int(m["shot"]) for m, _, _ in self.files.values()}
            if len(shots) != 1:
                raise ConfigError(f"data.file 里不止一炮：{sorted(shots)}")
            self.shot = shots.pop()
        else:
            self.shot = int(cfg["data"]["shot"])

    def times(self, cfg: dict) -> list:
        ts = slice_times(cfg, self.files)
        if ts is None:
            ts = self.aligned(cfg["slices"]["align"], cfg["slices"]["window"])
        if not ts:
            raise ConfigError("一片都没有：给 slices.times_s / --slices，或 data.file")
        if self.files:
            miss = [t for t in ts if not any(abs(t - tf) < 5e-4 for tf in self.files)]
            if miss:
                raise ConfigError(f"离线（data.file）只有 {sorted(self.files)} s 这几片，没有 {miss}")
        return ts

    def aligned(self, align: str, window) -> list:
        if self.files:
            raise ConfigError(f"slices.align = {align} 要从树里定时刻：离线（data.file）时用 times_s")
        if window is None:
            raise ConfigError(f"slices.align = {align} 要 slices.window / --window t0:t1")
        lib = self._lib()
        host, port = K.server_of(self.cfg["data"]["server"])
        s = lib.mds_open(host, port, self.timeout)
        try:
            if align == "thomson":
                s.open_tree("ts_east", self.shot)
                te2 = s.rows(r"\TE_CORETS")
                nch = len(s.read("data", r"\Z_CORETS")[0])
                w = len(te2[0]) if te2 else 0
                tb = [row[0] for row in te2] if w == nch + 1 else list(s.read("dim_of", r"\TE_CORETS")[0])
            else:
                doc, _ = lib.device("east", self.shot, self.cfg["data"]["chain"])
                tb = K.EquilibriumSeries(s, K.eq_signals(doc, None), "efit", self.shot).tb
        finally:
            s.close()
        ts = [round(float(x), 6) for x in tb if window[0] <= x <= window[1]]
        log(f"config: {len(ts)} slice(s) at {align} times in [{window[0]}, {window[1]}] s")
        return ts

    def _lib(self):
        if self.lib is None:
            raise ConfigError("要库（--lib）")
        return self.lib

    def at(self, t: float) -> tuple[dict, dict | None, dict, dict]:
        """(平坦测量, Thomson 或 None, 出处, 取不到的 {块: 原因})。"""
        if self.files:
            k = min(self.files, key=lambda x: abs(x - t))
            meas, th, origin = self.files[k]
            return copy.deepcopy(meas), copy.deepcopy(th), dict(origin), {}
        lib, chain, server = self._lib(), self.cfg["data"]["chain"], self.cfg["data"]["server"]
        errors = {}
        if self.msrc is None:
            t0 = time.time()
            self.msrc = K.MagneticsSource(lib, self.shot, chain, server, self.timeout)
            try:
                self.msrc.prefetch(point=True)
            finally:
                self.msrc.close()
            log(f"config: #{self.shot} magnetics / PF / Ip / TF / POINT read once ({time.time() - t0:.1f} s)")
        meas = self.msrc.at(t)
        #: ★W_dia · sawtooth · Thomson through one remembering session for the whole batch (FYL-REPORT-11 O-1a):
        #: the same calls as before, each whole-shot array read once instead of once per slice
        if self.shot_cache is None:
            self.shot_cache = K.ShotCache(lib)
        lib = self.shot_cache
        try:
            wd, wsrc = K.pull_w_dia(lib, self.shot, t, chain, server, self.timeout)
            meas.update(w_dia_J=wd, w_dia_source=wsrc)
        except Exception as e:                           # noqa: BLE001 — 取不到只记下
            errors["w_dia"] = K.sanitize(str(e))[:200]
        try:
            import kinetic_sawtooth
            meas["sawtooth"] = kinetic_sawtooth.pull_sawtooth(lib, self.shot, t, chain, server, self.timeout)
        except Exception as e:                           # noqa: BLE001
            errors["sawtooth"] = K.sanitize(str(e))[:300]
        th = None
        try:
            th = K.pull_thomson(lib, self.shot, t, server, self.timeout)
        except Exception as e:                           # noqa: BLE001
            errors["thomson"] = K.sanitize(str(e))[:300]
        return meas, th, {"kind": "mdsip", "shot": self.shot}, errors


# ================================================================================================ run

def _main_tier(res: dict):
    best = None
    for k in ("M", "K", "P", "D", "Q", "X"):
        t = (res.get("tiers") or {}).get(k) or {}
        if t.get("status") in ("ok", "unphysical"):
            best = k
    return best


def run_slice(lib, data: Data | None, t: float, scfg: dict, pl: dict, jobs: int | None, got=None) -> dict:
    """一片：阶梯（M · K · P · D）一次；要档 X 就另跑一次（带输入文件），把 X 并进来；S · J 按计划记。
    ``got``：已经取好的 ``data.at(t)``（批处理先逐片取数、再并行算，FYL-REPORT-11 O-2b）；缺省当场取。"""
    meas, th, origin, errors = got if got is not None else data.at(t)
    opts = run_options(scfg, jobs)
    res = K.reconstruct(meas, th, lib=lib, origin=origin, **opts)
    tiers = res["tiers"]
    rx = None                                            #: 档 X 那一次的记录（要档 X 时）
    if not scfg["ladder"]["fallback"] and (tiers.get("D") or {}).get("fallback_for") == "P":
        tiers.pop("D")
        pl["not_executed"].append({"key": "ladder.fallback", "why": "配置关了 D 顶替：顶替跑出的档 D 已丢弃"})
    p_ok = (tiers.get("P") or {}).get("status") in ("ok", "unphysical")
    if pl["x"]:
        bs = "J" in scfg["ladder"]["tiers"] and (p_ok or scfg["currents"]["bootstrap"]["profiles"] == "given"
                                                 or ("P" not in scfg["ladder"]["tiers"] and scfg["ladder"]["x"] is True))
        if "J" in scfg["ladder"]["tiers"] and not bs:
            tiers["J"] = {"status": "skipped", "why": "档 P 没跑成：D 只有压强标度、没有剖面形状，自举电流算不了"}
            pl["executed"].pop("J", None)
            pl["not_executed"].append({"key": "ladder.tiers.J", "why": tiers["J"]["why"]})
        others = pl["executed"].keys() - {"M", "K", "P", "D", "J"}
        if bs or others:
            p_rows = p_ok or scfg["pressure"]["source"] != "thomson" or ("P" not in scfg["ladder"]["tiers"] and th is not None)
            if not p_rows:
                pl["not_executed"].append({"key": "tier_x.pressure", "why": "Thomson 不可用：档 X 不收压强行（只磁测量 · POINT · 预设）"})
            try:
                rx = K.reconstruct(meas, th, lib=lib, origin=origin, kinetic_input=x_input(scfg, bs, p_rows),
                                   **{k: v for k, v in opts.items() if k not in ("tiers",)})
                tiers["X"] = rx["tiers"].get("X") or {"status": "error", "error": "档 X 没有结果"}
            except (SystemExit, RuntimeError, K.KernelError, K.Refused) as e:
                tiers["X"] = {"status": "error", "error": K.sanitize(f"{type(e).__name__}: {e}")[:300]}
                log(f"config: tier X failed — {tiers['X']['error']}")
            if bs:
                tiers["J"] = {"status": "skipped", "executed_in": "X",
                              "why": "档 J 作带 σ 的先验块还没有；自举电流已在档 X 里跑（tiers.X）"}
    if "S" in scfg["ladder"]["tiers"]:
        tiers["S"] = {"status": "skipped", "why": "内核没有 MSE 行族"}
    if "X" in tiers:                                     #: 档 X 并进来了：它的锯齿判读取自档 X 那一次（内核逐档判读，与别档无关）
        sx = ((rx.get("sawtooth") or {}).get("tiers") or {}).get("X") if rx else None
        if sx is not None:
            res.setdefault("sawtooth", {}).setdefault("tiers", {})["X"] = sx
    res["fylite:config"] = {"slice_config_sha256": fingerprint(scfg), "tiers": scfg["ladder"]["tiers"],
                            "executed": pl["executed"], "not_executed": pl["not_executed"], "warnings": pl["warnings"],
                            "fetch_errors": errors}
    return res


def validation(res: dict, checks) -> dict:
    """留出校验（只读结果）：解的物理校验 · 跨档 β_p + l_i(1)/2 · W/W_dia；锯齿 q=1 面与 ECE 高低场侧没有测量 → unevaluated。
    阈值没量过的只报读数（verdict = reading）。"""
    out = {"@type": "fylite:KineticReconValidation", "shot": res.get("shot"), "time_s": res.get("time_s"), "checks": []}
    tiers = res.get("tiers") or {}
    mk = _main_tier(res)

    def nums(t):
        sr = ((t or {}).get("physics_check") or {}).get("same_ruler") or {}
        return sr if (t or {}).get("status") in ("ok", "unphysical") else None

    for c in checks:
        if c == "physics":
            pcs = {k: t["physics_check"] for k, t in tiers.items() if isinstance(t, dict) and t.get("physics_check")}
            bad = {k: v.get("failed") for k, v in pcs.items() if not v.get("passed")}
            out["checks"].append({"id": c, "verdict": "fail" if bad else "pass" if pcs else "unevaluated",
                                  "detail": bad or sorted(pcs)})
        elif c == "cross_tier":
            lam = {k: n["betap"] + n["li1"] / 2 for k in ("M", "K", "P", "D", "Q", "X")
                   if (n := nums(tiers.get(k))) and K.fin(n.get("betap")) and K.fin(n.get("li1"))}
            out["checks"].append({"id": c, "verdict": "reading" if len(lam) >= 2 else "unevaluated",
                                  "values": {k: round(v, 5) for k, v in lam.items()},
                                  "spread": round(max(lam.values()) - min(lam.values()), 5) if len(lam) >= 2 else None,
                                  "note": "阈值未量过：只报读数"})
        elif c == "wdia":
            wd = (res.get("inputs") or {}).get("w_dia_J")
            n = nums(tiers.get(mk)) if mk else None
            used = mk == "D" or (tiers.get(mk) or {}).get("on") == "D"
            if wd is None or not n:
                out["checks"].append({"id": c, "verdict": "unevaluated", "note": "没有 W_dia 或没有解"})
            else:
                w = n.get("w_mhd_J")
                out["checks"].append({"id": c, "verdict": "inconclusive" if used else "reading", "tier": mk,
                                      "ratio": round(w / wd, 5) if K.fin(w) and wd else None,
                                      "note": "档 D 用它定了标度：除名" if used else "阈值未量过；档 P 只含热压"})
        elif c == "sawtooth_q1":
            sa = res.get("sawtooth") or {}
            tv = (sa.get("tiers") or {}).get(mk) if mk else None
            if not sa or not tv:
                out["checks"].append({"id": c, "verdict": "unevaluated", "note": sa.get("why") or "结果里没有锯齿判读"})
            else:
                inv = sa.get("inversion") or {}
                out["checks"].append({"id": c, "verdict": tv["verdict"], "tier": mk, "note": tv.get("why"),
                                      "r_inv": inv.get("r_inv"), "r_q1_lfs": tv.get("r_q1_lfs"), "dr_m": tv.get("dr_m"),
                                      "tol_m": sa.get("tol_m"), "n_crashes": (sa.get("crashes") or {}).get("n"),
                                      "by_tier": {k: v["verdict"] for k, v in (sa.get("tiers") or {}).items()}})
        else:
            out["checks"].append({"id": c, "verdict": "unevaluated", "note": "ECE 只有低场侧的道：高低场侧对称性查不了"})
    #: 磁相容性（每档对档 M 的 χ²_mag/行）与主显示档的留出集：结果里有（annotate_ladder）才写，只报读数
    compat = {k: t["facts"]["compat_mag_vs_M"] for k, t in tiers.items()
              if isinstance(t, dict) and K.fin(((t.get("facts") or {}).get("compat_mag_vs_M")))}
    if compat:
        out["checks"].append({"id": "compat_mag", "verdict": "reading", "values": compat,
                              "note": "χ²_mag/行 对档 M 之比；阈值未量过：只报读数（> 1 = 加的块把磁测量拉开了）"})
    if mk and (tiers.get(mk) or {}).get("held_out") is not None:
        out["held_out"] = {"tier": mk, "items": tiers[mk]["held_out"]}
    return out


def _tier_status(res: dict) -> dict:
    return {k: (t or {}).get("status") for k, t in (res.get("tiers") or {}).items()}


def index_row(t: float, res: dict | None, err: str | None, seconds: float | None, reused: bool) -> dict:
    row = {"time_s": t, "dir": f"t{round(t * 1000):05d}", "reused": reused}
    if res is None:
        return dict(row, status="error", error=err, tiers={}, seconds=seconds)
    mk = _main_tier(res)
    tv = (res["tiers"].get(mk) or {}) if mk else {}
    sr = (tv.get("physics_check") or {}).get("same_ruler") or {}
    f = tv.get("facts") or {}
    row.update(status=tv.get("status") or "error", main_tier=mk, tiers=_tier_status(res), seconds=res.get("seconds"),
               facts={"q0": f.get("q0"), "q95": f.get("q95"), "li1": sr.get("li1"), "betap": sr.get("betap"),
                      "w_mhd_J": sr.get("w_mhd_J"), "w_dia_J": (res.get("inputs") or {}).get("w_dia_J"),
                      "chi2_per_dof": f.get("chi2_per_dof")},
               not_executed=[x["key"] for x in (res.get("fylite:config") or {}).get("not_executed", [])])
    if not mk:
        row["error"] = (res["tiers"].get("M") or {}).get("error") or (res["tiers"].get("M") or {}).get("why")
    elif tv.get("status") == "unphysical":
        row["physics_failed"] = (tv.get("physics_check") or {}).get("failed")
    return row


def _write(path: Path, obj, indent=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(K.strict_json(obj), ensure_ascii=False, indent=indent,
                               separators=None if indent else (",", ":")) + "\n", encoding="utf-8")


#: the batch's slices for the forked workers: (lib, jobs, [(t, scfg, pl, got)]); set before the pool forks
_BATCH = None


def _slice_worker(i: int):
    """One slice in a forked worker: ``("ok", result, pl)`` or ``("error", message, None)``."""
    lib, jobs, items = _BATCH
    t, scfg, pl, got = items[i]
    t0 = time.time()
    try:
        return "ok", run_slice(lib, None, t, scfg, pl, jobs, got=got), pl
    except (K.KernelError, K.Refused, RuntimeError, SystemExit, ValueError, KeyError) as e:
        return "error", K.sanitize(f"{type(e).__name__}: {e}")[:400], round(time.time() - t0, 1)


def slice_workers(n_slices: int, jobs: int) -> int:
    """How many slices run at once: the CPUs divided by the threads one slice's tier-M scan uses (``jobs``), so the
    machine is filled and not oversubscribed; ``$EKR_BATCH_WORKERS`` overrides (1 = serial, in-process).
    ★``jobs`` itself is not changed: it is part of every record (``settings.jobs``), so the records are the same as
    a serial run's (FYL-REPORT-11 O-2b)."""
    env = os.environ.get("EKR_BATCH_WORKERS")
    if env:
        return max(1, min(n_slices, int(env)))
    return max(1, min(n_slices, (os.cpu_count() or 1) // max(1, jobs)))


def run_batch(cfg: dict, origin: dict, *, base: Path, out_root: Path, lib=None, jobs: int | None = None,
              dry_run: bool = False, resume: Path | None = None, timeout: float = 120.0, printer=print) -> int:
    if lib is None and not dry_run:
        lib = K.Lib(K.DEFAULT_LIB)
    data = Data(cfg, base, lib, timeout)
    if dry_run and cfg["slices"]["align"] != "none" and not data.files:
        pl = plan(cfg)
        printer(f"#{data.shot} · 时刻在取数时定（slices.align = {cfg['slices']['align']}，窗 {cfg['slices']['window']}）")
        for k, v in pl["executed"].items():
            printer(f"    跑   {k}: {v}")
        for x in pl["not_executed"]:
            printer(f"    不跑 {x['key']}: {x['why']}")
        return 0
    times = data.times(cfg)
    shot = data.shot
    per = []
    for t in times:
        scfg, so, diff = slice_config(cfg, origin, t)
        per.append((t, scfg, so, diff, plan(scfg)))
    if dry_run:
        printer(f"#{shot} · {len(times)} 片 · 输出 {out_root / str(shot)}")
        for t, scfg, _, diff, pl in per:
            ro = pl["run_options"]
            printer(f"\n{t:.4f} s  阶梯 {' '.join(pl['tiers'])} → reconstruct(tiers={ro['tiers']}, npp={ro['npp']}, nff={ro['nff']}, "
                    f"reject_sigma={ro['reject_sigma']}, psin_max={ro['psin_max']}, wdia_sigma={ro['wdia_sigma']})"
                    + ("  + 档 X（kinetic_input.py）" if pl["x"] else "") + (f"  逐片覆盖 {diff}" if diff else ""))
            for k, v in pl["executed"].items():
                printer(f"    跑   {k}: {v}")
            for x in pl["not_executed"]:
                printer(f"    不跑 {x['key']}: {x['why']}")
            for w in pl["warnings"]:
                printer(f"    ⚠ {w}")
        return 0
    odir = (resume or out_root / str(shot))
    odir.mkdir(parents=True, exist_ok=True)
    _write(odir / "config.resolved.json",
           {"@type": TYPE, "version": 2, "config": cfg, "origin": origin,
            "slices": {f"{t:g}": {"overrides": diff, "sha256": fingerprint(scfg)} for t, scfg, _, diff, _ in per}}, indent=1)
    rows = []
    todo = []                                        #: (i, t, scfg, diff, pl, got | error, fetch seconds)
    for i, (t, scfg, so, diff, pl) in enumerate(per):
        sd = odir / f"t{round(t * 1000):05d}"
        rp = sd / "result.json"
        if resume and rp.exists():
            try:
                old = json.loads(rp.read_text(encoding="utf-8"))
                if (old.get("fylite:config") or {}).get("slice_config_sha256") == fingerprint(scfg):
                    log(f"config: [{i + 1}/{len(per)}] {t:.4f} s unchanged — kept")
                    rows.append(index_row(t, old, None, old.get("seconds"), True))
                    continue
            except ValueError:
                pass
        #: ★fetch serially here (the shot cache makes every slice after the first cheap), compute below in
        #: parallel — the kernel's thread pool is never started in this process before the fork
        t0 = time.time()
        try:
            got = data.at(t)
        except (K.KernelError, K.Refused, RuntimeError, SystemExit, ValueError, KeyError) as e:
            got = K.sanitize(f"{type(e).__name__}: {e}")[:400]
        todo.append((i, t, scfg, diff, pl, got, round(time.time() - t0, 1)))

    def finish(i, t, scfg, diff, res, err, seconds):
        sd = odir / f"t{round(t * 1000):05d}"
        if err is not None:
            log(f"config: {t:.4f} s FAILED — {err}")
            rows.append(index_row(t, None, err, seconds, False))
            return
        if diff:
            res["fylite:config"]["overrides"] = diff
        _write(sd / "result.json", res)
        _write(sd / "validation.json", validation(res, scfg["validation"]["checks"]), indent=1)
        refs = [r for r in scfg["reference"] if r.get("gfile")]
        srcs = [r["source"] for r in scfg["reference"] if r.get("source")]
        if refs or srcs:
            try:
                cmp = K.compare(res, lib=lib, sources=",".join(srcs), server=scfg["data"]["server"],
                                result_name="result.json",
                                refs=[{"gfile": str(Path(r["gfile"]) if Path(r["gfile"]).is_absolute() else base / r["gfile"]),
                                       "afile": r.get("afile"), "label": r.get("label")} for r in refs])
                _write(sd / "compare.json", cmp)
            except (SystemExit, K.KernelError, RuntimeError, OSError) as e:
                _write(sd / "compare.json", {"error": K.sanitize(str(e))[:300]})
        rows.append(index_row(t, res, None, res.get("seconds"), False))

    ready = [x for x in todo if not isinstance(x[5], str)]
    for i, t, scfg, diff, pl, got, sec in todo:
        if isinstance(got, str):
            finish(i, t, scfg, diff, None, got, sec)
    run_jobs = int(jobs or cfg["run"]["jobs"])
    nw = slice_workers(len(ready), run_jobs)
    for i, t, scfg, diff, pl, got, sec in ready:
        log(f"config: [{i + 1}/{len(per)}] {t:.4f} s — tiers {''.join(pl['tiers'])}" + (" + X" if pl["x"] else ""))
    if nw <= 1:
        for i, t, scfg, diff, pl, got, sec in ready:
            t0 = time.time()
            try:
                res, err = run_slice(lib, data, t, scfg, pl, jobs, got=got), None
            except (K.KernelError, K.Refused, RuntimeError, SystemExit, ValueError, KeyError) as e:
                res, err = None, K.sanitize(f"{type(e).__name__}: {e}")[:400]
            finish(i, t, scfg, diff, res, err, round(time.time() - t0, 1))
    else:
        global _BATCH
        _BATCH = (lib, jobs, [(t, scfg, pl, got) for i, t, scfg, diff, pl, got, sec in ready])
        log(f"config: {len(ready)} slice(s) on {nw} worker process(es) × {run_jobs} thread(s)")
        try:
            with concurrent.futures.ProcessPoolExecutor(nw, mp_context=multiprocessing.get_context("fork")) as ex:
                futs = {ex.submit(_slice_worker, k): k for k in range(len(ready))}
                for f in concurrent.futures.as_completed(futs):
                    i, t, scfg, diff, pl, got, sec = ready[futs[f]]
                    kind, val, extra = f.result()
                    if kind == "ok":
                        #: the worker's plan edits (what ran, what did not) come back with it
                        pl.update(extra)
                        finish(i, t, scfg, diff, val, None, None)
                    else:
                        finish(i, t, scfg, diff, None, val, extra)
        finally:
            _BATCH = None
    rows.sort(key=lambda r: r["time_s"])
    st = [r["status"] for r in rows]
    idx = {"@type": BATCH_TYPE, "app": K.APP, "version": K.VERSION, "shot": shot,
           "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "comment": "批量：片 × 约束阶梯。含实验数据派生量：不入仓。", "config": "config.resolved.json",
           "tiers": cfg["ladder"]["tiers"], "slices": rows,
           "summary": {"n": len(rows), "n_ok": st.count("ok"), "n_unphysical": st.count("unphysical"),
                       "n_error": sum(1 for s in st if s not in ("ok", "unphysical")),
                       "n_reused": sum(1 for r in rows if r["reused"])}}
    _write(odir / "index.json", idx, indent=1)
    log(f"-> {odir}/index.json ({idx['summary']})")
    if idx["summary"]["n_error"]:
        return 1
    return 3 if idx["summary"]["n_unphysical"] else 0


# ================================================================================================ CLI

def _parse_run(argv: list):
    import argparse
    p = argparse.ArgumentParser(prog="kinetic_recon.py run <配置>", description="配置文件 v2 → 片 × 约束阶梯的结果目录")
    p.add_argument("config", nargs="?", help="配置文件（fylite:KineticReconInput v1 / v2）；给了 --resume 可省")
    p.add_argument("--tiers", help="ladder.tiers 的简写：M,K,P,S,J（M 总是跑）")
    p.add_argument("--slices", help="6.72 · 6.3,6.72 · t0:t1:dt · at-thomson · at-efit")
    p.add_argument("--window", help="at-* 的时间窗 t0:t1")
    p.add_argument("--set", action="append", default=[], metavar="键=值", help="改一个键（可重复）")
    p.add_argument("--jobs", type=int, help="run.jobs 的简写（档 M 设定点扫描的并行路数）")
    p.add_argument("--print-config", action="store_true", help="打印合成后的配置与每个键的来源，不运行")
    p.add_argument("--dry-run", action="store_true", help="列出每片 × 每档要收的块、今天做不了的项，不运行")
    p.add_argument("--resume", metavar="DIR", help="out/<炮号>：只重跑没有结果或配置变了的片")
    p.add_argument("--timeout", type=float, default=120.0, help="mdsip 读超时 [s]")
    p.add_argument("-o", "--out", default=None, help="输出根目录（缺省 output.dir）；结果写在 <根>/<炮号>/")
    return p.parse_args(argv)


def cmd_run(argv: list, lib_path: str | None) -> int:
    a = _parse_run(argv)
    try:
        doc, base = None, Path.cwd()
        if a.config:
            doc = json.loads(Path(a.config).read_text(encoding="utf-8"))
            base = Path(a.config).resolve().parent
        elif a.resume:
            rc = Path(a.resume) / "config.resolved.json"
            if not rc.exists():
                raise ConfigError(f"--resume {a.resume}：没有 config.resolved.json")
            doc = json.loads(rc.read_text(encoding="utf-8"))["config"]
            doc = dict(doc, **{"@type": TYPE, "version": 2})
        else:
            raise ConfigError("run：给配置文件，或 --resume out/<炮号>")
        flags = {}
        if a.tiers:
            flags["ladder.tiers"] = [x for x in a.tiers.replace(",", "").upper()]
        if a.slices:
            for k, v in parse_slices(a.slices, a.window).items():
                flags[f"slices.{k}"] = v
        elif a.window:
            flags["slices.window"] = parse_window(a.window)
        if a.jobs:
            flags["run.jobs"] = a.jobs
        cfg, origin = resolve(doc, a.set, flags)
        if a.print_config:
            print(json.dumps({"config": cfg, "origin": origin}, ensure_ascii=False, indent=1))
            return 0
        out_root = Path(a.out or cfg["output"]["dir"])
        lib = K.Lib(Path(lib_path)) if (lib_path and not a.dry_run) else None
        return run_batch(cfg, origin, base=base, out_root=out_root, lib=lib, jobs=a.jobs, dry_run=a.dry_run,
                         resume=Path(a.resume) if a.resume else None, timeout=a.timeout)
    except ConfigError as e:
        print(f"kinetic_recon.py run: {e}", file=sys.stderr)
        return 2


def cmd_init(argv: list, lib_path: str | None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="kinetic_recon.py init", description="写一份配置文件 v2（全部缺省键）")
    p.add_argument("--shot", type=int, required=True)
    p.add_argument("--time", type=float, action="append", required=True, help="时刻 [s]（可重复）")
    p.add_argument("--chain", default="east")
    p.add_argument("--server", help="mdsip 服务器（缺省 $FYLITE_MDSIP_SERVER；写进 data.server，空 = 用环境变量）")
    p.add_argument("--no-channels", action="store_true", help="不列逐道置信度表（缺省按装置事实列全、c = 1；要库）")
    p.add_argument("-o", "--out", required=True)
    a = p.parse_args(argv)
    d = copy.deepcopy(DEFAULTS)
    d["data"].update(shot=a.shot, chain=a.chain, server=a.server)
    d["slices"]["times_s"] = a.time
    if not a.no_channels:
        try:
            lib = K.Lib(Path(lib_path) if lib_path else K.DEFAULT_LIB)
            card, _ = lib.device("east", a.shot, a.chain)
            mag = card["magnetics"]
            d["magnetics"]["loops"] = {n: 1.0 for n in (K._name(x) for x in K._aos(mag.get("flux_loop"))) if n}
            d["magnetics"]["probes"] = {n: 1.0 for n in dict.fromkeys(K._name(x) for x in K._aos(mag.get("b_field_pol_probe"))) if n}
        except Exception as e:                           # noqa: BLE001 — 没有库照样写，只是不列道
            log(f"init: 逐道表没列（{type(e).__name__}: {e}）——道名在跑时由装置事实给")
    Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"-> {a.out}")
    return 0


def cmd_validate(argv: list, lib_path: str | None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="kinetic_recon.py validate", description="读 out/<炮号> 的结果，重写每片的 validation.json")
    p.add_argument("dir")
    p.add_argument("--checks", help=f"逗号分隔（缺省配置里的 validation.checks；可选 {', '.join(CHECKS)}）")
    a = p.parse_args(argv)
    d = Path(a.dir)
    try:
        rc = json.loads((d / "config.resolved.json").read_text(encoding="utf-8"))["config"]
    except (OSError, ValueError, KeyError):
        rc = DEFAULTS
    checks = a.checks.split(",") if a.checks else rc["validation"]["checks"]
    bad = [c for c in checks if c not in CHECKS]
    if bad:
        print(f"kinetic_recon.py validate: 认不出的校验 {bad}（{', '.join(CHECKS)}）", file=sys.stderr)
        return 2
    n = 0
    for rp in sorted(d.glob("t*/result.json")):
        v = validation(json.loads(rp.read_text(encoding="utf-8")), checks)
        _write(rp.parent / "validation.json", v, indent=1)
        n += 1
        print(f"{rp.parent.name}: " + " · ".join(f"{c['id']} {c['verdict']}" for c in v["checks"]))
    if not n:
        print(f"kinetic_recon.py validate: {d} 下没有 t*/result.json", file=sys.stderr)
        return 1
    return 0


def _is_config(path: str) -> bool:
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(d, dict) and d.get("@type") == TYPE


def route(argv: list):
    """``kinetic_recon.main`` 的前置：``init`` · ``validate``，与配置文件 / ``--resume`` 形的 ``run`` 在这里跑；
    其余（pull · kfile · run <测量文档> · compare · series）返回 None，照旧由 kinetic_recon 的解析器处理。"""
    argv = list(argv)
    lib = None
    if argv and argv[0] == "--lib" and len(argv) > 1:
        lib, argv = argv[1], argv[2:]
    elif argv and argv[0].startswith("--lib="):
        lib, argv = argv[0].split("=", 1)[1], argv[1:]
    if not argv:
        return None
    cmd, rest = argv[0], argv[1:]
    if cmd == "init":
        return cmd_init(rest, lib)
    if cmd == "validate":
        return cmd_validate(rest, lib)
    if cmd == "run":
        cand = [x for x in rest if not x.startswith("-")]
        if any(_is_config(x) for x in cand) or ("--resume" in rest and not any(Path(x).suffix == ".json" and not _is_config(x)
                                                                                for x in cand)):
            return cmd_run(rest, lib)
    return None
