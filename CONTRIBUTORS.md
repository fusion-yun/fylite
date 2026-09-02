# 贡献者 · Contributors

fylite 由中国科学院等离子体物理研究所（ASIPP）**「集成建模讨论组」**开发。版权归
ASIPP 与 fylite 贡献者所有，按 **Apache License 2.0** 发布（全文见
[`LICENSE`](LICENSE)）。

fylite is developed by the integrated-modelling group at the Institute of Plasma
Physics, Chinese Academy of Sciences (ASIPP). Copyright 2026 ASIPP and the fylite
contributors; licensed under the Apache License 2.0 (full text in
[`LICENSE`](LICENSE)).

★**`NOTICE` 与 Rust 内核源码同处，不在公开仓。** 它逐文件记的是移植出处与修改说明，
随内核留在 `fylite_kernel`；Apache-2.0 §4(d) 的义务附着在**分发件**上，所以它在打轮
那一刻由 `tools/build-wheel.sh` 装入（`pyproject.toml` 里那项因此写成 `NOTICE*` 这个
glob，缺席只是少一份文件，不是构建失败）。**普通检出里看不到它，不是漏了**——可读的
全表在 [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md)。

★**`NOTICE` sits with the Rust kernel sources, not in the public repository.** It
records port provenance and the statement of modification file by file, and stays
in `fylite_kernel`; the Apache-2.0 §4(d) obligation attaches to the **distribution**,
so `tools/build-wheel.sh` installs it at wheel-build time (hence the `NOTICE*` glob
in `pyproject.toml`). Its absence from a plain checkout is deliberate; the readable
full list is [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md).

## 维护者 · Maintainers

- Zhi YU (ASIPP) — <yuzhi@ipp.ac.cn>
- Xiaojuan LIU (ASIPP) — <lxj@ipp.ac.cn>

**寄给谁**：安全问题发给上面两位、标题带 `[fylite security]`，规矩（含★「报告里不要附
实验数据」）见 [`SECURITY.md`](SECURITY.md)；**其他一切走 issue**——本仓关掉了空白
issue，模板在 `.github/ISSUE_TEMPLATE/`。公开的问题在公开处答，答案才留得下来。

**Where to send what**: a security problem goes to both addresses above with
`[fylite security]` in the subject — the rules, including ★"do not attach
experimental data", are in [`SECURITY.md`](SECURITY.md). Everything else goes to an
**issue**: blank issues are off, and the templates are in `.github/ISSUE_TEMPLATE/`.

## 这份名单之外 · Beyond this list

★**这份文件不是贡献者全表，是收信地址。** 三处记录各管一段，别指望其中一处兼任另一处：

| 要找什么 | 去哪里读 |
| :--- | :--- |
| 谁改了哪一行、什么时候 | `git log` —— 逐提交的作者字段与 `Co-Authored-By:` 附署 |
| 数据、诊断几何、运行流程与对拍算例从谁那里来 | [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md)（英文：[`ACKNOWLEDGEMENTS.en.md`](ACKNOWLEDGEMENTS.en.md)） |
| 移植了谁的代码、改了什么、**不含**什么 | `NOTICE`（随内核，见上） |

★**This file is a set of addresses, not the roll of contributors.** Three records
each cover one thing: `git log` for who changed which line (author field and
`Co-Authored-By:` trailers), `ACKNOWLEDGEMENTS.md` for where the data, diagnostic
geometry, workflows and comparison cases came from, and `NOTICE` for what was
ported, what was modified, and what is *not* included.

两条实情，写在这里免得读者去 `git log` 里自己拼：

- 历史里的 `YuZhi` 与 `Zhi YU` 是**同一人**（两台机器上的两条 git 身份），不是两位贡献者。
- 相当一部分提交**由机器助手代写**，作者字段与 `Co-Authored-By:` 附署都如实记着这件事。
  ★署名归属看提交本身，责任不随之转移：**合并进 `develop` 的每一行都由维护者负责**。

Two facts a reader would otherwise have to reconstruct from `git log`: `YuZhi` and
`Zhi YU` are **one person** (two git identities on two machines), not two
contributors; and a substantial part of the history was **written with machine
assistance**, recorded honestly in the author field and the `Co-Authored-By:`
trailers. ★Credit follows the commit; responsibility does not move with it —
every line merged into `develop` is a maintainer's.

## 贡献如何授权 · How a contribution is licensed

按 Apache-2.0 **§5**：向本仓提交的贡献，缺省即按 **Apache-2.0** 授权，除非提交者明确
另作声明。本仓**没有**另立的贡献者协议（CLA）文件——没有要签的第二份东西。

Per Apache-2.0 **§5**, a contribution submitted here is licensed under Apache-2.0
by default unless its submitter explicitly states otherwise. This repository defines
no separate contributor agreement; there is no second document to sign.

## 这份文件会随轮出门 · This file ships

`python/pyproject.toml` 的 `license-files` 把它与 `LICENSE`、`NOTICE` 一并装进 wheel
（`python/CONTRIBUTORS.md` 是指回仓根的符号链接——setuptools 只在工程目录内解析那一项）。
于是它落在 [`SECURITY.md`](SECURITY.md) 那条**已发布制品**的规矩下：不写运营方内网地址，
不写构建者家目录路径。上面两个是机构邮箱，是有意公开的联系方式。

It is listed in `license-files`, so it goes out inside every wheel (and
`python/CONTRIBUTORS.md` is a symlink back to this file — setuptools resolves that
entry only inside the project directory). It therefore falls under the
published-artifact rule in [`SECURITY.md`](SECURITY.md): no operator-internal
address, no builder home path. The two addresses above are institutional and
published on purpose.

★`fylite_kernel/CONTRIBUTORS.md` 是同一份名单的另一处落地，而那边的 `NOTICE` 正指着
它（"Contributors are listed in CONTRIBUTORS.md"）。**版权行与维护者名单两处必须一致**
——漂了就有一处在说谎；`python/tests/test_contributors.py` 在能探到内核检出时逐字比对。
