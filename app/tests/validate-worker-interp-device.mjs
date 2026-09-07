// The interp page's device tier: the free solve and its ladder, off the kernel.
//
// ★第二十九刀 (2026-09-05): `interpRun` on the device tier used to solve the free
// boundary in the worker (`freeSolve`), summarise it, interpolate q / F onto 33
// levels and trace the ladder itself (`evLadderFromSolve` → `evLadderMetric`,
// the flat `equilibriumLadder`); the evolve page's device tier had already
// moved onto `code/refit` (第十九刀), which answers the same free solve AND its
// ladder.  The fixture was recorded on the page path; the door path is held to
// 1e-7 relative (the couple gate's precedent: the two hosts assemble the coil
// flux with different quadrature spellings, measured ~1e-9).
//
// Run: node app/tests/validate-worker-interp-device.mjs [--record]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = (() => { const i = process.argv.indexOf('--site'); return (i >= 0 ? process.argv[i + 1] : path.join(HERE, '..', 'assets')) + path.sep; })();
const FIX = path.join(HERE, 'fixtures', 'worker-interp-device.json');
const BASE = 'http://127.0.0.1:0/';
const RECORD = process.argv.includes('--record');
const OUT = (() => { const i = process.argv.indexOf('--out'); return i >= 0 ? process.argv[i + 1] : FIX; })();
//: the relative tolerance the two flux assemblies allow (see the header)
const TOL = 1e-7;

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
//: ★★不再显式传 `lambda` —— 走**出厂缺省**（2026-09-07 用户裁定 3e-1，`worker.js`
//: 与内核 `case.rs` 两侧同一个数）。此前这里写死 1e-3，于是闸子守着一个不出厂的
//: 配置：缺省改了它也不红，而它自己那一档的病态（1e-13 的输入扰动动 2–11 % 的
//: 电流）反倒要靠夹具容差兜。缺省改动时这道闸该红，红了就重录并写下为什么。
send({ cmd: 'start', target, ip, nPoints: 24, xWeight: 0, control: [], iMax: null,
       nRing: 4, peaking: 1 });
const st = take('start');
inbox.splice(0, inbox.length);
//: ★the designed START is a linear isoflux answer, not an equilibrium, so two
//: passes of the anneal (the design page's own `design` command,
//: `code/discharge`) run before anything is interpreted: the alternation —
//: refinement included — must stand on currents a design would actually hand
//: over.
//:
//: ★★2026-09-07，缺省 λ 1e-3 → 3e-1 且换直接解之后，这一段的**数量级变了**，
//: 而且是变好的一侧。旧夹具（λ=1e-3 + 投影梯度）记的是一个**塌掉的**位形：
//: a_minor 0.0195 m —— 要的是 0.6·a_max ≈ 0.357 m，差了十八倍 —— `chiE` / `chiI`
//: 二十一级**全是 NaN**（那一档的解释性输运根本没算出东西），tau_E 0.51 ms，
//: W_th 1.5 kJ。新的这一份：a_minor 0.3572 m（就是要的那个数）、chi 有限
//: （4.1–98 m²/s）、gm3 / gm7 回到 O(1)、tau_E 60 ms、W_th 255 kJ。
//:
//: ★★**但自由边界解不收敛了，而且这一条不是本次改动能收的。** 旧的
//: `free.residual` 是 4.9e-8（`converged: false`，跑满 400 步），新的是 5.8e-2。
//: 实测把预算加到 1200 / 4000 步，残差是 4.2e-2 / 5.0e-2 —— **不随预算下降，
//: 停在 5e-2 上下**，所以那不是「步数不够」。旧的那个近零残差属于那个 2 cm 的
//: 塌解：几乎没有东西要收敛。**这是一个未决问题**（是自由边界解本身的缺陷，还是
//: 两趟退火尚未把边界送到位、relax=0.3 上的欠松弛），本闸只把两侧的数记下来，
//: 不替它下结论；`free.converged` 两侧同为 false，所以那一条断言仍然成立。
send({ cmd: 'design', chan: Array.from(st.chan), target, ip, warm: true,
       prof: { beta0: 0.55, emp: 1, enp: 1, r0: target.r0 },
       schedule: [0.1, 0.03], gamma: 0.4, nPoints: 24, xWeight: 0, control: [],
       solve: { maxIter: 400, relax: 0.3, tol: 1e-8 } });
const dsg = take('design');
const chan = Array.from(dsg.chan);
inbox.splice(0, inbox.length);

const arr = (v) => (v ? Array.from(v) : null);
const rho = Array.from({ length: 41 }, (_, i) => 1.5 * amax * i / 40);
const profiles = { rho, te: rho.map((r) => 3000 - 2800 * (r / (1.5 * amax)) ** 2),
                   ti: rho.map((r) => 2500 - 2300 * (r / (1.5 * amax)) ** 2),
                   ne: rho.map((r) => 4e19 - 3.5e19 * (r / (1.5 * amax)) ** 2) };
const spec = { geometry: 'device', n: 21, edgePsin: 0.95, a: target.a, r0: target.r0, kappa: 1.6, delta: 0.3, q95: 3.5,
               b0, ip, r0Src: target.r0, gradFloor: 0.05, pE: 2, pI: 1, depCentre: 0, depWidth: 0.3, vLoop: 0.5,
               alpha: false, brem: true, impurity: '', cImp: 0, zeff: 1.5, dtFraction: 0.5, freeMaxIter: 400 };
send({ cmd: 'interp', spec, profiles, chan });
const out = take('interp');
const got = JSON.parse(JSON.stringify({
  rho: arr(out.rho), psin: arr(out.psin), vprime: arr(out.vprime), gm3: arr(out.gm3), gm7: arr(out.gm7),
  te: arr(out.te), ti: arr(out.ti), ne: arr(out.ne), chiE: arr(out.chiE), chiI: arr(out.chiI),
  qE: arr(out.qE), qI: arr(out.qI), wTh: out.wTh, tauE: out.tauE, b0: out.b0, aMinor: out.aMinor, rMajor: out.rMajor,
  free: out.free, geoSource: out.geoSource,
}));
if (RECORD) {
  writeFileSync(OUT, JSON.stringify(got));
  console.log(`recorded ${got.rho.length} surfaces on ${id} -> ${path.relative(process.cwd(), OUT)}`);
  process.exit(0);
}
const ref = JSON.parse(readFileSync(FIX, 'utf8'));
let worst = 0;
const close = (a, b, key) => {
  if (Array.isArray(a)) { assert.equal(a.length, b.length, `${key}: length`); a.forEach((v, i) => close(v, b[i], `${key}[${i}]`)); return; }
  if (typeof a !== 'number') { assert.deepEqual(a, b, key); return; }
  if (Number.isNaN(a) && Number.isNaN(b)) return;
  const d = Math.abs(a - b) / Math.max(Math.abs(b), 1e-300);
  if (a === 0 && b === 0) return;
  worst = Math.max(worst, d);
  assert.ok(d <= TOL, `${key}: ${a} vs ${b} (rel ${d.toExponential(2)} > ${TOL})`);
};
for (const key of ['rho', 'psin', 'vprime', 'gm3', 'gm7', 'te', 'ti', 'ne', 'chiE', 'chiI', 'qE', 'qI', 'wTh', 'tauE', 'b0', 'aMinor', 'rMajor'])
  close(got[key], ref[key], key);
assert.equal(got.geoSource, ref.geoSource, 'geoSource');
assert.equal(got.free.converged, ref.free.converged, 'free.converged');
const fmt = (v, d) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(d) : 'n/a');
console.log(`validate-worker-interp-device: 装置档的解释性输运在 ${id} 上到 ${TOL}（实测最坏 ${worst.toExponential(2)}），${got.rho.length} 级，tau_E ${fmt(got.tauE, 4)} s，chi_e(0.5) ${fmt(got.chiE[Math.floor(got.chiE.length / 2)], 3)}`);
