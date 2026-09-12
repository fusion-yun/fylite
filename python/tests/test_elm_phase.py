"""ELM 相位条件平均 —— H 模测量的那一维（H-15 / `FYL-DESIGN-21` 表 1.2）。

★★**为什么要有。** H 模的测量按时间窗平均，而一个 5 ms 窗里既有崩塌前恢复好的
台基、也有崩塌后被削平的台基：平均出来的剖面**哪一种都不是**，而台基梯度与自举
电流吃的正是这个差。此前本层只有窗口均值（`io/est2.py::reduce_est2`），相位这一维
根本不存在 —— 设计册表 1.2 的状态是 ✗，写着「没有 Dα 触发的输入端口，也没有相位
选择的 code」。

★这三个函数是**纯的**（不碰装置牌、不碰 MDSplus），所以本文件前六条**无条件跑**，
和 `fringe_gate` 那道闸同一个理由；`reduce_est2` 那一半是**可选开关**（缺省关，关着时
每一个数与从前逐位相同），它要装置牌里的通道表，所以那四条带 `requires_machine`。

★★**Dα 的节点名不在本分发里**（EAST 的绑定表没有 filterscope 通道，与 Thomson /
CER / ECE / MSE 同一个缺口），所以序列是**交进来**的，不是查出来的 —— 在这里编一个
节点名就是编数。

★实测读数（合成迹，2026-09-12）：周期 20 ms、占空比 2 %、噪声 σ = 0.02 的十次 ELM
上数出 **9** 个起始（第一个峰的上升沿在记录起点之前，所以是 9 而不是 10）；只有噪声
的迹交出 **0** 个。★标度**取峰值而不是百分位**也是实测改过来的：95 百分位落在静默
段里，电平因此落进噪声带，同一条迹被数成 **80** 次 ELM。
"""
from __future__ import annotations

import numpy as np
import pytest

from conftest import requires_machine
from fylite.io import est2

PERIOD = 0.02          #: ELM 周期 [s]
DUTY = 0.02            #: 亮段占周期的比例（Dα 峰宽）
SIGMA = 0.02           #: 噪声


def _trace(t0=0.0, t1=0.2, dt=1e-5, seed=7, amp=2.0, sigma=SIGMA):
    """十次 ELM 的合成 Dα：静默基线 0.1，每周期一个窄亮峰，加白噪声。"""
    rng = np.random.default_rng(seed)
    t = np.arange(t0, t1, dt)
    ph = (t % PERIOD) / PERIOD
    y = 0.1 + amp * np.exp(-(ph / DUTY) ** 2) + sigma * rng.standard_normal(t.size)
    return t, y


def test_the_onsets_are_the_rising_edges_and_nothing_else():
    """★★十次 ELM 数出九个起始，且每一个都落在一个周期边界上（到一个采样内）。"""
    t, y = _trace()
    on = est2.elm_onsets(t, y)
    assert len(on) == 9, on
    #: 每个起始都在 k·PERIOD 附近：相位定得准不准，全看这一条
    resid = [abs(v % PERIOD) for v in on]
    resid = [min(r, PERIOD - r) for r in resid]
    assert max(resid) < 2e-4, f"起始偏离周期边界 {max(resid):.2e} s"
    #: 升序、不重复
    assert on == sorted(on) and len(set(on)) == len(on)


def test_a_noise_only_trace_carries_no_elm():
    """★★只有噪声时交出空表 —— 噪声闸（5 σ̂，σ̂ = 1.4826·MAD）的全部用处。

    这一条变红的读法只有一种：电平又落进噪声带了，于是「这里没有 ELM」会被报成
    一串假起始，而下游的相位全是假的。
    """
    rng = np.random.default_rng(11)
    t = np.arange(0, 0.2, 1e-5)
    assert est2.elm_onsets(t, 0.1 + SIGMA * rng.standard_normal(t.size)) == []
    #: 一条常数迹也没有 ELM（标度为零）
    assert est2.elm_onsets(t, np.full(t.size, 0.3)) == []


def test_the_percentile_scale_is_not_what_is_used():
    """★★标度取**峰值**不取百分位：占空比 2 % 时 95 百分位在静默段里。

    这一条不是重复上面两条 —— 它直接量那个曾经的错：拿 95 百分位当标度，同一条迹
    的触发电平会落进噪声带。这里用**同一条迹**算出两个电平并比较，所以它钉的是
    「哪个统计量」，而不是某个实现细节。
    """
    t, y = _trace()
    base = float(np.median(y))
    lvl_pct = base + 0.3 * (float(np.percentile(y, 95)) - base)
    lvl_peak = base + 0.3 * (float(y.max()) - base)
    noise = 1.4826 * float(np.median(np.abs(y - base)))
    assert lvl_pct < base + 5.0 * noise, "95 百分位的电平不再落在噪声带里 —— 重新量这条迹"
    assert lvl_peak > base + 5.0 * noise, "峰值标度的电平落进了噪声带"
    assert len(est2.elm_onsets(t, y)) == 9


def test_the_refractory_keeps_one_elm_from_becoming_three():
    """★★死区：一次 ELM 的 Dα 峰常有子峰，逐个当起始会把一个周期切成三段。

    合成一条每次 ELM 带三个子峰（相距 0.4 ms）的迹：死区 0（每个上升沿都算）应当
    数出约三倍，缺省 2 ms 应当仍是九个。
    """
    rng = np.random.default_rng(3)
    t = np.arange(0, 0.2, 1e-5)
    y = np.full(t.size, 0.1) + SIGMA * rng.standard_normal(t.size)
    for k in range(1, 10):
        for j, a in enumerate((2.0, 1.6, 1.2)):
            y += a * np.exp(-((t - (k * PERIOD + j * 4e-4)) / 1.2e-4) ** 2)
    assert len(est2.elm_onsets(t, y, refractory_ms=2.0)) == 9
    assert len(est2.elm_onsets(t, y, refractory_ms=0.0)) >= 20


def test_the_phase_is_a_fraction_of_the_period_and_undefined_outside():
    """★相位在 [0,1) 内线性上升；第一次起始之前与最后一次之后是 `nan`，不是 0。"""
    t, y = _trace()
    on = est2.elm_onsets(t, y)
    ph = est2.elm_phase(t, on)
    inside = (t > on[0]) & (t < on[-1])
    assert np.all(np.isfinite(ph[inside]))
    assert np.all(np.isnan(ph[~inside]))
    assert 0.0 <= np.nanmin(ph) and np.nanmax(ph) < 1.0
    #: 一个周期之内，相位随时间单调上升
    seg = (t > on[2]) & (t < on[3])
    assert np.all(np.diff(ph[seg]) > 0)
    #: 起始时刻本身相位 ≈ 0
    assert float(est2.elm_phase([on[3] + 1e-9], on)[0]) < 1e-5


def test_the_band_selects_the_late_inter_elm_stretch():
    """★★条件平均**选对了段**：一条「崩塌后被削平、再线性恢复」的台基信号上，
    晚 inter-ELM 窗（0.6–0.9）的均值接近恢复值，而全窗均值明显更低。

    这就是这一步的全部意义：同一段数据，两种平均差出台基高度的一大截。
    """
    t, y = _trace()
    on = est2.elm_onsets(t, y)
    #: 台基信号：每次崩塌后从 0.4 线性恢复到 1.0（相位的线性函数）
    ph = est2.elm_phase(t, on)
    ped = 0.4 + 0.6 * ph
    band = est2.elm_phase_mask(t, on, (0.6, 0.9))
    inside = np.isfinite(ph)
    late = float(np.mean(ped[band]))
    allw = float(np.mean(ped[inside]))
    assert late == pytest.approx(0.4 + 0.6 * 0.75, abs=0.01), late
    assert allw == pytest.approx(0.4 + 0.6 * 0.5, abs=0.01), allw
    assert late - allw > 0.1, f"两种平均差 {late - allw:.3f} —— 那这一步就没有意义了"
    #: 另一段（崩塌瞬间）也选得出来，且明显更低
    crash = float(np.mean(ped[est2.elm_phase_mask(t, on, (0.0, 0.1))]))
    assert crash < allw < late


@requires_machine
def test_the_reduction_is_untouched_when_the_option_is_off():
    """★★缺省关：不给 `elm` 时，归约出来的数与从前**逐位相同**。

    钉法是对比同一次归约的两条路（不传 `elm` vs 传一个 `None`），而不是读一个标志：
    一个可选项最该保证的事就是「不打开时什么都没变」。
    """
    t, y = _trace()

    def get(leaf, tree):
        return (np.sin(1e3 * t) + 1.0, t)

    a = est2.reduce_est2(get, 1, 0.1, btor=1.8)
    b = est2.reduce_est2(get, 1, 0.1, btor=1.8, elm=None)
    assert a["coils"] == b["coils"] and a["expmp2"] == b["expmp2"]
    assert a["plasma"] == b["plasma"]


@requires_machine
def test_the_conditional_reduction_averages_only_the_band():
    """★★开关打开时，归约平均的**就是**相位带里的采样。

    通道信号取成相位的线性函数（与上面那一条同一个构造），于是期望值是解析的：
    带 0.6–0.9 的均值 = 0.4 + 0.6·0.75。窗取 ±8 ms（跨一个 ELM 周期），所以带内
    与带外都有采样 —— 否则这一条什么也没测。
    """
    t, y = _trace()
    on = est2.elm_onsets(t, y)
    ph = est2.elm_phase(t, on)
    chan = np.where(np.isfinite(ph), 0.4 + 0.6 * np.nan_to_num(ph), 0.0)

    def get(leaf, tree):
        return (chan, t)

    elm = {"time": t, "dalpha": y, "phase": (0.6, 0.9)}
    plain = est2.reduce_est2(get, 1, 0.1, btor=1.8, window_ms=8.0, drift_window=None)
    cond = est2.reduce_est2(get, 1, 0.1, btor=1.8, window_ms=8.0, drift_window=None, elm=elm)
    #: 磁探针那一列是同一个信号，所以直接比它
    assert cond["expmp2"][0] == pytest.approx(0.4 + 0.6 * 0.75, abs=0.02), cond["expmp2"][0]
    assert plain["expmp2"][0] == pytest.approx(0.4 + 0.6 * 0.5, abs=0.03), plain["expmp2"][0]
    assert cond["expmp2"][0] > plain["expmp2"][0]


@requires_machine
def test_an_empty_intersection_is_an_error_not_a_quiet_fallback():
    """★★窗与带无交集时**按名报错**：静默地退回普通窗口会交出一份跨崩塌的平均，
    而那既不是崩塌前也不是崩塌后 —— 它看起来完全正常，这才是危险的地方。"""
    t, y = _trace()

    def get(leaf, tree):
        return (np.ones(t.size), t)

    #: 窗 0.05 ms（一个采样量级）落在崩塌瞬间，带要 0.6–0.9
    on = est2.elm_onsets(t, y)
    at = on[3] + 0.0001
    with pytest.raises(RuntimeError) as e:
        est2.reduce_est2(get, 1, at, btor=1.8, window_ms=0.05, drift_window=None,
                         elm={"time": t, "dalpha": y, "phase": (0.6, 0.9)})
    assert "ELM phase band" in str(e.value), str(e.value)


@requires_machine
def test_it_refuses_a_series_it_cannot_phase():
    """★交了 Dα 却只有一个（或零个）起始时按名报错：相位是周期的分数，要两个起始。"""
    t, y = _trace()

    def get(leaf, tree):
        return (np.ones(t.size), t)

    rng = np.random.default_rng(5)
    flat = 0.1 + SIGMA * rng.standard_normal(t.size)
    with pytest.raises(RuntimeError) as e:
        est2.reduce_est2(get, 1, 0.1, btor=1.8, elm={"time": t, "dalpha": flat})
    assert "ELM onset" in str(e.value), str(e.value)
    with pytest.raises(RuntimeError) as e:
        est2.reduce_est2(get, 1, 0.1, btor=1.8, elm={"time": t})
    assert "dalpha" in str(e.value), str(e.value)
