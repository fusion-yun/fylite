// Worker that owns the fylite wasm instance.
//
// Every Grad-Shafranov solve is a single blocking call into the binary, so
// it runs here rather than on the UI thread.  The expensive setup — the
// per-coil grid response and the flux-loop response matrix — is built once
// on init and reused by every later command.

//: ★★THE BAR CATALOGUES TOO.  Half the messages this worker sends are
//: REFUSALS — no channel on, no gm2, a reference table that does not span
//: the metric — and `FyI18n.t` answers an unknown key with the key itself.
//: So every worker-side refusal used to reach the page as `e.err.nogm2`
//: rather than as the sentence that says why: the bar catalogues were
//: loaded in the page and nowhere else.
importScripts('i18n.js', 'lang-zh.js', 'lang-en.js',
              'lang-evolve-zh.js', 'lang-evolve-en.js',
              'lang-interp-zh.js', 'lang-interp-en.js',
              //: ★the GENERATED files, before `fylite.js`, which reads
              //: them rather than carrying its own copies any more: the
              //: kernel vocabularies (species table, deck name orders) and
              //: the ABI the binding must see (`version.js`)
              'version.js', 'deck-names.js',
              //: ★and the declared scope ledger (`ENTRY_SCOPE`), which is
              //: how this host decides「这次配置在条目范围内吗」without
              //: keeping a second opinion about it (S-2b)
              //: ★interface BEFORE `fyo.js`, which captures `FyNames` at load
              'fyo-interface.js', 'fyo.js',
              //: ★★算力那条路的两份（2026-09-05 用户裁定「webui 中 fylite_rs /
              //: fylite_kernel_ext wasm 功能由 api 端提供，只静态网页走 wasm」）：
              //: `kernel-abi.js` 是内核仓生成的参数种类表，`kernelapi.js` 是走
              //: `/api/kernel` 的那份导出面。两者都在 `fylite.js` 之前，因为
              //: `FyLite.attach()` 要用它们决定这个宿主该走哪条路。
              'kernel-abi.js', 'kernelapi.js',
              'device.js', 'fyodev.js', 'fylite.js');

// The machine arrives in the `init` message rather than as a global.  A
// Worker cannot read localStorage, so a device the visitor imported would be
// invisible here — and this is the half of the app that does the arithmetic.
var M = null, P = self.FyPhys;
var fy = null, grid = null, coilG = null, loopsM = null;
//: ★built on FIRST USE, not at init: the probe rows are 79 x nr x nz doubles
//: (2.7 MB on this deck) and most runs never fit probes.  A page that pays
//: for them at load pays on every visit for a channel it may not use.
var probesM = null, allM = null;
//: ★declared up here with the other machine caches (filled in far below,
//: beside the two functions that read it) so `init` can drop it.
var coilRowCache = { loops: null, probes: null };
//: the field the last START was designed with — coils plus the filament
//: cloud it was designed against.  The anneal that follows is entitled to
//: begin from it.

/** `{...a, ...b}` — this file is ES5, and `Object.assign` is not in it. */
function assign(a, b) {
  var out = {};
  for (var k in (a || {})) if (a.hasOwnProperty(k)) out[k] = a[k];
  for (var j in (b || {})) if (b.hasOwnProperty(j)) out[j] = b[j];
  return out;
}
var NG = 0, NEL = 0, NCH = 0;

function post(msg, transfer) { self.postMessage(msg, transfer || []); }

// --- channel <-> element ---------------------------------------------------

//: ★★The BRSP channel map, dense, built ONCE per machine — `(nch, nel)`,
//: and `chanW` is its `(nel, nch)` transpose, which is the wire format the
//: folded-field entry takes.  Both are the kernel's: the index direction is
//: the entire content of this map, and the two folds below used to be
//: written out in JS here, each walking `M.channels` its own way.
var chanMap = null, chanW = null;

function buildChannelMap() {
  chanMap = fy.channelWeights(M.channels, NEL);
  chanW = new Float64Array(NEL * NCH);
  for (var c = 0; c < NCH; c++)
    for (var j = 0; j < NEL; j++) chanW[j * NCH + c] = chanMap[c * NEL + j];
}

/** Channel ampere-turns onto the elements they drive (`W^T x`). */
function elementCurrents(chan) {
  return fy.channelFold(chanMap, NCH, NEL, chan);
}

/**
 * Per-channel `(psi, br, bz)` at points, each `(nch, npts)`.
 *
 * ★One kernel call for the response AND the fold — `channelField` does
 * both, and doing the fold here made it a second host for a matrix that has
 * one.  The transpose back into `(nch, npts)` is this page's own cache
 * layout, applied once per call rather than being the shape the arithmetic
 * happens in.
 */
function channelBlocks(els, pr, pz, nu, nv) {
  var f = fy.channelField(els, chanW, NCH, pr, pz, nu, nv);
  var npts = pr.length;
  var flip = function (src) {
    var out = new Float64Array(NCH * npts);
    for (var p = 0; p < npts; p++)
      for (var c = 0; c < NCH; c++) out[c * npts + p] = src[p * NCH + c];
    return out;
  };
  return { psi: flip(f.psi), br: flip(f.br), bz: flip(f.bz) };
}

function psiExtOf(chan) {
  return P.combine(coilG.psiCh, chan, NG);
}

// --- init ------------------------------------------------------------------

function init(machine) {
  if (machine) setMachine(machine);
  if (!M) return post({ type: 'error', where: 'init',
                        message: FyI18n.t('worker.no_machine') });
  var t0 = Date.now();
  return self.FyLite.attach('fylite_rs.wasm').then(function (inst) {
    fy = inst;
    //: the helper modules borrow the kernel rather than each loading
    //: one: one instance, one linear memory, one ABI check
    P.useKernel(fy);
    grid = P.makeGrid(M.grid);
    NG = grid.nr * grid.nz;
    NEL = M.coils.length;
    NCH = M.channels.length;
    buildChannelMap();
    var tG = Date.now();
    //: the per-channel grid response, built once and contracted per solve —
    //: a CACHE, which is why it is held here rather than recomputed: at 4x4
    //: filaments it is the most expensive thing on this page's init path
    coilG = { psiCh: P.gridChannelResponse(fy, M.coils, chanW, NCH, grid,
                                           4, 4) };
    var tL = Date.now();
    //: ★A MACHINE MAY HAVE NO FLUX LOOPS.  Asking for the response of an
    //: empty loop set allocates zero doubles — which the wasm allocator
    //: reports as a failure, because a null pointer is how it says no.
    //: `init` then died with 「wasm allocation of 0 f64 failed」 and the
    //: whole page was dead before its first frame: no kernel, no solve,
    //: three bars disabled.  It only showed up sometimes because the default
    //: machine was whichever preset's fetch finished first.
    //: ★The two descriptors that provoked it (BEST, CFETR) were withdrawn
    //: from this repository on 2026-09-01, so nothing BUNDLED reaches this
    //: branch today — but an IMPORTED device still can, which is why the
    //: guard stays and why `validate-design.mjs` walks the catalogue rather
    //: than naming those two ids.
    loopsM = (M.loops && M.loops.length)
      ? P.loopResponse(fy, grid, M.loops) : null;
    probesM = null; allM = null;
    //: ★the per-channel coil rows are a MACHINE cache like the two above:
    //: dropped here so switching machines cannot fit one deck's coils
    //: against another deck's loops
    coilRowCache = { loops: null, probes: null };
    post({ type: 'ready', abi: fy.abi, sha256: fy.sha256,
           bytes: fy.bytes,
           //: ★the ADAS species menu is ASKED FOR, not written into the
           //: page: an unknown name radiates zero rather than complaining,
           //: so a hard-coded menu that drifted from the kernel's table
           //: would offer species whose line radiation is always zero
           species: fy.adasSpecies(),
           timing: { load: tG - t0, coils: tL - tG, loops: Date.now() - tL },
           // dr/dz travel too: FyPhys.sample() divides by them, and without
           // them every page-side field lookup silently returns NaN
           grid: { r: grid.r, z: grid.z, nr: grid.nr, nz: grid.nz,
                   dr: grid.dr, dz: grid.dz } });
  }).catch(function (e) {
    post({ type: 'error', where: 'init', message: String(e && e.message || e) });
  });
}

// --- forward solve ---------------------------------------------------------

function freeSolve(chan, prof, ip, opts) {
  opts = opts || {};
  //: ★★AND IT SAYS WHETHER IT GOT THERE.  `gs_free_solve` returns whatever
  //: it reached: on the way out of a run that never met its tolerance the
  //: kernel leaves `iterations = max_iter` and `residual` at the last
  //: value, and both were being read by callers as though they described a
  //: converged field.  That is not hypothetical on this page — the droop
  //: trim RESETS its reference and keeps going every time it meets the
  //: tolerance, so a solve that is trimming exits at `max_iter` carrying
  //: 2e-4…1.5e-3 as often as it exits converged.
  //:
  //: ★The test is the RESIDUAL, not the iteration count.  `iterations ==
  //: max_iter` is neither necessary nor sufficient: the trim's `it + 20 <
  //: max_iter` guard lets a genuinely converged solve break on the last
  //: iteration with the count at the cap, and a solve stopped mid-trim has
  //: met the tolerance on some earlier iteration without being at the
  //: fixed point.  So the tolerance the caller asked for travels back with
  //: the answer and the comparison is made against it, once, here.
  var maxIter = opts.maxIter || 600, tol = opts.tol || 1e-9;
  var base = {
    r: grid.r, z: grid.z,
    //: ★the caller may hand over the external flux itself.  The twin needs
    //: it to put currents in the VESSEL — a field the fit is not told about
    //: and must recover — and no other caller passes it, so the default is
    //: still "the coils, and nothing else".
    psiExt: opts.psiExt || psiExtOf(chan),
    //: ★the warm start says WHERE the plasma is meant to be.  Iteration
    //: zero seeds a current disc, and without a hint it seeds it at the
    //: vessel centroid — right for currents that came from a discharge that
    //: ran, wrong for currents that came from a boundary design, whose
    //: field must have a minimum where the plasma belongs.
    psiInit: opts.psiInit || undefined,
    //: ★the anchors hold the current centroid while a design settles.  For
    //: the FIRST solve of a designed start only: the fixed-current Picard
    //: map has no radial restoring force of its own, so a vertical field a
    //: few percent off sends the column outward and it shrinks as it goes
    //: (measured from a designed EAST start: a = 0.45 m at three
    //: iterations, 0.03 m at three hundred).  Left on for every pass they
    //: would hold the shape with virtual currents instead of with the
    //: coils — the answer looking right for the wrong reason, which is why
    //: `fbAmp` is reported beside it.
    zcAnchor: opts.zcAnchor, rcAnchor: opts.rcAnchor,
    ip: ip, limR: M.limiter.r, limZ: M.limiter.z, signAxis: 1,
    relax: opts.relax || 0.3, maxIter: maxIter,
    tol: tol, fbGain: opts.fbGain === undefined ? 8.0 : opts.fbGain,
  };
  //: ★T-D6′ — the profile source is a TIER: the analytic family, or a
  //: tabulated p'/FF' pair used as a shape (`prof.tab`), normalised to Ip
  //: every round so the table's gauge divides out.  The delivered EAST
  //: profiles cross zero at psi_N ≈ 0.82, which no family member can
  //: represent (best fit 11.5 % relative RMS) — this tier is what lets
  //: the shape bar solve the machine's own diverted reference discharge.
  var out = prof.tab
    ? fy.gsFreeSolveTab(assign(base, { tabX: prof.tab.x,
                                       tabPp: prof.tab.pprime,
                                       tabFfp: prof.tab.ffprime }))
    : fy.gsFreeSolve(assign(base, { beta0: prof.beta0, emp: prof.emp,
                                    enp: prof.enp, r0: prof.r0 }));
  out.tol = tol; out.maxIter = maxIter;
  //: ★T-M16: the verdict is the KERNEL's, not `residual <= tol` computed
  //: here — the mask is part of the iteration's state, and a mask that
  //: still swaps cells floors the residual (`settled`: the answer stopped
  //: moving, the mask keeps quantisation-jittering, the tolerance can
  //: never be met — a steady-state reading, distinct from both success
  //: and failure and reported as itself).
  return out;
}

/** What a free solve says about itself, in the shape every consumer posts. */
function freeReport(res) {
  return { converged: !!res.converged, settled: !!res.settled,
           residual: res.residual,
           iterations: res.iterations, maxIter: res.maxIter, tol: res.tol };
}

/**
 * Everything the plots need from a solved field.  With `prof` given, the
 * analytic p'/FF' the solve actually ran on are recovered too: the solver
 * normalizes j_phi = j_c * S(R, x) to Ip, so j_c follows from the converged
 * field, and the two terms of S separate exactly into the pressure and the
 * poloidal-current channel.
 */
/**
 * Marching-squares segments for the levels a poloidal plot draws: `n` inside
 * the boundary and four dashed ones outside it.  One kernel call per level.
 */
function fluxSegments(psiAxis, psiBnd, psi, n) {
  var inner = [], outer = [];
  var lev = function (l) {
    return fy.contour({ r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz,
                        nr: grid.nr, nz: grid.nz, f: psi, level: l });
  };
  for (var k = 1; k <= n; k++)
    inner.push(lev(psiAxis + (psiBnd - psiAxis) * k / (n + 1)));
  for (var q = 1; q <= 4; q++)
    outer.push(lev(psiBnd - (psiAxis - psiBnd) * q * 0.25));
  return { inner: inner, outer: outer, n: n };
}

/**
 * The shape of `n` interior surfaces of a solved field.
 *
 * ★Traced, not prescribed.  The boundary's elongation is not the elongation
 * of the surface halfway in, and a local-stability deck built from the
 * boundary's kappa would be describing a surface the equilibrium never
 * found.  This is the same reason the local-stability page refuses to seed
 * its shape from the device descriptor.
 */
function surfaceShapes(res, count) {
  var out = [];
  for (var i = 1; i <= count; i++) {
    var x = i / (count + 1);
    var lev = res.psiAxis + (res.psiBnd - res.psiAxis) * x;
    try {
      var tr = fy.traceSurface({
        r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz,
        nr: grid.nr, nz: grid.nz, psi: res.psi, level: lev,
        axisR: res.axisR, axisZ: res.axisZ,
        limR: M.limiter.r, limZ: M.limiter.z, nTheta: 121 });
      if (tr.poly.length <= 8) continue;
      var sh = fy.shapeMetrics(tr.poly);
      //: ★the OUTLINE travels with the shape (T-A9).  The flux-surface
      //: averages the current conversion needs are integrals over this
      //: same contour, and tracing a second time to get them would let
      //: the metric and the shape describe two different surfaces.
      if (sh && sh.a > 0) out.push({ x: x, r0: sh.r0, a: sh.a,
                                     kappa: sh.kappa, delta: sh.delta,
                                     poly: tr.poly });
    } catch (e) { /* a surface that will not close is left out, not faked */ }
  }
  return out;
}

/**
 * What says whether a configuration is one the machine can run.
 *
 * ★The design bar could report kappa and delta to three decimals and had
 * nothing to say about the things a scenario is JUDGED by: which topology
 * it is (a diverted plasma is not a shape, it is a boundary that leaves the
 * plasma through a null), how close it passes the wall, how much of the
 * current profile is internal, and how hard the virtual vertical feedback
 * is having to work to keep it there.  All four are kernel entries; none
 * of them had a wire.
 *
 * Every one is wrapped: a criterion that throws must not take the solve
 * down with it — a page that cannot say q95 is worse than one that says
 * nothing about it, but both are better than a lost equilibrium.
 */
/**
 * The n = 0 vertical mode of a solved equilibrium: how fast it grows, and
 * whether it is in the regime feedback can reach at all.
 *
 * ★Why this belongs on a DESIGN screen.  Elongation is the control this
 * page offers most freely — the slider goes to 2.2 on every machine — and
 * elongation is exactly what buys vertical instability.  A design tool that
 * lets you ask for kappa and cannot say what it costs is handing over half
 * an answer.  The chain is entirely the kernel's (rigid filament set,
 * coupling gradient, external stiffness, rank-one plasma elimination); what
 * is here is the wire and the machine's own conductor set.
 *
 * `gamma` is the open-loop growth rate [1/s]; `kIdeal` is the regime
 * boundary — below it the mode is resistive-wall and a controller has time,
 * at or above it no feedback reaches it.  Reported as a RATIO because the
 * absolute stiffnesses mean nothing without each other.
 *
 * Computed on demand, not on every anneal pass: it costs a mutual-inductance
 * assembly over the whole conductor set, which is the most expensive thing
 * on this page after the solve itself.
 */
function verticalOf(res, prof2, chan) {
  if (!prof2 || !M.vessel || !M.vessel.length) return null;
  try {
    var g = { r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz,
              nr: grid.nr, nz: grid.nz };
    var poly = P.boundarySurface(grid, res.psi, res.psiAxis, res.psiBnd,
                                 res.axisR, res.axisZ, M.limiter.r,
                                 M.limiter.z, 181);
    var br = [], bz = [];
    poly.forEach(function (p) { br.push(p[0]); bz.push(p[1]); });
    var pl = fy.plasmaFilaments({
      grid: g, psi: res.psi, psiAxis: res.psiAxis, psiBnd: res.psiBnd,
      pprime: prof2.pprime, ffprim: prof2.ffprime, bndR: br, bndZ: bz,
      ip: res.ip, coarsen: 2 });
    if (!pl.r.length) return null;
    var coils = elementArrays(M.coils), ves = elementArrays(M.vessel);
    var ones = function (n) { var a = []; for (var i = 0; i < n; i++) a.push(1); return a; };
    var gEl = fy.couplingGradient({ pr: pl.r, pz: pl.z, pa: pl.a,
                                    lr: coils.r, lz: coils.z,
                                    lt: ones(coils.r.length) });
    var gVs = fy.couplingGradient({ pr: pl.r, pz: pl.z, pa: pl.a,
                                    lr: ves.r, lz: ves.z,
                                    lt: ones(ves.r.length) });
    //: the channel fold is the SAME map the fields use — a channel drives
    //: one or two elements at measured weights, and taking one element per
    //: channel would be wrong for exactly the split pairs
    var G = new Float64Array(NCH + gVs.length);
    for (var c = 0; c < NCH; c++) {
      var acc = 0;
      for (var j = 0; j < NEL; j++) acc += chanMap[c * NEL + j] * gEl[j];
      G[c] = acc;
    }
    for (var v = 0; v < gVs.length; v++) G[NCH + v] = gVs[v];
    var etaC = M.coil_resistivity_uohm_m === undefined
      ? 1.8e-8 : M.coil_resistivity_uohm_m * 1e-6;
    var etaV = M.vessel_resistivity_uohm_m === undefined
      ? 7.6e-7 : M.vessel_resistivity_uohm_m * 1e-6;
    var cm = fy.channelMatrices({
      coils: coils, vessel: ves, nch: NCH, weights: chanW,
      etaCoil: new Array(NEL).fill(etaC),
      etaVessel: new Array(ves.r.length).fill(etaV), nu: 3, nv: 3 });
    var elCur = elementCurrents(chan);
    var k = fy.verticalStiffness({ pr: pl.r, pz: pl.z, pa: pl.a,
                                   lr: coils.r, lz: coils.z,
                                   lt: ones(coils.r.length), cur: elCur,
                                   step: 1e-3 });
    var plant = fy.verticalPlant({ m: cm.m, r: cm.r, g: G, ip: res.ip, k: k });
    return { gamma: plant.gamma, k: k, kIdeal: plant.kIdeal,
             ratio: plant.kIdeal ? k / plant.kIdeal : null,
             nFilaments: pl.r.length };
  } catch (e) {
    return null;
  }
}

// --- T-D18 / T-D7: what a design may be ASKED for ---------------------------
//
// ★Two widenings of the same request, both of which used to stop at the
// kernel's door.
//
//   T-D18  the field nulls are a SET.  `fylite_rs_start_currents` took
//          exactly one (`xR`/`xZ`/`useX`), so 双零 was listed on the page and
//          DISABLED with that signature named as the reason.  Both sides of
//          the inverse solve — the linear start below and the anneal above —
//          now take as many as they are given, three rows each.
//   T-D7   a design may carry SHAPE-CONTROL rows: 「间隙 = 某值」 on a named
//          ray, and 「打击点落在这段壁上」.  Both become one isoflux row at a
//          point the WALL defines, which is why neither needed a second
//          solver: what was missing was a way to NAME the point.
//
// The rows arrive with the command and are remembered here, because the
// criteria block is assembled by `summarize`, which is reached from three
// commands and knows nothing about any of them.
var shapeCtl = [];

/**
 * The control points a set of shape-control rows names on this machine.
 *
 * A row the wall cannot answer (a ray that misses it) comes back `ok:false`
 * and is not turned into a row — it is REPORTED rather than dropped, the
 * same rule the limits column keeps.
 */
function controlPoints(rows) {
  var wr = M.limiter.r, wz = M.limiter.z;
  return (rows || []).map(function (row) {
    var w = row.w === undefined ? 1 : row.w;
    try {
      if (row.kind === 'strike') {
        var sn = fy.wallSnap({ wallR: wr, wallZ: wz, r: row.r, z: row.z });
        return { ok: true, kind: 'strike', r: sn.r, z: sn.z, w: w,
                 seg: sn.seg, moved: sn.dist, row: row };
      }
      var g = fy.gapRow({ wallR: wr, wallZ: wz, r0: row.r0, z0: row.z0,
                          dr: row.dr, dz: row.dz, gap: row.value });
      return { ok: true, kind: 'gap', r: g.ctlR, z: g.ctlZ, w: w,
               want: row.value, wallR: g.wallR, wallZ: g.wallZ,
               tWall: g.tWall, row: row };
    } catch (e) {
      return { ok: false, kind: row.kind, w: w, row: row, why: e.message };
    }
  });
}

/** Only the rows that became a point — what the solve is actually given. */
function controlUsable(cp) {
  return cp.filter(function (c) { return c.ok; });
}

/**
 * What each shape-control row ACHIEVED, on the boundary that came back.
 *
 * ★A gap is measured on the SAME ray the target was named on, by the same
 * kernel function, so the two halves of a 「目标 vs 实现」 row cannot be two
 * pieces of geometry that nearly agree.  A strike row is judged by the
 * distance from the wall point it asked for to the nearest landing the solve
 * actually made — which is zero when the leg went where it was sent.
 */
function controlAchieved(poly, strike) {
  var wr = M.limiter.r, wz = M.limiter.z;
  var br = [], bz = [];
  (poly || []).forEach(function (p) { br.push(p[0]); bz.push(p[1]); });
  return controlPoints(shapeCtl).map(function (c) {
    var out = { kind: c.kind, ok: c.ok, want: null, got: null,
                at: c.ok ? [c.r, c.z] : null, seg: c.seg === undefined
                  ? null : c.seg, why: c.why || null, label: c.row.label };
    if (!c.ok) return out;
    if (c.kind === 'strike') {
      out.want = 0;
      out.at = [c.r, c.z];
      var best = null;
      (strike || []).forEach(function (p) {
        var d = Math.hypot(p[0] - c.r, p[1] - c.z);
        if (best === null || d < best) best = d;
      });
      out.got = best;
      return out;
    }
    out.want = c.want;
    try {
      var g = fy.gapRow({ bndR: br, bndZ: bz, wallR: wr, wallZ: wz,
                          r0: c.row.r0, z0: c.row.z0, dr: c.row.dr,
                          dz: c.row.dz, gap: c.want });
      out.got = isFinite(g.achieved) ? g.achieved : null;
      out.at = [g.wallR, g.wallZ];
    } catch (e) { out.got = null; }
    return out;
  });
}

/** The field nulls a message asks for, as a set (T-D18). */
function nullSet(src) {
  if (src && src.xpoints && src.xpoints.length) return src.xpoints;
  return src && src.xpoint ? [src.xpoint] : [];
}

function criteria(res, poly, q2) {
  var g = { r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz,
            nr: grid.nr, nz: grid.nz };
  var out = { q95: q2 && isFinite(q2.q95) ? q2.q95 : null,
              q0: q2 && isFinite(q2.q0) ? q2.q0 : null,
              li3: null, strike: [], xpts: [], gap: null,
              //: ★the ratio, not the ampere: |I_fb| means nothing without
              //: the current it is holding up.  A virtual feedback current
              //: comparable to Ip says the equilibrium is standing on a
              //: control loop, not on the coils that were designed.
              fbRatio: res.ip ? Math.abs(res.fbAmp / res.ip) : null };
  try {
    out.li3 = P.li3(grid, res, res.ip, self.FyDevice.tf(M).r0);
  } catch (e) { out.li3 = null; }
  var wr = M.limiter.r, wz = M.limiter.z;
  try {
    out.strike = fy.strikePoints({ grid: g, psi: res.psi,
                                   psiBnd: res.psiBnd, wallR: wr,
                                   wallZ: wz, maxN: 16 });
  } catch (e) { out.strike = []; }
  try {
    out.xpts = fy.xPoints({ grid: g, psi: res.psi, psiAxis: res.psiAxis,
                            psiBnd: res.psiBnd, axisR: res.axisR,
                            axisZ: res.axisZ, maxN: 8 });
  } catch (e) { out.xpts = []; }
  try {
    var br = [], bz = [];
    poly.forEach(function (p) { br.push(p[0]); bz.push(p[1]); });
    var wc = fy.wallClearance({ bndR: br, bndZ: bz, wallR: wr, wallZ: wz });
    out.gap = isFinite(wc.gap) ? wc : null;
  } catch (e) { out.gap = null; }
  //: ★T-D7: the gap and strike rows this design was ASKED for, each with
  //: what it got.  An empty list is a design that asked for none.
  try {
    out.control = controlAchieved(poly, out.strike);
  } catch (e) { out.control = []; }
  return out;
}

function summarize(res, prof, opts) {
  var poly = P.boundarySurface(grid, res.psi, res.psiAxis, res.psiBnd,
                               res.axisR, res.axisZ, M.limiter.r,
                               M.limiter.z, 181);
  //: ★the kernel's, not physics.js's.  The worker HAS a kernel, so it has no
  //: excuse for the JS copy — `fylite_rs_shape_metrics` has been bound since
  //: v34 and kappa is the one quantity in this repo with a documented history
  //: of being got wrong (1.79 against EFIT's 1.389).  What still calls the JS
  //: one is the page thread, which has no kernel; that is a different problem
  //: and it is named where it lives.
  var sm = fy.shapeMetrics(poly);
  var flat = new Float64Array(poly.length * 2);
  poly.forEach(function (p, i) { flat[2 * i] = p[0]; flat[2 * i + 1] = p[1]; });
  var prof2 = null, q2 = null;
  if (prof && prof.tab) {
    //: ★the table tier's truth needs no recovery pass: the solve reports
    //: its own final normalisation `jc`, so the actual profiles are the
    //: table's times jc — and the pressure is the integral of that p'
    //: with the per-radian span, exactly the quadrature analyticTruth's
    //: kernel side applies to the family.
    var tb = prof.tab, nT = tb.x.length;
    var spanPr = (res.psiAxis - res.psiBnd) / (2 * Math.PI);
    var pp2 = new Float64Array(nT), ff2 = new Float64Array(nT),
        pInt = new Float64Array(nT);
    for (var ti = 0; ti < nT; ti++) {
      pp2[ti] = res.jc * tb.pprime[ti];
      ff2[ti] = res.jc * tb.ffprime[ti];
    }
    for (ti = nT - 2; ti >= 0; ti--)
      pInt[ti] = pInt[ti + 1] + 0.5 * (pp2[ti] + pp2[ti + 1])
        * (tb.x[ti + 1] - tb.x[ti]);
    for (ti = 0; ti < nT; ti++) pInt[ti] *= spanPr;
    prof2 = { x: Float64Array.from(tb.x), pprime: pp2, ffprime: ff2,
              p: pInt, jc: res.jc };
    try {
      q2 = P.qProfile(grid, res, prof2, M.limiter.r, M.limiter.z, F_EDGE,
                      { nq: 20, ntheta: 121 });
    } catch (e) { q2 = null; }
  } else if (prof) {
    var t = P.analyticTruth(grid, res, prof, M.limiter.r, M.limiter.z, 201);
    prof2 = { x: t.x, pprime: t.pprime, ffprime: t.ffprime, p: t.p, jc: t.jc };
    // q and F(psi) as well: without them a g-file export would be a
    // g-file with two empty columns
    try {
      q2 = P.qProfile(grid, res, prof2, M.limiter.r, M.limiter.z, F_EDGE,
                      { nq: 20, ntheta: 121 });
    } catch (e) { q2 = null; }
  }
  //: ★the flux contours travel WITH the solve (FYL-DESIGN-07 D-4).
  //: They used to be marching-squared on the page thread, which is the one
  //: place with no kernel — so the page carried its own copy of an algorithm
  //: the kernel already has.  The levels are a pure function of psi_axis /
  //: psi_bnd / the count, so nothing about them needs draw-time knowledge;
  //: computing them here is what lets that copy go.
  var segs = fluxSegments(res.psiAxis, res.psiBnd, res.psi, 14);

  return {
    fluxSegs: segs,
    criteria: criteria(res, poly, q2),
    surfaces: opts && opts.surfaces ? surfaceShapes(res, opts.surfaces) : null,
    profiles: prof2, q: q2,
    psi: res.psi, psiAxis: res.psiAxis, psiBnd: res.psiBnd,
    axisR: res.axisR, axisZ: res.axisZ, ip: res.ip, residual: res.residual,
    //: the solve's own verdict travels with its numbers — a summary that
    //: carried the residual but not whether it met the tolerance leaves
    //: every reader to guess what tolerance was asked for
    iterations: res.iterations, converged: !!res.converged,
    settled: !!res.settled, maskDelta: res.maskDelta,
    tol: res.tol, maxIter: res.maxIter, bndKind: res.bndKind,
    xptR: res.xptR, xptZ: res.xptZ, fbAmp: res.fbAmp,
    lcfs: flat, shape: sm,
  };
}

// --- discharge design ------------------------------------------------------
//
// Iso-flux least squares on the PF channels, annealed: each pass fits the
// coil-current CHANGE that would flatten psi over the target boundary
// (and null the field at the requested X point), applies it under-relaxed,
// and re-solves.  The regularization is annealed from stiff to loose so
// the first passes stay near the starting scenario and the later ones can
// reach the target; the plasma's own response to the current change is
// what the re-solve supplies.

/**
 * The machine as the fyo DEVICE DOCUMENT the kernel's document door reads.
 *
 * ★FYL-DESIGN-16 K-8 / W-1 (2026-09-05): a code that takes whole documents
 * (`code/discharge`, `code/breakdown`, `code/vstab`) reads the coils, the
 * channel map, the box and the limiter off ONE document, never off a list
 * of arrays this page assembled.  `FyoDevice.toFyo` is the page's writer
 * (the same one the device editor exports with); the measured channel map
 * rides beside it in the spelling `device_coils` reads.
 */
function deviceDoc() {
  var doc = self.FyoDevice.toFyo(M);
  doc.pf_channel_elements = M.channels.map(function (ch) {
    return ch.map(function (t) { return { element: t[0], weight: t[1] }; });
  });
  return doc;
}

/**
 * The plan for `code/discharge`, off the page's message.  ★The page's own
 * numbers, unchanged: 4×4 response quadrature, the nulls as a set, one
 * isoflux row per usable control point with its own weight.
 */
function designPlan(msg, o) {
  var t = msg.target;
  var settings = {
    r0: t.r0, z0: t.z0 === undefined ? 0 : t.z0, a: t.a, kappa: t.kappa,
    delta_upper: t.deltaU === undefined ? 0 : t.deltaU,
    delta_lower: t.deltaL === undefined ? 0 : t.deltaL,
    ip: msg.ip, n_points: msg.nPoints || 24, nu: 4,
    x_weight: o.nulls.length ? (msg.xWeight || 1) : 0,
    n_ring: msg.nRing || 4, peaking: msg.peaking === undefined ? 1 : msg.peaking,
    lam: msg.lambda === undefined ? 1e-3 : msg.lambda,
  };
  var discharge = {};
  if (o.nulls.length) {
    discharge['fylite:null_r'] = o.nulls.map(function (p) { return p.r; });
    discharge['fylite:null_z'] = o.nulls.map(function (p) { return p.z; });
  }
  if (o.ctl.length) {
    discharge['fylite:control_r'] = o.ctl.map(function (c) { return c.r; });
    discharge['fylite:control_z'] = o.ctl.map(function (c) { return c.z; });
    discharge['fylite:control_w'] = o.ctl.map(function (c) { return c.w; });
  }
  if (msg.iMax && msg.iMax.length) discharge['fylite:i_max_aturn'] = Array.from(msg.iMax);
  var inputs = { device: deviceDoc() };
  if (o.stage === 'start') {
    settings.stage = 'start';
  } else {
    settings.stage = 'anneal';
    settings.gamma = msg.gamma;
    settings.warm = msg.warm ? 1 : 0;
    var sv = msg.solve || {};
    settings.relax = sv.relax || 0.3;
    settings.max_iter = sv.maxIter || 600;
    settings.tol = sv.tol || 1e-9;
    settings.fb_gain = sv.fbGain === undefined ? 8.0 : sv.fbGain;
    var prof = msg.prof || {};
    if (prof.tab) {
      //: the delivered p'/FF' table rides in on the equilibrium's declared rows
      inputs.equilibrium = { time_slice: [{ profiles_1d: {
        'fylite:psi_norm': Array.from(prof.tab.x),
        dpressure_dpsi: Array.from(prof.tab.pprime),
        f_df_dpsi: Array.from(prof.tab.ffprime) } }] };
    } else {
      settings.beta0 = prof.beta0; settings.emp = prof.emp; settings.enp = prof.enp;
    }
    discharge['fylite:channel_aturns'] = Array.from(msg.chan);
    discharge['fylite:anneal_schedule'] = Array.from(msg.schedule || []);
  }
  if (Object.keys(discharge).length) inputs.discharge = discharge;
  return { settings: settings, inputs: inputs };
}

/** A record's `fields/<name>/data` flattened to a Float64Array (row-major). */
function fieldFlat(rec, name) {
  var d = rec.fields[name].data, out = [];
  (function walk(v) {
    if (Array.isArray(v)) v.forEach(walk); else out.push(v);
  })(d);
  return Float64Array.from(out);
}

function designRun(msg) {
  var target = msg.target, prof = msg.prof;
  //: ★T-D18 / T-D7: the nulls are a SET and the shape-control rows are
  //: another; both go to the kernel as the plan's bound inputs
  var nulls = msg.xWeight > 0 ? nullSet(msg) : [];
  var ctl = controlUsable(controlPoints(msg.control));
  var total = (msg.schedule || []).length;
  post({ type: 'progress', phase: 'design', pass: 0, total: total, err: NaN });
  //: ★★the anneal itself is `case.rs::discharge_case` (FYL-DESIGN-16 K-3,
  //: 2026-09-05): target points, response rows, ridge scale, the designed
  //: start's seed and anchor, the collapse-and-halve rule, best-of — one
  //: recipe for this page and for Python.  What stays here is the DISPLAY:
  //: the criteria, the flux segments, the profiles and the vertical mode of
  //: the answer, read off the field the kernel returns.
  var rec;
  try { rec = fy.complete('code/discharge', designPlan(msg, { stage: 'anneal', nulls: nulls, ctl: ctl })); }
  catch (e) { post({ type: 'error', where: 'design', message: e.message }); return; }
  var F = function (k) { return rec.facts[k].value; };
  var chan = Float64Array.from(rec.fields.aturns.data);
  var res = {
    psi: fieldFlat(rec, 'psi'), psiAxis: F('psi_axis'), psiBnd: F('psi_bnd'),
    axisR: F('axis_r'), axisZ: F('axis_z'), ip: F('ip'), residual: F('residual'),
    iterations: F('iterations'), converged: F('converged') === 1, settled: F('settled') === 1,
    bndKind: F('bnd_kind'), xptR: F('xpt_r'), xptZ: F('xpt_z'), fbAmp: F('fb_amp'), zc: F('zc'),
    maskDelta: null, tol: (msg.solve && msg.solve.tol) || 1e-9,
    maxIter: (msg.solve && msg.solve.maxIter) || 600,
  };
  var sum = summarize(res, prof);
  //: the vertical mode of the answer that is being returned, not of every
  //: pass along the way — it costs a mutual assembly over the whole
  //: conductor set
  if (sum.criteria) sum.criteria.vertical = verticalOf(res, sum.profiles, chan);
  var hp = rec.fields.history_pass.data, ha = rec.fields.history_alpha.data,
      he = rec.fields.history_err.data, hr = rec.fields.history_residual.data,
      hh = rec.fields.history_halvings.data, hs = rec.fields.history_shape.data;
  var notes = rec.notes || [], history = [];
  for (var i = 0; i < hp.length; i++) {
    var pass = hp[i];
    if (!isFinite(he[i])) {
      //: the pass that stopped the search: recorded with its reason
      var why = notes.filter(function (n) { return n.indexOf('pass ' + pass + ':') === 0; })[0];
      history.push({ pass: pass, alpha: ha[i], err: null, error: why || 'the pass failed' });
      break;
    }
    var entry = { pass: pass, alpha: i === 0 ? null : ha[i], err: he[i],
                  shape: { r0: hs[i][0], z0: hs[i][1], a: hs[i][2], kappa: hs[i][3],
                           deltaU: hs[i][4], deltaL: hs[i][5] },
                  residual: hr[i] };
    if (hh[i]) entry.stepHalvings = hh[i];
    history.push(entry);
    post({ type: 'progress', phase: 'design', pass: pass, total: total, err: he[i] });
  }
  post({ type: 'design', chan: chan, result: sum, pass: F('pass'),
         history: history, targetBoundary: fieldFlat(rec, 'target_boundary') },
       [sum.psi.buffer, sum.lcfs.buffer]);
}

// --- the START, and the pulse ----------------------------------------------

/**
 * The channel currents a shape anneal is entitled to begin from.
 *
 * ★Why this command exists.  The anneal above is a LOCAL method: it
 * linearises the boundary's response about the equilibrium it is standing
 * on.  Started from zero currents on a machine without a reference discharge
 * it lands 0.36 – 0.77 m from the target and reports the outcome in the same
 * words it uses for a converged design (measured across the four bundled
 * devices).  So the start is DESIGNED — by the kernel, `code/discharge` with
 * `stage: start`: one linear isoflux solve for the currents that make the
 * requested boundary a flux contour of coils + a filament cloud.
 *
 * What comes back is NOT an equilibrium — force balance is nowhere in it —
 * and the numbers beside it (`psiRms`, `bX`) say how well the request could
 * be met at all, before any equilibrium is paid for.
 */
function startRun(msg) {
  var nulls = msg.xWeight > 0 ? nullSet(msg) : [];
  var cpts = controlPoints(msg.control), ctl = controlUsable(cpts);
  var rec;
  try { rec = fy.complete('code/discharge', designPlan(msg, { stage: 'start', nulls: nulls, ctl: ctl })); }
  catch (e) { post({ type: 'error', where: 'start', message: e.message }); return; }
  var F = function (k) { return rec.facts[k].value; };
  var flags = rec.fields.start_at_bound.data, bind = [];
  for (var c = 0; c < flags.length; c++) if (flags[c] === 1) bind.push(c);
  var bxe = rec.fields.start_b_x_each.data, pxe = rec.fields.start_psi_x_each.data;
  //: ★the anneal that follows re-seeds itself from these currents (`warm`):
  //: the field this design was made with is the kernel's to rebuild, not a
  //: buffer this worker keeps between two commands
  var bX = F('start_b_x');
  post({ type: 'start', chan: Float64Array.from(rec.fields.aturns.data),
         psiRms: F('start_psi_rms'), bX: isFinite(bX) && bX >= 0 ? bX : null,
         psiXOffset: F('start_psi_x_offset'), bind: bind,
         //: per null and per control row, so a start that met one null and
         //: missed the other can say which — before an anneal is paid for
         nulls: nulls.map(function (p, k) { return { r: p.r, z: p.z, b: bxe[k], dpsi: pxe[k] }; }),
         ctlDpsi: Array.from(rec.fields.start_ctl_dpsi.data),
         ctlRows: cpts.map(function (c) {
           return { ok: c.ok, kind: c.kind, r: c.r, z: c.z, seg: c.seg,
                    want: c.want, label: c.row.label, why: c.why || null };
         }),
         targetBoundary: fieldFlat(rec, 'target_boundary') });
}

/**
 * The six element arrays the kernel takes, out of a device's element list.
 *
 * ★The two tilt defaults are the DECK's, not zero: `a2` defaults to 90
 * degrees, which is what `channelField` above already assumes.  A second
 * spelling with a 0 default here would silently turn every untilted
 * rectangle into a degenerate one.
 */
function elementArrays(els) {
  var o = { r: [], z: [], w: [], h: [], a: [], a2: [] };
  (els || []).forEach(function (e) {
    o.r.push(e.r); o.z.push(e.z); o.w.push(e.w); o.h.push(e.h);
    o.a.push(e.a1 === undefined ? 0 : e.a1);
    o.a2.push(e.a2 === undefined ? 90 : e.a2);
  });
  return o;
}

/**
 * A feed-forward pulse: a shape trajectory in, per-channel current and
 * VOLTAGE waveforms out, with the passive currents they induce.
 *
 * The chain, and what each link is worth:
 *
 *   * every waypoint is designed by `startRun`'s linear isoflux solve, so
 *     the trajectory is a sequence of states that ASK for the requested
 *     shape.  What it is not is a sequence of equilibria — which is why
 *     `verify` re-solves the free boundary at chosen waypoints and reports
 *     the shape actually obtained there, at the cost of one solve each;
 *   * the voltages come from the exact inverse of the circuit integrator
 *     this repo already ships, so the design and its verification are one
 *     discretisation rather than two that nearly agree;
 *   * the limits are REPORTED, never silently applied: a design that
 *     cannot be driven must say so rather than come back quietly clipped.
 */
function pulseRun(msg) {
  var wps = msg.waypoints, nt = wps.length;
  if (nt < 2) {
    post({ type: 'error', where: 'pulse',
           message: FyI18n.t('pulse.too_few') });
    return;
  }
  //: ★★the chain — every waypoint's start, the circuit, the feed-forward
  //: voltages, the checks — is `case.rs::pulse_case` (FYL-DESIGN-16 K-3,
  //: 2026-09-05).  This worker builds the plan and reads the record; what
  //: stays here is the DISPLAY of each check (`summarize` on the field the
  //: kernel returns), exactly as `designRun` keeps its own.
  var nulls = msg.xWeight > 0 ? nullSet(wps[0]) : [];
  var ctl = controlUsable(controlPoints(msg.control));
  var settings = { n_points: msg.nPoints || 24, nu: 4,
                   x_weight: nulls.length ? (msg.xWeight || 1) : 0,
                   lam: msg.lambda === undefined ? 1e-3 : msg.lambda };
  if (msg.etaCoil !== undefined) settings.eta_coil_uohm_m = msg.etaCoil * 1e6;
  if (msg.etaVessel !== undefined) settings.eta_vessel_uohm_m = msg.etaVessel * 1e6;
  var sv = msg.solve || {};
  settings.relax = sv.relax || 0.3;
  settings.max_iter = sv.maxIter || 600;
  settings.tol = sv.tol || 1e-9;
  settings.fb_gain = sv.fbGain === undefined ? 8.0 : sv.fbGain;
  var inputs = { device: deviceDoc() };
  var prof = msg.prof || {};
  if (prof.tab) {
    inputs.equilibrium = { time_slice: [{ profiles_1d: {
      'fylite:psi_norm': Array.from(prof.tab.x),
      dpressure_dpsi: Array.from(prof.tab.pprime),
      f_df_dpsi: Array.from(prof.tab.ffprime) } }] };
  } else {
    settings.beta0 = prof.beta0 === undefined ? 0.55 : prof.beta0;
    settings.emp = prof.emp === undefined ? 1 : prof.emp;
    settings.enp = prof.enp === undefined ? 1 : prof.enp;
  }
  var target = wps.map(function (wp) {
    var g = wp.target;
    return [g.r0, g.z0 === undefined ? 0 : g.z0, g.a, g.kappa,
            g.deltaU === undefined ? 0 : g.deltaU, g.deltaL === undefined ? 0 : g.deltaL];
  });
  inputs.pulse = { 'fylite:time': wps.map(function (wp) { return wp.t; }),
                   'fylite:ip': wps.map(function (wp) { return wp.ip; }),
                   'fylite:target': target };
  var verify = (msg.verify || []).filter(function (k) { return k >= 0 && k < nt && wps[k].ip > 0; });
  if (verify.length) inputs.pulse['fylite:verify'] = verify;
  var discharge = {};
  if (nulls.length) {
    discharge['fylite:null_r'] = nulls.map(function (p) { return p.r; });
    discharge['fylite:null_z'] = nulls.map(function (p) { return p.z; });
  }
  if (ctl.length) {
    discharge['fylite:control_r'] = ctl.map(function (c) { return c.r; });
    discharge['fylite:control_z'] = ctl.map(function (c) { return c.z; });
    discharge['fylite:control_w'] = ctl.map(function (c) { return c.w; });
  }
  if (msg.iMax && msg.iMax.length) discharge['fylite:i_max_aturn'] = Array.from(msg.iMax);
  if (Object.keys(discharge).length) inputs.discharge = discharge;
  post({ type: 'progress', phase: 'pulse', pass: 0, total: nt });
  var rec;
  try { rec = fy.complete('code/pulse', { settings: settings, inputs: inputs }); }
  catch (e) { post({ type: 'error', where: 'pulse', message: e.message }); return; }
  var t = rec.fields.time.data;
  var x = fieldFlat(rec, 'aturns');
  var rms = rec.fields.design_psi_rms.data, bxs = rec.fields.design_b_x.data,
      bound = rec.fields.design_at_bound.data;
  var designs = [];
  for (var k = 0; k < nt; k++) {
    var bind = [];
    for (var c = 0; c < NCH; c++) if (bound[k][c] === 1) bind.push(c);
    designs.push({ psiRms: rms[k], bX: isFinite(bxs[k]) ? bxs[k] : null, bind: bind });
    post({ type: 'progress', phase: 'pulse', pass: k + 1, total: nt });
  }
  var checks = [];
  var idx = rec.fields.check_index.data, okv = rec.fields.check_ok.data;
  var notes = rec.notes || [];
  var num = function (name, j) { return rec.fields[name].data[j]; };
  for (var j = 0; j < idx.length; j++) {
    var kk = idx[j];
    if (!okv[j]) {
      var why = notes.filter(function (n) { return n.indexOf('verify ' + kk + ':') === 0; })[0];
      checks.push({ k: kk, t: t[kk], error: why || 'the verify solve failed' });
      continue;
    }
    var res = {
      psi: Float64Array.from([].concat.apply([], rec.fields.check_psi.data[j])),
      psiAxis: num('check_psi_axis', j), psiBnd: num('check_psi_bnd', j),
      axisR: num('check_axis_r', j), axisZ: num('check_axis_z', j), ip: num('check_ip', j),
      residual: num('check_residual', j), iterations: num('check_iterations', j),
      converged: num('check_converged', j) === 1, settled: num('check_settled', j) === 1,
      bndKind: num('check_bnd_kind', j), xptR: num('check_xpt_r', j), xptZ: num('check_xpt_z', j),
      fbAmp: num('check_fb_amp', j), zc: num('check_zc', j), maskDelta: null,
      tol: settings.tol, maxIter: settings.max_iter,
    };
    var sum = summarize(res, null);
    checks.push({ k: kk, t: t[kk], shape: sum.shape, bndKind: sum.bndKind, criteria: sum.criteria,
                  fbRatio: sum.criteria ? sum.criteria.fbRatio : null, target: wps[kk].target });
  }
  var ff = { v: fieldFlat(rec, 'voltage'), y: fieldFlat(rec, 'passive_current'),
             nv: rec.dims.n_v };
  post({ type: 'pulse', t: t, x: x, v: ff.v, y: ff.y, nch: NCH,
         nv: ff.nv, designs: designs, checks: checks,
         resistance: rec.fields.resistance.data.slice(0, NCH) },
       [x.buffer]);
}

function flatten(poly) {
  var f = new Float64Array(poly.length * 2);
  poly.forEach(function (p, i) { f[2 * i] = p[0]; f[2 * i + 1] = p[1]; });
  return f;
}

// --- reconstruction --------------------------------------------------------

var MEAS_SCALE = 1 / (2 * Math.PI);

/** Vacuum R0*B0 of the machine: q needs a toroidal field, and the forward
 *  model never sees one (only FF' enters j_phi).  Device-level, not
 *  shot-level — a machine without a reference discharge still has one. */
var F_EDGE = 0;

function setMachine(m) {
  M = m;
  var t = self.FyDevice.tf(M);
  F_EDGE = t.b0 * t.r0;
}

/**
 * <j_phi>(x): the fitted cell currents binned onto normalized flux and
 * divided by the bin's cross-sectional area, i.e. the flux-surface-averaged
 * toroidal current density [A/m^2].
 */
function currentProfile(grid, res, cur, nbin) {
  nbin = nbin || 24;
  var nz = grid.nz, mi = grid.nr - 2, mj = nz - 2;
  var da = grid.dr * grid.dz, span = res.psiBnd - res.psiAxis;
  var sum = new Float64Array(nbin), area = new Float64Array(nbin);
  for (var i = 0; i < mi; i++)
    for (var j = 0; j < mj; j++) {
      var c = cur[i * mj + j];
      if (c === 0) continue;
      var x = (res.psi[(i + 1) * nz + (j + 1)] - res.psiAxis) / span;
      x = x < 0 ? 0 : (x > 1 ? 0.999999 : x);
      var b = Math.min(nbin - 1, (x * nbin) | 0);
      sum[b] += c; area[b] += da;
    }
  var xs = new Float64Array(nbin), js = new Float64Array(nbin);
  for (var b2 = 0; b2 < nbin; b2++) {
    xs[b2] = (b2 + 0.5) / nbin;
    js[b2] = area[b2] > 0 ? sum[b2] / area[b2] : NaN;
  }
  return { x: xs, j: js };
}

/** Deterministic normal deviates, so a given seed reproduces a run. */
function rng(seed) {
  var s = seed >>> 0 || 1;
  return function () {
    s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0;
    var u = (s >>> 8) / 16777216;
    s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0;
    var v = (s >>> 8) / 16777216;
    return Math.sqrt(-2 * Math.log(u + 1e-12)) * Math.cos(2 * Math.PI * v);
  };
}

// --- the reconstruction, in three parts ------------------------------------
//
// ★Split because the SAME fit is run many times over: the posterior (below)
// perturbs the kinetic constraint and re-solves, member after member, and
// everything that does not depend on the perturbation — the coil field, the
// loop readings, the weights, the twin's truth solve — must be built once.
// Running the whole of `reconRun` N times would re-solve the twin's forward
// equilibrium N times and would draw a different noise realisation for the
// LOOPS on every member, which is a different experiment from the one the
// error bars claim to be.

/** What every member of a run shares: measurements, weights, Ip, the twin. */
function reconInputs(msg) {
  var chan = Float64Array.from(msg.chan);
  var inp = { psiExt: psiExtOf(chan), truth: null, truthProf: null,
              truthRes: null, truthCur: null, sigma: 0, clean: null };
  var meas, wts, ip, d;

  if (msg.source === 'twin') {
    //: ★★THE TWIN CAN PUT CURRENT IN THE VESSEL.  It is the only way to
    //: judge the vessel fit: on a real shot the induced currents are exactly
    //: what nobody measured.  The mix is deliberately UNEQUAL between groups
    //: — a recovery test that injected the same number everywhere could be
    //: passed by a fit that only got the total right.
    var vTruth = null, vExt = null;
    //: ★the injection is a property of the TWIN, not of the fit: gating it
    //: on the fit switch would mean the two runs a reader compares — vessel
    //: fitted and not — were fitting two different shots
    if (msg.vessel && msg.vessel.twinInject) {
      var vgT = vesselResponse();
      if (vgT) {
        var MIX = [1, 0.5, -0.25];
        vTruth = new Float64Array(vgT.names.length);
        for (d = 0; d < vTruth.length; d++)
          vTruth[d] = (MIX[d] === undefined ? 0 : MIX[d]) * msg.vessel.twinInject;
        var addT = vesselPsi(vTruth);
        vExt = new Float64Array(inp.psiExt.length);
        for (d = 0; d < vExt.length; d++) vExt[d] = inp.psiExt[d] + addT[d];
        inp.vesselTruth = vTruth;
      }
    }
    // 1. truth: a forward free-boundary solve
    var t = freeSolve(chan, msg.prof, msg.ip,
                      vExt ? Object.assign({}, msg.solve, { psiExt: vExt })
                           : msg.solve);
    inp.truthRes = t;
    inp.truth = summarize(t);
    // 2. the current distribution the solver actually built, and the
    //    profiles it implies (recovered from the converged field)
    inp.truthProf = P.analyticTruth(grid, t, msg.prof, M.limiter.r,
                                    M.limiter.z, 201);
    inp.truthCur = P.fittedCurrentAnalytic(grid, t, msg.prof, inp.truthProf);
    // 3. synthetic loop readings through the SAME rows the fit uses
    meas = P.loopModel(loopsM, inp.truthCur, grid, MEAS_SCALE);
    //: the loops see the vessel's own flux too — without this the injected
    //: currents would be invisible to the very measurement that has to
    //: recover them
    if (vTruth) {
      var vgL = vesselResponse();
      for (d = 0; d < meas.length; d++)
        for (var gT = 0; gT < vTruth.length; gT++)
          meas[d] += vTruth[gT] * vgL.loops[gT * M.loops.length + d];
    }
    //: ★★AND THE PROBES.  A twin that synthesised only its flux loops could
    //: never exercise the probe block at all — which is 79 of this deck's
    //: 114 magnetic channels, and the block whose readings a real shot has
    //: to import.  A probe reads the FULL field, coils and vessel included,
    //: so this is taken off the truth's own psi map rather than off the
    //: plasma's contribution.
    if (M.probes && M.probes.length) {
      var prR = Float64Array.from(M.probes, function (p) { return p.r; });
      var prZ = Float64Array.from(M.probes, function (p) { return p.z; });
      var bfT = P.bField(grid, t.psi, prR, prZ);
      var bT = new Float64Array(M.probes.length);
      for (d = 0; d < M.probes.length; d++) {
        var aT = M.probes[d].angle * Math.PI / 180;
        bT[d] = bfT.br[d] * Math.cos(aT) + bfT.bz[d] * Math.sin(aT);
      }
      inp.probeTwin = bT;
    }
    var amp = 0;
    for (d = 0; d < meas.length; d++) amp = Math.max(amp, Math.abs(meas[d]));
    var sigma = msg.noise * amp, gauss = rng(msg.seed || 12345);
    inp.clean = Float64Array.from(meas);
    if (sigma > 0) for (d = 0; d < meas.length; d++) meas[d] += sigma * gauss();
    wts = new Float64Array(meas.length).fill(sigma > 0 ? 1 / sigma : 1);
    ip = msg.ip;
    inp.sigma = sigma;
    //: ★★THE TWIN'S CHORDS, FROM THE TWIN'S OWN TRUTH.  This is what makes
    //: the polarimeter row testable at all: on a real shot there is nothing
    //: to check the recovered `q(0)` against, and here there is.  The
    //: density is the page's — the SAME one the rows are weighted by — so
    //: what the synthetic reading carries is the field and nothing else.
    if (msg.density && msg.density.on && M.point &&
        M.point.interferometer && M.point.interferometer.length) {
      var tp = pointPredictions(t, msg.density);
      if (tp && !tp.error && tp.angleDeg) {
        var gp = rng((msg.seed || 12345) + 991), rel = msg.pointNoise || 0;
        inp.pointTwin = {
          nel: Float64Array.from(tp.nel, function (v) {
            return v * (1 + rel * gp()); }),
          faraday: Float64Array.from(tp.angleDeg, function (v) {
            return v * (1 + rel * gp()); }),
          clean: { nel: tp.nel, faraday: tp.angleDeg },
          synthetic: true,
        };
      }
    }
  } else {
    //: ★a slice of a SERIES brings its own readings; without a series this
    //: is the deck's single delivered slice, exactly as before
    var total = msg.loopMeasTotal;
    if (total && total.length === M.loops.length) {
      var cf = loopCoilFlux(chan);
      meas = new Float64Array(total.length);
      for (var q0 = 0; q0 < total.length; q0++) meas[q0] = total[q0] - cf[q0];
      inp.loopCoil = cf;
    } else {
      meas = Float64Array.from(msg.loopMeas || M.reference.loopMeas);
    }
    wts = Float64Array.from(msg.loopWeights || M.reference.loopWeights);
    ip = msg.ipOverride || (M.reference && M.reference.ip) || 0;
  }
  //: ★THE READER'S CHANNEL TABLE, applied here and nowhere else.  A loop
  //: switched off is a loop with weight zero — not a row removed — so every
  //: index downstream (the deck's names, the cross-section's markers, the
  //: residual table) still means the same channel.  A scale multiplies the
  //: deck's own weight rather than replacing it: the deck's relative
  //: calibration is what it knows and the reader's factor is what the
  //: reader knows, and one is not a substitute for the other.
  var nDeck = meas.length;
  for (var i = 0; i < nDeck; i++) {
    //: ★★A DECK-DISOWNED LOOP THE READER ASKED FOR gets a weight of its own:
    //: scaling zero is still zero, so a force-on that only multiplied would
    //: be a control that does nothing and says nothing.  The base is 1 —
    //: the deck has no opinion to scale here, which is the whole situation.
    if (msg.loopForce && msg.loopForce[i] && !(wts[i] > 0)) wts[i] = 1;
    else if (msg.loopMask && !msg.loopMask[i]) { wts[i] = 0; continue; }
    if (msg.loopScale && isFinite(msg.loopScale[i])) wts[i] *= msg.loopScale[i];
  }

  // --- probe rows, when the reader has supplied readings to fit -----------
  //
  // ★The weight is RELATIVE and the reason is the same one the pressure rows
  // needed: a row's pull is `w * |b|`, and a probe reading (~0.1 T) against a
  // loop reading (~0.5 Wb/rad) with equal weights is not equal footing.  So
  // the probe weights are put on the mean weighted loop row and then scaled
  // by the caller's own factor.
  inp.matrix = loopsM;
  inp.nLoops = meas.length;
  var pf = msg.probeFit;
  //: a twin's probe readings are its own, exactly as its chord readings are
  //: ★they are SYNTHETIC (sampled off the twin's own truth field), and it
  //: is tempting to let them skip the deck's 0/79 calibration mask — that
  //: would let a twin answer T-A6's question ahead of the calibrated
  //: data.  Tried 2026-08-23 and REVERTED: with the probe rows actually
  //: weighted the twin's member fit itself diverges (`gs_inverse_solve`:
  //: 法方程奇异, at outer iteration 43–80, even with zero vessel
  //: injection), so the weighted-probe twin is a repair of its own
  //: before it is a T-A6 instrument.  Until then the deck's verdict
  //: stands here as everywhere.
  if (pf && pf.on && inp.probeTwin && !(pf.meas && pf.meas.length))
    pf = { on: true, weight: pf.weight, mask: pf.mask, meas: inp.probeTwin };
  if (pf && pf.on && pf.meas && pf.meas.length && M.probes &&
      pf.meas.length === M.probes.length) {
    var mat = combinedRows();
    if (mat) {
      var sw = 0, nw = 0, sb = 0, d2;
      for (d2 = 0; d2 < meas.length; d2++) {
        if (!wts[d2]) continue;
        sw += wts[d2]; nw += 1; sb += meas[d2] * meas[d2];
      }
      var wBarL = nw ? sw / nw : 1, bBarL = nw ? Math.sqrt(sb / nw) : 1;
      //: plasma-only, to match what the rows predict
      var coilB = probeCoilField(chan);
      var pMeas = new Float64Array(pf.meas.length);
      for (d2 = 0; d2 < pf.meas.length; d2++)
        pMeas[d2] = pf.meas[d2] - coilB[d2];
      var pAmp = 0;
      for (d2 = 0; d2 < pMeas.length; d2++)
        pAmp = Math.max(pAmp, Math.abs(pMeas[d2]));
      var wP = (pf.weight || 1) * wBarL * bBarL / Math.max(pAmp, 1e-12);
      var nAll = meas.length + pf.meas.length;
      var m2 = new Float64Array(nAll), w2 = new Float64Array(nAll);
      m2.set(meas, 0); w2.set(wts, 0);
      for (d2 = 0; d2 < pf.meas.length; d2++) {
        m2[meas.length + d2] = pMeas[d2];
        //: the deck's own mask decides WHICH probes count, the reader's
        //: channel table can switch one off on top of that, and the slider
        //: only decides how much the surviving ones count against the loops.
        //: ★Three switches, one direction: none of them can turn a channel
        //: the deck disowns back on.
        //: ★★THREE MASKS, ALL OF WHICH MUST HOLD.  The deck's own weight is
        //: the machine's standing statement about a probe; the SHOT's
        //: `fwtmp2` is the reduction's statement about that probe on that
        //: day (a channel that went dead reads exactly 0.0 and is flagged
        //: here, not in the deck); the reader's table is the third.  Fitting
        //: without the shot mask asks the solver to put B = 0 at every dead
        //: probe — measured on #137985: the solve fails outright.
        //: ★★the reader's FORCE-ON overrides the deck's standing verdict and
        //: only that one: the shot's own validity flag still has to hold,
        //: because a channel that read exactly 0.0 that day is not a channel
        //: anybody can ask for.  〔Ruling 2026-08-31: preset = deck AND gate,
        //: and the disagreement between them is the reader's to resolve —
        //: measured on #137985, deck 21 of 79, gate 37, both 20.〕
        var deckSays = M.probes[d2].weight || (pf.force && pf.force[d2]);
        var keep = deckSays &&
                   (!pf.shotWeights || pf.shotWeights[d2]) &&
                   (!pf.mask || pf.mask[d2] || (pf.force && pf.force[d2]));
        var sc = (pf.scale && isFinite(pf.scale[d2])) ? pf.scale[d2] : 1;
        w2[meas.length + d2] = keep ? wP * sc : 0;
      }
      meas = m2; wts = w2;
      inp.matrix = mat;
      inp.nProbes = pf.meas.length;
      inp.probeWeight = wP;
      inp.probeCoil = coilB;
      inp.probePlasma = pMeas;
      //: what the instrument read, kept beside the plasma-only rows the fit
      //: was given: a residual column that showed the difference the SOLVER
      //: sees would be comparing a probe against a plasma
      inp.probeMeasFull = Float64Array.from(pf.meas);
    }
  }
  inp.meas = meas; inp.wts = wts; inp.ip = ip;
  return inp;
}

// --- kinetic rows ---------------------------------------------------------
//
// ★THE PRESSURE CONSTRAINT CARRIES A GAUGE, and getting it wrong does not
// fail — it fits a NEGATIVE central pressure and reports it.
//
// The kernel builds each pressure row as `span * (basis integrals)`, where
// `span = psi_bnd - psi_axis`.  This app carries psi as FULL FLUX with the
// axis at the MAXIMUM, so that span is NEGATIVE; EFIT's per-radian gauge,
// which the native callers use, has the axis at the minimum and a POSITIVE
// span.  The rows therefore come out with opposite signs in the two
// gauges, and a measurement handed over as a plain positive pressure is
// only correct in one of them.
//
// History worth keeping: this page once "fixed" the mismatch by flipping
// the sign INSIDE the kernel (0f8be04).  That made the app right and the
// native path wrong, and it was reverted upstream (c030188) with evidence
// — p' sign, q0 and the anchor all degraded there.  The mismatch was never
// a kernel bug; it is the caller's job to hand over the constraint in the
// gauge it is itself using, which is what this factor does.
//
// Measured, both ways, on the bundled shot: with the factor, residual
// 3.96e-9 / weighted chi^2 4.25e-4 / p(0) = +7499 Pa; without it,
// 1.84e-4 / 5.33e-4 / p(0) = -7642 Pa.
var PSI_GAUGE = -1;

/**
 * The pressure rows for ONE member, drawn with `seed`.
 *
 * ★`seed` is an argument rather than read from `msg`: it is the only thing
 * that changes between members of a posterior, and making it explicit is
 * what keeps "the same shot, measured again" separate from "a different
 * shot".
 */
/**
 * The non-thermal pressure a reader has declared, at `x`.
 *
 * ★★WHAT A KINETIC RECONSTRUCTION IS ACTUALLY CONSTRAINED BY.  The
 * equilibrium sees the TOTAL pressure — thermal plus fast ions plus
 * rotation — while a Thomson/CXRS profile measures the thermal part alone
 * and the bootstrap is driven by the thermal gradient.  Handing a thermal
 * profile over as though it were the total is the standard way a
 * beam-heated discharge comes out with the wrong `p'`, and nothing in the
 * fit can notice.
 *
 * ★Neither term is INVENTED here.  A fast-ion profile is used when one has
 * been imported; the parametrised fraction below is a SHAPE the reader set,
 * labelled as such everywhere it goes, and zero by default.  Rotation
 * pressure needs `omega(psi)` and a mass density, which this page has no
 * channel for, so it is only ever an imported profile.
 */
function extraPressure(pd, x, pTh) {
  if (!pd) return 0;
  var v = 0;
  if (pd.fast && pd.fast.length) v += profileAt(pd.fast, x);
  else if (pd.fastFraction > 0)
    v += pd.fastFraction * pTh *
         Math.pow(Math.max(1 - x * x, 0), pd.fastPeaking || 1);
  if (pd.rot && pd.rot.length) v += profileAt(pd.rot, x);
  return v;
}

function reconKinetic(msg, inp, seed) {
  var out = { xp: [], pmeas: [], wp: [] };
  if (!(msg.kinetic && msg.kinetic.on)) return out;
  var n = msg.kinetic.points, pref = null, d;
  // an imported profile wins over the bundled one; the twin always uses
  // its own truth, which is the whole point of the twin
  var ext = msg.kinetic.pressure;
  if (msg.source === 'twin') pref = function (x) { return inp.truthProf.pAt(x); };
  else {
    var pr = (ext && ext.length) ? ext : M.reference.pres, m = pr.length;
    pref = function (x) {
      var t2 = x * (m - 1), k = Math.min(m - 2, Math.max(0, t2 | 0));
      return pr[k] + (t2 - k) * (pr[k + 1] - pr[k]);
    };
  }
  //: ★the rows are the TOTAL pressure, because that is what the equilibrium
  //: is: the profile handed over is read as thermal when a decomposition
  //: has been declared, and as total when none has
  var pd = msg.pressure || null;
  var pTot = function (x) {
    var pt = pref(x);
    return pt + extraPressure(pd, x, pt);
  };
  var p0 = pTot(0), gk = rng(seed + 7);
  //: what the page draws is the PHYSICAL pressure it was told to believe;
  //: `pmeas` below is the same number in the kernel's row gauge.  Reporting
  //: the row value made the constraint points land mirrored below zero on a
  //: panel whose curve is positive — a picture of the sign convention, not
  //: of the measurement.
  // Put the pressure rows on the magnetics' footing before applying the
  // user's relative weight: a row's pull on the fit is w * |b|, so match
  // the TYPICAL weighted magnetic row.  Without the loop-weight factor
  // the pressure channel is silently inert whenever the loops are
  // weighted by 1/sigma (weights of ~1e3 against a raw ratio of ~1e-6).
  var sw = 0, nw = 0, sb = 0;
  for (d = 0; d < inp.meas.length; d++) {
    if (!inp.wts[d]) continue;
    sw += inp.wts[d]; nw += 1; sb += inp.meas[d] * inp.meas[d];
  }
  var wBar = nw ? sw / nw : 1, bBar = nw ? Math.sqrt(sb / nw) : 1;
  var w0 = msg.kinetic.weight * wBar * bBar / Math.max(p0, 1e-9);
  out.weight = w0;
  out.pPhys = [];
  out.pThermal = [];
  for (var q = 1; q <= n; q++) {
    var x = q / (n + 1), pv = pTot(x) * (1 + (msg.kinetic.noise || 0) * gk());
    out.xp.push(x);
    out.pPhys.push(pv);
    out.pThermal.push(pref(x));
    out.pmeas.push(PSI_GAUGE * pv);
    out.wp.push(w0);
  }
  return out;
}

// --- T-A5: the coil block -------------------------------------------------
//
// ★★WHAT THE PAGE HAS TO SUPPLY THAT IT NEVER HAD TO BEFORE: a sigma for the
// FLUX LOOPS.  A weighted least squares is a posterior only when `w = 1/σ`,
// and every deck here ships loop weights that are a 0/1 MASK — which asserts
// σ_loop = 1 Wb/rad.  Against a coil prior of a few per cent that assertion
// says the loops are worthless, and the fit leaves the currents exactly where
// it found them: measured on EAST #137985 at 4 s, a 20 % coil prior against
// mask weights moved the currents by 3e-4 of themselves and li(3) fell only
// 21.30 -> 18.06.  So「fit the coils」 is not a switch that can be flipped on
// its own — it obliges the reader to say how well the loops are measured, and
// the control says so beside the switch.
//
// The sigmas are RELATIVE and stated as such: σ_coil = rel * |I_c| per
// channel (a channel reading zero is therefore HELD, which is the right
// answer — there is no relative calibration of nothing), σ_loop = rel *
// max|plasma-only loop reading|, the same normalisation the posterior's own
// loop perturbation already uses.
function coilBlock(msg, inp) {
  var cf = msg.coilFit;
  if (!(cf && cf.on)) return null;
  if (!coilG || !coilG.psiCh) return null;
    //: ★`chanDrawn` when a posterior member perturbed the currents, `msg.chan`
  //: otherwise — the SAME vector `psiExt` was built from.  Fitting a
  //: correction against a different baseline than the field was built on is
  //: two coil sets in one solve.
  var nrow = inp.meas.length,
      chan = inp.chanDrawn || Float64Array.from(msg.chan);
  var rows = new Float64Array(nrow * NCH), c, i;
  var lrows = coilLoopRows(), nl = inp.nLoops;
  for (i = 0; i < nl; i++)
    for (c = 0; c < NCH; c++) rows[i * NCH + c] = lrows[c * M.loops.length + i];
  var off = nl;
  if (inp.nProbes) {
    var prows = coilProbeRows();
    //: ★the probe rows carry the solver's 2 pi pre-scale (see the assembly
    //: above), so the coil response at a probe has to carry it too — the
    //: two must be in ONE unit or the fit trades a tesla for a Wb/rad.
    for (i = 0; i < inp.nProbes; i++)
      for (c = 0; c < NCH; c++)
        rows[(off + i) * NCH + c] =
          prows[c * M.probes.length + i] * (2 * Math.PI);
    off += inp.nProbes;
  }
  //: ★A CHORD ROW THE COILS ARE INVISIBLE TO WOULD BE A LIE, not a
  //: simplification: the Faraday integrand is built on B_R, and the coils
  //: make B_R.  Rather than leave those rows' coil columns at zero, the
  //: fit is refused when they are present — `withFaradayRows` has no
  //: per-channel form and inventing one here would be a second host for
  //: the chord geometry.
  if (inp.nFaraday) return null;
  var amp = 0;
  for (i = 0; i < nl; i++)
    if (inp.wts[i]) amp = Math.max(amp, Math.abs(inp.meas[i]));
  var sig = new Float64Array(NCH);
  for (c = 0; c < NCH; c++) sig[c] = Math.abs(cf.sigma * chan[c]);
  return { coilPsi: coilG.psiCh, coilRows: rows, coilI0: chan,
           coilSigma: sig,
           measSigma: Math.max(cf.loopSigma * amp, 1e-300) };
}

/**
 * Solve one member and diagnose it.  Throws; the caller decides what that
 * means.
 *
 * ★`jPre` (T-A9) is the PRESCRIBED per-cell toroidal current [A] — the
 * bootstrap channel the kernel entry has taken since ABI v17 and this page
 * has always passed as empty.  With one supplied, the free coefficients
 * only make up the remainder, and the reported current is the plasma's:
 * the prescribed part is added back below, masked the way the solver masks
 * it, or every number this function returns would be short by it.
 */
function reconMember(msg, inp, kin, jPre) {
  var call = {
    r: grid.r, z: grid.z, psiExt: inp.psiExt, loopsM: inp.matrix || loopsM,
    meas: inp.meas,
    wts: inp.wts, measScale: MEAS_SCALE, npp: msg.npp, nff: msg.nff, ip: inp.ip,
    limR: M.limiter.r, limZ: M.limiter.z,
    xp: kin.xp, pmeas: kin.pmeas, wp: kin.wp,
    relax: msg.solve && msg.solve.relax || 0.3,
    maxIter: msg.solve && msg.solve.maxIter || 800,
    tol: 1e-9, fbGain: 8.0, warmup: msg.warmup === undefined ? 40 : msg.warmup,
  };
  if (jPre && jPre.length) call.jPre = jPre;
  var blk = coilBlock(msg, inp);
  //: ★TWO ENTRIES, BY NAME.  Without a coil block this is the entry it has
  //: always been and returns the numbers it has always returned; the coil
  //: entry is not a flag on it.
  var res = blk ? fy.gsInverseSolveCoils(Object.assign(call, blk))
                : fy.gsInverseSolve(call);

  // fit quality: forward-model the loops from the fitted coefficients
  var mask = P.plasmaMask(grid, res.psi, res.psiAxis, res.psiBnd,
                          M.limiter.r, M.limiter.z, 1);
  var fitCur = P.fittedCurrent(grid, res.psi, res.psiAxis, res.psiBnd,
                               res.coefs, msg.npp, msg.nff, mask);
  //: ★the prescribed part is part of the PLASMA, so it is added back
  //: before anything is forward-modelled or integrated — and it is masked
  //: with THIS iterate's plasma, the way the solver re-masks it, not with
  //: the one it was built on
  if (jPre && jPre.length === fitCur.length)
    for (var jp = 0; jp < fitCur.length; jp++)
      if (mask[jp]) fitCur[jp] += jPre[jp];
  var model = P.loopModel(loopsM, fitCur, grid, MEAS_SCALE);
  //: ★chi^2 IS THE LOOPS' — one block, one unit, one panel.  The probe and
  //: chord blocks pull on the same solution and are reported beside it in
  //: their own units (`probeRows`, `faraday`); adding them into this number
  //: would put teslas and line integrals on a Wb/rad axis and make the one
  //: figure of merit the page quotes depend on which extra blocks were on.
  var chi2 = 0, nfit = 0;
  for (var d = 0; d < inp.nLoops; d++) {
    if (!inp.wts[d]) continue;
    var r_ = inp.wts[d] * (model[d] - inp.meas[d]);
    chi2 += r_ * r_; nfit += 1;
  }
  var out = { result: summarize(res), model: model, chi2: chi2, nfit: nfit,
              fitCur: fitCur };
  //: ★the DOF, stated rather than left to be counted: a chi^2 with no row
  //: count beside it is a number nobody can compare with another run, and
  //: the count moves every time the reader switches a channel off
  out.ndof = Math.max(1, nfit + (kin.xp ? kin.xp.length : 0)
                      - (msg.npp + msg.nff));
  out.result.coefs = res.coefs;
  out.ipFitted = P.totalCurrent(fitCur);
  out.profiles = P.fittedProfiles(res.coefs, msg.npp, msg.nff,
                                  res.psiAxis, res.psiBnd, 201);
  out.q = P.qProfile(grid, res, out.profiles, M.limiter.r, M.limiter.z,
                     F_EDGE, { nq: 20, ntheta: 121 });
  out.jphi = currentProfile(grid, res, fitCur);
  //: li(3) is the kernel's integral over the psi map, so it costs one pass
  //: and needs nothing traced; it is one of the scalars a reconstruction is
  //: judged on, which is why it travels with every member and not only with
  //: the run the page happens to draw
  out.li3 = P.li3(grid, res, out.ipFitted, self.FyDevice.tf(M).r0);
  //: ★the coil fit reports itself: how far it moved the currents (in units
  //: of the sigma it was given), and what it moved them to.  A member that
  //: bought its residual with a coil excursion no calibration allows is a
  //: THIRD way to be wrong, beside the two `notAPlasma` already tests, and
  //: it cannot be seen from any other number the run reports.
  if (blk) {
    out.coilPull = res.coilPull;
    out.coilFit = res.coilFit;
    out.coilFitted = res.coilFitted;
    out.coilSigma = blk.coilSigma;
    out.coilBefore = blk.coilI0;
    out.measSigma = blk.measSigma;
  }
  out.raw = res;
  return out;
}

/**
 * Extend a row block with one Faraday row per chord.
 *
 * Returns a shadowed `inp` — the loops and probes it already carried, then
 * the chords — or null when the machine, the data or the density is missing.
 */
function withFaradayRows(inp, fr, pmN, geom, dens, chan) {
  //: ★the readings are an ARGUMENT, not a field of the request: they come
  //: from a file on a real shot and from the truth on a twin, and threading
  //: them through the request block is how the first wiring of this quietly
  //: built no rows at all (`no-rows`, with everything else switched on).
  if (!geom || !geom.length || !fr || !pmN || !pmN.n) return null;
  var n = Math.min(geom.length, pmN.n), NGc = grid.nr * grid.nz;
  var target = new Float64Array(n), any = false, i;
  for (i = 0; i < n; i++) {
    target[i] = pmN.weightPol[i] ? pmN.target[i] : NaN;
    if (isFinite(target[i])) any = true;
  }
  if (!any) return null;
  //: the rows are the PLASMA's; the coils' share of each reading is computed
  //: and subtracted, exactly as the probe block does with its own field
  var coil = chordCoilField(geom, dens, chan);
  for (i = 0; i < n; i++) if (isFinite(target[i])) target[i] -= coil[i];
  var rows = faradayRows(geom, dens);
  var base = inp.matrix || loopsM, nBase = inp.meas.length;
  var mat = new Float64Array(base.length + n * NGc);
  mat.set(base, 0); mat.set(rows, base.length);
  //: ★the same relative-weight rule the probe rows needed, and for the same
  //: reason: a row's pull is `w * |value|`, and a chord integral (~1e19 in
  //: SI) against a loop reading (~0.5 Wb/rad) at equal weights is not equal
  //: footing — it is the only row the fit would listen to.
  var sw = 0, nw = 0, sb = 0;
  for (i = 0; i < inp.nLoops; i++) {
    if (!inp.wts[i]) continue;
    sw += inp.wts[i]; nw += 1; sb += inp.meas[i] * inp.meas[i];
  }
  var wBar = nw ? sw / nw : 1, bBar = nw ? Math.sqrt(sb / nw) : 1, amp = 0;
  for (i = 0; i < n; i++)
    if (isFinite(target[i])) amp = Math.max(amp, Math.abs(target[i]));
  var wF = (fr.weight || 1) * wBar * bBar / Math.max(amp, 1e-30);
  var meas = new Float64Array(nBase + n), wts = new Float64Array(nBase + n);
  meas.set(inp.meas, 0); wts.set(inp.wts, 0);
  for (i = 0; i < n; i++) {
    meas[nBase + i] = isFinite(target[i]) ? target[i] : 0;
    //: a chord with no reading is a row with no weight, not a row that
    //: says the rotation was zero
    wts[nBase + i] = isFinite(target[i]) &&
                     (!fr.mask || fr.mask[i]) ? wF : 0;
  }
  var out = Object.create(inp);
  out.matrix = mat; out.meas = meas; out.wts = wts;
  out.nFaraday = n; out.faradayWeight = wF; out.faradayTarget = target;
  out.faradayCoil = coil; out.faradayRows = rows; out.faradayGeom = geom;
  return out;
}

/**
 * ★★ONE DEFINITION OF "THIS REQUEST, AT THAT SLICE", AND IT IS `seriesSlice`.
 *
 * The page used to carry a second, shorter copy of that rule (the analysis
 * page's `runSlice`, which put a slice's loops, weights, coils and Ip on the
 * request and stopped there).  The two copies disagreed about the three
 * things the copy did not have — the slice's own `ip`, its own `prof`, and
 * above all THE PRESSURE RULE: a slice with no pressure measured at its own
 * moment is fitted on magnetics alone, because the deck's delivered profile
 * belongs to the reference time and to no other.  So the same (shot, instant)
 * came back as two different answers depending on which control the reader
 * had touched.  Measured on #137985 before this, deck slices, stock settings:
 *
 *   t = 2.0 s   series 「磁通跨度退化」(rejected)  ·  picked 「重构完成」, l_i(3) 3.769
 *   t = 2.5 s   series solved, q95 1.111, l_i(3) 17.77  ·  picked 「法方程奇异」
 *
 * — opposite verdicts at BOTH instants, and nothing on the page said the two
 * routes were asking different questions.  A caller now NAMES the slice
 * (`msg.slice`) rather than re-spelling what a slice does, and the single
 * fit, the series loop and the batch queue are one code path.
 *
 * ★AND THE POSTERIOR IS THE FOURTH CALLER (T-A16).  `recon_mc` is `recon`
 * with a member count, so it has to resolve the slice through the SAME
 * function or the error bars are drawn for a different question from the one
 * the figures answer — measured on #137985 before this: picking t = 2.5 s and
 * pressing 跑后验 sampled the reference instant (I_p 393.46 kA, the delivered
 * pressure profile) while the cross-section and the scalars on screen were
 * the 401.54 kA magnetics-only fit at 2.5 s.  Hence `atSlice`, called by both
 * entry points and by nothing else.
 */
function atSlice(msg) {
  return msg && msg.slice ? seriesSlice(msg, msg.slice) : msg;
}

/**
 * The bootstrap current as a PRESCRIBED per-cell toroidal current [A].
 *
 * `j_phi = k F / R` with `k = <j.B>_bs / <B^2>`: the local distribution a
 * pure parallel current actually has.  ★Writing the flux-surface AVERAGE
 * into every cell of the surface instead would be smooth, plausible, and
 * would move current from the high-field side to the low-field one.
 */
function prescribedBootstrap(mem, cl) {
  var res = mem.raw, nz = grid.nz, mi = grid.nr - 2, mj = nz - 2;
  var da = grid.dr * grid.dz, span = res.psiBnd - res.psiAxis;
  if (!span) return null;
  var mask = P.plasmaMask(grid, res.psi, res.psiAxis, res.psiBnd,
                          M.limiter.r, M.limiter.z, 1);
  var out = new Float64Array(mi * mj);
  for (var i = 0; i < mi; i++) {
    var r = grid.r[i + 1];
    for (var j = 0; j < mj; j++) {
      if (!mask[i * mj + j]) continue;
      var x = (res.psi[(i + 1) * nz + (j + 1)] - res.psiAxis) / span;
      x = x < 0 ? 0 : (x > 1 ? 1 : x);
      out[i * mj + j] =
        interp1(cl.x, cl.kBs, x) * interp1(cl.x, cl.fPsi, x) / r * da;
    }
  }
  return out;
}

/**
 * The self-consistent outer loop: fit -> bootstrap -> fit.
 *
 * ★★WHAT IS SELF-CONSISTENT ABOUT IT.  The bootstrap current is a
 * functional of the equilibrium — it needs `q`, the trapped fraction and
 * the collisionality, all of which the fit produces — while the
 * equilibrium is a functional of the current.  A fit that is handed no
 * bootstrap current has to represent it with the same two polynomials it
 * represents everything else with, which is precisely the freedom this
 * loop removes: the bootstrap part becomes KNOWN physics on the
 * prescribed channel, and only the remainder is fitted.
 *
 * ★What is watched is the BOOTSTRAP FRACTION, not `q0` or the residual:
 * it is the one number the loop is about, it is bounded, and it is a
 * ratio — so「converged」cannot be bought by everything shrinking.
 *
 * The loop reports its whole history, including the rounds after it met
 * the tolerance, because a fixed point is a claim about a sequence and
 * one number cannot carry it.
 */
function closureLoop(msg, msgD, inp, kin, mem0) {
  var spec = msg.closure || {};
  var maxIt = Math.max(1, Math.min(10, (spec.iters | 0) || 3));
  var tol = spec.tol > 0 ? spec.tol : 0.01;
  var mem = mem0, err = null, stop = 'iterations';
  var hist = [], ips = [], q0s = [];
  var bs = reconBootstrap(msgD, mem);
  var cl = bs && !bs.error ? bs.closure : null;
  if (!cl || cl.error) {
    return { mem: null,
             report: { error: (bs && bs.error) || (cl && cl.error)
                              || 'no-density', history: [] } };
  }
  hist.push(cl.fBs);
  ips.push(mem.ipFitted);
  q0s.push(mem.q && mem.q.q ? mem.q.q[0] : NaN);
  for (var it = 0; it < maxIt; it++) {
    var jPre = prescribedBootstrap(mem, cl);
    if (!jPre) { err = 'no-span'; break; }
    var next;
    try { next = reconMember(msg, inp, kin, jPre); }
    catch (e) { err = e.message; break; }
    var bs2 = reconBootstrap(msgD, next);
    var cl2 = bs2 && !bs2.error ? bs2.closure : null;
    if (!cl2 || cl2.error) { err = (bs2 && bs2.error) || 'bootstrap-failed';
                             break; }
    mem = next; cl = cl2;
    hist.push(cl.fBs);
    ips.push(mem.ipFitted);
    q0s.push(mem.q && mem.q.q ? mem.q.q[0] : NaN);
    var a = hist[hist.length - 1], b = hist[hist.length - 2];
    if (Math.abs(a) > 0 && Math.abs(a - b) / Math.abs(a) < tol) {
      stop = 'converged';
      break;
    }
  }
  //: ★the spread over the LAST rounds, which is the closure criterion —
  //: `(max - min) / mean` over everything after the first round, so a
  //: sequence that wandered cannot pass by ending near where it started
  var tail = hist.slice(1);
  var spread = NaN;
  if (tail.length >= 2) {
    var mn = Math.min.apply(null, tail), mx = Math.max.apply(null, tail);
    var mean = tail.reduce(function (p, c) { return p + c; }, 0) / tail.length;
    spread = mean !== 0 ? (mx - mn) / Math.abs(mean) : NaN;
  }
  return {
    mem: mem === mem0 ? null : mem,
    report: {
      history: hist, ip: ips, q0: q0s, rounds: hist.length - 1,
      stop: err ? 'error' : stop, error: err, tol: tol, maxIter: maxIt,
      spread: spread,
      fBs: hist[hist.length - 1],
      model: 'prescribed-bootstrap-cell-current (j_phi = k F / R)',
    },
  };
}

function reconRun(msg0) {
  var msg = atSlice(msg0);
  var inp, mem;
  if (msg.source === 'twin') {
    try { inp = reconInputs(msg); }
    catch (e) { post({ type: 'error', where: 'truth', message: e.message }); return; }
  } else {
    inp = reconInputs(msg);
  }
  var kin = reconKinetic(msg, inp, msg.seed || 12345);
  try { mem = reconMember(msg, inp, kin); }
  catch (e) {
    //: ★A FAILURE CARRIES ITS PROVENANCE TOO.  A queue's summary row for a
    //: slice that did not solve still has to say what it was asked — which
    //: current it was constrained to, which basis it was fitted in — or the
    //: reader cannot tell a bad slice from a badly posed question.
    post({ type: 'error', where: 'recon', message: e.message,
           ip: inp.ip, channelBasis: channelBasisOf(msg) });
    return;
  }

  var fitUsed = inp;
  //: ★★THE VESSEL FIRST, because it changes the EXTERNAL field every later
  //: step is measured against: the chords are integrated through the solved
  //: map and the Faraday rows carry the coils' share explicitly.
  var vfit = null, vcur = null, inpBase = inp, vError = null;
  if (msg.vessel && msg.vessel.on && (M.vessel || []).length) {
    var nV = Math.max(1, Math.min(5, (msg.vessel.outer | 0) || 2));
    var psi0 = inp.psiExt;
    vcur = null;
    for (var iv = 0; iv < nV; iv++) {
      var f = fitVessel(inpBase, mem, msg, msg.vessel.rcond);
      if (!f) { vError = 'no-response'; break; }
      if (f.error) { vError = f.error; break; }
      //: ★nothing kept is an ANSWER: these channels cannot see the vessel
      //: independently of the plasma, and a zero handed over as a fitted
      //: current would read as "the vessel carried none"
      //: ★THE IDENTIFIABILITY GATE.  Below this the vessel's own signature
      //: is smaller than what the plasma basis can imitate, and a number
      //: fitted there is a number fitted to model error.  The threshold is
      //: the reader's, and refusing is the default posture of this project.
      if (!f.kept || !isFinite(f.survive) ||
          f.survive < (msg.vessel.minSurvive || 0)) {
        vError = 'not-identifiable';
        vfit = { names: f.names, current: null, kept: f.kept,
                 condition: f.condition, survive: f.survive, rows: f.rows,
                 singular: f.singular, singularRaw: f.singularRaw };
        break;
      }
      //: ★ACCUMULATED, not replaced: each pass explains what the loops still
      //: see AFTER the previous vessel field was already in the solve
      if (!vcur) vcur = new Float64Array(f.current.length);
      for (var g2 = 0; g2 < vcur.length; g2++) vcur[g2] += f.current[g2];
      var add = vesselPsi(vcur);
      var pe2 = new Float64Array(psi0.length);
      for (var c2 = 0; c2 < pe2.length; c2++) pe2[c2] = psi0[c2] + add[c2];
      var inpV = Object.create(inp);
      inpV.psiExt = pe2;
      var mv;
      try { mv = reconMember(msg, inpV, kin); }
      catch (eV) {
        //: ★the vessel field it just added made the equilibrium unsolvable.
        //: That is a REFUSAL with a cause, not an absent block: the last
        //: good fit stands and the page says why it stopped there.
        vError = 'solve-failed-with-vessel: ' + eV.message;
        break;
      }
      mem = mv; inpBase = inpV; fitUsed = inpV;
      vfit = { names: f.names, current: vcur, kept: f.kept,
               condition: f.condition, survive: f.survive, rows: f.rows,
               singular: f.singular, singularRaw: f.singularRaw };
    }
  }

  //: ★★THE CHORDS, BOTH WAYS.  First backwards — which density explains the
  //: measured line integrals — and then forwards, as rows the fit is given.
  //: The order is not free: the Faraday row is `n_e` times a Green's
  //: function, so a density fitted to the interferometer has to exist before
  //: the polarimeter can constrain anything.
  var dens = msg.density, dfit = null, geom = null,
      farError = null, farIters = 0;
  //: a twin's readings are its own; a real shot's have to have been imported
  //: a twin's readings are its own; a real shot's come from the deck, from a
  //: slice, or from a file — all four through one normalisation
  var pmN = normalisePointMeas(
    (msg.source === 'twin' && inp.pointTwin) ? inp.pointTwin
      : (msg.pointMeas || (M.reference && M.reference.point
          ? { nel19: M.reference.point.n_e_line19,
              bpolar: M.reference.point.bpolar,
              weightNel: M.reference.point.weight_nel,
              weightPol: M.reference.point.weight_pol } : null)));
  if (dens && dens.on && dens.fitChords && pmN) {
    geom = chordGeometry(mem.raw);
    dfit = fitDensityToChords(geom, pmN.nel, pmN.weightNel);
    if (dfit) dens = Object.assign({}, dens, { ne0: dfit.ne0,
                                               peaking: dfit.peaking,
                                               profile: null });
  }
  if (msg.faraday && msg.faraday.on && pmN && dens && dens.on) {
    var nOuter = Math.max(1, Math.min(5, (msg.faraday.outer | 0) || 2));
    for (var it = 0; it < nOuter; it++) {
      //: the surfaces the rows are built on are the PREVIOUS iterate's —
      //: which samples lie inside the plasma is part of the answer
      var g2 = chordGeometry(mem.raw);
      var inp2 = withFaradayRows(inpBase, msg.faraday, pmN, g2, dens,
                                 inp.chanDrawn || Float64Array.from(msg.chan));
      if (!inp2) { farError = 'no-rows'; break; }
      var m2;
      try { m2 = reconMember(msg, inp2, kin); }
      catch (e2) { farError = e2.message; break; }
      mem = m2; fitUsed = inp2; farIters = it + 1;
      //: the density is re-fitted on the new surfaces too, or the second
      //: pass would weight the rows by a density from the first geometry
      if (dfit) {
        var g3 = chordGeometry(mem.raw),
            d3 = fitDensityToChords(g3, pmN.nel, pmN.weightNel);
        if (d3) { dfit = d3; dens = Object.assign({}, dens,
          { ne0: d3.ne0, peaking: d3.peaking, profile: null }); }
      }
    }
  }
  var msgD = dens === msg.density ? msg
    : Object.assign({}, msg, { density: dens });

  //: ★★T-A9 — THE SELF-CONSISTENT OUTER LOOP, and it runs BEFORE the
  //: non-plasma test so that the answer judged is the answer reported.
  //: With the switch off nothing below runs and this fit is bit-for-bit
  //: the one it always was.
  var closureLoopRep = null;
  if (msg.closure && msg.closure.on) {
    var lp = closureLoop(msg, msgD, inp, kin, mem);
    closureLoopRep = lp.report;
    if (lp.mem) mem = lp.mem;
  }

  //: ★a solve that RETURNED is not a solve that SUCCEEDED — the same test the
  //: series loop applies to every slice, applied here to the one that is about
  //: to go on screen.  Judged on the FINAL member, after the vessel and the
  //: chord loops have had their say, because that is the answer the reader
  //: would otherwise be handed.
  var notPlasma = notAPlasma(inp, mem);
  if (notPlasma) {
    post({ type: 'error', where: 'recon', message: notPlasma,
           ip: inp.ip, channelBasis: channelBasisOf(msg) });
    return;
  }

  var out = { type: 'recon', source: msg.source, sigma: inp.sigma,
              //: ★THE EQUALITY THE FIT WAS GIVEN, beside the one it produced
              //: (`ipFitted` below).  They are one quantity computed two
              //: ways; `notAPlasma` rejects on how far apart they are, and a
              //: summary table that printed only the second could not be
              //: checked against that test at all.  ★NOT `result.ip`, which
              //: is a third thing — the current integrated off the shape
              //: refinement's own mask (0.8 kA from `ipFitted` on this shot).
              ipConstraint: inp.ip,
              channelBasis: channelBasisOf(msg),
              //: what the fit was actually given, so the page reports the
              //: channels it fitted rather than the ones it was offered
              fitRows: { loops: inp.nLoops, probes: inp.nProbes || 0,
                         probeWeight: inp.probeWeight || 0,
                         faraday: fitUsed.nFaraday || 0,
                         faradayWeight: fitUsed.faradayWeight || 0,
                         faradayIterations: farIters,
                         faradayError: farError } };
  if (dfit) out.densityFit = dfit;
  //: ★ONE PLACE ASSEMBLES THIS, whatever happened.  The first version
  //: reported the vessel only when a fit existed, so a REFUSAL — the
  //: channels cannot see the vessel, the projection was singular — arrived
  //: at the page as an absent block and was drawn as the generic
  //: "not identifiable", losing the actual reason.
  if (vError || vfit || inp.vesselTruth) {
    out.vessel = {
      names: (vfit && vfit.names) || vesselGroups().names,
      error: vError,
      current: vfit && vfit.current ? Float64Array.from(vfit.current) : null,
      truth: inp.vesselTruth ? Float64Array.from(inp.vesselTruth) : null,
      kept: vfit ? vfit.kept : null,
      rows: vfit ? vfit.rows : null,
      survive: vfit ? vfit.survive : null,
      condition: vfit ? vfit.condition : null,
      singular: vfit ? vfit.singular : null,
      singularRaw: vfit ? vfit.singularRaw : null,
      model: 'uniform-loop-voltage-per-group',
      rcond: msg.vessel ? msg.vessel.rcond : null,
    };
  }
  if (dfit) out.densityFit = dfit;
  if (pmN)
    out.pointMeas = { nel: pmN.nel, faraday: pmN.faradayDeg,
                      bpolar: Float64Array.from(pmN.target,
                                                function (v) { return v / 1e19; }),
                      weightNel: pmN.weightNel, weightPol: pmN.weightPol,
                      synthetic: !!pmN.synthetic };
  if (inp.clean) out.clean = inp.clean;
  if (kin.xp.length) {
    out.kineticWeight = kin.weight;
    out.kineticX = Float64Array.from(kin.xp);
    out.kineticP = Float64Array.from(kin.pPhys);
    //: the thermal half beside the total, so the page can show what the
    //: decomposition actually added rather than asserting that it did
    out.pThermalRows = Float64Array.from(kin.pThermal || []);
  }
  out.result = mem.result;
  //: ★SLICED TO THE LOOPS.  With probe readings imported, `inp.meas` and
  //: `inp.wts` are the COMBINED row block (loops then probes) while `model`
  //: is the loop forward model — so the page's residual, its RMS and its
  //: exported `flux_loop` list all ran off the end of `model` into
  //: `undefined` and reported NaN for a fit that had converged.  The probe
  //: rows travel below, in their own units.
  out.meas = fitUsed.meas.slice(0, inp.nLoops);
  out.wts = fitUsed.wts.slice(0, inp.nLoops);
  out.model = mem.model;
  if (inp.nProbes)
    out.probeRows = { meas: inp.probeMeasFull,
                      wts: fitUsed.wts.slice(inp.nLoops,
                                             inp.nLoops + inp.nProbes),
                      plasma: inp.probePlasma, coil: inp.probeCoil };
  out.chi2 = mem.chi2;
  out.nfit = mem.nfit;
  out.ndof = mem.ndof;
  //: ★T-A5 — the coil fit, reported as an ANSWER rather than inferred from
  //: the request: which channels were free, what they were before and after,
  //: and how far the fit moved them in units of the sigma it was told.  The
  //: page cannot recompute any of this from `msg`.
  if (mem.coilPull !== undefined)
    out.coilFit = { pull: mem.coilPull, fitted: mem.coilFitted,
                    before: mem.coilBefore, after: mem.coilFit,
                    sigma: mem.coilSigma, measSigma: mem.measSigma,
                    cap: COIL_PULL_MAX };
  out.ipFitted = mem.ipFitted;
  out.profiles = mem.profiles;
  out.q = mem.q;
  out.jphi = mem.jphi;
  out.li3 = mem.li3;
  //: only when a density was supplied; `null` is the page's cue to say which
  //: input is missing rather than to draw an empty panel
  //: ★★THE INSTRUMENT LAYER, and it is the kernel's.  `computed/measured`
  //: per channel against their own MEDIAN is a calibration statement rather
  //: than a residual: the median absorbs any global scale or unit offset, so
  //: only channel-relative inconsistency can reject a channel — a rule that
  //: judged the absolute ratio would reject the whole set the moment a unit
  //: changed.  This entry shipped in every artifact and was reachable from
  //: Python alone.
  out.selfcal = { loops: selfcalOf(out.meas, out.model, out.wts,
                                   msg.selfcalTol) };
  if (out.probeRows && out.probes)
    out.selfcal.probes = selfcalOf(out.probeRows.meas, out.probes.b,
                                   out.probeRows.wts, msg.selfcalTol);
  out.bootstrap = reconBootstrap(msgD, mem);
  if (closureLoopRep) out.closureLoop = closureLoopRep;
  out.probes = probePredictions(mem.raw, mem.fitCur, Float64Array.from(msg.chan));
  //: the predictions are drawn on the SOLVED surfaces of the fit that was
  //: kept, through the density that fit was made with
  out.point = pointPredictions(mem.raw, msgD.density);
  if (fitUsed.nFaraday && out.point) {
    //: ★★THE SAME NUMBER BY TWO ROUTES, as the probes do it.  One route is
    //: the solved psi map, sampled and integrated (`point.bpolar`); the
    //: other is the row block the fit was GIVEN, contracted with the fitted
    //: current, plus the coils' own share.  They are independent — one goes
    //: through the solver's field, the other through the Green's rows — so
    //: agreeing is the evidence that the rows are the rows for THESE chords,
    //: with this quadrature, in these units.  A missing 2 pi, a density
    //: evaluated on the wrong label or a coil term left out shows up here
    //: and nowhere else: the fit would simply move somewhere plausible.
    var viaRows = null, worst = NaN;
    try {
      //: ★THE CHECK IS ON THE FINAL SURFACES, not on the ones the last fit
      //: was given.  The rows the solver used were built on the previous
      //: iterate — that is what makes the constraint usable at all — so
      //: comparing them against the final field mixes two different
      //: questions: "are these the right rows" and "has the outer loop
      //: converged".  Measured with the two mixed: 22 %.  Separated: the
      //: number below, which is the discretisation difference alone.
      var gFin = chordGeometry(mem.raw);
      var rowsFin = faradayRows(gFin, dens);
      var coilFin = chordCoilField(gFin, dens,
                                   inp.chanDrawn || Float64Array.from(msg.chan));
      var pl = P.loopModel(rowsFin, mem.fitCur, grid, MEAS_SCALE);
      viaRows = new Float64Array(fitUsed.nFaraday);
      var amp = 0, i2;
      for (i2 = 0; i2 < fitUsed.nFaraday; i2++) {
        viaRows[i2] = pl[i2] + coilFin[i2];
        amp = Math.max(amp, Math.abs(out.point.bpolar[i2] * 1e19));
      }
      worst = 0;
      for (i2 = 0; i2 < fitUsed.nFaraday; i2++)
        worst = Math.max(worst, Math.abs(viaRows[i2] -
                                         out.point.bpolar[i2] * 1e19));
      worst = amp > 0 ? worst / amp : NaN;
    } catch (e3) { viaRows = null; }
    out.faraday = { target: fitUsed.faradayTarget,
                    coil: fitUsed.faradayCoil,
                    model: Float64Array.from(out.point.bpolar,
                                             function (v) { return v * 1e19; }),
                    viaRows: viaRows, rowsVsFieldRel: worst,
                    weight: fitUsed.faradayWeight,
                    measDeg: Float64Array.from(pmN.faradayDeg),
                    weight: Float64Array.from(pmN.weightPol),
                    synthetic: !!pmN.synthetic,
                    modelDeg: Float64Array.from(out.point.angleDeg) };
  }
  if (inp.truth) {
    out.truth = inp.truth;
    out.truthProfiles = { x: inp.truthProf.x, pprime: inp.truthProf.pprime,
                          ffprime: inp.truthProf.ffprime, p: inp.truthProf.p };
    out.truthQ = P.qProfile(grid, inp.truthRes, out.truthProfiles, M.limiter.r,
                            M.limiter.z, F_EDGE, { nq: 20, ntheta: 121 });
    out.truthJphi = currentProfile(grid, inp.truthRes, inp.truthCur);
  }
  post(out);
}

// --- probes as CONSTRAINTS ------------------------------------------------
//
// ★The rows are the kernel's (`fylite_rs_probe_response`), and they are the
// probe analogue of the flux-loop rows: `B_R cos a + B_Z sin a` per amp of
// toroidal current in each cell.  Predicting a probe needs none of this — the
// solved field already answers that — but FITTING one needs a row saying how
// each cell's current would move that reading.
//
// ★★The two families are in DIFFERENT UNITS and the solver applies ONE
// `meas_scale` to every row it is given.  The loops are handed over as full
// flux and want `1/2pi` (Wb/rad); the probe rows are already teslas and want
// 1.  So the probe rows are pre-multiplied by `2pi` here, and the solver's
// own factor takes them back — the alternative, rescaling the loop half,
// would change the arithmetic of the path that is already under gate.

function probeRows() {
  if (probesM) return probesM;
  if (!M.probes || !M.probes.length) return null;
  var raw = fy.probeResponse({
    gridR: grid.r, gridZ: grid.z,
    probeR: Float64Array.from(M.probes, function (p) { return p.r; }),
    probeZ: Float64Array.from(M.probes, function (p) { return p.z; }),
    angleRad: Float64Array.from(M.probes, function (p) {
      return p.angle * Math.PI / 180; }),
  });
  var k = 2 * Math.PI;
  for (var i = 0; i < raw.length; i++) raw[i] *= k;
  probesM = raw;
  return probesM;
}

/**
 * The COILS' contribution to each probe reading, in tesla.
 *
 * ★★This is the difference between a probe that constrains the plasma and a
 * probe that constrains nothing.  The deck's loop readings arrive with the
 * coil term already subtracted — they are the plasma flux, which is what the
 * response rows predict — while an imported probe reading is the FULL field
 * at that probe, plasma and coils together.  Fitting the full field against a
 * plasma-only row asks the plasma current to reproduce the coil field as
 * well, and the solver obliges: it converges on a distorted plasma with a
 * worse probe residual than it started with (measured on this shot: 2.32 %
 * before, 2.77 % after, with li(3) 2.67 -> 3.42).
 *
 * ★The PREDICTION on the panel is deliberately not treated this way: it is
 * the full solved field, because that is what a probe reads.
 */
/**
 * The COILS' flux at each loop [Wb/rad], for a reading that arrives whole.
 *
 * ★★TWO CONVENTIONS MEET HERE, and the deck says which is which.  The
 * reference discharge's `loopMeas` is the delivered reconstruction's channel
 * value with the coils' share ALREADY removed — it is compared directly
 * against the plasma-only forward model.  A raw instrument reading
 * (`loopMeasTotal`, and every slice of the time series) is the TOTAL flux:
 * plasma and coils together.  Handing the total to a plasma-only model asks
 * the plasma to account for the coils as well, and the fit obliges — with a
 * current distribution that is simply not the one that was there.  So the
 * subtraction happens here, once, with the same element response the vacuum
 * field itself is built from.
 */
//: ★★PER CHANNEL, NOT PER FOLDED VECTOR — and that is what T-A5 needed.
//: 「What do the coils contribute at this loop」 and 「what does ONE channel
//: contribute at this loop」 are the same Green's function contracted at
//: different moments: the first is the second times the channel currents.
//: While the currents were exactly known only the first was ever wanted, so
//: the fold happened inside these two helpers and the per-channel table had
//: no name.  A fit that carries the coil currents as unknowns needs exactly
//: that table — it IS the coil columns — so the table is built once, cached,
//: and the two folded answers are contractions of it.  One host for the
//: response, two questions.  (`coilRowCache` is declared at the top with
//: the other machine caches, so `init` can drop it on a machine change.)

/** `(nch, n_loops)` Wb/rad per unit channel current. */
function coilLoopRows() {
  if (coilRowCache.loops) return coilRowCache.loops;
  var nel = M.coils.length, n = M.loops.length;
  var lr = Float64Array.from(M.loops, function (p) { return p[0]; });
  var lz = Float64Array.from(M.loops, function (p) { return p[1]; });
  var resp = P.coilPointResponse(fy, M.coils, lr, lz, 4, 4);
  var out = new Float64Array(NCH * n);
  for (var c = 0; c < NCH; c++)
    for (var e = 0; e < nel; e++) {
      var w = chanMap[c * NEL + e];
      if (!w) continue;
      for (var i = 0; i < n; i++)
        //: the loop channel is Wb PER RADIAN, as every other loop number on
        //: this page is; the response is full flux
        out[c * n + i] += w * resp.psi[e * n + i] * MEAS_SCALE;
    }
  coilRowCache.loops = out;
  return out;
}

/** `(nch, n_probes)` tesla per unit channel current. */
function coilProbeRows() {
  if (coilRowCache.probes) return coilRowCache.probes;
  if (!M.probes || !M.probes.length) return null;
  var pr = Float64Array.from(M.probes, function (p) { return p.r; });
  var pz = Float64Array.from(M.probes, function (p) { return p.z; });
  var ang = Float64Array.from(M.probes,
                              function (p) { return p.angle * Math.PI / 180; });
  //: ★the angle projection is the kernel's — see `elementProbeResponse`.
  var resp = fy.elementProbeResponse(M.coils, pr, pz, ang, 3, 3);
  var n = M.probes.length, nel = M.coils.length;
  var out = new Float64Array(NCH * n);
  for (var c = 0; c < NCH; c++)
    for (var e = 0; e < nel; e++) {
      var w = chanMap[c * NEL + e];
      if (!w) continue;
      for (var i = 0; i < n; i++) out[c * n + i] += w * resp[i * nel + e];
    }
  coilRowCache.probes = out;
  return out;
}

//: ★★AND THE TWO FOLDED HELPERS ARE LEFT EXACTLY AS THEY WERE — they do
//: NOT contract the table above, and that is deliberate.  Rewriting them as
//: `sum_c I_c row_c` is the same arithmetic in a different summation order,
//: which moves every coil-subtracted channel by ~1e-16 relative.  Measured:
//: that was enough to flip one of the batch queue's eleven rows from a
//: kernel refusal to a `shape_metrics` failure — the Picard iteration on a
//: slice that was already failing is chaotic, and a bitwise-different input
//: lands it somewhere else.  Nothing about the answer improves, and a
//: refactor that perturbs a shipped result to remove a five-line
//: contraction is a bad trade.  The GREEN'S FUNCTION still has one host
//: (`coilPointResponse` / `elementProbeResponse`); what is written twice is
//: only which way the two sums are nested.
function loopCoilFlux(chan) {
  var el = elementCurrents(chan), nel = M.coils.length, n = M.loops.length;
  var lr = Float64Array.from(M.loops, function (p) { return p[0]; });
  var lz = Float64Array.from(M.loops, function (p) { return p[1]; });
  var resp = P.coilPointResponse(fy, M.coils, lr, lz, 4, 4);
  var out = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    var acc = 0;
    for (var e = 0; e < nel; e++) acc += el[e] * resp.psi[e * n + i];
    //: the loop channel is Wb PER RADIAN, as every other loop number on this
    //: page is; the response is full flux
    out[i] = acc * MEAS_SCALE;
  }
  return out;
}

function probeCoilField(chan) {
  var el = elementCurrents(chan);
  var pr = Float64Array.from(M.probes, function (p) { return p.r; });
  var pz = Float64Array.from(M.probes, function (p) { return p.z; });
  var ang = Float64Array.from(M.probes,
                              function (p) { return p.angle * Math.PI / 180; });
  //: ★the angle projection is the kernel's — see `elementProbeResponse`.
  //: What is left here is the contraction with the element currents, which
  //: is this page's question (what do the coils contribute at each probe),
  //: not a second spelling of what a probe reads.
  var resp = fy.elementProbeResponse(M.coils, pr, pz, ang, 3, 3);
  var n = M.probes.length, nel = M.coils.length;
  var out = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    var acc = 0;
    for (var e = 0; e < nel; e++) acc += el[e] * resp[i * nel + e];
    out[i] = acc;
  }
  return out;
}

/** [loop rows; probe rows] in one buffer, which is what the solver reads. */
function combinedRows() {
  if (allM) return allM;
  var pm = probeRows();
  if (!pm) return null;
  var n = grid.nr * grid.nz;
  allM = new Float64Array(loopsM.length + pm.length);
  allM.set(loopsM, 0);
  allM.set(pm, loopsM.length);
  return allM;
}

// --- what the reconstruction says each magnetic probe should read ----------
//
// ★This needs NO response matrix.  A probe reading is the poloidal field at a
// point, projected on the direction the probe measures along, and the solved
// psi map already carries that field — plasma and coils together, which is
// exactly what a probe sees.  A response matrix is what putting probes INTO
// the fit would need (rows relating each reading to the current distribution),
// and that is a different job from saying what the fitted equilibrium
// predicts at 79 places around the machine.
//
// ★The projection is the whole content: `AMP2` is the angle the probe
// measures ALONG, so the reading is `Br cos(a) + Bz sin(a)`.  Drop the angle
// and every channel returns Br — a smooth, plausible, wrong set of numbers.

function probePredictions(res, fitCur, chan) {
  if (!M.probes || !M.probes.length) return null;
  var n = M.probes.length;
  var b = new Float64Array(n);
  //: one crossing for the whole probe list, not one per probe
  var pr = new Float64Array(n), pz = new Float64Array(n);
  for (var i = 0; i < n; i++) { pr[i] = M.probes[i].r; pz[i] = M.probes[i].z; }
  var f = P.bField(grid, res.psi, pr, pz), br = f.br, bz = f.bz;
  for (i = 0; i < n; i++) {
    var a = M.probes[i].angle * Math.PI / 180;
    b[i] = br[i] * Math.cos(a) + bz[i] * Math.sin(a);
  }
  var out = { b: b, br: br, bz: bz };

  //: ★THE SAME NUMBER BY TWO ROUTES.  Above: the solved psi map, sampled and
  //: projected.  Below: the kernel's Green's rows applied to the fitted
  //: current, plus the coils' own field.  They are independent — one goes
  //: through the solver's field, the other through the response matrix that
  //: the fit is built on — so agreeing is evidence that the rows are the
  //: rows for THESE probes, at these angles, in these units.  A wrong angle
  //: convention or a missing 2pi shows up here and nowhere else.
  if (fitCur && chan) {
    try {
      var rows = probeRows();
      if (rows) {
        //: the rows were pre-scaled by 2pi for the solver's own meas_scale;
        //: applying that scale here undoes it, which is what makes this
        //: comparable to the sampled field
        var plasma = P.loopModel(rows, fitCur, grid, MEAS_SCALE);
        var coil = probeCoilField(chan);
        var viaRows = new Float64Array(n), amp = 0, worst = 0;
        for (var k = 0; k < n; k++) {
          viaRows[k] = plasma[k] + coil[k];
          amp = Math.max(amp, Math.abs(b[k]));
        }
        for (k = 0; k < n; k++)
          worst = Math.max(worst, Math.abs(viaRows[k] - b[k]));
        out.viaRows = viaRows;
        out.rowsVsFieldRel = amp > 0 ? worst / amp : NaN;
      }
    } catch (e) { out.rowsError = e.message; }
  }
  return out;
}

// --- POINT: line-integrated density, and the Faraday rotation --------------
//
// ★Both are predictions of the SAME two things the probes were: the solved
// psi map, and the density channel.  `n_e-line` is the density profile
// integrated along the sight line; the Faraday angle is the density weighted
// by the field ALONG THE BEAM, which for these horizontal chords is B_R.
// Neither needs a response matrix, and neither is a fit residual — the fit
// never sees them.
//
// ★★The quadrature is the KERNEL's (`fylite_rs_quadrature`, Simpson) and the
// samples are the kernel's (`fylite_rs_chord_samples`, which takes a 3-D
// origin and direction so a tangential chord is not silently flattened into
// its poloidal projection).  What is assembled here is only the integrand,
// which is physics that can be written down: `n_e(psi_N(s))` and
// `n_e(psi_N(s)) * B_R(s)`.
//
// ★The reported `bpolar` is `integral n_e B dl / 1e19`, the quantity EFIT is
// given rather than the angle itself, because that is the form the native
// path converts a measured angle INTO (`io.est2`, POINT block).  The angle in
// degrees is reported beside it, through the deck's own two constants, so a
// reader can check either against an instrument.

var POINT_SAMPLES = 401;

/**
 * Where each sight line is, and what the solved field is there.
 *
 * ★ONE GEOMETRY FOR THREE QUESTIONS.  The chord predictions, the density
 * channel fitted to the interferometer and the Faraday rows the fit can be
 * given all need the same three things — which samples are inside the
 * plasma, what `psi_N` is there, and what `B_R` is there — and each of them
 * had every reason to sample the line its own way.  Three samplings of one
 * chord is three answers to "where does the plasma start", and the
 * disagreement would show up as a physics discrepancy rather than as a
 * geometry one.
 *
 * The kept samples are the ones inside the grid AND inside the boundary;
 * the arrays are FULL LENGTH with zeros elsewhere, because the quadrature
 * is Simpson over the whole line and its abscissae must not move.
 */
function chordGeometry(res) {
  var pt = M.point;
  if (!pt || !pt.interferometer || !pt.interferometer.length) return null;
  var chords = pt.interferometer, n = chords.length, out = [];
  var span = res.psiBnd - res.psiAxis;
  for (var k = 0; k < n; k++) {
    var c = chords[k], fp = c.first_point || {};
    var th = c['fylite:theta'] || 0;
    //: theta is the tilt of the sight line in the poloidal plane; the beam
    //: enters from the outboard side, so it travels along -R
    var dir = [-Math.cos(th), 0, Math.sin(th)];
    var sm = fy.chordSamples({ origin3: [fp.r, 0, fp.z], dir3: dir,
                               length: 2.2, n: POINT_SAMPLES });
    //: ★TWO passes, because the field is now one crossing for the whole
    //: chord rather than one per sample.  The first pass decides which
    //: samples are in the plasma at all — the guards are unchanged — and
    //: only those are handed over.
    var boxI = [], boxR = [], boxZ = [], i;
    for (i = 0; i < POINT_SAMPLES; i++) {
      var rr = sm.r[i], zz = sm.z[i];
      if (!(rr > grid.r[0] && rr < grid.r[grid.nr - 1] &&
            zz > grid.z[0] && zz < grid.z[grid.nz - 1])) continue;
      boxI.push(i); boxR.push(rr); boxZ.push(zz);
    }
    var keep = [], keepR = [], keepZ = [], keepX = [];
    if (boxI.length) {
      var psAll = P.sample(grid, res.psi, Float64Array.from(boxR),
                           Float64Array.from(boxZ));
      for (var b = 0; b < boxI.length; b++) {
        var x = span !== 0 ? (psAll[b] - res.psiAxis) / span : 2;
        //: outside the boundary there is no plasma density to integrate; the
        //: scrape-off layer is not modelled and is not quietly given a value
        if (!(x >= 0 && x <= 1)) continue;
        keep.push(boxI[b]); keepR.push(boxR[b]); keepZ.push(boxZ[b]);
        keepX.push(x);
      }
    }
    var br = null;
    if (keep.length) {
      var bf = P.bField(grid, res.psi, Float64Array.from(keepR),
                        Float64Array.from(keepZ));
      br = bf.br;
    }
    out.push({ name: c.name, z: fp.z, ds: sm.ds, keep: keep, x: keepX,
               r: keepR, z2: keepZ, br: br, inside: keep.length });
  }
  return out;
}

/** A full-length integrand with `vals` dropped on the kept samples. */
function chordFill(g, vals) {
  var a = new Float64Array(POINT_SAMPLES);
  for (var i = 0; i < g.keep.length; i++) a[g.keep[i]] = vals[i];
  return a;
}

/** `integral f ds` along one chord, the kernel's Simpson rule. */
function chordIntegral(g, vals) {
  return fy.quadrature(chordFill(g, vals), g.ds, 0);
}

// --- the interferometer, read BACKWARDS ------------------------------------
//
// ★★A SYNTHETIC DIAGNOSTIC THAT CANNOT BE FITTED IS HALF A DIAGNOSTIC.  The
// page has predicted `n_e L` on eleven chords for as long as it has had a
// density, and the density it predicted them from was two sliders.  The
// forward operator is the same one either way, so the backward question —
// which density reproduces the chords that were MEASURED — costs no new
// physics: `n_e = n_e0 (1 - x^2)^alpha` is LINEAR in `n_e0`, so `alpha` is
// scanned and `n_e0` comes out in closed form on each one.
//
// ★What this does NOT do is invert the profile SHAPE.  Eleven line integrals
// through a two-parameter family determine two numbers; a page that returned
// a free radial profile from them would be returning its own regularisation.

var ALPHA_MIN = 0, ALPHA_MAX = 3, ALPHA_STEP = 0.02;

/**
 * The `(n_e0, alpha)` that best explains the measured chord densities.
 *
 * `meas` is one `n_e L` per chord [m^-2]; a non-finite entry is a chord the
 * reader has no reading for and is skipped rather than fitted to zero.
 */
function fitDensityToChords(geom, meas, weight) {
  if (!geom || !meas || !meas.length) return null;
  var n = Math.min(geom.length, meas.length);
  var best = null;
  for (var a = ALPHA_MIN; a <= ALPHA_MAX + 1e-9; a += ALPHA_STEP) {
    var num = 0, den = 0, shape = [], k, i;
    for (k = 0; k < n; k++) {
      var gk = geom[k];
      //: ★a chord the reduction gated out (a lost fringe) is NOT a chord
      //: that read zero.  Fitting to it would drag the whole density down by
      //: however many chords the interferometer happened to lose.
      if (!isFinite(meas[k]) || !gk.keep.length ||
          (weight && !weight[k])) { shape.push(NaN); continue; }
      var v = [];
      for (i = 0; i < gk.keep.length; i++)
        v.push(Math.pow(Math.max(1 - gk.x[i] * gk.x[i], 0), a));
      var I = chordIntegral(gk, v);
      shape.push(I);
      num += I * meas[k]; den += I * I;
    }
    if (!(den > 0)) continue;
    var ne0 = num / den, chi2 = 0, used = 0, model = [];
    for (k = 0; k < n; k++) {
      if (!isFinite(shape[k]) || !isFinite(meas[k])) { model.push(NaN); continue; }
      var m = ne0 * shape[k];
      model.push(m);
      var d = (m - meas[k]) / Math.max(Math.abs(meas[k]), 1e-30);
      chi2 += d * d; used += 1;
    }
    if (!used) continue;
    if (!best || chi2 < best.chi2)
      best = { ne0: ne0, peaking: a, chi2: chi2, used: used, model: model,
               //: the scan step IS the resolution of `alpha`, and it travels
               //: with the answer: a round trip through this fit returns the
               //: parameters it started from to within one step, which is
               //: exactly the check that says the operator is invertible
               step: ALPHA_STEP };
  }
  //: ★an alpha ON the edge of the scan is reported as such: the family did
  //: not contain the answer, and a boundary optimum that reads like an
  //: interior one is how a two-parameter fit hides being the wrong family
  if (best) best.atEdge = best.peaking <= ALPHA_MIN + 1e-9 ||
                          best.peaking >= ALPHA_MAX - 1e-9;
  return best;
}

// --- the polarimeter as a CONSTRAINT ---------------------------------------
//
// ★★THE ONLY INTERNAL CURRENT INFORMATION THIS MACHINE HAS.  A fit driven by
// flux loops and a pressure profile cannot resolve `q(0)`: the magnetics see
// the current distribution only through its moments outside the plasma, and
// the pressure constrains `p'`, not `FF'`.  MSE is what a tokamak normally
// answers this with and EAST's deck carries none — but it carries eleven
// polarimeter chords, and the Faraday rotation on a chord is
// `integral n_e B_R dl`, which IS an internal current measurement.
//
// The row is linear in the plasma current, exactly as a flux-loop row is:
// `B_R` at a point is a Green's function contracted with the cell currents
// (the kernel's `probe_response` at angle zero), and the chord integral of
// it is that same contraction under the quadrature weights.  So the rows go
// into the SAME least-squares block as the loops and the probes.
//
// ★TWO THINGS MAKE IT NOT A PLAIN LINEAR ROW, and both are stated rather
// than hidden:
//   1. WHICH SAMPLES ARE INSIDE the plasma depends on the solution.  The
//      rows are therefore built on the PREVIOUS iterate's surfaces and the
//      fit is repeated — the same device EFIT uses for MSE.  One repetition
//      is the default; the reader can ask for more.
//   2. `n_e` MULTIPLIES the row.  A Faraday constraint is only as good as
//      the density it is read through, which is why this page will not let
//      it be switched on without a density channel.

var QUAD_W = null;

/**
 * The kernel's own quadrature weights, recovered rather than re-derived.
 *
 * ★`fylite_rs_quadrature` owns the rule (Simpson over uniform samples), and
 * a row block needs the rule applied to a MATRIX — one column per grid cell
 * — which the entry cannot do.  Writing the weights out here would put
 * Simpson in a second host; asking the kernel what it does to each unit
 * vector does not.  `ds` factors out, so this is computed once at `ds = 1`
 * and scaled.
 */
function quadWeights(n) {
  if (QUAD_W && QUAD_W.length === n) return QUAD_W;
  var w = new Float64Array(n), e = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    e[i] = 1;
    w[i] = fy.quadrature(e, 1, 0);
    e[i] = 0;
  }
  QUAD_W = w;
  return w;
}

/**
 * One row per chord: `d(integral n_e B_R ds) / d j(cell)`, pre-scaled by
 * `2 pi` the way the probe rows are, because the solver divides every row
 * block by its `meas_scale`.
 */
function faradayRows(geom, spec) {
  var n = geom.length, NGc = grid.nr * grid.nz;
  var rows = new Float64Array(n * NGc);
  var w = quadWeights(POINT_SAMPLES);
  //: ★★THE ROW IS BUILT THE WAY THE FIELD IS READ.  `B_R` is not asked of
  //: the Green's rows directly: the kernel computes it from a psi map as
  //: `-(dpsi/dz)/(2 pi r)`, central-differenced at HALF the smaller cell —
  //: and inside the current-carrying region a filament-per-cell field and a
  //: differenced psi are not the same number.  Measured with the row block
  //: taken from `probe_response` at angle zero: the two routes agreed to
  //: 2 % on the outer chords and disagreed by 32 % and 46 % on the two
  //: chords either side of the axis, where `B_R` is a small difference of
  //: large cancelling parts.  A constraint whose model is wrong by half on
  //: two of eleven rows does not measure what its label says.
  //:
  //: So the row is the SAME finite difference, taken on the psi response:
  //: `d(psi)/dz` from the kernel's own point response at `z +- h`, divided
  //: by `2 pi r`.  The solver's `meas_scale` then multiplies the block by
  //: `2 pi`, which cancels the `2 pi` here — written out rather than
  //: cancelled on paper, because the two factors have different reasons.
  var h = 0.5 * Math.min(grid.dr, grid.dz), TWO_PI = 2 * Math.PI;
  for (var k = 0; k < n; k++) {
    var gk = geom[k], m = gk.keep.length;
    if (!m) continue;
    //: one chord at a time: the response for every kept sample of every
    //: chord at once is 2600 x 4225 doubles on this deck, and it is thrown
    //: away as soon as it is folded into eleven rows
    var pts = new Array(2 * m);
    for (var i = 0; i < m; i++) {
      pts[2 * i] = [gk.r[i], gk.z2[i] + h];
      pts[2 * i + 1] = [gk.r[i], gk.z2[i] - h];
    }
    var resp = P.loopResponse(fy, grid, pts);
    for (i = 0; i < m; i++) {
      var f = TWO_PI * w[gk.keep[i]] * gk.ds * densityAt(spec, gk.x[i]) *
              (-1 / (2 * h * TWO_PI * gk.r[i]));
      if (!f) continue;
      var up = 2 * i * NGc, dn = (2 * i + 1) * NGc, dst = k * NGc;
      for (var c = 0; c < NGc; c++)
        rows[dst + c] += f * (resp[up + c] - resp[dn + c]);
    }
  }
  return rows;
}

/**
 * `integral n_e B_R,coil ds` per chord — what the COILS put into a Faraday
 * reading.
 *
 * ★★THE HALF THAT IS NOT THE PLASMA, and leaving it out is the same mistake
 * the probe rows record: the response rows answer "what does a unit of
 * PLASMA current do here", while a polarimeter reads the whole field.
 * Handing the full reading to a plasma-only row block asks the plasma to
 * account for the coils as well, and the fit obliges — with a current
 * distribution that is simply not the one that was there.
 *
 * ★Read off the external psi map with the kernel's own `b_field`, which is
 * the same difference the plasma rows are built from — the coils' share has
 * to be subtracted in the units and with the discretisation the rows model,
 * not in a second one.
 */
function chordCoilField(geom, dens, chan) {
  var pe = psiExtOf(chan), out = new Float64Array(geom.length);
  for (var k = 0; k < geom.length; k++) {
    var gk = geom[k], m = gk.keep.length;
    if (!m) continue;
    var bf = P.bField(grid, pe, Float64Array.from(gk.r),
                      Float64Array.from(gk.z2));
    var vals = [];
    for (var i = 0; i < m; i++)
      vals.push(bf.br[i] * densityAt(dens, gk.x[i]));
    out[k] = chordIntegral(gk, vals);
  }
  return out;
}

/**
 * Every source of chord readings, in ONE shape.
 *
 * ★THREE SOURCES, TWO UNITS.  The device deck and its time slices carry what
 * EFIT is given — `n_e L / 1e19` and `∫n_e B dl / 1e19` — because that is
 * what the site's reduction produces; a magnetics document exported by this
 * page carries the line density in m^-2 and the rotation in DEGREES.  The
 * angle and `bpolar` are the same measurement through the laser constants,
 * so converting one into the other is lossless — but doing it in three
 * places would be three chances to drop a factor of two.  Here, once:
 * `nel` is m^-2, `target` is `∫n_e B_R ds` (the row block's own unit), and a
 * chord with no reading or no weight carries NaN rather than a zero.
 */
function normalisePointMeas(pm) {
  if (!pm) return null;
  var n = (pm.nel19 || pm.nel || pm.bpolar || pm.faraday || []).length;
  if (!n) return null;
  var out = { n: n, nel: new Float64Array(n), target: new Float64Array(n),
              faradayDeg: new Float64Array(n),
              weightNel: new Float64Array(n), weightPol: new Float64Array(n),
              synthetic: !!pm.synthetic };
  var pt = M.point || {};
  var cFar = (pt['fylite:faraday_constant'] || 0) *
             Math.pow(pt['fylite:laser_wavelength'] || 0, 2);
  for (var i = 0; i < n; i++) {
    out.nel[i] = pm.nel ? pm.nel[i]
      : (pm.nel19 ? pm.nel19[i] * 1e19 : NaN);
    var bp = pm.bpolar ? pm.bpolar[i] * 1e19
      : (pm.faraday && cFar ? faradayTarget(pm.faraday[i]) : NaN);
    out.target[i] = bp;
    out.faradayDeg[i] = pm.faraday ? pm.faraday[i]
      : (cFar ? bp * cFar * 2 * 180 / Math.PI : NaN);
    out.weightNel[i] = pm.weightNel ? pm.weightNel[i]
      : (isFinite(out.nel[i]) ? 1 : 0);
    out.weightPol[i] = pm.weightPol ? pm.weightPol[i]
      : (isFinite(bp) ? 1 : 0);
  }
  return out;
}

/** `integral n_e B_R ds` [T/m^2] that a measured rotation angle stands for. */
function faradayTarget(angleDeg) {
  var pt = M.point || {};
  var cFar = (pt['fylite:faraday_constant'] || 0) *
             Math.pow(pt['fylite:laser_wavelength'] || 0, 2);
  if (!cFar) return NaN;
  return angleDeg * Math.PI / 180 / (2 * cFar);
}

function pointPredictions(res, spec, geom) {
  var pt = M.point;
  if (!pt || !pt.interferometer || !pt.interferometer.length) return null;
  if (!spec || !spec.on) return { needsDensity: true };
  var chords = pt.interferometer, n = chords.length;
  var nel = new Float64Array(n), bpol = new Float64Array(n),
      ang = new Float64Array(n), lenIn = new Float64Array(n);
  var cFar = (pt['fylite:faraday_constant'] || 0) *
             Math.pow(pt['fylite:laser_wavelength'] || 0, 2);
  var g = geom || chordGeometry(res);
  if (!g) return null;

  for (var k = 0; k < n; k++) {
    var gk = g[k], ne = [], nb = [];
    for (var i = 0; i < gk.keep.length; i++) {
      var d = densityAt(spec, gk.x[i]);
      ne.push(d); nb.push(d * gk.br[i]);
    }
    try {
      nel[k] = chordIntegral(gk, ne);
      bpol[k] = chordIntegral(gk, nb) / 1e19;
    } catch (e2) { return { error: e2.message }; }
    ang[k] = cFar ? bpol[k] * 1e19 * cFar * 2 * 180 / Math.PI : NaN;
    lenIn[k] = gk.inside * gk.ds;
  }
  //: ★the SPEC, not just the sampled profile: the integral evaluates n_e at
  //: arbitrary psi_N along each chord, so a ladder of 24 values is not enough
  //: to reproduce it — anyone checking this number has to be able to build
  //: the same density the page built
  var spec2 = { ne0: spec.ne0, peaking: spec.peaking, zeff: spec.zeff,
                profile: (spec.profile && spec.profile.length)
                  ? Array.prototype.slice.call(spec.profile) : null };
  return { name: chords.map(function (c) { return c.name; }),
           spec: spec2,
           z: chords.map(function (c) { return (c.first_point || {}).z; }),
           nel: nel, nel19: Float64Array.from(nel, function (v) { return v / 1e19; }),
           bpolar: bpol, angleDeg: ang, chordLength: lenIn,
           source: spec.profile && spec.profile.length ? 'imported' : 'parametrised' };
}

// --- the bootstrap current, and the two analytic models side by side -------
//
// ★A reconstruction fits p' and FF'; it does not know how the current is
// SHARED between the ohmic and bootstrap channels, and nothing in the
// magnetics tells it.  What decides that share is n_e and T_e SEPARATELY —
// the bootstrap drive is a pressure gradient carried by trapped particles at
// a collisionality, and collisionality needs a density and a temperature,
// not their product.  So this block runs only when a density profile is
// supplied, and it says which one it used.
//
// ★★T_e is DERIVED, not measured: with `ni = ne` and `Ti = Te`, the fitted
// pressure gives `Te[eV] = p / (2 * ne * e)`.  That is an assumption about
// the ion channel, and it travels with every number below rather than being
// buried — a page that showed a bootstrap profile without saying which
// temperature produced it would be showing a curve nobody can check.
//
// ★The two currents are in DIFFERENT UNITS on purpose.  `redlBootstrap`
// returns |<j.B>|/B0 in A/m^2, which is a current; `neoSauter` returns NEO's
// own normalised `jpar`, which is not.  They are drawn on two panels and
// never subtracted from one another, and the fit's own <j_phi> is a third
// measure again — the difference between <j_phi> and j_bs is NOT J_ohm, and
// this file does not pretend otherwise.

var EV_J = 1.602176634e-19;

/** Linear read of a uniform-x profile at `x`. */
function profileAt(pr, x) {
  var m = pr.length, t = x * (m - 1);
  var k = Math.min(m - 2, Math.max(0, t | 0));
  return pr[k] + (t - k) * (pr[k + 1] - pr[k]);
}

/** n_e on the ladder: an imported profile, or the parametrised shape. */
function densityAt(spec, x) {
  var pr = spec.profile;
  if (pr && pr.length) {
    var m = pr.length, t = x * (m - 1);
    var k = Math.min(m - 2, Math.max(0, t | 0));
    return pr[k] + (t - k) * (pr[k + 1] - pr[k]);
  }
  //: n_e = n_e0 (1 - x^2)^alpha — a SHAPE the user set, not a measurement,
  //: which is why the page labels every number that follows from it
  return spec.ne0 * Math.pow(Math.max(1 - x * x, 0), spec.peaking);
}

// --- T-A9: <j.B> <-> <j_phi>, sigma_neo, and the three curves that add ----
//
// ★★WHAT THIS BLOCK IS FOR, IN ONE SENTENCE: the page could draw a
// bootstrap current and a fitted current and could not subtract them,
// because they are different quantities — `redlBootstrap` returns
// `|<j.B>|/B0` and the reconstruction returns `<j_phi>`.  The note that
// used to stand above `reconBootstrap` said exactly that and stopped there.
//
// The closure is written in the PARALLEL measure and it is the FIT that
// gets converted, not the parts.  The reason is the diamagnetic term: the
// identity is
//
//     <j_phi/R>/<1/R> = [ <j.B> ratio + F p' (1 - ratio) ] / (F <1/R>)
//
// and that `p'` piece belongs to neither the bootstrap nor the ohmic
// channel.  Written the other way round — convert each part and add — the
// pressure gradient is counted once per curve and three curves that look
// right do not sum to the fit.
//
// ★Both sides of the identity are built here from the SAME two fitted
// coefficients, by two different routes:
//
//     <j.B>            = (FF'/mu0 F) <B^2> + p' F
//     <j_phi/R>/<1/R>  = [ p' + (FF'/mu0) <1/R^2> ] / <1/R>
//
// so the kernel's conversion of the first must reproduce the second.  That
// is not a tolerance chosen here; it is an algebraic identity, and the gate
// asserts it at 1e-10.

/**
 * The ladder integral of a toroidal current density -> amperes.
 *
 * `dI/dpsi = <j_phi/R> dV/dpsi / 2pi`, and `jTor` is `<j_phi/R>/<1/R>` —
 * so the `<1/R>` goes back in here.
 *
 * ★`dV/dpsi` from the kernel is a MAGNITUDE (it is `2pi contour R dl /
 * |grad psi|`), so the label step is taken as a magnitude too: whether
 * psi rises or falls outward is a gauge, and a current that changed sign
 * with it would be a gauge bug wearing a physics face.
 *
 * ★The ladder does not reach the axis or the boundary — `surfaceShapes`
 * traces the interior — so the two END SEGMENTS are closed by LINEAR
 * EXTRAPOLATION from the nearest two interior nodes (T-A19).  The old
 * stubs — density pinned to ZERO at the axis and held CONSTANT to the
 * edge — were both wrong in the same direction: `dV/dpsi` is FINITE at
 * the axis (the contour length and |grad psi| vanish together), and the
 * edge density is still growing where the constant stub freezes it.
 * Together they undercounted the fit's own I_p by 3.88 % (377.24 kA
 * against 392.48 kA, measured on the delivered slice) — a deficit that
 * belonged entirely to the ladder's ends, since the conversion identity
 * holds to 1.7e-16.  Extrapolated ends are order-consistent with the
 * trapezoid between the nodes (both are the piecewise-linear model), so
 * the remaining gap shrinks as the ladder is refined — which the gate
 * asserts by comparing this quadrature against itself on every other
 * surface.
 */
function ladderCurrent(jTor, rInv, dvdpsi, xLad, dPsi) {
  var n = jTor.length, dens = new Float64Array(n + 2), xs = new Float64Array(n + 2), k;
  for (k = 0; k < n; k++) {
    dens[k + 1] = jTor[k] * rInv[k] * dvdpsi[k] / (2 * Math.PI);
    xs[k + 1] = xLad[k];
  }
  xs[0] = 0;
  xs[n + 1] = 1;
  //: the linear model of the two nearest nodes, carried to each end —
  //: not a new rule at the ends but the SAME piecewise-linear model the
  //: trapezoid already applies between the nodes
  dens[0] = n > 1
    ? dens[1] + (dens[2] - dens[1]) * (0 - xs[1]) / (xs[2] - xs[1])
    : dens[1];
  dens[n + 1] = n > 1
    ? dens[n] + (dens[n] - dens[n - 1]) * (1 - xs[n]) / (xs[n] - xs[n - 1])
    : dens[n];
  var sum = 0;
  for (k = 1; k < n + 2; k++)
    sum += 0.5 * (dens[k] + dens[k - 1]) * (xs[k] - xs[k - 1]);
  return sum * Math.abs(dPsi);
}

/**
 * The bootstrap / ohmic / total decomposition on the fit's own surfaces.
 *
 * `arr` carries the ladder `reconBootstrap` already built — the same
 * `eps`, `q`, `n_e`, `T_e`, `T_i`, `n_i`, `Z_eff` the bootstrap was
 * evaluated at, so `sigma_neo` and `j_bs` describe one plasma.
 */
function currentClosure(mem, shapes, arr) {
  var res = mem.result, prof = mem.profiles, n = shapes.length;
  if (!prof || !prof.pprime || !mem.q || !mem.q.f) return null;
  //: psi PER RADIAN — the gauge `p'` and `FF'` are written in, and the
  //: gauge `B_pol = |grad psi|/R` needs.  `res.psi` is the FULL flux.
  var scale = 1 / (2 * Math.PI);
  var psiA = res.psiAxis * scale, psiB = res.psiBnd * scale;
  var k;
  var b2 = new Float64Array(n), bt2 = new Float64Array(n),
      fps = new Float64Array(n), rInv = new Float64Array(n),
      rInv2 = new Float64Array(n), dvdpsi = new Float64Array(n),
      dpdpsi = new Float64Array(n), zero = new Float64Array(n),
      psiPr = new Float64Array(n), ffp = new Float64Array(n),
      jTotPar = new Float64Array(n), jPhiDirect = new Float64Array(n);
  for (k = 0; k < n; k++) {
    var xk = shapes[k].x;
    var f = interp1(prof.x, mem.q.f, xk);
    var pp = interp1(prof.x, prof.pprime, xk);
    var ffpk = interp1(prof.x, prof.ffprime, xk);
    ffp[k] = ffpk;
    var fs = fy.surfaceFsa({
      r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz,
      nr: grid.nr, nz: grid.nz, psi: res.psi, poly: shapes[k].poly,
      psiScale: scale, fPsi: f });
    b2[k] = fs.b2; bt2[k] = fs.bTor2; fps[k] = f;
    rInv[k] = fs.rInv; rInv2[k] = fs.rInv2; dvdpsi[k] = fs.dvdpsi;
    dpdpsi[k] = pp;
    psiPr[k] = psiA + xk * (psiB - psiA);
    //: the two routes, from the same two coefficients
    jTotPar[k] = (ffpk / (EV_MU0 * f)) * fs.b2 + pp * f;
    jPhiDirect[k] = (pp + (ffpk / EV_MU0) * fs.rInv2) / fs.rInv;
  }

  //: ★the identity check, in the page's own numbers.  Nothing downstream
  //: needs it — it is here because a conversion that silently disagreed
  //: with the fit it converts would produce three plausible curves.
  var conv = fy.jparbJphi({ b2: b2, bTor2: bt2, fPsi: fps, rInv: rInv,
                            dpdpsi: dpdpsi, jIn: jTotPar,
                            toToroidal: true });
  var identity = 0, amp = 0;
  for (k = 0; k < n; k++) {
    amp = Math.max(amp, Math.abs(jPhiDirect[k]));
    identity = Math.max(identity, Math.abs(conv.j[k] - jPhiDirect[k]));
  }
  identity = amp > 0 ? identity / amp : NaN;

  //: ★★THE SIGN IS THE FIT'S.  `redlBootstrap` returns a MAGNITUDE
  //: (`|<j.B>|/B0`), so it has to be oriented along the current the
  //: equilibrium actually carries before anything is subtracted — a
  //: bootstrap current pointing the wrong way turns「自举 + 欧姆」into
  //: 「欧姆 − 自举」and both curves still look like currents.
  var mid = jTotPar[(n / 2) | 0], sgn = mid < 0 ? -1 : 1;
  var jTot = new Float64Array(n), jBs = new Float64Array(n),
      jOhm = new Float64Array(n), bsPar = new Float64Array(n),
      ohmPar = new Float64Array(n);
  for (k = 0; k < n; k++) {
    jTot[k] = jTotPar[k] / arr.b0;
    jBs[k] = sgn * Math.abs(arr.jBsPar[k]);
    jOhm[k] = jTot[k] - jBs[k];
    bsPar[k] = jBs[k] * arr.b0;
    ohmPar[k] = jOhm[k] * arr.b0;
  }

  //: the three currents, each converted to the toroidal measure with NO
  //: pressure term (that term is the total's), plus the total WITH it
  var cBs = fy.jparbJphi({ b2: b2, bTor2: bt2, fPsi: fps, rInv: rInv,
                           dpdpsi: zero, jIn: bsPar, toToroidal: true });
  var cOhm = fy.jparbJphi({ b2: b2, bTor2: bt2, fPsi: fps, rInv: rInv,
                            dpdpsi: zero, jIn: ohmPar, toToroidal: true });
  var xLad = new Float64Array(n);
  for (k = 0; k < n; k++) xLad[k] = shapes[k].x;
  var dPsi = psiB - psiA;
  var iBs = ladderCurrent(cBs.j, rInv, dvdpsi, xLad, dPsi);
  var iOhm = ladderCurrent(cOhm.j, rInv, dvdpsi, xLad, dPsi);
  var iTot = ladderCurrent(conv.j, rInv, dvdpsi, xLad, dPsi);
  //: ★T-A19's refinement witness: the SAME quadrature on every other
  //: surface.  The end treatment is order-consistent with the interior,
  //: so halving the ladder must widen the gap to the fit's I_p — and the
  //: gate asserts that direction rather than assuming it.
  var xC = [], jC = [], rC = [], dC = [];
  for (k = 0; k < n; k += 2) {
    xC.push(xLad[k]); jC.push(conv.j[k]);
    rC.push(rInv[k]); dC.push(dvdpsi[k]);
  }
  var iTotCoarse = ladderCurrent(jC, rC, dC, xC, dPsi);
  //: the diamagnetic remainder, by subtraction of the two parallel parts
  //: from the total — which is the statement that the decomposition is
  //: complete rather than an assumption that it is
  var iDia = iTot - iBs - iOhm;

  //: ★sigma_neo on the SAME ladder, through the same collisionality
  var sig = fy.sigmaNeo({ eps: arr.eps, q: arr.q, ne: arr.ne, te: arr.te,
                          ti: arr.ti, ni: arr.ni, zeff: arr.zeff,
                          rMaj: arr.rMaj, zIon: 1, vintage: arr.vintage,
                          collisionless: false });
  //: <E.B> = (V_loop/2pi) F <1/R^2>, so a stationary slice implies one
  //: loop voltage per surface — and how far those agree is the closure's
  //: own report card, not a number the page asserts
  var vLoop = new Float64Array(n);
  for (k = 0; k < n; k++)
    vLoop[k] = 2 * Math.PI * ohmPar[k]
      / (sig.sigmaNeo[k] * fps[k] * rInv2[k]);

  //: `<j.B>_bs / <B^2>` — the coefficient a PURE PARALLEL current has in
  //: `j_phi = k F / R`.  It is what the prescribed-current channel needs:
  //: a flux-surface average cannot be written into a cell, and spreading
  //: the average uniformly around the surface would put bootstrap current
  //: on the low-field side that belongs on the high-field side.
  var kBs = new Float64Array(n);
  for (k = 0; k < n; k++) kBs[k] = bsPar[k] / b2[k];

  return {
    x: arr.x, jTot: jTot, jBs: jBs, jOhm: jOhm, kBs: kBs,
    jTotTor: conv.j, jBsTor: cBs.j, jOhmTor: cOhm.j,
    ratio: conv.ratio, b2: b2, bTor2: bt2, rInv: rInv, rInv2: rInv2,
    fPsi: fps, dvdpsi: dvdpsi, dpdpsi: dpdpsi, ffprime: ffp, psiPr: psiPr,
    sigmaNeo: sig.sigmaNeo, sigmaSpitzer: sig.sigmaSpitzer, f33: sig.f33,
    vLoop: vLoop, vintage: arr.vintage,
    iBs: iBs, iOhm: iOhm, iDia: iDia, iTot: iTot,
    iTotCoarse: iTotCoarse,
    fBs: iTot !== 0 ? iBs / iTot : NaN,
    //: the fit's own current beside the ladder's quadrature of it: the
    //: ladder stops short of the axis and short of the boundary, and this
    //: is how much that costs
    ipFitted: mem.ipFitted,
    identity: identity,
    //: what the curves are IN, spelled out, because three arrays with no
    //: unit are three decorations
    unit: 'A/m^2 (<j.B>/B0)', b0: arr.b0,
  };
}

function reconBootstrap(msg, mem) {
  var spec = msg.density;
  if (!spec || !(spec.on)) return null;
  //: ★T-A19: 96 surfaces, not 24.  The ladder integral's remaining gap to
  //: the fit's own I_p is the discrete-ladder-as-continuum error, and it
  //: is the SURFACE COUNT that controls it — measured on the EAST
  //: reference forward field (where sum(cells) = Ip holds exactly by
  //: construction): 24 faces +1.53 %, 48 faces +1.26 %, 96 faces +0.43 %,
  //: while tracing resolution (nTheta 121 vs 241) moves the fourth digit.
  //: The end treatment is a separate, smaller story (see ladderCurrent).
  var nS = 96;
  var shapes = surfaceShapes(mem.raw, nS);
  if (shapes.length < 4) return null;

  var tf = self.FyDevice.tf(M), b0 = Math.abs(tf.b0), rMaj = tf.r0;
  var n = shapes.length;
  var x = new Float64Array(n), eps = new Float64Array(n), q = new Float64Array(n),
      ne = new Float64Array(n), te = new Float64Array(n), ti = new Float64Array(n),
      ni = new Float64Array(n), zeff = new Float64Array(n),
      pTh = new Float64Array(n), iPsi = new Float64Array(n),
      psiBar = new Float64Array(n), kappa = new Float64Array(n),
      delta = new Float64Array(n), rmin = new Float64Array(n),
      r0s = new Float64Array(n);
  var prof = mem.profiles, qp = mem.q;
  //: psi PER RADIAN, which is the gauge the Redl coefficients are written in
  var psiA = mem.result.psiAxis / (2 * Math.PI),
      psiB = mem.result.psiBnd / (2 * Math.PI);

  for (var k = 0; k < n; k++) {
    var sh = shapes[k];
    x[k] = sh.x;
    rmin[k] = sh.a; r0s[k] = sh.r0; kappa[k] = sh.kappa; delta[k] = sh.delta;
    eps[k] = sh.r0 > 0 ? sh.a / sh.r0 : 0;
    q[k] = Math.abs(interp1(qp.x, qp.q, sh.x));
    var p = Math.max(interp1(prof.x, prof.p, sh.x), 1e-3);
    //: ★★THE BOOTSTRAP IS DRIVEN BY THE THERMAL GRADIENT.  `prof.p` is the
    //: FITTED pressure, which is the total the equilibrium carries — so the
    //: declared non-thermal part comes back off here.  Feeding a fast-ion
    //: pressure into a thermal drive is a bootstrap current that is simply
    //: too large, smoothly and without any warning.
    var pd2 = msg.pressure || null;
    var pThX = Math.max(p - extraPressure(pd2, sh.x, p), 1e-3);
    var d = Math.max(densityAt(spec, sh.x), 1e16);
    ne[k] = d; ni[k] = d; zeff[k] = spec.zeff;
    //: a MEASURED T_e wins over the derived one: deriving it from p and n_e
    //: is what you do when the temperature was never measured, not a
    //: correction to apply to one that was
    //: ★and the split is the reader's: `p_th = n_e e (T_e + T_i)` with
    //: `T_i = r T_e`, so a deck run at `T_i/T_e = 0.7` no longer gets a
    //: temperature 15 % too high in every collisionality it feeds
    var rTi = (pd2 && pd2.tite > 0) ? pd2.tite : 1;
    te[k] = (spec.temperature && spec.temperature.length)
      ? Math.max(profileAt(spec.temperature, sh.x), 1)
      : pThX / ((1 + rTi) * d * EV_J);    // eV — the stated assumption
    ti[k] = rTi * te[k];
    pTh[k] = pThX;
    iPsi[k] = interp1(prof.x, mem.q.f, sh.x);
    psiBar[k] = psiA + sh.x * (psiB - psiA);
  }

  var redl;
  try {
    redl = fy.redlBootstrap({ eps: eps, q: q, ne: ne, te: te, ti: ti, ni: ni,
                              zeff: zeff, pTh: pTh, iPsi: iPsi, psiBar: psiBar,
                              rMaj: rMaj, b0: b0, zIon: 1 });
  } catch (e) {
    return { error: e.message };
  }

  // --- the same surfaces through NEO's two analytic vintages --------------
  //
  // Sauter 1999 (vintage 0) and Redl 2021 (vintage 1) are what the delivered
  // figure puts beside its drift-kinetic solve.  Both come back in NEO's
  // normalised units, so they are compared with each other and with nothing
  // else.
  var jS = new Float64Array(n), jR = new Float64Array(n), vintOk = true;
  //: deuterium mass, kg — the surface block is SI
  var MD = 3.3435837724e-27;
  //: s = (r/q) dq/dr with r a LENGTH — forming it on the flux label instead
  //: is a dimensional error that still yields a smooth number
  var shear = new Float64Array(n);
  for (var si = 0; si < n; si++) {
    var i0 = Math.min(Math.max(si, 1), n - 2);
    var dR = rmin[i0 + 1] - rmin[i0 - 1], dQ = q[i0 + 1] - q[i0 - 1];
    shear[si] = (dR !== 0 && q[si] !== 0) ? rmin[si] / q[si] * (dQ / dR) : 0;
  }
  for (k = 0; k < n && vintOk; k++) {
    var aMin = rmin[n - 1];
    var surf = new Float64Array(20);
    var dlnnedr = 0, dlntedr = 0;
    //: gradients on the ladder in SI (per metre), one-sided at the ends
    var k0 = Math.min(Math.max(k, 1), n - 2);
    var dr = rmin[k0 + 1] - rmin[k0 - 1];
    if (dr !== 0) {
      dlnnedr = -(Math.log(ne[k0 + 1]) - Math.log(ne[k0 - 1])) / dr;
      dlntedr = -(Math.log(te[k0 + 1]) - Math.log(te[k0 - 1])) / dr;
    }
    surf[0] = aMin; surf[1] = Math.max(rmin[k], 1e-6);
    surf[2] = r0s[k];
    surf[3] = 0; surf[4] = 0; surf[5] = 0;
    surf[6] = Math.max(q[k], 1e-3);
    //: ★the shear slot, which used to be handed over as zero while the
    //: block below carried the real value — harmless only for as long as
    //: nobody read the geometry the kernel derives from THIS surface
    surf[7] = shear[k];
    surf[8] = kappa[k]; surf[9] = 0;
    surf[10] = delta[k]; surf[11] = 0;
    surf[12] = 0; surf[13] = 0;
    surf[14] = b0; surf[15] = te[k]; surf[16] = ne[k];
    surf[17] = dlnnedr; surf[18] = dlntedr; surf[19] = 0;
    try {
      var inp = fy.neoInputs({
        surf20: surf, signb: -1, signq: 1,
        ions: [{ z: 1, mass: MD, ni: ne[k], ti: ti[k],
                 dlnnidr: dlnnedr, dlntidr: dlntedr }] });
      //: ★★THE BLOCK IS THE KERNEL'S NOW.  `neoSauter` reads the fourteen
      //: slots in `NEO_SAUTER_SLOTS` order, `neoInputs` returns the same
      //: thirteen quantities in `NEO_DECK_GEOMETRY` order, and the two
      //: sequences are NOT the same — building one from the other by
      //: position is the transposition the kernel records as having
      //: produced fluxes 200x out, every number finite and plausible.  This
      //: file used to assemble the block by hand from the surface ladder;
      //: the permutation now lives once, in `fylite.js`, keyed by name.
      var geo14 = fy.neoGeo14(inp.geometry, 17);
      for (var vi = 0; vi < 2; vi++) {
        var r = fy.neoSauter({ z: inp.z, mass: inp.mass, dens: inp.dens,
                               temp: inp.temp, dlnndr: inp.dlnndr,
                               dlntdr: inp.dlntdr, geo14: geo14, nu1: inp.nu1,
                               ipccw: inp.ipccw, btccw: inp.btccw,
                               vintage: vi });
        if (vi === 0) jS[k] = r.jpar; else jR[k] = r.jpar;
      }
    } catch (e) {
      //: the vintages are a COMPARISON, not the answer: if NEO refuses this
      //: surface the physical bootstrap above still stands, and the panel
      //: says the comparison is missing rather than dropping a point into a
      //: line as though it were zero
      vintOk = false;
    }
  }

  //: ★T-A9 — the closure.  Everything above produced a bootstrap current
  //: in a measure the fitted current is not in; this is the block that puts
  //: the two on one axis and names the remainder.
  var closure = null;
  try {
    closure = currentClosure(mem, shapes, {
      x: x, eps: eps, q: q, ne: ne, te: te, ti: ti, ni: ni, zeff: zeff,
      rMaj: rMaj, b0: b0, jBsPar: redl.jBs,
      vintage: (msg.sigmaVintage === 0 || msg.sigmaVintage === 1)
        ? msg.sigmaVintage : 1 });
  } catch (e) {
    closure = { error: e.message };
  }

  return {
    x: x, jBs: redl.jBs, ft: redl.ft, nuEStar: redl.nuEStar,
    closure: closure,
    ne: ne, te: te, q: q, eps: eps,
    vintages: vintOk ? { sauter1999: jS, redl2021: jR } : null,
    source: (spec.profile && spec.profile.length) ? 'imported' : 'parametrised',
    teSource: (spec.temperature && spec.temperature.length)
      ? 'imported' : 'from-pressure',
    zeff: spec.zeff,
    //: what the drive was actually built on, so a reader can see whether the
    //: decomposition did anything
    tiOverTe: (msg.pressure && msg.pressure.tite > 0) ? msg.pressure.tite : 1,
    pThermal: pTh,
    //: the inputs travel with the answer: j_bs is ten profiles and a
    //: normalisation away from anything a reader can see, so a file that
    //: carried only the curve could not be checked against the same kernel
    //: entry from anywhere else
    inputs: { eps: eps, q: q, ni: ni, ti: ti, zeff: zeff, pTh: pTh,
              iPsi: iPsi, psiBar: psiBar, rMaj: rMaj, b0: b0 },
  };
}

/**
 * One channel block through the kernel's self-calibration.
 *
 * `alive` is the fit weight: a channel with no weight took no part, so it
 * has nothing to say about calibration either.
 */
function selfcalOf(meas, model, wts, tol) {
  if (!meas || !model || !meas.length) return null;
  var n = Math.min(meas.length, model.length);
  var alive = new Float64Array(n);
  for (var i = 0; i < n; i++) alive[i] = (wts && wts[i]) ? 1 : 0;
  try {
    var r = fy.selfcalSingle(meas.slice(0, n), model.slice(0, n), alive,
                             tol === undefined ? 0.2 : tol);
    r.dispersion = fy.factorDispersion(r.factors);
    r.tol = tol === undefined ? 0.2 : tol;
    return r;
  } catch (e) {
    return { error: e.message };
  }
}

// --- the vessel, as an unknown ---------------------------------------------
//
// ★★WHAT A FLAT-TOP FIT GETS AWAY WITH AND A RAMP DOES NOT.  Every fit on
// this page treats the external field as exactly known: the coil currents
// are given, the vacuum flux follows, and whatever the loops see beyond that
// is the plasma.  During a current ramp, a vertical excursion or a
// disruption precursor that is false — the vessel carries induced currents
// of its own, and a fit with nowhere to put them puts them in `p'` and
// `FF'`.  The deck describes the vessel (90 elements on EAST, in three
// groups), so those currents can be an unknown instead of an error.
//
// ★THE MODEL IS THREE NUMBERS, NOT NINETY.  Ninety unknowns against
// thirty-five loops is not a fit, it is an interpolation of the noise.  What
// is fitted is one current per GROUP — inner shell, outer shell, passive
// plates — distributed inside a group in proportion to each element's
// conductance (`area / eta`, i.e. a uniform loop voltage across the group).
// That is a MODEL and it is stated: a group whose current is not uniform in
// that sense is not in this family, and the residual will say so.

var vesselCache = null;

/** The vessel groups the deck declares, with their per-element weights. */
function vesselGroups() {
  if (vesselCache) return vesselCache;
  var v = M.vessel || [];
  if (!v.length) return (vesselCache = { names: [], weight: null });
  var names = [], idx = {};
  v.forEach(function (e) {
    var g = e.group || 'vessel';
    if (idx[g] === undefined) { idx[g] = names.length; names.push(g); }
  });
  //: conductance per element, normalised inside its own group: a group's
  //: fitted current is a TOTAL, and how it sits inside the group is the
  //: model above rather than another unknown
  var w = new Float64Array(names.length * v.length), sum = new Float64Array(names.length);
  v.forEach(function (e, i) {
    var g = idx[e.group || 'vessel'];
    var eta = e.eta || M.vessel_resistivity_uohm_m || 1;
    var c = Math.abs(e.w * e.h) / eta;
    w[g * v.length + i] = c;
    sum[g] += c;
  });
  for (var g = 0; g < names.length; g++)
    for (var i = 0; i < v.length; i++)
      if (sum[g] > 0) w[g * v.length + i] /= sum[g];
  vesselCache = { names: names, weight: w, n: v.length };
  return vesselCache;
}

/** Per-group flux at the loops [Wb/rad per A] and on the grid [Wb per A]. */
function vesselResponse() {
  var vg = vesselGroups();
  if (!vg.names.length) return null;
  if (vg.loops) return vg;
  var v = M.vessel, ng = vg.names.length, nl = M.loops.length;
  var els = v.map(function (e) {
    return { r: e.r, z: e.z, w: e.w, h: e.h, a1: e.a1 || 0, a2: e.a2 || 0 };
  });
  var lr = Float64Array.from(M.loops, function (p) { return p[0]; });
  var lz = Float64Array.from(M.loops, function (p) { return p[1]; });
  var atLoops = P.coilPointResponse(fy, els, lr, lz, 3, 3);
  var atGrid = P.coilGridResponse(fy, els, grid, 3, 3);
  var loopsG = new Float64Array(ng * nl), gridG = new Float64Array(ng * NG);
  for (var g = 0; g < ng; g++)
    for (var e = 0; e < v.length; e++) {
      var wgt = vg.weight[g * v.length + e];
      if (!wgt) continue;
      for (var i = 0; i < nl; i++)
        //: ★Wb/rad at the loops, because that is the unit the measurements
        //: and the loop model are in; the grid stays FULL flux, because that
        //: is what `psiExt` is
        loopsG[g * nl + i] += wgt * atLoops.psi[e * nl + i] * MEAS_SCALE;
      for (var c = 0; c < NG; c++)
        gridG[g * NG + c] += wgt * atGrid.psi[e * NG + c];
    }
  vg.loops = loopsG; vg.grid = gridG;
  //: ★AND AT THE PROBES, when the deck has them.  A probe sits centimetres
  //: from the vessel and a flux loop sees it from outside everything, so
  //: whether the vessel is identifiable at all is mostly a question about
  //: this block.  Units are tesla per amp — what the probe rows carry —
  //: with no 2 pi: that factor belongs to the solver's flux scale.
  if (M.probes && M.probes.length) {
    var np = M.probes.length;
    var pr = Float64Array.from(M.probes, function (p) { return p.r; });
    var pz = Float64Array.from(M.probes, function (p) { return p.z; });
    var ang = Float64Array.from(M.probes,
                                function (p) { return p.angle * Math.PI / 180; });
    var atP = fy.elementProbeResponse(els, pr, pz, ang, 3, 3);
    var probesG = new Float64Array(ng * np);
    for (var g2 = 0; g2 < ng; g2++)
      for (var e2 = 0; e2 < v.length; e2++) {
        var wg2 = vg.weight[g2 * v.length + e2];
        if (!wg2) continue;
        for (var p2 = 0; p2 < np; p2++)
          probesG[g2 * np + p2] += wg2 * atP[p2 * v.length + e2];
      }
    vg.probes = probesG;
  }
  return vg;
}

/** The external flux those group currents add, on the grid. */
function vesselPsi(cur) {
  var vg = vesselResponse();
  if (!vg) return null;
  return P.combine(vg.grid, cur, NG);
}

/**
 * The loop signature of each plasma basis coefficient, at the current
 * surfaces.
 *
 * ★`fitted_current` is LINEAR in the coefficients — that is the whole
 * content of the fit — so one unit vector per coefficient gives the design
 * block the loops see.  It is rebuilt per pass because the mask and the
 * surfaces are not fixed: within a pass they are.
 */
function plasmaLoopColumns(res, npp, nff, withProbes) {
  var nc = npp + nff, nl = M.loops.length;
  var pm = withProbes ? probeRows() : null;
  var np = pm ? M.probes.length : 0, nrow = nl + np;
  var mask = P.plasmaMask(grid, res.psi, res.psiAxis, res.psiBnd,
                          M.limiter.r, M.limiter.z, 1);
  var cols = new Float64Array(nc * nrow);
  for (var k = 0; k < nc; k++) {
    var e = new Float64Array(nc);
    e[k] = 1;
    var cur = P.fittedCurrent(grid, res.psi, res.psiAxis, res.psiBnd, e,
                              npp, nff, mask);
    var m = P.loopModel(loopsM, cur, grid, MEAS_SCALE);
    for (var i = 0; i < nl; i++) cols[k * nrow + i] = m[i];
    if (pm) {
      //: the probe rows carry the solver's 2 pi pre-scale, and `loopModel`
      //: applies `meas_scale` on top — so this comes back in tesla, which is
      //: the unit the probe measurements are in
      var mp = P.loopModel(pm, cur, grid, MEAS_SCALE);
      for (i = 0; i < np; i++) cols[k * nrow + nl + i] = mp[i];
    }
  }
  return { cols: cols, nc: nc, nrow: nrow, nLoops: nl, nProbes: np };
}

/**
 * The group currents that best explain what the loops see and the PLASMA
 * CANNOT.
 *
 * ★★THE FIRST VERSION OF THIS DIVERGED, and the reason is worth keeping.
 * It fitted the vessel to the residual left by the plasma fit, added the
 * vessel field to the external flux, re-fitted the plasma, and repeated.
 * The plasma basis can imitate a good part of a vessel field, so it
 * re-absorbed the correction every pass and the residual came back with the
 * same sign: measured on the twin with 12 kA injected, the fitted current
 * grew 15.7 -> 46.8 -> 77.5 kA over one, three and five passes.  An
 * alternating fit between two blocks that can imitate each other does not
 * converge to the joint answer; it walks.
 *
 * What a JOINT least squares would give is reachable without adding
 * unknowns to the kernel's solver — Frisch-Waugh-Lovell: the joint estimate
 * of the vessel block equals the regression of the residualised
 * measurements on the residualised vessel response, where "residualised"
 * means projected orthogonal to the plasma block's own columns.  So both
 * sides are regressed on `plasmaLoopColumns` first, and the vessel is left
 * with exactly what no plasma in this family could have produced.
 *
 * ★The projection is done with the kernel's own solves (D-4): a normal
 * equation written out here would be a second linear algebra.
 */
function fitVessel(inp, mem, msg, rcond) {
  var vg = vesselResponse();
  if (!vg) return null;
  //: ★EVERY MAGNETIC ROW THE FIT WAS GIVEN, not only the loops.  Whether the
  //: vessel can be seen at all is mostly a question about the PROBES: a loop
  //: outside everything sees a shell current as one more contribution to the
  //: same enclosed flux the plasma makes, while a probe sitting centimetres
  //: from that shell sees its own field.  Measured on the twin: with loops
  //: alone 5.6 % of the vessel signature survives being projected out of the
  //: plasma's reach, which is less than the fit's own model error.
  var ng = vg.names.length, nl = inp.nLoops, i, g;
  var useProbes = !!(inp.nProbes && vg.probes);
  var np = useProbes ? inp.nProbes : 0, nrow = nl + np;
  var pc = plasmaLoopColumns(mem.raw, msg.npp, msg.nff, useProbes), nc = pc.nc;
  var w = new Float64Array(nrow);
  for (i = 0; i < nrow; i++) w[i] = inp.wts[i] || 0;
  var A = new Float64Array(nrow * nc);
  for (i = 0; i < nrow; i++)
    for (var k = 0; k < nc; k++) A[i * nc + k] = pc.cols[k * pc.nrow + i];

  /** `y` with everything the plasma block could have explained taken out. */
  function residualise(y) {
    var c = P.ridgeLstsq(A, y, w, nrow, nc, new Float64Array(nc));
    if (!c) return null;
    var out = new Float64Array(nrow);
    for (var r = 0; r < nrow; r++) {
      var v = y[r];
      for (var k2 = 0; k2 < nc; k2++) v -= A[r * nc + k2] * c[k2];
      out[r] = v;
    }
    return out;
  }

  var b = new Float64Array(nrow), modelP = null;
  for (i = 0; i < nl; i++) b[i] = inp.meas[i] - mem.model[i];
  if (useProbes) {
    //: the probe block's model is the same rows the solver was given,
    //: contracted with the fitted current — plasma-only, like its
    //: measurements
    modelP = P.loopModel(probeRows(), mem.fitCur, grid, MEAS_SCALE);
    for (i = 0; i < np; i++) b[nl + i] = inp.meas[nl + i] - modelP[i];
  }
  var bt = residualise(b);
  if (!bt) return { error: 'plasma-projection-singular' };
  var At = new Float64Array(nrow * ng);
  for (g = 0; g < ng; g++) {
    var col = new Float64Array(nrow);
    for (i = 0; i < nl; i++) col[i] = vg.loops[g * nl + i];
    for (i = 0; i < np; i++) col[nl + i] = vg.probes[g * M.probes.length + i];
    var ct = residualise(col);
    if (!ct) return { error: 'plasma-projection-singular' };
    for (i = 0; i < nrow; i++) At[i * ng + g] = w[i] * ct[i];
  }
  var bw = new Float64Array(nrow);
  for (i = 0; i < nrow; i++) bw[i] = w[i] * bt[i];
  //: ★HOW MUCH OF THE VESSEL SURVIVES THE PROJECTION is the answer to "can
  //: these channels see the vessel at all".  The raw block's own singular
  //: values are computed too, and the ratio is reported: a vessel whose
  //: response is 99 % inside what the plasma basis can imitate is not
  //: badly conditioned, it is UNMEASURED — and the two must not read alike.
  var Aw = new Float64Array(nrow * ng);
  for (i = 0; i < nrow; i++)
    for (g = 0; g < ng; g++)
      Aw[i * ng + g] = w[i] * (i < nl ? vg.loops[g * nl + i]
                                      : vg.probes[g * M.probes.length + i - nl]);
  var r2, raw;
  try {
    r2 = fy.svdSolve(At, bw, nrow, ng, rcond === undefined ? 0.05 : rcond, 0);
    raw = fy.svdSolve(Aw, bw, nrow, ng, 1e-12, 0);
  } catch (e) {
    return { error: 'svd-failed: ' + e.message };
  }
  var survive = raw && raw.singular[0] > 0
    ? r2.singular[0] / raw.singular[0] : NaN;
  return { names: vg.names, current: r2.x, kept: r2.kept,
           condition: r2.condition, survive: survive,
           rows: { loops: nl, probes: np },
           singular: Array.prototype.slice.call(r2.singular),
           singularRaw: Array.prototype.slice.call(raw ? raw.singular : []) };
}

// --- a discharge, not a moment ---------------------------------------------
//
// ★★THE AXIS THIS PAGE DID NOT HAVE.  Everything above fits ONE time slice,
// and the first thing anyone does with a real shot is pull the time axis:
// how do I_p, q95, li and the axis position move.  Nothing in the physics
// prevented it — the deck simply carries one slice, and a page written for
// one slice acquires the assumption everywhere.
//
// ★Three sources, and which one it is decides what the traces MEAN:
//   deck      the slices the device document ships (EAST: exactly one)
//   twin      a swept forward solve — SYNTHETIC, and labelled so
//   imported  a time-series document someone else wrote
//
// ★Each slice is a FULL reconstruction, not an interpolation between two.
// That is the expensive answer and the only honest one: a trace of q95 whose
// middle was interpolated is a picture of the interpolation.

function seriesSlice(msg, sl) {
  //: one message per slice: the base request with this slice's own numbers
  //: on top, so a slice cannot silently inherit the previous slice's Ip
  var m = Object.assign({}, msg);
  if (sl.ip !== undefined) m.ip = sl.ip;
  if (sl.ipOverride !== undefined) m.ipOverride = sl.ipOverride;
  if (sl.chan) m.chan = sl.chan;
  if (sl.prof) m.prof = Object.assign({}, msg.prof, sl.prof);
  if (sl.loopMeas) m.loopMeas = sl.loopMeas;
  if (sl.loopMeasTotal) m.loopMeasTotal = sl.loopMeasTotal;
  //: a slice's probes and chords are its own, exactly as its coils are
  if (sl.probeMeas) m.probeFit = Object.assign({}, m.probeFit,
                                               { meas: sl.probeMeas,
                                                 mask: sl.probeWeights });
  if (sl.point) m.pointMeas = { nel19: sl.point.n_e_line19,
                                bpolar: sl.point.bpolar,
                                weightNel: sl.point.weight_nel,
                                weightPol: sl.point.weight_pol };
  if (sl.loopWeights) m.loopWeights = sl.loopWeights;
  //: ★★A PRESSURE PROFILE BELONGS TO ONE MOMENT.  The deck carries the
  //: delivered profile of ONE slice; carrying it across a whole discharge
  //: would constrain a 223 kA ramp with the pressure of a 400 kA flat-top.
  //: Measured on #137985: with the 4 s profile held over all nine slices,
  //: eight of them diverge (`法方程奇异`); without it, six solve.  So a slice
  //: with no pressure of its own is fitted on magnetics alone, and the page
  //: says which slices those were.
  m.kinetic = sl.pressure
    ? Object.assign({}, msg.kinetic, { pressure: sl.pressure })
    : Object.assign({}, msg.kinetic, { on: false });
  m.cmd = 'recon';
  return m;
}

/**
 * Which channel basis a resolved request is fitted in, as a stable token.
 *
 * ★THE WORKER SAYS IT, because the worker is the only place that knows: the
 * page's basis select is one input, the slice's own readings are another, and
 * `seriesSlice` is what settles the two.  A caller that re-derived this from
 * the message it SENT would be reading the question, not the answer — the
 * batch queue's summary table did exactly that for one revision and labelled
 * nine raw-basis deck slices as delivered-basis fits.
 */
function channelBasisOf(msg) {
  if (msg.source === 'twin') return 'synthetic-twin';
  return msg.loopMeasTotal ? 'raw-total-flux' : 'delivered-channel-values';
}

/**
 * Is this "solution" a plasma at all?  Returns why not, or null.
 *
 * ★★A SOLVE THAT RETURNS IS NOT A SOLVE THAT SUCCEEDED.  The series loop
 * counted every slice `reconMember` did not THROW on as solved, and the
 * kernel throws only when its own iteration gives up.  Measured on the twin
 * sweep (4 slices, Ip 320 → 700 kA, otherwise stock): the last two came back
 * with `a` = 0.036 m at R = 2.325 m — a 3.6 cm filament pinned against the
 * outboard limiter — carrying a FITTED current of 215 and 261 MA against the
 * 546 and 700 kA they were constrained to, with chi^2 = 4.0e10 against 145
 * for the two healthy slices.  Every scalar screamed and the page said
 * 「4 片，0 片未解出」.
 *
 * ★★★WHAT IS JUDGED HERE IS THE SOLVE, NOT THE DISCHARGE.  It would be easy
 * to reject on q95 — the bad slices sit at 0.013 — and it would be wrong:
 * that is a prior about which discharges are allowed, and this page exists to
 * reconstruct whatever was actually run.  Both tests below are statements the
 * METHOD makes about itself:
 *
 *   1. THE EQUALITY CONSTRAINT MUST HAVE HELD.  `ip` is imposed as an
 *      equality inside `gsInverseSolve`; `ipFitted` is the same current read
 *      back by integrating the fitted current density over the plasma mask.
 *      They are one quantity computed two ways, so they differ only by grid
 *      quadrature — measured 3.1e-5 relative on the healthy slices.  The
 *      threshold is 0.5, four orders of magnitude looser: this asks whether
 *      the constraint held AT ALL, and does not pretend to judge quadrature.
 *   2. THE BOUNDARY MUST BE A PLASMA, NOT A COLLAPSED COLUMN.  The same
 *      standard the design scenario's gate already applies to its own solves
 *      (「解出来的必须是等离子体而不是一团」), stated against the machine's
 *      own half-width so it carries to any device: a tenth of it.  On EAST
 *      that floor is 0.067 m, against 0.35–0.46 m for the healthy slices and
 *      0.036 m for the filaments — 6-8x clear one way, 0.54x the other.
 *
 * ★ON THIS DECK THE CURRENT TEST IS THE ONE THAT FIRES: the filaments fail it
 * by a factor of 375 before the geometry is looked at.  The second is kept
 * because it catches the other shape of the same failure — a collapsed column
 * that happens to carry the right total current — and because it is asserted
 * positively on every surviving slice, which is where it earns its place.
 *
 * ★BOTH BARS USE IT.  The single reconstruction had the identical hole:
 * measured on the twin at Ip = 700 kA, the page reported 「重构完成」 over
 * a = 0.036 m, q95 = 0.012 and chi^2 = 4.85e10, with the verdict line saying
 * nothing.  Rejecting there means the run reports as failed and the figures
 * stay on the last fit that succeeded — which the verdict now says in words.
 *
 * ★Rejecting by THROWING (in the series loop) is deliberate: the caller's
 * catch already writes the slice into `failed` with its reason, pushes NaN
 * into every trace and — this is the part that would be easy to miss — NaNs
 * the slice's row of the cross-slice calibration.  A 215 MA filament's
 * computed/measured ratios would otherwise poison the table for every channel.
 */
//: how many prior sigmas the coil fit is allowed to move a channel — see
//: the third test in `notAPlasma`
var COIL_PULL_MAX = 5.0;

function notAPlasma(inp, mem) {
  var want = Math.abs(inp.ip), got = Math.abs(mem.ipFitted);
  if (want > 0 && Math.abs(got - want) / want > 0.5)
    return FyI18n.t('recon.reject.ip',
                    { got: (got / 1e6).toPrecision(3),
                      want: (want / 1e3).toFixed(1),
                      times: (got / want).toPrecision(3) });
  var lim = M.limiter.r, lo = Infinity, hi = -Infinity;
  for (var i = 0; i < lim.length; i++) {
    if (lim[i] < lo) lo = lim[i];
    if (lim[i] > hi) hi = lim[i];
  }
  var aMachine = 0.5 * (hi - lo);
  var a = mem.result.shape ? mem.result.shape.a : NaN;
  if (aMachine > 0 && (!isFinite(a) || a < 0.1 * aMachine))
    return FyI18n.t('recon.reject.blob',
                    { a: isFinite(a) ? a.toFixed(3) : '—',
                      pct: isFinite(a) ? (100 * a / aMachine).toFixed(1) : '—',
                      floor: (0.1 * aMachine).toFixed(3) });
  //: ★★THE THIRD STATEMENT, and it exists only because the coil currents
  //: became unknowns (T-A5).  The first two ask whether the fit kept its own
  //: promises about the PLASMA; this one asks whether it kept the reader's
  //: promise about the MACHINE.  A joint fit can always drive its residual
  //: down by moving the coils, and the sigma the reader supplied is the
  //: statement of how far that is allowed to go — five times it is a fit
  //: that stopped believing the calibration it was handed, not a
  //: reconstruction of the shot that ran.  Measured on the nine deck slices
  //: at the default sigmas: 1.04-1.60.
  if (mem.coilPull !== undefined && !(mem.coilPull <= COIL_PULL_MAX))
    return FyI18n.t('recon.reject.coil',
                    { pull: isFinite(mem.coilPull)
                        ? mem.coilPull.toPrecision(3) : '—',
                      cap: COIL_PULL_MAX.toFixed(1) });
  return null;
}

function reconSeriesRun(msg) {
  var t0 = Date.now();
  var slices = msg.slices || [];
  if (!slices.length) {
    post({ type: 'error', where: 'series',
           message: FyI18n.t('ser.no_slices') });
    return;
  }
  var nl = M.loops.length;
  //: ★`coilPull` travels as a per-slice TRACE like every other scalar: a
  //: coil fit that is fine at flat top and straining on the ramp is exactly
  //: the shape of thing a single number for the run would hide.
  var keys = ['ip', 'q0', 'q95', 'li3', 'axisR', 'axisZ', 'span', 'chi2',
              'p0', 'kappa', 'a', 'r0', 'ipFitted', 'coilPull'];
  var out = { type: 'recon_series', time: [], failed: [],
              source: msg.source, synthetic: msg.source === 'twin' };
  keys.forEach(function (k) { out[k] = []; });
  //: (n_slice, n_channel) of computed/measured, which is what the kernel's
  //: cross-slice calibration takes
  var ratio = new Float64Array(slices.length * nl);
  for (var s0 = 0; s0 < slices.length; s0++) {
    var sm = seriesSlice(msg, slices[s0]), inp, mem;
    try {
      inp = reconInputs(sm);
      var kin = reconKinetic(sm, inp, (msg.seed || 12345) + 31 * s0);
      mem = reconMember(sm, inp, kin);
      //: ★a solve that returned is not a solve that succeeded — see
      //: `seriesRejection`.  Thrown rather than branched, so a slice rejected
      //: here travels the SAME path as one the kernel gave up on.
      var why = notAPlasma(inp, mem);
      if (why) throw new Error(why);
    } catch (e) {
      out.failed.push({ slice: s0, why: e.message });
      out.time.push(slices[s0].time);
      keys.forEach(function (k) { out[k].push(NaN); });
      for (var d0 = 0; d0 < nl; d0++) ratio[s0 * nl + d0] = NaN;
      post({ type: 'progress', frac: (s0 + 1) / slices.length });
      continue;
    }
    out.time.push(slices[s0].time);
    out.ip.push(inp.ip);
    out.ipFitted.push(mem.ipFitted);
    out.q0.push(mem.q.q0);
    out.q95.push(mem.q.q95);
    out.li3.push(mem.li3);
    out.axisR.push(mem.result.axisR);
    out.axisZ.push(mem.result.axisZ);
    out.span.push((mem.result.psiAxis - mem.result.psiBnd) / (2 * Math.PI));
    out.chi2.push(mem.chi2);
    out.p0.push(mem.profiles.p[0]);
    out.kappa.push(mem.result.shape ? mem.result.shape.kappa : NaN);
    out.a.push(mem.result.shape ? mem.result.shape.a : NaN);
    out.r0.push(mem.result.shape ? mem.result.shape.r0 : NaN);
    out.coilPull.push(mem.coilPull === undefined ? NaN : mem.coilPull);
    for (var d = 0; d < nl; d++) {
      var meas = inp.meas[d];
      ratio[s0 * nl + d] = (inp.wts[d] && meas !== 0)
        ? mem.model[d] / meas : NaN;
    }
    post({ type: 'progress', frac: (s0 + 1) / slices.length });
  }
  //: ★★THE CROSS-SLICE CALIBRATION, which is the kernel's and which one
  //: slice cannot give: a channel whose factor is steady across a discharge
  //: is miscalibrated, while one that wanders is noisy — and telling those
  //: two apart is the whole reason a shot has more than one slice.
  var alive = new Float64Array(nl).fill(1);
  try {
    var sc = fy.selfcalSlices(ratio, slices.length, nl, alive);
    out.selfcal = { factors: sc.factors, scatter: sc.scatter,
                    slices: sc.slices };
  } catch (e) { out.selfcalError = e.message; }
  out.ms = Date.now() - t0;
  post(out);
}

// --- profile fitting -------------------------------------------------------
//
// ★★THE FRONT END THE KINETIC CONSTRAINT NEVER HAD.  This page's pressure
// rows have always come from a profile someone else already fitted — a
// delivered g-file, or a JSON document this page could import but nothing
// could write.  The step in between, "measured points -> a profile", is the
// one every real analysis starts with, and the kernel has carried it all
// along (`fitting::fit`: shifted-Legendre basis, order chosen by GCV).
//
// ★THE SMOOTHNESS IS A DECLARED ORDER, not a silent default: the fit
// returns which order GCV chose and the whole sweep it chose from, so a
// reader can see whether the choice was sharp or a coin toss.

function profileFitRun(msg) {
  var n = (msg.x || []).length;
  if (!n) { post({ type: 'error', where: 'profile',
                   message: FyI18n.t('prof.no_points') }); return; }
  var t0 = Date.now();
  var r;
  try {
    r = fy.profileFitSweep(Float64Array.from(msg.x), Float64Array.from(msg.y),
                           Float64Array.from(msg.sigma),
                           Math.max(1, Math.min(8, msg.maxOrder | 0)));
  } catch (e) {
    post({ type: 'error', where: 'profile', message: e.message });
    return;
  }
  var nx = 101, curve = fy.profileCurve(r.best.coef, nx);
  var x = new Float64Array(nx);
  for (var i = 0; i < nx; i++) x[i] = i / (nx - 1);
  //: the fitted value AT THE POINTS as well, because a residual is what says
  //: whether the order was right and it cannot be read off a curve
  var at = fy.profileSample(r.best.coef, Float64Array.from(msg.x));
  post({ type: 'profile', quantity: msg.quantity, order: r.best.order,
         coef: Float64Array.from(r.best.coef), sweep: r.sweep,
         chi2PerDof: r.best.chi2PerDof, rss: r.best.rss, n: r.best.N,
         x: x, curve: curve, at: at, ms: Date.now() - t0 });
}

// --- the posterior ---------------------------------------------------------
//
// ★What the error bars are OVER is a choice, and it is the whole meaning of
// the number: here it is the kinetic constraint's own sigma — the pressure
// the fit is told to believe — re-drawn per member, with the magnetics held
// fixed.  That is the experiment "the same shot, with the pressure known
// only to sigma", and it is the one this page has the inputs for.  It is NOT
// a posterior over the magnetics (the loop readings arrive without their
// per-channel sigma), and the page says so rather than letting a reader
// assume the band covers everything.
//
// ★A member that fails to solve is COUNTED, not dropped silently: `nOk` and
// `n` are reported separately, because a posterior over the members that
// happened to converge is biased towards the easy corner of the space.

/** The sources this posterior draws from, named and quantified. */
function mcSources(msg) {
  var mc = msg.mc || {}, out = [];
  //: ★listed even at sigma zero — that run is the CONTROL that shows the
  //: spread comes from this input, and a file that omitted the source would
  //: describe an ensemble drawn over nothing
  if (msg.kinetic && msg.kinetic.on)
    out.push({ source: 'kinetic_pressure_sigma',
               relative: msg.kinetic.noise || 0 });
  if (+mc.loops > 0)
    out.push({ source: 'flux_loop_sigma', relative: +mc.loops,
               //: ★an ASSUMPTION, and it says so in the file: the deck
               //: carries fit weights, not per-channel sigmas
               basis: 'assumed-uniform-relative-to-max-reading' });
  if (+mc.coils > 0)
    out.push({ source: 'coil_current_sigma', relative: +mc.coils,
               basis: 'assumed-uniform-relative-per-channel' });
  if (mc.basis)
    out.push({ source: 'basis_order', relative: null,
               basis: 'uniform-over-neighbouring-orders-clipped-1-3' });
  return out;
}

/** mean / sigma / percentiles of one scalar across members. */
function ensembleStats(v) {
  var n = v.length;
  if (!n) return null;
  var mean = 0, i;
  for (i = 0; i < n; i++) mean += v[i];
  mean /= n;
  var s2 = 0;
  for (i = 0; i < n; i++) s2 += (v[i] - mean) * (v[i] - mean);
  //: sample sigma (n-1): the members are draws, not the population
  var sigma = n > 1 ? Math.sqrt(s2 / (n - 1)) : 0;
  var sorted = Array.prototype.slice.call(v).sort(function (a, b) { return a - b; });
  function pct(f) {
    var t = f * (n - 1), k = Math.min(n - 2, Math.max(0, Math.floor(t)));
    return n === 1 ? sorted[0] : sorted[k] + (t - k) * (sorted[k + 1] - sorted[k]);
  }
  return { mean: mean, sigma: sigma, p16: pct(0.16), p50: pct(0.50),
           p84: pct(0.84), min: sorted[0], max: sorted[n - 1], n: n };
}

/** Pointwise mean and +-1 sigma of a family of curves sampled on one x. */
function ensembleBand(curves) {
  if (!curves.length) return null;
  var n = curves[0].length, k = curves.length;
  var mean = new Float64Array(n), lo = new Float64Array(n), hi = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    var m = 0, j;
    for (j = 0; j < k; j++) m += curves[j][i];
    m /= k;
    var s2 = 0;
    for (j = 0; j < k; j++) s2 += (curves[j][i] - m) * (curves[j][i] - m);
    var sd = k > 1 ? Math.sqrt(s2 / (k - 1)) : 0;
    mean[i] = m; lo[i] = m - sd; hi[i] = m + sd;
  }
  return { mean: mean, lo: lo, hi: hi };
}

/**
 * One member's inputs: the base block with the sources the reader asked to
 * vary re-drawn on this member's own stream.
 *
 * ★ONE STREAM PER SOURCE, seeded apart.  Switching the coil source on must
 * not change which magnetics noise the members got — otherwise two runs that
 * differ by one checkbox differ everywhere, and no source can be attributed
 * anything.  The pressure keeps the stream it always had (`seed` itself), so
 * a posterior over pressure alone reproduces the ensembles this page drew
 * before the other three sources existed.
 */
function mcMember(msg, inp, seed) {
  var mc = msg.mc || {}, out = inp, i;
  var relL = +mc.loops || 0, relC = +mc.coils || 0;
  if (relL > 0) {
    //: the perturbation is relative to the LARGEST reading, not to each
    //: channel's own value: a loop that happens to read near zero would
    //: otherwise be treated as the best-measured channel on the machine
    var amp = 0;
    for (i = 0; i < inp.nLoops; i++) amp = Math.max(amp, Math.abs(inp.meas[i]));
    var gl = rng(seed + 7717);
    var meas = Float64Array.from(inp.meas);
    for (i = 0; i < inp.nLoops; i++) meas[i] += relL * amp * gl();
    out = Object.create(out); out.meas = meas;
  }
  if (relC > 0) {
    //: ★the coil currents are an INPUT the fit treats as exact, and their
    //: calibration is not.  Perturbing them here propagates that the only
    //: way this solver allows: the vacuum field is rebuilt per member, so
    //: the plasma has to explain the loops against a different external
    //: flux.
    var gc = rng(seed + 3313);
    var chan = Float64Array.from(msg.chan);
    for (i = 0; i < chan.length; i++) chan[i] *= (1 + relC * gc());
    out = Object.create(out);
    out.psiExt = psiExtOf(chan);
    out.chanDrawn = chan;
  }
  return out;
}

/** The basis orders for one member, when the reader varies them too. */
function mcBasis(msg, seed) {
  if (!(msg.mc && msg.mc.basis)) return { npp: msg.npp, nff: msg.nff };
  //: ★uniform over the neighbouring orders, clipped to what the page offers.
  //: The basis is a STRUCTURAL choice, not a measurement error, so this
  //: spread answers "how much of the answer is my truncation" — a different
  //: question from the other three, and labelled as such in the file.
  var g = rng(seed + 5519);
  //: ★UNIFORM over {n0-1, n0, n0+1}, built from the same gaussian stream the
  //: other sources use: for a standard normal `P(|g| < 0.4307) = 1/3`
  //: exactly, and the remaining two thirds split evenly by sign.  One
  //: generator for the whole worker is worth more than a second one whose
  //: distribution has to be trusted separately.
  var pick = function (n0) {
    var v = g();
    var d = Math.abs(v) < 0.4307 ? 0 : (v > 0 ? 1 : -1);
    return Math.min(3, Math.max(1, n0 + d));
  };
  return { npp: pick(msg.npp), nff: pick(msg.nff) };
}

function reconMcRun(msg0) {
  var t0 = Date.now();
  //: ★THE SAME SLICE RESOLUTION AS THE SINGLE FIT — see `atSlice`.  Without
  //: this the band belonged to the reference instant while the figures under
  //: it belonged to the picked one (T-A16).
  var msg = atSlice(msg0);
  var nWant = Math.max(2, Math.min(64, msg.members | 0));
  var inp;
  //: ★★AND THE REFUSAL MOVES HERE WITH IT.  The page checks its own switches
  //: before sending, which is the right guard for the question it asked; but
  //: a slice can REMOVE a source after the fact — a slice with no pressure
  //: measured at its own moment is fitted on magnetics alone (`seriesSlice`),
  //: so 「压强约束 σ」 ticked on the page draws nothing at all there.  Every
  //: member would then be the identical fit and the table would print ± 0,
  //: which reads as certainty.  Only the resolved message knows, so it is the
  //: one that says no.
  if (!mcSources(msg).length) {
    post({ type: 'error', where: 'mc',
           message: FyI18n.t('recon.mc.novaried') });
    return;
  }
  try { inp = reconInputs(msg); }
  catch (e) { post({ type: 'error', where: 'truth', message: e.message }); return; }

  var keys = ['q0', 'q95', 'ip', 'p0', 'li3', 'chi2', 'axisR', 'axisZ',
              'psiSpan', 'npp', 'nff'],
      acc = {}, qc = [], pc = [], xq = null, xp = null, failed = [];
  keys.forEach(function (k) { acc[k] = []; });

  for (var i = 0; i < nWant; i++) {
    //: the seed is the member index on top of the run's own seed, so a
    //: posterior is reproducible and two runs at the same seed are the same
    //: ensemble — an error bar that moved because it was re-rolled would be
    //: indistinguishable from one that moved because the input changed
    var seed = (msg.seed || 12345) + 101 * (i + 1);
    var inpI = mcMember(msg, inp, seed);
    var kin = reconKinetic(msg, inpI, seed);
    var basis = mcBasis(msg, seed);
    var msgI = basis.npp === msg.npp && basis.nff === msg.nff ? msg
      : Object.assign({}, msg, { npp: basis.npp, nff: basis.nff });
    var mem;
    try { mem = reconMember(msgI, inpI, kin); }
    catch (e) { failed.push({ member: i, why: e.message }); continue; }
    acc.npp.push(basis.npp);
    acc.nff.push(basis.nff);
    acc.q0.push(mem.q.q0);
    acc.q95.push(mem.q.q95);
    acc.ip.push(mem.ipFitted);
    acc.p0.push(mem.profiles.p[0]);
    acc.li3.push(mem.li3);
    acc.chi2.push(mem.chi2);
    acc.axisR.push(mem.result.axisR);
    acc.axisZ.push(mem.result.axisZ);
    acc.psiSpan.push((mem.result.psiAxis - mem.result.psiBnd) / (2 * Math.PI));
    if (!xq) { xq = mem.q.x; xp = mem.profiles.x; }
    qc.push(mem.q.q);
    pc.push(mem.profiles.p);
    post({ type: 'progress', frac: (i + 1) / nWant });
  }

  var stats = {};
  keys.forEach(function (k) { stats[k] = ensembleStats(acc[k]); });
  //: ★the members travel with the summary.  A sigma whose members cannot be
  //: seen is a number nobody downstream can check, and checking it is the
  //: only thing that separates an error bar from a decoration.
  post({ type: 'recon_mc', n: nWant, nOk: qc.length, failed: failed,
         members: acc,
         seed: msg.seed || 12345,
         sigmaP: msg.kinetic && msg.kinetic.on ? (msg.kinetic.noise || 0) : 0,
         //: ★WHAT WAS VARIED, as a list rather than as a sentence in the
         //: page's prose.  A sigma in a file whose sources cannot be read
         //: back is a number nobody downstream can interpret, and "the
         //: error bar" is the single most re-quoted number a page produces.
         varied: mcSources(msg),
         stats: stats,
         qBand: xq ? { x: xq, band: ensembleBand(qc) } : null,
         pBand: xp ? { x: xp, band: ensembleBand(pc) } : null,
         ms: Date.now() - t0 });
}

// --- L0: prescribed zero-dimensional discharge -----------------------------

/**
 * One pass over a prescribed discharge (FYL-DESIGN-05).
 *
 * The waveforms are built by the page and travel as arrays: the kernel
 * decides what follows from them physically, not what a ramp looks like.
 * The whole trace is one call — 0-D is cheaper than a single GS solve, so
 * there is no reason to slice it.
 */
/**
 * The plan for `code/zerod` off a page message: the bound waveforms (the
 * page's `t / ip / ne0 / te0 / pInj` on SUMMARY rows), the ten parameters as
 * settings, the geometry and the phase table when the criteria need them.
 *
 * ★★FYL-DESIGN-16 K-3 (2026-09-05, the sixth tool to sink): the four 0-D
 * commands below used to compose eight flat exports here — the evaluation,
 * then `zerodCriteria` (averages · stored energy · limits · loop voltage ·
 * flux budget · P_LH per instant), the predictive tier, the flux account at a
 * solved l_i, the Monte-Carlo sweep.  They are `case.rs::zerod_case` now, one
 * code with a `stage`; this worker builds the plan and reshapes the record
 * into the answers the page already reads.
 */
function zerodPlan(msg, extra) {
  var par = msg.par || [];
  var settings = {
    tite: par[0], pn: par[1], pt: par[2], edge_frac: par[3], r0: par[4], a: par[5],
    kappa: par[6], zeff: par[7], li: par[8], dtf: par[9],
    n_rho: (msg.rho && msg.rho.length) || 41,
    bt: Math.abs(self.FyDevice.tf(M).b0),
  };
  if (msg.geom) { settings.r0 = msg.geom.r0; settings.a = msg.geom.a; settings.kappa = msg.geom.kappa; }
  if (msg.phases && msg.phases.length === 4) {
    settings.t_bd = msg.phases[0]; settings.t_ru = msg.phases[1];
    settings.t_ft = msg.phases[2]; settings.t_end = msg.phases[3];
  }
  if (msg.li !== undefined) settings.li = msg.li;
  if (msg.phiAvail !== undefined) settings.phi_avail = msg.phiAvail;
  var k;
  for (k in (extra || {})) if (extra.hasOwnProperty(k)) settings[k] = extra[k];
  var summary = { time: Array.from(msg.t) };
  if (msg.ip) summary.global_quantities = { ip: { value: Array.from(msg.ip) } };
  if (msg.ne0 || msg.te0) {
    summary.local = { magnetic_axis: {} };
    if (msg.ne0) summary.local.magnetic_axis.n_e = { value: Array.from(msg.ne0) };
    //: keV on the page, eV on the wire
    if (msg.te0) summary.local.magnetic_axis.t_e = { value: Array.from(msg.te0, function (v) { return v * 1e3; }) };
  }
  var pAux = msg.pInj || msg.pAux;
  if (pAux) summary.heating_current_drive = { power_additional: { value: Array.from(pAux) } };
  if (msg.vLoop) {
    summary.global_quantities = summary.global_quantities || {};
    summary.global_quantities.v_loop = { value: Array.from(msg.vLoop) };
  }
  return { settings: settings, inputs: { summary: summary } };
}

/** The record's summary rows as the page's `tr` object. */
function zerodTraces(rec, nt, nr) {
  var sm = rec.fields.summary, cp = rec.fields.core_profiles;
  var pAlpha = Float64Array.from(sm.fusion.power.value.data);
  var pNeu = sm.fusion.neutron_power_total.value.data;
  var pFus = new Float64Array(nt);
  for (var k = 0; k < nt; k++) pFus[k] = pAlpha[k] + pNeu[k];
  var kev = function (a) { return Float64Array.from(a, function (v) { return v / 1e3; }); };
  return { vLoop: Float64Array.from(sm.global_quantities.v_loop.value.data), pFus: pFus,
           pAlpha: pAlpha, q: Float64Array.from(sm.global_quantities.fusion_gain.value.data),
           ne: fieldFlat(rec, 'core_profiles').length ? Float64Array.from([].concat.apply([], cp.profiles_1d.electrons.density.data)) : new Float64Array(nt * nr),
           te: kev([].concat.apply([], cp.profiles_1d.electrons.temperature.data)),
           ti: kev([].concat.apply([], cp.profiles_1d.t_i_average.data)),
           volume: rec.facts.volume.value };
}

function zerodFluxOf(rec) {
  var F = function (k) { return rec.facts[k] ? rec.facts[k].value : null; };
  if (F('flux_phi_ind') === null) return null;
  var ts = F('flux_t_sustain');
  return { phiInd: F('flux_phi_ind'), phiResRamp: F('flux_phi_res_ramp'), phiRamp: F('flux_phi_ramp'),
           phiConsumed: F('flux_phi_consumed'), vFlattop: F('flux_v_flattop'), lP: F('flux_l_p'),
           tSustain: ts < 0 ? null : ts };
}

function zerodRun(msg) {
  var t0 = Date.now();
  var rec;
  try { rec = fy.complete('code/zerod', zerodPlan(msg, { criteria: 1 })); }
  catch (e) { post({ type: 'error', where: 'zerod', message: e.message }); return; }
  var nt = msg.t.length, nr = msg.rho.length;
  var tr = zerodTraces(rec, nt, nr);
  var C = function (k) { return Array.from(rec.fields['criteria_' + k].data); };
  var limits = { neBar: C('ne_bar'), fGw: C('f_greenwald'), nGw: C('n_greenwald'), qCyl: C('q_cyl'),
                 wTh: C('w_th'), betaT: C('beta_t'), betaP: C('beta_p'), betaN: C('beta_n'),
                 fTroyon: C('f_troyon'), pOhm: C('p_ohm'), pHeat: C('p_heat'), pLH: C('p_lh'),
                 flux: zerodFluxOf(rec) };
  post({ type: 'zerod', result: tr, nt: nt, nr: nr, limits: limits, ms: Date.now() - t0 });
}

/**
 * The flux account again, at an internal inductance somebody else solved.
 *
 * ★T-D10.  The 0-D account charges the inductive flux against a STATED
 * assumption, l_i = 0.9, because a zero-dimensional layer has no
 * current-diffusion solve to produce one.  The design bar on the same page
 * solves an equilibrium that reports l_i(3) — measured 1.491 on EAST, 66 %
 * away — and the two were a bar and 2400 px apart.  This recomputes the
 * account at the solved value so the reader can see what the assumption is
 * worth, and it is a SECOND answer beside the first: the assumption is not
 * replaced, because a 0-D account quietly wearing a solved l_i would look
 * like it had computed the current diffusion it explicitly does not.
 */
function zerodFluxRun(msg) {
  var t0 = Date.now();
  var rec;
  try {
    rec = fy.complete('code/zerod', { settings: { stage: 'flux', t_bd: msg.phases[0], t_ru: msg.phases[1],
                                                  t_ft: msg.phases[2], t_end: msg.phases[3], r0: msg.r0, a: msg.a,
                                                  li: msg.li, phi_avail: msg.phiAvail || 0 },
                                      inputs: { summary: { time: Array.from(msg.t),
                                                           global_quantities: { ip: { value: Array.from(msg.ip) },
                                                                                v_loop: { value: Array.from(msg.vLoop) } } } } });
  } catch (e) { post({ type: 'error', where: 'zerodflux', message: e.message }); return; }
  post({ type: 'zerodflux', result: zerodFluxOf(rec), li: msg.li, ms: Date.now() - t0 });
}

/**
 * TIER B (FYL-DESIGN-05 §3 档 B) — the predictive pass.
 *
 * Kept a SEPARATE command from `zerod` rather than a flag on it, so that
 * nothing can produce a tier-B number while a caller believes it asked for
 * tier A — and the kernel's own record says `predicted` beside its answer.
 */
function zerodPredictRun(msg) {
  var t0 = Date.now();
  var pred = msg.pred || [0, 1, 2.5, Math.abs(self.FyDevice.tf(M).b0), 0];
  var rec;
  try {
    rec = fy.complete('code/zerod', zerodPlan(msg, { stage: 'predict', tau_law: pred[0], hfac: pred[1],
                                                       meff: pred[2], bt: pred[3], w0: pred[4] }));
  } catch (e) { post({ type: 'error', where: 'zerodb', message: e.message }); return; }
  var P = function (k) { return Float64Array.from(rec.fields['prediction_' + k].data); };
  var tr = { wTh: P('w_th'), tauE: P('tau_e'), te0: P('te0'), pOhm: P('p_ohm'), pAlpha: P('p_alpha'),
             pHeat: P('p_heat'), pLH: P('p_lh'), balance: P('balance') };
  post({ type: 'zerodb', result: tr, nt: msg.t.length, ms: Date.now() - t0 });
}

/**
 * Monte-Carlo over a 0-D scenario (FYL-DESIGN-04 §6.5 候选五).
 *
 * ★This capability is judged `○` for the reconstruction tier in §3.5 — a
 * thousand reconstructions is seventeen minutes.  On the 0-D tier the SAME
 * capability is `●`: a thousand evaluations is seconds.  The verdict was
 * given per capability while the cost is per fidelity tier.
 *
 * The samples arrive already built.  Deciding what a perturbed waveform
 * looks like is the page's job (FYL-DESIGN-05 §4); what follows from it is
 * the kernel's (`stage: uq`).  Only STATISTICS come back — returning a
 * thousand traces would cost more in transfer than the whole sweep costs in
 * arithmetic.
 */
function zerodMonteCarlo(msg) {
  var t0 = Date.now();
  var n = msg.nSample, nt = msg.nt, nr = msg.rho.length;
  var rows = function (a, w) {
    var out = [];
    for (var s = 0; s < n; s++) out.push(Array.from(a.subarray(s * w, (s + 1) * w)));
    return out;
  };
  var plan = { settings: { stage: 'uq', n_sample: n, slice: msg.slice, n_rho: nr,
                           tite: msg.par[0], pn: msg.par[1], pt: msg.par[2], edge_frac: msg.par[3],
                           r0: msg.par[4], a: msg.par[5], kappa: msg.par[6], zeff: msg.par[7],
                           li: msg.par[8], dtf: msg.par[9] },
               inputs: { summary: { time: Array.from(msg.t), global_quantities: { ip: { value: Array.from(msg.ip.subarray(0, nt)) } } },
                         uq: { 'fylite:sample_ip': rows(msg.ip, nt), 'fylite:sample_ne_axis': rows(msg.ne0, nt),
                               'fylite:sample_te_axis': rows(msg.te0, nt), 'fylite:sample_p_aux': rows(msg.pInj, nt),
                               'fylite:sample_params': rows(msg.par, 10) } } };
  var rec;
  try { rec = fy.complete('code/zerod', plan); }
  catch (e) { post({ type: 'error', where: 'zerodmc', message: e.message }); return; }
  var stat = function (k) {
    var r = rec.fields['uq_' + k].data;
    if (!r[0]) return { n: 0, dropped: r[1] };
    return { n: r[0], dropped: r[1], mean: r[2], p05: r[3], p25: r[4], p50: r[5], p75: r[6], p95: r[7],
             min: r[8], max: r[9] };
  };
  var stats = { pFus: stat('p_fus'), q: stat('q'), vLoop: stat('v_loop'), pAlpha: stat('p_alpha') };
  post({ type: 'zerodmc', stats: stats, n: n, ms: Date.now() - t0,
         samples: { pFus: Float64Array.from(rec.fields.uq_samples_p_fus.data),
                    q: Float64Array.from(rec.fields.uq_samples_q.data) } });
}

/**
 * Order statistics of a sample.
 *
 * ★Percentiles, not mean ± sigma: these outputs are NOT symmetric — P_fus
 * goes as <sigma v> which is steeply non-linear in temperature, so a
 * symmetric band around the mean would claim a lower bound the samples never
 * visit.  NaNs (Q with nothing injected) are dropped, and how many were
 * dropped is reported rather than absorbed.
 */
function summariseSamples(a) {
  var v = Array.prototype.filter.call(a, isFinite).sort(function (x, y) {
    return x - y;
  });
  if (!v.length) return { n: 0, dropped: a.length };
  var at = function (p) {
    var i = p * (v.length - 1), lo = Math.floor(i), hi = Math.ceil(i);
    return v[lo] + (v[hi] - v[lo]) * (i - lo);
  };
  var mean = 0;
  for (var i = 0; i < v.length; i++) mean += v[i];
  return { n: v.length, dropped: a.length - v.length, mean: mean / v.length,
           p05: at(0.05), p25: at(0.25), p50: at(0.50), p75: at(0.75),
           p95: at(0.95), min: v[0], max: v[v.length - 1] };
}

// --- the turbulence closure (TGLF), loaded on demand ------------------------

//: the SECOND module, and the reason the kernel was split in two: the
//: turbulence closure of the modelling page's 1.5-D stage is its only
//: consumer, and every other page would otherwise have paid 323 KB for it at
//: startup.  ★It is fetched on FIRST USE (`transportTurb`), so a reader who
//: never switches the closure to 湍流 never downloads it.
var tglf = null;

/**
 * The pressure-gradient scale length the saturation rules take, built the
 * way the source builds it: a density-weighted sum over species, then
 * clamped.  The clamp is the source's (`RLNP_CUTOFF`, 18 above and 4
 * below) and is reproduced rather than dropped — it is what keeps a steep
 * deck from driving the rule outside where it was fitted.
 */
function dlnpdr(sp) {
  var ptot = 0, grad = 0;
  for (var i = 0; i < sp.as.length; i++) {
    ptot += sp.as[i] * sp.taus[i];
    grad += sp.as[i] * sp.taus[i] * (sp.rlns[i] + sp.rlts[i]);
  }
  var v = sp.miller14[1] * grad / Math.max(ptot, 0.01);
  return Math.max(Math.min(v, sp.rlnpCutoff), 4.0);
}

/**
 * The turbulent tier: a TGLF-derived diffusivity driving the transport
 * solve, on an OUTER loop.
 *
 * ★★Why this one command exists at all, when the 1.5D page runs its other
 * three tiers on the main thread and says so.  Those cost microseconds, and
 * a worker round-trip would cost more than the solve.  This one costs
 * SECONDS — a TGLF evaluation is ~25 ms per (radius, wavenumber) — so the
 * same reasoning that keeps the others on the main thread moves this one
 * off it.  The rule was never "the main thread is faster"; it was "put the
 * work where it does not make the page stop answering".
 *
 * ★The closure is evaluated OUTSIDE the Picard loop, and the kernel names
 * that arrangement rather than hiding it (`model = 3`, given chi).  A
 * turbulent closure inside the loop is about a minute per round; frozen and
 * re-evaluated on the outer loop it is seconds.  Anchored natively in
 * `tests/test_transport_given_closure.py`: at the fixed point the two
 * arrangements agree to machine precision.
 *
 * ★The two channels are SUMMED — neoclassical is a floor, turbulence sits
 * on top — and the sum is formed here, in the open, rather than inside the
 * kernel where a reader could not see which channels were in it.
 */
/**
 * A rectangular sub-grid that tightly bounds the last closed surface.
 *
 * ★Expanded by a margin and snapped to grid indices, because the fixed
 * solve needs its Dirichlet border OUTSIDE the plasma: with the border on
 * the surface itself the source region would be the whole box and the
 * normalisation would have nowhere to end.
 */
function evPlasmaBox(eq, margin) {
  if (!eq.lcfs || !eq.lcfs.length) return null;
  var rMin = Infinity, rMax = -Infinity, zMin = Infinity, zMax = -Infinity;
  for (var k = 0; k + 1 < eq.lcfs.length; k += 2) {
    var rr = eq.lcfs[k], zz = eq.lcfs[k + 1];
    if (!isFinite(rr) || !isFinite(zz)) continue;
    if (rr < rMin) rMin = rr; if (rr > rMax) rMax = rr;
    if (zz < zMin) zMin = zz; if (zz > zMax) zMax = zz;
  }
  if (!(rMax > rMin) || !(zMax > zMin)) return null;
  var m = margin === undefined ? 0.15 : margin;
  var dR = (rMax - rMin) * m, dZ = (zMax - zMin) * m;
  var i0 = Math.max(0, Math.floor((rMin - dR - grid.r[0]) / grid.dr));
  var i1 = Math.min(grid.nr - 1, Math.ceil((rMax + dR - grid.r[0]) / grid.dr));
  var j0 = Math.max(0, Math.floor((zMin - dZ - grid.z[0]) / grid.dz));
  var j1 = Math.min(grid.nz - 1, Math.ceil((zMax + dZ - grid.z[0]) / grid.dz));
  if (i1 - i0 < 6 || j1 - j0 < 6) return null;
  var nr = i1 - i0 + 1, nz = j1 - j0 + 1;
  var r = new Float64Array(nr), z = new Float64Array(nz);
  for (var i = 0; i < nr; i++) r[i] = grid.r[i0 + i];
  for (var j = 0; j < nz; j++) z[j] = grid.z[j0 + j];
  return { i0: i0, j0: j0, nr: nr, nz: nz, r: r, z: z };
}

/** One field restricted to that box, row-major over (R, Z). */
function evSubField(psi, box) {
  var out = new Float64Array(box.nr * box.nz);
  for (var i = 0; i < box.nr; i++)
    for (var j = 0; j < box.nz; j++)
      out[i * box.nz + j] = psi[(box.i0 + i) * grid.nz + (box.j0 + j)];
  return out;
}

/**
 * The FIXED-BOUNDARY PICARD, on a sub-box, in this app's gauge — one call.
 *
 * ★★THE LOOP IS IN THE KERNEL NOW (T-M7), and what moved is the whole of
 * it: the axis rule, the flood fill, the source assembly and the Picard.
 * `fylite_rs_gs_fixed_box` takes the two rules this page had to keep in
 * JavaScript — an axis searched inside a dilation of the previous plasma
 * ("the axis is a continuous object; it does not teleport") and a plasma
 * taken by CONNECTIVITY rather than by the threshold `0 <= psibar < 1` —
 * because `gs_fixed_solve`, the entry that existed, searched the whole
 * rectangle and took the threshold set.  Both of ITS rules are right on a
 * machine-sized grid and wrong on a box cut around one plasma: the box's
 * own outboard corner is farther from psi_b than the axis is (measured on
 * EAST: axis +0.774 Wb against a corner at -0.916 Wb), so the search took
 * the corner and the source region became an annulus OUTSIDE the
 * separatrix; the threshold rule also admits a diverted plasma's private
 * flux region, which is above psi_b and is not plasma.  That, and not a fit
 * or a noisy FF', is what "I_p 129 kA, axis at (2.400, 0.656)" was.
 *
 * ★★What is left here is the CALL and the refusals, and that is the point:
 * the numbers below are the same numbers to the last bit — the entry was
 * written against this loop, spelling for spelling, and `validate-evolve`'s
 * 定形边界回灌 section is what says so.  Moving work is not a licence to
 * move an answer.
 *
 * ★★ONE GAUGE, stated once.  `psi` is this app's TOTAL flux (Wb)
 * everywhere, exactly as `gs_free_solve` produced it, so the equation
 * solved is the free solver's own:
 *
 *     Delta* psi = -2 pi mu0 R j_phi,   j_phi = R p' + FF'/(mu0 R)
 *
 * with p' and FF' taken against psi PER RADIAN — the gauge `analytic_truth`
 * reports them in and the gauge `qProfile` consumes.  `gauge: 2 pi` is how
 * that is said to the kernel, and no conversion crosses any boundary of
 * this function.  The version this replaces needed one and got it wrong: it
 * handed `gs_fixed_solve` (an equation in psi per radian) a field in Wb
 * together with derivatives taken against Wb, leaving its source short by
 * 4 pi^2 — not by 2 pi, which is why "the current is not out by 2 pi" did
 * not clear it.
 *
 * ★★AND THE PROFILES ARE GIVEN AGAINST PSIBAR, not against psi.  `source`
 * carries `dp/dpsibar` [Pa] and `d(F^2/2)/dpsibar` [T^2 m^2] — what the
 * transport determines is the pressure at a normalised flux, and the flux
 * SPAN is part of what this solve finds.  Handing the loop `dp/dpsi`
 * computed with the span the free solve happened to have would fix the
 * pressure to a span the answer does not have: measured on EAST, a
 * refinement that deepened the well by 36 % came back holding 36 % more
 * pressure than the march ever computed, and reported the beta_p to match.
 * The kernel divides by the CURRENT span, which is also what makes the
 * current self-limiting — a deeper well is a smaller dp/dpsi.
 *
 * The two shapes `source` takes are not interchangeable and both are used:
 * the zero test's p'/FF' are a TABLE (201 points of the kernel's own shape
 * function) with a span scale applied to the evaluated value, and the
 * refinement's are the monomial COEFFICIENTS it actually ran on, evaluated
 * as a polynomial.  A reader re-solving this box from the session file gets
 * the same source to the last bit rather than the same source plus an
 * interpolation of it.  (Measured: a 41-point linear table of the same
 * cubic moved the re-solved field by 5.9e-4 of the flux span — larger than
 * the zero test it was meant to check.)
 *
 * Returns an object with `why` set when the plasma leaves the box.
 */
/**
 * The machine limiter clipped against a horizontal half-plane
 * (Sutherland–Hodgman, one clip edge).  What it is for: on a DIVERTED
 * source field the PRIVATE flux region below the X point carries
 * s·psi > s·psi_b too (that is the same fact that misled the naive
 * boundary rule, T-D6′), and the fixed-box refinement's connectivity
 * flood can leak into it through the X saddle cell and touch the box
 * border — which is, correctly, a refusal.  Cutting the vessel at the X
 * point's height excludes the private region while leaving every
 * confined cell exactly as the free solve had it.
 */
function evClipLimiterZ(zcut, keepAbove) {
  var pr = M.limiter.r, pz = M.limiter.z, n = pr.length;
  var outR = [], outZ = [];
  for (var i = 0; i < n; i++) {
    var j = (i + 1) % n;
    var aIn = keepAbove ? pz[i] >= zcut : pz[i] <= zcut;
    var bIn = keepAbove ? pz[j] >= zcut : pz[j] <= zcut;
    if (aIn) { outR.push(pr[i]); outZ.push(pz[i]); }
    if (aIn !== bIn) {
      var t = (zcut - pz[i]) / (pz[j] - pz[i]);
      outR.push(pr[i] + t * (pr[j] - pr[i]));
      outZ.push(zcut);
    }
  }
  return outR.length >= 3
    ? { r: Float64Array.from(outR), z: Float64Array.from(outZ) }
    : null;
}

/** The refinement's vessel: clipped at the X point for a diverted source. */
function evRefineLimiter(eq) {
  if (eq.bndKind === 1 && isFinite(eq.xptZ)) {
    var below = eq.xptZ < eq.axisZ;
    var clip = evClipLimiterZ(eq.xptZ, below);
    if (clip) return clip;
  }
  return M.limiter;
}

function evFixedPicard(box, psi0, psiBnd, sAxis, seed, source, opts) {
  var lim = (opts && opts.limiter) || M.limiter;
  return fy.gsFixedBox({
    r: box.r, z: box.z,
    //: ★the PARENT grid's spacing, not `box.r[1] - box.r[0]`: the box is a
    //: window on the machine grid and its nodes are that grid's nodes.  The
    //: two agree to a ulp, and a cell area that moves by a ulp moves every
    //: I_p this page reports against a stored one.
    dr: grid.dr, dz: grid.dz,
    psi: psi0, psiBoundary: psiBnd, signAxis: sAxis,
    seedR: seed.r, seedZ: seed.z,
    //: ★T-M17: the current the Dirichlet border was computed for — the
    //: kernel holds I_p there by solving the FF' constant, which is what
    //: stops a source that integrates differently from inflating psi
    //: across the separatrix saddle and running to the box ring
    ipTarget: opts.ipTarget,
    //: ★the vessel test, and it is the FREE solver's own: that solve floods
    //: its plasma over vessel-interior nodes only, and so does the mask
    //: `analytic_truth` normalises against.  A refinement whose plasma is
    //: allowed one cell the free solve was not would be compared against a
    //: field built from a different source — measured, that alone is a 2e-3
    //: pointwise difference in the zero test on a diverted EAST boundary.
    limR: lim.r, limZ: lim.z,
    source: source,
    gauge: 2 * Math.PI,
    //: ±2 cells, the free solver's own dilation
    dilate: 2,
    relax: opts.relax === undefined ? 0.5 : opts.relax,
    maxIter: opts.maxIter || 300, tol: opts.tol || 1e-9,
  });
}

/**
 * The coupled equilibrium, REFINED on the transport's own pressure.
 *
 * ★★WHAT THIS REPLACES.  The free-boundary solver takes a two-parameter
 * current family, `(1 - psibar^emp)^enp` times a paramagnetic mix, so a
 * coupled march could only hand its pressure back through those two
 * numbers — a shape outside the family simply could not be represented, and
 * the page reported the fit residual and lived with it.  The refinement
 * takes p' and FF' as POLYNOMIALS, so the transport's own pressure gradient
 * goes in to whatever degree the reader asks for.
 *
 * What is kept from the free solve is the EXTERNAL field: the Dirichlet
 * border of the sub-box is that solve's own, untouched, and only the plasma
 * source is replaced.  So the plasma boundary is where Grad-Shafranov puts
 * it given this pressure and this current — which is the self-consistent
 * statement the family could not make.
 *
 * ★★AND IT REPORTS ITS OWN ZERO TEST.  Before the refinement proper, the
 * same loop is run on the source the free solve ITSELF used — the analytic
 * `p'`/`FF'` that field implies — and the answer is compared with that
 * field pointwise.  A refinement machine that cannot reproduce the
 * equilibrium it starts from has nothing to say about a different pressure,
 * and the two numbers (`zeroPsi`, relative to the flux span, and `zeroIp`)
 * are the calibration a reader is owed rather than a claim.  Both gauges —
 * total flux against per radian — are pinned by that one comparison: a
 * factor 2 pi anywhere in the chain moves `zeroIp` by orders.
 *
 * Returns null when it cannot be done, having posted why.
 */
function evFixedRefine(eq, geo, st, sp, degP, degF, prof, pFast) {
  var n = geo.rho.length, i;
  var span = eq.psiBnd - eq.psiAxis;
  if (!(Math.abs(span) > 0)) return null;

  //: the app's convention, read off the field rather than assumed: this
  //: repo's psi has its MAXIMUM on axis (`session.js`, `signAxis: 1`)
  var sAxis = span < 0 ? 1 : -1;
  //: the free solve's own span, per radian — `analytic_truth`'s sign
  //: convention, (psi_axis - psi_bnd) / 2 pi
  var spanPrFree = (eq.psiAxis - eq.psiBnd) / (2 * Math.PI);

  //: the pressure the march reached — PLUS the fast-ion contribution when a
  //: beam supplied one (T-M12): the scalar the G-S source takes is the
  //: trace third of the split, `(p_par + 2 p_perp) / 3`, so BOTH branches
  //: enter the equilibrium through it.  `pFast` arrives already on this
  //: ladder and already carrying that combination.
  var pPa = new Float64Array(n);
  for (i = 0; i < n; i++)
    pPa[i] = (st.ne[i] * st.te[i] + st.ni[i] * st.ti[i]) * EV_QE
           + (pFast ? pFast[i] : 0);

  //: ★★WHAT IS FITTED IS d/dpsibar, NOT d/dpsi.  What the march determines
  //: is the pressure at a normalised flux; the flux SPAN is part of what
  //: the refinement finds, so a profile pinned to the free solve's span
  //: would hold a pressure the march never computed once the well moved
  //: (measured on EAST: a well 36 % deeper came back carrying 36 % more
  //: pressure and reported the beta_p to match).  These two tables are
  //: therefore gauge-free — Pa and T^2 m^2 per unit psibar — and
  //: `evFixedPicard` divides by the span the ITERATE has.
  //:
  //: ★★WHERE THE QUOTIENTS ARE TAKEN, and it is not a detail.  Node 0 of
  //: this ladder is PREPENDED, not traced (`with_axis_node`): rho, psi_N
  //: and V' are zeroed there and the flux-surface averages repeat their
  //: innermost traced value, while the transport's zero-flux axis condition
  //: repeats T there too.  A difference across that node is the derivative
  //: of a FILL, and it is not small: measured on EAST it reported dp/dpsibar
  //: at the axis eleven times too shallow and put a spike at node 1 beside
  //: it, and the cubic that had to swallow both came back with a 65 %
  //: relative residual — the "noisy finite difference" the page was blaming
  //: on FF'.  So the quotients run over the TRACED intervals only and sit at
  //: the interval MIDPOINTS, where a two-point quotient is second order
  //: instead of first; the polynomial supplies psibar = 0 and 1 by
  //: extrapolation, which is what a profile family in psibar is for.
  //:
  //: ★★AND FF' IS THE EQUILIBRIUM'S OWN, from that equilibrium's analytic
  //: truth rather than differenced out of a ladder.  The pressure is the
  //: transport's, the paramagnetic part is not, and the page says which is
  //: which.  It used to be a finite difference of `geo.fpol` — the F of the
  //: ladder the march had been RUNNING on, which belongs to the PREVIOUS
  //: equilibrium, divided by THIS one's span: two equilibria mixed into one
  //: derivative, and on EAST the two disagreed by 60 %.
  var nm = n - 2, xs = [], dpTab = new Float64Array(nm),
      dgTab = new Float64Array(nm);
  for (i = 1; i < n - 1; i++) {
    var dx = geo.psin[i + 1] - geo.psin[i];
    xs.push(0.5 * (geo.psin[i] + geo.psin[i + 1]));
    dpTab[i - 1] = dx !== 0 ? (pPa[i + 1] - pPa[i]) / dx : 0;
    //: FF' per radian, back to per psibar with the free solve's own span
    dgTab[i - 1] = -spanPrFree
      * evInterp(eq.profiles.x, eq.profiles.ffprime, xs[i - 1]);
  }
  var fitP = fy.polyFit(xs, dpTab, degP);
  var fitF = fy.polyFit(xs, dgTab, degF);

  //: ★the box margin stays at 15 % for BOTH classes.  A roomier box for
  //: the diverted source was tried (v108) and made things worse, not
  //: better: with a 30 % margin the zero test itself exploded (ψ pointwise
  //: 1.75, I_p off 78 % — the connectivity solve grabs structure the
  //: tighter window excludes).  The diverted refusal that remains
  //: (「涨到了子网格边界」on coupled blocks) is a真 limitation of the
  //: polynomial-source refinement on a separatrix-bounded field, recorded
  //: in TODO.md as its own item rather than papered over here.
  var box = evPlasmaBox(eq);
  if (!box) throw new Error(FyI18n.t('e.err.refine_box'));
  var sub = evSubField(eq.psi, box);
  var seed = { r: eq.axisR, z: eq.axisZ };
  //: the X-clipped vessel rides on BOTH solves below — the zero test must
  //: run on the same mask rule as the refinement it vouches for
  //: ★maxIter 600, not 300: the I_p constraint adds a slow mode (the FF'
  //: shift is re-solved each iterate), and the zero test measured at the
  //: old cap came back mid-descent — residual above tolerance, and the
  //: gate's Δ* anchor 4e-3 off where a converged box sits at 1e-6.
  var loop = { relax: 0.5, maxIter: 600, tol: 1e-9,
               limiter: evRefineLimiter(eq),
               //: ★T-M17: both solves below — the zero test and the
               //: refinement proper — run under the free solve's own I_p.
               //: The zero test's ip criterion is then exact by
               //: construction and what it pins moves entirely onto psi,
               //: which is the half that was ever informative.
               ipTarget: eq.ip };

  //: --- the zero test ---------------------------------------------------
  //: the free solve's OWN source, taken from the field it converged to.
  //: `analyticTruth` reports p'/FF' per radian; the loop wants them per
  //: psibar, and the free solve's own span is the one that converts them —
  //: which is exactly the identity the test is checking, so a 2 pi anywhere
  //: in the chain lands here and nowhere else.
  var zero = null;
  //: the analytic truth is a TABLE (201 points of the kernel's own shape
  //: function), so the kernel is told to read it as one — the refinement's
  //: own source below is a polynomial and is declared as a polynomial.
  //: ★The span scale rides ALONGSIDE the table rather than being folded
  //: into 201 stored values: `scale * interp(v)` and `interp(scale * v)`
  //: are the same number rounded twice differently, and this table is the
  //: zero test's own reference.
  if (prof && eq.profiles && eq.profiles.pprime) {
    var z0 = evFixedPicard(box, sub, eq.psiBnd, sAxis, seed,
                           { x: eq.profiles.x,
                             pprime: eq.profiles.pprime,
                             ffprime: eq.profiles.ffprime,
                             ppScale: -spanPrFree, ffScale: -spanPrFree },
                           loop);
    if (!z0.why) {
      //: pointwise, against the SPAN — psi's zero is the coil gauge, so a
      //: difference divided by psi itself would measure that offset and not
      //: the field
      var dmx = 0;
      for (i = 0; i < z0.psi.length; i++) {
        var dd = Math.abs(z0.psi[i] - sub[i]);
        if (dd > dmx) dmx = dd;
      }
      zero = { psi: dmx / Math.abs(span), ip: z0.ip, ipRef: eq.ip,
               ipRel: Math.abs(z0.ip - eq.ip) / Math.max(Math.abs(eq.ip), 1),
               iterations: z0.iterations, residual: z0.residual,
               //: the field this is measured AGAINST, and how well the free
               //: solve reached it — the zero test cannot be tighter than
               //: the equilibrium it is comparing with
               freeIterations: eq.iterations, freeResidual: eq.residual,
               axisR: z0.axisR, axisZ: z0.axisZ };
    } else {
      zero = { why: z0.why };
    }
  }

  //: ★★AND THE ZERO TEST IS A GATE, not a footnote.  A refinement machine
  //: that cannot come back to the equilibrium it started from has nothing
  //: to say about a different pressure, so when it does not, the answer is
  //: REFUSED and the two-parameter family's stands — the same posture the
  //: rest of this function takes towards a failure.  The two numbers are
  //: the closure criteria this feature was held to, and they are refusal
  //: thresholds rather than pass marks: what they buy is that a refinement
  //: the page DOES use has always reproduced its own starting point.
  //:
  //: What sets them: measured across six coupling blocks on EAST, the zero
  //: test tracks the FREE solve's own convergence and nothing else —
  //: blocks whose free solve broke on its 1e-9 tolerance came back at
  //: 2.0e-5 to 5.3e-5 pointwise, one that stopped at residual 1.2e-6 came
  //: back at 2.2e-4, and the two that ran out of iterations mid-trim
  //: (2.2e-4 and 1.5e-3) came back at 5.1e-4 and 1.9e-3.  The refinement
  //: is converging correctly in all six; in the last two it is converging
  //: to the equilibrium the free field had not yet reached.  So the
  //: residual and the iteration count of that solve travel WITH the
  //: refusal — the reason is upstream, and a reader sent to look at the
  //: refinement would be looking in the wrong place.
  if (!zero || zero.why)
    throw new Error(FyI18n.t('e.err.refine_zerofail', {
      why: zero ? zero.why : 'no analytic profiles on the free solve',
      it: eq.iterations, fresid: eq.residual.toExponential(1) }));
  //: residual-aware threshold — see EV_ZERO_SCALE
  var zeroPsiTol = Math.max(EV_ZERO_PSI,
                            EV_ZERO_SCALE * (isFinite(eq.residual)
                                             ? eq.residual : 0));
  if (!(zero.psi < zeroPsiTol && zero.ipRel < EV_ZERO_IP))
    throw new Error(FyI18n.t('e.err.refine_zero', {
      psi: zero.psi.toExponential(2), ip: (100 * zero.ipRel).toFixed(2),
      psiTol: zeroPsiTol.toExponential(1),
      ipTol: (100 * EV_ZERO_IP).toFixed(0),
      it: eq.iterations, fresid: eq.residual.toExponential(1) }));

  //: --- the refinement proper -------------------------------------------
  //: ★`ev` stays: the profiles this solve ran on are sampled BELOW, for the
  //: q solve and for the pressure that is integrated back out, and those
  //: have to be the same polynomial the kernel evaluated.  The kernel sums
  //: the monomials the same way (`acc += c[k] * t; t *= x`, not Horner) and
  //: says so.
  var ev = function (c, x) {
    var acc = 0, t = 1;
    for (var q = 0; q < c.length; q++) { acc += c[q] * t; t *= x; }
    return acc;
  };
  var refined = evFixedPicard(box, sub, eq.psiBnd, sAxis, seed,
                              { x: null, pprime: fitP.coef,
                                ffprime: fitF.coef }, loop);
  var diagOf = function (rr) {
    return 'I_p ' + (rr.ip / 1e3).toFixed(1) + ' kA · psi_axis '
      + rr.psiAxis.toFixed(4) + ' / psi_b ' + eq.psiBnd.toFixed(4)
      + ' · axis (' + rr.axisR.toFixed(3) + ', ' + rr.axisZ.toFixed(3)
      + ') · ' + rr.iterations + ' it, resid ' + rr.residual.toExponential(1);
  };
  if (refined.why)
    throw new Error(FyI18n.t('e.err.refine_' + (
      refined.why === 'grew' ? 'grew' : 'axis')));
  //: ★T-M17: the FF' constant the I_p constraint solved is PART of the
  //: source the answer satisfies.  Folded into the coefficient array here,
  //: once, so the q solve, the recovered pressure, the exported source and
  //: the gate's native re-solve all see the source the kernel actually ran
  //: — none of them needs to know the constraint existed.
  //: (a plain Array, like `polyFit`'s own — a Float64Array here would
  //: JSON-serialise as an object and the exported source would be a dict)
  var dgCoef = Array.from(fitF.coef);
  dgCoef[0] += refined.ffShift || 0;

  //: the refined interior back into the full field
  var psiFull = Float64Array.from(eq.psi);
  for (var bi = 0; bi < box.nr; bi++)
    for (var bj = 0; bj < box.nz; bj++)
      psiFull[(box.i0 + bi) * grid.nz + (box.j0 + bj)] =
        refined.psi[bi * box.nz + bj];

  var res2 = { psi: psiFull, psiAxis: refined.psiAxis,
               psiBnd: eq.psiBnd, axisR: refined.axisR,
               axisZ: refined.axisZ };
  //: ★a refinement that produced no closed surface says WHAT it produced.
  //: The failure this guards is not a crash: it is a psi map with no plasma
  //: in it, and "the boundary trace threw" tells a reader nothing about
  //: which of the axis, the current or the gauge went wrong.
  var poly2 = null, sm2 = null;
  try {
    poly2 = P.boundarySurface(grid, res2.psi, res2.psiAxis, res2.psiBnd,
                              res2.axisR, res2.axisZ, M.limiter.r,
                              M.limiter.z, 181);
    sm2 = fy.shapeMetrics(poly2);
  } catch (eB) { sm2 = null; }
  if (!sm2 || !(sm2.a > 0))
    throw new Error(FyI18n.t('e.err.refine_open', { diag: diagOf(refined) }));

  //: the profiles on a uniform psi_N grid, for the q solve — and HERE the
  //: per-radian gauge, because that is what `qProfile` divides the span by.
  //: The span is the one the refinement REACHED, not the one it started
  //: from: the tables are per psibar and this is where they come back out.
  var NX = 41, px = new Float64Array(NX), pp = new Float64Array(NX),
      ff = new Float64Array(NX), pv = new Float64Array(NX),
      dpv = new Float64Array(NX);
  var spanPrFix = (res2.psiAxis - res2.psiBnd) / (2 * Math.PI);
  for (i = 0; i < NX; i++) {
    px[i] = i / (NX - 1);
    dpv[i] = ev(fitP.coef, px[i]);
    pp[i] = -dpv[i] / spanPrFix;
    ff[i] = -ev(dgCoef, px[i]) / spanPrFix;
  }
  //: ★p is RECOVERED, not copied back: integrated inward from the
  //: transport's edge pressure through the polynomial the solve actually
  //: ran on, so the fit's own residual is in it.  Copying the input array
  //: here would make every beta_p that reads it a restatement of its input.
  var pEdge = pPa[n - 1], h = 1 / (NX - 1), acc = 0;
  pv[NX - 1] = pEdge;
  for (i = NX - 2; i >= 0; i--) {
    acc += 0.5 * (dpv[i] + dpv[i + 1]) * h;
    pv[i] = pEdge - acc;
  }
  var prof2 = { x: px, pprime: pp, ffprime: ff, p: pv };
  var q2 = null;
  try {
    q2 = P.qProfile(grid, res2, prof2, M.limiter.r, M.limiter.z, F_EDGE,
                    { nq: 20, ntheta: 121 });
  } catch (e) { q2 = null; }
  if (!q2) return null;

  var NQ = 33, qT = new Float64Array(NQ), fT = new Float64Array(NQ);
  for (i = 0; i < NQ; i++) {
    var x2 = i / (NQ - 1);
    qT[i] = Math.abs(evInterp(q2.x, q2.q, x2));
    fT[i] = evInterp(px, q2.f, x2);
  }
  var geo2 = evLadderMetric({
    psi: res2.psi, psiAxis: res2.psiAxis, psiBnd: res2.psiBnd,
    axisR: res2.axisR, axisZ: res2.axisZ,
    gridR0: grid.r[0], gridZ0: grid.z[0], dr: grid.dr, dz: grid.dz,
    nr: grid.nr, nz: grid.nz, limR: M.limiter.r, limZ: M.limiter.z,
    qTable: qT, fTable: fT,
    b0: Math.abs(self.FyDevice.tf(M).b0), aMinor: sm2.a, rMaj: sm2.r0,
    n: sp.n, edgePsin: sp.edgePsin, nTheta: 121, source: 'device' });

  return {
    //: ★★THE SOLVED BOX TRAVELS OUT, and it is not a debug crumb: it is the
    //: only form in which the claim "this field solves Grad-Shafranov for
    //: this pressure" can be checked by anyone who is not this function.
    //: The full-grid map would be the coils' field pasted around it; what
    //: carries the claim is the sub-box — its border is the Dirichlet data,
    //: its interior is what was solved, and the two profiles below are the
    //: source, per radian.  `app/tests/validate-evolve.mjs` hands the four
    //: of them to `libfylite_kernel.so` and re-solves Delta* natively.
    field: { r: box.r, z: box.z, psi: refined.psi,
             psiAxis: refined.psiAxis, psiBnd: eq.psiBnd,
             axisR: refined.axisR, axisZ: refined.axisZ,
             //: ★★THE VESSEL THE SOLVE WAS CONFINED TO — the X-clipped one
             //: on a diverted source (`evRefineLimiter`), not the machine's.
             //: Exporting the machine's handed the gate's native re-solve a
             //: DIFFERENT equation: its flood leaked through the X saddle
             //: into the private flux region the solve had excluded —
             //: measured, +0.5 % of current from cells the kernel never
             //: fed, a 4e-3 Δ* residual, and a Picard re-run that "reached
             //: the box border" on the very field it was given.
             limR: loop.limiter.r, limZ: loop.limiter.z,
             //: ★the SOURCE, as the monomial coefficients the solve ran on
             //: and in the gauge it ran in: dp/dpsibar [Pa] and
             //: d(F^2/2)/dpsibar [T^2 m^2].  Not a sampled copy of them —
             //: a table is a second, lossier statement of the same thing,
             //: and a reader checking the field would be checking their
             //: interpolation of it.
             dpCoef: fitP.coef, dgCoef: dgCoef, ip: refined.ip,
             //: ★T-M17: what the constraint did, in the open — the target
             //: it held, the constant it solved, and what the fitted
             //: source wanted before it
             ipTarget: eq.ip, ffShift: refined.ffShift || 0,
             ipRaw: refined.ipRaw },
    eq: { psi: res2.psi, psiAxis: res2.psiAxis, psiBnd: res2.psiBnd,
          axisR: res2.axisR, axisZ: res2.axisZ, shape: sm2, q: q2,
          //: ★the refined equilibrium's OWN profiles travel with it: the
          //: next block's beta_p reads `eq.profiles`, and a refined field
          //: still carrying the family's would report the pressure it
          //: replaced.  The free solve's stays with the free solve, which
          //: is what the (emp, enp, beta0) feedback is about.
          profiles: prof2,
          //: ★flat [r, z, r, z, ...], the shape every other consumer of
          //: `eq.lcfs` on this page reads — `summarize` flattens its own,
          //: and a nested one here would draw a boundary of NaNs
          lcfs: (function () {
            var a = new Float64Array(poly2.length * 2);
            for (var k = 0; k < poly2.length; k++) {
              a[2 * k] = poly2[k][0]; a[2 * k + 1] = poly2[k][1];
            }
            return a;
          })() },
    geo: geo2,
    fitP: fitP, fitF: fitF, zero: zero,
    ipSolved: refined.ip, iterations: refined.iterations,
    residual: refined.residual,
  };
}

/** The march's ion list, flat and channel-major, from the split state. */
function evIonFlat(st, nIon, n) {
  if (nIon < 2) return st.ni;
  var out = new Float64Array(2 * n);
  out.set(st.ni, 0); out.set(st.nz, n);
  return out;
}

/**
 * The particle source for that list — one block per species.
 *
 * ★★T-C20: the impurity's block used to be left at zero, and the comment
 * that said so read as a physics statement when it was a wiring one.  It is
 * the caller's `sz` now, which is a PRESCRIBED deposition exactly like the
 * main ion's fuelling — there is no sputtering, injection or wall-recycling
 * model in this build, and there will not be one until an external case
 * exists to judge it against (the same rule the fuelling source itself is
 * under).  ★Zero is still a legitimate answer and still the default: it
 * means「只有再分配」, not「没有这一项」.
 */
function evSourceFlat(sn, nIon, n, sz) {
  if (nIon < 2) return sn;
  var out = new Float64Array(2 * n);
  out.set(sn, 0);
  if (sz) out.set(sz, n);
  return out;
}

/**
 * Z_eff on the ladder — the slider's number, or the composition's own when
 * the composition is a solved quantity (T-C20).
 *
 * ★★`sum_s n_s Z_s^2 / n_e` over the species the march is actually carrying.
 * It is a PROFILE, because the two species diffuse differently and that is
 * the entire point of giving the impurity its own D/v: a Z_eff that stayed
 * flat while the impurity peaked would be reporting a composition nobody
 * solved for.
 *
 * ★It falls back to the control whenever the impurity is not a CHANNEL —
 * with the density channel off the composition is what the reader said it
 * was, and the state carries no second species to read.
 */
function evZeffOf(ctx, st) {
  var sp = ctx.sp, n = ctx.rho.length, nIon = ctx.nIon || 1;
  if (!(ctx.channels && ctx.channels.density) || nIon < 2 || !st.ni || !st.ne)
    return evFill(n, sp.zeff);
  //: ★★THE ION LIST COMES IN FLAT AND ION-MAJOR, and reading it as though
  //: the second species were a separate `nz` field is how this returned a
  //: perfectly flat Z_eff while the impurity was visibly moving — the gate
  //: caught exactly that.  ★The closure is handed the KERNEL's state
  //: (`{rho, te, ti, ne, psi, ni}`), and its `ni` is the whole list; the
  //: worker's own `st.nz` exists only between steps, after the split.
  var flat = st.ni.length >= nIon * n;
  var nz = flat ? null : st.nz;
  if (!flat && !nz) return evFill(n, sp.zeff);
  var z = sp.impurityZ, out = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    var ne = st.ne[i];
    var main = flat ? st.ni[i] : st.ni[i];
    var imp = flat ? st.ni[n + i] : nz[i];
    //: ★a floor of 1 rather than a NaN: a surface with no electrons on it is
    //: a grid artefact, and a Z_eff of NaN would silently poison sigma
    out[i] = ne > 0
      ? Math.min(30, Math.max(1, (main + imp * z * z) / ne))
      : 1;
  }
  return out;
}

/** The radial subset a turbulent closure is evaluated on. */
function evTurbRadii(n, nRad) {
  var out = [];
  nRad = Math.max(2, nRad | 0);
  for (var j = 0; j < nRad; j++)
    out.push(Math.round(1 + (n - 3) * (j / Math.max(1, nRad - 1))));
  return out;
}

/** The ky grid, log-spaced over the same span the 1.5-D bar uses. */
function evKyGrid(nKy) {
  var out = [], lo = 0.05, hi = 0.8;
  nKy = Math.max(2, nKy | 0);
  for (var k = 0; k < nKy; k++)
    out.push(+(lo * Math.pow(hi / lo, k / Math.max(1, nKy - 1))).toFixed(6));
  return out;
}

function turbulentChi(sp, neo, x, y, chiNeo) {
  var nr = sp.radii.length, sub = new Float64Array(nr), xs = new Float64Array(nr);
  for (var i = 0; i < nr; i++) {
    var k = sp.radii[i], o = 20 * k, aMin = neo.surf[o];
    xs[i] = x[k];
    var rLoc = neo.surf[o + 1] / aMin, q = Math.abs(neo.surf[o + 6]);
    //: ★a/L_T from the CURRENT iterate — this is the whole reason the
    //: closure is re-evaluated at all.  Centred where it can be; the
    //: gradient is taken against rmin (a LENGTH), not the radial label,
    //: because TGLF's normalisation is a/L and `a` is a length too.
    var k0 = Math.min(Math.max(k, 1), y.length - 2);
    var dT = y[k0 + 1] - y[k0 - 1];
    var dr = (neo.surf[20 * (k0 + 1) + 1] - neo.surf[20 * (k0 - 1) + 1]) / aMin;
    //: `dr` is already in units of `a` (both lengths came from the same
    //: block and were divided by `aMin`), so a/L_T is just -(dT/dr)/T
    var rlt = (dr !== 0 && y[k] > 0) ? -(dT / dr) / y[k] : 0;
    rlt = Math.max(Math.min(rlt, 20), 0.1);
    var rln = Math.max(Math.min(aMin * neo.surf[o + 17], 20), 0);
    var deck = {
      miller14: [rLoc, neo.surf[o + 2] / aMin, 0.0, q,
                 neo.surf[o + 8], 0.0, neo.surf[o + 10], 0.0,
                 0.0, 0.0, 0.0, 0.0, 1.0, 128],
      //: q' from the same q and shear the neoclassical block carries, so
      //: the two closures cannot end up describing different surfaces
      pPrime: 0.0, qPrime: (q / Math.max(rLoc, 1e-3)) * (q / Math.max(rLoc, 1e-3))
                            * neo.surf[o + 7],
      width: sp.width, kx0: 0.0, thetaTrapped: 0.7,
      zs: [-1.0, 1.0], mass: [0.0002723, 1.0], as: [1.0, 1.0],
      taus: [1.0, 1.0], rlns: [rln, rln], rlts: [rlt, rlt],
      signBt: 1.0, xnue: 0.0, zeff: 1.0, xnuModel: 2.0, xnuFactor: 1.0,
      park: 1.0, wdiaTrapped: 0.0, vparModel: 0.0, alphaMach: 0.0,
      alphaP: 1.0, signIt: 1.0, betae: 0.0, useBper: 0.0, useBpar: 0.0,
      dampPsi: 0.0, dampSig: 0.0, linskerFactor: 0.0, useMhdRule: 1.0,
      wdZero: 0.1, vexbShear: 0.0, alphaE: 1.0, alphaQuench: 0.0,
      rlnpCutoff: 18.0, vpar: [0, 0], vparShear: [0, 0],
      nbasis: 4, nxgrid: 16, ky: sp.ky, satRule: sp.satRule,
    };
    //: ★★THE E x B SHEAR, and it is the kernel's number rather than this
    //: file's.  `VEXB_SHEAR` is four conventions deep — which sign, which
    //: radius the rotation derivative is taken against, which length it is
    //: normalised by, and which sound speed — so it is asked of
    //: `mapping::tglf_local`, which already carries all four together with
    //: the `c_s` its own derived block defines.  Zero when the momentum
    //: channel is off, and zero is then a STATEMENT (no rotation was
    //: solved) rather than the placeholder it used to be.
    //:
    //: ★The parallel-velocity half of that block (`vpar`, `vpar_shear`) is
    //: deliberately left out: this deck runs `VPAR_MODEL = 0`, under which
    //: TGLF does not read them, and shipping them into a model that ignores
    //: them would be reporting a coupling that is not in the run.
    if (sp.w0) {
      var i6 = 6 * k;
      var loc = fy.tglfLocal({
        surf20: neo.surf.subarray(o, o + 20), signb: neo.signb,
        signq: neo.signq, w0: sp.w0[k], w0p: sp.w0p[k],
        iz: [neo.ion[i6]], imass: [neo.ion[i6 + 1]], ini: [neo.ion[i6 + 2]],
        iti: [neo.ion[i6 + 3]], idlnn: [neo.ion[i6 + 4]],
        idlnt: [neo.ion[i6 + 5]], betaeScale: 1, nuScale: 1,
        rotation: true });
      deck.vexbShear = loc.vexbShear;
    }
    var u = tglf.tglfUnits(deck.miller14, deck.pPrime, deck.qPrime,
                           deck.width, deck.thetaTrapped);
    var kg = tglf.tglfKygrid({ zs: deck.zs, mass: deck.mass, as: deck.as,
                               taus: deck.taus, nky: sp.ky.length });
    var f = tglf.tglfFlux({
      miller18: deck.miller14.concat([deck.pPrime, deck.qPrime,
                                      deck.width, deck.kx0]),
      scal30: [u.rUnit, u.qUnit, u.bUnit, deck.signBt, u.ft, kg.rhoIon,
               deck.width, dlnpdr(deck), deck.vexbShear, deck.alphaE,
               deck.alphaQuench, deck.xnue, deck.zeff, deck.xnuModel,
               deck.xnuFactor, deck.park, deck.wdiaTrapped,
               deck.thetaTrapped, deck.vparModel, deck.alphaMach,
               deck.alphaP, deck.signIt, deck.betae, deck.useBper,
               deck.useBpar, deck.dampPsi, deck.dampSig,
               deck.linskerFactor, deck.useMhdRule, deck.wdZero],
      geom4: [deck.pPrime, deck.qPrime, deck.kx0, deck.miller14[13]],
      zs: deck.zs, mass: deck.mass, as: deck.as, taus: deck.taus,
      rlns: deck.rlns, rlts: deck.rlts, vpar: deck.vpar,
      vparShear: deck.vparShear, ky: sp.ky,
      nbasis: deck.nbasis, nxgrid: deck.nxgrid, satRule: sp.satRule });
    //: the ion energy flux, gyro-Bohm normalised, turned into a diffusivity
    //: by the same drive and the same unit the neoclassical path uses
    var qi = Math.abs(f.energy[1]);
    sub[i] = qi / Math.max(rlt, 1e-6) * neo.chigb[k];
  }
  //: ★interpolated back onto the solver grid, and the SUBSET is reported.
  //: A tier that quietly evaluated six radii and drew twenty-one would be
  //: presenting an interpolation as a calculation.
  var out = new Float64Array(x.length);
  for (var j = 0; j < x.length; j++) out[j] = interp1(xs, sub, x[j]);
  return { chi: out, sub: sub, xs: xs };
}

function transportTurb(msg) {
  var t0 = Date.now(), sp = msg.spec, neo = msg.neo;
  var start = function () {
    var x = Float64Array.from(sp.x), y = Float64Array.from(sp.y0);
    var chiPrev = null, r = null, settled = false, passes = 0, last = null;
    for (var it = 0; it < sp.outer; it++) {
      var chiNeo = fy.neoChi(x, y, neo, sp.chi0);
      var tb = turbulentChi(sp, neo, x, y, chiNeo);
      var chi = new Float64Array(x.length);
      for (var k = 0; k < x.length; k++) {
        var want = chiNeo[k] + tb.chi[k];
        //: ★under-relaxed on CHI, not on the temperature.  The turbulent
        //: channel is stiff — chi rises steeply with a/L_T — so an
        //: unrelaxed outer loop oscillates between an over- and an
        //: under-transported profile rather than converging.
        chi[k] = chiPrev ? chiPrev[k] + sp.relax * (want - chiPrev[k]) : want;
      }
      chiPrev = chi;
      r = fy.transportStep({
        x: x, yOld: y, vprime: Float64Array.from(sp.vprime),
        metric: Float64Array.from(sp.metric),
        velocity: Float64Array.from(sp.velocity),
        source: Float64Array.from(sp.source),
        model: 3, p0: sp.chi0, p1: 0.25, p2: 1.75,
        neo: neo, chiGiven: chi, dPc: sp.dPc || 0,
        dt: Infinity, theta: 1, edgeValue: sp.edge,
        tol: 1e-10, maxInner: 200 });
      passes += 1;
      var move = Math.abs(r.y[0] - y[0]) / Math.max(Math.abs(r.y[0]), 1e-12);
      y = Float64Array.from(r.y);
      last = { chi: chi, chiNeo: chiNeo, turb: tb };
      post({ type: 'turb_pass', it: passes, t0: y[0], move: move,
             chiMin: Math.min.apply(null, Array.from(chi)),
             chiMax: Math.max.apply(null, Array.from(chi)) });
      if (move < sp.tol) { settled = true; break; }
    }
    post({ type: 'transport_turb', y: Array.from(y),
           chi: Array.from(last.chi), chiNeo: Array.from(last.chiNeo),
           chiTurb: Array.from(last.turb.chi),
           subX: Array.from(last.turb.xs), subChi: Array.from(last.turb.sub),
           outer: passes, settled: settled,
           iterations: r.innerIterations, converged: r.converged,
           residual: r.residual, ms: Date.now() - t0,
           bytes: tglf.bytes, sha256: tglf.sha256 });
  };
  if (tglf) return start();
  self.FyLite.loadExt('fylite_kernel_ext.wasm').then(function (inst) {
    tglf = inst;
    start();
  }).catch(function (e) {
    post({ type: 'error', where: 'transport_turb',
           message: String(e && e.message || e) });
  });
}

// --- breakdown: the pre-plasma field null ----------------------------------
//
// Reconnected (T-D14) from the pre-restructure site, as a bar of the design
// scenario: the step a discharge starts with, BEFORE any plasma exists.
// ★It is PURELY VACUUM — there is no Grad-Shafranov solve anywhere in it:
// the field is linear in the coil currents, so "design a null" is one small
// box-constrained least-squares (`breakdown.rs`, one call through
// `designNull`), not an outer loop around a solver.  That is also why it is
// the cheapest capability in the chain.
//
// ★The channel response is taken at subdivision 3x3 because that is what
// the native path (`breakdown.py`) uses; this worker's equilibrium entries
// call the same kernel at 4x4, and mixing the two would leave two
// "responses" that differ in the third digit and nothing pointing at why.

/** Disc sampling: centre plus concentric rings (`breakdown::null_disc`). */
function nullDisc(r0, z0, radius, nRing, nTheta) {
  var r = [r0], z = [z0];
  for (var k = 1; k <= nRing; k++) {
    var rad = radius * k / nRing;
    for (var t = 0; t < nTheta; t++) {
      var th = 2 * Math.PI * t / nTheta;
      r.push(r0 + rad * Math.cos(th));
      z.push(z0 + rad * Math.sin(th));
    }
  }
  return { r: Float64Array.from(r), z: Float64Array.from(z) };
}

/** |B_pol| of channel currents `x` on the whole grid, for the picture. */
function gridBpolOf(x) {
  var n = grid.nr * grid.nz;
  var rr = new Float64Array(n), zz = new Float64Array(n);
  for (var i = 0; i < grid.nr; i++)
    for (var j = 0; j < grid.nz; j++) {
      rr[i * grid.nz + j] = grid.r[i];
      zz[i * grid.nz + j] = grid.z[j];
    }
  var f = channelBlocks(M.coils, rr, zz, 3, 3);
  var out = new Float64Array(n), mx = 0;
  for (var p = 0; p < n; p++) {
    var br = 0, bz = 0;
    for (var c = 0; c < NCH; c++) {
      br += x[c] * f.br[c * n + p];
      bz += x[c] * f.bz[c * n + p];
    }
    out[p] = Math.hypot(br, bz);
    if (out[p] > mx) mx = out[p];
  }
  return { values: out, scale: mx };
}

/**
 * One field-null design.
 *
 * ★The rows are the KERNEL's, not ours: the tolerance-normalised null rows
 * (teslas, ~1e-3), the flux row scaled by its own target (webers, ~1e-1),
 * the ridge toward the reference currents and the symmetric box all live in
 * `breakdown.rs` — left raw, the flux row would swamp the null and the
 * "design" would come back a uniform field.  This side samples the disc,
 * evaluates the coils on it, and reads the answer back.
 */
function nullSolve(sp) {
  var disc = nullDisc(sp.r0, sp.z0, sp.radius, sp.nRing, sp.nTheta);
  var np = disc.r.length;
  var f = channelBlocks(M.coils, disc.r, disc.z, sp.nu, sp.nv);
  var c0 = channelBlocks(M.coils, Float64Array.of(sp.r0),
                         Float64Array.of(sp.z0), sp.nu, sp.nv);
  var lim = null;
  if (sp.iMax) {
    lim = new Float64Array(NCH);
    if (typeof sp.iMax === 'number') lim.fill(sp.iMax);
    else for (var cL = 0; cL < NCH; cL++) lim[cL] = sp.iMax[cL];
  }
  var sol = fy.designNull({
    br: f.br, bz: f.bz, psi: c0.psi, nch: NCH, npts: np,
    bTol: sp.bTol, fluxTarget: sp.fluxTarget,
    weightNull: sp.weightNull, weightFlux: sp.weightFlux, lambda: sp.lam,
    xRef: sp.xRef || null, iMax: lim,
  });

  // achieved field on the disc, and on the grid for the picture
  var bpol = new Float64Array(np), bMax = 0, sum2 = 0;
  for (var p2 = 0; p2 < np; p2++) {
    var br = 0, bz = 0;
    for (var c5 = 0; c5 < NCH; c5++) {
      br += sol.x[c5] * f.br[c5 * np + p2];
      bz += sol.x[c5] * f.bz[c5 * np + p2];
    }
    bpol[p2] = Math.hypot(br, bz);
    bMax = Math.max(bMax, bpol[p2]);
    sum2 += bpol[p2] * bpol[p2];
  }
  var flux = 0;
  for (var c6 = 0; c6 < NCH; c6++) flux += sol.x[c6] * c0.psi[c6];

  var gb = gridBpolOf(sol.x);
  //: two different things, and conflating them would hide the useful one.
  //: `over`  — the bound was VIOLATED.  Under a bounded solve this should
  //:           stay empty; a non-empty one means the projection failed.
  //: `bind`  — the solution SITS ON the bound.  That is the answer to
  //:           "what is stopping this design", and it is a normal, healthy
  //:           state rather than an error.
  //: ★This page's contours are of |B_pol|, not of psi — the null IS the
  //: subject and there is no equilibrium to summarise.  The levels are
  //: capped near the CRITERION, not at the field's own maximum: |B_pol| by
  //: the coils is tens of times the null tolerance, and levels spread over
  //: that range would put the whole null between the first two lines.
  var caps = Math.min(gb.scale, 10 * sp.bTol);
  return { aturns: sol.x, iterations: sol.iterations,
           //: ★a design that ran out of iterations is a point on a descent,
           //: not a minimum, and it travels marked as such
           converged: sol.converged,
           bpol: bpol, discR: disc.r, discZ: disc.z,
           bMax: bMax, bRms: Math.sqrt(sum2 / np),
           bCentre: bpol[0], flux: flux, over: sol.over, bind: sol.bind,
           limits: lim, bpolGrid: gb.values, bpolScale: gb.scale,
           fluxSegs: fluxSegments(0, caps, gb.values, 14) };
}

function breakdownRun(msg) {
  var t0 = Date.now();
  //: solve FIRST — the old page computed `ms` in the same object literal as
  //: the solve and property order made it 0 ms forever
  var r = nullSolve(msg.spec);
  post({ type: 'breakdown', spec: msg.spec, ms: Date.now() - t0, result: r });
}

// --- dispatch --------------------------------------------------------------

self.onmessage = function (ev) {
  var msg = ev.data;
  try {
    // A worker has no localStorage, so it cannot see the page's choice —
    // the page tells it, and error text comes back in the right language.
    if (msg.lang) FyI18n.use(msg.lang);
    if (msg.cmd === 'init') return init(msg.machine);
    //: ★needs BOTH modules: the core solves, tglf closes.  They never call
    //: each other — chi crosses between them as plain numbers on this side —
    //: so no combined artifact is involved, and the second module is fetched
    //: on first use inside `transportTurb` rather than at init.
    if (msg.cmd === 'transport_turb') {
      if (!fy) return post({ type: 'error', message: FyI18n.t('worker.not_ready') });
      return transportTurb(msg);
    }
    if (!fy) return post({ type: 'error', message: FyI18n.t('worker.not_ready') });
    //: ★T-D7: the shape-control rows travel with the command that uses
    //: them, and are remembered for the criteria block — which is assembled
    //: by `summarize`, reached from three commands, and knows about none of
    //: them.  A command that carries no rows is a design that asked for
    //: none, so this is an assignment and not a merge.
    if (msg.cmd === 'solve' || msg.cmd === 'design' || msg.cmd === 'start'
        || msg.cmd === 'pulse')
      shapeCtl = msg.control || [];
    if (msg.cmd === 'solve') {
      var t0 = Date.now();
      var chan0 = Float64Array.from(msg.chan);
      var res = freeSolve(chan0, msg.prof, msg.ip, msg.solve);
      var sum = summarize(res, msg.prof, { surfaces: msg.surfaces || 0 });
      //: one solve, one answer — the vertical mode of THIS field, since
      //: nothing else is going to be computed after it
      if (sum.criteria && msg.vertical !== false)
        sum.criteria.vertical = verticalOf(res, sum.profiles, chan0);
      return post({ type: 'solve', result: sum, chan: chan0,
                    ms: Date.now() - t0 });
    }
    if (msg.cmd === 'evolve') {
      //: ★the turbulent tier needs the SECOND module, and it is fetched
      //: before the march rather than in the middle of it: a run that
      //: stopped at step 40 to download 323 KB would report a step time
      //: nobody can read.
      //: ★T-C13: the flux-match tier (4) is the SAME closure, so it needs
      //: the same module — and needs it more, because every Newton probe is
      //: a TGLF evaluation.
      if (((msg.spec.closure | 0) === 3 || (msg.spec.closure | 0) === 4)
          && !tglf) {
        return self.FyLite.loadExt('fylite_kernel_ext.wasm').then(function (inst) {
          tglf = inst;
          evolveRun(msg);
        }).catch(function (e) {
          post({ type: 'error', where: 'evolve',
                 message: String(e && e.message || e) });
        });
      }
      return evolveRun(msg);
    }
    if (msg.cmd === 'interp') return interpRun(msg);
    if (msg.cmd === 'zerod') return zerodRun(msg);
    if (msg.cmd === 'zerodb') return zerodPredictRun(msg);
    if (msg.cmd === 'zerodflux') return zerodFluxRun(msg);
    if (msg.cmd === 'zerodmc') return zerodMonteCarlo(msg);
    if (msg.cmd === 'design') return designRun(msg);
    if (msg.cmd === 'start') return startRun(msg);
    if (msg.cmd === 'pulse') return pulseRun(msg);
    if (msg.cmd === 'breakdown') return breakdownRun(msg);
    if (msg.cmd === 'recon') return reconRun(msg);
    if (msg.cmd === 'recon_mc') return reconMcRun(msg);
    if (msg.cmd === 'profile_fit') return profileFitRun(msg);
    if (msg.cmd === 'recon_series') return reconSeriesRun(msg);
  } catch (e) {
    post({ type: 'error', where: msg.cmd, message: String(e && e.message || e) });
  }
};

function interp1(x, v, at) {
  if (!x || !x.length) return 1;
  if (at <= x[0]) return v[0];
  for (var i = 1; i < x.length; i++)
    if (x[i] >= at) {
      var w = (at - x[i - 1]) / (x[i] - x[i - 1]);
      return v[i - 1] + w * (v[i] - v[i - 1]);
    }
  return v[v.length - 1];
}

// ==========================================================================
// 含时演化 — the core march, optionally alternating with the equilibrium
// ==========================================================================
//
// ★★What this replaces and why it is not the same page again.  The bar this
// one supersedes (`coupled`) alternated a free-boundary solve with a STEADY
// single-channel temperature solve and fed back one number, the pressure
// AMPLITUDE.  Everything a predictive run is actually asked for — a time
// axis, T_e and T_i with the exchange between them, the density, the current
// profile from its own diffusion, sources in watts — was outside it, in the
// kernel, unreached.  So this is a wire, not a new physics claim:
// `core_march_*` is the machine, `equilibrium_ladder` is the metric, and
// every source term below is an entry of the same binary.
//
// Three things a reader must be able to trust here, so each is stated in the
// page as well as in this file:
//
//   UNITS      rho is rho_tor in METRES, V' = dV/drho [m^2], T in eV,
//              n in m^-3, every source in W/m^3.  The energy balance is the
//              kernel's — capacity (3/2)V'n — which is what makes tau_E and
//              W_th reportable at all.  The old 1.5-D bar solved on a
//              normalised label with chi in m^2/s, i.e. an equation missing
//              a factor a^2, and no stored energy anywhere.
//   GEOMETRY   `miller` builds the metric from four scalars, `gfile` and
//              `device` take it from a SOLVED field through the ladder.  The
//              current channel is REFUSED on Miller geometry: it needs
//              <|grad rho|^2/R^2>, which four scalars do not determine.
//   CADENCE    `couple = 0` freezes the geometry for the whole march;
//              `couple = K` re-solves the equilibrium every K steps and
//              re-traces the ladder, carrying dV'/dt across the join
//              (`vprimeOld`) so the energy a moving volume takes with it is
//              not created out of nothing.

//: ★the free-boundary solve the coupled march re-runs each block, and its
//: tolerance in ONE place: `evFixedRefine` refuses to refine a field that
//: did not reach it, so the number the solve is asked for and the number
//: the refinement checks cannot drift apart.
var EV_FREE_OPTS = { maxIter: 600, relax: 0.3, tol: 1e-9 };
/**
 * The same options with the reader's own iteration cap, when the bar
 * carries one.
 *
 * ★The CAP is a control and the TOLERANCE is not.  What "converged" means
 * here is fixed by the refinement that reads the field; how long the solver
 * is allowed to look for it is a budget, and a reader who lowers it must
 * see the answer change from a number into "it did not get there" rather
 * than into a quietly worse number.
 */
function evFreeOpts(sp) {
  var m = sp && sp.freeMaxIter > 0 ? sp.freeMaxIter | 0 : EV_FREE_OPTS.maxIter;
  return { maxIter: m, relax: EV_FREE_OPTS.relax, tol: EV_FREE_OPTS.tol };
}
//: ★the accuracy the fixed-boundary refinement is HELD TO, and the reason
//: it is a pair rather than one number: the pointwise one (against the flux
//: span) says the field came back, the current one says the source that
//: produced it did.  Both are refusal thresholds — a refinement that misses
//: either is not used — and both are the closure criteria this feature was
//: written against, not numbers picked to make a run pass.
var EV_ZERO_PSI = 1e-3, EV_ZERO_IP = 0.01;
//: ★the zero test「cannot be tighter than the equilibrium it is comparing
//: with」(the comment at its gate says so) — and since v108 that field can
//: legitimately be a SETTLED one, floored at 1e-3…1e-2 by mask
//: quantisation jitter.  So the psi threshold scales with the source
//: field's own achieved residual: 3x covers every measured pairing (old
//: ladder: free 2.2e-4 → zero 5.1e-4, 1.5e-3 → 1.9e-3; settled tier:
//: 2.9e-3 → 5.2e-3, 6.8e-2 → 3.2e-2), while a refinement that genuinely
//: broke still lands far outside it.
var EV_ZERO_SCALE = 3.0;
var EV_QE = 1.602176634e-19;
var EV_MD = 3.3435837724e-27;
//: ★★the same deuteron in GRAMS, for the CGS family (`collision_rates`,
//: `exchange_power`, `rad_ion`).  Handing that entry the kilogram value is
//: not a small error: the rate carries `sqrt(m_i)` over `(m_e T_i + m_i
//: T_e)^1.5`, so a mass 1000x too small comes back as an exchange rate 1000x
//: too FAST — 0.2 ms instead of 0.15 s — which reads as a stiff coupling
//: rather than as a unit bug, and the heat pair then blows up at any usable
//: dt.  Measured here before it was fixed.
var EV_MD_G = 3.3435837724e-24;
var EV_MU0 = 4e-7 * Math.PI;
//: SI -> CGS on the way into the three entries that are written in it
var EV_M3_TO_CM3 = 1e-6, EV_ERG_TO_W = 0.1;

function evFill(n, v) { var a = new Float64Array(n); a.fill(v); return a; }

/** integral f dV over the ladder, trapezoid on `f * V'`. */
function evVolInt(rho, vprime, f) {
  var s = 0;
  for (var i = 1; i < rho.length; i++)
    s += 0.5 * (f[i] * vprime[i] + f[i - 1] * vprime[i - 1])
       * (rho[i] - rho[i - 1]);
  return s;
}

/** The enclosed volume, so a volume average is one call away. */
function evVolume(rho, vprime) {
  return evVolInt(rho, vprime, evFill(rho.length, 1));
}

/**
 * `df/dx`: second order central inside, FIRST order one-sided at the ends.
 *
 * ★★THE ENDS ARE FIRST ORDER AND THAT IS MEASURED, NOT LAZY.  The
 * three-point one-sided stencil is the textbook choice and it is NOT
 * resolution-stable on a packed transport ladder: on the bundled synthetic
 * g-file the last node came out at 0.923 / 0.952 / 0.960 of the header
 * current at 81 / 201 / 401 surfaces — still creeping — while every CENTRAL
 * node sat at 0.9676–0.9679 at all three.  It differences the quantity the
 * contour extraction is noisiest in exactly where the surfaces are most
 * crowded.  First order does not.
 *
 * ★This is the SAME six lines as `fylite.fyo.nonuniform_gradient` on the
 * other host, written out rather than delegated on either side so that
 * 「两个宿主逐位相同」 is a claim about ONE formula.  The cross-host judge is
 * `app/tests/validate-ip-reading.mjs`.
 */
function evNonuniformGradient(f, x) {
  var n = x.length, d = new Float64Array(n), i;
  for (i = 1; i < n - 1; i++) {
    var hs = x[i] - x[i - 1], hd = x[i + 1] - x[i];
    d[i] = (hs * hs * f[i + 1] + (hd * hd - hs * hs) * f[i]
            - hd * hd * f[i - 1]) / (hs * hd * (hd + hs));
  }
  d[0] = (f[1] - f[0]) / (x[1] - x[0]);
  d[n - 1] = (f[n - 1] - f[n - 2]) / (x[n - 1] - x[n - 2]);
  return d;
}

//: ★★T-C14 曾在这里放过一个自写的 `evOnPsin`——而仓里**早就有** `evRemap`
//: （`evInterp` 逐点，同一件事）。删掉了：一件事两份实现，迟早会有人只改一份。
//: ★保留的是那条**规矩**，它不在函数里而在这里：换梯子时按 **psi_N** 相对标，
//: 因为 `T` / `n` / `q` 是**强度量**、是通量标签的函数——重解之后是「同一团等
//: 离子体换了个标法」。T-M14 那条守恒再分配是给**壳层→梯子的源密度**用的
//: （积分必须守住），不是这里。★按 `rho` 插值才是真错误：rho 是长度，重解之后
//: 同一个 rho 是另一个面。★`psi` 不这样搬——它由刚解出的那张场自己给。

/**
 * One STATIONARY round's equilibrium half (T-C14 步 6): the free boundary
 * re-solved on the pressure this round produced, and the metric ladder
 * rebuilt on it.
 *
 * ★★It is the SAME arithmetic the coupled march runs once per block —
 * shape fit on `dp/dpsi_N`, `beta0` moved by the ratio of the two `beta_p`
 * under-relaxed, free solve, new ladder — lifted here so the two cannot
 * drift apart.  What differs is only WHEN: the march counts steps, this
 * counts rounds.
 *
 * ★Device geometry only.  A g-file's metric came from a file and there is
 * no boundary to re-solve; an analytic Miller has no free boundary at all
 * (and the outer loop is refused there for the current channel already).
 * Both are REPORTED as skipped with the reason rather than silently
 * producing a round that did nothing.
 */
function evStationaryEquilibrium(ctx, st, chan, prof, beta0, ipNow) {
  var sp = ctx.sp, geo = ctx.geo, n = geo.rho.length;
  //: ★★★THE CURRENT THIS STEP SOLVES FOR IS THE ONE THE psi LADDER CARRIES,
  //: not the one on the slider, and getting that wrong is not a detail — it
  //: is the difference between a loop that settles and a LIMIT CYCLE.
  //: Measured: with the equilibrium re-solved at the REQUESTED I_p while
  //: 步 4 left the ladder carrying only the non-inductive current (397 kA
  //: asked, 258 kA carried on `evolve-east-hmode`), each round pulled q one
  //: way and the next pulled it back — eight rounds ran, the loop's own Δp
  //: never came down, and 2 of the 9 free solves along the way ran their
  //: full 600 iterations without reaching tolerance.
  //: ★So one round refers to ONE current throughout — the one the ladder
  //: carries.  ★Since 步 4 now SOLVES for the loop voltage that holds the
  //: requested current, the two normally agree and this reads as「用请求
  //: 值」; it stops agreeing exactly when the voltage hit the reader's own
  //: range, and then the geometry follows the current that actually exists
  //: rather than the one that was asked for.  ★Falling back to the slider
  //: when 步 4 could not read one is stated rather than silent — `ipUsed`
  //: rides in the round's record.
  var ipUse = isFinite(ipNow) && Math.abs(ipNow) > 0 ? ipNow : sp.ip;
  if (sp.geometry !== 'device')
    return { skipped: sp.geometry === 'gfile'
      ? 'metric came from a g-file: no boundary to re-solve'
      : 'analytic geometry has no free boundary' };
  var pPa = new Float64Array(n), dp = new Float64Array(n);
  var pfT = null;
  if (ctx.pFastPar) {
    pfT = new Float64Array(n);
    for (var kf = 0; kf < n; kf++)
      pfT[kf] = (ctx.pFastPar[kf] + 2 * ctx.pFastPerp[kf]) / 3;
  }
  for (var k2 = 0; k2 < n; k2++)
    pPa[k2] = (st.ne[k2] * st.te[k2] + st.ni[k2] * st.ti[k2]) * EV_QE
            + (pfT ? pfT[k2] : 0);
  for (var k3 = 0; k3 < n; k3++) {
    var lo = Math.max(k3 - 1, 0), hi = Math.min(k3 + 1, n - 1);
    var dpsin = geo.psin[hi] - geo.psin[lo];
    dp[k3] = dpsin !== 0 ? (pPa[hi] - pPa[lo]) / dpsin : 0;
  }
  var fit = evFitShape(geo.psin, dp);
  var volNow = evVolume(geo.rho, geo.vprime);
  var pAvgT = volNow > 0 ? evVolInt(geo.rho, geo.vprime, pPa) / volNow : 0;
  var bpa = EV_MU0 * Math.abs(ipUse) / (2 * Math.PI * geo.a);
  var bpTarget = 2 * EV_MU0 * pAvgT / (bpa * bpa);
  var pAvgE = evEqPressure(ctx.eqFree, geo);
  var bpEq = isFinite(pAvgE) ? 2 * EV_MU0 * pAvgE / (bpa * bpa) : NaN;
  //: ★`beta0` is the solver's pressure/paramagnetic MIX, not a beta — moved
  //: by the RATIO of the two beta_p, under-relaxed, and both reported so a
  //: reader can see whether the alternation is closing or wandering.  Same
  //: rule, same relaxation control, as the coupled march.
  if (isFinite(bpTarget) && isFinite(bpEq) && bpEq > 0) {
    var want = beta0 * Math.pow(bpTarget / bpEq, sp.relax);
    beta0 = Math.min(0.95, Math.max(0.05, want));
  }
  //: ★★★AND THE GEOMETRY IS UNDER-RELAXED TOO, on the same factor and for
  //: the same reason.  Measured on `evolve-east-hmode` once 步 4 held the
  //: requested current: the minor radius stopped collapsing but started
  //: OSCILLATING with period two — 0.4015 -> 0.4623 -> 0.3816 -> 0.4378 ->
  //: 0.3682 m — because a wider plasma gives a lower beta_p, which the next
  //: round's fit turns back into a narrower one.  Δq was converging (9.9 ->
  //: 6.5 -> 5.1 %) while Δp was not (41.6 -> 49.5 -> 37.1 -> 25.0 %), which
  //: is what「几何在振」 looks like from the pressure's side.
  //: ★What is blended is the THREE NUMBERS the free solve actually runs on
  //: (`beta0` and the two shape exponents), not the ladder: a blended metric
  //: would be a geometry no equilibrium produced, while a blended INPUT is
  //: just a smaller step toward the same fixed point.
  var empNew = fit ? fit.emp : sp.emp, enpNew = fit ? fit.enp : sp.enp;
  var gRelax = sp.fmORelax === undefined ? 1 : sp.fmORelax;
  if (gRelax < 1 && prof) {
    beta0 = prof.beta0 + gRelax * (beta0 - prof.beta0);
    if (isFinite(prof.emp)) empNew = prof.emp + gRelax * (empNew - prof.emp);
    if (isFinite(prof.enp)) enpNew = prof.enp + gRelax * (enpNew - prof.enp);
  }
  var profNew = { beta0: beta0, emp: empNew, enp: enpNew, r0: sp.r0Src };
  var eq;
  try {
    eq = summarize(freeSolve(chan, profNew, ipUse, evFreeOpts(sp)),
                   profNew, {});
  } catch (e) {
    return { failed: String(e && e.message || e) };
  }
  //: ★★★AND THEN REFINED ON THE TRANSPORT'S OWN PRESSURE — the step the
  //: coupled march has always taken and this one was missing.  The free
  //: solve above runs the two-parameter plasma source `(emp, enp, beta0)`;
  //: `evFixedRefine` replaces it with `p'` and `FF'` as polynomials, so the
  //: pressure gradient the flux match produced goes in AS ITSELF.
  //: ★★Measured, and this is what the omission cost: without it the
  //: re-solve could not hold the matched pressure inside the family, and
  //: the plasma SHRANK every round — a 0.4015 -> 0.3213 -> 0.2845 ->
  //: 0.0406 m over four rounds on `evolve-east-hmode`, at which point the
  //: free solve ran its full 600 iterations at residual 2e-1.  The MARCH's
  //: own coupled re-solve on the same case and the same machine does not
  //: do that (beta0 0.850 -> 0.916, both beta_p closing) — the difference
  //: was this call.
  //: ★A refinement that FAILS is reported and the family's answer stands,
  //: same rule as the march: a round that silently fell back would be
  //: reporting a shape it did not use.
  var refined = null, refineWhy = null;
  if (sp.coupleFixed) {
    try {
      refined = evFixedRefine(eq, geo, st, sp, sp.degP, sp.degF, profNew,
                              pfT);
    } catch (eR) {
      refined = null;
      refineWhy = String(eR && eR.message || eR);
    }
    if (!refined && !refineWhy) refineWhy = FyI18n.t('e.err.refine');
  }
  if (refined) eq = refined.eq;
  var geoNew = refined ? refined.geo : evLadderFromSolve(eq, sp);
  //: the profiles, relabelled onto the new ladder — see the note above
  //: this function for WHY it is psi_N and not rho
  var psinOld = geo.psin;
  //: ★`q` rides along: it is `2 pi B0 rho / (dpsi/drho)`, a function of the
  //: flux label like the rest, and the outer loop's OWN convergence test
  //: compares it round to round.  ★It was nulled here at first — and then
  //: `dQ` was silently NaN from round two on, i.e. half the convergence
  //: test quietly stopped existing.  The next round's steady solve replaces
  //: it anyway; what this keeps alive is the COMPARISON.
  var carried = ['te', 'ti', 'ne', 'ni', 'nz', 'omega', 'q'];
  for (var c2 = 0; c2 < carried.length; c2++) {
    var key = carried[c2];
    if (st[key]) st[key] = evRemap(psinOld, st[key], geoNew.psin);
  }
  //: ★psi comes from the field that was just solved, not from the profile
  //: that rode on the old one
  var psiNew = new Float64Array(geoNew.rho.length);
  for (var p2 = 0; p2 < psiNew.length; p2++) psiNew[p2] = evPsiOf(geoNew, p2);
  st.psi = psiNew;
  //: ★only the label moves here.  Everything else the new ladder invalidates
  //: — the source arrays, the beam's chords, the cross-section — is the
  //: CALLER's to rebuild, because those live in the run's own closure.
  //: ★★This was found the hard way: without that rebuild the next round's
  //: TGLF was handed source arrays still sized for the OLD ladder and the
  //: kernel refused with「空指针或缓冲区长度不符」.  The coupled march has
  //: done this correctly all along (`rebuildBeam()` + `rebuildSources(t)`
  //: right after its own re-solve); this simply follows it.
  ctx.eqFree = eq;
  return { eq: eq, geo: geoNew, beta0: beta0, fit: fit, psinOld: psinOld,
           bpTarget: bpTarget, bpEq: bpEq, ipUsed: ipUse,
           refined: refined ? { ip: refined.ipSolved, ipTarget: ipUse,
                                resP: refined.fitP.relative,
                                resF: refined.fitF.relative } : null,
           refineWhy: refineWhy,
           free: freeReport(eq),
           aOld: geo.a, aNew: geoNew.a };
}

/**
 * One STATIONARY round's current half: the steady psi at the matched
 * profiles, then the sawtooth it may have made possible (T-C14 步 4 与 5).
 *
 * ★★WHY THIS IS A SEPARATE ROUND AND NOT PART OF THE MATCH.  The flux
 * matcher's unknowns are the two temperature gradients; `sigma` and the
 * bootstrap current are functions of the state it is solving for, so the
 * current profile cannot be inside its Jacobian without the target chasing
 * the answer — the same failure the burn showed and the same fix: Picard on
 * the outside, Newton on the inside.  The pedestal is already lagged this
 * way and so is the burn; this adds the current and the sawtooth to the
 * SAME split rather than inventing a second one.
 *
 * ★`dt = Infinity` IS the steady solve — the kernel's own statement
 * (`transport.rs`: "`dt = inf` solves the steady state"), not a large
 * number standing in for one.
 *
 * ★★AND THE LOOP VOLTAGE IS THE READER'S, NOT SOLVED FOR.  A steady current
 * profile is fixed by `sigma`, the non-inductive current and the BOUNDARY
 * FLUX RATE; `I_p` comes out, it does not go in.  Holding a requested `I_p`
 * needs the feedback loop (`ipctl`, T-C16) — so what this does is run at the
 * voltage the page was given and REPORT the current that results beside the
 * one that was asked for.  A step that quietly rescaled to the requested
 * `I_p` would be reporting a current no equation produced.
 *
 * Returns what moved, so the outer loop can judge convergence on it.
 */
function evStationaryCurrent(ctx, st) {
  var sp = ctx.sp, geo = ctx.geo, n = geo.rho.length;
  if (!geo.gm2) return null;
  var zList = ctx.zList || [1];
  //: ★the closure hook is the SAME one the march uses, so sigma and the
  //: non-inductive current are this state's own rather than a second
  //: opinion about it.  `channels.current` has to be on for `evClosure` to
  //: assemble `j_ni` at all, and on this tier it is not — so it is turned
  //: on for the length of this call and put back.  ★Stated rather than
  //: hidden: the reader's switch says「电流道」 for the MARCH, and this
  //: round is not a march.
  var was = ctx.channels.current;
  ctx.channels.current = true;
  //: ★★★NOT `dt = Infinity` — A LONG FINITE STEP, and the difference is the
  //: whole of 步 4.  At `dt = Infinity` the time derivative is gone, so the
  //: Ohmic term `sigma E` — which IS `-dpsi/dt` — is identically zero and
  //: the answer carries ONLY the non-inductive current, whatever the loop
  //: voltage says: measured on the Python side of the same kernel, the
  //: enclosed current there is exactly linear in `j_ni` and unchanged to
  //: 1e-12 by a decade of `sigma_par`, by the boundary flux, and by a
  //: boundary rate of -5 Wb/s.  ★A tokamak holding a flat top is NOT in
  //: that state: it is STATIONARY with `dpsi/dt = V_loop` uniform, which is
  //: what a long finite step with a boundary RATE reaches — measured, again
  //: on the same kernel: `dt = 1e5` and `dt = 1e7` give the same profile to
  //: 1e-5, and the enclosed current is AFFINE in the rate to five digits
  //: (slope 1.03502e6 / 1.03499e6 / 1.03499e6 A per Wb/s over three
  //: intervals).
  //: ★★★WHY THIS MATTERS, measured the hard way: with 步 4 returning the
  //: non-inductive current alone (264 kA against the 400 kA asked for) and
  //: 步 6 re-solving the free boundary for THAT current on the machine's own
  //: coils, the plasma SHRANK every round — a 0.4015 -> 0.3213 -> 0.2845 ->
  //: 0.0406 m over four rounds, at which point the free solve ran its full
  //: 600 iterations at residual 2e-1 and the profiles ran away to
  //: T_e(0) = 10 keV on a 4 cm plasma.  Solving 步 6 for the SLIDER's
  //: current instead just moved the inconsistency: q was pulled one way and
  //: pushed back the next round, and the loop became a limit cycle.  ★The
  //: fix is neither: it is to make 步 4 actually REACH the requested
  //: current, which is what an Ohmic transformer does and what upstream's
  //: `ActorSteadyStateCurrent` does.
  var dtSteady = evSteadyDt(ctx, geo);
  var res = null, err = null, probe = null, vLoop = 0, vClamped = false;
  var solveAt = function (rate) {
    return fy.coreMarch({
      rho: geo.rho, te: st.te, ti: st.ti,
      ni: evIonFlat(st, zList.length, n), z: zList,
      edgeNi: ctx.edgeNi, psi: st.psi,
      vprime: geo.vprime, gm3: geo.gm3, gm2: geo.gm2,
      fpol: geo.fpol, b0: geo.b0,
      //: the heat channel is OFF here — the match already solved it, and a
      //: steady heat solve on top would be a second answer to the question
      //: the Newton machine just answered
      qE: evFill(n, 0), qI: evFill(n, 0),
      sN: evSourceFlat(evFill(n, 0), zList.length, n),
      dt: dtSteady, dtTarget: 0, dtMin: 0, dtMax: 0,
      maxOuter: 1, tolSteady: sp.tolSteady, nCoupling: sp.nCoupling,
      edgeTe: st.te[n - 1], edgeTi: st.ti[n - 1],
      edgePsi: st.psi[n - 1], edgePsiRate: rate,
      b0Dot: 0, dPc: 0, tol: 1e-10, maxInner: 60,
      channels: { heat: false, density: false, current: true },
    }, function (state) { return evClosure(ctx, state); });
  };
  //: ★the same march with the coefficients HELD FIXED — the companion the
  //: record carries so another host can reproduce one solve exactly
  var solveAtFrozen = function (rate, sig, jni) {
    return fy.coreMarch({
      rho: geo.rho, te: st.te, ti: st.ti,
      ni: evIonFlat(st, zList.length, n), z: zList,
      edgeNi: ctx.edgeNi, psi: st.psi,
      vprime: geo.vprime, gm3: geo.gm3, gm2: geo.gm2,
      fpol: geo.fpol, b0: geo.b0,
      qE: evFill(n, 0), qI: evFill(n, 0),
      sN: evSourceFlat(evFill(n, 0), zList.length, n),
      dt: dtSteady, dtTarget: 0, dtMin: 0, dtMax: 0,
      maxOuter: 1, tolSteady: sp.tolSteady, nCoupling: sp.nCoupling,
      edgeTe: st.te[n - 1], edgeTi: st.ti[n - 1],
      edgePsi: st.psi[n - 1], edgePsiRate: rate,
      b0Dot: 0, dPc: 0, tol: 1e-10, maxInner: 60,
      channels: { heat: false, density: false, current: true },
    }, function () { return { sigmaPar: sig, jNi: jni }; });
  };
  var ipOf = function (r) {
    var a = r && r.psi ? evEnclosedIp(geo, r.psi) : null;
    return a ? a[a.length - 1] : NaN;
  };
  try {
    //: ★TWO SOLVES FIND THE VOLTAGE AND A THIRD RUNS ON IT.  The current is
    //: affine in the rate (measured above), so a zero-voltage solve and one
    //: probe determine the line exactly; the third solve is taken rather
    //: than the affine combination of the first two so that `q` comes from
    //: the kernel that produced the psi it belongs to.
    res = solveAt(0);
    var target = sp.ip;
    var vA = 0, iA = ipOf(res);
    //: ★the first probe is 0.1 V because that is the scale a tokamak flat
    //: top actually sits at (EAST's own case ships 0.15 V).
    var vB = 0.1;
    if (isFinite(iA) && isFinite(target) && Math.abs(target) > 0) {
      //: ★★A SECANT, NOT ONE EXTRAPOLATION, and the difference was measured:
      //: the enclosed current is affine in the rate for a FROZEN closure
      //: (five digits, on the Python side), but each solve here re-runs the
      //: closure, so the bootstrap moves with the q the last solve produced.
      //: One extrapolation off the first line overshot by 18 % (473 kA for a
      //: 400 kA target); a couple of secant steps close it.
      //: ★It stops when the READING is within 1 % of the request, and the
      //: reading is `evEnclosedIp` — the same quadrature the feedback loop
      //: uses, biased ~3 % low on this ladder — so what is held is the same
      //: quantity the rest of the page reports, not a second one.
      probe = solveAt(vB);
      var iB = ipOf(probe);
      for (var it = 0; it < 4; it++) {
        var slope = (iB - iA) / (vB - vA);
        if (!isFinite(slope) || Math.abs(slope) === 0) break;
        var vNext = vB + (target - iB) / slope;
        //: ★clamped to the reader's own loop-voltage range, and the clamp is
        //: REPORTED: a run that quietly drove a boundary condition the page
        //: could not have been asked for is a run nobody can check.
        var vMax = 5, vMin = -1;
        if (vNext > vMax) { vNext = vMax; vClamped = true; }
        if (vNext < vMin) { vNext = vMin; vClamped = true; }
        var rNext = solveAt(vNext);
        var iNext = ipOf(rNext);
        vA = vB; iA = iB; vB = vNext; iB = iNext; res = rNext;
        if (!isFinite(iNext)) break;
        if (Math.abs(iNext / target - 1) < 0.01) break;
        if (vClamped) break;
      }
      vLoop = vB;
    }
  } catch (e) {
    err = String(e && e.message || e);
  }
  if (!res) { ctx.channels.current = was; return { failed: err || 'steady current failed' }; }
  //: ★★★AND psi IS RE-ANCHORED TO THE EDGE IT CAME IN ON.  A stationary
  //: state with a loop voltage consumes flux, so a step `dtSteady` long
  //: raises psi by `V_loop * dtSteady` — thousands of Wb — and every
  //: quantity anyone reads off this profile (`q`, the enclosed current, the
  //: match's own metric) depends only on `dpsi/drho`.  Left unshifted the
  //: state would carry a number that grows without bound round after round,
  //: and on a g-file geometry — where 步 6 does not replace psi — it would
  //: keep growing.  ★The shift is a GAUGE choice and it is stated: what the
  //: solve determined is the profile's SHAPE, and the flux the transformer
  //: spent is reported as `vLoop` instead of being hidden inside psi.
  if (res.psi && res.psi.length === n) {
    var shift = st.psi[n - 1] - res.psi[n - 1];
    if (isFinite(shift) && shift !== 0)
      for (var sh = 0; sh < n; sh++) res.psi[sh] += shift;
  }
  //: ★★★UNDER-RELAXATION, kept from the diagnosis above: even with 步 4
  //: reaching the requested current, one round may throw the next one a long
  //: way.  ★A relaxed step does NOT move the fixed point — at the fixed
  //: point the stationary solve returns what it was given, so the blend
  //: returns it too.  ★It touches `q` and `psi` and nothing else: `q` is
  //: what the transport closure actually feels (TGLF's growth rates go
  //: through the magnetic shear).  ★The FIRST round is taken whole: its
  //: previous `q` came from the starting geometry, not from a solved round.
  var relax = sp.fmORelax === undefined ? 1 : sp.fmORelax;
  if (relax < 1 && !ctx.fmFirstCurrent && st.q && res.q
      && res.q.length === st.q.length) {
    for (var rq = 0; rq < res.q.length; rq++)
      res.q[rq] = st.q[rq] + relax * (res.q[rq] - st.q[rq]);
    for (var rp = 0; rp < res.psi.length && rp < st.psi.length; rp++)
      res.psi[rp] = st.psi[rp] + relax * (res.psi[rp] - st.psi[rp]);
  }
  ctx.fmFirstCurrent = false;
  //: ★★T-C14〔五〕 — EVERYTHING ANOTHER HOST NEEDS TO REDO THIS SOLVE, on
  //: the same terms as the beam's and the wave's `fylite:inputs`: a file
  //: carrying only the answer could not be held to the criterion「装配层同
  //: 口径」.  ★The two coefficients are the closure's OWN last pass
  //: (`sigma_par`, `j_ni`), because that is what the psi channel was handed
  //: — recomputing them on the other host would be a second answer to a
  //: different question.  ★Only the LAST round is kept: the rounds share
  //: their arithmetic and eight copies of it would be eight times the file
  //: for no extra claim.
  //: ★★★AND A FROZEN COMPANION SOLVE, so「两个宿主同一个解」can be an EXACT
  //: claim rather than an approximate one.  The march above re-runs the
  //: closure every coupling pass, so the `sigma_par` / `j_ni` recorded
  //: below are its LAST pass — and a second host solving with those frozen
  //: lands one Picard pass away, measured at 1.3 % in psi and 0.94 % in
  //: I_p.  That gap is not a discrepancy between the two solvers, it is the
  //: difference between two QUESTIONS, and a tolerance wide enough to
  //: swallow it would no longer catch the errors this gate exists for.
  //: ★So the file carries the answer to the question the other host is
  //: actually asked: the same solve with those coefficients held fixed.
  //: ★It is a COMPANION and is labelled one — the run itself keeps `res`,
  //: and how far the frozen solve sits from it goes in the record too,
  //: because that distance IS「内层的耦合收敛了没有」.
  var frozenSig = ctx.lastSigma ? Float64Array.from(ctx.lastSigma) : null;
  var frozenJni = ctx.lastJni ? Float64Array.from(ctx.lastJni) : null;
  var frozenPsi = null, frozenGap = null;
  if (frozenSig && frozenJni) {
    try {
      var fr = solveAtFrozen(vLoop, frozenSig, frozenJni);
      if (fr && fr.psi) {
        frozenPsi = Float64Array.from(fr.psi);
        var fShift = st.psi[n - 1] - frozenPsi[n - 1];
        if (isFinite(fShift) && fShift !== 0)
          for (var fk = 0; fk < n; fk++) frozenPsi[fk] += fShift;
        var num = 0, den = 0;
        for (var fg = 0; fg < n; fg++) {
          num = Math.max(num, Math.abs(frozenPsi[fg] - res.psi[fg]));
          den = Math.max(den, Math.abs(res.psi[fg]));
        }
        frozenGap = den > 0 ? num / den : 0;
      }
    } catch (eF) { frozenPsi = null; }
  }
  ctx.steadyRecord = {
    rho: geo.rho, vprime: geo.vprime, gm3: geo.gm3, gm2: geo.gm2,
    fpol: geo.fpol, b0: geo.b0,
    te: Float64Array.from(st.te), ti: Float64Array.from(st.ti),
    ni: evIonFlat(st, zList.length, n), z: zList, edgeNi: ctx.edgeNi,
    psiIn: Float64Array.from(st.psi),
    edgePsi: st.psi[n - 1], edgePsiRate: vLoop, dt: dtSteady,
    sigmaPar: ctx.lastSigma ? Float64Array.from(ctx.lastSigma) : null,
    jNi: ctx.lastJni ? Float64Array.from(ctx.lastJni) : null,
    tolSteady: sp.tolSteady, nCoupling: sp.nCoupling,
    psiOut: frozenPsi || Float64Array.from(res.psi),
    psiOutRun: Float64Array.from(res.psi),
    frozen: !!frozenPsi, frozenGap: frozenGap,
    q: res.q ? Float64Array.from(res.q) : null,
  };
  var psiOld = st.psi;
  st.psi = res.psi; st.q = res.q;
  //: ★★THE FLAG STAYS ON ACROSS THE SAWTOOTH, and this was a real defect
  //: the gate caught: `evSawtooth` refuses without `channels.current`
  //: (rightly — with q prescribed there is nothing for a crash to rebuild),
  //: and restoring the flag one line too early made it refuse EVERY round.
  //: Measured: q(0) fell 0.788 -> 0.683 over two rounds with a sawtooth
  //: switched ON and not one crash.  The current round and the crash that
  //: follows it are ONE round, so the flag spans both.
  var saw = evSawtooth(ctx, st);
  ctx.channels.current = was;
  var ipArr = evEnclosedIp(geo, st.psi);
  return {
    psiRepaired: res.psiRepaired,
    q0: st.q ? evQAxis(ctx, st.q) : NaN,
    sawtooth: saw,
    ip: ipArr ? ipArr[ipArr.length - 1] : null,
    ipRequested: sp.ip,
    //: ★★the voltage this step had to find to hold the requested current,
    //: and whether the reader's range cut it off.  It is the number 步 4
    //: PRODUCES — the flat top's flux consumption — and it is reported
    //: rather than folded away.
    vLoop: vLoop, vLoopClamped: vClamped, dtSteady: dtSteady,
    dPsi: (function () {
      var num = 0, den = 0;
      for (var i = 0; i < n; i++) {
        num = Math.max(num, Math.abs(st.psi[i] - psiOld[i]));
        den = Math.max(den, Math.abs(psiOld[i]));
      }
      return den > 0 ? num / den : 0;
    }()),
  };
}

/**
 * How long a step counts as「稳态」 for 步 4.
 *
 * ★★A NUMBER WITH A REASON rather than a big constant: the current channel
 * relaxes on the resistive time `tau_R ~ mu0 a^2 sigma`, so a step a
 * thousand of those long has reached the stationary state whatever the
 * machine.  ★Measured on the Python side of the same kernel: `dt = 1e5` and
 * `dt = 1e7` give the same profile to 1e-5 on a ladder whose tau_R is
 * ~5 s — i.e. anything past a few hundred tau_R is the same answer.
 * ★`Infinity` is NOT the same answer: it drops the time derivative and with
 * it the entire Ohmic current (see `evStationaryCurrent`).
 */
function evSteadyDt(ctx, geo) {
  var sig = ctx.lastSigma, sMax = 0;
  if (sig) for (var i = 0; i < sig.length; i++)
    if (sig[i] > sMax) sMax = sig[i];
  if (!(sMax > 0)) sMax = 1e8;
  var a = geo.a > 0 ? geo.a : 1;
  return Math.max(1e3, 1e3 * EV_MU0 * a * a * sMax);
}

/**
 * The I_p feedback loop: the boundary flux rate that holds the requested
 * plasma current (T-C16, upstream's `ActorControllerIp`).
 *
 * ★★★THE ERROR IS A RATIO, AND THAT IS THE WHOLE DESIGN.  `evEnclosedIp`
 * reads about 3 % LOW against a prescribed current — the ladder's own
 * quadrature (V′ 0.7 %, gm2 1.1 %), measured NOT to close with resolution
 * (0.9664 → 0.9682 as the ladder edge goes 0.95 → 0.9999, and the reading
 * itself is flat at 0.9676 across 81/201/401 surfaces).  A loop closed on
 * the ABSOLUTE reading would therefore sit there, converged and content, on
 * a current 3 % away from the one that was asked for.  So the loop takes
 * its OWN first reading as the calibration and holds the RATIO: whatever
 * the ladder's bias is, it is in both terms and cancels.
 *
 * ★What it does NOT do is hide the bias — the calibration ratio is
 * reported, in the readings and in the file.  A correction nobody can see
 * is a correction nobody can check.
 *
 * ★PI, not PID.  The 5:1 proportional-to-integral ratio is upstream's own
 * ITER case (`P = 10 Omega`, `I = 2 Omega`, **`D = 0`**); a derivative term
 * on a quantity this noisy would be differentiating the ladder's
 * quadrature.  The absolute scale is the reader's, on the page, because a
 * gain nobody can see is a model nobody can check.
 *
 * ★The integral is clamped to the loop-voltage slider's own range: an
 * integrator that may wind anywhere will, and the run then reports a
 * boundary condition the page could not have been asked for.
 */
function evIpControl(ctx, st, dt, t) {
  var sp = ctx.sp, c = ctx.ipCtl;
  var arr = evEnclosedIp(ctx.geo, st.psi);
  if (!c || !arr) return;
  var meas = arr[arr.length - 1];
  //: ★the calibration: the loop's own first reading against the request.
  //: Taken here rather than passed in, so a resumed march re-calibrates on
  //: the state it actually restarted from.
  //: ★the set point at THIS time — a constant unless the waveform is
  //: driving it (`waveip`), in which case the loop is tracking a schedule
  var target = ctx.ipTargetNow === undefined ? sp.ip : ctx.ipTargetNow;
  if (c.ratio0 === null) {
    //: ★the calibration is taken against the set point the run STARTED on,
    //: not against whatever the waveform has reached later: it is a
    //: property of the ladder, not of the schedule
    c.ratio0 = target !== 0 ? meas / target : 1;
    if (!isFinite(c.ratio0) || c.ratio0 === 0) c.ratio0 = 1;
  }
  var want = target * c.ratio0;
  //: relative error, positive when the current is BELOW target — so a
  //: positive gain raises the loop voltage, which raises the current
  var err = want !== 0 ? (want - meas) / Math.abs(want) : 0;
  c.integral += err * (dt > 0 ? dt : 0);
  var corr = c.kp * err + c.ki * c.integral;
  //: ★the clamp is on the OUTPUT, and the integral is unwound with it
  //: rather than being left to grow behind a saturated output
  var lo = -1, hi = 5, base = ctx.vLoopBase || 0;
  var vNew = base + corr;
  if (vNew > hi) {
    vNew = hi;
    if (c.ki > 0) c.integral = (hi - base - c.kp * err) / c.ki;
  } else if (vNew < lo) {
    vNew = lo;
    if (c.ki > 0) c.integral = (lo - base - c.kp * err) / c.ki;
  }
  ctx.vLoopNow = vNew;
  c.last = { t: t, ip: meas, want: want, err: err, vLoop: vNew,
             integral: c.integral };
  c.log.push(c.last);
}

/**
 * The toroidal plasma current enclosed by each ladder surface [A].
 *
 *     I(rho) = V' <|grad rho|^2/R^2> (dpsi/drho) / (2 pi mu0)
 *
 * ★★THE CONSTANT IS READ OFF THE KERNEL'S OWN OPERATOR, not fitted.
 * `transport::solve_psi` carries the current-diffusion channel on the metric
 * `M = V' gm2 / (4 pi^2 F)` with psi in Wb/rad, which fixes `1/(2 pi mu0)`.
 * Measured against a g-file that states its own current, the near misses
 * land at 6.08x (`1/mu0`), 0.154x (`1/(4 pi^2 mu0)`) and 38.2x
 * (`2 pi/mu0`) — the constant is IDENTIFIED, and the judge pins those three
 * too, so a future edit cannot "fix" the residual by moving it.
 *
 * ★★AND IT READS 3.2 % LOW, WHICH DOES NOT GO AWAY.  Pushing the ladder's
 * outer edge from psi_N = 0.95 to 0.9999 moves the ratio only 0.9664 →
 * 0.9682: it is not current sitting outside the last surface, it is the
 * ladder's own quadrature (V′ 0.7 %, gm2 1.1 %).  **So a feedback loop must
 * control the RATIO to its own t = 0 reading, never the absolute value** —
 * otherwise it drives steadily onto an I_p that is 3 % wrong.  Every place
 * this number is shown says so beside it.
 *
 * ★★★AND THE GAUGE IS THE WHOLE OF THIS PARAGRAPH.  The formula above is
 * for psi in **Wb/rad**, which is what the ladder on the OTHER host carries
 * (`fylite.fyo`).  THIS host's psi is the app's own convention — TOTAL flux
 * in Wb, `fylite:psi_convention = full_flux_Wb_axis_max`, which `evPsiOf`
 * builds straight from the equilibrium's `psiAxis`/`psiBnd` — i.e. `2 pi`
 * times the other one.  So the divisor here is `4 pi^2 mu0`, not
 * `2 pi mu0`.
 * ★★This was NOT reasoned out in advance: the first run of the cross-host
 * judge reported the browser at **6.51x** the requested current, which is
 * `2 pi` times 1.036 — the gauge, caught by the one gate written to catch
 * exactly a `2 pi` slip.  Both numbers are kept in the comment because the
 * next person to touch either host's psi needs to know which gauge they are
 * in, and「差了 2π」 is invisible in a profile shape.
 *
 * Returns `null` when the metric has no `gm2`.  Every tier states one since
 * S-2c 批二; a reading that guessed would be a current nobody computed.
 */
function evEnclosedIp(geo, psi) {
  if (!geo || !geo.gm2 || !psi) return null;
  var n = geo.rho.length;
  if (n < 3 || psi.length !== n) return null;
  //: ★a flux that is identically zero is not a flux this reads a current
  //: off — it is a tier that never solved one.  Before S-2c 批二 the `gm2`
  //: test above happened to exclude that case; now that every tier states a
  //: gm2, the zero flux has to be refused on its own account, or the
  //: analytic tier would report I_p = 0 where it used to report nothing.
  var live = false;
  for (var k = 0; k < n && !live; k++) live = psi[k] !== 0;
  if (!live) return null;
  var d = evNonuniformGradient(psi, geo.rho), out = new Float64Array(n);
  //: 4 pi^2 = (2 pi)^2: one factor is the formula's, the other converts
  //: this host's TOTAL-flux psi to the per-radian psi the formula is in
  var denom = 4 * Math.PI * Math.PI * EV_MU0;
  for (var i = 0; i < n; i++)
    out[i] = geo.vprime[i] * geo.gm2[i] * d[i] / denom;
  return out;
}

/**
 * A deposition shape carrying `total` watts (or particles/s).
 *
 * ★Normalised by the VOLUME INTEGRAL, which is the only way a slider in MW
 * means megawatts.  The old bar's "heating power density peak" was a number
 * in arbitrary units — its own caption said so — and nothing downstream
 * could be a power.
 */
function evDeposit(rho, vprime, centre, width, total) {
  var n = rho.length, edge = rho[n - 1], g = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    var x = (rho[i] / edge - centre) / Math.max(width, 1e-3);
    g[i] = Math.exp(-x * x);
  }
  var norm = evVolInt(rho, vprime, g);
  if (!(norm > 0)) return new Float64Array(n);
  for (var k = 0; k < n; k++) g[k] *= total / norm;
  return g;
}

/**
 * ★★THE BEAM, replacing the prescribed Gaussian (T-M2).
 *
 * What the bar had was a Gaussian in rho with a centre and a width, and a
 * separate I_CD slider: the deposition was a SHAPE the reader drew, so a
 * density scan moved the plasma and not the place the beam stopped — which
 * is exactly backwards, and the one thing a beam model is for.
 *
 * ★★Every number below is the kernel's.  The rays over the beam's finite
 * cross-section, their geometry, `pitch(R) = R_tan/R`, where the profile is
 * read along a ray, the Janev stopping cross-section, the attenuation and
 * the shell binning are ONE call (`beam_deposit`); the Stix critical energy
 * and slowing time are another (`beam_slowing`); the electron/ion power
 * split and tau_eff another (`beam_energy_partition`); the electron
 * shielding another (`beam_shielding`); the driven current another
 * (`beam_current`); the first-orbit-loss mask another
 * (`first_orbit_loss`).  What this function is, is the ASSEMBLY — and it is
 * the same assembly `fylite.scenario.model.nbi.deposit` performs, deliberately,
 * so the gate can put the two side by side.
 *
 * ★★IT NEEDS A psi_N MAP ON THE (R, Z) GRID, so it exists on the two tiers
 * that have one — the solved equilibrium and an imported g-file — and NOT on
 * Miller.  A Miller shape has no psi map to attenuate along; a beam model
 * fed a made-up one would be reporting a stopping depth nobody computed.
 */
function evBeamDeposit(field, geo, st, sp) {
  var nsh = Math.max(4, sp.beamShells | 0), i, c;
  var span = field.psiBnd - field.psiAxis;
  if (!isFinite(span) || span === 0)
    throw new Error(FyI18n.t('e.err.beam_nopsi'));
  var fr = [Math.max(0, sp.beamF1), Math.max(0, sp.beamF2),
            Math.max(0, sp.beamF3)];
  if (!(fr[0] + fr[1] + fr[2] > 0)) throw new Error(FyI18n.t('e.err.beam_fractions'));
  //: ★★the assembly is `case.rs::beam_case` (FYL-DESIGN-16 K-3, 2026-09-05):
  //: the shell table on the psi map, the profiles at the shell centres, the
  //: trapped fraction and the shielding, then per energy component the
  //: deposition · first-orbit-loss mask · slowing-down · electron/ion split ·
  //: fast-ion pressure and its pitch split · torque · driven current — ONE
  //: recipe for this page and for `fylite.scenario.model.nbi.deposit` (the
  //: kernel repository's `test_beam_code.py` holds it to the old flat
  //: assembly bit for bit).  What stays here is the PLAN: the field as an
  //: `fyo:equilibrium` document (q on the ladder's own psi_N, which the case
  //: reads beside it), the state as `core_profiles`, the beam as the DD's
  //: `nbi` unit — and the echo of the inputs the report re-runs on.
  var ng = field.nr * field.nz, psin2d = new Float64Array(ng);
  for (i = 0; i < ng; i++) psin2d[i] = (field.psi[i] - field.psiAxis) / span;
  var rg = new Array(field.nr), zg = new Array(field.nz);
  for (i = 0; i < field.nr; i++) rg[i] = field.r0 + field.dr * i;
  for (i = 0; i < field.nz; i++) zg[i] = field.z0 + field.dz * i;
  var np0 = geo.psin.length, qAbs = new Array(np0);
  for (i = 0; i < np0; i++) qAbs[i] = Math.abs(geo.q ? geo.q[i] : 1);
  var eqDoc = {
    vacuum_toroidal_field: { r0: Math.abs(geo.r0) || 1, b0: Math.abs(geo.b0) || 1 },
    time_slice: {
      global_quantities: { magnetic_axis: { r: field.axisR, z: field.axisZ },
                           psi_axis: field.psiAxis, psi_boundary: field.psiBnd },
      profiles_1d: { q: qAbs, 'fylite:psi_norm': Array.from(geo.psin) },
      profiles_2d: { grid: { dim1: rg, dim2: zg }, psi: Array.from(field.psi) } },
    'fylite:limiter': { r: Array.from(field.limR), z: Array.from(field.limZ) } };
  var cp = { profiles_1d: { grid: { 'fylite:psi_norm': Array.from(geo.psin) },
                            electrons: { density: Array.from(st.ne),
                                         temperature: Array.from(st.te) } } };
  var unit = { name: 'nbi', energy: { data: sp.beamEnergy },
               power_launched: { data: sp.beamPower },
               beam_power_fraction: { data: fr },
               species: { a: sp.beamMass, z_n: 1 },
               beamlets_group: [{ tangency_radius: sp.beamRtan, position: { z: sp.beamZ },
                                  direction: sp.beamDir, width_horizontal: sp.beamWidth,
                                  width_vertical: sp.beamWidth }] };
  var settings = { n_shells: nsh, stopping_model: sp.beamStopping, n_samples: sp.beamSamples,
                   n_width_r: sp.beamNWidth, n_width_z: sp.beamNWidth,
                   orbit_losses: sp.beamOrbit ? 1 : 0, zeff: sp.zeff, impurity_form: 'exp',
                   n_theta: 181 };
  var rec = fy.complete('code/beam', { settings: settings,
                                       inputs: { equilibrium: eqDoc, core_profiles: cp,
                                                 nbi: { unit: [unit] } } });
  var F = function (k) { return fieldFlat(rec, k); };
  var X = function (k) { return rec.facts[k].value; };
  var src = rec.fields.core_sources.source['0'].profiles_1d;
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  var nc = rec.dims.n_components | 0;
  var cAbs = F('component_absorbed'), cRet = F('component_retained'),
      cPitch = F('component_pitch'), cMask = F('component_orbit_mask'),
      cE = F('component_energy'), cP = F('component_power'),
      cShine = F('component_shinethrough'), cOrbit = F('component_orbit_loss'),
      cAbsF = F('component_absorbed_fraction'), cCur = F('component_current');
  var records = [];
  for (c = 0; c < nc; c++) {
    var sl = function (a) { return Array.from(a.subarray(c * nsh, (c + 1) * nsh)); };
    records.push({ energy: cE[c], power: cP[c], absorbed: sl(cAbs), retained: sl(cRet),
                   orbitMask: sp.beamOrbit ? sl(cMask) : null, pitch: sl(cPitch),
                   shinethrough: cShine[c], orbitLoss: cOrbit[c],
                   absorbedFraction: cAbsF[c], current: cCur[c] });
  }
  //: the input echo the report carries — the profile held to psi_N = 1 as the
  //: re-run oracle reads it (a clamped interpolation, so the same numbers)
  var hold = geo.psin[np0 - 1] < 1 - 1e-9, nprof = hold ? np0 + 1 : np0;
  var psinProf = new Float64Array(nprof), neP = new Float64Array(nprof),
      teP = new Float64Array(nprof);
  for (i = 0; i < np0; i++) {
    psinProf[i] = geo.psin[i]; neP[i] = Math.max(st.ne[i], 1e16); teP[i] = Math.max(st.te[i], 1);
  }
  if (hold) { psinProf[np0] = 1; neP[np0] = neP[np0 - 1]; teP[np0] = teP[np0 - 1]; }
  var edges = F('psin_edges'), rminC = F('rminor');
  return {
    psin: flat(src.grid['fylite:psi_norm']), edges: edges, dvolume: F('dvolume'), area: F('area'),
    rminor: rminC, rmajor: F('rmajor'), eps: F('eps'), ft: F('ft'),
    shielding: F('shielding'), shieldingG: F('shielding_g'), zeff: F('zeff'), zsum: F('zsum'),
    pDep: F('p_dep'), pE: flat(src.electrons.energy), pI: flat(src.total_ion_energy),
    pFast: F('p_fast'), pitch: F('pitch'), tauEff: F('tau_eff'),
    pPar: F('p_fast_par'), pPerp: F('p_fast_perp'), torque: F('torque'),
    torqueTotal: X('torque_total'),
    jNbi: flat(src.j_parallel),
    pInjected: X('p_injected'), pAbsorbed: X('p_absorbed'),
    shinethrough: X('shinethrough'), orbitLossFraction: X('orbit_loss_fraction'),
    iNbi: X('i_nbi'), fastEnergy: X('fast_energy'),
    components: records,
    inputs: { r0: field.r0, z0: field.z0, dr: field.dr, dz: field.dz,
              nr: field.nr, nz: field.nz, psin2d: psin2d,
              psinProf: psinProf, ne: neP, te: teP, rStart: field.r0 + field.dr * (field.nr - 1),
              tangencyRadius: sp.beamRtan, zHeight: sp.beamZ,
              widthR: sp.beamWidth, widthZ: sp.beamWidth,
              direction: sp.beamDir, nWidthR: sp.beamNWidth,
              nWidthZ: sp.beamNWidth, nSamples: sp.beamSamples,
              mass: sp.beamMass, stopping: sp.beamStopping,
              impurityForm: 'exp', aEdge: X('a_edge'),
              b0: Math.abs(geo.b0) || 1, r0Field: Math.abs(geo.r0) || 1,
              orbit: !!sp.beamOrbit },
  };
}

/**
 * The beam's record, flattened for the wire and for the file.
 *
 * ★★THE INPUTS TRAVEL WITH THE OUTPUTS.  A deposition profile whose reader
 * cannot re-run `beam_deposit` on the same psi map, the same chord and the
 * same n_e / T_e is a picture, not a claim — and the gate's oracle is
 * precisely that re-run.  The psi_N map is the big array here and it is
 * written whole: a beam is attenuated along a chord through it, so nothing
 * smaller identifies the calculation.
 */
function evBeamReport(b, sp) {
  var arr = function (a) { return Array.from(a); };
  return {
    psin: arr(b.psin), edges: arr(b.edges), dvolume: arr(b.dvolume),
    area: arr(b.area), rminor: arr(b.rminor), rmajor: arr(b.rmajor),
    eps: arr(b.eps), ft: arr(b.ft),
    //: ★the shielding is reported as ITSELF, beside the current it is
    //: already inside — not multiplied into one number.  `g` is the
    //: shielding function, `factor` the surviving fraction 1 - (Z_b/Z_eff)G.
    shielding: arr(b.shielding), shieldingG: arr(b.shieldingG),
    zeff: arr(b.zeff), zsum: arr(b.zsum),
    pDep: arr(b.pDep), pE: arr(b.pE), pI: arr(b.pI), pFast: arr(b.pFast),
    //: ★T-M12: the pitch-preserving split and the prompt torque, per shell.
    //: The gate recomputes every one of these from the per-component
    //: records in this same file — same pd, same pitch, same rmajor — so a
    //: torque that did not come out of the SAME `beam_deposit` call as the
    //: pressure would fail there, not here.
    pPar: arr(b.pPar), pPerp: arr(b.pPerp), torque: arr(b.torque),
    torqueTotal: b.torqueTotal,
    pitch: arr(b.pitch), tauEff: arr(b.tauEff), jNbi: arr(b.jNbi),
    pInjected: b.pInjected, pAbsorbed: b.pAbsorbed,
    //: ★★T-M11: the deposited power the LADDER CANNOT REACH, and the
    //: surface it stops at.  `pAbsorbed` is the shell quadrature over the
    //: whole plasma and the march integrates over psi_N <= this edge, so
    //: without this row the difference between the two numbers cannot be
    //: split into "a different domain" and "a different discretisation" —
    //: and only the second of those refines away.
    pOutsideLadder: b.pOutsideLadder === undefined ? null : b.pOutsideLadder,
    ladderEdgePsin: b.ladderEdgePsin === undefined ? null : b.ladderEdgePsin,
    //: ★T-M14: the nodal source the march's ladder integral is the
    //: trapezoid of — the conservative remap's own output, exported so the
    //: quadrature gate can re-take the trapezoid outside this code
    onLadder: b.onLadder ? arr(b.onLadder) : null,
    //: ★shine-through is its OWN fraction, not a haircut on the power: a
    //: beam that misses the plasma and one that is absorbed inefficiently
    //: are different machines
    shinethrough: b.shinethrough, orbitLossFraction: b.orbitLossFraction,
    iNbi: b.iNbi, fastEnergy: b.fastEnergy,
    components: b.components, cadence: b.cadence,
    inputs: {
      grid: { r0: b.inputs.r0, z0: b.inputs.z0, dr: b.inputs.dr,
              dz: b.inputs.dz, nr: b.inputs.nr, nz: b.inputs.nz },
      psin2d: arr(b.inputs.psin2d),
      psinProf: arr(b.inputs.psinProf), ne: arr(b.inputs.ne),
      te: arr(b.inputs.te), rStart: b.inputs.rStart,
      tangencyRadius: b.inputs.tangencyRadius, zHeight: b.inputs.zHeight,
      widthR: b.inputs.widthR, widthZ: b.inputs.widthZ,
      direction: b.inputs.direction, nWidthR: b.inputs.nWidthR,
      nWidthZ: b.inputs.nWidthZ, nSamples: b.inputs.nSamples,
      mass: b.inputs.mass, stopping: b.inputs.stopping,
      impurityForm: b.inputs.impurityForm, aEdge: b.inputs.aEdge,
      b0: b.inputs.b0, r0Field: b.inputs.r0Field, orbit: b.inputs.orbit,
      power: sp.beamPower, energy: sp.beamEnergy,
      fractions: [sp.beamF1, sp.beamF2, sp.beamF3],
    },
  };
}


/**
 * ★★HOW MUCH OF A SHELL-BINNED DEPOSITION LIES OUTSIDE THE LADDER (T-M11).
 *
 * The metric ladder stops at `edgePsin` (0.95) and the deposition shells
 * run to psi_N = 1, so the two quadratures over "the same" absorbed power
 * are not over the same plasma: whatever is deposited beyond the ladder's
 * outermost surface is power the march never receives.  That part is a
 * CALIBRE difference — refining either grid does not remove it — and it has
 * to be measured before the rest of the gap can be called discretisation.
 *
 * ★It is measured, not estimated.  `shell_table` is called a second time on
 * the deposition edges WITH `edgePsin` inserted as a knot, so the split of
 * the straddling shell is the kernel's own traced volume and not a linear
 * guess; the sub-shells inherit their parent shell's density (which IS what
 * a shell quadrature says the density is there), and the sum is
 * `shell_sum`.  Nothing here re-spells a volume.
 */
function evOutsideLadder(field, edges, pDep, edgePsin) {
  var nsh = edges.length - 1, i;
  if (!(edgePsin > edges[0]) || !(edgePsin < edges[nsh])) return null;
  //: the deposition edges with the ladder's boundary inserted, deduplicated
  var merged = [], eps = 1e-12;
  for (i = 0; i <= nsh; i++) {
    if (merged.length && Math.abs(edges[i] - merged[merged.length - 1]) < eps)
      continue;
    if (edgePsin > merged[merged.length - 1] + eps && edgePsin < edges[i] - eps)
      merged.push(edgePsin);
    merged.push(edges[i]);
  }
  var span = field.psiBnd - field.psiAxis;
  var ng = field.nr * field.nz, psin2d = new Float64Array(ng);
  for (i = 0; i < ng; i++) psin2d[i] = (field.psi[i] - field.psiAxis) / span;
  var t2 = fy.shellTable({
    r0: field.r0, z0: field.z0, dr: field.dr, dz: field.dz,
    nr: field.nr, nz: field.nz, psin2d: psin2d,
    axisR: field.axisR, axisZ: field.axisZ,
    limR: field.limR, limZ: field.limZ,
    levels: Float64Array.from(merged), nTheta: 181 });
  var m = merged.length - 1;
  var sub = new Float64Array(m), dvSub = new Float64Array(m);
  for (i = 0; i < m; i++) {
    var c = 0.5 * (merged[i] + merged[i + 1]);
    dvSub[i] = Math.max(t2.dvolume[i], 0);
    if (c <= edgePsin) continue;
    //: the parent deposition shell this sub-shell sits in
    var k = 0;
    while (k < nsh - 1 && c > edges[k + 1]) k += 1;
    sub[i] = pDep[k];
  }
  return { power: fy.shellSum(sub, dvSub), edgePsin: edgePsin,
           volume: fy.shellSum(evFill(m, 1), dvSub) };
}

/**
 * ★★THE LOWER-HYBRID WAVE (T-M10) — the other half of the wave sources the
 * beam batch left unwired.
 *
 * ★★Every number below is the kernel's, and the whole per-launcher chain is
 * ONE call: which surfaces the wave can reach, where each end of the
 * launched band resonates, the damping layer between them, the Fisch
 * current-drive weighting, the normalisation and the sigma envelope are
 * `lh_deposit` — reached through `code/wave` (2026-09-05), which also reports
 * the resonant temperature and the local CD weight beside it, so no second
 * host spells either.  This side hands over the PLAN, and it is the same plan
 * `fylite.scenario.model.lh.deposit` performs.
 *
 * ★★IT NEEDS THE SAME psi_N MAP THE BEAM NEEDS, for the shell table's
 * volumes and mid-shell major radii — so it exists on the solved-equilibrium
 * and imported-g-file tiers and NOT on Miller.  It needs one thing more than
 * the beam: |F(psi)| per shell, because accessibility is set by |B| ~ F/R,
 * and four Miller scalars do not carry F.
 *
 * ★★THE UP-SHIFT IS THE READER'S AND IT IS THE MOST IMPORTANT INPUT.  EAST's
 * launchers emit n_par ~ 1.8-2.4, which resonates at 4.8-8.8 keV — above the
 * plasma — so a strict single-pass model deposits NOTHING.  Real LHCD damps
 * after multi-pass propagation up-shifts n_par; a range (rather than a
 * factor) is the honest form, because the range widens the effective band
 * and therefore `sigma_j`, which is the uncertainty in WHERE the current
 * lands.
 */
function evLhDeposit(field, geo, st, sp) {
  var nsh = Math.max(4, sp.lhShells | 0), i, k;
  var span = field.psiBnd - field.psiAxis;
  if (!isFinite(span) || span === 0)
    throw new Error(FyI18n.t('e.err.lh_nopsi'));
  if (!(sp.lhUpLo > 0) || !(sp.lhUpHi >= sp.lhUpLo))
    throw new Error(FyI18n.t('e.err.lh_upshift'));
  var launched = [[sp.lhNpar1Lo, sp.lhNpar1Hi], [sp.lhNpar2Lo, sp.lhNpar2Hi]];
  var powers = [sp.lhPower1, sp.lhPower2];
  var names = (sp.lhNames && sp.lhNames.length) ? sp.lhNames : ['LH1', 'LH2'];
  var antennas = [], raw = [];
  for (i = 0; i < 2; i++) {
    if (!(powers[i] > 0)) continue;
    var lo = launched[i][0], hi = launched[i][1];
    if (!(lo > 0) || !(hi >= lo)) throw new Error(FyI18n.t('e.err.lh_band'));
    antennas.push({ name: names[i], frequency: 0,
                    power_launched: { data: powers[i] }, power_reflected: { data: 0 },
                    'fylite:n_parallel_min': lo, 'fylite:n_parallel_max': hi });
    raw.push([lo, hi]);
  }
  if (!antennas.length) throw new Error(FyI18n.t('e.err.lh_nopower'));
  //: ★★the assembly is `case.rs::wave_case` (FYL-DESIGN-16 K-3, 2026-09-05):
  //: the shell table on the psi map, the profiles and |F| at the shell
  //: centres, the bands scaled by the up-shift, one `lh_deposit`, the
  //: per-launcher resonance diagnostics — ONE recipe for this page and for
  //: `fylite.scenario.model.lh.deposit` (`test_wave_code.py` in the kernel
  //: repository holds it to the old flat assembly bit for bit).  What stays
  //: here is the PLAN: the field as an `fyo:equilibrium` document (F on the
  //: ladder's own psi_N, which the case reads beside it), the state as
  //: `core_profiles`, the launchers as the DD's `lh_antennas` antennas.
  var rg = new Array(field.nr), zg = new Array(field.nz);
  for (i = 0; i < field.nr; i++) rg[i] = field.r0 + field.dr * i;
  for (i = 0; i < field.nz; i++) zg[i] = field.z0 + field.dz * i;
  var np0 = geo.psin.length, fAbs = new Array(np0), neP = new Array(np0), teP = new Array(np0);
  for (i = 0; i < np0; i++) {
    fAbs[i] = Math.abs(geo.fpol[i]);
    neP[i] = Math.max(st.ne[i], 1e16);
    teP[i] = Math.max(st.te[i], 1);
  }
  var eqDoc = {
    vacuum_toroidal_field: { r0: Math.abs(geo.r0) || 1, b0: Math.abs(geo.b0) || 1 },
    time_slice: {
      global_quantities: { magnetic_axis: { r: field.axisR, z: field.axisZ },
                           psi_axis: field.psiAxis, psi_boundary: field.psiBnd },
      profiles_1d: { f: fAbs, 'fylite:psi_norm': Array.from(geo.psin) },
      profiles_2d: { grid: { dim1: rg, dim2: zg }, psi: Array.from(field.psi) } },
    'fylite:limiter': { r: Array.from(field.limR), z: Array.from(field.limZ) } };
  var cp = { profiles_1d: { grid: { 'fylite:psi_norm': Array.from(geo.psin) },
                            electrons: { density: neP, temperature: teP } } };
  var settings = { eta_cd: sp.lhEtaCd, xi: sp.lhXi, upshift_min: sp.lhUpLo, upshift_max: sp.lhUpHi,
                   n_shells: nsh, width_floor: sp.lhWidthFloor, cd_model: 'fisch', n_theta: 181 };
  var rec = fy.complete('code/wave', { settings: settings,
                                       inputs: { equilibrium: eqDoc, core_profiles: cp,
                                                 lh_antennas: { antenna: antennas } } });
  var F = function (k) { return fieldFlat(rec, k); };
  var X = function (k) { return rec.facts[k].value; };
  var src = rec.fields.core_sources.source['0'].profiles_1d;
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  var nl = rec.dims.n_launchers | 0;
  var lP = F('launcher_power'), lCur = F('launcher_current'),
      lElo = F('launcher_band_min'), lEhi = F('launcher_band_max'),
      lRlo = F('launcher_res_min'), lRhi = F('launcher_res_max'),
      lTlo = F('launcher_t_res_min'), lThi = F('launcher_t_res_max'),
      lReach = F('launcher_reach_fraction');
  var per = [], pw = [];
  for (k = 0; k < nl; k++) {
    pw.push(lP[k]);
    per.push({ name: antennas[k].name, power: lP[k], band: raw[k], bandEffective: [lElo[k], lEhi[k]],
               iLh: lCur[k],
               resLo: isFinite(lRlo[k]) ? lRlo[k] : null, resHi: isFinite(lRhi[k]) ? lRhi[k] : null,
               tResLo: lTlo[k], tResHi: lThi[k], reachFraction: lReach[k] });
  }
  var bands = per.map(function (r) { return r.bandEffective; });
  return {
    psin: flat(src.grid['fylite:psi_norm']), edges: F('psin_edges'), dvolume: F('dvolume'),
    area: F('area'), rmajor: F('rmajor'),
    ne: F('ne'), te: F('te'), fPol: F('f_pol'), nAcc: F('n_acc'), cdWeight: F('cd_weight'),
    pDep: flat(src.electrons.energy), jLh: flat(src.j_parallel), sigmaJ: F('sigma_j'),
    pLaunched: X('p_absorbed'), pDeposited: X('p_deposited'),
    iLh: X('i_lh'), iLhShell: X('i_lh_shell'),
    neBar: X('ne_bar'), teMax: X('te_max'),
    deposited: !!X('resonated'),
    launchers: per, bands: bands,
    inputs: { r0: geo.r0, etaCd: sp.lhEtaCd, xi: sp.lhXi,
              widthFloor: sp.lhWidthFloor, cdModel: 'fisch',
              upshift: [sp.lhUpLo, sp.lhUpHi], nShells: nsh },
  };
}

/**
 * The wave's record, flattened for the wire and for the file.
 *
 * ★★THE INPUTS TRAVEL WITH THE OUTPUTS, for the same reason the beam's do:
 * the closure criterion for this feature is that `kernel.lh_deposit` at
 * THESE parameters reproduces the profile pointwise, and a file carrying
 * only the profile could not be held to it.  The six per-shell arrays the
 * entry reads are written whole.
 */
function evLhReport(lh) {
  var arr = function (a) { return Array.from(a); };
  return {
    psin: arr(lh.psin), edges: arr(lh.edges), dvolume: arr(lh.dvolume),
    area: arr(lh.area), rmajor: arr(lh.rmajor),
    ne: arr(lh.ne), te: arr(lh.te), fPol: arr(lh.fPol),
    nAcc: arr(lh.nAcc), cdWeight: arr(lh.cdWeight),
    pDep: arr(lh.pDep), jLh: arr(lh.jLh), sigmaJ: arr(lh.sigmaJ),
    pLaunched: lh.pLaunched, pDeposited: lh.pDeposited,
    pOutsideLadder: lh.pOutsideLadder === undefined ? null
                                                    : lh.pOutsideLadder,
    ladderEdgePsin: lh.ladderEdgePsin === undefined ? null
                                                    : lh.ladderEdgePsin,
    onLadder: lh.onLadder ? arr(lh.onLadder) : null,
    iLh: lh.iLh, iLhShell: lh.iLhShell, neBar: lh.neBar, teMax: lh.teMax,
    deposited: lh.deposited, launchers: lh.launchers, cadence: lh.cadence,
    inputs: lh.inputs,
  };
}

/**
 * ★★T-M14 — THE SHELL → LADDER REMAP IS CONSERVATIVE NOW.
 *
 * What it replaced: a POINT sample of a shell AVERAGE at the ladder nodes,
 * followed by the march's trapezoid.  That rule does not conserve the
 * integral — measured on the reference case, the march's ladder integral of
 * the same beam sat +3.16 % above the shells' own quadrature over the shared
 * domain at 21 surfaces (+1.68 % at 61, converging but never gone), which is
 * power nobody injected.  T-M11 measured and reported the gap; this closes
 * the discretisation half of it.
 *
 * How this one works — 逐区间积分, against the kernel's own volumes:
 *
 *   1. Each ladder node owns a DUAL CELL in psi_N (midpoint to midpoint;
 *      the axis node from 0, the edge node to `edgePsin`).
 *   2. `shell_table` is called once on the union of dual-cell boundaries
 *      and deposition-shell edges, so every sub-shell volume is the
 *      kernel's traced volume — the same authority `evOutsideLadder`
 *      already leans on — and each sub-shell inherits its parent shell's
 *      density, which IS what a shell quadrature says the density is there.
 *   3. A node's value is its dual-cell energy divided by its own trapezoid
 *      quadrature weight (`w_i * V'_i`), so the march's reported ladder
 *      integral (`evVolInt`, trapezoid on f·V') reproduces the dual-cell
 *      energies EXACTLY, by construction.
 *
 * ★The axis node's V' is zero, so its weight cannot carry energy: its
 * dual-cell energy is folded into the first traced node and the axis VALUE
 * repeats its neighbour (the same `with_axis_node` convention the metric
 * itself follows).  What remains of the old gap is the CALIBRE half —
 * shells beyond `edgePsin`, declared and reported, never remapped — plus
 * contour-tracing consistency between independent `shell_table` partitions
 * of one field (measured ~1e-3 relative, where 3.16 % used to be).
 *
 * ★One OPERATOR per (field, ladder, shell edges), applied to every array of
 * the same shells (`pE`, `pI`, `pDep`, `jNbi`, …): the trace is the
 * expensive part and the application is a sparse sum, and a second copy of
 * the rule would be a second chance to write it differently.
 */
function evShellLadderOp(field, geo, edges) {
  var n = geo.rho.length, nsh = edges.length - 1, i;
  //: dual-cell boundaries in psi_N — node i owns [half[i], half[i+1]]
  var half = new Float64Array(n + 1);
  half[0] = Math.min(geo.psin[0], edges[0]);
  for (i = 1; i < n; i++) half[i] = 0.5 * (geo.psin[i - 1] + geo.psin[i]);
  half[n] = geo.psin[n - 1];
  //: merged, deduplicated knots over the LADDER's domain: shell edges
  //: beyond `edgePsin` belong to the calibre half (`evOutsideLadder`)
  var eps = 1e-12, knots = [], a = 0, b = 0;
  var push = function (v) {
    if (!knots.length || v > knots[knots.length - 1] + eps) knots.push(v);
  };
  while (a <= n || b <= nsh) {
    var va = a <= n ? half[a] : Infinity;
    var vb = b <= nsh ? edges[b] : Infinity;
    if (va <= vb) { push(va); a += 1; }
    else { if (vb <= half[n] + eps) push(vb); b += 1; }
  }
  while (knots.length && knots[knots.length - 1] > half[n] + eps) knots.pop();

  var span = field.psiBnd - field.psiAxis;
  var ng = field.nr * field.nz, psin2d = new Float64Array(ng);
  for (i = 0; i < ng; i++) psin2d[i] = (field.psi[i] - field.psiAxis) / span;
  var t = fy.shellTable({
    r0: field.r0, z0: field.z0, dr: field.dr, dz: field.dz,
    nr: field.nr, nz: field.nz, psin2d: psin2d,
    axisR: field.axisR, axisZ: field.axisZ,
    limR: field.limR, limZ: field.limZ,
    levels: Float64Array.from(knots), nTheta: 181 });

  var m = knots.length - 1;
  var subDual = new Int32Array(m), subShell = new Int32Array(m),
      dvSub = new Float64Array(m);
  for (i = 0; i < m; i++) {
    var c = 0.5 * (knots[i] + knots[i + 1]);
    dvSub[i] = Math.max(t.dvolume[i], 0);
    var d = 0;
    while (d < n - 1 && c > half[d + 1]) d += 1;
    subDual[i] = d;
    var k = 0;
    while (k < nsh - 1 && c > edges[k + 1]) k += 1;
    subShell[i] = k;
  }
  //: the trapezoid's own node weights, the rule `evVolInt` applies
  var w = new Float64Array(n);
  for (i = 0; i < n; i++) {
    var lo = i > 0 ? geo.rho[i - 1] : geo.rho[0];
    var hi = i < n - 1 ? geo.rho[i + 1] : geo.rho[n - 1];
    w[i] = 0.5 * (hi - lo);
  }
  return {
    apply: function (values) {
      var E = new Float64Array(n), g = new Float64Array(n), j;
      for (j = 0; j < m; j++) E[subDual[j]] += values[subShell[j]] * dvSub[j];
      //: forward-carry through nodes whose quadrature weight cannot hold
      //: energy (the axis node, V' = 0) — conservation before shape
      var carry = 0;
      for (j = 0; j < n; j++) {
        var den = w[j] * geo.vprime[j];
        var e = E[j] + carry;
        if (den > 1e-300) { g[j] = e / den; carry = 0; }
        else { g[j] = 0; carry = e; }
      }
      //: the axis node repeats its neighbour, for the march and the
      //: figures — its trapezoid weight is zero either way
      if (n > 1 && w[0] * geo.vprime[0] <= 1e-300) g[0] = g[1];
      return g;
    },
  };
}

/**
 * The toroidal-momentum channel, one step.
 *
 * ★★OPERATOR-SPLIT, and the page says so.  `core_march` carries heat,
 * density and current together because the heat capacity moves with the
 * density; the kernel keeps momentum as its own entry (`solve_momentum`),
 * so this advances omega on the SAME dt from the same old state, with the
 * density and chi_i the closure just produced.  What the split costs is the
 * within-step feedback of rotation on the heat channels — and on this tier
 * that feedback runs through the E x B shear, which the turbulent closure
 * is re-evaluated on its own cadence anyway.
 *
 * ★★chi_phi IS PRESCRIBED, as a Prandtl number times the ion heat
 * diffusivity, and that is a modelling choice rather than a closure: a
 * momentum diffusivity is a TGLF output and this port does not carry
 * upstream's toroidal-stress weights (`assembly.solve_momentum` and
 * `closure.momentum_chi_phi` both say so, the second by refusing).  The
 * number is the reader's and travels in the file.
 *
 * ★★<R^2> IS ON THIS LADDER NOW (T-M8).  The capacity is `V' n m <R^2>`,
 * and until this batch the ladder carried `<|grad rho|^2>` and
 * `<|grad rho|^2 / R^2>` but no plain `<R^2>`, so the channel substituted
 * the surface's own major radius squared, `R_maj(rho)^2` — the first term
 * of it.  Both metric carriers return the average itself now: the traced
 * ladder from `equilibrium_ladder`'s own contour integrals, the Miller tier
 * from `geo_surface`, against the same volume weight in both.  On a
 * circular surface the two differ by exactly `1.5 r^2` — the O((a/R)^2)
 * this page used to declare and live with.
 *
 * ★And a carrier without the column is REFUSED rather than substituted: a
 * capacity quietly built from R_maj^2 is the failure this closed, and it
 * must not be able to come back through a fallback.
 */
function evMomentumStep(ctx, st, omega, chiI, dt) {
  var geo = ctx.geo, sp = ctx.sp, n = geo.rho.length, i;
  if (!geo.r2 || geo.r2.length !== n)
    throw new Error(FyI18n.t('e.err.no_r2'));
  var r2 = geo.r2, chiPhi = new Float64Array(n);
  for (i = 0; i < n; i++) {
    chiPhi[i] = Math.max(sp.prandtl * chiI[i], 1e-6);
  }
  var out = fy.solveMomentum({
    rho: geo.rho, omega: omega, vprime: geo.vprime, gm3: geo.gm3,
    r2: r2, dens: st.ni, mass: EV_MD, chiPhi: chiPhi, torque: ctx.torque,
    //: ★the edge is a Dirichlet ZERO: this tier has no scrape-off layer and
    //: no wall torque, so the boundary condition is "the plasma is not
    //: rotating where the model stops".  A control for it would be a
    //: measurement this page does not have.
    dt: dt, edge: 0, maxOuter: 1, tolSteady: 0, dPc: sp.dPc,
    tol: 1e-10, maxInner: 60 });
  return out.omega;
}

/**
 * dω/dr against the surface's own minor radius, in metres — which is the
 * length TGLF's rotation block differentiates against (`mapping::tglf_local`
 * forms `gamma_p0 = -R_maj w0'` and then `gamma_eb0 = gamma_p0 r/(q R)`).
 * Centred where it can be.
 */
function evOmegaShear(geo, omega) {
  var n = omega.length, out = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    var lo = Math.max(i - 1, 0), hi = Math.min(i + 1, n - 1);
    var dr = geo.rmin[hi] - geo.rmin[lo];
    out[i] = dr !== 0 ? (omega[hi] - omega[lo]) / dr : 0;
  }
  return out;
}

/** Linear interpolation of `v(x)` at `at`, both monotone increasing. */
function evInterp(x, v, at) { return interp1(x, v, at); }

/** `v` sampled from grid `xs` onto grid `xt`. */
function evRemap(xs, v, xt) {
  var out = new Float64Array(xt.length);
  for (var i = 0; i < xt.length; i++) out[i] = evInterp(xs, v, xt[i]);
  return out;
}

// --- the metric ------------------------------------------------------------

/**
 * The metric from four scalars — the reduced tier, and the page says so.
 *
 * The label is the minor radius r [m] (not rho_tor): `geo_surface` returns
 * dV/dr and <|grad r|^2> for the surface it was asked about, so r is the
 * label whose metrics these ARE.  ★★`gm2` used to be null here, on the claim
 * 「a Miller surface set does not determine <|grad r|^2/R^2>」 — WRONG: the
 * surface set fixes R(theta) and |grad r|(theta), and `geometry::solve`
 * merely had no such column.  S-2c 批二 added the column instead of keeping
 * the refusal.  The old note's other half stands: no SUBSTITUTE would do —
 * gm2 is neither <|grad r|^2>/<R^2> (5 % apart at R0/a = 6) nor 1/R0^2.
 */
function evMillerMetric(sp) {
  var n = Math.max(5, sp.n | 0), a = sp.a, r0 = sp.r0;
  var rho = new Float64Array(n), vp = new Float64Array(n),
      gm3 = new Float64Array(n), gm7 = new Float64Array(n),
      r2 = new Float64Array(n), gm2 = new Float64Array(n),
      q = new Float64Array(n),
      shear = new Float64Array(n), kap = new Float64Array(n),
      del = new Float64Array(n), rmaj = new Float64Array(n),
      shift = new Float64Array(n), psin = new Float64Array(n);
  var q0 = 1.0, qa = sp.q95;
  for (var i = 0; i < n; i++) {
    var x = i / (n - 1);
    rho[i] = a * x;
    psin[i] = x * x;             //: psi_N ~ (r/a)^2 near a circular plasma
    q[i] = q0 + (qa - q0) * x * x;
    shear[i] = q[i] !== 0 ? x * (2 * (qa - q0) * x) / q[i] : 0;
    kap[i] = sp.kappa; del[i] = sp.delta; rmaj[i] = r0; shift[i] = 0;
    if (i === 0) continue;
    var g = fy.geoSurface({ rmin: rho[i], rmaj: r0, q: q[i], shear: shear[i],
                            kappa: sp.kappa, sKappa: 0, delta: sp.delta,
                            sDelta: 0, nTheta: 201 });
    vp[i] = g.volumePrime;
    gm3[i] = g.fsaGradR2;
    //: <|grad r|>, which the interpretive inversion needs for the FLUX
    //: while the conduction law uses <|grad r|^2> beside it — upstream's
    //: convention, and the reason a profile made by a chi0 conduction
    //: solve inverts to chi0/gm7 rather than to chi0
    gm7[i] = g.fsaGradR;
    //: ★<R^2> [m^2] (T-M8), the toroidal-momentum capacity's weight.  The
    //: geometry above is handed to `geo_surface` in METRES, so this comes
    //: back in metres squared and needs no a^2.  It is NOT R_maj^2: on a
    //: circular surface it is R_maj^2 + 1.5 r^2, and that difference is
    //: what the momentum channel used to be wrong by.
    r2[i] = g.fsaR2;
    //: ★<|grad r|^2/R^2> [m^-2] (S-2c 批二), from the same surface solve and
    //: in the same label (r [m]) — one label's metric, so no chain rule
    gm2[i] = g.fsaGradR2OverR2;
  }
  //: the axis is SET, not asked: the surface degenerates there
  vp[0] = 0; gm3[0] = gm3[1]; gm7[0] = gm7[1]; r2[0] = r2[1]; gm2[0] = gm2[1];
  return { rho: rho, vprime: vp, gm3: gm3, gm7: gm7, gm2: gm2, r2: r2,
           fpol: evFill(n, Math.abs(sp.b0) * r0), q: q, shear: shear,
           kappa: kap, delta: del, rmaj: rmaj, shift: shift, psin: psin,
           //: the surface's own minor radius [m].  On this tier the label IS
           //: that radius, so the two arrays coincide — they do not on the
           //: ladder tiers, where the label is rho_tor.
           rmin: rho.slice(),
           a: a, r0: r0, b0: Math.abs(sp.b0), source: 'miller' };
}

/**
 * The metric a SOLVED field determines: rho_tor [m], V' [m^2], <|grad
 * rho|^2>, <|grad rho|^2/R^2>, q and F — one traced surface set, the
 * kernel's.
 *
 * ★The axis node is PREPENDED rather than traced: the innermost contour
 * degenerates, so V'(0) = 0 and the flux-surface averages repeat their
 * innermost traced value.  That asymmetry is the kernel's own
 * `with_axis_node` rule and it is applied here once for every consumer.
 */
function evLadderMetric(o) {
  var nlev = Math.max(4, (o.n | 0) - 1);
  var lo = 0.02, hi = o.edgePsin || 0.95;
  var levels = new Float64Array(nlev);
  for (var i = 0; i < nlev; i++) levels[i] = lo + (hi - lo) * i / (nlev - 1);
  var psin2d = new Float64Array(o.psi.length);
  var span = o.psiBnd - o.psiAxis;
  for (var k = 0; k < o.psi.length; k++)
    psin2d[k] = (o.psi[k] - o.psiAxis) / span;
  var lad = fy.equilibriumLadder({
    r0: o.gridR0, z0: o.gridZ0, dr: o.dr, dz: o.dz, nr: o.nr, nz: o.nz,
    psin: psin2d, axisR: o.axisR, axisZ: o.axisZ,
    limR: o.limR, limZ: o.limZ, levels: levels,
    qTable: o.qTable, fTable: o.fTable,
    //: ★ONE gauge, converted once.  Both carriers hand this function the
    //: app's own psi [Wb, axis = max] — the free-boundary solver's directly,
    //: an EQDSK's through `psiFromGfile` — and the ladder wants Wb per
    //: radian.  The factor lived at the two call sites and one of them had
    //: it and the other did not.
    dpsi: (o.psiBnd - o.psiAxis) / (2 * Math.PI), b0: o.b0,
    aMinor: o.aMinor, nTheta: o.nTheta || 121 });
  var m = lad.kept, n = m + 1;
  var head = function (src, axis) {
    var a = new Float64Array(n);
    a[0] = axis === undefined ? src[0] : axis;
    for (var j = 0; j < m; j++) a[j + 1] = src[j];
    return a;
  };
  //: ★★THE MILLER ROWS COME BACK NORMALISED BY `a_minor` (`r/a`, `rmaj/a`,
  //: `zmag/a` — the kernel says so at `miller_from_polys`), and the surface
  //: block the neoclassical closure reads takes METRES.  Multiplying here,
  //: once, is what keeps every consumer below in one unit; the shears, the
  //: shift and the elongation are dimensionless and are left alone.
  var metres = function (src) {
    var out = new Float64Array(m);
    for (var j = 0; j < m; j++) out[j] = src[j] * o.aMinor;
    return out;
  };
  return {
    rho: head(lad.rho, 0), vprime: head(lad.vprime, 0),
    gm3: head(lad.gm3), gm7: head(lad.gm7), gm2: head(lad.gm2),
    //: ★<R^2> [m^2] (T-M8).  `head` repeats the innermost TRACED value at
    //: the prepended axis node, the same rule every other flux-surface
    //: average on this ladder follows — and unlike the Miller rows it needs
    //: no `a_minor`, because it is an average over the grid's own metres
    //: rather than a normalised shape coefficient.
    r2: head(lad.fsaR2),
    fpol: head(lad.fpol),
    q: head(lad.q), psin: head(lad.psin, 0),
    shear: head(lad.miller.shear, 0), kappa: head(lad.miller.kappa),
    delta: head(lad.miller.delta),
    rmaj: head(metres(lad.miller.rmaj)),
    rmin: head(metres(lad.miller.rmin), 0),
    shift: head(lad.miller.shift, 0),
    a: o.aMinor, r0: o.rMaj, b0: Math.abs(o.b0), source: o.source || 'ladder',
    psiAxis: o.psiAxis, psiBnd: o.psiBnd, dpsi: o.dpsi,
  };
}

/** The ladder of a free-boundary solve, q and F taken from that same field. */
function evLadderFromSolve(eq, sp) {
  var gx = grid;
  //: q and F on a UNIFORM psi_N grid, which is what the ladder entry
  //: interpolates them on — resampled here rather than assumed
  //: ★★REFUSED rather than defaulted.  The ladder turns q into rho_tor
  //: (`rho ~ sqrt(integral q dpsi)`), so a q table standing in at 1 does not
  //: produce a coarse metric — it produces a DIFFERENT radial coordinate,
  //: silently, and every profile on it is then a profile of another plasma.
  if (!eq.q || !eq.shape || !(eq.shape.a > 0))
    throw new Error(FyI18n.t('e.err.noladder'));
  var prof = { x: eq.profiles.x, pprime: eq.profiles.pprime,
               ffprime: eq.profiles.ffprime, p: eq.profiles.p };
  var NQ = 33, qT = new Float64Array(NQ), fT = new Float64Array(NQ);
  for (var i = 0; i < NQ; i++) {
    var x = i / (NQ - 1);
    qT[i] = Math.abs(evInterp(eq.q.x, eq.q.q, x));
    fT[i] = evInterp(prof.x, eq.q.f, x);
  }
  var sm = eq.shape;
  return evLadderMetric({
    psi: eq.psi, psiAxis: eq.psiAxis, psiBnd: eq.psiBnd,
    axisR: eq.axisR, axisZ: eq.axisZ,
    gridR0: gx.r[0], gridZ0: gx.z[0], dr: gx.dr, dz: gx.dz,
    nr: gx.nr, nz: gx.nz, limR: M.limiter.r, limZ: M.limiter.z,
    qTable: qT, fTable: fT,
    b0: Math.abs(self.FyDevice.tf(M).b0), aMinor: sm.a, rMaj: sm.r0,
    n: sp.n, edgePsin: sp.edgePsin, nTheta: 121, source: 'device',
  });
}

/**
 * The poloidal flux the current channel marches, in the KERNEL's gauge.
 *
 * ★★Two properties, and each was measured rather than assumed.  (1) The
 * SCALE is the total poloidal flux [Wb] — 2 pi times an EQDSK's psi — which
 * is what makes the channel's own `q = 2 pi B0 rho / (dpsi/drho)` reproduce
 * the q profile the same equilibrium carries: on the bundled synthetic case
 * the two agree to ~1 %, while the per-radian reading is 2 pi out.  (2) It
 * INCREASES outward: the sign is what the q above is positive for, and the
 * kernel's monotone repair reports a huge correction (7e4 Wb here) when a
 * decreasing psi is handed in, which is how this was found.
 *
 * ★The app's own gauge has the axis at the MAXIMUM, so the sign is chosen
 * from the two endpoints rather than assumed: a carrier that ever hands over
 * the other orientation then still marches the same equation.
 */
function evPsiOf(geo, i) {
  if (geo.psiAxis === undefined) return 0;
  var s = geo.psiBnd >= geo.psiAxis ? 1 : -1;
  return s * (geo.psiAxis + (geo.psiBnd - geo.psiAxis) * geo.psin[i]);
}

/**
 * The poloidal picture of the geometry this march is actually on.
 *
 * ★★A 1.5-D page that never draws its own cross-section asks the reader to
 * take the metric on trust.  Six outlines and a boundary cost six contour
 * traces — nothing beside a march — and they are what makes「这些剖面住在这
 * 张平衡上」 checkable by eye: an imported ITER equilibrium and a Miller
 * ellipse do not look alike, and the difference is the whole point of the
 * geometry control above them.
 *
 * The tiers differ in WHAT can be drawn, and that difference is the honest
 * one: a traced field has real surfaces and a real wall; the analytic tier
 * has a family of Miller outlines and NO wall, because four scalars do not
 * describe one.
 */
function evOutlines(geo, ctxObj) {
  var levels = [0.15, 0.3, 0.45, 0.6, 0.75, 0.9], out = [], i;
  var flat = function (poly) {
    var a = new Float64Array(poly.length * 2);
    for (var k = 0; k < poly.length; k++) {
      a[2 * k] = poly[k][0]; a[2 * k + 1] = poly[k][1];
    }
    return Array.from(a);
  };
  if (geo.source === 'miller') {
    //: the analytic family: one outline per radius, the shape parameters
    //: constant because that is what this tier prescribes
    for (i = 0; i < levels.length; i++)
      out.push(flat(fy.millerBoundary({
        r0: geo.r0, z0: 0, a: geo.a * levels[i], kappa: geo.kappa[0],
        deltaU: geo.delta[0], deltaL: geo.delta[0] }, 121)));
    var bnd = flat(fy.millerBoundary({
      r0: geo.r0, z0: 0, a: geo.a, kappa: geo.kappa[0],
      deltaU: geo.delta[0], deltaL: geo.delta[0] }, 181));
    var pad = geo.a * 0.25;
    return { outlines: out, lcfs: bnd, limR: null, limZ: null,
             axisR: geo.r0, axisZ: 0, source: geo.source,
             view: { rmin: geo.r0 - geo.a - pad, rmax: geo.r0 + geo.a + pad,
                     zmin: -(geo.a * geo.kappa[0] + pad),
                     zmax: geo.a * geo.kappa[0] + pad } };
  }
  //: a traced field: the surfaces are contours of the psi that was solved
  var g = ctxObj;
  var trace = function (level) {
    try {
      var t = fy.traceSurface({
        r0: g.r0, z0: g.z0, dr: g.dr, dz: g.dz, nr: g.nr, nz: g.nz,
        psi: g.psi, level: g.psiAxis + (g.psiBnd - g.psiAxis) * level,
        axisR: g.axisR, axisZ: g.axisZ, limR: g.limR, limZ: g.limZ,
        nTheta: 121 });
      return t.poly.length > 8 ? flat(t.poly) : null;
    } catch (e) { return null; }
  };
  for (i = 0; i < levels.length; i++) {
    var o = trace(levels[i]);
    if (o) out.push(o);
  }
  //: ★the boundary is traced a hair INSIDE psi_bnd, the same inset the rest
  //: of this app uses: a level set at exactly the boundary flux leaks
  //: through any neck the tracer can resolve
  var lc = trace(0.995);
  return { outlines: out, lcfs: lc, limR: Array.from(g.limR),
           limZ: Array.from(g.limZ), axisR: g.axisR, axisZ: g.axisZ,
           source: geo.source,
           view: { rmin: g.r0, rmax: g.r0 + g.dr * (g.nr - 1),
                   zmin: g.z0, zmax: g.z0 + g.dz * (g.nz - 1) } };
}

// --- the closure -----------------------------------------------------------

/** The 20-slot surface block and the ion rows the neoclassical chi reads. */
function evNeoBlocks(ctx, st) {
  var n = ctx.rho.length, g = ctx.geo;
  var surf = new Float64Array(20 * n), ion = new Float64Array(6 * n);
  var chigb = new Float64Array(n);
  var a = g.a, b0 = g.b0;
  var dln = function (v, k) {
    var k0 = Math.min(Math.max(k, 1), n - 1);
    var d = ctx.rho[k0] - ctx.rho[k0 - 1];
    if (!(d > 0) || !(v[k] > 0)) return 0;
    return -(v[k0] - v[k0 - 1]) / d / v[k];
  };
  for (var k = 0; k < n; k++) {
    var o = 20 * k;
    //: ★the SURFACE's minor radius and major radius, both in metres — not
    //: the label (rho_tor) and not the aspect ratio.  The 1.5-D bar carried
    //: the ratio in the major-radius slot until 2026-08-23 and its
    //: neoclassical chi was 25 % out, converged and smooth.
    surf[o] = a; surf[o + 1] = Math.max(g.rmin[k], 1e-6);
    surf[o + 2] = g.rmaj[k];
    surf[o + 3] = g.shift[k]; surf[o + 4] = 0; surf[o + 5] = 0;
    surf[o + 6] = Math.max(Math.abs(g.q[k]), 1e-3); surf[o + 7] = g.shear[k];
    surf[o + 8] = g.kappa[k]; surf[o + 9] = 0;
    surf[o + 10] = g.delta[k]; surf[o + 11] = 0;
    surf[o + 12] = 0; surf[o + 13] = 0;
    surf[o + 14] = b0; surf[o + 15] = st.te[k]; surf[o + 16] = st.ne[k];
    surf[o + 17] = dln(st.ne, k); surf[o + 18] = dln(st.te, k);
    surf[o + 19] = 0;
    var i6 = 6 * k;
    ion[i6] = 1.0; ion[i6 + 1] = EV_MD;
    ion[i6 + 2] = st.ni[k]; ion[i6 + 3] = st.ti[k];
    ion[i6 + 4] = dln(st.ni, k); ion[i6 + 5] = dln(st.ti, k);
    var cs = Math.sqrt(Math.max(st.te[k], 1) * EV_QE / EV_MD);
    var rhos = EV_MD * cs / (EV_QE * b0);
    chigb[k] = rhos * rhos * cs / a;
  }
  return { surf: surf, ion: ion, nion: 1, signb: -1, signq: 1,
           rhoStar: 0.001, nTheta: 17, tToEv: 1, chigb: chigb };
}

/**
 * The closure at one state: diffusivities, the exchange, the conductivity,
 * the non-inductive current, and every source the march carries.
 *
 * Every physical term is an ENTRY of the kernel.  What this function owns is
 * the assembly — units, which channel a term lands in, and the two
 * deliberately prescribed pieces (chi_e/chi_i on the neoclassical tier, and
 * the particle diffusivity), each named where it is set.
 */
function evClosure(ctx, st) {
  var sp = ctx.sp, n = ctx.rho.length;
  //: ★★★T-C20 — Z_eff IS A RESULT WHEN THE COMPOSITION IS BEING SOLVED FOR.
  //: With two ion channels running, `sum_s n_s Z_s^2 / n_e` is a PROFILE the
  //: march produced, and the slider that used to pin it set the starting
  //: composition and nothing more.  ★Using the slider here instead would be
  //: exactly the「两套成分」 the old refusal existed to prevent — the
  //: resistivity, the bootstrap and the radiation would all be evaluated on
  //: a composition the density channel had already moved away from.
  var zeff = evZeffOf(ctx, st);
  //: ★kept so the readings and the file can report the composition the
  //: closures were ACTUALLY evaluated on — a Z_eff that is a result and is
  //: not printed is a result nobody can check
  ctx.lastZeff = zeff;
  var neCgs = new Float64Array(n), niCgs = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    neCgs[i] = st.ne[i] * EV_M3_TO_CM3;
    niCgs[i] = st.ni[i] * EV_M3_TO_CM3;
  }

  // --- diffusivities -------------------------------------------------------
  var chiI, chiE;
  //: ★★T-C13 — the flux-match tier runs the SAME closure the turbulent tier
  //: runs (neoclassical floor plus TGLF), and it has to, because what the
  //: match is a root find OF is exactly this model's flux.  A tier that
  //: matched one closure and reported another would be answering a question
  //: nobody asked.
  var wantTurb = sp.closure === 3 || sp.closure === 4;
  if (sp.closure === 2 || wantTurb) {
    var neo = evNeoBlocks(ctx, st);
    chiI = fy.neoChi(ctx.rho, st.ti, neo, sp.chi0);
    ctx.lastNeo = neo;
    //: ★★THE TURBULENT CLOSURE, INSIDE THE MARCH.  TGLF lived on the
    //: interactive bar above and nowhere else, so the one combination a
    //: predictive study actually wants — time dependence WITH a turbulent
    //: closure — was the one this page could not do.  The chain is the same
    //: one that bar uses (`tglf_units` → `tglf_kygrid` → `tglf_flux`, the
    //: ion energy flux over a/L_T times the gyro-Bohm unit), evaluated on
    //: the same neoclassical surface block so the two closures cannot end
    //: up describing different surfaces.
    //:
    //: ★★It is evaluated on a CADENCE and under-relaxed, and both are
    //: physics rather than economy.  A TGLF call per radius per step is
    //: minutes of arithmetic for a plasma whose turbulence equilibrates in
    //: microseconds — the standard separation of timescales — and the
    //: turbulent channel is stiff, so an unrelaxed closure oscillates
    //: between an over- and an under-transported profile.  How many steps
    //: actually re-evaluated it is REPORTED, because a cadence that quietly
    //: never fired would be a neoclassical run wearing a turbulent label.
    if (wantTurb) {
      //: ★the cadence counts STEPS, and the march is what counts them.
      //: `core_march` calls this closure more than once per step (its own
      //: Picard coupling), so a counter kept here fired about twice as
      //: often as the control said — a cadence of 5 evaluating every 2.9
      //: steps, with nothing anywhere saying so.
      //:
      //: ★★NEITHER RULE APPLIES ON THE FLUX-MATCH TIER, and both would be
      //: wrong there rather than merely wasteful.  A cadence would hand the
      //: Newton probe a chi that had not moved, so the finite-difference
      //: Jacobian would see ZERO response from the turbulent channel — the
      //: singular matrix the kernel refuses.  And under-relaxation would
      //: make the flux a function of the ITERATION HISTORY rather than of
      //: `x`, which is not a function the root find can converge on.  The
      //: relaxation on this tier is the matcher's own per-point backoff.
      var due = sp.closure === 4 || !ctx.turbChi || !!ctx.turbDue;
      if (due) {
        //: ★the rotation the momentum channel solved travels INTO the
        //: closure, which is the whole point of having the channel: without
        //: omega there is no E x B shear and the turbulent tier is missing
        //: its most important suppression mechanism.  Absent when the
        //: channel is off, and the deck then keeps its zero.
        var tb = turbulentChi({ radii: ctx.matchRadii
                                  || evTurbRadii(n, sp.turbNrad),
                                ky: evKyGrid(sp.turbNky),
                                satRule: 1, width: 1.65,
                                //: ★from the CONTEXT, not from `st`: this
                                //: closure is called by `core_march` with
                                //: the march's own state, and that state
                                //: has no omega in it — the momentum
                                //: channel is split off and advances
                                //: outside the march.  Reading `st.omega`
                                //: here silently gave every deck a zero
                                //: shear on a plasma rotating at Mach 0.4.
                                w0: ctx.omega || null,
                                w0p: ctx.omega
                                  ? evOmegaShear(ctx.geo, ctx.omega) : null },
                              neo, ctx.rho, st.ti, chiI);
        if (sp.closure === 4 || !ctx.turbChi) ctx.turbChi = tb.chi;
        else
          for (var tk = 0; tk < n; tk++)
            ctx.turbChi[tk] += sp.turbRelax * (tb.chi[tk] - ctx.turbChi[tk]);
        ctx.turbSub = { xs: tb.xs, sub: tb.sub };
        ctx.turbEvals = (ctx.turbEvals | 0) + 1;
        ctx.turbDue = false;
      }
      var withTurb = new Float64Array(n);
      for (var tj = 0; tj < n; tj++)
        withTurb[tj] = chiI[tj] + ctx.turbChi[tj];
      chiI = withTurb;
      ctx.lastChiNeo = fy.neoChi(ctx.rho, st.ti, neo, sp.chi0);
    }
  } else {
    chiI = evFill(n, sp.chi0);
  }
  //: ★PRESCRIBED, and the page says which: Chang-Hinton is an ION heat
  //: flux, so the electron channel is the ion one times a ratio the reader
  //: sets.  A neoclassical electron chi is a different model, not a factor.
  chiE = new Float64Array(n);
  for (var e = 0; e < n; e++) chiE[e] = chiI[e] * sp.chiRatio;

  // --- collisions: the exchange, and the Coulomb log the resistivity uses --
  var cr = fy.collisionRates({
    neCgs: neCgs, te: st.te, niCgs: niCgs, ti: st.ti,
    mass: [EV_MD_G], z: [1], therm: [1] });
  var sxCgs = fy.exchangePower(cr.exch, neCgs, st.te, st.ti);
  var sx = new Float64Array(n);
  for (var x2 = 0; x2 < n; x2++) sx[x2] = sxCgs[x2] * EV_ERG_TO_W;

  var eta = fy.spitzerEta(st.te, zeff, cr.loglam);
  var sigma = new Float64Array(n);
  for (var s2 = 0; s2 < n; s2++) sigma[s2] = 1 / Math.max(eta[s2], 1e-12);

  // --- the non-inductive current ------------------------------------------
  var jni = new Float64Array(n);
  if (ctx.channels.current) {
    if (sp.bootstrap) {
      var eps = new Float64Array(n), pth = new Float64Array(n);
      for (var b = 0; b < n; b++) {
        //: both in metres, so the ratio is the surface's own inverse aspect
        //: ratio rather than one divided by a normalised other
        eps[b] = Math.max(ctx.geo.rmin[b], 1e-4) / ctx.geo.rmaj[b];
        pth[b] = (st.ne[b] * st.te[b] + st.ni[b] * st.ti[b]) * EV_QE;
      }
      var bs = fy.redlBootstrap({
        eps: eps, q: ctx.geo.q, ne: st.ne, te: st.te, ti: st.ti, ni: st.ni,
        zeff: zeff, pTh: pth, iPsi: ctx.geo.fpol, psiBar: st.psi,
        rMaj: ctx.geo.r0, b0: ctx.geo.b0, zIon: 1, collisionless: false });
      //: ★j_bs(0) = 0 is the CALLER's convention, and the kernel says so:
      //: only the caller knows whether its first surface is the axis.  Ours
      //: is — the axis node is prepended above.
      jni.set(bs.jBs); jni[0] = 0;
      ctx.lastBs = jni.slice();
    }
    //: ★★THE DRIVEN CURRENT: the beam's, when there is a beam.  It is not
    //: the I_CD slider scaled — it is `beam_current` on the deposited power
    //: and the absorption-weighted pitch, with the bulk's return current
    //: AND the beam ions' own trapping already in it, so the slider is
    //: disabled on the page rather than added on top of a current the model
    //: produced.
    if (ctx.beamJ) {
      for (var d3 = 0; d3 < n; d3++) jni[d3] += ctx.beamJ[d3];
      ctx.lastCd = Float64Array.from(ctx.beamJ);
    } else if (sp.iCd !== 0 && !ctx.lhJ) {
      //: the driven current, prescribed: a Gaussian carrying I_CD.  ★The
      //: area element is dA/drho = V'/(2 pi R0), which is exact for a
      //: circular surface and an approximation for this one — it is the
      //: normalisation of a PRESCRIBED profile, not a deposition model.
      var area = new Float64Array(n);
      for (var c = 0; c < n; c++)
        area[c] = ctx.geo.vprime[c] / (2 * Math.PI * ctx.geo.r0);
      var cd = evDeposit(ctx.rho, area, sp.cdCentre, sp.cdWidth, sp.iCd);
      for (var d2 = 0; d2 < n; d2++) jni[d2] += cd[d2];
      ctx.lastCd = cd;
    }
    //: ★★AND THE WAVE'S OWN DRIVEN CURRENT, added but never merged.  It is
    //: `lh_deposit`'s `j_lh`, so the I_CD slider is disabled on the page
    //: whenever the wave is on: a page offering a prescribed driven current
    //: beside a current-drive model is offering two answers to one question.
    //: ★It is kept in `lastLh` rather than folded into `lastCd`, because the
    //: attribution — which term put this current here — is the reason a
    //: 1.5-D march carries an LH model at all.
    ctx.lastLh = null;
    if (ctx.lhJ) {
      for (var d4 = 0; d4 < n; d4++) jni[d4] += ctx.lhJ[d4];
      ctx.lastLh = Float64Array.from(ctx.lhJ);
    }
  }

  ctx.lastChi = { e: chiE, i: chiI };
  ctx.lastSigma = sigma;
  //: ★the TOTAL non-inductive current, kept beside its bootstrap half:
  //: `lastBs` is the attribution the readings draw, this is what the psi
  //: channel was actually handed — and it is the second of the two
  //: coefficients another host needs to redo the steady solve (T-C14〔五〕).
  ctx.lastJni = Float64Array.from(jni);
  ctx.lastCr = cr;

  // --- the particle channel ------------------------------------------------
  //: ★per-ion, because the march's ion list may carry an impurity.  With
  //: the density channel off these are zeros either way; the LENGTH is what
  //: the binding checks, and a mismatch there is a silent read past the end.
  var nIon = ctx.nIon || 1;
  var dn = new Float64Array(nIon * n), vn = new Float64Array(nIon * n);
  if (ctx.channels.density) {
    for (var p2 = 0; p2 < n; p2++) {
      //: PRESCRIBED: D = f chi_e and a constant pinch.  There is no
      //: particle closure in this build — the turbulent D/v would come from
      //: the same TGLF run the heat channel is not using here — so the two
      //: knobs are the reader's and are named as prescribed on the page.
      dn[p2] = sp.dOverChi * chiE[p2];
      vn[p2] = sp.pinch;
    }
    //: ★★★T-C20 — AND THE SECOND SPECIES GETS ITS OWN, which is the whole
    //: of this item's browser half.  The kernel's density channel has always
    //: been PER ION (`ni` ion-major, `z` and `edge_ni` one per species, the
    //: closure's `d_n`/`v_n` and the source `s_n` one block per species,
    //: `n_ion` a run-time quantity with no cap in the code) and the Python
    //: assembly layer has always taken an `ions` list — but this closure
    //: sized the two arrays for every species and then filled only the
    //: FIRST block.  ★An impurity handed D = 0 and v = 0 is not「杂质不
    //: 输运」, it is frozen: it stays exactly where the initial dilution put
    //: it while everything around it moves.
    //: ★They are PRESCRIBED on the same terms as the main ion's and named
    //: that way on the page — a turbulent impurity D/v would come out of the
    //: same TGLF run the particle channel is not using here.  ★Their
    //: defaults are the main ion's own two numbers, so switching the second
    //: species on changes nothing until the reader moves them: what the two
    //: controls buy is the ABILITY to say「杂质输运得不一样」, which is the
    //: only interesting thing about having two species at all.
    for (var pz = 0; pz < n && nIon > 1; pz++) {
      dn[n + pz] = sp.dOverChiZ * chiE[pz];
      vn[n + pz] = sp.pinchZ;
    }
  }
  return { chiE: chiE, chiI: chiI, sExchange: sx, dN: dn, vN: vn,
           sigmaPar: sigma, jNi: jni };
}

/**
 * Every source the march carries, at the state a step STARTS from.
 *
 * ★★Called once per outer step, and that is why the march is driven one
 * step per call: `CoreMarch` takes `q_e`/`q_i` at construction and holds
 * them for the whole march (the closure it asks for carries chi, the
 * exchange, D/v, sigma and j_ni — and no source).  A page that ran twenty
 * steps in one call would therefore be showing an alpha power that RESPONDS
 * to the temperature in its table while the temperature was driven by the
 * alpha power of the initial state.  Measured before it was fixed: the
 * reported P_alpha moved and the plasma it was heating did not.
 *
 * The Ohmic term is the one that needs the previous step as well: E_par
 * comes from the flux the march is itself moving.
 */
function evSources(ctx, st, dt) {
  var sp = ctx.sp, n = ctx.rho.length;
  var qE = new Float64Array(n), qI = new Float64Array(n);
  for (var h = 0; h < n; h++) { qE[h] = ctx.heatE[h]; qI[h] = ctx.heatI[h]; }
  var diag = { pAlpha: 0, pRad: 0, pLine: 0, pOhm: 0, pAux: ctx.pAux,
               //: ★the two ladder integrals the march itself performed, kept
               //: apart from their sum: the beam's is the number T-M11 holds
               //: against `shell_sum(p_dep, dV)`
               pAuxBeam: ctx.pAuxBeam || 0, pAuxLh: ctx.pAuxLh || 0,
               //: T-M12: the beam's computed total torque (N·m), null when
               //: the slider is still in charge
               torqueBeam: ctx.torqueBeam == null ? null : ctx.torqueBeam };
  var neCgs = new Float64Array(n), niCgs = new Float64Array(n),
      tiKev = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    neCgs[i] = st.ne[i] * EV_M3_TO_CM3;
    niCgs[i] = st.ni[i] * EV_M3_TO_CM3;
    tiKev[i] = st.ti[i] * 1e-3;
  }

  if (sp.alpha) {
    //: ★★T-C13 — THE BURN CAN BE FROZEN, and only the flux-match tier ever
    //: freezes it.  `ctx.fmFreezeAlpha` is the alpha power density at the
    //: state an iteration STARTED from; see `evFluxMatch` for the
    //: measurement that put it there and for the self-consistency number
    //: that says what the freeze cost.
    //: ★The freeze is a PICARD SPLIT and not an approximation of the
    //: answer: at the fixed point the frozen source is evaluated at the
    //: converged profile, so it equals the live one — which is exactly
    //: what the check reports.
    //: ★THE FUEL FRACTION IS DERIVED when the impurity is in the
    //: quasi-neutrality: n_D = n_T = n_i/2, and n_i is what `ion_dilution`
    //: gave.  Leaving the slider in charge there would burn fuel the
    //: composition does not contain — the alphas go as f^2, so a Z_eff of
    //: 1.7 with argon is a factor 1.3 in P_alpha on its own.
    var fDT = sp.quasi ? sp.dtEffective : sp.dtFraction;
    //: ★`zsum` is `sum_j n_j Z_j^2 / (n_e A_j)`, the field-ion sum that sets
    //: the alpha's critical energy.  It was written out here for a 50:50
    //: D-T mix with nothing else in it; with an impurity in the
    //: quasi-neutrality that is not the plasma, and the kernel already knew
    //: how to say so (`field_ion_sum`).
    var zsum = sp.quasi
      ? fy.fieldIonSum({ zeff: evFill(n, sp.zeff), mainMass: 2.5,
                         mainCharge: 1, impCharge: sp.impurityZ,
                         impMass: sp.impurityA })[0]
      : sp.dtFraction * (1 / 2 + 1 / 3);
    var al = ctx.fmFreezeAlpha
      || fy.alphaHeating({ ne: st.ne, teEv: st.te, tiKev: tiKev,
                           dtFraction: fDT, zeff: sp.zeff,
                           zsum: zsum });
    for (var a2 = 0; a2 < n; a2++) { qE[a2] += al.e[a2]; qI[a2] += al.i[a2]; }
    diag.pAlpha = evVolInt(ctx.rho, ctx.geo.vprime, al.total);
    ctx.lastAlpha = al.total;
  }
  if (sp.brem) {
    //: ★★THE IMPURITY IS NAMED, not guessed.  The kernel's ADAS table is
    //: keyed by species and an unknown id radiates zero, so line radiation
    //: was withheld while the page had no way to say WHICH species — that
    //: is now a control, and what arrives here is the reader's choice plus
    //: its concentration `n_z = c_z n_e`.
    //:
    //: ★★THE BULK ION IS NAMED TOO, and that is not a detail: `rad_ion`
    //: builds its ADAS total as `sum_j n_e n_j Lz(id_j)`, so a species left
    //: at -1 contributes NOTHING to it.  Leaving the hydrogenic bulk
    //: unnamed made the total zero for every plasma with no impurity in it
    //: — a page reporting that a deuterium plasma does not radiate.  The
    //: kernel's table carries H/D/T (identical coefficients), so the bulk
    //: is `D` and the total is the ADAS answer for the whole composition.
    var ions = [{ n: niCgs, z: 1, id: sp.bulkId }];
    var nz = null;
    if (sp.quasi && st.nz) {
      //: ★the impurity the QUASI-NEUTRALITY carries, not a second
      //: concentration typed beside it: with dilution on there is one
      //: composition and the radiation is computed from it.
      nz = new Float64Array(n);
      for (var zq = 0; zq < n; zq++) nz[zq] = st.nz[zq] * EV_M3_TO_CM3;
      ions.push({ n: nz, z: sp.impurityZ, id: sp.impurityId });
    } else if (sp.impurityId >= 0 && sp.cImp > 0) {
      nz = new Float64Array(n);
      for (var z2 = 0; z2 < n; z2++) nz[z2] = neCgs[z2] * sp.cImp;
      ions.push({ n: nz, z: sp.impurityZ, id: sp.impurityId });
    }
    var rd = fy.radIon({ te: st.te, ne: neCgs, ions: ions });
    var rad = new Float64Array(n), line = new Float64Array(n);
    for (var r2 = 0; r2 < n; r2++) {
      //: ★the TOTAL, which is the ADAS value for the composition named.
      //: `line` beside it is that number MINUS the routine's own NRL
      //: bremsstrahlung estimate — a decomposition of one answer, not a
      //: second model, and the kernel says so at its entry.  For pure
      //: deuterium the two agree to a few per cent at keV temperatures and
      //: diverge below 300 eV, where the ADAS curve carries what the
      //: NRL formula does not.
      rad[r2] = rd.total[r2] * EV_ERG_TO_W;
      line[r2] = rd.line[r2] * EV_ERG_TO_W;
      qE[r2] -= rad[r2];
    }
    diag.pRad = evVolInt(ctx.rho, ctx.geo.vprime, rad);
    diag.pLine = evVolInt(ctx.rho, ctx.geo.vprime, line);
    ctx.lastRad = rad;
    ctx.lastLine = line;
  }
  if (ctx.channels.current && sp.ohmic) {
    //: ★Ohm's law, not a current reconstruction.  The parallel field comes
    //: from the flux the march is itself moving — E_par = 2 pi rho
    //: (dpsi/dt) / V', which is the CHANNEL's own relation between a moving
    //: flux and the current it drives (equate its source term with
    //: `sigma E`), not a separate model.  ★The SIGN is the marched gauge's:
    //: psi increases outward here, so a positive loop voltage raises the
    //: edge flux and E_par is positive with it — the same flip the edge
    //: boundary condition carries, and for the same reason.  On a circular
    //: surface it reduces to V_loop / (2 pi R0); the axis takes its
    //: neighbour's ratio, where V' vanishes by construction.  It is LAGGED
    //: by one step — the rate is measured across the step just taken — and
    //: the page says so.
    var ohm = new Float64Array(n);
    var sigma = ctx.lastSigma;
    if (ctx.psiPrev && dt > 0 && sigma) {
      var vp = ctx.geo.vprime;
      for (var o2 = 0; o2 < n; o2++) {
        var k4 = vp[o2] > 0 ? o2 : Math.min(o2 + 1, n - 1);
        var ratio = vp[k4] > 0 ? 2 * Math.PI * ctx.rho[k4] / vp[k4]
                               : 1 / (2 * Math.PI * ctx.geo.r0);
        var epar = ratio * (st.psi[o2] - ctx.psiPrev[o2]) / dt;
        ohm[o2] = sigma[o2] * epar * epar;
        qE[o2] += ohm[o2];
      }
    }
    diag.pOhm = evVolInt(ctx.rho, ctx.geo.vprime, ohm);
    ctx.lastOhm = ohm;
  }
  ctx.lastDiag = diag;
  return { qE: qE, qI: qI, diag: diag };
}

// --- T-C13: the STEADY state, solved rather than marched to ----------------
//
// ★★WHY THIS EXISTS AT ALL, and it is not a new model.  The kernel has
// carried a Newton flux matcher since 07-31 — `flux_match`, six ABI entries,
// validated against TGYRO's own iteration table to 1e-6 — and NOT ONE LINE
// of this front end called it.  Every tier on this bar therefore marched a
// PRESCRIBED chi: the reader could choose which chi model supplied it, but
// never ask the question a predictive transport code is for, which is「哪一
// 组梯度让模型通量等于源项要求的通量」.  So this is WIRING, not physics
// (T-C13), and the physics below is the two lines that turn a gradient
// vector into a flux — everything else is the kernel's.
//
// ★What is matched: the ELECTRON and ION heat channels, two unknowns per
// match radius, laid out channel-fastest exactly as the kernel's Jacobian
// expects.  The unknown is `a/L_T` — dimensionless, TGLF's own
// normalisation, and the band it is clamped into is TGLF's own [0.1, 20].
//
// ★What is NOT matched, and refused rather than approximated: the density
// and current channels (each would be its own matched channel with its own
// model flux, and this build has no particle closure — `dOverChi` is a
// prescribed ratio), the momentum channel, and the equilibrium alternation.
// Iterating the equilibrium AROUND this solve is the stationary outer loop
// and is its own item.

/**
 * The match radii: `nRad` ladder nodes spread evenly in `rho_hat` between an
 * INNER BOUNDARY the reader sets and the node just inside the ladder's edge.
 *
 * ★★THE INNER BOUNDARY IS A CONTROL AND NOT A DEFAULT, and the first
 * measurement on this tier is why.  Matched from the node next to the axis
 * (which is where the turbulent tier's own radial subset starts), the ITER
 * case DIVERGED: at `rho_hat` = 0.23 the Newton step drove `a/L_Ti` to −3.6
 * — a HOLLOW temperature profile, which carries flux the wrong way — and
 * the residual climbed from 104 % to 141 % over twelve iterations while the
 * outer three radii were already matched to 0.4 %.
 *
 * ★It is not a numerical nuisance and it is not fixed by damping.  Near the
 * axis a LOCAL model has nothing to say: there is no unstable drift mode at
 * `rho_hat` < 0.15 (TGLF's own `a/L_T` band starts at 0.1), the enclosed
 * power divided by a vanishing `V'` demands a flux that a marginally-stable
 * model cannot carry, and raising the core gradient raises `T(0)`, hence the
 * ALPHA power, hence the target itself — a burning plasma's core target
 * chases its own answer.  So the core is left OUT of the match and the
 * profile inside the innermost matched radius follows from that radius'
 * gradient falling to zero on axis, which is what regularity requires
 * anyway.  Upstream's own grids start at 0.1–0.2 for the same reason.
 */
function evMatchRadii(rho, nRad, rhoMin) {
  var n = rho.length, edge = rho[n - 1], out = [];
  var lo = Math.min(Math.max(rhoMin, 0.02), 0.7) * edge;
  var hi = rho[n - 2];
  nRad = Math.max(2, nRad | 0);
  for (var j = 0; j < nRad; j++) {
    var want = lo + (hi - lo) * (j / (nRad - 1));
    //: the NEAREST ladder node, because the closure is evaluated on nodes:
    //: a match radius between two of them would be matching an interpolation
    var best = 1, bd = Infinity;
    for (var k = 1; k <= n - 2; k++) {
      var d = Math.abs(rho[k] - want);
      if (d < bd) { bd = d; best = k; }
    }
    if (!out.length || best > out[out.length - 1]) out.push(best);
  }
  return out;
}

/** `-d ln y/dr` in units of `1/a`, centred, on the node `k`. */
function evLogGrad(rho, y, k, a) {
  var n = y.length;
  var k0 = Math.min(Math.max(k, 1), n - 2);
  var d = rho[k0 + 1] - rho[k0 - 1];
  if (!(d > 0) || !(y[k] > 0)) return 0;
  return -a * (y[k0 + 1] - y[k0 - 1]) / d / y[k];
}

/** The cumulative volume integral of a density, node by node. */
function evCumInt(rho, vprime, q) {
  var n = rho.length, out = new Float64Array(n), acc = 0;
  for (var i = 1; i < n; i++) {
    acc += 0.5 * (q[i] * vprime[i] + q[i - 1] * vprime[i - 1])
           * (rho[i] - rho[i - 1]);
    out[i] = acc;
  }
  return out;
}

/**
 * The Newton flux match: the steady state of the heat channel pair.
 *
 * `edge` carries the Dirichlet pair the profiles are reintegrated from; it
 * is an object rather than two numbers because the pedestal model MOVES it
 * between iterations, exactly as it moves it between steps on the marching
 * tiers.  `report(k, res)` fires at each iteration boundary.
 *
 * Returns `{ st, record }`.  It THROWS on a refusal from the kernel — a
 * singular Newton matrix among them — and the caller reports that as a
 * failure rather than falling back to a constant chi: a run that silently
 * became a different closure is the failure this whole item removes.
 */
function evFluxMatch(ctx, st0, edge, report) {
  var sp = ctx.sp, geo = ctx.geo, rho = ctx.rho, n = rho.length;
  var sel = evMatchRadii(rho, sp.turbNrad, sp.fmRhoMin);
  var m = sel.length;
  if (m < 2) throw new Error(FyI18n.t('e.err.fm_radii'));
  //: ★★AND THE CLOSURE IS EVALUATED ON EXACTLY THOSE RADII.  What the match
  //: is a root find OF is the model flux at the match radii, so evaluating
  //: the model somewhere else and interpolating onto them would make the
  //: Jacobian a property of the interpolation.
  ctx.matchRadii = sel;
  var a = geo.a, NE = 2, p = 2 * m;

  //: the interpolation nodes the gradient vector is spread over: the AXIS,
  //: where a regular profile has zero gradient by symmetry, then the match
  //: radii.  Without the axis node the innermost matched gradient would be
  //: carried flat into r = 0 and the reintegrated profile would have a cusp
  //: on it — a peak the match never asked for.
  var xNodes = new Float64Array(m + 1), rMatch = new Float64Array(m);
  xNodes[0] = 0;
  for (var i = 0; i < m; i++) { rMatch[i] = rho[sel[i]]; xNodes[i + 1] = rho[sel[i]]; }

  //: ★TGLF's own band, and the reason it is TGLF's: `turbulentChi` clamps
  //: `a/L_T` into [0.1, 20] before it builds a deck, so a match that walked
  //: outside it would be probing a model that had stopped responding — the
  //: singular Jacobian the kernel refuses, arrived at on purpose.
  var LO = 0.1, HI = 20;
  var clamp = function (v) {
    return !isFinite(v) ? LO : Math.min(Math.max(v, LO), HI);
  };

  /** The full-ladder profile a channel's gradient vector implies. */
  var profileOf = function (x, ch, anchor) {
    var zv = new Float64Array(m + 1);
    for (var j = 0; j < m; j++) zv[j + 1] = x[NE * j + ch] / a;
    var zFull = new Float64Array(n);
    for (var k = 0; k < n; k++) zFull[k] = interp1(xNodes, zv, rho[k]);
    return { prof: fy.reintegrate(zFull, rho, anchor, true), z: zFull };
  };

  //: the state every candidate shares: the density, the composition and the
  //: rotation are NOT matched here, so they are the ones the bar built.
  var stateAt = function (x) {
    var e = profileOf(x, 0, edge.te), n2 = profileOf(x, 1, edge.ti);
    return { st: { te: e.prof, ti: n2.prof, ne: st0.ne, ni: st0.ni,
                   nz: st0.nz || null, psi: st0.psi, q: st0.q || null,
                   omega: st0.omega || null },
             ze: e.z, zi: n2.z };
  };

  //: ★★THE TWO LINES THAT ARE THIS FUNCTION'S OWN PHYSICS.  The conduction
  //: flux the 1.5-D operator carries is `V' <|grad rho|^2> n chi dT/drho`,
  //: so per unit `V'` it is `gm3 n chi z T` with `z = -dlnT/drho` — the
  //: same form the native cross-anchor uses to hold this solver against the
  //: marching one (`tests/test_transport_east.py`).  And the target is the
  //: power that crossed the surface: the volume integral of the sources
  //: inside it, per unit `V'`.
  //:
  //: ★THE EXCHANGE IS A TRANSFER, not a source, and it appears with OPPOSITE
  //: SIGNS in the two targets — the kernel's own convention (`q_e - s_x`,
  //: `q_i + s_x`, positive to the ions).  Dropping it would make the two
  //: channels independent and the matched split between them meaningless.
  //: It sits INSIDE the callback because it depends on the very temperatures
  //: being solved for, which is also why the target Jacobian belongs in the
  //: Newton matrix — and the kernel puts it there.
  var evaluate = function (x) {
    var c = stateAt(x), stx = c.st;
    var cl = evClosure(ctx, stx);
    var src = evSources(ctx, stx, sp.dt);
    var qe = new Float64Array(n), qi = new Float64Array(n);
    for (var k = 0; k < n; k++) {
      qe[k] = src.qE[k] - cl.sExchange[k];
      qi[k] = src.qI[k] + cl.sExchange[k];
    }
    var pe = evCumInt(rho, geo.vprime, qe), pi = evCumInt(rho, geo.vprime, qi);
    var flux = new Float64Array(p), target = new Float64Array(p);
    for (var j = 0; j < m; j++) {
      var kk = sel[j], vp = Math.max(geo.vprime[kk], 1e-30);
      flux[NE * j] = geo.gm3[kk] * stx.ne[kk] * cl.chiE[kk] * c.ze[kk]
                     * stx.te[kk] * EV_QE;
      flux[NE * j + 1] = geo.gm3[kk] * stx.ni[kk] * cl.chiI[kk] * c.zi[kk]
                         * stx.ti[kk] * EV_QE;
      target[NE * j] = pe[kk] / vp;
      target[NE * j + 1] = pi[kk] / vp;
    }
    return { flux: flux, target: target, state: c };
  };

  // --- the starting point --------------------------------------------------
  var x0 = new Float64Array(p);
  for (var j0 = 0; j0 < m; j0++) {
    x0[NE * j0] = clamp(evLogGrad(rho, st0.te, sel[j0], a));
    x0[NE * j0 + 1] = clamp(evLogGrad(rho, st0.ti, sel[j0], a));
  }

  //: ★★THE RESIDUAL IS MADE DIMENSIONLESS HERE, and it has to be done on
  //: THIS side: the kernel's residual is `(f - g)^2` in W^2/m^4, so a
  //: tolerance on it would be a number the reader could only find by trying,
  //: and a different number on every machine.
  //:
  //: ★Scaling both f and g by the SAME per-point weight changes NOTHING the
  //: matcher decides — the Newton system is `(W J_f - W J_g) dx = -W(f-g)r`,
  //: and W cancels; the per-point backoff compares each point with itself.
  //: So this is a change of MEASURE and not of algorithm, which is the only
  //: reason it is allowed here at all.
  //:
  //: ★The weights are frozen at the starting target, not recomputed each
  //: iteration: a residual whose own yardstick moved would make「残差随轮次
  //: 下降」 a statement about the yardstick.  The floor keeps the innermost
  //: radii — where the enclosed power is a few per cent of the total — from
  //: setting the tolerance for the whole solve.
  var first = evaluate(x0), wRef = 0;
  for (var q0 = 0; q0 < p; q0++)
    wRef = Math.max(wRef, Math.abs(first.target[q0]));
  var floor = 0.05 * wRef;
  var w = new Float64Array(p);
  for (var q1 = 0; q1 < p; q1++)
    w[q1] = 1 / Math.max(Math.abs(first.target[q1]), floor, 1e-30);

  //: ★★★THE BURN IS FROZEN WITHIN AN ITERATION, and this is the second
  //: thing the first measurement on this tier decided.  With the alpha power
  //: LIVE inside the Jacobian, the ITER case did not converge: the residual
  //: sat at 100–157 % over twelve iterations and the innermost matched
  //: `a/L_T` was driven NEGATIVE.  With the identical run and the burn
  //: switched off it converged monotonically — 85 → 49 → 22.6 → 8.4 → 4.8 →
  //: 4.1 → 3.3 → 2.5 → 1.65 % — and every radius landed inside 1.7 %.
  //:
  //: ★It is not a numerical nuisance.  A Jacobian probe moves EVERY radius
  //: of a channel together, so raising the gradient raises `T(0)`, hence
  //: the alpha power, hence the enclosed power, hence the TARGET the step
  //: was trying to reach — a burning plasma's target chases its own answer,
  //: and where the target Jacobian beats the flux Jacobian the Newton step
  //: points the wrong way.  That is a real property of the fixed point, not
  //: of this solver.
  //:
  //: ★★And it is upstream's own arrangement.  In the reference framework the
  //: flux matcher matches against the sources a SEPARATE actor produced, and
  //: the burn feedback is closed by the stationary outer loop that runs the
  //: two in turn — which is a different item.  So the split here is Picard
  //: in the burn, Newton in the conduction: the alpha power is re-evaluated
  //: at every ITERATION BOUNDARY and held fixed within the iteration.
  //:
  //: ★★THE FREEZE IS CHECKED RATHER THAN TRUSTED.  At the fixed point the
  //: frozen source is evaluated at the converged profile and therefore
  //: equals the live one; how far that is from true is measured at the end
  //: and reported as its own number, because a split nobody quantified is
  //: indistinguishable from a modelling error.
  var evAlphaFreeze = function (stx) {
    if (!sp.alpha) return null;
    var tiKev = new Float64Array(n);
    for (var i2 = 0; i2 < n; i2++) tiKev[i2] = stx.ti[i2] * 1e-3;
    var fDT = sp.quasi ? sp.dtEffective : sp.dtFraction;
    var zsum = sp.quasi
      ? fy.fieldIonSum({ zeff: evFill(n, sp.zeff), mainMass: 2.5,
                         mainCharge: 1, impCharge: sp.impurityZ,
                         impMass: sp.impurityA })[0]
      : sp.dtFraction * (1 / 2 + 1 / 3);
    return fy.alphaHeating({ ne: stx.ne, teEv: stx.te, tiKev: tiKev,
                             dtFraction: fDT, zeff: sp.zeff, zsum: zsum });
  };

  var history = [], evals = 0, lastState = first.state;
  var wrapped = function (x) {
    var v = evaluate(x);
    evals += 1;
    lastState = v.state;
    var f2 = new Float64Array(p), g2 = new Float64Array(p);
    for (var k = 0; k < p; k++) { f2[k] = v.flux[k] * w[k]; g2[k] = v.target[k] * w[k]; }
    return { flux: f2, target: g2 };
  };

  //: ★★THE TOLERANCE THE READER SETS IS A RELATIVE FLUX ERROR; the kernel's
  //: is on `(f - g)^2`.  The square is taken HERE, once, rather than the
  //: control being labelled with a squared quantity — a slider reading
  //: 4e-4 for「1 % 的通量差」 is a control nobody can set on purpose.
  ctx.fmFreezeAlpha = evAlphaFreeze(first.state.st);
  var res = fy.fluxMatch({
    x0: x0, nEvolve: NE, dx: sp.fmDx, dxMax: sp.fmDxMax,
    relaxFactor: 2.0, iterations: sp.fmIter, method: 3,
    tol: sp.fmTol * sp.fmTol,
  }, wrapped, function (it) {
    //: ★the residual the kernel reports is `(f - g)^2` on the SCALED pair,
    //: so its square root is a relative flux error and that is what the page
    //: prints.  Reporting the square would make「进公差」 read as a much
    //: smaller number than it is.
    history.push({ iteration: it.iterations, worst: Math.sqrt(Math.max(it.worst, 0)),
                   converged: it.converged, tPed: ctx.pedestal ? ctx.pedestal.tPed : null });
    if (report) report(it.iterations, history[history.length - 1]);
    //: ★★THE PEDESTAL MOVES BETWEEN ITERATIONS, exactly as it moves between
    //: steps on the marching tiers: EPED1-NN takes the GLOBAL beta_N, which
    //: is what this solve is producing, so it is re-evaluated on the
    //: PREVIOUS iteration's profiles and lagged by one — the same lag, said
    //: the same way.  Without this a matched ITER case would be held to the
    //: pedestal of its starting parabola.
    //: ★the burn is re-frozen at the point THIS iteration ended on — the
    //: machine's own `x`, not the last point it evaluated: a backoff reverts
    //: components, so those two are not the same state and freezing the
    //: wrong one would put the source of a rejected trial into the next
    //: iteration.
    var stIt = stateAt(it.x).st;
    ctx.fmFreezeAlpha = evAlphaFreeze(stIt);
    if (sp.pedestal && ctx.evPedestal) {
      ctx.pedestal = ctx.evPedestal(ctx.evBetaN(stIt));
      edge.te = ctx.pedestal.tPed;
      edge.ti = ctx.pedestal.tPed;
    }
  });

  //: ★the answer is re-derived from the matched gradients rather than
  //: carried out of the last callback: the last point the machine evaluated
  //: is not necessarily the point it returned (a backoff reverts components),
  //: and shipping the wrong one would put a profile beside a residual that
  //: does not belong to it.
  //: ★the burn is re-frozen ONE LAST TIME at the answer, so the numbers
  //: reported are the ones a reader would get by evaluating the model at
  //: the matched profile — and then the SAME point is evaluated with the
  //: burn live, and the two are compared.  That difference IS what the
  //: Picard split cost, in the only units that matter here (relative flux).
  ctx.fmFreezeAlpha = evAlphaFreeze(stateAt(res.x).st);
  var fin = evaluate(res.x);
  ctx.fmFreezeAlpha = null;
  var live = evaluate(res.x);
  var burnCheck = 0;
  for (var b2 = 0; b2 < p; b2++)
    burnCheck = Math.max(burnCheck,
                         Math.abs((live.flux[b2] - live.target[b2])
                                  - (fin.flux[b2] - fin.target[b2])) * w[b2]);
  var relative = new Float64Array(p);
  for (var r2 = 0; r2 < p; r2++)
    relative[r2] = (fin.flux[r2] - fin.target[r2])
                   * w[r2];
  var worst = 0;
  for (var r3 = 0; r3 < p; r3++)
    worst = Math.max(worst, Math.abs(relative[r3]));

  return {
    st: fin.state.st,
    record: {
      radii: Array.from(rMatch),
      //: the normalised label the figures and the tables use, so the panel
      //: does not have to divide by an edge it cannot see
      rhoN: sel.map(function (k) { return rho[k] / rho[n - 1]; }),
      psin: sel.map(function (k) { return geo.psin ? geo.psin[k] : NaN; }),
      index: sel.slice(),
      //: a/L_T per channel, which is what was actually solved for
      alte: sel.map(function (_, j) { return res.x[NE * j]; }),
      alti: sel.map(function (_, j) { return res.x[NE * j + 1]; }),
      fluxE: sel.map(function (_, j) { return fin.flux[NE * j]; }),
      fluxI: sel.map(function (_, j) { return fin.flux[NE * j + 1]; }),
      targetE: sel.map(function (_, j) { return fin.target[NE * j]; }),
      targetI: sel.map(function (_, j) { return fin.target[NE * j + 1]; }),
      relE: sel.map(function (_, j) { return relative[NE * j]; }),
      relI: sel.map(function (_, j) { return relative[NE * j + 1]; }),
      history: history, iterations: res.iterations, converged: res.converged,
      worst: worst, tol: sp.fmTol, evaluations: evals,
      channels: NE, nRadii: m, dx: sp.fmDx, dxMax: sp.fmDxMax,
      rhoMin: sp.fmRhoMin,
      //: ★T-C13 — the Picard split in the burn, and what it cost.  `null`
      //: when there is no burn to split.
      burnFrozen: !!sp.alpha,
      burnCheck: sp.alpha ? burnCheck : null,
      //: ★the yardstick travels with the numbers it scaled: without it the
      //: residual column cannot be re-derived from the flux columns beside it
      weightFloor: floor, weightRef: wRef,
    },
  };
}

/**
 * A sawtooth crash between two steps, when the current channel says the core
 * has q < 1.
 *
 * ★★What this IS: the kernel's trigger (`q_crossing`) and its
 * content-conserving mixing (`sawtooth_crash`), applied to the state between
 * two time steps.  What it is NOT — and the page says so — is a stability
 * theory: nothing here decides whether the mode is unstable, only that q has
 * fallen through 1, and the mixing radius is `k r_1` with `k` the reader's.
 *
 * ★It needs the CURRENT channel: with q prescribed, a crash would be
 * triggered by a profile nothing in the march can move, and the rebuilt psi
 * would have nowhere to go.
 */
function evSawtooth(ctx, st) {
  var sp = ctx.sp, n = ctx.rho.length;
  if (!sp.sawtooth || !ctx.channels.current || !st.q) return null;
  var r1 = fy.qCrossing(ctx.rho, evQProfile(ctx, st.q), 1.0);
  //: no q = 1 surface is the ANSWER for a discharge that is not sawtoothing
  if (r1 === null || !(r1 > 0)) return null;
  var rMix = Math.min(sp.sawMix * r1, ctx.rho[n - 1] * 0.98);
  var c;
  try {
    c = fy.sawtoothCrash({ rho: ctx.rho, vprime: ctx.geo.vprime, psi: st.psi,
                           profiles: [st.te, st.ti, st.ni], b0: ctx.geo.b0,
                           rMix: rMix });
  } catch (e) {
    //: a mixing radius the model cannot honour is a REFUSAL, not a crash —
    //: the state is left exactly as the march reached it and the run says so
    return { refused: String(e && e.message || e), r1: r1, rMix: rMix };
  }
  st.te = c.profiles[0]; st.ti = c.profiles[1]; st.ni = c.profiles[2];
  //: n_e is quasi-neutrality's answer, so it follows the ion mix rather than
  //: being flattened on its own
  var ne = new Float64Array(n);
  for (var i = 0; i < n; i++) ne[i] = st.ni[i];
  st.ne = ne;
  st.psi = c.psi; st.q = c.q;
  return { r1: r1, rMix: rMix, psiMoved: c.psiMoved, iMix: c.iMix };
}

/**
 * The q profile with a believable AXIS value.
 *
 * ★★The current channel reads `q = 2 pi B0 rho / (dpsi/drho)` with
 * `dpsi[0] = dpsi[1]` and `rho` floored at `rho[1]/2`, so at a PREPENDED
 * axis node it returns exactly `q(rho_1)/2` — measured: 0.43 against the
 * equilibrium's own 0.95, constant from the first step, i.e. an artifact of
 * the node and not a result.  The linear extrapolation is the convention the
 * kernel's own `q_profile` states for the same quantity.
 *
 * ★It is used by the READING and by the SAWTOOTH TRIGGER, which is why it is
 * one function: a trigger reading the raw node would fire on a q that is
 * half of what the plasma has, on every discharge, for ever.
 */
function evQAxis(ctx, q) {
  return Math.abs(q.length > 2 && ctx.rho[2] > ctx.rho[1]
    ? q[1] - (q[2] - q[1]) * ctx.rho[1] / (ctx.rho[2] - ctx.rho[1])
    : q[0]);
}

/** That q profile as an array — the axis node repaired, the rest untouched. */
function evQProfile(ctx, q) {
  var out = Float64Array.from(q, Math.abs);
  out[0] = evQAxis(ctx, q);
  return out;
}

// --- the readings ----------------------------------------------------------

/**
 * What a predictive run is judged on, from the state it reached.
 *
 * ★These are DEFINITIONS, not closures: stored energy, the volume averages,
 * beta_N, the Greenwald fraction and tau_E written the way every code writes
 * them.  They are here rather than in the kernel because each needs the
 * scenario's own Ip and geometry, and they are listed on the page beside
 * the formula so a reader can see which convention was taken.
 */
function evReadings(ctx, st, diag, t) {
  var n = ctx.rho.length, g = ctx.geo, vp = g.vprime;
  var w = new Float64Array(n), p = new Float64Array(n);
  for (var i = 0; i < n; i++) {
    p[i] = (st.ne[i] * st.te[i] + st.ni[i] * st.ti[i]) * EV_QE;   // Pa
    w[i] = 1.5 * p[i];                                            // J/m^3
  }
  var vol = evVolume(ctx.rho, vp);
  var wTh = evVolInt(ctx.rho, vp, w);
  //: ★T-M12: the fast-ion branches enter the READINGS too — the betas take
  //: the trace third `(p_par + 2 p_perp)/3` on top of the thermal pressure,
  //: and the stored energy of the branches, `W = p_par/2 + p_perp`, is
  //: reported as its own number BESIDE `wTh` rather than folded into it
  //: (tau_E stays the thermal definition, and the page says which).
  var pTot = p, wFast = null;
  if (ctx.pFastPar) {
    pTot = new Float64Array(n);
    var wf = new Float64Array(n);
    for (var jf = 0; jf < n; jf++) {
      pTot[jf] = p[jf]
        + (ctx.pFastPar[jf] + 2 * ctx.pFastPerp[jf]) / 3;
      wf[jf] = ctx.pFastPar[jf] / 2 + ctx.pFastPerp[jf];
    }
    wFast = evVolInt(ctx.rho, vp, wf);
  }
  var pAvg = vol > 0 ? evVolInt(ctx.rho, vp, pTot) / vol : 0;
  var neAvg = vol > 0 ? evVolInt(ctx.rho, vp, st.ne) / vol : 0;
  var ipMA = Math.abs(ctx.sp.ip) / 1e6;
  var betaT = 2 * EV_MU0 * pAvg / (g.b0 * g.b0);
  var betaN = ipMA > 0 ? betaT * 100 * g.a * g.b0 / ipMA : NaN;
  var betaP = ipMA > 0
    ? 2 * EV_MU0 * pAvg / Math.pow(EV_MU0 * Math.abs(ctx.sp.ip)
                                   / (2 * Math.PI * g.a), 2) : NaN;
  var nG = ipMA > 0 ? neAvg / (ipMA / (Math.PI * g.a * g.a) * 1e20) : NaN;
  var pIn = diag.pAux + diag.pAlpha + diag.pOhm;
  var pLoss = pIn - diag.pRad;
  //: ★tau_E on the LOSS power (heating minus radiation), the steady-state
  //: definition, and it is only a confinement time once dW/dt is small —
  //: which is why the page reports dW/dt beside it rather than folding it
  //: in silently.
  var tauE = pLoss > 0 ? wTh / pLoss : NaN;
  var q = ctx.channels.current && st.q ? st.q : g.q;
  var q0 = evQAxis(ctx, q);
  return {
    t: t, te0: st.te[0], ti0: st.ti[0], ne0: st.ne[0],
    q0: q0, q95: Math.abs(evInterp(g.psin, q, 0.95)),
    wTh: wTh, wFast: wFast, volume: vol, pAvg: pAvg, neAvg: neAvg,
    betaT: betaT, betaN: betaN, betaP: betaP, greenwald: nG, tauE: tauE,
    pAux: diag.pAux, pAuxBeam: diag.pAuxBeam, pAuxLh: diag.pAuxLh,
    torqueBeam: diag.torqueBeam == null ? null : diag.torqueBeam,
    pAlpha: diag.pAlpha, pRad: diag.pRad,
    //: ★the LINE half of the radiated power, beside the total it is part
    //: of — the brem/line split is a decomposition of one ADAS number and
    //: only their sum is that number
    pLine: diag.pLine, pOhm: diag.pOhm,
    //: Q = 5 P_alpha / P_ext — the fusion gain, not the ratio to the total
    qFus: diag.pAux > 0 ? 5 * diag.pAlpha / diag.pAux : NaN,
    //: ★the rotation the momentum channel reached, and NaN when there is
    //: no channel — a zero here would read as "solved, and it is at rest"
    omega0: st.omega ? st.omega[0] : NaN,
    //: the Mach number the sound speed on axis implies, which is what a
    //: reader compares a rotation against
    mach: st.omega
      ? st.omega[0] * g.rmaj[0]
        / Math.sqrt(Math.max(st.ti[0], 1) * EV_QE / EV_MD) : NaN,
    //: ★★THE PLASMA CURRENT THE psi PROFILE ACTUALLY CARRIES (T-C16's
    //: feedback quantity, and what T-C14's steady-current step has to be
    //: checked against).  Every tier states a `gm2` since S-2c 批二, so this
    //: is no longer null on the analytic one.
    //: ★It reads about 3 % LOW against a prescribed I_p and that gap does
    //: not close with resolution (it is the ladder's own quadrature), so
    //: the RATIO is reported beside it: that is the number a feedback loop
    //: may use, and the absolute one is not.
    ipPsi: (function () {
      var arr = evEnclosedIp(g, st.psi);
      return arr ? arr[arr.length - 1] : null;
    }()),
    //: ★T-C16: what the loop is doing, when it is on — the voltage it
    //: settled on, the relative error it is holding, and the calibration
    //: ratio it took on its first step.  ★The calibration is REPORTED
    //: rather than folded in: a correction nobody can see is a correction
    //: nobody can check.
    ipCtl: ctx.ipCtl && ctx.ipCtl.last
      ? { vLoop: ctx.ipCtl.last.vLoop, err: ctx.ipCtl.last.err,
          ratio0: ctx.ipCtl.ratio0, want: ctx.ipCtl.last.want }
      : null,
  };
}

// --- the equilibrium half --------------------------------------------------

/**
 * The two-parameter shape the free-boundary solver takes, fitted to the
 * pressure gradient the march produced.
 *
 * ★★This is what makes the feedback a SHAPE feedback rather than an
 * amplitude one, and the reason it is well posed: the solver's source is
 * `j_phi = j_c [beta0 R/R0 + (1-beta0) R0/R] (1 - psibar^emp)^enp`, whose
 * pressure term is `R p'`, so `(1 - psibar^emp)^enp` IS `dp/dpsibar`
 * normalised — the very profile the transport solution knows.  Fitting it to
 * anything else (the pressure itself, the temperature) would be fitting the
 * model's shape function to a quantity it is not.
 *
 * Coarse grid then one refinement, because two parameters do not deserve a
 * solver and the residual is REPORTED either way: a shape the family cannot
 * reach is a finding, not something to hide behind a converged flag.
 */
function evFitShape(psin, dpdpsin) {
  var n = psin.length;
  var tgt = new Float64Array(n), tt = 0;
  for (var i = 0; i < n; i++) {
    tgt[i] = Math.abs(dpdpsin[i]);
    tt += tgt[i] * tgt[i];
  }
  if (!(tt > 0)) return null;
  //: ★★THE FIT IS SCALE-FREE, and it has to be: the solver normalises `j_c`
  //: to `I_p`, so only the SHAPE of (1 - psibar^emp)^enp is a claim about
  //: this plasma and its amplitude is not one.  Normalising the target by
  //: its axis value instead — the first version here — asks the family to
  //: match a number it never had to, and it reported a residual of 3.3 on a
  //: perfectly ordinary profile.  The optimal scale is the projection, in
  //: closed form, so the search stays two-dimensional.
  var score = function (emp, enp) {
    var mm = 0, mt = 0, k;
    var m = new Float64Array(n);
    for (k = 0; k < n; k++) {
      var b = 1 - Math.pow(Math.min(Math.max(psin[k], 0), 1), emp);
      m[k] = Math.pow(Math.max(b, 0), enp);
      mm += m[k] * m[k];
      mt += m[k] * tgt[k];
    }
    if (!(tt > 0) || !(mm > 0)) return Infinity;
    //: residual of the best-scaled target against the model, RELATIVE to
    //: the model's own norm — a number a reader can judge without knowing
    //: the pressure's units
    var c = mt / tt, acc = 0;
    for (k = 0; k < n; k++) {
      var d = m[k] - c * tgt[k];
      acc += d * d;
    }
    return acc / mm;
  };
  var best = { emp: 1, enp: 1, rms: Infinity };
  var sweep = function (e0, e1, p0, p1, steps) {
    for (var a = 0; a <= steps; a++)
      for (var b = 0; b <= steps; b++) {
        var emp = e0 + (e1 - e0) * a / steps, enp = p0 + (p1 - p0) * b / steps;
        var v = score(emp, enp);
        if (v < best.rms) best = { emp: emp, enp: enp, rms: v };
      }
  };
  sweep(0.4, 4.0, 0.4, 4.0, 18);
  sweep(Math.max(0.2, best.emp - 0.25), best.emp + 0.25,
        Math.max(0.2, best.enp - 0.25), best.enp + 0.25, 10);
  best.rms = Math.sqrt(best.rms);
  return best;
}

/** The equilibrium's own volume-averaged pressure, from the p(psibar) it ran on. */
function evEqPressure(eq, geo) {
  if (!eq.profiles || !eq.profiles.p) return NaN;
  var n = geo.psin.length, p = new Float64Array(n);
  for (var i = 0; i < n; i++)
    p[i] = evInterp(eq.profiles.x, eq.profiles.p, Math.min(geo.psin[i], 1));
  var vol = evVolume(geo.rho, geo.vprime);
  return vol > 0 ? evVolInt(geo.rho, geo.vprime, p) / vol : NaN;
}

// --- the run ---------------------------------------------------------------

/**
 * INTERPRETIVE analysis: measured profiles in, the chi they imply out.
 *
 * ★★THE OTHER DIRECTION, and the one a predictive study needs first.  Every
 * other bar on this page prescribes a diffusivity and solves for a profile.
 * This one takes profiles that already exist — an imported reference table,
 * a published run, a shot's analysis output — together with the sources that
 * kept them there, and asks what effective diffusivity their own power
 * balance requires.  That is where a number like "chi0 = 0.6" comes from;
 * without it the constant tier is a knob with no provenance.
 *
 * ★It is NOT a fit and not a prediction: nothing is minimised, and the
 * answer is an algebraic inversion of the same power balance the march
 * integrates.  Where the gradient is below the kernel's floor the answer is
 * NaN and stays NaN — that region is dividing by noise, and filling it in
 * would report the flattest part of the profile as its most anomalous.
 *
 * ★The SOURCES are the reader's: a prescribed Gaussian in megawatts, plus
 * the state-dependent terms this page already computes from the profiles
 * themselves (alpha, radiation, Ohmic from a prescribed loop voltage).  What
 * comes out is only as good as they are, which is the honest statement of
 * every interpretive analysis ever done.
 */
function interpRun(msg) {
  var t0 = Date.now(), sp = msg.spec, prof = msg.profiles;
  if (!prof || !prof.rho || prof.rho.length < 3)
    return post({ type: 'error', where: 'interp',
                  message: FyI18n.t('i.err.noref') });
  //: ★★the bar itself is `case.rs::interpretive_case` (FYL-DESIGN-16 K-3,
  //: 2026-09-05): the species resolved where the kernel is, the metric tier,
  //: the reference profiles read onto its radii without extrapolation, the
  //: sources (the volume-normalised deposition, alpha, ADAS radiation, the
  //: Ohmic term from a PRESCRIBED loop voltage), the two inversions, the
  //: valid-only interior average and the energy account — one recipe for this
  //: page and for Python (the kernel repository's `test_interpretive_code.py`
  //: holds it to the old flat assembly bit for bit).  What stays here is the
  //: PLAN: which tier, and — on the device tier — the free-boundary solve whose
  //: ladder is bound in, until that solve sinks with the evolve line.
  var settings = {
    geometry: sp.geometry === 'device' ? 'ladder' : (sp.geometry || 'miller'),
    n: sp.n, edge_psin: sp.edgePsin, a: sp.a, r0: sp.r0, kappa: sp.kappa,
    delta: sp.delta, q95: sp.q95, b0: sp.b0, n_theta: 121,
    grad_floor: sp.gradFloor, p_e: sp.pE, p_i: sp.pI,
    dep_centre: sp.depCentre, dep_width: sp.depWidth, v_loop: sp.vLoop,
    alpha: sp.alpha ? 1 : 0, brem: sp.brem ? 1 : 0,
    impurity: sp.impurity || '', c_imp: sp.cImp, zeff: sp.zeff,
    dt_fraction: sp.dtFraction };
  //: a control the page did not set is a setting the kernel does not see —
  //: the door refuses a non-scalar, and `undefined` is one
  Object.keys(settings).forEach(function (k) {
    if (settings[k] === undefined || settings[k] === null) delete settings[k];
  });
  var cp = { grid: { rho_tor: Array.from(prof.rho) },
             electrons: { temperature: Array.from(prof.te),
                          density: Array.from(prof.ne) } };
  if (prof.ti && prof.ti.length) cp.t_i_average = Array.from(prof.ti);
  var inputs = { core_profiles: { profiles_1d: cp } };
  var free = null;
  if (sp.geometry === 'device') {
    if (!msg.chan)
      return post({ type: 'error', where: 'interp',
                    message: FyI18n.t('recon.noref') });
    var p = { beta0: 0.55, emp: 1.0, enp: 1.0, r0: sp.r0Src };
    var eq = summarize(freeSolve(Float64Array.from(msg.chan), p, sp.ip,
                                 evFreeOpts(sp)), p, {});
    var lad;
    try { lad = evLadderFromSolve(eq, sp); }
    catch (e) { return post({ type: 'error', where: 'interp', message: e.message }); }
    //: ★the metric this bar inverts on is only as good as the equilibrium
    //: it was traced from, so the solve's own verdict rides with it
    free = freeReport(eq);
    settings.a = lad.a; settings.r0 = lad.r0; settings.b0 = lad.b0;
    inputs.equilibrium = { time_slice: { profiles_1d: {
      rho_tor: Array.from(lad.rho), dvolume_drho_tor: Array.from(lad.vprime),
      gm3: Array.from(lad.gm3), gm7: Array.from(lad.gm7),
      'fylite:psi_norm': Array.from(lad.psin) } } };
  } else if (sp.geometry === 'gfile') {
    var g = msg.gfile;
    if (!g)
      return post({ type: 'error', where: 'interp',
                    message: FyI18n.t('e.err.nogfile') });
    inputs.equilibrium = interpGfileDoc(g);
  }
  var rec;
  try { rec = fy.complete('code/interpretive', { settings: settings, inputs: inputs }); }
  catch (e) { return post({ type: 'error', where: 'interp', message: e.message }); }
  var F = function (k) { return fieldFlat(rec, k); };
  var X = function (k) { return rec.facts[k].value; };
  var cpr = rec.fields.core_profiles.profiles_1d;
  var ladr = rec.fields.equilibrium.time_slice.profiles_1d;
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  var validE = F('valid_e'), validI = F('valid_i');
  var asBool = function (v) { return Array.from(v, function (x) { return x !== 0; }); };
  var on = function (k, flag) { return X(flag) ? F(k) : null; };
  var src = sp.geometry === 'device' ? 'device' : settings.geometry;
  post({ type: 'interp',
         rho: flat(ladr.rho_tor), psin: flat(ladr['fylite:psi_norm']),
         vprime: flat(ladr.dvolume_drho_tor),
         gm3: flat(ladr.gm3), gm7: flat(ladr.gm7),
         te: flat(cpr.electrons.temperature), ti: flat(cpr.t_i_average),
         ne: flat(cpr.electrons.density),
         chiE: F('chi_e'), chiI: F('chi_i'),
         validE: asBool(validE), validI: asBool(validI),
         qE: F('q_e'), qI: F('q_i'), powerE: F('power_e'), powerI: F('power_i'),
         srcE: F('src_e'), srcI: F('src_i'),
         alpha: on('alpha', 'alpha_on'), rad: on('rad', 'brem_on'),
         ohm: on('ohm', 'ohm_on'),
         avgE: { chi: X('avg_chi_e'), n: X('avg_n_e'), used: X('avg_used_e') },
         avgI: { chi: X('avg_chi_i'), n: X('avg_n_i'), used: X('avg_used_i') },
         chiEHalf: X('chi_e_half'), chiIHalf: X('chi_i_half'),
         wTh: X('w_th'), tauE: X('tau_e'),
         diag: { pAux: X('p_aux'), pAuxBeam: 0, pAuxLh: 0, torqueBeam: null,
                 pAlpha: X('p_alpha'), pRad: X('p_rad'), pLine: X('p_line'),
                 pOhm: X('p_ohm') },
         geoSource: src,
         //: null on the two tiers that do not solve one — a g-file and a
         //: Miller shape are given, not converged to
         free: free,
         b0: X('b0'), aMinor: X('a_minor'), rMajor: X('r_major'),
         ms: Date.now() - t0 });
}

/**
 * The page's g-file payload as the `fyo:equilibrium` document the kernel's
 * g-file tier reads: the psi map `[R, Z]` in the page's own gauge with its axis
 * and boundary values beside it (the tier normalises, so the gauge cancels),
 * the axis, the limiter, q and F on the uniform psi_N grid, the field, and
 * the boundary outline the minor radius is measured from.
 */
function interpGfileDoc(g) {
  var i, r = new Array(g.nr), z = new Array(g.nz);
  for (i = 0; i < g.nr; i++) r[i] = g.r0 + g.dr * i;
  for (i = 0; i < g.nz; i++) z[i] = g.z0 + g.dz * i;
  if (!g.bndR || !g.bndZ || g.bndR.length < 3)
    throw new Error('interp: the g-file payload carries no boundary outline (nbbbs = 0)');
  return { vacuum_toroidal_field: { r0: g.rmaj, b0: g.b0 },
           time_slice: {
             global_quantities: { magnetic_axis: { r: g.axisR, z: g.axisZ },
                                  psi_axis: g.psiAxis, psi_boundary: g.psiBnd },
             profiles_1d: { q: Array.from(g.qTable), f: Array.from(g.fTable) },
             profiles_2d: { grid: { dim1: r, dim2: z }, psi: Array.from(g.psi) },
             boundary: { outline: { r: Array.from(g.bndR), z: Array.from(g.bndZ) } } },
           'fylite:limiter': { r: Array.from(g.limR), z: Array.from(g.limZ) } };
}

/**
 * What this configuration asks for that `evolve_heat` does NOT carry.
 *
 * ★★★S-2b.  Read from the KERNEL'S OWN declaration (`ENTRY_SCOPE`,
 * generated into `fyo-interface.js`), never from a list kept here.  Python's
 * `cases.plan` refuses an out-of-scope case from the same rows; two hosts
 * answering「在范围内吗」from two lists agree until the day a capability
 * sinks and only one list is edited, and then one host runs a discharge the
 * other refuses under the same case name.
 *
 * Returns an array of glosses — empty means the entry is the whole answer.
 */
function evScopeMiss(sp) {
  var N = self.FyNames, rows = N && N.BLOCKS && N.BLOCKS.ENTRY_SCOPE;
  if (!rows) {
    //: ★a missing generated file THROWS rather than defaulting to「在范围
    //: 内」: defaulting would silently route every run onto the entry,
    //: including the ones it cannot carry
    throw new Error('worker: assets/fyo-interface.js must load before this '
                    + '(ENTRY_SCOPE is the declared scope ledger)');
  }
  var miss = [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i], field = r.shape, v = field ? sp[field] : undefined;
    //: `closure` and `couple` are numeric: 0 is IN scope.  The declaration
    //: says WHICH controls decide the scope; what counts as「on」for a
    //: numeric one is this host reading its own control, and it is written
    //: out rather than left to truthiness.
    if (r.key === 'closure' || r.key === 'couple') {
      if (+v) miss.push(r.gloss);
    } else if (r.units === 'required') {
      if (!v) miss.push(r.gloss);
    } else if (r.key === 'resume') {
      //: the browser's resume does not ride on `sp` — it is a whole state
      //: the page hands the worker, so the test is for THAT
      if (msgHasResume) miss.push(r.gloss);
    } else if (r.units === 'sunk') {
      //: ★a capability the entry carries (2026-09-05 第十五刀: the density
      //: channel, the impurity in the quasi-neutrality, the momentum
      //: channel) — on or off, it is in scope
      continue;
    } else if (v) {
      miss.push(r.gloss);
    }
  }
  return miss;
}

/**
 * The march, driven through the KERNEL ENTRY instead of this file's loop.
 *
 * ★★★S-2b.  For a configuration the entry carries whole (`evScopeMiss` says
 * so), every physics decision inside a step is the kernel's — the sources
 * rebuilt per step, the exchange ceiling, the closure, the pedestal's lagged
 * edge, the current channel, the sawtooth.  What is left here is what was
 * always the host's: the metric, the initial profiles, and the page's own
 * readings.  Python's `model.evolve` calls the SAME entry with the SAME
 * blocks, so a corpus case is one orchestration on both hosts instead of two
 * that a gate has to keep equal.
 *
 * ★★ONE STEP PER CALL, and it is the same requirement the loop below states
 * for its own call: a page draws between steps, and the readings it draws
 * are computed from the state each step reached.  A call carrying twenty
 * steps would hand back one final state and nineteen readings nobody could
 * build.  The entry's continuation pair makes N single-step calls identical
 * to one N-step call BIT FOR BIT (`test_driving_the_entry_in_blocks_equals_
 * one_long_run`), so this costs an ABI crossing per step and nothing else.
 *
 * It fills exactly what the loop fills — `st`, `trace`, `crashes`, `steps`,
 * `tNow` and the `ctx.last*` a reading reads — and returns, so the tail of
 * `evolveRun` (the readings, the record, the one `post` that carries them)
 * is untouched and there is still ONE exit.
 */
function evEntryMarch(ctx, st, geo, sp, trace, crashes, tStart) {
  var n = geo.rho.length, prev = null, steps = 0, tNow = tStart || 0;
  //: ★★the march is `case.rs::evolve` (FYL-DESIGN-16 K-3, 2026-09-05), one step
  //: per call so the page can report as it goes: the plan carries the ladder
  //: this run is on (bound rows — the traced tiers' own rmin/rmaj beside the
  //: metric), the state as it stands (`state`, then `resume` with the lagged
  //: arrays the entry hands back), and the bar's controls spelled in SI.  It
  //: used to be the flat export `fy.scenario('evolve_heat', …)` with the same
  //: blocks packed here; `app/tests/validate-worker-evolve.mjs` holds the door
  //: to that path's answer step by step.
  var arr = function (v) { return v ? Array.from(v) : null; };
  var settings = {
    geometry: 'ladder', n_steps: 1, state: 1,
    a: geo.a, r0: geo.r0, b0: geo.b0, kappa: sp.kappa, delta: sp.delta,
    te_axis: sp.te0, ti_axis: sp.ti0, ne_axis: sp.ne0,
    edge_te: sp.edgeTe, edge_ti: sp.edgeTi, edge_ne: sp.edgeNe,
    peaking_t: sp.peakT, peaking_n: sp.peakN,
    chi0: sp.chi0, chi_ratio: sp.chiRatio, d_pc: sp.dPc,
    dt: sp.dt, dt_target: sp.dtTarget,
    p_e: sp.pE * 1e6, p_i: sp.pI * 1e6, dep_centre: sp.depCentre, dep_width: sp.depWidth,
    brem: sp.brem ? 1 : 0, bulk: 'D', impurity: sp.impurity || '',
    imp_conc: sp.impurity ? sp.cImp : 0, imp_z: sp.impurityZ || 0,
    alpha: sp.alpha ? 1 : 0, dt_fraction: sp.dtFraction, zeff: sp.zeff,
    pedestal: sp.pedestal ? 1 : 0, ip_a: Math.abs(sp.ip),
    current: ctx.channels.current ? 1 : 0,
    ohmic: sp.ohmic ? 1 : 0, bootstrap: sp.bootstrap ? 1 : 0, v_loop: sp.vLoop || 0,
    sawtooth: sp.sawtooth ? 1 : 0, saw_mix: sp.sawtooth ? sp.sawMix : 0,
    saw_period: sp.sawPeriod || 0,
    i_cd_a: sp.iCd || 0, cd_centre: sp.cdCentre, cd_width: sp.cdWidth,
    resume: 0, t_start: 0, dt_start: 0, edge_te_in: 0, edge_ti_in: 0, capped_in: 0, saw_elapsed_in: 0,
    //: ★第十五刀 — the density channel (the impurity in the quasi-neutrality
    //: with it) and the momentum channel, the sliders in SI (fuel 1e20/s ->
    //: 1/s; the torque is N.m on both sides)
    'ch-density': ctx.channels.density ? 1 : 0, d_over_chi: sp.dOverChi, pinch: sp.pinch,
    fuel_rate: (sp.fuel || 0) * 1e20, fuel_centre: sp.fuelCentre, fuel_width: sp.fuelWidth,
    quasi: sp.quasi ? 1 : 0, d_over_chi_z: sp.dOverChiZ, pinch_z: sp.pinchZ,
    fuel_z_rate: (sp.fuelZ || 0) * 1e20,
    'ch-momentum': ctx.momentum ? 1 : 0, prandtl: sp.prandtl, torque: sp.torque || 0,
    dt_fraction_in: 0
  };
  Object.keys(settings).forEach(function (k) {
    if (settings[k] === undefined || settings[k] === null) delete settings[k];
  });
  var ladder = { rho_tor: arr(geo.rho), dvolume_drho_tor: arr(geo.vprime), gm3: arr(geo.gm3),
                 gm2: arr(geo.gm2), f: arr(geo.fpol), q: arr(geo.q),
                 'fylite:r_minor': arr(geo.rmin), 'fylite:r_major': arr(geo.rmaj),
                 'fylite:r2_average': arr(geo.r2),
                 psi: arr(st.psi) };
  Object.keys(ladder).forEach(function (k) { if (!ladder[k]) delete ladder[k]; });
  var zeros = new Float64Array(n);
  var state = { te: st.te, ti: st.ti, ne: st.ne, psi: st.psi,
                psiPrev: zeros, sigmaPrev: zeros, exchPrev: zeros,
                //: the page's own start: the dilution it built, the rotation at rest
                ni: st.ni, nz: st.nz || null, omega: st.omega || null };
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  while (steps < sp.nSteps) {
    if (prev) {
      settings.resume = 1;
      settings.t_start = prev.t_end;
      settings.dt_start = prev.dt_next;
      settings.edge_te_in = prev.edge_te_out;
      settings.edge_ti_in = prev.edge_ti_out;
      settings.capped_in = prev.dt_capped;
      settings.saw_elapsed_in = prev.saw_elapsed_out;
      settings.dt_fraction_in = prev.dt_fraction_used;
      state = { te: prev.te, ti: prev.ti, ne: prev.ne_out, psi: prev.psi,
                psiPrev: prev.psi_prev_out, sigmaPrev: prev.sigma_prev_out, exchPrev: prev.exch_prev_out,
                ni: prev.ni_main, nz: prev.nz, omega: prev.omega };
    }
    var plan = { settings: settings, inputs: {
      equilibrium: { time_slice: { profiles_1d: ladder } },
      core_profiles: { profiles_1d: { grid: { psi: arr(state.psi) },
                                      electrons: { temperature: arr(state.te), density: arr(state.ne) },
                                      t_i_average: arr(state.ti),
                                      'fylite:ion_density': arr(state.ni),
                                      'fylite:impurity_density': sp.quasi && state.nz ? arr(state.nz) : undefined,
                                      rotation_frequency_tor_sonic: ctx.momentum && state.omega ? arr(state.omega) : undefined } },
      evolve: { 'fylite:psi_prev': arr(state.psiPrev), 'fylite:sigma_prev': arr(state.sigmaPrev),
                'fylite:exch_prev': arr(state.exchPrev) } } };
    var cp1 = plan.inputs.core_profiles.profiles_1d;
    Object.keys(cp1).forEach(function (k) { if (cp1[k] === undefined || cp1[k] === null) delete cp1[k]; });
    var rec = fy.complete('code/evolve', plan);
    var F = function (k) { return fieldFlat(rec, k); };
    var X = function (k) { return rec.facts[k].value; };
    var cpr = rec.fields.core_profiles.profiles_1d, sm = rec.fields.summary;
    var tr = rec.fields.core_transport.model['0'].profiles_1d;
    var o = { te: flat(cpr.electrons.temperature), ti: flat(cpr.t_i_average), ne_out: flat(cpr.electrons.density),
              psi: F('psi'), q: F('q'), j_bs: F('j_bs'), j_cd: F('j_cd'),
              chi_e: flat(tr.electrons.energy.d), chi_i: flat(tr.total_ion_energy.d),
              exch_prev_out: F('exch_prev_out'), psi_prev_out: F('psi_prev_out'), sigma_prev_out: F('sigma_prev_out'),
              dt_capped: X('dt_capped'), settled: X('settled') !== 0,
              saw_r1: F('saw_r1'), saw_mixed: F('saw_mixed'), saw_refused: F('saw_refused'),
              p_alpha: flat(sm.fusion.power.value), p_rad: flat(sm.global_quantities.power_radiated.value),
              p_line: flat(sm.global_quantities.power_line.value), p_ohm: flat(sm.global_quantities.power_ohm.value),
              dt_used: F('dt_used'), balance: F('balance'), t_ped: F('t_ped'), ped_extrap: X('ped_extrap'),
              t_end: X('t_end'), dt_next: X('dt_next'), edge_te_out: X('edge_te_out'), edge_ti_out: X('edge_ti_out'),
              saw_elapsed_out: X('saw_elapsed_out'), dt_fraction_used: X('dt_fraction_used'),
              //: 第十五刀: the composition and the two channels
              ni_main: flat(cpr['fylite:ion_density']), zeff: flat(cpr.zeff),
              nz: sp.quasi && cpr['fylite:impurity_density'] ? flat(cpr['fylite:impurity_density']) : null,
              omega: ctx.momentum && cpr.rotation_frequency_tor_sonic ? flat(cpr.rotation_frequency_tor_sonic) : null };
    steps += 1;
    tNow = o.t_end;
    st.te = o.te; st.ti = o.ti; st.ne = o.ne_out; st.ni = o.ni_main;
    if (sp.quasi) st.nz = o.nz;
    if (ctx.momentum) { st.omega = o.omega; ctx.omega = o.omega; }
    ctx.lastZeff = o.zeff;
    if (ctx.channels.current) { st.psi = o.psi; st.q = o.q; }
    ctx.lastBs = ctx.channels.current ? o.j_bs : null;
    ctx.lastChi = { e: o.chi_e, i: o.chi_i };
    var nuMax = 0;
    for (var q = 0; q < n; q++) {
      var nu = o.exch_prev_out[q];
      if (isFinite(nu) && nu > nuMax) nuMax = nu;
    }
    ctx.tauExch = nuMax > 0 ? 1 / nuMax : null;
    ctx.lastCd = (sp.iCd && ctx.channels.current) ? o.j_cd : null;
    ctx.dtCapped = o.dt_capped | 0;
    var r1 = o.saw_r1[0], mixed = o.saw_mixed[0];
    if (r1 > 0) {
      crashes.push({ step: steps, t: tNow, r1: r1, rMix: mixed,
                     refused: o.saw_refused[0]
                       ? FyI18n.t('e.err.sawmix') : undefined });
    }
    ctx.lastDiag = { pAux: (sp.pE + sp.pI) * 1e6, pAuxBeam: 0, pAuxLh: 0,
                     torqueBeam: null, pAlpha: o.p_alpha[0],
                     pRad: o.p_rad[0], pLine: o.p_line[0],
                     pOhm: o.p_ohm[0] };
    var rd = evReadings(ctx, st, ctx.lastDiag, tNow);
    rd.dt = o.dt_used[0];
    rd.steady = !!o.settled;
    rd.crashes = crashes.length;
    rd.crashed = r1 > 0 && !o.saw_refused[0];
    rd.balance = o.balance[0];
    if (sp.pedestal) {
      rd.pedTPed = o.t_ped[0];
      rd.pedExtrap = o.ped_extrap;
    }
    trace.push(rd);
    if (steps % Math.max(1, sp.report | 0) === 0 || steps === sp.nSteps) {
      post({ type: 'evolve_step', step: steps, nSteps: sp.nSteps,
             rho: geo.rho, psin: geo.psin, reading: rd,
             te: st.te, ti: st.ti, ne: st.ne, q: st.q,
             ni: st.ni, nz: st.nz || null, omega: st.omega || null,
             chiE: ctx.lastChi.e, chiI: ctx.lastChi.i,
             jni: ctx.lastBs || null,
             geoSource: geo.source, coupled: 0, viaEntry: true });
    }
    prev = o;
    if (o.settled) break;
  }
  return { steps: steps, tNow: tNow, settled: !!(prev && prev.settled) };
}

//: set by `evolveRun` before the scope test; a module-level flag rather than
//: an argument only because `evScopeMiss` is called from one place and the
//: page's resume arrives on the message, not on the spec
var msgHasResume = false;

function evolveRun(msg) {
  var t0 = Date.now(), sp = msg.spec;
  //: ★the page's resume is a whole STATE on the message, not a switch on the
  //: spec, so the scope test is told about it here rather than guessing
  msgHasResume = !!msg.resume;
  var channels = { heat: !!sp.chHeat, density: !!sp.chDensity,
                   current: !!sp.chCurrent };
  //: ★★NOT a fourth channel of `core_march`, because the kernel does not
  //: have it as one: heat, density and current are marched together (the
  //: heat capacity moves with the density) and momentum is its own entry.
  //: So it is switched on beside them and advanced beside them, and
  //: `evMomentumStep` says what that split costs.
  var momentum = !!sp.chMomentum;
  //: ★★THE SPECIES IS RESOLVED HERE, where the kernel is, and a name the
  //: table does not carry is an ERROR rather than a plasma that radiates
  //: nothing: `adas_id` answers -1 for an unknown name and downstream that
  //: is indistinguishable from "no impurity", which is precisely the trap
  //: the kernel's own comment warns about.  Z comes from the periodic
  //: table beside the binding (`FyLite.ADAS_Z`), checked by the gate.
  sp.impurityId = -1; sp.impurityZ = 0;
  //: the hydrogenic bulk, named so the ADAS total is a total (see the
  //: radiation block).  It is in the shipped table, so this cannot fail
  //: quietly — and if it ever did, the check below would catch it.
  sp.bulkId = fy.adasId('D');
  if (sp.bulkId < 0)
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.species', { name: 'D' }) });
  if (sp.impurity) {
    sp.impurityId = fy.adasId(sp.impurity);
    sp.impurityZ = (self.FyLite.ADAS_Z || {})[sp.impurity];
    sp.impurityA = (self.FyLite.ADAS_A || {})[sp.impurity];
    if (sp.impurityId < 0 || !(sp.impurityZ > 0) || !(sp.impurityA > 0))
      return post({ type: 'error', where: 'evolve',
                    message: FyI18n.t('e.err.species',
                                      { name: sp.impurity }) });
  }
  if (!(channels.heat || channels.density || channels.current))
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.nochannel') });
  //: ★★T-C13 — WHAT THE FLUX-MATCH TIER REFUSES, and every one of them is
  //: refused rather than quietly ignored.  It solves the STEADY state of the
  //: heat channel pair: there is no time axis, so a waveform and a resumed
  //: state have nothing to mean here; the density and current channels would
  //: each be their own matched channel with their own model flux (and this
  //: build has no particle closure — D/chi is a prescribed ratio); the
  //: momentum channel is advanced beside the march and there is no march;
  //: and iterating the EQUILIBRIUM around this solve is the stationary outer
  //: loop, which is a separate item and not this one.
  if (sp.closure === 4) {
    if (!channels.heat)
      return post({ type: 'error', where: 'evolve',
                    message: FyI18n.t('e.err.fm_needheat') });
    if (channels.density || channels.current || momentum)
      return post({ type: 'error', where: 'evolve',
                    message: FyI18n.t('e.err.fm_channels') });
    if (sp.wave || msg.resume)
      return post({ type: 'error', where: 'evolve',
                    message: FyI18n.t('e.err.fm_notime') });
    if (sp.couple > 0)
      return post({ type: 'error', where: 'evolve',
                    message: FyI18n.t('e.err.fm_couple') });
  }

  // --- the geometry, and what it allows ------------------------------------
  //: ★★EVERY free-boundary solve this march stands on, with its own verdict.
  //: A coupled run re-solves the equilibrium once per block, and until now
  //: nothing anywhere said whether any of them reached the tolerance they
  //: were asked for — so a march built on a field the solver had not found
  //: read exactly like one built on a field it had.
  var freeLog = [];
  var geo = null, eq = null, chan = null, beta0 = sp.beta0;
  var prof = { beta0: beta0, emp: sp.emp, enp: sp.enp, r0: sp.r0Src };
  //: what the cross-section is traced on — the same psi the metric came from
  var field = null;
  if (sp.geometry === 'device') {
    if (!msg.chan) return post({ type: 'error', where: 'evolve',
                                 message: FyI18n.t('recon.noref') });
    chan = Float64Array.from(msg.chan);
    eq = summarize(freeSolve(chan, prof, sp.ip, evFreeOpts(sp)), prof, {});
    //: ★★THE EQUILIBRIUM THIS MARCH STANDS ON, and whether the solver got
    //: there.  Block 0 is the one every frozen-geometry run uses for its
    //: whole march, so a run with `couple = 0` has exactly this one entry
    //: and it is still the thing that decides whether the metric ladder
    //: means anything.
    freeLog.push(assign({ block: 0 }, freeReport(eq)));
    geo = evLadderFromSolve(eq, sp);
    field = { psi: eq.psi, psiAxis: eq.psiAxis, psiBnd: eq.psiBnd,
              axisR: eq.axisR, axisZ: eq.axisZ,
              r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz,
              nr: grid.nr, nz: grid.nz,
              limR: M.limiter.r, limZ: M.limiter.z };
  } else if (sp.geometry === 'gfile') {
    var g = msg.gfile;
    field = { psi: Float64Array.from(g.psi), psiAxis: g.psiAxis,
              psiBnd: g.psiBnd, axisR: g.axisR, axisZ: g.axisZ,
              r0: g.r0, z0: g.z0, dr: g.dr, dz: g.dz, nr: g.nr, nz: g.nz,
              limR: Float64Array.from(g.limR), limZ: Float64Array.from(g.limZ) };
    geo = evLadderMetric({
      psi: Float64Array.from(g.psi), psiAxis: g.psiAxis, psiBnd: g.psiBnd,
      axisR: g.axisR, axisZ: g.axisZ,
      gridR0: g.r0, gridZ0: g.z0, dr: g.dr, dz: g.dz, nr: g.nr, nz: g.nz,
      limR: Float64Array.from(g.limR), limZ: Float64Array.from(g.limZ),
      qTable: Float64Array.from(g.qTable), fTable: Float64Array.from(g.fTable),
      b0: Math.abs(g.b0), aMinor: g.a,
      rMaj: g.rmaj, n: sp.n, edgePsin: sp.edgePsin, nTheta: 121,
      source: 'gfile' });
  } else {
    geo = evMillerMetric(sp);
  }
  //: ★★What the current channel needs is TWO things, and until S-2c 批二
  //: only one of them was ever missing, so the refusal tested only that
  //: one.  `gm2` is now stated by every tier (the analytic one included).
  //: An INITIAL FLUX is not: `evPsiOf` returns 0 where there is no
  //: equilibrium, so the analytic tier would march current diffusion from
  //: psi = 0 — a run, not a refusal, and one whose q is whatever the
  //: solver's clamp says.  So the test moved to what is actually absent.
  if (channels.current && !geo.gm2)
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.nogm2') });
  if (channels.current && geo.psiAxis === undefined)
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.nopsi_init') });
  //: ★★T-C16: the I_p loop acts through the boundary flux RATE on the
  //: current channel and closes on a current read off `psi` through `gm2`.
  //: Without either there is nothing to drive and nothing to measure, so
  //: this REFUSES rather than running an open loop that looks closed — the
  //: same rule the current channel itself follows one line above.
  if (sp.ipCtl && (!channels.current || !geo.gm2
                   || geo.psiAxis === undefined))
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.ipctl_needs') });
  //: ★★T-C14: the outer loop's current round alternates the psi channel with
  //: a re-TRACED equilibrium.  On the analytic tier there is nothing to
  //: alternate WITH, so more than one round is REFUSED rather than quietly
  //: collapsing to one — a reader who asked for five rounds and silently
  //: got one would have no way to tell.
  //: ★The test names the TIER, not `!geo.gm2`: the two coincided only while
  //: the analytic tier had no gm2, and S-2c 批二 gave it one — at which point
  //: the old spelling stops firing and lets the silent collapse through.  Nor
  //: `!== 'gfile'`: a ladder from a SOLVE says `'ladder'` and is traced too.
  if (sp.closure === 4 && sp.fmOuter > 1 && geo.source === 'miller')
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.fm_outer_nogm2') });
  //: ★★THE BEAM NEEDS A psi_N MAP ON THE (R, Z) GRID, and the analytic tier
  //: does not have one.  Refused rather than approximated: attenuating a
  //: chord through a made-up flux map would report a stopping depth nobody
  //: computed, which is the failure the whole beam model exists to remove.
  if (sp.beam && !field)
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.beam_nofield') });
  //: ★the wave needs the same map, for the shell table's volumes and
  //: mid-shell major radii — and one thing more: |F(psi)| per surface,
  //: because accessibility is set by |B| ~ F/R.  Four Miller scalars carry
  //: neither, so this tier refuses rather than inventing a field.
  if (sp.lh && (!field || !geo.fpol))
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.lh_nofield') });

  // --- the state it starts from --------------------------------------------
  var n = geo.rho.length;
  var st = { te: new Float64Array(n), ti: new Float64Array(n),
             ne: new Float64Array(n), ni: new Float64Array(n),
             psi: new Float64Array(n), q: null,
             //: ★the rotation starts at REST and is present only when the
             //: channel is on.  `null` is what tells every consumer below
             //: — the closure's E x B shear among them — that no rotation
             //: was solved; a zero array would say "solved, and it came out
             //: zero", which is a different statement.
             omega: momentum ? new Float64Array(n) : null };
  //: ★the reference's own profiles, when the reader asked to start on them.
  //: They arrive on rho_tor [m] — the label this bar marches on — so this is
  //: an interpolation onto the ladder and nothing else: no re-gridding
  //: convention, no fit, no smoothing.
  var rp = sp.useRef && msg.refProf ? msg.refProf : null;
  var refAt = function (key, at) {
    var xs = rp.rho, vs = rp[key];
    if (!vs) return NaN;
    if (at <= xs[0]) return vs[0];
    for (var j = 1; j < xs.length; j++)
      if (xs[j] >= at) {
        var w = (at - xs[j - 1]) / (xs[j] - xs[j - 1]);
        return vs[j - 1] + w * (vs[j] - vs[j - 1]);
      }
    return vs[vs.length - 1];
  };
  for (var i = 0; i < n; i++) {
    var xb = geo.rho[i] / geo.rho[n - 1];
    var sh = Math.pow(Math.max(1 - xb * xb, 0), sp.peakT);
    var shn = Math.pow(Math.max(1 - xb * xb, 0), sp.peakN);
    st.te[i] = sp.edgeTe + (sp.te0 - sp.edgeTe) * sh;
    st.ti[i] = sp.edgeTi + (sp.ti0 - sp.edgeTi) * sh;
    st.ne[i] = sp.edgeNe + (sp.ne0 - sp.edgeNe) * shn;
    if (rp) {
      var rte = refAt('te', geo.rho[i]), rti = refAt('ti', geo.rho[i]),
          rne = refAt('ne', geo.rho[i]);
      if (isFinite(rte) && rte > 0) st.te[i] = rte;
      //: a reference with no ion temperature leaves T_i where the controls
      //: put it rather than silently making it the electron one
      if (isFinite(rti) && rti > 0) st.ti[i] = rti;
      if (isFinite(rne) && rne > 0) st.ne[i] = rne;
    }
    st.ni[i] = st.ne[i];
    st.psi[i] = evPsiOf(geo, i);
  }

  //: ★★THE IMPURITY IN THE QUASI-NEUTRALITY, when the reader asks for it.
  //: Until now Z_eff entered the resistivity, the radiation and the
  //: bootstrap while the main ion was undiluted — n_i = n_e — so a plasma
  //: with Z_eff = 1.7 had the fusion rate and the ion heat capacity of a
  //: pure hydrogenic one.  `ion_dilution` is the kernel's own LOC_N_ION = 1
  //: posture: n_i = (Z_imp - Z_eff)/(Z_imp - 1) n_e, and it REFUSES a Z_eff
  //: that this impurity cannot produce rather than flooring it.
  //:
  //: ★The impurity then goes into the march's ION LIST, where the kernel
  //: derives n_e = sum_s Z_s n_s from it — the same closure it applies to
  //: any composition, so nothing here has to assert quasi-neutrality by
  //: hand.
  //:
  //: ★★★T-C20 — AND THE DENSITY CHANNEL IS NO LONGER REFUSED BESIDE IT.
  //: The refusal read「这一版没有杂质输运来在两者之间裁决」, and that was a
  //: statement about the WIRING wearing a physics statement's clothes: the
  //: kernel's density channel has always been per-ion and the assembly layer
  //: has always taken an `ions` list; what was missing was a closure that
  //: filled the second species' D/v and a source that filled its block.
  //: Both exist now (`evClosure`, `evSourceFlat`).
  //: ★★And the refusal's REASON dissolves exactly when they do.  It was
  //: 「n_e 在演化而 Z_eff 被钉死，那是两套成分」 — true, and it stops being
  //: true the moment BOTH ions are channels: then `n_e = sum_s Z_s n_s` is
  //: quasi-neutrality's answer (the kernel's own rule, not an assertion made
  //: here) and **Z_eff is a RESULT**, computed from the two species that
  //: were solved for.  The slider stops being an input and the page says so.
  //: ★What Z_eff still sets in that mode is the STARTING composition — the
  //: dilution the first state is built from — and that is a different job
  //: from pinning it for all time.
  var zList = [1], edgeNi = [rp ? st.ne[n - 1] : sp.edgeNe];
  if (sp.quasi) {
    if (!(sp.impurityId >= 0) || !(sp.impurityZ > 1))
      return post({ type: 'error', where: 'evolve',
                    message: FyI18n.t('e.err.quasi_species') });
    var nMain = fy.ionDilution(st.ne, sp.zeff, sp.impurityZ);
    if (!nMain)
      return post({ type: 'error', where: 'evolve',
                    message: FyI18n.t('e.err.quasi_zeff',
                                      { zeff: sp.zeff, z: sp.impurityZ,
                                        name: sp.impurity }) });
    st.nz = new Float64Array(n);
    for (var qz = 0; qz < n; qz++) {
      st.ni[qz] = nMain[qz];
      st.nz[qz] = (st.ne[qz] - nMain[qz]) / sp.impurityZ;
    }
    //: ★what the composition IMPLIES for the fuel: n_D = n_T = n_i/2, so
    //: the D-T fraction is half the dilution — a derived number, and the
    //: control that used to set it is disabled on the page while it is.
    sp.dtEffective = 0.5 * nMain[0] / st.ne[0];
    zList = [1, sp.impurityZ];
    edgeNi = [st.ni[n - 1], st.nz[n - 1]];
    //: ★the composition is CHECKED against the closure that will be applied
    //: to it, rather than assumed: a mix whose electron density is not the
    //: one the reader asked for is a different plasma.
    var back = fy.quasiNeutralNe([{ n: st.ni, z: 1 },
                                  { n: st.nz, z: sp.impurityZ }]);
    for (var qc = 0; qc < n; qc++)
      if (Math.abs(back[qc] - st.ne[qc]) > 1e-6 * Math.abs(st.ne[qc]))
        return post({ type: 'error', where: 'evolve',
                      message: FyI18n.t('e.err.quasi_check') });
  }

  //: ★★CONTINUING A MARCH, rather than starting a new one.  A discharge is
  //: not one phase, and every run before this one began again from a
  //: prescribed analytic shape — so a ramp-up followed by a flat-top could
  //: only be modelled by pretending the flat-top started from a parabola.
  //:
  //: What is resumed is the STATE and only the state: the four profiles the
  //: channels own.  The geometry, the grid and every control are read afresh
  //: from this message, which is the point — continuing is how a reader
  //: CHANGES something and carries the plasma across the change.
  //:
  //: ★The grid must match, and it is checked here rather than interpolated:
  //: silently re-gridding a state would put a smoothing step between two
  //: halves of what the file calls one march.
  if (msg.resume) {
    var rs = msg.resume;
    if (!rs.te || rs.te.length !== n)
      return post({ type: 'error', where: 'evolve',
                    message: FyI18n.t('e.err.resume_grid',
                                      { was: rs.te ? rs.te.length : 0,
                                        now: n }) });
    for (var q2 = 0; q2 < n; q2++) {
      st.te[q2] = rs.te[q2]; st.ti[q2] = rs.ti[q2];
      st.ne[q2] = rs.ne[q2]; st.ni[q2] = rs.ne[q2];
      if (rs.psi && rs.psi.length === n) st.psi[q2] = rs.psi[q2];
    }
  }

  var sendOutlines = function () {
    try {
      post(Object.assign({ type: 'evolve_geometry' },
                         evOutlines(geo, field)));
    } catch (e) {
      //: a picture that cannot be drawn is not a run that cannot be made —
      //: the march owns the numbers, this owns the picture
      post({ type: 'evolve_geometry', outlines: [], lcfs: null,
             why: String(e && e.message || e) });
    }
  };
  sendOutlines();

  //: ★the edge the channels are PINNED to is the state's own last point when
  //: the reference supplied it: a march started on published profiles and
  //: held to a different edge would be solving a third problem
  var edgeTe = rp ? st.te[n - 1] : sp.edgeTe;
  var edgeTi = rp ? st.ti[n - 1] : sp.edgeTi;

  //: ★★THE PEDESTAL IS A RESULT NOW, when asked (T-M4): with the model on,
  //: the edge temperature is the EPED1-NN surrogate's pedestal top —
  //: p_ped/(2 n_e,ped k), EPED's own T_e = T_i convention — and the two
  //: sliders that used to set it are disabled on the page.  The ladder
  //: stops at `edgePsin` (~0.95) and EPED's own top sits at psi_N =
  //: 1 - width (~0.96 on ITER), so the Dirichlet point IS the pedestal
  //: top this bar's metric can stand on; the pedestal INTERIOR is not on
  //: the ladder and is not modelled — the model supplies the boundary
  //: value, nothing else.
  //:
  //: ★beta_N feeds back: EPED takes the GLOBAL beta_N, which is what the
  //: march is computing — so the model is re-evaluated each step on the
  //: PREVIOUS step's reading, lagged one step exactly like the Ohmic
  //: rate.  The first evaluation uses the initial profiles' own beta_N.
  //: ★a reference-pinned run keeps the reference's edge: reproducing
  //: published profiles under a different boundary would be a third
  //: problem again.
  var evBetaNOf = function (state) {
    var pv = new Float64Array(n);
    for (var bq = 0; bq < n; bq++)
      pv[bq] = (state.ne[bq] * state.te[bq]
                + state.ni[bq] * state.ti[bq]) * EV_QE;
    var vol = evVolume(geo.rho, geo.vprime);
    var pAvg = vol > 0 ? evVolInt(geo.rho, geo.vprime, pv) / vol : 0;
    var betaT = 2 * EV_MU0 * pAvg / (geo.b0 * geo.b0);
    var ipMA = Math.abs(sp.ip) / 1e6;
    return ipMA > 0 ? betaT * 100 * geo.a * Math.abs(geo.b0) / ipMA : 0;
  };
  var ctx0Pedestal = null;
  var evPedestalEval = function (betan) {
    var inp = {
      a: geo.a, betan: Math.max(0.05, betan), bt: Math.abs(geo.b0),
      delta: sp.delta, ip: Math.abs(sp.ip) / 1e6, kappa: sp.kappa,
      //: deuterium, or the DT average when the burn is on — the same
      //: composition statement the alpha channel makes
      mass: sp.alpha ? 2.5 : 2.0,
      neped: sp.edgeNe / 1e19, r: geo.r0, zeffped: sp.zeff };
    var res = fy.eped1nn(inp);
    return { inputs: inp,
             pPed: res.pPed[0], width: res.width[0],
             pPedAll: Array.from(res.pPed), widthAll: Array.from(res.width),
             extrapolation: res.extrapolation, worstInput: res.worstInput,
             tPed: res.pPed[0] / (2 * sp.edgeNe * EV_QE) };
  };
  if (sp.pedestal && !rp) {
    ctx0Pedestal = evPedestalEval(evBetaNOf(st));
    edgeTe = ctx0Pedestal.tPed;
    edgeTi = ctx0Pedestal.tPed;
  }

  var ctx = { sp: sp, geo: geo, rho: geo.rho, channels: channels,
              //: 第十五刀: the entry march reads the momentum switch here
              momentum: momentum,
              //: ★T-C16: the loop's state lives on `ctx` because it is
              //: STATEFUL across steps (the integral) — a controller
              //: rebuilt each step is a proportional controller wearing an
              //: integral gain's name.  `ratio0 = null` means「还没标定」;
              //: it is taken on the first step, from the run's own reading.
              ipCtl: sp.ipCtl ? { kp: sp.ipKp, ki: sp.ipKi, ratio0: null,
                                  integral: 0, last: null, log: [] } : null,
              //: ★T-C14：外环第一轮的稳态电流不欠松弛——它没有可混的上一轮
              fmFirstCurrent: true,
              psiPrev: null, pAux: (sp.pE + sp.pI) * 1e6,
              //: ★the two auxiliary powers the march itself integrated, kept
              //: APART from the total: the beam's is the one T-M11 compares
              //: against the shell quadrature, and a total that had a wave
              //: in it would answer a different question.
              pAuxBeam: 0, pAuxLh: 0, torqueBeam: null,
              pFastPar: null, pFastPerp: null,
              //: T-M4 — the pedestal record the readings and the export
              //: carry when the model drives the edge
              pedestal: ctx0Pedestal,
              //: the beam's own driven current on the ladder, when a beam
              //: is what the auxiliary power is, and the wave's beside it —
              //: two arrays, because attributing q(psi) is the whole point
              beamJ: null, lhJ: null,
              //: how many species the march's ion list carries, so the
              //: closure sizes its per-ion arrays to match
              nIon: zList.length };

  //: ★★THE ACTUATORS IN TIME.  Everything above is a flat-top: the powers
  //: and the loop voltage were constants for the whole march, so what this
  //: bar could model was one segment of a discharge and never a discharge.
  //: The shape is the KERNEL's trapezoid over the four phase times
  //: `[0, t_rampup_end, t_flattop_end, t_end]` — the same one the 0-D line
  //: uses, rather than four lines of arithmetic written again here.
  //:
  //: ★The FLAT-TOP value is 1: the trapezoid multiplies the sliders rather
  //: than replacing them, so a reader who switches the waveform off gets
  //: back exactly the run they had.  `start` and `end` are the fractions at
  //: t = 0 and t = t_end.
  //:
  //: ★V_loop is the CURRENT actuator here, and that is not a substitution:
  //: with the current channel on, I_p is a result of the flux the loop
  //: voltage moves, so a "current ramp" IS a loop-voltage waveform.  The
  //: I_p control stays what it always was — the equilibrium's current, used
  //: by the readings and by a coupled re-solve.
  var wfAt = function (t) {
    if (!sp.wave) return 1;
    var v = fy.zerodWaveform({
      phases: [0, sp.waveRamp, sp.waveFlat, sp.waveEnd],
      t: [t], flat: 1, start: sp.waveStart, end: sp.waveEnd2, which: 0 });
    return isFinite(v[0]) ? v[0] : 1;
  };
  //: ★★THE BEAM, when the reader asked for one.  It is re-evaluated per
  //: COUPLING BLOCK rather than per step: the deposition depends on n_e and
  //: T_e through the stopping cross-section, and re-attenuating 600 samples
  //: on nine rays every step would put a ray trace inside the inner loop
  //: for a change the block cadence already bounds.  The page says which
  //: cadence it ran on, and a frozen-geometry march evaluates it once.
  //:
  //: ★A beam that CANNOT be evaluated is a refusal, not a silent fall back
  //: to the Gaussian: a march reporting a deposition profile the reader did
  //: not ask for is the failure this whole item exists to remove.
  var beam = null, lh = null;
  var rebuildBeam = function () {
    if (sp.beam) {
      beam = evBeamDeposit(field, geo, st, sp);
      beam.cadence = sp.couple > 0 ? sp.couple : 0;
      //: ★T-M11: the part of the deposition the ladder cannot reach,
      //: measured on the kernel's own traced volumes.  It is the CALIBRE
      //: half of the gap between the two quadratures and it does not
      //: refine away, so it is separated here rather than left inside a
      //: single percentage nobody can decompose.
      var bo = evOutsideLadder(field, beam.edges, beam.pDep, sp.edgePsin);
      beam.pOutsideLadder = bo ? bo.power : null;
      beam.ladderEdgePsin = bo ? bo.edgePsin : null;
      //: ★T-M14: the conservative remap operator, rebuilt with the field
      //: and the ladder it belongs to — a beam re-evaluated on a refreshed
      //: equilibrium is re-remapped through that equilibrium's volumes
      beam.ladderOp = evShellLadderOp(field, geo, beam.edges);
    } else { beam = null; }
    if (sp.lh) {
      lh = evLhDeposit(field, geo, st, sp);
      lh.cadence = sp.couple > 0 ? sp.couple : 0;
      var lo = evOutsideLadder(field, lh.edges, lh.pDep, sp.edgePsin);
      lh.pOutsideLadder = lo ? lo.power : null;
      lh.ladderEdgePsin = lo ? lo.edgePsin : null;
      lh.ladderOp = evShellLadderOp(field, geo, lh.edges);
    } else { lh = null; }
  };
  rebuildBeam();
  var rebuildSources = function (t) {
    var k = wfAt(t === undefined ? 0 : t);
    var kp = sp.wavePower ? k : 1;
    ctx.waveNow = k;
    if (beam) {
      //: ★★THE POWER SPLIT IS A RESULT NOW.  With a beam, P_e and P_i are
      //: not two sliders: the split is `ion_power_fraction(E_crit, E)` per
      //: shell, and the two controls that used to set it are disabled on
      //: the page rather than quietly ignored here.
      var bE = beam.ladderOp.apply(beam.pE);
      var bI = beam.ladderOp.apply(beam.pI);
      ctx.heatE = new Float64Array(geo.rho.length);
      ctx.heatI = new Float64Array(geo.rho.length);
      for (var q = 0; q < geo.rho.length; q++) {
        ctx.heatE[q] = bE[q] * kp; ctx.heatI[q] = bI[q] * kp;
      }
      //: ★the array the reported ladder integral is the trapezoid OF —
      //: exported with the quadrature block so the gate's oracle can take
      //: numpy's own trapezoid of it and land on the same number
      beam.onLadder = new Float64Array(geo.rho.length);
      for (var qL = 0; qL < geo.rho.length; qL++)
        beam.onLadder[qL] = ctx.heatE[qL] + ctx.heatI[qL];
      //: ★what the MARCH actually put in, on the march's own metric — not
      //: the beam's shell quadrature.  The two are the same integral over
      //: two different discretisations of the same plasma, and reporting
      //: the shell number beside a march that used the ladder one would be
      //: a power nobody deposited.  Both travel; the page prints the gap.
      ctx.pAuxBeam = evVolInt(geo.rho, geo.vprime, ctx.heatE)
                   + evVolInt(geo.rho, geo.vprime, ctx.heatI);
      ctx.pAux = ctx.pAuxBeam;
      ctx.beamJ = beam.ladderOp.apply(beam.jNbi);
      if (kp !== 1)
        for (var q2 = 0; q2 < ctx.beamJ.length; q2++) ctx.beamJ[q2] *= kp;
      //: ★★THE TORQUE IS A RESULT NOW (T-M12), like the power split above:
      //: with a beam, the momentum source is the beam's own PROMPT input —
      //: tau_phi = p_dep (2/v_b) xi R per energy component, the kernel's,
      //: out of the SAME `beam_deposit` call as the pressure — and the
      //: slider that used to set the total is disabled on the page rather
      //: than quietly ignored here.  Remapped by the same conservative
      //: ladder operator as the heat, scaled by the same waveform (the
      //: torque rides the power).
      var bT = beam.ladderOp.apply(beam.torque);
      ctx.torque = new Float64Array(geo.rho.length);
      for (var q3 = 0; q3 < geo.rho.length; q3++)
        ctx.torque[q3] = bT[q3] * kp;
      ctx.torqueBeam = beam.torqueTotal * kp;
      //: ★T-M12: the fast-ion pressure BRANCHES on the ladder, remapped by
      //: the same conservative operator as the heat (it conserves ∫p dV,
      //: which is 2/3 of the branch's energy) and scaled by the same
      //: waveform.  Downstream, the refinement's p' takes their trace third
      //: and the readings' beta takes the same — that is where the split
      //: 进平衡与输运.
      var bPar = beam.ladderOp.apply(beam.pPar);
      var bPerp = beam.ladderOp.apply(beam.pPerp);
      ctx.pFastPar = new Float64Array(geo.rho.length);
      ctx.pFastPerp = new Float64Array(geo.rho.length);
      for (var q4 = 0; q4 < geo.rho.length; q4++) {
        ctx.pFastPar[q4] = bPar[q4] * kp;
        ctx.pFastPerp[q4] = bPerp[q4] * kp;
      }
    } else {
      ctx.pAux = (sp.pE + sp.pI) * 1e6 * kp;
      ctx.pAuxBeam = 0;
      ctx.torqueBeam = null;
      ctx.pFastPar = null;
      ctx.pFastPerp = null;
      ctx.heatE = evDeposit(geo.rho, geo.vprime, sp.depCentre, sp.depWidth,
                            sp.pE * 1e6 * kp);
      ctx.heatI = evDeposit(geo.rho, geo.vprime, sp.depCentre, sp.depWidth,
                            sp.pI * 1e6 * kp);
      ctx.beamJ = null;
      //: ★without a beam the torque rides the same prescribed Gaussian as
      //: the auxiliary power, because that Gaussian IS what this tier calls
      //: a beam.  What that assumes — one beam, no geometry, no
      //: shine-through — is exactly what the beam model above removes.
      //: `evDeposit` normalises by the volume integral, so the slider is a
      //: total torque in N m and the array is a torque DENSITY [J/m^3].
      ctx.torque = evDeposit(geo.rho, geo.vprime, sp.depCentre, sp.depWidth,
                             sp.torque * (sp.wavePower ? k : 1));
    }
    //: ★★THE WAVE, ON TOP OF WHATEVER THE BEAM OR THE GAUSSIAN PUT IN.  LH
    //: damps by electron Landau damping, so ALL of it goes to the electron
    //: channel — there is no ion share to split and inventing one would be
    //: a second deposition model.  The driven current is its own array
    //: beside the beam's, never summed into it: attributing q(psi) is the
    //: whole reason this term exists.
    ctx.lhJ = null;
    ctx.pAuxLh = 0;
    if (lh) {
      var lE = lh.ladderOp.apply(lh.pDep);
      for (var w1 = 0; w1 < geo.rho.length; w1++) ctx.heatE[w1] += lE[w1] * kp;
      ctx.pAuxLh = evVolInt(geo.rho, geo.vprime, lE) * kp;
      ctx.pAux += ctx.pAuxLh;
      lh.onLadder = new Float64Array(geo.rho.length);
      for (var w3 = 0; w3 < geo.rho.length; w3++)
        lh.onLadder[w3] = lE[w3] * kp;
      ctx.lhJ = lh.ladderOp.apply(lh.jLh);
      if (kp !== 1)
        for (var w2 = 0; w2 < ctx.lhJ.length; w2++) ctx.lhJ[w2] *= kp;
    }
    ctx.fuel = evDeposit(geo.rho, geo.vprime, sp.fuelCentre, sp.fuelWidth,
                         sp.fuel * 1e20 * (sp.waveFuel ? k : 1));
    //: ★T-C20：杂质的那一份，同一条沉积、自己的速率。缺省 0——「只有再分配」
    //: 是一个正当的答案，而不是「没有这一项」。
    ctx.fuelZ = sp.fuelZ > 0
      ? evDeposit(geo.rho, geo.vprime, sp.fuelCentre, sp.fuelWidth,
                  sp.fuelZ * 1e20 * (sp.waveFuel ? k : 1))
      : null;
    ctx.vLoopNow = sp.vLoop * (sp.waveVloop ? k : 1);
    //: ★T-C16: the I_p SET POINT rides the same waveform when asked, so the
    //: loop can be given a schedule rather than only a constant — which is
    //: what upstream's controller tracks.  With the feedback off this is
    //: read by nothing.
    ctx.ipTargetNow = sp.ip * (sp.waveIp ? k : 1);
    //: ★the loop voltage BEFORE the I_p loop touches it.  The controller
    //: adds to this rather than to its own previous output, so a waveform
    //: and a feedback loop can both be on without the two compounding.
    ctx.vLoopBase = ctx.vLoopNow;
  };
  rebuildSources(msg.tStart || 0);

  //: ★the clock CONTINUES on a resumed march: the waveform is a function
  //: of discharge time, and a second segment that restarted the clock would
  //: replay the ramp-up it was supposed to follow.
  var trace = [], steps = 0, tNow = msg.tStart || 0, wPrev = null, dwdt = 0;
  var blocks = sp.couple > 0
    ? Math.max(1, Math.ceil(sp.nSteps / sp.couple)) : 1;
  var perBlock = sp.couple > 0 ? sp.couple : sp.nSteps;
  var vprimeOld = null, fit = null, bpTarget = NaN, bpEq = NaN, bpFix = NaN;
  var rounds = [], crashes = [], settledEarly = false, refineWhy = null;
  //: ★the FREE solve's own summary, kept beside the equilibrium the march
  //: runs on.  With the refinement on, `eq` is the refined field, whose
  //: pressure IS the transport's — so reading beta_p off it would feed the
  //: (emp, enp, beta0) loop its own answer and freeze it.  That loop is
  //: about the FAMILY, so it keeps seeing the family.
  var eqFree = eq, refinedField = null;
  var dtNow = sp.dt;
  //: ★the closure once BEFORE the first step, so the exchange cap below has
  //: a rate to bound the first step with.  Without it the cap starts one
  //: step late — and the first step is the one a reader is most likely to
  //: have made enormous.
  if (channels.heat) evClosure(ctx, st);

  // --- T-C13: the flux-match tier solves, it does not march ----------------
  //
  // ★★A ROOT FIND INSTEAD OF A MARCH, and that is what「稳态」 means here:
  // the answer is the gradient vector at which the model flux equals the
  // power that has to cross each surface, found by the kernel's own Newton
  // machine.  There is no time axis and the bar says so — the 时间轨迹 panel
  // is withdrawn on this tier rather than drawn from a single point.
  //
  // ★★AND IT DOES NOT FALL BACK.  A match that will not converge is reported
  // AS a failure, naming which of the two things went wrong (the kernel
  // refused, or the residual never reached the tolerance) — the whole reason
  // this tier exists is that the bar could otherwise only ever run a
  // prescribed chi, so quietly becoming one again would be worse than
  // stopping.
  var fluxMatch = null, stationary = null;
  if (sp.closure === 4) {
    //: ★the composition the steady-current round needs, handed to `ctx`
    //: once here rather than threaded through every call: it is the SAME
    //: pair the march below uses, so the two rounds cannot end up on
    //: different ion lists.
    ctx.zList = zList; ctx.edgeNi = edgeNi;
    //: ★the free solve the equilibrium half compares its beta_p against —
    //: the FAMILY's, not the refined one, exactly as the coupled march
    //: keeps them apart
    ctx.eqFree = eqFree;
    var edgePair = { te: edgeTe, ti: edgeTi };
    //: the pedestal model, handed to the matcher so it can move the anchor
    //: between iterations exactly as the march moves it between steps
    ctx.evPedestal = evPedestalEval;
    ctx.evBetaN = evBetaNOf;
    // --- T-C14: the stationary outer loop --------------------------------
    //
    // ★★IT IS THE PICARD THAT WAS ALREADY RUNNING, widened.  Inside one
    // match the burn is frozen at the iteration boundary and the pedestal is
    // lagged by one — both because a quantity that moves WITH the unknowns
    // makes the target chase the answer (measured; T-C13).  `sigma`, the
    // bootstrap current and the sawtooth are in exactly that class, so they
    // belong in the same split rather than in a second one: match with them
    // held, then move them, then match again.
    //
    // ★★`fmOuter = 1` IS the previous behaviour, exactly — one match, no
    // current round — so every case shipped before this runs unchanged.
    //
    // ★What is NOT here yet is the equilibrium half (步 6): re-solving the
    // free boundary changes the rho ladder itself, so the profiles need the
    // conservative remap the marching tiers get through `vprimeOld`.  That
    // is a separate batch and the record says so rather than leaving a
    // reader to assume the geometry moved.
    var outerRounds = [], outerConverged = false, outerWhy = null;
    var pOf = function (state) {
      var pv = new Float64Array(n);
      for (var i2 = 0; i2 < n; i2++)
        pv[i2] = (state.ne[i2] * state.te[i2]
                  + state.ni[i2] * state.ti[i2]) * EV_QE;
      return pv;
    };
    var relMax = function (a2, b2) {
      var num = 0, den = 0;
      for (var i3 = 0; i3 < a2.length; i3++) {
        num = Math.max(num, Math.abs(a2[i3] - b2[i3]));
        den = Math.max(den, Math.abs(b2[i3]));
      }
      return den > 0 ? num / den : 0;
    };
    for (var rnd = 0; rnd < sp.fmOuter; rnd++) {
      var pPrev = pOf(st), qPrev = st.q ? Float64Array.from(st.q) : null;
      var fmOut;
      try {
        fmOut = evFluxMatch(ctx, st, edgePair, (function (r) {
          return function (k, h) {
            post({ type: 'evolve_match', iteration: k,
                   iterations: sp.fmIter, worst: h.worst, tol: sp.fmTol,
                   round: r + 1, rounds: sp.fmOuter });
          };
        }(rnd)));
      } catch (eFm) {
        return post({ type: 'error', where: 'evolve',
                      message: FyI18n.t('e.err.fm_failed',
                                        { why: String(eFm && eFm.message
                                                      || eFm) }) });
      }
      st = fmOut.st;
      fluxMatch = fmOut.record;
      edgeTe = edgePair.te; edgeTi = edgePair.ti;
      //: ★a round whose MATCH did not converge ends the loop: alternating
      //: onto a state the inner solve never reached would be iterating a
      //: quantity nobody solved for
      if (!fluxMatch.converged) { outerWhy = 'match'; break; }
      if (sp.fmOuter <= 1) { outerConverged = true; break; }
      var cur = evStationaryCurrent(ctx, st);
      if (!cur || cur.failed) {
        outerWhy = (cur && cur.failed) || 'current';
        break;
      }
      //: ★★步 6：平衡在电流与锯齿之后重解，次序照上游（源→台基→输运→电流→
      //: 锯齿→平衡）。它换掉 rho 梯子，所以剖面按 psi_N 相对标一次——见
      //: `evRemap`；随后**照推进档那一套把 ctx 收拾干净**——源、束流、
      //: 截面图都要重建，否则下一轮的 TGLF 会拿到旧长度的数组。
      //: ★the label the previous round's profiles are ON, captured before
      //: the re-solve moves it — the convergence numbers below compare two
      //: rounds and both have to be on one grid
      var psinBefore = geo.psin;
      var eqRound = evStationaryEquilibrium(ctx, st, chan, prof, beta0,
                                           cur.ip);
      if (eqRound && eqRound.failed) { outerWhy = eqRound.failed; break; }
      if (eqRound && eqRound.geo) {
        geo = eqRound.geo; beta0 = eqRound.beta0;
        prof = { beta0: beta0, emp: eqRound.fit ? eqRound.fit.emp : sp.emp,
                 enp: eqRound.fit ? eqRound.fit.enp : sp.enp, r0: sp.r0Src };
        eq = eqRound.eq; eqFree = eq;
        freeLog.push(assign({ block: rnd + 1 }, eqRound.free));
        //: ★★EVERYTHING THE NEW LADDER INVALIDATES, rebuilt — the same five
        //: lines the coupled march runs after its own re-solve.  Leaving
        //: them out is what made the next round's TGLF receive source
        //: arrays sized for the OLD ladder; the kernel refused with
        //: 「空指针或缓冲区长度不符」 and the run stopped, which is at least
        //: loud.  ★`ctx.geo` / `ctx.rho` / `n` move here rather than inside
        //: the helper because these five live in this closure.
        field = { psi: eq.psi, psiAxis: eq.psiAxis, psiBnd: eq.psiBnd,
                  axisR: eq.axisR, axisZ: eq.axisZ,
                  r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz,
                  nr: grid.nr, nz: grid.nz,
                  limR: M.limiter.r, limZ: M.limiter.z };
        ctx.geo = geo; ctx.rho = geo.rho; ctx.psiPrev = null;
        rebuildBeam();
        rebuildSources(tNow);
        //: ★the convergence numbers compare two ROUNDS, so the previous
        //: round's pressure and q are relabelled onto the new ladder too —
        //: otherwise the「变化」 would be mostly the grid moving
        pPrev = evRemap(psinBefore, pPrev, geo.psin);
        if (qPrev) qPrev = evRemap(psinBefore, qPrev, geo.psin);
        n = geo.rho.length;
      }
      var dP = relMax(pOf(st), pPrev);
      var dQ = qPrev && st.q ? relMax(st.q, qPrev) : NaN;
      //: ★the FIRST round has nothing to compare against (`q` came from the
      //: starting profiles, not from a previous round's steady solve), so
      //: it never counts as converged however small the numbers look
      var first = rnd === 0;
      var round = { round: rnd + 1, dPressure: dP, dQ: dQ,
                    q0: cur.q0, ip: cur.ip, ipRequested: cur.ipRequested,
                    psiRepaired: cur.psiRepaired,
                    sawtooth: cur.sawtooth || null,
                    //: ★步 4 解出来的环电压——平顶的磁通消耗，是这一步的**产出**
                    vLoop: cur.vLoop, vLoopClamped: cur.vLoopClamped,
                    matchIterations: fluxMatch.iterations,
                    matchWorst: fluxMatch.worst,
                    //: ★步 6 的账：解出来了没有、a 动了多少、两个 beta_p，
                    //: 以及跳过时的理由——跳过也要写出来
                    equilibrium: eqRound && eqRound.geo
                      ? { aOld: eqRound.aOld, aNew: eqRound.aNew,
                          beta0: eqRound.beta0, bpTarget: eqRound.bpTarget,
                          bpEq: eqRound.bpEq, ipUsed: eqRound.ipUsed,
                          free: eqRound.free }
                      : null,
                    equilibriumSkipped: eqRound ? (eqRound.skipped || null)
                                                : null };
      outerRounds.push(round);
      post({ type: 'evolve_round', round: rnd + 1, rounds: sp.fmOuter,
             dPressure: dP, dQ: dQ });
      if (!first && dP < sp.fmOTol && (isNaN(dQ) || dQ < sp.fmOTol)) {
        outerConverged = true;
        break;
      }
    }
    stationary = sp.fmOuter > 1
      ? { rounds: outerRounds, converged: outerConverged, why: outerWhy,
          tolerance: sp.fmOTol, maxRounds: sp.fmOuter,
          //: ★how many rounds the geometry actually took part in, and when
          //: it took part in none, WHY — a reader must not have to infer
          //: either from a missing key
          equilibriumRounds: outerRounds.filter(function (r) {
            return r.equilibrium;
          }).length,
          equilibriumWhy: (outerRounds.length
                           && outerRounds[0].equilibriumSkipped) || null }
      : null;
    //: ★ONE reading, at the matched state — and it is the state's own
    //: reading, not a step's: `dt`, the crash count and dW/dt are zero
    //: because nothing advanced, and `steady` is the MATCHER's verdict
    //: rather than the marching steady test.  ★`evaluate` has already run
    //: the closure and the sources at this exact state, so `ctx.lastDiag`
    //: is theirs; recomputing them here would be a second answer to the
    //: same question.
    var rdFm = evReadings(ctx, st, ctx.lastDiag, 0);
    rdFm.dt = 0; rdFm.delta = fluxMatch.worst; rdFm.retries = 0;
    rdFm.steady = fluxMatch.converged;
    rdFm.crashes = 0; rdFm.crashed = false; rdFm.dwdt = 0;
    if (sp.pedestal && ctx.pedestal) {
      rdFm.pedTPed = edgeTe;
      rdFm.pedPPed = ctx.pedestal.pPed;
      rdFm.pedWidth = ctx.pedestal.width;
      rdFm.pedExtrap = ctx.pedestal.extrapolation;
    }
    trace.push(rdFm);
    post({ type: 'evolve_step', step: 1, nSteps: 1,
           rho: geo.rho, psin: geo.psin, reading: rdFm,
           te: st.te, ti: st.ti, ne: st.ne, q: st.q,
           chiE: ctx.lastChi ? ctx.lastChi.e : null,
           chiI: ctx.lastChi ? ctx.lastChi.i : null,
           jni: ctx.lastBs || null,
           geoSource: geo.source, coupled: 0 });
    //: the march loop below is skipped whole; `rounds` stays empty, which is
    //: exactly what「没有一轮平衡交替」 should look like in the file
    blocks = 0;
  }

  //: ★★★S-2b — THE ONE BRANCH.  When `ENTRY_SCOPE` says the kernel entry
  //: carries this configuration whole, the march below does not run: the
  //: entry runs it, one step per call, and fills the same `st` / `trace` /
  //: `crashes` / `steps` / `tNow` the loop fills.  The tail of this function
  //: — the readings, the record, the single `post` that carries them — is
  //: untouched, so there is still ONE exit and one payload.
  //:
  //: ★What this buys is NOT fewer lines here (the loop stays, for every
  //: configuration the entry does not carry).  It is that a configuration
  //: with a corpus case is ONE orchestration on both hosts: Python's
  //: `model.evolve` calls this same entry with these same blocks.  Before
  //: it, the two hosts ran two loops that a gate had to keep equal — an
  //: agreement by JUDGEMENT rather than by construction.
  var entryMiss = evScopeMiss(sp);
  var viaEntry = blocks > 0 && entryMiss.length === 0;
  if (viaEntry) {
    var em = evEntryMarch(ctx, st, geo, sp, trace, crashes, tNow);
    steps = em.steps;
    tNow = em.tNow;
    settledEarly = em.settled;
    blocks = 0;
  }

  for (var blk = 0; blk < blocks; blk++) {
    var take = Math.min(perBlock, sp.nSteps - steps);
    if (take <= 0) break;
    var sn = new Float64Array(n);
    if (channels.density) sn.set(ctx.fuel);
    //: ★T-C20：杂质自己那一块源。与主离子的加料同一条规矩——**规定的**沉积，
    //: 不是溅射/注入/壁再循环模型（那些没有可判的外部算例，本仓就不写）。
    var snZ = null;
    if (channels.density && zList.length > 1 && ctx.fuelZ) snZ = ctx.fuelZ;
    var res = null, firstOfBlock = true;

    //: ★★ONE STEP PER CALL, and that is a physics requirement rather than a
    //: style: `CoreMarch` takes `q_e`/`q_i` at construction and holds them
    //: for the whole march, so a call carrying twenty steps would drive all
    //: twenty with the alpha power, the radiation and the Ohmic power of the
    //: state it STARTED from — while the table beside it reported the ones
    //: that had moved.  A burning-plasma page may not have its heating
    //: decoupled from its temperature.  The price is one state save/load per
    //: step, which is arithmetic on `n` doubles.
    for (var stp = 0; stp < take; stp++) {
      //: ★the actuators at THIS time, not at the start of the run.  With no
      //: waveform this is the same arithmetic it always was (the factor is
      //: exactly 1), which is why switching it off reproduces the old run.
      if (sp.wave) rebuildSources(tNow);
      //: the turbulent closure's cadence, counted in STEPS by the loop that
      //: takes them
      if (sp.closure === 3
          && steps % Math.max(1, sp.turbEvery | 0) === 0) ctx.turbDue = true;
      var src = evSources(ctx, st, dtNow);
      //: ★★T-C16: the loop moves the boundary rate BEFORE the step that
      //: uses it, on the state the step starts from — the same lag every
      //: other feedback on this bar carries (the Ohmic rate, the pedestal),
      //: said the same way.  With the loop off, `ctx.vLoopNow` is whatever
      //: the slider (and the waveform) put there and nothing here runs.
      if (ctx.ipCtl) evIpControl(ctx, st, dtNow, tNow);
      var psiAtStart = st.psi.slice();
      //: ★★THE EXCHANGE TIME BOUNDS THE STEP, and it has to be bounded
      //: HERE because nothing downstream can see it.  The collisional
      //: exchange reaches the operator EXPLICITLY (the kernel puts it in
      //: the two source terms), so the heat pair relaxes towards each
      //: other at about `nu_exch` per second and an explicit step longer
      //: than that time does not blow up — it QUIETLY DECOUPLES the two
      //: channels.  Measured on the ITER case shipped with this bar: the
      //: adaptive controller, whose target is a 2 % change per step, grew
      //: dt to 0.13 s against an exchange time of ~0.1 s and reported
      //: T_e = 11.8 keV beside T_i = 6.3 keV — a 2:1 split with no warning
      //: anywhere, and half the alpha power that the resolved run gives.
      //: The controller cannot see this: the change per step stays small
      //: precisely because the channels stopped talking.
      //:
      //: The cap is a QUARTER of the fastest exchange time on the grid.
      //: It binds only where it must, and every time it does is counted
      //: and reported — a step silently shortened is its own kind of
      //: opaque.
      var dtMaxNow = sp.dtMax, capNow = 0;
      if (channels.heat && ctx.lastCr && ctx.lastCr.exch) {
        var nuMax = 0, ex = ctx.lastCr.exch;
        for (var v2 = 0; v2 < ex.length; v2++)
          if (isFinite(ex[v2]) && ex[v2] > nuMax) nuMax = ex[v2];
        if (nuMax > 0) {
          capNow = 0.25 / nuMax;
          if (capNow < dtMaxNow) dtMaxNow = capNow;
          if (dtNow > capNow) dtNow = capNow;
          ctx.tauExch = 1 / nuMax;
        }
      }
      res = fy.coreMarch({
        rho: geo.rho, te: st.te, ti: st.ti,
        ni: evIonFlat(st, zList.length, n), z: zList,
        edgeNi: edgeNi, psi: st.psi,
        vprime: geo.vprime,
        //: the moved metric is consumed by the FIRST step after a re-solve
        //: and by no other
        vprimeOld: firstOfBlock ? vprimeOld : null,
        gm3: geo.gm3, gm2: geo.gm2, fpol: geo.fpol, b0: geo.b0,
        qE: src.qE, qI: src.qI,
        sN: evSourceFlat(sn, zList.length, n, snZ),
        dt: dtNow, dtTarget: sp.dtTarget, dtMin: sp.dtMin, dtMax: dtMaxNow,
        maxOuter: 1, tolSteady: sp.tolSteady, nCoupling: sp.nCoupling,
        edgeTe: edgeTe, edgeTi: edgeTi,
        edgePsi: st.psi[n - 1],
        //: ★★THE EDGE RATE IS +V_loop, and the sign is the whole of this
        //: comment.  `evPsiOf` hands the march a psi that INCREASES
        //: outward (the kernel's monotone repair demands it) while the
        //: app's own gauge has the axis at the maximum — so the profile is
        //: flipped on the way in, and the boundary RATE has to be flipped
        //: with it.  It was not: the rate went in as `-V_loop`, which in
        //: the marched gauge lowers the edge flux, flattens dpsi/drho and
        //: DRIVES THE CURRENT DOWN.
        //:
        //: Measured on the EAST case shipped with this bar (0.5 s, current
        //: channel, constant chi): V_loop = 0 held q95 at 3.1, V_loop =
        //: +0.5 V took it to 26 and then to a NaN, and V_loop = -1 V — the
        //: physically wrong sign — was the one that raised the current.  A
        //: transformer that de-energised the plasma.
        //:
        //: ★It hid because the only thing the Ohmic term does with the rate
        //: is SQUARE it: `sigma E^2` is positive either way, so the gate
        //: that asked "does the loop voltage drive an Ohmic power" passed
        //: on the wrong sign.  The check beside it now asks whether the
        //: current went UP.
        //:
        //: The arithmetic, in the marched gauge: the channel's own relation
        //: between a moving flux and the current it drives is
        //: `j = 2 pi rho sigma (dpsi/dt) / V'`, which on a circular surface
        //: (V' = 4 pi^2 R0 rho) is `sigma V_loop / (2 pi R0)` when
        //: `dpsi/dt = V_loop`.
        edgePsiRate: ctx.vLoopNow,
        b0Dot: sp.b0Dot, dPc: sp.dPc, tol: 1e-10, maxInner: 60,
        channels: channels,
      }, function (state) { return evClosure(ctx, state); });
      firstOfBlock = false;

      //: ★the ion list comes back flat and is split here, so everything
      //: downstream keeps reading `st.ni` as THE MAIN ION.  A state whose
      //: `ni` silently became two species concatenated would be read as a
      //: main-ion density twice as long as the grid.
      st = { te: res.te, ti: res.ti, ne: res.ne,
             ni: res.ni.subarray ? res.ni.subarray(0, n) : res.ni.slice(0, n),
             nz: zList.length > 1
               ? (res.ni.subarray ? res.ni.subarray(n, 2 * n)
                                  : res.ni.slice(n, 2 * n))
               : null,
             psi: res.psi, q: res.q, omega: st.omega };
      //: ★★the momentum channel, advanced on the SAME dt the core march
      //: took, from the state it started from, with the chi_i the closure
      //: produced for that step.  Split, and `evMomentumStep` says what the
      //: split costs.
      if (momentum) {
        st.omega = evMomentumStep(ctx, st,
                                  st.omega || new Float64Array(n),
                                  (ctx.lastChi && ctx.lastChi.i)
                                    || evFill(n, sp.chi0), res.dt);
        ctx.omega = st.omega;
      }
      //: ★the crash happens BETWEEN steps, on the state the step reached —
      //: it is an event, not a term in the equation, and the next step
      //: starts from the mixed profiles
      var saw = evSawtooth(ctx, st);
      if (saw) {
        saw.step = steps + 1;
        saw.t = tNow + res.dt;
        crashes.push(saw);
      }
      //: the flux the step started from, for the NEXT step's Ohmic rate.
      //: ★A CRASH BREAKS THAT RATE: reconnection moves psi by an amount no
      //: resistive step took, and `sigma E^2` on it would report a spike of
      //: Ohmic power that never happened.  So the step after a crash has no
      //: rate to measure and no Ohmic term, which the page states.
      ctx.psiPrev = (saw && !saw.refused) ? null : psiAtStart;
      steps += 1;
      //: ★the controller's dt is carried forward: it is the machine's
      //: report of what the next step should be, and a march that threw it
      //: away would adapt inside a step and forget between steps
      dtNow = res.dt;
      //: ★a step that RAN AT the exchange ceiling is counted, not only one
      //: that had to be cut back to it: the reader's question is "was my dt
      //: the one that was used", and the answer is no in both cases.
      if (capNow > 0 && capNow < sp.dtMax && res.dt >= capNow * (1 - 1e-9))
        ctx.dtCapped = (ctx.dtCapped | 0) + 1;
      tNow += res.dt;
      var rd = evReadings(ctx, st, src.diag, tNow);
      //: ★T-M4: the NEXT step's edge from THIS step's beta_N — lagged one
      //: step, like the Ohmic rate; the reading carries what was applied
      //: so a reader can see the boundary the step actually ran under.
      if (sp.pedestal && !rp) {
        rd.pedTPed = edgeTe;
        rd.pedPPed = ctx.pedestal ? ctx.pedestal.pPed : null;
        rd.pedWidth = ctx.pedestal ? ctx.pedestal.width : null;
        rd.pedExtrap = ctx.pedestal ? ctx.pedestal.extrapolation : null;
        ctx.pedestal = evPedestalEval(rd.betaN);
        edgeTe = ctx.pedestal.tPed;
        edgeTi = ctx.pedestal.tPed;
      }
      rd.dt = res.dt; rd.delta = res.delta; rd.retries = res.retries;
      rd.steady = res.steady;
      rd.crashes = crashes.length;
      rd.crashed = !!(saw && !saw.refused);
      rd.dwdt = wPrev === null ? 0
        : (rd.wTh - wPrev) / Math.max(res.dt, 1e-12);
      wPrev = rd.wTh;
      trace.push(rd);
      if (steps % Math.max(1, sp.report | 0) === 0 || steps === sp.nSteps)
        post({ type: 'evolve_step', step: steps, nSteps: sp.nSteps,
               rho: geo.rho, psin: geo.psin, reading: rd,
               te: st.te, ti: st.ti, ne: st.ne, q: st.q, ni: st.ni, nz: st.nz || null, omega: st.omega || null,
               chiE: ctx.lastChi ? ctx.lastChi.e : null,
               chiI: ctx.lastChi ? ctx.lastChi.i : null,
               jni: ctx.lastBs || null,
               geoSource: geo.source, coupled: blk });
      //: ★a march that reached its own steady state STOPS, and says it did:
      //: running the remaining steps would report "time was up" for a run
      //: that had actually settled
      if (res.steady) { settledEarly = true; break; }
    }

    //: ★the block's own record.  The equilibrium half BELOW writes its
    //: numbers back into this entry rather than into the next one: a row
    //: whose beta_p came from the previous block's alternation and whose
    //: refinement came from this one is a row nobody can read.
    rounds.push({ block: blk + 1, steps: steps, settled: res.steady,
                  delta: res.delta, psiRepaired: res.psiRepaired,
                  dt: res.dt, retries: res.retries,
                  fit: null, bpTarget: NaN, bpEq: NaN, bpFix: NaN,
                  beta0: beta0, refined: null, refineWhy: null,
                  //: the equilibrium half below writes its own solve's
                  //: verdict here; a block that re-solved nothing keeps null
                  free: null });

    if (settledEarly) break;

    // --- the equilibrium half, if the reader asked for one ----------------
    if (sp.couple > 0 && sp.geometry === 'device' && blk < blocks - 1) {
      var vpOldOnPsin = { psin: geo.psin.slice(), vprime: geo.vprime.slice() };
      //: the pressure the march reached, and the gradient the solver's own
      //: shape function IS
      var pPa = new Float64Array(n), dp = new Float64Array(n);
      //: T-M12: the fast branches' trace third rides along, so the shape
      //: fit, the beta_p target and the refinement all see the SAME total
      //: pressure — thermal plus fast — rather than three different ones
      var pfT = null;
      if (ctx.pFastPar) {
        pfT = new Float64Array(n);
        for (var kf = 0; kf < n; kf++)
          pfT[kf] = (ctx.pFastPar[kf] + 2 * ctx.pFastPerp[kf]) / 3;
      }
      for (var k2 = 0; k2 < n; k2++)
        pPa[k2] = (st.ne[k2] * st.te[k2] + st.ni[k2] * st.ti[k2]) * EV_QE
                + (pfT ? pfT[k2] : 0);
      for (var k3 = 0; k3 < n; k3++) {
        var lo = Math.max(k3 - 1, 0), hi = Math.min(k3 + 1, n - 1);
        var dpsin = geo.psin[hi] - geo.psin[lo];
        dp[k3] = dpsin !== 0 ? (pPa[hi] - pPa[lo]) / dpsin : 0;
      }
      fit = evFitShape(geo.psin, dp);
      var volNow = evVolume(geo.rho, geo.vprime);
      var pAvgT = volNow > 0 ? evVolInt(geo.rho, geo.vprime, pPa) / volNow : 0;
      var bpa = EV_MU0 * Math.abs(sp.ip) / (2 * Math.PI * geo.a);
      bpTarget = 2 * EV_MU0 * pAvgT / (bpa * bpa);
      var pAvgE = evEqPressure(eqFree, geo);
      bpEq = isFinite(pAvgE) ? 2 * EV_MU0 * pAvgE / (bpa * bpa) : NaN;
      //: ★beta0 is the solver's pressure/paramagnetic MIX, not a beta.  It
      //: is moved by the RATIO of the two beta_p — the one the transport
      //: solution implies against the one the last equilibrium carried —
      //: under-relaxed, and both numbers are reported so the reader can see
      //: whether the alternation is closing or wandering.
      if (isFinite(bpTarget) && isFinite(bpEq) && bpEq > 0) {
        var want = beta0 * Math.pow(bpTarget / bpEq, sp.relax);
        beta0 = Math.min(0.95, Math.max(0.05, want));
      }
      prof = { beta0: beta0, emp: fit ? fit.emp : sp.emp,
               enp: fit ? fit.enp : sp.enp, r0: sp.r0Src };
      eq = summarize(freeSolve(chan, prof, sp.ip, evFreeOpts(sp)), prof, {});
      eqFree = eq;
      //: ★this block's own solve, logged whether or not it got there.  The
      //: refinement below is held to the FREE solve's convergence (that is
      //: what the zero test measures), so a block whose free solve ran out
      //: of iterations produces a refinement that looks worse for a reason
      //: that is not the refinement's.
      var freeNow = assign({ block: blk + 1 }, freeReport(eq));
      freeLog.push(freeNow);
      //: ★★AND THEN, when asked, REFINED on the transport's own pressure.
      //: The free solve above fixes the boundary and the external field;
      //: this replaces the two-parameter plasma source with p' and FF' as
      //: polynomials, so the pressure gradient the march produced goes in
      //: as itself rather than through `(emp, enp)`.  A refinement that
      //: fails is REPORTED and the family's answer stands — a coupled march
      //: that silently fell back would be reporting a shape it did not use.
      var refined = null;
      //: ★per BLOCK, not per run: a refinement that failed in block 1 and
      //: succeeded in block 2 must not leave block 2 wearing block 1's
      //: reason
      refineWhy = null;
      if (sp.coupleFixed) {
        try {
          refined = evFixedRefine(eq, geo, st, sp, sp.degP, sp.degF, prof,
                                  pfT);
        } catch (e2) {
          refined = null;
          refineWhy = String(e2 && e2.message || e2);
        }
        if (!refined && !refineWhy) refineWhy = FyI18n.t('e.err.refine');
      }
      var geoNew = refined ? refined.geo : evLadderFromSolve(eq, sp);
      if (refined) eq = refined.eq;
      //: ★the beta_p the REFINED equilibrium carries, on its own metric and
      //: from the pressure recovered out of the p' the solve ran on — the
      //: number the two-parameter family could not reach.  Reported beside
      //: the other two so "the pressure feed-back bites" is a comparison a
      //: reader can make rather than a claim this code makes.
      bpFix = NaN;
      if (refined) {
        var bpaR = EV_MU0 * Math.abs(sp.ip) / (2 * Math.PI * geo.a);
        var pAvgF = evEqPressure(refined.eq, geoNew);
        bpFix = isFinite(pAvgF) ? 2 * EV_MU0 * pAvgF / (bpaR * bpaR) : NaN;
      }
      //: ★the profiles travel on psi_N, the label both ladders share.  The
      //: rho grid MOVED — that is what a re-solved equilibrium does — and
      //: carrying arrays across node by node would be comparing two
      //: different radii.
      var remap = function (v) { return evRemap(geo.psin, v, geoNew.psin); };
      st = { te: remap(st.te), ti: remap(st.ti), ne: remap(st.ne),
             ni: remap(st.ni),
             //: the rotation moves onto the new ladder with everything else
             omega: st.omega ? (ctx.omega = remap(st.omega)) : null,
             psi: (function () {
               var p2 = new Float64Array(geoNew.rho.length);
               for (var j = 0; j < p2.length; j++) p2[j] = evPsiOf(geoNew, j);
               return p2;
             })(), q: null };
      vprimeOld = evRemap(vpOldOnPsin.psin, vpOldOnPsin.vprime, geoNew.psin);
      geo = geoNew;
      field = { psi: eq.psi, psiAxis: eq.psiAxis, psiBnd: eq.psiBnd,
                axisR: eq.axisR, axisZ: eq.axisZ,
                r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz,
                nr: grid.nr, nz: grid.nz,
                limR: M.limiter.r, limZ: M.limiter.z };
      ctx.geo = geo; ctx.rho = geo.rho; n = geo.rho.length;
      ctx.psiPrev = null;
      //: ★the beam follows the equilibrium it stops in: a new psi map is a
      //: new set of chords, a new attenuation and a new shell table.  A
      //: coupled march whose beam kept block 0's deposition would be
      //: heating a plasma that had moved.
      rebuildBeam();
      rebuildSources(tNow);
      //: ★the picture follows the alternation: a coupled run whose
      //: cross-section still showed the first equilibrium would be drawing
      //: a plasma the profiles no longer live on
      sendOutlines();
      post({ type: 'evolve_couple', block: blk + 1, beta0: beta0,
             //: the free solve this block's geometry came out of
             free: freeNow,
             //: ★the refinement's own record: the two polynomial fits and
             //: the current the fixed solve produced against the current
             //: the free solve was asked for.  A 2 pi gauge error is a 2 pi
             //: current error, and this is the row it shows up in.
             refined: refined ? {
               ip: refined.ipSolved, ipTarget: sp.ip,
               resP: refined.fitP.relative, resF: refined.fitF.relative,
               degP: sp.degP, degF: sp.degF,
               iterations: refined.iterations, residual: refined.residual,
               //: ★the zero test: this machine re-solving the equilibrium
               //: it started from, out of that equilibrium's own p'/FF'.
               //: `psi` is pointwise against the flux span, `ipRel` against
               //: the free solve's own current.
               zero: refined.zero,
             } : null,
             refineWhy: refineWhy,
             fit: fit, bpTarget: bpTarget, bpEq: bpEq, bpFix: bpFix,
             lcfs: eq.lcfs, shape: eq.shape });
      //: this block's alternation, written back onto this block's row
      var recNow = rounds[rounds.length - 1];
      recNow.free = freeNow;
      recNow.fit = fit; recNow.beta0 = beta0;
      recNow.bpTarget = bpTarget; recNow.bpEq = bpEq; recNow.bpFix = bpFix;
      recNow.refineWhy = refineWhy;
      if (refined) refinedField = refined.field;
      recNow.refined = refined ? {
        ip: refined.ipSolved, ipTarget: sp.ip,
        resP: refined.fitP.relative, resF: refined.fitF.relative,
        degP: sp.degP, degF: sp.degF,
        iterations: refined.iterations, residual: refined.residual,
        zero: refined.zero } : null;
    }
  }

  //: ★★AND THE MARCH SAYS SO.  Every free-boundary solve it stood on, in
  //: order, with the verdict each one reached — so "this answer used an
  //: equilibrium the solver never found" is a fact in the file and on the
  //: screen rather than something a reader would have to suspect.
  //: ★★THE BEAM'S OWN RECORD, whole.  Every number it produced AND every
  //: number it consumed: without the inputs a reader has a deposition
  //: profile they cannot re-derive, and the gate's oracle is `beam_deposit`
  //: at THESE parameters and no others.
  post({ type: 'evolve', trace: trace, rounds: rounds, crashes: crashes,
         //: ★T-M4: the pedestal record the last step ran under — the ten
         //: EPED inputs AND the full eighteen-output answer, so the gate's
         //: oracle can re-call `eped1nn` at exactly these numbers and the
         //: page can be held to having applied the standard solution
         pedestal: (sp.pedestal && ctx.pedestal) ? ctx.pedestal : null,
         beam: beam ? evBeamReport(beam, sp) : null,
         //: ★★THE WAVE'S OWN RECORD (T-M10), whole and beside the beam's —
         //: never merged with it.  Two sources that deposit in different
         //: places and drive current by different physics are two records,
         //: and the file has to be able to say which one put the power
         //: where.  The inputs travel too: the gate's oracle is
         //: `lh_deposit` at THESE parameters and no others.
         lh: lh ? evLhReport(lh) : null,
         freeSolves: freeLog,
         //: ★T-M16: `settled` is a third verdict, not a failure — a solve
         //: that froze on the mask-jitter floor is a steady-state reading
         freeUnconverged: freeLog.filter(function (r) {
           return !r.converged && !r.settled; }).length,
         //: the LAST refinement's solved box, so the file carries one
         //: checkable instance of the claim rather than only its summary
         refinedField: refinedField,
         rho: geo.rho, psin: geo.psin, vprime: geo.vprime, gm3: geo.gm3,
         gm2: geo.gm2, fpol: geo.fpol, qGeo: geo.q,
         //: ★the vacuum field the march ran on travels with it.  On the
         //: ladder tiers it is the DEVICE's, not anything a control holds,
         //: and without it the current channel cannot be re-run by anyone.
         b0: geo.b0, aMinor: geo.a, rMajor: geo.r0,
         te: st.te, ti: st.ti, ne: st.ne, ni: st.ni,
         //: the rotation, and the torque density that drove it — the second
         //: because a rotation profile without the torque that produced it
         //: cannot be re-run by anyone
         omega: st.omega ? Array.from(st.omega) : null,
         torque: momentum ? Array.from(ctx.torque) : null,
         prandtl: momentum ? sp.prandtl : null,
         //: ★the <R^2> the channel actually ran on — the KERNEL's column
         //: (T-M8), not R_maj^2.  It travels because the capacity cannot be
         //: re-derived from the rest of the file: `<R^2>` is a flux-surface
         //: average, and the ladder's other columns do not determine it.
         r2: momentum ? Array.from(geo.r2) : null,
         //: ★and R_maj^2 beside it, which is what this channel used to run
         //: on.  Two columns a reader can divide is how "O((a/R)^2) at the
         //: EAST edge" stops being a claim about the past.
         rmaj2: momentum ? (function () {
           var a = new Float64Array(geo.rmaj.length);
           for (var i = 0; i < a.length; i++)
             a[i] = geo.rmaj[i] * geo.rmaj[i];
           return Array.from(a);
         })() : null,
         nz: st.nz ? Array.from(st.nz) : null, psi: st.psi,
         //: ★★T-C20：闭包实际用的 Z_eff。成分在演化时它是**结果**（逐面的），
         //: 否则就是滑杆那个数铺平——两种情形都写出来，读者一看就知道是哪一种
         zeffProfile: ctx.lastZeff ? Array.from(ctx.lastZeff) : null,
         zeffSolved: !!(channels.density && zList.length > 1),
         q: st.q || geo.q, chiE: ctx.lastChi ? ctx.lastChi.e : null,
         chiI: ctx.lastChi ? ctx.lastChi.i : null,
         //: ★T-C16 的逐步记录：闸子照着它判「关掉跟不上、开着跟得上」
         stationary: stationary,
         //: ★T-C14〔五〕：稳态电流那一步的全部入参与出参，供另一宿主原样重做
         steady: (stationary && ctx.steadyRecord) || null,
         ipCtlLog: ctx.ipCtl ? ctx.ipCtl.log : null,
         ipCtlRatio0: ctx.ipCtl ? ctx.ipCtl.ratio0 : null,
         jni: ctx.lastBs || null, ohm: ctx.lastOhm || null,
         alpha: ctx.lastAlpha || null, rad: ctx.lastRad || null,
         line: ctx.lastLine || null,
         //: ★what the named impurity IMPLIES, reported rather than applied.
         //: Quasi-neutrality with one impurity at `c_z = n_z/n_e` gives
         //: `n_i/n_e = 1 - Z c_z` and `Z_eff = 1 + c_z Z (Z - 1)`; this
         //: tier still runs on the Z_eff CONTROL and an undiluted bulk ion,
         //: so the two numbers go to the reader to compare rather than
         //: being folded in behind the reader's back.
         //: ★when the impurity is IN the quasi-neutrality these are not
         //: implications any more, they are what the march ran on — the
         //: concentration and the dilution the kernel's own `ion_dilution`
         //: produced.  Reporting the slider's numbers there would print a
         //: composition the solver never saw.
         impurity: sp.quasi && st.nz ? {
           name: sp.impurity, z: sp.impurityZ, applied: true,
           c: st.nz[0] / st.ne[0],
           zEff: sp.zeff,
           dilution: st.ni[0] / st.ne[0],
           dtFraction: sp.dtEffective,
         } : ((sp.impurityId >= 0 && sp.cImp > 0) ? {
           name: sp.impurity, z: sp.impurityZ, c: sp.cImp, applied: false,
           zEff: 1 + sp.cImp * sp.impurityZ * (sp.impurityZ - 1),
           dilution: 1 - sp.impurityZ * sp.cImp,
         } : null),
         geoSource: geo.source, steps: steps, tEnd: tNow,
         //: how often the exchange time had to shorten the step, and what
         //: that time was — a cap that bound silently would be the defect
         //: it was put here to prevent
         dtCapped: ctx.dtCapped | 0, tauExch: ctx.tauExch || null,
         //: ★how many times the turbulent closure was actually evaluated,
         //: and where.  A cadence that never fired would be a neoclassical
         //: run wearing a turbulent label, and nothing else in the file
         //: would say so.
         turbEvals: ctx.turbEvals || 0,
         turbChi: ctx.turbChi ? Array.from(ctx.turbChi) : null,
         chiNeo: ctx.lastChiNeo ? Array.from(ctx.lastChiNeo) : null,
         turbX: ctx.turbSub ? Array.from(ctx.turbSub.xs) : null,
         turbSub: ctx.turbSub ? Array.from(ctx.turbSub.sub) : null,
         //: ★★T-C13 — the match's whole record: the radii it matched on, the
         //: `a/L_T` it solved for, both fluxes against both targets, the
         //: per-iteration residual history and the yardstick that made those
         //: residuals dimensionless.  Everything the page prints and
         //: everything a gate would need to re-derive it, in one block.
         fluxMatch: fluxMatch,
         ms: Date.now() - t0 });
}
