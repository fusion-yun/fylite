# _spec — vendored SpData schema projection (L1 executable projection)

Verbatim copies of the SpData contract schemas that fylite's manifest layer targets
(`SP-REPORT-15` T-1.1, protocol-member discipline). Pattern follows the SpHarness
precedent (`spharness/schemas/README.md`): a local executable copy so fylite builds,
validates, and tests **offline with zero sp/fy imports**.

**Upstream wins.** The authoritative source is the SpData repo (`spdata/schemas/*.schema.json`,
contract truth per its `.context/PROJECT.md`). If this copy and upstream disagree, upstream
is correct — re-vendor; never edit these files in place, and never change field semantics
here first.

| File | Upstream | Vendored from |
| --- | --- | --- |
| `common.schema.json` | `spdata/schemas/common.schema.json` | spdata `f1a4d65` (2026-07) |
| `compute_artifact.schema.json` | `spdata/schemas/compute_artifact.schema.json` | spdata `f1a4d65` |
| `data_artifact.schema.json` | `spdata/schemas/data_artifact.schema.json` | spdata `f1a4d65` |
| `workflow_ir.schema.json` | `spdata/schemas/workflow_ir.schema.json` | spdata `f1a4d65` |

Known upstream caveat (recorded in SP-REPORT-15 §Pending): these schemas' `$id` points at
the spharness domain and their prose authority (`docs/ontology/artifact/*.md`) is not yet
re-homed (SP-ADR-101 / SPM-ADR-112 OI-2, both pending). When that governance lands, re-vendor
and update this table. Drift is checked by `python/tests/test_manifest_conformance.py` (byte-compare
against the spdata worktree when present; skipped otherwise).
