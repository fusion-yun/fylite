"""PCS 步进会话（台账 I-8 · PCS-W6 / PCS-V6）：会话往返、固定步长、分步等价、按名拒绝。

每一步都是内核的 ``code/evolve``；工况取内核判据自己的 Miller 缺省（``evolve_default``）。
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from fylite import engine
from fylite.engine import session as S

_DEFAULT = dict(zip(
    "ch-heat ch-density ch-current dt nsteps dttarget nlev te0 ti0 peakt peakn edgete edgeti edgene "
    "vloop pe pi dep depw alpha brem ohmic bootstrap zeff cimp dtfrac chiratio chi0 ne0 amin rmaj "
    "kappa delta q95 bunit ip pedestal sawtooth couple".split(),
    [1, 0, 0, 0.002, 12, 0.02, 25, 3, 2.5, 1.5, 0.5, 0.3, 0.3, 3, 0, 4, 4, 0, 0.35, 1, 1, 1, 0,
     1.5, 0, 0.5, 1, 0.4, 10, 2, 3.1, 1.86, 0.48, 3, 5.3, 15000, 0, 0, 0]))


@pytest.fixture(scope="module", autouse=True)
def _kernel():
    try:
        from fylite import kernel
        kernel.require_data()
    except Exception as exc:  # the data-plane library is not loadable here
        pytest.skip(f"the runtime library is not loadable: {exc}")


def _plan():
    st = {k: float(v) for k, v in _DEFAULT.items()}
    st.update({"geometry": "miller", "closure": "0", "species": ""})
    return {"settings": st, "inputs": {}}


def _ellipse(n=64):
    th = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    return (3.1 + 2.0 * np.cos(th)).tolist(), (3.7 * np.sin(th)).tolist()


def test_the_clock_moves_ten_milliseconds_a_step():
    sid = S.open_session(_plan(), ec_sources=[None, None, None])["session"]
    for k in range(3):
        out = S.step_session(sid, k, {"ip": 15e6, "p_ec": [0.0, 0.0, 0.0]})
        assert out["flags"]["rejected"] is False, out["reason"]
        assert out["t"] == pytest.approx(S.STEP_S * (k + 1), abs=1e-12)
        assert all(np.isfinite(out["te"])) and out["te0"] > 0.0
        assert out["flags"]["phase"] == "zerod"
    summary = S.close_session(sid)
    assert summary["steps"] == 3 and summary["rejected"] == 0
    assert summary["wall_ms"]["n"] == 3 and summary["wall_ms"]["max"] >= summary["wall_ms"]["p50"]


def test_two_sessions_under_the_same_commands_march_bit_for_bit_alike():
    """The session keeps no hidden state beyond the record it hands on: the same commands, the same bits.

    (Step equivalence across block splits is the kernel's own fingerprint on the core chain —
    here the host sub-steps each 10 ms against the exchange cap, so a three-step run is not the
    same sequence of kernel steps.)
    """
    outs = []
    for _ in range(2):
        sid = S.open_session(_plan())["session"]
        for k in range(3):
            out = S.step_session(sid, k, {"ip": 15e6 - 1e5 * k})
        S.close_session(sid)
        outs.append(out)
    assert outs[0]["te"] == outs[1]["te"] and outs[0]["ti"] == outs[1]["ti"]
    assert outs[0]["t"] == outs[1]["t"] == pytest.approx(3 * S.STEP_S, abs=1e-12)


@pytest.mark.parametrize("k, cmd, word", [
    (5, {}, "k must be 0"),
    (0, {"dt": 0.02}, "dt must be"),
    (0, {"p_nbi": 1e6}, "neutral beam"),
    (0, {"p_lh": 1e6}, "lower hybrid"),
    (0, {"gas_rate": -1.0}, "gas_rate is negative"),
    (0, {"p_ec": [0.0]}, "p_ec has 1 groups"),
    (0, {"p_ec": [1e6, 0.0, 0.0]}, "no deposition table"),
    (0, {"lcfs_r": [3.0] * 5, "lcfs_z": [0.0] * 5}, "at least 16"),
    (0, {"pellet": [{"n_atoms": 1e21, "velocity_initial": 300.0, "fraction_t": 1.5}]}, "fraction_t"),
])
def test_a_rejected_step_says_why_and_the_session_goes_on(k, cmd, word):
    sid = S.open_session(_plan(), ec_sources=[None, None, None])["session"]
    out = S.step_session(sid, k, cmd)
    assert out["flags"]["rejected"] is True
    assert word in out["reason"]
    ok = S.step_session(sid, 0, {})
    assert ok["flags"]["rejected"] is False and ok["t"] == pytest.approx(S.STEP_S, abs=1e-12)
    assert S.close_session(sid)["rejected"] == 1


def test_commands_become_the_kernel_settings():
    """Interface v0.2 §3 → ``code/evolve``: the unit folds and the pellet / puff mapping (ledger I-9)."""
    s = S.Session(_plan(), ec_sources=[0, None, 2], ic_source=3)
    st = s._commands_to_settings({"ip": 15e6, "p_ec": [72e6, 0.0, 5e6], "p_ic": 20e6,
                                  "gas_rate": 2e21,
                                  "pellet": [{"n_atoms": 3e19, "velocity_initial": 300.0},
                                             {"n_atoms": 2e19, "velocity_initial": 300.0}]})
    assert st["ip"] == 15e3
    assert st["source_power_0"] == 72e6 and st["source_power_2"] == 5e6 and st["source_power_3"] == 20e6
    assert "source_power_1" not in st
    assert st["gas_rate"] == 2e21
    assert st["fuel_rate"] == pytest.approx(5e19 / S.STEP_S)
    assert (st["fuel_centre"], st["fuel_width"]) == (S.Session.PELLET_CENTRE, S.Session.PELLET_WIDTH)
    #: a step without a pellet sends no burst on
    quiet = s._commands_to_settings({"gas_rate": 0.0})
    assert quiet["fuel_rate"] == 0.0 and quiet["gas_rate"] == 0.0 and "fuel_centre" not in quiet


def test_a_kernel_refusal_is_a_rejected_step_and_the_session_goes_on(monkeypatch):
    """Interface §5: a refusal never ends the session — the kernel's included (I-10 ramp-down, -23)."""
    from fylite.io import fydoc
    s = S.Session(_plan())

    def refuse(cmd):
        raise fydoc.Refused(-23, {"refusal": {"code": -23, "message": "a species state that did not settle"}})
    monkeypatch.setattr(s, "_march", refuse)
    out = s.step(0, {"ip": 15e6})
    assert out["flags"]["rejected"] is True and out["kernel_code"] == -23
    assert "did not settle" in out["reason"]
    assert s.rejected == 1 and s.k_next == 0 and s.prev is None
    monkeypatch.undo()
    out = s.step(0, {"ip": 15e6})
    assert out["flags"]["rejected"] is False and s.k_next == 1


def test_a_session_restored_from_its_snapshot_marches_bit_for_bit_like_the_uninterrupted_one():
    """Ledger I-21b / PCS-V16: snapshot -> JSON -> restore -> next step equals the uninterrupted next step."""
    import json
    a = S.Session(_plan())
    for k in range(2):
        a.step(k, {"ip": 15e6 - 1e5 * k})
    snap = json.loads(json.dumps(a.snapshot()))
    out_a = a.step(2, {"ip": 15e6 - 2e5})
    opened = S.restore_session(snap)
    assert opened["k_next"] == 2
    out_b = S.step_session(opened["session"], 2, {"ip": 15e6 - 2e5})
    assert out_b["flags"]["rejected"] is False
    assert out_a["t"] == out_b["t"] and out_a["te"] == out_b["te"] and out_a["ne"] == out_b["ne"] and out_a["ti"] == out_b["ti"]
    S.close_session(opened["session"])
    with pytest.raises(S.SessionError, match="not a session snapshot"):
        S.Session.from_snapshot({"format": "something else"})


def test_the_session_carries_every_scalar_the_kernel_resume_hands_on():
    """The kernel's own resume gate (`a_resumed_march_is_the_same_march_under_the_pcs_opt_ins`) hands these
    scalars from one call to the next; a session that drops one re-starts that piece of state every 10 ms."""
    kernel_pairs = {("t_end", "t_start"), ("dt_next", "dt_start"), ("edge_te_out", "edge_te_in"),
                    ("edge_ti_out", "edge_ti_in"), ("saw_elapsed_out", "saw_elapsed_in"),
                    ("ipctl_ratio0_out", "ipctl_ratio0_in"), ("ipctl_integral_out", "ipctl_integral_in"),
                    ("ipctl_calibrated_out", "ipctl_calibrated_in"), ("dt_capped", "capped_in"),
                    ("dt_fraction_used", "dt_fraction_in"), ("chi_scale_ploss_ref", "chi_scale_ploss_ref"),
                    ("chi_scale_ne_ref", "chi_scale_ne_ref"), ("chi_scale_ip_ref", "chi_scale_ip_ref"),
                    ("chi_scale_w_ref", "chi_scale_w_ref"), ("chi_scale_int", "chi_scale_int")}
    assert kernel_pairs <= set(S._CARRY), sorted(kernel_pairs - set(S._CARRY))


def test_a_resume_hands_every_lagged_profile_the_record_carries():
    """The kernel resumes from six lagged arrays in declared ``core_profiles`` slots; all six cross back."""
    s = S.Session(_plan())
    lags = {slot: {"data": [float(i)] * 3} for i, slot in enumerate(S._PROFILE_LAGS)}
    prof = {"electrons": {"temperature": {"data": [1.0, 1.0, 1.0]}, "density": {"data": [2.0, 2.0, 2.0]}},
            "t_i_average": {"data": [1.0, 1.0, 1.0]}, "fylite:ion_density": {"data": [2.0, 2.0, 2.0]}, **lags}
    rec = {"facts": {"t_end": {"value": 0.01}}, "fields": {"core_profiles": {"profiles_1d": prof}}}
    st, inp = s._resume({"ip": 15e3}, rec, 0.01)
    handed = inp["core_profiles"]["profiles_1d"]
    assert st["resume"] == 1.0 and st["state"] == 1.0
    for i, slot in enumerate(S._PROFILE_LAGS):
        assert handed[slot] == [float(i)] * 3, slot


def test_the_phase_flag_follows_the_kernel_lh_trace():
    """``flags.phase``: zerod before 1 s, the kernel's L-H phase after it (ledger I-7), else unknown."""
    def record(t, lh=None):
        prof = {"data": [2.0, 1.0]}
        rec = {"facts": {"t_end": {"value": t}},
               "fields": {"core_profiles": {"profiles_1d": {
                   "electrons": {"temperature": prof, "density": prof}, "t_i_average": prof}}}}
        if lh is not None:
            rec["fields"]["lh_phase"] = {"data": lh}
        return rec

    s = S.Session(_plan())
    assert s._outputs(record(0.5, [1.0]), {})["flags"]["phase"] == "zerod"
    assert s._outputs(record(2.0, [0.0, 1.0]), {})["flags"]["phase"] == "H"
    assert s._outputs(record(2.0, [1.0, 0.0]), {})["flags"]["phase"] == "L"
    assert s._outputs(record(2.0), {})["flags"]["phase"] is None


def test_a_self_intersecting_lcfs_is_refused_and_an_ellipse_is_not():
    r, z = _ellipse()
    assert S._rejection(0, {"lcfs_r": r, "lcfs_z": z}, 0, 0.0, 1.0) is None
    bow = list(zip(r, z))
    bow[10], bow[40] = bow[40], bow[10]
    msg = S._rejection(0, {"lcfs_r": [p[0] for p in bow], "lcfs_z": [p[1] for p in bow]}, 0, 0.0, 1.0)
    assert msg is not None and "self-intersects" in msg
    assert "missing at t" in S._rejection(0, {}, 0, 1.0, 1.0)


def test_the_session_rides_json_rpc():
    def call(method, params, rid):
        return engine.handle_rpc_request({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})

    opened = call("fylite.session.open", {"plan": _plan()}, 1)
    sid = opened["result"]["session"]
    stepped = call("fylite.session.step", {"session": sid, "k": 0, "commands": {"ip": 15e6}}, 2)
    assert stepped["result"]["t"] == pytest.approx(S.STEP_S, abs=1e-12)
    closed = call("fylite.session.close", {"session": sid}, 3)
    assert closed["result"]["steps"] == 1
    gone = call("fylite.session.step", {"session": sid, "k": 1}, 4)
    assert gone["error"]["code"] == -32602 and "no open session" in gone["error"]["message"]
