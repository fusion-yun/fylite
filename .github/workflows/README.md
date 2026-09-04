# `.github/workflows/` —— 闸子在 CI 里怎么排班

★★**判据是「改了什么」，不是「提交了几次」。** 每个工作流按**路径**触发，只跑它
守的那一层；一次只动 `rust/` 的提交不跑 Python 档，一次只动文档的提交不编 Rust。
全量（含跨实现对拍与浏览器门）**每周一次**，外加两个人为入口。

| 工作流 | 什么时候跑 | 跑什么 | 量级 |
| :--- | :--- | :--- | :--- |
| `python.yml` | `python/**` · `cases/**` · `benchmark/**` · `docs/**` · `pyproject.toml` | Python 档全跑 + 三本册子的结构检查 | ~2 min |
| `rust.yml` | `rust/**` · `tools/dd-ids-table.py` | clippy + `cargo test` ×3 套特性 | ~5 min |
| `physics.yml` | `benchmark/physics/**` · `scenario/{physics,suite}.py` · `tools/benchmark-run.py` · `rust/fylite_runtime/**` | 数据层构建 + 物理校验批（能评的那条真跑） | ~4 min |
| `app.yml` | `app/**` · `tools/make-app-*.mjs` · `tools/app-pages/**` | 站点静态门（不需要浏览器与 wasm 的那几道） | ~1 min |
| `full.yml` | **每周一 03:00 UTC** · 手动 · 提交信息含 `[ci full]` | 以上全部 + imas-python / imas-core 跨实现对拍 | ~15 min |

★**跳过**：GitHub 原生认提交信息里的 `[skip ci]`。★**取消**：同一分支的新提交会
取消仍在跑的上一轮（`concurrency`），所以连续推送不会排队烧机器。

## 这里**不跑**什么，以及为什么

* **物理数值档**——它在内核仓，跟着它判的代码走（本仓 README「两个仓库」）。
* **要内核的那些**——`libfylite_kernel.so` 由私有仓构建。公开检出里它不在场，
  于是这一档按 `python/conftest.py` 的政策**点名跳过**（不是失败：缺输入与缺实现
  是两件事）。CI 的绿因此说的是「本仓自己的那一半成立」，不是「全都验过了」。
* **要浏览器或 wasm 的站点门**（31 道 Playwright + 几道读构建产物的）——它们要的
  制品同样来自私有仓；`app.yml` 只跑在干净检出里**真的能判**的那 6 道。
* **要私有语料的那些**（`tests/data` → fydoc 的 `oracle/`、EAST 帧夹具）——同上，
  不在场就跳过并点名。

★这张表**不是遗漏清单**：每一条都写明了判据在哪、由谁跑。一个把跑不了的东西
标成绿的 CI，比没有 CI 更坏。
