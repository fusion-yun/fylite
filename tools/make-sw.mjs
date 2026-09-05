#!/usr/bin/env node
// Generate `app/sw.js` and `app/manifest.webmanifest` — the precache that makes
// the static site openable after the network is gone (`FYL-DESIGN-18` U-20,
// closing `-11`-adjacent gap G-5).
//
//     node tools/make-sw.mjs            # write both
//     node tools/make-sw.mjs --check    # fail if what is on disk differs
//
// ★What was and was not true before this.  「载入后离线可用」 was true: once a
// page and its wasm are in memory nothing else is fetched.  「断网后重新打开」
// was NOT — a reload with no network is a blank tab, because every asset comes
// off the origin.  `NR-ENV-001` says the browser runtime must be offline
// capable, and only the first half was measured.  A precache service worker is
// the whole difference.
//
// ★The list is GENERATED, not written.  A hand-kept precache list is a list
// that silently loses the asset added last week: the page still works for
// whoever has the network and fails only offline, which is the hardest failure
// to notice.  This walks `app/` the way `make-app-embed.mjs` walks it for the
// executable, so the two faces cache the same set.
//
// ★Cache-first, and versioned by the app version.  A stale asset is worse than
// a slow one here — the wasm and the page have to be the same build — so the
// cache name carries `FyVersion.app` and installing a new version drops every
// older cache in one sweep.  `/api/` is never cached: it is the desktop
// viewer's live data face, and a cached「网关未连」would outlive the gateway.
import { readdirSync, statSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..', 'app');
const check = process.argv.includes('--check');

//: directories that are not part of the published site (`build-site.sh` drops
//: the same three) plus the ones a precache must not pull in
const SKIP = new Set(['tests', 'server', 'facts', 'guide']);
const SKIP_FILE = /^(sw\.js|manifest\.webmanifest)$/;

function walk(dir, base = '') {
  const out = [];
  for (const name of readdirSync(dir).sort()) {
    if (base === '' && (SKIP.has(name) || SKIP_FILE.test(name))) continue;
    if (name.startsWith('.')) continue;
    const p = join(dir, name), rel = base ? `${base}/${name}` : name;
    const st = statSync(p);
    if (st.isDirectory()) out.push(...walk(p, rel));
    else out.push(rel);
  }
  return out;
}

//: ★★THE WASM IS ALWAYS LISTED, PRESENT OR NOT — and that is what makes this
//: file deterministic.  The three modules are built into `app/assets/` by the
//: kernel repo and are NOT in git (`.gitignore`), so walking the tree gives a
//: different answer on a checkout that has built them and one that has not:
//: whoever regenerates without a build would silently drop them from the
//: published site's precache, and `--check` would go red for everyone else.
//: They are part of the published site by definition, so they are named here
//: rather than discovered.  `install` tolerates a member that 404s, which is
//: exactly the source-checkout case.
//: ★★2026-09-05 名字带版本（`tools/soname.sh`）：页面取的是
//: `assets/fylite_rs.wasm.<kernel>`，因为站点构建只发真文件、不发那两级符号链接。
//: 预缓存表必须用**同一条规则**算出**同一串 URL** —— 差一个字符的后果是：在线时
//: 一切正常，断网重载 404，而这正是这份文件存在的理由。
//: 规则的另一半在 `app/assets/fylite.js` 的 `versioned()`（导出为 `FyLite.wasmUrl`）；
//: 这里按同一条拼，并由 `--check` 保证生成物与磁盘一致。
//: ★中间层那一份**不进预缓存**：它是装置面板要用时才取的（`factsdb.js` 惰性载入），
//: 而它有两兆多。把它塞进首屏的预缓存，等于让每个只想看一眼首页的读者先付这笔钱。
//: 离线时装置面板因此可能取不到——那是一句「这一版没带装置信息」，不是页面打不开。
const WASM_STEMS = ['assets/fylite_rs.wasm', 'assets/fylite_kernel_ext.wasm'];
//: ★★VENDORED THIRD-PARTY MEGABYTES ARE NOT PRECACHED (`FYL-DESIGN-18` U-25).
//: `assets/vendor/h5wasm/` is ~4.2 MB — more than this repository's three
//: kernel modules together — and it is an ON-DEMAND capability: `h5source.js`
//: pulls it with a dynamic `import()` the first time somebody opens an HDF5
//: file.  Precaching it would make every reader pay, on every first visit, for
//: something most of them never use, and would quadruple what an offline
//: install costs.  A reader who DOES open one gets it kept by the service
//: worker's runtime cache, so the second time is offline-capable too.
const VENDOR = /^assets\/vendor\//;
//: ★★`.wasm` 与 `.wasm.<版本>` 两种拼写都从走树的结果里滤掉：目录里同时躺着真
//: 文件与两级符号链接，走树会把三份都收进来，于是预缓存表里出现同一份字节的三个
//: 名字（其中两个站点根本不发）。它们由下面的 `WASM_STEMS` 具名给出。
const WASMISH = /\.wasm(\.[0-9][^/]*)?$/;
const walked = walk(APP).filter((f) => !/\.(map|md)$/.test(f) && !WASMISH.test(f)
                                       && !VENDOR.test(f));

const version = (() => {
  const m = /app:\s*'([^']+)'/.exec(readFileSync(join(APP, 'assets', 'version.js'), 'utf8'));
  return m ? m[1] : '0';
})();
//: 内核版本 —— URL 的后缀。★与 app 版本读自同一份生成物（`version.js`，内核仓
//: 的构建写的），所以「页面以为的内核版本」与「文件名上的版本」不可能是两个数。
const kernelVersion = (() => {
  const m = /kernel:\s*'([^']+)'/.exec(readFileSync(join(APP, 'assets', 'version.js'), 'utf8'));
  if (!m) throw new Error('make-sw: assets/version.js 里读不出 kernel 版本');
  return m[1];
})();
const WASM = WASM_STEMS.map((f) => `${f}.${kernelVersion}`);
const files = walked.concat(WASM).sort();
const wasm = WASM.filter((f) => existsSync(join(APP, f)));

const sw = `// GENERATED by tools/make-sw.mjs — do not edit.  Re-run it after adding an
// asset; the list below is what an offline reload has to find in the cache
// (\`FYL-DESIGN-18\` U-20).
//
// ★Cache-first for everything in the list, network-only for \`/api/\`.  A
// desktop viewer's data face must never be answered out of a cache: 「网关未连」
// cached once would outlive the gateway coming up.
// ★One cache per app version.  The page and the wasm are one build; serving a
// new page against an old module is the failure this naming prevents, and
// activate() drops every cache that is not this one.
const VERSION = ${JSON.stringify(version)};
const CACHE = 'fylite-' + VERSION;
const PRECACHE = ${JSON.stringify(files, null, 2)};

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) =>
    //: ★one at a time, and a miss does not fail the install.  \`addAll\` is
    //: all-or-nothing: one asset that 404s (a wasm that this checkout does not
    //: carry) would leave the site with NO cache at all rather than a partial
    //: one, and the reader would discover it only offline.
    Promise.all(PRECACHE.map((u) => c.add(u).catch(() => null)))
  ).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.indexOf('/api/') >= 0) return;          // the live data face
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((hit) =>
    hit || fetch(e.request).then((res) => {
      //: what was fetched and is ours joins the cache, so a page reached by a
      //: link nobody precached is there next time too
      if (res && res.ok && res.type === 'basic') {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    }).catch(() => hit))
  );
});
`;

const manifest = {
  name: 'fylite',
  short_name: 'fylite',
  description: 'a self-contained tokamak equilibrium, transport and turbulence kernel',
  start_url: './index.html',
  scope: './',
  display: 'standalone',
  background_color: '#f4f5f7',
  theme_color: '#1668c8',
  icons: [{ src: './assets/fy_mark.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }]
};

const targets = [['sw.js', sw],
                 ['manifest.webmanifest', JSON.stringify(manifest, null, 2) + '\n']];
let stale = [];
for (const [name, body] of targets) {
  const p = join(APP, name);
  const old = existsSync(p) ? readFileSync(p, 'utf8') : null;
  if (check) {
    console.log(`  ${old === body ? 'ok     ' : 'DIFFERS'}  app/${name}`);
    if (old !== body) stale.push(name);
  } else {
    writeFileSync(p, body);
    console.log(`  app/${name}  (${(body.length / 1024).toFixed(1)} kB)`);
  }
}
if (!check) console.log(`  预缓存 ${files.length} 个文件（含三份 wasm；本检出实有 ${wasm.length} 份）`);
if (stale.length) {
  console.error(`生成物已漂移，请重跑 node tools/make-sw.mjs：\n  ${stale.join('\n  ')}`);
  process.exit(1);
}
