// The analysis page's one-member fit, off `code/reconstruction`.
//
// ★第三十一刀 (2026-09-05): `reconMember` — the inverse solve on the rows the
// page assembled, then the forward loop model, the fitted cell current, the
// 1-D profiles, q, l_i(3) — used to run on two solve exports and six
// post-processing exports.  `code/reconstruction` gained a ROWS-GIVEN tier
// for it: the page still assembles its rows (the twin's truth, the reader's
// channel table, the probe and chord blocks, the kinetic rows in their gauge
// — none of that moved), binds them on DISCHARGE slots beside the external
// flux it built, and reads the same numbers back.  The fixture was recorded
// on the page path and the door path is held to it BIT FOR BIT: the rows are
// the same kernel rows on the same grid, and the post-processing is the
// page's own spelling (`fitted_profiles` · `f_profile` · `loop_model`).
//
// ★Runs on EAST #137985 @ 4 s, the one deck with a reference discharge: the
// shipped decks carry no magnetics (best / cfetr: 0 loops, 0 probes), and a
// synthetic set on them was tried first — the twin's truth is a cold free
// solve on designed currents, and on those machines it does not hold a
// plasma the fit can recover (measured: 「no plasma formed」 / singular normal
// equations in every configuration).  The deck is read the way the kernel's
// own tests read it (`FYLITE_DEVICE_DIR`) when the staged copy is absent.
//
// Six configurations: the loops with the deck's kinetic rows (the page's
// stock question), the magnetics alone, the deck's probes on the raw basis,
// the coil currents fitted as observations (T-A5), and the twin twice (第三十二刀:
// its truth off `code/forward`), once with a vessel current injected.
//
// Run: node app/tests/validate-worker-recon.mjs [--record]
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = (() => { const i = process.argv.indexOf('--site'); return (i >= 0 ? process.argv[i + 1] : path.join(HERE, '..', 'assets')) + path.sep; })();
const FIX = path.join(HERE, 'fixtures', 'worker-recon.json');
const BASE = 'http://127.0.0.1:0/';
const RECORD = process.argv.includes('--record');
const OUT = (() => { const i = process.argv.indexOf('--out'); return i >= 0 ? process.argv[i + 1] : FIX; })();

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

//: ★EAST: the one deck with a reference discharge (35 loops, 79 probes, the
//: delivered reconstruction's channel values, the raw est2 basis beside it).
//: The staged copy first (`dist/facts/device/east.jsonld`, the way every
//: browser gate reads it); else the kernel repository's own page document
//: through `FYLITE_DEVICE_DIR` (the kernel's pytest environment); else skip.
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
const chan = Array.from(R.aturns);
const ip = R.ip;

/** The analysis page's `reconMessage`, stock controls, twin source. */
function message(over) {
  const m = {
    cmd: 'recon', source: 'deck', chan: chan.slice(), ip,
    prof: { beta0: 0.60, emp: 1.40, enp: 1.10, r0: tf.r0 },
    noise: 0.005, seed: 7, npp: 2, nff: 2,
    loopMask: null, loopScale: null, loopForce: null, loopMeasTotal: null,
    selfcalTol: 0.20, warmup: 40, solve: { maxIter: 800, relax: 0.3 },
    //: the delivered basis: the deck's channel values against the deck's Ip
    ipOverride: ip,
    mc: { loops: 0, coils: 0, basis: false },
    kinetic: { on: true, points: 9, weight: 0.2, noise: 0.03, pressure: null },
    probeFit: { on: false, shotWeights: null, weight: 1, mask: null, scale: null, force: null, meas: null },
    coilFit: { on: false, sigma: 0.07, loopSigma: 0.03 },
    pressure: { tite: 1, fastFraction: 0, fastPeaking: 2, fast: null, rot: null },
    density: { on: false, ne0: 3.5e19, peaking: 0.5, zeff: 1.5, profile: null, temperature: null, fitChords: false },
    pointMeas: null, pointNoise: 0,
    faraday: { on: false, weight: 1, outer: 2 },
    vessel: { on: false, rcond: 0.05, outer: 2, minSurvive: 0.10, twinInject: 0 },
    closure: { on: false, iters: 4, tol: 0.01 },
    sigmaVintage: 2021,
  };
  return Object.assign(m, over || {});
}

//: the deck's probe verdict (`fwtmp2`) as the shot mask, its readings as measured
const PF = { on: true, shotWeights: Array.from(R.probeWeights), weight: 1, mask: null, scale: null, force: null,
             meas: Array.from(R.probeMeas) };
const CONFIGS = {
  kinetic: {},
  magnetics: { kinetic: { on: false, points: 9, weight: 0.2, noise: 0.03, pressure: null } },
  //: ★the probes on the RAW basis — the deck's total flux with the page's own coil
  //: share removed, against the Rogowski current: the probe readings are raw, and
  //: on the delivered basis the mixture goes singular (measured: outer iteration
  //: 147), exactly as the deck's own provenance note says
  probes_raw: { loopMeasTotal: Array.from(R.loopMeasTotal), ipOverride: R.ipMeasured, probeFit: PF },
  //: the coil currents as observations (T-A5), delivered basis: 800 outer
  //: iterations, unconverged — the member the page returns, held as returned
  coils: { coilFit: { on: true, sigma: 0.07, loopSigma: 0.03 } },
  //: ★第三十二刀: the TWIN — its truth is a forward free-boundary solve on the
  //: deck's reference currents with the page's analytic profile, its readings
  //: are that field's (noise drawn on the page); once with the vessel carrying
  //: an injected current the loops see and the fit is not told about
  twin: { source: 'twin' },
  twin_inject: { source: 'twin', vessel: { on: false, rcond: 0.05, outer: 2, minSurvive: 0.10, twinInject: 5e3 } },
};

const arr = (v) => (v === null || v === undefined) ? null : Array.from(v);
function pick(m) {
  const r = m.result;
  return {
    result: { psiAxis: r.psiAxis, psiBnd: r.psiBnd, axisR: r.axisR, axisZ: r.axisZ, ip: r.ip,
              iterations: r.iterations, residual: r.residual, bndKind: r.bndKind, fbAmp: r.fbAmp,
              coefs: arr(r.coefs), shape: r.shape, q95: r.criteria && r.criteria.q95,
              psi: arr(r.psi) },
    ipConstraint: m.ipConstraint, sigma: m.sigma,
    meas: arr(m.meas), wts: arr(m.wts), model: arr(m.model),
    chi2: m.chi2, nfit: m.nfit, ndof: m.ndof, ipFitted: m.ipFitted,
    profiles: m.profiles ? { x: arr(m.profiles.x), pprime: arr(m.profiles.pprime), ffprime: arr(m.profiles.ffprime), p: arr(m.profiles.p) } : null,
    q: m.q ? { x: arr(m.q.x), q: arr(m.q.q), f: arr(m.q.f), q0: m.q.q0, q95: m.q.q95 } : null,
    jphi: m.jphi ? { x: arr(m.jphi.x), j: arr(m.jphi.j) } : null,
    li3: m.li3,
    probes: m.probes ? { b: arr(m.probes.b), br: arr(m.probes.br), bz: arr(m.probes.bz),
                         viaRows: arr(m.probes.viaRows), rowsVsFieldRel: m.probes.rowsVsFieldRel } : null,
    probeRows: m.probeRows ? { meas: arr(m.probeRows.meas), wts: arr(m.probeRows.wts) } : null,
    fitRows: m.fitRows,
    kinetic: m.kineticX ? { x: arr(m.kineticX), p: arr(m.kineticP), weight: m.kineticWeight } : null,
    coilFit: m.coilFit ? { pull: m.coilFit.pull, fitted: m.coilFit.fitted, after: arr(m.coilFit.after),
                           before: arr(m.coilFit.before), sigma: arr(m.coilFit.sigma), measSigma: m.coilFit.measSigma } : null,
    //: the twin's own truth and what was synthesised from it
    truth: m.truth ? { psiAxis: m.truth.psiAxis, psiBnd: m.truth.psiBnd, axisR: m.truth.axisR, axisZ: m.truth.axisZ,
                       ip: m.truth.ip, iterations: m.truth.iterations, residual: m.truth.residual, converged: m.truth.converged,
                       bndKind: m.truth.bndKind, xptR: m.truth.xptR, xptZ: m.truth.xptZ, fbAmp: m.truth.fbAmp,
                       shape: m.truth.shape, q95: m.truth.criteria && m.truth.criteria.q95, psi: arr(m.truth.psi) } : null,
    truthProfiles: m.truthProfiles ? { x: arr(m.truthProfiles.x), pprime: arr(m.truthProfiles.pprime),
                                       ffprime: arr(m.truthProfiles.ffprime), p: arr(m.truthProfiles.p) } : null,
    truthQ: m.truthQ ? { x: arr(m.truthQ.x), q: arr(m.truthQ.q), f: arr(m.truthQ.f), q0: m.truthQ.q0, q95: m.truthQ.q95 } : null,
    truthJphi: m.truthJphi ? { x: arr(m.truthJphi.x), j: arr(m.truthJphi.j) } : null,
    clean: arr(m.clean),
    vessel: m.vessel ? { truth: arr(m.vessel.truth), error: m.vessel.error } : null,
  };
}

const got = {};
for (const [name, over] of Object.entries(CONFIGS)) {
  send(message(over));
  const m = take('recon');
  inbox.splice(0, inbox.length);
  got[name] = JSON.parse(JSON.stringify(pick(m)));
}

if (RECORD) {
  writeFileSync(OUT, JSON.stringify({ device: id, configs: got }));
  console.log(`recorded ${Object.keys(got).length} fits on ${id} -> ${path.relative(process.cwd(), OUT)}`);
  process.exit(0);
}

const ref = JSON.parse(readFileSync(FIX, 'utf8'));
assert.equal(ref.device, id, 'the fixture was recorded on ' + ref.device);
//: ★BIT FOR BIT — see the header.  A failure prints the path and the two values.
const TRIG = /\.probes\.(b\[|rowsVsFieldRel$)/;
let worst = 0, worstAt = '';
function walk(a, b, at) {
  if (Array.isArray(b)) {
    assert.ok(Array.isArray(a) && a.length === b.length, `${at}: length ${a && a.length} vs ${b.length}`);
    for (let i = 0; i < b.length; i++) walk(a[i], b[i], `${at}[${i}]`);
  } else if (b && typeof b === 'object') {
    for (const k of Object.keys(b)) walk(a === null || a === undefined ? undefined : a[k], b[k], `${at}.${k}`);
  } else if (typeof b === 'number') {
    const d = Math.abs(a - b) / Math.max(Math.abs(b), 1e-300);
    if (!(d <= worst)) { worst = d; worstAt = at; }
    //: ★第三十三刀: the probe projection `br cos(a) + bz sin(a)` — the browser's
    //: `Math.cos` / `Math.sin` (fdlibm) and the kernel's libm differ in the last
    //: bit for some angles (measured: 1.2e-16 on one of 79), so the projected
    //: reading and the figure derived from it are held to 1e-14; br / bz and
    //: the rows route carry no transcendental and stay bit for bit
    if (TRIG.test(at)) { assert.ok(d <= 1e-14, `${at}: ${a} vs ${b} (rel ${d.toExponential(2)} > 1e-14)`); return; }
    assert.ok(Object.is(a, b) || a === b, `${at}: ${a} vs ${b} (rel ${d.toExponential(2)})`);
  } else {
    assert.deepEqual(a, b, at);
  }
}
for (const name of Object.keys(ref.configs)) walk(got[name], ref.configs[name], name);
const k = got.kinetic;
console.log(`validate-worker-recon: ${Object.keys(ref.configs).length} fits on ${id} bit for bit but the probe projection's last bit (worst rel ${worst.toExponential(2)} at ${worstAt || '—'}); ` +
            `kinetic: ${k.result.iterations} it, chi2/ndof ${(k.chi2 / k.ndof).toExponential(3)}, Ip ${(k.ipFitted / 1e6).toFixed(4)} MA, ` +
            `q0 ${k.q.q0.toFixed(3)}, q95 ${k.q.q95.toFixed(3)}, li3 ${k.li3.toFixed(4)}; probes_raw: ${got.probes_raw.fitRows.probes} probe rows, ${got.probes_raw.result.iterations} it; coils: pull ${got.coils.coilFit.pull.toFixed(3)}`);
