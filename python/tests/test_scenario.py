"""``fylite.scenario`` — the four lines on the Python side (FYL-DESIGN-08).

Three kinds of check, and the first two are the ones that keep this package
from becoming a navigation layer that promises more than the repository has:

* **the register against the design document.**  FYL-DESIGN-07 §8 is the
  oracle for what is covered, partly covered, unbuilt and deliberately not
  built.  ``app/tests/validate-site.mjs`` no longer parses it (that stopped being
  an app-side oracle when the lines model was withdrawn), so this is the
  one place the register is held to the document.
* **D-4′.**  Nothing under ``scenario/`` may import ``scipy`` or
  ``contourpy``: physics and numerics have one host.  Checked on the AST, so
  it fails on the import rather than on the first number.
* **the tools themselves** — that each runs, carries its reduced-tier
  statement, and (where it is cheap enough to assert) that it discriminates.
  ★A tool that "passes" on a degenerate case is worse than an untested one:
  it reports a tick.  So the breakdown check drives the design into a corner
  where the answer must be "no, and here is what stopped it", and the
  coupled check asserts the METRIC moves round to round rather than the
  temperature, which barely moves at all.
"""
import ast
import re
from pathlib import Path

import numpy as np
import pytest

from conftest import east_measurements

from fylite import kernel, scenario as S
from fylite.io import geqdsk

ROOT = Path(__file__).resolve().parents[2]

#: ★The oracle is the coverage table, not a path.  That document has been
#: renamed twice while this test existed (`app-scenarios.md` ->
#: `FYL-DESIGN-07.md` -> `docs/archive/`), and each time a passing suite went
#: red for a reason that had nothing to do with what it checks.  So the
#: candidates are tried in order and the FIRST that exists wins; if none does,
#: the test skips saying so rather than failing as though the register had
#: drifted.
_DESIGN07_CANDIDATES = (
    "docs/archive/FYL-DESIGN-07.md",
    "docs/design/FYL-DESIGN-07.md",
    "docs/design/app-scenarios.md",
)
DESIGN07 = next((ROOT / c for c in _DESIGN07_CANDIDATES if (ROOT / c).exists()),
                None)
GFILE = ROOT / "tests/data/FYDOC-CASE-12-synthetic/g_synthetic.geqdsk"

needs_kernel = pytest.mark.skipif(not kernel.available(),
                                  reason="Rust kernel not built")


# --------------------------------------------------------------------------- #
# 1. the register against its oracle
# --------------------------------------------------------------------------- #
def _doc_rows() -> dict:
    """§8's requirement rows.

    ★No longer "as ``validate-lines.mjs`` parses them": that gate is gone
    (``validate-site.mjs`` replaced it and deliberately dropped the row
    comparison), so this parser is the only one, and naming a departed twin
    made it read as the mirror of something.
    """
    if DESIGN07 is None:
        pytest.skip("the coverage table document is not in this checkout; "
                    f"looked for {list(_DESIGN07_CANDIDATES)}")
    md = DESIGN07.read_text(encoding="utf-8")
    sec = next(s for s in re.split(r"^## ", md, flags=re.M)
               if s.startswith("8. 覆盖表"))
    rows = {}
    for line in sec.split("\n"):
        m = re.match(r"^\|\s*S-\d+\s*\|\s*`([^`]+)`[^|]*\|\s*([●◐○—])\s*\|",
                     line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def test_the_register_matches_the_design_document_row_for_row():
    doc = _doc_rows()
    assert len(doc) >= 20, ("§8 parsed only %d rows — the parser missed the "
                            "table" % len(doc))
    mine = {r["fr"]: r["verdict"] for r in S.coverage()}
    assert set(doc) == set(mine), {
        "in the document, not in the register": sorted(set(doc) - set(mine)),
        "in the register, not in the document": sorted(set(mine) - set(doc))}
    for fr, verdict in doc.items():
        assert mine[fr] == verdict, f"{fr}: document {verdict}, register {mine[fr]}"


#: 浏览器的**页名**与这个包的**场景线名**，在一处对不上，列在这里。
#:
#: ★★2026-09-01：设计线的页被浏览器改叫 `pulse_design`（`scenario-design.js` →
#: `scenario-pulse_design.js`），而线的名字仍是 `design`。此前这道闸直接拿文件名当
#: 线名比，于是「页改了个名」表现为「`discharge` 不属于它所在的那条线」——一句
#: 与事实无关的话。**页名是界面词，线名是领域词，两者本就可以不同**；能不同，就
#: 得有一处显式写下它们怎么对应，而不是靠两边碰巧同名。
#: ★这张表只许**因浏览器改名而增删**，不许用来把一个真的放错线的能力糊过去：
#: 下面 `line_of` 的成员检查照旧，改名之后仍然是它在判。
_PAGE_LINE = {"pulse_design": "design"}


def _browser_bars() -> dict:
    """Every 功能栏 the browser registers, bar id -> page.

    ★Read from the DECLARATION SITE (``<PAGE>.bar('<id>', {...})`` in
    ``app/assets/scenario-<page>.js``), not from a list that names them a
    second time: a second list is a thing that can disagree with the pages.
    The page comes from the file name, so a bar cannot be attributed to a
    page it is not declared on.
    """
    bars = {}
    for js in sorted((ROOT / "app/assets").glob("scenario-*.js")):
        page = _PAGE_LINE.get(js.stem.split("-", 1)[1], js.stem.split("-", 1)[1])
        for bar in re.findall(r"\.bar\('(\w+)'", js.read_text(encoding="utf-8")):
            assert bar not in bars, f"{bar} is declared on two pages"
            bars[bar] = page
    assert bars, "no bars found — the app's registration shape changed again"
    return bars


def test_the_tool_set_matches_the_browsers():
    """The two hosts' capability names, and every disagreement declared.

    ★★The oracle has moved THREE times, and this is the third: first
    ``app/assets/lines.js``'s ``PAGES`` map, then ``data-part`` on the pages,
    and now the pages carry ONE part each (``scenario.js``'s own header says
    so: "the four pages carry ONE part each since the site was cut back to
    the four typical scenarios") while the capability-sized unit is the
    功能栏 — ``DESIGN.bar('zerod', …)``.  Against the stale oracle this test
    compared three page names to nine tools and had been red; what it was
    BLIND to in the meantime is the finding: the browser's ``evolve`` bar and
    this package's ``coupled`` are one capability under two names.

    So the equality is gone and three checkable statements replace it:

    1. a tool that declares a ``bar`` must find it in the browser, on a page
       the tool actually belongs to (``line_of`` — MEMBERSHIP, because the
       browser puts a bar where it is USED and ``owner`` says who implements
       it: ``zerod`` is owned by ``model`` and pressed on ``design``);
    2. a tool that declares ``bar: None`` must NOT have one — if the browser
       grows the bar, the register has to notice rather than stay silent;
    3. every remaining bar must be declared in ``BROWSER_ONLY_BARS`` with a
       reason, and no bar may be claimed from both sides at once.
    """
    bars = _browser_bars()
    claimed = {}
    for tool, meta in S.TOOLS.items():
        bar = meta["bar"]
        if bar is None:
            assert tool not in bars, (
                f"the browser now has a bar called {tool!r} — set "
                f"TOOLS[{tool!r}]['bar'] and drop the note that says it has "
                "none")
            continue
        assert bar in bars, (
            f"{tool!r} declares the browser bar {bar!r}, which no page "
            f"registers; the browser has {sorted(bars)}")
        assert bar not in claimed, (
            f"bar {bar!r} is claimed by both {claimed[bar]!r} and {tool!r} — "
            "one capability, two register entries")
        claimed[bar] = tool
        page = bars[bar]
        assert page in S.line_of(tool), (
            f"the browser puts {bar!r} on the {page!r} page, but {tool!r} "
            f"belongs to {S.line_of(tool)} — one of the two is wrong about "
            "which scenario this capability serves")

    loose = sorted(set(bars) - set(claimed))
    assert loose == sorted(S.BROWSER_ONLY_BARS), {
        "undeclared browser bars": sorted(set(loose)
                                          - set(S.BROWSER_ONLY_BARS)),
        "declared but no longer there": sorted(set(S.BROWSER_ONLY_BARS)
                                               - set(loose))}
    for bar in loose:
        assert S.BROWSER_ONLY_BARS[bar].strip(), f"{bar} has an empty reason"


def test_no_browser_bar_is_declared_from_both_sides():
    """★The two registers are halves of one statement, so an id may appear in
    exactly one of them.  Without this, moving a bar from
    ``BROWSER_ONLY_BARS`` onto a tool would leave it in both and each list
    would keep reading as complete on its own."""
    declared = {m["bar"] for m in S.TOOLS.values() if m["bar"]}
    both = declared & set(S.BROWSER_ONLY_BARS)
    assert not both, f"declared on both sides: {sorted(both)}"


def test_every_tool_has_an_entry_that_exists_and_a_reduced_tier_note():
    for tool, meta in S.TOOLS.items():
        mod_name, func = meta["entry"].split(".")
        mod = getattr(S, mod_name)
        assert callable(getattr(mod, func)), meta["entry"]
        assert meta["fr"] and meta["scope"] and meta["caveat"], tool


def test_unbuilt_requirements_are_recorded_as_gaps_not_as_functions():
    """★Every ``○`` row must be named by its line's :func:`gaps`, and must
    NOT have a function.  An unbuilt capability that acquires a callable
    returning zeros is how "not built" starts reading as "built"."""
    named = {g["fr"] for g in S.control.gaps()} | {g["fr"]
                                                   for g in S.analysis.gaps()}
    for row in S.coverage():
        if row["verdict"] == "○":
            assert row["at"] is None, row
            if row["line"] in ("control", "analysis"):
                assert row["fr"] in named, (
                    f"{row['fr']} is unbuilt and unnamed by gaps()")


# --------------------------------------------------------------------------- #
# 2. D-4′
# --------------------------------------------------------------------------- #
FORBIDDEN = {"scipy", "contourpy"}


def test_the_scenario_layer_imports_no_numerics_library():
    pkg = Path(S.__file__).parent
    for path in sorted(pkg.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert name.split(".")[0] not in FORBIDDEN, (
                    f"{path.name} imports {name}: physics and numerics have "
                    "one host (FYL-DESIGN-08 D-4′)")


# --------------------------------------------------------------------------- #
# 3. the tools
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def reference():
    """A real EAST shot's coil currents and plasma current."""
    meas = east_measurements()
    return {"aturns": np.asarray(meas["brsp"], float),
            "ip": float(meas["plasma"])}


@needs_kernel
def test_zerod_carries_its_tier_and_the_two_tiers_are_different_answers():
    ev = S.model.zerod(ip_flattop=1.0e6, te_flattop=10.0)
    assert ev["tier"] == "prescribed"
    assert ev["provenance"]["tool"] == "zerod"
    assert "不是预言" in ev["provenance"]["caveat"]
    pr = S.model.zerod(ip_flattop=1.0e6, te_flattop=10.0, predict=True,
                       bt=2.0)
    assert pr["tier"] == "predicted"
    #: the prescribed pass reads the user's own temperature back; the
    #: predicted pass solves for one.  They must not be the same array.
    assert not np.allclose(pr["prediction"]["te0"], pr["te"][:, 0])


@needs_kernel
def test_transport_steady_solve_responds_to_the_power_it_is_given():
    lo = S.model.transport(power=2.0, chi0=1.0)
    hi = S.model.transport(power=8.0, chi0=1.0)
    assert lo["converged"] and hi["converged"]
    assert hi["y"][0] > 1.5 * lo["y"][0]
    #: the edge is held, so the response is in the profile and not a shift
    assert lo["y"][-1] == pytest.approx(hi["y"][-1], rel=1e-9)


@needs_kernel
def test_transport_refuses_a_closure_it_was_not_given_the_blocks_for():
    from fylite import kernel as K
    with pytest.raises(K.KernelError):
        S.model.transport(closure="neoclassical")
    with pytest.raises(K.KernelError):
        S.model.transport(closure="given")


@needs_kernel
def test_breakdown_meets_the_avalanche_criterion_and_says_so():
    d = S.design.breakdown(r0=1.85, radius=0.3, flux_target=0.3)
    assert d["feasible"] and d["reason"] is None
    assert d["b_max"] <= d["b_tol"]
    assert d["provenance"]["fr"] == ("S10-FR-LIM-1/2",)


@needs_kernel
def test_an_impossible_breakdown_says_which_limit_stopped_it():
    """★The non-degenerate half.  A 3 Wb flux request under a 5 kA-turn box
    cannot be met; what the tool must NOT do is report the trivial
    "everything off" solution as a success because its null is beautiful.

    Measured: that corner gives a null of 8e-7 T — far inside tolerance —
    while delivering 0.015 Wb of the 3 Wb asked for, with eight channels
    sitting on their bound.
    """
    d = S.design.breakdown(r0=1.85, radius=0.3, flux_target=3.0,
                           i_max_aturn=np.full(12, 5.0e3))
    assert not d["feasible"]
    assert d["reason"] == "flux_not_met_at_channel_limits"
    assert d["b_max"] <= d["b_tol"], "the null itself was fine"
    assert abs(d["flux_Wb"]) < 0.5, "the flux was nowhere near the request"
    assert d["blocked_by"], "an infeasible design that names nothing"
    assert all(b["name"].startswith("PF") for b in d["blocked_by"])


@needs_kernel
def test_the_feasible_scan_separates_reachable_from_unreachable():
    """A scan whose every point is feasible tests nothing, so this one is
    driven across the boundary — and the map must land on both sides."""
    f = S.design.feasible(
        axis1={"name": "flux_target", "values": [0.3, 3.0]},
        axis2={"name": "weight_flux", "values": [1.0, 100.0]},
        r0=1.85, radius=0.3)
    assert f["n_points"] == 4
    assert 0 < f["n_feasible"] < f["n_points"], f["feasible"]


@needs_kernel
@pytest.mark.slow
def test_discharge_moves_the_boundary_toward_the_target(reference):
    """The anneal must IMPROVE the shape error against the starting machine
    state.  ★It need not improve monotonically — the search travels from the
    last pass, not the best one — so the assertion is on the best pass, and
    the history is asserted to record every pass including a worse one."""
    d = S.design.discharge(
        target={"r0": 1.88, "a": 0.42, "kappa": 1.6,
                "delta_upper": 0.4, "delta_lower": 0.5},
        ip=reference["ip"], aturns0=reference["aturns"], passes=4,
        max_iter=400, tol=1e-8)
    first = d["history"][0]["err"]
    assert d["shape_error"] < first
    assert d["pass"] >= 1
    assert len(d["history"]) == 5
    #: the returned shape is the traced boundary's, not the target restated
    assert d["shape"]["kappa"] != pytest.approx(1.6, rel=1e-6)


@needs_kernel
@pytest.mark.slow
def test_the_coupled_loop_actually_couples(reference):
    """★The METRIC is what has to move.  With a fixed source and a
    prescribed chi the axis temperature barely responds — measured here,
    ~1e-3 per round against ~4e-2 in V' — so a coupling check written on the
    temperature would pass on a loop whose equilibrium had been unwired.
    """
    c = S.model.coupled(aturns=reference["aturns"], ip=reference["ip"],
                        n_outer=3, n_rho=41, max_iter=400, tol=1e-8)
    assert len(c["history"]) == 3
    assert all(h["surfaces"] > 20 for h in c["history"])
    moved = [h["metric_change"] for h in c["history"][1:]]
    assert all(m > 1e-3 for m in moved), moved
    #: and the feedback is on the amplitude only — the provenance says so,
    #: because a reader who takes this for a shape-feeding loop has taken it
    #: for a stronger claim than it is
    assert c["provenance"]["feedback"] == "pressure amplitude only"


@needs_kernel
def test_profit_fits_and_refuses_to_call_extrapolation_interpolation():
    x = np.linspace(0.0, 0.9, 30)
    y = 1.0 - x ** 2
    f = S.analysis.profit(x, y, sigma_frac=0.02,
                          evaluate_at=np.linspace(0.0, 1.0, 41))
    assert f["order"] <= 3
    assert f["extrapolated"] is True
    assert f["provenance"]["gcv"] == "in-sample only"
    inside = S.analysis.profit(x, y, sigma_frac=0.02)
    assert inside["extrapolated"] is False


@needs_kernel
def test_a_reconstructed_profile_cannot_be_fed_back_as_a_measurement():
    """★The one input that would make the fit a confirmation of itself."""
    derived = {"x": np.linspace(0, 1, 5), "p": np.ones(5),
               "provenance": {"source": S.analysis.DERIVED}}
    with pytest.raises(ValueError, match="confirmation of itself"):
        S.analysis.reconstruction({"plasma": 1.0}, pressure=derived)


@needs_kernel
@pytest.mark.slow
def test_vstab_reports_a_regime_and_responds_to_the_wall(reference):
    g = geqdsk.read_geqdsk(GFILE)
    near = S.control.vstab(g, coil_aturns=reference["aturns"])
    far = S.control.vstab(g, coil_aturns=reference["aturns"],
                          vessel_scale=1.5)
    assert near["regime"] in ("stable", "resistive-wall", "ideal-unstable")
    #: the wall distance is the discriminator: moving it must change the
    #: answer, or the passive structure is not in the model at all
    assert near["growth_rate"] != far["growth_rate"]


def test_no_scenario_module_reads_a_gfile_key():
    """★The scenario layer speaks fyo documents, not EFIT deck keys.

    ``fyo.as_equilibrium`` is the door: an ``fyo:equilibrium`` document
    passes through, a g-file path or a ``read_geqdsk`` dict is converted ON
    THE WAY IN, and nothing inside reads a deck name.  ``scenario/model``
    was moved onto that door first; ``control`` and ``design`` were not, and
    for a while three functions carried the format in their own names
    (``vertical_mode_from_gfile``, ``plasma_filaments_from_gfile``,
    ``plasma_mass_from_gfile``).

    ★★What the leak actually cost, beyond naming: `stability.py` and
    `design/shape.py` each carried their OWN copy of the GEQDSK unpacking —
    rebuild the grid from ``rleft``/``rdim``/``nw``, reshape ``psirz`` and
    transpose it out of the deck's ``[z, r]`` into the kernel's ``[r, z]``.
    Three transposes of one convention, in three modules, none of them the
    one place the document settles it.  A fourth copy that got the order
    wrong would not raise; it would return a mirrored plasma.

    The AST, not a grep: these names appear in prose all over this tree.
    """
    import ast
    import fylite
    from pathlib import Path as _P

    #: GEQDSK header/table names.  Deliberately not every g-file key — these
    #: are the ones with an accessor on the document, so a hit means a
    #: consumer went round it.
    #: GEQDSK header/table names.  Deliberately not every g-file key — these
    #: are the ones with an accessor on the document, so a hit means a
    #: consumer went round it.  Banned everywhere under ``scenario/``.
    DECK_KEYS = {"psirz", "simag", "sibry", "rmaxis", "zmaxis", "rbbbs",
                 "zbbbs", "pprime", "ffprim", "qpsi", "fpol", "rleft",
                 "rdim", "zmid", "zdim", "bcentr", "rcentr"}
    #: ★★The KERNEL's solve-result names (:data:`fylite.kernel.FREE_SOLVE_KEYS`).
    #: Neither a file format nor a standard, so neither this rule's original
    #: list nor ``test_deck_names_have_one_source`` could see them — and they
    #: had quietly become a FOURTH vocabulary in this layer, beside the NEO
    #: deck, TGYRO's CGS and TGLF's deck.  ``_metric_on`` read five.
    #:
    #: ★These are allowed AT the kernel boundary and nowhere else: a function
    #: that calls the kernel must unpack what it returns, and forbidding that
    #: would just push the same names one frame out.  What the rule forbids is
    #: the names TRAVELLING — being read in a function that did not make the
    #: call, which is how `_metric_on` came to spell them.
    #:
    #: ★``psi_bnd`` earns its place twice over: the kernel spells it that way,
    #: ``reconstruct``'s result says ``psi_bry``, the DD says
    #: ``psi_boundary``.  Three spellings of one number already.
    ABI_KEYS = {"psi_bnd", "psi_bry", "axis_r", "axis_z", "bnd_kind",
                "xpt_r", "xpt_z", "fb_amp"}
    root = _P(fylite.__file__).parent / "scenario"

    #: ★The exemption is for the functions that CALL A SOLVE — the entries
    #: that return these keys — not for any function that touches the kernel.
    #: The looser rule was tried and it let `_metric_on` keep reading
    #: `psi_bnd`: that function calls `K.trace_surface`, so "calls the kernel"
    #: was true of the very code this rule was written for.  You may unpack
    #: what you solved for; you may not unpack what someone else solved.
    SOLVE_ENTRIES = {"gs_free_solve", "gs_inverse_solve"}

    def _calls_a_solve(fn) -> bool:
        return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in SOLVE_ENTRIES
                   for n in ast.walk(fn))

    #: ★The unit is the TOP-LEVEL function, not each nested one.
    #: `design.discharge` splits its boundary across two sibling closures —
    #: `solve(x)` calls `gs_free_solve`, `measure(res)` unpacks what it
    #: returned — and that is still one boundary, written for readability.
    #: Checking each closure on its own called `measure` a violation, which
    #: would have pushed a real separation-of-concerns into one function to
    #: satisfy a test.
    bad = []
    for f in sorted(root.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        nested = {id(n) for top in ast.walk(tree)
                  if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef))
                  for n in ast.walk(top)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n is not top}
        for fn in [n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and id(n) not in nested]:
            allowed = ABI_KEYS if _calls_a_solve(fn) else set()
            for node in ast.walk(fn):
                #: `x["simag"]` — a subscript by a constant string
                if (isinstance(node, ast.Subscript)
                        and isinstance(node.slice, ast.Constant)
                        and node.slice.value in (DECK_KEYS | ABI_KEYS) - allowed):
                    bad.append(f"{f.relative_to(root)}:{node.lineno} "
                               f"[{node.slice.value!r}] in {fn.name}()")
    assert not bad, (
        "scenario modules read EFIT deck keys or kernel ABI names away from "
        "the boundary:\n  " + "\n  ".join(bad)
        + "\n\nTake the equilibrium through `fyo.as_equilibrium` and read it "
          "with `fyo.psi_map_of` / `axis_of` / `boundary_of` / `profile_of` / "
          "`psi_range_of`; unpack a kernel result where the kernel is called "
          "and pass quantities on.")


def test_no_scenario_signature_names_a_file_format():
    """★A parameter called ``gfile`` is the same defect as a function called
    ``*_from_gfile``, one level in.

    Every one of these took whatever ``fyo.as_equilibrium`` accepts — a
    document, a reconstruction result, a path — so the format in the name was
    the one input it did NOT require.  Seven signatures carried it: the
    ``WaveSource`` and ``BeamSource`` protocols and their implementations, and
    the transport hook.  A protocol's parameter name is the worst place for it,
    too: it binds every backend anyone writes.

    ★★The rule is narrower than "no format names", and the narrowing is the
    reasoning.  A name lies only when the parameter accepts MORE than that
    format, so this bans the EQUILIBRIUM-file spellings — the ones
    ``fyo.as_equilibrium`` made into a door that takes three kinds of input.
    It does not ban ``afile``: ``recon_rs._diagnostic_signals(meas, afile,
    ...)`` really does take an a-file dict and nothing else (``csilop``,
    ``cmpr2``, the forward-model channel values), there is no fyo door for
    it, and that name is TRUE.  The first version of this case flagged it,
    which is how the rule got stated properly.

    ★``kind``/``source`` VALUES are not in scope either — ``"gfile"`` naming a
    file format a caller really is choosing is fine.  What this forbids is a
    parameter whose NAME says the format when its TYPE does not.
    """
    import ast
    import fylite
    from pathlib import Path as _P

    BANNED = {"gfile", "geqdsk", "eqdsk", "gfile_path", "g_file"}
    root = _P(fylite.__file__).parent / "scenario"
    bad = []
    for f in sorted(root.rglob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            a = node.args
            for arg in (*a.posonlyargs, *a.args, *a.kwonlyargs):
                if arg.arg in BANNED:
                    bad.append(f"{f.relative_to(root)}:{node.lineno} "
                               f"{node.name}({arg.arg}=...)")
    assert not bad, (
        "scenario signatures name a file format in a parameter:\n  "
        + "\n  ".join(bad)
        + "\n\nCall it `eq` and take it through `fyo.as_equilibrium` — the "
          "parameter accepts a document, a reconstruction or a path, and only "
          "the name said otherwise.")


def test_the_transport_caveat_says_where_the_particle_source_comes_from():
    """★★A posture only a docstring carries is a posture that leaves with
    the number.

    This package has no fuelling model — no pellet, no gas puff, no beam
    particle source — and that is a deliberate deviation (FYL-DESIGN-03 ②:
    "粒子源无可信 EAST 模型"), not an oversight.  What makes it honest is
    that every transport result SAYS so: the caveat travels with the
    result, which is the whole reason provenance exists here.  If a
    fuelling model ever does arrive, this case is what makes someone
    rewrite the caveat instead of leaving a stale one attached to every
    answer.
    """
    from fylite import scenario as S

    caveat = S.TOOLS["transport"]["caveat"]
    assert "粒子源由调用方给定" in caveat
    assert "本包不含加料模型" in caveat


def test_the_browser_never_stores_anything_in_a_cookie():
    """★★`FYL-SDD-01` DE-COMP-05.1 不变式 5，落成闸子。

    BYOK LLM 前端把读者自己的密钥交给页面。存 `document.cookie` 是错的，理由不是
    偏好：**cookie 随每一次同源请求自动发出**——页面每取一个 `.wasm`、一份算例目录，
    密钥都跟着走一趟，送到托管方的服务器。`sessionStorage` 不会。

    ★这条闸子是**保持**而不是修复：写它的时候全树实测 0 处 `document.cookie`。
    一条今天就成立的规矩，值得有一条闸子替它守着——否则它只是文档里的一句话。

    ★同一 origin 的隔离是**按 origin 不按路径**的（站点发布在
    `fusion-yun.github.io/fylite/`），所以换成 `localStorage` 也不解决同域可读；
    那一条是部署决定，登记在 `FYL-REPORT-02` R2-06，不由本闸子判。
    """
    hits = []
    for p in sorted((ROOT / "app").rglob("*.js")):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "document.cookie" in line:
                hits.append(f"{p.relative_to(ROOT)}:{n}")
    assert not hits, (
        "app/ 里出现了 document.cookie:\n  " + "\n  ".join(hits)
        + "\n\nFYL-SDD-01 DE-COMP-05.1：密钥必须存 sessionStorage，禁止 cookie。"
          "cookie 随每次同源请求自动发出。")
