// Gate for the design scenario's own CRITERIA: the operating-domain
// limits, the flux account, the divertor observables, and the start a
// shape anneal begins from.
//
//   node app/tests/validate-limits.mjs
//
// Needs no browser and no network: it loads `assets/fylite_rs.wasm`
// through the same binding the pages use and checks the answers against
// published numbers and closed-form identities.  What it is FOR: these
// quantities have no second implementation anywhere, so the only thing
// that can catch a wrong wire is an assertion against something outside
// the repo.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const HERE = new URL('.', import.meta.url).pathname;
const SITE = HERE + '../assets/';
globalThis.self = globalThis;
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

const fy = await globalThis.FyLite.fromBytes(
  readFileSync(SITE + 'fylite_rs.wasm'));
let fails = 0;
function ok(name, cond, detail) {
  console.log(`${cond ? 'ok   ' : 'FAIL '} ${name}${detail ? '  ' + detail : ''}`);
  if (!cond) fails++;
}
const rel = (a, b) => Math.abs(a - b) / Math.abs(b);

// --- operating domain ------------------------------------------------------
// ITER's baseline is the anchor because its numbers are published as a set:
// 15 MA, R0 = 6.2 m, a = 2 m, B_t = 5.3 T, and a Greenwald density quoted
// at 1.2e20 m^-3 with beta_N near 1.8.
const L = fy.zerodLimits({ ip: 15e6, r0: 6.2, a: 2.0, kappa: 1.7, bt: 5.3,
                           neBar: 1.0e20, wTh: 320e6, volume: 830 });
ok('greenwald density = the published ITER value',
   rel(L.nGreenwald, 1.19e20) < 0.01, `n_GW = ${L.nGreenwald.toExponential(3)}`);
ok('greenwald fraction is n_bar / n_GW',
   rel(L.fGreenwald, 1.0e20 / L.nGreenwald) < 1e-12,
   `f_GW = ${L.fGreenwald.toFixed(3)}`);
ok('beta_N lands where the ITER baseline is quoted',
   L.betaN > 1.4 && L.betaN < 2.1, `beta_N = ${L.betaN.toFixed(3)}`);
ok('beta_N is the identity beta_t[%] a B / Ip[MA]',
   Math.abs(L.betaN - L.betaT * 100 * 2.0 * 5.3 / 15) < 1e-12);
ok('the Troyon ratio is beta_N / 2.8',
   Math.abs(L.fTroyon - L.betaN / 2.8) < 1e-12,
   `f_Troyon = ${L.fTroyon.toFixed(3)}`);
ok('q_cyl inverts the current it brackets', (() => {
  const MU0 = 4e-7 * Math.PI, q = 3.0;
  const ip = 2 * Math.PI * 4 * 5.3 * (1 + 1.7 * 1.7) / (2 * MU0 * 6.2 * q);
  const got = fy.zerodLimits({ ip: ip, r0: 6.2, a: 2, kappa: 1.7, bt: 5.3,
                               neBar: 1e20, wTh: 1, volume: 1 }).qCyl;
  return Math.abs(got - q) < 1e-9;
})());

// --- flux account ----------------------------------------------------------
const nT = 101, t = [], v = [], ipw = [];
for (let i = 0; i < nT; i++) { t.push(i * 0.1); v.push(1.0); ipw.push(4e5); }
const B = fy.zerodFluxBudget({ t, vLoop: v, ip: ipw, phases: [0, 1, 8, 10],
                               r0: 1.85, a: 0.45, li: 0.9, phiAvail: 0 });
ok('one volt for ten seconds is ten webers',
   Math.abs(B.phiConsumed - 10) < 1e-9, `${B.phiConsumed.toFixed(6)} Wb`);
ok('an undeclared swing is not a duration', B.tSustain === null);
ok('the inductive flux uses L_p I_p',
   Math.abs(B.phiInd - B.lP * 4e5) < 1e-6,
   `L_p = ${(B.lP * 1e6).toFixed(3)} uH`);
const B2 = fy.zerodFluxBudget({ t, vLoop: v, ip: ipw, phases: [0, 1, 8, 10],
                                r0: 1.85, a: 0.45, li: 0.9, phiAvail: 20 });
ok('a declared swing becomes a flat-top duration',
   Math.abs(B2.tSustain - (20 - B2.phiRamp) / 1.0) < 1e-6,
   `${B2.tSustain.toFixed(2)} s`);

// --- the L-H threshold, and the ohmic power the margin is charged against --
//
// ★T-D9 put P_LH and P_heat/P_LH into the ANALYSIS tier's criteria table,
// where the heating power is P_aux + P_ohm + P_alpha rather than a marched
// one.  Two things had to be true for that to be honest, and neither can be
// seen from the page:
//
//   1. the threshold is Martin 2008 as published — the criteria pass reaches
//      it through `zerod_predict`, which is the only door this ABI has to
//      it, and reads back nothing else;
//   2. the ohmic term is Ip^2 Rp with the kernel's own Rp, not V_loop x Ip,
//      which carries the inductive term and is wrong wherever Ip is moving.
//
// The oracle for (1) is the published formula written out here from the
// paper's own coefficients, and the anchor is the value Martin is usually
// quoted at for the ITER baseline (~50 MW).  For (2) it is the closed-form
// split of the loop voltage.
{
  const NR = 41, rho = [];
  for (let i = 0; i < NR; i++) rho.push(i / (NR - 1));
  const R0 = 6.2, A = 2.0, KAP = 1.85, BT = 5.3, IP = 15e6;
  //: ti_over_te, peaking_n, peaking_t, edge_frac, r0, a, kappa, zeff, li, dt
  const par = [1.0, 1.0, 1.5, 0.05, R0, A, KAP, 1.8, 0.9, 0.5];
  const tt = [0, 1, 2], ipw2 = [IP, IP, IP], ne0 = [1.0e20, 1.0e20, 1.0e20];
  const te0 = [10, 10, 10], pAux = [50e6, 50e6, 50e6];
  const ev = fy.zerodEvaluate({ t: tt, ip: ipw2, ne0, te0, pInj: pAux,
                                rho, par });
  const pr = fy.zerodPredict({ t: tt, ip: ipw2, ne0, pAux, rho, par,
                               pred: [0, 1.0, 2.0, BT, 0] });
  const neK = Array.from(ev.ne.slice(NR, 2 * NR));
  const nbar = fy.zerodAverages({ rho, f: neK }).volume;
  //: the paper's own coefficients, written here and nowhere else in this
  //: file: P_thr[MW] = 0.0488 n20^0.717 B^0.803 S^0.941, with the
  //: elliptical surface 4 pi^2 R0 a sqrt((1+kappa^2)/2)
  const S = 4 * Math.PI * Math.PI * R0 * A * Math.sqrt((1 + KAP * KAP) / 2);
  const martin = 1e6 * 0.0488 * Math.pow(nbar / 1e20, 0.717)
                 * Math.pow(BT, 0.803) * Math.pow(S, 0.941);
  ok('the L-H threshold is Martin 2008 as published',
     rel(pr.pLH[1], martin) < 1e-12,
     `${(pr.pLH[1] / 1e6).toFixed(2)} MW against ${(martin / 1e6).toFixed(2)}`);
  ok('and at the ITER baseline it lands where Martin is quoted',
     pr.pLH[1] / 1e6 > 30 && pr.pLH[1] / 1e6 < 90,
     `${(pr.pLH[1] / 1e6).toFixed(1)} MW, n̄_e = ${(nbar / 1e20).toFixed(3)}e20`);
  //: ★non-degenerate: the threshold must MOVE with the field and the
  //: surface it is regressed against, or the row is a constant with a name
  const pr2 = fy.zerodPredict({ t: tt, ip: ipw2, ne0, pAux, rho,
                                par: [1.0, 1.0, 1.5, 0.05, R0, A, 1.2, 1.8,
                                      0.9, 0.5],
                                pred: [0, 1.0, 2.0, BT, 0] });
  ok('and it moves with the surface it is regressed against',
     rel(pr2.pLH[1], pr.pLH[1]) > 0.05,
     `κ 1.85 → 1.2 : ${(pr.pLH[1] / 1e6).toFixed(1)} → ` +
     `${(pr2.pLH[1] / 1e6).toFixed(1)} MW`);

  //: (2) the ohmic split — V_loop = Ip Rp + Lp dIp/dt and the published
  //: external inductance — used to be checked here through the flat
  //: `zerodLoopVoltage` binding.  That export is oracle-only since T-4
  //: (2026-09-05): the same check lives in the kernel repository's
  //: `tests/test_oracle_marshalling.py`, against the same entry.
}

// --- divertor observables --------------------------------------------------
// An analytic circular psi in a box: the crossings of the left wall are
// known in closed form.
const g = { r0: 0, z0: -1, dr: 0.005, dz: 0.005, nr: 401, nz: 401 };
const psi = new Float64Array(g.nr * g.nz);
for (let i = 0; i < g.nr; i++)
  for (let j = 0; j < g.nz; j++) {
    const r = g.r0 + g.dr * i, z = g.z0 + g.dz * j;
    psi[i * g.nz + j] = (r - 1) * (r - 1) + z * z;
  }
const sp = fy.strikePoints({ grid: g, psi: Array.from(psi), psiBnd: 0.25,
                             wallR: [0.8, 1.6, 1.6, 0.8],
                             wallZ: [-0.6, -0.6, 0.6, 0.6] });
const want = Math.sqrt(0.25 - 0.04);
ok('two strike points, where the surface crosses the wall',
   sp.length === 2 && Math.abs(sp[0][0] - 0.8) < 2e-3
   && Math.abs(sp[0][1] + want) < 2e-3 && Math.abs(sp[1][1] - want) < 2e-3,
   JSON.stringify(sp.map(p => p.map(x => +x.toFixed(3)))));
ok('a surface inside the wall lands nowhere',
   fy.strikePoints({ grid: g, psi: Array.from(psi), psiBnd: 0.01,
                     wallR: [0.8, 1.6, 1.6, 0.8],
                     wallZ: [-0.6, -0.6, 0.6, 0.6] }).length === 0);

// --- the start -------------------------------------------------------------
// Eight point coils on a circle, one channel each: the design has to make
// the requested boundary far more isoflux than the plasma alone is.
const nc = 8, cr = [], cz = [];
for (let i = 0; i < nc; i++) {
  const th = 2 * Math.PI * i / nc;
  cr.push(1.85 + 1.2 * Math.cos(th));
  cz.push(1.2 * Math.sin(th));
}
const zc = new Array(nc).fill(0);
const weights = new Array(nc * nc).fill(0);
for (let i = 0; i < nc; i++) weights[i * nc + i] = 1;
const bndR = [], bndZ = [];
for (let i = 0; i < 24; i++) {
  const th = 2 * Math.PI * i / 24;
  bndR.push(1.85 + 0.45 * Math.cos(th));
  bndZ.push(0.74 * Math.sin(th));
}
const fil = fy.fillFilaments({ bndR, bndZ, ip: 4e5, nRing: 4, peaking: 1 });
ok('the filament cloud carries the current it was given',
   Math.abs(fil.a.reduce((s, x) => s + x, 0) - 4e5) < 1e-6);
const D = fy.startCurrents({
  elements: { r: cr, z: cz, w: zc, h: zc, a: zc, a2: zc }, nch: nc,
  weights, bndR, bndZ, filR: fil.r, filZ: fil.z, filA: fil.a,
  useX: false, length: 2 * Math.PI * 1.85 * 0.45, lambda: 1e-3, nu: 1, nv: 1 });
ok('the start returns one current per channel', D.x.length === nc);
ok('and reports what it achieved', D.psiRms >= 0 && D.bX === null,
   `psi_rms = ${D.psiRms.toExponential(2)} Wb`);
const capped = fy.startCurrents({
  elements: { r: cr, z: cz, w: zc, h: zc, a: zc, a2: zc }, nch: nc,
  weights, bndR, bndZ, filR: fil.r, filZ: fil.z, filA: fil.a,
  iMax: new Array(nc).fill(1e4),
  useX: false, length: 1, lambda: 1e-4, nu: 1, nv: 1 });
ok('a bounded start stays inside its bound and says which channels bind',
   capped.x.every(x => Math.abs(x) <= 1e4 + 1e-6) && capped.bind.length > 0,
   `${capped.bind.length} of ${nc} at bound`);

console.log(fails ? `\n${fails} FAILED` : '\nALL GREEN');
process.exit(fails ? 1 : 0);
