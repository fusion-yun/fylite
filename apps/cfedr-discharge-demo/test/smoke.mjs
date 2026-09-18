import fs from "fs";
import vm from "vm";
import { makeDom } from "./domshim.mjs";
const SLOT = 'var FY_DATA = null; // FY_DATA_SLOT';
function inject(js, D) {
  const n = js.split(SLOT).length - 1;
  if (n !== 1) throw new Error(`数据槽出现 ${n} 次，应为 1`);
  return js.replace(SLOT, "var FY_DATA = " + JSON.stringify(D) + ";");
}

const [tplPath, dataPath, runPath0] = process.argv.slice(2);
//: 2026-09-17：页面成了单文件（没有数据槽），于是「演示数据」不再注入，而是加载后调
//: `loadOutput` 喂进去——与用户点「导入」走的是同一条路。
const runPath = (dataPath && dataPath !== "-" && !runPath0) ? dataPath : runPath0;
const tpl = fs.readFileSync(tplPath, "utf8");
const js = tpl.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
const D = (dataPath && dataPath !== "-" && fs.existsSync(dataPath)) ? JSON.parse(fs.readFileSync(dataPath, "utf8")) : {};

const { document, localStorage, store } = makeDom();
const sandbox = {
  document, localStorage, console,
  navigator: { clipboard: { writeText: async () => {} } },
  URL: { createObjectURL: () => "blob:x", revokeObjectURL() {} },
  Blob: class { constructor() {} },
  FileReader: class { readAsText() {} },
  setTimeout: () => 0, JSON, Math, Number, Object, Array, Set, Map, String, isFinite, parseFloat, WebAssembly,
};
sandbox.window = sandbox; sandbox.globalThis = sandbox;
const src = (js.includes(SLOT) && dataPath && dataPath !== "-") ? inject(js, D) : js;
vm.createContext(sandbox);
vm.runInContext(src, sandbox, { filename: "studio.js" });
if (runPath) sandbox.loadOutput(fs.readFileSync(runPath, "utf8"), runPath.split("/").pop());

// —— 断言：初始化把该画的都画了 ——
const html = id => store.get(id)?.innerHTML || store.get(id)?.textContent || "";
const checks = [
  ["波形有可拖控制点", /class="h"/.test(html("wave"))],
  ["波形有节点竖线", /class="pick"/.test(html("wave"))],
  //: 端点手柄的 class 是 `pt end`，中间的是 `pt`——所以这里按前缀匹配
  ["截面有控制点", /class="pt[ "]/.test(html("xs"))],
  //: 截面只读：线段画得出来，手柄一个都没有
  ["截面只读（无手柄）", !/cursor:grab/.test(html("xs")) && !/data-drag/.test(html("xs"))],
  ["截面有控制点轨迹", /polyline/.test(html("xs"))],
  ["按曲线重采样按钮", !!store.get("bnd-resample")],
  ["Miller 参数波形（可编）", /class="mh"/.test(html("millwave")) && /class="mpick"/.test(html("millwave"))],
  ["输入已就绪（不再在页面上堆 JSON）", (html("gen-note") || store.get("gen-note")?.textContent || "").includes("已就绪")],
];
if (runPath) {
  checks.push(["0-D 时序图", html("traces").includes("<svg")]);
  const RUN = JSON.parse(fs.readFileSync(runPath, "utf8"));
  const hasPF = (RUN.pf_current || []).some(r => (r || []).length);
  checks.push([`PF 波形图（${hasPF ? "有电流" : "无电流→应给说明"}）`,
    hasPF ? html("pfwave").length > 200 && html("pfwave-legend").includes("<span") : html("pfwave").includes("没有 PF 电流")]);
  checks.push(["位形图", html("eqxs").includes("polygon")]);
  //: ★2026-09-17 排版改按报告页：温度与密度**常驻看图区**（`prof-t` / `prof-n`），
  //: 下面那一栏只画 `meta.profiles` 的其余通道；相位芯片是新的一行。
  checks.push(["温度剖面常驻", html("prof-t").includes("<svg")]);
  checks.push(["密度剖面常驻", html("prof-n").includes("<svg")]);
  checks.push(["相位芯片", html("out-chips").includes("<button") || html("out-chips").includes("没有相位")]);
  checks.push(["一维通道芯片", html("prof-chips").includes("input")]);
  checks.push(["一维小多图", html("profs").includes("<svg")]);
  checks.push(["导出按钮已启用", store.get("save-gfile")?.disabled === false]);
}
let bad = 0;
for (const [name, ok] of checks) { if (!ok) bad++; console.log(`${ok ? "ok  " : "FAIL"} ${name}`); }

// —— 导出路径：切片与 g-file 真的写得出来吗 ——
if (runPath) {
  //: 取哪一片：短时序（几步的冒烟文件）里没有第 10 片，取最后一片即可——从前写死 10，
  //: 于是一份 6 步的输出会报两条假的 FAIL
  const nt = JSON.parse(fs.readFileSync(runPath, "utf8")).time.length;
  const pick = Math.min(10, nt - 1);
  const gf = sandbox.gfileText ? sandbox.gfileText(pick) : null;
  if (gf) {
    const lines = gf.split("\n");
    console.log(`ok   g-file ${lines.length} 行，首行「${lines[0].trim().slice(0, 40)}」`);
    console.log("     g-file 2–3 行：" + lines[1].trim().slice(0, 78));
    console.log("                  " + lines[2].trim().slice(0, 78));
    const nums = lines[1].trim().split(/\s+/).length;
    if (nums !== 5) { console.log("FAIL g-file 第二行不是 5 个数"); bad++; }
    //: ★g-file 是 GEQDSK：ψ 每弧度。输出文件里的 ψ 是整匝 Wb（`meta.psi_convention`），
    //: 所以第三行的 simag / sibry 应当正好是文件里那两个数的 1/2π——差 2π 是老病。
    const RUNJ = JSON.parse(fs.readFileSync(runPath, "utf8"));
    //: ★g-file 的数是定宽的，**负号会和前一个数连在一起**（`…E+00-4.66…E-03`），
    //: 所以按「一个完整的 Fortran 指数数」切，不能按分隔符切。
    const g3 = lines[2].match(/-?\d\.\d+E[+-]\d+/g) || [];
    const simag = parseFloat(g3[2]), sibry = parseFloat(g3[3]);
    const want = [RUNJ.psi_axis[pick] / (2 * Math.PI), RUNJ.psi_bnd[pick] / (2 * Math.PI)];
    const off = Math.max(Math.abs(simag / want[0] - 1), Math.abs(sibry / want[1] - 1));
    if (RUNJ["meta.psi_convention"] !== "full_flux_Wb_axis_max") {
      console.log("FAIL 输出文件没有声明 ψ 的通量规（meta.psi_convention）"); bad++;
    }
    if (off < 1e-6) console.log(`ok   g-file 的 ψ 是每弧度（simag ${simag.toFixed(4)} = 文件 ${RUNJ.psi_axis[pick].toFixed(4)} / 2π）`);
    else { console.log(`FAIL g-file 的 ψ 不是每弧度：simag ${simag} 对 ${want[0]}`); bad++; }
  } else { console.log("FAIL g-file 写不出来"); bad++; }
  const sl = sandbox.sliceAt ? sandbox.sliceAt(pick) : null;
  if (sl && sl.Te && !Array.isArray(sl.Te[0]) && sl["meta.units"]) console.log("ok   单片 JSON");
  else { console.log("FAIL 单片 JSON"); bad++; }
}
process.exit(bad ? 1 : 0);
