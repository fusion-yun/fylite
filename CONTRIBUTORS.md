# Contributors

fylite is developed by the integrated-modelling group at the Institute of Plasma
Physics, Chinese Academy of Sciences (ASIPP). Copyright 2026 ASIPP and the fylite
contributors; licensed under the Apache License 2.0 (full text in
[`LICENSE`](LICENSE)).

## Maintainers

- Zhi YU (ASIPP) — <yuzhi@ipp.ac.cn>
- Xiaojuan LIU (ASIPP) — <lxj@ipp.ac.cn>

## Contact

Security reports go to both addresses above, with `[fylite security]` in the
subject; the rules — including *do not attach experimental data* — are in
[`SECURITY.md`](SECURITY.md). Everything else goes to an issue: blank issues are
off, and the templates are in `.github/ISSUE_TEMPLATE/`.

## Where the rest is recorded

This file is a set of addresses, not the roll of contributors:

- **Who changed which line, and when** — `git log`: the author field and the
  `Co-Authored-By:` trailers.
- **Where the data, diagnostic geometry, workflows and comparison cases came
  from** — [`docs/ACKNOWLEDGEMENTS.md`](docs/ACKNOWLEDGEMENTS.md).
- **What was ported, what was modified, and what is not included** — `NOTICE`.
  It stays with the Rust kernel sources and is installed into the wheel at build
  time, so a plain checkout of this repository does not carry it.

Two facts a reader would otherwise reconstruct from `git log`: `YuZhi` and
`Zhi YU` are one person (two git identities on two machines), and a substantial
part of the history was written with machine assistance, recorded in the author
field and the `Co-Authored-By:` trailers. Credit follows the commit;
responsibility does not — every line merged into `develop` is a maintainer's.

## How a contribution is licensed

Per Apache-2.0 §5, a contribution submitted here is licensed under Apache-2.0
unless its submitter states otherwise. There is no separate contributor agreement
to sign.
