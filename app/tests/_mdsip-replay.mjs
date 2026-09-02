// 回放一台 mdsip 服务器 —— **答的每一个字节都是真服务器录下来的**。
//
//   import { replayMdsip } from './_mdsip-replay.mjs';
//   const mds = await replayMdsip();     // -> { port, close, misses, seen }
//
// ## 它取代了什么，为什么
//
// 从前这里是一台**解析式假服务器**（`_mdsip-fake.mjs`）：它读懂表达式，按解析式
// 波形现算一个答案。它自己的文件头写着「IT IS NOT A SECOND IMPLEMENTATION OF
// MDSplus —— 它只答 `mdsip.mjs` 拼出来的那些表达式」。这句话正是它的天花板：
//
//   * 客户端**把问题拼错**时，假服务器照收照答，门全绿——它的判据是「和写这台假
//     服务器的人当初的读法一致」，不是「和真服务器一致」；
//   * 于是「两个宿主逐字段对拍」只有**编解码**那一半是真交叉检验，**表达式拼装**
//     那一半是循环的：两个实现一起错，没有东西看得见。
//
// 录下来的帧没有这个毛病。夹具 `fixtures/mdsip-east.json` 是
// `tools/mds-record.mjs` 架在客户端与 EAST 之间录的**请求→应答**对，所以这台回放
// 器钉住的是**真服务器对真请求的回答**：问题拼错一个字，就命不中任何一条记录，
// 而**命不中是响的**（见 `misses`）。
//
// ## 两处刻意的改写，其余逐字回放
//
//   * ★**消息序号**（头的第 12 字节，每发一条 +1、应答原样回声）：索引时抹平，
//     回放时改成来访者的那一位。不改的话客户端会看见别人的序号。
//   * ★**登录**：第一条消息的载荷是用户名，回放不比对——mdsip 不做认证，录的时候
//     是谁不重要。
//
// 除这两处外没有任何字节是构造的：命不中时答的也是录来的那条 `%TREE-W-NNF`
// （夹具里特意问了一个不存在的节点），而不是现编一个错误帧。
//
// ## 一处例外：窗口切片是**本地切**的
//
// ★浏览器门里有「拖着放大」那一节，取的窗口是**像素算出来的**——同一道门跑两趟，
// 落在 `data(\PCRL01)[1701:4429:6]` 这样的下标上会差几个样点。要把每一种窗口都录
// 下来是不可能的。所以夹具里按每路信号存**一条底稿**（从第 0 点起、覆盖整条的一次
// 抽稀，**每路不超过 2000 点**），窗口切片由这里从底稿上取。
//
//   * **样点成对地都是真的**：`data` 与 `dim_of` 用同一套下标去取，所以画出来的每
//     一个 (t, y) 都是真服务器给过的那一对，不是算出来的。
//   * ★底稿是抽稀过的（`\VP1` 整条 115 万点，存不下也不必存），所以请求的下标按
//     **最近邻**落到底稿上：窗口的**点数与步长**与请求一致，落点可能差几个样点。
//     门看的是点数、步长、图注与单位，不是某一个样点的身份。底稿步长为 1 时
//     （短信号）这一层是恒等的，落点也精确。
//   * ★要的点数**多于底稿在这个窗口里有的**（放大到很窄的窗口时客户端会请求
//     整段原始样点），答回去的就**只是窗口里那些真样点**——比请求的少。绝不
//     重复样点去凑数：凑出来的是一段谁也看不出来的假曲线，而少几个点是看得见的。
//   * 没有底稿时同样不猜：`misses` 里看得见。
import net from 'node:net';
import fs from 'node:fs';

//: ★★夹具**不在本仓**。它是对 EAST 内网服务器录下的真会话（#137985 的原始样点
//: 与树的节点名拓扑），2026-09-02 迁到私有的 `fydata`
//: （`corpus/experiment/east/mdsip-137985.json`）——本仓是公开仓，不再分发它。
//: 缺省仍看**原来那个位置**，所以持有 fydata 的人把文件拷回去就什么都不用改；
//: 拷不动的，用 `FYLITE_MDS_FIXTURE` 指过去。两条都落空时，用它的门自报跳过，
//: **不假造一台服务器**——那正是这个文件头上半段说过的、被取代掉的东西。
const FIXTURE = process.env.FYLITE_MDS_FIXTURE
  || new URL('./fixtures/mdsip-east.json', import.meta.url).pathname;
const HEADER_LEN = 48;

/** 夹具在哪（给门在跳过消息里说得出位置）。 */
export function fixturePath() { return FIXTURE; }

/** 夹具在不在。门据此**跳过**——回放器没有底稿时不猜。 */
export function haveFixture() { return fs.existsSync(FIXTURE); }

/** 一句话说清缺的是什么、从哪拿。门与 `loadFixture` 用同一句。 */
export const FIXTURE_ABSENT =
  `没有 mdsip 录音夹具：${FIXTURE}\n`
  + '  它是 EAST 内网的实验数据，随 fydata（私有）走，不在本公开仓里。\n'
  + '  有 fydata 的话：cp <fydata>/corpus/experiment/east/mdsip-137985.json '
  + 'app/tests/fixtures/mdsip-east.json\n'
  + '  或：FYLITE_MDS_FIXTURE=<fydata>/corpus/experiment/east/mdsip-137985.json';

/** 抹平序号；索引与回放两侧用同一个函数，才谈得上对得上。 */
function maskId(msg, off) {
  const m = Buffer.from(msg);
  m[off] = 0;
  return m;
}

/** 按长度前缀切帧——与 `tools/mds-record.mjs` 同一套。 */
function framer(onMessage) {
  let buf = Buffer.alloc(0);
  return (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    for (;;) {
      if (buf.length < 4) return;
      const n = buf.readUInt32BE(0);
      if (!(n >= HEADER_LEN && n <= 64 * 1024 * 1024)) throw new Error(`长度字段 ${n} 不像一条消息`);
      if (buf.length < n) return;
      onMessage(buf.subarray(0, n));
      buf = buf.subarray(n);
    }
  };
}

/** `data(\X)[a:b:c]` / `dim_of(\X)[a:b:c]` —— 切片请求的形状。 */
const SLICE = /^(data|dim_of)\((.+)\)\[(\d+):(\d+):(\d+)\]$/;

/**
 * 从整条曲线的应答帧上切一段出来。
 *
 * 帧的布局（与 `mdsip.rs` 一致）：前 4 字节整条长度、8..10 元素字节数、
 * 13 dtype、15 维数、16+4i 各维长度、48 起是载荷。一维数组的载荷就是
 * `dims[0] × elemLen` 字节，所以按下标切就是按 `elemLen` 步长搬字节。
 */
function sliceFrame(draft, want) {
  const { frame, step: step0 } = draft;
  const { a, b, step } = want;
  const elemLen = frame.readUInt16BE(8);
  const ndims = frame[15];
  const have = frame.readUInt32BE(16);          // 底稿里的点数
  if (ndims !== 1 || elemLen === 0 || 48 + have * elemLen !== frame.length) return null;
  //: 底稿覆盖到原始下标 (have-1)*step0；请求超出的部分按原始长度自己截断。
  const last = Math.min(b, (have - 1) * step0);
  const idx = [];
  for (let i = a; i <= last; i += step) {
    //: ★最近邻：底稿第 k 点是原始第 k*step0 点（见文件头）。
    const k = Math.min(have - 1, Math.round(i / step0));
    //: 同一个底稿点被要到两次（窗口比底稿细）时只给一次——见文件头。
    if (idx.length && idx[idx.length - 1] === k) continue;
    idx.push(k);
  }
  if (!idx.length) return null;
  const out = Buffer.alloc(48 + idx.length * elemLen);
  frame.copy(out, 0, 0, 48);
  out.writeUInt32BE(out.length, 0);
  out.writeUInt32BE(idx.length, 16);
  idx.forEach((src, k) => frame.copy(out, 48 + k * elemLen, 48 + src * elemLen, 48 + (src + 1) * elemLen));
  return out;
}

export function loadFixture(path = FIXTURE) {
  if (!fs.existsSync(path)) throw new Error(FIXTURE_ABSENT);
  const doc = JSON.parse(fs.readFileSync(path, 'utf8'));
  const idOff = doc.msgIdOffset;
  if (typeof idOff !== 'number') throw new Error(`${path} 里没有 msgIdOffset —— 夹具是旧格式`);
  const byKey = new Map();
  const whole = new Map();     // `ctx|func(node)` -> {frame, step} 底稿
  let login = null;
  let notFound = null;
  for (const e of doc.exchanges) {
    if (e.kind === 'login') { login = Buffer.from(e.res, 'base64'); continue; }
    byKey.set(`${e.ctx || ''}|${e.req}`, Buffer.from(e.res, 'base64'));
    const m = SLICE.exec(e.expr || '');
    //: 底稿＝从第 0 点起的一次覆盖整条的抽稀。同一路留点数最多的那一条。
    if (m && m[3] === '0') {
      const k = `${e.ctx || ''}|${m[1]}(${m[2]})`;
      const frame = Buffer.from(e.res, 'base64');
      const prev = whole.get(k);
      if (!prev || frame.readUInt32BE(16) > prev.frame.readUInt32BE(16))
        whole.set(k, { frame, step: Number(m[5]) });
    }
    //: 任意一条「节点不存在」的应答都行，取第一条：它只在命不中时用。
    if (notFound === null && /NO_SUCH_NODE/.test(e.expr || '')) notFound = Buffer.from(e.res, 'base64');
  }
  if (!login) throw new Error(`${path} 里没有登录应答`);
  if (!notFound) throw new Error(`${path} 里没有录到「节点不存在」的应答 —— 命不中时无字节可答`);
  return { doc, idOff, byKey, whole, login, notFound };
}

/**
 * 起一台回放服务器。`misses` 是命不中的请求（表达式 + 当时开着的树），门可以
 * 断言它为空——**一条命不中就是「客户端问了夹具里没有的问题」**，那正是要看见的事。
 */
export async function replayMdsip(path = FIXTURE) {
  const { doc, idOff, byKey, whole, login, notFound } = loadFixture(path);
  const misses = [];
  const seen = [];

  const server = net.createServer((sock) => {
    let first = true;
    let ctx = null;
    const onMessage = (msg) => {
      const id = msg[idOff];
      const reply = (bytes) => {
        const out = Buffer.from(bytes);
        out[idOff] = id;                       // 把序号回声给来访者
        sock.write(out);
      };
      if (first) { first = false; reply(login); return; }
      const expr = msg.subarray(HEADER_LEN).toString('latin1');
      const key = `${ctx || ''}|${maskId(msg, idOff).toString('base64')}`;
      let hit = byKey.get(key);
      //: 没有逐字命中时，看看能不能从整条曲线上切出来（见文件头）。
      let sliced = false;
      if (!hit) {
        const m = SLICE.exec(expr);
        const draft = m && whole.get(`${ctx || ''}|${m[1]}(${m[2]})`);
        const cut = draft && sliceFrame(draft,
          { a: Number(m[3]), b: Number(m[4]), step: Number(m[5]) });
        if (cut) { hit = cut; sliced = true; }
      }
      const open = /^TreeOpen\("([^"]+)",(-?\d+)\)$/.exec(expr);
      seen.push({ ctx, expr, hit: Boolean(hit), sliced });
      if (!hit) misses.push({ ctx, expr });
      if (open) ctx = `${open[1]}:${open[2]}`;
      reply(hit || notFound);
    };
    const feed = framer(onMessage);
    sock.on('data', (c) => { try { feed(c); } catch { sock.destroy(); } });
    sock.on('error', () => sock.destroy());
  });

  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  return {
    port: server.address().port,
    server: doc.server,
    recordedAt: doc.recordedAt,
    misses,
    seen,
    close: () => new Promise((r) => server.close(r)),
  };
}
