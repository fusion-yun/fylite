// The interp page's g-file source: the kernel's traced ladder IS the page's own.
//
// ★第二十七刀 (2026-09-05): `interpRun` on a g-file binds the page's equilibrium
// document (full-turn Wb, axis at the maximum — `fylite:psi_convention`) and the
// kernel traces the ladder.  Until that cut the kernel read every document as
// per radian, so this path's rho_tor came out exactly sqrt(2 pi) too large —
// measured, and nothing held it.  The fixture was recorded when the page still
// carried its own ladder spelling (`evLadderMetric`: span / 2 pi, its level rule,
// 121 theta points) and the two paths were measured EQUAL (worst relative
// difference 0); ★第二十八刀 retired that page function, so the fixture is the
// spelling now, held bit for bit.
//
// Run: node app/tests/validate-worker-interp-gfile.mjs [--record]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets') + path.sep;
const FIX = path.join(HERE, 'fixtures', 'worker-interp-gfile.json');
const RECORD = process.argv.includes('--record');
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

const got = JSON.parse(JSON.stringify({ rho: Array.from(out.rho), vprime: Array.from(out.vprime), gm3: Array.from(out.gm3),
                                         gm7: Array.from(out.gm7), psin: Array.from(out.psin), aMinor: out.aMinor,
                                         te: Array.from(out.te), chiE: Array.from(out.chiE) }));
if (RECORD) {
  writeFileSync(FIX, JSON.stringify(got));
  console.log(`recorded ${got.rho.length} surfaces -> ${path.relative(process.cwd(), FIX)}`);
  process.exit(0);
}
const ref = JSON.parse(readFileSync(FIX, 'utf8'));
for (const key of ['rho', 'vprime', 'gm3', 'gm7', 'psin', 'te', 'chiE'])
  assert.deepEqual(got[key], ref[key], `${key} bit for bit`);
assert.equal(got.aMinor, ref.aMinor, 'a bit for bit');
console.log(`validate-worker-interp-gfile: g-file 档的梯子逐位（${got.rho.length} 级，夹具录于页面自己的拼法与内核相等之时），rho_edge ${got.rho[got.rho.length - 1].toFixed(4)} m，a ${got.aMinor.toFixed(4)} m`);
