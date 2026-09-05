// Oracle test for the L0 zero-D layer (FYL-DESIGN-05 O-2 / FYL-DESIGN-08 N-1):
// the shipped `.so` driven DIRECTLY, against an oracle that does not go
// through it.
//
// ★It used to say `python/fylite/zerod.py` here.  That module is gone
// (FYL-DESIGN-08 N-1) and so was this gate's second section: it still
// called `S.dt_reactivity` on `fylite.scenario.model`, which never re-
// exported it, so the gate died with an AttributeError before its first
// assertion and had been dead since the move.  The reactivity is now
// checked against **Bosch & Hale 1992, Table VII** typed into the gate --
// the oracle is the paper -- plus three values off the published curve,
// because a coefficient mistyped from that table would otherwise be
// mistyped identically on both sides of the comparison.
//
// ★What this gate checks CHANGED when the numpy 0-D layer was retired
// (FYL-DESIGN-08 N-1), and saying so is the point.  It used to guard a
// TRANSCRIPTION: `zerod.rs` against an independent numpy implementation, where
// the risk was a quietly altered convention — the volume weight, T_i/T_e, the
// Z_eff default, the edge fraction, which `max()` guard sits where.  There is
// no second implementation now, so that risk is gone by construction and this
// gate would be comparing the kernel with itself — except for one layer that
// is still two things.
//
// ★That layer is the PARAMETER MAP.  Below, the ten scalars are written out by
// hand in the order the ABI documents; the Python face used to build them from a
// `Scenario` dataclass through a `kernel_params()` helper (gone with the door, 2026-09-05).  A field read into the wrong
// slot — peaking_n where peaking_t belongs, li where zeff does — produces a
// perfectly smooth discharge of a different plasma, and nothing else in the
// suite would notice.  That is what these cases now pin, and it is why the
// hand-written vector must NOT be replaced by a call into the package:
// the moment the two sides build the vector the same way, this gate stops
// testing anything.
//
//   node tests/app/validate-zerod.mjs [--lib /path/to/libfylite_kernel.so]
//
// The Rust side is reached through the same .so the Python loader uses, via
// a tiny ctypes shim run in Python — so this gate exercises the shipped
// artefact rather than a `cargo test` build.

import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../..';
const argLib = process.argv.indexOf('--lib');
const LIB = argLib > 0 ? process.argv[argLib + 1]
                       : `${ROOT}/python/fylite/_lib/libfylite_kernel.so`;
if (!existsSync(LIB)) {
  console.error(`没有找到 ${LIB} —— 先跑 rust/build.sh`);
  process.exit(2);
}

// Four cases chosen to move every knob the transcription could have got
// wrong: peaking factors, T_i/T_e, Z_eff, the D-T fraction, an ITER-scale
// geometry, and a case whose temperature leaves the reactivity's validity
// range so the "refuse to extrapolate" branch is exercised end to end.
const CASES = [
  { name: 'EAST 参考', ip: 4.0e5, ne: 4.0e19, te: 3.0, ti_over_te: 0.9,
    pn: 1.0, pt: 1.5, r0: 1.85, a: 0.45, kappa: 1.8, zeff: 1.8, dtf: 0.5,
    nbi: 2.0e6, t_on: 1.0, t_off: 8.0 },
  { name: 'ITER 15 MA', ip: 1.5e7, ne: 1.0e20, te: 20.0, ti_over_te: 1.0,
    pn: 0.5, pt: 2.0, r0: 6.2, a: 2.0, kappa: 1.85, zeff: 1.6, dtf: 0.5,
    nbi: 5.0e7, t_on: 2.0, t_off: 60.0 },
  { name: '尖峰剖面 + 稀释', ip: 8.0e5, ne: 7.0e19, te: 8.0, ti_over_te: 0.75,
    pn: 2.5, pt: 3.0, r0: 1.7, a: 0.5, kappa: 2.0, zeff: 3.0, dtf: 0.35,
    nbi: 1.0e7, t_on: 0.5, t_off: 5.0 },
  { name: '冷等离子体（反应率出界）', ip: 2.0e5, ne: 2.0e19, te: 0.15,
    ti_over_te: 0.9, pn: 1.0, pt: 1.5, r0: 1.85, a: 0.45, kappa: 1.8,
    zeff: 2.0, dtf: 0.5, nbi: 0.0, t_on: 0.0, t_off: 0.0 },
];

const PY = `
import ctypes, json, math, sys
import numpy as np
sys.path.insert(0, ${JSON.stringify(ROOT + '/python')})
# ★\`scenario.model\`, not \`fylite.zerod\`: the 0-D objects live with the
# model scenario now.  Only used for its module-level constants here --
# every number below comes through the ABI directly.
from fylite.scenario import model as S

lib = ctypes.CDLL(${JSON.stringify(LIB)})
lib.fylite_rs_abi_version.restype = ctypes.c_uint32
arr = np.ctypeslib.ndpointer(np.float64, flags="C_CONTIGUOUS")
u64, i32, f64 = ctypes.c_uint64, ctypes.c_int32, ctypes.c_double
lib.fylite_rs_dt_reactivity.restype = f64
lib.fylite_rs_dt_reactivity.argtypes = [f64]
lib.fylite_rs_zerod_volume.restype = f64
lib.fylite_rs_zerod_volume.argtypes = [f64, f64, f64]
lib.fylite_rs_zerod_evaluate.restype = i32
lib.fylite_rs_zerod_evaluate.argtypes = [arr, arr, arr, arr, arr, u64,
                                         arr, u64, arr, arr, arr, arr]

cases = json.loads(sys.argv[1])
out = {"abi": int(lib.fylite_rs_abi_version()), "cases": []}

# ---- the reactivity on its own -------------------------------------
# The oracle here is the PAPER, not this repository: Bosch & Hale 1992,
# Table VII, typed in below and evaluated independently.  There is no
# second implementation inside 'python/' any more (the numpy 0-D layer was
# retired), and 'kernel.dt_reactivity' is a ctypes wrapper around the very
# '.so' under test -- comparing against it would be comparing the kernel
# with itself.
BH_BG, BH_MRC2 = 34.3827, 1124656.0
BH_C = [1.17302e-9, 1.51361e-2, 7.51886e-2, 4.60643e-3,
        1.35000e-2, -1.06750e-4, 1.36600e-5]

def bosch_hale(t):
    """<sigma v> for D-T [m^3/s]; 0 outside the fit's 0.2-100 keV range."""
    if not (0.2 <= t <= 100.0):
        return 0.0
    c = BH_C
    theta = t / (1.0 - (t * (c[1] + t * (c[3] + t * c[5])))
                 / (1.0 + t * (c[2] + t * (c[4] + t * c[6]))))
    xi = (BH_BG * BH_BG / (4.0 * theta)) ** (1.0 / 3.0)
    return (c[0] * theta * math.sqrt(xi / (BH_MRC2 * t ** 3))
            * math.exp(-3.0 * xi) * 1e-6)

grid = np.concatenate([[0.05, 0.1, 0.19], np.geomspace(0.2, 100.0, 60),
                       [100.5, 150.0]])
rust_sv = np.array([lib.fylite_rs_dt_reactivity(float(x)) for x in grid])
py_sv = np.array([bosch_hale(float(x)) for x in grid])
inside = (grid >= 0.2) & (grid <= 100.0)
out["reactivity"] = {
    "n": int(grid.size),
    "max_rel": float(np.max(np.abs(rust_sv - py_sv)
                            / np.where(py_sv > 0, py_sv, 1.0))),
    "bitwise": bool(np.array_equal(rust_sv, py_sv)),
    # non-degeneracy: the curve must actually vary, and the refusal to
    # extrapolate must be a refusal and not an accident of a flat zero
    "span": float(np.max(rust_sv[inside]) / np.min(rust_sv[inside])),
    "outside_zero": bool(np.all(rust_sv[~inside] == 0.0)),
    "inside_positive": bool(np.all(rust_sv[inside] > 0.0)),
    # the anchor: three values off the published curve, to catch a
    # coefficient mistyped the SAME way on both sides of the comparison
    "anchor": [[float(t), float(lib.fylite_rs_dt_reactivity(t))]
               for t in (10.0, 20.0, 64.0)],
}

for c in cases:
    scn = S.Scenario(
        ip_flattop=c["ip"], ne_flattop=c["ne"], te_flattop=c["te"],
        ti_over_te=c["ti_over_te"], peaking_n=c["pn"], peaking_t=c["pt"],
        r0=c["r0"], a=c["a"], kappa=c["kappa"], zeff=c["zeff"],
        dt_fraction=c["dtf"],
        nbi=S.Waveform(power_w=c["nbi"], t_on=c["t_on"], t_off=c["t_off"]))
    ref = S.evaluate(scn)
    t, rho = ref["t"], ref["rho"]
    nt, nr = t.size, rho.size

    # the waveforms the page would build: recomputed through the SAME
    # helpers, because deciding their shape is not the kernel's job
    ph = scn.phases
    ip = ph.waveform(t, scn.ip_flattop, start_value=0.0, end_value=0.0)
    ne0 = ph.waveform(t, scn.ne_flattop, start_value=0.02 * scn.ne_flattop,
                      end_value=0.02 * scn.ne_flattop)
    te0 = ph.waveform(t, scn.te_flattop, start_value=0.01 * scn.te_flattop,
                      end_value=0.01 * scn.te_flattop)
    p_inj = scn.nbi.at(t) + scn.ec.at(t) + scn.lh.at(t)

    par = np.array([scn.ti_over_te, scn.peaking_n, scn.peaking_t, 0.05,
                    scn.r0, scn.a, scn.kappa, scn.zeff, 0.9,
                    scn.dt_fraction], float)
    os_ = np.zeros(4 * nt); op = np.zeros(3 * nt * nr); vol = np.zeros(1)
    rc = lib.fylite_rs_zerod_evaluate(
        np.ascontiguousarray(t, float), np.ascontiguousarray(ip, float),
        np.ascontiguousarray(ne0, float), np.ascontiguousarray(te0, float),
        np.ascontiguousarray(p_inj, float), nt,
        np.ascontiguousarray(rho, float), nr, par, os_, op, vol)

    def cmp(a, b):
        a = np.asarray(a, float).ravel(); b = np.asarray(b, float).ravel()
        fa, fb = np.isfinite(a), np.isfinite(b)
        if not np.array_equal(fa, fb):
            return {"max_rel": float("inf"), "note": "NaN 位置不一致"}
        a, b = a[fa], b[fb]
        if a.size == 0:
            return {"max_rel": 0.0, "bitwise": True}
        scale = np.maximum(np.abs(b), np.max(np.abs(b)) * 1e-300 + 1e-300)
        return {"max_rel": float(np.max(np.abs(a - b) / scale)),
                "bitwise": bool(np.array_equal(a, b))}

    m = nt * nr
    out["cases"].append({
        "name": c["name"], "rc": int(rc), "nt": int(nt), "nr": int(nr),
        "v_loop": cmp(os_[0:nt], ref["v_loop"]),
        "p_fus": cmp(os_[nt:2*nt], ref["p_fus"]),
        "p_alpha": cmp(os_[2*nt:3*nt], ref["p_alpha"]),
        "q": cmp(os_[3*nt:4*nt], ref["q"]),
        "ne": cmp(op[0:m], ref["ne"]),
        "te": cmp(op[m:2*m], ref["te"]),
        "ti": cmp(op[2*m:3*m], ref["ti"]),
        "volume": cmp([vol[0]], [ref["volume"]]),
        "volume_probe": cmp([lib.fylite_rs_zerod_volume(scn.r0, scn.a,
                                                        scn.kappa)],
                            [ref["volume"]]),
        "p_fus_peak": float(np.max(ref["p_fus"])),
    })
print(json.dumps(out))
`;

const res = JSON.parse(execFileSync('python3', ['-c', PY, JSON.stringify(CASES)],
                                    { encoding: 'utf8', maxBuffer: 1 << 28 }));

const TOL = 1e-12;
let bad = 0;

console.log(`库 ABI v${res.abi}\n`);
console.log('=== 一、反应率单函数（含越界分支）===');
{
  const r = res.reactivity;
  const ok = r.max_rel <= TOL;
  console.log(`  逐点 vs Bosch-Hale 1992 表 VII：${r.n} 点  ` +
              `最大相对差 ${r.max_rel.toExponential(2)}` +
              `  ${r.bitwise ? '（逐位相同）' : ''}  ${ok ? '✓' : '✗'}`);
  if (!ok) bad += 1;

  // 非退化：两边同时为零时相对比较恒成立，所以这条曲线必须真的是一条曲线
  const nd = r.span > 1e3 && r.outside_zero && r.inside_positive;
  console.log(`  这条曲线不是一条平的零线  有效区内跨 ${r.span.toExponential(1)} ` +
              `个量级、区外恒零、区内恒正  ${nd ? '✓' : '✗'}`);
  if (!nd) bad += 1;

  // 锚点：两边照同一份系数表算，一个抄错的系数会同时抄错——所以还要
  // 对一次纸面上的值。容差 2 % 的来源是所引数值本身只有三位有效数字。
  const PUB = { 10: 1.13e-22, 20: 4.33e-22, 64: 8.94e-22 };
  for (const [t, got] of r.anchor) {
    const want = PUB[t];
    const rel = Math.abs(got - want) / want;
    const okA = rel <= 0.02;
    console.log(`  T_i = ${t} keV：${got.toExponential(3)} m³/s ` +
                `对已刊出的 ${want.toExponential(3)}（差 ${(rel * 100).toFixed(2)} %）` +
                `  ${okA ? '✓' : '✗'}`);
    if (!okA) bad += 1;
  }
}

console.log('\n=== 二、整条时间轨迹 ===');
const FIELDS = ['v_loop', 'p_fus', 'p_alpha', 'q', 'ne', 'te', 'ti',
                'volume', 'volume_probe'];
for (const c of res.cases) {
  const worst = Math.max(...FIELDS.map((f) => c[f].max_rel));
  const allBits = FIELDS.every((f) => c[f].bitwise);
  const ok = c.rc === 0 && worst <= TOL;
  console.log(`  ${c.name.padEnd(24)} nt=${c.nt} nr=${c.nr}  rc=${c.rc}  ` +
              `最大相对差 ${worst.toExponential(2)}` +
              `${allBits ? '（全项逐位相同）' : ''}  ${ok ? '✓' : '✗'}`);
  if (!ok) {
    bad += 1;
    for (const f of FIELDS)
      if (c[f].max_rel > TOL)
        console.log(`      ${f}: ${c[f].max_rel.toExponential(3)}` +
                    (c[f].note ? ` — ${c[f].note}` : ''));
  }
}

console.log(`\n判定：${bad ? `0D 转写不通过（${bad} 项）`
                          : `0D 转写通过（容差 ${TOL.toExponential(0)}）`}`);
process.exit(bad ? 1 : 0);
