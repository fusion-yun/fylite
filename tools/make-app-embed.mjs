// app/（本仓）-> fylite_runtime 的 rust/fylite_runtime/src/bin/app/assets.rs（内嵌资源表，生成物）
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
import { readdirSync, statSync, lstatSync, realpathSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const HERE = new URL('.', import.meta.url).pathname;
//: ★★`--from DIR` —— 描述**要内嵌的那一棵树**，不是源树。缺省仍是 `app/`（提交进仓
//: 的那张表因此是源树的），而 `tools/build-app-exe.sh` 给的是它装好的那一棵：
//: 可执行文件从 2026-09-05 起**一份 wasm 也不带**：装置信息走它自己的 `/api/facts`
//: （那张表已经在这个进程里），算力走 `/api/kernel`（内核静态库链在里面）——两条都是
//: 当天的用户裁定。于是「表描述的」与「编译期真在的」必须
//: 是同一棵——否则 `include_bytes!` 在编译期指着一个不存在的文件，而那是一屏
//: `couldn't read`，看起来像编译坏了。
const FROM = (() => {
  const i = process.argv.indexOf('--from');
  if (i < 0) return null;
  const d = process.argv[i + 1];
  return d.endsWith('/') ? d : d + '/';
})();
const APP = FROM || (HERE + '../app/');

//: ★★2026-09-02：`app/` 与 `rust/fylite_runtime/` 都在本仓了——数据层从内核仓搬了
//: 过来，于是这张表的读者与被读的目录同处一棵树。从前这里要跨仓解析内核检出
//: （`$FYLITE_KERNEL`，探测不到就报错），那一整段随之取消：现在是一个相对路径，
//: 猜不错也不需要猜。
const OUT = HERE + '../rust/fylite_runtime/src/bin/app/assets.rs';
//: ★★`facts` 仍在跳过名单里，但**理由变了**：2026-09-05 用户裁定「fylite 下已无
//: facts 目录」，`app/facts` 那条指向仓根的符号链接随之撤除，所以今天这里根本没有
//: 这个目录可走。留着这一条是**防回归**——那条链接一旦被谁重新拉起来，`statSync`
//: 会跟着它把整份语料（逐个的卡片、许可账、只进内部版的机器）编进可执行文件。
//: 装置文档按**同一条发布规则**逐份加进来，从暂存的那棵树里取（见下）。
const SKIP = new Set(['tests', 'server', 'facts']);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.jsonld': 'application/ld+json; charset=utf-8',
  //: ★★`app/manifest.webmanifest`（`tools/make-sw.mjs` 的产物）落地时漏了这一格，
  //: 于是本生成器**在 develop 上一直跑不起来**——按名拒绝，不猜 content-type。
  //: 没人先发现，是因为 `rust/build.sh --exe` 读的是已提交的 `assets.rs`，只有
  //: `tools/build-app-exe.sh` 会重跑生成器。规范值是 `application/manifest+json`。
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  //: ★这一行是整张表里唯一不能出错的：浏览器只在 `application/wasm` 下走
  //: 流式编译，MIME 错了就是一句 TypeError，而不是一个慢一点的页面。
  //: ★★2026-09-05：磁盘上的名字是 `fylite_rs.wasm.0.0.1`（`tools/soname.sh`），
  //: 「最后一个点之后」已经不是扩展名了——查表前先经 `logicalName()` 把版本后缀
  //: 剥掉。这张表按逻辑名索引，发出去的仍是 `application/wasm`：本仓的加载器不
  //: 依赖它（走 arrayBuffer），但内嵌服务器发对了，别的读者才不必猜。
  '.wasm': 'application/wasm',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8',
};

//: 版本化制品的**逻辑名**：`fylite_rs.wasm.0.0.1` -> `fylite_rs.wasm`。
//: 只认 `.so` / `.wasm` 后面跟一串以数字开头的版本——不写成「剥掉最后一段」，
//: 那会把 `g900003.00230_ITER…` 这类本来就带点的文件名一起剥了。
const SONAME = /^(.*\.(?:wasm|so))\.[0-9][0-9A-Za-z.+-]*$/;
function logicalName(f) { const m = SONAME.exec(f); return m ? m[1] : f; }

function walk(dir, prefix = '') {
  const out = [];
  for (const name of readdirSync(dir).sort()) {
    if (prefix === '' && SKIP.has(name)) continue;
    const full = dir + name;
    //: ★★符号链接不进表（2026-09-05）。版本化之后 `app/assets/` 里一份 wasm 有
    //: 三个名字：真文件 `.wasm.0.0.1` 加 `.wasm.0` 与 `.wasm` 两级链接。`statSync`
    //: 跟随链接，照原样走下去会把**同一兆多字节编进可执行文件三遍**，而且其中两个
    //: 名字站点根本不发（`build-site.sh` 只发真文件）。收真文件那一个就够——
    //: 页面取的正是它（`fylite.js` 的 `versioned()`）。
    //: ★只滤**指向版本化真文件的**那种链接，不是「所有链接一概不收」：上面那段
    //: 老注释说的「真出现链接时收它指向的东西」对别的链接仍然成立，而这里要挡的
    //: 是一个具体的形状——两个别名指着同一份字节。
    if (lstatSync(full).isSymbolicLink() &&
        SONAME.test(realpathSync(full).split('/').pop())) continue;
    //: 目录里现在没有符号链接了——`app/cases`（指向仓顶 `cases/`）随算例
    //: 菜单一同撤掉，`app/facts/device/*.jsonld` 仍是链接但由发布流水线落实体。
    //: `statSync` 跟随链接，这一点保持不变：真出现链接时收它指向的东西。
    const st = statSync(full);
    if (st.isDirectory()) out.push(...walk(full + '/', prefix + name + '/'));
    else out.push(prefix + name);
  }
  return out;
}

//: ★★装置文档按发布规则加，不按目录加。规则只有一处实现——
//: `tools/facts-publish.py`（它读每个条目的 `facts/<域>/<id>/rights.json`）。这里
//: 只问它「这一版带哪几台」，不自己判许可：两个发布者各判一遍，某一天它们会给出
//: 不同的答案，而先发现的人是拿到制品的那个。
//: 缺省是**内部版**（2026-09-05 裁定，`FYL-DESIGN-19` A-14）——committed 的这张表
//: 因此是内部版的那一张，与 `facts/` 的缺省生成（`abox-to-facts.py` 也已缺省
//: internal）对得上；公开版构建重跑本生成器（`--flavour public`），树会变脏，而那
//: 正是「这一份不是缺省制品」的信号。★表里只有**路径**，装置字节不入库
//: （`facts/` 整棵是生成物），所以这张表本身不发布任何受限数据。
//: ★★**装置文档不再进这张表**（2026-09-05 用户裁定：页面也走中间层 wasm，撤掉
//: `facts.jsonld`）。此前这里按发布规则逐台把 `facts/device/<id>.jsonld` 加进来，
//: 于是同一批 432 KB 在一个可执行文件里装了两遍：一遍在这张表里（给页面的 HTTP 面），
//: 一遍在 `facts.rs` 里（给命令行）。今天页面经 `fylite_runtime.wasm` 读那一份，
//: 表里因此一条装置也没有——少的正是那多出来的一遍。
//: ★许可闸没有松：进 `facts.rs` 的仍是 `tools/facts-publish.py` 按每台 `rights.json`
//: 选出来的那几台，只是它现在编进 wasm 与 `.so`，不再落成可 fetch 的文件。

//: ★★两份 wasm 必须以**版本化的真名**进表（2026-09-05，`FYL-DESIGN-19` G-8）。
//: 生成器按「目录里现有的名字」写表，于是在一份 wasm 还没版本化的检出上重跑它，
//: 表会从 `.wasm.0.0.1` **静默降回** `.wasm`——站点与可执行文件随之丢掉版本化命名，
//: 而丢了不报错：页面照样能开，只是缓存与版本对不上号，且下一个人看到的是一份
//: 「有人重跑过生成器」的干净 diff。本次实测正是这样撞上的。
//: 版本从 `assets/version.js` 读——与 `tools/build-site.sh` 同一处来源，所以
//: 「表以为的版本」与「站点发的版本」不可能是两个数。
const WASM_STEMS = ['fylite_rs.wasm', 'fylite_kernel_ext.wasm',
                    'fylite_web.wasm', 'fylite_runtime.wasm'];
function checkWasmIsVersioned(list) {
  const vjs = APP + 'assets/version.js';
  if (!existsSync(vjs)) {
    console.error('[embed] 读不出 app/assets/version.js —— 先在内核仓跑构建');
    process.exit(1);
  }
  const m = /kernel:\s*'([^']*)'/.exec(readFileSync(vjs, 'utf8'));
  if (!m || !m[1]) {
    console.error('[embed] app/assets/version.js 里没有 kernel 版本');
    process.exit(1);
  }
  //: ★中间层那一份的版本另有出处（`assets/runtime-version.js`，由本仓
  //: `rust/build.sh` 生成）：它与内核不是同一个版本号，拿内核的版本去找它会
  //: 永远找不到，而“找不到”在这里是拒绝——一条假的红线比没有红线更贵。
  const rv = existsSync(APP + 'assets/runtime-version.js')
    ? (/FyRuntimeVersion\s*=\s*'([^']*)'/.exec(readFileSync(APP + 'assets/runtime-version.js', 'utf8')) || [])[1]
    : null;
  //: ★中间层的两份产物（`fylite_facts.wasm` / `fylite_runtime.wasm`）版本另有出处。
  const want = (s) => (s.startsWith('fylite_web') || s.startsWith('fylite_runtime') ? rv : m[1]);
  //: ★★只核对**这棵树里真有的**那些 stem。可执行文件那一棵**三份 wasm 都不带**
  //: （2026-09-05 两次裁定：装置信息走本进程的 `/api/facts`，算力走 `/api/kernel`
  //: 与链进去的内核静态库；见 `tools/build-app-exe.sh` 里删文件那两段），而
  //: 「不带」与「带了个没版本的」是两回事：前者是设计，后者是那个静默降级的缺陷。
  //: 所以判据是「有这个 stem 的任何名字，就必须是版本化的真名」。
  const present = (s) => list.some((f) => f === `assets/${s}` || f.startsWith(`assets/${s}.`));
  const bad = WASM_STEMS.filter((s) => present(s) && (!want(s) || !list.includes(`assets/${s}.${want(s)}`)));
  if (bad.length) {
    console.error(`[embed] 这些 wasm 不是版本化的真文件：${bad.join(' ')}`);
    console.error(`[embed]   表里要的是 assets/<名>.${m[1]}（tools/soname.sh 的命名）`);
    console.error('[embed]   先在内核仓跑 rust/build.sh --wasm-check，再重跑本生成器');
    console.error('[embed]   ——照写会把版本化命名静默降级（FYL-DESIGN-19 G-8）');
    process.exit(1);
  }
}

const files = [...walk(APP)].sort();
checkWasmIsVersioned(files);
const extOf = (f) => { const l = logicalName(f); return l.slice(l.lastIndexOf('.')); };
const unknown = [...new Set(files.map(extOf))].filter((e) => !(e in MIME));
if (unknown.length) {
  console.error(`[embed] 不认识的扩展名：${unknown.join(' ')}`);
  console.error('[embed] 加进 MIME 表再跑——猜一个 content-type 比报错更糟');
  process.exit(1);
}

const rows = files.map((f) => {
  const ext = extOf(f);
  //: ★★路径过 `$FYLITE_APP_DIR`，不是相对 `.rs` 文件往上数。仓拆开之前
  //: 这里写的是 `../../../../../app/${f}`——从 `rust/fylite_runtime/src/bin/app/` 上溯
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
  console.log(`[embed] -> rust/fylite_runtime/src/bin/app/assets.rs（${files.length} 个文件）`);
}
