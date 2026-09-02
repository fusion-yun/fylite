// Oracle test for T-A9 — the bootstrap / ohmic / fitted-current closure.
//
// ★★WHAT THIS GATE IS ABOUT.  The reconstruction bar has drawn a bootstrap
// current beside a fitted current for as long as it has existed, and the
// caption said in as many words that the two could not be subtracted: one
// is `|<j.B>|/B0`, the other is `<j_phi>`, and they are different
// quantities on the same surface.  T-A9 landed the two kernel entries that
// close the gap — the per-surface conversion and the neoclassical
// conductivity — plus the flux-surface averages the conversion needs.  Six
// things are checked, each of which can fail while the others pass:
//
//   1. THE CONVERSION IS AN IDENTITY, AND IT CLOSES.  `<j.B>` and
//      `<j_phi/R>/<1/R>` are both assembled here, in this file, from the
//      fit's own p' and FF' and the exported surface averages — two
//      different expressions of the same two coefficients.  The kernel's
//      conversion of the first must be the second.  A conversion with the
//      pressure term dropped, or `<B_tor^2>` where `<B^2>` belongs, gives
//      three smooth plausible curves and fails here.
//   2. THE AVERAGES ARE A REAL GEOMETRY.  `<B^2>` must be
//      `<B_pol^2> + <B_tor^2>` with `<B_tor^2> = F^2 <1/R^2>`, and
//      `<1/R^2>` must exceed `<1/R>^2` (Cauchy-Schwarz) by a margin that
//      is not rounding.  A page substituting `1/R0^2` passes every
//      tolerance in item 1 and fails this one.
//   3. sigma_neo IS THE KERNEL'S, AND IT IS SAUTER'S.  The page's profile
//      is recomputed two ways: natively through `fylite.kernel.sigma_neo`
//      on the exported inputs (does this page put the right array in the
//      right slot?) and, independently, from the published Sauter-1999
//      formulae transcribed HERE from the paper (is the kernel computing
//      what the paper says?).
//   4. THE TRAPPING CORRECTION IS DOING WORK.  F33 must fall well below 1
//      over the ladder — if it did not, sigma_neo would be Spitzer with
//      extra steps and the ohmic SHAPE would still be missing.
//   5. THE THREE CURVES ADD, AND THEIR INTEGRALS ADD.  j_tot = j_bs +
//      j_ohm surface by surface, and I_bs + I_ohm + I_dia is the ladder's
//      own total — which is then compared with the Ip the fit produced, so
//      the quadrature's truncation is a reported number and not an
//      assumption.
//   6. THE OUTER LOOP IS A FIXED POINT.  With the closure switch on, the
//      bootstrap current goes onto the kernel's prescribed-current channel
//      and the fit is repeated.  The bootstrap fraction must MOVE on the
//      first round (or "converged" means nothing) and then stop moving —
//      the closure criterion is < 5 % variation across the loop's rounds.
//
// ★Runs on EAST, installed from `machine_desc/` the way an imported machine
// is — the one built-in device has no reference discharge, so there is
// nothing for a reconstruction to fit.
//
//   node app/tests/validate-closure.mjs [--playwright DIR] [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { seedDevice, envWithDeck, missingDeviceMessage } from './_device.mjs';
import { browser } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const iu = process.argv.indexOf('--url');
const BASE = iu > 0 ? process.argv[iu + 1] : 'http://127.0.0.1:8767/app/';
const MU0 = 4e-7 * Math.PI;

const OUT = mkdtempSync(join(tmpdir(), 'clo-'));
let pass = 0, fail = 0;
const ok = (c, name, note) => {
  if (c) { pass += 1; console.log(`  ok    ${name}${note ? '  — ' + note : ''}`); }
  else { fail += 1; console.log(`  FAIL  ${name}${note ? '  — ' + note : ''}`); }
};

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1400, height: 1100 } });
if (!await seedDevice(ctx, 'east')) {
  console.error(missingDeviceMessage('east'));
  process.exit(2);
}
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  //: ★the analysis page probes the MDSplus gateway once at load
  //: (`mds-source.js` → `api/health`) and is designed to keep working
  //: without one — on the bare http-server the probe 404s by design, and
  //: the browser's complaint cannot be suppressed from script.  Same
  //: filter `validate-analysis.mjs` carries, by URL (the text has none).
  if (m.type() === 'error' && !/favicon/.test(m.text())
      && !/\/api\/health$/.test((m.location() || {}).url || ''))
    errs.push('console: ' + m.text().slice(0, 200));
});

const RUNKEY = '#analysis-reconstruction-run';

/** One reconstruction, and the kinetic session document it produced. */
async function run(closure, tag) {
  await page.evaluate((on) => {
    const set = (id, v) => {
      const e = document.getElementById(id);
      if (e.checked !== v) { e.checked = v; e.dispatchEvent(new Event('change')); }
    };
    set('reconstruction-neon', true);
    set('reconstruction-closure', on);
  }, closure);
  // 〔共同的纪律〕idle, then click, then wait for busy, then wait for done
  await page.waitForFunction(
    (k) => !document.querySelector(k).classList.contains('stop'), RUNKEY,
    { timeout: 300000 });
  await page.click(RUNKEY);
  await page.waitForFunction(
    (k) => document.querySelector(k).classList.contains('stop'), RUNKEY,
    { timeout: 60000 }).catch(() => {});
  await page.waitForFunction(
    () => /重构完成|converged|失败|fail/.test(
      document.getElementById('analysis-status').textContent),
    null, { timeout: 600000 });
  const status = await page.textContent('#analysis-status');
  if (/失败|fail/.test(status)) throw new Error(`${tag}: ${status}`);
  await page.click('#analysis-ioexport');
  const [dl] = await Promise.all([
    page.waitForEvent('download'),
    page.click('#analysis-iofmt-reconstruction-kinetic')]);
  const f = join(OUT, `k_${tag}.json`);
  await dl.saveAs(f);
  return JSON.parse(readFileSync(f, 'utf8'));
}

await page.goto(BASE + 'pages/analysis.html?device=east#part-reconstruction',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /就绪|Ready/.test(document.getElementById('analysis-status').textContent),
  null, { timeout: 180000 });

const plain = await run(false, 'plain');
// the loop's own knobs: as many rounds as the page allows, tightest tolerance
await page.evaluate(() => {
  const set = (id, v) => {
    const e = document.getElementById(id);
    e.value = v; e.dispatchEvent(new Event('input'));
  };
  set('reconstruction-closit', 6);
  set('reconstruction-clostol', 0.002);
});
const looped = await run(true, 'loop');
await br.close();

const cl = plain['fylite:current_closure'];
const bs = plain['fylite:bootstrap'];
if (!cl || cl['fylite:error'] || !bs) {
  console.error('反演页没有给出闭环块：' +
                JSON.stringify(cl && cl['fylite:error']));
  process.exit(1);
}
const S = cl['fylite:surface'];
const arr = (v) => Float64Array.from(v);
const n = arr(cl['fylite:j_total']).length;
const b2 = arr(S.b2), bt2 = arr(S.b_tor2), F = arr(S.f_psi),
      rInv = arr(S.r_inv), rInv2 = arr(S.r_inv2), dv = arr(S.dv_dpsi),
      pp = arr(S.dp_dpsi), ffp = arr(S.ffprime), ratio = arr(S.ratio),
      psiB = arr(S.psi_bar);
const B0 = S.b0;
const jTot = arr(cl['fylite:j_total']), jBs = arr(cl['fylite:j_bootstrap']),
      jOhm = arr(cl['fylite:j_ohmic']),
      jTotTor = arr(cl['fylite:j_total_toroidal']),
      jBsTor = arr(cl['fylite:j_bootstrap_toroidal']),
      jOhmTor = arr(cl['fylite:j_ohmic_toroidal']);
const sig = arr(cl['fylite:sigma_neo']), sSp = arr(cl['fylite:sigma_spitzer']),
      f33 = arr(cl['fylite:f33']);
const I = cl['fylite:currents'];

const relMax = (a, b) => {
  let d = 0, s = 0;
  for (let k = 0; k < a.length; k++) {
    d = Math.max(d, Math.abs(a[k] - b[k]));
    s = Math.max(s, Math.abs(b[k]));
  }
  return s > 0 ? d / s : NaN;
};

console.log('〔一〕换算是一条恒等式，而且它闭合');

// ★BOTH SIDES ARE BUILT HERE, from the fit's own two coefficients:
//     <j.B>           = (FF'/mu0 F) <B^2> + p' F
//     <j_phi/R>/<1/R> = [ p' + (FF'/mu0) <1/R^2> ] / <1/R>
// The page's `j_total` is the first (divided by B0); the kernel's
// conversion of it must be the second.  Neither expression goes through
// the entry under test.
const parHere = new Float64Array(n), torHere = new Float64Array(n);
for (let k = 0; k < n; k++) {
  parHere[k] = ((ffp[k] / (MU0 * F[k])) * b2[k] + pp[k] * F[k]);
  torHere[k] = (pp[k] + (ffp[k] / MU0) * rInv2[k]) / rInv[k];
}
const parRel = relMax(Float64Array.from(jTot, (v) => v * B0), parHere);
ok(parRel < 1e-9,
   '页面的 j_tot 就是这一次拟合自己的 p′ 与 FF′ 经 ⟨B²⟩ 组出的 ⟨j·B⟩',
   `相对差 ${parRel.toExponential(2)}（判据 1e-9，来源：会话文件 12 位有效）`);
const torRel = relMax(jTotTor, torHere);
ok(torRel < 1e-9,
   '内核换算出的 ⟨j_φ⟩ 就是同两个系数直接写出的 ⟨j_φ⟩ ——恒等式闭合',
   `相对差 ${torRel.toExponential(2)}（判据 1e-9）`);
ok(cl['fylite:identity_residual'] < 1e-10,
   '页面自己报的恒等式残差也在 1e-10 以下',
   `${(+cl['fylite:identity_residual']).toExponential(2)}`);

// ★NOT DEGENERATE: the diamagnetic term must actually be doing something,
// or「converting the fit and not the parts」would be a distinction without
// a difference.  Drop it and the toroidal current has to move.
let diaMax = 0;
for (let k = 0; k < n; k++) {
  const noDia = (jTot[k] * B0 * ratio[k]) / (F[k] * rInv[k]);
  diaMax = Math.max(diaMax,
                    Math.abs(noDia - jTotTor[k]) / Math.abs(jTotTor[k] || 1));
}
ok(diaMax > 1e-3,
   '换算里的 p′ 项不是摆设：去掉它，环向电流就变',
   `最大相对变动 ${(100 * diaMax).toFixed(2)} %`);

console.log('');
console.log('〔二〕逐面平均是一副真几何');
let splitRel = 0, csMin = Infinity;
for (let k = 0; k < n; k++) {
  const bTor = F[k] * F[k] * rInv2[k];
  splitRel = Math.max(splitRel, Math.abs(bTor - bt2[k]) / bt2[k]);
  csMin = Math.min(csMin, rInv2[k] / (rInv[k] * rInv[k]) - 1);
}
ok(splitRel < 1e-10, '⟨B_tor²⟩ 恰为 F²⟨1/R²⟩',
   `相对差 ${splitRel.toExponential(2)}（判据 1e-10，来源：会话文件 12 位有效）`);
let bpolMin = Infinity, ratioMin = 1, ratioMax = 0;
for (let k = 0; k < n; k++) {
  bpolMin = Math.min(bpolMin, b2[k] - bt2[k]);
  ratioMin = Math.min(ratioMin, ratio[k]);
  ratioMax = Math.max(ratioMax, ratio[k]);
}
ok(bpolMin > 0, '⟨B²⟩ − ⟨B_tor²⟩ = ⟨B_pol²⟩ 处处为正',
   `最小 ${bpolMin.toExponential(3)} T²`);
ok(csMin > 1e-5,
   '⟨1/R²⟩ 严格大于 ⟨1/R⟩²（Cauchy-Schwarz），差值不是舍入',
   `最小相对超出 ${csMin.toExponential(2)}`);
ok(ratioMin > 0.5 && ratioMax < 1 && ratioMax - ratioMin > 1e-3,
   '⟨B_tor²⟩/⟨B²⟩ 在 (0,1) 内且逐面不同——它若恒为 1，换算就退化成一次除法',
   `${ratioMin.toFixed(5)} … ${ratioMax.toFixed(5)}`);

console.log('');
console.log('〔三〕σ_neo 是内核的，而且是 Sauter 的');

// ★THE SECOND SPELLING, transcribed from Sauter et al., Phys. Plasmas 6,
// 2834 (1999) eqs. (13)/(13a)/(13b) and (18b), evaluated on the ladder's
// own f_t and nu*_e (which the page exports through the bootstrap block).
// It is an oracle for the FORMULA; the native call below is an oracle for
// the WIRING, and the two fail differently.
const bi = bs['fylite:inputs'];
const nat = JSON.parse(execFileSync('python3', ['-c', `
import json, sys
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
import numpy as np
from fylite import kernel as K
i = json.load(sys.stdin)
r = K.sigma_neo(eps=i["eps"], q_abs=i["q"], ne=i["ne"], te=i["te"],
                ti=i["ti"], ni=i["ni"], zeff=i["zeff"], r_maj=i["r_maj"],
                vintage=${cl['fylite:sigma_model'] === 'sauter-1999' ? 0 : 1})
old = K.sigma_neo(eps=i["eps"], q_abs=i["q"], ne=i["ne"], te=i["te"],
                  ti=i["ti"], ni=i["ni"], zeff=i["zeff"], r_maj=i["r_maj"],
                  vintage=0)
new = K.sigma_neo(eps=i["eps"], q_abs=i["q"], ne=i["ne"], te=i["te"],
                  ti=i["ti"], ni=i["ni"], zeff=i["zeff"], r_maj=i["r_maj"],
                  vintage=1)
print(json.dumps({k: np.asarray(v).tolist() for k, v in r.items()}
                 | {"s99": old["sigma_neo"].tolist(),
                    "s21": new["sigma_neo"].tolist()}))
`], { input: JSON.stringify(bi), encoding: 'utf8',
      env: envWithDeck('east') }));

ok(relMax(sig, Float64Array.from(nat.sigma_neo)) < 1e-10,
   '页面的 σ_neo 就是原生同一入口按同一批逐面输入算出的那条',
   `相对差 ${relMax(sig, Float64Array.from(nat.sigma_neo)).toExponential(2)}（判据 1e-10，来源：会话文件 12 位有效）`);
ok(relMax(sSp, Float64Array.from(nat.sigma_spitzer)) < 1e-10,
   '页面的 σ_Spitzer 同样是原生那条',
   `相对差 ${relMax(sSp, Float64Array.from(nat.sigma_spitzer)).toExponential(2)}`);

// the published formulae, written out here
const lnE = (ne, te) =>
  23.5 - Math.log(Math.sqrt(ne / 1e6) * Math.pow(te, -1.25))
       - Math.sqrt(1e-5 + Math.pow(Math.log(te) - 2, 2) / 16);
let sauterRel = 0;
for (let k = 0; k < n; k++) {
  const z = Math.max(bi.zeff[k], 1);
  const ft = nat.ft[k], nue = nat.nu_e_star[k];
  const x33 = ft / (1 + (0.55 - 0.1 * ft) * Math.sqrt(nue)
                      + 0.45 * (1 - ft) * nue / Math.pow(z, 1.5));
  const F33 = 1 - (1 + 0.36 / z) * x33 + (0.59 / z) * x33 * x33
                - (0.23 / z) * Math.pow(x33, 3);
  const sSpHere = 1.9012e4 * Math.pow(bi.te[k], 1.5)
    / (z * lnE(bi.ne[k], bi.te[k]) * (0.58 + 0.74 / (0.76 + z)));
  const want = sSpHere * F33;
  sauterRel = Math.max(sauterRel, Math.abs(nat.s99[k] - want) / want);
}
ok(sauterRel < 1e-13,
   'σ_neo 的 Sauter-1999 档逐面等于本文件按论文式 (13)/(13a)/(13b) 写出的值',
   `相对差 ${sauterRel.toExponential(2)}`);

// the two vintages are two answers, and they must not be the same one
let vintMax = 0;
for (let k = 0; k < n; k++)
  vintMax = Math.max(vintMax,
                     Math.abs(nat.s99[k] - nat.s21[k]) / nat.s21[k]);
ok(vintMax > 0.02,
   'Sauter-1999 与 Redl-2021 两档确实是两个答案',
   `最大相对差 ${(100 * vintMax).toFixed(2)} %`);

console.log('');
console.log('〔四〕捕获修正真的在干活');
let f33min = 1, f33max = 0;
for (let k = 0; k < n; k++) {
  f33min = Math.min(f33min, f33[k]);
  f33max = Math.max(f33max, f33[k]);
  if (!(f33[k] > 0 && f33[k] <= 1)) { f33min = -1; break; }
}
ok(f33min > 0 && f33max <= 1, 'F₃₃ 逐面落在 (0, 1]——捕获只能减小电导率');
ok(f33min < 0.75,
   '芯部到中部有三分之一以上的电导率被捕获粒子压掉——这正是欧姆电流的形状所在',
   `F₃₃ ${f33min.toFixed(4)} … ${f33max.toFixed(4)}`);
// and the shape is NOT the Spitzer shape: normalise both to the axis and
// they must part company
let shapeGap = 0;
for (let k = 0; k < n; k++)
  shapeGap = Math.max(shapeGap,
                      Math.abs(sig[k] / sig[0] - sSp[k] / sSp[0]));
ok(shapeGap > 0.05,
   'σ_neo 的形状不是 σ_Spitzer 的形状——归一到轴上之后两条分开',
   `最大形状差 ${shapeGap.toFixed(4)}`);

console.log('');
console.log('〔五〕三条曲线相加，它们的积分也相加');
let addRel = 0;
for (let k = 0; k < n; k++)
  addRel = Math.max(addRel,
                    Math.abs(jTot[k] - jBs[k] - jOhm[k])
                    / Math.max(Math.abs(jTot[k]), 1e-30));
ok(addRel < 1e-10, 'j_tot = j_bs + j_ohm 逐面成立',
   `最大相对差 ${addRel.toExponential(2)}（判据 1e-10，来源：会话文件 12 位有效）`);
// the same statement in the toroidal measure, where it is NOT free: the
// three toroidal curves were converted separately
let torAdd = 0, torAmp = 0;
for (let k = 0; k < n; k++) {
  torAmp = Math.max(torAmp, Math.abs(jTotTor[k]));
  const dia = (pp[k] * (1 - ratio[k])) / rInv[k];
  torAdd = Math.max(torAdd,
                    Math.abs(jTotTor[k] - jBsTor[k] - jOhmTor[k] - dia));
}
ok(torAdd / torAmp < 1e-10,
   '环向度量下 j_tot = j_bs + j_ohm + j_dia——抗磁项恰好补上那一份',
   `最大相对差 ${(torAdd / torAmp).toExponential(2)}`);
const sumRel = Math.abs(
  I['fylite:i_bootstrap'] + I['fylite:i_ohmic'] + I['fylite:i_diamagnetic']
  - I['fylite:i_ladder']) / Math.abs(I['fylite:i_ladder']);
ok(sumRel < 1e-12, '三份电流之和就是梯子求积出的总电流',
   `相对差 ${sumRel.toExponential(2)}`);
const quad = Math.abs(I['fylite:i_ladder'] - I['fylite:i_fitted'])
  / Math.abs(I['fylite:i_fitted']);
//: ★T-A19, measured to its decomposition.  The old ladder (24 faces,
//: density pinned to zero at the axis, held constant to the edge) missed
//: the fit's own I_p by 3.88 %.  The ends were most of it: linear
//: extrapolation moved the gap to +1.2 %, and quadrature ORDER is now
//: irrelevant (trapezoid vs parabolic composite: 0.06 %).  The rest is
//: the surface count and the fitted field's own mask calibre: on the
//: forward field (where sum(cells) = Ip holds by construction) the gap
//: runs 24 faces +1.53 % → 96 faces +0.43 %; on the fitted field 96
//: faces measure +1.11 % — the remainder belongs to the fit's mask, and
//: the row's label now says so.  The assertion pins the measured state:
//: inside 1.5 %, and shrinking as faces are added.
ok(quad < 0.015,
   '梯子求积的总电流与拟合给出的 I_p 相差在 1.5 % 以内（T-A19：96 面 + 线性外推端段；余差是拟合场的掩膜口径，标在行名里）',
   `${(100 * quad).toFixed(3)} %，梯子 ${(I['fylite:i_ladder'] / 1e3).toFixed(2)} kA vs 拟合 ${(I['fylite:i_fitted'] / 1e3).toFixed(2)} kA`);
//: ...and it must SHRINK as the ladder is refined — asserted by running
//: the same quadrature on every other surface, where the gap must widen.
const quadC = Math.abs(I['fylite:i_ladder_coarse'] - I['fylite:i_fitted'])
  / Math.abs(I['fylite:i_fitted']);
ok(isFinite(quadC) && quadC > quad,
   '面数减半后差值变大——所以这个差确实随加密缩小，不是端点处理的巧合',
   `48 面 ${(100 * quadC).toFixed(3)} % > 96 面 ${(100 * quad).toFixed(3)} %`);
ok(I['fylite:bootstrap_fraction'] > 0 &&
   I['fylite:bootstrap_fraction'] < 1 &&
   Math.abs(I['fylite:i_bootstrap']) > 1e3,
   '自举份额是一个真数：既非零也不是全部',
   `${(100 * I['fylite:bootstrap_fraction']).toFixed(2)} %，I_bs = ${(I['fylite:i_bootstrap'] / 1e3).toFixed(2)} kA`);

console.log('');
console.log('〔六〕自洽外环是一个不动点');
const loop = looped['fylite:closure_loop'];
ok(!!loop && !loop.error, '外环跑起来了',
   loop ? `${loop.rounds} 轮，${loop.stop}` : '没有外环块');
if (loop && !loop.error) {
  const h = loop.history.map(Number);
  ok(h.length >= 3, '外环至少跑了两轮（起点 + 两个迭代）',
     `自举份额逐轮 ${h.map((v) => (100 * v).toFixed(3)).join(' → ')} %`);
  // ★NON-DEGENERATE: prescribing the bootstrap current must CHANGE the
  // answer on the first round, or「converged」is a statement about a loop
  // that never ran.
  const first = Math.abs(h[1] - h[0]) / Math.abs(h[1]);
  ok(first > 1e-3,
     '第一轮确实动了——把自举电流交给规定电流道不是一次空操作',
     `第一步相对变动 ${(100 * first).toFixed(2)} %`);
  // ★THE CLOSURE CRITERION, and it is about the loop's ITERATES.  `h[0]`
  // is the fit made before any bootstrap current was prescribed — the
  // starting point, not a round — and the assertion just above is that
  // the first round moved away from it.  Its distance from the fixed
  // point is reported here rather than asserted: a bound one part in
  // twenty from the threshold would be a gate that fails for reasons
  // unrelated to the claim.
  const tail = h.slice(1);
  const mn = Math.min(...tail), mx = Math.max(...tail);
  const mean = tail.reduce((a, b) => a + b, 0) / tail.length;
  const spread = (mx - mn) / Math.abs(mean);
  const whole = (Math.max(...h) - Math.min(...h))
    / Math.abs(h.reduce((a, b) => a + b, 0) / h.length);
  ok(spread < 0.05,
     '★闭合判据：自举份额在外环各轮之间的变动 < 5 %',
     `${(100 * spread).toFixed(3)} %（连起点一起算是 ${(100 * whole).toFixed(2)} %，那一段是「外环改变了多少」而不是「外环稳不稳」）`);
  // ★A CONTRACTION, not merely a small last step: each round must move
  // the fraction by far less than the one before it.  A sequence that
  // wandered by the same amount every round would satisfy a bound on the
  // last step alone.
  if (h.length >= 3) {
    const d1 = Math.abs(h[1] - h[0]), d2 = Math.abs(h[2] - h[1]);
    ok(d2 * 10 < d1,
       '迭代是收缩的：第二轮的移动不到第一轮的十分之一',
       `Δ₁ = ${(100 * d1).toExponential(2)} → Δ₂ = ${(100 * d2).toExponential(2)}（百分点）`);
  }
  ok(loop.stop === 'converged',
     '外环是自己停的，不是用满轮数停的',
     `tol = ${loop.tol}，上限 ${loop.maxIter} 轮`);
  // the fitted current must not have drifted while the loop ran: the
  // prescribed part is part of the plasma, and a bookkeeping error there
  // shows up as an Ip that walks
  const ipDrift = Math.max(...loop.ip.map((v) => Math.abs(v - loop.ip[0])))
    / Math.abs(loop.ip[0]);
  ok(ipDrift < 0.01,
     '外环各轮的 I_p 没有走——规定电流道那一份被算回了总量里',
     `最大相对漂移 ${(100 * ipDrift).toFixed(3)} %`);
}

// ★AND THE SWITCH IS A SWITCH: with the loop off there is no loop block,
// so a reader can tell a fit that iterated from one that did not.
ok(!plain['fylite:closure_loop'],
   '外环关着时会话文件里没有外环块（关着的开关不留痕迹）');

console.log('');
ok(errs.length === 0, '没有 pageerror', errs.slice(0, 3).join(' | '));

console.log('');
console.log(`判定：${fail === 0 ? '闭环通过' : '闭环未通过'} —— ${pass} 项通过，${fail} 项失败`);
process.exit(fail === 0 ? 0 : 1);
