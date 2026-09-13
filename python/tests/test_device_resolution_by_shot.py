"""EAST device data resolved BY SHOT AND MEASUREMENT CHAIN at use time (user rulings R-S1 /
R-S2 and the measurement-chain ruling, 2026-09-13).

The rule lives in the runtime (``fylite_runtime::device_resolve``); ``fylite.device``
reaches it through ``libfylite_runtime.so`` and ``fy run --device`` calls it directly.
The per-provider groups are converted once by ``tools/abox-to-facts.py`` and ship in
``east_resolution.jsonld`` beside the card and in the bundled tier.

A device request gives ONLY the shot and the measurement chain: fydoc's manifest declares
the chains (``measurement_chains``: pcs_east · east · efit_east — no est2) and gives every
magnetics provider its ``measurement_chain``.

Gates
=====
(a) the BUNDLED tier resolves EAST by shot and chain: #70754 -> the <=97030 magnetics family,
    #137985 and no shot -> ``east_new`` — through the C ABI, and through a ``fy`` that
    sees no corpus on disk;
(b) Python and the command line agree on the providers for shots straddling
    45563 / 70754 / 80000 / 97030 / 97034, with no chain and within every declared chain —
    including the refusals (a gap inside a chain);
(c) the measurement chain decides and the refusals are named: within a chain the covering
    provider wins, a rangeless one only when none covers; a gap, an undeclared chain (est2),
    a removed request key (``providers`` / ``basis`` / ``provider=``) are each refused by name
    — in the library, on the command line, and on the reconstruction path
    (``fylite.fyo.as_measurements``: a measurement whose chain differs from the bound card's
    magnetics chain is refused).

And the invariants the design rests on: the static card IS the no-shot resolution (both
spellings); every converted group is exactly what building that provider gives, with
``pf_active`` (supplies included) the same for every provider; no magnetics group carries
per-channel fit arrays; the bundled copy carries only the document form.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap

import pytest
import yaml

from fylite import device as D
from fylite import facts as F

ROOT = pathlib.Path(__file__).resolve().parents[2]
CARD_DIR = ROOT / "dist" / "facts" / "device" / "east"
CARD = CARD_DIR / "east_device.yaml"
DOC = ROOT / "dist" / "facts" / "device" / "east.jsonld"
RES = CARD_DIR / "east_resolution.jsonld"
EXE = ROOT / "rust" / "fylite_runtime" / "target" / "release" / "fy"
TOOL = ROOT / "tools" / "abox-to-facts.py"
#: straddling every EAST boundary the shot rule could meet: EFIT cm->m 45563, PCS N-pole
#: <=70754, VP >=80000, the probe renaming 97030/97034 (and the unknown band between)
SHOTS = [45562, 45563, 70754, 70755, 79999, 80000, 97030, 97032, 97034, 137985, None]
CHAINS = [None, "east", "pcs_east", "efit_east"]


def _need(p: pathlib.Path):
    if not p.is_file():
        pytest.skip(f"no {p.relative_to(ROOT)} (python3 tools/abox-to-facts.py east)")


def _runtime():
    lib = F._lib()
    if lib is None or not hasattr(lib, "fylite_runtime_device_resolve"):
        pytest.skip("libfylite_runtime.so without fylite_runtime_device_resolve (bash rust/build.sh)")


def _exe() -> pathlib.Path:
    if not EXE.is_file():
        pytest.skip("no fy executable (bash rust/build.sh --exe)")
    return EXE


@pytest.fixture(scope="module")
def resolution() -> dict:
    _need(RES)
    _runtime()
    return json.loads(RES.read_text(encoding="utf-8"))


def _show(shots) -> str | None:
    """The record's `shots` as the command line's one-line summary spells it."""
    if isinstance(shots, list):
        return f"[{shots[0]}, {'—' if shots[1] is None else shots[1]}]"
    return None


_SUMMARY = re.compile(r"(\w+)=(\S+?)(?: (\[[^\]]*\]))?(?:,|\)|$)")


def _device_line(stdout: str) -> str:
    line = next((ln for ln in stdout.splitlines() if ln.strip().startswith("device ")), None)
    assert line is not None, stdout
    return line


def _cli_selection(line: str) -> dict:
    m = re.search(r"\(resolved (.*)\)\s*$", line)
    assert m, line
    return {ids: (prov, rng) for ids, prov, rng in _SUMMARY.findall(m.group(1) + ")")}


def _dry(exe, *args, cwd, env=None):
    return subprocess.run([str(exe), "run", "analysis", "--device", "east", "--dry-run", "--offline",
                           *args], capture_output=True, text=True, timeout=180, cwd=cwd,
                          env=env if env is not None else dict(os.environ))


def _shot_args(shot):
    return [f"shot={shot}"] if shot is not None else []


def _chain_args(chain):
    return [f"measurement_chain={chain}"] if chain is not None else []


# ───────────────────────────── (a) the bundled tier ─────────────────────────────

def test_the_bundled_tier_resolves_east_by_shot_and_chain():
    _runtime()
    text = F.bundled_resolution("device", "east")
    if text is None:
        pytest.skip("this libfylite_runtime.so bundles no device/east resolution (build with facts)")
    res = json.loads(text)
    assert not any("card" in v for provs in res["variants"].values() for v in provs.values()), \
        "the bundled copy carries the document form only (A-13)"
    assert list(res["manifest"]["measurement_chains"]) == ["pcs_east", "east", "efit_east"]
    old = D.select_providers(shot=70754, resolution=res)["magnetics"]
    assert (old["provider"], old["shots"]) == ("base", [0, 97030]), old
    for shot in (137985, None):
        new = D.select_providers(shot=shot, resolution=res)["magnetics"]
        assert (new["provider"], new["shots"]) == ("east_new", [97034, None]), (shot, new)
    assert D.select_providers(shot=137985, measurement_chain="efit_east",
                              resolution=res)["magnetics"]["provider"] == "efit"
    #: the bundled DOCUMENT, resolved from the bundled resolution, is that family
    card = json.loads(F.bundled_doc("device", "east"))
    doc = D.resolve_document(card, res, shot=70754, form="document")["document"]
    assert (doc["magnetics"]["fylite:provider"], doc["magnetics"]["measurement_chain"]) == ("base", "east")
    assert len(doc["magnetics"]["b_field_pol_probe"]) == 38
    assert doc["_valid_shots"] == [0, 97030]


def test_fy_resolves_east_by_shot_from_the_bundled_tier(tmp_path):
    exe = tmp_path / "bin" / "fy"
    exe.parent.mkdir()
    shutil.copy2(_exe(), exe)
    env = {k: v for k, v in os.environ.items() if k not in ("FY_FACTS_PATH", "FY_FACTS_BUNDLED")}
    for shot, want in ((70754, None), (137985, "east_new"), (None, "east_new")):
        r = _dry(exe, *_shot_args(shot), cwd=tmp_path, env=env)
        assert r.returncode == 0, r.stdout + r.stderr
        line = _device_line(r.stdout)
        assert "<buildin>" in line, f"not the bundled tier: {line}"
        sel = _cli_selection(line)
        if want is None:
            assert sel["magnetics"][1] == "[0, 97030]", line
        else:
            assert sel["magnetics"] == (want, "[97034, —]"), line
    r = subprocess.run([str(exe), "list", "devices", "east"], capture_output=True, text=True,
                       timeout=60, cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert re.search(r"resolves\s+magnetics\s+no shot -> east_new", r.stdout), r.stdout
    assert "chain efit_east" in r.stdout, r.stdout


# ───────────────────────────── (b) Python and the runtime agree ─────────────────────────────

@pytest.mark.parametrize("chain", CHAINS, ids=lambda c: c or "no-chain")
def test_python_and_the_command_line_agree_on_the_providers(resolution, chain):
    exe = _exe()
    for shot in SHOTS:
        r = _dry(exe, *_shot_args(shot), *_chain_args(chain), cwd=ROOT)
        try:
            py = D.select_providers(shot=shot, measurement_chain=chain, resolution=resolution)
        except D.ProviderSelectionError as e:
            #: a refusal is the same refusal on both routes
            said = r.stdout + r.stderr
            assert r.returncode != 0, (shot, chain, said)
            assert str(e).split(" — ")[0] in said, (shot, chain, str(e), said)
            continue
        assert r.returncode == 0, (shot, chain, r.stdout + r.stderr)
        line = _device_line(r.stdout)
        assert "dist/facts" in line, f"not the staged corpus: {line}"
        cli = _cli_selection(line)
        assert {k: (v["provider"], _show(v["shots"])) for k, v in py.items()} == \
            {k: (p, rng or None) for k, (p, rng) in cli.items()}, (shot, chain, line)


# ───────────────────────────── (c) the chain decides; refusals are named ─────────────────────────────

def test_the_measurement_chain_decides_within_itself_and_refuses_by_name(resolution):
    sel = lambda **q: D.select_providers(resolution=resolution, **q)["magnetics"]  # noqa: E731
    #: within chain `east`: the ranged provider covering the shot; no shot = the open upper end
    assert sel(shot=70754, measurement_chain="east")["provider"] == "base"
    assert sel(shot=137985, measurement_chain="east")["provider"] == "east_new"
    assert sel(measurement_chain="east")["provider"] == "east_new"
    #: a rangeless provider of its chain, at any shot; the era-limited PCS bindings never compete
    for shot in (45562, 70754, 137985, None):
        assert sel(shot=shot, measurement_chain="pcs_east")["provider"] == "pcs"
        assert sel(shot=shot, measurement_chain="efit_east")["provider"] == "efit"
    #: a gap inside the chain names the chain, the shot and the declared ranges
    with pytest.raises(D.ProviderSelectionError) as gap:
        sel(shot=97032, measurement_chain="east")
    assert all(s in str(gap.value) for s in ('"east"', "97032", "[0, 97030]", "[97034, —]")), gap.value
    #: an undeclared chain — there is no est2 chain — is refused, never the default
    with pytest.raises(D.ProviderSelectionError, match=r'"est2".*not declared'):
        sel(shot=137985, measurement_chain="est2")
    #: the wall keeps the manifest default whatever the chain
    assert D.select_providers(resolution=resolution, shot=137985,
                              measurement_chain="efit_east")["wall"]["provider"] == "base"
    #: the removed request keys are refused by the runtime by name
    for key, value in (("providers", {"magnetics": "efit"}), ("basis", "est2")):
        lib_q = json.dumps({"shot": 137985, key: value})
        with pytest.raises(D.ProviderSelectionError, match=f'"{key}"'):
            _raw_request(resolution, lib_q)
    #: the card resolved in a chain is that chain's array, with no per-channel fit arrays
    _need(CARD)
    mag = D.resolve_document(D.load_device(CARD), resolution, shot=137985,
                             measurement_chain="efit_east")["document"]["magnetics"]
    assert (mag["fylite:provider"], mag["measurement_chain"]) == ("efit", "efit_east")
    assert (len(mag["b_field_pol_probe"]), len(mag["flux_loop"])) == (76, 35)
    assert not any("weight" in c or "bit_error" in c for c in (*mag["b_field_pol_probe"], *mag["flux_loop"]))


def _raw_request(resolution: dict, request: str) -> dict:
    """The C ABI with a request document as written (to reach the runtime's own key check)."""
    import ctypes
    lib = F._lib()
    fn = lib.fylite_runtime_device_resolve
    fn.restype = ctypes.c_int64
    fn.argtypes = [ctypes.c_char_p, ctypes.c_uint64] * 4 + [ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint64]
    r, q = json.dumps(resolution).encode(), request.encode()
    text = F._ask(fn, b"", 0, r, len(r), q, len(q), b"", 0)
    out = json.loads(text)
    if "error" in out:
        raise D.ProviderSelectionError(out["error"])
    return out


def _measurement(tmp_path: pathlib.Path, chain: str | None, n_probe: int, n_loop: int) -> pathlib.Path:
    """A synthetic IMAS-shaped measurement document (no shot data) declaring ``chain``."""
    doc = {"magnetics": {"flux_loop": [{"flux": 0.01}] * n_loop,
                         "b_field_pol_probe": [{"field": 0.001}] * n_probe, "ip": [4.0e5]},
           "pf_active": {"coil": [{"current": 1000.0}] * 12},
           "tf": {"b_field_tor_vacuum_r": -3.15}}
    if chain is not None:
        doc["measurement_chain"] = chain
    p = tmp_path / f"meas-{chain}.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_the_command_line_takes_the_chain_from_the_measurement_document(resolution, tmp_path):
    exe = _exe()
    efit = _measurement(tmp_path, "efit_east", 76, 35)
    ok = _dry(exe, "--input", str(efit), cwd=ROOT)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert _cli_selection(_device_line(ok.stdout))["magnetics"][0] == "efit"
    #: a chain the device does not declare, read off the document, is refused by name
    est2 = _measurement(tmp_path, "est2", 79, 35)
    bad = _dry(exe, "--input", str(est2), cwd=ROOT)
    said = bad.stdout + bad.stderr
    assert bad.returncode != 0 and "est2" in said and "not declared" in said, said
    #: the document declares a chain: measurement_chain= is refused, naming both
    both = _dry(exe, "--input", str(efit), "measurement_chain=east", cwd=ROOT)
    said = both.stdout + both.stderr
    assert both.returncode != 0 and "measurement_chain=east" in said and "efit_east" in said, said
    #: provider= is not a request of any kind any more (2026-09-13): it selects no provider of the
    #: card, and the templates' common `provider` parameter is gone, so the scenario refuses it by
    #: name like any unknown parameter.  (The data fetch's `--provider` is a fixed option, not this.)
    for spelled in ("provider=magnetics=efit", "provider=efit"):
        named = _dry(exe, spelled, cwd=ROOT)
        said = named.stdout + named.stderr
        assert named.returncode != 0, said
        assert "takes no parameter" in said and "provider" in said, said


def test_the_reconstruction_path_refuses_a_measurement_of_another_chain(tmp_path):
    _need(CARD)
    _runtime()
    meas = _measurement(tmp_path, "efit_east", 76, 35)
    code = textwrap.dedent("""
        import sys
        from fylite import device as D, fyo
        D.use_device(D.document() if sys.argv[1] == "static" else D.document(measurement_chain="efit_east"))
        try:
            m = fyo.as_measurements(sys.argv[2], 4.0)
        except fyo.MeasurementInputError as e:
            if "never paired" in str(e):
                print("REFUSED:", e)
                sys.exit(3)
            print("OTHER:", e)
            sys.exit(4)
        print("READ", m["measurement_chain"], len(m["expmp2"]), len(m["coils"]))
    """)
    #: the child binds the bundled EAST card this gate already required (`_need(CARD)`), whatever
    #: the caller's environment names — without it `device.document()` has no directory to resolve
    env = dict(os.environ, FYLITE_DEVICE_DIR=str(CARD_DIR))
    run = lambda which: subprocess.run([sys.executable, "-c", code, which, str(meas)],  # noqa: E731
                                       capture_output=True, text=True, timeout=300, cwd=ROOT / "python",
                                       env=env)
    static = run("static")
    assert static.returncode == 3, static.stdout + static.stderr
    assert "efit_east" in static.stdout and "'east'" in static.stdout, static.stdout
    matched = run("efit_east")
    assert matched.returncode == 0 and "READ efit_east 76 35" in matched.stdout, matched.stdout + matched.stderr


# ───────────────────────────── the invariants ─────────────────────────────

def test_the_static_card_is_the_no_shot_resolution(resolution):
    _need(CARD)
    _need(DOC)
    card = D.load_device(CARD)
    assert D.resolve_document(card, resolution, form="card")["document"] == card
    doc = json.loads(DOC.read_text(encoding="utf-8"))
    assert D.resolve_document(doc, resolution, form="document")["document"] == doc
    rec = card["provenance"]["fylite:resolution"]
    assert "latest" in rec["shot"]
    assert rec["measurement_chains"] == ["pcs_east", "east", "efit_east"]
    #: which shot range each IDS represents (R-S2)
    assert (rec["ids"]["magnetics"]["provider"], rec["ids"]["magnetics"]["shots"]) == ("east_new", [97034, None])
    assert rec["ids"]["wall"]["provider"] == "base" and rec["ids"]["wall"]["shots"].startswith("all")
    assert card["_valid_shots"] == [97034, None]
    assert (card["magnetics"]["fylite:provider"], card["magnetics"]["measurement_chain"]) == ("east_new", "east")


def _tool():
    spec = importlib.util.spec_from_file_location("abox_to_facts_resolution", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_each_converted_group_is_that_provider_built(resolution):
    a2f = _tool()
    fydoc = pathlib.Path(os.environ.get("FYDOC") or a2f.FYDOC)
    if not (a2f.device_root(fydoc) / "east").is_dir():
        pytest.skip(f"no fydoc EAST A-Box under {fydoc}")
    _need(CARD)
    card = D.load_device(CARD)
    for ids, provs in resolution["variants"].items():
        for name, v in provs.items():
            assert "fylite:absent" not in v, (ids, name, v)
            built = yaml.safe_load(yaml.dump(a2f.build("east", fydoc, providers={ids: name}),
                                             allow_unicode=True, sort_keys=False))
            for key, val in v["card"].items():
                assert built[key] == val, (ids, name, key)
            #: pf_active — supplies in element order included — is one set for every provider
            assert built["pf_active"] == card["pf_active"], (ids, name)
            assert built["pf_channel_elements"] == card["pf_channel_elements"], (ids, name)
            assert built["operational"] == card["operational"], (ids, name)


# ───────────── (4) two routes, one rule: generated variant card == use-time resolution ─────────────

@pytest.fixture(scope="module")
def generator():
    """(tool, fydoc, resolution, the default build) — the card-generation route, in process."""
    a2f = _tool()
    fydoc = pathlib.Path(os.environ.get("FYDOC") or a2f.FYDOC)
    if not (a2f.device_root(fydoc) / "east").is_dir():
        pytest.skip(f"no fydoc EAST A-Box under {fydoc}")
    _need(CARD)
    _runtime()
    return a2f, fydoc, a2f.east_resolution(fydoc), a2f.build("east", fydoc)


@pytest.mark.parametrize("chain", [None, "east", "efit_east"], ids=lambda c: c or "no-chain")
@pytest.mark.parametrize("shot", [70754, 97030, 97034, 137985])
def test_a_generated_variant_card_is_the_use_time_resolution(generator, shot, chain):
    a2f, fydoc, res, base = generator
    card = a2f.variant_card("east", fydoc, copy.deepcopy(base), shot=shot, measurement_chain=chain,
                            resolution=res)
    card = yaml.safe_load(yaml.dump(card, allow_unicode=True, sort_keys=False))       # as written
    use = D.document(shot=shot, measurement_chain=chain)
    assert card["_selection"] == {k: v["provider"] for k, v in
                                  use["provenance"]["fylite:resolution"]["ids"].items()}
    assert card.get("_valid_shots") == use.get("_valid_shots")
    assert card["_shot"] == shot
    assert card.get("_measurement_chain") == chain
    #: and not only the summary fields: the whole card, less what generation adds
    assert {k: v for k, v in card.items() if k not in ("_selection", "_shot", "_measurement_chain")} == use


def test_a_gap_in_a_chain_refuses_the_same_way_on_both_routes(generator):
    a2f, fydoc, res, base = generator
    ask = {"shot": 97032, "measurement_chain": "east"}
    with pytest.raises(SystemExit) as gen:
        a2f.variant_card("east", fydoc, copy.deepcopy(base), resolution=res, **ask)
    with pytest.raises(D.ProviderSelectionError) as use:
        D.document(**ask)
    assert str(gen.value) == f"east: {use.value}"
    assert "97032" in str(use.value) and '"east"' in str(use.value)


def test_the_generation_surface_keeps_its_refusals(generator, tmp_path):
    a2f, fydoc, res, base = generator
    #: an undeclared chain
    with pytest.raises(SystemExit, match="not declared"):
        a2f.variant_card("east", fydoc, copy.deepcopy(base), shot=137985,
                         measurement_chain="est2", resolution=res)
    #: a default that does not cover the shot (the runtime's strict request) …
    with pytest.raises(SystemExit, match="outside"):
        a2f.variant_card("east", fydoc, copy.deepcopy(base), shot=97032, resolution=res)
    #: … while use time, unpinned, uses it and says so
    assert D.document(shot=97032)["magnetics"]["fylite:provider"] == "east_new"
    tool = [sys.executable, str(TOOL)]
    no_out = subprocess.run(tool + ["east", "--shot", "137985", "--measurement-chain", "efit_east"],
                            capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert no_out.returncode == 2 and "-o" in no_out.stderr, no_out.stderr
    no_machine = subprocess.run(tool + ["--all", "--shot", "137985", "-o", str(tmp_path)],
                                capture_output=True, text=True, timeout=120, cwd=ROOT)
    assert no_machine.returncode == 2 and "ONE named machine" in no_machine.stderr, no_machine.stderr
    #: the removed selection flags are not accepted
    for flag in (["--select", "magnetics=efit"], ["--basis", "est2"]):
        r = subprocess.run(tool + ["east", *flag, "-o", str(tmp_path)],
                           capture_output=True, text=True, timeout=120, cwd=ROOT)
        assert r.returncode == 2 and "unrecognized arguments" in r.stderr, r.stderr


def test_the_generator_refuses_two_providers_of_one_chain_covering_a_shot(generator):
    """★The rule's own manifest check, reached through the generation route."""
    a2f, fydoc, res, base = generator
    bad = copy.deepcopy(res)
    avail = bad["manifest"]["providers"]["magnetics"]["available"]
    avail["twin"] = dict(avail["base"])
    bad["variants"]["magnetics"]["twin"] = bad["variants"]["magnetics"]["base"]
    with pytest.raises(SystemExit) as e:
        a2f.variant_card("east", fydoc, copy.deepcopy(base), shot=70754, resolution=bad)
    assert '"base"' in str(e.value) and '"twin"' in str(e.value) and '"east"' in str(e.value), e.value


def test_every_magnetics_group_states_its_chain_and_no_group_carries_fit_arrays(resolution):
    manifest = resolution["manifest"]["providers"]["magnetics"]["available"]
    for name, v in resolution["variants"]["magnetics"].items():
        mag = v["card"]["magnetics"]
        assert mag["measurement_chain"] == manifest[name]["measurement_chain"], name
        assert mag["measurement_chain"] in resolution["manifest"]["measurement_chains"], name
        assert not any("weight" in c or "bit_error" in c for c in (*mag["b_field_pol_probe"], *mag["flux_loop"])), name
        assert "fylite:channel_basis" not in mag, name
    assert "basis_providers" not in resolution
    assert set(resolution["variants"]["magnetics"]) == {"base", "east_new", "pcs", "efit"}
    assert set(resolution["variants"]["wall"]) == {"base", "m093060"}
    assert not any("fylite:absent" in v for v in resolution["variants"]["wall"].values())
