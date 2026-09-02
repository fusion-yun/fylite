"""EFIT<->NEO self-consistent loop mechanics (monkeypatched; no MDSplus/solver)."""

from pathlib import Path

import numpy as np
import pytest


#: ★A stub of the reconstruction has to return an EQUILIBRIUM, not a path to
#: one: the real door answers in memory and the loop converts it once, at the
#: top of each round.  A `read_geqdsk` dict is what `fyo.as_equilibrium`
#: accepts, so these stubs stay stubs without asserting a shape the door does
#: not produce.  (`gfile` rides along where a test checks what the archive
#: recorded — that key is the loop's artifact path, not its equilibrium.)
def _eqdict():
    from fylite.io import geqdsk
    return geqdsk.read_geqdsk(
        str(Path(__file__).resolve().parents[2]
            / "tests/data/synthetic/g_synthetic.geqdsk"))


def test_self_consistent_mechanics(monkeypatch):
    from fylite.scenario.analysis import loop as m
    calls = []

    doc = _eqdict()

    def fake_run(shot, t, **kw):
        fsa = kw.get("current_fsa") or {}
        calls.append(fsa)
        if not fsa:                         # base reconstruction
            return {**doc, "gfile": "g", "q0": 1.60, "q95": 4.0,
                    "ne_profile": None}
        # constrained re-run: q0 relaxes toward 1.0 (geometric -> converges)
        prev = calls_q0[-1]
        q0 = 1.0 + 0.3 * (prev - 1.0)
        calls_q0.append(q0)
        return {**doc, "gfile": "g", "q0": q0, "q95": 3.5, "ne_profile": None}

    calls_q0 = [1.60]
    monkeypatch.setattr(m, "_efit_run", fake_run)
    monkeypatch.setattr(m, "_profiles_from_result",
                        lambda res, n=40, **kw: (np.full(40, 4e19),
                                           np.linspace(3000, 100, 40),
                                           np.linspace(0.05, 0.95, 40)))
    monkeypatch.setattr(m.neo_geometry, "surface_inputs",
                        lambda g, **kw: [
                            {"psin": p, "species": [{"z": 1.0}],
                             "rmin_over_a": p, "rmaj_over_a": 3.0, "q": 2.0,
                             "shear": 1.0, "shift": 0.0, "kappa": 1.4,
                             "s_kappa": 0.0, "delta": 0.1, "s_delta": 0.0,
                             "zeta": 0.0, "s_zeta": 0.0,
                             #: ★the three the real `surface_inputs`
                             #: computes.  A stub is a statement about what
                             #: the callee accepts; leaving them out said
                             #: the callee takes a surface with no
                             #: collisionality and no unit, and it does not.
                             "nu_1": 0.08, "rho_star": 3.0e-3,
                             "current_unit": 3.0e6}
                            for p in np.linspace(0.15, 0.9, 8)])
    # the loop routes the bootstrap through the pluggable current-source backend
    # (K-18), which calls neo.bootstrap
    monkeypatch.setattr("fylite.scenario.model.neoclassical.bootstrap",
                        lambda species, **kw: {"jpar_dke": 0.01 * kw["rmin_over_a"]})

    out = m.self_consistent(137985, 4.0, max_iter=8, tol=0.02, n_surfaces=8,
                            bootstrap_fraction=0.3)
    assert out["converged"] and 2 <= out["n_iter"] <= 8
    # the base run had no constraint; every re-run carried the FSA J constraint
    con = [c for c in calls if c]
    #: ★the constraint is the kernel's now, not a namelist's: named
    #: surfaces, a shape in units of its own mean, one weight per row.
    assert con and all("shape" in c for c in con)
    c = con[0]
    n = len(c["x"])
    assert n == 8 and len(c["shape"]) == n
    #: ★`RZEROJ = 0` was EFIT's way of SELECTING the flux-surface-averaged
    #: flavour among several.  There is nothing to select any more: the
    #: kernel's constraint IS the FSA one, so the row that used to carry the
    #: mode carries nothing and is gone.
    assert abs(np.mean(c["shape"]) - 1.0) < 1e-9          # the shape is j/<j>
    # final q0 converged near the 1.0 fixed point
    assert abs(out["result"]["q0"] - 1.0) < 0.05
    # K-15/K-18: cross-round panel + backend provenance on the result
    assert out["convergence_panel"]["converged"] is True
    assert out["convergence_panel"]["iter"][0] == 0
    assert out["current_source"] == "neo" and out["profile_kind"] == "linear"
    #: ★`profile_backend` was the key, and the family behind it is gone: the
    #: two "fitters" differed by this string, so it is what it always was.
    assert out["current_key"] == "jpar_dke"
    # every round carries its staleness snapshot (downstream of a fresh equilibrium)
    assert "constraint" in out["history"][-1]["stale"]


def test_self_consistent_archives_immutable_snapshots(monkeypatch, tmp_path):
    from fylite import engine
    from fylite.scenario.analysis import loop as m
    calls_q0 = [1.60]

    doc = _eqdict()

    def fake_run(shot, t, **kw):
        fsa = kw.get("current_fsa") or {}
        if not fsa:
            return {**doc, "gfile": str(tmp_path / "g0"), "q0": 1.60,
                    "q95": 4.0, "ne_profile": None}
        prev = calls_q0[-1]
        q0 = 1.0 + 0.3 * (prev - 1.0)
        calls_q0.append(q0)
        return {**doc, "gfile": str(tmp_path / "g0"), "q0": q0, "q95": 3.5,
                "ne_profile": None}

    (tmp_path / "g0").write_text("PSI ...")
    monkeypatch.setattr(m, "_efit_run", fake_run)
    monkeypatch.setattr(m, "_profiles_from_result",
                        lambda res, n=40, **kw: (np.full(40, 4e19),
                                           np.linspace(3000, 100, 40),
                                           np.linspace(0.05, 0.95, 40)))
    monkeypatch.setattr(m.neo_geometry, "surface_inputs",
                        lambda g, **kw: [
                            {"psin": p, "species": [{"z": 1.0}],
                             "rmin_over_a": p, "rmaj_over_a": 3.0, "q": 2.0,
                             "shear": 1.0, "shift": 0.0, "kappa": 1.4,
                             "s_kappa": 0.0, "delta": 0.1, "s_delta": 0.0,
                             "zeta": 0.0, "s_zeta": 0.0,
                             #: ★the three the real `surface_inputs`
                             #: computes.  A stub is a statement about what
                             #: the callee accepts; leaving them out said
                             #: the callee takes a surface with no
                             #: collisionality and no unit, and it does not.
                             "nu_1": 0.08, "rho_star": 3.0e-3,
                             "current_unit": 3.0e6}
                            for p in np.linspace(0.15, 0.9, 8)])
    monkeypatch.setattr("fylite.scenario.model.neoclassical.bootstrap",
                        lambda species, **kw: {"jpar_dke": 0.01 * kw["rmin_over_a"]})

    arch = tmp_path / "archive"
    out = m.self_consistent(137985, 4.0, max_iter=6, tol=0.02, n_surfaces=8,
                            bootstrap_fraction=0.3, archive=arch)
    idx = engine.list_snapshots(arch)
    assert idx == list(range(len(idx))) and len(idx) >= 3   # iter-000, 001, ...
    snap1 = engine.load_snapshot(arch, 1)
    assert "shape" in snap1["inputs"] and snap1["state"]["constrained"] is True
    assert "g0" in snap1["artifacts"]                       # g-file archived
    assert out["archive"] == str(arch)


def test_plot_current_components(tmp_path):
    from pathlib import Path
    from fylite import plot
    lr = {"bootstrap_fraction": 0.3, "n_iter": 2, "result": {"q0": 0.78},
          "current": {"psin": [0.1, 0.3, 0.5, 0.7, 0.9],
                      "j_ohm": [2.2, 1.1, 0.4, 0.2, 0.14],
                      "j_bootstrap": [0.28, 0.52, 0.43, 0.2, 0.03],
                      "j_total": [2.48, 1.62, 0.83, 0.4, 0.17]}}
    out = tmp_path / "jcomp.png"
    w = plot.plot_current_components(lr, out, build_time="2026-07-25 00:00:00")
    assert Path(w).exists() and Path(w).stat().st_size > 0
    # K-20: the beam component is drawn only when a beam backend produced one
    lr["current"]["j_nbi"] = [0.5, 0.4, 0.2, 0.05, 0.0]
    lr["current"]["nbi_fraction"] = 0.11
    out2 = tmp_path / "jcomp_nbi.png"
    w2 = plot.plot_current_components(lr, out2, build_time="2026-07-25 00:00:00")
    assert Path(w2).exists() and Path(w2).stat().st_size > Path(w).stat().st_size


def _fake_loop_env(monkeypatch, m, tmp_path):
    """The shared monkeypatch scaffold: no MDSplus, no EFIT, no NEO."""
    calls_q0 = [1.60]
    gfile = str(tmp_path / "g0")
    (tmp_path / "g0").write_text("PSI ...")

    doc = _eqdict()

    def fake_run(shot, t, **kw):
        fsa = kw.get("current_fsa") or {}
        if not fsa:
            return {**doc, "gfile": gfile, "q0": 1.60, "q95": 4.0,
                    "ne_profile": None, "ip": 4.0e5}
        prev = calls_q0[-1]
        q0 = 1.0 + 0.3 * (prev - 1.0)
        calls_q0.append(q0)
        return {**doc, "gfile": gfile, "q0": q0, "q95": 3.5,
                "ne_profile": None, "ip": 4.0e5}

    monkeypatch.setattr(m, "_efit_run", fake_run)
    monkeypatch.setattr(m, "_profiles_from_result",
                        lambda res, n=40, **kw: (np.full(40, 4e19),
                                           np.linspace(3000, 100, 40),
                                           np.linspace(0.05, 0.95, 40)))
    monkeypatch.setattr(m.neo_geometry, "surface_inputs",
                        lambda g, **kw: [
                            {"psin": p, "species": [{"z": 1.0}],
                             "rmin_over_a": p, "rmaj_over_a": 3.0, "q": 2.0,
                             "shear": 1.0, "shift": 0.0, "kappa": 1.4,
                             "s_kappa": 0.0, "delta": 0.1, "s_delta": 0.0,
                             "zeta": 0.0, "s_zeta": 0.0,
                             #: ★the three the real `surface_inputs`
                             #: computes.  A stub is a statement about what
                             #: the callee accepts; leaving them out said
                             #: the callee takes a surface with no
                             #: collisionality and no unit, and it does not.
                             "nu_1": 0.08, "rho_star": 3.0e-3,
                             "current_unit": 3.0e6}
                            for p in np.linspace(0.15, 0.9, 8)])
    monkeypatch.setattr("fylite.scenario.model.neoclassical.bootstrap",
                        lambda species, **kw: {"jpar_dke": 0.01 * kw["rmin_over_a"]})


def test_default_loop_has_no_beam_term(monkeypatch, tmp_path):
    """K-20 must be inert until asked for: with no ``beams`` configured the
    constraint is exactly what it was before beams existed.

    ★★It used to be inert because the family's DEFAULT was a null backend,
    ``beam_backend="none"``.  That member was indistinguishable from the
    real one — ``MetisBeam.deposit`` returns ``None`` when ``beams`` is
    empty — so it bought nothing, and it cost this: passing ``beams=``
    without also passing ``beam_backend="metis"`` computed no beam, in
    silence.  The family has one member and is the default now, so the
    inertness comes from there being no beam rather than from a second way
    of saying so.
    """
    from fylite.scenario.analysis import loop as m
    _fake_loop_env(monkeypatch, m, tmp_path)
    out = m.self_consistent(137985, 4.0, max_iter=4, tol=0.02, n_surfaces=8,
                            bootstrap_fraction=0.3)
    assert out["nbi"] is None and out["fast_pressure"] is None
    assert out["beam_source"] == "metis"
    assert not any(out["current"]["j_nbi"])
    # ohmic + bootstrap alone, exactly as before beams existed
    assert np.allclose(np.asarray(out["current"]["j_ohm"])
                       + np.asarray(out["current"]["j_bootstrap"]),
                       out["current"]["j_total"])


def test_a_beam_model_can_be_substituted(monkeypatch, tmp_path):
    """With a beam configured the constraint gains a third component whose
    weight is |I_NBI|/|I_p| — computed from the model, not passed in.

    ★★And the model is SUBSTITUTED by passing one.  This used to register a
    throw-away class in the live backend registry
    (``engine._backend_families()["beam_source"]["backends"]["stub"] = ...``)
    and select it by name — which was the registry's only exercise of its
    own extension point anywhere in the tree.  ``beam_source=<object>`` is
    the extension point now, and it needs no registration step, no name and
    no reaching into a private dict.
    """
    from fylite.scenario.model import nbi
    from fylite.scenario.analysis import loop as m
    _fake_loop_env(monkeypatch, m, tmp_path)
    fake = {"psin": np.linspace(0.05, 0.95, 12),
            "j_nbi": np.linspace(2.0e5, 0.0, 12),
            "p_fast": np.linspace(5.0e3, 0.0, 12),
            "i_nbi": 4.0e4}

    class _Stub:
        name = "stub"

        def deposit(self, **kw):
            return fake

    out = m.self_consistent(137985, 4.0, max_iter=4, tol=0.02, n_surfaces=8,
                            bootstrap_fraction=0.3, beam_source=_Stub(),
                            beams=[nbi.Beam(energy=6e4, power=2e6,
                                            tangency_radius=1.26)])
    assert out["beam_source"] == "stub"
    c = out["current"]
    assert c["nbi_fraction"] == pytest.approx(4.0e4 / 4.0e5)      # = 0.1
    assert any(c["j_nbi"])
    assert np.allclose(np.asarray(c["j_ohm"]) + np.asarray(c["j_bootstrap"])
                       + np.asarray(c["j_nbi"]), c["j_total"])
    # the ohmic share shrank by exactly the beam's share
    assert np.mean(c["j_ohm"]) == pytest.approx(1.0 - 0.3 - 0.1)
    assert np.mean(c["j_nbi"]) == pytest.approx(0.1)
    # the pressure channel comes back too, but is not silently applied
    assert out["fast_pressure"]["p_fast"][0] == pytest.approx(5.0e3)


def test_the_departed_drivers_two_arguments_are_refused_not_ignored():
    """★``out`` and ``final_uncertainty`` named the EFIT driver's file
    output and its uncertainty pass.  The driver left with LICENSE 3.1 and
    the Rust reconstruction answers in memory, so neither can be honoured —
    and an argument that is accepted and then does nothing is the exact
    failure this loop just came out of (a constraint addressed to a reader
    that is not there).  It must REFUSE, before any work is done.
    """
    import pytest

    from fylite.scenario.analysis import loop as m

    for kw in ({"out": "/tmp/somewhere"}, {"final_uncertainty": 8}):
        with pytest.raises(NotImplementedError) as e:
            m.self_consistent(137985, 4.0, **kw)
        #: the message has to name the replacement, not just the loss
        assert "write_geqdsk" in str(e.value)


def test_the_history_records_how_many_constraint_rows_actually_held(monkeypatch):
    """★The loop asks for one FSA row per surface; the kernel reports how
    many reached the fit.  A round that imposed fewer than it wrote must say
    so in its own record — a history that only carries `constrained: True`
    reads as if the constraint held everywhere, which is the one thing the
    count exists to deny.
    """
    from fylite.scenario.analysis import loop as m
    doc = _eqdict()
    calls_q0 = [1.60]

    def fake_run(shot, t, **kw):
        fsa = kw.get("current_fsa") or {}
        if not fsa:
            return {**doc, "gfile": "g", "q0": 1.60, "q95": 4.0,
                    "ne_profile": None}
        prev = calls_q0[-1]
        q0 = 1.0 + 0.3 * (prev - 1.0)
        calls_q0.append(q0)
        #: the kernel's answer when two of the requested surfaces would not
        #: trace on this field
        return {**doc, "gfile": "g", "q0": q0, "q95": 3.5,
                "ne_profile": None, "fsa_rows_used": len(fsa["x"]) - 2}

    monkeypatch.setattr(m, "_efit_run", fake_run)
    monkeypatch.setattr(m, "_profiles_from_result",
                        lambda res, eq=None, n=40, **kw: (
                            np.full(40, 4e19), np.linspace(3000, 100, 40),
                            np.linspace(0.05, 0.95, 40)))
    monkeypatch.setattr(m.neo_geometry, "surface_inputs",
                        lambda g, **kw: [
                            {"psin": p, "species": [{"z": 1.0}],
                             "rmin_over_a": p, "rmaj_over_a": 3.0, "q": 2.0,
                             "shear": 1.0, "shift": 0.0, "kappa": 1.4,
                             "s_kappa": 0.0, "delta": 0.1, "s_delta": 0.0,
                             "zeta": 0.0, "s_zeta": 0.0,
                             "nu_1": 0.08, "rho_star": 3.0e-3,
                             "current_unit": 3.0e6}
                            for p in np.linspace(0.15, 0.9,
                                                 kw["n_surfaces"])])
    monkeypatch.setattr("fylite.scenario.model.neoclassical.bootstrap",
                        lambda species, **kw: {"jpar_dke": 1e-3})

    out = m.self_consistent(137985, 4.0, max_iter=2, tol=1e-9, n_surfaces=6)
    con = [r for r in out["history"] if r.get("constrained")]
    assert con, "no constrained round happened"
    for r in con:
        assert r["fsa_rows_asked"] == 6
        assert r["fsa_rows_used"] == 4, (
            "the round reported the number it ASKED for, not the number that "
            "held")
