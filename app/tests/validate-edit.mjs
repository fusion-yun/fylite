// The edit gate: a try changes the plan, can be taken back, and a shape that
// cannot be drawn is refused rather than corrected (`FYL-DESIGN-18` U-15 ·
// U-23, §八).
//
//     node app/tests/validate-edit.mjs [--playwright <dir>] [--chrome <bin>]
//
// The claims, each of which fails in a way that looks fine from outside:
//
//   U-15  a drag writes the PLAN.  A page keeping the dragged shape in its own
//         variables passes every visual check and sends the OLD boundary the
//         moment a drag is abandoned — so the assertion is on the document, not
//         on the canvas.
//   U-15  every try is a version, and「回到 #1」is a plan.  An undo that mutated
//         the plan in place would leave the earlier version holding the later
//         numbers; the gate keeps a reference to an old version and checks it
//         did not move.
//   P-6   a self-intersecting or out-of-limiter outline is REFUSED by name and
//         left alone.  A validator that quietly nudged the point back inside
//         would produce a shape nobody chose.
//   U-23  a channel the dossier disabled cannot be reopened from the figure.
//
// ★And the tier table: no gesture in `edit.js` returns C.  A slider that could
// reach an annealing run is exactly what D-9 forbids, and it is one grep.
import { readFileSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..');
let bad = 0;
const fail = (m) => { console.log('  FAIL  ' + m); bad++; };
const ok = (m) => console.log('  ok    ' + m);

console.log('\n〔一〕档位：没有一个手势能到 C 档（D-9）');
const src = readFileSync(join(APP, 'assets', 'edit.js'), 'utf8');
const code = src.replace(/\/\*[\s\S]*?\*\//g, '').split('\n')
  .map((l) => l.replace(/(^|\s)\/\/.*$/, '')).join('\n');
if (!/drag: 'A'/.test(code) || !/release: 'B'/.test(code) || !/key: 'C'/.test(code))
  fail('档位表不全');
else ok('档位表在一处：拖动 A · 松手 B · 按键 C');
if (/return 'C'/.test(code)) fail("edit.js 里有直接返回 'C' 的路径 —— 手势不得到 C 档");
else ok("没有手势返回 'C'（滑杆与把手永远到不了退火 / 扫描）");

console.log('\n〔二〕浏览器里：试改写计划 · 版本 · 拒绝 · 通道权限');
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
  await pg.addScriptTag({ url: '../assets/edit.js' });

  const r = await pg.evaluate(() => {
    const out = { steps: [] };
    const say = (n, p, d) => out.steps.push({ name: n, pass: !!p, detail: d || '' });
    if (!window.FyEdit) { say('FyEdit 已加载', false); return out; }

    const plan0 = { id: 'cases/discharge-iter', type: 'fyo:ScenarioSpecification',
                    parameters: [{ type: 'spo:ParameterSetting',
                                   sets_parameter: 'code/discharge#kappa', literal_value: 1.62 }] };
    const e = FyEdit.editor(plan0, { code: 'discharge' });

    e.setHandle('kappa', 1.90);
    const p1 = e.plan();
    say('方把手写 sets_parameter，不是页面自己的变量（U-15）',
        FyEdit.getParam(p1, 'code/discharge#kappa') === 1.90
        && plan0.parameters[0].literal_value === 1.62,
        `plan=${FyEdit.getParam(p1, 'code/discharge#kappa')} caller=${plan0.parameters[0].literal_value}`);

    e.setHandle('du', 0.45);
    const held = e.plan();
    e.setHandle('kappa', 2.05);
    say('每次试改是一个版本，早先取到的那份没有跟着变',
        e.versions().length === 4 && FyEdit.getParam(held, 'code/discharge#kappa') === 1.90
        && FyEdit.getParam(e.plan(), 'code/discharge#kappa') === 2.05,
        `${e.versions().length} 个版本`);
    e.undo();
    say('撤销回到上一版计划', FyEdit.getParam(e.plan(), 'code/discharge#kappa') === 1.90);
    e.goto(0);
    say('「回到 #1」是换回那一版计划', FyEdit.getParam(e.plan(), 'code/discharge#kappa') === 1.62);
    e.goto(3);
    e.setHandle('a', 1.75);
    say('从中间改出新枝时丢掉重做尾巴（历史不含糊）', e.versions().length === 5);

    const p = { r0: 6.2, a: 1.75, kappa: 1.9, du: 0.25, dl: 0.4 };
    const hs = FyEdit.handles(p);
    const back = hs.map((h) => FyEdit.fromHandle(h.name, h.r, h.z, p));
    say('把手位置 ↔ 参数值可逆（拖一个像素只改一个数）',
        Math.abs(back[1] - p.a) < 1e-9 && Math.abs(back[2] - p.kappa) < 1e-9
        && Math.abs(back[3] - p.du) < 1e-9, JSON.stringify(back.map((x) => +x.toFixed(4))));
    const ml = FyEdit.miller(p, 64);
    const kap = (Math.max(...ml.z) - Math.min(...ml.z)) / (Math.max(...ml.r) - Math.min(...ml.r));
    say('解析轮廓的拉长比就是输入的那个（A 档画的是同一个形状）',
        Math.abs(kap - p.kappa) < 0.02, kap.toFixed(3));

    const outline = { r: ml.r, z: ml.z };
    e.setOutline(outline, 'g138569.04000#time_slice/boundary/outline');
    const b = e.plan().inputs.find((x) => x.binds_port.port_name === 'boundary');
    say('路点写成绑到 boundary 端口的文档，并记下它派生自哪里（U-15）',
        !!b && b.bound_to['fylite:edited_from'].indexOf('g138569') === 0
        && b.bound_to.time_slice.boundary.outline.r.length === 64);

    const lim = { r: [4, 8.5, 8.5, 4], z: [-5, -5, 5, 5] };
    const good = FyEdit.validateOutline(outline, lim);
    const outside = { r: outline.r.map((v, i) => (i === 3 ? 12 : v)), z: outline.z.slice() };
    const v2 = FyEdit.validateOutline(outside, lim);
    const bow = { r: [0, 1, 0, 1], z: [0, 1, 1, 0] };
    const v3 = FyEdit.validateOutline(bow, null);
    say('合规的通过；出了限制器的按名拒绝并给出坐标（P-6）',
        good.ok && !v2.ok && /限制器之外/.test(v2.why) && /R = 12/.test(v2.why), v2.why);
    say('自交的按名拒绝，并说出是哪两段', !v3.ok && /自交/.test(v3.why), v3.why);
    say('拒绝不改数：被判失败的那份轮廓原样还在', outside.r[3] === 12, String(outside.r[3]));
    const noLim = FyEdit.validateOutline(outline, null);
    say('没有限制器时不谎称通过，而是说明没判（P-10）',
        noLim.ok && /未对限制器判定/.test(noLim.why), noLim.why);

    const knots = [{ x: 0, y: 3 }, { x: 0.3, y: 2.6 }, { x: 0.6, y: 1.5 }, { x: 1, y: 0.2 }];
    const grid = [0, 0.15, 0.3, 0.45, 0.6, 0.8, 1];
    const ys = FyEdit.pchip(knots, grid);
    const atKnots = knots.every((k) => Math.abs(FyEdit.pchip(knots, [k.x])[0] - k.y) < 1e-9);
    let mono = true;
    for (let i = 1; i < ys.length; i++) if (ys[i] > ys[i - 1] + 1e-12) mono = false;
    say('剖面曲线过每个节点，在单调的节点间不过冲（是造型，不是拟合）',
        atKnots && mono && Math.min(...ys) > 0, ys.map((v) => +v.toFixed(3)).join(','));
    e.setProfile('te', knots, grid);
    const teKnots = FyEdit.getParam(e.plan(), 'code/discharge#te_knots');
    say('剖面写成数组参数，节点也一并留下（可以再编辑）',
        FyEdit.getParam(e.plan(), 'code/discharge#te').length === grid.length && teKnots.length === 4);

    const dossier = { disabled: [7] };
    const okCh = e.setChannel('magnetics', 3, { weight: 0 }, dossier);
    const noCh = e.setChannel('magnetics', 7, { enabled: true }, dossier);
    const hand = e.plan().inputs.find((x) => x.binds_port.port_name === 'magnetics');
    say('改权重写进手填层，带 fylite:edited_from（U-23）',
        !okCh.refused && !!hand && hand.bound_to['fylite:weight']['3'] === 0
        && hand.bound_to['fylite:edited_from'] === 'magnetics');
    say('卷宗禁用的通道打不开，且说出理由（-12 G-9）',
        !!noCh.refused && /卷宗禁用/.test(noCh.refused), noCh.refused);
    return out;
  });

  for (const s of r.steps) (s.pass ? ok : fail)(`${s.name}${s.detail ? ' — ' + s.detail : ''}`);
  const fatal = errs.filter((e) => /edit\.js/.test(e));
  if (fatal.length) fail(`页面抛错：${fatal[0]}`);
  await br.close();
  srv.close();
}

console.log(bad ? `\n${bad} 处失败` : '\n试改闸全部通过');
process.exit(bad ? 1 : 0);
