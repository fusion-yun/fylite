// LH 沉积：页面报的那条剖面，是不是 `kernel.lh_deposit` 那条（T-M10）
//
// ★★WHAT THIS CLOSES.  The beam batch (T-M2) wired the whole NBI chain and
// said, on the page and in the changelog, that LH was NOT wired — so the
// item read as half done because it was half done.  This is the other half:
// the lower-hybrid launcher, its n_parallel band, the up-shift, the
// accessibility gate, the Landau-resonant layer, the Fisch current-drive
// weighting and the sigma envelope, all of it the kernel's and all of it in
// ONE call (`lh_deposit`), with `lh_accessibility` for the resonant
// temperature the page reports beside it and the fisch closed form for the local
// CD weight.
//
// ★★THE ORACLE IS THE KERNEL, called from Python on the inputs the page
// wrote out — the same discipline as `validate-beam.mjs`, and for the same
// reason: what is under test is the ASSEMBLY.  Which array goes into which
// argument, on which grid, in which units, and whether the band the file
// says was launched is the band the entry was actually given.  A page that
// handed `lh_deposit` its rmaj where f_pol belongs would not raise; it would
// report a plausible accessibility limit for a machine with a 1.8 T field
// where there is none.
//
// ★AND FOUR CHECKS THAT GO THROUGH NO KERNEL ENTRY AT ALL:
//   · `T_res = m_e c^2 / (2 xi^2 n_par^2)` written out here, from the
//     electron rest energy, against the resonant temperature the file
//     reports — the one number in this chain with a closed form;
//   · `sum(p_dep dV)` equals the launched power of exactly those systems
//     that found a resonance, and nothing else — the model's own
//     conservation;
//   · `I_LH = eta_CD P / (n_e_bar R0)` in closed form, which is what says
//     the accessible fraction was NOT multiplied into the driven current;
//   · the effective band is the launched band times the up-shift, exactly.
//
//   node app/tests/validate-lh.mjs [--playwright DIR] [--chrome BIN]
//                                  [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { deviceDoc, seedDeviceDocs, missingDeviceMessage } from './_device.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';

//: ★the LH block is written at 12 significant digits — not this file's
//: usual 7 — precisely so this comparison can be made at 1e-6, which is the
//: closure criterion the feature was written against.  What is left below
//: it is not rounding: it is the same Rust built twice (wasm and the native
//: `.so`) differing in the libm behind `exp`/`sqrt`.
const TOL = 1e-6;

//: electron rest energy [eV].  ★Written HERE, in this file, so the resonant
//: temperature has an oracle that is not the kernel's own constant — the
//: same job `ME_C2_EV` does for `python/tests/test_lh.py`.
const ME_C2_EV = 510998.95;

const BASECASE = {
  geometry: 'device', 'ch-heat': true, 'ch-density': false,
  'ch-current': true, nsteps: 4, nlev: 31, dt: 0.001, dttarget: 0,
  fuel: 0, alpha: false, brem: true, ohmic: true, bootstrap: true,
  zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, closure: 0,
  chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3, edgeti: 0.3, edgene: 0.5,
  ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0.5, ip: 400, couple: 0,
  freeiter: 600, species: '', cimp: 0, wave: false,
  //: ★the beam is OFF in every case: this gate is about the wave, and a
  //: run carrying both would leave "which source put that power there"
  //: to be untangled.  The Gaussian's own controls are set anyway, so the
  //: cases differ in the wave and in nothing else.
  beam: false, pe: 2, pi: 2, dep: 0, depw: 0.3,
  //: ★the prescribed driven current is set NON-ZERO on purpose: with the
  //: wave on it must be disabled AND ignored, and a case that left it at
  //: zero could not tell "ignored" from "happened to be nothing".
  icd: 300,
  //: ★the two bands are EAST's, each on its own system: LH1 is the 2.45 GHz
  //: launcher (1.91-2.43) and LH2 the 4.6 GHz one (1.80-2.23).  They used to
  //: be written the other way round here, mirroring the page's own swapped
  //: literals (T-M15) — the arithmetic did not care, but a case that calls
  //: the 4.6 GHz band LH1 teaches the reader the wrong machine.
  lh: true, lhpower1: 2, lhnpar1lo: 1.91, lhnpar1hi: 2.43,
  lhpower2: 0, lhnpar2lo: 1.80, lhnpar2hi: 2.23,
  lhuplo: 1.80, lhuphi: 2.20, lhetacd: 1.00, lhxi: 3.0,
  lhwidth: 0.05, lhshells: 24,
};

const CASES = [
  //: both ends of the effective band resonate, so sigma_j is a real
  //: interval rather than a degenerate zero
  { id: 'base', name: '一套系统 · 带两端都共振', cfg: {} },
  //: ★only the UPPER end resonates: the spread between the two ends is then
  //: undefined and the kernel returns sigma_j = 0.  A structural claim, and
  //: the case that says the envelope is the spread and not a fudge factor.
  { id: 'oneend', name: '只有上端共振（σ_j 必须恰为零）',
    cfg: { lhuplo: 1.60 } },
  //: ★a strict single-pass model: EAST's launched band resonates at
  //: 4.8-8.8 keV, above this plasma, so NOTHING is deposited — a result,
  //: not a failure, and the page has to say which of the two it is
  { id: 'cold', name: '不上移：一处也不共振（这是结果不是失败）',
    cfg: { lhuplo: 1.00, lhuphi: 1.00 } },
  //: two systems with different bands and different powers
  { id: 'two', name: '两套系统，各自的带与各自的功率',
    cfg: { lhpower2: 1.5 } },
  //: ★xi moves the resonant temperature as xi^-2, so the layer must move.
  //: This is the check a prescribed shape could never pass.
  { id: 'xi', name: 'ξ 3.0 → 2.4（共振层必须挪）', cfg: { lhxi: 2.4 } },
  //: the wave off, for the comparison
  { id: 'off', name: '关掉（对照）', cfg: { lh: false } },
];

const OUT = mkdtempSync(join(tmpdir(), 'lh-'));
const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1440, height: 1100 } });
const EAST_DOC = deviceDoc('east');
if (!EAST_DOC) {
  console.error(missingDeviceMessage('east'));
  process.exit(2);
}
//: ★★A SECOND MACHINE, made here rather than shipped (T-M15).  The claim
//: under test is that the launcher settings follow the DEVICE, and a claim
//: like that cannot be tested against one machine: identical numbers prove
//: nothing when there is only one document they could have come from.  So
//: this is EAST with a different set of antennas — one launcher, another
//: name, another nameplate, another band — installed through the same import
//: channel as EAST itself.  No test-only path in the app, and no invented
//: machine committed to the repository.
const VARIANT_ID = 'east-lh-variant';
const VARIANT_ANT = [{
  name: 'LHX', frequency: 3.7e9,
  'fylite:max_power': 2.5e6, 'fylite:n_parallel': [1.55, 2.75],
}];
const VARIANT_DOC = JSON.parse(JSON.stringify(EAST_DOC));
VARIANT_DOC['fylite:device_id'] = VARIANT_ID;
VARIANT_DOC.name = 'EAST (LH variant)';
VARIANT_DOC.lh_antennas = { antenna: VARIANT_ANT };
//: ★the no-antenna machine is seeded HERE, with the other two: the seeding
//: is an init script that rewrites the store on EVERY navigation, so a doc
//: written into localStorage later is erased by the next page.goto and the
//: page silently falls back to a machine that HAS antennas — which is
//: exactly what this gate's first run caught.
const NONE_ID = 'east-lh-none';
const NONE_DOC = { ...VARIANT_DOC, 'fylite:device_id': NONE_ID,
                   name: 'EAST (no LH)', lh_antennas: { antenna: [] } };
await seedDeviceDocs(ctx, { east: EAST_DOC, [VARIANT_ID]: VARIANT_DOC,
                            [NONE_ID]: NONE_DOC });
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

//: ★★THE ANALYTIC TIER FIRST, before anything runs.  The wave needs a psi_N
//: map on the (R, Z) grid AND |F(psi)| per surface; Miller has neither, so
//: the switch must be DISABLED rather than producing a deposition judged
//: accessible against a field nobody computed.
await page.evaluate(() => {
  const g = document.getElementById('model-evolve-geometry');
  g.value = 'miller'; g.dispatchEvent(new Event('change'));
});
const millerState = await page.evaluate(() => ({
  disabled: document.getElementById('model-evolve-lh').disabled,
  checked: document.getElementById('model-evolve-lh').checked,
  note: (document.getElementById('model-evolve-lh-off') || {}).textContent
        || '',
  noteHidden: (document.getElementById('model-evolve-lh-off') || {}).hidden,
}));

const RUN = '#model-evolve-run';
const got = {};
for (const c of CASES) {
  const cfg = { ...BASECASE, ...c.cfg };
  await page.evaluate((v) => {
    //: geometry, then the switch, then the panel's own controls — the
    //: switch is disabled off the two tiers that have a psi map, and its
    //: panel means nothing until it is on
    const rank = (id) => (id === 'geometry' ? 0
                          : (id === 'lh' || id === 'beam') ? 1
                          : /^(lh|beam)/.test(id) ? 2 : 0);
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
    note: (document.getElementById('model-evolve-lh-note') || {})
          .textContent || '',
    noteHidden: !!(document.getElementById('model-evolve-lh-note') || {})
                 .hidden,
    scalars: (document.getElementById('model-evolve-scalars') || {})
             .textContent || '',
    figHidden: !!(document.getElementById('model-evolve-lhfig-box') || {})
                .hidden,
    icdDisabled: document.getElementById('model-evolve-icd').disabled,
  }));
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${c.id}.json`);
  await dl.saveAs(f);
  got[c.id] = { case: c, cfg, screen, file: f,
                doc: JSON.parse(readFileSync(f, 'utf8')) };
}
// --- the launchers come from the DEVICE, not from the markup (T-M15) ------
//
// ★★What is under test is a SOURCE, not a value.  Reading 1.91 off the page
// proves nothing by itself — the markup could have said 1.91.  So the same
// six controls are read on three machines seeded through the import channel:
// EAST as this repository describes it, a variant whose antennas are
// deliberately different, and one that declares no antenna at all.  A page
// that still carried its own numbers would give the same three answers.
const readLaunchers = () => page.evaluate(() => {
  const g = (id) => document.getElementById('model-evolve-' + id);
  const txt = (id) => ((g(id) || {}).textContent || '').trim();
  const grp = (n) => ({
    hidden: !!(g('lhgrp' + n) || {}).hidden,
    power: (g('lhpower' + n) || {}).value,
    powerMax: (g('lhpower' + n) || {}).max,
    lo: (g('lhnpar' + n + 'lo') || {}).value,
    hi: (g('lhnpar' + n + 'hi') || {}).value,
    label: txt('lh-p' + n + '-lab'),
    loLabel: txt('lh-n' + n + 'lo-lab'),
  });
  return { one: grp(1), two: grp(2), src: txt('lh-src'),
           boxDisabled: !!(g('lh') || {}).disabled,
           off: txt('lh-off') };
});

const openOn = async (id) => {
  await page.goto(BASE + 'pages/model.html?device=' + id,
                  { waitUntil: 'networkidle' });
  await page.waitForFunction(
    () => /就绪|Ready|完成|Done|失败|Failed/i.test(
      (document.querySelector('[data-bar="evolve"] .funcbar-state') || {})
        .textContent || ''), null, { timeout: 180000 });
  //: the geometry tier the wave needs, so the switch is not disabled for a
  //: reason that has nothing to do with the launchers
  await page.evaluate(() => {
    const g = document.getElementById('model-evolve-geometry');
    if (g && g.value !== 'device') { g.value = 'device';
      g.dispatchEvent(new Event('change')); }
  });
  return readLaunchers();
};

const seen = { east: await openOn('east'), variant: await openOn(VARIANT_ID) };
seen.none = await openOn(NONE_ID);

await br.close();

// --- the oracle: `lh_deposit` again, from Python, on the file's inputs ----

const PY = `
import json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
from fylite import kernel as K


def rel(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(b))), 1e-300))


def run(path):
    doc = json.load(open(path))
    w = doc.get("fylite:lh")
    if w is None:
        return {"lh": False}
    inp = w["fylite:inputs"]
    psin = np.asarray(w["fylite:psin"], float)
    dvol = np.asarray(w["fylite:dvolume"], float)
    rmaj = np.asarray(w["fylite:r_major"], float)
    ne = np.asarray(w["fylite:n_e"], float)
    te = np.asarray(w["fylite:t_e"], float)
    fpol = np.asarray(w["fylite:f_pol"], float)
    area = np.asarray(w["fylite:area"], float)
    lau = w["fylite:launchers"]
    bands = [tuple(L["fylite:n_parallel_effective"]) for L in lau]
    powers = [L["fylite:power"] for L in lau]

    #: ★the whole chain, re-called on the file's own arrays
    dep = K.lh_deposit(psin, dvol=dvol, rmaj=rmaj, ne=ne, te=te, f_pol=fpol,
                       bands=bands, powers=powers,
                       eta_cd=inp["fylite:eta_cd"], r0=inp["fylite:r0"],
                       xi=inp["fylite:xi"],
                       width_floor=inp["fylite:width_floor"],
                       cd_model=inp["fylite:cd_model"])

    #: ★accessibility re-called on its OWN entry from the file's f_pol and
    #: rmaj: |B| ~ F/R is what the limit is a function of, so this is where
    #: a page that mixed those two arrays up would be caught
    acc = K.lh_accessibility(ne, fpol / np.maximum(rmaj, 1e-6),
                             n_parallel=bands[0][1], xi=inp["fylite:xi"])
    #: ★and the local CD weight — the "fisch" model's closed form (T_e / max(n_e, 1),
    #: heating::lh_efficiency), which code/wave reports as cd_weight; the
    #: flat export that used to spell it retired with T-4 (2026-09-05)
    assert inp["fylite:cd_model"] == "fisch", inp["fylite:cd_model"]
    eff = np.where(ne <= 0.0, 0.0, te / np.maximum(ne, 1.0))

    res_lo = [L["fylite:resonance_psin_lo"] for L in lau]
    res_hi = [L["fylite:resonance_psin_hi"] for L in lau]

    def same(mine, ref):
        #: NaN in the kernel is null in the file — "this band end resonates
        #: nowhere" is a result and it must survive the round trip as one
        out = 0.0
        for a, b in zip(mine, ref):
            if a is None:
                if not np.isnan(b):
                    return float("inf")
            else:
                if np.isnan(b):
                    return float("inf")
                out = max(out, abs(a - b) / max(abs(b), 1e-300))
        return out

    #: the model's own conservation, with no kernel entry in it: the shells
    #: carry exactly the power of the systems that found a resonance
    p_shell = float(np.sum(np.asarray(w["fylite:p_deposited_density"], float)
                           * dvol))
    p_res = float(sum(L["fylite:power"] for L in lau
                      if L["fylite:resonance_psin_lo"] is not None
                      or L["fylite:resonance_psin_hi"] is not None))

    return {
        "lh": True, "n_shell": int(psin.size), "n_lau": len(lau),
        "j_err": rel(w["fylite:j_lh"], dep["j_lh"]),
        "sig_err": rel(w["fylite:sigma_j"], dep["sigma_j"]),
        "p_err": rel(w["fylite:p_deposited_density"], dep["p_dep"]),
        "nacc_err": rel(w["fylite:n_accessible"], dep["n_acc"]),
        "nacc_entry_err": rel(w["fylite:n_accessible"],
                              acc["n_par_accessible"]),
        "cdw_err": rel(w["fylite:cd_weight"], eff),
        "ilau_err": rel([L["fylite:i_lh"] for L in lau], dep["i_lau"]),
        "ilh_err": abs(w["fylite:i_lh"] - dep["i_lh"])
                   / max(abs(dep["i_lh"]), 1e-300),
        "nebar_err": abs(w["fylite:n_e_bar"] - dep["ne_bar"])
                     / max(abs(dep["ne_bar"]), 1e-300),
        "res_lo_err": same(res_lo, dep["res_lo"]),
        "res_hi_err": same(res_hi, dep["res_hi"]),
        #: I = sum(j dS) with the kernel's own area element, so the two
        #: currents in the file are the same current
        "ishell_err": abs(w["fylite:i_lh_shell_sum"]
                          - float(K.shell_sum(
                              np.asarray(w["fylite:j_lh"], float), area)))
                      / max(abs(w["fylite:i_lh"]), 1e-300),
        "p_shell": p_shell, "p_resonant": p_res,
        "p_launched": w["fylite:power_launched"],
        "p_deposited": w["fylite:power_deposited"],
        "i_lh": w["fylite:i_lh"],
        "eta_cd": inp["fylite:eta_cd"], "r0": inp["fylite:r0"],
        "ne_bar": w["fylite:n_e_bar"], "xi": inp["fylite:xi"],
        "upshift": inp["fylite:upshift"],
        "deposited": bool(w["fylite:deposited"]),
        "te_max": w["fylite:t_e_max"],
        "j_max": float(np.max(np.abs(np.asarray(w["fylite:j_lh"], float)))),
        "sigma_max": float(np.max(np.asarray(w["fylite:sigma_j"], float))),
        "p_dep_max": float(np.max(np.asarray(
            w["fylite:p_deposited_density"], float))),
        "p_dep": [float(v) for v in
                  np.asarray(w["fylite:p_deposited_density"], float)],
        "psin": [float(v) for v in psin],
        "nacc_min": float(np.min(np.asarray(w["fylite:n_accessible"], float))),
        "nacc_max": float(np.max(np.asarray(w["fylite:n_accessible"], float))),
        "cdw_min": float(np.min(eff)), "cdw_max": float(np.max(eff)),
        "launchers": [{
            "name": L["fylite:name"], "power": L["fylite:power"],
            "band": L["fylite:n_parallel"],
            "eff": L["fylite:n_parallel_effective"],
            "i": L["fylite:i_lh"],
            "res_lo": L["fylite:resonance_psin_lo"],
            "res_hi": L["fylite:resonance_psin_hi"],
            "t_lo": L["fylite:t_resonant_lo"],
            "t_hi": L["fylite:t_resonant_hi"],
            "reach": L["fylite:accessible_volume_fraction"]} for L in lau],
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
const LIVE = ['base', 'oneend', 'cold', 'two', 'xi'];
const DEP = ['base', 'oneend', 'two', 'xi'];

console.log('\n〔零之前〕发射器设定取自装置文档，不是页面写死的（T-M15）');
{
  const A = (EAST_DOC.lh_antennas || {}).antenna || [];
  const near = (a, b) => Math.abs(+a - +b) < 1e-9;
  ok(A.length === 2, 'EAST 的装置文档声明了两套发射器', String(A.length));
  ok(near(seen.east.one.lo, A[0]['fylite:n_parallel'][0])
     && near(seen.east.one.hi, A[0]['fylite:n_parallel'][1])
     && near(seen.east.two.lo, A[1]['fylite:n_parallel'][0])
     && near(seen.east.two.hi, A[1]['fylite:n_parallel'][1]),
     '两条 n_∥ 带逐端等于文档里的那两条',
     `${seen.east.one.lo}–${seen.east.one.hi} / `
     + `${seen.east.two.lo}–${seen.east.two.hi}`);
  //: ★the one that would have caught the swap this item found: the label的
  //: 名字与那一路的带宽必须来自同一条 antenna
  ok(seen.east.one.label.includes(A[0].name)
     && seen.east.two.label.includes(A[1].name),
     '每一路的标签写的是它自己那条 antenna 的名字（LH1/LH2 不再对调）',
     `${seen.east.one.label} | ${seen.east.two.label}`);
  ok(near(seen.east.one.powerMax, A[0]['fylite:max_power'] / 1e6)
     && near(seen.east.two.powerMax, A[1]['fylite:max_power'] / 1e6),
     '功率滑杆的上界是铭牌功率',
     `${seen.east.one.powerMax} / ${seen.east.two.powerMax} MW`);
  ok(/lh_antennas/.test(seen.east.src)
     && seen.east.src.includes(A[0].name) && seen.east.src.includes(A[1].name),
     '框内那行写明了出处（装置文档的 lh_antennas.antenna）',
     seen.east.src.slice(0, 60) + '…');

  //: ★★换一台装置——这一条才是判据：同样六个控件，另一份文档，另一组数
  const V = VARIANT_ANT[0];
  ok(near(seen.variant.one.lo, V['fylite:n_parallel'][0])
     && near(seen.variant.one.hi, V['fylite:n_parallel'][1])
     && near(seen.variant.one.powerMax, V['fylite:max_power'] / 1e6)
     && seen.variant.one.label.includes(V.name),
     '换一台声明了不同天线的装置：名字、带宽、铭牌全跟着变',
     `${seen.variant.one.label} ${seen.variant.one.lo}–${seen.variant.one.hi}`);
  ok(seen.variant.two.hidden,
     '并且它只有一套发射器时，第二组控件是收起来的，而不是留着上一台的数');
  ok(!near(seen.variant.one.lo, seen.east.one.lo),
     '两台机器给出的确实是两组数（否则上一条恒成立）',
     `${seen.east.one.lo} → ${seen.variant.one.lo}`);

  //: ★一台没有天线的机器：这一档整个停用，而不是拿一个默认值顶上
  ok(seen.none.boxDisabled, '装置不声明天线时，LH 这一档是禁用的');
  ok(/lh_antennas|天线|antenna/.test(seen.none.off),
     '并且说的是「这台机器没有天线」而不是别的理由',
     seen.none.off.slice(0, 50) + '…');
}

console.log('\n〔零〕解析几何档上，波是停用的（那一档没有 ψ_N 图，也没有逐面 F）');
ok(millerState.disabled && !millerState.checked,
   'Miller 档：LH 的开关是禁用的，而不是勾得上却算不了');
ok(!millerState.noteHidden && /ψ|psi/.test(millerState.note)
   && /F\(ψ\)|F\(psi\)/.test(millerState.note),
   '并且说清了缺的是哪两样', millerState.note.slice(0, 56) + '…');

console.log('\n〔一〕每一档都算成了，波真的跑了，I_CD 成了结果');
for (const id of LIVE) {
  ok(/完成|Done/.test(got[id].screen.state), `${id}：算成了`,
     got[id].screen.state.slice(3, 44));
  ok(ref[id].lh === true, `${id}：文件里有波的记录`,
     `${ref[id].n_shell} 个壳层 · ${ref[id].n_lau} 套系统`);
  ok(!got[id].screen.figHidden && !got[id].screen.noteHidden,
     `${id}：沉积图与读数都在屏幕上`);
  ok(got[id].screen.icdDisabled,
     `${id}：I_CD 滑块已停用（驱动电流成了 j_LH）`);
}
ok(ref.off.lh === false, '对照那一档没有波的记录，也没有假装有一份');
ok(got.off.screen.figHidden && got.off.screen.noteHidden,
   '对照那一档屏幕上也没有沉积图');
ok(!got.off.screen.icdDisabled,
   '对照那一档 I_CD 滑块是活的（束也关着，所以只有波能停用它）');

console.log(`\n〔二〕沉积与驱动电流 vs kernel.lh_deposit（判据 ${TOL}，` +
            '来源：会话文件 12 位有效）');
for (const id of LIVE) {
  const r = ref[id];
  ok(r.p_err < TOL, `${id}：逐壳沉积功率密度 p_dep`, r.p_err.toExponential(2));
  ok(r.j_err < TOL, `${id}：逐壳驱动电流密度 j_LH`, r.j_err.toExponential(2));
  ok(r.sig_err < TOL, `${id}：逐壳 σ_j`, r.sig_err.toExponential(2));
  ok(r.nacc_err < TOL, `${id}：逐面可及性上限 n_∥,acc`,
     r.nacc_err.toExponential(2));
  ok(r.ilau_err < TOL && r.ilh_err < TOL,
     `${id}：逐系统与合计的驱动电流`,
     `${r.ilau_err.toExponential(2)} / ${r.ilh_err.toExponential(2)}`);
  ok(r.res_lo_err < TOL && r.res_hi_err < TOL,
     `${id}：带两端各自的共振位置（不共振必须是 null，不是 0）`,
     `${r.res_lo_err.toExponential(2)} / ${r.res_hi_err.toExponential(2)}`);
  ok(r.nebar_err < TOL, `${id}：体积平均密度 n̄_e`,
     r.nebar_err.toExponential(2));
}

console.log('\n〔二乙〕可及性与效率各自是另一个入口重算出来的，而且都不是常数');
for (const id of LIVE) {
  const r = ref[id];
  ok(r.nacc_entry_err < TOL,
     `${id}：n_∥,acc vs kernel.lh_accessibility(n_e, |F|/R)`,
     r.nacc_entry_err.toExponential(2));
  ok(r.cdw_err < TOL, `${id}：局域电流驱动权重 vs fisch 闭式（heating::lh_efficiency）`,
     r.cdw_err.toExponential(2));
}
ok(ref.base.nacc_max > 1.2 * ref.base.nacc_min,
   '可及性上限是一条真剖面而不是一个常数（否则这一条什么也没测）',
   `${ref.base.nacc_min.toFixed(4)} … ${ref.base.nacc_max.toFixed(4)}`);
ok(ref.base.cdw_max > 1.2 * ref.base.cdw_min,
   '电流驱动权重也是',
   `${ref.base.cdw_min.toExponential(2)} … ${ref.base.cdw_max.toExponential(2)}`);
ok(ref.base.ishell_err < TOL,
   'I_LH = shell_sum(j_LH, dS)：文件里的两个电流是同一个电流',
   ref.base.ishell_err.toExponential(2));

console.log('\n〔三〕★★可及性与效率没有被乘成一个数');
for (const id of DEP) {
  const r = ref[id];
  //: I_LH = eta_cd * P / (n_e_bar * R0) in closed form: if the accessible
  //: fraction had been folded in anywhere, this would not hold
  let want = 0;
  for (const L of r.launchers)
    if (L.res_lo !== null || L.res_hi !== null)
      want += r.eta_cd * L.power / (r.ne_bar * r.r0);
  const d = Math.abs(r.i_lh - want) / Math.max(Math.abs(want), 1e-300);
  ok(d < 1e-12,
     `${id}：I_LH 恰为 η_CD·P/(n̄_e R₀) 的闭式——可及份额没有乘进去`,
     `${(r.i_lh / 1e3).toFixed(2)} kA · 相对差 ${d.toExponential(2)}`);
}
ok(ref.base.launchers.every((L) => L.reach > 0 && L.reach <= 1),
   '可及份额自己是一个 (0, 1] 的数，单独报出',
   ref.base.launchers.map((L) => L.reach.toFixed(3)).join(' · '));
ok(/可及体积份额|accessible volume fraction/.test(got.base.screen.scalars)
   && /η/.test(got.base.screen.scalars),
   '屏幕上可及份额与 η_CD 是两行，不是一行');

console.log('\n〔四〕共振温度有闭式：T_res = m_e c²/(2 ξ² n_∥²)（这一条不经内核）');
for (const id of LIVE) {
  const r = ref[id];
  let worst = 0;
  for (const L of r.launchers)
    for (const [np, t] of [[L.eff[0], L.t_lo], [L.eff[1], L.t_hi]])
      worst = Math.max(worst,
        Math.abs(t - ME_C2_EV / (2 * r.xi * r.xi * np * np)) / t);
  ok(worst < 1e-12, `${id}：文件里的共振温度对上闭式`,
     worst.toExponential(2));
}

console.log('\n〔五〕守恒：壳层积出的功率 = 找到共振的那些系统的功率，一瓦不多一瓦不少');
for (const id of LIVE) {
  const r = ref[id];
  const d = Math.abs(r.p_shell - r.p_resonant)
            / Math.max(r.p_launched, 1e-300);
  //: ★1e-11, and the source of the number: the profile travels in the file
  //: at 12 significant digits, so re-summing it here sits on a rounding
  //: floor of order n·1e-12 (measured 1.24e-12 on `oneend` the first time
  //: this bar actually ran) — the original 1e-12 was AT the floor, not
  //: above it.  1e-11 is one order up and eleven below a lost shell.
  ok(d < 1e-11, `${id}：Σ p_dep·dV = ${(r.p_resonant / 1e6).toFixed(3)} MW`,
     `投入 ${(r.p_launched / 1e6).toFixed(2)} MW · 相对差 ${d.toExponential(2)}`);
}

console.log('\n〔六〕上移因子是有效带的来源，而且它真的会改变答案');
for (const id of LIVE) {
  const r = ref[id];
  let worst = 0;
  for (const L of r.launchers)
    worst = Math.max(
      worst,
      Math.abs(L.eff[0] - L.band[0] * r.upshift[0]) / L.eff[0],
      Math.abs(L.eff[1] - L.band[1] * r.upshift[1]) / L.eff[1]);
  ok(worst < 1e-12, `${id}：有效带 = 发射带 × 上移因子`,
     `${r.launchers[0].eff.map((v) => v.toFixed(3)).join('–')}`);
}
ok(ref.cold.deposited === false && ref.cold.p_dep_max === 0
   && ref.cold.i_lh === 0,
   '★不上移那一档：一处也不共振，沉积与电流<strong>恰为</strong>零'
     .replace(/<[^>]+>/g, ''),
   `T_res ${ref.cold.launchers[0].t_hi.toFixed(0)}–` +
   `${ref.cold.launchers[0].t_lo.toFixed(0)} eV vs T_e,max ` +
   `${ref.cold.te_max.toFixed(0)} eV`);
ok(ref.cold.launchers.every((L) => L.res_lo === null && L.res_hi === null),
   '两端都写 null（不是 0——0 会读成「在磁轴上」）');
ok(/没有共振|nothing resonated/.test(got.cold.screen.note)
   && /keV/.test(got.cold.screen.note),
   '★而且页面说了为什么：共振温度对上这张剖面的最高温度',
   got.cold.screen.note.slice(0, 60) + '…');
ok(ref.base.deposited === true && ref.base.p_dep_max > 0,
   '而默认那一档确实沉积了（否则上一条在一次什么都没发生的运行上恒真）',
   `${(ref.base.p_dep_max / 1e6).toFixed(3)} MW/m³`);

console.log('\n〔七〕σ_j 是带两端的间距，不是一个凑出来的宽度');
ok(ref.base.launchers[0].res_lo !== null
   && ref.base.launchers[0].res_hi !== null
   && ref.base.sigma_max > 0,
   '默认档两端都共振，σ_j 非零',
   `ψ_N ${ref.base.launchers[0].res_lo.toFixed(3)} … ` +
   `${ref.base.launchers[0].res_hi.toFixed(3)} · ` +
   `σ_j,max ${(ref.base.sigma_max / 1e3).toFixed(1)} kA/m²`);
ok(ref.oneend.launchers[0].res_lo === null
   && ref.oneend.launchers[0].res_hi !== null
   && ref.oneend.sigma_max === 0,
   '只有一端共振时 σ_j <strong>恰为</strong>零——间距没有第二个端点可量'
     .replace(/<[^>]+>/g, ''),
   `σ_j,max ${ref.oneend.sigma_max}`);
ok(ref.oneend.j_max > 0,
   '而电流仍然驱出来了（σ = 0 不是「没算」）',
   `${(ref.oneend.j_max / 1e3).toFixed(1)} kA/m²`);

console.log('\n〔八〕这不是一条画好的形状：控件一改，层就挪');
const peak = (id) => {
  const p = ref[id].p_dep;
  let k = 0;
  for (let i = 1; i < p.length; i++) if (p[i] > p[k]) k = i;
  return ref[id].psin[k];
};
ok(Math.abs(peak('xi') - peak('base')) > 1e-9,
   'ξ 3.0 → 2.4：沉积峰值换了壳层（T_res ∝ ξ⁻²）',
   `psi_N ${peak('base').toFixed(4)} → ${peak('xi').toFixed(4)}`);
ok(Math.abs(peak('oneend') - peak('base')) > 1e-9
   || ref.oneend.sigma_max !== ref.base.sigma_max,
   '上移因子下端一改，层与 σ_j 至少有一个跟着变',
   `psi_N ${peak('base').toFixed(4)} → ${peak('oneend').toFixed(4)}`);

console.log('\n〔九〕两套系统：各是各的带、各是各的共振、电流可加');
ok(ref.two.n_lau === 2 && ref.base.n_lau === 1,
   '功率为零的那一套被丢掉而不是当作一个零带进来',
   `${ref.base.n_lau} → ${ref.two.n_lau} 套`);
{
  const s = ref.two.launchers.reduce((a, L) => a + L.i, 0);
  ok(Math.abs(ref.two.i_lh - s) / s < 1e-12,
     'I_LH = Σ 逐系统电流', `${(ref.two.i_lh / 1e3).toFixed(2)} kA`);
  ok(ref.two.launchers[0].eff[0] !== ref.two.launchers[1].eff[0]
     && ref.two.launchers[0].res_hi !== ref.two.launchers[1].res_hi,
     '两套系统的有效带与共振位置确实不同',
     ref.two.launchers.map((L) => L.name + ' ψ_N '
       + (L.res_hi === null ? '—' : L.res_hi.toFixed(3))).join(' · '));
  ok(ref.two.p_shell > ref.base.p_shell,
     '第二套投上去之后，沉积功率确实多了',
     `${(ref.base.p_shell / 1e6).toFixed(2)} → ` +
     `${(ref.two.p_shell / 1e6).toFixed(2)} MW`);
}

console.log('\n〔十〕页面没有报错');
ok(errs.length === 0, '没有 pageerror / console error',
   errs.slice(0, 3).join(' | '));

console.log(`\n${n - bad}/${n} 项通过`);
process.exit(bad ? 1 : 0);
