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

def test_the_zerod_volume_is_the_elliptic_formula_at_every_metis_point():
    """★0D 的体积**恰好**是 `2 π² R a² κ` —— 四个工作点逐位，并与读数逐位相同。

    ★这正是它比 METIS 高 2.87 % 的原因：METIS 用带三角度的形状体积，这里是纯椭圆截面。
    **公式差，一次可修**——这条记录挂着「保留负面结果」的裁定，所以门钉住现状。
    """
    M = _model()
    for p in _read("zerod_metis_metrics.json")["points"]:
        o = p["overrides"]
        r = M.zerod(time=np.array([0.0, p["t_s"]]), **o)
        v = _last(r["volume"])
        assert v == 2.0 * np.pi ** 2 * o["r0"] * o["a"] ** 2 * o["kappa"], (p["case"], v)
        assert v == p["volume_m3"]["fylite"], (p["case"], v)


def test_the_volume_gap_to_metis_is_systematic_not_scattered():
    """★四个工作点上的相对差散布只有 1.3e-4 —— 偏差是**系统性**的，所以是公式，不是噪声。"""
    rel = [p["volume_m3"]["rel"] for p in _read("zerod_metis_metrics.json")["points"]]
    assert all(0.028 < r < 0.029 for r in rel), rel
    assert max(rel) - min(rel) < 2e-4, rel
