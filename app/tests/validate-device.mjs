// Oracle test for app/assets/fyodev.js: every bundled device must survive a
// round trip through the fyo document and come back bit-identical.
//
// A device descriptor is the one input where a dropped field does NOT fail
// loudly — the solver happily produces a plausible, wrong equilibrium from a
// machine that lost half its coils.  So the check is equality of the whole
// structure, not a spot check of a few numbers.
//
//   node tests/app/validate-device.mjs

import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { presetProblems, presets } from './_preset.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const SITE = HERE + '../assets/';
globalThis.self = globalThis;
for (const f of ['i18n.js', 'lang-zh.js', 'lang-en.js',
                 'device.js', 'fyodev.js'])
  vm.runInThisContext(readFileSync(SITE + f, 'utf8'), { filename: f });

const { FyoDevice: FY } = globalThis;
//: ★the presets are fyo/JSON-LD documents now, read the way a page reads
//: them — `assets/dev-iter.js` was a script that pushed a global
const DEV = presets(FY);
//: ★★**样本不写死**。2026-09-05 实测：这里从前写死 `DEV.iter`，而 ITER 在本检出里
//: 读不进（上游的 `tf` 把 b0 标为「需要确认」，真值要从参考平衡表头取，而那份 g
//: 文件不在检出里）——于是整条闸子以一句 `Cannot read properties of undefined` 死掉，
//: 报的还是与它要问的事无关的东西。闸子问的是「坏文档会不会被拒」，那对**任何**
//: 一台读得进的机器都成立。
if (!Object.keys(DEV).length) {
  console.error('这一版一台机器也读不进——先看 presetProblems()：');
  console.error(JSON.stringify(presetProblems(), null, 1));
  process.exit(1);
}
console.log(`（这一版读不进的：${Object.keys(presetProblems()).join(' ') || '无'}）`);

/** Deep compare with a path, so a failure says WHICH field moved. */
function diff(a, b, path = '') {
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b)) return [`${path}: array vs not`];
    if (a.length !== b.length)
      return [`${path}: length ${a.length} -> ${b.length}`];
    return a.flatMap((v, i) => diff(v, b[i], `${path}[${i}]`));
  }
  if (a && typeof a === 'object') {
    if (!b || typeof b !== 'object') return [`${path}: object vs not`];
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    return [...keys].flatMap((k) => diff(a[k], b[k], path ? `${path}.${k}` : k));
  }
  if (typeof a === 'number' && typeof b === 'number')
    return a === b ? [] : [`${path}: ${a} -> ${b}`];
  return a === b ? [] : [`${path}: ${JSON.stringify(a)} -> ${JSON.stringify(b)}`];
}

/** Only the fields the descriptor contract actually defines. */
function normalise(m) {
  return {
    id: m.id, name: m.name, grid: m.grid,
    tf: globalThis.FyDevice.tf(m),
    coils: m.coils, channels: m.channels, loops: m.loops,
    limiter: m.limiter,
    vessel: m.vessel || [],
    vesselOutline: m.vesselOutline || [],
    ui: m.ui || undefined,
    reference: m.reference || undefined,
    //: ★T-M15: the LH launchers are device data now, so they are part of
    //: "came back bit-identical" — a section left out of this list is a
    //: section the round trip cannot see being dropped.
    lhAntennas: m.lhAntennas || [],
  };
}

let bad = 0;
for (const id of Object.keys(DEV)) {
  const m = DEV[id];
  const text = JSON.stringify(FY.toFyo(m));
  const back = FY.fromFyo(JSON.parse(text));
  const d = diff(normalise(m), normalise(back));
  const size = (text.length / 1024).toFixed(1);
  console.log(`${id.padEnd(6)} ${String(m.coils.length).padStart(3)} 线圈  ` +
              `${String(m.loops.length).padStart(4)} 磁通环  ` +
              `${String(m.limiter.r.length).padStart(4)} 限制器点  ` +
              `${String((m.lhAntennas || []).length)} LH  ` +
              `${size.padStart(6)} KB  ` +
              (d.length ? `✗ ${d.length} 处不符` : '✓ 往返逐位相同'));
  d.slice(0, 8).forEach((x) => console.log('    ' + x));
  if (d.length) bad += 1;
}

// A malformed document has to be refused, not silently repaired: the whole
// point of validating on import is that a wrong machine looks right.
//
//: ★★每一条坏法自带**前提**：它要改的那一节，得先在文档里。2026-09-05 之前这里
//: 拿同一台机器跑完整张表，于是「磁通环坐标是 NaN」在一台没有磁通环的机器上不是
//: 「没测到」，而是 `Cannot read properties of undefined` ——闸子死在自己的样本上，
//: 报的与被测代码无关。现在每条各自挑第一台**带着那一节**的机器；一节全仓都没有，
//: 就明说这条**没测到**，而不是把它算成通过。装置各带各的（BEST/CFETR 无磁通环，
//: EAST 有 35 个），所以「一台包打」这个假设本来就不成立。
const REJECT = [
  ['@type 不对', () => true,
   (d) => { d['@type'] = 'something/else'; }],
  ['没有线圈', (d) => d.pf_active?.coil?.length,
   (d) => { d.pf_active.coil = []; }],
  ['网格盒缺失', (d) => d['fylite:grid'],
   (d) => { delete d['fylite:grid']; }],
  ['网格上下界反了', (d) => d['fylite:grid'],
   (d) => { const g = d['fylite:grid']; const t = g.rmin; g.rmin = g.rmax; g.rmax = t; }],
  ['限制器出网格盒', (d) => d.wall?.description_2d?.[0]?.limiter?.unit?.[0]?.outline?.r?.length,
   (d) => { d.wall.description_2d[0].limiter.unit[0].outline.r[0] = 1e3; }],
  ['通道指向不存在的线圈', (d) => d.pf_active?.coil?.length,
   (d) => { d['fylite:channel_map'] = [[[999, 1]]]; }],
  ['线圈缺 width', (d) => d.pf_active?.coil?.[0]?.element?.[0]?.geometry?.rectangle,
   (d) => { delete d.pf_active.coil[0].element[0].geometry.rectangle.width; }],
  ['磁通环坐标是 NaN', (d) => d.magnetics?.flux_loop?.[0]?.position?.[0],
   (d) => { d.magnetics.flux_loop[0].position[0].r = 'x'; }],
  //: ★a declared launcher with half a band must be refused rather than
  //: half-read: the band is what the page's defaults come from, and a
  //: launcher that lost its upper end would silently become the markup's.
  //: 这两条自己造整节，所以任何一台都当得了样本。
  ['LH 天线的 n∥ 带不成对', () => true, (d) => {
    d.lh_antennas = { antenna: [{ name: 'LH1', frequency: 2.45e9,
                                  'fylite:max_power': 4e6,
                                  'fylite:n_parallel': [2.0] }] };
  }],
  ['LH 天线没有铭牌功率', () => true, (d) => {
    d.lh_antennas = { antenna: [{ name: 'LH1', frequency: 2.45e9,
                                  'fylite:n_parallel': [1.9, 2.4] }] };
  }],
];
//: 每台各出一份干净文档，坏法在拷贝上做，互不沾染。
const DOCS = Object.keys(DEV).sort().map((id) => [id, FY.toFyo(DEV[id])]);
console.log('\n=== 坏文档必须被拒 ===');
let untested = 0;
for (const [what, need, mutate] of REJECT) {
  const hit = DOCS.find(([, d]) => need(d));
  if (!hit) {
    console.log(`  ${what.padEnd(22)} ★没测到：这一版没有一台机器带这一节`);
    untested += 1;
    continue;
  }
  const [id, clean] = hit;
  const doc = JSON.parse(JSON.stringify(clean));
  mutate(doc);
  let msg = null;
  try { FY.fromFyo(doc); } catch (e) { msg = e.message; }
  console.log(`  ${what.padEnd(22)} [${id}] ${msg ? '✓ 拒绝：' + msg : '✗ 被接受了'}`);
  if (!msg) bad += 1;
}
if (untested)
  console.log(`★${untested} 条坏法没测到——语料里缺那一节，不是被测代码通过了。`);

console.log('\n判定：' + (bad ? `装置读写不通过（${bad} 项）` : '装置读写通过'));
process.exit(bad ? 1 : 0);
