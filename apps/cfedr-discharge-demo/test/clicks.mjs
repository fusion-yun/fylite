import fs from "fs"; import vm from "vm"; import { makeDom } from "./domshim.mjs";
const SLOT = 'var FY_DATA = null; // FY_DATA_SLOT';
function inject(js, D) {
  const n = js.split(SLOT).length - 1;
  if (n !== 1) throw new Error(`数据槽出现 ${n} 次，应为 1`);
  return js.replace(SLOT, "var FY_DATA = " + JSON.stringify(D) + ";");
}
const [tplPath, dataPath, runPath] = process.argv.slice(2);
const tpl = fs.readFileSync(tplPath, "utf8");
let js = tpl.match(/<script[^>]*>([\s\S]*?)<\/script>/)[1];
if (dataPath && dataPath !== "-") {
  const D = JSON.parse(fs.readFileSync(dataPath, "utf8"));
  if (runPath) D.demo = JSON.parse(fs.readFileSync(runPath, "utf8"));
  js = inject(js, D);
}
const { document, localStorage, store } = makeDom();
const saved = [];
const sandbox = { document, localStorage, console,
  navigator: { clipboard: { writeText: async () => {} } },
  URL: { createObjectURL: () => "blob:x", revokeObjectURL() {} },
  Blob: class { constructor(parts) { saved.push((parts[0] || "").length); } },
  FileReader: class { readAsText() {} }, setTimeout: () => 0,
  JSON, Math, Number, Object, Array, Set, Map, String, isFinite, parseFloat };
sandbox.window = sandbox; sandbox.globalThis = sandbox;
vm.createContext(sandbox);
let bad = 0;
const el = id => store.get(id);
const step = (name, fn, check) => {
  try { fn(); const ok = check ? check() : true; console.log(`${ok ? "ok  " : "FAIL"} ${name}`); if (!ok) bad++; }
  catch (e) { console.log(`FAIL ${name} —— ${e.constructor.name}: ${e.message}`); bad++; }
};
try { vm.runInContext(js, sandbox, { filename: "studio.js" }); console.log("ok   脚本加载（无 __DATA__ 也不炸）"); }
catch (e) { console.log(`FAIL 脚本加载 —— ${e.message}`); process.exit(1); }

//: `let` 声明不会挂到 vm 的 global 上，所以状态一律**从 DOM 读**——正好也是用户看得见的那一面
const nodeCount = () => +((el("node-count").textContent || "").match(/(\d+)/) || [0, 0])[1];
const bndCount = () => +((el("bnd-t").textContent || "").match(/·\s*(\d+)\s*点/) || [0, 0])[1];
const frameT = () => (el("clock").textContent || "");
let n0 = nodeCount();
step("加一个节点", () => el("add-node").fire("click"), () => nodeCount() === n0 + 1);
step("删除选中", () => el("del-node").fire("click"), () => nodeCount() === n0);
step("下一节点 / 上一节点", () => { el("bnd-next").fire("click"); el("bnd-prev").fire("click"); });
step("复制上一节点", () => { el("bnd-next").fire("click"); el("bnd-copy").fire("click"); });
//: ★2026-09-17 之后磁面**只有一种编法**（拖轨迹顶点）：Miller 参数格与「Miller / 直接拖点」
//: 那个档位开关都撤了，剩下的是「按曲线重采样」——把这一节点的点放回它自己那条拟合曲线上。
step("按曲线重采样", () => el("bnd-resample").fire("click"), () => (el("xs").innerHTML || "").includes('class="pt'));
//: ★Miller 参数波形是磁面的第二种编法：四条曲线、每节点一个可拖控制点（`mh`）、竖线选时刻（`mpick`）
step("Miller 参数波形可编", () => {}, () => {
  const mw = el("millwave").innerHTML || "";
  return (mw.match(/class="mh"/g) || []).length === 4 * nodeCount()
      && (mw.match(/class="mpick"/g) || []).length === nodeCount();
});
step("改控制点数 → 12", () => { el("npts").value = "12"; el("npts").fire("change"); },
  () => bndCount() === 12);
step("叠显 / 轨迹开关", () => { el("bnd-show-all").checked = true; el("bnd-show-all").fire("change"); el("bnd-track").checked = false; el("bnd-track").fire("change"); });
step("主题：深 → 浅 → 自动", () => { el("th-dark").fire("click"); el("th-light").fire("click"); el("th-auto").fire("click"); },
  () => el("th-auto").getAttribute("aria-pressed") === "true");
step("切页签", () => { el("tab-out").fire("click"); el("tab-in").fire("click"); });
step("初始化即报出可导出的输入", () => {}, () => (el("gen-note").textContent || "").includes("已就绪"));
step("磁轴手柄已画出", () => {}, () => (el("xs").innerHTML || "").includes('class="axis"'));
//: ★★截面是**只读视图**：控制点的轨迹画成线段，当前时刻那一组点画出来作定位；**没有手柄**，
//: 编磁面走「Miller 参数波形」。这里断言的正是"画得出线、且一个可拖的东西都没有"。
step("轨迹画成线段", () => { el("bnd-track").checked = true; el("bnd-track").fire("change"); },
  () => {
    const xs = el("xs").innerHTML || "";
    //: 每个控制点一条轨迹 + 磁轴一条 + Miller 拟合曲线 + 限制器
    return (xs.match(/<polyline/g) || []).length >= bndCount() + 2;
  });
step("截面上没有可拖的手柄", () => {},
  () => {
    const xs = el("xs").innerHTML || "";
    return !/cursor:grab/.test(xs) && !/data-drag/.test(xs) && (xs.match(/class="pt"/g) || []).length === bndCount();
  });
step("轨迹开关复位", () => { el("bnd-track").checked = true; el("bnd-track").fire("change"); });
{
  const before = nodeCount();
  step("撤销（加点后回退）", () => { el("add-node").fire("click"); el("undo").fire("click"); }, () => nodeCount() === before);
  step("重做", () => el("redo").fire("click"), () => nodeCount() === before + 1);
  step("再撤销一次", () => el("undo").fire("click"), () => nodeCount() === before);
}
step("导出输入 JSON", () => el("save-in").fire("click"), () => saved.length >= 1);
step("恢复本算例波形", () => el("reset-nodes").fire("click"), () => nodeCount() === n0);
const loaded0 = !!(el("out-note")?.textContent || "").includes("个时刻");
if (loaded0) {
  const loaded = !!(el("out-note")?.textContent || "").includes("个时刻");
  step("初始化时自动载入演示输出", () => {}, () => loaded);
  step("导出整份", () => el("save-out").fire("click"), () => saved.length >= 2);
  step("导出当前片 JSON", () => el("save-slice").fire("click"), () => saved.length >= 3);
  step("导出当前片 g-file", () => el("save-gfile").fire("click"), () => saved.length >= 4);
  step("拖时间条", () => { el("scrub").value = "5"; el("scrub").fire("input"); }, () => frameT().includes("t ="));
  step("播放 / 暂停", () => { el("play").fire("click"); el("play").fire("click"); });
  step("温度与密度各成一格、并入一维剖面", () => {},
    () => (el("profs").innerHTML || "").includes("温度 T_e") && (el("profs").innerHTML || "").includes("电子密度 n_e"));
  step("已撤掉本时刻 PF 柱状图", () => {}, () => !store.get("pfbar"));
}
console.log(bad ? `\n${bad} 项失败` : "\n全部通过");
process.exit(bad ? 1 : 0);
