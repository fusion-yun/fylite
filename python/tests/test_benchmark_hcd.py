"""Gates of the `tr-sources` records (heating & current drive, FR-TR-004 · NR-TR-001).

Three readings, written by ``tools/benchmark-hcd.py``:

* ``hcd_power_closure.json`` — every family's power account through the tree doors (re-run here);
* ``ec_toray_cfedr20ma.json`` — `code/rf_ray` against TORAY-GA's own answer on CFEDR 20 MA (re-run here; needs the
  kernel checkout, where the internal TORAY reference lives);
* ``hcd_metis_kernel.json`` — the kernel's METIS comparisons (ICRH has no `code/` door), parsed from its
  ``[register]`` lines: held here to the kernel tests' own bands, so a reading that drifts out of them goes red on
  this side too.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
READINGS = ROOT / "docs" / "benchmark" / "readings"
REPRO_REL, REPRO_ABS = 1e-6, 1e-12


def _tool():
    spec = importlib.util.spec_from_file_location("benchmark_hcd", ROOT / "tools" / "benchmark-hcd.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _want(name: str) -> dict:
    p = READINGS / name
    if not p.is_file():
        pytest.skip(f"no {name} recorded (tools/benchmark-hcd.py)")
    return json.loads(p.read_text(encoding="utf-8"))


def _walk(g, w, path=""):
    if isinstance(w, dict):
        for k, v in w.items():
            _walk(g[k], v, f"{path}/{k}")
    elif isinstance(w, list):
        assert len(g) == len(w), path
        for i, v in enumerate(w):
            _walk(g[i], v, f"{path}[{i}]")
    elif isinstance(w, float):
        assert abs(g - w) <= max(REPRO_ABS, REPRO_REL * abs(w)), (path, g, w)
    else:
        assert g == w, (path, g, w)


def _toray_here() -> bool:
    k = os.environ.get("FYLITE_KERNEL")
    return bool(k) and (Path(k) / "rust/fylite/testdata/reference/cfedr_toray_20ma.txt").is_file()


def _run(fn):
    try:
        return fn()
    except FileNotFoundError as e:
        pytest.skip(f"input not on this machine: {e}")
    except Exception as e:  # noqa: BLE001 — a host without the library skips by name
        if "library" in str(e).lower():
            pytest.skip(f"no runtime library here: {e}")
        raise


# ───────────────────────────────────────────────────────────── the power accounts

@pytest.fixture(scope="module")
def closure() -> dict:
    if not _toray_here():
        pytest.skip("the EC account runs on CFEDR 20 MA, whose reference lives in the kernel ($FYLITE_KERNEL)")
    return _run(_tool().closure)


def test_hcd_nbi_account_closes_with_all_three_sinks_carrying_power(closure):
    """★P_inj = P_abs + P_shine + P_orbit, term by term (the SRS source table's words), and the deposited profile's
    volume integral is P_abs.  Both beams are set up so that shine-through AND first-orbit loss carry power — an
    account that closed with a sink at zero would not have tested that sink."""
    n = closure["nbi"]
    assert n["p_shine_W"] > 0.0 and n["p_orbit_W"] > 0.0, n
    assert n["injected_vs_declared_rel"] < 1e-12
    assert n["closure_rel"] < 1e-12 and n["profile_integral_rel"] < 1e-12, n


def test_hcd_lh_account_closes(closure):
    """Coupled (launched − reflected) = absorbed = deposited = ∫ p dV, per launcher and in total."""
    lh = closure["lh"]
    assert lh["deposited"] == 1.0
    assert lh["absorbed_vs_coupled_rel"] < 1e-12 and lh["profile_integral_rel"] < 1e-12
    assert lh["per_launcher_sum_rel"] < 1e-12


def test_hcd_ec_account_closes(closure):
    """Launched = absorbed + left + not traced; the shells plus what lies beyond the last one = absorbed; the power
    density times the shell volume = the shell power (the kernel's own gate on these is 1e-9)."""
    ec = closure["ec"]
    assert ec["closure_rel"] < 1e-9 and ec["shells_plus_outside_rel"] < 1e-9, ec
    assert ec["density_times_volume_rel"] < 1e-9, ec


def test_hcd_the_accounts_reproduce_their_reading(closure):
    _walk(closure, _want("hcd_power_closure.json"))


# ───────────────────────────────────────────────────────────── EC against TORAY

@pytest.fixture(scope="module")
def toray() -> dict:
    if not _toray_here():
        pytest.skip("no TORAY reference: set $FYLITE_KERNEL to a kernel checkout (it is internal and lives there)")
    return _run(_tool().toray)


def test_ec_the_branch_is_read_off_torays_data(toray):
    """★Which branch TORAY launched is declared nowhere; it is read off |N| on the surfaces both rays cross.  Both
    halves are held: the agreement AND the discrimination (a medium where the two branches collapsed would pass the
    first alone)."""
    b = toray["branch"]
    assert b["identified"] == "O"
    assert b["n_abs_rel_worst"]["O"] < 0.01 and b["n_abs_rel_worst"]["X"] > 0.05, b


def test_ec_the_ray_follows_torays(toray):
    """Two independent tracers on one equilibrium: the same place on the same surface (5 mm), the same depth (1 %),
    the same N∥ (1e-3) — the kernel oracle's bands."""
    r = toray["ray"]
    assert r["dr_mm_max"] < 5.0 and r["dz_mm_max"] < 5.0, r
    assert r["deepest_rel"] < 0.01 and r["npar_rel_max"] < 1e-3, r


def test_ec_deposition_and_current_against_torays(toray):
    """Where the power lands (peak within 0.05 in psi_N — our shells are 0.02 wide), how much is absorbed (> 0.5; TORAY
    absorbs 0.999 in one pass), and the driven current per incident watt (0.9–1.2 of TORAY's)."""
    d, c = toray["deposition"], toray["current"]
    assert d["peak_dpsin"] <= 0.05 and d["absorbed_fraction"] > 0.5, d
    assert 0.9 < c["ratio"] < 1.2, c


def test_ec_the_comparison_reproduces_its_reading(toray):
    _walk(toray, _want("ec_toray_cfedr20ma.json"))


# ───────────────────────────────────────────────────────────── the kernel's METIS comparisons

def test_hcd_the_kernel_metis_readings_sit_in_the_kernel_bands():
    """★ICRH has no `code/` door, and the ECCD rows are judged inside the kernel: their gates are Rust tests the
    public CI cannot run.  What this side CAN hold is the recorded reading — each number against the band the
    kernel test asserts, so a reading that is re-recorded out of band goes red here too."""
    r = _want("hcd_metis_kernel.json")["readings"]
    lay, tail, split = r["icrh_layer"], r["icrh_tail"], r["icrh_split"]
    assert lay["r_res_rel_max"] < 0.03 and lay["x_res_abs_max"] < 0.075, lay
    assert tail["n_min_rel_max"] < 0.03 and tail["fraction_rel_max"] < 0.05, tail
    assert tail["e_crit_rel_max"] < 0.10 and tail["tau_s_rel_max"] < 0.10, tail
    assert split["rows"] >= 15 and 0.85 < split["p_el_ratio_min"] and split["p_el_ratio_max"] < 1.15, split
    assert 0.85 < split["w_fast_ratio_min"] and split["w_fast_ratio_max"] < 1.15, split
    un = r["icrh_unsettled"]
    assert un["p_el_ratio_min"] < 0.5 and un["p_el_ratio_max"] > 5.0, un
    prof = r["icrh_profile"]
    assert prof["peak_abs_max"] <= 0.05 + 1e-9 and prof["width_rel_max"] < 0.05, prof
    assert r["icrh_closure"]["total_rel"] < 1e-12 and r["icrh_closure"]["ion_rel"] < 1e-12
    fw = r["fwcd_measured"]
    assert 0.70 < fw["ratio_min"] and fw["ratio_max"] < 1.30 and abs(fw["ratio_median"] - 1.0) < 0.05, fw
    gz = r["eccd_giruzzi"]
    assert 0.85 < gz["ratio_min"] and gz["ratio_max"] < 1.25, gz
    ad = r["eccd_adjoint"]
    assert ad["rows"] >= 25 and ad["ratio_min"] > 0.015 and ad["ratio_max"] < 1.0, ad
    assert 0.2 < ad["ratio_median"] < 0.6 and ad["loglog_corr_metis"] > 0.9 and ad["loglog_corr_fit"] > 0.9, ad
