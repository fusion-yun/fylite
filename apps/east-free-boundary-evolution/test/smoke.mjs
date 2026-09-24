// 页面的 node 检查：把 fb_evolution.html 的脚本在一个极小 DOM 垫片里真的跑一遍，喂一份份结果 JSON，
// 断言对应的那一页每一块都画出了东西。
//
//   node test/smoke.mjs fb_evolution.html <result.json> [更多.json …]
//
// 每个文件按它自己的 @type 走自己的一套断言：
//   fylite:EastFreeBoundaryEvolution  → 演化页（逐步走：截面 · 时间迹 · 被动丝 · 热图；步导航与键盘）
//   fylite:EastFreeBoundaryInitial    → 初始态页（边界叠画 · 对照表 · Z_anchor 扫描）
//   fylite:EastFreeBoundaryComparison → 比较页（成对表；两份 run 都在时，差随时间 + 与 compare 自己的数对上）
//   fylite:EastFreeBoundaryGeometry / fylite:EastFreeBoundaryCase / wall.json → 辅助文件（线圈 · 限制器 · 轮廓）
// 给了两份以上 run 时另查叠加；最后把全部文件当一次「拖入」再载一遍。
//
// ★结果 JSON 带实验数据，不入仓——所以这道检查要调用方给文件（fb_evolution.py 的输出目录）。
// ★垫片只认 HTML 里真有的 id：脚本里拼错一个 id，这里当场报错，而不是在浏览器里静默画不出来。
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import vm from "node:vm";

const [, , htmlPath, ...resultPaths] = process.argv;
if (!htmlPath || !resultPaths.length) {
  console.error("usage: node test/smoke.mjs fb_evolution.html <result.json> [更多.json …]");
  process.exit(2);
}
const html = readFileSync(htmlPath, "utf8");
const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join("\n");

function element(id) {
  const listeners = {};
  return {
    id, innerHTML: "", textContent: "", hidden: false, disabled: false, value: "", max: "", attrs: {},
    addEventListener(k, fn) { (listeners[k] ||= []).push(fn); },
    fire(k, ev) { for (const fn of listeners[k] || []) fn(ev || {}); },
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
const fireDoc = (k, ev) => { for (const fn of docListeners[k] || []) fn(ev); };
const store = {};
const alerts = [];
//: 同步的 FileReader：拖入的「文件」是 {name, text}
class FileReader { readAsText(fl) { this.result = fl.text; if (this.onload) this.onload(); } }
const ctx = {
  document, console, JSON, Math, Number, String, Array, Object, isFinite, parseFloat, Set, Infinity, NaN,
  localStorage: { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); } },
  alert: (m) => alerts.push(m), FileReader,
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(script, ctx, { filename: htmlPath });
const FB = ctx.FB, S = FB.state;

let failed = 0, passed = 0;
const check = (cond, what) => { console.log(`${cond ? "ok  " : "FAIL"} ${what}`); if (cond) passed++; else failed++; };
const count = (s, re) => (String(s).match(re) || []).length;
const clearEls = () => { for (const e of Object.values(els)) { e.innerHTML = ""; e.textContent = ""; } };
const ms = (fn) => { const t0 = performance.now(); fn(); return performance.now() - t0; };

//: 原理页：不要结果就能读，各节都在，页内目录每一条都指得到
check(/<div id="docview">/.test(html) && /<div id="resview" hidden>/.test(html), "打开时停在「原理与过程」（原理页可见、结果页 hidden）");
const sections = [...html.matchAll(/<h2 id="(d-[a-z]+)"/g)].map((m) => m[1]);
const navs = [...html.matchAll(/<a href="#(d-[a-z]+)"/g)].map((m) => m[1]);
check(sections.length >= 8, `原理页 ${sections.length} 节（${sections.join(" ")}）`);
check(navs.length === sections.length && navs.every((n) => sections.includes(n)) && new Set(navs).size === navs.length, "页内目录与各节一一对上");
check(sections.includes("d-circuit") && /<var>R<\/var><sub><var>k<\/var><\/sub> <var>I<\/var><sub><var>k<\/var><\/sub> \+ dΨ<sub><var>k<\/var><\/sub>\/d<var>t<\/var> = 0/.test(html), "回路方程 R_k I_k + dΨ_k/dt = 0 在原理页");
check(sections.includes("d-pair") && /虚拟竖直线圈对/.test(html), "虚拟线圈对有一节");
check((html.match(/<span class="n">\(\d+\)<\/span>/g) || []).length >= 8, "公式块带编号（≥ 8 条）");
check(!/https?:\/\//.test(html.replace(/<!--[\s\S]*?-->/g, "")), "页面不引任何网络资源");

// ============================================================================== 逐个文件
const files = resultPaths.map((p) => ({ path: p, name: basename(p), text: readFileSync(p, "utf8") }));
//: 辅助文件（case / wall）先载，限制器与轮廓才有得画——拖入时的次序无所谓，这里只为断言确定
const kindOf = (t) => { const m = t.slice(0, 300).match(/"@type":\s*"([^"]+)"/); return m ? m[1] : (/"tau_s"/.test(t) ? "wall" : "?"); };
const AUX = ["fylite:EastFreeBoundaryGeometry", "fylite:EastFreeBoundaryCase", "wall"];
files.sort((a, b) => (AUX.includes(kindOf(a.text)) ? 0 : 1) - (AUX.includes(kindOf(b.text)) ? 0 : 1));
const runs = [];
let cmpFile = null;
for (const fl of files) {
  const ty = kindOf(fl.text);
  console.log(`\n--- ${fl.path}  (${ty})`);
  clearEls();
  const before = alerts.length;
  let okLoad;
  const t = ms(() => { okLoad = FB.load(fl.text, fl.name); });
  check(okLoad === true, `载入（${t.toFixed(0)} ms，${(fl.text.length / 1e6).toFixed(1)} MB）`);
  check(alerts.length === before, `没有弹窗（${alerts.slice(before).join(" | ")}）`);
  check(els.resview.hidden === false && els.docview.hidden === true, "载入后切到「结果」页签");
  if (ty === "fylite:EastFreeBoundaryEvolution") { runs.push(fl); runChecks(fl); }
  else if (ty === "fylite:EastFreeBoundaryInitial") initChecks(fl);
  else if (ty === "fylite:EastFreeBoundaryComparison") cmpFile = fl;
  else if (ty === "fylite:EastFreeBoundaryCase") check(S.kase && S.kase.gfile && els.loaded.innerHTML.includes("case ·"), "case.json 记作辅助文件（限制器、g-file 边界）");
  else if (ty === "fylite:EastFreeBoundaryGeometry") {
    const g = JSON.parse(fl.text).geometry;
    check(S.geom && els.loaded.innerHTML.includes("geometry ·"), `geometry.json 记作辅助文件（${g.pf_coils.length} 个 PF 元素 · ${g.ic_coils.length} 个 IC · 限制器 ${g.limiter ? g.limiter.r.length : 0} 点）`);
    check(g.ic_coils.length === 2 && g.pf_coils.every((c) => [c.r, c.z, c.dr, c.dz].every(Number.isFinite)), "geometry.json：两个 IC，PF 元素都带 r · z · dr · dz");
  }
  else if (ty === "wall") check(S.wall && els.loaded.innerHTML.includes("wall ·"), "wall.json 按形状认作辅助文件");
  else check(false, `未知的 @type：${ty}（这道检查不认）`);
}
//: 比较页放到最后：那时 run 都载入了，差随时间才画得出
if (cmpFile) { console.log(`\n--- ${cmpFile.path}  (fylite:EastFreeBoundaryComparison，run 都载入之后)`); cmpChecks(cmpFile); }

// ============================================================================== 演化页
function runChecks(fl) {
  const res = JSON.parse(fl.text.replace(/([:\[,]\s*)(NaN|-?Infinity)(?=\s*[,\]}])/g, "$1null"));
  const i = S.runs.findIndex((r) => r.name === fl.name.replace(/\.json$/, ""));
  FB.setRuns(i, -1);
  const A = S.runs[S.a], n = res.time.length, m = res.sources.r.length;
  check(S.view === "evo" && els.evmain.hidden === false && els.inmain.hidden === true && els.cmmain.hidden === true, "开的是演化页");
  check(els.title.textContent.includes(String(res.shot)) && els.title.textContent.includes(res.passive), "标题带炮号与被动模式");
  check(els.evslider.max === String(n - 1), `滑条 ${n} 步`);
  check(els.evdiffcard.hidden === true, "没有叠加时不出差卡");
  //: 截面
  const xs = els.xs.innerHTML;
  check(count(xs, /class="fil"/g) === m, `截面画了 ${m} 根丝（${count(xs, /class="fil"/g)}）`);
  check(count(xs, /class="bndA"/g) === 1, "截面有这一步的边界");
  geometryChecks(res, xs);
  check(els.xslegend.innerHTML.includes("<linearGradient") && els.xslegend.innerHTML.includes("−"), "丝电流色标（发散，带量程）");
  //: 时间迹：每张都有曲线，光标在叠层里
  for (const tr of FB.TRACES) {
    const box = els[tr.id].innerHTML;
    check(box.includes("<path") || box.includes("结果里没有这一量"), `时间迹 #${tr.id}${box.includes("<path") ? "" : "（缺就说缺）"}`);
  }
  check(["t-ip", "t-ar", "t-az", "t-fb", "t-pas", "t-gs", "t-li", "t-bp"].every((id) => els[id].innerHTML.includes("<path")), "必备的八张时间迹都画出曲线");
  check(els["t-ip"].innerHTML.includes('stroke-dasharray="5 3"'), "I_p 图上有目标（虚线）");
  check(els["t-li"].innerHTML.includes("EFIT 迹"), "l_i 图上有 EFIT 迹");
  check(els["t-fb-c"].innerHTML.includes("<line") && els["t-ip-c"].innerHTML.includes("<line"), "时间光标画在叠层里");
  const nLim = res.scalars.bnd_kind.filter((v) => v === 0).length;
  check(nLim === 0 || els["t-ip"].innerHTML.includes("限制器位形"), `限制器位形的时段涂出来（${nLim} 步）`);
  const nBad = res.scalars.gs_state.filter((v) => v !== 2).length;
  check(nBad === 0 || count(els["t-gs"].innerHTML, /定住|未收敛也未定住/g) >= nBad, `GS 没收敛的 ${nBad} 步在残差图上打点`);
  if ((res.profile_segments || []).length > 1) check(els["t-li"].innerHTML.includes("efit-trend：新一段剖面的起点"), "efit-trend 的分段标在 l_i 图上");
  //: 被动丝与热图
  check(els["src-i"].innerHTML.includes("<path") && els["src-psi"].innerHTML.includes("<path"), "被动丝：这一步的电流与磁通");
  check(count(els["src-psi"].innerHTML, /<path /g) >= 3, "三种磁通（tot · ext · p）");
  check(els["src-i"].innerHTML.includes("轮廓 1"), "轮廓分界标在丝序号图上");
  const rects = count(els.hmap.innerHTML, /<rect /g);
  check(res.passive === "zero" ? rects >= 1 : rects > 50, `热图 ${rects} 块${res.passive === "zero" ? "（zero：全是底色）" : ""}`);
  check(els["hmap-c"].innerHTML.includes("<line"), "热图上的时间光标");
  check(count(els["t-ch"].innerHTML, /<path /g) >= (res.channels.names || []).length, `线圈通道安匝 ${res.channels.names.length} 条`);
  check(els.evwall.innerHTML.includes("轮廓") && (S.wall ? els.evwall.innerHTML.includes("L/R 时间") : els.evwall.innerHTML.includes("没有载入")), "被动丝回路卡（τ 或说缺 wall.json）");
  //: 设定与说明原样
  check(els.evopts.innerHTML.includes(res.kernel.sha256) && els.evopts.innerHTML.includes(res.passive), "设定卡：内核 sha256 · 被动模式");
  check(res.door.notes.every((x) => els.evnotes.innerHTML.includes(x.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"))), `门的 ${res.door.notes.length} 条说明原样印出`);
  check(els.evfoot.innerHTML.includes(res.app), "页脚带出处");
  //: 走步：两端顶住、越界夹回、键盘、ψ 等值线只在最后一步
  FB.goStep(0);
  check(els.evprev.disabled === true && els.evnext.disabled === false && els.evpos.textContent.includes(`第 1 / ${n} 步`), "第 0 步：上一步停用");
  check(els.evstate.innerHTML.includes("第 0 步不记"), "第 0 步的迭代数说明不记");
  check(!els.xsnote.textContent.includes("最后一步（psi_last_Wb）"), "中间步不画 ψ 等值线（只说只有最后一步）");
  const fx = { key: "ArrowRight", target: {}, preventDefault() {} };
  fireDoc("keydown", fx);
  check(S.k === 1, "→ 键进一步");
  fireDoc("keydown", Object.assign({}, fx, { shiftKey: true }));
  check(S.k === 11, "Shift → 进十步");
  fireDoc("keydown", Object.assign({}, fx, { key: "End" }));
  check(S.k === n - 1 && els.evnext.disabled === true, "End 到末步、下一步停用");
  const psiLines = count(els.xs.innerHTML, /stroke="var\(--flux\)"/g);
  check(psiLines > 50 && els.xsnote.textContent.includes("psi_last_Wb"), `末步画 ψ 等值线（${psiLines} 段，标明是 psi_last_Wb）`);
  check(count(els.xs.innerHTML, /opacity="0\.[0-9]+"/g) >= 10, "末步有之前各步边界的淡迹");
  FB.goStep(n + 99);
  check(S.k === n - 1, "越界的步号夹回范围内");
  //: 边界种类在状态行里
  const kl = res.scalars.bnd_kind.indexOf(0), kx = res.scalars.bnd_kind.indexOf(1);
  if (kl >= 0) { FB.goStep(kl); check(els.evstate.innerHTML.includes("限制器位形"), `第 ${kl} 步（限制器）状态行写明`); }
  if (kx >= 0) { FB.goStep(kx); check(els.evstate.innerHTML.includes("X 点位形") && els.xs.innerHTML.includes("X 点（边界由它定）"), `第 ${kx} 步（X 点）状态行与截面都标了`); }
  const ks = res.scalars.gs_state.indexOf(1);
  if (ks >= 0) { FB.goStep(ks); check(els.evstate.innerHTML.includes("定住"), `第 ${ks} 步（定住）照说`); }
  //: 快：走 60 步，每步只重画截面、被动丝两张图与光标
  const dt = ms(() => { for (let k = 0; k < 60; k++) FB.goStep(Math.floor(k * (n - 1) / 59)); }) / 60;
  check(dt < 60, `换一步 ${dt.toFixed(1)} ms（node 里，含截面与被动丝两张图）`);
}

//: 线圈与限制器：结果文件的 geometry 块 → geometry.json → 缺（照说）
function geometryChecks(res, xs) {
  const geo = res.geometry || (S.geom && S.geom.geometry);
  if (geo && geo.pf_coils) {
    check(count(xs, /class="coil"/g) === geo.pf_coils.length, `截面画了 ${geo.pf_coils.length} 个 PF 元素（${count(xs, /class="coil"/g)}）`);
    check(count(xs, /class="ic"/g) === 2, "截面画了 2 个 IC 线圈");
    const nfig = geo.ic_coils.filter((c) => c.figure_rz).length;
    check(count(xs, /class="icfig"/g) === nfig, `附图上的 IC 位置画成虚框（${nfig}，未用）`);
    check(els.xscoil.innerHTML.includes("取装置事实") && els.xscoil.innerHTML.includes("← facts") !== !!(res.options && res.options.ic_rz), "说明线圈取装置事实、IC 位置从哪来");
    check(els.xslegend.innerHTML.includes("kA·匝"), "线圈安匝色标（与丝的分开）");
    const fill = (xs.match(/<rect class="coil"[^>]*fill="([^"]+)"/g) || []).filter((m) => /var\(--(pos|neg)\)/.test(m)).length;
    check(fill > 0, `PF 线圈按通道安匝着色（${fill} 个非零）`);
  } else check(els.xscoil.innerHTML.includes("缺线圈") && count(xs, /class="coil"/g) === 0, "没有几何：不画线圈，说缺什么、怎么补");
  const lim = geo && geo.limiter ? geo.limiter : res.limiter ? res.limiter : S.kase ? { r: S.kase.gfile.rlim } : null;
  if (lim) {
    const m = xs.match(/<path d="([^"]+)" fill="none" stroke="var\(--wall\)" stroke-width="1.6"/);
    const nv = m ? (m[1].match(/[ML]/g) || []).length : 0;
    check(nv === lim.r.length && els.xslegend.innerHTML.includes("限制器（"), `画了限制器（${nv} / ${lim.r.length} 个顶点）`);
  } else check(els.xslegend.innerHTML.includes("没有限制器"), "没有限制器就说没有");
}

//: 旧的 run 文件、又没拖 geometry.json：照样画，说缺什么
function noGeometryChecks() {
  if (!runs.length) return;
  console.log("\n--- 没有几何的 run");
  const keep = [S.geom, S.kase];
  S.geom = null; S.kase = null;
  const R = S.runs[0], had = R.res.geometry, hadLim = R.res.limiter;
  delete R.res.geometry; delete R.res.limiter; R.cache.xs = null;
  FB.setRuns(0, -1); FB.goStep(0);
  check(count(els.xs.innerHTML, /class="fil"/g) === R.m && count(els.xs.innerHTML, /class="bndA"/g) === 1, "没有几何也照画丝与边界");
  check(count(els.xs.innerHTML, /class="coil"|class="ic"/g) === 0 && els.xscoil.innerHTML.includes("缺线圈") && els.xscoil.innerHTML.includes("fb_evolution.py geometry"), "说缺线圈、给出补的命令");
  check(els.xslegend.innerHTML.includes("没有限制器"), "说没有限制器");
  if (had) R.res.geometry = had; if (hadLim) R.res.limiter = hadLim;
  [S.geom, S.kase] = keep; R.cache.xs = null; FB.render();
}

// ============================================================================== 叠加
function overlayChecks() {
  if (runs.length < 2) { console.log("\n（只给了一份 run：跳过叠加）"); return; }
  console.log("\n--- 叠加");
  const named = (s) => S.runs.findIndex((r) => r.name === s);
  //: 挑一对时间网格一样的（优先 zero vs induced），再挑一对不一样的（1 ms 的检查）
  let a = named("run_zero"), b = named("run_induced");
  if (a < 0 || b < 0) { a = 0; b = 1; }
  FB.setRuns(a, b);
  const A = S.runs[a], B = S.runs[b];
  check(els.evdiffcard.hidden === false, `${A.name} 上叠 ${B.name}：出差卡`);
  check(count(els.xs.innerHTML, /class="bndB"/g) === 1 && els.xslegend.innerHTML.includes("叠加"), "截面上叠了第二条边界");
  check(els["t-ar"].innerHTML.includes("var(--rB)") && els["t-ip"].innerHTML.includes("var(--rB)"), "时间迹叠了第二种颜色");
  check(["d-ax", "d-bd", "d-psi", "d-sum"].every((id) => els[id].innerHTML.includes("<path")), "差卡四张图（磁轴 · 边界 · 丝磁通 · 丝电流之和）");
  const d = FB.pairDiff(A, B);
  check(d.matched === Math.min(A.n, B.n) || els.evdiffnote.textContent.includes(`${d.matched} / ${A.n}`), `按时刻对上 ${d.matched} 步并写明`);
  check(els.evstate.innerHTML.includes("叠加"), "状态行两份都写");
  FB.goStep(Math.floor(A.n / 2));
  check(els["d-ax-c"].innerHTML.includes("<line"), "差卡上也有时间光标");
  //: 按钮：点「无」取消叠加
  els.runB.fire("click", { target: { closest: () => ({ getAttribute: () => "-1", disabled: false }) } });
  check(S.b === -1 && els.evdiffcard.hidden === true, "点「无」取消叠加");
  //: 时间网格不同的一对：只比对得上的时刻
  const odd = S.runs.findIndex((r) => Math.abs(r.dtmin - A.dtmin) > 1e-6);
  if (odd >= 0) {
    FB.setRuns(a, odd);
    const dd = FB.pairDiff(A, S.runs[odd]);
    check(dd.matched > 0 && dd.matched < A.n && els.evdiffnote.textContent.includes("对不上的时刻不比"), `步长不同（${S.runs[odd].name}）：只比对得上的 ${dd.matched} 步`);
    FB.goStep(A.n - 1);
    check(S.runs[odd].res.time[S.runs[odd].n - 1] < A.res.time[A.n - 1] - 1e-6 ? els.evstate.innerHTML.includes("这个时刻没有步") : true, "叠加那份在这个时刻没有步：照说");
  }
  FB.setRuns(a, -1);
}
overlayChecks();
noGeometryChecks();

// ============================================================================== 初始态页
function initChecks(fl) {
  const res = JSON.parse(fl.text);
  const V = Object.keys(res.variants);
  check(S.view === "init" && els.inmain.hidden === false && els.evmain.hidden === true, "开的是初始态页");
  check(els.title.textContent.includes(String(res.shot)), "标题带炮号");
  check(count(els.inxs.innerHTML, /class="bndV"/g) === V.length, `截面叠画 ${V.length} 个解的边界`);
  const hasRef = !!((res.reference && res.reference.boundary) || S.kase);
  check(hasRef ? count(els.inxs.innerHTML, /class="bndRef"/g) === 1 : els.inlegend.innerHTML.includes("没有参考边界"), hasRef ? "画了参考边界（g-file）" : "没有参考边界就说没有");
  const geo = res.geometry || (S.geom && S.geom.geometry);
  check(geo && geo.pf_coils ? count(els.inxs.innerHTML, /class="coil"/g) === geo.pf_coils.length && count(els.inxs.innerHTML, /class="ic"/g) === 2 : els.inlegend.innerHTML.includes("缺线圈"),
    geo ? "初始态截面也画了 PF / IC 线圈" : "初始态：没有几何就说缺线圈");
  const tb = els.intable.innerHTML;
  for (const lab of ["q_95", "l_i(1) 同尺", "β_p 同尺", "磁轴距离", "边界距离", "ψ_N 图之差"]) check(tb.includes(lab), `对照表有「${lab}」`);
  for (const v of V) { const c = res.variants[v].compare; check(tb.includes(((c.q95 || {}).ours).toFixed(3)) && tb.includes((c.axis_distance_m * 100).toFixed(2)), `${v}：q_95 与磁轴距离照数填进表`); }
  check(count(els.inscan.innerHTML, /<circle /g) >= V.reduce((a, v) => a + ((res.variants[v].zc_search || {}).scan || []).length, 0), "Z_anchor 扫描的每个点都画了");
  check(V.every((v) => (res.variants[v].notes || []).every((x) => els.innotes.innerHTML.includes(x.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")))), "各解的说明原样");
}

// ============================================================================== 比较页
function cmpChecks(fl) {
  clearEls();
  check(FB.load(fl.text, fl.name) === true, "载入");
  const res = JSON.parse(fl.text), pairs = Object.keys(res.pairs || {});
  check(S.view === "cmp" && els.cmmain.hidden === false, "开的是比较页");
  check(count(els.cmpairs.innerHTML, /<tr/g) === pairs.length + 1, `成对表 ${pairs.length} 行`);
  check(count(els.cmbars.innerHTML, /<rect /g) >= pairs.length, "成对的差画成横条");
  check(count(els.cmruns.innerHTML, /<tr>/g) >= Object.keys(res.runs || {}).length, "各 run 摘要表");
  const loaded = (nm) => S.runs.some((r) => r.name === nm);
  const full = pairs.filter((k) => k.split(" vs ").every(loaded));
  check(full.length === 0 || els.cmpairs.innerHTML.includes("叠加到演化页"), `两份都载入的 ${full.length} 对可以叠加`);
  const miss = pairs.filter((k) => !k.split(" vs ").every(loaded));
  check(miss.length === 0 || els.cmpairs.innerHTML.includes("缺 "), `缺 run 的 ${miss.length} 对写明缺哪份`);
  //: 同一个解（prescribed 回放 induced）要认出来
  const same = pairs.filter((k) => res.pairs[k].axis_shift_max_m < 1e-6 && res.pairs[k].boundary_distance_max_m < 1e-6);
  check(count(els.cmpairs.innerHTML, /同一个解/g) === same.length, `认出 ${same.length} 对是同一个解`);
  for (const key of full.slice(0, 3)) {
    S.pair = key; FB.render();
    check(["c-ax", "c-bd", "c-psi", "c-sum"].every((id) => els[id].innerHTML.includes("<path") || els[id].innerHTML.includes("对不上")), `「${key}」差随时间四张图`);
    //: 与 compare 自己的数对上：同一个边界距离定义、同一组时刻（每 n/40 步）
    const [x, y] = key.split(" vs ").map((nm) => S.runs.find((r) => r.name === nm));
    const n = Math.min(x.n, y.n), p = res.pairs[key];
    let dax = 0, dbd = 0;
    for (let k = 0; k < n; k++) dax = Math.max(dax, Math.hypot(x.s.axis_r[k] - y.s.axis_r[k], x.s.axis_z[k] - y.s.axis_z[k]));
    for (let k = 0; k < n; k += Math.max(1, Math.floor(n / 40))) dbd = Math.max(dbd, FB.bdist(x.res.boundary[k], y.res.boundary[k]).max_m);
    const close = (u, v) => Math.abs(u - v) <= 1e-9 + 1e-6 * Math.abs(v);
    check(close(dax, p.axis_shift_max_m) && close(dbd, p.boundary_distance_max_m), `「${key}」页面算的磁轴移动 ${(dax * 100).toFixed(3)} cm · 边界距离 ${(dbd * 100).toFixed(3)} cm = compare 的`);
  }
  if (full.length) {
    const key = full[0];
    els.cmpairs.fire("click", { target: { closest: (sel) => sel === "button[data-overlay]" ? { getAttribute: () => key } : null } });
    check(S.view === "evo" && S.b >= 0 && els.evdiffcard.hidden === false, `「叠加到演化页」：${key} 叠上`);
    FB.setView("cmp");
  }
  check(els.cmfoot.innerHTML.includes(res.app), "页脚带出处");
}

// ============================================================================== 一次拖入全部
console.log("\n--- 一次拖入全部文件");
{
  const n0 = alerts.length, k0 = S.runs.length;
  clearEls();
  fireDoc("drop", { preventDefault() {}, dataTransfer: { files: files.map((x) => ({ name: x.name, text: x.text })) } });
  check(alerts.length === n0, `拖入 ${files.length} 份没有弹窗`);
  check(S.runs.length === k0 && runs.length === k0, `同名的 run 替换、不重复（${S.runs.length} 份）`);
  check(runs.length === 0 || (S.view === "evo" && els.evmain.hidden === false), "拖进来有 run 就停在演化页");
  check(els.fname.textContent.length > 0 && els.loaded.innerHTML.includes("已载入"), "载入的文件列出来");
}

// ============================================================================== 不认的文件
console.log("\n--- 按名拒收");
{
  const n0 = alerts.length, a0 = S.a, r0 = S.runs.length;
  check(FB.load('{"hello": 1}', "x.json") === false && alerts.length === n0 + 1, "没有 @type 的文件按名拒收");
  check(FB.load('{"@type": "fylite:KineticReconResult", "shot": 1, "tiers": {}}', "kr.json") === false && alerts.length === n0 + 2,
    "@type 是别的 fylite 文档（动理学反演结果）也拒收");
  const msg = alerts[alerts.length - 1];
  check(msg.includes("fylite:KineticReconResult") && ["fylite:EastFreeBoundaryEvolution", "fylite:EastFreeBoundaryInitial", "fylite:EastFreeBoundaryComparison"].every((t) => msg.includes(t)),
    "拒收时说出它是什么、本页收哪几种");
  check(FB.load("{not json", "bad.json") === false && alerts.length === n0 + 3, "不是 JSON 也照说");
  check(FB.load('{"@type": "fylite:EastFreeBoundaryEvolution", "shot": 1}', "empty.json") === false && alerts[alerts.length - 1].includes("缺"), "@type 对但缺块：说缺什么");
  check(S.a === a0 && S.runs.length === r0, "拒收不动已经载入的");
}

console.log(failed ? `\n${passed} 项通过，${failed} 项失败` : `\n全部 ${passed} 项通过`);
process.exit(failed ? 1 : 0);
