"""FR-EQ-015: the device linear model — zero-plasma limit against the bare circuit, γ travels with the
export, and the carrier is em_coupling."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from fylite.scenario.control import lti

ROOT = Path(__file__).resolve().parents[2]


def test_a_single_loop_decays_at_minus_r_over_l():
    m = lti.linear_model([[2e-3]], [0.5])
    assert m.A.shape == (1, 1) and m.A[0, 0] == -0.5 / 2e-3


def test_two_coupled_loops_have_the_closed_form_eigenvalues():
    """★零等离子体极限：A = −M⁻¹R 的本征值是 det(λM + R) = 0 的两根——
    (L1 L2 − M12²) λ² + (L1 R2 + L2 R1) λ + R1 R2 = 0。"""
    L1, L2, M12, R1, R2 = 3e-3, 1.2e-3, 1.1e-3, 0.4, 0.9
    m = lti.linear_model([[L1, M12], [M12, L2]], [R1, R2])
    a, b, c = L1 * L2 - M12 ** 2, L1 * R2 + L2 * R1, R1 * R2
    want = np.sort(np.roots([a, b, c]).real)
    got = np.sort(np.linalg.eigvals(m.A).real)
    assert np.allclose(got, want, rtol=1e-12, atol=0.0), (got, want)
    assert m.gamma < 0.0


def test_the_rigid_tier_is_a_rank_one_update_of_the_static_one():
    """刚性档对静止档恰是一次秩一修正：M_eff⁻¹ 由 Sherman–Morrison 给出，两档的 A 之差逐元对上。
    ★（「I_p → 0 时刚性档退回静止档」**不是**一个极限：没有等离子体电流就没有刚性竖直模，k_ideal = 0，刚性档按名拒绝。）"""
    rng = np.random.default_rng(3)
    X = rng.normal(size=(5, 5))
    M = X @ X.T * 1e-3 + np.eye(5) * 1e-3
    R = rng.uniform(0.1, 1.0, 5)
    G = rng.normal(size=5) * 1e-4
    ip = 3e5
    k_ideal = ip * ip * float(G @ np.linalg.solve(M, G))
    k = 0.4 * k_ideal
    s = lti.linear_model(M, R, plasma_response="static")
    r = lti.linear_model(M, R, plasma_response="rigid", ip=ip, G=G, k=k)
    Mi = np.linalg.inv(M)
    u = Mi @ G
    c = ip * ip / k
    Meff_inv = Mi + c * np.outer(u, u) / (1.0 - c * float(G @ u))
    want = -Meff_inv @ np.diag(R)
    assert np.allclose(r.A, want, rtol=1e-9, atol=1e-9 * np.abs(want).max())
    assert r.gamma > 0.0 > s.gamma
    with pytest.raises(lti.ModelRefused, match="ideal"):
        lti.linear_model(M, R, plasma_response="rigid", ip=0.0, G=G, k=1e5)


def test_one_loop_and_a_rigid_plasma_reproduce_the_dispersion_root():
    """★γ 随导出：单回路 + 刚性等离子体的色散根 γ = kR/(I_p² G² − kL)——FR-EQ-016 那条色散关系的闭式。"""
    L, R, G, ip = 2e-3, 0.5, 3e-6, 4e5
    k = 300.0                                  #: k_ideal = I_p² G²/L = 720 N/m：阻性壁档
    m = lti.linear_model([[L]], [R], plasma_response="rigid", ip=ip, G=[G], k=k)
    want = k * R / (ip * ip * G * G - k * L)
    assert want > 0.0 and abs(m.gamma - want) < 1e-12 * want


def test_beyond_the_ideal_limit_the_export_is_refused():
    L, R, G, ip = 2e-3, 0.5, 3e-6, 4e5
    k_ideal = ip * ip * G * G / L
    with pytest.raises(lti.ModelRefused, match="ideal"):
        lti.linear_model([[L]], [R], plasma_response="rigid", ip=ip, G=[G], k=1.01 * k_ideal)
    #: 阻性壁档一侧照常导出，γ 在逼近理想极限时发散（有限但大）
    near = lti.linear_model([[L]], [R], plasma_response="rigid", ip=ip, G=[G], k=0.99 * k_ideal).gamma
    far = lti.linear_model([[L]], [R], plasma_response="rigid", ip=ip, G=[G], k=0.5 * k_ideal).gamma
    assert near > far > 0.0


def test_the_plasma_response_is_a_parameter_and_the_unimplemented_tier_is_named():
    for bad in ("perturbed_gs", "deformable"):
        with pytest.raises(lti.ModelRefused, match="plasma_response"):
            lti.linear_model([[1e-3]], [0.1], plasma_response=bad)
    with pytest.raises(lti.ModelRefused, match="needs G and k"):
        lti.linear_model([[1e-3]], [0.1], plasma_response="rigid")


def test_the_carrier_is_em_coupling_and_its_fields_exist():
    table = (ROOT / "rust/fylite_runtime/ids/em_coupling.tsv").read_text().splitlines()
    leaves = {line.split("\t")[0] for line in table if not line.startswith("#")}
    assert set(lti.EM_COUPLING_FIELDS) <= leaves
    m = lti.linear_model([[2e-3, 5e-4], [5e-4, 1e-3]], [0.5, 0.2], B_act=[[1.0], [0.0]], C=[[1.0, 0.0], [0.3, 0.7]])
    doc = lti.to_em_coupling(m)
    names = [c["name"] for c in doc["coupling_matrix"]]
    assert names == ["M_eff", "R", "A", "B", "C", "D"]
    for c in doc["coupling_matrix"]:
        d = np.asarray(c["data"])
        assert d.shape == (len(c["rows_uri"]), len(c["columns_uri"]))
    assert json.loads(doc["code"]["parameters"])["gamma_per_s"] == m.gamma


# ----------------------------- EAST, through the kernel door ----------------------------- #
CASE = "FYDOC-CASE-23-east-137985-efit-east"


@pytest.fixture(scope="module")
def east():
    from fylite.engine import benchmark as bm
    store = bm.store_dir()
    if store is None or not (store / CASE / "case.yaml").is_file():
        pytest.skip(f"no {CASE} in the case store (set $FYDOC_ORACLE)")
    spec = importlib.util.spec_from_file_location("benchmark_wall_vstab", ROOT / "tools" / "benchmark-wall-vstab.py")
    tool = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(tool)
        dev = tool.east_card()
    except Exception as e:  # noqa: BLE001 — no card / runtime: skip by name
        pytest.skip(f"no EAST device card / runtime library here: {e}")
    from fylite import fyo
    from fylite.scenario.control.vertical import vertical_system
    g, a, _ = tool.kefit_slice(store / CASE)
    return vertical_system(fyo.as_equilibrium(g), coil_aturns=np.asarray(a["ccbrsp"], float)[:12],
                           eta_coil_uohm_m=0.0, device=dev, passive_groups=tool.GROUPS, coarsen=1)


def test_on_east_the_exported_gamma_is_the_kernels_growth_rate(east):
    m = lti.from_vertical_system(east, plasma_response="rigid")
    rel = abs(m.gamma - east.gamma_openloop) / east.gamma_openloop
    print(f"[register] EAST #137985：导出 γ {m.gamma:.6g} /s，门的 γ {east.gamma_openloop:.6g} /s，相对 {rel:.2e}；"
          f"静止档 γ {lti.from_vertical_system(east, plasma_response='static').gamma:.6g} /s；状态 {m.A.shape[0]} 维")
    assert rel < 1e-10
    #: ★静止档：EAST 的 12 个 PF 线圈超导（电阻 0），各给一个零衰减模——γ 恰为 0，不是负
    assert lti.from_vertical_system(east, plasma_response="static").gamma <= 1e-9
