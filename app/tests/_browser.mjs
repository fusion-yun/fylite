// How every browser gate finds a browser.
//
// ★Two things are the OPERATOR's, not the repository's: playwright itself
// (a developer tool, not a dependency of the shipped app) and the chromium
// it drives.  The first has been resolved from `--playwright` /
// `$PLAYWRIGHT_PATH` since these gates were written; the second was not
// resolved at all, and playwright pins one chromium BUILD per release — so
// an operator whose install carries a different build was told to download
// a second copy of a browser they already have, and every browser gate died
// before its first assertion.  `--chrome <binary>` / `$CHROME_PATH` says
// which one to use; with neither, playwright's own default applies and
// nothing changes for a matching install.
//
//   import { browser } from './_browser.mjs';
//   const br = await browser();          // same options as chromium.launch()

import { createRequire } from 'node:module';

/** The value of `--flag x`, else `$ENV`, else undefined. */
export function flag(name, env) {
  const i = process.argv.indexOf('--' + name);
  return i > 0 ? process.argv[i + 1] : (env ? process.env[env] : undefined);
}

/** playwright's `chromium`, resolved from wherever the operator has it. */
export function chromium() {
  const pw = flag('playwright', 'PLAYWRIGHT_PATH');
  try {
    const req = createRequire(pw ? pw.replace(/\/*$/, '/') + 'x.js'
                                 : import.meta.url);
    return req('playwright').chromium;
  } catch (e) {
    console.error('找不到 playwright —— 用 --playwright <装有 playwright 的目录> ' +
                  '或设 $PLAYWRIGHT_PATH');
    process.exit(2);
  }
}

/** A launched chromium, honouring `--chrome` / `$CHROME_PATH`. */
export function browser(opts = {}) {
  const bin = flag('chrome', 'CHROME_PATH');
  return chromium().launch(bin ? { executablePath: bin, ...opts } : opts);
}

//: ★★`returningVisitor` WAS HERE and is gone (2026-09-01, with the case
//: menus themselves).  It seeded `fylite:seen:<page>:<bar>` so that a fresh
//: browser context would not be a first visit and would therefore not have
//: a bar's INITIAL CASE applied over the configuration the gate was about to
//: build.  No bar applies a case any more — every one opens on its factory
//: settings — so a fresh context IS the state these gates assumed, and the
//: seeding had nothing left to prevent.
