// The main-thread physics face (`FyPhys`) must still reach the kernel it names.
//
// ★★WHY THIS EXISTS (T-4 第十二刀, 2026-09-06).  The worker fixture gates exercise
// every door the WORKER calls; they never load a page's main thread.  第十一刀
// retired `enclosed_volume` on that evidence — and `scenario-pulse_design.js`
// calls `FyPhys.surfaceVolume(poly)` on the main thread, which is
// `KERNEL.enclosedVolume(...)`, which was gone.  No gate went red.  This one does:
// it reads every `KERNEL.<proto>(` a `FyPhys` function makes, requires the
// prototype to exist, and requires every `fylite_rs_*` symbol that prototype
// calls to be a function export of the shipped wasm.
//
// Run: node app/tests/validate-fyphys-surface.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.join(HERE, '..', 'assets');
const js = readFileSync(path.join(SITE, 'fylite.js'), 'utf8');
const wasm = new WebAssembly.Module(readFileSync(path.join(SITE, 'fylite_rs.wasm')));
const exported = new Set(WebAssembly.Module.exports(wasm).filter((e) => e.kind === 'function').map((e) => e.name));

const protos = {};
for (const m of js.matchAll(/\n  Fy\.prototype\.([A-Za-z0-9_]+) = function[\s\S]*?\n  \};/g)) protos[m[1]] = m[0];
const bad = [];
let checked = 0;
for (const m of js.matchAll(/\n  function ([A-Za-z0-9_]+)\([^)]*\) \{([\s\S]*?)\n  \}/g)) {
  const fn = m[1];
  for (const p of new Set(Array.from(m[2].matchAll(/KERNEL\.([A-Za-z0-9_]+)\(/g), (x) => x[1]))) {
    checked++;
    if (!protos[p]) { bad.push(`FyPhys.${fn} calls KERNEL.${p}, and Fy has no such prototype`); continue; }
    for (const sym of new Set(Array.from(protos[p].matchAll(/fylite_rs_[a-z0-9_]+/g), (x) => x[0]))) {
      if (!exported.has(sym)) bad.push(`FyPhys.${fn} -> ${p} -> ${sym}, which the wasm does not export`);
    }
  }
}
assert.equal(bad.length, 0, 'the main-thread physics face is broken:\n  ' + bad.join('\n  '));
console.log(`validate-fyphys-surface: ${checked} FyPhys -> kernel edges resolve on the shipped wasm (${exported.size} exports)`);
