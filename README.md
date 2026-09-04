# fylite — a self-contained tokamak equilibrium, transport and turbulence kernel

![FYLITE](./docs/figures/fylite_logo.svg)

fylite packs a Grad-Shafranov solver (forward and inverse), a 1.5-D
core-transport step, neoclassical and gyro-Landau-fluid closures, and an
equilibrium-reconstruction row into **one re-entrant Rust kernel**, with a
thin Python layer for assembly and orchestration and a browser front end
built from the same kernel compiled to WebAssembly.

No Fortran, no MPI, no LAPACK, no system numerical libraries: the Rust crate
has one optional dependency (`rayon`), the Python package needs only `numpy`,
and the native library and the `.wasm` modules come out of the same
`c_api.rs`.

It is a standalone package — zero code dependency on any other repository —
covering five task classes with a lightweight feature set: physics modelling
and experiment analysis first, then control simulation, discharge design and
device parameter optimisation; one minimal runnable, interactive, comparable
closed loop per class.

Four constraints position the package:

- **single machine** — no cluster, no required server component; the browser
  pages work offline once loaded;
- **ms–s interactive response** — single solves, reconstructions and redraws;
  batch work (outer loops, grid scans) is explicitly batch: steppable and
  interruptible, never disguised as instant;
- **limited multithreading** — a few worker threads at most, no distributed
  runtime; the browser host is single-threaded;
- **cross-platform** — the same compute core runs as native Python and as
  browser WebAssembly.

## Try it · 在线演示

<https://fusion-yun.github.io/fylite/> — the whole kernel compiled to
WebAssembly and running in the browser. Nothing to install, nothing uploaded.

## Reporting a problem · 报障

Open an issue. The kernel source is not published, so reproducing a report
depends on knowing **which binary** you ran: the issue template asks for the
demo page's footer line (`kernel … · interface … · app …`) and the kernel
`sha256` shown on its credits page. Those two are what make a report
actionable. Patches cannot be merged here — the source they would touch is in
the private kernel repository — so a precise issue is the contribution.

## How fylite is built

- **Public literature + public code.** Papers give the equations; vendored
  reference implementations give the operating conventions and the white-box
  referee — port fidelity is judged by same-deck runs against the original,
  not by reading.
- **One framework implementation per physics capability.** Alternative
  physics models coexist as parameter tiers, never as a second code path.
- **No plugin mechanism.** Declaration-driven entry tables and parameter
  tiers cover what plugins would; the payoff is a single body of code where a
  profile error can be chased down to one line.
- **No multi-source code integration.** The operating conventions that
  integrated suites accumulate over decades are measured back one at a time
  through benchmarks — reference data, frozen input decks and two-sided
  referees are first-class assets here, not an afterthought.
- **Rust kernel, thin Python/JS front ends.** The kernel carries its own
  numerical primitives; one C boundary produces the native library and the
  WebAssembly modules alike.
- **A complete reduced-model kernel — and no more.** Reduced models with
  public reference implementations are ported white-box; HPC-scale codes have
  their *products* consumed — saturation rules, surrogates — never their
  bodies absorbed.

Fidelity claims state only what was measured: every claim ships with its null
hypothesis and an open attribution list for the residual.

**Status: alpha.** Capabilities and numerical conventions are still moving;
entry points and result formats may change without a migration path. Gaps are
listed rather than filled with functions that return zeros. The release
version lives in one place, [`VERSION`](VERSION); the kernel version and the
ABI number are two separate quantities, each reported by the build itself.

**Distribution, during alpha.** The Python package ships a **pre-compiled**
kernel rather than building one at install time, so the wheel is
platform-tagged and the published surface is **Linux x86-64 only** — other
platforms are refused at install time instead of failing at the first kernel
call. Build one with `bash tools/build-wheel.sh`, which derives the tag from
the binary rather than asserting it. The browser build carries the same kernel
as WebAssembly and has no platform limit at all, and `bash tools/build-app-exe.sh`
packs that browser build into a **single executable** — Linux and Windows —
that serves its own embedded copy on the loopback address and opens your
browser, so an offline machine with no Python still gets the whole demo from
one file. The Rust sources are not published; what ships is the compiled
artifact, the Python and JS layers, and the evidence that judges them.

**Licence: Apache-2.0** (see [`LICENSE`](LICENSE)). ★`NOTICE` — the
per-component provenance Apache-2.0 §4(d) requires — is not a file in this
repository: it describes the kernel source and lives with it, and it is copied
into the wheel at build time by `tools/build-wheel.sh`. The obligation attaches
to the distribution, and that is where it is discharged.

---

## Quick start

```bash
# Python 一律走 uv 的临时环境；本仓不建 .venv（`--no-project` 是必须的）
# ★★工程文件都在 `python/` 下（`pyproject.toml` / `pytest.ini` / `conftest.py`），
#   而 pytest 是从参数向上找 ini 的 —— 所以要么点名 `python/tests`，要么先 cd 进去。
#   在**仓根裸跑 `pytest`** 找不到任何 ini，那不是本档。
uv run --no-project --with pytest --with numpy python -m pytest python/tests

pip install -e python   # optional — numpy only；工程在 `python/`，不在仓根
```

The kernel binaries (`python/fylite/_lib/libfylite.so`, `app/assets/*.wasm`)
are committed pre-built, so none of the above needs a Rust toolchain.
Rebuilding them is a different repository's job — see below.

Nothing above needs a machine description, a shot, or a network. Everything
that does need a device deck takes one explicitly — `$FYLITE_DEVICE_DIR`, or
a path handed to the entry point. ★`machine_desc/` was **abolished** on
2026-09-02: a deck has one source of truth, the A-Box in the private data
repository, and you materialise it wherever you like with
`tools/abox-to-machine-desc.py` — see
[the install chapter](docs/guide/install.md).

```python
from fylite import scenario as S

z = S.model.zerod()                     # 0-D discharge, prescribed profiles
t = S.model.transport(power=4.0)        # one 1.5-D transport step
f = S.analysis.profit(x, y, sigma_frac=0.05)   # profile fit, GCV smoothing
```

★★2026-09-04 (user ruling): **this package has no command line.** `pip install
fylite` gives you a LIBRARY — no `fylite` console script, no `python -m fylite`.
The one command line there is is the Rust executable `fy` (`bash rust/build.sh
--exe`), which carries `app` / `data` / `case`; everything the Python verbs used
to do is a library call, listed side by side in
[the CLI guide](docs/guide/cli.md).

```python
from fylite.engine import cases, manifest_catalog
cases.catalogue()             # the scenario corpus: 25 plan documents
manifest_catalog()            # the capability catalogue, as JSON-LD
```

The user guide is [`docs/guide/`](docs/guide/index.md) — start at
[quick start](docs/guide/quickstart.md), or go straight to the **worked
examples**, one runnable chapter per family: [the case corpus](docs/examples/index.md)
· [0-D](docs/examples/zerod.md) · [1.5-D](docs/examples/transport.md)
· [time evolution](docs/examples/evolve.md) ·
[discharge design](docs/examples/design.md) ·
[equilibrium reconstruction](docs/examples/reconstruction.md). Every command
and number in them was measured in this repository, and every chapter says what
its family **cannot** answer. The API map is
[`docs/reference/api.md`](docs/reference/api.md).

## The four scenario lines

Capabilities are organised by **purpose**; the same nine tool ids are used in
the browser, in a notebook and at the CLI. A tool is implemented once and
listed on every line it serves.

| line | tools |
| :--- | :--- |
| `design` — discharge design | `discharge` · `breakdown` · `feasible` · `zerod` |
| `control` — control simulation | `vstab` · `coupled` |
| `model` — physics modelling | `zerod` · `transport` · `coupled` · `tglf` · `discharge` · `reconstruction` |
| `analysis` — experiment analysis | `reconstruction` · `zerod` |

Every result carries a `provenance` entry naming what it is a reduced tier of
and **where it is not equivalent**. Capabilities that are not built stay
listed as gaps (`○` in `fylite.scenario.TOOLS`), and a request outside a
model's range returns an error rather than a number that looks like an
answer. What the physics can and cannot do today is [`FEATURE.md`](FEATURE.md).

## What ships, and what does not

- **No third-party solver code or recorded output ships here in any form.**
  The free-boundary forward solve, the transport step and the closures are
  the kernel's own or white-box translations declared in the kernel's `NOTICE`
  (see Attribution below — it ships inside the wheel, not as a file here).
- **No experimental data is committed.** No shot files, no reconstructions of
  real discharges — machine-checked, not merely stated. [`cases/`](cases/)
  publishes the *specification* of each case (a plan document, no numbers) and
  resolves its data through `$FYLITE_DEVICE_DIR`; the synthetic equilibrium the
  test suite runs on is produced by the kernel itself, regenerable
  byte-for-byte.
- **Machine descriptions are inputs — and have exactly one source.**
  `machine_desc/` was abolished (2026-09-02): a deck kept here as well as in the
  A-Box would be a second source of truth, and the wrong one of two does not
  announce itself — it just lets a machine quietly run on another description.
  Decks are materialised on demand from the A-Box in the private data repository
  and found through `$FYLITE_DEVICE_DIR`. What a source does not carry is
  declared, with a reason, rather than defaulted.
- **`app/` ships four device presets**, because a page that can be handed any
  machine still needs one to open with — a redistribution decision recorded
  with its provenance in `app/facts/device/catalogue.jsonld`.

## Where the physics lives

One host: `rust/fylite/src/`. The Python layer does data assembly, device
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

[`app/`](app/) is a static site running the same kernel as WebAssembly:
prose pages (entrance, features, credits) generated in Chinese and English
alike, scenario pages (`design` / `model` / `analysis`) that switch language
in place, and two tool pages that compute nothing themselves: a data browser,
and a **case report** page that renders a plan and its record — the same
presentation spec `engine.casereport.render` derives, drawn by a port of the same
rules (`app/tests/validate-report.mjs` holds the two hosts to one spec). Open
`app/index.html` or serve the directory; the published copy is
<https://fusion-yun.github.io/fylite/>.

Each browser tool has a gate under [`app/tests/`](app/tests/README.md) that
sends the page's own exported session file through the native implementation
and compares.

## Talking to other tools

fylite describes itself rather than being described: the JSON-LD manifests in
`python/fylite/_manifest/` are authored files; the engine only loads,
validates and seals them.

| entry point | what it is for |
| :--- | :--- |
| `engine.manifest_catalog()` | the machine-readable capability catalogue (JSON-LD) |
| `engine.manifest.write_manifests()` / `seal_manifests()` | check / re-seal / export the authored manifests |
| `engine.serve.serve_stdio()` | catalogue + entry invocation as JSON-RPC 2.0 over stdio (experimental) |
| `engine.serve.mcp_stdio()` | an MCP stdio server: curated tools plus tools reflected from the manifests |

`python/fylite/engine/` stays stdlib-pure at import time, so a host can load
the protocol face without paying for numpy or the kernel.

## Reading and writing data

The **data layer** (`rust/fylite_runtime/`, source open, built into
`libfylite_runtime.so` and the `fy data` command) converts between data
sources and fyo documents, merges several sources, and assembles them from a
JSON-LD description. Files are recognised by **content**, never by name.

| source | read | write | layouts |
| :--- | :-: | :-: | :--- |
| MDSplus (mdsip, read-only by construction; A-Box binding tables; time windows sliced server-side) | ✓ | — | fyo |
| fydata A-Box YAML (`machine.yaml`, providers, bindings) | ✓ | — | fyo |
| EFIT a-file | ✓ | — | fyo |
| EFIT g-file | ✓ | ✓ | fyo |
| JSON / JSON-LD | ✓ | ✓ | fyo · IMAS DD |
| HDF5 | ✓ | ✓ | fyo · IMAS (imas-core HDF5 backend: `master.h5` + `<ids>.h5`) |
| netCDF | ✓ | ✓ | fyo · IMAS (imas-python netCDF backend) |

## Running a case

A case is **one structure in, one structure out**: a `fyo:ScenarioSpecification`
(the documents under `cases/`, an `spo:ComputationPlan`) goes in, an
`spo:ComputationRecord` with its produced datasets comes out. The kernel
completes the case from its structure — settings by name, bound inputs by fyo
path — and the data layer owns both ends: the `fy case` command reads and
composes the plan documents, resolves bound inputs through the format readers,
loads `libfylite_kernel.so` at run time and writes the record and the datasets
as fyo documents.

```sh
fy case describe                                   # what the kernel completes, and what it declares
fy case plan cases/evolve-default.jsonld --set nsteps=12
fy case run  cases/evolve-default.jsonld --set nsteps=12 --record records/evolve
#  -> records/evolve/{record.jsonld, plan.jsonld, core_profiles.fyo.jsonld, summary.fyo.jsonld, ...}
```

Several plan documents compose (later ones override earlier ones, then `--set`
and `--bind`). A case the kernel cannot complete is **refused with the missing
thing named** — a capability not yet sunk, an equilibrium ladder not bound —
and the refusal is recorded too (`run_state: rejected`). Build it with
`./rust/build.sh --exe`; the kernel is found by `--kernel`, `$FYLITE_KERNEL_LIB`
or `python/fylite/_lib/`.

A plan can state its own delivery: an output port binding whose
`bound_concretization.format_iri` is `fyo:ImasHdf5Format` makes `run` write the
produced datasets as one IMAS data entry (`imas/master.h5` + `imas/<ids>.h5`,
the imas-core HDF5 backend layout, gzip, `_SHAPE` / `AOS_SHAPE` tables), which
`--format imas-hdf5` also selects. `cases/evolve-iter-15ma.jsonld` is the
acceptance case for exactly that: fyo / JSON-LD in, IMAS DD HDF5 out, read
back here with h5py and with the data layer's own reader (the layout is the one
`verify/imas_roundtrip.py` checks against imas-python). A from-source HDF5 needs zlib for it
(`--static` carries `hdf5/zlib`; the IMAS layout deflates every chunked dataset).

The same run is **one function** on the data layer: `fylite_runtime_case_json`
takes the plan as JSON-LD text (one document, or an array composed in order)
and returns the record as JSON-LD text with the datasets inline on their
output ports. `fy case json plan.jsonld` and, in Python,
`fylite.io.fydoc.case_json(plan)` are faces on it. The kernel behind both is
its own single door, `fylite_rs_fyo`: settings by name and inputs by fyo path
in, fields by fyo path out, no handle and no state between calls.

## Physics checks

Beside the V&V register (what fylite was measured *against*) there is a second
question: is what it produced **self-consistent**? A run that converged quickly
can still carry a negative temperature, and a profile that agrees with another
code to 1 % can still violate Grad–Shafranov — two errors cancelling.

`benchmark/physics/` is the register that asks it. Each preset case is judged
against **physical law** (finiteness, positivity, the Grad–Shafranov equation),
against the **documents' own definitions** (ψ endpoints, V′ > 0, the τ_E, β_N and
Greenwald formulae) and against the **window the case declares** (bounds,
steady-state). Verdicts are the four-state acceptance vocabulary, and a quantity
that is absent is `unevaluated` **by name** — never silently passed.

```bash
python tools/benchmark-run.py            # run the batch, print the statistics
python tools/benchmark-run.py --write    # write benchmark/physics/ + BENCHMARK.md
```

```python
from fylite.engine import suite          # was `fylite cases --physics` before 2026-09-04
suite.entries()                          # the preset cases and their criteria
suite.run_entry(suite.entry("equilibrium-gfile"))
```

The summary table is [`BENCHMARK.md`](BENCHMARK.md); the register, its per-case
records and reports are in [`benchmark/physics/`](benchmark/physics/), and the
check register itself — what each check reads, its formula, its assumptions — is
`docs/reference/benchmark.md`.

The IMAS layouts are checked against the real readers, not against a
description of them: `rust/fylite_runtime/verify/imas_roundtrip.py` writes with
imas-python, reads with this library, writes with this library, and reads
back with imas-python and imas-core, leaf by leaf.

```bash
fy data info  g063982.04800                          # what is this file?
fy data convert g063982.04800 shot.nc --layout imas   # imas-python opens it
fy data merge machine.h5 shot.nc -o all.jsonld         # later sources win
fy data assemble east.jsonld -o east.h5 --shot 70754   # $source + $link
fy data fetch --machine east --ids magnetics \
                  --shot 138569 --time 4:5 --host mds.ipp.ac.cn -o mag.json   # 4–5 s, sliced on the server
```

```python
from fylite.io import fydoc
b = fydoc.read("g063982.04800")                 # a bundle of fyo documents
psi = b.array("equilibrium/time_slice/0/profiles_2d/0/psi")   # [R, Z]
b.write("entry_dir", layout="imas")             # IMAS HDF5 data entry
m, fails = fydoc.fetch("fydata/machine/tokamak/east/machine.yaml", "magnetics",
                       shot=138569, time=(4.0, 5.0), host="mds.ipp.ac.cn")
m.array("magnetics/b_field_pol_probe/0/field/data")   # the probe's 4–5 s slice; position from the geometry
```

The C libraries this needs (`libhdf5`, `libnetcdf`) are linked dynamically by
default; `rust/build.sh --static` compiles them in for machines without them.

## Continuous integration

★**判据按「改了什么」排班，不按「提交了几次」。** 每个工作流按路径触发，只跑它守
的那一层；全量（含跨实现对拍）每周一次，外加手动与提交信息 `[ci full]` 两个入口。

| 工作流 | 触发 | 跑什么 |
| :--- | :--- | :--- |
| `python` | `python/` `cases/` `benchmark/` `docs/` | Python 档 + 三本册子的结构检查 |
| `rust` | `rust/` | clippy(`-D warnings`) + `cargo test` ×3 套特性 |
| `physics-checks` | 判据册 · 批次 · 数据层 | 构建数据层 + 物理校验批（能评的那条真跑，`--strict`） |
| `app` | `app/` | 站点静态门（干净检出里真能判的那 6 道） |
| `full` | 周一 03:00 UTC · 手动 · `[ci full]` | 以上全部 + imas-python / imas-core 跨实现对拍 |

★CI 的绿说的是「**本仓自己的那一半**成立」：要内核（私有仓构建）、要浏览器与 wasm、
要私有语料的判据，在公开检出里**点名跳过**而不是失败——缺输入与缺实现是两件事，
`python/conftest.py` 与 `.github/workflows/README.md` 分别写明了这条政策与它的边界。

## Repository map

| path | contents |
| :--- | :--- |
| `python/fylite/` | assembly, device plumbing, IO, scenarios, the protocol engine (a LIBRARY: no CLI since 2026-09-04) |
| `rust/fylite_runtime/` | the data layer (source open): data sources ↔ fyo, IMAS netCDF/HDF5, mdsip, the `fy data` command |
| `python/tests/` | the Python tier — assembly, IO, the protocol faces, the registries, the ABI marshalling (`python/pytest.ini`) |
| | ★the physics/numerics tier is **not here**: it lives in the kernel repository with the code it judges |
| `app/` | the static browser site and its gates |
| ~~`machine_desc/`~~ | abolished 2026-09-02 — decks come from the A-Box, found through `$FYLITE_DEVICE_DIR` |
| `models/` | neural surrogates as data — one `.npz` each, none compiled in |
| ~~`examples/`~~ | removed 2026-09-02 — the runnable specifications are `cases/`, read through `fylite.engine.cases` |
| `benchmark/` `cases/` | the V&V registry and the worked cases |
| `benchmark/physics/` + [`BENCHMARK.md`](BENCHMARK.md) | the **physics-check register**: preset cases judged against physical law, the documents' own definitions and each case's declared window (`tools/benchmark-run.py`) |
| `docs/` | the MyST book: user guide, reference, cases |
| `tools/` | deck converters, page generators, oracle store maintenance |

## Two repositories

★2026-09-01 the project was split. **This** is the main repository and holds
everything above. The **Rust kernel source** lives in `fusion-yun/fylite_kernel`,
which is private and carries its own proprietary licence.

That boundary is a source boundary, not a build boundary — the two halves are
wired both ways and each direction is explicit:

| | |
| :--- | :--- |
| kernel → here | `rust/build.sh` builds `libfylite.so` and the three `.wasm`, and **installs them plus every generated file** (`_abi.py`, `_fyo_interface.py`, `_cgs.py`, `_deck_names.py`, `app/assets/version.js`, `fyo-interface.js`, `deck-names.js`, `abi.json`) into a checkout of this repository. Point it with `FYLITE_PUBLIC=`; it probes for a sibling and **refuses to guess** if it cannot find one. |
| here → kernel | `tools/build-app-exe.sh` builds the single-file desktop viewer: the viewer's *content* (the whole `app/`) is here, its *code* (`src/bin/app/`) is there. It generates the asset table into the kernel tree and compiles with `FYLITE_APP_DIR` pointing back here. Point it with `FYLITE_KERNEL=`; same refuse-to-guess rule (`tools/kernel-path.sh`). |

★★**What this repository cannot do on its own: rebuild what it ships.**
`python/fylite/_lib/libfylite.so`, the three `app/assets/*.wasm`, and eight
generated files (`_abi.py`, `_fyo_interface.py`, `_deck_names.py`, `_cgs.py`,
`app/assets/{version,fyo-interface,deck-names}.js`, `abi.json`) are committed
here but **produced there**. A reader with a complete checkout of this
repository has every line of the application layer and cannot reproduce the
twelve artifacts it runs on. That is a property of the split, stated here so
nobody concludes they are missing a step: the kernel source is not published,
and the binaries are what stands in for it. What CAN be checked from here is
that the committed artifacts are the ones that were built —
`python/tests/test_bundled_artifacts.py` asks git exactly that — and what they
answer, which is what `benchmark/` is for.

★What it answers is the public V&V register, `benchmark/` — a RENDERING of the
kernel repository's register (its `tools/benchmark-publish.py` writes this
directory): one `fyo:ComparisonRecord` per comparison, every reference dataset
with its admissibility class and sha256, every gate with the checkout it runs
in, and the outcome of running those gates on the day of publication. It is
read through the same verb as the scenario corpus:

```python
from fylite.engine import cases, casereport
from fylite.engine import benchmark as bm

cases.catalogue()                 # the scenario corpus (cases/)
bm.records()                      # the V&V register: kind, verdict, re-run, admissibility
bm.load("V-01")                   # one record, JSON-LD
[bm.problems(r, bm.registry_dir()) for r in bm.graph()]   # structure (the test tier's own function)
bm.run("V-09")                    # its private gates ($FYLITE_KERNEL=../fylite_kernel)
casereport.render(cases.run("evolve-default"))   # a case -> report.md + figures/*.svg + presentation.jsonld
casereport.render("records/<run>")               # render a record `fy case run` wrote
```

★The frozen test corpus is not here either: `tests/data` is a symlink to
`fydoc/cases/` (recorded oracle answers, upstream release cases,
reference profiles; the same tree the kernel checkout mounts at its `tests/data`). Without it the physics tier is not collected, and the
run header says so by name rather than failing 965 times.

★Neither direction hard-codes a path into a committed file. The embedded
asset table says `env!("FYLITE_APP_DIR")`, not a directory — a build machine's
layout must not end up compiled into anyone's source.

```bash
# rebuild the kernel artifacts (in the fylite_kernel checkout)
FYLITE_PUBLIC=/path/to/fylite bash rust/build.sh --wasm-check

# rebuild the desktop viewer (here)
FYLITE_KERNEL=/path/to/fylite_kernel bash tools/build-app-exe.sh linux
```

Three files at the root answer three different questions:
[`FEATURE.md`](FEATURE.md) — what physics is computable and what judges it;
[`TODO.md`](TODO.md) — what is still missing, each item with the criterion
that would close it; `changelog.md` — what changed; it records the kernel's development and
lives with it in the kernel repository.

## Attribution

Parts of the physics are white-box translations of published open-source
reference implementations rather than independent reimplementations.
`NOTICE` names the files, the upstream revisions, and the ways the
translations deliberately differ — it describes the Rust source and so lives
beside it, in the kernel repository.

★**It still has to travel with what is distributed from here.** Apache-2.0
section 4(d) attaches the obligation to the DISTRIBUTION, not to the source
tree: the wheel declares `license-files = [… "NOTICE" …]` through
`python/NOTICE`, and that symlink is currently dangling. Until a copy is
restored here, a built wheel ships without it.

[`ACKNOWLEDGEMENTS.en.md`](ACKNOWLEDGEMENTS.en.md) is the full human-readable list
of every upstream code, published formula, reference dataset and cross-code
oracle this project stands on — and how the code was built (AI-assisted,
gold-fixture verified).
