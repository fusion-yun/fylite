// The model page's turbulent-transport panel (`transport_turb`), held to the bit.
//
// ★第二十五刀 (2026-09-05): the panel's outer loop — Chang-Hinton chi on the bar's
// Miller surfaces, TGLF on the sampled radii, the relaxed total, one steady
// transport step — used to be written out in `worker.js::transportTurb` +
// `turbulentChi` on the flat exports (`neoChi` · `tglfUnits/Kygrid/Flux` ·
// `transportStep`), with the surface blocks (`neoBlocks`) and the metric
// (`metrics`) built on the page.  The fixture was recorded on THAT path; the
// worker now drives two doors per pass (`code/turbulence` on the extension
// binary, `code/transport` closure 3 on the core) and must land on the same
// bits.
//
// ★The message carries BOTH spellings: the old flat arrays (built here by the
// page's own transcriptions, read by the loop path when recording) and the
// bar's scalars (read by the door path).  Neither side reads the other's.
//
// Run: node app/tests/validate-worker-transport-turb.mjs [--record]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const argSite = process.argv.indexOf('--site');
const SITE = argSite > 0 ? path.resolve(process.argv[argSite + 1]) + path.sep : path.join(HERE, '..', 'assets') + path.sep;
const argOut = process.argv.indexOf('--out');
const FIX = argOut > 0 ? path.resolve(process.argv[argOut + 1]) : path.join(HERE, 'fixtures', 'worker-transport-turb.json');
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
const fy = globalThis.fy;

// --- the page's own prescriptions (scenario-model.js), transcribed for the record ---------
const EV_PER_KEV = 1e3, NE_UNIT = 1e19, MD = 3.3435837724e-27, QE = 1.602176634e-19;
const rhoGrid = (c) => { const x = new Float64Array(c.n); for (let i = 0; i < c.n; i++) x[i] = c.amin * i / (c.n - 1); return x; };
const rhoBar = (x, i) => (x[x.length - 1] > 0 ? x[i] / x[x.length - 1] : 0);
const tStart = (c, x, k) => { const rb = rhoBar(x, k); return c.edge + 2 * (1 - rb * rb); };
const chiGyroBohm = (teEv, bT, aM) => { const cs = Math.sqrt(teEv * QE / MD); const rhos = MD * cs / (QE * bT); return rhos * rhos * cs / aM; };
function metrics(c, x) {
  const q0 = 1.0, qa = c.q95, a = c.amin, rmaj = c.rmaj * a;
  const vp = new Float64Array(x.length), gr = new Float64Array(x.length), shear = new Float64Array(x.length);
  for (let i = 1; i < x.length; i++) {
    const rb = rhoBar(x, i), q = q0 + (qa - q0) * rb * rb, dq = 2 * (qa - q0) * rb;
    shear[i] = rb * dq / q;
    const g = fy.geoSurface({ rmin: x[i], rmaj, q, shear: shear[i], kappa: c.kappa, sKappa: 0, delta: c.delta, sDelta: 0, nTheta: 201 });
    vp[i] = g.volumePrime; gr[i] = g.fsaGradR2;
  }
  vp[0] = 0; gr[0] = gr.length > 1 ? gr[1] : 1;
  return { vprime: vp, gradR2: gr, qEdge: qa };
}
function neoBlocks(c, x) {
  const a = c.amin, b = c.bunit, ne0 = c.ne0, cpk = c.nepeak, n = x.length;
  const surf = new Float64Array(20 * n), ion = new Float64Array(6 * n), chigb = new Float64Array(n);
  const rmaj = c.rmaj * a, kap = c.kappa, del = c.delta, q0 = 1.0, qa = c.q95;
  for (let k = 0; k < n; k++) {
    const r = Math.max(rhoBar(x, k), 1e-6), q = q0 + (qa - q0) * r * r, shear = r * (2 * (qa - q0) * r) / q;
    const ne = ne0 * (1 - cpk * r * r) * NE_UNIT;
    const dlnnedr = (2 * cpk * r / Math.max(1 - cpk * r * r, 1e-6)) / a;
    const te = tStart(c, x, k) * EV_PER_KEV, o = 20 * k;
    surf[o] = a; surf[o + 1] = r * a; surf[o + 2] = rmaj; surf[o + 3] = 0; surf[o + 4] = 0; surf[o + 5] = 0;
    surf[o + 6] = q; surf[o + 7] = shear; surf[o + 8] = kap; surf[o + 9] = 0; surf[o + 10] = del; surf[o + 11] = 0;
    surf[o + 12] = 0; surf[o + 13] = 0; surf[o + 14] = b; surf[o + 15] = te; surf[o + 16] = ne;
    surf[o + 17] = dlnnedr; surf[o + 18] = dlnnedr; surf[o + 19] = 0;
    const i6 = 6 * k;
    ion[i6] = 1.0; ion[i6 + 1] = MD; ion[i6 + 2] = ne; ion[i6 + 3] = te; ion[i6 + 4] = dlnnedr; ion[i6 + 5] = dlnnedr;
    chigb[k] = chiGyroBohm(te, b, a);
  }
  return { surf, ion, nion: 1, signb: -1, signq: 1, rhoStar: 0.001, nTheta: 17, tToEv: EV_PER_KEV, chigb };
}
function message(c) {
  const x = rhoGrid(c), m = metrics(c, x);
  const src = new Float64Array(x.length), y0 = new Float64Array(x.length), metric = new Float64Array(x.length);
  for (let i = 0; i < x.length; i++) {
    src[i] = c.power * Math.exp(-Math.pow(rhoBar(x, i) / c.width, 2));
    y0[i] = tStart(c, x, i);
    metric[i] = m.vprime[i] * m.gradR2[i];
  }
  const vel = new Float64Array(x.length); vel.fill(c.pinch);
  const radii = [];
  for (let j = 0; j < c.nrad; j++) radii.push(Math.round(1 + (x.length - 3) * (j / Math.max(1, c.nrad - 1))));
  const ky = [], lo = 0.05, hi = 0.8;
  for (let kk = 0; kk < c.nky; kk++) ky.push(+(lo * Math.pow(hi / lo, kk / Math.max(1, c.nky - 1))).toFixed(6));
  return {
    cmd: 'transport_turb', neo: neoBlocks(c, x),
    spec: { x, y0, vprime: m.vprime, metric, velocity: vel, source: src, edge: c.edge, chi0: c.chi0, dPc: c.dpc,
            radii, ky, satRule: 1, width: 1.65, outer: c.outer, relax: 0.5, tol: 1e-4 },
    //: the door path's spelling: the bar itself
    bar: { n: c.n, amin: c.amin, rmaj: c.rmaj, kappa: c.kappa, delta: c.delta, q95: c.q95, bunit: c.bunit,
           ne0: c.ne0, nepeak: c.nepeak, chi0: c.chi0, power: c.power, width: c.width, edge: c.edge,
           pinch: c.pinch, dpc: c.dpc, nrad: c.nrad, nky: c.nky, outer: c.outer, relax: 0.5, tol: 1e-4 },
  };
}

const DEFAULTS = { n: 41, amin: 0.6, rmaj: 3, kappa: 1.6, delta: 0.3, q95: 3.5, bunit: 2, ne0: 3, nepeak: 0.4,
                   chi0: 0.6, power: 12, width: 0.36, edge: 0.3, pinch: 0, dpc: 0, nrad: 6, nky: 6, outer: 6 };
const CASES = {
  //: the bar as it opens
  bar: { ...DEFAULTS },
  //: a pinch, a Pfirsch-Schlüter term, a steeper density, fewer radii — and
  //: enough outer passes that the settle rule can fire
  pinched: { ...DEFAULTS, pinch: -0.5, dpc: 0.5, nepeak: 0.6, nrad: 4, nky: 4, outer: 8, n: 31, q95: 2.8 },
};

const got = {};
for (const [name, c] of Object.entries(CASES)) {
  inbox.splice(0, inbox.length);
  send(message(c));
  const t0 = Date.now();
  while (!inbox.some((m) => m.type === 'transport_turb' || m.type === 'error')) {
    if (Date.now() - t0 > 900000) throw new Error(`${name}: no answer in 15 min`);
    await new Promise((r) => setTimeout(r, 25));
  }
  const errs = inbox.filter((m) => m.type === 'error');
  assert.equal(errs.length, 0, `${name}: worker error: ${errs.map((e) => e.message).join('; ')}`);
  const fin = inbox.find((m) => m.type === 'transport_turb');
  const passes = inbox.filter((m) => m.type === 'turb_pass')
    .map((p) => ({ it: p.it, t0: p.t0, move: p.move, chiMin: p.chiMin, chiMax: p.chiMax }));
  got[name] = JSON.parse(JSON.stringify({
    y: Array.from(fin.y), chi: Array.from(fin.chi), chiNeo: Array.from(fin.chiNeo), chiTurb: Array.from(fin.chiTurb),
    subX: Array.from(fin.subX), subChi: Array.from(fin.subChi),
    outer: fin.outer, settled: fin.settled, iterations: fin.iterations, converged: fin.converged, residual: fin.residual,
    passes,
  }));
  assert.ok(got[name].y.length === c.n && got[name].chi.length === c.n, `${name}: the answer is on the bar's grid`);
  assert.ok(got[name].subChi.length === c.nrad && got[name].passes.length === got[name].outer, `${name}: one pass per outer iteration, one sub-grid value per radius`);
  assert.ok(got[name].chiTurb.some((v) => v > 0), `${name}: the turbulence transports something`);
}

if (RECORD) {
  writeFileSync(FIX, JSON.stringify(got));
  console.log(`recorded ${Object.keys(got).join(' ')} -> ${path.relative(process.cwd(), FIX)}`);
  process.exit(0);
}
const ref = JSON.parse(readFileSync(FIX, 'utf8'));
for (const name of Object.keys(CASES)) {
  for (const key of ['y', 'chi', 'chiNeo', 'chiTurb', 'subX', 'subChi'])
    assert.deepEqual(got[name][key], ref[name][key], `${name}: ${key} bit for bit`);
  for (const key of ['outer', 'settled', 'iterations', 'converged', 'residual'])
    assert.deepEqual(got[name][key], ref[name][key], `${name}: ${key}`);
  assert.deepEqual(got[name].passes, ref[name].passes, `${name}: the per-pass readings bit for bit`);
}
const b = got.bar;
console.log(`validate-worker-transport-turb: 2 个配置逐位（默认 · 夹箍+PS+陡密度），bar ${b.outer} 轮${b.settled ? '收敛' : '未收敛'}，T(0) 终值 ${b.y[0].toFixed(4)} keV，chi 范围 ${Math.min(...b.chi).toFixed(3)}–${Math.max(...b.chi).toFixed(3)} m^2/s`);
