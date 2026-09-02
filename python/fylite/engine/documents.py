"""Document / signal / channel-map mechanics (generic data plane).

Document loading, timed signal evaluation, and the bidirectional
channel-map applier.  The domain CONTENT — which paths, which counts,
which units — is a declarative table owned by the domain module
(:mod:`fylite.fyo` for EAST).
"""

from __future__ import annotations

import json
from pathlib import Path


# --------------------------------------------------------------------------- #
# Document / signal / channel-map mechanics (generic data-plane machinery)
#
# The generic half of the measurement data plane: document loading, timed
# signal evaluation, and a small **bidirectional channel-map applier**.  The
# domain CONTENT — which paths, which counts, which unit conventions — is a
# declarative table owned by the domain module (fylite.device for EAST);
# nothing here knows what a flux loop is.  The table grammar is deliberately
# shaped after the dict-canonical spirit of SpData ``sp:read`` so that, when
# the three-key expression form is finalized upstream (SP-REPORT-15 OI-3 /
# SPD-ADR-104), a table serializes into the DataArtifact's ``sp:read`` entries
# mechanically instead of being rewritten.
#
# Table grammar — a tuple of entries:
#
#   {"target": <flat key>,
#    "sources": [ {"path": (seg, ...),        # str key | int index | "*" fan-out
#                  "scale": float,            # optional multiplier
#                  "scalar_only": bool},      # accept only a bare number
#                 ... ],                      # tried in order (fallback chain)
#    "count": int,                            # required with a "*" segment
#    "label": str, "note": str,               # error-message identity
#    "missing": str,                          # error when no source yields
#    "units": {"key": ..., "default": ...,    # optional units branch:
#              "per_channel": {unit: callable},   # vector multiplier factory
#              "passthrough": (...aliases),
#              "expose": <result key>},       # resolved units echoed here
#    "invert": {"path": (...), "scale": float}}   # inverse direction; default
#                                                 # = first "*"-bearing source
# --------------------------------------------------------------------------- #

def load_document(path):
    """Load a JSON / JSON-LD / YAML document by suffix."""
    path = Path(path)
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml
        return yaml.safe_load(text)
    return json.loads(text)


def signal_at(sig, time_s: float, what: str, *, error=ValueError) -> float:
    """Evaluate a ``{data[, time]}`` node (or bare scalar) at ``time_s``,
    linearly interpolating array data on its time base."""
    import numpy as np
    if sig is None:
        raise error(f"missing signal: {what}")
    if isinstance(sig, (int, float)):
        return float(sig)
    if isinstance(sig, dict):
        data = np.atleast_1d(np.asarray(sig.get("data"), dtype=float))
        if data.size == 1:
            return float(data[0])
        t = sig.get("time")
        if t is None:
            raise error(f"{what}: array data ({data.size}) without a time base")
        t = np.asarray(t, dtype=float)
        if t.shape != data.shape:
            raise error(f"{what}: time shape {t.shape} != data shape "
                        f"{data.shape}")
        #: ★``kernel`` was never imported in this module, so **every timed
        #: signal** — the whole reason this branch exists — raised
        #: ``NameError`` instead of interpolating.  Nothing caught it because
        #: the shipped measurement documents carry per-slice scalars; a
        #: document with a real time base would have hit it on the first
        #: channel.  Imported here rather than at module scope: the engine's
        #: import surface stays stdlib (DE-COMP-03).
        from .. import kernel
        return float(kernel.interp(time_s, t, data))
    arr = np.atleast_1d(np.asarray(sig, dtype=float))
    if arr.size == 1:
        return float(arr[0])
    raise error(f"{what}: array without time base; wrap as "
                "{{data: [...], time: [...]}}")


def _path_label(path, i=None) -> str:
    parts = []
    for seg in path:
        if seg == "*":
            parts[-1] += f"[{i}]" if i is not None else "[*]"
        elif isinstance(seg, int):
            parts[-1] += f"[{seg}]"
        else:
            parts.append(str(seg))
    return ".".join(parts)


class _SourceMiss(Exception):
    """Internal: this source does not apply — try the next in the chain."""


def _walk(doc, path):
    node = doc
    for k, seg in enumerate(path):
        if seg == "*":
            if not isinstance(node, list):
                raise _SourceMiss()
            rest = path[k + 1:]
            return [(_i, item) for _i, item in enumerate(node)], rest
        if isinstance(seg, int):
            if not isinstance(node, list) or len(node) <= seg:
                raise _SourceMiss()
            node = node[seg]
        else:
            if not isinstance(node, dict) or seg not in node:
                raise _SourceMiss()
            node = node[seg]
    return node, None


def apply_channel_map(table, doc: dict, time_s: float, *,
                      error=ValueError) -> dict:
    """Forward direction: document -> flat values dict, per the table.
    Fallback chains are tried in order; malformed signals raise ``error``
    (they do not fall through); fan-out entries enforce ``count``."""
    out = {}
    for entry in table:
        got = None
        for src in entry["sources"]:
            path, scale = src["path"], src.get("scale", 1.0)
            try:
                node, rest = _walk(doc, path)
            except _SourceMiss:
                if "count" in entry:
                    # a missing fan-out container counts as zero channels
                    raise error(
                        f"{entry['label']} needs exactly {entry['count']} "
                        f"channels ({entry['note']}), got 0")
                continue
            if rest is not None:  # fan-out
                items = node
                if len(items) != entry["count"]:
                    raise error(
                        f"{entry['label']} needs exactly {entry['count']} "
                        f"channels ({entry['note']}), got {len(items)}")
                vals = []
                for i, item in items:
                    leaf, _ = ((item, None) if not rest
                               else _walk_leaf(item, rest, error,
                                               _path_label(path, i)))
                    vals.append(signal_at(
                        leaf, time_s, _path_label(path, i),
                        error=error) * scale)
                got = vals
            else:
                if src.get("scalar_only") and not isinstance(node,
                                                             (int, float)):
                    continue
                got = signal_at(node, time_s, _path_label(path),
                                error=error) * scale
            break
        if got is None:
            raise error(entry["missing"])
        units = entry.get("units")
        if units is not None:
            unit = str(doc.get(units["key"], units["default"]))
            if unit in units.get("passthrough", ()):
                pass
            elif unit in units.get("per_channel", {}):
                vec = units["per_channel"][unit]()
                got = [v * w for v, w in zip(got, vec)]
            else:
                allowed = sorted(set(units.get("per_channel", {}))
                                 | set(units.get("passthrough", ())))
                raise error(f"{units['key']} must be one of {allowed}, "
                            f"got {unit!r}")
            if "expose" in units:
                out[units["expose"]] = unit
        out[entry["target"]] = got
    return out


def _walk_leaf(item, rest, error, label):
    """Navigate the post-fan-out remainder of a path inside one item."""
    node = item
    for seg in rest:
        if isinstance(node, dict):
            node = node.get(seg)
        else:
            node = None
        if node is None:
            break
    return node, None


def invert_channel_map(table, values: dict) -> dict:
    """Inverse direction: flat values dict -> nested plain payload, per the
    table's ``invert`` specs (default: the first fan-out source path)."""
    doc: dict = {}

    def _set(path, value):
        node = doc
        for seg in path[:-1]:
            node = node.setdefault(seg, {})
        node[path[-1]] = value

    for entry in table:
        if entry["target"] not in values:
            continue
        v = values[entry["target"]]
        inv = entry.get("invert")
        if inv is None:
            inv = next(s for s in entry["sources"] if "*" in s["path"])
        path, scale = inv["path"], inv.get("scale", 1.0)
        if "*" in path:
            k = path.index("*")
            head, leaf = path[:k], path[k + 1:]
            items = [({leaf[0]: float(x)} if leaf else float(x)) for x in v]
            _set(head, items)
        elif isinstance(path[-1], int):
            assert path[-1] == 0, "invert supports only [0] placement"
            _set(path[:-1], [float(v) * scale])
        else:
            _set(path, float(v) * scale)
    return doc
