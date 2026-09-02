// Oracle test for the kinetic reconstruction page and its posterior.
//
// The page had no gate at all while it grew a Monte-Carlo error bar, and an
// error bar is exactly the kind of number that looks right whatever it is.
// Four things are checked, each of which can fail while the others pass:
//
//   1. THE FIT AGREES WITH ITS OWN CONSTRAINT.  The reconstruction is driven
//      by the deck's flux loops; the fitted Ip must come back as the deck's
//      Ip, and the forward-modelled loop readings must sit on the measured
//      ones.  A fit that quietly ignored the magnetics would still converge.
//   2. li(3) IS THE KERNEL'S, NOT THE PAGE'S.  The exported psi map is fed
//      back through the SAME kernel entry from Python (ctypes on the shipped
//      `libfylite_kernel.so`).  A page that recomputed the integral in JavaScript —
//      or handed over the wrong gauge — reads plausibly and differs here.
//   3. THE POSTERIOR IS THE MEMBERS.  The reported mean / sigma / percentiles
//      are recomputed with numpy from the member values the page exports.
//      A summary that cannot be re-derived from its own members is a
//      decoration, and this is the check that says so.
//   4. THE BOOTSTRAP IS THE KERNEL'S TOO.  With a density supplied, j_bs is
//      recomputed natively from the ten per-surface profiles the page
//      exports.  A page that assembled the Redl inputs in the wrong order —
//      psi per radian against psi normalised, eV against keV — gets a smooth
//      curve of the wrong size, which is why the inputs travel with it.
//   5. THE PROBES ARE THE SOLVED FIELD, PROJECTED.  The 79 predicted probe
//      readings are recomputed from the exported psi map in Python — sampled
//      at each probe and projected on its own angle — and compared with the
//      delivered reconstruction's own channel values.  Dropping the angle
//      returns Br everywhere: 79 smooth, plausible, wrong numbers.
//   6. THE POINT CHANNELS ARE THE SAME TWO INPUTS, INTEGRATED.  The chord
//      predictions are recomputed natively from the exported psi map and the
//      exported n_e profile.  A chord sampled from the wrong end, or a
//      Faraday integrand built on B_z instead of B_R, still produces eleven
//      smooth numbers of about the right size.
//   7. THE SPREAD IS CAUSED BY WHAT IT CLAIMS.  With the pressure sigma at
//      zero every member is the same fit and the sigma must be exactly zero;
//      with it raised the spread must appear.  The same seed must reproduce
//      the same ensemble — an error bar that moves when nothing moved cannot
//      be told from one that moved because the input did.
//
// ★Runs on EAST, installed from `machine_desc/` the way an imported machine is: the
// one built-in device has no reference discharge, so there is nothing for a
// reconstruction to fit (see `_device.mjs`).
//
// ★The analysis page carries TWO bars since the profile fit gained a front
// end (`profile` then `reconstruction`), so its export menu items are named
// per bar — `#analysis-iofmt-reconstruction-json` and friends, the same
// convention the model page has always used.  The reconstruction still runs
// from `#analysis-reconstruction-run`.
//
//   node tests/app/validate-recon.mjs [--playwright DIR] [--url BASE]

import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { seedDevice, envWithDeck, missingDeviceMessage } from './_device.mjs';
import { browser } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const iu = process.argv.indexOf('--url');
const BASE = iu > 0 ? process.argv[iu + 1] : 'http://127.0.0.1:8767/app/';

const MEMBERS = 8;
const OUT = mkdtempSync(join(tmpdir(), 'rec-'));
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
  //: ★★`/api/health` 404 是**约定的降级路径**，不是脚本错误：这一页在没有
  //: 网关时照常工作（`assets/mds-source.js` 的开头写着「缺网关是一个功能
  //: 减少的页面，不是一个坏掉的页面」），而这个门跑在一台纯静态服务器上，
  //: 那里本来就没有网关。浏览器仍会为一个 404 响应记一行 console error，
  //: 而把它算成脚本错误，等于要求这一页在没有网关时不去问网关在不在。
  //: 〔2026-08-31：接上单文件查看器的请求面之后才发现——同一份页面对着
  //: `fylite-app`（有 /api）通过，对着静态服务器只差这一行。〕
  if (m.type() === 'error' && !/favicon/.test(m.text()) &&
      !/api\/health/.test(m.location() && m.location().url || ''))
    errs.push('console: ' + m.text().slice(0, 200));
});

const ready = () => page.waitForFunction(
  () => /就绪|Ready/.test(document.getElementById('analysis-status').textContent),
  null, { timeout: 180000 });
const fitted = () => page.waitForFunction(
  () => /重构完成|converged|失败|fail/.test(
    document.getElementById('analysis-status').textContent),
  null, { timeout: 180000 });
const posted = () => page.waitForFunction(
  () => /后验完成|Posterior done|失败|fail/.test(
    document.getElementById('analysis-status').textContent),
  null, { timeout: 600000 });

async function setSlider(id, v) {
  await page.evaluate(([i, x]) => {
    const el = document.getElementById(i);
    el.value = x;
    el.dispatchEvent(new Event('input'));
  }, [id, v]);
}

/** Run one posterior and take the session document out of the page. */
async function runPosterior(sigmaPct, seed) {
  await page.evaluate(() => {
    const c = document.getElementById('reconstruction-neon');
    if (!c.checked) { c.checked = true; c.dispatchEvent(new Event('change')); }
  });
  await setSlider('reconstruction-knoise', sigmaPct);
  await setSlider('reconstruction-seed', seed);
  await setSlider('reconstruction-mcn', MEMBERS);
  await page.waitForFunction(() => !document.getElementById('analysis-reconstruction-run').classList.contains('stop'), null, { timeout: 300000 });
await page.click('#analysis-reconstruction-run');
  await fitted();
  await page.click('#reconstruction-mcrun');
  await posted();
  await page.click('#analysis-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#analysis-iofmt-reconstruction-json')]);
  const f = join(OUT, `p_${sigmaPct}_${seed}.json`);
  await dl.saveAs(f);
  await page.click('#analysis-ioexport');
  const [dm] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#analysis-iofmt-reconstruction-magnetics')]);
  const fm = join(OUT, `m_${sigmaPct}_${seed}.json`);
  await dm.saveAs(fm);
  await page.click('#analysis-ioexport');
  const [dk] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#analysis-iofmt-reconstruction-kinetic')]);
  const fk = join(OUT, `k_${sigmaPct}_${seed}.json`);
  await dk.saveAs(fk);
  const doc = JSON.parse(readFileSync(f, 'utf8'));
  doc.__kinetic = JSON.parse(readFileSync(fk, 'utf8'));
  doc.__magnetics = JSON.parse(readFileSync(fm, 'utf8'));
  return doc;
}

await page.goto(BASE + 'pages/analysis.html?device=east#part-reconstruction',
                { waitUntil: 'networkidle' });
await ready();

const A = await runPosterior(0.03, 7);
const B = await runPosterior(0.03, 7);     // same seed: same ensemble
const Z = await runPosterior(0, 7);        // no sigma: no spread

//: ★T-A6's twin runs (judged in section 八 below, after the native part):
//: eddy groups injected into the twin at deliberately unequal amounts.
//: At the shipped identifiability threshold (10 %) the loops-only twin
//: must REFUSE — 5.7 % of the vessel signature survives the projection,
//: which is the measured fact the entry stands on.  With the reader
//: explicitly lowering the threshold, the fit proceeds and must carry
//: the truth beside its numbers and REPORT the recovery error itself —
//: which is how the page says, in numbers, why T-A6 waits on
//: calibrated probes rather than on more iterations.
const VSL = {};
{
  await page.click('#reconstruction-tab-twin');
  await page.waitForTimeout(400);
  await page.evaluate(() => {
    const c = document.getElementById('reconstruction-vesselfit');
    if (!c.checked) { c.checked = true; c.dispatchEvent(new Event('change')); }
  });
  await setSlider('reconstruction-vinject', 10);
  //: arm 1: the SHIPPED threshold — must refuse, with the cause
  await page.waitForFunction(() => !document.getElementById('analysis-reconstruction-run').classList.contains('stop'), null, { timeout: 300000 });
  await page.click('#analysis-reconstruction-run');
  await fitted();
  await page.click('#analysis-ioexport');
  const [dr] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#analysis-iofmt-reconstruction-json')]);
  const fr = join(OUT, 'vessel_refused.json');
  await dr.saveAs(fr);
  VSL.refusedDoc = JSON.parse(readFileSync(fr, 'utf8'));
  VSL.refusedNote = await page.evaluate(() =>
    (document.getElementById('reconstruction-vessel-note') || {}).textContent || '');
  //: arm 2: the reader's explicit override — numbers, with the truth
  //: and the page's own honesty about how far off they are
  await setSlider('reconstruction-vminsurv', 0.02);
  await page.waitForFunction(() => !document.getElementById('analysis-reconstruction-run').classList.contains('stop'), null, { timeout: 300000 });
  await page.click('#analysis-reconstruction-run');
  await fitted();
  await page.click('#analysis-ioexport');
  const [dv] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#analysis-iofmt-reconstruction-json')]);
  const fv = join(OUT, 'vessel_twin.json');
  await dv.saveAs(fv);
  VSL.twinDoc = JSON.parse(readFileSync(fv, 'utf8'));
  VSL.twinNote = await page.evaluate(() =>
    (document.getElementById('reconstruction-vessel-note') || {}).textContent || '');
}
await br.close();

const res = A['fylite:result'];
const post = res['fylite:posterior'];

// --- the native side: li(3) on the exported psi, and the statistics --------

const PY = `
import ctypes, json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
# ★\`kernel\`, not \`rustlib\`: the two merged when \`fylite/io\` gained a home.
from fylite import kernel as rustlib

doc = json.load(sys.stdin)
res = doc["fylite:result"]
eq = res["equilibrium"]["time_slice"][0]
g2 = eq["profiles_2d"][0]
r = np.asarray(g2["grid"]["dim1"], float)
z = np.asarray(g2["grid"]["dim2"], float)
psi = np.ascontiguousarray(np.asarray(g2["psi"], float))
gq = eq["global_quantities"]
post = res["fylite:posterior"]

lib = rustlib.load()
if lib is None:
    print(json.dumps({"error": "libfylite_kernel.so not loadable"})); sys.exit(0)
f64, u64 = ctypes.c_double, ctypes.c_uint64
P = ctypes.POINTER(ctypes.c_double)
lib.fylite_rs_li3.restype = ctypes.c_int32
lib.fylite_rs_li3.argtypes = [f64, f64, f64, f64, u64, u64, P,
                              f64, f64, f64, f64, P]
out = np.zeros(1)
rc = lib.fylite_rs_li3(
    r[0], z[0], r[1] - r[0], z[1] - z[0], len(r), len(z),
    psi.ctypes.data_as(P), gq["psi_axis"], gq["psi_boundary"],
    ${'${IPFIT}'}, ${'${R0}'}, out.ctypes.data_as(P))

# --- probes: sample the exported psi at each probe and project ------------
probes = json.loads(${'${PROBES}'})
pred = doc.get("__magnetics", {}).get("fylite:probe_b") or []
probe_rel = None
if probes and pred:
    dr, dz = r[1] - r[0], z[1] - z[0]
    grid2 = psi.reshape(len(r), len(z))          # R-major, as the app writes it

    def sample(rr, zz):
        i = min(max((rr - r[0]) / dr, 0), len(r) - 1.000001)
        j = min(max((zz - z[0]) / dz, 0), len(z) - 1.000001)
        i0, j0 = int(i), int(j)
        fi, fj = i - i0, j - j0
        return ((1 - fi) * (1 - fj) * grid2[i0, j0]
                + fi * (1 - fj) * grid2[i0 + 1, j0]
                + (1 - fi) * fj * grid2[i0, j0 + 1]
                + fi * fj * grid2[i0 + 1, j0 + 1])

    h = 0.5 * min(dr, dz)
    got = []
    for p in probes:
        rr, zz = p["r"], p["z"]
        dpr = (sample(rr + h, zz) - sample(rr - h, zz)) / (2 * h)
        dpz = (sample(rr, zz + h) - sample(rr, zz - h)) / (2 * h)
        br = -dpz / (2 * np.pi * rr)
        bz = dpr / (2 * np.pi * rr)
        a = np.radians(p["angle"])
        got.append(br * np.cos(a) + bz * np.sin(a))
    got = np.asarray(got)
    ref = np.asarray(pred[:len(got)], float)
    probe_rel = float(np.abs(ref - got).max() / max(np.abs(got).max(), 1e-30))

# --- POINT: the chord integrals, from the same psi and the same n_e -------
point = json.loads(${'${POINT}'})
pt_doc = doc.get("__magnetics", {}).get("fylite:point")
kin_doc = doc.get("__kinetic", {})
nel_rel = bpol_rel = None
spec = (pt_doc or {}).get("fylite:density_spec") or {}
if point and pt_doc and spec:
    #: rebuild n_e the way the page built it — from the SPEC, not from the
    #: 24-point ladder the kinetic file also carries.  Comparing an analytic
    #: shape against a linear interpolation OF that shape is a check on the
    #: interpolation, and it lands at about a per cent.
    prof = spec.get("profile")

    def ne_of(x):
        if prof:
            m = len(prof)
            t = x * (m - 1)
            k = min(m - 2, max(0, int(t)))
            return prof[k] + (t - k) * (prof[k + 1] - prof[k])
        return spec["ne0"] * max(1.0 - x * x, 0.0) ** spec["peaking"]
    span = gq["psi_boundary"] - gq["psi_axis"]
    nsamp = 401
    got_nel, got_bpol = [], []
    for c in point["chords"]:
        # the same sight line: from the first point, inboard along -R
        th = c["theta"]
        rr = c["r"] - np.cos(th) * np.linspace(0, 2.2, nsamp)
        zz = c["z"] + np.sin(th) * np.linspace(0, 2.2, nsamp)
        ds = 2.2 / (nsamp - 1)
        ne_s = np.zeros(nsamp)
        nb_s = np.zeros(nsamp)
        h = 0.5 * min(dr, dz)
        for i in range(nsamp):
            if not (r[0] < rr[i] < r[-1] and z[0] < zz[i] < z[-1]):
                continue
            x = (sample(rr[i], zz[i]) - gq["psi_axis"]) / span
            if not (0.0 <= x <= 1.0):
                continue
            d = float(ne_of(x))
            dpz = (sample(rr[i], zz[i] + h) - sample(rr[i], zz[i] - h)) / (2 * h)
            br = -dpz / (2 * np.pi * rr[i])
            ne_s[i] = d
            nb_s[i] = d * br
        # Simpson, as the kernel's quadrature does
        def simpson(v, ds):
            n = len(v)
            if n < 3:
                return float(np.trapezoid(v, dx=ds)) if hasattr(np, "trapezoid") else float(np.trapz(v, dx=ds))
            m = n - 1 if (n - 1) % 2 == 0 else n - 2
            tot = v[0] + v[m]
            tot += 4 * v[1:m:2].sum() + 2 * v[2:m:2].sum()
            out = tot * ds / 3
            if m != n - 1:
                out += 0.5 * (v[m] + v[n - 1]) * ds
            return float(out)
        got_nel.append(simpson(ne_s, ds))
        got_bpol.append(simpson(nb_s, ds) / 1e19)
    a_nel = np.asarray(pt_doc["fylite:n_e_line"], float)
    a_bp = np.asarray(pt_doc["fylite:bpolar"], float)
    g_nel = np.asarray(got_nel)
    g_bp = np.asarray(got_bpol)
    nel_rel = float(np.abs(a_nel - g_nel).max() / max(np.abs(g_nel).max(), 1e-30))
    bpol_rel = float(np.abs(a_bp - g_bp).max() / max(np.abs(g_bp).max(), 1e-30))

bs = doc.get("__kinetic", {}).get("fylite:bootstrap")
jbs_native, jbs_rel = None, None
if bs:
    i = bs["fylite:inputs"]
    from fylite import kernel as K
    got = K.redl_bootstrap(
        eps=i["eps"], q_abs=i["q"], ne=i["ne"], te=i["te"], ti=i["ti"],
        ni=i["ni"], zeff=i["zeff"], p_th=i["p_th"], i_psi=i["i_psi"],
        psi_bar=i["psi_bar"], r_maj=i["r_maj"], b0=i["b0"])
    a = np.asarray(bs["fylite:j_bs"], float)
    n_ = np.asarray(got["j_bs"], float)
    scale = max(np.abs(n_).max(), 1e-30)
    jbs_native = float(np.abs(n_).max())
    jbs_rel = float(np.abs(a - n_).max() / scale)

mv = post["fylite:member_values"]
recomputed = {}
for k, v in mv.items():
    a = np.asarray(v, float)
    recomputed[k] = {
        "mean": float(a.mean()),
        "sigma": float(a.std(ddof=1)) if a.size > 1 else 0.0,
        "p16": float(np.percentile(a, 16)),
        "p50": float(np.percentile(a, 50)),
        "p84": float(np.percentile(a, 84)),
        "n": int(a.size),
    }
print(json.dumps({"li3_native": float(out[0]), "rc": int(rc),
                  "recomputed": recomputed,
                  "jbs_native_max": jbs_native, "jbs_rel": jbs_rel,
                  "probe_rel": probe_rel,
                  "nel_rel": nel_rel, "bpol_rel": bpol_rel}))
`;

function pyCheck(doc, r0, ipFit, probes) {
  const chords = ((DEV['fylite:point'] || {}).interferometer || []).map((c) => ({
    r: c.first_point.r, z: c.first_point.z, theta: c['fylite:theta'] || 0 }));
  const src = PY.replace('${R0}', String(r0)).replace('${IPFIT}', String(ipFit))
                .replace('${PROBES}', JSON.stringify(JSON.stringify(probes)))
                .replace('${POINT}',
                         JSON.stringify(JSON.stringify({ chords: chords })));
  return JSON.parse(execFileSync('python3', ['-c', src], {
    input: JSON.stringify(doc), env: envWithDeck('east'),
    encoding: 'utf8', maxBuffer: 1 << 28 }));
}

// R0 is the device's vacuum-field reference, the same one the page hands the
// kernel; it is read from the deck rather than assumed here.
const DEV = JSON.parse(readFileSync(
  ROOT + '/machine_desc/east/fylite_device_east.json', 'utf8'));
const R0 = DEV.tf.r0;

//: li(3) is scored on the SAME Ip the page used — the fitted current, not
//: the deck's nominal — or the two sides would be dividing by different
//: numbers and the comparison would be of bookkeeping, not of the integral
const ipFitted = A['fylite:result']['fylite:ip_fitted'];
let cmp;
const PROBES = (DEV.magnetics.b_field_pol_probe || []).map((p) => ({
  r: p.position[0].r, z: p.position[0].z,
  angle: p['fylite:angle_deg'], w: p['fylite:weight'] }));
try { cmp = pyCheck(A, R0, ipFitted, PROBES); }
catch (e) {
  console.error('原生侧失败：' + String(e.stderr || e.message).slice(0, 400));
  process.exit(1);
}

// --------------------------------------------------------------------------

let bad = 0;
function check(name, ok, detail) {
  console.log(`  ${ok ? '✓' : '✗'} ${name}${detail ? '   ' + detail : ''}`);
  if (!ok) bad += 1;
}
const rel = (a, b) => Math.abs(a - b) / Math.max(Math.abs(b), 1e-30);

console.log('\n=== 一、拟合与它自己的约束 ===');
const ipDeck = DEV['fylite:reference_discharge'].ip;
const ipFit = res['equilibrium'].time_slice[0].global_quantities.ip;
check('Ip 回到装置卷宗的 Ip', rel(ipFit, ipDeck) < 1e-6,
      `${(ipFit / 1e3).toFixed(1)} kA vs ${(ipDeck / 1e3).toFixed(1)} kA`);
const mag = res['magnetics'];
const meas = mag.flux_loop.map((l) => l.flux.data);
const model = mag.flux_loop.map((l) => l['fylite:reconstructed']);
const wts = mag.flux_loop.map((l) => l['fylite:weight']);
let n = 0, s2 = 0, amp = 0;
for (let i = 0; i < meas.length; i++) {
  //: the loops the deck gives zero weight are not part of the fit, so they
  //: are not part of what the fit is judged on either
  if (!wts[i] || !isFinite(meas[i]) || !isFinite(model[i])) continue;
  amp = Math.max(amp, Math.abs(meas[i]));
  s2 += (model[i] - meas[i]) ** 2; n += 1;
}
const rms = Math.sqrt(s2 / Math.max(n, 1));
//: a FLOOR, not a physics tolerance.  This fit has no vessel currents and
//: four free coefficients against 30 loops, so a few per cent of residual is
//: the model, not a defect; what the bar catches is a fit that stopped
//: reading the magnetics at all, which lands at order 100 %.
check('磁通环残差 RMS 在读数幅值的 5% 以内', rms < 0.05 * amp,
      `${(100 * rms / amp).toFixed(2)} %（${rms.toExponential(2)} / ` +
      `${amp.toExponential(2)} Wb/rad，${n} 道）`);

console.log('\n=== 二、li(3) 对原生内核 ===');
check('内核返回 0', cmp.rc === 0, `rc = ${cmp.rc}`);
//: 1e-6 rather than machine epsilon because the psi map travels through the
//: session document at 7 significant figures — the tolerance is the FILE's,
//: not the integral's
check('页面的 li(3) 与原生一致（1e-6）',
      rel(res['fylite:li3'], cmp.li3_native) < 1e-6,
      `${res['fylite:li3'].toFixed(9)} vs ${cmp.li3_native.toFixed(9)}`);

console.log('\n=== 三、后验就是它的成员 ===');
check(`${MEMBERS} 个成员全部收敛`, post['fylite:members_ok'] === MEMBERS,
      `${post['fylite:members_ok']}/${post['fylite:members']}`);
const KEYS = ['q0', 'q95', 'ip', 'p0', 'li3', 'chi2', 'axisR', 'axisZ'];
let worst = 0, worstKey = '';
for (const k of KEYS) {
  const got = post['fylite:statistics'][k], want = cmp.recomputed[k];
  if (!got || !want) { check(`统计量 ${k} 存在`, false); continue; }
  for (const f of ['mean', 'sigma', 'p16', 'p50', 'p84']) {
    const d = rel(got[f], want[f]);
    if (d > worst) { worst = d; worstKey = `${k}.${f}`; }
  }
}
check('mean / sigma / 16-50-84 % 与 numpy 逐项一致（1e-9）', worst < 1e-9,
      `最大相对差 ${worst.toExponential(1)}（${worstKey}）`);

console.log('\n=== 四、自举电流对原生内核 ===');
const kin = A.__kinetic;
const kbs = kin && kin['fylite:bootstrap'];
check('导出的动理学文件带 j_bs 与它的全部输入', !!(kbs && kbs['fylite:inputs']),
      kbs ? `${kbs['fylite:j_bs'].length} 面，模型 ${kbs['fylite:model']}` : '缺');
check('页面的 j_bs 与原生 redl_bootstrap 一致（1e-6）',
      cmp.jbs_rel !== null && cmp.jbs_rel < 1e-6,
      cmp.jbs_rel === null ? '未算' :
      `最大相对差 ${cmp.jbs_rel.toExponential(1)}，峰值 ` +
      `${(cmp.jbs_native_max / 1e3).toFixed(1)} kA/m²`);
//: the two vintages are a COMPARISON and must actually differ — reading the
//: same coefficient set twice would draw two identical curves and look fine
const vt = kin && kin['fylite:neo_vintages'];
let vsep = 0;
if (vt) {
  const a99 = vt['fylite:sauter_1999'], a21 = vt['fylite:redl_2021'];
  for (let i = 0; i < a99.length; i++)
    vsep = Math.max(vsep, Math.abs(a99[i] - a21[i]) /
                          Math.max(Math.abs(a99[i]), 1e-30));
}
check('Sauter-1999 与 Redl-2021 确为两套系数（曲线可分）', vsep > 0.02,
      vt ? `最大相对差 ${(100 * vsep).toFixed(1)} %` : '未解出');

console.log('\n=== 五、探针即解出的场，按角投影 ===');
check('装置卷宗带探针几何', PROBES.length > 0,
      `${PROBES.length} 道，${PROBES.filter((p) => p.w).length} 道带非零权重`);
check('页面的探针预测与原生重算一致（1e-5）',
      cmp.probe_rel !== null && cmp.probe_rel < 1e-5,
      cmp.probe_rel === null ? '未算' : `最大相对差 ${cmp.probe_rel.toExponential(1)}`);
//: the physics check, and a FLOOR: the probes take no part in this fit, so
//: agreeing with the delivered reconstruction at them is corroboration, not
//: a fitted residual.  A projection that dropped the angle lands at order
//: 100 % here, which is what the bar is for.
const refMag = existsSync(ROOT + '/machine_desc/east/fylite_magnetics_east.json')
  ? JSON.parse(readFileSync(ROOT + '/machine_desc/east/fylite_magnetics_east.json', 'utf8'))
  : null;
if (!refMag) {
  console.log('  —  没有 machine_desc/east/fylite_magnetics_east.json，跳过与交付重构的对照');
} else {
  const refb = refMag['fylite:probe_b'];
  const mine = A.__magnetics['fylite:probe_b'];
  let sw = 0, nw = 0, amp = 0;
  for (let i = 0; i < refb.length && i < mine.length; i++) {
    amp = Math.max(amp, Math.abs(refb[i]));
    if (!PROBES[i] || !PROBES[i].w) continue;
    sw += (mine[i] - refb[i]) ** 2; nw += 1;
  }
  const prms = Math.sqrt(sw / Math.max(nw, 1));
    //: ★the SAME probe reading by two independent routes: the Green's rows
  //: applied to the fitted current plus the coils' own field, against the
  //: solved psi map sampled and projected.  They are not expected to match
  //: to machine precision — the sampled one is a finite difference of a
  //: 65x65 map AT THE WALL, where it is coarsest — but a wrong angle
  //: convention or a missing 2pi lands at order 100 %, not at 1 %.
  const viaRows = A.__magnetics['fylite:probe_via_rows'] || [];
  const rowsRel = A.__magnetics['fylite:probe_rows_vs_field'];
  check('格林行与解出的场两条路一致（<2%）',
        viaRows.length > 0 && rowsRel !== undefined && rowsRel < 0.02,
        rowsRel === undefined ? '未算'
          : `最大相对差 ${(100 * rowsRel).toFixed(2)} %（采样场在壁处最粗）`);
  check('加权探针上与交付重构一致（<5% 峰值场）', prms < 0.05 * amp,
        `RMS ${prms.toExponential(2)} T = ${(100 * prms / amp).toFixed(1)} % ` +
        `（${nw} 道，峰值 ${amp.toFixed(3)} T）`);
}

console.log('\n=== 六、POINT 两路即同样两个输入的积分 ===');
const ptDoc = A.__magnetics['fylite:point'];
check('导出的磁量文件带 POINT 两路与弦内长度', !!(ptDoc && ptDoc['fylite:bpolar']),
      ptDoc ? `${ptDoc.z.length} 弦` : '缺');
check('线积分 n_e 与原生重算一致（1e-5）',
      cmp.nel_rel !== null && cmp.nel_rel < 1e-5,
      cmp.nel_rel === null ? '未算' : `最大相对差 ${cmp.nel_rel.toExponential(1)}`);
check('∫n_e B_R dl 与原生重算一致（1e-5）',
      cmp.bpol_rel !== null && cmp.bpol_rel < 1e-5,
      cmp.bpol_rel === null ? '未算' : `最大相对差 ${cmp.bpol_rel.toExponential(1)}`);
//: the physics the panel claims: the chords are symmetric about the midplane,
//: so B_R changes sign across it and the Faraday integral must follow — a
//: model built on B_z instead would come back one-signed
if (ptDoc) {
  const bp = ptDoc['fylite:bpolar'];
  const up = bp.slice(0, 4).every((v) => v > 0);
  const dn = bp.slice(-4).every((v) => v < 0);
  check('法拉第积分在中平面上下变号', up && dn,
        `上四弦 ${bp.slice(0, 2).map((v) => v.toExponential(1)).join(', ')} … ` +
        `下四弦 ${bp.slice(-2).map((v) => v.toExponential(1)).join(', ')}`);
}

console.log('\n=== 七、误差棒确实来自它声称的那个量 ===');
const sA = A['fylite:result']['fylite:posterior']['fylite:statistics'];
const sB = B['fylite:result']['fylite:posterior']['fylite:statistics'];
const sZ = Z['fylite:result']['fylite:posterior']['fylite:statistics'];
let same = true;
for (const k of KEYS) same = same && sA[k].mean === sB[k].mean && sA[k].sigma === sB[k].sigma;
check('同一种子给出同一组后验', same);
//: the claim is that the members are the SAME FIT, which is exact; the
//: sigma of identical values is only zero to rounding (the mean of n equal
//: doubles need not be that double), so the members are what is tested
const mZ = Z['fylite:result']['fylite:posterior']['fylite:member_values'];
const zeroSpread = KEYS.every((k) => Math.max(...mZ[k]) === Math.min(...mZ[k]));
check('压强 σ = 0 时每个成员是同一次拟合（逐位相同）', zeroSpread,
      `q95: max−min = ${(Math.max(...mZ.q95) - Math.min(...mZ.q95)).toExponential(1)}` +
      `，σ = ${sZ.q95.sigma.toExponential(1)}`);
const spread = KEYS.filter((k) => sA[k].sigma > 0);
check('压强 σ > 0 时后验有宽度', spread.length >= 4,
      `${spread.length}/${KEYS.length} 个标量展开：q95 σ = ${sA.q95.sigma.toExponential(2)}`);
console.log('\n=== 八、涡流：孪生注入还原与可辨识门槛（T-A6）===');
//: ★T-A6's twin half, pinned to what is TRUE today.  The ramp-up story
//: re-attributed (coil currents as σ-observations solve every slice),
//: what remains of the entry is the narrowed question: can the eddy
//: GROUP currents themselves be pinned?  Measured here: with flux loops
//: alone 5.7 % of the vessel signature survives the plasma projection —
//: below the shipped 10 % threshold, so the fit REFUSES, with the cause
//: in the file; force it (reader's explicit 2 %) and the recovered
//: groups are ~3x off — which the page itself reports, truth beside
//: fit.  「< 30 %」therefore still waits on the probe channel: the deck
//: carries 0/79 calibrated probes, and the weighted-probe twin fit is a
//: repair of its own (member fit diverges; see reconInputs).  This
//: section pins the refusal, the honesty, and the recorded truth — the
//: three things that must already hold for the entry to close the day
//: the calibrated shot arrives.
{
  const rdoc = VSL.refusedDoc;
  const rc = rdoc['fylite:result']['fylite:vessel_currents'];
  check('默认门槛（10%）：孪生的涡流拟合拒答——文件带原因、不带电流',
        !!rc && !rc['fylite:current'] && !!rc['fylite:error'],
        rc ? String(rc['fylite:error']).slice(0, 40) : 'absent');
  check('拒答的文件仍记下注入的真值——等数据的那半有对照可查',
        !!rc && !!rc['fylite:truth'] && rc['fylite:truth'].length >= 2);
  check('页面说的是「看不见」而不是「没有」',
        /看不出|看不见|不可辨识|cannot|blind|see the vessel/i.test(VSL.refusedNote),
        VSL.refusedNote.slice(0, 80));
}
{
  const vdoc = VSL.twinDoc;
  const vc = vdoc['fylite:result']['fylite:vessel_currents'];
  check('读者压低门槛后：文件里带逐组电流与逐组真值', !!vc && !!vc['fylite:truth']
        && !!vc['fylite:current'],
        vc ? `${vc['fylite:groups'].length} 组` : 'absent');
  if (vc && vc['fylite:truth'] && vc['fylite:current']) {
    const t = vc['fylite:truth'], c = vc['fylite:current'];
    //: the injection is DELIBERATELY unequal — a fit that only got the
    //: total right must fail the per-group comparison
    const distinct = new Set(t.map((v) => v.toFixed(1))).size;
    check('注入的各组量刻意不等（不是同一个数摊三份）', distinct === t.length,
          t.map((v) => (v / 1e3).toFixed(2) + ' kA').join(' / '));
    let num = 0, den = 0;
    for (let i = 0; i < t.length; i++) {
      num += (c[i] - t[i]) * (c[i] - t[i]);
      den += t[i] * t[i];
    }
    const rel = Math.sqrt(num / den);
    check('还原误差是页面自己报出来的数（今天 ~3x——正是等标定探针的理由）',
          /还原到相对误差|recovered to/.test(VSL.twinNote) && isFinite(rel),
          `${(100 * rel).toFixed(1)} %`);
    check('文件里的真值使还原误差可由读者复算', rel > 0,
          `loops-only 基线在册：${(100 * rel).toFixed(0)} %`);
  }
}

check('页面无脚本错误', errs.length === 0, errs[0] || '');

console.log(`\n判定：${bad ? `动理学反演不通过（${bad} 项）`
  : '动理学反演通过（拟合回到自身约束；li(3) 与 j_bs 对原生 1e-6；' +
    '探针按角投影、POINT 两路按内核求积，皆对原生 1e-5，' +
    '且探针与交付重构在加权道上一致；后验可由其成员重算；' +
    '误差棒随压强 σ 出现与消失）'}`);
process.exit(bad ? 1 : 0);
