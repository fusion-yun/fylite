// 台基模型（T-M4）：边界温度从「你给一个数」变成「解出的台基顶」，而且解出的
// 就是 EPED1-NN 在文件所载输入上的答案。
//
// ★★WHAT THIS REPLACES.  The 含时演化 bar's edge temperature was a SLIDER —
// the ITER case's 3 keV pedestal top was typed in by hand, and TODO called
// it the modelling page's largest single-point error source.  With the
// model on, the edge is the EPED1-NN surrogate's pedestal top: EPED1's two
// constraints (peeling-ballooning stability + the KBM width
// Δ = 0.076·√β_p,ped — Snyder, PoP 16 056118 (2009)) through the published
// network surrogate (Meneghini, NF 57 086034 (2017); weights from the
// open-source EPEDNN.jl, Apache-2.0, sha256-pinned in the kernel).
//
// ★THE ORACLE IS THE KERNEL FROM THE OTHER HOST: the file carries the ten
// EPED inputs and all eighteen outputs at 12 significant digits, and
// Python re-calls `kernel.eped1nn` (the native .so — a different build of
// the same Rust) at exactly those inputs.  Beside that, claims no re-call
// can fake:
//
//   〔一〕the switch: off, the two sliders are live and the file has no
//        pedestal block; on, they are disabled and the note names the model.
//   〔二〕the oracle re-call, all 18 outputs; the APPLIED solution is
//        index 0 (dmagGH/sol0 — the standard EPED1 prediction), and
//        T_ped = p_ped/(2 n_e,ped k) closes as an identity.
//   〔三〕the march actually ran under it: the final state's edge T_e/T_i
//        equal the last applied pedestal top (Dirichlet, so equality).
//   〔四〕EPED's own KBM closure on the exported case:
//        G = Δ/√β_p,ped within 10 % of 0.076 — a units slip in either
//        output breaks this identity immediately.
//   〔五〕the model moved the answer: on vs off differ at the edge, and
//        the readings carry the solved top where the slider's number was.
//   〔六〕★THE LITERATURE, per case rather than per range: the same kernel
//        entry point, on the input sets the EPED papers print in full,
//        against the values they print — two DIII-D shots (132003 /
//        132017, NF 49 085035 (2009) p. 6) and the ITER baseline
//        (NF 51 103016 (2011) §5 p. 7).  Page citations and the measured
//        ratios: `docs/note/pedestal-literature.md`.
//
//   node app/tests/validate-pedestal.mjs [--playwright DIR] [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';
const OUT = mkdtempSync(join(tmpdir(), 'ped-'));

//: device tier, heat channel only — the shortest march that has a real
//: boundary to pin.  edgene = 2e19: the pedestal-top TEMPERATURE goes as
//: p_ped/n_e,ped and EPED's pressure is only weakly density-dependent, so
//: a very thin edge would report a spectacular T_ped that is the model
//: answering the question as asked.
const BASECASE = {
  geometry: 'device', 'ch-heat': true, 'ch-density': false,
  'ch-current': false, 'ch-momentum': false, nsteps: 10, nlev: 21,
  dt: 0.002, dttarget: 0, pe: 2, pi: 2, dep: 0, depw: 0.3, fuel: 0,
  alpha: false, brem: false, ohmic: false, bootstrap: false, icd: 0,
  zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, couple: 0,
  closure: 0, chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3, edgeti: 0.3,
  edgene: 2.0, ne0: 5, peakt: 1.5, peakn: 0.5, vloop: 0, ip: 400,
  species: '', cimp: 0, sawtooth: false, wave: false, couplefixed: false,
  torque: 0, prandtl: 1, beam: false, lh: false, useref: false,
};

const CASES = [
  { id: 'off', name: '模型关（滑杆边界）', cfg: { pedestal: false } },
  { id: 'on', name: '模型开（EPED1-NN 边界）', cfg: { pedestal: true } },
];

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
  if (m.type() === 'error' && !/favicon/.test(m.text())
      && !/\/api\/health/.test((m.location() || {}).url || ''))
    errs.push('console: ' + m.text().slice(0, 200));
});
await page.goto(BASE + 'pages/model.html?device=east',
                { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /就绪|Ready|完成|Done|失败|Failed/i.test(
    (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
      .textContent || ''), null, { timeout: 180000 });

const got = {};
for (const c of CASES) {
  const cfg = { ...BASECASE, ...c.cfg };
  await page.evaluate((v) => {
    const rank = (id) => (id === 'geometry' ? 0 : 1);
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
  const ui = await page.evaluate(() => ({
    teDis: document.getElementById('model-evolve-edgete').disabled,
    tiDis: document.getElementById('model-evolve-edgeti').disabled,
    noteHidden: (document.getElementById('model-evolve-pedestal-note') || {})
                .hidden,
    note: (document.getElementById('model-evolve-pedestal-note') || {})
          .textContent || '',
  }));
  const RUN = '#model-evolve-run';
  await page.waitForFunction((k) => !document.querySelector(k)
    .classList.contains('stop'), RUN, { timeout: 300000 });
  await page.click(RUN);
  await page.waitForFunction(
    () => /完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
        .textContent || ''), null, { timeout: 900000 });
  const scalars = await page.evaluate(
    () => (document.getElementById('model-evolve-scalars') || {}).textContent
          || '');
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${c.id}.json`);
  await dl.saveAs(f);
  got[c.id] = { ui, scalars, doc: JSON.parse(readFileSync(f, 'utf8')) };
}
await br.close();

// --- the oracle: kernel.eped1nn from Python on the file's own inputs -----

const PY = `
import json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
from fylite import kernel as K

doc = json.load(open(sys.argv[1]))
ped = doc["fylite:pedestal"]
inp = ped["fylite:inputs"]
r = K.eped1nn(
    a=inp["fylite:a"], betan=inp["fylite:beta_n"], bt=inp["fylite:b_t"],
    delta=inp["fylite:delta"], ip=inp["fylite:ip_ma"],
    kappa=inp["fylite:kappa"], mass=inp["fylite:mass"],
    neped=inp["fylite:neped_1e19"], r=inp["fylite:r_major"],
    zeffped=inp["fylite:zeff_ped"])
mine_p = np.asarray(ped["fylite:p_ped"], float)
mine_w = np.asarray(ped["fylite:width"], float)
ap = ped["fylite:applied"]

def rel(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(b))), 1e-300))

#: the KBM closure on THIS case, from the file's own inputs
mu0 = 4e-7 * np.pi
perim = 2 * np.pi * inp["fylite:a"] * np.sqrt(
    (1 + inp["fylite:kappa"] ** 2) / 2)
bp = mu0 * inp["fylite:ip_ma"] * 1e6 / perim
beta_p_ped = 2 * mu0 * ap["fylite:p_ped"] / bp ** 2
QE = 1.602176634e-19

#: ★the published cases, evaluated through the SAME entry point the page
#: uses.  Inputs quoted verbatim from NF 49 085035 (2009) p. 6 for the two
#: DIII-D shots; ITER is this repo's Scenario-2 reading.  Z_eff,ped and
#: mass are NOT in those quotes — EPED1 takes eight inputs, EPED1-NN ten
#: (NF 57 086034 table 2 p. 8) — so they are assumed and the band below is
#: sized for that (sweeping Z_eff,ped 1.5..3.0 moves 132017 by 15 %).
PUBLISHED = [
    ("DIII-D 132003", dict(a=0.58, betan=2.1, bt=1.62, delta=0.2, ip=1.16,
                           kappa=1.8, mass=2.0, neped=5.0, r=1.7,
                           zeffped=2.0), 6.7e3, 0.036),
    ("DIII-D 132017", dict(a=0.59, betan=2.3, bt=2.1, delta=0.55, ip=0.85,
                           kappa=1.8, mass=2.0, neped=4.0, r=1.7,
                           zeffped=2.0), 12.2e3, 0.067),
    ("ITER baseline", dict(a=2.0, betan=1.8, bt=5.3, delta=0.485, ip=15.0,
                           kappa=1.85, mass=2.5, neped=7.0, r=6.2,
                           zeffped=1.8), 92.0e3, 0.040),
]
lit = []
for nm, kw, p_pub, w_pub in PUBLISHED:
    q = K.eped1nn(**kw)
    lit.append({"name": nm, "p": q["p_ped"][0], "w": q["width"][0],
                "p_pub": p_pub, "w_pub": w_pub,
                "rp": q["p_ped"][0] / p_pub, "rw": q["width"][0] / w_pub})

print(json.dumps({
    "lit": lit,
    "p_err": rel(mine_p, r["p_ped"]),
    "w_err": rel(mine_w, r["width"]),
    "applied_is_sol0": rel([ap["fylite:p_ped"], ap["fylite:width"]],
                           [r["p_ped"][0], r["width"][0]]),
    "tped_identity": abs(ap["fylite:t_ped"]
                         - ap["fylite:p_ped"]
                         / (2 * inp["fylite:neped_1e19"] * 1e19 * QE))
                     / ap["fylite:t_ped"],
    "g_kbm": float(ap["fylite:width"] / np.sqrt(beta_p_ped)),
    "t_ped": ap["fylite:t_ped"],
    "p_ped": ap["fylite:p_ped"],
    "extrap": ped["fylite:extrapolation"],
}))
`;

let ref;
try {
  ref = JSON.parse(execFileSync('python3', ['-c', PY, join(OUT, 'on.json')],
                                { encoding: 'utf8', maxBuffer: 1 << 26 }));
} catch (e) {
  console.error('原生对照跑不起来：\n' + (e.stderr || e.message));
  process.exit(2);
}

// --- assertions --------------------------------------------------------

let bad = 0, n = 0;
const ok = (cond, what, detail) => {
  n += 1;
  if (!cond) { bad += 1; console.log('  ✗ ' + what + (detail ? ' — ' + detail : '')); }
  else console.log('  ✓ ' + what + (detail ? ' — ' + detail : '')); };

console.log('〔一〕开关：关着滑杆是活的，开着滑杆停用、注记点名模型');
ok(!got.off.ui.teDis && !got.off.ui.tiDis, '关：边界 T_e / T_i 滑杆是活的');
ok(got.off.ui.noteHidden !== false || got.off.ui.note === '',
   '关：没有台基注记');
ok(!('fylite:pedestal' in got.off.doc), '关：文件里没有台基块');
ok(!/台基顶/.test(got.off.scalars), '关：读数里没有那一行');
ok(got.on.ui.teDis && got.on.ui.tiDis, '开：两个滑杆停用（不是被悄悄忽略）');
ok(!got.on.ui.noteHidden && /EPED/.test(got.on.ui.note),
   '开：注记点名 EPED1-NN 与出处');

console.log('\n〔二〕oracle：kernel.eped1nn 在文件所载输入上重调（判据 1e-6，'
            + '来源：束块同款 12 位有效）');
ok(ref.p_err < 1e-6, '18 路里的 9 路压强逐一', ref.p_err.toExponential(2));
ok(ref.w_err < 1e-6, '9 路宽度逐一', ref.w_err.toExponential(2));
ok(ref.applied_is_sol0 < 1e-6,
   '被应用的就是标准解（dmagGH/sol0，EPED1 论文里被验证的那一个）',
   ref.applied_is_sol0.toExponential(2));
ok(ref.tped_identity < 1e-9,
   'T_ped = p_ped/(2 n_e,ped k) 恒等（EPED 自己的 T_e=T_i 约定）',
   ref.tped_identity.toExponential(2));

console.log('\n〔三〕推进真的跑在它下面：末态边界 = 最后应用的台基顶');
const teOf = (doc) => {
  const p = doc['fylite:result'].core_profiles.profiles_1d;
  return (p && p.electrons && p.electrons.temperature) || null;
};
{
  const doc = got.on.doc;
  const res = doc['fylite:result'];
  const te = teOf(doc);
  const sm = res.summary['fylite:t_ped'];
  ok(Array.isArray(te) && te.length > 0, '末态 T_e 剖面在文件里');
  ok(Array.isArray(sm) && sm.length > 0 && isFinite(sm[sm.length - 1]),
     'summary 里有 t_ped 一列，逐步记着应用的边界');
  if (te && sm) {
    const edge = te[te.length - 1];
    const want = sm[sm.length - 1];
    //: Dirichlet — the last step's state holds the edge it was pinned to;
    //: the trace value is what the NEXT step would take, one lag apart,
    //: so the comparison is against the trace at the last APPLIED step.
    //: 7-digit file rounding on top.
    const d = Math.abs(edge - want) / Math.max(Math.abs(want), 1e-300);
    ok(d < 0.05, '末态 T_e(edge) 贴着应用的台基顶（滞后一步以内）',
       `${(edge / 1e3).toFixed(3)} vs ${(want / 1e3).toFixed(3)} keV · `
       + `相对 ${d.toExponential(1)}`);
  }
}

console.log('\n〔四〕EPED 自己的 KBM 闭合：Δ = 0.076·√β_p,ped（单位滑一位它当场碎）');
ok(Math.abs(ref.g_kbm - 0.076) < 0.1 * 0.076,
   'G = Δ/√β_p,ped 在 0.076 的 10% 之内',
   `G = ${ref.g_kbm.toFixed(4)} · p_ped ${(ref.p_ped / 1e3).toFixed(1)} kPa`
   + ` · T_ped ${(ref.t_ped / 1e3).toFixed(2)} keV`);

console.log('\n〔五〕模型动了答案，而且读数说了');
{
  const teOff = teOf(got.off.doc), teOn = teOf(got.on.doc);
  const eOff = teOff[teOff.length - 1], eOn = teOn[teOn.length - 1];
  ok(Math.abs(eOn - eOff) / Math.max(eOff, 1) > 0.2,
     '开与关的边界温度差 20% 以上（0.3 keV 的滑杆 vs 解出的台基顶）',
     `${(eOff / 1e3).toFixed(3)} → ${(eOn / 1e3).toFixed(3)} keV`);
  ok(/台基顶/.test(got.on.scalars), '读数里台基顶是自己一行');
  ok(ref.extrap === 0 || /外推/.test(got.on.scalars),
     '外推距离为零，或读数里写明了外推',
     `extrapolation = ${ref.extrap}`);
}

console.log('\n〔六〕文献逐例：同一内核入口，对论文印出来的数'
            + '（判据 ±20%，出处 = 论文自报精度 NF 51 103016 §5 p.7）');
for (const c of ref.lit) {
  ok(c.rp >= 0.8 && c.rp <= 1.2, `${c.name}：p_ped 对发表值`,
     `${(c.p / 1e3).toFixed(2)} vs ${(c.p_pub / 1e3).toFixed(1)} kPa · `
     + `比值 ${c.rp.toFixed(3)}`);
  ok(c.rw >= 0.8 && c.rw <= 1.2, `${c.name}：Δψ_N 对发表值`,
     `${c.w.toFixed(4)} vs ${c.w_pub.toFixed(3)} · 比值 ${c.rw.toFixed(3)}`);
}
{
  //: ★the paper's own CLAIM about the pair, not just its two numbers
  //: (NF 49 085035 p. 6): higher triangularity and larger B_T/I_p give
  //: "substantially larger pedestal height and width for 132017, despite
  //: similar values of I_p x B_T" — 1.879 vs 1.785, 5 % apart.  Both
  //: values could drift the same way and stay in band; this contrast
  //: cannot.
  const [lo, hi] = ref.lit;
  const rp = hi.p / lo.p, rw = hi.w / lo.w;
  ok(rp > 1.5 && rp < 2.3,
     '132017 / 132003 的台基高度反差（发表值 1.82，I_p·B_T 只差 5%）',
     `×${rp.toFixed(2)}`);
  ok(rw > 1.5 && rw < 2.3, '同一对的宽度反差（发表值 1.86）',
     `×${rw.toFixed(2)}`);
}

console.log('\n〔七〕页面没有报错');
ok(errs.length === 0, '没有 pageerror / console error',
   errs.slice(0, 3).join(' | '));

console.log(`\n${n - bad}/${n} 项通过`);
process.exit(bad ? 1 : 0);
