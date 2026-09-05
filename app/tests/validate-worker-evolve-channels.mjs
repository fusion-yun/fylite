// 模型页 worker 的 evolve 命令走文档门（FYL-DESIGN-16 K-3，2026-09-05）——第十五刀：
// 密度通道（含准中性里的杂质）与动量通道。
//
// 三个配置，切门**之前**用 `--record` 在 worker 自己的循环路径（`fy.coreMarch` 逐步、
// `fy.solveMomentum` 在旁）录下答案；切门之后同样的三个配置必须走条目（viaEntry）
// 而且逐位相同：
//   density  密度通道 + 加料，主离子一种（Z_eff 是滑杆）
//   quasi    密度通道 + 杂质进准中性（两种离子各自的 D/v 与加料，Z_eff 是结果）
//   momentum 热通道 + 动量通道（规定的力矩、Prandtl 数）
//
// `evolveRun` 在「范围内」的场合（闭合 0/1、热通道，电流通道要 g 文件或装置档的 ψ）走
// `evEntryMarch`：一步一步调 `evolve_heat`，每步把上一步的状态续回去。从前那是扁平导出
// `fy.scenario('evolve_heat', …)`；今天是 `fy.complete('code/evolve', …)`，计划里 `resume` 与
// 上一步的记录。这道门在 node 里把 worker 当脚本跑（与 validate-worker-design.mjs 同一套
// 宿主桩），Miller 档、热通道 + α + 辐射（Miller 档没有 ψ，页面自己拒绝电流通道）：
//
//   * `--record` 把每步的 te / ti / ne / psi / q 与读数写进 fixtures/worker-evolve-entry.json
//     （在切门**之前**跑一次，那就是旧配方的答案）；
//   * 默认对着那份 fixture **逐位**判——门与扁平导出到达同一个条目，同样的数。
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets') + path.sep;
const FIX = path.join(HERE, 'fixtures', 'worker-evolve-channels.json');
const BASE = 'http://127.0.0.1:0/';
const RECORD = process.argv.includes('--record');

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

const a = 0.45, nSteps = 10;
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
  fuel: 2.0, fuelCentre: 1.0, fuelWidth: 0.25,
  alpha: true, brem: true, ohmic: false, bootstrap: false, iCd: 0, cdCentre: 0.4, cdWidth: 0.2,
  zeff: 1.5, impurity: 'C', cImp: 0.01, dtFraction: 0.5, quasi: false, useRef: false,
  ip: 1.0e6, r0Src: 4.1 * a, emp: 1, enp: 1, beta0: 0.55, couple: 0,
};
const CASES = {
  density: { chDensity: true },
  quasi: { chDensity: true, quasi: true, fuelZ: 0.02 },
  momentum: { chMomentum: true, torque: 3.0, prandtl: 0.8 },
};
const arr = (v) => (v ? Array.from(v) : null);
const got = {};
for (const name of Object.keys(CASES)) {
  inbox.splice(0, inbox.length);
  send({ cmd: 'evolve', spec: Object.assign({}, base, CASES[name]) });
  const errs = inbox.filter((m) => m.type === 'error');
  assert.equal(errs.length, 0, name + ': worker error: ' + errs.map((e) => e.message).join(' | '));
  const steps = inbox.filter((m) => m.type === 'evolve_step');
  const done = inbox.find((m) => m.type === 'evolve');
  assert.ok(done, name + ': no final evolve message; inbox: ' + inbox.map((m) => m.type).join(','));
  assert.ok(steps.length >= 1, name + ': no evolve_step posts');
  if (!RECORD) assert.ok(steps.every((s) => s.viaEntry), name + ': the case ran on the entry path (viaEntry) on every step');
  got[name] = {
    steps: steps.map((s) => ({ step: s.step, te: arr(s.te), ti: arr(s.ti), ne: arr(s.ne), chiE: arr(s.chiE), chiI: arr(s.chiI),
                               //: through JSON, as the fixture is: a NaN reading (no rotation) is null there
                               reading: JSON.parse(JSON.stringify({ t: s.reading.t, dt: s.reading.dt, steady: s.reading.steady,
                                          omega0: s.reading.omega0, mach: s.reading.mach, ne0: s.reading.ne0, betaN: s.reading.betaN })) })),
    final: { te: arr(done.te), ti: arr(done.ti), ne: arr(done.ne), ni: arr(done.ni), nz: arr(done.nz), omega: arr(done.omega),
             torque: arr(done.torque), zeffProfile: arr(done.zeffProfile), zeffSolved: done.zeffSolved,
             impurity: done.impurity, steps: done.steps, tEnd: done.tEnd, trace: done.trace.length },
  };
}
if (RECORD) {
  writeFileSync(FIX, JSON.stringify(got));
  console.log(`recorded ${Object.keys(got).join(' ')} -> ${path.relative(process.cwd(), FIX)}`);
  process.exit(0);
}
const ref = JSON.parse(readFileSync(FIX, 'utf8'));
if (process.argv.includes('--debug')) {
  const rel = (x, y) => { let m = 0; for (let i = 0; i < x.length; i++) m = Math.max(m, Math.abs(x[i] - y[i]) / Math.max(Math.abs(y[i]), 1e-300)); return m; };
  for (const name of Object.keys(CASES)) {
    for (let k = 0; k < ref[name].steps.length; k++) {
      const g = got[name].steps[k], r = ref[name].steps[k];
      console.log(name, 'step', k + 1, 'dt', g.reading.dt, r.reading.dt, 'te', rel(g.te, r.te).toExponential(2), 'ti', rel(g.ti, r.ti).toExponential(2), 'ne', rel(g.ne, r.ne).toExponential(2), 'ne0', g.ne[0], r.ne[0]);
    }
    console.log(name, 'final ni0', got[name].final.ni[0], ref[name].final.ni[0], 'nz0', got[name].final.nz && got[name].final.nz[0], ref[name].final.nz && ref[name].final.nz[0]);
  }
  process.exit(0);
}
if (false) {
  for (const name of Object.keys(CASES)) {
    const g = got[name].steps[0], r = ref[name].steps[0];
    console.log(name, 'step1 te0', g.te[0], r.te[0], 'te_edge-1', g.te[g.te.length - 2], r.te[r.te.length - 2],
                'ne0', g.ne[0], r.ne[0], 'ne_mid', g.ne[12], r.ne[12], 'chiE0', g.chiE[0], r.chiE[0], 'dt', g.reading.dt, r.reading.dt);
  }
  process.exit(0);
}
for (const name of Object.keys(CASES)) {
  const g = got[name], r = ref[name];
  assert.equal(g.steps.length, r.steps.length, name + ': step count');
  for (let k = 0; k < r.steps.length; k++) {
    for (const key of ['te', 'ti', 'ne', 'chiE', 'chiI'])
      assert.deepEqual(g.steps[k][key], r.steps[k][key], `${name} step ${k + 1}: ${key} bit for bit`);
    assert.deepEqual(g.steps[k].reading, r.steps[k].reading, `${name} step ${k + 1}: reading`);
  }
  assert.deepEqual(g.final, r.final, name + ': the final state');
}
console.log(`validate-worker-evolve-channels: ${Object.keys(CASES).length} 个配置逐位（密度 · 准中性 · 动量），`
            + `n_e(0) 终值 ${(got.quasi.final.ne[0] / 1e19).toFixed(3)}e19，ω(0) 终值 ${got.momentum.final.omega[0].toFixed(3)} rad/s`);
