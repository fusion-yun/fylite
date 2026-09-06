// The page's SUMMARY of a solved field, held against a fixture — 第三十九刀
// (2026-09-06): `summarize` (the 181-point boundary and its shape metrics,
// the flux segments, the criteria — li(3), strike points, X-points, wall gap,
// the control rows' achievement, the feedback ratio — the traced surfaces and,
// with a profile family or table, the profiles and q) moves onto
// `code/summary`.  This gate records what the OLD path answered for the
// `solve` command (analytic family and profile table, six surfaces, one
// strike row and one gap row) and for one `design` pass, and holds the door
// to it bit for bit.
//
// ★Why a fixture: the summary is geometry, and every step of it is the
// kernel's on both paths.  A number that moves when the work moves is a
// transcription error, not a rounding difference.
//
// Run: node app/tests/validate-worker-summary.mjs [--record]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets') + path.sep;
const FIX = path.join(HERE, 'fixtures', 'worker-summary.json');
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
const R = M.reference, tf = globalThis.FyDevice.tf(M);
const chan = Array.from(R.aturns), ip = R.ip;
const lim = M.limiter, k5 = Math.min(5, lim.r.length - 1);
//: one strike row on a wall vertex, one outward gap row through the geometric centre
const CONTROL = [
  { kind: 'strike', r: lim.r[k5], z: lim.z[k5], w: 1, label: 'leg' },
  { kind: 'gap', r0: tf.r0, z0: 0, dr: 1, dz: 0, value: 0.05, w: 1, label: 'out' },
];
const nT = 41, tab = { x: [], pprime: [], ffprime: [] };
for (let i = 0; i < nT; i++) {
  const x = i / (nT - 1), s = Math.pow(Math.max(1 - Math.pow(x, 1.4), 0), 1.1);
  tab.x.push(x); tab.pprime.push(s); tab.ffprime.push(0.3 * s);
}
const SOLVE = { maxIter: 600, relax: 0.3, tol: 1e-9 };
const bb = globalThis.FyDevice.bbox(M);
const rgeo = 0.5 * (bb.rmin + bb.rmax), amax = 0.5 * (bb.rmax - bb.rmin);
const target = { r0: rgeo, z0: 0.5 * (bb.zmin + bb.zmax), a: 0.6 * amax, kappa: 1.6, deltaU: 0.4, deltaL: 0.5 };
const CONFIGS = {
  analytic: { cmd: 'solve', chan, prof: { beta0: 0.60, emp: 1.40, enp: 1.10, r0: tf.r0 }, ip, solve: SOLVE,
              surfaces: 6, control: CONTROL, vertical: false },
  table: { cmd: 'solve', chan, prof: { tab }, ip, solve: SOLVE, surfaces: 4, control: CONTROL, vertical: false },
  bare: { cmd: 'solve', chan, prof: { beta0: 0.55, emp: 1, enp: 1, r0: tf.r0 }, ip, solve: SOLVE,
          surfaces: 0, control: [], vertical: false },
  design: { cmd: 'design', chan, target, ip, warm: true, prof: { beta0: 0.55, emp: 1, enp: 1, r0: target.r0 },
            schedule: [0.1, 0.03], gamma: 0.4, nPoints: 24, xWeight: 0, control: CONTROL,
            solve: { maxIter: 400, relax: 0.3, tol: 1e-8 }, vertical: false },
};

const arr = (v) => (v === null || v === undefined) ? null : Array.from(v);
function pick(sum) {
  const c = sum.criteria;
  return {
    psiAxis: sum.psiAxis, psiBnd: sum.psiBnd, axisR: sum.axisR, axisZ: sum.axisZ, ip: sum.ip,
    iterations: sum.iterations, residual: sum.residual, bndKind: sum.bndKind, fbAmp: sum.fbAmp,
    lcfs: arr(sum.lcfs), shape: sum.shape,
    fluxSegs: sum.fluxSegs ? { inner: sum.fluxSegs.inner.map(arr), outer: sum.fluxSegs.outer.map(arr), n: sum.fluxSegs.n } : null,
    criteria: c ? { q95: c.q95, q0: c.q0, li3: c.li3, fbRatio: c.fbRatio, strike: c.strike, xpts: c.xpts, gap: c.gap,
                    control: (c.control || []).map((r) => ({ kind: r.kind, ok: r.ok, want: r.want, got: r.got, at: r.at, seg: r.seg })) } : null,
    surfaces: sum.surfaces ? sum.surfaces.map((s) => ({ x: s.x, r0: s.r0, a: s.a, kappa: s.kappa, delta: s.delta, poly: s.poly })) : null,
    profiles: sum.profiles ? { x: arr(sum.profiles.x), pprime: arr(sum.profiles.pprime), ffprime: arr(sum.profiles.ffprime),
                               p: arr(sum.profiles.p), jc: sum.profiles.jc } : null,
    q: sum.q ? { x: arr(sum.q.x), q: arr(sum.q.q), f: arr(sum.q.f), q0: sum.q.q0, q95: sum.q.q95 } : null,
  };
}

const got = {};
for (const [name, msg] of Object.entries(CONFIGS)) {
  await send(msg);
  const m = take(msg.cmd);
  got[name] = pick(m.result);
}

if (RECORD) {
  writeFileSync(FIX, JSON.stringify({ device: id, configs: got }));
  console.log(`recorded ${Object.keys(got).length} summaries on ${id} -> ${FIX}`);
  process.exit(0);
}
if (!existsSync(FIX)) { console.log('跳过：没有夹具（先 --record）'); process.exit(0); }
const want = JSON.parse(readFileSync(FIX, 'utf8'));
assert.equal(want.device, id);
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
assert.equal(bad.length, 0, 'the summary moved:\n  ' + bad.slice(0, 20).join('\n  ') + (bad.length > 20 ? `\n  … ${bad.length} in all` : ''));
const a = got.analytic;
console.log(`validate-worker-summary: ${Object.keys(want.configs).length} summaries on ${id} bit for bit; analytic: q95 ${a.q ? a.q.q95.toFixed(3) : '—'}, `
            + `${a.criteria.strike.length} strike legs, ${a.criteria.xpts.length} X-points, gap ${a.criteria.gap ? a.criteria.gap.gap.toFixed(3) : '—'}, `
            + `${a.surfaces.length} surfaces, boundary ${a.lcfs.length / 2} points`);
