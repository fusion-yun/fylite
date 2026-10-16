// NBI 沉积：页面报的那条剖面，是不是 `code/beam` 那条（T-M2；REL-34 改写）
//
// ★★WHAT THIS REPLACES.  The 含时演化 bar's auxiliary heating was a
// PRESCRIBED GAUSSIAN: a deposition centre and a width, drawn by the reader
// in rho, plus an I_CD slider beside it.  A shape, not a model — so a
// density scan moved the plasma and not the place the beam stopped, which is
// the one thing a beam model is for.  With the beam on, the deposition is
// the kernel's `code/beam` door — since REL-33(b1) one call to the
// clean-room `hcd::nbi_deposit`.
//
// ★★REL-34 (2026-09-24): this gate used to re-run the OLD recipe (the flat
// `beam_deposit` · `beam_slowing` · `beam_energy_partition` ·
// `fast_ion_pressure_split` · `beam_torque` · `beam_current` ·
// `beam_shielding` entries, per component, from Python) and compare the page
// to it.  That recipe was METIS-lineage code living in the tests; it is gone.
// The door does the assembly now and the page only READS it, so what is
// held here is what the page's file must satisfy on its own: the power
// account closes per energy component and in total, the profiles integrate
// to the totals the page prints, the electron / ion split and the pressure
// branches are identities of the door's own arrays, the two shielding
// numbers are the pair F = 1 − (1 − G)/Z_eff (Z_b = 1), and the signs and
// the geometry move the way the physics says.  Beside that, the page checks
// that never went through a kernel entry: the Miller tier disables the beam,
// the replaced controls are disabled, the profile is NOT the Gaussian, and
// moving the chord moves the profile.
//
//   node ui/tests/validate-beam.mjs [--playwright DIR] [--chrome BIN]
//                                    [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const BASE = flag('url') || 'http://127.0.0.1:8767/ui/';

//: ★the file writes the beam block at 12 significant digits — not this
//: file's usual 7 — precisely so this comparison can be made at 1e-6: an
//: oracle re-running the call on inputs rounded at 7 digits would be
//: measuring the rounding it introduced itself.  1e-6 is the closure
//: criterion this feature was written against.
//:
//: ★What is actually left at 12 digits is NOT the rounding: measured here,
//: the deposition agrees to 4.6e-12 and the driven current to 5.5e-12,
//: which is the two builds of the same Rust — wasm and the native `.so` —
//: differing in the libm behind `exp`/`ln` inside the stopping
//: cross-section.  1e-6 sits six orders above that floor and six orders
//: below any modelling choice, which is what makes it a criterion rather
//: than a number picked to pass.
//: ★REL-34: every check below is now within ONE file (the page's own
//: numbers), so what is left at 12 digits is the page's rounding alone.
const TOL = 1e-6;

const BASECASE = {
  geometry: 'device', 'ch-heat': true, 'ch-density': false,
  'ch-current': true, nsteps: 10, nlev: 21, dt: 0.001, dttarget: 0,
  fuel: 0, alpha: false, brem: true, ohmic: true, bootstrap: true,
  zeff: 1.5, chiratio: 1, dchi: 0.3, pinch: 0, dpc: 0, closure: 0,
  chi0: 1.0, te0: 3, ti0: 2.5, edgete: 0.3, edgeti: 0.3, edgene: 0.5,
  ne0: 3, peakt: 1.5, peakn: 0.5, vloop: 0.5, ip: 400, couple: 0,
  freeiter: 600, species: '', cimp: 0, wave: false,
  //: the Gaussian's own controls, set even in the beam cases: with the
  //: beam on they are disabled, and a case that left them at the previous
  //: case's values would be comparing two runs that differ in more than
  //: the one thing under test
  pe: 2, pi: 2, dep: 0, depw: 0.3, icd: 0,
  beam: true, beampower: 4, beamenergy: 60, beamrtan: 1.26, beamz: 0,
  beamwidth: 0.10, beamdir: '1', beamstop: 'janev',
  beamf1: 1, beamf2: 0, beamf3: 0, beamshells: 24, beamorbit: true,
};

const CASES = [
  { id: 'co', name: '顺流注入 · 60 keV 单能', cfg: {} },
  //: ★counter-injection: the signs of the driven current and the torque
  //: must flip
  { id: 'counter', name: '逆流注入',
    cfg: { beamdir: '-1' } },
  //: ★a chord that passes further out: the deposition must MOVE.  This is
  //: the check the prescribed Gaussian could never pass — its profile is
  //: what the reader drew, and no beam geometry enters it.
  { id: 'outer', name: '切向半径外移 1.26 → 2.00 m',
    cfg: { beamrtan: 2.00 } },
  //: ★three energy components, because they change the stopping depth
  //: materially and one call per component is the granularity the kernel
  //: works at — a page that summed them wrong would still look plausible
  { id: 'three', name: '全 / 半 / 三分之一 三个能量成分',
    cfg: { beamf1: 0.55, beamf2: 0.30, beamf3: 0.15 } },
  //: ★the Gaussian, for the comparison: same power, no beam
  { id: 'gauss', name: '规定高斯（对照）',
    cfg: { beam: false, pe: 2, pi: 2, dep: 0, depw: 0.3 } },
];

const OUT = mkdtempSync(join(tmpdir(), 'nb-'));
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

//: ★★THE ANALYTIC TIER FIRST, before anything is run: the beam needs a
//: psi_N map on the (R, Z) grid and Miller has none, so the control must be
//: DISABLED there rather than silently producing a deposition through a
//: flux map nobody computed.
await page.evaluate(() => {
  const g = document.getElementById('model-evolve-geometry');
  g.value = 'miller'; g.dispatchEvent(new Event('change'));
});
const millerState = await page.evaluate(() => ({
  disabled: document.getElementById('model-evolve-beam').disabled,
  checked: document.getElementById('model-evolve-beam').checked,
  note: (document.getElementById('model-evolve-beam-off') || {}).textContent
        || '',
  noteHidden: (document.getElementById('model-evolve-beam-off') || {}).hidden,
}));

const RUN = '#model-evolve-run';
const got = {};
for (const c of CASES) {
  const cfg = { ...BASECASE, ...c.cfg };
  await page.evaluate((v) => {
    //: ★the geometry first, then the beam switch, then the beam's own
    //: controls: the switch is disabled off the two tiers that have a psi
    //: map, and its panel's controls only mean anything once it is on.
    const rank = (id) => (id === 'geometry' ? 0
                          : id === 'beam' ? 1
                          : /^beam/.test(id) ? 2 : 0);
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
  //: idle, then running, then done — the status line is the previous run's
  //: until the new one starts
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
    note: (document.getElementById('model-evolve-beam-note') || {})
          .textContent || '',
    noteHidden: !!(document.getElementById('model-evolve-beam-note') || {})
                 .hidden,
    scalars: (document.getElementById('model-evolve-scalars') || {})
             .textContent || '',
    figHidden: !!(document.getElementById('model-evolve-beamfig-box') || {})
                .hidden,
    //: ★the controls the beam REPLACES: with it on they must be
    //: disabled, not merely ignored downstream (T-M12 added the torque)
    disabled: ['pe', 'pi', 'dep', 'depw', 'icd', 'torque'].map((id) =>
      document.getElementById('model-evolve-' + id).disabled),
  }));
  await page.click('#model-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#model-iofmt-evolve-json')]);
  const f = join(OUT, `${c.id}.json`);
  await dl.saveAs(f);
  got[c.id] = { case: c, cfg, screen, file: f,
                doc: JSON.parse(readFileSync(f, 'utf8')) };
}
await br.close();

// --- the file's own books, in numpy (no kernel entry is re-called) ------

const PY = `
import json, sys
import numpy as np


def rel(a, b):
    """max |a - b| / max|b| — a RELATIVE difference against the reference's
    own scale."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(b))), 1e-300))


def run(path):
    doc = json.load(open(path))
    b = doc.get("fylite:beam")
    if b is None:
        return {"beam": False}
    A = lambda k: np.asarray(b[k], float)  # noqa: E731
    edges, dvol, area = A("fylite:psin_edges"), A("fylite:dvolume"), A("fylite:area")
    rmaj, zeff = A("fylite:r_major"), A("fylite:z_eff")
    pdep, pe, pi = A("fylite:p_deposited"), A("fylite:p_electron"), A("fylite:p_ion")
    pf, par, perp = A("fylite:p_fast"), A("fylite:p_fast_par"), A("fylite:p_fast_perp")
    tq, j = A("fylite:torque_nbi"), A("fylite:j_nbi")
    g, f = A("fylite:shielding_g"), A("fylite:shielding_factor")
    w = 1.5 * pf                               # W = (3/2) p_iso, exact
    comps = []
    for c in b["fylite:components"]:
        comps.append({"energy": c["fylite:energy"], "power": c["fylite:power"],
                      #: confined + shine-through + orbit-lost = 1 per component
                      "closure": float(c["fylite:absorbed_total"] + c["fylite:shinethrough"]
                                       + c["fylite:orbit_loss"]),
                      "absorbed_w": float(c["fylite:power"] * c["fylite:absorbed_total"])})
    p_inj, p_abs = b["fylite:power_injected"], b["fylite:power_absorbed"]
    return {
        "beam": True, "n_shell": int(edges.size - 1),
        "components": comps,
        "inj_err": abs(sum(c["power"] for c in comps) - p_inj) / p_inj,
        "abs_comp_err": abs(sum(c["absorbed_w"] for c in comps) - p_abs) / p_abs,
        "total_closure": float((p_abs / p_inj) + b["fylite:shinethrough"] + b["fylite:orbit_loss_fraction"]),
        "pabs_err": abs(float(np.sum(pdep * dvol)) - p_abs) / p_abs,
        "split_sum": rel(pe + pi, pdep),
        "i_err": abs(float(np.sum(j * area)) - b["fylite:i_nbi"]) / max(abs(b["fylite:i_nbi"]), 1e-300),
        "area_err": rel(area, dvol / (2.0 * np.pi * rmaj)),
        "shield_pair": rel(f, 1.0 - (1.0 - g) / zeff),
        "shield_min": float(min(np.min(f), np.min(g))),
        "shield_max": float(max(np.max(f), np.max(g))),
        "energy_id": rel(par / 2.0 + perp, w),
        "trace_id": rel((par + 2.0 * perp) / 3.0, pf),
        "tq_total_err": abs(b["fylite:torque_nbi_total"] - float(np.sum(tq * dvol)))
                        / max(abs(b["fylite:torque_nbi_total"]), 1e-300),
        "tq_total": b["fylite:torque_nbi_total"],
        "aniso": float(np.max(np.abs(par - perp)) / max(float(np.max(perp)), 1e-300)),
        "shine": b["fylite:shinethrough"],
        "orbit": b["fylite:orbit_loss_fraction"],
        "i_nbi": b["fylite:i_nbi"],
        "p_dep": [float(v) for v in pdep],
        "psin": [float(v) for v in A("fylite:psin")],
        "nonneg": bool(np.all(pdep >= 0) and np.all(pf >= 0) and np.all(pe >= 0) and np.all(pi >= 0)),
        "ion_fraction": float(np.sum(pi * dvol) / max(float(np.sum((pe + pi) * dvol)), 1e-300)),
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

// --- assertions --------------------------------------------------------

let bad = 0, n = 0;
const ok = (cond, what, detail) => {
  n += 1;
  if (!cond) { bad += 1; console.log('  ✗ ' + what + (detail ? ' — ' + detail : '')); }
  else console.log('  ✓ ' + what + (detail ? ' — ' + detail : '')); };

console.log('\n〔零〕解析几何档上，束是停用的（那一档没有 ψ_N 图）');
ok(millerState.disabled && !millerState.checked,
   'Miller 档：束的开关是禁用的，而不是勾得上却算不了');
ok(!millerState.noteHidden && /ψ|psi/.test(millerState.note),
   '并且说清了缺的是什么', millerState.note.slice(0, 48) + '…');

console.log('\n〔一〕每一档都算成了，且束真的跑了');
for (const id of ['co', 'counter', 'outer', 'three']) {
  ok(/完成|Done/.test(got[id].screen.state), `${id}：算成了`,
     got[id].screen.state.slice(3, 46));
  ok(ref[id].beam === true, `${id}：文件里有束的记录`,
     `${ref[id].n_shell} 个壳层`);
  ok(!got[id].screen.figHidden && !got[id].screen.noteHidden,
     `${id}：沉积图与束的读数都在屏幕上`);
  ok(got[id].screen.disabled.every(Boolean),
     `${id}：P_e / P_i / 沉积中心 / 沉积宽度 / I_CD / 力矩 六个控件已停用`);
}
ok(ref.gauss.beam === false,
   '对照那一档（规定高斯）没有束的记录，也没有假装有一份');
ok(got.gauss.screen.figHidden && got.gauss.screen.noteHidden,
   '对照那一档屏幕上也没有沉积图');
ok(got.gauss.screen.disabled.every((v) => !v),
   '对照那一档六个控件都是活的');

const IDS = ['co', 'counter', 'outer', 'three'];
console.log('\n〔二〕功率账：每个能量成分与总账各自闭合（约束 + 穿透 + 首轨损失 = 注入）');
for (const id of IDS) {
  const r = ref[id];
  ok(r.components.every((c) => Math.abs(c.closure - 1) < 1e-9),
     `${id}：${r.components.length} 个能量成分各自闭合`,
     r.components.map((c) => (c.closure - 1).toExponential(1)).join(' · '));
  ok(r.inj_err < TOL && r.abs_comp_err < TOL,
     `${id}：成分之和 = 注入功率、成分的约束之和 = 吸收功率`,
     `${r.inj_err.toExponential(2)} / ${r.abs_comp_err.toExponential(2)}`);
  ok(Math.abs(r.total_closure - 1) < TOL, `${id}：总账 P_abs/P_inj + 穿透 + 首轨损失 = 1`,
     (r.total_closure - 1).toExponential(2));
}

console.log('\n〔三〕剖面积分回到页面印的总量');
for (const id of IDS) {
  const r = ref[id];
  ok(r.pabs_err < TOL, `${id}：P_abs = Σ p_dep dV`, r.pabs_err.toExponential(2));
  ok(r.i_err < TOL && r.area_err < 1e-9, `${id}：I_NBI = Σ j dS，dS = dV/(2πR)`,
     `${r.i_err.toExponential(2)} / ${r.area_err.toExponential(2)}`);
  ok(r.split_sum < 1e-9, `${id}：p_e + p_i = p_dep`, r.split_sum.toExponential(2));
  ok(r.nonneg, `${id}：p_dep · p_fast · p_e · p_i 处处非负`);
}

console.log('\n〔四〕穿透是单独的一个数，不是功率上的一刀');
for (const id of ['co', 'outer']) {
  const sh = ref[id].shine;
  ok(sh > 0 && sh < 1, `${id}：穿透份额落在 (0, 1) 之内`,
     (100 * sh).toFixed(2) + ' %');
}
ok(ref.outer.shine > ref.co.shine,
   '切向半径外移，穿透变多（弦更短、穿过的密度更低）',
   `${(100 * ref.co.shine).toFixed(2)} % → ${(100 * ref.outer.shine).toFixed(2)} %`);
ok(/穿透|shine/.test(got.co.screen.note)
   && /穿透份额|shine-through/.test(got.co.screen.scalars),
   '屏幕上穿透是自己一行，不是混在加热功率里');

console.log('\n〔五〕屏蔽是两个数，且是一对（F = 1 − (1 − G)/Z_eff，Z_b = 1）');
for (const id of ['co', 'counter', 'three']) {
  ok(ref[id].shield_pair < 1e-9, `${id}：存活份额与 G 成对`,
     ref[id].shield_pair.toExponential(2));
}
ok(ref.co.shield_min > 0 && ref.co.shield_max < 1,
   'G 与存活份额逐壳落在 (0, 1) 之内',
   `${ref.co.shield_min.toFixed(4)} … ${ref.co.shield_max.toFixed(4)}`);
ok(/屏蔽因子|shielding factor/.test(got.co.screen.note),
   '屏幕上屏蔽因子是单列的，不是乘进电流里的一个数');

console.log('\n〔六〕逆流注入：电流与力矩反号，首轨损失是份额');
ok(Math.sign(ref.counter.i_nbi) === -Math.sign(ref.co.i_nbi),
   '顺流与逆流的束驱电流反号',
   `${(ref.co.i_nbi / 1e3).toFixed(1)} kA vs ${(ref.counter.i_nbi / 1e3).toFixed(1)} kA`);
//: ★REL-34: no「顺流恰为零」— the clean-room first-orbit model loses co-passing
//: births on the inboard leg, and at R_t = 1.26 m the chord passes inside the
//: inboard edge, so the co loss is not zero there (and need not be below the
//: counter one); the ordering is held in tests/test_nbi.py at R_t inside the plasma
for (const id of ['co', 'counter'])
  ok(ref[id].orbit >= 0 && ref[id].orbit < 1, `${id}：首轨损失份额落在 [0, 1) 之内`,
     (100 * ref[id].orbit).toFixed(2) + ' %');

console.log('\n〔七〕电子 / 离子分配是解出来的，不是那两个滑块');
//: ★the case ran with P_e = P_i = 2 MW on the disabled sliders, so a page
//: that had passed those through would come back with a 50:50 split — which
//: is why the two are set EQUAL in the base case
ok(Math.abs(ref.co.ion_fraction - 0.5) > 0.02,
   '而且它不是 50:50——两个停用的滑块正好是 2 / 2 MW，直接透传会给出 0.5',
   `离子份额 ${ref.co.ion_fraction.toFixed(4)}`);

console.log('\n〔八〕这不是那条高斯：形状会跟着束的几何走');
const peak = (id) => {
  const p = ref[id].p_dep;
  let k = 0;
  for (let i = 1; i < p.length; i++) if (p[i] > p[k]) k = i;
  return ref[id].psin[k];
};
ok(Math.abs(peak('outer') - peak('co')) > 1e-9,
   '切向半径一改，沉积峰值就换了壳层',
   `psi_N ${peak('co').toFixed(4)} → ${peak('outer').toFixed(4)}`);
const relDiff = (() => {
  let m = 0;
  for (let i = 0; i < ref.co.p_dep.length; i++) {
    const a = ref.co.p_dep[i], b = ref.three.p_dep[i];
    m = Math.max(m, Math.abs(a - b) / Math.max(Math.abs(a), 1e-300));
  }
  return m;
})();
ok(relDiff > 0.05,
   '三个能量成分与单能是不同的剖面（半能与三分之一能停得更外面）',
   `逐壳最大相对差 ${(100 * relDiff).toFixed(1)} %`);

console.log('\n〔八乙〕T-M12：快离子压强分两支、束力矩取代滑块');
for (const id of ['co', 'counter', 'three']) {
  const t = ref[id];
  ok(t.energy_id < 1e-9, `${id}：p_∥/2 + p_⊥ = W 恒等`, t.energy_id.toExponential(2));
  ok(t.trace_id < 1e-9, `${id}：(p_∥ + 2p_⊥)/3 = p_fast 恒等（标量道没动）`,
     t.trace_id.toExponential(2));
  ok(t.tq_total_err < TOL, `${id}：力矩总量 = Σ τ_φ dV`,
     `${t.tq_total.toFixed(3)} N·m · ` + t.tq_total_err.toExponential(2));
}
ok(ref.co.aniso > 0.05,
   '切向束的两支确实不相等（各向异性不是改了个名字）',
   `max|p_∥ − p_⊥|/max(p_⊥) ${(100 * ref.co.aniso).toFixed(1)} %`);
ok(ref.co.tq_total > 0 && ref.counter.tq_total < 0,
   '力矩的符号是 pitch 的：顺流为正、逆流为负',
   `${ref.co.tq_total.toFixed(3)} vs ${ref.counter.tq_total.toFixed(3)} N·m`);
ok(/束力矩/.test(got.co.screen.scalars),
   '读数里的束力矩是算出的那一行（滑块已停用）');
ok(/快离子储能/.test(got.co.screen.scalars),
   '快离子储能 W_fast 有自己一行（不在 w_th 里）');
ok(!/束力矩/.test(got.gauss.screen.scalars)
   && !/快离子储能/.test(got.gauss.screen.scalars),
   '对照那一档两行都不在——没有束就没有这两个数');

console.log('\n〔九〕页面没有报错');
ok(errs.length === 0, '没有 pageerror / console error',
   errs.slice(0, 3).join(' | '));

console.log(`\n${n - bad}/${n} 项通过`);
process.exit(bad ? 1 : 0);
