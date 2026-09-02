"""Reader for JETTO's self-describing binary outputs (.jsp / .jst / .ex …).

The on-disk format, derived from the bytes of the files themselves (it is
self-describing, so no other source is needed):

* the file is a sequence of SECTIONS, each opened by ``*\\n*<name>\\n``;
* a section holds BLOCKS, each opened by an ASCII spec line
  ``#<dtype>;<nrows>;<npoints>;<label>;<nmeta>\\n`` followed by ``nmeta``
  ASCII metadata lines and then the payload — for ``char`` one text line,
  otherwise ``nrows`` runs of ``npoints`` big-endian values (``float`` 4
  bytes, ``double`` 8, ``int`` 4) with a ``\\n`` between runs;
* a label repeats once per output section (one section per written time
  point in a ``.jsp``), so stacking equal labels in file order yields the
  ``(nt, nx)`` array a profile is.

Endianness comes from the ``File Format`` block (``b``/``l``); everything
this repository has met is big-endian.

★This is what a JETTO run leaves when it does NOT write IMAS — the JET
case (job 101612) benchmarked in
``docs/note/jintrac-case04-101612-reproduction.md`` ships only
these.  The reader is deliberately minimal: labels → stacked float arrays,
metadata kept as text, nothing interpreted.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

_SPEC = re.compile(rb"#(\w+);(\d+);(\d+);([\w, \d\-\(\)/%.]+);(\d+)\n")
_SIZES = {b"float": (4, ">f4"), b"double": (8, ">f8"), b"int": (4, ">i4")}


def read(path) -> dict:
    """Parse one JETTO binary file.

    Returns ``{label: ndarray}`` — numeric blocks stacked ``(nt, npoints)``
    (``nt`` is how many sections carried the label), plus two side tables:
    ``"_meta"`` (label → list of metadata-line tuples) and ``"_text"``
    (label → list of the ``char`` payloads, e.g. ``File Format``).
    """
    raw = Path(path).read_bytes()
    data: dict[str, list[np.ndarray]] = {}
    meta: dict[str, list] = {}
    text: dict[str, list[str]] = {}
    swap = ">"
    pos = 0
    n = len(raw)
    while pos < n:
        if raw.startswith(b"*\n*", pos):            # section header
            pos = raw.index(b"\n", pos + 2) + 1
            continue
        m = _SPEC.match(raw, pos)
        if m is None:                                # tolerate stray bytes
            nxt = raw.find(b"\n#", pos)
            if nxt < 0:
                break
            pos = nxt + 1
            continue
        dtype, nrows, npts, label, nmeta = (
            m.group(1), int(m.group(2)), int(m.group(3)),
            m.group(4).decode("latin-1").strip(), int(m.group(5)))
        pos = m.end()
        lines = []
        for _ in range(nmeta):
            e = raw.index(b"\n", pos)
            lines.append(raw[pos:e].decode("latin-1"))
            pos = e + 1
        scale = 1.0
        if lines:
            meta.setdefault(label, []).append(tuple(lines))
            #: metadata layout observed: (units, description, scale, xbase, …)
            if len(lines) >= 3:
                try:
                    scale = float(lines[2])
                except ValueError:
                    scale = 1.0
        if dtype == b"char":
            e = raw.index(b"\n", pos)
            val = raw[pos:e].decode("latin-1")
            text.setdefault(label, []).append(val)
            pos = e + 1
            if val in ("b", "l") and label == "File Format":
                swap = {"b": ">", "l": "<"}[val]
            continue
        size, np_dtype = _SIZES[dtype]
        rows = []
        for r in range(nrows):
            buf = raw[pos:pos + npts * size]
            rows.append(np.frombuffer(buf, np_dtype.replace(">", swap)))
            pos += npts * size
            if r + 1 < nrows and raw.startswith(b"\n", pos):
                pos += 1
        block = np.vstack(rows) if len(rows) > 1 else rows[0]
        data.setdefault(label, []).append(block * scale)
        # payload may or may not be newline-terminated; resync on the next
        # marker rather than assuming
        while pos < n and not (raw.startswith(b"#", pos)
                               or raw.startswith(b"*\n*", pos)):
            pos += 1
    out: dict = {}
    for label, blocks in data.items():
        try:
            out[label] = np.squeeze(np.array(blocks, float))
        except ValueError:                            # ragged: keep list
            out[label] = blocks
    out["_meta"] = meta
    out["_text"] = text
    return out
