// The design page's vertical-stability criterion, off `code/vstab`.
//
// ★第三十刀 (2026-09-05): `verticalOf` — the boundary trace, the plasma
// filaments, the coupling gradients to coils and vessel, the channel
// matrices, the stiffness and the plant — used to be written out in the
// worker on six flat exports.  `code/vstab` (sunk for Python from this very
// function) answers the same numbers off the device document, the page's
// equilibrium document and the channel currents.  The fixture was recorded on
// the page path; the door path is held to 1e-7 relative (the coil flux is
// assembled with two quadrature spellings, the couple gate's precedent).
//
// Run: node app/tests/validate-worker-vertical.mjs [--record]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = (() => { const i = process.argv.indexOf('--site'); return (i >= 0 ? process.argv[i + 1] : path.join(HERE, '..', 'assets')) + path.sep; })();
const FIX = path.join(HERE, 'fixtures', 'worker-vertical.json');
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
const CANDIDATES = ['best', 'cfetr', 'east', 'iter', 'west', 'jt60sa', 'cfedr'];
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
//: ★none of the shipped device documents the harness can parse carries a vessel,
//: and a vertical criterion without a wall is `null` on both paths.  So a
//: synthetic shell is put on the machine HERE — sixteen rectangles on an
//: ellipse around the target, one resistivity — and it reaches both paths the
//: same way: `elementArrays(M.vessel)` on the page's, `toFyo(M)` → the device
//: document's `wall/description_2d/vessel/unit` on the door's.
{
  const bb0 = globalThis.FyDevice.bbox(M);
  const rc = 0.5 * (bb0.rmin + bb0.rmax), zc = 0.5 * (bb0.zmin + bb0.zmax), ax = 0.5 * (bb0.rmax - bb0.rmin);
  M.vessel = Array.from({ length: 16 }, (_, k) => {
    const th = 2 * Math.PI * k / 16;
    return { r: rc + 0.75 * ax * Math.cos(th), z: zc + 1.2 * ax * Math.sin(th), w: 0.06, h: 0.06 };
  });
  M.vessel_resistivity_uohm_m = 0.76;
}
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

//: ★the DESIGN answer's own criterion (`summarize` at the design's pass): the
//: design's equilibrium is a plasma (q95 ~3); a cold `solve` on its currents
//: collapses on these decks, and a criterion on two filaments says nothing
const v = dsg.result && dsg.result.criteria && dsg.result.criteria.vertical;
assert.ok(v, 'no vertical criterion in the design answer: ' + JSON.stringify(dsg.result && dsg.result.criteria));
const sol = dsg;
const got = JSON.parse(JSON.stringify({ gamma: v.gamma, k: v.k, kIdeal: v.kIdeal, ratio: v.ratio, nFilaments: v.nFilaments,
                                         ip: sol.result.ip, q0: sol.result.q && sol.result.q.q0, q95: sol.result.criteria.q95, a: sol.result.shape && sol.result.shape.a }));
if (RECORD) {
  writeFileSync(OUT, JSON.stringify(got));
  console.log(`recorded the vertical criterion on ${id} -> ${path.relative(process.cwd(), OUT)}`);
  process.exit(0);
}
const TOL = 1e-7;
const ref = JSON.parse(readFileSync(FIX, 'utf8'));
let worst = 0;
for (const key of ['gamma', 'k', 'kIdeal', 'ratio', 'ip', 'q95', 'a']) {
  const a = got[key], b = ref[key];
  if (a === null && b === null) continue;
  const d = Math.abs(a - b) / Math.max(Math.abs(b), 1e-300);
  worst = Math.max(worst, d);
  assert.ok(d <= TOL, `${key}: ${a} vs ${b} (rel ${d.toExponential(2)} > ${TOL})`);
}
assert.equal(got.nFilaments, ref.nFilaments, 'nFilaments');
console.log(`validate-worker-vertical: 竖直模在 ${id} 上到 ${TOL}（实测最坏 ${worst.toExponential(2)}），gamma ${got.gamma.toExponential(3)} 1/s，k/k_ideal ${got.ratio === null ? 'n/a' : got.ratio.toFixed(4)}，${got.nFilaments} 根细丝，q95 ${got.q95.toFixed(2)}`);
