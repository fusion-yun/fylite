// docs/guide/ (the subset named by public.yml)  ->  app/guide/*.html
//
// ★指南与仓内其余章节住在同一本书 `docs/guide/` 里（2026-09-01：原
// `docs/user_guide/` 并入）。「哪几篇随演示公开发布」由 `docs/guide/public.yml`
// 的 toc 定——一处来源；发布面与目录**不是**同一件事，所以它是一张单独的表
// 而不是一个按目录取的通配。
//
// ★为什么不是 `myst build --html`。MyST 的站点构建要从 `api.mystmd.org` 下载一份
// 站点模板，这给发布链加了一个**远端依赖**：一台离线或受网络策略约束的机器上，
// 「重建产物」这件事会失败，而产物入库的全部意义就是任何人都能重建它并逐字比对。
// 而且 book-theme 是它自己的一整套设计系统，与站点其余页面的外观互不相干。
//
// 所以这里用的是 MyST 的**解析与渲染库本身**（`myst-parser` + `myst-to-html`，
// 都在 npm 上，可离线缓存）：语法、指令、容器、表格全部由 MyST 处理，本文件只
// 负责把渲染出的片段套进站点自己的外壳（同一份 `site.css` / `style.css`、
// 同样的页头页脚），使指南与它所属的站点看起来是一件东西。
//
// 用法：node tools/make-guide-pages.mjs [--check]
import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync, readdirSync } from 'node:fs';
import { mystParse } from 'myst-parser';
import { mystToHtml } from 'myst-to-html';

const HERE = new URL('.', import.meta.url).pathname;
//: ★2026-09-02 工具搬回公开仓：`docs/` 与 `app/` 都在隔壁。
const SRC = HERE + '../docs/guide/';
//: 公开子集的名单（顺序即侧栏顺序）。仓内其余章节不在其中，也不该在——
//: 它们引仓内路径与文档编号，公开页上那些都是断链。
const PUBLIC = 'public.yml';
const DEST = HERE + '../app/guide/';
const PUB = 'https://fusion-yun.github.io/fylite/guide/';

//: ★★2026-09-01 仓一分为二：这份 `abi.json` 由 fylite_kernel 的 `rust/build.sh`
//: 生成，并**装进本仓** `app/assets/`。此前这里读的是 `../rust/wasm/abi.json`
//: ——那是一条跨仓的运行期依赖，仓拆开之后本仓单独一份检出就再也生不出
//: 页脚上的版本号。读装进来的那份，本仓自足。
const VER = JSON.parse(readFileSync(HERE + '../app/assets/abi.json', 'utf8'));

/** 目录顺序取自 public.yml 的 toc —— 一处来源，不在本文件里再抄一遍。 */
function toc() {
  const y = readFileSync(SRC + PUBLIC, 'utf8');
  const block = y.slice(y.indexOf('\n  toc:'));
  return [...block.matchAll(/- file:\s*(\S+\.md)/g)].map((m) => m[1]);
}

const esc = (s) => String(s).replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/** frontmatter 归 frontmatter，正文归 MyST。 */
function split(md) {
  const m = /^---\n([\s\S]*?)\n---\n/.exec(md);
  if (!m) return { meta: {}, body: md };
  const meta = {};
  for (const line of m[1].split('\n')) {
    const kv = /^(\w+):\s*(.*)$/.exec(line);
    if (kv) meta[kv[1]] = kv[2].replace(/^["']|["']$/g, '');
  }
  return { meta, body: md.slice(m[0].length) };
}

function page({ id, title, sub, html, pages }) {
  //: 侧栏是本书的目录；当前页不做成链接——一个指向自己的链接是噪音
  const side = pages.map((p) => (p.id === id
    ? `    <span class="here">${esc(p.title)}</span>`
    : `    <a href="${p.id}.html">${esc(p.title)}</a>`)).join('\n');
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)} · fylite 用户指南</title>
<link rel="icon" href="../assets/fy_mark.svg">
${sub ? `<meta name="description" content="${esc(sub)}">\n` : ''}<link rel="stylesheet" href="../assets/style.css">
<link rel="stylesheet" href="../assets/site.css">
<link rel="stylesheet" href="guide.css">
<script src="../assets/theme.js"></script>
</head>
<body data-page="guide">

<header class="top">
  <a class="brand" href="../index.html"><img src="../assets/fy_mark.svg" alt="" width="32" height="32"></a>
  <div class="titles">
  <h1>${esc(title)}</h1>
  <span class="sub">fylite 用户指南</span>
  </div>
  <nav>
    <a href="../index.html">演示首页</a>
    <a href="../features.html">功能与边界</a>
    <button id="theme-toggle" class="iconbtn" type="button"></button>
  </nav>
</header>

<div class="guide-wrap">
<aside class="guide-toc" aria-label="目录">
${side}
</aside>

<main class="doc guide-body">
${html}
</main>
</div>

<footer>
  <a class="mark" href="../index.html" tabindex="-1" aria-hidden="true"><img src="../assets/fy_mark.svg" alt="" width="24" height="24"></a>
  <a href="../index.html">fylite 首页</a>
  <a href="index.html">指南目录</a>
  <span class="copy">© 2026 中国科学院等离子体物理研究所（ASIPP）与 fylite 贡献者 · Apache-2.0 · alpha 版</span>
  <span class="ver" title="kernel ${VER.kernel_version} · interface ${VER.abi_version} · app ${VER.app_version}">内核 ${VER.kernel_version} · 接口 ${VER.abi_version} · 前端 ${VER.app_version}</span>
</footer>

</body>
</html>
`;
}

const files = toc();
const pages = files.map((f) => {
  const { meta, body } = split(readFileSync(SRC + f, 'utf8'));
  const id = f.replace(/\.md$/, '');
  return { id, file: f, title: meta.title || id, body };
});

const out = new Map();
for (const p of pages) {
  //: MyST 解析 + 渲染；.md 链接改指生成出来的 .html
  const html = mystToHtml(mystParse(p.body))
    .replace(/href="([\w-]+)\.md(#[^"]*)?"/g, 'href="$1.html$2"')
    //: 正文的首个 h1 与页头标题是同一句话，去掉一份——留两份是排版噪音，
    //: 而去掉 markdown 里的那句会让源文件在别的阅读器里失去标题
    .replace(/^\s*<h1>[\s\S]*?<\/h1>/, '');
  const sub = /<p>([\s\S]*?)<\/p>/.exec(html);
  out.set(`${p.id}.html`, page({
    id: p.id,
    title: p.title,
    sub: sub ? sub[1].replace(/<[^>]*>/g, '').slice(0, 150) : '',
    html,
    pages,
  }));
}
out.set('guide.css', readFileSync(HERE + 'app-pages/guide.css', 'utf8'));

const check = process.argv.includes('--check');
if (check) {
  let bad = 0;
  const have = existsSync(DEST) ? new Set(readdirSync(DEST)) : new Set();
  for (const [name, text] of out) {
    if (!have.has(name)) { console.error(`[guide] 缺 ${name}`); bad++; continue; }
    if (readFileSync(DEST + name, 'utf8') !== text) {
      console.error(`[guide] ${name} 与源不同步`); bad++;
    }
    have.delete(name);
  }
  for (const extra of have) { console.error(`[guide] 多余 ${extra}`); bad++; }
  if (bad) { console.error('[guide] 重跑 bash tools/build-guide.sh'); process.exit(1); }
  console.log(`[guide] app/guide/ 与 docs/guide/ 的公开子集一致（${out.size} 个文件）`);
} else {
  rmSync(DEST, { recursive: true, force: true });
  mkdirSync(DEST, { recursive: true });
  for (const [name, text] of out) writeFileSync(DEST + name, text);
  console.log(`[guide] -> app/guide/ （${out.size} 个文件）`);
  for (const name of out.keys()) console.log('   ', name);
  console.log(`[guide] 发布后位于 ${PUB}`);
}
