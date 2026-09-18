// Gate for the DOCUMENT face's typography.
//
// A stylesheet is the one place in this app where a change can be wrong without
// anything breaking: nothing throws, no gate goes red, the page just gets a
// little harder to read.  That is exactly how the document face ended up with
// TEN font sizes between 12 and 17 px — 12.5, 13.5, 14.5, 15.5 among them —
// spanning a factor of 1.42 in total, with `h3` SMALLER than the body text it
// was supposed to head.  Nobody decided that; it accumulated, half a pixel at a
// time.  This gate is what stops it accumulating again.
//
// It is a plain text check over the two stylesheets — no browser, no DOM.  What
// it asserts is only what was actually decided (docs/note/
// app-typography.md); it does not have an opinion about anything else.
//
//   node tests/validate-typography.mjs

import { readFileSync } from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
const SITE = HERE + '../assets/';

let bad = 0;
const fail = (m) => { console.log('  FAIL ' + m); bad++; };
const ok = (m) => console.log('  ok   ' + m);

const css = {
  'style.css': readFileSync(SITE + 'style.css', 'utf8'),
  'site.css': readFileSync(SITE + 'site.css', 'utf8'),
};
// comments carry prose that talks ABOUT the old values ("was #b4600a", "650")
const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '');

// --- 1. the type scale ----------------------------------------------------
//
// 16 x 1.2^n = 13 / 16 / 19 / 23, plus 14 for tables — one deliberate member off
// the scale, because 13 px Chinese in a four-column table is too small to read
// and 16 px bursts the columns.  The INSTRUMENT face (`.panel`, `.toolbar`,
// readouts, figure captions) is not covered: 12-13 px there is right for what it
// is, and this gate has no business tidying it.

const SCALE = new Set([13, 14, 16, 19, 23]);
{
  const src = strip(css['site.css']);
  const offenders = [];
  //: every rule whose selector mentions `.doc` — that IS the document face
  for (const m of src.matchAll(/([^{}]*\.doc[^{}]*)\{([^}]*)\}/g)) {
    const [sel, body] = [m[1].trim().replace(/\s+/g, ' '), m[2]];
    for (const f of body.matchAll(/font-size:\s*([\d.]+)px/g))
      if (!SCALE.has(Number(f[1]))) offenders.push(`${sel} -> ${f[1]}px`);
  }
  if (offenders.length)
    fail(`document-face sizes off the scale {${[...SCALE].join(', ')}}: `
         + offenders.join('; '));
  else ok(`document-face font sizes all on the scale {${[...SCALE].join(', ')}}`);
}

// --- 2. no synthesised CJK weights ----------------------------------------
//
// Source Han Sans / Noto Sans CJK ship 250/300/350/400/500/700/900 and Microsoft
// YaHei ships only 400 and 700.  A run asked for 550 or 650 is snapped or
// SYNTHESISED — the browser strokes the glyph wider, and a dense character at
// 13-16 px turns to mud.  Three weights, all of them real.

const WEIGHTS = new Set(['400', '500', '600', '700', 'normal', 'bold', 'inherit']);
{
  const offenders = [];
  for (const [f, src] of Object.entries(css))
    for (const m of strip(src).matchAll(/font-weight:\s*([a-z0-9]+)/g))
      if (!WEIGHTS.has(m[1])) offenders.push(`${f}: ${m[1]}`);
  if (offenders.length)
    fail(`font weights a CJK family cannot supply: ${offenders.join(', ')}`);
  else ok('font weights are 400 / 500 / 600 / 700 only');
}

// --- 3. document tables are prose tables ----------------------------------
//
// `style.css` sets `text-align: right` on every cell, which is correct for ITS
// tables — they are readouts of numbers.  Applied to the capability table it set
// three columns of Chinese prose flush right, ragged left.  A `.doc` rule must
// put them back, and must not be undone.

{
  const src = strip(css['site.css']);
  const cell = [...src.matchAll(/([^{}]*\.doc[^{}]*(?:td|th)[^{}]*)\{([^}]*)\}/g)];
  const lefts = cell.filter((m) => /text-align:\s*left/.test(m[2]));
  const rights = cell.filter((m) => /text-align:\s*right/.test(m[2])
                                 && !/\.num/.test(m[1]));
  if (!lefts.length)
    fail('no `.doc` rule sets text-align: left on cells — prose would be ragged left');
  else if (rights.length)
    fail(`a .doc cell rule still right-aligns: ${rights.map((m) => m[1].trim())}`);
  else ok('document-table cells are left-aligned; only `.num` is right-aligned');
}

// --- 4. the measure is expressed in a unit that means something for Han ----
//
// `ch` is the advance width of the character `0`.  `96ch` was meant to say
// "96 characters" and measured out to 58 Han characters per line.

{
  const src = strip(css['site.css']);
  const chs = [...src.matchAll(/([^{}]*\.(?:doc|intro|lead|bound|scope)[^{}]*)\{([^}]*max-width:\s*[\d.]+ch[^}]*)\}/g)];
  if (chs.length)
    fail(`measure written in \`ch\`, which is the width of a zero: ${chs.map((m) => m[1].trim())}`);
  else ok('the measure is set in `rem` / `em`, not `ch`');
}

// --- 5. one column edge ---------------------------------------------------
{
  const src = strip(css['site.css']);
  if (!/--measure:\s*\d+rem/.test(src))
    fail('`.doc` declares no `--measure` column');
  else if (!/max-width:\s*var\(--measure\)/.test(src))
    fail('`--measure` is declared but no text element uses it');
  else ok('the text column is one `--measure`, shared by every text element');
}

// --- 6. contrast ----------------------------------------------------------
//
// Recomputed here rather than trusted: `--muted` is normal-size text on these
// pages (table heads, notes, card subtitles), so it owes WCAG AA 4.5:1 against
// BOTH surfaces it sits on — and the light palette is the one that failed.

const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.substr(i, 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m);
  return (x + 0.05) / (y + 0.05);
};
{
  const src = css['style.css'];
  //: the light palette is bare `:root {`; the dark ones are inside a media
  //: query or an attribute selector
  const block = src.match(/:root\s*\{([\s\S]*?)\}/)[1];
  const tok = {};
  for (const m of block.matchAll(/(--[a-z]+):\s*(#[0-9a-f]{6})/g)) tok[m[1]] = m[2];
  let worst = 99, worstName = '';
  for (const name of ['--fg', '--muted', '--accent', '--warn'])
    for (const surface of ['--bg', '--panel']) {
      const r = ratio(tok[name], tok[surface]);
      if (r < worst) { worst = r; worstName = `${name} on ${surface}`; }
      if (r < 4.5)
        fail(`light palette: ${name} on ${surface} is ${r.toFixed(2)}:1, under WCAG AA 4.5`);
    }
  if (!bad) ok(`light palette clears WCAG AA everywhere (worst ${worstName} ${worst.toFixed(2)}:1)`);
}

console.log(bad ? `\nFAILED (${bad})` : '\nPASS');
process.exit(bad ? 1 : 0);
