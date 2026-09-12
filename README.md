# fylite — a self-contained tokamak equilibrium, transport and turbulence kernel

![FYLITE](./docs/figures/fylite_logo.svg)

fylite packs a Grad-Shafranov solver (forward and inverse), a 1.5-D
core-transport step, neoclassical and gyro-Landau-fluid closures, and an
equilibrium-reconstruction row into **one re-entrant Rust kernel**, with a thin
Python layer for assembly and orchestration and a browser front end built from
the same kernel compiled to WebAssembly.

No Fortran, no MPI, no LAPACK, no system numerical libraries: the Rust crate has
one optional dependency (`rayon`), the Python package needs only `numpy`, and
the native library and the `.wasm` modules come out of the same C boundary.

It is a standalone package — zero code dependency on any other repository —
covering physics modelling, experiment analysis, control simulation and
discharge design, with one minimal runnable, interactive, comparable closed loop
per line. Four constraints size it:

- **single machine** — no cluster, no required server component; the browser
  pages work offline once loaded;
- **ms–s interactive response** — single solves, reconstructions and redraws;
  batch work (outer loops, grid scans) is explicitly batch: steppable and
  interruptible, never disguised as instant;
- **limited multithreading** — a few worker threads at most, no distributed
  runtime; the browser host is single-threaded;
- **cross-platform** — the same compute core runs as native Python and as
  browser WebAssembly.

**Status: alpha.** Capabilities and numerical conventions are still moving;
entry points and result formats may change without a migration path. Gaps are
listed rather than filled with functions that return zeros. The release version
lives in one place, [`VERSION`](VERSION); the kernel version and the ABI number
are two separate quantities, each reported by the build itself.

And it says so on every face. The three interfaces — the browser page, the `fy`
command line and the Python package — open with the same notice, declared once
in [`python/fylite/_notice.json`](python/fylite/_notice.json): the page shows it
as the band across its header, and `fy` and `import fylite` print it as a banner
on **stderr, and only when stderr is a terminal**, so `fy list --json | jq` and
`python x.py > out` carry only your data. `FY_NO_BANNER=1` drops the wordmark and
the version line and **keeps the notice** — it is a condition of use, not
decoration — and `FY_LANG` picks the language.

## Try it

<https://fusion-yun.github.io/fylite/> — the whole kernel compiled to
WebAssembly and running in the browser. Nothing to install, nothing uploaded.
The three scenario pages are under `pages/`
([model](https://fusion-yun.github.io/fylite/pages/model.html) ·
[pulse_design](https://fusion-yun.github.io/fylite/pages/pulse_design.html) ·
[analysis](https://fusion-yun.github.io/fylite/pages/analysis.html)), beside the
two tool pages: a data browser and a case report.

```bash
bash tools/build-site.sh --public dist/site   # local preview of the published site
python3 -m http.server -d dist/site 8000      # static: no /api/*
```

Publishing is a local step (`bash tools/publish-site.sh [site-repo]`), not a
hosted job: no `.wasm` is committed here, so a runner with only this checkout
cannot build the site at all. The script builds, runs the three gates that need
no browser, replaces the site repository's `fylite/` directory — and stops
there: no `add`, no `commit`, no `push`, because when to expose something is a
person's decision.

## Quick start

```bash
# tests run in a throwaway uv environment; this repository keeps no .venv
uv run --no-project --with pytest --with numpy --with matplotlib \
  python -m pytest python/tests

pip install -e python   # optional — numpy only
```

The Python project files (`pyproject.toml`, `pytest.ini`, `conftest.py`) live
under `python/`, and pytest looks for its ini upwards from the arguments — so
name `python/tests`, or run from inside that directory. `matplotlib` is not
optional for the test run: three plotting gates import it inside the test body,
with no `importorskip` in front, so without it they are red rather than skipped.

The kernel binaries are **not committed** (`.gitignore` refuses `*.so*` and
`*.wasm*`, and `python/tests/test_bundled_artifacts.py` holds that direction
shut) — see [The kernel](#the-kernel). A checkout without them still collects:
what needs a kernel is skipped **by name**, not failed.

Nothing above needs a machine description, a shot, or a network. Everything that
does need a device deck takes one explicitly — `$FYLITE_DEVICE_DIR`, or a path
handed to the entry point; see [the install chapter](docs/guide/install.md).

```python
from fylite import scenario as S

z = S.model.zerod()                     # 0-D discharge, prescribed profiles
t = S.model.transport(power=4.0)        # one 1.5-D transport step
f = S.analysis.profit(x, y, sigma_frac=0.05)   # profile fit, GCV smoothing
```

```python
from fylite.engine import cases, manifest_catalog
cases.catalogue()             # the scenario corpus
manifest_catalog()            # the capability catalogue, as JSON-LD
```

The Python package is a **library**: no `fylite` console script, no
`python -m fylite`. The one command line is the Rust executable `fy`
(`bash rust/build.sh --exe`), whose four command words are `app` / `data` /
`run` / `list` (a bare `fy` runs `app`); everything a Python verb would do is a
library call, listed side by side in [the CLI guide](docs/guide/cli.md). It is
built to `rust/fylite_runtime/target/release/fy` and nothing here puts it on
your `$PATH` — `fy` is a short name, so check `command -v fy` before assuming a
bare `fy` is this one.

The user guide is [`docs/guide/`](docs/guide/index.md) — start at
[quick start](docs/guide/quickstart.md), or go straight to the **worked
examples**, one runnable chapter per family:
[the case corpus](docs/examples/index.md) ·
[0-D](docs/examples/zerod/zerod.md) ·
[1.5-D](docs/examples/transport/transport.md) ·
[time evolution](docs/examples/evolve/evolve.md) ·
[discharge design](docs/examples/design/design.md) ·
[equilibrium reconstruction](docs/examples/reconstruction/reconstruction.md).
Every command and number in them was measured in this repository, and every
chapter says what its family **cannot** answer. The API map is
[`docs/reference/api.md`](docs/reference/api.md).

## The four scenario lines

Capabilities are organised by **purpose**; a tool is implemented once and listed
on every line it serves. The browser offers those tools it has a bar for; the
correspondence between the two hosts is declared in the register, not assumed.

| line | tools |
| :--- | :--- |
| `design` — discharge design | `discharge` · `breakdown` · `feasible` · `zerod` |
| `control` — control simulation | `vstab` · `coupled` |
| `model` — physics modelling | `discharge` · `reconstruction` · `zerod` · `transport` · `coupled` · `evolve` |
| `analysis` — experiment analysis | `reconstruction` · `zerod` |

Every result carries a `provenance` entry naming what it is a reduced tier of
and **where it is not equivalent**. Capabilities that are not built stay listed
as gaps (`○` in `fylite.scenario.TOOLS`), and a request outside a model's range
returns an error rather than a number that looks like an answer. What the
physics can and cannot do today is
[`docs/reference/fidelity.md`](docs/reference/fidelity.md) — the measured
limits — and [`TODO.md`](TODO.md) for what is not built yet.
[`PLAN.md`](PLAN.md) is narrower: the ordered plan, with its criteria, for landing
the kinetic-reconstruction scenario and its flow-graph page (`FYL-DESIGN-21`).

## How fylite is built

- **Public literature + public code.** Papers give the equations; vendored
  reference implementations give the operating conventions and the white-box
  referee — port fidelity is judged by same-deck runs against the original, not
  by reading.
- **One framework implementation per physics capability.** Alternative physics
  models coexist as parameter tiers, never as a second code path.
- **No plugin mechanism.** Declaration-driven entry tables and parameter tiers
  cover what plugins would; the payoff is a single body of code where a profile
  error can be chased down to one line.
- **No multi-source code integration.** The operating conventions that
  integrated suites accumulate over decades are measured back one at a time
  through benchmarks — reference data, frozen input decks and two-sided referees
  are first-class assets here, not an afterthought.
- **Rust kernel, thin Python/JS front ends.** The kernel carries its own
  numerical primitives; one C boundary produces the native library and the
  WebAssembly modules alike.
- **A complete reduced-model kernel — and no more.** Reduced models with public
  reference implementations are ported white-box; HPC-scale codes have their
  *products* consumed — saturation rules, surrogates — never their bodies
  absorbed.

Fidelity claims state only what was measured: every claim ships with its null
hypothesis and an open attribution list for the residual.

## What ships, and what does not

- **No third-party solver code or recorded output ships here in any form.** The
  free-boundary forward solve, the transport step and the closures are the
  kernel's own or white-box translations declared in its `NOTICE` (see
  [Attribution](#attribution)).
- **No experimental data is committed.** No shot files, no reconstructions of
  real discharges — machine-checked, not merely stated.
  [`docs/examples/`](docs/examples/) publishes the *specification* of each case
  (a plan document, no numbers) and resolves its data through
  `$FYLITE_DEVICE_DIR`; the synthetic equilibrium the test suite runs on is
  produced by the kernel itself, regenerable byte-for-byte.
- **Machine descriptions are inputs, with exactly one source.** A deck kept here
  as well as at its source would be a second source of truth, and the wrong one
  of two does not announce itself — it just lets a machine quietly run on
  another description. Decks are materialised on demand and found through
  `$FYLITE_DEVICE_DIR`. What a source does not carry is declared, with a reason,
  rather than defaulted.
- **The pages open on device presets** — a page that can be handed any machine
  still needs one to open with. The corpus is `facts/` at the repository root
  (`facts/device/`), and the descriptions travel **compiled into**
  `fylite_web.wasm`, read through `app/assets/factsdb.js`. One copy, one path.
  Which machine goes into which build is a redistribution decision made per
  entry in its own `rights.json` and answered by `tools/facts-publish.py`, with
  the provenance in `facts/device/catalogue.jsonld`.

## Where the physics lives

The kernel is one Rust crate. The Python layer does data assembly, device
plumbing, orchestration, plotting and provenance — it does not carry a second
implementation of a discretisation or a closed form, and that rule is gated.

| layer | modules |
| :--- | :--- |
| kernels, linear algebra, electromagnetics | `kernels.rs` `linalg.rs` `electromagnetics.rs` |
| equilibrium (forward / inverse), surfaces | `equilibrium.rs` `inverse.rs` `surfaces.rs` `geometry.rs` |
| transport, 0-D, evolution, sources, heating | `transport.rs` `zerod.rs` `evolution.rs` `sources.rs` `heating.rs` |
| neoclassical, turbulence, closures | `neoclassical.rs` `dke.rs` `gyrofluid.rs` `closure_tables.rs` `flr_tables.rs` |
| stability, control, pulse, breakdown | `stability.rs` `control.rs` `pulse.rs` `breakdown.rs` |
| fitting, diagnostics, profile mapping | `fitting.rs` `diagnostics.rs` `mapping.rs` |
| document layer, scenarios, data transport | `fyo.rs` `scenario.rs` `bundle.rs` `mdsip.rs` |
| the one C boundary | `c_api.rs` (`ABI_VERSION`, generated into both hosts) |

## Browser

[`app/`](app/) is a static site running the same kernel as WebAssembly: prose
pages (entrance, features, credits) generated in Chinese and English alike,
scenario pages (`design` / `model` / `analysis`) that switch language in place,
and two tool pages that compute nothing themselves: a data browser, and a **case
report** page that renders a plan and its record — the same presentation spec
`engine.casereport.render` derives, drawn by a port of the same rules
(`app/tests/validate-report.mjs` holds the two hosts to one spec). Open
`app/index.html` or serve the directory.

Each browser tool has a gate under [`app/tests/`](app/tests/README.md) that
sends the page's own exported session file through the native implementation and
compares.

## Talking to other tools

fylite describes itself rather than being described: the JSON-LD manifests in
`python/fylite/_manifest/` are authored files; the engine only loads, validates
and seals them.

| entry point | what it is for |
| :--- | :--- |
| `engine.manifest_catalog()` | the machine-readable capability catalogue (JSON-LD) |
| `engine.manifest.write_manifests()` / `seal_manifests()` | check / re-seal / export the authored manifests |
| `engine.serve.serve_stdio()` | catalogue + entry invocation as JSON-RPC 2.0 over stdio (experimental) |
| `engine.serve.mcp_stdio()` | an MCP stdio server: curated tools plus tools reflected from the manifests |

`python/fylite/engine/` stays stdlib-pure at import time, so a host can load the
protocol face without paying for numpy or the kernel.

## Reading and writing data

The **data layer** (`rust/fylite_runtime/`, source open, built into
`libfylite_runtime.so` and the `fy data` command) converts between data sources
and fyo documents, merges several sources, and assembles them from a JSON-LD
description. Files are recognised by **content**, never by name.

| source | read | write | layouts |
| :--- | :-: | :-: | :--- |
| MDSplus (mdsip, read-only by construction; binding tables; time windows sliced server-side) | ✓ | — | fyo |
| device deck YAML (`machine.yaml`, providers, bindings) | ✓ | — | fyo |
| EFIT a-file | ✓ | — | fyo |
| EFIT g-file | ✓ | ✓ | fyo |
| JSON / JSON-LD | ✓ | ✓ | fyo · IMAS DD |
| HDF5 | ✓ | ✓ | fyo · IMAS (imas-core HDF5 backend: `master.h5` + `<ids>.h5`) |
| netCDF | ✓ | ✓ | fyo · IMAS (imas-python netCDF backend) |

```bash
fy data info  g063982.04800                          # what is this file?
fy data convert g063982.04800 shot.nc --layout imas  # imas-python opens it
fy data merge machine.h5 shot.nc -o all.jsonld       # later sources win
fy data assemble device.jsonld -o device.h5 --shot 70754
fy data fetch --device <name> --ids magnetics \
              --shot 138569 --time 4:5 --host <mdsip-host> -o mag.json
```

```python
from fylite.io import fydoc
b = fydoc.read("g063982.04800")                 # a bundle of fyo documents
psi = b.array("equilibrium/time_slice/0/profiles_2d/0/psi")   # [R, Z]
b.write("entry_dir", layout="imas")             # IMAS HDF5 data entry
m, fails = fydoc.fetch("machine.yaml", "magnetics",            # the device deck
                       shot=138569, time=(4.0, 5.0), host="<mdsip-host>")
m.array("magnetics/b_field_pol_probe/0/field/data")   # the 4–5 s slice
```

The C libraries this needs (`libhdf5`, `libnetcdf`) are linked dynamically by
default; `rust/build.sh --static` compiles them in for machines without them.

## Running a case

A case is **one structure in, one structure out**: a `fyo:ScenarioSpecification`
(the documents under `docs/examples/`, an `spo:ComputationPlan`) goes in, an
`spo:ComputationRecord` with its produced datasets comes out. The kernel
completes the case from its structure — settings by name, bound inputs by fyo
path — and the data layer owns both ends: `fy run` reads and composes the plan
documents, resolves bound inputs through the format readers, loads the kernel at
run time and writes the record and the datasets as fyo documents.

```sh
fy list kernel                                     # what the kernel completes, and what it declares
fy run docs/examples/evolve/evolve-default.jsonld nsteps=12 --dry-run
fy run docs/examples/evolve/evolve-default.jsonld nsteps=12 --record records/evolve
#  -> records/evolve/{record.jsonld, plan.jsonld, core_profiles.fyo.jsonld, summary.fyo.jsonld, ...}
```

The same command takes a **line and a scenario** instead of files, and then it
resolves the device and the shot itself:

```sh
fy run analysis --device <name> shot=137985 time=4.0 --only-magnetic -o rec/
fy list scenarios --line analysis                  # what there is, and whether it runs today
```

Several plan documents compose (later ones override earlier ones, then the
`key=value` parameters and `--bind`). A case the kernel cannot complete is
**refused with the missing thing named** — a capability not yet sunk, an
equilibrium ladder not bound — and the refusal is recorded too
(`run_state: rejected`). The kernel is found by `--kernel`, `$FYLITE_KERNEL_LIB`
or `python/fylite/_lib/`.

A plan can state its own delivery: an output port binding whose
`bound_concretization.format_iri` is `fyo:ImasHdf5Format` makes `run` write the
produced datasets as one IMAS data entry (`imas/master.h5` + `imas/<ids>.h5`,
the imas-core HDF5 backend layout, gzip, `_SHAPE` / `AOS_SHAPE` tables), which
`--format imas-hdf5` also selects. `docs/examples/evolve/` carries the
acceptance case for exactly that: fyo / JSON-LD in, IMAS DD HDF5 out, read back
here with h5py and with the data layer's own reader. A from-source HDF5 needs
zlib for it (`--static` carries `hdf5/zlib`; the IMAS layout deflates every
chunked dataset).

The same run is **one function** on the data layer: `fylite_runtime_case_json`
takes the plan as JSON-LD text (one document, or an array composed in order) and
returns the record as JSON-LD text with the datasets inline on their output
ports. `fy run plan.jsonld --json` and, in Python,
`fylite.io.fydoc.case_json(plan)` are faces on it. The kernel behind both is its
own single door, `fylite_rs_fyo`: settings by name and inputs by fyo path in,
fields by fyo path out, no handle and no state between calls.

## Checks

Two registers answer two different questions.

**Was it measured against something?** [`docs/benchmark/`](docs/benchmark/) is
the V&V register: one `fyo:ComparisonRecord` per comparison, every reference
dataset with its admissibility class and sha256, every gate with the checkout it
runs in, and the outcome of running those gates on the day of publication. It is
read through the same verb as the scenario corpus:

```python
from fylite.engine import cases, casereport
from fylite.engine import benchmark as bm

cases.catalogue()                 # the scenario corpus (docs/examples/)
bm.records()                      # the V&V register: kind, verdict, re-run, admissibility
bm.load("V-01")                   # one record, JSON-LD
casereport.render(cases.run("evolve-default"))   # a case -> report.md + figures/*.svg + presentation.jsonld
casereport.render("records/<run>")               # render a record `fy run` wrote
```

**Is what it produced self-consistent?** A run that converged quickly can still
carry a negative temperature, and a profile that agrees with another code to 1 %
can still violate Grad–Shafranov — two errors cancelling.
[`docs/benchmark/physics/`](docs/benchmark/physics/) is the register that asks
it: each preset case is judged against **physical law** (finiteness, positivity,
the Grad–Shafranov equation), against the **documents' own definitions** (ψ
endpoints, V′ > 0, the τ_E, β_N and Greenwald formulae) and against the **window
the case declares** (bounds, steady-state). Verdicts use the four-state
acceptance vocabulary, and a quantity that is absent is `unevaluated` **by
name** — never silently passed.

```bash
python tools/benchmark-run.py            # run the batch, print the statistics
python tools/benchmark-run.py --write    # write docs/benchmark/physics/ + BENCHMARK.md
```

```python
from fylite.engine import suite
suite.entries()                          # the preset cases and their criteria
suite.run_entry(suite.entry("equilibrium-gfile"))
```

The summary table is [`BENCHMARK.md`](BENCHMARK.md); the check register itself —
what each check reads, its formula, its assumptions — is
[`docs/reference/benchmark.md`](docs/reference/benchmark.md).

The IMAS layouts are checked against the real readers, not against a description
of them: `rust/fylite_runtime/verify/imas_roundtrip.py` writes with
imas-python, reads with this library, writes with this library, and reads back
with imas-python and imas-core, leaf by leaf.

There is no CI workflow here; the gates run from a checkout — `cargo test`
(Rust), `pytest` (the Python tier), `node app/tests/validate-*.mjs` (the site's
static gates) and `tools/benchmark-run.py` (the physics batch). Anything needing
the kernel, a browser or data that is not distributed here is **skipped by
name** rather than failed: a missing input and a missing implementation are
different things. That policy and its boundary are stated in
`python/conftest.py`.

## Repository map

| path | contents |
| :--- | :--- |
| `python/fylite/` | assembly, device plumbing, IO, scenarios, the protocol engine (a library, not a CLI) |
| `rust/fylite_runtime/` | the data layer (source open): data sources ↔ fyo, IMAS netCDF/HDF5, mdsip, the `fy` executable |
| `python/tests/` | the Python tier — assembly, IO, the protocol faces, the registries, the ABI marshalling (`python/pytest.ini`); the physics/numerics tier is not here, it lives with the code it judges |
| `app/` | the static browser site and its gates |
| `app/cases/` | worked **session** documents for the pages' import button — a different thing from the scenario corpus in `docs/examples/`; each one is filtered on the device it declares against the machines the build carries |
| `facts/` | the reference corpus, one directory per entry (`facts/device/`), with its redistribution rights |
| `models/` | neural surrogates as data — one `.npz` each, none compiled in |
| `docs/examples/` | the runnable specifications, one directory per example, read through `fylite.engine.cases` |
| `docs/benchmark/` | the V&V register, plus the physics-check register under `physics/` |
| `docs/` | the MyST book: user guide, reference, examples |
| `tools/` | deck converters, page generators, build and publish scripts |

## The kernel

The Rust kernel source is not published. What is committed here is the whole
application layer — the Python package, the browser site, the data layer, the
examples and the registers — plus the generated files the two halves must agree
on (`_abi.py`, `_fyo_interface.py`, `_deck_names.py`, `_cgs.py`,
`app/assets/{version,fyo-interface,deck-names}.js`, `abi.json`).

Binaries do not travel with the repository. `python/fylite/_lib/libfylite_kernel.so`
and the kernel `app/assets/*.wasm` are produced by the kernel build and
installed into a checkout; `libfylite_runtime.so` and `app/assets/fylite_web.wasm`
come from this repository's own `bash rust/build.sh`. Distributions pack them:
`tools/build-wheel.sh`, `tools/build-site.sh`, `tools/build-app-exe.sh`.

So a complete checkout of this repository has every line of the application layer
and cannot reproduce the kernel it calls. That is a property of the split, stated
here so nobody concludes they are missing a step. What *can* be checked from here
is that the library on disk speaks the ABI this package expects and that no binary
has crept back into git (`python/tests/test_bundled_artifacts.py`) — and what the
kernel answers, which is what the registers above are for.

Neither build hard-codes a path into a committed file, and neither guesses one:

```bash
FYLITE_PUBLIC=/path/to/fylite bash rust/build.sh --wasm-check   # kernel side: build and install the artifacts here
FYLITE_KERNEL=/path/to/kernel bash tools/build-app-exe.sh linux # here: the single-file desktop viewer
```

**Distribution.** The Python package ships a **pre-compiled** kernel rather than
building one at install time, so the wheel is platform-tagged and the published
surface is **Linux x86-64 only** — other platforms are refused at install time
instead of failing at the first kernel call. Build one with
`bash tools/build-wheel.sh`, which derives the tag from the binary rather than
asserting it. The browser build carries the same kernel as WebAssembly and has no
platform limit at all, and `bash tools/build-app-exe.sh` packs that browser build
into a **single executable** — Linux and Windows — that serves its own embedded
copy on the loopback address and opens your browser, so an offline machine with no
Python still gets the whole demo from one file.

## Licence and attribution

**Apache-2.0** (see [`LICENSE`](LICENSE)). Parts of the physics are white-box
translations of published open-source reference implementations rather than
independent reimplementations; `NOTICE` names the files, the upstream revisions
and the ways the translations deliberately differ.

`NOTICE` is not a file in this repository: it describes the kernel source and
lives with it. The obligation Apache-2.0 §4(d) creates attaches to the
**distribution**, and that is where it is discharged — `tools/build-wheel.sh`
installs `NOTICE` into the wheel and `tools/build-site.sh` copies it, with
`LICENSE`, to the root of the published site (the site ships the wasm that
`NOTICE` describes, so the site is a distribution). **Both refuse to build
without it**: an unattributed distribution is not a smaller product, it is a
licence breach, and it is the kind that never announces itself.

[`docs/ACKNOWLEDGEMENTS.md`](docs/ACKNOWLEDGEMENTS.md) is the full
human-readable list of every upstream code, published formula, reference dataset
and cross-code oracle this project stands on — and how the code was built
(AI-assisted, gold-fixture verified).

## Reporting a problem

Open an issue. The kernel source is not published, so reproducing a report
depends on knowing **which binary** you ran: the issue template asks for the demo
page's footer line (`kernel … · interface … · app …`) and the kernel `sha256`
shown on its credits page. Those two are what make a report actionable. Patches
cannot be merged here — the source they would touch is not in this repository —
so a precise issue is the contribution.
