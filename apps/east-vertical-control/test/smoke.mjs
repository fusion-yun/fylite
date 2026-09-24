// 页面的 node 检查：把 vs_control.html 的脚本在一个极小 DOM 垫片里真跑一遍，喂 vs_control.py 的结果 JSON，
// 把每个控件的每一档都拨一遍，断言每一块都画出了东西、没有一处抛异常。
//
//   node test/smoke.mjs vs_control.html <result.json>
//
// ★结果 JSON 带实验数据，不入仓——所以这道检查要调用方给文件。
// ★垫片只认 HTML 里真有的 id：脚本里拼错一个选择器，这里当场报错，而不是在浏览器里静默画不出来。
// ★颜色 token 从页面自己的 :root 块读——脚本里引用一个没定义的 token，这里也当场报错。
import { readFileSync } from "node:fs";
import vm from "node:vm";

const [, , htmlPath, resultPath] = process.argv;
if (!htmlPath || !resultPath) { console.error("usage: node test/smoke.mjs vs_control.html <result.json>"); process.exit(2); }
const html = readFileSync(htmlPath, "utf8");
const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join("\n");
const rootBlock = html.match(/:root\s*\{([\s\S]*?)\}/)[1];
const tokens = Object.fromEntries([...rootBlock.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));

let made = 0;
function node(tag, id) {
  const listeners = {};
  const e = {
    tag, id, children: [], attrs: {}, _html: "", textContent: "", hidden: false, value: "", max: "",
    dataset: {}, style: {}, parent: null,
    classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); } },
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); this.children = []; },
    insertAdjacentHTML(_w, v) { this._html += v; },
    appendChild(c) { c.parent = this; this.children.push(c); return c; },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter((x) => x !== this); },
    setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; },
    addEventListener(k, fn) { (listeners[k] ||= []).push(fn); },
    fire(k, ev) { for (const fn of listeners[k] || []) fn(ev || { clientX: 10, clientY: 10, preventDefault() {} }); },
    querySelector(sel) { const cls = sel.replace(/^\./, ""); const walk = (n) => { for (const c of n.children) { if ((c.attrs.class || "").split(" ").includes(cls)) return c; const r = walk(c); if (r) return r; } return null; }; return walk(this); },
    getBoundingClientRect() { return { left: 0, top: 0, width: 600, height: 300 }; },
  };
  made++;
  return e;
}
const byId = {};
//: 静态 <select> 的初值与浏览器一样：带 selected 的那一项，否则第一项
for (const m of html.matchAll(/<select id="([^"]+)">([\s\S]*?)<\/select>/g)) {
  const opts = [...m[2].matchAll(/<option(?: value="([^"]*)")?( selected)?>([^<]*)<\/option>/g)];
  if (!opts.length) continue;
  const pick = opts.find((o) => o[2]) || opts[0];
  (byId[m[1]] = node("select", m[1])).value = pick[1] ?? pick[3];
}
const document = {
  querySelector(sel) {
    if (!sel.startsWith("#")) throw new Error(`the script asks for ${sel}; the shim only knows #ids`);
    const id = sel.slice(1);
    if (!ids.has(id)) throw new Error(`the script asks for #${id}, which the page does not have`);
    return (byId[id] ||= node("div", id));
  },
  createElementNS(_ns, tag) { return node(tag); },
  documentElement: node("html"), body: node("body"),
  addEventListener() {},
};
const ctx = {
  document, console, JSON, Math, Number, String, Array, Object, isFinite, Set, Infinity, NaN, parseInt, Promise,
  localStorage: { _s: {}, getItem(k) { return this._s[k] ?? null; }, setItem(k, v) { this._s[k] = String(v); }, removeItem(k) { delete this._s[k]; } },
  getComputedStyle: () => ({ getPropertyValue: (v) => { if (!(v in tokens)) throw new Error(`colour token ${v} is not defined in :root`); return tokens[v]; } }),
  setInterval: () => 1, clearInterval: () => {},
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(script + "\n;globalThis.__accept = accept; globalThis.__renderAll = renderAll;", ctx, { filename: htmlPath });

const D = JSON.parse(readFileSync(resultPath, "utf8"));
const fails = [];
const check = (ok, what) => { if (!ok) fails.push(what); };
const svgCount = (id) => { const h = byId[id]; if (!h) return 0; const walk = (n) => n.children.reduce((a, c) => a + 1 + walk(c), 0); return walk(h); };

// 拒收
ctx.__accept({ "@type": "fylite:SomethingElse" }, "other.json");
check(byId.loaded.textContent.includes("不是 vs_control.py 的结果"), "a foreign @type is not refused by name");

ctx.__accept(D, "result.json");
check(byId.res.hidden === false && byId.empty.hidden === true, "the result pane does not open");
check(byId.kpis.innerHTML.includes("开环增长率"), "the readouts are missing");
for (const id of ["xs", "c-xi", "c-u", "c-i", "gm", "pareto", "dsw", "poles"]) check(svgCount(id) > 5, `#${id} drew nothing`);
check(byId["t-plant"].innerHTML.includes("接线判据"), "the plant table lacks the wiring check");
check(byId["t-cases"].innerHTML.split("<tr>").length - 2 === D.simulations.length, "the case table does not list every case");
if (D.wall_scan) for (const id of ["ws-v", "ws-e"]) check(svgCount(id) > 5, `#${id} drew nothing`);
else check(byId["ws-v"].innerHTML.includes("--no-scan"), "a run without the wall scan does not say so");

// 每个工况 × 每种视图 × 首末帧
for (let c = 0; c < D.simulations.length; c++) {
  byId.case.value = String(c); byId.case.onchange();
  for (const v of ["sim", "mode"]) {
    byId.view.value = v; byId.view.onchange();
    for (const f of [0, D.simulations[c].frames.t.length - 1]) {
      byId.frame.value = String(f); byId.frame.oninput();
      check(svgCount("xs") > D.geometry.passive.length, `case ${c} view ${v} frame ${f}: the cross-section lost its passive elements`);
    }
  }
}
// 每张增益图 × 每种着色
for (let g = 0; g < D.controller.gain_maps.length; g++) {
  byId.dsel.value = String(g);
  for (const q of ["settle_s", "u_peak_V", "max_re"]) {
    byId.gq.value = q; byId.dsel.onchange();
    const want = D.controller.gain_maps[g].kp.length * D.controller.gain_maps[g].kd.length;
    check(svgCount("gm") >= want, `gain map ${g} (${q}) drew ${svgCount("gm")} of ${want} cells`);
  }
}
// 播放、放大、风格
byId.play.onclick(); byId.play.onclick();
for (const m of ["1", "100"]) { byId.mag.value = m; byId.mag.onchange(); }
byId.theme.onclick(); byId.theme.onclick(); byId.theme.onclick();
// 悬停：每张图的命中层都触发一次
let hovered = 0;
const hoverAll = (n) => { for (const c of n.children) { c.fire("mousemove"); c.fire("mouseleave"); hovered++; hoverAll(c); } };
for (const id of ["xs", "c-xi", "gm", "pareto", "dsw", "poles"]) hoverAll(byId[id]);

if (fails.length) { console.error("FAIL\n  " + fails.join("\n  ")); process.exit(1); }
console.log(`ok — ${D.simulations.length} cases · ${D.controller.gain_maps.length} gain maps · ${made} nodes · ${hovered} hovers · wall scan ${D.wall_scan ? "yes" : "no"}`);
