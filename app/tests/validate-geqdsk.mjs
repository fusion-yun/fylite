// Oracle test for app/assets/geqdsk.js: parse the bundled g-file in JS and
// require it to agree, field by field, with fylite's own Python reader; then
// round-trip through the writer and require the numbers to survive.
//
//   node tests/app/validate-geqdsk.mjs
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import vm from 'node:vm';

const HERE = new URL('.', import.meta.url).pathname;
globalThis.self = globalThis;
// geqdsk.js raises its errors through the catalogue, so the runtime and at
// least one language have to be present even in a headless oracle run.
for (const f of ['i18n.js', 'lang-zh.js', 'lang-en.js',
                 'geqdsk.js'])
  vm.runInThisContext(readFileSync(HERE + '../assets/' + f, 'utf8'), { filename: f });
const G = globalThis.FyGeqdsk;

// ★The kernel is attached even in this headless run, and that is the point.
// `geqdsk.js` derives the imported boundary's shape metrics, which are the
// LAST physics still computed in JavaScript — they are there only because
// they run on the page thread, which has no kernel.  Attaching one here
// costs 0.06 ms and ~1 MB (measured, `docs/note/app-provenance.md`), and it
// means the day that repoint happens this gate is already holding the kernel
// path rather than waiting for a browser to prove it.
//: ★THE GENERATED FILES LOAD FIRST.  `fylite.js` stopped carrying two
//: hand-kept semantics in 2026-08-26's batches — the ADAS species table
//: (`deck-names.js`, `FyDeck`) and the ABI it expects (`version.js`,
//: `FyVersion.abi`) — and a missing generated file THROWS rather than
//: defaulting, which is the point: a binding that cannot say which ABI
//: it expects would mount any build and blow up on the first changed
//: signature.  ★Every host that loads the binding by hand owes it these
//: two, and these four node harnesses were the hosts that got missed.
for (const f of ['version.js', 'deck-names.js', 'fylite.js'])
  vm.runInThisContext(readFileSync(HERE + '../assets/' + f, 'utf8'),
                      { filename: f });
const _KERNEL = await globalThis.FyLite.fromBytes(
  readFileSync(HERE + '../assets/fylite_rs.wasm'));
globalThis.FyPhys.useKernel(_KERNEL);

//: ★★2026-09-02：语料从已删的 `tests/data/` 改指数据层自带的那份。
//: 顺带地，这道闸的**含义变了而判据没变**：它比的一直是「JS ↔ fylite 的
//: Python 读入器」，而 Python 那一侧现在是数据层（Rust）的薄壳——于是它成了
//: 三份实现之间缺的那条边（JS ↔ 数据层），一行路径换来的。
const SRC = HERE + '../../rust/fylite_runtime/testdata/g_synthetic.geqdsk';
const py = (path) => JSON.parse(execFileSync('python3', ['-c', `
import sys, json; sys.path.insert(0, '${HERE}../../python')
from fylite.io import geqdsk as G
g = G.read_geqdsk('${path}')
print(json.dumps({k: (list(v) if isinstance(v, (list, tuple)) else v)
                  for k, v in g.items() if k != 'header'}))
`], { encoding: 'utf8', maxBuffer: 1 << 28 }));

const ours = G.parse(readFileSync(SRC, 'utf8'));
const theirs = py(SRC);

let bad = 0;
const cmp = (k, tol = 0) => {
  const a = ours[k], b = theirs[k];
  if (Array.isArray(b) || ArrayBuffer.isView(b)) {
    if (a.length !== b.length) { console.log(`FAIL ${k}: 长度 ${a.length} vs ${b.length}`); bad++; return; }
    let worst = 0, at = -1;
    for (let i = 0; i < b.length; i++) {
      const d = Math.abs(a[i] - b[i]) / Math.max(1e-30, Math.abs(b[i]));
      if (d > worst) { worst = d; at = i; }
    }
    const ok = worst <= tol;
    if (!ok) bad++;
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${k.padEnd(8)} n=${String(b.length).padStart(5)}  最大相对差 ${worst.toExponential(1)}${at >= 0 && !ok ? ' @' + at : ''}`);
  } else {
    const d = Math.abs(a - b) / Math.max(1e-30, Math.abs(b));
    const ok = d <= tol;
    if (!ok) bad++;
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${k.padEnd(8)} ${a} vs ${b}`);
  }
};
console.log('=== 一、JS 解析 vs fylite 自身的 Python 读法 ===');
['nw','nh','rdim','zdim','rcentr','rleft','zmid','rmaxis','zmaxis','simag',
 'sibry','bcentr','current','nbbbs','limitr'].forEach(k => cmp(k));
['fpol','pres','ffprim','pprime','psirz','qpsi','rbbbs','zbbbs','rlim','zlim']
  .forEach(k => cmp(k));

console.log('\n=== 二、写出后再由 Python 读回（往返）===');
// rebuild the app-gauge inputs from the parsed g-file, then write
const psi = G.psiFromGfile(ours);
const txt = G.format({
  grid: { nr: ours.nw, nz: ours.nh, rmin: ours.rleft,
          rmax: ours.rleft + ours.rdim,
          zmin: ours.zmid - ours.zdim / 2, zmax: ours.zmid + ours.zdim / 2 },
  psi, psiAxis: -2 * Math.PI * ours.simag, psiBnd: -2 * Math.PI * ours.sibry,
  axisR: ours.rmaxis, axisZ: ours.zmaxis, ip: ours.current,
  rcentr: ours.rcentr, bcentr: ours.bcentr,
  fpol: ours.fpol, pres: ours.pres,
  pprime: ours.pprime.map(v => -v), ffprime: ours.ffprim.map(v => -v),
  qpsi: ours.qpsi,
  boundary: ours.rbbbs.map((r, i) => [r, ours.zbbbs[i]]),
  limiter: { r: ours.rlim, z: ours.zlim },
  caseName: 'roundtrip',
});
const tmp = join(mkdtempSync(join(tmpdir(), 'gq-')), 'g_roundtrip.00000');
writeFileSync(tmp, txt);
const back = py(tmp);
let worst = 0, worstK = '';
for (const k of ['rdim','zdim','rcentr','rleft','zmid','rmaxis','zmaxis','simag',
                 'sibry','bcentr','current','fpol','pres','ffprim','pprime',
                 'psirz','qpsi','rbbbs','zbbbs','rlim','zlim']) {
  const a = theirs[k], b = back[k];
  const arr = Array.isArray(a);
  const n = arr ? a.length : 1;
  if (arr && b.length !== n) { console.log(`FAIL ${k} 长度`); bad++; continue; }
  for (let i = 0; i < n; i++) {
    const x = arr ? a[i] : a, y = arr ? b[i] : b;
    const d = Math.abs(x - y) / Math.max(1e-30, Math.abs(x));
    if (d > worst) { worst = d; worstK = k + (arr ? '[' + i + ']' : ''); }
  }
}
console.log(`往返最大相对差 ${worst.toExponential(1)}  (最差项 ${worstK})`);
if (worst > 1e-8) { console.log('FAIL 往返超差'); bad++; }
console.log(`\n判定：${bad === 0 ? 'g-file 读写通过' : bad + ' 项未过'}`);
process.exit(bad === 0 ? 0 : 1);
