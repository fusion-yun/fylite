// 自由边界解的残差**不是**位形达标的判据 —— 同一台机器、同一个目标，两个岭
//
// ★★这道闸要说的一件事（F-34，2026-09-12 实测）。`free.residual` 是不动点迭代
// 的自洽度，**不是**「解出来的位形是不是要的那一个」。两者在 EAST 公共卡上不仅
// 不同，这一段 λ 上还**反着走**：
//
// =======  ============  ==========  ==========  ============  =========
// `lam`    `start_cond`  `psiRms`    `aMinor`    `shapeErr`    `residual`
// =======  ============  ==========  ==========  ============  =========
// 1e-3     2.5562e8      4.198e-4    0.3051     0.0208        7.201e-3
// 1e-2     2.7410e6      9.536e-4    **0.0195**  **0.9375**    **1.627e-5**
// 3e-2     3.0476e5      2.234e-3    0.3091     **0.0079**    3.843e-3
// 1e-1     2.7431e4      1.255e-2    0.3279     0.0524        5.557e-3
// 3e-1     3.0488e3      2.866e-2    0.3572     0.1463        5.833e-2
// 1.0      2.7530e2      4.727e-2    0.4167     0.3372        7.111e-4
// =======  ============  ==========  ==========  ============  =========
//
// （目标 `a` = 0.3116 m；`shapeErr` = |aMinor − a|/a；κ₂ 由 `start_cond` 报出，见
// `python/tests/test_start_design_conditioning.py`。`solve.maxIter` 全程 400。）
//
// ★★两条**已测**的结论：
//
//   1. **残差不随 κ₂ 单调**。κ₂ 扫了六个量级（2.55e8 → 2.75e2），残差在
//      [1.6e-5, 5.8e-2] 里来回走，没有次序。所以「设计那一步的落点越可复现，
//      自由解越收敛」这个假设**被否掉了** —— F-16 报出来的 κ₂ 界定的是「输入扰动
//      把电流推多远」，不是「自由解收不收敛」。
//   2. **最小的残差属于一个塌掉的位形**：λ=1e-2 上 aMinor 0.0195 m，是要的
//      0.3116 m 的 6 %，而它的残差 1.63e-5 是全表最小的 —— 比位形最准那一档
//      （λ=3e-2，shapeErr 0.79 %）小 236 倍。**一个只读 `free.residual` 的验收
//      判据可以被一次塌解满足。** 这就是这道闸钉住的事。
//
// ★**推测（未测）**：要的那个位形不是所设压强/电流剖面的平衡，于是电流越是把它
// 按到目标上，不动点迭代越是被推离它自己的解 —— 这能解释 1 与 2 的反向，但本闸
// 不下这个结论，它只钉住「残差与位形是两件事」。
//
// ★变红的两种读法：**(a)** 塌解不再出现（λ=1e-2 上 aMinor 回到 O(0.3)）—— 那是
// 好消息，重测整表并改上面的数；**(b)** 次序反了（塌解的残差不再最小）—— 那是
// 残差的定义或 droop trim 动了，先看 `validate-freeconv.mjs`。
//
// Run: node app/tests/validate-free-residual-vs-shape.mjs
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = (() => { const i = process.argv.indexOf('--site'); return (i >= 0 ? process.argv[i + 1] : path.join(HERE, '..', 'assets')) + path.sep; })();
const BASE = 'http://127.0.0.1:0/';
//: 塌解那一档与位形最准那一档。两个数就够说明「残差与位形是两件事」
const LAM_COLLAPSE = 1e-2;
const LAM_ON_TARGET = 3e-2;

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

//: 与 `validate-worker-interp-device.mjs` 同一条取机器的路子
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

const bb = globalThis.FyDevice.bbox(M), tf = globalThis.FyDevice.tf(M);
const rgeo = 0.5 * (bb.rmin + bb.rmax), amax = 0.5 * (bb.rmax - bb.rmin);
const target = { r0: rgeo, z0: 0.5 * (bb.zmin + bb.zmax), a: 0.6 * amax, kappa: 1.6, deltaU: 0.4, deltaL: 0.5 };
const b0 = Math.abs(tf.b0 * tf.r0 / rgeo);
const ip = 2 * Math.PI * target.a * target.a * b0 * (1 + target.kappa * target.kappa)
           / (2 * 4e-7 * Math.PI * rgeo * 3.5);
const rho = Array.from({ length: 41 }, (_, i) => 1.5 * amax * i / 40);
const profiles = { rho, te: rho.map((r) => 3000 - 2800 * (r / (1.5 * amax)) ** 2),
                   ti: rho.map((r) => 2500 - 2300 * (r / (1.5 * amax)) ** 2),
                   ne: rho.map((r) => 4e19 - 3.5e19 * (r / (1.5 * amax)) ** 2) };

//: 一档 = 设计一次起始电流 → 两趟退火 → 解释栏的自由解，与
//: `validate-worker-interp-device.mjs` 逐个设置相同，只有 `lambda` 不同
const atRidge = (lambda) => {
  send({ cmd: 'start', target, ip, nPoints: 24, xWeight: 0, control: [], iMax: null,
         nRing: 4, peaking: 1, lambda });
  const st = take('start');
  inbox.splice(0, inbox.length);
  send({ cmd: 'design', chan: Array.from(st.chan), target, ip, warm: true, lambda,
         prof: { beta0: 0.55, emp: 1, enp: 1, r0: target.r0 },
         schedule: [0.1, 0.03], gamma: 0.4, nPoints: 24, xWeight: 0, control: [],
         solve: { maxIter: 400, relax: 0.3, tol: 1e-8 } });
  const chan = Array.from(take('design').chan);
  inbox.splice(0, inbox.length);
  const spec = { geometry: 'device', n: 21, edgePsin: 0.95, a: target.a, r0: target.r0, kappa: 1.6, delta: 0.3, q95: 3.5,
                 b0, ip, r0Src: target.r0, gradFloor: 0.05, pE: 2, pI: 1, depCentre: 0, depWidth: 0.3, vLoop: 0.5,
                 alpha: false, brem: true, impurity: '', cImp: 0, zeff: 1.5, dtFraction: 0.5, freeMaxIter: 400 };
  send({ cmd: 'interp', spec, profiles, chan });
  const out = take('interp');
  inbox.splice(0, inbox.length);
  return { psiRms: st.psiRms, aMinor: out.aMinor, free: out.free,
           shapeErr: Math.abs(out.aMinor - target.a) / target.a };
};

const collapse = atRidge(LAM_COLLAPSE);
const onTarget = atRidge(LAM_ON_TARGET);

//: ①两档都得**是**自由解跑出来的东西，否则下面的比较没有对象
for (const [name, r] of [['collapse', collapse], ['onTarget', onTarget]]) {
  assert.ok(Number.isFinite(r.free.residual) && r.free.residual > 0,
            `${name}: free.residual 不是有限正数（${r.free.residual}）—— 自由解没跑`);
  assert.ok(Number.isFinite(r.aMinor) && r.aMinor > 0,
            `${name}: aMinor 不是有限正数（${r.aMinor}）`);
}

//: ②λ=1e-2 那一档**塌了**：小半径不到要的五分之一（实测 6.3 %）
assert.ok(collapse.aMinor < 0.2 * target.a, (
  `λ=${LAM_COLLAPSE} 上没有塌解：aMinor ${collapse.aMinor.toFixed(4)} m 对目标 ` +
  `${target.a.toFixed(4)} m（实测 0.0195 m）。若位形回到 O(0.3) 这是好消息 —— ` +
  '重测整表并改抬头里的数，这道闸的对象就不在了'));

//: ③而它的残差是两档里**更小**的那一个 —— 这就是「残差不是位形判据」
assert.ok(collapse.free.residual < onTarget.free.residual, (
  `塌解的残差 ${collapse.free.residual.toExponential(3)} 不再小于位形最准那一档的 ` +
  `${onTarget.free.residual.toExponential(3)} —— 次序反了，先看 validate-freeconv.mjs ` +
  '里残差的定义与 droop trim'));
//: 实测 236 倍；界取 10 倍，留一个量级余地，问的是「次序」而不是某一位
assert.ok(onTarget.free.residual > 10 * collapse.free.residual, (
  `两档的残差只差 ${(onTarget.free.residual / collapse.free.residual).toFixed(1)} 倍` +
  '（实测 236 倍）—— 反向的幅度塌了，重测整表'));

//: ④位形那一面是反过来的：塌解的位形误差比位形最准那一档大两个量级（实测 118 倍）
assert.ok(collapse.shapeErr > 10 * onTarget.shapeErr, (
  `位形误差只差 ${(collapse.shapeErr / onTarget.shapeErr).toFixed(1)} 倍（实测 118 倍）`));

//: ⑤两档都**没有**报收敛 —— 所以这件事与「谁收敛了」无关，纯粹是残差读不出位形
for (const [name, r] of [['collapse', collapse], ['onTarget', onTarget]]) {
  assert.equal(r.free.converged, false, (
    `${name}: 自由解报了收敛（residual ${r.free.residual.toExponential(3)}）—— ` +
    '那是新情况，整表重测'));
}

console.log(`validate-free-residual-vs-shape: ${id} 上残差与位形反向 —— ` +
  `λ=${LAM_COLLAPSE}：aMinor ${collapse.aMinor.toFixed(4)} m（位形误差 ` +
  `${(100 * collapse.shapeErr).toFixed(1)} %）残差 ${collapse.free.residual.toExponential(3)}；` +
  `λ=${LAM_ON_TARGET}：aMinor ${onTarget.aMinor.toFixed(4)} m（${(100 * onTarget.shapeErr).toFixed(2)} %）` +
  `残差 ${onTarget.free.residual.toExponential(3)} —— 残差差 ` +
  `${(onTarget.free.residual / collapse.free.residual).toFixed(0)} 倍，位形差 ` +
  `${(collapse.shapeErr / onTarget.shapeErr).toFixed(0)} 倍`);
