"""A-3 — the run says what it was reproducible from, and the claim is checked.

Two halves, and each is useless without the other:

* the run manifest RECORDS the environment that can change a number, read
  off the declaration rather than a list kept by hand here;
* the thing the record implies — that the thread count is NOT one of those
  things — is MEASURED, on a real run, by replaying it at two thread counts
  and comparing the delivered numbers.

★The comparison is on the NUMBERS, not on the files.  A run record carries a
timestamp and a run id, so two runs can never be byte-identical and a gate
that hashed the files would be measuring the clock.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from fylite.engine import manifest as M
from fylite.engine import provenance as P


# --------------------------------------------------------------------------- #
# the record
# --------------------------------------------------------------------------- #
def test_the_fingerprint_records_exactly_the_declared_result_bearing_set():
    """★★Read off the declaration, never remembered.

    A fingerprint carrying a hand-kept list goes stale on the day someone
    adds a variable, and the failure is silent: the run records an
    environment it was not run in.
    """
    declared = M.environment()
    want = {n for n, spec in declared.items() if spec.get("affects_result")}
    got = set(P.env_fingerprint()["variables"])
    assert got == want, {"only recorded": sorted(got - want),
                         "only declared": sorted(want - got)}
    #: a detector that matched an empty set would pass the line above
    assert len(want) >= 5, sorted(want)


def test_every_declared_variable_says_whether_it_can_change_a_number():
    """★The declaration is the single place that answers 「这个变量会不会
    改一个数」, so an entry that does not answer it is the gap, not a
    default."""
    missing = [n for n, spec in M.environment().items()
               if "affects_result" not in spec
               or not str(spec.get("affects_result_why", "")).strip()]
    assert not missing, (
        f"these entries do not say whether they change a result, or say it "
        f"without a reason: {missing}")


def test_an_unset_variable_is_recorded_as_unset_not_omitted(monkeypatch):
    """★「没有设」 is a fact about the run.  A key that is simply absent
    cannot be told apart from a fingerprint written before the variable
    existed."""
    monkeypatch.delenv("FYLITE_DEVICE_DIR", raising=False)
    fp = P.env_fingerprint()
    assert "FYLITE_DEVICE_DIR" in fp["variables"]
    assert fp["variables"]["FYLITE_DEVICE_DIR"] is None


def test_the_thread_setting_records_the_request_and_the_machine(monkeypatch):
    """★Both, because they are different facts: what was asked for, and what
    the machine could have given.  A record with only the request cannot say
    what an unset variable meant."""
    monkeypatch.setenv("RAYON_NUM_THREADS", "3")
    t = P.env_fingerprint()["threads"]
    assert t["RAYON_NUM_THREADS"] == "3"
    assert isinstance(t["available_parallelism"], int)
    assert t["available_parallelism"] >= 1
    monkeypatch.delenv("RAYON_NUM_THREADS")
    assert P.env_fingerprint()["threads"]["RAYON_NUM_THREADS"] is None


def test_the_fingerprint_survives_an_unreadable_declaration(monkeypatch):
    """★A provenance record must not be the thing that breaks a run — but it
    must SAY it could not read the declaration rather than report an empty
    environment, which reads as「没有一个会影响结果的变量」."""
    def boom():
        raise OSError("no declaration here")
    monkeypatch.setattr(M, "environment", boom)
    got = P.env_fingerprint()["variables"]
    assert list(got) == ["$error"], got


# --------------------------------------------------------------------------- #
# the claim the record implies
# --------------------------------------------------------------------------- #
def _numbers(obj, out, path=""):
    if isinstance(obj, dict):
        for k, v in sorted(obj.items()):
            _numbers(v, out, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _numbers(v, out, f"{path}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[path] = float(obj)


def _delivered_digest(run_dir: Path) -> tuple[str, str, int, list]:
    """The NUMBERS a run delivered, hashed — scalars and arrays apart."""
    res = json.loads((run_dir / "result.json").read_text())
    nums: dict = {}
    _numbers(res, nums)
    blob = json.dumps({k: repr(v) for k, v in sorted(nums.items())},
                      sort_keys=True).encode()
    h = hashlib.sha256()
    npz = dict(np.load(run_dir / "arrays.npz"))
    for k in sorted(npz):
        h.update(k.encode())
        h.update(np.ascontiguousarray(npz[k]).tobytes())
    return (hashlib.sha256(blob).hexdigest(), h.hexdigest(),
            len(nums), sorted(npz))


@pytest.mark.parametrize("case", ["breakdown-iter"])
def test_the_thread_count_does_not_change_a_number(case, tmp_path,
                                                   monkeypatch):
    """★★A-3's closing criterion: replay across ``RAYON_NUM_THREADS`` and the
    delivered numbers must be bit-identical.

    The kernel's parallel paths are per-element with identical arithmetic
    (``rust/fylite/src/kernels.rs``), so this SHOULD hold — and a claim that
    should hold is exactly the kind that is worth a gate, because when it
    stops holding nothing else will say so.

    ★Measured 2026-08-26 on the heavier case too (`discharge-iter`: 138
    scalars and the full psi map, bit-identical at 1 and 4 threads).  That
    one is not parametrized here because it is a ~14 s free-boundary anneal
    and this is the default tier; the physics tier carries it.
    """
    from fylite.scenario import cases

    seen = {}
    for n in ("1", "4"):
        monkeypatch.setenv("RAYON_NUM_THREADS", n)
        monkeypatch.setenv("FYLITE_RUN_DIR", str(tmp_path / n))
        monkeypatch.setenv("FYLITE_SESSION", f"det-{n}")
        r = cases.run(case)
        seen[n] = _delivered_digest(Path(r["run_dir"]))

    #: ★the digest must have digested something — two empty runs agree
    assert seen["1"][2] >= 10 and seen["1"][3], seen["1"]
    assert seen["1"][:2] == seen["4"][:2], {
        "1 thread": seen["1"], "4 threads": seen["4"],
        "why this matters": "the kernel claims per-element parallelism with "
                            "identical arithmetic; a difference here means a "
                            "reduction became order-dependent"}


def test_the_run_manifest_carries_the_environment(tmp_path, monkeypatch):
    """★The record has to be IN the delivered manifest, not merely
    computable — a reader opening a run directory is the whole point."""
    from fylite.scenario import cases

    monkeypatch.setenv("RAYON_NUM_THREADS", "2")
    monkeypatch.setenv("FYLITE_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("FYLITE_SESSION", "det-manifest")
    r = cases.run("breakdown-iter")
    man = json.loads((Path(r["run_dir"]) / "manifest.json").read_text())
    env = man["environment"]
    assert env["threads"]["RAYON_NUM_THREADS"] == "2", env["threads"]
    declared = {n for n, s in M.environment().items() if s.get("affects_result")}
    assert set(env["variables"]) == declared
