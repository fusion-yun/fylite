// NBI 沉积：页面报的那条剖面，是不是 `kernel.beam_deposit` 那条（T-M2）
//
// ★★WHAT THIS REPLACES.  The 含时演化 bar's auxiliary heating was a
// PRESCRIBED GAUSSIAN: a deposition centre and a width, drawn by the reader
// in rho, plus an I_CD slider beside it.  A shape, not a model — so a
// density scan moved the plasma and not the place the beam stopped, which is
// the one thing a beam model is for.  With the beam on, the deposition is
// `kernel.beam_deposit` (the footprint's rays, the Janev stopping
// cross-section, the attenuation along the chord and the shell binning),
// the electron/ion split is `ion_power_fraction`, the driven current is
// `beam_current` and the shielding is `beam_shielding`.
//
// ★★THE ORACLE IS THE KERNEL ITSELF, called from Python on the inputs the
// page wrote out.  That is legitimate here and it is not "comparing the
// kernel with itself": what is under test is the ASSEMBLY on the browser
// side — which array goes into which argument, in which order, in which
// units, on which grid — and the assembly is exactly where a page can be
// wrong while every kernel entry is right.  The transposed psi_N map is the
// canonical instance: it does not raise, it traces a plausible surface of
// the wrong plasma.
//
// ★So the entries are re-called INDEPENDENTLY here — `beam_deposit`,
// `beam_shielding`, `beam_slowing`, `beam_energy_partition`, `beam_current`,
// `shell_sum` — from the file's own inputs, and every number the page prints
// is checked against that re-call.  Beside that, three checks that do not go
// through any kernel entry at all: `sum(absorbed) + shinethrough = 1`
// (conservation, the only cheap check this model has), the profile is NOT
// the Gaussian it replaced, and moving the chord moves the profile.
//
//   node app/tests/validate-beam.mjs [--playwright DIR] [--chrome BIN]
//                                    [--url BASE]

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser, flag } from './_browser.mjs';
import { seedDevice, missingDeviceMessage } from './_device.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const BASE = flag('url') || 'http://127.0.0.1:8767/app/';

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
  //: ★counter-injection: the sign of the driven current must flip and the
  //: first-orbit-loss mask must stop being all zeros (the kernel refuses to
  //: invent a loss for a co-injected ion, which drifts inward)
  { id: 'counter', name: '逆流注入（首轨损失只在这一档存在）',
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

// --- the oracle: the same kernel entries, from Python, on the file's inputs

const PY = `
import json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
from fylite import kernel as K


def rel(a, b):
    """max |a - b| / max|b| — a RELATIVE difference against the reference's
    own scale, because a per-shell fraction is tiny in the shells the beam
    never reached and dividing by it there would measure nothing."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(b))), 1e-300))


def run(path):
    doc = json.load(open(path))
    b = doc.get("fylite:beam")
    if b is None:
        return {"beam": False}
    inp = b["fylite:inputs"]
    g = inp["fylite:grid"]
    grid = K.Grid(g["r0"], g["z0"], g["dr"], g["dz"], g["nr"], g["nz"])
    #: ★R-major, as the file says and as the kernel demands.  A transposed
    #: map does not raise; it traces a plausible surface of the wrong plasma.
    assert inp["fylite:psin_2d_order"] == "r_major"
    psin2d = np.asarray(inp["fylite:psin_2d"], float).reshape(g["nr"], g["nz"])
    edges = np.asarray(b["fylite:psin_edges"], float)
    prof = np.asarray(inp["fylite:profile_psin"], float)
    ne = np.asarray(inp["fylite:profile_ne"], float)
    te = np.asarray(inp["fylite:profile_te"], float)
    nsh = edges.size - 1
    dvol = np.maximum(np.asarray(b["fylite:dvolume"], float), 1e-9)
    area = np.asarray(b["fylite:area"], float)
    rmin = np.asarray(b["fylite:r_minor"], float)
    rmaj = np.asarray(b["fylite:r_major"], float)
    psin_c = np.asarray(b["fylite:psin"], float)
    zeff_c = np.asarray(b["fylite:z_eff"], float)
    zsum = np.asarray(b["fylite:z_sum"], float)
    shield = np.asarray(b["fylite:shielding_factor"], float)
    ne_c = K.interp(psin_c, prof, ne)
    te_c = K.interp(psin_c, prof, te)
    #: ★one slowing-down evaluation, reused: e_crit / e_gamma / tau_s do not
    #: depend on the beam energy, which is why the kernel takes e_beam
    #: separately in the partition entry
    sd = K.beam_slowing(te_c, ne_c, mass=inp["fylite:mass"], zeff=zeff_c,
                        zsum=zsum, e_beam=1.0)

    comps, dep_err, shine_err = [], 0.0, 0.0
    p_dep = np.zeros(nsh)
    p_ion = np.zeros(nsh)
    j_ref = np.zeros(nsh)
    j_bare = np.zeros(nsh)
    #: T-M12 — the split branches and the prompt torque, re-accumulated
    #: from the SAME per-component records the deposition check uses
    par_ref = np.zeros(nsh)
    perp_ref = np.zeros(nsh)
    tq_ref = np.zeros(nsh)
    for c in b["fylite:components"]:
        out = K.beam_deposit(
            grid, psin2d,
            tangency_radius=inp["fylite:tangency_radius"],
            z_height=inp["fylite:z_height"],
            width_r=inp["fylite:width_r"], width_z=inp["fylite:width_z"],
            direction=inp["fylite:direction"],
            n_width_r=int(inp["fylite:n_width_r"]),
            n_width_z=int(inp["fylite:n_width_z"]),
            n_samples=int(inp["fylite:n_samples"]),
            r_start=inp["fylite:r_start"], psin_prof=prof, ne=ne, te=te,
            psin_edges=edges, mass=inp["fylite:mass"],
            energy=c["fylite:energy"], model=inp["fylite:stopping_model"],
            impurity_form=inp["fylite:impurity_form"])
        ref = out["absorbed"]
        dep_err = max(dep_err, rel(c["fylite:absorbed_fraction"], ref))
        shine_err = max(shine_err,
                        abs(c["fylite:shinethrough"] - out["shinethrough"])
                        / max(abs(out["shinethrough"]), 1e-300))

        #: ★the first-orbit mask: what survives it is what became a power
        #: density, so the page's "retained" array must be the absorbed one
        #: with masked entries zeroed and NOTHING else touched.  Checked
        #: rather than trusted — a page that renormalised after masking
        #: would be putting the lost power back in somewhere else.
        #: ★compared against the FILE's own absorbed array, not against the
        #: re-computed one: this is a STRUCTURAL claim about two arrays in
        #: one document (same values, same rounding), so it is exact —
        #: mixing in the wasm/native difference would turn an exact check
        #: into a tolerance nobody needs.
        got_keep = np.asarray(c["fylite:retained_fraction"], float)
        got_abs = np.asarray(c["fylite:absorbed_fraction"], float)
        mk = c["fylite:orbit_mask"]
        m = np.zeros(nsh, bool) if mk is None else np.asarray(mk, bool)
        mask_ok = bool(np.array_equal(got_keep, np.where(m, 0.0, got_abs)))

        pd = c["fylite:power"] * got_keep / dvol
        p_dep += pd
        part = K.beam_energy_partition(
            sd["e_crit"], sd["tau_s"],
            e_beam=np.full(nsh, c["fylite:energy"]))
        p_ion += pd * part["ion_fraction"]
        pitch = np.asarray(c["fylite:pitch"], float)
        #: ★T-M12: the branches out of the pitch-preserving split and the
        #: prompt torque — kernel entries re-called INDEPENDENTLY on this
        #: component's own pd / pitch / energy, i.e. "同一次调用出来的量"
        _, d_par, d_perp = K.fast_ion_pressure_split(pd, part["tau_eff"],
                                                     pitch)
        par_ref += d_par
        perp_ref += d_perp
        tq_ref += K.beam_torque(pd, pitch, rmaj,
                                energy=c["fylite:energy"],
                                mass=inp["fylite:mass"])
        j_ref += K.beam_current(
            pd, pitch, e_crit=sd["e_crit"], e_gamma=sd["e_gamma"],
            tau_s=sd["tau_s"], rmin=rmin, rmaj=rmaj, shield=shield,
            energy=c["fylite:energy"], mass=inp["fylite:mass"],
            multiplier=1.0)
        #: ★the same current with the shielding removed: if it comes out the
        #: same, the separately-reported factor is a decoration
        j_bare += K.beam_current(
            pd, pitch, e_crit=sd["e_crit"], e_gamma=sd["e_gamma"],
            tau_s=sd["tau_s"], rmin=rmin, rmaj=rmaj, shield=np.ones(nsh),
            energy=c["fylite:energy"], mass=inp["fylite:mass"],
            multiplier=1.0)

        comps.append({"energy": c["fylite:energy"],
                      "power": c["fylite:power"],
                      #: sum(absorbed) + shinethrough = 1 — the model's own
                      #: conservation, which touches no page number at all
                      "closure": float(ref.sum() + out["shinethrough"]),
                      "shine": float(out["shinethrough"]),
                      "mask_ok": mask_ok,
                      "n_lost": int(m.sum())})

    #: the shielding, re-called: G and the surviving fraction are two
    #: numbers out of one entry and the page must not have folded them
    sh = K.beam_shielding(np.asarray(b["fylite:trapped_fraction"], float),
                          zeff_c)
    j_mine = np.asarray(b["fylite:j_nbi"], float)
    i_ref = K.shell_sum(j_mine, area)
    pabs_ref = K.shell_sum(np.asarray(b["fylite:p_deposited"], float), dvol)
    pe_mine = np.asarray(b["fylite:p_electron"], float)
    pi_mine = np.asarray(b["fylite:p_ion"], float)
    #: T-M12: the file's branches / torque against the re-accumulation, the
    #: two closure identities, and the total against shell_sum
    par_mine = np.asarray(b["fylite:p_fast_par"], float)
    perp_mine = np.asarray(b["fylite:p_fast_perp"], float)
    tq_mine = np.asarray(b["fylite:torque_nbi"], float)
    pf_mine = np.asarray(b["fylite:p_fast"], float)
    w_mine = 1.5 * pf_mine                      # W = (3/2) p_iso, exact
    tm12 = {
        "par_err": rel(par_mine, par_ref),
        "perp_err": rel(perp_mine, perp_ref),
        "tq_err": rel(tq_mine, tq_ref),
        "energy_id": rel(par_mine / 2.0 + perp_mine, w_mine),
        "trace_id": rel((par_mine + 2.0 * perp_mine) / 3.0, pf_mine),
        "tq_total_err": abs(b["fylite:torque_nbi_total"]
                            - K.shell_sum(tq_mine, dvol))
                        / max(abs(K.shell_sum(tq_mine, dvol)), 1e-300),
        "tq_total": b["fylite:torque_nbi_total"],
        "tq_sign": float(np.sign(b["fylite:torque_nbi_total"])),
        "par_peak": float(np.max(par_mine)),
        "perp_peak": float(np.max(perp_mine)),
        #: anisotropy is REAL for a tangential beam: at the pressure peak
        #: the two branches must differ (isotropy would make them equal)
        "aniso": float(np.max(np.abs(par_mine - perp_mine))
                       / max(float(np.max(perp_mine)), 1e-300)),
    }

    return {
        "beam": True, "n_shell": nsh,
        "dep_err": dep_err, "shine_err": shine_err,
        "sh_err": rel(b["fylite:shielding_factor"], sh["factor"]),
        "g_err": rel(b["fylite:shielding_g"], sh["g"]),
        "j_err": rel(j_mine, j_ref),
        "i_err": abs(b["fylite:i_nbi"] - i_ref) / max(abs(i_ref), 1e-300),
        "p_err": rel(b["fylite:p_deposited"], p_dep),
        "pabs_err": abs(b["fylite:power_absorbed"] - pabs_ref)
                    / max(abs(pabs_ref), 1e-300),
        "pi_err": rel(pi_mine, p_ion),
        "split_sum": float(np.max(np.abs(
            pe_mine + pi_mine - np.asarray(b["fylite:p_deposited"], float)))),
        "components": comps,
        "shine": b["fylite:shinethrough"],
        "orbit": b["fylite:orbit_loss_fraction"],
        "i_nbi": b["fylite:i_nbi"],
        "shield_min": float(np.min(sh["factor"])),
        "shield_max": float(np.max(sh["factor"])),
        "p_dep": [float(v) for v in np.asarray(b["fylite:p_deposited"], float)],
        "psin": [float(v) for v in psin_c],
        "j_peak": float(np.max(np.abs(j_mine))),
        "j_bare_peak": float(np.max(np.abs(j_bare))),
        "ion_fraction": float(
            np.sum(pi_mine * dvol)
            / max(float(np.sum((pe_mine + pi_mine) * dvol)), 1e-300)),
        "tm12": tm12,
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

console.log(`\n〔二〕沉积剖面 vs kernel.beam_deposit（判据 ${TOL}，来源：会话文件 12 位有效）`);
for (const id of ['co', 'counter', 'outer', 'three']) {
  const r = ref[id];
  ok(r.dep_err < TOL, `${id}：逐壳吸收份额`, r.dep_err.toExponential(2));
  ok(r.shine_err < TOL, `${id}：穿透份额`, r.shine_err.toExponential(2));
}

console.log('\n〔二乙〕首轨掩膜只是把几个壳层清零，没有把丢掉的功率放回别处');
for (const id of ['co', 'counter', 'outer', 'three'])
  ok(ref[id].components.every((c) => c.mask_ok),
     `${id}：留存份额 = 吸收份额 × (1 − 掩膜)`,
     `被清零的壳层 ${ref[id].components.map((c) => c.n_lost).join(' · ')}`);

console.log('\n〔三〕守恒：吸收 + 穿透 = 1（这一条不经过页面的任何数）');
for (const id of ['co', 'counter', 'outer', 'three'])
  ok(ref[id].components.every((c) => Math.abs(c.closure - 1) < 1e-9),
     `${id}：${ref[id].components.length} 个能量成分各自闭合`,
     ref[id].components.map((c) => (c.closure - 1).toExponential(1)).join(' · '));

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

console.log('\n〔四乙〕沉积功率密度与吸收总功率，也是重算出来的');
for (const id of ['co', 'three']) {
  ok(ref[id].p_err < TOL, `${id}：p_dep = P·留存份额/dV 逐壳`,
     ref[id].p_err.toExponential(2));
  ok(ref[id].pabs_err < TOL, `${id}：P_abs = shell_sum(p_dep, dV)`,
     ref[id].pabs_err.toExponential(2));
}

console.log('\n〔五〕束驱电流与屏蔽因子，是两个数');
for (const id of ['co', 'counter', 'three']) {
  ok(ref[id].j_err < TOL, `${id}：j_NBI vs kernel.beam_current 逐壳`,
     ref[id].j_err.toExponential(2));
  ok(ref[id].i_err < TOL, `${id}：I_NBI = shell_sum(j, dS)`,
     ref[id].i_err.toExponential(2));
  ok(ref[id].sh_err < TOL && ref[id].g_err < TOL,
     `${id}：屏蔽的两个数（G 与存活份额）vs kernel.beam_shielding`,
     `${ref[id].sh_err.toExponential(2)} / ${ref[id].g_err.toExponential(2)}`);
}
//: ★the shielding must BITE: if the same current comes out with shield = 1
//: then reporting the factor separately would be reporting a decoration
ok(ref.co.j_bare_peak > ref.co.j_peak * 1.05,
   '屏蔽确实起了作用（去掉它电流明显更大，所以那个因子不是摆设）',
   `峰值 ${(ref.co.j_peak / 1e3).toFixed(1)} → ` +
   `${(ref.co.j_bare_peak / 1e3).toFixed(1)} kA/m²`);
ok(ref.co.shield_min > 0 && ref.co.shield_max < 1,
   '存活份额逐壳落在 (0, 1) 之内',
   `${ref.co.shield_min.toFixed(4)} … ${ref.co.shield_max.toFixed(4)}`);
ok(/屏蔽因子|shielding factor/.test(got.co.screen.note),
   '屏幕上屏蔽因子是单列的，不是乘进电流里的一个数');

console.log('\n〔六〕逆流注入：电流反号，首轨损失只在这一档不为零');
ok(Math.sign(ref.counter.i_nbi) === -Math.sign(ref.co.i_nbi),
   '顺流与逆流的束驱电流反号',
   `${(ref.co.i_nbi / 1e3).toFixed(1)} kA vs ${(ref.counter.i_nbi / 1e3).toFixed(1)} kA`);
ok(ref.co.orbit === 0 && ref.counter.orbit > 0,
   '首轨损失：顺流恰为零（内核拒绝为向内漂的离子编一个损失），逆流不为零',
   `顺流 ${(100 * ref.co.orbit).toFixed(2)} % · 逆流 ${(100 * ref.counter.orbit).toFixed(2)} %`);

console.log('\n〔七〕电子 / 离子分配是解出来的，不是那两个滑块');
for (const id of ['co', 'three']) {
  ok(ref[id].pi_err < TOL,
     `${id}：p_i vs ion_power_fraction(E_c, E) 逐壳`,
     ref[id].pi_err.toExponential(2));
  ok(ref[id].split_sum < 1e-6 * Math.max(...ref[id].p_dep),
     `${id}：p_e + p_i = p_dep`, ref[id].split_sum.toExponential(2));
}
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

console.log(`\n〔八乙〕T-M12：快离子压强分两支、束力矩取代滑块（判据 ${TOL}）`);
for (const id of ['co', 'counter', 'three']) {
  const t = ref[id].tm12;
  //: ★the closure criterion verbatim: the branches and the torque must be
  //: the quantities out of the SAME `beam_deposit` call — re-accumulated
  //: here per component from the file's own retained fraction and pitch
  ok(t.par_err < TOL && t.perp_err < TOL,
     `${id}：p_∥ / p_⊥ vs kernel.fast_ion_pressure_split 逐壳`,
     `${t.par_err.toExponential(2)} / ${t.perp_err.toExponential(2)}`);
  ok(t.tq_err < TOL,
     `${id}：τ_φ vs kernel.beam_torque 逐壳（同一份 pd 与 ξ）`,
     t.tq_err.toExponential(2));
  //: the two identities that CLOSE the split, on the file's own arrays
  ok(t.energy_id < 1e-9, `${id}：p_∥/2 + p_⊥ = W 恒等`,
     t.energy_id.toExponential(2));
  ok(t.trace_id < 1e-9, `${id}：(p_∥ + 2p_⊥)/3 = p_fast 恒等（标量道没动）`,
     t.trace_id.toExponential(2));
  ok(t.tq_total_err < TOL, `${id}：力矩总量 = shell_sum(τ_φ, dV)`,
     `${t.tq_total.toFixed(3)} N·m · ` + t.tq_total_err.toExponential(2));
}
//: ★the split must SPLIT: a tangential beam's two branches differ, and a
//: page that filled both with the isotropic (2/3)W would pass every
//: identity above
ok(ref.co.tm12.aniso > 0.05,
   '切向束的两支确实不相等（各向异性不是改了个名字）',
   `max|p_∥ − p_⊥|/max(p_⊥) ${(100 * ref.co.tm12.aniso).toFixed(1)} %`);
//: the torque's sign is the pitch's — co positive, counter negative
ok(ref.co.tm12.tq_sign > 0 && ref.counter.tm12.tq_sign < 0,
   '力矩的符号是 pitch 的：顺流为正、逆流为负',
   `${ref.co.tm12.tq_total.toFixed(3)} vs ` +
   `${ref.counter.tm12.tq_total.toFixed(3)} N·m`);
//: and the READINGS carry the two computed rows where the slider's number
//: used to be
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
