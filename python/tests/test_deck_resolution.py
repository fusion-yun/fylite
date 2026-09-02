"""The computational box comes from the deck, and from one place.

★What this file replaces, and why.  Three test modules covered the
Green's-table subsystem — the cache, the official ASIPP set and the grid box
read out of ``ec6565.ddd`` — 15 tests in all, every one of them skipping
because the tables and their generator are removed (LICENSE 3.1).  A test
that can never run is not coverage.  The table-selection grammar that
outlived them (``ensure_tables`` / ``KEFIT_TABLES`` / ``--tables``) is gone
too: it had no caller left and could only ever return the one configured
deck.  What survives is small and real: the box is read from the deck that
defines it, and an explicit path wins over the configured one.
"""
from __future__ import annotations

import pytest

from conftest import requires_machine
from fylite import device

pytestmark = requires_machine


def test_the_box_comes_from_the_fyo_document():
    """★It used to come from ``east_geom.txt``, which said the same thing the
    document already said — ``solver_dims`` and ``machine.default_grid`` —
    down to the last digit.  Two spellings of one box is how they drift."""
    box = device.grid_box()
    assert box["source"] == "fyo:device_document"
    assert (box["nw"], box["nh"]) == (device.NW, device.NH)
    assert tuple(box["grid"]) == tuple(float(v) for v in device.DEFAULT_GRID)
    assert (len(box["rgrid"]), len(box["zgrid"])) == (box["nw"], box["nh"])
    rmin, rmax, zmin, zmax = box["grid"]
    assert box["rgrid"][0] == pytest.approx(rmin)
    assert box["rgrid"][-1] == pytest.approx(rmax)
    assert box["zgrid"][0] == pytest.approx(zmin)
    assert box["zgrid"][-1] == pytest.approx(zmax)


def test_the_geometry_deck_is_read_by_io_and_only_to_check_the_document():
    """★The deck's one surviving job, and why it is not `grid_box`'s.

    ``verify_solver_dims`` exists to catch a declaration that disagrees with
    the shipped artifact — "worse than a literal, because it looks
    authoritative".  It read `grid_box`, which now answers from the document,
    so leaving it there would have made it compare the declaration with
    itself and pass unconditionally: a green light that means nothing.  The
    deck parser is `io.efund` and this is its caller.
    """
    from fylite.io import efund
    geom = device.deck_path("east_geom.txt")
    if not geom.exists():
        pytest.skip(f"no geometry deck at {geom}")
    raw = efund.read_geom_box(geom)
    assert (raw["nw"], raw["nh"]) == (device.NW, device.NH)
    assert tuple(raw["grid"]) == tuple(float(v) for v in device.DEFAULT_GRID)
    assert device.verify_solver_dims()["ok"] is True


def test_a_deck_that_disagrees_with_the_document_is_refused(tmp_path):
    """★The case that proves the check still has teeth.  A box read from the
    document can never contradict the document; one read from a deck can, and
    that contradiction must be loud."""
    p = tmp_path / "geom.txt"
    p.write_text("33 17\n1.0 2.0 0.0 1.0\n")
    with pytest.raises(device.DeviceDocumentError, match="solver_dims"):
        device.verify_solver_dims(p)


def test_the_coil_turns_come_from_the_document_in_efit_order():
    """``TURNFC`` was the sixth column of ``east_geom.txt``; it is
    ``pf_active.coil[].turns`` reordered by each coil's ``efit_index``."""
    turns = device.turnfc()
    assert len(turns) == device.NFCOIL
    assert turns == [float(device.PF_TURNS[i]) for i in device.PF_EFIT_ORDER]


def test_the_probe_positions_come_from_the_fyo_document_not_a_deck():
    """★This used to assert the opposite — that ``source`` was
    ``deck_path("dprobe.dat")``.

    The probe positions are device data, and the browser has always carried
    them in the fyo document; only Python needed a Fortran deck to find out
    where its probes were.  They are in the document now, so the deck is an
    importer (``tools/efund-deck-to-fyo.py``) rather than a reader the
    runtime calls.
    """
    geo = device.probe_geometry()
    assert geo["source"] == "fyo:device_document"
    assert len(geo["r"]) == len(geo["z"]) == len(geo["angle_deg"]) > 0
    assert len(geo["length"]) == len(geo["r"])


def test_no_reader_in_the_package_opens_the_efund_probe_deck():
    """★The boundary itself, not just one function's behaviour.

    ``dprobe.dat`` is a historical remnant: the Python side speaks fyo.  A
    single stray ``_resolve(path, "dprobe.dat")`` would quietly reintroduce
    the second source this migration removed, and the failure mode is silence
    — a machine described in two places that happen to agree today.
    """
    import ast
    import fylite
    from pathlib import Path as _P
    pkg = _P(fylite.__file__).parent

    #: ★the AST, not a grep: this module and `device.py` both DESCRIBE the
    #: deck in prose ("it used to parse `dprobe.dat`"), and a line-based
    #: check calls every one of those a defect.  A string constant that is
    #: not a docstring is a filename the code can actually open.
    def literals(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        doc_nodes = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
                body = getattr(node, "body", None) or []
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    doc_nodes.add(id(body[0].value))
        return [n for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in doc_nodes and "dprobe.dat" in n.value]

    hits = [f"{f.relative_to(pkg)}:{n.lineno}"
            for f in pkg.rglob("*.py") for n in literals(f)]
    assert not hits, ("the efund probe deck is still named by code inside the "
                      "package: " + ", ".join(hits))


def test_device_geometry_names_match_positions():
    geo = device.device_geometry()
    assert len(geo["probes"]["node"]) == len(geo["probes"]["r"])
    assert len(geo["flux_loops"]["node"]) == len(geo["flux_loops"]["r"])
