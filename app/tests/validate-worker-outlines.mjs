// The model page's outlines, held against a fixture — 第四十五刀 (2026-09-06):
// `evOutlines` (six flux surfaces at fixed psi_N levels and the boundary at
// 0.995, traced on a solved field with the device limiter, or drawn from the
// Miller family for a metric that has no field) moves onto `code/outlines`.
// This gate calls the worker's own helper on both routes — a field from the
// `solve` command on EAST, and a Miller geometry — records what the old path
// drew, and holds the door to it bit for bit.
//
// Run: node app/tests/validate-worker-outlines.mjs [--record]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets') + path.sep;
const FIX = path.join(HERE, 'fixtures', 'worker-outlines.json');
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
//: a field: one solve on the reference currents
await send({ cmd: 'solve', chan: Array.from(R.aturns), prof: { beta0: 0.60, emp: 1.40, enp: 1.10, r0: tf.r0 }, ip: R.ip,
             solve: { maxIter: 600, relax: 0.3, tol: 1e-9 }, surfaces: 0, control: [], vertical: false });
const eq = take('solve').result;
const grid = globalThis.grid;
const field = { psi: eq.psi, psiAxis: eq.psiAxis, psiBnd: eq.psiBnd, axisR: eq.axisR, axisZ: eq.axisZ,
                r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz, nr: grid.nr, nz: grid.nz,
                limR: M.limiter.r, limZ: M.limiter.z };
const CONFIGS = {
  field: [{ source: 'field' }, field],
  miller: [{ source: 'miller', r0: tf.r0, a: 0.42, kappa: [1.7], delta: [0.45] }, null],
};
const arr = (v) => (v === null || v === undefined) ? null : Array.from(v);
const got = {};
for (const [name, [geo, ctx]] of Object.entries(CONFIGS)) {
  const o = globalThis.evOutlines(geo, ctx);
  got[name] = { outlines: o.outlines.map(arr), lcfs: arr(o.lcfs), limR: arr(o.limR), limZ: arr(o.limZ),
                axisR: o.axisR, axisZ: o.axisZ, source: o.source, view: o.view };
}
if (RECORD) {
  writeFileSync(FIX, JSON.stringify({ device: id, configs: got }));
  console.log(`recorded ${Object.keys(got).length} outline sets on ${id} -> ${FIX}`);
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
assert.equal(bad.length, 0, 'the outlines moved:\n  ' + bad.slice(0, 20).join('\n  ') + (bad.length > 20 ? `\n  … ${bad.length} in all` : ''));
console.log(`validate-worker-outlines: ${Object.keys(want.configs).length} outline sets on ${id} bit for bit; field: ${got.field.outlines.length} surfaces, `
            + `boundary ${got.field.lcfs ? got.field.lcfs.length / 2 : 0} points; miller: ${got.miller.outlines.length} surfaces`);
