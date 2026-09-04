// The round-trip gate: the document set is one exchange unit, and it survives
// leaving and coming back (`FYL-DESIGN-18` U-18 · U-19; NR-QUAL-007 fourth
// clause — the fourth of the four gates §十三 names).
//
//     node app/tests/validate-bundle.mjs [--playwright <dir>] [--chrome <bin>]
//
// The criterion the design states: **export → clear → import → export again,
// with `plan.jsonld` and `presentation.jsonld` byte-identical and
// `record.jsonld` leaf-identical**.
//
// ★It is verified against a zip reader that is not ours.  A writer and a reader
// written in the same file agree with each other by construction; that says
// nothing about whether what was written is a zip.  So the bytes the browser
// produced are handed to Python's `zipfile` — and, where present, to `unzip -t`.
// If either refuses, the「移步」 of U-19 does not happen, whatever our own
// reader thinks.
import { readFileSync, writeFileSync, existsSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';
import { tmpdir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..');
let bad = 0;
const fail = (m) => { console.log('  FAIL  ' + m); bad++; };
const ok = (m) => console.log('  ok    ' + m);

console.log('\n〔一〕交换单元只有一种，分类按内容不按文件名（U-18）');
const src = readFileSync(join(APP, 'assets', 'bundle.js'), 'utf8');
if (!/TYPE_OF/.test(src) || !/doc\.type \|\| doc\['@type'\]/.test(src))
  fail('bundle.js 不是按 @type 分类的');
else ok('分类读的是文档的 @type');
if (/getTime\(\)|Date\.now\(\)/.test(src.replace(/\/\/.*$/gm, '')))
  fail('zip 里写了时间戳 —— 同一份文档集每次导出都会是不同的字节');
else ok('zip 不带时间戳（往返闸比的是字节）');

console.log('\n〔二〕浏览器写出的 zip，交给别人的读者');
const flag = (name, env) => { const i = process.argv.indexOf('--' + name); return i > 0 ? process.argv[i + 1] : process.env[env]; };
if (!flag('playwright', 'PLAYWRIGHT_PATH')) {
  console.log('  跳过 —— 用 --playwright <装有 playwright 的目录> 或设 $PLAYWRIGHT_PATH');
} else {
  const { browser } = await import('./_browser.mjs');
  const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                  '.css': 'text/css; charset=utf-8', '.json': 'application/json',
                  '.jsonld': 'application/ld+json', '.svg': 'image/svg+xml' };
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
  await pg.addScriptTag({ url: '../assets/bundle.js' });

  const r = await pg.evaluate(() => {
    const out = { steps: [], b64: null, b64b: null };
    const say = (name, pass, detail) => out.steps.push({ name, pass: !!pass, detail: detail || '' });
    if (!window.FyBundle) { say('FyBundle 已加载', false); return out; }

    const plan = { '@context': ['context.jsonld'], id: 'cases/transport-iter-15ma',
                   type: 'fyo:ScenarioSpecification', title: { zh: '芯部输运', en: 'core transport' },
                   parameters: [{ type: 'spo:ParameterSetting', sets_parameter: 'code/transport#a',
                                  literal_value: 1.75 }] };
    const record = { id: 'r-b1', type: 'spo:ComputationRecord', run_state: 'succeeded',
                     environment: { kernel_sha256: 'aa11bb22cc33', abi: 125, app_version: '0.0.1-alpha' },
                     'fylite:state': { step: 20, sum: 1.5 },
                     inputs: [{ binds_port: { port_name: 'core_profiles', port_direction: 'output' },
                                bound_to: { id: 'ds/cp', type: 'fyo:core_profiles',
                                            profiles_1d: { grid: { rho_tor_norm: [0, 0.5, 1] },
                                                           electrons: { temperature: [3, 1.5, 0.2] } } } }] };
    const presentation = { id: 'r-b1/presentation', type: 'spo:PresentationSpecification',
                           has_panel: [{ type: 'spo:Panel', has_view: [
                             { type: 'spo:View', view_kind: 'line_chart',
                               'fylite:layout': { x: 0, y: 0, w: 6, h: 4 },
                               'fylite:domain': [0.2, 0.8],
                               has_series: [{ binds_quantity: 'ds/cp#profiles_1d/electrons/temperature' }] }] }] };
    const inputs = { magnetics: { id: 'ds/mag', type: 'fyo:magnetics', 'fylite:assembly': { shot: 138569 } } };

    const zip1 = FyBundle.build({ plan, record, presentation, inputs, report: '# 报告\n' });
    const set = FyBundle.read(zip1);

    say('分类：计划 · 记录 · 规格 · 输入 · 环境 · 报告各归各位',
        set.plan.id === plan.id && set.record.id === record.id
        && set.presentation.id === presentation.id
        && set.inputs.magnetics.id === 'ds/mag'
        && set.environment.kernel_sha256 === 'aa11bb22cc33'
        && set.report === '# 报告\n' && set.unknown.length === 0,
        JSON.stringify({ inputs: Object.keys(set.inputs), unknown: set.unknown }));

    //: THE CRITERION: export -> clear -> import -> export again
    const zip2 = FyBundle.build({ plan: set.plan, record: set.record,
                                  presentation: set.presentation, inputs: set.inputs,
                                  report: set.report });
    const a = FyBundle.unzip(zip1), b = FyBundle.unzip(zip2);
    say('往返：plan.jsonld 与 presentation.jsonld 逐字节相同（§十三 往返闸）',
        a['plan.jsonld'] === b['plan.jsonld']
        && a['presentation.jsonld'] === b['presentation.jsonld']);
    say('往返：record.jsonld 逐叶子相同', a['record.jsonld'] === b['record.jsonld']);
    say('往返：整份 zip 逐字节相同（无时间戳，可比较）',
        zip1.length === zip2.length && zip1.every((v, i) => v === zip2[i]),
        `${zip1.length} vs ${zip2.length}`);
    say('布局与钉住的定义域活着穿过了一次往返（U-14 · U-17）',
        b['presentation.jsonld'].includes('fylite:layout')
        && b['presentation.jsonld'].includes('fylite:domain'));

    //: what a partial set can drive (U-18: 缺哪一份就少哪一条投影，不报错)
    const onlyPlan = FyBundle.read(FyBundle.build({ plan }));
    const cap1 = FyBundle.capabilities(onlyPlan), cap2 = FyBundle.capabilities(set);
    say('只有计划的集合能开输入页、不能出报告；完整的能续跑（U-18）',
        cap1.inputPage && !cap1.report && !cap1.resume
        && cap2.report && cap2.resume, JSON.stringify([cap1, cap2]));

    //: an unrecognised member is kept and listed, never dropped
    const withJunk = FyBundle.zip({ 'plan.jsonld': JSON.stringify(plan), 'notes.txt': 'hi' });
    const junkSet = FyBundle.read(withJunk);
    say('不认识的成员被列出而不是丢掉', junkSet.plan && junkSet.unknown.length === 1,
        JSON.stringify(junkSet.unknown));

    //: a second plan in one set is a fact about the set
    const two = FyBundle.zip({ 'a.jsonld': JSON.stringify(plan), 'b.jsonld': JSON.stringify(plan) });
    const twoSet = FyBundle.read(two);
    say('一套里两份计划：取其一并把另一份点名', twoSet.plan && /第二份 plan/.test(String(twoSet.unknown)),
        JSON.stringify(twoSet.unknown));

    const b64 = (u8) => { let s = ''; for (const v of u8) s += String.fromCharCode(v); return btoa(s); };
    out.b64 = b64(zip1);
    out.b64b = b64(zip2);
    return out;
  });

  for (const s of r.steps) (s.pass ? ok : fail)(`${s.name}${s.detail ? ' — ' + s.detail : ''}`);

  if (r.b64) {
    const dir = mkdtempSync(join(tmpdir(), 'fy-bundle-'));
    const f = join(dir, 'bundle.zip');
    writeFileSync(f, Buffer.from(r.b64, 'base64'));
    //: ★someone else's reader.  Python's `zipfile` verifies the central
    //: directory, the local headers and every CRC.
    try {
      const listed = execFileSync('python3', ['-c', `
import json, zipfile
z = zipfile.ZipFile(${JSON.stringify(f)})
bad = z.testzip()
assert bad is None, bad
names = sorted(z.namelist())
plan = json.loads(z.read('plan.jsonld'))
print(json.dumps({'names': names, 'plan': plan['id'],
                  'utf8': json.loads(z.read('record.jsonld'))['id']}))
`], { encoding: 'utf8' });
      const got = JSON.parse(listed);
      const want = ['environment.json', 'inputs/magnetics.jsonld', 'plan.jsonld',
                    'presentation.jsonld', 'record.jsonld', 'report.md'];
      if (String(got.names) !== String(want)) fail(`Python 读到的成员是 ${got.names}`);
      else if (got.plan !== 'cases/transport-iter-15ma') fail('Python 读到的计划不对');
      else ok(`Python 的 zipfile 读得回（CRC 全过，${got.names.length} 个成员，UTF-8 完好）`);
    } catch (e) {
      fail(`Python 的 zipfile 读不了这个 zip：${String(e.message).split('\n').slice(-3).join(' ')}`);
    }
    try {
      execFileSync('unzip', ['-tqq', f], { encoding: 'utf8' });
      ok('unzip -t 也认（两个独立的读者）');
    } catch (e) {
      if (/ENOENT/.test(String(e.message))) console.log('  note  这台机器上没有 unzip，跳过第二个读者');
      else fail(`unzip -t 拒绝：${e.message}`);
    }
  }

  const fatal = errs.filter((e) => /bundle\.js/.test(e));
  if (fatal.length) fail(`页面抛错：${fatal[0]}`);
  await br.close();
  srv.close();
}

console.log(bad ? `\n${bad} 处失败` : '\n往返闸全部通过');
process.exit(bad ? 1 : 0);
