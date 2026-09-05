// 两条算力路，同一批数 —— `/api/kernel` 与 wasm 必须**逐位相同**。
//
// ★★2026-09-05 用户裁定：「webui 中 fylite_rs / fylite_kernel_ext wasm 功能由 api
// 端提供，只静态网页走 wasm」。于是同一份物理有两种到达方式，而**两种到达方式就是
// 两个可能不一致的答案**——除非有人比。这里就是比的地方。
//
// 判据：**逐位相同为主，超越函数上放到 1 e-14 相对差**。
//
// ★★这条界线是实测定的，不是拍的（2026-09-05，本闸子第一次跑出来的数）：
//
//   逐位相同   ellipke（10 个数）· trappedFractionEps · interp · quadrature ·
//              adasSpecies · adasId + adasCooling —— 纯算术与查表
//   末位不同   spitzerEta   1/3 个点，相对差 2.2e-16（≈1 ULP）
//              millerBoundary 2/66 个点，1.9e-16
//              dtReactivity 1/3 个点，1.4e-15 —— Bosch–Hale 式里有 exp，
//                            指数把末位差放大了几个 ULP
//
// 两条路后面是同一份 Rust 源码，但编到两个目标：原生 x86-64 链 glibc 的 libm，
// wasm32 用 Rust 自带的那份。〔判读〕差异来自两个 libm 实现对同一个超越函数的末位
// 取舍不同（判据：不含超越函数的入口逐位相同，含 exp/pow/ln 的不同），不是桥搬错了
// 参数——搬错参数的表现是**量级级别**的错（一个长度短一格、一个入参当成了出参），
// 那种错这条界线照样拦得住。
//
// 〔判读〕差异来自两个 libm 实现对同一个超越函数的末位取舍不同，不是桥搬错了参数：
// 搬错参数的表现是**量级级别**的错（一个长度短一格、一个入参当成了出参），而不是
// 末位。所以这里两条都查：逐位不同就报出来并数出来，超过 1 e-15 才判不通过。
//
// ★这也意味着**两条路的结果不能互相续算**——而那件事已经由内核身份挡住了：
// 两条路报的 sha256 本来就不同（一份是 `.wasm` 的，一份是链进桌面进程的那份归档的），
// `checkpoint.js` 按它拒绝续上不是自己写的状态。
//
//   node app/tests/validate-kernel-api.mjs
//
// ★这条闸子要一个**跑起来的 `fy app`**（自带算力的那种构建）。没有就跳过并说明
// 为什么——那是「这台机器上没建过」，不是「不通过」。
//
// ★★同步传输在浏览器里是 XHR（`kernelapi.js` 抬头写了为什么必须同步）。node 没有
// 同步 HTTP，所以这里用 `curl` 现起一个进程顶上——**那是本闸子的宿主细节**，不是被
// 测代码的：被测的是 `kernelapi.js` 怎么编排参数，不是它用哪个类发请求。

import { readFileSync, existsSync } from 'node:fs';
import { execFileSync, spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import vm from 'node:vm';

const HERE = new URL('.', import.meta.url).pathname;
const SITE = HERE + '../assets/';
const ROOT = HERE + '../../';
const EXE = ROOT + 'rust/fylite_runtime/target/release/fy';
const PORT = 8974 + (process.pid % 500);

if (!existsSync(EXE)) {
  console.log(`跳过：没有 ${EXE} —— 先跑 bash rust/build.sh --exe`);
  process.exit(0);
}
if (!existsSync(SITE + 'kernel-abi.js')) {
  console.log('跳过：没有 assets/kernel-abi.js —— 它由内核仓的 rust/build.sh 生成');
  process.exit(0);
}

// --- 起一个自带算力的 fy app ------------------------------------------------
const app = spawn(EXE, ['app', '--port', String(PORT), '--no-open',
                        '--app-dir', ROOT + 'app'],
                  { stdio: ['ignore', 'pipe', 'pipe'] });
const BASE = `http://127.0.0.1:${PORT}/`;
process.on('exit', () => app.kill());

function curl(args, input) {
  //: ★`input` 必须真的喂进 stdin：`--data-binary @-` 而不给 stdin，curl 送的是
  //: **空正文**，而服务端报的是「JSON 读不动」——一句与桥毫无关系的话。
  return execFileSync('curl', ['-s', '--noproxy', '*', ...args],
                      { encoding: 'utf8', input: input === undefined ? '' : input,
                        maxBuffer: 256 * 1024 * 1024 });
}

let health = null;
for (let i = 0; i < 50; i++) {
  try {
    health = JSON.parse(curl([BASE + 'api/health']));
    break;
  } catch (e) { execFileSync('sleep', ['0.1']); }
}
if (!health) { console.error('fy app 没起来'); process.exit(1); }
if (!health.kernel || !health.kernel.linked) {
  console.log('跳过：这个 fy 没有链内核（' + JSON.stringify(health.kernel) + '）');
  console.log('  要链：在内核仓跑 rust/build.sh（它装 rust/kernel-lib/libfylite_kernel_static.a），再重建 fy');
  process.exit(0);
}
console.log(`算力：abi ${health.kernel.abi}，${health.kernel.symbols} 个符号，`
            + `内核 ${health.kernel.version} ${String(health.kernel.sha256).slice(0, 12)}…`);

// --- 宿主面：页面在浏览器里有的那几样 ---------------------------------------
globalThis.self = globalThis;
globalThis.location = { hostname: '127.0.0.1', href: BASE, search: '' };
//: ★i18n 要一点 DOM。补到「够它跑完」为止，不多补：一个笼统的 `document = {}`
//: 会让漏掉的调用以 `undefined` 悄悄通过，而这条闸子要的是真答案。
globalThis.document = {
  currentScript: { src: BASE + 'assets/kernelapi.js' },
  documentElement: { lang: 'zh', setAttribute() {}, getAttribute: () => 'zh' },
  getElementById: () => null,
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener() {},
  createElement: () => ({ style: {}, addEventListener() {}, remove() {}, click() {},
                          appendChild() {} }),
  body: { appendChild() {} },
};
globalThis.localStorage = {
  _s: {},
  getItem(k) { return k in this._s ? this._s[k] : null; },
  setItem(k, v) { this._s[k] = String(v); },
  removeItem(k) { delete this._s[k]; },
};
globalThis.fetch = async (url) => {
  const text = curl([String(url)]);
  return { ok: true, status: 200, json: async () => JSON.parse(text),
           text: async () => text };
};
//: ★同步 XHR，用 curl 顶（见抬头）。只实现被用到的那几个成员。
globalThis.XMLHttpRequest = class {
  open(method, url) { this._url = url; this._m = method; }
  setRequestHeader() {}
  send(body) {
    this.responseText = curl(['-X', this._m, '--data-binary', '@-',
                              '-H', 'content-type: application/json', this._url], body);
    this.status = this.responseText.startsWith('{') ? 200 : 500;
    if (this.responseText.includes('"error"')) this.status = 400;
  }
};

for (const f of ['i18n.js', 'lang-zh.js', 'lang-en.js', 'version.js',
                 'deck-names.js', 'kernel-abi.js', 'kernelapi.js', 'fylite.js'])
  vm.runInThisContext(readFileSync(SITE + f, 'utf8'), { filename: f });

const FyLite = globalThis.FyLite;
const wasmFile = SITE + 'fylite_rs.wasm.' + (globalThis.FyVersion && globalThis.FyVersion.kernel
                                             || '0.0.1');
if (!existsSync(wasmFile)) {
  console.log(`跳过：没有 ${wasmFile} —— 两条路要都在才比得成`);
  process.exit(0);
}

const wasmBytes = readFileSync(wasmFile);
const viaWasm = await FyLite.fromBytes(wasmBytes);
//: ★`fromBytes` 不散列（浏览器里是 `load()` 顺手算的，用 `crypto.subtle`）。
//: 这条闸子要比两条路各自报的身份，所以在这里补上——用同一种散列。
viaWasm.sha256 = createHash('sha256').update(wasmBytes).digest('hex');
viaWasm.bytes = wasmBytes.byteLength;
const viaApi = await FyLite.attach('assets/fylite_rs.wasm');
if (viaApi.via !== 'api') {
  console.error('探测没走到 /api/kernel —— 这条闸子比的就不是两条路了');
  process.exit(1);
}

// --- 比 --------------------------------------------------------------------
const CASES = [
  ['ellipke  完全椭圆积分（入数组、两个出数组）',
   (fy) => fy.ellipke([0, 0.25, 0.5, 0.75, 0.9])],
  ['dtReactivity  纯标量进、标量出',
   (fy) => [fy.dtReactivity(1), fy.dtReactivity(10), fy.dtReactivity(30)]],
  ['trappedFractionEps  一入一出',
   (fy) => fy.trappedFractionEps([0.01, 0.1, 0.3, 0.5])],
  ['spitzerEta  三个入数组',
   (fy) => fy.spitzerEta([100, 1000, 5000], [1, 2, 3], [15, 16, 17])],
  ['interp  两组长度不同的入数组',
   (fy) => fy.interp([0.1, 0.5, 0.9], [0, 0.25, 0.5, 0.75, 1], [0, 1, 4, 9, 16])],
  ['quadrature  规则由整数选，出一个数',
   (fy) => fy.quadrature([0, 1, 4, 9, 16, 25, 36], 0.5, 0)],
  ['adasSpecies  字节出参（名字表）',
   (fy) => fy.adasSpecies()],
  ['adasId + adasCooling  字节入参，再走一次数组',
   (fy) => {
     const id = fy.adasId('W');
     return [id].concat(Array.from(fy.adasCooling(id, [0.1, 1, 10])));
   }],
  ['millerBoundary  形状参数进、两条轮廓出',
   (fy) => fy.millerBoundary({ r0: 1.85, z0: 0.02, a: 0.45, kappa: 1.8,
                               deltaU: 0.4, deltaL: 0.55 }, 33)],
];

function flat(v) {
  if (v == null) return [v];
  if (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') return [v];
  if (Array.isArray(v) || ArrayBuffer.isView(v)) return Array.from(v).flatMap(flat);
  return Object.keys(v).sort().flatMap((k) => flat(v[k]));
}

let bad = 0, totalOff = 0, worstAll = 0;
for (const [what, run] of CASES) {
  let a, b, err = null;
  try { a = flat(run(viaWasm)); } catch (e) { err = 'wasm: ' + e.message; }
  try { b = flat(run(viaApi)); } catch (e) { err = err || ('api: ' + e.message); }
  if (err) { console.log(`  ✗ ${what}\n      ${err}`); bad += 1; continue; }
  if (a.length !== b.length) {
    console.log(`  ✗ ${what}  长度不同：wasm ${a.length}，api ${b.length}`);
    bad += 1;
    continue;
  }
  //: ★`Object.is` 让 NaN 与 NaN 算相同、+0 与 -0 算不同——两者都是想要的，
  //: 因为第一问是「两条路搬的是不是同一批字节」。
  let off = 0, worst = 0, where = -1;
  //: 全局记账：判定那一行要说的是实测到的样子，不是一句想当然的「逐位相同」。
  for (let i = 0; i < a.length; i++) {
    if (Object.is(a[i], b[i])) continue;
    off += 1;
    const rel = (typeof a[i] === 'number' && typeof b[i] === 'number')
      ? Math.abs(a[i] - b[i]) / Math.max(Math.abs(a[i]), Math.abs(b[i]), Number.MIN_VALUE)
      : Infinity;
    if (rel > worst) { worst = rel; where = i; }
  }
  const ok = worst <= 1e-14;
  totalOff += off;
  if (worst > worstAll) worstAll = worst;
  console.log(`  ${ok ? (off ? '≈' : '✓') : '✗'} ${what}  （${a.length} 个数`
              + (off ? `，${off} 个末位不同，最大相对差 ${worst.toExponential(1)}` : '，逐位相同')
              + '）');
  if (!ok) {
    bad += 1;
    console.log(`      [${where}] wasm ${a[where]} ≠ api ${b[where]}`);
  }
}

// --- 那三个不桥的，必须按名拒绝 ---------------------------------------------
console.log('\n=== 不桥的那几个必须按名拒绝 ===');
for (const name of ['fylite_rs_fyo', 'fylite_rs_free', 'fylite_rs_alloc', 'no_such_symbol']) {
  const body = JSON.stringify({ fn: name, args: [] });
  const answer = curl(['-X', 'POST', '--data-binary', '@-',
                       '-H', 'content-type: application/json', BASE + 'api/kernel'], body);
  const refused = answer.includes('"error"');
  //: ★`alloc` / `free` 拒绝得**尤其**要紧：`free` 的第一格按类型看是个出缓冲，
  //: 桥若照办就是让内核释放一块桥自己的内存——一个 HTTP 请求触发的未定义行为。
  console.log(`  ${refused ? '✓' : '✗'} ${name.padEnd(18)} ${answer.slice(0, 90)}`);
  if (!refused) bad += 1;
}

// --- 身份：两条路报的不是同一个，而且都得报 ---------------------------------
console.log('\n=== 算力身份 ===');
console.log(`  wasm  sha256 ${String(viaWasm.sha256).slice(0, 16)}…  ${viaWasm.bytes} 字节`);
console.log(`  api   sha256 ${String(viaApi.sha256).slice(0, 16)}…  内核 ${viaApi.kernelVersion}`);
if (!viaApi.sha256) {
  //: ★★续算闸（`checkpoint.js`）按内核散列判「这份状态是不是当前这个内核写的」。
  //: 走 API 时没有一份 `.wasm` 可散列，所以身份必须由请求面报出来——报不出，
  //: 那道闸就只会说「当前内核还没报出身份」，而读者会以为是还没加载完。
  console.log('  ✗ /api/health 没报出内核身份 —— 续算闸会因此永远说「等它就绪」');
  bad += 1;
}
if (viaApi.abi !== viaWasm.abi) {
  console.log(`  ✗ ABI 不同：wasm ${viaWasm.abi}，api ${viaApi.abi} —— 两份内核不是同一次构建`);
  bad += 1;
}

console.log('\n判定：' + (bad
  ? `两条算力路不一致（${bad} 项）`
  : (totalOff
     ? `两条算力路一致（${totalOff} 个数末位不同，最大相对差 ${worstAll.toExponential(1)}，`
       + '都在 1 e-14 以内——见抬头对两份 libm 的判读）'
     : '两条算力路逐位相同')));
process.exit(bad ? 1 : 0);
