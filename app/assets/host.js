// Which host is serving this page — the published site, or the desktop viewer?
//
// The single-file viewer (`fylite`) serves the SAME BYTES as the website:
// `app/` is embedded in the executable verbatim, so a page cannot be built
// differently for the two.  Anything that must differ has to be decided at
// runtime, and this is the one place that decides it.  The answer is published
// as `data-fy-host` on <html>, so the difference can be expressed in CSS
// instead of in DOM surgery scattered across the pages.
//
//     :root[data-fy-host="desktop"] footer .qr { display: none; }
//
// ★★THE TEST IS «DOES A REQUEST FACE ANSWER», NOT «WHAT IS THE HOSTNAME».
// `127.0.0.1` is equally true of `myst start`, of `python3 -m http.server`
// and of the desktop viewer, so the hostname on its own distinguishes
// nothing — a page that trusted it would call a local site preview a desktop
// viewer.  What only the viewer has is `/api/health`: it answers even with no
// `--mdsip` attached (`ok:true`, `mdsip:null`), because 「没配」 is not
// 「不能用」.
//
// ★The hostname is still used, but only as a NEGATIVE filter and only to
// avoid a pointless request: the viewer binds the loopback address and that
// is not configurable (`rust/fylite/src/bin/app/main.rs` states it as one of
// its boundaries), so a page served from anywhere else cannot be it.  Off
// loopback we therefore skip the probe entirely — the published site makes no
// request at all and its footer never flickers.  On loopback the endpoint,
// not the hostname, is what decides.
(function (root) {
  'use strict';
  if (typeof document === 'undefined') return;

  //: taken from THIS script's own URL, like `site.js` does, so it is right
  //: whether the page sits at the site root or under `pages/`
  var ROOT = (function () {
    var s = document.currentScript && document.currentScript.src;
    return s ? s.replace(/assets\/host\.js(\?.*)?$/, '') : '';
  })();

  var html = document.documentElement;
  //: ★the default is «site», and deliberately so: it is the case that is
  //: published, and defaulting the other way would hide the QR for a frame on
  //: every reader's first paint in order to be tidy about the rare one.
  html.setAttribute('data-fy-host', 'site');

  var h = location.hostname;
  var loopback = h === '127.0.0.1' || h === 'localhost' || h === '::1' || h === '[::1]';
  if (!loopback) return;

  try {
    fetch(ROOT + 'api/health', { headers: { accept: 'application/json' } })
      .then(function (r) { if (r.ok) html.setAttribute('data-fy-host', 'desktop'); })
      //: no gateway here — that is a static server, i.e. the site
      .catch(function () {});
  } catch (e) { /* no fetch: treat as the site, which is the safe default */ }

  root.FyHost = {
    /** 'site' | 'desktop' — the answer as it stands right now. */
    kind: function () { return html.getAttribute('data-fy-host'); },
  };
})(typeof self !== 'undefined' ? self : globalThis);
