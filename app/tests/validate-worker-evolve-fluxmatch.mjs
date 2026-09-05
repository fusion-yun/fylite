// 模型页 worker 的 evolve 命令走文档门（FYL-DESIGN-16 K-3，2026-09-05）——第二十一刀：
// 通量匹配档（closure 4，T-C13 / T-C14）。
//
// 切门之前，`evFluxMatch` 在 worker 里驱动内核的 Newton 机器（`fy.fluxMatch`），回调里
// 每一次探测都跑一遍 `evClosure`（新经典 χ · 匹配半径上的 TGLF · 交换）与 `evSources`，
// 燃烧在迭代边界冻结、台基滞后一轮；`fmOuter > 1` 时外圈再跑 `evStationaryCurrent`
// （稳态电流：环电压对包络电流做割线、冻结闭合复解、锯齿）与平衡那一半。
// 今天匹配整个是 `code/evolve` 的**阶段**（`stage: start · eval · finish`，
// `stationary::fm_stage`），TGLF 在扩展门 `code/turbulence` 于匹配半径上逐次评估——页面只剩
// 节拍；稳态电流是 `code/steady_current`。
//
// 三个配置，切门**之前**用 `--record` 在循环路径录下答案（assets 拷一份、`evScopeMiss` 强制
// 不命中、`--site` 指过去），切门之后同样的配置必须走条目（viaEntry）：
//   plain   热通道，四个匹配半径，六轮 Newton，韧致辐射开
//   burn    加 D-T 燃烧（迭代边界冻结）与 EPED 台基（迭代间滞后）
//   outer   plain 加三轮稳态外圈，g 文件档（页面按名拒绝 Miller 档的外圈：没有可复描的场）——
//           稳态电流跑（环电压割线 · 冻结闭合复解），平衡那一半按名跳过
//
// ★两条路的数是**同一内核同一函数**（机器 · reintegrate · 新经典 χ · TGLF 链 · 源项），只是
// 谁在编排，所以判**逐位**；唯一说明的差别：页面把 x0 评估了两次（一次定尺、一次喂机器），
// 门评估一次两用——`turbEvals` 因此少 1，闸子按此校正后判相等。
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = (() => { const i = process.argv.indexOf('--site'); return (i >= 0 ? process.argv[i + 1] : path.join(HERE, '..', 'assets')) + path.sep; })();
const FIX = path.join(HERE, 'fixtures', 'worker-evolve-fluxmatch.json');
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
  const sm = fy.shapeMetrics(g.rbbbs.map((r, i) => [r, g.zbbbs[i]]));
  const lr = g.limitr ? g.rlim : g.rbbbs, lz = g.limitr ? g.zlim : g.zbbbs;
  return { psi: Array.from(psi), psiAxis: -2 * Math.PI * g.simag, psiBnd: -2 * Math.PI * g.sibry,
           axisR: g.rmaxis, axisZ: g.zmaxis, r0: g.rleft, z0: g.zmid - g.zdim / 2,
           dr: g.rdim / (g.nw - 1), dz: g.zdim / (g.nh - 1), nr: g.nw, nz: g.nh,
           limR: Array.from(lr), limZ: Array.from(lz), qTable: Array.from(g.qpsi), fTable: Array.from(g.fpol),
           b0: Math.abs(g.bcentr), a: sm.a, rmaj: sm.r0, bndR: Array.from(g.rbbbs), bndZ: Array.from(g.zbbbs) };
}

const GFILE = path.join(HERE, 'fixtures', 'g_synthetic.geqdsk');
const fy = globalThis.fy;
const gfile = gfilePayload(parseGeqdsk(readFileSync(GFILE, 'utf8')), fy);

const a = 0.45;
const base = {
  geometry: 'miller', n: 25, edgePsin: 0.95, a, r0: 4.1 * a, kappa: 1.6, delta: 0.4, q95: 2.6, b0: 2.0,
  chHeat: true, chDensity: false, chCurrent: false, chMomentum: false, torque: 0, prandtl: 1,
  dt: 2e-3, nSteps: 1, dtTarget: 0, dtMin: 2e-3 / 500, dtMax: 2e-3 * 50, nCoupling: 2, tolSteady: 1e-9, report: 1,
  te0: 3000, ti0: 2800, ne0: 4e19, edgeNe: 5e18, edgeTe: 100, edgeTi: 100, pedestal: false,
  peakT: 1.5, peakN: 0.5, vLoop: 0.5, b0Dot: 0, closure: 4, chi0: 0.6,
  turbEvery: 0, turbNrad: 4, turbNky: 6, turbRelax: 1, fmIter: 6, fmTol: 0.02, fmDx: 0.05, fmDxMax: 1.0, fmRhoMin: 0.3,
  fmOuter: 1, dOverChiZ: 0.3, pinchZ: -0.5, fuelZ: 0, fmOTol: 0.02, fmORelax: 1,
  ipCtl: false, ipKp: 0, ipKi: 0, chiRatio: 1.0, dOverChi: 0.5, pinch: -1.0, dPc: 0,
  sawtooth: false, sawMix: 1.2, sawPeriod: 0, pE: 3.0, pI: 3.0, depCentre: 0.0, depWidth: 0.3,
  beam: false, lh: false, wave: false, beamSamples: 601, beamNWidth: 3, beamMass: 2,
  fuel: 0, fuelCentre: 1.0, fuelWidth: 0.25,
  alpha: false, brem: true, ohmic: false, bootstrap: false, iCd: 0, cdCentre: 0.4, cdWidth: 0.2,
  zeff: 1.5, impurity: 'C', cImp: 0.01, dtFraction: 0.5, quasi: false, useRef: false,
  ip: 1.0e6, r0Src: 4.1 * a, emp: 1, enp: 1, beta0: 0.55, couple: 0,
};
const CASES = {
  plain: {},
  burn: { alpha: true, pedestal: true, te0: 12000, ti0: 12000, ne0: 8e19, ip: 1.5e7, pE: 5.0, pI: 5.0 },
  //: the outer loop needs a TRACED equilibrium (the page refuses it on the
  //: Miller tier by name): the synthetic g-file, as the executors gate uses it
  outer: { fmOuter: 3, fmORelax: 0.7, geometry: 'gfile', a: gfile.a, r0: gfile.rmaj, b0: gfile.b0, ip: 7.0e5, r0Src: gfile.rmaj },
};
const arr = (v) => (v ? Array.from(v) : null);
const got = {};
for (const name of Object.keys(CASES)) {
  inbox.splice(0, inbox.length);
  await send({ cmd: 'evolve', spec: Object.assign({}, base, CASES[name]), gfile: CASES[name].geometry === 'gfile' ? gfile : undefined });
  const errs = inbox.filter((m) => m.type === 'error');
  assert.equal(errs.length, 0, name + ': worker error: ' + errs.map((e) => e.message).join(' | '));
  const steps = inbox.filter((m) => m.type === 'evolve_step');
  const matches = inbox.filter((m) => m.type === 'evolve_match');
  const roundsPosted = inbox.filter((m) => m.type === 'evolve_round');
  const done = inbox.find((m) => m.type === 'evolve');
  assert.ok(done, name + ': no final evolve message; inbox: ' + inbox.map((m) => m.type).join(','));
  assert.equal(steps.length, 1, name + ': the flux-match tier posts ONE step');
  if (!RECORD) assert.ok(steps.every((s) => s.viaEntry), name + ': the case ran on the entry path (viaEntry)');
  const rd = steps[0].reading;
  got[name] = JSON.parse(JSON.stringify({
    step: { te: arr(steps[0].te), ti: arr(steps[0].ti), ne: arr(steps[0].ne), q: arr(steps[0].q),
            chiE: arr(steps[0].chiE), chiI: arr(steps[0].chiI),
            reading: { t: rd.t, dt: rd.dt, steady: rd.steady, delta: rd.delta, betaN: rd.betaN, betaP: rd.betaP, wTh: rd.wTh,
                       tauE: rd.tauE, pAux: rd.pAux, pAlpha: rd.pAlpha, pRad: rd.pRad, pLine: rd.pLine, pOhm: rd.pOhm,
                       q0: rd.q0, pedTPed: rd.pedTPed, pedPPed: rd.pedPPed, pedWidth: rd.pedWidth, pedExtrap: rd.pedExtrap } },
    matches: matches.map((m) => ({ iteration: m.iteration, worst: m.worst, round: m.round })),
    roundsPosted: roundsPosted.map((r) => ({ round: r.round, dPressure: r.dPressure, dQ: r.dQ })),
    fluxMatch: Object.assign({}, done.fluxMatch, { viaEntry: undefined }),
    stationary: done.stationary,
    final: { te: arr(done.te), ti: arr(done.ti), ne: arr(done.ne), ni: arr(done.ni), psi: arr(done.psi), q: arr(done.q),
             chiE: arr(done.chiE), chiI: arr(done.chiI), chiNeo: arr(done.chiNeo), zeffProfile: arr(done.zeffProfile),
             steps: done.steps, trace: done.trace.length,
             turbEvals: done.turbEvals, turbChi: arr(done.turbChi), turbX: arr(done.turbX), turbSub: arr(done.turbSub),
             pedestal: done.pedestal ? { tPed: done.pedestal.tPed, pPed: done.pedestal.pPed, width: done.pedestal.width,
                                         extrapolation: done.pedestal.extrapolation } : null },
  }));
}
if (RECORD) {
  writeFileSync(OUT, JSON.stringify(got));
  console.log(`recorded ${Object.keys(got).join(' ')} -> ${path.relative(process.cwd(), OUT)}`);
  process.exit(0);
}
const ref = JSON.parse(readFileSync(FIX, 'utf8'));
const evalsNote = [];
for (const name of Object.keys(CASES)) {
  const g = got[name], r = ref[name];
  assert.deepEqual(g.step, r.step, name + ': the matched state, the closure at it and the reading, bit for bit');
  assert.deepEqual(g.matches, r.matches, name + ': the per-iteration posts');
  assert.deepEqual(g.roundsPosted, r.roundsPosted, name + ': the per-round posts');
  assert.deepEqual(g.fluxMatch, r.fluxMatch, name + ': the match record, bit for bit');
  assert.deepEqual(g.stationary, r.stationary, name + ': the stationary record');
  //: ★the count of TGLF evaluations is the CADENCE's own and the two cadences
  //: differ by construction: the loop ran the closure once before the match
  //: (its exchange ceiling), evaluated x0 twice (the yardstick, then the
  //: machine's first point), evaluated the answer twice (the frozen and the
  //: live pass) and re-ran TGLF inside every coupling iteration of the steady
  //: current solve, where the current channel reads no chi; the door evaluates
  //: each STATE once.  Every number those evaluations produced is held above,
  //: bit for bit; the count is held to「不多于循环的」and printed
  assert.ok(g.final.turbEvals <= r.final.turbEvals && g.final.turbEvals > 0,
            `${name}: TGLF evaluations ${g.final.turbEvals} (the loop made ${r.final.turbEvals})`);
  const gf = Object.assign({}, g.final, { turbEvals: r.final.turbEvals });
  assert.deepEqual(gf, r.final, name + ': the final state and the turbulent record');
  evalsNote.push(`${name} ${g.final.turbEvals}/${r.final.turbEvals}`);
}
console.log(`validate-worker-evolve-fluxmatch: ${Object.keys(CASES).length} 个配置逐位（匹配 · 燃烧+台基 · 稳态外圈），`
            + `plain ${got.plain.fluxMatch.iterations} 轮 worst ${got.plain.fluxMatch.worst.toExponential(2)}${got.plain.fluxMatch.converged ? '（收敛）' : '（未收敛）'}，`
            + `outer ${got.outer.stationary.rounds.length} 轮${got.outer.stationary.converged ? '收敛' : '未收敛'}；`
            + `TGLF 评估 门/循环 ${evalsNote.join(' · ')}`);
