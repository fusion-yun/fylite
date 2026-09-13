"""Raw diagnostic series → the flat measurement dict — one reduction shared by the
live MDSplus reader and the offline HDF5 dump reader.

The reduction is the GUI_v5 convention: a windowed mean about the requested time
with a pre-shot linear drift subtracted, POINT with its own window after the
−0.9 s baseline offset, optionally conditioned on the ELM phase.
:func:`reduce_series` takes a ``get(leaf, tree)`` callable, so the two sources
(:func:`read_mds` off live MDSplus, :func:`read_hdf5_dump` off a dump) funnel
through ONE reduction and are byte-identical.

★★2026-09-13 (user ruling: est2 removed at every layer).  This is the general half
of the retired ``fylite.io.est2`` (kept at ``archive/python/fylite/io/est2.py``):
the windowed mean, the drift, the POINT block, the fringe gate and the ELM phase
are arithmetic on series and belong to no channel order.  The three seams that
did belong to one are gone:

* **the channels are the resolved device's.**  Probe / loop / PF / POINT node
  names come from the device document resolved for the shot and the measurement
  chain (:func:`fylite.device.document`) — the one derivation
  :mod:`fylite.device` runs, not a probe basis this module knows;
* **the tree is the chain's.**  The main tree a node is read from is the
  ``tree`` of the chain's ``measurement_chains`` entry in the card's resolution
  document (:func:`chain_tree`), not a literal; the Ip fallback reads the
  document's own ``data_source.mdsplus.pcs_tree``;
* **the output names its chain.**  The flat dict carries ``measurement_chain``
  (the resolved magnetics group's) where it used to stamp ``"basis": "est2"``.

★★Probe weights — the rule, stated once and recorded in the output as
``probe_weight_rule``:

* ``"device"`` — every probe channel of the resolved magnetics group carries a
  ``weight``: a probe that returned data gets that weight;
* ``"unit"`` — the group carries none (EAST's providers carry none since the est2
  arrays left fydoc): every probe that returned data gets weight 1.

In both, a probe whose node is absent from the tree gets 0 — an absent node is not
a reading, and that is the only zero this rule writes.  No mask is invented and
nothing is refused.  The reduction does not gate readings by value
(``operational.probe_gate``); that hygiene step belongs to its own caller
(:func:`fylite.io.mds.fetch_measurements`).

★The windowed mean, the drift fit and the fringe gate ARE numerics on measurement
series; under the one-host rule they are a migration candidate for the kernel
(ledger: ``tests/PHYSICS-MIGRATION.md``).
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["reduce_series", "read_mds", "read_hdf5_dump", "chain_tree", "fringe_gate",
           "elm_onsets", "elm_phase", "elm_phase_mask", "PROBE_WEIGHT_RULES"]

#: the key a card's resolution document spells its chain table under (the runtime's
#: ``device_resolve::CHAINS_KEY``)
CHAINS_KEY = "measurement_chains"

#: the values ``probe_weight_rule`` takes (see the module header)
PROBE_WEIGHT_RULES = ("device", "unit")


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

    ★★这一步为什么要有（H-15 / `FYL-SDD-07` 表 1.2）。H 模的测量要按 ELM 相位
    **条件平均**，否则一个 5 ms 窗里既有崩塌前恢复好的台基、也有崩塌后被削平的台基，
    平均出来的剖面**哪一种都不是**。此前本层只有窗口均值（`reduce_series`），相位这一
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
    """The device module, imported lazily: the channel nodes and turns live with
    the document they are derived from."""
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


def chain_tree(chain: str | None, *, card=None) -> str:
    """The MDSplus tree measurement chain ``chain`` is read from: the ``tree`` of its
    ``measurement_chains`` entry in the resolution document beside the configured
    card (``card`` names another).

    ★Refused by name, never guessed: no chain (a document whose magnetics group
    declares none), a card with no resolution document, or a chain the table does
    not declare (or declares without a tree).
    """
    dev = _dev()
    if not chain:
        raise dev.MachineDataMissing(
            f"no measurement chain: the device document's magnetics group declares no "
            f"{dev.CHAIN_KEY}, so no tree can be named — resolve the device in a chain "
            "(fylite.device.document(shot=..., measurement_chain=...))")
    where = card if card is not None else dev.card_path()
    table = (dev.resolution_of(where).get("manifest") or {}).get(CHAINS_KEY) or {}
    entry = table.get(chain) if isinstance(table, dict) else None
    tree = entry.get("tree") if isinstance(entry, dict) else None
    if not tree:
        raise dev.MachineDataMissing(
            f"measurement chain {chain!r} names no tree in the {CHAINS_KEY} table of the "
            f"resolution document beside {where} (declared: {sorted(table) if isinstance(table, dict) else table!r})")
    return str(tree)


def _names(device_doc):
    """The derived names of ``device_doc`` — the bound device's when ``None``.  The
    one derivation :mod:`fylite.device` runs, not a second reading of the document."""
    dev = _dev()
    return dev._ensure() if device_doc is None else dev._derive(device_doc)


def _need(names: dict, key: str, device_doc):
    """A derived name, or the device module's own named refusal when it is absent."""
    if key in names:
        return names[key]
    dev = _dev()
    if device_doc is None:
        return getattr(dev, key)             # raises MachineDataMissing naming the group
    hint = dev._MISSING_WHERE.get(key, "its group is absent from the document")
    raise dev.MachineDataMissing(
        f"{key} does not derive from the device document resolved for this read: {hint}")


# --------------------------------------------------------------------------- #
# the reduction — the single conversion the MDSplus reader and the HDF5 dump   #
# reader share, so both funnel raw series through ONE place into the flat dict #
# --------------------------------------------------------------------------- #
def reduce_series(get, shot: int, time_s: float, *,
                  device_doc: dict | None = None, measurement_chain: str | None = None,
                  window_ms: float = 5.0, btor: float | None = None,
                  drift_window: tuple | None = (-6.9, -6.1),
                  read_point: bool = False, point_window_ms: float | None = None,
                  point_fringe_gate: float = 0.15, elm: dict | None = None,
                  source: str | None = None, error=RuntimeError) -> dict:
    """Reduce raw series → the flat measurement dict (core: the flux loops, poloidal
    probes and PF coils of the device, Ip, Btor; ``read_point`` adds the POINT
    polarimeter/interferometer block).

    ``device_doc`` is the device the channels are read against — the bound device
    when ``None``; :func:`read_mds` passes the document resolved for the shot.  Its
    magnetics group's ``measurement_chain`` names the tree (:func:`chain_tree`) and
    is stamped on the output; a ``measurement_chain`` that differs from it is
    refused (geometry and readings of two chains are never paired).

    ★★``elm`` turns the windowed mean into an **ELM-phase conditional** mean
    (H-15 / ``FYL-SDD-07`` 1.2).  It is opt-in and OFF by default: absent,
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
    series (None == node-not-found).  The magnetic reduction is the GUI_v5
    windowed mean (|t−t₀| ≤ ``window_ms``) with pre-shot linear drift subtraction
    over ``drift_window``; POINT uses its own ``point_window_ms`` window after the
    pre-shot offset subtraction.  Probe weights follow the rule in the module
    header (``probe_weight_rule`` in the output).
    """
    import numpy as np

    dev = _dev()
    names = _names(device_doc)
    doc = device_doc if device_doc is not None else names["EAST_DEVICE"]
    mag = doc["magnetics"]
    chain = mag.get(dev.CHAIN_KEY)
    if measurement_chain is not None and measurement_chain != chain:
        raise error(
            f"raw reduce: measurement chain {measurement_chain!r} was asked for, but the "
            f"device document's magnetics group is in {chain!r} — geometry and readings of "
            "two chains are never paired; resolve the device in that chain "
            f"(fylite.device.document(shot=..., measurement_chain={measurement_chain!r}))")
    tree = chain_tree(chain)
    pcs_tree = names.get("PCS_TREE")

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
            raise error("raw reduce: `elm` needs both `time` and `dalpha` "
                        "(the series is handed in — this distribution names no D-alpha node)")
        elm_band = tuple(elm.get("phase", elm_band))
        elm_onset = elm_onsets(et, ey, threshold=float(elm.get("threshold", 0.3)),
                               refractory_ms=float(elm.get("refractory_ms", 2.0)),
                               noise_guard=float(elm.get("noise_guard", 5.0)))
        if len(elm_onset) < 2:
            raise error(f"raw reduce: the D-alpha series carries {len(elm_onset)} ELM onset(s) — "
                        "a phase needs two (it is a fraction of a period); this may be an L-mode or "
                        "ELM-free stretch, or the wrong channel")

    def avg(leaf, where, scale=1.0, required=True, drift=True):
        r = get(leaf, where)
        if r is None:
            if required:
                raise error(f"raw reduce: required node {leaf} ({where}) absent")
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
                    f"raw reduce: no sample of {leaf} lies in both the +/-{window_ms} ms window at "
                    f"{tw} s and the ELM phase band {elm_band} ({int(sel.sum())} in the window, "
                    f"{int(band[:n].sum())} in the band over the whole series) — widen the window, "
                    "widen the band, or pick a slice with an inter-ELM stretch in it")
            sel = both
        return float(np.mean(s[sel])) * scale

    coils = [avg(nd, tree, 1.0 / (2.0 * np.pi))
             for nd in _need(names, "FLUX_LOOP_NODES", device_doc)]

    #: probe weights: the device's own per-channel `weight` when every probe carries
    #: one, else 1 for every probe that returned data (module header); 0 = no reading
    probe_chans = dev._aos(mag.get("b_field_pol_probe"))
    device_w = ([float(c["weight"]) for c in probe_chans]
                if probe_chans and all(isinstance(c, dict) and "weight" in c
                                       for c in probe_chans) else None)
    rule = "device" if device_w is not None else "unit"
    expmp2, fwtmp2 = [], []
    for i, nd in enumerate(_need(names, "B_PROBE_NODES", device_doc)):
        v = avg(nd, tree, required=False)
        expmp2.append(0.0 if v is None else v)
        fwtmp2.append(0.0 if v is None else (device_w[i] if device_w is not None else 1.0))

    turns = _need(names, "PF_TURNS", device_doc)
    raw_pf = [avg(nd, tree, turns[i], drift=False)
              for i, nd in enumerate(_need(names, "PF_NODES", device_doc))]
    brsp = [raw_pf[i] for i in _need(names, "PF_EFIT_ORDER", device_doc)]

    #: ★the main-tree Ip node is optional — a document built from the A-Box names
    #: none, because the A-Box binds Ip only in the PCS tree (the read below).
    ip_node = names.get("MDS_IP")
    plasma = (avg(ip_node, tree, 1000.0, required=False, drift=False)
              if ip_node else None)
    if plasma is None or abs(plasma) < 5.0e4:          # <50 kA: not a real Ip
        pcrl = (avg(r"\pcrl01", pcs_tree, required=False, drift=False)
                if pcs_tree else None)
        if pcrl is not None and abs(pcrl) > abs(plasma or 0.0):
            plasma = pcrl
    if plasma is None:
        raise error(f"no plasma current for shot {shot}: "
                    + (f"both {ip_node} ({tree}) and " if ip_node else
                       "the device document names no main-tree Ip node "
                       "(data_source.mdsplus.ip_node) and ")
                    + (rf"{pcs_tree}:\pcrl01 returned no data" if pcs_tree else
                       "no PCS tree (data_source.mdsplus.pcs_tree) to read it from"))

    if btor is None:
        a = avg(_need(names, "MDS_BT", device_doc), tree, 1.7 / 1.8 / 4086.0,
                required=False, drift=False)
        btor = a if (a and abs(a) > 0.5) else 1.8

    meas = {"shot": int(shot), "time_s": float(time_s),
            "itime_ms": int(round(float(time_s) * 1000)),
            "plasma": abs(plasma), "btor": float(btor),
            "brsp": brsp, "coils": coils, "expmp2": expmp2, "fwtmp2": fwtmp2,
            "n_probe_active": int(sum(1 for v in fwtmp2 if v > 0)),
            dev.CHAIN_KEY: chain,
            "probe_weight_rule": rule,
            "source": source or f"mds:{tree}:{shot}"}

    if read_point:                                    # POINT polarimeter-interfer.
        pw = (point_window_ms if point_window_ms is not None
              else _need(names, "POINT_WINDOW_MS", device_doc)) / 1e3
        base_s = _need(names, "POINT_BASELINE_S", device_doc)
        base_tol = _need(names, "POINT_BASELINE_TOL", device_doc)

        def point_chord(node):
            """Windowed mean after the pre-shot offset subtraction."""
            r = get(node, tree)
            if r is None:
                return None
            s = np.asarray(r[0], dtype=float)
            tb = np.asarray(r[1], dtype=float)
            n = min(len(s), len(tb))
            s, tb = s[:n], tb[:n]
            base = np.abs(tb - base_s) < base_tol
            s = s - (float(np.mean(s[base])) if base.any() else 0.0)
            sel = np.abs(tb - tw) <= pw
            if not sel.any():
                sel = np.zeros(n, bool)
                sel[int(np.abs(tb - tw).argmin())] = True
            return float(np.mean(s[sel]))

        ne_l = [point_chord(nd) for nd in _need(names, "POINT_NE_NODES", device_doc)]
        fr_l = [point_chord(nd) for nd in _need(names, "POINT_FR_NODES", device_doc)]
        kpol = -1.0 if (fr_l[0] is not None and fr_l[0] < 0) else 1.0
        c_far = (_need(names, "POINT_FARADAY_C", device_doc)
                 * _need(names, "POINT_LASER_LAMBDA", device_doc) ** 2)
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
        meas["point"] = {"n_chord": _need(names, "POINT_NCHORD", device_doc), "kpol": kpol,
                         "bnel": bnel, "bpolar": bpolar,
                         "fwtnel": fwtnel, "fwtpol": fwtpol,
                         "n_ne_active": int(sum(fwtnel)),
                         "n_fr_active": int(sum(fwtpol)),
                         "fringe_dropped": dropped}
    return meas


def read_hdf5_dump(dump_dir, shot: int, time_s: float, *,
                   measurement_chain: str | None = None,
                   window_ms: float = 5.0,
                   btor: float | None = None,
                   drift_window: tuple | None = (-6.9, -6.1),
                   read_point: bool = False,
                   point_window_ms: float | None = None,
                   point_fringe_gate: float = 0.15) -> dict:
    """Offline measurement dict from a fyo-semantic HDF5 dump of raw series
    (``<dump_dir>/<shot>_magnetics.h5`` + ``<shot>_pf_active.h5``; with
    ``read_point`` also ``_polarimeter.h5`` + ``_interferometer.h5``): the dump's
    full series are served to the SHARED :func:`reduce_series` against the bound
    device, so the result is byte-identical to :func:`read_mds` off live MDSplus
    for the same device.

    Nodes are found by each channel's ``name`` attribute, in the order the bound
    device lists them — no hardcoded ordering.  A main-tree Ip absent from the dump
    falls to the PCS Rogowski exactly as the live path does.
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
        raise _bad_input()(f"HDF5 dump missing: {dump / f'{shot}_magnetics.h5'}")
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
    if read_point:                    # POINT: faraday + n_e chords
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
        return reduce_series(get, shot, time_s, measurement_chain=measurement_chain,
                             window_ms=window_ms, btor=btor,
                             drift_window=drift_window, read_point=read_point,
                             point_window_ms=point_window_ms,
                             point_fringe_gate=point_fringe_gate,
                             source=f"fyo-hdf5:{dump}", error=_bad_input())
    finally:
        for f in files:
            f.close()


# ---------------------------------------------------------------------------
# Direct MDSplus read
#
# ★★2026-09-01 自 `io/kfile.py` 迁入（那个模块整体移除：它是 EFIT `&IN1` k-file 的
# 写入机）。★2026-09-13 随 est2 移除从 `io/est2.py` 迁到这里，改名 `read_mds`：读的
# 树与通道不再是字面量，而是按炮号与测量链解析出的装置文档给的。
# ---------------------------------------------------------------------------
def read_mds(shot: int, time_s: float, *,
             measurement_chain: str | None = None,
             server: str | None = None,
             window_ms: float = 5.0,
             btor: float | None = None,
             read_point: bool = False,
             point_window_ms: float | None = None,
             point_fringe_gate: float = 0.15,
             drift_window: tuple[float, float] | None = (-6.9, -6.1)) -> dict:
    """Read one slice of raw series off MDSplus and reduce it (:func:`reduce_series`).

    Headless reproduction of the GUI_v5 data path — NO dialogs, NO plotting.  The
    device is resolved for ``shot`` in ``measurement_chain`` (default: the bound
    device's magnetics chain) through :func:`fylite.device.document`; its channels
    are read from that chain's tree (:func:`chain_tree`), each averaged over
    ``[t-window, t+window]``:

    * the flux loops -> ``coils`` (value/2/pi, Wb/rad);
    * the poloidal probes -> ``expmp2`` (Tesla), ``fwtmp2`` by the weight rule;
    * the PF Rogowskis × turns -> ``brsp`` in the document's fit order;
    * Ip [A] (main-tree node if the document names one, else the PCS Rogowski);
      Btor from the document's toroidal-field node.

    ``server`` resolves through :func:`fylite.device.mdsip_server`
    (``server=`` → ``$FYLITE_MDSIP_SERVER`` → the device document).  Reads through
    the engine's mdsip client.
    """
    import numpy as np
    from .. import kernel
    from .mds import MdsError, _server

    dev = _dev()
    chain = measurement_chain if measurement_chain is not None else dev.measurement_chain()
    doc = dev.document(shot=int(shot), measurement_chain=chain)
    tree = chain_tree(doc["magnetics"].get(dev.CHAIN_KEY))

    host, port = _server(server)
    #: ★★2026-09-04：transport is the engine's mdsip client, not the site
    #: ``MDSplus`` package (see :mod:`.mds` for what left with it).  One
    #: session, one current tree — re-select only on a switch.
    conn = kernel.MdsSession(host, port)
    _cur = {"tree": None}

    def get(leaf, where):
        """Full series ``(data, time)`` for one leaf on tree ``where`` — the node
        provider handed to the shared reducer; None on NNF (absent node)."""
        nd = leaf if leaf.startswith("\\") else "\\" + leaf
        if where != _cur["tree"]:
            conn.open_tree(where, int(shot))
            _cur["tree"] = where
        try:
            s, _d = conn.read("data", nd)
            tb, _d = conn.read("dim_of", nd)
            return np.asarray(s, dtype=float), np.asarray(tb, dtype=float)
        except kernel.KernelError:             # NNF is data, not a failure
            return None

    try:
        return reduce_series(
            get, shot, time_s, device_doc=doc, measurement_chain=chain,
            window_ms=window_ms, btor=btor,
            drift_window=drift_window, read_point=read_point,
            point_window_ms=point_window_ms, point_fringe_gate=point_fringe_gate,
            source=f"mdsplus:{host}:{port}:{tree}:{shot}", error=MdsError)
    finally:
        conn.close()
