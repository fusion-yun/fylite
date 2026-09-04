// The source-stack gate: the page orders, the middle layer merges, and the
// order the page drew is the order that won (`FYL-DESIGN-18` U-5 · U-6 · U-7,
// §五).
//
//     node app/tests/validate-sources.mjs [--playwright <dir>] [--chrome <bin>]
//
// ★★WHAT THIS GATE MAY NOT DO, and why it once did it.  An earlier version
// handed the document the page writes to `fylite.io.fydoc.assemble` — the
// middle layer through its PYTHON binding — and asserted the merge came out
// top-row-first.  That is not this gate's to assert.  **Python is not in the
// front end's path** (user ruling, 2026-09-04): the browser's middle layer is
// `fylite_runtime` compiled to wasm (`FYL-DESIGN-16` H-4, phase W-1), and that
// door does not exist yet — measured, see G-15: the crate builds for wasm32 and
// exports NOTHING, because `c_api` and `assembly` are both behind the `mdsip`
// feature that the wasm tier switches off.  Having another host perform the
// operation and reporting the answer as the front end's makes a path that is
// missing look like a path that works.
//
// ★The distinction against the seventeen gates here that DO run Python: those
// compare — the browser computes an answer, `python/fylite` computes the same
// answer independently, and the gate holds the two together (对拍, the shape
// `README.md` describes and `U-12` requires).  Comparing two implementations is
// not the same as borrowing one.
//
// ★So this gate asserts what the front end is responsible for: the ORDER the
// stack draws, the document it writes, and that the document matches the
// contract `rust/fylite_runtime/src/assembly.rs` states in its own header.
// Whether that document merges correctly is the middle layer's to prove, on its
// own side, and the browser's to re-prove once it has a door.
import { readFileSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..');
const ROOT = join(APP, '..');
let bad = 0;
const fail = (m) => { console.log('  FAIL  ' + m); bad++; };
const ok = (m) => console.log('  ok    ' + m);

console.log('\n〔一〕页面不合并（U-5：合并只在中间层做一次）');
const src = readFileSync(join(APP, 'assets', 'sources.js'), 'utf8');
const code = src.replace(/\/\*[\s\S]*?\*\//g, '').split('\n')
  .map((l) => l.replace(/(^|\s)\/\/.*$/, '')).join('\n');
if (/function\s+merge\s*\(|Object\.assign\(.*doc/.test(code))
  fail('sources.js 里有自己的合并实现 —— D-3：合成只在一处');
else ok('sources.js 只排次序与开关，不合并');
if (!/\.reverse\(\)/.test(code)) fail('assembly() 没有把栈序倒过来写 merge —— 优先级会反');
else ok('merge 按栈序倒写（栈顶优先 ↔ merge 末位优先）');
if (!/basis: 'derived'/.test(code)) fail('逐量出处没有标出它是页面推出来的（G-14）');
else ok('逐量出处标为 derived，不冒充中间层记下的');

console.log('\n〔二〕浏览器里写出装配文档，交给真的中间层执行');
const flag = (n, e) => { const i = process.argv.indexOf('--' + n); return i > 0 ? process.argv[i + 1] : process.env[e]; };
if (!flag('playwright', 'PLAYWRIGHT_PATH')) {
  console.log('  跳过 —— 用 --playwright <装有 playwright 的目录> 或设 $PLAYWRIGHT_PATH');
} else {
  const { browser } = await import('./_browser.mjs');
  const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                  '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml',
                  '.json': 'application/json', '.jsonld': 'application/ld+json' };
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

  const r = await pg.evaluate(() => {
    const out = { steps: [], asm: null, asmSwapped: null, topAlias: null };
    const say = (n, p, d) => out.steps.push({ name: n, pass: !!p, detail: d || '' });
    if (!window.FySources) { say('FySources 已加载', false); return out; }

    //: two sources that overlap on one leaf and differ in channel ORDER, so
    //: the gate also sees L-12's align-by-name rather than by index
    const meas = { id: 'ds/meas', type: 'fyo:magnetics', magnetics: { b_field_pol_probe: [
      { name: 'P1', field: { data: [1, 2] } }, { name: 'P2', field: { data: [3, 4] } }] } };
    const dossier = { id: 'ds/dossier', type: 'fyo:magnetics', magnetics: { b_field_pol_probe: [
      { name: 'P2', position: { r: 1.8, z: 0.1 } },
      { name: 'P1', position: { r: 2.2, z: 0.0 }, field: { data: [9, 9] } }] } };

    const s = FySources.stack('magnetics', [
      { kind: 'fetch', file: 'meas.json', doc: meas, label: 'MDSplus 取数文档' },
      { kind: 'device', file: 'dossier.json', doc: dossier, label: '装置卷宗' },
      { kind: 'mdsbind', file: 'bind.yaml', query: '?host=h&port=8000', label: '在线取数' },
      { kind: 'hand', file: 'w.json', doc: { magnetics: { 'fylite:weight': [1, 0] } }, on: false }
    ]);

    const a = s.assembly();
    say('装配文档是 fylite:Assembly/1，别名映射 + 有序 merge（U-5）',
        a['@type'] === 'fylite:Assembly/1' && typeof a.$source === 'object'
        && Array.isArray(a.merge), JSON.stringify(a.merge));
    say('关掉的层不进 $source（关掉就是不参与，不是权重为 0）',
        !Object.keys(a.$source).some((k) => /hand/.test(k)) && a.merge.length === 3,
        Object.keys(a.$source).join(','));
    say('merge 是栈序的倒序：栈顶那个排在最后（末位覆盖）',
        a.merge[a.merge.length - 1] === s.layers()[0].alias, a.merge.join(' → '));
    say('mdsbind 源写成 mdsbind: URI 并带查询串，不写成 file:',
        /^mdsbind:bind\.yaml\?host=h/.test(a.$source[s.layers()[2].alias]),
        a.$source[s.layers()[2].alias]);

    // reordering moves the winner
    s.move(0, 1);                        // the dossier becomes the top row
    const a2 = s.assembly();
    say('上下移动改的是谁赢：新的栈顶排到 merge 的末位',
        a2.merge[a2.merge.length - 1] === s.layers()[0].alias
        && s.layers()[0].kind === 'device', a2.merge.join(' → '));
    s.move(0, 1);                        // back
    say('移回去恢复原序', s.layers()[0].kind === 'fetch');

    // U-6 / U-7: who won each leaf, who was shadowed, and what is opaque
    const prov = s.provenance({ 'fylite:assembly': { merged: ['x', 'y'], shot: 0 } });
    const shared = prov.rows.filter((x) => x.shadowed.length);
    //: ★`name` overlaps too, and legitimately: both documents identify their
    //: channels, which is exactly what L-12 aligns on.  The assertion is about
    //: the one leaf that carries a VALUE in both, so it names it rather than
    //: counting rows — the first version of this gate counted, and failed on
    //: two `name` rows that were the module working correctly.
    const dup = shared.filter((x) => /field\/data$/.test(x.path));
    say('逐量出处：重叠的叶子标出赢家与被盖住的（U-6 · U-7）',
        dup.length === 1 && /\[P1\]/.test(dup[0].path)
        && dup[0].from === s.layers()[0].alias
        && dup[0].shadowed.length === 1
        && shared.every((x) => x.from === s.layers()[0].alias),
        JSON.stringify(dup[0] || null) + ` 共 ${shared.length} 条重叠`);
    say('结构数组按 name 而不是下标对齐（L-12：两份的通道次序不同）',
        prov.rows.some((x) => /\[P1\]/.test(x.path)) && prov.rows.some((x) => /\[P2\]/.test(x.path)));
    say('页面拿不到内容的源被点名，而不是当作没给（P-10）',
        prov.opaque.length === 1 && /拿不到/.test(prov.note), prov.note);
    say('中间层真正记下的东西单独列出，不与推出来的混在一起（G-14）',
        prov.recorded && prov.recorded.merged.length === 2
        && prov.rows.every((x) => x.basis === 'derived'));

    // a record as a source, and staleness
    const rec = { id: 'r-99', type: 'spo:ComputationRecord', inputs: [
      { binds_port: { port_name: 'core_profiles', port_direction: 'output' },
        bound_to: { id: 'ds/cp', type: 'fyo:core_profiles' } }] };
    const layer = FySources.fromRecord(rec, 'core_profiles');
    say('上游记录可以当一层源（U-5 第五行，收编页间交接）',
        layer && layer.kind === 'record' && layer.doc.id === 'ds/cp'
        && layer.generation === 'r-99');
    say('上游重跑之后这一层标为过期，而不是静默更新（-12 G-2）',
        FySources.stale(layer, 'r-100') === true && FySources.stale(layer, 'r-99') === false);

    //: hand the documents and the assembly out for the middle layer to run
    out.topAlias = null;
    //: ★the layer handed to §三 drops the mdsbind source, and not to make the
    //: gate pass: what §三 measures is the MERGE ORDER, and an mdsbind layer
    //: would send the middle layer to a server.  With a binding file that does
    //: not exist the assembler correctly reports it as a failure — which is a
    //: fact about the fixture, not about the page's document.
    out.asm = s.assembly();
    out.topAlias = s.layers()[0].alias;
    s.move(0, 1);
    out.asmSwapped = s.assembly();       // the same stack, other way up
    s.move(0, 1);
    return out;
  });

  for (const s of r.steps) (s.pass ? ok : fail)(`${s.name}${s.detail ? ' — ' + s.detail : ''}`);
  const fatal = errs.filter((e) => /sources\.js/.test(e));
  if (fatal.length) fail(`页面抛错：${fatal[0]}`);
  await br.close();
  srv.close();

  // --- 〔三〕 the document matches the middle layer's stated contract ---------
  console.log('\n〔三〕装配文档合中间层自己写下的契约（不借别的宿主来执行它）');
  //: the contract is the module header of `rust/fylite_runtime/src/assembly.rs`:
  //: `$source` is alias -> URI, `merge` names those aliases in order, and the
  //: semantics are 「后者覆盖前者」.  Reading it here rather than running it is
  //: the point — see this file's header.
  const asmRs = join(ROOT, 'rust', 'fylite_runtime', 'src', 'assembly.rs');
  if (!existsSync(asmRs)) {
    console.log('  跳过 —— 本检出没有中间层源码，契约无处可读');
  } else if (!r.asm) {
    fail('页面没有产出装配文档');
  } else {
    const header = readFileSync(asmRs, 'utf8').split('\n').filter((l) => l.startsWith('//'))
      .join('\n');
    if (!/后者覆盖前者/.test(header))
      fail('assembly.rs 的头注不再声明「后者覆盖前者」—— 倒序写 merge 的依据没了，重新读它');
    else ok('契约就在 assembly.rs 的头注里：merge 后者覆盖前者');
    const src2 = r.asm.$source, mg = r.asm.merge;
    const aliasesOk = Array.isArray(mg) && mg.every((a) => typeof src2[a] === 'string');
    if (!aliasesOk) fail('merge 里出现了 $source 没有的别名');
    else ok(`merge 的每个别名都在 $source 里（${mg.length} 个）`);
    if (mg[mg.length - 1] !== r.topAlias)
      fail(`栈顶 ${r.topAlias} 没有排在 merge 的末位 —— 按契约它会被别人盖住`);
    else ok(`栈顶 ${r.topAlias} 排在 merge 末位，按契约它赢（这是文档层面的断言）`);
    if (String(r.asmSwapped.merge) === String(mg))
      fail('把栈倒过来之后 merge 没有变 —— 次序没有承重');
    else ok('把栈倒过来，merge 跟着倒（次序是承重的）');
    console.log('  note  这一节不执行合并。浏览器今天没有中间层的门（G-15：'
                + 'c_api 与 assembly 都在 mdsip 特性门后，wasm 层零导出），'
                + '「合并真按这个次序发生」要等 W-1 落地后在浏览器里自己证。');
  }
}

console.log(bad ? `\n${bad} 处失败` : '\n源栈闸全部通过');
process.exit(bad ? 1 : 0);
