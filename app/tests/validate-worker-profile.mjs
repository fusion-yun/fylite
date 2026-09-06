// The profile bar's fit, held against a fixture — 第四十四刀 (2026-09-06):
// `profileFitRun` (the GCV sweep over polynomial orders, the best order's
// coefficients, its curve on 101 points and its values at the data) moves
// onto `code/profile_fit`.  Three point sets are fitted — a clean quadratic,
// a noisy pedestal-like shape with one point switched off, and a short set
// that only affords a line — recorded on the old path and held bit for bit:
// the fit is one weighted least-squares sweep on identical rows.
//
// Run: node app/tests/validate-worker-profile.mjs [--record]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets') + path.sep;
const FIX = path.join(HERE, 'fixtures', 'worker-profile.json');
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

function eastDoc() {
  const d = deviceDoc('east');
  if (d) return d;
  const dir = process.env.FYLITE_DEVICE_DIR;
  const f = dir && path.join(dir, 'fylite_device_east.json');
  return f && existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : null;
}
const doc = eastDoc();
if (!doc) { console.log('跳过：没有 EAST 装置文档（dist/facts/device/east.jsonld 或 $FYLITE_DEVICE_DIR/fylite_device_east.json）'); process.exit(0); }
const M = globalThis.FyoDevice.fromFyo(doc), id = 'east';
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

//: a deterministic noise: xorshift32, uniform in (-1, 1)
function noise(seed) {
  let s = seed >>> 0 || 1;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return (s >>> 8) / 8388608 - 1; };
}
const quad = (() => { const x = [], y = [], sg = []; for (let i = 0; i < 21; i++) { const t = i / 20; x.push(t); y.push(3 - 2 * t * t); sg.push(0.05); } return { x, y, sigma: sg }; })();
const ped = (() => {
  const g = noise(11), x = [], y = [], sg = [];
  for (let i = 0; i < 31; i++) { const t = i / 30; x.push(t); y.push(2 * Math.pow(Math.max(1 - t * t, 0), 1.5) + 0.3 + 0.05 * g()); sg.push(i === 7 ? 0 : 0.08); }
  return { x, y, sigma: sg };
})();
const line = { x: [0.1, 0.5, 0.9], y: [1.0, 0.8, 0.5], sigma: [0.1, 0.1, 0.1] };
const CONFIGS = {
  quad: { cmd: 'profile_fit', x: quad.x, y: quad.y, sigma: quad.sigma, maxOrder: 6, quantity: 'te' },
  pedestal: { cmd: 'profile_fit', x: ped.x, y: ped.y, sigma: ped.sigma, maxOrder: 8, quantity: 'ne' },
  line: { cmd: 'profile_fit', x: line.x, y: line.y, sigma: line.sigma, maxOrder: 4, quantity: 'ti' },
};
const arr = (v) => (v === null || v === undefined) ? null : Array.from(v);
const got = {};
for (const [name, msg] of Object.entries(CONFIGS)) {
  await send(msg);
  const m = take('profile');
  got[name] = { quantity: m.quantity, order: m.order, coef: arr(m.coef), sweep: m.sweep, chi2PerDof: m.chi2PerDof,
                rss: m.rss, n: m.n, x: arr(m.x), curve: arr(m.curve), at: arr(m.at) };
}
if (RECORD) {
  writeFileSync(FIX, JSON.stringify({ device: id, configs: got }));
  console.log(`recorded ${Object.keys(got).length} fits -> ${FIX}`);
  process.exit(0);
}
if (!existsSync(FIX)) { console.log('跳过：没有夹具（先 --record）'); process.exit(0); }
const want = JSON.parse(readFileSync(FIX, 'utf8'));
const bad = [];
function walk(a, b, p) {
  if (a === null || a === undefined || typeof a !== 'object') {
    const same = (a === b) || (typeof a === 'number' && typeof b === 'number' && Number.isNaN(a) && Number.isNaN(b))
      || (a === null && b === undefined) || (a === undefined && b === null);
    if (!same) bad.push(`${p}: ${a} vs ${b}`);
    return;
  }
  if (b === null || b === undefined || typeof b !== 'object') { bad.push(`${p}: object vs ${b}`); return; }
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) walk(a[k], b[k], p + '.' + k);
}
for (const name of Object.keys(want.configs)) walk(want.configs[name], JSON.parse(JSON.stringify(got[name])), name);
assert.equal(bad.length, 0, 'the fit moved:\n  ' + bad.slice(0, 20).join('\n  ') + (bad.length > 20 ? `\n  … ${bad.length} in all` : ''));
console.log(`validate-worker-profile: ${Object.keys(want.configs).length} fits bit for bit; orders ${Object.values(got).map((g) => g.order).join('/')}, `
            + `pedestal chi2/dof ${got.pedestal.chi2PerDof.toFixed(3)} on ${got.pedestal.n} points`);
