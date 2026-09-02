# `nn_tables/` — neural surrogates as DATA

Every surrogate this repository can evaluate lives here as one `.npz`, and
**none of them is compiled into `libfylite.so` or the wasm**: the kernel
holds the arithmetic (`rust/fylite/src/nn.rs`), these files hold the
numbers, and `fylite.nn` loads one when something asks for it.

```python
from fylite import nn
nn.available()                     # what is reachable
s = nn.load("epednn")              # <Surrogate epednn: 10->32x2->18, 1 members, gelu +powerlaw>
mean, spread = s(x)                # x in the model's own `s.xnames` order
s.outside_training_box(x)          # {name: (value, lo, hi)} for anything out of the box
```

`$FYLITE_NN_DIR` is searched **before** this directory, so a user can
override a shipped model or keep a big one outside the checkout.

## What is here

| file | shape | from | size |
| --- | --- | --- | ---: |
| `epednn.npz` | 10 → 32×2 → 18, 1 member, gelu, **power-law head** | EPEDNN.jl `delta_ne_sqrt_power`, via `rust/tools/extract_epednn.py` | 33 kB |
| `sat2_em_d3d_azf-1.npz` | 31 → 32 + 5 residual blocks → 4, **20 members**, elu | TGLFNN.jl 1.7.1, via `tools/nn-export.jl` | 3.5 MB |
| `qlknn_7_11.npz` | 10 → 133×5 → 8, 1 member, tanh | `fusion_surrogates` `d678186`, via `rust/tools/export_qlknn_7_11.py` | 301 kB |

The first two upstreams are Apache-2.0 (ProjectTorreyPines); QLKNN_7_11's
**weights are CC-BY 4.0** while its upstream software is Apache-2.0 (Google
LLC — see `FUSION-SURROGATES-NOTICE.md`, which states why the distinction
matters here). Their licence and notice files travel beside the weights,
and every export records the package, version, source file and its sha256
so a quoted number is traceable. **Cite doi:10.1063/1.5134126 when quoting
a QLKNN number** — upstream asks for it.

## A model that is CALLED but never shipped: UKAEA's TGLF-NN

★★[`tglfnn-ukaea`](https://github.com/ukaea/tglfnn-ukaea) — UKAEA's TGLF
SAT2 surrogates (JET / STEP / multi-machine) — **is supported and is not
here, and never will be.** Upstream is **LGPL** (its `LICENSE` says 2.1,
its `pyproject.toml` says 3.0; either way copyleft), and this repository is
Apache-2.0 and was deliberately rebuilt clean. The ruling (2026-08-30) is
*call it, do not vendor it*: distribution is what triggers copyleft, and
running a model the user already has does not.

So the weights stay in the user's own checkout, the export lands **outside
this repository**, and `$FYLITE_NN_DIR` points `fylite.nn` at it:

```bash
git clone https://github.com/ukaea/tglfnn-ukaea
python3 rust/tools/export_tglfnn_ukaea.py /path/to/tglfnn-ukaea --out ~/nn
export FYLITE_NN_DIR=~/nn
```

`rust/tools/export_tglfnn_ukaea.py` **refuses to write anywhere inside this
tree**, and `tests/test_nn_tglfnn_ukaea.py` asserts both that refusal and
that no `tglfnn-ukaea-*` file has appeared in `nn_tables/` — the rule is a
gate, not a note. In a fresh checkout
`fylite.scenario.model.tglfnn_ukaea` is inert: `available()` is False and
every entry point raises `TglfnnUkaeaUnavailable` naming the licence
reason and the recipe above. That is the intended state.

Three fluxes, five members each, `13 → 512×5 → 2`, **relu**, ~21 MB per
flux. Two things about it are worth knowing before use:

* **the particle channel is the ION flux** (`pfi_gb`) — the opposite of
  QLKNN's, which is electron-only. Upstream lists `pfe_gb` in its config
  but does not publish its parameters, so it is refused, not derived.
* **no variance, and no training box.** Each member emits
  `(μ, pre-softplus variance)` and upstream combines them as
  `E[softplus(v)] + Var[μ]`; the kernel has no per-column output
  activation, so the second column is exported raw, named `*_var_raw`, and
  the module refuses to serve it as a variance. The flux **mean** is
  exact — de-normalisation is affine, so it commutes with the average over
  members. Upstream publishes no min/max either, so
  `outside_training_box` returns `{}` for these models: an absence of a
  guard, not a clean bill of health.

Verified at **2.19e-15** against an independent numpy forward pass written
in the test file (it reads the same pickle but shares no code with the
exporter, so a transposition or a member-slicing slip cannot cancel).
★What is *not* claimed: upstream's own JAX `predict()` was not run — JAX is
not installed and does not belong in the shared venv.

`Act::Relu` was added to `nn.rs` for this model (`from_code` 4). **ABI not
bumped** — an enum value is not a signature, same as `Act::Tanh` before it.

★The shipped `sat2_em_d3d_azf-1.npz` (GA's `TGLFNN.jl`, Apache-2.0) stays
as the in-tree TGLF surrogate, because it is the one that *can* ship. The
two are not interchangeable: 31 raw TGLF-namelist inputs and a 20-member
ELU residual-block ensemble against 13 physics inputs and a 5-member relu
Gaussian ensemble.

## QLKNN: one net now, not twenty

★**2026-08-30 — QLKNN_7_11 replaced the twenty-net `qlknn-hyper` set.**
The old set was twenty networks over one nine-dimensional input, and a flux
was what a nine-step sequence of clippings and multiplications made of
their twenty answers. QLKNN_7_11 is **one** network over ten inputs that
emits eight targets — three leading fluxes, four ratios to them, and a
growth rate — so the composition is one multiplication, upstream's own
`flux_map`. It still lives in `fylite.scenario.model.qlknn` and *not* in
the kernel, because it is caller-side arithmetic.

What the swap changed, beyond arithmetic:

* **the edge arrived.** 7_11 was trained on QLKNN11D **plus QLKNN7D-edge**;
  qlknn-hyper was core-only, so its answers past the pedestal top were
  extrapolation.
* **the input basis changed.** `Zeff` is gone; dilution enters through
  `Ani` and `normni`. A caller cannot rename the old nine into these ten.
* **`dfe` went away with the twenty.** This model predicts a particle
  *flux*, not a D/V split. That decomposition is caller-side arithmetic
  over the flux and the density gradient — TORAX does exactly that, with
  two different conventions (`DV_effective` and `Dscaled`), which is
  precisely why fixing one here would be wrong.
* **1.4 MB of ten files became 301 kB of one.**

```bash
git clone https://github.com/google-deepmind/fusion_surrogates
python3 rust/tools/export_qlknn_7_11.py /path/to/fusion_surrogates --out ~/nn
export FYLITE_NN_DIR=~/nn        # searched BEFORE this directory
```

★Weights are stored **float32, losslessly** — not as a size/accuracy
trade. The net was trained in float32, so the cast is the identity; the
exporter re-checks that and refuses rather than degrade it quietly. The
scalings stay float64. Verified end to end at **1.63e-13** against
upstream's own shipped test vectors — the 25 points its own suite asserts
to ten decimals — see `tests/test_nn_qlknn.py`.

## What a model file declares

The evaluator is deliberately dumb: everything a model needs in order to
be evaluated correctly is IN the file, not in whichever caller remembers
it.  That is why the two very different models below share one code path.

* `n_in` / `n_hidden` / `n_hidden_layers` / `n_blocks` / `n_out` /
  `activation` / `n_members` — the shape;
* `x_shift`, `x_abs` — the model's own input conditioning (EPED-NN adds 1
  to the triangularity and takes the modulus of every input; TGLF-NN does
  neither);
* `log10_mask` — which inputs the NETWORK sees as `log10` (a different
  transform from the power-law head's, which always logs);
* `xm` / `xs`, `ym` / `ys` — the standardisations, applied in that order;
* `powerlaw` — optional `n_out × (n_in+1)` head that the network CORRECTS
  rather than replaces (EPED-NN has one, TGLF-NN does not);
* `xbounds` — the training box, reported by `outside_training_box` and
  never enforced: upstream warns rather than refuses, and so does this.

★A model whose weight count disagrees with its declared shape is refused
at load, against the count the KERNEL computes — not against a second
implementation of the same sum in Python.

## Adding another

Write an exporter that produces the keys above.  Nothing else changes: no
Rust, no ABI bump, no new entry point.  Text fields travel as NUL-joined
UTF-8 bytes because `.npz` has no string array.

## The one thing these files cannot tell you

Whether the answer should be believed.  `sat2_em_d3d_azf-1` is trained on
DIII-D, and on FUSE's own ITER case its two outermost faces (ρ ≥ 0.75)
leave the training box — see `tests/test_nn_surrogate.py`.  The box check
is data the caller must read, not a guard that fires.
