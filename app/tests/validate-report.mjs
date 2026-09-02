// Gate for the case-report page — ONE RULE, TWO HOSTS.
//
// `python/fylite/engine/casereport.py` derives a presentation specification
// from a record and renders MyST + SVG; `app/assets/casereport.js` is a port
// of the same rules and renders the same record in the DOM.  What this gate
// holds is that the two derive THE SAME SPEC from the same record — panel by
// panel, view by view, series by series — and draw the same number of
// figures.  A rule that drifts on one side (a coordinate found here and not
// there, a one-sample array read as a curve on one host) shows up as a
// mismatch, not as two reports that each look fine.
//
// The record comes from the Python face itself (`fylite cases --report`), so
// the gate needs the kernel: with no data library it SKIPS by name — it does
// not fall back to a hand-made record, which would only prove the hand-made
// record renders.  A supplied spec is checked too: given Python's
// presentation.jsonld, the page draws exactly what Python drew.
//
//     node app/tests/validate-report.mjs [--playwright DIR] [--chrome PATH]
//     (FYLITE_PYTHON="uv run --no-project --with numpy python" when numpy is not on python3)
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { browser } from './_browser.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = resolve(HERE, '../..');
const out = mkdtempSync(join(tmpdir(), 'fylite-report-'));

// 1. the Python face writes the record, the report and its derived spec
//: `$FYLITE_PYTHON` names the interpreter (a command line: `uv run --with numpy python`
//: on a host that keeps numpy out of the system python); plain `python3` otherwise
const PY = (process.env.FYLITE_PYTHON || 'python3').split(/\s+/);
try {
  execFileSync(PY[0], [...PY.slice(1), '-m', 'fylite', 'cases', '--report', 'evolve-default', '--out', out],
    { cwd: ROOT, env: { ...process.env, PYTHONPATH: join(ROOT, 'python') }, stdio: 'pipe' });
} catch (e) {
  const msg = String(e.stderr || e.message);
  if (/data library|KernelError|libfylite|No module named 'numpy'/.test(msg)) {
    console.log('skip: the Python face could not run the case here — ' + msg.trim().split('\n').pop());
    process.exit(0);
  }
  throw e;
}
const pySpec = JSON.parse(readFileSync(join(out, 'presentation.jsonld'), 'utf8'));
const pyFigs = readdirSync(join(out, 'figures')).filter((f) => f.endsWith('.svg')).length;
const report = readFileSync(join(out, 'report.md'), 'utf8');
const pyDirectives = (report.match(/^:::\{figure\}/gm) || []).length;
if (pyDirectives !== pyFigs) throw new Error(`python wrote ${pyFigs} svg but ${pyDirectives} figure directives`);

/** The spec without its JSON-LD context — the part both hosts must agree on. */
const strip = (s) => { const c = JSON.parse(JSON.stringify(s)); delete c['@context']; return c; };
const same = (a, b) => JSON.stringify(strip(a)) === JSON.stringify(strip(b));

// 2. the page, fed the same record through its file door
const b = await browser();
const page = await b.newPage();
page.on('pageerror', (e) => { throw e; });
await page.goto('file://' + join(ROOT, 'app/pages/report.html'));
await page.setInputFiles('#report-files', [join(out, 'record.jsonld'), join(out, 'plan.jsonld')]);
await page.waitForFunction(() => self.FyCaseReport && self.FyCaseReport.lastSpec);
const jsSpec = await page.evaluate(() => self.FyCaseReport.lastSpec);
const jsFigs = await page.evaluate(() => document.querySelectorAll('figure.report-fig svg').length);
const jsRefused = await page.evaluate(() => document.querySelectorAll('.report-refused').length);
if (!same(pySpec, jsSpec)) {
  const a = JSON.stringify(strip(pySpec), null, 1).split('\n'), c = JSON.stringify(strip(jsSpec), null, 1).split('\n');
  const i = a.findIndex((l, k) => l !== c[k]);
  throw new Error(`the two hosts derive different specs; first difference at line ${i}:\n  python: ${a[i]}\n  page:   ${c[i]}`);
}
if (jsFigs !== pyFigs) throw new Error(`python drew ${pyFigs} figures, the page ${jsFigs}`);
const kinds = await page.evaluate(() => [...document.querySelectorAll('figure.report-fig')].map((f) => f.dataset.kind));
if (!kinds.includes('map')) throw new Error('the page drew no poloidal section for a record that carries an outline');
const tables = await page.evaluate(() => [...document.querySelectorAll('table.report-table')].map((t) => t.id));
for (const id of ['rep-parameters', 'rep-ports', 'rep-readings', 'rep-provenance']) {
  if (!tables.includes(id)) throw new Error(`table ${id} missing from the page`);
}
console.log(`derived spec: ${jsFigs} figures on both hosts (${kinds.join(', ')}), ${jsRefused} refused, ${tables.length} tables`);

// 3. a SUPPLIED spec is drawn as given: Python's own file yields the same page
await page.setInputFiles('#report-files', [join(out, 'record.jsonld'), join(out, 'plan.jsonld'), join(out, 'presentation.jsonld')]);
await page.waitForFunction((n) => document.querySelectorAll('figure.report-fig svg').length === n, pyFigs);
const how = await page.evaluate(() => document.getElementById('report-status').textContent);
if (!/随文件提供|supplied/.test(how)) throw new Error('the page did not report the supplied spec: ' + how);

// 3b. A DOCUMENT MAY NOT WRITE THE PAGE.  The plan's prose is rendered as text:
// a note carrying markup must appear as characters, and a script tag in it must
// never become an element.  This page opens files the reader chose — and `?src=`
// lets a link choose for them — so the note is the one field an attacker
// controls end to end.
{
  const evil = JSON.parse(readFileSync(join(out, 'plan.jsonld'), 'utf8'));
  evil.note = { zh: '<img src=x onerror=1><b>bold</b>', en: '<img src=x onerror=1><b>bold</b>' };
  const evilPath = join(out, 'plan-evil.jsonld');
  writeFileSync(evilPath, JSON.stringify(evil));
  await page.setInputFiles('#report-files', [join(out, 'record.jsonld'), evilPath]);
  await page.waitForFunction(() => self.FyCaseReport && self.FyCaseReport.lastSpec);
  const injected = await page.evaluate(() =>
    document.querySelectorAll('#report-host img, #report-host b').length);
  if (injected) throw new Error(`the plan's note created ${injected} element(s) — it must render as text`);
  const shown = await page.evaluate(() =>
    [...document.querySelectorAll('#report-host p.note')].some((p) => p.textContent.includes('<b>bold</b>')));
  if (!shown) throw new Error('the note did not render as text at all');
  console.log('ok: a document-supplied note renders as text, not markup');
}

// 4. the language switch re-renders the chrome without touching the figures
await page.evaluate(() => self.FyI18n.use('en'));
await page.waitForFunction(() => /Table 1/.test(document.getElementById('rep-parameters').textContent));
const again = await page.evaluate(() => document.querySelectorAll('figure.report-fig svg').length);
if (again !== pyFigs) throw new Error('re-rendering in English changed the figure count');
await b.close();
console.log('ok: casereport.js and casereport.py agree on the record');
