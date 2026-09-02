"""fylite.kernel's loader — the S0 exit criteria of FYL-DESIGN-01, as tests.

Three contracts:

* the core is loadable and callable end to end (dlopen -> symbol ->
  f64 round-trip) when the library is present;
* a missing library is reported by ``load()`` / ``available()`` and refused
  loudly by ``require()`` — there is nothing to fall back to;
* a present library with the wrong ABI is refused, never quietly unused.
"""
import ctypes

import pytest

from fylite import kernel
from fylite._paths import KERNEL_LIB


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    """Each test sees an unresolved loader (the cache is process-global)."""
    monkeypatch.setattr(kernel, "_cache", None)
    monkeypatch.delenv("FY_KERNEL_LIB", raising=False)


# --------------------------------------------------------------------------- #
# missing library: supported, quiet on the default path, loud on request
# --------------------------------------------------------------------------- #
def test_a_missing_kernel_is_an_error_now(monkeypatch, tmp_path):
    """★★The posture inverted, and this test is where it is written down.

    Design §3.4 said a missing library is NOT an error: every consumer fell
    back — numpy for L1/L2/L5-L7, the Fortran path for L3/L4.  There are no
    such implementations left.  The numpy twins are references in
    `tests/oracles/`, deliberately unreachable from shipping code, and the
    Fortran libraries left with LICENSE 3.1/3.2.  So a missing kernel is not
    a degraded run; it is no run, and `require` says so instead of quietly
    producing numbers from somewhere else.
    """
    monkeypatch.setenv("FY_KERNEL_LIB", str(tmp_path / "nope.so"))
    #: the probe itself still answers rather than raising — "is it there"
    #: is a legitimate question with a legitimate negative answer
    assert kernel.load() is None
    assert kernel.available() is False
    with pytest.raises(kernel.KernelError, match="only host"):
        kernel.require()


def test_negative_probe_is_cached(monkeypatch, tmp_path):
    """A failed probe must not retry dlopen on every call."""
    monkeypatch.setenv("FY_KERNEL_LIB", str(tmp_path / "nope.so"))
    assert kernel.load() is None
    calls = {"n": 0}
    real_exists = type(tmp_path).exists

    def counting(self):
        calls["n"] += 1
        return real_exists(self)

    monkeypatch.setattr(type(tmp_path), "exists", counting)
    assert kernel.load() is None          # cached — no new stat
    assert calls["n"] == 0


# --------------------------------------------------------------------------- #
# present library: the S0 "loadable and callable" gate
# --------------------------------------------------------------------------- #
needs_lib = pytest.mark.skipif(not KERNEL_LIB.exists(),
                               reason="libfylite_kernel.so not built "
                                      "(rust/build.sh)")


@needs_lib
def test_core_loads_and_reports_the_expected_abi():
    lib = kernel.load()
    assert lib is not None
    assert int(lib.fylite_rs_abi_version()) == kernel.ABI_VERSION
    assert kernel.available() is True


@needs_lib
def test_ping_round_trips_a_double():
    lib = kernel.load()
    for x in (0.0, 2.5, -1.0e300, 6.02214076e23):
        assert lib.fylite_rs_ping(ctypes.c_double(x)) == x


@needs_lib
def test_wrong_abi_version_is_refused(monkeypatch, tmp_path):
    """A present-but-incompatible library must be loud, not quietly unused.

    Simulated by lying about the expected version — equivalent to loading a
    library built against a different contract.
    """
    monkeypatch.setattr(kernel, "ABI_VERSION", 999)
    with pytest.raises(kernel.KernelError, match="ABI"):
        kernel.load()


def test_wasm_module_passes_the_node_smoke_check():
    """The deferred-last wasm stage (design §8): the SAME capi surface,
    compiled for wasm32-unknown-unknown with --no-default-features,
    instantiates in a JS runtime and passes the ladder — abi/ping,
    ellipke against closed forms, mutual_filaments BIT-IDENTICAL to the
    native x86-64 value (straight-line IEEE-754), and a full
    fixed-boundary GS solve converging to 1e-10.  Skips when node or
    the wasm artifact is absent (build with rust/build.sh --wasm-check).
    """
    import shutil
    import subprocess
    from fylite._paths import KERNEL_LIB
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    root = KERNEL_LIB.parents[3] / "rust"
    # the DIST copy, not the cargo target: build.sh now builds two wasm
    # variants (`core` and `tglf`) that both land on the same target
    # path, so whatever is there is whichever was built last — the
    # feature-reduced one.  build.sh checks the dist copy for the same
    # reason.
    wasm = root / "wasm" / "dist" / "fylite_rs.wasm"
    if not wasm.exists():
        pytest.skip("wasm artifact not built (rust/build.sh --wasm-check)")
    proc = subprocess.run([node, str(root / "wasm" / "check.mjs"),
                           str(wasm)], capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ALL GREEN" in proc.stdout
