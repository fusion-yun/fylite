"""kinetic_input.py 的纯函数：输入文件的规范化与查错、设定映射、置信度、电流分箱（不载 libfylite.so）。"""
import copy
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kinetic_input as KI  # noqa: E402
import kinetic_recon as K  # noqa: E402


def doc(**over):
    d = {"@type": KI.TYPE, "data": {"file": "pull.json"}}
    d.update(over)
    return d


def test_defaults_fill_every_key_and_everything_but_pressure_is_off():
    d = KI.normalize(doc())
    assert set(d) == set(KI.DEFAULTS)
    assert d["pressure"]["on"] and not d["pedestal"]["on"] and not d["q0"]["on"]
    assert not d["currents"]["bootstrap"]["on"] and not d["currents"]["external"]["on"] and not d["ip"]["on"]


@pytest.mark.parametrize("bad", [
    {"basis": {"pprime": {"mode": "cubic"}}},
    {"basis": {"ffprime": {"mode": "spline", "knots": [0, 1]}}},
    {"basis": {"pprime": {"mode": "fixed", "psin": [0, 1], "value": [1]}}},
    {"currents": {"bootstrap": {"use": "both"}}},
    {"currents": {"external": {"on": True, "psin": [0, 1], "j": [1]}}},
    {"q0": {"on": True, "sigma": 0}},
    {"pressure": {"source": "profile", "profile": {"psin": [0, 1], "p": [1, 0], "sigma": [1, 1]}}},
])
def test_bad_inputs_are_refused(bad):
    with pytest.raises(SystemExit):
        KI.normalize(doc(**bad))


def test_unknown_top_level_key_is_refused():
    with pytest.raises(SystemExit, match="不认识的键"):
        KI.normalize(doc(pedstal={"on": True}))


def test_fit_settings_map_to_kernel_keys():
    d = KI.normalize(doc(q0={"on": True, "target": 1.05, "sigma": 0.05}, ip={"on": True, "sigma_A": 3000.0},
                         pedestal={"on": True, "x": 0.94, "w": 0.02, "ffprime": True},
                         basis={"pprime": {"mode": "spline", "knots": [0, 0.5, 0.95, 1.0], "tension": 2.0},
                                "ffprime": {"mode": "poly", "n": 3, "edge_zero": False}}))
    st, disc, cons, _ = KI.fit_settings(d, 201)
    assert st["q0_target"] == 1.05 and st["q0_weight"] == pytest.approx(20.0)     #: 1/σ in q units
    assert st["ip_sigma"] == 3000.0
    assert st["pprime_ped_x"] == 0.94 and st["ffprime_ped_w"] == 0.02
    assert st["pprime_basis"] == "spline" and st["pprime_knots"] == "0.0 0.5 0.95 1.0" and st["pprime_edge"] == "zero"
    assert st["ffprime_basis"] == "poly_free" and st["nff"] == 3
    assert not disc and len(cons) >= 5


def test_fixed_profile_is_resampled_on_the_kernel_grid():
    d = KI.normalize(doc(basis={"pprime": {"mode": "fixed", "psin": [0.0, 1.0], "value": [2.0, 0.0]}}))
    st, disc, _, _ = KI.fit_settings(d, 11)
    assert st["pprime_basis"] == "fixed"
    v = disc["fylite:pprime_fixed"]
    assert len(v) == 11 and v[0] == 2.0 and v[-1] == 0.0 and v[5] == pytest.approx(1.0)


def test_point_confidence_scales_the_weights_and_zero_turns_a_chord_off():
    meas = {"point": {"fwtpol": [1.0, 1.0, 1.0], "fwtnel": [1.0, 0.0, 1.0]}}
    d = KI.normalize(doc(point={"faraday": [1.0, 0.0, 2.0], "density": [0.5, 1.0, 1.0]}))
    m = KI.apply_point(meas, d)
    assert m["point"]["fwtpol"] == [1.0, 0.0, 2.0] and m["point"]["fwtnel"] == [0.5, 0.0, 1.0]
    assert meas["point"]["fwtpol"] == [1.0, 1.0, 1.0]                       #: the caller's document is untouched


def test_thomson_confidence_divides_sigma_and_zero_drops_the_point():
    th = {"te": [1000.0, 1000.0, 1000.0], "ne": [3e19, 3e19, 3e19], "r": [1.8, 1.9, 2.0], "z": [0.0] * 3,
          "te_err": [50.0] * 3, "ne_err": [1.5e18] * 3}
    base = K.pressure_from_thomson(th, sigma_floor=0.05)
    p = K.pressure_from_thomson(th, sigma_floor=0.05, conf=[2.0, 0.0, 1.0])
    assert p["index"] == [0, 2] and p["n_off"] == 1 and p["n_dropped"] == 0
    assert p["sigpre"][0] == pytest.approx(base["sigpre"][0] / 2.0) and p["sigpre"][1] == pytest.approx(base["sigpre"][2])


def _toy():
    """A 7×7 box, ψ_N = r² about the centre (ψ decreasing outward), boundary a square around the inner 3×3 cells."""
    gr = [1.0 + 0.1 * i for i in range(7)]
    gz = [-0.3 + 0.1 * j for j in range(7)]
    psi = [[1.0 - ((r - 1.3) ** 2 + z ** 2) / 0.09 for z in gz] for r in gr]
    fa = {"psi_axis": 1.0, "psi_bnd": 0.0}
    fi = {"grid_r": gr, "grid_z": gz, "psi": psi, "boundary": [[1.0, -0.3], [1.6, -0.3], [1.6, 0.3], [1.0, 0.3]]}
    return fa, fi


def test_cells_are_interior_and_r_major():
    fa, fi = _toy()
    geo, da = KI._cells(fa, fi)
    assert len(geo) == 5 and len(geo[0]) == 5 and da == pytest.approx(0.01)
    assert geo[2][2][1] == pytest.approx(0.0) and geo[2][2][2]                  #: the centre cell is the axis
    assert geo[0][0][0] == pytest.approx(1.1)


def test_external_current_is_normalized_to_its_total_and_follows_ip():
    fa, fi = _toy()
    geo, da = KI._cells(fa, fi)
    ex = {"psin": [0.0, 1.0], "j": [1.0, 0.0], "total_A": 5e4}
    cells, _ = KI.external_cells(ex, geo, da, -1.0)
    assert sum(map(sum, cells)) == pytest.approx(-5e4)
    b = KI.binned_j(cells, geo, da)
    assert sum(j * a for j, a in zip(b["j"], b["area"]) if math.isfinite(j)) == pytest.approx(-5e4)
    filled = [j for j in b["j"] if math.isfinite(j)]
    assert filled[0] < filled[-1] < 0.0                                         #: j(ψ_N) = 1 − ψ_N: largest on axis


def test_template_lists_every_channel_at_confidence_one(monkeypatch, tmp_path):
    pull = tmp_path / "pull.json"
    pull.write_text('{"measurements": {"shot": 1, "time_s": 4.0, "coils": [0, 0], "expmp2": [0, 0, 0], '
                    '"point": {"bpolar": [0, 0]}}, "thomson": {"te": [1, 2, 3, 4]}}')

    class Lib:
        def device(self, *a):
            return {"magnetics": {"flux_loop": [{"name": "FL1B"}, {"name": "FL2B"}],
                                  "b_field_pol_probe": [{"name": "P1"}, {"name": "P2"}, {"name": "P1"}]}}, {}
    d = KI.template(str(pull), Lib())
    assert d["magnetics"]["loops"] == {"FL1B": 1.0, "FL2B": 1.0}
    assert d["magnetics"]["probes"] == {"P1": 1.0, "P2": 1.0}                   #: a duplicated name is one entry
    assert d["point"]["faraday"] == [1.0, 1.0] and d["pressure"]["thomson"] == [1.0] * 4
    assert KI.normalize(copy.deepcopy(d)) == KI.normalize(d)


def test_warm_start_is_automatic_for_the_extended_bases_and_the_page_strings_are_read():
    st, _, cons, _ = KI.fit_settings(KI.normalize(doc()), 201)
    assert "warm_start" not in st                                                #: plain poly: the recorded solve
    st, _, _, _ = KI.fit_settings(KI.normalize(doc(pedestal={"on": True})), 201)
    assert st["warm_start"] == 1
    d = KI.normalize(doc(solver={"warm_start": "false", "condin": 1e6}, basis={"pprime": {"mode": "spline"}}))
    assert d["solver"]["warm_start"] is False
    st, _, cons, _ = KI.fit_settings(d, 201)
    assert "warm_start" not in st and st["condin"] == 1e6 and any("#137985" in c for c in cons)
    with pytest.raises(SystemExit):
        KI.normalize(doc(solver={"warm_start": "maybe"}))
