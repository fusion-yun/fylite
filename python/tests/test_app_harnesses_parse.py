"""Every browser validation harness must at least PARSE.

★★Why this exists.  ``app/tests/*.mjs`` are the gates for the browser side:
they drive the pages with Playwright and compare against the native kernel.
Nine of the fifteen could not be loaded by node at all — a ``SyntaxError``
before the first statement — and had been in that state for long enough
that the ABI-rename comments which caused it name four different ABI
versions.

The cause is one mechanical thing, repeated: each harness embeds a Python
program in a JS **template literal**, and a comment written in this
repository's house style puts module names in markdown backticks::

    const PY = `
    # ★`kernel.geo_surface`, not `fylite.geo` (converged at ABI 70).
    ...

The first backtick of that comment closes the template literal.  The prose is
right, the reference is right, and the file is dead.

★Nothing noticed because a harness that fails to load fails the same way as
one that was never run: silently, unless someone runs it by hand.  This
costs milliseconds, needs no browser and no kernel, and it is the smallest
statement that would have caught it — a file that cannot be parsed cannot be
a gate.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HARNESSES = sorted((Path(__file__).resolve().parents[2]
                    / "app" / "tests").glob("*.mjs"))

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not HARNESSES,
    reason="node or app/tests is not in this tree")


@pytest.mark.parametrize("src", HARNESSES, ids=lambda p: p.name)
def test_the_harness_parses(src: Path):
    r = subprocess.run(["node", "--check", str(src)],
                       capture_output=True, text=True)
    assert r.returncode == 0, (
        f"{src.name} does not parse, so it cannot gate anything:\n"
        + (r.stderr or r.stdout).strip()[:600]
        + "\n\nA backtick inside an embedded Python block closes the "
          "template literal it lives in — escape it as \\`.")
