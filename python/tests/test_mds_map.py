"""闸子：`mapping/east-mds.json` —— MDSplus 读入的**绑定**表。

★**为什么一份数据文件需要自己的闸子。**  这张表说的是「哪个节点喂哪个语义位置、
过哪个标度、按哪条时间基取片」。它错了不会报错：读回来的仍然是一个量级正常的数组，
只是来自另一条通道、或差一个 2π。所以这里判的不是「文件能解析」，而是三件事——

1. **它引用的每一个机器事实，在装置卷宗里解得开**（`device:` 引用逐条走真文档）。
   这是这张表得以「只管一半」的全部理由：另一半没有被抄，而是被指着。
2. **它声明的标度与窗口，就是今天的代码实际施加的那些**——用一根合成的输入管子
   把归约跑一遍，把标度**量出来**再比，而不是在测试里把常数重抄一遍（重抄的那份
   与被测的那份一起错，第二个见证就不是见证）。
3. **两个宿主拼写的是同一批节点**：Python 侧从 `fylite.io.mds` 的源里抽出实际拼出的
   `\\EFIT_EAST::TOP…` 全集，与表里的双向比对（浏览器网关那半在
   `app/tests/validate-mds-map.mjs`，同一份文件、同一条判据）。

★本批（P0）**不切换任何消费者**：代码仍走它自己的常量，这张表与它们**逐字段等价**，
而上面第 2、3 条就是那个「等价」的可执行形式。等 P1/P2 把消费者改成读表之后，第 3 条
会自然退役（源里不再有可抽的字符串），第 1、2 条继续管着。
"""
from __future__ import annotations

import inspect
import json
import math
import re
from pathlib import Path

import pytest

import conftest

REPO = Path(__file__).resolve().parents[2]
MAP_FILE = REPO / "mapping" / "east-mds.json"
SCHEMA_FILE = REPO / "mapping" / "mds-map.schema.json"


@pytest.fixture(scope="module")
def mapping() -> dict:
    if not MAP_FILE.is_file():
        pytest.skip(f"no acquisition map at {MAP_FILE}")
    return json.loads(MAP_FILE.read_text(encoding="utf-8"))


def _groups(mapping) -> dict:
    return {g["id"]: g for g in mapping["groups"]}


# --------------------------------------------------------------------------- #
# 1. 形状                                                                       #
# --------------------------------------------------------------------------- #
def test_schema_validates(mapping):
    """完整的 schema 校验——`jsonschema` 不在就跳过这一项（只有这一项）。"""
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(mapping)


def test_shape_invariants(mapping):
    """schema 说不出的那几条，恒开：id 唯一、节点来源唯一、时间基指得到人。"""
    gs = mapping["groups"]
    ids = [g["id"] for g in gs]
    assert len(ids) == len(set(ids)), f"重复的 group id: {ids}"

    for g in gs:
        srcs = [k for k in ("nodes", "node", "node_ref", "channels_ref") if k in g]
        assert len(srcs) == 1, f"{g['id']}: 节点来源必须恰好一个，得到 {srcs}"
        trees = [k for k in ("tree", "tree_ref") if k in g]
        assert len(trees) == 1, f"{g['id']}: 树必须恰好一个，得到 {trees}"
        t = g.get("time") or {}
        if "group" in t:
            assert t["group"] in ids, f"{g['id']}: 时间基指向不存在的组 {t['group']}"


def test_every_declared_fyo_slot_resolves(mapping):
    """★J-2 那条：表里写的 fyo 槽必须是**生成表里已声明的**槽。

    写错一个路径，两个宿主会**一致地**写出一份没有读者的文档——一致的错误比不一致的
    错误更难发现，所以这一条在 P0 就得管住。
    """
    from fylite import fyo

    seen = set()
    for g in mapping["groups"]:
        for tgt in [g.get("target")] + [n.get("target") for n in g.get("nodes", [])]:
            slot = (tgt or {}).get("fyo_slot")
            if not slot:
                continue
            path = fyo.path_of(slot["table"], slot["key"])   # 未声明即抛
            assert path, f"{slot} 解出空路径"
            seen.add((slot["table"], slot["key"]))

    #: ★逐条钉住而不是「至少 N 个」：一个槽被悄悄删掉，与它从来没写过一样看不出来。
    assert seen == {
        ("EQUILIBRIUM", "boundary_r"), ("EQUILIBRIUM", "boundary_z"),
        ("EQUILIBRIUM", "axis_r"), ("EQUILIBRIUM", "axis_z"),
        ("EQUILIBRIUM", "psi_axis"), ("EQUILIBRIUM", "psi_boundary"),
        ("EQUILIBRIUM", "q_1d"),
    }, f"对照槽的集合变了: {sorted(seen)}"


# --------------------------------------------------------------------------- #
# 2. 引用闸：每个 `device:` 引用在装置卷宗里解得开                                 #
# --------------------------------------------------------------------------- #
def _refs(obj, out=None):
    """表里出现的全部 `device:` 引用（任意深度）。"""
    out = [] if out is None else out
    if isinstance(obj, dict):
        for v in obj.values():
            _refs(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _refs(v, out)
    elif isinstance(obj, str) and obj.startswith("device:"):
        out.append(obj)
    return out


def _resolve(doc, ref: str):
    """`device:a.b[].c` → 卷宗里的值（`[]` 一步展开为逐元素取值）。"""
    node = doc
    for seg in ref[len("device:"):].split("."):
        arr = seg.endswith("[]")
        key = seg[:-2] if arr else seg
        if isinstance(node, list):
            node = [n[key] for n in node]          # 已在 AoS 内，逐元素取
        else:
            assert isinstance(node, dict) and key in node, f"{ref}: 解不到 {key!r}"
            node = node[key]
        if arr:
            assert isinstance(node, list), f"{ref}: {key} 不是数组"
    return node


@pytest.fixture(scope="module")
def deck() -> dict:
    yaml = pytest.importorskip("yaml")
    path = conftest.machine_device_file("east_device.yaml")
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def test_map_names_the_deck_it_resolves_against(mapping, deck):
    path = conftest.machine_device_file("east_device.yaml")
    assert Path(path).name == mapping["device_document"]


def test_every_device_ref_resolves(mapping, deck):
    """★这一条是「配置只管卷宗不管的那半」这个边界的**唯一**守卫。

    它一旦不跑，表里就可以静静地长出一份自己的通道清单，而那正是本次要关掉的形状。
    """
    refs = sorted(set(_refs(mapping)))
    assert refs, "表里一个 device: 引用都没有——那它就不是「只管一半」的那张表了"
    for ref in refs:
        val = _resolve(deck, ref)
        assert val is not None, f"{ref}: 解到 None"


def test_channel_refs_agree_with_the_device_module(mapping, deck):
    """逐通道引用解出来的名字，必须与 `fylite.device` 派生的那份**逐字相同**。

    两条路（本测试直接走 YAML，被测代码走 `device`）解到同一份名字，才说明这张表指的
    确实是代码在用的那些通道。
    """
    conftest.machine_tables()
    from fylite import device

    expect = {
        "device:magnetics.flux_loop[].name": device.FLUX_LOOP_NODES,
        "device:magnetics.b_field_pol_probe[].name": device.B_PROBE_NODES,
        "device:pf_active.coil[].name": device.PF_NODES,
        "device:interferometer.channel[].name": device.POINT_NE_NODES,
        "device:polarimeter.channel[].name": device.POINT_FR_NODES,
    }
    used = set(_refs(mapping))
    for ref, want in expect.items():
        assert ref in used, f"{ref} 不再被表引用——通道是从哪来的？"
        assert tuple(_resolve(deck, ref)) == tuple(want), f"{ref}: 与 device 派生的不一致"


# --------------------------------------------------------------------------- #
# 3. 等价闸：把标度**量出来**，与表里声明的比                                      #
# --------------------------------------------------------------------------- #
class _Pipe:
    """一根只回常数的合成输入管子，形状与 `reduce_est2` 的 `get` 完全一样。

    ★用它把归约跑一遍，读出的就是代码**实际施加**的标度——比在测试里重抄一遍常数强，
    因为重抄的那份与被测的那份会一起错。
    """

    def __init__(self, value=1.0, overrides=None, t0=-7.0, t1=10.0, n=3401):
        import numpy as np
        self.t = np.linspace(t0, t1, n)
        self.value = value
        self.overrides = overrides or {}

    def __call__(self, leaf, tree):
        import numpy as np
        v = self.overrides.get((leaf, tree), self.overrides.get(leaf, self.value))
        if v is None:
            return None
        return (np.full_like(self.t, float(v)), self.t)


@pytest.fixture(scope="module")
def measured(deck):
    """常数 1.0 喂进归约（关掉漂移扣除，否则常数会被自己减成 0）。"""
    conftest.machine_tables()
    from fylite.io import est2
    return est2.reduce_est2(_Pipe(), shot=0, time_s=1.0, drift_window=None)


def test_declared_windows_are_the_code_defaults(mapping):
    """窗口与漂移区间：与 `reduce_est2` / `read_east_mds` 的**签名缺省**逐值相同。"""
    from fylite.io import est2

    d_est2 = inspect.signature(est2.reduce_est2).parameters
    d_kfile = inspect.signature(est2.read_east_mds).parameters
    win_ms = d_est2["window_ms"].default
    assert win_ms == d_kfile["window_ms"].default, "两个入口的窗口缺省已经分家"
    drift = d_est2["drift_window"].default

    for gid in ("est2-flux-loop", "est2-b-probe", "est2-pf-current",
                "est2-ip", "est2-btor"):
        sel = _groups(mapping)[gid]["select"]
        assert sel["window_s"] == pytest.approx(win_ms / 1e3), f"{gid}: 窗口不符"
    assert _groups(mapping)["est2-flux-loop"]["select"]["drift_window_s"] == list(drift)
    assert _groups(mapping)["est2-b-probe"]["select"]["drift_window_s"] == list(drift)
    for gid in ("est2-pf-current", "est2-ip", "est2-btor"):
        assert _groups(mapping)[gid]["select"]["drift_window_s"] is None, \
            f"{gid}: 表里说要扣漂移，而代码这一路不扣"


def test_flux_loop_scale_is_measured_not_asserted(mapping, measured):
    """磁通环：量出来的标度 == 表里的 factor（就是那个 1/2π）。"""
    g = _groups(mapping)["est2-flux-loop"]
    factor = g["scale"]["factor"]
    assert factor == pytest.approx(1.0 / (2.0 * math.pi), rel=0, abs=1e-15)
    for v in measured["coils"]:
        assert v == pytest.approx(factor, rel=1e-12)


def test_probe_has_no_scale(mapping, measured):
    """磁探针：表里没有 scale，代码也不能有——1.0 进、1.0 出。"""
    assert "scale" not in _groups(mapping)["est2-b-probe"]
    live = [v for v, w in zip(measured["expmp2"], measured["fwtmp2"]) if w > 0]
    assert live, "没有一道活探针，这个判据就没被跑到"
    for v in live:
        assert v == pytest.approx(1.0, rel=1e-12)


def test_pf_scale_and_order_come_from_the_deck(mapping, measured, deck):
    """线圈：标度是逐通道匝数、次序是 efit_index —— 两条都按表里的引用核。"""
    g = _groups(mapping)["est2-pf-current"]
    assert g["scale"]["ref"] == "device:pf_active.coil[].turns"
    assert g["order_ref"] == "device:pf_active.coil[].efit_index"

    turns = [float(t) for t in _resolve(deck, g["scale"]["ref"])]
    order = [int(i) for i in _resolve(deck, g["order_ref"])]
    assert measured["brsp"] == pytest.approx([turns[i] for i in order], rel=1e-12)


def test_ip_scale_and_its_cross_tree_fallback(mapping, deck):
    """Ip：标度 1000（kA→A），以及**换树**的那一级回退按表里写的阈值触发。"""
    from fylite.io import est2
    g = _groups(mapping)["est2-ip"]
    assert g["scale"] == 1000.0
    assert g["units_in"] == "kA" and g["units_out"] == "A"

    m = est2.reduce_est2(_Pipe(), shot=0, time_s=1.0, drift_window=None)
    assert m["plasma"] == pytest.approx(1000.0, rel=1e-12), "kA→A 的标度变了"

    fb = g["fallback"][0]
    assert fb["node"] == r"\pcrl01"
    assert _resolve(deck, fb["tree_ref"]) == "pcs_east"
    thresh = float(re.search(r"([0-9.]+e[0-9+]+)", fb["when"]).group(1))
    #: 主节点给出的 Ip 落在阈值以下 → 必须换到 pcs 树那一道上去
    m2 = est2.reduce_est2(
        _Pipe(overrides={r"\pcrl01": 2.0 * thresh}), shot=0, time_s=1.0,
        drift_window=None)
    assert m2["plasma"] == pytest.approx(2.0 * thresh, rel=1e-12), \
        "回退没有按表里写的阈值触发"


def test_btor_scale_and_constant_fallback(mapping, deck):
    """B_t：两个分支都量——大信号量出 factor，小信号落到那个**编出来的** 1.8 T。"""
    from fylite.io import est2
    g = _groups(mapping)["est2-btor"]
    factor = g["scale"]["factor"]
    const = g["fallback"][0]["constant"]

    small = est2.reduce_est2(_Pipe(), shot=0, time_s=1.0, drift_window=None)
    assert small["btor"] == pytest.approx(const, rel=1e-12), "常数回退的值变了"

    big = est2.reduce_est2(_Pipe(value=1.0e5), shot=0, time_s=1.0, drift_window=None)
    assert big["btor"] == pytest.approx(1.0e5 * factor, rel=1e-12), "FoCS 标度变了"


def test_gate_and_point_refs_point_at_real_deck_values(mapping, deck):
    """读数卫生的门与 POINT 的窗口/基线：表里只给引用，值必须在卷宗里且与代码一致。"""
    conftest.machine_tables()
    from fylite import device as _dev
    from fylite import device

    gate = _resolve(deck, _groups(mapping)["efit-b-probe"]["gate_ref"])
    #: ★2026-09-01：门限此前经 `io.kfile` 的惰性属性取，kfile 已随 EFIT k-file
    #: 写入机移除；它本来就是装置文档的内容，这里直读文档，与 `io.mds` 同一条路。
    _op = _dev.document()["operational"]["probe_gate"]
    assert float(gate["min_tesla"]) == float(_op["min_tesla"])
    assert float(gate["max_tesla"]) == float(_op["max_tesla"])

    for gid in ("point-density", "point-faraday"):
        sel = _groups(mapping)[gid]["select"]
        assert float(_resolve(deck, sel["window_ref"])) * 1e3 == device.POINT_WINDOW_MS
        base = _resolve(deck, sel["baseline_ref"])
        assert float(base["centre_s"]) == device.POINT_BASELINE_S
        assert float(base["tolerance_s"]) == device.POINT_BASELINE_TOL


# --------------------------------------------------------------------------- #
# 4. 跨宿主闸（Python 半）：表与 `io.mds` 拼出的节点全集，双向相等                   #
# --------------------------------------------------------------------------- #
def _efit_nodes_of_map(mapping) -> set:
    out = set()
    for g in mapping["groups"]:
        if g.get("tree") != "efit_east":
            continue
        for n in g.get("nodes", []):
            out.add(n["name"])
        if "node" in g:
            out.add(g["node"])
        for fb in g.get("fallback", []):
            if "node" in fb:
                out.add(fb["node"])
    return out


def _efit_nodes_of_source(src: str) -> set:
    """源里 `M + "EXPMPI"` 这种拼法还原成整条节点路径。"""
    prefixes = dict(re.findall(r'^\s*([A-Z])\s*=\s*r"(\\EFIT_EAST::TOP[^"]*)"',
                               src, re.M))
    assert prefixes, "源里找不到 \\EFIT_EAST 前缀——抽取器该改了，不是表该改"
    out = set()
    for var, pre in prefixes.items():
        for suf in re.findall(rf'\b{var}\s*\+\s*"([A-Z0-9_]+)"', src):
            out.add(pre + suf)
    return out


def test_map_and_io_mds_spell_the_same_efit_nodes(mapping):
    """★这道闸子的形状就是本次要关掉的那条分叉：**两处拼写、一个契约**。

    P1 之后 `io.mds` 不再自带这些字符串，抽取器会抽空——那时这道闸子就该退役（它的
    话由「代码读表」本身接过去），而不是被放宽。
    """
    src = (REPO / "python" / "fylite" / "io" / "mds.py").read_text(encoding="utf-8")
    in_code = _efit_nodes_of_source(src)
    in_map = _efit_nodes_of_map(mapping)
    assert in_code - in_map == set(), f"代码读了表里没有的节点: {sorted(in_code - in_map)}"
    assert in_map - in_code == set(), f"表里有代码不读的节点: {sorted(in_map - in_code)}"
