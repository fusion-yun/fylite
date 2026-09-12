"""est2-basis measurement reduction — shared by the live MDSplus reader and
the offline fyo/HDF5 dump reader.

Raw est2 series → the flat measurement dict (35 flux loops, 79 b-probes,
12 PF coils, Ip, Btor; optionally the 11-chord POINT block).  The reduction
is the GUI_v5 convention: a windowed mean about the requested time with a
pre-shot linear drift subtracted, POINT with its own window after the
−0.9 s baseline offset.  :func:`reduce_est2` takes a ``get(leaf, tree)``
callable, so the two sources (:func:`read_east_mds` off
live MDSplus, :func:`measurements_from_est2_hdf5` off the dump) funnel
through ONE reduction and are byte-identical.

★This used to live in ``fylite.imas_io`` beside the measurement-document
face.  The two had nothing in common but a file: this is a data SOURCE
reducing raw series (``io/``'s remit), that was the fyo document face of
the flat dict (``fyo``'s).  ★The windowed mean, the drift fit and the
fringe gate ARE numerics on measurement series; under the one-host rule
they are a migration candidate for the kernel (ledger:
``tests/PHYSICS-MIGRATION.md``) — this move changed their address,
not their arithmetic.
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["reduce_est2", "measurements_from_est2_hdf5", "read_east_mds", "fringe_gate",
           "elm_onsets", "elm_phase", "elm_phase_mask"]


def fringe_gate(mags, gate: float) -> list[bool]:
    """Which POINT chords keep their weight: ``gate·median ≤ |n_e,line| ≤ median/gate``.

    A fringe jump is an integer number of 2π in the interferometer phase, so
    a chord that has lost fringes can land BELOW the run of its neighbours or
    ABOVE it — the sign of the jump is not fixed.  The band is therefore
    symmetric in log magnitude about the median of the non-zero chords;
    ``gate ≤ 0`` disables it (every non-zero chord is good).  A chord with no
    reading (``None``/0) is never good.  ★F-14 (2026-09-12): the criterion
    used to be the floor alone — EAST #137985 c4 sat 3–166× above the
    same-slice median on 6 of 9 slices and reached the reconstruction with
    ``weight_nel = 1.0``.  Pure so it can be pinned without a device deck.
    """
    import numpy as np
    mag = np.array([abs(v) if v is not None else 0.0 for v in mags], float)
    if gate <= 0:
        return [bool(m > 0) for m in mag]
    med = float(np.median(mag[mag > 0])) if (mag > 0).any() else 0.0
    lo, hi = gate * med, (med / gate if gate > 0 else float("inf"))
    return [bool(m > 0 and lo < m < hi) for m in mag]


def elm_onsets(t, y, *, threshold: float = 0.3, refractory_ms: float = 2.0,
               noise_guard: float = 5.0) -> list[float]:
    """ELM 起始时刻：Dα 迹上的**上升沿**，带一个死区。

    ★★这一步为什么要有（H-15 / `FYL-DESIGN-21` 表 1.2）。H 模的测量要按 ELM 相位
    **条件平均**，否则一个 5 ms 窗里既有崩塌前恢复好的台基、也有崩塌后被削平的台基，
    平均出来的剖面**哪一种都不是**。此前本层只有窗口均值（`reduce_est2`），相位这一
    维根本没有。

    ★判据（触发电平）是相对的，不是一个绝对值：基线取中位数，标度取**峰值**与基线
    之差，电平 = 基线 + `threshold` × 标度。理由是 Dα 的绝对值随视线、镜面镀膜与
    放大倍数变，而「一次 ELM 比静默期亮多少」不变。缺省 0.3 取在标度的下三分之一处：
    比它低会把噪声算成 ELM，比它高会漏掉小 ELM。
    ★★**标度不取百分位**，这是实测改过来的（2026-09-12）：ELM 的占空比只有百分之
    几，于是 95（甚至 98）百分位**落在静默段里**，电平因此落进噪声带 —— 合成迹上
    10 次 ELM 被数成 **80** 次。峰值没有这个问题，代价是它对单个野点敏感，所以下面
    还有一道噪声闸。
    ★★噪声闸：电平同时不低于 基线 + `noise_guard` × σ̂，σ̂ = 1.4826 × MAD（中位数
    绝对偏差，对少数亮点稳健）。缺省 5σ̂ —— 一条**只有噪声**的迹因此交出空表而不是
    一串假起始，这是这道闸要的行为：宁可说「这里没有 ELM」。

    ★★死区（`refractory_ms`）不是一个平滑器：一次 ELM 的 Dα 峰常有**两三个**子峰
    （多丝、多次崩塌），逐个当成起始就会把一个周期切成三段，相位因此全错。缺省
    2 ms 是 EAST / DIII-D 上 I 型 ELM 的典型上升与衰减时间量级；把它设成 0 就是
    「每个上升沿都算一次」。

    交出的是**时刻**（秒），按时间升序；一条没有任何上升沿的迹交出空表 —— 那是
    「这一段里没有 ELM」，由调用方决定它是 L 模、是无 ELM 模式，还是接错了通道。
    ★纯函数：不碰装置牌，也不碰 MDSplus，所以钉得住。
    """
    import numpy as np
    t = np.asarray(t, float)
    y = np.asarray(y, float)
    n = min(t.size, y.size)
    t, y = t[:n], y[:n]
    ok = np.isfinite(t) & np.isfinite(y)
    t, y = t[ok], y[ok]
    if t.size < 3:
        return []
    base = float(np.median(y))
    scale = float(y.max() - base)
    if not (scale > 0.0):
        return []
    mad = float(np.median(np.abs(y - base)))
    floor = base + float(noise_guard) * 1.4826 * mad
    level = max(base + float(threshold) * scale, floor)
    if not (level < y.max()):
        #: 噪声闸把电平推到峰值之上 —— 这条迹上没有比噪声更亮的东西
        return []
    dead = float(refractory_ms) / 1000.0
    above = y > level
    out: list[float] = []
    for k in range(1, t.size):
        if above[k] and not above[k - 1]:
            #: 线性插值到穿越点，而不是取穿越后的那个采样：相位是按时间算的，
            #: 一个采样间隔在 ELM 周期里可以是百分之几
            dy = y[k] - y[k - 1]
            frac = (level - y[k - 1]) / dy if dy != 0.0 else 0.0
            tc = float(t[k - 1] + frac * (t[k] - t[k - 1]))
            if out and tc - out[-1] < dead:
                continue
            out.append(tc)
    return out


def elm_phase(times, onsets):
    """每个时刻的 ELM 相位 ∈ [0, 1)：0 = 刚崩塌，趋近 1 = 下一次崩塌前。

    两次起始之间线性归一化 —— 周期本身是变的（ELM 频率随功率与密度漂），所以按
    **周期分数**而不是按「崩塌后多少毫秒」定相位，这样不同周期才可比。

    ★第一次起始**之前**与最后一次起始**之后**是 `nan`，不是 0 也不是 1：那两段的
    相位**没有定义**（不知道它前面或后面的周期有多长），写成一个数就是编数。
    """
    import numpy as np
    times = np.asarray(times, float)
    o = np.asarray(sorted(float(v) for v in onsets), float)
    out = np.full(times.shape, np.nan)
    if o.size < 2:
        return out
    idx = np.searchsorted(o, times, side="right") - 1
    inside = (idx >= 0) & (idx < o.size - 1)
    i = idx[inside]
    span = o[i + 1] - o[i]
    good = span > 0
    ph = np.full(i.shape, np.nan)
    ph[good] = (times[inside][good] - o[i][good]) / span[good]
    out[inside] = ph
    return out


def elm_phase_mask(times, onsets, phase: tuple = (0.6, 0.9)):
    """相位落在 [lo, hi) 里的那些采样。

    ★缺省 0.6–0.9 是**晚 inter-ELM 窗**：台基已经恢复而下一次崩塌还没到。反演要的
    正是这一段 —— 台基梯度在这里是它的「满值」。要另一段（例如崩塌瞬间的 0.0–0.1）
    把 `phase` 交进来即可；这个函数不替人选。
    ★相位是 `nan` 的采样一律**不**入选（见 :func:`elm_phase`）。
    """
    import numpy as np
    lo, hi = float(phase[0]), float(phase[1])
    ph = elm_phase(times, onsets)
    with np.errstate(invalid="ignore"):
        return np.asarray(np.isfinite(ph) & (ph >= lo) & (ph < hi))


def _dev():
    """The device module, imported lazily: the channel nodes, masks and
    turns live with the document they are derived from."""
    from .. import device
    return device


def _bad_input():
    """:class:`fylite.fyo.MeasurementInputError`, imported lazily.  This module
    RAISES the measurement-contract error; it does not own it — the face that
    defines the contract does.  Lazy because :mod:`fylite.fyo` imports
    :mod:`fylite.io` on its way in, so a module-level import here would close
    the cycle."""
    from ..fyo import MeasurementInputError
    return MeasurementInputError


# --------------------------------------------------------------------------- #
# est2 reduction — the single conversion the MDSplus reader and the offline    #
# fyo/HDF5 reader share, so both funnel raw est2 series through ONE place into #
# the flat measurement dict (est2 basis, 79 probes).                           #
# --------------------------------------------------------------------------- #
def reduce_est2(get, shot: int, time_s: float, *,
                window_ms: float = 5.0, btor: float | None = None,
                drift_window: tuple | None = (-6.9, -6.1),
                read_point: bool = False, point_window_ms: float | None = None,
                point_fringe_gate: float = 0.15, elm: dict | None = None,
                source: str | None = None, error=RuntimeError) -> dict:
    """Reduce raw est2 series → the flat measurement dict (core: 35 flux loops,
    79 b-probes, 12 PF coils, Ip, Btor; ``read_point`` adds the 11-chord POINT
    polarimeter/interferometer block).

    ★★``elm`` turns the windowed mean into an **ELM-phase conditional** mean
    (H-15 / ``FYL-DESIGN-21`` 1.2).  It is opt-in and OFF by default: absent,
    every number this function returns is bit-for-bit what it returned before
    the option existed.  Given, it is
    ``{"time": [...], "dalpha": [...], "phase": (lo, hi), ...}`` — the D-alpha
    series the caller fetched, plus the phase band to keep (see
    :func:`elm_phase_mask`); ``threshold`` / ``refractory_ms`` /
    ``noise_guard`` pass through to :func:`elm_onsets`.  The samples averaged
    are then those inside the time window AND inside the phase band.
    ★**The series is handed in, not looked up**: no D-alpha node is named
    anywhere in this distribution (EAST's binding table has no filterscope
    channel, same gap as Thomson / CER / ECE / MSE), so naming one here would
    be inventing it.  ★An empty intersection is an ERROR, not a quiet fallback
    to the plain window: "no inter-ELM sample in this window" is a fact about
    the discharge, and averaging across the crash instead would return a
    profile that is neither pre- nor post-crash.

    ``get(leaf, tree) -> (data, time) | None`` supplies each raw node's FULL
    series (``tree`` ∈ {"east", "pcs_east"}; None == node-not-found). The
    magnetic reduction is the GUI_v5 windowed mean (|t−t₀| ≤ ``window_ms``) with
    pre-shot linear drift subtraction over ``drift_window``; POINT uses its own
    ``point_window_ms`` window after the −0.9 s pre-shot offset subtraction. The
    SAME arithmetic runs whether the series came from live MDSplus
    (:func:`read_east_mds`) or the HDF5 dump
    (:func:`measurements_from_est2_hdf5`), so the two paths are byte-identical.
    """
    import numpy as np

    tw = float(time_s)
    w = window_ms / 1000.0
    b0, b1 = drift_window or (None, None)

    #: ELM 相位条件平均（可选，缺省关）。起始只算一次，供下面每个通道共用 ——
    #: 同一次放电上不同通道用不同的相位划分会让它们互相不可比
    elm_onset: list[float] = []
    elm_band = (0.6, 0.9)
    if elm is not None:
        et, ey = elm.get("time"), elm.get("dalpha")
        if et is None or ey is None:
            raise error("est2 reduce: `elm` needs both `time` and `dalpha` "
                        "(the series is handed in — this distribution names no D-alpha node)")
        elm_band = tuple(elm.get("phase", elm_band))
        elm_onset = elm_onsets(et, ey, threshold=float(elm.get("threshold", 0.3)),
                               refractory_ms=float(elm.get("refractory_ms", 2.0)),
                               noise_guard=float(elm.get("noise_guard", 5.0)))
        if len(elm_onset) < 2:
            raise error(f"est2 reduce: the D-alpha series carries {len(elm_onset)} ELM onset(s) — "
                        "a phase needs two (it is a fraction of a period); this may be an L-mode or "
                        "ELM-free stretch, or the wrong channel")

    def avg(leaf, tree, scale=1.0, required=True, drift=True):
        r = get(leaf, tree)
        if r is None:
            if required:
                raise error(f"est2 reduce: required node {leaf} ({tree}) absent")
            return None
        s = np.asarray(r[0], dtype=float)
        tb = np.asarray(r[1], dtype=float)
        n = min(len(s), len(tb))
        s, tb = s[:n], tb[:n]
        if drift and b0 is not None:
            base = (tb >= b0) & (tb <= b1)
            if base.sum() > 2:
                p = np.polyfit(tb[base], s[base], 1)
                s = s - (p[0] * tb + p[1])
        sel = np.abs(tb - tw) <= w
        if not sel.any():
            sel = np.zeros(n, bool)
            sel[int(np.abs(tb - tw).argmin())] = True
        if elm_onset:
            #: 窗内**且**相位带内。空交集按名报错（见抬头）——不悄悄退回普通窗口
            band = np.asarray(elm_phase_mask(tb, elm_onset, elm_band))
            both = sel & band[:n]
            if not both.any():
                raise error(
                    f"est2 reduce: no sample of {leaf} lies in both the +/-{window_ms} ms window at "
                    f"{tw} s and the ELM phase band {elm_band} ({int(sel.sum())} in the window, "
                    f"{int(band[:n].sum())} in the band over the whole series) — widen the window, "
                    "widen the band, or pick a slice with an inter-ELM stretch in it")
            sel = both
        return float(np.mean(s[sel])) * scale

    coils = [avg(nd, "east", 1.0 / (2.0 * np.pi)) for nd in _dev().FLUX_LOOP_NODES]
    expmp2, fwtmp2 = [], []
    for i, nd in enumerate(_dev().B_PROBE_NODES):
        v = avg(nd, "east", required=False)
        expmp2.append(0.0 if v is None else v)
        fwtmp2.append(0.0 if v is None else float(_dev().FWTMP2_MASK[i]))
    raw_pf = [avg(nd, "east", _dev().PF_TURNS[i], drift=False)
              for i, nd in enumerate(_dev().PF_NODES)]
    brsp = [raw_pf[i] for i in _dev().PF_EFIT_ORDER]

    plasma = avg(_dev().MDS_IP, "east", 1000.0, required=False, drift=False)
    if plasma is None or abs(plasma) < 5.0e4:          # <50 kA: not a real Ip
        pcrl = avg(r"\pcrl01", "pcs_east", required=False, drift=False)
        if pcrl is not None and abs(pcrl) > abs(plasma or 0.0):
            plasma = pcrl
    if plasma is None:
        raise error(f"no plasma current for shot {shot}: both {_dev().MDS_IP} and "
                    r"pcs_east:\pcrl01 returned no data")

    if btor is None:
        a = avg(_dev().MDS_BT, "east", 1.7 / 1.8 / 4086.0, required=False, drift=False)
        btor = a if (a and abs(a) > 0.5) else 1.8

    meas = {"shot": int(shot), "time_s": float(time_s),
            "itime_ms": int(round(float(time_s) * 1000)),
            "plasma": abs(plasma), "btor": float(btor),
            "brsp": brsp, "coils": coils, "expmp2": expmp2, "fwtmp2": fwtmp2,
            "n_probe_active": int(sum(1 for v in fwtmp2 if v > 0)),
            "basis": "est2",
            "source": source or f"est2:{shot}"}

    if read_point:                                    # POINT polarimeter-interfer.
        pw = (point_window_ms if point_window_ms is not None
              else _dev().POINT_WINDOW_MS) / 1e3          # intev_pol = 0.03 s

        def point_chord(node):
            """Windowed mean after the GUI's -0.9 s pre-shot offset subtraction."""
            r = get(node, "east")
            if r is None:
                return None
            s = np.asarray(r[0], dtype=float)
            tb = np.asarray(r[1], dtype=float)
            n = min(len(s), len(tb))
            s, tb = s[:n], tb[:n]
            base = np.abs(tb - _dev().POINT_BASELINE_S) < _dev().POINT_BASELINE_TOL
            s = s - (float(np.mean(s[base])) if base.any() else 0.0)
            sel = np.abs(tb - tw) <= pw
            if not sel.any():
                sel = np.zeros(n, bool)
                sel[int(np.abs(tb - tw).argmin())] = True
            return float(np.mean(s[sel]))

        ne_l = [point_chord(nd) for nd in _dev().POINT_NE_NODES]
        fr_l = [point_chord(nd) for nd in _dev().POINT_FR_NODES]
        kpol = -1.0 if (fr_l[0] is not None and fr_l[0] < 0) else 1.0
        c_far = _dev().POINT_FARADAY_C * _dev().POINT_LASER_LAMBDA ** 2
        # fringe-jump hygiene: an interferometer chord whose |n_e,line| falls
        # outside the symmetric band gate·median … median/gate has jumped
        # fringes (either way) -> drop it (and its paired Faraday chord, which
        # shares the density). gate<=0 disables.  (:func:`fringe_gate`)
        good_l = fringe_gate(ne_l, point_fringe_gate)
        bnel, bpolar, fwtnel, fwtpol, dropped = [], [], [], [], []
        for i, (a_ne, b_fr, good) in enumerate(zip(ne_l, fr_l, good_l)):
            if a_ne is not None and not good:
                dropped.append(i + 1)
            # interferometer target: |line-integrated n_e| (GUI: nnel/1e19==|a_p|)
            bnel.append(abs(a_ne) if a_ne is not None else 0.0)
            fwtnel.append(1.0 if good else 0.0)
            # polarimeter target: Faraday angle -> int n_e*B_pol dl (GUI line 424)
            bpolar.append((kpol * b_fr / c_far / 2.0 * np.pi / 180.0) / 1e19
                          if b_fr is not None else 0.0)
            fwtpol.append(1.0 if (good and b_fr is not None) else 0.0)
        meas["point"] = {"n_chord": _dev().POINT_NCHORD, "kpol": kpol,
                         "bnel": bnel, "bpolar": bpolar,
                         "fwtnel": fwtnel, "fwtpol": fwtpol,
                         "n_ne_active": int(sum(fwtnel)),
                         "n_fr_active": int(sum(fwtpol)),
                         "fringe_dropped": dropped}
    return meas


def measurements_from_est2_hdf5(dump_dir, shot: int, time_s: float, *,
                                window_ms: float = 5.0,
                                btor: float | None = None,
                                drift_window: tuple | None = (-6.9, -6.1),
                                read_point: bool = False,
                                point_window_ms: float | None = None,
                                point_fringe_gate: float = 0.15) -> dict:
    """Offline est2 measurement dict from the fyo-semantic HDF5 dump
    (``<dump_dir>/<shot>_magnetics.h5`` + ``<shot>_pf_active.h5``; with
    ``read_point`` also ``_polarimeter.h5`` + ``_interferometer.h5``) — the
    unification of the est2 path through the fyo layer: the dump's raw full
    series are served to the SHARED :func:`reduce_est2`, so the result is
    byte-identical to :func:`read_east_mds` off live MDSplus.

    Node names are resolved by each channel's ``name`` attribute (est2 basis:
    ``\\HBPH*`` probes, ``FL*`` loops, ``PF*`` coils, ``pcrl01`` Ip,
    ``focs_it`` Btor, ``point_f*``/``point_n*`` POINT chords) — no hardcoded
    ordering. ``\\ipm`` is absent from the dump (weak on 2022-era shots), so Ip
    falls to ``pcrl01`` exactly as the live path does.
    """
    import h5py
    import numpy as np

    dump = Path(dump_dir)
    files: list = []
    index: dict = {}

    def _reg_aos(h5, ids, aos, quantity):
        grp = h5[ids][aos]
        for k in grp:
            cg = grp[k]
            if not isinstance(cg, h5py.Group):
                continue
            name = cg.attrs.get("name")
            if name is None or quantity not in cg or "data" not in cg[quantity]:
                continue
            q = cg[quantity]
            index[str(name).upper()] = (q["data"], q.get("time"))

    def _open(name):
        p = dump / f"{shot}_{name}.h5"
        if not p.exists():
            return None
        h5 = h5py.File(p, "r"); files.append(h5)
        return h5

    mag = _open("magnetics")
    if mag is None:
        raise _bad_input()(f"est2 HDF5 dump missing: {dump / f'{shot}_magnetics.h5'}")
    _reg_aos(mag, "magnetics", "b_field_pol_probe", "field")
    _reg_aos(mag, "magnetics", "flux_loop", "flux")
    ip0 = mag["magnetics"]["ip"]["0"]
    if "data" in ip0:
        index[str(ip0.attrs.get("name", "pcrl01")).upper()] = (
            ip0["data"], ip0.get("time"))
    tf = mag["magnetics"].get("tf_b_field_tor_vacuum_r_raw")
    if tf is not None and "data" in tf:
        index["FOCS_IT"] = (tf["data"], tf.get("time"))
    pf = _open("pf_active")
    if pf is not None:
        _reg_aos(pf, "pf_active", "coil", "current")
    if read_point:                    # POINT: point_f* (faraday) + point_n* (n_e)
        pol = _open("polarimeter")
        if pol is not None:
            _reg_aos(pol, "polarimeter", "channel", "faraday_angle")
        itf = _open("interferometer")
        if itf is not None:
            _reg_aos(itf, "interferometer", "channel", "n_e_line")

    def get(leaf, tree):
        e = index.get(leaf.lstrip("\\").upper())
        if e is None:
            return None
        data, time = e
        return np.asarray(data[:]), (None if time is None else np.asarray(time[:]))

    try:
        return reduce_est2(get, shot, time_s, window_ms=window_ms, btor=btor,
                           drift_window=drift_window, read_point=read_point,
                           point_window_ms=point_window_ms,
                           point_fringe_gate=point_fringe_gate,
                           source=f"fyo-hdf5:{dump}", error=_bad_input())
    finally:
        for f in files:
            f.close()


# ---------------------------------------------------------------------------
# Direct EAST MDSplus read
#
# ★★2026-09-01 自 `io/kfile.py` 迁入。那个模块被整体移除——它的主体是 EFIT
# `&IN1` k-file 的**写入机**，为一个不在本发行版里的求解器准备输入，并且在注释里
# 逐条转述了该求解器的内部实现（`efitdud6565.f` / `weqdud6565.f` 的 namelist 与
# 装配式），与本仓自己的清净室声明相抵触。
# ★这个函数不属于那一半：它只依赖 `device` 与本模块的 `reduce_est2`，做的是
# 「从 MDSplus 取 est2 信号并归约」——归约本来就在这里，读取跟过来是回家，不是搬家。
# ---------------------------------------------------------------------------
def read_east_mds(shot: int, time_s: float, *,
                  server: str | None = None,
                  window_ms: float = 5.0,
                  btor: float | None = None,
                  read_point: bool = False,
                  point_window_ms: float | None = None,
                  point_fringe_gate: float = 0.15,
                  drift_window: tuple[float, float] | None = (-6.9, -6.1)) -> dict:
    """Read the ``east`` tree and build an est2 (79-probe) measurement dict.

    Headless reproduction of the GUI's data path — NO dialogs, NO plotting:

    * time axis ``dim_of(\\pf1p)``; each channel is averaged over
      ``[t-window, t+window]`` (GUI uses ``|t-t3|<0.005`` s),
    * 35 flux loops ``FLUX_LOOP_NODES`` -> ``COILS`` (value/2/pi, Wb/rad),
    * 79 probes ``B_PROBE_NODES`` -> ``EXPMP2`` (Tesla),
    * 12 PF Rogowskis ``PF_NODES`` * ``PF_TURNS`` -> ``BRSP`` in EFIT coil
      order (``PF_EFIT_ORDER``),
    * ``\\ipm`` (kA) -> ``PLASMA`` [A]; ``\\focs_it`` -> ``BTOR``.

    ``server`` defaults to :data:`device.MDS_SERVER` (or the
    ``KEFIT_MDS_SERVER`` env).  Reads through the engine's mdsip client.
    """
    import numpy as np
    from .. import kernel
    from .mds import _server

    host, port = _server(server)
    #: ★★2026-09-04：transport is the engine's mdsip client, not the site
    #: ``MDSplus`` package (see :mod:`.mds` for what left with it).  One
    #: session, one current tree — re-select only on a switch, as before.
    conn = kernel.MdsSession(host, port)
    _cur = {"tree": None}

    def read_tree(tree):
        conn.open_tree(tree, int(shot))
        _cur["tree"] = tree

    def get(leaf, tree):
        """Full series ``(data, time)`` for one leaf on ``tree`` — the node
        provider handed to the shared est2 reducer; None on NNF (absent node).
        """
        nd = leaf if leaf.startswith("\\") else "\\" + leaf
        if tree != _cur["tree"]:
            read_tree(tree)
        try:
            s, _d = conn.read("data", nd)
            tb, _d = conn.read("dim_of", nd)
            return np.asarray(s, dtype=float), np.asarray(tb, dtype=float)
        except kernel.KernelError:             # NNF is data, not a failure
            return None

    # Full est2 reduction (loops/probes/PF/Ip/Btor + optional POINT) is the ONE
    # implementation in io.est2.reduce_est2, shared with the offline HDF5 reader
    # so the live and offline paths are byte-identical.
    meas = est2.reduce_est2(
        get, shot, time_s, window_ms=window_ms, btor=btor,
        drift_window=drift_window, read_point=read_point,
        point_window_ms=point_window_ms, point_fringe_gate=point_fringe_gate,
        source=f"mdsplus:{host}:{port}:east:{shot}", error=KefitReadError)
    conn.close()
    return meas


