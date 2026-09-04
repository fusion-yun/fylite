// The checkpoint gate: a run is a sequence of door calls, and stopping in the
// middle of one loses nothing (`FYL-DESIGN-18` U-8 · U-9 · U-10 · U-11 · U-19;
// NR-QUAL-007 third clause).
//
//     node app/tests/validate-checkpoint.mjs [--playwright <dir>] [--chrome <bin>]
//
// ★The equivalence claim is the point.  `FYL-DESIGN-18` §十三 names one
// criterion for this gate: **N steps in one call ≡ k steps + resume(N − k)**.
// With a real kernel that is a bit-for-bit comparison of two runs; here the
// stepper is a deterministic fake, which tests the thing this repository owns —
// that the marcher carries the state across the seam and asks for exactly the
// steps that are left. A fake that ignored the state would fail the same way a
// broken kernel would.
//
// ★Cancel is not an error, and not a terminate.  The march resolves carrying
// the steps that ran; the assertions read the resolved value, so a cancel that
// threw, or one that lost the completed steps, fails here.
//
// ★The store is checked for what U-10 claims: what comes back out is the same
// BYTES that went in, because a checkpoint and an export are the same document
// (U-18) and「一样但不逐字节一样」is how two files that must be interchangeable
// stop being interchangeable.
import { readFileSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..');
let bad = 0;
const fail = (m) => { console.log('  FAIL  ' + m); bad++; };
const ok = (m) => console.log('  ok    ' + m);

// --- 〔一〕 the marcher owns no worker, and the store owns no format ----------
console.log('\n〔一〕两个模块的边界（U-8：步进器是注入的；U-10：断点没有自己的格式）');
//: ★comments are stripped before this grep: `run.js` NAMES `terminate()` in
//: the paragraph explaining why it does not call it, and a gate that cannot
//: tell prose from code makes the prose unwritable.
const decomment = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').split('\n')
  .map((l) => l.replace(/(^|\s)\/\/.*$/, '')).join('\n');
const run = decomment(readFileSync(join(APP, 'assets', 'run.js'), 'utf8'));
const cp = decomment(readFileSync(join(APP, 'assets', 'checkpoint.js'), 'utf8'));
for (const w of ['Worker', 'postMessage', 'terminate', 'wasm'])
  if (new RegExp(`\\b${w}\\s*\\(`).test(run)) fail(`run.js 直接用了 ${w}() —— 步进器必须是注入的`);
if (!/opts\.step|o\.step/.test(run)) fail('run.js 没有注入的 step()');
else ok('run.js 只认注入的 step()，不认识 worker、wasm 或 terminate');
if (/checkpoint_version|"format"|fylite:checkpoint\/1/.test(cp))
  fail('checkpoint.js 发明了一种断点格式 —— U-10 说断点就是一份记录');
else ok('checkpoint.js 没有发明断点格式');
if (!/JSON\.stringify\(record\)/.test(cp)) fail('checkpoint.js 没有按原样文本存记录');
else ok('记录以文本原样入库（U-18：与导出同一批字节）');

// --- 〔二〕 in a browser ------------------------------------------------------
console.log('\n〔二〕浏览器里：等价性 · 进度 · 取消 · 断点仓 · 内核身份');
const flag = (name, env) => { const i = process.argv.indexOf('--' + name); return i > 0 ? process.argv[i + 1] : process.env[env]; };
if (!flag('playwright', 'PLAYWRIGHT_PATH')) {
  console.log('  跳过 —— 用 --playwright <装有 playwright 的目录> 或设 $PLAYWRIGHT_PATH');
} else {
  const { browser } = await import('./_browser.mjs');
  const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                  '.css': 'text/css; charset=utf-8', '.json': 'application/json',
                  '.jsonld': 'application/ld+json', '.svg': 'image/svg+xml' };
  const srv = createServer((req, res) => {
    const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (p.split('/').includes('..')) { res.writeHead(400).end(); return; }
    const f = join(APP, p);
    if (!existsSync(f)) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'content-type': TYPES[extname(f)] || 'application/octet-stream' });
    res.end(readFileSync(f));
  });
  await new Promise((r) => srv.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${srv.address().port}/`;
  const br = await browser();
  const pg = await br.newPage({ viewport: { width: 1000, height: 800 } });
  const errs = [];
  pg.on('pageerror', (e) => errs.push(String(e)));
  await pg.goto(`${url}pages/page_model.html`, { waitUntil: 'domcontentloaded' });
  await pg.addScriptTag({ url: '../assets/run.js' });
  await pg.addScriptTag({ url: '../assets/checkpoint.js' });

  const r = await pg.evaluate(async () => {
    const out = { steps: [] };
    const say = (name, pass, detail) => out.steps.push({ name, pass: !!pass, detail: detail || '' });
    if (!window.FyRun || !window.FyCheckpoint) { say('FyRun / FyCheckpoint 已加载', false); return out; }

    //: A deterministic stepper: the state is a running sum that DEPENDS on the
    //: state it was handed, so a marcher that dropped the state across a seam
    //: gets a different answer — which is exactly the failure the equivalence
    //: criterion is written to catch.
    const KERNEL = { sha256: 'aa11bb22cc33', abi: 125 };
    let calls = 0;
    const step = (from, count, state) => {
      calls++;
      let s = state ? state.sum : 0;
      for (let i = 0; i < count; i++) s = s * 1.000001 + (from + i + 1);
      const st = { step: from + count, sum: s };
      return Promise.resolve({
        steps: count, state: st,
        record: { id: 'r-gate', type: 'spo:ComputationRecord', run_state: 'running',
                  environment: { kernel_sha256: KERNEL.sha256, abi: KERNEL.abi },
                  'fylite:state': st }
      });
    };

    // (a) N in one go vs k + resume(N-k) — the criterion of §十三
    const one = await FyRun.march({ budget: 60, step, firstChunk: 60, msTarget: 1e9 }).promise;
    const partA = await FyRun.march({ budget: 23, step }).promise;
    const partB = await FyRun.march({ budget: 37, step, state: partA.state }).promise;
    say('N 步一次 ≡ k 步 + 恢复(N−k) 步（§十三 断点闸判据）',
        one.state.step === 60 && partB.state.step === 60 && one.state.sum === partB.state.sum,
        `one=${one.state.sum} split=${partB.state.sum}`);
    say('分片是多次调用，不是一次（U-8：一串门调用）', calls > 3, `${calls} 次 step()`);

    // (b) progress is counted, and the estimate is reported not promised
    const seen = [];
    const m2 = FyRun.march({ budget: 40, step, onProgress: (p) => seen.push(p) });
    await m2.promise;
    const last = seen[seen.length - 1];
    say('进度按步数出，末次 frac = 1，eta 有值', last && last.done === 40 && last.frac === 1
        && seen[0].etaMs === null && last.msPerStep !== null,
        `${seen.length} 次报告，首次 eta=${seen[0] && seen[0].etaMs}`);

    // (c) cancel: resolves, keeps what ran, never rejects, is not `hard`
    let ran = 0;
    const slow = (from, count, state) => new Promise((res) => setTimeout(() => {
      ran += count;
      res({ steps: count, state: { step: from + count }, record: { id: 'x', type: 'spo:ComputationRecord' } });
    }, 5));
    const m3 = FyRun.march({ budget: 1000, step: slow, msTarget: 10 });
    setTimeout(() => m3.cancel(), 40);
    const c = await m3.promise.then((v) => v, (e) => ({ threw: String(e) }));
    say('取消 = 切预算：promise 兑现、保住已算的步、不是硬中断（U-9）',
        !c.threw && c.cancelled === true && c.hard === false && c.done > 0 && c.done < 1000,
        `done=${c.done} hard=${c.hard} threw=${c.threw || 'no'}`);
    say('取消后步进器不再被调用', ran === c.done, `stepper ran ${ran}, march says ${c.done}`);
    const m4 = FyRun.march({ budget: 100, step: slow, msTarget: 10 });
    setTimeout(() => m4.cancel(true), 30);
    const c4 = await m4.promise;
    say('硬中断有自己的名字，不与取消混为一谈', c4.cancelled === true && c4.hard === true);

    // (d) the store: same bytes back, listed newest first, removable
    if (!FyCheckpoint.available()) { say('IndexedDB 可用', false, '这个上下文没有 IndexedDB'); return out; }
    await FyCheckpoint.clear();
    const rec = { id: 'r-1', type: 'spo:ComputationRecord',
                  environment: { kernel_sha256: KERNEL.sha256, abi: KERNEL.abi },
                  'fylite:state': { step: 20, sum: 1.5 } };
    const bytes = JSON.stringify(rec);
    const key = await FyCheckpoint.put('evolve-flattop', rec, { budget: 60 });
    const back = await FyCheckpoint.text(key);
    say('存进去的与取出来的是同一批字节（U-10 · U-18）', back === bytes,
        back === bytes ? '' : `${(back || '').length} vs ${bytes.length}`);
    const rows = await FyCheckpoint.list();
    say('清单行的每个值都读自记录，没有第二份真源',
        rows.length === 1 && rows[0].step === 20 && rows[0].kernel === KERNEL.sha256
        && rows[0].name === 'evolve-flattop' && rows[0].budget === 60,
        JSON.stringify(rows[0]));
    say('清单不带记录本身（列表不搬大对象）', rows[0].record === undefined);

    // (e) kernel identity (U-11 / S-6)
    const v1 = FyCheckpoint.resumable(rec, KERNEL);
    const v2 = FyCheckpoint.resumable(rec, { sha256: '99ff0011', abi: 125 });
    const v3 = FyCheckpoint.resumable({ id: 'x', type: 'spo:ComputationRecord' }, KERNEL);
    say('同一内核可续；换了内核按名拒绝并说出两个哈希（U-11）',
        v1.ok === true && v2.ok === false && /aa11bb22/.test(v2.why) && /99ff0011/.test(v2.why),
        v2.why);
    say('没有 fylite:state 的记录不谎称可续', v3.ok === false && /fylite:state/.test(v3.why), v3.why);
    let threw = null;
    try { FyCheckpoint.forResume(rec, { sha256: '99ff0011', abi: 125 }, false); } catch (e) { threw = String(e.message); }
    const forced = FyCheckpoint.forResume(rec, { sha256: '99ff0011', abi: 125 }, true);
    say('不允许漂移就拒绝；允许了就把漂移写进记录（U-11：写进 environment，不是写在一个复选框里）',
        threw && forced.environment.kernel_drift_allowed === true
        && forced.environment.kernel_sha256_written_by === KERNEL.sha256
        && (forced.caveat || []).some((x) => /显式允许/.test(x))
        && rec.environment.kernel_drift_allowed === undefined,
        threw ? '' : '未拒绝');

    // (f) the march hands records to the store, and a refusing store does not
    //     kill the march (P-10)
    await FyCheckpoint.clear();
    let saved = 0;
    const m5 = FyRun.march({ budget: 30, step, checkpointEvery: 10,
                             onCheckpoint: (record2, done) => { saved++; if (done === 20) throw new Error('仓满'); } });
    const c5 = await m5.promise;
    say('每 N 步落一次断点；仓拒绝时行军照走（P-10）', saved >= 2 && c5.done === 30, `saved=${saved}`);
    await FyCheckpoint.clear();
    return out;
  });

  for (const s of r.steps) (s.pass ? ok : fail)(`${s.name}${s.detail ? ' — ' + s.detail : ''}`);
  const fatal = errs.filter((e) => /run\.js|checkpoint\.js/.test(e));
  if (fatal.length) fail(`页面抛错：${fatal[0]}`);
  await br.close();
  srv.close();
}

console.log(bad ? `\n${bad} 处失败` : '\n断点闸全部通过');
process.exit(bad ? 1 : 0);
