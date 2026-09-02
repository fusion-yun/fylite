// 门：桌面查看器内嵌的资源表必须与 `app/` 同步。
//
// ★为什么要这条门：表是生成物（`tools/make-app-embed.mjs`），而漏重跑生成器的
// 后果不是编译失败，是**运行时 404**——一个只有拿到 .exe 的人才会遇到的缺失。
// 这条把它提前到本机的一次失败。
import { execFileSync } from 'node:child_process';

const ROOT = new URL('../../', import.meta.url).pathname;
try {
  const out = execFileSync('node', [ROOT + 'tools/make-app-embed.mjs', '--check'],
                           { encoding: 'utf8' });
  console.log('  ✓ ' + out.trim());
  console.log('\nPASS');
} catch (e) {
  console.error((e.stdout || '') + (e.stderr || ''));
  console.error('FAIL');
  process.exit(1);
}
