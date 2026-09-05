// The preset machines a published page ships, read the way a page reads them.
//
// ★★A preset is an fyo/JSON-LD document under `app/facts/device/`, listed by
// `app/facts/device/catalogue.jsonld`, and parsed by `FyoDevice.fromFyo` — the
// same reader an imported file goes through.  It used to be
// `assets/dev-iter.js`, a script that pushed a descriptor onto a global, so
// a gate could get the machine by loading one more file.  It cannot now, and
// it should not want to: a gate that reached past the document reader would
// be testing a machine the page never builds.
//
// `presets(vm)` runs the catalogue through whatever `FyoDevice` is already in
// the host, so a gate that has stubbed the DOM gets exactly the descriptors
// its page would.

import { readFileSync, existsSync } from 'node:fs';
import vm from 'node:vm';

const HERE = new URL('.', import.meta.url).pathname;
const ASSETS = HERE + '../assets/';
//: ★2026-09-05 用户裁定：仓顶已无 `facts/`，也没有 `app/facts` 那条链接；
//: 拖回来的语料在 `dist/facts/`（构建暂存区）。
export const DEVICES_DIR = HERE + '../../dist/facts/device/';

/** The catalogue document, or null when this tree ships no presets. */
export function catalogue() {
  const f = DEVICES_DIR + 'catalogue.jsonld';
  return existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : null;
}

/** `{id: document}` for every machine the catalogue lists. */
export function presetDocs() {
  const cat = catalogue();
  const out = {};
  for (const e of (cat && cat['fylite:devices']) || []) {
    const id = e['fylite:device_id'];
    const f = DEVICES_DIR + e['fylite:document'];
    if (!id || !existsSync(f)) continue;
    out[id] = JSON.parse(readFileSync(f, 'utf8'));
  }
  return out;
}

/**
 * `{id: descriptor}` — the documents through `FyoDevice.fromFyo`.
 *
 * ★Takes the reader as an argument rather than importing it: these gates run
 * the browser sources through `vm` into the current realm, so the reader a
 * gate must use is the one IT loaded, not a second copy.
 */
export function presets(FyoDevice) {
  const docs = presetDocs();
  const out = {};
  for (const id of Object.keys(docs)) {
    //: ★★**读不了的那一台点名跳过，不带着整轮闸子一起死**——与页面同一条纪律
    //: （`devices.js` 的 `load()` 逐份 `.catch`，把失败记进 `out.failed`）。
    //: 2026-09-05 实测：这里从前直接 `fromFyo`，于是**语料里第一台读不了的机器
    //: 就让每一条用它的闸子整个崩掉**，报的还是那一台的错——而闸子问的本来是
    //: 别的事（q 剖面、装置导入）。一台机器的数据缺口不该表现成一屏无关的红。
    //: ★跳过的那几台由 `presetProblems()` 报出来，另有闸子盯它们（不是无声的）。
    try {
      const m = FyoDevice.fromFyo(docs[id]);
      m.id = id;
      out[id] = m;
    } catch (e) {
      skipped[id] = e.message;
    }
  }
  return out;
}

//: 上一次 `presets()` 读不了的那几台：`{id: 为什么}`。
const skipped = {};

/** Which presets the reader refused last time, and why. */
export function presetProblems() { return { ...skipped }; }

/**
 * Put the page's own facts layer into this host, reading the **shipped wasm**.
 *
 * ★★2026-09-05 用户裁定之后，`devices.js` 的 `load()` 不再 fetch 目录与逐台文档，
 * 而是问 `FyFactsDb`——静态站点上那是 `assets/fylite_web.wasm` 里编着的
 * `facts.rs`。于是一条只在磁盘上摆几份 `.jsonld` 的闸子测不到页面真正走的那条路：
 * 它会以「这一版一台机器也没有」通过或失败，而两种都与被测代码无关。
 *
 * 这里装的是**真的 `factsdb.js`**（不是仿件），只把它够得着的宿主面补齐：
 *   · `fetch` —— 只答 `assets/*.wasm*`，从磁盘取；别的一律 404，
 *     于是 `/api/facts` 那条路自己关掉（`location` 无 hostname，探都不会探）；
 *   · `FyRuntimeVersion` —— 版本化真文件名要用它（`tools/soname.sh` 的规矩）。
 * 副作用是这条闸子同时验了**制品**：目录与文档若没编进那份 wasm，这里就空。
 *
 * 返回一个 `{ok, why}`：wasm 不在检出里时 `ok=false`，调用方自己决定是跳过还是红。
 */
export function installFactsDb(root) {
  vm.runInThisContext(readFileSync(ASSETS + 'runtime-version.js', 'utf8'),
                      { filename: 'runtime-version.js' });
  const v = root.FyRuntimeVersion;
  //: ★2026-09-05：装置那扇门搬进 `fylite_facts.wasm`（0.43 MB，只带这一面），
  //: 与页面读的是同一份产物（`factsdb.js`）。
  const wasm = ASSETS + `fylite_web.wasm.${v}`;
  if (!existsSync(wasm))
    return { ok: false, why: `${wasm} 不在检出里——先跑 bash rust/build.sh` };
  const prior = root.fetch;
  root.fetch = async (url) => {
    const m = String(url).match(/assets\/([A-Za-z0-9_.-]+\.wasm[0-9.]*)$/);
    if (m && existsSync(ASSETS + m[1])) {
      const buf = readFileSync(ASSETS + m[1]);
      return { ok: true, status: 200,
               arrayBuffer: async () => buf.buffer.slice(
                 buf.byteOffset, buf.byteOffset + buf.byteLength) };
    }
    if (prior) return prior(url);
    return { ok: false, status: 404 };
  };
  //: ★★载入器在前（2026-09-05）：`factsdb.js` 不再自己 fetch 那份 wasm，它问
  //: `FyRuntimeWeb`——那是 H-4 第一块落地时拆出来的一处实现，`geqdsk.js` 也用它。
  vm.runInThisContext(readFileSync(ASSETS + 'runtimeweb.js', 'utf8'),
                      { filename: 'runtimeweb.js' });
  vm.runInThisContext(readFileSync(ASSETS + 'factsdb.js', 'utf8'),
                      { filename: 'factsdb.js' });
  return { ok: true, wasm };
}
