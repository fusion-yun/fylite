// 发出去的那一份，与仓里这一份是不是同一份（T-C5）。
//
// ★★这道闸子跑在**已发布的 URL** 上，不是本地服务器上。仓里的每一道其他闸子
// 判的都是「源对不对」；这一道判的是**发布**——两件不同的事，而 2026-08-24 那
// 张线上截图正是它们分开的那一天：功能栏的栏头没有横排、标题是浏览器默认大小、
// 折叠钮与计算键成了空蓝方块。
//
// ★**当时的结论是「新 HTML 配旧 CSS」，实测把它推翻了一半**：把公开仓
// `main` 那一版（`9add58d`，`chore: sync fylite/ from fylite@d756f0b`）原样起一个
// 静态服务、按 `/fylite/pages/model.html` 打开——栏头 `display: flex`、标题
// 15 px、折叠钮 14 px 描边、计算键 30 px 蓝底白三角、三张样式表 174 条规则全部
// 解析、控制台零报错。**`main` 上那一份是对的。**
//
// 差的不是内容，是**发布本身**：`.github/workflows/publish-app.yml` 是
// **`workflow_dispatch` 手动触发**（`push:` 那一段是**故意注释掉**的，见文件抬头
// 「MANUAL ONLY, deliberately」），所以 `main` 往前走**不会**自动发出去——线上那一
// 份是**上一次有人按下发布**时的那一份。这就是那张截图的成因，也是这道闸子存在的
// 理由：**「这次发对了」不是判据，「下次发错了会自己喊」才是。**
//
// 判三件事：
//   〔一〕**资产逐字节**：`assets/` 下每一个 css/js 的 sha256 与仓里的一致。
//         一个字节不同就说出是哪一个文件——「HTML 新了 CSS 旧了」这类错，
//         在这里是一行输出，不是一张截图。
//   〔二〕**算出来的样式**：栏头是 flex、折叠钮拿到 14 px 与描边、计算键是
//         30 px 蓝底白三角。〔一〕判的是字节，这一条判的是**读者看到的东西**
//         ——两者都要，因为字节相同而渲染不同（缓存、CDN、Jekyll 处理）也发生过。
//   〔三〕**页面自己不报错**。
//
//   node app/tests/validate-published.mjs [--site https://fusion-yun.github.io/fylite/]
//                                         [--playwright DIR]
//
// ★**取不到站点时它不判红，而是说清楚为什么**：出口被挡、站点还没发、离线跑闸
// ——这三种都不是「发布错了」，而一道在这些情况下判红的闸子，很快就会被人默认
// 忽略。退出码 3 是「没能判」，与 1（判红了）分开。

import { readFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { browser, flag } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const APP = HERE + '../';
const SITE = (flag('site', 'FYLITE_SITE')
              || 'https://fusion-yun.github.io/fylite/').replace(/\/*$/, '/');

let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};
const sha = (buf) => createHash('sha256').update(buf).digest('hex');

console.log(`已发布的那一份：${SITE}`);

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN',
                                  viewport: { width: 1134, height: 1000 } });
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  //: ★★`/api/*` 上的 404 **不是错误，是答案**（2026-09-05）：静态宿主没有请求面，页面据此
  //: 判断该走 wasm（`factsdb.js` / `kernelapi.js` 探的就是这件事——探「这条路答不答」，
  //: 不看主机名）。发布出去的站点不在回环地址上，一个探测也不发；本地静态服务器上那几条
  //: 404 是这套判别的正常足迹，不该让「页面没有报错」变红。
  if (m.type() === 'error' && !/favicon/.test(m.text())
      && !/\/api\//.test((m.location() && m.location().url) || ''))
    errs.push('console: ' + m.text().slice(0, 200));
});

let resp;
try {
  resp = await page.goto(SITE + 'pages/model.html',
                         { waitUntil: 'networkidle', timeout: 60000 });
} catch (e) {
  console.log(`  —   取不到站点（${String(e.message).slice(0, 90)}）`);
  console.log('      这不是「发布错了」：出口被挡 / 站点还没发 / 离线跑闸都会到这里。');
  console.log('      退出码 3 = 没能判，与 1 = 判红了分开。');
  await br.close();
  process.exit(3);
}
if (!resp || !resp.ok()) {
  console.log(`  —   站点回 HTTP ${resp ? resp.status() : '?'} —— 没能判（退出码 3）`);
  await br.close();
  process.exit(3);
}

// 〔一〕资产逐字节 ----------------------------------------------------------

console.log('\n〔一〕assets/ 下每一个 css/js 的 sha256');
const names = readdirSync(APP + 'assets')
  .filter((f) => /\.(css|js)$/.test(f)).sort();
let same = 0;
const drift = [];
for (const f of names) {
  const local = sha(readFileSync(APP + 'assets/' + f));
  let remote = null;
  try {
    const r = await page.request.get(SITE + 'assets/' + f);
    if (r.ok()) remote = sha(await r.body());
  } catch (e) { /* 下面按 remote === null 报 */ }
  if (remote === null) { drift.push(`${f}: 取不到`); continue; }
  if (remote === local) same += 1;
  else drift.push(`${f}: 线上 ${remote.slice(0, 12)} ≠ 仓里 ${local.slice(0, 12)}`);
}
say(drift.length === 0, `${names.length} 个资产逐字节相同`,
    drift.length ? `\n        ` + drift.join('\n        ') : `${same} 个`);
//: ★这一条红了，读的人要知道**下一步是什么**：不是改源，是**重新发布**
if (drift.length)
  console.log('        ↑ 差在发布，不在源：跑 publish-app.yml（workflow_dispatch）。');

// 〔二〕算出来的样式 --------------------------------------------------------

console.log('\n〔二〕读者看到的那一份');
await page.waitForFunction(
  () => document.querySelector('.funcbar-head'), null, { timeout: 60000 })
  .catch(() => {});
const seen = await page.evaluate(() => {
  const h = document.querySelector('.funcbar-head');
  const t = document.querySelector('.funcbar-title');
  const f = document.querySelector('.funcbar-fold');
  const fs = f && f.querySelector('svg');
  const r = document.querySelector('.funcbar-run');
  const rs = r && r.querySelector('svg');
  const cs = (e) => e ? getComputedStyle(e) : null;
  return {
    head: h ? cs(h).display : null,
    title: t ? cs(t).fontSize : null,
    fold: fs ? { w: fs.getBoundingClientRect().width, stroke: cs(fs).stroke,
                 fill: cs(fs).fill } : null,
    run: r ? { w: r.getBoundingClientRect().width, bg: cs(r).backgroundColor } : null,
    runSvg: rs ? { w: rs.getBoundingClientRect().width, fill: cs(rs).fill } : null,
    sheets: [...document.styleSheets].map((s) => {
      try { return (s.href || 'inline').split('/').pop() + ':' + s.cssRules.length; }
      catch (e) { return (s.href || 'inline') + ':BLOCKED'; }
    }),
  };
});
say(seen.head === 'flex', '栏头是横排（.funcbar-head display:flex）',
    String(seen.head));
say(seen.title === '15px', '栏标题是 15 px（不是浏览器默认的大标题）',
    String(seen.title));
say(!!seen.fold && Math.abs(seen.fold.w - 14) < 1 && seen.fold.fill === 'none',
    '折叠钮是 14 px 的描边人字（不是一个空方块）',
    seen.fold ? `${seen.fold.w}px · fill ${seen.fold.fill}` : '没有折叠钮');
say(!!seen.run && Math.abs(seen.run.w - 30) < 1
    && !!seen.runSvg && Math.abs(seen.runSvg.w - 15) < 1,
    '计算键是 30 px 蓝底、里面有 15 px 的白三角',
    seen.run ? `${seen.run.w}px · ${seen.run.bg} · svg ${seen.runSvg ? seen.runSvg.w : '—'}px` : '没有计算键');
say(seen.sheets.every((s) => !/BLOCKED|:0$/.test(s)),
    '每一张样式表都解析了（不是零条规则、不是跨域挡下）',
    seen.sheets.join(' · '));

// 〔三〕零报错 --------------------------------------------------------------

console.log('');
say(errs.length === 0, '线上那一页零报错', errs.join(' | ').slice(0, 200));

await br.close();
console.log(bad ? `\n✗ ${bad} 条不过 —— 发出去的与仓里的不是同一份` : '\n全部通过');
process.exit(bad ? 1 : 0);
