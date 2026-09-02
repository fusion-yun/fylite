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
import { presets } from './_preset.mjs';

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
const REJECT = [
  ['@type 不对', (d) => { d['@type'] = 'something/else'; }],
  ['没有线圈', (d) => { d.pf_active.coil = []; }],
  ['网格盒缺失', (d) => { delete d['fylite:grid']; }],
  ['网格上下界反了', (d) => { const g = d['fylite:grid']; const t = g.rmin; g.rmin = g.rmax; g.rmax = t; }],
  ['限制器出网格盒', (d) => { d.wall.description_2d[0].limiter.unit[0].outline.r[0] = 1e3; }],
  ['通道指向不存在的线圈', (d) => { d['fylite:channel_map'] = [[[999, 1]]]; }],
  ['线圈缺 width', (d) => { delete d.pf_active.coil[0].element[0].geometry.rectangle.width; }],
  ['磁通环坐标是 NaN', (d) => { d.magnetics.flux_loop[0].position[0].r = 'x'; }],
  //: ★a declared launcher with half a band must be refused rather than
  //: half-read: the band is what the page's defaults come from, and a
  //: launcher that lost its upper end would silently become the markup's.
  ['LH 天线的 n∥ 带不成对', (d) => {
    d.lh_antennas = { antenna: [{ name: 'LH1', frequency: 2.45e9,
                                  'fylite:max_power': 4e6,
                                  'fylite:n_parallel': [2.0] }] };
  }],
  ['LH 天线没有铭牌功率', (d) => {
    d.lh_antennas = { antenna: [{ name: 'LH1', frequency: 2.45e9,
                                  'fylite:n_parallel': [1.9, 2.4] }] };
  }],
];
console.log('\n=== 坏文档必须被拒 ===');
for (const [what, mutate] of REJECT) {
  const doc = JSON.parse(JSON.stringify(FY.toFyo(DEV.iter)));
  mutate(doc);
  let msg = null;
  try { FY.fromFyo(doc); } catch (e) { msg = e.message; }
  console.log(`  ${what.padEnd(22)} ${msg ? '✓ 拒绝：' + msg : '✗ 被接受了'}`);
  if (!msg) bad += 1;
}

console.log('\n判定：' + (bad ? `装置读写不通过（${bad} 项）` : '装置读写通过'));
process.exit(bad ? 1 : 0);
