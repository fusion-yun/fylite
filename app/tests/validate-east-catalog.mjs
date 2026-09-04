// Gate for `app/facts/device/east-signals.json` — the EAST diagnostic catalogue.
//
//   node app/tests/validate-east-catalog.mjs
//   FYLITE_MDSIP_SERVER=127.0.0.1:8000 node app/tests/validate-east-catalog.mjs
//
// ★WHY A CATALOGUE NEEDS A GATE OF ITS OWN.  A node path does not say which
// tree it lives in, and that mapping cannot be derived — measured on #137985,
// `\PCRL01` is on `pcs_east` while `\POINT_F1` is on `east`, and asking `east`
// for `\PCRL01` answers `%TREE-W-NNF`: not empty data, *absent*.  So the page
// leans on this file to know where to look, which makes a wrong entry worse
// than a missing one: the reader is told the signal does not exist when it was
// only looked for in the wrong place.
//
// ★WHAT IS ASSERTED AND WHAT IS ONLY REPORTED.  Structure is asserted — every
// node must be a node path the read-only client would accept, every tree a
// plain tree name, and a row with no tree must say why.  RESOLUTION IS NOT
// ASSERTED, because whether a node holds data is a property of a SHOT: #137985
// stored 21 of its 79 magnetic probes, and a gate that failed on that would be
// demanding a fully-instrumented discharge, not a correct catalogue.  What the
// live pass asserts is the one shot-independent thing: **every tree the
// catalogue names must open**.  The rest is a report.
//
// ★AND IT NEVER EDITS THE FILE.  A catalogue silently filtered against one
// shot becomes a false claim about every other one.

import { existsSync, readFileSync } from 'node:fs';
import { startApp } from './_site.mjs';
import { replayMdsip, haveFixture, FIXTURE_ABSENT } from './_mdsip-replay.mjs';

//: ★★目录本身与回放夹具**都不在本仓**：一个采自 EAST 内网 Wiki，一个是对 EAST
//: 服务器录下的真会话，2026-09-02 一并迁到私有的 `fydata`。两者缺一，这道门就
//: **跳过**——它守的是「目录里的名字客户端肯不肯发」，没有目录就无从守起，而
//: 拿一份手写的样本去守，守住的是样本不是目录。
const CATALOGUE = process.env.FYLITE_SIGNAL_CATALOGUE
  || new URL('../facts/device/east-signals.json', import.meta.url).pathname;
if (!existsSync(CATALOGUE)) {
  console.log(`SKIP —— 没有 EAST 诊断目录：${CATALOGUE}`);
  console.log('  它随 fydata（私有）走。有 fydata 的话：');
  console.log('    cp <fydata>/corpus/device/east/east_signals.json app/facts/device/east-signals.json');
  console.log('  或：FYLITE_SIGNAL_CATALOGUE=<fydata>/corpus/device/east/east_signals.json');
  process.exit(0);
}
if (!haveFixture()) { console.log('SKIP —— ' + FIXTURE_ABSENT); process.exit(0); }

//: ★★守卫问的是**发布出去的那个宿主**，不是这里再写一遍规则。2026-09-01 退役
//: `app/server/` 之前，这道门 import 的是 Node 客户端的 `isNodePath` /
//: `isTreeName`；那两个函数是 Rust 那份的移植，于是「目录里的名字客户端肯不肯发」
//: 这件事，被一个**副本**回答了。现在逐条问 `/api/node`：400 就是守卫拒了，
//: 别的状态码都算它肯发（拿不到数据是另一回事）。
const mds = await replayMdsip();
const app = await startApp(`127.0.0.1:${mds.port}`);
const GUARD_SHOT = 137985;
/** 守卫收不收这一条？400 = 拒。 */
async function accepted(tree, node) {
  const q = `tree=${encodeURIComponent(tree || '')}&shot=${GUARD_SHOT}`
    + `&node=${encodeURIComponent(node)}`;
  const r = await fetch(`${app.url}api/node?${q}`);
  if (r.status !== 400) return { ok: true };
  return { ok: false, why: ((await r.json()).error || '').slice(0, 80) };
}

const HERE = new URL('.', import.meta.url).pathname;
const FILE = CATALOGUE;

let bad = 0;
const ok = (m) => console.log('  ok   ' + m);
const fail = (m) => { console.log('  FAIL ' + m); bad++; };
const info = (m) => console.log('       ' + m);

const cat = JSON.parse(readFileSync(FILE, 'utf8'));

console.log('shape and provenance');

for (const k of ['$schema', 'generated_by', 'generated_at', 'source', 'categories', 'diagnostics'])
  if (cat[k] === undefined) fail(`the catalogue has no \`${k}\``);
for (const k of ['file', 'sha256', 'retrieved', 'index'])
  if (!cat.source || !cat.source[k]) fail(`\`source.${k}\` is missing — the file cannot say where it came from`);
if (!/^[0-9a-f]{64}$/.test((cat.source || {}).sha256 || ''))
  fail('`source.sha256` is not a sha256 — a provenance field that is not checkable is decoration');
if (!bad) ok(`generated ${cat.generated_at} by ${cat.generated_by} from ${(cat.source.file || '').split('/').pop()}`);

const diags = cat.diagnostics || [];
const signals = diags.flatMap((d) => (d.signals || []).map((s) => ({ ...s, of: d.title })));

console.log('\nentries');

for (const d of diags) {
  if (!d.title) fail('a diagnostic with no title');
  if (!d.category) fail(`${d.title}: no category`);
  if (!cat.categories.includes(d.category)) fail(`${d.title}: category ${d.category} is not in \`categories\``);
}
if (!bad) ok(`${diags.length} diagnostics in ${cat.categories.length} categories, ${signals.length} signals`);

// ★Every node must be something the read-only client would actually send.  A
// catalogue entry that the guard refuses is an entry the page can never fetch,
// and it would fail at the click rather than here.
let refused = 0;
for (const s of signals) {
  if (s.tree === null || s.tree === undefined) {
    if (!s.unfetchable) fail(`${s.of}: ${s.node} has no tree and no reason given`);
    continue;
  }
  const a = await accepted(s.tree, s.node);
  if (!a.ok) {
    fail(`${s.of}: ${s.tree}${s.node} —— 宿主的守卫不肯发：${a.why}`);
    refused++;
  }
}
if (!refused) ok('every node is a path the read-only guard accepts');

const noTree = signals.filter((s) => !s.tree);
if (noTree.length) info(`${noTree.length} signal(s) carry no tree and say why: ` +
  noTree.map((s) => `${s.node} (${s.unfetchable})`).join('; '));

// ★The same node on the same tree must not be given two different units.  The
// upstream lists a diagnostic's raw and processed sections separately and the
// same name can appear in both; two units for one node is a harvest error and
// the page would show whichever it read last.
const seen = new Map();
let clash = 0;
for (const s of signals) {
  if (!s.tree) continue;
  const k = `${s.tree}|${s.node.toUpperCase()}`;
  const prev = seen.get(k);
  if (prev && prev.unit && s.unit && prev.unit !== s.unit) {
    fail(`${k} is listed with unit ${JSON.stringify(prev.unit)} (${prev.of}) and ${JSON.stringify(s.unit)} (${s.of})`);
    clash++;
  }
  if (!prev) seen.set(k, s);
}
if (!clash) ok(`${seen.size} distinct (tree, node) pairs, no unit disagreements`);

const byTree = {};
for (const s of signals) if (s.tree) byTree[s.tree] = (byTree[s.tree] || 0) + 1;
info('trees: ' + Object.entries(byTree).map(([t, n]) => `${t} ${n}`).join(' · '));

// --- the live pass --------------------------------------------------------

const SERVER = process.env.FYLITE_MDSIP_SERVER;
if (!SERVER) {
  console.log('\nlive pass  SKIPPED (set FYLITE_MDSIP_SERVER=host[:port] to run it)');
} else {
  const SHOT = Number(process.env.FYLITE_CATALOG_SHOT || 137985);
  // A full sweep is ~2 round trips per signal; on a tunnelled link that is
  // minutes.  The cap is announced, never silent.
  const CAP = Number(process.env.FYLITE_CATALOG_PER_DIAG || 0);
  console.log(`\nlive pass  ${SERVER} #${SHOT}` + (CAP ? `  (first ${CAP} signal(s) per diagnostic)` : ''));

  const pick = [];
  for (const d of diags) {
    const rows = (d.signals || []).filter((s) => s.tree);
    for (const s of (CAP ? rows.slice(0, CAP) : rows)) pick.push({ ...s, of: d.title });
  }
  if (CAP) info(`checking ${pick.length} of ${signals.filter((s) => s.tree).length} signals — the rest were NOT checked`);

  const trees = [...new Set(pick.map((s) => s.tree))].sort();
  const report = { resolved: 0, nodata: 0, absent: 0, unitMismatch: [] };

  //: 活跑也走同一个宿主，只是把它接到真站点上——门与读者跑的是同一条路。
  const live = await startApp(SERVER);
  const get = async (path) => {
    const r = await fetch(live.url + path);
    return { code: r.status, body: await r.json() };
  };
  for (const tree of trees) {
    const opened = await get(`api/tree?tree=${encodeURIComponent(tree)}&shot=${SHOT}`
                             + `&path=${encodeURIComponent('\\TOP')}`);
    if (opened.code !== 200) {
      // ★This one IS a failure: a tree that will not open is a catalogue error
      // (a wrong name), not a property of the shot.
      fail(`tree ${tree} will not open: ${opened.body.error}`);
      continue;
    }
    ok(`tree ${tree} opens on #${SHOT}`);
    for (const s of pick.filter((x) => x.tree === tree)) {
      //: 一次问答就够：`/api/node` 一并答 size 与 units（客户端那两次
      //: `getSize`/`getUnits` 是它内部的事）。
      const r = await get(`api/node?tree=${encodeURIComponent(tree)}&shot=${SHOT}`
                          + `&node=${encodeURIComponent(s.node)}`);
      if (r.code !== 200) { report.absent++; continue; }
      const n = Number(r.body.size || 0);
      if (!(n > 0)) { report.nodata++; continue; }
      report.resolved++;
      const u = String(r.body.units || '');
      if (s.unit && u.trim() && !unitLooksSame(u, s.unit))
        report.unitMismatch.push(`${tree}${s.node}: catalogue ${JSON.stringify(s.unit)} vs server ${JSON.stringify(u)}`);
    }
  }
  live.close();

  info(`#${SHOT}: ${report.resolved} resolved · ${report.nodata} present-but-no-data · ${report.absent} not found`);
  if (report.unitMismatch.length) {
    info(`${report.unitMismatch.length} unit disagreement(s) with the server — reported, NOT corrected here:`);
    for (const m of report.unitMismatch.slice(0, 12)) info('  · ' + m);
    if (report.unitMismatch.length > 12) info(`  · … and ${report.unitMismatch.length - 12} more`);
  } else info('no unit disagreements with the server');
  info('★resolution is shot-dependent and is a REPORT, not a verdict.');
}

/** Units are written by two hands; compare them the way a reader would. */
function unitLooksSame(a, b) {
  const norm = (s) => String(s).toLowerCase().replace(/[\s.]/g, '')
    .replace(/\^/g, '').replace(/degrees?/, 'deg').replace(/^a\.u\.?$/, 'au');
  return norm(a) === norm(b);
}

app.close();
await mds.close();

console.log(bad ? `\nFAILED (${bad})` : '\nPASS');
process.exit(bad ? 1 : 0);
