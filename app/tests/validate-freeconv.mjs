// 自由边界平衡：解出来的，还是跑完了？——含时演化栏与解释栏的收敛自报
//
// ★★WHAT THIS GATE IS ABOUT.  `gs_free_solve` returns whatever it reached.
// A run that never met its tolerance comes back with `iterations = max_iter`
// and the last residual it happened to have, and until this batch every
// consumer on the 物理建模 page read those numbers as though they described
// a converged field.  That is not a hypothetical: the solver's droop trim
// RESETS its reference and keeps going every time it meets the tolerance, so
// a solve that is trimming runs to the cap and exits carrying a residual
// instead of stopping.  Measured on EAST's reference discharge, the tier the
// bar ships on: cap 20 → residual 6.9e-3, cap 600 (the shipped default) →
// 4.2e-5, cap 3000 → 3.9e-6, and it first meets 1e-9 at 7787 iterations.  So
// the default has NEVER converged, and nothing anywhere said so.
//
// ★★THE ORACLE, and why it is not the page's own flag.  What this gate must
// not do is ask the page whether it converged and then check that it said
// what it said.  So the verdict is checked against two facts established
// WITHOUT it:
//
//   1. a solve that stopped at `iterations < max_iter` cannot be changed by
//      raising the cap — the iteration it broke on is the same iteration at
//      any larger budget, so that run IS the terminal answer, by
//      construction rather than by assertion;
//   2. a solve that used its whole budget produced a DIFFERENT answer from
//      that one — a different minor radius, a different R0, a different q
//      profile.  "It did not converge" is then a fact about the field, and
//      the page's sentence is checked against the field rather than against
//      itself.
//
// ★★v108 (T-M16) split the verdict in three, and this gate's world changed
// with it.  The kernel now answers for itself: 达标 (residual within
// tolerance AND the mask unchanged over consecutive rounds), 稳态 (the
// answer stopped moving while mask-quantisation jitter floors the residual
// — the solver STOPS there, because more rounds change nothing), or 用尽预算.
// On EAST's reference discharge — now solved DIVERTED under the fixed
// boundary rule — the strict tolerance is unreachable (the floor is the
// mask's, measured ~6e-4) and the solver settles at ~111 rounds; so the
// old ladder "600 never converges, 7787 does" no longer exists, and what
// this gate asserts instead is: the low cap exhausts its budget and says
// so; the default cap lets the solver reach its OWN verdict (settled,
// stopped before the cap); and a vastly larger cap reproduces the settled
// answer bit-for-bit — which is fact 1 above, now about the settled exit.
//
// ★And the degenerate way to pass: report the same verdict always.  The
// cases must therefore land on BOTH sides — the low cap capped, the
// default settled — before either wording is inspected, which is the rule
// `app/tests/README.md` states for every gate that compares the ones that
// worked with the ones that did not.
//
//   node app/tests/validate-freeconv.mjs [--playwright DIR] [--chrome BIN]
//                                        [--url BASE]

import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const BASE = flag('url') || 'http://127.0.0.1:8767/app/';

//: ★the file writes 7 significant digits, so a relative difference above
//: 1e-6 is a difference in the ANSWER and not in the rounding.  1e-3 is
//: three orders above that floor — chosen so the assertion is about a
//: geometry a reader would notice, not about the last digit.
const ROUND = 1e-6, DIFF = 1e-3;
const TOL = 1e-9;                       // what the solver was asked for

//: ★the big cap is no longer "enough to converge" — nothing is, on this
//: machine: the mask-jitter floor (measured ~6e-4 against tol 1e-9) makes
//: the strict tolerance unreachable, and the solver SETTLES at ~111
//: rounds instead.  10000 exists to prove the settled exit is terminal:
//: 9400 extra rounds of budget must not change one digit.  It is also the
//: slider's ceiling, so this is a value a reader can actually set.
const CAP_LOW = 20, CAP_DEFAULT = 600, CAP_ENOUGH = 10000;

const BASECASE = {
  geometry: 'device', 'ch-heat': true, 'ch-density': false,
  'ch-current': true, nsteps: 10, nlev: 21, dt: 0.001, dttarget: 0,
  pe: 3, pi: 3, dep: 0, depw: 0.3, fuel: 0, alpha: false, brem: true,
  ohmic: true, bootstrap: true, icd: 0, zeff: 1.5, chiratio: 1, dchi: 0.3,
  pinch: 0, dpc: 0, closure: 0, chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3,
  edgeti: 0.3, edgene: 0.5, ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0.5,
  ip: 400, couple: 0, relax: 0.5, couplefixed: false, species: '', cimp: 0,
};

const CASES = [
  { name: `装置平衡 · 上限 ${CAP_LOW}（明显不够）`, id: 'low',
    cfg: { freeiter: CAP_LOW } },
  { name: `装置平衡 · 上限 ${CAP_DEFAULT}（本页默认——求解器在其内自行停下）`,
    id: 'default', cfg: { freeiter: CAP_DEFAULT } },
  { name: `装置平衡 · 上限 ${CAP_ENOUGH}（多给 9400 轮，必须一字不变）`,
    id: 'enough', cfg: { freeiter: CAP_ENOUGH } },
  //: the ALTERNATION: one free solve per block, so "did the equilibrium
  //: converge" is not a single fact and the report must not pretend it is
  { name: `装置平衡 · 耦合 · 上限 ${CAP_LOW}`, id: 'coupled',
    cfg: { freeiter: CAP_LOW, couple: 4 } },
  //: ★the tier that solves NOTHING.  A page that printed a convergence
  //: verdict for a Miller shape would be reporting on an iteration that
  //: never happened, which is its own kind of lie.
  { name: '解析几何（不解平衡）', id: 'miller',
    cfg: { geometry: 'miller', 'ch-current': false, freeiter: CAP_LOW } },
];

const OUT = mkdtempSync(join(tmpdir(), 'fc-'));
const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
//: EAST, because the device tier is the only one that solves a free
//: boundary and the bundled ITER descriptor carries no reference discharge
if (!await seedDevice(ctx, 'east')) {
  console.error(missingDeviceMessage('east'));
  process.exit(2);
}
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  if (m.type() === 'error' && !/favicon/.test(m.text()))
    errs.push('console: ' + m.text().slice(0, 200));
});

await page.goto(BASE + 'pages/model.html?device=east',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /就绪|Ready|完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 180000 });

const RUN = '#model-evolve-run';
const got = {};
for (const c of CASES) {
  const cfg = { ...BASECASE, ...c.cfg };
  await page.evaluate((v) => {
    //: `couplefixed` last, as everywhere: the page only lets it be ticked
    //: once the geometry and the cadence allow it
    const late = (id) => (id === 'couplefixed' ? 1 : 0);
    Object.keys(v).sort((a, b) => late(a) - late(b)).forEach((id) => {
      const el = document.getElementById('model-evolve-' + id)
                 || document.getElementById('model-' + id);
      if (!el) throw new Error('no control evolve-' + id);
      if (el.type === 'checkbox') el.checked = !!v[id];
      else el.value = v[id];
      el.dispatchEvent(new Event(
        el.tagName === 'SELECT' || el.type === 'checkbox' ? 'change' : 'input'));
    });
  }, cfg);
  //: ★the three-step discipline: the key must be idle, then it must enter
  //: the running state, and only then is "done" this run's "done".  The
  //: status line is the PREVIOUS run's until the new one starts.
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
    verdict: (document.getElementById('model-evolve-verdict') || {})
             .textContent || '',
    geo: (document.getElementById('model-evolve-geo') || {}).textContent || '',
  }));
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${c.id}.json`);
  await dl.saveAs(f);
  got[c.id] = { case: c, cfg, screen,
                doc: JSON.parse(readFileSync(f, 'utf8')) };
}

//: ★the 解释栏 runs the SAME free solve on the same tier, and it inverts a
//: chi off the metric that comes out of it.  One run, to check that a bar
//: which merely CONSUMES an equilibrium says what it is standing on too.
//: Its input is a reference profile, so it is fed the one the march at the
//: default cap just produced — read out of that run's own file, which is
//: also what makes the radii line up with the ladder it will invert on.
{
  const cp = got.default.doc['fylite:result'].core_profiles;
  const rho = got.default.doc['fylite:result']
              .equilibrium.time_slice[0].profiles_1d.rho_tor;
  const te = cp.profiles_1d.electrons.temperature;
  const ti = cp.profiles_1d.t_i_average;
  const ne = cp.profiles_1d.electrons.density;
  const rows = rho.map((r, i) =>
    `${r},${te[i] / 1e3},${ti[i] / 1e3},${ne[i] / 1e19}`);
  //: ★one row past the edge, holding the edge values.  The inversion
  //: REFUSES to extrapolate (rightly), and the interpretive bar's own solve
  //: is at slightly different profile parameters, so its ladder can reach a
  //: hair past this one's — a refusal there would be about the table, not
  //: about anything this gate is asking.
  const last = rho.length - 1;
  rows.push(`${rho[last] * 1.5},${te[last] / 1e3},${ti[last] / 1e3},` +
            `${ne[last] / 1e19}`);
  const csv = ['rho,TE,TI,NE'].concat(rows).join('\n');
  const [ch] = await Promise.all([page.waitForEvent('filechooser'),
                                  page.click('#model-ioimport')]);
  await ch.setFiles({ name: 'freeconv-ref.csv', mimeType: 'text/csv',
                      buffer: Buffer.from(csv) });
  await page.waitForFunction(
    () => /freeconv-ref\.csv/.test(
      (document.getElementById('model-status') || {}).textContent || ''),
    null, { timeout: 60000 });
}
await page.evaluate(() => {
  const set = (id, v) => {
    const el = document.getElementById('model-interp-' + id)
               || document.getElementById('model-' + id);
    if (!el) throw new Error('no control interp-' + id);
    el.value = v;
    el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input'));
  };
  set('geometry', 'device');
  set('nlev', 21);
  set('ip', 400);
});
const IKEY = '#model-interp-run';
await page.waitForFunction((k) => !document.querySelector(k)
  .classList.contains('stop'), IKEY, { timeout: 300000 });
await page.click(IKEY);
await page.waitForFunction((k) => document.querySelector(k)
  .classList.contains('stop'), IKEY, { timeout: 60000 }).catch(() => {});
await page.waitForFunction(
  () => /完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="interp"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 900000 });
const interpText = await page.evaluate(() => ({
  state: (document.querySelector('[data-bar="interp"] .funcbar-state')
          || {}).textContent || '',
  scalars: (document.getElementById('model-interp-scalars') || {})
           .textContent || '',
}));
//: the T-M9 note beside the iteration-budget slider, read once
got.noteText = await page.evaluate(() =>
  (document.querySelector('[data-i18n="e.freeiter_note"]') || {})
    .textContent || '');
await br.close();

// --- assertions --------------------------------------------------------

let bad = 0, n = 0;
const ok = (cond, what, detail) => {
  n += 1;
  if (!cond) { bad += 1; console.log('  ✗ ' + what + (detail ? ' — ' + detail : '')); }
  else console.log('  ✓ ' + what + (detail ? ' — ' + detail : ''));
};
const rec = (id) => got[id].doc['fylite:free_boundary'] || [];
const eqOf = (id) => got[id].doc['fylite:result'].equilibrium;
const aOf = (id) => eqOf(id)['fylite:a_minor'];
const r0Of = (id) => eqOf(id).vacuum_toroidal_field.r0;
const qOf = (id) => eqOf(id).time_slice[0].profiles_1d.q;
const relMax = (x, y) => {
  let m = 0;
  for (let i = 0; i < x.length; i++) {
    const d = Math.abs(x[i] - y[i]) / Math.max(Math.abs(y[i]), 1e-300);
    if (d > m) m = d;
  }
  return m;
};

console.log('\n〔一〕文件里的自报是自洽的');
for (const id of ['low', 'default', 'enough', 'coupled']) {
  const list = rec(id);
  ok(list.length > 0, `${id}：装置档写出了 ${list.length} 条自由边界记录`);
  const capped = got[id].cfg.freeiter;
  let good = true, why = '';
  list.forEach((r, i) => {
    const c = r['fylite:converged'], st = r['fylite:settled'],
          res = r['fylite:residual'],
          tol = r['fylite:tolerance'], it = r['fylite:iterations'],
          mx = r['fylite:max_iterations'];
    if (tol !== TOL) { good = false; why = `第 ${i} 条容差 ${tol} ≠ ${TOL}`; }
    if (mx !== capped) { good = false; why = `第 ${i} 条上限 ${mx} ≠ 控件 ${capped}`; }
    if (!(it > 0 && it <= mx)) { good = false; why = `第 ${i} 条轮数 ${it} 不在 (0, ${mx}]`; }
    //: ★the verdict is the KERNEL's three-way answer, and its laws are
    //: checkable from the record alone: 达标 implies the residual is
    //: within tolerance; 达标 and 稳态 exclude each other; a verdict
    //: reached before the cap means the solver stopped ITSELF.
    if (c && res > tol) {
      good = false;
      why = `第 ${i} 条自报达标而残差 ${res} > 容差 ${tol}`;
    }
    if (c && st) { good = false; why = `第 ${i} 条同时自报达标与稳态`; }
    if (!c && !st && it < mx) {
      good = false;
      why = `第 ${i} 条既非达标也非稳态，却在 ${it}/${mx} 轮就停了`;
    }
    if (r['fylite:block'] !== i) { good = false; why = `第 ${i} 条轮号 ${r['fylite:block']}`; }
  });
  ok(good, `${id}：三分自报守它自己的定律（达标⇒残差≤容差；达标⊕稳态；提前停⇒有判定），轮号连续、上限＝控件`, why);
}

console.log('\n〔二〕两边都非空——这道闸子不能靠「一律报同一种」通过');
const lowCapped = rec('low').filter((r) =>
  !r['fylite:converged'] && !r['fylite:settled']);
const defSettled = rec('default').filter((r) => r['fylite:settled']);
const enoughSettled = rec('enough').filter((r) => r['fylite:settled']);
ok(lowCapped.length === rec('low').length && lowCapped.length > 0,
   `上限 ${CAP_LOW}：${lowCapped.length}/${rec('low').length} 条报用尽预算（既非达标也非稳态）`,
   `残差 ${lowCapped[0] && lowCapped[0]['fylite:residual'].toExponential(2)}`);
ok(defSettled.length === rec('default').length && defSettled.length > 0,
   `上限 ${CAP_DEFAULT}（默认）：${defSettled.length}/${rec('default').length} 条报到稳态`,
   `残差地板 ${defSettled[0] && defSettled[0]['fylite:residual'].toExponential(2)}`);
ok(enoughSettled.length === rec('enough').length,
   `上限 ${CAP_ENOUGH}：同样全部到稳态`);

console.log('\n〔三〕不经页面自报的判据：默认那次自己停了，不够的那次跑满了');
const eR = rec('enough')[0], lR = rec('low')[0], dR = rec('default')[0];
//: ★this is the whole oracle for "that one IS the terminal answer": it
//: broke out before the cap, so the same run at any larger cap breaks on
//: the same iteration and produces the same field.  Nothing about it is
//: read off the page's flag.
ok(dR['fylite:iterations'] < dR['fylite:max_iterations'],
   `默认那次在到顶之前自己停了（到稳态）：${dR['fylite:iterations']}/${dR['fylite:max_iterations']} 轮`,
   `——再给更多轮数不会改变这张场`);
ok(lR['fylite:iterations'] === lR['fylite:max_iterations'],
   `不够那次把预算用光了：${lR['fylite:iterations']}/${lR['fylite:max_iterations']} 轮`);
//: ★the terminal-exit fact, by construction: 9400 extra rounds of budget
//: change neither the iteration it stopped on nor the residual it carried
ok(eR['fylite:iterations'] === dR['fylite:iterations']
   && eR['fylite:residual'] === dR['fylite:residual'],
   `多给 ${CAP_ENOUGH - CAP_DEFAULT} 轮预算，停在同一轮、带同一个残差`,
   `${eR['fylite:iterations']} 轮，残差 ${eR['fylite:residual'].toExponential(2)}`);
//: the low cap stopped mid-transit, so its residual is far above the floor
ok(lR['fylite:residual'] > 5 * dR['fylite:residual'],
   '上限不够那次停在半路，残差远高于稳态地板',
   `${lR['fylite:residual'].toExponential(2)} 对 ${dR['fylite:residual'].toExponential(2)}`);

console.log('\n〔四〕自报是关于那张场的事实，不只是一句话');
const dA = Math.abs(aOf('low') - aOf('default')) / aOf('default');
const dQ = relMax(qOf('low'), qOf('default'));
ok(dA > DIFF && dQ > DIFF,
   `不够那次解出的几何与稳态那张不同（判据 ${DIFF}，来源：会话文件 7 位有效 = ${ROUND}）`,
   `a 差 ${(100 * dA).toFixed(2)} %、q 逐点最大 ${(100 * dQ).toFixed(2)} %`);
const dA2 = Math.abs(aOf('default') - aOf('enough')) / aOf('enough');
const dQ2 = relMax(qOf('default'), qOf('enough'));
ok(dA2 <= ROUND && dQ2 <= ROUND,
   '默认与大上限解出的是同一张场——差值不高于文件的取整',
   `a 差 ${(100 * dA2).toFixed(6)} %、q 逐点最大 ${(100 * dQ2).toFixed(6)} %`);

console.log('\n〔五〕屏幕上说的，与文件里写的是同一件事');
//: ★three wordings, three facts: 「未达标」(capped) — 「稳态」(settled,
//: neither success nor failure) — 「达标」.  The settled row must NOT
//: read as a failure, and must not read as plain success either.
const NO = /未达标|没收敛|did not converge|ran out of iterations/;
const SETTLED = /稳态|settled/;
ok(NO.test(got.low.screen.geo),
   '上限不够时，截面旁那一行报的是「未达标」而不是一个数',
   got.low.screen.geo.replace(/^[\s\S]*自由边界收敛/, '').slice(0, 60));
ok(NO.test(got.low.screen.verdict),
   '上限不够时，终态读数下的结论明说这次用了没收敛的平衡',
   got.low.screen.verdict.slice(0, 44) + '…');
ok(!NO.test(got.default.screen.geo) && SETTLED.test(got.default.screen.geo),
   '默认档下，同一行报的是「到稳态自行停下」——既不是失败也不是达标',
   got.default.screen.geo.replace(/^[\s\S]*自由边界收敛/, '').slice(0, 80));
ok(!NO.test(got.default.screen.verdict),
   '默认档下，结论里没有那句警告（稳态不是失败）');
ok(!NO.test(got.enough.screen.geo) && SETTLED.test(got.enough.screen.geo),
   '大上限下报的仍是「稳态」——多给预算不改判定');
//: ★and the run must have SUCCEEDED — a failed run leaves the previous
//: run's numbers on the screen, and reading them would be scoring a run
//: that did not happen
ok(/完成|Done/.test(got.low.screen.state) && /完成|Done/.test(got.enough.screen.state),
   '两次都是算成了的（不是把上一次的屏幕当成这一次的答案）');
//: ★★T-M9's closure: the DEFAULT is a choice, and the page states it —
//: the budget note beside the slider names 600, names the settled exit,
//: and quotes the measured round it stops on.  The slider itself (ceiling
//: 10000) is the one-click escalation for cases that can truly converge.
const note = got.noteText;
ok(/600/.test(note) && SETTLED.test(note),
   'T-M9：滑块旁的注记写明默认 600 是预算、求解器在其内自行到稳态',
   note.slice(0, 80) + '…');

console.log('\n〔六〕耦合推进：一轮一次求解，一条一个自报');
const cl = rec('coupled');
ok(cl.length > 1, `耦合那次写出了 ${cl.length} 条记录（起始平衡 + 每轮回灌各一）`);
ok(cl.every((r) => !r['fylite:converged'] && !r['fylite:settled']),
   `${cl.length} 条全部报用尽预算（上限 ${CAP_LOW} 连稳态窗都装不下）`,
   cl.map((r) => r['fylite:residual'].toExponential(1)).join(' · '));
ok(new RegExp(`${cl.filter((r) => !r['fylite:converged'] && !r['fylite:settled']).length}`)
     .test(got.coupled.screen.verdict)
   && new RegExp(`${cl.length}`).test(got.coupled.screen.verdict),
   '结论报出的是「几次求解里几次没到」而不是一句笼统的话',
   got.coupled.screen.verdict.slice(0, 60) + '…');

console.log('\n〔七〕不解平衡的那一档，什么也不报');
ok(rec('miller').length === 0,
   '解析几何档没有自由边界记录（那一档的形状是给定的，不是收敛来的）');
ok(!/自由边界收敛|Free-boundary convergence/.test(got.miller.screen.geo),
   '截面旁没有这一行');
ok(!NO.test(got.miller.screen.verdict),
   '结论里没有那句警告');

console.log('\n〔八〕解释栏用的是同一张平衡，也说它的账');
ok(/完成|Done/.test(interpText.state), '解释栏算成了',
   interpText.state.slice(0, 50));
ok(/自由边界收敛|Free-boundary convergence/.test(interpText.scalars),
   '解释栏的读数表里有「自由边界收敛」一行');
ok(SETTLED.test(interpText.scalars) && !NO.test(interpText.scalars),
   '它报的也是「稳态」——与含时演化栏在同一档上一致',
   interpText.scalars.replace(/^[\s\S]*自由边界收敛/, '').slice(0, 80));

console.log('\n〔九〕页面自己没出错');
ok(errs.length === 0, '没有 pageerror / console error', errs.slice(0, 3).join(' | '));

console.log(`\n${n - bad}/${n} 项通过`);
process.exit(bad ? 1 : 0);
