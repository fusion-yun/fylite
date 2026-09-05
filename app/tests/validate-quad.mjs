// 两套求积，一个积分：差从哪一步来，哪一半会随加密消失（T-M11）
//
// ★★WHAT THIS IS ABOUT.  With the beam on, the 含时演化 bar prints the
// absorbed power TWICE and the two numbers disagree by about 1 %:
// `shell_sum(p_dep, dV)` over the deposition shells says one thing, and the
// volume integral the march itself performs on its metric ladder says
// another.  The previous batch deliberately did NOT normalise one onto the
// other — renormalising turns a checkable disagreement into an invisible
// choice — and this gate is what makes keeping them both a claim rather
// than a shrug.
//
// ★★THE CLAIM, and since T-M14 it is a different claim from the one this
// gate was born with.  The difference between the two numbers used to be
// two things; the remap change removed one of them BY CONSTRUCTION:
//
//   1. A CALIBRE difference.  The ladder stops at psi_N = `edgePsin`
//      (0.95); the shells run to 1.  Whatever is deposited outside the
//      ladder's outermost surface is power the march never receives, and
//      NO refinement of either grid recovers it.  Measured: ~1.1 % of the
//      absorbed power, growing slightly with the ladder (it converges on
//      how much power is really out there).  T-M13 made the edge a
//      declared, movable calibre; this half IS that calibre.
//   2. A DISCRETISATION difference — GONE (T-M14).  The march used to
//      point-sample a shell AVERAGE onto its nodes and then apply the
//      trapezoid (measured 3.16 % at 21 surfaces, 1.68 % at 61, converging
//      but never zero).  The remap is now a conservative per-interval
//      integration: each node's dual cell is accounted against the
//      kernel's own traced volumes (`shell_table`, whose per-shell volumes
//      TELESCOPE — they are differences of one cumulative V(psi_N), so any
//      partition sums exactly), and the nodal value is solved back through
//      the march's own trapezoid weight.  The ladder integral is therefore
//      IDENTICALLY `shell_sum - outside`, and what remains of this half is
//      floating-point roundoff — asserted below at 1e-9 where 3.16 % stood.
//
// So the raw gap no longer shrinks TOWARDS minus the calibre — it EQUALS
// minus the calibre, at every rung, and the gate asserts that identity
// directly.  ★The old rule is kept in the oracle as a NEGATIVE CONTROL:
// re-computing the ladder integral by point sampling still lands ~3 %
// away, which is the measured size of the bias the conservative remap
// removed — a gate that only asserted "the gap is small now" could be
// passed by a broken export.
//
// ★★THE ORACLE DOES NOT GO THROUGH THE PAGE'S PATH.  The nodal source the
// march integrated travels in the file (`fylite:on_ladder`, T-M14), and
// the ladder integral is re-taken here with `numpy.trapezoid` — an
// independently written trapezoid, not the kernel's.  The conservation
// identity is checked from the file's three raw numbers.  If the page's
// number were something other than the integral it says it is, this is
// where it would show.
//
//   node app/tests/validate-quad.mjs [--playwright DIR] [--chrome BIN]
//                                    [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';

//: ★the ladder arrays travel at 7 significant digits (this file's usual
//: rounding), so a re-integration of them cannot agree better than about
//: 1e-7.  Measured here: 2.5e-9 … 9.2e-8.  1e-6 sits an order above that
//: floor and four orders below the ~1 % the gate is about.
const TOL = 1e-6;

const BASECASE = {
  geometry: 'device', 'ch-heat': true, 'ch-density': false,
  'ch-current': true, nsteps: 2, nlev: 31, dt: 0.001, dttarget: 0,
  fuel: 0, alpha: false, brem: true, ohmic: true, bootstrap: true,
  zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, closure: 0,
  chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3, edgeti: 0.3, edgene: 0.5,
  ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0.5, ip: 400, couple: 0,
  freeiter: 600, species: '', cimp: 0, wave: false, edgepsin: 0.95,
  pe: 2, pi: 2, dep: 0, depw: 0.3, icd: 0, lh: false,
  beam: true, beampower: 4, beamenergy: 60, beamrtan: 1.26, beamz: 0,
  beamwidth: 0.10, beamdir: '1', beamstop: 'janev',
  beamf1: 1, beamf2: 0, beamf3: 0, beamshells: 24, beamorbit: true,
};

//: ★the LADDER is refined and the shells are held: the ladder is the coarse
//: host of the two, and refining both at once would leave "which one was
//: it" unanswered.
//: ★11 was a rung here until v108.  The boundary-rule fix (T-D6′) made the
//: device equilibrium DIVERTED — bigger, separatrix-bounded — and at 11
//: surfaces the point-sampled ladder's discretisation error is no longer
//: even signed consistently: measured 1.10 % at 11 faces against 3.16 %
//: at 21 (an accidental cancellation, not a better answer), which breaks
//: every monotonicity claim below without saying anything about the
//: quadrature.  The refinement claims need rungs on the asymptotic
//: branch, so the ladder starts at 21.
const LADDER = [21, 41, 61];
//: ★and the other knob, for the check that says refining the WRONG grid
//: makes it worse — without which "refine something until it passes" would
//: be a strategy.
const SHELLS = [16, 48];

const CASES = [
  ...LADDER.map((n) => ({ id: 'L' + n, nlev: n, nsh: 24, cfg: { nlev: n } })),
  ...SHELLS.map((n) => ({ id: 'S' + n, nlev: 21, nsh: n,
                          cfg: { nlev: 21, beamshells: n } })),
  //: ★T-M13 — the ladder's outer edge is a CONTROL now (capped < 1).  One
  //: rung at 0.97 against the 0.95 the other cases hold: the calibre gap
  //: must FOLLOW the control, which is what turns「写死 0.95」into a
  //: declared calibre a reader can move.
  { id: 'E97', nlev: 21, nsh: 24, cfg: { nlev: 21, edgepsin: 0.97 } },
];

const OUT = mkdtempSync(join(tmpdir(), 'qd-'));
const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
if (!await seedDevice(ctx, 'east')) {
  console.error(missingDeviceMessage('east'));
  process.exit(2);
}
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
await page.goto(BASE + 'pages/model.html?device=east',
                { waitUntil: 'networkidle' });
//: ★★等**留得住的信号**，不等状态行（2026-09-05 真浏览器实测改）。这里从前等的是
//: 状态行里出现「就绪 / Ready」，而那句话在页面上只存在一瞬：各栏的初始状态紧接着把它
//: 换成自己的（实测 0.49 s 时已是「待机——摆好目标，合开关起放电」，`status.kernel_ready`
//: 在 MutationObserver 里一次痕迹也没留下）。于是这一等就是 180 秒的超时，而**页面本身
//: 一直是好的**——`FyDesignReady` 与 `FYLITE_KERNEL` 都按时到位。状态行是给读者看的：
//: 它会改词、会被覆盖、还随语言变，判据挂在它上面就是把闸子挂在措辞上。
await page.waitForFunction(() => !!self.FYLITE_KERNEL, null, { timeout: 180000 });

const RUN = '#model-evolve-run';
//: T-M13's cap, read off the live control while the page is open — the
//: assertion itself runs after the browser is gone
const EDGE_MAX = await page.evaluate(
  () => +document.getElementById('model-evolve-edgepsin').max);
const got = {};
for (const c of CASES) {
  const cfg = { ...BASECASE, ...c.cfg };
  await page.evaluate((v) => {
    const rank = (id) => (id === 'geometry' ? 0
                          : (id === 'beam' || id === 'lh') ? 1
                          : /^(beam|lh)/.test(id) ? 2 : 0);
    Object.keys(v).sort((a, b) => rank(a) - rank(b)).forEach((id) => {
      const el = document.getElementById('model-evolve-' + id)
                 || document.getElementById('model-' + id);
      if (!el) throw new Error('no control evolve-' + id);
      if (el.type === 'checkbox') el.checked = !!v[id];
      else el.value = v[id];
      el.dispatchEvent(new Event(
        el.tagName === 'SELECT' || el.type === 'checkbox' ? 'change' : 'input'));
    });
  }, cfg);
  await page.waitForFunction((k) => !document.querySelector(k)
    .classList.contains('stop'), RUN, { timeout: 300000 });
  await page.click(RUN);
  await page.waitForFunction((k) => document.querySelector(k)
    .classList.contains('stop'), RUN, { timeout: 60000 }).catch(() => {});
  await page.waitForFunction(
    () => /完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
        .textContent || ''), null, { timeout: 900000 });
  const screen = await page.evaluate(() => ({
    state: (document.querySelector('[data-bar="evolve"] .funcbar-state')
            || {}).textContent || '',
    quad: (document.getElementById('model-evolve-quad-note') || {})
          .textContent || '',
    quadHidden: !!(document.getElementById('model-evolve-quad-note') || {})
                 .hidden,
    scalars: (document.getElementById('model-evolve-scalars') || {})
             .textContent || '',
  }));
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${c.id}.json`);
  await dl.saveAs(f);
  got[c.id] = { case: c, screen, file: f };
}

//: ★and one run with NO beam, so the paragraph about a quadrature nobody
//: performed is not on the screen
await page.evaluate(() => {
  const e = document.getElementById('model-evolve-beam');
  e.checked = false; e.dispatchEvent(new Event('change'));
});
await page.waitForFunction((k) => !document.querySelector(k)
  .classList.contains('stop'), RUN, { timeout: 300000 });
await page.click(RUN);
await page.waitForFunction((k) => document.querySelector(k)
  .classList.contains('stop'), RUN, { timeout: 60000 }).catch(() => {});
await page.waitForFunction(
  () => /完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 900000 });
const noBeam = await page.evaluate(() => ({
  quadHidden: !!(document.getElementById('model-evolve-quad-note') || {})
               .hidden,
  scalars: (document.getElementById('model-evolve-scalars') || {})
           .textContent || '',
}));
await br.close();

// --- the oracle: the same integral, written again in another host ---------

const PY = `
import json, sys
import numpy as np


def run(path):
    doc = json.load(open(path))
    b = doc["fylite:beam"]
    q = doc["fylite:quadrature"]["fylite:beam"]
    ts = doc["fylite:result"]["equilibrium"]["time_slice"][0]["profiles_1d"]
    rho = np.asarray(ts["rho_tor"], float)
    vprime = np.asarray(ts["dvolume_drho_tor"], float)
    lad_psin = np.asarray(ts["fylite:psi_norm"], float)
    psin = np.asarray(b["fylite:psin"], float)
    #: ★p_e + p_i, because that is what the march summed — not p_dep, which
    #: is the same array by a different route.  Checking the route the march
    #: took is the point.
    pdep = (np.asarray(b["fylite:p_electron"], float)
            + np.asarray(b["fylite:p_ion"], float))
    #: ★T-M14: the nodal source the march integrated is IN the file, and
    #: numpy's OWN trapezoid re-takes the integral — nothing in this line
    #: came from the code under test
    on_ladder = np.asarray(q["fylite:on_ladder"], float)
    ladder = float(np.trapezoid(on_ladder * vprime, rho))
    #: the OLD rule, kept as a negative control: point-sample the shell
    #: averages, then trapezoid.  Its distance from the reported integral
    #: is the measured size of the bias the conservative remap removed.
    old_rule = float(np.trapezoid(np.interp(lad_psin, psin, pdep) * vprime,
                                  rho))
    shell = float(q["fylite:shell_sum"])
    out = float(q["fylite:outside_ladder"])
    inside = shell - out
    #: the deposited power that sits in shells whose CENTRE is beyond the
    #: ladder's edge — a cruder split than the worker's (which inserts the
    #: edge as a knot and asks the kernel for the traced volumes), and it is
    #: here only to bound the worker's number, not to replace it
    dvol = np.asarray(b["fylite:dvolume"], float)
    edge = float(q["fylite:edge_psin"])
    crude = float(np.sum((np.asarray(b["fylite:p_deposited"], float)
                          * dvol)[psin > edge]))
    return {
        "n_ladder": int(rho.size), "n_shell": int(psin.size),
        "shell": shell, "ladder_file": float(q["fylite:ladder_integral"]),
        "ladder_recomputed": ladder, "outside": out, "edge": edge,
        "ladder_err": abs(ladder - float(q["fylite:ladder_integral"]))
                      / max(abs(ladder), 1e-300),
        "old_bias": abs(old_rule - float(q["fylite:ladder_integral"]))
                    / max(abs(float(q["fylite:ladder_integral"])), 1e-300),
        "gap": (float(q["fylite:ladder_integral"]) - shell) / shell,
        "calibre": out / shell,
        "disc": (float(q["fylite:ladder_integral"]) - inside) / inside,
        #: the decomposition is an IDENTITY and it has to close exactly:
        #: ladder == (shell - outside) * (1 + disc)
        "closes": abs(inside * (1.0 + (float(q["fylite:ladder_integral"])
                                       - inside) / inside)
                      - float(q["fylite:ladder_integral"]))
                  / max(abs(shell), 1e-300),
        "crude_outside": crude,
        #: ★the ladder covers LESS volume than the shells and still
        #: integrates MORE power — the fact that makes "it is just the
        #: missing edge" wrong on its own
        "vol_ladder": float(np.trapezoid(vprime, rho)),
        "vol_shell": float(np.sum(dvol)),
        "psin_max": float(lad_psin[-1]),
    }


print(json.dumps({k: run(v) for k, v in json.loads(sys.argv[1]).items()}))
`;

const files = Object.fromEntries(
  Object.entries(got).map(([k, v]) => [k, v.file]));
let ref;
try {
  ref = JSON.parse(execFileSync('python3', ['-c', PY, JSON.stringify(files)],
                                { encoding: 'utf8', maxBuffer: 1 << 28 }));
} catch (e) {
  console.error('原生对照跑不起来：\n' + (e.stderr || e.message));
  process.exit(2);
}

// --- assertions ------------------------------------------------------------

let bad = 0, n = 0;
const ok = (cond, what, detail) => {
  n += 1;
  if (!cond) { bad += 1; console.log('  ✗ ' + what + (detail ? ' — ' + detail : '')); }
  else console.log('  ✓ ' + what + (detail ? ' — ' + detail : '')); };
const pc = (v) => (100 * v).toFixed(4) + ' %';
const pcSigned = (v) => (100 * v).toPrecision(3) + ' %';

console.log('\n〔一〕每一档都算成了，两个数都在文件里，而且都不是零');
for (const c of CASES) {
  const r = ref[c.id];
  ok(/完成|Done/.test(got[c.id].screen.state), `${c.id}：算成了`,
     `梯子 ${r.n_ladder} 点 · 壳层 ${r.n_shell} 个`);
  ok(r.shell > 0 && r.ladder_file > 0 && r.outside > 0,
     `${c.id}：壳层求积 / 梯子体积分 / 圈外功率三个数都非零`,
     `${(r.shell / 1e6).toFixed(6)} / ${(r.ladder_file / 1e6).toFixed(6)} / ` +
     `${(r.outside / 1e6).toFixed(6)} MW`);
}

console.log(`\n〔二〕页面报的「梯子体积分」确实是那个积分（判据 ${TOL}，` +
            '来源：文件里的节点源按 12 位有效截断）');
for (const c of CASES)
  ok(ref[c.id].ladder_err < TOL,
     `${c.id}：对文件里的节点源用 numpy 自己的梯形重算`,
     ref[c.id].ladder_err.toExponential(2));

console.log('\n〔二丙〕★负对照：旧的点采样规则重算出来仍差 ~3 %——' +
            '守恒重映射消掉的偏差是真的，不是导出改了个名字');
for (const c of CASES)
  ok(ref[c.id].old_bias > 0.005,
     `${c.id}：点采样 + 梯形与报告的积分差得远（> 0.5 %）`,
     pcSigned(ref[c.id].old_bias));

console.log('\n〔二乙〕分解是一个恒等式，它必须严格闭合');
for (const c of CASES)
  ok(ref[c.id].closes < 1e-12,
     `${c.id}：梯子 = （壳层 − 圈外）×（1 + 离散差）`,
     ref[c.id].closes.toExponential(2));

console.log('\n〔三〕两套求积不是同一个域：梯子体积更小，功率也只小圈外那一份' +
            '——不再多算（T-M14 之前它反而更大）');
for (const c of CASES) {
  const r = ref[c.id];
  ok(r.vol_ladder < r.vol_shell && r.ladder_file < r.shell,
     `${c.id}：体积 ${r.vol_ladder.toFixed(3)} < ${r.vol_shell.toFixed(3)} m³，` +
     '功率同向',
     `功率差 ${pcSigned(r.gap)}`);
  ok(Math.abs(r.psin_max - r.edge) < 1e-9,
     `${c.id}：梯子的最外一个节点就是 ψ_N = ${r.edge}`,
     r.psin_max.toFixed(6));
}
//: ★the worker's split is the kernel's traced volumes with the ladder edge
//: inserted as a knot; the crude one bins by shell centre.  They must agree
//: to within about one shell, which is what says the worker's number is a
//: split of the same thing and not a different quantity.
for (const c of CASES) {
  const r = ref[c.id];
  const d = Math.abs(r.outside - r.crude_outside) / r.shell;
  ok(d < 0.01, `${c.id}：圈外功率与「按壳层中心粗分」相差不到一个壳层`,
     `${(r.outside / 1e6).toFixed(6)} vs ${(r.crude_outside / 1e6).toFixed(6)} MW`);
}

console.log('\n〔四〕★★口径差是一个固定偏置：加密梯子它不缩，反而略涨');
const cal = LADDER.map((k) => ref['L' + k].calibre);
ok(cal.every((v) => v > 0.008 && v < 0.013),
   `各档梯子上口径差都落在 0.8–1.3 % 之间`, cal.map(pc).join(' · '));
ok(cal[cal.length - 1] >= cal[0],
   '最细那档的口径差不小于最粗那档——它不是一个会被加密消掉的东西',
   `${pc(cal[0])} → ${pc(cal[cal.length - 1])}`);
ok(cal.every((v, i) => i === 0 || v >= cal[i - 1] - 1e-12),
   '而且它逐档单调不减（它在收敛到 ψ_N > 0.95 那一圈里真正有多少功率）',
   cal.map(pc).join(' → '));

console.log('\n〔四乙〕★T-M13：外边界是控件（ψ_N < 1），口径差随它走');
{
  const e97 = ref.E97, l21 = ref.L21;
  ok(Math.abs(e97.edge - 0.97) < 1e-9 && Math.abs(e97.psin_max - 0.97) < 1e-9,
     '0.97 档：会话文件记的外边界与梯子最外节点都站在 0.97 上',
     `edge ${e97.edge} · psin_max ${e97.psin_max.toFixed(6)}`);
  ok(e97.calibre > 0 && e97.calibre < l21.calibre,
     '外边界往 1 推，口径差缩小——它是一个随控件走的声明口径，不再是常数',
     `0.95 档 ${pc(l21.calibre)} → 0.97 档 ${pc(e97.calibre)}`);
  ok(e97.vol_ladder > l21.vol_ladder && e97.vol_ladder < l21.vol_shell,
     '梯子体积随边界外推变大，但仍小于壳层整域',
     `${l21.vol_ladder.toFixed(3)} → ${e97.vol_ladder.toFixed(3)} ` +
     `< ${l21.vol_shell.toFixed(3)} m³`);
  ok(EDGE_MAX < 1.0, '控件自己的上限停在 1.0 之下——ψ_N = 1 不是梯子能站的磁面',
     `max = ${EDGE_MAX}`);
}

console.log('\n〔五〕★★T-M14：离散差按构造为零——每一档都在浮点噪声以内');
//: ★1e-9 is six orders below the 3.16 % the point-sampled rule measured
//: here, and six above float roundoff: the identity holds because the
//: kernel's traced shell volumes TELESCOPE (each is a difference of one
//: cumulative V(psi_N)), so the operator's dual-cell partition sums to
//: exactly the shells' own volumes — no partition noise to allow for.
for (const k of LADDER)
  ok(Math.abs(ref['L' + k].disc) < 1e-9,
     `L${k}：|离散差| < 1e-9（点采样规则在此档曾测得 ` +
     `${pcSigned(ref['L' + k].old_bias)}）`,
     ref['L' + k].disc.toExponential(2));

console.log('\n〔五乙〕原始差不再「奔向」−口径差——它就是 −口径差，每一档');
const gaps = LADDER.map((k) => ref['L' + k].gap);
for (let i = 0; i < LADDER.length; i++)
  ok(Math.abs(gaps[i] + cal[i]) < 1e-9,
     `L${LADDER[i]}：原始差 = −口径差（1e-9）`,
     `${pcSigned(gaps[i])} vs −${pc(cal[i])}`);

console.log('\n〔六〕壳层加密与否都改变不了恒等式；旧规则在同一变化下会变得更糟' +
            '（负对照——「随便加密到通过」在旧规则下不是一条路，在新规则下没有东西可通）');
for (const k of SHELLS)
  ok(Math.abs(ref['S' + k].disc) < 1e-9,
     `S${k}：梯子不动、壳层换档，|离散差| 仍 < 1e-9`,
     ref['S' + k].disc.toExponential(2));
ok(ref.S48.old_bias > ref.S16.old_bias,
   `★旧点采样规则在壳层 ${SHELLS.join(' → ')} 下偏差反而涨——被采样的剖面加细`
   + '不是把采样它的尺子加细，守恒规则没有这个失败模式',
   `${pcSigned(ref.S16.old_bias)} → ${pcSigned(ref.S48.old_bias)}`);
ok(Math.abs(ref['S16'].shell - ref['S48'].shell) / ref['S16'].shell < 1e-6,
   '壳层求积本身几乎不随壳层数动（它按构造 = P_inj × 吸收份额）',
   `${(ref.S16.shell / 1e6).toFixed(6)} vs ${(ref.S48.shell / 1e6).toFixed(6)} MW`);

console.log('\n〔七〕页面说得出这一栏的口径是哪一个，也印得出两半');
const note = got.L31 ? got.L31.screen.quad : got.L21.screen.quad;
ok(!got.L21.screen.quadHidden && note.length > 200,
   '束开着时那一段注记在屏幕上', note.slice(0, 40) + '…');
ok(/梯子体积分/.test(note) && /口径/.test(note),
   '注记里点名「口径是梯子体积分」');
ok(/没有归一化/.test(note),
   '并且明说没有归一化——两个数都留着');
ok(/守恒/.test(note) && /恒等于/.test(note),
   '★T-M14：注记说清重映射是守恒的、两数之差就是口径差本身');
ok(/0\.95/.test(note), '注记里写出了梯子停在哪一面', 'ψ_N = 0.95');
for (const c of CASES) {
  const s = got[c.id].screen.scalars;
  ok(/壳层求积 \/ 梯子体积分/.test(s) && /口径差/.test(s) && /离散差/.test(s),
     `${c.id}：终态读数里三行都在（两个数 · 口径差 · 离散差）`);
}
//: ★the screen's numbers are the file's numbers, not a second calculation
{
  const s = got.L61.screen.scalars.replace(/\s+/g, '');
  const want = (ref.L61.shell / 1e6).toFixed(3) + '/' +
               (ref.L61.ladder_file / 1e6).toFixed(3);
  ok(s.includes(want), '屏幕上那一行的两个数就是文件里的两个数', want);
}
ok(noBeam.quadHidden && !/口径差/.test(noBeam.scalars),
   '★关掉束之后那一段与那三行都不在了（没跑过的求积不该有段落）');

console.log('\n〔八〕页面没有报错');
ok(errs.length === 0, '没有 pageerror / console error',
   errs.slice(0, 3).join(' | '));

console.log(`\n${n - bad}/${n} 项通过`);
process.exit(bad ? 1 : 0);
