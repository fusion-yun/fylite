// 一棵**装好的** `app/` 树里，哪些东西只属于内部版——以及怎么把它们拿掉。
//
//     node tools/app-flavour.mjs --strip <dir>            # 内部版专有 -> 删掉
//     node tools/app-flavour.mjs --check public   <dir>   # 断言它们不在了
//     node tools/app-flavour.mjs --check internal <dir>   # 断言它们还在
//
// ★★为什么是一个独立的工具，而不是 `build-site.sh` 里的一行 `sed`。
//
// 发布者有两个（站点 `tools/build-site.sh`、单可执行文件 `tools/build-app-exe.sh`），
// 而后者的内容**正是**前者装出来的那一棵树，所以规则写在这里、由站点脚本调用一次，
// 两个制品按构造同规则。这与装置数据那一条的分工完全同形：许可判据只有一处实现
// （`tools/facts-publish.py`），两个发布者都不自己判。
//
// ★★被删掉的是**警示带的后半句**，不是整条带子（2026-09-05 用户裁定）。带子上有两句：
//
//   `chrome.alpha`         「alpha 版，用于概念验证」—— 说这份东西成熟到什么程度，
//                          每一版都成立，公开版也成立，所以它留下；
//   `chrome.internal_only` 「仅限内部测试，请勿公开传播！」—— 说这一份能给谁看，
//                          只有内部版成立，所以公开版里它必须**不存在**。
//
// 「不存在」是照字面的：不是 `display:none`，不是注释掉。带子上的那个 `<span>` 整个
// 删掉，**连同两份语料里的那一条**——留着词条等于把这句话仍然发出去，只是没有元素去
// 显示它，而一个打开 `assets/lang-zh.js` 的人读到的是同一句话。
//
// ★★`--strip` 一条都没删到 = 失败，不是「无事可做」。这个工具认的是一个**形状**
// （`<span class="warn-io">` 与语料里那一行）；形状哪天变了而工具没跟上，静默的
// 后果正是一个带着「仅限内部测试」的公开站点。删到零条时红着退出，是把这种沉默
// 换成一次构建失败。

import { readdirSync, statSync, readFileSync, writeFileSync } from 'node:fs';
import { join, extname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));

//: ★★**判据不在这个文件里**（2026-09-08）。哪几句话、哪一句只属于内部版，写在
//: `python/fylite/_notice.json` —— 三个界面（浏览器 / `fy` / Python）共用的那一份。
//: 这里读它，不抄它：抄一份进来就是一份可以各自过期的副本，而它过期的样子正是
//: 一个「删不到东西」的公开版构建。
const SPEC = JSON.parse(readFileSync(
  join(HERE, '..', 'python', 'fylite', '_notice.json'), 'utf8'));

/** 只属于内部版的那几条：`flavours` 里没有 `public` 的。 */
const INTERNAL_ONLY = SPEC.notices.filter((n) => !n.flavours.includes('public'));
if (!INTERNAL_ONLY.length) {
  console.error('[flavour] _notice.json 里没有任何一条只属于内部版 ——'
                + ' 公开版与内部版说的话一样，这个工具就没有可做的事了');
  process.exit(2);
}

/** 带子上那个 `<span>`（两种拼法：生成的散文页无 `data-i18n`，动态页有）。 */
const spanOf = (n) => new RegExp(`<span class="${n.span_class}"[^>]*>[\\s\\S]*?<\\/span>`, 'g');
/** 语料里的一整行词条：`  'chrome.internal_only': '…',` */
const entryOf = (n) => new RegExp(`^[ \\t]*'${n.i18n_key.replace('.', '\\.')}':[^\\n]*\\n`, 'gm');

/** 那几句话本身，两种语言，取自同一份 JSON。 */
function sentences() {
  return INTERNAL_ONLY.flatMap((n) => [n.zh, n.en]);
}

function walk(dir, exts) {
  const out = [];
  for (const name of readdirSync(dir).sort()) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) out.push(...walk(full, exts));
    else if (exts.has(extname(name))) out.push(full);
  }
  return out;
}

const TEXT = new Set(['.html', '.js', '.mjs', '.json']);

function strip(dir) {
  let spans = 0, entries = 0, files = 0;
  for (const f of walk(dir, TEXT)) {
    const src = readFileSync(f, 'utf8');
    let s = src;
    for (const n of INTERNAL_ONLY) {
      s = s.replace(spanOf(n), () => { spans++; return ''; });
      s = s.replace(entryOf(n), () => { entries++; return ''; });
    }
    if (s !== src) { writeFileSync(f, s); files++; }
  }
  if (spans === 0 || entries === 0) {
    console.error(`[flavour] --strip 删到 ${spans} 个 span、${entries} 条词条 ——`
                  + ' 至少有一样是零，说明标记的形状变了而这个工具没跟上。');
    console.error('[flavour]   一个「删不到东西」的公开版构建正是要防的那件事，'
                  + '所以这里失败而不是通过。');
    process.exit(1);
  }
  console.log(`[flavour] 公开版：删掉 ${spans} 个内部提示 span、${entries} 条语料词条`
              + `（共 ${files} 个文件）`);
}

function check(flavour, dir) {
  const said = sentences();
  const bad = [];
  const seen = { span: 0, key: 0, text: 0 };
  for (const f of walk(dir, TEXT)) {
    const s = readFileSync(f, 'utf8');
    const hit = [];
    for (const n of INTERNAL_ONLY) {
      if (s.includes(`class="${n.span_class}"`)) { hit.push(n.span_class); seen.span++; }
      if (s.includes(n.i18n_key)) { hit.push(n.i18n_key); seen.key++; }
    }
    for (const t of said) if (s.includes(t)) { hit.push('「' + t + '」'); seen.text++; }
    if (hit.length && flavour === 'public') {
      bad.push(`${relative(dir, f)}：${hit.join('、')}`);
    }
  }
  if (flavour === 'public') {
    if (bad.length) {
      console.error('[flavour] 公开版里还留着内部提示：');
      for (const b of bad.slice(0, 12)) console.error('  ' + b);
      if (bad.length > 12) console.error(`  …… 另有 ${bad.length - 12} 处`);
      process.exit(1);
    }
    console.log('[flavour] 公开版：内部提示词一处不剩（元素、键、两种语言的原句）');
  } else {
    //: ★内部版反着查：**带**着它才对。一个把提示悄悄漏掉的内部版不会有人抱怨——
    //: 它看起来只是干净——所以这一头也要有断言。
    if (seen.span === 0 || seen.key === 0 || seen.text === 0) {
      console.error(`[flavour] 内部版里找不到内部提示（span ${seen.span} · 键 ${seen.key}`
                    + ` · 原句 ${seen.text}）—— 这一版应当带着它`);
      process.exit(1);
    }
    console.log(`[flavour] 内部版：内部提示在 ${seen.span} 个页面上`);
  }
}

const [mode, ...rest] = process.argv.slice(2);
if (mode === '--strip' && rest.length === 1) strip(rest[0]);
else if (mode === '--check' && rest.length === 2
         && (rest[0] === 'public' || rest[0] === 'internal')) check(rest[0], rest[1]);
else {
  console.error('用法：node tools/app-flavour.mjs --strip <dir>');
  console.error('      node tools/app-flavour.mjs --check public|internal <dir>');
  process.exit(2);
}
