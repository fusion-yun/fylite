"""The fyo interface: one declaration, two hosts, and nowhere else.

★★Why this file exists.  Which document PATH a kernel slot is written
under is a contract between the Python layer and the browser, and it was
kept by two independent sets of literals: ``fylite/fyo.py`` spelled its
own, ``app/assets/session.js`` spelled its own, and the only shared
artifact was a list of ``fylite:`` TERMS whose browser copy nothing at
runtime imported.  That is the exact shape the repository has been burned
by before — ``psi_norm`` written bare on one side and prefixed on the
other, inside documents both typed ``fyo:equilibrium``: no error, just a
section the other host could not find.

The paths are declared once now, beside the code that produces the numbers
(``rust/fylite/src/fyo.rs``), and generated into both hosts by
``rust/build.sh``.  What this file checks is the three ways that could
still rot:

1. the generated files are the declaration (staleness);
2. the walkers HONOUR it — a slot lands exactly at its declared path,
   arrays of structure included;
3. **the two hosts build the same document** — the claim the whole
   arrangement exists to make, checked by having each build a skeleton of
   every slot and comparing them.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from fylite import fyo
from fylite import _fyo_interface as iface

ROOT = Path(__file__).resolve().parents[2]
JS_TABLE = ROOT / "app/assets/fyo-interface.js"
JS_WALKER = ROOT / "app/assets/fyo.js"

#: ★★2026-09-01 仓一分为二：字段表的**声明**与它生成的 `wasm/fyo-interface.json`
#: 都在内核检出里（`$FYLITE_KERNEL`，同级目录探测），本仓只有生成物的另外两个
#: 消费者（Python 的 `_fyo_interface` 与页面的 `fyo-interface.js`）。
#: ★所以下面那条「声明与生成物一致」的判据**只有拿到内核检出才做得了**：
#: 拿不到就点名跳过，而不是让它以「读不到文件」的样子长红——一条永远红的判据，
#: 与没有判据是同一件事，而且更吵。
def _kernel_root() -> Path | None:
    import os
    cands = ([Path(os.environ["FYLITE_KERNEL"])] if os.environ.get("FYLITE_KERNEL")
             else [ROOT.parent / "fylite_kernel", ROOT.parent / "fylite_dev"])
    for c in cands:
        if (c / "rust/fylite/src/fyo.rs").is_file():
            return c
    return None


_KROOT = _kernel_root()
KERNEL_DECL = (_KROOT / "rust/fylite/src/fyo.rs") if _KROOT else None
WASM_JSON = (_KROOT / "rust/wasm/fyo-interface.json") if _KROOT else None
requires_kernel_checkout = pytest.mark.skipif(
    _KROOT is None,
    reason=("字段表的声明在内核仓（fylite_kernel）里，本仓没有；"
            "设 $FYLITE_KERNEL 指向一份检出即可跑这条"))

SLOTS = [(t, k) for t in sorted(iface.TABLES)
         for k in iface.TABLES[t]["slots"]]


# --------------------------------------------------------------------------- #
# 1. the generated files ARE the declaration
# --------------------------------------------------------------------------- #
@requires_kernel_checkout
def test_every_declared_slot_reached_both_generated_files():
    js = JS_TABLE.read_text(encoding="utf-8")
    blob = json.loads(WASM_JSON.read_text(encoding="utf-8"))
    missing = []
    for table, key in SLOTS:
        path = iface.TABLES[table]["slots"][key]["path"]
        if json.dumps(path) not in js:
            missing.append(f"{table}/{key} is not in {JS_TABLE.name}")
        if blob["tables"].get(table, {}).get("slots", {}).get(key, {}) \
                .get("path") != path:
            missing.append(f"{table}/{key} is not in {WASM_JSON.name}")
    assert not missing, "\n  ".join(["run rust/build.sh:"] + missing)


@requires_kernel_checkout
def test_the_declaration_is_the_one_that_was_generated():
    """★The direction that catches an edit to the SOURCE with no rebuild —
    which is the direction that actually happens."""
    src = KERNEL_DECL.read_text(encoding="utf-8")
    declared = set()
    for name, _ in re.findall(r"@fyo-table\s+([A-Z_0-9]+)\s+(\S+)", src):
        declared.add(name)
    assert declared == set(iface.TABLES), (
        f"rust/fylite/src/fyo.rs declares {sorted(declared)} and "
        f"_fyo_interface.py carries {sorted(iface.TABLES)} — run "
        "rust/build.sh")
    for table, key in SLOTS:
        path = iface.TABLES[table]["slots"][key]["path"]
        assert f'"{key}"' in src and f'"{path}"' in src, (
            f"{table}/{key} is in the generated file and not in the Rust "
            "declaration — the generated file was edited by hand")


# --------------------------------------------------------------------------- #
# 2. the walker honours the declaration
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("table,key", SLOTS,
                         ids=[f"{t}.{k}" for t, k in SLOTS])
def test_a_slot_lands_at_its_declared_path(table: str, key: str):
    doc: dict = {}
    fyo.put(doc, table, key, 42.0)
    assert fyo.get(doc, table, key) == 42.0
    #: ★walked by hand, from the declaration, WITHOUT the walker — the
    #: point is to check the walker rather than to agree with it
    node = doc
    segs = fyo.path_of(table, key).split("/")
    for seg in segs[:-1]:
        node = node[seg]
        if seg in fyo.AOS:
            assert isinstance(node, list) and len(node) == 1, (
                f"{seg} is declared an array of structure and is a "
                f"{type(node).__name__}")
            node = node[0]
    assert node[segs[-1]] == 42.0


def test_a_slot_that_is_not_declared_is_refused_with_where_to_add_it():
    with pytest.raises(KeyError, match="rust/fylite/src/fyo.rs"):
        fyo.path_of("EQUILIBRIUM", "not_a_slot")
    with pytest.raises(KeyError, match="rust/fylite/src/fyo.rs"):
        fyo.path_of("NO_SUCH_TABLE", "ip")


def test_a_missing_slot_reads_as_missing_and_not_as_zero():
    """★A document that never carried a slot must say so.  A default of
    zero here is how a plasma with no current becomes a plasma with a
    current of zero, which reads as a measurement."""
    with pytest.raises(KeyError, match="fyo:equilibrium"):
        fyo.get({}, "EQUILIBRIUM", "ip")
    assert fyo.get({}, "EQUILIBRIUM", "ip", None) is None


# --------------------------------------------------------------------------- #
# 3. the two hosts build the SAME document
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_browser_walker_and_this_one_build_the_same_document():
    """★★The claim the whole arrangement exists to make.

    Each host is asked to place a marker in EVERY declared slot, and the two
    documents are compared as JSON.  A path spelled differently, an array of
    structure taken for a mapping, a table one host has and the other does
    not — all of them show up here as a diff, which is what the old
    arrangement could not produce.
    """
    script = f"""
      globalThis.self = globalThis;
      require({str(JS_TABLE)!r});
      require({str(JS_WALKER)!r});
      const F = globalThis.FyFyo, N = globalThis.FyNames;
      const out = {{}};
      for (const table of Object.keys(N.TABLES).sort()) {{
        const doc = {{'@type': F.type(table)}};
        for (const key of F.keys(table)) F.put(doc, table, key, 42);
        out[table] = doc;
      }}
      process.stdout.write(JSON.stringify(out));
    """
    got = subprocess.run(["node", "-e", script], capture_output=True,
                         text=True, cwd=ROOT)
    assert got.returncode == 0, got.stderr
    browser = json.loads(got.stdout)

    mine = {}
    for table in sorted(iface.TABLES):
        doc = {"@type": iface.TABLES[table]["type"]}
        for key in iface.TABLES[table]["slots"]:
            fyo.put(doc, table, key, 42)
        mine[table] = doc
    assert browser == mine


# --------------------------------------------------------------------------- #
# 4. the hosts read the table rather than keeping a copy of it
# --------------------------------------------------------------------------- #
def test_the_python_writers_no_longer_spell_a_declared_leaf_by_hand():
    """★The gate that keeps the convergence from decaying.

    Scope is chosen the way the vocabulary gate chooses its own: only the
    leaves that are DISTINCTIVE enough that a literal cannot be an ordinary
    local name.  ``ip``, ``f`` and ``q`` are declared slots too and are also
    perfectly ordinary identifiers — gating those would bury the rule in
    false positives, which is how a rule stops being read.
    """
    #: ★and not a leaf that IS a slot key: `put(doc, "EQUILIBRIUM",
    #: "psi_boundary", ...)` has to name the key, so finding that literal
    #: is the gate seeing the sanctioned call rather than a hand-spelling.
    keys = {k for _, k in SLOTS}
    distinctive = sorted({
        leaf for t, k in SLOTS
        if (leaf := iface.TABLES[t]["slots"][k]["path"].rsplit("/", 1)[-1])
        and len(leaf) > 8 and leaf not in keys})
    src = (ROOT / "python/fylite/fyo.py").read_text(encoding="utf-8")
    #: prose is not a spelling — the file explains these names at length
    code = "\n".join(l for l in src.splitlines()
                     if not l.lstrip().startswith(("#", '"', "'")))
    spelled = sorted(leaf for leaf in distinctive
                     if f'"{leaf}"' in code or f"'{leaf}'" in code)
    assert not spelled, (
        f"fyo.py spells declared leaves by hand: {spelled}\n"
        "Write them through fyo.put/fyo.get with the slot name; the path "
        "is declared in rust/fylite/src/fyo.rs.")


# --------------------------------------------------------------------------- #
# 5. the scenario face: named quantities over one symbol
# --------------------------------------------------------------------------- #
from fylite import kernel as K  # noqa: E402
from fylite._paths import KERNEL_LIB  # noqa: E402

_needs_kernel = pytest.mark.skipif(not KERNEL_LIB.exists(),
                                   reason="libfylite_kernel.so not built")

ENTRIES = list(iface.ENTRIES)
#: dimensions each entry is exercised at, in its own declared names
DIMS = {"zerod": {"nt": 7, "nr": 5}, "transport": {"n": 21},
        "profit": {"n": 40, "m": 4}, "vstab": {"n": 3},
        "evolve_heat": {"n": 21, "nt": 6}}


@pytest.mark.parametrize("entry", ENTRIES)
def test_every_entry_declares_blocks_that_can_be_laid_out(entry: str):
    lay = K.scenario_layout(entry, DIMS[entry])
    assert set(lay) == {"params", "input", "out"}
    for role, rows in lay.items():
        assert rows, f"{entry}/{role} is empty"
        #: contiguous and in declaration order — the offset IS the contract
        at = 0
        for key, (off, n) in rows.items():
            assert off == at, f"{entry}/{role}/{key}"
            at += n


@_needs_kernel
@pytest.mark.parametrize("entry", ENTRIES)
def test_the_kernel_and_this_host_size_the_blocks_the_same(entry: str):
    """★If these disagree, `_fyo_interface.py` and the built library are
    different generations — which is exactly the drift the declaration
    exists to prevent, and it is cheap to ask."""
    import numpy as np
    dims = DIMS[entry]
    lay = K.scenario_layout(entry, dims)
    mine = [sum(n for _, n in lay[r].values())
            for r in ("params", "input", "out")]
    dv = np.ascontiguousarray([dims[d] for d in iface.ENTRY_BLOCKS[entry]["dims"]],
                              dtype=np.uint64)
    got = np.empty(3)
    rc = K.require().fylite_rs_scenario_sizes(ENTRIES.index(entry), dv,
                                              dv.size, got)
    assert rc == 0
    assert [int(v) for v in got] == mine




@_needs_kernel
def test_an_argument_the_entry_does_not_take_is_refused_by_name():
    """★A silently ignored argument is how a caller ends up believing it
    asked for something it did not."""
    with pytest.raises(K.KernelError, match="ti_over_te"):
        K.scenario("zerod", params={"nope": 1.0}, nt=3, nr=3)
    with pytest.raises(K.KernelError, match="needs dimensions"):
        K.scenario("zerod", nt=3)
    with pytest.raises(K.KernelError, match="no entry"):
        K.scenario("not_an_entry", n=3)


@_needs_kernel
def test_an_unported_closure_is_refused_rather_than_defaulted():
    """★Asking the transport entry for a closure it does not carry must not
    quietly return the constant one's answer — a perfectly plausible
    profile from a different model."""
    import numpy as np
    n = 21
    rho = np.linspace(0.0, 1.0, n)
    inputs = dict(rho=rho, y_init=300.0, vprime=2.0 * rho + 1e-3,
                  source=50.0, velocity=0.0)
    ok = K.scenario("transport", n=n, inputs=inputs, params=dict(
        model=0, p0=1.0, dt=float("inf"), theta=1.0, edge_value=100.0,
        relax=1.0, relax_coeff=1.0, tol=1e-12, steps=1))
    assert ok["y"][0] > ok["y"][-1] and ok["converged"] == 1.0
    with pytest.raises(K.KernelError, match="refused"):
        K.scenario("transport", n=n, inputs=inputs, params=dict(
            model=3, p0=1.0, dt=float("inf"), theta=1.0, edge_value=100.0,
            relax=1.0, relax_coeff=1.0, tol=1e-12, steps=1))


@_needs_kernel
@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_both_hosts_run_the_same_scenario_and_agree():
    """★★★The whole point, end to end: the browser packs from the same
    declaration, calls the same symbol in the wasm build of the same kernel,
    and unpacks to the same numbers."""
    import numpy as np
    nt, nr = 7, 5
    wasm = ROOT / "app/assets/fylite_rs.wasm"
    if not wasm.exists():
        pytest.skip("wasm artifact not built")
    script = f"""
      (async () => {{
        globalThis.self = globalThis;
        self.FyI18n = {{ t: function (k) {{ return k; }} }};
        require({str(JS_TABLE)!r});
        require({str(JS_WALKER)!r});
        //: ★the generated kernel vocabularies, BEFORE the binding that reads
        //: them: `fylite.js` stopped carrying the species table by hand on
        //: 2026-08-26 and now throws rather than run with an empty one — so
        //: this harness is a third host with the same load order the worker
        //: and the pages have
        require({str(ROOT / "app/assets/version.js")!r});
        require({str(ROOT / "app/assets/deck-names.js")!r});
        require({str(ROOT / "app/assets/fylite.js")!r});
        const fs = require('fs');
        const b = fs.readFileSync({str(wasm)!r});
        const k = await self.FyLite.fromBytes(
          b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
        const nt = {nt}, nr = {nr};
        const r = k.scenario('zerod',
          {{ti_over_te: 0.9, peaking_n: 1.1, peaking_t: 1.7, edge_frac: 0.1,
            r0: 1.85, a: 0.45, kappa: 1.8, zeff: 1.6, li: 0.9,
            dt_fraction: 0.5}},
          {{t: Array.from({{length: nt}}, (_, i) => i * 0.5), ip: 1.0e6,
            ne0: 6e19, te0: 8e3, p_inj: 4e6,
            rho: Array.from({{length: nr}}, (_, i) => i / (nr - 1))}},
          {{nt: nt, nr: nr}});
        const plain = {{}};
        for (const key of Object.keys(r)) {{
          plain[key] = typeof r[key] === 'number' ? r[key]
                                                  : Array.from(r[key]);
        }}
        process.stdout.write(JSON.stringify(plain));
      }})().catch(e => {{ console.error(e.message); process.exit(1); }});
    """
    got = subprocess.run(["node", "-e", script], capture_output=True,
                         text=True, cwd=ROOT)
    assert got.returncode == 0, got.stderr
    browser = json.loads(got.stdout)

    t = np.arange(nt) * 0.5
    mine = K.scenario(
        "zerod",
        params=dict(ti_over_te=0.9, peaking_n=1.1, peaking_t=1.7,
                    edge_frac=0.1, r0=1.85, a=0.45, kappa=1.8, zeff=1.6,
                    li=0.9, dt_fraction=0.5),
        inputs=dict(t=t, ip=1.0e6, ne0=6e19, te0=8e3, p_inj=4e6,
                    rho=np.linspace(0.0, 1.0, nr)), nt=nt, nr=nr)
    assert sorted(browser) == sorted(mine)
    for key, want in mine.items():
        #: ★the two hosts run the same arithmetic on different backends
        #: (native cdylib vs wasm), which is a float-format difference and
        #: not a model one — the repo measures that at ~1e-12
        assert np.allclose(browser[key], want, rtol=1e-11, atol=0.0), key


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node not installed")
def test_both_hosts_march_the_same_discharge():
    """★★★同 case 双宿主对拍 (TODO §2.8) — for the loop itself.

    The 含时演化 bar's time loop is the kernel's since 2026-08-26, so the
    strongest thing that can be said about it is that BOTH kernel builds run
    it to the same discharge: native (this host, `libfylite_kernel.so`) and wasm
    (the browser's build, driven here through the same binding a page uses).

    ★The march is chosen to be hostile on purpose — 12 adaptive steps with
    the sources rebuilt each time, ADAS radiation with an impurity, D-T alpha
    heating, and the EPED1-NN pedestal moving the Dirichlet edge every step.
    Every one of those is a place where a divergence would compound rather
    than cancel.

    ★★The tolerance is MEASURED, not guessed: 5.5e-15 relative, worst over
    every returned row (2026-08-26).  It is not bit-identical and should not
    be expected to be — the two builds differ in float codegen (fma
    contraction, libm) — so the band is float-summation-order wide, three
    orders above the measurement.  A real divergence (a feedback applied in
    the wrong order, a unit bent on one side) is 1e-3 or worse and cannot
    hide under it.
    """
    import numpy as np
    from fylite import kernel as K, _deck_names as D
    wasm = ROOT / "app/assets/fylite_rs.wasm"
    if not wasm.exists():
        pytest.skip("wasm artifact not built")

    n, nt = 25, 12
    rho = np.linspace(0.0, 2.0, n)
    rb = rho / 2.0
    inputs = {"rho": rho, "vprime": 4 * np.pi ** 2 * 6.2 * rho,
              "gm3": np.ones(n),
              "te_init": 300 + 2700 * (1 - rb ** 2),
              "ti_init": 300 + 2200 * (1 - rb ** 2),
              "ne": 1e20 * (0.5 + 0.5 * (1 - rb ** 2))}
    params = {"b0": 5.3, "chi0": 0.4, "chi_ratio": 1.0, "edge_te": 300,
              "edge_ti": 300, "dt": 0.002, "dt_target": 0.02,
              "dt_min": 1e-5, "dt_max": 0.02, "d_pc": 0,
              "p_e": 4e6, "p_i": 4e6, "dep_centre": 0, "dep_width": 0.3,
              "brem": 1, "bulk_id": K.adas_id("D"), "imp_id": K.adas_id("C"),
              "imp_conc": 0.01, "imp_z": D.ADAS_Z["C"], "alpha": 1,
              "dt_fraction": 0.5, "zeff": 1.5, "pedestal": 1, "ip": 15e6,
              "a": 2.0, "r0": 6.2, "kappa": 1.86, "delta": 0.48}
    native = K.scenario("evolve_heat", params=params, inputs=inputs,
                        n=n, nt=nt)

    js_params = ", ".join(f"{k}: {v!r}" for k, v in params.items())
    #: ★plain floats, not numpy scalars: `repr(np.float64(2.0))` is
    #: `np.float64(2.0)` under numpy 2, which is valid Python and not valid
    #: JavaScript — the harness died on `np is not defined`
    js_inputs = ", ".join(
        f"{k}: {[float(x) for x in np.atleast_1d(np.asarray(v, float))]!r}"
        for k, v in inputs.items())
    script = f"""
      (async () => {{
        globalThis.self = globalThis;
        self.FyI18n = {{ t: function (k) {{ return k; }} }};
        require({str(JS_TABLE)!r});
        require({str(JS_WALKER)!r});
        require({str(ROOT / "app/assets/version.js")!r});
        require({str(ROOT / "app/assets/deck-names.js")!r});
        require({str(ROOT / "app/assets/fylite.js")!r});
        const fs = require('fs');
        const b = fs.readFileSync({str(wasm)!r});
        const k = await self.FyLite.fromBytes(
          b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
        const r = k.scenario('evolve_heat', {{{js_params}}},
                             {{{js_inputs}}}, {{n: {n}, nt: {nt}}});
        const plain = {{}};
        for (const key of Object.keys(r)) {{
          plain[key] = typeof r[key] === 'number' ? r[key]
                                                  : Array.from(r[key]);
        }}
        process.stdout.write(JSON.stringify(plain));
      }})().catch(e => {{
        console.error(String(e && e.message || e));
        process.exit(1);
      }});
    """
    got = subprocess.run(["node", "-e", script], capture_output=True,
                         text=True, cwd=ROOT)
    assert got.returncode == 0, got.stderr
    other = json.loads(got.stdout)

    assert set(other) == set(native), {
        "only native": sorted(set(native) - set(other)),
        "only wasm": sorted(set(other) - set(native))}
    #: ★★TWO ROWS ARE NOT COMPARED RELATIVELY, and refusing to is the
    #: honest reading rather than an exemption.  `balance` / `balance_worst`
    #: ARE machine noise — the conservation residual of a scheme that
    #: conserves by construction, i.e. the difference of nearly equal
    #: numbers.  Two builds' noise agreeing to 1e-12 RELATIVE would be a
    #: coincidence, not a property; what is checkable is that both are
    #: small.  Comparing them like the physical rows made this gate demand
    #: that two roundings match, and it duly failed at 0.43.
    NOISE = {"balance", "balance_worst"}
    for key in sorted(NOISE):
        for who, r in (("native", native), ("wasm", other)):
            v = float(np.max(np.abs(np.atleast_1d(np.asarray(r[key],
                                                             float)))))
            assert v < 1e-10, f"{who} {key} is not machine noise: {v:.2e}"

    worst, where = 0.0, None
    for key in sorted(set(native) - NOISE):
        a = np.atleast_1d(np.asarray(native[key], float))
        b = np.atleast_1d(np.asarray(other[key], float))
        assert a.shape == b.shape, (key, a.shape, b.shape)
        rel = float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(a))),
                                                1e-30))
        if rel > worst:
            worst, where = rel, key
    assert worst < 1e-12, (
        f"the two kernel builds marched to different discharges: worst "
        f"relative difference {worst:.3e} on {where!r} (measured 5.5e-15 "
        "when the loop was sunk).  Either an assembly bent a unit on one "
        "side, or a feedback is applied in a different order.")
    #: ★the discrete decisions must agree EXACTLY: how many steps were taken,
    #: whether it settled, how many hit the exchange ceiling.  A float band
    #: cannot excuse a different number of steps.
    for key in ("steps", "settled", "dt_capped"):
        assert float(native[key]) == float(other[key]), key


# --------------------------------------------------------------------------- #
# 6. A-1 — the two hosts READ the same value out of the same document
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_both_hosts_read_the_same_value_from_the_same_document():
    """★★A-1's criterion, literally: 两宿主同文档同槽取值逐位相同.

    The existing walker gate writes a marker into every slot and compares
    the two documents — that holds the PATHS.  This holds the other
    direction, which is the one a reader actually uses: a REAL document,
    with real numbers of many magnitudes, is handed to both hosts and every
    declared slot is read back.  A host that dug to the right place and
    parsed the value differently — an array-of-structure step taken as a
    mapping, a leaf read one level up — passes the write gate and fails this
    one.

    ★The comparison is EXACT (``==`` on the doubles), never a tolerance: this
    is a claim about getting the same number back, and a tolerance would let
    exactly the class of defect being hunted through.

    ★It compares numbers and not their printed forms, and that is a
    correction rather than a preference: the first version compared
    `repr(x)` with JavaScript's `String(x)`, and JS prints -3.5e17 as
    `-350000000000000000` while Python prints `-3.5e+17`.  The values were
    identical and the gate was red — it had started comparing two number
    FORMATTERS.  JSON round-trips a double exactly on both sides, so the
    numbers travel as numbers.
    """
    doc_by_table = {}
    #: ★magnitudes on purpose: a tiny, a huge, a negative and a value whose
    #: decimal form is not its binary one.  A round-trip that only ever saw
    #: 42 would not notice a host that went through a float32 or a toFixed.
    marks = [1e-300, -3.5e17, 0.1, 6.02214076e23, -1.0, 2.2250738585072014e-308]
    for table in sorted(iface.TABLES):
        doc = {"@type": iface.TABLES[table]["type"]}
        for i, key in enumerate(iface.TABLES[table]["slots"]):
            fyo.put(doc, table, key, marks[i % len(marks)])
        doc_by_table[table] = doc

    script = f"""
      globalThis.self = globalThis;
      require({str(JS_TABLE)!r});
      require({str(JS_WALKER)!r});
      const F = globalThis.FyFyo, N = globalThis.FyNames;
      const docs = {json.dumps(doc_by_table)};
      const out = {{}};
      for (const table of Object.keys(N.TABLES).sort()) {{
        const got = {{}};
        for (const key of F.keys(table)) {{
          //: as a NUMBER: JSON round-trips a double exactly, and a string
          //: would make this a comparison of two formatters
          got[key] = F.get(docs[table], table, key, null);
        }}
        out[table] = got;
      }}
      process.stdout.write(JSON.stringify(out));
    """
    got = subprocess.run(["node", "-e", script], capture_output=True,
                         text=True, cwd=ROOT)
    assert got.returncode == 0, got.stderr
    browser = json.loads(got.stdout)

    mine = {table: {key: float(fyo.get(doc_by_table[table], table, key))
                    for key in iface.TABLES[table]["slots"]}
            for table in sorted(iface.TABLES)}
    assert set(browser) == set(mine)
    for table in sorted(mine):
        assert set(browser[table]) == set(mine[table]), table
        for key, want in sorted(mine[table].items()):
            got_v = browser[table][key]
            assert got_v is not None, (table, key, "the browser read nothing")
            #: exact, and `==` on floats is the point
            assert float(got_v) == want, (table, key, got_v, want)
    #: ★and the marks really did exercise several magnitudes — a round trip
    #: that only ever saw one number proves nothing about the others
    assert len({v for t in mine.values() for v in t.values()}) >= 4


def test_the_section_tags_come_from_the_declaration_in_both_hosts():
    """★★A-1: `fyo:magnetics` and friends were spelled by hand in BOTH hosts
    — `_SECTION_TYPES` here, string literals in `app/assets/session.js` —
    which is one contract kept in two places.  Neither writes the string now,
    and this holds that: the tags must equal the declaration, and the literal
    must be gone from the browser file."""
    for name in ("MAGNETICS", "PF_ACTIVE", "TF"):
        assert name in iface.TABLES, name
        #: slotless on purpose: the tag is the shared fact, the payload
        #: inside a section is a device deck's own
        assert iface.TABLES[name]["slots"] == {}, name
    assert fyo._SECTION_TYPES == {
        "magnetics": iface.TABLES["MAGNETICS"]["type"],
        "pf_active": iface.TABLES["PF_ACTIVE"]["type"],
        "tf": iface.TABLES["TF"]["type"]}
    js = (ROOT / "app/assets/session.js").read_text(encoding="utf-8")
    for tag in ("'fyo:magnetics'", "'fyo:pf_active'"):
        assert tag not in js, (
            f"{tag} is spelled by hand in session.js again — it is declared "
            "in the kernel and reachable as FyFyo.type()")
    assert js.count("FyFyo.type(") >= 2


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_browser_session_writer_really_produces_the_declared_tags():
    """★★Reading the literal out of the file says the string is gone; it does
    NOT say the replacement works.  `self.FyFyo` has to actually be there when
    `session.js` runs, and「加载序对不对」is a different question from
    「字面量还在不在」 — the four node harnesses that died on a missing
    generated file were exactly this distinction going unchecked.

    So the writer is RUN, in the load order the pages use
    (`fyo-interface.js` -> `fyo.js` -> `session.js`), and its output is
    compared with the declaration.
    """
    script = f"""
      globalThis.self = globalThis;
      require({str(JS_TABLE)!r});
      require({str(JS_WALKER)!r});
      require({str(ROOT / "app/assets/session.js")!r});
      const S = self.FySession;
      const m = {{ channels: [[[0]]], coils: [{{name: 'PF1'}}], loops: [[1, 0]] }};
      process.stdout.write(JSON.stringify({{
        pf: S.pfActive(m, [42])['@type'],
        mag: S.magnetics(m, [1.0], [1.0], [1.0])['@type'],
      }}));
    """
    got = subprocess.run(["node", "-e", script], capture_output=True,
                         text=True, cwd=ROOT)
    assert got.returncode == 0, got.stderr
    made = json.loads(got.stdout)
    assert made["pf"] == iface.TABLES["PF_ACTIVE"]["type"]
    assert made["mag"] == iface.TABLES["MAGNETICS"]["type"]


def test_the_browser_walker_stays_a_walker():
    """★A-1's ratchet: `fyo.js` 手写行数只减不增.

    The file is the hand-written walker over a generated table, and its
    value is that it is SMALL — every line of it is a semantics this
    repository keeps in a second place.

    ★★口径改了（2026-08-27），和 §2.8 那道闸同一天同一个理由: it counted RAW
    lines, so it charged for COMMENTS.  A ratchet that bills you for writing
    down why a line is there teaches the opposite of what this repository
    wants — and it billed twice on the day this changed: the packer was
    made to NAME the row it cannot read (it dereferenced an undefined value
    to build the message that would have named it), and the unpacker was
    made to read the DECLARED shape instead of the computed length (an
    entry run at `nt = 1` was handing per-step rows back as bare numbers,
    and `out.p_rad[0]` came out `undefined` — travelling as NaN into a page
    reading three layers away).  Both are corrections; both are mostly
    prose.  So the measure is code: non-blank, non-comment.

    Measured 2026-08-27: **146** code lines (222 raw).
    """
    src = (ROOT / "app/assets/fyo.js").read_text(
        encoding="utf-8").splitlines()
    code = [ln for ln in src
            if ln.strip()
            and not ln.strip().startswith(("//", "/*", "*", "*/"))]
    assert len(code) <= 146, (
        f"app/assets/fyo.js grew to {len(code)} code lines (baseline 146, "
        f"{len(src)} raw).  It is the hand-written half of a generated "
        "contract: sink the semantics into the declaration and generate "
        "them out, or argue the growth.")
