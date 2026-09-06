// 放电设计页主线程的形状与体积：`FyPhys.shapeMetrics` · `surfaceVolume` 走 `code/shape`——与退役前的扁平答案逐位相同
//
// ★★WHAT THIS GATE IS ABOUT.  T-4 第二十一刀 (2026-09-06) took `fylite_rs_shape_metrics`
// and `fylite_rs_enclosed_volume` off the interface: the pulse-design page reads
// the shape and the volume of every solved slice's boundary on its MAIN THREAD,
// and that goes through the tree door now (`code/shape`, facts).  The fixture
// `fixtures/fyphys-shape.json` was recorded on the flat exports BEFORE the cut;
// every number here must equal it to the bit.
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
globalThis.FyPhys.useKernel(fy);
const fixture = JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'fyphys-shape.json'), 'utf8'));
let n = 0;
for (const c of fixture.cases) {
  const sh = globalThis.FyPhys.shapeMetrics(c.poly);
  for (const k of ['r0', 'a', 'kappa', 'deltaU', 'deltaL', 'z0', 'delta'])
    assert.ok(Object.is(sh[k], c.shape[k]), `case ${n} ${k}: door ${sh[k]} != recorded flat ${c.shape[k]}`);
  const vol = globalThis.FyPhys.surfaceVolume(c.poly);
  assert.ok(Object.is(vol, c.volume), `case ${n} volume: door ${vol} != recorded flat ${c.volume}`);
  n += 1;
}
assert.equal(globalThis.FyPhys.surfaceVolume([[1, 0], [2, 0]]), 0, 'the degenerate outline is the page\'s zero');
assert.ok(typeof fy.shapeMetrics !== 'function' && typeof fy.enclosedVolume !== 'function', 'a flat prototype is back');
console.log(`validate-fyphys-shape: ${n} outlines through code/shape, shape and volume bit for bit against the recorded flat exports`);
