# 94048 first workflow adapter

The versioned definition is `cases/EQ-P01-94048/workflow.json`. Nodes use registered
stdlib tools; kernel calls consume the pinned native package through the document ABI.
Runtime requires `FYLITE_EQ_DATA` pointing at the manifested frozen dataset; it does
not import fylite_dev or historical application Python modules.

GET `/fylite/eq/api/workflow/info|cases|case|runs|run|artifact|analysis` provides definitions,
current cases, run snapshots, events, logs and named artifacts. Query with case_id,
run_id and artifact name as applicable. POST `save` creates a case or revision
(base_revision required for updates); `execute` takes case_id, revision, target,
request_id; `cancel` takes case_id and run_id. POSTs require the current page token
returned by the host info endpoint. IDs and paths are validated under the explicitly
selected personal root. This is a single Unix user localhost service, not multiuser auth.

The target defines its dependency closure. The targeted step is executed; matching
upstream artifacts may be reused after fingerprint and file SHA checks. Each run has
its own snapshot/status/events/stdout/stderr and artifacts; edits never modify earlier
snapshots. A cache hit is recorded as reused, not a new solve. Native input identity
records the canonical request SHA and table identities so it can be regenerated without
storing a duplicate hex-encoded table request.

No live native iteration telemetry, arbitrary script execution, diagnostic outer loop,
ONETWO rerun, model service or native checkpoint resume is implemented in this first
workflow. Scientific limits are displayed in the guide and actual reports.

Acceptance: `python tests/accept_workflow_94048.py --root <installed-eq> --data <dataset>
--personal <personal-test-root> --record <new-record-directory>`.


Current lifecycle: this native workflow service is the active application route; the
historical wasm UI and synchronous kernel bridge are frozen references, not runtime
requirements. The current host is direct, localhost and one Unix user; neither its
page token nor subprocess identity checks implement shared-user authentication.
Definitions, groups and node help are configuration-driven; new runs freeze the full
DAG definition. Only the adapted fixed-pressure route is validated. Conditional/loop
execution, arbitrary editor composition and generic domain viewers remain future work.
The analysis endpoint augments saved reports read-only with identified reference data
and declared device geometry; it does not rewrite historical numerical results.

Engineering backlog: readable modules, configurable API base and messages, JSDoc/checkJs,
lint and repository-contained browser regression fixtures. These gates are planned,
not claimed to be installed. Release checks must run without a fylite_dev checkout;
report PASS/FAIL/SKIP/NOT_RUN separately and block on missing mandatory inputs.


## Reviewed experimental-input pipeline (definition v4)

The route now reads frozen experimental windows or uses the bundled libsp
`mds_read_many` to acquire EAST94048 at5.760s on Shenma. Set
`FYLITE_MDSIP_SERVER` in the service environment to override the existing site
endpoint. This adapter is deliberately limited to the audited94048 mapping/time;
it does not enable arbitrary shots or online pressure. Acquisition errors fail the
node without falling back to cached values. Raw retained windows and their hashes
are saved in each personal run as acquired-waveforms.json.gz.

Stages: sources → quality → magnetic/pressure processing → review_data →
constraints → assemble → review_input → solve → report → review_results.
Pressure remains the archived ONETWO6.510s output (0.750s mismatch), with historical
edge-current priors and response tables. Review is informed permission to continue
the declared research/replay route, not proof of same-time experimental validity.

Review nodes enter waiting_review and stop the worker. POST review requires
case_id,run_id,identity,approved(boolean),note(nonempty); identity is returned by
the review artifact. It binds the run snapshot and all completed artifact hashes.
The backend rejects stale revisions, changed artifacts/data/tools and stale approval
identities. Approvals are per run, recorded with Unix actor/time/note; the single-user
host does not authenticate individual collaborators. Decline ends the run as
rejected; edit/save and create a new run. Resume skips own hash-checked completed
nodes. Cancellation also works while waiting. Test scripts mark their automated
approvals as test fixtures, never as user's scientific review.

Initialization PF/loop observations and weights, initial Ip and FSA measured Ip
now share the processed observation identity with the main fit. Historical shape,
response tables and artificial edge-current constraints remain explicit inherited
inputs. Existing old run snapshots/results are not migrated or rewritten.


### Magnetic processing task / shared automation API

The magnetic task separates raw datasets, immutable previews and adopted inputs. Save a
personal case first. Explicitly fetch once, or import the raw waveforms from an existing
run; select the dataset, change the half-window/drift setting, inspect channels and sample
tables, and adopt the exact preview with a note. Adoption creates a case revision without
starting the equilibrium solver. Future runs copy the adopted raw data and magnetic values;
no new MDSplus request is made. Changing magnetic parameters invalidates adoption; q/pressure
changes preserve it. Historical snapshots and public examples are never overwritten.

All routes use the existing `/fylite/eq/api/workflow/` prefix and POST token checks:

- `execute`: `target=sources, fresh_source=true` explicitly reads raw data as a recorded task.
- `processing-import`: case_id, base_revision, run_id → immutable personal dataset.
- `processing-objects` (GET): case_id → dataset and preview metadata.
- `processing-preview` (POST): case_id, base_revision, dataset_id, parameters → preview,
  identity, quality and magnetic values. GET takes case_id and preview_id.
- `processing-adopt`: case_id, base_revision, preview_id, identity, parameters, note → new
  case revision. Stale revisions, parameters, tool/data identities and empty notes fail closed.

These APIs are available to UI and automation callers; no LLM integration or automatic
scientific approval is implemented. Current scope remains the audited EAST 94048/5.760 s
binding, historical channel weights and fixed ONETWO pressure at 6.510 s. Preview is not
an equilibrium solve. Manual masks, per-channel weight edits and diagnostic outer loops
are not implemented. Validate with `tests/accept_magnetic_processing.py` using an installed
native payload, reference data, isolated personal root and a new record directory.


## W1 minimal object contract (candidate; not deployed)

`object_contracts.py` exposes read-only Dataset, ProcessingRevision, ConstraintSet,
InputBundle, Plan, Run and Artifact views via GET `objects?case_id=...&run_id=...`.
IDs are scoped by case/run/type; payload hashes use
`legacy-python-json-sort-keys-v1` (the unchanged Python `hobj` encoding). Original
file SHA256 remains separate. Completed artifacts and raw waveform references are
verified before producing a view. Objects are derived from immutable recorded inputs,
not migrated by rewriting old snapshots. Definitions with revisions 2/3/4 retain
their original identity; missing frozen definitions remain readable but cannot be
executed using today's definition. Synthetic compatibility fixtures do not establish
compatibility with every historical record.

POST `save` optionally accepts `source_case_id` and `source_revision` for Save As.
The adopted dataset and preview closure is copied byte-for-byte into a new personal
case, and published only after validation. Changed magnetic parameters preserve
copied raw data but invalidate adoption; pressure/q changes preserve magnetic adoption.
A stale tool identity remains readable but requires a new processing preview before
execution. No old run or scientific review receipt is transferred to authorize a new run.

`info.tool_definitions` describes the existing registered tools only; native
checkpoint, automatic retries, generic branches/loops and unsupported q modes remain
unavailable. Errors retain the existing error string with an additive structured
`error_detail` on worker failures. The current 11-node DAG and three review gates
are unchanged. Run `tests/test_workflow_objects.py` and, with the manifested dataset,
`tests/test_workflow_golden.py`. The latter checks actual preprocessing hashes against
eaeeb83, without invoking a solver or fetching online data.
