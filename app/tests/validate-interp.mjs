// The interpretive bar — by ROUND TRIP against a chi this page itself chose.
//
// ★★Why a round trip and not a comparison with a table.  An interpretive
// inversion has no reference answer in general: what a real machine's
// profiles imply is whatever they imply.  But a profile this page MADE with
// a constant chi0 has a known answer, and the kernel states it exactly —
// the flux uses gm7 and the conduction law gm3, so a profile produced by a
// chi0 conduction solve inverts to `chi0 / gm7`, not to chi0.  That factor
// is the one thing an implementation gets wrong silently, and it is what
// this gate measures.
//
// The chain is the reader's own, end to end:
//
//   1. march to a steady state with a constant chi0 (heat channel only,
//      symmetric between the species so the exchange term vanishes);
//   2. write those profiles out as a reference CSV and IMPORT them, through
//      the same file path a published table takes;
//   3. invert them on the same metric with the same sources;
//   4. require chi_interp * gm7 == chi0 wherever the gradient is above the
//      kernel's floor.
//
// ★And the refusals, which are half of what this bar is: a table that does
// not span the metric must be REFUSED rather than extrapolated, and the
// flat region near the axis must come back as no answer rather than as a
// large one.
//
//   node app/tests/validate-interp.mjs [--playwright DIR] [--url BASE]

import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'ip-'));
let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};

//: ★symmetric between the species ON PURPOSE: the march couples the heat
//: pair through the collisional exchange and the inversion has no such
//: term, so a case with T_e != T_i would be comparing two different
//: equations.  Equal powers, equal chi, equal boundaries — the exchange is
//: then identically zero and the two agree or the wiring is wrong.
const CHI0 = 1.0;
const MARCH = {
  geometry: 'miller', 'ch-heat': true, 'ch-density': false,
  'ch-current': false, nsteps: 400, nlev: 31, dt: 0.005, dttarget: 0,
  pe: 3, pi: 3, dep: 0, depw: 0.35, fuel: 0,
  alpha: false, brem: false, ohmic: false, bootstrap: false, icd: 0,
  zeff: 1.5, species: '', cimp: 0, chiratio: 1, dchi: 0.3, pinch: 0,
  dpc: 0, couple: 0, closure: 0, chi0: CHI0,
  te0: 3, ti0: 3, edgete: 0.3, edgeti: 0.3, edgene: 0.5, ne0: 5,
  peakt: 1.5, peakn: 0.5, vloop: 0, ip: 400, useref: false, sawtooth: false,
  amin: 0.6, rmaj: 3.0, kappa: 1.6, delta: 0.3, q95: 3.5, bunit: 2.0,
};

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
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

const setAll = async (bar, cfg) => page.evaluate(([b, c]) => {
  Object.keys(c).forEach((id) => {
    const el = document.getElementById(`model-${b}-${id}`)
               || document.getElementById('model-' + id);
    if (!el) throw new Error(`no control ${b}-${id}`);
    if (el.type === 'checkbox') el.checked = !!c[id];
    else el.value = c[id];
    el.dispatchEvent(new Event(el.tagName === 'SELECT' || el.type === 'checkbox'
                               ? 'change' : 'input'));
  });
}, [bar, cfg]);

const waitBar = (id) => page.waitForFunction(
  (b) => /完成|Done|失败|Failed/i.test(
    (document.querySelector(`[data-bar="${b}"] .funcbar-state`) || {})
      .textContent || ''), id, { timeout: 900000 });

// --- 1. the march ----------------------------------------------------------

console.log('一、造一条已知 χ₀ 的剖面');
await setAll('evolve', MARCH);
await page.click('#model-evolve-run');
await waitBar('evolve');
await page.click('#model-ioexport');
const [dl] = await Promise.all([page.waitForEvent('download'),
                                page.click('#model-iofmt-evolve-json')]);
const marchFile = join(OUT, 'march.json');
await dl.saveAs(marchFile);
const march = JSON.parse(readFileSync(marchFile, 'utf8'));
const mres = march['fylite:result'];
const rho = mres.equilibrium.time_slice[0].profiles_1d.rho_tor;
const te = mres.core_profiles.profiles_1d.electrons.temperature;
const ti = mres.core_profiles.profiles_1d.t_i_average;
const ne = mres.core_profiles.profiles_1d.electrons.density;
const trace = mres.summary;
const dw = trace.global_quantities.denergy_thermal_dt.value;
const wth = trace.global_quantities.energy_thermal.value;
const rel = Math.abs(dw[dw.length - 1]) / Math.max(wth[wth.length - 1], 1e-30);
//: ★the inversion has NO dW/dt term, so the profile it is handed must be a
//: steady one — otherwise the mismatch it reports is the march still moving
say(rel < 1e-2, '推进已接近定态（反演里没有 dW/dt 这一项）',
    `|dW/dt|/W = ${rel.toExponential(2)} 1/s`);
say(Math.abs(te[0] - ti[0]) / te[0] < 1e-6,
    '两条热道对称，交换项恒为零',
    `T_e(0) ${(te[0] / 1e3).toFixed(4)} / T_i(0) ${(ti[0] / 1e3).toFixed(4)} keV`);

// --- 2. those profiles, back in through the file path -----------------------

console.log('\n二、写成参考剖面 CSV 再导入');
const csv = ['rho,TE,TI,NE'].concat(rho.map((r, i) =>
  `${r},${te[i] / 1e3},${ti[i] / 1e3},${ne[i] / 1e19}`)).join('\n');
const [ch1] = await Promise.all([page.waitForEvent('filechooser'),
                                 page.click('#model-ioimport')]);
await ch1.setFiles({ name: 'roundtrip.csv', mimeType: 'text/csv',
                     buffer: Buffer.from(csv) });
await page.waitForTimeout(800);
const imported = await page.evaluate(() =>
  (document.getElementById('model-status') || {}).textContent || '');
say(/roundtrip\.csv/.test(imported), '导入成功', imported.slice(0, 70));

// --- 3. the inversion, on the same metric ----------------------------------

console.log('\n三、在同一套度规上反演');
await setAll('interp', {
  geometry: 'miller', nlev: MARCH.nlev, gradfloor: 0.001, ip: MARCH.ip,
  pe: MARCH.pe, pi: MARCH.pi, dep: MARCH.dep, depw: MARCH.depw,
  vloop: 0, alpha: false, brem: false, species: '', cimp: 0,
  zeff: MARCH.zeff, dtfrac: 0.5,
});
await page.click('#model-interp-run');
await waitBar('interp');
await page.click('#model-ioexport');
const [dl2] = await Promise.all([page.waitForEvent('download'),
                                 page.click('#model-iofmt-interp-json')]);
const invFile = join(OUT, 'interp.json');
await dl2.saveAs(invFile);
const inv = JSON.parse(readFileSync(invFile, 'utf8'));
const ires = inv['fylite:result'];
const gm7 = ires.equilibrium.time_slice[0].profiles_1d.gm7;
const chiE = ires.core_transport.profiles_1d.electrons.energy.d;
const chiI = ires.core_transport.profiles_1d.total_ion_energy.d;
const validE = ires.core_transport['fylite:valid_e'];

say(Array.isArray(gm7) && gm7.every((v) => v > 0),
    '度规带着 gm7 一起出来了', `${gm7.length} 点`);

//: ★★THE FACTOR.  chi_interp * gm7 must be chi0 — that gm7 is the whole of
//: what an implementation gets wrong here, and getting it wrong produces a
//: chi that is smooth, positive and about 15 % off.
//: ★THE INTERIOR, and the bounds are the measured ones rather than round
//: numbers.  Two regions are ill-conditioned for reasons that are
//: discretisation rather than wiring, and the bar's caveat states both:
//:
//:   near the AXIS, V' goes to zero and the flux is the ratio of two small
//:   numbers — on this 31-point grid rho/a = 0.03 is 50 % high, 0.07 is
//:   6.8 %, 0.10 is 2.6 %, and by 0.15 it is under 1 %;
//:   at the BOUNDARY, the last two nodes carry a one-sided difference —
//:   0.97 is 17 % low and the edge node 110 % high.
//:
//: Between them the round trip recovers chi0 to well under a per cent, and
//: THAT is the factor this gate exists to measure.
const errsChi = [];
for (let i = 0; i < chiE.length; i++) {
  const x = rho[i] / rho[rho.length - 1];
  if (x < 0.15 || x > 0.93) continue;
  if (!validE[i] || chiE[i] === null) continue;
  errsChi.push(Math.abs(chiE[i] * gm7[i] - CHI0) / CHI0);
}
const worst = errsChi.length ? Math.max(...errsChi) : NaN;
if (process.env.FY_DUMP)
  chiE.forEach((v, i) => console.log('   ', i,
    (rho[i] || 0).toFixed(4), 'gm7', (gm7[i] || 0).toFixed(4),
    'chi', v === null ? 'null' : v.toFixed(4),
    'chi*gm7', v === null ? '—' : (v * gm7[i]).toFixed(4)));
say(errsChi.length > 5, '有足够多的有效点可判',
    `${errsChi.length}/${chiE.length}`);
//: 3 % is the finite-difference of a 31-point grid plus the residual dW/dt,
//: and it is two orders below the 1/gm7 factor this is really guarding
say(worst < 0.02, 'χ·gm7 把 χ₀ 找了回来（0.15 ≤ ρ/a ≤ 0.93）',
    `最大相对差 ${(100 * worst).toFixed(2)} %  (χ₀ = ${CHI0})`);
//: ★and the average must NOT be the one the end nodes bias: it is taken
//: over the interior, the readings say so, and the count travels in the file
const glob = ires['fylite:global'];
say(glob['fylite:valid_points'] === validE.filter(Boolean).length,
    '文件里的有效点数与标记一致', String(glob['fylite:valid_points']));
say(Math.abs(glob['fylite:chi_e_average'] * gm7[Math.floor(gm7.length / 2)]
             - CHI0) / CHI0 < 0.05,
    '平均值也在 χ₀ 附近（两端未污染它）',
    `⟨chi⟩ ${glob['fylite:chi_e_average'].toFixed(4)} m^2/s`);
const sameChannels = chiE.every((v, i) =>
  v === null || chiI[i] === null || Math.abs(v - chiI[i]) <= 1e-6 * Math.abs(v));
say(sameChannels, '对称输入下两条道反出同一个 χ');

//: ★the axis end must be a REFUSAL, not a large number: the gradient there
//: is below the floor by construction
say(validE[0] === false && chiE[0] === null,
    '轴上梯度低于地板，回来的是「没有答案」而不是一个大数',
    `valid=${validE[0]} chi=${chiE[0]}`);

// --- 4. what it must refuse ------------------------------------------------

console.log('\n四、够不着的表要拒绝');
//: a table that stops at half radius cannot be inverted on a metric that
//: reaches the edge — and filling it in would be inventing the profile
const half = ['rho,TE,TI,NE'].concat(
  rho.filter((r) => r <= rho[rho.length - 1] * 0.5)
     .map((r, i) => `${r},${te[i] / 1e3},${ti[i] / 1e3},${ne[i] / 1e19}`)).join('\n');
const [ch2] = await Promise.all([page.waitForEvent('filechooser'),
                                 page.click('#model-ioimport')]);
await ch2.setFiles({ name: 'half.csv', mimeType: 'text/csv',
                     buffer: Buffer.from(half) });
await page.waitForTimeout(800);
await page.click('#model-interp-run');
await page.waitForTimeout(3000);
const st = await page.evaluate(() =>
  (document.querySelector('[data-bar="interp"] .funcbar-state') || {})
    .textContent || '');
say(/不外推|No extrapolation|覆盖|covers/.test(st),
    '半径盖不住就拒绝，并说清差在哪里', st.replace(/\s+/g, ' ').slice(0, 90));

await br.close();
if (errs.length) { console.log('\n页面报错：'); errs.forEach((e) => console.log('  ' + e)); }
console.log(bad || errs.length ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad || errs.length ? 1 : 0);
