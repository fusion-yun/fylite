// 页面的 node 检查：把 kinetic_recon.html 的脚本在一个极小 DOM 垫片里真的跑一遍，喂一份份结果 JSON，
// 断言对应的那一页每一块都画出了东西。
//
//   node test/smoke.mjs kinetic_recon.html <result.json> [更多.json …]
//
// 每个文件按它自己的 @type 走自己的一套断言：
//   fylite:KineticReconResult  → 三档反演页（另查只有档 M 的结果也能载；物理校验的徽章 · 逐条表，合成一档不物理的）
//   fylite:KineticReconSeries  → 时间序列页（另查每个量的迹都画了、滑条 / 点迹 / 键盘换时刻截面跟着换、失败的时刻标出来、
//                                不物理的时刻另标（琥珀）且与失败分开、汇总写明排除了几片）
//   fylite:Wei2026Profiles     → 逐片剖面页（另查换片、清洗剔点画成叉、缺 T_i 照说）
//   fylite:Wei2026Transport    → 输运页（另查无效段涂出来、台基带、加热与驱动的账）
//
// ★结果 JSON 带实验数据，不入仓——所以这道检查要调用方给文件（kinetic_recon.py run / series · wei2026.py 的输出）。
// ★垫片只认 HTML 里真有的 id：脚本里拼错一个 id，这里当场报错，而不是在浏览器里静默画不出来。
import { readFileSync } from "node:fs";
import vm from "node:vm";

const [, , htmlPath, ...resultPaths] = process.argv;
if (!htmlPath || !resultPaths.length) {
  console.error("usage: node test/smoke.mjs kinetic_recon.html <result.json> [更多.json …]");
  process.exit(2);
}
const html = readFileSync(htmlPath, "utf8");
const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join("\n");

function element(id) {
  const listeners = {};
  return {
    id, innerHTML: "", textContent: "", hidden: false, attrs: {},
    addEventListener(k, fn) { (listeners[k] ||= []).push(fn); },
    fire(k, ev) { for (const fn of listeners[k] || []) fn(ev); },
    setAttribute(k, v) { this.attrs[k] = String(v); }, removeAttribute(k) { delete this.attrs[k]; },
    getAttribute(k) { return this.attrs[k]; },
  };
}
const els = {};
const docListeners = {};
const document = {
  getElementById(id) {
    if (!ids.has(id)) throw new Error(`the script asks for #${id}, which the page does not have`);
    return (els[id] ||= element(id));
  },
  documentElement: element("html"),
  addEventListener(k, fn) { (docListeners[k] ||= []).push(fn); },
};
const store = {};
const alerts = [];
const ctx = {
  document, console, JSON, Math, Number, String, Array, Object, isFinite, parseFloat,
  localStorage: { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); } },
  alert: (m) => alerts.push(m), FileReader: class {},
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(script, ctx, { filename: htmlPath });

let failed = 0;
const check = (cond, what) => { console.log(`${cond ? "ok  " : "FAIL"} ${what}`); if (!cond) failed++; };
const count = (s, re) => (String(s).match(re) || []).length;
//: 上一份文件画的东西不许冒充这一份画的
const clearEls = () => { for (const e of Object.values(els)) { e.innerHTML = ""; e.textContent = ""; } };

//: 原理页：不要结果就能读，各节都在，页内目录每一条都指得到
check(/<div id="docview">/.test(html) && /<div id="resview" hidden>/.test(html), "打开时停在「原理与过程」（标记里原理页可见、结果页 hidden）");
const sections = [...html.matchAll(/<h2 id="(d-[a-z]+)"/g)].map((m) => m[1]);
const navs = [...html.matchAll(/<a href="#(d-[a-z]+)"/g)].map((m) => m[1]);
check(sections.length === 12, `原理页十二节（${sections.join(" ")}）`);
check(navs.length === sections.length && navs.every((n) => sections.includes(n)), "页内目录与各节一一对上");
check(sections.includes("d-profiles") && sections.includes("d-transport"), "两种 wei2026 输出各有一节原理");
check(sections.includes("d-series"), "时间序列对拍有一节原理");
check(/<div class="eq">/.test(html) && (html.match(/<span class="n">\(\d\)<\/span>/g) || []).length >= 8, "公式块带编号（≥ 8 条）");

// ============================================================================== 逐个文件
let lastType = null;
for (const resultPath of resultPaths) {
  const text = readFileSync(resultPath, "utf8");
  const res = JSON.parse(text);
  const ty = res["@type"];
  console.log(`\n--- ${resultPath}  (${ty})`);
  clearEls();
  const before = alerts.length;
  check(ctx.KR.load(text, "input.json") === true, "载入");
  check(alerts.length === before, `没有弹窗（${alerts.slice(before).join(" | ")}）`);
  check(els.resview.hidden === false && els.docview.hidden === true, "载入后切到「结果」页签");
  check(els.title.textContent.includes(String(res.shot)), "标题带炮号");
  check(els.empty.hidden === true, "空状态收起");

  lastType = ctx.KR.state.type;
  if (ty === "fylite:KineticReconResult" && res.tiers && res.tiers.X) kinxChecks(text, res);
  else if (ty === "fylite:KineticReconResult") reconChecks(text, res);
  else if (ty === "fylite:KineticReconSeries") seriesChecks(text, res);
  else if (ty === "fylite:KefitSlices") kefitChecks(res);
  else if (ty === "fylite:Wei2026Profiles") profilesChecks(res);
  else if (ty === "fylite:Wei2026Transport") transportChecks(res);
  else check(false, `未知的 @type：${ty}（这道检查不认）`);
}

// ============================================================================== 档 X：十一格 + 输入文件编辑
function kinxChecks(text, res) {
  const X = res.tiers.X;
  check(els.xmain.hidden === false && els.main.hidden === true && els.kmain.hidden === true, "带档 X 的结果开的是十一格页");
  check(els.xtoggle.hidden === false && els.xtoggle.textContent.includes("三档"), "有「看三档并排」的切换");
  if (X.status === "ok" || X.status === "unphysical") {
    for (const id of ["xva", "xvb", "xvc", "xvd", "xve", "xvf", "xvh", "xvi", "xvj", "xvk"])
      check(els[id].innerHTML.includes("<svg") && els[id].innerHTML.includes('stroke="var(--tX)"'), `(${id.slice(2)}) 画出了档 X`);
    for (const id of ["xvh", "xvi", "xvj", "xvk"]) check(els[id].innerHTML.includes('stroke="var(--tM)"'), `(${id.slice(2)}) 基础档作对照`);
    check(count(els.xvc.innerHTML, /<svg/g) === 2, "(c) χ² 与置信度两条");
    check(els.xva.innerHTML.includes('fill="var(--ok)"'), "(a) 进拟合的测量画成绿点");
    check(els.xvg.innerHTML.includes('data-src="ours"') && els.xvg.innerHTML.includes('data-src="kefit"'), "(g) 档 X 与基础档的边界");
    check(els.xvs.innerHTML.includes("q₀") && els.xvs.innerHTML.includes("约束"), "标量 · 约束表");
    const cu = (X.kinetic || {}).currents || {};
    if (cu.boot) check(els.xvf.innerHTML.includes('stroke="var(--tP)"'), "(f) 画了自举电流");
    if ((X.kinetic.passes || []).length > 1) check(els.xvs.innerHTML.includes("外环"), "外环逐遍表");
  }
  els.xtoggle.fire("click");
  check(ctx.KR.state.type === "recon" && els.main.hidden === false && els.xmain.hidden === true, "切到三档并排");
  check(els.tierbtns.innerHTML.includes('data-tier="X"'), "三档页的档按钮里有 X");
  els.xtoggle.fire("click");
  check(ctx.KR.state.type === "kinx", "再切回十一格");
  if (res.physics_check) check(X.physics_check && "passed" in X.physics_check || X.status === "error", "档 X 也过物理校验");
  editorChecks(X.input);
}
function editorChecks(inp) {
  if (!inp) return;
  els["tab-in"].fire("click");
  check(els.inview.hidden === false && els.resview.hidden === true && els.docview.hidden === true, "「输入」页签");
  check(ctx.KR.edLoad(JSON.parse(JSON.stringify(inp)), "in.json") === true, "输入文件载入编辑器");
  const nl = Object.keys(inp.magnetics.loops).length;
  check(count(els.edch.innerHTML, /data-p="magnetics.loops" data-t="conf"/g) === nl, `逐道置信度：磁通环 ${nl} 格`);
  check(count(els.edch.innerHTML, /data-bulk=/g) === 10, "五组各有「全设 1 / 全关」");
  for (const k of ["q0.on", "pedestal.x", "basis.pprime.mode", "currents.bootstrap.use", "currents.external.total_A", "pressure.source"])
    check(els.edform.innerHTML.includes(`data-p="${k}"`), `表单有 ${k}`);
  const name = Object.keys(inp.magnetics.loops)[0];
  els.edch.fire("change", { target: { getAttribute: (a) => ({ "data-p": "magnetics.loops", "data-t": "conf", "data-k": name })[a], value: "0" } });
  check(ctx.KR.state.inp.magnetics.loops[name] === 0 && els.edjson.textContent.includes(`"${name}": 0`), `改一道置信度（${name} → 0）进 JSON`);
  els.edform.fire("change", { target: { getAttribute: (a) => ({ "data-p": "currents.bootstrap.x", "data-t": "list" })[a], value: "0.9, 0.95 0.99" } });
  check(JSON.stringify(ctx.KR.state.inp.currents.bootstrap.x) === "[0.9,0.95,0.99]", "列表字段按逗号 / 空白拆");
  els.edform.fire("change", { target: { getAttribute: (a) => ({ "data-p": "pressure.profile", "data-t": "cols", "data-c": "psin,p,sigma" })[a], value: "0 1000 100\n0.5 500 50" } });
  check(JSON.stringify(ctx.KR.state.inp.pressure.profile.p) === "[1000,500]", "多列字段按行拆成各列");
  els.edch.fire("click", { target: { closest: () => ({ getAttribute: (a) => ({ "data-bulk": "pressure.thomson", "data-v": "0" })[a] }) } });
  check(ctx.KR.state.inp.pressure.thomson.every((v) => v === 0), "「全关」把一组置信度都设 0");
  check(ctx.KR.edLoad({ "@type": "fylite:KineticReconResult" }, "x.json") === false, "不是输入文件的拒收");
  els["tab-res"].fire("click");
}

// ============================================================================== 三档反演页
function reconChecks(text, res) {
  check(els.main.hidden === false && els.wmain.hidden === true && els.tmain.hidden === true, "开的是三档反演页");
  els["tab-doc"].fire("click");
  check(els.docview.hidden === false && els.resview.hidden === true, "点「原理与过程」切回去");
  els["tab-res"].fire("click");
  check(els.resview.hidden === false, "点「结果」再切回来");
  const okTiers = ["M", "K", "P"].filter((k) => res.tiers[k] && res.tiers[k].status === "ok");
  check(count(els.ladder.innerHTML, /<tr>/g) >= 1 + Object.keys(res.tiers).length, `阶梯表每档一行（${Object.keys(res.tiers).join("")}）`);
  for (const k of okTiers) {
    ctx.KR.state.main = k;
    ctx.KR.render();
    const xs = els.xs.innerHTML;
    check(count(xs, /<line /g) > 50, `档 ${k}：截面画出了 ψ_N 等值线（${count(xs, /<line /g)} 段）`);
    check(count(xs, /<path /g) >= 1 + okTiers.length, `档 ${k}：限制器 + 各档边界`);
    const nch = res.tiers[k].channels.loops.length + res.tiers[k].channels.probes.length;
    check(count(els.magbars.innerHTML, /<rect /g) >= nch - 5, `档 ${k}：磁残差条 ${count(els.magbars.innerHTML, /<rect /g)} / ${nch}`);
    for (const id of ["pq", "pp", "ppr", "pff"]) check(els[id].innerHTML.includes("<path"), `档 ${k}：剖面 #${id} 有曲线`);
  }
  if (res.tiers.K && res.tiers.K.status === "ok") check(count(els.kbody.innerHTML, /<svg/g) === 2, "档 K：法拉第与线密度两张残差图");
  if (res.tiers.P && res.tiers.P.status === "ok") {
    check(els.pbody.innerHTML.includes("<svg"), "档 P：外环证书图");
    check(count(els.pbody.innerHTML, /<tr/g) >= res.tiers.P.thomson.points.length, "档 P：逐点表");
  }
  check(els.foot.innerHTML.includes(res.app), "页脚带出处");
  physReconChecks(text, res);
  //: 缺档也得画得出来：只留 M
  const onlyM = JSON.parse(text);
  delete onlyM.tiers.K; delete onlyM.tiers.P;
  check(ctx.KR.load(JSON.stringify(onlyM), "only-M.json") === true, "只有档 M 的结果也能载入");
  check(els.kbody.innerHTML.includes("没跑档 K") && els.pbody.innerHTML.includes("没跑档 P"), "缺的档说「没跑」，不报错");
}

//: 物理校验：每档一枚徽章（过 / 不物理 + 条目），主显示档逐条列；另合成一份档 M 不物理的，查它照画、徽章与阶梯都标出来
function physReconChecks(text, res) {
  const has = (t) => t && (t.status === "ok" || t.status === "unphysical");
  ctx.KR.load(text, "again.json");
  if (!res.physics_check) {
    check(els.phys.innerHTML.includes("没做物理校验"), "物理校验：旧结果（没有 physics_check）说「没做物理校验」");
  } else {
    for (const k of ["M", "K", "P"]) {
      const t = res.tiers[k];
      if (!has(t)) continue;
      const want = t.status === "unphysical" ? "unphysical" : "pass";
      check(new RegExp(`data-tier-phys="${k}"[^]*?data-phys="${want}"`).test(els.phys.innerHTML), `物理校验：档 ${k} 的徽章是「${want === "pass" ? "物理 ✓" : "不物理"}」`);
      if (want === "unphysical") check(t.physics_check.failed.every((id) => els.phys.innerHTML.includes(id)), `物理校验：档 ${k} 没过的条目都列出（${t.physics_check.failed.join(",")}）`);
    }
    check(count(els.ladder.innerHTML, /data-phys="(pass|unphysical)"/g) === ["M", "K", "P"].filter((k) => has(res.tiers[k])).length, "阶梯表每个有解的档带一枚物理校验徽章");
    const main = res.tiers[ctx.KR.state.main];
    check(count(els.phys.innerHTML, /data-check="/g) === main.physics_check.checks.length, `主显示档 ${ctx.KR.state.main} 逐条 ${main.physics_check.checks.length} 行（值 · 界 · 结论）`);
    check(els.phys.innerHTML.includes("界值与理由") && Object.keys(res.physics_check.bounds).every((b) => els.phys.innerHTML.includes(b)), "界值与理由逐条列出");
  }
  //: 合成：档 M 不物理（负储能）——数照画，徽章 · 阶梯注 · 逐条表都标出来
  const syn = JSON.parse(text), M = syn.tiers.M;
  if (!has(M)) return;
  const wcheck = { id: "w_positive", value: -373793, bound: "> 0 J", pass: false, kind: "physical", why: "同尺储能 W = -373.8 kJ ≤ 0：压强整体为负，不是物理解（smoke 合成）" };
  M.status = "unphysical";
  M.physics_check = { passed: false, failed: ["w_positive"], checks: [wcheck].concat(((M.physics_check || {}).checks || []).filter((c) => c.id !== "w_positive")) };
  syn.physics_check = syn.physics_check || { enabled: true, select: false, bounds: {}, tiers: {} };
  syn.physics_check.enabled = true;
  check(ctx.KR.load(JSON.stringify(syn), "synthetic-unphysical.json") === true, "载入合成的档 M 不物理的结果");
  ctx.KR.state.main = "M"; ctx.KR.render();
  check(/data-tier-phys="M"[^]*?data-phys="unphysical"/.test(els.phys.innerHTML) && els.phys.innerHTML.includes("不物理：w_positive"), "合成：档 M 的徽章是「不物理：w_positive」");
  check(els.ladder.innerHTML.includes('data-phys="unphysical"') && els.ladnote.innerHTML.includes("物理校验没过"), "合成：阶梯表与阶梯注标出档 M 不物理");
  check(/<tr class="bad" data-check="w_positive">/.test(els.phys.innerHTML) && els.phys.innerHTML.includes("-373.8 kJ"), "合成：逐条表里没过的那条标出来，连值与理由");
  check(count(els.xs.innerHTML, /<line /g) > 50 && els.pq.innerHTML.includes("<path"), "合成：不物理的档数照画（截面 · 剖面）");
}

// ============================================================================== 时间序列页
//: 单片对拍（kefit_compare.py --page）：十一格都画了、截面两边的边界 · 等值线 · X 点、换时刻跟着换
function kefitChecks(res) {
  check(els.kmain.hidden === false && els.smain.hidden === true && els.main.hidden === true, "开的是单片对拍页");
  const i0 = res.slices.findIndex((s) => !s.error);
  check(ctx.KR.state.i === Math.max(0, i0), "停在第一片画得了的");
  const n = res.slices.length;
  check(els.kpos.textContent.includes(`/ ${n} 个时刻`) && els.kslider.max === String(Math.max(0, n - 1)), `时间条：共 ${n} 个时刻，滑条到 ${n - 1}`);
  check(els.ktx.innerHTML.includes("<svg") && count(els.ktx.innerHTML, /<rect data-i=/g) === n, `整段 X 点迹：每个时刻一条可点的竖条（${n}）`);
  check(count(els.ktx.innerHTML, /<line [^>]*stroke-dasharray="4 3"/g) >= 2, "整段 X 点迹：±0.005 的双零带");
  check(els.ktd.innerHTML.includes("<svg"), "整段距离迹");
  if (i0 < 0) return;
  for (const id of ["ka", "kb", "kc", "kd", "ke", "kh", "ki", "kj", "kk"])
    check(els[id].innerHTML.includes("<svg") && els[id].innerHTML.includes('stroke="var(--tM)"') && els[id].innerHTML.includes('stroke="var(--tX)"'), `(${id.slice(1)}) 两边都画了`);
  check(els.ka.innerHTML.includes('fill="var(--ok)"'), "(a) 用了的测量画成绿点");
  check(els.kg.innerHTML.includes('data-src="ours"') && els.kg.innerHTML.includes('data-src="kefit"'), "(g) 两边的最外闭合面");
  check(els.kg.innerHTML.includes('data-k="ours-0.5"') && els.kg.innerHTML.includes('data-k="kefit-0.5"'), "(g) 两边的 ψ_N 等值线");
  check(count(els.kg.innerHTML, /data-xpt=/g) >= 4 && els.kg.innerHTML.includes('stroke="var(--wall)"'), "(g) X 点与限制器");
  check(els.kf.innerHTML.includes("q₉₅") && els.kf.innerHTML.includes("X 点") && els.kf.innerHTML.includes("磁轴距离"), "(f) 标量表与两个解之间");
  //: 换时刻：与时间序列页同一套——滑条拖动 · ◀ ▶ · 键盘左右键 · 点整段的迹；截面跟着换
  if (n > 1) {
    const a = Math.max(0, i0), last = n - 1;
    ctx.KR.goSlice(a);
    check(els.kprev.disabled === (a === 0) && els.knext.disabled === (a === last), "◀ ▶ 在两头变灰");
    const g0 = els.kg.innerHTML;
    els.kslider.fire("input", { target: { value: String(last) } });
    check(ctx.KR.state.i === last && els.kg.innerHTML !== g0 && els.kslider.value === String(last), "拖滑条换时刻，截面跟着换");
    check(els.ktx.innerHTML.includes("<title>当前 t "), "整段迹上画了当前时刻");
    els.kprev.fire("click");
    check(ctx.KR.state.i === last - 1, "◀ 走到上一时刻");
    els.knext.fire("click");
    check(ctx.KR.state.i === last, "▶ 走到下一时刻");
    for (const fn of docListeners.keydown || []) fn({ key: "ArrowLeft", preventDefault() {} });
    check(ctx.KR.state.i === last - 1, "键盘左键走到上一时刻");
    els.ktd.fire("click", { target: { closest: () => ({ getAttribute: () => String(a) }) } });
    check(ctx.KR.state.i === a && els.kg.innerHTML === g0, "点整段的迹选时刻（截面回到那一时刻）");
  }
}
function seriesChecks(text, res) {
  check(els.smain.hidden === false && els.main.hidden === true && els.wmain.hidden === true && els.tmain.hidden === true, "开的是时间序列页");
  const n = res.slices.length, srcs = Object.keys(res.sources || {});
  const okIdx = res.slices.map((s, i) => s.status === "ok" ? i : -1).filter((i) => i >= 0);
  check(els.spos.textContent.includes(`/ ${n} 个时刻`), `片头写着共 ${n} 个时刻`);
  check(ctx.KR.state.i === (okIdx.length ? okIdx[0] : 0), "停在第一个有解的时刻");
  //: 每个量一张迹，每张都画了线；我们与参考两条都在
  const traces = ["sq0", "sq95", "sli", "sbp", "sw", "sip", "sar", "saz", "szc", "sdax", "sdbd", "sdpsi", "schi", "snrej"];
  for (const id of traces) check(els[id].innerHTML.includes("<svg") && count(els[id].innerHTML, /<path d="M/g) >= 1, `迹 #${id} 画了线`);
  const hasRef = (grp, k, src) => res.slices.some((s) => s.refs && s.refs[src] && s.refs[src][grp] && Number.isFinite(s.refs[src][grp][k]));
  for (const [id, grp, k] of [["sq0", "scalars", "q0"], ["sq95", "scalars", "q95"], ["sli", "same_ruler", "li1"], ["sbp", "same_ruler", "betap"],
    ["sw", "same_ruler", "w_mhd_J"], ["sar", "scalars", "axis_r"], ["saz", "scalars", "axis_z"]]) {
    check(els[id].innerHTML.includes('stroke="var(--tM)"'), `#${id}：我们的迹`);
    if (srcs.includes("efit")) check(hasRef(grp, k, "efit") ? els[id].innerHTML.includes('stroke="var(--tK)"') : els[id + "h"].innerHTML.includes("没有这一量"), `#${id}：离线 EFIT 的迹（或说缺）`);
  }
  //: X 点平衡（2026-09-23 起的序列才有）：有就画，双零的两条灰横线也在
  if (res.slices.some((s) => s.ours && Number.isFinite(s.ours.xpt_dpsin))) {
    check(els.sxpt.innerHTML.includes("<svg") && els.sxpt.innerHTML.includes('stroke="var(--tM)"'), "X 点平衡的迹：我们的一条");
    check(count(els.sxpt.innerHTML, /<line [^>]*stroke-dasharray="4 3"/g) >= 2, "X 点平衡的迹：±0.005 的双零带");
  }
  //: 本机 KEFIT 作参考来源（series --kefit）：紫色的迹、截面上的边界、汇总里的形位行
  if (srcs.includes("kefit")) {
    check(els.sq95.innerHTML.includes('stroke="var(--tX)"'), "q₉₅ 图上有本机 KEFIT 的迹");
    check(els.stlegend.innerHTML.includes("本机 KEFIT"), "图例写着本机 KEFIT");
    check(els.ssum.innerHTML.includes("我们 − 本机 KEFIT") && els.ssum.innerHTML.includes('data-xpoint-config="kefit"'), "汇总有本机 KEFIT 一块与 X 点形位行");
  }
  check(els.sip.innerHTML.includes('stroke="var(--muted)"'), "I_p 图上有实测 I_p");
  if (srcs.includes("efit")) {
    const nref = res.slices.filter((s) => s.refs && s.refs.efit && s.refs.efit.scalars && Number.isFinite(s.refs.efit.scalars.q0)).length;
    check(count(els.sq0.innerHTML, /<circle [^>]*stroke="var\(--tK\)"/g) === nref, `q₀ 图上离线 EFIT 的 ${nref} 个点都画了（我们失败的时刻也画）`);
  }
  const wd = res.slices.some((s) => s.measured && Number.isFinite(s.measured.w_dia_J));
  check(wd ? els.sw.innerHTML.includes('stroke="var(--muted)"') : els.swh.innerHTML.includes("W_dia 没有"), `W 图上${wd ? "有实测 W_dia" : "说了没有 W_dia"}`);
  check(count(els.sq95.innerHTML, /<rect data-i=/g) === n, `每个时刻一条可点的竖条（${n}）`);
  check(count(els.ssum.innerHTML, /<tr>/g) >= 2 + srcs.reduce((a, s) => a + Object.keys((res.summary.by_source || {})[s] || {}).length, 0), "汇总表每个量一行");
  check(els.smeta.innerHTML.includes("档 M 的设定") && els.sprov.innerHTML.includes("出处") && els.sprov.innerHTML.includes("用时"), "设定 · 出处 · 用时");
  check(els.sfoot.innerHTML.includes(res.app), "页脚带出处");
  //: 截面：我们的边界 + 参考的边界 + 限制器
  if (okIdx.length) {
    ctx.KR.goSlice(okIdx[0]);
    const s0 = res.slices[okIdx[0]];
    check(els.sxs.innerHTML.includes('data-src="ours"'), "截面：我们的边界");
    for (const src of srcs) if (s0.refs[src] && (s0.refs[src].boundary || []).length) check(els.sxs.innerHTML.includes(`data-src="${src}"`), `截面：${src} 的边界`);
    //: 参考的虚线画在我们的实线之上（贴着我们的参考才看得见）
    for (const src of srcs) if (s0.refs[src] && (s0.refs[src].boundary || []).length)
      check(els.sxs.innerHTML.indexOf(`data-src="${src}"`) > els.sxs.innerHTML.indexOf('data-src="ours"'), `截面：${src} 的边界画在我们之上`);
    if (s0.ours && s0.ours.xpt_upper) check(count(els.sxs.innerHTML, /data-xpt="我们-/g) === 2, "截面：我们的两个 X 点");
    if (res.device && res.device.limiter) check(els.sxs.innerHTML.includes('stroke="var(--wall)"'), "截面：限制器");
    check(els.sslice.innerHTML.includes("<table") && els.sslice.innerHTML.includes("两个解之间"), "这一时刻的数表");
  }
  //: 换时刻：滑条 · 点迹 · 键盘；截面跟着换
  if (okIdx.length >= 2) {
    const [a, b] = [okIdx[0], okIdx[okIdx.length - 1]];
    ctx.KR.goSlice(a);
    const xa = els.sxs.innerHTML, na = els.sxsnote.innerHTML;
    els.sslider.fire("input", { target: { value: String(b) } });
    check(ctx.KR.state.i === b && els.sxs.innerHTML !== xa && els.sxsnote.innerHTML !== na, "滑条换时刻，截面跟着换");
    check(els.sq95.innerHTML.includes(`<title>当前 t `), "迹上画了当前时刻");
    els.sq0.fire("click", { target: { closest: () => ({ getAttribute: () => String(a) }) } });
    check(ctx.KR.state.i === a && els.sxs.innerHTML === xa, "点迹选时刻（截面回到那一时刻）");
    els.sdbd.fire("click", { target: { closest: () => null } });
    check(ctx.KR.state.i === a, "点在迹外不换时刻");
    for (const fn of docListeners.keydown || []) fn({ key: "ArrowRight", preventDefault() {} });
    check(ctx.KR.state.i === a + 1, "键盘右键走到下一时刻");
  }
  ctx.KR.goSlice(0);
  check(els.sprev.disabled === true && (n === 1 || els.snext.disabled === false), "第一个时刻：上一时刻按钮停用");
  ctx.KR.goSlice(n + 5);
  check(els.snext.disabled === true && ctx.KR.state.i === n - 1 && els.sslider.value === String(n - 1), "越界夹回最后一个时刻、滑条对上");
  //: 失败的时刻：结果里有的照标；另合成一个，查失败的路径一定走得通。不物理的时刻（有解、校验没过）不算失败，另查
  const failMarks = (m) => count(els.sq95.innerHTML, /<title>失败 t /g) === m && count(els.schi.innerHTML, /<title>失败 t /g) === m;
  const unIdx = res.slices.map((s, i) => s.status === "unphysical" ? i : -1).filter((i) => i >= 0);
  const nf = n - okIdx.length - unIdx.length;
  check(failMarks(nf), `失败的 ${nf} 个时刻在迹上标出来`);
  if (nf) check(res.slices.filter((s) => s.status !== "ok" && s.status !== "unphysical").every((s) => els.sfail.innerHTML.includes(String(s.why || "").slice(0, 20).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])))), "失败原因逐条列出");
  else check(els.sfail.innerHTML.includes("每个时刻都有解"), "没有失败时照说");
  seriesPhysChecks(text, res, okIdx, unIdx, failMarks, nf);
  if (okIdx.length >= 2) {
    const syn = JSON.parse(text), j = okIdx[1];
    syn.slices[j] = { time_s: syn.slices[j].time_s, status: "error", why: "合成的失败（smoke）：没有一个竖直设定点收敛", seconds: 0,
      refs: syn.slices[j].refs };
    check(ctx.KR.load(JSON.stringify(syn), "synthetic.json") === true, "载入合成了一个失败时刻的序列");
    check(failMarks(nf + 1), "合成的失败时刻在每张迹上标成红竖虚线");
    check(els.sfail.innerHTML.includes("合成的失败"), "失败原因列在「失败的时刻」里");
    ctx.KR.goSlice(j);
    check(els.sxsnote.innerHTML.includes("没有解") && els.sslice.innerHTML.includes("合成的失败") && els.sstate.innerHTML.includes("失败"), "停在失败的时刻：截面与数表都说没有解");
    check(srcs.every((src) => !(syn.slices[j].refs[src] || {}).boundary || els.sxs.innerHTML.includes(`data-src="${src}"`)), "失败的时刻仍画出参考的边界");
  }
}

//: 不物理的时刻：与失败分开标（琥珀竖虚线 · 空心琥珀点）、汇总写明排除了几片、这一片的表列出没过的条目；另合成一个
function seriesPhysChecks(text, res, okIdx, unIdx, failMarks, nf) {
  const unMarks = (m) => count(els.sq95.innerHTML, /<title>不物理 t /g) === m && count(els.schi.innerHTML, /<title>不物理 t /g) === m;
  ctx.KR.load(text, "again.json");
  check(unMarks(unIdx.length), `不物理的 ${unIdx.length} 个时刻在迹上另标（琥珀竖虚线），不算进失败的 ${nf} 个`);
  check(els.stlegend.innerHTML.includes("不物理的时刻") && els.stlegend.innerHTML.includes("失败的时刻"), "图例分开说失败（红）与不物理（琥珀）");
  const su = res.summary || {};
  if (unIdx.length) {
    check(su.n_unphysical === unIdx.length && su.n_ok === okIdx.length, `汇总的片数对得上（做成 ${su.n_ok} · 不物理 ${su.n_unphysical} · 失败 ${su.n_failed}）`);
    check(new RegExp(`data-unph-count>${unIdx.length}<`).test(els.ssum.innerHTML) && els.ssum.innerHTML.includes(`${unIdx.length} 片不物理，已从下面的均值 / rms 里排除`), "汇总卡写明排除了几片不物理的");
    check(Object.keys(su.unphysical.checks_fired).every((k) => els.ssum.innerHTML.includes(k)), `汇总卡列出触发的校验（${Object.keys(su.unphysical.checks_fired).join(",")}）`);
    check(unIdx.every((i) => els.sfail.innerHTML.includes(`data-unph-t="${+res.slices[i].time_s.toFixed(4)}"`)), "「失败的时刻 · 缺口」里逐个列出不物理的时刻");
    const withQ0 = unIdx.filter((i) => Number.isFinite((res.slices[i].ours || {}).q0)).length;
    check(count(els.sq0.innerHTML, /<circle [^>]*stroke="var\(--unph\)"/g) === withQ0, `q₀ 图上不物理时刻画成空心琥珀点（${withQ0}）`);
    const j = unIdx[0], sl = res.slices[j];
    ctx.KR.goSlice(j);
    check(els.sstate.innerHTML.includes("不物理") && !els.sstate.innerHTML.includes("失败："), "停在不物理的时刻：状态行写「不物理」，不写「失败」");
    check(sl.physics_check.failed.every((id) => els.sslice.innerHTML.includes(`data-check="${id}"`)), `这一片的表列出没过的条目（${sl.physics_check.failed.join(",")}）`);
    check(els.sxs.innerHTML.includes('data-unph="1"') && els.sxsnote.innerHTML.includes("不物理"), "截面：我们的边界画成琥珀虚线、注里说不物理");
  } else if ((res.physics_check || {}).enabled) {
    check(els.sfail.innerHTML.includes("都过了物理校验"), "没有不物理的时刻时照说");
  }
  if (okIdx.length >= 2) {
    const syn = JSON.parse(text), j = okIdx[okIdx.length - 1];
    syn.slices[j].status = "unphysical";
    syn.slices[j].physics_check = { passed: false, failed: ["q0_range"], checks: [{ id: "q0_range", value: 0.108, bound: [0.3, 20], pass: false, kind: "physical", why: "q0 = 0.108 不在 [0.3, 20] 内（smoke 合成）" }] };
    check(ctx.KR.load(JSON.stringify(syn), "synthetic-unphysical.json") === true, "载入合成了一个不物理时刻的序列");
    check(unMarks(unIdx.length + 1) && failMarks(nf), "合成的不物理时刻另标一条琥珀竖虚线，失败的个数不变");
    ctx.KR.goSlice(j);
    check(els.sslice.innerHTML.includes('data-check="q0_range"') && els.sslice.innerHTML.includes("smoke 合成"), "合成的不物理时刻：表里列出 q0_range 与理由");
  }
}

// ============================================================================== 逐片剖面页
function profilesChecks(res) {
  check(els.wmain.hidden === false && els.main.hidden === true && els.tmain.hidden === true, "开的是逐片剖面页");
  const n = res.slices.length;
  check(els.wpos.textContent.includes(`/ ${n} 片`), `片头写着共 ${n} 片`);
  check(els.wnrmse.innerHTML.includes("<svg") && els.wh98.innerHTML.includes("<svg"), "全炮两张图：NRMSE 与 H_98");
  check(els.wh98.innerHTML.includes("H 模判据区"), "H_98 图上画了 L / H 阈带");
  check(count(els.wsum.innerHTML, /<tr>/g) >= 5, "汇总表（片数 · 模式 · 三个 NRMSE）");
  check(els.wdata.innerHTML.length > 0 && els.wmethod.innerHTML.includes("<h3>"), "数据与缺口、方法两卡都填了");
  check(els.wfoot.innerHTML.includes(res.app), "页脚带出处");

  //: 逐片走一遍：每一片该画的都画了，剔掉的点画成叉，缺的量照说缺
  let drew = 0, crosses = 0, saidNoTi = 0;
  for (let i = 0; i < n; i++) {
    ctx.KR.goSlice(i);
    const sl = res.slices[i];
    if (sl.status !== "ok") continue;
    drew++;
    for (const key of ["te", "ne", "ti"]) {
      const box = els["w" + key].innerHTML, head = els["w" + key + "h"].innerHTML;
      if (sl[key] && sl[key].fit) {
        check(box.includes("<path"), `片 ${i} ${key}：拟合曲线`);
        if ((sl[key].points || []).length) check(count(box, /<circle |<path d="M/g) > 1, `片 ${i} ${key}：测点也画了`);
        if (key !== "ti" && !head.includes("NRMSE")) check(false, `片 ${i} ${key}：标题没写 NRMSE`);
      } else {
        check(box.includes("这一片没有"), `片 ${i} ${key}：缺就说缺`);
        if (key === "ti") saidNoTi++;
      }
      //: 剔掉的点要么在图里画成叉，要么大得出界、钉在边上画成三角——两样加起来必须一个不少
      const rm = (sl[key] && sl[key].points || []).filter((p) => p[2] === 0).length;
      if (rm) {
        const x = count(box, /stroke-width="1.4"/g), out = count(box, /（出界）/g);
        crosses += x;
        check(x + out === rm, `片 ${i} ${key}：${rm} 个剔掉的点都在（叉 ${x} + 出界三角 ${out}）`);
      }
      if (sl[key] && sl[key].pedestal && sl[key].rho_e != null) { check(box.includes("台基段") && box.includes("ρ_e"), `片 ${i} ${key}：台基段与 ρ_e 标出来了`); }
    }
    check(els.wacct.innerHTML.includes("H_98"), `片 ${i}：H_98 的账`);
  }
  check(drew > 0, `走过每一片（${drew} 片做成了 / 共 ${n}）`);
  check(crosses > 0, `清洗剔掉的点确实画成了叉（全炮 ${crosses} 个）`);
  const noTi = res.slices.filter((s) => s.status === "ok" && !(s.ti && s.ti.fit)).length;
  check(saidNoTi === noTi, `没有 T_i 的 ${noTi} 片都写明了`);
  const sources = new Set(res.slices.filter((s) => s.status === "ok").map((s) => s.ne && s.ne.source));
  for (const src of sources) {
    const i = res.slices.findIndex((s) => s.ne && s.ne.source === src);
    ctx.KR.goSlice(i);
    const want = { thomson: "Thomson", reflectometer: "反射计", point: "POINT 弦拟合" }[src];
    check(!want || els.wnotes.innerHTML.includes(want), `n_e 来源 ${src} 在图下说明了`);
  }
  //: 换片：两端顶住，中间走得动
  ctx.KR.goSlice(0);
  check(els.wprev.disabled === true && (n === 1 || els.wnext.disabled === false), "第一片：上一片按钮停用");
  ctx.KR.goSlice(n - 1);
  check(els.wnext.disabled === true && els.wslider.value === String(n - 1), "最后一片：下一片按钮停用、滑条对上");
  ctx.KR.goSlice(n + 99);
  check(ctx.KR.state.i === n - 1, "越界的片号夹回范围内");
}

// ============================================================================== 输运页
function transportChecks(res) {
  check(els.tmain.hidden === false && els.main.hidden === true && els.wmain.hidden === true, "开的是输运页");
  const prof = res.profiles || {};
  for (const key of ["te", "ne", "ti"]) {
    const box = els["t" + key].innerHTML;
    check(prof[key] && prof[key].fit ? box.includes("<path") : box.includes("这一片没有"), `剖面 ${key}：${prof[key] && prof[key].fit ? "画了" : "缺就说缺"}`);
  }
  if (prof.mode === "H" && prof.te && prof.te.pedestal) check(els.tte.innerHTML.includes("台基段") && els.tte.innerHTML.includes("ρ_e"), "H 模：T_e 的台基段与 ρ_e 标出来了");
  const tr = res.transport || {};
  check(els.tchi.innerHTML.includes("<svg") && count(els.tchi.innerHTML, /<path /g) >= 2, "χ_e 与 χ_i 两条曲线");
  const ninv = (v) => (v || []).filter((x) => !x).length;
  if (ninv(tr.valid_e)) check(els.tchi.innerHTML.includes("χ_e 无效") && els.tchinote.innerHTML.includes("判无效"), `χ_e 的 ${ninv(tr.valid_e)} 个无效点涂出来并写明`);
  if (ninv(tr.valid_i)) check(els.tchi.innerHTML.includes("χ_i 无效"), `χ_i 的 ${ninv(tr.valid_i)} 个无效点涂出来`);
  check(els.tchinote.innerHTML.includes("点有效"), "χ 的有效点数写出来了");
  const nterm = ["src_e", "src_i", "exchange", "rad", "ohm"].filter((k) => tr[k]).length;
  check(count(els.tsrc.innerHTML, /<path /g) >= nterm, `源 · 交换 · 辐射 · 欧姆 ${nterm} 条`);
  check(els.tjcd.innerHTML.includes("<path") && els.tjnote.innerHTML.includes("I_cd"), "驱动电流剖面与总量");
  const dep = ["lh", "ec"].filter((k) => (res.heating || {})[k] && res.heating[k].deposition).length;
  check(dep === 0 || els.tdep.innerHTML.includes("<path"), `LH / EC 沉积（${dep} 路）`);
  check(dep === 0 || els.tdepj.innerHTML.includes("<path"), "驱动电流密度沉积");
  check(els.tlh.innerHTML.includes("LH") && els.tec.innerHTML.includes("EC"), "LH 与 EC 的账两块都在");
  if ((res.heating || {}).ec && (res.heating.ec.skipped || []).length) check(els.tec.innerHTML.includes("没算的束"), "没算的 EC 束连同理由列出来");
  check(count(els.tfacts.innerHTML, /<tr>/g) >= Object.keys(tr.facts || {}).length - 4, "输运事实表");
  check((tr.notes || []).length === 0 || els.tfacts.innerHTML.includes("内核的注"), "内核的注原样印出");
  check(els.teq.innerHTML.includes("平衡") && els.teq.innerHTML.includes("<h3>"), "平衡与方法卡");
  check(els.tfoot.innerHTML.includes(res.app), "页脚带出处");
}

// ============================================================================== 不认的文件
console.log("\n--- 按名拒收");
const n0 = alerts.length;
check(ctx.KR.load('{"hello": 1}', "x.json") === false && alerts.length === n0 + 1, "没有 @type 的文件按名拒收");
check(ctx.KR.load('{"@type": "fylite:KineticReconMeasurements", "shot": 1}', "meas.json") === false && alerts.length === n0 + 2,
  "@type 是别的 fylite 文档（测量文档）也拒收");
check(alerts[alerts.length - 1].includes("fylite:Wei2026Profiles") && alerts[alerts.length - 1].includes("fylite:KineticReconSeries")
  && alerts[alerts.length - 1].includes("fylite:KefitSlices"), "拒收时说清了收哪五种");
if (lastType) check(ctx.KR.state.type === lastType, "拒收不动已经载入的那一份");

console.log(failed ? `\n${failed} 项失败` : "\n全部通过");
process.exit(failed ? 1 : 0);
