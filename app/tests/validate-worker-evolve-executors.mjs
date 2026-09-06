// 模型页 worker 的 evolve 命令走文档门（FYL-DESIGN-16 K-3，2026-09-05）——第十七刀：
// 推进循环里的两个执行器，中性束（`beam`）与低杂波（`lh`）。
//
// 三个配置，切门**之前**用 `--record` 在 worker 自己的循环路径（`evBeamDeposit` /
// `evLhDeposit` 走 `code/beam` / `code/wave`，`evShellLadderOp` 把壳层沉积守恒地重映射到
// 梯子，再 `fy.coreMarch` 逐步）录下答案；切门之后同样的三个配置必须走条目（viaEntry）
// 而且逐位相同：
//   beam    热 + 电流 + 动量通道，一束 60 keV 顺流注入（一阶轨道损失开），力矩是束自己的
//   lh      热 + 电流通道，一个低杂波天线（n_∥ 带 1.8–2.2，上移 1–1.5）
//   both    束 + 波 + 四相梯形波形（功率跟波形走）+ 动量通道
//
// 度规是 g 文件档：束要沿弦衰减的 ψ 图，波要壳层体积与中平面大半径——Miller 档没有 ψ 图，
// 页面自己拒绝。g 文件是内核仓 `tests/data/FYDOC-CASE-12-synthetic` 的合成平衡（一份
// 拷贝在 fixtures/ 里），这里用本文件自己的读法解析（页面的读法走数据层 wasm，node 里
// 不装它；数是同一份，页面 `gfilePayload` 的规矩逐字：`psi = -2π psirz` 转成 R 主序，
// a / R0 由内核的 `shape_metrics` 量边界）。
//
//   * `--record [--site DIR]` 把每步的 te / ti / ne / q 与读数、终态与两份执行器记录写进
//     fixtures/worker-evolve-executors.json——切门之后要重录时，把 assets 拷一份、让它的 `evScopeMiss`
//     一律不命中（强制走循环），用 `--site` 指过去，录的就是**同一内核上循环路径的答案**；
//   * 默认对着那份 fixture **逐位**判（q 的轴节点除外：循环带的是 `core_march` 的半节点值，条目外推——见下）。
//
// ★fixture 的来历：第一次录自切门前的循环；切门时内核的 `uniform_axis` 改为取能逐位复原网格轴的间距
// （合成 g 文件的 Z 轴上首差差一个 ulp，壳体积因此全部动 1e-15），`code/beam` / `code/wave` 自己的壳表
// 也随之动了最后一位，于是按上面的办法在同一内核上重录了一次（2026-09-05）。
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';
//: ★T-4 第二十一刀 (2026-09-06): the gate's own shape reading goes through `code/shape` too
function shapeOf(fy, r, z) {
  const f = fy.complete('code/shape', { settings: {}, inputs: { equilibrium: {
    time_slice: { boundary: { outline: { r: Float64Array.from(r), z: Float64Array.from(z) } } } } } }).facts;
  return { r0: f.r0.value, a: f.a.value, kappa: f.kappa.value, deltaU: f.delta_upper.value,
           deltaL: f.delta_lower.value, z0: f.z0.value, delta: 0.5 * (f.delta_upper.value + f.delta_lower.value) };
}


const HERE = path.dirname(fileURLToPath(import.meta.url));
//: `--site DIR` runs the worker out of another assets directory — a scratch copy
//: whose `evScopeMiss` is forced to miss, so `--record` reads the LOOP's answer
//: on the same kernel; the gate proper always reads the shipped assets
const SITE = (() => { const i = process.argv.indexOf('--site'); return (i >= 0 ? process.argv[i + 1] : path.join(HERE, '..', 'assets')) + path.sep; })();
const FIX = path.join(HERE, 'fixtures', 'worker-evolve-executors.json');
const GFILE = path.join(HERE, 'fixtures', 'g_synthetic.geqdsk');
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

/** GEQDSK, the fixed-column format: a header ending in `idum nw nh`, then the numbers. */
function parseGeqdsk(text) {
  const lines = text.split('\n');
  const head = lines[0].trim().split(/\s+/);
  const nw = +head[head.length - 2], nh = +head[head.length - 1];
  const nums = (lines.slice(1).join('\n').match(/[-+]?\d+\.\d+[EeDd][-+]?\d+|[-+]?\d+/g) || []).map(Number);
  let at = 0;
  const take = (n) => { const v = nums.slice(at, at + n); at += n; return v; };
  const [rdim, zdim, rcentr, rleft, zmid] = take(5);
  const [rmaxis, zmaxis, simag, sibry, bcentr] = take(5);
  take(5); take(5);
  const fpol = take(nw), pres = take(nw), ffprim = take(nw), pprime = take(nw);
  const psirz = take(nw * nh), qpsi = take(nw);
  const [nbbbs, limitr] = take(2);
  const bb = take(2 * nbbbs), ll = take(2 * limitr);
  const rbbbs = [], zbbbs = [], rlim = [], zlim = [];
  for (let i = 0; i < nbbbs; i++) { rbbbs.push(bb[2 * i]); zbbbs.push(bb[2 * i + 1]); }
  for (let i = 0; i < limitr; i++) { rlim.push(ll[2 * i]); zlim.push(ll[2 * i + 1]); }
  return { nw, nh, rdim, zdim, rcentr, rleft, zmid, rmaxis, zmaxis, simag, sibry, bcentr,
           fpol, pres, ffprim, pprime, psirz, qpsi, nbbbs, limitr, rbbbs, zbbbs, rlim, zlim };
}
/** The page's `gfilePayload`, verbatim: the app gauge (psi = -2 pi psirz, R-major). */
function gfilePayload(g, fy) {
  const psi = new Float64Array(g.nw * g.nh);
  for (let j = 0; j < g.nh; j++)
    for (let i = 0; i < g.nw; i++) psi[i * g.nh + j] = -2 * Math.PI * g.psirz[j * g.nw + i];
  const sm = shapeOf(fy, g.rbbbs, g.zbbbs);
  const lr = g.limitr ? g.rlim : g.rbbbs, lz = g.limitr ? g.zlim : g.zbbbs;
  return { psi: Array.from(psi), psiAxis: -2 * Math.PI * g.simag, psiBnd: -2 * Math.PI * g.sibry,
           axisR: g.rmaxis, axisZ: g.zmaxis, r0: g.rleft, z0: g.zmid - g.zdim / 2,
           dr: g.rdim / (g.nw - 1), dz: g.zdim / (g.nh - 1), nr: g.nw, nz: g.nh,
           limR: Array.from(lr), limZ: Array.from(lz), qTable: Array.from(g.qpsi), fTable: Array.from(g.fpol),
           b0: Math.abs(g.bcentr), a: sm.a, rmaj: sm.r0, bndR: Array.from(g.rbbbs), bndZ: Array.from(g.zbbbs) };
}

//: the worker attaches its kernel only with a machine; the g-file tier then
//: reads nothing off it (the field, the limiter and the boundary are the file's)
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
const fy = globalThis.fy;
assert.ok(fy && typeof fy.complete === 'function', 'the worker holds a kernel after init');
const gfile = gfilePayload(parseGeqdsk(readFileSync(GFILE, 'utf8')), fy);

const nSteps = 6;
const base = {
  geometry: 'gfile', n: 21, edgePsin: 0.95, a: gfile.a, r0: gfile.rmaj, kappa: 1.6, delta: 0.3, q95: 3.0, b0: gfile.b0,
  chHeat: true, chDensity: false, chCurrent: true, chMomentum: false, torque: 0, prandtl: 1,
  dt: 1e-3, nSteps, dtTarget: 0, dtMin: 1e-3 / 500, dtMax: 1e-3 * 50, nCoupling: 2, tolSteady: 1e-9, report: 1,
  te0: 3000, ti0: 2500, ne0: 3e19, edgeNe: 5e18, edgeTe: 300, edgeTi: 300, pedestal: false,
  peakT: 1.5, peakN: 0.5, vLoop: 0.5, b0Dot: 0, closure: 0, chi0: 1.0,
  turbEvery: 0, turbNrad: 0, turbNky: 0, turbRelax: 0, fmIter: 0, fmTol: 0, fmDx: 0, fmDxMax: 0, fmRhoMin: 0,
  fmOuter: 1, dOverChiZ: 0.3, pinchZ: -0.5, fuelZ: 0, fmOTol: 0, fmORelax: 0,
  ipCtl: false, ipKp: 0, ipKi: 0, chiRatio: 1.0, dOverChi: 0.3, pinch: 0, dPc: 0,
  sawtooth: false, sawMix: 1.2, sawPeriod: 0, pE: 2.0, pI: 2.0, depCentre: 0.0, depWidth: 0.3,
  beam: false, lh: false, wave: false,
  beamPower: 4e6, beamEnergy: 60e3, beamRtan: 1.26, beamZ: 0, beamWidth: 0.10, beamDir: 1, beamStopping: 'janev',
  beamF1: 1, beamF2: 0, beamF3: 0, beamShells: 24, beamOrbit: true, beamSamples: 601, beamNWidth: 3, beamMass: 2,
  lhNames: ['LH1', 'LH2'], lhPower1: 2e6, lhPower2: 0, lhNpar1Lo: 1.8, lhNpar1Hi: 2.2, lhNpar2Lo: 2.0, lhNpar2Hi: 2.4,
  lhUpLo: 1.0, lhUpHi: 1.5, lhEtaCd: 1e19, lhXi: 3.0, lhWidthFloor: 0.05, lhShells: 24,
  fuel: 0, fuelCentre: 1.0, fuelWidth: 0.25,
  alpha: false, brem: true, ohmic: true, bootstrap: true, iCd: 0, cdCentre: 0.4, cdWidth: 0.2,
  zeff: 1.5, impurity: '', cImp: 0, dtFraction: 0.5, quasi: false, useRef: false,
  ip: 7.0e5, r0Src: gfile.rmaj, emp: 1, enp: 1, beta0: 0.55, couple: 0,
};
const CASES = {
  beam: { beam: true, chMomentum: true },
  lh: { lh: true },
  both: { beam: true, lh: true, chMomentum: true, wave: true, waveRamp: 0.002, waveFlat: 0.004, waveEnd: 0.008,
          waveStart: 0.3, waveEnd2: 0.5, wavePower: true, waveFuel: false, waveVloop: false, waveIp: false },
};
const arr = (v) => (v ? Array.from(v) : null);
const num = (v) => (v === undefined ? null : v);
const got = {};
for (const name of Object.keys(CASES)) {
  inbox.splice(0, inbox.length);
  send({ cmd: 'evolve', spec: Object.assign({}, base, CASES[name]), gfile });
  const errs = inbox.filter((m) => m.type === 'error');
  assert.equal(errs.length, 0, name + ': worker error: ' + errs.map((e) => e.message).join(' | '));
  const steps = inbox.filter((m) => m.type === 'evolve_step');
  const done = inbox.find((m) => m.type === 'evolve');
  assert.ok(done, name + ': no final evolve message; inbox: ' + inbox.map((m) => m.type).join(','));
  assert.ok(steps.length >= 1, name + ': no evolve_step posts');
  if (!RECORD) assert.ok(steps.every((s) => s.viaEntry), name + ': the case ran on the entry path (viaEntry) on every step');
  const rd = (r) => JSON.parse(JSON.stringify({ t: r.t, dt: r.dt, steady: r.steady, omega0: r.omega0, mach: r.mach, ne0: r.ne0,
                                                betaN: r.betaN, betaP: r.betaP, wFast: num(r.wFast), pAux: r.pAux,
                                                pAuxBeam: r.pAuxBeam, pAuxLh: r.pAuxLh, torqueBeam: num(r.torqueBeam),
                                                pOhm: r.pOhm, q0: r.q0 }));
  got[name] = {
    steps: steps.map((s) => ({ step: s.step, te: arr(s.te), ti: arr(s.ti), ne: arr(s.ne), q: arr(s.q), jni: arr(s.jni),
                               chiE: arr(s.chiE), chiI: arr(s.chiI), reading: rd(s.reading) })),
    final: { te: arr(done.te), ti: arr(done.ti), ne: arr(done.ne), psi: arr(done.psi), q: arr(done.q), omega: arr(done.omega),
             torque: arr(done.torque), jni: arr(done.jni), ohm: arr(done.ohm),
             //: the two executors' whole records (the beam's carries its input echo, psi map included)
             beam: JSON.parse(JSON.stringify(done.beam)), lh: JSON.parse(JSON.stringify(done.lh)),
             steps: done.steps, tEnd: done.tEnd, trace: done.trace.length },
  };
}
if (RECORD) {
  writeFileSync(OUT, JSON.stringify(got));
  console.log(`recorded ${Object.keys(got).join(' ')} -> ${path.relative(process.cwd(), OUT)}`);
  process.exit(0);
}
const ref = JSON.parse(readFileSync(FIX, 'utf8'));

for (const name of Object.keys(CASES)) {
  const g = got[name], r = ref[name];
  assert.equal(g.steps.length, r.steps.length, name + ': step count');
  for (let k = 0; k < r.steps.length; k++) {
    for (const key of ['te', 'ti', 'ne', 'jni', 'chiE', 'chiI'])
      assert.deepEqual(g.steps[k][key], r.steps[k][key], `${name} step ${k + 1}: ${key} bit for bit`);
    //: ★q's AXIS node is a convention, not a number the march reached: the loop
    //: carries `core_march`'s half-node value (q_1 / 2) and the entry extrapolates
    //: from the interior (the sawtooth trigger reads it); the page's q0 reading is
    //: its own interior extrapolation on both paths.  Every other node is held.
    assert.deepEqual(g.steps[k].q.slice(1), r.steps[k].q.slice(1), `${name} step ${k + 1}: q[1:] bit for bit`);
    assert.deepEqual(g.steps[k].reading, r.steps[k].reading, `${name} step ${k + 1}: reading`);
  }
  const fin = (f) => Object.assign({}, f, { q: f.q ? f.q.slice(1) : null });
  assert.deepEqual(fin(g.final), fin(r.final), name + ': the final state and the two executors\' records');
}
console.log(`validate-worker-evolve-executors: ${Object.keys(CASES).length} 个配置逐位（束 · 波 · 束+波+波形），`
            + `T_e(0) 终值 ${got.beam.final.te[0].toFixed(1)} / ${got.lh.final.te[0].toFixed(1)} eV，`
            + `束沉积 ${(got.beam.final.beam.pAbsorbed / 1e6).toFixed(3)} MW`);
