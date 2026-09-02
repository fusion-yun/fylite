// mdsip 录制代理 —— 把**真服务器答的字节**存成夹具。
//
//   node tools/mds-record.mjs --server <主机:端口> --out app/tests/fixtures/x.json
//
// ★`--server` **没有默认值**，这是有意的：一个默认指向某家运营方内网
// 地址的工具，既把那个地址发了出去，又会让换一台服务器的人以为不用给。
//   # 另一个终端把宿主指向它印出的端口，跑一遍要覆盖的请求，然后 SIGINT
//
// ## 为什么要有它
//
// 从前的离线夹具是一台**解析式假服务器**（`_mdsip-fake.mjs` 的旧版），它自述
// 「IT IS NOT A SECOND IMPLEMENTATION OF MDSplus —— 它只答 `mdsip.mjs` 拼出来的
// 那些表达式」。于是「Rust 请求面 ⟷ Node 网关」的对拍有一半是**循环**的：表达式
// 拼错了，假服务器照收，两边一起错也能全绿。★录下来的字节没有这个毛病——它钉住的
// 是**真服务器对真请求的回答**，编解码与表达式拼装一起钉。
//
// ## 它录什么
//
// mdsip 的分帧是「头 48 字节，前 4 字节大端写整条消息的长度」，而且**同一条连接上
// 只有一个问题在飞**（客户端自己保证）。所以按顺序配对「客户端消息 -> 服务器消息」
// 就是请求/应答对，不需要理解载荷。
//
//   * 第一条是**登录**（载荷是用户名，不是表达式），单独标 `kind: "login"`；
//     回放时不比对用户名——录的时候是谁不重要，那一格没有认证。
//   * ★★请求头的**第 12 字节是消息序号**，每发一条加一，应答把它原样回声。所以
//     索引前把这一位抹平（`MSGID_OFF`），否则同一个问题问四次就会存成四条不同的
//     记录，而回放时客户端的序号又与录制时对不上，一条也命不中。回放器答的时候
//     再把它改回来访者的那一位——这是**改写一个回声位**，不是编造字节。
//   * ★★mdsip 是**有状态**的：`data(\WMHD)` 只在 `TreeOpen` 之后才有意义，同一句
//     表达式在不同的树/炮下答案不同。所以索引里带上**这条连接当前开着的树与炮**
//     （`ctx`），否则两棵树里的同名节点会互相顶掉。
//   * ★故意去问一个不存在的节点，把 `%TREE-W-NNF` 那条应答也录进来：回放遇到
//     没录过的请求时答它，于是**回放器答的每一个字节都是录来的**，没有一处是编的。
import net from 'node:net';
import fs from 'node:fs';

const flag = (n, d) => { const i = process.argv.indexOf('--' + n); return i > 0 ? process.argv[i + 1] : d; };
const _srv = flag('server');
if (!_srv) { console.error('用法：--server <主机:端口>（无默认值，见抬头）'); process.exit(2); }
const [HOST, PORT] = String(_srv).split(':');
const OUT = flag('out', 'app/tests/fixtures/mdsip-east.json');
const LISTEN = Number(flag('port', 0));

/** 按长度前缀把字节流切成整条消息。 */
function framer(onMessage) {
  let buf = Buffer.alloc(0);
  return (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    for (;;) {
      if (buf.length < 4) return;
      const n = buf.readUInt32BE(0);
      if (!(n >= 48 && n <= 64 * 1024 * 1024)) throw new Error(`长度字段 ${n} 不像一条消息`);
      if (buf.length < n) return;
      onMessage(buf.subarray(0, n));
      buf = buf.subarray(n);
    }
  };
}

/** 消息序号在头里的位置——每条 +1，应答回声。索引前抹平，回放时改回来。 */
export const MSGID_OFF = 12;

/** 抹平序号后的请求字节，用作索引。 */
function maskId(msg) {
  const m = Buffer.from(msg);
  m[MSGID_OFF] = 0;
  return m;
}

const exchanges = [];          // {kind, ctx, expr, req, res} —— req/res 是 base64
const seen = new Map();        // ctx|请求(base64) -> 序号
let logins = 0;

//: ★`--merge`：把已有夹具读进来接着录。一次录制会话只覆盖跑过的那些请求，
//: 而夹具是**几趟**攒起来的（端点扫一趟、浏览器门一趟、整条曲线一趟），没有它
//: 每一趟都会把前一趟盖掉。
if (process.argv.includes('--merge') && fs.existsSync(OUT)) {
  const old = JSON.parse(fs.readFileSync(OUT, 'utf8'));
  for (const e of old.exchanges) {
    const key = e.kind === 'login' ? ' login' : `${e.ctx || ''}|${e.req}`;
    if (seen.has(key)) continue;
    seen.set(key, exchanges.length);
    exchanges.push(e);
    if (e.kind === 'login') logins++;
  }
  process.stderr.write(`并入已有夹具：${exchanges.length} 对\n`);
}

const proxy = net.createServer((client) => {
  const up = net.connect(Number(PORT), HOST);
  const pending = [];          // 已发出、还没收到应答的请求
  let first = true;
  let ctx = null;              // 这条连接当前开着的树与炮

  const fromClient = framer((msg) => {
    const expr = msg.subarray(48).toString('latin1');
    const open = /^TreeOpen\("([^"]+)",(-?\d+)\)$/.exec(expr);
    pending.push({ bytes: Buffer.from(msg), login: first, ctx });
    //: ★开树的那一条自己**不**在新上下文里——它是把上下文换掉的动作。
    if (open) ctx = `${open[1]}:${open[2]}`;
    first = false;
    up.write(msg);
  });
  const fromServer = framer((msg) => {
    const q = pending.shift();
    if (!q) { client.write(msg); return; }          // 不成对：原样转发，不录
    const req = maskId(q.bytes).toString('base64');
    const key = q.login ? ' login' : `${q.ctx || ''}|${req}`;
    if (!seen.has(key)) {
      seen.set(key, exchanges.length);
      exchanges.push({
        kind: q.login ? 'login' : 'request',
        ctx: q.login ? null : q.ctx,
        expr: q.login ? null : q.bytes.subarray(48).toString('latin1'),
        req,
        res: maskId(msg).toString('base64'),
      });
      if (q.login) logins++;
      const what = q.login ? '(login)' : q.bytes.subarray(48).toString('latin1').slice(0, 76);
      process.stderr.write(`  ${String(exchanges.length).padStart(3)}  ${
        String(q.ctx || '-').padEnd(18)} ${what}\n`);
    }
    client.write(msg);
  });

  client.on('data', (c) => { try { fromClient(c); } catch (e) { process.stderr.write(`x ${e.message}\n`); client.destroy(); } });
  up.on('data', (c) => { try { fromServer(c); } catch (e) { process.stderr.write(`x ${e.message}\n`); up.destroy(); } });
  const bye = () => { client.destroy(); up.destroy(); };
  client.on('error', bye);
  up.on('error', bye);
  client.on('close', () => up.destroy());
  up.on('close', () => client.destroy());
});

function save() {
  const doc = {
    note: '真服务器录下的 mdsip 帧；由 tools/mds-record.mjs 生成，勿手改。',
    server: `${HOST}:${PORT}`,
    recordedAt: new Date().toISOString(),
    msgIdOffset: MSGID_OFF,
    logins,
    exchanges,
  };
  fs.mkdirSync(OUT.replace(/\/[^/]*$/, ''), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(doc, null, 1) + '\n');
  const kb = (fs.statSync(OUT).size / 1024).toFixed(0);
  process.stderr.write(`\n${exchanges.length} 对（含 ${logins} 次登录）-> ${OUT}  ${kb} KB\n`);
}

process.on('SIGINT', () => { save(); process.exit(0); });
process.on('SIGTERM', () => { save(); process.exit(0); });

proxy.listen(LISTEN, '127.0.0.1', () => {
  process.stderr.write(`录制中：127.0.0.1:${proxy.address().port} -> ${HOST}:${PORT}\n`);
  process.stdout.write(`${proxy.address().port}\n`);
});
