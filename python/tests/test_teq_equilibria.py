"""C-06：ITER 参考平衡集（TEQ / CORSICA 写出）满不满足本仓的 Grad–Shafranov 律。

★★**问的是「两边对同一个方程是不是同一个理解」**。参考侧是 ITER 的机构参考平衡，
由 CORSICA 的自由边界求解器 TEQ 写出（**代码名读自 g-file 首行** `TEQ g … #900003`，
不是从标题推断的）；本仓这一侧是 `fylite.engine.physics` 的定律级判据
`Δ*ψ = −μ₀R²p′ − f f′`，只在边界内取内点。一份平衡满不满足 GS，与谁写的它无关。

实测（2026-09-08，中分辨率 129×257）
------------------------------------
=================  ===========  ==========  ===============================
文档                残差         内点        备注
=================  ===========  ==========  ===============================
`2V2XYR` 15 MA 燃烧  1.487e-02   11 845      —
`2V3FDF`  9 MA 稳态  1.357e-02   11 863      —
`34S6TV` 15 MA SOF   2.297e-04   11 930      **比两个燃烧点好六十倍**
（对照：仓内合成件      1.474e-04    3 838）
=================  ===========  ==========  ===============================

★**符号支毫不含糊**：另一支（`Δ*ψ = +μ₀R²p′ + ff′`）在每一份上都给 ~2.0，
即约定一致，不需要任何 COCOS 翻转。这一条本身就是一次口径确认。

★★★**残差随网格只掉一阶，不是二阶**——同一份平衡的三种分辨率（该文档自带）：

    LR  65×129   3.665e-02
    MR 129×257   1.487e-02      比 0.406
    HR 257×513   7.948e-03      比 0.534   （h² 应给 0.250）

二阶差分作用在光滑解上应当每加密一倍掉到四分之一。掉一半 ⇒ **残差里有一部分不是
算子的截断误差**：候选是 p′/ff′ 是**表格值**（插值精度有限）、或解自身在边缘不够光滑
（两个燃烧点比 SOF 差六十倍，与「陡边缘主导」一致）。**本门不下这个结论**，只把标度记下来。

★★**因此判决与分辨率绑定**：0.02 的带在 MR / HR 上通过，在 **LR 上不通过**（3.7e-2）。
同一份物理平衡，换个网格就换个判决——所以这条记录的带**必须点名分辨率**，
而下面的断言各判各的分辨率，不混着判。

语料：ITER IDM 件（Internal Use），在本机 `data/ITER Scenario/` 之下、**不在任何仓里**；
够不到就 skip 并点名。
"""
from __future__ import annotations

import os
import pathlib

import pytest

ROOT = pathlib.Path(os.environ.get(
    "ITER_SCENARIO_ROOT", str(pathlib.Path.home() / "workspace/data/ITER Scenario")))

BURN = ROOT / ("15MA_plasma_of_inductive_scenario_at_bur_2V2XYR_v1_4/"
               "15MA inductive - burn/Standard domain R-Z")
CASES = {
    "2V2XYR-15MA-burn": BURN / "Medium resolution - 129x257" / "g900003.00230_ITER_15MA_eqdsk16MR.txt",
    "2V3FDF-9MA-ss": ROOT / ("9MA_plasma_of_steady_state_scenario_at_b_2V3FDF_v1_3/"
                             "9MA steady state - burn/Standard domain R-Z/Medium resolution - 129x257/"
                             "g900004.00230_ITER_09MA_eqdsk14MR.txt"),
    "34S6TV-15MA-sof": ROOT / ("Representative_plasma_of_15MA_inductive__34S6TV_v1_2/"
                               "15MA inductive - SOF/Standard domain R-Z/Medium resolution - 129x257/"
                               "g900005.00080_ITER_15MA_eqdsk14MR.txt"),
}
RESOLUTIONS = {
    "LR": BURN / "Low resolution - 65x129" / "g900003.00230_ITER_15MA_eqdsk16LR.txt",
    "MR": BURN / "Medium resolution - 129x257" / "g900003.00230_ITER_15MA_eqdsk16MR.txt",
    "HR": BURN / "High resolution - 257x513" / "g900003.00230_ITER_15MA_eqdsk16HR.txt",
}

#: 中分辨率上的带。★实测最劣 1.487e-02，带取 2e-2 并**点名分辨率**——
#: 同一份平衡在 LR 上是 3.7e-2，判决换网格就换。
BAND_MR = 2.0e-2


def _residual(path: pathlib.Path) -> float:
    from fylite.engine import physics as ph, suite as sc
    rec, _ = sc.record_from_products([str(path)])
    r = ph._c_grad_shafranov(ph.Reader(sc.datasets_of(rec)), {})
    if r.measured is None:
        pytest.fail(f"{path.name}: 评不了 —— {r.detail}")
    return float(r.measured)


@pytest.fixture(scope="module", autouse=True)
def _corpus():
    missing = [k for k, p in CASES.items() if not p.is_file()]
    if missing:
        pytest.skip(f"没有 ITER IDM 平衡件（Internal Use）：{missing}；根 = {ROOT}")


@pytest.mark.parametrize("name", sorted(CASES))
def test_the_reference_equilibrium_satisfies_our_grad_shafranov(name):
    got = _residual(CASES[name])
    assert got <= BAND_MR, f"{name}: 残差 {got:.3e}（中分辨率带 {BAND_MR:.0e}）"


def test_the_sign_convention_needs_no_flip():
    """★另一符号支应当**远差**。它若变得同样小，说明这份文档的 ψ 或源函数换了约定，
    而那时「满足 GS」这句话就不再指同一件事。"""
    from fylite.engine import physics as ph, suite as sc
    rec, _ = sc.record_from_products([str(CASES["2V2XYR-15MA-burn"])])
    r = ph._c_grad_shafranov(ph.Reader(sc.datasets_of(rec)), {})
    other = float(r.detail.split("另一符号支")[1].strip(" （）").split("）")[0])
    assert other > 1.0, f"另一支只有 {other:.3e}——符号约定不再无歧义"
    assert not r.caveat, f"判据自己报了符号告警：{r.caveat}"


def test_the_residual_falls_only_first_order_with_the_grid():
    """★★★这条钉的是**读法**：残差不是纯粹的算子截断误差。

    二阶差分作用在光滑解上，网格加密一倍残差应当掉到 1/4。实测掉到约 1/2
    （0.406 · 0.534），所以残差里有一部分来自别处——表格化的 p′/ff′，或解自身在
    边缘的不光滑。**本条不判定是哪一个**，它判定的是「不要把这个残差读成算子误差」。
    它若哪天真的掉到 1/4，这条会红，而那说明来源变了，值得有人看一眼。"""
    missing = [k for k, p in RESOLUTIONS.items() if not p.is_file()]
    if missing:
        pytest.skip(f"缺分辨率件：{missing}")
    r = {k: _residual(p) for k, p in RESOLUTIONS.items()}
    for a, b in (("LR", "MR"), ("MR", "HR")):
        ratio = r[b] / r[a]
        assert 0.30 < ratio < 0.75, (
            f"{a}→{b} 残差比 {ratio:.3f}：{'掉到二阶了' if ratio <= 0.30 else '几乎不降'}"
            f"——残差的来源与 2026-09-08 实测（0.406 / 0.534）不同了")


def test_the_verdict_depends_on_the_resolution_and_that_is_recorded():
    """★★同一份物理平衡，低分辨率上**不通过**中分辨率的带。

    这不是缺陷，是判据的性质；写成断言，免得日后有人把 LR 的件塞进来、
    看到红色去怀疑平衡。"""
    if not RESOLUTIONS["LR"].is_file():
        pytest.skip("缺低分辨率件")
    assert _residual(RESOLUTIONS["LR"]) > BAND_MR, (
        "低分辨率件现在过得了中分辨率的带——带与分辨率的绑定关系变了，须重新记")
