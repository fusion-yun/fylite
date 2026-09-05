// 设计页的 worker 走文档门（FYL-DESIGN-16 K-3 第三刀的页面一半，2026-09-05）。
//
// `worker.js` 的 `startRun` / `designRun` 从前各自编排十几个扁平导出；今天它们把一份
// 计划交给 `code/discharge`（`fy.complete`，静态站点上是 wasm 的 `fylite_rs_fyo_tree`），
// 留在 worker 里的只有显示：判据 · 通量分段 · 剖面 · 垂直模。这道门在 node 里
// **把 worker 当脚本跑**（`importScripts` / `postMessage` 用 vm 顶上），对着发布出去的
// EAST 装置文档（`dist/facts/device/east.jsonld`，`tools/abox-to-facts.py --all` 拖回）：
//
//   1. `init` 起得来（wasm 那条路，不需要 fy 宿主）；
//   2. `start` 答回有限的电流、psiRms、绑定集与目标边界；
//   3. `design`（两遍退火）答回 history 三条、形状六个量有限、判据在、pass 在 0..2；
//      同一请求再发一次**逐位相同**（门无状态）；
//   4. 缺 schedule 的 design 仍然答（内核按 passes 造表）——页面从不发 schedule=null 之外的
//      东西，但 worker 不该因此死。
//
// 物理的对拍在内核仓（`tests/test_discharge_code.py`：旧 Python 配方 vs 内核，安匝 1e-9）；
// 这里判的是**页面这一侧接得上、说得清**。
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { deviceDoc } from './_device.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets') + path.sep;
const BASE = 'http://127.0.0.1:0/';
//: ★EAST when the card is here (it is hand-maintained and not pulled from the
//: A-Box, so a fresh checkout may lack it), else the first published machine
//: whose document the page's reader accepts — a machine with no reference
//: discharge is exactly the case the designed start exists for
const CANDIDATES = ['east', 'iter', 'west', 'jt60sa', 'cfetr', 'cfedr', 'best'];

// --- the worker's host ------------------------------------------------------
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

let M = null, id = null, why = [];
for (const c of CANDIDATES) {
  const d = deviceDoc(c);
  if (!d) continue;
  try { M = globalThis.FyoDevice.fromFyo(d); id = c; break; }
  catch (e) { why.push(c + ': ' + e.message); }
}
if (!M) {
  console.log('跳过：dist/facts/device/ 里没有页面读得懂的装置文档（tools/abox-to-facts.py --all）'
              + (why.length ? '\n  ' + why.join('\n  ') : ''));
  process.exit(0);
}
let n = 0;
const ok = (msg) => { n += 1; console.log('  ok ' + msg); };
const take = (type) => {
  const i = inbox.findIndex((m) => m.type === type || m.type === 'error');
  assert.ok(i >= 0, `no ${type} answer; inbox: ` + inbox.map((m) => m.type).join(','));
  const m = inbox.splice(i, 1)[0];
  assert.notEqual(m.type, 'error', `${type}: worker error: ` + m.message);
  return m;
};
const send = (msg) => globalThis.self.onmessage({ data: msg });

// --- 1. init ------------------------------------------------------------------
await send({ cmd: 'init', machine: M });
inbox.splice(0, inbox.length);
ok(`init on ${M.name}: ${M.coils.length} coils, ${M.channels.length} channels`);

// --- 2. start -----------------------------------------------------------------
//: the target sized from the machine's own box and field: 60 % of the half
//: width, κ 1.6, and the current a q95 of 3.5 implies there (the page's own
//: `ranges` rule, `device.js`)
const bb = globalThis.FyDevice.bbox(M), tf = globalThis.FyDevice.tf(M);
const rgeo = 0.5 * (bb.rmin + bb.rmax), amax = 0.5 * (bb.rmax - bb.rmin);
const target = { r0: rgeo, z0: 0.5 * (bb.zmin + bb.zmax), a: 0.6 * amax, kappa: 1.6, deltaU: 0.4, deltaL: 0.5 };
const b0 = Math.abs(tf.b0 * tf.r0 / rgeo);
const ip = 2 * Math.PI * target.a * target.a * b0 * (1 + target.kappa * target.kappa)
           / (2 * 4e-7 * Math.PI * rgeo * 3.5);
send({ cmd: 'start', target, ip, nPoints: 24, xWeight: 0, control: [], iMax: null,
       nRing: 4, peaking: 1, lambda: 1e-3 });
const st = take('start');
assert.equal(st.chan.length, M.channels.length);
assert.ok(Array.from(st.chan).every(Number.isFinite), 'finite start currents');
assert.ok(Number.isFinite(st.psiRms) && st.psiRms >= 0, 'psiRms');
assert.ok(Array.isArray(st.bind));
assert.equal(st.targetBoundary.length, 48);
assert.equal(st.bX, null, 'no null asked for: bX is null');
ok(`start: psiRms ${st.psiRms.toExponential(2)}, ${st.bind.length} channels at bound`);

// --- 3. design ----------------------------------------------------------------
const design = { cmd: 'design', chan: Array.from(st.chan), target, ip, warm: true,
                 prof: { beta0: 0.55, emp: 1, enp: 1, r0: target.r0 },
                 schedule: [0.1, 0.03], gamma: 0.4, nPoints: 24, xWeight: 0, control: [],
                 solve: { maxIter: 400, relax: 0.3, tol: 1e-8 } };
send(design);
const d = take('design');
assert.equal(d.history.length, 3, 'pass 0 + two passes');
assert.ok(d.pass >= 0 && d.pass <= 2);
const hist = d.history.filter((h) => h.err !== null);
assert.ok(hist.every((h) => Number.isFinite(h.err)), 'finite errors');
for (const k of ['r0', 'z0', 'a', 'kappa', 'deltaU', 'deltaL'])
  assert.ok(Number.isFinite(d.result.shape[k]), 'shape.' + k);
assert.ok(d.result.criteria && typeof d.result.criteria === 'object', 'criteria present');
assert.equal(d.result.psi.length, M.grid.nr * M.grid.nz);
assert.ok(d.result.lcfs.length > 16, 'a traced boundary');
assert.equal(d.chan.length, M.channels.length);
const best = d.history.find((h) => h.pass === d.pass);
assert.equal(best.err, Math.min(...hist.map((h) => h.err)), 'the returned pass is the best one');
const progress = inbox.filter((m) => m.type === 'progress');
assert.ok(progress.length >= 2, 'progress was posted');
inbox.splice(0, inbox.length);
ok(`design: best pass ${d.pass}, err ${best.err.toFixed(4)} (from ${d.history[0].err.toFixed(4)}), boundary ${d.result.lcfs.length / 2} points, vertical ${d.result.criteria.vertical ? 'on' : 'off'}`);

send(design);
const d2 = take('design');
assert.deepEqual(Array.from(d2.chan), Array.from(d.chan), 'the same request twice: bit for bit');
assert.deepEqual(d2.history.map((h) => h.err), d.history.map((h) => h.err));
inbox.splice(0, inbox.length);
ok('the same design twice: identical currents and history (the door is stateless)');

// --- 4. no schedule -----------------------------------------------------------
send({ ...design, schedule: null, warm: false });
const d3 = take('design');
assert.ok(d3.history.length >= 1);
inbox.splice(0, inbox.length);
ok(`schedule=null: the kernel's own geometric table ran (${d3.history.length - 1} passes)`);

// --- 5. pulse ------------------------------------------------------------------
const wps = [0.0, 0.5, 1.5, 2.5].map((tk, k) => ({
  t: tk, ip: [0, 0.6 * ip, ip, 0.4 * ip][k],
  target: { r0: target.r0, z0: target.z0, a: target.a * [0.8, 0.9, 1, 0.9][k], kappa: target.kappa,
            deltaU: target.deltaU, deltaL: target.deltaL } }));
send({ cmd: 'pulse', waypoints: wps, nPoints: 24, xWeight: 0, verify: [2], iMax: null,
       prof: { beta0: 0.55, emp: 1, enp: 1, r0: target.r0 }, solve: { maxIter: 400, relax: 0.3 } });
const pu = take('pulse');
assert.equal(pu.t.length, 4);
assert.equal(pu.nch, M.channels.length);
assert.equal(pu.x.length, 4 * pu.nch);
assert.equal(pu.v.length, 4 * pu.nch);
assert.ok(Array.from(pu.v).every(Number.isFinite), 'finite voltages');
assert.ok(Array.from(pu.x.slice(0, pu.nch)).every((c) => c === 0), 'no plasma at t=0: zero currents');
assert.equal(pu.designs.length, 4);
assert.equal(pu.designs[0].psiRms, 0);
assert.ok(pu.designs[2].psiRms > 0);
assert.equal(pu.checks.length, 1);
assert.equal(pu.checks[0].k, 2);
assert.ok(!pu.checks[0].error, 'the check solved: ' + (pu.checks[0].error || ''));
assert.ok(Number.isFinite(pu.checks[0].shape.a), 'the checked waypoint has a shape');
assert.equal(pu.resistance.length, pu.nch);
inbox.splice(0, inbox.length);
ok(`pulse: 4 waypoints, ${pu.nv} passive conductors, check at k=2: a=${pu.checks[0].shape.a.toFixed(3)} (asked ${wps[2].target.a.toFixed(3)})`);

console.log(`validate-worker-design: ${n} 项通过`);
