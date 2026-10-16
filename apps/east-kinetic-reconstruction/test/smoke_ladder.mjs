// 阶梯页的 node 检查：把 kinetic_ladder.html 的脚本在一个极小 DOM 垫片里真的跑一遍，喂结果 · 时间序列 · 比较 JSON 与 g-file，
// 断言三区（输入 · 边界 · 输出）与批量表都画出了东西，改输入会把受影响的档标成过期、且不自动重跑。
//
//   node test/smoke_ladder.mjs kinetic_ladder.html <文件> [更多文件 …]
//
// 文件按内容认：@type 为 fylite:KineticReconResult / KineticReconSeries / KineticReconComparison / KineticReconInput 的 JSON，
// 或 G-EQDSK 文本。★结果 JSON 带实验数据，不入仓——所以这道检查要调用方给文件。
// ★垫片只认 HTML 里真有的 id：脚本里拼错一个 id，这里当场报错，而不是在浏览器里静默画不出来。
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import vm from "node:vm";

const [, , htmlPath, ...paths] = process.argv;
if (!htmlPath || !paths.length) {
  console.error("usage: node test/smoke_ladder.mjs kinetic_ladder.html <file> [more …]");
  process.exit(2);
}
const html = readFileSync(htmlPath, "utf8");
const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join("\n");

function element(id) {
  const listeners = {};
  return {
    id, innerHTML: "", textContent: "", hidden: false, attrs: {}, dataset: {},
    addEventListener(k, fn) { (listeners[k] ||= []).push(fn); },
    fire(k, ev) { for (const fn of listeners[k] || []) fn(ev); },
    setAttribute(k, v) { this.attrs[k] = String(v); }, removeAttribute(k) { delete this.attrs[k]; },
    getAttribute(k) { return this.attrs[k]; },
  };
}
const els = {};
const document = {
  getElementById(id) {
    if (!ids.has(id)) throw new Error(`the script asks for #${id}, which the page does not have`);
    return (els[id] ||= element(id));
  },
  documentElement: element("html"),
  addEventListener() {},
};
const alerts = [];
const ctx = {
  document, console, JSON, Math, Number, String, Array, Object, Set, isFinite, parseFloat,
  localStorage: { getItem: () => null, setItem: () => {} },
  alert: (m) => alerts.push(m), FileReader: class {}, setTimeout,
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(script, ctx, { filename: htmlPath });

let failed = 0;
const check = (cond, what) => { console.log(`${cond ? "ok  " : "FAIL"} ${what}`); if (!cond) failed++; };
const count = (s, re) => (String(s).match(re) || []).length;

check(!els.empty.hidden && els.zones.hidden, "empty state: intro shown, zones hidden");

const kinds = [];
let resultsText = "";
for (const p of paths) {
  const text = readFileSync(p, "utf8");
  const k = ctx.loadText(text, basename(p));
  kinds.push(k);
  if (k === "result") resultsText += text;
}
ctx.render();
console.log(`loaded: ${kinds.join(", ")}`);

check(els.empty.hidden && !els.zones.hidden && !els.batchwrap.hidden, "zones and batch shown after loading");
check(count(els.strip.innerHTML, /<circle data-i=/g) >= 1, "time strip draws one marker per slice");
check(count(els.btab.innerHTML, /<tr data-i=/g) >= 1, "batch table has a row per slice");
check(/<path d="M/.test(els.traces.innerHTML) || /<circle/.test(els.traces.innerHTML), "slice traces drawn");

if (kinds.includes("result")) {
  // 找一片结果（不是时间序列）来查三区
  const n = count(els.btab.innerHTML, /<tr data-i=/g);
  let found = false;
  for (let i = 0; i < n && !found; i++) {
    ctx.go(i);
    if (/档 [MKPDQX]/.test(els.consnote.textContent || "")) found = true;
  }
  check(found, "a result slice selected");
  check(/<path d="M[^"]+Z"/.test(els.xs.innerHTML), "cross-section: limiter / LCFS paths");
  check(count(els.xs.innerHTML, /<line x1=/g) > 50, "cross-section: ψ_N contours inside the LCFS");
  check(count(els.prof.innerHTML, /<svg /g) === 6, "six profile panels (q · p · ⟨J_φ⟩ · Tₑ · p′ · FF′)");
  const svgs = els.prof.innerHTML.split("<svg ").slice(1);
  const withJ = kinds.includes("result") && /jphi/.test(resultsText);
  if (withJ) check(/<path d="M/.test(svgs[2]) && !/没有数据/.test(svgs[2]), "⟨J_φ⟩ panel drawn from profiles.jphi");
  else check(/没有 ⟨J_φ⟩|没有数据/.test(els.proflegend.innerHTML + svgs[2]), "old result: ⟨J_φ⟩ absence said");
  if (/thomson_points/.test(resultsText)) check(count(svgs[3], /<circle/g) >= 3 && /Tₑ 门过/.test(els.proflegend.innerHTML), "Tₑ panel: Thomson mapped by the tiers, gate counts stated");
  if (/q0_sigma"\s*:\s*[0-9.]/.test(resultsText)) check(/q₀ = [0-9.]+ ± [0-9.]+/.test(els.q0card.innerHTML) || /带：\S/.test(els.q0card.innerHTML), "q₀ card shows the band, or says why the main tier has none");
  else if (/q0_sigma_note/.test(resultsText)) check(/带：/.test(els.q0card.innerHTML), "q₀ card says why there is no band");
  check(/tchip/.test(els.ltab.innerHTML) && /q₀/.test(els.ltab.innerHTML), "ladder table: tier columns and rows");
  check(/没跑：内核(无|没有) MSE/.test(els.ltab.innerHTML), "ladder table: tier S says why it did not run");
  check(/对 [MK]/.test(els.ltab.innerHTML) || count(els.ltab.innerHTML, /<th>/g) <= 3, "ladder table: deltas are against the tier below");
  check(/收敛|不物理|未收敛|没有一档/.test(els.conv.innerHTML), "boundary: convergence line first");
  check(/q₀ = /.test(els.q0card.innerHTML), "boundary: q₀ card");
  if (/"blocks"\s*:/.test(resultsText)) {
    check(/tag">磁 · measurement/.test(els.cons.innerHTML), "boundary: constraint blocks listed from the record");
    check(/留作校验/.test(els.vals.innerHTML), "boundary: held-out diagnostics listed");
    check(/磁相容性/.test(els.ltab.innerHTML), "ladder table: magnetics compatibility row");
  }
  if (/"sawtooth"\s*:\s*\{"status"\s*:\s*"ok"/.test(resultsText) || /"status":"ok","tol_m"|"inversion"\s*:/.test(resultsText)) {
    check(/锯齿 q=1 面/.test(els.vals.innerHTML) && /data-verdict="(pass|fail|inconclusive)"/.test(els.vals.innerHTML), "boundary: sawtooth check gives a verdict (ECE + SXR in the result)");
    check(/R_inv \d/.test(els.q0card.innerHTML), "q₀ card: inversion radius");
    check(/锯齿反转半径（ECE）/.test(els.xslegend.innerHTML), "cross-section: inversion-radius tick");
  } else check(/data-verdict="unevaluated"/.test(els.vals.innerHTML), "boundary: sawtooth check is unevaluated (no ECE / SXR in the result)");
  check(/kinetic_recon\.py run/.test(els.cmd.innerHTML), "input: today's command written out");
  check(/数据源|磁通环/.test(els.src.innerHTML), "input: data sources listed");

  // 改基 → 全部档过期；不自动重跑（结果照留）
  const before = els.ltab.innerHTML;
  els.bas.fire("change", { target: { id: "basissel", value: "kin-3-2", dataset: {} } });
  check(/◌/.test(els.ltab.innerHTML) || /过期/.test(els.warns.innerHTML), "changing the basis marks tiers stale");
  check(/改过/.test(els.cfgchip.textContent), "config chip counts the changed keys");
  check(count(els.ltab.innerHTML, /q₀/g) === count(before, /q₀/g), "results stay on the page (no auto re-run)");
  els.bas.fire("change", { target: { id: "basissel", value: "efit-1-2", dataset: {} } });
}
if (kinds.includes("gfile")) check(/对照/.test(els.xslegend.innerHTML) || /对照/.test(els.ltab.innerHTML), "g-file drawn as a reference");
check(!alerts.length, `no alerts${alerts.length ? ": " + alerts.join(" | ") : ""}`);

console.log(failed ? `${failed} check(s) FAILED` : "all checks passed");
process.exit(failed ? 1 : 0);
