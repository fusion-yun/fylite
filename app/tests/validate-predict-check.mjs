// The edge back OUT of the modelling scenario: a predicted pressure profile
// taken by the reconstruction bar as its kinetic constraint.
//
// ★★2026-09-01: the carrier changed. There used to be a one-click
// 「交给反演场景」 button (a `localStorage` handoff bus); it was withdrawn, and
// with it the receiving panel on the analysis page — that panel only accepted
// `kind === 'profile'` and had no second source, so it could never have
// received anything again. **The edge itself is untouched**: the same document
// leaves through the export menu and enters through the import button, applied
// by the same `FORMATS.profile.apply`. This gate now drives that path, which is
// also the path that works between two machines.
//
// ★★Why this edge and not another.  Every other edge on this site runs INTO
// the modelling page — an operating point from design, a g-file from either
// of the other two — so a prediction could be admired and never checked.
// What the analysis page takes as a kinetic constraint is a pressure profile
// on a uniform psi_N grid, which is exactly what a march produces; with that
// edge in place a prediction can be reconstructed against real magnetics.
//
// ★What the gate is really guarding is the GAP AT THE EDGE.  The metric
// ladder stops at psi_N = 0.95, so the march has no answer between there and
// the separatrix.  The document is written to 1.0 with the last solved value
// HELD across the gap, and both facts travel as fields.  A future version
// that extrapolated a gradient into that gap instead — inventing the one
// feature this bar does not model — would still produce a smooth, plausible,
// wrong constraint, and this is the check that would see it.
//
//   node app/tests/validate-predict-check.mjs [--playwright DIR] [--url BASE]

import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'fylite-predict-'));
let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad += 1;
};

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN',
                                  viewport: { width: 1440, height: 1100 } });
if (!await seedDevice(ctx, 'east')) {
  console.error(missingDeviceMessage('east'));
  process.exit(2);
}
const errs = [];
const watch = (p) => {
  p.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
  p.on('console', (m) => {
    //: ★★`/api/*` 上的 404 **不是错误，是答案**（2026-09-05）：静态宿主没有请求面，页面据此
    //: 判断该走 wasm（`factsdb.js` / `kernelapi.js` 探的就是这件事——探「这条路答不答」，
    //: 不看主机名）。发布出去的站点不在回环地址上，一个探测也不发；本地静态服务器上那几条
    //: 404 是这套判别的正常足迹，不该让「页面没有报错」变红。
    if (m.type() === 'error' && !/favicon/.test(m.text())
        && !/\/api\//.test((m.location() && m.location().url) || ''))
      errs.push('console: ' + m.text().slice(0, 200));
  });
};

// --- the march, and the file it writes -------------------------------------

const model = await ctx.newPage();
watch(model);
await model.goto(BASE + 'pages/model.html?device=east',
                 { waitUntil: 'networkidle' });
//: ★★等**留得住的信号**，不等状态行（2026-09-05 真浏览器实测改）。这里从前等的是
//: 状态行里出现「就绪 / Ready」，而那句话在页面上只存在一瞬：各栏的初始状态紧接着把它
//: 换成自己的（实测 0.49 s 时已是「待机——摆好目标，合开关起放电」，`status.kernel_ready`
//: 在 MutationObserver 里一次痕迹也没留下）。于是这一等就是 180 秒的超时，而**页面本身
//: 一直是好的**——`FyDesignReady` 与 `FYLITE_KERNEL` 都按时到位。状态行是给读者看的：
//: 它会改词、会被覆盖、还随语言变，判据挂在它上面就是把闸子挂在措辞上。
await model.waitForFunction(() => !!self.FYLITE_KERNEL, null, { timeout: 180000 });

/** 从导出菜单里存一份文件下来；没有下载就回 null。 */
async function exportPressure(name) {
  await model.click('#model-ioexport');
  const d = await Promise.all([
    model.waitForEvent('download', { timeout: 15000 }).catch(() => null),
    model.click('#model-iofmt-evolve-pressure'),
  ]).then((r) => r[0]);
  if (!d) return null;
  const f = join(OUT, name);
  await d.saveAs(f);
  return f;
}

console.log('建模页 · 推进并导出');
//: ★nothing to write before there is a march, and the page must SAY so
//: rather than write an empty document
const early = await exportPressure('early.json');
const earlyNote = await model.evaluate(() =>
  document.getElementById('model-status').textContent || '');
say(early === null, '还没跑过就没有文件可导', String(early).slice(0, 40));
say(/没有|尚未|none|nothing/i.test(earlyNote), '而且页面说了为什么',
    earlyNote.replace(/\s+/g, ' ').slice(0, 50));

//: a short march on the bar's own defaults.
//: ★2026-08-31 起这里不再选算例：随页面发的「算例菜单」那一批已经撤了
//: （语料只住在 `cases/`，页面不取），`#model-evolve-case` 这个控件不存在
//: 了。本门要的是**这一栏跑一次**，跑的是哪一个算例不影响它问的那几件事
//: （文档的形状、解到哪里、那以外是不是平推）。
await model.evaluate(() => {
  const n = document.getElementById('model-evolve-nsteps');
  n.value = 20; n.dispatchEvent(new Event('input'));
});
await model.click('#model-evolve-run');
await model.waitForFunction(
  () => /完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 600000 });

const file = await exportPressure('pressure.json');
say(!!file, '推进之后导得出一份剖面文件');
const doc = file ? JSON.parse(readFileSync(file, 'utf8')) : {};
const p = doc['fylite:pressure'] || [];
say(doc['fylite:page'] === 'profile'
    && doc['fylite:pressure_grid'] === 'uniform_psi_normalised',
    '是反演页读得懂的那份文档',
    `${doc['fylite:page']} · ${doc['fylite:pressure_grid']}`);
//: ★the provenance is the whole point of carrying one: a prediction that
//: came back in as data would be a measurement nobody made
say(doc['fylite:provenance'] === 'model-evolve-prediction',
    '出处说明这是一条预测', doc['fylite:provenance']);
say(p.length > 5 && p.every((v) => isFinite(v) && v > 0),
    '压强是一条有限的正剖面', `${p.length} 点`);
say(p[0] > p[p.length - 1], '压强从轴向外下降',
    `${p[0].toExponential(3)} → ${p[p.length - 1].toExponential(3)} Pa`);

//: ★★THE GAP.  Everything at or beyond the solved edge must be the last
//: solved value, exactly — a held value, not an extrapolated one.
const solved = doc['fylite:psi_norm_solved'];
say(typeof solved === 'number' && solved > 0 && solved < 1,
    '文件说出了它解到哪里', String(solved));
say(doc['fylite:beyond_solved'] === 'held', '也说出了那以外是平推的',
    doc['fylite:beyond_solved']);
const n = p.length;
const tail = [];
for (let i = 0; i < n; i++) if (i / (n - 1) >= solved) tail.push(p[i]);
say(tail.length > 0 && tail.every((v) => v === tail[tail.length - 1]),
    '解不到的那一段确实是同一个值，不是外推出来的',
    `${tail.length} 点 · ${tail.length ? tail[0].toExponential(3) : ''} Pa`);

// --- the far side ----------------------------------------------------------

console.log('\n反演页 · 导入');
const analysis = await ctx.newPage();
watch(analysis);
await analysis.goto(BASE + 'pages/analysis.html?device=east',
                    { waitUntil: 'networkidle' });
await analysis.waitForFunction(
  () => /就绪|Ready/i.test(
    document.getElementById('analysis-status').textContent || ''),
  null, { timeout: 180000 });

//: ★nothing is applied until the file comes in.  The constraint's own switch
//: ships ticked and its note carries the default prose, so what says "nothing
//: has been applied" is that neither the file nor its provenance is named yet.
const before = await analysis.evaluate(() =>
  (document.getElementById('reconstruction-kin-note') || {}).textContent || '');
say(!/model-evolve-prediction|fylite_model_pressure/.test(before),
    '导入之前什么也没动', before.slice(0, 40));

if (file) {
  const [chooser] = await Promise.all([analysis.waitForEvent('filechooser'),
                                       analysis.click('#analysis-ioimport')]);
  await chooser.setFiles(file);
  await analysis.waitForFunction(
    () => /剖面|profile|失败|Failed/i.test(
      document.getElementById('analysis-status').textContent || ''),
    null, { timeout: 60000 });
}
const after = await analysis.evaluate(() => ({
  kin: document.getElementById('reconstruction-kin').checked,
  note: (document.getElementById('reconstruction-kin-note') || {})
          .textContent || '',
}));
say(after.kin === true, '导入之后动理学约束是开着的');
say(/model-evolve-prediction/.test(after.note),
    '页面上写着这条约束的出处', after.note.replace(/\s+/g, ' ').slice(0, 80));

await br.close();
if (errs.length) { console.log('\n页面报错：'); errs.forEach((e) => console.log('  ' + e)); }
console.log(bad || errs.length ? `\n★ ${bad} 项未过` : '\n全部通过');
process.exit(bad || errs.length ? 1 : 0);
