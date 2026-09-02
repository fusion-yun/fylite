"""Immutable iteration versioning + staleness (K-15; engine concern 3).

Write-once ``iter-NNN`` snapshots of a loop, the downstream-staleness
tracker over the stage graph, and the cross-round convergence panel.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


# =========================================================================== #
# Immutable iteration versioning + staleness propagation (K-15)
# =========================================================================== #
STAGES = ("equilibrium", "profiles", "mapping", "bootstrap", "beam", "wave",
          "constraint")
_EDGES = {
    "equilibrium": ("profiles", "mapping", "beam", "wave"),
    "profiles": ("bootstrap", "beam", "wave"),
    "mapping": ("bootstrap",),
    "bootstrap": ("constraint",),
    # K-20: the beam deposition reads the equilibrium geometry and the kinetic
    # profiles, and feeds the current constraint alongside the bootstrap.
    "beam": ("constraint",),
    # K-20 (LH): the wave deposition reads the same equilibrium geometry and
    # kinetic profiles, and feeds the current decomposition.
    "wave": ("constraint",),
    "constraint": ("equilibrium",),
}


class Staleness:
    """Downstream staleness tracker over the loop's stage dependency graph.

    ``invalidate(stage)`` marks that stage and everything reachable downstream
    stale (terminating at already-stale nodes, so the ``constraint→equilibrium``
    cycle is safe); ``refresh(stage)`` clears one stage once it is recomputed.
    ``stale`` is the current stale set.
    """

    def __init__(self, edges: dict | None = None):
        self._edges = edges or _EDGES
        self.stale: set[str] = set()

    def invalidate(self, stage: str) -> set[str]:
        """Mark ``stage`` + its downstream cone stale; return the newly-marked set."""
        added: set[str] = set()
        stack = [stage]
        while stack:
            s = stack.pop()
            if s in self.stale:
                continue
            self.stale.add(s)
            added.add(s)
            stack.extend(self._edges.get(s, ()))
        return added

    def refresh(self, stage: str) -> None:
        """Clear ``stage`` (it has just been recomputed against fresh upstreams)."""
        self.stale.discard(stage)

    def downstream(self, stage: str) -> set[str]:
        """The forward cone of ``stage`` (all reachable successors, excluding it)."""
        seen: set[str] = set()
        stack = list(self._edges.get(stage, ()))
        while stack:
            s = stack.pop()
            if s == stage or s in seen:
                continue
            seen.add(s)
            stack.extend(self._edges.get(s, ()))
        return seen

    def recomputed(self, stage: str) -> set[str]:
        """Mark ``stage`` fresh and (re)staleify its whole downstream cone.

        This is the per-round equilibrium event: a fresh equilibrium is itself
        current, but every stage derived from it (profiles/mapping/bootstrap/
        constraint) is now stale until recomputed — even if it was fresh a moment
        ago.  Returns the (re)staled downstream set.
        """
        self.refresh(stage)
        cone = self.downstream(stage)
        self.stale |= cone
        return cone

    def is_stale(self, stage: str) -> bool:
        return stage in self.stale

    def snapshot(self) -> list[str]:
        """Stale stages in canonical stage order (JSON-friendly)."""
        return [s for s in STAGES if s in self.stale]


class SnapshotError(RuntimeError):
    """An immutable snapshot index already exists (write-once violated)."""


def snapshot(archive, index: int, *, inputs=None, state=None,
             artifacts=None) -> Path:
    """Archive one iteration as a write-once ``iter-NNN`` directory.

    ``inputs`` (e.g. the constraint namelist) → ``inputs.json``; ``state`` (q₀,
    q95, |Δq₀|, current components) → ``state.json``; ``artifacts`` (on-disk
    paths, e.g. the round's g-file) are copied in.  Refuses to overwrite an
    existing index — iterations are immutable versions.  Returns the dir.
    """
    root = Path(archive)
    root.mkdir(parents=True, exist_ok=True)
    d = root / f"iter-{int(index):03d}"
    if d.exists():
        raise SnapshotError(f"snapshot {d} already exists (immutable)")
    d.mkdir()
    if inputs is not None:
        (d / "inputs.json").write_text(json.dumps(inputs, indent=2, default=str))
    if state is not None:
        (d / "state.json").write_text(json.dumps(state, indent=2, default=str))
    for a in (artifacts or []):
        p = Path(a)
        if p.is_file():
            shutil.copyfile(p, d / p.name)
    return d


def load_snapshot(archive, index: int) -> dict:
    """Read back an archived iteration's ``inputs``/``state`` + artifact names."""
    d = Path(archive) / f"iter-{int(index):03d}"
    if not d.is_dir():
        raise SnapshotError(f"no snapshot {d}")

    def _read(name):
        p = d / name
        return json.loads(p.read_text()) if p.is_file() else None

    arts = [p.name for p in d.iterdir()
            if p.name not in ("inputs.json", "state.json")]
    return {"dir": str(d), "index": int(index), "inputs": _read("inputs.json"),
            "state": _read("state.json"), "artifacts": sorted(arts)}


def list_snapshots(archive) -> list[int]:
    """Indices of the archived iterations, ascending."""
    root = Path(archive)
    if not root.is_dir():
        return []
    idx = []
    for d in root.glob("iter-*"):
        try:
            idx.append(int(d.name.split("-")[1]))
        except (IndexError, ValueError):
            continue
    return sorted(idx)


def convergence_panel(history: list[dict]) -> dict:
    """Cross-round quality panel from the loop's per-round ``history``.

    Returns aligned ``iter``/``q0``/``q95``/``dq0`` series plus ``converged``
    (last ``dq0`` under ``tol`` when carried) and ``n_iter`` — the data a
    convergence panel renders without re-deriving anything from the loop.
    """
    hist = list(history or [])
    return {
        "iter": [h.get("iter") for h in hist],
        "q0": [h.get("q0") for h in hist],
        "q95": [h.get("q95") for h in hist],
        "dq0": [h.get("dq0") for h in hist],
        "stale": [h.get("stale") for h in hist],
        "n_iter": max((h.get("iter", 0) for h in hist), default=0),
        "converged": bool(hist and hist[-1].get("converged")),
    }
