// 页面的 node 检查：把 kinetic_recon.html 的脚本在一个极小 DOM 垫片里真的跑一遍，喂一份结果 JSON，
// 断言每一块都画出了东西。
//
//   node test/smoke.mjs kinetic_recon.html <result.json>
//
// ★结果 JSON 带实验数据，不入仓——所以这道检查要调用方给一份（kinetic_recon.py run 的输出）。
// ★垫片只认 HTML 里真有的 id：脚本里拼错一个 id，这里当场报错，而不是在浏览器里静默画不出来。
import { readFileSync } from "node:fs";
import vm from "node:vm";

const [, , htmlPath, resultPath] = process.argv;
if (!htmlPath || !resultPath) {
  console.error("usage: node test/smoke.mjs kinetic_recon.html <result.json>");
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

const text = readFileSync(resultPath, "utf8");
const res = JSON.parse(text);
check(ctx.KR.load(text, "result.json") === true, "结果 JSON 载入");
check(alerts.length === 0, `没有弹窗（${alerts.join(" | ")}）`);
check(els.main.hidden === false && els.empty.hidden === true, "空状态收起、主区打开");
check(els.title.textContent.includes(String(res.shot)), "标题带炮号");

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

//: 缺档也得画得出来：只留 M
const onlyM = JSON.parse(text);
delete onlyM.tiers.K; delete onlyM.tiers.P;
check(ctx.KR.load(JSON.stringify(onlyM), "only-M.json") === true, "只有档 M 的结果也能载入");
check(els.kbody.innerHTML.includes("没跑档 K") && els.pbody.innerHTML.includes("没跑档 P"), "缺的档说「没跑」，不报错");
//: 不是结果文件：拒收，不画
check(ctx.KR.load('{"hello": 1}', "x.json") === false && alerts.length === 1, "不是结果文件就按名拒收");

console.log(failed ? `\n${failed} 项失败` : "\n全部通过");
process.exit(failed ? 1 : 0);
