// 文件端点：桌面宿主替页面读文件，读出来的必须与原生读法**同一份文档**。
//
// ★★2026-09-05 用户裁定：*hdf5 走 fy app 的文件端点，静态站点保留 h5wasm*。
// 于是同一份 `.h5` 有两条读法——页面里的 h5wasm（NIST 的 Emscripten 包，4.1 MB）与
// 本进程链着的 libhdf5。**两条读法就是两个可能不一致的答案**，除非有人比。
//
// 比的方式与 `validate-h5.mjs` 同一个锚：`fixtures/equilibrium.json` 是**原生读法**
// 对 `fixtures/equilibrium.h5` 的结果，两份都提交在仓里。那条闸子拿它验浏览器那一路；
// 这条拿它验请求面那一路。于是两条读法各自对同一个参照负责，而不是互相对照——
// 互相对照的坏处是两边一起漂的时候没人会红。
//
//   node app/tests/validate-file-api.mjs
//
// ★这条闸子要一个**带 hdf5 那一面的 `fy`**。没有就跳过并说明为什么——那是「这台
// 机器上没建过」，不是「不通过」。
// ★服务端那半用 curl（node 起进程即可，不必开浏览器）；页面选路那半要 playwright，
// 没有就只跳过那一段。

import { existsSync, readFileSync } from 'node:fs';
import { execFileSync, spawn } from 'node:child_process';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../../';
const EXE = ROOT + 'rust/fylite_runtime/target/release/fy';
const FIX = HERE + 'fixtures/equilibrium.h5';
const REF = HERE + 'fixtures/equilibrium.json';
const PORT = 8910 + (process.pid % 400);

for (const [p, why] of [[EXE, '先跑 bash tools/build-app-exe.sh --mode web'],
                        [FIX, '夹具缺失（fixtures/README.md 有配方）'],
                        [REF, '原生参照缺失（同上）']]) {
  if (!existsSync(p)) { console.log(`跳过：没有 ${p} —— ${why}`); process.exit(0); }
}

const app = spawn(EXE, ['app', '--port', String(PORT), '--no-open', '--app-dir', ROOT + 'app'],
                  { stdio: ['ignore', 'pipe', 'pipe'] });
const BASE = `http://127.0.0.1:${PORT}/`;
process.on('exit', () => app.kill());

const curl = (args, input) =>
  execFileSync('curl', ['-s', '--noproxy', '*', ...args],
               { encoding: 'utf8', input: input === undefined ? '' : input,
                 maxBuffer: 256 * 1024 * 1024 });

let health = null;
for (let i = 0; i < 60; i++) {
  try { health = JSON.parse(curl([BASE + 'api/health'])); break; }
  catch (e) { execFileSync('sleep', ['0.1']); }
}
if (!health) { console.error('fy app 没起来'); process.exit(1); }

let bad = 0;
const ok = (cond, what, note) => {
  console.log(`  ${cond ? 'ok  ' : '✗   '} ${what}${note ? '  — ' + note : ''}`);
  if (!cond) bad += 1;
};

console.log('〔一〕请求面自报它读得了文件');
if (!health.file) {
  //: ★没有 hdf5 那一面的构建（`--no-default-features` 之类）**照答**，答的是 false。
  //: 那不是坏了，是这一版不带；页面据此走 h5wasm。所以这里跳过而不是判红。
  console.log('  跳过：这个 fy 的 /api/health 说 file:false（构建时没有 hdf5 那一面）');
  process.exit(0);
}
ok(health.file === true, '/api/health 的 file 格为真');

console.log('\n〔二〕同一份 .h5，与原生参照逐叶子相同');
const answer = curl(['-X', 'POST', '--data-binary', '@' + FIX,
                     BASE + 'api/read?name=equilibrium.h5']);
let doc = null;
try { doc = JSON.parse(answer); } catch (e) { /* 下面报 */ }
ok(!!doc && !doc.error, '端点答了一份文档', doc && doc.error ? doc.error : answer.slice(0, 80));
if (doc && !doc.error) {
  const leaves = (o, p = '', acc = {}) => {
    if (Array.isArray(o)) { acc[p] = o.join(','); return acc; }
    if (o && typeof o === 'object') {
      for (const k of Object.keys(o)) leaves(o[k], p ? p + '/' + k : k, acc);
      return acc;
    }
    acc[p] = o; return acc;
  };
  const a = leaves(JSON.parse(readFileSync(REF, 'utf8'))), b = leaves(doc);
  const missing = Object.keys(a).filter((k) => !(k in b));
  const extra = Object.keys(b).filter((k) => !(k in a));
  const differ = Object.keys(a).filter((k) => k in b && String(a[k]) !== String(b[k]));
  ok(missing.length === 0 && extra.length === 0, '叶子集合相同',
     `缺 ${JSON.stringify(missing)} 多 ${JSON.stringify(extra)}`);
  ok(differ.length === 0, `逐叶子取值相同（${Object.keys(a).length} 片）`,
     differ.slice(0, 3).map((k) => `${k}: ${a[k]} vs ${b[k]}`).join('; '));
  //: ★标量与长度 1 的数组之别：属性与 dataset 在 HDF5 里是两种东西，读错这一处
  //: 得到的文档看起来完全正常。
  ok(typeof doc.time_slice.global_quantities.ip === 'number' && Array.isArray(doc.time),
     '标量是标量、数组是数组（属性 ↔ dataset 的分别没有丢）');
}

console.log('\n〔三〕拒绝的那几种，各说各的话');
const refuse = (what, args, input) => {
  const t = curl(['-X', 'POST', ...args], input);
  let j = null;
  try { j = JSON.parse(t); } catch (e) { /* 非 JSON 也算没拒对 */ }
  ok(!!(j && j.error), what, (j && j.error ? j.error : t).slice(0, 90));
};
refuse('不是 HDF5 的按名拒绝', ['--data-binary', '@-', BASE + 'api/read?name=x.h5'], 'not an hdf5 file');
refuse('空正文', ['--data-binary', '@-', BASE + 'api/read?name=x.h5'], '');
refuse('文件名里带路径分隔符', ['--data-binary', '@' + FIX,
                              BASE + 'api/read?name=..%2Fetc%2Fpasswd']);

console.log('\n〔四〕页面在这个宿主里走的是端点，不是那 4 MB');
const pw = process.env.PLAYWRIGHT_PATH
        || (process.argv.indexOf('--playwright') > 0
            ? process.argv[process.argv.indexOf('--playwright') + 1] : null);
if (!pw) {
  console.log('  跳过 —— 用 --playwright <装有 playwright 的目录> 或设 $PLAYWRIGHT_PATH');
} else {
  const { createRequire } = await import('node:module');
  const req = createRequire(pw.replace(/\/*$/, '/') + 'x.js');
  const { chromium } = req('playwright');
  const bin = process.env.CHROME_PATH;
  const br = await chromium.launch(bin ? { executablePath: bin } : {});
  const pg = await br.newPage();
  const seen = [];
  pg.on('request', (r) => {
    if (/api\/read|vendor\/h5wasm/.test(r.url())) seen.push(r.url().replace(BASE, ''));
  });
  await pg.goto(BASE + 'pages/analysis.html', { waitUntil: 'load' });
  await pg.addScriptTag({ url: BASE + 'assets/h5source.js' });
  const bytes = [...readFileSync(FIX)];
  const r = await pg.evaluate(async (b) => {
    try {
      const doc = await self.FyH5.read(new Uint8Array(b), { name: 'equilibrium.h5' });
      return { ok: true, type: doc['@type'], h5wasm: self.FyH5.loaded(),
               ip: doc.time_slice.global_quantities.ip };
    } catch (e) { return { ok: false, why: e.message }; }
  }, bytes);
  await br.close();
  ok(r.ok && r.type === 'fyo:equilibrium', '页面读出了同一份文档',
     r.ok ? `ip=${r.ip}` : r.why);
  ok(r.h5wasm === false, '而且**没有**载入那 4 MB 的 h5wasm', `loaded=${r.h5wasm}`);
  ok(seen.some((u) => u.includes('api/read')) && !seen.some((u) => u.includes('h5wasm')),
     '实测的请求只有 /api/read', seen.join(' ') || '（没有请求）');
}

console.log('\n判定：' + (bad ? `文件端点 ${bad} 项不符` : '文件端点与原生读法同一份文档'));
process.exit(bad ? 1 : 0);
