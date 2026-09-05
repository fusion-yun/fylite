// The interp page's g-file source: the kernel's traced ladder IS the page's own.
//
// ★第二十七刀 (2026-09-05): `interpRun` on a g-file binds the page's equilibrium
// document (full-turn Wb, axis at the maximum — `fylite:psi_convention`) and the
// kernel traces the ladder.  Until this cut the kernel read every document as
// per radian, so this path's rho_tor came out exactly sqrt(2 pi) too large —
// measured, and nothing held it.  This gate holds it: the ladder the kernel
// returns for the `interp` command equals `evLadderMetric` (the page's own
// spelling, span / 2 pi, its level rule, 121 theta points) on the same payload,
// to 1e-12 relative.  No fixture: it is one worker path against the other.
//
// Run: node app/tests/validate-worker-interp-gfile.mjs
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets') + path.sep;
const BASE = 'http://127.0.0.1:0/';

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

//: the synthetic g-file, already in the page's gauge (`gfilePayload`'s numbers,
//: dumped once by Python: psi = -2 pi psirz in [R, Z], axis at the maximum)
const g = JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'g_synthetic.page.json'), 'utf8'));
g.psi = Float64Array.from(g.psi);
const n = 31, edgePsin = 0.95;
const a = g.bndR.reduce((m, v) => Math.max(m, v), -1e9) - g.bndR.reduce((m, v) => Math.min(m, v), 1e9);
const spec = { geometry: 'gfile', n, edgePsin, a: a / 2, r0: g.rmaj, kappa: 1.6, delta: 0.3, q95: 3.5, b0: g.b0,
               ip: 4e5, r0Src: g.rmaj, gradFloor: 0.05, pE: 2, pI: 1, depCentre: 0, depWidth: 0.3, vLoop: 0,
               alpha: false, brem: false, impurity: '', cImp: 0, zeff: 1.5, dtFraction: 0.5 };
const rho = Array.from({ length: 41 }, (_, i) => 2.0 * i / 40);
const profiles = { rho, te: rho.map((r) => 3000 - 2900 * (r / 2) ** 2), ti: rho.map((r) => 2800 - 2700 * (r / 2) ** 2),
                   ne: rho.map((r) => 4e19 - 3.5e19 * (r / 2) ** 2) };
send({ cmd: 'interp', spec, profiles, gfile: g });
const errs = inbox.filter((m) => m.type === 'error');
assert.equal(errs.length, 0, 'worker error: ' + errs.map((e) => e.message).join('; '));
const out = inbox.find((m) => m.type === 'interp');
assert.ok(out, 'no interp answer');

//: the page's own ladder on the same payload
const lad = globalThis.evLadderMetric({
  psi: g.psi, psiAxis: g.psiAxis, psiBnd: g.psiBnd, axisR: g.axisR, axisZ: g.axisZ,
  gridR0: g.r0, gridZ0: g.z0, dr: g.dr, dz: g.dz, nr: g.nr, nz: g.nz,
  limR: Float64Array.from(g.limR), limZ: Float64Array.from(g.limZ),
  qTable: Float64Array.from(g.qTable), fTable: Float64Array.from(g.fTable),
  b0: Math.abs(g.b0), aMinor: out.aMinor, rMaj: g.rmaj, n, edgePsin, nTheta: 121, source: 'gfile' });
const close = (got, want, key) => {
  assert.equal(got.length, want.length, `${key}: ${got.length} vs ${want.length} surfaces`);
  let worst = 0;
  for (let i = 0; i < got.length; i++) {
    const d = Math.abs(got[i] - want[i]) / Math.max(Math.abs(want[i]), 1e-300);
    if (want[i] === 0 && got[i] === 0) continue;
    worst = Math.max(worst, d);
  }
  assert.ok(worst <= 1e-12, `${key}: worst relative difference ${worst.toExponential(2)} > 1e-12`);
  return worst;
};
const w = ['rho', 'vprime', 'gm3', 'gm7', 'psin'].map((k) => close(out[k], lad[k], k));
console.log(`validate-worker-interp-gfile: g-file 档的梯子与页面自己的拼法一致（${out.rho.length} 级，最坏 ${Math.max(...w).toExponential(1)}），rho_edge ${out.rho[out.rho.length - 1].toFixed(4)} m，a ${out.aMinor.toFixed(4)} m`);
