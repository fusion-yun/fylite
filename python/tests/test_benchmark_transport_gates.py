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
    `3.52/17.59` 差 +0.59 %——与工作点无关，是一个常数（2026-09-19 已改为 3.52/17.59 本身）；
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
    #: ★哪一档最劣随内核动（2026-09-19 α 份额改后不再是台基那档）——门判全部变体，并逐档对上读数
    want = _read("evolve15_switch_sweep.json")["variants"]
    for n, w in worst.items():
        assert w == want[n]["balance_worst"], (n, w, want[n]["balance_worst"])


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


def test_the_current_switch_alone_feeds_the_driven_channels_nothing(sweep):
    """★开关扫描里的 `current` 档只**打开**电流道，不给源——所以三道在那一档仍是零。
    这是算例的姿态，不是缺口：给了源的那一次见下一道门。"""
    for name, r in sweep["runs"].items():
        for k in ("j_bs", "j_cd", "j_lh"):
            assert _absmax(r[k]) == 0.0, (name, k, _absmax(r[k]))


def _evolve15_tool():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bev15", ROOT / "tools" / "benchmark-evolve15.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_driven_currents_answer_when_their_sources_are_given(sweep):
    """★★FR-TR-004（2026-09-19 转成立）：驱动电流三道**各开自己的源**就有数——自举给非零 j_bs；
    给定 CD 的沉积积分闭合到舍入（1 MA / 2 MA 两档）。★此前「恒为零」是因为开关扫描只开了电流道、没给源。
    ★束与 LH 执行器的逐位对拍在内核仓 `tests/test_evolve_executors_code.py`（EAST g-file）。门从公开入口重算，逐位对上读数。"""
    got = _evolve15_tool().driven_currents(sweep["M"], sweep["base"])["runs"]
    want = _read("evolve15_driven_currents.json")["runs"]
    assert got == want
    assert want["bootstrap"]["j_bs"] > 1e5 and want["bootstrap"]["j_cd"] == 0.0
    for name in ("i_cd_1MA", "i_cd_2MA"):
        assert abs(want[name]["i_cd_rel_error"]) < 1e-12, want[name]
        assert want[name]["j_cd"] > 0.0 and want[name]["balance_worst"] < 1e-12
    #: 线性：2 MA 的峰值恰是 1 MA 的两倍
    assert want["i_cd_2MA"]["j_cd"] == pytest.approx(2.0 * want["i_cd_1MA"]["j_cd"], rel=1e-12)


# ═══════════════════════════════════════════════════ tr-pedestal-eped-feedback · FR-TR-009

def test_the_pedestal_feedback_settles_on_the_eped_target(sweep):
    """★★FR-TR-009：台基反馈（EPED1-NN 每步定下一步的边界，滞后一步）推到收敛。

    滞后一步，所以末步的相对步长**就是**「边界离 EPED-NN 目标还有多远」——收敛到目标即它趋零。
    ★α 关（定 χ 下开 α 会热失控，没有不动点可到）：末步 < 1e-6，且 NN 输入始终在训练箱内（外推 0）。
    ★α 开那一档照录为读数：状态被推出训练箱（外推 > 0）——正是本域开篇说的「不报错的外推」，门钉住它照实报出来。
    门从公开入口重跑，逐位对上读数。
    """
    tool = _evolve15_tool()
    got = tool.pedestal_feedback(sweep["M"], sweep["base"])
    want = _read("pedestal_eped_feedback.json")
    assert got["runs"] == want["runs"]
    off, on = want["runs"]["alpha_off"], want["runs"]["alpha_on"]
    assert off["rel_step_last"] < 1e-6 and off["rel_step_last"] < off["rel_step_mid"], off
    assert off["ped_extrapolation"] == 0.0, off
    assert on["ped_extrapolation"] > 0.0 and on["rel_step_last"] > 1e-4, on


# ═════════════════════════════════════════════════ tr-closure-dt-burn-astra · FR-TR-004

#: 内核的常数（`zerod.rs::E_ALPHA_FRACTION`）：α 与 DT 反应的 Q 值之比本身（2026-09-19 由 0.2013 改）
_ALPHA_FRACTION = 3.52 / 17.59


def test_the_alpha_share_is_the_q_value_ratio_at_every_operating_point():
    """★★α 份额在差得很远的工作点上都**恰好**是 3.52/17.59——α 的 Q 值对反应的 Q 值。

    ★此前是写死的 0.2013（与它自己的注释 `3.52/17.59` 差 +0.59 %），这道门那时钉的是那个常数、
    挂着「常数一动门就红」。用户 2026-09-19「close FR-TR-*」之后常数改成比值本身，门跟着改。
    """
    M = _model()
    for ne, te in ((1e20, 20.0), (6e19, 12.0), (1.2e20, 28.0)):
        r = M.zerod(time=np.array([0.0, 1.0]), ne_flattop=ne, te_flattop=te, dt_fraction=0.5)
        share = _last(r["p_alpha"]) / _last(r["p_fus"])
        assert share == pytest.approx(_ALPHA_FRACTION, rel=1e-12), (ne, te, share)


def test_the_alpha_share_against_the_rounded_branching_is_the_rounding():
    """★对本册旧参照 3.5/17.6 的 +0.63 % 是**那个参照的四舍五入**，不是实现差——读数记的就是它。"""
    rec = _read("dt_burn_astra_metrics.json")["compare"]
    assert rec["alpha_share_vs_q_values"] == pytest.approx(0.0, abs=1e-12)
    assert rec["alpha_share_vs_3p5_over_17p6"] == pytest.approx(_ALPHA_FRACTION / (3.5 / 17.6) - 1.0, rel=1e-9)
    assert 0.006 < rec["alpha_share_vs_3p5_over_17p6"] < 0.0065


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


def test_like_for_like_w_agrees_only_by_cancellation():
    """★★约定对齐之后 W 对 METIS ±0.2 %——但读数把它拆开了：不计稀释与体平均加权各自是几个百分点，
    相消才落进带里。这道门守的是**拆开的那几项**，从 CASE-10 的剖面当场重算，而不是那个 ±0.2 %。
    """
    rec = _read("zerod_metis_attribution.json")["w_th_like_for_like"]["points"]
    rows = {(r["case"], round(float(r["t_s"]), 4)): r for r in _metis_csv()}
    x = np.linspace(0.0, 1.0, 21)
    e = 1.602176634e-19
    for p in rec:
        r = rows[(p["case"], round(p["t_s"], 4))]
        a = {k: np.array([float(r[f"{k}_{i:02d}"]) for i in range(21)]) for k in ("nep", "tep", "tip", "nip", "vpr")}
        w0 = 1.5 * e * np.trapezoid((a["nep"] * a["tep"] + a["nip"] * a["tip"]) * a["vpr"], x)
        w1 = 1.5 * e * np.trapezoid(a["nep"] * (a["tep"] + a["tip"]) * a["vpr"], x)
        v = np.trapezoid(a["vpr"], x)
        te_r = np.trapezoid(a["tep"] * 2.0 * x, x) / (np.trapezoid(a["tep"] * a["vpr"], x) / v) - 1.0
        dec = p["decomposition"]
        assert w1 / w0 - 1.0 == pytest.approx(dec["no_dilution_ni_eq_ne"], rel=1e-9)
        assert te_r == pytest.approx(dec["rho_weight_vs_metis_vpr_te_avg"], rel=1e-9)
        #: 相消：总差远小于任一分项
        assert abs(p["w_rel_total"]) < 0.25 * min(dec["no_dilution_ni_eq_ne"], dec["rho_weight_vs_metis_vpr_te_avg"])
        assert dec["no_dilution_ni_eq_ne"] > 0.02 and dec["rho_weight_vs_metis_vpr_te_avg"] > 0.05


def test_with_dilution_the_like_for_like_w_is_left_with_the_weighting_alone():
    """★稀释补上之后（`z_imp` 喂 METIS 自己的 C + Ar），W 的剩余偏差不再相消：−2.4…−3.4 %，
    方向与大小就是 0D 的椭圆加权（把 T 的体平均抬高、换成轴值就压低 W）。门从公开入口当场重算。"""
    M = _model()
    from fylite.scenario.model import Phases, Scenario, _zerod_plan
    from fylite.io import fydoc
    pts = _read("zerod_metis_attribution.json")["w_th_like_for_like"]["points"]
    over = {(p["case"], round(p["t_s"], 4)): p for p in _read("zerod_metis_metrics.json")["points"]}
    assert M is not None
    wth = {(r["case"], round(float(r["t_s"]), 4)): float(r["wth_J"]) for r in _metis_csv()}
    for p in pts:
        o = dict(over[(p["case"], round(p["t_s"], 4))]["overrides"])
        o.update(ne_flattop=p["fed"]["ne_axis"], te_flattop=p["fed"]["te_axis_keV"], peaking_n=p["fit"]["peaking_n"],
                 peaking_t=p["fit"]["peaking_t"], edge_frac=p["fit"]["edge_frac"], ti_over_te=p["fit"]["ti_over_te"],
                 zeff=p["diluted"]["zeff"], z_imp=6.0, z_imp2=18.0, r_imp2=0.06)
        ts = p["t_s"]
        ph = Phases(t_breakdown=0.0, t_rampup_end=1.0, t_flattop_end=ts + 10.0, t_end=ts + 20.0)
        rec = fydoc.complete("code/zerod", _zerod_plan(Scenario(**o, phases=ph), np.array([0.0, ts]), 41))
        w = _last(rec["fields"]["summary"]["global_quantities"]["energy_thermal"]["value"]["data"])
        wm = wth[(p["case"], round(ts, 4))]
        assert (w - wm) / wm == pytest.approx(p["diluted"]["w_rel"], rel=1e-9)
        assert -0.036 < p["diluted"]["w_rel"] < -0.022, p
        #: 稀释那一项正好是之前被相消掉的那一块
        assert p["diluted"]["w_rel"] < p["diluted"]["w_rel_undiluted"] - 0.02


def test_with_metis_s_own_volume_weight_the_like_for_like_w_lands_within_the_profile_form():
    """★★FR-TR-014 b：0D 体平均的权重换成 METIS 自己的 dV/dρ（绑 `dvolume_drho_tor`）之后，W 对 METIS
    +0.3…+1.0 %——剩下的只有幂律剖面形状那一项；嵌套 D 形面（κ(0)、位移取 METIS 自己的）夹在 2ρ 与它之间。
    门从公开入口逐点重算三种权重，轴值按各自的权重从 METIS 体平均换算（换算与平均用同一权重，不重复计）。"""
    import importlib.util
    assert _model() is not None
    spec = importlib.util.spec_from_file_location("bzw", Path(__file__).resolve().parents[2] / "tools" / "benchmark-zerod-weight.py")
    bzw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bzw)
    att = _read("zerod_metis_attribution.json")
    like = {(p["case"], round(p["t_s"], 4)): p for p in att["w_th_like_for_like"]["points"]}
    over = {(p["case"], round(p["t_s"], 4)): p["overrides"] for p in _read("zerod_metis_metrics.json")["points"]}
    rows = {(r["case"], round(float(r["t_s"]), 4)): r for r in _metis_csv()}
    pts = att["w_th_weighted"]["points"]
    assert len(pts) == 4
    for q in pts:
        key = (q["case"], round(q["t_s"], 4))
        shape = (q["shape"]["kappa_axis"], q["shape"]["shift_axis_m"])
        for v in ("circular", "shaped", "bound"):
            got = bzw.run_point(like[key], over[key], rows[key], v, shape)
            assert got["w_rel"] == pytest.approx(q[v]["w_rel"], rel=1e-9, abs=1e-12), (key, v)
        #: the judged cell: METIS's own geometry, within the 2 % the record states
        assert abs(q["bound"]["w_rel"]) < 0.02, q
        #: and the order the attribution says: 2ρ below, the D between, METIS's own weight above
        assert q["circular"]["w_rel"] < q["shaped"]["w_rel"] < q["bound"]["w_rel"], q
        #: the shape fed is METIS's: κ on axis below the edge's, the axis shifted outward
        assert 0.8 < shape[0] / float(rows[key]["kappa_geo"]) < 0.95 and 0.1 < shape[1] < 0.13
