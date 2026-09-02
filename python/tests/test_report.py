"""The report face: one recorded run -> one MyST document, ONE template.

★What is being gated is the template's discipline, not prose taste:

* the five sections, in the declared order, on every report;
* tables captioned ABOVE (the `{table}` container argument), figures
  captioned BELOW, anchors ``tbl-*`` / ``fig-*``;
* NO bulk arrays — the report is a projection of the record, and an inlined
  array would be a second, ungated copy of ``arrays.npz``;
* 验收 quoted verbatim from ``acceptance.json``, never re-judged;
* honest degradation — a missing renderer or a missing run says so by name.

★Every test drives the REAL tool face (``serve.call_mcp_tool``) into a
temporary run root, same as ``test_replay.py`` and for the same reason: a
report renderer tested against a hand-made manifest would prove the
hand-made manifest renders.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fylite.engine import report, serve

ROOT = Path(__file__).resolve().parents[2]

try:
    import matplotlib  # noqa: F401
    HAVE_MPL = True
except ImportError:
    HAVE_MPL = False


@pytest.fixture()
def run_root(tmp_path, monkeypatch):
    monkeypatch.setenv("FYLITE_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("FYLITE_SESSION", tmp_path.name)
    return tmp_path


@pytest.fixture()
def a_run(run_root):
    out = serve.call_mcp_tool("fylite_zerod", {"n_rho": 9})
    assert not out.get("isError"), out
    result = json.loads(out["content"][0]["text"])
    return run_root / run_root.name / result["run"]


def test_the_sections_come_in_the_declared_order(a_run):
    """The template IS the order — a reader of one report has read them all."""
    text = report.render(a_run)
    heads = re.findall(r"^## (.+)$", text, re.M)
    assert tuple(heads) == report.SECTIONS, heads
    #: and the frontmatter names the run, so a saved file identifies itself
    assert text.startswith("---\n")
    assert a_run.name in text.splitlines()[1]


def test_tables_are_captioned_above_and_anchored(a_run):
    """★The academic convention, as syntax: a `{table}` container's argument
    is its caption (rendered above); every table carries a `tbl-` label."""
    text = report.render(a_run)
    tables = re.findall(r":::\{table\}(.*)\n:label: (\S+)", text)
    assert len(tables) >= 3, "args, results and acceptance at least"
    for caption, label in tables:
        assert caption.strip(), f"{label} has no caption above the table"
        assert label.startswith("tbl-"), label


def test_no_bulk_array_ever_reaches_the_report(a_run):
    """★★The rule that makes the template safe to generate from any run.

    An interior element of the largest array must not appear — min/max/mean
    are the summary's own numbers, an interior value could only come from
    serialising the array itself.
    """
    import numpy as np
    data = np.load(a_run / "arrays.npz")
    text = report.render(a_run)
    #: ★the probe must not itself BE a summary statistic — `ne` is a
    #: prescribed profile whose interior elements sit exactly at its max,
    #: which the summary table legitimately prints.  Pick an interior value
    #: whose 6-sig rendering differs from every statistic of its array.
    y = data["v_loop"]
    stats = {f"{float(v):.6g}" for v in (y.min(), y.max(), y.mean())}
    probe = next(float(v) for v in y[len(y) // 3:]
                 if f"{float(v):.6g}" not in stats)
    assert repr(probe) not in text
    assert f"{probe:.6g}" not in text
    #: and the whole projection stays a document, not a data file
    assert len(text.encode()) < 32_000, "a report this size is carrying data"
    #: the 正本 is still named, by hash, so nothing was lost — only projected
    man = json.loads((a_run / "manifest.json").read_text())
    npz_sha = next(a["sha256"] for a in man["artifacts"]
                   if a["name"] == "arrays.npz")
    assert npz_sha in text


def test_acceptance_is_quoted_not_rejudged(a_run):
    """★Every state and every `tbd` reason comes from acceptance.json
    verbatim — the report may not soften「未评估」into anything else."""
    acc = json.loads((a_run / "acceptance.json").read_text())
    text = report.render(a_run)
    assert f"`{acc['state']}`" in text
    for c in acc["criteria"]:
        assert c["name"] in text
        if c.get("tbd"):
            assert c["tbd"] in text, (
                "the tbd reason is the honest part of an unevaluated "
                "criterion, and the report dropped it")


def test_figures_degrade_honestly(a_run):
    """★Absent renderer / refused figures: the report says so, in the text,
    rather than thinning silently."""
    text = report.render(a_run, figures=False)
    assert "--no-figures" in text
    if not HAVE_MPL:
        text = report.render(a_run)
        assert "matplotlib 不可用" in text
        assert ":::{figure}" not in text, (
            "a figure directive with no renderer points at a file that "
            "was never written")


@pytest.mark.skipif(not HAVE_MPL, reason="matplotlib not installed")
def test_every_figure_directive_points_at_a_file_that_exists(a_run, tmp_path):
    out = tmp_path / "out"
    dest = report.write(a_run, out=out / "report.md")
    text = dest.read_text()
    figs = re.findall(r":::\{figure\} (\S+)", text)
    assert figs, "matplotlib is present and 1-D traces exist — expect figures"
    for rel in figs:
        assert (dest.parent / rel).is_file(), rel
    #: captions BELOW: the container body (after the option lines and a
    #: blank line) carries 图 N
    assert re.search(r":::\{figure\}[\s\S]*?\n\n图 \d：", text)


def test_a_missing_run_is_refused_by_name(run_root):
    with pytest.raises(SystemExit, match="r-never-happened"):
        report.render("r-never-happened")


def test_a_directory_without_a_manifest_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit, match="manifest"):
        report.render(tmp_path / "empty")


def test_the_template_doc_states_the_same_order():
    """★docs/reference/report-template.md is the normative prose of
    :data:`report.SECTIONS`; this holds the two together, the same way the
    CLI spec and its handlers are held together."""
    doc = (ROOT / "docs/reference/report-template.md").read_text()
    listed = re.findall(r"^\d\. \*\*(\S+)\*\*", doc, re.M)
    assert tuple(listed) == report.SECTIONS, (
        f"the template doc lists {listed}, report.SECTIONS says "
        f"{report.SECTIONS} — change both or neither")
    #: and the docs book actually carries the page.  ★It is the REFERENCE
    #: book's own toc since `docs/` was split into four books (2026-09-01);
    #: a page in no toc is a page nobody reaches.
    assert "report-template.md" in (
        ROOT / "docs/reference/myst.yml").read_text()


def test_the_cli_command_is_declared_and_reachable():
    """Same shape as test_replay's gate: declared flags == read flags."""
    spec = json.loads((ROOT / "python/fylite/_cli.json").read_text())
    cmd = next(c for c in spec["commands"] if c["name"] == "report")
    mod, func = cmd["handler"].split(":")
    import importlib
    assert callable(getattr(importlib.import_module(mod), func))
    flags = {a.get("dest") or a["flags"][-1].lstrip("-").replace("-", "_")
             for a in cmd["args"]}
    body = re.search(r"def _cli_report\(.*?\n(?=\ndef )",
                     (ROOT / "python/fylite/engine/cli.py").read_text(),
                     re.S).group(0)
    for used in re.findall(r"args\.(\w+)", body):
        assert used in flags, (
            f"_cli_report reads args.{used}, which `fylite report` does "
            "not declare")
