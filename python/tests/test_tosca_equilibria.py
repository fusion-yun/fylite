"""C-07：TOSCA 的 ITER 平衡运行空间（li 扫描，61 份）对本仓的 Grad–Shafranov 律。

与 `C-06` 同一条判据、不同的问题：那边是三份**参考态**，这边是一整片**运行空间**
（`li` 0.57 → 1.20 × 四种 PF6/偏滤器设计变体，61 份 EQDSK，65×129）。一片扫描能答
一份参考态答不了的事——残差**随什么变**。

★**代码归属读自载荷本身**：61 份的首行都写着产码（45 份 `TOSCA_VT`、16 份 `From TOSCA`），
不必依赖随附报告的正文。登记册此前记的「归属是推断得来的」已经不成立。

★★★**先得修一个读入端的缺陷，这批才读得进来**（2026-09-08）。TOSCA 在三个整数
**之后**还写产码名——

    EQ_name : S2_2001_li065_a             02/26/2009   3  65 129 TOSCA_VT

而本仓的头一行解析取「最后两个 token」，注记还写着「只有尾部是可靠的」。**实测推翻了
那句话**：61 份一份也读不进来。三份文件（TOSCA · EAST 真炮 · 仓内合成）的列位**逐列
相同**（48/52/56），因为 `(a48, 3i4)` 本来就规定了那些列。解析改为**按位先行、尾部
兜底**，本批随即全数读入。

实测（2026-09-08，61 份全部评上，0 份符号告警）
------------------------------------------------
残差 min **1.62e-04** · 中位 **1.22e-02** · max **4.51e-02**。

★★**残差随 `li` 变，且不是平滑的趋势而是一个台阶**（Pearson −0.852）::

    li 0.57  4.32e-02      li 0.80  9.59e-03
    li 0.63  3.33e-02      li 0.85  1.38e-02
    li 0.70  1.92e-02      li 1.00  1.81e-04   ←
    li 0.73  1.19e-02      li 1.20  1.69e-04   ←

低 li（≤0.75）中位 1.95e-02，高 li（≥1.00）中位 1.70e-04——**相差 114 倍**，
而 0.85 → 1.00 之间一步就掉了 75 倍。高 li 那两档的残差与仓内**合成件**（1.47e-04）
和 TEQ 的 SOF 件（2.30e-04）同量级，即「这台算子在这个网格上能到的最好水平」。

〔推测，本门不判定〕一个平滑的物理效应不会这样跳；更像**两个子批次**（不同的求解设置
或不同的收敛判据）。要判定得看随附报告或问上游——所以本门只**钉住这个结构**：
低 li 显著差、高 li 达到本底、两者之间有台阶。

★因此**一条横跨全扫描的带是误导**：4.5e-2 的带对高 li 那两档松了两个数量级。
下面按档分别判。

语料：ITER IDM 件（Internal Use），在本机 `data/ITER Scenario/` 之下、不在任何仓里。
"""
from __future__ import annotations

import os
import pathlib
import re

import numpy as np
import pytest

ROOT = pathlib.Path(os.environ.get(
    "ITER_SCENARIO_ROOT", str(pathlib.Path.home() / "workspace/data/ITER Scenario")))
EQDSK = ROOT / ("Plasma_equilibrium_operational_space_dur_2ENZF5_v2_0/Operating space 15MA/"
                "Operating space 15MA-EQDSK")

#: 全扫描的上限（实测 max 4.51e-02，留一档）。★它只是**上限**，不是判据的全部：
#: 高 li 那两档要另判，否则这条带对它们松两个数量级。
BAND_ALL = 6.0e-2
#: 高 li（≥1.00）实测中位 1.70e-04，与合成件同量级。
BAND_HIGH_LI = 5.0e-4
#: 低/高 li 的差距实测 114 倍。钉住它**存在且大**。
MIN_LI_CONTRAST = 20.0


def _cases():
    out = []
    for p in sorted(EQDSK.rglob("*.EQDSK")):
        m = re.match(r"li(\d+)_(min|max)", p.stem)
        if m:
            out.append((int(m.group(1)) / 100.0, p))
    return out


@pytest.fixture(scope="module")
def measured():
    cases = _cases()
    if len(cases) < 20:
        pytest.skip(f"没有 TOSCA 平衡集（ITER IDM，Internal Use）：{EQDSK}")
    from fylite.engine import physics as ph, suite as sc
    rows = []
    for li, p in cases:
        rec, _ = sc.record_from_products([str(p)])
        r = ph._c_grad_shafranov(ph.Reader(sc.datasets_of(rec)), {})
        assert r.measured is not None, f"{p.name}: 评不了 —— {r.detail}"
        rows.append({"li": li, "res": float(r.measured), "flip": bool(r.caveat), "name": p.stem})
    return rows


def test_every_equilibrium_in_the_scan_is_readable(measured):
    """★★这一条是那次读入端修复的判据：61 份**一份不缺**。

    修复前它们整批读不进来（头一行三个整数之后还有产码名），而当时的错误信息是
    「GEQDSK header has no `nw nh`」——听起来像文件坏了，其实是本仓的解析比格式更严。"""
    assert len(measured) >= 60, f"只读进来 {len(measured)} 份"


def test_the_whole_scan_satisfies_grad_shafranov(measured):
    worst = max(measured, key=lambda r: r["res"])
    assert worst["res"] <= BAND_ALL, f"最劣 {worst['res']:.3e} 在 {worst['name']}（带 {BAND_ALL:.0e}）"


def test_the_sign_convention_holds_across_the_whole_scan(measured):
    """★61 份没有一份需要翻符号。单份可能巧合，一整片不会。"""
    flipped = [r["name"] for r in measured if r["flip"]]
    assert not flipped, f"这些份要求翻符号：{flipped[:5]}"


def test_the_high_li_end_reaches_the_operator_floor(measured):
    """★高 li 那两档应当达到本底（与仓内合成件同量级）。它若变差，是这批件变了，
    不是算子变了——因为合成件那条对照仍在别处判着。"""
    hi = np.array([r["res"] for r in measured if r["li"] >= 1.00])
    assert hi.size >= 8, f"高 li 只有 {hi.size} 份"
    assert np.median(hi) <= BAND_HIGH_LI, f"高 li 中位 {np.median(hi):.3e}（带 {BAND_HIGH_LI:.0e}）"


def test_the_residual_is_much_worse_at_low_li_and_that_structure_is_the_finding(measured):
    """★★★本条最有价值的一句：残差**随 li 变**，低 li 差两个数量级。

    一条横跨全扫描的带会把它平掉，所以这里判的是**对比度**而不是幅值。
    它若消失（对比度掉到 20 倍以下），要么这批件换了，要么算子的行为变了——
    两者都该有人看一眼，而不是让一条宽带子继续报绿。"""
    lo = np.array([r["res"] for r in measured if r["li"] <= 0.75])
    hi = np.array([r["res"] for r in measured if r["li"] >= 1.00])
    assert lo.size and hi.size
    contrast = float(np.median(lo) / np.median(hi))
    assert contrast >= MIN_LI_CONTRAST, (
        f"低/高 li 的残差对比只有 {contrast:.1f} 倍（实测 114 倍）——这批件或算子变了")
    li = np.array([r["li"] for r in measured]); res = np.array([r["res"] for r in measured])
    assert np.corrcoef(li, res)[0, 1] < -0.5, "残差不再随 li 单调下降"
