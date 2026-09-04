#!/usr/bin/env node
// Vendor h5wasm into `app/assets/vendor/h5wasm/` (`FYL-DESIGN-18` U-25).
//
//     node tools/vendor-h5wasm.mjs            # fetch, verify, write
//     node tools/vendor-h5wasm.mjs --check    # fail if what is on disk differs
//
// ★Why vendored and not fetched at run time.  The app has no build step and no
// package manager at the reader's end; a page that pulled a module off a CDN
// would stop working the moment the network went (U-20) and would hand a third
// party the ability to change what runs in a reader's browser.  So the bytes
// live here, and this script is how they got here — version, size and sha256
// written into `PROVENANCE.md` beside them.
//
// ★What the licence obliges (read it: `LICENSE.txt`, copied verbatim).  h5wasm
// is NIST-developed software: the notice must be kept INTACT with the copy, the
// National Institute of Standards and Technology must be explicitly
// acknowledged as the source, and modified works must say what was changed and
// when.  Nothing here is modified — this script copies, it does not patch — and
// that fact is recorded so the third clause has a documented answer.
//
// ★Only the ESM build is taken.  The IIFE bundle is 5.7 MB against the ESM
// pair's 4.2 MB, and the pages load it with a dynamic `import()` anyway
// (`h5source.js`): the cost is paid by a reader who opens an HDF5 file and by
// nobody else.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, mkdirSync, existsSync, rmSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const DEST = join(HERE, '..', 'app', 'assets', 'vendor', 'h5wasm');
const check = process.argv.includes('--check');

//: ★pinned, and the pin is the point.  A floating version would change what a
//: reader's browser runs without a commit here saying so.
const VERSION = '0.10.3';
const TAKE = [
  ['dist/esm/hdf5_hl.js', 'hdf5_hl.js'],
  ['dist/esm/hdf5_util.js', 'hdf5_util.js'],
  ['LICENSE.txt', 'LICENSE.txt'],
];

function fetchPackage() {
  const dir = join(tmpdir(), `h5wasm-vendor-${process.pid}`);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  execFileSync('npm', ['pack', `h5wasm@${VERSION}`], { cwd: dir, stdio: 'pipe' });
  const tgz = readdirSync(dir).find((f) => f.endsWith('.tgz'));
  execFileSync('tar', ['xzf', tgz], { cwd: dir });
  return join(dir, 'package');
}

const sha = (b) => createHash('sha256').update(b).digest('hex');

const pkg = fetchPackage();
const files = TAKE.map(([from, to]) => {
  const body = readFileSync(join(pkg, from));
  return { to, body, size: body.length, sha: sha(body) };
});

const prov = `# h5wasm —— 出处与许可

★**这是别人的代码，逐字节照抄，一处未改。** 本目录由 \`tools/vendor-h5wasm.mjs\`
写出；改版本要改那个脚本里的 \`VERSION\` 并重跑，不要手改这里的任何文件。

| 项 | 值 |
| :--- | :--- |
| 上游 | \`h5wasm\` （npm） |
| 版本 | \`${VERSION}\` （**钉死**：浮动版本会在没有任何提交说明的情况下改变读者浏览器里跑的东西） |
| 取自 | \`npm pack h5wasm@${VERSION}\` 的 \`dist/esm/\` |
| 许可 | NIST 公共服务条款，见同目录 \`LICENSE.txt\`（**原样保留，不得删改**） |
| 改动 | **无**。本脚本只拷贝，不打补丁——许可里「修改过的作品应注明改了什么、何时改的」这一条因此有一个确定的答案：没有改动 |
| 内含 | HDF5 C 库（经 Emscripten 编成 wasm，以 base64 内嵌在 \`hdf5_util.js\` 里，故没有独立的 \`.wasm\`） |

| 文件 | 字节 | sha256 |
| :--- | ---: | :--- |
${files.map((f) => `| \`${f.to}\` | ${f.size.toLocaleString('en-US')} | \`${f.sha}\` |`).join('\n')}

★**为什么这几 MB 不进预缓存。** 两个 ESM 文件合计约 4.2 MB，比本仓自己的三份内核
wasm 加起来（约 1.56 MB）还大。它是**按需能力**，不是每个读者都要的东西，所以
\`h5source.js\` 用动态 \`import()\` 取它，\`tools/make-sw.mjs\` 把本目录排除在预缓存之外：
打开过 HDF5 的读者由 service worker 的运行时缓存留下它，没打开过的人一个字节也不下。

★**致谢是许可义务，不是客套**：NIST 条款要求「明确承认 NIST 为该软件的来源」。
这句话落在 \`docs/ACKNOWLEDGEMENTS.md\` 与 \`app/credits.html\`，不只落在这里。
`;

const want = files.map((f) => [f.to, f.body])
  .concat([['PROVENANCE.md', Buffer.from(prov, 'utf8')]]);

if (check) {
  let bad = 0;
  for (const [name, body] of want) {
    const p = join(DEST, name);
    const old = existsSync(p) ? readFileSync(p) : null;
    const same = old && Buffer.compare(old, body) === 0;
    console.log(`  ${same ? 'ok     ' : 'DIFFERS'}  ${name}`);
    if (!same) bad++;
  }
  if (bad) { console.error(`h5wasm 的 vendor 目录已漂移，请重跑 node tools/vendor-h5wasm.mjs`); process.exit(1); }
  console.log(`h5wasm ${VERSION} 与上游一致。`);
} else {
  mkdirSync(DEST, { recursive: true });
  for (const [name, body] of want) writeFileSync(join(DEST, name), body);
  const total = files.reduce((a, f) => a + f.size, 0);
  console.log(`h5wasm ${VERSION} -> app/assets/vendor/h5wasm/  (${(total / 1048576).toFixed(2)} MB, ${files.length} 个文件 + PROVENANCE.md)`);
}
