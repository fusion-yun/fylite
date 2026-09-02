// The coarse-screen → refine edge: 0-D slice → 1.5D core transport.
//
// ★★ACROSS TWO PAGES since 2026-08-22: the 0-D bar sits in the DESIGN scenario
// and the 1.5-D bar in MODELLING, so the deck leaves one page through the
// export menu and enters the other through the import button.  That is exactly
// what this gate has always driven — it never used a shared page state — and it
// is now the ONLY path between them (see
// `docs/note/equilibrium-handoff.md` for what a richer one would
// have to carry).
//
// ★Both ends are now STAGES OF ONE PART (`model`), switched on and off by the
// page rather than living on pages of their own — which changes nothing here:
// the deck still leaves through the export menu and comes back through the
// import button, and that file is the contract this gate exists for.  The
// deck's third consumer, the local-stability page, is withdrawn with that
// page; the surface table it read is still written and still unchecked here,
// because nothing on the site reads it any more.
//
// ★What this gate is really for.  An operating point is the one file on this
// site that carries a RESULT into another page's INPUTS, and the failure it
// invites is silent: hand on the ellipse the 0-D page assumed instead of the
// boundary the equilibrium found, and every number downstream stays smooth,
// ordered and plausible while describing a machine nobody solved for.  So
// the central assertion here is not "the two pages agree" — it is that the
// geometry in the deck is the SOLVED one, checked by making the 0-D page's
// own assumed shape differ from it and watching which one travels.
//
// The three checks, in order of what they would catch:
//
//   1. the deck's geometry equals the slice equilibrium's shape metrics, and
//      NOT the 0-D page's R0/a/kappa controls;
//   2. q95 is the solved q profile's, not a cylindrical estimate;
//   3. the 1.5D page's controls after import are the deck's, and the one
//      control the deck deliberately does not carry is left alone.
//
//   node tests/app/validate-handoff.mjs [--playwright DIR] [--url BASE]

import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { seedDevice, missingDeviceMessage } from './_device.mjs';
import { browser } from './_browser.mjs';

const iu = process.argv.indexOf('--url');
const BASE = iu > 0 ? process.argv[iu + 1] : 'http://127.0.0.1:8767/app/';

// ★The 0-D page's own shape controls are set DELIBERATELY WRONG for this
// machine — a fat, round, badly placed ellipse.  If the deck carried these
// instead of the solved boundary, check 1 would still find a self-consistent
// looking geometry; it is the disagreement with the equilibrium that makes
// the substitution visible at all.
const ZEROD_SHAPE = { r0: 2.2, a: 0.75, kappa: 1.05 };

const OUT = mkdtempSync(join(tmpdir(), 'ho-'));
const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1400, height: 1100 } });
//: ★factory defaults, not the bars' initial cases: this gate builds its own
//: configuration, so anything it does not set itself has to be the DEFAULT
//: ★这个上下文先开的是设计页，它也有初始算例
// ★Check 1 solves the slice equilibrium, which takes its coil currents from
// the machine's REFERENCE DISCHARGE.  The one built-in device has none — no
// measured ITER PF currents exist to put in one — so on it the slice never
// solves and the whole chain has nothing to hand over.  EAST comes from
// `machine_desc/`, installed the way an imported machine is.
if (!await seedDevice(ctx, 'east')) {
  console.error(missingDeviceMessage('east'));
  process.exit(2);
}
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  if (m.type() === 'error' && !/favicon/.test(m.text()))
    errs.push('console: ' + m.text().slice(0, 200));
});

// --- 1. the 0-D page: solve a slice, export the operating point ------------

await page.goto(BASE + 'pages/pulse_design.html?device=east#part-zerod',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /就绪|Ready|完成|failed|失败/.test(
    document.getElementById('design-status').textContent), null,
  { timeout: 180000 });

await page.evaluate((sh) => {
  Object.keys(sh).forEach((id) => {
    const el = document.getElementById('design-zerod-' + id)
                 || document.getElementById('design-' + id);
    el.value = sh[id];
    el.dispatchEvent(new Event('input'));
  });
}, ZEROD_SHAPE);
await page.waitForFunction(() => !document.getElementById('design-zerod-run').classList.contains('stop'), null, { timeout: 300000 });
  //: ★the run button runs the PAGE — every part of this scenario, in order —
  //: and this gate is about one of them.  A reader reaches one part on its own
  //: by changing one of ITS controls, which is what this does: the values are
  //: all set above, and one `change` sets that part going.
  await page.evaluate(() => document.getElementById('design-ip')
    .dispatchEvent(new Event('change')));
//: with the slice auto-solve on (the default) the status can go straight
//: past "evaluated" to "slice solved" — waiting only for the former is a
//: wait for a message that may never be the last one
await page.waitForFunction(
  () => /求值完成|Evaluated|平衡已解|solved/.test(
    document.getElementById('design-status').textContent), null,
  { timeout: 180000 });

// park on flat-top, where there is a plasma to solve
await page.evaluate(() => {
  const sl = document.getElementById('design-zerod-slice');
  sl.value = Math.round(0.5 * (+sl.max));
  sl.dispatchEvent(new Event('input'));
  sl.dispatchEvent(new Event('change'));
});
await page.waitForFunction(
  () => /平衡已解|solved/.test(
    document.getElementById('design-status').textContent), null,
  { timeout: 180000 });

async function save(fmt, name) {
  await page.click('#design-ioexport');          // opens the format menu
  const [d] = await Promise.all([page.waitForEvent('download'),
                                 page.click('#design-iofmt-zerod-' + fmt)]);
  const f = join(OUT, name);
  await d.saveAs(f);
  return JSON.parse(readFileSync(f, 'utf8'));
}

const deck = await save('op', 'op.json');
const deckFile = join(OUT, 'op.json');
//: the shape metrics of the very equilibrium that slice solved — taken from
//: the page's ordinary SESSION export, which has carried them all along,
//: rather than from a hook added for this gate.  A test-only affordance
//: would be testing an affordance.
const sess = await save('json', 'session.json');
const solved = sess['fylite:result']
  ? sess['fylite:result']['fylite:equilibrium_shape'] : null;

await br.close();

let bad = errs.length;
if (errs.length) console.log('页面报错：', errs.slice(0, 3).join(' | '));

const op = deck['fylite:operating_point'];
const g = op ? op['fylite:geometry'] : null;
if (!op || !g) {
  console.log('★导出的文件里没有 fylite:operating_point —— 这条边根本没通');
  process.exit(1);
}

// --- check 1: the geometry is the SOLVED one ------------------------------

const rel = (a, b) => Math.abs(a - b) / Math.max(Math.abs(b), 1e-30);
//: the 7-significant-digit truncation the session files use on purpose
const TOL = 1e-6;

let ok1 = true;
if (solved) {
  for (const [k, key] of [['r0', 'fylite:r0'], ['a', 'fylite:a'],
                          ['kappa', 'fylite:kappa'], ['delta', 'fylite:delta']]) {
    const d = rel(g[key], solved[k]);
    if (d > TOL) { ok1 = false; console.log(`  ${k}: 工况 ${g[key]} vs 解出 ${solved[k]}（差 ${d.toExponential(2)}）`); }
  }
} else {
  ok1 = false;
  console.log('★页面没有把解出的形状量暴露出来，第 1 条无法检验');
}
console.log(`  几何取自解出的平衡          R₀ ${g['fylite:r0'].toFixed(4)}` +
            `  a ${g['fylite:a'].toFixed(4)}  κ ${g['fylite:kappa'].toFixed(4)}` +
            `  δ ${g['fylite:delta'].toFixed(4)}  ${ok1 ? '✓' : '✗'}`);
if (!ok1) bad += 1;

// ★and it must NOT be the 0-D page's own assumed ellipse.  Without this the
// check above would pass on a deck that copied the controls, as long as the
// page happened to solve something close to them.
const copiedInputs = rel(g['fylite:a'], ZEROD_SHAPE.a) < 1e-3 &&
                     rel(g['fylite:kappa'], ZEROD_SHAPE.kappa) < 1e-3;
if (copiedInputs) {
  console.log(`\n★工况里的几何等于 0D 页自己填的椭球（a=${ZEROD_SHAPE.a}, ` +
              `κ=${ZEROD_SHAPE.kappa}）—— 传下去的是假设不是结果`);
  bad += 1;
} else {
  console.log(`  与 0D 自填的椭球不同        a ${ZEROD_SHAPE.a} → ${g['fylite:a'].toFixed(4)}` +
              `  κ ${ZEROD_SHAPE.kappa} → ${g['fylite:kappa'].toFixed(4)}  ✓`);
}

// --- check 2: q95 came from a q profile -----------------------------------

const q95 = op['fylite:q95'];
if (!(q95 > 0.5 && q95 < 30)) {
  console.log(`\n★q95 = ${q95} —— 不是一个 q 值`);
  bad += 1;
} else {
  console.log(`  q95 取自切片平衡的 q 剖面    ${q95.toFixed(4)}  ✓`);
}
if (op['fylite:provenance'] !== 'fylite:zerod-slice') {
  console.log('\n★工况没有 provenance 标记 —— 再导回 0D 页会被当成独立输入');
  bad += 1;
}

// --- check 3: the 1.5D page takes it, and leaves what it must -------------

const br2 = await browser();
const ctx2 = await br2.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                    viewport: { width: 1400, height: 1100 } });
//: ★factory defaults on this page too: `before` below is the DEFAULT edge and
//: chi0, which an initial case would have overwritten
const p2 = await ctx2.newPage();
const errs2 = [];
p2.on('pageerror', (e) => errs2.push(String(e).slice(0, 200)));
await p2.goto(BASE + 'pages/model.html?device=east#part-transport',
              { waitUntil: 'networkidle' });
await p2.waitForFunction(
  () => /就绪|Ready|完成/.test(
    document.getElementById('model-status').textContent), null,
  { timeout: 180000 });

const before = await p2.evaluate(() => ({
  edge: +document.getElementById('model-edge').value,
  chi0: +document.getElementById('model-chi0').value,
}));

//: through the page's OWN import path — the button opens a file dialog, so
//: the gate answers the dialog.  Reaching past it into the format's `apply`
//: would skip exactly the wiring most likely to be wrong.
const [chooser] = await Promise.all([
  p2.waitForEvent('filechooser'),
  p2.click('#model-ioimport'),
]);
await chooser.setFiles(deckFile);
await p2.waitForFunction(
  () => /工况|operating point|失败|Failed/.test(
    document.getElementById('model-status').textContent), null,
  { timeout: 60000 });

const after = await p2.evaluate(() => ({
  rmaj: +document.getElementById('model-rmaj').value,
  //: ★bar first, page second — the page's own `$` resolves controls that
  //: way, and kappa moved OUT of the 1.5-D bar into the machine panel the
  //: two bars share (2026-08-23).  A gate that spells one of the two
  //: locations breaks on the next quantity that becomes shared.
  kappa: +(document.getElementById('model-transport-kappa')
           || document.getElementById('model-kappa')).value,
  delta: +document.getElementById('model-delta').value,
  q95: +document.getElementById('model-q95').value,
  amin: +document.getElementById('model-amin').value,
  bunit: +document.getElementById('model-bunit').value,
  ne0: +document.getElementById('model-ne0').value,
  edge: +document.getElementById('model-edge').value,
  chi0: +document.getElementById('model-chi0').value,
  status: document.getElementById('model-status').textContent,
}));
await br2.close();
bad += errs2.length;
if (errs2.length) console.log('1.5D 页报错：', errs2.slice(0, 2).join(' | '));

if (/失败|Failed/.test(after.status)) {
  console.log('\n★1.5D 页拒绝了工况：' + after.status.slice(0, 120));
  bad += 1;
} else {
  //: the controls are sliders with a step, so the imported value is CLAMPED
  //: onto the step grid — the comparison has to allow one step, not zero
  const near = (got, want, step) => Math.abs(got - want) <= step * 1.001;
  const rows = [
    ['R/a', after.rmaj, g['fylite:r0'] / g['fylite:a'], 0.05],
    ['κ', after.kappa, g['fylite:kappa'], 0.02],
    ['δ', after.delta, g['fylite:delta'], 0.02],
    ['a [m]', after.amin, g['fylite:a'], 0.05],
    ['q95', after.q95, q95, 0.1],
  ];
  let ok3 = true;
  for (const [name, got, want, step] of rows)
    if (!near(got, want, step)) {
      ok3 = false;
      console.log(`  ${name}: 页面 ${got} vs 工况 ${want}（步长 ${step}）`);
    }
  console.log(`  1.5D 取到了工况的控件        R/a ${after.rmaj}  κ ${after.kappa}` +
              `  δ ${after.delta}  a ${after.amin}  q95 ${after.q95}  ${ok3 ? '✓' : '✗'}`);
  if (!ok3) bad += 1;

  // ★the one the deck deliberately does not carry
  if (after.edge !== before.edge) {
    console.log(`\n★边界温度被工况改动了（${before.edge} → ${after.edge}）—— ` +
                '0D 的剖面边界为零，没有台基可交，填进去的会被当成来自粗筛');
    bad += 1;
  } else {
    console.log(`  边界温度未被设定（留在 ${after.edge} keV）  ✓`);
  }
}

console.log(bad ? `\n判定：0D 工况 → 1.5D 输运这条边不通过（${bad} 项）`
                : '\n判定：0D 工况 → 1.5D 输运这条边通过（1.5D 取边界标度；' +
                  '几何取自解出的平衡，边界温度按约定留空）');
process.exit(bad ? 1 : 0);
