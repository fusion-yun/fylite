// The PRIVATE kernel fixtures a browser / worker gate needs — one resolver.
//
// ★★2026-09-13 (user ruling, `machine_desc` retirement): the EAST device card is
// generated from fydoc's A-Box (`dist/facts/device/east.jsonld`, `_device.mjs`)
// and carries no shot.  The #137985 reference discharge, its slice series and
// their provenance (`fylite:reference_discharge` · `fylite:slices` ·
// `fylite:slices_provenance`) are experiment data, kept ONLY in the kernel
// checkout as `tests/data/east/reference_discharge_137985.fyo.jsonld` (server
// scrubbed to mds.invalid).  This public repository never carries a copy: a gate
// reads that file where it lies, located through `$FYLITE_KERNEL`, and SKIPS
// with the variable and the file named when it is not there.
//
// ★★2026-09-13 (user ruling: est2 removed at every layer): that reference discharge
// is the est2 record (79 probes + 35 loops) and the device of that channel order —
// the `efit_w_pf` magnetics provider — is gone.  So a gate that fits or solves on
// the discharge against the device SKIPS by name ({@link EST2_REMOVED}); the kernel's
// `tests/data/east/` moves to the kernel `archive/`, and a missing file names itself
// and the same reason.
//
// ★One place, not per-file path code: the location rule (which variable, which
// relative path) is what drifts, and a gate that spells it itself is the gate
// that goes on reading a retired path.

import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { DEVICE_DIR, deviceDoc, seedDeviceDocs } from './_device.mjs';

/** The environment variable naming the kernel CHECKOUT (not the library). */
export const KERNEL_ENV = 'FYLITE_KERNEL';
/** The reference discharge, relative to the kernel checkout. */
export const REFERENCE_DISCHARGE = 'tests/data/east/reference_discharge_137985.fyo.jsonld';
/** The three keys that fixture carries, as a device document spells them. */
export const SHOT_KEYS = ['fylite:reference_discharge', 'fylite:slices', 'fylite:slices_provenance'];
/**
 * Why an est2-bound EAST gate skips when its input was ARCHIVED (user ruling 2026-09-13):
 * given ONLY when the file is gone from its old path and its mirrored copy exists under
 * `$FYLITE_KERNEL/archive/<same path>` — a broken checkout never reads as "archived".
 */
export const EST2_REMOVED = 'est2 removed (2026-09-13): FYDOC-CASE-22 and the EAST fit inputs archived; '
  + 'an efit_east #137985 case will replace them';
/** …and why a record still at its old path skips: it is est2-ordered and pairs with no chain. */
export const EST2_UNPAIRED = 'est2 removed (2026-09-13): the est2 device array is gone, so this est2 '
  + 'record pairs with no measurement chain; an efit_east #137985 case will replace it';

/**
 * A file in the kernel checkout: `{ path }`, or `{ why }` naming what is missing
 * (and {@link EST2_REMOVED} when its archived copy exists).
 */
export function kernelFile(rel) {
  const root = process.env[KERNEL_ENV];
  if (!root) {
    return { why: `$${KERNEL_ENV} is not set — ${rel} lives only in the private kernel checkout` };
  }
  const p = path.resolve(root, rel);
  if (!existsSync(p)) {
    const tail = existsSync(path.resolve(root, 'archive', rel)) ? ` — ${EST2_REMOVED}` : '';
    return { why: `${p} is absent ($${KERNEL_ENV}=${root})${tail}` };
  }
  return { path: p };
}

/**
 * The #137985 reference-discharge document: `{ doc, path }` or `{ why }`.
 * `doc` holds exactly the keys of {@link SHOT_KEYS} the fixture carries.
 */
export function referenceDischarge() {
  const f = kernelFile(REFERENCE_DISCHARGE);
  if (f.why) return f;
  const full = JSON.parse(readFileSync(f.path, 'utf8'));
  if (!full['fylite:reference_discharge']) {
    return { why: `${f.path} carries no fylite:reference_discharge` };
  }
  const doc = {};
  for (const k of SHOT_KEYS) if (k in full) doc[k] = full[k];
  return { doc, path: f.path };
}

const WEB_WASM = path.join(path.dirname(new URL(import.meta.url).pathname), '../assets/fylite_web.wasm');

/**
 * `id`'s device document resolved for `request` (`{shot, measurement_chain}` — nothing
 * else: user ruling 2026-09-13) by THE rule — the runtime's `fylite_runtime_device_resolve`,
 * in the shipped `fylite_web.wasm`, not a second implementation — `{ doc, selected }` or `{ why }`.
 */
export function resolvedDeviceDoc(id, request) {
  const dev = deviceDoc(id);
  if (!dev) return { why: `dist/facts/device/${id}.jsonld is absent (python3 tools/abox-to-facts.py ${id})` };
  const resPath = path.join(DEVICE_DIR, id, `${id}_resolution.jsonld`);
  if (!existsSync(resPath)) return { why: `${resPath} is absent (python3 tools/abox-to-facts.py ${id})` };
  if (!existsSync(WEB_WASM)) return { why: `${WEB_WASM} is absent (bash rust/build.sh)` };
  const e = new WebAssembly.Instance(new WebAssembly.Module(readFileSync(WEB_WASM)), {}).exports;
  if (typeof e.fylite_runtime_device_resolve !== 'function') {
    return { why: `${WEB_WASM} exports no fylite_runtime_device_resolve (bash rust/build.sh)` };
  }
  const enc = new TextEncoder();
  const args = [JSON.stringify(dev), readFileSync(resPath, 'utf8'), JSON.stringify(request), 'document'];
  const held = [];
  try {
    const flat = [];
    for (const s of args) {
      const b = enc.encode(s);
      const p = Number(e.fylite_runtime_alloc(BigInt(b.length)));
      if (!p) throw new Error('fylite_runtime_alloc failed');
      held.push([p, b.length]);
      new Uint8Array(e.memory.buffer, p, b.length).set(b);
      flat.push(p, BigInt(b.length));
    }
    const need = Number(e.fylite_runtime_device_resolve(...flat, 0, 0n));
    if (need <= 0) return { why: `fylite_runtime_device_resolve -> ${need}` };
    const o = Number(e.fylite_runtime_alloc(BigInt(need)));
    held.push([o, need]);
    const got = Number(e.fylite_runtime_device_resolve(...flat, o, BigInt(need)));
    const out = JSON.parse(new TextDecoder().decode(new Uint8Array(e.memory.buffer, o, Math.min(got, need))));
    //: ★a refusal is the runtime's named sentence; a gate must not run on a guess
    if (out.error) throw new Error(`device ${id} resolved for ${JSON.stringify(request)}: ${out.error}`);
    return { doc: out.document, selected: out.selected };
  } finally {
    for (const [p, n] of held) e.fylite_runtime_free(p, BigInt(n));
  }
}

/**
 * EAST as a gate runs it: the A-Box-built device document with the kernel fixture's
 * shot keys added — `{ doc, path, selected }` or `{ why }`.
 *
 * ★★2026-09-13 (est2 removed): the only shot data those gates have is the #137985
 * reference discharge, an est2 record (35 loops, 79 probes in the est2 order), and no
 * measurement chain of the device pairs with it.  So this SKIPS by name — the missing
 * file first when it is already gone ({@link kernelFile}), else {@link EST2_UNPAIRED} —
 * until the efit_east #137985 case replaces it, when the seam resolves the device in that
 * case's `measurement_chain` (`resolvedDeviceDoc('east', { shot, measurement_chain })`).
 *
 * ★Added, never read back into the public tree: the merged document lives in
 * the gate's memory (and the page's localStorage the gate seeds).
 */
export function eastWithShot() {
  const ref = referenceDischarge();
  if (ref.why) return ref;
  return { why: `${ref.path} — ${EST2_UNPAIRED}` };
}

/**
 * Install EAST-with-shot as an imported device in every page of `ctx`:
 * `{ doc }` on success, `{ why }` (nothing seeded) when an input is missing.
 * ★For the page gates whose bars fit or solve on the machine's reference
 * discharge (analysis, recon, closure, handoff, recon-slices).
 */
export async function seedEastWithShot(ctx) {
  const e = eastWithShot();
  if (e.why) return e;
  await seedDeviceDocs(ctx, { east: e.doc });
  return e;
}

/** The one-line skip message a gate prints. */
export function skipMessage(gate, why) {
  return `跳过 ${gate}：${why}`;
}
