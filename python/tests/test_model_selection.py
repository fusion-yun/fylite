"""How a model is chosen — and it is no longer by name.

★★★This file was ``test_backends.py`` and its subject was K-18's pluggable
backend REGISTRY, ``engine.backend(family, name)``.  The registry is
retired (FYL-SDD-01 DE-LOG-03).  What it came down to, measured rather than
argued:

* Ten built-ins were four.  ``sauter`` and ``sauter2021`` were one line
  each, selecting a different column of the SAME NEO answer;
  ``profile_fitter`` was a whole family for the string ``"linear"`` vs
  ``"pchip"``; the two ``"none"`` members were null objects
  indistinguishable from the real one.
* Both remaining consumers still had to branch on the NAME.  ``loop.py``
  asked ``backend_meta("current_source")["neo_backed"]`` before it could
  decide what to pass; ``fyo.neoclassical_source`` handled ``redl`` in one
  arm of an ``if`` and then looked up ``solver`` in the other — where the
  lookup had exactly ONE reachable answer.  A name→factory map that gives
  neither of its callers polymorphism is a dict with a ceremony.
* Nothing outside Python read it, and ``register_backend``, the only
  extension point a third party could reach, had no caller but a test.

So a model is CONSTRUCTED where it is chosen, and passed as an object —
which is what ``loop.self_consistent(transport=...)`` already did in the
same signature.  These cases pin what each retired piece became.
"""
import numpy as np
import pytest

from fylite import engine
from fylite.scenario.model import neoclassical as neo


def test_the_registry_is_gone_and_stays_gone():
    """★A retired mechanism that leaves its entry points importable is a
    mechanism with no callers and no gate — which is how the last one came
    to have three families, four built-ins and two consumers that both
    bypassed it.
    """
    import importlib

    for name in ("backend", "backend_names", "backend_meta",
                 "register_backend", "declare_family", "families",
                 "BackendError", "BACKENDS_SPEC_PATH"):
        assert not hasattr(engine, name), (
            f"engine.{name} is back — the pluggable-backend registry was "
            "retired (FYL-SDD-01 DE-LOG-03); a model is constructed where "
            "it is chosen.")
    for mod in ("fylite.engine.registry", "fylite._backends"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)


def test_the_two_current_sources_are_two_kernel_functions():
    """★What the ``current_source`` family came down to, and why it was not
    worth a registry: two classes, chosen by one ``if``.

    They ARE different — ``redl_coefficients`` takes L34 from the ``f31``
    fit at a second effective trapped fraction, NEO's ``sauter_redl`` sets
    ``L34 = L31``, and ``test_redl.py`` pins the gap at 4.1 % / 15.7 %.
    What is not different is how you get one: you name the class.
    """
    assert neo.NeoSource().name == "neo"
    assert neo.RedlSource().name == "redl"


def test_the_profile_interpolant_is_an_argument_not_a_family():
    """★★``profile_fitter`` was a backend family with two members, and the
    whole of the difference between ``LinearFitter`` and ``PchipFitter`` was
    the string they handed one class — which already took it as an argument
    and dispatched it to two kernel entries.  A family, a protocol, two
    classes and two registry entries, for a ``kind=``.

    The default stays byte-identical to the pre-K-18 loop (``np.interp``),
    and the alternative stays reachable, which is the whole of what the
    family provided.
    """
    x, y = [0.0, 0.5, 1.0], [4.0, 3.0, 1.0]
    xq = [0.1, 0.25, 0.75]
    assert np.allclose(engine.fit_profile(x, y)(xq), np.interp(xq, x, y))
    assert np.allclose(engine.fit_profile(x, y, kind="linear")(xq),
                       np.interp(xq, x, y))
    #: pchip is a DIFFERENT interpolant, not a second name for the default —
    #: which is the one thing a two-member family did assert
    assert not np.allclose(engine.fit_profile(x, y, kind="pchip")(xq),
                           np.interp(xq, x, y))
    #: and an unknown kind raises at the fit, not at the first evaluation
    with pytest.raises(ValueError, match="profile kind"):
        engine.fit_profile(x, y, kind="nope")


def test_neo_source_uses_jpar_dke(monkeypatch):
    seen = {}

    def fake_bootstrap(species, **kw):
        seen["kw"] = kw
        return {"jpar_dke": 0.11, "jpar_sauter": 0.07}

    monkeypatch.setattr(neo, "bootstrap", fake_bootstrap)
    surf = [_surface()]
    #: ★the backend returns a CURRENT: NEO's `jpar_dke` times the surface's
    #: own `current_unit` [A·T/m²].  It used to hand back the normalised
    #: number, so this case asserted `== [0.11]` and would have gone on
    #: asserting it whatever unit the caller then read it as.
    assert neo.NeoSource().bootstrap(surf) == [0.11 * 2.0e6]
    # geometry kwargs forwarded, species not in geo kwargs
    assert "rmin_over_a" in seen["kw"] and "species" not in seen["kw"]
    # ...and the two magnitude-bearing numbers travel with them
    assert seen["kw"]["nu_1"] == 0.09 and seen["kw"]["rho_star"] == 2.5e-3


def _surface() -> dict:
    """One surface in the shape :func:`neo.surface_inputs` returns.

    ★``nu_1``/``rho_star``/``current_unit`` are not decoration: NEO's answer
    is linear in ``rho_star``, its magnitude depends on ``nu_1``, and without
    the unit there is no current to report.  A stub that omits them describes
    a callee that does not exist."""
    return {"species": [{"z": -1}], "rmin_over_a": 0.3, "q": 1.5,
            "rmaj_over_a": 3.0, "shear": 0.2, "shift": 0.0, "kappa": 1.4,
            "s_kappa": 0.1, "delta": 0.1, "s_delta": 0.0, "zeta": 0.0,
            "s_zeta": 0.0,
            "nu_1": 0.09, "rho_star": 2.5e-3, "current_unit": 2.0e6}


def test_the_analytic_branches_are_a_key_not_a_backend(monkeypatch):
    """★★``sauter`` and ``sauter2021`` were registered ``current_source``
    backends, which said there were three models.  There is one: a single
    NEO call returns ``jpar_dke``, ``jpar_sauter`` and ``jpar_sauter_2021``
    together, on the same geometry and the same collisionality.

    The give-away was in ``fyo.neoclassical_source``, which carried both
    spellings in ONE SIGNATURE — ``solver="sauter2021"`` and
    ``solver="neo", key="jpar_sauter_2021"`` were the same call — while its
    own docstring said ``key`` was what selected the branch.
    """
    monkeypatch.setattr(neo, "bootstrap",
                        lambda species, **kw: {"jpar_dke": 0.11,
                                               "jpar_sauter": 0.07})
    surf = [_surface()]
    got = neo.NeoSource(key="jpar_sauter").bootstrap(surf)
    assert got == [0.07 * 2.0e6]


def test_asking_for_an_analytic_key_skips_the_drift_kinetic_solve():
    """★The rule the two retired subclasses carried as a hand-written
    ``analytic_only=True``: with it separate from ``key``, the two could
    disagree, and a caller asking for ``jpar_sauter`` could pay 1.3 s per
    surface for a ``jpar_dke`` it discarded.  It follows from the key now.
    """
    assert neo.NeoSource(key="jpar_sauter")._neo_kw["analytic_only"] is True
    assert neo.NeoSource(key="jpar_dke")._neo_kw["analytic_only"] is False
    #: explicit still wins — a caller may want the DKE in `last_solves`
    #: beside an analytic answer
    assert neo.NeoSource(key="jpar_sauter",
                         analytic_only=False)._neo_kw["analytic_only"] is False
    with pytest.raises(neo.NeoclassicalError, match="not one of"):
        neo.NeoSource(key="jpar_nonesuch")


def test_a_null_backend_was_indistinguishable_from_the_real_one():
    """★★``beam_source="none"`` and ``wave_source="none"`` were the family
    DEFAULTS and were null objects — and they returned exactly what the real
    member returns, because ``MetisBeam.deposit`` and ``LHAnalytic.drive``
    both open by returning ``None`` when nothing is configured.  So the null
    member served no call the real one did not, and its cost was real:
    passing ``beams=`` and forgetting ``beam_backend="metis"`` computed no
    beam at all, silently.
    """
    from fylite.scenario.model import lh, nbi

    nothing = dict(eq=None, ne=None, te=None, psin_prof=None)
    assert nbi.MetisBeam().deposit(**nothing) is None
    assert lh.LHAnalytic().drive(**nothing) is None
    assert not hasattr(nbi, "NoBeam") and not hasattr(lh, "NoWave")


def test_a_surface_with_no_unit_is_refused_rather_than_assumed(monkeypatch):
    """★★The defect this contract exists to remove, asserted from the other
    side.  Defaulting a missing ``current_unit`` to 1.0 would hand back NEO's
    normalised number under an amps label — which is precisely what
    ``fyo.neoclassical_source`` did, eight orders from the branch beside it,
    for as long as nobody compared them."""
    monkeypatch.setattr(neo, "bootstrap",
                        lambda species, **kw: {"jpar_dke": 0.11,
                                               "jpar_sauter": 0.07})
    bare = {k: v for k, v in _surface().items() if k != "current_unit"}
    with pytest.raises(neo.NeoclassicalError, match="current_unit"):
        neo.NeoSource().bootstrap([bare])


#: ★``test_register_custom_current_source`` was here.  It registered a
#: throw-away class under ``current_source/const`` and then popped it back
#: out of the live registry dict — and it was ``register_backend``'s ONLY
#: caller in the tree, which is the whole evidence there was that the
#: extension point was reachable.  Substituting a model is now passing one:
#: ``self_consistent(beam_source=<object>)``, pinned by
#: ``test_loop.py::test_a_beam_model_can_be_substituted``.
