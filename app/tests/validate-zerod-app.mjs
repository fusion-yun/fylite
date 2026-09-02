// Oracle test for the 0-D page (FYL-DESIGN-05 O-3): what the browser puts
// in a session file must be what `python/fylite/zerod.py` computes for
// the same configuration.
//
// O-2 already pins Rust against Python inside one process.  This gate closes
// the remaining links of the chain — the waveform construction that the PAGE
// does in JavaScript (phases, trapezoids, heating windows), the marshalling
// through wasm linear memory, and the units the controls carry (kA, 1e19,
// keV, MW).  A unit slip in any of those is invisible to O-2 and would show
// up here as a clean factor.
//
//   node tests/app/validate-zerod-app.mjs [--url http://127.0.0.1:8767/app/]
//
// Needs a server serving the repo and playwright's chromium.

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { browser } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const iu = process.argv.indexOf('--url');
const BASE = iu > 0 ? process.argv[iu + 1] : 'http://127.0.0.1:8767/app/';

// playwright is a developer tool, not a dependency of the shipped app, so it
// is resolved from wherever the operator has it rather than vendored in.
// `--playwright DIR` or $PLAYWRIGHT_PATH points at the install.

// Three configurations that move the units as well as the physics: a
// modest ohmic case, a hot D-T case where the reactivity is large, and one
// whose temperature sits below the parameterisation's floor so the
// refuse-to-extrapolate branch is crossed by the WHOLE chain.
const CASES = [
  { name: 'EAST 型', ip: 400, ne: 4.0, te: 3.0, tite: 0.9, pn: 1.0, pt: 1.5,
    zeff: 1.8, dtf: 0.5, r0: 1.85, a: 0.45, kappa: 1.65, pnbi: 2.0,
    t_rampup_end: 1.0, t_flattop_end: 8.0, t_end: 10.0, t_on: 1.0, t_off: 8.0 },
  { name: '燃烧型', ip: 900, ne: 10.0, te: 20.0, tite: 1.0, pn: 0.5, pt: 2.0,
    zeff: 1.6, dtf: 0.5, r0: 1.9, a: 0.5, kappa: 2.0, pnbi: 30.0,
    t_rampup_end: 2.0, t_flattop_end: 30.0, t_end: 40.0, t_on: 2.0, t_off: 30.0 },
  { name: '冷（反应率出界）', ip: 200, ne: 2.0, te: 0.2, tite: 0.5, pn: 1.0,
    pt: 1.5, zeff: 2.0, dtf: 0.35, r0: 1.8, a: 0.4, kappa: 1.4, pnbi: 0.0,
    t_rampup_end: 0.5, t_flattop_end: 4.0, t_end: 6.0, t_on: 0.0, t_off: 0.0 },
];

const OUT = mkdtempSync(join(tmpdir(), 'zerod-app-'));
const br = await browser();
const ctx = await br.newContext({ locale: 'zh-CN', acceptDownloads: true,
                                  viewport: { width: 1400, height: 1100 } });
//: ★factory defaults — which is now simply what a fresh context gives:
//: no bar applies an initial case any more (2026-09-01).
const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
page.on('console', (m) => {
  if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200));
});

await page.goto(BASE + 'pages/pulse_design.html?device=iter#part-zerod', { waitUntil: 'networkidle' });
// This gate is about the 0-D chain.  The per-slice equilibrium (P2) would
// otherwise overwrite the status line and add a ~0.6 s solve per case for
// nothing, so it is switched off for the duration.
//: readiness first, then press the button — the page no longer computes on
//: load, and neither does a visitor's first glance
await page.waitForFunction(
  () => /就绪|Ready|内核就绪|kernel/.test(
    document.getElementById('design-status').textContent), null, { timeout: 120000 });
await page.waitForFunction(() => !document.getElementById('design-zerod-run').classList.contains('stop'), null, { timeout: 300000 });
  //: ★the run button runs the PAGE — every part of this scenario, in order —
  //: and this gate is about one of them.  A reader reaches one part on its own
  //: by changing one of ITS controls, which is what this does: the values are
  //: all set above, and one `change` sets that part going.
  await page.evaluate(() => document.getElementById('design-ip')
    .dispatchEvent(new Event('change')));
await page.waitForFunction(
  () => /求值完成|Evaluated|平衡已解|solved/.test(
    document.getElementById('design-status').textContent), null, { timeout: 120000 });
await page.uncheck('#design-zerod-eqauto');

const results = [];
for (const c of CASES) {
  await page.evaluate((cfg) => {
    Object.keys(cfg).forEach((id) => {
      if (id === 'name') return;
      const el = document.getElementById('design-zerod-' + id)
                 || document.getElementById('design-' + id);
      el.value = cfg[id];
      el.dispatchEvent(new Event('input'));
    });
  }, c);
  await page.waitForFunction(() => !document.getElementById('design-zerod-run').classList.contains('stop'), null, { timeout: 300000 });
  //: ★the run button runs the PAGE — every part of this scenario, in order —
  //: and this gate is about one of them.  A reader reaches one part on its own
  //: by changing one of ITS controls, which is what this does: the values are
  //: all set above, and one `change` sets that part going.
  await page.evaluate(() => document.getElementById('design-ip')
    .dispatchEvent(new Event('change')));
  await page.waitForFunction(
    () => /求值完成|Evaluated/.test(document.getElementById('design-status').textContent),
    null, { timeout: 120000 });
  await page.click('#design-ioexport');
  const [dl] = await Promise.all([page.waitForEvent('download'),
                                  page.click('#design-iofmt-zerod-json')]);
  const f = join(OUT, `${results.length}.json`);
  await dl.saveAs(f);
  results.push({ name: c.name, doc: JSON.parse(readFileSync(f, 'utf8')) });
}
await br.close();

// The Python side, given the SAME configuration the file records.
const PY = `
import json, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
# ★\`scenario.model\`, not \`fylite.zerod\`: the 0-D objects (\`Scenario\`,
# \`Phases\`, \`Waveform\`) live with the model scenario now -- same objects,
# and this gate kept the old name until nothing ran it.
from fylite.scenario import model as S

docs = json.load(sys.stdin)
out = []
for d in docs:
    c, r = d["cfg"], d["res"]
    scn = S.Scenario(
        phases=S.Phases(0.0, c["t_rampup_end"], c["t_flattop_end"], c["t_end"]),
        ip_flattop=c["ip"] * 1e3, ne_flattop=c["ne"] * 1e19,
        te_flattop=c["te"], ti_over_te=c["tite"],
        peaking_n=c["pn"], peaking_t=c["pt"], r0=c["r0"], a=c["a"],
        kappa=c["kappa"], zeff=c["zeff"], dt_fraction=c["dtf"],
        nbi=S.Waveform(power_w=c["pnbi"] * 1e6, t_on=c["t_on"],
                       t_off=c["t_off"]))
    # ★The page sizes its own grid to the shortest phase, so the reference
    # must be evaluated ON THAT GRID.  Letting scenario.evaluate() build its
    # own would compare two different discretisations and call the
    # difference a disagreement.
    ref = S.evaluate(scn, time=np.asarray(r["fylite:time"], float))

    def cmp(name, got, want):
        got = np.asarray([np.nan if v is None else v for v in got], float)
        want = np.asarray(want, float)
        if got.shape != want.shape:
            return {"field": name, "rel": float("inf"), "note": "长度不同"}
        fa, fb = np.isfinite(got), np.isfinite(want)
        if not np.array_equal(fa, fb):
            return {"field": name, "rel": float("inf"), "note": "NaN 位置不同"}
        g, w = got[fa], want[fb]
        if g.size == 0:
            return {"field": name, "rel": 0.0}
        scale = np.maximum(np.abs(w), np.max(np.abs(w)) * 1e-12 + 1e-300)
        return {"field": name, "rel": float(np.max(np.abs(g - w) / scale))}

    fields = [cmp("t", r["fylite:time"], ref["t"]),
              cmp("ip", r["fylite:ip"], ref["ip"]),
              cmp("p_inj", r["fylite:p_injected"], ref["p_inj"]),
              cmp("v_loop", r["fylite:v_loop"], ref["v_loop"]),
              cmp("p_fus", r["fylite:p_fusion"], ref["p_fus"]),
              cmp("p_alpha", r["fylite:p_alpha"], ref["p_alpha"]),
              cmp("q", r["fylite:q_fusion"], ref["q"])]
    fields.append({"field": "volume",
                   "rel": abs(r["fylite:volume_ellipsoid"] - ref["volume"])
                          / ref["volume"]})
    out.append({"fields": fields, "p_fus_peak": float(np.max(ref["p_fus"]))})
print(json.dumps(out))
`;

const payload = results.map((r) => ({
  cfg: r.doc['fylite:config'], res: r.doc['fylite:result'],
}));
const cmp = JSON.parse(execFileSync('python3', ['-c', PY], {
  input: JSON.stringify(payload), encoding: 'utf8', maxBuffer: 1 << 28 }));

// The session file keeps traces at 7 significant digits on purpose (the size
// of a discharge trace is what makes the file usable at all), so the honest
// band here is the truncation, not machine epsilon.
const TOL = 1e-6;
let bad = errs.length;
if (errs.length) console.log('页面报错：', errs.slice(0, 3).join(' | '));

for (let i = 0; i < cmp.length; i++) {
  const worst = cmp[i].fields.reduce((a, b) => (a.rel > b.rel ? a : b));
  const ok = worst.rel <= TOL;
  console.log(`  ${results[i].name.padEnd(18)} 最大相对差 ` +
              `${worst.rel.toExponential(2)} (${worst.field})` +
              `  P_fus 峰值 ${(cmp[i].p_fus_peak / 1e6).toExponential(2)} MW` +
              `  ${ok ? '✓' : '✗'}`);
  if (!ok) {
    bad += 1;
    cmp[i].fields.filter((f) => f.rel > TOL).forEach((f) =>
      console.log(`      ${f.field}: ${f.rel.toExponential(3)}` +
                  (f.note ? ` — ${f.note}` : '')));
  }
}

console.log(`\n判定：${bad ? `0D 页面与原生不一致（${bad} 项）`
                          : `0D 页面与原生一致（容差 ${TOL.toExponential(0)}，` +
                            `即会话文件有意的 7 位有效截断）`}`);
process.exit(bad ? 1 : 0);
