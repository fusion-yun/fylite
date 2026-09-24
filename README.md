# fylite — a self-contained tokamak equilibrium, transport and turbulence kernel

![FYLITE](./docs/figures/fylite_logo.svg)

fylite packs a Grad-Shafranov solver (forward and inverse), a 1.5-D
core-transport step, neoclassical and gyro-Landau-fluid closures, and an
equilibrium-reconstruction row into **one re-entrant Rust kernel**, with a thin
Python layer for assembly and orchestration and a browser front end built from
the same kernel compiled to WebAssembly.

It is a standalone package covering physics modelling, experiment analysis,
control simulation and discharge design, with one minimal runnable, interactive,
comparable closed loop per line. Four constraints size it:

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
listed rather than filled with functions that return zeros.

## What this repository is

This is the **release repository**: one snapshot commit per release, carrying
what a user needs — the user guide, the worked examples, the application
walk-throughs and the licences. The Python wheel and the `fy` executable are
attached to each [GitHub Release](https://github.com/fusion-yun/fylite/releases),
not committed. Development happens elsewhere, so patches cannot be merged here;
a precise issue is the contribution (see [Reporting a problem](#reporting-a-problem)).

> ★The kernel binaries (wheel, `fy`) are licensed under PolyForm Noncommercial
> 1.0.0 ([`LICENSE-BINARY`](LICENSE-BINARY)) — noncommercial use only.

| path | what it is |
| :--- | :--- |
| [`docs/`](docs/index.md) | the user guide: install, quick start, the three hosts (browser, `fy`, Python), how to read results, and the topic chapters |
| [`examples/`](examples/index.md) | the worked examples — one directory per family, the runnable scenario documents beside the chapter that explains them |
| [`apps/`](apps/README.md) | application walk-throughs built on the released package |
| [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) | every upstream code, published formula, reference dataset and cross-code benchmark this project stands on |
| [`NOTICE`](NOTICE) · [`LICENSE`](LICENSE) · [`LICENSE-BINARY`](LICENSE-BINARY) | attribution and the licence terms (see [Licence](#licence-and-attribution)) |
| [`CHANGELOG.md`](CHANGELOG.md) | what changed, release by release |

## Try it

<https://fusion-yun.github.io/fylite/> — the whole kernel compiled to
WebAssembly and running in the browser. Nothing to install, nothing uploaded.
The three scenario pages are under `pages/`
([model](https://fusion-yun.github.io/fylite/pages/model.html) ·
[pulse_design](https://fusion-yun.github.io/fylite/pages/pulse_design.html) ·
[analysis](https://fusion-yun.github.io/fylite/pages/analysis.html)), beside the
two tool pages: a data browser and a case report.

## Install

From a release: the wheel (Python, numpy only) and `fy` (one static
executable). The [install chapter](docs/install.md) covers both, and the
machine descriptions a run needs (`$FYLITE_DEVICE_DIR`).

```python
from fylite import scenario as S

z = S.model.zerod()                     # 0-D discharge, prescribed profiles
t = S.model.transport(power=4.0)        # one 1.5-D transport step
```

The Python package is a **library**: no `fylite` console script, no
`python -m fylite`. The one command line is `fy`, whose four command words are
`app` / `data` / `run` / `list` — see [the CLI guide](docs/cli.md).

Every interface — the browser page, `fy` and the Python package — opens with the
same notice. `fy` and `import fylite` print it on **stderr, and only when stderr
is a terminal**, so `fy list --json | jq` and `python x.py > out` carry only your
data. `FY_NO_BANNER=1` drops the wordmark and the version line and **keeps the
notice** — it is a condition of use, not decoration — and `FY_LANG` picks the
language.

## Running a case

A case is **one structure in, one structure out**: a scenario specification
(the documents under [`examples/`](examples/index.md)) goes in, a computation
record with its produced datasets comes out. A case the kernel cannot complete
is **refused with the missing thing named**, and the refusal is recorded too.

```sh
fy list kernel                                     # what the kernel completes
fy run examples/evolve/evolve-default.jsonld nsteps=12 --dry-run
fy run examples/evolve/evolve-default.jsonld nsteps=12 --record records/evolve
#  -> records/evolve/{record.jsonld, plan.jsonld, core_profiles.fyo.jsonld, ...}
```

The worked examples are one chapter per family, every command and number in
them measured, every chapter saying what its family **cannot** answer:
[0-D](examples/zerod/zerod.md) ·
[1.5-D](examples/transport/transport.md) ·
[time evolution](examples/evolve/evolve.md) ·
[discharge design](examples/design/design.md) ·
[equilibrium reconstruction](examples/reconstruction/reconstruction.md).
What the physics can and cannot do today is [capabilities and limits](docs/limits.md).

## Reading and writing data

`fy data` and `fylite.io.fydoc` convert between data sources and fyo documents,
merge several sources, and assemble them from a JSON-LD description. Files are
recognised by **content**, never by name.

| source | read | write | layouts |
| :--- | :-: | :-: | :--- |
| MDSplus (mdsip, read-only by construction) | ✓ | — | fyo |
| device deck YAML | ✓ | — | fyo |
| EFIT a-file | ✓ | — | fyo |
| EFIT g-file | ✓ | ✓ | fyo |
| JSON / JSON-LD | ✓ | ✓ | fyo · IMAS DD |
| HDF5 | ✓ | ✓ | fyo · IMAS (imas-core HDF5 backend) |
| netCDF | ✓ | ✓ | fyo · IMAS (imas-python netCDF backend) |

```bash
fy data info  g063982.04800                          # what is this file?
fy data convert g063982.04800 shot.nc --layout imas  # imas-python opens it
fy data merge machine.h5 shot.nc -o all.jsonld       # later sources win
```

## What ships, and what does not

- **No experimental data is committed.** No shot files, no reconstructions of
  real discharges. [`examples/`](examples/index.md) publishes the
  *specification* of each case (a plan document, no numbers) and resolves its
  data through `$FYLITE_DEVICE_DIR`.
- **Machine descriptions are inputs, with exactly one source**, found through
  `$FYLITE_DEVICE_DIR`; what a source does not carry is declared, with a reason,
  rather than defaulted.
- **No third-party solver code ships in any form other than the translations
  `NOTICE` declares.**

## Licence and attribution

- The Python package source (inside the wheel) is **Apache-2.0** ([`LICENSE`](LICENSE)).
- The compiled kernel (`libfylite.so` in the wheel, `fy`, the site's `.wasm`) is
  distributed under the **PolyForm Noncommercial License 1.0.0**
  ([`LICENSE-BINARY`](LICENSE-BINARY)): free for noncommercial purposes —
  personal research and study, and use by educational institutions, public
  research organisations and government institutions — and **not for commercial
  use**. For a commercial licence, contact the author, YU Zhi
  <yuzhi@ipp.ac.cn>. The kernel's source is not published, so the kernel is not
  open source; only the Apache-2.0 parts are.
- The documentation and examples are **CC-BY-4.0**.

Parts of the physics are white-box translations of published open-source
reference implementations rather than independent reimplementations;
[`NOTICE`](NOTICE) names them, their upstream licences and the ways the
translations deliberately differ, and travels with every distribution (wheel and
site). [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) is the full human-readable
list — and says how the code was built (AI-assisted, gold-fixture verified).

## Reporting a problem

Open an issue. The kernel source is not published, so reproducing a report
depends on knowing **which binary** you ran: the issue template asks for the demo
page's footer line (`kernel … · interface … · app …`) and the kernel `sha256`
shown on its credits page. Security issues: see [`SECURITY.md`](SECURITY.md).
