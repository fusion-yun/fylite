// The turbulent closure INSIDE the time march.
//
// ★★The combination a predictive study actually wants — time dependence with
// a turbulent closure — was the one this page could not do: TGLF lived on
// the interactive bar and nowhere else.  Wiring it into the march invites
// three silent failures, and this gate is one check per failure.
//
//   THE CADENCE NEVER FIRES.  TGLF is evaluated every N steps, so a counter
//   kept in the wrong place gives a run that is neoclassical throughout and
//   labelled turbulent.  (It happened: `core_march` calls the closure more
//   than once per step, so a counter kept in the closure fired twice as
//   often as the control said.)  The file carries the evaluation count and
//   this checks it against the arithmetic.
//
//   THE SPLIT DOES NOT ADD UP.  chi = chi_neo + chi_turb is the whole of
//   what this tier is; the file carries all three and they are compared.
//
//   THE TURBULENCE DOES NOTHING.  A closure wired in and always returning
//   zero would pass both checks above.  So the same case is run on the
//   neoclassical tier as well, and the turbulent one must transport MORE
//   and end up COLDER.
//
//   node app/tests/validate-turb-march.mjs [--playwright DIR] [--url BASE]

import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'tb-'));
let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};

//: ★small on purpose: this tier costs about 45 ms per (radius x ky) and the
//: gate is checking WIRING, not convergence.  The cadence and the step count
//: are chosen so the arithmetic below has an exact answer.
const STEPS = 20, EVERY = 5, NRAD = 4, NKY = 4;
const CFG = {
  geometry: 'device', 'ch-heat': true, 'ch-density': false,
  'ch-current': false, nsteps: STEPS, nlev: 21, dt: 0.002, dttarget: 0,
  pe: 1.5, pi: 1.5, dep: 0, depw: 0.35, fuel: 0,
  alpha: false, brem: true, ohmic: false, bootstrap: false, icd: 0,
  zeff: 1.5, species: '', cimp: 0, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0,
  couple: 0, chi0: 0.2, te0: 2, ti0: 2, edgete: 0.3, edgeti: 0.3,
  edgene: 0.5, ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0, ip: 400,
  useref: false, sawtooth: false, wave: false, resume: false,
  turbevery: EVERY, turbnrad: NRAD, turbnky: NKY, turbrelax: 0.5,
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

const set = (cfg) => page.evaluate((c) => {
  Object.keys(c).forEach((id) => {
    const el = document.getElementById('model-evolve-' + id)
               || document.getElementById('model-' + id);
    if (!el) throw new Error('no control ' + id);
    if (el.type === 'checkbox') el.checked = !!c[id];
    else el.value = c[id];
    el.dispatchEvent(new Event(el.tagName === 'SELECT' || el.type === 'checkbox'
                               ? 'change' : 'input'));
  });
}, cfg);
let n = 0;
const runAndGrab = async () => {
  await page.click('#model-evolve-run');
  await page.waitForFunction(
    () => /完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
        .textContent || ''), null, { timeout: 900000 });
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${n++}.json`);
  await dl.saveAs(f);
  return JSON.parse(readFileSync(f, 'utf8'));
};

console.log('一、新经典档（对照）');
await set({ ...CFG, closure: 2 });
const neoDoc = await runAndGrab();
const neoT = neoDoc['fylite:result'].core_profiles.profiles_1d
                   .electrons.temperature;
const neoChi = neoDoc['fylite:result'].core_transport.profiles_1d
                     .total_ion_energy.d;
say(!neoDoc['fylite:result'].core_transport['fylite:turbulence'],
    '新经典档不带湍流记录');
say(neoT[0] > 0, '跑出来了', `T_e(0) = ${(neoT[0] / 1e3).toFixed(3)} keV`);

console.log('\n二、新经典＋湍流档');
await set({ ...CFG, closure: 3 });
const turbDoc = await runAndGrab();
const tres = turbDoc['fylite:result'].core_transport;
const tb = tres['fylite:turbulence'];
const turbT = turbDoc['fylite:result'].core_profiles.profiles_1d
                     .electrons.temperature;
const chiI = tres.profiles_1d.total_ion_energy.d;

say(!!tb, '文件里带着湍流记录');
//: ★the cadence, in the arithmetic the control describes: one evaluation
//: before the first step (nothing to hold yet) and one at every step whose
//: index is a multiple of the cadence
const wantEvals = 1 + Math.ceil(STEPS / EVERY);
say(tb['fylite:evaluations'] === wantEvals,
    'TGLF 求值次数就是节律说的那个数',
    `${tb['fylite:evaluations']} (期望 ${wantEvals} = 1 + ⌈${STEPS}/${EVERY}⌉)`);
say(tb['fylite:radii'] === NRAD && tb['fylite:ky_points'] === NKY,
    '半径数与 ky 点数如实记录',
    `${tb['fylite:radii']} x ${tb['fylite:ky_points']}`);
say(Array.isArray(tb['fylite:evaluated_at_rho'])
    && tb['fylite:evaluated_at_rho'].length === NRAD,
    '记下了 TGLF 到底在哪几个半径上算的',
    (tb['fylite:evaluated_at_rho'] || []).map((v) => v.toFixed(3)).join(' '));

//: ★★THE SPLIT ADDS UP.  This is the whole of what the tier is: the chi the
//: march used is the neoclassical one plus the turbulent one, and a file
//: that carried three arrays which did not satisfy that would be carrying a
//: decomposition of something else.
const cn = tb['fylite:chi_neoclassical'], cturb = tb['fylite:chi_turbulent'];
let worst = 0;
for (let i = 0; i < chiI.length; i++) {
  const want = cn[i] + cturb[i];
  worst = Math.max(worst, Math.abs(chiI[i] - want) / Math.max(want, 1e-30));
}
say(worst < 1e-6, 'χ = χ_neo + χ_turb 逐点成立',
    `最大相对差 ${worst.toExponential(1)}`);

//: ★★AND THE TURBULENCE DOES SOMETHING.  A closure wired in and returning
//: zero would satisfy every check above.
const maxTurb = Math.max(...cturb);
say(maxTurb > 0, '湍流那一份不是零', `max χ_turb = ${maxTurb.toFixed(3)} m^2/s`);
const chiUp = chiI.some((v, i) => v > neoChi[i] * 1.05);
say(chiUp, '湍流档的 χ 高过纯新经典档');
say(turbT[0] < neoT[0],
    '输运多了，芯部就更冷',
    `${(turbT[0] / 1e3).toFixed(3)} < ${(neoT[0] / 1e3).toFixed(3)} keV`);

await br.close();
if (errs.length) { console.log('\n页面报错：'); errs.forEach((e) => console.log('  ' + e)); }
console.log(bad || errs.length ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad || errs.length ? 1 : 0);
