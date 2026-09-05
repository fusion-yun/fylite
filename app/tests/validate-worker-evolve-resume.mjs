// 模型页 worker 的 evolve 命令走文档门（FYL-DESIGN-16 K-3，2026-09-05）——第二十二刀：
// 页面的**续跑**（`msg.resume`：一整份状态从页面递回，`msg.tStart` 接着走时钟）。
//
// 循环路径把递回的 te / ti / ne / psi 盖到起始剖面上、时钟从 `tStart` 接着走，其余（滞后的
// 通量与电导、交换上限、台基、控制器）都从头来——就是「从这份态开始的一次新推进」。条目
// 早就认 `state`（起始剖面按给定绑定）；这一刀给推进的时钟一个起点（`t_start` 不再只在
// `resume` 下读）。`ENTRY_SCOPE` 的 `resume` 行本来就是 sunk，worker 的 `evScopeMiss` 不再
// 因 `msg.resume` 拒绝条目路径。
//
// 判法：先跑三步（两条路早已逐位），把终态当 `resume`、`tEnd` 当 `tStart` 再跑三步；切门之前
// 用 `--record` 在循环路径录下第二段（assets 拷一份、`evScopeMiss` 强制不命中、`--site` 指过去），
// 切门之后第二段必须走条目（viaEntry）且逐位。
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = (() => { const i = process.argv.indexOf('--site'); return (i >= 0 ? process.argv[i + 1] : path.join(HERE, '..', 'assets')) + path.sep; })();
const FIX = path.join(HERE, 'fixtures', 'worker-evolve-resume.json');
const BASE = 'http://127.0.0.1:0/';
const RECORD = process.argv.includes('--record');
const OUT = (() => { const i = process.argv.indexOf('--out'); return i >= 0 ? process.argv[i + 1] : FIX; })();

globalThis.self = globalThis;
globalThis.location = { hostname: '127.0.0.1', href: BASE + 'assets/worker.js', search: '' };
globalThis.localStorage = { _s: {}, getItem(k) { return k in this._s ? this._s[k] : null; },
                            setItem(k, v) { this._s[k] = String(v); }, removeItem(k) { delete this._s[k]; } };
globalThis.importScripts = function () {
  for (const f of arguments) vm.runInThisContext(readFileSync(SITE + f, 'utf8'), { filename: f });
};
const inbox = [];
globalThis.postMessage = function (m) { inbox.push(m); };
globalThis.fetch = async (url) => {
  const u = String(url);
  if (/api\/health/.test(u)) throw new Error('offline: no desktop face');
  const f = SITE + path.basename(u.split('?')[0]);
  if (!existsSync(f)) throw new Error('no such asset ' + f);
  const bytes = readFileSync(f);
  return { ok: true, status: 200, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
           json: async () => JSON.parse(bytes.toString('utf8')), text: async () => bytes.toString('utf8') };
};
vm.runInThisContext(readFileSync(SITE + 'worker.js', 'utf8'), { filename: 'worker.js' });

const CANDIDATES = ['east', 'iter', 'west', 'jt60sa', 'cfetr', 'cfedr', 'best'];
let M = null;
for (const c of CANDIDATES) {
  const d = deviceDoc(c);
  if (!d) continue;
  try { M = globalThis.FyoDevice.fromFyo(d); break; } catch (e) { /* next */ }
}
if (!M) { console.log('跳过：dist/facts/device/ 里没有页面读得懂的装置文档'); process.exit(0); }
const send = (msg) => globalThis.self.onmessage({ data: msg });
await send({ cmd: 'init', machine: M });
inbox.splice(0, inbox.length);


const a = 0.45, nSteps = 3;
const base = {
  geometry: 'miller', n: 25, edgePsin: 0.95, a, r0: 4.1 * a, kappa: 1.6, delta: 0.4, q95: 2.6, b0: 2.0,
  chHeat: true, chDensity: false, chCurrent: false, chMomentum: false, torque: 0, prandtl: 1,
  dt: 2e-3, nSteps, dtTarget: 0, dtMin: 2e-3 / 500, dtMax: 2e-3 * 50, nCoupling: 2, tolSteady: 1e-9, report: 1,
  te0: 3000, ti0: 2800, ne0: 4e19, edgeNe: 5e18, edgeTe: 100, edgeTi: 100, pedestal: false,
  peakT: 1.5, peakN: 0.5, vLoop: 0.5, b0Dot: 0, closure: 0, chi0: 1.0,
  turbEvery: 0, turbNrad: 0, turbNky: 0, turbRelax: 0, fmIter: 0, fmTol: 0, fmDx: 0, fmDxMax: 0, fmRhoMin: 0,
  fmOuter: 1, dOverChiZ: 0.3, pinchZ: -0.5, fuelZ: 0, fmOTol: 0, fmORelax: 0,
  ipCtl: false, ipKp: 0, ipKi: 0, chiRatio: 1.0, dOverChi: 0.5, pinch: -1.0, dPc: 0,
  sawtooth: false, sawMix: 1.2, sawPeriod: 0, pE: 2.0, pI: 1.0, depCentre: 0.0, depWidth: 0.3,
  beam: false, lh: false, wave: false, beamSamples: 601, beamNWidth: 3, beamMass: 2,
  fuel: 0, fuelCentre: 1.0, fuelWidth: 0.25,
  alpha: true, brem: true, ohmic: false, bootstrap: false, iCd: 0, cdCentre: 0.4, cdWidth: 0.2,
  zeff: 1.5, impurity: 'C', cImp: 0.01, dtFraction: 0.5, quasi: false, useRef: false,
  ip: 1.0e6, r0Src: 4.1 * a, emp: 1, enp: 1, beta0: 0.55, couple: 0,
};
const arr = (v) => (v ? Array.from(v) : null);
const run = (msg) => {
  inbox.splice(0, inbox.length);
  send(msg);
  const errs = inbox.filter((m) => m.type === 'error');
  assert.equal(errs.length, 0, 'worker error: ' + errs.map((e) => e.message).join(' | '));
  const steps = inbox.filter((m) => m.type === 'evolve_step');
  const done = inbox.find((m) => m.type === 'evolve');
  assert.ok(done && steps.length === nSteps, 'the march posted its steps');
  return { steps, done };
};
//: the first leg: fresh, the same on both routes (validate-worker-evolve holds it)
const first = run({ cmd: 'evolve', spec: Object.assign({}, base) });
const resume = { te: arr(first.done.te), ti: arr(first.done.ti), ne: arr(first.done.ne), psi: arr(first.done.psi) };
//: the second leg: the page's resume — the state handed back, the clock continued
const second = run({ cmd: 'evolve', spec: Object.assign({}, base), resume, tStart: first.done.tEnd });
if (!RECORD) assert.ok(second.steps.every((s) => s.viaEntry), 'the resumed leg ran on the entry path (viaEntry)');
const got = {
  tStart: first.done.tEnd,
  //: ★no `q` in the record: with the current channel off the loop reports the
  //: march's zero q and the entry reports none (the ladder's at the end) — a
  //: convention of each route, not a number either reached
  steps: second.steps.map((s) => ({ step: s.step, te: arr(s.te), ti: arr(s.ti), ne: arr(s.ne), jni: arr(s.jni),
                                    reading: JSON.parse(JSON.stringify({ t: s.reading.t, dt: s.reading.dt, betaN: s.reading.betaN,
                                                                         pOhm: s.reading.pOhm, dwdt: s.reading.dwdt, q0: s.reading.q0 })) })),
  final: { te: arr(second.done.te), ti: arr(second.done.ti), ne: arr(second.done.ne), psi: arr(second.done.psi),
           steps: second.done.steps, tEnd: second.done.tEnd, trace: second.done.trace.length },
};
if (RECORD) {
  writeFileSync(OUT, JSON.stringify(got));
  console.log(`recorded -> ${path.relative(process.cwd(), OUT)}`);
  process.exit(0);
}
const ref = JSON.parse(readFileSync(FIX, 'utf8'));
assert.equal(got.tStart, ref.tStart, 'the first leg ended where the fixture\'s did');
assert.equal(got.steps.length, ref.steps.length);
for (let k = 0; k < ref.steps.length; k++) {
  for (const key of ['te', 'ti', 'ne'])
    assert.deepEqual(got.steps[k][key], ref.steps[k][key], `resumed step ${k + 1}: ${key} bit for bit`);
  assert.deepEqual(got.steps[k].reading, ref.steps[k].reading, `resumed step ${k + 1}: reading (the clock continued)`);
}
assert.deepEqual(got.final, ref.final, 'the resumed leg\'s final state');
assert.ok(got.steps[0].reading.t > got.tStart, 'the clock continued from tStart');
console.log(`validate-worker-evolve-resume: 续跑三步逐位（时钟从 ${got.tStart.toFixed(4)} s 接着走到 ${got.final.tEnd.toFixed(4)} s），T_e(0) 终值 ${got.final.te[0].toFixed(1)} eV`);
