"""Protocol-member conformance — the data/declarative plane (SP-REPORT-15 T-3.1).

The execution-domain twin of this suite is ``test_protocol_conformance.py``
(six-phase protocol, I-1..I-8).  This file applies the same three-part
discipline to the *manifest* layer introduced by SP-REPORT-15:

* **PART A — structure.**  The five first-batch manifests (三算一流一源) carry
  the required semantic keys, fyo-typed ports, and well-formed governance
  projections; the catalog reflects the builders (never hand-copied).
* **PART B — vendored-schema validation.**  Each ``fylite:projection``
  validates against the matching vendored SpData schema
  (``fylite/_spec/*.schema.json``).  Skipped when the optional ``jsonschema``
  package is absent.
* **PART C — independence + drift.**  The new modules import nothing from the
  sp / fy ecosystem (I-8 extended); the vendored schemas byte-match the SpData
  worktree when one is present (upstream-wins discipline), else skipped —
  exactly PART C's "cross-check only if the upstream happens to be there".
* **PART D — semantic round-trip.**  ``to_fyo`` -> ``interpret_measurements``
  reproduces the flat measurement dict; plain input is untouched; the
  RunManifest semantic keys are strictly additive.
"""
from __future__ import annotations

import ast
import inspect
import json
import pathlib

import pytest

from conftest import requires_machine
from fylite import engine, fyo
from fylite import device

#: device-derived counts are read through the module at use time
pytestmark = requires_machine

try:
    import jsonschema  # optional — validation gains teeth when present
    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    HAVE_JSONSCHEMA = False

DOCS = engine.load_manifests()
#: ★★It was a frozen list of five ("the first batch"), and a frozen list is
#: the wrong shape for a set that is meant to GROW: adding the seven scenario
#: tools to the tool face (FYL-REPORT-01 L-3) made this file red without any
#: of its invariants being violated.  What is worth gating is the RULES —
#: one workflow, one source, the rest solvers; ids namespaced; artifact ids
#: shaped and ending in the name — so the set is read from the tree and the
#: rules are asserted over it.
NAMES = tuple(sorted(DOCS))

#: the two singular members, by kind (everything else is a compute artifact)
_ONE_OF_A_KIND = {"workflow-ir/2.0": "kinetic_reconstruction",
                  "data-artifact/2.0": "east_mdsplus"}
SPDATA_SCHEMAS = pathlib.Path("/home/salmon/workspace/spdata/schemas")


# --------------------------------------------------------------------------- #
# PART A — structure
# --------------------------------------------------------------------------- #

def test_the_set_is_solvers_plus_one_workflow_and_one_source():
    kinds = {n: d["fylite:projection"]["$schema"] for n, d in DOCS.items()}
    for schema, name in _ONE_OF_A_KIND.items():
        assert [n for n, k in kinds.items() if k == schema] == [name]
    solvers = {n for n, k in kinds.items() if k == "compute-artifact/2.0"}
    assert solvers == set(DOCS) - set(_ONE_OF_A_KIND.values())
    assert len(solvers) >= 3


@pytest.mark.parametrize("name", NAMES)
def test_structure_is_clean(name):
    assert engine.validate_structure(DOCS[name]) == []


@pytest.mark.parametrize("name", NAMES)
def test_ids_and_artifact_ids_are_namespaced(name):
    doc = DOCS[name]
    assert doc["@id"] == f"fylite:{name}"
    aid = doc["fylite:projection"]["artifact_id"]
    tenant, project, kind, local = aid.split("/", 3)
    #: ``fylite/<project>/<kind>/<name>`` — the project says what the artifact
    #: is BOUND to: ``east`` for the machine-bound ones (the EAST tree, the
    #: 65x65 reconstruction), ``scenario`` for the four scenario lines, which
    #: take their machine from a deck and are not EAST's.
    assert tenant == "fylite" and project in ("east", "scenario")
    assert kind in ("compute_artifact", "data_artifact", "workflow_template")
    assert local == name


def test_solver_kind_is_well_known():
    """ADR-006 retired external/script_block kinds; the three compute
    artifacts use the well-known ``solver`` kind instead."""
    for n in ("efit", "neo", "tglf"):
        assert DOCS[n]["fylite:projection"]["kind"] == "solver"


@pytest.mark.parametrize("name", NAMES)
def test_ports_are_fyo_typed(name):
    ports = DOCS[name]["fylite:ports"]
    for side in ("in", "out"):
        for p in ports[side]:
            assert p["data_type"].startswith("fyo:"), (name, p)


def test_trust_state_is_honest():
    """Unpromoted artifacts say so: provenance unverified / sandbox_local,
    signature explicitly UNSIGNED — never a fabricated trust claim."""
    for n in ("efit", "neo", "tglf", "east_mdsplus"):
        proj = DOCS[n]["fylite:projection"]
        assert proj["provenance_class"] == "unverified"
        assert proj["signature"]["value"] == "UNSIGNED"
    wf = DOCS["kinetic_reconstruction"]["fylite:projection"]
    assert wf["header"]["provenance_class"] == "sandbox_local"
    assert wf["header"]["egress_allowed"] is False


#: manifests that declare which registered scenario tool they are
_TOOL_DOCS = {n: d["fylite:tool"] for n, d in DOCS.items() if "fylite:tool" in d}


def test_every_built_scenario_tool_is_on_the_tool_face():
    """★★The skill taught ten capabilities the tool face did not carry.

    ``fylite.scenario.TOOLS`` is the register the browser and Python share —
    organised by PURPOSE, which is the granularity a caller can route on —
    while the tool face carried the method-level artifacts (efit / neo /
    tglf) and asked the caller to know which solver answers their question.
    Every BUILT tool is now declared by a manifest; a tool that is not built
    stays absent, because ``scenario`` has no function for it either.
    """
    from fylite.scenario import TOOLS
    exposed = set(_TOOL_DOCS.values())
    missing = sorted(set(TOOLS) - exposed)
    assert not missing, (
        f"registered scenario tools with no manifest: {missing} — a "
        "capability the skill teaches and the tool face cannot run")


def test_a_declared_tool_key_is_a_real_one():
    from fylite.scenario import TOOLS
    unknown = {n: k for n, k in _TOOL_DOCS.items() if k not in TOOLS}
    assert not unknown, f"manifests naming tools that are not registered: {unknown}"


def test_one_tool_one_door():
    """★A capability with two manifests is two doors on one entry, and a
    caller cannot tell which one the caveat belongs to."""
    seen = {}
    for name, key in _TOOL_DOCS.items():
        seen.setdefault(key, []).append(name)
    doubled = {k: v for k, v in seen.items() if len(v) > 1}
    assert not doubled, f"one tool, two manifests: {doubled}"


def test_the_reduced_tier_note_is_derived_not_copied():
    """The description a caller reads carries the D-2 caveat, and carries it
    from ``scenario.TOOLS`` — not from a sentence pasted into the manifest."""
    from fylite.scenario import TOOLS
    tools = {t["name"]: t for t in engine.llm_tools()}
    for name, key in _TOOL_DOCS.items():
        desc = tools[f"fylite_{name}"]["description"]
        assert TOOLS[key]["caveat"] in desc, name
        assert TOOLS[key]["caveat"] not in json.dumps(DOCS[name],
                                                      ensure_ascii=False), (
            f"{name}: the caveat is COPIED into the manifest; it belongs to "
            "scenario.TOOLS and would drift from it here")


#: manifests that declare what a STRUCTURED argument must contain
_SHAPE_DOCS = {n: d["fylite:argument_shapes"] for n, d in DOCS.items()
               if "fylite:argument_shapes" in d}

#: the other required arguments each shaped entry needs before it gets far
#: enough to look inside the structure under test
_SHAPE_FIXTURES = {
    "efit": {}, "tglf": {}, "discharge": {"ip": 4.0e5},
    "feasible": {"r0": 1.85, "axis1": {"name": "r0", "values": [1.8]},
                 "axis2": {"name": "r0", "values": [1.8]}},
}


def test_a_declared_shape_is_held_against_the_behaviour(request):
    """★★Reflection cannot see what a structured argument must contain: a
    signature says ``meas: dict`` and the deck it wants is three named
    arrays.  Measured, before the declaration: ``fylite_efit(meas={})``
    answered ``KeyError: 'brsp'`` — the truth, one key at a time, with the
    caller guessing between rounds.

    So the declaration is checked against the code rather than trusted: call
    the entry with the structure EMPTY and the failure must name a key the
    manifest declares.  A shape that drifts from what the entry reads goes
    red here.
    """
    assert _SHAPE_DOCS, "no manifest declares an argument shape any more"
    for name, shapes in sorted(_SHAPE_DOCS.items()):
        fn = engine.resolve_entry(DOCS[name]["fylite:entry"])
        for param, shape in sorted(shapes.items()):
            kwargs = dict(_SHAPE_FIXTURES.get(name, {}))
            kwargs[param] = {}
            try:
                fn(**kwargs)
            except Exception as exc:              # noqa: BLE001 — the subject
                message = f"{type(exc).__name__}: {exc}"
            else:
                pytest.fail(f"{name}.{param}: an empty structure was accepted; "
                            "the declared shape claims keys are required")
            assert any(k in message for k in shape["required"]), (
                f"{name}.{param}: the declared required keys "
                f"{shape['required']} appear nowhere in what the entry "
                f"actually complains about ({message})")


def test_a_shaped_argument_reaches_the_tool_schema():
    tools = {t["name"]: t for t in engine.llm_tools()}
    for name, shapes in _SHAPE_DOCS.items():
        props = tools[f"fylite_{name}"]["input_schema"]["properties"]
        for param, shape in shapes.items():
            branch = props[param]["anyOf"][0]
            assert branch["required"] == list(shape["required"])
            assert shape["note"] in props[param]["description"]


def test_catalog_reflects_the_builders():
    cat = engine.manifest_catalog()
    entries = {e["@id"]: e for e in cat["fylite:manifests"]}
    assert set(entries) == {f"fylite:{n}" for n in DOCS}
    for n in NAMES:
        e = entries[f"fylite:{n}"]
        assert e["ports"] == DOCS[n]["fylite:ports"]
        assert e["entry"] == DOCS[n]["fylite:entry"]


@pytest.mark.parametrize("name", NAMES)
def test_entries_resolve_to_real_callables(name):
    """The catalog is a reflection contract: every declared entry point must
    import and be callable — a manifest for a phantom function is drift."""
    fn = engine.resolve_entry(DOCS[name]["fylite:entry"])
    assert callable(fn)


def test_data_artifact_channel_counts_are_reflected():
    addr = DOCS["east_mdsplus"]["fylite:addressing"]
    families = {e["@type"]: e["fylite:channels"] for e in addr["sp:read"]}
    assert families["fyo:magnetics"] == {"flux_loop": device.NSILOP,
                                         "b_field_pol_probe": device.NPROBE}
    assert families["fyo:pf_active"] == {"coil": device.NFCOIL}


def test_files_are_sealed():
    """The authored files are the source; their derived hash fields must be
    current (edit -> `fylite manifest --seal` -> this test verifies the seal
    is idempotent)."""
    for name, doc in DOCS.items():
        assert engine.seal_manifest(doc) == doc, f"{name}: stale hashes"


# --------------------------------------------------------------------------- #
# PART A' — workflow DAG integrity
# --------------------------------------------------------------------------- #

WF = DOCS["kinetic_reconstruction"]["fylite:projection"]


def test_workflow_is_a_template_with_bound_versions_absent():
    assert WF["header"]["form"] == "template"
    assert "bound_artifact_versions" not in WF["header"]


def test_workflow_nodes_are_unique_and_edges_resolve():
    nodes = {n["id"]: n for n in WF["dag"]["nodes"]}
    assert len(nodes) == len(WF["dag"]["nodes"])
    for e in WF["dag"]["edges"]:
        for node_key, port_key, side in (("source_node", "source_port", "out"),
                                         ("target_node", "target_port", "in")):
            node = nodes[e[node_key]]
            ports = {p["port_id"] for p in node["ports"][side]}
            assert e[port_key] in ports, (e["id"], e[port_key], node["id"])


def test_task_nodes_reference_first_batch_compute_artifacts():
    task_refs = {n["artifact_ref"]["artifact_id"]
                 for n in WF["dag"]["nodes"] if n["kind"] == "task"}
    assert task_refs == {f"fylite/east/compute_artifact/{n}"
                         for n in ("efit", "neo", "tglf")}


def test_closure_edges_are_feedback_and_dag_is_acyclic_without_them():
    """The 平衡↔电流↔剖面↔通量 closure rides `feedback` edges (excluded from
    the acyclicity check by contract); the remaining data edges must be a DAG."""
    feedback = [e for e in WF["dag"]["edges"] if e.get("kind") == "feedback"]
    assert {(e["source_node"], e["target_node"]) for e in feedback} == {
        ("neo", "efit"), ("tglf", "profiles")}

    data_edges = [(e["source_node"], e["target_node"])
                  for e in WF["dag"]["edges"] if e.get("kind") != "feedback"]
    order, seen = [], set()

    def visit(v, stack):
        assert v not in stack, f"cycle through {v} in non-feedback edges"
        if v in seen:
            return
        seen.add(v)
        for s, t in data_edges:
            if s == v:
                visit(t, stack | {v})
        order.append(v)

    for n in {s for s, _ in data_edges}:
        visit(n, frozenset())


def test_loop_children_are_the_selfconsistency_stages():
    inner = {n["id"] for n in WF["dag"]["nodes"]
             if n["parent_id"] == "selfconsistency"}
    assert inner == {"efit", "profiles", "neo", "tglf"}
    loop = next(n for n in WF["dag"]["nodes"] if n["id"] == "selfconsistency")
    assert loop["kind"] == "loop"
    # loop controls mirror the real self_consistent defaults
    assert loop["attrs"] == {"max_iter": 8, "tol": 0.02}


def test_measurement_input_binds_the_data_artifact():
    src = next(n for n in WF["dag"]["nodes"] if n["id"] == "measurements")
    ref = src["ports"]["out"][0]["data_ref"]
    assert ref["data_artifact_id"] == "fylite/east/data_artifact/east_mdsplus"


# --------------------------------------------------------------------------- #
# PART B — vendored-schema validation
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(not HAVE_JSONSCHEMA, reason="optional jsonschema missing")
@pytest.mark.parametrize("name", NAMES)
def test_projection_validates_against_vendored_schema(name):
    engine.validate_projection(DOCS[name])


@pytest.mark.skipif(not HAVE_JSONSCHEMA, reason="optional jsonschema missing")
def test_validation_actually_rejects(name="efit"):
    """Guard against a vacuously-green validator."""
    doc = json.loads(json.dumps(DOCS[name]))
    del doc["fylite:projection"]["owner"]
    with pytest.raises(jsonschema.ValidationError):
        engine.validate_projection(doc)


# --------------------------------------------------------------------------- #
# PART C — independence + drift
# --------------------------------------------------------------------------- #

def _assert_no_ecosystem_imports(module):
    src = pathlib.Path(inspect.getfile(module)).read_text()
    banned = {"sp", "fytok", "fyeq", "fytrans", "fydata", "spdm"}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            roots = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            roots = [(node.module or "").split(".")[0]]
        else:
            continue
        assert not (set(roots) & banned), \
            f"{module.__name__} imports {roots} (line {node.lineno})"


def test_manifest_layer_imports_nothing_from_the_sp_or_fy_ecosystem():
    """I-8 extended to the declarative/data/tool planes: fyo and sp appear
    only as CURIE strings (vocabulary), never as imports (code)."""
    from fylite.io import est2
    for module in (engine, fyo, est2):
        _assert_no_ecosystem_imports(module)


@pytest.mark.skipif(not SPDATA_SCHEMAS.is_dir(),
                    reason="spdata worktree not present — vendored copy "
                           "stands alone by design")
@pytest.mark.parametrize("basename", ["common", "compute_artifact",
                                      "data_artifact", "workflow_ir"])
def test_vendored_schemas_match_upstream(basename):
    """Upstream-wins: when the SpData worktree is checked out next door, the
    vendored copy must be byte-identical (re-vendor on upstream change)."""
    ours = (engine.SPEC_DIR / f"{basename}.schema.json").read_bytes()
    theirs = (SPDATA_SCHEMAS / f"{basename}.schema.json").read_bytes()
    assert ours == theirs, f"_spec/{basename}.schema.json drifted from spdata"


# --------------------------------------------------------------------------- #
# PART D — semantic round-trip + RunManifest
# --------------------------------------------------------------------------- #

def _sample_measurements() -> dict:
    return {
        "plasma": 4.0e5,
        "btor": -1.8,
        "brsp": [float(1000 + i) for i in range(device.NFCOIL)],
        "coils": [0.01 * i for i in range(device.NSILOP)],
        "expmp2": [0.001 * i for i in range(device.NPROBE)],
        "source": "test",
        "time_s": 3.5,
        "coil_current_units": "A.turns",
    }


def test_to_fyo_then_interpret_round_trips():
    meas = _sample_measurements()
    doc = fyo.measurements(meas)
    assert doc["@type"] == "fylite:MeasurementSet"
    assert doc["magnetics"]["@type"] == "fyo:magnetics"
    back = fyo.as_measurements(doc, time_s=meas["time_s"])
    for key in ("plasma", "btor", "time_s"):
        assert back[key] == pytest.approx(meas[key])
    for key in ("brsp", "coils", "expmp2"):
        assert back[key] == pytest.approx(meas[key])
    assert back["source"] == "semantic:normal-form"


def test_tf_field_uses_the_imas_r_bt_convention():
    doc = fyo.measurements(_sample_measurements())
    assert doc["tf"]["b_field_tor_vacuum_r"] == pytest.approx(-1.8 * device.RCENTR)


def test_plain_dict_input_is_a_pass_through():
    """The semantic layer is additive: a plain IMAS-shaped dict takes the
    exact same path as before."""
    doc = engine.strip_semantic(fyo.measurements(_sample_measurements()))
    assert not engine.is_semantic(doc)
    via_semantic = fyo.as_measurements(doc, time_s=3.5)
    direct = fyo.as_measurements(doc, 3.5)
    assert via_semantic == direct


def test_strip_semantic_removes_at_and_dollar_aliases():
    doc = {"@id": "x", "$type": "y", "a": {"@context": {}, "b": [
        {"$onto": "z", "c": 1}]}}
    assert engine.strip_semantic(doc) == {"a": {"b": [{"c": 1}]}}


def test_run_manifest_semantic_keys_are_additive():
    rm = engine.RunManifest(created="2026-08-01T00:00:00Z",
                            code={"rev": "test"}, environment={})
    flat = rm.to_dict(semantic=False)
    sem = rm.to_dict()
    assert "@context" not in flat
    assert sem["@id"] == "urn:fylite:run/2026-08-01T00:00:00Z"
    assert sem["@type"] == ["fylite:RunManifest", "prov:Entity"]
    # every legacy key survives with an identical value
    for k, v in flat.items():
        assert sem[k] == v
    assert set(sem) - set(flat) == {"@context", "@id", "@type"}
