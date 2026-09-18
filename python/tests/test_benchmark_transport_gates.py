"""输运组五条**此前一道门都没有**的记录，各补一道（2026-09-18）。

★★没有门的记录，数变了不会有任何东西红——它的判决只在写下的那一刻作数。这五条是：

  * `tr-closure-plugin-dispatch`（`FR-TR-003`）
  * `tr-coupling-nn-weights-external`（`FR-TR-013`）
  * `tr-closure-15d-source-switches`（`FR-TR-004` · `FR-TR-009`）
  * `tr-closure-dt-burn-astra`（`FR-TR-004`）
  * `tr-pedestal-zerod-bookkeeping-metis`（`FR-TR-014`）

★它们的读数当初是一次性脚本量的，**没有提交进来的生成工具**。所以每道门都从公开入口
从零重跑，并与读数**逐位**对上——对不上就说明要么实现动了、要么读数不再作数，两种都该红。

★★补门的过程里查出三件事，都记进了对应记录：
  * `fylite.nn` 的内置目录指着 09-01 就改名掉的 `nn_tables/`，干净检出里一个模型都找不到
    （已修，见 `nn.py` 的 `BUILTIN_DIR`）；
  * α 份额偏 +1.23 % 的成因：`zerod.rs` 写死 `E_ALPHA_FRACTION = 0.2013`，与它自己的注释
    `3.52/17.59` 差 +0.59 %——与工作点无关，是一个常数；
  * 1.5D 开关扫描记的「最劣能量平衡残差 1.154e-13」只是基线那一档的，全部变体里最劣的是
    台基那档 1.298e-13。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
RD = ROOT / "docs" / "benchmark" / "readings"
KERNEL_SRC = ROOT.parent / "fylite_kernel" / "rust" / "fylite" / "src"


def _read(name: str) -> dict:
    return json.loads((RD / name).read_text(encoding="utf-8"))


def _model():
    try:
        from fylite.scenario import model as M
        M.transport(n_rho=11, closure="constant")      # 运行库在不在
    except Exception as e:  # noqa: BLE001 —— 没有运行库就按名跳过
        pytest.skip(f"no runtime library here: {e}")
    return M


def _last(v) -> float:
    return float(np.atleast_1d(np.asarray(v, float))[-1])


def _absmax(v) -> float:
    return float(np.max(np.abs(np.atleast_1d(np.asarray(v, float)))))


# ═══════════════════════════════════════════════ tr-closure-plugin-dispatch · FR-TR-003

_DISPATCH = dict(n_rho=41, dt=float("inf"), steps=1, tol=1e-13, max_inner=4000, d_pc=0.0)


def test_the_five_closure_names_dispatch_to_distinct_behaviour():
    """★五个名字：两个跑通且解**互不相同**，另三个**各自按名拒绝、各自说出缺什么**。

    ★读数里的 `profile_sha` 就是解的平方和 —— 这里逐位对上它。
    """
    M = _model()
    want = _read("closure_dispatch.json")["runs"]
    sums = {}
    for name in ("constant", "stiff"):
        y = np.asarray(M.transport(closure=name, **_DISPATCH)["y"], float)
        sums[name] = float(np.sum(y * y))
        assert sums[name] == want[name]["profile_sha"], (name, sums[name], want[name]["profile_sha"])
    assert sums["constant"] != sums["stiff"], "两个闭包给出了同一个解——分派退化成了一个"
    #: ★另三个的拒绝要**说出缺什么**：一句笼统的「不行」等于没拒
    for name, must_say in (("neoclassical", "b0"), ("given", "chi_given"), ("turbulent", "chi_turb")):
        with pytest.raises(Exception) as e:
            M.transport(closure=name, **_DISPATCH)
        assert must_say in str(e.value), (name, str(e.value))


def test_an_unknown_closure_is_refused_with_the_valid_set():
    """★无效名按名拒绝，并**列出有效集**——读者要知道该改成什么。"""
    M = _model()
    with pytest.raises(Exception) as e:
        M.transport(closure="no-such-closure", **_DISPATCH)
    msg = str(e.value)
    assert "no-such-closure" in msg, msg
    for valid in ("constant", "stiff", "neoclassical", "given", "turbulent"):
        assert valid in msg, (valid, msg)


def test_every_closure_that_runs_answers_with_the_same_keys():
    """★统一前端：跑通的闭包输出同一套键（11 个）——下游不必按闭包分支读。"""
    M = _model()
    keys = {name: frozenset(M.transport(closure=name, **_DISPATCH)) for name in ("constant", "stiff")}
    assert len(set(keys.values())) == 1, keys
    assert len(next(iter(keys.values()))) == 11, keys


# ═══════════════════════════════════════════ tr-coupling-nn-weights-external · FR-TR-013

def test_no_weight_table_is_compiled_into_the_kernel():
    """★★内核源码里的常量权重表 = 0 —— 内核只装算术，数在文件里。

    ★这是一条**结构判据**，最会一声不响地腐烂：加一张 `const W: [f64; N]`，
    数值一个都不变，而记录当场不成立。
    """
    nn = KERNEL_SRC / "nn.rs"
    if not nn.is_file():
        pytest.skip("内核仓不在这台机器上")
    src = nn.read_text(encoding="utf-8")
    tables = re.findall(r"(?:const|static)\s+[A-Z_0-9]+\s*:\s*&?\[f64", src)
    assert tables == [], f"nn.rs 里出现了常量权重表: {tables}"
    assert re.search(r"fn forward\([^)]*weights:\s*&\[f64\]", src), "nn::forward 不再把权重当入参收"


def test_the_models_live_outside_the_package():
    """★权重在仓根 `models/`，**不在包里**；打包只收 `fylite*`。"""
    npz = sorted(p.name for p in (ROOT / "models").glob("*.npz"))
    assert npz == ["epednn.npz", "qlknn_7_11.npz", "sat2_em_d3d_azf-1.npz"], npz
    assert not list((ROOT / "python" / "fylite").rglob("*.npz")), "有 .npz 进了包目录"
    toml = (ROOT / "python" / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'include\s*=\s*\[\s*"fylite\*"\s*\]', toml), "packages.find 不再只收 fylite*"
    for lic in ("EPEDNN-LICENSE", "TGLFNN-LICENSE", "FUSION-SURROGATES-LICENSE"):
        assert (ROOT / "models" / lic).is_file(), f"缺许可证 {lic}"


def test_the_checkout_reaches_its_own_models(monkeypatch):
    """★★干净检出里 `nn.available()` 就该列出 `models/` 里的三个。

    ★2026-09-18 补这道门时它返回 `[]`：`BUILTIN_DIR` 还指着 09-01 就改名掉的
    `nn_tables/`，而 `models/README.md` 的示例（`nn.available()`）因此跑不通——
    这条路**此前一道测试都没有**。
    """
    monkeypatch.delenv("FYLITE_NN_DIR", raising=False)
    from fylite import nn
    assert nn.available() == ["epednn", "qlknn_7_11", "sat2_em_d3d_azf-1"], nn.available()


def test_a_missing_model_is_refused_by_name(monkeypatch):
    """★缺它则在用到的那一点按名拒绝，不是在导入时，也不是返回一个空代理。"""
    monkeypatch.delenv("FYLITE_NN_DIR", raising=False)
    from fylite import nn
    with pytest.raises(nn.NNDataMissing) as e:
        nn.load("no-such-model")
    assert "no-such-model" in str(e.value), str(e.value)


# ════════════════════════════════════════════ tr-closure-15d-source-switches · FR-TR-004/009

_SWITCHES = {"pedestal": {"pedestal": True}, "current": {"current": True},
             "density": {"density": True}, "dt_target": {"dt_target": 0.02}}


@pytest.fixture(scope="module")
def sweep() -> dict:
    M = _model()
    from fylite.engine import cases
    try:
        base = cases.plan("evolve-iter-15ma")["arguments"]
    except SystemExit as e:
        pytest.skip(f"evolve-iter-15ma 不可用: {e}")
    out = {"baseline": M.evolve(**base)}
    for name, ov in _SWITCHES.items():
        out[name] = M.evolve(**{**base, **ov})
    return {"runs": out, "base": base, "M": M}


def test_the_switch_sweep_reproduces_its_recorded_readings(sweep):
    """★每一档的 `p_alpha` 与读数**逐位**相同 —— 读数还作数的证据。"""
    want = _read("evolve15_switch_sweep.json")["variants"]
    for name, r in sweep["runs"].items():
        assert _last(r["p_alpha"]) == want[name]["p_alpha"]["last"], name


def test_the_energy_balance_holds_on_every_variant(sweep):
    """★★能量平衡在**每一档**上都 < 1e-12。

    ★记录原写「最劣残差 1.154e-13」——那只是基线那一档的；全部可跑变体里最劣的是
    台基那档 1.298e-13。门按全部变体判，而不是按基线。
    """
    worst = {n: _absmax(r["balance_worst"]) for n, r in sweep["runs"].items()}
    assert max(worst.values()) < 1e-12, worst
    assert max(worst, key=worst.get) == "pedestal", worst


def test_every_opened_switch_moves_at_least_one_output(sweep):
    """★打开的控件**至少改变一项产出**——否则它是死的，而死控件看起来和活的一样。"""
    base = sweep["runs"]["baseline"]
    probe = ("p_alpha", "p_rad", "t_ped", "ne", "ni", "q", "psi", "te")
    for name in _SWITCHES:
        r = sweep["runs"][name]
        moved = [k for k in probe if k in r and k in base
                 and not np.array_equal(np.asarray(r[k], float), np.asarray(base[k], float))]
        assert moved, f"{name} 打开了却什么都没动"


def test_the_sawtooth_is_refused_without_the_current_channel(sweep):
    """★锯齿的触发是 q(0) < 1，而 q 只在解电流扩散时才有——所以不开电流就按名拒绝。"""
    with pytest.raises(Exception) as e:
        sweep["M"].evolve(**{**sweep["base"], "sawtooth": True})
    assert "current" in str(e.value), str(e.value)


def test_the_driven_currents_are_still_zero(sweep):
    """★★**记名的缺口**：驱动电流三道在所有变体里恒为零。

    这道门守的是一个**负面结果**：本册判这一格 inconclusive，因为量不到。
    ★哪天有人给 1.5D 接上了 CD 波源，这道门会红——**那正是它该红的时候**：
    记录要跟着改，从「量不到」变成真量一次。
    """
    for name, r in sweep["runs"].items():
        for k in ("j_bs", "j_cd", "j_lh"):
            assert _absmax(r[k]) == 0.0, (name, k, _absmax(r[k]))


# ═════════════════════════════════════════════════ tr-closure-dt-burn-astra · FR-TR-004

#: 内核的常数（`zerod.rs::E_ALPHA_FRACTION`）与两个参照
_ALPHA_FRACTION = 0.2013


def test_the_alpha_share_is_the_hardcoded_constant_at_every_operating_point():
    """★★α 份额在差得很远的工作点上都**恰好**是 0.2013 —— 它是一个写死的常数。

    ★这条门把记录里那句「α 份额偏 +1.23 %，而分支比是常数、本该到舍入——等内核查」
    **答上了**：偏差来自 `E_ALPHA_FRACTION = 0.2013`，与它自己的注释 `3.52/17.59`
    差 +0.59 %，与本册参照 `3.5/17.6` 差 +1.23 %。★这条记录挂着「不改内核、保留负面结果」
    的裁定，所以常数不动——门钉住它，**常数一动门就红**，记录得跟着改。
    """
    M = _model()
    for ne, te in ((1e20, 20.0), (6e19, 12.0), (1.2e20, 28.0)):
        r = M.zerod(time=np.array([0.0, 1.0]), ne_flattop=ne, te_flattop=te, dt_fraction=0.5)
        share = _last(r["p_alpha"]) / _last(r["p_fus"])
        assert share == pytest.approx(_ALPHA_FRACTION, rel=1e-12), (ne, te, share)


def test_the_alpha_share_offsets_are_the_recorded_ones():
    """★两个偏差都是从同一个常数算出来的——钉住它们，是钉住「偏差的成因」。"""
    assert _ALPHA_FRACTION / (3.52 / 17.59) - 1.0 == pytest.approx(5.928125e-3, rel=1e-9)
    rec = _read("dt_burn_astra_metrics.json")["compare"]["alpha_share_vs_3p5_over_17p6"]
    assert _ALPHA_FRACTION / (3.5 / 17.6) - 1.0 == pytest.approx(rec, rel=1e-9)


# ══════════════════════════════════════════ tr-pedestal-zerod-bookkeeping-metis · FR-TR-014

def test_the_zerod_volume_is_the_d_shape_and_lands_on_metis():
    """★★0D 的体积是带三角度的 D 形积分（2026-09-18 起，`FR-TR-014` 的缺口补上）——四个工作点逐位等于读数，
    对 METIS 落在 ±0.25 % 内；不给 `delta` 时仍是 `2 π² R a² κ`，逐位。

    ★此前这里钉的是椭圆公式与它高出 METIS 的 2.87 %（当时的裁定是「保留负面结果」）；用户 2026-09-18
    要求补上这一格，旧值并列留在读数里（`rel_ellipse_before_2026_09_18`）。
    """
    M = _model()
    for p in _read("zerod_metis_metrics.json")["points"]:
        o = p["overrides"]
        r = M.zerod(time=np.array([0.0, p["t_s"]]), **o)
        v = _last(r["volume"])
        assert v == p["volume_m3"]["fylite"], (p["case"], v)
        assert abs(p["volume_m3"]["rel"]) < 2.5e-3, (p["case"], p["volume_m3"]["rel"])
        assert 0.0283 < p["volume_m3"]["rel_ellipse_before_2026_09_18"] < 0.0288
        flat = {k: v for k, v in o.items() if k != "delta"}
        v0 = _last(M.zerod(time=np.array([0.0, p["t_s"]]), **flat)["volume"])
        assert v0 == 2.0 * np.pi ** 2 * o["r0"] * o["a"] ** 2 * o["kappa"], (p["case"], v0)


def test_what_is_left_of_the_volume_gap_is_the_separatrix_not_the_formula():
    """★补上之后剩下的 ±0.2 % 随时刻走（+0.08 → −0.20 %）——METIS 在 ITER 上积的是它的**分离面**，
    而分离面不恰好是 (R, a, κ, δ) 那条 D；分离面积分本身对 METIS 逐位（读数 `zerod_metis_attribution.json`）。
    """
    rel = [p["volume_m3"]["rel"] for p in _read("zerod_metis_metrics.json")["points"]]
    assert max(rel) - min(rel) < 3e-3, rel
    att = _read("zerod_metis_attribution.json")["volume"]["by_case"]["ITER_rampup_ECCD"]
    assert all(x["separatrix_rel"] is not None and abs(x["separatrix_rel"]) < 3e-4 for x in att)


def _metis_csv():
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    p = (store / "FYDOC-CASE-10-metis" / "corpus" / "metis_cert_zerod.csv") if store else None
    if p is None or not p.is_file():
        pytest.skip("no CASE-10 METIS corpus (set $FYDOC_ORACLE)")
    import csv
    rows = [r for r in csv.reader(line for line in p.open(encoding="utf-8") if not line.startswith("#"))]
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def _metis_dshape_volume(r0, a, kappa, delta):
    """METIS `zgeo0.m` without a separatrix：`R = R0 + a cos(u + asin(δ) sin u)`、`Z = aκ sin u`，201 点梯形。"""
    t = np.arcsin(max(0.0, min(1.0, delta)))
    u = np.linspace(0.0, 2.0 * np.pi, 201)
    r = r0 + a * np.cos(u + t * np.sin(u))
    z = a * kappa * np.sin(u)
    dr = -a * np.sin(u + t * np.sin(u)) * (1.0 + t * np.cos(u))
    return float(np.trapezoid(2.0 * np.pi * r * (-z * dr), u))


def test_the_metis_volume_is_its_own_boundary_so_the_gap_is_the_ellipse():
    """★★体积那处 2.87 % 归因到公式一级（2026-09-18）：METIS 的体积就是**它那条边界**围出来的体积。

    没有分离面的 8 个算例上，`zgeo0.m` 的 D 形积分复现 METIS 到 1.2e-3；ITER 一族（记录用的那四点）
    D 形复现到 ±0.25 %，而 `2π²Ra²κ`（0D 的公式）一律高 2.84–2.87 %——差的正是三角形变把截面往内挪的那一块。
    有分离面的 20 个算例由分离面积分复现（读 .mat，钉在读数里）。★内核不动：用户裁定「保留负面结果」。
    """
    rec = _read("zerod_metis_attribution.json")["volume"]
    by = rec["by_case"]
    for r in _metis_csv():
        vp = float(r["vp_m3"])
        args = [float(r[k]) for k in ("R_m", "a_m", "kappa_geo", "delta_geo")]
        rel = (_metis_dshape_volume(*args) - vp) / vp
        want = [x for x in by[r["case"]] if abs(x["t_s"] - float(r["t_s"])) < 1e-9][0]
        assert rel == pytest.approx(want["dshape_rel"], rel=1e-9, abs=1e-12)
        if want["separatrix_rel"] is None:
            assert abs(rel) < 2e-3, (r["case"], rel)
        if r["case"].startswith(("ITER_rampup", "iter_2nbi", "reference_NTM")):
            ell = (2.0 * np.pi ** 2 * args[0] * args[1] ** 2 * args[2] - vp) / vp
            assert 0.0283 < ell < 0.0288 and abs(rel) < 2.5e-3, (r["case"], ell, rel)
    assert rec["separatrix_integral_vs_metis_worst"] < 6e-3
    assert rec["cases_with_separatrix"] + rec["cases_without"] == 28


def test_the_thermal_energy_is_bracketed_by_the_peaking_convention_not_judged():
    """★W_th 判不了，且读数说清了为什么：0D 的剖面形状由固定峰化指数定。

    喂体平均（记录的做法）偏 −64…−69 %，喂 METIS 自己的轴值偏 +29…+80 %——真值在两者之间，
    落在哪取决于峰化约定，而不是能量账。★METIS 自己的账是闭合的：存下的 W_th 对它自己剖面的积分 ≤ 0.13 %。
    """
    w = _read("zerod_metis_attribution.json")["w_th"]
    assert all(abs(x) < 1.3e-3 for x in w["metis_wth_vs_own_profile_integral"])
    assert all(-0.70 < x < -0.63 for x in w["fed_volume_averages_into_axis_slots_rel"])
    assert all(0.28 < x < 0.81 for x in w["fed_metis_axis_values_rel"])
