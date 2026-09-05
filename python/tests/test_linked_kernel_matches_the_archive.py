"""The kernel linked into the runtime is the archive on disk — not last week's.

2026-09-05, measured: ``libfylite_runtime.so`` links the kernel's static archive, and
that copy carried the SAME version, ABI and interface digest as the installed ``.so``
while being a different build — eight gates went red on it and green on the ``.so``,
and nothing on either side could say why.  Version, ABI and digest are statements
about the interface; two builds of one version differ in code, not in interface.

So the runtime now carries the archive's own fingerprint (``kernel-static.json``,
embedded at link time) and this gate holds it against the json beside the archive
NOW.  A mismatch means: the kernel was rebuilt and the runtime was not — run the
public ``rust/build.sh`` again.  ★It is a gate on the BUILD ORDER, which is exactly
the thing a reader of two identical version strings cannot see.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fylite.io import fydoc

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_JSON = ROOT / "rust" / "kernel-lib" / "kernel-static.json"


def test_the_linked_kernel_is_the_archive_beside_the_runtime():
    try:
        linked = fydoc.linked_kernel()
    except Exception as exc:  # noqa: BLE001  — no data library here at all
        pytest.skip(f"no runtime library to ask: {exc}")
    if linked is None:
        pytest.skip("this runtime links no kernel (dlopen path only) — nothing to compare")
    if not ARCHIVE_JSON.is_file():
        pytest.skip(f"no archive fingerprint at {ARCHIVE_JSON} — the kernel's build.sh writes it")
    disk = json.loads(ARCHIVE_JSON.read_text(encoding="utf-8"))
    for key in ("kernel_version", "abi"):
        assert linked.get(key) == disk.get(key), (key, linked, disk)
    assert linked.get("sha256") == disk.get("sha256"), (
        f"the runtime links a kernel built {linked.get('built')} (sha {str(linked.get('sha256'))[:12]}…) "
        f"but the archive on disk is from {disk.get('built')} (sha {str(disk.get('sha256'))[:12]}…) — "
        "the kernel was rebuilt after the runtime.  Rebuild the runtime: bash rust/build.sh")
