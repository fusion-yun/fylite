"""The device's linear electromagnetic model, exported (FR-EQ-015).

    dI/dt = A I + B v ,     y = C I + D v

``I`` holds the circuit currents (active coils, passive structure), ``v`` the supply voltages,
``y`` the magnetic diagnostics.  The model is assembled from matrices this repository already
computes — the kernel's ``code/vstab`` door (:func:`fylite.scenario.control.vertical.vertical_system`)
gives the inductances, resistances, the plasma coupling gradient and the flux-loop rows — so this
module does linear algebra and shaping, nothing else.

★**The plasma response is a PARAMETER, not a function name** (FYTOK-ADR-118 D2): one entry,
``plasma_response`` =

* ``"static"`` — the plasma current is frozen and does not move: ``M_eff = M``;
* ``"rigid"``  — the massless rigid vertical displacement: force balance ``k ξ + I_p Gᵀ I = 0``
  eliminates ξ and leaves ``M_eff = M − (I_p²/k) G Gᵀ``;
* ``"perturbed_gs"`` — a perturbed Grad–Shafranov response: **not implemented, refused by name**.

``A = −M_eff⁻¹ R``, ``B = M_eff⁻¹ B_act``.  The vertical-instability reading travels WITH the model:
``gamma`` is the largest real eigenvalue of ``A``.  ★In the resistive-wall regime ``M_eff`` has exactly
one negative eigenvalue — that IS the unstable mode.  Beyond the ideal limit (``k ≥ k_ideal =
I_p² Gᵀ M⁻¹ G``) ``M_eff`` turns positive definite and ``A`` would read "stable", while the massless
model's growth is infinite: the export is **refused** there rather than invent an answer.

The carrier is IMAS ``em_coupling`` (DD 4.1.1): each matrix is one ``coupling_matrix`` entry with
``name``, ``quantity``, ``rows_uri``, ``columns_uri`` and ``data`` — no parallel data model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

PLASMA_RESPONSES = ("static", "rigid", "perturbed_gs")


class ModelRefused(ValueError):
    """An export that would not mean anything."""


@dataclass
class LinearModel:
    A: np.ndarray
    B: np.ndarray
    C: np.ndarray | None
    D: np.ndarray | None
    M_eff: np.ndarray
    R: np.ndarray
    gamma: float                      # largest real eigenvalue of A [1/s]
    plasma_response: str
    state_names: list = field(default_factory=list)
    input_names: list = field(default_factory=list)
    output_names: list = field(default_factory=list)


def linear_model(M, R, *, plasma_response: str = "static", ip: float = 0.0, G=None, k: float | None = None,
                 B_act=None, C=None, C_xi=None, P_loops=None,
                 state_names=None, input_names=None, output_names=None) -> LinearModel:
    """Assemble ``(A, B, C, D)`` from the circuit matrices and the chosen plasma response.

    ``M`` (n, n) inductances [H]; ``R`` (n,) or (n, n) resistances [Ω]; ``G`` (n,) coupling gradient
    [Wb/(A m)]; ``k`` external-field stiffness [N/m] (> 0 destabilising); ``B_act`` (n, n_in)
    voltage injection; ``C`` (n_out, n) diagnostic response to the circuit currents; with the rigid
    response the plasma shift ξ = ``C_xi`` · I adds ``P_loops ⊗ C_xi`` to the outputs.
    """
    if plasma_response not in PLASMA_RESPONSES:
        raise ModelRefused(f"plasma_response = {plasma_response!r}: one of {PLASMA_RESPONSES}")
    if plasma_response == "perturbed_gs":
        raise ModelRefused("plasma_response = 'perturbed_gs' is not implemented in fylite: "
                           "only 'static' and 'rigid' are delivered")
    M = np.asarray(M, float)
    n = M.shape[0]
    Rm = np.diag(np.asarray(R, float)) if np.ndim(R) == 1 else np.asarray(R, float)
    if M.shape != (n, n) or Rm.shape != (n, n) or not np.allclose(M, M.T, rtol=1e-12, atol=0.0):
        raise ModelRefused("M must be a symmetric (n, n) matrix and R (n,) or (n, n)")
    M_eff = M.copy()
    Cy = None if C is None else np.asarray(C, float).copy()
    if plasma_response == "rigid":
        if G is None or k is None:
            raise ModelRefused("the rigid response needs G and k")
        G = np.asarray(G, float)
        if not k > 0.0:
            raise ModelRefused(f"k = {k}: the rigid vertical response is defined for a destabilising field (k > 0)")
        M_eff = M - (ip * ip / k) * np.outer(G, G)
        if Cy is not None and C_xi is not None and P_loops is not None:
            Cy = Cy + np.outer(np.asarray(P_loops, float), np.asarray(C_xi, float))
    try:
        np.linalg.cholesky(M)
    except np.linalg.LinAlgError:
        raise ModelRefused("M is not positive definite: not a set of passive circuits") from None
    if plasma_response == "rigid":
        #: ★k_ideal = I_p² Gᵀ M⁻¹ G.  In the resistive-wall regime (k < k_ideal) M_eff carries exactly ONE
        #: negative eigenvalue — that is the unstable vertical mode, not an error.  At k >= k_ideal M_eff turns
        #: positive definite and A would read "stable": the massless model's growth is infinite there.
        k_ideal = ip * ip * float(G @ np.linalg.solve(M, G))
        if k >= k_ideal:
            raise ModelRefused(f"k = {k:.6g} >= k_ideal = {k_ideal:.6g}: beyond the ideal limit the massless rigid "
                               "plasma grows infinitely fast — no finite model to export")
    A = -np.linalg.solve(M_eff, Rm)
    B = None if B_act is None else np.linalg.solve(M_eff, np.asarray(B_act, float))
    D = None if (Cy is None or B is None) else np.zeros((Cy.shape[0], B.shape[1]))
    gamma = float(np.max(np.linalg.eigvals(A).real))
    return LinearModel(A=A, B=B if B is not None else np.zeros((n, 0)), C=Cy, D=D, M_eff=M_eff, R=Rm, gamma=gamma,
                       plasma_response=plasma_response,
                       state_names=list(state_names or [f"circuit({i + 1})" for i in range(n)]),
                       input_names=list(input_names or []), output_names=list(output_names or []))


def from_vertical_system(vs, *, plasma_response: str = "rigid", state_names=None, output_names=None) -> LinearModel:
    """The same model from :func:`fylite.scenario.control.vertical.vertical_system`'s plant.

    ``vs.M_star`` is already the rigid-corrected inductance; the static response undoes that
    correction (``M = M* + (I_p²/k) G Gᵀ``) so both tiers come from ONE set of kernel matrices.
    """
    M = vs.M_star + (vs.ip * vs.ip / vs.k) * np.outer(vs.G, vs.G)
    return linear_model(M, vs.R, plasma_response=plasma_response, ip=vs.ip, G=vs.G, k=vs.k,
                        B_act=vs.B_act, C=vs.loops_C, C_xi=vs.C_xi, P_loops=vs.loops_P,
                        state_names=state_names, output_names=output_names)


#: the em_coupling leaves this export writes (checked against the IDS table by the tests)
EM_COUPLING_FIELDS = ("coupling_matrix/name", "coupling_matrix/quantity/name", "coupling_matrix/quantity/description",
                      "coupling_matrix/rows_uri", "coupling_matrix/columns_uri", "coupling_matrix/data")


def to_em_coupling(model: LinearModel) -> dict:
    """The model as an ``em_coupling`` document: one ``coupling_matrix`` per matrix, plus the γ reading
    in ``code.parameters`` (a judged quantity — never a DD physics field)."""
    import json
    s, i, o = model.state_names, model.input_names, model.output_names
    entries = [("M_eff", "inductance", "H", s, s, model.M_eff), ("R", "resistance", "Ohm", s, s, model.R),
               ("A", "state_matrix", "1/s", s, s, model.A)]
    if model.B.shape[1]:
        entries.append(("B", "input_matrix", "A/(V s)", s, i or [f"input({j + 1})" for j in range(model.B.shape[1])], model.B))
    if model.C is not None:
        entries.append(("C", "output_matrix", "mixed", o or [f"output({j + 1})" for j in range(model.C.shape[0])], s, model.C))
    if model.D is not None:
        entries.append(("D", "feedthrough_matrix", "mixed", o or [f"output({j + 1})" for j in range(model.D.shape[0])],
                        i or [f"input({j + 1})" for j in range(model.D.shape[1])], model.D))
    return {"ids_properties": {"homogeneous_time": 2, "comment": f"fylite linear model, plasma_response = {model.plasma_response}"},
            "coupling_matrix": [{"name": name, "quantity": {"name": q, "description": f"{q} [{u}]"},
                                 "rows_uri": list(r), "columns_uri": list(c), "data": np.asarray(d, float).tolist()}
                                for name, q, u, r, c, d in entries],
            "code": {"name": "fylite", "parameters": json.dumps({"plasma_response": model.plasma_response,
                                                                   "gamma_per_s": model.gamma})}}
