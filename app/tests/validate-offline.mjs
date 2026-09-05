// The offline gate: the published site opens again after the network is gone
// (`FYL-DESIGN-18` U-20; `FYL-SRS-01` NR-ENV-001).
//
//     node app/tests/validate-offline.mjs [--playwright <dir>] [--chrome <bin>]
//
// ★The claim being measured is the SECOND half of「离线可用」.  The first —
// nothing is fetched once a page is loaded — has always been true and is not
// what fails.  What fails is a reload with no network, and the only way to know
// is to take the network away and reload.  So this gate does exactly that:
// loads a page, waits for the worker to take control, switches the context
// offline, reloads, and asserts the page is still a page.
//
// ★The precache list is checked against what the pages actually load.  A
// generated list can still be generated from the wrong place; the assertion
// that matters is that every `<script src>` and `<link href>` of every page is
// in it.  An asset missing from the cache breaks only the offline reload,
// which is the failure nobody notices until they are on a train.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { dirname, join, extname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..');
const REPO = join(APP, '..');
let bad = 0;
const fail = (m) => { console.log('  FAIL  ' + m); bad++; };
const ok = (m) => console.log('  ok    ' + m);

console.log('\n〔一〕生成物与生成器一致，清单覆盖每一页真正加载的东西');
try {
  execFileSync('node', [join(REPO, 'tools', 'make-sw.mjs'), '--check'], { encoding: 'utf8' });
  ok('sw.js 与 manifest.webmanifest 与 tools/make-sw.mjs 一致');
} catch (e) {
  fail('生成物已漂移 —— 重跑 node tools/make-sw.mjs');
}
const sw = readFileSync(join(APP, 'sw.js'), 'utf8');
const listed = new Set(JSON.parse(/const PRECACHE = (\[[\s\S]*?\]);/.exec(sw)[1]));
const pages = [...readdirSync(APP).filter((f) => f.endsWith('.html')).map((f) => f),
               ...readdirSync(join(APP, 'pages')).filter((f) => f.endsWith('.html')).map((f) => 'pages/' + f)];
const missing = new Set();
for (const p of pages) {
  if (!listed.has(p)) missing.add(p);
  const src = readFileSync(join(APP, p), 'utf8');
  for (const m of src.matchAll(/<(?:script src|link[^>]*href)="([^":]+)"/g)) {
    let ref = m[1];
    if (/^(https?:)?\/\//.test(ref) || ref.startsWith('#')) continue;
    //: resolve `../assets/x.js` from `pages/`
    const base = p.includes('/') ? p.slice(0, p.lastIndexOf('/') + 1) : '';
    const abs = new URL(ref, 'http://x/' + base).pathname.slice(1);
    if (!listed.has(abs) && existsSync(join(APP, abs))) missing.add(abs);
  }
}
if (missing.size) fail(`预缓存清单漏了 ${missing.size} 个：${[...missing].slice(0, 6).join(' ')}`);
else ok(`${pages.length} 张页面及其加载的每一个存在的资源都在清单里（清单 ${listed.size} 项）`);
if (/\/api\//.test(sw) && /url\.pathname\.indexOf\('\/api\/'\) >= 0\) return;/.test(sw))
  ok('/api/ 从不入缓存（桌面版的数据面必须是活的）');
else fail('sw.js 没有把 /api/ 排除在缓存之外');
if (!/const CACHE = 'fylite-' \+ VERSION/.test(sw)) fail('缓存名没有带版本');
else ok('缓存名带应用版本，装新版时清掉旧的');

console.log('\n〔二〕浏览器里：装上 worker，断网，重新打开');
const flag = (name, env) => { const i = process.argv.indexOf('--' + name); return i > 0 ? process.argv[i + 1] : process.env[env]; };
if (!flag('playwright', 'PLAYWRIGHT_PATH')) {
  console.log('  跳过 —— 用 --playwright <装有 playwright 的目录> 或设 $PLAYWRIGHT_PATH');
} else {
  const { browser } = await import('./_browser.mjs');
  const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                  '.css': 'text/css; charset=utf-8', '.json': 'application/json',
                  '.jsonld': 'application/ld+json', '.svg': 'image/svg+xml',
                  '.webmanifest': 'application/manifest+json' };
  let served = 0;
  //: 断网之后还打到服务器的那些路径，逐条记下来——「有几个」说不出是哪一个。
  let counting = false;
  const stray = [];
  const srv = createServer((req, res) => {
    const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    if (p.split('/').includes('..')) { res.writeHead(400).end(); return; }
    //: ★no `/api/health` here, on purpose: this server IS the site face, and
    //: `host.js` decides that by the endpoint not answering
    const f = join(APP, p === '/' ? 'index.html' : p);
    if (!existsSync(f) || !extname(f)) { res.writeHead(404).end(); return; }
    served++;
    if (counting) stray.push(p);
    res.writeHead(200, { 'content-type': TYPES[extname(f)] || 'application/octet-stream',
                         'cache-control': 'no-store' });
    res.end(readFileSync(f));
  });
  await new Promise((r) => srv.listen(0, '127.0.0.1', r));
  const url = `http://127.0.0.1:${srv.address().port}/`;
  const br = await browser();
  const ctx = await br.newContext();
  const pg = await ctx.newPage();
  await pg.goto(url + 'index.html', { waitUntil: 'load' });

  const reg = await pg.evaluate(async () => {
    if (!navigator.serviceWorker) return { sw: false };
    const r = await navigator.serviceWorker.ready.catch(() => null);
    //: `ready` resolves on activation; control of THIS page comes on the next
    //: navigation, which is the reload below
    return { sw: !!r, scope: r && r.scope,
             manifest: !!document.querySelector('link[rel="manifest"]') };
  });
  if (!reg.sw) fail('service worker 没有装上');
  else ok(`service worker 已激活（scope ${reg.scope}）`);
  if (!reg.manifest) fail('没有注入 <link rel="manifest">');
  else ok('manifest 已注入');

  //: give the precache a moment to finish adding, then pull the plug
  await pg.waitForTimeout(1500);
  const before = served;
  counting = true;
  await ctx.setOffline(true);
  const err = [];
  pg.on('pageerror', (e) => err.push(String(e)));
  let reloaded = true;
  try {
    await pg.reload({ waitUntil: 'load', timeout: 15000 });
  } catch (e) { reloaded = false; fail(`断网后重新打开失败：${String(e.message).split('\n')[0]}`); }

  if (reloaded) {
    //: ★what to assert on THIS page, and why not `FyI18n`.  `index.html` is a
    //: PROSE page: it is generated per language and deliberately loads neither
    //: `i18n.js` nor `site.js` (`tests/README.md`〔站点形状〕).  Asserting a
    //: script it never had would have failed here for a reason that has nothing
    //: to do with the cache — it did, on this gate's first run.  What it does
    //: load is `theme.js` and `host.js`, and what it has of its own is the
    //: hero and the footer that `make-app-pages.mjs` wrote into the markup.
    const state = await pg.evaluate(() => ({
      title: document.title,
      scripts: [...document.querySelectorAll('script[src]')].length,
      hasHost: !!(window.FyHost && FyHost.kind()),
      styled: getComputedStyle(document.body).backgroundColor,
      images: [...document.querySelectorAll('img')].filter((i) => i.complete && i.naturalWidth > 0).length,
      imgs: document.querySelectorAll('img').length
    }));
    if (!state.title) fail('断网后重新打开：页面没有标题');
    else if (!state.hasHost)
      fail('断网后重新打开：host.js 没从缓存出来');
    else if (state.imgs && state.images !== state.imgs)
      fail(`断网后重新打开：${state.imgs} 张图只画出 ${state.images} 张（SVG 没进缓存）`);
    else if (!/rgb/.test(state.styled))
      fail('断网后重新打开：样式表没从缓存出来');
    else ok(`断网后重新打开成功：标题「${state.title}」，${state.scripts} 个脚本、${state.imgs} 张图与样式表全部从缓存出来`);
    //: a page the reader had not visited before going offline must also open —
    //: that is what a PREcache is for, as against a cache of what was visited
    try {
      await pg.goto(url + 'pages/page_model.html', { waitUntil: 'domcontentloaded', timeout: 15000 });
      const t2 = await pg.evaluate(() => ({ ctl: document.querySelectorAll('.ctl').length,
                                            form: !!window.FyForm }));
      if (t2.ctl > 100 && t2.form)
        ok(`断网后打开一张从没访问过的页面：${t2.ctl} 个控件由词表画出来（预缓存不是浏览记录）`);
      else fail(`断网后的 page_model.html 只有 ${t2.ctl} 个控件`);
    } catch (e) {
      fail(`断网后打不开没访问过的页面：${String(e.message).split('\n')[0]}`);
    }
  }
  //: ★★**惰性制品不算数**（2026-09-05）。`tools/make-sw.mjs` 明写了两样东西不进
  //: 预缓存，理由都是「让每个只想看一眼首页的读者先付这笔钱是不对的」：中间层的
  //: `fylite_runtime.wasm`（2.14 MB，装置面板要用时才取）与 `assets/vendor/`
  //: （h5wasm，4.2 MB，打开 HDF5 时才取）。它们在断网后当然取不到——**那是那条
  //: 裁定的直接后果**，不是「离线坏了」。
  //: ★这一条在 2026-09-05 之前从未触发过，而原因不体面：`factsdb.js` 取那份 wasm
  //: 时用的是**相对页面**的地址，于是在 `pages/` 下的每一页都取成
  //: `pages/assets/fylite_runtime.wasm.…` 并得到 404——404 不进本服务器的计数。
  //: 地址修对之后，这一笔才第一次记上账。
  //: ★★留下的**真问题**照记：站点离线时装置面板没有装置（那份 wasm 取不到），
  //: 而页面对「一台机器也没有」的容忍度是逐处写的。要改就是改预缓存策略
  //: （+2.14 MB 首屏），那是一条要人裁的取舍，不该由这条闸子替谁决定。
  const LAZY = /\/assets\/fylite_runtime\.wasm|\/assets\/vendor\//;
  const strayCount = stray.filter((p) => !LAZY.test(p)).length;
  console.log(`  note  断网前伺服了 ${before} 个请求；断网后共 ${served - before} 个`
              + `（其中惰性制品 ${stray.length - strayCount} 个，按裁定不进预缓存）`);
  if (strayCount) fail('断网之后仍有请求打到服务器 —— 那不是离线：' + stray.join(' '));

  await ctx.setOffline(false);
  await br.close();
  srv.close();
}

console.log(bad ? `\n${bad} 处失败` : '\n离线闸全部通过');
process.exit(bad ? 1 : 0);
