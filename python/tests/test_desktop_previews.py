"""The desktop shell previews are generated artifacts, and 16:9, and scalable.

``docs/figures/desktop-*.svg`` are drawn by ``tools/make-desktop-preview.py``
and committed.  Three things can go wrong without anything turning red, and
each is one assertion here:

  THE FILE DRIFTS FROM ITS GENERATOR.  A figure edited by hand, or a generator
  changed without a re-run, leaves a drawing of the layout somebody argued for
  two revisions ago on the page — and `FYL-DESIGN-11` cites its numbers.
  ``--check`` is the same shape as ``make-app-pages.mjs --check``.

  THE BOX STOPS BEING 16:9.  16:9 is not decoration here: it is the desktop
  viewer's own default measure, and the fold line these drawings argue about
  is 900 px OF THAT BOX (V-13).  A preview at some other ratio is a preview of
  a different claim.

  MARKDOWN LEAKS INTO A LABEL.  These strings sit next to prose that IS
  Markdown, and ``**bold**`` / backticks were copied across twice; SVG paints
  them literally and nothing complains.  The generator now reads its own
  ``<text>`` nodes and refuses — asserted here so the guard cannot be dropped.

  THE FILE GROWS A FIXED SIZE.  ``width``/``height`` on the root give an SVG an
  intrinsic size, and it then stops scaling — which is precisely the property
  the ruling asked for (V-14).  This is easy to reintroduce, because the OTHER
  figure generator in this repo (``make-app-figures.py``) declares both by
  design; those are tall wireframes with a natural size and are not covered
  here.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "tools" / "make-desktop-preview.py"
FIGS = REPO / "docs" / "figures"
#: the five drawings FYL-DESIGN-11 embeds …
NAMES = ["desktop-shell", "desktop-data", "desktop-pulse-design",
         "desktop-model", "desktop-analysis",
         #: … and the four FYL-DESIGN-09 embeds.  Same generator on purpose:
         #: they carry the same shell, and two generators drawing it would be
         #: two shells (V-11 / V-12).
         "pd-config", "pd-design", "pd-sim", "pd-vocab"]


#: ★★2026-09-01：预览图 `docs/figures/desktop-*.svg` 与画它们的
#: `tools/make-desktop-preview.py` 都随各自的树移出了本仓（在 fylite_kernel）。
#: 这道闸问的是「图与生成器是否同步」——两样都不在，它无事可判。
pytestmark = pytest.mark.skipif(
    not GEN.is_file() or not FIGS.is_dir(),
    reason="桌面预览图与其生成器已移出本仓（tools/ 与 docs/figures 在 fylite_kernel）")


def test_every_preview_exists():
    missing = [n for n in NAMES if not (FIGS / f"{n}.svg").exists()]
    assert not missing, f"缺预览图：{missing} —— 跑 python {GEN.relative_to(REPO)}"


def test_previews_agree_with_their_generator():
    r = subprocess.run([sys.executable, str(GEN), "--check"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_no_markdown_leaks_into_a_label():
    """The generator refuses; this pins that it still does."""
    src = GEN.read_text(encoding="utf-8")
    assert 'Markdown 记号' in src, "生成器丢了 Markdown 守卫"
    for n in NAMES:
        body = (FIGS / f"{n}.svg").read_text(encoding="utf-8")
        for m in re.finditer(r"<text[^>]*>([^<]*)</text>", body):
            t = m.group(1)
            assert "**" not in t and "`" not in t, f"{n}.svg: {t[:50]!r}"


def test_previews_are_16_by_9_and_have_no_intrinsic_size():
    for n in NAMES:
        head = (FIGS / f"{n}.svg").read_text(encoding="utf-8")[:400]
        m = re.search(r'viewBox="0 0 (\d+) (\d+)"', head)
        assert m, f"{n}.svg: 根元素没有 viewBox"
        w, h = int(m.group(1)), int(m.group(2))
        assert w * 9 == h * 16, f"{n}.svg: {w}×{h} 不是 16:9"
        root = head.split(">", 1)[0]
        assert " width=" not in root and " height=" not in root, (
            f"{n}.svg: 根元素带了 width/height，它就不再随容器缩放了（V-14）")
