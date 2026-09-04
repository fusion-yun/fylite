"""The front-end design previews (`FYL-DESIGN-18`) are generated, 16:9, scalable.

``docs/figures/fe-*.svg`` are drawn by ``tools/make-frontend-design-figures.py``
and committed.  The three failure modes are the ones ``test_desktop_previews.py``
names for the shell previews — drift from the generator, a box that is not
16:9, Markdown leaking into a label, a root that grows a fixed size — and the
assertions are the same shape.  ★The generator IMPORTS the shell generator and
calls its ``strip()``; two files drawing the shell would be two shells
(`FYL-DESIGN-11` V-11 / V-12), so a divergence there is a drift here.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "tools" / "make-frontend-design-figures.py"
SHELL_GEN = REPO / "tools" / "make-desktop-preview.py"
FIGS = REPO / "docs" / "figures"
NAMES = ["fe-input-page", "fe-sources", "fe-geometry-edit", "fe-composite-2d",
         "fe-profiles", "fe-workbench", "fe-run-checkpoint", "fe-report"]

pytestmark = pytest.mark.skipif(
    not GEN.is_file() or not SHELL_GEN.is_file() or not FIGS.is_dir(),
    reason="预览图生成器或图目录不在本仓")


def test_every_preview_exists():
    missing = [n for n in NAMES if not (FIGS / f"{n}.svg").exists()]
    assert not missing, f"缺预览图：{missing} —— 跑 python {GEN.relative_to(REPO)}"


def test_previews_agree_with_their_generator():
    r = subprocess.run([sys.executable, str(GEN), "--check", "-d", str(FIGS)],
                       capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr


def test_no_markdown_leaks_into_a_label():
    for n in NAMES:
        svg = (FIGS / f"{n}.svg").read_text(encoding="utf-8")
        for m in re.finditer(r"<text[^>]*>(.*?)</text>", svg, re.S):
            assert "**" not in m.group(1) and "`" not in m.group(1), (n, m.group(1)[:60])


def test_previews_are_16_by_9_and_have_no_intrinsic_size():
    for n in NAMES:
        svg = (FIGS / f"{n}.svg").read_text(encoding="utf-8")
        root = svg[:svg.index(">") + 1]
        vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', root)
        assert vb, (n, root)
        w, h = int(vb.group(1)), int(vb.group(2))
        assert abs(w / h - 16 / 9) < 1e-6, (n, w, h)
        assert " width=" not in root and " height=" not in root, (n, root)
