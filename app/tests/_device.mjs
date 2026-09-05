// The device deck a browser gate runs on.
//
// ★★2026-09-02：这段抬头从前写着「EAST is not a preset: its deck lives in
// `machine_desc/` at the repository root」。**那已经不成立**：2026-08-22 用户裁定
// 装置数据入 `app/`，而分仓之后 `app/facts/device/east.jsonld` 与 `iter.jsonld` 是随
// `app/` 一起发布的**真文档**（不是链接——分仓那阵它们曾是指向 `machine_desc/`
// 的符号链接，克隆下来就是两条断链，已改回实拷）。源树那一份今天是 `devices/`
// ——本仓 gitignored 的拖回输入。
//
// 所以取法是**先看发布出去的那份，再回退到源树**：前者在只有本仓的检出上就有，
// 后者只在两边都检出的机器上才有。两者内容逐字节相同（`catalogue.jsonld` 的注记
// 与 `python/tests/test_machine_desc.py` 各自说过这件事）。
//
// A page reads a non-preset machine exactly one way — the import channel,
// which parses a fyo device document and keeps it in localStorage.  So that is
// the way a gate installs it too: `seed()` puts the document where an imported
// device lives, and the page then resolves `?device=east` with no test-only
// code path anywhere in the app.

import { existsSync, readFileSync } from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
//: ★2026-09-04 `machine_desc/` → `devices/` → `facts/device/`；★★2026-09-05 用户
//: 裁定「fylite 下已无 facts 目录」，拖回的语料落在构建暂存区 **`dist/facts/device/`**：
//: 一个个体一目录（卡片 + 许可账同住），旁边一份页面读得懂的 `<id>.jsonld`，
//: gitignored，由 `tools/abox-to-facts.py` 从 fydoc 的 A-Box 拖回。
//: ★**只有这一处来源了**。从前这里先看 `app/facts/device/`（指向仓根 `facts/` 的
//: 符号链接）再回退源树；那条链接与仓根 `facts/` 都已撤，而**发布出去的那一份**
//: 今天不是文件，是编进 `libfylite_runtime.so` / `fylite_runtime.wasm` 的
//: `facts.rs`（同日裁定：页面也走中间层 wasm）。闸子要的是一份能拖进页面的文档
//: 文本，所以读暂存区里的那一份——与编进制品的是同一批字节。
export const DEVICE_DIR = HERE + '../../dist/facts/device';

/** The fyo device document for `id`, or null when this checkout has none. */
export function deviceDoc(id) {
  const f = `${DEVICE_DIR}/${id}.jsonld`;
  return existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : null;
}

/**
 * Install `id` as an imported device in every page of `ctx`.
 *
 * Returns false when the deck is absent, naming where it was looked for —
 * a caller that needs the machine can then say so and stop, rather than
 * silently running on whichever device the page defaulted to.
 */
export async function seedDevice(ctx, id) {
  const doc = deviceDoc(id);
  if (!doc) return false;
  await seedDeviceDocs(ctx, { [id]: doc });
  return true;
}

/**
 * Install a whole map of `{id: document}` as imported devices.
 *
 * ★For a gate that has to SWITCH machines: a device switch reloads the page
 * with `?device=<id>`, and the page can only resolve an id the store already
 * holds.  Both (or all) documents therefore have to be seeded in one go,
 * before the first navigation.
 */
export async function seedDeviceDocs(ctx, docs) {
  await ctx.addInitScript((dev) => {
    localStorage.setItem('fylite-devices', JSON.stringify(dev));
  }, docs);
}

/** The deck directory itself — the layout `fylite.machine` documents. */
export function deckDir(id) { return `${DEVICE_DIR}/${id}`; }

/**
 * Environment for a native oracle that needs the same machine.
 *
 * `fylite.machine` deliberately guesses no location, so a gate that installed
 * a device in the browser has to say where the Python half should read it
 * from — otherwise the two halves compare two different machines, or the
 * oracle stops on a missing deck it is standing next to.  An explicitly set
 * `$FYLITE_DEVICE_DIR` wins: whoever set it meant it.
 */
export function envWithDeck(id) {
  if (process.env.FYLITE_DEVICE_DIR) return process.env;
  return { ...process.env, FYLITE_DEVICE_DIR: deckDir(id) };
}

/** Message for a gate that cannot run without the deck. */
export function missingDeviceMessage(id) {
  return `装置数据缺失：${DEVICE_DIR}/${id}.jsonld 不存在。`
       + `\n它由 tools/abox-to-facts.py 从 fydoc 的 A-Box 拖回（暂存区 gitignored）：`
       + `\n  python3 tools/abox-to-facts.py ${id}`;
}
