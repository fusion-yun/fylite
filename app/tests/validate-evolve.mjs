// The 含时演化 bar — the MARCH, end to end, against the native package.
//
// ★What this covers and why it can.  The bar's frozen-geometry tiers are
// fully reproducible from what the page writes: the metric ladder travels in
// the session file, the starting profiles are the controls' own prescribed
// shape on that ladder, every source is a kernel entry, and the closure is
// the constant tier.  So Python re-runs the SAME march through
// `fylite.scenario.model.assembly.solve_core` and the two must land on the
// same profiles.  That is a stronger statement than any per-entry gate: it
// checks the ASSEMBLY — which weight goes where, which unit crosses which
// boundary, which source lands in which channel — and the assembly is where
// a page can be wrong while every kernel entry is right.
//
// ★What it deliberately does NOT re-run: the free-boundary equilibrium of a
// coupled case.  The native side has no device descriptor (the same reason
// `validate-coupled` gave), so for `couple > 0` what is checked is what the
// alternation itself claims — the beta_p feedback law and the shape fit,
// re-derived here from the page's own per-round record.
//
// ★And the arithmetic that is NOT the kernel's: the readings.  W_th, the
// volume averages, beta_N, the Greenwald fraction and tau_E are definitions
// this page owns, so Python recomputes them from the exported profiles and
// the exported metric rather than trusting the numbers beside them.
//
//   node tests/app/validate-evolve.mjs [--playwright DIR] [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
//: ★the browser and the playwright that drives it are the OPERATOR's, and
//: `_browser.mjs` is where every gate asks for them — `--playwright` /
//: `$PLAYWRIGHT_PATH` for the library, `--chrome` / `$CHROME_PATH` for the
//: binary, because playwright pins one chromium build per release.
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';

// ★The constant closure throughout, and that is not a weakening: a
// neoclassical chi would put the page and the reference on two evaluations
// of the same closure at slightly different states, and what this gate is
// about is the ASSEMBLY around the closure.  The neoclassical tier has its
// own gate where the closure lives (`tests/test_transport_neo_closure.py`).
//: ★Every number here is a value the CONTROL can actually take: the step
//: counts are multiples of the slider's own step (5), and a case that asks
//: for 12 gets 10 — silently, because that is what a range input does.  The
//: first version of this gate did exactly that, and the reference then
//: marched two steps further than the page: 7 % apart, with nothing wrong
//: anywhere.
const CASES = [
  //: heat pair only, frozen Miller geometry — the smallest march that has a
  //: capacity, an exchange and a real power in megawatts
  { name: 'Miller · 热道', geometry: 'miller', 'ch-heat': true,
    'ch-density': false, 'ch-current': false, nsteps: 10, nlev: 21,
    dt: 0.002, dttarget: 0, pe: 3, pi: 3, dep: 0, depw: 0.3, fuel: 0,
    alpha: false, brem: true, ohmic: false, bootstrap: false, icd: 0,
    zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 0,
    closure: 0, chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3, edgeti: 0.3,
    edgene: 0.5, ne0: 5, peakt: 1.5, peakn: 0.5, vloop: 0, ip: 400 },
  //: the particle channel on, so the heat capacity moves while the
  //: temperatures are solved — the coupling the kernel's core march exists
  //: for, and the one an operator-split page gets wrong silently
  { name: 'Miller · 热道+粒子道', geometry: 'miller', 'ch-heat': true,
    'ch-density': true, 'ch-current': false, nsteps: 10, nlev: 21,
    dt: 0.002, dttarget: 0, pe: 4, pi: 2, dep: 0, depw: 0.35, fuel: 4,
    alpha: false, brem: true, ohmic: false, bootstrap: false, icd: 0,
    zeff: 1.5, chiratio: 1.2, dchi: 0.3, pinch: -0.5, dpc: 0, couple: 0,
    closure: 0, chi0: 0.8, te0: 3, ti0: 3, edgete: 0.3, edgeti: 0.3,
    edgene: 0.5, ne0: 5, peakt: 1.5, peakn: 0.5, vloop: 0, ip: 400 },
  //: a SOLVED equilibrium's ladder, with the current channel: q is a result
  //: here, and there is a flux to start it from, which the analytic tier
  //: has not (its gm2 is real since S-2c 批二; its psi is still zero)
  { name: '装置平衡 · 热道+电流道', geometry: 'device', 'ch-heat': true,
    'ch-density': false, 'ch-current': true, nsteps: 10, nlev: 21,
    dt: 0.001, dttarget: 0, pe: 2, pi: 2, dep: 0, depw: 0.3, fuel: 0,
    alpha: false, brem: true, ohmic: true, bootstrap: true, icd: 0,
    zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 0,
    closure: 0, chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3, edgeti: 0.3,
    edgene: 0.5, ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0.5, ip: 400 },
  //: the ALTERNATION: the equilibrium re-solved twice inside one march
  { name: '装置平衡 · 耦合', geometry: 'device', 'ch-heat': true,
    'ch-density': false, 'ch-current': true, nsteps: 10, nlev: 21,
    dt: 0.001, dttarget: 0, pe: 3, pi: 3, dep: 0, depw: 0.3, fuel: 0,
    alpha: false, brem: true, ohmic: true, bootstrap: true, icd: 0,
    zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 4,
    relax: 0.5, closure: 0, chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3,
    edgeti: 0.3, edgene: 0.5, ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0.5,
    ip: 400 },
  //: ★the BURNING tier: alpha heating on, hot and dense enough for it to be
  //: a number rather than a rounding error.  What it is here to catch is the
  //: failure that hid for one revision of this bar: the sources are fixed at
  //: the start of a `core_march` call, so a page that marched many steps per
  //: call REPORTED an alpha power that responded to the temperature while
  //: the plasma it heated was driven by the initial state's.
  { name: 'Miller · 燃烧（α 加热）', geometry: 'miller', 'ch-heat': true,
    'ch-density': false, 'ch-current': false, nsteps: 10, nlev: 21,
    dt: 0.002, dttarget: 0, pe: 5, pi: 5, dep: 0, depw: 0.30, fuel: 0,
    alpha: true, brem: true, ohmic: false, bootstrap: false, icd: 0,
    zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 0,
    closure: 0, chi0: 1.0, te0: 15, ti0: 15, edgete: 0.3, edgeti: 0.3,
    edgene: 0.5, ne0: 10, peakt: 1.5, peakn: 0.5, vloop: 0, ip: 400 },
  //: ★★LINE RADIATION, with the species NAMED.  Same march as the first
  //: case with argon at 1 % added, and it is here for two reasons: the
  //: radiated power must GROW (line radiation is not free), and the native
  //: re-run must reproduce it — which it can only do if the page sent the
  //: kernel the same species id and the same Z, so this is the gate on the
  //: `ADAS_Z` table beside the binding as much as on the wiring.
  { name: 'Miller · 线辐射（Ar 1%）', geometry: 'miller', 'ch-heat': true,
    'ch-density': false, 'ch-current': false, nsteps: 10, nlev: 21,
    dt: 0.002, dttarget: 0, pe: 3, pi: 3, dep: 0, depw: 0.3, fuel: 0,
    alpha: false, brem: true, ohmic: false, bootstrap: false, icd: 0,
    zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 0,
    closure: 0, chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3, edgeti: 0.3,
    edgene: 0.5, ne0: 5, peakt: 1.5, peakn: 0.5, vloop: 0, ip: 400,
    species: 'Ar', cimp: 1.0 },
  //: ★the NEOCLASSICAL tier, on the ladder: what it adds here is the block
  //: assembly — the surface's own minor and major radius in metres, the
  //: prescribed density's gradient, the gyro-Bohm unit — and that assembly
  //: is exactly what a page can get wrong while every kernel entry is right
  //: (it did: the 1.5-D bar carried the aspect ratio in the major-radius
  //: slot).  Not re-run natively: the closure would then be evaluated twice
  //: at slightly different states, which is the comparison that shares its
  //: inputs with what it is comparing.
  { name: '装置平衡 · 中子闭包', geometry: 'device', 'ch-heat': true,
    'ch-density': false, 'ch-current': false, nsteps: 10, nlev: 21,
    dt: 0.001, dttarget: 0, pe: 1, pi: 1, dep: 0, depw: 0.30, fuel: 0,
    alpha: false, brem: true, ohmic: false, bootstrap: false, icd: 0,
    zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 0,
    closure: 2, chi0: 0.20, te0: 3, ti0: 2.5, edgete: 0.3, edgeti: 0.3,
    edgene: 0.5, ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0, ip: 400 },
  //: ★★THE FIXED-BOUNDARY REFINEMENT, at two pressures and nothing else
  //: different.  One case would show that the refinement runs; two show
  //: that the PRESSURE is what moves it, which is the claim the feature
  //: makes and the one the two-parameter family cannot make — its beta_p
  //: is capped by (emp, enp, beta0) at a fixed I_p, so a march that walks
  //: past that cap leaves the family behind and the refinement has to
  //: follow.  Everything the pair asserts is below, under 定形边界回灌.
  { name: '装置平衡 · 耦合 + 定形回灌', geometry: 'device', 'ch-heat': true,
    'ch-density': false, 'ch-current': true, nsteps: 10, nlev: 21,
    dt: 0.001, dttarget: 0, pe: 3, pi: 3, dep: 0, depw: 0.3, fuel: 0,
    alpha: false, brem: true, ohmic: true, bootstrap: true, icd: 0,
    zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 4,
    relax: 0.5, closure: 0, chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3,
    edgeti: 0.3, edgene: 0.5, ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0.5,
    ip: 400, couplefixed: true, degp: 3, degf: 3, refine: true },
  //: ★the SAME case with two thirds of the auxiliary power, and nothing
  //: else moved: the two differ in the pressure the march reaches and in
  //: nothing a reader could confuse for it.  ★2 MW per channel, not 1: at
  //: 1 MW the FREE solve itself breaks on this diverted equilibrium (the
  //: family + beta feedback runs 600 iterations to residual 3.1e-1 — no
  //: equilibrium), and a refinement of a field that is not an answer has
  //: nothing to refine; the honest refusal it reports is the free solve's,
  //: not T-M17's.  At 2 MW the free solves are healthy and the pressure
  //: pair still differs far beyond the 2 % the comparison below demands.
  { name: '装置平衡 · 耦合 + 定形回灌（另一条压强）', geometry: 'device',
    'ch-heat': true, 'ch-density': false, 'ch-current': true, nsteps: 10,
    nlev: 21, dt: 0.001, dttarget: 0, pe: 2, pi: 2, dep: 0, depw: 0.3,
    fuel: 0, alpha: false, brem: true, ohmic: true, bootstrap: true,
    icd: 0, zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 4,
    relax: 0.5, closure: 0, chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3,
    edgeti: 0.3, edgene: 0.5, ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0.5,
    ip: 400, couplefixed: true, degp: 3, degf: 3, refine: true },
];

const OUT = mkdtempSync(join(tmpdir(), 'ev-'));
const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
//: ★factory defaults, not the bars' initial cases: this gate builds its own
//: configuration and compares it against a native run, so anything it does
//: not set itself has to be the DEFAULT rather than a case's value
//: EAST, because four of the six cases start from the machine's REFERENCE
//: DISCHARGE — the built-in ITER descriptor deliberately carries none
if (!await seedDevice(ctx, 'east')) {
  console.error(missingDeviceMessage('east'));
  process.exit(2);
}
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  if (m.type() === 'error' && !/favicon/.test(m.text()))
    errs.push('console: ' + m.text().slice(0, 200));
});

await page.goto(BASE + 'pages/model.html?device=east', { waitUntil: 'networkidle' });
const barState = (id) =>
  `((document.querySelector('[data-bar="${id}"] .funcbar-state')||{}).textContent||'')`;
await page.waitForFunction(
  () => /就绪|Ready|完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {}).textContent || ''),
  null, { timeout: 180000 });

//: ★the ADAS table as the KERNEL reports it, beside the atomic numbers the
//: binding carries.  A species the menu offers with no Z would build a
//: radiation call with `z = undefined`, so the two are checked against each
//: other here rather than discovered in a run.
const adas = await page.evaluate(() => ({
  menu: Array.from(document.getElementById('model-evolve-species').options)
             .map((o) => o.value).filter(Boolean),
  z: self.FyLite.ADAS_Z,
}));

const got = [];
for (const c0 of CASES) {
  //: ★every case states the WHOLE composition, including the absence of an
  //: impurity.  The cases run in order on one page, so a field a case does
  //: not set is the previous case's — which is how the argon case would have
  //: silently poisoned every run after it.
  //: ★`couplefixed` joins that list for the same reason: it is a checkbox,
  //: so a case that does not name it inherits the previous case's tick.
  const c = { species: '', cimp: 0, couplefixed: false, degp: 3, degf: 3,
              ...c0 };
  await page.evaluate((cfg) => {
    //: ★`couplefixed` is applied LAST, and that is not tidiness: the page
    //: only lets it be ticked when the coupling rhythm is non-zero AND the
    //: geometry is the device's, so a case that ticked it before setting
    //: those two would be ticking a disabled box.  This gate ran two
    //: "refinement" cases with no refinement in them exactly once.
    const late = (id) => (id === 'couplefixed' ? 1 : 0);
    Object.keys(cfg).sort((a, b) => late(a) - late(b)).forEach((id) => {
      if (id === 'name' || id === 'refine' || cfg[id] === undefined) return;
      const el = document.getElementById('model-evolve-' + id)
                 || document.getElementById('model-' + id);
      //: ★a control this bar does not have is an ERROR, not a skip — the
      //: silent skip is how a gate runs a case it did not mean to
      if (!el) throw new Error('no control evolve-' + id);
      if (el.type === 'checkbox') el.checked = !!cfg[id];
      else el.value = cfg[id];
      el.dispatchEvent(new Event(el.tagName === 'SELECT' || el.type === 'checkbox'
                                 ? 'change' : 'input'));
    });
  }, c);
  //: this bar never runs by itself — pressing its own key is both how a
  //: reader runs it and how this gate does
  await page.click('#model-evolve-run');
  await page.waitForFunction(
    (s) => /完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {}).textContent || ''),
    null, { timeout: 900000 });
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${got.length}.json`);
  await dl.saveAs(f);
  got.push({ case: c, doc: JSON.parse(readFileSync(f, 'utf8')) });
}
await br.close();

const PY = `
import json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
from fylite import kernel as K
#: ★the file is read THROUGH THE DECLARATION, not by walking paths spelled
#: again here: fyo.get(doc, TABLE, key) resolves the same slot the page
#: wrote with FyFyo.put, so a page that wrote to the wrong path fails
#: here rather than producing a document only it can read.
from fylite import fyo as FYO

QE = 1.602176634e-19

def vol_int(rho, vp, f):
    return float(np.trapezoid(np.asarray(f, float) * vp, rho))

out = []
for d in json.load(sys.stdin):
    c = d["case"]
    res = d["doc"]["fylite:result"]
    eq, cp = res["equilibrium"], res["core_profiles"]
    ct, cs, sm = res["core_transport"], res["core_sources"], res["summary"]

    def arr(doc, table, key, default=None):
        v = FYO.get(doc, table, key, default)
        return None if v is None else np.asarray(v, float)

    rho = arr(eq, "LADDER", "rho")
    vp = arr(eq, "LADDER", "vprime")
    gm3 = arr(eq, "LADDER", "gm3")
    gm2 = arr(eq, "LADDER", "gm2", None)
    gm2 = gm2 if gm2 is not None else np.zeros_like(gm3)
    fpol = arr(eq, "LADDER", "fpol")
    b0 = float(FYO.get(eq, "EQUILIBRIUM", "b0"))
    n = rho.size

    te = arr(cp, "CORE_PROFILES", "te")
    ti = arr(cp, "CORE_PROFILES", "ti")
    ne = arr(cp, "CORE_PROFILES", "ne")

    #: the march, column by column out of the summary
    def tcol(key):
        return arr(sm, "SUMMARY", key)
    t_axis = tcol("time")

    # --- the readings this page OWNS, recomputed ------------------------
    pres = (ne * te + ne * ti) * QE
    w_th = vol_int(rho, vp, 1.5 * pres)
    volume = vol_int(rho, vp, np.ones(n))
    w_tr = tcol("w_th")
    read_rel = abs(w_th - w_tr[-1]) / max(abs(w_th), 1e-30)
    p_alpha_tr = tcol("p_alpha")

    rec = {
        "name": c["name"],
        "reading_rel": read_rel,
        "volume": volume,
        "steps": int(t_axis.size),
        "t_end": float(t_axis[-1]),
        "monotone_t": bool(np.all(np.diff(t_axis) > 0)),
        "te_axis": float(te[0]), "ti_axis": float(ti[0]),
        "q_axis": float(tcol("q_axis")[-1]), "q95": float(tcol("q95")[-1]),
        #: ★the FIRST q95 beside the last: a loop voltage's job is to change
        #: the current, and only the direction of that change can tell a
        #: transformer from an anti-transformer.  The Ohmic power cannot:
        #: it is sigma E^2, positive for either sign.
        "q95_first": float(tcol("q95")[0]),
        "p_alpha": float(p_alpha_tr[-1]),
        "p_ohm": float(tcol("p_ohm")[-1]),
        "p_rad": float(tcol("p_rad")[-1]),
        "p_line": float(tcol("p_line")[-1]),
        #: the alpha power must MOVE with the temperature, not sit at the
        #: value the first state had
        "alpha_span": float(p_alpha_tr.max() - p_alpha_tr.min()),
        "geometry": eq["fylite:geometry_source"],
        "coupling": len(d["doc"].get("fylite:coupling") or []),
        "chi_lo": float(np.min(arr(ct, "CORE_TRANSPORT", "chi_i"))),
        "chi_hi": float(np.max(arr(ct, "CORE_TRANSPORT", "chi_i"))),
        #: ★the DOCUMENT SHAPE itself: every section is typed, and the two
        #: coordinate grids agree.  A page that wrote a slot to the wrong
        #: path would come back with a missing array here rather than with a
        #: number that looks plausible.
        "types": [eq.get("@type"), cp.get("@type"), ct.get("@type"),
                  cs.get("@type"), sm.get("@type")],
        "grid_agrees": bool(np.allclose(
            arr(ct, "CORE_TRANSPORT", "rho"), rho, rtol=1e-9, atol=0)
            and np.allclose(arr(cp, "CORE_PROFILES", "psin"),
                            arr(eq, "LADDER", "psin"), rtol=1e-9, atol=0)),
        "shape_res": [r.get("fylite:shape_residual")
                      for r in (d["doc"].get("fylite:coupling") or [])
                      if r.get("fylite:shape_residual") is not None],
        "march_rel": None,
    }

    # --- the fixed-boundary refinement, RE-SOLVED natively ---------------
    #
    # ★★This is the one piece of the equilibrium half that CAN be re-run
    # here, and it is the piece the page's claim rests on.  The file carries
    # the refinement's own sub-box: the Dirichlet border it was given, the
    # interior it produced, and the SOURCE as monomial coefficients in
    # psibar.  So this side rebuilds the plasma with the kernel's own
    # point-in-polygon and its own flood rule, forms
    # j_phi = R p' + FF'/(mu0 R) in the gauge the file declares, and asks
    # the native libfylite.so to solve Delta* psi = -2 pi mu0 R j_phi with that same
    # border.  The answer must BE the field the page shipped.
    #
    # ★What that pins, which nothing else here can: the two gauges.  The
    # page's own zero test compares two of its own solves; this compares the
    # page's field against an independent host's inversion of the equation
    # the file names.  A factor 2 pi (total flux against per radian) or
    # 4 pi^2 anywhere in the chain lands here as an answer orders apart —
    # which is exactly the failure this feature shipped with.
    rf = d["doc"].get("fylite:refined_field")
    if rf is not None:
        rr = np.asarray(rf["fylite:r"], float)
        zz = np.asarray(rf["fylite:z"], float)
        nr, nz = rr.size, zz.size
        psi = np.asarray(rf["fylite:psi"], float).reshape(nr, nz)
        pa, pb = float(rf["fylite:psi_axis"]), float(rf["fylite:psi_boundary"])
        cpp = np.asarray(rf["fylite:pprime_coef"], float)
        cff = np.asarray(rf["fylite:ffprime_coef"], float)
        lr = np.asarray(rf["fylite:limiter_r"], float)
        lz = np.asarray(rf["fylite:limiter_z"], float)
        sgn = 1.0 if pa > pb else -1.0
        RG, ZG = np.meshgrid(rr, zz, indexing="ij")
        iv = np.asarray(K.inside_polygon(RG.ravel(), ZG.ravel(), lr, lz)
                        ).reshape(nr, nz).astype(bool)
        ai = int(round((float(rf["fylite:axis_r"]) - rr[0]) / (rr[1] - rr[0])))
        aj = int(round((float(rf["fylite:axis_z"]) - zz[0]) / (zz[1] - zz[0])))
        mask = np.zeros((nr, nz), bool)
        stack, touched = [(ai, aj)], False
        while stack:
            i, j = stack.pop()
            if i < 0 or j < 0 or i >= nr or j >= nz or mask[i, j]:
                continue
            if not iv[i, j] or sgn * psi[i, j] <= sgn * pb:
                continue
            mask[i, j] = True
            if i in (0, nr - 1) or j in (0, nz - 1):
                touched = True
                continue
            stack += [(i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)]
        span_pr = (pb - pa) / (2.0 * np.pi)
        xn = np.clip((psi - pa) / (pb - pa), 0.0, 1.0)
        pol = lambda c, u: sum(c[k] * u ** k for k in range(len(c)))
        #: ★T-M17: the kernel's declared edge control is PART of the
        #: equation the file names — j_phi carries a C¹ smoothstep to zero
        #: over the last edge_taper of psibar, and the file DECLARES the
        #: width.  Spelled here independently (numpy, not the kernel's
        #: function), so a taper that silently changed width or shape
        #: lands as a residual.
        w_tap = float(rf.get("fylite:edge_taper", 0.05))
        st = np.clip((1.0 - xn) / w_tap, 0.0, 1.0)
        tap = np.where(xn <= 1.0 - w_tap, 1.0, st * st * (3.0 - 2.0 * st))
        jphi = np.where(mask, tap * (RG * pol(cpp, xn) / span_pr
                        + pol(cff, xn) / span_pr / (4e-7 * np.pi * RG)), 0.0)
        jphi[0, :] = jphi[-1, :] = 0.0
        jphi[:, 0] = jphi[:, -1] = 0.0
        ip_nat = float(jphi.sum() * (rr[1] - rr[0]) * (zz[1] - zz[0]))
        rhs = -2.0 * np.pi * (4e-7 * np.pi) * RG * jphi
        lib = K.require()
        sol = np.ascontiguousarray(psi.copy())
        rc = lib.fylite_rs_deltastar_solve(
            np.ascontiguousarray(rr), nr, np.ascontiguousarray(zz), nz,
            sol, np.ascontiguousarray(rhs))
        rec["refine_rc"] = int(rc)
        rec["refine_cells"] = int(mask.sum())
        rec["refine_touched"] = bool(touched)
        rec["refine_psi_rel"] = float(np.abs(sol - psi).max() / abs(pb - pa))
        rec["refine_ip_rel"] = abs(ip_nat - float(rf["fylite:ip"])) \
            / max(abs(float(rf["fylite:ip"])), 1.0)
        rec["refine_ip"] = ip_nat
        #: ★non-degenerate: a field with no current in it would pass every
        #: relative comparison above, so the current itself has to be a
        #: current and the source has to have both channels in it
        rec["refine_pp0"] = float(pol(cpp, 0.0))
        rec["refine_ff0"] = float(pol(cff, 0.0))

        # --- the WHOLE Picard, re-run natively (T-M7) --------------------
        #
        # ★★The Delta* re-solve above checks the field against the equation;
        # this checks the LOOP.  The refinement's axis rule and plasma rule
        # are the kernel's now (\`fylite_rs_gs_fixed_box\`), so a second host
        # can run the same loop on the same box: the border, the source
        # coefficients, the gauge the file declares and the axis it reports
        # as the seed.  The page's field must be that loop's FIXED POINT —
        # start it there and it comes straight back.
        #
        # ★And this is the assertion T-M7 exists for.  The rule it replaced
        # took the interior extremum FARTHEST from psi_b over the whole
        # rectangle, which on this box is a corner: an entry still carrying
        # that rule would come back with an axis on the border ring and a
        # field orders away, not with the page's.  So the axis is checked
        # against the corner as well as against the page.
        try:
            #: ★T-M17: the re-run holds the same I_p the page's solve held —
            #: the file declares the target.  Without it the loop is a
            #: DIFFERENT dynamical system (the unconstrained one), whose
            #: transients on a separatrix-bounded field run away from the
            #: very fixed point being checked.
            tgt = rf.get("fylite:ip_target")
            bx = K.gs_fixed_box(
                rr, zz, psi, psi_boundary=pb, sign_axis=sgn,
                seed_r=float(rf["fylite:axis_r"]),
                seed_z=float(rf["fylite:axis_z"]),
                pprime=cpp, ffprime=cff, limiter_r=lr, limiter_z=lz,
                gauge=2.0 * np.pi, dilate=2, relax=0.5, max_iter=600,
                tol=1e-9,
                ip_target=None if tgt is None else float(tgt))
            rec["box_ok"] = True
            rec["box_iterations"] = bx["iterations"]
            rec["box_psi_rel"] = float(
                np.abs(bx["psi"] - psi).max() / abs(pb - pa))
            rec["box_ip_rel"] = abs(bx["ip"] - float(rf["fylite:ip"])) \
                / max(abs(float(rf["fylite:ip"])), 1.0)
            rec["box_axis_dr"] = abs(bx["axis_r"]
                                     - float(rf["fylite:axis_r"]))
            rec["box_axis_dz"] = abs(bx["axis_z"]
                                     - float(rf["fylite:axis_z"]))
            #: how far the axis it found sits from the nearest box edge, in
            #: cells — the whole-rectangle rule would put it at 1
            dcell = min((bx["axis_r"] - rr[0]) / (rr[1] - rr[0]),
                        (rr[-1] - bx["axis_r"]) / (rr[1] - rr[0]),
                        (bx["axis_z"] - zz[0]) / (zz[1] - zz[0]),
                        (zz[-1] - bx["axis_z"]) / (zz[1] - zz[0]))
            rec["box_axis_cells_in"] = float(dcell)
        except Exception as e:                      # noqa: BLE001
            rec["box_ok"] = False
            rec["box_why"] = str(e)[:200]

    # --- the march itself, RE-RUN through the KERNEL'S OWN LOOP ---------
    #
    # ★★ONE CALL, and that is the point of this revision (TODO §1.4, the
    # assembly-level half of the cross-host claim).  Until 2026-08-26 this
    # block carried its own step-by-step march — SourceSet, bremsstrahlung,
    # alpha split, deposit, one \`solve_core\` per step — which made it a
    # FOURTH implementation of an orchestration the kernel now owns
    # (\`evolve_heat\`), sitting in a JS string where nothing could gate it.
    # A gate that reproduces the page by re-deriving the page's arrangement
    # is only as good as its own copy of that arrangement, and this copy had
    # no reader but this file.
    #
    # ★What replaces it is the assembly entry the CORPUS uses
    # (\`fylite.scenario.model.evolve\`, whose loop is the kernel's), reached
    # through the SAME mapper the corpus goes through
    # (\`cases.args_for\`).  So this comparison is now「浏览器循环 vs 内核
    # 循环」 with one translation of the page's controls, not two — a unit
    # that is wrong is wrong in both places at once and is caught by the
    # corpus gate, instead of being right here and wrong there.
    #
    # ★And the SCOPE is the entry's, said by name rather than guessed by a
    # boolean list.  \`args_for\` refuses a configuration outside what has
    # been sunk (the density and current channels, sawteeth, beams, waves,
    # the device / g-file geometry tiers, the equilibrium alternation) and
    # names the missing capability; the refusal travels to the reader as a
    # SKIP with its reason, which is the honest report for a comparison this
    # side cannot make yet.  ★That the previous boolean list covered TWO
    # cases this entry cannot yet run (the particle channel, and every
    # device-geometry case) is recorded in TODO as coverage the sinking owes
    # back — not hidden here behind a silently narrower filter.
    import fylite.scenario.cases as CASES
    import fylite.scenario.model as MODEL

    cfg = d["doc"].get("fylite:config") or {}
    try:
        args = CASES.args_for("evolve", cfg)
    except SystemExit as exc:
        rec["march_skip"] = str(exc)
    except Exception as exc:                        # noqa: BLE001
        #: ★a mapper that BREAKS is not a case out of scope, and must not be
        #: reported as one — the two look identical from the outside and
        #: only one of them is acceptable
        rec["march_error"] = f"{type(exc).__name__}: {exc}"
    else:
        r = MODEL.evolve(**args)
        #: the ladder the entry built from the page's own controls must BE
        #: the ladder the page shipped — a metric that differs is a march
        #: comparison that was never on the same grid
        rec["march_grid_rel"] = float(
            np.max(np.abs(np.asarray(r["rho"], float) - rho))
            / max(float(np.max(np.abs(rho))), 1e-30))
        rec["march_rel"] = max(
            float(np.max(np.abs(r["te"] - te)) / max(np.max(np.abs(te)), 1e-30)),
            float(np.max(np.abs(r["ti"] - ti)) / max(np.max(np.abs(ti)), 1e-30)))
        rec["march_steps"] = int(r["steps"])
    out.append(rec)
print(json.dumps(out))
`;

const ref = JSON.parse(execFileSync('python3', ['-c', PY], {
  input: JSON.stringify(got.map(g => ({
    case: { ...g.case, z_imp: adas.z[g.case.species] }, doc: g.doc }))),
  encoding: 'utf8', maxBuffer: 1 << 28 }));

let bad = 0;
const refineCases = [];
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};
ref.forEach((r, i) => {
  const c = { species: '', cimp: 0, ...CASES[i] };
  console.log(`\n${c.name}`);
  //: the readings this page OWNS, re-derived rather than believed
  say(r.reading_rel < 1e-5, 'W_th matches the exported profiles',
      `rel ${r.reading_rel.toExponential(1)}`);
  say(r.steps === c.nsteps, 'every step is in the trace',
      `${r.steps}/${c.nsteps}`);
  say(r.monotone_t, 'the time axis increases', `t_end ${r.t_end.toFixed(4)} s`);
  say(r.volume > 0, 'the metric encloses a volume',
      `${r.volume.toFixed(3)} m^3`);
  //: ★★the export is fyo, and it is read back through the DECLARATION:
  //: every section carries the type its table declares, and the two grids
  //: that must agree do.  A slot written to the wrong path comes back
  //: missing here rather than as a plausible number.
  say(r.types.join(',') === 'fyo:equilibrium,fyo:core_profiles,' +
        'fyo:core_transport,fyo:core_sources,fyo:summary',
      'the result is five typed fyo documents', r.types.join(' '));
  say(r.grid_agrees, 'the sections share one coordinate grid');
  say(r.te_axis > 0 && r.ti_axis > 0, 'both temperatures are positive',
      `${(r.te_axis / 1e3).toFixed(3)} / ${(r.ti_axis / 1e3).toFixed(3)} keV`);
  //: ★a mapper that BROKE is a failure, not a case out of scope — the two
  //: are indistinguishable from outside unless one of them is loud
  if (r.march_error !== undefined)
    say(false, '把页面控件映射到内核入口时出错', r.march_error);
  else if (r.march_rel === null) {
    //: ★SKIPPED BY NAME.  The entry says which capability it lacks; a
    //: comparison this side cannot make is reported as not made, with the
    //: reason, rather than quietly left out of the count.
    console.log(`  skip  内核循环还沉不下这一档 — ${r.march_skip}`);
  } else {
    //: ★the two sides must be on ONE ladder before their profiles are
    //: compared: the entry rebuilds the Miller metric from the page's own
    //: controls, so a metric that differs means the comparison below was
    //: never on the same grid — and would then be measuring the assembly
    //: of the geometry, silently, instead of the march.
    say(r.march_grid_rel < 1e-9, '两侧站在同一条度规梯子上',
        `rel ${r.march_grid_rel.toExponential(1)}`);
    say(r.march_steps === r.steps, '两侧走了同样多步',
        `${r.march_steps}/${r.steps}`);
    //: ★the tolerance is the FILE's, not the solver's: the session rounds
    //: every array to 7 significant digits, and a march is nonlinear, so the
    //: two sides start from grids that differ in the 7th digit — that
    //: rounding, amplified, is the floor and nothing here can go below it.
    //: ★TIGHTENED 1e-4 → 1e-5 when the reference became the kernel's own
    //: loop (2026-08-26): the old number had to cover a hand-written march
    //: that only APPROXIMATED the page's arrangement, and measured 1e-5…1e-6
    //: because of it.  The three in-scope cases now measure
    //: **1.1e-7 / 3.4e-7 / 1.2e-7** — about seven times the file's own
    //: rounding, which is what a nonlinear march does to it.  1e-5 keeps ~30x
    //: headroom over the worst of those while being ten times tighter than a
    //: reference that is no longer here.
    say(r.march_rel < 1e-5, 'the kernel loop reaches the same profiles',
        `rel ${r.march_rel.toExponential(1)}`);
  }
  const wantGeo = 'fylite:' + (c.geometry === 'miller' ? 'miller' : 'device');
  say(r.geometry === wantGeo, 'the geometry source is recorded', r.geometry);
  if (c['ch-current'])
    say(r.q_axis > 0.2 && r.q_axis < 20 && r.q95 > r.q_axis,
        'q is solved and ordered', `q0 ${r.q_axis.toFixed(2)} q95 ${r.q95.toFixed(2)}`);
  if (c.alpha) {
    say(r.p_alpha > 0, 'the alphas are heating something',
        `${(r.p_alpha / 1e6).toFixed(3)} MW`);
    //: ★the whole point of per-step sources: a frozen source would report
    //: the same alpha power at every step
    say(r.alpha_span > 0.01 * r.p_alpha,
        'the alpha power follows the temperature',
        `span ${(r.alpha_span / 1e6).toExponential(2)} MW`);
  }
  if (c.closure === 2)
    //: a neoclassical chi is a PROFILE — it falls with temperature, so a
    //: flat one means the block never reached the closure
    say(r.chi_hi > 1.5 * r.chi_lo && r.chi_lo > 0,
        'the neoclassical closure produced a profile',
        `${r.chi_lo.toFixed(3)}–${r.chi_hi.toFixed(3)} m^2/s`);
  if (c.brem) say(r.p_rad > 0, 'the plasma radiates',
                  `${(r.p_rad / 1e6).toExponential(2)} MW`);
  if (c.species)
    //: ★line radiation is not free: with an impurity named the non-brem
    //: part must DOMINATE the answer — argon at 1 % radiates far more than
    //: the deuterium it sits in
    say(r.p_line > 0.5 * r.p_rad,
        'the named species dominates the radiation',
        `line ${(r.p_line / 1e6).toExponential(2)} of ${(r.p_rad / 1e6).toExponential(2)} MW`);
  else if (c.brem)
    //: ★and without one it must NOT: pure deuterium's ADAS curve and the
    //: routine's own NRL bremsstrahlung agree to a few per cent at keV
    //: temperatures, so the difference between them is a small residual
    //: rather than a radiating species nobody chose
    say(Math.abs(r.p_line) < 0.5 * r.p_rad,
        'with no impurity the split is a small residual',
        `line ${(r.p_line / 1e6).toExponential(2)} of ${(r.p_rad / 1e6).toExponential(2)} MW`);
  //: ★NOT on a refined run, and the reason is what the two endpoints are.
  //: This assertion reads the FIRST q95 against the LAST; on a refined run
  //: the first comes from the two-parameter family and the last from the
  //: fixed-boundary refinement, which is a more peaked current profile by
  //: construction (measured on this pair: q0 0.64 -> 0.50 while q95 2.22 ->
  //: 2.39).  Their difference is therefore not the loop voltage's doing and
  //: the direction it points says nothing about the transformer.  The
  //: un-refined coupled case above still carries this one.
  if (c.ohmic && c['ch-current'] && c.vloop !== 0 && !c.refine) {
    //: the Ohmic term is lagged by one step, so it is zero on the first and
    //: must not be zero at the last
    say(r.p_ohm > 0, 'the loop voltage drives an Ohmic power',
        `${(r.p_ohm / 1e6).toExponential(2)} MW`);
    //: ★★AND IT DRIVES IT THE RIGHT WAY.  q95 goes as 1/Ip, so a positive
    //: loop voltage must LOWER it.  The page had the edge flux rate at
    //: -V_loop in a gauge whose psi increases outward, so a positive
    //: voltage de-energised the plasma — and the assertion above passed
    //: through the whole of that, because sigma E^2 does not care which
    //: way E points.
    const want = c.vloop > 0;
    const rose = r.q95_first > r.q95;
    say(rose === want,
        `正的环电压把电流${want ? '驱上去' : '压下来'}`,
        `q95 ${r.q95_first.toFixed(3)} → ${r.q95.toFixed(3)}`);
  }
  if (c.couple > 0) {
    say(r.coupling >= 2, 'the alternation ran more than one block',
        `${r.coupling} blocks`);
    say(r.shape_res.every(v => v < 1),
        'the shape fit is inside its own family',
        `residual ${r.shape_res.map(v => v.toExponential(1)).join(', ')}`);
  }
  if (c.refine) refineCases.push({ c, r, rows: got[i].doc['fylite:coupling'] || [],
                                 doc: got[i].doc });
});

// --- 定形边界回灌 ------------------------------------------------------
//
// ★★Three things, and they are the three this feature was told to prove
// before it could be claimed.  ①The ZERO TEST: the refinement, run on the
// p'/FF' the free solve itself implies, must come back to that field.  It
// is a refusal threshold inside the page, so a block that reports a
// refinement has already met it — what is asserted here is that the number
// travels, that it is real (the test ran, on a plasma), and that it is
// where the closure criteria put it.  ②The PRESSURE actually biting: two
// cases differing only in the pressure, and the refined beta_p must move
// with it and sit closer to the transport's than the two-parameter family
// gets.  ③FAILURE STAYING SAFE: every block either refined or said why,
// never neither and never both, and a block that refused still carries the
// family's answer.
//
// ★And under all three, the NATIVE re-solve: the page's field, its border
// and its source coefficients handed to the native libfylite.so, which
// inverts Delta* itself.  That is the oracle this bar could not have for
// the free-boundary half.
console.log('\n定形边界回灌');
{
  const ZP = 1e-3, ZI = 0.01;
  say(refineCases.length >= 2, '回灌跑了不止一条压强',
      `${refineCases.length} 个算例`);
  //: ★★T-M17 CLOSED (the declared edge taper, `BOX_EDGE_TAPER` in
  //: `equilibrium.rs`): on the diverted reference equilibrium the
  //: polynomial-source refinement used to refuse EVERY block — its mask,
  //: fed by a source alive at ψ̄ = 1, grew to the sub-box ring across the
  //: flat approach to the separatrix.  With the source tapered to zero
  //: over the last 0.05 of ψ̄ the runaway has no feed, so the assertion is
  //: UNCONDITIONAL again: at least one block per pressure truly refines,
  //: and the growth refusal never appears.  (A block may still refuse for
  //: upstream reasons — a free solve that broke on its own tolerance fails
  //: the zero test honestly — which is why "at least one", not "all".)
  refineCases.forEach(({ c, r, rows, doc }) => {
    const ran = rows.filter((q) => q['fylite:refined']);
    const said = rows.filter((q) => !q['fylite:refined'] && q['fylite:refine_why']);
    const blocks = rows.filter((q) => q['fylite:beta_p_transport'] !== null);
    say(ran.length > 0,
        `${c.name}：至少有一轮真的细化了（T-M17 已关闭，无条件断言恢复）`,
        `${ran.length} 成 / ${said.length} 退 / ${blocks.length} 轮`);
    //: ★a growth refusal is still LEGAL on one kind of block: one whose
    //: FREE solve broke (600 iterations, residual ~1e-1 — no equilibrium).
    //: A field that is not an answer has nothing shaped like a plasma to
    //: refine, and the refusal text points at the upstream residual.  What
    //: T-M17 closed is growth on HEALTHY fields — so the assertion is that
    //: every remaining「涨」sits on a block whose free residual is above
    //: 1e-2, an order past anything the settled verdict ever floors at.
    const fbRows = doc['fylite:free_boundary'] || [];
    const freeResOf = (b) => {
      const q = fbRows.find((e) => e['fylite:block'] === b);
      return q ? q['fylite:residual'] : undefined;
    };
    say(said.every((q) => {
      if (!/涨到了子网格边界|grew/.test(q['fylite:refine_why'])) return true;
      const fr = freeResOf(q['fylite:block']);
      return fr !== undefined && fr > 1e-2;
    }), `${c.name}：剩下的「涨」只出现在自由解自己没解出来的块上（残差 > 1e-2）`,
        said.length ? said.map((q) =>
          `块 ${q['fylite:block']} 自由解残差 ` +
          `${(freeResOf(q['fylite:block']) || NaN).toExponential(1)}`)
          .join(' ／ ') : '无退');
    //: ★★failure stays safe AND says why — the one thing that already
    //: worked before this batch and the one thing that must not be lost.
    //: Every block that had an equilibrium half either refined or named a
    //: reason; never silence, and never both at once.
    say(blocks.every((q) => !!q['fylite:refined'] !== !!q['fylite:refine_why']),
        `${c.name}：每一轮要么细化了、要么说了为什么`,
        `${ran.length} 成 / ${said.length} 退`);
    say(blocks.every((q) => Number.isFinite(q['fylite:beta_p_equilibrium'])),
        `${c.name}：退回去的那一轮仍然带着两参数族的答案`);
    ran.forEach((q) => {
      const zt = q['fylite:refined']['fylite:zero_test'];
      const b = q['fylite:block'];
      say(!!zt, `${c.name} 第 ${b} 轮：零测试的数跟着走`);
      if (!zt) return;
      //: ★not a stub: a zero test that reported 0 without iterating, or
      //: that compared against a current of zero, would satisfy every
      //: relative bound below and mean nothing
      say(zt['fylite:iterations'] >= 2 && zt['fylite:psi_pointwise'] > 0
            && Math.abs(zt['fylite:ip_free']) > 1e3,
          `${c.name} 第 ${b} 轮：零测试确实解了一次`,
          `${zt['fylite:iterations']} 次迭代 · 对照 I_p `
          + `${(zt['fylite:ip_free'] / 1e3).toFixed(1)} kA`);
      //: ★the closure criteria themselves — RESIDUAL-AWARE since v108: the
      //: zero test cannot come back closer to the free field than the free
      //: solve itself got (measured across six blocks, it tracks that and
      //: nothing else), so the page's own refusal threshold is
      //: max(1e-3, 3 × free residual) and this asserts the same bound.
      const zpAllowed = Math.max(ZP, 3 * zt['fylite:free_residual']);
      say(zt['fylite:psi_pointwise'] < zpAllowed,
          `${c.name} 第 ${b} 轮：ψ 与自由解逐点差 < ${zpAllowed.toExponential(1)}`
          + '（max(1e-3, 3×自由解残差)）',
          `${zt['fylite:psi_pointwise'].toExponential(2)}`
          + `（自由解自己 ${zt['fylite:free_iterations']} 次迭代、残差 `
          + `${zt['fylite:free_residual'].toExponential(1)}）`);
      say(zt['fylite:ip_relative'] < ZI,
          `${c.name} 第 ${b} 轮：I_p 相对差 < ${100 * ZI} %`,
          `${(100 * zt['fylite:ip_relative']).toFixed(3)} %`);
    });
    //: ★the native re-solve, on the one refined box the file carries
    if (r.refine_psi_rel !== undefined) {
      say(r.refine_rc === 0 && !r.refine_touched && r.refine_cells > 100,
          `${c.name}：原生侧重建出的等离子体是一团等离子体`,
          `${r.refine_cells} 个格点，未触及子网格边界`);
      say(r.refine_pp0 !== 0 && r.refine_ff0 !== 0,
          `${c.name}：源的两条通道都在`,
          `dp/dψ̄(0) ${r.refine_pp0.toExponential(2)} Pa · `
          + `d(F²/2)/dψ̄(0) ${r.refine_ff0.toExponential(2)} T²m²`);
      //: ★the tolerance and where it comes from: the file writes this psi
      //: at 12 significant digits (4e-12 of the flux span) and the
      //: refinement's own Picard stops at 1e-9 of it.  1e-6 is three
      //: orders above both — and six below what a 2 pi gauge error moves,
      //: which is the failure this check exists for.
      say(r.refine_psi_rel < 1e-6,
          `${c.name}：原生 Δ* 重解就是页面交出来的那张场`,
          `逐点 ${r.refine_psi_rel.toExponential(2)}（除以磁通跨度）`);
      say(r.refine_ip_rel < 1e-6,
          `${c.name}：原生重算的 I_p 就是页面报的那个`,
          `${(r.refine_ip / 1e3).toFixed(2)} kA，相对差 `
          + `${r.refine_ip_rel.toExponential(2)}`);
      //: ★★T-M7: the LOOP is the kernel's, and this says so from outside.
      //: `fylite_rs_gs_fixed_box` is handed the same box and asked to run
      //: the whole Picard; the page's field has to be its fixed point.
      say(r.box_ok === true, `${c.name}：内核的定形回灌能在这个子框上跑`,
          r.box_ok ? `${r.box_iterations} 轮` : (r.box_why || ''));
      if (r.box_ok) {
        //: ★the closure criterion itself: the axis is found INSIDE the box
        //: and not on it.  The rule this replaced takes the interior
        //: extremum farthest from psi_b over the whole rectangle, which on
        //: a box cut around a plasma is the corner one cell in.
        say(r.box_axis_cells_in > 4,
            `${c.name}：找轴落在框里，不在框角上`,
            `离最近的框边 ${r.box_axis_cells_in.toFixed(1)} 格`);
        say(r.box_axis_dr < 1e-6 && r.box_axis_dz < 1e-6,
            `${c.name}：内核找到的轴就是页面报的那个轴`,
            `Δ ${r.box_axis_dr.toExponential(1)} / `
            + `${r.box_axis_dz.toExponential(1)} m`);
        //: ★the tolerance and its source: the loop is started AT the page's
        //: field, so what it can move by is its own stopping tolerance
        //: (1e-9 of the span) plus the file's 12 significant digits — and
        //: the field it re-solves from is a 7-digit-free copy of the page's
        //: own.  1e-6 is three orders above that.
        say(r.box_psi_rel < 1e-6,
            `${c.name}：页面交出来的那张场就是内核这圈 Picard 的不动点`,
            `逐点 ${r.box_psi_rel.toExponential(2)}（除以磁通跨度）`);
        say(r.box_ip_rel < 1e-6, `${c.name}：内核这圈算出的 I_p 也是那个`,
            `相对差 ${r.box_ip_rel.toExponential(2)}`);
      }
    } else {
      //: T-M17 closed: a case with a refined block MUST carry its sub-box,
      //: and the unconditional assertion above already failed if none ran —
      //: so reaching here is itself a failure to name
      say(false,
          `${c.name}：会话文件里没有细化过的子网格（细化成功后它必须在）`,
          `${ran.length} 轮细化成功`);
    }
  });
  //: ★★THE PRESSURE FEED-BACK, and the only way to see it is two cases.
  //: What is compared is the LAST block that refined in each: beta_p must
  //: MOVE with the pressure (a refinement that ignored p' would report the
  //: same number twice) and must sit closer to the transport's beta_p than
  //: the two-parameter family does — the family's is capped by (emp, enp,
  //: beta0) at a fixed I_p, which is the whole reason this feature exists.
  if (refineCases.length >= 2) {
    const lastOf = (k) => {
      const rows = refineCases[k].rows.filter((q) => q['fylite:refined']);
      return rows[rows.length - 1];
    };
    const A = lastOf(0), B = lastOf(1);
    if (!A || !B) {
      //: T-M17 closed: the pressure-bite comparison has a subject again,
      //: and losing it is a failure, not a degraded mode
      say(false, '两条压强都必须有细化成功的一轮（T-M17 已关闭）',
          `A ${A ? '有' : '无'} · B ${B ? '有' : '无'}`);
    } else {
      const fA = A['fylite:beta_p_refined'], fB = B['fylite:beta_p_refined'];
      const tA = A['fylite:beta_p_transport'], tB = B['fylite:beta_p_transport'];
      const eA = A['fylite:beta_p_equilibrium'], eB = B['fylite:beta_p_equilibrium'];
      say(Number.isFinite(fA) && Number.isFinite(fB),
          '两条压强都报出了细化后的 β_p', `${fA} / ${fB}`);
      //: the transport's own beta_p must differ between the two, or the
      //: comparison below is comparing a case with itself
      say(Math.abs(tA - tB) > 0.02 * Math.max(tA, tB),
          '两条算例的输运 β_p 确实不同',
          `${tA.toFixed(3)} vs ${tB.toFixed(3)}`);
      say(Math.abs(fA - fB) > 0.02 * Math.max(fA, fB),
          '细化后的 β_p 跟着压强动了',
          `${fA.toFixed(3)} → ${fB.toFixed(3)}`);
      const relF = (f, t) => Math.abs(f - t) / Math.abs(t);
      say(relF(fA, tA) < relF(eA, tA) && relF(fB, tB) < relF(eB, tB),
          '细化后的 β_p 比两参数族更贴输运给的那条',
          `A 细化 ${(100 * relF(fA, tA)).toFixed(1)} % vs 族 `
          + `${(100 * relF(eA, tA)).toFixed(1)} % · B 细化 `
          + `${(100 * relF(fB, tB)).toFixed(1)} % vs 族 `
          + `${(100 * relF(eB, tB)).toFixed(1)} %`);
    }
  }
}
console.log('\nADAS 物种表');
{
  const missing = adas.menu.filter((n) => !(n in adas.z));
  const extra = Object.keys(adas.z).filter((n) => adas.menu.indexOf(n) < 0);
  say(adas.menu.length > 0, '菜单来自内核', `${adas.menu.length} 个物种`);
  say(missing.length === 0, '每个物种都有原子序数',
      missing.length ? missing.join(' ') : '');
  say(extra.length === 0, '原子序数表里没有内核不认的物种',
      extra.length ? extra.join(' ') : '');
}
if (errs.length) { console.log('\n页面报错：'); errs.forEach(e => console.log('  ' + e)); }
console.log(bad || errs.length ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad || errs.length ? 1 : 0);
