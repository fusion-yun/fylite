// app/（本仓）-> fylite_engine 的 rust/fylite_engine/src/bin/app/assets.rs（内嵌资源表，生成物）
//
// ★为什么生成而不是手写：桌面版把整个 `app/` 编进可执行文件，需要一张
// 「路径 -> include_bytes! -> MIME」的表。手写它意味着每加一页、每换一个
// 图标都要记得改这里，而漏改的表现是**运行时 404**——一个只在别人机器上
// 才发现的缺失。生成器每次从目录本身读，漏不掉。
//
// 与 `tools/make-app-pages.mjs`、`rust/build.sh`（生成 `_abi.py` / `version.js`）
// 同一惯例：产物入库，门校验它与源同步。
//
// 不收 `tests/` 与 `server/`：与发布流水线送出去的那份 `app/` 保持同一子集
// ——桌面版分发的东西不该比站点多。
import { readdirSync, statSync, readFileSync, writeFileSync, existsSync } from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
const APP = HERE + '../app/';

//: ★★2026-09-02：`app/` 与 `rust/fylite_engine/` 都在本仓了——数据层从内核仓搬了
//: 过来，于是这张表的读者与被读的目录同处一棵树。从前这里要跨仓解析内核检出
//: （`$FYLITE_KERNEL`，探测不到就报错），那一整段随之取消：现在是一个相对路径，
//: 猜不错也不需要猜。
const OUT = HERE + '../rust/fylite_engine/src/bin/app/assets.rs';
const SKIP = new Set(['tests', 'server']);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.jsonld': 'application/ld+json; charset=utf-8',
  //: ★这一行是整张表里唯一不能出错的：浏览器只在 `application/wasm` 下走
  //: 流式编译，MIME 错了就是一句 TypeError，而不是一个慢一点的页面。
  '.wasm': 'application/wasm',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
};

function walk(dir, prefix = '') {
  const out = [];
  for (const name of readdirSync(dir).sort()) {
    if (prefix === '' && SKIP.has(name)) continue;
    const full = dir + name;
    //: 目录里现在没有符号链接了——`app/cases`（指向仓顶 `cases/`）随算例
    //: 菜单一同撤掉，`app/devices/*.jsonld` 仍是链接但由发布流水线落实体。
    //: `statSync` 跟随链接，这一点保持不变：真出现链接时收它指向的东西。
    const st = statSync(full);
    if (st.isDirectory()) out.push(...walk(full + '/', prefix + name + '/'));
    else out.push(prefix + name);
  }
  return out;
}

const files = walk(APP);
const unknown = [...new Set(files.map((f) => f.slice(f.lastIndexOf('.'))))]
  .filter((e) => !(e in MIME));
if (unknown.length) {
  console.error(`[embed] 不认识的扩展名：${unknown.join(' ')}`);
  console.error('[embed] 加进 MIME 表再跑——猜一个 content-type 比报错更糟');
  process.exit(1);
}

const rows = files.map((f) => {
  const ext = f.slice(f.lastIndexOf('.'));
  //: ★★路径过 `$FYLITE_APP_DIR`，不是相对 `.rs` 文件往上数。仓拆开之前
  //: 这里写的是 `../../../../../app/${f}`——从 `rust/fylite_engine/src/bin/app/` 上溯
  //: 五级到仓根再进 `app/`，同一个仓里成立。2026-09-01 `app/` 搬到主仓之后，
  //: 那条相对路径指向内核仓里并不存在的 `app/`，96 个文件全部
  //: `couldn't read`。★不改成绝对路径：那会把构建机的目录布局**编进内核源码**
  //: （而这棵树本来就在防这件事），而且换台机器即失效。用编译期环境变量，
  //: 由 `tools/build-app-exe.sh` 递进来，源码里留下的是一个名字不是一条路径。
  return `    ("${f}", include_bytes!(concat!(env!("FYLITE_APP_DIR"), "/${f}")), "${MIME[ext]}"),`;
}).join('\n');

const src = `//! \`app/\` 的内嵌资源表 —— **生成物**，勿手改。
//!
//! 由 \`tools/make-app-embed.mjs\` 从目录本身读出；改了 \`app/\` 之后重跑它，
//! 门 \`app/tests/validate-embed.mjs\` 校验两者同步。
//!
//! 表里是 (站点内路径, 字节, content-type)。路径用 \`/\` 分隔，与 URL 一致；
//! 查找是精确匹配，不做路径拼接——因此这张表天然免疫 \`..\` 穿越。

/// 站点的全部文件：路径、内容、content-type。
pub static ASSETS: &[(&str, &[u8], &str)] = &[
${rows}
];
`;

const check = process.argv.includes('--check');
if (check) {
  const have = readFileSync(OUT, 'utf8');
  if (have !== src) {
    console.error('[embed] assets.rs 与 app/ 不同步——重跑 node tools/make-app-embed.mjs');
    process.exit(1);
  }
  console.log(`[embed] assets.rs 与 app/ 一致（${files.length} 个文件）`);
} else {
  writeFileSync(OUT, src);
  console.log(`[embed] -> rust/fylite_engine/src/bin/app/assets.rs（${files.length} 个文件）`);
}
