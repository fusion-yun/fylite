"""A-7 — every declared scenario entry, on both kernel builds, compared.

★★"单核双宿主" is what this repository claims about itself, and this is the
claim's end-to-end form: every entry the kernel DECLARES is run on native
(`libfylite_kernel.so`) and on wasm (the browser's build, driven through the same
binding a page loads), and what must be identical is identical.

What makes it a claim rather than a comparison is that the split is
DECLARED.  `ENTRY_OUT_KIND` in `rust/fylite/src/fyo.rs` says which outputs
are counts and flags — integers by construction, where two hosts disagreeing
means they took different paths — and those are HASHED.  A digest has no
tolerance to argue about, which is exactly right for「走了同样的路」.  The
float rows get the measured cross-host band; the noise rows get「both small」,
because comparing two hosts' arithmetic noise relatively is a category error.

Run: needs `node` and the built wasm; skips by name without either.
"""
from __future__ import annotations

import shutil

import numpy as np
import pytest

from fylite import kernel as K
from fylite.engine import crosshost as X

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not X.WASM.exists(),
    reason="A-7 needs node and app/assets/fylite_rs.wasm")


def _zerod():
    nt, nr = 7, 5
    return dict(
        dims={"nt": nt, "nr": nr},
        params=dict(ti_over_te=0.9, peaking_n=1.1, peaking_t=1.7,
                    edge_frac=0.1, r0=1.85, a=0.45, kappa=1.8, zeff=1.6,
                    li=0.9, dt_fraction=0.5),
        inputs=dict(t=np.arange(nt) * 0.5, ip=np.full(nt, 1.0e6),
                    ne0=np.full(nt, 6e19), te0=np.full(nt, 8e3),
                    p_inj=np.full(nt, 4e6), rho=np.linspace(0.0, 1.0, nr)))


def _transport():
    n = 21
    rho = np.linspace(0.0, 1.0, n)
    return dict(
        dims={"n": n},
        params=dict(model=0, p0=1.0, p1=0.0, p2=0.0, dt=float("inf"),
                    theta=1.0, edge_value=100.0, relax=1.0, relax_coeff=1.0,
                    d_pc=0.0, tol=1e-12, steps=8),
        inputs=dict(rho=rho, y_init=np.full(n, 300.0),
                    vprime=2.0 * rho + 1e-3, source=np.full(n, 50.0),
                    velocity=np.zeros(n)))


def _profit():
    n, m = 40, 4
    x = np.linspace(0.0, 1.0, n)
    #: a smooth truth plus a FIXED perturbation — no RNG, because a gate
    #: whose input differs between the two calls compares two problems
    y = 3.0 - 2.0 * x ** 2 + 0.01 * np.cos(17.0 * x)
    return dict(dims={"n": n, "m": m},
                params=dict(reserved=0.0),
                inputs=dict(x=x, y=y, sigma=np.full(n, 0.01)))


def _vstab():
    n = 6
    #: a symmetric, diagonally dominant inductance-like matrix and positive
    #: resistances — a plant the entry can actually reduce
    #:
    #: ★★the OLD parameters (ip 4e5, k 1.4) put the root at gamma = 8e-15
    #: — numerically ZERO (a growth time of megayears), where the relative
    #: band compares two hosts' bisection leftovers instead of a number.
    #: It passed for months because the two committed builds happened to
    #: leave bit-identical residue; the first recompile (ABI v116) moved a
    #: last ulp and the「difference」read 4.6e-9 — of nothing.  The call
    #: now pins the root near gamma ≈ 2e2 s⁻¹, where gamma·M and R are the
    #: SAME order, so the mass and resistive halves of the dispersion are
    #: both load-bearing and the band asks about a real number.
    i = np.arange(n, dtype=float)
    m = 1e-6 * (np.eye(n) * 12.0 + 1.0 / (1.0 + np.abs(i[:, None] - i[None, :])))
    return dict(dims={"n": n},
                params=dict(ip=1.0e3, k=1.5e11),
                inputs=dict(m=m.ravel(), r=np.full(n, 1e-3),
                            g=np.linspace(0.2, 1.0, n)))


def _evolve_heat():
    from fylite import _deck_names as D
    n, nt = 25, 12
    rho = np.linspace(0.0, 2.0, n)
    rb = rho / 2.0
    return dict(
        dims={"n": n, "nt": nt},
        params={"b0": 5.3, "chi0": 0.4, "chi_ratio": 1.0, "edge_te": 300,
                "edge_ti": 300, "dt": 0.002, "dt_target": 0.02,
                "dt_min": 1e-5, "dt_max": 0.02, "d_pc": 0, "p_e": 4e6,
                "p_i": 4e6, "dep_centre": 0, "dep_width": 0.3, "brem": 1,
                "bulk_id": K.adas_id("D"), "imp_id": K.adas_id("C"),
                "imp_conc": 0.01, "imp_z": D.ADAS_Z["C"], "alpha": 1,
                "dt_fraction": 0.5, "zeff": 1.5, "pedestal": 1, "ip": 15e6,
                "a": 2.0, "r0": 6.2, "kappa": 1.86, "delta": 0.48},
        inputs={"rho": rho, "vprime": 4 * np.pi ** 2 * 6.2 * rho,
                "gm3": np.ones(n), "te_init": 300 + 2700 * (1 - rb ** 2),
                "ti_init": 300 + 2200 * (1 - rb ** 2),
                "ne": 1e20 * (0.5 + 0.5 * (1 - rb ** 2))})


def _evolve_heat_current():
    """``evolve_heat`` with the CURRENT channel on (S-2c 批二).

    ★A separate call rather than a change to `_evolve_heat`: the two are
    different branches of the entry — `ch_current` gates the metric it
    reads, the closure rows it asks for, the Ohmic term it folds back into
    `q_e` and three of its outputs — and a cross-host claim about one of
    them says nothing about the other.  The pair is asserted to differ
    below, so neither can quietly become the other.
    """
    call = _evolve_heat()
    n = call["dims"]["n"]
    rho = call["inputs"]["rho"]
    a, r0, b0 = 2.0, 6.2, 5.3
    x = rho / a
    q_init = 1.0 + (3.5 - 1.0) * x ** 2
    gm2 = np.zeros(n)
    for i in range(1, n):
        shear = x[i] * (2.0 * (3.5 - 1.0) * x[i]) / q_init[i]
        g = K.geo_surface(rmin_over_a=rho[i], rmaj_over_a=r0, q=q_init[i],
                          shear=shear, kappa=1.86, s_kappa=0.0, delta=0.48,
                          s_delta=0.0, ntheta=201)
        gm2[i] = g["fsa_grad_r2_over_r2"]
    gm2[0] = gm2[1]
    fpol = np.full(n, r0 * abs(b0))
    #: seeded by inverting THE ENTRY's own q relation — see
    #: `test_evolve_entry.py::test_the_current_channel_is_seeded_from_...`
    dpsi = np.zeros(n)
    dpsi[1:] = 2.0 * np.pi * abs(b0) * rho[1:] / q_init[1:]
    psi_init = np.zeros(n)
    for i in range(1, n):
        psi_init[i] = psi_init[i - 1] \
            + 0.5 * (dpsi[i] + dpsi[i - 1]) * (rho[i] - rho[i - 1])
    call["params"].update({"ch_current": 1.0, "ohmic": 1.0,
                           "bootstrap": 1.0, "v_loop": 0.0})
    call["inputs"].update({"gm2": gm2, "fpol": fpol, "psi_init": psi_init,
                           "rmin": rho.copy(), "rmaj": np.full(n, r0),
                           "q_init": q_init})
    #: ★★SIX steps, and the number was re-measured on 2026-08-30 rather than
    #: inherited.  This march amplifies (that is its own gate, below), so the
    #: step count decides whether the 1e-12 band is answering「两个构建算的是
    #: 同一件事」or「一个非线性行进放大了多少 ulp」— only the first is a
    #: cross-host claim.  Measured `worst` on the current variant:
    #:
    #:   nt = 1, 2, 3   →  3.0e-16, 2.2e-16, 2.1e-16   (ulp)
    #:   nt = 6         →  2.2e-15
    #:   nt = 12, 24    →  1.745e-12 both (it grows, then SATURATES)
    #:
    #: ★It used to sit at twelve, where the figure was 5.7e-16, and the
    #: Redl `L34 = L31` fix (2026-08-30) moved the crossing one doubling
    #: earlier — the corrected bootstrap current makes the current-diffusion
    #: march stiffer.  ★★That is amplification and NOT a new host-dependent
    #: operation, which is a distinction that was measured, not assumed:
    #: `j_bs` is bit-identical across the two hosts through three steps and
    #: 2.0e-16 at six.  A fix that introduced a host-dependent op would show
    #: up in `j_bs` at step ONE.
    call["dims"]["nt"] = 6
    return call


CALLS = {"zerod": _zerod, "transport": _transport, "profit": _profit,
         "vstab": _vstab, "evolve_heat": _evolve_heat}

#: Second calls into an entry whose BRANCHES a single call cannot cover.
#: Keyed by a label; the value is `(entry, builder)`.
def _evolve_heat_sawtooth():
    """``evolve_heat`` with the current channel AND a sawtoothing core.

    ★A third call because the crash is a third branch: it replaces te / ti /
    ni / ne / psi / q between two steps, and none of that runs on either
    call above.  The core is made hollow (``q(0) = 0.8``) the way a traced
    geometry tier will hand one in — the prescribed-Miller assembly cannot
    make one, in EITHER host (`worker.js`: `var q0 = 1.0`).
    """
    call = _evolve_heat_current()
    n = call["dims"]["n"]
    rho = call["inputs"]["rho"]
    a, r0, b0 = 2.0, 6.2, 5.3
    x = rho / a
    q_init = 0.80 + (3.5 - 0.80) * x ** 2
    gm2 = np.zeros(n)
    for i in range(1, n):
        shear = x[i] * (2.0 * (3.5 - 0.80) * x[i]) / q_init[i]
        g = K.geo_surface(rmin_over_a=rho[i], rmaj_over_a=r0, q=q_init[i],
                          shear=shear, kappa=1.86, s_kappa=0.0, delta=0.48,
                          s_delta=0.0, ntheta=201)
        gm2[i] = g["fsa_grad_r2_over_r2"]
    gm2[0] = gm2[1]
    dpsi = np.zeros(n)
    dpsi[1:] = 2.0 * np.pi * abs(b0) * rho[1:] / q_init[1:]
    psi_init = np.zeros(n)
    for i in range(1, n):
        psi_init[i] = psi_init[i - 1] \
            + 0.5 * (dpsi[i] + dpsi[i - 1]) * (rho[i] - rho[i - 1])
    call["params"].update({"sawtooth": 1.0, "saw_mix": 1.2})
    call["inputs"].update({"gm2": gm2, "psi_init": psi_init,
                           "q_init": q_init})
    #: ★SIX steps, for the same measured reason the call this one is built
    #: from takes six — the band is a statement about one evaluation, so the
    #: gate that uses it asks a question the band can answer, and the
    #: divergence gets its own gate instead of a widened tolerance.  Restated
    #: here rather than inherited silently: this variant's own figures are in
    #: `test_the_sawtooth_variant_agrees_and_does_not_amplify`, and they are
    #: not the current channel's.
    call["dims"]["nt"] = 6
    return call


VARIANTS = {"evolve_heat/current": ("evolve_heat", _evolve_heat_current),
            "evolve_heat/sawtooth": ("evolve_heat", _evolve_heat_sawtooth)}


def test_every_declared_entry_has_a_call_here():
    """★★The list is taken FROM THE KERNEL, so an entry added tomorrow makes
    this gate red until somebody says how to call it.  A cross-host claim
    that quietly covered four of five entries would be the silent narrowing
    this repository refuses — and「五分之四」is indistinguishable from
    「全部」in a passing test."""
    from fylite import _fyo_interface as FI
    assert set(FI.ENTRIES) == set(CALLS), {
        "declared, not called here": sorted(set(FI.ENTRIES) - set(CALLS)),
        "called here, not declared": sorted(set(CALLS) - set(FI.ENTRIES))}


@pytest.mark.parametrize("entry", sorted(CALLS))
def test_both_hosts_agree_on_this_entry(entry):
    """★The whole of A-7 for one entry: same declared call, both builds,
    and the counts and flags must HASH the same."""
    call = CALLS[entry]()
    native = X.run_native(entry, **call)
    wasm = X.run_wasm(entry, **call)
    rec = X.compare(entry, native, wasm)
    assert rec["verdict"] == "same", rec
    #: ★and the record names the host, so the report explains itself rather
    #: than leaving a reader to assume which side produced which figure
    assert rec["environment"]["native"]["host"] == "native"
    assert rec["environment"]["wasm"]["host"] == "wasm"


@pytest.mark.parametrize("label", sorted(VARIANTS))
def test_both_hosts_agree_on_this_variant(label):
    """★The same claim as above, for a branch the entry's default call does
    not reach.  `evolve_heat/current` is the whole of S-2c 批二 crossing the
    ABI twice: two builds, one declaration, and psi / j_bs / p_ohm / q must
    agree to the same band as the heat channel's own outputs."""
    entry, build = VARIANTS[label]
    call = build()
    native = X.run_native(entry, **call)
    wasm = X.run_wasm(entry, **call)
    rec = X.compare(entry, native, wasm)
    assert rec["verdict"] == "same", rec


def test_the_current_variant_actually_takes_the_other_branch():
    """★★A variant that produced the base call's answer would make the gate
    above a duplicate wearing a second name.  The current channel's four
    outputs are zeros on the base call — that is what「channel off」means —
    and must not be on the variant."""
    base = X.run_native("evolve_heat", **_evolve_heat())
    var = X.run_native("evolve_heat", **_evolve_heat_current())
    for key in ("psi", "j_bs", "q", "p_ohm"):
        b = np.atleast_1d(np.asarray(base[key], float))
        v = np.atleast_1d(np.asarray(var[key], float))
        assert not np.any(b), f"{key} is non-zero with the channel off: {b}"
        assert np.any(v), f"{key} is all zeros with the channel on: {v}"
    #: and the current channel moves the HEAT channel too (the Ohmic term),
    #: so the two calls are not the same march with extra columns bolted on
    assert not np.allclose(np.asarray(base["te"]), np.asarray(var["te"]))


def test_the_two_hosts_diverge_by_amplification_and_the_rate_is_pinned():
    """★★The divergence is an amplified ulp, and it is gated where it is
    actually visible.

    The two builds are not bit-identical — different float codegen, fma
    contraction and libm — so every quantity starts off differing by an ulp,
    and a nonlinear march AMPLIFIES that.  Measured on the CURRENT-channel
    variant (re-measured 2026-08-30), `worst`:

    ``2.2e-15`` at 6 steps, ``1.745e-12`` at 12 and again at 24 (in
    `p_ohm`) — it grows by ~800× and then SATURATES, because the march
    reaches a steady state and stops feeding the difference.

    ★The 2026-08-28 figures were ``5.7e-16`` at 6 and 12 and ``6.2e-13`` at
    24.  The Redl `L34 = L31` fix moved the crossing one doubling earlier;
    see `_evolve_heat_current`, where the evidence that this is
    amplification and not a new host-dependent operation is written down.

    ★★It is gated on that variant and no longer on the sawtooth one, and
    the reason is a defect this repository has written down rather than a
    convenience: the sawtooth has **no crash period** (TODO T-C28), so on a
    core with a q = 1 surface it crashes on EVERY step, and a crash
    re-flattens the state.  There is then nothing left between crashes for
    the march to amplify — measured: the sawtooth variant sits at a FLAT
    3.15e-13 at 6, 12 and 24 steps.  Gating "it grows" there would be gating
    a growth that this model cannot produce.

    ★★The point of writing it down as a GATE rather than as a widened band:
    a band chosen to swallow 6.2e-13 would agree with any future
    disagreement up to that size, including a real one.  What is actually
    checkable is the SHAPE of the divergence — it starts at machine epsilon
    and grows — and that the DISCRETE outputs never part, because a step
    count or a crash count differing is a disagreement no float noise can
    excuse.
    """
    import numpy as np

    short = _evolve_heat_current()                      # nt = 6
    long_ = _evolve_heat_current()
    long_["dims"] = dict(long_["dims"], nt=24)
    worst = {}
    for label, call in (("short", short), ("long", long_)):
        native = X.run_native("evolve_heat", **call)
        wasm = X.run_wasm("evolve_heat", **call)
        rec = X.compare("evolve_heat", native, wasm)
        worst[label] = rec["worst"]
        #: the discrete digest is the part that may NOT drift, at any length
        assert rec["discrete"]["native"] == rec["discrete"]["wasm"], (
            f"{label}: the counts/flags parted — float noise does not "
            "explain a different number of steps or crashes")
    assert worst["short"] < 1e-14, (
        f"the two hosts already differ by {worst['short']:.2e} after six "
        "steps of an uncrashed march; that is not amplification, that is a "
        "disagreement about the step")
    assert worst["long"] > worst["short"] * 100, (
        f"short {worst['short']:.2e} vs long {worst['long']:.2e}: the "
        "divergence did not grow, so the explanation written here (a march "
        "amplifying an ulp) is not what is happening — re-diagnose before "
        "trusting either gate")


def test_the_sawtooth_variant_agrees_and_does_not_amplify():
    """★★The sawtooth path's own cross-host claim, stated as what it IS.

    It does not run away (see above: the crash re-flattens the state every
    step because the model has no period), so what is checkable here is
    that the two hosts AGREE at every length and that the discrete digest
    never parts.  Re-measured 2026-08-30: ``3.09e-13`` at 6 steps and
    ``6.49e-13`` at 12 and again at 24 — one step up, then it SATURATES,
    and the saturation is what is gated below.  ★That is a sharper claim
    than the「flat ``3.15e-13``」recorded on 2026-08-28 and it is why the
    Redl `L34 = L31` fix (which doubled the 12-step figure) does not
    overturn the physics argument: the current-channel variant grows ~800×
    over the same interval, this one grows 2×.

    ★★The worst key is a crash-geometry RADIUS — the two hosts
    interpolating the q = 1 crossing an ulp apart, not a physical quantity
    drifting.  It is gated as「a radius」and no longer as the single name
    ``saw_mixed``, because ``saw_mixed`` is ``saw_mix × saw_r1`` EXACTLY
    (measured: the ratio is 1.2 at every step), so the two rows carry the
    same relative divergence to three digits and which of them wins the
    `max` is decided by the last ulp of that scaling.  Pinning the winner
    was pinning a coin flip, and the fix moved the coin.

    ★★When the crash period lands (T-C28) this fixture will stop crashing
    every step and WILL begin to amplify — at which point this gate fails
    and must be re-measured rather than relaxed.  That is deliberate: it
    ties the gate to the defect it is standing in for.
    """
    import numpy as np

    worst = {}
    for nt in (6, 12, 24):
        call = _evolve_heat_sawtooth()
        call["dims"] = dict(call["dims"], nt=nt)
        native = X.run_native("evolve_heat", **call)
        wasm = X.run_wasm("evolve_heat", **call)
        rec = X.compare("evolve_heat", native, wasm)
        worst[nt] = rec["worst"]
        assert rec["discrete"]["native"] == rec["discrete"]["wasm"], (
            f"nt={nt}: the counts/flags parted — float noise does not "
            "explain a different number of crashes")
        assert float(native["saw_count"]) == float(wasm["saw_count"]) >= 1
        assert rec["worst"] < 1e-12, (
            f"nt={nt}: the hosts differ by {rec['worst']:.2e} in "
            f"{rec['worst_key']}, beyond the cross-host band")
        assert rec["worst_key"] in ("saw_mixed", "saw_r1"), (
            f"nt={nt}: the worst disagreement moved to {rec['worst_key']!r} "
            "— it used to be a crash radius, and a physical quantity "
            "taking its place is a different claim")
        #: ★and「a radius」is only the right reading while the two radii are
        #: the same row scaled, so the tie is CHECKED rather than asserted
        #: from the docstring: if they ever came apart, `worst_key` would
        #: start carrying information again and this gate would be wrong to
        #: accept either name.
        r1 = np.asarray(native["saw_r1"], float)
        mixed = np.asarray(native["saw_mixed"], float)
        hit = r1 > 0.0
        assert np.allclose(mixed[hit], call["params"]["saw_mix"] * r1[hit],
                           rtol=0, atol=0), (
            "saw_mixed is no longer saw_mix × saw_r1, so the two rows no "
            "longer carry the same relative divergence and accepting "
            "either as `worst_key` has stopped being justified")
    #: ★the saturation, which is the checkable form of「不放大」: the crash
    #: re-flattens the state, so past step 12 the march adds nothing
    assert worst[24] == pytest.approx(worst[12], rel=1e-3), (
        f"12 steps {worst[12]:.3e} vs 24 steps {worst[24]:.3e}: the "
        "divergence did not saturate, so the crash is no longer "
        "re-flattening the state — re-diagnose (T-C28?) before relaxing")


def test_the_sawtooth_variant_actually_crashes():
    """★Same rule for the third branch: a variant that never triggered would
    make its cross-host gate a duplicate of the current channel's."""
    saw = X.run_native("evolve_heat", **_evolve_heat_sawtooth())
    cur = X.run_native("evolve_heat", **_evolve_heat_current())
    assert float(saw["saw_count"]) >= 1, "the hollow core did not sawtooth"
    assert float(cur["saw_count"]) == 0, (
        "the current-channel call sawtoothed; then the two variants are not "
        "testing different branches")
    assert np.any(np.asarray(saw["saw_mixed"]) > 0.0)


@pytest.mark.parametrize("entry", sorted(CALLS))
def test_the_discrete_digest_is_load_bearing(entry):
    """★★A digest that ignored the thing it is supposed to catch would pass
    every assertion above.  One count or flag is bumped by one on the wasm
    side and the digests must part; when an entry declares no exact output
    the digest says so IN WORDS rather than hashing nothing into a value
    that looks like agreement."""
    call = CALLS[entry]()
    native = X.run_native(entry, **call)
    kinds = X.out_kinds(entry)
    exact = sorted(k for k, v in kinds.items() if v in ("count", "flag"))
    if not exact:
        assert X.discrete_digest(entry, native) == "sha256:none-declared"
        pytest.skip(f"{entry} declares no count/flag output")
    bent = dict(native)
    key = exact[0]
    bent[key] = np.atleast_1d(np.asarray(native[key], float)) + 1.0
    assert X.discrete_digest(entry, bent) != X.discrete_digest(entry, native)


@pytest.mark.parametrize("entry", sorted(CALLS))
def test_a_row_declared_exact_really_is_an_integer(entry):
    """★The declaration is a claim about the physics and can be wrong.  A
    key declared `count` that comes back at 3.5 means the table is lying,
    and hashing it would launder the lie into an agreement."""
    call = CALLS[entry]()
    out = X.run_native(entry, **call)
    for key, kind in sorted(X.out_kinds(entry).items()):
        if kind not in ("count", "flag"):
            continue
        v = np.atleast_1d(np.asarray(out[key], float))
        assert np.all(v == np.floor(v)), (entry, key, v[:4])
        if kind == "flag":
            assert set(np.unique(v)) <= {0.0, 1.0}, (entry, key, np.unique(v))


def test_a_ledger_node_that_is_not_an_entry_is_refused_by_name():
    """★A tool that is host assembly around many kernel calls has no wasm
    counterpart outside a browser page.  Reporting it as「一致」because
    nobody ran it twice is the failure this refusal exists to prevent."""
    doc = {"fylite:projection": {"dag": {"nodes": [
        {"id": "n1", "tool": "fylite_evolve"},
        {"id": "n2", "tool": "fylite_discharge"},
        {"id": "n3", "tool": "fylite_reconstruct"}]}}}
    got = X.for_ledger(doc)
    assert [r["id"] for r in got["runnable"]] == ["n1"]
    #: the tool is `evolve`; the entry at its core is `evolve_heat`, and the
    #: report names both so a reader can see the tool is not the entry
    assert got["runnable"][0] == {"id": "n1", "entry": "evolve_heat",
                                  "tool": "evolve"}
    assert sorted(got["refused"]) == ["n2", "n3"]
    assert "no counterpart" in got["refused"]["n2"]


# --------------------------------------------------------------------------- #
# the ledger half — A-7's own words are 同一账本
# --------------------------------------------------------------------------- #
def test_a_real_recorded_ledger_is_sorted_into_runnable_and_refused(
        tmp_path, monkeypatch):
    """★★Against a ledger this repository actually WROTE, not a dict shaped
    like one by hand.  A hand-built document agrees with whatever the reader
    expects; a recorded one carries the node shape the recorder really uses —
    and it caught a defect here: `attrs.tool` is where `ledger.record` puts
    the tool, while this driver was reading `node.tool`, so every node
    refused itself with a message about host assembly.  That is a refusal
    for the wrong reason, and from outside it reads like an answer.
    """
    from fylite.engine import ledger
    from fylite.engine import cases

    monkeypatch.setenv("FYLITE_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("FYLITE_SESSION", "a7")
    cases.run("evolve-default")
    cases.run("transport-iter-15ma")
    doc = ledger.load(tmp_path / "a7")
    got = X.for_ledger(doc)

    #: `evolve` declares `evolve_heat` at its core, so it can be cross-checked
    assert [(r["tool"], r["entry"]) for r in got["runnable"]] \
        == [("evolve", "evolve_heat")]
    #: ★and `transport` is REFUSED even though a declared entry bears that
    #: exact name — because this tool reaches the kernel through the flat
    #: exports and never calls it.  A name is not a declaration, and a
    #: cross-host report about a path the tool does not take would be a
    #: wrong answer to the right question.
    assert len(got["refused"]) == 1
    assert "no `kernel_entry`" in next(iter(got["refused"].values()))


def test_the_ledger_sorting_covers_every_node(tmp_path, monkeypatch):
    """★Every node lands in exactly one bin.  A node that fell out of both
    would be a run nobody said anything about, which is the shape of every
    silent gap this repository has had to dig out."""
    from fylite.engine import ledger
    from fylite.engine import cases

    monkeypatch.setenv("FYLITE_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("FYLITE_SESSION", "a7b")
    cases.run("evolve-default")
    cases.run("zerod-iter-15ma")
    cases.run("transport-iter-15ma")
    doc = ledger.load(tmp_path / "a7b")
    ids = {n["id"] for n in doc["fylite:projection"]["dag"]["nodes"]}
    got = X.for_ledger(doc)
    assert len(ids) == 3
    assert {r["id"] for r in got["runnable"]} | set(got["refused"]) == ids
    assert not ({r["id"] for r in got["runnable"]} & set(got["refused"]))
