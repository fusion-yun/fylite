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

__all__ = ["reduce_est2", "measurements_from_est2_hdf5", "read_east_mds"]


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
                point_fringe_gate: float = 0.15,
                source: str | None = None, error=RuntimeError) -> dict:
    """Reduce raw est2 series → the flat measurement dict (core: 35 flux loops,
    79 b-probes, 12 PF coils, Ip, Btor; ``read_point`` adds the 11-chord POINT
    polarimeter/interferometer block).

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
        # fringe-jump hygiene: an interferometer chord whose |n_e,line| collapses
        # to a small fraction of the median has lost fringes -> drop it (and its
        # paired Faraday chord, which shares the density). gate<=0 disables.
        mag = np.array([abs(v) if v is not None else 0.0 for v in ne_l])
        med = float(np.median(mag[mag > 0])) if (mag > 0).any() else 0.0
        floor = point_fringe_gate * med if point_fringe_gate > 0 else -1.0
        bnel, bpolar, fwtnel, fwtpol, dropped = [], [], [], [], []
        for i, (a_ne, b_fr) in enumerate(zip(ne_l, fr_l)):
            good = (a_ne is not None) and (abs(a_ne) > floor)
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
    ``KEFIT_MDS_SERVER`` env).  Requires the ``MDSplus`` thin client.
    """
    import MDSplus  # deferred: from the shared login environment
    import numpy as np

    host = server or os.environ.get("KEFIT_MDS_SERVER") or device.MDS_SERVER
    conn = MDSplus.Connection(host)
    _cur = {"tree": None}

    def read_tree(tree):
        conn.openTree(tree, int(shot))
        _cur["tree"] = tree

    def get(leaf, tree):
        """Full series ``(data, time)`` for one leaf on ``tree`` — the node
        provider handed to the shared est2 reducer; None on NNF (absent node).
        MDSplus.Connection has a single current-tree context, so re-select only
        on a switch."""
        nd = leaf if leaf.startswith("\\") else "\\" + leaf
        if tree != _cur["tree"]:
            read_tree(tree)
        try:
            s = np.asarray(conn.get(nd).data(), dtype=float)
            tb = np.asarray(conn.get(f"dim_of({nd})").data(), dtype=float)
            return s, tb
        except Exception:                      # noqa: BLE001 — NNF is data
            return None

    # Full est2 reduction (loops/probes/PF/Ip/Btor + optional POINT) is the ONE
    # implementation in io.est2.reduce_est2, shared with the offline HDF5 reader
    # so the live and offline paths are byte-identical.
    meas = est2.reduce_est2(
        get, shot, time_s, window_ms=window_ms, btor=btor,
        drift_window=drift_window, read_point=read_point,
        point_window_ms=point_window_ms, point_fringe_gate=point_fringe_gate,
        source=f"mdsplus:{host}:east:{shot}", error=KefitReadError)
    conn.closeAllTrees()
    return meas


