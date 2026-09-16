"""Pereverzev-Corrigan 稳定化，跑自本检出（登记册记录 `tr-paradigm-pereverzev`）。

★★2026-09-16：本册 2026-09-16 重起后 `tr/` 组的**第一条记录**的门。守的是 `FYTOK-SRS-04`
`FR-TR-005` 抄录判据的三句话，而三句话量下来**结论不一样**——这正是要分三个 test 的理由。

*第一、二句成立。* 「P-C 离散精确对消」与「定态对 $d_{pc}$ 不敏感」是同一件事的因与果：
P-C 项按构造在不动点上恒等消去，于是定态与 $d_{pc}$ 无关。扫 $d_{pc}$ = 0 … 40，两种闭包
逐点相对偏差最大 **1.45e-11**，在内核自报的 rel < 1e-9 档内。

★**它不是机器精度，是 Picard 容差限。** 偏差随 $d_{pc}$ 单调上行（constant 闭包
3.0e-14 → 4.5e-12，stiff 6.0e-14 → 1.4e-11），因为两条路走到同一个不动点的**精度**由
`tol` 定，不由对消的代数定。把这一档写成「机器精度」会是夸大——对消在代数上是精确的，
量出来的数是收敛容差的像。

★★*第三句演示不了，如实记。* 判据要「刚性闭包下 Picard 收敛（**裸环停滞对照**）」，而
本接口上**造不出停滞的裸环**：扫遍 `stiff` 闭包的刚度盒（`p1` × `p2` 十二点，chi 动态范围
最高 8001 倍），$d_{pc}$ = 0 **每一点都收敛**，最慢 495 次内迭代。机理在闭包的形式里——
`case.rs::diffusivity_of` 是 `chi0 (p1 + p2 g/(1+g))`，对梯度**有界且饱和**，g→∞ 时
chi 趋于 `chi0 (p1+p2)`。而 P-C 要对付的是 chi 随梯度**不封顶**或**带阈值**的那类闭包。
于是这条对照**不是没人去做，是这一族闭包里不存在**——记录判 `inconclusive` 而不是 `pass`，
覆盖上算半条。

★**第三个 test 钉的是一个否定结论**，这是有意的：哪天内核换了闭包、或者接上了真正刚性的
那一路（`evolve` 的 `turbulent` / flux-match），这个 test 会红，而红在这里的意思是
**记录该重判了**——那时判据的对照项才第一次有得可量。

读数由 `tools/benchmark-transport.py readings` 产出；新鲜度由记录的 `run.kernel` 与
`docs/benchmark/meta/kernel.json` 比，不在这里判。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
READINGS = "transport_pc.json"

#: ★接受档取内核自己那道门的自报值，不是本册另定一个。
#: `transport.rs::the_pereverzev_corrigan_fixed_point_is_independent_of_d_pc` 断的就是 1e-9。
ACCEPT = 1e-9

#: ★★扫到 100 而只判到 40：`stiff` 闭包在 $d_{pc}$ = 100 上顶到 `max_inner` = 4000 没收敛。
#: 一个没收敛的解**不是定态**，拿它比不动点没有意义——所以它记在读数里、不进判据。
#: 这不是把不利数据摘出去：不收敛这件事本身就在读数的 `converged` 上写着。
JUDGED_MAX_D_PC = 40.0


@pytest.fixture(scope="module")
def want() -> dict:
    p = ROOT / "docs" / "benchmark" / "readings" / READINGS
    if not p.is_file():
        pytest.skip(f"no {READINGS} recorded in docs/benchmark/readings")
    return json.loads(p.read_text(encoding="utf-8"))


def test_the_steady_state_does_not_depend_on_d_pc(want):
    """判据一、二：定态与 $d_{pc}$ 无关，收敛了的点逐点比到 rel < 1e-9。"""
    checked = 0
    for closure, sweep in want["d_pc_independence"].items():
        for pt in sweep["points"]:
            if pt["d_pc"] > JUDGED_MAX_D_PC:
                continue
            assert pt["converged"], f"{closure} d_pc={pt['d_pc']} 没收敛，判不了"
            assert pt["rel_deviation_from_d_pc_0"] < ACCEPT, \
                f"{closure} d_pc={pt['d_pc']}: rel {pt['rel_deviation_from_d_pc_0']:.3e} ≥ {ACCEPT}"
            checked += 1
    #: ★两种闭包 × 五个判到的 d_pc——少一点就说明读数被截了
    assert checked == 10, checked


def test_d_pc_actually_reaches_the_assembly(want):
    """★否则上一个 test 是在拿一个解跟它自己比。

    内核自己那道门也断这一条（`assert_ne!(plain.inner_iterations, stab.inner_iterations)`）：
    定态**相同**而路径**不同**，两句合起来才说明这一项装上了且只改条件数。
    """
    for closure, sweep in want["d_pc_independence"].items():
        by_d = {p["d_pc"]: p for p in sweep["points"]}
        bare, stab = by_d[0.0]["inner_iterations"], by_d[JUDGED_MAX_D_PC]["inner_iterations"]
        assert bare != stab, f"{closure}: d_pc 没改变求解路径（两边都是 {bare} 次内迭代）"


def test_the_bare_loop_does_not_stagnate_in_this_closure_family(want):
    """★★判据第三句的对照项——**演示不了**，这个 test 钉住的就是这件事。

    它断的是一个否定结论：刚度盒里裸环一个都没停滞。这一天内核接上真正刚性的闭包，
    它就该红——红在这里读作「对照项第一次有得可量了，记录该重判」，不是「回归坏了」。
    """
    rows = want["stagnation_control"]["rows"]
    assert len(rows) == 12, len(rows)
    stagnated = [r for r in rows if not r["converged"]]
    assert not stagnated, \
        f"裸环在这些点上停滞了——判据的对照项现在可量了，`tr-paradigm-pereverzev` 该重判：{stagnated}"
    #: ★把「刚度确实扫开了」也钉住，否则「都收敛」可能只是因为盒子太小
    assert max(r["chi_dynamic_range"] for r in rows) > 1e3, "刚度盒没扫开，'都收敛'说明不了什么"


def test_the_large_d_pc_end_is_recorded_as_not_converged(want):
    """★不利的那一端留在读数里，且标着它没收敛——不是摘出去。

    `stiff` 闭包 $d_{pc}$ = 100 顶到 `max_inner` 没收敛。求解器**自己说了**
    （`converged = False`），没有把顶到上限的那个剖面当定态交回来——这一条本身值得守。
    """
    stiff = {p["d_pc"]: p for p in want["d_pc_independence"]["stiff"]["points"]}
    top = stiff[100.0]
    assert not top["converged"], "d_pc=100 现在收敛了——读数该重取，判据的判到档可以放宽"
    assert top["inner_iterations"] == want["settings"]["max_inner"], top
