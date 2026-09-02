"""K-16 — partial-success semantics + stage-level recovery over a scan."""
import sys

import pytest

#: ★the service reconstructs on the Rust inverse now (LICENSE 3.1
#: removed the EFIT driver), so the stub target moved with it
import fylite.scenario.analysis.recon_rs  # noqa: F401
# fylite.run's package attribute is the run() *function* (it shadows the
# submodule); get the module object via sys.modules.
run_mod = sys.modules["fylite.scenario.analysis.recon_rs"]


# --------------------------------------------------------------------------- #
# run_series: structured reports, partial/failed status, resume
# --------------------------------------------------------------------------- #
def _fake_run_factory(behaviour):
    """behaviour: time -> "ok" | "partial" | "raise".

    ★Stubs ``reconstruct_shot``, the shot/time door — not ``reconstruct``,
    which takes an already-assembled measurement dict.  These cases used to
    stub the latter, and passed: ``run_series`` was calling it as
    ``reconstruct(shot, t, ...)``, a signature it has never had, and this
    stub happened to match the broken call rather than the real function.
    A stub that agrees with its caller and not with its callee asserts
    nothing about either.
    """
    def _fake_run(shot, t, *, require_diagnostics=True, **kw):
        b = behaviour(round(float(t), 6))
        if b == "raise":
            raise run_mod.KefitRunError(f"solver blew up at {t}")
        diag = {"point": {"status": "ok"}}
        if b == "partial":
            diag["pressure"] = {"status": "failed", "reason": "Thomson NODATA"}
        return {"q0": 0.7, "q95": 3.0, "diagnostic_status": diag, "time_s": t}
    return _fake_run


def test_run_series_reports_ok_partial_failed(monkeypatch):
    def behaviour(t):
        return {1.0: "ok", 2.0: "partial", 3.0: "raise"}[t]
    monkeypatch.setattr(run_mod, "reconstruct_shot", _fake_run_factory(behaviour))

    out = run_mod.run_series(137985, [1.0, 2.0, 3.0])
    statuses = [r["status"] for r in out["reports"]]
    assert statuses == ["ok", "partial", "failed"]
    assert out["n_ok"] == 2 and out["n_partial"] == 1 and out["n_failed"] == 1
    # failed slice retains an error + a traceback tail
    failed = out["reports"][2]
    assert "solver blew up" in failed["error"]
    assert failed["traceback"]
    # partial slice surfaces which diagnostic dropped and why
    assert out["reports"][1]["diagnostic_status"]["pressure"]["status"] == "failed"


def test_run_series_fail_fast(monkeypatch):
    monkeypatch.setattr(run_mod, "reconstruct_shot", _fake_run_factory(lambda t: "raise"))
    with pytest.raises(run_mod.KefitRunError):
        run_mod.run_series(137985, [1.0], keep_going=False)


def test_run_series_resume_skips_completed(monkeypatch):
    # first pass: t=2.0 fails
    def behaviour1(t):
        return {1.0: "ok", 2.0: "raise"}[t]
    monkeypatch.setattr(run_mod, "reconstruct_shot", _fake_run_factory(behaviour1))
    first = run_mod.run_series(137985, [1.0, 2.0])
    assert first["n_failed"] == 1

    # second pass: everything would succeed, but t=1.0 must NOT be re-run
    called = []

    def _fake_run(shot, t, *, require_diagnostics=True, **kw):
        called.append(round(float(t), 6))
        return {"q0": 0.7, "diagnostic_status": {"point": {"status": "ok"}}}

    monkeypatch.setattr(run_mod, "reconstruct_shot", _fake_run)
    second = run_mod.run_series(137985, [1.0, 2.0], resume=first)
    assert called == [2.0]                        # only the previously-failed slice re-ran
    assert second["reports"][0].get("resumed") is True
    assert second["n_failed"] == 0


# --------------------------------------------------------------------------- #
# _east_measurements: per-diagnostic status, partial vs strict
# --------------------------------------------------------------------------- #
def _patch_mds(monkeypatch, *, thomson_ok=True):
    monkeypatch.setattr(run_mod.est2, "read_east_mds",
                        lambda *a, **k: {"point": {"n_ne_active": 8,
                                                   "n_fr_active": 3}}
                        if k.get("read_point") else {})

    def _fetch(shot, t, *, server=None):
        if not thomson_ok:
            raise RuntimeError("Thomson NODATA")
        return {"sample_time_s": t}
    monkeypatch.setattr(run_mod.mds, "fetch_thomson", _fetch)
    monkeypatch.setattr(run_mod.mds, "pressure_from_thomson",
                        lambda th, **k: {"n_points": 20, "n_dropped": 2,
                                         "ion_factor": 1.0, "sigma_source": "measured",
                                         "assumptions": "declared"})


def test_east_measurements_partial_records_failed_diagnostic(monkeypatch):
    _patch_mds(monkeypatch, thomson_ok=False)
    meas, extra = run_mod._east_measurements(
        137985, 4.0, read_point=True, read_pressure=True,
        require_diagnostics=False)
    st = extra["diagnostic_status"]
    assert st["point"]["status"] == "ok"
    assert st["thomson"]["status"] == "failed"
    assert st["pressure"]["status"] == "missing"   # no Thomson -> pressure not built
    assert "pressure" not in meas


def test_east_measurements_strict_raises(monkeypatch):
    _patch_mds(monkeypatch, thomson_ok=False)
    with pytest.raises(RuntimeError):
        run_mod._east_measurements(137985, 4.0, read_point=True,
                                   read_pressure=True, require_diagnostics=True)


def test_east_measurements_ok_surfaces_dropped_count(monkeypatch):
    _patch_mds(monkeypatch, thomson_ok=True)
    meas, extra = run_mod._east_measurements(
        137985, 4.0, read_point=True, read_pressure=True,
        require_diagnostics=False)
    assert extra["diagnostic_status"]["pressure"]["status"] == "ok"
    assert extra["pressure_dropped"] == 2
    assert "pressure" in meas

#: ★The K-17 test that stood here is gone with the function it tested.
#: `_emit_output` placed the EFIT driver's on-disk g-file/a-file into a
#: caller's directory and recycled the solver's tmpfs workdir; no solver in
#: this distribution writes either, nothing called it, and two of its own
#: statements named a session tracker (`_SOLVER`) that has no definition
#: here.  Versioned, non-overwriting delivery is `engine.deliver`, which has
#: its own tests.
