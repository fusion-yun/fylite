// Minimal canvas plotting for the fylite web apps: a poloidal
// cross-section view and a generic XY line plot.  No external libraries —
// the pages are served as plain static files.

(function (root) {
  'use strict';

  /**
   * Smallest 1-2-5 step that keeps labels at least `minPx` apart.
   * `spanPx` may be 0 before the first layout, hence the guard.
   */
  function niceStep(span, spanPx, minPx) {
    if (!(span > 0) || !(spanPx > 0)) return 1;
    var want = span * minPx / spanPx;
    var pow = Math.pow(10, Math.floor(Math.log10(want)));
    var m = want / pow;
    return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * pow;
  }

  function css(el, name) {
    return getComputedStyle(el).getPropertyValue(name).trim();
  }

  /** Device-pixel-ratio aware canvas setup; returns the 2-D context. */
  function prepare(canvas) {
    var dpr = self.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    var w = Math.max(1, Math.round(rect.width)),
        h = Math.max(1, Math.round(rect.height));
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    var ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return { ctx: ctx, w: w, h: h, dpr: dpr };
  }

  function palette(el) {
    return {
      fg: css(el, '--fg') || '#222',
      muted: css(el, '--muted') || '#888',
      grid: css(el, '--grid') || '#ddd',
      wall: css(el, '--wall') || '#666',
      coil: css(el, '--coil') || '#b07',
      flux: css(el, '--flux') || '#89a',
      lcfs: css(el, '--lcfs') || '#c33',
      alt: css(el, '--alt') || '#2a7',
      accent: css(el, '--accent') || '#06c',
      bg: css(el, '--panel') || '#fff',
    };
  }

  /**
   * The colour of series `i` in a plot that draws MANY of them.
   *
   * ★A plot with a coil per channel cannot take its colours from the
   * palette's five named roles — there are twelve of them on the smallest
   * bundled machine.  The rotation stays inside the theme by taking the
   * accent's own hue as the starting point and stepping around the wheel by
   * the golden angle, which is what keeps adjacent channels distinguishable
   * without a hand-picked table that would have to grow with the machine.
   * Lives here rather than in a page: "which colour is series i" is a
   * plotting question, and two pages answering it differently would draw
   * the same channel in two colours.
   */
  function seriesColor(col, i) {
    return 'hsl(' + ((210 + i * 137.508) % 360).toFixed(1) + ' 62% 46%)';
  }

  // --- poloidal cross-section ----------------------------------------------

  /**
   * opts: {machine, grid, psi, psiAxis, psiBnd, lcfs, target, reference,
   *        axis, xpoint, loops, loopColor, loopUsed, chords, chordColor,
   *        coilLabel, coilFill,
   *        handles, legend, legendAnchor, nLevels, caption, view}
   */
  /**
   * 截面图的**平移与缩放**（2026-09-08 用户裁定：可交互缩放）。缺省取景由调用方给，
   * 见 `contentView`（同日裁定：初始框住平衡计算区域，不含线圈）。
   *
   * ★★视图状态挂在**画布自己**身上（`__fyZoom`），不挂在调用方：每一次重画都由调用方
   * 重新给一份 `opts`，若视图存在调用方那边，读者一动控件视图就被打回原样——那正是
   * 「缩放没有用」的样子。★`null` 表示「跟着调用方给的默认走」，双击即回到它，所以
   * 「我把图缩乱了」永远有一步可退。
   * ★重画用的是**上一次的 `opts`**（`__fyOpts`）：图里那些数组（ψ、边界、线圈）都在
   * 里面，交互不需要知道它们是什么，也不该去问调用方要。
   * ★不抢拖拽：页面在这张画布上已经有可拖的 O 点与 X 点，它们用的是指针捕获——捕获期间
   * 这里一律不平移。滚轮缩放没有这个问题，因为它不与拖拽共用手势。
   */
  function sameBox(a, b) {
    return !!a && !!b && a.rmin === b.rmin && a.rmax === b.rmax &&
           a.zmin === b.zmin && a.zmax === b.zmax;
  }

  //: ★★**缩放的两头都拿核心计算区域当尺**（2026-09-08 用户裁定：网格盒的 1/2 ~ 2 倍）。
  //: 此前夹的是「当前缺省视野」的倍数，于是同一个滚轮在不同取景下走得不一样远——勾了
  //: 「视野含全部 PF 线圈」，那一档的两倍已是 ITER 的 22 m。改用网格盒之后，能看到的
  //: 最小与最大是装置自己的尺度，与读者此刻取的景无关。
  //: ★起点已在带外时（例如含线圈那一框对小机器可能超过 4 倍），只拦「往外走」的那一半：
  //: 一律拒绝会把读者锁死在带外，连往回走都不许。
  var ZOOM_MIN = 0.5, ZOOM_MAX = 2;
  function zoomFactor(canvas, v, k) {
    var o = canvas.__fyOpts, g = o && o.machine && o.machine.grid;
    if (!g) return k;
    var ref = Math.max(g.rmax - g.rmin, g.zmax - g.zmin);
    var now = Math.max(v.rmax - v.rmin, v.zmax - v.zmin);
    var out = k > 1;                 //: 这一步是想「看得更宽」还是「看得更近」
    var next = now * k;
    //: ★越界的那一步**削到正好落在界上**，不是整步作废：作废会在带边留下最多一步
    //: （0.835 倍）够不着的余量，读者滚到那里只觉得「卡住了」，而界在哪里也说不清。
    if (next > ZOOM_MAX * ref) k = ZOOM_MAX * ref / now;
    else if (next < ZOOM_MIN * ref) k = ZOOM_MIN * ref / now;
    //: 削完之后方向若反了（说明已经贴着界，甚至在界外），这一步就不动——不能借着
    //: 「夹住」把读者往回推，那是另一件事。
    return (out ? k > 1 : k < 1) ? k : 0;
  }

  function attachPanZoom(canvas) {
    if (canvas.__fyPanZoom) return;
    canvas.__fyPanZoom = true;
    var drag = null;
    var redraw = function () {
      if (canvas.__fyOpts) poloidal(canvas, canvas.__fyOpts);
    };
    canvas.addEventListener('wheel', function (ev) {
      var v = canvas.__fyZoom || canvas.__fyBaseView;
      if (!v) return;
      ev.preventDefault();
      var rect = canvas.getBoundingClientRect();
      var fx = (ev.clientX - rect.left) / Math.max(1, rect.width);
      var fy = (ev.clientY - rect.top) / Math.max(1, rect.height);
      //: 以指针所在处为不动点缩放——否则读者要一边滚一边追着目标平移
      //: ★方向：滚轮向上（`deltaY < 0`）**放大**，即视野变窄。写反了会让「放大」把
      //: 图缩小，实测第一版就是反的。
      var k = Math.exp((ev.deltaY > 0 ? 1 : -1) * 0.18);
      k = zoomFactor(canvas, v, k);
      if (!k) return;
      var rw = (v.rmax - v.rmin) * k, zw = (v.zmax - v.zmin) * k;
      var rAt = v.rmin + (v.rmax - v.rmin) * fx;
      var zAt = v.zmax - (v.zmax - v.zmin) * fy;
      canvas.__fyZoom = { rmin: rAt - rw * fx, rmax: rAt + rw * (1 - fx),
                          zmin: zAt - zw * (1 - fy), zmax: zAt + zw * fy };
      redraw();
    }, { passive: false });
    canvas.addEventListener('pointerdown', function (ev) {
      if (canvas.hasPointerCapture && canvas.hasPointerCapture(ev.pointerId)) return;
      var v = canvas.__fyZoom || canvas.__fyBaseView;
      if (!v) return;
      drag = { x: ev.clientX, y: ev.clientY, v: v, id: ev.pointerId, moved: false };
    });
    canvas.addEventListener('pointermove', function (ev) {
      if (!drag || ev.pointerId !== drag.id) return;
      if (canvas.hasPointerCapture && canvas.hasPointerCapture(ev.pointerId)) { drag = null; return; }
      var rect = canvas.getBoundingClientRect();
      var dr = (ev.clientX - drag.x) / Math.max(1, rect.width) * (drag.v.rmax - drag.v.rmin);
      var dz = (ev.clientY - drag.y) / Math.max(1, rect.height) * (drag.v.zmax - drag.v.zmin);
      if (!drag.moved && Math.abs(ev.clientX - drag.x) + Math.abs(ev.clientY - drag.y) < 3) return;
      drag.moved = true;
      canvas.__fyZoom = { rmin: drag.v.rmin - dr, rmax: drag.v.rmax - dr,
                          zmin: drag.v.zmin + dz, zmax: drag.v.zmax + dz };
      redraw();
    });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (t) {
      canvas.addEventListener(t, function () { drag = null; });
    });
    //: ★回到默认：一步，且不必知道默认是什么
    canvas.addEventListener('dblclick', function () {
      canvas.__fyZoom = null; redraw();
    });
  }

  /**
   * 画布还没有布局盒时**不画**，等它有了再画。
   *
   * ★★折叠或未选中的功能栏，其画布的盒是 0×0——`prepare()` 会把背衬钉成 1×1，然后
   * 整幅图（等值线追踪、线圈、边界）朝一个 1 像素的缓冲画一遍：白做，而且一旦面板被
   * 显示出来而没人重画，读者看到的是一张按 1×1 拉伸的糊图。
   * ★用 `ResizeObserver` 而不是「显示时记得重画」：后者要求每一个显示面板的地方都记得
   * 调一次，而那种「记得」正是本仓一再修掉的东西。它同时把**窗口缩放**也一并管了——
   * 此前改窗口大小，图要等下一次重画才跟上。
   */
  function redrawWhenSized(canvas) {
    if (canvas.__fyRO || typeof ResizeObserver !== 'function') return;
    canvas.__fyRO = new ResizeObserver(function (entries) {
      var r = entries[0] && entries[0].contentRect;
      if (!r || r.width < 2 || r.height < 2) return;
      if (canvas.__fyOpts) poloidal(canvas, canvas.__fyOpts);
    });
    try { canvas.__fyRO.observe(canvas); } catch (e) { /* 观察不了就照旧 */ }
  }

  //: ★★**画什么、图例写什么，只能有一份规则**（2026-09-08）。超差段的判据是
  //: 「两端都超」，于是「max > tol」并不等于「图上真有红段」（孤点超差画不出东西）。
  //: 页面要决定要不要给图例条目，就得问同一个函数，而不是在那边再写一遍这条规则——
  //: 两处各写一遍，就会有一天图上没红段而图例说有（反之亦然），而那种不一致没人会报。
  var GAP_WIDTH = 4.5;
  function gapSegments(pts, tol) {
    var out = [], n = pts.length / 3;
    if (!(n > 1) || !isFinite(tol)) return out;
    for (var i = 0; i < n; i++) {
      var j = (i + 1) % n;
      if (pts[3 * i + 2] > tol && pts[3 * j + 2] > tol) out.push([i, j]);
    }
    return out;
  }

  //: ★★**夹取管住了画法，视野就得管住内容**（2026-09-08 实测）。同一天加的两条：
  //: 「框外不画」和「缺省框＝平衡计算网格盒」。两条各自都对，合起来却会**静默吞掉
  //: 被点名要画的东西**——ITER 的磁通环有 110 个，其中 **71 个在网格盒外**（环装在
  //: 器壁与线圈之间，网格盒只框到器壁），于是反演页画了、也被夹掉了，图上一个不见，
  //: 而没有任何一句提示说少了什么。那页要看的正是「哪个环残差大」。
  //: ★所以缺省视野从网格盒起，再**长到装得下调用方点名要画的诊断**（磁通环、视线）。
  //: 不含线圈：线圈是背景，没被点名，撑大视野只会把等离子体压小——那正是这次要改掉
  //: 的毛病。
  //: ★调用方显式给了 `view` 就照它的办：那是一次明确的选择（例如「视野含全部 PF 线圈」）。
  function contentView(o, M) {
    var b = { rmin: M.grid.rmin, rmax: M.grid.rmax,
              zmin: M.grid.zmin, zmax: M.grid.zmax }, grew = false;
    function eat(r, z) {
      if (!isFinite(r) || !isFinite(z)) return;
      if (r < b.rmin) { b.rmin = r; grew = true; }
      if (r > b.rmax) { b.rmax = r; grew = true; }
      if (z < b.zmin) { b.zmin = z; grew = true; }
      if (z > b.zmax) { b.zmax = z; grew = true; }
    }
    //: 只认**这里真的画出来的**那几样。磁探针不在其列（本图不画它们），为不画的东西
    //: 撑大视野，等于把等离子体压小去迁就一个看不见的点。
    if (o.loops) o.loops.forEach(function (l) { eat(l[0], l[1]); });
    if (o.chords) o.chords.forEach(function (c) { eat(c.r0, c.z0); eat(c.r1, c.z1); });
    if (!grew) return M.grid;   //: 恰好等于网格盒时交回它本身，那圈点线框就不会重复画
    var m = 0.04 * Math.max(b.rmax - b.rmin, b.zmax - b.zmin);
    return { rmin: Math.max(0.02, b.rmin - m), rmax: b.rmax + m,
             zmin: b.zmin - m, zmax: b.zmax + m };
  }

  function poloidal(canvas, o) {
    var box = canvas.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) {
      //: 记下要画什么，等有了盒子再画（见上）
      canvas.__fyOpts = o;
      redrawWhenSized(canvas);
      return null;
    }
    redrawWhenSized(canvas);
    var p = prepare(canvas), ctx = p.ctx, col = palette(canvas);
    var M = o.machine;
    var pad = { l: 42, r: 12, t: 10, b: 30 };
    //: ★交互后的视图优先；`__fyBaseView` 记下调用方的默认，供「回到默认」与缩放起点用
    canvas.__fyOpts = o;
    //: ★★**缩放状态与坐标变换是两样东西**（2026-09-08 实测）。这里原先把交互后的视野
    //: 也叫 `__fyView`——而那个名字**早就有主**：每次画完，本函数会把这张图的坐标变换
    //: （`X/Y/rOf/zOf` + 边界）写在 `canvas.__fyView` 上，页面靠它把指针位置换回 (R, Z)。
    //: 于是第一次画完之后「读者缩放过」就永远为真，调用方再换视野也被压住：实测勾上
    //: 「视野含全部 PF 线圈」后 `__fyBaseView` 已经变成 1.23–12.44 m，画出来的仍是
    //: 3.89–8.44 m 的那一张，两张截图逐字节相同。缩放本身看不出毛病，因为变换对象恰好
    //: 也带着同名的 rmin..zmax，自己喂自己刚好自洽。
    var base = o.view || contentView(o, M);
    //: ★调用方换了缺省视野（换了取景方式），先前的缩放就作废——那是对旧取景的操作，
    //: 留着它等于把新选择吞掉。
    if (!sameBox(base, canvas.__fyBaseView)) canvas.__fyZoom = null;
    canvas.__fyBaseView = base;
    attachPanZoom(canvas);
    var view = canvas.__fyZoom || base;
    var rmin = view.rmin, rmax = view.rmax,
        zmin = view.zmin, zmax = view.zmax;
    var aw = p.w - pad.l - pad.r, ah = p.h - pad.t - pad.b;
    // keep the aspect ratio true — a tokamak cross-section that is not
    // isometric misreads elongation, the quantity these pages are about
    var s = Math.min(aw / (rmax - rmin), ah / (zmax - zmin));
    var ox = pad.l + (aw - s * (rmax - rmin)) / 2,
        oy = pad.t + (ah - s * (zmax - zmin)) / 2;
    var X = function (r) { return ox + (r - rmin) * s; };
    var Y = function (z) { return oy + (zmax - z) * s; };

    ctx.fillStyle = col.bg;
    ctx.fillRect(0, 0, p.w, p.h);

    // frame + ticks
    ctx.strokeStyle = col.grid; ctx.lineWidth = 1;
    ctx.strokeRect(X(rmin), Y(zmax), s * (rmax - rmin), s * (zmax - zmin));
    if (view !== M.grid) {
      // the computational box, when it is not the whole picture
      ctx.setLineDash([2, 4]);
      ctx.strokeRect(X(M.grid.rmin), Y(M.grid.zmax),
                     s * (M.grid.rmax - M.grid.rmin),
                     s * (M.grid.zmax - M.grid.zmin));
      ctx.setLineDash([]);
    }
    ctx.fillStyle = col.muted;
    ctx.font = '11px system-ui, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    // Tick spacing has to come from the PIXELS, not from the data range: a
    // step chosen for a 1.6 m wide EAST view puts twenty labels across a
    // 10 m wide ITER view and they run together into a single smear.
    var rstep = niceStep(rmax - rmin, s * (rmax - rmin), 46),
        zstep = niceStep(zmax - zmin, s * (zmax - zmin), 26);
    var dec = function (st) { return st < 0.999 ? 1 : 0; };
    for (var r = Math.ceil(rmin / rstep) * rstep; r <= rmax; r += rstep) {
      ctx.fillText(r.toFixed(dec(rstep)), X(r), Y(zmin) + 5);
      ctx.beginPath(); ctx.moveTo(X(r), Y(zmin)); ctx.lineTo(X(r), Y(zmin) - 4);
      ctx.stroke();
    }
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (var z = Math.ceil(zmin / zstep) * zstep; z <= zmax; z += zstep) {
      ctx.fillText(z.toFixed(dec(zstep)), X(rmin) - 6, Y(z));
      ctx.beginPath(); ctx.moveTo(X(rmin), Y(z)); ctx.lineTo(X(rmin) + 4, Y(z));
      ctx.stroke();
    }
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    ctx.fillText('R [m]', (X(rmin) + X(rmax)) / 2, p.h - 14);

    //: ★★**框外不画**（2026-09-08 实测）。视野由 `deviceView`（网格 + PF 线圈）定，而
    //: 画的东西不止这些：真空室 / 被动结构可以远在视野之外——ITER 的低温恒温器顶底盖
    //: 在轴对称描述里一直伸到 **R = 0**，最长一段 19 m，于是它们被画在坐标框外面，
    //: 图上多出一堆没有坐标可依的灰条。
    //: ★修在**这里**而不是在每一处画法里：视野与画什么本来就该分开，一处夹取管住
    //: 所有元件——今天的、以及以后加进来的。框、刻度与标签在夹取之外画（它们本来就
    //: 该压在边上）。
    ctx.save();
    ctx.beginPath();
    ctx.rect(X(rmin), Y(zmax), s * (rmax - rmin), s * (zmax - zmin));
    ctx.clip();

    // Vessel: some decks give it as discrete rectangular elements (EAST),
    // others as closed polylines (ITER's annular inner/outer walls).  Both
    // are decoration — no vessel current enters any solve.
    ctx.globalAlpha = 0.45;
    //: a caller may be analysing a MOVED vessel (wall-proximity sweeps);
    //: drawing the descriptor's copy would put the picture and the number
    //: in disagreement with nothing to say so
    var vessel = o.vesselOverride || M.vessel;
    if (vessel && vessel.length) {
      ctx.fillStyle = col.wall;
      vessel.forEach(function (v) {
        ctx.fillRect(X(v.r - v.w / 2), Y(v.z + v.h / 2),
                     Math.max(1.5, s * v.w), Math.max(1.5, s * v.h));
      });
    }
    if (M.vesselOutline && M.vesselOutline.length) {
      ctx.strokeStyle = col.wall;
      ctx.lineWidth = 1;
      M.vesselOutline.forEach(function (o) {
        ctx.beginPath();
        for (var vi = 0; vi < o.r.length; vi++) {
          var vx = X(o.r[vi]), vy = Y(o.z[vi]);
          if (vi === 0) ctx.moveTo(vx, vy); else ctx.lineTo(vx, vy);
        }
        ctx.closePath();
        ctx.stroke();
      });
    }
    ctx.globalAlpha = 1;
    // PF coils (only those inside the drawn box get a label)
    ctx.strokeStyle = col.coil; ctx.lineWidth = 1.2;
    ctx.fillStyle = col.coil;
    M.coils.forEach(function (c, k2) {
      var x0 = X(c.r - c.w / 2), y0 = Y(c.z + c.h / 2);
      var cw = s * c.w, ch = s * c.h;
      if (x0 + cw < X(rmin) || x0 > X(rmax)) return;
      // fill carries the current: hue = sign, opacity = |I| / max|I|
      var f = o.coilFill ? o.coilFill(k2) : null;
      ctx.fillStyle = f ? f.color : col.coil;
      ctx.globalAlpha = f ? f.alpha : 0.25;
      ctx.fillRect(x0, y0, cw, ch);
      ctx.globalAlpha = 1;
      ctx.strokeStyle = col.coil; ctx.lineWidth = 1.2;
      ctx.strokeRect(x0, y0, cw, ch);
      if (!o.coilLabel) return;
      var txt = o.coilLabel(k2);
      if (!txt) return;
      // name centred ON the element; most elements are narrower than their
      // own name, so it gets a chip and is allowed to overhang
      ctx.font = '9px system-ui, sans-serif';
      ctx.textBaseline = 'middle';
      ctx.textAlign = 'center';
      var lx = x0 + cw / 2, ly = y0 + ch / 2, tw = ctx.measureText(txt).width;
      ctx.globalAlpha = 0.72;
      ctx.fillStyle = col.bg;
      ctx.fillRect(lx - tw / 2 - 2, ly - 6, tw + 4, 12);
      ctx.globalAlpha = 1;
      ctx.fillStyle = col.fg;
      ctx.fillText(txt, lx, ly);
    });

    // flux contours
    if (o.psi && o.nLevels) {
      ctx.lineWidth = 0.8;
      ctx.strokeStyle = col.flux;
      var a = o.psiAxis, b = o.psiBnd, k;
      //: ★The kernel computes these and they travel with the solve.  There
      //: is no local fallback: every caller that draws a psi field has a
      //: worker behind it, and the one path that does not (an imported
      //: g-file) needs shape metrics, never contours — checked, not assumed.
      //: A caller that asks for levels without bringing segments is a wiring
      //: mistake, and silently drawing nothing would hide it.
      if (!o.fluxSegs)
        throw new Error('FyPlot.poloidal: nLevels given without fluxSegs');
      var f = o.fluxSegs;
      for (k = 0; k < f.inner.length && k < o.nLevels; k++)
        drawSegs(ctx, f.inner[k], X, Y);
      ctx.setLineDash([2, 3]);
      for (k = 0; k < f.outer.length; k++) drawSegs(ctx, f.outer[k], X, Y);
      ctx.setLineDash([]);
    }

    // limiter
    ctx.strokeStyle = col.wall; ctx.lineWidth = 1.6;
    ctx.beginPath();
    M.limiter.r.forEach(function (rr, i) {
      var fn = i ? 'lineTo' : 'moveTo';
      ctx[fn](X(rr), Y(M.limiter.z[i]));
    });
    ctx.closePath(); ctx.stroke();

    // reference / target outlines
    if (o.reference) {
      ctx.strokeStyle = col.alt; ctx.lineWidth = 1.6;
      ctx.setLineDash([5, 3]);
      polyline(ctx, o.reference, X, Y, true);
      ctx.setLineDash([]);
    }
    if (o.target) {
      ctx.strokeStyle = col.accent; ctx.lineWidth = 1.4;
      ctx.setLineDash([4, 4]);
      polyline(ctx, o.target, X, Y, true);
      ctx.setLineDash([]);
    }
    //: ★★**判据落在图上**（2026-09-08）：把**超出容差的那几段**边界标出来。
    //: 数据是内核逐点报的距离（`boundary_gap_point`，[r, z, d] × n，量在分离面上），
    //: 容差是页面判「达到目标」用的同一个数（3 % 小半径）——所以图上被标红的，正是
    //: 结论行说未达标的那部分，两者不会各说各话。
    //: ★**二态，不做彩色渐变**：渐变会造出一种并不存在的精度（读者会去比较两段的颜色
    //: 深浅），而这里真正要回答的是「哪几段没达到」。超差多少由结论行的 RMS / 最大值
    //: 说，那是数字该干的活。
    if (o.gapMarks && o.gapMarks.pts && o.gapMarks.pts.length) {
      var gp = o.gapMarks.pts, segs = gapSegments(gp, o.gapMarks.tol);
      ctx.strokeStyle = col.lcfs; ctx.lineWidth = GAP_WIDTH;
      ctx.lineCap = 'round';
      for (var gi = 0; gi < segs.length; gi++) {
        var i0 = 3 * segs[gi][0], i1 = 3 * segs[gi][1];
        ctx.beginPath();
        ctx.moveTo(X(gp[i0]), Y(gp[i0 + 1]));
        ctx.lineTo(X(gp[i1]), Y(gp[i1 + 1]));
        ctx.stroke();
      }
      ctx.lineWidth = 1; ctx.lineCap = 'butt';
    }
    // last closed flux surface
    if (o.lcfs && o.lcfs.length) {
      ctx.strokeStyle = col.lcfs; ctx.lineWidth = 2;
      polyline(ctx, o.lcfs, X, Y, true);
    }
    //: ★★SIGHT LINES, drawn where they look.  A chord diagnostic is the one
    //: measurement whose GEOMETRY is the physics — which flux surfaces it
    //: crosses is the whole content of `∫n_e dl` — and a page that reported
    //: eleven numbers without showing where the eleven beams go asks the
    //: reader to hold the machine in their head.  Drawn under the markers
    //: and over the flux map, in the deck's own coordinates, and clipped to
    //: the view like everything else.
    if (o.chords && o.chords.length) {
      ctx.save();
      ctx.lineWidth = 1.2;
      ctx.strokeStyle = o.chordColor || col.accent;
      o.chords.forEach(function (c) {
        ctx.globalAlpha = c.weight === 0 ? 0.28 : 0.85;
        if (c.weight === 0) ctx.setLineDash([3, 3]); else ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(X(c.r0), Y(c.z0));
        ctx.lineTo(X(c.r1), Y(c.z1));
        ctx.stroke();
      });
      ctx.restore();
    }
    // flux loops, drawn as squares: filled = fitted, hollow = weight zero
    if (o.loops) {
      ctx.lineWidth = 1.2;
      o.loops.forEach(function (l, i) {
        var s2 = 3, cx = X(l[0]), cy = Y(l[1]);
        var c = o.loopColor ? o.loopColor(i) : col.muted;
        var used = o.loopUsed ? o.loopUsed(i) : true;
        if (used) { ctx.fillStyle = c; ctx.fillRect(cx - s2, cy - s2, 2 * s2, 2 * s2); }
        else { ctx.strokeStyle = c; ctx.strokeRect(cx - s2, cy - s2, 2 * s2, 2 * s2); }
      });
    }
    ctx.restore();   //: 夹取到此为止——磁轴标记、X 点、图例与说明画在框上，见上面那段
    // axis + X point
    // a circle in machine coordinates — the region a criterion is stated
    // over, drawn where the criterion applies rather than described in prose
    if (o.circle) {
      ctx.strokeStyle = col.accent; ctx.lineWidth = 1.4;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      //: ★clamped: on a canvas with no layout yet (a result panel still
      //: folded), the fitted scale `s` goes negative and `arc` THROWS on a
      //: negative radius — which aborts the caller mid-draw and, measured on
      //: the breakdown bar, left its busy latch stuck on the first solve.
      //: Every other primitive here just draws nowhere at negative scale;
      //: this one has to be told to.
      ctx.arc(X(o.circle.r), Y(o.circle.z),
              Math.max(0, s * o.circle.radius), 0, 2 * Math.PI);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    if (o.axis) marker(ctx, X(o.axis[0]), Y(o.axis[1]), col.fg, '+');
    if (o.xpoint && isFinite(o.xpoint[0]))
      marker(ctx, X(o.xpoint[0]), Y(o.xpoint[1]), col.lcfs, 'x');

    if (o.caption) {
      ctx.fillStyle = col.muted;
      ctx.font = '11px system-ui, sans-serif';
      ctx.textAlign = 'left'; ctx.textBaseline = 'top';
      ctx.fillText(o.caption, X(rmin) + 6, Y(zmax) + 6);
    }
    // draggable handles, drawn last so they sit above everything
    if (o.handles) o.handles.forEach(function (h) {
      drawHandle(ctx, X(h.r), Y(h.z), h.kind, h.color || col.accent, col);
    });

    if (o.legend && o.legend.length) {
      // anchoring to the view corner collides with the outer coils' current
      // labels in the wide device view, so callers may anchor it elsewhere
      var la = o.legendAnchor;
      drawLegend(ctx, o.legend, la ? X(la.r) : X(rmax), la ? Y(la.z) : Y(zmax),
                 col);
    }

    // the page needs to turn pointer positions back into (R, Z) — publish
    // the transform rather than have callers re-derive the letterboxing
    canvas.__fyView = {
      X: X, Y: Y,
      rOf: function (px) { return rmin + (px - ox) / s; },
      zOf: function (py) { return zmax - (py - oy) / s; },
      rmin: rmin, rmax: rmax, zmin: zmin, zmax: zmax, scale: s,
    };
  }

  /** A grab handle: ring plus glyph, sized to be an obvious pointer target. */
  function drawHandle(ctx, x, y, kind, color, col) {
    ctx.beginPath();
    ctx.arc(x, y, 8, 0, 2 * Math.PI);
    ctx.fillStyle = col.bg; ctx.globalAlpha = 0.75; ctx.fill(); ctx.globalAlpha = 1;
    ctx.strokeStyle = color; ctx.lineWidth = 1.6; ctx.stroke();
    marker(ctx, x, y, color, kind === 'x' ? 'x' : '+');
  }

  /** Small legend box anchored to the top-right of the plot frame. */
  function drawLegend(ctx, items, right, top, col) {
    ctx.font = '11px system-ui, sans-serif';
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    var wLab = 0;
    items.forEach(function (it) {
      wLab = Math.max(wLab, ctx.measureText(it.label).width);
    });
    var pad = 6, sw = 20, bw = pad * 2 + sw + 6 + wLab, bh = items.length * 15 + 8;
    var bx = right - bw - 6, by = top + 6;
    ctx.globalAlpha = 0.88;
    ctx.fillStyle = col.bg;
    ctx.fillRect(bx, by, bw, bh);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = col.grid; ctx.lineWidth = 1;
    ctx.strokeRect(bx, by, bw, bh);
    var y = by + 11;
    items.forEach(function (it) {
      var x = bx + pad;
      ctx.strokeStyle = it.color; ctx.fillStyle = it.color;
      ctx.lineWidth = it.width || 2;
      if (it.kind === 'square') {
        if (it.hollow) ctx.strokeRect(x + sw / 2 - 3, y - 3, 6, 6);
        else ctx.fillRect(x + sw / 2 - 3, y - 3, 6, 6);
      } else if (it.kind === 'plus' || it.kind === 'x') {
        marker(ctx, x + sw / 2, y, it.color, it.kind === 'plus' ? '+' : 'x');
      } else {
        ctx.setLineDash(it.dash || []);
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + sw, y); ctx.stroke();
        ctx.setLineDash([]);
      }
      ctx.fillStyle = col.fg;
      ctx.fillText(it.label, x + sw + 6, y);
      y += 15;
    });
  }

  function drawSegs(ctx, segs, X, Y) {
    ctx.beginPath();
    for (var i = 0; i < segs.length; i += 4) {
      ctx.moveTo(X(segs[i]), Y(segs[i + 1]));
      ctx.lineTo(X(segs[i + 2]), Y(segs[i + 3]));
    }
    ctx.stroke();
  }

  function polyline(ctx, flat, X, Y, close) {
    if (!flat.length) return;
    ctx.beginPath();
    for (var i = 0; i < flat.length; i += 2) {
      var fn = i ? 'lineTo' : 'moveTo';
      ctx[fn](X(flat[i]), Y(flat[i + 1]));
    }
    if (close) ctx.closePath();
    ctx.stroke();
  }

  function marker(ctx, x, y, color, kind) {
    ctx.strokeStyle = color; ctx.lineWidth = 1.8;
    ctx.beginPath();
    if (kind === '+') {
      ctx.moveTo(x - 5, y); ctx.lineTo(x + 5, y);
      ctx.moveTo(x, y - 5); ctx.lineTo(x, y + 5);
    } else {
      ctx.moveTo(x - 4, y - 4); ctx.lineTo(x + 4, y + 4);
      ctx.moveTo(x + 4, y - 4); ctx.lineTo(x - 4, y + 4);
    }
    ctx.stroke();
  }

  // --- XY line plot ---------------------------------------------------------

  /**
   * opts: {series: [{x, y, color, dash, label, kind:'line'|'dots'|'bars'}],
   *        xlabel, ylabel, ymin, ymax, xmin, xmax, zeroLine}
   */
  function xy(canvas, o) {
    var p = prepare(canvas), ctx = p.ctx, col = palette(canvas);
    var pad = { l: 54, r: 10, t: 12, b: 30 };
    var xmin = o.xmin, xmax = o.xmax, ymin = o.ymin, ymax = o.ymax;
    o.series.forEach(function (s) {
      for (var i = 0; i < s.x.length; i++) {
        if (!isFinite(s.x[i])) continue;
        //: an envelope carries two y arrays and no `y`; both edges have to
        //: be inside the frame or the band is drawn clipped and reads as a
        //: narrower uncertainty than it is
        var ys = s.kind === 'envelope' ? [s.yLo[i], s.yHi[i]] : [s.y[i]];
        if (xmin === undefined || s.x[i] < xmin) xmin = s.x[i];
        if (xmax === undefined || s.x[i] > xmax) xmax = s.x[i];
        for (var k = 0; k < ys.length; k++) {
          if (!isFinite(ys[k])) continue;
          if (ymin === undefined || ys[k] < ymin) ymin = ys[k];
          if (ymax === undefined || ys[k] > ymax) ymax = ys[k];
        }
      }
    });
    // A threshold you cannot see is not a threshold: make room for it.
    if (o.hline !== undefined && isFinite(o.hline)) {
      if (ymin === undefined || o.hline < ymin) ymin = o.hline;
      if (ymax === undefined || o.hline > ymax) ymax = o.hline;
    }
    if (!(xmax > xmin)) { xmin -= 1; xmax += 1; }
    if (!(ymax > ymin)) { ymin -= 1; ymax += 1; }
    var m = 0.06 * (ymax - ymin);
    ymin -= m; ymax += m;
    // the left margin has to clear the widest tick label AND the rotated
    // axis title; a fixed margin puts "5.6e+5" straight through the title
    ctx.font = '11px system-ui, sans-serif';
    var tickW = 0;
    for (var tk = 0; tk <= 4; tk++)
      tickW = Math.max(tickW, ctx.measureText(fmt(ymin + (ymax - ymin) * tk / 4)).width);
    pad.l = Math.max(pad.l, Math.ceil(tickW) + (o.ylabel ? 24 : 10));
    var X = function (v) { return pad.l + (v - xmin) / (xmax - xmin) * (p.w - pad.l - pad.r); };
    var Y = function (v) { return p.h - pad.b - (v - ymin) / (ymax - ymin) * (p.h - pad.t - pad.b); };
    //: ★★THE INVERSE MAPPING, LEFT ON THE CANVAS.  A figure a reader can
    //: only look at is half a figure: the first thing anyone does with a
    //: time trace is point at a moment and ask to see it.  The page cannot
    //: work out where the axes are — the padding, the nice-step rounding and
    //: the auto range all live in here — so the plot leaves behind what it
    //: alone knows.  `toData` is CSS pixels relative to the canvas, which is
    //: what a click event gives.
    canvas.fyxy = {
      xmin: xmin, xmax: xmax, ymin: ymin, ymax: ymax,
      //: ★the plot box in CSS pixels, and the FORWARD map beside the inverse
      //: one.  A caller that can turn a click into a value but not a value
      //: into a position can read the figure and not annotate it — which is
      //: half of what「把光标停在 t = 3.20 s」needs (`FYL-DESIGN-18` U-17).
      //: `prepare()` leaves the context scaled by the device pixel ratio, so
      //: these are the coordinates a caller draws in.
      box: { l: pad.l, r: p.w - pad.r, t: pad.t, b: p.h - pad.b },
      toPixel: function (x, y) {
        var w = p.w - pad.l - pad.r, h = p.h - pad.t - pad.b;
        return { px: pad.l + (x - xmin) / ((xmax - xmin) || 1) * w,
                 py: p.h - pad.b - (y - ymin) / ((ymax - ymin) || 1) * h };
      },
      toData: function (px, py) {
        var w = p.w - pad.l - pad.r, h = p.h - pad.t - pad.b;
        return { x: xmin + (px - pad.l) / (w || 1) * (xmax - xmin),
                 y: ymin + (p.h - pad.b - py) / (h || 1) * (ymax - ymin),
                 inside: px >= pad.l && px <= p.w - pad.r &&
                         py >= pad.t && py <= p.h - pad.b };
      },
    };

    ctx.fillStyle = col.bg; ctx.fillRect(0, 0, p.w, p.h);

    // Bands go down first, under everything: they are context, not data.
    // `o.bands = [{x0, x1, color, label}]` — an x interval and a colour, the
    // smallest primitive that says "this stretch of time is the ramp".
    if (o.bands) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(pad.l, pad.t, p.w - pad.l - pad.r, p.h - pad.t - pad.b);
      ctx.clip();
      o.bands.forEach(function (b) {
        var x0 = X(Math.max(b.x0, xmin)), x1 = X(Math.min(b.x1, xmax));
        if (!(x1 > x0)) return;
        ctx.globalAlpha = 0.10;
        ctx.fillStyle = b.color || col.muted;
        ctx.fillRect(x0, pad.t, x1 - x0, p.h - pad.t - pad.b);
        ctx.globalAlpha = 1;
        if (b.label) {
          ctx.fillStyle = col.muted;
          ctx.font = '10px system-ui, sans-serif';
          ctx.textAlign = 'center'; ctx.textBaseline = 'top';
          ctx.fillText(b.label, (x0 + x1) / 2, pad.t + 2);
        }
      });
      ctx.restore();
    }
    // a marked instant — the slice the profiles below belong to
    if (o.marker !== undefined && isFinite(o.marker)) {
      ctx.save();
      ctx.strokeStyle = col.accent; ctx.lineWidth = 1.2;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(X(o.marker), pad.t); ctx.lineTo(X(o.marker), p.h - pad.b);
      ctx.stroke();
      ctx.restore();
    }
    // a horizontal reference level — a threshold belongs on the plot, not
    // only in the caption
    if (o.hline !== undefined && isFinite(o.hline) &&
        o.hline >= ymin && o.hline <= ymax) {
      ctx.save();
      ctx.strokeStyle = col.warn || col.accent; ctx.lineWidth = 1.2;
      ctx.setLineDash([6, 3]);
      ctx.beginPath();
      ctx.moveTo(pad.l, Y(o.hline)); ctx.lineTo(p.w - pad.r, Y(o.hline));
      ctx.stroke();
      ctx.restore();
    }
    ctx.strokeStyle = col.grid; ctx.lineWidth = 1;
    ctx.strokeRect(pad.l, pad.t, p.w - pad.l - pad.r, p.h - pad.t - pad.b);
    ctx.fillStyle = col.muted; ctx.font = '11px system-ui, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (var k = 0; k <= 4; k++) {
      var xv = xmin + (xmax - xmin) * k / 4;
      ctx.fillText(fmt(xv), X(xv), p.h - pad.b + 5);
      if (k && k < 4) {
        ctx.beginPath(); ctx.moveTo(X(xv), pad.t); ctx.lineTo(X(xv), p.h - pad.b);
        ctx.globalAlpha = 0.4; ctx.stroke(); ctx.globalAlpha = 1;
      }
    }
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    for (k = 0; k <= 4; k++) {
      var yv = ymin + (ymax - ymin) * k / 4;
      ctx.fillText(fmt(yv), pad.l - 6, Y(yv));
      if (k && k < 4) {
        ctx.beginPath(); ctx.moveTo(pad.l, Y(yv)); ctx.lineTo(p.w - pad.r, Y(yv));
        ctx.globalAlpha = 0.4; ctx.stroke(); ctx.globalAlpha = 1;
      }
    }
    if (o.zeroLine && ymin < 0 && ymax > 0) {
      ctx.strokeStyle = col.muted; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(pad.l, Y(0)); ctx.lineTo(p.w - pad.r, Y(0));
      ctx.stroke(); ctx.setLineDash([]);
    }
    if (o.xlabel) {
      ctx.fillStyle = col.muted; ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
      ctx.fillText(o.xlabel, (pad.l + p.w - pad.r) / 2, p.h - 2);
    }
    if (o.ylabel) {
      ctx.save(); ctx.translate(11, (pad.t + p.h - pad.b) / 2); ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(o.ylabel, 0, 0); ctx.restore();
    }

    // ★Envelopes go under every line, whatever order the caller listed them
    // in: a +-1 sigma band painted over its own mean hides the quantity it
    // is the uncertainty OF.
    o.series.forEach(function (s) {
      if (s.kind !== 'envelope') return;
      ctx.save();
      ctx.beginPath();
      var started = false, i;
      for (i = 0; i < s.x.length; i++) {
        if (!isFinite(s.yHi[i])) continue;
        if (!started) { ctx.moveTo(X(s.x[i]), Y(s.yHi[i])); started = true; }
        else ctx.lineTo(X(s.x[i]), Y(s.yHi[i]));
      }
      for (i = s.x.length - 1; i >= 0; i--) {
        if (!isFinite(s.yLo[i])) continue;
        ctx.lineTo(X(s.x[i]), Y(s.yLo[i]));
      }
      ctx.closePath();
      ctx.globalAlpha = s.alpha === undefined ? 0.22 : s.alpha;
      ctx.fillStyle = s.color;
      ctx.fill();
      ctx.restore();
    });

    o.series.forEach(function (s) {
      if (s.kind === 'envelope') return;
      ctx.strokeStyle = s.color; ctx.fillStyle = s.color;
      ctx.lineWidth = s.width || 1.8;
      ctx.setLineDash(s.dash || []);
      if (s.kind === 'dots') {
        for (var i = 0; i < s.x.length; i++) {
          if (!isFinite(s.y[i])) continue;
          ctx.beginPath();
          ctx.arc(X(s.x[i]), Y(s.y[i]), s.radius || 3, 0, 2 * Math.PI);
          ctx.fill();
        }
      } else if (s.kind === 'stems') {
        //: ★A RESIDUAL IS A STEM, NEVER A POLYLINE (`FYL-DESIGN-12` · U-21):
        //: the abscissa is a channel index, and joining channel 3 to
        //: channel 4 draws a slope between two things that have no
        //: neighbourhood.  Line from the zero line, dot at the tip.
        var yz = Y(Math.max(ymin, Math.min(ymax, 0)));
        ctx.lineWidth = s.width || 1.4;
        for (i = 0; i < s.x.length; i++) {
          if (!isFinite(s.y[i])) continue;
          ctx.beginPath();
          ctx.moveTo(X(s.x[i]), yz); ctx.lineTo(X(s.x[i]), Y(s.y[i]));
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(X(s.x[i]), Y(s.y[i]), s.radius || 2.4, 0, 2 * Math.PI);
          ctx.fill();
        }
      } else if (s.kind === 'bars') {
        var bw = Math.max(2, (p.w - pad.l - pad.r) / (s.x.length * 1.7));
        for (i = 0; i < s.x.length; i++) {
          if (!isFinite(s.y[i])) continue;
          var y0 = Y(Math.max(0, Math.min(ymax, 0))), y1 = Y(s.y[i]);
          ctx.fillRect(X(s.x[i]) - bw / 2, Math.min(y0, y1), bw, Math.abs(y1 - y0));
        }
      } else {
        ctx.beginPath();
        var started = false;
        for (i = 0; i < s.x.length; i++) {
          if (!isFinite(s.y[i])) { started = false; continue; }
          if (!started) { ctx.moveTo(X(s.x[i]), Y(s.y[i])); started = true; }
          else ctx.lineTo(X(s.x[i]), Y(s.y[i]));
        }
        ctx.stroke();
      }
      ctx.setLineDash([]);
    });

    // legend
    var labels = o.series.filter(function (s) { return s.label; });
    if (labels.length) {
      ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
      ctx.font = '11px system-ui, sans-serif';
      var bw = 0;
      labels.forEach(function (s) {
        bw = Math.max(bw, ctx.measureText(s.label).width);
      });
      var bx = p.w - pad.r - 34 - bw, by = pad.t + 3;
      ctx.globalAlpha = 0.85;
      ctx.fillStyle = col.bg;
      ctx.fillRect(bx - 5, by, bw + 38, labels.length * 15 + 8);
      ctx.globalAlpha = 1;
      var y = pad.t + 10;
      labels.forEach(function (s) {
        if (s.kind === 'envelope') {
          //: a band's key is a band, not a line: drawn as a line it reads as
          //: one more curve, which is the thing it is not
          ctx.save();
          ctx.globalAlpha = s.alpha === undefined ? 0.22 : s.alpha;
          ctx.fillStyle = s.color;
          ctx.fillRect(bx, y - 4, 22, 8);
          ctx.restore();
        } else {
          ctx.strokeStyle = s.color; ctx.lineWidth = 2.4;
          ctx.setLineDash(s.dash || []);
          ctx.beginPath();
          ctx.moveTo(bx, y); ctx.lineTo(bx + 22, y);
          ctx.stroke(); ctx.setLineDash([]);
        }
        ctx.fillStyle = col.fg;
        ctx.fillText(s.label, bx + 28, y);
        y += 15;
      });
    }
  }

  function fmt(v) {
    var a = Math.abs(v);
    if (a === 0) return '0';
    if (a >= 1e4 || a < 1e-3) return v.toExponential(1);
    if (a >= 100) return v.toFixed(0);
    if (a >= 10) return v.toFixed(1);
    if (a >= 1) return v.toFixed(2);
    return v.toFixed(3);
  }

  /**
   * The same legend items as `o.legend`, rendered as HTML for callers that
   * want the key OUTSIDE the plot.  In a crowded view an in-canvas legend
   * has nowhere to sit that does not cover something.
   */
  function legendHTML(items) {
    return items.map(function (it) {
      var sw;
      if (it.kind === 'square')
        sw = '<i class="sw-box" style="' +
             (it.hollow ? 'border-color:' + it.color
                        : 'background:' + it.color + ';border-color:' + it.color) +
             '"></i>';
      else if (it.kind === 'plus' || it.kind === 'x')
        sw = '<i class="sw-gl" style="color:' + it.color + '">' +
             (it.kind === 'plus' ? '+' : '×') + '</i>';
      else
        sw = '<i class="sw-line" style="border-top-color:' + it.color +
             ';border-top-style:' + (it.dash ? 'dashed' : 'solid') +
             ';border-top-width:' + (it.width || 2) + 'px"></i>';
      return '<span class="lg-item">' + sw + it.label + '</span>';
    }).join('');
  }

  /**
   * Horizontal diverging scale for the coil-current colouring, drawn into
   * its own small canvas outside the figure: the numbers are in the table,
   * the figure only carries sign and relative magnitude, and without a key
   * "darker" means nothing.
   */
  function currentScale(canvas, o) {
    var p = prepare(canvas), ctx = p.ctx, col = palette(canvas);
    ctx.fillStyle = col.bg; ctx.fillRect(0, 0, p.w, p.h);
    // the unit sits to the LEFT of the bar; measure it so the bar starts
    // clear of it instead of underneath
    ctx.font = '10px system-ui, sans-serif';
    var unit = o.unit || '';
    var padL = unit ? Math.ceil(ctx.measureText(unit).width) + 12 : 30;
    var padR = 34, y = 6, bh = 12, w = p.w - padL - padR, pad = padL;
    if (w <= 10) return;
    for (var i = 0; i < w; i++) {
      var t = i / (w - 1) * 2 - 1;             // -1 .. +1
      ctx.fillStyle = t < 0 ? o.negColor : o.posColor;
      ctx.globalAlpha = 0.12 + 0.88 * Math.abs(t);
      ctx.fillRect(pad + i, y, 1, bh);
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = col.grid; ctx.lineWidth = 1;
    ctx.strokeRect(pad, y, w, bh);
    ctx.fillStyle = col.muted;
    ctx.font = '10px system-ui, sans-serif';
    ctx.textBaseline = 'top'; ctx.textAlign = 'center';
    ctx.fillText('−' + o.max, pad, y + bh + 3);
    ctx.fillText('0', pad + w / 2, y + bh + 3);
    ctx.fillText('+' + o.max, pad + w, y + bh + 3);
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    ctx.fillText(unit, 2, y + bh / 2);
  }

  /** A view box that encloses the whole machine, not just the grid. */
  function deviceView(M, margin) {
    var m = margin === undefined ? 0.1 : margin;
    var b = { rmin: M.grid.rmin, rmax: M.grid.rmax,
              zmin: M.grid.zmin, zmax: M.grid.zmax };
    M.coils.forEach(function (c) {
      b.rmin = Math.min(b.rmin, c.r - c.w / 2);
      b.rmax = Math.max(b.rmax, c.r + c.w / 2);
      b.zmin = Math.min(b.zmin, c.z - c.h / 2);
      b.zmax = Math.max(b.zmax, c.z + c.h / 2);
    });
    return { rmin: Math.max(0.02, b.rmin - m), rmax: b.rmax + m,
             zmin: b.zmin - m, zmax: b.zmax + m };
  }

  root.FyPlot = { poloidal: poloidal, xy: xy, palette: palette,
                  gapSegments: gapSegments, GAP_WIDTH: GAP_WIDTH,
                  seriesColor: seriesColor,
                  deviceView: deviceView,
                  legendHTML: legendHTML, currentScale: currentScale };
})(typeof self !== 'undefined' ? self : globalThis);
