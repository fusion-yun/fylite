// The workbench gate: tiles edit the specification, and a gesture's result is
// either in it or visibly not (`FYL-DESIGN-18` U-14 · U-16 · U-17;
// NR-QUAL-007 second clause).
//
//     node app/tests/validate-workbench.mjs [--playwright <dir>] [--chrome <bin>]
//
// Four things are asserted, and each is a claim the design makes:
//
//   U-14  moving a tile writes `fylite:layout` AND re-sorts `has_view`
//         row-major — because a renderer that does not know the layout term
//         (Python's) reads the ORDER, so the order has to agree with what the
//         workbench shows.  A layout that changed without the order changing
//         would give two different readings of one arrangement.
//   U-17  a view has TWO interaction states.  A zoom is transient and marked
//         「未钉住」; pinning writes `fylite:domain` and clears the mark.  A gate
//         that only checked the pin would pass a workbench that silently
//         exported every zoom.
//   U-17  sharing is by coordinate family: zooming `time` moves every trace
//         against time and NOTHING against rho.
//   U-16  a layer switch is in-spec at once — it is not a transient.
//
// ★No kernel, no worker: a synthetic record and a hand-written spec. What is
// under test is a document being edited.
import { readFileSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..');
let bad = 0;
const fail = (m) => { console.log('  FAIL  ' + m); bad++; };
const ok = (m) => console.log('  ok    ' + m);

console.log('\n〔一〕布局是规格的扩展词，不是页面的私有状态（U-14）');
const wb = readFileSync(join(APP, 'assets', 'workbench.js'), 'utf8');
if (!/fylite:layout/.test(wb)) fail('workbench.js 不写 fylite:layout');
else ok('布局写在 fylite:layout 上');
if (!/localStorage|sessionStorage/.test(wb)) ok('布局不存进浏览器私有存储（它属于规格，随导出走）');
else fail('workbench.js 用了 localStorage —— 布局会与规格脱钩');
const css = readFileSync(join(APP, 'assets', 'style.css'), 'utf8');
if (!/repeat\(12, 1fr\)/.test(css)) fail('style.css 的工作台栅格不是 12 列');
else ok('12 列栅格与 fylite:layout 的计数单位一致');

console.log('\n〔二〕浏览器里：移动 · 缩放 · 钉住 · 共享 · 图层');
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
  const pg = await br.newPage({ viewport: { width: 1400, height: 900 } });
  const errs = [];
  pg.on('pageerror', (e) => errs.push(String(e)));
  await pg.goto(`${url}pages/page_model.html`, { waitUntil: 'domcontentloaded' });
  await pg.addScriptTag({ url: '../assets/workbench.js' });

  const r = await pg.evaluate(() => {
    const out = { steps: [] };
    const say = (name, pass, detail) => out.steps.push({ name, pass: !!pass, detail: detail || '' });
    if (!window.FyWorkbench || !window.FyFig) { say('FyWorkbench / FyFig 已加载', false); return out; }

    const t = [0, 1, 2, 3, 4], rho = [0, 0.25, 0.5, 0.75, 1];
    const record = { id: 'r-wb', type: 'spo:ComputationRecord', inputs: [
      { binds_port: { port_name: 'p', port_direction: 'output' },
        bound_to: { id: 'ds/p', type: 'fyo:core_profiles',
                    comment: ['time [s]', 'profiles_1d/grid/rho_tor_norm [1]'],
                    time: t, ip: [1, 2, 3, 4, 5], beta: [0.1, 0.2, 0.3, 0.4, 0.5],
                    profiles_1d: { grid: { rho_tor_norm: rho },
                                   electrons: { temperature: [3, 2.4, 1.5, 0.7, 0.2] } } } } ] };
    const V = (kind, abscissa, q, extra) => Object.assign({
      type: 'spo:View', view_kind: kind, caption: { zh: q },
      comment: 'abscissa ds/p#' + abscissa,
      has_series: [{ binds_quantity: 'ds/p#' + q, series_role: 'computed' }] }, extra || {});
    const spec = { type: 'spo:PresentationSpecification', has_panel: [{ type: 'spo:Panel', has_view: [
      V('line_chart', 'time', 'ip'),
      V('line_chart', 'time', 'beta'),
      V('line_chart', 'profiles_1d/grid/rho_tor_norm', 'profiles_1d/electrons/temperature'),
    ] }] };

    const host = document.createElement('div');
    host.style.width = '1200px';
    document.body.appendChild(host);
    const w = FyWorkbench.mount(host, { spec, record });

    try {
      // families
      const fams = w.tiles().map((x) => x.family);
      say('坐标族由横轴决定：两条时序同族，剖面不同族（U-17）',
          fams[0] === 'time' && fams[1] === 'time' && fams[2] === 'rho_tor_norm', fams.join(','));

      // default layout, and every tile really is on the grid
      const tiles = host.querySelectorAll('.wb-tile');
      say('三个视图各成一块瓦片，落在 12 列栅格上',
          tiles.length === 3 && tiles[0].getAttribute('data-layout') === '0,0,6,4',
          tiles[0] && tiles[0].getAttribute('data-layout'));

      // U-14: move re-sorts has_view row-major and writes the layout
      w.move(0, { x: 6, y: 4 });                     // the first tile goes last
      const s1 = w.spec();
      const order = s1.has_panel[0].has_view.map((v) => v.caption.zh);
      const l0 = s1.has_panel[0].has_view[2]['fylite:layout'];
      say('移动写 fylite:layout，并把 has_view 按先行后列重排（U-14）',
          order[0] === 'beta' && order[2] === 'ip' && l0.x === 6 && l0.y === 4,
          order.join(',') + ' / ' + JSON.stringify(l0));
      say('重排后瓦片位置不变（重排改的是次序，不是位置）',
          host.querySelectorAll('.wb-tile')[0].getAttribute('data-layout') === '6,4,6,4');

      // resize
      w.move(1, { w: 12, h: 6 });
      say('缩放写宽高，且不越出 12 列',
          w.tiles()[1].layout.w === 12 - w.tiles()[1].layout.x && w.tiles()[1].layout.h === 6,
          JSON.stringify(w.tiles()[1].layout));

      // U-17: a zoom is transient, shared by family, and marked
      w.zoom('time', [1, 3]);
      const tl = w.tiles();
      const flags = [...host.querySelectorAll('.wb-tile')].map((e) => !e.querySelector('.wb-flag').hidden);
      say('缩放按族共享：两条时序动，剖面不动（U-17）',
          tl[0].domain && tl[1].domain && !tl[2].domain,
          JSON.stringify(tl.map((x) => x.domain)));
      say('缩放是瞬态：规格里没有 fylite:domain，瓦片上有「未钉住」',
          !w.spec().has_panel[0].has_view.some((v) => v['fylite:domain'])
          && flags.filter(Boolean).length === 2,
          JSON.stringify(flags));

      // pin: the transient becomes in-spec, and the mark clears
      w.pin(0);
      const s2 = w.spec();
      const pinned = s2.has_panel[0].has_view.filter((v) => v['fylite:domain']);
      const flags2 = [...host.querySelectorAll('.wb-tile')].map((e) => !e.querySelector('.wb-flag').hidden);
      say('钉住把定义域写进规格，只写同族的那些，并清掉标记（U-17）',
          pinned.length === 2 && pinned[0]['fylite:domain'][0] === 1
          && pinned[0]['fylite:domain'][1] === 3 && flags2.every((x) => !x),
          `${pinned.length} 个视图被钉住`);

      // the cursor is shared and never in-spec
      w.setCursor('time', 2.5);
      const cur = w.tiles().map((x) => x.cursor);
      say('光标按族共享，且不进规格（U-17）',
          cur[0] === 2.5 && cur[1] === 2.5 && cur[2] === null
          && !JSON.stringify(w.spec()).includes('cursor'), JSON.stringify(cur));

      // U-16: a layer switch is in-spec at once
      const mapSpec = { has_panel: [{ has_view: [{ view_kind: 'map', caption: { zh: '截面' },
        flux_layer: 'ds/eq', overlay_layer: [{ id: 'ds/ref' }] }] }] };
      const host2 = document.createElement('div');
      document.body.appendChild(host2);
      const w2 = FyWorkbench.mount(host2, { spec: mapSpec, record });
      w2.setLayer(0, 'ds/ref', false);
      const ov = w2.spec().has_panel[0].has_view[0].overlay_layer[0];
      say('图层开关立刻进规格，不是瞬态（U-16）', ov['fylite:visible'] === false, JSON.stringify(ov));
      host2.remove();

      // the workbench edited a COPY: the caller's spec is untouched
      say('工作台改的是自己那份，调用方交进来的规格没被就地改写',
          !JSON.stringify(spec).includes('fylite:layout'));
    } catch (e) {
      say('工作台运行无异常', false, String((e && e.stack) || e));
    } finally {
      host.remove();
    }
    return out;
  });

  for (const s of r.steps) (s.pass ? ok : fail)(`${s.name}${s.detail ? ' — ' + s.detail : ''}`);
  const fatal = errs.filter((e) => /workbench\.js|fig\.js/.test(e));
  if (fatal.length) fail(`页面抛错：${fatal[0]}`);
  await br.close();
  srv.close();
}

console.log(bad ? `\n${bad} 处失败` : '\n工作台闸全部通过');
process.exit(bad ? 1 : 0);
