// The device deck a browser gate runs on.
//
// ★★2026-09-02：这段抬头从前写着「EAST is not a preset: its deck lives in
// `machine_desc/` at the repository root」。**那已经不成立**：2026-08-22 用户裁定
// 装置数据入 `app/`，而分仓之后 `app/devices/east.jsonld` 与 `iter.jsonld` 是随
// `app/` 一起发布的**真文档**（不是链接——分仓那阵它们曾是指向 `machine_desc/`
// 的符号链接，克隆下来就是两条断链，已改回实拷）。`machine_desc/` 本身留在私有
// 的内核仓。
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
export const DEVICE_DIR = HERE + '../../machine_desc';
export const PRESET_DIR = HERE + '../devices';

/** The fyo device document for `id`, or null when neither copy is present. */
export function deviceDoc(id) {
  for (const f of [`${PRESET_DIR}/${id}.jsonld`,
                   `${DEVICE_DIR}/${id}/fylite_device_${id}.json`])
    if (existsSync(f)) return JSON.parse(readFileSync(f, 'utf8'));
  return null;
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
  return `装置数据缺失：${DEVICE_DIR}/${id}/fylite_device_${id}.json 不存在。`
       + `\n发布的预设在 app/devices/，源树在私有仓的 machine_desc/；两处都没有。`
       + `该文件由 data/${id}/ 的装置卷宗生成。`;
}
