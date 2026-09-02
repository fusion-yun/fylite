// Assembly gate for the 1.5D transport page.
//
// The two borrowed halves already have their own gates (`validate-geo`,
// `validate-transport`).  What neither covers is the LAYER BETWEEN them,
// which is where this page can be wrong while both halves are right:
//
//   * the prescribed q(rho) the metric is built on;
//   * which weight goes where — capacity V', flux V'<|grad r|^2>;
//   * the axis convention (V'(0) is set, not asked of geo_do);
//   * the source, the edge value and the grid.
//
// So Python rebuilds the metric from the SAME prescription and re-solves with
// it, and both are compared against what the page exported.
//
//   node tests/app/validate-transport-app.mjs [--playwright DIR] [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const iu = process.argv.indexOf('--url');
const BASE = iu > 0 ? process.argv[iu + 1] : 'http://127.0.0.1:8767/app/';

// The two PRESCRIBED closure tiers: only the stiff one exercises the Picard
// loop, and the shaping differs so a metric wired to the wrong surface shows
// up.
//
// ★The NEOCLASSICAL tier is not compared here.  Its diffusivity is the
// kernel's own, so re-solving it on this side would mean rebuilding the NEO
// normalisation in Python — the second copy D-4 exists to prevent.  It is
// gated instead where the closure lives, against a natively assembled loop
// (`tests/test_transport_neo_closure.py`).  What this file adds for it is
// the one thing that gate cannot see: that the PAGE assembles the physical
// blocks correctly, checked below by re-deriving chi from the page's own
// export through the kernel's `neo_chi`.
const CASES = [
  { name: '常数 χ', rmaj: 3.0, kappa: 1.6, delta: 0.3, q95: 3.5, chi0: 0.6,
    pinch: 0, power: 12, width: 0.35, edge: 0.3, n: 41, closure: 0 },
  { name: '刚性闭包', rmaj: 3.4, kappa: 1.9, delta: 0.45, q95: 5.0, chi0: 0.9,
    pinch: -0.5, power: 20, width: 0.25, edge: 0.5, n: 61, closure: 1 },
  //: ★The power is 6, not the page's default 12, because 12 runs the
  //: neoclassical closure into its thermal runaway and the solve is
  //: singular.  That is the physics (see the closure's own note) rather
  //: than a limit of the page, and a gate case has to sit where the
  //: equation is well posed.
  { name: '中子闭包', rmaj: 3.0, kappa: 1.6, delta: 0.3, q95: 3.5, chi0: 0.6,
    pinch: 0, power: 6, width: 0.35, edge: 0.3, n: 41, closure: 2,
    amin: 0.6, bunit: 2.0, ne0: 3.0 },
];

const OUT = mkdtempSync(join(tmpdir(), 'tr-'));
const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true });
//: ★factory defaults, not the bars' initial cases: this gate builds its own
//: configuration, so anything it does not set itself has to be the DEFAULT
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200));
});

await page.goto(BASE + 'pages/model.html?device=iter#part-model', { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /完成|Done|未收敛|失败|Failed|就绪|Ready/.test(
    document.getElementById('model-status').textContent), null, { timeout: 180000 });

const got = [];
for (const c of CASES) {
  await page.evaluate((cfg) => {
    Object.keys(cfg).forEach((id) => {
      if (id === 'name') return;
      const el = document.getElementById('model-transport-' + id)
                 || document.getElementById('model-' + id);
      if (el.type === 'checkbox') el.checked = cfg[id]; else el.value = cfg[id];
      //: a <select> answers to `change`, a range to `input`
      el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input'));
    });
  }, c);
  await page.waitForFunction(() => !document.getElementById('model-transport-run').classList.contains('stop'), null, { timeout: 300000 });
  //: ★the run button runs the PAGE — every part of this scenario, in order —
  //: and this gate is about one of them.  A reader reaches one part on its own
  //: by changing one of ITS controls, which is what this does: the values are
  //: all set above, and one `change` sets that part going.
  await page.evaluate(() => document.getElementById('model-chi0')
    .dispatchEvent(new Event('change')));
  await page.waitForFunction(
    () => /完成|Done|未收敛/.test(document.getElementById('model-status').textContent),
    null, { timeout: 180000 });
  //: the page's parts each write their own file, so the button asks which
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-transport-json')]);
  const f = join(OUT, `${got.length}.json`);
  await dl.saveAs(f);
  got.push({ name: c.name, case: c, doc: JSON.parse(readFileSync(f, 'utf8')) });
}
await br.close();

const PY = `
import json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
# ★\`kernel.geo_surface\`, not \`fylite.geo\` (converged at ABI 70).
from fylite import kernel as K

out = []
for d in json.load(sys.stdin):
    c, p = d["case"], d["profile"]
    rho = np.asarray(p["rho"], float)
    n = rho.size
    #: ★the grid is the minor radius in METRES; a is its last point rather
    #: than a control, so this reference reads the same geometry the page ran
    #: on even when the case did not name amin
    a = float(rho[-1])
    x = rho / a
    # the metric, rebuilt from the SAME prescription the page states
    q0, qa = 1.0, c["q95"]
    vp = np.zeros(n); gr2 = np.zeros(n)
    for i in range(1, n):
        r = float(x[i])
        q = q0 + (qa - q0) * r * r
        dq = 2.0 * (qa - q0) * r
        #: metres in, metres out: geo_do is scale-covariant, so a surface
        #: given in metres returns dV/dr in m^2 and a dimensionless
        #: <|grad r|^2>
        g = K.geo_surface(rmin_over_a=float(rho[i]),
                             rmaj_over_a=c["rmaj"] * a, q=q,
                             shear=r * dq / q, kappa=c["kappa"], s_kappa=0.0,
                             delta=c["delta"], s_delta=0.0, ntheta=201)
        vp[i] = g["volume_prime"]; gr2[i] = g["fsa_grad_r2"]
    gr2[0] = gr2[1] if n > 1 else 1.0        # axis: set, not asked
    vp_b = np.asarray(p["volume_prime"], float)
    gr_b = np.asarray(p["fsa_grad_r2"], float)
    m_rel = max(np.max(np.abs(vp - vp_b)) / max(np.max(np.abs(vp)), 1e-30),
                np.max(np.abs(gr2 - gr_b)) / max(np.max(np.abs(gr2)), 1e-30))

    # re-solve on the page's OWN exported metric
    src = c["power"] * np.exp(-(x / c["width"]) ** 2)
    chi0 = c["chi0"]
    # ★the closure is named, not written.  fylite.transport is gone — the
    # solver core is in the kernel — and a Python callable cannot cross the
    # ABI anyway.  It does not need to: the page's stiff closure IS the
    # kernel's "stiff" model, chi0 * (p1 + p2 * g / (1 + g)) with p1 = 0.25,
    # p2 = 1.75, so the reference asks for that model by name instead of
    # rebuilding it here.  A copy of it in this file would be exactly the
    # second implementation D-4' exists to remove.
    # --- the neoclassical tier: check the PAGE's block assembly ----------
    #
    # Not by re-deriving chi here — that would rebuild the NEO normalisation
    # outside the kernel, which is the copy D-4 exists to prevent.  Instead
    # the blocks are rebuilt from the page's own exported CONFIG, handed to
    # the kernel's neo_chi at the page's own exported temperature, and the
    # answer compared with the chi the page exported.  What that tests is
    # exactly the page's share of the work: the unit conversions and the
    # prescribed density profile.
    if int(c["closure"]) == 2:
        from fylite import kernel as rustlib
        import ctypes
        lib = rustlib.load()
        # SI, as the block takes since the conversion moved behind the ABI
        amin = a
        surf = np.zeros((n, 20)); ion = np.zeros((n, 6))
        for k in range(n):
            r = max(float(x[k]), 1e-6)
            q = q0 + (qa - q0) * r * r
            shear = r * (2.0 * (qa - q0) * r) / q
            #: the density peaking is a CONTROL now, not the 0.4 that used
            #: to be written into both hosts
            cpk = float(c.get("nepeak", 0.4))
            ne = c["ne0"] * (1.0 - cpk * r * r) * 1e19
            dlnnedr = (2 * cpk * r / max(1.0 - cpk * r * r, 1e-6)) / amin
            te = (c["edge"] + 2.0 * (1.0 - float(x[k]) ** 2)) * 1e3
            #: ★R0 in METRES.  'rmaj' is the aspect ratio on this page, and
            #: the block takes a major radius — the neoclassical chi came out
            #: 25 % off with the ratio in that slot, converged and smooth.
            surf[k] = [amin, r * amin, c["rmaj"] * amin, 0, 0, 0, q, shear,
                       c["kappa"], 0, c["delta"], 0, 0, 0,
                       c["bunit"], te, ne, dlnnedr, dlnnedr, 0]
            ion[k] = [1.0, 3.3435837724e-27, ne, te, dlnnedr, dlnnedr]
        scal = np.array([-1.0, 1.0, 0.001, 17, 1e3])
        gb = np.asarray(p["chi_gyrobohm"], float)
        chi = np.zeros(n)
        rc = lib.fylite_rs_neo_chi(
            rho, np.asarray(p["t_e"], float), n, surf.ravel(), ion.ravel(), 1,
            scal, gb.ctypes.data_as(ctypes.c_void_p), chi0, chi)
        chi_b = np.asarray(p["chi"], float)
        out.append({"metric_rel": float(m_rel), "neo": True, "rc": int(rc),
                    "chi_rel": float(np.max(np.abs(chi - chi_b))
                                     / max(float(np.max(np.abs(chi_b))), 1e-30)),
                    "chi_lo": float(np.min(chi_b)),
                    "chi_hi": float(np.max(chi_b)),
                    "it_browser": int(p["inner_iterations"]),
                    "t0": float(np.asarray(p["t_e"], float)[0])})
        continue

    y0 = c["edge"] + 2.0 * (1.0 - x ** 2)
    #: velocity is a PROFILE, one value per point — the page fills an array
    #: with the pinch it was given, and a bare scalar here reaches the kernel
    #: as a zero-length array
    r = K.transport_step(rho, y0, vprime=vp_b, metric=vp_b * gr_b,
                         source=src, velocity=np.full(n, c["pinch"]),
                         model=("stiff" if int(c["closure"]) == 1 else "constant"),
                         p0=chi0, p1=0.25, p2=1.75,
                         #: steady state, asked for as one implicit step of
                         #: infinite length rather than by a separate entry
                         dt=float("inf"), theta=1.0,
                         edge_value=c["edge"], tol=1e-10, max_inner=200)
    ry = np.asarray(r["y"], float)
    yb = np.asarray(p["t_e"], float)
    scale = max(float(np.max(np.abs(ry))), 1e-30)
    out.append({"metric_rel": float(m_rel),
                "y_rel": float(np.max(np.abs(ry - yb)) / scale),
                "it_native": int(r["inner_iterations"]),
                "it_browser": int(p["inner_iterations"]),
                "t0": float(ry[0])})
print(json.dumps(out))
`;

const cmp = JSON.parse(execFileSync('python3', ['-c', PY], {
  //: ★the case is read back from the page's OWN export, not from what the
  //: gate asked for.  A range input snaps its value to its step grid, so
  //: `width: 0.35` on a 0.02 grid starting at 0.10 becomes 0.36 — and the
  //: gate then rebuilt the source from a width the page never used, which
  //: read as a 3e-2 disagreement in the profile.  Whatever the page actually
  //: ran with is what the reference must be given.
  input: JSON.stringify(got.map((g) => ({
    case: Object.assign({}, g.case,
      Object.fromEntries(Object.entries(g.doc['fylite:config'])
        .map(([k, v]) => [k, typeof v === 'boolean' ? v : Number(v)]))),
    profile: {
      //: ★the grid is the minor radius in METRES now (the bar used to solve
      //: on r/a with chi in m^2/s, an equation short of a factor a^2), and
      //: the temperature's key names the SPECIES the tier solved — the
      //: neoclassical and turbulent tiers answer with T_i
      rho: g.doc['fylite:profile']['fylite:r_minor'],
      channel: g.doc['fylite:profile']['fylite:channel'],
      t_e: g.doc['fylite:profile']['fylite:temperature'],
      volume_prime: g.doc['fylite:profile']['fylite:volume_prime'],
      fsa_grad_r2: g.doc['fylite:profile']['fylite:fsa_grad_r2'],
      inner_iterations: g.doc['fylite:profile']['fylite:inner_iterations'],
      //: the neoclassical tier exports these two as well; the gyro-Bohm
      //: unit has to travel or the exported chi is a number without a scale
      chi: g.doc['fylite:profile']['fylite:chi'],
      chi_gyrobohm: g.doc['fylite:profile']['fylite:chi_gyrobohm'],
    } }))),
  encoding: 'utf8', maxBuffer: 1 << 27 }));

// The session file truncates to 7 significant digits on purpose, and the
// profile is re-solved FROM those truncated weights — so this band is that
// truncation, not the two solvers.
const TOL = 1e-6;
let bad = errs.length;
if (errs.length) console.log('页面报错：', errs.slice(0, 3).join(' | '));

for (let i = 0; i < cmp.length; i++) {
  const c = cmp[i];
  if (c.neo) {
    //: the same band as the rest — the chi came back through the kernel on
    //: both sides, so the only slack is the session file's 7-digit
    //: truncation.  The spread check is the non-degenerate one: a chi that
    //: was flat, or zero, would agree with itself perfectly.
    const ok = c.rc === 0 && c.metric_rel <= TOL && c.chi_rel <= TOL &&
               c.chi_hi > 1.5 * c.chi_lo && c.chi_lo > 0;
    console.log(`  ${got[i].name.padEnd(6)} 度规 ${c.metric_rel.toExponential(2)}` +
                `  χ 装配 ${c.chi_rel.toExponential(2)}` +
                `  χ ${c.chi_lo.toFixed(4)}–${c.chi_hi.toFixed(4)} m²/s` +
                `  内迭代 ${c.it_browser}` +
                `  T(0) ${c.t0.toFixed(4)}  ${ok ? '✓' : '✗'}`);
    if (!ok) bad += 1;
    continue;
  }
  const ok = c.metric_rel <= TOL && c.y_rel <= TOL &&
             c.it_native === c.it_browser;
  console.log(`  ${got[i].name.padEnd(6)} 度规 ${c.metric_rel.toExponential(2)}` +
              `  剖面 ${c.y_rel.toExponential(2)}` +
              `  内迭代 ${c.it_browser}/${c.it_native}` +
              `  T(0) ${c.t0.toFixed(4)}  ${ok ? '✓' : '✗'}`);
  if (!ok) bad += 1;
}

// The stiff case must actually iterate, or the Picard loop was never entered
// and the two tiers are the same test run twice.
if (!(cmp[1].it_browser > cmp[0].it_browser + 1)) {
  console.log('\n★刚性算例的内迭代次数没有明显多于常数档 —— Picard 环没有被走到。');
  bad += 1;
}

console.log(`\n判定：${bad ? `1.5D 页面与原生不一致（${bad} 项）`
                          : `1.5D 页面与原生一致（度规与剖面 ${TOL.toExponential(0)}，` +
                            `即会话文件有意的 7 位有效截断；内迭代次数亦相同）`}`);
process.exit(bad ? 1 : 0);
