"""B-09：电流爬升段的环电压，对 DINA 的 ITER 15 MA 含时场景。

★★**这是全图唯一覆盖电流爬升的参考**——S8 现有三条（TORAX · JINTRAC ×2）全在平顶或
准稳态窗口，而爬升段是另一套物理占主导（欧姆电阻、磁通消耗、L dI/dt）。

★★**先摆平「比的是不是同一个量」，再谈差多少。** 首轮按字面比 `Vloop` 得到 6–8 倍的差，
而那不是模型的差：DINA 随件的参数说明写着——

    Vloop,V - plasma loop voltage [V]: …, where … is the plasma conductivity,
              integration over the plasma volume

即 DINA 的 `Vloop` 是**电导率的体积分**（电阻项），感应那一半它另记
（`D(PSI)res` 磁通电阻损耗 · `Cejima` Ejima 系数）；而本仓 `loop_voltage_ohmic` 返回的是
**Ip·Rp + Lp·dIp/dt**。在 0.2151 MA/s 上 `Lp dIp/dt` 约 2.6 V——那 6–8 倍的大头就是它。
**两个量不同名而同字**，照字面比会把一次口径不符写成一次模型缺陷。

★本门因此比**电阻项对电阻项**：把该时刻的态摆成平顶（dIp/dt = 0）再读 `v_loop`，
用的仍是本仓自己的实现，不是本文件里重抄一遍公式。

★★**平顶段不判，且理由要留在门里**：DINA 平顶的电流大半是**非感应**的
（自举 ~4 MA 加 NBI/EC 驱动），而本仓 0-D 把整个 I_p 都当欧姆电流驱动。实测那里比值 3.8——
这不是缺陷，是这条比较不适用的区间。下面有一条断言把「它就该很大」钉住，
免得哪天有人把平顶也纳进来、看到 3.8 以为是回归。

语料：ITER IDM 件（Internal Use），在本机 `data/ITER Scenario/` 之下，**不在任何仓里**。
够不到就 skip 并点名——这是一条只在有语料的机器上跑得起来的门。
"""
from __future__ import annotations

import os
import pathlib

import numpy as np
import pytest

TRACE = pathlib.Path(os.environ.get(
    "ITER_SCENARIO_ROOT", str(pathlib.Path.home() / "workspace/data/ITER Scenario")
)) / ("DINA_simulation_of_15MA_DT_scenario__15M_XA8GXS_v1_1/15MA DT-DINA2018-07/"
      "TEXT data/15MA-DINA2018-07_Data2.TXT")

COLS = ["time,s", "Ip,MA", "<Te>,keV", "<Ne>,10(19)m-3", "Zeff", "li(3)",
        "Vloop,V", "ap,m", "Rp,m", "kp", "Te(0)/<Te>"]

#: 爬升段实测比值 0.66..1.00 ⇒ 最劣偏低 34 %。带取 40 %：一档余量。
#: ★这个带说的是「0-D 的 Spitzer + 新经典电阻，对 DINA 的电导率体积分，在爬升段差多少」。
BAND = 0.40
#: 平顶实测 3.8。断言它 **大**——那是排除该区间的理由本身。
FLAT_TOP_MIN_RATIO = 2.0


@pytest.fixture(scope="module")
def dina():
    if not TRACE.is_file():
        pytest.skip(f"没有 DINA 语料（ITER IDM，Internal Use）：{TRACE}")
    cols = TRACE.open().readline().rstrip("\n").split("\t")
    ix = {c: i for i, c in enumerate(cols)}
    rows = []
    with TRACE.open() as fh:
        next(fh)
        for line in fh:
            p = line.split("\t")
            if len(p) < len(cols):
                continue
            try:
                rows.append([float(p[ix[k]]) for k in COLS])
            except (ValueError, KeyError):
                pass
    d = np.array(rows)
    ip = np.abs(d[:, 1])
    flat = ip > 0.95 * ip.max()
    return {"d": d, "t": d[:, 0], "ip": ip, "flat": flat, "t_ft0": d[:, 0][flat][0]}


@pytest.fixture(scope="module")
def resistive():
    from fylite._paths import KERNEL_LIB
    if not KERNEL_LIB.exists():
        pytest.skip("没有内核（rust/build.sh）")
    from fylite.io import fydoc

    def f(row) -> float:
        """本仓在该态下的**电阻项**：摆成平顶读 v_loop，于是 dIp/dt = 0。"""
        s = {"ip": abs(row[1]) * 1000, "r0": float(row[8]), "a": float(row[7]),
             "kappa": float(row[9]), "du": 0.4, "dl": 0.4, "ne": float(row[3]),
             "te": float(row[2] * row[10]), "tite": 0.9, "pn": 0.3, "pt": 1.5,
             "zeff": float(row[4]), "dtf": 0.45, "meff": 2.5, "paux": 1.0,
             "t_ru": 1.0, "t_ft": 8.0, "t_end": 10.0, "t_on": 1.0, "t_off": 8.0,
             "slice": 100.0, "hfac": 1.0, "tau_law": 0.0, "w0": 1.0, "pfscale": 1.0,
             "phiavail": 0.0, "eqauto": 1.0}
        sm = fydoc.complete("code/zerod", {"settings": s, "inputs": {}})["fields"]["summary"]
        t = np.asarray(sm["time"]["data"], float)
        v = np.asarray(sm["global_quantities"]["v_loop"]["value"]["data"], float)
        return abs(float(v[int(np.argmin(abs(t - 5.0)))]))
    return f


def test_the_reference_really_covers_the_ramp(dina):
    """★先判参考侧覆盖什么。本条的全部价值在于它覆盖爬升，覆盖不到就无从谈起。"""
    t, ip, flat = dina["t"], dina["ip"], dina["flat"]
    assert t.max() > 400, f"轨迹只到 {t.max():.0f} s"
    assert ip.max() > 14.0, f"Ip 峰只有 {ip.max():.2f} MA"
    rate = (ip[flat][0] - 1.0) / (dina["t_ft0"] - t[ip > 1.0][0])
    assert 0.1 < rate < 0.5, f"爬升率 {rate:.3f} MA/s 不像 ITER 的 15 MA 场景"


def test_the_resistive_loop_voltage_agrees_through_the_ramp(dina, resistive):
    d, t, t_ft0 = dina["d"], dina["t"], dina["t_ft0"]
    worst, where = 0.0, None
    for frac in (0.25, 0.5, 0.75, 0.95):
        tt = 3.0 + frac * (t_ft0 - 3.0)
        i = int(np.argmin(abs(t - tt)))
        vf, vd = resistive(d[i]), abs(d[i, 6])
        dev = abs(vf / vd - 1.0)
        if dev > worst:
            worst, where = dev, tt
    assert worst <= BAND, f"爬升段最劣偏差 {worst:.0%} 在 t={where:.1f} s（带 {BAND:.0%}）"


def test_the_flat_top_is_excluded_and_this_is_why(dina, resistive):
    """★★钉住排除的**理由**，不只是排除本身。

    平顶上 DINA 的电流大半非感应，而本仓 0-D 全按欧姆驱动，所以比值该**大**。
    它若哪天变小，要么是本仓加了自举，要么是参考换了——两者都该有人来看一眼，
    而不是让一条悄悄放宽的判据把平顶也收进来。"""
    d, flat = dina["d"], dina["flat"]
    k = int(np.where(flat)[0][len(np.where(flat)[0]) // 2])
    ratio = resistive(d[k]) / abs(d[k, 6])
    assert ratio >= FLAT_TOP_MIN_RATIO, (
        f"平顶比值只有 {ratio:.2f}——本仓 0-D 不含非感应电流，这个比值本该很大；"
        "它变小了，说明有一侧变了")
