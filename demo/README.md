# Demo

- [kinetic_reconstruction](kinetic_reconstruction/README.md)：输入编辑、原生动理学反演、输出对比与独立 Python 调用（内部演示包）。

# Examples — rendered reconstructions

〔目录〕`east137985-recon-figure/` 等五个目录收 NFEC2026 海报算例的规格
（见下节）；`scripts/` 收一个自证式脚本。本文件其余部分记这些算例的溯源与诚实边界。

★这段原先还写着 `notebooks/`（七本 notebook）与 `scripts/{g,a}137985*`——**本仓一个
都没有**：这份 README 是从 `fylite_port` 抄过来的，指着另一棵树的内容。同一类缺陷
（README 说有、树里没有）也正是九个测试模块静默跳过的原因，所以现在的规则由测试
机检（`python/tests/test_examples_are_fyo.py`），不由本文件承诺。

## NFEC2026 海报算例（2026-08-20 立规格；2026-08-21 数据面重建，仍待实跑出图）

服务 fydoc `FYD-PAPER-03`（NFEC2026 张贴海报）的五个算例，每例一个目录，
README 载明目的、海报挂点、运行方式、输出规格（A0 可读字号）与诚实边界；
实跑产物出图后替换海报现图。

| 目录 | 内容 | 海报挂点 | 依赖 |
| :--- | :--- | :--- | :--- |
| ~~`east137985-recon-figure/`~~（已归档 [`archive/examples/east137985-recon-figure/`](../archive/examples/east137985-recon-figure/README.md)） | #137985 重构 4 面板海报级重渲染 | 图 2 替换 | 〔2026-09-13 随「彻底移除 est2」归档：输入是 est2 基的 CASE-22；待 efit_east 链算例重立〕 |
| ~~`recon-to-transport/`~~（已归档 [`archive/examples/recon-to-transport/`](../archive/examples/recon-to-transport/README.md)） | 重构平衡→输运自洽→实测剖面（闭环） | 新增图 | 〔同上〕 |
| [`zerod-metis/`](zerod-metis/README.md) | 0D 全放电 vs METIS 认证基线 | 图 5 替换（现为示意，**印前必换**） | 离线（fywork CASE-07 基线） |
| [`port-parity/`](port-parity/README.md) | NEO/TGLF 移植 parity 散点 | 新增小图 | 离线（oracle 夹具） |
| [`vv-gold-numbers/`](vv-gold-numbers/README.md) | V&V 金标数字表汇总 | V&V 栏数字溯源 | 离线 |

★**数据面已重建（2026-08-21）。** 本目录**只发布规格**：每个算例一份
`case.fyo.jsonld` + README，外加 `zerod-metis` 那一份不含装置与放电的建模基线。
#137985 的 g/a-file 与运行摘要（223 KB 中的 204 KB，与私有仓 `fylite_port` 逐位
相同的 EFIT 记录输出）已转为 fyo 文档并移出 `examples/`（2026-09-13 起在 `tests/data/FYDOC-CASE-22-east-137985-efit/`；同日随「彻底移除 est2」归档到 `archive/tests/data/FYDOC-CASE-22-east-137985-efit/`）
（`tools/case-to-fyo.py`）；对标答案由 `fylite_port` 离线产出，冻结在
`tests/data/oracle/`。规则由 `python/tests/test_examples_are_fyo.py` 机检，不靠约定。
判定与实测数字见
[`docs/note/port-oracle-examples.md`](../../fylite_dev/docs/note/port-oracle-examples.md)。

〔清单里的 `storage_uri` 只有两种合法形态〕**树内相对路径**（必须解析得到文件），
或 **`$VAR/相对路径` + `fylite:external": "VAR"`**（声明用哪个环境变量解析）。
第三种——既不在树里也不说怎么找——正是本仓吃过亏的那种：
`examples/scripts/g137985_loop.04000` 这个字面路径在本仓从来不存在，于是九个测试
模块**静默跳过**了好几个月。

| 入口 | 内容 |
| :--- | :--- |
| ~~`scripts/forward_equilibrium.py`~~（已归档 [`archive/examples/scripts/forward_equilibrium.py`](../archive/examples/scripts/forward_equilibrium.py)，2026-09-13 随「彻底移除 est2」） | 前向正解的自证式脚本（扫剖面 + 线圈归零对照）——输入取自 `tests/data/FYDOC-CASE-22-east-137985-efit/corpus/` 的 fyo 文档，答案经 `tests/data/oracle/` 重放 |

All artifacts are for **EAST shot 137985 @ 4.0 s** on the est2/GUI_v5 path with
**loops-only magnetics** (`FWTMP2 = 0` — the quality benchmark while per-channel
probe calibration is missing; gap K-4).

Data comes from the **MDSplus server** (`202.127.204.12`); the EASTCORPUS file
corpus is retired, so there is no local-file path.

## NEO self-consistent loop + diagnostic geometry (2026-07-31)

The current deliverable: the shot carried through the **EFIT↔NEO current loop**,
rendered as one figure that answers both *where the fitted diagnostics are* and
*what NEO actually returned*.

```python
lr = fylite.loop.self_consistent(
        137985, 4.0, point=True, pressure=True, thomson_ne=True,
        extra_namelist={"FWTMP2": [0.0] * 79},
        current_backend="neo", neo_resolution="fast",
        n_surfaces=16, max_iter=6, out=<dir>,
        final_uncertainty=16, uncertainty_seed=7)
fylite.plot.plot_reconstruction(
        lr["result"], lr["result"]["gfile"], "<dir>/recon.png",
        current=lr["current"], geometry=fylite.device_geometry(), neo=lr)
```

`final_uncertainty=N` re-runs the converged constraint through
`run(uncertainty=N)`, so the **same converged equilibrium** carries `errorbars`
(per-scalar 1σ + 16/50/84), `profiles` (q/pressure/n_e mean±σ bands) and
`diagnostics` (measured-vs-forward per family).

| File | What |
| :--- | :--- |
| `g137985_loop_errorbars.png` | the one-figure summary — flux map **with the 79 probes / 35 loops / 11 POINT chords drawn on it**, q/p/n_e ±1σ bands, the J_ohm/J_bs/J_tot decomposition, the **NEO bootstrap panel**, the four diagnostic families, and a geometry-provenance block |
| `g137985_loop.04000` / `a137985_loop.04000` | the converged g/a-file of the loop |
| `summary_137985_loop.json` | scalars + per-scalar σ + loop meta (converged, n_iter, backend, resolution, `profile_source`) + the raw NEO `jpar_dke` and its Sauter-1999/2021 baselines + the geometry channel counts |

Converged in **2 iterations**; posterior (n=16, seed=7, 16/16 converged):
**q0 0.783±0.0089, q95 3.08±0.011, Ip 393±1.4 kA, li 1.95±0.057,
βp 0.302±0.015, W_mhd 37.0±1.8 kJ, χ² 11.8±0.43**.  Two independent server
fetches reproduced these scalars digit-for-digit.  Against the earlier
single-fit kinetic combo (q0 0.706, li 2.11 — artifacts retired, see below) the
bootstrap-constrained current **raises q0 ≈11 % and lowers li ≈7 %**, the
direction expected when off-axis bootstrap current is imposed where the single
fit had none.

What the two newer panels say:

- **NEO bootstrap** — `jpar_dke` (drift-kinetic) against the Sauter-1999 and
  Redl-2021 coefficients *NEO itself* evaluated on the same surfaces, geometry,
  collisionality and normalization (`bootstrap_baseline.source =
  neo:jpar_sauter_2021`, i.e. the exported-coefficient path of K-19/K-21, not
  the Python transcription).  Sauter-1999 overshoots the kinetic solve by ≈30 %
  near the peak while Redl-2021 tracks it within a few percent — the reason the
  2021 set is the analytic default.
- **diagnostic geometry** — the flux map shows that this benchmark fits
  **0 of 79 probes** (`FWTMP2=0`) and **35 of 35 loops**.  Unweighted channels
  keep both their measurement and the forward prediction, drawn muted: with the
  probes out of the fit, that measured-vs-predicted scatter *is* the loops-only
  benchmark's evidence (G-04).

Honest caveats (tracked in the FYD-PORT-01-FYLITE gap register):

- `sigpre`/`sig19` use the **measured** per-point Thomson error
  (`\TE_CORETSERR`/`\NE_CORETSERR`) propagated, not a flat fraction; this is the
  honest σ, and it pushes `chi_pressure` to ≈1228 — the flat 20 % was *masking*
  a real pressure tension (fast-ion/Zeff, K-10);
- ion pressure uses the declared Ti-shape / n_i=n_e / no-fast-ion assumptions;
- no ASIPP kinetic-EFIT oracle exists for this shot (K-9): treat the numbers as
  self-consistent, not externally validated;
- the POINT n_e-line panel still shows the known measured-vs-forward offset.

## 前向自由边界正解 (2026-08-02) — FR-EQ-001

同一 GS 核的另一种驱动：`iconvr=3` 跳过外层拟合循环，给定 Ip、线圈电流与剖面，
让边界随线圈场浮动。本例**完全离线**——输入取自上面那次重构自己的 a-file，
不需要 MDSplus，也不需要参考样例包。

```bash
python examples/scripts/forward_equilibrium.py [outdir]
```

脚本不作断言、只作**实测**：先扫剖面参数，再做一次「线圈全部归零」的对照。
单次正解约 0.05 s，所以下面每一行都是可复跑的实验。

| 剖面 | 轴 R | 轴 Z | q0 | q95 | p′(0) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `betap0=0.30` | 1.8122 | −0.0036 | 1.2181 | 3.9813 | −2.413e+05 |
| `betap0=0.69` | 1.8269 | −0.0036 | 1.1767 | 3.9741 | −5.328e+05 |
| `betap0=1.50` | 1.8542 | −0.0036 | 1.0672 | 3.9497 | −1.034e+06 |
| `emp=2.0` | 1.8164 | −0.0023 | 0.7972 | 3.8136 | −5.525e+05 |
| `enp=2.0` | 1.8231 | −0.0051 | 1.6042 | 4.0701 | −2.987e+05 |

对照——12 个 PF 线圈电流全部归零：q0 1.1767→1.0141（−13.8 %）、
q95 3.9741→2.2383（−43.7 %）、边界 R 区间 [1.379, 2.225]→[1.625, 2.370] m。
**边界确实浮在线圈场上，这是一次货真价实的正解。**

**`chisq is None` 不是缺陷**：被跳过的正是那个拟合外层，报告拟合优度会是无意义的。
（这也正是判据：同一份 k-file 去掉 `ICONVR=3` 反而根本产不出 g-file。）

〔诚实边界——两条，都是量出来的〕

1. **可规定的剖面只有解析三参数**（`BETAP0`/`EMP`/`ENP`，即 `icurrt=4`）。
   p′/FF′ 的**多项式**通道在平衡模式下是惰性的：`KPPCUR`/`KFFCUR`、经
   `kefit_set_profile` 送达 `brsp(nfcoil+1…)` 的系数、以及 `CALPA`/`XALPA` +
   `CGAMA`/`XGAMA` 约束行全都不起作用——`ICURRT` 取 2 与 4 各配「有/无约束行」，
   四种组合给出**逐位相同**的平衡。机理：`currnt` 在 `nitett <= 1` 时绕过多项式解
   （`if ((nitett.le.1).and.(icinit.gt.0)) go to 3100`），而唯一压在该循环之上的
   `NXITER` 是**重读输入**的轮次而非 GS 迭代数（调大它会让 `&IN1` 读取直接报错）。
   故 `forward_equilibrium(pprime_coefs=…)` 现在**直接抛错**，不再静默无效。
2. **与上面那次重构的闭环检验不闭合**。把三个解析参数拟合到该炮自己的动理学重构，
   q0 能到 −2.6 %，但 q95 仍 +19 %、磁轴高 73 mm、边界逐点中位差 45 mm。
   瓶颈是**表达力而非数值**：三个解析参数无法复现一条在动理学压强与自举电流约束下
   拟合出来的 18 系数 p′/FF′。因此这个模式应当当作**独立的正向求解器**来用，
   而不是当作反演的往返自检。

## Retained as test fixtures, not as gallery output

`g137985.04000` / `a137985.04000` are the 2026-07-22 +POINT run, kept for two
reasons that have nothing to do with display:

- **ten test modules load the g-file** as their equilibrium fixture
  (`test_chords`, `test_redl`, `test_nbi`, `test_miller`, `test_lh`,
  `test_loop_neo_live`, `test_bootstrap_gate`, `test_current_sigma`,
  `test_versioning`, `test_inwant_weight`), and
  <!-- ★2026-09-08: `test_tomography` was here and is retired (its subject,
       `fylite.scenario.analysis.tomography`, sank into the kernel); the count
       went eleven → ten with it.  See `tests/PHYSICS-MIGRATION.md`. -->
  `test_pressure` / `test_provenance` use the a-file as the byte-level
  `geqdsk.read_afile` anchor (`tsaisq` 2.90, `qqmagx` 0.891);
- it is the repo's only **non-physical-pressure specimen**.  The converged loop
  equilibrium is physical (`n_nonphysical = 0`), so the K-22 fail-loud guards —
  `nonphysical_pressure_is_refused_by_default`,
  `pressure_health_counts_the_nonphysical_region`,
  `gfile_pressure_source_raises_on_nonphysical_pressure`,
  `synthetic_substitution_is_recorded_and_warned` — lose their subject if this
  file goes.  Substituting the loop g-file was tried: 9 tests fail.

Do not regenerate casually.

## Retired artifacts

| Removed | Date | Why |
| :--- | :--- | :--- |
| `g137985_point_4000ms.png`, `g137985_point_qp_profiles.png` | 2026-07-22 | flux map / qp profiles of the +POINT run — superseded by the loop figure's panels |
| `g137985_kinetic.04000`, `a137985_kinetic.04000`, `g137985_kinetic_4000ms.png`, `summary_137985_kinetic.json` | 2026-07-24 | the single-fit kinetic combo (q0 0.706, q95 3.05, χ² 11.2, βp 0.322, li 2.106, W_mhd 37.5 kJ); its numbers are kept above as the loop's comparison baseline |
| `g137985_reconstruction_errorbars.png`, `g137985_errorbars.04000`, `summary_137985_errorbars.json` | 2026-07-24 | superseded by the loop set — and the figure drew its probe panel from the *amplitude gate*, so a `FWTMP2=0` run read as constrained by 21 probes it never saw (fixed in `8c1780e`) |
| `g137985_recon_current.png`, `g137985_current_components.png` | — | orphans: documented nowhere, left over from earlier iterations of the one figure |
| `g137985_forward.04000`, `a137985_forward.04000`, `g137985_forward.png` | 2026-08-02 | 前向正解初版的产物，其"给定剖面"走的是**惰性的**多项式通道（见上节诚实边界 1），保留会误导；现示例全离线且 <1 s 可复跑，不再随仓携带产物 |

Regenerate (needs the EAST MDSplus server reachable):

```bash
cd ~/workspace/fylite
KEFIT_MDS_SERVER=202.127.204.12 PYTHONPATH=python:$PYTHONPATH python - <<'EOF'
# the loop figure via fylite.loop.self_consistent(..., final_uncertainty=16)
# + fylite.plot.plot_reconstruction(..., geometry=..., neo=...);
# standalone flux maps via fylite.plot.plot_gfile
EOF
```
