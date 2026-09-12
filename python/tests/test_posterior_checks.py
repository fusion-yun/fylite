"""H-18 的两条后验检验：振荡判据的落点，与中子那条的「明写 unevaluated」。"""
from __future__ import annotations

import numpy as np
import pytest

from fylite.engine import physics as ph


class _R:
    def __init__(self, d): self.d = d; self.missing = []
    def arr(self, table, key):
        v = self.d.get(key)
        if v is None:
            self.missing.append(f"{table}/{key}")
        return v


def _osc(pprime, ffprime, **opt):
    return ph.CHECKS["source-oscillation"].fn(
        _R({"dpressure_dpsi": np.asarray(pprime, float),
            "f_df_dpsi": np.asarray(ffprime, float)}), opt)


def test_a_monotone_pair_measures_zero():
    """★单调剖面的 TV/量程 恰好是 1，所以判据量到 0 —— 这是整条的锚。"""
    x = np.linspace(0.0, 1.0, 65)
    r = _osc(1.0 - x, 2.0 - 2.0 * x)
    assert r.measured == pytest.approx(0.0, abs=1e-12), r.detail
    #: 期望类不带缺省带，所以没声明 tolerance 时判决是 unevaluated —— 而**数照样报**
    assert r.state == ph.UNEVALUATED and r.measured is not None
    assert _osc(1.0 - x, 2.0 - 2.0 * x, tolerance=0.15).state == ph.PASS


def test_an_oscillating_source_is_measured_and_the_worse_one_decides():
    """★判在更振荡的那一条上，因为坏的是它。"""
    x = np.linspace(0.0, 1.0, 65)
    smooth = 1.0 - x
    wiggly = (1.0 - x) + 0.05 * np.sin(12.0 * np.pi * x)
    r = _osc(smooth, wiggly, tolerance=0.15)
    assert r.measured > 0.3, r.detail
    assert r.state != ph.PASS
    assert "ff'" in r.detail and "p'" in r.detail
    #: 两条换位，读数不变（判的是 max，不是某一条）
    assert _osc(wiggly, smooth, tolerance=0.15).measured == pytest.approx(r.measured)


def test_the_reading_is_the_one_measured_on_the_real_records():
    """★钉住实测落点（2026-09-12）：这三个数是这条判据的量程标定。

    解析家族（`code/forward` 的 truth）**恰好 0**；同一条 EAST 动理学反演
    `nff = 2` 给 0.0246，`nff = 3` 给 0.0882 —— 基一富，振荡跟着长。内核侧的
    读数由 `test_reconstruction_code.py` 产出；这里钉的是**判据本身**在这三个
    数上的判决，所以公开仓不需要内核夹具也能核。
    """
    for measured, tol, want in ((0.0000, 0.15, ph.PASS), (0.0246, 0.15, ph.PASS),
                                (0.0882, 0.15, ph.PASS), (0.0882, 0.05, ph.CONDITIONAL)):
        assert ph._verdict(measured, tol) == want, (measured, tol)


def test_no_sources_is_unevaluated_and_names_what_is_missing():
    r = ph.CHECKS["source-oscillation"].fn(_R({}), {})
    assert r.state == ph.UNEVALUATED and r.missing, r


def test_the_neutron_check_is_registered_and_says_what_it_lacks():
    """★★「明写 unevaluated」：它在册子里，且它自己说出缺什么。

    不写进册子与「评过了」在读者眼里长得一样 —— `plan()` 据 `reads` 回答「能评
    哪几条、缺哪个量」，所以这条必须在表上，且必须点名。
    """
    c = ph.CHECKS["neutron-yield"]
    assert c.kind == "expectation" and c.tolerance is None
    r = c.fn(_R({}), {})
    assert r.state == ph.UNEVALUATED
    assert any("neutron" in m for m in r.missing), r.missing
    assert "code" in r.detail and "SUMMARY" in r.detail
    assert r.caveat and any("H-18" in x for x in r.caveat)
