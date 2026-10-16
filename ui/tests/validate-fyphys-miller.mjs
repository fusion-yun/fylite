// 放电设计页主线程的 Miller 边界：`FyPhys.millerBoundary` 走 `code/outlines`——与退役前的扁平答案逐位相同
//
// ★★WHAT THIS GATE IS ABOUT.  T-4 第二十刀 (2026-09-06) took `fylite_rs_miller_boundary`
// off the interface: the pulse-design page draws the target boundary three
// times on its MAIN THREAD through `FyPhys.millerBoundary`, and that now goes
// through the tree door (`code/outlines`, the Miller route, the record's
// `lcfs` field).  Moving the call is not a licence to move the answer: the
// fixture `fixtures/fyphys-miller.json` was recorded on the flat export
// BEFORE the cut, and every number here must equal it to the bit.
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
const fixture = JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'fyphys-miller.json'), 'utf8'));
let n = 0;
for (const c of fixture.cases) {
  const got = globalThis.FyPhys.millerBoundary(c.params, c.params.n);
  assert.equal(got.length, c.boundary.length, `点数 ${got.length} != ${c.boundary.length}`);
  for (let i = 0; i < got.length; i++) {
    assert.ok(Object.is(got[i][0], c.boundary[i][0]) && Object.is(got[i][1], c.boundary[i][1]),
      `case ${n} point ${i}: door (${got[i]}) != recorded flat (${c.boundary[i]})`);
  }
  n += 1;
}
assert.ok(typeof fy.millerBoundary !== 'function', 'the flat prototype is back');
console.log(`validate-fyphys-miller: ${n} boundaries through code/outlines, bit for bit against the recorded flat export`);
