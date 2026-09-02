"""Small shared helpers for the engine package — no concern of its own.

Anything here is used by two or more engine modules and is too small to
deserve a module of its own: keeping ONE copy is the whole point.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path) -> str | None:
    """Streaming SHA-256 of a file, or ``None`` if it is missing/unreadable."""
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
