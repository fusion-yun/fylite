"""Direct EAST MDSplus (efit_east tree) -> measurement dict.

Data source: ``KEFIT_MDS_SERVER`` (``host`` or ``host:port``, port 8000 by
default; the site's own address comes from whoever runs the server, and from
the device deck's ``fylite:mds.server`` — it is not written down here), else
the device document's declared server.  Transport is the engine's read-only
mdsip client (:class:`fylite.kernel.MdsSession`); see :func:`_session` for
what left with the site ``MDSplus`` package (2026-09-04).

Nodes read (all on the shared GTIME base):
  \\EFIT_EAST::TOP.MEASUREMENTS:EXPMPI   (t, 38|76)  probes  -> EXPMP2
  \\EFIT_EAST::TOP.MEASUREMENTS:SILOPT   (t, 35)     loops   -> COILS
  \\EFIT_EAST::TOP.MEASUREMENTS:FCCURT   (t, 13)     F-coils -> BRSP[0:12]
  \\EFIT_EAST::TOP.MEASUREMENTS:PLASMA   (t,)        Ip [A]  -> PLASMA
  \\EFIT_EAST::TOP.RESULTS.GEQDSK:GTIME  time base [s]
  \\BCENTR -> BTOR; if absent, fall back to FPOL edge value / device.RCENTR
    (vacuum R*Bt).  ★2026-09-01: this used to name
    ``\\EFIT_EAST::TOP.RESULTS.GEQDSK:BCENTR``, which answers size 0 /
    ``%TREE-E-NODATA`` on **every** shot tried (#100000 #137984 #137985 #140000
    #150000 #165704) — so the fallback below ran always, and the comment that
    said "NODATA on some shots" was a wrong path written down as a fact about
    the machine.  The tag answers 112 points with units ``T``.

FCCURT units decision (data-driven, shot 70754 @ 3.5 s):
  FCCURT[0:12] = [5.4e5, -7.1e4, 4.9e5, 2.0e6, -4.8e5, 2.8e4, 5.5e5, 2.3e5,
  1.8e5, 2.0e6, -4.7e5, 3.2e4] for a 0.50 MA shot — the same 1e5–1e6 scale as
  the reference k-file BRSP for the 1.0 MA shot 93060 (9.4e5 … 2.9e6).
  Dividing by TURNFC (32–248) would leave O(1e3–1e4) A, far too small to be
  A-turns after re-multiplication. => FCCURT is already **A-turns** and is
  passed to BRSP unchanged.  The 13th column (~-4.5e3, in-vessel/IC circuit)
  is DROPPED.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from .. import device


class MdsError(RuntimeError):
    pass



def _probe_gate() -> tuple[float, float]:
    """探针有效性门限 ``(min_tesla, max_tesla)``，取自装置文档。

    ★★2026-09-01：此前这两个数经 ``io.kfile.PROBE_GATE_MIN/MAX`` 取——而 kfile
    是 EFIT ``&IN1`` 的**写入机**，已整体移除。门限本身与 k-file 无关：它是这台
    机器的**装置事实**（``operational.probe_gate``），写在装置文档里，本模块读它
    比经过一个写输入文件的模块更短、也更说得清它是什么。
    """
    op = device.document()["operational"]["probe_gate"]
    return float(op["min_tesla"]), float(op["max_tesla"])


def _server(spec: str | None = None) -> tuple[str, int]:
    """``host`` or ``host:port`` → ``(host, port)``; port defaults to 8000 (mdsip)."""
    spec = spec or os.environ.get("KEFIT_MDS_SERVER") or device.MDS_SERVER
    host, _, port = str(spec).partition(":")
    return host, (int(port) if port else 8000)


def _session(tree: str, shot: int, server: str | None = None):
    """An open, read-only mdsip session on ``tree`` / ``shot``.

    ★★2026-09-04：transport is the ENGINE's mdsip client
    (:class:`fylite.kernel.MdsSession`), not the site ``MDSplus`` package.
    Two things left with that package: the local-tree mode
    (``KEFIT_MDS_ROOT`` + ``MDSplus.Tree``) — the engine speaks the wire
    protocol, not the tree file format, and the only tree that mode ever
    pointed at lived under the retired ``machine_desc/`` — and the
    ``efit_east_path`` environment plumbing that mode needed.
    """
    from .. import kernel
    host, port = _server(server)
    s = kernel.MdsSession(host, port)
    try:
        s.open_tree(tree, int(shot))
    except kernel.KernelError as e:
        s.close()
        raise MdsError(f"cannot open {tree} shot {shot} on {host}:{port}: {e}") from e
    return s


def _get(s, node: str) -> np.ndarray:
    """``data(node)`` as a numpy array in row-major index order.

    ★The wire gives dims **fastest-varying axis first** (`mdsip.rs`);
    numpy's ``a[it][ch]`` wants the slowest first, so a 2-D answer is
    reshaped with the dims REVERSED — the same rule ``mdsbind`` applies on
    the Rust side.  Reversing the bytes instead of the dims would read a
    silently transposed table, which this repository has met once already.
    """
    v, dims = s.read("data", node)
    return v.reshape(tuple(reversed(dims))) if len(dims) > 1 else v


def _dim_of(s, node: str) -> np.ndarray:
    v, _dims = s.read("dim_of", node)
    return v


def _pick(gt: np.ndarray, time_s: float, interp: str):
    """Return (index or None, weights) — nearest sample by default."""
    if interp == "nearest":
        return int(np.argmin(np.abs(gt - time_s)))
    raise ValueError(f"unsupported interp mode {interp!r}")


def fetch_measurements(shot: int, time_s: float, *,
                       btor: float | None = None,
                       interp: str = "nearest") -> dict:
    """Read the efit_east measurement nodes at the sample nearest ``time_s``.

    Returns a measurement dict for the reconstruction face (without itime_ms —
    the caller sets it; ``sample_time_s`` reports the actual sample used).
    ``btor`` overrides the BCENTR/FPOL-derived toroidal field.
    """
    host, port = _server()
    source = f"{host}:{port}"
    s = _session("efit_east", shot)

    def get(path):
        return _get(s, path)

    M = r"\EFIT_EAST::TOP.MEASUREMENTS:"
    G = r"\EFIT_EAST::TOP.RESULTS.GEQDSK:"
    gt = get(G + "GTIME")
    it = _pick(gt, float(time_s), interp)
    sample_t = float(gt[it])

    expmpi = get(M + "EXPMPI")
    silopt = get(M + "SILOPT")
    fccurt = get(M + "FCCURT")
    plasma = get(M + "PLASMA")

    nch = expmpi.shape[1]
    expmp2 = np.zeros(device.NPROBE)
    fwtmp2 = np.zeros(device.NPROBE)
    expmp2[:min(nch, device.NPROBE)] = expmpi[it][:device.NPROBE]
    # Probe channel gating (data hygiene, the fitweight.dat role — NOT tuning):
    # weight 1 only for present channels with a plausible |B| (Tesla), the
    # shared PROBE_GATE_MIN/MAX bounds.  #70754 diagnosis (2026-07-21):
    # 39/76 channels dead + 3 outliers; weighting them 1.0 collapses the fitted
    # current and breaks the boundary tracer, while the 34 live channels agree
    # with the equilibrium field (corr 0.75, median ratio 0.94).
    lo, hi = _probe_gate()
    ok = (np.abs(expmp2) > lo) & (np.abs(expmp2) < hi)
    fwtmp2[:min(nch, device.NPROBE)] = ok[:min(nch, device.NPROBE)].astype(float)
    if silopt.shape[1] < device.NSILOP:
        raise MdsError(f"SILOPT has {silopt.shape[1]} channels, need {device.NSILOP}")
    coils = silopt[it][:device.NSILOP]

    # FCCURT: first 12 columns, A-turns (see module docstring); col 13 dropped.
    brsp = list(map(float, fccurt[it][:12]))

    if btor is None:
        try:
            btor = float(get("\\BCENTR")[it])
        except Exception:
            # genuinely unreadable on this shot: vacuum R*Bt from FPOL edge
            try:
                fpol = get(G + "FPOL")
                btor = float(fpol[it][-1]) / device.RCENTR
            except Exception as e:
                raise MdsError(
                    f"no \\BCENTR and no FPOL for shot {shot}: pass btor= "
                    f"explicitly") from e

    s.close()
    return {"shot": int(shot), "time_s": float(time_s),
            "sample_time_s": sample_t, "sample_index": it,
            "plasma": float(plasma[it]), "btor": float(btor),
            "brsp": brsp, "coils": list(map(float, coils)),
            "expmp2": list(map(float, expmp2)),
            "fwtmp2": list(map(float, fwtmp2)),
            "n_probe_channels": int(nch),
            "source": f"mdsplus:{source}:efit_east:{shot}"}


def fetch_thomson(shot: int, time_s: float, *,
                  server: str | None = None) -> dict:
    """Read the EAST core Thomson-scattering profile nearest ``time_s``, plus
    the TXCS core ion temperature — the raw inputs for a kprfit=1 pressure
    constraint (:func:`pressure_from_thomson`).

    Reads through the engine's mdsip client (like the est2 path):

    * ``ts_east``: ``\\TE_CORETS`` / ``\\NE_CORETS`` — rows are laser slices
      with **column 0 = time [s]** and columns 1..N the values at the N
      spatial points of ``\\R_CORETS`` / ``\\Z_CORETS`` (vertical chord,
      R = 1.9 m on 137985; Z spans about -0.15..0.66 m, not monotonic);
    * ``analysis``: ``\\TI0_TXCS`` — core T_i(t) [eV], window-averaged
      (+-0.2 s) around the chosen Thomson slice; None when absent.

    Returns raw, UNFILTERED points (te [eV], ne [m^-3], r/z [m]); quality
    gating (dead-channel floor, ne range) is the assembler's job.
    """
    host, port = _server(server)
    s = _session("ts_east", shot, server)
    te2 = _get(s, r"\TE_CORETS")
    ne2 = _get(s, r"\NE_CORETS")
    r = _get(s, r"\R_CORETS")
    z = _get(s, r"\Z_CORETS")
    if te2.ndim != 2 or te2.shape[1] < 2:
        raise MdsError(f"TE_CORETS shape {te2.shape} not (slices, 1+npts)")
    slice_t = te2[:, 0]                    # column 0 carries the slice time
    it = int(np.argmin(np.abs(slice_t - float(time_s))))
    sample_t = float(slice_t[it])
    te = te2[it, 1:]
    ne = ne2[it, 1:]
    # per-point measurement error (\TE_CORETSERR / \NE_CORETSERR, same
    # slices x (1+npts) layout as the values): the diagnostic's own reported
    # 1-sigma.  Best-effort — some vintages lack it, some points carry garbage
    # fill-values on failed channels (those are gated by value or naturally
    # down-weighted by 1/sigma^2 downstream).  None -> the assembler falls back
    # to a flat fractional sigma.
    te_err = ne_err = None
    try:
        teE = _get(s, r"\TE_CORETSERR")
        neE = _get(s, r"\NE_CORETSERR")
        if teE.shape == te2.shape and neE.shape == ne2.shape:
            te_err = teE[it, 1:]
            ne_err = neE[it, 1:]
    except Exception:
        pass                               # error nodes absent -> None
    npts = min(len(te), len(ne), len(r), len(z))
    te, ne, r, z = te[:npts], ne[:npts], r[:npts], z[:npts]
    if te_err is not None:
        te_err, ne_err = te_err[:npts], ne_err[:npts]

    ti0 = None
    try:
        s.open_tree("analysis", int(shot))
        tiv = _get(s, r"\TI0_TXCS")
        tit = _dim_of(s, r"\TI0_TXCS")
        sel = np.abs(tit - sample_t) <= 0.2
        if not sel.any():
            sel = np.zeros(len(tit), bool)
            sel[int(np.abs(tit - sample_t).argmin())] = True
        ti0 = float(np.mean(tiv[sel]))
    except Exception:
        pass                               # TXCS absent -> electron-only

    s.close()
    return {"shot": int(shot), "time_s": float(time_s),
            "sample_time_s": sample_t, "slice_index": it,
            "r": list(map(float, r)), "z": list(map(float, z)),
            "te": list(map(float, te)), "ne": list(map(float, ne)),
            "te_err": None if te_err is None else list(map(float, te_err)),
            "ne_err": None if ne_err is None else list(map(float, ne_err)),
            "ti0": ti0,
            "source": f"mdsplus:{host}:{port}:ts_east:{shot}"}


def _thomson_rel_sigma(th: dict, ne, te, *, cap: float):
    """Per-point relative 1-sigma from the Thomson error nodes:
    ``sqrt((dne/ne)^2 + (dTe/Te)^2)``, aligned to the full point list.

    Returns ``(rel, usable)`` where ``usable`` is finite, positive and within
    ``cap`` (garbage fill-values on failed channels reach ~1e5-1e8 and are cut
    far below any real Thomson error ~<1); ``(None, None)`` when the payload
    carries no error nodes (older vintages) — the caller then falls back to a
    flat fractional sigma.
    """
    if th.get("te_err") is None or th.get("ne_err") is None:
        return None, None
    dte = np.abs(np.asarray(th["te_err"], dtype=float))
    dne = np.abs(np.asarray(th["ne_err"], dtype=float))
    with np.errstate(divide="ignore", invalid="ignore"):
        rte = dte / np.where(te != 0, te, np.nan)
        rne = dne / np.where(ne != 0, ne, np.nan)
        rel = np.sqrt(rte ** 2 + rne ** 2)
    usable = np.isfinite(rel) & (rel > 0) & (rel <= float(cap))
    return rel, usable


def pressure_from_thomson(th: dict, *, sigpre_frac: float = 0.2,
                          te_floor: float = 50.0,
                          te_ceiling: float = 8000.0,
                          ne_range: tuple = (1e18, 2e21),
                          ti0: float | None = None,
                          zeff_dilution: float = 1.0,
                          use_measured_sigma: bool = True,
                          sigma_floor: float = 0.05,
                          sigma_cap: float = 2.0) -> dict:
    """Assemble a kprfit=1 ``meas["pressure"]`` dict from Thomson (+TXCS) data.

    Per accepted point (real-space (R,Z) — EFIT maps them through its own
    psi, RPRESS>0 convention):

        p = e * ne * Te * (1 + dilution * Ti0/Te0)   [Pa]

    with two DECLARED assumptions, reported in ``["assumptions"]``:

    * ``ti_shape``: T_i(x) = Ti0 * Te(x)/Te0 (TXCS gives only the core value;
      the 2-D TXCS profile is NODATA on the surveyed shots) — so p_i scales
      p_e by the constant Ti0/Te0.  Te0 is the **median of the 5 highest
      accepted Te** — robust against a single hot outlier channel (the raw
      max on 137985 reaches ~11.9 keV, K-1);
    * ``ni = dilution * ne`` (``zeff_dilution``, default 1.0 — no Zeff
      correction; fast-ion pressure NOT included: expect a low bias on
      NBI-heated shots).

    Quality gate (K-1): drop points with Te <= ``te_floor`` (dead-channel
    floor is ~20 eV on ts_east), Te >= ``te_ceiling`` (default 8 keV —
    outlier channels well above any plausible EAST core Te), or ne outside
    ``ne_range``.

    ``sigpre`` (K-13 / K-1 residual): when the payload carries the Thomson
    error nodes and ``use_measured_sigma``, each point's 1-sigma is the
    diagnostic's own **measured** relative error propagated to pressure —
    ``sigma_p/p = sqrt((dne/ne)^2 + (dTe/Te)^2)`` — floored at ``sigma_floor``
    (a single over-tight point must not dominate) and its failed channels (rel
    > ``sigma_cap``) dropped from the gate.  Absent errors (or
    ``use_measured_sigma=False``) fall back to the flat ``sigpre_frac``·p.
    Either way a 100 Pa absolute floor applies.
    """
    te = np.asarray(th["te"], dtype=float)
    ne = np.asarray(th["ne"], dtype=float)
    r = np.asarray(th["r"], dtype=float)
    z = np.asarray(th["z"], dtype=float)
    ok = (te > float(te_floor)) & (te < float(te_ceiling)) \
        & (ne > ne_range[0]) & (ne < ne_range[1]) \
        & np.isfinite(te) & np.isfinite(ne)
    rel, usable = ((None, None) if not use_measured_sigma
                   else _thomson_rel_sigma(th, ne, te, cap=sigma_cap))
    if rel is not None:
        ok = ok & usable                   # drop failed-channel (garbage-err) points
    if not ok.any():
        raise MdsError("pressure_from_thomson: no Thomson point passed the "
                       f"quality gate (te_floor={te_floor}, "
                       f"te_ceiling={te_ceiling}, ne_range={ne_range})")
    te, ne, r, z = te[ok], ne[ok], r[ok], z[ok]
    t_i0 = float(ti0 if ti0 is not None else (th.get("ti0") or 0.0))
    # robust core Te: median of the top-5 accepted values (a single surviving
    # outlier would otherwise set the ion factor for every point)
    top = np.sort(te)[-5:]
    te0 = float(np.median(top))
    ion_factor = 1.0 + float(zeff_dilution) * (t_i0 / te0 if te0 > 0 else 0.0)
    e_charge = 1.602176634e-19
    p = e_charge * ne * te * ion_factor
    if rel is not None:
        rel_ok = np.clip(rel[ok], float(sigma_floor), None)
        sigpre = np.maximum(rel_ok * p, 100.0)
        sigma_source = "measured"
    else:
        sigpre = np.maximum(sigpre_frac * p, 100.0)
        sigma_source = "flat_fraction"
    return {"r": list(map(float, r)), "z": list(map(float, z)),
            "pressr": list(map(float, p)),
            "sigpre": list(map(float, sigpre)),
            "sigma_source": sigma_source,
            "sigma_rel_median": (float(np.median(rel[ok])) if rel is not None
                                 else float(sigpre_frac)),
            "n_points": int(ok.sum()), "n_dropped": int((~ok).sum()),
            "ti0": t_i0, "te0": te0, "ion_factor": float(ion_factor),
            "assumptions": {
                "ti_shape": "Ti(x) = Ti0*Te(x)/Te0 (TXCS core value only; "
                            "Te0 = median of top-5 accepted Te)",
                "ni": f"ni = {zeff_dilution}*ne (no Zeff correction)",
                "fast_ion": "fast-ion pressure NOT included",
                "sigpre": (f"measured per-point sqrt((dne/ne)^2+(dTe/Te)^2), "
                           f"floor {sigma_floor}, failed-channel cap {sigma_cap}"
                           if sigma_source == "measured"
                           else f"flat {sigpre_frac} of p (no error nodes)")},
            "source": th.get("source")}


def thomson_ne_points(th: dict, *, sig_frac: float = 0.15,
                      te_floor: float = 50.0, te_ceiling: float = 8000.0,
                      ne_range: tuple = (1e18, 2e21),
                      use_measured_sigma: bool = True,
                      sigma_floor: float = 0.05, sigma_cap: float = 2.0) -> dict:
    """Assemble a ``meas["thomson_ne"]`` dict (density-spline rows, K-5) from
    the same :func:`fetch_thomson` payload the pressure path uses.

    Same quality gate as :func:`pressure_from_thomson` (a point must carry a
    credible Te for its ne to be trusted — Thomson infers both from the same
    scattered spectrum).  Values are converted to the density-spline working
    unit (1e19 m^-3).  ``sig19`` (K-13) uses the **measured** ne error
    ``\\NE_CORETSERR`` when present (floored at ``sigma_floor``·ne, failed
    channels rel > ``sigma_cap`` dropped); else the flat ``sig_frac``·ne, both
    with a 0.05 (1e19) absolute floor.
    """
    te = np.asarray(th["te"], dtype=float)
    ne = np.asarray(th["ne"], dtype=float)
    r = np.asarray(th["r"], dtype=float)
    z = np.asarray(th["z"], dtype=float)
    ok = (te > float(te_floor)) & (te < float(te_ceiling)) \
        & (ne > ne_range[0]) & (ne < ne_range[1]) \
        & np.isfinite(te) & np.isfinite(ne)
    ne_err = th.get("ne_err")
    rel_ne = usable = None
    if use_measured_sigma and ne_err is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_ne = np.abs(np.asarray(ne_err, dtype=float)) \
                / np.where(ne != 0, ne, np.nan)
        usable = np.isfinite(rel_ne) & (rel_ne > 0) & (rel_ne <= float(sigma_cap))
        ok = ok & usable
    if not ok.any():
        raise MdsError("thomson_ne_points: no Thomson point passed the gate")
    ne19 = ne[ok] / 1e19
    if rel_ne is not None:
        sig19 = np.maximum(np.clip(rel_ne[ok], float(sigma_floor), None) * ne19,
                           0.05)
        sigma_source = "measured"
    else:
        sig19 = np.maximum(sig_frac * ne19, 0.05)
        sigma_source = "flat_fraction"
    return {"r": list(map(float, r[ok])), "z": list(map(float, z[ok])),
            "ne19": list(map(float, ne19)),
            "sig19": list(map(float, sig19)),
            "sigma_source": sigma_source,
            "n_points": int(ok.sum()), "n_dropped": int((~ok).sum()),
            "source": th.get("source")}


def fetch_diamagnetic(shot: int, time_s: float, *, node: str = r"\Diahi1",
                      window_s: float = 0.05,
                      baseline_window: tuple = (-5.0, -1.0),
                      scale_mwb_per_v: float | None = None,
                      server: str | None = None) -> dict:
    """Read the EAST diamagnetic-loop signal for a DFLUX constraint (K-3).

    ``east:\\Diahi1`` is an integrator output in **volts** (137985: pre-shot
    -0.008 V, flat-top plateau -0.030 V, std 3e-4 — flux-proportional).  This
    returns the baseline-subtracted window average in volts; converting to
    the solver's ``DFLUX`` (mWb; ``diamag = 1e-3*dflux`` in the Fortran)
    requires the loop calibration constant, which is NOT publicly recorded
    — pass ``scale_mwb_per_v`` explicitly to get ``dflux_mwb``, else only
    the raw volts are returned and nothing should be wired into the fit.
    """
    host, port = _server(server)
    s = _session("east", shot, server)
    nd = node if node.startswith("\\") else "\\" + node
    d = _get(s, nd)
    t = _dim_of(s, nd)
    s.close()
    n = min(len(d), len(t))
    d, t = d[:n], t[:n]
    b = (t >= baseline_window[0]) & (t <= baseline_window[1])
    base = float(d[b].mean()) if b.any() else 0.0
    sel = np.abs(t - float(time_s)) <= window_s
    if not sel.any():
        raise MdsError(f"{nd}: no samples within {window_s}s of t={time_s}")
    volts = float(d[sel].mean() - base)
    out = {"shot": int(shot), "time_s": float(time_s), "node": nd,
           "volts": volts, "volts_std": float(d[sel].std()),
           "baseline_v": base,
           "dflux_mwb": (volts * scale_mwb_per_v
                         if scale_mwb_per_v is not None else None),
           "scale_mwb_per_v": scale_mwb_per_v,
           "source": f"mdsplus:{host}:{port}:east:{shot}"}
    return out


#: ★NO CALLER in this package.  That is not a defect here the way it is
#: elsewhere: :mod:`fylite.io` exists to read other people's formats for
#: whoever needs them, and a reader with no in-package consumer is still a
#: usable one.  Noted so the next audit does not have to re-derive it.
def efit_reference(shot: int, time_s: float) -> dict:
    """efit_east reference GEQDSK slice (for comparison/reporting only)."""
    s = _session("efit_east", shot)

    def get(path):
        return _get(s, path)

    G = r"\EFIT_EAST::TOP.RESULTS.GEQDSK:"
    A = r"\EFIT_EAST::TOP.RESULTS.AEQDSK:"
    M = r"\EFIT_EAST::TOP.MEASUREMENTS:"
    gt = get(G + "GTIME")
    it = int(np.argmin(np.abs(gt - float(time_s))))
    out = {"it": it, "t": float(gt[it])}
    nb = int(get(G + "NBBBS")[it])
    out["rbbbs"] = get(G + "RBBBS")[it][:nb]
    out["zbbbs"] = get(G + "ZBBBS")[it][:nb]
    out["rmaxis"] = float(get(G + "RMAXIS")[it])
    out["zmaxis"] = float(get(G + "ZMAXIS")[it])
    out["psi_axis"] = float(get(G + "SSIMAG")[it])
    out["psi_bry"] = float(get(G + "SSIBRY")[it])
    out["ip"] = float(get(M + "PLASMA")[it])
    out["qpsi"] = get(G + "QPSI")[it]
    for key, path in (("q95", A + "Q95"), ("betap", A + "BETAP"),
                      ("li", A + "LI")):
        try:
            out[key] = float(get(path)[it])
        except Exception:
            out[key] = float("nan")
    s.close()
    return out
