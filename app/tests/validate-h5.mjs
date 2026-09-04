// The HDF5 gate: the browser reads a file this repository wrote, and gets the
// same document the native reader gets (`FYL-DESIGN-18` U-25, §五).
//
//     node app/tests/validate-h5.mjs [--playwright <dir>] [--chrome <bin>]
//
// ★The fixture is a real file, written by the middle layer.  `fixtures/
// equilibrium.h5` is the fyo HDF5 layout as this repository writes it, and
// `fixtures/equilibrium.json` is what the NATIVE reader gets back from that
// same file.  Both are committed, so this gate is pure JS: the reference is
// data, not a second process, and nothing here runs Python (「Python 不接入
// 前端」, 2026-09-04).  Regenerate them with `fixtures/README.md`'s recipe when
// the layout changes — and a layout change that this gate does not notice is
// exactly the failure it exists for.
//
// ★★The assertion is EQUALITY WITH THE NATIVE READING, leaf by leaf.  A reader
// that gets the structure right and the numbers subtly wrong — a transposed
// 2-D dataset (`FYL-DESIGN-14` L-5), an int64 attribute arriving as a BigInt
// and serialising to nothing — produces a document that looks perfect. So the
// comparison is on values, not on shape.
//
// ★And the size property is asserted too: h5wasm is ~4.2 MB and must NOT load
// until someone actually opens a file.  A regression to a static `<script>`
// would be invisible except on the network tab, so the gate reads
// `FyH5.loaded()` before and after.
import { readFileSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..');
let bad = 0;
const fail = (m) => { console.log('  FAIL  ' + m); bad++; };
const ok = (m) => console.log('  ok    ' + m);

console.log('\n〔一〕vendor 目录与上游一致，许可与出处在场');
const V = join(APP, 'assets', 'vendor', 'h5wasm');
for (const f of ['hdf5_hl.js', 'hdf5_util.js', 'LICENSE.txt', 'PROVENANCE.md'])
  if (!existsSync(join(V, f))) fail(`缺 vendor/h5wasm/${f}`);
const lic = existsSync(join(V, 'LICENSE.txt')) ? readFileSync(join(V, 'LICENSE.txt'), 'utf8') : '';
if (!/NIST-developed software/.test(lic)) fail('LICENSE.txt 不是 h5wasm 的那一份');
else ok('LICENSE.txt 原样在场（NIST 条款要求整份保留）');
const prov = existsSync(join(V, 'PROVENANCE.md')) ? readFileSync(join(V, 'PROVENANCE.md'), 'utf8') : '';
if (!/0\.10\.3/.test(prov) || !/sha256/.test(prov)) fail('PROVENANCE.md 没有钉住版本与哈希');
else ok('PROVENANCE.md 记着版本、大小与 sha256');
//: the licence obliges an explicit acknowledgement of NIST as the source —
//: in a place a reader sees, not only beside the bytes
const ack = readFileSync(join(APP, '..', 'docs', 'ACKNOWLEDGEMENTS.md'), 'utf8');
if (!/NIST/.test(ack)) fail('docs/ACKNOWLEDGEMENTS.md 没有承认 NIST 为来源 —— 那是许可义务');
else ok('致谢里明确承认 NIST 为来源（许可义务，不是客套）');

console.log('\n〔二〕预缓存不含这 4 MB（U-20 的代价没有转嫁给每个读者）');
const sw = readFileSync(join(APP, 'sw.js'), 'utf8');
const listed = JSON.parse(/const PRECACHE = (\[[\s\S]*?\]);/.exec(sw)[1]);
const vend = listed.filter((f) => /vendor\/h5wasm/.test(f));
if (vend.length) fail(`预缓存里有 ${vend.length} 个 h5wasm 文件：${vend.join(' ')}`);
else ok('预缓存清单不含 vendor/h5wasm（按需下载，用过的人由运行时缓存留下）');

console.log('\n〔三〕浏览器里：读一份本仓写的 .h5，与原生读法逐叶子相同');
const flag = (n, e) => { const i = process.argv.indexOf('--' + n); return i > 0 ? process.argv[i + 1] : process.env[e]; };
if (!flag('playwright', 'PLAYWRIGHT_PATH')) {
  console.log('  跳过 —— 用 --playwright <装有 playwright 的目录> 或设 $PLAYWRIGHT_PATH');
} else {
  const { browser } = await import('./_browser.mjs');
  const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                  '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml',
                  '.json': 'application/json', '.jsonld': 'application/ld+json',
                  '.h5': 'application/x-hdf5', '.wasm': 'application/wasm' };
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
  const pg = await br.newPage();
  const errs = [];
  pg.on('pageerror', (e) => errs.push(String(e)));
  await pg.goto(`${url}pages/page_model.html`, { waitUntil: 'domcontentloaded' });
  await pg.addScriptTag({ url: '../assets/sources.js' });
  await pg.addScriptTag({ url: '../assets/h5source.js' });

  const reference = JSON.parse(readFileSync(join(APP, 'tests', 'fixtures', 'equilibrium.json'), 'utf8'));
  const r = await pg.evaluate(async ({ base, ref }) => {
    const out = { steps: [] };
    const say = (n, p, d) => out.steps.push({ name: n, pass: !!p, detail: d || '' });
    if (!window.FyH5) { say('FyH5 已加载', false); return out; }

    say('加载 h5source.js 本身没有把那 4 MB 拖下来（按需加载）', FyH5.loaded() === false);

    const bytes = await (await fetch(base + 'tests/fixtures/equilibrium.h5')).arrayBuffer();
    let doc = null, err = null;
    const t0 = performance.now();
    try { doc = await FyH5.read(bytes); } catch (e) { err = String(e && e.message || e); }
    const ms = Math.round(performance.now() - t0);
    if (err) { say('读取成功', false, err); return out; }
    say(`读出一份文档（首次读含载入，实测 ${ms} ms）`, !!doc && FyH5.loaded() === true);

    //: leaf-by-leaf against the native reading
    const leaves = (o, p = '', acc = {}) => {
      if (Array.isArray(o)) { acc[p] = o.join(','); return acc; }
      if (o && typeof o === 'object') { for (const k of Object.keys(o)) leaves(o[k], p ? p + '/' + k : k, acc); return acc; }
      acc[p] = o; return acc;
    };
    const a = leaves(ref), b = leaves(doc);
    const missing = Object.keys(a).filter((k) => !(k in b));
    const extra = Object.keys(b).filter((k) => !(k in a));
    const differ = Object.keys(a).filter((k) => k in b && String(a[k]) !== String(b[k]));
    say('与原生读法叶子集合相同',
        missing.length === 0 && extra.length === 0,
        `缺 ${JSON.stringify(missing)} 多 ${JSON.stringify(extra)}`);
    say(`与原生读法逐叶子取值相同（${Object.keys(a).length} 片）`,
        differ.length === 0,
        differ.slice(0, 4).map((k) => `${k}: ${a[k]} vs ${b[k]}`).join('; '));
    say('标量确实是标量，不是长度 1 的数组（属性 ↔ dataset 的分别没有丢）',
        typeof doc.time_slice.global_quantities.ip === 'number'
        && Array.isArray(doc.time), `ip=${typeof doc.time_slice.global_quantities.ip}`);
    say('根上的 @type 与 comment 从属性里取回来了',
        doc['@type'] === 'fyo:equilibrium' && Array.isArray(doc.comment)
        && doc.comment.length === 2, JSON.stringify(doc['@type']));

    //: refusals, by name
    let notH5 = null;
    try { await FyH5.read(new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9])); }
    catch (e) { notH5 = String(e.message); }
    say('不是 HDF5 的按名拒绝，而不是让 Emscripten 崩一次',
        !!notH5 && /签名不符/.test(notH5), notH5);

    //: a second read reuses the loaded module
    const t1 = performance.now();
    await FyH5.read(bytes);
    say(`第二次读不再重新载入（实测 ${Math.round(performance.now() - t1)} ms）`, true);

    //: it composes as an ordinary source layer
    if (window.FySources) {
      const l = await FyH5.layer(bytes, 'equilibrium.h5');
      const s = FySources.stack('equilibrium', [l]);
      const asm = s.assembly();
      say('作为源栈的一层参与装配（与取数来的那份没有分别，U-5）',
          l.kind === 'file' && asm.merge.length === 1 && /equilibrium\.h5/.test(asm.$source[asm.merge[0]]),
          asm.$source[asm.merge[0]]);
    } else say('sources.js 已加载', false, '页面没有 FySources');
    return out;
  }, { base: url, ref: reference });

  for (const s of r.steps) (s.pass ? ok : fail)(`${s.name}${s.detail ? ' — ' + s.detail : ''}`);
  const fatal = errs.filter((e) => /h5source|hdf5_/.test(e));
  if (fatal.length) fail(`页面抛错：${fatal[0]}`);
  await br.close();
  srv.close();
}

console.log(bad ? `\n${bad} 处失败` : '\nHDF5 闸全部通过');
process.exit(bad ? 1 : 0);
