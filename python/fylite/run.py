"""The EFIT forward solve — an entry that this distribution cannot answer.

★What this module was.  It drove ``libefit.so``, a proprietary EFIT-lineage
solver, through a fork-isolated shared-library call: staging a workdir,
writing k-files and namelists, parsing the solver's output, session reuse,
self-calibration, probe audits.  Two thousand lines of plumbing for one
library, and that library was removed with the EFIT lineage (LICENSE 3.1).

★What replaced it, and why that is gone too.  What survived the removal was
the ability to READ a frozen reference — a fixture reader over a recording
store, with a record/replay hook that could drive a separate checkout of the
reference implementation to fill it.  Both are gone from this distribution
now: the recordings are outputs of a proprietary solver and do not ship, and
the hook named a private repository from a public module.

★★**So this entry raises, and that is the whole of it.**  It never answered
in this distribution either — the store carried no ``efit.*`` record at all,
so every input already raised.  What changed is that it now says so directly
instead of through two layers of machinery that could not reach an answer.

★Routing it to a different solver would be worse than raising: it would hand
back numbers from something else under EFIT's name.  Production forward
solves belong to the kernel's `code/forward` door (`fylite.io.fydoc.complete`)
— the kernel owns physics and numerics.
"""
from __future__ import annotations

class KefitRunError(RuntimeError):
    """A reconstruction failed: bad input, solver abort/timeout, or no g-file."""


def forward_equilibrium(measurements, *, betap0=None, emp=None, enp=None,
                        pprime_coefs=None, ffprim_coefs=None,
                        brsp=None, icprof: int | None = None,
                        extra_namelist=None, **run_kw) -> dict:
    """Solve the equilibrium FORWARD from measurements — **not available here**.

    ★This raises :class:`KefitRunError` for every input, always.  The solver it
    named is not in this distribution and neither are its recorded answers; see
    the module docstring.  The signature is kept so that callers which offer a
    forward-reference path fail at the call with a reason, rather than at an
    attribute lookup with a ``NameError``.

    For a forward free-boundary solve, use the `code/forward` door
    (``fydoc.complete("code/forward", …)``).  That is a different solver and says so — it is not a stand-in that would
    return its own numbers under EFIT's name.

    ★The measured account of what drove the reference solve (which inputs moved
    q0 and q95, and which parameters were inert) was recorded while the solver
    was reachable.  It described that solver's internals and has been removed
    from this package along with it; the account lives with the kernel history.
    """
    raise KefitRunError(
        "efit.forward_equilibrium is not available in this distribution: the "
        "EFIT-lineage solver was removed under LICENSE 3.1, and its recorded "
        "answers are outputs of that solver and do not ship either. "
        "Use the code/forward door for a forward free-boundary solve.")


#: ★★``_diagnostic_signals`` and ``_infer_kind`` were RE-EXPORTED here,
#: from ``scenario.analysis.recon_rs``, "so the assembly helpers keep ONE
#: definition".  They already did: nothing in this module used either name,
#: and the import existed only so a caller could type ``fylite.run.
#: _diagnostic_signals``.  One did — a test — while every other caller went
#: to ``recon_rs`` directly.
#:
#: What it cost was the package's only import CYCLE.  ``recon_rs`` imports
#: ``KefitRunError`` back out of this module, so the two could only be
#: loaded in one order, and `fylite/__init__.py` had to force it by
#: importing ``.run`` before ``.scenario`` — a rule that lived as a comment
#: on an import line and that nothing checked.  With this re-export gone
#: the cycle is gone, ``import fylite.scenario`` stands on its own, and
#: this package's ``__init__`` needs no order at all.
#:
#: A private name re-exported across a package boundary is a second address
#: for one function, and the leading underscore says it should not have had
#: a first public one.
