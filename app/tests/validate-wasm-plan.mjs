// wasm 打包清单：**每一份都要说得出谁读它、谁发它**。
//
// ★★为什么有这条闸子（2026-09-05 用户「清理规划 wasm 打包的内容」）。这一周里有
// 两份 wasm 静静地待在发行面上而没有任何读者：
//
//   · 内核那两份（1.46 MB）内嵌在可执行文件里，而同一个进程链着原生内核——
//     同一批物理装了两遍，直到「算力由 api 端提供」那条裁定把它收掉；
//   · 中间层的全套那一份（2.14 MB）装进 `app/assets/`、拷进站点，而页面一处也不
//     载入它——`cp -RL` 还把它解引用成三份，站点凭空胖四兆。
//
// 两件事都不是「构建坏了」：构建全绿，制品也都是好的，只是**没有人问过「谁读它」**。
// 这条闸子把那句问话变成判据：清单在下面，一份产物要么有读者、要么写明为什么没有。
//
//   node app/tests/validate-wasm-plan.mjs
//
// ★纯静态检查：读源码与构建脚本，不起浏览器、不需要构建产物在场。产物不在场时
// 「谁发它」那几条照查（那是脚本里的事实），只有「盘上有没有」这一条会跳过。

import { readFileSync, existsSync, readdirSync } from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
const ROOT = HERE + '../../';
const ASSETS = ROOT + 'app/assets/';

const read = (p) => (existsSync(ROOT + p) ? readFileSync(ROOT + p, 'utf8') : '');

//: ★★**清单**。每一份 wasm 一行：谁造它、谁读它、发到哪里去。
//: 加一份 wasm 就要在这里加一行——那正是这条闸子的用处：让「多一份产物」变成一次
//: 需要写下理由的改动，而不是一次谁也没注意到的构建输出。
const PLAN = [
  {
    file: 'fylite_rs.wasm',
    what: '内核核心（平衡 · 重构 · 0-D）',
    from: '内核仓 fylite_kernel',
    //: ★名字由**调用点**给（`FyLite.attach('fylite_rs.wasm')`），不是绑定里写死的：
    //: worker 与页面线程各取一次。所以读者是它们，不是 `fylite.js`。
    reader: ['worker.js', 'scenario-model.js'],
    site: true, precache: true, exe: false,
    why: '静态站点唯一的算力；桌面宿主走 /api/kernel（2026-09-05 裁定）',
  },
  {
    file: 'fylite_kernel_ext.wasm',
    what: '内核扩展（TGLF + DKE）',
    from: '内核仓 fylite_kernel',
    reader: ['fylite.js', 'worker.js'],  //: `loadExt()` 的缺省名 + 调用点
    site: true, precache: true, exe: false,
    why: '同上；惰性载入，只有开湍流档的读者才付这笔钱',
  },
  {
    file: 'fylite_web.wasm',
    what: '中间层的**浏览器面**：装置那扇门 + g-file 那扇门',
    from: '本仓 rust/build.sh（缺省那一份，feature `abi_gfile`）',
    //: ★★**只有载入器按名取它**：`factsdb.js`（装置）与 `geqdsk.js`（g-file）都经
    //: `FyRuntimeWeb` 到达，不各自拼 URL——那正是把载入器单独拆出来的目的。名字从
    //: `fylite_facts.wasm` 改过来（2026-09-05 落地 H-4 第一块）：它不再只带装置那一面。
    reader: ['runtimeweb.js'],
    site: true, precache: true, exe: false,
    why: '静态站点的装置数据与 g-file 读法；0.51 MB，进得了预缓存，于是断网也用得上',
  },
  {
    file: 'fylite_runtime.wasm',
    what: '中间层全套 C 导出（g-file · 文档树 · 打包 · 读文本）',
    from: '本仓 rust/build.sh --full-wasm（缺省不出）',
    reader: null,                        //: ★有意为空
    site: false, precache: false, exe: false,
    why: 'H-4 的第一块已落地（g-file 走 `fylite_web.wasm`），而**全套**这一份的消费者'
       + '——文档树 / 打包 / 读文本（`fyo.js` · `session.js` 的职责）——仍未落地，'
       + '页面一处也不载入它。2.14 MB，发出去就是死重；那天把 build.sh 的缺省与 '
       + 'build-site.sh 各改一行即可',
  },
];

let bad = 0;
const ok = (cond, what, note) => {
  console.log(`  ${cond ? 'ok  ' : '✗   '} ${what}${note ? '  — ' + note : ''}`);
  if (!cond) bad += 1;
};

// --- 一、每一份都要有读者，或写明为什么没有 --------------------------------
console.log('〔一〕谁读它');
const pageSources = readdirSync(ASSETS).filter((f) => f.endsWith('.js'))
  .map((f) => ({ f, text: readFileSync(ASSETS + f, 'utf8') }));
for (const row of PLAN) {
  //: ★★在**页面源码**里找这个名字，而且只认**引号里的**那种。页面取它靠的就是
  //: 字面量（`FyLite.wasmUrl()` 只补版本号，不拼名字），而注记里提到一个产物名是
  //: 常事——第一版这条判据用的是整文件 substring，于是三处**注释**把「没有读者」
  //: 判成了红：那不是缺陷，是判据把散文当成了代码。
  //: ★★**逐行**看，而且跳过注释行。整文件一个正则不行：`[^'\"]*` 会跨行，于是文件
  //: 前面随便一个引号加上后面注记里的一次提名就算「引用」——第二版就是这么把三处
  //: 注释又判成红的。产物名在代码里总是一行之内的一个字面量。
  const cited = new RegExp("['\"][^'\"]*" + row.file.replace(/\./g, '\\.'));
  const code = (text) => text.split('\n')
    .filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l));
  const hits = pageSources.filter((s) => code(s.text).some((l) => cited.test(l)))
    .map((s) => s.f);
  if (row.reader) {
    const missing = row.reader.filter((r) => !hits.includes(r));
    ok(missing.length === 0,
       `${row.file} 的读者：${row.reader.join(' ')}`,
       missing.length ? '这几处没在取它：' + missing.join(' ')
                      : '实测取它的：' + (hits.join(' ') || '无'));
  } else {
    //: ★★「没有读者」是一条**要维持**的事实，不是一条容忍：它一旦有了读者，
    //: 清单就过期了，而过期的清单比没有清单更坏。
    ok(hits.length === 0, `${row.file} 没有读者（清单如此声明）`,
       hits.length ? '却被这些文件提到：' + hits.join(' ') : row.why);
  }
}

// --- 二、站点发什么 ---------------------------------------------------------
console.log('\n〔二〕站点发什么（tools/build-site.sh）');
const site = read('tools/build-site.sh');
const kernelWasm = /KERNEL_WASM="?([^"\n]*)"?/.exec(site);
const shipped = new Set(
  (kernelWasm ? kernelWasm[1].split(/\s+/) : [])
    .concat((/WASM_STEMS="([^"]*)"/.exec(site) || [null, ''])[1].split(/\s+/))
    .filter((x) => x && x.endsWith('.wasm'))
    .flatMap((x) => (x.startsWith('$') ? [] : [x])));
for (const row of PLAN) {
  if (row.site) {
    ok(shipped.has(row.file), `${row.file} 进站点`);
  } else {
    ok(!shipped.has(row.file) && site.includes(`rm -f "$OUT"/assets/${row.file}`),
       `${row.file} 不进站点，而且是**删掉**的（不是忘了）`, row.why);
  }
}

// --- 三、预缓存 -------------------------------------------------------------
console.log('\n〔三〕预缓存（tools/make-sw.mjs 的清单，离线时能不能取到）');
const sw = read('tools/make-sw.mjs');
const stems = (/const WASM_STEMS = \[([^\]]*)\]/.exec(sw) || [null, ''])[1];
for (const row of PLAN) {
  const inList = stems.includes(row.file);
  ok(inList === row.precache,
     `${row.file} ${row.precache ? '进' : '不进'}预缓存`,
     row.precache ? '' : row.why);
}

// --- 四、可执行文件内嵌什么 -------------------------------------------------
console.log('\n〔四〕可执行文件（tools/build-app-exe.sh）');
const exe = read('tools/build-app-exe.sh');
for (const row of PLAN) {
  ok(!row.exe, `${row.file} 不内嵌`);
}
//: ★★一份也不带，而且是**删掉**的。可执行文件里页面的算力与装置信息都走本进程
//: （/api/kernel · /api/facts），带 wasm 就是同一批字节装两遍。
ok(/rm -f "\$STAGE"\/assets\/fylite_runtime\.wasm\*/.test(exe)
   && /fylite_rs\.wasm\*/.test(exe) && /fylite_kernel_ext\.wasm\*/.test(exe),
   '内嵌树里三份 wasm 都被显式删掉');
//: ★h5wasm 同理（2026-09-05 裁定：hdf5 走 fy app 的文件端点）。
ok(/rm -rf "\$STAGE"\/assets\/vendor/.test(exe),
   'assets/vendor（h5wasm 4.1 MB）也不内嵌 —— 页面走 /api/read');

// --- 五、盘上有没有（有产物时才查） -----------------------------------------
console.log('\n〔五〕这一份检出里实有的');
const v = (/kernel:\s*'([^']*)'/.exec(read('app/assets/version.js')) || [])[1];
const rv = (/FyRuntimeVersion\s*=\s*'([^']*)'/.exec(read('app/assets/runtime-version.js')) || [])[1];
for (const row of PLAN) {
  const ver = row.from.includes('内核仓') ? v : rv;
  const real = ver && existsSync(ASSETS + `${row.file}.${ver}`);
  const note = real ? `${(readFileSync(ASSETS + `${row.file}.${ver}`).length / 1048576).toFixed(2)} MB`
                    : '不在盘上';
  //: ★不在盘上不算错（制品不入库，一份新鲜检出里一个也没有），但**要报出来**：
  //: 它决定下面那句「这一版发得出去吗」的答案。
  console.log(`  note  ${row.file.padEnd(24)} ${note}${real ? '' : ' —— ' + (row.site ? '站点会缺它' : '按清单本就不出')}`);
}

console.log('\n判定：' + (bad ? `wasm 打包清单 ${bad} 项不符` : 'wasm 打包清单与构建脚本一致'));
process.exit(bad ? 1 : 0);
