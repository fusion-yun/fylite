# Acknowledgements

fylite is a standalone, lightweight implementation of the fyo semantic contract
covering tokamak equilibrium, transport and 0-D modelling.

fylite is developed as part of the work of the **Integrated Modelling Discussion
Group**（集成建模讨论组）at the Institute of Plasma Physics, Chinese Academy of
Sciences (ASIPP). Copyright is held by ASIPP and the fylite contributors, and it
is released under the **Apache License 2.0**.

This project has benefited from the work and the collaborators below. With
thanks:

## Principal collaborations

- **The Integrated Modelling Discussion Group**: Youwen SUN (孙有文),
  Qilong REN (任启龙), Xiang JIAN (简祥), Tianyang XIA (夏天阳), Zhi YU (于治),
  Xiaojuan LIU (刘晓娟), Yemin HU (胡也民), Xiaotao XIAO (肖小涛) and others.
- **The ASIPP EAST team** — the discharge data, the operational EFIT workflow
  and the per-channel diagnostic geometry.
- **Jinping QIAN (钱金平), Guoqiang LI (李国强), Qilong REN (任启龙),
  L. L. Lao et al.** — the port of EFIT to EAST and its kinetic reconstruction
  (KEFIT), the upstream reference baseline of this repository's reconstruction
  line.
- **Youwen SUN (孙有文)** — the HT-7 soft-X-ray tomography work (camera-geometry
  parameterisation and the chord-Green / weighted-pseudo-inverse method
  skeleton).
- **Ting LAN (兰婷)** — collecting and curating the EAST experimental data
  corpus; the per-channel diagnostic geometry reaches this project through
  fydata.
- **Yao HUANG (黄耀) and the EAST PCS group** — the plasma-control-system
  interface note (magnetic-probe geometry and the equilibrium↔PCS variable
  cross-check).
- **Xuemin WU (吴学民), Hui SHENG (盛回)** — guidance on and clarification of the
  KEFIT operating procedure, and the benchmark cases they provided.

## Upstream code that was ported (white-box translation)

The modules below are **white-box ports** of upstream code, not independent
reimplementations from the literature. That distinction is a licence
obligation, so it is stated here in the body rather than in a footnote.

| Upstream | Authors / institution | Licence | What fylite took | Where |
| :-- | :-- | :-- | :-- | :-- |
| **GACODE — GEO** | J. Candy, General Atomics | Apache-2.0 | flux-surface local geometry (Miller-family shape and metric, `geo.f90`) | `rust/fylite/src/geometry.rs` |
| **GACODE — NEO** | E. Belli, J. Candy, General Atomics | Apache-2.0 | neoclassical analytic models (`neo_equilibrium`, `neo_make_profiles`, `compute_Sauter*`) and the drift-kinetic solve | `rust/fylite/src/neoclassical.rs`、`dke.rs` |
| **GACODE — TGLF** | G. M. Staebler et al., General Atomics | Apache-2.0 | gyro-Landau-fluid model, FLR fit tables, trapped-closure tables | `rust/fylite/src/gyrofluid.rs`、`flr_tables.rs`、`closure_tables.rs` |
| **GACODE — TGYRO / expro** | General Atomics and the GACODE contributors | Apache-2.0 | NEO / TGLF input maps, source and radiation terms, volume integrals, `expro_compute_derived`, `input.gacode` reader | `rust/fylite/src/mapping.rs`、`sources.rs`、`bundle.rs`；`python/fylite/scenario/model/{mapping,sources}.py`；`python/fylite/io/gacode.py` |
| **NCLASS** (vendored inside GACODE) | W. A. Houlberg | via NEO | neoclassical coefficients as carried by NEO | via the NEO port |
| **METIS** | J. F. Artaud et al., CEA/IRFM | CeCILL-C | fast-neutral-beam model: chord attenuation, Janev stopping cross sections, Stix critical energy and beam-driven current (formula-level transcription, see "Physics transcribed from published formulae") | `rust/fylite/src/heating.rs` |
| **FyTok — fytrans** | Institute of Plasma Physics, CAS (fylite's parent project) | Apache-2.0 | the channel-declaration syntax (kept verbatim, so a declaration round-trips between the parent project and this one); the 1.5-D transport core is anchored bit-for-bit against it | `python/fylite/scenario/`; see [FyTok](https://github.com/fusion-yun/fytok) |

**Statement of modification** (Apache-2.0 §4b): a port is a translation, not a
copy — module state became explicit arguments, LAPACK / UMFPACK were replaced by
this repository's own dense and sparse routines, upstream `STOP` became a
returned error code, and the result is re-entrant. Several places
**deliberately diverge** from upstream behaviour (mostly where upstream quietly
overwrites its own inputs); each is marked in-source. The full list is in
`NOTICE`. UMFPACK was **not** ported — the sparse LU is written from scratch.

## Physics transcribed from published formulae

| Source | Used for | Where |
| :-- | :-- | :-- |
| **METIS** — J. F. Artaud et al., *Nucl. Fusion* 58 (2018) 105001; CEA/IRFM, CeCILL-C | NBI fast-neutral ionisation, beam current-drive integral, slowing-down energy, impurity form (`z0signbi`、`zicd0`、`zsupra0`、`zfract0`); **the minority ICRH chain** (`z0icrh` — resonance layer, Stix distribution, fast-ion content, Eriksson electron share — and `z0qp`) — formula-level transcription, kept byte-comparable to METIS | `rust/fylite/src/heating.rs` |
| L. L. Lao et al., *Nucl. Fusion* 25 (1985) 1611 | reconstruction structure (Picard + least squares) — algorithm reference only, see "What was deliberately not taken" | `rust/fylite/src/inverse.rs` |
| O. Sauter, C. Angioni, Y. R. Lin-Liu, *Phys. Plasmas* 6 (1999) 2834 | bootstrap current / conductivity | `rust/fylite/src/neoclassical.rs` |
| A. Redl, C. Angioni, E. Belli, O. Sauter, *Phys. Plasmas* 28 (2021) 022502 | bootstrap recalibration (two readings **kept apart**: NEO's `compute_Sauter_mod` and the IMAS.jl / FUSE lineage) | `rust/fylite/src/neoclassical.rs`、`python/fylite/scenario/model/neoclassical.py` |
| Hinton–Hazeltine; Chang–Hinton; Hirshman–Sigmar; Taguchi; Hinton–Rosenbluth; Koh et al.; Y. R. Lin-Liu & R. L. Miller (1995) | analytic neoclassical variants and trapped fraction | `rust/fylite/src/neoclassical.rs`、`dke.rs` |
| Y. R. Lin-Liu & F. L. Hinton, *Phys. Plasmas* 4 (1997) 4179 | NBCD electron shielding | `rust/fylite/src/heating.rs` |
| T. H. Stix, *Nucl. Fusion* 15 (1975) 737 | the minority ICRH distribution and its H function | `rust/fylite/src/heating.rs` |
| ITER Physics Basis, *Nucl. Fusion* 39 (1999) 2495, Chapter 6 §3.5 (p. 2512) — the measured fast-wave current-drive efficiencies (JFT-2M, DIII-D, Tore-Supra), their linear `T_e0` dependence and the ITER extrapolation; the data points themselves as tabulated in METIS `fitetafwcd.m` | FWCD efficiency and the gate on it | `rust/fylite/src/heating.rs` |
| M. Bornatici, R. Cano, O. De Barbieri, F. Engelmann, *Nucl. Fusion* 23 (1983) 1153, Table 12 — read in the verbatim reprint of A. Sabri et al., *Int. J. Emerging Technology and Advanced Engineering* 2 (8) (2012) 253, Table I (the original was not obtainable here; the reprint is what was transcribed, and both are cited in-source) | EC optical depth of a `1/R` slab (O-mode `n>=1`, X-mode `n>=2`) and the cold perpendicular refractive indices | `rust/fylite/src/heating.rs` |
| G. Giruzzi, *Nucl. Fusion* 27 (1987) 2069 (as fitted in METIS `zicd0.m`); Y. R. Lin-Liu, GA-A24257 (the `Z_eff` dependence) | EC current-drive efficiency | `rust/fylite/src/heating.rs` |
| ITER / IMAS EC launch-angle convention, as implemented in **FUSE** (`IMAS.jl` `pol_tor_angles_2_vector`, Apache-2.0) | the two steering angles a machine description stores, and the direction they mean | `rust/fylite/src/heating.rs` |
| R. K. Janev, C. D. Boley, D. E. Post (1989) | beam-stopping / charge-exchange cross sections | `rust/fylite/src/heating.rs` |
| S. Weiland et al., *Nucl. Fusion* 58 (2018) 082032 (RABBIT) | fast NBI model class | `rust/fylite/src/heating.rs` |
| T. Pütterich et al., *Nucl. Fusion* 59 (2019) 056013; Open-ADAS (<https://open.adas.ac.uk>) | cooling-curve Chebyshev fits | `rust/fylite/src/sources.rs` |
| ITER Physics Basis, *Nucl. Fusion* 39 (1999) 2175 (IPB98(y,2)); P. N. Yushmanov et al., *Nucl. Fusion* 30 (1990) 1999 (ITER89-P); Y. Martin et al., *J. Phys. Conf. Ser.* 123 (2008) 012033 (L–H threshold); H.-S. Bosch & G. M. Hale, *Nucl. Fusion* 32 (1992) 611 (D-T reactivity) | 0-D scalings | `rust/fylite/src/zerod.rs` |
| P. B. Snyder et al., *Phys. Plasmas* 16 (2009) 056118 (the two EPED1 constraints); O. Meneghini et al., *Nucl. Fusion* 57 (2017) 086034 (the EPED1-NN surrogate) | pedestal model; the network weights come from the open-source EPEDNN.jl (ProjectTorreyPines, Apache-2.0; licence and checksum carried in this repository) | see the FUSE / EPEDNN rows under "Reference data, oracles and cross-code anchors" |
| S. Jardin, *Computational Methods in Plasma Physics* §4.4; Hockney's direct elliptic solver (*J. ACM* 12 (1965) 95); Solov'ev analytic equilibrium | GS solver numerics and analytic oracle | `rust/fylite/src/equilibrium.rs` |
| Qian (2014) EFIT `&IN1` Thomson-density spline convention | k-file constraint block | `python/fylite/io/kfile.py` |

## What was deliberately not taken

An acknowledgement that lists only what was taken is incomplete. The items
below were **deliberately not taken**, for differing reasons, but they belong to
the same record:

- **EFIT lineage**: no EFIT-family source, Green's-table generator or recorded
  output is present in any form; `equilibrium.rs` and `inverse.rs` are
  clean-room (their author has not read `fortran/efit/src/`).
- **GRAY**: the EC ray-tracing port was stopped; its licence does not permit
  direct translation, and no GRAY physics source was read for fylite.
- **UMFPACK**: not ported — the sparse LU is written from scratch (see
  "Upstream code that was ported").

## Reference data, oracles and cross-code anchors

| Data / oracle | Provider | Terms | Use |
| :-- | :-- | :-- | :-- |
| GACODE regression decks and recorded outputs (`tglf01` GA standard case, TGYRO `treg01`, libgeo/libneo/libtglf recordings) | General Atomics (GACODE `6357db306` / `5efddfdf1`) | Apache-2.0 | `tests/data/*`、`tests/oracles/` — the gold fixtures of the ports |
| **EAST shot #137985 @ 4.0 s** (magnetics, POINT, Thomson; `efit_east` tree) | EAST team, Institute of Plasma Physics, CAS (ASIPP); MDSplus server on the institute network | institutional | the only real-shot fixture set (`examples/scripts/`、`examples/east137985-recon-figure/`). ★**not published with the demonstration** |
| EAST operational EFIT workflow (`EFIT_POINT_GUI_v5.m`, est2 `dprobe.dat`, `fitweight.dat`) | ASIPP | institutional; reproduced headlessly, not copied | `python/fylite/io/kfile.py`、`fylite.machine` |
| **KEFIT reference bundle** (**not in this repository**) | EAST KEFIT — the port of DIII-D-lineage EFIT to EAST and its kinetic reconstruction by G. Q. Li, Q. L. Ren, J. P. Qian, L. L. Lao et al. (*Plasma Phys. Control. Fusion* 55 (2013) 125008; H. Fan et al. 2024 for the internal-q constraint); ASIPP | internal, unlicensed, not redistributed | upstream reference baseline of the reconstruction line: byte-equivalent g-file comparison, the k/g/a/m file contracts, the GUI_v5 workflow reproduced in `python/fylite/io/kfile.py` |
| **sxht7** — ASIPP HT-7 soft-X-ray tomography code (c. 2008) | Youwen SUN (孙有文), ASIPP | internal, unlicensed | camera-geometry parameterisation (4 cameras × 6 numbers) and the Fourier–Bessel / chord-Green / weighted-pseudo-inverse method skeleton, ported into `python/fylite/device.py` (camera geometry) and `python/fylite/scenario/analysis/tomography.py` (method skeleton) |
| EAST plasma-control-system interface note (*数字托克马克仿真模拟平台等离子体控制系统接口说明*, 2022; ISO-FLUX control points, segments, X-point, magnetic geometry) | Yao HUANG (黄耀), EAST PCS group, ASIPP | internal document | cross-check of magnetic-probe geometry; equilibrium↔PCS interface variables |
| EAST experimental data corpus `YLK_*` / `eastylk` (shots #137985–137989 etc.; per-channel diagnostic geometry `<DIAG>_desc.json` and signals) | collected and curated by Ting LAN (兰婷), ASIPP | institutional | per-channel EAST diagnostic geometry that reaches fylite through fydata; predecessor of the MDSplus-based real-shot fixtures (the file corpus itself is retired as a fixture path) |
| **TokSys** EAST electromagnetic model (`make_east_objects.m`、`rzrig`、`EAST_PS_params`) | General Atomics | external, not vendored | cross-code anchor for circuits and vertical stability (`tests/test_benchmark_toksys.py`) |
| **METIS certification baseline** | CEA/IRFM (via fywork CASE-07) | CeCILL-C; not redistributed here | 0-D energy-accounting comparison (`examples/zerod-metis/`) |
| **METIS certification suite — the ICRH / ECCD answers** | CEA/IRFM (J.-F. Artaud and the METIS contributors) | CeCILL-C; the archives are **not redistributed here** — only the derived table, with each archive's sha256 in its header | the reference a future ICRH / ECRH model is judged by (`tests/data/reference/metis_cert_hcd.csv`, written by `tools/metis-cert-to-oracle.py`; assessment in `docs/note/icrh-ecrh-gap.md`) |
| **FUSE device cases — the INPUT scalars only** (`case_parameters(:X)` for ITER, KSTAR, DTT, SPARC, ARC, FPP, K-DEMO, MANTA, EXCITE) | ProjectTorreyPines (FUSE.jl `494d565`, with IMAS.jl and MillerExtendedHarmonic.jl v2.1.2 for the two resolution rules) | Apache-2.0; **no FUSE source or data file is redistributed here** — what is carried is a table of scalars read out of a checkout, with the commit and the source file named in every generated document | the worked cases the time-evolution bar offers (`docs/cases/evolve-fuse-*.jsonld`, written by `tools/fuse-case-to-fylite.py`; inventory and judgement in `docs/note/fuse-cases.md`). ★These carry FUSE's **INPUTS** only — chi_0 and the rest of the closure are this repository's, so they are not a reproduction of FUSE's answer |
| **FUSE — one ITER run's INPUTS and ANSWERS** (`FUSE.init(:ITER, init_from=:scalars)`, FUSE 0.7.0 / EPEDNN 1.0.7, recorded 2026-08-29) | ProjectTorreyPines | Apache-2.0; **no FUSE source or data file is redistributed here** — the records hold the ten EPED inputs FUSE chose and the nine answers it gave, plus its solved equilibrium, 0-D account and profiles | the T-C1′ benchmark: `tests/data/fuse/iter_eped.json`、`iter_init.json`, gated by `tests/test_fuse_benchmark.py`, re-captured by `tools/fuse/capture-iter.jl`. ★The pedestal layer is not「two models agree」: FUSE's `ActorPedestal` and this kernel load the **same** EPEDNN BSON weights, so it measures whether the port stayed the same function (4.4e-16) |
| **TGLF-NN — the ARCHITECTURE and one run's ANSWERS; no weights** | ProjectTorreyPines (TGLFNN.jl 1.7.1) | Apache-2.0; ★★**no model file is redistributed and none is compiled in** — `rust/fylite/src/nn.rs` implements the dense+residual family the shipped models use, `tools/nn-export.jl` converts one on a host that has the package, and `$FYLITE_NN_DIR` is where the user keeps it | the surrogate path, gated by `tests/test_nn_surrogate.py` against TGLF-NN's own answers on FUSE's ITER decks (`tests/data/fuse/iter_tglfnn.json`, 4.9e-14). Each export records the upstream package, version, file and sha256, so a quoted number is traceable to an artefact this repository does not hold |
| ITER device description (PF/CS coils, wall, 110 flux loops; ITER EDA, 26 Apr 2010) | ITER Organization, via the `fydata` package | as recorded in fydata | browser preset device (`app/devices/iter.jsonld`); the ITER configuration built into the demonstration comes from here |

## Libraries and tooling

`numpy` (required); optional `PyYAML`、`matplotlib`、`MDSplus` (lazy, not on
PyPI); Rust crate `rayon` (optional `parallel` feature). The browser front end
**vendors no third-party JavaScript**. Documentation is built with MyST.

## References

The methods used in this project are all public methods. The main sources are
listed below by topic; the module-by-module correspondence is in "Upstream code
that was ported" and "Physics transcribed from published formulae".

### Equilibrium and reconstruction

- The equilibrium itself is the Grad–Shafranov equation (Grad and Rubin 1958;
  Shafranov 1966).
- Fitting p′/FF′ polynomials to magnetic measurements and solving alternately
  with the equilibrium under the plasma-current equality constraint is the
  reconstruction framework of Lao et al.: L. L. Lao, H. St. John,
  R. D. Stambaugh, A. G. Kellman, W. Pfeiffer, *Reconstruction of current
  profile parameters and plasma shapes in tokamaks*, Nuclear Fusion **25**
  (1985) 1611.
- Free-boundary solution and the stabilised treatment of vertical position:
  S. C. Jardin, *Computational Methods in Plasma Physics*, CRC Press, 2010.
- Fast direct solution on a regular grid: R. W. Hockney, *A fast direct
  solution of Poisson's equation using Fourier analysis*, Journal of the ACM
  **12** (1965) 95.
- Definitions of safety factor, shape quantities and other equilibrium
  measures, and the general background of tokamak physics: J. Wesson,
  *Tokamaks*, 4th ed., Oxford University Press, 2011.

### Transport and turbulence

- Analytic expressions for neoclassical conductivity and bootstrap current:
  O. Sauter, C. Angioni, Y. R. Lin-Liu, *Neoclassical conductivity and
  bootstrap current formulas*, Physics of Plasmas **6** (1999) 2834.
- Recalibration of the bootstrap current: A. Redl, C. Angioni, E. Belli,
  O. Sauter, *A new set of analytical formulae for the computation of the
  bootstrap current*, Physics of Plasmas **28** (2021) 022502.
- Analytic neoclassical variants and trapped fraction: C. S. Chang,
  F. L. Hinton, Physics of Fluids **25** (1982) 1493; Y. R. Lin-Liu,
  R. L. Miller, Physics of Plasmas **2** (1995) 1666.
- Gyro-Landau-fluid quasilinear transport model (TGLF): G. M. Staebler,
  J. E. Kinsey, R. E. Waltz, *A theory-based transport model with comprehensive
  physics*, Physics of Plasmas **14** (2007) 055909.
- Direct solution of the drift-kinetic equation (NEO): E. A. Belli, J. Candy,
  *Kinetic calculation of neoclassical transport including self-consistent
  electron and impurity dynamics*, Plasma Physics and Controlled Fusion **50**
  (2008) 095010.

### 0-D integrated modelling, sources and atomic data

- Energy-confinement scaling laws: ITER Physics Basis, Nuclear Fusion **39**
  (1999) 2175 (IPB98(y,2)); P. N. Yushmanov et al., Nuclear Fusion **30** (1990)
  1999 (ITER89-P).
- D-T reactivity: H.-S. Bosch, G. M. Hale, *Improved formulas for fusion
  cross-sections and thermal reactivities*, Nuclear Fusion **32** (1992) 611.
- L–H threshold power: Y. Martin et al., *Power requirement for accessing the
  H-mode*, Journal of Physics: Conference Series **123** (2008) 012033.
- The 0-D integrated-modelling comparison code, and the source of the
  fast-neutral-beam model: J. F. Artaud et al., *Metis: a fast integrated
  tokamak modelling tool*, Nuclear Fusion **58** (2018) 105001.
- Impurity radiative cooling curves: T. Pütterich et al., Nuclear Fusion **59**
  (2019) 056013; Open-ADAS, <https://open.adas.ac.uk>.
- Neutral-beam stopping and charge-exchange cross sections: R. K. Janev,
  C. D. Boley, D. E. Post, *Penetration of energetic neutral beams into fusion
  plasmas*, Nuclear Fusion **29** (1989) 2125.

## Full texts

This file is the readable acknowledgement list in full. The binding, per-file
statements are:

- [`LICENSE`](LICENSE) — the full text of Apache License 2.0
- [`NOTICE`](NOTICE) — per-file port provenance, statement of modification, and
  what is *not* included
- [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) — the Chinese version of this
  file
- [`CONTRIBUTORS.md`](CONTRIBUTORS.md) — maintainers and copyright
