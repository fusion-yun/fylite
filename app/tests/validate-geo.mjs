// Wiring gate for the flux-surface averages: the browser's `geoSurface`
// against `python/fylite/kernel.geo_surface`.
//
// ★This is a WIRING test, and the band says so.  Both sides call the same
// Rust `geo_do` translation, so any disagreement is in the fourteen
// positional arguments — a set that is easy to get wrong and impossible to
// notice: swap `s_kappa` for `s_delta` and a plausible dV/dr comes back for
// a surface nobody asked about.  The Python path builds the same call from
// NAMED parameters, so the two packings are independent.
//
// It is also the test that keeps a SECOND convention out of the repo.  Every
// flux-surface moment a transport layer needs comes from these fourteen
// numbers with one weight (G_theta / B); the moment the browser computes its
// own, this gate stops being able to tell the two apart.
//
//   node tests/app/validate-geo.mjs [--playwright DIR] [--url BASE]

import { execFileSync } from 'node:child_process';
import { browser } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const iu = process.argv.indexOf('--url');
const BASE = iu > 0 ? process.argv[iu + 1] : 'http://127.0.0.1:8767/app/';

// Surfaces chosen so that each argument that could be mis-packed actually
// MOVES something: a circular reference (where the closed forms are known),
// then shaping, shear, elevation and Shafranov shift switched on one at a
// time so a swap cannot hide behind another entry being equal.
const CASES = [
  { name: '圆截面', rmin: 0.5, rmaj: 3.0, q: 2.0 },
  { name: '拉长', rmin: 0.5, rmaj: 3.0, q: 2.0, kappa: 1.7, sKappa: 0.3 },
  { name: '三角度', rmin: 0.5, rmaj: 3.0, q: 2.0, kappa: 1.7, sKappa: 0.3,
    delta: 0.4, sDelta: 0.5 },
  { name: '剪切+移位', rmin: 0.6, rmaj: 3.2, q: 3.0, shear: 1.4,
    kappa: 1.5, sKappa: 0.2, delta: 0.3, sDelta: 0.4, drmaj: -0.15 },
  { name: '抬高+挤压', rmin: 0.35, rmaj: 2.8, q: 1.4, shear: 0.6,
    kappa: 1.2, sKappa: 0.1, zeta: 0.08, sZeta: 0.05,
    zmag: 0.05, dzmag: 0.02 },
];

const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN' });
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));

await page.goto(BASE + 'pages/pulse_design.html?device=iter#part-discharge', { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => /mT|失败|Failed|就绪|Ready/.test(document.getElementById('design-status').textContent),
  null, { timeout: 180000 });

//: the pages let the WORKER own `fylite.js`, so the binding is not on the
//: document.  Loading it here exercises the same file the worker imports.
//: ★absolute, from BASE: the page lives one directory down in `pages/`,
//: and a site-root-relative url resolves against the DOCUMENT — which is how
//: this gate ended up asking for `pages/assets/fylite.js`.
await page.addScriptTag({ url: BASE + 'assets/fylite.js' });

const got = await page.evaluate(async ([cases, wasm]) => {
  const fy = await self.FyLite.load(wasm);
  return cases.map((c) => fy.geoSurface(Object.assign({ nTheta: 501 }, c)));
}, [CASES, BASE + 'assets/fylite_rs.wasm']);
await br.close();

const PY = `
import json, sys
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
# ★\`kernel.geo_surface\`, not \`fylite.geo\`: the module converged at ABI 70
# and this gate kept the old name (see PHYSICS-MIGRATION.md).
from fylite import kernel as K

KEYMAP = {"f": "f", "ffprime": "ffprime", "fsaBp2": "fsa_bp2",
          "fsaBt2": "fsa_bt2", "fsaGradR": "fsa_grad_r",
          "fsaGradR2": "fsa_grad_r2", "gradR0": "grad_r0", "surf": "surf",
          "volume": "volume", "volumePrime": "volume_prime",
          "bt0": "bt0", "bp0": "bp0"}
out = []
for d in json.load(sys.stdin):
    c, b = d["case"], d["browser"]
    ref = K.geo_surface(
        rmin_over_a=c["rmin"], rmaj_over_a=c["rmaj"], q=c["q"],
        shear=c.get("shear", 0.0), kappa=c.get("kappa", 1.0),
        s_kappa=c.get("sKappa", 0.0), delta=c.get("delta", 0.0),
        s_delta=c.get("sDelta", 0.0), zeta=c.get("zeta", 0.0),
        s_zeta=c.get("sZeta", 0.0), drmaj=c.get("drmaj", 0.0),
        zmag=c.get("zmag", 0.0), dzmag=c.get("dzmag", 0.0),
        ntheta=501)
    worst, who = 0.0, ""
    for jk, pk in KEYMAP.items():
        if pk not in ref:
            continue
        a, e = float(b[jk]), float(ref[pk])
        rel = abs(a - e) / max(abs(e), 1e-30)
        if rel > worst:
            worst, who = rel, pk
    out.append({"worst": worst, "who": who,
                "vprime": float(ref["volume_prime"]),
                "gradr": float(ref["fsa_grad_r"])})
print(json.dumps(out))
`;

let cmp;
try {
  cmp = JSON.parse(execFileSync('python3', ['-c', PY], {
    input: JSON.stringify(CASES.map((c, i) => ({ case: c, browser: got[i] }))),
    encoding: 'utf8', maxBuffer: 1 << 26 }));
} catch (e) {
  const s = String(e.stderr || e);
  if (/not available|No module named/.test(s)) {
    console.log('原生 Rust 核未构建，无法作为参照 —— 跳过');
    process.exit(0);
  }
  throw e;
}

// Same Rust, two targets: what is left is the backends' floating-point
// freedom, not arithmetic.  Anything a mis-packed argument could do is many
// orders above this.
const TOL = 1e-9;
let bad = errs.length;
if (errs.length) console.log('页面报错：', errs.slice(0, 3).join(' | '));

for (let i = 0; i < cmp.length; i++) {
  const c = cmp[i], ok = c.worst <= TOL;
  console.log(`  ${CASES[i].name.padEnd(7)} 最大相对差 ${c.worst.toExponential(2)}` +
              (c.who ? ` (${c.who})` : '') +
              `  V' ${c.vprime.toFixed(5)}  <|∇r|> ${c.gradr.toFixed(5)}` +
              `  ${ok ? '✓' : '✗'}`);
  if (!ok) bad += 1;
}

// The circular surface has closed forms, so one case is anchored OUTSIDE
// both implementations: V' = (2 pi)^2 R0 r and <|grad r|> = 1 exactly.
const c0 = cmp[0];
const vExact = 4 * Math.PI * Math.PI * CASES[0].rmaj * CASES[0].rmin;
const vRel = Math.abs(c0.vprime - vExact) / vExact;
const gRel = Math.abs(c0.gradr - 1);
const anchored = vRel <= 1e-6 && gRel <= 1e-6;
console.log(`  圆截面解析锚  V' ${vRel.toExponential(2)}  <|∇r|> ` +
            `${gRel.toExponential(2)}  ${anchored ? '✓' : '✗'}`);
if (!anchored) bad += 1;

// Two surfaces that returned the same numbers would make the comparison
// above vacuous — a packing bug that ignored an argument could pass.
const spread = new Set(cmp.map((c) => c.vprime.toFixed(6)));
if (spread.size < cmp.length) {
  console.log('\n★不同算例给出了相同的 V′ —— 有参数没有真正进入计算。');
  bad += 1;
}

console.log(`\n判定：${bad ? `磁面平均与原生不一致（${bad} 项）`
                          : `磁面平均与原生一致（接线 ${TOL.toExponential(0)}，` +
                            `圆截面另对解析式 1e-6）`}`);
process.exit(bad ? 1 : 0);
