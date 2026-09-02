// 门：`app/guide/` 必须与 `docs/guide/` 的公开子集（`public.yml`）同步，
// 且指南页只引站点已有的资源。
//
// ★为什么要这条门：指南是**生成物且入库**（与三张说明页、三个 .wasm 同一惯例），
// 而发布流水线只做拷贝——所以「源改了但没重跑生成器」不会在发布时被发现，
// 只会安静地发布一份过期的指南。这条门把它变成一次失败。
import { execFileSync } from 'node:child_process';
import { readFileSync, readdirSync } from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../../';
let bad = 0;
const fail = (m) => { console.error('  ✗ ' + m); bad++; };

// 1. 与源同步（生成器自带 --check）
try {
  const out = execFileSync('bash', [ROOT + 'tools/build-guide.sh', '--check'],
                           { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  console.log('  ✓ ' + out.trim().split('\n').pop());
} catch (e) {
  fail('app/guide/ 与 docs/guide/ 的公开子集不同步：' + String(e.stdout || e.stderr || e).trim());
}

// 2. 引用的样式表必须真的在 app/ 下 —— 一个 404 的样式表在本机上看不出来，
//    因为浏览器只是退回无样式，页面照旧显示
const pages = readdirSync(ROOT + 'app/guide').filter((f) => f.endsWith('.html'));
if (!pages.length) fail('app/guide/ 下没有页面');
for (const f of pages) {
  const html = readFileSync(ROOT + 'app/guide/' + f, 'utf8');
  for (const m of html.matchAll(/(?:href|src)="((?:\.\.\/)?assets\/[^"]+)"/g)) {
    const rel = m[1].startsWith('../') ? m[1].slice(3) : 'guide/' + m[1];
    try { readFileSync(ROOT + 'app/' + rel); } catch { fail(`${f} 指向不存在的 ${m[1]}`); }
  }
  //: 指南是发布物，不许引仓内私有路径
  if (/docs\/(design|report|reference)\//.test(html)) fail(`${f} 引了仓内私有文档路径`);
}
if (!bad) console.log(`  ✓ ${pages.length} 页的资源引用都成立`);

process.exit(bad ? 1 : 0);
