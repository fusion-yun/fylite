// The source-stack gate: the page orders, the middle layer merges, and the
// order the page drew is the order that won (`FYL-DESIGN-18` U-5 · U-6 · U-7,
// §五).
//
//     node app/tests/validate-sources.mjs [--playwright <dir>] [--chrome <bin>]
//
// ★★The assertion that matters is made by the REAL assembler.  The stack is
// drawn top-wins; `merge` is last-wins; so the document the page writes has to
// reverse the order, and a mistake there is invisible from inside the browser —
// the numbers still assemble, the table still renders, and the answer quietly
// comes from the source the reader ranked last.  So this gate takes the
// assembly document the page produced, hands it to `fylite.io.fydoc.assemble`
// (the middle layer through its C ABI), and asserts the value that came back is
// the TOP row's.  Nothing short of running it can catch an inverted priority.
//
// ★It skips, rather than passing, when the middle layer is not built: an
// assertion about the merge that never reached the merge is not evidence.
import { readFileSync, existsSync, mkdtempSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';
import { tmpdir } from 'node:os';

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
    const out = { steps: [], docs: null, asm: null, asmSwapped: null };
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
    out.docs = { 'meas.json': meas, 'dossier.json': dossier };
    //: ★the layer handed to §三 drops the mdsbind source, and not to make the
    //: gate pass: what §三 measures is the MERGE ORDER, and an mdsbind layer
    //: would send the middle layer to a server.  With a binding file that does
    //: not exist the assembler correctly reports it as a failure — which is a
    //: fact about the fixture, not about the page's document.
    const off = FySources.stack('magnetics', s.layers().filter((l) => l.kind !== 'mdsbind'));
    out.asm = off.assembly();
    off.move(0, 1);
    out.asmSwapped = off.assembly();     // the same stack, other way up
    return out;
  });

  for (const s of r.steps) (s.pass ? ok : fail)(`${s.name}${s.detail ? ' — ' + s.detail : ''}`);
  const fatal = errs.filter((e) => /sources\.js/.test(e));
  if (fatal.length) fail(`页面抛错：${fatal[0]}`);
  await br.close();
  srv.close();

  // --- 〔三〕 the real middle layer runs what the page wrote -------------------
  console.log('\n〔三〕真的中间层执行这份装配文档，看谁赢了');
  if (!r.asm) fail('页面没有产出装配文档');
  else if (!existsSync(join(ROOT, 'python', 'fylite', '_lib', 'libfylite_runtime.so'))) {
    console.log('  跳过 —— 中间层未构建（rust/build.sh）；没到过合并的断言不是证据');
  } else {
    const dir = mkdtempSync(join(tmpdir(), 'fy-src-'));
    for (const [name, doc] of Object.entries(r.docs)) writeFileSync(join(dir, name), JSON.stringify(doc));
    writeFileSync(join(dir, 'asm.json'), JSON.stringify(r.asm));
    writeFileSync(join(dir, 'asm-swapped.json'), JSON.stringify(r.asmSwapped));
    const run = (f) => JSON.parse(execFileSync('python3', ['-c', `
import json, sys
from fylite.io import fydoc
b, failed = fydoc.assemble(${JSON.stringify(join(dir, f))})
d = b.to_dict()
probe = {p['name']: p for p in d.get('b_field_pol_probe', [])}
print(json.dumps({'failed': failed,
                  'p1_field': probe.get('P1', {}).get('field', {}).get('data'),
                  'p1_pos': probe.get('P1', {}).get('position'),
                  'merged': (d.get('fylite:assembly') or {}).get('merged')}))
`], { encoding: 'utf8', cwd: ROOT, env: { ...process.env, PYTHONPATH: join(ROOT, 'python') } }));
    try {
      const top = run('asm.json'), swapped = run('asm-swapped.json');
      if (top.failed.length) fail(`中间层拒绝了页面写的装配文档：${top.failed}`);
      else ok(`中间层执行成功，merged = ${top.merged.join(' → ')}`);
      //: the fetch layer is the top row and carries P1.field = [1, 2];
      //: the dossier carries [9, 9].  Top-wins means [1, 2] comes out.
      if (String(top.p1_field) !== '1,2')
        fail(`栈顶没赢：P1.field = ${top.p1_field}（栈顶给的是 1,2）—— merge 的次序反了`);
      else ok('栈顶的那一层赢了重叠的叶子（U-7），实测 P1.field = 1,2');
      if (String(swapped.p1_field) !== '9,9')
        fail(`把栈倒过来之后赢家没换：P1.field = ${swapped.p1_field}`);
      else ok('把栈倒过来，赢家跟着换（实测 9,9）—— 次序确实是承重的');
      if (!top.p1_pos || top.p1_pos.r !== 2.2)
        fail(`没有从另一层补上几何：P1.position = ${JSON.stringify(top.p1_pos)}`);
      else ok('没被盖住的叶子从下层补齐（L-12 按 name 对齐，两份的通道次序不同）');
    } catch (e) {
      fail(`中间层执行失败：${String(e.message).split('\n').slice(-3).join(' ')}`);
    }
  }
}

console.log(bad ? `\n${bad} 处失败` : '\n源栈闸全部通过');
process.exit(bad ? 1 : 0);
