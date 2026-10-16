"""kinetic_input.py 的纯函数：输入文件的规范化与查错、模板（不载库）。

设定映射（fit_settings）、POINT / Thomson 置信度、电流分箱已是内核的（code/kinetic，
``src/door/case/kinetic/x.rs`` · ``p.rs``），测试在那边。"""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kinetic_input as KI  # noqa: E402


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


def test_the_page_strings_for_warm_start_are_read():
    """The warm-start mapping itself (auto → on for the extended bases) is fit_settings', tested in the kernel."""
    assert KI.normalize(doc())["solver"]["warm_start"] == "auto"
    d = KI.normalize(doc(solver={"warm_start": "false", "condin": 1e6}, basis={"pprime": {"mode": "spline"}}))
    assert d["solver"]["warm_start"] is False and d["solver"]["condin"] == 1e6
    assert KI.normalize(doc(solver={"warm_start": "true"}))["solver"]["warm_start"] is True
    with pytest.raises(SystemExit):
        KI.normalize(doc(solver={"warm_start": "maybe"}))
