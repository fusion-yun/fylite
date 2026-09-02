// The TOROIDAL MOMENTUM channel — omega against the native march, and the
// E x B shear against the transport it is supposed to suppress.
//
// ★★What this bar could not do before, and why it mattered.  `solve_momentum`
// and `momentum_weights` have been in the C port all along and no browser
// binding reached either, so the page had no rotation — and with no rotation
// there is no E x B shear, which left the turbulent closure's single most
// important suppression mechanism switched off with a hard zero in the deck
// (`VEXB_SHEAR: 0.0`, written as a literal).  A zero that nobody chose reads
// exactly like a zero that somebody measured.
//
// Four things have to hold:
//
//   ①The channel SWITCHES.  Off, the file carries no rotation at all and the
//   readings have no row for it — not a zero, which would say "solved, and
//   it came out at rest".  On, both are there and the plasma is turning.
//
//   ②The rotation is the KERNEL's.  Python re-marches the same channel
//   through `assembly.solve_momentum` from what the file carries — the
//   metric, the density, the <R^2> the capacity ran on, the torque density,
//   the Prandtl number and chi_i — and the two must agree pointwise.  That
//   is an oracle outside the path under test: a different host, a different
//   binding, the same kernel entry.
//
//   ③The TORQUE is a torque.  The deposition is normalised by the volume
//   integral, so the slider is newton-metres; Python integrates the exported
//   density against the exported metric and must get the slider back.  A
//   profile shaped right and scaled wrong would pass every comparison in ②.
//
//   ⑤<R^2> IS THE KERNEL'S COLUMN (T-M8).  The capacity of the momentum
//   equation is `V' n m <R^2>`, and this channel used to substitute the
//   surface's own `R_maj(rho)^2` because the metric ladder had no such
//   column.  Two assertions, and they are the closure criteria: the file's
//   `fylite:r2` must BE `geo_surface`'s `<R^2>` on the same surfaces
//   (pointwise), and putting `R_maj^2` back must visibly move the rotation
//   — a column nobody's answer depends on would satisfy the first alone.
//
//   ④The SHEAR REACHES TGLF, and the only way to see that from outside is
//   the transport it changes: the same run with and without a torque must
//   NOT be identical, and the rotating one must be the less transported.
//   This is the assertion that would have caught the bug this batch found —
//   the closure is called by `core_march` with the march's own state, which
//   has no omega in it, so reading the rotation from there gave every deck a
//   zero shear on a plasma at Mach 0.4 and the two runs came back bit for
//   bit the same.
//
//   node app/tests/validate-momentum.mjs [--playwright DIR] [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'mom-'));

//: ★Miller geometry and the CONSTANT closure for the two cases the native
//: re-march compares against: chi_phi is Pr x chi_i, so a closure whose chi_i
//: moves with the state would make the reference a second evaluation of that
//: closure at a slightly different state rather than the same channel.  The
//: turbulent pair below is a different question and runs on its own cases.
const BASE_CASE = {
  geometry: 'miller', 'ch-heat': true, 'ch-density': false,
  'ch-current': false, nsteps: 20, nlev: 21, dt: 0.002, dttarget: 0,
  pe: 3, pi: 3, dep: 0, depw: 0.3, fuel: 0, alpha: false, brem: false,
  ohmic: false, bootstrap: false, icd: 0, zeff: 1.5, chiratio: 1,
  dchi: 0.3, pinch: 0, dpc: 0, couple: 0, closure: 0, chi0: 1.0,
  te0: 3, ti0: 2.5, edgete: 0.3, edgeti: 0.3, edgene: 0.5, ne0: 5,
  peakt: 1.5, peakn: 0.5, vloop: 0, ip: 400, species: '', cimp: 0,
  sawtooth: false, wave: false, couplefixed: false,
  'ch-momentum': false, torque: 0, prandtl: 1,
};

//: ★★the turbulent pair, and everything about it is chosen so the ONLY
//: difference is the torque: the same closure, the same cadence, the same
//: subset of radii, the same ky grid, the same number of steps.  A pair that
//: differed in anything else would be comparing two runs rather than one run
//: with and without rotation.
const TURB = {
  ...BASE_CASE, closure: 3, nsteps: 20, dt: 0.001, chi0: 0.5,
  turbevery: 2, turbnrad: 5, turbnky: 5, turbrelax: 0.5,
  'ch-momentum': true, prandtl: 1,
};

const CASES = [
  { name: '动量道关', c: { ...BASE_CASE } },
  { name: '动量道开 · 力矩 4 N·m', c: { ...BASE_CASE, 'ch-momentum': true,
                                        torque: 4, prandtl: 1 } },
  { name: '动量道开 · 力矩 4 N·m · Pr 0.5',
    c: { ...BASE_CASE, 'ch-momentum': true, torque: 4, prandtl: 0.5 } },
  { name: '湍流 · 不加转动', c: { ...TURB, torque: 0 }, turb: true },
  { name: '湍流 · 加转动 10 N·m', c: { ...TURB, torque: 10 }, turb: true },
];

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
//: ★factory defaults, not the bars' initial cases: this gate builds its own
//: configuration, so anything it does not set itself has to be the DEFAULT
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

await page.goto(BASE + 'pages/model.html?device=east',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /就绪|Ready|完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 180000 });

const got = [];
for (const k of CASES) {
  await page.evaluate((cfg) => {
    //: ★the checkbox goes LAST for the same reason the refinement's does:
    //: a panel that is only shown once the channel is on must be on before
    //: the sliders inside it are touched
    const late = (id) => (id === 'ch-momentum' ? -1 : 0);
    Object.keys(cfg).sort((a, b) => late(a) - late(b)).forEach((id) => {
      const el = document.getElementById('model-evolve-' + id)
                 || document.getElementById('model-' + id);
      if (!el) throw new Error('no control evolve-' + id);
      if (el.type === 'checkbox') el.checked = !!cfg[id];
      else el.value = cfg[id];
      el.dispatchEvent(new Event(
        el.tagName === 'SELECT' || el.type === 'checkbox' ? 'change' : 'input'));
    });
  }, k.c);
  await page.click('#model-evolve-run');
  await page.waitForFunction(
    () => /完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
        .textContent || ''), null, { timeout: 900000 });
  const rows = await page.evaluate(
    () => (document.getElementById('model-evolve-scalars') || {}).innerText || '');
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${got.length}.json`);
  await dl.saveAs(f);
  got.push({ name: k.name, c: k.c, turb: !!k.turb, rows,
             doc: JSON.parse(readFileSync(f, 'utf8')) });
}
//: ★the Miller surfaces the page built, read from the controls that built
//: them — so the oracle below runs `geo_surface` on the SAME geometry
//: rather than on a geometry this file decided on.  `evMillerMetric`'s own
//: rules travel with it: q0 = 1, the label is the minor radius, 201 theta.
const geom = await page.evaluate(() => {
  const g = (id) => +(document.getElementById('model-evolve-' + id)
                      || document.getElementById('model-' + id)).value;
  return { a: g('amin'), rmajOverA: g('rmaj'), kappa: g('kappa'),
           delta: g('delta'), q95: g('q95'), n: g('nlev') };
});
await br.close();

const PY = `
import json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
from fylite import fyo as FYO
from fylite import kernel as K
from fylite.scenario.model import assembly as asm

out = []
for d in json.load(sys.stdin):
    c = d["case"]
    res = d["doc"]["fylite:result"]
    eq, cp, ct = res["equilibrium"], res["core_profiles"], res["core_transport"]

    def arr(doc, table, key, default=None):
        v = FYO.get(doc, table, key, default)
        return None if v is None else np.asarray(v, float)

    rec = {"name": d["name"], "has_omega": "fylite:omega_tor" in cp,
           "omega_rel": None, "torque_total": None, "chi": None,
           "te_axis": float(arr(cp, "CORE_PROFILES", "te")[0]),
           "steps": None}
    chi = arr(ct, "CORE_TRANSPORT", "chi_i")
    rec["chi"] = [float(v) for v in chi]
    if not rec["has_omega"]:
        out.append(rec)
        continue

    rho = arr(eq, "LADDER", "rho")
    vp = arr(eq, "LADDER", "vprime")
    gm3 = arr(eq, "LADDER", "gm3")
    ne = arr(cp, "CORE_PROFILES", "ne")
    ni = arr(cp, "CORE_PROFILES", "ni")
    ni = ne if ni is None else ni
    omega = np.asarray(cp["fylite:omega_tor"], float)
    torque = np.asarray(cp["fylite:torque_density"], float)
    r2 = np.asarray(cp["fylite:r2"], float)
    pr = float(cp["fylite:momentum_prandtl"])
    edge = float(cp["fylite:omega_edge"])

    #: ③the slider is newton-metres: the density integrated over the volume
    rec["torque_total"] = float(np.trapezoid(torque * vp, rho))

    #: ②the same channel, re-marched here.  Deuterium, the mass the page
    #: sends; the constant closure makes chi_i a constant in time, so
    #: chi_phi = Pr chi_i is the same profile at every step and the
    #: reference is the same equation rather than a second evaluation of a
    #: closure at a slightly different state.
    MD = 3.343583772e-27
    w = np.zeros_like(rho)
    nsteps = int(c["nsteps"])
    rec["steps"] = nsteps
    for _ in range(nsteps):
        w = asm.solve_momentum(
            rho, w, vprime=vp, gm3=gm3, r2=r2, ni=ni, mass=MD,
            chi_phi=pr * chi, torque=torque, dt=float(c["dt"]), edge=edge,
            max_outer=1, tol_steady=0.0, d_pc=float(c["dpc"]),
            tol=1e-10, max_inner=60)["omega"]
    scale = max(float(np.max(np.abs(omega))), 1e-30)
    rec["omega_rel"] = float(np.max(np.abs(w - omega)) / scale)

    #: ⑤<R^2>, rebuilt HERE from \`kernel.geo_surface\` on the same Miller
    #: surfaces the page built — a different host, a different binding, the
    #: same kernel entry, and nothing of the page's own arithmetic in
    #: between.  \`evMillerMetric\`'s rules are restated rather than
    #: imported: the label is the minor radius, q0 = 1, the shear is the
    #: analytic one that q profile implies, 201 theta.
    gm = d["geom"]
    rmaj2 = np.asarray(cp["fylite:rmaj2"], float)
    a_min, r0 = float(gm["a"]), float(gm["rmajOverA"]) * float(gm["a"])
    nlev, q95 = max(5, int(gm["n"])), float(gm["q95"])
    want = np.zeros(nlev)
    for i in range(1, nlev):
        x = i / (nlev - 1)
        qi = 1.0 + (q95 - 1.0) * x * x
        want[i] = K.geo_surface(
            rmin_over_a=a_min * x, rmaj_over_a=r0, q=qi,
            shear=(x * (2.0 * (q95 - 1.0) * x) / qi) if qi != 0 else 0.0,
            kappa=float(gm["kappa"]), s_kappa=0.0,
            delta=float(gm["delta"]), s_delta=0.0, ntheta=201)["fsa_r2"]
    #: the axis node is the innermost traced value repeated — the ladder's
    #: own rule for a surface that degenerates, applied on both sides
    want[0] = want[1]
    rec["r2_n"] = int(r2.size)
    rec["r2_rel"] = float(np.max(np.abs(r2 - want) / np.abs(want)))
    #: how far the substitution this replaces actually was, at the edge and
    #: at its worst — reported, so "O((a/R)^2)" is a number here too
    rec["r2_over_rmaj2_edge"] = float(r2[-1] / rmaj2[-1] - 1.0)
    rec["r2_over_rmaj2_max"] = float(np.max(np.abs(r2 / rmaj2 - 1.0)))

    #: ★and the substitution PUT BACK: the same march, the same everything,
    #: with R_maj^2 in the capacity.  A column the answer does not depend on
    #: would come back identical and would not be worth carrying.
    w2 = np.zeros_like(rho)
    for _ in range(nsteps):
        w2 = asm.solve_momentum(
            rho, w2, vprime=vp, gm3=gm3, r2=rmaj2, ni=ni, mass=MD,
            chi_phi=pr * chi, torque=torque, dt=float(c["dt"]), edge=edge,
            max_outer=1, tol_steady=0.0, d_pc=float(c["dpc"]),
            tol=1e-10, max_inner=60)["omega"]
    rec["omega_sub_rel"] = float(np.max(np.abs(w2 - omega)) / scale)
    rec["omega_sub_axis"] = float(w2[0])
    rec["omega_axis"] = float(omega[0])
    rec["omega_native_axis"] = float(w[0])
    #: ★non-degenerate: a channel that solved a rotation of zero would
    #: satisfy the comparison above exactly and mean nothing
    rec["omega_span"] = float(np.max(omega) - np.min(omega))
    out.append(rec)
print(json.dumps(out))
`;

const ref = JSON.parse(execFileSync('python3', ['-c', PY], {
  input: JSON.stringify(got.map(g => ({ name: g.name, case: g.c, doc: g.doc,
                                       geom }))),
  encoding: 'utf8', maxBuffer: 1 << 28 }));

let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};

console.log('一、通道开得了也关得掉');
say(!ref[0].has_omega, '关着的时候文件里没有转动',
    'core_profiles 无 fylite:omega_tor');
say(!/ω/.test(got[0].rows), '关着的时候读数里也没有那一行');
say(ref[1].has_omega, '开着的时候有');
say(/ω/.test(got[1].rows), '读数里也有');

console.log('\n二、ω_φ 与原生逐个格点');
[1, 2].forEach((i) => {
  const r = ref[i];
  //: ★the tolerance and its source: the ladder and the density travel in
  //: the session file at 7 significant digits, so the two sides march the
  //: same equation with coefficients that differ in the 7th digit.  The
  //: momentum equation is LINEAR in omega at fixed coefficients, so that
  //: difference does not amplify over the march — it stays at the rounding.
  //: 1e-6 is an order above it and orders below anything a wiring mistake
  //: (a mass, a metric, a missing 2 pi) would move.
  say(r.omega_rel < 1e-6, `${r.name}：与原生 march 逐点`,
      `相对 ${r.omega_rel.toExponential(2)}（${r.steps} 步）`);
  //: not the trivial fixed point
  say(Math.abs(r.omega_axis) > 1e3 && r.omega_span > 1e3,
      `${r.name}：解出来的是转动，不是零`,
      `ω(0) ${(r.omega_axis / 1e3).toFixed(2)} krad/s · 跨度 `
      + `${(r.omega_span / 1e3).toFixed(2)}`);
});
//: ★the Prandtl number is a MODEL, not a decoration: half the momentum
//: diffusivity has to leave more rotation behind
say(Math.abs(ref[2].omega_axis) > Math.abs(ref[1].omega_axis),
    '普朗特数减半，转得更快（χ_φ 是规定的，而且真的用上了）',
    `Pr 1 → ${(ref[1].omega_axis / 1e3).toFixed(2)} · Pr 0.5 → `
    + `${(ref[2].omega_axis / 1e3).toFixed(2)} krad/s`);

console.log('\n三、滑块上的那个数就是牛顿米');
[1, 2].forEach((i) => {
  const want = +CASES[i].c.torque;
  const rel = Math.abs(ref[i].torque_total - want) / want;
  //: the deposition is normalised by a trapezoid over the same metric this
  //: integral uses, so what is left is the file's 7-digit rounding
  say(rel < 1e-5, `${ref[i].name}：力矩密度的体积分回到滑块`,
      `${ref[i].torque_total.toFixed(4)} 对 ${want} N·m`);
});

console.log('\n四、E×B 剪切确实进了 TGLF');
{
  const A = ref[3], B = ref[4];       // no torque / torque
  const chiA = A.chi, chiB = B.chi;
  const same = chiA.every((v, k) => v === chiB[k]);
  //: ★★the assertion that would have caught this batch's own bug: with the
  //: rotation read from the wrong state the deck kept its literal zero and
  //: the two runs came back BIT FOR BIT identical at Mach 0.4.
  say(!same, '加了转动之后湍流通道不再是同一个答案');
  const mean = (v) => v.reduce((a, b) => a + b, 0) / v.length;
  say(mean(chiB) < mean(chiA), '加转动 → χ 下降',
      `⟨χ_i⟩ ${mean(chiA).toFixed(4)} → ${mean(chiB).toFixed(4)} m²/s`);
  //: and the temperature follows, which is the only thing a reader sees
  say(B.te_axis > A.te_axis, '芯部因此更热',
      `T_e(0) ${(A.te_axis / 1e3).toFixed(3)} → `
      + `${(B.te_axis / 1e3).toFixed(3)} keV`);
  say(B.has_omega && Math.abs(B.omega_axis) > 1e4,
      '而且那一路真的在转', `ω(0) ${(B.omega_axis / 1e3).toFixed(1)} krad/s`);
}

console.log('\n五、⟨R²⟩ 用的就是内核那一列');
{
  //: ★the tolerance and its source: the session file writes this column at
  //: 12 significant digits, so the two sides are comparing numbers that
  //: differ at 1e-12 by construction.  1e-6 is six orders above that and
  //: orders below anything a wrong weight (a contour mean instead of the
  //: volume average), a wrong surface or a wrong unit would move.
  const R2TOL = 1e-6;
  [1, 2].forEach((i) => {
    const r = ref[i];
    say(r.r2_rel < R2TOL, `${r.name}：⟨R²⟩ 与 geo_surface 逐点`,
        `相对 ${r.r2_rel.toExponential(2)}（${r.r2_n} 个格点，容差 `
        + `${R2TOL.toExponential(0)}）`);
    //: ★not a rename of R_maj^2: the column has to DIFFER from the thing it
    //: replaced, or every comparison above is satisfied by the old code
    say(r.r2_over_rmaj2_max > 0.01,
        `${r.name}：⟨R²⟩ 不是 R_maj² 换了个名字`,
        `边界 ${(100 * r.r2_over_rmaj2_edge).toFixed(2)} % · 最大 `
        + `${(100 * r.r2_over_rmaj2_max).toFixed(2)} %`);
    //: ★★and the closure criterion's other half: put R_maj^2 back and the
    //: answer moves.  A column that changed nothing would pass the
    //: pointwise test above and still not be worth a kernel entry.
    say(r.omega_sub_rel > 1e-3,
        `${r.name}：换回 R_maj² 结果确实变`,
        `ω 逐点相对 ${r.omega_sub_rel.toExponential(2)}（ω(0) `
        + `${(r.omega_axis / 1e3).toFixed(2)} → `
        + `${(r.omega_sub_axis / 1e3).toFixed(2)} krad/s）`);
  });
}

console.log('\n六、页面没有报错');
say(errs.length === 0, '无 pageerror / console.error',
    errs.slice(0, 2).join(' | '));

console.log(bad ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad ? 1 : 0);
