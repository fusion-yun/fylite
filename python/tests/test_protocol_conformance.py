"""ExecutionBody protocol conformance — fylite as the architecture-validation case.

``fylite.engine.ExecutionBody`` implements SpModel's ``ExecutionBody`` protocol
(SPM-ADR-111 D1/D2/D3/D6/D7 + SPM-ADR-112 D4) for a real non-reentrant Fortran
library, while importing **nothing** from the sp / fy ecosystem.  This suite is the
executable statement of that claim, in three parts:

* **PART A — support (static).**  Walk ``engine.PROTOCOL`` — the contract restated
  as data — against the implementation: declarations, phase set, scope state,
  vocabulary, error taxonomy, and the members deliberately declared
  not-applicable.
* **PART B — support (behavioural).**  Assert invariants I-1..I-8 by observation,
  driving real forked calls against ``libc`` as a stand-in library.  Signatures
  cannot express "dispose always runs"; only running it can.
* **PART C — independence + drift.**  ``engine`` must not import ``sp`` / ``fytok``
  (asserted from the AST, PART B's I-8).  Then, **only if** ``sp.core.execution``
  happens to be importable, cross-check ``PROTOCOL`` against the real upstream so
  drift is caught wherever the ecosystem is installed — and skip otherwise, so the
  ecosystem never becomes a dependency of this port.

Every test here runs on the standard library plus ``libc``; none needs
``libefit.so``, the Green tables, or MDSplus.
"""
from __future__ import annotations

import ast
import ctypes.util
import dataclasses
import inspect
import pathlib
import threading

import pytest

from fylite import engine
from fylite.engine import (
    DELIVER, PROTOCOL, RECLAIM, RETAIN, CallScope, CallTimeout, CallTrace,
    ConcurrentInvocationError, Disposition, EngineError, EnvironmentAcquireError,
    ExecuteError, ExecutionBody, PoisonedBodyError,
)

LIBC = ctypes.util.find_library("c") or "libc.so.6"

#: the protocol's phase methods in driver order (dispose excluded: it is P-6 and
#: runs from the driver's ``finally``, so it is asserted separately)
PHASE_METHODS = [m for _, m, _ in PROTOCOL["phases"]]


# =========================================================================== #
# PART A — support, statically: every declared member is really there
# =========================================================================== #
@pytest.mark.parametrize("name", PROTOCOL["declarations"])
def test_declaration_is_a_class_level_flag(name):
    """D1 / D3 / D7 declarations are class attributes, not instance state — a
    consumer must be able to read them off the class before constructing."""
    assert hasattr(ExecutionBody, name), f"missing declaration {name}"
    value = getattr(ExecutionBody, name)
    if name == "kind":
        assert isinstance(value, str) and value
    elif name == "manifest_kind":
        assert value is None or isinstance(value, str)
    else:
        assert isinstance(value, bool)


@pytest.mark.parametrize("name", PHASE_METHODS)
def test_phase_method_exists_and_is_callable(name):
    """D3: all six phases are override points on the body, not driver internals."""
    assert callable(getattr(ExecutionBody, name, None)), f"missing phase {name}"


@pytest.mark.parametrize("name", PROTOCOL["environment_members"]
                         + PROTOCOL["call_members"]
                         + PROTOCOL["provenance_members"])
def test_protocol_member_exists_and_is_callable(name):
    assert callable(getattr(ExecutionBody, name, None)), f"missing member {name}"


@pytest.mark.parametrize("name", PROTOCOL["scope_state_attrs"])
def test_scope_state_attribute_exists_under_the_upstream_name(name):
    """D2/D7 scope state uses the upstream attribute names, so a reader moving
    between the two implementations finds the same state under the same name."""
    s = ExecutionBody(lib_path=LIBC)
    try:
        assert hasattr(s, name), f"missing scope state {name}"
    finally:
        s.close()


def test_disposition_vocabulary_is_the_protocol_three():
    assert [d.value for d in Disposition] == list(PROTOCOL["dispositions"])
    # the historical module constants are the enum members themselves
    assert (RECLAIM, DELIVER, RETAIN) == (
        Disposition.RECLAIM, Disposition.DELIVER, Disposition.RETAIN)
    # str mixin: value comparison and JSON round-trip keep working ...
    assert RETAIN == "retain" and str(RETAIN) == "retain"
    # ... while identity comparison behaves as on upstream's plain Enum
    assert Disposition("retain") is RETAIN


def test_environment_state_names_are_the_protocol_three():
    s = ExecutionBody(lib_path=LIBC)
    try:
        assert s._env_state in PROTOCOL["environment_states"]
        s.poison("probe")
        assert s._env_state == "poisoned"
        s.close()
        assert s._env_state == "poisoned"     # I-5: poison survives close
    finally:
        s.close()


def test_error_taxonomy_shape():
    """The local family mirrors upstream's OperatorError tree, and keeps the
    ``RuntimeError`` base so pre-taxonomy ``except RuntimeError`` callers work."""
    assert issubclass(EngineError, RuntimeError)
    for local in PROTOCOL["errors"]:
        cls = getattr(engine, local)
        assert issubclass(cls, EngineError), f"{local} is outside the taxonomy"
    # the two concrete P-4 faults specialize ExecuteError
    assert issubclass(CallTimeout, ExecuteError)
    assert issubclass(engine.CallCancelled, ExecuteError)
    # a timeout is still a TimeoutError for callers that catch the builtin
    assert issubclass(CallTimeout, TimeoutError)


def test_call_scope_carries_the_protocol_fields():
    fields = {f.name for f in dataclasses.fields(CallScope)}
    assert {"call_id", "workdir", "owns_workdir", "disposition"} <= fields


def test_identity_keys_present_and_class_named():
    s = ExecutionBody(lib_path=LIBC)
    try:
        ident = s.environment_identity()
        assert set(PROTOCOL["identity_keys"]) <= set(ident)
        assert ident["body_kind"] == ExecutionBody.kind
        assert ident["body_class"].endswith("ExecutionBody")
        proj = s.manifest_projection()
        assert proj["kind"] == ExecutionBody.manifest_kind
        assert proj["concretization"] == s.environment_identity()
    finally:
        s.close()


@pytest.mark.parametrize("name", ["bind", "compile", "ensure_compiled",
                                 "cache_key", "prepare_inputs"])
def test_not_applicable_members_are_absent_not_stubbed(name):
    """The compile / port half of the upstream body presupposes an Operator and a
    RuntimeBackend.  It is declared not-applicable in ``PROTOCOL`` and genuinely
    absent — a stub would advertise support that does not exist."""
    assert name in PROTOCOL["not_applicable"]
    assert not hasattr(ExecutionBody, name)


@pytest.mark.parametrize("name", ["InputValidationError", "OutputValidationError",
                                  "CompilerError"])
def test_not_applicable_errors_are_absent(name):
    assert name in PROTOCOL["not_applicable"]
    assert not hasattr(engine, name)


def test_local_extensions_are_real_and_documented():
    """Every extension beyond the protocol exists and carries its reason, so the
    reference case cannot quietly grow undeclared surface."""
    for name, reason in PROTOCOL["local_extensions"].items():
        assert hasattr(ExecutionBody, name), f"declared extension {name} missing"
        assert reason and isinstance(reason, str)


# =========================================================================== #
# PART B — support, behaviourally: the invariants signatures cannot express
# =========================================================================== #
class _Recorder(ExecutionBody):
    """Records the phase sequence of each call (and can fail a chosen phase)."""

    def __init__(self, *a, fail_in: str | None = None, **kw) -> None:
        super().__init__(*a, **kw)
        self.seen: list[str] = []
        self.fail_in = fail_in

    def _mark(self, phase):
        self.seen.append(phase)
        if self.fail_in == phase:
            raise RuntimeError(f"boom in {phase}")

    def interpret_inputs(self, request):
        self._mark("interpret_inputs")
        return super().interpret_inputs(request)

    def provision(self, request, *, workdir=None):
        self._mark("provision")
        return super().provision(request, workdir=workdir)

    def stage(self, call):
        self._mark("stage")
        return super().stage(call)

    def execute(self, call, timeout, cancel_token=None):
        self._mark("execute")
        return super().execute(call, timeout, cancel_token)

    def interpret_outputs(self, res):
        self._mark("interpret_outputs")
        return super().interpret_outputs(res)

    def harvest(self, call, res):
        self._mark("harvest")
        return super().harvest(call, res)

    def dispose(self, call, res):
        self._mark("dispose")
        return super().dispose(call, res)


def test_i1_phases_run_in_protocol_order_once_per_attempt():
    s = _Recorder(lib_path=LIBC)
    try:
        assert s.invoke(lambda lib: 1).ok
        assert s.seen == PHASE_METHODS, f"phase order drifted: {s.seen}"
    finally:
        s.close()


@pytest.mark.parametrize("phase", ["interpret_inputs", "stage", "execute",
                                   "interpret_outputs", "harvest"])
def test_i2_dispose_always_runs_when_a_phase_raises(phase):
    """P-6 is the driver's ``finally``: no override can skip release."""
    s = _Recorder(lib_path=LIBC, fail_in=phase)
    try:
        with pytest.raises(RuntimeError, match="boom"):
            s.invoke(lambda lib: 1)
        if phase == "interpret_inputs":
            # P-1 precedes P-2, so there is no lease to release yet
            assert "dispose" not in s.seen
        else:
            assert s.seen[-1] == "dispose"
    finally:
        s.close()


def test_i3_a_raising_phase_forces_retain_and_keeps_the_scene():
    """D3's retain-on-failure, on the path that used to lose it: a private,
    reclaim-provisioned workspace whose execute phase raises."""
    kept: list = []

    class Reclaiming(ExecutionBody):
        def provision(self, request, *, workdir=None):
            call = super().provision(request, workdir=workdir)
            call.disposition = RECLAIM          # as a COW call is provisioned
            kept.append(call)
            return call

        def execute(self, call, timeout, cancel_token=None):
            (call.workdir / "evidence.log").write_text("why it failed")
            raise CallTimeout("wedged")

    s = Reclaiming(lib_path=LIBC)
    try:
        with pytest.raises(CallTimeout):
            s.invoke(lambda lib: 1)
        call = kept[-1]
        assert call.disposition == RETAIN
        assert (call.workdir / "evidence.log").is_file(), "failure scene reclaimed"
        assert s.last_disposition() == "retain"          # I-7
    finally:
        s.close()


def test_i4_acquire_is_idempotent_and_poison_guarded():
    s = ExecutionBody(lib_path=LIBC)
    try:
        s.acquire()
        s.acquire()                                    # idempotent
        assert s.environment_ready()
        s.poison("broken")
        with pytest.raises(PoisonedBodyError):
            s.acquire()
        with pytest.raises(PoisonedBodyError):         # and no call is served
            s.invoke(lambda lib: 1)
    finally:
        s.close()


def test_i4_acquire_failure_poisons_and_wraps():
    class Broken(ExecutionBody):
        def _acquire_environment(self):
            raise OSError("no such device")

    s = Broken(lib_path=LIBC)
    try:
        s.close()                                      # -> cold, so acquire runs
        with pytest.raises(EnvironmentAcquireError, match="no such device"):
            s.acquire()
        assert not s.environment_ready()
        assert s._env_state == "poisoned"
    finally:
        s.close()


def test_i5_close_is_idempotent_and_sweeps():
    s = ExecutionBody(lib_path=LIBC)
    d = s.scratch()
    assert d.is_dir()
    s.close()
    s.close()                                          # idempotent
    assert not d.exists(), "close did not sweep a tracked workdir"


def test_i6_exclusive_environment_admits_one_in_flight_call():
    started, release = threading.Event(), threading.Event()

    class Blocking(ExecutionBody):
        def execute(self, call, timeout, cancel_token=None):
            started.set()
            release.wait(5)
            return super().execute(call, timeout, cancel_token)

    s = Blocking(lib_path=LIBC)
    out: list = []
    t = threading.Thread(target=lambda: out.append(s.invoke(lambda lib: 1)))
    t.start()
    try:
        assert started.wait(5)
        with pytest.raises(ConcurrentInvocationError, match="single-in-flight"):
            s.invoke(lambda lib: 1)
    finally:
        release.set()
        t.join(10)
        s.close()
    assert out and out[0].ok


def test_i6_reentrant_body_admits_concurrent_calls():
    s = ExecutionBody(lib_path=LIBC, exclusive_environment=False)
    try:
        assert not s._is_exclusive
        assert s.invoke(lambda lib: 1).ok
    finally:
        s.close()


def test_i7_last_disposition_tracks_the_most_recent_call():
    s = ExecutionBody(lib_path=LIBC)
    try:
        assert s.last_disposition() == ""               # before any call
        s.invoke(lambda lib: 1)
        assert s.last_disposition() == "retain"         # fork-per-call: consumed
    finally:
        s.close()


def test_i7_trace_pairs_identity_with_disposition():
    """D6: the two things an operator lifts off a body are exactly the two the
    call trace carries."""
    s = ExecutionBody(lib_path=LIBC)
    try:
        r = s.invoke(lambda lib: 1)
        assert isinstance(r.trace, CallTrace)
        assert r.trace.disposition == s.last_disposition()
        assert r.trace.environment_identity["library"] == LIBC
    finally:
        s.close()


def test_i8_engine_imports_nothing_from_the_sp_or_fy_ecosystem():
    """Independence, asserted from the source: a protocol *implementation* that
    imported the protocol's owner would prove nothing about portability."""
    src = pathlib.Path(inspect.getfile(engine)).read_text()
    banned = {"sp", "fytok", "fyeq", "fytrans", "fydata", "spdm"}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            roots = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            roots = [(node.module or "").split(".")[0]]
        else:
            continue
        assert not (set(roots) & banned), f"engine imports {roots} (line {node.lineno})"


def test_subclass_with_its_own_init_can_attach_a_holder_in_place():
    """Regression: a domain subclass has its own ``__init__`` signature, so the
    ``cow()`` alternate constructor cannot serve it — ``start_holder()`` must, or
    the subclass is forced to nest a second body with a second environment scope
    (which is what ``EFITSession`` used to do)."""
    class Domain(ExecutionBody):
        def __init__(self, *, tables=None):        # deliberately not the base's
            super().__init__(lib_path=LIBC)
            self.tables = tables

    with pytest.raises(TypeError):                 # the constructor cannot adapt
        Domain.cow(LIBC, {}, warmup=lambda *a: 1, slice=lambda *a: 1)

    s = Domain(tables="t")
    try:
        s.start_holder({}, warmup=lambda lib, b, r: 1, slice=lambda lib, b, r: 1)
        assert s._holder is not None and s._holder.is_alive()
        assert s.environment_identity()["mode"] == "cow"    # one body, one scope
        assert s.invoke(("req",)).ok
    finally:
        s.close()
    assert s._holder is None                       # the same close tears it down


# =========================================================================== #
# PART C — drift check against the real upstream, only when it is installed
# =========================================================================== #
def _upstream():
    return pytest.importorskip(
        "sp.core.execution",
        reason="sp is not installed — the port does not depend on it, so the "
               "drift cross-check is skipped (PART A/B still assert conformance)")


def test_upstream_disposition_values_match():
    U = _upstream()
    assert [d.value for d in U.Disposition] == list(PROTOCOL["dispositions"])


def test_upstream_declares_the_same_class_level_flags():
    U = _upstream()
    for name in PROTOCOL["declarations"]:
        assert hasattr(U.ExecutionBody, name), f"upstream lost declaration {name}"


def test_upstream_has_the_same_phase_and_scope_members():
    U = _upstream()
    names = (PHASE_METHODS + list(PROTOCOL["environment_members"])
             + list(PROTOCOL["call_members"]) + list(PROTOCOL["provenance_members"]))
    missing = [n for n in names if not hasattr(U.ExecutionBody, n)]
    assert not missing, f"PROTOCOL names absent upstream (drift): {missing}"


def test_upstream_scope_state_uses_the_same_attribute_names():
    U = _upstream()
    private = set(U.ExecutionBody.__private_attributes__)
    assert set(PROTOCOL["scope_state_attrs"]) <= private
    assert U.ExecutionBody.__private_attributes__["_env_state"].default \
        == PROTOCOL["environment_states"][0] == "cold"


def test_upstream_call_scope_fields_are_a_subset_of_the_local_one():
    U = _upstream()
    up = {f.name for f in dataclasses.fields(U.CallScope)}
    local = {f.name for f in dataclasses.fields(CallScope)}
    assert up <= local, f"upstream CallScope fields not carried locally: {up - local}"


def test_upstream_error_taxonomy_maps_one_to_one():
    U = _upstream()
    assert issubclass(U.OperatorError, RuntimeError)      # same base as EngineError
    for local, upstream_name in PROTOCOL["errors"].items():
        assert hasattr(engine, local), f"local error {local} missing"
        assert hasattr(U, upstream_name), f"upstream error {upstream_name} missing"
        assert issubclass(getattr(U, upstream_name), U.OperatorError)


def test_not_applicable_members_do_exist_upstream():
    """The not-applicable ruling must name real upstream surface — otherwise it is
    an excuse for something that was never part of the protocol."""
    U = _upstream()
    for name in ("bind", "compile", "ensure_compiled", "cache_key", "prepare_inputs"):
        assert hasattr(U.ExecutionBody, name), f"{name} is not upstream surface"
    for name in ("InputValidationError", "OutputValidationError", "CompilerError"):
        assert hasattr(U, name), f"{name} is not upstream surface"


def test_local_extensions_are_genuinely_absent_upstream():
    U = _upstream()
    present = [n for n in PROTOCOL["local_extensions"]
               if hasattr(U.ExecutionBody, n)]
    assert not present, (
        f"declared local extensions now exist upstream — adopt them instead of "
        f"maintaining a parallel one: {present}")
