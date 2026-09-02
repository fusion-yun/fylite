"""est2 (GUI_v5) path: self-contained EAST device data + GUI-faithful k-file.

Offline structural checks (no live MDSplus).  The est2 path is triggered by a
79-probe measurement vector or meas["basis"]=="est2"; it auto-applies the baked
EAST device data (masks, error floors, FWTFC, operational limiter) from
fylite._data/east_device.yaml via device — no fydata, no external file.
"""
import re


from conftest import requires_machine

#: ★★These need the machine DECK, and nothing here needs the reference
#: discharge.  The mark used to be ````, which gates
#: on ``examples/scripts/g137985.04000`` — a file not one of the fifteen
#: cases below opens.  So the whole module skipped, always, including four
#: gates that need no data of any kind: the machine-neutrality scan (pure
#: text), the one-reader-of-the-device-document check (pure AST), the
#: paths-carry-paths-only check, and the no-deck-is-bundled check.
#:
#: ★That is worse than a stale mark.  Those two AST/text gates are the ones
#: that catch a machine constant or a second document reader creeping back
#: in, and they are cheap by design so they can run every time — the same
#: reasoning ``test_oracle_reachable`` is built on.  A gate that cannot run
#: reports nothing, and reports it as a skip that reads like "this
#: distribution ships no machine data".
pytestmark = requires_machine
from fylite import device as dev
from fylite import device


def _est2_meas():
    return dict(shot=70754, itime_ms=3500, plasma=4.99e5, btor=1.8,
                basis="est2", brsp=[3e5] * 12, coils=[0.05] * 35,
                expmp2=[0.1] * device.NMAGPRI)


def test_device_data_self_contained():
    assert len(device.B_PROBE_NODES) == 79 and len(device.FLUX_LOOP_NODES) == 35
    assert len(device.PF_NODES) == 12 and device.PF_TURNS[6] == 248
    assert len(device.BITMPI) == 79 and len(device.PSIBIT) == 35
    assert sum(device.FWTMP2_MASK) == 26            # only 26/79 probes trusted
    assert device.FWTSI_MASK.count(0) == 5          # loops 15,32,33,34,35 off
    assert device.LIMITR == 60 and len(device.XLIM) == 60
def test_no_device_description_is_bundled_with_the_package():
    """★The inverse of what this test used to assert.  It once checked that
    ``east_device.yaml`` SHIPPED inside the package; the distribution now
    ships none on purpose (code and machine description have different
    owners and different licences), and the document is an input resolved
    through ``$FYLITE_DEVICE_DIR``.  A test still asserting the old
    arrangement is a claim about a package that no longer exists.
    """
    from pathlib import Path as _P
    import fylite
    pkg = _P(fylite.__file__).parent
    assert not list(pkg.rglob("east_device.yaml"))
    assert not list(pkg.rglob("*.ddd"))
    #: and the configured one loads through the one door
    doc = device.document()
    assert doc["@type"] == "fyo:DeviceDescription"


def test_device_yaml_uses_fyo_dd_v4_key_names():
    d = device.EAST_DEVICE
    # fyo semantics in this port are JSON-LD (@context/@id/@type) — the same
    # convention fyo.measurements stamps on measurement documents.
    assert d["@type"] == "fyo:DeviceDescription"
    assert d["@id"].startswith("fylite:device/")
    assert "fyo" in d["@context"] and d["_dd_version"] == "4.1.1"
    for sec in ("magnetics", "pf_active", "wall", "interferometer", "polarimeter"):
        assert d[sec]["@type"].startswith("fyo:"), sec
    # every top-level physics group is an IDS name, not an invented one
    for ids in ("magnetics", "pf_active", "wall", "interferometer", "polarimeter"):
        assert ids in d, ids
    assert {"b_field_pol_probe", "flux_loop"} <= set(d["magnetics"])
    assert "coil" in d["pf_active"]
    #: ★``limiter.unit`` is an ARRAY of structures in the DD, and EAST carries
    #: two era-dependent contours in it (``efit_w_pf``, ``m-file``).  This
    #: line asserted ``"outline" in ...["unit"]`` against a bare mapping and
    #: went on "passing" as a skip through the whole change that made it a
    #: list — the module was gated on a reference discharge none of its cases
    #: opens, so nothing here had run in a long time.
    #: `description_2d` is the DD's array now (`@fyo-table DEVICE`)
    units = d["wall"]["description_2d"][0]["limiter"]["unit"]
    assert isinstance(units, list) and units, units
    assert {"efit_w_pf", "m-file"} <= {u["name"] for u in units}
    for u in units:
        assert {"r", "z"} <= set(u["outline"]), u.get("name")
    los = d["interferometer"]["channel"][0]["line_of_sight"]
    assert {"r", "z"} <= set(los["first_point"])


def test_constants_still_match_the_yaml_channel_for_channel():
    """The re-export must not drift from the file it loads."""
    d = device.EAST_DEVICE
    pr = d["magnetics"]["b_field_pol_probe"]
    lo = d["magnetics"]["flux_loop"]
    assert device.B_PROBE_NODES == tuple(c["name"] for c in pr)
    assert device.FWTMP2_MASK == tuple(c["weight"] for c in pr)
    assert device.BITMPI == tuple(c["bit_error"] for c in pr)
    assert device.FLUX_LOOP_NODES == tuple(c["name"] for c in lo)
    assert device.PSIBIT == tuple(c["bit_error"] for c in lo)
    assert len(device.B_PROBE_NODES) == device.NMAGPRI == 79
    assert len(device.FLUX_LOOP_NODES) == device.NSILOP == 35
    assert len(device.PF_NODES) == device.NFCOIL == 12
    assert len(device.XLIM) == len(device.YLIM) == device.LIMITR == 60
    assert len(device.POINT_ZPOL) == device.POINT_NCHORD == 11
    assert len(device.PCS_PROBE_NODES_GEOM) == 38


def test_operational_settings_are_config_but_not_dressed_as_an_ids():
    """Machine-neutral code means the solver settings are config too — but they
    have no IDS home, so they must not masquerade as one."""
    op = device.EAST_OPERATIONAL
    assert op["@type"] == "fylite:OperationalSettings"     # not fyo:*
    assert {"probe_gate", "gui_v5_fig", "fit_control", "point_density_fit"} <= set(op)
    # and the namelist writer reads them from there, not from its own literals
    #: ★★2026-09-01：此前这四条经 `io.kfile` 的惰性属性读同一批数。kfile 已随
    #: EFIT k-file 写入机整体移除，而这些**门限与拟合缺省本来就是装置文档的内容**
    #: ——经一个写输入文件的模块去读它们，多的是一个地址，不是一个来源。
    assert float(op["probe_gate"]["min_tesla"]) == 0.02
    assert float(op["probe_gate"]["max_tesla"]) == 1.0
    assert op["fit_control"]["MXITER"] == -50
    # the IDS groups stay clean of solver keys
    for ids in ("magnetics", "pf_active", "wall"):
        assert "MXITER" not in str(device.EAST_DEVICE[ids])
def test_the_code_layer_is_machine_neutral():
    """No module may hold machine constants: every EAST-specific number lives in
    the device config.  The check is textual on purpose — a constant that came
    back would be invisible to any behavioural test."""
    import re as _re
    from pathlib import Path as _P
    import fylite
    pkg = _P(fylite.__file__).parent
    # a few machine numbers that used to be hard-coded in _east_device.py
    banned = {
        "0.62866": "PF coil R", "1.35838": "limiter R", "2.6635": "probe R",
        "432.5e-6": "POINT laser wavelength", "2.62e-13": "POINT Faraday const",
        "HBPH1T": "probe node name", "PCBPV1T": "PCS probe node name",
        "FL1B": "flux-loop node name", "point_n1": "POINT node name",
    }
    offenders = []
    #: ★``rglob``, not ``glob``.  This scanned the 12 top-level modules and
    #: none of the 42 under ``io/`` / ``scenario/`` / ``engine/`` — so the
    #: rule "no module may hold machine constants" was enforced on a fifth of
    #: the package, and the four subpackages that grew since are exactly
    #: where a constant would land now.  It was clean when widened; that is
    #: the point of widening it while it is.
    for f in sorted(pkg.rglob("*.py")):
        body = f.read_text(encoding="utf-8")
        # strip comments/docstrings crudely: only flag code lines
        code = "\n".join(l.split("#")[0] for l in body.splitlines())
        for lit, what in banned.items():
            if lit in code:
                offenders.append(f"{f.relative_to(pkg)}: {lit} ({what})")
    assert not offenders, "machine constants leaked back into code: " + "; ".join(offenders)


def test_no_module_but_device_names_an_mdsplus_node():
    """★★The rule the blocklist above cannot express.

    That scan looks for NINE SPECIFIC LITERALS that leaked out of
    ``_east_device.py`` once.  It can therefore only ever re-find that leak —
    and a new one was sitting in the package while it passed:
    ``scenario/model/lh.py`` carried EAST's two LH systems (frequencies,
    nameplate powers, ``n_∥`` bands, ports, and the MDSplus nodes ``PLHI1`` /
    ``PLHR1`` / ``PLHI2`` / ``PLHR2``) as the DEFAULT ARGUMENT of
    ``east_launchers``.  A machine description in a function signature, in a
    package whose README opens with "No machine description".

    ★So this checks a SHAPE instead of a list.  An MDSplus node name is a
    short all-caps identifier written as a string next to an ``injected`` /
    ``reflected`` / ``node`` / ``nodes`` key, and the only module allowed to
    hold one is ``device.py`` — which reads them from the document.  A shape
    can catch the next leak; a list can only catch the last one.
    """
    import re as _re
    from pathlib import Path as _P
    import fylite
    pkg = _P(fylite.__file__).parent
    #: a node-ish literal: 4-12 chars, all caps + digits, at least one digit
    node = _re.compile(r"""["']([A-Z][A-Z0-9_]{3,11})["']""")
    ctx = _re.compile(r"\b(inject|reflect|node|tree|mds|signal|tag)", _re.I)
    bad = []
    for f in sorted(pkg.rglob("*.py")):
        if f.name in ("device.py", "_paths.py"):
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#")[0]
            if not ctx.search(code):
                continue
            for m in node.finditer(code):
                if any(c.isdigit() for c in m.group(1)):
                    bad.append(f"{f.relative_to(pkg)}:{i} {m.group(1)!r}")
    assert not bad, (
        "an MDSplus-shaped node name outside device.py:\n  " + "\n  ".join(bad)
        + "\n\nNode names are machine description.  Put it in the device "
          "document and read it through fylite.device.")


def test_exactly_one_module_reads_the_device_document():
    """One module reads the device document, and it is the one named for it.

    ★It used to be ``imas_io.py`` — which also parsed MEASUREMENT documents,
    so "bad input" meant two different things there.  The device half lives
    in ``device.py`` now, beside the resolution of WHERE the document is.

    ★The old detection here searched only the text before the module's
    first triple quote — which, for any module with a docstring, is nothing
    at all.  It passed on its other clause (a constant since retired) and
    would not have caught a second reader.  This one walks the AST.
    """
    import ast
    from pathlib import Path as _P
    import fylite
    pkg = _P(fylite.__file__).parent

    def calls_loader(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "load_device"):
                return True
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "load_device"):
                return True
        return False

    readers = sorted(f.name for f in pkg.rglob("*.py") if calls_loader(f))
    assert readers == ["device.py"], readers


def test_load_device_fails_loud_on_a_half_a_device(tmp_path):
    """A device file quietly missing pf_active would build a machine with no
    coils; that must be an error, not a silent half-machine."""
    import pytest as _pt
    ok = device.document()
    p = tmp_path / "dev.yaml"
    import yaml
    half = {k: v for k, v in ok.items() if k != "pf_active"}
    p.write_text(yaml.safe_dump(half, allow_unicode=True))
    with _pt.raises(device.DeviceDocumentError, match="pf_active"):
        device.load_device(p)
    # and a document with no semantic header at all
    p2 = tmp_path / "plain.yaml"
    p2.write_text(yaml.safe_dump({k: v for k, v in ok.items()
                                  if not k.startswith("@")}, allow_unicode=True))
    with _pt.raises(device.DeviceDocumentError, match="semantic header"):
        device.load_device(p2)


def test_paths_module_carries_paths_only():
    """`_paths` is about package resources; machine facts and compiled dims are
    config now, so none of them may reappear there."""
    from pathlib import Path as _P
    import fylite
    body = (_P(fylite.__file__).parent / "_paths.py").read_text(encoding="utf-8")
    code = "\n".join(l.split("#")[0] for l in body.splitlines())
    for n in ("NW", "NH", "NFCOIL", "NSILOP", "NPROBE", "RCENTR", "DEFAULT_GRID"):
        assert f"{n} =" not in code and f"{n}=" not in code, n


def test_declared_compiled_dims_are_verified_against_the_shipped_tables():
    """A config that disagrees with the binary is worse than a literal: it looks
    authoritative and is wrong.  So the declaration is checked, not trusted."""
    v = device.verify_solver_dims()
    assert v["ok"] and v["declared"] == {"nw": 65, "nh": 65}
    assert (v["box"]["nw"], v["box"]["nh"]) == (device.NW, device.NH)
    assert device.SOLVER_DIMS["@type"] == "fylite:CompiledDimensions"
    # the note must say it is a declaration, not a knob
    assert "编译期" in device.SOLVER_DIMS["note"]


def test_machine_facts_come_from_config():
    assert device.EAST_MACHINE["@type"] == "fyo:machine"
    assert device.RCENTR == device.EAST_MACHINE["r_centre"] == 1.75
    g = device.EAST_MACHINE["default_grid"]
    assert device.DEFAULT_GRID == (g["r_min"], g["r_max"], g["z_min"], g["z_max"])
