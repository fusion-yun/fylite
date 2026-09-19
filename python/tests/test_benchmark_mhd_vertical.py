"""竖直稳定性的门（register record `mhd-vertical-freegsnke-east137985` · `FR-EQ-016`）。

★★本域的行文把顺序说死了：「先把锚钉牢，再去和别人对拍」。于是这里的门分两类——
**解析锚**（不需要任何外部码，`code/vstab` 自己就该满足）与**对拍**（对 FreeGSNKE 那次
已录制的运行）。两类都要：锚守的是接线，对拍守的是物理。

★没有案例库、没有装置卡、没有运行库：**按名跳过**，与本册其余需要机器数据的门同一条政策。
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = "FYDOC-CASE-23-east-137985-efit-east"
IDENT = ROOT / "docs/benchmark/readings/vstab_identities_east137985.json"
WALL = ROOT / "docs/benchmark/readings/wall_vstab_east137985.json"

#: 记录第④格：gamma/eta 四档的散布。★留三个量级的余量——判据要的是「成比例」，
#: 而 4.44e-16 是一个 ulp；把门卡在实测值上，换台机器就会红在舍入上。
PROPORTIONAL_TOL = 1e-12
#: 记录第⑧格：本册自立的 1 % 口径
CROSS_TOL = 0.01


def _tool():
    spec = importlib.util.spec_from_file_location(
        "benchmark_wall_vstab", ROOT / "tools" / "benchmark-wall-vstab.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def case() -> Path:
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    if store is None or not (store / CASE / "case.yaml").is_file():
        pytest.skip(f"no {CASE} in the case store (set $FYDOC_ORACLE to the fydoc cases/ tree)")
    try:
        from fylite import device
        device.document(shot=137985, measurement_chain="east")
    except Exception as e:  # noqa: BLE001 — 没有卡或运行库就按名跳过
        pytest.skip(f"no EAST device card / runtime library here: {e}")
    return store / CASE


@pytest.fixture(scope="module")
def ident(case) -> dict:
    return _tool().identities(case)


def test_the_growth_rate_is_proportional_to_the_wall_resistance(ident):
    """★判据④的锚：被动电阻整体缩放 x 倍，gamma 就该是 x 倍。

    ★★这条不需要外部码，却能抓住阻性壁支上大多数接线错误——把 R 接错位置、
    或把 tau_w 从错的矩阵里取，比例立刻不成立。
    """
    got = ident["gamma_proportional_to_Rw"]
    assert got["spread_rel"] < PROPORTIONAL_TOL, got["sweep"]
    #: ★两头都验：只验比例会放过一个 gamma 恒为零的实现——它同样「成比例」
    assert all(s["gamma"] > 0.0 for s in got["sweep"]), got["sweep"]


def test_a_wall_further_out_grows_faster_until_the_ideal_limit(ident):
    """★判据⑥：壁越远 gamma 越大，越过理想阈值之后转判读、不再给有限数。

    ★单调性**只在有限支上**判：越界之后 gamma 是 +inf，而 `inf > inf` 为假——
    拿严格单调去套那一段，测出来的是判法的毛病，不是实现的。
    """
    got = ident["wall_farther_grows_faster"]
    assert got["n_finite"] >= 2, got["sweep"]
    assert got["monotone_over_the_finite_branch"] is True, got["sweep"]
    assert got["reaches_the_ideal_tier"] is True, got["sweep"]


def test_the_ideal_tier_is_loud_and_not_a_plausible_number(ident):
    """★判据⑤的 fail-loud 半边：理想不稳必须三样同时出现——+inf、regime 2、一条 note。

    ★单看其中任何一样都不够：一个只把 regime 置 2 却仍给出有限 gamma 的实现，
    下游会**照样把它当一个数用下去**。
    """
    tier = ident["three_regimes"]["ideal"]
    assert tier is not None, ident["three_regimes"]
    assert math.isinf(tier["gamma"]) and tier["gamma"] > 0.0, tier
    assert tier["regime_code"] == 2.0, tier
    assert any("ideal" in n for n in (tier.get("notes") or [])), tier


def test_the_linear_model_has_a_carrier_to_land_in(ident):
    """★判据⑦：`mhd_linear` 的载体在（清单口 + IDS 表）。"""
    got = ident["mhd_linear_carrier"]
    assert got["declared_in_manifest"] and got["ids_table_present"], got


def test_the_recorded_identity_readings_are_what_this_checkout_computes(ident):
    """★记录引的那份读数与本检出现算的一致——记录里的数不会悄悄过期。"""
    want = json.loads(IDENT.read_text(encoding="utf-8"))
    for k in ("gamma", "k", "k_ideal", "ip"):
        assert ident["base"][k] == pytest.approx(want["base"][k], rel=1e-9), k
    assert ident["three_regimes"]["codes_seen"] == want["three_regimes"]["codes_seen"]


def test_the_wall_and_the_growth_rate_agree_with_freegsnke(case):
    """★判据⑧：对 FreeGSNKE 那次已录制的运行——壁的 L/R 与刚体色散。

    ★对的是**刚体对刚体**：参照那一侧另有一支可形变的 gamma（是刚体的 2.165 倍），
    那是刚体模型里没有的物理，不是谁算错了。
    """
    got = _tool().readings(case)
    for name, s in got["wall"]["sets"].items():
        assert abs(s["tau1_rel"]) < CROSS_TOL, (name, s)
    for name, s in got["vstab"]["sets"].items():
        c = s["compare"]
        assert abs(c["gamma_rel"]) < CROSS_TOL, (name, c)
        assert abs(c["k_rel"]) < CROSS_TOL, (name, c)
        assert abs(c["k_ideal_rel"]) < CROSS_TOL, (name, c)


def test_the_stiffness_identity_closes_filament_by_filament(ident):
    """★★刚度恒等式逐根细丝取（2026-09-19）：`k = −2π Σ I_i R_i ∂B_z/∂R|_i` 对门的 k 到 1e-4 以内（实测 3.4e-8），同号。

    点等离子体式 `2π I_p n B_z` 差 0.89 %：约 0.53 % 是等离子体的有限尺寸（外场只在磁轴取一次），约 0.36 % 是
    8 × 8 分丝与门的中心单丝两种线圈模型之差——逐根细丝、同一个线圈模型取，两项都没了。"""
    s = ident["stiffness_identity"]
    assert abs(s["rel_filaments"]) < 1e-4, s
    assert math.copysign(1.0, s["k_identity_filaments"]) == math.copysign(1.0, s["k_door"])
    assert abs(s["rel_magnitude"]) > 1e-3, "the point-plasma form stays off by finite size"
    want = json.loads(IDENT.read_text(encoding="utf-8"))["stiffness_identity"]
    assert s["k_identity_filaments"] == pytest.approx(want["k_identity_filaments"], rel=1e-9)
