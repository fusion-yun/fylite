// 现读切片按裁定拒绝（用户裁定 2026-09-15：efit_east 树只作对拍比较数据）
//
// ★★WHAT THIS GATES NOW.  This file used to gate the live-slice strip (T-A21): read a stored slice of a shot
// through /api/measurements, draw the shot's slice table, click a mark to read that slice, and mark the tried
// slices converged / failed.  What it read was the efit_east MEASUREMENTS record — EFIT's own input channels —
// taken as the reconstruction's input.  By user ruling (2026-09-15) that tree is comparison data only, so the
// page refuses the slice by name WHICHEVER host answered: this gate hands the page a well-formed canned answer
// and asserts the refusal, that no slice table is drawn, and that the page stays free of errors.  The retired
// gate is in git history.
//
//   node app/tests/validate-recon-slices.mjs [--playwright DIR] [--chrome BIN] [--url BASE]

import { browser, flag } from './_browser.mjs';
import { seedDeviceDocs } from './_device.mjs';
import { eastWithShot, skipMessage } from './_kernel-fixture.mjs';

const BASE = flag('url') || 'http://127.0.0.1:8767/app/';

//: the A-Box-built EAST document with the #137985 reference discharge from the PRIVATE kernel fixture — skipped
//: by name without it (the canned answer below is built from its channels, so it is well-formed)
const EAST = eastWithShot();
if (EAST.why) { console.log(skipMessage('validate-recon-slices', EAST.why)); process.exit(0); }
const DECK = EAST.doc;
const REF = DECK['fylite:reference_discharge'] || {};

const canned = (shot, want) => ({
  server: 'canned', tree: 'efit_east', shot, time_requested: want, time_s: want, slice_index: 0,
  slices: 1, times: [want],
  loops: (REF.loopMeasTotal || []).slice(), probes: (REF.probeMeas || []).slice(0, 76),
  aturns: (REF.aturns || []).slice(0, 12), ip: REF.ipMeasured || 0, bcentr: REF.bcentr ?? null,
  counts: {}, probe_gate: { min_tesla: 0.02, max_tesla: 1.0 },
  provenance: { nodes: {}, kind: 'canned from the shipped reference discharge' },
});

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', viewport: { width: 1440, height: 1100 } });
await seedDeviceDocs(ctx, { east: DECK });
const asked = [];
await ctx.route('**/api/health', (route) =>
  route.fulfill({ status: 200, contentType: 'application/json',
                  body: JSON.stringify({ mdsip: 'canned:0', ok: true }) }));
await ctx.route('**/api/measurements*', (route) => {
  const u = new URL(route.request().url());
  asked.push(u.search);
  route.fulfill({ status: 200, contentType: 'application/json',
                  body: JSON.stringify(canned(Number(u.searchParams.get('shot')), Number(u.searchParams.get('time')))) });
});

const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
await page.goto(BASE + 'pages/analysis.html?device=east', { waitUntil: 'networkidle' });
await page.waitForFunction(() => !!self.FYLITE_KERNEL, null, { timeout: 180000 });

//: the page's own face, called directly: it must refuse whatever it is handed
const direct = await page.evaluate(() => {
  try { self.FyRecon.useMeasurements({}); return 'accepted'; } catch (e) { return String((e && e.message) || e); }
});
//: and through the source panel, with the canned host answering 200
await page.fill('#reconstruction-mds-shot', '137985');
await page.fill('#reconstruction-mds-time', '4.041');
await page.click('#reconstruction-mds-read');
await page.waitForFunction(
  () => /用不了|cannot be used|读不到|Could not read/.test(
    (document.getElementById('reconstruction-mds-note') || {}).textContent || ''),
  null, { timeout: 60000 }).catch(() => {});
const after = await page.evaluate(() => {
  const strip = document.getElementById('reconstruction-mds-slices');
  return { note: (document.getElementById('reconstruction-mds-note') || {}).textContent || '',
           stripHidden: strip ? !!strip.hidden : true };
});
await br.close();

let bad = 0, n = 0;
const ok = (cond, what, detail) => {
  n += 1;
  if (!cond) bad += 1;
  console.log(`  ${cond ? '✓' : '✗'} ${what}${detail ? ' — ' + detail : ''}`);
};
const RULING = /comparison data only|只作对拍比较数据/;

console.log('\n〔一〕页面按裁定拒绝现读切片，不论宿主答了什么');
ok(RULING.test(direct), 'FyRecon.useMeasurements 按名拒绝', direct.slice(0, 80));
ok(asked.length >= 1, '读取确实发出了请求（被拒的是答复，不是按钮）', `${asked.length} 次`);
ok(RULING.test(after.note), '来源栏的注记写明裁定', after.note.replace(/\s+/g, ' ').slice(0, 80));
ok(after.stripHidden, '没有画出存储片表（没有可试的切片）');

console.log('\n〔二〕页面没有报错');
ok(!errs.length, '控制台干净', errs.slice(0, 2).join(' | '));

console.log(`\n判定：${bad ? bad + ' / ' + n + ' 条不符' : n + ' 条全过'}`);
process.exit(bad ? 1 : 0);
