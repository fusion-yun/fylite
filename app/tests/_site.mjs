// 一个能跑的站点，给浏览器门用：磁盘上的 `app/` + 真正的请求面 + 回放的 mdsip。
//
//   import { fakeSite } from './_site.mjs';
//   const site = await fakeSite();        // -> { url, misses, close }
//
// ## 三层，各是什么
//
//   1. **mdsip**：`_mdsip-replay.mjs` 回放真服务器录下的帧（EAST #137985）。
//   2. **请求面**：`fylite`——**发布出去的那个宿主本身**，不是仿制品。
//      2026-09-01 退役 `app/server/` 之后，`/api/*` 只有这一份实现。
//   3. **静态文件**：这里现起一个只读 HTTP，从**磁盘**上的 `app/` 伺服，
//      `/api/*` 转给第 2 层。
//
// ★为什么第 3 层不直接用 `fylite` 自己的静态面：它伺服的是**编进二进制**的
// 那一份，改了 `app/` 要重新 build 才看得见。门要能在改完页面之后立刻跑。两份是否
// 一致由 `validate-embed.mjs` 单独把关，所以这里从磁盘读不会放过「只改了源树、忘了
// 重嵌」这种错——那本来就是另一道门的事。
//
// ★这一层**没有任何协议代码**：它是静态文件加一个转发，mdsip 只被 `fylite`
// 说。这正是退役 `app/server/` 的意思——一组端点只留一份实现。
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { replayMdsip } from './_mdsip-replay.mjs';

const HERE = new URL('.', import.meta.url).pathname;
const APP = path.resolve(HERE, '..');
export const EXE = process.env.FYLITE_APP
  || path.resolve(HERE, '../../rust/fylite/target/release/fylite');

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.jsonld': 'application/ld+json',
  '.svg': 'image/svg+xml', '.wasm': 'application/wasm', '.png': 'image/png',
  '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.map': 'application/json',
};

/**
 * 起 `fylite`，等它把自己选中的端口印在第一行。
 *
 * ★导出给别的门用：退役 `app/server/` 之后，「起一个带请求面的宿主」只有这一种
 * 做法了。`mdsip` 可以是回放器的端口，也可以是真站点（`host:port`）。
 */
export async function startApp(mdsip) {
  if (!fs.existsSync(EXE)) throw new Error(`找不到 ${EXE}\n  先 bash tools/build-app-exe.sh linux`);
  const proc = spawn(EXE, ['--port', '0', '--no-open',
                           '--mdsip', String(mdsip), '--mds-user',
                           process.env.FYLITE_MDSIP_USER || process.env.USER || 'gate'],
                     { stdio: ['ignore', 'pipe', 'pipe'] });
  const port = await new Promise((resolve, reject) => {
    let buf = '';
    const t = setTimeout(() => reject(new Error('可执行体没在 10 s 内报出地址')), 10000);
    proc.stdout.on('data', (d) => {
      buf += d;
      const m = buf.match(/http:\/\/127\.0\.0\.1:(\d+)/);
      if (m) { clearTimeout(t); resolve(Number(m[1])); }
    });
    proc.on('exit', (c) => { clearTimeout(t); reject(new Error(`可执行体退出，码 ${c}`)); });
  });
  return { proc, port, url: `http://127.0.0.1:${port}/`, close: () => proc.kill() };
}

export async function fakeSite() {
  //: ★录制通道：`FYLITE_MDSIP_LIVE=host:port` 时不回放，直接把请求面指到那里。
  //: 夹具就是这么来的——`tools/mds-record.mjs` 架在中间，把这一趟门跑出来的
  //: 请求与真服务器的应答录下来。**平时它是空的，门跑的是回放。**
  const live = process.env.FYLITE_MDSIP_LIVE;
  const mds = live
    ? { port: Number(live.split(':')[1]), misses: [], seen: [], close: async () => {} }
    : await replayMdsip();
  if (live && !/^127\.0\.0\.1:\d+$/.test(live))
    throw new Error(`FYLITE_MDSIP_LIVE 只接 127.0.0.1:PORT（录制代理），拿到 ${live}`);
  const exe = await startApp(`127.0.0.1:${mds.port}`);

  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname.startsWith('/api/')) {
      //: 原样转给请求面：查询串、方法、状态码、正文都不加工——门要看见的是
      //: **那个宿主**答了什么。
      const up = http.request(
        { host: '127.0.0.1', port: exe.port, path: url.pathname + url.search, method: req.method,
          //: ★不复用连接：请求面是一问一答、答完就关（`Connection: close`）。
          //: 默认 agent 会 keep-alive，第二个请求发到一条已经被对面关掉的
          //: socket 上就悬在那里——页面停在「正在检查网关…」，门只报 goto 超时。
          agent: false },
        (r) => {
          //: ★逐跳首部要摘掉再转：请求面是 `Connection: close` 的一问一答，
          //: 把这一句原样抄给浏览器，浏览器就在一条它以为还活着的连接上等一个
          //: 永远不来的结束——页面停在「正在检查网关…」，而门只会说 goto 超时。
          const h = { ...r.headers };
          for (const k of ['connection', 'keep-alive', 'transfer-encoding', 'upgrade']) delete h[k];
          res.writeHead(r.statusCode, h);
          r.pipe(res);
        });
      up.on('error', (e) => { res.writeHead(502, { 'content-type': 'text/plain' }); res.end(String(e.message)); });
      req.pipe(up);
      return;
    }
    let file = path.join(APP, decodeURIComponent(url.pathname));
    if (url.pathname.split('/').includes('..')) { res.writeHead(400).end(); return; }
    try {
      let st = fs.statSync(file);
      if (st.isDirectory()) { file = path.join(file, 'index.html'); st = fs.statSync(file); }
      res.writeHead(200, {
        'content-type': TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream',
        'content-length': st.size,
        'cache-control': 'no-store',
      });
      if (req.method === 'HEAD') return res.end();
      fs.createReadStream(file).pipe(res);
    } catch {
      res.writeHead(404, { 'content-type': 'text/plain' });
      res.end('404 ' + url.pathname);
    }
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));

  return {
    url: `http://127.0.0.1:${server.address().port}/`,
    misses: mds.misses,
    seen: mds.seen,
    async close() {
      await new Promise((done) => server.close(done));
      exe.proc.kill();
      await mds.close();
    },
  };
}
