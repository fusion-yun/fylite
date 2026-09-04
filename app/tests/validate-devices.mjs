// Oracle test for app/assets/devices.js: the machine REGISTRY, not the
// descriptor.  `validate-device.mjs` next door checks that one machine
// survives a round trip through the fyo document; this checks that a visitor
// can get several machines INTO the page and one back out of it.
//
// ★★Why it exists.  Importing a device switches to it, and switching reloads
// (a page half-way between two tokamaks is still showing the previous one's
// numbers).  That is right for one file and wrong for four: each import
// reloaded before the next could start, so a reader with four decks could
// load one.  `importMany` stores them all and leaves the switch to the
// caller — and this is what holds it to that.
//
//   node app/tests/validate-devices.mjs

import { readFileSync, existsSync } from 'node:fs';
import { DEVICES_DIR } from './_preset.mjs';
import vm from 'node:vm';

const HERE = new URL('.', import.meta.url).pathname;
const SITE = HERE + '../assets/';
const DESC = HERE + '../../machine_desc/';

globalThis.self = globalThis;

// --- the browser surface these modules touch, and no more -----------------
// ★A stub per thing that is actually reached.  A blanket `document = {}`
// would let a missing call through as `undefined` and report a pass.
const store = {};
globalThis.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: (k) => { delete store[k]; },
};
globalThis.location = { search: '', href: 'http://localhost/pages/model.html' };
globalThis.URL = URL;
globalThis.URLSearchParams = URLSearchParams;
globalThis.document = {
  documentElement: { lang: 'zh', setAttribute() {}, getAttribute: () => 'zh' },
  getElementById: () => null,
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener() {},
  createElement: () => ({ style: {}, addEventListener() {}, remove() {},
                          click() {}, appendChild() {} }),
  body: { appendChild() {} },
};

for (const f of ['i18n.js', 'lang-zh.js', 'lang-en.js',
                 'device.js', 'fyodev.js', 'geqdsk.js', 'devices.js'])
  vm.runInThisContext(readFileSync(SITE + f, 'utf8'), { filename: f });

// ★The presets arrive by FETCH now, so a host with no `fetch` has none.
// `load()` takes the directory, which is what lets this read them off disk
// without a server; the page passes nothing and resolves it from its own
// script URL.
globalThis.fetch = async (url) => {
  const f = url.replace(/^.*\/(?:devices|facts\/device)\//, DEVICES_DIR);
  if (!existsSync(f)) return { ok: false, status: 404 };
  const text = readFileSync(f, 'utf8');
  return { ok: true, status: 200, json: async () => JSON.parse(text) };
};
await globalThis.FyDevices.load(DEVICES_DIR);

const D = globalThis.FyDevices;
let bad = 0;
const ok = (cond, what) => {
  if (cond) { console.log('  ok   ' + what); return; }
  console.log('  FAIL ' + what); bad++;
};

// --- what the build ships -------------------------------------------------
const builtin = D.list().filter((d) => d.builtin).map((d) => d.id);
const presetIds = builtin.slice();
ok(builtin.length >= 1, `the build ships ${builtin.length} machine(s) `
   + `(${builtin.join(', ')})`);

// --- several documents in one go -----------------------------------------
// ★The real files, not fixtures.  A registry test on invented documents
// checks the registry against a machine nobody has.
//: ★★2026-09-01：这张表原是 `['iter', 'cfetr', 'best']`——按当时仓里有哪几台
//: 写死的。cfetr 与 best 已随「PF 线圈表出处是私人通信」的裁定移出公开仓，于是
//: 只剩 iter 一台，而下面那条 `>= 2` 就红了。红的不是注册表，是这张表过期了。
//: 改成按 `machine_desc/` **实际在场**的来取，并保持「至少两台」——两台是这组
//: 判据的下限（`importMany` 的「一次调用留下全部」与 id 冲突那两条都要多于一台
//: 才检得动），所以它仍然是判据，不是摆设。
const ids = ['east', 'iter'].filter(
  (id) => existsSync(`${DESC}${id}/fylite_device_${id}.json`));
const files = ids.map((id) => ({
  name: `fylite_device_${id}.json`,
  text: readFileSync(`${DESC}${id}/fylite_device_${id}.json`, 'utf8'),
}));
ok(files.length >= 2, `machine_desc carries importable documents (${ids.join(', ')})`);

// one unreadable file rides along: a partial import must SAY so
files.push({ name: 'not-a-device.json', text: '{"@type":"fylite:Nope/1"}' });
files.push({ name: 'unreadable.json', error: 'EACCES' });

const r = D.importMany(files);
ok(r.added.length === ids.length,
   `all ${ids.length} device documents were kept in one call (got ${r.added.length})`);
ok(r.failed.length === 2,
   `both unusable files were reported, not dropped (got ${r.failed.length})`);
ok(r.failed.every((f) => f.name && f.why), 'each failure names the file and why');
for (const a of r.added)
  ok(a.coils > 0 && a.name, `${a.id}: ${a.coils} coils, ${a.loops} loops`);

// ★a built-in must never be shadowed: an imported machine with a built-in's
// id would make every provenance claim on the page false
const clash = D.importMany([{ name: 'iter.json',
                              text: files[0].text }]);
ok(clash.added.length === 1 && clash.added[0].id !== builtin[0]
   && clash.added[0].id.startsWith(ids[0]),
   `a second ${ids[0]} is renamed rather than shadowing anything `
   + `(${clash.added[0] && clash.added[0].id})`);

const after = D.list().map((d) => d.id);
ok(after.length === builtin.length + ids.length + 1,
   `the list shows every machine (${after.join(', ')})`);

// --- and back out ---------------------------------------------------------
const victim = clash.added[0].id;
const gone = D.remove(victim);
ok(gone && gone.removed === victim && gone.next,
   `removing an imported machine names where to go next (${gone && gone.next})`);
ok(!D.list().some((d) => d.id === victim), 'it is out of the list');
ok(D.remove(builtin[0]) === null, 'a built-in refuses to be removed');
ok(D.remove('no-such-machine') === null, 'removing what is not there is a no-op');

// --- the store survives a reload -----------------------------------------
// ★Re-running the module against the SAME localStorage is what a reload is.
// The imported machines have to come back, or the page reloads into a
// tokamak the visitor never chose.
for (const k of Object.keys(globalThis))
  if (k === 'FyDevices') delete globalThis[k];
vm.runInThisContext(readFileSync(SITE + 'devices.js', 'utf8'),
                    { filename: 'devices.js#reload' });

// ★★The imported machines are back IMMEDIATELY — they are in localStorage,
// which is synchronous.  The PRESETS are not: they are fetched, so a fresh
// instance has none until `load()` resolves, which is precisely why the
// page's boot waits for it before finalising anything.
// ★the ids the IMPORT produced, not the ids of the source machines: every
// one of them collides with a preset of the same name and is renamed, which
// is the shadowing rule doing its job
const mine = r.added.map((a) => a.id);
const beforeLoad = globalThis.FyDevices.list().map((d) => d.id).sort();
ok(mine.every((id) => beforeLoad.includes(id)),
   `imported machines are back at once (${beforeLoad.join(', ')})`);
ok(!presetIds.some((id) => beforeLoad.includes(id)),
   `and the presets are NOT, until the catalogue has been read `
   + `(${presetIds.join(', ')})`);

await globalThis.FyDevices.load(DEVICES_DIR);
const back = globalThis.FyDevices.list().map((d) => d.id).sort();
ok(presetIds.every((id) => back.includes(id)),
   `the presets arrive with load() (${back.join(', ')})`);
ok(mine.every((id) => back.includes(id)), 'and every imported machine is still there');

// --- the SELECTION BAR itself --------------------------------------------
// ★★The list is not the whole control: it is a list and two verbs, and the
// add verb is the one that must take SEVERAL files.  A registry that can do
// it and a bar that calls it one file at a time is the same defect one layer
// up, so the wiring is checked rather than assumed.
function el(tag) {
  return { tagName: tag, id: '', innerHTML: '', value: '', disabled: false,
           title: '', _on: {},
           addEventListener(k, f) { (this._on[k] = this._on[k] || []).push(f); },
           fire(k) { (this._on[k] || []).forEach((f) => f()); },
           get options() { return (this.innerHTML.match(/<option/g) || []); } };
}
const sel = el('SELECT'), addBtn = el('BUTTON'), delBtn = el('BUTTON');
const nodes = { 'm-device': sel, 'm-dev-add': addBtn, 'm-dev-del': delBtn };
globalThis.document.getElementById = (id) => nodes[id] || null;

// the picker records what it was asked for instead of opening one
let picked = null;
globalThis.FyGeqdsk.openTexts = (cb, accept) => { picked = { cb, accept }; };

let said = null;
globalThis.confirm = () => true;
globalThis.FyDevices.installSelector('m-device', {
  addBtn: 'm-dev-add', removeBtn: 'm-dev-del',
  report: (msg, cls) => { said = { msg, cls }; },
});
ok(sel.options.length === globalThis.FyDevices.list().length,
   `the bar lists every machine (${sel.options.length})`);

addBtn.fire('click');
ok(picked !== null, 'the add control opens a picker');
ok(String(picked.accept).includes('json'), 'and asks for JSON');

// ★the real reader is `input.multiple`; check the picker itself sets it
let madeInput = null;
globalThis.document.createElement = () => (madeInput = {
  style: {}, addEventListener() {}, remove() {}, click() {}, appendChild() {},
});
//: put the real picker back over the recorder, then ask it for files
vm.runInThisContext(readFileSync(SITE + 'geqdsk.js', 'utf8'),
                    { filename: 'geqdsk.js#picker' });
globalThis.FyGeqdsk.openTexts(() => {}, '.json');
ok(madeInput && madeInput.multiple === true,
   'the picker accepts more than one file at a time');
ok(madeInput && madeInput.type === 'file', 'and it is a file input');

// ★The active machine here is the BUILT-IN one, and a built-in cannot be
// removed — so the control must be disabled rather than offering an action
// it will refuse.  A button that reports "cannot" only after being pressed
// teaches the reader to distrust the bar.
ok(delBtn.disabled === true,
   'the remove control is disabled while a built-in machine is active');

console.log(bad ? `判定：装置注册表 ${bad} 项未过` : '判定：装置注册表与选择栏通过');
process.exit(bad ? 1 : 0);
