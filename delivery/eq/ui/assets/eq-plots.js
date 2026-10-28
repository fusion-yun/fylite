/* FYLite · 结果图（EQP）
   六联图：磁面 / q / p / p' / FF' / 逐道残差
   只依赖 canvas 2d，无外部库。 */
(function (global) {
  'use strict';
  var CW = 520, CH = 330;               // CSS 像素尺寸
  var PAD = { l: 58, r: 16, t: 22, b: 40 };
  var COL = {
    ink: '#183342', axis: '#b9c9d2', grid: '#e6edf1',
    main: '#17657f', ref: '#a3741d', band: 'rgba(23,101,127,0.13)',
    ok: '#2f7d5b', warn: '#c08a2e', bad: '#a3453b', grey: '#b6c6cf'
  };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function makePanel(host, title, sub, hgt) {
    var fig = el('figure', 'eqp-fig');
    var head = el('div', 'eqp-head');
    head.appendChild(el('b', null, title));
    if (sub) head.appendChild(el('small', null, sub));
    fig.appendChild(head);
    var cv = document.createElement('canvas');
    var dpr = Math.min(global.devicePixelRatio || 1, 2);
    var HH = hgt || CH;
    cv.width = CW * dpr; cv.height = HH * dpr;
    cv.style.width = '100%'; cv.style.maxWidth = CW + 'px';
    var ctx = cv.getContext('2d');
    ctx.scale(dpr, dpr);
    fig.appendChild(cv);
    host.appendChild(fig);
    return { ctx: ctx, w: CW, h: HH, fig: fig };
  }

  function frame(ctx, xr, yr, xlab, ylab, xticks, yticks, H) {
    var W = CW; H = H || CH;
    var L = PAD.l, R = W - PAD.r, T = PAD.t, B = H - PAD.b;
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = COL.axis; ctx.lineWidth = 1;
    ctx.strokeRect(L, T, R - L, B - T);
    ctx.font = '11px ui-monospace,Consolas,monospace';
    ctx.fillStyle = '#5b7080';
    var sx = function (v) { return L + (R - L) * (v - xr[0]) / (xr[1] - xr[0] || 1); };
    var sy = function (v) { return B - (B - T) * (v - yr[0]) / (yr[1] - yr[0] || 1); };
    (yticks || []).forEach(function (v) {
      var y = sy(v);
      ctx.strokeStyle = COL.grid; ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(R, y); ctx.stroke();
      ctx.fillStyle = '#5b7080'; ctx.textAlign = 'right';
      ctx.fillText(fmt(v), L - 6, y + 4);
    });
    (xticks || []).forEach(function (v) {
      var x = sx(v);
      ctx.strokeStyle = COL.grid; ctx.beginPath(); ctx.moveTo(x, T); ctx.lineTo(x, B); ctx.stroke();
      ctx.fillStyle = '#5b7080'; ctx.textAlign = 'center';
      ctx.fillText(fmt(v), x, B + 15);
    });
    if (xlab) { ctx.fillStyle = '#526c79'; ctx.textAlign = 'center'; ctx.fillText(xlab, (L + R) / 2, H - 8); }
    if (ylab) {
      ctx.save(); ctx.translate(12, (T + B) / 2); ctx.rotate(-Math.PI / 2);
      ctx.fillStyle = '#526c79'; ctx.textAlign = 'center'; ctx.fillText(ylab, 0, 0); ctx.restore();
    }
    return { sx: sx, sy: sy, L: L, R: R, T: T, B: B };
  }

  function fmt(v) {
    if (!isFinite(v)) return '—';
    var a = Math.abs(v);
    if (a === 0) return '0';
    if (a >= 1e4) return (v / 1e3).toFixed(0) + 'k';
    if (a >= 100) return v.toFixed(0);
    if (a >= 10) return v.toFixed(1);
    if (a >= 1) return v.toFixed(2);
    return v.toPrecision(2);
  }

  function ticks(min, max, n) {
    var out = [], i;
    for (i = 0; i <= n; i++) out.push(min + (max - min) * i / n);
    return out;
  }

  function line(ctx, xs, ys, g, color, width) {
    if (!xs || !ys || !xs.length) return;
    ctx.strokeStyle = color; ctx.lineWidth = width || 1.8; ctx.beginPath();
    for (var i = 0; i < xs.length; i++) {
      var x = g.sx(xs[i]), y = g.sy(ys[i]);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  function band(ctx, xs, lo, hi, g, fill) {
    if (!xs || !lo || !hi) return;
    ctx.fillStyle = fill || COL.band; ctx.beginPath();
    for (var i = 0; i < xs.length; i++) {
      var x = g.sx(xs[i]), y = g.sy(hi[i]);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    for (var j = xs.length - 1; j >= 0; j--) ctx.lineTo(g.sx(xs[j]), g.sy(lo[j]));
    ctx.closePath(); ctx.fill();
  }

  /* ---- 磁面：marching squares（只画 LCFS 内部的等值线） ---- */
  function inside(poly, x, y) {
    var c = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      var xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) c = !c;
    }
    return c;
  }

  function contours(ctx, grid, psi, g, poly, axisVal, edgeVal) {
    var nr = grid.r.length, nz = grid.z.length;
    var i, j;
    var lo = Math.min(axisVal, edgeVal), hi = Math.max(axisVal, edgeVal);
    var span = hi - lo || 1;
    var levels = [0.1, 0.22, 0.35, 0.48, 0.61, 0.74, 0.87, 0.96];
    levels.forEach(function (lv, idx) {
      var target = lo + span * lv;
      ctx.strokeStyle = idx === levels.length - 1 ? COL.main : 'rgba(23,101,127,0.38)';
      ctx.lineWidth = idx === levels.length - 1 ? 2.2 : 1;
      ctx.beginPath();
      for (i = 0; i < nr - 1; i++) {
        for (j = 0; j < nz - 1; j++) {
          var a = psi[i][j], b = psi[i + 1][j], c = psi[i + 1][j + 1], d = psi[i][j + 1];
          var seg = march(a, b, c, d, target);
          for (var k = 0; k < seg.length; k += 4) {
            var r1 = grid.r[i] + (grid.r[i + 1] - grid.r[i]) * seg[k];
            var z1 = grid.z[j] + (grid.z[j + 1] - grid.z[j]) * seg[k + 1];
            var r2 = grid.r[i] + (grid.r[i + 1] - grid.r[i]) * seg[k + 2];
            var z2 = grid.z[j] + (grid.z[j + 1] - grid.z[j]) * seg[k + 3];
            ctx.moveTo(g.sx(r1), g.sy(z1)); ctx.lineTo(g.sx(r2), g.sy(z2));
          }
        }
      }
      ctx.stroke();
    });
  }

  function lerp(v0, v1, t) { return (t - v0) / (v1 - v0 || 1e-12); }

  function march(a, b, c, d, t) {
    var pts = [];
    if ((a < t) !== (b < t)) pts.push([lerp(a, b, t), 0]);
    if ((b < t) !== (c < t)) pts.push([1, lerp(b, c, t)]);
    if ((d < t) !== (c < t)) pts.push([lerp(d, c, t), 1]);
    if ((a < t) !== (d < t)) pts.push([0, lerp(a, d, t)]);
    var out = [];
    if (pts.length >= 2) out = [pts[0][0], pts[0][1], pts[1][0], pts[1][1]];
    if (pts.length === 4) out = out.concat([pts[2][0], pts[2][1], pts[3][0], pts[3][1]]);
    return out;
  }

  function residualPanel(host, title, channels) {
    var p = makePanel(host, title, '加权残差 σ，灰=未参与拟合');
    var vals = channels.map(function (c) { return c.sigma; });
    var rawMax = Math.max.apply(null, vals.map(Math.abs));
    var mx = Math.min(10, Math.max(2, Math.ceil(rawMax)));
    var clipped = rawMax > mx;
    var g = frame(p.ctx, [0, channels.length], [-mx, mx], '通道序号', 'σ' + (clipped ? '（截断 ±' + mx + '）' : ''), ticks(0, channels.length, 4), [-mx, 0, mx]);
    var bw = Math.max(1.5, (g.R - g.L) / channels.length * 0.55);
    channels.forEach(function (c, i) {
      var x = g.L + (g.R - g.L) * (i + 0.5) / channels.length;
      var y0 = g.sy(0), y1 = g.sy(Math.max(-mx, Math.min(mx, c.sigma)));
      var mag = Math.abs(c.sigma);
      p.ctx.fillStyle = !c.used ? 'rgba(182,198,207,0.55)' : mag > 2 ? COL.bad : mag > 1 ? COL.warn : COL.main;
      p.ctx.fillRect(x - bw / 2, Math.min(y0, y1), bw, Math.abs(y1 - y0) || 1);
    });
    var big = channels.filter(function (c) { return c.used && Math.abs(c.sigma) > 5; });
    if (big.length) {
      var det = el('details', 'eqp-outliers');
      det.appendChild(el('summary', null, '已使用通道中 ' + big.length + ' 道 |σ| > 5（展开）'));
      var ul = el('ul');
      big.sort(function (a, b) { return Math.abs(b.sigma) - Math.abs(a.sigma); }).forEach(function (c) {
        var li = el('li', null, c.name + '（' + c.kind + '）  σ = ' + c.sigma.toFixed(1));
        ul.appendChild(li);
      });
      det.appendChild(ul);
      if (p.fig) p.fig.appendChild(det);
    }
  }

  function render(host, result) {
    host.innerHTML = '';
    var pr = result.profiles || {};
    var psin = pr.psin || [];
    var grid = result.grid, psi = result.psi;

    // 1 磁面
    if (grid && psi && grid.r && grid.z) {
      var lim = (result.limiter && result.limiter.r) ? result.limiter : null;
      var rmin = grid.r[0], rmax = grid.r[grid.r.length - 1];
      var zmin = grid.z[0], zmax = grid.z[grid.z.length - 1];
      var b = result.boundary || [];
      var padR = (rmax - rmin) * 0.12, padZ = (zmax - zmin) * 0.12;
      var R0 = b.length ? Math.min.apply(null, b.map(function (q) { return q[0]; })) - padR : rmin;
      var R1 = b.length ? Math.max.apply(null, b.map(function (q) { return q[0]; })) + padR : rmax;
      var Z0 = b.length ? Math.min.apply(null, b.map(function (q) { return q[1]; })) - padZ : zmin;
      var Z1 = b.length ? Math.max.apply(null, b.map(function (q) { return q[1]; })) + padZ : zmax;
      R0 = Math.max(R0, rmin); R1 = Math.min(R1, rmax);
      Z0 = Math.max(Z0, zmin); Z1 = Math.min(Z1, zmax);
      var H1 = 430;
      var pw = CW - PAD.l - PAD.r, ph = H1 - PAD.t - PAD.b;
      var rr0 = R1 - R0, zz0 = Z1 - Z0, kk = Math.max(rr0 / pw, zz0 / ph);
      var dr = (pw * kk - rr0) / 2, dz = (ph * kk - zz0) / 2;
      R0 -= dr; R1 += dr; Z0 -= dz; Z1 += dz;
      var p1 = makePanel(host, '磁面与边界', 'ψ 等值线 · 黑线为 LCFS', H1);
      var g1 = frame(p1.ctx, [R0, R1], [Z0, Z1], 'R / m', 'Z / m',
        ticks(R0, R1, 4), ticks(Z0, Z1, 4), H1);
      var ai = Math.round((result.facts.axis_r - grid.r[0]) / (grid.r[1] - grid.r[0]));
      var aj = Math.round((result.facts.axis_z - grid.z[0]) / (grid.z[1] - grid.z[0]));
      ai = Math.max(0, Math.min(grid.r.length - 1, ai)); aj = Math.max(0, Math.min(grid.z.length - 1, aj));
      var axisVal = psi[ai][aj];
      var edgeVals = b.map(function (q) {
        var ii = Math.round((q[0] - grid.r[0]) / (grid.r[1] - grid.r[0]));
        var jj = Math.round((q[1] - grid.z[0]) / (grid.z[1] - grid.z[0]));
        ii = Math.max(0, Math.min(grid.r.length - 1, ii)); jj = Math.max(0, Math.min(grid.z.length - 1, jj));
        return psi[ii][jj];
      });
      var edgeVal = edgeVals.length ? edgeVals.reduce(function (a, c) { return a + c; }, 0) / edgeVals.length : axisVal;
      if (b.length) {
        var path = new Path2D();
        b.forEach(function (q, idx) {
          var x = g1.sx(q[0]), y = g1.sy(q[1]);
          if (idx === 0) path.moveTo(x, y); else path.lineTo(x, y);
        });
        path.closePath();
        p1.ctx.save(); p1.ctx.clip(path);
        contours(p1.ctx, grid, psi, g1, b, axisVal, edgeVal);
        p1.ctx.restore();
      } else {
        contours(p1.ctx, grid, psi, g1, b, axisVal, edgeVal);
      }
      if (result.boundary && result.boundary.length) {
        var bx = result.boundary.map(function (q) { return q[0]; });
        var bz = result.boundary.map(function (q) { return q[1]; });
        line(p1.ctx, bx.concat([bx[0]]), bz.concat([bz[0]]), g1, COL.ink, 1.6);
      }
      if (lim) line(p1.ctx, lim.r.concat([lim.r[0]]), lim.z.concat([lim.z[0]]), g1, '#9aaab4', 1.2);
      if (result.facts && isFinite(result.facts.axis_r)) {
        p1.ctx.fillStyle = COL.bad;
        p1.ctx.beginPath();
        p1.ctx.arc(g1.sx(result.facts.axis_r), g1.sy(result.facts.axis_z), 3, 0, 6.29);
        p1.ctx.fill();
      }
    }

    // 2 q(ψN)
    if (psin.length && pr.qpsi) {
      var p2 = makePanel(host, '安全因子 q(ψN)', 'q₀ ' + fmt(result.facts?.q0) + ' · q₉₅ ' + fmt(result.facts?.q95));
      var qmax = Math.max.apply(null, pr.qpsi), qmin = Math.min.apply(null, pr.qpsi);
      var g2 = frame(p2.ctx, [0, 1], [Math.min(0, qmin), qmax * 1.05], 'ψN', 'q', [0, 0.2, 0.4, 0.6, 0.8, 1], ticks(Math.min(0, qmin), qmax * 1.05, 4));
      line(p2.ctx, psin, pr.qpsi, g2, COL.main, 2);
    }

    // 3 p(ψN)
    if (psin.length && pr.pres) {
      var presK = pr.pres.map(function (v) { return v / 1000; });
      var pmax = Math.max.apply(null, presK);
      var target = pr.pres_target || pr.pres_one_two || null;
      var tK = target ? target.map(function (v) { return v / 1000; }) : null;
      var top = Math.max.apply(null, presK.concat(tK || []));
      var p3 = makePanel(host, '压力 p(ψN)', (tK ? 'kPa · 实线本次，虚线外部目标' : 'kPa · 中心 ' + fmt(pmax) + ' kPa'));
      var g3 = frame(p3.ctx, [0, 1], [0, top * 1.08], 'ψN', 'p / kPa', [0, 0.2, 0.4, 0.6, 0.8, 1], ticks(0, top * 1.08, 4));
      if (tK) line(p3.ctx, psin, tK, g3, COL.ref, 1.6);
      line(p3.ctx, psin, presK, g3, COL.main, 2);
    }

    // 4 p'(ψN)
    if (psin.length && pr.pprime) {
      var sig = pr.pprime_sigma || [];
      var lo = pr.pprime.map(function (v, i) { return (v - (sig[i] || 0)) / 1e5; });
      var hi = pr.pprime.map(function (v, i) { return (v + (sig[i] || 0)) / 1e5; });
      var mid = pr.pprime.map(function (v) { return v / 1e5; });
      var lo0 = Math.min.apply(null, lo), hi0 = Math.max.apply(null, hi);
      var p4 = makePanel(host, '压力梯度 p′(ψN)', '×10⁵ Pa/Wb · 阴影为拟合不确定度');
      var g4 = frame(p4.ctx, [0, 1], [lo0, hi0], 'ψN', 'p′', [0, 0.2, 0.4, 0.6, 0.8, 1], ticks(lo0, hi0, 4));
      band(p4.ctx, psin, lo, hi, g4);
      line(p4.ctx, psin, mid, g4, COL.main, 2);
    }

    // 5 FF'(ψN)
    if (psin.length && pr.ffprim) {
      var s2 = pr.ffprim_sigma || [];
      var lo2 = pr.ffprim.map(function (v, i) { return v - (s2[i] || 0); });
      var hi2 = pr.ffprim.map(function (v, i) { return v + (s2[i] || 0); });
      var l2 = Math.min.apply(null, lo2), h2 = Math.max.apply(null, hi2);
      var p5 = makePanel(host, 'FF′(ψN)', '阴影为拟合不确定度');
      var g5 = frame(p5.ctx, [0, 1], [l2, h2], 'ψN', 'FF′', [0, 0.2, 0.4, 0.6, 0.8, 1], ticks(l2, h2, 4));
      band(p5.ctx, psin, lo2, hi2, g5);
      line(p5.ctx, psin, pr.ffprim, g5, COL.main, 2);
    }

    // 5b 电流分量（仅当结果里带分量时）
    if (pr.jphi_psin && (pr.jphi_bs || pr.jphi_oh || pr.jphi_driven)) {
      var jx = pr.jphi_psin;
      var jt = pr.jphi || [];
      var series = [
        { y: pr.jphi_bs, c: COL.main, dash: null },
        { y: pr.jphi_oh, c: '#7b909c', dash: null },
        { y: pr.jphi_driven, c: COL.ref, dash: '5 4' }
      ].filter(function (s) { return s.y && s.y.length; });
      var all = [].concat(jt, series.reduce(function (a, s) { return a.concat(s.y); }, []));
      var jlo = Math.min.apply(null, all), jhi = Math.max.apply(null, all);
      var p6 = makePanel(host, '电流分量 j(ψN)', 'A/m² · 多分量');
      var g6 = frame(p6.ctx, [0, 1], [jlo, jhi], 'ψN', 'j / A·m⁻²', [0, 0.2, 0.4, 0.6, 0.8, 1], ticks(jlo, jhi, 4));
      series.forEach(function (s) { line(p6.ctx, jx, s.y, g6, s.c, 1.6); });
      if (jt.length) line(p6.ctx, jx, jt, g6, COL.ink, 2.2);
    }

    // 6 逐道残差
    if (result.channels) {
      var ch = (result.channels.loops || []).map(function(c){return Object.assign({kind:'磁通环'},c)}).concat((result.channels.probes || []).map(function(c){return Object.assign({kind:'探针'},c)}));
      if (ch.length) residualPanel(host, '逐道加权残差', ch);
    }
  }

  global.EQP = { render: render };
})(window);
