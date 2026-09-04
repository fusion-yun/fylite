"""The case-report face: plan + record -> MyST + SVG through a presentation spec.

★What is gated is §13's discipline (FYL-REPORT-06), not prose taste:

* P1 — the derived spec copies no number: every series BINDS a quantity by
  `<dataset id>#<path>`, and the report inlines no array;
* P2 — the abscissa is the quantity's own coordinate: a profile under
  `profiles_1d/electrons/` is drawn against `profiles_1d/grid/rho_tor`, a trace
  of the summary's length against `time`, and a one-sample array is a READING;
* the poloidal section is drawn exactly when an equilibrium dataset carries a
  boundary outline, and refused BY NAME otherwise — with the rest rendered;
* the five sections come in the run-report order, tables captioned above,
  figures below, and every figure directive names a file that exists.

The rule tests run on a hand-shaped record (no kernel); the last one drives
the real JSON door on the corpus and skips where the data library is absent.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fylite.engine import casereport as cr
from fylite.engine.report import SECTIONS

ROOT = Path(__file__).resolve().parents[2]


def _record(*, with_outline: bool = True) -> dict:
    rho = [i / 10 for i in range(11)]
    t = [0.0, 0.5, 1.0]
    cp = {"id": "run/x/core_profiles", "type": "fyo:core_profiles",
          "comment": ["profiles_1d/grid/rho_tor [m] [11]", "profiles_1d/electrons/temperature [eV] [11]",
                      "profiles_1d/t_i_average [eV] [11]", "profiles_1d/electrons/density [m^-3] [11]"],
          "profiles_1d": {"grid": {"rho_tor": rho},
                          "electrons": {"temperature": [1000 * (1 - r * r) + 10 for r in rho],
                                        "density": [1e19 * (1 - r) for r in rho]},
                          "t_i_average": [800 * (1 - r * r) + 10 for r in rho]}}
    sm = {"id": "run/x/summary", "type": "fyo:summary",
          "comment": ["time [s] [3]", "local/magnetic_axis/t_e/value [eV] [3]"],
          "time": t, "local": {"magnetic_axis": {"t_e": {"value": [1000.0, 1100.0, 1150.0]}}}}
    eq = {"id": "run/x/equilibrium", "type": "fyo:equilibrium",
          "comment": ["time [s] [1]", "time_slice/global_quantities/magnetic_axis/r [m] [1]",
                      "time_slice/boundary/outline/r [m] [5]", "time_slice/boundary/outline/z [m] [5]"],
          "time": [1.0], "time_slice": [{"global_quantities": {"magnetic_axis": {"r": [1.8], "z": [0.0]}},
                                         "profiles_1d": {"rho_tor": rho, "dvolume_drho_tor": [2 * r for r in rho]}}]}
    if with_outline:
        eq["time_slice"][0]["boundary"] = {"outline": {"r": [2.4, 1.8, 1.2, 1.8, 2.4], "z": [0.0, 1.0, 0.0, -1.0, 0.0]}}

    def port(name, doc):
        return {"type": "spo:PortBinding", "binds_port": {"type": "spo:PortDefinition", "port_name": name,
                                                           "port_direction": "output"}, "bound_to": doc}
    return {"id": "run/x", "type": "spo:ComputationRecord", "run_state": "succeeded",
            "started_at": "2026-09-02T00:00:00Z", "ended_at": "2026-09-02T00:00:01Z",
            "realizes": {"id": "cases/evolve-default", "type": "fyo:ScenarioSpecification"},
            "executed_code": {"id": "code/evolve", "type": "spo:Code", "name": "fylite", "version": "abi 125"},
            "parameters": [{"type": "spo:ParameterSetting", "sets_parameter": "code/evolve#te0", "literal_value": 3}],
            "inputs": [port("core_profiles", cp), port("summary", sm), port("equilibrium", eq)]}


def test_the_derived_spec_binds_quantities_and_copies_no_number():
    spec = cr.derive_presentation(None, _record())
    assert spec["type"] == "spo:PresentationSpecification"
    text = json.dumps(spec)
    assert "1e+19" not in text and "1000" not in text.replace("1000 *", ""), "a number leaked into the spec"
    refs = [s["binds_quantity"] for p in spec["has_panel"] for v in p["has_view"] for s in v.get("has_series", [])]
    assert refs and all(re.match(r"^run/x/\w+#[\w/:]+$", r) for r in refs), refs


def test_a_profile_sits_on_its_containers_grid_and_a_trace_on_time():
    spec = cr.derive_presentation(None, _record())
    charts = [(v["comment"], [s["binds_quantity"] for s in v["has_series"]])
              for p in spec["has_panel"] for v in p["has_view"] if v["view_kind"] == "line_chart"]
    te = "run/x/core_profiles#profiles_1d/electrons/temperature"
    ti = "run/x/core_profiles#profiles_1d/t_i_average"
    ne = "run/x/core_profiles#profiles_1d/electrons/density"
    te_chart = next(c for c in charts if te in c[1])
    assert te_chart[0] == "abscissa run/x/core_profiles#profiles_1d/grid/rho_tor"
    assert ti in te_chart[1], "same units, same grid -> one chart"
    assert ne not in te_chart[1], "other units -> its own chart"
    ne_chart = next(c for c in charts if ne in c[1])
    assert ne_chart[0] == te_chart[0]
    tr = next(c for c in charts if "run/x/summary#local/magnetic_axis/t_e/value" in c[1])
    assert tr[0] == "abscissa run/x/summary#time"


def test_a_one_sample_array_is_a_reading_not_a_curve():
    spec = cr.derive_presentation(None, _record())
    readings = [s["binds_quantity"] for p in spec["has_panel"] if p["panel_kind"] == "readings"
                for v in p["has_view"] for s in v["has_series"]]
    assert "run/x/equilibrium#time_slice/global_quantities/magnetic_axis/r" in readings
    curves = [s["binds_quantity"] for p in spec["has_panel"] for v in p["has_view"]
              if v["view_kind"] == "line_chart" for s in v["has_series"]]
    assert not any("magnetic_axis/r" in c for c in curves)


def test_the_poloidal_section_is_drawn_with_an_outline_and_refused_by_name_without(tmp_path):
    spec = cr.derive_presentation(None, _record())
    maps = [v for p in spec["has_panel"] for v in p["has_view"] if v.get("type") == "fyo:PoloidalSectionView"]
    assert len(maps) == 1 and maps[0]["flux_layer"] == "run/x/equilibrium"
    spec2 = cr.derive_presentation(None, _record(with_outline=False))
    assert not [v for p in spec2["has_panel"] for v in p["has_view"] if v.get("type") == "fyo:PoloidalSectionView"]
    assert any("PoloidalSectionView refused by name" in c for c in spec2["caveat"])
    #: and the rest still renders
    dest = cr.render(_record(with_outline=False), out=tmp_path / "r2")
    assert dest.is_file() and (tmp_path / "r2" / "figures").is_dir()


def test_the_report_keeps_the_template_and_every_figure_exists(tmp_path):
    dest = cr.render(_record(), out=tmp_path / "r")
    text = dest.read_text(encoding="utf-8")
    heads = re.findall(r"^## (.+)$", text, re.M)
    assert heads == list(SECTIONS), heads
    figs = re.findall(r"^:::\{figure\} (\S+)$", text, re.M)
    assert figs and all((tmp_path / "r" / f).is_file() for f in figs), figs
    assert re.search(r"^:::\{table\} 表 \d：", text, re.M)
    #: no bulk array: no line with more than four numbers in a row
    assert not re.search(r"(-?\d+(\.\d+)?(e[+-]?\d+)?,\s*){5,}", text)
    svg = (tmp_path / "r" / figs[0]).read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "<path" in svg
    assert (tmp_path / "r" / "presentation.jsonld").is_file()


def test_a_supplied_presentation_is_drawn_as_given(tmp_path):
    spec = {"type": "spo:PresentationSpecification", "id": "run/x/custom", "presents": ["run/x"],
            "has_panel": [{"type": "spo:Panel", "panel_kind": "results", "has_view": [
                {"type": "spo:View", "view_kind": "line_chart", "caption": {"zh": "只画 Te", "en": "Te only"},
                 "has_series": [{"type": "spo:Series", "binds_quantity": "run/x/core_profiles#profiles_1d/electrons/temperature",
                                 "series_role": "computed", "line_style": "dashed"}]},
                {"type": "spo:View", "view_kind": "verdict", "caption": {"zh": "判定", "en": "verdict"}}]}]}
    dest = cr.render(_record(), out=tmp_path / "c", presentation=spec)
    text = dest.read_text(encoding="utf-8")
    assert text.count(":::{figure}") == 1 and "只画 Te" in text
    assert "未渲染" in text and "comparison record" in text   # the verdict view refused by name
    assert "stroke-dasharray" in (tmp_path / "c" / "figures" / "fig-01.svg").read_text()


def test_the_corpus_case_renders_through_the_json_door(tmp_path):
    from fylite import kernel
    try:
        kernel.require_data()
    except Exception as exc:                                  # noqa: BLE001
        pytest.skip(f"data library not available: {exc}")
    if not (ROOT / "cases" / "catalogue.jsonld").is_file():
        pytest.skip("corpus not in this checkout")
    dest = cr.run_and_render("evolve-default", ROOT / "cases", out=tmp_path / "e")
    text = dest.read_text(encoding="utf-8")
    assert "run_state" not in text.split("## 结果")[0] or "succeeded" in text
    assert text.count(":::{figure}") >= 5
    spec = json.loads((tmp_path / "e" / "presentation.jsonld").read_text(encoding="utf-8"))
    assert any(v.get("type") == "fyo:PoloidalSectionView" for p in spec["has_panel"] for v in p["has_view"])
