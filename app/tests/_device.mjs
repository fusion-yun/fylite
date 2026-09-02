// The device deck a browser gate runs on.
//
// ★`app/` ships its PRESET machines as fyo/JSON-LD documents under
// `app/devices/`, listed with their public sources by
// `devices/catalogue.jsonld` — everything under `app/` is published, so a
// preset is a redistribution and the licence question is answered per
// machine there.  EAST is not a preset: its deck and its reference discharge
// live in `machine_desc/east/` at the repository root, outside both the
// wheel (`python/pyproject.toml` packages only `fylite*`) and the published
// copy (`publish-app.yml` copies `app/` alone).
//
// A page reads a non-preset machine exactly one way — the import channel,
// which parses a fyo device document and keeps it in localStorage.  So that is
// the way a gate installs it too: `seed()` puts the document where an imported
// device lives, and the page then resolves `?device=east` with no test-only
// code path anywhere in the app.

import { existsSync, readFileSync } from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
export const DEVICE_DIR = HERE + '../../machine_desc';

/** The fyo device document for `id`, or null when the deck is not present. */
export function deviceDoc(id) {
  const f = `${DEVICE_DIR}/${id}/fylite_device_${id}.json`;
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
  return `装置数据缺失：${DEVICE_DIR}/${id}/fylite_device_${id}.json 不存在。`
       + `\n本仓不随 app/ 发布装置数据（见 machine_desc/README.md）；`
       + `该文件由 data/${id}/ 的装置卷宗生成。`;
}
