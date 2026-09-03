"""Minimal GEQDSK reader / writer — enough for run summaries and comparisons.

★★The writer is here, beside the reader, because ``FR-DATA-002`` asks for a
round trip ("平衡结果必须可写出与读回 g-file 格式") and only the read half
existed in this module.  The write half was in :mod:`fylite.appsession`,
reachable only from a browser session document — so a reconstruction computed
in this process could not be written out at all, which is what left
``fylite run`` with a ``res['gfile']`` nothing produced.  The formatter moved;
:mod:`fylite.appsession` calls it here now, so there is still exactly one
place that knows the format's column rules.

★It also hosts the two things every consumer of a g-file derives before it
can do anything: the ``(R, Z)`` grid the header implies and the normalised
flux on it (:func:`grid`, :func:`flux_map`).  Those had been written out
per consumer — the plotting module owned the grid and three physics modules
imported it from there, each then normalising psi itself with its own
flat-psi guard.  A g-file's own geometry belongs beside the g-file reader,
and a matplotlib module is not where a transport metric should be reaching
for it.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np



#: g-file numbers are five to a line, 16 columns each, ``%16.9E``.
_PER_LINE = 5


def _f16(v) -> str:
    return f"{float(v):16.9E}"


def _block(arr) -> str:
    out = []
    for i, v in enumerate(arr):
        out.append(_f16(v))
        if i % _PER_LINE == _PER_LINE - 1:
            out.append("\n")
    if len(arr) % _PER_LINE:
        out.append("\n")
    return "".join(out)


def format_geqdsk(g: dict) -> str:
    """A g-file dict (:func:`read_geqdsk`'s shape) → GEQDSK text."""
    nw, nh = g["nw"], g["nh"]
    s = f"{str(g.get('header', 'fylite'))[:48]:<48}   0{nw:4d}{nh:4d}\n"
    s += _block([g["rdim"], g["zdim"], g["rcentr"], g["rleft"], g["zmid"]])
    s += _block([g["rmaxis"], g["zmaxis"], g["simag"], g["sibry"], g["bcentr"]])
    s += _block([g["current"], g["simag"], 0.0, g["rmaxis"], 0.0])
    s += _block([g["zmaxis"], 0.0, g["sibry"], 0.0, 0.0])
    for k in ("fpol", "pres", "ffprim", "pprime"):
        s += _block(g[k])
    s += _block(g["psirz"]) + _block(g["qpsi"])
    s += f"{g['nbbbs']:5d}{g['limitr']:5d}\n"
    s += _block([v for pair in zip(g["rbbbs"], g["zbbbs"]) for v in pair])
    s += _block([v for pair in zip(g["rlim"], g["zlim"]) for v in pair])
    return s


def write_geqdsk(g: dict, path: str | Path) -> Path:
    """Write a g-file dict and read it back before returning the path.

    ★The read-back is not belt-and-braces: this format carries nine
    significant digits in fixed columns, and a value that overflows one
    (or a length that disagrees with the header) produces a file that looks
    written and cannot be parsed.  Refusing to leave one behind is cheaper
    than discovering it downstream.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(format_geqdsk(g))
    read_geqdsk(p)
    return p


def gfile_name(shot=None, time_s=None) -> str:
    """The conventional deck name for a slice: ``g<shot>.<milliseconds>``.

    Falls back to a name that says what it is when there is no shot/time to
    build one from — a synthetic or file-driven run has neither, and naming
    it ``g000000.00000`` would claim a slice that does not exist.
    """
    if shot is None or time_s is None:
        return "g_reconstruction.geqdsk"
    return f"g{int(shot):06d}.{round(float(time_s) * 1000):05d}"


def read_geqdsk(path: str | Path) -> dict:
    """一份 g-file -> 字典。**读入在数据层**（`rust/fylite_runtime/`）。

    ★★2026-09-02：这里从前是本文件自己的固定列读法。本仓曾有三份 g-file 读入
    ——这一份、`app/assets/geqdsk.js`，与数据层那份；JS 的注释自己写着它返回的
    是「the same field names fylite's own `read_geqdsk` returns」。三处拼写、
    一个契约，而拼错了不报错。现在产品路径只有数据层那一条。

    ★**返回的仍然是 list**，不是 ndarray：本包有 17 个文件读这本字典，它们的
    契约是这本字典的形状，而换掉读入器不该是换掉那个形状的时机。

    ★★2026-09-04：那份固定列的 Python 参照读法（`_read_geqdsk_reference`）**不在本包里了**
    ——它搬进了它唯一的读者 `tests/test_gfile_equivalence.py`，作为那道闸自己的见证。
    包里只剩一份实现；见证留在判它的地方。
    """
    from .. import kernel

    g = kernel.read_gfile(path)
    out = dict(g)
    for name in kernel.GFILE_ARRAYS:
        out[name] = [float(x) for x in g[name]]
    return out



def grid(g: dict):
    """The ``(R, Z, psi)`` a g-file's header implies.

    ★``psi`` comes back indexed ``[z, r]`` — the file's OWN order, since
    GEQDSK writes ``((psi(i,j), i=1,nw), j=1,nh)`` with R fastest.  The
    kernel wants ``[r, z]``; on a square grid a missing transpose is not a
    crash but a differently-shaped plasma, so every caller that hands this
    to the kernel transposes explicitly rather than relying on the shape to
    say which way round it is.
    """
    r = g["rleft"] + np.linspace(0.0, g["rdim"], g["nw"])
    z = g["zmid"] - g["zdim"] / 2.0 + np.linspace(0.0, g["zdim"], g["nh"])
    psi = np.asarray(g["psirz"], dtype=float).reshape(g["nh"], g["nw"])
    return r, z, psi


def flux_map(g: dict):
    """``(R, Z, psi_N, dpsi)`` — :func:`grid` with psi normalised.

    ``psi_N = (psi - simag) / (sibry - simag)``, indexed ``[z, r]`` like
    :func:`grid`, and ``dpsi`` the span it was divided by (which callers
    need to get back to Wb/rad).  Raises :class:`ValueError` on a flat
    psi: there is no normalisation then, and a floor would hand every
    consumer a plasma filling the box.
    """
    r, z, psi = grid(g)
    dpsi = float(g["sibry"]) - float(g["simag"])
    if dpsi == 0.0:
        raise ValueError("flat psi (sibry == simag) — no flux map")
    return r, z, (psi - float(g["simag"])) / dpsi, dpsi


def kernel_flux_map(g: dict):
    """``(grid, psi_N[r, z], dpsi)`` — :func:`flux_map` in the KERNEL's
    index order.

    ★★The transpose is the whole content of this function, and it is here
    because it was written out in three modules, each with its own ★comment
    explaining it.  A g-file stores ``psi`` as ``[z, r]``; every kernel
    entry takes ``[r, z]``.  On a square grid — 65 x 65, which is what this
    device ships — a missing transpose is NOT a crash: it is a different
    plasma, and this repo measured one (kappa 1.41 against 2.05) before a
    second, independent path caught it.

    One host means one place to be wrong, and one place a reader has to
    check.
    """
    import numpy as _np
    r, z, psin, dpsi = flux_map(g)
    from .. import kernel as _kernel
    return (_kernel.grid_of(r, z),
            _np.ascontiguousarray(_np.asarray(psin, float).T), dpsi)


def limiter(g: dict):
    """``(rlim, zlim)`` as float arrays — empty when the deck carries none.

    An accessor, not a policy: what an empty limiter MEANS is the kernel's
    to say (``surfaces::trace``: the grid is the limiter).  This package
    used to answer that question itself, with a four-point box of the
    grid's edges built in ``metrics`` and borrowed by ``nbi`` through a
    private name; a deck without a limiter then traced one way from the
    hosts that built the box and another from any that did not.
    """
    return (np.asarray(g.get("rlim", []), float),
            np.asarray(g.get("zlim", []), float))


def q_at(g: dict, psin: float) -> float:
    """Linear interp of q on the uniform normalized-psi grid."""
    q = g["qpsi"]
    n = len(q)
    x = psin * (n - 1)
    i = min(int(x), n - 2)
    f = x - i
    return q[i] * (1 - f) + q[i + 1] * f


def summary(g: dict) -> dict:
    return {
        "psi_axis": g["simag"], "psi_bry": g["sibry"],
        "ip": g["current"], "btor_rcentr": g["bcentr"],
        "rmaxis": g["rmaxis"], "zmaxis": g["zmaxis"],
        "q0": g["qpsi"][0] if len(g["qpsi"]) else None,
        "q95": q_at(g, 0.95) if len(g["qpsi"]) else None,
        "rleft": g["rleft"], "rdim": g["rdim"],
        "zmid": g["zmid"], "zdim": g["zdim"],
        "nbbbs": g["nbbbs"],
    }


# --------------------------------------------------------------------------- #
# EFIT a-file (aeqdsk) — selected scalars
# --------------------------------------------------------------------------- #
# Field order transcribed from the port's own writer (weqdud6565.f, the
# `write (neqdsk,1040)` sequence) — NOT from any generic aeqdsk spec, since
# vintages differ.  Scalars come 4 per line; the CO2 blocks are sized by
# mco2v/mco2r from the `*time jflag lflag limloc mco2v mco2r qmflag ...`
# header line; the magnetics arrays are sized by the `nsilop magpri nfcoil
# nesum` int line that follows scalar group 21.
_AFILE_SCALARS_1 = [                       # groups 1-6 (4 each, in order)
    "tsaisq", "rcencm", "bcentr", "pasmat",
    "cpasma", "rout", "zout", "aout",
    "eout", "doutu", "doutl", "vout",
    "rcurrt", "zcurrt", "qsta", "betat",
    "betap", "ali", "oleft", "oright",
    "otop", "obott", "qpsib", "vertn",
]
_AFILE_SCALARS_2 = [                       # groups 11-21 (after the CO2 blocks)
    "shearb", "bpolav", "s1", "s2",
    "s3", "qout", "olefs", "orighs",
    "otops", "sibdry", "areao", "wplasm",
    "terror", "elongm", "qqmagx", "cdflux",
    "alpha", "rttt", "psiref", "xndnt",
    "rseps1", "zseps1", "rseps2", "zseps2",
    "sepexp", "obots", "btaxp", "btaxv",
    "aaq1", "aaq2", "aaq3", "seplim",
    "rmagx", "zmagx", "simagx", "taumhd",
    "betapd", "betatd", "wplasmd", "fluxx",
    "vloopt", "taudia", "qmerci", "tavem",
]
_AFILE_SCALARS_3 = [                       # groups after the magnetics arrays
    "pbinj", "rvsin", "zvsin", "rvsout",
    "zvsout", "vsurfa", "wpdot", "wbdot",
    "slantu", "slantl", "zuperts", "chipre",
    "cjor95", "pp95", "ssep", "yyy2",
    "xnnc", "cprof", "oring", "cjor0",
    "fexpan", "qqmin", "chigamt", "ssi01",
]


def read_afile(path: str | Path, *, arrays: bool = False) -> dict:
    """Parse the port's EFIT a-file (aeqdsk) into a dict of named scalars.

    Returns the fields listed in ``_AFILE_SCALARS_*`` (a-file chi2 ``tsaisq``,
    ``betap``/``ali``/``wplasm`` [J] for the W_dia<->W_mhd cross-check,
    convergence ``terror`` — the operational GUI's errorm<1e-3 accept gate —
    the computed diamagnetic flux ``cdflux``, diamagnetic-corrected
    ``betapd/wplasmd``, ``taumhd``/``taudia``, ``qqmin``, ...).  Best-effort:
    stops cleanly at whatever the file provides.
    """
    text = Path(path).read_text(errors="replace").split("\n")
    # locate the `*time ...` header line carrying mco2v/mco2r
    ih = next(i for i, ln in enumerate(text) if ln.startswith("*"))
    hdr = text[ih].split()
    mco2v, mco2r = int(hdr[4]), int(hdr[5])
    num = re.compile(r"[-+]?\d\.\d+E[-+]\d\d|[-+]?\d+\.\d+|\b\d+\b")

    toks: list[str] = []
    for ln in text[ih + 1:]:
        toks.extend(num.findall(ln.replace("E+", "e+").replace("E-", "e-")
                                  .replace("e+", "E+").replace("e-", "E-")))
    out: dict = {}
    i = 0

    def take(names):
        nonlocal i
        for nm in names:
            if i >= len(toks):
                return False
            out[nm] = float(toks[i])
            i += 1
        return True

    if not take(_AFILE_SCALARS_1):
        return out
    i += 2 * mco2v + 2 * mco2r              # rco2v/dco2v/rco2r/dco2r blocks
    if not take(_AFILE_SCALARS_2):
        return out
    # `nsilop magpri nfcoil nesum` int line, then the four arrays
    if i + 4 > len(toks):
        return out
    nsil, magp, nfc, nes = (int(float(toks[i + k])) for k in range(4))
    i += 4
    if arrays and i + nsil + magp + nfc <= len(toks):
        # computed (fitted-model) signals — csilop: flux loops, cmpr2:
        # magnetic probes, ccbrsp: F-coil currents.  The probe forward
        # predictions are the model side of per-channel self-calibration
        # (K-4): from a loops-only fit they are pure predictions.
        out["csilop"] = [float(t) for t in toks[i:i + nsil]]
        out["cmpr2"] = [float(t) for t in toks[i + nsil:i + nsil + magp]]
        out["ccbrsp"] = [float(t)
                         for t in toks[i + nsil + magp:i + nsil + magp + nfc]]
    i += nsil + magp + nfc + nes
    take(_AFILE_SCALARS_3)
    return out


# --------------------------------------------------------------------------- #
# T-C22 〔二〕 — what convention did this file arrive in?
# --------------------------------------------------------------------------- #
#: The four combinations a GEQDSK can plausibly be in, as the FACTOR that
#: makes the kernel's own equation close:
#:
#:     Δ*ψ = −factor · (μ0 R² pprime + ffprim)
#:
#: derived from ``equilibrium.rs``'s own statement — ``Δ*ψ = −gauge μ0 R j_φ``
#: with ``j_φ = R dp/dψ + FF'/(μ0 R)`` and ``dp/dψ = (dp/dψbar) gauge/span``:
#:
#:   * the table is ``dp/dψ``      → factor = ``gauge``
#:   * the table is ``dp/dψbar``   → factor = ``gauge² / span``
#:
#: with ``gauge`` 1 for ψ per radian and 2π for total flux [Wb].
#:
#: ★★They are TRIED, not assumed.  A GEQDSK carries no convention field, so
#: the only honest source is the file's own numbers: whichever factor makes
#: the equation close is the one the writer used.  That is T-C22 〔三〕's rule
#: applied to the reader — 以物理量符号的实测校验为准，不采信对方自述 — and
#: it is available at all only because the Δ* OPERATOR is on the ABI (v114).
def _candidates(span: float) -> dict:
    import math
    two_pi = 2.0 * math.pi
    out = {"dpsi, per radian": 1.0,
           "dpsi, total flux [Wb]": two_pi}
    if span and abs(span) > 0.0:
        out["dpsibar, per radian"] = 1.0 / span
        out["dpsibar, total flux [Wb]"] = two_pi * two_pi / span
    return out


#: ★★ONE spelling of the span the candidate factors are built on, because
#: TWO of them is a defect this file already had for one revision: the
#: measurement used the axis-to-zero span while the transform used
#: `sibry - simag`, so every `dpsibar` target was refused with "no candidate
#: convention" — the transform was right and the two sides simply were not
#: talking about the same number.  Same reason `transport.rs` factored
#: `faces()`: a checker that builds its own version of the discretisation is
#: checking something else.
def _candidate_span(g: dict) -> float:
    """The flux span ``psibar`` is normalised by: ``sibry - simag``.

    ★★It was ``-simag`` until 2026-08-26, and that was the shipped synthetic
    fixture's own arithmetic mistaken for the format's: that file puts its
    boundary at psi ~ 0, so the two numbers agree there and nothing said
    otherwise.  On a real EFIT reconstruction they differ by tens of percent
    (measured on EAST #78841: 0.1647 against 0.2325), and every ``dpsibar``
    candidate factor was built on the wrong one.

    A GEQDSK tabulates its profiles against normalised flux, so the span is
    the one the normalisation uses — the header's own two levels.
    """
    return float(g["sibry"]) - float(g["simag"])


def _seq(v):
    """``v``, or an empty list when it is absent — array-safe.

    ★Same reason as :func:`_first`: ``v or []`` asks a numpy array for its
    truth value, and「缺不缺」 is a question about presence, not about
    whether the numbers happen to be zero.
    """
    return [] if v is None else v


def _first(seq, default: float) -> float:
    """``seq[0]``, or ``default`` when there is no first element.

    ★Exists because ``seq or [default]`` raises on a numpy array: the
    ambiguous-truth-value error, from a line that only wanted「有没有第一个」.
    """
    return float(seq[0]) if seq is not None and len(seq) else float(default)


def measure_cocos(g: dict) -> dict:
    """What this file's own numbers say about the convention it is in.

    Returns the measured record — never the file's word for it, because a
    GEQDSK has no word for it:

    ``psi_axis``      ``"minimum"`` or ``"maximum"`` (which end ψ rises from)
    ``sign_ip`` / ``sign_b0`` / ``sign_q``      +1 / −1
    ``profile_gauge`` the winning entry of :func:`_candidates`, or ``None``
    ``residual``      how well it closed (relative), or ``None``
    ``runner_up``     the next best, so a caller can see the margin
    ``margin``        how many times better the winner is than the next
    ``mask``          which region the equation was tested on
    ``note``          why nothing was decided, when nothing was

    ★The gauge is decided by the kernel's own Grad-Shafranov equation, on
    this file's own field and profiles.  When no candidate closes, the answer
    is ``None`` **with the residuals reported** rather than the nearest one:
    a convention picked by "least bad" is a convention nobody measured.
    """
    import numpy as np

    from .. import kernel as _K

    rec = {
        "psi_axis": ("minimum" if g["sibry"] > g["simag"] else "maximum"),
        "sign_ip": 1 if g.get("current", 0.0) >= 0 else -1,
        "sign_b0": 1 if g.get("bcentr", 0.0) >= 0 else -1,
        #: ★`or` on a numpy array raises rather than falling through, and a
        #: caller that built `g` from arrays is a caller this function should
        #: still answer — so ask for the length, not the truthiness.
        "sign_q": 1 if _first(g.get("qpsi"), 1.0) >= 0 else -1,
        "profile_gauge": None, "residual": None, "runner_up": None,
        "margin": None, "mask": None, "note": None,
    }
    try:
        r, z, psi_read = grid(g)
    except Exception as e:                       # noqa: BLE001
        rec["note"] = f"the grid could not be built: {e}"
        return rec
    #: ★the transpose the module docstring names: the kernel is row-major
    #: `[r, z]` and this reader hands back the file's own `[z, r]`
    psi = np.ascontiguousarray(np.asarray(psi_read, float).T)
    pp_tab = np.asarray(_seq(g.get("pprime")), float)
    ffp_tab = np.asarray(_seq(g.get("ffprim")), float)
    if pp_tab.size < 2 or ffp_tab.size != pp_tab.size:
        rec["note"] = "no usable p' / FF' table to test the equation with"
        return rec

    sim, sib = float(g["simag"]), float(g["sibry"])
    span_file = sib - sim
    if not (abs(span_file) > 0.0):
        rec["note"] = "simag equals sibry: there is no flux span to test on"
        return rec
    #: the profiles are tabulated against NORMALISED flux, which is what the
    #: header's two levels define
    span_solve = _candidate_span(g)
    psibar = (psi - sim) / span_solve
    look = np.clip(psibar, 0.0, 1.0)
    xtab = np.linspace(0.0, 1.0, pp_tab.size)
    pp = np.interp(look, xtab, pp_tab)
    ffp = np.interp(look, xtab, ffp_tab)

    mu0 = 4e-7 * np.pi
    R = np.asarray(r, float)[:, None] * np.ones((1, len(z)))
    bracket = -(mu0 * R ** 2 * pp + ffp)
    try:
        lhs = _K.deltastar_apply(r, z, psi)
    except Exception as e:                       # noqa: BLE001
        rec["note"] = f"the Δ* operator is unavailable: {e}"
        return rec

    inner = np.zeros(psi.shape, bool)
    inner[2:-2, 2:-2] = True
    #: ★★INSIDE THE PLASMA BOUNDARY, not merely inside a psi_N band.  A band
    #: is what an analytic fixture needs and it is WRONG on a real diverted
    #: reconstruction: psi_N re-enters the same range in the private-flux
    #: region and the near SOL, where the current is zero while the profile
    #: lookup still hands back a p'/FF' — so a minority of points sit far off
    #: the equation and a max-norm is decided by them.  ★Measured on three
    #: EAST reconstructions (2026-08-26): the band gives 0.43 / 0.66 / 0.76
    #: while the MEDIAN over the same points is 0.006 / 0.008 / 0.23 — the
    #: bulk was closing all along and the mask was reporting the leak.
    #: Inside the file's own boundary polygon: 0.019 / 0.049 / 0.464.
    rb = np.asarray(_seq(g.get("rbbbs")), float)
    zb = np.asarray(_seq(g.get("zbbbs")), float)
    mask_kind = "psi_N band"
    if rb.size >= 5 and rb.size == zb.size:
        rg, zg = np.meshgrid(np.asarray(r, float), np.asarray(z, float),
                             indexing="ij")
        try:
            ins = np.asarray(_K.inside_polygon(rg.ravel(), zg.ravel(), rb, zb)
                             ).reshape(psi.shape).astype(bool)
            inner = inner & ins
            mask_kind = "inside the file's boundary polygon"
        except Exception:                        # noqa: BLE001
            pass
    rec["mask"] = mask_kind
    sel = inner & (psibar > 0.05) & (psibar < 0.95)
    if sel.sum() < 50:
        rec["note"] = ("too few interior points to test the equation on "
                       f"({mask_kind})")
        return rec

    scored = {}
    denom = float(np.max(np.abs(bracket[sel])))
    for name, factor in _candidates(span_solve).items():
        got = float(np.max(np.abs(lhs[sel] - factor * bracket[sel]))
                    / max(abs(factor) * denom, 1e-300))
        scored[name] = got
    order = sorted(scored, key=scored.get)
    best, second = order[0], (order[1] if len(order) > 1 else None)
    margin = (scored[second] / scored[best]) if second and scored[best] > 0 \
        else float("inf")
    rec["margin"] = margin
    #: ★★THE DECISION IS THE MARGIN, and the residual is REPORTED rather
    #: than thresholded.  They answer different questions, and an earlier
    #: version of this rule conflated them:
    #:
    #:   margin    "which convention is this file in?"  — scale-free, which
    #:             is what makes this a measurement.  The wrong candidates
    #:             are off by 2*pi or by the span, so they land near 1
    #:             WHATEVER the file's own quality is.
    #:   residual  "how good is this file?"  — a question this function is
    #:             not asked and cannot answer without knowing the file's
    #:             grid and provenance.
    #:
    #: ★What forced the separation: this repo's OWN forward solve, on a 65x65
    #: grid, writes g-files at residual 0.15-0.17 — an order worse than a
    #: 129x129 EFIT reconstruction (0.019 / 0.073) because the grid is
    #: coarser, and yet their convention is perfectly well determined
    #: (margin 5.8).  A ceiling tuned to reconstructions refused them for
    #: being coarse, which is not what「约定量不出来」means.
    #:
    #: ★Where 3.0 comes from, said plainly because a threshold moved after
    #: seeing data has to be: the measured margins are 1.97 for the one file
    #: that must be refused (EAST #63982, whose best candidate beats the next
    #: by a factor of two — a coin toss, not a measurement) and
    #: {5.8, 11.5, 44.7, 10143} for the four that must be accepted.  The cut
    #: can sit anywhere in (1.97, 5.8); 3.0 is near the geometric middle
    #: (sqrt(1.97*5.8) = 3.4), so neither side is grazing it.
    #:
    #: ★1.0 is NOT fitted to anything: it is where the residual equals the
    #: term it is a residual of, and past that nothing has closed in any
    #: sense worth the word.
    if scored[best] < 1.0 and margin >= 3.0:
        rec["profile_gauge"] = best
        rec["residual"] = scored[best]
        rec["runner_up"] = (second, scored[second]) if second else None
    else:
        why = ("its residual is as large as the term it is a residual of, so "
               "nothing closed" if scored[best] >= 1.0 else
               f"it beats the runner-up by only {margin:.2f}x, and a margin "
               "under 3 is a coin toss rather than a measurement")
        rec["note"] = (
            "no candidate convention makes this file satisfy the "
            f"Grad-Shafranov equation — the closest is {best!r} at "
            f"{scored[best]:.3e} and {why}.  Reading it anyway would be "
            "assuming a convention nobody measured; the file, its profiles "
            "or its ψ orientation disagree with each other.")
        rec["runner_up"] = (best, scored[best])
    return rec


def require_convention(g: dict, *, profile_gauge: str = "dpsi, per radian",
                       ) -> dict:
    """The measured record, or a refusal naming what was measured instead.

    ★T-C22 〔二〕's rule: a file whose convention does not match what the
    caller needs is TRANSFORMED explicitly or REFUSED — never read as-is.
    This is the refusal half, and it stays a refusal: it does no transform
    of its own, because which factor a mismatch needs depends on the
    quantity the caller is about to use (ψ alone scales one way, a
    ψ-derivative table the other) and guessing that is the failure being
    prevented.

    ★The transform half is :func:`to_convention` (T-C22 〔三〕), which moves
    every field by a DECLARED rule and then re-measures its own output.  A
    caller that wants the conversion asks for it by name; this function is
    for the caller that wants to be stopped.
    """
    rec = measure_cocos(g)
    if rec["profile_gauge"] is None:
        raise ValueError(
            "this g-file's convention could not be measured, so it will not "
            f"be read as though it were {profile_gauge!r}: {rec['note']}")
    if rec["profile_gauge"] != profile_gauge:
        raise ValueError(
            f"this g-file is in {rec['profile_gauge']!r} (measured: the "
            f"Grad-Shafranov equation closes to {rec['residual']:.2e} there) "
            f"and the caller asked for {profile_gauge!r}.  Convert it "
            "explicitly — reading it as-is is the silent factor T-C22 exists "
            "to stop.")
    return rec


# --------------------------------------------------------------------------- #
# T-C22 〔三〕 — the EXPLICIT transform, for exchange with another tool
# --------------------------------------------------------------------------- #
#: How each GEQDSK field responds to a change of convention.  ★★DECLARED,
#: one row per field, with the reason — not derived from a rule about
#: "flux-like" names, because the whole failure this layer exists to stop is
#: a plausible rule applied to a field it does not fit.
#:
#: ``"psi"``        scales with the gauge (it IS the flux)
#: ``"table"``      a p'/FF' table: scales by the factor the equation needs
#: ``"invariant"``  the same number in every convention, and WHY
#: A field absent from this table is REFUSED rather than passed through: a
#: reader that hands us a g-file with a key nobody classified is handing us a
#: quantity nobody thought about.
_RESPONSE = {
    "psirz": ("psi", "the poloidal flux map itself"),
    "simag": ("psi", "the flux at the axis"),
    "sibry": ("psi", "the flux at the boundary"),
    "pprime": ("table", "dp/dpsi (or dp/dpsibar): the equation fixes it"),
    "ffprim": ("table", "F dF/dpsi (or per psibar): the same slot"),
    #: ★q is the SAFETY FACTOR and a GEQDSK stores the physical one in every
    #: convention — it is not `dPhi/dpsi` in the file's own gauge.  This is
    #: exactly the row a "flux-like things scale" rule gets wrong, which is
    #: why every row here carries its reason.
    "qpsi": ("invariant", "the physical safety factor, dimensionless"),
    "pres": ("invariant", "a pressure is a pressure"),
    "fpol": ("invariant", "F = R B_tor, a field quantity"),
    "current": ("invariant", "the plasma current in ampere"),
    "bcentr": ("invariant", "the vacuum field at rcentr, in tesla"),
    "rdim": ("invariant", "box geometry, in metres"),
    "zdim": ("invariant", "box geometry, in metres"),
    "rcentr": ("invariant", "box geometry, in metres"),
    "rleft": ("invariant", "box geometry, in metres"),
    "zmid": ("invariant", "box geometry, in metres"),
    "rmaxis": ("invariant", "the magnetic axis, in metres"),
    "zmaxis": ("invariant", "the magnetic axis, in metres"),
    "rbbbs": ("invariant", "the boundary polygon, in metres"),
    "zbbbs": ("invariant", "the boundary polygon, in metres"),
    "rlim": ("invariant", "the limiter polygon, in metres"),
    "zlim": ("invariant", "the limiter polygon, in metres"),
    "nw": ("invariant", "a count"),
    "nh": ("invariant", "a count"),
    "nbbbs": ("invariant", "a count"),
    "limitr": ("invariant", "a count"),
    "header": ("invariant", "the file's own first line"),
    #: ★this function's own annotations, classified so that converting a
    #: converted file is an ordinary call and not a refusal
    "fylite:converted_from": ("invariant", "provenance: what it arrived as"),
    "fylite:converted_residual": ("invariant",
                                  "provenance: what the copy measured"),
}

#: every convention this layer knows, in one place
CONVENTIONS = ("dpsi, per radian", "dpsi, total flux [Wb]",
               "dpsibar, per radian", "dpsibar, total flux [Wb]")


def _gauge_of(name: str) -> float:
    """The factor psi is expressed in: 1 per radian, 2*pi for total flux."""
    import math
    if name not in CONVENTIONS:
        raise ValueError(f"unknown convention {name!r}; the declared set is "
                         f"{list(CONVENTIONS)}")
    return 2.0 * math.pi if "total flux" in name else 1.0


def to_convention(g: dict, target: str, *, tol_ratio: float = 10.0) -> dict:
    """A copy of ``g`` expressed in ``target``, or a refusal.

    ★★T-C22 〔三〕: 对外交换走显式变换层，**以物理量符号的实测校验为准，不采
    信对方自述**.  Two halves, and both matter:

    *The source is MEASURED* (:func:`measure_cocos`), never taken from the
    caller or from anything the counterpart says about its own file.  A
    ``target`` that already equals the measured source returns an unchanged
    copy — the identity is a real answer here, not a special case.

    *The result is RE-MEASURED*, and this function raises if the copy does
    not come back as ``target`` with a Grad-Shafranov residual within
    ``tol_ratio`` of the source's.  That is the difference between a
    transform and an assertion: a factor applied to the wrong field would
    still produce a file, and only re-measuring says whether that file still
    satisfies the equation.

    Every field is moved according to :data:`_RESPONSE`, and a field this
    table does not classify is refused rather than copied — an unclassified
    quantity is one nobody decided about.
    """
    import numpy as np

    src = measure_cocos(g)
    if src["profile_gauge"] is None:
        raise ValueError(
            "this g-file's convention could not be measured, so it cannot be "
            f"converted to {target!r}: {src['note']}")
    if target not in CONVENTIONS:
        raise ValueError(f"unknown target convention {target!r}; the "
                         f"declared set is {list(CONVENTIONS)}")
    unclassified = sorted(k for k in g if k not in _RESPONSE)
    if unclassified:
        raise ValueError(
            f"these g-file fields are not classified in _RESPONSE: "
            f"{unclassified}.  A quantity nobody classified is a quantity "
            "nobody decided about — add a row with its reason rather than "
            "letting it through unchanged")

    if target == src["profile_gauge"]:
        return {k: (list(v) if isinstance(v, list) else v)
                for k, v in g.items()}

    #: ★the SAME span the measurement's candidate factors are built on —
    #: not `sibry - simag`, which is a different number on this fixture and
    #: made every `dpsibar` target refuse itself
    span_old = _candidate_span(g)
    k = _gauge_of(target) / _gauge_of(src["profile_gauge"])
    span_new = k * span_old
    f_src = _candidates(span_old)[src["profile_gauge"]]
    f_tgt = _candidates(span_new)[target]
    #: ★ONE scalar for both tables, and it is not a guess: the equation
    #: `Delta* psi = -factor (mu0 R^2 pprime + ffprim)` holds on both sides,
    #: psi carries k, so the tables must carry `k * f_src / f_tgt`.  What
    #: makes it trustworthy is the re-measurement below, not this line.
    s = k * f_src / f_tgt

    out = {}
    for key, val in g.items():
        kind = _RESPONSE[key][0]
        if kind == "invariant":
            out[key] = list(val) if isinstance(val, list) else val
        elif kind == "psi":
            out[key] = ([float(v) * k for v in val] if isinstance(val, list)
                        else float(val) * k)
        else:                                    # "table"
            out[key] = [float(v) * s for v in val]

    got = measure_cocos(out)
    if got["profile_gauge"] != target:
        raise ValueError(
            f"the transform to {target!r} did not produce a file in that "
            f"convention — it measures as {got['profile_gauge']!r} "
            f"({got['note'] or ''}).  The declaration in _RESPONSE and the "
            "equation disagree; do not ship this file")
    if got["residual"] > tol_ratio * max(src["residual"], 1e-300):
        raise ValueError(
            f"the transform to {target!r} measures as {target!r} but the "
            f"Grad-Shafranov residual grew from {src['residual']:.3e} to "
            f"{got['residual']:.3e} — more than the {tol_ratio}x this "
            "function allows.  Something moved that should not have")
    out["fylite:converted_from"] = src["profile_gauge"]
    out["fylite:converted_residual"] = got["residual"]
    return out
