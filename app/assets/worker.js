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
function verticalOf(res, prof2, chan, lcfs) {
  if (!prof2 || !M.vessel || !M.vessel.length || !lcfs || lcfs.length < 6) return null;
  //: ★第三十刀: the criterion is `code/vstab`'s — sunk for Python from this
  //: very function — off the device document, the page's equilibrium
  //: document (its gauge stated) and the channel currents.  What stays here
  //: is the two resistivities the page always supplied where the machine
  //: named none, in the door's own unit (µΩ·m), and the reading back.
  try {
    var etaC = M.coil_resistivity_uohm_m === undefined ? 1.8e-8 : M.coil_resistivity_uohm_m * 1e-6;
    var etaV = M.vessel_resistivity_uohm_m === undefined ? 7.6e-7 : M.vessel_resistivity_uohm_m * 1e-6;
    var br = [], bz = [], i;
    for (i = 0; i + 1 < lcfs.length; i += 2) { br.push(lcfs[i]); bz.push(lcfs[i + 1]); }
    var rg = new Array(grid.nr), zg = new Array(grid.nz);
    for (i = 0; i < grid.nr; i++) rg[i] = grid.r[0] + grid.dr * i;
    for (i = 0; i < grid.nz; i++) zg[i] = grid.z[0] + grid.dz * i;
    var eqDoc = {
      'fylite:psi_convention': 'full_flux_Wb_axis_max',
      vacuum_toroidal_field: { r0: self.FyDevice.tf(M).r0, b0: Math.abs(self.FyDevice.tf(M).b0) },
      time_slice: {
        global_quantities: { ip: res.ip, magnetic_axis: { r: res.axisR, z: res.axisZ },
                             psi_axis: res.psiAxis, psi_boundary: res.psiBnd },
        profiles_1d: { dpressure_dpsi: Array.from(prof2.pprime), f_df_dpsi: Array.from(prof2.ffprime) },
        profiles_2d: { grid: { dim1: rg, dim2: zg }, psi: Array.from(res.psi) },
        boundary: { outline: { r: br, z: bz } } } };
    var rec = fy.complete('code/vstab', {
      settings: { passive: 'vessel', circuit: 'full', ic: 1, coarsen: 2, nu: 3, nv: 3, step: 1e-3,
                  eta_coil: etaC * 1e6, eta_vessel: etaV * 1e6 },
      inputs: { device: deviceDoc(), equilibrium: eqDoc, discharge: { 'fylite:channel_aturns': Array.from(chan) } } });
    var X = function (k) { return rec.facts[k].value; };
    var k = X('k'), kIdeal = X('k_ideal');
    return { gamma: X('gamma'), k: k, kIdeal: kIdeal, ratio: kIdeal ? k / kIdeal : null,
             nFilaments: X('n_filaments') };
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
  if (sum.criteria) sum.criteria.vertical = verticalOf(res, sum.profiles, chan, sum.lcfs);
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

/**
 * The twin's truth off `code/forward` (第三十二刀): one free-boundary solve on
 * the channel currents and the analytic profile, then everything a twin
 * synthesises from that field — the profiles and cell current the family
 * implies, the loop model through the loop rows, the FULL field at every
 * probe on its own angle, q.  `opts` as `freeSolve` took them (`psiExt` for
 * an injected vessel, `psiInit` for a warm start, the two anchors).
 *
 * ★The external flux is always HANDED OVER, never left for the door to
 * assemble: the page's channel cache and the kernel's element fold sum the
 * same Green's functions in a different order, and a twin whose readings
 * moved by an ulp between the two would be a different shot.
 */
function forwardTruth(chan, prof, ip, opts) {
  opts = opts || {};
  var settings = {
    beta0: prof.beta0, emp: prof.emp, enp: prof.enp, r0: prof.r0,
    relax: opts.relax || 0.3, max_iter: opts.maxIter || 600,
    tol: opts.tol || 1e-9, fb_gain: opts.fbGain === undefined ? 8.0 : opts.fbGain,
    n_profile: 201, n_q: 20, n_theta: 121, x_lo: 0.06, x_hi: 1 - P.BOUNDARY_INSET,
  };
  if (opts.zcAnchor !== undefined) settings.zc_anchor = opts.zcAnchor;
  if (opts.rcAnchor !== undefined) settings.rc_anchor = opts.rcAnchor;
  var inputs = { device: deviceDoc(),
                 discharge: { 'fylite:channel_aturns': Float64Array.from(chan), 'fylite:ip': [ip],
                              'fylite:psi_ext': Float64Array.from(opts.psiExt || psiExtOf(chan)) } };
  if (opts.psiInit)
    inputs.equilibrium = { time_slice: { profiles_2d: { psi: Float64Array.from(opts.psiInit) } } };
  var rec = fy.complete('code/forward', { settings: settings, inputs: inputs });
  var X = function (k) { return rec.facts[k].value; };
  var F = function (k) { return rec.fields[k] ? fieldFlat(rec, k) : null; };
  var res = { psi: F('psi'), iterations: X('iterations'), psiAxis: X('psi_axis'),
              psiBnd: X('psi_bnd'), axisR: X('axis_r'), axisZ: X('axis_z'),
              ip: X('ip'), residual: X('residual'), bndKind: X('bnd_kind'),
              xptR: X('xpt_r'), xptZ: X('xpt_z'), fbAmp: X('fb_amp'), zc: X('zc'),
              converged: X('converged') === 1, settled: X('settled') === 1,
              tol: settings.tol, maxIter: settings.max_iter };
  var p = F('pres'), m = p.length;
  var tp = { x: F('psin_1d'), pprime: F('pprime'), ffprime: F('ffprim'), p: p,
             jc: X('jc'), spanPr: X('span_pr'),
             //: the interpolator stays on this side: a convenience for the
             //: page, not part of what the field implies
             pAt: function (xq) {
               var u = xq * (m - 1), k = Math.min(m - 2, Math.max(0, u | 0));
               return p[k] + (u - k) * (p[k + 1] - p[k]);
             } };
  return { res: res, prof: tp, cur: F('current'), loops: F('loop_model'), probes: F('probe_field'),
           q: { x: F('q_x'), q: F('q'), f: F('fpol'), q0: X('q0'), q95: X('q95') } };
}

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
    // 1-3. the truth: one forward free-boundary solve, the current
    //      distribution and profiles it implies, the loop readings through
    //      the SAME rows the fit uses — `code/forward` (第三十二刀)
    var fw = forwardTruth(chan, msg.prof, msg.ip,
                          vExt ? Object.assign({}, msg.solve, { psiExt: vExt })
                               : msg.solve);
    var t = fw.res;
    inp.truthRes = t;
    inp.truth = summarize(t);
    inp.truthProf = fw.prof;
    inp.truthCur = fw.cur;
    inp.truthQ = fw.q;
    meas = fw.loops;
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
    if (M.probes && M.probes.length && fw.probes) inp.probeTwin = fw.probes;
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
      var tp = chordsOf(t, msg.density).point;
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
  //: ★第三十一刀: the solve and its post-processing are `code/reconstruction`'s
  //: ROWS-GIVEN tier — the two inverse entries, `plasmaMask`, `fittedCurrent`,
  //: `loopModel`, `fittedProfiles`, `qProfile` and `li3` used to be called
  //: here.  What stays is the page's own ROW ASSEMBLY (the twin's truth, the
  //: reader's channel table, the probe and chord blocks, the kinetic rows in
  //: the solver's gauge — `reconInputs` / `reconKinetic` / `withFaradayRows`
  //: are untouched) and the chi^2 over the loops.  The rows the page built
  //: are what the door is given: the external flux it assembled, the
  //: plasma-only readings and their weights, the extra rows, the pressure
  //: rows as rows.  The door builds the loop and probe Green's rows on the
  //: same grid (the same kernel rows this page built its `loopsM` from),
  //: solves, and post-processes in this page's spelling.
  var nl = inp.nLoops, np_ = inp.nProbes || 0, nx = inp.nFaraday || 0;
  var chan = inp.chanDrawn || Float64Array.from(msg.chan);
  var disc = {
    'fylite:channel_aturns': Float64Array.from(chan),
    'fylite:ip': [inp.ip],
    'fylite:b_tor': [self.FyDevice.tf(M).b0],
    'fylite:psi_ext': Float64Array.from(inp.psiExt),
    'fylite:loop_plasma': Float64Array.from(inp.meas.slice(0, nl)),
    'fylite:loop_weight': Float64Array.from(inp.wts.slice(0, nl)),
  };
  if (np_) {
    disc['fylite:probe_plasma'] = Float64Array.from(inp.meas.slice(nl, nl + np_));
    disc['fylite:probe_weight'] = Float64Array.from(inp.wts.slice(nl, nl + np_));
  }
  if (nx) {
    var NGm = grid.nr * grid.nz, offX = (nl + np_) * NGm;
    disc['fylite:row_extra'] = Float64Array.from((inp.matrix || loopsM).slice(offX, offX + nx * NGm));
    disc['fylite:meas_extra'] = Float64Array.from(inp.meas.slice(nl + np_, nl + np_ + nx));
    disc['fylite:weight_extra'] = Float64Array.from(inp.wts.slice(nl + np_, nl + np_ + nx));
  }
  if (kin.xp && kin.xp.length) {
    disc['fylite:pressure_x'] = Float64Array.from(kin.xp);
    disc['fylite:pressure'] = Float64Array.from(kin.pmeas);
    disc['fylite:pressure_weight'] = Float64Array.from(kin.wp);
  }
  //: ★`jPre` (T-A9) is the PRESCRIBED per-cell toroidal current [A]: with one
  //: supplied the free coefficients only make up the remainder, and the door
  //: adds it back into the reported current under the iterate's own mask
  if (jPre && jPre.length) disc['fylite:current_source'] = Float64Array.from(jPre);
  var settings = {
    npp: msg.npp, nff: msg.nff,
    relax: msg.solve && msg.solve.relax || 0.3,
    max_iter: msg.solve && msg.solve.maxIter || 800,
    tol: 1e-9, fb_gain: 8.0, warmup: msg.warmup === undefined ? 40 : msg.warmup,
    n_profile: 201, n_q: 20, n_theta: 121, x_lo: 0.06, x_hi: 1 - P.BOUNDARY_INSET,
  };
  //: T-A5 — the coil currents as OBSERVATIONS.  The door builds the block this
  //: page used to (`coilBlock`: sigma_c = rel |I_c|, sigma_loop = rel max|loop
  //: reading|); with chord rows present it stays off, as it always did — the
  //: Faraday integrand is built on B_R and the coils make B_R.
  var cf = msg.coilFit, blk = !!(cf && cf.on && coilG && coilG.psiCh && !nx);
  if (blk) { settings.coil_fit_sigma = cf.sigma; settings.coil_fit_loop_sigma = cf.loopSigma; }
  var rec = fy.complete('code/reconstruction',
                        { settings: settings, inputs: { device: deviceDoc(), discharge: disc } });
  var X = function (k) { return rec.facts[k].value; };
  var F = function (k) { return fieldFlat(rec, k); };
  var res = { psi: F('psi'), coefs: F('coefficients'), iterations: X('iterations'),
              psiAxis: X('psi_axis'), psiBnd: X('psi_bnd'), axisR: X('axis_r'),
              axisZ: X('axis_z'), ip: X('ip'), residual: X('residual'),
              bndKind: X('bnd_kind'), fbAmp: X('fb_amp') };
  if (blk) {
    res.coilPull = X('coil_pull'); res.coilFitted = X('coil_fitted');
    res.coilFit = F('coil_current');
  }
  var fitCur = F('current');
  var model = F('loop_model');
  //: ★chi^2 IS THE LOOPS' — one block, one unit, one panel.  The probe and
  //: chord blocks pull on the same solution and are reported beside it in
  //: their own units (`probeRows`, `faraday`); adding them into this number
  //: would put teslas and line integrals on a Wb/rad axis and make the one
  //: figure of merit the page quotes depend on which extra blocks were on.
  var chi2 = 0, nfit = 0;
  for (var d = 0; d < nl; d++) {
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
  out.ipFitted = X('ip_fitted');
  out.profiles = { x: F('psin_1d'), pprime: F('pprime'), ffprime: F('ffprim'), p: F('pres'),
                   spanPr: (res.psiAxis - res.psiBnd) / (2 * Math.PI) };
  out.q = { x: F('q_x'), q: F('q'), f: F('fpol'), q0: X('q0'), q95: X('q95') };
  out.jphi = currentProfile(grid, res, fitCur);
  //: li(3) is the kernel's integral over the psi map on the FITTED current,
  //: one of the scalars a reconstruction is judged on, which is why it travels
  //: with every member and not only with the run the page happens to draw
  out.li3 = X('li3_fitted');
  //: ★the coil fit reports itself: how far it moved the currents (in units
  //: of the sigma it was given), and what it moved them to.  A member that
  //: bought its residual with a coil excursion no calibration allows is a
  //: THIRD way to be wrong, beside the two `notAPlasma` already tests, and
  //: it cannot be seen from any other number the run reports.
  if (blk) {
    var ampL = 0;
    for (var i = 0; i < nl; i++)
      if (inp.wts[i]) ampL = Math.max(ampL, Math.abs(inp.meas[i]));
    out.coilPull = res.coilPull;
    out.coilFit = res.coilFit;
    out.coilFitted = res.coilFitted;
    out.coilSigma = Float64Array.from(chan, function (c) { return Math.abs(cf.sigma * c); });
    out.coilBefore = chan;
    out.measSigma = Math.max(cf.loopSigma * ampL, 1e-300);
  }
  //: ★第三十三刀: what the fit says every probe should read, by the door's
  //: two routes (the sampled field; the Green's rows on the fitted current
  //: plus the coils' field) — `probePredictions` used to sample and contract
  //: here on three flat exports
  if (rec.fields.probe_model)
    out.probes = { b: F('probe_model'), br: F('probe_br'), bz: F('probe_bz'),
                   viaRows: F('probe_via_rows'), rowsVsFieldRel: X('probe_rows_vs_field') };
  out.raw = res;
  return out;
}

/**
 * Extend a row block with one Faraday row per chord.
 *
 * Returns a shadowed `inp` — the loops and probes it already carried, then
 * the chords — or null when the machine, the data or the density is missing.
 */
function withFaradayRows(inp, fr, pmN, ch) {
  //: ★the readings are an ARGUMENT, not a field of the request: they come
  //: from a file on a real shot and from the truth on a twin, and threading
  //: them through the request block is how the first wiring of this quietly
  //: built no rows at all (`no-rows`, with everything else switched on).
  if (!ch || !ch.n || !fr || !pmN || !pmN.n) return null;
  var n = Math.min(ch.n, pmN.n), NGc = grid.nr * grid.nz;
  var target = new Float64Array(n), any = false, i;
  for (i = 0; i < n; i++) {
    target[i] = pmN.weightPol[i] ? pmN.target[i] : NaN;
    if (isFinite(target[i])) any = true;
  }
  if (!any) return null;
  //: the rows are the PLASMA's; the coils' share of each reading is computed
  //: and subtracted, exactly as the probe block does with its own field
  var coil = ch.coil;
  for (i = 0; i < n; i++) if (isFinite(target[i])) target[i] -= coil[i];
  var rows = ch.rows.length === n * NGc ? ch.rows : ch.rows.slice(0, n * NGc);
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
  out.faradayCoil = coil; out.faradayRows = rows;
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
    dfit = chordsOf(mem.raw, dens, { nel: pmN.nel, nelWeight: pmN.weightNel }).fit;
    if (dfit) dens = Object.assign({}, dens, { ne0: dfit.ne0,
                                               peaking: dfit.peaking,
                                               profile: null });
  }
  if (msg.faraday && msg.faraday.on && pmN && dens && dens.on) {
    var nOuter = Math.max(1, Math.min(5, (msg.faraday.outer | 0) || 2));
    for (var it = 0; it < nOuter; it++) {
      //: the surfaces the rows are built on are the PREVIOUS iterate's —
      //: which samples lie inside the plasma is part of the answer
      var ch2 = chordsOf(mem.raw, dens, { rows: true, psiExt: psiExtOf(inp.chanDrawn || Float64Array.from(msg.chan)) });
      var inp2 = withFaradayRows(inpBase, msg.faraday, pmN, ch2);
      if (!inp2) { farError = 'no-rows'; break; }
      var m2;
      try { m2 = reconMember(msg, inp2, kin); }
      catch (e2) { farError = e2.message; break; }
      mem = m2; fitUsed = inp2; farIters = it + 1;
      //: the density is re-fitted on the new surfaces too, or the second
      //: pass would weight the rows by a density from the first geometry
      if (dfit) {
        var d3 = chordsOf(mem.raw, dens, { nel: pmN.nel, nelWeight: pmN.weightNel }).fit;
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
  out.probes = mem.probes || null;
  //: the predictions are drawn on the SOLVED surfaces of the fit that was
  //: kept, through the density that fit was made with
  //: ★第三十四刀: the chords are `code/chords`' — the readings on the FINAL
  //: surfaces, and with Faraday rows in the fit the same reading by the rows
  //: route (the rows on the fitted current plus the coils' share)
  var chFin = (msgD.density && msgD.density.on)
    ? chordsOf(mem.raw, msgD.density, fitUsed.nFaraday
        ? { rows: true, psiExt: psiExtOf(inp.chanDrawn || Float64Array.from(msg.chan)), current: mem.fitCur }
        : {})
    : null;
  out.point = chFin ? chFin.point : (M.point && M.point.interferometer && M.point.interferometer.length
                                     ? { needsDensity: true } : null);
  if (fitUsed.nFaraday && out.point) {
    var viaRows = chFin.viaRows, worst = chFin.rowsVsFieldRel;
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
    out.truthQ = inp.truthQ;
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
// --- POINT: line-integrated density, and the Faraday rotation --------------
//
// ★第三十四刀: the chords are `code/chords`' — sampled through the box and the
// plasma, the line density and the Faraday integral on the kernel's Simpson
// rule over the full-length line, the coils' share off the external flux, the
// Faraday rows for the fit on the kernel's own quadrature weights, and the
// density fitted back to measured line densities.  What stays here is the
// deck's three reading shapes in one (`normalisePointMeas`) and the reading a
// measured angle stands for.

var POINT_SAMPLES = 401;

/**
 * One call to `code/chords` for a psi map and a density spec.
 *
 * `opts.psiExt` (the external flux, for the coils' share and the rows route),
 * `opts.rows` (the Faraday rows), `opts.current` (the fitted cells: the
 * reading by the rows route), `opts.nel` / `opts.nelWeight` (measured line
 * densities: the density fitted back).  Returns `{point, fit, rows, coil,
 * viaRows, rowsVsFieldRel, n}`; `point` is `null` when the machine has no
 * chords, `{needsDensity: true}` when the spec is off.
 */
function chordsOf(res, spec, opts) {
  opts = opts || {};
  var pt = M.point;
  if (!pt || !pt.interferometer || !pt.interferometer.length)
    return { point: null, fit: null, rows: null, coil: null, viaRows: null, rowsVsFieldRel: NaN, n: 0 };
  if (!spec || !spec.on)
    return { point: { needsDensity: true }, fit: null, rows: null, coil: null, viaRows: null, rowsVsFieldRel: NaN, n: 0 };
  var settings = { n_samples: POINT_SAMPLES, length: 2.2, rows: opts.rows ? 1 : 0 };
  var disc = {};
  if (spec.profile && spec.profile.length) disc['fylite:ne_profile'] = Float64Array.from(spec.profile);
  else { settings.ne0 = spec.ne0; settings.peaking = spec.peaking; }
  if (opts.psiExt) disc['fylite:psi_ext'] = Float64Array.from(opts.psiExt);
  if (opts.current) disc['fylite:current_cells'] = Float64Array.from(opts.current);
  if (opts.nel) {
    disc['fylite:chord_nel'] = Float64Array.from(opts.nel);
    if (opts.nelWeight) disc['fylite:chord_nel_weight'] = Float64Array.from(opts.nelWeight);
  }
  var inputs = { device: deviceDoc(), discharge: disc,
                 equilibrium: { time_slice: { global_quantities: { psi_axis: res.psiAxis, psi_boundary: res.psiBnd },
                                              profiles_2d: { psi: Float64Array.from(res.psi) } } } };
  var rec = fy.complete('code/chords', { settings: settings, inputs: inputs });
  var X = function (k) { return rec.facts[k] ? rec.facts[k].value : undefined; };
  var F = function (k) { return rec.fields[k] ? fieldFlat(rec, k) : null; };
  var chords = pt.interferometer, n = chords.length;
  var spec2 = { ne0: spec.ne0, peaking: spec.peaking, zeff: spec.zeff,
                profile: (spec.profile && spec.profile.length)
                  ? Array.prototype.slice.call(spec.profile) : null };
  var point = { name: chords.map(function (c) { return c.name; }),
                spec: spec2,
                z: chords.map(function (c) { return (c.first_point || {}).z; }),
                nel: F('chord_nel'), nel19: F('chord_nel19'),
                bpolar: F('chord_bpolar'), angleDeg: F('chord_angle_deg'), chordLength: F('chord_length'),
                source: spec.profile && spec.profile.length ? 'imported' : 'parametrised' };
  var fit = null;
  if (rec.facts.fit_ne0)
    fit = { ne0: X('fit_ne0'), peaking: X('fit_peaking'), chi2: X('fit_chi2'), used: X('fit_used'),
            model: F('fit_model'), step: X('fit_step'), atEdge: X('fit_at_edge') === 1 };
  return { point: point, fit: fit, rows: F('faraday_rows'), coil: F('chord_coil'),
           viaRows: F('faraday_via_rows'), rowsVsFieldRel: X('faraday_rows_vs_field'), n: n };
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


// --- the turbulence closure (TGLF), loaded on demand ------------------------

//: the SECOND module, and the reason the kernel was split in two: the
//: turbulence closure of the modelling page's 1.5-D stage is its only
//: consumer, and every other page would otherwise have paid 323 KB for it at
//: startup.  ★It is fetched on FIRST USE (`transportTurb`), so a reader who
//: never switches the closure to 湍流 never downloads it.
var tglf = null;

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
 * The model page's turbulent-transport panel, on two doors.
 *
 * ★第二十五刀 (2026-09-05): what this function wrote out — Chang-Hinton chi on
 * the bar's surfaces (`neoChi` on blocks the page built), TGLF on the
 * sampled radii (`turbulentChi`, the deck and the flat `tglf*` exports),
 * the relaxed total, one steady `transportStep` — is `code/turbulence`
 * (the extension binary) and `code/transport` closure `turbulent` (the
 * core) now.  What stays here is the CADENCE between the two binaries: the
 * extension answers chi_turb on the state as it stands, the core folds it
 * into the closure and takes the step, and the loop runs until the axis
 * settles or the outer count is spent.  The per-pass readings the page
 * shows come off the core's record.
 */
function transportTurb(msg) {
  var t0 = Date.now(), bar = msg.bar;
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  var start = function () {
    try { return loop(); }
    catch (e) { return post({ type: 'error', where: 'transport_turb', message: String(e && e.message || e) }); }
  };
  var loop = function () {
    var x = new Float64Array(bar.n);
    for (var i = 0; i < bar.n; i++) x[i] = bar.amin * i / (bar.n - 1);
    var y = null, chiPrev = null, settled = false, passes = 0, rec = null, tr = null;
    for (var it = 0; it < bar.outer; it++) {
      var tin = { 'fylite:rho': Array.from(x) };
      if (y) tin['fylite:y'] = Array.from(y);
      tr = tglf.complete('code/turbulence', {
        settings: { amin: bar.amin, rmaj: bar.rmaj, q95: bar.q95, kappa: bar.kappa, delta: bar.delta,
                    nepeak: bar.nepeak, ne0: bar.ne0, bunit: bar.bunit, edge: bar.edge,
                    n_rad: bar.nrad, n_ky: bar.nky, sat_rule: 1, width: 1.65 },
        inputs: { transport: tin } });
      var cin = { 'fylite:rho': Array.from(x), 'fylite:chi_turb': Array.from(fieldFlat(tr, 'chi_turb')) };
      if (y) cin['fylite:y_init'] = Array.from(y);
      if (chiPrev) cin['fylite:chi_prev'] = Array.from(chiPrev);
      rec = fy.complete('code/transport', {
        settings: { closure: 'turbulent', chi0: bar.chi0, p1: 0.25, p2: 1.75, power: bar.power, width: bar.width,
                    edge: bar.edge, pinch: bar.pinch, dpc: bar.dpc, amin: bar.amin, rmaj: bar.rmaj,
                    kappa: bar.kappa, delta: bar.delta, q95: bar.q95, bunit: bar.bunit, ne0: bar.ne0,
                    nepeak: bar.nepeak, turb_relax: bar.relax, steps: 1 },
        inputs: { transport: cin } });
      var X = function (k) { return rec.facts[k].value; };
      y = fieldFlat(rec, 'y');
      chiPrev = flat(rec.fields.core_transport.model['0'].profiles_1d.electrons.energy.d);
      passes += 1;
      post({ type: 'turb_pass', it: passes, t0: y[0], move: X('move'),
             chiMin: Math.min.apply(null, Array.from(chiPrev)),
             chiMax: Math.max.apply(null, Array.from(chiPrev)) });
      if (X('move') < bar.tol) { settled = true; break; }
    }
    var lad = rec.fields.equilibrium.time_slice.profiles_1d;
    var X2 = function (k) { return rec.facts[k].value; };
    post({ type: 'transport_turb', y: Array.from(y),
           chi: Array.from(chiPrev), chiNeo: Array.from(fieldFlat(rec, 'chi_neo')),
           chiTurb: Array.from(fieldFlat(rec, 'chi_turb')),
           subX: Array.from(fieldFlat(tr, 'xs')), subChi: Array.from(fieldFlat(tr, 'sub')),
           vprime: Array.from(flat(lad.dvolume_drho_tor)), gradR2: Array.from(flat(lad.gm3)),
           chiGb: Array.from(fieldFlat(rec, 'chi_gb')), source: Array.from(fieldFlat(rec, 'source')),
           outer: passes, settled: settled,
           iterations: X2('inner_iterations'), converged: X2('converged') !== 0,
           residual: X2('residual'), ms: Date.now() - t0,
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
        sum.criteria.vertical = verticalOf(res, sum.profiles, chan0, sum.lcfs);
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
 * The equilibrium document an executor reads off the page's field: the psi
 * map in the page's own gauge — STATED (`fylite:psi_convention`, 第二十七刀:
 * the kernel's readers honour it) — the axis, the limiter, and the one set of
 * 1-D rows the caller hands over.  One spelling for the beam and the wave.
 */
function evFieldDoc(field, geo, prof1d) {
  var i, rg = new Array(field.nr), zg = new Array(field.nz);
  for (i = 0; i < field.nr; i++) rg[i] = field.r0 + field.dr * i;
  for (i = 0; i < field.nz; i++) zg[i] = field.z0 + field.dz * i;
  prof1d['fylite:psi_norm'] = Array.from(geo.psin);
  return {
    'fylite:psi_convention': 'full_flux_Wb_axis_max',
    vacuum_toroidal_field: { r0: Math.abs(geo.r0) || 1, b0: Math.abs(geo.b0) || 1 },
    time_slice: {
      global_quantities: { magnetic_axis: { r: field.axisR, z: field.axisZ },
                           psi_axis: field.psiAxis, psi_boundary: field.psiBnd },
      profiles_1d: prof1d,
      profiles_2d: { grid: { dim1: rg, dim2: zg }, psi: Array.from(field.psi) } },
    'fylite:limiter': { r: Array.from(field.limR), z: Array.from(field.limZ) } };
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
function evBeamPlan(field, geo, st, sp) {
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
  var np0 = geo.psin.length, qAbs = new Array(np0);
  for (i = 0; i < np0; i++) qAbs[i] = Math.abs(geo.q ? geo.q[i] : 1);
  var eqDoc = evFieldDoc(field, geo, { q: qAbs });
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
  //: the input echo the report carries — the profile held to psi_N = 1 as the
  //: re-run oracle reads it (a clamped interpolation, so the same numbers)
  var hold = geo.psin[np0 - 1] < 1 - 1e-9, nprof = hold ? np0 + 1 : np0;
  var psinProf = new Float64Array(nprof), neP = new Float64Array(nprof),
      teP = new Float64Array(nprof);
  for (i = 0; i < np0; i++) {
    psinProf[i] = geo.psin[i]; neP[i] = Math.max(st.ne[i], 1e16); teP[i] = Math.max(st.te[i], 1);
  }
  if (hold) { psinProf[np0] = 1; neP[np0] = neP[np0 - 1]; teP[np0] = teP[np0 - 1]; }
  return { settings: settings, eqDoc: eqDoc, cp: cp, unit: unit,
           echo: { psin2d: psin2d, psinProf: psinProf, ne: neP, te: teP } };
}

/**
 * The beam's record read off `code/beam`'s answer — the same reading for the
 * standalone call (`evBeamDeposit`) and for the record the march carries
 * under `fields.beam` since 第十七刀 (`F` / `X` / `nc` are the accessors, so
 * one reading serves both shapes).
 */
function evBeamRead(fields, F, X, nc, plan, field, geo, sp) {
  var sl, c;
  var nsh = plan.settings.n_shells;
  var src = fields.core_sources.source['0'].profiles_1d;
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  var cAbs = F('component_absorbed'), cRet = F('component_retained'),
      cPitch = F('component_pitch'), cMask = F('component_orbit_mask'),
      cE = F('component_energy'), cP = F('component_power'),
      cShine = F('component_shinethrough'), cOrbit = F('component_orbit_loss'),
      cAbsF = F('component_absorbed_fraction'), cCur = F('component_current');
  var records = [];
  for (c = 0; c < nc; c++) {
    sl = function (a) { return Array.from(a.subarray(c * nsh, (c + 1) * nsh)); };
    records.push({ energy: cE[c], power: cP[c], absorbed: sl(cAbs), retained: sl(cRet),
                   orbitMask: sp.beamOrbit ? sl(cMask) : null, pitch: sl(cPitch),
                   shinethrough: cShine[c], orbitLoss: cOrbit[c],
                   absorbedFraction: cAbsF[c], current: cCur[c] });
  }
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
              nr: field.nr, nz: field.nz, psin2d: plan.echo.psin2d,
              psinProf: plan.echo.psinProf, ne: plan.echo.ne, te: plan.echo.te,
              rStart: field.r0 + field.dr * (field.nr - 1),
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
function evLhPlan(field, geo, st, sp) {
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
  var np0 = geo.psin.length, fAbs = new Array(np0), neP = new Array(np0), teP = new Array(np0);
  for (i = 0; i < np0; i++) {
    fAbs[i] = Math.abs(geo.fpol[i]);
    neP[i] = Math.max(st.ne[i], 1e16);
    teP[i] = Math.max(st.te[i], 1);
  }
  var eqDoc = evFieldDoc(field, geo, { f: fAbs });
  var cp = { profiles_1d: { grid: { 'fylite:psi_norm': Array.from(geo.psin) },
                            electrons: { density: neP, temperature: teP } } };
  var settings = { eta_cd: sp.lhEtaCd, xi: sp.lhXi, upshift_min: sp.lhUpLo, upshift_max: sp.lhUpHi,
                   n_shells: nsh, width_floor: sp.lhWidthFloor, cd_model: 'fisch', n_theta: 181 };
  return { settings: settings, eqDoc: eqDoc, cp: cp, antennas: antennas, raw: raw, nsh: nsh };
}

/** The wave's record read off `code/wave`'s answer (standalone, or the march's `fields.lh`). */
function evLhRead(fields, F, X, nl, plan, geo, sp) {
  var k;
  var antennas = plan.antennas, raw = plan.raw, nsh = plan.nsh;
  var src = fields.core_sources.source['0'].profiles_1d;
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
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
    //: ★第二十九刀: the free solve AND its ladder are `code/refit`'s (the
    //: evolve page's device tier since 第十九刀); the page reads them back
    var rf;
    try { rf = evRefit(assign({}, sp, { emp: 1.0, enp: 1.0, relax: 0.5 }), Float64Array.from(msg.chan), { fit: 0, beta0: 0.55 }); }
    catch (e) { return post({ type: 'error', where: 'interp', message: String(e && e.message || e) }); }
    var lad = rf.geo;
    free = freeReport(rf.eq);
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
  return { 'fylite:psi_convention': 'full_flux_Wb_axis_max',
           vacuum_toroidal_field: { r0: g.rmaj, b0: g.b0 },
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
    //: `closure` is numeric: 0 is IN scope.  The declaration says WHICH
    //: controls decide the scope; what counts as「on」for a numeric one is
    //: this host reading its own control, and it is written out rather than
    //: left to truthiness.  (`couple` sank whole — 第十九·二十刀 — and is a
    //: `sunk` row now.)
    if (r.key === 'closure') {
      //: ★第十六刀: the neoclassical closure (2) is the entry's; 第十八刀: the
      //: turbulent one (3) too, on the extension's chi between blocks;
      //: 第二十一刀: the flux-match tier (4) as stages — every closure is in
      continue;
    } else if (r.units === 'required') {
      if (!v) miss.push(r.gloss);
    } else if (r.key === 'resume') {
      //: ★第二十二刀: the browser's resume is a whole state the page hands the
      //: worker — bound as the entry's `state`, the clock continued by
      //: `t_start`; a fresh march from there, which is what the loop did too
      continue;
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
 * The equilibrium half of a coupled block, through the KERNEL's `code/refit`.
 *
 * ★★★第十九刀 (2026-09-05).  Between two blocks of the march the loop below
 * used to run a dozen flat exports in a row: `evFitShape` (the transport
 * pressure's shape fitted to the analytic current family), the two beta_p
 * and the under-relaxed move of `beta0`, `freeSolve` (`fy.gsFreeSolve` on
 * the coil flux), `summarize` (the analytic truth, the q profile, the
 * boundary), `evLadderFromSolve` (`fy.equilibriumLadder`), `evRemap` of the
 * state onto the new ladder by psi_N, `evPsiOf` for the flux in the march's
 * gauge, the old V' remapped for the first step's moving volume.  All of it
 * is `case.rs::refit_case` now — one plan in, one record out — and the SAME
 * door with `fit: 0` is the device tier's start (the solve and the ladder,
 * nothing fitted).  What this function keeps is the plan and the reading.
 *
 * `o.fit`: 1 for the alternation (state + ladder + previous equilibrium's
 * p(psi_N) bound), 0 for the start.  Returns the pieces the march needs in
 * the shapes it already used: `eq` (what `summarize` returned, minus the
 * display-only parts), `geo` (what `evLadderMetric` returned), `field`, and
 * with `fit` the remapped `st`, `vprimeOld`, `fit`, `bpTarget`, `bpEq`,
 * `beta0` and the solve's `free` report.
 */
/** The zero test's four numbers, read back off the door's `refine:` note. */
function evRefineZeroNumbers(note) {
  var m = /psi ([-+0-9.e]+) \(tol ([-+0-9.e]+)\), I_p ([-+0-9.e]+)% \(tol ([0-9]+)%\)/.exec(note || '');
  return m ? { psi: m[1], psiTol: m[2], ip: m[3], ipTol: m[4] } : { psi: '?', psiTol: '?', ip: '?', ipTol: '1' };
}

function evRefit(sp, chan, o) {
  var arr = function (v) { return v ? Array.from(v) : null; };
  var t = self.FyDevice.tf(M), fo = evFreeOpts(sp);
  var settings = {
    ip: o.ip === undefined ? sp.ip : o.ip, beta0: o.beta0,
    emp: o.emp === undefined ? sp.emp : o.emp, enp: o.enp === undefined ? sp.enp : o.enp, r0: sp.r0Src,
    //: 第二十一刀: the stationary outer loop under-relaxes the family it hands the solve
    fit_relax: o.fitRelax === undefined ? 1 : o.fitRelax,
    b0: t.b0, r0_tf: t.r0, relax: sp.relax, n: sp.n, edge_psin: sp.edgePsin, n_theta: 121,
    gs_relax: fo.relax, gs_tol: fo.tol, fb_gain: 8.0, max_iter: fo.maxIter, fit: o.fit ? 1 : 0,
    //: 第二十刀: the fixed-boundary refinement is a stage of the same door
    couple_fixed: o.fit && sp.coupleFixed ? 1 : 0, deg_p: sp.degP, deg_f: sp.degF };
  var inputs = { device: deviceDoc(), discharge: { 'fylite:channel_aturns': Array.from(chan) } };
  if (o.fit) {
    var geo = o.geo, st = o.st;
    settings.a = geo.a;
    inputs.equilibrium = { time_slice: { profiles_1d: {
      rho_tor: arr(geo.rho), dvolume_drho_tor: arr(geo.vprime), 'fylite:psi_norm': arr(geo.psin) } } };
    var cp = { electrons: { temperature: arr(st.te), density: arr(st.ne) },
               t_i_average: arr(st.ti), 'fylite:ion_density': arr(st.ni) };
    if (st.omega) cp.rotation_frequency_tor_sonic = arr(st.omega);
    if (st.nz) cp['fylite:impurity_density'] = arr(st.nz);
    inputs.core_profiles = { profiles_1d: cp };
    //: the fast branches' trace third rides along (T-M12), so the fit and the
    //: beta_p target see the same total pressure the march did
    if (o.pFastThird) inputs.evolve = { 'fylite:p_fast_third': arr(o.pFastThird) };
    //: the previous equilibrium's own p(psi_N) — the FREE solve's, whatever the
    //: march ran on (`evEqPressure(eqFree, geo)`)
    if (o.eqPrev && o.eqPrev.profiles && o.eqPrev.profiles.p)
      inputs.refit = { 'fylite:eq_x': arr(o.eqPrev.profiles.x), 'fylite:eq_p': arr(o.eqPrev.profiles.p) };
  }
  Object.keys(settings).forEach(function (k) {
    if (settings[k] === undefined || settings[k] === null) delete settings[k];
  });
  var rec = fy.complete('code/refit', { settings: settings, inputs: inputs });
  var X = function (k) { return rec.facts[k].value; };
  var F = function (k) { return fieldFlat(rec, k); };
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  var lad = rec.fields.equilibrium.time_slice.profiles_1d;
  var eq = {
    psi: F('psi'), psiAxis: X('psi_axis'), psiBnd: X('psi_bnd'), axisR: X('axis_r'), axisZ: X('axis_z'),
    ip: X('ip'), residual: X('residual'), iterations: X('iterations'),
    converged: X('converged') === 1, settled: X('settled') === 1,
    maskDelta: X('mask_delta') < 0 ? null : X('mask_delta'), tol: fo.tol, maxIter: fo.maxIter,
    bndKind: X('bnd_kind'), xptR: X('xpt_r'), xptZ: X('xpt_z'), fbAmp: X('fb_amp'),
    profiles: { x: F('profile_x'), pprime: F('pprime'), ffprime: F('ffprime'), p: F('pres'), jc: X('jc') },
    q: { x: F('q_x'), q: F('q'), f: F('f'), q0: X('q0'), q95: X('q95') },
    lcfs: F('boundary'),
    shape: { r0: X('r0'), a: X('a'), kappa: X('kappa'), deltaU: X('delta_upper'), deltaL: X('delta_lower'),
             z0: X('z0'), delta: 0.5 * (X('delta_upper') + X('delta_lower')) },
  };
  var geoNew = {
    rho: flat(lad.rho_tor), vprime: flat(lad.dvolume_drho_tor), gm3: flat(lad.gm3), gm7: flat(lad.gm7),
    gm2: flat(lad.gm2), r2: flat(lad['fylite:r2_average']), fpol: flat(lad.f), q: flat(lad.q),
    psin: flat(lad['fylite:psi_norm']), shear: flat(lad.magnetic_shear), kappa: flat(lad.elongation),
    delta: flat(lad.triangularity_upper), rmaj: flat(lad['fylite:r_major']), rmin: flat(lad['fylite:r_minor']),
    shift: flat(lad['fylite:shift']),
    a: X('a'), r0: X('r0'), b0: X('b0'), source: 'device',
    psiAxis: eq.psiAxis, psiBnd: eq.psiBnd, dpsi: (eq.psiBnd - eq.psiAxis) / (2 * Math.PI),
  };
  var field = { psi: eq.psi, psiAxis: eq.psiAxis, psiBnd: eq.psiBnd,
                axisR: eq.axisR, axisZ: eq.axisZ,
                r0: grid.r[0], z0: grid.z[0], dr: grid.dr, dz: grid.dz,
                nr: grid.nr, nz: grid.nz,
                limR: M.limiter.r, limZ: M.limiter.z };
  //: the FREE solve's own p(psi_N) — what the next alternation's beta_p reads,
  //: whichever equilibrium the march stands on
  var eqFree = { profiles: { x: F('free_profile_x'), p: F('free_pres') } };
  var out = { eq: eq, eqFree: eqFree, geo: geoNew, field: field,
              free: { converged: eq.converged, settled: eq.settled, residual: eq.residual,
                      iterations: eq.iterations, maxIter: eq.maxIter, tol: eq.tol },
              beta0: X('beta0'), emp: X('emp'), enp: X('enp'), refined: null, refineWhy: null, bpFix: NaN };
  if (o.fit && sp.coupleFixed) {
    //: ★the refinement's own record, and its refusal by NAME: the door reports
    //: a failed refinement (`fixed_why`) and the family's answer stands, as the
    //: loop did; the page's wording is rebuilt here from the door's facts
    if (X('fixed_ok')) {
      out.refined = {
        ip: X('fixed_ip'), ipTarget: X('fixed_ip_target'),
        resP: X('res_p'), resF: X('res_f'), degP: X('deg_p'), degF: X('deg_f'),
        iterations: X('fixed_iterations'), residual: X('fixed_residual'),
        zero: { psi: X('zero_psi'), ip: X('zero_ip'), ipRef: X('fixed_ip_target'), ipRel: X('zero_ip_rel'),
                iterations: X('zero_iterations'), residual: X('zero_residual'),
                freeIterations: eq.iterations, freeResidual: eq.residual,
                axisR: X('zero_axis_r'), axisZ: X('zero_axis_z') },
        field: { r: F('box_r'), z: F('box_z'), psi: F('box_psi'),
                 psiAxis: X('fixed_psi_axis'), psiBnd: eq.psiBnd,
                 axisR: X('fixed_axis_r'), axisZ: X('fixed_axis_z'),
                 limR: F('box_limiter_r'), limZ: F('box_limiter_z'),
                 dpCoef: Array.from(F('dp_coef')), dgCoef: Array.from(F('dg_coef')),
                 ip: X('fixed_ip'), ipTarget: X('fixed_ip_target'), ffShift: X('fixed_ff_shift'), ipRaw: X('fixed_ip_raw') },
      };
      out.bpFix = X('bp_fix');
    } else {
      var why = X('fixed_why'), note = (rec.notes || []).filter(function (t) { return t.indexOf('refine: ') === 0; })[0] || '';
      var fr = { it: eq.iterations, fresid: eq.residual.toExponential(1) };
      out.refineWhy = why === 1 ? FyI18n.t('e.err.refine_box')
        : why === 2 ? FyI18n.t('e.err.refine_zerofail', assign(fr, { why: note.replace(/^refine: /, '') }))
        : why === 3 ? FyI18n.t('e.err.refine_zero', assign(fr, evRefineZeroNumbers(note)))
        : why === 4 ? FyI18n.t('e.err.refine_grew')
        : why === 5 ? FyI18n.t('e.err.refine_axis')
        : why === 6 ? FyI18n.t('e.err.refine_open', { diag: note.replace(/^refine: [^:]*: /, '') })
        : (note.replace(/^refine: /, '') || FyI18n.t('e.err.refine'));
    }
  }
  if (o.fit) {
    var cpr = rec.fields.core_profiles.profiles_1d;
    out.st = { te: flat(cpr.electrons.temperature), ti: flat(cpr.t_i_average), ne: flat(cpr.electrons.density),
               ni: flat(cpr['fylite:ion_density']),
               omega: cpr.rotation_frequency_tor_sonic ? flat(cpr.rotation_frequency_tor_sonic) : null,
               nz: cpr['fylite:impurity_density'] ? flat(cpr['fylite:impurity_density']) : null,
               psi: flat(cpr.grid.psi), q: null };
    out.vprimeOld = F('vprime_old');
    out.fit = X('fit_found') ? { emp: X('fit_emp'), enp: X('fit_enp'), rms: X('fit_rms') } : null;
    out.bpTarget = X('bp_target');
    out.bpEq = X('bp_eq');
  }
  return out;
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
/**
 * The entry's PLAN for this configuration: the controls spelled in SI, the
 * ladder rows, the equilibrium document (the psi map with an executor), the
 * executors' own plans.  Shared by the march (`evEntryMarch`) and the
 * flux-match tier (`evFluxMatchEntry`, 第二十一刀) — one spelling.
 */
function evEntryPlan(ctx, st, geo, sp, field) {
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
    //: 第二十二刀: the clock continues on a resumed march (`msg.tStart`)
    resume: 0, t_start: 0, dt_start: 0, edge_te_in: 0, edge_ti_in: 0, capped_in: 0, saw_elapsed_in: 0,
    //: ★第十五刀 — the density channel (the impurity in the quasi-neutrality
    //: with it) and the momentum channel, the sliders in SI (fuel 1e20/s ->
    //: 1/s; the torque is N.m on both sides)
    'ch-density': ctx.channels.density ? 1 : 0, d_over_chi: sp.dOverChi, pinch: sp.pinch,
    fuel_rate: (sp.fuel || 0) * 1e20, fuel_centre: sp.fuelCentre, fuel_width: sp.fuelWidth,
    quasi: sp.quasi ? 1 : 0, d_over_chi_z: sp.dOverChiZ, pinch_z: sp.pinchZ,
    fuel_z_rate: (sp.fuelZ || 0) * 1e20,
    'ch-momentum': ctx.momentum ? 1 : 0, prandtl: sp.prandtl, torque: sp.torque || 0,
    dt_fraction_in: 0,
    //: 第十六刀 — the waveform, the I_p loop, the closure
    wave: sp.wave ? 1 : 0, wave_ramp: sp.waveRamp, wave_flat: sp.waveFlat, wave_end: sp.waveEnd,
    wave_start: sp.waveStart, wave_end2: sp.waveEnd2,
    wave_power: sp.wavePower ? 1 : 0, wave_vloop: sp.waveVloop ? 1 : 0, wave_fuel: sp.waveFuel ? 1 : 0,
    wave_ip: sp.waveIp ? 1 : 0,
    ipctl: sp.ipCtl ? 1 : 0, ip_kp: sp.ipKp, ip_ki: sp.ipKi,
    ipctl_ratio0_in: 1, ipctl_integral_in: 0, ipctl_calibrated_in: 0,
    //: 第十八刀: the turbulent tier (3) marches on the chi the extension's
    //: `code/turbulence` evaluates between blocks
    closure: (sp.closure | 0) === 3 ? 3 : ((sp.closure | 0) === 2 ? 2 : 0),
    //: 第十七刀: the ladder's edge as the bar states it (the remap's knot)
    edge_psin: sp.edgePsin
  };
  //: ★第十七刀 — the executors go INTO the plan: the beam's and the wave's own
  //: settings (each with its shell count under its own name, since the two sit
  //: in one settings map here), the units / antennas as documents, and the psi
  //: map on the equilibrium — the entry evaluates them once on the state it
  //: starts from, remaps them onto this ladder and hands the arrays back for
  //: the next step to bind (`evolve/fylite:beam_*` · `lh_*`).  The record's
  //: `fields.beam` / `fields.lh` is `code/beam`'s / `code/wave`'s whole answer,
  //: read by the same `evBeamRead` / `evLhRead` the standalone calls use.
  var beamPlan = sp.beam ? evBeamPlan(field, geo, st, sp) : null;
  var lhPlan = sp.lh ? evLhPlan(field, geo, st, sp) : null;
  if (beamPlan) {
    Object.keys(beamPlan.settings).forEach(function (k) {
      settings[k === 'n_shells' ? 'beam_shells' : k] = beamPlan.settings[k];
    });
    settings.beam = 1;
  }
  if (lhPlan) {
    Object.keys(lhPlan.settings).forEach(function (k) {
      settings[k === 'n_shells' ? 'lh_shells' : k] = lhPlan.settings[k];
    });
    settings.lh = 1;
  }
  Object.keys(settings).forEach(function (k) {
    if (settings[k] === undefined || settings[k] === null) delete settings[k];
  });
  var ladder = { rho_tor: arr(geo.rho), dvolume_drho_tor: arr(geo.vprime), gm3: arr(geo.gm3),
                 gm2: arr(geo.gm2), f: arr(geo.fpol), q: arr(geo.q),
                 'fylite:r_minor': arr(geo.rmin), 'fylite:r_major': arr(geo.rmaj),
                 'fylite:r2_average': arr(geo.r2),
                 magnetic_shear: arr(geo.shear), elongation: arr(geo.kappa), triangularity_upper: arr(geo.delta),
                 'fylite:shift': arr(geo.shift), 'fylite:psi_norm': arr(geo.psin),
                 psi: arr(st.psi) };
  Object.keys(ladder).forEach(function (k) { if (!ladder[k]) delete ladder[k]; });
  var eqBase = (beamPlan || lhPlan) ? (beamPlan || lhPlan).eqDoc : null;
  var equilibrium = eqBase
    ? { vacuum_toroidal_field: eqBase.vacuum_toroidal_field,
        time_slice: { global_quantities: eqBase.time_slice.global_quantities,
                      profiles_1d: ladder, profiles_2d: eqBase.time_slice.profiles_2d },
        'fylite:limiter': eqBase['fylite:limiter'] }
    : { time_slice: { profiles_1d: ladder } };
  return { settings: settings, ladder: ladder, equilibrium: equilibrium, beamPlan: beamPlan, lhPlan: lhPlan };
}

function evEntryMarch(ctx, st, geo, sp, trace, crashes, tStart, field, blk) {
  //: ★第十九刀: one BLOCK of the march when `blk` is given — the steps it
  //: takes counted from `blk.steps0`, the continuation (`blk.prev`) the
  //: previous block's last record with its arrays on this ladder, and the
  //: first step told that the lag is broken and the volume moved
  var n = geo.rho.length, prev = blk && blk.prev || null, steps = blk ? blk.steps0 : 0;
  var stop = blk ? blk.steps0 + blk.take : sp.nSteps, first = true, tNow = tStart || 0;
  var wPrev = blk && blk.wPrev !== undefined ? blk.wPrev : null;
  //: ★★the march is `case.rs::evolve` (FYL-DESIGN-16 K-3, 2026-09-05), one step
  //: per call so the page can report as it goes: the plan carries the ladder
  //: this run is on (bound rows — the traced tiers' own rmin/rmaj beside the
  //: metric), the state as it stands (`state`, then `resume` with the lagged
  //: arrays the entry hands back), and the bar's controls spelled in SI.  It
  //: used to be the flat export `fy.scenario('evolve_heat', …)` with the same
  //: blocks packed here; `app/tests/validate-worker-evolve.mjs` holds the door
  //: to that path's answer step by step.
  var arr = function (v) { return v ? Array.from(v) : null; };
  var planBase = evEntryPlan(ctx, st, geo, sp, field);
  var settings = planBase.settings, ladder = planBase.ladder, equilibrium = planBase.equilibrium;
  settings.t_start = tNow;
  var beamPlan = planBase.beamPlan, lhPlan = planBase.lhPlan;
  var beam = null, lh = null;
  //: the equilibrium document: the ladder rows, and — with an executor — the
  //: psi map, the axis and the limiter the shell tables are traced on
  //: ★★第十八刀 — the turbulent closure, BETWEEN blocks.  The TGLF chain lives in
  //: the extension module, which the core wasm cannot call; so the extension's
  //: own door (`code/turbulence`, the page's `turbulentChi` sunk: the surface
  //: blocks, the sampled radii, the deck, units / ky grid / flux, chi in
  //: gyro-Bohm units interpolated onto the ladder, relaxed against the previous
  //: answer) is knocked on the state a block starts from, and the march takes
  //: its answer as `chi_turb` for `turbEvery` steps.  The page's loop evaluated
  //: it once BEFORE the march (`evClosure` for the exchange ceiling) and again
  //: on every due step, the first due step being step 1 on the same state — a
  //: relaxation that moves nothing; kept, so `turbEvals` counts as the loop's.
  var turb = (sp.closure | 0) === 3;
  var turbEvery = Math.max(1, sp.turbEvery | 0);
  var turbPlan = function (stNow) {
    var prof = { grid: { rho_tor: arr(geo.rho) },
                 electrons: { temperature: arr(stNow.te), density: arr(stNow.ne) },
                 t_i_average: arr(stNow.ti), 'fylite:ion_density': arr(stNow.ni),
                 rotation_frequency_tor_sonic: ctx.momentum && stNow.omega ? arr(stNow.omega) : undefined };
    Object.keys(prof).forEach(function (k) { if (prof[k] === undefined || prof[k] === null) delete prof[k]; });
    var plan = { settings: { a: geo.a, b0: geo.b0, n_rad: sp.turbNrad, n_ky: sp.turbNky, sat_rule: 1,
                             width: 1.65, relax: sp.turbRelax },
                 inputs: { equilibrium: { time_slice: { profiles_1d: ladder } },
                           core_profiles: { profiles_1d: prof } } };
    if (ctx.turbChi) plan.inputs.evolve = { 'fylite:chi_turb': Array.from(ctx.turbChi) };
    return plan;
  };
  var turbEval = function (stNow) {
    var rec = tglf.complete('code/turbulence', turbPlan(stNow));
    ctx.turbChi = fieldFlat(rec, 'chi_turb');
    ctx.turbSub = { xs: fieldFlat(rec, 'xs'), sub: fieldFlat(rec, 'sub') };
    ctx.turbEvals = (ctx.turbEvals | 0) + 1;
  };
  if (turb) turbEval(st);
  var zeros = new Float64Array(n);
  var state = { te: st.te, ti: st.ti, ne: st.ne, psi: st.psi,
                psiPrev: zeros, sigmaPrev: zeros, exchPrev: zeros,
                //: the page's own start: the dilution it built, the rotation at rest
                ni: st.ni, nz: st.nz || null, omega: st.omega || null };
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  while (steps < stop) {
    if (prev) {
      settings.resume = 1;
      settings.t_start = prev.t_end;
      settings.dt_start = prev.dt_next;
      settings.edge_te_in = prev.edge_te_out;
      settings.edge_ti_in = prev.edge_ti_out;
      settings.capped_in = prev.dt_capped;
      settings.saw_elapsed_in = prev.saw_elapsed_out;
      settings.dt_fraction_in = prev.dt_fraction_used;
      settings.ipctl_ratio0_in = prev.ipctl_ratio0;
      settings.ipctl_integral_in = prev.ipctl_integral;
      settings.ipctl_calibrated_in = prev.ipctl_calibrated;
      state = { te: prev.te, ti: prev.ti, ne: prev.ne_out, psi: prev.psi,
                psiPrev: prev.psi_prev_out, sigmaPrev: prev.sigma_prev_out, exchPrev: prev.exch_prev_out,
                ni: prev.ni_main, nz: prev.nz, omega: prev.omega };
    }
    var carried = { 'fylite:psi_prev': arr(state.psiPrev), 'fylite:sigma_prev': arr(state.sigmaPrev),
                    'fylite:exch_prev': arr(state.exchPrev) };
    if (prev && sp.beam && prev.beam_e) {
      carried['fylite:beam_e'] = prev.beam_e; carried['fylite:beam_i'] = prev.beam_i;
      carried['fylite:beam_torque'] = prev.beam_torque; carried['fylite:beam_j'] = prev.beam_j;
      carried['fylite:beam_p_par'] = prev.beam_p_par; carried['fylite:beam_p_perp'] = prev.beam_p_perp;
    }
    if (prev && sp.lh && prev.lh_e) { carried['fylite:lh_e'] = prev.lh_e; carried['fylite:lh_j'] = prev.lh_j; }
    //: ★第十九刀 — the first step after an alternation: the lagged flux and
    //: conductivity sit on the previous ladder and are dropped (the loop's
    //: `ctx.psiPrev = null`), and the moving-volume term takes the old V'
    //: remapped onto this ladder (`vprime_old`) for this one step
    settings.lag_reset = first && blk && blk.lagReset ? 1 : 0;
    settings.vprime_moved = first && blk && blk.vprimeOld ? 1 : 0;
    if (settings.vprime_moved) carried['fylite:vprime_old'] = Array.from(blk.vprimeOld);
    first = false;
    if (turb) {
      //: the cadence (the loop's `steps % turbEvery === 0`, on the state the step starts from)
      if (steps % turbEvery === 0) turbEval(state);
      carried['fylite:chi_turb'] = Array.from(ctx.turbChi);
    }
    var plan = { settings: settings, inputs: {
      equilibrium: equilibrium,
      core_profiles: { profiles_1d: { grid: { psi: arr(state.psi), 'fylite:psi_norm': arr(geo.psin) },
                                      electrons: { temperature: arr(state.te), density: arr(state.ne) },
                                      t_i_average: arr(state.ti),
                                      'fylite:ion_density': arr(state.ni),
                                      'fylite:impurity_density': sp.quasi && state.nz ? arr(state.nz) : undefined,
                                      rotation_frequency_tor_sonic: ctx.momentum && state.omega ? arr(state.omega) : undefined } },
      evolve: carried } };
    if (beamPlan) plan.inputs.nbi = { unit: [beamPlan.unit] };
    if (lhPlan) plan.inputs.lh_antennas = { antenna: lhPlan.antennas };
    var cp1 = plan.inputs.core_profiles.profiles_1d;
    Object.keys(cp1).forEach(function (k) { if (cp1[k] === undefined || cp1[k] === null) delete cp1[k]; });
    if (!cp1.grid['fylite:psi_norm']) delete cp1.grid['fylite:psi_norm'];
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
              omega: ctx.momentum && cpr.rotation_frequency_tor_sonic ? flat(cpr.rotation_frequency_tor_sonic) : null,
              //: 第十六刀
              wave_k: F('wave_k'), v_loop_used: F('v_loop_used'), ip_psi: F('ip_psi'), ip_want: F('ip_want'),
              ip_err: F('ip_err'), chi_neo: F('chi_neo'),
              ipctl_ratio0: X('ipctl_ratio0_out'), ipctl_integral: X('ipctl_integral_out'),
              ipctl_calibrated: X('ipctl_calibrated_out'),
              //: 第十七刀
              p_aux: F('p_aux'), p_aux_beam: F('p_aux_beam'), p_aux_lh: F('p_aux_lh'), j_lh: F('j_lh'), ohm: F('ohm'),
              beam_e: sp.beam ? F('beam_e') : null, beam_i: sp.beam ? F('beam_i') : null,
              beam_torque: sp.beam ? F('beam_torque') : null, beam_j: sp.beam ? F('beam_j') : null,
              beam_p_par: sp.beam ? F('beam_p_par') : null, beam_p_perp: sp.beam ? F('beam_p_perp') : null,
              lh_e: sp.lh ? F('lh_e') : null, lh_j: sp.lh ? F('lh_j') : null };
    steps += 1;
    tNow = o.t_end;
    //: the executors' records, off the first step's answer — the same reading
    //: as the standalone calls, on the record the march carries
    var sub = function (node) {
      return { F: function (k) { return fieldFlat({ fields: node }, k); },
               X: function (k) { return fieldFlat({ fields: node }, k)[0]; },
               dim: function (k) { return fieldFlat({ fields: node.dims }, k)[0] | 0; } };
    };
    var outside = function (r, obj) {
      var po = r.F('p_outside_ladder')[0], pe = r.F('ladder_edge_psin')[0];
      obj.pOutsideLadder = isFinite(po) ? po : null;
      obj.ladderEdgePsin = isFinite(pe) ? pe : null;
      obj.cadence = 0;
    };
    if (sp.beam && !beam && rec.fields.beam) {
      var rb = sub(rec.fields.beam);
      beam = evBeamRead(rec.fields.beam, rb.F, rb.X, rb.dim('n_components'), beamPlan, field, geo, sp);
      outside(rb, beam);
    }
    if (sp.lh && !lh && rec.fields.lh) {
      var rl = sub(rec.fields.lh);
      lh = evLhRead(rec.fields.lh, rl.F, rl.X, rl.dim('n_launchers'), lhPlan, geo, sp);
      outside(rl, lh);
    }
    //: what the page's `rebuildSources` left in `ctx` for the readings and the
    //: record: the fast-ion branches, the torque and the on-ladder arrays at
    //: this step's waveform factor
    var kpNow = sp.wavePower ? o.wave_k[0] : 1;
    var scaled = function (a) {
      var out = new Float64Array(a.length);
      for (var q1 = 0; q1 < a.length; q1++) out[q1] = a[q1] * kpNow;
      return out;
    };
    if (beam) {
      ctx.pFastPar = scaled(o.beam_p_par); ctx.pFastPerp = scaled(o.beam_p_perp);
      ctx.torque = scaled(o.beam_torque);
      ctx.torqueBeam = beam.torqueTotal * kpNow;
      beam.onLadder = new Float64Array(n);
      //: the page's order: each channel scaled, then summed
      for (var q2 = 0; q2 < n; q2++) beam.onLadder[q2] = o.beam_e[q2] * kpNow + o.beam_i[q2] * kpNow;
    }
    if (lh) lh.onLadder = scaled(o.lh_e);
    st.te = o.te; st.ti = o.ti; st.ne = o.ne_out; st.ni = o.ni_main;
    if (sp.quasi) st.nz = o.nz;
    if (ctx.momentum) { st.omega = o.omega; ctx.omega = o.omega; }
    ctx.lastZeff = o.zeff;
    ctx.waveNow = o.wave_k[0];
    //: the page's loop keeps `lastChiNeo` for the turbulent tiers only (the
    //: neoclassical chi IS `chiI` there); the entry reports it as `chi_neo`
    if (turb) ctx.lastChiNeo = o.chi_neo;
    if (ctx.ipCtl && ctx.channels.current) {
      ctx.vLoopNow = o.v_loop_used[0];
      ctx.ipCtl.ratio0 = o.ipctl_calibrated ? o.ipctl_ratio0 : null;
      ctx.ipCtl.integral = o.ipctl_integral;
      ctx.ipCtl.last = { t: tNow, ip: o.ip_psi[0], want: o.ip_want[0], err: o.ip_err[0],
                         vLoop: o.v_loop_used[0], integral: o.ipctl_integral };
      ctx.ipCtl.log.push(ctx.ipCtl.last);
    }
    if (ctx.channels.current) { st.psi = o.psi; st.q = o.q; }
    ctx.lastBs = ctx.channels.current ? o.j_bs : null;
    ctx.lastOhm = o.ohm;
    ctx.lastChi = { e: o.chi_e, i: o.chi_i };
    var nuMax = 0;
    for (var q = 0; q < n; q++) {
      var nu = o.exch_prev_out[q];
      if (isFinite(nu) && nu > nuMax) nuMax = nu;
    }
    ctx.tauExch = nuMax > 0 ? 1 / nuMax : null;
    //: the driven currents the page's `evClosure` keeps apart: the beam's (or
    //: the prescribed Gaussian when neither executor is on), and the wave's
    ctx.lastCd = ctx.channels.current && (sp.beam || (sp.iCd && !sp.lh)) ? o.j_cd : null;
    ctx.lastLh = ctx.channels.current && sp.lh ? o.j_lh : null;
    ctx.dtCapped = o.dt_capped | 0;
    var r1 = o.saw_r1[0], mixed = o.saw_mixed[0];
    if (r1 > 0) {
      crashes.push({ step: steps, t: tNow, r1: r1, rMix: mixed,
                     refused: o.saw_refused[0]
                       ? FyI18n.t('e.err.sawmix') : undefined });
    }
    ctx.lastDiag = { pAux: o.p_aux[0], pAuxBeam: o.p_aux_beam[0], pAuxLh: o.p_aux_lh[0],
                     torqueBeam: beam ? beam.torqueTotal * kpNow : null, pAlpha: o.p_alpha[0],
                     pRad: o.p_rad[0], pLine: o.p_line[0],
                     pOhm: o.p_ohm[0] };
    var rd = evReadings(ctx, st, ctx.lastDiag, tNow);
    rd.dt = o.dt_used[0];
    rd.steady = !!o.settled;
    rd.crashes = crashes.length;
    rd.crashed = r1 > 0 && !o.saw_refused[0];
    rd.balance = o.balance[0];
    //: the loop's dW/dt: the stored energy's move over the step just taken,
    //: nothing on the first step (第二十二刀: the resumed leg starts over too)
    rd.dwdt = wPrev === null ? 0 : (rd.wTh - wPrev) / Math.max(rd.dt, 1e-12);
    wPrev = rd.wTh;
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
             geoSource: geo.source, coupled: blk ? blk.index : 0, viaEntry: true });
    }
    prev = o;
    if (o.settled) break;
  }
  return { steps: steps, tNow: tNow, settled: !!(prev && prev.settled), beam: beam, lh: lh, prev: prev, wPrev: wPrev };
}

/**
 * The flux-match tier, driven through the KERNEL (第二十一刀, 2026-09-05).
 *
 * ★★A ROOT FIND IN STAGES.  `evFluxMatch` used to run the kernel's Newton
 * machine from here with a JavaScript callback that evaluated the closure
 * (`evClosure`: the neoclassical chi, TGLF at the match radii, the exchange)
 * and the sources at every probe.  The machine, the evaluation, the frozen
 * burn, the lagged pedestal and the record are `case.rs::evolve` with
 * `closure: 4` now — as STAGES, because TGLF lives in the extension module the
 * core wasm cannot call: `start` hands back the state at x0 and the match
 * radii, this function knocks on the extension's `code/turbulence` at those
 * radii, `eval` takes the chi and asks for the next state (or marks the
 * matched one final), and `finish` writes the record.  What is left here is
 * the CADENCE, the per-iteration post, and the stationary outer loop's own
 * bookkeeping — its current half is `code/steady_current`, its equilibrium
 * half `evRefit` (第十九刀's door, with the loop's relaxation of the family).
 *
 * The page's `evaluate` ran the closure on x0 twice (once for the yardstick,
 * once as the machine's first point); the door evaluates that state once and
 * serves both, so `turbEvals` counts one call fewer for the same match.
 */
function evFluxMatchEntry(ctx, st, geo, sp, field, chan, prof, beta0, eqFree, edgeTe, edgeTi, freeLog) {
  var arr = function (v) { return v ? Array.from(v) : null; };
  var flat = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  var CARRIED = ['fm_machine', 'fm_x', 'fm_w', 'fm_scalars', 'fm_alpha_e', 'fm_alpha_i', 'fm_alpha_total',
                 'fm_hist_worst', 'fm_hist_conv', 'fm_hist_tped'];
  var n = geo.rho.length;
  var stateDoc = function (stx) {
    var cp = { grid: { psi: arr(stx.psi), 'fylite:psi_norm': arr(geo.psin) },
               electrons: { temperature: arr(stx.te), density: arr(stx.ne) },
               t_i_average: arr(stx.ti), 'fylite:ion_density': arr(stx.ni),
               'fylite:impurity_density': sp.quasi && stx.nz ? arr(stx.nz) : undefined };
    Object.keys(cp).forEach(function (k) { if (cp[k] === undefined || cp[k] === null) delete cp[k]; });
    if (!cp.grid['fylite:psi_norm']) delete cp.grid['fylite:psi_norm'];
    if (!cp.grid.psi) delete cp.grid.psi;
    return { profiles_1d: cp };
  };
  //: the extension's door at the MATCH radii on the state a stage asked for
  //: (the page's `turbulentChi` with `ctx.matchRadii`, no relaxation on this tier)
  var turbAt = function (rec) {
    var lad = rec.fields.equilibrium.time_slice.profiles_1d;
    var cpr = rec.fields.core_profiles.profiles_1d;
    var rows = {};
    ['rho_tor', 'fylite:r_minor', 'fylite:r_major', 'fylite:shift', 'q', 'magnetic_shear', 'elongation', 'triangularity_upper']
      .forEach(function (k) { rows[k] = Array.from(flat(lad[k])); });
    var plan = { settings: { a: rec.facts.a.value, b0: rec.facts.b0.value, n_rad: sp.turbNrad, n_ky: sp.turbNky,
                             sat_rule: 1, width: 1.65, relax: 1 },
                 inputs: { equilibrium: { time_slice: { profiles_1d: rows } },
                           core_profiles: { profiles_1d: {
                             grid: { rho_tor: rows.rho_tor },
                             electrons: { temperature: Array.from(flat(cpr.electrons.temperature)), density: Array.from(flat(cpr.electrons.density)) },
                             t_i_average: Array.from(flat(cpr.t_i_average)), 'fylite:ion_density': Array.from(flat(cpr['fylite:ion_density'])) } },
                           turbulence: { 'fylite:radii': Array.from(fieldFlat(rec, 'fm_index')) } } };
    var t = tglf.complete('code/turbulence', plan);
    ctx.turbChi = fieldFlat(t, 'chi_turb');
    ctx.turbSub = { xs: fieldFlat(t, 'xs'), sub: fieldFlat(t, 'sub') };
    ctx.turbEvals = (ctx.turbEvals | 0) + 1;
    return ctx.turbChi;
  };
  //: one match: the stages, the extension between them, the per-iteration post
  var matchOnce = function (stStart, edge, round) {
    var base = evEntryPlan(ctx, stStart, geo, sp, field);
    var settings = base.settings;
    settings.closure = 4; settings.n_rad = sp.turbNrad; settings.fm_rho_min = sp.fmRhoMin;
    settings.fm_iter = sp.fmIter; settings.fm_tol = sp.fmTol; settings.fm_dx = sp.fmDx; settings.fm_dx_max = sp.fmDxMax;
    settings.edge_te = edge.te; settings.edge_ti = edge.ti;
    var inputs = { equilibrium: base.equilibrium, core_profiles: stateDoc(stStart) };
    if (base.beamPlan) inputs.nbi = { unit: [base.beamPlan.unit] };
    if (base.lhPlan) inputs.lh_antennas = { antenna: base.lhPlan.antennas };
    var plan = function (stage, carried) {
      var inp = assign(inputs, carried ? { evolve: carried } : {});
      return { settings: assign(settings, { stage: stage }), inputs: inp };
    };
    var rec = fy.complete('code/evolve', plan('start', null));
    var beamRec = rec.fields.beam || null, lhRec = rec.fields.lh || null;
    execJ = { beam: rec.fields.fm_beam_j ? fieldFlat(rec, 'fm_beam_j') : null,
              lh: rec.fields.fm_lh_j ? fieldFlat(rec, 'fm_lh_j') : null };
    var posted = 0, guard = 0;
    for (;;) {
      var carried = {};
      CARRIED.forEach(function (k) { carried['fylite:' + k] = Array.from(fieldFlat(rec, k)); });
      carried['fylite:chi_turb'] = Array.from(turbAt(rec));
      var stage = rec.facts.fm_final.value === 1 ? 'finish' : 'eval';
      rec = fy.complete('code/evolve', plan(stage, carried));
      //: the page posted once per iteration boundary; the door keeps the
      //: history, so a boundary is a history that grew
      var hist = fieldFlat(rec, 'fm_hist_worst');
      for (; posted < hist.length; posted++)
        post({ type: 'evolve_match', iteration: posted + 1, iterations: sp.fmIter, worst: hist[posted],
               tol: sp.fmTol, round: round, rounds: sp.fmOuter });
      if (rec.facts.fm_phase.value === 3) break;
      if (++guard > (2 + 4) * sp.fmIter + 80) throw new Error('the flux match did not finish');
    }
    var F = function (k) { return fieldFlat(rec, k); };
    var X = function (k) { return rec.facts[k].value; };
    var cpr = rec.fields.core_profiles.profiles_1d;
    var stOut = { te: flat(cpr.electrons.temperature), ti: flat(cpr.t_i_average), ne: flat(cpr.electrons.density),
                  ni: flat(cpr['fylite:ion_density']), nz: stStart.nz || null, psi: stStart.psi, q: stStart.q || null,
                  omega: stStart.omega || null };
    //: what the page's `evaluate` left in `ctx` at the matched state
    ctx.lastChi = { e: F('chi_e'), i: F('chi_i') };
    ctx.lastChiNeo = F('chi_neo');
    ctx.lastZeff = F('zeff');
    ctx.lastBs = null;
    ctx.lastDiag = { pAlpha: X('p_alpha'), pRad: X('p_rad'), pLine: X('p_line'), pOhm: 0, pAux: X('p_aux'),
                     pAuxBeam: X('p_aux_beam'), pAuxLh: X('p_aux_lh'),
                     torqueBeam: isFinite(X('torque_beam')) ? X('torque_beam') : null };
    if (sp.pedestal && X('ped_on')) {
      ctx.pedestal = { tPed: X('ped_tped'), pPed: X('ped_pped'), width: X('ped_width'),
                       extrapolation: X('ped_extrap'), worstInput: X('ped_worst_input') };
    }
    var histW = F('fm_hist_worst'), histC = F('fm_hist_conv'), histT = F('fm_hist_tped');
    var history = [];
    for (var h = 0; h < histW.length; h++)
      history.push({ iteration: h + 1, worst: histW[h], converged: histC[h] === 1,
                     tPed: isFinite(histT[h]) ? histT[h] : null });
    var sel = Array.from(F('fm_index'), function (v) { return v | 0; });
    var record = {
      radii: Array.from(F('fm_radii')), rhoN: Array.from(F('fm_rho_n')), psin: Array.from(F('fm_psin')), index: sel,
      alte: Array.from(F('fm_alte')), alti: Array.from(F('fm_alti')),
      fluxE: Array.from(F('fm_flux_e')), fluxI: Array.from(F('fm_flux_i')),
      targetE: Array.from(F('fm_target_e')), targetI: Array.from(F('fm_target_i')),
      relE: Array.from(F('fm_rel_e')), relI: Array.from(F('fm_rel_i')),
      history: history, iterations: X('fm_iterations'), converged: X('fm_converged') === 1,
      worst: X('fm_worst'), tol: sp.fmTol, evaluations: X('fm_evals'),
      channels: 2, nRadii: X('n_radii'), dx: sp.fmDx, dxMax: sp.fmDxMax, rhoMin: sp.fmRhoMin,
      burnFrozen: !!sp.alpha, burnCheck: sp.alpha ? X('fm_burn_check') : null,
      weightFloor: X('fm_weight_floor'), weightRef: X('fm_weight_ref'),
      viaEntry: true,
    };
    return { st: stOut, record: record, edge: { te: X('edge_te_out'), ti: X('edge_ti_out') },
             beamRec: beamRec, lhRec: lhRec };
  };
  //: the current half of a stationary round (`code/steady_current`)
  var steadyCurrent = function (stx, first) {
    if (!geo.gm2) return null;
    var lad = { rho_tor: arr(geo.rho), dvolume_drho_tor: arr(geo.vprime), gm3: arr(geo.gm3), gm2: arr(geo.gm2),
                f: arr(geo.fpol), q: arr(geo.q), 'fylite:r_minor': arr(geo.rmin), 'fylite:r_major': arr(geo.rmaj) };
    var settings = { a: geo.a, r0: geo.r0, b0: geo.b0, ip_a: sp.ip, zeff: sp.zeff, bootstrap: sp.bootstrap ? 1 : 0,
                     quasi: sp.quasi ? 1 : 0, imp_z: sp.impurityZ || 0, tol_steady: sp.tolSteady, n_coupling: sp.nCoupling,
                     relax: sp.fmORelax === undefined ? 1 : sp.fmORelax, first: first ? 1 : 0,
                     sawtooth: sp.sawtooth ? 1 : 0, saw_mix: sp.sawtooth ? sp.sawMix : 0,
                     i_cd_a: sp.iCd || 0, cd_centre: sp.cdCentre, cd_width: sp.cdWidth };
    var evolve = {};
    if (stx.q) evolve['fylite:q_prev'] = arr(stx.q);
    //: the executors' driven current on the ladder, as the match's start stage
    //: evaluated it (the loop's `ctx.beamJ` / `ctx.lhJ`)
    if (execJ.beam) evolve['fylite:beam_j'] = arr(execJ.beam);
    if (execJ.lh) evolve['fylite:lh_j'] = arr(execJ.lh);
    var rec;
    try {
      rec = fy.complete('code/steady_current', { settings: settings, inputs: {
        equilibrium: { time_slice: { profiles_1d: lad } }, core_profiles: stateDoc(stx), evolve: evolve } });
    } catch (e) { return { failed: String(e && e.message || e) }; }
    var X = function (k) { return rec.facts[k].value; };
    var cpr = rec.fields.core_profiles.profiles_1d;
    var psiOld = stx.psi;
    stx.te = flat(cpr.electrons.temperature); stx.ti = flat(cpr.t_i_average); stx.ne = flat(cpr.electrons.density);
    stx.ni = flat(cpr['fylite:ion_density']); stx.psi = flat(cpr.grid.psi); stx.q = fieldFlat(rec, 'q');
    ctx.steadyRecord = { rho: geo.rho, vprime: geo.vprime, gm3: geo.gm3, gm2: geo.gm2, fpol: geo.fpol, b0: geo.b0,
                         psiIn: psiOld, edgePsiRate: X('v_loop'), dt: X('dt_steady'),
                         sigmaPar: fieldFlat(rec, 'sigma'), jNi: fieldFlat(rec, 'j_ni'),
                         tolSteady: sp.tolSteady, nCoupling: sp.nCoupling,
                         psiOut: X('frozen') ? fieldFlat(rec, 'psi_frozen') : fieldFlat(rec, 'psi_out_run'),
                         psiOutRun: fieldFlat(rec, 'psi_out_run'), frozen: !!X('frozen'), frozenGap: X('frozen_gap'),
                         q: stx.q, viaEntry: true };
    return { psiRepaired: X('psi_repaired'), q0: X('q0'),
             sawtooth: X('saw_r1') > 0 ? { r1: X('saw_r1'), rMix: X('saw_r_mix'), psiMoved: X('saw_psi_moved'), iMix: X('saw_i_mix'),
                                          refused: X('saw_refused') ? FyI18n.t('e.err.sawmix') : undefined } : null,
             ip: isFinite(X('ip')) ? X('ip') : null, ipRequested: sp.ip, vLoop: X('v_loop'), vLoopClamped: !!X('v_loop_clamped'),
             dtSteady: X('dt_steady'), dPsi: X('d_psi') };
  };
  var pOf = function (state) {
    var pv = new Float64Array(state.te.length);
    for (var i2 = 0; i2 < pv.length; i2++) pv[i2] = (state.ne[i2] * state.te[i2] + state.ni[i2] * state.ti[i2]) * EV_QE;
    return pv;
  };
  var relMax = function (a2, b2) {
    var num = 0, den = 0;
    for (var i3 = 0; i3 < a2.length; i3++) { num = Math.max(num, Math.abs(a2[i3] - b2[i3])); den = Math.max(den, Math.abs(b2[i3])); }
    return den > 0 ? num / den : 0;
  };
  var edge = { te: edgeTe, ti: edgeTi };
  var execJ = { beam: null, lh: null };
  var outerRounds = [], outerConverged = false, outerWhy = null, fluxMatch = null;
  var beamRec = null, lhRec = null, eq = null;
  for (var rnd = 0; rnd < sp.fmOuter; rnd++) {
    var pPrev = pOf(st), qPrev = st.q ? Float64Array.from(st.q) : null;
    var fmOut;
    try { fmOut = matchOnce(st, edge, rnd + 1); }
    catch (eFm) { throw new Error(FyI18n.t('e.err.fm_failed', { why: String(eFm && eFm.message || eFm) })); }
    st = fmOut.st; fluxMatch = fmOut.record; edge = fmOut.edge;
    if (fmOut.beamRec) beamRec = fmOut.beamRec;
    if (fmOut.lhRec) lhRec = fmOut.lhRec;
    if (!fluxMatch.converged) { outerWhy = 'match'; break; }
    if (sp.fmOuter <= 1) { outerConverged = true; break; }
    var cur = steadyCurrent(st, rnd === 0);
    if (!cur || cur.failed) { outerWhy = (cur && cur.failed) || 'current'; break; }
    //: the equilibrium half: the alternation at this round's current (device tier)
    var psinBefore = geo.psin, eqRound = null;
    if (sp.geometry !== 'device') {
      eqRound = { skipped: sp.geometry === 'gfile' ? 'metric came from a g-file: no boundary to re-solve'
                                                  : 'analytic geometry has no free boundary' };
    } else {
      var ipUse = isFinite(cur.ip) && Math.abs(cur.ip) > 0 ? cur.ip : sp.ip;
      var pfT = null;
      if (ctx.pFastPar) {
        pfT = new Float64Array(n);
        for (var kf = 0; kf < n; kf++) pfT[kf] = (ctx.pFastPar[kf] + 2 * ctx.pFastPerp[kf]) / 3;
      }
      var rf;
      try {
        rf = evRefit(sp, chan, { fit: 1, beta0: beta0, geo: geo, st: st, pFastThird: pfT, eqPrev: eqFree,
                                 ip: ipUse, emp: prof.emp, enp: prof.enp,
                                 fitRelax: sp.fmORelax === undefined ? 1 : sp.fmORelax });
      } catch (eR) { eqRound = { failed: String(eR && eR.message || eR) }; }
      if (eqRound && eqRound.failed) { outerWhy = eqRound.failed; break; }
      var aOld = geo.a;
      beta0 = rf.beta0; prof = { beta0: rf.beta0, emp: rf.emp, enp: rf.enp, r0: sp.r0Src };
      eq = rf.eq; eqFree = rf.eqFree;
      freeLog.push(assign({ block: rnd + 1 }, rf.free));
      st = assign(rf.st, { q: st.q ? evRemap(psinBefore, st.q, rf.geo.psin) : null });
      geo = rf.geo; field = rf.field;
      ctx.geo = geo; ctx.rho = geo.rho; ctx.psiPrev = null; n = geo.rho.length;
      pPrev = evRemap(psinBefore, pPrev, geo.psin);
      if (qPrev) qPrev = evRemap(psinBefore, qPrev, geo.psin);
      eqRound = { aOld: aOld, aNew: geo.a, beta0: rf.beta0, bpTarget: rf.bpTarget, bpEq: rf.bpEq, ipUsed: ipUse,
                  free: rf.free, fit: rf.fit, refined: rf.refined ? { ip: rf.refined.ip, ipTarget: ipUse, resP: rf.refined.resP, resF: rf.refined.resF } : null,
                  refineWhy: rf.refineWhy, geo: true };
    }
    var dP = relMax(pOf(st), pPrev);
    var dQ = qPrev && st.q ? relMax(st.q, qPrev) : NaN;
    var first = rnd === 0;
    outerRounds.push({ round: rnd + 1, dPressure: dP, dQ: dQ, q0: cur.q0, ip: cur.ip, ipRequested: cur.ipRequested,
                       psiRepaired: cur.psiRepaired, sawtooth: cur.sawtooth || null,
                       vLoop: cur.vLoop, vLoopClamped: cur.vLoopClamped,
                       matchIterations: fluxMatch.iterations, matchWorst: fluxMatch.worst,
                       equilibrium: eqRound && eqRound.geo
                         ? { aOld: eqRound.aOld, aNew: eqRound.aNew, beta0: eqRound.beta0, bpTarget: eqRound.bpTarget,
                             bpEq: eqRound.bpEq, ipUsed: eqRound.ipUsed, free: eqRound.free }
                         : null,
                       equilibriumSkipped: eqRound ? (eqRound.skipped || null) : null });
    post({ type: 'evolve_round', round: rnd + 1, rounds: sp.fmOuter, dPressure: dP, dQ: dQ });
    if (!first && dP < sp.fmOTol && (isNaN(dQ) || dQ < sp.fmOTol)) { outerConverged = true; break; }
  }
  var stationary = sp.fmOuter > 1
    ? { rounds: outerRounds, converged: outerConverged, why: outerWhy, tolerance: sp.fmOTol, maxRounds: sp.fmOuter,
        equilibriumRounds: outerRounds.filter(function (r) { return r.equilibrium; }).length,
        equilibriumWhy: (outerRounds.length && outerRounds[0].equilibriumSkipped) || null }
    : null;
  return { st: st, geo: geo, field: field, eq: eq, eqFree: eqFree, beta0: beta0, prof: prof,
           record: fluxMatch, stationary: stationary, edgeTe: edge.te, edgeTi: edge.ti,
           beamRec: beamRec, lhRec: lhRec };
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
  //: ★T-4 第五刀: the species, the start profiles, the dilution, the
  //: pedestal edge and the actuators at t_start are the PROBE's now
  //: (`code/evolve` with `probe: 1`, below the geometry); a name the
  //: table does not carry is its refusal.
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
  var geo = null, eq = null, chan = null, beta0 = sp.beta0, eqFree0 = null;
  var prof = { beta0: beta0, emp: sp.emp, enp: sp.enp, r0: sp.r0Src };
  //: what the cross-section is traced on — the same psi the metric came from
  var field = null;
  if (sp.geometry === 'device') {
    if (!msg.chan) return post({ type: 'error', where: 'evolve',
                                 message: FyI18n.t('recon.noref') });
    chan = Float64Array.from(msg.chan);
    //: ★第十九刀: the start is `code/refit` with `fit: 0` — the free solve on
    //: the coils at these currents and the ladder traced off it, the same door
    //: the alternation below knocks on between blocks (it used to be
    //: `summarize(freeSolve(…))` + `evLadderFromSolve` here, flat exports)
    var rf0;
    try { rf0 = evRefit(sp, chan, { fit: 0, beta0: beta0 }); }
    catch (e0) { return post({ type: 'error', where: 'evolve', message: String(e0 && e0.message || e0) }); }
    eq = rf0.eq; geo = rf0.geo; field = rf0.field;
    eqFree0 = rf0.eqFree;
    //: ★★THE EQUILIBRIUM THIS MARCH STANDS ON, and whether the solver got
    //: there.  Block 0 is the one every frozen-geometry run uses for its
    //: whole march, so a run with `couple = 0` has exactly this one entry
    //: and it is still the thing that decides whether the metric ladder
    //: means anything.
    freeLog.push(assign({ block: 0 }, freeReport(eq)));
  } else if (sp.geometry === 'gfile') {
    var g = msg.gfile;
    field = { psi: Float64Array.from(g.psi), psiAxis: g.psiAxis,
              psiBnd: g.psiBnd, axisR: g.axisR, axisZ: g.axisZ,
              r0: g.r0, z0: g.z0, dr: g.dr, dz: g.dz, nr: g.nr, nz: g.nz,
              limR: Float64Array.from(g.limR), limZ: Float64Array.from(g.limZ) };
    //: ★第二十八刀: the g-file tier's metric is the PROBE's too — the document
    //: (its gauge stated) traced by the kernel on the page's own level rule
    //: (`n`, 121 theta points); how many surfaces it keeps is only known
    //: once it answers, so the grid size waits for the probe
    geo = { rho: null, n: 0, a: g.a, r0: g.rmaj, b0: Math.abs(g.b0), source: 'gfile', pending: true,
            psiAxis: g.psiAxis, psiBnd: g.psiBnd, doc: interpGfileDoc(g) };
  } else {
    //: ★第二十六刀: the analytic tier's metric is the PROBE's (below): the
    //: kernel spells the page's grid (x_i = i/(n-1), rho = a·x) and builds
    //: every row on it; nothing is bound but the size
    geo = { rho: null, n: Math.max(5, sp.n | 0), a: sp.a, r0: sp.r0, b0: Math.abs(sp.b0),
            source: 'miller', pending: true };
  }
  //: ★★What the current channel needs is TWO things, and until S-2c 批二
  //: only one of them was ever missing, so the refusal tested only that
  //: one.  `gm2` is now stated by every tier (the analytic one included).
  //: An INITIAL FLUX is not: `evPsiOf` returns 0 where there is no
  //: equilibrium, so the analytic tier would march current diffusion from
  //: psi = 0 — a run, not a refusal, and one whose q is whatever the
  //: solver's clamp says.  So the test moved to what is actually absent.

  // --- the state it starts from --------------------------------------------
  var n = geo.pending ? geo.n : geo.rho.length;
  //: ★★T-4 第五刀 (第二十四刀): THE START STATE COMES FROM THE PROBE.  What
  //: this function used to build by hand before its first block — the
  //: parabolic profiles or the reference's, the dilution and its check, the
  //: pedestal edge at start, the waveform factor at t_start, the torque
  //: deposit, beta_N — is `code/evolve` with `probe: 1` now, and the page
  //: reads the answer.  The ladder's psi keeps the page's spelling
  //: (`evPsiOf`) and is bound like the other ladder rows; a resumed state
  //: is bound as the state and comes back as it went.
  var rp = sp.useRef && msg.refProf ? msg.refProf : null;
  var rs = msg.resume || null;
  //: ★the grid is known before the probe on every tier but the g-file's,
  //: where the kernel decides how many surfaces it keeps: the resume check
  //: and the start psi wait for the answer there
  var sizeKnown = n > 0;
  if (sizeKnown && rs && (!rs.te || rs.te.length !== n))
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.resume_grid',
                                    { was: rs.te ? rs.te.length : 0, now: n }) });
  var psi0 = null;
  if (sizeKnown) {
    psi0 = new Float64Array(n);
    for (var i = 0; i < n; i++)
      psi0[i] = rs && rs.psi && rs.psi.length === n ? rs.psi[i] : evPsiOf(geo, i);
  } else if (rs && rs.psi) {
    psi0 = Float64Array.from(rs.psi);
  }
  var st = { te: null, ti: null, ne: null, ni: null, nz: null, psi: psi0, q: null,
             omega: momentum && sizeKnown ? new Float64Array(n) : null };
  var spProbe = assign({}, sp); spProbe.beam = false; spProbe.lh = false;
  var pp = evEntryPlan({ channels: channels, momentum: momentum }, st, geo, spProbe, field);
  var ps = pp.settings;
  ps.probe = 1; ps.state = rs ? 1 : 0; ps.reference = rp ? 1 : 0;
  ps.t_start = msg.tStart || 0;
  if (geo.pending && geo.source === 'miller') { ps.geometry = 'miller'; ps.q95 = sp.q95; ps.n = n; }
  if (geo.pending && geo.source === 'gfile') {
    ps.geometry = 'gfile'; ps.n = Math.max(5, sp.n | 0); ps.edge_psin = sp.edgePsin; ps.n_theta = 121;
  }
  var arrOr = function (v) { return v ? Array.from(v) : undefined; };
  var pin = { equilibrium: geo.doc || pp.equilibrium };
  if (rs) {
    pin.core_profiles = { profiles_1d: {
      grid: psi0 ? { psi: Array.from(psi0) } : {},
      electrons: { temperature: Array.from(rs.te), density: Array.from(rs.ne) },
      t_i_average: Array.from(rs.ti) } };
    if (!psi0) delete pin.core_profiles.profiles_1d.grid;
  } else if (rp) {
    var refT = { grid: { rho_tor: Array.from(rp.rho) },
                 electrons: { temperature: arrOr(rp.te), density: arrOr(rp.ne) },
                 t_i_average: arrOr(rp.ti) };
    if (!refT.electrons.temperature) delete refT.electrons.temperature;
    if (!refT.electrons.density) delete refT.electrons.density;
    if (!refT.t_i_average) delete refT.t_i_average;
    pin.core_profiles = { profiles_1d: refT };
  }
  var prec;
  try { prec = fy.complete('code/evolve', { settings: ps, inputs: pin }); }
  catch (eP) {
    return post({ type: 'error', where: 'evolve', message: String(eP && eP.message || eP) });
  }
  var PF = function (k) { return fieldFlat(prec, k); };
  var PN = function (node) { return fieldFlat({ fields: { v: node } }, 'v'); };
  var PX = function (k) { return prec.facts[k] ? prec.facts[k].value : NaN; };
  var pcp = prec.fields.core_profiles.profiles_1d;
  if (geo.pending) {
    var plad = prec.fields.equilibrium.time_slice.profiles_1d;
    var row = function (k) { return plad[k] ? PN(plad[k]) : null; };
    var wasGfile = geo.source === 'gfile', gAxis = geo.psiAxis, gBnd = geo.psiBnd;
    geo = { rho: row('rho_tor'), vprime: row('dvolume_drho_tor'), gm3: row('gm3'), gm2: row('gm2'),
            r2: row('fylite:r2_average'), fpol: row('f'), q: row('q'), shear: row('magnetic_shear'),
            kappa: row('elongation'), delta: row('triangularity_upper'), rmaj: row('fylite:r_major'),
            rmin: row('fylite:r_minor'), shift: row('fylite:shift'), psin: row('fylite:psi_norm'),
            a: wasGfile ? PX('a') : sp.a, r0: wasGfile ? PX('r0_geo') : sp.r0,
            b0: wasGfile ? PX('b0') : Math.abs(sp.b0), source: wasGfile ? 'gfile' : 'miller' };
    if (wasGfile) { geo.psiAxis = gAxis; geo.psiBnd = gBnd; }
    if (!sizeKnown) {
      n = geo.rho.length;
      if (rs && (!rs.te || rs.te.length !== n))
        return post({ type: 'error', where: 'evolve',
                      message: FyI18n.t('e.err.resume_grid', { was: rs.te ? rs.te.length : 0, now: n }) });
      st.psi = psi0 && psi0.length === n ? psi0 : PN(plad.psi);
      if (momentum) st.omega = new Float64Array(n);
    }
  }
  //: ★第二十八刀: what the channels and the executors need is asked of the
  //: geometry the probe RESOLVED (its rows exist on every tier now)
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
  st.te = PN(pcp.electrons.temperature); st.ti = PN(pcp.t_i_average);
  st.ne = PN(pcp.electrons.density); st.ni = PN(pcp['fylite:ion_density']);
  sp.bulkId = PX('bulk_id'); sp.impurityId = PX('imp_id');
  sp.impurityZ = PX('imp_z') || 0; sp.impurityA = PX('imp_mass') || 0;
  var zList = [1], edgeNi = [rp ? st.ne[n - 1] : sp.edgeNe];
  if (sp.quasi) {
    st.nz = PN(pcp['fylite:impurity_density']);
    if (PX('quasi_check') > 1e-6)
      return post({ type: 'error', where: 'evolve',
                    message: FyI18n.t('e.err.quasi_check') });
    sp.dtEffective = PX('dt_fraction_used');
    zList = [1, sp.impurityZ];
    edgeNi = [st.ni[n - 1], st.nz[n - 1]];
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

  //: the Dirichlet edge the march starts from — the reference's own edge on
  //: a reference start, the case's otherwise, the EPED1-NN pedestal top when
  //: the model is on (T-M4: p_ped/(2 n_e,ped k), T_e = T_i); the record the
  //: readings and the export carry is the probe's evaluation
  var edgeTe = PX('edge_te_out'), edgeTi = PX('edge_ti_out');
  var ctx0Pedestal = null;
  if (sp.pedestal && !rp) {
    ctx0Pedestal = {
      inputs: { a: geo.a, betan: Math.max(0.05, PX('beta_n')), bt: Math.abs(geo.b0),
                delta: sp.delta, ip: Math.abs(sp.ip) / 1e6, kappa: sp.kappa,
                mass: PX('ped_mass'), neped: PX('ped_neped'), r: geo.r0, zeffped: sp.zeff },
      pPed: PX('ped_pped'), width: PX('ped_width'),
      pPedAll: Array.from(PF('ped_p_ped_all')), widthAll: Array.from(PF('ped_width_all')),
      extrapolation: PX('ped_extrap'), worstInput: PX('ped_worst') | 0,
      tPed: PX('ped_tped') };
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

  //: the actuators at t_start, off the probe: the waveform factor the run
  //: starts at and the prescribed torque deposit (the record's `torque` with
  //: the momentum channel and no beam; a beam sets its own per step)
  ctx.waveNow = PX('wave_now');
  ctx.pFastPar = null; ctx.pFastPerp = null;
  ctx.torque = Float64Array.from(PF('torque'));
  //: the executors' reports, filled from the entry's own records as the
  //: blocks return them (a refused / absent executor stays null)
  var beam = null, lh = null;

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
  var eqFree = eqFree0 || eq, refinedField = null;
  //: ★the closure once BEFORE the first step, so the exchange cap below has
  //: a rate to bound the first step with.  Without it the cap starts one
  //: step late — and the first step is the one a reader is most likely to
  //: have made enormous.
  //: ★the pre-march closure evaluation is the LOOP's (its first exchange
  //: ceiling); on the entry path the entry evaluates its own, and since
  //: 第十八刀 the turbulent tier's first TGLF call is the extension door's
  //: (`evEntryMarch`), not this flat-export path's


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
  //: ★第二十一刀: the flux-match tier runs through the kernel's stages when the
  //: ledger says the entry carries this configuration; the loop below stays for
  //: what it does not (the page's resume)
  var fmViaEntry = sp.closure === 4 && evScopeMiss(sp).length === 0;
  if (fmViaEntry) {
    ctx.zList = zList; ctx.edgeNi = edgeNi;
    ctx.eqFree = eqFree;
    var fmr;
    try {
      fmr = evFluxMatchEntry(ctx, st, geo, sp, field, chan, prof, beta0, eqFree, edgeTe, edgeTi, freeLog);
    } catch (eFmE) {
      return post({ type: 'error', where: 'evolve', message: String(eFmE && eFmE.message || eFmE) });
    }
    st = fmr.st; geo = fmr.geo; field = fmr.field; beta0 = fmr.beta0; prof = fmr.prof;
    if (fmr.eq) { eq = fmr.eq; }
    eqFree = fmr.eqFree;
    fluxMatch = fmr.record; stationary = fmr.stationary;
    edgeTe = fmr.edgeTe; edgeTi = fmr.edgeTi;
    n = geo.rho.length;
    if (sp.beam && fmr.beamRec && !beam) {
      var rbF = (function (node) { return { F: function (k) { return fieldFlat({ fields: node }, k); },
                                            X: function (k) { return fieldFlat({ fields: node }, k)[0]; },
                                            dim: function (k) { return fieldFlat({ fields: node.dims }, k)[0] | 0; } }; })(fmr.beamRec);
      var bp0 = evBeamPlan(field, geo, st, sp);
      beam = evBeamRead(fmr.beamRec, rbF.F, rbF.X, rbF.dim('n_components'), bp0, field, geo, sp);
      beam.cadence = 0;
    }
    var rdFmE = evReadings(ctx, st, ctx.lastDiag, 0);
    rdFmE.dt = 0; rdFmE.delta = fluxMatch.worst; rdFmE.retries = 0;
    rdFmE.steady = fluxMatch.converged;
    rdFmE.crashes = 0; rdFmE.crashed = false; rdFmE.dwdt = 0;
    if (sp.pedestal && ctx.pedestal) {
      rdFmE.pedTPed = edgeTe;
      rdFmE.pedPPed = ctx.pedestal.pPed;
      rdFmE.pedWidth = ctx.pedestal.width;
      rdFmE.pedExtrap = ctx.pedestal.extrapolation;
    }
    trace.push(rdFmE);
    post({ type: 'evolve_step', step: 1, nSteps: 1,
           rho: geo.rho, psin: geo.psin, reading: rdFmE,
           te: st.te, ti: st.ti, ne: st.ne, q: st.q,
           chiE: ctx.lastChi ? ctx.lastChi.e : null,
           chiI: ctx.lastChi ? ctx.lastChi.i : null,
           jni: ctx.lastBs || null,
           geoSource: geo.source, coupled: 0, viaEntry: true });
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
  //: ★★★T-4 第四刀 (第二十三刀, 2026-09-05): THE ONLY BRANCH.  The loop that used
  //: to run every configuration the entry did not carry is gone — since the
  //: twenty-second cut there was none left.  A configuration the ledger still
  //: calls out is refused by name here rather than run some other way.
  var entryMiss = evScopeMiss(sp);
  if (entryMiss.length)
    return post({ type: 'error', where: 'evolve',
                  message: FyI18n.t('e.err.entry_scope', { what: entryMiss.join('; ') }) });
  var viaEntry = blocks > 0;
  if (viaEntry) {
    //: ★★第十九刀 — the block cadence on the entry path.  `couple = K` on the
    //: device tier runs the entry K steps at a time and knocks on `code/refit`
    //: between blocks; everything the loop below did in its equilibrium half
    //: is that door's (`evRefit`).  What stays here is the loop's own
    //: bookkeeping: the round record, the `evolve_couple` post, the picture.
    var lastO = null, wPrevE = null;
    for (var eb = 0; eb < blocks; eb++) {
      var ebTake = Math.min(perBlock, sp.nSteps - steps);
      if (ebTake <= 0) break;
      var em = evEntryMarch(ctx, st, geo, sp, trace, crashes, tNow, field,
                            { index: eb, steps0: steps, take: ebTake, prev: lastO,
                              lagReset: eb > 0, vprimeOld: eb > 0 ? vprimeOld : null, wPrev: wPrevE });
      wPrevE = em.wPrev;
      steps = em.steps;
      tNow = em.tNow;
      if (em.beam) beam = em.beam;
      if (em.lh) lh = em.lh;
      settledEarly = em.settled;
      lastO = em.prev;
      //: the block's own record, in the loop's shape; the step-controller
      //: fields the entry does not report stay null
      rounds.push({ block: eb + 1, steps: steps, settled: em.settled,
                    delta: null, psiRepaired: null, dt: lastO ? lastO.dt_used[0] : null, retries: null,
                    fit: null, bpTarget: NaN, bpEq: NaN, bpFix: NaN,
                    beta0: beta0, refined: null, refineWhy: null, free: null });
      if (settledEarly) break;
      if (!(sp.couple > 0 && sp.geometry === 'device' && eb < blocks - 1)) continue;
      //: the fast branches' trace third, as the loop hands it to the fit
      var pfT = null;
      if (ctx.pFastPar) {
        pfT = new Float64Array(n);
        for (var kf = 0; kf < n; kf++) pfT[kf] = (ctx.pFastPar[kf] + 2 * ctx.pFastPerp[kf]) / 3;
      }
      var rf;
      try {
        rf = evRefit(sp, chan, { fit: 1, beta0: beta0, geo: geo, st: st, pFastThird: pfT, eqPrev: eqFree });
      } catch (e1) {
        return post({ type: 'error', where: 'evolve', message: String(e1 && e1.message || e1) });
      }
      var psinOld = geo.psin;
      beta0 = rf.beta0; fit = rf.fit; bpTarget = rf.bpTarget; bpEq = rf.bpEq; bpFix = rf.bpFix;
      eq = rf.eq; eqFree = rf.eqFree;
      var refinedE = rf.refined, refineWhyE = rf.refineWhy;
      if (refinedE) refinedField = refinedE.field;
      var freeNowE = assign({ block: eb + 1 }, rf.free);
      freeLog.push(freeNowE);
      vprimeOld = rf.vprimeOld;
      st = rf.st;
      geo = rf.geo; field = rf.field;
      ctx.geo = geo; ctx.rho = geo.rho; n = geo.rho.length;
      ctx.psiPrev = null;
      ctx.omega = st.omega;
      //: the executors follow the equilibrium they stop in: the next block's
      //: first step evaluates them afresh on the new psi map (no carried
      //: arrays), which is the loop's `rebuildBeam()`
      beam = null; lh = null;
      //: the turbulent chi the relaxation continues from moves onto the new
      //: ladder by psi_N with the state (the loop kept the stale array)
      if (ctx.turbChi) ctx.turbChi = evRemap(psinOld, ctx.turbChi, geo.psin);
      //: the continuation: the last record's scalars, its arrays on the new
      //: ladder; the lagged pair is dropped (`lag_reset`), the exchange ceiling
      //: keeps the previous closure's fastest rate (the loop reads `ctx.lastCr`
      //: unchanged across the alternation)
      var exMax = 0;
      for (var ke = 0; ke < lastO.exch_prev_out.length; ke++) {
        var exv = lastO.exch_prev_out[ke];
        if (isFinite(exv) && exv > exMax) exMax = exv;
      }
      lastO = assign(lastO, {
        te: st.te, ti: st.ti, ne_out: st.ne, psi: st.psi, ni_main: st.ni, nz: st.nz, omega: st.omega,
        psi_prev_out: new Float64Array(n), sigma_prev_out: new Float64Array(n), exch_prev_out: evFill(n, exMax),
        beam_e: null, beam_i: null, beam_torque: null, beam_j: null, beam_p_par: null, beam_p_perp: null,
        lh_e: null, lh_j: null });
      sendOutlines();
      var refRec = refinedE ? {
        ip: refinedE.ip, ipTarget: refinedE.ipTarget, resP: refinedE.resP, resF: refinedE.resF,
        degP: refinedE.degP, degF: refinedE.degF, iterations: refinedE.iterations, residual: refinedE.residual,
        zero: refinedE.zero } : null;
      post({ type: 'evolve_couple', block: eb + 1, beta0: beta0, free: freeNowE,
             refined: refRec, refineWhy: refineWhyE,
             fit: fit, bpTarget: bpTarget, bpEq: bpEq, bpFix: bpFix,
             lcfs: eq.lcfs, shape: eq.shape });
      var recE = rounds[rounds.length - 1];
      recE.free = freeNowE;
      recE.fit = fit; recE.beta0 = beta0;
      recE.bpTarget = bpTarget; recE.bpEq = bpEq; recE.bpFix = bpFix;
      recE.refineWhy = refineWhyE;
      recE.refined = refRec;
    }
    blocks = 0;
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
