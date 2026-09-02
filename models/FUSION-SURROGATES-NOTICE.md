# `fusion_surrogates` — notice for `qlknn_7_11.npz`

Upstream: <https://github.com/google-deepmind/fusion_surrogates>
Copyright 2025 Google LLC. *"This is not an official Google product."*

## Two licences, and which one covers the weights

Upstream states them separately, and so must this repository:

| what | licence |
| --- | --- |
| **software** (the inference library) | Apache License 2.0 — `FUSION-SURROGATES-LICENSE` |
| **all other materials**, which is to say **the model weights and metadata** | Creative Commons Attribution 4.0 International (**CC-BY 4.0**) |

`nn_tables/qlknn_7_11.npz` is a format conversion of upstream's
`qlknn_7_11.qlknn` — weights and metadata — so it travels under **CC-BY
4.0**, whose one obligation is attribution: this file, kept beside it.
None of upstream's *software* was copied; `rust/tools/export_qlknn_7_11.py`
reads the archive and writes this repository's own format.

★This is the third licence class in `nn_tables/` (Apache-2.0 for EPED-NN
and TGLF-NN, and formerly MIT for the retired qlknn-hyper set). All three
are compatible with this repository's Apache-2.0, and each is recorded
against the model it covers rather than assumed from the directory.

## The model

QLKNN_7_11 is a neural surrogate of
[QuaLiKiz](https://gitlab.com/qualikiz-group/QuaLiKiz), a quasilinear
gyrokinetic code for turbulent transport in tokamaks. It is based on the
QLKNN10D model of van de Plassche et al., and was trained by combining the
[QLKNN11D](https://zenodo.org/record/8017522) and
[QLKNN7D-edge](https://zenodo.org/record/8106431) datasets. Upstream notes
that a paper describing the model itself is in preparation.

## Citation

Upstream asks that this be cited when the model is used:

> K. L. van de Plassche, J. Citrin, C. Bourdelle, Y. Camenen, F. J. Casson,
> V. I. Dagnelie, F. Felici, A. Ho, S. Van Mulders,
> *"Fast modeling of turbulent transport in fusion plasmas using neural
> networks"*, Physics of Plasmas **27**, 022310 (2020),
> [doi:10.1063/1.5134126](https://doi.org/10.1063/1.5134126).

Version: `git:d678186baaffec30c34cdf838321eaa4bcf0b018`, archive version
tag `11D`, `sha256` of the source archive recorded inside the `.npz`.
