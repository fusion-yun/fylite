#!/usr/bin/env python3
"""Generate `docs/examples/scenario/` — the scenario templates `fy run` parses against.

A scenario template is a `fyo:ScenarioSpecification` like any other case in the
corpus (so `fy run <template>` composes it exactly as it composes a plan), plus
one extension block in `fylite:` words: the PARAMETER TABLE — every name the
code takes, its type, its range, and which of them are switches or come from
the device document.  `FYL-DESIGN-17` E-11 / E-18 / E-24.

★★Why generated rather than written.  The names a code takes are already
stated in the corpus, once per case, as `code/<x>#<name>` IRIs — 279 of them
across nine codes.  Transcribing that into a second file by hand is the
failure this repository keeps writing gates against: the two lists agree on
the day they are written and not on any day after.  So the vocabulary is
LIFTED from the corpus and only what the corpus cannot say — a title, which
ports the scenario has, which names are switches — is written here, in
`OVERLAY`.  `python/tests/test_scenario_templates.py` re-runs this file and
fails on a diff.

★Types are inferred from the literals the corpus carries; where a name appears
with both an int and a float the wider type wins.  A `choices` list or a range
is never inferred — an enumeration seen twice is not an enumeration — so those
come from `OVERLAY` or are absent.

Usage: python3 tools/make-scenario-templates.py [--check]
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import OrderedDict, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT / "docs" / "examples"
OUT = CORPUS / "scenario"

#: Written here because the corpus cannot state it: what the scenario IS, which
#: line it serves, what it must be handed, and which names are switches.
#: ★`ports.requires` is `card` or `manifest`: a card describes a machine, a
#: manifest is what a fetch can run against (`facts.rs` MANIFEST).  A scenario
#: that needs coil geometry and channel tables needs the manifest; one that
#: needs sizes does not.
OVERLAY: dict[str, dict] = {
    "reconstruction": {
        "title": {"zh": "平衡反演", "en": "Equilibrium reconstruction"},
        "lines": ["analysis"],
        "ports": {
            "device": {"requires": "manifest", "type": "fyo:DeviceDescription",
                       "ids": ["pf_active", "wall", "magnetics", "tf"]},
            "measurements": {"primary": True, "ids": ["magnetics", "pf_active", "tf"]},
            "pressure": {"optional": True,
                         "note": "the profile scenario's product; one carrying "
                                 "`derived-from-reconstruction` provenance is refused"},
        },
        "common": ["shot", "time", "provider", "epoch"],
        "time": "point",
        "types": {"basis": {"type": "choice", "choices": ["delivered", "raw"]},
                  "sigvint": {"type": "str"},
                  "mcn": {"type": "int", "min": 0},
                  "maxit": {"type": "int", "min": 1},
                  "kpts": {"type": "int", "min": 1},
                  "kw": {"type": "float", "min": 0.0}},
        "from_device": {"basis": "fylite:channel_basis"},
        #: ★the two switches are the analysis page's own presets `mag` and
        #: `kin` (app/assets/scenario-analysis.js), value for value.  They are
        #: not invented here, and the page's slider values (kw, kpts) are NOT
        #: part of them: a switch expands booleans only (E-18).
        "switches": {
            "only_magnetic": {"kin": False, "neon": False, "probefit": False,
                              "pointfit": False, "farfit": False, "vesselfit": False},
            "kinetic": {"kin": True, "neon": True, "probefit": False,
                        "pointfit": True, "farfit": False, "vesselfit": False},
        },
        #: the two the page ships as its factory setting, lifted from the
        #: corpus entry that extracted them (`reconstruction-default`).
        "defaults": {"basis": "delivered", "maxit": 800},
        "caveat": {"zh": "磁测量单独约束不住内部剖面；正向算子只有磁通环与探针一支，弦积分族缺席。",
                   "en": "Magnetics alone do not constrain the internal profiles; the forward "
                         "operator has flux loops and probes only, no line integrals."},
    },
    "series": {
        "title": {"zh": "时间序列反演", "en": "Reconstruction over a run of time slices"},
        "lines": ["analysis"],
        "ports": {"device": {"requires": "manifest", "type": "fyo:DeviceDescription",
                             "ids": ["pf_active", "wall", "magnetics", "tf"]},
                  "measurements": {"primary": True, "ids": ["magnetics", "pf_active", "tf"],
                                   "per": "slice"}},
        "common": ["shot", "time", "provider", "epoch"],
        "time": "selection",
        "types": {"coilsrc": {"type": "str"}, "nslice": {"type": "int", "min": 1}},
    },
    "profile": {
        "title": {"zh": "剖面拟合", "en": "Profile fitting"},
        "lines": ["analysis"],
        "ports": {"points": {"primary": True,
                             "note": "the measured points with their per-point sigma"}},
        "common": ["shot", "time"],
        "time": "point",
        "types": {"quantity": {"type": "str"}, "maxorder": {"type": "int", "min": 1},
                  "npts": {"type": "int", "min": 2}, "sigma": {"type": "float", "min": 0.0}},
    },
    "transport": {
        "title": {"zh": "定态芯部输运", "en": "Steady-state core transport"},
        "lines": ["model"],
        "ports": {"device": {"requires": "card", "optional": True,
                             "type": "fyo:DeviceDescription"}},
        "common": ["provider", "epoch"],
        "types": {"closure": {"type": "str"}},
        "from_device": {},
        "caveat": {"zh": "几何固定、无平衡反馈；粒子源由调用方给定，本包不含加料模型。",
                   "en": "Fixed geometry, no equilibrium feedback; the particle source is the "
                         "caller's — this package carries no fuelling model."},
    },
    "evolve": {
        "title": {"zh": "含时演化", "en": "Time-dependent evolution"},
        "lines": ["model"],
        "ports": {"device": {"requires": "card", "optional": True,
                             "type": "fyo:DeviceDescription"}},
        "common": ["provider", "epoch"],
        "types": {"closure": {"type": "str"}, "geometry": {"type": "str"},
                  "species": {"type": "str"}, "fuel": {"type": "int"},
                  "beamstop": {"type": "str"}, "beamdir": {"type": "str"}},
        "caveat": {"zh": "循环在内核（evolve_heat 条目），范围只有内核条目声明的那些：常数闭包、"
                         "热通道一条；密度 / 电流 / 动量通道、基座、锯齿、束流、波、演化平衡不在。",
                   "en": "The loop is the kernel's (`evolve_heat`), and the scope is what that "
                         "entry declares: a constant closure and the heat channel. Density, "
                         "current, momentum, pedestal, sawteeth, beams, waves and an evolving "
                         "equilibrium are not in it."},
    },
    "zerod": {
        "title": {"zh": "0-D 放电分析", "en": "0-D discharge analysis"},
        "lines": ["model", "design"],
        "ports": {"device": {"requires": "card", "optional": True,
                             "type": "fyo:DeviceDescription"}},
        "common": ["provider", "epoch"],
        "types": {"tau_law": {"type": "str"}},
        "caveat": {"zh": "n_e、T_e、T_i 是规定的输入不是结果，故 Q 不是预言。",
                   "en": "n_e, T_e and T_i are prescribed inputs rather than results, so Q is "
                         "not a prediction."},
    },
    "discharge": {
        "title": {"zh": "静态线圈反解", "en": "Static coil inversion"},
        "lines": ["design"],
        "ports": {"device": {"requires": "manifest", "type": "fyo:DeviceDescription",
                             "ids": ["pf_active", "wall", "tf"]}},
        "common": ["provider", "epoch"],
        "types": {"class": {"type": "str"}, "profsrc": {"type": "str"},
                  "startmode": {"type": "str"}},
        "caveat": {"zh": "每一步是收敛到 tol 的静态解，不含惯性与演化。",
                   "en": "Each step is a static solve converged to tol; no inertia, no evolution."},
    },
    "breakdown": {
        "title": {"zh": "击穿场零设计", "en": "Breakdown null design"},
        "lines": ["design", "control"],
        "ports": {"device": {"requires": "manifest", "type": "fyo:DeviceDescription",
                             "ids": ["pf_active", "wall", "tf"]}},
        "common": ["provider", "epoch"],
        "caveat": {"zh": "限值由使用者填（非机器数据）；纯真空，无等离子体、无 G-S。",
                   "en": "The limits are the user's to state (they are not machine data); pure "
                         "vacuum, no plasma, no Grad-Shafranov."},
    },
    "pfwave": {
        "title": {"zh": "PF 电源整定与波形", "en": "PF supply sizing over a waveform"},
        "lines": ["design"],
        "ports": {"device": {"requires": "manifest", "type": "fyo:DeviceDescription",
                             "ids": ["pf_active", "wall", "tf"]}},
        "common": ["provider", "epoch"],
    },
}

#: The scenarios the documents name that get NO template, and why (E-8: a
#: reason a reader can find in the data, not in prose).  `line` is the line it
#: would belong to; `folded_into` names the scenario whose parameters carry it.
NO_TEMPLATE = [
    ("posterior", "analysis", "reconstruction",
     {"zh": "后验采样是反演的一组参数（mcn · mc-*），不是另一个场景。",
      "en": "The posterior is a group of the reconstruction's own parameters (mcn, mc-*), not a "
            "second scenario."}),
    ("batch", "analysis", None,
     {"zh": "队列是宿主机制：命令行上是 series，或一个 shell 循环。",
      "en": "A queue is host plumbing: on a command line it is `series`, or a shell loop."}),
    ("loop", "analysis", None,
     {"zh": "反演—输运自洽外环在本分发里跑不起来（指南「自洽外环」自述）；库路径复原后再设。",
      "en": "The self-consistent reconstruction/transport outer loop does not run in this "
            "distribution (the guide says so); a template waits on the library path."}),
    ("sxr", "analysis", None,
     {"zh": "软 X 射线层析：文档提及，无工具、无栏、无语料。",
      "en": "Soft X-ray tomography is named in the documents and has no tool, no bar and no case."}),
    ("coupled", "model", "evolve",
     {"zh": "平衡—输运静态交替是 evolve 的 couple 参数（2026-08-26 栏让给 evolve）。",
      "en": "The static equilibrium/transport alternation is `evolve`'s `couple` parameter."}),
    ("tglf", "model", "transport",
     {"zh": "湍流通量是两条栏里的一个闭包模式（closure · turb-*），独立模板待 P2-c。",
      "en": "Turbulent flux is a closure mode of two bars (closure, turb-*); a template of its "
            "own waits on P2-c."}),
    ("interp", "model", None,
     {"zh": "剖面插值是工具不是场景。",
      "en": "Grid interpolation is a utility, not a scenario."}),
    ("sim", "design", None,
     {"zh": "交互时间推进是浏览器的档位，不是批式动作（FYL-DESIGN-10 P-1）。",
      "en": "The interactive time march is a browser tier, not a batch action."}),
    ("pulse", "design", None,
     {"zh": "整脉冲前馈设计今天没有 code IRI（语料的 pulse-iter 用 code/pfwave），"
            "模板需要一个真实的 code——P2-c。",
      "en": "Whole-pulse feed-forward design has no code IRI today (the corpus's `pulse-iter` "
            "prescribes code/pfwave), and a template needs a real one — P2-c."}),
    ("feasible", "design", None,
     {"zh": "可行域扫描无栏、无语料，扫描轴的参数词表要先立——P2-c。",
      "en": "The feasibility scan has no bar and no case; its axis vocabulary has to be stated "
            "first — P2-c."}),
    ("vstab", "control", None,
     {"zh": "垂直稳定裕度有内核 entry（vstab）但无 case code、无语料词表——P2-c。",
      "en": "Vertical stability has a kernel entry (`vstab`) but no case code and no corpus "
            "vocabulary — P2-c."}),
    ("vertical", "control", None,
     {"zh": "垂直反馈闭环无栏无语料，参数词表要先立。",
      "en": "The vertical feedback loop has no bar and no case; its vocabulary has to be stated "
            "first."}),
    ("evolution", "control", None,
     {"zh": "电压驱动的位形演化同上。",
      "en": "Voltage-driven shape evolution, likewise."}),
]

LINES = OrderedDict([
    ("analysis", {"title": {"zh": "实验分析", "en": "Experiment analysis"},
                  "default": "reconstruction",
                  "conops": "S-L2"}),
    ("model", {"title": {"zh": "物理建模", "en": "Physics modelling"},
               "default": "transport",
               "conops": "S-L1"}),
    ("design", {"title": {"zh": "放电运行设计", "en": "Discharge operation design"},
                "default": "zerod",
                "conops": "S-L4"}),
    ("control", {"title": {"zh": "控制仿真", "en": "Control simulation"},
                 "default": "breakdown",
                 "conops": "S-L3"}),
])

#: What the kernel's case door accepts today (`fyo_interface.rs` CASE_CODES).
#: ★Stated here so the generated data can say "not runnable, and here is why"
#: without loading a kernel; `fy list scenarios` reads the LIVE table and the
#: gate compares the two, so a kernel that grows a code makes this stale
#: loudly rather than quietly.
DOOR = {"evolve", "zerod", "transport",
        "vstab",
        "breakdown", "discharge", "pulse", "reconstruction", "interpretive", "coupled", "beam"}


def widen(a: str, b: str) -> str:
    order = ["bool", "int", "float", "str"]
    return order[max(order.index(a), order.index(b))]


def type_of(v) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    return "str"


def vocabulary() -> dict[str, dict[str, str]]:
    """Every `code/<x>#<name>` the corpus sets, with the widest type seen."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    for f in sorted(CORPUS.glob("*/*.jsonld")):
        if f.parent.name == "scenario":
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        code = doc.get("prescribes_code", {}).get("id", "")
        if not code.startswith("code/"):
            continue
        name = code.split("/", 1)[1]
        for p in doc.get("parameters", []):
            iri = p.get("sets_parameter", "")
            if "#" not in iri or "literal_value" not in p:
                continue
            key = iri.split("#", 1)[1]
            t = type_of(p["literal_value"])
            out[name][key] = widen(out[name].get(key, t), t)
    return out


def task_kinds() -> dict[str, str]:
    out: dict[str, str] = {}
    for f in sorted(CORPUS.glob("*/*.jsonld")):
        if f.parent.name == "scenario":
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        code = doc.get("prescribes_code", {}).get("id", "")
        kind = doc.get("prescribed_task_kind")
        if code.startswith("code/") and kind:
            out.setdefault(code.split("/", 1)[1], kind)
    return out


def template(name: str, vocab: dict[str, str], kind: str) -> OrderedDict:
    o = OVERLAY[name]
    types = o.get("types", {})
    from_device = o.get("from_device", {})
    table = OrderedDict()
    for key in sorted(vocab):
        entry = OrderedDict()
        override = types.get(key, {})
        entry["type"] = override.get("type", vocab[key])
        for extra in ("choices", "min", "max", "note"):
            if extra in override:
                entry[extra] = override[extra]
        if key in from_device:
            entry["from_device"] = from_device[key]
        table[key] = entry

    doc = OrderedDict()
    doc["@context"] = ["../context.jsonld"]
    doc["id"] = f"scenario/{name}"
    doc["type"] = "fyo:ScenarioSpecification"
    doc["title"] = o["title"]
    doc["note"] = {
        "zh": f"场景模板：`fy run <线> {name}` 的参数表与端口声明。GENERATED by "
              f"tools/make-scenario-templates.py — 词表逐条取自语料的 code/{name}#<名> IRI，"
              f"不要手改。",
        "en": f"Scenario template: the parameter table and ports of `fy run <line> {name}`. "
              f"GENERATED by tools/make-scenario-templates.py — the vocabulary is lifted from "
              f"the corpus's own code/{name}#<name> IRIs; do not hand-edit.",
    }
    doc["prescribed_task_kind"] = kind
    doc["prescribes_code"] = OrderedDict([
        ("id", f"code/{name}"),
        ("type", "spo:Code"),
        ("name", "fylite"),
    ])
    doc["fylite:lines"] = o["lines"]
    doc["fylite:ports"] = o["ports"]
    doc["fylite:common"] = o["common"]
    if "time" in o:
        doc["fylite:time"] = o["time"]
    doc["fylite:vocabulary"] = table
    if o.get("switches"):
        doc["fylite:switches"] = o["switches"]
    if o.get("caveat"):
        doc["caveat"] = o["caveat"]
    doc["parameters"] = [
        OrderedDict([("type", "spo:ParameterSetting"),
                     ("sets_parameter", f"code/{name}#{k}"),
                     ("literal_value", v)])
        for k, v in sorted(o.get("defaults", {}).items())
    ]
    return doc


def index(vocab: dict[str, dict[str, str]]) -> OrderedDict:
    rows = []
    for name in sorted(OVERLAY):
        o = OVERLAY[name]
        runnable = name in DOOR
        row = OrderedDict([
            ("name", name),
            ("lines", o["lines"]),
            ("template", True),
            ("code", f"code/{name}"),
            ("parameters", len(vocab.get(name, {}))),
            ("runnable", runnable),
        ])
        if not runnable:
            row["reason"] = {
                "zh": f"内核的 case 门今天不认 code/{name}（CASE_CODES 只有 "
                      f"{' · '.join(sorted(DOOR))}）；FYL-DESIGN-17 P2。",
                "en": f"The kernel's case door does not accept code/{name} today (CASE_CODES "
                      f"carries {', '.join(sorted(DOOR))} only); FYL-DESIGN-17 P2.",
            }
        rows.append(row)
    for name, line, folded, reason in NO_TEMPLATE:
        row = OrderedDict([("name", name), ("lines", [line]), ("template", False),
                           ("runnable", False)])
        if folded:
            row["folded_into"] = folded
        row["reason"] = reason
        rows.append(row)

    doc = OrderedDict()
    doc["@context"] = ["../context.jsonld"]
    doc["id"] = "scenario/lines"
    doc["type"] = "fylite:ScenarioIndex"
    doc["title"] = {"zh": "场景目录", "en": "The scenario catalogue"}
    doc["note"] = {
        "zh": "四条线与它们的缺省场景，以及文档明确涉及的每一个场景：有模板的、并入别的场景的、"
              "以及不设模板的——后两类各带理由（FYL-DESIGN-17 E-8 / E-17）。GENERATED by "
              "tools/make-scenario-templates.py。",
        "en": "The four lines with their default scenarios, and every scenario the documents "
              "name: templated, folded into another, or without a template — the last two with "
              "the reason stated here rather than in prose (FYL-DESIGN-17 E-8 / E-17). "
              "GENERATED by tools/make-scenario-templates.py.",
    }
    doc["fylite:lines"] = OrderedDict(
        (k, OrderedDict([("title", v["title"]), ("default", v["default"]),
                         ("conops", v["conops"])])) for k, v in LINES.items())
    doc["fylite:scenarios"] = rows
    return doc


def main() -> int:
    check = "--check" in sys.argv[1:]
    vocab = vocabulary()
    kinds = task_kinds()
    missing = sorted(set(OVERLAY) - set(vocab))
    if missing:
        print(f"[scenario] no corpus vocabulary for {missing} — a template needs a real code",
              file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    wrote, stale = [], []
    files = {f"{n}.jsonld": template(n, vocab[n], kinds[n]) for n in sorted(OVERLAY)}
    files["lines.jsonld"] = index(vocab)
    for name, doc in files.items():
        text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
        path = OUT / name
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        (stale if check else wrote).append(name)
        if not check:
            path.write_text(text, encoding="utf-8")
    for extra in sorted(OUT.glob("*.jsonld")):
        if extra.name not in files:
            (stale if check else wrote).append(f"{extra.name} (removed)")
            if not check:
                extra.unlink()
    if check and stale:
        print(f"[scenario] out of date: {', '.join(stale)} — re-run "
              f"tools/make-scenario-templates.py", file=sys.stderr)
        return 1
    total = sum(len(v) for v in vocab.values())
    print(f"[scenario] {len(files)} files, {len(OVERLAY)} templates, "
          f"{total} parameter names lifted from the corpus"
          + (f"; wrote {', '.join(wrote)}" if wrote else "; already current"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
