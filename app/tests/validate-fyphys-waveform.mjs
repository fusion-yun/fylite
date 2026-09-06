// 放电设计页主线程的四相梯形：`FyPhys.waveform` 走 `code/waveform`——与退役前的扁平答案逐位相同
//
// ★★WHAT THIS GATE IS ABOUT.  T-4 第二十二刀 (2026-09-06) took `fylite_rs_zerod_waveform`
// off the interface: the pulse-design page's `wave()` (Ip, n_e, T_e trajectories,
// the phase label) goes through the tree door now (`code/waveform`, the `value`
// field).  The fixture `fixtures/fyphys-waveform.json` was recorded on the flat
// export BEFORE the cut for all six shapes; every number here must equal it to
// the bit.
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
const fixture = JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'fyphys-waveform.json'), 'utf8'));
let n = 0;
for (const c of fixture.cases) {
  const p = c.params;
  const got = globalThis.FyPhys.waveform(p.phases, p.t, { flat: p.flat, start: p.start || 0, end: p.end || 0, which: p.which });
  assert.equal(got.length, c.value.length, `case ${n}: ${got.length} != ${c.value.length}`);
  for (let i = 0; i < got.length; i++)
    assert.ok(Object.is(got[i], c.value[i]), `case ${n} (which ${p.which}) sample ${i}: door ${got[i]} != recorded flat ${c.value[i]}`);
  n += 1;
}
assert.ok(typeof fy.zerodWaveform !== 'function', 'the flat prototype is back');
console.log(`validate-fyphys-waveform: ${n} waveforms through code/waveform (all six shapes), bit for bit against the recorded flat export`);
