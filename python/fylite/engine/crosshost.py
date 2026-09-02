"""A-7 — run one declared scenario entry on BOTH kernel builds and compare.

★★"单核双宿主" is the claim this repository makes about itself: the browser
and the command line are two faces of ONE kernel, not two implementations
that agree.  Everything else in the tree checks a slice of that.  This checks
it end to end, on the only surface where both hosts speak the same language —
the DECLARED scenario entries (``rust/fylite/src/fyo.rs``, ``@fyo-entry``).

Three things make it a claim rather than a comparison:

1. **What must be IDENTICAL is declared, not decided here.**  Two builds do
   not produce bit-identical floats and are not meant to (native and wasm
   differ in float codegen — fma contraction, libm — measured 5.5e-15 on a
   hostile march).  So "the same answer" cannot mean "the same bytes" for
   every row.  It MUST mean exactly that for the counts and the flags, and
   which outputs those are is a fact about the physics: it lives in
   ``ENTRY_OUT_KIND`` in the kernel and is generated into both hosts.

2. **The counts and flags are HASHED.**  A digest is the right instrument
   for「完全一样」: it does not have a tolerance to argue about, and two
   hosts whose discrete decisions differ took different paths — no float
   band excuses that, and none is offered.

3. **A difference that remains must be EXPLAINED BY THE RECORD** (A-7's own
   words).  :func:`compare` returns the environment fingerprint of each side
   beside the numbers, and ``env_fingerprint`` names the host, so a report
   says which build produced which figure rather than leaving a reader to
   assume.

★Scope, stated rather than implied.  An entry is a single kernel symbol, so
both hosts can call it — and that is the KERNEL half of a tool, not the whole
of it.  ``model.evolve`` assembles a Miller metric and initial profiles
before calling ``evolve_heat``; that assembly is host code by design (the
"双薄面" ruling) and is NOT what this compares.  What this compares is that
the sunk core answers the same on both builds.

★And today exactly ONE tool declares such a core (``evolve`` →
``evolve_heat``).  ``zerod`` / ``transport`` / ``profit`` / ``vstab`` exist as
declared entries — the browser calls them that way — but their Python tools
reach the same kernel code through the flat exports, so they carry no
``kernel_entry`` and :func:`for_ledger` will not claim them.  A tool that is
assembly around many kernel calls (``discharge``, ``reconstruction``,
``coupled``) is refused by name rather than reported as agreeing because
nobody ran it twice.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from .. import _paths

__all__ = ["out_kinds", "run_native", "run_wasm", "discrete_digest",
           "compare", "for_ledger", "WASM"]

#: the browser's build, as shipped
WASM = _paths.PKG.parent.parent / "app/assets/fylite_rs.wasm"

#: ★a key the declaration does not mention is `real` — the safe default: it
#: is compared, just not hashed.  Making the default `count` would silently
#: promote a new float row into an exactness claim nobody made.
_DEFAULT_KIND = "real"


def out_kinds(entry: str) -> dict:
    """``{output key: kind}`` for one entry, from the kernel's declaration.

    ★The generated block reuses the four-column block schema, so its columns
    arrive named ``key``/``shape``/``units``/``gloss`` while they actually
    carry ``entry``/``key``/``kind``/``why``.  That is unpacked HERE, once,
    rather than at every reader — a caller should not have to know that the
    third column of a block called ENTRY_OUT_KIND is the kind.
    """
    from .. import _fyo_interface as FI
    return {row["shape"]: row["units"]
            for row in FI.BLOCKS["ENTRY_OUT_KIND"] if row["key"] == entry}


def _declared_outputs(entry: str) -> list:
    from .. import _fyo_interface as FI
    return [r["key"] for r in FI.BLOCKS[FI.ENTRY_BLOCKS[entry]["out"]]]


def run_native(entry: str, *, params: dict, inputs: dict, dims: dict) -> dict:
    """The entry, through this host's ``libfylite.so``."""
    from .. import kernel as K
    return K.scenario(entry, params=params, inputs=inputs, **dims)


def run_wasm(entry: str, *, params: dict, inputs: dict, dims: dict,
             wasm=None, node: str = "node") -> dict:
    """The entry, through the browser's wasm build, driven by node.

    ★Through ``app/assets/fylite.js`` — the SAME binding a page loads, and
    its generated companions — rather than a second loader written here.  A
    harness that instantiated the module its own way would be checking a
    third host nobody ships.
    """
    import numpy as np

    root = _paths.PKG.parent.parent
    wasm = Path(wasm) if wasm else WASM
    if not wasm.exists():
        raise FileNotFoundError(f"{wasm} — build it with rust/build.sh --wasm")

    def _num(x):
        """One float as JavaScript spells it.

        ★Python's `repr` is not a JS literal, in two ways that both bit:
        `repr(np.float64(2.0))` is `np.float64(2.0)` under numpy 2 (valid
        Python, `np is not defined` in node), and `repr(float("inf"))` is
        `inf` — which node also reads as an undefined name.  ★The second was
        found by the transport entry, whose `dt` is legitimately infinite
        (「一步走到定态」), and it failed as a NameError rather than as a
        number: the wrong kind of error for a wrong number.
        """
        x = float(x)
        if x != x:
            return "NaN"
        if x == float("inf"):
            return "Infinity"
        if x == float("-inf"):
            return "-Infinity"
        return repr(x)

    def _js(v):
        a = np.atleast_1d(np.asarray(v, float))
        return "[" + ", ".join(_num(x) for x in a) + "]"

    p_js = ", ".join(f"{k}: {_num(v)}" for k, v in params.items())
    i_js = ", ".join(f"{k}: {_js(v)}" for k, v in inputs.items())
    d_js = ", ".join(f"{k}: {int(v)}" for k, v in dims.items())
    asset = lambda n: str(root / "app/assets" / n)     # noqa: E731
    script = f"""
      (async () => {{
        globalThis.self = globalThis;
        self.FyI18n = {{ t: function (k) {{ return k; }} }};
        require({asset('fyo-interface.js')!r});
        require({asset('fyo.js')!r});
        require({asset('version.js')!r});
        require({asset('deck-names.js')!r});
        require({asset('fylite.js')!r});
        const fs = require('fs');
        const b = fs.readFileSync({str(wasm)!r});
        const k = await self.FyLite.fromBytes(
          b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
        const r = k.scenario({entry!r}, {{{p_js}}}, {{{i_js}}}, {{{d_js}}});
        const plain = {{}};
        for (const key of Object.keys(r)) {{
          plain[key] = typeof r[key] === 'number' ? r[key] : Array.from(r[key]);
        }}
        process.stdout.write(JSON.stringify(plain));
      }})().catch(e => {{
        console.error(String(e && e.message || e));
        process.exit(1);
      }});
    """
    got = subprocess.run([node, "-e", script], capture_output=True, text=True,
                         cwd=root)
    if got.returncode != 0:
        raise RuntimeError(f"the wasm host refused {entry!r}: {got.stderr}")
    return json.loads(got.stdout)


def discrete_digest(entry: str, out: dict) -> str:
    """SHA-256 over the entry's ``count`` and ``flag`` outputs.

    ★A digest, deliberately, and only over those rows: it has no tolerance to
    argue about, which is exactly right for「两边走了同样的路」and exactly
    wrong for a float.  ★The entry name is inside the digest so two entries'
    hashes can never collide into a false agreement.
    """
    import numpy as np

    kinds = out_kinds(entry)
    h = hashlib.sha256()
    h.update(entry.encode())
    exact = sorted(k for k, v in kinds.items() if v in ("count", "flag"))
    if not exact:
        #: ★said, not silently hashed to a constant: an entry with nothing
        #: exact to compare has no discrete claim, and a digest of nothing
        #: would look like agreement
        return "sha256:none-declared"
    for key in exact:
        if key not in out:
            raise KeyError(f"{entry}: {key!r} is declared {kinds[key]!r} and "
                           "the run did not return it")
        v = np.atleast_1d(np.asarray(out[key], float))
        #: an integer by construction; a non-integer here is the declaration
        #: being wrong, and saying so beats hashing a lie
        if not np.all(v == np.floor(v)):
            raise ValueError(f"{entry}: {key!r} is declared {kinds[key]!r} "
                             f"but is not integral: {v[:4]}")
        h.update(key.encode())
        h.update(np.ascontiguousarray(v.astype(np.int64)).tobytes())
    return "sha256:" + h.hexdigest()


def compare(entry: str, native: dict, wasm: dict, *, band: float = 1e-12,
            noise_max: float = 1e-10) -> dict:
    """What the two hosts agreed and disagreed on, row by row.

    Returns ``{"entry", "same_keys", "discrete", "worst", "worst_key",
    "noise", "verdict", "environment"}``.  ``verdict`` is ``"same"`` when the
    discrete digests match and every ``real`` row is inside ``band``.
    """
    import numpy as np

    from .provenance import env_fingerprint

    kinds = out_kinds(entry)
    only_n = sorted(set(native) - set(wasm))
    only_w = sorted(set(wasm) - set(native))
    rec = {"entry": entry, "same_keys": not (only_n or only_w),
           "only_native": only_n, "only_wasm": only_w,
           "discrete": {"native": discrete_digest(entry, native),
                        "wasm": discrete_digest(entry, wasm)},
           "worst": 0.0, "worst_key": None, "noise": {}, "verdict": "differs",
           #: ★A-7's own words: a difference must be EXPLAINED by the record.
           #: The fingerprint names the host, so a report says which build
           #: produced which figure instead of leaving it to be assumed.
           "environment": {"native": env_fingerprint(),
                           "wasm": {"host": "wasm", "artifact": str(WASM)}}}
    if not rec["same_keys"]:
        rec["verdict"] = "key sets differ"
        return rec
    for key in sorted(native):
        kind = kinds.get(key, _DEFAULT_KIND)
        a = np.atleast_1d(np.asarray(native[key], float))
        b = np.atleast_1d(np.asarray(wasm[key], float))
        if kind == "noise":
            #: ★comparing two hosts' noise RELATIVELY is a category error —
            #: it is the difference of nearly equal numbers on each side, so
            #: agreement to 1e-12 would be a coincidence, not a property.
            #: What is checkable is that both are small.
            rec["noise"][key] = {"native": float(np.max(np.abs(a))),
                                 "wasm": float(np.max(np.abs(b)))}
            continue
        if kind in ("count", "flag"):
            continue                              # the digest carries these
        scale = max(float(np.max(np.abs(a))), 1e-300)
        rel = float(np.max(np.abs(a - b)) / scale)
        if rel > rec["worst"]:
            rec["worst"], rec["worst_key"] = rel, key
    same_hash = rec["discrete"]["native"] == rec["discrete"]["wasm"]
    noisy = [k for k, v in rec["noise"].items()
             if max(v["native"], v["wasm"]) > noise_max]
    if not same_hash:
        rec["verdict"] = "the hosts took different discrete paths"
    elif noisy:
        rec["verdict"] = f"noise rows are not machine noise: {noisy}"
    elif rec["worst"] > band:
        rec["verdict"] = (f"{rec['worst_key']} differs by {rec['worst']:.2e}, "
                          f"beyond the {band:.0e} cross-host band")
    else:
        rec["verdict"] = "same"
    return rec


def for_ledger(doc: dict) -> dict:
    """Which nodes of a recorded instance this driver can cross-check.

    ★Refused BY NAME, never dropped: a scenario tool that is Python assembly
    around many kernel calls (``discharge``, ``reconstruction``, ``coupled``)
    has no wasm counterpart outside a browser page, and a report that simply
    omitted it would read as「两宿主一致」about a node nobody ran twice.
    """
    from ..scenario import TOOLS

    entries = set(_entry_names())
    runnable, refused = [], {}
    for node in (doc.get("fylite:projection") or {}).get("dag", {}).get(
            "nodes") or []:
        #: ★the tool is in `attrs`, where `ledger.record` puts it — not at
        #: the node's top level.  Reading the wrong place made every node
        #: refuse itself with a message about assembly, which is a refusal
        #: for the wrong reason and reads as an answer.
        attrs = node.get("attrs") or {}
        tool = (attrs.get("tool") or node.get("tool") or "")
        tool = tool.replace("fylite_", "")
        spec = TOOLS.get(tool) or {}
        core = spec.get("kernel_entry")
        #: ★★ONLY a declared `kernel_entry` counts.  There was a fallback here
        #: that accepted a tool whose NAME happens to match an entry, and it
        #: promptly claimed `transport` — whose Python tool reaches the same
        #: kernel code through the flat exports and never calls that entry.
        #: A cross-host report about a path the tool does not take is worse
        #: than no report: it is a wrong answer to the right question, and a
        #: name is not a declaration.
        if core and core in entries:
            runnable.append({"id": node["id"], "entry": core, "tool": tool})
        elif core:
            refused[node["id"]] = (
                f"tool {tool!r} declares kernel_entry {core!r}, which the "
                "kernel does not declare as a scenario entry")
        else:
            refused[node["id"]] = (
                f"tool {tool!r} declares no `kernel_entry` — its host "
                "assembly does not hand a single kernel symbol the answer, "
                "so the wasm build has no counterpart to run against it")
    return {"runnable": runnable, "refused": refused}


def _entry_names() -> tuple:
    from .. import _fyo_interface as FI
    return tuple(FI.ENTRIES)
