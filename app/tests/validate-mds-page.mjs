// Gate for the device-data page's LAYOUT and its SHOT BAR.
//
//   node app/tests/validate-mds-page.mjs [--playwright DIR] [--chrome BIN]
//
// ★It brings its own site.  `_site.mjs` serves `app/` off the disk, puts the
// SHIPPED request face (`fylite`) behind `/api/`, and gives that face a
// replayed mdsip server — so this gate needs no static server, no tunnel and
// no institute network, and everything between the page and the socket is the
// shipped code.
//
// ★★2026-09-01: the mdsip end is now **frames recorded off the real EAST
// server** (`fixtures/mdsip-east.json`), not a hand-written fake.  That change
// corrected a claim this gate had been making: the old fake modelled a GAP at
// #137983, and the real site has no such gap — #137982…#137985 all open.  The
// walk below therefore uses the case the machine really has: the counter's
// last written shot (#165704) with **nothing** at #165705.
//
// ★WHAT IT IS FOR.  Two of this page's claims are claims about a chain that
// no offline check reaches:
//
//   the GRID.  Six traces have to be readable at once, which is a statement
//   about pixels: how many columns, how tall each figure is, and whether the
//   six of them fit a screen.  A narrow screen must fall back to one column
//   whatever the reader selected, because two 300 px figures are two
//   unreadable ones.
//
//   the SHOT BAR.  `Latest` must land on `current_shot` — the one number the
//   page cannot compute — and `Prev`/`Next` must REPORT a shot number the site
//   never wrote instead of silently sitting on it.  The fake site is built so
//   that both are exercised: its counter has run past what was written, and
//   there is a gap between two written shots.

import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { fakeSite } from './_site.mjs';
import { haveFixture, FIXTURE_ABSENT } from './_mdsip-replay.mjs';

//: 录制那一刻站点的实况（`fixtures/mdsip-east.json`，2026-09-01）。
//: ★重录之后这两个数会变——它们是**录下来的机器状态**，不是本门挑的参数。
const LATEST = 165704;      // current_shot("east")，且这一炮是写下来了的
const UNWRITTEN = 165705;   // 站点还没写：TreeOpen 报 "cannot open east shot"
const SHOT = 137985;

//: ★夹具（那次录音）不在本仓时**跳过**：这道门量的就是「宿主对着真机答过的
//: 字节做了什么」，没有那些字节就没有可量的东西。
if (!haveFixture()) { console.log('SKIP —— ' + FIXTURE_ABSENT); process.exit(0); }

const OUT = mkdtempSync(join(tmpdir(), 'fylite-mds-'));

let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};

const site = await fakeSite();
const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  //: ★a 404 from `/api/signal` is not a page error, it is the answer.  This
  //: gate deliberately walks onto shot numbers the site never wrote, and the
  //: gateway reports those as 404s that the browser logs; what must stay empty
  //: is JS faults.
  if (m.type() === 'error' && !/favicon|Failed to load resource/.test(m.text()))
    errs.push('console: ' + m.text().slice(0, 200));
});

//: ★★不用 `networkidle` 等它：**页面装载时发的两个 `/api/health` 里有一个永远
//: 不落地**（浏览器侧一直挂着，服务端两条都答了、都发完了——旧栈 `gateway.mjs`
//: 上一模一样，所以这不是换宿主换出来的）。`networkidle` 于是永远等不到，30 s
//: 超时，而报出来的是「goto 超时」——**看不出真正的毛病是一个不落地的请求**。
//: 这里改成等页面自己说网关在，那个悬着的请求另记 TODO，别让它把这道门顶死。
//: `/api/` 在飞的请求；`apiQuiet` 据此判「安静」，掉队的那个不算数。
const inflight = new Map();
page.on('request', (r) => { if (/\/api\//.test(r.url())) inflight.set(r, Date.now()); });
const landed = (r) => inflight.delete(r);
page.on('requestfinished', landed);
page.on('requestfailed', landed);

/**
 * 等到 `/api/` 安静下来 —— `networkidle` 的替身（理由见上）。
 * ★超过 3 s 还没落地的请求算**掉队**，不再计入「在飞」：否则那一个不落地的
 * health 会让每一次等待都走满超时。
 */
async function apiQuiet(quietMs = 400, timeout = 25000) {
  const t0 = Date.now();
  let since = Date.now();
  for (;;) {
    const live = [...inflight.values()].filter((t) => Date.now() - t < 3000).length;
    if (live) since = Date.now();
    else if (Date.now() - since >= quietMs) return;
    if (Date.now() - t0 > timeout) return;
    await page.waitForTimeout(50);
  }
}

await page.goto(site.url + 'pages/data.html', { waitUntil: 'load' });
await page.waitForFunction(
  () => /mdsip|网关|gateway/i.test(document.getElementById('mds-gw')?.textContent || ''),
  null, { timeout: 20000 });
await page.waitForTimeout(300);

// --- helpers ---------------------------------------------------------------

const shotBox = () => page.$eval('#mds-shot', (e) => e.value);
const noteOf = (id) => page.$eval('#' + id, (e) => ({ text: e.textContent.trim(), warn: e.classList.contains('warn') }));
/**
 * Every figure as it is on screen.
 *
 * ★It re-reads until every live figure HAS a box.  A canvas measured in the
 * same tick it was appended in can still report a zero rect, and a gate that
 * took that reading would fail on layout timing rather than on layout — the
 * flake showed up as "six figures, none of them any pixels wide" one run in
 * three.  A figure that never gets a box outlasts the retries and is then
 * reported as it is, which is the failure this check is actually for.
 */
async function figures() {
  const read = () => page.$$eval('#mds-figs figure', (els) => els.map((f) => {
    const cv = f.querySelector('canvas');
    const box = cv ? cv.getBoundingClientRect() : null;
    return { dead: f.classList.contains('dead'),
             cap: (f.querySelector('figcaption') || {}).textContent || '',
             w: box ? Math.round(box.width) : 0, h: box ? Math.round(box.height) : 0 };
  }));
  for (let i = 0; i < 25; i++) {
    const got = await read();
    if (got.every((f) => f.dead || f.w > 0)) return got;
    await page.waitForTimeout(120);
  }
  return read();
}

/** The first drawn canvas and its box, queried fresh: `draw()` replaces the
 *  whole figure list, so a handle taken before the last redraw is detached and
 *  `boundingBox()` answers null. */
async function liveCanvas() {
  for (let i = 0; i < 20; i++) {
    const cvs = await page.$$('#mds-figs figure canvas');
    for (const cv of cvs) {
      //: ★scrolled into view FIRST, then measured.  `mouse.move` takes viewport
      //: coordinates and silently does nothing outside them, so a figure below
      //: the fold is a hover that never happens — which reads exactly like a
      //: readout that does not work.
      await cv.scrollIntoViewIfNeeded().catch(() => {});
      const box = await cv.boundingBox();
      const vp = page.viewportSize();
      if (box && box.width > 10 && box.y >= 0 && box.y + box.height <= vp.height)
        return { cv: cv, box: box };
    }
    await page.waitForTimeout(120);
  }
  throw new Error('没有一幅完整落在视口里的图可以指');
}

const gridCols = () => page.$eval('#mds-figs',
  (e) => getComputedStyle(e).gridTemplateColumns.split(' ').filter(Boolean).length);
/** The figure column, from the top of the first figure to the bottom of the last. */
const gridHeight = () => page.$eval('#mds-figs', (e) => Math.round(e.getBoundingClientRect().height));

/**
 * Do something that makes the page ask the gateway, and wait for the answer.
 *
 * ★NOT a wait on the status line.  A fetch is six serial round trips and the
 * status line from the PREVIOUS one is still on screen when the click lands —
 * a gate that waited for "some text and an enabled button" measured the old
 * fetch and passed on stale figures.  So it waits for the first `/api/`
 * response the action causes, then for the network to go quiet.
 */
async function act(fn) {
  const first = page.waitForResponse((r) => /\/api\//.test(r.url()), { timeout: 20000 })
    .catch(() => null);
  await fn();
  await first;
  await apiQuiet();
  await page.waitForTimeout(120);
}

/**
 * Wait until the fetch chain has actually FINISHED, and answer with its last
 * word.
 *
 * ★`act` waits for the network to go quiet, which is enough for a fetch of one
 * shot — but a window change now walks the current shot's two passes AND one
 * pass over every pinned trace (T-S8), and a gate that measured in the middle
 * of that read half-refetched figures.  The page says when it is done: the
 * status line stops saying `正在…` and reports what came back.
 */
async function settled() {
  for (let i = 0; i < 120; i++) {
    const t = await page.$eval('#mds-fetch-note', (e) => e.textContent.trim());
    if (/已取回|一路也没取到/.test(t)) { await page.waitForTimeout(120); return t; }
    await page.waitForTimeout(150);
  }
  return page.$eval('#mds-fetch-note', (e) => e.textContent.trim());
}

/** Pick exactly the six zero-order chips the page offers on the widest set. */
async function pickSix() {
  await page.$$eval('#mds-zero button', (bs) => {
    bs.forEach((b) => { if (b.classList.contains('on')) b.click(); });
  });
  await page.$$eval('#mds-zero button', (bs) => { bs.slice(0, 6).forEach((b) => b.click()); });
}

// --- 1. the chain is up ----------------------------------------------------

console.log('网关与首屏');
{
  const gw = await noteOf('mds-gw');
  say(!gw.warn && /127\.0\.0\.1/.test(gw.text), '页面找到了网关', gw.text.slice(0, 60));
  const trees = await page.$$eval('#mds-tree option', (os) => os.map((o) => o.value));
  say(trees.includes('pcs_east') && trees.includes('efit_east'),
      '树的清单来自网关', trees.join(' '));
}

await page.selectOption('#mds-tree', 'pcs_east');
await page.fill('#mds-shot', '137985');
await act(() => page.click('#mds-open'));

{
  const figs = await figures();
  say(figs.length >= 4 && figs.every((f) => !f.dead && f.w > 0),
      `#137985 打开后画出了 ${figs.length} 幅图`, figs.map((f) => f.w + 'x' + f.h).join(' '));
  say(figs.some((f) => /抽稀|全部/.test(f.cap)), '图注说了这条曲线是什么', figs[0] && figs[0].cap.slice(0, 48));
}

// --- 2. the grid -----------------------------------------------------------

console.log('\n面板网格');
await pickSix();
await act(() => page.click('#mds-fetch'));

{
  const figs = await figures();
  const cols = await gridCols();
  const h = await gridHeight();
  say(figs.length === 6, '六路信号都在图上', String(figs.length));
  say(cols === 2, '自适应把六幅图排成两列', `${cols} 列`);
  //: ★THE CLOSING CRITERION: six traces readable at once.  Readable is two
  //: measurements — the grid fits one screen (900 px viewport), and a figure
  //: is not so narrow that a flat top is a smear.
  say(h <= 900, '六幅图的版面在一屏之内', `${h} px ≤ 900 px`);
  say(figs.every((f) => f.w >= 300), '每幅图仍有可读的宽度',
      Math.min(...figs.map((f) => f.w)) + ' px');
  say(figs.every((f) => f.h === figs[0].h) && figs[0].h < 210,
      '两列时图高跟着列数缩', figs[0].h + ' px');
}

for (const n of [1, 3]) {
  await page.selectOption('#mds-cols', String(n));
  const cols = await gridCols();
  say(cols === n, `选 ${n} 列就是 ${n} 列`, `${cols} 列`);
}

{
  //: ★the narrow fallback is a RULE, not a preference: it must win over the
  //: reader's own selection, which is still 3 columns from the loop above.
  await page.setViewportSize({ width: 800, height: 900 });
  await page.waitForTimeout(120);
  const cols = await gridCols();
  const figs = await figures();
  say(cols === 1, '窄屏不论选了几列都退回单列', `${cols} 列`);
  say(figs.every((f) => f.w >= 300), '退回单列后每幅图仍读得出',
      Math.min(...figs.map((f) => f.w)) + ' px');
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.selectOption('#mds-cols', 'auto');
  await page.waitForTimeout(120);
}

// --- 3. Latest -------------------------------------------------------------

console.log('\n炮号导航');
await act(async () => {
  await page.click('#mds-latest');
  await page.waitForFunction((want) => document.getElementById('mds-shot').value === String(want),
                             LATEST, { timeout: 20000 }).catch(() => {});
});

{
  say((await shotBox()) === String(LATEST), '「最新」落到 current_shot 那一炮',
      `#${await shotBox()} vs #${LATEST}`);
  const note = await noteOf('mds-shot-note');
  say(/current_shot/.test(note.text), '状态行说得出这个数是哪里来的', note.text.slice(0, 70));
  const figs = await figures();
  say(figs.some((f) => !f.dead && f.w > 0), `#${LATEST} 有数，图画了出来`,
      `${figs.filter((f) => !f.dead).length}/${figs.length}`);
}

// --- 4. 走过站点写下的最后一炮 ---------------------------------------------
//
// ★★这一节从前叫「Prev / Next across a gap」，走的是假服务器里那个**编出来的**
// 空号 #137983。换成录制帧之后发现真机上根本没有那个空号（#137982…#137985 都开得
// 开），于是判据挪到机器真有的那一处：计数器停在 #165704，#165705 打不开。
// ★这不是把判据放松了——要看的行为一字未改：**踩到没有数的一炮时页面得报出来，
// 不能静默停着、也不能把上一炮的曲线留在屏幕上冒充这一炮**。

await act(() => page.click('#mds-next'));
{
  const figs = await figures();
  const fetchNote = await noteOf('mds-fetch-note');
  say((await shotBox()) === String(UNWRITTEN), '踩到没写下来的一炮时炮号停在那里，不静默跳过',
      await shotBox());
  say(fetchNote.warn, '取不到被报出来', fetchNote.text.slice(0, 60));
  say(figs.every((f) => f.dead), '上一炮的曲线没有留在屏幕上冒充这一炮',
      `${figs.filter((f) => f.dead).length}/${figs.length} 幅报错`);
  say(figs.every((f) => /取不到|cannot/.test(f.cap)), '每一幅图带着服务器自己的话',
      (figs[0] || {}).cap.slice(0, 70));
  const open = await noteOf('mds-open-note');
  const list = await noteOf('mds-list-note');
  say(open.warn && new RegExp(String(UNWRITTEN)).test(open.text),
      '树也说了它打不开这一炮，而不是停在「正在打开…」', open.text.slice(0, 60));
  say(list.warn && /%TREE|status|cannot open/.test(list.text), '拒绝的理由是服务器自己的话',
      list.text.slice(0, 70));
}

await act(() => page.click('#mds-prev'));
{
  const figs = await figures();
  say((await shotBox()) === String(LATEST) && figs.some((f) => !f.dead),
      '退回一格就又有数了', `#${await shotBox()}`);
}

await page.fill('#mds-shot', String(SHOT));
await act(() => page.click('#mds-open'));

await act(() => page.click('#mds-prev'));
{
  const figs = await figures();
  say((await shotBox()) === String(SHOT - 1), '「上一炮」走一格', await shotBox());
  say(figs.some((f) => !f.dead && f.w > 0), `#${SHOT - 1} 有数，图重新画了出来`,
      `${figs.filter((f) => !f.dead).length}/${figs.length}`);
}

await act(() => page.click('#mds-next'));
say((await shotBox()) === String(SHOT), '「下一炮」同样只走一格', await shotBox());

// --- 5. 多炮叠加（T-S3） ----------------------------------------------------

console.log('\n多炮叠加');
await page.fill('#mds-shot', String(SHOT));
await act(() => page.click('#mds-open'));
await page.click('#mds-pin');
await act(() => page.click('#mds-prev'));               // -> #137984, #137985 pinned

{
  const figs = await figures();
  const live = figs.filter((f) => !f.dead);
  say(live.length > 0 && live.every((f) => /#137984/.test(f.cap) && /#137985/.test(f.cap)),
      '同一幅图上两炮都在，且图注各自写着炮号',
      (live[0] || {}).cap.replace(/\s+/g, ' ').slice(0, 90));
  //: ★the two curves must be DIFFERENT data, not the same array drawn twice:
  //: the traces used to be keyed by (tree, node) alone, and the second shot
  //: silently overwrote the first while the legend claimed two.
  const rows = await page.$$eval('#mds-scalars tr', (trs) => trs.map(
    (tr) => [...tr.children].map((td) => td.textContent)));
  const shots = [...new Set(rows.map((r) => r[0]))].sort();
  say(shots.length === 2 && shots.includes('#137984') && shots.includes('#137985'),
      '读数表逐炮一行', shots.join(' '));
  const byShot = {};
  rows.forEach((r) => { byShot[r[0]] = (byShot[r[0]] || []).concat([r.slice(2).join('|')]); });
  say(JSON.stringify(byShot['#137984']) !== JSON.stringify(byShot['#137985']),
      '两炮的数是两份，不是同一份画了两遍');
}

// --- 5'. 缩放时钉住的那一炮跟着重取（T-S8） --------------------------------
//
// ★这是 T-S8 的关闭判据本身。2026-08-25 裁定走第二条路：钉住的那几炮在松手后按
// 新窗口**重取一次**（只一遍，不走 256 点那一遍）。判据因此是**同一幅图上两炮的
// 步长相同**——在这以前，缩放只细化当前那一炮，钉住的那一条仍是整炮的步长，
// 「放大真的变清晰」只兑现给其中一炮。
//
// ★步长本身不足以判死：两炮样点数相同时它们的窗口步长本来就会相等。所以同时看
// **钉住那一条的图注有没有自己的窗口行**——没有重取就没有窗口行，这一项是二值的。

console.log('\n缩放时钉住的那一炮（T-S8）');
{
  //: 图注是 `<br>` 分行的，textContent 会把几行黏成一行——所以按 innerHTML 拆。
  const capLines = () => page.$$eval('#mds-figs figure figcaption',
    (els) => els.map((c) => c.innerHTML.split(/<br\s*\/?>/i)
      .map((l) => l.replace(/<[^>]+>/g, '').trim()).filter(Boolean)));
  /** 每幅图里逐炮的 {步长, 有没有窗口行}；`全取` 就是步长 1。 */
  const perShot = async () => (await capLines()).map((lines) => {
    const out = {};
    for (const l of lines) {
      const who = /#(\d+)/.exec(l);
      if (!who) continue;
      const dec = /每 (\d+) 个取一个/.exec(l);
      out[who[1]] = { stride: dec ? Number(dec[1]) : 1, win: /窗口 = 第/.test(l) };
    }
    return out;
  });
  const both = (rows) => rows.filter((r) => Object.keys(r).length === 2);

  const before = both(await perShot());
  say(before.length > 0 && before.every((r) => Object.values(r).every((v) => !v.win)),
      '放大之前：两炮都还在整炮上', `${before.length} 幅图上有两炮`);

  const box = (await liveCanvas()).box;
  let calls = 0;
  const count = (r) => { if (/\/api\/signal/.test(r.url())) calls += 1; };
  page.on('request', count);
  await act(async () => {
    await page.mouse.move(box.x + box.width * 0.35, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2, { steps: 8 });
    await page.mouse.up();
  });
  const fetchNote = await settled();
  page.off('request', count);

  const after = both(await perShot());
  const picks = await page.$$eval('#mds-picked li', (els) => els.length);
  //: ★★「相同」放宽成「同一档」（差 ≤ 2 %）——2026-09-01，换成真机数据之后。
  //: 窗口是秒，落到样点上要按每条曲线**当前手里那一份**的时间轴去找下标，而两炮
  //: 手里的那一份细度不一样（一条刚按新窗口取回来，另一条是钉住的），于是同一个
  //: 时间窗算出的步长会差一两个：实测 `\VP1` 739 / 741（0.27 %）。★这不会把它要防
  //: 的那件事放过去：没重取的时候钉住那一炮停在整炮步长上，实测是 2484 对 739
  //: ——差 236 %，离这条界远得很。
  const sameStride = (r) => {
    const v = Object.values(r).map((x) => x.stride);
    return Math.abs(v[0] - v[1]) <= 0.02 * Math.max(v[0], v[1]);
  };
  say(after.length === before.length && after.every(sameStride),
      '★★放大之后同一幅图上两炮的步长同档（差 ≤ 2 %，T-S8 关闭判据）',
      after.map((r) => Object.values(r).map((v) => v.stride).join('/')).join(' '));
  say(after.every((r) => Object.values(r).every((v) => v.win)),
      '★钉住那一炮的图注也写出了自己的窗口——它真的按新窗口重取了',
      //: ★逐炮报出来：只说「6 幅图 × 2 炮」的话，红了也不知道是哪一炮少了窗口行。
      after.map((r) => Object.entries(r).map(([sh, v]) => `#${sh}${v.win ? '✓' : '✗'}`).join('/')).join(' '));
  //: 而且对两炮都真的变清晰了：本来就整取的（样点少于图宽）没有更细可言，所以
  //: 只对本来抽稀的那几路问这句。
  const sharper = after.every((r, i) => Object.entries(r).every(
    ([sh, v]) => !(before[i][sh] && before[i][sh].stride > 1) || v.stride < before[i][sh].stride));
  say(sharper, '★两炮的步长都塌下去了，不只是相等',
      before.map((r, i) => Object.keys(r).map(
        (sh) => `${r[sh].stride}→${after[i][sh].stride}`).join('/')).join(' '));
  //: ★代价是量出来的，不是估的：当前那一炮最多两遍（粗+细），钉住那一炮一遍。
  say(calls >= picks && calls <= picks * 3,
      '一次缩放的往返数在界内（当前炮 ≤ 2 遍 · 钉住的 1 遍）',
      `${calls} 次请求 / ${picks} 路 × 2 炮`);
  say(/钉住/.test(fetchNote) && /137985/.test(fetchNote),
      '★状态行说出了替钉住那一炮花掉的往返，不让读者从步长里推',
      fetchNote.slice(0, 60));
}

{
  //: ★不只是窗口会把两炮拉开：把**采样**调高，当前那一炮下一次取回就细化了，钉住那一条
  //: 若留在原处就是同一个缺陷换了个控件。判据仍是同一句——同一幅图上两炮同口径。
  const capLines = () => page.$$eval('#mds-figs figure figcaption',
    (els) => els.map((c) => c.innerHTML.split(/<br\s*\/?>/i)
      .map((l) => l.replace(/<[^>]+>/g, '').trim()).filter(Boolean)));
  const strides = async () => (await capLines()).map((ls) => ls.filter((l) => /#\d+/.test(l))
    .map((l) => { const d = /每 (\d+) 个取一个/.exec(l); return d ? Number(d[1]) : 1; }))
    .filter((v) => v.length === 2);

  const was = await strides();
  await page.selectOption('#mds-rate', '4096');
  await act(() => page.click('#mds-fetch'));
  const note = await settled();
  const now = await strides();
  say(now.length === was.length && now.every((v) => v[0] === v[1]),
      '★把采样调高之后两炮仍是同一口径（窗口不是唯一能把两炮拉开的控件）',
      was.map((v) => v.join('/')).join(' ') + ' → ' + now.map((v) => v.join('/')).join(' '));
  say(/钉住/.test(note) && /137985/.test(note),
      '★而且这一轮同样说出了替钉住那一炮花掉的往返', note.slice(0, 56));
  await page.selectOption('#mds-rate', 'auto');
}

{
  //: ★双击回到整炮，钉住那一炮也要跟着回来——否则它会停在窗口里，而图注说的是整炮。
  const cv = (await liveCanvas()).cv;
  await act(() => cv.dblclick({ force: true }));
  await settled();
  const capLines = () => page.$$eval('#mds-figs figure figcaption',
    (els) => els.map((c) => c.innerHTML.split(/<br\s*\/?>/i)
      .map((l) => l.replace(/<[^>]+>/g, '').trim()).filter(Boolean)));
  const rows = (await capLines()).filter((ls) => ls.filter((l) => /#\d+/.test(l)).length === 2);
  say(rows.length > 0 && rows.every((ls) => ls.every((l) => !/窗口 = 第/.test(l))),
      '★双击之后两炮一起回到整炮', `${rows.length} 幅图`);
}

{
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#mds-export')]);
  const f = join(OUT, 'overlay.json');
  await dl.saveAs(f);
  const doc = JSON.parse(readFileSync(f, 'utf8'));
  const shots = [...new Set(doc.signals.map((sg) => sg.shot))].sort();
  say(doc.signals.every((sg) => sg.shot != null) && shots.length === 2,
      '导出的 JSON 里每条信号带自己的炮号', shots.join(' '));
}

await page.click('#mds-unpin');
{
  const rows = await page.$$eval('#mds-scalars tr', (trs) => trs.length);
  const figs = await figures();
  say(figs.filter((f) => !f.dead).every((f) => !/#137985/.test(f.cap)),
      '「只留当前」之后钉住那一炮真的走了', `读数表 ${rows} 行`);
}

// --- 6. 状态行（T-S1） ------------------------------------------------------

console.log('\n状态行');
const stRows = () => page.$$eval('#mds-status .mds-st', (els) => els.map((e) => ({
  cls: e.className,
  k: e.querySelector('.k').textContent.trim(),
  v: e.querySelector('.v').textContent.trim(),
  w: e.querySelector('.w').textContent.trim(),
})));

{
  const rows = await stRows();
  say(rows.length === 6, '状态行六格', rows.map((r) => r.k).join(' / '));
  const shot = rows[0], ip = rows[1], pulse = rows[2], it = rows[3], bt = rows[4], date = rows[5];
  say(shot.v === '#137984' && /pcs_east/.test(shot.w), '炮号那一格说得出它自己从哪来', shot.v);
  say(/PCRL01/.test(ip.w) && /Rogowski/.test(ip.w) && ip.v !== '',
      'I_p 有值、点名节点，并重复了「它不是等离子体电流」', `${ip.v} · ${ip.w.slice(0, 40)}`);
  say(/PCRL01/.test(pulse.w) && /10 ?%/.test(pulse.w) && pulse.v !== '',
      '放电时长写明是推出来的，并写出推的规则', `${pulse.v} · ${pulse.w.slice(0, 46)}`);
  //: ★THE DATE IS A RECORD'S WRITE TIME, and the line has to say that: it is
  //: the one field a reader would otherwise take for the shot clock.
  say(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z$/.test(date.v), '日期这一格给出了一个日期', date.v);
  say(/TIME_INSERTED/.test(date.w) && /(写下来的时刻|record was written)/.test(date.w),
      '★并说明它是「记录写下来的时刻」，不是放电时刻', date.w.slice(0, 46));
  say(/TFP/.test(it.w), '★I_t 那一格点名了它查实的节点（值要等这一路取回来）',
      it.w.slice(0, 40));
  say(!/I<?t|It\b/.test(bt.k) && /环向场|toroidal/i.test(bt.k),
      'B_t 仍单列一格，不与 I_t 混为一谈', bt.k);
  const what = await page.$eval('[data-i18n="mds.status.what"]', (e) => e.textContent);
  say(/TFP/.test(what) && /TIME_INSERTED/.test(what) && /(B|环向场)/.test(what),
      '栏注写出这两格是怎么查实的，且 B_t 不是 I_t');
}

{
  //: ★the two fields that only lack a TRACE offer the pick that fills them.
  //: Six picks is the cap, so free two slots first — the point of the check is
  //: the offer and the value it produces, not the limit.
  for (const _ of [0, 1]) {
    await page.click('#mds-picked li:last-child button');
    await page.waitForTimeout(120);
  }
  const rowIdx = { it: 3, bt: 4 };
  for (const [name, idx] of Object.entries(rowIdx)) {
    const before = (await stRows())[idx];
    say(/missing/.test(before.cls) && /(TFP|BCENTR)/.test(before.w),
        `${name === 'it' ? 'I_t' : 'B_t'} 缺的是那一路没取，栏里点名了它`, before.w.slice(0, 46));
    const btn = await page.$(`#mds-status .mds-st:nth-child(${idx + 1}) button`);
    if (btn) await act(() => btn.click());
    const after = (await stRows())[idx];
    say(after.v !== '' && after.v !== '—' && /(TFP|BCENTR)/.test(after.w),
        `按「加进来」之后 ${name === 'it' ? 'I_t' : 'B_t'} 有了值与出处`,
        `${after.v} · ${after.w.slice(0, 36)}`);
  }
  //: and the units are the ones the tree gave, not a guess
  const rows = await stRows();
  say(/A$/.test(rows[3].v.trim()) && /T$/.test(rows[4].v.trim()),
      'I_t 是安培、B_t 是特斯拉，单位来自树', `${rows[3].v} / ${rows[4].v}`);
}

// --- 7. 悬停读数与拖动平移（T-S2） -----------------------------------------

console.log('\n图上交互');
{
  const box = (await liveCanvas()).box;
  let calls = 0;
  const count = (r) => { if (/\/api\//.test(r.url())) calls += 1; };
  page.on('request', count);
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await page.waitForTimeout(250);
  const read = await page.$eval('#mds-figs figure .mds-read',
    (e) => ({ hidden: e.hidden, text: e.textContent.trim() }));
  say(!read.hidden && /=/.test(read.text), '悬停给出读数', read.text.slice(0, 60));
  //: ★AND IT ASKS THE SERVER NOTHING.  A readout that fetched would turn
  //: moving the mouse into load on the site.
  say(calls === 0, '★悬停一次请求也不发', `${calls} 次`);
  page.off('request', count);
}

{
  //: a window first (drag), then slide it (shift-drag) — the same window and
  //: the same re-fetch, at a different offset
  const box = (await liveCanvas()).box;
  await act(async () => {
    await page.mouse.move(box.x + box.width * 0.35, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.55, box.y + box.height / 2, { steps: 8 });
    await page.mouse.up();
  });
  const win0 = await page.$eval('#mds-win-note', (e) => e.textContent.trim());
  say(/…/.test(win0), '框选给出了一个时间窗', win0.slice(0, 46));

  let calls = 0;
  const count = (r) => { if (/\/api\/signal/.test(r.url())) calls += 1; };
  page.on('request', count);
  await act(async () => {
    await page.keyboard.down('Shift');
    await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.4, box.y + box.height / 2, { steps: 8 });
    await page.mouse.up();
    await page.keyboard.up('Shift');
  });
  page.off('request', count);
  const win1 = await page.$eval('#mds-win-note', (e) => e.textContent.trim());
  say(win1 !== win0 && /…/.test(win1), 'Shift 拖动把窗口整体挪了位置', win1.slice(0, 46));
  const picks = await page.$$eval('#mds-picked li', (els) => els.length);
  say(calls > 0 && calls <= picks * 2,
      '平移恰好取回一轮（两遍取，最多每路两次）', `${calls} 次请求 / ${picks} 路`);
}

// --- 8. 存图与打印（T-S5） --------------------------------------------------

console.log('\n存图与打印');
{
  const cvBox = await liveCanvas();
  const fig = await cvBox.cv.evaluateHandle((c) => c.parentElement);
  const btn = await fig.asElement().$('.mds-png');
  const [dl] = await Promise.all([page.waitForEvent('download'), btn.click({ force: true })]);
  const f = join(OUT, 'fig.png');
  await dl.saveAs(f);
  const head = readFileSync(f).subarray(0, 8);
  say(head.equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])),
      '存出来的确实是一张 PNG', dl.suggestedFilename());
  //: ★the file name is the provenance that survives the download
  say(/pcs_east/.test(dl.suggestedFilename()) && /PCRL01/.test(dl.suggestedFilename())
      && /1379\d\d/.test(dl.suggestedFilename()),
      '文件名带树·节点·炮号', dl.suggestedFilename());
}

{
  await page.emulateMedia({ media: 'print' });
  await page.waitForTimeout(120);
  const print = await page.evaluate(() => ({
    apparatus: getComputedStyle(document.querySelector('#tool-mdsplus .layout > div')).display,
    cols: getComputedStyle(document.getElementById('mds-figs')).gridTemplateColumns
      .split(' ').filter(Boolean).length,
    caps: document.querySelectorAll('#mds-figs figcaption').length,
    png: getComputedStyle(document.querySelector('#mds-figs .mds-png')).display,
  }));
  say(print.apparatus === 'none', '打印时左边那一列控件不在', print.apparatus);
  say(print.cols === 1, '打印时图排成单列', `${print.cols} 列`);
  say(print.caps > 0, '★打印时图注还在——没有图注的曲线不再说自己是抽稀的', `${print.caps} 条`);
  say(print.png === 'none', '打印时按不了的按钮不出现在纸上', print.png);
  await page.emulateMedia({ media: 'screen' });
}

// --- 9. 工作区（T-S4） ------------------------------------------------------

console.log('\n工作区');
{
  await page.selectOption('#mds-cols', '3');
  //: ★the workspace worth testing has a PINNED shot that is not the current
  //: one, a window, and a layout — restoring it has to bring back a
  //: comparison, not just a shot number.
  await page.click('#mds-pin');                       // pin #137984
  await act(() => page.click('#mds-next'));           // -> #137985, #137984 pinned
  const b2 = (await liveCanvas()).box;
  await act(async () => {
    await page.mouse.move(b2.x + b2.width * 0.3, b2.y + b2.height / 2);
    await page.mouse.down();
    await page.mouse.move(b2.x + b2.width * 0.6, b2.y + b2.height / 2, { steps: 8 });
    await page.mouse.up();
  });
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#mds-ws-save')]);
  const f = join(OUT, 'ws.json');
  await dl.saveAs(f);
  const doc = JSON.parse(readFileSync(f, 'utf8'));
  say(doc['@type'] === 'fylite:MdsWorkspace/1', '工作区文件自报它是什么', doc['@type']);
  //: ★NOT ONE SAMPLE IN THE FILE.  A workspace carrying arrays would be the
  //: data copy the page's own boundary line says it does not make.
  const text = readFileSync(f, 'utf8');
  say(!/"data"|"time"\s*:\s*\[/.test(text) && text.length < 12000,
      '★文件里没有一个样点', `${text.length} 字节`);
  say(doc.picked.length > 0 && doc.cols === 3 && doc.shot === 137985
      && doc.window && doc.pinned.length === 1 && doc.server,
      '六项设定都在文件里', `${doc.picked.length} 路 · ${doc.cols} 列 · #${doc.shot}`
      + ` · 钉 ${doc.pinned.join()} · 窗 ${doc.window && Math.round(doc.window.x0 * 100) / 100}`);

  // 走开：换炮、换列数、去掉信号
  await page.selectOption('#mds-cols', '1');
  await act(() => page.click('#mds-next'));
  await page.click('#mds-clear');
  await page.waitForTimeout(150);

  await page.setInputFiles('#mds-ws-file', f);
  await page.waitForFunction(() => document.getElementById('mds-shot').value === '137985',
                             null, { timeout: 20000 }).catch(() => {});
  await apiQuiet();
  await page.waitForTimeout(400);
  const back = await page.evaluate(() => ({
    shot: document.getElementById('mds-shot').value,
    cols: document.getElementById('mds-cols').value,
    picks: [...document.querySelectorAll('#mds-picked code')].map((c) => c.textContent),
    win: document.getElementById('mds-win-note').textContent.trim(),
    pins: [...document.querySelectorAll('#mds-pins button')].map((b) => b.textContent.trim()),
  }));
  say(back.shot === String(doc.shot), '读回来落在文件里那一炮', back.shot);
  say(back.cols === '3', '列数跟着回来', back.cols);
  say(back.picks.length === doc.picked.length, '选中的信号逐条回来',
      `${back.picks.length}/${doc.picked.length}`);
  say(/…/.test(back.win), '时间窗跟着回来', back.win.slice(0, 46));
  say(back.pins.length === 1 && /137984/.test(back.pins.join(' ')),
      '钉住的那一炮也回来了（重新取回来的，不是文件里存的数）', back.pins.join(' '));
  const figs = await figures();
  const live = figs.filter((f) => !f.dead);
  say(live.length > 0, '读回来之后图是画出来的，不是一屏空框', `${live.length}/${figs.length}`);
  say(live.some((f) => /#137984/.test(f.cap) && /#137985/.test(f.cap)),
      '★读回来的是那一份对比：两炮都在同一幅图上',
      (live[0] || {}).cap.replace(/\s+/g, ' ').slice(0, 80));
}

// --- 10. no page errors ----------------------------------------------------

say(errs.length === 0, '整轮没有页面报错', errs.slice(0, 2).join(' | '));

await br.close();
//: ★★命不中＝这一趟问了夹具里没有的问题。回放器答不出的那一条会变成一幅报错
//: 的图，症状看起来像页面坏了——所以先把它自己说出来。重录：
//:   node tools/mds-record.mjs --server <站点> --port 8210 --out app/tests/fixtures/mdsip-east.json
//:   FYLITE_MDSIP_LIVE=127.0.0.1:8210 node app/tests/validate-mds-page.mjs …
say(site.misses.length === 0, `回放全部命中（${site.seen.length} 次问答）`,
    site.misses.length
      ? `${site.misses.length} 条命不中：` + site.misses.slice(0, 8).map((m) => `[${m.ctx}] ${m.expr}`).join(' · ')
      : '');

await site.close();

console.log(bad ? `\nFAILED (${bad})` : '\nPASS');
process.exit(bad ? 1 : 0);
