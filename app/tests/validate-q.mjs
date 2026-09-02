// Oracle test for app/assets/physics.js qProfile(): feed the machinery a
// reference equilibrium's OWN psi map and OWN F profile, and require it to
// reproduce that equilibrium's OWN q.  If this fails, q does not ship.
//
//   node tests/app/validate-q.mjs
//
// Reads tests/data/synthetic/g_synthetic.geqdsk directly, so it needs no
// network and no build.  Kept beside the publish workflow rather than in
// app/, because app/ ships to the public site and this is a development
// gate.  Last run: <= 0.72 % on ten surfaces from x = 0.1 to 0.95.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { presets } from './_preset.mjs';

// ★The surface tracing comes from the KERNEL, not from a JavaScript copy.
// It used to run `FyPhys.lcfs` + `surfaceIntegrals`, which were kept in
// physics.js FOR this gate — a second implementation whose only consumer was
// the thing meant to check the first.  That is not independence, it is a
// second thing to keep right.  The oracle here was never the tracer anyway:
// it is EFIT's OWN q from the g-file, and that is untouched.

const HERE = new URL('.', import.meta.url).pathname;
const SITE = HERE + '../assets/';
globalThis.self = globalThis;
//: `FyPhys` now lives inside `fylite.js` (physics.js was folded in)
//: ★THE GENERATED FILES LOAD FIRST.  `fylite.js` stopped carrying two
//: hand-kept semantics in 2026-08-26's batches — the ADAS species table
//: (`deck-names.js`, `FyDeck`) and the ABI it expects (`version.js`,
//: `FyVersion.abi`) — and a missing generated file THROWS rather than
//: defaulting, which is the point: a binding that cannot say which ABI
//: it expects would mount any build and blow up on the first changed
//: signature.  ★Every host that loads the binding by hand owes it these
//: two, and these four node harnesses were the hosts that got missed.
for (const f of ['i18n.js', 'lang-zh.js', 'device.js', 'fyodev.js',
                 'version.js', 'deck-names.js', 'fylite.js'])
  vm.runInThisContext(readFileSync(SITE + f, 'utf8'), { filename: f });
//: ★and it needs the KERNEL attached, because the JS copies of sampling and
//: surface tracing are gone — this gate was left calling `FyPhys.sample`
//: with nothing behind it and died on its first line of arithmetic, which
//: is the failure mode `test_app_gate_imports.py` was written about: a gate
//: that cannot start reports nothing, and reports it silently.
globalThis.FyPhys.useKernel(
  await globalThis.FyLite.fromBytes(readFileSync(SITE + 'fylite_rs.wasm')));
// EAST by name, not through FyDevices' resolution: this gate is about the
// bundled EAST equilibrium specifically, and going through the registry
// would make it depend on whatever machine happened to be selected.
const P = globalThis.FyPhys, M = presets(globalThis.FyoDevice).iter;

// --- minimal g-file reader -------------------------------------------------
const txt = readFileSync(HERE + '../../rust/fylite_data/testdata/g_synthetic.geqdsk', 'utf8');
const lines = txt.split('\n');
const head = lines[0];
const nw = parseInt(head.slice(-8, -4)), nh = parseInt(head.slice(-4));
const nums = [];
for (let i = 1; i < lines.length; i++) {
  const l = lines[i];
  for (let c = 0; c + 16 <= l.length; c += 16) {
    const v = parseFloat(l.slice(c, c + 16));
    if (!isNaN(v)) nums.push(v);
  }
  if (nums.length > 20 + 5 * nw + nw * nh + nw) break;
}
let k = 0;
const [rdim, zdim, rcentr, rleft, zmid] = nums.slice(k, k += 5);
const [rmaxis, zmaxis, simag, sibry, bcentr] = nums.slice(k, k += 5);
k += 5; k += 5;                                   // current,simag,.. / xdum..
const fpol = nums.slice(k, k += nw);
const pres = nums.slice(k, k += nw);
const ffprim = nums.slice(k, k += nw);
const pprime = nums.slice(k, k += nw);
const psirz = nums.slice(k, k += nw * nh);
const qpsi = nums.slice(k, k += nw);
console.log(`g-file: nw=${nw} nh=${nh} rleft=${rleft} rdim=${rdim} zmid=${zmid} zdim=${zdim}`);
console.log(`  simag=${simag.toFixed(5)} sibry=${sibry.toFixed(5)} ` +
  `rmaxis=${rmaxis.toFixed(4)} zmaxis=${zmaxis.toFixed(4)} bcentr=${bcentr} rcentr=${rcentr}`);
console.log(`  qpsi[0]=${qpsi[0].toFixed(4)} qpsi[-1]=${qpsi[nw-1].toFixed(4)} ` +
  `fpol[0]=${fpol[0].toFixed(4)} fpol[-1]=${fpol[nw-1].toFixed(4)}`);

// --- into the fylite gauge: psi_full = -2 pi * psirz, axis = max ------------
const grid = P.makeGrid({ nr: nw, nz: nh, rmin: rleft, rmax: rleft + rdim,
                          zmin: zmid - zdim / 2, zmax: zmid + zdim / 2 });
// g-file psirz is (nh rows) x (nw cols) in Fortran write order: psirz[j*nw+i]
// with i the R index; our layout is [i*nz+j].
const psi = new Float64Array(nw * nh);
for (let j = 0; j < nh; j++)
  for (let i = 0; i < nw; i++)
    psi[i * nh + j] = -2 * Math.PI * psirz[j * nw + i];
const psiAxis = -2 * Math.PI * simag, psiBnd = -2 * Math.PI * sibry;
console.log(`  gauge check: psi_axis=${psiAxis.toFixed(4)} > psi_bnd=${psiBnd.toFixed(4)} ? ` +
  (psiAxis > psiBnd ? 'yes' : 'NO — sign wrong'));
const samp = P.sample(grid, psi, rmaxis, zmaxis);
console.log(`  psi(rmaxis,zmaxis)=${samp.toFixed(4)} vs psi_axis=${psiAxis.toFixed(4)} ` +
  `(diff ${(Math.abs(samp - psiAxis) / Math.abs(psiAxis - psiBnd) * 100).toFixed(2)}% of span)`);

// --- q on EFIT's own surfaces, using EFIT's own F --------------------------
// ★The bounding contour is the FILE's own grid box, one cell in, not a
// device limiter.  A g-file's q profile is a property of that file; pairing
// it with some machine's wall makes the gate a test of whether the two
// happen to describe the same tokamak — and when they do not, every ray
// leaves the box and the gate reports q = 0 everywhere, which reads as a
// tracing bug rather than as a mismatched pair.
const lim = {
  r: [grid.r[1], grid.r[nw - 2], grid.r[nw - 2], grid.r[1], grid.r[1]],
  z: [grid.z[1], grid.z[1], grid.z[nh - 2], grid.z[nh - 2], grid.z[1]],
};
const xg = Array.from({ length: nw }, (_, i) => i / (nw - 1));
const fAt = (x) => { const t = x * (nw - 1), i = Math.min(nw - 2, t | 0);
                     return fpol[i] + (t - i) * (fpol[i + 1] - fpol[i]); };
const qAt = (x) => { const t = x * (nw - 1), i = Math.min(nw - 2, t | 0);
                     return qpsi[i] + (t - i) * (qpsi[i + 1] - qpsi[i]); };

// one kernel call per surface: [n, gq, perimeter, dl_over_grad, dv_dpsi, vol]
const wasm = new WebAssembly.Instance(
  new WebAssembly.Module(readFileSync(SITE + 'fylite_rs.wasm')), {});
const E = wasm.exports;
const put = (arr) => {
  const p = E.fylite_rs_alloc(BigInt(arr.length * 8));
  new Float64Array(E.memory.buffer, Number(p), arr.length).set(arr);
  return p;
};
const P_PSI = put(psi), P_LR = put(lim.r), P_LZ = put(lim.z);
const P_RZ = E.fylite_rs_alloc(BigInt(2 * 241 * 8));
const P_INFO = E.fylite_rs_alloc(BigInt(6 * 8));
function trace(level) {
  const n = E.fylite_rs_trace_surface(
    grid.r[0], grid.z[0], grid.dr, grid.dz, BigInt(grid.nr), BigInt(grid.nz),
    P_PSI, level, rmaxis, zmaxis, P_LR, P_LZ, BigInt(lim.r.length),
    BigInt(241), P_RZ, P_INFO);
  if (n < 0) return null;
  const inf = new Float64Array(E.memory.buffer, Number(P_INFO), 6);
  return { n: inf[0], gq: inf[1] };
}

console.log('\n   x     q(本实现)   q(参照)    相对差');
let worst = 0, n = 0;
for (const x of [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]) {
  const lev = psiAxis + (psiBnd - psiAxis) * x;
  const si = trace(lev);
  if (!si) { console.log(`  ${x} — 追踪失败`); continue; }
  const q = fAt(x) * si.gq, qe = qAt(x);
  const rel = (q - qe) / qe;
  worst = Math.max(worst, Math.abs(rel)); n++;
  console.log(`  ${x.toFixed(2)}  ${q.toFixed(4).padStart(9)} ${qe.toFixed(4).padStart(10)}` +
    `  ${(rel * 100).toFixed(2).padStart(8)}%`);
}
console.log(`\n最大相对差 ${(worst * 100).toFixed(2)}% （${n} 个面）`);
console.log(worst < 0.05 ? '判定：q 机器通过（<5%），可上页' : '判定：不通过，勿上页');

// --- beta_p / l_i / W: MEASURED AND REJECTED, kept as a record ------------
// The same machinery can produce these, but on this very field, with this
// field's own pressure profile, the plausible definitions land
//   W  47.5 kJ vs the reference's 37.0 kJ   (+28 %)
//   beta_p 0.351 vs 0.302                   (+16 %)
//   l_i    1.768 vs 1.955                   (-10 %)
// The spread is definitional, not numerical, and nothing here adjudicates
// it — so they are not computed in physics.js and not shown on the page.
// Re-open only with a definition pinned to the reference's own.
