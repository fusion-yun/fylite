// The form gate: a function page's controls come from its vocabulary, and
// from nowhere else (`FYL-DESIGN-18` U-1 / U-2; NR-QUAL-007 first clause).
//
//     node app/tests/validate-form.mjs [--playwright <dir>] [--chrome <bin>]
//
// Three sections, checked IN BOTH DIRECTIONS (the `-10` G-14 lesson — a
// one-way check is a permanent exemption for whichever side it does not read):
//
//   〔一〕the page is mounts only.  `pages/<page>.html` carries no `<input>` and
//        no `<select>`; every `[data-form="x"]` names a vocabulary entry, and
//        every vocabulary entry has exactly one mount.  Ids are unique and
//        carry the page prefix; each `kind` carries the fields its markup needs.
//   〔二〕the generated page is the source page plus the strip, still — the v2
//        page carries the same mounts, so what 〔一〕 proved holds on both.
//   〔三〕in a browser, every entry became exactly one element of the right tag
//        with the vocabulary's own min / max / step / value, its readout span
//        exists, no mount is left over, none is marked missing, and the values
//        `FySession.collect` reads back are the vocabulary's defaults.
//
// ★The browser section does not need the `fy` executable: the page's controls
// exist before any worker or kernel answers, so a plain static server over
// `app/` is enough (and is all this file runs).
import { readFileSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';
import { createContext, runInContext } from 'node:vm';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..');
const PAGES = ['model'];

let bad = 0;
const fail = (m) => { console.log('  FAIL  ' + m); bad++; };
const ok = (m) => console.log('  ok    ' + m);

/** The vocabulary, evaluated the way the browser evaluates it. */
function vocabOf(page) {
  const src = readFileSync(join(APP, 'assets', `vocab-${page}.js`), 'utf8');
  //: in a browser `window` IS the global; give the sandbox the same shape
  const g = {}; g.window = g;
  const ctx = createContext(g);
  runInContext(src, ctx);
  return g.FyVocab[page];
}

const NEEDS = {
  range: ['id', 'min', 'max', 'step', 'readout'],
  select: ['id', 'i18n', 'choices'],
  checkbox: ['id', 'i18n'],
};

for (const page of PAGES) {
  console.log(`\n〔一〕pages/${page}.html 只有挂点；词表与挂点一一对应`);
  const V = vocabOf(page);
  const html = readFileSync(join(APP, 'pages', `${page}.html`), 'utf8');
  const stray = html.match(/<(input|select)\b[^>]*>/g) || [];
  if (stray.length) fail(`${stray.length} 个手写控件仍在页面里：${stray.slice(0, 3).join(' ')}`);
  else ok('页面里没有手写的 <input> / <select>');

  const mounts = [...html.matchAll(/data-form="([^"]+)"/g)].map((m) => m[1]);
  const names = V.params.map((p) => p.name);
  const dupN = names.filter((n, i) => names.indexOf(n) !== i);
  const dupM = mounts.filter((n, i) => mounts.indexOf(n) !== i);
  if (dupN.length) fail(`词表里重复的名字：${dupN}`);
  if (dupM.length) fail(`页面里重复的挂点：${dupM}`);
  const noEntry = mounts.filter((m) => !names.includes(m));
  const noMount = names.filter((n) => !mounts.includes(n));
  if (noEntry.length) fail(`挂点没有词表条目：${noEntry}`);
  if (noMount.length) fail(`词表条目没有挂点：${noMount}`);
  if (!noEntry.length && !noMount.length && !dupN.length && !dupM.length)
    ok(`${names.length} 条词表条目 ↔ ${mounts.length} 个挂点，双向一一对应`);

  const ids = new Set();
  for (const p of V.params) {
    if (!p.id.startsWith(`${page}-`)) fail(`${p.name}: id ${p.id} 不带页前缀`);
    if (p.id !== `${page}-${p.name}`) fail(`${p.name}: id ${p.id} 与名字不对应`);
    if (ids.has(p.id)) fail(`重复 id ${p.id}`);
    ids.add(p.id);
    for (const k of NEEDS[p.kind] || ['kind']) if (p[k] === undefined) fail(`${p.name}: ${p.kind} 缺 ${k}`);
    if (!NEEDS[p.kind]) fail(`${p.name}: 未知的 kind ${p.kind}`);
    if (p.kind === 'range') {
      if (!(p.min < p.max)) fail(`${p.name}: min ${p.min} ≥ max ${p.max}`);
      if (p.value !== undefined && (p.value < p.min || p.value > p.max))
        fail(`${p.name}: 默认值 ${p.value} 在 [${p.min}, ${p.max}] 之外`);
      if (!p.readout.startsWith(`${page}-`)) fail(`${p.name}: 读数 id ${p.readout} 不带页前缀`);
      //: ★an off-grid default is snapped by the browser and never read back as
      //: written — a default nothing runs is not a default (found on `width`)
      if (p.value !== undefined && Math.abs(((p.value - p.min) / p.step) % 1) > 1e-6
          && Math.abs(((p.value - p.min) / p.step) % 1 - 1) > 1e-6)
        fail(`${p.name}: 默认值 ${p.value} 不在 min + k·step 的格上，浏览器会吸附到别处`);
    }
    if (!p.i18n && !p.label_id) fail(`${p.name}: 既无 i18n 键也无控制器填的标签 id`);
  }
  //: the U-2 table: one kind, one parameter type
  const TYPE = { range: ['double', 'integer'], select: ['enum'], checkbox: ['boolean'] };
  const off = V.params.filter((p) => !(TYPE[p.kind] || []).includes(p.type));
  if (off.length) fail(`kind ↔ type 不合 U-2：${off.map((p) => `${p.name}(${p.kind}/${p.type})`)}`);
  else ok('每条的 kind 与 type 合 U-2 的映射表');
  const tbd = V.params.filter((p) => p.iri === '[TBD]').length;
  console.log(`  note  ${tbd}/${V.params.length} 条的 IRI 仍是 [TBD]（G-1：控制词表今天不在内核 code 表里）`);

  console.log(`\n〔二〕pages/page_${page}.html 带同一组挂点`);
  const v2 = join(APP, 'pages', `page_${page}.html`);
  if (!existsSync(v2)) fail(`没有 ${v2}`);
  else {
    const s2 = readFileSync(v2, 'utf8');
    const m2 = [...s2.matchAll(/data-form="([^"]+)"/g)].map((m) => m[1]);
    if (String(m2) !== String(mounts)) fail('v2 页面的挂点与原页面不同——重跑 tools/make-page-v2.mjs');
    else ok(`${m2.length} 个挂点相同`);
    if (!/<script src="\.\.\/assets\/vocab-model\.js"><\/script>\s*<script src="\.\.\/assets\/form\.js"><\/script>/.test(s2)
        || !/assets\/form\.js"><\/script>[\s\S]*assets\/scenario\.js"><\/script>/.test(s2))
      fail('vocab-*.js / form.js 不在 scenario.js 之前，或没有紧挨着');
    else ok('vocab-model.js → form.js → … → scenario.js 的次序成立');
  }
}

// --- 〔三〕 in the browser -----------------------------------------------------
console.log('\n〔三〕浏览器里：每条词表条目恰成一个元素，属性与默认值是词表的');
const flag = (name, env) => { const i = process.argv.indexOf('--' + name); return i > 0 ? process.argv[i + 1] : process.env[env]; };
if (!flag('playwright', 'PLAYWRIGHT_PATH')) {
  console.log('  跳过 —— 用 --playwright <装有 playwright 的目录> 或设 $PLAYWRIGHT_PATH');
} else {
  const { browser } = await import('./_browser.mjs');
  const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.jsonld': 'application/ld+json',
                  '.svg': 'image/svg+xml', '.wasm': 'application/wasm' };
  const srv = createServer((req, res) => {
    const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (p.split('/').includes('..')) { res.writeHead(400).end(); return; }
    const f = join(APP, p);
    if (!existsSync(f)) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'content-type': TYPES[extname(f)] || 'application/octet-stream' });
    res.end(readFileSync(f));
  });
  await new Promise((r) => srv.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${srv.address().port}/`;
  const br = await browser();
  const ctx = await br.newContext({ viewport: { width: 1600, height: 900 } });
  for (const page of PAGES) {
    const V = vocabOf(page);
    for (const f of [`${page}.html`, `page_${page}.html`]) {
      const pg = await ctx.newPage();
      const errs = [];
      pg.on('pageerror', (e) => errs.push(String(e)));
      await pg.goto(`${url}pages/${f}`, { waitUntil: 'domcontentloaded' });
      const r = await pg.evaluate((params) => {
        const out = { left: document.querySelectorAll('[data-form]').length,
                      missing: document.querySelectorAll('[data-form-missing]').length,
                      mounted: window.FyForm && FyForm.mounted, wrong: [] };
        for (const p of params) {
          const els = document.querySelectorAll('#' + CSS.escape(p.id));
          if (els.length !== 1) { out.wrong.push(`${p.name}: ${els.length} 个元素`); continue; }
          const el = els[0];
          const tag = { range: 'INPUT', select: 'SELECT', checkbox: 'INPUT' }[p.kind];
          if (el.tagName !== tag) out.wrong.push(`${p.name}: ${el.tagName}`);
          if (p.kind === 'range') {
            for (const k of ['min', 'max', 'step'])
              if (+el.getAttribute(k) !== p[k]) out.wrong.push(`${p.name}.${k}=${el.getAttribute(k)}≠${p[k]}`);
            if (p.value !== undefined && +el.value !== p.value) out.wrong.push(`${p.name}.value=${el.value}≠${p.value}`);
            if (!document.getElementById(p.readout)) out.wrong.push(`${p.name}: 无读数 #${p.readout}`);
            if (!el.closest('.ctl')) out.wrong.push(`${p.name}: 不在 .ctl 里`);
          }
          if (p.kind === 'select' && el.options.length !== p.choices.length)
            out.wrong.push(`${p.name}: ${el.options.length} 项 ≠ ${p.choices.length}`);
          if (p.kind === 'checkbox' && el.checked !== !!p.checked) out.wrong.push(`${p.name}.checked=${el.checked}`);
          const lab = p.label_id ? document.getElementById(p.label_id)
                                 : el.closest('.ctl, label').querySelector(`[data-i18n="${p.i18n}"]`);
          if (!lab) out.wrong.push(`${p.name}: 标签没有 ${p.label_id || p.i18n}`);
        }
        //: the session layer reads the same ids
        if (window.FySession) {
          const ids = params.filter((p) => p.kind === 'range').map((p) => p.id);
          const got = FySession.collect(ids, document);
          for (const p of params)
            if (p.kind === 'range' && p.value !== undefined && got[p.id] !== p.value)
              out.wrong.push(`${p.name}: collect → ${got[p.id]}`);
        } else out.wrong.push('FySession 未加载');
        return out;
      }, V.params);
      const fatal = errs.filter((e) => /form\.js|vocab-/.test(e));
      if (fatal.length) fail(`${f}: form.js 抛错：${fatal[0]}`);
      if (r.left) fail(`${f}: ${r.left} 个挂点没被替换`);
      if (r.missing) fail(`${f}: ${r.missing} 个挂点标为缺条目`);
      if (r.mounted !== V.params.length) fail(`${f}: FyForm.mounted=${r.mounted} ≠ ${V.params.length}`);
      if (r.wrong.length) fail(`${f}: ${r.wrong.length} 处不符：${r.wrong.slice(0, 5).join('; ')}`);
      if (!r.left && !r.missing && !r.wrong.length && r.mounted === V.params.length)
        ok(`${f}: ${V.params.length} 个控件与词表逐条相符，FySession.collect 读回默认值`);
      await pg.close();
    }
  }
  await br.close();
  srv.close();
}

console.log(bad ? `\n${bad} 处失败` : '\n表单闸全部通过');
process.exit(bad ? 1 : 0);
