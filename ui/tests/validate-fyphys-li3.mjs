// 分析页主线程的 li(3)：`FyPhys.li3` 走 `code/li3`——与退役前的扁平答案逐位相同
//
// ★★WHAT THIS GATE IS ABOUT.  T-4 第二十三刀 (2026-09-06) took `fylite_rs_li3` off the
// interface: the analysis page reports li(3) for a g-file it opens as a
// reference on its MAIN THREAD, and that goes through the tree door now
// (`code/li3`, the `li3` fact).  The fixture `fixtures/fyphys-li3.json` was
// recorded on the flat export BEFORE the cut (analytic maps on the page's own
// `makeGrid` axes); every number here must equal it to the bit.
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
const fixture = JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'fyphys-li3.json'), 'utf8'));
let n = 0;
for (const c of fixture.cases) {
  const g = globalThis.FyPhys.makeGrid(c.box);
  for (let i = 0; i < g.nr; i++) assert.ok(Object.is(g.r[i], c.r[i]), `case ${n}: the page's R axis moved`);
  const got = globalThis.FyPhys.li3(g, { psi: Float64Array.from(c.psi), psiAxis: c.psiAxis, psiBnd: c.psiBnd }, c.ip, c.r0);
  assert.ok(Object.is(got, c.li3), `case ${n}: door li3 ${got} != recorded flat ${c.li3}`);
  n += 1;
}
assert.ok(typeof fy.li3 !== 'function', 'the flat prototype is back');
console.log(`validate-fyphys-li3: ${n} maps through code/li3, li(3) bit for bit against the recorded flat export`);
