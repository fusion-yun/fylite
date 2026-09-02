// The v2 shell pages — `pages/page_*.html`.
//
//   node app/tests/validate-page-v2.mjs [--playwright DIR] [--chrome BIN]
//
// Four pages under the shared two-row strip (`FYL-DESIGN-11` V-11 / V-12,
// `FYL-DESIGN-10` P-25 / P-26), generated from the four originals by
// `tools/make-page-v2.mjs`.  What has to stay true, in order of how much it
// would cost to get wrong:
//
//   〔一〕THE BODY IS THE ORIGINAL'S.  This is the whole basis for calling the
//   new pages functionally complete: they are not a second implementation,
//   they are the same markup under a different strip.  Asserted by re-running
//   the generator and comparing — the same shape as `make-app-pages --check`.
//
//   〔二〕THE ORIGINALS ARE UNTOUCHED.  `shell.css` and `shell.js` are inert
//   without `data-fy-shell="v2"`, and the four originals must not carry it.
//   The point of keeping both sets is having a control to measure against;
//   a control that has quietly been changed is not one.
//
//   〔三〕ONE OUTPUT ABOVE THE FOLD (P-26).  Measured at 1600 x 900 — the
//   desktop's own default measure (V-13).  This is the claim the whole
//   exercise is for, and it is the one that decays silently: a panel that
//   grows by 80 px moves the first figure below the fold and nothing else
//   changes.  Needs a browser; skipped with a loud line when there is none.
//
// ★Assertion counts are printed and asserted non-empty.  A gate whose
// selector matches nothing reports every check it did not do as passing —
// that failure has been found in this repository twice.

import { existsSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { flag } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const APP = HERE + '../';
const IDS = ['pulse_design', 'model', 'analysis', 'data'];

let bad = 0;
const ok = (m) => console.log('  ok   ' + m);
const fail = (m) => { console.log('  FAIL ' + m); bad++; };

// --- 〔一〕 the body is the original's ---------------------------------------
console.log('〔一〕这四页是原页面加一条外壳，不是第二份实现');
try {
  execFileSync(process.execPath, [APP + '../tools/make-page-v2.mjs', '--check'],
               { stdio: 'pipe' });
  ok(`${IDS.length} 页与 tools/make-page-v2.mjs 一致（正文逐字取自原页面）`);
} catch (e) {
  fail('生成物已漂移：' + String(e.stdout || e.message).trim().split('\n').pop());
}

// --- 〔二〕 the strip is there, and only here --------------------------------
console.log('\n〔二〕外壳在新页面上，且四张原页面一字未动');
let checked = 0;
for (const id of IDS) {
  const f = `pages/page_${id}.html`;
  if (!existsSync(APP + f)) { fail(`${f} 不在`); continue; }
  const s = readFileSync(APP + f, 'utf8');
  checked++;
  if (!/<body[^>]*data-fy-shell="v2"/.test(s))
    fail(`${f}: 没有 data-fy-shell="v2" —— shell.css / shell.js 对它全部失效`);
  if (!/<header class="shell"/.test(s)) fail(`${f}: 没有 header.shell`);
  if (/<header class="top"/.test(s)) fail(`${f}: 还留着旧的 header.top`);
  //: matched as a TAG, not as a substring: the comment above the tag contains
  //: the same filename, and a page that lost the tag but kept the comment
  //: would otherwise pass
  for (const a of ['shell.css', 'shell.js']) {
    const re = a.endsWith('.css')
      ? new RegExp(`<link[^>]+href="[^"]*assets/${a.replace('.', '\\.')}"`)
      : new RegExp(`<script[^>]+src="[^"]*assets/${a.replace('.', '\\.')}"`);
    if (!re.test(s)) fail(`${f}: 没有载入 assets/${a}`);
  }
  //: the three slots exist as empty hosts; shell.js fills them by MOVING the
  //: page's own controls in
  for (const cls of ['shell-r1', 'shell-r2', 'shell-in', 'shell-state',
                     'shell-exit', 'shell-prog'])
    if (!s.includes(`class="${cls}"`)) fail(`${f}: 外壳缺 .${cls}`);
  //: the heading is the SOURCE page's own — the data page is a tool page and
  //: `site.js render()` never fills a `data-line-h1` for it
  const src = readFileSync(APP + `pages/${id}.html`, 'utf8');
  const titles = (src.match(/<div class="titles">[\s\S]*?<\/div>/) || [''])[0]
    .replace(/\s+/g, ' ');
  const mine = (s.match(/<div class="titles">[\s\S]*?<\/div>/) || [''])[0]
    .replace(/\s+/g, ' ');
  if (!titles || titles !== mine)
    fail(`${f}: 抬头不是原页面那一份（原「${titles.slice(0, 40)}…」）`);
}
if (!checked) fail('一个 v2 页面也没检查到 —— 这一节等于没跑');
else ok(`${checked} 张新页面各带完整外壳`);

let clean = 0;
for (const id of IDS) {
  const s = readFileSync(APP + `pages/${id}.html`, 'utf8');
  if (/data-fy-shell/.test(s)) fail(`pages/${id}.html 被打上了 v2 标记 —— 它是对照组`);
  else if (/shell\.(js|css)/.test(s)) fail(`pages/${id}.html 载入了 shell 资源`);
  else clean++;
}
if (clean !== IDS.length) fail(`只有 ${clean}/${IDS.length} 张原页面是干净的`);
else ok(`${clean} 张原页面未被触碰（对照组仍然成立）`);

// --- 〔三〕 one output above the fold ----------------------------------------
console.log('\n〔三〕16:9 首屏（1600 × 900）之内至少一处输出');
if (!flag('playwright', 'PLAYWRIGHT_PATH')) {
  console.log('  跳过 —— 用 --playwright <装有 playwright 的目录> 或设 $PLAYWRIGHT_PATH');
} else {
  const { browser } = await import('./_browser.mjs');
  const { fakeSite } = await import('./_site.mjs');
  const site = await fakeSite();
  const br = await browser();
  const ctx = await br.newContext({ viewport: { width: 1600, height: 900 } });
  let seen = 0;
  for (const id of IDS) {
    const pg = await ctx.newPage();
    const errs = [];
    pg.on('pageerror', (e) => errs.push(String(e)));
    //: `site.url` already ends in `/` — a second one makes `//pages/…`
    await pg.goto(`${site.url}pages/page_${id}.html`,
                  { waitUntil: 'domcontentloaded' });
    await pg.waitForTimeout(6000);
    const r = await pg.evaluate(() => {
      const shell = document.querySelector('header.shell');
      const box = document.getElementById('shell-empty');
      const live = [...document.querySelectorAll('canvas, table')]
        .filter((e) => e.getBoundingClientRect().height > 40);
      const y = (e) => Math.round(e.getBoundingClientRect().y + scrollY);
      const cands = [];
      if (live.length) cands.push(y(live[0]));
      //: ★an EMPTY STATE counts, and that is deliberate: `FYL-DESIGN-13` P-10
      //: says a page with nothing to show names the missing step rather than
      //: drawing a blank, and a box with axes and that sentence is an output
      //: in the only sense this assertion cares about — the reader learns what
      //: this page will draw and what has to happen first.
      if (box && !box.hidden && box.getBoundingClientRect().height > 40)
        cands.push(y(box));
      return {
        sticky: shell ? getComputedStyle(shell).position : null,
        h: shell ? Math.round(shell.getBoundingClientRect().height) : null,
        nav: document.querySelectorAll('header.shell nav a.navic').length,
        theme: !!document.querySelector('header.shell #theme-toggle'),
        leftover: document.querySelectorAll('main .panel.toolbar').length,
        first: cands.length ? Math.min(...cands) : null,
      };
    });
    await pg.close();
    seen++;
    if (errs.length) fail(`page_${id}: ${errs.length} 个 pageerror —— ${errs[0]}`);
    if (r.sticky !== 'sticky') fail(`page_${id}: 外壳不是 sticky（${r.sticky}）`);
    if (r.nav !== 4) fail(`page_${id}: 外壳上有 ${r.nav} 枚页面图标，应为 4`);
    if (!r.theme) fail(`page_${id}: 主题开关不在外壳上`);
    if (r.leftover) fail(`page_${id}: 正文里还留着 ${r.leftover} 条工具条 —— 没搬干净`);
    if (r.first === null) fail(`page_${id}: 整页找不到一处输出，连空态图也没有`);
    else if (r.first >= 900)
      fail(`page_${id}: 首处输出在 ${r.first} px，落在 16:9 首屏之外（P-26）`);
    else ok(`page_${id}: 外壳 ${r.h} px · 首处输出 ${r.first} px`);
  }
  if (!seen) fail('一页也没在浏览器里跑到 —— 这一节等于没跑');
  await br.close();
  await site.close();
}

console.log('');
if (bad) { console.log(`FAILED (${bad})`); process.exit(1); }
console.log('PASS');
