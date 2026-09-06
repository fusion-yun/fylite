// The browser's electromagnetic layer must CALL the kernel, not restate it.
//
// ★What this gate pins is not a number — it is a HOST COUNT.  Five quantities
// on this page used to be written out in JavaScript beside the kernel entries
// that already computed them: the BRSP channel map and its two folds, the
// resistance formula, the loop→grid mutual block, and a magnetic probe's
// angle projection.  Every one of them agreed with the kernel, which is
// exactly why a numerical gate alone would never have found them: a second
// implementation is a defect while it is still correct (FYL-SDD-01 DE-COMP-01,
// "同一物理量只有一个实现在此").  What it costs is paid later, on the change
// that moves one host and not the other.
//
// ★T-4 第二十五刀 (2026-09-06): the wrappers this gate used to drive against the
// wasm (`channelWeights` · `channelField` · `elementResponse` ·
// `elementProbeResponse`) left the binding — no page called them; every
// response the pages read comes off the tree door (`code/coilshare` ·
// `code/vstab` · `code/reconstruction`), and the flat entries are oracle-only,
// held to their numpy references in the kernel repository
// (`tests/test_rust_kernels.py` · `tests/test_oracle_marshalling.py`).  What
// is left here is the half a numerical gate cannot do: the grep that keeps
// the transcriptions from coming back.
//
//   node app/tests/validate-em-hosts.mjs

import fs from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';

let bad = 0;
const report = (what, ok, detail) => {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${what.padEnd(34)} ${detail}`);
  if (!ok) bad++;
};

// --- the transcriptions must not come back ----------------------------------
// ★A numerical gate cannot see a SECOND host that agrees.  These do.
const FORBIDDEN = [
  { file: 'app/assets/worker.js', re: /2\s*\*\s*Math\.PI\s*\*\s*\w+\.r\s*\/\s*\(/,
    what: '真空室电阻公式内联' },
  { file: 'app/assets/worker.js', re: /M\.channels\.forEach/,
    what: '通道图在页面里被重走' },
  { file: 'app/assets/worker.js', re: /\.br\[[^\]]*\]\s*\*\s*ca/,
    what: '探针角投影内联' },
  { file: 'app/assets/fylite.js', re: /lr\.fill\(/,
    what: 'loopResponse 逐回路填数组' },
  //: and the flat prototypes themselves: a binding that grew them back would
  //: put the fourteen-argument packing on the page again
  { file: 'app/assets/fylite.js', re: /Fy\.prototype\.(elementResponse|channelField|channelWeights|elementProbeResponse)\b/,
    what: '电磁点响应的扁平原型回来了' },
];
for (const f of FORBIDDEN) {
  const src = fs.readFileSync(`${ROOT}/${f.file}`, 'utf8');
  report(`未复活：${f.what}`, !f.re.test(src), f.file);
}

console.log(bad === 0 ? '\n判定：电磁面单一宿主通过'
                      : `\n判定：${bad} 项未过`);
process.exit(bad === 0 ? 0 : 1);
