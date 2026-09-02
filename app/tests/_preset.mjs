// The preset machines a published page ships, read the way a page reads them.
//
// ★★A preset is an fyo/JSON-LD document under `app/devices/`, listed by
// `app/devices/catalogue.jsonld`, and parsed by `FyoDevice.fromFyo` — the
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

const HERE = new URL('.', import.meta.url).pathname;
export const DEVICES_DIR = HERE + '../devices/';

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
    const m = FyoDevice.fromFyo(docs[id]);
    m.id = id;
    out[id] = m;
  }
  return out;
}
