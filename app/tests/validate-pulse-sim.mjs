// Gate for the two pulse scenarios: 脉冲设计 (whole pulse) and 交互仿真
// (driven live).  FYL-DESIGN-09 is the design; this is the part of it a
// machine can hold to.
//
//   node app/tests/validate-pulse-sim.mjs [--url http://127.0.0.1:8767/app/]
//                                         [--playwright DIR] [--chrome BIN]
//
// ★★WHAT IS BEING GATED IS MOSTLY WHAT THE PAGES SAY ABOUT THEIR OWN
// NUMBERS.  Neither page computes physics — the trapezoid, the boundary, the
// 0-D traces, the coil design and the free-boundary solve are all kernel
// entries with gates of their own.  What only a browser can check is the pair
// of distinctions these two pages exist to keep:
//
//   1. 已解片 vs 插值片 (D-8).  The play-head runs over ~120 instants and the
//      equilibrium is solved at a handful.  A page that drew the target
//      boundary in the colour of a solved one would be reporting a wrong
//      number as a right one — the failure `validate-design.mjs` was written
//      for, one page over.
//   2. 滑块改的是未来 (D-12).  In simulation mode a slider must change what
//      happens NEXT and leave the history alone.  This cannot be seen in a
//      picture: it is a statement about two arrays, so the page publishes its
//      history and the gate compares them point by point.
//
// Plus the two failures that were actually found while building the pages,
// and are therefore the ones most likely to come back:
//
//   * the voltage column indexed by the PASSIVE count instead of the channel
//     count — every peak came back `NaN`, which reads as "no limit data";
//   * the verification instants spread over the index range rather than over
//     the PHASES, which put all three inside the flat top and checked nothing
//     about either ramp.

import { browser, flag } from './_browser.mjs';

const BASE = flag('url') || 'http://127.0.0.1:8767/app/';

let bad = 0;
const fail = (m, why) => { console.log('  FAIL ' + m + (why ? '  — ' + why : '')); bad++; };
const ok = (m, why) => console.log('  ok   ' + m + (why ? '  — ' + why : ''));
const check = (cond, m, why) => (cond ? ok(m, why) : fail(m, why));

const br = await browser();
const ctx = await br.newContext({ viewport: { width: 1400, height: 1000 } });
const errors = [];

/** One page, with its console kept — a page error is a failure by itself. */
async function open(path) {
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(`${path}: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`${path}: console ${m.text()}`);
  });
  await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
  return page;
}

const wait = (page, fn, ms = 180000, arg = null) =>
  page.waitForFunction(fn, arg, { timeout: ms });

// ==========================================================================
console.log('〔一〕脉冲设计：一条时间轴，解过的片与没解的片分得清');
// ==========================================================================

const P = await open('pages/pulse_design.html#design');
//: ★读的是这一条栏自己的状态行，不是页面那一条。合并之后一页有六条栏而只有
//: 一条页面状态行——它说的是「最后开口的那条栏」，开页时那是自己跑完的击穿栏。
//: 「这一栏准备好了没有」是栏的事实，所以问栏。
const barState = (page, bar) => page.evaluate(
  (b) => (document.querySelector(`[data-bar="${b}"] .funcbar-state`) || {})
    .textContent || '', bar);
await wait(P, (b) => {
  const e = document.querySelector(`[data-bar="${b}"] .funcbar-state`);
  return e && /ready|就绪/i.test(e.textContent);
}, 60000, 'pulse').catch(() => fail('页面就绪', '内核握手没有到'));

//: three checks, so the three phases each get one
await P.evaluate(() => {
  const set = (id, v) => { const e = document.getElementById(id);
    e.value = v; e.dispatchEvent(new Event('input')); };
  set('pulse_design-pulse-nverify', '3');
});
await P.click('#pulse_design-pulse-run');
await wait(P, (b) => {
  const e = document.querySelector(`[data-bar="${b}"] .funcbar-state`);
  return e && /designed|已设计|done|完成/i.test(e.textContent);
}, 180000, 'pulse').catch(() => fail('整条脉冲跑完', '状态行没有报完成'));

const pub = await P.evaluate(() => {
  const b = self.FyScenario.pages.pulse_design.bus.pulse;
  return typeof b === 'function' ? b() : b;
});
check(!!pub && pub.checks && pub.checks.length === 3,
      '要求校验几片就解几片', pub ? `${pub.checks.length} 片` : '没有产物');

//: ★the claim: the verified instants are spread over the PHASES.  Evenly
//: spaced indices put all three inside the flat top on a default pulse.
if (pub && pub.checks) {
  const [t0, t1, t2, t3] = pub.phases;
  const inPhase = (t) => (t <= t1 ? 'up' : (t <= t2 ? 'flat' : 'down'));
  const got = [...new Set(pub.checks.map((c) => inPhase(c.t)))].sort();
  check(got.length === 3, '三片落在三个相位里，不是三片都在平顶',
        pub.checks.map((c) => `${c.t.toFixed(2)}s·${inPhase(c.t)}`).join(' '));
  //: and each of them reports BOTH shapes — "所要求" beside "实际得到"
  const both = pub.checks.every((c) => c.target && c.shape &&
    isFinite(c.target.a) && isFinite(c.shape.a));
  check(both, '每一片都同时报出目标位形与实现位形');
}

//: ★the voltage column: finite, and per CHANNEL
if (pub && pub.peaks) {
  const finite = pub.peaks.every((p) => isFinite(p.i) && isFinite(p.v));
  check(finite, '逐通道电流与电压峰值都是有限数（不是 NaN）',
        pub.peaks.map((p) => p.v.toFixed(1)).join(' '));
  check(pub.peaks.length === pub.nch,
        '表里的行数就是通道数', `${pub.peaks.length} / ${pub.nch}`);
}

//: ★没有声明限值就没有判定 — and the page says which of the two it is
const undecl = await P.evaluate(() => ({
  rows: [...document.querySelectorAll('#pulse_design-pulse-channels tr')]
    .map((r) => r.lastElementChild.textContent.trim()),
  src: document.getElementById('pulse_design-pulse-limits-src').textContent,
}));
check(undecl.rows.length > 0 && undecl.rows.every((v) => /未声明|no limit/i.test(v)),
      '未声明限值时逐通道报「限值未声明」，不报「在限内」',
      undecl.rows[0]);
check(/装置描述|device description/i.test(undecl.src),
      '并说明限值为什么没有：装置描述里没有这张表');

//: with a ceiling the verdicts become verdicts
const decl = await P.evaluate(() => {
  const e = document.getElementById('pulse_design-vcap');
  e.value = '20'; e.dispatchEvent(new Event('input'));
  //: the table is redrawn by the next run; re-run cheaply by asking the
  //: controller's own redraw through a change of the play-head
  const s = document.getElementById('pulse_design-pulse-slice');
  s.dispatchEvent(new Event('input'));
  return null;
});
void decl;

//: ★已解片 vs 插值片, the page's core sentence
if (pub && pub.checks && pub.checks.length) {
  const tSolved = pub.checks[0].t;
  const noteAt = async (t) => P.evaluate((tt) => {
    const bus = self.FyScenario.pages.pulse_design.bus.pulse;
    void bus;
    const s = document.getElementById('pulse_design-pulse-slice');
    //: the slider indexes a uniform 0..NT-1 grid over the whole pulse
    const t0 = +document.getElementById('pulse_design-t_bd').value;
    const t1 = +document.getElementById('pulse_design-t_end').value;
    const k = Math.round((tt - t0) / (t1 - t0) * (+s.max));
    s.value = String(k);
    s.dispatchEvent(new Event('input'));
    var e = document.getElementById('pulse_design-pulse-slice-note');
    return { state: e.getAttribute('data-slice'), text: e.textContent };
  }, t);
  const solved = await noteAt(tSolved);
  check(solved.state === 'solved',
        '停在校验过的时刻，面板说「已解片」', solved.text.slice(0, 60));
  //: an instant between two verified ones — deliberately NOT one of them
  const between = (pub.checks.length > 1)
    ? 0.5 * (pub.checks[0].t + pub.checks[1].t) : pub.checks[0].t + 0.9;
  const interp = await noteAt(between);
  check(interp.state === 'interpolated',
        '停在没解过的时刻，面板说「插值片（未解）」', interp.text.slice(0, 60));
}

await P.close();

// ==========================================================================
console.log('');
console.log('〔二〕交互仿真：开关起落，滑块改的是未来');
// ==========================================================================

const S = await open('pages/pulse_design.html#simulate');
await wait(S, (b) => {
  const e = document.querySelector(`[data-bar="${b}"] .funcbar-state`);
  return e && /Idle|待机/i.test(e.textContent);
}, 60000, 'sim').catch(() => fail('页面就绪', '状态行没有到待机'));

const history = () => S.evaluate(() => {
  const b = self.FyScenario.pages.pulse_design.bus.sim;
  return typeof b === 'function' ? b() : b;
});

check(/还没有解过平衡|No equilibrium/i.test(
        await S.evaluate(() => document.getElementById('pulse_design-sim-eq-note').textContent)),
      '还没解过平衡时，截面板自己说图上只有目标边界');

//: a coarse step so the run gets somewhere in a few seconds of wall clock
await S.evaluate(() => {
  const set = (id, v) => { const e = document.getElementById(id);
    e.value = v; e.dispatchEvent(new Event('input')); };
  set('pulse_design-sim-dt', '0.1'); set('pulse_design-sim-rate', '20'); set('pulse_design-sim-eqevery', '5');
});
await S.click('#pulse_design-sim-power');
await wait(S, () => {
  const b = self.FyScenario.pages.pulse_design.bus.sim;
  const h = typeof b === 'function' ? b() : b;
  return h && h.phase === 'flat' && h.ticks > 12;
}, 60000).catch(() => fail('合开关就起放电', '没有走到平顶'));

const before = await history();
check(before.phase === 'flat' && before.began.up !== undefined,
      '相位由开关推出：上升 → 平顶，并记下各自何时开始',
      `up@${before.began.up} flat@${before.began.flat}`);
check(before.ip[before.ip.length - 1] > 0.99 * before.ipTarget[0],
      'I_p 到了目标才算平顶',
      `${(before.ip[before.ip.length - 1] / 1e3).toFixed(1)} kA`);

//: ★★THE ONE THING ONLY THIS PAGE CAN GET WRONG: push a slider and the past
//: must not move.  Compared point by point, not by eye.
const nBefore = before.t.length;
const pauxBefore = before.paux.slice(0, nBefore);
await S.evaluate(() => {
  const e = document.getElementById('pulse_design-paux');
  e.value = '20'; e.dispatchEvent(new Event('input'));
});
await wait(S, (n) => {
  const b = self.FyScenario.pages.pulse_design.bus.sim;
  const h = typeof b === 'function' ? b() : b;
  return h && h.t.length > n + 6;
}, 60000, nBefore).catch(() => fail('推滑块之后仿真继续走', ''));
const after = await history();
const pastKept = pauxBefore.every((v, i) => v === after.paux[i]) &&
  before.t.every((v, i) => v === after.t[i]);
check(pastKept, '★推滑块只改未来：改动之前的历史逐点未变',
      `${nBefore} 点对齐`);
const newer = after.paux.slice(nBefore + 1);
check(newer.length > 0 && newer.every((v) => v > pauxBefore[nBefore - 1]),
      '而改动之后的每一步都用了新值',
      `${(pauxBefore[nBefore - 1] / 1e6).toFixed(1)} → ` +
      `${(newer[newer.length - 1] / 1e6).toFixed(1)} MW`);

//: ★the equilibrium beat says how old the picture is — waited for, because a
//: beat is every N steps and a solve costs about a second
await wait(S, () => {
  const b = self.FyScenario.pages.pulse_design.bus.sim;
  const h = typeof b === 'function' ? b() : b;
  return h && h.eqSolves > 0;
}, 60000).catch(() => fail('推进中真解过平衡', ''));
const eqNote = await S.evaluate(() =>
  document.getElementById('pulse_design-sim-eq-note').textContent);
check(/上次真解|Last real solve/i.test(eqNote),
      '截面板报出这一帧的边界是哪一次真解的', eqNote.slice(0, 70));

//: ★flux: undeclared swing is 未知, never a duration
const flux = await S.evaluate(() =>
  document.getElementById('pulse_design-sim-fluxtab').textContent);
check(/未知|unknown/i.test(flux),
      '未声明摆幅时「还能维持」报未知，不给一个数');

//: ★opening the switch is a controlled ramp-down, and it ends
await S.click('#pulse_design-sim-power');
await wait(S, () => {
  const b = self.FyScenario.pages.pulse_design.bus.sim;
  const h = typeof b === 'function' ? b() : b;
  return h && (h.phase === 'down' || h.phase === 'end');
}, 30000).catch(() => fail('断开关进入下降沿', ''));
const down = await history();
check(down.phase === 'down' || down.phase === 'end',
      '断开关＝受控下降沿（不是急停）', down.phase);
await wait(S, () => {
  const b = self.FyScenario.pages.pulse_design.bus.sim;
  const h = typeof b === 'function' ? b() : b;
  return h && h.phase === 'end';
}, 90000).catch(() => fail('下降沿走完就结束', ''));
const end = await history();
check(end.phase === 'end' && end.ip[end.ip.length - 1] === 0,
      '结束时电流确实到零', `${end.ticks} 步`);
check(!(await S.evaluate(() => document.getElementById('pulse_design-sim-power').checked)),
      '结束之后开关自己回到断开位');
//: and a finished discharge cannot be resumed
await S.click('#pulse_design-sim-power');
const resumed = await S.evaluate(() => ({
  checked: document.getElementById('pulse_design-sim-power').checked,
  status: (document.querySelector('[data-bar="sim"] .funcbar-state') || {})
    .textContent || '',
}));
check(!resumed.checked, '结束之后合不上开关——那是另一炮，要重置',
      resumed.status.trim().slice(0, 40));

await S.close();

// ==========================================================================
console.log('');
check(errors.length === 0, '两页都没有 pageerror / console error',
      errors.slice(0, 3).join(' | '));
await ctx.close();
await br.close();

console.log('');
console.log(bad ? `FAILED (${bad})` : 'PASS');
process.exit(bad ? 1 : 0);
