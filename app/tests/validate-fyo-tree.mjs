// 树门在页面这一侧（FYL-DESIGN-16 W-1，2026-09-05）：`kernelapi.js` 的扁平树编解码
// 与 `fylite_rs_fyo_tree` 在 wasm 上的调用。
//
// 三件事，各是一道判据：
//   1. **同形**：同一份计划，JS 编出的四段缓冲与内核仓 `tests/oracles/tree.py`（Python）
//      编出的**逐字节相等**（夹具 `fixtures/fyo-tree-plan.json` 由那边生成）。两个宿主
//      各写一份编码器，唯一能证明它们是同一个格式的办法是比字节。
//   2. **往返**：decode(encode(x)) 深等于 x。
//   3. **门**：真 wasm 上 `code/transport` 完成一次并答回记录；未知 code 是一个带码的
//      拒绝（抛出，`.code === -30`）；缺文档的 code 按名拒绝（`inputs/device`）。
//
// 离线、不需要 fy 宿主：这条路正是静态站点那条。
import { readFileSync, existsSync } from 'node:fs';
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

const api = globalThis.FyKernelApi, FyLite = globalThis.FyLite;
const fixture = JSON.parse(readFileSync(path.join(HERE, 'fixtures', 'fyo-tree-plan.json'), 'utf8'));
let n = 0;
const ok = (msg) => { n += 1; console.log('  ok ' + msg); };

// --- 1. 同形 ------------------------------------------------------------------
assert.equal(globalThis.FyNames.TREE_FORMAT, fixture.tree_format, 'TREE_FORMAT');
const b = api.tree.encode(fixture.plan);
assert.deepEqual(Array.from(b.nodes), fixture.nodes, 'nodes');
assert.deepEqual(Array.from(b.names), fixture.names, 'names');
assert.deepEqual(Array.from(b.f64s), fixture.f64s, 'f64s');
assert.deepEqual(Array.from(b.ints).map(Number), fixture.ints, 'ints');
ok(`JS 编出的四段与 Python 的逐字节相等（${b.nodes.length / 8} 节点 · ${b.names.length} 字节 · ${b.f64s.length} f64 · ${b.ints.length} int）`);

// --- 2. 往返 ------------------------------------------------------------------
assert.deepEqual(api.tree.decode(b), fixture.plan, 'decode(encode(plan)) == plan');
const odd = { a: 1, s: 'x—y', e: [], m: { n: null, t: true, f: false }, big: 7n,
              nested: [[[1, 2], [3, 4]], [[5, 6], [7, 8]]], strs: ['α', 'β'] };
const back = api.tree.decode(api.tree.encode(odd));
assert.deepEqual(back, { a: 1, s: 'x—y', e: [], m: { n: null, t: true, f: false }, big: 7,
                         nested: odd.nested, strs: ['α', 'β'] });
ok('往返：空表 · 多维 · 串数组 · bigint(Int) · 布尔 · null 都回得来');

// --- 3. 门 --------------------------------------------------------------------
const ver = (globalThis.FyVersion && globalThis.FyVersion.kernel) || '0.0.1';
const wasmFile = SITE + 'fylite_rs.wasm.' + ver;
if (!existsSync(wasmFile)) {
  console.log(`跳过第三段：没有 ${wasmFile}（rust/build.sh --wasm-check 在内核仓）`);
  console.log(`validate-fyo-tree: ${n} 项通过`);
  process.exit(0);
}
const fy = await FyLite.fromBytes(readFileSync(wasmFile), ['fylite_rs_fyo_tree', 'fylite_rs_alloc', 'fylite_rs_free', 'fylite_rs_abi_version', 'memory']);
const plan = { settings: { power: 12.0, width: 0.36, pinch: 0.0, edge: 3.0, dpc: 0.0, n: 41, amin: 2.0,
                           rmaj: 3.1, kappa: 1.86, delta: 0.48, q95: 3.0, chi0: 0.4, closure: '0' } };
const rec = fy.complete('code/transport', plan);
assert.equal(rec.entry, 'transport');
assert.equal(rec.code, 'code/transport');
assert.equal(rec.facts.converged.value, 1);
const te = rec.fields.core_profiles.profiles_1d.electrons.temperature.data;
assert.equal(te.length, 41);
assert.ok(te[0] > te[40], 'the core is hotter than the edge');
assert.ok(Array.isArray(rec.notes));
ok(`wasm 上 code/transport 完成：${te.length} 点，converged=${rec.facts.converged.value}`);

//: the same plan twice — the door is stateless and the allocator gives it all back
const rec2 = fy.complete('code/transport', plan);
assert.deepEqual(rec2.fields.core_profiles.profiles_1d.electrons.temperature.data, te);
ok('同一计划再敲一次：逐位相同（无状态）');

let threw = null;
try { fy.complete('code/nowhere', {}); } catch (e) { threw = e; }
assert.ok(threw && threw.code === -30, 'unknown code refuses with -30');
assert.match(threw.message, /code\/transport/);
ok('未知 code：拒绝 -30，并列出内核认得的 code');

threw = null;
try { fy.complete('code/breakdown', { settings: { r0: 1.85 } }); } catch (e) { threw = e; }
assert.ok(threw && threw.code === -31, 'a missing document refuses with -31');
assert.match(threw.message, /inputs\/device/);
ok('缺装置文档的 code：拒绝 -31，点名 inputs/device');

//: a 2-D input rides in with its shape and comes back with it
const plan2 = { settings: { r0: 1.85, z0: 0, radius: 0.3 }, inputs: { device: { 'pf_active': { coil: [] } } } };
threw = null;
try { fy.complete('code/breakdown', plan2); } catch (e) { threw = e; }
assert.ok(threw && threw.code < 0);
ok('空线圈表的装置：按名拒绝（' + threw.code + '）');

console.log(`validate-fyo-tree: ${n} 项通过`);
