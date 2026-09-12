// 改一个档位 = 改会话文档的一个字段 —— 而不是改页面里的一个变量
//
// ★★这道闸要说的一件事（H-10 的**会话文档**这一半，2026-09-12）。设计里那一条是
// 「节点卡改档位 = 改计划」，判据「改一个档位后导出的计划与手改该字段的计划逐字节
// 相同」。今天**计划文档还没有落点**（H-1 待裁：三处候选各有一条硬约束），所以能
// 被断言的是同一条判据在**会话文档**（`fylite:AppSession/1`，`assets/session.js` 的
// `collect` → `envelope`）上的那一半 —— 那也正是页面今天真正导出的那份文件。
//
// ★为什么这件事要一道闸：若页面把档位存在自己的变量里，每一项目视检查都会通过，
// 而**导出的文件里没有它**，别人拿这份文件重跑得到的是另一次运行。这与
// `validate-edit.mjs`（一次拖动落成计划的一个版本）是同一条判据的两半：那一半管
// 几何手把，这一半管 141 个档位。
//
// ★oracle 不是页面：控件集合取自**词表** `assets/vocab-model.js`（U-1 / U-2 之后
// 词表是源，页面只带挂点），元素由词表逐条造出来，`FySession.collect` 读它们。
// 所以这道闸问的是「`collect`/`apply`/`envelope` 这条路上，一个档位是否就是文档
// 的一个字段」，不问页面是否长得对（那是 `validate-form.mjs`）。
//
// ★不需要 wasm、不需要 `fy`、不需要浏览器：`session.js` 只要一个带
// `getElementById` 的对象。
//
// Run: node app/tests/validate-setting-is-the-document.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = (() => { const i = process.argv.indexOf('--site'); return (i >= 0 ? process.argv[i + 1] : path.join(HERE, '..', 'assets')) + path.sep; })();

globalThis.self = globalThis;
globalThis.window = globalThis;
vm.runInThisContext(readFileSync(SITE + 'session.js', 'utf8'), { filename: 'session.js' });
vm.runInThisContext(readFileSync(SITE + 'vocab-model.js', 'utf8'), { filename: 'vocab-model.js' });
const S = globalThis.FySession;
const V = globalThis.FyVocab.model;
assert.ok(S && V && Array.isArray(V.params) && V.params.length > 0, '词表或 session.js 没装上');

//: 一条词表条目 → 一个控件。`collect` 只用 `type` / `tagName` / `value` /
//: `checked`，`apply` 另外用 `min` / `max`（它按控件自己的界夹逼一份导入的值）
const elementOf = (p) => {
  if (p.kind === 'checkbox') return { id: p.id, type: 'checkbox', checked: !!p.checked };
  if (p.kind === 'select') {
    return { id: p.id, tagName: 'SELECT', type: 'select-one', value: String(p.choices[0].value) };
  }
  return { id: p.id, type: p.kind, value: p.value,
           min: p.min === undefined ? '' : p.min, max: p.max === undefined ? '' : p.max };
};
//: 页面那一侧的 `scope` 是按部件前缀解析名字的 `$`（`assets/scenario.js`）；
//: 这里照同一个契约给一个，键用词表的 `name`
const build = () => {
  const by = {};
  V.params.forEach((p) => { by[p.name] = elementOf(p); });
  return { by, scope: { getElementById: (name) => by[name] || null } };
};
const NAMES = V.params.map((p) => p.name);

//: ---- ⓪每个档位**自己声明缺省** ----
//: ★★这一条是写这道闸时撞上的真错（2026-09-12）：六条 LH 档位（`evolve-lhpower1`
//: 与另外五条）只有 `min` / `max` / `step`。`form.js` 只在声明了 `value` 时才写
//: value 属性，而 `input[type=range]` 缺 value 时按 HTML 规范取 min 与 max 的中点
//: —— 真正在跑的缺省于是由浏览器定，词表说不出它是什么。补登的六个数就是那六个
//: 中点（见 `vocab-model.js` 抬头）。缺省不声明 ⇒ 下面「手改 = 改档位」那几条也
//: 无从谈起：`collect` 在一个没有 value 的元素上读回 NaN。
{
  const undeclared = V.params.filter((p) => (
    p.kind === 'range' ? p.value === undefined
    : p.kind === 'checkbox' ? p.checked === undefined
    : !(p.choices && p.choices.length)));
  assert.deepEqual(undeclared.map((p) => p.name), [], (
    `这些档位没有声明缺省：${undeclared.map((p) => p.name).join(',')} —— ` +
    '浏览器会替它们挑一个（range 取 min/max 的中点），于是跑的是一个词表说不出的数'));
}

//: ---- ①一个档位就是一个字段：141 条全在，一条不多 ----
const fresh = build();
const base = S.collect(NAMES, fresh.scope);
assert.equal(Object.keys(base).length, NAMES.length, (
  `导出的配置有 ${Object.keys(base).length} 个字段，词表有 ${NAMES.length} 个档位 —— ` +
  '某个档位没进文件（`collect` 找不到它）或多出了一个'));
NAMES.forEach((n) => assert.ok(n in base, `档位 ${n} 不在导出的配置里`));

//: ---- ②改一个档位，**只有**那一个字段动 ----
const moved = (name, mutate) => {
  const w = build();
  const before = S.collect(NAMES, w.scope);
  mutate(w.by[name]);
  const after = S.collect(NAMES, w.scope);
  const diff = NAMES.filter((n) => JSON.stringify(before[n]) !== JSON.stringify(after[n]));
  assert.deepEqual(diff, [name], (
    `改 ${name} 一个档位，导出的配置动了 ${diff.length} 个字段（${diff.join(',')}）` +
    '—— 一个档位不再对应一个字段'));
  return { before, after };
};
//: 三种控件各一个代表：连续量 · 枚举 · 开关
const rng = V.params.find((p) => p.kind === 'range' && p.max > p.value);
const sel = V.params.find((p) => p.kind === 'select' && p.choices.length > 1);
const chk = V.params.find((p) => p.kind === 'checkbox');
assert.ok(rng && sel && chk, '词表里三种控件不全 —— 代表选不出来');
const cases = [
  [rng.name, (el) => { el.value = rng.value + (rng.step || 0.1); }, rng.value + (rng.step || 0.1)],
  [sel.name, (el) => { el.value = String(sel.choices[1].value); }, String(sel.choices[1].value)],
  [chk.name, (el) => { el.checked = !chk.checked; }, !chk.checked],
];
for (const [name, mutate, want] of cases) {
  const { before, after } = moved(name, mutate);
  assert.deepEqual(after[name], want, `${name}: 文件里写下的不是改后的值`);

  //: ---- ③与**手改该字段**逐字节相同 ----
  const hand = JSON.parse(JSON.stringify(before));
  hand[name] = want;
  assert.equal(JSON.stringify(after), JSON.stringify(hand), (
    `${name}: 改档位导出的配置与手改该字段的配置不逐字节相同 —— ` +
    '页面那一侧多写或少写了东西'));

  //: ---- ④手改的那一份读回来就是它（往返），且**按控件自己的界夹逼** ----
  const w = build();
  const r = S.apply(hand, w.scope);
  assert.deepEqual(r.skipped, [], `${name}: 导入时被跳过的字段：${r.skipped.join(',')}`);
  assert.equal(JSON.stringify(S.collect(NAMES, w.scope)), JSON.stringify(hand), (
    `${name}: 手改的配置导入再导出不是同一份 —— 往返丢了东西`));
}

//: ---- ⑤越界的手改进不来（一份文件是不可信输入，不能把求解器推出 UI 的界）----
{
  const w = build();
  const wild = JSON.parse(JSON.stringify(base));
  wild[rng.name] = rng.max * 1e3;
  S.apply(wild, w.scope);
  const got = S.collect(NAMES, w.scope)[rng.name];
  assert.equal(got, rng.max, (
    `手改成 ${wild[rng.name]} 之后读回 ${got}，而控件的上界是 ${rng.max} —— 没有夹逼`));
}

//: ---- ⑥导出的**整份文档**里，除两个时间戳以外没有别的不定项 ----
const envOf = (cfg) => S.envelope('model', cfg, null);
const stamp = (d) => { const o = JSON.parse(JSON.stringify(d)); o['@id'] = 'x'; o['fylite:created'] = 'x'; return o; };
{
  const a = envOf(base), b = envOf(base);
  const da = Object.keys(a).filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]));
  assert.ok(da.every((k) => k === '@id' || k === 'fylite:created'), (
    `同一组档位的两份文档除时间戳外还差：${da.join(',')}`));
  assert.equal(JSON.stringify(stamp(a)), JSON.stringify(stamp(b)), '同一组档位的两份文档不逐字节相同');
}
//: 而改一个档位之后，两份文档之差**恰好**是那一个字段
{
  const w = build();
  w.by[rng.name].value = rng.value + (rng.step || 0.1);
  const changed = stamp(envOf(S.collect(NAMES, w.scope)));
  const plain = stamp(envOf(base));
  const diff = Object.keys(changed).filter((k) => JSON.stringify(changed[k]) !== JSON.stringify(plain[k]));
  assert.deepEqual(diff, ['fylite:config'], `改一个档位动了文档的 ${diff.join(',')}`);
  const cd = Object.keys(changed['fylite:config']).filter(
    (k) => JSON.stringify(changed['fylite:config'][k]) !== JSON.stringify(plain['fylite:config'][k]));
  assert.deepEqual(cd, [rng.name], `改一个档位动了配置的 ${cd.join(',')}`);
}

console.log(`validate-setting-is-the-document: 词表 ${NAMES.length} 个档位各是文档的一个字段；` +
  `改 ${rng.name} / ${sel.name} / ${chk.name} 三种控件各一个，导出的配置与手改该字段的逐字节相同；` +
  `越界的手改被夹到 ${rng.max}；整份文档之差恰为那一个字段（时间戳除外）`);
