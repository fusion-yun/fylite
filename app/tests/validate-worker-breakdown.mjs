// The breakdown page's null design, held against a fixture — 第四十二刀
// (2026-09-06): `nullSolve` (the disc, the channel field on it, the bounded
// null design, |B| on the disc and on the whole box, the contours the page
// draws) moves onto `code/breakdown`.  This gate records what the page's own
// path answered for three specs on EAST — limits off, a uniform ampere-turn
// cap, a flux target with the reference currents as the design's anchor —
// and holds the door to it.
//
// ★Tolerance, stated: the currents are one bounded solve on identical rows
// and hold bit for bit.  |B| is `Math.hypot` on the page and libm's hypot in
// the kernel (one ulp apart in the last bit), and the RMS is a sequential sum
// on the page against a pairwise one in the kernel — so the field numbers,
// their maximum, and the contour segments cut from that map are held to
// 1e-13 relative, measured and written down here rather than hidden.
//
// Run: node app/tests/validate-worker-breakdown.mjs [--record]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets') + path.sep;
const FIX = path.join(HERE, 'fixtures', 'worker-breakdown.json');
const BASE = 'http://127.0.0.1:0/';
const RECORD = process.argv.includes('--record');
const TOL = 1e-13;

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
const tf = globalThis.FyDevice.tf(M), R = M.reference;
const base = { r0: tf.r0, z0: 0, radius: 0.3, bTol: 2e-3, nRing: 4, nTheta: 16, fluxTarget: null,
               weightNull: 1, weightFlux: 1, lam: 1e-12, xRef: null, iMax: null, nu: 3, nv: 3 };
const nCh = M.channels.length;
const CONFIGS = {
  free: base,
  capped: Object.assign({}, base, { iMax: new Array(nCh).fill(2.0e4) }),
  flux: Object.assign({}, base, { fluxTarget: 1.5, weightFlux: 3, xRef: R ? Array.from(R.aturns) : null,
                                  iMax: new Array(nCh).fill(6.0e4) }),
};

const arr = (v) => (v === null || v === undefined) ? null : Array.from(v);
function pick(r) {
  return { aturns: arr(r.aturns), iterations: r.iterations, converged: r.converged, bpol: arr(r.bpol),
           discR: arr(r.discR), discZ: arr(r.discZ), bMax: r.bMax, bRms: r.bRms, bCentre: r.bCentre, flux: r.flux,
           over: r.over, bind: r.bind, limits: arr(r.limits), bpolGrid: arr(r.bpolGrid), bpolScale: r.bpolScale,
           fluxSegs: { inner: r.fluxSegs.inner.map(arr), outer: r.fluxSegs.outer.map(arr), n: r.fluxSegs.n } };
}
const got = {};
for (const [name, spec] of Object.entries(CONFIGS)) {
  await send({ cmd: 'breakdown', spec });
  got[name] = pick(take('breakdown').result);
}
if (RECORD) {
  writeFileSync(FIX, JSON.stringify({ device: id, configs: got }));
  console.log(`recorded ${Object.keys(got).length} null designs on ${id} -> ${FIX}`);
  process.exit(0);
}
if (!existsSync(FIX)) { console.log('跳过：没有夹具（先 --record）'); process.exit(0); }
const want = JSON.parse(readFileSync(FIX, 'utf8'));
assert.equal(want.device, id);
const bad = [];
let worst = 0, worstAt = '—';
const EXACT = /\.(aturns|iterations|converged|over|bind|limits|discR|discZ)\b/;
function walk(a, b, p) {
  if (a === null || a === undefined || typeof a !== 'object') {
    if (typeof a === 'number' && typeof b === 'number' && !EXACT.test(p)) {
      const rel = Math.abs(a - b) / Math.max(Math.abs(a), Math.abs(b), 1e-300);
      if (Number.isNaN(a) && Number.isNaN(b)) return;
      if (rel > worst) { worst = rel; worstAt = p; }
      if (rel > TOL) bad.push(`${p}: ${a} vs ${b} (rel ${rel.toExponential(2)})`);
      return;
    }
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
assert.equal(bad.length, 0, 'the null design moved:\n  ' + bad.slice(0, 20).join('\n  ') + (bad.length > 20 ? `\n  … ${bad.length} in all` : ''));
const f = got.free;
console.log(`validate-worker-breakdown: ${Object.keys(want.configs).length} null designs on ${id}; currents bit for bit, fields to ${TOL} `
            + `(worst rel ${worst.toExponential(2)} at ${worstAt}); free: B_max ${(f.bMax * 1e3).toFixed(3)} mT in ${f.iterations} it, `
            + `${f.fluxSegs.inner.length} contour levels`);
