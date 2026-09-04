#!/usr/bin/env node
// Transcribe a function page's hand-written controls into a control
// vocabulary, and leave mount points behind (`FYL-DESIGN-18` U-1 / U-2, stage U0).
//
//     node tools/transcribe-form-vocab.mjs model            # writes both files
//     node tools/transcribe-form-vocab.mjs model --dry-run  # prints the vocabulary only
//
// ★ONE-SHOT, BY DESIGN.  This script reads `app/pages/<page>.html`, lifts every
// `.ctl` control (range · select) and every checkbox label into
// `app/assets/vocab-<page>.js`, and rewrites the page so that each control is a
// `<… data-form="<name>">` mount that `assets/form.js` fills at load.  After it
// has run once the page carries no controls to transcribe, and the vocabulary
// file is the SOURCE from then on: edit that file, not this script and not the
// page.  Running it again on a mounted page finds nothing and changes nothing.
//
// ★What it can and cannot know.  A page carries `min` / `max` / `step` / `value`,
// an i18n key and the unit written inside the label text (`[keV]`); it does NOT
// carry the parameter's IRI (`code/<cap>#<name>`), its tier (A / B / C), or its
// group in the sense of U-3.  Those fields are written as `[TBD]` so the gap
// is visible in the data rather than papered over (`FYL-DESIGN-18` G-1).
//
// ★Why the mounts keep the page's own structure.  Stage U0 generates the
// CONTROLS, not the panels: headings, notes, folded boxes (`hidden`) and the
// order of things stay in the page, where `-10` / `-12` decided them.  U-3
// (the vocabulary decides grouping) is stage U2, when the vocabulary comes
// from the kernel's code table.
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = join(HERE, '..', 'app');
const page = process.argv[2];
const dry = process.argv.includes('--dry-run');
if (!page) { console.error('usage: transcribe-form-vocab.mjs <page> [--dry-run]'); process.exit(2); }

const srcPath = join(APP, 'pages', `${page}.html`);
let html = readFileSync(srcPath, 'utf8');
const prefix = `${page}-`;

//: the attribute string of a tag (everything after the tag name) → {name: value}
const attrsOf = (attrStr) => {
  const out = {};
  for (const m of attrStr.matchAll(/([a-zA-Z][\w-]*)(?:="([^"]*)")?/g))
    out[m[1]] = m[2] === undefined ? '' : m[2];
  return out;
};
const unitOf = (label) => {
  const m = label.match(/\s*\[([^\]]+)\]\s*$/);
  return m ? m[1] : '';
};
const numType = (a) => {
  const ints = ['min', 'max', 'step'].every((k) => a[k] !== undefined && /^-?\d+$/.test(a[k]));
  return ints ? 'integer' : 'double';
};

const params = [];
const seen = new Set();
const nameOf = (id) => {
  if (!id.startsWith(prefix)) throw new Error(`control id ${id} does not start with ${prefix}`);
  const n = id.slice(prefix.length);
  if (seen.has(n)) throw new Error(`duplicate control ${id}`);
  seen.add(n);
  return n;
};

// --- 1. `.ctl` blocks: range and select ------------------------------------
// A `.ctl` never nests another <div>, so the first `</div>` closes it; the
// `.ctl checks` groups contain only <label>s and are handled in step 2.
html = html.replace(/([ \t]*)<div class="ctl( [^"]*)?"([^>]*)>([\s\S]*?)<\/div>/g,
  (whole, indent, extraCls, divAttrs, inner) => {
    if (/checks/.test(extraCls || '')) return whole;              // step 2
    const range = inner.match(/<input type="range"([^>]*)>/);
    const select = inner.match(/<select id="([^"]+)">([\s\S]*?)<\/select>/);
    const check = inner.match(/<label( class="chk")?><input type="checkbox"([^>]*)>\s*<span data-i18n="([^"]+)">([\s\S]*?)<\/span><\/label>/);
    const attrs = attrsOf(divAttrs);
    if (range) {
      const a = attrsOf(range[1]);
      const lab = inner.match(/<label><span data-i18n="([^"]+)">([\s\S]*?)<\/span>\s*<span class="val" id="([^"]+)"><\/span><\/label>/)
        || inner.match(/<label><span id="([^"]+)"><\/span>\s*<span class="val" id="([^"]+)"><\/span><\/label>/);
      if (!lab) throw new Error(`range ${a.id}: label shape not recognised`);
      const p = { name: nameOf(a.id), id: a.id, kind: 'range', type: numType(a),
                  min: +a.min, max: +a.max, step: +a.step };
      if (a.value !== undefined) p.value = +a.value;
      if (lab.length === 4) { p.i18n = lab[1]; p.label = lab[2]; p.units = unitOf(lab[2]); p.readout = lab[3]; }
      else { p.label_id = lab[1]; p.readout = lab[2]; p.units = '[TBD]'; }
      if (Object.keys(attrs).length) p.attrs = attrs;
      p.iri = '[TBD]'; p.tier = '[TBD]';
      params.push(p);
      return `${indent}<div data-form="${p.name}"></div>`;
    }
    if (select) {
      const lab = inner.match(/<label for="([^"]+)" data-i18n="([^"]+)">([\s\S]*?)<\/label>/);
      if (!lab || lab[1] !== select[1]) throw new Error(`select ${select[1]}: label shape not recognised`);
      const choices = [...select[2].matchAll(/<option value="([^"]*)" data-i18n="([^"]+)"><\/option>/g)]
        .map((m) => ({ value: m[1], i18n: m[2] }));
      const p = { name: nameOf(select[1]), id: select[1], kind: 'select', type: 'enum',
                  i18n: lab[2], label: lab[3], choices, iri: '[TBD]', tier: '[TBD]' };
      if (Object.keys(attrs).length) p.attrs = attrs;
      params.push(p);
      return `${indent}<div data-form="${p.name}"></div>`;
    }
    if (check) {
      const a = attrsOf(check[2]);
      const p = { name: nameOf(a.id), id: a.id, kind: 'checkbox', type: 'boolean',
                  checked: a.checked !== undefined, i18n: check[3], label: check[4],
                  wrap: 'ctl', iri: '[TBD]', tier: '[TBD]' };
      if (check[1]) p.label_class = 'chk';
      params.push(p);
      return `${indent}<div data-form="${p.name}"></div>`;
    }
    throw new Error(`.ctl block not recognised:\n${whole.slice(0, 200)}`);
  });

// --- 2. bare checkbox labels (inside `.ctl checks`, or a folded box) --------
html = html.replace(/([ \t]*)<label><input type="checkbox"([^>]*)>\s*<span data-i18n="([^"]+)">([\s\S]*?)<\/span><\/label>/g,
  (whole, indent, inputAttrs, key, label) => {
    const a = attrsOf(inputAttrs);
    const p = { name: nameOf(a.id), id: a.id, kind: 'checkbox', type: 'boolean',
                checked: a.checked !== undefined, i18n: key, label, iri: '[TBD]', tier: '[TBD]' };
    params.push(p);
    return `${indent}<span data-form="${p.name}"></span>`;
  });

const left = html.match(/<(input|select)\b[^>]*>/g) || [];
if (left.length) throw new Error(`controls left untranscribed:\n  ${left.join('\n  ')}`);

const header = `// GENERATED ONCE by tools/transcribe-form-vocab.mjs from pages/${page}.html
// (${new Date().toISOString().slice(0, 10)}) — and the SOURCE from then on.  Edit this file, not the page:
// the page carries only \`data-form\` mounts, and assets/form.js draws each
// control from the entry below that shares its name (FYL-DESIGN-18 U-1 / U-2).
//
// ★\`[TBD]\` is a value, not a placeholder to be quietly filled: the IRI
// (\`code/<cap>#<name>\`), the tier (A / B / C) and the group are what the
// kernel's code table will declare (FYL-DESIGN-16 K-2, as amended by
// FYL-DESIGN-18 §十二); a page cannot know them, so it says so.  \`units\` were
// read out of the label text and are what the label says, no more.
// ★\`kind\` is the CONTROL, \`type\` is the parameter: U-2 maps one to the other
// and this file records both so the gate can check the mapping held.
(function () {
  'use strict';
  window.FyVocab = window.FyVocab || {};
  FyVocab.${page} = ${JSON.stringify({ page, code: '[TBD]', params }, null, 2)};
})();
`;

if (dry) { process.stdout.write(header); process.exit(0); }
writeFileSync(join(APP, 'assets', `vocab-${page}.js`), header);
writeFileSync(srcPath, html);
console.log(`${params.length} controls → app/assets/vocab-${page}.js; ${srcPath} now carries mounts only`);
