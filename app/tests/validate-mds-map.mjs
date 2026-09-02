// 闸子：`mapping/east-mds.json` 的**浏览器宿主那一半**。
//
//   node app/tests/validate-mds-map.mjs
//
// ★WHAT THIS CLOSES.  浏览器宿主的请求面（`rust/fylite/src/bin/app/api.rs`）与
// `python/fylite/io/mds.py` 各自拼写同一批 `\EFIT_EAST::TOP…` 节点。两处拼写、
// 一个契约：其中一处被改了名字或改了列的取法，另一处不会红，两个宿主从此对同一炮
// 同一时刻给出不同的数，而它们看起来都是对的。这道闸子把那条分叉变成机器能发现的
// 东西。
//
// ★2026-09-01：从前这一半读的是 `app/server/gateway.mjs` 的源码。那个 Node 网关
// 已退役，请求面只剩 Rust 这一份，所以抽取器改成读它——**要抽的是发布出去的那份
// 拼法**，不是任何一份副本的。
//
// ★THE ASSERTION IS ONE-DIRECTIONAL, ON PURPOSE.  宿主读的必须都在表里；表里
// 有宿主不读的**是允许的**，而且现在就有——FPOL 那级回退宿主有意不做（它回
// null：真空场是页面自己的卷宗里已有的数，在测量记录里现编一个机器常数是另一
// 回事），efit 交付的重构切片宿主也不服务。所以差集是**打印出来**的，不是判掉的。
//
// ★AND IT DOES NOT VALIDATE THE SCHEMA.  形状检查由 schema 文件自己的
// `required` 驱动（读它、按它查），而不是在这里把字段名再抄一遍——抄的那份会与
// schema 分家，而分家的那天两边都不会红。完整的 schema 校验在 Python 侧那道闸子里。

import { readFileSync, existsSync } from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
const MAP = HERE + '../../mapping/east-mds.json';
const SCHEMA = HERE + '../../mapping/mds-map.schema.json';
const HOST_SRC = HERE + '../../rust/fylite/src/bin/app/api.rs';
const DEVICE = HERE + '../devices/east.jsonld';
const DECK_DIR = HERE + '../../machine_desc/east/';

let bad = 0;
const ok = (m) => console.log('  ok   ' + m);
const fail = (m) => { console.log('  FAIL ' + m); bad++; };
const info = (m) => console.log('       ' + m);

const map = JSON.parse(readFileSync(MAP, 'utf8'));
const schema = JSON.parse(readFileSync(SCHEMA, 'utf8'));

// ------------------------------------------------------------------
console.log('形状（按 schema 自己的 required 查）');

for (const k of schema.required || [])
  if (map[k] === undefined) fail(`表里没有 \`${k}\``);
if (map.$schema !== schema.properties.$schema.const)
  fail(`\`$schema\` 是 ${map.$schema}，schema 说的是 ${schema.properties.$schema.const}`);

const groupReq = schema.$defs.Group.required || [];
for (const g of map.groups || []) {
  for (const k of groupReq)
    if (g[k] === undefined) fail(`组 ${g.id || '(无 id)'}: 缺 \`${k}\``);
  const srcs = ['nodes', 'node', 'node_ref', 'channels_ref'].filter((k) => g[k] !== undefined);
  if (srcs.length !== 1) fail(`组 ${g.id}: 节点来源应恰好一个，得到 ${srcs.join(',') || '零个'}`);
  const trees = ['tree', 'tree_ref'].filter((k) => g[k] !== undefined);
  if (trees.length !== 1) fail(`组 ${g.id}: 树应恰好一个，得到 ${trees.join(',') || '零个'}`);
}
if (!bad) ok(`${map.groups.length} 组，${(schema.required || []).length} 个顶层必填字段齐`);

if (!existsSync(DECK_DIR + map.device_document))
  fail(`\`device_document\` 指的 ${map.device_document} 不在 machine_desc/east/`);
else ok(`引用解析的对象 = ${map.device_document}`);

// ------------------------------------------------------------------
console.log('\n两个宿主拼出的 efit_east 节点');

/** 表里 efit_east 那些组的节点全集（含回退里的）。 */
const mapNodes = new Set();
for (const g of map.groups) {
  if (g.tree !== 'efit_east') continue;
  for (const n of g.nodes || []) mapNodes.add(n.name);
  if (g.node) mapNodes.add(g.node);
  for (const fb of g.fallback || []) if (fb.node) mapNodes.add(fb.node);
}

/** 宿主源里 `format!("{M}SILOPT")` 这种拼法还原成整条路径。 */
//: ★先把注释行剥掉：这个文件的注释里就写着 `{G}BCENTR`（讲的是一处改动的来龙
//: 去脉），当成代码抽出来就会凭空多一个节点。
const host = readFileSync(HOST_SRC, 'utf8')
  .split('\n').filter((l) => !/^\s*\/\//.test(l)).join('\n');
const prefixes = new Map();
for (const m of host.matchAll(/const\s+([A-Z])\s*:\s*&str\s*=\s*"(\\\\EFIT_EAST::TOP[^"]*)"/g))
  prefixes.set(m[1], m[2].replace(/\\\\/g, '\\'));
const hostNodes = new Set();
for (const [v, pre] of prefixes)
  for (const m of host.matchAll(new RegExp(`\\{${v}\\}([A-Z0-9_]+)`, 'g')))
    hostNodes.add(pre + m[1]);
//: ★也收裸标签：真空场读的是 `c.get("\\BCENTR")`，不带前缀。只认 `.get("\\…")`
//: 这一种写法——那正是「向服务器要一个节点」的那一句，别处的 `.get("tree")` 之类
//: 取的是查询参数，不是节点。
for (const m of host.matchAll(/\.get\("(\\\\[A-Z0-9_.:]+)"\)/g))
  hostNodes.add(m[1].replace(/\\\\/g, '\\'));

if (!prefixes.size)
  fail('宿主源里找不到 \\EFIT_EAST 前缀 —— 该改的是这个抽取器，不是那张表');
else if (!hostNodes.size)
  fail('前缀找到了但一个拼接都没找到 —— 同上');
else {
  const missing = [...hostNodes].filter((n) => !mapNodes.has(n));
  if (missing.length) fail(`宿主读了表里没有的节点: ${missing.join(', ')}`);
  else ok(`宿主拼出的 ${hostNodes.size} 个节点全部在表里`);
  const extra = [...mapNodes].filter((n) => !hostNodes.has(n));
  if (extra.length) {
    info(`表里另有 ${extra.length} 个节点宿主不读（有意，见表内说明）:`);
    for (const n of extra) info('  · ' + n);
  }
}

// ------------------------------------------------------------------
console.log('\n`device:` 引用在浏览器侧装置文档里的样子（报告，不是判据）');

// ★★这一节**判不了**，而说清楚为什么判不了比给一个假的绿更有用。
//
// 表里的引用是对着**工作站那份卷宗**（`machine_desc/east/east_device.yaml`）解的
// ——表的顶层 `device_document` 就是这么声明的。`app/devices/east.jsonld` 不是那份
// 卷宗的副本，它是页面用得着的那些字段的另一份文档，两者在两处**成员就不同**：
//
//   · `pf_active.coil` 在这里是 14 条**物理线圈**（PF1..PF14），在卷宗里是 12 条
//     **PCS 通道**（PF1P…）。同一条引用路径在两边解得开、解出来的**不是同一批东西**
//     ——这正是「解得开」比「解不开」危险的地方，所以这里不把它算作通过。
//   · 非 DD 的字段在这里带 `fylite:` 前缀（`fylite:weight`），卷宗里是裸名。
//
// ⇒ **P2 的前置**：JS 宿主要按引用取通道，得先有一条它读得到的卷宗（node 没有
// YAML 解析器；要么给卷宗一份 JSON 导出，要么由 Python 侧生成一份解析好的绑定）。
// 这道闸子的作用是让那个前置在动手之前就摆在明面上，而不是在 P2 中途被撞见。

const dev = JSON.parse(readFileSync(DEVICE, 'utf8'));

/** `device:a.b[].c` → 值；解不开回 null（解不开本身是要报告的事实，不抛）。 */
function resolve(doc, ref) {
  let node = doc;
  for (const seg of ref.slice('device:'.length).split('.')) {
    const arr = seg.endsWith('[]');
    const key = arr ? seg.slice(0, -2) : seg;
    if (Array.isArray(node)) node = node.map((n) => (n ? n[key] : undefined));
    else if (node && typeof node === 'object' && key in node) node = node[key];
    else return null;
    if (arr && !Array.isArray(node)) return null;
  }
  return node;
}

const refs = new Set();
(function walk(o) {
  if (Array.isArray(o)) o.forEach(walk);
  else if (o && typeof o === 'object') Object.values(o).forEach(walk);
  else if (typeof o === 'string' && o.startsWith('device:')) refs.add(o);
})(map);

const REF_RE = /^device:[A-Za-z_][A-Za-z0-9_]*((\.[A-Za-z_][A-Za-z0-9_:]*)|(\[\]))*$/;
let malformed = 0;
for (const ref of refs) if (!REF_RE.test(ref)) { fail(`引用写法不合法: ${ref}`); malformed++; }
if (!malformed) ok(`${refs.size} 条 device: 引用，写法都合法`);

const shown = [];
for (const ref of [...refs].sort()) {
  const v = resolve(dev, ref);
  if (v === null || v === undefined) { shown.push([ref, '不带']); continue; }
  if (Array.isArray(v)) {
    const holes = v.filter((x) => x === undefined).length;
    shown.push([ref, holes ? `${v.length} 项，其中 ${holes} 项无此字段` : `${v.length} 项`]);
  } else shown.push([ref, JSON.stringify(v)]);
}
const w = Math.max(...shown.map(([r]) => r.length));
for (const [ref, what] of shown) info(`  ${ref.padEnd(w)}  ${what}`);

console.log(bad ? `\n${bad} 项未过` : '\nALL GREEN');
process.exit(bad ? 1 : 0);
