// The browser's electromagnetic layer must CALL the kernel, not restate it.
//
// ★What this gate pins is not a number — it is a HOST COUNT.  Five quantities
// on this page used to be written out in JavaScript beside the kernel entries
// that already computed them: the BRSP channel map and its two folds, the
// resistance formula, the loop→grid mutual block, and a magnetic probe's
// angle projection.  Every one of them agrees with the kernel today, which is
// exactly why a numerical gate alone would never have found them: a second
// implementation is a defect while it is still correct (FYL-SDD-01 DE-COMP-01,
// "同一物理量只有一个实现在此").  What it costs is paid later, on the change
// that moves one host and not the other.
//
// So this file does two things:
//
//   1. drives every replacement wrapper against the wasm the pages actually
//      load, alongside the JS it replaced — transcribed here verbatim, where
//      being a second implementation is the POINT;
//   2. greps the page sources for the transcriptions themselves, so a
//      re-introduced one fails here rather than in six months.
//
// ★The probe angle is the one worth naming: which way a sensor points decides
// the SIGN of what it reads, and a wrong convention does not raise — a fit
// converges on a plasma tilted to match it.
//
//   node app/tests/validate-em-hosts.mjs
//
// No browser and no machine data: the conductors below are synthetic, chosen
// to include a SPLIT-PAIR channel (the case that makes the fold a matrix
// rather than a relabelling, and the one an inline rewrite gets wrong).

import fs from 'node:fs';
import vm from 'node:vm';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';

const ctx = { console, TextDecoder, TextEncoder, WebAssembly, Math, Date };
ctx.self = ctx; ctx.globalThis = ctx;
vm.createContext(ctx);
//: ★THE GENERATED FILES LOAD FIRST.  `fylite.js` stopped carrying two
//: hand-kept semantics in 2026-08-26's batches — the ADAS species table
//: (`deck-names.js`, `FyDeck`) and the ABI it expects (`version.js`,
//: `FyVersion.abi`) — and a missing generated file THROWS rather than
//: defaulting, which is the point: a binding that cannot say which ABI
//: it expects would mount any build and blow up on the first changed
//: signature.  ★Every host that loads the binding by hand owes it these
//: two, and these four node harnesses were the hosts that got missed.
for (const f of ['i18n.js', 'lang-en.js', 'version.js', 'deck-names.js',
                 'fylite.js'])
  vm.runInContext(fs.readFileSync(`${ROOT}/app/assets/${f}`, 'utf8'), ctx);

const WASM = `${ROOT}/app/assets/fylite_rs.wasm`;
if (!fs.existsSync(WASM)) {
  console.error(`没有找到 ${WASM} —— 先跑 rust/build.sh --wasm-check`);
  process.exit(2);
}
const fy = await ctx.FyLite.fromBytes(fs.readFileSync(WASM));

let bad = 0;
const report = (what, ok, detail) => {
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${what.padEnd(34)} ${detail}`);
  if (!ok) bad++;
};

// --- a synthetic machine ---------------------------------------------------
// ★channel 2 drives a PAIR at the 44:204 turn split.  Ten of EAST's twelve
// channels drive one element and would pass any fold; the two that do not are
// the whole reason the map is a matrix.
const els = [];
for (let i = 0; i < 6; i++)
  els.push({ r: 1.4 + 0.22 * i, z: -0.5 + 0.3 * i, w: 0.09, h: 0.13, a1: 0, a2: 90 });
const channels = [[[0, 1]], [[1, 1]], [[2, 0.175], [3, 0.825]], [[4, 1]]];
const NEL = els.length, NCH = channels.length;

const pr = Float64Array.from([1.5, 1.85, 2.1, 2.4, 1.7]);
const pz = Float64Array.from([0.0, 0.35, -0.4, 0.1, 0.8]);
const NP = pr.length;

const maxAbs = (a, b, n) => {
  let m = 0;
  for (let i = 0; i < n; i++) m = Math.max(m, Math.abs(a[i] - b[i]));
  return m;
};

// --- 1. the channel map ----------------------------------------------------
const wMap = fy.channelWeights(channels, NEL);
{
  const ref = new Float64Array(NCH * NEL);
  channels.forEach((combo, c) => combo.forEach(p => { ref[c * NEL + p[0]] += p[1]; }));
  report('channelWeights = 内联稠密化', maxAbs(wMap, ref, ref.length) === 0,
         '逐位');
  //: ★非退化：转置的权重矩阵不是崩溃，是另一台装置。若这张图对称，本闸什么也没测。
  let asym = false;
  for (let c = 0; c < NCH && !asym; c++)
    for (let j = 0; j < NEL; j++)
      if (c < NEL && j < NCH && wMap[c * NEL + j] !== wMap[j * NEL + c]) asym = true;
  report('通道图确非对称（非退化）', asym, '转置可辨');
}

// --- 2. the two folds ------------------------------------------------------
const chan = Float64Array.from([3.1e5, -8.4e4, 1.9e6, 5.5e5]);
//: ★the ampere-turn fold (`channelFold`) left with its export in T-4 第十一刀
//: (2026-09-06): no page called it — the folded field below is the one the pages
//: read, and the kernel repository's `test_oracle_marshalling.py` holds the fold.

const wT = new Float64Array(NEL * NCH);
for (let c = 0; c < NCH; c++)
  for (let j = 0; j < NEL; j++) wT[j * NCH + c] = wMap[c * NEL + j];

const er = fy.elementResponse(els, pr, pz, 3, 3);
{
  const cf = fy.channelField(els, wT, NCH, pr, pz, 3, 3);
  const toChannels = (resp) => {          // the removed worker.js helper
    const out = new Float64Array(NCH * NP);
    channels.forEach((combo, c) => combo.forEach(p => {
      const off = p[0] * NP, w = p[1], to = c * NP;
      for (let i = 0; i < NP; i++) out[to + i] += w * resp[off + i];
    }));
    return out;
  };
  for (const [name, got] of [['psi', cf.psi], ['br', cf.br], ['bz', cf.bz]]) {
    const old = toChannels(er[name]);
    let bit = true, scale = 0;
    for (let p = 0; p < NP; p++)
      for (let c = 0; c < NCH; c++) {
        if (got[p * NCH + c] !== old[c * NP + p]) bit = false;
        scale = Math.max(scale, Math.abs(old[c * NP + p]));
      }
    report(`channelField.${name} = toChannels`, bit && scale > 0, '逐位');
  }
}

// --- 3 · 4. the resistance formula and the loop -> grid mutual block ------
// ★Both wrappers (`resistances` · `mutualFilaments`) left with their exports in
// T-4 第十刀 (2026-09-06): no page called them, so they are oracle-only and not
// in this wasm.  The host-count claim for them is held where the exports now
// live — the kernel repository's `tests/test_rust_kernels.py` against the
// numpy references in `tests/oracles/em.py` — and section 6 below still greps
// this tree for the transcriptions they replaced.

// --- 5. the probe angle projection ----------------------------------------
{
  const ang = Float64Array.from([0, Math.PI / 2, Math.PI / 4, 1.1, -0.7]);
  const got = fy.elementProbeResponse(els, pr, pz, ang, 3, 3);
  let bit = true, signs = new Set();
  for (let i = 0; i < NP; i++) {
    const ca = Math.cos(ang[i]), sa = Math.sin(ang[i]);
    for (let e = 0; e < NEL; e++) {
      const old = er.br[e * NP + i] * ca + er.bz[e * NP + i] * sa;
      if (got[i * NEL + e] !== old) bit = false;
      signs.add(Math.sign(got[i * NEL + e]));
    }
  }
  report('elementProbeResponse = 内联投影', bit, '逐位');
  //: ★非退化：读数必须两种符号都有，否则符号约定错了本闸也照过
  report('探针读数两种符号都出现（非退化）', signs.has(1) && signs.has(-1),
         `${[...signs].join(',')}`);
}

// --- 6. the transcriptions must not come back ------------------------------
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
];
for (const f of FORBIDDEN) {
  const src = fs.readFileSync(`${ROOT}/${f.file}`, 'utf8');
  report(`未复活：${f.what}`, !f.re.test(src), f.file);
}

console.log(bad === 0 ? '\n判定：电磁面单一宿主通过'
                      : `\n判定：${bad} 项未过`);
process.exit(bad === 0 ? 0 : 1);
