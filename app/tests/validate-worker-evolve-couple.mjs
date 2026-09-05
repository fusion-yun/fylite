// 模型页 worker 的 evolve 命令走文档门（FYL-DESIGN-16 K-3，2026-09-05）——第十九刀：
// 装置档的平衡交替（`couple = K`：每 K 步在装置线圈上重解一次自由边界平衡）。
//
// 切门之前，交替的一块是 worker 自己的十几个扁平导出串起来的：`evFitShape` 把输运压强
// 的形状拟到解析电流族、两个 β_p 之比推动 `beta0`、`freeSolve`（`fy.gsFreeSolve`）、
// `summarize`（解析真值 · q 剖面 · 边界）、`evLadderFromSolve`（`fy.equilibriumLadder`）、
// `evRemap` 把剖面按 ψ_N 搬到新梯子、`evPsiOf` 在推进的规范里重建极向通量、老 V' 重映射给
// 下一步的移动体积。今天这一块整个是内核的 `code/refit`（`fit: 1`），装置档的起始解
// 也是它（`fit: 0`：只解只描梯子）；页面留下的只有**块的节拍**——第十八刀湍流档的同一条规矩。
//
// 两个配置，切门**之前**用 `--record` 在 worker 自己的循环路径录下答案（把 assets 拷一份、
// 让它的 `evScopeMiss` 一律不命中，`--site` 指过去）；切门之后同样的配置必须走条目（viaEntry）：
//   plain   热 + 电流通道，couple 2，五步（三块：2 · 2 · 1）
//   beam    热 + 电流 + 动量通道，一束顺流注入，couple 2 —— 束随平衡重建（新 ψ 图新弦）
//   fixed   plain 加固定边界细化（第二十刀：`coupleFixed`，p′ / FF′ 三次多项式）——细化的记录
//           （零测试 · 拟合残差 · I_p · 解出的子网格）或它按名的拒绝，两条路要一样。
//           ★在这台机器上两次交替都走**拒绝**那条路（等离子体缩到 a ≈ 0.18 m，围不出 ≥ 6 格的
//           子网格——`refine_box`，与循环路径同一句话）；细化本身在内核仓 `tests/test_evolve_couple_code.py`
//           用 EAST 参考放电判（零测试 · 记录的一致性 · 压强从边界向内回积）。
//
// ★判到多紧：线圈通量在两条路上是**同一组 4×4 细丝的同一个和，加的次序不同**（页面按通道响应
// 缓存后合成，内核按元件折叠后一次装配；网格轴的 linspace 也是两种写法），所以自由边界解只能到浮点和的
// 次序误差（实测最坏 4.6e-9，容差 1e-7），
// 它下游的梯子、重映射与后续块的推进跟着这个量级走；第 0 块（起始解之前的推进不存在，起始解
// 本身就是这条差别的来源）也一样。读数与记录（rounds · evolve_couple）按同一容差判；整数与
// 判据逐位。
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = (() => { const i = process.argv.indexOf('--site'); return (i >= 0 ? process.argv[i + 1] : path.join(HERE, '..', 'assets')) + path.sep; })();
const FIX = path.join(HERE, 'fixtures', 'worker-evolve-couple.json');
const BASE = 'http://127.0.0.1:0/';
const RECORD = process.argv.includes('--record');
const OUT = (() => { const i = process.argv.indexOf('--out'); return i >= 0 ? process.argv[i + 1] : FIX; })();
//: the relative tolerance the two flux assemblies allow (see the header)
const REL = 1e-7;

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

//: EAST when its card is here, else the first published machine the page reads
const CANDIDATES = ['east', 'iter', 'west', 'jt60sa', 'cfetr', 'cfedr', 'best'];
let M = null, id = null;
for (const c of CANDIDATES) {
  const d = deviceDoc(c);
  if (!d) continue;
  try { M = globalThis.FyoDevice.fromFyo(d); id = c; break; } catch (e) { /* next */ }
}
if (!M) { console.log('跳过：dist/facts/device/ 里没有页面读得懂的装置文档'); process.exit(0); }
const send = (msg) => globalThis.self.onmessage({ data: msg });
const take = (type) => {
  const i = inbox.findIndex((m) => m.type === type || m.type === 'error');
  assert.ok(i >= 0, `no ${type} answer; inbox: ` + inbox.map((m) => m.type).join(','));
  const m = inbox.splice(i, 1)[0];
  assert.notEqual(m.type, 'error', `${type}: worker error: ` + m.message);
  return m;
};
await send({ cmd: 'init', machine: M });
inbox.splice(0, inbox.length);

// --- the designed start: the channel currents the march's equilibria stand on ---
const bb = globalThis.FyDevice.bbox(M), tf = globalThis.FyDevice.tf(M);
const rgeo = 0.5 * (bb.rmin + bb.rmax), amax = 0.5 * (bb.rmax - bb.rmin);
const target = { r0: rgeo, z0: 0.5 * (bb.zmin + bb.zmax), a: 0.6 * amax, kappa: 1.6, deltaU: 0.4, deltaL: 0.5 };
const b0 = Math.abs(tf.b0 * tf.r0 / rgeo);
const ip = 2 * Math.PI * target.a * target.a * b0 * (1 + target.kappa * target.kappa)
           / (2 * 4e-7 * Math.PI * rgeo * 3.5);
send({ cmd: 'start', target, ip, nPoints: 24, xWeight: 0, control: [], iMax: null,
       nRing: 4, peaking: 1, lambda: 1e-3 });
const st = take('start');
inbox.splice(0, inbox.length);
//: ★the designed START is a linear isoflux answer, not an equilibrium: on the
//: first published machine the free solve on those currents shrank the plasma
//: to a tenth of the target (measured: a = 0.12 m for 0.6 * a_max asked), and a
//: plasma that small has no sub-grid to refine on.  Two passes of the anneal
//: (the design page's own `design` command, `code/discharge`) put the boundary
//: where it was asked, and the alternation — refinement included — runs on
//: currents a design would actually hand over.
send({ cmd: 'design', chan: Array.from(st.chan), target, ip, warm: true,
       prof: { beta0: 0.55, emp: 1, enp: 1, r0: target.r0 },
       schedule: [0.1, 0.03], gamma: 0.4, nPoints: 24, xWeight: 0, control: [],
       solve: { maxIter: 400, relax: 0.3, tol: 1e-8 } });
const dsg = take('design');
const chan = Array.from(dsg.chan);
inbox.splice(0, inbox.length);

const nSteps = 5;
const base = {
  geometry: 'device', n: 17, edgePsin: 0.95, a: target.a, r0: target.r0, kappa: 1.6, delta: 0.3, q95: 3.5, b0,
  chHeat: true, chDensity: false, chCurrent: true, chMomentum: false, torque: 0, prandtl: 1,
  dt: 1e-3, nSteps, dtTarget: 0, dtMin: 1e-3 / 500, dtMax: 1e-3 * 50, nCoupling: 2, tolSteady: 1e-9, report: 1,
  te0: 2000, ti0: 1500, ne0: 3e19, edgeNe: 5e18, edgeTe: 200, edgeTi: 200, pedestal: false,
  peakT: 1.5, peakN: 0.5, vLoop: 0.5, b0Dot: 0, closure: 0, chi0: 1.0,
  turbEvery: 0, turbNrad: 0, turbNky: 0, turbRelax: 0, fmIter: 0, fmTol: 0, fmDx: 0, fmDxMax: 0, fmRhoMin: 0,
  fmOuter: 1, dOverChiZ: 0.3, pinchZ: -0.5, fuelZ: 0, fmOTol: 0, fmORelax: 0,
  ipCtl: false, ipKp: 0, ipKi: 0, chiRatio: 1.0, dOverChi: 0.3, pinch: 0, dPc: 0,
  sawtooth: false, sawMix: 1.2, sawPeriod: 0, pE: 1.0, pI: 1.0, depCentre: 0.0, depWidth: 0.3,
  beam: false, lh: false, wave: false,
  beamPower: 2e6, beamEnergy: 60e3, beamRtan: 0.7 * rgeo, beamZ: 0, beamWidth: 0.10, beamDir: 1, beamStopping: 'janev',
  beamF1: 1, beamF2: 0, beamF3: 0, beamShells: 24, beamOrbit: true, beamSamples: 601, beamNWidth: 3, beamMass: 2,
  fuel: 0, fuelCentre: 1.0, fuelWidth: 0.25,
  alpha: false, brem: true, ohmic: true, bootstrap: true, iCd: 0, cdCentre: 0.4, cdWidth: 0.2,
  zeff: 1.5, impurity: '', cImp: 0, dtFraction: 0.5, quasi: false, useRef: false,
  ip, r0Src: target.r0, emp: 1, enp: 1, beta0: 0.55, relax: 0.5, couple: 2, coupleFixed: false,
  freeMaxIter: 400,
};
const CASES = {
  plain: {},
  beam: { beam: true, chMomentum: true },
  fixed: { coupleFixed: true, degP: 3, degF: 3 },
};
const arr = (v) => (v ? Array.from(v) : null);
const num = (v) => (v === undefined ? null : v);
const got = {};
for (const name of Object.keys(CASES)) {
  inbox.splice(0, inbox.length);
  send({ cmd: 'evolve', spec: Object.assign({}, base, CASES[name]), chan });
  const errs = inbox.filter((m) => m.type === 'error');
  assert.equal(errs.length, 0, name + ': worker error: ' + errs.map((e) => e.message).join(' | '));
  const steps = inbox.filter((m) => m.type === 'evolve_step');
  const couples = inbox.filter((m) => m.type === 'evolve_couple');
  const geoms = inbox.filter((m) => m.type === 'evolve_geometry');
  const done = inbox.find((m) => m.type === 'evolve');
  assert.ok(done, name + ': no final evolve message; inbox: ' + inbox.map((m) => m.type).join(','));
  assert.equal(steps.length, nSteps, name + ': one evolve_step per step');
  assert.equal(couples.length, 2, name + ': two alternations between three blocks');
  assert.equal(geoms.length, 3, name + ': the picture follows each alternation');
  if (!RECORD) assert.ok(steps.every((s) => s.viaEntry), name + ': the case ran on the entry path (viaEntry) on every step');
  const rd = (r) => JSON.parse(JSON.stringify({ t: r.t, dt: r.dt, steady: r.steady, betaN: r.betaN, betaP: r.betaP,
                                                wTh: r.wTh, pAux: r.pAux, pAuxBeam: r.pAuxBeam, pOhm: r.pOhm, q0: r.q0,
                                                ipPsi: num(r.ipPsi), omega0: num(r.omega0) }));
  got[name] = {
    steps: steps.map((s) => ({ step: s.step, coupled: s.coupled, n: s.rho.length, rho: arr(s.rho), psin: arr(s.psin),
                               te: arr(s.te), ti: arr(s.ti), ne: arr(s.ne), q: arr(s.q), jni: arr(s.jni),
                               omega: arr(s.omega), reading: rd(s.reading) })),
    couples: couples.map((c) => ({ block: c.block, beta0: c.beta0, fit: c.fit, bpTarget: c.bpTarget, bpEq: c.bpEq, bpFix: c.bpFix,
                                   free: c.free, shape: c.shape, lcfs: c.lcfs.length, refined: c.refined, refineWhy: c.refineWhy })),
    rounds: done.rounds.map((r) => ({ block: r.block, steps: r.steps, settled: r.settled, fit: r.fit, beta0: r.beta0,
                                      bpTarget: r.bpTarget, bpEq: r.bpEq, bpFix: r.bpFix, free: r.free,
                                      refined: r.refined, refineWhy: r.refineWhy })),
    freeSolves: done.freeSolves,
    //: the last refinement's solved box (the session file's checkable claim)
    refinedField: done.refinedField ? {
      nr: done.refinedField.r.length, nz: done.refinedField.z.length,
      r0: done.refinedField.r[0], z0: done.refinedField.z[0],
      psi: arr(done.refinedField.psi), psiAxis: done.refinedField.psiAxis, psiBnd: done.refinedField.psiBnd,
      axisR: done.refinedField.axisR, axisZ: done.refinedField.axisZ,
      limR: arr(done.refinedField.limR), limZ: arr(done.refinedField.limZ),
      dpCoef: arr(done.refinedField.dpCoef), dgCoef: arr(done.refinedField.dgCoef),
      ip: done.refinedField.ip, ipTarget: done.refinedField.ipTarget, ffShift: done.refinedField.ffShift,
      ipRaw: done.refinedField.ipRaw } : null,
    final: { te: arr(done.te), ti: arr(done.ti), ne: arr(done.ne), psi: arr(done.psi), q: arr(done.q), omega: arr(done.omega),
             rho: arr(done.rho), psin: arr(done.psin), vprime: arr(done.vprime), gm3: arr(done.gm3), gm2: arr(done.gm2),
             fpol: arr(done.fpol), qGeo: arr(done.qGeo), aMinor: done.aMinor, rMajor: done.rMajor, b0: done.b0,
             beam: done.beam ? { pAbsorbed: done.beam.pAbsorbed, torqueTotal: done.beam.torqueTotal,
                                 onLadder: arr(done.beam.onLadder) } : null,
             steps: done.steps, tEnd: done.tEnd, trace: done.trace.length },
  };
}
got.machine = id;
if (RECORD) {
  writeFileSync(OUT, JSON.stringify(got));
  console.log(`recorded ${Object.keys(got).join(' ')} on ${id} -> ${path.relative(process.cwd(), OUT)}`);
  process.exit(0);
}
const ref = JSON.parse(readFileSync(FIX, 'utf8'));
//: the fixture is one machine's answer; a checkout whose first published
//: machine is another one cannot be judged against it
if (ref.machine !== id) {
  console.log(`跳过：fixture 录自 ${ref.machine}，这份检出先读到的是 ${id}（用 --record --site 在同一装置上重录）`);
  process.exit(0);
}

//: ★the comparison: numbers to REL (NaN against NaN, null against null),
//: strings / booleans / integers-by-value exactly, walking any nesting
let worst = 0;
function close(a, b, where) {
  if (a === null || b === null || a === undefined || b === undefined) {
    assert.ok((a ?? null) === (b ?? null), `${where}: ${a} vs ${b}`); return;
  }
  if (typeof a === 'number') {
    assert.equal(typeof b, 'number', where);
    if (Number.isNaN(a) || Number.isNaN(b)) { assert.ok(Number.isNaN(a) && Number.isNaN(b), `${where}: ${a} vs ${b}`); return; }
    const d = Math.abs(a - b), s = Math.max(Math.abs(a), Math.abs(b));
    const rel = s > 0 ? d / s : 0;
    if (rel > worst) worst = rel;
    assert.ok(d <= REL * s || d === 0, `${where}: ${a} vs ${b} (rel ${rel.toExponential(2)})`);
    return;
  }
  if (Array.isArray(a)) {
    assert.ok(Array.isArray(b) && a.length === b.length, `${where}: length ${a.length} vs ${b && b.length}`);
    for (let i = 0; i < a.length; i++) close(a[i], b[i], `${where}[${i}]`);
    return;
  }
  if (typeof a === 'object') {
    const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
    assert.deepEqual(ka, kb, `${where}: keys`);
    for (const k of ka) close(a[k], b[k], `${where}.${k}`);
    return;
  }
  assert.equal(a, b, where);
}
for (const name of Object.keys(CASES)) {
  //: the fixture went through JSON (NaN -> null); the live answer takes the same road
  const g = JSON.parse(JSON.stringify(got[name])), r = ref[name];
  assert.equal(g.steps.length, r.steps.length, name + ': step count');
  for (let k = 0; k < r.steps.length; k++) {
    const gs = g.steps[k], rs = r.steps[k];
    assert.equal(gs.coupled, rs.coupled, `${name} step ${k + 1}: the block it ran in`);
    assert.equal(gs.n, rs.n, `${name} step ${k + 1}: the ladder's node count`);
    for (const key of ['rho', 'psin', 'te', 'ti', 'ne', 'jni', 'omega'])
      close(gs[key], rs[key], `${name} step ${k + 1}: ${key}`);
    //: q's axis node is a convention (the loop's half node, the entry's extrapolation)
    close(gs.q.slice(1), rs.q.slice(1), `${name} step ${k + 1}: q[1:]`);
    close(gs.reading, rs.reading, `${name} step ${k + 1}: reading`);
  }
  close(g.couples, r.couples, name + ': the alternations');
  close(g.rounds, r.rounds, name + ': the rounds');
  close(g.freeSolves, r.freeSolves, name + ': the free solves');
  close(g.refinedField, r.refinedField, name + ': the refined box');
  const fin = (f) => Object.assign({}, f, { q: f.q ? f.q.slice(1) : null });
  close(fin(g.final), fin(r.final), name + ': the final state');
}
const fx = got.fixed.couples.map((c) => (c.refined ? `细化 I_p ${(c.refined.ip / 1e3).toFixed(1)} kA` : '细化拒绝'));
console.log(`validate-worker-evolve-couple: ${Object.keys(CASES).length} 个配置在 ${id} 上到 ${REL.toExponential(0)}`
            + `（实测最坏 ${worst.toExponential(2)}），三块两次交替（fixed：${fx.join(' · ')}），`
            + `beta0 ${got.plain.couples.map((c) => c.beta0.toFixed(4)).join(' → ')}，`
            + `T_e(0) 终值 ${got.plain.final.te[0].toFixed(1)} eV`);
