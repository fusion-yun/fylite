// 磁面几何量走 `code/metric`——与退役前的扁平 `geoSurface` 答案逐位相同，圆截面另对解析式
//
// ★★WHAT THIS GATE IS ABOUT.  T-4 第二十四刀 (2026-09-06) took `fylite_rs_geo_surface_gm2`
// off the interface: the flux-surface moments of a local Miller / MXH surface
// come through the tree door now (`code/metric`, the ladder rows in, the
// DD-named moments out).  `validate-geo.mjs` used to hold the browser's packing
// of GEO's fourteen positional scalars against Python's; there is one packing
// left — the kernel's own, off named rows — so the wiring question is closed
// and this gate asks two others: the door lands on the recorded flat answers
// (`fixtures/metric.json`, recorded BEFORE the cut: the five wiring surfaces
// and one MXH surface at 501 theta, two of the model page's Miller ladders at
// 201) to the bit, and the circular surface stays anchored OUTSIDE both
// implementations (V' = (2 pi)^2 R0 r, <|grad r|> = 1).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets') + path.sep;
const BASE = 'http://127.0.0.1:0/';
globalThis.self = globalThis;
globalThis.location = { hostname: '127.0.0.1', href: BASE, search: '' };
globalThis.document = {
  currentScript: { src: BASE + 'assets/kernelapi.js' },
  documentElement: { lang: 'zh', setAttribute() {}, getAttribute: () => 'zh' },
  getElementById: () => null, querySelector: () => null, querySelectorAll: () => [],
  addEventListener() {},
  createElement: () => ({ style: {}, addEventListener() {}, remove() {}, click() {}, appendChild() {} }),
  body: { appendChild() {} },
};
globalThis.localStorage = { _s: {}, getItem(k) { return k in this._s ? this._s[k] : null; },
                            setItem(k, v) { this._s[k] = String(v); }, removeItem(k) { delete this._s[k]; } };
globalThis.fetch = async () => { throw new Error('this gate is offline'); };
for (const f of ['i18n.js', 'lang-zh.js', 'lang-en.js', 'version.js', 'deck-names.js',
                 'fyo-interface.js', 'kernel-abi.js', 'kernelapi.js', 'fylite.js'])
  vm.runInThisContext(readFileSync(SITE + f, 'utf8'), { filename: f });
const fy = await globalThis.FyLite.fromBytes(readFileSync(SITE + 'fylite_rs.wasm'),
  ['fylite_rs_fyo_tree', 'fylite_rs_alloc', 'fylite_rs_free', 'fylite_rs_abi_version', 'memory']);
const fixture = JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'metric.json'), 'utf8'));

//: the flat wrapper's spelling -> (the door's row, its field on the record)
const ROWS = { rmin: 'fylite:r_minor', rmaj: 'fylite:r_major', q: 'q', shear: 'magnetic_shear', kappa: 'elongation',
               delta: 'triangularity_upper', drmaj: 'fylite:shift', sKappa: 'fylite:s_elongation',
               sDelta: 'fylite:s_triangularity', zeta: 'fylite:squareness', sZeta: 'fylite:s_squareness',
               zmag: 'fylite:z_magnetic', dzmag: 'fylite:dz_magnetic' };
const LADDER = { volume: 'volume', volumePrime: 'dvolume_drho_tor', fsaGradR2: 'gm3', fsaGradR: 'gm7',
                 fsaGradR2OverR2: 'gm2', fsaR2: 'fylite:r2_average' };
const RAW = { f: 'f', ffprime: 'ffprime', fsaBp2: 'fsa_bp2', fsaBt2: 'fsa_bt2', gradR0: 'grad_r0', surf: 'surf',
              bt0: 'bt0', bp0: 'bp0', thetaScale: 'thetascale', bl: 'bl' };
const flat = (node) => { const out = []; (function walk(v) { if (Array.isArray(v)) v.forEach(walk); else out.push(v); })(node.data); return out; };

function door(cases, nTheta) {
  //: every case in ONE row: the door is a ladder, one node per surface
  const n = cases.length, rows = {};
  for (const [k, p] of Object.entries(ROWS)) {
    const col = new Float64Array(n);
    for (let i = 0; i < n; i++) col[i] = (k in cases[i]) ? cases[i][k] : ({ kappa: 1 }[k] || 0);
    rows[p] = col;
  }
  if (cases.some((c) => c.shape)) {
    const mxh = new Float64Array(22 * n);
    cases.forEach((c, i) => { if (c.shape) mxh.set(c.shape, 22 * i); });
    rows['fylite:mxh_harmonics'] = mxh;
  }
  const rec = fy.complete('code/metric', { settings: { n_theta: nTheta },
                                           inputs: { equilibrium: { time_slice: { profiles_1d: rows } } } });
  assert.equal(rec.entry, 'metric');
  assert.equal(rec.dims.n, n);
  const lad = rec.fields.equilibrium.time_slice.profiles_1d;
  const got = cases.map(() => ({}));
  for (const [k, p] of Object.entries(LADDER)) flat(lad[p]).forEach((v, i) => { got[i][k] = v; });
  for (const [k, p] of Object.entries(RAW)) flat(rec.fields[p]).forEach((v, i) => { got[i][k] = v; });
  return got;
}

let checked = 0;
const compare = (got, want, tag) => {
  for (const k of Object.keys(want)) {
    assert.ok(k in got, `${tag}: the door has no ${k}`);
    assert.ok(Object.is(got[k], want[k]), `${tag} ${k}: door ${got[k]} != recorded flat ${want[k]}`);
    checked += 1;
  }
};
// (1) the wiring surfaces, one row
const surf = door(fixture.surfaces.map((s) => s.case), 501);
fixture.surfaces.forEach((s, i) => compare(surf[i], s.flat, s.case.name));
// (2) the same surfaces one at a time: a node's answer does not depend on its neighbours
fixture.surfaces.forEach((s) => compare(door([s.case], 501)[0], s.flat, s.case.name + ' (alone)'));
// (3) the model page's Miller ladders at 201 theta
for (const l of fixture.ladders) {
  const got = door(l.rows, 201);
  l.rows.forEach((r, i) => compare(got[i], r.flat, `ladder n=${l.bar.n} node ${i + 1}`));
}
// (4) the circular surface anchored outside both implementations
const c0 = fixture.surfaces[0];
assert.equal(c0.case.name, '圆截面');
const vExact = 4 * Math.PI * Math.PI * c0.case.rmaj * c0.case.rmin;
assert.ok(Math.abs(surf[0].volumePrime - vExact) / vExact <= 1e-6, `circular V' ${surf[0].volumePrime} vs ${vExact}`);
assert.ok(Math.abs(surf[0].fsaGradR - 1) <= 1e-6, `circular <|grad r|> ${surf[0].fsaGradR}`);
// (5) every wiring surface gives a different V' — an argument that did not reach the solve would hide here
assert.equal(new Set(surf.map((g) => g.volumePrime.toFixed(6))).size, surf.length, 'two surfaces gave the same V\'');
// (6) the refusals name things
for (const [plan, what] of [
  [{ settings: {}, inputs: { equilibrium: { time_slice: { profiles_1d: { q: Float64Array.of(2) } } } } }, /r_minor/],
  [{ settings: {}, inputs: { equilibrium: { time_slice: { profiles_1d: { 'fylite:r_minor': Float64Array.of(0.5), q: Float64Array.of(2) } } } } }, /major radius/],
  [{ settings: { rmaj: 3 }, inputs: { equilibrium: { time_slice: { profiles_1d: { 'fylite:r_minor': Float64Array.of(0.5, 0.6), q: Float64Array.of(2) } } } } }, /2 values|has 1 values/],
]) {
  let err = null;
  try { fy.complete('code/metric', plan); } catch (e) { err = e; }
  assert.ok(err && what.test(String(err.message || err)), `refusal: ${err && err.message}`);
}
assert.ok(typeof fy.geoSurface !== 'function', 'the flat prototype is back');
console.log(`validate-metric: ${checked} numbers through code/metric bit for bit against the recorded flat export (${fixture.surfaces.length} surfaces, ${fixture.ladders.length} ladders), circular anchor 1e-6`);
