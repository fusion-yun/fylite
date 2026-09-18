"""FR-EQ-026: the MHD delivery layer — every rule is a refusal, and each refusal is falsified here."""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pytest

from fylite import mhd_records as mr

SRC = "Freidberg, Ideal MHD (2014) §12.8, Eq. (12.166)"


def test_energy_principle_records_have_no_growthrate():
    for rec in (mr.kink_record(3, 1, 2.015625, 3.0, 2.0, source=SRC),
                mr.ballooning_record(1.0, 0.6086, source=SRC),
                mr.surface_current_record(1.71, 0.21, source=SRC)):
        assert "growthrate" not in rec["mode"], rec["kind"]


def test_the_assembly_catches_an_energy_principle_record_with_a_growthrate():
    rec = mr.kink_record(3, 1, 2.015625, 3.0, 2.0, source=SRC)
    rec["mode"]["growthrate"] = 0.0          # 0 would read as "neutrally stable"
    with pytest.raises(mr.RecordRefused, match="energy-principle"):
        mr.assemble_time_slice([rec], 1.0)
    # the non-empty control: a vertical mode may carry one
    ok = mr.assemble_time_slice([mr.vertical_mode_record(120.0, ideal_flag=0, regime="resistive_wall")], 1.0)
    assert ok["time_slice"][0]["toroidal_mode"][0]["growthrate"] == 120.0


def test_judged_quantities_ride_in_code_parameters_not_in_dd_fields():
    ids = mr.assemble_time_slice([mr.kink_record(3, 1, 2.015625, 3.0, 2.0, source=SRC),
                                  mr.surface_current_record(1.71, 0.21, source=SRC)], 2.0)
    for mode in ids["time_slice"][0]["toroidal_mode"]:
        assert set(mode) <= mr.DD_MODE_FIELDS
    params = json.loads(ids["code"]["parameters"])
    assert params[0]["q_lower"] == 2.015625 and params[1]["q_star_crit"] == 1.71
    bad = mr.kink_record(3, 1, 2.0, 3.0, 2.0, source=SRC)
    bad["mode"]["q_crit"] = 1.7              # a judged quantity leaking into the mode
    with pytest.raises(mr.RecordRefused, match="not a DD toroidal_mode field"):
        mr.assemble_time_slice([bad], 1.0)


def test_the_dd_field_set_is_the_ids_tables_own():
    table = Path(__file__).resolve().parents[2] / "rust/fylite_runtime/ids/mhd_linear.tsv"
    leaves = {line.split("\t")[0][len("time_slice/toroidal_mode/"):].split("/")[0]
              for line in table.read_text().splitlines() if line.startswith("time_slice/toroidal_mode/")}
    assert mr.DD_MODE_FIELDS <= leaves


def test_l0_is_a_q_limit_and_says_so():
    rec = mr.kink_record(2, 1, 1.0, 2.0, math.inf, source=SRC)
    assert rec["kind"] == "q_limit" and "not a beta limit" in rec["parameters"]["caveat"]


def test_ballooning_leaves_n_phi_empty_unless_given():
    assert "n_phi" not in mr.ballooning_record(1.0, 0.6, source=SRC)["mode"]
    assert mr.ballooning_record(1.0, 0.6, source=SRC, n_phi=20)["mode"]["n_phi"] == 20
    for bad in (0, -3, 2.5, True):
        with pytest.raises(mr.RecordRefused):
            mr.ballooning_record(1.0, 0.6, source=SRC, n_phi=bad)


def test_the_surface_current_record_carries_its_own_caveats():
    cav = " ".join(mr.surface_current_record(1.71, 0.21, source=SRC)["parameters"]["caveat"])
    assert "optimistic" in cav and "cylindrical-equivalent" in cav


def test_an_empty_source_is_refused_for_the_oracle_and_the_scaling():
    for f in (lambda s: mr.surface_current_record(1.71, 0.21, source=s),
              lambda s: mr.scaling_law_record("beta_N", 2.8, source=s)):
        for s in ("", "   "):
            with pytest.raises(mr.RecordRefused, match="source"):
                f(s)


def test_a_scaling_fills_no_dd_field_and_refuses_non_finite():
    ids = mr.assemble_time_slice([mr.scaling_law_record("beta_N (Troyon)", 2.8, source="Troyon et al. 1984")], 0.5)
    assert ids["time_slice"][0]["toroidal_mode"] == []
    assert "empirical" in json.loads(ids["code"]["parameters"])[0]["caveat"]
    for v in (math.nan, math.inf):
        with pytest.raises(mr.RecordRefused, match="not finite"):
            mr.scaling_law_record("beta_N", v, source="Troyon et al. 1984")


def test_ideal_flag_is_never_guessed():
    with pytest.raises(TypeError):
        mr.vertical_mode_record(120.0, regime="resistive_wall")           # no default
    with pytest.raises(mr.RecordRefused, match="must be 0"):
        mr.vertical_mode_record(120.0, ideal_flag=1, regime="resistive_wall")
    with pytest.raises(mr.RecordRefused):
        mr.vertical_mode_record(120.0, ideal_flag=True, regime="ideal")
    assert mr.vertical_mode_record(5e3, ideal_flag=1, regime="ideal")["ideal_flag"] == 1


def test_the_module_imports_only_json_and_math_on_the_syntax_tree():
    tree = ast.parse(Path(mr.__file__).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    # ★the docstring mentions other packages by name — a text grep would trip on it, the tree does not
    assert names == {"__future__", "json", "math"}, names
