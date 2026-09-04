// The spec gate, page half: a figure is drawn from the presentation
// specification, by the report face's resolver, and a view it cannot draw is
// refused BY NAME (`FYL-DESIGN-18` U-12 · U-16 · U-17 · U-21 · U-22;
// NR-QUAL-007 second clause).
//
//     node app/tests/validate-fig.mjs [--playwright <dir>] [--chrome <bin>]
//
// ★Why a synthetic record and not a real run.  What is under test is the
// PROJECTION — spec in, marks out — and that is decided before any kernel
// answers.  A gate that needed a wasm run would test the kernel's arithmetic
// on the way to testing a renderer, and would skip on every machine without a
// build.  The record below is written here, in one place, and every assertion
// reads it.
//
// ★The stub is the assertion.  `FyPlot` is replaced by a recorder for the
// duration, so the gate reads WHAT WAS ASKED FOR — series kinds, dashes,
// domains, layers — rather than counting pixels.  A pixel check would pass a
// residual drawn as a polyline (the one thing U-21 forbids) as long as it was
// the right colour.
import { readFileSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..');
let bad = 0;
const fail = (m) => { console.log('  FAIL  ' + m); bad++; };
const ok = (m) => console.log('  ok    ' + m);

// --- 〔一〕 one resolver, not two --------------------------------------------
console.log('\n〔一〕fig.js 不自带第二份解析规则（U-12：一份规格两端同画）');
const fig = readFileSync(join(APP, 'assets', 'fig.js'), 'utf8');
for (const name of ['coordinateOf', 'quantities', 'index', 'resolve'])
  if (new RegExp(`function\\s+${name}\\s*\\(`).test(fig))
    fail(`fig.js 自己定义了 ${name}() —— 它必须用 FyCaseReport 的那一份`);
for (const call of ['R.resolve', 'R.index', 'R.coordinateOf'])
  if (!fig.includes(call)) fail(`fig.js 没有用 ${call}`);
if (!bad) ok('解析走 FyCaseReport（index / resolve / coordinateOf），fig.js 只管怎么画');
const cr = readFileSync(join(APP, 'assets', 'casereport.js'), 'utf8');
if (!/index: index, resolve: resolve/.test(cr)) fail('casereport.js 没有导出 index / resolve');
else ok('casereport.js 导出了 index / resolve 供 fig.js 复用');
if (!/kind === 'stems'/.test(readFileSync(join(APP, 'assets', 'plot.js'), 'utf8')))
  fail("plot.js 没有 'stems' —— U-21 的残差茎无处落");
else ok("plot.js 认得 'stems'（U-21：不连续横轴不画折线）");

// --- 〔二〕 the spec vocabulary carries the new terms -------------------------
console.log('\n〔二〕呈现规格词表带 layout / visible / domain（G-3）');
const ctxDoc = JSON.parse(readFileSync(join(APP, '..', 'docs', 'examples', 'context.jsonld'), 'utf8'))['@context'];
for (const term of ['layout', 'visible', 'domain', 'fylite'])
  if (!ctxDoc[term]) fail(`context.jsonld 没有 ${term}`);
if (ctxDoc.layout && ctxDoc.visible && ctxDoc.domain) ok('三个词都在，且 fylite: 前缀已声明');

// --- 〔三〕 in a browser ------------------------------------------------------
console.log('\n〔三〕浏览器里：五种视图各画对，画不了的按名拒绝');
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
  const pg = await br.newPage({ viewport: { width: 1200, height: 900 } });
  const errs = [];
  pg.on('pageerror', (e) => errs.push(String(e)));
  //: the page is loaded only for its scripts; nothing on it is under test
  await pg.goto(`${url}pages/page_model.html`, { waitUntil: 'domcontentloaded' });

  const r = await pg.evaluate(() => {
    const out = { steps: [] };
    const say = (name, pass, detail) => out.steps.push({ name, pass: !!pass, detail: detail || '' });
    if (!window.FyFig) { say('FyFig 已加载', false); return out; }
    if (!window.FyCaseReport) { say('FyCaseReport 已加载', false); return out; }

    //: ONE synthetic record: an equilibrium with a boundary outline, a
    //: core_profiles with a grid and two profiles, and a magnetics with a
    //: per-channel residual (no coordinate — the stem case).
    const rho = [0, 0.25, 0.5, 0.75, 1];
    const record = {
      id: 'r-gate', type: 'spo:ComputationRecord', run_state: 'succeeded',
      inputs: [
        { binds_port: { port_name: 'core_profiles', port_direction: 'output' },
          bound_to: { id: 'ds/core_profiles', type: 'fyo:core_profiles',
                      comment: ['profiles_1d/electrons/temperature [eV]', 'profiles_1d/grid/rho_tor_norm [1]'],
                      profiles_1d: { grid: { rho_tor_norm: rho },
                                     electrons: { temperature: [3000, 2400, 1500, 700, 200] },
                                     ion: [{ temperature: [2500, 2000, 1300, 600, 180] }] } } },
        { binds_port: { port_name: 'equilibrium', port_direction: 'output' },
          bound_to: { id: 'ds/equilibrium', type: 'fyo:equilibrium',
                      time_slice: { boundary: { outline: { r: [1.6, 2.2, 1.6, 1.0], z: [-0.8, 0, 0.8, 0] } },
                                    global_quantities: { magnetic_axis: { r: 1.7, z: 0.02 } } } } },
        { binds_port: { port_name: 'magnetics', port_direction: 'output' },
          bound_to: { id: 'ds/magnetics', type: 'fyo:magnetics',
                      comment: ['residual [T]'],
                      residual: [0.02, -0.01, 0.04, -0.03, 0.01, 0.02] } },
      ],
    };

    //: capture what the plotter was ASKED to draw
    const calls = { xy: [], poloidal: [] };
    const realXY = FyPlot.xy, realPol = FyPlot.poloidal;
    FyPlot.xy = (cv, o) => { calls.xy.push(o); };
    FyPlot.poloidal = (cv, o) => { calls.poloidal.push(o); };
    const host = document.createElement('div');
    document.body.appendChild(host);

    try {
      // (a) the derived spec draws, and every view of it is one of fig.js's kinds
      const spec = FyFig.derive(null, record);
      const res = FyFig.renderSpec(host, spec, record);
      const kinds = [];
      (spec.has_panel || []).forEach((p) => (p.has_view || []).forEach((v) => kinds.push(v.view_kind)));
      say('推出的规格能整份画出', res.drawn > 0 && res.refused.length === 0,
          `drawn=${res.drawn} refused=${JSON.stringify(res.refused.map((x) => x.why))}`);
      say('推出的每种 view_kind 都被 fig.js 认得',
          kinds.every((k) => FyFig.KINDS.includes(k)), kinds.join(','));
      say('线图的横轴是量自己的坐标（P2）',
          calls.xy.length > 0 && calls.xy[0].series[0].x.length === 5
          && calls.xy[0].series[0].x[4] === 1, JSON.stringify(calls.xy[0] && calls.xy[0].xlabel));
      say('极向截面用了边界轮廓与磁轴',
          calls.poloidal.length === 1 && calls.poloidal[0].lcfs.length === 8
          && calls.poloidal[0].axis[0] === 1.7);

      // (b) a stem view: index abscissa, stems mark, zero line — never a line
      calls.xy.length = 0; host.innerHTML = '';
      const stem = { has_panel: [{ type: 'spo:Panel', has_view: [{
        type: 'spo:View', view_kind: 'stem', caption: { zh: '逐通道残差' },
        has_series: [{ binds_quantity: 'ds/magnetics#residual', series_role: 'computed' }] }] }] };
      const rs = FyFig.renderSpec(host, stem, record);
      const s0 = calls.xy[0] && calls.xy[0].series[0];
      say('stem 视图画成茎，横轴是通道序号，带零线',
          rs.drawn === 1 && s0 && s0.kind === 'stems' && s0.x.length === 6
          && s0.x[0] === 1 && calls.xy[0].zeroLine === true,
          s0 ? `${s0.kind} x0=${s0.x[0]} n=${s0.x.length}` : 'no call');

      // (c) a table view: one column per series, one row per index
      host.innerHTML = '';
      const tbl = { has_panel: [{ has_view: [{ view_kind: 'table', caption: { zh: '残差表' },
        has_series: [{ binds_quantity: 'ds/magnetics#residual', display_label: { zh: '残差' } }] }] }] };
      FyFig.renderSpec(host, tbl, record);
      const rows = host.querySelectorAll('tbody tr').length;
      say('table 视图逐行渲染（U-21）', rows === 6, `${rows} 行`);

      // (d) baseline role is marked apart from computed (U-22)
      calls.xy.length = 0; host.innerHTML = '';
      const cmp = { has_panel: [{ has_view: [{ view_kind: 'line_chart',
        comment: 'abscissa ds/core_profiles#profiles_1d/grid/rho_tor_norm',
        has_series: [
          { binds_quantity: 'ds/core_profiles#profiles_1d/electrons/temperature', series_role: 'computed' },
          { binds_quantity: 'ds/core_profiles#profiles_1d/ion/temperature', series_role: 'baseline' }] }] }] };
      FyFig.renderSpec(host, cmp, record);
      const ss = calls.xy[0] ? calls.xy[0].series : [];
      say('baseline 与 computed 在非颜色通道上分得开（U-22 · P-27）',
          ss.length === 2 && !ss[0].dash && Array.isArray(ss[1].dash),
          JSON.stringify(ss.map((s) => s.dash || null)));

      // (e) a pinned domain is honoured (U-17)
      calls.xy.length = 0; host.innerHTML = '';
      const pinned = JSON.parse(JSON.stringify(cmp));
      pinned.has_panel[0].has_view[0]['fylite:domain'] = [0.2, 0.8];
      FyFig.renderSpec(host, pinned, record);
      say('钉住的定义域被采用（U-17）',
          calls.xy[0] && calls.xy[0].xmin === 0.2 && calls.xy[0].xmax === 0.8,
          `${calls.xy[0] && calls.xy[0].xmin}..${calls.xy[0] && calls.xy[0].xmax}`);

      // (f) refusals: a quantity that is not there, and a map with no outline
      host.innerHTML = '';
      const gone = { has_panel: [{ has_view: [
        { view_kind: 'line_chart', caption: { zh: '不存在的量' },
          has_series: [{ binds_quantity: 'ds/core_profiles#profiles_1d/nowhere' }] },
        { view_kind: 'map', caption: { zh: '没有轮廓' }, flux_layer: 'ds/core_profiles' },
        { view_kind: 'wat', caption: { zh: '未知种类' } }] }] };
      const rf = FyFig.renderSpec(host, gone, record);
      const notes = host.querySelectorAll('[data-fig-refused]').length;
      say('三种画不了各出一句拒绝，且不画空图（P-6 · P-10）',
          rf.drawn === 0 && rf.refused.length === 3 && notes === 3
          && rf.refused.every((x) => /按名拒绝/.test(x.why)),
          `drawn=${rf.drawn} notes=${notes} ${JSON.stringify(rf.refused.map((x) => x.why.slice(0, 30)))}`);
      say('拒绝的句子指名道姓',
          rf.refused.some((x) => x.why.includes('nowhere'))
          && rf.refused.some((x) => x.why.includes('边界轮廓'))
          && rf.refused.some((x) => x.why.includes('wat')));
    } catch (e) {
      say('渲染过程无异常', false, String(e && e.stack || e));
    } finally {
      FyPlot.xy = realXY; FyPlot.poloidal = realPol;
      host.remove();
    }
    return out;
  });

  for (const s of r.steps) (s.pass ? ok : fail)(`${s.name}${s.detail ? ' — ' + s.detail : ''}`);
  const fatal = errs.filter((e) => /fig\.js|casereport|plot\.js/.test(e));
  if (fatal.length) fail(`页面抛错：${fatal[0]}`);
  await br.close();
  srv.close();
}

console.log(bad ? `\n${bad} 处失败` : '\n规格闸（页面半边）全部通过');
process.exit(bad ? 1 : 0);
