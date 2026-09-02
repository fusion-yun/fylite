// Gate for the design scenario's CRITERIA and for the state its anneal
// begins from.
//
//   node app/tests/validate-design.mjs [--url http://127.0.0.1:8767/app/]
//                                      [--playwright DIR] [--chrome BIN]
//
// ★★What this is for.  A bundled machine may carry no reference discharge
// (of the two shipped today, ITER does not), and the anneal is a local
// method: it linearises the boundary's response about the equilibrium it is
// standing on.  Started from zero currents it converged 0.36 – 0.77 m from
// its target while the status line read "inverse solve finished" — the
// failure mode this gate exists to keep out is not a wrong number, it is a
// wrong number reported as a right one.
//
// So what is asserted here is mostly REPORTING: that a design which did not
// reach its target says so, that the criteria a configuration is judged by
// are present and finite, and that the vertical-position feedback is
// declared rather than absorbed.  The physics behind each criterion is
// pinned in the kernel's own tests and in `validate-limits.mjs`; what only a
// browser can check is that the page asks for them and shows what comes back.
import { createRequire } from 'node:module';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { catalogue } from './_preset.mjs';

const iu = process.argv.indexOf('--url');
const BASE = iu > 0 ? process.argv[iu + 1] : 'http://127.0.0.1:8767/app/';
const ip = process.argv.indexOf('--playwright');
const PW = ip > 0 ? process.argv[ip + 1] : process.env.PLAYWRIGHT_PATH;
let chromium;
try {
  const req = createRequire(PW ? PW.replace(/\/*$/, '/') + 'x.js'
                               : import.meta.url);
  ({ chromium } = req('playwright'));
} catch (e) {
  console.error('找不到 playwright —— 用 --playwright <装有 playwright 的目录> ' +
                '或设 $PLAYWRIGHT_PATH');
  process.exit(2);
}

let fails = 0;
function ok(name, cond, detail) {
  console.log(`${cond ? 'ok   ' : 'FAIL '} ${name}${detail ? '  ' + detail : ''}`);
  if (!cond) fails++;
}

//: ★and the BROWSER the same way: playwright pins a chromium build per
//: release, and an operator whose install has a different one would
//: otherwise be told to download a second copy of a browser they have.
const ic = process.argv.indexOf('--chrome');
const CHROME = ic > 0 ? process.argv[ic + 1] : process.env.CHROME_PATH;
const br = await chromium.launch(CHROME ? { executablePath: CHROME } : {});
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
//: ★factory defaults — which is now simply what a fresh context gives:
//: no bar applies an initial case any more (2026-09-01).
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
//: ★a console 404 does not say WHICH resource, so the URL is taken from
//: the response instead: the pages ship no favicon and every browser asks
//: for one, which would otherwise make this gate red on every run for a
//: file the site does not claim to have.
page.on('response', (r) => {
  if (r.status() === 404 && !/favicon/.test(r.url()))
    errs.push('404: ' + r.url().slice(-60));
});
page.on('console', (m) => {
  if (m.type() === 'error' && !/status of 404/.test(m.text()))
    errs.push('console: ' + m.text().slice(0, 200));
});

await page.goto(BASE + 'pages/pulse_design.html#configure', { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);

/** Wait for a bar to stop running, then return the page's status line. */
async function runBar(bar, budget = 300) {
  //: ★合并之后一条栏可能在没显示的那个模式里，而看不见的按钮点不动。切到它
  //: 所在的模式再点——「这条栏在哪个模式里」由页面自己回答（`FyModes.forBar`），
  //: 闸子不另存一张会过期的表。
  await page.evaluate((b) => self.FyModes && self.FyModes.set(self.FyModes.forBar(b)), bar);
  await page.click(`#pulse_design-${bar}-run`);
  for (let i = 0; i < budget; i++) {
    await page.waitForTimeout(500);
    const busy = await page.evaluate(
      () => !!document.querySelector('.funcbar-run.stop'));
    if (!busy && i > 2) break;
  }
  return await page.evaluate(
    () => document.getElementById('pulse_design-status')?.innerText || '');
}
const rows = async (id) => await page.evaluate((sel) => {
  const b = document.getElementById(sel);
  return b ? Array.from(b.rows, (r) => Array.from(r.cells, (c) => c.innerText))
           : [];
}, id);

//: ★T-D12: the bar's TERMINAL MARKER, read as a state rather than as prose.
//: Every assertion below that asks "did this bar finish, and did it get what
//: it was asked for" reads this — the wording of the sentence beside it is
//: free to change, the vocabulary of `data-state` is not.
const STATES = ['done', 'miss', 'fail', 'busy', 'idle'];
const barState = async (bar) => await page.evaluate((b) => {
  const e = document.querySelector(`[data-bar="${b}"] .funcbar-state`);
  return e ? { state: e.dataset.state || '',
               mark: (e.querySelector('.state-mark') || {}).textContent || '',
               text: e.textContent || '' } : null;
}, bar);

// --- T-D12: the terminal marker ---------------------------------------------
// Before anything is asked of the page, all three bars are 未运行 — and they
// SAY it, in the same slot and the same vocabulary they will use to say
// 已完成.  An empty strip is not a state, and it is what the probe that
// measured this page mistook for a run still in flight.
//: the kernel handshake first — 2.5 s is enough on an idle machine and is
//: not on a loaded one, and「未运行」would then be read off a page that has
//: not finished booting rather than off one that has and was asked nothing
//: ★合并之后一页有六条栏而只有一条页面状态行——它说的是「最后开口的那条栏」，
//: 开页时那是自己跑完的击穿栏。「内核握手到了没有」因此问栏，不问那一行。
await page.waitForFunction(
  () => [...document.querySelectorAll('[data-bar] .funcbar-state')]
    .some((e) => /就绪|Ready|失败|failed/.test(e.textContent)), null,
  { timeout: 180000 });
const idle = await Promise.all(
  ['zerod', 'discharge', 'pulse', 'breakdown'].map(barState));
ok('every bar carries a terminal marker before anything is run',
   idle.every((s) => s && s.state === 'idle' && s.mark.length > 0),
   idle.map((s) => s && `${s.state}:${s.text.slice(0, 90)}`).join(' | '));

// --- T-D11: unrun panels are folded, long explanations are foldable ---------
// Measured at 1440 x 900 on EAST before this: the three bars open came to
// 6490 px and the shape bar alone to 1980 of them — with some 900 px of
// tables reading 「—」 in every cell and plots with nothing but axes, because
// it had not been run.  A panel that has never held a result is a
// placeholder the size of half a screen.
const panels = async () => await page.evaluate(() => {
  const all = Array.from(document.querySelectorAll('.panel[data-result]'));
  return { total: all.length,
           folded: all.filter((p) => p.classList.contains('folded')).length,
           badges: Array.from(document.querySelectorAll('.funcbar-results'))
             .filter((e) => !e.hidden).map((e) => e.textContent) };
});
const p0 = await panels();
ok('every result panel starts folded on a page where nothing has run',
   p0.total > 0 && p0.folded === p0.total, `${p0.folded}/${p0.total} folded`);
//: ★六条栏（配置四条 + 设计 + 仿真）自合并起同在一页，**六条都报数**。这个
//: 数字写在这里是为了**它变了就有人看见**：少一条意味着有一条栏的结果块没有
//: 报数，而不是「页面变了」。
//: ★★它曾经写着 **5**，附一句「仿真那一条没有折起来的结果块」——那句话是错的。
//: 真正的成因是**击穿场零栏被初始算例自动跑过了**：这道闸子自称测的是出厂值，
//: 而 `returningVisitor` 播的键是 `fylite:seen:design:*`，页面改名成 `pulse_design`
//: 之后播空了，于是初始算例照样施用、那一栏的结果已出、徽标随之隐藏。算例菜单
//: 2026-09-01 撤除后页面真的停在出厂值上，六条栏都在「按住结果」，数就是 6
//: （同批 `18/20 folded` 也回到 `20/20`）。★钉住的数正是这样起作用的。
ok('and each bar says how many results it is holding back',
   p0.badges.length === 6 && p0.badges.every((t) => /\d/.test(t)),
   p0.badges.join(' | '));
// ★long explanations: clamped, with a key, and the text still in the document
// — a fold that removed the sentence would be a fold that removed the reason.
const notes = await page.evaluate(() => {
  const c = Array.from(document.querySelectorAll('.note.clamped'));
  return { n: c.length, keys: c.map((x) => x.getAttribute('data-i18n')),
           buttons: document.querySelectorAll('button.note-more').length,
           text: c.length ? (c[0].textContent || '').length : 0 };
});
ok('long explanations are folded but still in the document',
   notes.n > 0 && notes.buttons === notes.n && notes.text > 100,
   `${notes.n} clamped, first is ${notes.text} chars: ${notes.keys.join(', ')}`);
await page.evaluate(() => document.querySelector('button.note-more').click());
const clampedAfter = await page.evaluate(
  () => document.querySelectorAll('.note.clamped').length);
ok('and a key opens one', clampedAfter === notes.n - 1,
   `${notes.n} clamped → ${clampedAfter}`);

// --- the page BOOTS, on every machine it offers -----------------------------
// ★Found by the marker above, which is the whole point of having one: on
// some loads the strip read 「失败」 before anything had been asked of the
// page.  A descriptor carrying no magnetics asks for the response of an
// empty flux-loop set, which allocates zero doubles, and the wasm allocator
// reports that as a failure — so `init` died and the page had no kernel at
// all.  It showed up only sometimes because the default machine was
// whichever preset's fetch finished first.
//
// ★★THE LIST COMES FROM THE CATALOGUE, not from two ids written here.  It
// used to name `best` and `cfetr` — the two magnetics-free descriptors —
// and both were withdrawn from this repository on 2026-09-01 (their PF coil
// tables come from private communication).  `?device=` falls back to the
// first machine when it does not know the id, silently, so the loop went on
// booting EAST twice and printing 「a machine with no magnetics still brings
// up the kernel (best)」 — a gate reporting a pass for a check it was no
// longer performing.  Hence the second assertion: the page must LAND on the
// machine that was asked for.
//
// ★The zero-allocation path itself is therefore no longer exercised here:
// nothing this repository ships has an empty flux-loop set.  It is still
// guarded where the allocation happens (`assets/worker.js`, the note on
// `gridChannelResponse`); restoring a magnetics-free descriptor to
// `devices/` brings this loop's coverage back with it, no edit needed.
const dev0 = await page.evaluate(
  () => document.querySelector('select').value);
ok('the default machine is the first the catalogue declares, every load',
   dev0 === 'east', `default = ${dev0}`);
const OFFERED = ((catalogue() || {})['fylite:devices'] || [])
  .map((e) => e['fylite:device_id']).filter(Boolean);
ok('the catalogue declares at least one machine', OFFERED.length > 0,
   OFFERED.join(', '));
for (const id of OFFERED) {
  await page.goto(BASE + `pages/pulse_design.html?device=${id}#configure`,
                  { waitUntil: 'networkidle' });
  await page.waitForFunction(
    () => [...document.querySelectorAll('[data-bar] .funcbar-state')]
      .some((e) => /就绪|Ready|失败|failed/.test(e.textContent)), null,
    { timeout: 180000 });
  const got = await page.evaluate(
    () => document.querySelector('select').value);
  ok(`?device=${id} lands on that machine`, got === id, `selected = ${got}`);
  const st0 = await barState('zerod');
  ok(`the kernel comes up on the machine the catalogue offers (${id})`,
     st0.state !== 'fail', `${st0.state} · ${st0.text.slice(0, 60)}`);
}

// --- a machine WITHOUT a reference discharge --------------------------------
// The case the page used to get silently wrong.  ITER's descriptor carries
// no reference shot, so the anneal has to design its own start.
await page.locator('select').first().selectOption({ label: 'ITER' });
await page.waitForTimeout(3500);
const st = await runBar('discharge');
ok('a machine with no reference discharge still designs a start',
   /设计|design|反解|inverse|退火|anneal|达到|reach/i.test(st),
   st.slice(0, 60).replace(/\n/g, ' '));

const pAfter = await page.evaluate(() => {
  const sec = document.querySelector('[data-bar="discharge"]');
  const all = Array.from(sec.querySelectorAll('.panel[data-result]'));
  const badge = sec.querySelector('.funcbar-results');
  return { total: all.length,
           folded: all.filter((p) => p.classList.contains('folded')).length,
           badge: badge && !badge.hidden ? badge.textContent : '' };
});
ok('a bar that has produced a result opens the panels that hold it',
   pAfter.total > 0 && pAfter.folded === 0 && pAfter.badge === '',
   `${pAfter.folded}/${pAfter.total} still folded · badge "${pAfter.badge}"`);

const shape = await rows('pulse_design-discharge-shape');
ok('the deviation table compares Z0 as well as R0',
   shape.some((r) => /Z/.test(r[0])), `${shape.length} rows`);
const crit = Object.fromEntries((await rows('pulse_design-discharge-criteria'))
  .map((r) => [r[0], r[1]]));
const val = (k) => {
  const key = Object.keys(crit).find((n) => n.includes(k));
  return key === undefined ? NaN : parseFloat(crit[key]);
};
ok('q95 is reported and finite', isFinite(val('q95')), `q95 = ${val('q95')}`);
ok('the internal inductance is reported', isFinite(val('l')),
   `li(3) = ${val('l')}`);
ok('the virtual vertical feedback is declared as a RATIO to Ip',
   isFinite(val('I')), `|I_fb|/Ip = ${val('I')}`);
ok('the wall clearance is reported', isFinite(val('隙')) || isFinite(val('clear')),
   `gap = ${val('隙')}`);

// ★the equilibrium has to be a PLASMA, not a collapsed column: the failure
// that hid behind "finished" was a 0.04 m blob at the outboard wall
const got = shape.map((r) => parseFloat(r[2]));
const aRow = shape.findIndex((r) => /^a\b/.test(r[0]));
ok('the solved boundary is a plasma, not a collapsed column',
   aRow >= 0 && got[aRow] > 0.5 * parseFloat(shape[aRow][1]),
   `a = ${got[aRow]} against a target of ${shape[aRow] && shape[aRow][1]}`);

// ★and when it does NOT reach the target, it has to say so
const far = shape.some((r, i) => {
  const tol = /κ|delta|δ/.test(r[0]) ? 0.03 : 0.03 * parseFloat(shape[aRow][1]);
  return Math.abs(parseFloat(r[3])) > tol;
});
//: the two ways this page says "not reached" are the anneal that landed
//: short and the anneal no pass improved; what must never appear over a
//: table of deviations larger than the tolerance is the plain success line
ok('a design that missed its target says so rather than reporting success',
   !far || /不优于起点|没有达到|did not reach|improved on the starting/.test(st),
   st.slice(0, 40).replace(/\n/g, ' '));
//: ★and it says so as a STATE.  This is the same judgement as the line above
//: made without reading a word of the message: `far` is computed from the
//: deviation table, `data-state` from the anneal's own error against its own
//: tolerance, and the two must not disagree.
const dst = await barState('discharge');
ok('the marker agrees with the deviation table about whether the target was met',
   STATES.includes(dst.state) && dst.state !== 'idle' && dst.state !== 'busy'
     && (far ? dst.state !== 'done' : dst.state === 'done'),
   `state=${dst.state} far=${far}`);

// --- the operating domain, on the 0-D bar ----------------------------------
const lim = await rows('pulse_design-zerod-limits');
ok('the 0-D bar reports the operating domain before it is run',
   lim.length === 0, `${lim.length} rows`);
await runBar('zerod');
const zst = await barState('zerod');
ok('a 0-D evaluation that finished reports 已完成 as its marker',
   zst.state === 'done', `state=${zst.state} · ${zst.text.slice(0, 40)}`);
const lim2 = Object.fromEntries((await rows('pulse_design-zerod-limits'))
  .map((r) => [r[0], r[1]]));
const keys = Object.keys(lim2);
ok('the Greenwald fraction is reported', keys.some((k) => /Greenwald|格林/.test(k)),
   keys.length + ' criteria');
ok('normalised beta is reported', keys.some((k) => /β\s*N|beta/i.test(k)));
const flux = await rows('pulse_design-zerod-flux');
ok('the flux account is reported', flux.length >= 6, `${flux.length} rows`);
ok('an undeclared swing is not shown as a duration',
   flux.some((r) => /未声明|not declared|no swing/.test(r[1])),
   flux.map((r) => r[1]).join(' | ').slice(0, 60));

// --- T-D3: the geometry is ONE set of controls ------------------------------
// EAST from here on: it is the machine whose description carries the vessel,
// which the trajectory below needs, and the machine every number in the TODO
// was measured on.
await page.locator('select').first().selectOption({ label: 'EAST' });
await page.waitForTimeout(3500);

// ★First structurally: a shared quantity is a shared CONTROL.  R0/a/kappa
// lived twice on this page — once per bar, seeded from the same descriptor
// and free to drift after (measured at load: a = 0.45 on the 0-D bar against
// 0.445 on the design bar).  Counting the live controls is the only check
// that cannot be satisfied by keeping two of them in step by hand.
const dupes = await page.evaluate(() => {
  const out = {};
  for (const n of ['r0', 'a', 'kappa', 'du', 'dl', 'ip']) {
    out[n] = Array.from(
      document.querySelectorAll('#tool-pulse_design input, #tool-pulse_design select'))
      .filter((e) => e.id === 'pulse_design-' + n || e.id.endsWith('-' + n))
      .map((e) => e.id);
  }
  return out;
});
ok('every shared geometry quantity is exactly one control on the page',
   Object.values(dupes).every((v) => v.length === 1),
   Object.entries(dupes).map(([k, v]) => `${k}:${v.join('+')}`).join(' '));

// ★And then behaviourally: moving the page's kappa has to move BOTH bars'
// answers.  Nothing else proves they read it — two controls kept equal by a
// listener would pass the count above and fail here.
const shapeGot = async () => (await rows('pulse_design-discharge-shape'))
  .map((r) => parseFloat(r[2]));
const domain = async () => Object.fromEntries(
  (await rows('pulse_design-zerod-limits')).map((r) => [r[0], parseFloat(r[1])]));
const setShared = async (id, v) => {
  await page.evaluate(([i, x]) => {
    const e = document.getElementById(i);
    e.value = x;
    e.dispatchEvent(new Event('input'));
    e.dispatchEvent(new Event('change'));
  }, [id, v]);
  //: the 0-D bar recomputes on `change`; let it finish before pressing
  //: anything, or the next bar's key is disabled when the click lands
  for (let i = 0; i < 60; i++) {
    await page.waitForTimeout(250);
    if (!await page.evaluate(
      () => !!document.querySelector('.funcbar-run.stop'))) break;
  }
};
//: three passes rather than eight: what is being asserted is that the solve
//: MOVED, not where it landed, and eight passes buy nothing for that
await page.evaluate(() => {
  const e = document.getElementById('pulse_design-discharge-passes');
  e.value = '3'; e.dispatchEvent(new Event('input'));
});
await setShared('pulse_design-kappa', '1.45');
await runBar('zerod');
const dom1 = await domain();
await runBar('discharge');
const got1 = await shapeGot();
await setShared('pulse_design-kappa', '1.85');
await runBar('zerod');
const dom2 = await domain();
await runBar('discharge');
const got2 = await shapeGot();
const domKeys = Object.keys(dom1).filter((k) => isFinite(dom1[k]));
const domMoved = domKeys.filter((k) => Math.abs(dom1[k] - dom2[k]) > 1e-9);
ok('the 0-D bar reads the page-level kappa',
   domMoved.length >= 3,
   `${domMoved.length}/${domKeys.length} criteria moved: ` +
   domMoved.slice(0, 3).map((k) => `${k} ${dom1[k]}→${dom2[k]}`).join(' · '));
const shapeMoved = got1.filter((v, i) => isFinite(v) && isFinite(got2[i])
                                         && Math.abs(v - got2[i]) > 1e-4);
ok('the design bar reads the same page-level kappa',
   shapeMoved.length >= 2,
   `solved ${got1.map((v) => v.toFixed(3)).join(',')} → ` +
   `${got2.map((v) => v.toFixed(3)).join(',')}`);

// --- T-D1: the criteria are pinned to a geometry, and say which -------------
// Same page, two panels, and until now they disagreed in silence: the volume
// panel reported the sliders 44 % away from the shape this shot's equilibrium
// found, while the operating-domain block — every row of which is linear in
// that volume or in a² — said nothing at all about which of the two it stood
// on.  The slice equilibrium does NOT depend on the sliders (it is solved
// from the reference coil currents scaled by Ip), so moving the sliders onto
// the solved shape is a clean way to drive the disagreement to zero.
const geomCol = async () => (await rows('pulse_design-zerod-limits')).map((r) => r[3]);
const banner = async () => await page.evaluate(() => {
  const e = document.getElementById('pulse_design-zerod-limits-geo');
  return { shown: !e.hidden,
           text: e.hidden ? '(hidden)' : (e.innerText || '').slice(0, 120) };
});
//: the slice equilibrium arrives AFTER the 0-D answer the run key waits for
const sliceSolved = async () => {
  for (let i = 0; i < 80; i++) {
    await page.waitForTimeout(400);
    const r = await rows('pulse_design-zerod-volumes');
    if (r.some((x) => /R₀/.test(x[1]))) return r;
  }
  return await rows('pulse_design-zerod-volumes');
};

await setShared('pulse_design-kappa', '1.65');
await runBar('zerod');
const vol1 = await sliceSolved();
// ★T-D2(a): the bar must not contradict itself.  The status line read
// 「5.05 s 的平衡已解（1141 ms）」 while the criteria table beside it read
// 「q95 — 未解」, because the slice solve redrew the volume panel and not the
// criteria block.
const q95Row = (await rows('pulse_design-zerod-limits'))
  .find((r) => /q\s*95/i.test(r[0])) || [];
const zsaid = await barState('zerod');
ok('the criteria table and the status line agree that the slice is solved',
   /平衡已解|solved/.test(zsaid.text) && isFinite(parseFloat(q95Row[1]))
     && !/未解|not solved/.test(q95Row[2] || ''),
   `${zsaid.text.slice(0, 26)} ‖ q95 ${q95Row[1]} · ${q95Row[2]}`);
const geo1 = await geomCol();
const ban1 = await banner();
ok('every criterion names the geometry it was computed on',
   geo1.length >= 10 && geo1.every((g) => g && g.trim().length > 0),
   geo1.slice(0, 3).join(' | '));
ok('the block warns when the sliders are not the shape this shot makes',
   ban1.shown && /42|4[0-9]|-3[0-9]/.test(ban1.text),
   ban1.text.slice(0, 70));

//: move the sliders onto the boundary the equilibrium actually found
const solved = (vol1.find((r) => /R₀/.test(r[1])) || ['', ''])[1];
const num = (k) => parseFloat((solved.match(
  new RegExp(k + '\\s*([-\\d.]+)')) || [])[1]);
const [sr0, sa, sk] = [num('R₀'), num('a'), num('κ')];
ok('the volume panel reports the solved shape as three numbers',
   [sr0, sa, sk].every(isFinite), `R0=${sr0} a=${sa} κ=${sk}`);
await setShared('pulse_design-r0', String(sr0));
await setShared('pulse_design-a', String(sa));
await setShared('pulse_design-kappa', String(sk));
await runBar('zerod');
await sliceSolved();
const geo2 = await geomCol();
const ban2 = await banner();
const changed = geo1.filter((g, i) => g !== geo2[i]);
ok('changing the shape difference changes the annotation on the criteria rows',
   changed.length >= 8, `${changed.length} rows re-labelled: ` +
   `${geo1[1]} → ${geo2[1]}`);
ok('and the block stops warning once the two shapes agree',
   !ban2.shown, ban2.text.slice(0, 60));

// --- T-D9: the L-H margin is in the ANALYSIS tier ---------------------------
// 「这炮进不进得了 H 模」 is asked before a shot is scheduled, and the default
// tab carried Greenwald, q_cyl and Troyon and no P_LH at all — the Martin
// scaling was in the kernel but reachable only from the prediction tab.  The
// scaling itself is pinned in `validate-limits.mjs` against the published
// coefficients; what only a browser can check is that the default tab asks
// for it, marks it as an empirical scaling (FR-PULSE-003), and that the
// ratio beside it is a ratio.
const tierA = await page.evaluate(
  () => document.getElementById('pulse_design-zerod-tab-a').className);
ok('the tier under test is the analysis tier, which is the default',
   /on/.test(tierA), `tab-a class = "${tierA}"`);
const lh1 = Object.fromEntries((await rows('pulse_design-zerod-limits'))
  .map((r) => [r[0], r]));
const lhKey = Object.keys(lh1).find((k) => /P\s*LH|P<sub>LH/i.test(k)
                                            && !/\//.test(k));
const rtKey = Object.keys(lh1).find((k) => /\/\s*P\s*LH/i.test(k));
ok('the analysis tier reports the L-H threshold power',
   lhKey !== undefined && isFinite(parseFloat(lh1[lhKey][1])),
   `${lhKey} = ${lhKey && lh1[lhKey][1]}`);
ok('and the margin P_heat / P_LH beside it',
   rtKey !== undefined && isFinite(parseFloat(lh1[rtKey][1])),
   `${rtKey} = ${rtKey && lh1[rtKey][1]}`);
//: FR-PULSE-003: every criterion says what public thing it is read against
//: and of what NATURE — an empirical scaling is not a limit this layer can
//: compute, and the row may not read as one
ok('and says it is an empirical scaling, not a limit this layer computes',
   lhKey !== undefined && /Martin|经验|empirical/.test(lh1[lhKey][2]),
   lhKey && lh1[lhKey][2]);
// ★the threshold does not depend on the heating power and the ratio does:
// ten times the auxiliary power must move one of them and not the other.
const lhV1 = parseFloat(lh1[lhKey][1]), rt1 = parseFloat(lh1[rtKey][1]);
await setShared('pulse_design-paux', '20');
await runBar('zerod');
const lh2 = Object.fromEntries((await rows('pulse_design-zerod-limits'))
  .map((r) => [r[0], r]));
const lhV2 = parseFloat(lh2[lhKey][1]), rt2 = parseFloat(lh2[rtKey][1]);
ok('the threshold does not move with the heating power',
   Math.abs(lhV2 - lhV1) < 1e-9, `P_LH ${lhV1} → ${lhV2} MW`);
ok('and the margin does',
   rt2 > 3 * rt1, `P_heat/P_LH ${rt1} → ${rt2} with P_aux 2 → 20 MW`);
await setShared('pulse_design-paux', '2');
await runBar('zerod');
await sliceSolved();

// --- T-D2(b): the several q95 on this page ----------------------------------
// q_cyl, this bar's slice equilibrium and the design bar's solved boundary
// are three different numbers under one name — measured on EAST at 4.48,
// 2.38 and 4.21, the last two nearly a factor of two apart because one is a
// small limiter plasma at the slice current and the other the flat-top
// design.  Nothing on the page said so.
const q95Note = async () => await page.evaluate(() => {
  const e = document.getElementById('pulse_design-zerod-q95-note');
  return e.hidden ? '' : e.innerText;
});
const note1 = await q95Note();
ok('the page names its several q95 and how far apart they are',
   /q95/i.test(note1) && /%/.test(note1),
   note1.split('\n')[0].slice(0, 60));
//: ★each of them with the geometry AND the boundary class it stands on: two
//: q95 a factor of two apart usually differ because one boundary touches a
//: limiter and the other has an X point, and the number alone cannot say so
ok('and reports each one against its own geometry and boundary class',
   /R₀/.test(note1) && /限制器|偏滤器|limiter|diverted/.test(note1)
     && note1.split('\n').length >= 4,
   note1.split('\n').slice(1).join(' ‖ ').slice(0, 130));

// --- T-D10: the two l_i, side by side ---------------------------------------
// The flux account charges the inductive flux against a STATED assumption,
// l_i = 0.9, because a 0-D layer has no current-diffusion solve.  The design
// bar on the same page solves an equilibrium reporting l_i(3) = 1.491 — 66 %
// away — and the two were a bar and 2400 px apart.
const fluxRows = async () => await page.evaluate(() => Array.from(
  document.getElementById('pulse_design-zerod-flux').rows,
  (r) => Array.from(r.cells, (c) => c.innerText)));
//: the second account is computed in the worker and arrives after the draw
for (let i = 0; i < 40; i++) {
  const f = await fluxRows();
  if (f.some((r) => /↳/.test(r[0]) && isFinite(parseFloat(r[1])))) break;
  await page.waitForTimeout(300);
}
const fx = await fluxRows();
const cell = (re) => { const r = fx.find((x) => re.test(x[0])); return r ? r[1] : ''; };
const assumed = parseFloat(cell(/假设|assumed/));
const solvedLi = parseFloat(cell(/解出的 l|solved by the shape/));
ok('the flux account states the l_i it assumes',
   Math.abs(assumed - 0.9) < 1e-9, `l_i = ${assumed}`);
ok('and shows the l_i(3) the design bar solved beside it',
   isFinite(solvedLi) && Math.abs(solvedLi - assumed) > 0.1,
   `assumed ${assumed} vs solved ${solvedLi}`);
const indBase = parseFloat(cell(/^电感磁通|^L<sub>p|^Lp/));
const indAlt = parseFloat(cell(/↳.*L/));
ok('and a row recomputed at the solved value',
   isFinite(indAlt) && Math.abs(indAlt - indBase) > 1e-6,
   `Φ_ind ${indBase} → ${indAlt} Wb`);
// ★THE RULE THIS ITEM IS ABOUT: the assumption is not quietly replaced.  The
// account's own inductive flux must still be the one at 0.9 — checked against
// the published external inductance μ0 R0 (ln(8R0/a) + l_i/2 − 2), whose
// dependence on l_i is exactly μ0 R0 Δl_i / 2, written out here.
const geo = await page.evaluate(() => ({
  r0: +document.getElementById('pulse_design-r0').value,
  ip: +document.getElementById('pulse_design-ip').value * 1e3 }));
const dPhi = 4e-7 * Math.PI * geo.r0 * (solvedLi - assumed) / 2 * geo.ip;
ok('the assumption is NOT replaced — the two rows differ by exactly μ0 R0 Δl_i Ip / 2',
   Math.abs((indAlt - indBase) - dPhi) < 1e-3,
   `measured ${(indAlt - indBase).toFixed(4)} Wb against ${dPhi.toFixed(4)} Wb`);

// --- T-D4: the pulse bar designs for a shape that was SOLVED ----------------
// It read the design bar's target CONTROLS: not running the design bar at all
// and pressing the pulse key gave bit-identical currents and volts, so the
// supplies were sized for a shape this machine had just failed to make.
//
// ★A FRESH PAGE, because the first of the two cases T-D4 asks about is the
// one where nothing has been solved yet — and by here the design bar has run
// three times.
await page.goto(BASE + 'pages/pulse_design.html?device=east#configure',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => [...document.querySelectorAll('[data-bar] .funcbar-state')]
    .some((e) => /就绪|Ready|失败|failed/.test(e.textContent)), null,
  { timeout: 180000 });
await page.evaluate(() => {
  const sec = document.querySelector('[data-bar="pfwave"]');
  if (sec.classList.contains('folded')) sec.querySelector('.funcbar-fold').click();
});
await page.waitForTimeout(500);
const pulseKey = async () => await page.evaluate(() => {
  const e = document.getElementById('pulse_design-pfwave-run');
  const n = document.querySelector('[data-bar="pfwave"] .funcbar-need');
  return { disabled: !!e.disabled, title: e.title,
           need: n && !n.hidden ? n.textContent : '' };
});
const beforeKey = await pulseKey();
ok('the pulse bar is blocked until a configuration has been solved',
   beforeKey.disabled && /位形|shape|coil|电流/.test(beforeKey.need),
   `${beforeKey.need} · ${beforeKey.title.slice(0, 40)}`);
//: the catalogue has carried this sentence since the bar was written and
//: nothing referenced it — a dead key, because nothing declared the
//: dependency it describes
ok('and the sentence saying what to do first is finally shown',
   /反解出一个位形|Design a configuration/.test(beforeKey.title),
   beforeKey.title.slice(0, 50));

await runBar('discharge');
const dsrc = await barState('discharge');
const afterKey = await pulseKey();
ok('and unblocked once it has', !afterKey.disabled,
   afterKey.title.slice(0, 30));

await page.fill('#pulse_design-vcap', '10');
await runBar('pfwave');
const pstate = await page.evaluate(
  () => document.querySelector('[data-bar="pfwave"] .funcbar-state')?.textContent || '');
const srcNote = await page.evaluate(
  () => document.getElementById('pulse_design-pfwave-source').innerText);
ok('the trajectory says which configuration it was designed for',
   /R₀/.test(srcNote), srcNote.slice(0, 60));
//: EAST's default target is not reached (位形误差 0.0479 against a tolerance
//: of 0.0284), so the trajectory inherits that verdict instead of reporting
//: a clean finish over a power supply nobody can build a shot with
ok('a trajectory designed for a configuration that missed says so',
   dsrc.state !== 'miss' || /未达成|未达目标|not met|missed/.test(srcNote),
   `${dsrc.state} · ${srcNote.slice(0, 46)}`);

const chans = await rows('pulse_design-pfwave-channels');
ok('the trajectory reports a demand for every channel',
   chans.length > 0, `${chans.length} channels`);
ok('both a current and a voltage are reported per channel',
   chans.every((r) => isFinite(parseFloat(r[1])) && isFinite(parseFloat(r[2]))),
   chans[0] && chans[0].join(' '));
//: ★limits are REPORTED, never applied: a 10 V/turn cap is well under what a
//: ramp needs, so some channel must be marked over it — and its current must
//: still be the one the design asked for rather than a clipped one
ok('a declared voltage limit is reported rather than silently applied',
   chans.some((r) => /超限|over/.test(r[4])) && /★/.test(pstate),
   pstate.slice(0, 60));
//: ★T-D12 again, on the one outcome no class can express: the run finished,
//: and what it produced does not fit inside a limit the machine declared.
//: That is 未达目标, not 已完成 — and the marker has to be the one that
//: disagrees with "finished", because the sentence beside it does.
const pst = await barState('pulse');
ok('a trajectory over a declared limit is marked 未达目标, not 已完成',
   pst.state === 'miss', `state=${pst.state} · ${pst.text.slice(0, 40)}`);
const checks = await rows('pulse_design-pfwave-checks');
ok('the forward verification solves real plasmas',
   checks.length > 0 && checks.every((r) => {
     const a = parseFloat((r[2] || '').split(',')[1]);
     return isFinite(a) && a > 0.1;
   }), checks.map((r) => r[2]).join(' | ').slice(0, 80));

// --- T-D8: the verification samples every phase, not the easiest twice -----
// Measured before this change: the default two points landed at t = 2.50 and
// 7.50 s with the flat-top running 1.0–8.0 s — both inside it, and the two
// configurations were identical to three decimals.  The hard instants (just
// after breakdown, mid-ramp, the retrace) were never verified at all.
const phaseCol = (rs) => rs.map((r) => r[1]);
ok('the default sampling no longer spends both points on the flat-top',
   new Set(phaseCol(checks)).size >= 2,
   `${phaseCol(checks).join(' + ')} at t = ` +
   checks.map((r) => r[0]).join(', '));
ok('and the two configurations it verifies are no longer identical',
   new Set(checks.map((r) => r[2])).size === checks.length,
   checks.map((r) => r[2]).join('  ‖  '));
// --- T-D15: the ramp is resolved, not sampled once --------------------------
// Measured before this change, at the defaults this gate is standing on
// (21 waypoints, breakdown 0 / ramp end 1 / flat-top end 8 / end 10 s): the
// grid was uniform at 0.5 s, so the 1 s ramp held ONE waypoint and the flat
// top held fifteen.  The ramp is where dI/dt is largest and the per-turn
// voltage is a difference quotient across neighbouring waypoints, so the one
// segment this bar exists to size the supplies for was resolved by a single
// sample — and it is why the four strata below could not all be populated.
//
// ★THE ORACLE IS THE GATE'S OWN CLASSIFICATION.  The waypoint times come off
// the bus (`FyScenario.pages.pulse_design.bus.pfwave()`), the phase boundaries come
// off the four controls, and the counting is done here — the page's own
// 「击穿 1 · 斜坡 7 · 平顶 5 · 下降 8」 readout is then checked AGAINST that,
// rather than being the thing that is trusted.
const pctl = await page.evaluate(() => {
  //: ★相位是这一页共用的一组控件（D-1 · D-20），不再是这条栏自己的四个框——
  //: 合并前它们在两条栏里各有一份，两处填得不一样时页面不会说。
  const g = (id) => +document.getElementById('pulse_design-' + id).value;
  const b = (id) => +document.getElementById('pulse_design-pfwave-' + id).value;
  return { bd: g('t_bd'), ra: g('t_ru'), fl: g('t_ft'), en: g('t_end'),
           n: b('npts'), nv: b('nverify') };
});
const traj = await page.evaluate(() => {
  const b = FyScenario.pages.pulse_design.bus.pfwave;
  const v = typeof b === 'function' ? b() : b;
  return v && { t: v.t, split: v.split, pinned: v.pinned,
                checks: v.checks.map((c) => ({ t: c.t, s: c.stratum,
                  target: c.target })) };
});
const phOf = (t) => (t <= pctl.bd ? 0
  : (t < pctl.ra ? 1 : (t <= pctl.fl ? 2 : 3)));
const wcount = [0, 0, 0, 0];
(traj ? traj.t : []).forEach((t) => { wcount[phOf(t)]++; });
ok('the trajectory publishes the waypoints it was built on',
   !!traj && traj.t.length === pctl.n,
   traj ? `${traj.t.length} waypoints, npts = ${pctl.n}` : 'no product');
//: the item itself: 「斜坡段只有一个波点」
ok('at default settings the ramp holds at least 3 waypoints, not one',
   wcount[1] >= 3,
   `breakdown ${wcount[0]} · ramp ${wcount[1]} · flat ${wcount[2]} · ` +
   `down ${wcount[3]} at t = ${traj.t.map((x) => x.toFixed(3)).join(' ')}`);
ok('and so does every other phase that has a duration',
   wcount[1] >= 3 && wcount[2] >= 3 && wcount[3] >= 3,
   `ramp ${wcount[1]} / flat ${wcount[2]} / down ${wcount[3]}`);
//: ★NON-DEGENERATE.  Every count above is also satisfied by simply asking
//: for more points on the SAME uniform grid, which is the fix this item does
//: not want (the flat top would grow with the ramp and the cost with both).
//: A refined grid is one whose steps are not all the same.
const steps = traj.t.slice(1).map((x, i) => x - traj.t[i]);
const rstep = Math.max(...steps) / Math.min(...steps);
ok('the grid is refined rather than merely finer — its steps are not uniform',
   rstep > 2, `step ${Math.min(...steps).toFixed(3)} … ` +
   `${Math.max(...steps).toFixed(3)} s, ratio ${rstep.toFixed(1)}`);
//: the corners of the trapezoid are grid points, or a difference quotient is
//: taken across a kink and is neither of the two slopes it joins
const onGrid = (x) => traj.t.some((t) => Math.abs(t - x) < 1e-9);
ok('and the phase boundaries are themselves waypoints',
   onGrid(pctl.bd) && onGrid(pctl.ra) && onGrid(pctl.fl) && onGrid(pctl.en),
   `${pctl.bd} / ${pctl.ra} / ${pctl.fl} / ${pctl.en}`);
//: what the page CLAIMS about its own grid, against the count above
const gsplit = await page.evaluate(
  () => document.getElementById('pulse_design-pfwave-gridsplit').innerText);
ok('the panel states the split, and states the one the gate counted',
   String(traj.split) === String(wcount)
     && wcount.every((c) => new RegExp(`\\b${c}\\b`).test(gsplit)),
   `${gsplit.replace(/\s+/g, ' ')} vs [${wcount}]`);
//: ★and the second half of the closure criterion: with the ramp resolved,
//: T-D8's stratified sampling covers all four strata AT THE DEFAULT nverify.
//: Before, the default was 2 — a budget below the number of strata cannot
//: cover them however the grid is built.
ok('the default verification budget is one point per phase',
   pctl.nv === 4, `nverify default = ${pctl.nv}`);
ok('and at that default the stratified sampling takes one from each phase',
   checks.length === 4 && new Set(phaseCol(checks)).size === 4
     && new Set(traj.checks.map((c) => c.s)).size === 4,
   `${phaseCol(checks).join(' · ')} at t = ` +
   `${checks.map((r) => r[0]).join(', ')}`);

// ★one point per phase, on a grid the reader asked for rather than the
// default one.  The default pulse USED to put a single waypoint inside its
// 1 s ramp, so 「just after breakdown」 and 「ramp」 could not both be drawn
// from it and this section had to raise `npts` to 41 to have four strata at
// all; T-D15 below is the same assertion at the DEFAULT settings.  It is kept
// because the stratification has to hold on a grid of any size.
await page.evaluate(() => {
  const e = document.getElementById('pulse_design-pfwave-npts');
  e.value = '41'; e.dispatchEvent(new Event('input'));
  const v = document.getElementById('pulse_design-pfwave-nverify');
  v.value = '4'; v.dispatchEvent(new Event('input'));
});
await runBar('pfwave');
const checks4 = await rows('pulse_design-pfwave-checks');
const ph4 = phaseCol(checks4);
ok('nverify = 4 puts one point in each of the four phases',
   checks4.length === 4 && new Set(ph4).size === 4,
   `${ph4.join(' · ')} at t = ${checks4.map((r) => r[0]).join(', ')}`);
ok('and every one of them is a solved plasma',
   checks4.every((r) => {
     const a = parseFloat((r[2] || '').split(',')[1]);
     return isFinite(a) && a > 0.1;
   }), checks4.map((r) => r[2]).join(' | ').slice(0, 90));
await page.evaluate(() => {
  const e = document.getElementById('pulse_design-pfwave-npts');
  e.value = '21'; e.dispatchEvent(new Event('input'));
  const v = document.getElementById('pulse_design-pfwave-nverify');
  v.value = '2'; v.dispatchEvent(new Event('input'));
});

// ★THE TEST THAT ONLY THE FIX PASSES: move the target controls and run the
// trajectory again WITHOUT re-solving.  Reading the controls, every number
// below moves; reading what was solved, not one of them does.
const chansA = chans.map((r) => r.join(' '));
await setShared('pulse_design-kappa', '1.35');
await runBar('pfwave');
const chansB = (await rows('pulse_design-pfwave-channels')).map((r) => r.join(' '));
ok('moving the target without re-solving does not move the trajectory',
   chansA.length === chansB.length && chansA.every((r, i) => r === chansB[i]),
   `${chansA[0]}  vs  ${chansB[0]}`);
// ...and re-solving DOES move it, or the check above would pass on a bar
// that had simply stopped reading anything at all.
await runBar('discharge');
await runBar('pfwave');
const chansC = (await rows('pulse_design-pfwave-channels')).map((r) => r.join(' '));
ok('re-solving the configuration does move it',
   chansC.some((r, i) => r !== chansA[i]),
   `${chansA[0]}  vs  ${chansC[0]}`);

// --- T-D5: engineering limits, and what「no limit」has to look like --------
// The 「对照」 column was empty on every channel of every machine: the page
// could say PF1 needs 778.2 kA·turn at 50.5 V/turn and not say whether EAST's
// PF1 can give it.  The descriptor now has a slot for that, none of the four
// bundled machines fills it, and the rule is FR-PULSE-004's: an undeclared
// limit is reported as 未知 and NEVER replaced by a default.
await page.fill('#pulse_design-vcap', '0');
await runBar('pfwave');
const cap0 = await rows('pulse_design-pfwave-channels');
ok('with nothing declared, every channel says 未知 rather than a verdict',
   cap0.length > 0 && cap0.every((r) => /未知|unknown/.test(r[3])
                                     && /未知|unknown/.test(r[4])),
   cap0[0] && cap0[0].join(' | '));
ok('and never「within」— there is no limit to be within',
   cap0.every((r) => !/在限值内|within/.test(r[4])),
   cap0.map((r) => r[4]).join(' ').slice(0, 60));
const srcNone = await page.evaluate(
  () => document.getElementById('pulse_design-pfwave-limits-src').innerText);
ok('and the panel says the machine declares none',
   /没有工程限值段|no engineering-limits section/.test(srcNone),
   srcNone.slice(0, 60));

// ★now DECLARE some, on the live machine, and watch the column fill without
// a single number in the design moving: limits are reported, never applied.
await page.evaluate(() => {
  self.FYLITE_MACHINE.limits = {
    provenance: 'validate-design.mjs, synthetic',
    oh_flux_swing_Wb: 12.0,
    per_channel: self.FYLITE_MACHINE.channels.map(() => (
      { i_max_kAturn: 500, v_max_V_per_turn: 60, f_max_kN: 900 })),
  };
});
await runBar('pfwave');
const cap1 = await rows('pulse_design-pfwave-channels');
ok('a declared per-channel limit fills the column it was empty in',
   cap1.every((r) => /500/.test(r[3]) && /60/.test(r[3]))
     && cap1.some((r) => /超限|over/.test(r[4]))
     && cap1.some((r) => /在限值内|within/.test(r[4])),
   cap1[0] && cap1[0].join(' | '));
ok('and the demand is untouched — reported, never clipped',
   cap0.length === cap1.length
     && cap0.every((r, i) => r[1] === cap1[i][1] && r[2] === cap1[i][2]),
   `${cap0[0][1]}/${cap0[0][2]} → ${cap1[0][1]}/${cap1[0][2]}`);
//: ★the force column stays 未知 even when a force limit IS declared: this
//: page does not compute coil forces, so there is nothing to read it
//: against, and「within」would be a verdict on an unmade measurement
ok('a declared force limit is shown but not turned into a verdict',
   cap1.every((r) => /900/.test(r[3])),
   cap1[0][3]);

// ★and the OH swing: declared on the machine, it becomes a flat-top duration
// — the FR-PULSE-004 half that was already right, now fed from the device.
await runBar('zerod');
const fx2 = await rows('pulse_design-zerod-flux');
const cell2 = (re) => { const r = fx2.find((x) => re.test(x[0])); return r ? r[1] : ''; };
const swing = cell2(/可用摆幅|available swing/);
const ramp = parseFloat(cell2(/到平顶合计|to flat-top/));
const vflat = parseFloat(cell2(/平顶平均环电压|flat-top/));
const sustain = parseFloat(cell2(/可维持的平顶|sustain/));
ok('a swing declared by the machine is used and says where it came from',
   /12\.00/.test(swing) && /装置描述|device description/.test(swing),
   swing.replace(/\n/g, ' '));
ok('and it becomes a flat-top duration, not a mystery',
   isFinite(sustain) && Math.abs(sustain - (12.0 - ramp) / vflat) < 0.15,
   `${sustain} s against (12.0 − ${ramp}) / ${vflat} = ` +
   `${((12.0 - ramp) / vflat).toFixed(2)} s`);

// --- T-D13: target shapes at several instants -------------------------------
// There was ONE target shape — the flat top — and this bar scaled it by
// phase.  Real pulse design gives a shape at each of several key instants;
// T-D15 gave the time grid, this gives the targets on it.  The rows are
// pinned corrections on the phase-scaled flat top, which is what makes the
// first assertion below possible at all: a reader who gives one target has
// to keep getting exactly today's answer.
await page.evaluate(() => {
  const v = document.getElementById('pulse_design-pfwave-nverify');
  v.value = '4'; v.dispatchEvent(new Event('input'));
});
await runBar('pfwave');
const kBase = (await rows('pulse_design-pfwave-channels')).map((r) => r.join(' '));
const kNote0 = await page.evaluate(
  () => document.getElementById('pulse_design-pfwave-keys-note').innerText);
ok('with no instants given the panel says the flat top is scaled by phase',
   /^0\b/.test(kNote0.trim()), kNote0.trim().slice(0, 50));

// ★ADDING ONE CHANGES NOTHING.  The row is seeded with the shape the
// trajectory already had at that instant, so its correction is exactly zero
// — this is the assertion that says single-target behaviour still works, and
// it is worth nothing without the one after it.
await page.click('#pulse_design-pfwave-keyadd');
await runBar('pfwave');
const kAdd = (await rows('pulse_design-pfwave-channels')).map((r) => r.join(' '));
ok('an instant seeded from the trajectory leaves the trajectory alone',
   kBase.length === kAdd.length && kBase.every((r, i) => r === kAdd[i]),
   `${kBase[0]}  vs  ${kAdd[0]}`);

// ...and now two instants that ask for something else: a rounder, smaller
// plasma mid-ramp and a squatter one on the flat top.  Both instants are OFF
// the refined grid, so they also have to be inserted into it.
const KROW = [{ i: 0, t: 0.40, a: 0.330, k: 1.900 },
              { i: 1, t: 3.20, a: 0.380, k: 1.250 }];
const setKey = async (r) => await page.evaluate((k) => {
  const set = (f, v) => {
    const e = document.getElementById(`pulse_design-pfwave-kf${k.i}-f${f}`);
    e.value = v; e.dispatchEvent(new Event('input'));
  };
  set('t', k.t.toFixed(2)); set('a', k.a.toFixed(3));
  set('kappa', k.k.toFixed(3));
}, r);
await setKey(KROW[0]);
await page.click('#pulse_design-pfwave-keyadd');
await setKey(KROW[1]);
await runBar('pfwave');
const traj2 = await page.evaluate(() => {
  const v = FyScenario.pages.pulse_design.bus.pfwave();
  return v && { t: v.t, pinned: v.pinned, n: v.t.length };
});
const pinnedAt = traj2.t.filter((x, i) => traj2.pinned[i]);
ok('an instant that was asked for is an instant that was designed for',
   KROW.every((k) => traj2.t.some((t) => Math.abs(t - k.t) < 1e-9))
     && pinnedAt.length === 2 && traj2.n === pctl.n + 2,
   `${traj2.n} waypoints, pinned at ${pinnedAt.join(', ')}`);

const chk13 = await rows('pulse_design-pfwave-checks');
const atT = (t) => chk13.find(
  (r) => Math.abs(parseFloat(r[0].replace('★', '')) - t) < 5e-3);
const tgOf = (r) => r[2].split(',').map((x) => parseFloat(x));
ok('the verification spends its points on the instants that were pinned',
   KROW.every((k) => { const r = atT(k.t); return r && /★/.test(r[0]); }),
   chk13.map((r) => r[0]).join(' · '));
//: ★EACH INSTANT AGAINST ITS OWN TARGET.  One target on the page would have
//: put the same numbers in both rows; the check that this is not that is the
//: pair below — each row equals ITS OWN row, and the two rows differ.
ok('and each of them is checked against its own target, not a scaled flat top',
   KROW.every((k) => {
     const g = tgOf(atT(k.t));
     return Math.abs(g[1] - k.a) < 5e-4 && Math.abs(g[2] - k.k) < 5e-4;
   }),
   KROW.map((k) => `t=${k.t}: ${atT(k.t)[2]}  asked ${k.a}, ${k.k}`).join(' | '));
ok('and the two targets are different targets',
   String(tgOf(atT(KROW[0].t))) !== String(tgOf(atT(KROW[1].t))),
   `${atT(KROW[0].t)[2]}  ‖  ${atT(KROW[1].t)[2]}`);
const kEdit = (await rows('pulse_design-pfwave-channels')).map((r) => r.join(' '));
ok('and asking for a different shape does move the supplies',
   kEdit.some((r, i) => r !== kBase[i]),
   `${kBase[0]}  vs  ${kEdit[0]}`);

// ★A ROW THIS BAR CANNOT USE IS DROPPED AND SAID SO — not clipped into one it
// can.  Same rule as the limits column: the page must not answer a question
// nobody asked it.
await page.evaluate(() => {
  [0, 1].forEach((i) => {
    const e = document.getElementById(`pulse_design-pfwave-kf${i}-ft`);
    e.value = '99'; e.dispatchEvent(new Event('input'));
  });
});
const kNote2 = await page.evaluate(
  () => document.getElementById('pulse_design-pfwave-keys-note').innerText);
await runBar('pfwave');
const kDrop = (await rows('pulse_design-pfwave-channels')).map((r) => r.join(' '));
ok('an instant outside the pulse is reported as unused, not clipped into it',
   /2/.test(kNote2) && /未采用|not used/.test(kNote2)
     && kBase.every((r, i) => r === kDrop[i]),
   `${kNote2.trim().slice(0, 60)} · ${kDrop[0]}`);

// --- T-D16: the pulse bar has a session file of its own ---------------------
// The (时刻, 位形) rows T-D13 added are control state, and this bar had no
// session format — so they could not be saved and could not be handed to
// anyone.  Neither could any other setting on it: the two bars beside it have
// written session files since they were built and this one never did.
//
// Two things are asserted, and the second is the one that keeps the first
// honest.  ①ROUND TRIP: export → import → the same trajectory, exactly.
// ②WHAT THE FILE CANNOT CARRY: the flat-top 位形 this trajectory aims at is
// not this bar's input to give — it is what the bar above SOLVED (T-D4) — so
// the file records it as provenance and the import must SAY whether the
// configuration standing on the page is that one, rather than quietly
// applying a subset or, worse, restoring a boundary nobody recomputed.
//
// ★THE ORACLE IS NOT THE RENDERED TABLE.  The per-channel demand is read off
// the bus at full precision (`bus.pulse().demand`); the table rounds to a
// tenth of a kA·turn, so 「逐位相同」 read off it would be a statement about
// the formatter.  The rendered rows are compared as well, because that is
// what the reader sees.
const OUT = mkdtempSync(join(tmpdir(), 'pulse_design-'));
const savePulse = async (name) => {
  await page.click('#pulse_design-ioexport');
  const [d] = await Promise.all([page.waitForEvent('download'),
                                 page.click('#pulse_design-iofmt-pfwave-json')]);
  const f = join(OUT, name);
  await d.saveAs(f);
  return JSON.parse(readFileSync(f, 'utf8'));
};
const importPulse = async (name, doc) => {
  const f = join(OUT, name);
  if (doc) writeFileSync(f, JSON.stringify(doc, null, 1));
  const [ch] = await Promise.all([page.waitForEvent('filechooser'),
                                  page.click('#pulse_design-ioimport')]);
  await ch.setFiles({ name, mimeType: 'application/json',
                      buffer: readFileSync(f) });
  await page.waitForTimeout(900);
  return await page.evaluate(() => ({
    note: (document.getElementById('pulse_design-pfwave-imported') || {}).innerText || '',
    hidden: !!(document.getElementById('pulse_design-pfwave-imported') || {}).hidden,
    keys: (document.getElementById('pulse_design-pfwave-keys-note') || {}).innerText || '',
    status: (document.getElementById('pulse_design-status') || {}).innerText || '',
  }));
};
const pulseBus = async () => await page.evaluate(() => {
  const v = FyScenario.pages.pulse_design.bus.pfwave();
  return v && { t: v.t.slice(), demand: v.demand };
});

// put the two rows back where T-D13 had them before moving them off the
// pulse, so the file has something in it that is not the default
await setKey(KROW[0]);
await setKey(KROW[1]);
await page.evaluate(() => {
  const e = document.getElementById('pulse_design-vcap');
  e.value = '10'; e.dispatchEvent(new Event('change'));
});
await runBar('pfwave');
const busA = await pulseBus();
const tableA = (await rows('pulse_design-pfwave-channels')).map((r) => r.join(' '));
ok('the trajectory publishes its per-channel demand unrounded',
   !!busA && busA.demand.length > 0
     && busA.demand.some((d) => d.i > 0 && d.v > 0),
   busA ? `${busA.demand.length} channels, PF1 ${busA.demand[0].i.toFixed(6)} ` +
          `A·turn / ${busA.demand[0].v.toFixed(6)} V/turn` : 'no product');

const pdoc = await savePulse('pulse.json');
const pcfg = pdoc['fylite:config'] || {};
ok('the pulse bar writes a session document that names the bar',
   pdoc['@type'] === 'fylite:AppSession/1' && pdoc['fylite:page'] === 'pulse',
   `${pdoc['@type']} · ${pdoc['fylite:page']}`);
//: ★the discipline the corpus's own documents are held to (`fylite cases
//: --check`), applied here to the file a READER saves: a case is a session
//: document, so a session document that carried a result would be a number
//: nobody recomputed
ok('and it is a case in form — inputs, no result',
   !pdoc['fylite:result'] && !pdoc['fylite:reference'] && !!pdoc['fylite:config'],
   Object.keys(pdoc).join(' '));
//: ★合并之后前缀不再只有一个：「这一炮」的量（相位、位形比、限值）住在页面
//: 上，求解设定（波点数、校验片数）留在栏上。写死任一个前缀都会在另一半上
//: 落空，所以这里按名字挑。
const PD_SHARED = new Set(['t_bd', 't_ru', 't_ft', 't_end', 'a0', 'a1',
                           'vcap', 'icap', 'z0', 'ip', 'r0', 'a', 'kappa',
                           'du', 'dl', 'ne', 'te', 'paux', 'hfac',
                           'phiavail', 't_on', 't_off']);
const PD_ID = (id) => (PD_SHARED.has(id) ? 'pulse_design-' : 'pulse_design-pfwave-') + id;
const PCTL = ['t_bd', 't_ru', 't_ft', 't_end', 'npts', 'a0', 'nverify', 'vcap'];
const plainKeys = Object.keys(pcfg).filter((k) => !k.includes(':'));
ok('the ids inside are bare, as every session file on these pages is',
   plainKeys.length === PCTL.length
     && PCTL.every((k) => plainKeys.includes(k))
     && plainKeys.every((k) => !/^design/.test(k)),
   plainKeys.join(' '));
const krows = pcfg['fylite:target_keys'];
ok('the (instant, shape) rows are in the file',
   Array.isArray(krows) && krows.length === 2
     && KROW.every((k, i) => krows[i].t === k.t && krows[i].a === k.a
                             && krows[i].kappa === k.k),
   JSON.stringify(krows));
//: ★AND AT FULL PRECISION, not at the three decimals the cells display.
//: T-D13's property is that a row seeded from the trajectory is a correction
//: of EXACTLY zero; rounding on the way out would make it about 1e-8 —
//: small, and not zero, and the round trip would then be a different run.
const moreThan3dp = (v) => isFinite(v)
  && Math.abs(v * 1e3 - Math.round(v * 1e3)) > 1e-9;
ok('and verbatim, carrying more digits than the cells show',
   Array.isArray(krows) && krows.some(
     (r) => ['r0', 'z0', 'du', 'dl'].some((c) => moreThan3dp(r[c]))),
   JSON.stringify(krows && krows[0]));
const solvedShape = await page.evaluate(() => {
  const d = FyScenario.pages.pulse_design.bus.discharge();
  return d && d.shape;
});
const dfor = pdoc['fylite:designed_for'];
ok('the configuration it was designed for is recorded as provenance',
   !!dfor && !!dfor['fylite:shape'] && !!solvedShape
     && ['r0', 'z0', 'a', 'kappa', 'deltaU', 'deltaL'].every(
          (c) => dfor['fylite:shape'][c] === solvedShape[c]),
   dfor ? JSON.stringify(dfor['fylite:shape']) : 'absent');

// ★NON-DEGENERACY FIRST.  Move every setting the file carries, and the rows
// with them: a round trip onto a page that never changed would pass on an
// import that did nothing at all.
await page.evaluate((shared) => {
  const set = (id, v, ev) => {
    const e = document.getElementById(
      (shared.includes(id) ? 'pulse_design-' : 'pulse_design-pfwave-') + id);
    e.value = v; e.dispatchEvent(new Event(ev));
  };
  set('npts', '33', 'input'); set('a0', '0.70', 'input');
  set('nverify', '2', 'input'); set('vcap', '0', 'change');
  set('t_ft', '7.0', 'change');
  //: the rows go too — the indices shift on each removal, so the last first
  document.querySelector('[data-kfdel="1"]').click();
  document.querySelector('[data-kfdel="0"]').click();
}, [...PD_SHARED]);
await runBar('pfwave');
const busMid = await pulseBus();
ok('moving those settings moves the trajectory',
   busMid.t.length !== busA.t.length
     && busMid.demand.some((d, i) => d.i !== busA.demand[i].i),
   `${busA.t.length} → ${busMid.t.length} waypoints, PF1 ` +
   `${(busA.demand[0].i / 1e3).toFixed(1)} → ` +
   `${(busMid.demand[0].i / 1e3).toFixed(1)} kA·turn`);

const back1 = await importPulse('pulse.json');
const ctlBack = await page.evaluate((shared) => {
  const g = (id) => +document.getElementById(
    (shared.includes(id) ? 'pulse_design-' : 'pulse_design-pfwave-') + id).value;
  return { t_bd: g('t_bd'), t_ru: g('t_ru'), t_ft: g('t_ft'), t_end: g('t_end'),
           npts: g('npts'), a0: g('a0'), nverify: g('nverify'), vcap: g('vcap') };
}, [...PD_SHARED]);
//: the LATTICE hazard: a range input snaps to its own step, and a value that
//: snapped is a different run.  ★This gate is where it is checked now — the
//: corpus gate that used to state it went with the case menus (2026-09-01),
//: while import/export, which runs the same `FySession.apply`, did not.
ok('every control comes back holding exactly what the file asked for',
   PCTL.every((k) => ctlBack[k] === pcfg[k]),
   PCTL.filter((k) => ctlBack[k] !== pcfg[k])
       .map((k) => `${k}: ${pcfg[k]}→${ctlBack[k]}`).join(' ') || 'all exact');
//: ★the rows are checked by writing the file AGAIN: the cells display three
//: decimals, so reading them back would compare the formatter with itself.
//: Two exports whose `fylite:config` blocks are identical strings is the
//: whole round trip, rows and controls together, at full precision.
const pdoc2 = await savePulse('pulse-again.json');
ok('and the file written after the import is the file that was read',
   JSON.stringify(pdoc2['fylite:config']) === JSON.stringify(pcfg),
   JSON.stringify(pdoc2['fylite:config']).slice(0, 110));
//: ★and it says it in prose, not in markup: `FyI18n.t` escapes what it
//: substitutes, so a translated sentence pushed through a placeholder
//: reaches the reader as its own `<strong>` tags
ok('the import says it is standing on the configuration the file was written against',
   /一致|same/.test(back1.note) && !back1.hidden && !/<\w+>/.test(back1.note),
   back1.note.replace(/\s+/g, ' ').slice(0, 110));

await runBar('pfwave');
const busB = await pulseBus();
const tableB = (await rows('pulse_design-pfwave-channels')).map((r) => r.join(' '));
ok('export → import → the per-channel demand is bit-identical',
   busB.demand.length === busA.demand.length
     && busB.demand.every((d, i) => d.i === busA.demand[i].i
                                 && d.v === busA.demand[i].v),
   busB.demand.map((d, i) => `${(d.i - busA.demand[i].i)}/${d.v - busA.demand[i].v}`)
      .join(' ').slice(0, 80) || '');
ok('and so are the waypoints it was built on, and the table on screen',
   busB.t.length === busA.t.length
     && busB.t.every((t, i) => t === busA.t[i])
     && tableB.length === tableA.length
     && tableB.every((r, i) => r === tableA[i]),
   `${busB.t.length} waypoints · ${tableA[0]}`);

// ★AND THE HALF THAT MATTERS WHEN THE FILE TRAVELS.  A file written against
// one configuration, opened on a page holding another, must SAY so — and
// must not restore the sender's boundary, which nothing here recomputed.
const alien = JSON.parse(readFileSync(join(OUT, 'pulse.json'), 'utf8'));
alien['fylite:designed_for']['fylite:shape'].a += 0.05;
const back2 = await importPulse('pulse-alien.json', alien);
ok('a file designed against another configuration says so rather than applying it',
   /不是|not/.test(back2.note)
     && new RegExp(alien['fylite:designed_for']['fylite:shape'].a.toFixed(3))
          .test(back2.note),
   back2.note.replace(/\s+/g, ' ').slice(0, 130));
await runBar('pfwave');
const busC = await pulseBus();
ok('and the trajectory follows the page, not the shape written in the file',
   busC.demand.every((d, i) => d.i === busA.demand[i].i
                            && d.v === busA.demand[i].v),
   `PF1 ${(busC.demand[0].i / 1e3).toFixed(3)} vs ` +
   `${(busA.demand[0].i / 1e3).toFixed(3)} kA·turn`);

// ★a file with no rows section is not a file asking for no rows
const noKeys = JSON.parse(readFileSync(join(OUT, 'pulse.json'), 'utf8'));
delete noKeys['fylite:config']['fylite:target_keys'];
const back3 = await importPulse('pulse-nokeys.json', noKeys);
const stillTwo = await page.evaluate(
  () => document.querySelectorAll('[data-kfdel]').length);
ok('a file carrying no rows section leaves the rows alone and says it did',
   stillTwo === 2 && /不带|carries no/.test(back3.note),
   `${stillTwo} rows · ${back3.note.replace(/\s+/g, ' ').slice(0, 100)}`);

// --- T-D6: the boundary class is an input -----------------------------------
// This page could set δu/δl and, separately, tick a field-null constraint at
// two numbers, and it could READ 「限制器 / 偏滤器」 off the answer.  What it
// could not do was ASK for a class, and nothing judged whether the class that
// came back was the one wanted.
//
// ★A FRESH PAGE for this section: the sections above have moved the shared
// geometry and left the coil table wherever their last anneal put it, and the
// bit-identical claim below is about a control, not about the order the gate
// happens to press things in.
await page.goto(BASE + 'pages/pulse_design.html?device=east#configure',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => [...document.querySelectorAll('[data-bar] .funcbar-state')]
    .some((e) => /就绪|Ready|失败|failed/.test(e.textContent)), null,
  { timeout: 180000 });
const clsOpts = await page.evaluate(() => {
  const s = document.getElementById('pulse_design-discharge-class');
  return s ? Array.from(s.options).map(
    (o) => ({ v: o.value, dis: !!o.disabled })) : null;
});
ok('the boundary class is a control on the page, not a reading off the answer',
   !!clsOpts && ['limiter', 'lsn', 'usn', 'dn']
     .every((v) => clsOpts.some((o) => o.v === v)),
   clsOpts ? clsOpts.map((o) => o.v + (o.dis ? '(disabled)' : '')).join(' ')
           : 'no control');
//: ★T-D18 CLOSES THIS.  The double null used to be offered and DISABLED,
//: because the start design's kernel entry took exactly one field null; the
//: entry now takes a SET, so the option is live and the page names the entry
//: that made it so.  This assertion replaces the one that pinned the
//: limitation — it is the same fact, on the other side of the fix.
const clsNote = await page.evaluate(() => {
  const p = Array.from(document.querySelectorAll('[data-part="pulse_design"] .note'))
    .find((e) => /双零|[Dd]ouble null/.test(e.innerText));
  return p ? p.innerText : '';
});
ok('the double null is selectable, and the page names the entry that takes a set of nulls',
   !!clsOpts && clsOpts.find((o) => o.v === 'dn').dis === false
     && /start_currents_multi/.test(clsNote),
   clsNote.replace(/\s+/g, ' ').slice(-150));

const clsState = async () => await page.evaluate(() => {
  const g = (i) => document.getElementById('pulse_design-discharge-' + i);
  return { cls: g('class').value, usex: g('usex').checked,
           dis: g('usex').disabled, xr: +g('xr').value, xz: +g('xz').value };
});
const setClass = async (v) => {
  await page.evaluate((x) => {
    const e = document.getElementById('pulse_design-discharge-class');
    e.value = x; e.dispatchEvent(new Event('change'));
  }, v);
  await page.waitForTimeout(300);
};
const uiSeed = await page.evaluate(() => {
  const u = (self.FYLITE_MACHINE.ui || {});
  return u.xr && u.xz ? { r: +u.xr.value, z: +u.xz.value } : null;
});
//: ★T-D17: the seed is a NUMBER WITH A SOURCE now — the reference
//: discharge's own lower X point (delivered boundary corner, (1.606,
//: −0.7215), declared at the page's own 3-decimal control grid as −0.722:
//: `setNum` writes `toFixed(3)`, and a declared 4th decimal would come
//: back off the declaration and fail every exact-match round-trip above).
//: The old (1.62, −1.00) sat 0.28 m below it, and 选单零 dropped every
//: reader onto that invented point.  Pinned here so a descriptor edit
//: cannot quietly bring the invented number back; the assertions below
//: then say the page FOLLOWS the declared seed.
ok('EAST 声明的 X 种子就是参考放电的真 X 点（(1.606, −0.7215) 取页面 3 位）',
   !!uiSeed && Math.abs(uiSeed.r - 1.606) < 1e-9 &&
   Math.abs(Math.abs(uiSeed.z) - 0.722) < 1e-9,
   uiSeed && `种子 (${uiSeed.r}, ${uiSeed.z})`);
const cLim0 = await clsState();
ok('“limiter” asks for no field null at all, and the checkbox is the class’s',
   cLim0.cls === 'limiter' && cLim0.usex === false && cLim0.dis === true,
   JSON.stringify(cLim0));
await setClass('lsn');
const cLsn = await clsState();
//: ★WHERE THE NULL GOES IS THE DEVICE'S BUSINESS FIRST.  EAST declares a
//: seed in its descriptor; a page that overwrote it with a corner of its own
//: would be inventing a number the machine file already states.
ok('a single null adds the X-point row automatically, at the seed the device declares',
   cLsn.usex === true && cLsn.dis === true && !!uiSeed
     && cLsn.xr === uiSeed.r && cLsn.xz === -Math.abs(uiSeed.z),
   `${JSON.stringify(cLsn)} vs device seed ${JSON.stringify(uiSeed)}`);
await setClass('usn');
const cUsn = await clsState();
ok('and the upper null is the same seed on the other side',
   cUsn.xr === uiSeed.r && cUsn.xz === Math.abs(uiSeed.z),
   `${cUsn.xr}, ${cUsn.xz}`);

// ★BIT-IDENTICAL AT “LIMITER”.  A reader who never touches this control has
// to get the answer this page gave before it existed — so the limiter run is
// taken, the class is moved away and back, and the second limiter run must
// reproduce the first exactly.  The middle run is what stops that from being
// a statement about a page that had simply stopped reading the control.
const dState = async () => await page.evaluate(() => {
  const d = FyScenario.pages.pulse_design.bus.discharge();
  const st = document.querySelector('[data-bar="discharge"] .funcbar-state');
  return d && { shape: d.shape, chan: d.chan, err: d.err, reached: d.reached,
                bnd: d.bndKind, q95: d.criteria.q95, cls: d.boundaryClass,
                met: d.classMet, legs: d.strike,
                mark: st ? st.dataset.state : '' };
});
//: ★★AND THE INPUTS ARE READ BESIDE THE ANSWER, for the bit-identical
//: assertions below.  Those assertions compare six numbers; when they fail
//: they used to print those six numbers, which says a design differs and
//: nothing about WHY — and the one time this went red (TODO T-D19) it was on
//: a host this repository could not reproduce, so the six numbers were the
//: whole of the evidence and they were not enough to name a cause.
//: A snapshot of every control the bar owns costs one `evaluate` per run and
//: turns「两次答案不同」into「这个控件不同」or「输入完全相同」— which is a
//: different, and much harder, thing to explain away.
const dControls = async () => await page.evaluate(() => {
  const sec = document.querySelector('[data-bar="discharge"]');
  const out = {};
  sec.querySelectorAll('input, select').forEach((e) => {
    if (!e.id) return;
    out[e.id] = e.type === 'checkbox' ? !!e.checked : e.value;
  });
  out['*ctlRows'] = document.querySelectorAll('[data-ctldel]').length;
  return out;
});
//: what differs between two control snapshots, as one readable line
const dWhy = (a, b) => {
  const ks = [...new Set([...Object.keys(a || {}), ...Object.keys(b || {})])];
  const d = ks.filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]))
    .map((k) => `${k} ${JSON.stringify(a[k])}→${JSON.stringify(b[k])}`);
  return d.length ? `控件差异: ${d.join(' · ')}`
                  : '控件逐项相同 —— 两次的输入没有差别';
};
//: ★and from the SAME starting state each time.  This anneal is a local
//: method that begins at the coil currents in the table, so a second run
//: started on the first run's answer is a different run whatever the class
//: says — 「回到参考放电」 is the page's own way of saying "start here".
const fromReference = async (cls) => {
  await page.click('#pulse_design-discharge-reset');
  for (let i = 0; i < 120; i++) {
    await page.waitForTimeout(250);
    if (!await page.evaluate(
      () => !!document.querySelector('.funcbar-run.stop'))) break;
  }
  await page.waitForTimeout(600);
  await setClass(cls);
  //: read AFTER the class is applied and BEFORE the run — these are the
  //: inputs the anneal about to run actually sees
  const ctrls = await dControls();
  await runBar('discharge');
  return { ...await dState(), '#controls': ctrls };
};
const dLim1 = await fromReference('limiter');
const dLsn = await fromReference('lsn');
const dLim2 = await fromReference('limiter');
const same = (a, b) => a.chan.length === b.chan.length
  && a.chan.every((v, i) => v === b.chan[i])
  && a.err === b.err && a.q95 === b.q95
  && ['r0', 'z0', 'a', 'kappa', 'deltaU', 'deltaL']
       .every((k) => a.shape[k] === b.shape[k]);
ok('asking for a single null moves the design',
   !same(dLim1, dLsn),
   `err ${dLim1.err.toFixed(6)} → ${dLsn.err.toFixed(6)}, ` +
   `q95 ${dLim1.q95.toFixed(6)} → ${dLsn.q95.toFixed(6)}, ` +
   `PF1 ${(dLim1.chan[0] / 1e3).toFixed(3)} → ${(dLsn.chan[0] / 1e3).toFixed(3)} kA·turn`);
ok('and coming back to “limiter” is bit-identical to what it gave before',
   same(dLim1, dLim2),
   `err ${dLim1.err} / ${dLim2.err} · q95 ${dLim1.q95} / ${dLim2.q95} · ` +
   `PF1 ${dLim1.chan[0]} / ${dLim2.chan[0]}\n        ` +
   dWhy(dLim1['#controls'], dLim2['#controls']));

// ★AND THE CLASS IS JUDGED.  The verdict must follow the solved topology in
// both directions, or「says so」would be satisfied by a row that always
// complains.  Under “limiter” it must report 未要求 rather than a verdict.
const critRow = async (re) => (await rows('pulse_design-discharge-criteria'))
  .find((r) => re.test(r[0])) || [];
const dJudge = await fromReference('lsn');
const rowCls = await critRow(/要求的位形类别|Class asked/);
const rowLeg = await critRow(/打击点数|Strike points/);
const legNote = await page.evaluate(
  () => document.getElementById('pulse_design-discharge-strike-verdict').innerText);
ok('the criteria table carries the class that was asked for, judged',
   rowCls.length === 3 && /单零|single null/.test(rowCls[1])
     && (dJudge.bnd === 1) === !/★/.test(rowCls[2]),
   `${rowCls.join(' | ')}  (bndKind ${dJudge.bnd})`);
ok('the strike points are a criterion, with the number the class requires',
   rowLeg.length === 3 && /2/.test(legNote)
     && new RegExp(`\\b${dJudge.legs}\\b`).test(legNote)
     && (dJudge.legs >= 2 && dJudge.bnd === 1) === !/★/.test(rowLeg[2]),
   `${rowLeg.join(' | ')} · ${legNote.replace(/\s+/g, ' ').slice(0, 110)}`);
//: ★the measured fact on the only machine with a real descriptor, stated as
//: an implication so the assertion stays true the day the model can do it
ok('a design asked for a divertor and handed a limiter does not report success',
   dJudge.bnd === 1
     ? (dJudge.met === true)
     : (dJudge.met === false && dJudge.reached === false
        && dJudge.mark === 'miss'),
   `bndKind ${dJudge.bnd} · classMet ${dJudge.met} · reached ` +
   `${dJudge.reached} · marker ${dJudge.mark} · legs ${dJudge.legs}`);
await fromReference('limiter');
const rowFree = await critRow(/要求的位形类别|Class asked/);
ok('and “limiter” reports 未要求 rather than a verdict it did not earn',
   /—/.test(rowFree[2]) && !/★/.test(rowFree[2]),
   rowFree.join(' | '));

// ★the class travels in the session file, and a file written before this
// control existed still says what it asked for — in the old vocabulary
const dSave = async () => {
  await page.click('#pulse_design-ioexport');
  const [d] = await Promise.all([page.waitForEvent('download'),
                                 page.click('#pulse_design-iofmt-discharge-json')]);
  const f = join(OUT, 'design.json');
  await d.saveAs(f);
  return JSON.parse(readFileSync(f, 'utf8'));
};
await setClass('usn');
const dDoc = await dSave();
await setClass('limiter');
const dImport = async (doc) => {
  writeFileSync(join(OUT, 'design-in.json'), JSON.stringify(doc, null, 1));
  const [ch] = await Promise.all([page.waitForEvent('filechooser'),
                                  page.click('#pulse_design-ioimport')]);
  await ch.setFiles({ name: 'design-in.json', mimeType: 'application/json',
                      buffer: readFileSync(join(OUT, 'design-in.json')) });
  await page.waitForTimeout(1200);
  return await clsState();
};
const backCls = await dImport(dDoc);
ok('the class round-trips through the session file',
   dDoc['fylite:config']['class'] === 'usn' && backCls.cls === 'usn'
     && backCls.usex === true && backCls.xz === Math.abs(uiSeed.z),
   `${dDoc['fylite:config']['class']} → ${JSON.stringify(backCls)}`);
const oldDoc = JSON.parse(JSON.stringify(dDoc));
delete oldDoc['fylite:config']['class'];
oldDoc['fylite:config'].usex = true;
oldDoc['fylite:config'].xz = -1.0;
oldDoc['fylite:config'].z0 = 0;
const backOld = await dImport(oldDoc);
ok('a session written before this control still says what it asked for',
   backOld.cls === 'lsn' && backOld.usex === true,
   `usex true, xz −1.00 → ${backOld.cls}`);

// --- T-D18: the start design takes TWO field nulls ---------------------------
// The kernel entry the start design goes through took exactly one field null
// (`xR`/`xZ`/`useX`), so 双零 was listed on the page and DISABLED with that
// signature named as the reason.  It now takes a SET
// (`fylite_rs_start_currents_multi`), and the anneal's rows were widened the
// same way — three rows per null on both sides of the inverse solve.
//
// ★A FRESH PAGE again: the section above ended inside a session import.
await page.goto(BASE + 'pages/pulse_design.html?device=east#configure',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => [...document.querySelectorAll('[data-bar] .funcbar-state')]
    .some((e) => /就绪|Ready|失败|failed/.test(e.textContent)), null,
  { timeout: 180000 });

const dnState = async () => await page.evaluate(() => {
  const g = (i) => document.getElementById('pulse_design-discharge-' + i);
  //: ★Z₀ 是页面共用的了：一个量被两条栏读，就不住在其中一条栏里（D-20）
  return { cls: g('class').value, hidden2: !!g('x2row').hidden,
           z0: +document.getElementById('pulse_design-z0').value,
           x1: { r: +g('xr').value, z: +g('xz').value },
           x2: { r: +g('xr2').value, z: +g('xz2').value } };
});
await setClass('dn');
const dn0 = await dnState();
//: ★one above the requested axis and one below — which is what 双零 MEANS.
//: Two nulls typed into the same half is two nulls and not a double null,
//: and the criterion below is what tells them apart.
ok('“double null” opens a second X-point row, above the axis and below it',
   dn0.hidden2 === false && dn0.x1.z < dn0.z0 && dn0.x2.z > dn0.z0
     && dn0.x1.r === uiSeed.r && dn0.x2.r === uiSeed.r
     && Math.abs(dn0.x1.z) === Math.abs(uiSeed.z)
     && Math.abs(dn0.x2.z) === Math.abs(uiSeed.z),
   JSON.stringify(dn0));

//: the START is where the kernel entry is: run through 场设计起始 so the
//: linear design is the thing being asked, and read what it achieved AT EACH
//: NULL — the single-null design cannot report a second one at all
const setStartMode = async (v) => {
  await page.evaluate((x) => {
    const e = document.getElementById('pulse_design-discharge-startmode');
    e.value = x; e.dispatchEvent(new Event('change'));
  }, v);
  await page.waitForTimeout(200);
};
await setStartMode('start');
const dSnl = await fromReference('lsn');
const snlStart = await page.evaluate(
  () => FyScenario.pages.pulse_design.bus.discharge().start);
const dDn = await fromReference('dn');
const dnStart = await page.evaluate(
  () => FyScenario.pages.pulse_design.bus.discharge().start);
ok('the start design accepts two field nulls and reports each of them',
   dnStart.nulls.length === 2 && snlStart.nulls.length === 1
     && dnStart.nulls.every((n) => isFinite(n.b) && isFinite(n.dpsi)),
   dnStart.nulls.map((n) => `(${n.r}, ${n.z}) |B| ${n.b.toExponential(3)} ` +
                            `dpsi ${n.dpsi.toFixed(4)}`).join(' · '));
//: ★and it HOLDS both.  A second row that was accepted and then abandoned
//: would satisfy "takes two" and not "designs a double null", so the test is
//: that neither null is worse than the single-null design's one null.
ok('and holds both of them as well as the single-null design holds its one',
   dnStart.nulls.every((n) => n.b <= 1.5 * snlStart.nulls[0].b)
     && Math.abs(dnStart.nulls[0].b - dnStart.nulls[1].b)
          <= 0.2 * Math.max(dnStart.nulls[0].b, dnStart.nulls[1].b),
   `|B| ${dnStart.nulls[0].b.toExponential(3)} / ` +
   `${dnStart.nulls[1].b.toExponential(3)} T against single null ` +
   `${snlStart.nulls[0].b.toExponential(3)} T`);
//: each on the BOUNDARY'S OWN flux surface — the row that makes a null a
//: divertor rather than a null somewhere in the machine
ok('and each of the two sits on the boundary’s own flux surface',
   dnStart.nulls.every((n) => Math.abs(n.dpsi)
                              <= 1.5 * Math.abs(snlStart.nulls[0].dpsi)),
   dnStart.nulls.map((n) => n.dpsi.toFixed(5)).join(' / ') +
   ` against ${snlStart.nulls[0].dpsi.toFixed(5)} Wb`);
ok('asking for two nulls is a different design from asking for one',
   dDn.chan.some((v, i) => Math.abs(v - dSnl.chan[i]) > 1e3),
   `PF1 ${(dSnl.chan[0] / 1e3).toFixed(1)} → ${(dDn.chan[0] / 1e3).toFixed(1)}` +
   ` kA·turn, err ${dSnl.err.toFixed(4)} → ${dDn.err.toFixed(4)}`);

const rowNulls = await critRow(/场零点行|Field-null rows/);
const rowLegsDn = await critRow(/打击点数|Strike points/);
const legNoteDn = await page.evaluate(
  () => document.getElementById('pulse_design-discharge-strike-verdict').innerText);
ok('the criteria table says the design carries an X-point row above and below',
   rowNulls.length === 3 && /^\s*1\s*\/\s*1\s*$/.test(rowNulls[1])
     && !/★/.test(rowNulls[2]),
   rowNulls.join(' | '));
//: ★TWO LEGS PER NULL.  The number used to be the constant 2 because one
//: null was all that could be asked for; a double null lands four.
const legsWantedDn = await page.evaluate(
  () => FyScenario.pages.pulse_design.bus.discharge().legsWanted);
ok('and the strike-point criterion then requires 4 legs',
   legsWantedDn === 4 && /\b4\b/.test(legNoteDn)
     && rowLegsDn.length === 3,
   `${rowLegsDn.join(' | ')} · ${legNoteDn.replace(/\s+/g, ' ').slice(0, 120)}`);

//: ★two nulls on the SAME side is not a double null, and the row that judges
//: it must say so — otherwise 「1 / 1」 above is a label, not a criterion
await page.evaluate(() => {
  const e = document.getElementById('pulse_design-discharge-xz2');
  e.value = '-1.20'; e.dispatchEvent(new Event('input'));
});
await page.waitForTimeout(300);
const rowNulls2 = await critRow(/场零点行|Field-null rows/);
ok('two nulls typed onto the same side are reported as not a double null',
   /^\s*0\s*\/\s*2\s*$/.test(rowNulls2[1]) && /★/.test(rowNulls2[2]),
   rowNulls2.join(' | '));
await setClass('dn');   // re-seed the pair

// ★the second null travels in the session file
const dnDoc = await dSave();
await setClass('limiter');
const backDn = await dImport(dnDoc);
const backDn2 = await dnState();
ok('the second field null round-trips through the session file',
   backDn.cls === 'dn' && backDn2.hidden2 === false
     && backDn2.x2.z === Math.abs(uiSeed.z)
     && dnDoc['fylite:config'].xz2 === Math.abs(uiSeed.z),
   `${JSON.stringify(backDn2.x1)} / ${JSON.stringify(backDn2.x2)}`);

// --- T-D7: gaps and strike points become TARGETS -----------------------------
// The page could report 「最小壁间隙 0.062 m」 and where the legs landed, and
// could target neither.  Both are now rows of the inverse solve — one isoflux
// row at a control point the WALL defines — and they go into BOTH sides of it,
// the linear start and every pass of the anneal.
await setStartMode('auto');
const ctlCount = async () => await page.evaluate(
  () => document.querySelectorAll('[data-ctldel]').length);
const addCtl = async (k) => {
  await page.click('#pulse_design-discharge-ctladd-' + k);
  await page.waitForTimeout(300);
};
const setCtl = async (id, v) => {
  await page.evaluate(([i, x]) => {
    const e = document.getElementById(i);
    e.value = x; e.dispatchEvent(new Event('input'));
    e.dispatchEvent(new Event('change'));
  }, [id, String(v)]);
  await page.waitForTimeout(200);
};
const shapeRowsNow = async () => await rows('pulse_design-discharge-shape');
//: one at a time: deleting a row re-renders the list, so a handle taken
//: before the click is a handle into a list that no longer exists
const clearCtl = async () => {
  for (let i = 0; i < 12; i++) {
    const n = await page.evaluate(() => {
      const b = document.querySelector('button.kfdel[data-ctldel]');
      if (!b) return 0;
      b.click();
      return 1;
    });
    await page.waitForTimeout(200);
    if (!n) break;
  }
};
const ctlGot = async () => await page.evaluate(
  () => FyScenario.pages.pulse_design.bus.discharge().criteria.control);

const before7 = (await shapeRowsNow()).length;
await addCtl('gap');
ok('a gap row can be added to the constraint set',
   await ctlCount() === 1, `${await ctlCount()} row(s)`);

// ★A ROW AT WEIGHT ZERO IS A MEASUREMENT, NOT A CONSTRAINT.  It is also the
// baseline every claim below is made against: the un-targeted gap on this
// ray, from a design that must be bit for bit the one with no row at all.
await setCtl('pulse_design-discharge-ctl0-wt', 0);
await setCtl('pulse_design-discharge-ctl0-val', 0.12);
const dW0 = await fromReference('limiter');
const gW0 = (await ctlGot())[0];
ok('a row at weight zero measures and does not constrain — bit-identical to no row',
   dW0.err === dLim1.err && dW0.q95 === dLim1.q95
     && dW0.chan.every((v, i) => v === dLim1.chan[i]),
   `err ${dW0.err} / ${dLim1.err} · q95 ${dW0.q95} / ${dLim1.q95} · ` +
   `PF1 ${dW0.chan[0]} / ${dLim1.chan[0]}`);
ok('and it reports the gap that ray actually has, measured to the wall it names',
   gW0.ok === true && isFinite(gW0.got) && gW0.got > 0
     && Math.abs(gW0.at[0] - 2.37) < 1e-6 && Math.abs(gW0.at[1]) < 1e-6,
   `ROG ${gW0.got.toFixed(5)} m to the wall at ` +
   `(${gW0.at[0].toFixed(3)}, ${gW0.at[1].toFixed(3)})`);

// ★AND THE ROW BITES, BOTH WAYS.  Ask for more clearance and get more, ask
// for less and get less — from the same baseline, so this is the constraint
// doing work rather than the anneal wandering.
await setCtl('pulse_design-discharge-ctl0-wt', 4);
await setCtl('pulse_design-discharge-ctl0-val', 0.20);
const dBig = await fromReference('limiter');
const gBig = (await ctlGot())[0];
await setCtl('pulse_design-discharge-ctl0-val', 0.02);
const dSml = await fromReference('limiter');
const gSml = (await ctlGot())[0];
//: ★Two-point monotonicity, not three (revised with T-D6′).  The
//: untargeted baseline's boundary is the FREE separatrix — the machine
//: solves diverted now — while both targeted runs bring the X-paired
//: control row in, which re-anchors the whole outboard flux; the three
//: numbers are no longer points on one constraint curve.  What must
//: hold is that the row steers monotonically: a larger ask yields a
//: larger solved gap than a smaller ask, by a margin a reader would
//: notice.
ok('asking for a larger gap solves a larger gap than asking for a smaller one',
   isFinite(gBig.got) && isFinite(gSml.got)
     && gBig.got > gSml.got + 0.02,
   `asked 0.020 → ${gSml.got.toFixed(5)} · untargeted ${gW0.got.toFixed(5)} · ` +
   `asked 0.200 → ${gBig.got.toFixed(5)} m`);
ok('and the design it took to do that is not the untargeted one',
   dBig.chan.some((v, i) => Math.abs(v - dW0.chan[i]) > 1e3)
     && dSml.chan.some((v, i) => Math.abs(v - dW0.chan[i]) > 1e3),
   `PF1 ${(dW0.chan[0] / 1e3).toFixed(1)} → ${(dSml.chan[0] / 1e3).toFixed(1)}` +
   ` / ${(dBig.chan[0] / 1e3).toFixed(1)} kA·turn`);
//: ★the same ray both times: a target and an achievement measured by two
//: pieces of geometry is how a 「目标 vs 实现」 row comes to compare a number
//: with itself
ok('the target and the achievement are read on the same ray',
   Math.abs(gBig.at[0] - gW0.at[0]) < 1e-9
     && Math.abs(gSml.at[0] - gW0.at[0]) < 1e-9,
   `wall point R ${gW0.at[0].toFixed(4)} in all three runs`);

// ★AND IT SHOWS UP WHERE A TARGET BELONGS: 「目标 vs 实现」.
const shp1 = await shapeRowsNow();
const gapRowT = shp1.find((r) => /间隙|Gap/.test(r[0])) || [];
ok('「目标 vs 实现」 grows the gap row, with what was asked and what was got',
   shp1.length === before7 + 1 && gapRowT.length === 4
     && Math.abs(parseFloat(gapRowT[1]) - 0.02) < 1e-9
     && Math.abs(parseFloat(gapRowT[2]) - gSml.got) < 5e-4,
   gapRowT.join(' | '));

// --- the strike-point row ---------------------------------------------------
await addCtl('strike');
await setCtl('pulse_design-discharge-ctl1-wt', 4);
const dStrk = await fromReference('limiter');
const gotAll = await ctlGot();
const sRow = gotAll[1];
//: ★which wall SEGMENT — the kernel snaps the request onto the wall and says
//: which one and how far it moved, so a request half a metre off the wall is
//: answered rather than silently relocated
const onWall = await page.evaluate((p) => {
  const w = self.FYLITE_MACHINE.limiter;
  let d = Infinity;
  for (let i = 0; i < w.r.length; i++) {
    const j = (i + 1) % w.r.length;
    const er = w.r[j] - w.r[i], ez = w.z[j] - w.z[i];
    const l2 = er * er + ez * ez;
    const t = l2 > 0 ? Math.max(0, Math.min(1,
      ((p[0] - w.r[i]) * er + (p[1] - w.z[i]) * ez) / l2)) : 0;
    d = Math.min(d, Math.hypot(p[0] - (w.r[i] + t * er),
                               p[1] - (w.z[i] + t * ez)));
  }
  return { d: d, n: w.r.length };
}, sRow.at);
ok('a strike-point row names a wall SEGMENT, and its point is on that wall',
   sRow.ok === true && Number.isInteger(sRow.seg) && sRow.seg >= 0
     && sRow.seg < onWall.n && onWall.d < 1e-6,
   `segment ${sRow.seg} of ${onWall.n}, ` +
   `(${sRow.at[0].toFixed(3)}, ${sRow.at[1].toFixed(3)}), ` +
   `${onWall.d.toExponential(1)} m off the wall`);
const shp2 = await shapeRowsNow();
const sRowT = shp2.find((r) => /打击点|Strike/.test(r[0])) || [];
//: ★judged by the distance from the nearest landing to the point it asked
//: for, whose target is zero — a row that reads 「found 1」 says nothing
//: about whether the leg went where it was sent
ok('and 「目标 vs 实现」 grows it too, targeted at zero miss distance',
   shp2.length === before7 + 2 && sRowT.length === 4
     && parseFloat(sRowT[1]) === 0
     && (dStrk.legs === 0 ? sRowT[2] === '—'
         : Math.abs(parseFloat(sRowT[2]) - sRow.got) < 5e-4),
   `${sRowT.join(' | ')}  (${dStrk.legs} landing(s))`);

// ★BOTH SIDES OF THE INVERSE SOLVE.  Everything above went through the
// ANNEAL — EAST has a reference discharge, so 自动 starts there and the
// linear design never runs.  The rows have to reach the START as well, or a
// machine without a reference shot would be designing to a different request
// than the one it was given.
await setStartMode('start');
const dStart7 = await fromReference('limiter');
const st7 = await page.evaluate(
  () => FyScenario.pages.pulse_design.bus.discharge().start);
ok('the linear start design carries the same rows the anneal does',
   st7.ctlRows.length === 2 && st7.ctlDpsi.length === 2
     && st7.ctlRows.every((r) => r.ok)
     && st7.ctlDpsi.every((v) => isFinite(v)),
   st7.ctlRows.map((r, i) => `${r.kind}@(${r.r.toFixed(2)}, ` +
     `${r.z.toFixed(2)}) dpsi ${st7.ctlDpsi[i].toFixed(4)}`).join(' · '));
await setStartMode('auto');

// ★the rows travel in the session file, and a file that carries no rows
// section is not a file asking for no rows — the pulse bar's rule, kept
const ctlDoc = await dSave();
await clearCtl();
ok('deleting the rows puts 「目标 vs 实现」 back to the six shape quantities',
   await ctlCount() === 0 && (await shapeRowsNow()).length === before7,
   `${(await shapeRowsNow()).length} rows`);
await dImport(ctlDoc);
const ctlBack7 = await page.evaluate(() => ({
  n: document.querySelectorAll('[data-ctldel]').length,
  val: document.getElementById('pulse_design-discharge-ctl0-val')
    ? +document.getElementById('pulse_design-discharge-ctl0-val').value : null,
  wt: document.getElementById('pulse_design-discharge-ctl0-wt')
    ? +document.getElementById('pulse_design-discharge-ctl0-wt').value : null,
  sr: document.getElementById('pulse_design-discharge-ctl1-pr')
    ? +document.getElementById('pulse_design-discharge-ctl1-pr').value : null,
}));
ok('the constraint set round-trips through the session file',
   ctlDoc['fylite:config']['fylite:shape_control'].length === 2
     && ctlBack7.n === 2 && ctlBack7.val === 0.02 && ctlBack7.wt === 4
     && Math.abs(ctlBack7.sr - sRow.at[0]) < 5e-3,
   JSON.stringify(ctlDoc['fylite:config']['fylite:shape_control']));
const noCtl = JSON.parse(JSON.stringify(ctlDoc));
delete noCtl['fylite:config']['fylite:shape_control'];
await dImport(noCtl);
ok('a file carrying no constraint section leaves the rows alone',
   await ctlCount() === 2, `${await ctlCount()} row(s)`);

// ★AND THE ONE THING NONE OF THIS MAY COST: the limiter design with no rows
// is still, after every widening above, the design this page gave before any
// of it existed.
await clearCtl();
const dLim3 = await fromReference('limiter');
ok('and with no nulls and no rows, 限制器 is still bit-identical to before',
   same(dLim1, dLim3),
   `err ${dLim1.err} / ${dLim3.err} · q95 ${dLim1.q95} / ${dLim3.q95} · ` +
   `PF1 ${dLim1.chan[0]} / ${dLim3.chan[0]}\n        ` +
   dWhy(dLim1['#controls'], dLim3['#controls']));

// ============================================================
// ★T-D6′ — the delivered p′/FF′ tier: the machine's own reference
// discharge, forward-solved, must come out DIVERTED.
//
// The entry blamed the analytic family; the measured root cause was the
// naive boundary rule's private-region misread (saddle at psi_N = 1.213
// on the converged field, 1.000 under the guard).  With the rule fixed
// (kernel v108) AND the delivered profiles available as a shape source,
// the shape bar must now solve EAST's own diverted shot — and the
// delivered tier must land nearer the delivered reconstruction
// (a = 0.440, R0 = 1.814, X = (1.606, −0.7215)) than the family does.
console.log('\n★T-D6′：交付 p′/FF′ 档——参考放电正解出偏滤器');
const setProfSrc = async (v) => page.evaluate((val) => {
  const el = document.getElementById('pulse_design-discharge-profsrc');
  el.value = val;
  el.dispatchEvent(new Event('change'));
}, v);
const referenceSolve = async () => {
  await page.click('#pulse_design-discharge-reset');
  for (let i = 0; i < 240; i++) {
    await page.waitForTimeout(250);
    if (!await page.evaluate(
      () => !!document.querySelector('.funcbar-run.stop'))) break;
  }
  await page.waitForTimeout(600);
  return await page.evaluate(() => {
    const d = FyScenario.pages.pulse_design.bus.discharge();
    const st = document.querySelector('[data-bar="discharge"] .funcbar-state');
    return d && { shape: d.shape, bnd: d.bndKind,
                  xpts: (d.criteria && d.criteria.xpts) || [],
                  status: st ? st.textContent : '' };
  });
};
await setClass('limiter');
await setProfSrc('analytic');
const refAna = await referenceSolve();
await setProfSrc('delivered');
const refDel = await referenceSolve();
ok('交付档：参考电流正解出 bndKind = 1（偏滤器）', refDel.bnd === 1,
   `bnd ${refDel.bnd}`);
ok('解析档在同一判据下也是偏滤器——判据修的是所有档',
   refAna.bnd === 1, `bnd ${refAna.bnd}`);
const xLow = refDel.xpts.slice().sort((a, b) => a.z - b.z)[0] || {};
ok('交付档的下 X 点落在交付重构的 X 点邻域 (1.606, −0.7215)',
   Math.abs(xLow.r - 1.606) < 0.08 && Math.abs(xLow.z + 0.7215) < 0.12,
   `X (${(xLow.r || NaN).toFixed(3)}, ${(xLow.z || NaN).toFixed(3)})`);
const dDel = Math.abs(refDel.shape.a - 0.440);
const dAna = Math.abs(refAna.shape.a - 0.440);
ok('交付档的 a 靠近交付重构的 0.440（±0.03）', dDel < 0.03,
   `a ${refDel.shape.a.toFixed(3)}`);
ok('且比解析族更近——族表达不了交付剖面（ψ_N≈0.82 变号）不是一句空话',
   dDel < dAna,
   `|Δa| 交付 ${dDel.toFixed(3)} < 解析 ${dAna.toFixed(3)}`);
ok('R0 靠近交付重构的 1.814（±0.03）',
   Math.abs(refDel.shape.r0 - 1.814) < 0.03,
   `R0 ${refDel.shape.r0.toFixed(3)}`);
//: ★the status line reports the KERNEL's verdict; on this shot the mask
//: quantisation-jitters and the honest word is 稳态, not a silent success
ok('状态行报的是内核的三分自报（达标/稳态），不是残差比较',
   /稳态|settled|达标|converged/.test(refDel.status),
   refDel.status.slice(0, 70));

//: and the tier is GATED on the machine actually carrying delivered
//: profiles — on ITER (no reference discharge) the option must be
//: disabled and the select must fall back to the analytic family.
await page.goto(BASE + 'pages/pulse_design.html?device=iter#configure',
                { waitUntil: 'networkidle' });
await page.waitForFunction(() => !!document.getElementById('pulse_design-discharge-profsrc'),
                           null, { timeout: 60000 });
await page.waitForTimeout(1500);
const iterOpt = await page.evaluate(() => {
  const el = document.getElementById('pulse_design-discharge-profsrc');
  const opt = el.querySelector('option[value="delivered"]');
  return { disabled: opt.disabled, value: el.value };
});
ok('无参考放电的装置上「交付」档不可选、选择器回到解析族',
   iterOpt.disabled && iterOpt.value === 'analytic',
   JSON.stringify(iterOpt));

// --- T-D14: the breakdown bar, reconnected ----------------------------------
// The pre-plasma field null, back on the page the discharge starts on.
// What is asserted is mostly REPORTING, exactly as for the other bars: the
// bar's verdict has to AGREE with its own numbers, the degenerate posing has
// to be refused by name, and the exported design has to carry what a reader
// needs to re-judge it (currents, the limits in force, who sat on them).
console.log('\n★T-D14：击穿场零——接回放电设计页');
//: still on the ITER page from the section above — the machine with no
//: reference discharge, which is exactly the machine the bias-to-reference
//: switch must be disabled on
const bdIter = await page.evaluate(() => {
  const el = document.getElementById('pulse_design-breakdown-usexref');
  return el && { disabled: el.disabled, checked: el.checked };
});
ok('无参考放电的装置上「偏向参考电流」不可勾', !!bdIter && bdIter.disabled &&
   !bdIter.checked, JSON.stringify(bdIter));

await page.goto(BASE + 'pages/pulse_design.html#configure', { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => [...document.querySelectorAll('[data-bar] .funcbar-state')]
    .some((e) => /就绪|Ready/.test(e.textContent)), null, { timeout: 180000 });
const bdStatus = await runBar('breakdown');
ok('运行后状态行给出达/未达判据与实测数字',
   /场零达判据|未达判据/.test(bdStatus) && /mT/.test(bdStatus),
   bdStatus.slice(0, 90));
const bd = await page.evaluate(() => {
  const d = FyScenario.pages.pulse_design.bus.breakdown();
  if (!d) return null;
  return { bMax: d.bMax, bTol: d.spec.bTol, converged: d.converged,
           n: d.aturns.length, flux: d.flux, fluxT: d.spec.fluxTarget,
           big: Math.max(...Array.from(d.aturns, Math.abs)),
           bind: Array.from(d.bind || []), over: Array.from(d.over || []),
           verdict: document.getElementById('pulse_design-breakdown-verdict')
             .textContent,
           coilRows: document.getElementById('pulse_design-breakdown-coils')
             .rows.length };
});
ok('有界求解收敛，且答案不是退化的全零电流',
   !!bd && bd.converged === true && bd.big > 1e3,
   bd && `max |I| ${(bd.big / 1e3).toFixed(1)} kA·匝`);
ok('通道表逐路一行，与装置的通道数一致', !!bd && bd.coilRows === bd.n,
   bd && `${bd.coilRows} 行 / ${bd.n} 通道`);
//: the verdict has to SAY what the numbers say — feasible iff the criterion
//: held, and it may not claim the bound was violated under a bounded solve
ok('可行性结论与它自己的数字一致（达标 ↔ 可行措辞）',
   !!bd && (bd.bMax <= bd.bTol) === /可行|Feasible/.test(bd.verdict) &&
   !/越上限/.test(bd.verdict),
   bd && `|B|max ${(bd.bMax * 1e3).toFixed(3)} mT vs 容差 ` +
   `${(bd.bTol * 1e3).toFixed(2)} mT · ${bd.verdict.slice(0, 40)}`);
ok('有界求解下没有越界通道（over 必须为空——非空说明投影失败）',
   !!bd && bd.over.length === 0, bd && `over ${JSON.stringify(bd.over)}`);
//: ★the degenerate posing is REFUSED BY NAME: "minimise |B|" with no flux
//: target and no reference bias is solved by switching every coil off, and
//: the bar must say that instead of dressing zeros up as a design.
//: (`setChk` flips WITHOUT the change event — the bar re-runs on every
//: change, and two flips plus the gate's own run key would be three racing
//: solves with the status read off whichever finished last)
const setChk = async (id, v) => page.evaluate(([i, val]) => {
  document.getElementById('pulse_design-breakdown-' + i).checked = val;
}, [id, v]);
await setChk('usefluxTarget', false);
await setChk('usexref', false);
const bdDeg = await runBar('breakdown');
ok('退化提法（不要磁通、不偏参考）被点名拒绝，而不是把全零报成设计',
   /退化|degenerate/.test(bdDeg), bdDeg.slice(0, 80));
await setChk('usefluxTarget', true);
await setChk('usexref', true);
//: switching the limits off must change the QUESTION being answered, and
//: the verdict must say which question it answered (`b.verdict.nolimit`)
await setChk('uselimits', false);
await runBar('breakdown');
const bdNoLim = await page.evaluate(() =>
  document.getElementById('pulse_design-breakdown-verdict').textContent);
ok('不加上限时结论换到「不限电流能做到多好」的措辞',
   /未加电流上限|No current limit/.test(bdNoLim), bdNoLim.slice(0, 60));
await setChk('uselimits', true);
await runBar('breakdown');
//: the exported design carries enough to be re-judged: the currents, the
//: limits actually in force, who sat on them, and the verdict scalars
{
  //: the export menu populates on first open — the item id exists only
  //: after `#pulse_design-ioexport` has been pressed once
  await page.click('#pulse_design-ioexport');
  const [d] = await Promise.all([page.waitForEvent('download'),
                                 page.click('#pulse_design-iofmt-breakdown-json')]);
  const doc = JSON.parse(readFileSync(await d.path(), 'utf8'));
  const r = doc['fylite:result'] || {};
  ok('会话文件：页名、逐路电流、生效上限、达标与否俱全',
     doc['fylite:page'] === 'breakdown' &&
     Array.isArray(r['fylite:pf_channel_current']) &&
     r['fylite:pf_channel_current'].length === bd.n &&
     Array.isArray(r['fylite:pf_channel_limit']) &&
     typeof r['fylite:null_ok'] === 'boolean',
     `${(r['fylite:pf_channel_current'] || []).length} 路 · ` +
     `null_ok ${r['fylite:null_ok']}`);
}

ok('no page errors', errs.length === 0, errs.join(' / ').slice(0, 200));
await br.close();
console.log(fails ? `\n${fails} FAILED` : '\nALL GREEN');
process.exit(fails ? 1 : 0);
