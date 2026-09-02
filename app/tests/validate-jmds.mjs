// Gate for `tools/jmds` — the pure-client jar.
//
//   node app/tests/validate-jmds.mjs
//   FYLITE_MDSIP_SERVER=<host:port> node app/tests/validate-jmds.mjs
//
// ★WHAT `jmds` IS FOR.  One person, one workstation, a JRE and nothing else:
// no server process and no site install of MDSplus.  FYL-DESIGN-06 §1 marks
// that native case `●` and the browser case `✗`; the browser one is covered by
// the shipped host (`fylite-app`) and this lane does not touch it.  The jar is
// only useful if what it writes IS the document that host answers, so that is
// what is asserted: every `/api/signal` field equal, both arrays equal BIT FOR
// BIT.
//
// ★TWO HALVES, AND ONLY ONE OF THEM NEEDS A SERVER.  The refusals are checked
// offline, because `jmds` applies its character rules BEFORE it opens a socket
// — that is the point of them, and a guard that needed a live server to prove
// would be the wrong shape.  The equality half needs a real site and runs only
// with `FYLITE_MDSIP_SERVER` set.
//
// ★WHY NOT THE OFFLINE FIXTURE.  `_mdsip-replay.mjs` answers the exact
// requests that were recorded, and the Java client asks differently on the way
// in — measured: it writes its header LITTLE-ENDIAN (`client_type` 0x03, not
// the 0xc0|0x03 this repository's client declares) and its `connect()` pushes
// 1473 bytes of TDI `public fun …` definitions into the session before any
// read.  Every one of those is a request the fixture never recorded, and a
// replay that cannot answer is not a criterion.  The divergence is recorded in
// `docs/note/jvm-mdsip-probe.md`; the gate stays honest and asks a real server.
//
// ★IT SKIPS RATHER THAN PRETENDS.  No `java`, or no jar, and it says so and
// stops — it does not pass.

import { existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { startApp } from './_site.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const JAR = HERE + '../../tools/jmds/jmds.jar';
const SERVER = process.env.FYLITE_MDSIP_SERVER || '';
const TREE = process.env.FYLITE_JMDS_TREE || 'pcs_east';
const NODE = process.env.FYLITE_JMDS_NODE || '\\PCRL01';

let bad = 0;
const ok = (m) => console.log('  ok   ' + m);
const fail = (m) => { console.log('  FAIL ' + m); bad++; };
const info = (m) => console.log('       ' + m);

const haveJava = spawnSync('java', ['-version']).status === 0;
if (!haveJava || !existsSync(JAR)) {
  console.log('SKIP — the JVM lane is optional and is not set up here');
  info(haveJava ? `no ${JAR}` : 'no `java` on PATH');
  info('build it with:  sh tools/jmds/build.sh   (no JDK needed)');
  process.exit(0);
}

/** Run the jar against `server` and hand back what it said. */
function jmds(server, args) {
  const r = spawnSync('java', ['-jar', JAR, '--server', server, ...args],
                      { encoding: 'utf8', timeout: 120000 });
  return { status: r.status, out: (r.stdout || '').trim(), err: (r.stderr || '').trim() };
}

// --------------------------------------------------------------------------
// 1. the read-only rule, checked with no server in sight
// --------------------------------------------------------------------------

console.log('refusals happen before the socket, so they need no server');

//: ★The address here is one nothing listens on.  If a refusal ever started
//: happening on the far side of a connection instead of before it, these would
//: stop exiting 2 and start timing out — which is exactly the regression worth
//: catching.
const NOWHERE = '127.0.0.1:9';

for (const attempt of ['getenv("HOME")', '\\PCRL01;spawn', 'data(\\PCRL01)', '\\PCRL01 + 1',
                       '\\PCRL01,1']) {
  const r = jmds(NOWHERE, ['--tree', TREE, '--shot', '1', '--node', attempt]);
  if (r.status === 2 && /refused/.test(r.err)) ok(`refused --node ${JSON.stringify(attempt)}`);
  else fail(`--node ${JSON.stringify(attempt)} was NOT refused (exit ${r.status})`);
}
for (const attempt of ['pcs east', 'pcs_east)', 'pcs-east', '']) {
  const r = jmds(NOWHERE, ['--tree', attempt, '--shot', '1', '--node', NODE]);
  if (r.status === 2 && /refused/.test(r.err)) ok(`refused --tree ${JSON.stringify(attempt)}`);
  else fail(`--tree ${JSON.stringify(attempt)} was NOT refused (exit ${r.status})`);
}
{
  const r = jmds(NOWHERE, ['--tree', TREE, '--shot', '1', '--node', NODE, '--wat', 'x']);
  if (r.status === 2) ok('refused an unknown argument');
  else fail(`an unknown argument was NOT refused (exit ${r.status})`);
}

// --------------------------------------------------------------------------
// 2. the same document, two implementations
// --------------------------------------------------------------------------

if (!SERVER) {
  console.log('\nno FYLITE_MDSIP_SERVER — the equality half needs a real site, skipped');
  info('  FYLITE_MDSIP_SERVER=host:port node app/tests/validate-jmds.mjs');
} else {
  console.log(`\nthe same document, two implementations — ${SERVER} ${TREE} ${NODE}`);

  //: ★另一边是**发布出去的那个宿主**（`fylite-app`），不是仿制品：这道门比的是
  //: jar 与读者手里那个东西答的是不是同一份文档。
  const host = await startApp(SERVER);
  const base = host.url.replace(/\/$/, '');

  const shotDoc = await (await fetch(`${base}/api/shot?tree=${TREE}`)).json();
  //: ★the counter runs AHEAD of what was written, so step back until a shot
  //: actually holds this node — and use the SAME shot on both sides.
  let shot = null, a = null;
  for (let s = shotDoc.shot; s > shotDoc.shot - 8 && shot == null; s--) {
    const r = await fetch(`${base}/api/signal?tree=${TREE}&shot=${s}`
                          + `&node=${encodeURIComponent(NODE)}&points=1500`);
    if (r.ok) { shot = s; a = await r.json(); }
  }
  if (shot == null) fail(`no shot within 8 of ${shotDoc.shot} holds ${NODE} on ${TREE}`);
  else {
    info(`shot #${shot} (the counter is at ${shotDoc.shot})`);
    const run = jmds(SERVER, ['--tree', TREE, '--shot', String(shot), '--node', NODE,
                              '--points', '1500',
                              ...(process.env.FYLITE_MDSIP_USER
                                  ? ['--user', process.env.FYLITE_MDSIP_USER] : [])]);
    let b = null;
    if (run.status !== 0) fail(`jmds exited ${run.status}: ${run.err.split('\n')[0]}`);
    else { try { b = JSON.parse(run.out); } catch (e) { fail('jmds did not answer JSON: ' + e.message); } }

    if (b) {
      const scalars = ['server', 'tree', 'shot', 'node', 'units', 'timeUnits',
                       'n', 'first', 'last', 'stride', 'returned', 'decimated', 'windowed'];
      const off = scalars.filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]));
      for (const k of off) fail(`\`${k}\`: 宿主 ${JSON.stringify(a[k])} vs jmds ${JSON.stringify(b[k])}`);
      if (!off.length)
        ok(`${scalars.length} scalar fields agree (n=${a.n}, stride=${a.stride}, returned=${a.returned})`);

      for (const k of ['data', 'time']) {
        const x = a[k], y = b[k];
        if (!Array.isArray(x) || !Array.isArray(y)) { fail(`\`${k}\` is not an array on both sides`); continue; }
        if (x.length !== y.length) { fail(`\`${k}\` length ${x.length} vs ${y.length}`); continue; }
        //: ★`Object.is`, not a tolerance: these are the same bytes off the same
        //: socket, decoded twice.  Anything but bit equality is a decoder
        //: difference, and a decoder difference is what this gate is for.
        let n = 0, worst = 0;
        for (let i = 0; i < x.length; i++)
          if (!Object.is(x[i], y[i])) { n++; worst = Math.max(worst, Math.abs(x[i] - y[i])); }
        if (n) fail(`\`${k}\`: ${n}/${x.length} samples differ (worst ${worst})`);
        else ok(`\`${k}\`: ${x.length} samples agree bit for bit`);
      }

      if (b.tool && b.toolVersion) ok(`jmds says how it was made (${b.tool} ${b.toolVersion})`);
      else fail('jmds output carries no provenance');
    }

    const r = jmds(SERVER, ['--tree', TREE, '--current-shot',
                            ...(process.env.FYLITE_MDSIP_USER
                                ? ['--user', process.env.FYLITE_MDSIP_USER] : [])]);
    const j = r.status === 0 ? JSON.parse(r.out) : null;
    if (j && j.currentShot === shotDoc.shot) ok(`both answer current_shot("${TREE}") = ${shotDoc.shot}`);
    else fail(`current_shot: 宿主 ${JSON.stringify(shotDoc.shot)} vs jmds ${JSON.stringify(j && j.currentShot)}`);
  }

  host.close();
}

console.log(bad ? `\nFAILED (${bad})` : '\nPASS');
process.exit(bad ? 1 : 0);
