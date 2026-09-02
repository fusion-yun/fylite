"""The kernel compiles with no warnings — and the check proves it compiled.

★★Why the second clause is the point.  While writing this, a first attempt
counted warnings with ``grep -c '^warning'`` and got **zero** — from a build
that had failed with twenty errors and never reached the warning stage.  A
broken crate scored better than a clean one.

That is the failure this suite keeps meeting from a new direction: a check
that returns green because nothing ran.  So this test asserts the exit status
FIRST and the warning count second, and would rather be skipped than
guess.

★Why warnings at all.  The build carried seventeen, twelve of them one
deliberate thing (upstream TGLF's Fortran field names).  Buried among them
were a docstring promising a guard that did not exist, two vestigial
parameters, and an ``#[allow(non_snake_case)]`` sitting on a ``macro_rules!``
definition — where an attribute does not reach the expansion, so it silenced
nothing while looking like it did.  Noise is not neutral; it is where a real
one hides.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

CRATE = Path(__file__).resolve().parents[2] / "rust" / "fylite"

pytestmark = [
    pytest.mark.skipif(shutil.which("cargo") is None, reason="no cargo"),
    pytest.mark.skipif(not CRATE.is_dir(), reason="crate not present"),
    pytest.mark.skipif(os.environ.get("FY_SKIP_CARGO") == "1",
                       reason="FY_SKIP_CARGO=1"),
]


def _build():
    """``cargo build`` on the real crate, warnings forced to re-emit.

    ``--message-format=short`` keeps the output small; touching nothing means
    a warm target dir answers in about a second, but cargo caches warnings,
    so ``-Awarnings``-free re-emission needs the check to run on a build that
    actually compiles the lib.  ``cargo check`` re-emits reliably and is
    cheaper than a full build.
    """
    return subprocess.run(
        ["cargo", "check", "--lib", "--message-format=short"],
        cwd=CRATE, capture_output=True, text=True, timeout=900)


def test_the_crate_compiles_and_emits_no_warnings():
    p = _build()
    out = (p.stdout or "") + (p.stderr or "")

    #: ★the exit status FIRST.  A crate that fails to compile emits no
    #: warnings, and a warning count taken from it reads as a perfect score.
    assert p.returncode == 0, (
        "the crate does not compile — the warning count below is meaningless "
        f"until it does:\n{out[-3000:]}")

    #: ★`--message-format=short` puts the FILE first — `src/x.rs:9:5:
    #: warning: ...` — so a `startswith("warning:")` filter matches none of
    #: them and reports a clean build over any number of warnings.  That is
    #: how the first version of this test passed with a probe warning
    #: deliberately planted in `transport.rs`.
    warn = [ln for ln in out.splitlines()
            if "warning:" in ln
            #: cargo's own trailing tally is a summary, not a finding
            and "generated" not in ln]
    assert not warn, (
        f"{len(warn)} compiler warning(s):\n  " + "\n  ".join(warn[:25])
        + "\n\nFix them or say why not in an #[allow(...)] with a note. "
          "Twelve identical warnings are how the thirteenth stays invisible.")


def test_the_wasm_targets_still_compile():
    """★★The wasm feature sets, built and their EXIT STATUS asserted.

    A `#[cfg(feature = "core")]` on code that uses `gyrofluid` compiles
    natively — the native build has every feature — and breaks
    `wasm32-unknown-unknown --features core`, where the `use ... as gf` is
    absent.  DE-COMP-01's invariant says that target MUST always build.

    ★This shipped once, in the commit that extracted
    `flux_inputs_from_blocks`.  `rust/build.sh` behaved correctly — it has
    `set -euo pipefail` and exits 101 — but the check was run as
    `build.sh --wasm-check | grep "wasm check"`, and when the aborted script
    printed nothing, the empty output was read as success.  In a pipeline
    `$?` belongs to grep, and it was not looked at either.

    So the assertion here is on the RETURN CODE, and the test exists so that
    the wasm invariant does not depend on anyone reading output correctly.
    """
    if not shutil.which("cargo"):
        pytest.skip("no cargo")
    target = subprocess.run(["rustc", "--print", "target-list"],
                            capture_output=True, text=True, timeout=60)
    if "wasm32-unknown-unknown" not in (target.stdout or ""):
        pytest.skip("wasm32-unknown-unknown target not installed")

    for feat in ("core", "tglf", "dke"):
        p = subprocess.run(
            ["cargo", "build", "--release", "--target",
             "wasm32-unknown-unknown", "--no-default-features",
             "--features", feat, "--message-format=short"],
            cwd=CRATE, capture_output=True, text=True, timeout=1800)
        assert p.returncode == 0, (
            f"the wasm build broke for --features {feat}:\n"
            + ((p.stdout or "") + (p.stderr or ""))[-2500:])


def test_a_failing_build_cannot_be_mistaken_for_a_clean_one():
    """★The guard on the guard, asserted rather than assumed.

    If ``cargo check`` ever starts reporting success for a crate it did not
    compile, the test above becomes decorative.  This pins the property the
    whole file rests on: a non-zero exit is what a broken build gives.
    """
    p = subprocess.run(
        ["cargo", "check", "--lib", "--message-format=short",
         "--features", "no-such-feature-exists"],
        cwd=CRATE, capture_output=True, text=True, timeout=300)
    assert p.returncode != 0, (
        "cargo reported success for an impossible build — the clean-build "
        "assertion above can no longer be trusted")
