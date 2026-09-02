// Oracle gate for what the analysis scenario gained beyond a single magnetic
// fit: the channel table, the chord channels read backwards, the vessel
// unknown, the profile-fit bar and the time-series bar.
//
// `validate-recon.mjs` already scores the fit itself against the native
// kernel.  This one scores the LAYERS AROUND it, and every check here is one
// that can fail while that one passes:
//
//   1. THE FIGURE OF MERIT IS THE CHANNELS.  The weighted chi^2 the page
//      quotes is recomputed here from the exported per-channel list.  A page
//      that scored chi^2 over rows it did not fit — or kept scoring a channel
//      the reader switched off — reads perfectly and is wrong.
//   2. THE MASK IS THE FIT.  Switching channels off must change the row count
//      the fit was given, the degrees of freedom AND the answer.  A mask that
//      reached the table and not the solver would look identical here except
//      for the number of ticks.
//   3. SELF-CALIBRATION IS A RATIO, NOT A RESIDUAL.  The factor column is
//      recomputed as computed/measured against its own median.
//   4. THE INTERFEROMETER INVERTS.  Chord densities predicted from a known
//      (n_e0, alpha) are fed back in as measurements; the fit must return the
//      two numbers they were made from, to within the scan step.  This is the
//      one check that says the backward path is the forward path.
//   5. THE FARADAY ROWS ARE THE FIELD.  The exported constraint carries the
//      two independent routes' disagreement; internal-field rows built the
//      wrong way sit at tens of per cent (measured: 46 %) and still fit.
//   6. THE VESSEL ANSWERS OR REFUSES.  With loops alone the twin's injected
//      eddy currents are not identifiable and the page must SAY so; with the
//      probes in, the well-determined group must come back.
//   7. A FAILED SLICE IS NOT A ZERO.  The series file must carry `null` and
//      a named reason, never a plausible number.
//   8. THE PROFILE FIT RETURNS THE PROFILE.  Points sampled from a known
//      polynomial must be reproduced by the fitted curve.
//   9. AN UPSTREAM THAT MOVED IS SAID SO.  Re-fitting the profile after a
//      reconstruction must grow the note, and pressing the key must clear it.
//      Three states, not one: a note that always said it would pass a
//      one-sided check and mean nothing.
//  10. A PRESET SETS THE QUESTION, IT DOES NOT ANSWER IT.  It must move the
//      switches and must NOT start a solve — watched with an observer put on
//      the run key BEFORE the click, because a run that started and finished
//      leaves the status line saying what it said before.
//  11. THE PINNED COLUMN IS THE PREVIOUS RUN.  Cell for cell, against the run
//      before it, while the reconstruction column has moved.
//  12. Ip IS A CHANNEL OF THE BASIS TOO.  Switching the channel basis must
//      switch the Ip equality constraint with it — the deck carries both the
//      delivered current and the raw Rogowski one, they differ by 1.9 %, and
//      fitting raw loops against a delivered current is the mixture the
//      basis note itself forbids.
//  13. THE CURSOR CARRIES THE INSTANT.  Clicking the time series must re-fit
//      that slice and the verdict must say which — including when the slice
//      does not converge, where the previous fit used to stand unmarked.
//  14. THE DECK'S TIME AXIS IS THE DECK'S.  Nine slices, and the nine times
//      are the ones in the device document on disk.
//  15. THE CONTROLS SPLIT INTO 必设 / 进阶, and folding one away removes
//      nothing: every control in a closed group is still reachable by id and
//      still travels in the session file.
//  16. THE PAGE'S ONE STATUS LINE SAYS WHOSE MESSAGE IT IS.
//  17. A QUEUE THAT RUNS N FITS UNATTENDED REPORTS EACH ONE HONESTLY.  Both
//      kinds of row present; the converged ones satisfy the two criteria the
//      page rejects on, recomputed here; the rejected ones name which one
//      failed; each row carries its own shot, instant and channel basis
//      (deck document as oracle); a converged row is the SAME COMPUTATION as
//      a single run of that (shot, instant); and a queue that is stopped says
//      so, with the entries it never reached reading 未运行 rather than the
//      numbers they carried a moment earlier.
//  18. THE FILE'S CONSTRAINT IS THE FIT'S CONSTRAINT (T-A15).  A session file
//      exported after picking a slice must record the current that slice was
//      constrained to, not the page's reference/basis one — and a plain run
//      must record the basis one again, or "always the slice's" would be
//      just as wrong.
//  19. THE POSTERIOR FOLLOWS THE PICKED SLICE (T-A16).  Error bars drawn for
//      one instant under figures showing another are the same class of
//      failure as §11's pinned column.  The median must MOVE when the slice
//      does, and must move onto that slice's own deterministic fit.
//  20. A SERIES FILE THIS PAGE WROTE, THIS PAGE CAN READ (T-A14).  Export →
//      import → re-run must reproduce the trajectory, the file must carry
//      each slice's own readings, and a file missing them must be REFUSED
//      rather than quietly re-fitted on the reference instant's.
//
// ★Runs on EAST, installed from `machine_desc/` the way an imported machine
// is — the built-in devices carry no reference discharge.
//
//   node app/tests/validate-analysis.mjs [--playwright DIR] [--chrome BIN] [--url BASE]

import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { browser } from './_browser.mjs';
import { seedDevice, deviceDoc, missingDeviceMessage } from './_device.mjs';

const iu = process.argv.indexOf('--url');
const BASE = iu > 0 ? process.argv[iu + 1] : 'http://127.0.0.1:8767/app/';

const OUT = mkdtempSync(join(tmpdir(), 'ana-'));
const DEV = deviceDoc('east');
if (!DEV) { console.error(missingDeviceMessage('east')); process.exit(2); }

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1500, height: 1300 } });
await seedDevice(ctx, 'east');
const errs = [];
/** A page of this scenario, wired to the error log. */
async function newPage(context) {
  const pg = await context.newPage();
  pg.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
  pg.on('console', (m) => {
    //: ★the analysis page probes the MDSplus gateway once at load
    //: (`mds-source.js` → `api/health`) and is DESIGNED to keep working
    //: without one — on the bare http-server this gate runs against, the
    //: probe 404s by design, and the browser's own resource-load complaint
    //: cannot be suppressed from script.  Same standing as the favicon
    //: line; filtered by URL because the complaint's text carries none.
    if (m.type() === 'error' && !/favicon/.test(m.text())
        && !/\/api\/health$/.test((m.location() || {}).url || ''))
      errs.push('console: ' + m.text().slice(0, 200));
  });
  return pg;
}
let page = await newPage(ctx);

/**
 * A reader who has just opened the page, on the same machine.
 *
 * ★★THE SECTIONS ABOVE IMPORT FILES, and an import REPLACES the shot's
 * measurements — the chord readings, the probe readings, the pressure points.
 * That is what those sections are for, and it is also why the sections below
 * cannot run on what they leave behind: measured here, the delivered-basis fit
 * lands on χ² 3.30e-4 against the deck's own 4.55e-4, and the raw basis stops
 * converging altogether.  Neither number would be telling us anything about
 * the cursor or the Ip constraint, which is what those sections are about.  A
 * fresh CONTEXT rather than a reload: the page remembers its controls in
 * `localStorage`, so reloading would restore exactly the settings we are
 * trying to leave.
 */
async function freshPage() {
  const c2 = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                   viewport: { width: 1500, height: 1300 } });
  await seedDevice(c2, 'east');
  page = await newPage(c2);
  await page.goto(BASE + 'pages/analysis.html?device=east',
                  { waitUntil: 'networkidle' });
  await page.waitForFunction(() => /就绪|Ready/.test(
    document.getElementById('analysis-status').textContent), null,
    { timeout: 180000 });
}

const set = (id, v) => page.evaluate(([i, x]) => {
  const e = document.getElementById(i);
  e.value = x; e.dispatchEvent(new Event('input'));
}, [id, v]);
const check_ = (id, v) => page.evaluate(([i, x]) => {
  const e = document.getElementById(i);
  e.checked = x; e.dispatchEvent(new Event('change'));
}, [id, v]);
const text = (id) => page.evaluate(
  (i) => { const e = document.getElementById(i); return e ? e.textContent : ''; }, id);

/**
 * Press one bar's run key and wait for THAT run.
 *
 * ★Waits for the page to go busy first.  A status line still reading "done"
 * from the previous run satisfies the finish condition immediately, and every
 * number read after that belongs to the previous question — which is how a
 * gate comes to pass while measuring nothing.
 */
/**
 * `run`, plus the assertion that the run SUCCEEDED.
 *
 * ★`doneRe` matches 失败 as well as 完成 — it has to, or a gate whose run
 * broke would hang instead of reporting.  But every section below reads
 * numbers off the screen afterwards, and a failed run leaves the PREVIOUS
 * run's numbers there: measured here once, a picked slice that did not
 * converge left the verdict quoting the fit before it, and the check that
 * read it was scoring a run that never happened.
 */
async function runOk(bar, doneRe, what) {
  const st = await run(bar, doneRe);
  check(`${what}：这一次确实算成了`, !/失败|failed/.test(st), st.slice(0, 72));
  return st;
}

async function run(bar, doneRe, timeout = 600000) {
  const key = `#analysis-${bar}-run`;
  await page.waitForFunction((k) => !document.querySelector(k)
    .classList.contains('stop'), key, { timeout: 300000 });
  await page.click(key);
  await page.waitForFunction((k) => document.querySelector(k)
    .classList.contains('stop'), key, { timeout: 60000 }).catch(() => {});
  await page.waitForFunction((re) => new RegExp(re).test(
    document.getElementById('analysis-status').textContent), doneRe, { timeout });
  return page.evaluate(() => document.getElementById('analysis-status').textContent);
}

async function save(fmt, name) {
  await page.click('#analysis-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#analysis-iofmt-' + fmt)]);
  const f = join(OUT, name);
  await dl.saveAs(f);
  return JSON.parse(readFileSync(f, 'utf8'));
}

/** The same download, kept as text — the batch bar also writes a csv. */
async function saveRaw(fmt, name) {
  await page.click('#analysis-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#analysis-iofmt-' + fmt)]);
  const f = join(OUT, name);
  await dl.saveAs(f);
  return readFileSync(f, 'utf8');
}

async function importFile(f, doneRe) {
  const [chooser] = await Promise.all([page.waitForEvent('filechooser'),
                                       page.click('#analysis-ioimport')]);
  await chooser.setFiles(f);
  await page.waitForFunction((re) => new RegExp(re).test(
    document.getElementById('analysis-status').textContent), doneRe,
    { timeout: 60000 });
}

await page.goto(BASE + 'pages/analysis.html?device=east',
                { waitUntil: 'networkidle' });
await page.waitForFunction(() => /就绪|Ready/.test(
  document.getElementById('analysis-status').textContent), null, { timeout: 180000 });

let bad = 0;
function check(name, ok, detail) {
  console.log(`  ${ok ? '✓' : '✗'} ${name}${detail ? '   ' + detail : ''}`);
  if (!ok) bad += 1;
}
const rel = (a, b) => Math.abs(a - b) / Math.max(Math.abs(b), 1e-30);

// --- 1 & 2: the channels, and the mask ------------------------------------

console.log('\n=== 一、加权 χ² 就是那些通道 ===');
await check_('reconstruction-neon', true);
await run('reconstruction', '重构完成|失败');
const A = await save('reconstruction-json', 'a.json');
const magA = A['fylite:result'].magnetics.flux_loop;
const chi2A = magA.reduce((s, l) => {
  const d = l['fylite:weight'] * (l['fylite:reconstructed'] - l.flux.data);
  return s + d * d;
}, 0);
const nFitA = magA.filter((l) => l['fylite:weight'] > 0).length;
check('页面的 χ² 可由导出的逐道读数重算（1e-6）',
      rel(chi2A, A['fylite:result']['fylite:chi2']) < 1e-6,
      `${chi2A.toExponential(4)} vs ${A['fylite:result']['fylite:chi2'].toExponential(4)}`);
check('参与拟合的道数与 n_fitted 一致',
      nFitA === A['fylite:result']['fylite:n_fitted'],
      `${nFitA} vs ${A['fylite:result']['fylite:n_fitted']}`);

console.log('\n=== 二、掩膜进的是求解器，不只是表 ===');
const OFF = 3;
//: ★ONE AT A TIME, re-querying each round: the table redraws on every change,
//: so a list of nodes captured before the first click is a list of nodes that
//: no longer exist — and only the first switch takes.  (This gate caught that
//: on itself: it asked for three channels and got one.)
for (let k = 0; k < OFF; k++) {
  await page.evaluate(() => {
    const box = Array.from(document.querySelectorAll(
      '#reconstruction-chan-body input[data-chan]'))
      .filter((b) => !b.disabled && b.checked)[0];
    box.checked = false;
    box.dispatchEvent(new Event('change', { bubbles: true }));
  });
}
await run('reconstruction', '重构完成|失败');
const B = await save('reconstruction-json', 'b.json');
const magB = B['fylite:result'].magnetics.flux_loop;
const nFitB = magB.filter((l) => l['fylite:weight'] > 0).length;
const maskB = (B['fylite:config'] || {})['fylite:loop_mask'] || [];
check('会话文件带掩膜，且关掉的道数对得上',
      maskB.filter((v) => !v).length === OFF,
      `${maskB.filter((v) => !v).length} 道关闭 / ${maskB.length}`);
check('掩膜掉的道权重为零、不再参与拟合', nFitB === nFitA - OFF,
      `${nFitA} → ${nFitB}`);
const chi2B = magB.reduce((s, l) => {
  const d = l['fylite:weight'] * (l['fylite:reconstructed'] - l.flux.data);
  return s + d * d;
}, 0);
check('关道之后的 χ² 仍可由文件重算（1e-6）',
      rel(chi2B, B['fylite:result']['fylite:chi2']) < 1e-6,
      `${chi2B.toExponential(4)} vs ${B['fylite:result']['fylite:chi2'].toExponential(4)}`);
//: ★the answer must MOVE.  A mask that reached the weights but not the
//: solution would pass every count above and change nothing physical.
check('关道之后拟合结果确实变了',
      A['fylite:result']['fylite:li3'] !== B['fylite:result']['fylite:li3'],
      `li(3) ${A['fylite:result']['fylite:li3'].toFixed(6)} → ` +
      `${B['fylite:result']['fylite:li3'].toFixed(6)}`);

console.log('\n=== 三、自标定是比值，不是残差 ===');
const facs = magB.map((l) => (l['fylite:weight'] > 0 && l.flux.data !== 0)
  ? l['fylite:reconstructed'] / l.flux.data : NaN).filter(isFinite);
const sorted = facs.slice().sort((a, b) => a - b);
const med = sorted.length % 2 ? sorted[(sorted.length - 1) / 2]
  : 0.5 * (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]);
const shown = await page.evaluate(() => {
  const tr = document.querySelectorAll('#reconstruction-chan-body tr');
  const out = [];
  tr.forEach((r) => {
    const td = r.querySelectorAll('td');
    out.push([td[1].textContent.trim(), td[7] ? td[7].textContent.trim() : '']);
  });
  return out;
});
const anyCal = shown.filter((r) => r[1] && r[1] !== '—').length;
check('逐道表里有自标定一列', anyCal > 0, `${anyCal} 行带因子`);
//: the column is f/median; the median of the column itself must therefore be
//: 1 to the precision it is printed at
const col = shown.map((r) => parseFloat(r[1])).filter((v) => isFinite(v))
                 .sort((a, b) => a - b);
const colMed = col.length % 2 ? col[(col.length - 1) / 2]
  : 0.5 * (col[col.length / 2 - 1] + col[col.length / 2]);
check('该列确为 f / 中位数（列的中位数 = 1）', Math.abs(colMed - 1) < 5e-3,
      `列中位数 ${colMed.toFixed(4)}，重算的 f 中位数 ${med.toFixed(4)}`);

// --- 4: the interferometer, backwards -------------------------------------

console.log('\n=== 四、干涉弦反过来能定出它正过来用的那两个数 ===');
const NE0 = 4.7, ALPHA = 1.15;
await page.evaluate(() => {
  const boxes = Array.from(document.querySelectorAll(
    '#reconstruction-chan-body input[data-chan]'));
  boxes.forEach((b) => { if (!b.disabled && !b.checked) {
    b.checked = true; b.dispatchEvent(new Event('change', { bubbles: true })); } });
});
await set('reconstruction-ne0', NE0);
await set('reconstruction-nepk', ALPHA);
await run('reconstruction', '重构完成|失败');
const magDoc = await save('reconstruction-magnetics', 'm.json');
writeFileSync(join(OUT, 'm-in.json'), JSON.stringify(magDoc));
await importFile(join(OUT, 'm-in.json'), '已导入|imported');
await check_('reconstruction-pointfit', true);
await run('reconstruction', '重构完成|失败');
const note = await text('reconstruction-point-note');
const mNe = note.match(/n?e?0? ?= ?([\d.]+)×10/) || note.match(/= ([\d.]+)×10/);
const mAl = note.match(/α = ([\d.]+)/);
check('弦上的密度被还原（n_e0 与 α，容差 = 扫描步长）',
      !!(mNe && mAl) && Math.abs(+mNe[1] - NE0) < 0.05 &&
      Math.abs(+mAl[1] - ALPHA) < 0.05,
      mNe && mAl ? `n_e0 ${mNe[1]} (${NE0})，α ${mAl[1]} (${ALPHA})` : '未报出');

// --- 5: the Faraday rows --------------------------------------------------

console.log('\n=== 五、法拉第行与解出的场是同一件事 ===');
await page.click('#reconstruction-tab-twin');
await check_('reconstruction-farfit', true);
await run('reconstruction', '重构完成|失败');
const magF = await save('reconstruction-magnetics', 'f.json');
const fc = magF['fylite:faraday_constraint'];
check('导出的磁量文件带法拉第约束的全部记账', !!fc,
      fc ? `${fc['fylite:rows']} 行，外迭代 ${fc['fylite:outer_iterations']}` : '缺');
check('行 vs 场两条独立路径一致（<5%）',
      !!fc && fc['fylite:rows_vs_field_relative'] < 0.05,
      fc ? `${(100 * fc['fylite:rows_vs_field_relative']).toFixed(2)} %` : '—');
//: ★the target is the reading MINUS the coils' share; if that subtraction
//: were dropped the rows would ask the plasma to account for the coils
if (fc) {
  const pt = DEV['fylite:point'] || {};
  const cFar = (pt['fylite:faraday_constant'] || 0) *
               Math.pow(pt['fylite:laser_wavelength'] || 0, 2);
  let worstT = 0;
  fc['fylite:measured_deg'].forEach((deg, i) => {
    const full = deg * Math.PI / 180 / (2 * cFar);
    worstT = Math.max(worstT, rel(fc['fylite:target'][i],
                                  full - fc['fylite:coil_share'][i]));
  });
  check('约束值 = 读数换算 − 线圈份额（1e-5）', worstT < 1e-5,
        `最大相对差 ${worstT.toExponential(1)}`);
}

// --- 6: the vessel, answered or refused -----------------------------------

console.log('\n=== 六、真空室：能定就给数，定不出就明说 ===');
await check_('reconstruction-farfit', false);
await check_('reconstruction-vesselfit', true);
await set('reconstruction-vinject', 12);
await check_('reconstruction-probefit', false);
await run('reconstruction', '重构完成|失败');
const vNoLoops = await text('reconstruction-vessel-note');
check('只有磁通环时拒绝作答，并给出残存比例',
      /看不见|cannot see/.test(vNoLoops) && /%/.test(vNoLoops),
      vNoLoops.slice(0, 70));
await check_('reconstruction-probefit', true);
await run('reconstruction', '重构完成|失败');
const V = await save('reconstruction-json', 'v.json');
const vc = V['fylite:result']['fylite:vessel_currents'];
check('加上探针之后给出逐组电流与它的可辨识记账', !!vc,
      vc ? `${vc['fylite:groups'].join(' / ')}，留下 ${vc['fylite:svd_modes_kept']} 个模` : '缺');
//: ★THE CRITERION IS THE EQUILIBRIUM, NOT THE THREE CURRENTS.  Only the
//: combinations these channels can see are determined — the page says so and
//: reports how many modes it kept — so requiring each group's current back
//: would be a gate on a quantity the method never claims.  What the vessel
//: unknown IS for is the equilibrium it distorts: with the currents injected
//: and unmodelled the twin's own truth is missed, and fitting them must
//: recover it.
const vTruth = await page.evaluate(() => {
  const o = {};
  document.querySelectorAll('#reconstruction-scalars tr').forEach((tr) => {
    const td = tr.querySelectorAll('td');
    if (td.length >= 3) o[td[0].textContent.trim()] =
      [parseFloat(td[1].textContent), parseFloat(td[2].textContent)];
  });
  return o;
});
const errOn = Math.abs(vTruth['q0'][0] - vTruth['q0'][1]);
await check_('reconstruction-vesselfit', false);
await run('reconstruction', '重构完成|失败');
const vOff = await page.evaluate(() => {
  const o = {};
  document.querySelectorAll('#reconstruction-scalars tr').forEach((tr) => {
    const td = tr.querySelectorAll('td');
    if (td.length >= 3) o[td[0].textContent.trim()] =
      [parseFloat(td[1].textContent), parseFloat(td[2].textContent)];
  });
  return o;
});
const errOff = Math.abs(vOff['q0'][0] - vOff['q0'][1]);
//: ★threshold recalibrated at kernel v108: the guarded limiter-ψ boundary
//: rule moved the twin's truth/fit pair slightly, and the recovery measured
//: here went from >2x to 1.67x (|Δq0| 0.920 → 0.552, a 40 % cut).  The
//: claim this line makes — fitting the vessel moves q(0) MARKEDLY toward
//: truth, on currents nobody measured — survives; "误差减半" was a number
//: pinned to the pre-v108 boundary rule, not part of the claim.
check('拟合真空室之后，孪生的 q(0) 明显更接近真值（误差至少缩小三分之一）',
      errOn < 0.67 * errOff,
      `|Δq0| ${errOff.toFixed(3)}（不拟合）→ ${errOn.toFixed(3)}（拟合）`);
if (vc) check('逐组电流与真值一并写进文件（可辨识的那几个组合才算数）',
              Array.isArray(vc['fylite:truth']) &&
              vc['fylite:truth'].length === vc['fylite:current'].length,
              vc['fylite:truth']
                ? vc['fylite:current'].map((v, i) =>
                    `${(v / 1e3).toFixed(1)}/${(vc['fylite:truth'][i] / 1e3).toFixed(1)}`).join(' ')
                : '缺');

// --- 7: a slice either is a plasma or is a null, never a number ------------
//
// ★★THIS SECTION USED TO PASS ON NOTHING.  It asserted "one null per stated
// reason", which a run in which 4 of 4 slices failed satisfies without saying
// anything at all — the degenerate pass `app/tests/README.md` forbids.  And
// the other side of the same coin was worse: on a clean page the same sweep
// solved 4 of 4, two of them with q95 = 0.013 — the page counting a 3.6 cm,
// 215 MA filament against the outboard limiter as a solved slice.  So the
// section now runs from a defined starting state, asserts the run contains
// BOTH kinds of slice, and scores the survivors as plasmas.

console.log('\n=== 七、解出来的必须是等离子体，没解出来的写 null 带原因 ===');
//: ★from a fresh page for the same reason sections 十二/十三 are: the six
//: sections above leave imports, masks and switches in force, and this one is
//: about the series bar, not about their residue.  With that residue this
//: sweep fails 4 of 4 and the section measures nothing.
await freshPage();
await page.click('#analysis-series-tab-twin');
const NS = 4, IP0 = 320, IP1 = 700;    // the far end will not solve
await set('analysis-series-nslice', NS);
await set('analysis-series-ip0', IP0);
await set('analysis-series-ip1', IP1);
await run('series', '时间序列完成|失败');
const S = await save('series-series', 's.json');
const tt = S['fylite:time'], sc = S['fylite:scalars'];
check('每条标量轨迹与时间轴等长',
      Object.keys(sc).every((k) => sc[k].length === tt.length),
      `${tt.length} 片`);
const q95 = sc['fylite:q95'];
const nulls = q95.filter((v) => v === null).length;
const okIdx = q95.map((v, i) => (v === null ? -1 : i)).filter((i) => i >= 0);
const failed = S['fylite:failed_slices'] || [];
//: ★★THE NON-DEGENERACY CHECK.  Everything below compares the two kinds of
//: slice against each other; with only one kind present there is nothing to
//: compare and every other line here is vacuously true.
check('这条扫描既有解出来的片、也有没解出来的片（否则本节什么也没测）',
      okIdx.length > 0 && nulls > 0,
      `${okIdx.length} 片解出 / ${nulls} 片未解出，共 ${tt.length} 片`);
check('未解出的片在文件里是 null 且带原因',
      nulls === failed.length && failed.every((f) => f['fylite:why']),
      `${nulls} 个 null / ${failed.length} 条原因` +
      (failed[0] ? `（首条：${String(failed[0]['fylite:why']).slice(0, 40)}）` : ''));

//: ★ORACLE 1: the ramp the two sliders DEFINE — computed here, not read back
//: from the page.  `ip0 → ip1` linear over `nslice` points is what the labels
//: say, and it is the current the fit was constrained to.
const wantIp = (i) => (IP0 + (NS > 1 ? i / (NS - 1) : 0) * (IP1 - IP0)) * 1e3;
//: ★ORACLE 2: the machine's own half-width, read straight out of the deck
//: document on disk — the same polygon the page fits inside, parsed here
//: rather than through the page's device reader.
const limR = [];
for (const d2 of DEV.wall.description_2d || [])
  for (const u of ((d2.limiter || {}).unit) || [])
    for (const r of (u.outline || {}).r || []) limR.push(r);
const aMachine = 0.5 * (Math.max(...limR) - Math.min(...limR));
//: tolerance source: `ipFitted` integrates the fitted current density over the
//: plasma mask ON THE GRID, while `ip` is the equality the normal equations
//: imposed — one quantity, two computations, differing by grid quadrature.
//: Measured here on the surviving slices: 3.1e-5.  1e-3 is 32x that.
let worstIp = 0, worstA = Infinity;
for (const i of okIdx) {
  worstIp = Math.max(worstIp, rel(sc['fylite:ipFitted'][i], wantIp(i)));
  worstA = Math.min(worstA, sc['fylite:a'][i]);
}
//: ★tolerance recalibrated at kernel v108: the guarded boundary rule moves
//: which cells the plasma mask claims at the edge, and the mask is exactly
//: what `ipFitted`'s quadrature runs over — measured here 3.1e-5 before,
//: 2.1e-3 after (≈1 kA of one boundary-cell ring on a 447 kA slice).  5e-3
//: still asks the same question — did the equality constraint HOLD — and
//: stays 1e2 below the 0.5 that `notAPlasma` rejects filaments at.
check('解出来的那几片确实满足了它们的 Ip 等式约束（5e-3，源：网格求积）',
      okIdx.length > 0 && worstIp < 5e-3,
      `最大相对差 ${worstIp.toExponential(1)}`);
check(`解出来的那几片是等离子体，不是一团（a > 0.1 × 真空室半宽 = ${(0.1 * aMachine).toFixed(3)} m）`,
      okIdx.length > 0 && worstA > 0.1 * aMachine,
      `最小 a = ${isFinite(worstA) ? worstA.toFixed(3) : '—'} m，` +
      `真空室半宽 ${aMachine.toFixed(3)} m`);
//: ★AND THE REJECTED ONES SAY WHICH TEST THEY FAILED — a bare "failed" would
//: leave the reader unable to tell a kernel that gave up from a solve that
//: returned nonsense, and those call for different next moves.
check('被判未解出的那几片，说清是哪一条不成立',
      failed.length > 0 && failed.every(
        (f) => /等式约束|不是等离子体|gs_inverse_solve|发散|奇异/
          .test(String(f['fylite:why']))),
      failed.map((f) => String(f['fylite:why']).slice(0, 34)).join(' ／ '));
//: ★AND THEY ARE KEPT OUT OF THE CROSS-SLICE CALIBRATION.  That table is a
//: median of computed/measured ACROSS slices; a 215 MA filament's ratios would
//: poison every channel in it.
const cal = S['fylite:channel_calibration'];
const used = cal ? Math.max(...cal['fylite:slices_used']) : NaN;
check('未解出的片不进逐道跨时片标定',
      !!cal && isFinite(used) && used <= okIdx.length,
      `标定最多用到 ${used} 片，解出来的有 ${okIdx.length} 片`);
check('出处写明这是孪生扫描而不是一炮放电',
      S['fylite:provenance'] === 'synthetic-twin-sweep',
      S['fylite:provenance']);

//: ★★AND THE SAME TEST ON THE BAR A READER ACTUALLY WATCHES.  The single
//: reconstruction had the identical hole and it is the worse of the two:
//: measured on the twin at Ip = 700 kA, the page reported 「重构完成」 over
//: a = 0.036 m at R = 2.325 m, q95 = 0.012 and chi^2 = 4.85e10 — a 3.6 cm
//: filament against the outboard limiter — and said nothing.  Two runs, one
//: either side of the cliff, because "it rejects" is worth nothing without
//: "and it still accepts the good one".
await page.click('#reconstruction-tab-twin');
await set('reconstruction-ip', 450);
const stGood = await run('reconstruction', '重构完成|重构失败');
const good = await page.evaluate(() => {
  const o = {};
  document.querySelectorAll('#reconstruction-scalars tr').forEach((tr) => {
    const td = tr.querySelectorAll('td');
    if (td.length >= 2) o[td[0].textContent.trim()] = parseFloat(td[1].textContent);
  });
  return o;
});
const aKey = Object.keys(good).find((k) => /^a\b/.test(k));
check('孪生在 450 kA 上照常解出，而且解出来的是等离子体',
      !/失败|failed/.test(stGood) && good[aKey] > 0.1 * aMachine,
      `a = ${good[aKey]} m（下限 ${(0.1 * aMachine).toFixed(3)} m）`);
await set('reconstruction-ip', 700);
const stBad = await run('reconstruction', '重构完成|重构失败');
check('孪生在 700 kA 上退化成一团电流丝，页面按失败报出并说明为什么',
      /失败|failed/.test(stBad) &&
      /等式约束|不是等离子体/.test(stBad),
      stBad.slice(0, 62));
const vdBad = await text('reconstruction-verdict');
check('可信度一行也说这一次没解出来，而不是把上一次的数字当成这一次',
      /没有解出来|did not solve/.test(vdBad), vdBad.slice(0, 52) + '…');
await page.click('#reconstruction-tab-real');

// --- 8: the profile fit returns the profile -------------------------------

console.log('\n=== 八、剖面拟合还原它被喂进去的那条剖面 ===');
const X = [], Y = [], SG = [];
const f = (x) => 8000 * (1 - 0.9 * x * x) + 500;
for (let i = 0; i < 21; i++) {
  const x = i / 20;
  X.push(x); Y.push(f(x)); SG.push(10);
}
const pts = { '@context': { fylite: 'urn:fylite:' },
              '@type': 'fylite:AppSession/1', 'fylite:page': 'profile_points',
              'fylite:points': { 'fylite:psi_norm': X, 'fylite:value': Y,
                                 'fylite:sigma': SG,
                                 'fylite:quantity': 'pressure' },
              'fylite:provenance': 'gate-synthetic-quadratic' };
const pf = join(OUT, 'points.json');
writeFileSync(pf, JSON.stringify(pts));
await importFile(pf, '已导入|imported');
await run('profile', '剖面拟合完成|失败');
const P = await save('profile-profile', 'p.json');
const curve = P['fylite:pressure'];
let worstP = 0;
for (let i = 0; i < curve.length; i++)
  worstP = Math.max(worstP, rel(curve[i], f(i / (curve.length - 1))));
check('拟合出的曲线在整条 ψ̄ 上复现源多项式（1e-3）', worstP < 1e-3,
      `最大相对差 ${worstP.toExponential(1)}`);
check('文件写明阶数由 GCV 选、以及点数与基',
      !!(P['fylite:fit'] && P['fylite:fit']['fylite:order_chosen_by'] === 'gcv'),
      P['fylite:fit'] ? `第 ${P['fylite:fit']['fylite:order']} 阶，` +
        `${P['fylite:fit']['fylite:points']} 点，${P['fylite:fit']['fylite:basis']}` : '缺');
check('出处随文件走（导入的点不冒充测量）',
      P['fylite:provenance'] === 'gate-synthetic-quadratic',
      String(P['fylite:provenance']));

// --- 9: the upstream that moved after you ran (T-A2) ------------------------
//
// ★★THE NOTICE WAS WRITTEN AND UNREACHABLE.  `drawKineticSource` has computed
// this staleness since the pin batch, but `S.publish` wakes nobody, so the
// only times the note was ever redrawn were during the reconstruction bar's
// own run — the one moment at which it cannot be stale.  Measured before the
// wake was added: re-fit the profile, wait, read the note, and it is the same
// sentence forever.  Three states are asserted here, not one: absent, then
// present, then absent again.  A note that simply always said it would pass a
// one-sided check and mean nothing.

console.log('\n=== 九、上游剖面变了要说（T-A2）===');
await page.click('#analysis-profile-tab-deck');
await run('profile', '剖面拟合完成|失败');
await run('reconstruction', '重构完成|失败');
const kin0 = await text('reconstruction-kin-note');
check('刚重构完，注记不说「已重算」', !/已重算/.test(kin0), kin0.slice(0, 60) + '…');
//: a DIFFERENT profile, not the same one twice: the sigma moves the points
await set('analysis-profile-sigma', 0.15);
await run('profile', '剖面拟合完成|失败');
const kin1 = await text('reconstruction-kin-note');
check('剖面重拟之后，注记长出「已重算」字样', /已重算/.test(kin1),
      (kin1.match(/★[^★]*已重算[^。]*。/) || [kin1])[0].slice(0, 70));
await run('reconstruction', '重构完成|失败');
const kin2 = await text('reconstruction-kin-note');
check('再按一次计算键，该字样消失', !/已重算/.test(kin2), kin2.slice(0, 60) + '…');

// --- 10: a preset sets the question, it does not answer it (T-A3 a) --------

console.log('\n=== 十、预设改设定，但不开算（T-A3 a）===');
const boxIds = ['reconstruction-kin', 'reconstruction-neon',
                'reconstruction-probefit', 'reconstruction-pointfit',
                'reconstruction-farfit', 'reconstruction-vesselfit'];
const boxes = () => page.evaluate((ids) => ids.map(
  (i) => document.getElementById(i).checked), boxIds);
//: put the switches somewhere the preset must move them AWAY from
await page.evaluate((ids) => ids.forEach((i) => {
  const e = document.getElementById(i);
  if (!e.checked) { e.checked = true; e.dispatchEvent(new Event('change', { bubbles: true })); }
}), boxIds);
const before = await boxes();
const scal0 = await text('reconstruction-scalars');
//: ★watch the run key from BEFORE the click: "no run happened" cannot be read
//: off a status line afterwards, because a run that started and finished
//: leaves the line saying exactly what it said before.
await page.evaluate(() => {
  window.__ranDuringPreset = false;
  const k = document.getElementById('analysis-reconstruction-run');
  new MutationObserver(() => {
    if (k.classList.contains('stop')) window.__ranDuringPreset = true;
  }).observe(k, { attributes: true, attributeFilter: ['class'] });
});
await page.click('#reconstruction-preset-mag');
await page.waitForTimeout(2500);
const after = await boxes();
const ranIt = await page.evaluate(() => window.__ranDuringPreset);
//: the oracle is what 纯磁反演 MEANS — magnetics and nothing else — not a
//: copy of the table in the source
check('「纯磁反演」把六个非磁开关全部关上',
      after.every((v) => v === false) && before.some((v) => v === true),
      `${before.filter(Boolean).length} 个开 → ${after.filter(Boolean).length} 个开`);
check('按预设不开算（计算键自始至终没进过运行态）', ranIt === false,
      ranIt ? '★点了预设就跑了一次' : '未运行');
check('屏幕上的答案没有被预设改动',
      (await text('reconstruction-scalars')) === scal0, '标量表逐字未变');
//: ★put the pressure rows back before the sections below.  「纯磁反演」 means
//: magnetics and nothing else, and magnetics alone does not form a plasma on
//: this deck's ramp slices — leaving the preset in force would make the
//: sections that follow measure the preset instead of what they are about.
await check_('reconstruction-kin', true);

// --- 11: the pinned column is the PREVIOUS run (T-A3 b) --------------------

console.log('\n=== 十一、钉住列就是上一次那次（T-A3 b）===');
const cols = () => page.evaluate(() => {
  const o = {};
  document.querySelectorAll('#reconstruction-scalars tr').forEach((tr) => {
    const td = tr.querySelectorAll('td');
    if (!td.length) return;
    const name = td[0].textContent.trim();
    o[name] = { recon: td[1] ? td[1].textContent.trim() : null,
                pin: (() => { const p = tr.querySelector('td.pin-col');
                              return p ? p.textContent.trim() : null; })() };
  });
  return o;
});
await run('reconstruction', '重构完成|失败');
const P1 = await cols();
const pinHidden = await page.evaluate(() => {
  const th = document.getElementById('reconstruction-th-pin');
  return !th || th.style.display === 'none'; });
check('没钉住时，钉住列的表头是收起的', pinHidden,
      pinHidden ? '表头未显示' : '★空列却有表头');
await page.click('#reconstruction-pin');
//: move the ANSWER, not just a label: a different p′ order is a different fit
await page.selectOption('#reconstruction-npp', '3');
await run('reconstruction', '重构完成|失败');
const P2 = await cols();
const pinShown = await page.evaluate(() => {
  const th = document.getElementById('reconstruction-th-pin');
  return !!th && th.style.display !== 'none'; });
check('钉住之后，钉住列的表头出现', pinShown);
const named = Object.keys(P1).filter((k) => P1[k].recon && P1[k].recon !== '—');
const pinnedRows = named.filter((k) => P2[k] && P2[k].pin && P2[k].pin !== '—');
const moved = named.filter((k) => P2[k] && P2[k].recon !== P1[k].recon);
//: ★NON-DEGENERATE: if the second run answered the same thing, "the pin equals
//: the previous run" is satisfied by the pin equalling the current one too.
check('第二次拟合的答案确实动了（否则这一项什么也没测）', moved.length > 0,
      moved.slice(0, 3).map((k) => `${k} ${P1[k].recon}→${P2[k].recon}`).join('，'));
const pinWrong = pinnedRows.filter((k) => P2[k].pin !== P1[k].recon);
check('钉住列逐格等于上一次的重构列',
      pinnedRows.length > 0 && pinWrong.length === 0,
      `${pinnedRows.length} 格比对，${pinWrong.length} 格不符` +
      (pinWrong.length ? `（${pinWrong[0]}: ${P2[pinWrong[0]].pin} vs ${P1[pinWrong[0]].recon}）` : ''));
await page.click('#reconstruction-unpin');
await page.selectOption('#reconstruction-npp', '2');

// --- 12: the deck's nine slices, and pointing at one of them (T-A3 d, e) ---

console.log('\n=== 十二、卷宗九个时片，点一个就重算那一片（T-A3 d/e）===');
await freshPage();
//: the oracle is the DECK DOCUMENT on disk, read here, not through the page
const deckSlices = (DEV['fylite:slices'] || []).map((s2) => s2.time_s);
await page.click('#analysis-series-tab-deck');
await run('series', '时间序列完成|失败');
const SD = await save('series-series', 'sd.json');
check('卷宗时片数 = 9', SD['fylite:time'].length === 9,
      `${SD['fylite:time'].length} 片`);
check('九个时刻与卷宗文件里的逐个相同（1e-9）',
      deckSlices.length === SD['fylite:time'].length &&
      deckSlices.every((t, i) => Math.abs(t - SD['fylite:time'][i]) < 1e-9),
      `${SD['fylite:time'].join(' / ')} s`);
//: ★the instant is one the gate CHOSE, and it is not the reference slice the
//: page would have shown anyway (4 s) — otherwise "the verdict carries that
//: instant" would be satisfied by a verdict that never moved.
/**
 * Click the time series at one instant, and wait for what that starts.
 *
 * ★The pixel is solved from the plot's own inverse, and the canvas is
 * scrolled into view first: `page.mouse.click` takes VIEWPORT coordinates and
 * this page is several screens long, so a rect read for a canvas below the
 * fold sends the click to whatever happens to be on screen.
 */
async function pickSlice(t) {
  await page.evaluate(() => document.getElementById('analysis-series-ip')
    .scrollIntoView({ block: 'center' }));
  await page.waitForTimeout(200);
  const hit = await page.evaluate((tt) => {
    const c = document.getElementById('analysis-series-ip');
    const m = c.fyxy; if (!m) return null;
    const r = c.getBoundingClientRect();
    //: toData is affine in the pixel, so two samples invert it exactly
    const a = m.toData(0, r.height / 2), b = m.toData(r.width, r.height / 2);
    const px = (tt - a.x) / (b.x - a.x) * r.width, py = r.height / 2;
    const d = m.toData(px, py);
    return { x: r.left + px, y: r.top + py, inside: d.inside, got: d.x };
  }, t);
  if (!hit || !hit.inside) return { hit: hit, status: null };
  await page.waitForFunction((k) => !document.querySelector(k)
    .classList.contains('stop'), '#analysis-reconstruction-run',
    { timeout: 300000 });
  await page.mouse.click(hit.x, hit.y);
  await page.waitForFunction((k) => document.querySelector(k)
    .classList.contains('stop'), '#analysis-reconstruction-run',
    { timeout: 60000 }).catch(() => {});
  await page.waitForFunction((re) => new RegExp(re).test(
    document.getElementById('analysis-status').textContent), '重构完成|重构失败',
    { timeout: 900000 });
  return { hit: hit, status: await page.evaluate(
    () => document.getElementById('analysis-status').textContent) };
}
const lbl = (t) => (+t).toFixed(3).replace(/\.?0+$/, '') + ' s';

//: ★NOT the deck's reference slice (4 s): "the verdict carries that instant"
//: would be satisfied by a verdict that never moved off the moment the page
//: shows by default.
//: ★★AND IT IS AN INSTANT THE TRACE ABOVE SAYS SOLVES.  It used to be
//: `deckSlices[2]` (2 s), which the series bar rejects — and the pick
//: reported 「重构完成」 there, because the two routes were re-spelling "this
//: request, at that slice" differently and disagreeing about the answer (the
//: page-side copy had neither the slice's own `ip`/`prof` nor the rule that a
//: slice with no pressure of its own is fitted on magnetics alone).  With one
//: definition (`worker.js`, `seriesSlice`) the two agree, so the instant the
//: cursor is tested on is one the trace it was clicked on calls solved.
const T_PICK = deckSlices[3];
const A2 = await pickSlice(T_PICK);
check('时序图把自己的逆映射留在画布上，目标时刻落在图内',
      !!A2.hit && A2.hit.inside && Math.abs(A2.hit.got - T_PICK) < 1e-6,
      A2.hit ? `点在 t = ${A2.hit.got.toFixed(3)} s 处` : '缺 fyxy');
check(`点选那一片确实算成了（t = ${lbl(T_PICK)}）`,
      !/失败|failed/.test(A2.status || '失败'), (A2.status || '').slice(0, 66));
const vd = await text('reconstruction-verdict');
check(`点选之后，可信度一行带的是那一刻（t = ${lbl(T_PICK)}）`,
      vd.indexOf('t = ' + lbl(T_PICK)) === 0, vd.slice(0, 56) + '…');
//: ★the trace and the cursor are the same computation now, not two that
//: happen to agree: this is the instant the series above solved.
check('点选的这一刻，正是上面那条轨迹说解出来了的那一刻',
      SD['fylite:scalars']['fylite:q95'][3] !== null &&
      Math.abs(SD['fylite:time'][3] - T_PICK) < 1e-9,
      `轨迹在 t = ${lbl(T_PICK)} 处 q95 = ${SD['fylite:scalars']['fylite:q95'][3]}`);
check('带的不是卷宗的参考时刻（4 s）',
      Math.abs(T_PICK - (DEV['fylite:reference_discharge'] || {}).time_s) > 1e-6 &&
      vd.indexOf('t = 4 s') !== 0,
      `参考时刻 ${DEV['fylite:reference_discharge'].time_s} s`);

//: ★★AND THE INSTANT SURVIVES A SLICE THAT DOES NOT SOLVE.  Four of these
//: nine do not (the ramp — `docs/reference/fidelity.md` §逐时片重构), and a
//: failure leaves `last` holding the PREVIOUS fit: measured before this was
//: fixed, the verdict went on reading "t = 2 s" with the 2 s numbers under
//: every later pick.  Either outcome is acceptable here; quoting the moment
//: someone else asked about is not.
const T_RAMP = deckSlices[0];
const A1 = await pickSlice(T_RAMP);
const vd2 = await text('reconstruction-verdict');
check(`点一片爬升段（t = ${lbl(T_RAMP)}）之后，那一行说的还是刚点的那一刻`,
      vd2.indexOf('t = ' + lbl(T_RAMP)) >= 0 &&
      vd2.indexOf('t = ' + lbl(T_PICK)) < 0,
      (/失败|failed/.test(A1.status || '') ? '（该片未解出）' : '（该片解出）') +
      vd2.slice(0, 46) + '…');

// --- 13: Ip is a channel of the basis too (T-A3 c) -------------------------
//
// ★★The basis switch moved the 35 loops and left the Ip equality constraint
// on the delivered a-file number in both settings — the exact mixture the
// basis note two lines above forbids.  Both currents are in the deck; this
// asserts the fit is constrained by the one belonging to the basis it is in.

console.log('\n=== 十三、Ip 等式约束与磁通环同源（T-A3 c）===');
const RD = DEV['fylite:reference_discharge'] || {};
check('卷宗同时带交付 Ip 与原始 Rogowski Ip，且两者不同（非退化前提）',
      isFinite(RD.ip) && isFinite(RD.ipMeasured) &&
      rel(RD.ipMeasured, RD.ip) > 0.005,
      `交付 ${(RD.ip / 1e3).toFixed(1)} kA vs 原始 ${(RD.ipMeasured / 1e3).toFixed(1)} kA` +
      `（差 ${(100 * rel(RD.ipMeasured, RD.ip)).toFixed(2)} %）`);
await page.evaluate(() => {
  const e = document.getElementById('reconstruction-basis');
  e.value = 'delivered'; e.dispatchEvent(new Event('change'));
});
await runOk('reconstruction', '重构完成|失败', '交付基准');
const D = await save('reconstruction-json', 'ipd.json');
const cfgD = D['fylite:config'] || {};
check('交付基准：文件记的 Ip 约束就是卷宗的交付 Ip（1e-9）',
      cfgD['fylite:channel_basis'] === 'delivered' &&
      cfgD['fylite:ip_source'] === 'delivered' &&
      rel(cfgD['fylite:ip_constraint'], RD.ip) < 1e-9,
      `${cfgD['fylite:ip_source']} ${(cfgD['fylite:ip_constraint'] / 1e3).toFixed(2)} kA`);
const li3D = D['fylite:result']['fylite:li3'];
await page.evaluate(() => {
  const e = document.getElementById('reconstruction-basis');
  e.value = 'raw'; e.dispatchEvent(new Event('change'));
});
await runOk('reconstruction', '重构完成|失败', '原始基准');
const Rw = await save('reconstruction-json', 'ipr.json');
const cfgR = Rw['fylite:config'] || {};
check('原始基准：文件记的 Ip 约束换成了原始 Rogowski（1e-9）',
      cfgR['fylite:channel_basis'] === 'raw' &&
      cfgR['fylite:ip_source'] === 'raw' &&
      rel(cfgR['fylite:ip_constraint'], RD.ipMeasured) < 1e-9,
      `${cfgR['fylite:ip_source']} ${(cfgR['fylite:ip_constraint'] / 1e3).toFixed(2)} kA`);
//: ★the constraint must reach the SOLVER, not only the file
check('换基准之后拟合结果确实变了（约束进了求解器）',
      Rw['fylite:result']['fylite:li3'] !== li3D,
      `li(3) ${li3D.toFixed(6)} → ${Rw['fylite:result']['fylite:li3'].toFixed(6)}`);
const bn = await text('reconstruction-basis-note');
check('通道基准那一行当场说出用的是哪个 Ip',
      /Rogowski/.test(bn) && /同源/.test(bn), bn.slice(-46));
await page.evaluate(() => {
  const e = document.getElementById('reconstruction-basis');
  e.value = 'delivered'; e.dispatchEvent(new Event('change'));
});

// --- 14: every figure says which shot it is (T-A10) ------------------------
//
// ★A picture saved out of this page, or read over a shoulder, used to be a
// curve with no provenance at all while the FILENAMES had carried device,
// shot and time since they were written.  The twin says 合成 rather than a
// shot number: a synthetic run has no shot, and printing one would be a lie
// rather than an omission.

console.log('\n=== 十四、每张图带 装置 #炮号 @时刻（T-A10）===');
const stamps = () => page.evaluate(() => {
  const out = [];
  document.querySelectorAll('section[data-bar] figure').forEach((f) => {
    const st = f.querySelector(':scope > .figstamp-row > .figstamp');
    out.push({ bar: f.closest('section[data-bar]').dataset.bar,
               canvas: (f.querySelector('canvas') || {}).id || '?',
               stamp: st ? st.textContent.trim() : null });
  });
  return out;
});
const SH = (DEV['fylite:reference_discharge'] || {}).shot;
const st1 = await stamps();
const bare = st1.filter((f) => !f.stamp);
check('反演页每一张图都有角标', st1.length > 0 && bare.length === 0,
      `${st1.length} 张图，${bare.length} 张没有` +
      (bare.length ? `（${bare.slice(0, 2).map((f) => f.canvas).join(' ')}）` : ''));
//: the oracle is the deck document on disk: the shot number and the times
const reconStamps = st1.filter((f) => f.bar === 'reconstruction');
check(`平衡反演栏的角标带 装置 #${SH} @时刻`,
      reconStamps.length > 0 &&
      reconStamps.every((f) => f.stamp && f.stamp.indexOf('#' + SH) > 0 &&
                               /@[\d.]+ s$/.test(f.stamp)),
      reconStamps[0] ? reconStamps[0].stamp : '—');
const serStamps = st1.filter((f) => f.bar === 'series');
check('时间序列栏的角标带的是算出来的那一段时间',
      serStamps.length > 0 && serStamps.every(
        (f) => f.stamp && f.stamp.indexOf('#' + SH) > 0 &&
               f.stamp.indexOf('@' + lbl(deckSlices[0]).replace(' s', '') + '–' +
                               lbl(deckSlices[8]).replace(' s', '') + ' s') > 0),
      serStamps[0] ? serStamps[0].stamp : '—');
//: ★AND THE TWIN IS MARKED.  A synthetic run carrying a real shot number is
//: the one failure mode a stamp can have that is worse than no stamp.
await page.click('#reconstruction-tab-twin');
const st2 = (await stamps()).filter((f) => f.bar === 'reconstruction');
check('切到合成孪生之后，反演栏的角标标「合成」且不再带炮号',
      st2.length > 0 && st2.every((f) => f.stamp && /合成/.test(f.stamp) &&
                                         f.stamp.indexOf('#') < 0),
      st2[0] ? st2[0].stamp : '—');
await page.click('#reconstruction-tab-real');

// --- 15: 必设 / 进阶, and folding hides nothing (T-A11) ---------------------

console.log('\n=== 十五、控件分「必设 / 进阶」（T-A11）===');
const advState = () => page.evaluate(() => {
  const o = {};
  document.querySelectorAll('details.adv').forEach((d) => {
    o[d.id.replace('reconstruction-adv-', '')] =
      { open: d.open, ctls: d.querySelectorAll('input, select').length };
  });
  return o;
});
const A0 = await advState();
check('进阶分组存在，且每一组都真的装着控件',
      Object.keys(A0).length >= 6 &&
      Object.keys(A0).every((k) => A0[k].ctls > 0),
      Object.keys(A0).map((k) => `${k}:${A0[k].ctls}`).join(' '));
//: 纯磁反演 is magnetics and nothing else, so every gated group must fold away
await page.click('#reconstruction-preset-mag');
const Amag = await advState();
const gated = ['kinetic', 'density', 'vessel', 'point', 'probe'];
check('按「纯磁反演」之后，被关掉的那几块的进阶分组全部收起',
      gated.every((k) => Amag[k] && Amag[k].open === false),
      gated.map((k) => `${k}:${Amag[k].open ? '开' : '收'}`).join(' '));
await page.click('#reconstruction-preset-kin');
const Akin = await advState();
check('按「动理学反演」之后，它用到的那几块自动展开，用不到的仍收着',
      Akin.kinetic.open && Akin.density.open && Akin.point.open &&
      !Akin.vessel.open && !Akin.probe.open,
      gated.map((k) => `${k}:${Akin[k].open ? '开' : '收'}`).join(' '));
//: ★★FOLDING IS NOT REMOVING.  Every control inside a closed group must still
//: be reachable by id and still carry its value into the session file — that
//: is the whole reason the split is safe to make.
await page.click('#reconstruction-preset-mag');
const reach = await page.evaluate(() => {
  const ids = [];
  document.querySelectorAll('details.adv').forEach((d) => {
    if (d.open) return;
    d.querySelectorAll('input[id], select[id]').forEach((e) => ids.push(e.id));
  });
  return { ids: ids,
           found: ids.filter((i) => !!document.getElementById(i)).length };
});
check('收起的分组里每个控件仍能按 id 取到（折叠不影响可及性）',
      reach.ids.length > 0 && reach.found === reach.ids.length,
      `${reach.found} / ${reach.ids.length} 个可及`);
await runOk('reconstruction', '重构完成|失败', '收起进阶之后');
const AF = await save('reconstruction-json', 'adv.json');
const cfgF = AF['fylite:config'] || {};
const missing = reach.ids.filter(
  (i) => cfgF[i.replace('reconstruction-', '')] === undefined);
check('收起的分组里的设定照样写进会话文件',
      reach.ids.length > 0 && missing.length === 0,
      `${reach.ids.length - missing.length} / ${reach.ids.length} 项在文件里` +
      (missing.length ? `（缺 ${missing.slice(0, 3).join(' ')}）` : ''));

// --- 16: whose message is on the page's one status line (T-A13) ------------
//
// ★★Three bars, one line.  `scenario.js` says it outright — the page line only
// ever shows the newest message — and each bar's own strip is inside the bar,
// which can be folded or simply off screen.  So the line keeps its rule and
// gains the name of whoever is talking.

console.log('\n=== 十六、页面状态行说明是哪一栏在说话（T-A13）===');
const who = () => page.evaluate(() => {
  const st = document.getElementById('analysis-status');
  const w = st.querySelector('.who');
  return { who: w ? w.textContent.trim() : null, all: st.textContent.trim() };
});
await page.click('#analysis-profile-tab-deck');
await runOk('profile', '剖面拟合完成|失败', '剖面栏');
const W1 = await who();
await runOk('reconstruction', '重构完成|失败', '反演栏');
const W2 = await who();
check('剖面拟合栏说完话，页面状态行署它的名',
      !!W1.who && /剖面/.test(W1.who) && /剖面拟合完成/.test(W1.all),
      W1.all.slice(0, 48));
check('反演栏接着说话，署名跟着换成它，不是盖掉后无从分辨',
      !!W2.who && /反演|重构|平衡/.test(W2.who) && W2.who !== W1.who &&
      /重构完成/.test(W2.all),
      W2.all.slice(0, 48));

// --- 17: the batch queue (T-A12) -------------------------------------------
//
// ★★N FITS NOBODY IS WATCHING.  A single reconstruction is read by the person
// who asked for it; a queue produces a TABLE, and a table is exactly where
// 「求解器返回了」 stops being distinguishable from 「解出来了」 — which is the
// failure this page was audited for on 2026-08-23, when a 3.6 cm filament
// carrying 215 MA was counted as a solved reconstruction.  So this section
// asserts four things, and the first of them is that there is anything to
// assert:
//
//   · both kinds of row are present (without that, every line below is
//     vacuously true — the rule §七 was written for);
//   · the converged rows ARE what they claim to be, judged by the two
//     criteria the page already uses, recomputed here from the file;
//   · the rejected rows name which criterion failed;
//   · a converged row is the SAME COMPUTATION as a single run of that
//     (shot, instant), not a second one that agrees.
//
// ★And the provenance, which is the other half of a summary table: which
// shot, which instant, which channel basis, per ROW — with the deck document
// on disk as the oracle for all three.

console.log('\n=== 十七、批处理队列：N 个 (炮, 时刻) 跑完，一份汇总表（T-A12）===');
await freshPage();
//: ★TWO SOURCES IN ONE QUEUE, which is the point of a queue: the deck's nine
//: instants of #137985, and a two-point twin sweep that is not a shot at all.
//: The far end of that sweep (700 kA) is the 3.6 cm filament from the audit —
//: a deliberately unsolvable entry, put in the same table as the good ones.
await page.click('#analysis-series-tab-deck');
await page.click('#analysis-batch-add');
const qAfterDeck = await page.evaluate(
  () => document.querySelectorAll('#analysis-batch-queue tr').length);
await page.click('#analysis-series-tab-twin');
await set('analysis-series-nslice', 2);
await set('analysis-series-ip0', 320);
await set('analysis-series-ip1', 700);
await page.click('#analysis-batch-add');
const qAll = await page.evaluate(
  () => document.querySelectorAll('#analysis-batch-queue tr').length);
check('队列吃下两种来源的时片（卷宗九片 + 孪生两点）',
      qAfterDeck === deckSlices.length && qAll === deckSlices.length + 2,
      `${qAfterDeck} → ${qAll} 条`);

const stBatch = await run('batch', '批处理完成|批处理已中断|失败');
check('这一趟跑完了（而不是中断或失败）',
      /批处理完成/.test(stBatch) && !/中断|失败/.test(stBatch),
      stBatch.slice(0, 72));
const BQ = await save('batch-summary', 'batch.json');
const brows = BQ['fylite:rows'] || [];
check('汇总表一行一条，队列多长表就多长',
      BQ['fylite:queued'] === qAll && BQ['fylite:ran'] === qAll &&
      brows.length === qAll && BQ['fylite:interrupted'] === false,
      `queued ${BQ['fylite:queued']} / ran ${BQ['fylite:ran']} / ` +
      `${brows.length} 行 / 中断 ${BQ['fylite:interrupted']}`);

const okRows = brows.filter((r) => r['fylite:converged']);
const badRows = brows.filter((r) => r['fylite:state'] === 'reject');
//: ★★THE NON-DEGENERACY CHECK, first, because every line below compares the
//: two kinds against each other and with only one kind present says nothing.
check('这份汇总表既有已收敛的行、也有被拒的行（否则本节什么也没测）',
      okRows.length > 0 && badRows.length > 0 &&
      okRows.length + badRows.length === brows.length,
      `${okRows.length} 行已收敛 / ${badRows.length} 行未解出，共 ${brows.length} 行`);

//: ★ORACLE: the same two criteria the page rejects on, recomputed here from
//: the file — the Ip equality (`notAPlasma` rejects past 0.5) and the
//: machine's own half-width (0.1x, `aMachine` above, parsed from the deck
//: document on disk in §七).  This is「成功的那些确实是它们自称的东西」.
let worstRatio = 0, worstMinA = Infinity, missingIp = 0;
for (const r of okRows) {
  const c = r['fylite:ip_constraint'], f = r['fylite:ipFitted'];
  if (!(isFinite(c) && isFinite(f) && c)) { missingIp += 1; continue; }
  worstRatio = Math.max(worstRatio, Math.abs(f - c) / Math.abs(c));
  worstMinA = Math.min(worstMinA, r['fylite:a']);
}
check('每一行已收敛的都带上了它的 I_p 约束与拟合值两列',
      okRows.length > 0 && missingIp === 0,
      `${okRows.length - missingIp} / ${okRows.length} 行两列俱全`);
check('已收敛的那些确实满足了自己的 I_p 等式约束（判据 0.5，与页面同一条）',
      okRows.length > 0 && worstRatio < 0.5,
      `最大相对差 ${worstRatio.toExponential(2)}`);
check(`已收敛的那些是等离子体不是一团（a > 0.1 × 真空室半宽 = ${(0.1 * aMachine).toFixed(3)} m）`,
      okRows.length > 0 && worstMinA > 0.1 * aMachine,
      `最小 a = ${isFinite(worstMinA) ? worstMinA.toFixed(3) : '—'} m`);
//: ★and each rejected row says WHICH test it failed — a bare「没解出来」
//: leaves a reader unable to tell a kernel that gave up from a solve that
//: returned nonsense, and those call for different next moves.
check('每一行被拒的都写明是哪一条不成立',
      badRows.length > 0 && badRows.every(
        (r) => /等式约束|不是等离子体|gs_inverse_solve|发散|奇异|退化/
          .test(String(r['fylite:why'] || ''))),
      badRows.map((r) => String(r['fylite:why']).slice(0, 26)).join(' ／ '));
check('被拒的行不带任何一个看着像答案的数',
      badRows.every((r) => r['fylite:ipFitted'] === null &&
                           r['fylite:q95'] === null && r['fylite:li3'] === null &&
                           r['fylite:a'] === null),
      `${badRows.length} 行全空`);

// --- provenance: which shot, which instant, which channel basis ------------
//
// ★The oracle is the deck document on disk: its nine slice times, its shot
// number and — for the basis — the fact that each slice ships its own
// `loopMeasTotal`, which is the raw basis whatever the page's select says.

const deckRows = brows.filter((r) => r['fylite:source'] === 'deck');
const twinRows = brows.filter((r) => r['fylite:source'] === 'twin');
check('两种来源都在同一张表里（否则「跨炮」这件事没被测到）',
      deckRows.length === deckSlices.length && twinRows.length === 2,
      `卷宗 ${deckRows.length} 行 / 孪生 ${twinRows.length} 行`);
check(`卷宗那几行逐行带炮号 #${SH}，时刻与卷宗文件里的逐个相同（1e-9）`,
      deckRows.length === deckSlices.length &&
      deckRows.every((r, i) => r['fylite:shot'] === SH &&
                     Math.abs(r['fylite:time'] - deckSlices[i]) < 1e-9),
      deckRows.map((r) => r['fylite:time']).join(' / ') + ' s');
//: ★★A SYNTHETIC ROW MUST NOT CARRY A SHOT NUMBER.  Of everything a
//: provenance column can get wrong this is the worst: a real shot number over
//: a run that never happened is a lie rather than an omission.
check('孪生那两行不带炮号，也不冒充一炮放电',
      twinRows.length > 0 && twinRows.every(
        (r) => r['fylite:shot'] === null && r['fylite:synthetic'] === true &&
               String(r['fylite:shot_label']).indexOf('#') < 0 &&
               r['fylite:channel_basis'] === 'synthetic-twin'),
      twinRows.map((r) => r['fylite:shot_label']).join(' / '));
//: ★the deck's slices carry their own total flux, so the basis they are
//: fitted in is the RAW one — whatever the reconstruction bar's select says,
//: which on a fresh page is 交付重构的通道值
const selBasis = await page.evaluate(
  () => document.getElementById('reconstruction-basis').value);
check('卷宗那几行的通道基准是它们实际用的那一种（原始总磁通），不是控件上写的那一种',
      selBasis === 'delivered' &&
      deckRows.every((r) => r['fylite:channel_basis'] === 'raw-total-flux'),
      `控件 ${selBasis}，表里 ${deckRows[0] && deckRows[0]['fylite:channel_basis']}`);
//: ★AND THE CONSTRAINT IS THE SLICE'S OWN, oracle = the deck document
const deckIp = (DEV['fylite:slices'] || []).map((x) => x.ip);
const ipOff = deckRows.map((r, i) => rel(r['fylite:ip_constraint'], deckIp[i]))
                      .filter((v) => v > 1e-6);
check('每一行的 I_p 约束是那一片自己的电流（对卷宗文件，1e-6）',
      deckRows.length === deckIp.length && ipOff.length === 0,
      `${deckRows.length} 行逐行相同，例：${deckRows[0]['fylite:ip_constraint']} A`);

// --- the csv is the same table ---------------------------------------------
const csv = await saveRaw('batch-table', 'batch.csv');
const clines = csv.trim().split('\n');
const chead = clines[0].split(',');
check('CSV 与 JSON 是同一张表（行数、炮号、时刻、状态逐行相同）',
      clines.length === brows.length + 1 &&
      brows.every((r, i) => {
        const c = clines[i + 1].split(',');
        return c[1] === String(r['fylite:shot_label']) &&
               +c[2] === r['fylite:time'] &&
               c[6] === r['fylite:state'];
      }),
      `${clines.length - 1} 行，列名 ${chead.slice(0, 5).join(' ')}…`);

// --- a converged row IS a single run of that (shot, instant) ---------------
//
// ★★THE ONE CHECK THAT SAYS THE QUEUE IS THE PAGE AND NOT A SECOND PROGRAM.
// Both routes send the reconstruction bar's own request with one slice named
// on it, so this is the same computation twice rather than two that agree —
// and it is asserted because it USED NOT TO BE: with the page re-spelling
// what a slice does, t = 2.5 s came back solved from the series loop and
// 「法方程奇异」 from the single fit, on the same deck, same settings.

const pick = okRows.find((r) => r['fylite:source'] === 'deck');
check('汇总表里至少有一条卷宗行已收敛，可以拿来做单跑对照',
      !!pick, pick ? `t = ${pick['fylite:time']} s` : '一条也没有');
//: the bus is the documented gate entry (`app/tests/README.md`): the slice
//: list is the series bar's, the way to fit one is the reconstruction bar's
await page.click('#analysis-series-tab-deck');
await page.waitForFunction((k) => !document.querySelector(k)
  .classList.contains('stop'), '#analysis-reconstruction-run',
  { timeout: 300000 });
await page.evaluate((t) => {
  const bus = FyScenario.pages.analysis.bus;
  const ser = bus.series(), req = bus.reconstruction();
  const sl = ser.slices.filter((s2) => Math.abs(s2.time - t) < 1e-9)[0];
  const p = req.runSlice(sl, String(t) + ' s');
  if (p && p.catch) p.catch(() => {});
}, pick['fylite:time']);
await page.waitForFunction((k) => document.querySelector(k)
  .classList.contains('stop'), '#analysis-reconstruction-run',
  { timeout: 60000 }).catch(() => {});
await page.waitForFunction((re) => new RegExp(re).test(
  document.getElementById('analysis-status').textContent), '重构完成|重构失败',
  { timeout: 900000 });
const stOne = await text('analysis-status');
check(`单跑同一个 (炮, 时刻)（t = ${pick['fylite:time']} s）也解出来了`,
      !/失败|failed/.test(stOne), stOne.slice(0, 66));
const ONE = await save('reconstruction-json', 'one.json');
const or = ONE['fylite:result'] || {};
//: tolerance source: the summary file writes 7 significant digits
//: (`toPrecision(7)`, the rule every array this app exports follows) while
//: the session file writes the double.  Nothing else differs — it is one
//: computation — so anything above the rounding is a real disagreement.
const same = [['li3', or['fylite:li3'], pick['fylite:li3']],
              ['chi2', or['fylite:chi2'], pick['fylite:chi2']],
              ['ipFitted', or['fylite:ip_fitted'], pick['fylite:ipFitted']],
              ['a', (or['fylite:shape'] || {}).a, pick['fylite:a']]];
const worstSame = Math.max(...same.map(([, a, b]) => rel(a, b)));
check('已收敛那一行与单跑同一片逐格相同（1e-6，源：汇总表 7 位有效截断）',
      !/失败|failed/.test(stOne) && worstSame < 1e-6,
      same.map(([k, a, b]) => `${k} ${(+a).toPrecision(8)} vs ${b}`).join('；') +
      `（最大 ${worstSame.toExponential(1)}）`);

// --- interrupting -----------------------------------------------------------
//
// ★★A STOPPED QUEUE MUST NOT LEAVE THE LAST FULL TABLE STANDING.  That is the
// same class of failure as the four this page was audited for: a page
// reporting work it did not do.  The previous answer is dropped when the run
// STARTS, so the entries the interruption never reached read 未运行 — and
// this asserts it against the complete run just made, row by row.

const KEY = '#analysis-batch-run';
const wasNumbers = brows.map((r) => r['fylite:state']);
await page.waitForFunction((k) => !document.querySelector(k)
  .classList.contains('stop'), KEY, { timeout: 300000 });
await page.click(KEY);
await page.waitForFunction((k) => document.querySelector(k)
  .classList.contains('stop'), KEY, { timeout: 60000 });
//: ★a pending row is `tr.off`; wait until at least two entries have answered,
//: so the stop lands in the MIDDLE of the queue and not before it
await page.waitForFunction(() => document.querySelectorAll(
  '#analysis-batch-rows tr:not(.off)').length >= 2, null, { timeout: 600000 });
await page.click(KEY);                       // the run key is the stop key
const stStop = await page.waitForFunction((re) => new RegExp(re).test(
  document.getElementById('analysis-status').textContent), '中断',
  { timeout: 120000 }).then(() => text('analysis-status'));
check('队列可以中断，中断了就说自己中断了', /中断/.test(stStop),
      stStop.slice(0, 76));
const BS = await save('batch-summary', 'batch-stop.json');
const srows = BS['fylite:rows'] || [];
const notRun = srows.filter((r) => r['fylite:state'] === 'pending');
check('中断的那一趟自报「跑了几条 / 共几条」，且没有跑完',
      BS['fylite:interrupted'] === true && BS['fylite:ran'] < BS['fylite:queued'] &&
      BS['fylite:ran'] > 0 && BS['fylite:not_run'] === notRun.length &&
      notRun.length === BS['fylite:queued'] - BS['fylite:ran'],
      `跑了 ${BS['fylite:ran']} / ${BS['fylite:queued']} 条，${notRun.length} 条未运行`);
check('没跑到的那几条写「未运行」，一格数字都没有',
      notRun.length > 0 && notRun.every(
        (r) => r['fylite:converged'] === false && r['fylite:ipFitted'] === null &&
               r['fylite:q95'] === null && r['fylite:li3'] === null &&
               r['fylite:chi2'] === null && r['fylite:why'] === null &&
               r['fylite:channel_basis'] === null),
      `${notRun.length} 条`);
//: ★★AND THEY ARE NOT LAST TIME'S ANSWERS.  This is the assertion the whole
//: paragraph exists for: the same entries carried numbers a moment ago.
const wereAnswered = notRun.filter(
  (r) => wasNumbers[r['fylite:index']] !== 'pending').length;
check('上一趟给出过答案的那几条，这一趟写的是「未运行」而不是上一趟的数字',
      notRun.length > 0 && wereAnswered === notRun.length,
      `${wereAnswered} 条上一趟有答案（其中 ` +
      `${notRun.filter((r) => wasNumbers[r['fylite:index']] === 'ok').length} ` +
      `条上一趟已收敛），这一趟全部写「未运行」`);
const shownOff = await page.evaluate(() => ({
  all: document.querySelectorAll('#analysis-batch-rows tr').length,
  off: document.querySelectorAll('#analysis-batch-rows tr.off').length }));
check('屏幕上的表与文件说的是同一件事',
      shownOff.all === srows.length && shownOff.off === notRun.length,
      `屏幕 ${shownOff.off} / ${shownOff.all} 行未运行`);

// --- 18: the file's Ip constraint is the one the fit used (T-A15) ----------
//
// ★★`jsonDoc()` wrote the page's `ipConstraint()` — the reference/basis
// current — while a picked slice is constrained to THAT SLICE'S OWN current.
// Measured on this deck before the fix: the session file said 393.46 kA under
// fits actually constrained to 223–401 kA, one number for nine different
// questions.  The oracle here is the DECK DOCUMENT on disk: the worker imposes
// `msg.ipOverride` and a deck slice's `ipOverride` is its own `ip`, which §17
// already ties to the worker's own reply (the summary table takes
// `ipConstraint` off the reply and matches the same file to 1e-6).

console.log('\n=== 十八、会话文件记的 I_p 约束就是这次拟合用的那一个（T-A15）===');
await freshPage();
await page.click('#analysis-series-tab-deck');
await run('series', '时间序列完成|失败');
const SS = await save('series-series', 'ss.json');
const solvedIdx = SS['fylite:scalars']['fylite:q95']
  .map((v, i) => (v === null ? -1 : i)).filter((i) => i >= 0);
//: ★both kinds present, before anything below compares them
check('卷宗九片里既有解出来的也有没解出来的（非退化前提，才有片可点）',
      solvedIdx.length >= 2 && solvedIdx.length < SS['fylite:time'].length,
      `${solvedIdx.length} / ${SS['fylite:time'].length} 片解出`);
const T_A = SS['fylite:time'][solvedIdx[0]], T_B = SS['fylite:time'][solvedIdx[1]];
const deckIpAll = (DEV['fylite:slices'] || []).map((x) => x.ip);
const ipAt = (t) => deckIpAll[deckSlices.findIndex((x) => Math.abs(x - t) < 1e-9)];
check('这两片自己的电流与页面的基准电流确实不同（非退化前提）',
      rel(ipAt(T_A), RD.ip) > 0.005 && rel(ipAt(T_B), RD.ip) > 0.005,
      `t = ${lbl(T_A)} ${(ipAt(T_A) / 1e3).toFixed(2)} kA · ` +
      `t = ${lbl(T_B)} ${(ipAt(T_B) / 1e3).toFixed(2)} kA · ` +
      `基准 ${(RD.ip / 1e3).toFixed(2)} kA`);
for (const t of [T_A, T_B]) {
  const st = await pickSlice(t);
  check(`点选 t = ${lbl(t)} 这一片确实算成了`,
        !/失败|failed/.test(st.status || '失败'), (st.status || '').slice(0, 60));
  const FS = await save('reconstruction-json', `ipslice-${t}.json`);
  const cs = FS['fylite:config'] || {};
  check(`t = ${lbl(t)}：文件记的 I_p 约束是那一片自己的电流（对卷宗文件，1e-9）`,
        rel(cs['fylite:ip_constraint'], ipAt(t)) < 1e-9,
        `文件 ${cs['fylite:ip_constraint']} A，卷宗 ${ipAt(t)} A`);
  check(`t = ${lbl(t)}：而不再是页面的基准电流 ${(RD.ip / 1e3).toFixed(2)} kA`,
        rel(cs['fylite:ip_constraint'], RD.ip) > 0.005,
        `差 ${(100 * rel(cs['fylite:ip_constraint'], RD.ip)).toFixed(2)} %`);
  check(`t = ${lbl(t)}：文件同时说出这个数从哪来、属于哪一刻`,
        cs['fylite:ip_source'] === 'slice' &&
        Math.abs(cs['fylite:slice_time'] - t) < 1e-9,
        `ip_source ${cs['fylite:ip_source']} · slice_time ${cs['fylite:slice_time']}`);
  //: ★the same disease one column over: the select is the QUESTION and the
  //: deck slice's own total flux settles the basis differently
  check(`t = ${lbl(t)}：通道基准两栏并列——控件写 delivered，拟合用的是 raw-total-flux`,
        cs['fylite:channel_basis'] === 'delivered' &&
        cs['fylite:channel_basis_fitted'] === 'raw-total-flux',
        `${cs['fylite:channel_basis']} / ${cs['fylite:channel_basis_fitted']}`);
}
//: ★★AND THE OTHER SIDE OF IT.  A file that always wrote 「那一片自己的」
//: would be just as wrong; a plain run is the reference instant again and the
//: basis current is then the right answer.
await runOk('reconstruction', '重构完成|失败', '不点片、直接跑一次');
const NOSL = await save('reconstruction-json', 'noslice.json');
const cn = NOSL['fylite:config'] || {};
check('不点片直接跑，文件记回基准电流，且不再声称属于某一片',
      rel(cn['fylite:ip_constraint'], RD.ip) < 1e-9 &&
      cn['fylite:ip_source'] === 'delivered' &&
      cn['fylite:slice_time'] === undefined,
      `${cn['fylite:ip_source']} ${(cn['fylite:ip_constraint'] / 1e3).toFixed(2)} kA`);

// --- 19: the posterior follows the picked slice (T-A16) --------------------
//
// ★★`runPosterior` built its message without `sliceOn`, so pressing 跑后验
// after picking an instant drew error bars for the REFERENCE fit under figures
// showing the picked one.  The discriminating test is that the band MOVES when
// the slice does: before the fix both runs sent the identical message and came
// back with the identical ensemble.
//
// ★The source drawn over is the flux-loop sigma, not the pressure: a deck
// slice with no pressure of its own is fitted on magnetics alone, so the
// pressure switch has nothing to perturb there — which is the second thing
// this section asserts, because the page used to promise it anyway.

console.log('\n=== 十九、后验跟着时片走（T-A16）===');
await check_('reconstruction-kin', true);
await set('reconstruction-mcn', 4);
const runPost = async (doneRe = '后验完成|失败') => {
  const key = '#analysis-reconstruction-run';
  await page.waitForFunction((k) => !document.querySelector(k)
    .classList.contains('stop'), key, { timeout: 300000 });
  await page.click('#reconstruction-mcrun');
  await page.waitForFunction((k) => document.querySelector(k)
    .classList.contains('stop'), key, { timeout: 60000 }).catch(() => {});
  await page.waitForFunction((re) => new RegExp(re).test(
    document.getElementById('analysis-status').textContent), doneRe,
    { timeout: 900000 });
  return text('analysis-status');
};
await pickSlice(T_A);
const stNo = await runPost();
check('点了一片磁测量-only 的时刻之后，抽不到东西的后验被拒——而不是给一条宽度为 0 的误差棒',
      /失败/.test(stNo) && /没有任何一条来源可抽|Nothing is left/.test(stNo),
      stNo.slice(0, 72));
await set('reconstruction-mcloops', 0.002);
const post = {};
for (const t of [T_A, T_B]) {
  await pickSlice(t);
  const stP = await runPost();
  check(`t = ${lbl(t)} 的后验跑成了`, /后验完成/.test(stP), stP.slice(0, 60));
  const PF = await save('reconstruction-json', `post-${t}.json`);
  const po = (PF['fylite:result'] || {})['fylite:posterior'] || {};
  post[t] = { po: po, cfg: PF['fylite:config'] || {},
              gap: await text('reconstruction-mc-gap') };
}
//: ★非退化前提：两条带都真的有成员、都真的抽了东西
check('两片的后验都有收敛成员、都确实抽了某样东西（非退化前提）',
      [T_A, T_B].every((t) => post[t].po['fylite:members_ok'] > 0 &&
                              (post[t].po['fylite:varied'] || []).length > 0),
      [T_A, T_B].map((t) => `t=${lbl(t)} ${post[t].po['fylite:members_ok']}/` +
        `${post[t].po['fylite:members']} 成员，抽 ` +
        `${(post[t].po['fylite:varied'] || []).map((v) => v.source).join('+')}`).join('；'));
const p50 = (t) => post[t].po['fylite:statistics'].q95.p50;
check('换一片之后，后验的中位数跟着变（这一条在修好之前恒不成立：两趟发的是同一条消息）',
      rel(p50(T_A), p50(T_B)) > 0.4,
      `q95 中位数 t=${lbl(T_A)} ${p50(T_A).toFixed(4)} → ` +
      `t=${lbl(T_B)} ${p50(T_B).toFixed(4)}（差 ${(100 * rel(p50(T_A), p50(T_B))).toFixed(1)} %）`);
//: ★★AND IT MOVED TO THE RIGHT PLACE.  「变了」 alone would be satisfied by a
//: band drawn over anything at all; the oracle is the deterministic fit of
//: that same slice on the trace above, which the band must sit on and the
//: other slice's must not.
const traceQ = (t) => SS['fylite:scalars']['fylite:q95'][
  SS['fylite:time'].findIndex((x) => Math.abs(x - t) < 1e-9)];
const own = [T_A, T_B].map((t) => rel(p50(t), traceQ(t)));
const cross = [rel(p50(T_A), traceQ(T_B)), rel(p50(T_B), traceQ(T_A))];
check('每条带都落在它那一片自己那次拟合上（对时序轨迹 < 25 %），离另一片的远（> 40 %）',
      Math.max(...own) < 0.25 && Math.min(...cross) > 0.4,
      `本片 ${own.map((v) => (100 * v).toFixed(1) + ' %').join(' / ')}；` +
      `跨片 ${cross.map((v) => (100 * v).toFixed(1) + ' %').join(' / ')}`);
check('屏幕上的后验说明写明这条带属于哪一刻，文件里也记着',
      [T_A, T_B].every((t) => post[t].gap.indexOf('t = ' + lbl(t)) >= 0 &&
                    Math.abs(post[t].cfg['fylite:slice_time'] - t) < 1e-9),
      post[T_B].gap.slice(-30));

// --- 20: a series file this page wrote, this page can read (T-A14) ---------
//
// ★★`build` wrote `time` and `ip`; `apply` throws `ser.no_readings` unless a
// slice carries flux-loop readings — so a series file exported here could not
// be read back here, and a queue could not be assembled across SHOTS, because
// a shot's instants can only arrive in a file.  The fix writes the readings
// (the other way round — relaxing `apply` — would make every imported slice
// fall back on the reconstruction bar's own measurements, i.e. N identical
// fits under N different labels), so this drives the round trip and compares
// the trajectory.

console.log('\n=== 二十、时序文件写得出也读得回，重跑出同一条轨迹（T-A14）===');
await freshPage();
await page.click('#analysis-series-tab-deck');
await run('series', '时间序列完成|失败');
const RT1 = await save('series-series', 'rt1.json');
const rt1 = join(OUT, 'rt1.json');
const outSl = RT1['fylite:slices'] || [];
//: oracle: the deck document on disk says how wide a slice is
const nLoopDeck = (DEV['fylite:slices'] || [])[0].loopMeasTotal.length;
const nChanDeck = (DEV['fylite:slices'] || [])[0].aturns.length;
check('导出的时序文件逐片带自己的读数，而不只是时刻与电流',
      outSl.length === deckSlices.length && outSl.every(
        (e) => (e['fylite:flux_loop_total'] || []).length === nLoopDeck &&
               (e['fylite:weight'] || []).length === nLoopDeck &&
               (e['fylite:coil_current'] || []).length === nChanDeck &&
               isFinite(e['fylite:ip'])),
      `${outSl.length} 片，每片 ${nLoopDeck} 道磁通环 + ${nChanDeck} 道线圈电流`);
check('写出的读数就是卷宗里那一片的读数（逐位相同）',
      outSl.every((e, i) => e['fylite:flux_loop_total'].every(
        (v, k) => v === DEV['fylite:slices'][i].loopMeasTotal[k]) &&
        e['fylite:ip'] === DEV['fylite:slices'][i].ip),
      `${outSl.length} 片逐位对上卷宗文件`);
await importFile(rt1, '已导入|导入失败');
const busSer = await page.evaluate(() => {
  const s = FyScenario.pages.analysis.bus.series();
  return { n: s.slices.length, src: s.source, syn: s.synthetic, shot: s.shot };
});
check('这一页导出的时序文件，这一页导得回来',
      busSer.src === 'file' && busSer.n === deckSlices.length &&
      busSer.syn === false,
      `${busSer.n} 片，来源 ${busSer.src}`);
await run('series', '时间序列完成|失败');
const RT2 = await save('series-series', 'rt2.json');
const sc1 = RT1['fylite:scalars'], sc2 = RT2['fylite:scalars'];
let worstRT = 0, wKey = '', nullGap = 0, nCmp = 0;
for (const k of Object.keys(sc1)) {
  const u = sc1[k], v = sc2[k] || [];
  if (u.length !== v.length) { nullGap += 1; continue; }
  u.forEach((x, i) => {
    if (x === null || v[i] === null) {
      if ((x === null) !== (v[i] === null)) nullGap += 1;
      return;
    }
    nCmp += 1;
    const r = rel(x, v[i]);
    if (r > worstRT) { worstRT = r; wKey = `${k}[${i}]`; }
  });
}
const distinct = new Set(sc1['fylite:q95'].filter((v) => v !== null)).size;
check('往返之后重跑出的是同一条轨迹（标量逐格 1e-6）',
      nullGap === 0 && nCmp > 0 && worstRT < 1e-6,
      `${nCmp} 格，最大相对差 ${worstRT.toExponential(1)}` +
      (wKey ? `（${wKey}）` : '') + `，null 位置 ${nullGap ? '不一致' : '一致'}`);
check('这条轨迹不是一条常数（否则「重跑出同一条」什么也没说）',
      distinct >= 2 &&
      RT1['fylite:time'].length === RT2['fylite:time'].length &&
      RT1['fylite:time'].every(
        (t, i) => Math.abs(t - RT2['fylite:time'][i]) < 1e-9),
      `${distinct} 个不同的 q95，时刻逐个相同`);
//: ★★AND IT REFUSES WHAT IT CANNOT CARRY.  A file that round-trips by
//: silently dropping a slice's readings is worse than one that says no: the
//: slice would be re-fitted on the reconstruction bar's own measurements, i.e.
//: the reference instant under another instant's label.
const stripped = JSON.parse(readFileSync(rt1, 'utf8'));
delete stripped['fylite:slices'][2]['fylite:flux_loop_total'];
const sfp = join(OUT, 'stripped.json');
writeFileSync(sfp, JSON.stringify(stripped));
await importFile(sfp, '已导入|导入失败');
const stStrip = await text('analysis-status');
check('少了一片读数的文件被拒绝，并说出是哪一片——不是悄悄借用反演栏的测量',
      /导入失败/.test(stStrip) && /第 3 片/.test(stStrip),
      stStrip.slice(0, 76));
//: ★A SWEEP HAS NO READINGS AT ALL, and comes back as a sweep rather than as
//: measurements — the one provenance error worse than refusing the file.
await page.click('#analysis-series-tab-twin');
await set('analysis-series-nslice', 2);
await run('series', '时间序列完成|失败');
const TW = await save('series-series', 'tw.json');
const twf = join(OUT, 'tw.json');
const twSl = TW['fylite:slices'] || [];
check('孪生扫描导出的是它的驱动点（I_p、β₀）而不是假装成读数',
      TW['fylite:provenance'] === 'synthetic-twin-sweep' && twSl.length === 2 &&
      twSl.every((e) => isFinite(e['fylite:ip']) && e['fylite:prof'] &&
                        !e['fylite:flux_loop'] && !e['fylite:flux_loop_total']),
      `${TW['fylite:provenance']}，${twSl.length} 片，` +
      `例：I_p ${twSl[0]['fylite:ip']} A、β₀ ${twSl[0]['fylite:prof'].beta0}`);
await importFile(twf, '已导入|导入失败');
const busTw = await page.evaluate(() => {
  const s = FyScenario.pages.analysis.bus.series();
  return { n: s.slices.length, syn: s.synthetic, shot: s.shot };
});
check('孪生扫描导回来仍是孪生扫描：不带炮号，也不被当成一炮实测',
      busTw.n === 2 && busTw.syn === true && busTw.shot === null,
      `${busTw.n} 片，合成 ${busTw.syn}，炮号 ${busTw.shot}`);

// --- 21: coil currents as observations carrying sigma (T-A5) --------------
//
// ★★THE CLOSURE CRITERION, DRIVEN END TO END.  The solver treated the coil
// currents as EXACTLY KNOWN — they entered only as the vacuum field and as
// the share subtracted from every channel — and on EAST #137985 the raw
// Rogowski currents are 2-9 % off the delivered reconstruction's own fitted
// values, so the nine deck slices came back with li(3) of 9 to 1430 (or did
// not solve at all).  With the coil currents in the fitted vector under a
// sigma prior, at least seven of the nine must converge with li(3) in
// [0.5, 3].
//
// ★The BEFORE half is asserted first and is not decoration: a criterion of
// the form「seven of nine land in a window」 says nothing unless it is shown
// that they did not before.  Both halves run the same nine slices, the same
// raw Rogowski currents, the same basis orders — only the switch moves.
//
// ★And the two standing rejections are re-asserted ON THE NEW PATH.  A coil
// block that reached its li(3) by quietly loosening the Ip equality or by
// collapsing the boundary would satisfy the criterion above and be worthless;
// so every surviving slice is checked against the same two statements the
// page already makes, plus the third that only exists because the coils
// became unknowns (how far they were moved, in units of the sigma given).

console.log('\n=== 二十一、线圈电流当作带 σ 的观测量（T-A5）===');
await freshPage();

const LI_LO = 0.5, LI_HI = 3.0;
const inWin = (v) => v !== null && isFinite(v) && v >= LI_LO && v <= LI_HI;

/** Run the nine deck slices on their own raw Rogowski currents. */
async function deckSeries(fitCoils, name) {
  await page.click('#analysis-series-tab-deck');
  await page.evaluate(() => {
    const e = document.getElementById('analysis-series-coilsrc');
    e.value = 'slice'; e.dispatchEvent(new Event('change'));
  });
  await check_('reconstruction-coilfit', fitCoils);
  if (fitCoils) {
    await set('reconstruction-coilsig', 0.07);
    await set('reconstruction-loopsig', 0.03);
  }
  await run('series', '时间序列完成|失败');
  return save('series-series', name);
}

const C0 = await deckSeries(false, 'coil_off.json');
const C1 = await deckSeries(true, 'coil_on.json');
const li0 = C0['fylite:scalars']['fylite:li3'];
const li1 = C1['fylite:scalars']['fylite:li3'];
const a1 = C1['fylite:scalars']['fylite:a'];
const ipf1 = C1['fylite:scalars']['fylite:ipFitted'];
const pull1 = C1['fylite:scalars']['fylite:coilPull'];
const pull0 = C0['fylite:scalars']['fylite:coilPull'];
const t1 = C1['fylite:time'];
const nOff = li0.filter(inWin).length, nOn = li1.filter(inWin).length;

check(`卷宗九片都在表里，两趟问的是同一个问题（只有开关动了）`,
      li0.length === deckSlices.length && li1.length === deckSlices.length &&
      C0['fylite:provenance'] === 'reconstructed-from-slices' &&
      C1['fylite:provenance'] === 'reconstructed-from-slices',
      `${li0.length} 片 / ${li1.length} 片`);
//: the premise: without the coil block this criterion is nowhere near met
check(`关着开关时，落在 li(3) ∈ [${LI_LO}, ${LI_HI}] 的不到七片（否则本节什么也没测）`,
      nOff < 7,
      `${nOff}/9 片在窗内；li(3) = ${li0.map(
        (v) => (v === null ? 'null' : (+v).toPrecision(4))).join(', ')}`);
check(`★关闭判据：开关打开后九片里至少七片收敛且 li(3) ∈ [${LI_LO}, ${LI_HI}]`,
      nOn >= 7,
      `${nOn}/9 片；li(3) = ${li1.map(
        (v) => (v === null ? 'null' : (+v).toPrecision(4))).join(', ')}`);
check('这九片用的确实是时片自带的原始 Rogowski 电流（对卷宗文件逐道相同）',
      (C1['fylite:slices'] || []).length === deckSlices.length &&
      (C1['fylite:slices'] || []).every((e, i) =>
        (e['fylite:coil_current'] || []).every(
          (v, k) => v === DEV['fylite:slices'][i].aturns[k])),
      `${(C1['fylite:slices'] || []).length} 片 × ` +
      `${DEV['fylite:slices'][0].aturns.length} 道`);

//: ★the switch has to have DONE something.  A coil block that reported a
//: fit while leaving the currents where it found them is exactly the failure
//: the loop-sigma argument is about, and it would pass every check above if
//: the slices happened to converge for another reason.
const okIdx1 = li1.map((v, i) => (v === null ? -1 : i)).filter((i) => i >= 0);
const pulls = okIdx1.map((i) => pull1[i]).filter((v) => v !== null);
check('关着开关时不报线圈位移，开着时逐片都报',
      pull0.every((v) => v === null) &&
      pulls.length === okIdx1.length && pulls.every((v) => isFinite(v)),
      `关：${pull0.filter((v) => v !== null).length} 片有数；` +
      `开：${pulls.length}/${okIdx1.length} 片有数`);
check('线圈电流确实被挪动了（不是名义上开了开关）',
      pulls.length > 0 && Math.min(...pulls) > 0.1,
      `位移 ${Math.min(...pulls).toPrecision(3)} – ` +
      `${Math.max(...pulls).toPrecision(3)} σ`);
check('每一片的位移都在判据上限之内（5 σ），否则那一片本该被拒',
      pulls.length > 0 && Math.max(...pulls) <= 5.0,
      `最大 ${Math.max(...pulls).toPrecision(3)} σ`);

//: ★★the two standing rejections, re-asserted on the coil-fitted path
const worstIpC = Math.max(...okIdx1.map(
  (i) => rel(Math.abs(ipf1[i]), Math.abs(DEV['fylite:slices'][i].ip))));
check('已收敛的那些仍然满足 I_p 等式约束（判据 0.5，与页面同一条）',
      okIdx1.length > 0 && worstIpC < 0.5,
      `最大相对差 ${worstIpC.toExponential(2)}`);
const minA1 = Math.min(...okIdx1.map((i) => a1[i]));
check(`已收敛的那些仍然是等离子体不是一团（a > 0.1 × 真空室半宽 = ${
        (0.1 * aMachine).toFixed(3)} m）`,
      okIdx1.length > 0 && minA1 > 0.1 * aMachine,
      `最小 a = ${minA1.toFixed(3)} m`);
check('每一片的时刻对上卷宗文件（1e-9）',
      t1.length === deckSlices.length &&
      t1.every((v, i) => Math.abs(v - deckSlices[i]) < 1e-9),
      `${t1.length} 片`);

//: ★and the page says which of the two statements the coil source note is
//: making — the raw currents stopped being an equality input and became the
//: centre of a prior, and that is a different sentence
const srcNote = await text('analysis-series-coil-note');
check('线圈来源那条注记跟着开关改口（等式输入 → 先验中心）',
      /一起拟合|fitted too/.test(srcNote), srcNote.slice(0, 60));

// --- 22: a pick off the twin sweep re-solves as the twin (T-A17) ----------
//
// ★★THE SOURCE RIDES WITH THE SLICE.  `pickAt` hands a slice to the
// reconstruction bar; before this batch it did not hand over WHOSE slice it
// was, so a drive point picked off a SYNTHETIC sweep was re-fitted under
// the bar's own 实测 tab — the drive point's `ip` ignored (the real path
// reads `ipOverride`), the twin slice has no readings, and the fit quietly
// re-solved the REFERENCE instant under the picked label.  What is asserted
// here is the closure criterion verbatim: the fit uses THAT SLICE's drive
// point rather than the bar's basis current, and the status line says the
// slice is synthetic.  The drive currents are set well away from the deck's
// 393.46 kA so「用了谁的电流」is a fact with daylight around it.

console.log('\n=== 二十二、点选孪生扫描的一片，按合成源重解（T-A17）===');
await freshPage();
await page.click('#analysis-series-tab-twin');
await set('analysis-series-nslice', 3);
//: ★the sweep BRACKETS the twin's own workable point (450 kA, β₀ 0.60 — the
//: single-fit defaults every twin section upstream fits green at).  This is
//: not dodging: the twin member fit at low I_p genuinely diverges (section
//: 七 measured 320 kA → 法方程奇异), and a pick of a slice that cannot fit
//: is a test of the failure path, not of T-A17's re-routing.  What T-A17
//: has to show is that the pick lands on the TWIN path with the SLICE's
//: drive point — so the picked point must be one where the twin path can
//: answer at all, and it must differ from the bar's basis current
//: (450 ≠ 393.46 kA) or the constraint assertion proves nothing.
await set('analysis-series-ip0', 430);
await set('analysis-series-ip1', 470);
await set('analysis-series-b0', 0.60);
await set('analysis-series-b1', 0.60);
await run('series', '时间序列完成|失败');
const swStatus = await page.evaluate(
  () => document.getElementById('analysis-status').textContent);
const twinMid = await page.evaluate(() => {
  const s = FyScenario.pages.analysis.bus.series();
  return { t: s.slices[1].time, ip: s.slices[1].ip, syn: s.synthetic };
});
check('孪生扫描在册且中间片带自己的驱动点（450 kA）',
      twinMid.syn === true && Math.abs(twinMid.ip - 450e3) < 1,
      `t = ${lbl(twinMid.t)}，I_p ${(twinMid.ip / 1e3).toFixed(1)} kA`);
check('扫描的三片全部解出（非退化前提：点选点必须可解）',
      /，0 片未解出|, 0 unsolved/.test(swStatus), swStatus.slice(0, 60));
const P22 = await pickSlice(twinMid.t);
check('孪生扫描上的点选算成了',
      !!P22.hit && !/重构失败|失败/.test(P22.status || '失败'),
      (P22.status || '').slice(0, 70));
//: the closure criterion's second half: the STATUS LINE names the pick as
//: synthetic, in the same sentence as the numbers
check('状态行说得出这一片是合成的',
      /合成|synthetic/i.test(P22.status || ''), (P22.status || '').slice(0, 96));
const vd22 = await text('reconstruction-verdict');
check('可信度一行带那一刻，并说它是孪生扫描里点选的、合成的',
      vd22.indexOf('t = ' + lbl(twinMid.t)) === 0 && /合成|synthetic/.test(vd22),
      vd22.slice(0, 72));
//: the closure criterion's first half, read OFF THE ANSWER: the session
//: file's Ip constraint is what the worker actually imposed, and it must be
//: the picked drive point — not the bar's delivered/basis current
const RJ22 = await save('reconstruction-json', 'ta17.json');
const ipc22 = RJ22['fylite:config']['fylite:ip_constraint'];
check('拟合用的是那一片的驱动点电流，不是反演栏的 ipOverride',
      Math.abs(ipc22 - 450e3) < 1,
      `约束 ${(ipc22 / 1e3).toFixed(2)} kA（反演栏基准 393.46 kA）`);
check('会话文件记下：约束来自 slice，且这一片是合成的',
      RJ22['fylite:config']['fylite:ip_source'] === 'slice' &&
      RJ22['fylite:config']['fylite:slice_synthetic'] === true,
      `ip_source ${RJ22['fylite:config']['fylite:ip_source']} · ` +
      `slice_synthetic ${RJ22['fylite:config']['fylite:slice_synthetic']}`);
//: ★and the OTHER direction must not regress: a pick off the DECK series is
//: still a measurement — no 合成 wording, and the slice's own delivered-basis
//: current stands.  Asserted on the same freshly loaded page, so the two
//: directions cannot pass by the page being stuck in either mode.
await page.click('#analysis-series-tab-deck');
await run('series', '时间序列完成|失败');
const P22b = await pickSlice(deckSlices[3]);
check('换回卷宗时序，点选仍按实测走（状态行没有「合成」）',
      !!P22b.hit && !/合成|synthetic/i.test(P22b.status || '合成'),
      (P22b.status || '').slice(0, 80));

check('页面无脚本错误', errs.length === 0, errs.slice(0, 2).join(' | '));

await br.close();
console.log(`\n判定：反演场景的分析层${bad ? `不通过（${bad} 项）` : '通过'}`);
process.exit(bad ? 1 : 0);
