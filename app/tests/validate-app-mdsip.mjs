// 门：**发布出去的那个宿主，对着真服务器录下来的帧**。
//
//   node app/tests/validate-app-mdsip.mjs [--exe <fylite-app>]
//
// ★这道门从前叫「两个宿主，一组端点，同一个答案」：仓里的 Node 网关
// （`app/server/gateway.mjs` + `mdsip.mjs`）与单文件查看器自己带的 Rust 请求面
// 逐字段对拍。2026-09-01 网关退役，`/api/*` 只剩 `rust/fylite/src/bin/app/api.rs`
// 这一份实现，这门的判据也就换了根：
//
//   * **从前**：两个实现互为判据。问题出在它们**共用一台按其中一方的读法写的假
//     服务器**——表达式拼错了假服务器照收，两边一起错也全绿。编解码那一半是真
//     交叉检验，表达式拼装那一半是循环的。
//   * **现在**：判据是 `fixtures/mdsip-east.json` —— `tools/mds-record.mjs` 架在
//     客户端与 EAST 之间录下的**请求→应答**对。宿主拼错一个字就命不中任何一条
//     记录，而**命不中是响的**（`misses`，下面是断言不是日志）。
//   * **另一个实现仍然在**，只是换了位置：`app/tests/validate-jmds.mjs` 拿
//     `tools/jmds` 那个**纯 Java 客户端**与这个宿主逐字段比、两条数组逐位比。
//     它要一台真服务器，所以是活跑那一档——一个独立实现的对照值得单独一趟。
//
// ★它不需要网络：`_mdsip-replay.mjs` 回放那些帧，宿主指向它。于是这门比的是
// **协议实现**，不是某一天某台机器上的数据。
//
// ★★它钉住三条本来只有真服务器才会暴露的解码规则——三条都是 2026-08-31 把 Rust
// 客户端第一次指向 EAST 时抓出来的：
//   * 登录应答是 `dtype = 0` + 零字节：空载荷必须能解码，否则握手就完不成；
//   * `getnci(...,"TIME_INSERTED")` 是 **u64**，缺这个 dtype 会让每个节点都报
//     「从未写入」——那看起来像个答案；
//   * 定宽文本表的**填充是分隔符**，在解码处 trim 掉就再也切不开名字。
// 录下来的帧三条都带着，所以这门看得见它们。

import { existsSync } from 'node:fs';
import { startApp, EXE } from './_site.mjs';
import { replayMdsip, haveFixture, FIXTURE_ABSENT } from './_mdsip-replay.mjs';

const flag = (n) => { const i = process.argv.indexOf('--' + n); return i > 0 ? process.argv[i + 1] : undefined; };
const exePath = flag('exe') || EXE;

let bad = 0;
const say = (ok, what, detail) => {
  console.log(`${ok ? '  ok  ' : '  ✗   '}${what}${detail ? '  ' + detail : ''}`);
  if (!ok) bad++;
};

if (!existsSync(exePath)) {
  console.log(`跳过：找不到 ${exePath}\n  先 bash tools/build-app-exe.sh linux，或 --exe <路径>`);
  process.exit(0);
}

//: ★同一姿态：判据不在手里就**跳过**，不降格成一台假服务器。
if (!haveFixture()) { console.log('跳过：' + FIXTURE_ABSENT); process.exit(0); }

const mds = await replayMdsip();
const app = await startApp(`127.0.0.1:${mds.port}`);

const get = async (path) => {
  const r = await fetch(app.url.replace(/\/$/, '') + path);
  return { status: r.status, body: await r.json() };
};

const SHOT = 137985;
//: 夹具里有的一个 1-D 信号；`\\TOP` 之外的节点也要读得动
const N = encodeURIComponent('\\WMHD');
//: 每个端点答多少个键是钉住的，`server` 那一格也算在内。
const CASES = [
  ['/api/measurements?shot=' + SHOT + '&time=4.0', 16],
  ['/api/tree?tree=efit_east&shot=' + SHOT + '&path=' + encodeURIComponent('\\TOP'), 5],
  ['/api/node?tree=efit_east&shot=' + SHOT + '&node=' + N, 9],
  ['/api/signal?tree=efit_east&shot=' + SHOT + '&node=' + N + '&points=8', 15],
];

try {
  const h = await get('/api/health');
  say(h.status === 200 && h.body.ok === true, '宿主的 /api/health 说接上了',
      JSON.stringify(h.body.mdsip));

  for (const [path, keys] of CASES) {
    const a = await get(path);
    //: ★键数是钉住的：一个端点悄悄少答一个字段，页面上表现为某一格空着，
    //: 而「200 且是 JSON」这种检查看不见它。
    const got = a.status === 200 ? Object.keys(a.body).length : 0;
    say(a.status === 200 && got === keys, `${path.split('?')[0]} 答了 ${keys} 个键`,
        a.status === 200 ? Object.keys(a.body).join(' ') : `HTTP ${a.status}`);
  }

  //: ★★★这三条是上面注释里那三处缺陷的直接判据，写成断言而不是靠别的检查
  //: 顺带覆盖：一条规则被别的检查捎带过，改坏时报出来的是别的东西。
  const node = (await get(CASES[2][0])).body;
  say(typeof node.inserted === 'number' && node.inserted > 0,
      'TIME_INSERTED 读得出来（u64 dtype）', String(node.inserted));
  say(/^\d{4}-\d\d-\d\dT/.test(String(node.insertedIso)),
      'ISO 时间戳是个时间戳', String(node.insertedIso));
  const tree = (await get(CASES[1][0])).body;
  say(tree.nodes.length > 1 && tree.nodes.every((n) => n.name && !/\s/.test(n.name)),
      '定宽文本表切成了单个名字（填充是分隔符）',
      tree.nodes.slice(0, 3).map((n) => n.name).join(','));

  //: ★★命不中＝宿主问了夹具里没有的问题。要么它改了拼法，要么用例改了参数；
  //: 两种都得有人看一眼，所以它是一条断言。重录见 `tools/mds-record.mjs`。
  say(mds.misses.length === 0,
      `回放全部命中（${mds.seen.length} 次问答）`,
      mds.misses.length ? mds.misses.slice(0, 4).map((m) => `${m.ctx || '-'} ${m.expr}`).join(' · ') : '');
} finally {
  app.close();
  await mds.close();
}

console.log(bad ? `\nFAIL (${bad})` : '\nPASS');
process.exit(bad ? 1 : 0);
