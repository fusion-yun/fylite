// The actuators in time, and continuing a march.
//
// ★★Two things this bar could not do until now, and one silent failure each
// invites.
//
//   A WAVEFORM.  The powers and the loop voltage were constants for the whole
//   march, so what the bar modelled was one SEGMENT of a discharge.  The
//   shape is the kernel's trapezoid, and the failure to guard against is a
//   second spelling of it: a page that wrote its own would agree with the
//   kernel on the flat-top and disagree on the corners, which is exactly
//   where a ramp is a ramp.  So the trace's own P_aux is compared against
//   `kernel.zerod_waveform` point by point.
//
//   CONTINUING.  A continued march must start from the state the previous
//   one ended on and must carry the CLOCK with it — a segment that restarted
//   the clock would replay the ramp-up it was meant to follow, and every
//   number in it would look perfectly reasonable.
//
// ★And the refusal: continuing onto a different grid is refused rather than
// interpolated, because a smoothing step slipped between two halves of one
// march is a third problem.
//
//   node app/tests/validate-waveform.mjs [--playwright DIR] [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'wf-'));
let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};

const WAVE = { ramp: 0.2, flat: 0.4, end: 0.5, start: 0.1, end2: 0.1 };
const PE = 3, PI = 3;
const BASECFG = {
  geometry: 'miller', 'ch-heat': true, 'ch-density': false,
  'ch-current': false, nsteps: 200, nlev: 31, dt: 0.005, dttarget: 0,
  pe: PE, pi: PI, dep: 0, depw: 0.35, fuel: 0,
  alpha: false, brem: true, ohmic: false, bootstrap: false, icd: 0,
  zeff: 1.5, species: '', cimp: 0, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0,
  couple: 0, closure: 0, chi0: 1.0, te0: 1, ti0: 1, edgete: 0.3,
  edgeti: 0.3, edgene: 0.5, ne0: 5, peakt: 1.5, peakn: 0.5, vloop: 0,
  ip: 400, useref: false, sawtooth: false, resume: false,
  amin: 0.6, rmaj: 3.0, kappa: 1.6, delta: 0.3, q95: 3.5, bunit: 2.0,
  waveramp: WAVE.ramp, waveflat: WAVE.flat, waveend: WAVE.end,
  wavestart: WAVE.start, waveend2: WAVE.end2,
  wavepower: true, wavevloop: false, wavefuel: false,
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
const wait = () => page.waitForFunction(
  () => /完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 900000 });
const state = () => page.evaluate(() =>
  (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
    .textContent || '');
let n = 0;
const grab = async () => {
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${n++}.json`);
  await dl.saveAs(f);
  return JSON.parse(readFileSync(f, 'utf8'));
};
const summary = (doc) => doc['fylite:result'].summary;

// --- 1. the waveform off ---------------------------------------------------

console.log('一、关掉波形 = 原来那次运行');
await set({ ...BASECFG, wave: false });
await page.click('#model-evolve-run');
await wait();
const flatDoc = await grab();
const flatAux = summary(flatDoc).heating_current_drive.power_additional.value;
say(flatAux.every((v) => Math.abs(v - (PE + PI) * 1e6) < 1),
    'P_aux 全程等于滑块上的兆瓦',
    `${(flatAux[0] / 1e6).toFixed(3)} … ${(flatAux[flatAux.length - 1] / 1e6).toFixed(3)} MW`);

// --- 2. the waveform on ----------------------------------------------------

console.log('\n二、打开波形，逐点对内核的梯形');
await set({ ...BASECFG, wave: true });
await page.click('#model-evolve-run');
await wait();
const waveDoc = await grab();
const wsum = summary(waveDoc);
const t = wsum.time;
const aux = wsum.heating_current_drive.power_additional.value;
say(t[t.length - 1] > WAVE.flat,
    '这一段跨过了平顶的末端（否则波形没有被检验）',
    `t_end ${t[t.length - 1].toFixed(3)} s`);

const PY = `
import json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
from fylite import kernel as K
d = json.load(sys.stdin)
#: ★the page evaluates the waveform at the time the step STARTS from, and
#: the trace stamps the time it reached — so the sample compared here is the
#: previous entry's time, with 0 for the first step.
t = np.asarray(d["t"], float)
t0 = np.concatenate([[d["t_start"]], t[:-1]])
w = K.zerod_waveform((0.0, ${WAVE.ramp}, ${WAVE.flat}, ${WAVE.end}), t0,
                     "trapezoid", flat=1.0, start=${WAVE.start},
                     end=${WAVE.end2})
want = w * ${(PE + PI)} * 1e6
got = np.asarray(d["aux"], float)
rel = np.max(np.abs(got - want) / max(np.max(want), 1e-30))
print(json.dumps({"rel": float(rel), "wmin": float(w.min()),
                  "wmax": float(w.max())}))
`;
const cmp = JSON.parse(execFileSync('python3', ['-c', PY], {
  input: JSON.stringify({ t, aux, t_start: 0 }), encoding: 'utf8' }));
//: 1e-6 is the session file's own 7-significant-digit rounding, three
//: orders below anything the corner of a trapezoid moves
say(cmp.rel < 1e-6, 'P_aux 逐点就是内核那条梯形',
    `最大相对差 ${cmp.rel.toExponential(1)}`);
say(cmp.wmin < 0.5 && cmp.wmax > 0.99,
    '这一段确实走过了升/平/降', `份额 ${cmp.wmin.toFixed(2)}–${cmp.wmax.toFixed(2)}`);

// --- 3. continuing ---------------------------------------------------------

console.log('\n三、续跑');
const endT = t[t.length - 1];
const cp = waveDoc['fylite:result'].core_profiles.profiles_1d;
const teEnd = cp.electrons.temperature;
await set({ resume: true });
await page.click('#model-evolve-run');
await wait();
const contDoc = await grab();
const csum = summary(contDoc);
const ct = csum.time;
//: ★the file carries the WHOLE discharge, so the second segment starts at
//: index `t.length` — and that is the entry the clock has to have advanced
say(ct[t.length] > endT, '时钟接着走，没有回到 0',
    `${endT.toFixed(3)} → ${ct[t.length].toFixed(3)} s`);
//: ★the whole discharge is in the file, not only the second segment
say(ct.length > t.length, '文件里是整条放电，不只是第二段',
    `${t.length} + ? = ${ct.length} 点`);
say(Math.abs(ct[t.length - 1] - endT) < 1e-9,
    '两段在接缝处严丝合缝', `t[${t.length - 1}] = ${ct[t.length - 1].toFixed(6)} s`);
const teStart = csum.local.magnetic_axis.t_e.value[t.length];
//: the first continued step has already moved, so this is a closeness check
//: rather than an equality one — what it rules out is a restart from the
//: prescribed parabola, which at these settings is 1 keV
say(Math.abs(teStart - teEnd[0]) / teEnd[0] < 0.1,
    '第二段从上一段的终态起步，而不是从解析剖面',
    `${(teEnd[0] / 1e3).toFixed(3)} → ${(teStart / 1e3).toFixed(3)} keV（解析起点是 1.000）`);

// --- 4. the refusal --------------------------------------------------------

console.log('\n四、换了网格就拒绝');
await set({ resume: true, nlev: 21 });
await page.click('#model-evolve-run');
await wait();
const st = await state();
say(/网格|grid/.test(st) && /拒绝|Refused|refused/.test(st),
    '网格点数变了：拒绝而不是插值', st.replace(/\s+/g, ' ').slice(0, 90));

await br.close();
if (errs.length) { console.log('\n页面报错：'); errs.forEach((e) => console.log('  ' + e)); }
console.log(bad || errs.length ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad || errs.length ? 1 : 0);
