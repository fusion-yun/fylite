#!/usr/bin/env python3
"""Write the equilibrium register records that THIS checkout authors (2026-09-15), their reports, index rows and toc.

★★用户裁定 2026-09-15：「完善平衡相关 benchmark，不动 fylite_kernel」「废弃 libefit 对标，直接对标 KEFIT」。
The rest of the public register is rendered from the kernel's registry by the kernel's publisher; these records are
authored here instead, because their gates live here (``python/tests/test_benchmark_equilibrium.py`` and the three
residual-reading gates) and the kernel checkout is not to be touched.  The script is the single writer of what it adds,
so rerunning it gives the same bytes; each record says in its ``run.comment`` who wrote it.

    new        V-16  GS 残差读法（合并 C-06 · C-07 · B-10 的残差部分）
               V-17  定边界 GS 算子与求解器：Solov'ev 与制造解（门在内核检出，只读复测）
               B-12  EAST #137985 原始树输入：fylite 与 KEFIT 同一组数（取代 B-06 · B-11）
               B-14  自由边界正问题对 KEFIT：同一组线圈电流与 p′/FF′
               V-18  反演孪生体：已知真值（fylite 自己）
               B-15  反演孪生体：KEFIT 在同一份合成测量上
    changed    C-06 · C-07 · B-10 → retired, superseded_by V-16 ; B-06 · B-11 → superseded_by B-12 ;
               C-03 → a 2026-09-15 re-run finding (its gate skips since 2026-09-14) and the G-4 caveat
    ★2026-09-15 second batch (用户「补全 fixed-boundary 情景」; the kernel's `code/fixed_boundary` door):
               V-19  定边界：给定轮廓上的 Solov'ev 精确解（fylite 与 CHEASE）
               B-16  定边界对 CHEASE：EAST #137985 KEFIT ψ_N = 0.995 面上的同一问题
    ★2026-09-15 (/goal「完善磁平衡相关计算功能 … pf 导体线圈，导体壁等被动导体耦合」; the kernel's `code/evolve_free_boundary`):
               V-21  自由边界演化与 PF 电路 · 无源件耦合：EAST 卡片上的恒等式
               B-21  静态逆问题：同一目标形状下 fylite 的线圈设计对 FreeGSNKE 的反演解
               V-22  静态逆问题的第二个形状：ITER 参考分离面上的线圈设计（无参考侧，自洽判据）

    python tools/benchmark-equilibrium-records.py --reruns <reruns.json> --case $FYDOC_ORACLE/FYDOC-CASE-23-east-137985-efit-east \
        [--solovev <solovev_fixed_boundary.json from tools/benchmark-fixed-boundary.py solovev>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BM = ROOT / "docs" / "benchmark"
REG = BM / "registry.jsonld"
DATE = "2026-09-15"
CASE = "FYDOC-CASE-23-east-137985-efit-east"
#: 每条记录都带一条「本条写入时把门跑一遍」的 finding，`build()` 逐条取。缺哪一条就在
#: `apply()` 里停住——★新立的记录第一次写册时 registry 里还没有它，必须由 `--reruns` 给出。
NEED_RERUN = ("B-12", "B-14", "B-15", "B-16", "B-17", "B-18", "B-19", "B-20", "B-21", "C-03",
              "V-16", "V-17", "V-18", "V-19", "V-21", "V-22", "V-23")
PTR = f"$FYDOC_ORACLE/{CASE}/corpus/"
MD = "https://www.iana.org/assignments/media-types/text/markdown"
WRITER = ("本条由公开检出的 `tools/benchmark-equilibrium-records.py` 直写（2026-09-15，用户裁定「完善平衡相关 benchmark，"
          "不动 fylite_kernel」），不经内核仓的发布器；门在本检出里跑")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def crit(rid, n, label, basis, tol=None, norm=None, caveat=None, unit=None):
    c = {"id": f"record/{rid}/criterion/{n}", "type": "fyo:AcceptanceCriterion", "quantity_label": label}
    if norm:
        c["norm"] = norm
    if tol is not None:
        c["tolerance"] = {"type": "spo:QuantityValue", "numeric_value": tol}
        if unit:
            c["tolerance"]["has_unit"] = {"type": "spo:Unit", "ucum_code": unit}
    c["tolerance_basis"] = basis
    if caveat:
        c["caveat"] = caveat
    return c


def finding(title, verdict, literal=None, value=None, criterion=None, caveat=None, kind=None):
    f = {"type": "fyo:ComparisonFinding", "title": title}
    if kind:
        f["finding_kind"] = kind
    if literal is not None:
        f["deviation_literal"] = literal
    f["verdict"] = verdict
    if value is not None:
        f["measured_deviation"] = {"type": "spo:QuantityValue", "numeric_value": value}
    if criterion:
        f["criterion"] = criterion
    if caveat:
        f["caveat"] = caveat
    return f


def reruns_from_registry(reg: dict) -> dict:
    """上一次写册时记下的复测结果，自 registry 自己的 `re-run` finding 反读。

    ★★为什么要有它：``--reruns`` 是一份「把门跑一遍」的**实测**结果，而参考件
    （CHEASE · FreeGSNKE · KEFIT · efund · TokSys）在多数机器上不可得。没有这个
    反读，为了动一条记录就得替其余十五条**编造**复测结论——那是不能做的事。
    反读之后，没重跑的记录原样带回它上次那一条，**连标题里的日期一起带**。
    """
    out: dict[str, dict] = {}
    for r in reg.get("@graph", []):
        if r.get("type") != "fyo:ComparisonRecord":
            continue
        rid = r["id"].split("/", 1)[1]
        for f in r.get("findings", []):
            if f.get("finding_kind") == "re-run":
                out[rid] = {"verdict": f.get("verdict"), "literal": f.get("deviation_literal"),
                            "caveat": f.get("caveat"), "title": f.get("title"), "rid": rid, "carried": True}
                break
    return out


def rerun_finding(r: dict) -> dict:
    """「本条写入时把门跑一遍」的那条 finding。

    ★``carried`` 的一支是**没有重跑**的：标题连同它原来的日期一起带回，并在
    caveat 里写明本次沿用。把上一次的结果贴上今天的日期，是伪造复测。
    """
    if r.get("carried"):
        cav = list(r.get("caveat") or [])
        cav.insert(0, f"★本次写册**未重跑**本条：沿用上一次的复测结果，标题里的日期即那一次的日期。"
                      f"要重跑，把 `{r.get('rid', '<记录号>')}` 列进 `--only` 并在 `--reruns` 里给出本次实测。")
        return finding(r.get("title") or f"复测 {DATE}（本条写入时把门跑一遍）",
                       r["verdict"], r["literal"], kind="re-run", caveat=cav)
    #: ★实测的一支同样认 `title`：`DATE` 是写册日，不一定是跑门日。把门在 09-16 跑出的结果
    #: 贴上 09-15 的标题，读者看到的日期就是假的——这与 `carried` 那一支要防的是同一件事。
    return finding(r.get("title") or f"复测 {DATE}（本条写入时把门跑一遍）",
                   r["verdict"], r["literal"], kind="re-run", caveat=r.get("caveat"))


def gate(name, caveat=None):
    g = {"type": "spo:Code", "name": name}
    if caveat:
        g["caveat"] = caveat
    return g


def data(uri, license_, checksum=None, caveat=None):
    d = {"type": "spo:Concretization", "storage_uri": uri, "provenance_class": "registered", "quality_state": "valid",
         "license": license_}
    if checksum:
        d["checksum"] = f"sha256:{checksum}"
    if caveat:
        d["caveat"] = caveat
    return d


def record(rid, title, kind, subject, reference, criteria, findings, gates, inputs, report, caveat, verdict,
           validity=None, state="accepted"):
    r = {"id": f"record/{rid}", "type": "fyo:ComparisonRecord", "title": title, "comparison_kind": kind,
         "compared_subject": {"type": "spo:Code", "name": "fylite", "comment": subject},
         "compared_reference": reference, "criteria": criteria, "findings": findings,
         "run": {"type": "spo:ComputationalProcess", "recorded": DATE, "realizes": gates, "has_input": inputs, "comment": WRITER},
         "account": {"type": "spo:Concretization", "storage_uri": f"$FYDOC_ORACLE/{CASE}/{CASE}.md", "format_iri": MD,
                     "caveat": ["完整账在 fydoc 算例书 CASE-23 书页（internal）；公开侧的结构化摘要见 report"]},
         "report": {"type": "spo:Concretization", "storage_uri": f"reports/{report}", "format_iri": MD},
         "caveat": caveat, "assertion_state": state, "overall_verdict": verdict}
    if validity:
        r["validity_domain"] = validity
    return r


KEFIT_REF = {"type": "spo:Code", "name": "KEFIT",
             "version": "kefit_reference_bundle（third_party，锁定件）active/point/efit_w_pf，gfortran 64 位本地构建（magpri 76；构建配方 CASE-23 corpus/kefit/kefit_build_recipe.json）",
             "license": "private-artefact"}
KEFIT_CAVEAT_BUILD = "KEFIT 的可执行体不入仓：由构建配方与源 sha256 重建；门只回放已记录、sha256 索引过的运行件，不重跑 KEFIT"


# ------------------------------------------------------------------------------------------------ records

def build(case: Path, reruns: dict, solovev: dict) -> tuple[list[dict], dict[str, str]]:
    import yaml
    sums = yaml.safe_load((case / "case.yaml").read_text(encoding="utf-8"))["data"]["checksums"]
    fk = json.loads((case / "corpus/benchmark/forward_kefit_east137985.json").read_text(encoding="utf-8"))["cases"]
    tw = json.loads((case / "corpus/benchmark/twin_east137985.json").read_text(encoding="utf-8"))
    rd = json.loads((case / "corpus/benchmark/comparison_readings_east137985.fyo.jsonld").read_text(encoding="utf-8"))
    raw = next(t for t in rd["fylite:tiers"] if t.get("@id") == "#R-raw-trees")
    gate_mod = (ROOT / "python/tests/test_benchmark_equilibrium.py").read_text(encoding="utf-8")
    bands = {k: json.loads(re.search(rf"^{k} = (\{{.*\}})$", gate_mod, re.M).group(1)) for k in ("B14_BAND", "V18_BAND", "B15_BAND")}
    recs, reports = [], {}
    T = "python/tests/test_benchmark_equilibrium.py"

    # ---------------------------------------------------------------- V-16
    reg = json.loads(REG.read_text(encoding="utf-8"))
    old = {r["id"]: r for r in reg["@graph"]}
    carried = []
    for rid in ("record/C-06", "record/C-07", "record/B-10"):
        for f in old[rid]["findings"]:
            if str(f.get("finding_kind", "")).startswith("re-run"):
                continue
            g = dict(f)
            g["title"] = f"〔{rid.split('/')[1]}〕" + g["title"]
            g.pop("criterion", None)
            carried.append(g)
    v16_crit = [
        crit("V-16", 1, "GS 残差（Δ*ψ − RHS，边界内内点），TEQ / CORSICA 三份 ITER 参考平衡，**MR 129×257 与 HR 257×513**", "measured_band", 0.02, "relative",
             ["原 C-06 的判据；带绑定分辨率，LR 65×129 不在带内（残差随网格只掉一阶）"]),
        crit("V-16", 2, "GS 残差，TOSCA 2009 批 li 扫描 61 份（65×129）", "measured_band", 0.06, "relative", ["原 C-07 的判据；残差随 li 成台阶"]),
        crit("V-16", 3, "GS 残差，CHEASE `ntcase=2`，**输出盒 201×129 · 默认内部网格**", "measured_band", 0.08, "relative",
             ["原 B-10 的判据；输出盒与内部网格两个分辨率都点名"]),
        crit("V-16", 4, "口径：从数里读出的 COCOS 对文件自述（三组语料）", "machine_precision",
             caveat=["一条恒等式或离散标签的判定；COCOS 的读写往返另在 V-15"]),
    ]
    recs.append(record(
        "V-16", "GS 残差读法：外部平衡集上，本仓的判据读出什么（合并 C-06 · C-07 · B-10 的残差部分）", "verification",
        "fylite: g-file 读入端 + GS 残差判据（Δ*ψ − RHS）+ COCOS 口径测量（measure_cocos）",
        [{"type": "spo:Code", "name": "TEQ / CORSICA", "version": "ITER IDM 参考平衡件（首行 `TEQ g 04/07/2010`）", "license": "restricted"},
         {"type": "spo:Code", "name": "TOSCA", "version": "ITER IDM 2009 批运行空间（61 份 EQDSK）", "license": "restricted"},
         {"type": "spo:Code", "name": "CHEASE", "version": "本机构建，`ntcase=2` 随码算例", "license": "public"}],
        v16_crit,
        carried + [rerun_finding(reruns["V-16"])],
        [gate("python/tests/test_teq_equilibria.py"), gate("python/tests/test_tosca_equilibria.py"), gate("python/tests/test_chease_equilibrium.py")],
        [data("$ITER_SCENARIO_ROOT/（TEQ 四份与 TOSCA 两份 ITER IDM 文档）", "restricted",
              caveat=["受限件只存指针；逐件 sha256 在门的语料清单里（ITER IDM Internal Use）"]),
         data("$THIRD_PARTY/chease（本机构建；`ntcase=2` 随码算例）", "public", caveat=["参考侧由码自己产生，可复算；不涉及 sha256 冻结件"])],
        "V-16-gs-residual-reading.md",
        ["★★类别改判：原 C-06 / C-07 标 C（确认）、B-10 标 B（对拍），可三条的门问的都是「本仓的残差判据在别人写出的平衡上读出什么」——参考是那份文件，不是另一套模型对同一状态的答案；按 README「类别由参考是什么决定」，这是 V（判据本身）",
         "★**本条不验证 fylite 的 GS 求解器**：三组语料都不是 fylite 解出来的。求解器的验证在 V-17（解析 / 制造解）与 B-14（对 KEFIT 的正问题）",
         "★B-10 原题「同一边界与剖面下的 GS 解」与门不符（门没有让 fylite 求解）；由 fylite 自己在给定边界上求解的对拍 2026-09-15 由 V-19（Solov'ev，与 CHEASE 同轮廓）与 B-16（EAST 形状对 CHEASE）立——内核当日新增树门 code/fixed_boundary",
         "纳入类别（参考数据）：restricted、public"],
        "pass"))
    reports["V-16"] = "V-16-gs-residual-reading.md"

    # ---------------------------------------------------------------- V-17
    kn = "私仓的门：内核检出中 `pytest tests/…`（只读复测：不写字节码、不写缓存、不改文件）"
    recs.append(record(
        "V-17", "定边界 GS 算子与求解器：Solov'ev 精确解与制造解", "verification",
        "fylite: 内核 equilibrium.rs 的 Δ* 算子、Hockney 快速直接解法与定边界 Picard 迭代（经 C-ABI）",
        [{"type": "spo:Code", "name": "Solov'ev 解析解", "version": "ψ = (f/8) R⁴ + (g/2) Z² + c₂ R²（公开闭式）", "license": "public"}],
        [crit("V-17", 1, "Solov'ev 精确解经 C-ABI 重现", "machine_precision", caveat=["解析解：本条是 verification，机器精度即判据"]),
         crit("V-17", 2, "Δ* 算子作用于 Solov'ev 解给出其源项", "machine_precision"),
         crit("V-17", 3, "内核单元测试：Solov'ev 误差 33² 网格 < 1e-10、65² < 1e-9；制造解二阶收敛；算子与解法互逆；定边界 Picard 收敛并如实报告",
              "machine_precision", caveat=["这几条是内核 `cargo test` 的断言（`equilibrium.rs` 单元测试），阈值照录断言本身，本条未另测数值"])],
        [finding("Solov'ev 经 C-ABI（`test_rust_kernels.py::test_solovev_is_reproduced_through_the_abi`）", "pass", "门通过（2026-09-15 只读复测）", criterion="record/V-17/criterion/1"),
         finding("Δ* 作用于 Solov'ev（`test_oracle_marshalling.py::test_the_deltastar_operator_returns_the_solovev_source`）", "pass", "门通过（2026-09-15 只读复测）", criterion="record/V-17/criterion/2"),
         finding("内核 Rust 单元测试（`solovev_is_reproduced_to_machine_precision` · `manufactured_solution_converges_at_second_order` · `stencil_and_solver_are_mutually_inverse` · `fixed_boundary_picard_converges_and_reports_it`）",
                 "unevaluated", "本条写入时未跑：`cargo test` 会在内核检出里构建，而本轮裁定不动内核仓", criterion="record/V-17/criterion/3"),
         rerun_finding(reruns["V-17"])],
        [gate("$FYLITE_KERNEL/tests/test_rust_kernels.py::test_solovev_is_reproduced_through_the_abi", [kn]),
         gate("$FYLITE_KERNEL/tests/test_oracle_marshalling.py::test_the_deltastar_operator_returns_the_solovev_source", [kn]),
         gate("$FYLITE_KERNEL/rust/fylite/src/equilibrium.rs", ["私仓的门：`cargo test -p fylite equilibrium::`；本条写入时未跑（不在内核检出里构建）"])],
        [], "V-17-solovev-manufactured.md",
        ["★这是 S1 干路上第一条**针对求解器本身**的登记记录：此前平衡正问题的 V 只在内核单元测试里，公开册看不见",
         "★只覆盖定边界与解析 / 制造解；自由边界正问题的外部对照在 B-14", "纳入类别（参考数据）：public（解析闭式）"],
        "pass"))
    reports["V-17"] = "V-17-solovev-manufactured.md"

    # ---------------------------------------------------------------- B-12
    rej = raw["fylite:variants"]["rejected"]["slices"]
    allp = raw["fylite:variants"]["all_probes"]["slices"]
    f12 = []
    for key in ("4.041", "4.944", "5.976"):
        e = rej[key]
        M, K = e["fylite_M"], e["kefit"]["mag"]
        f12.append(finding(f"{key} s 纯磁（剔 7 探针）：fylite 对 KEFIT", "inconclusive",
                           f"q₀ {M['q0']:.3f} 对 {K['q0']:.3f} · q₉₅ {M['q95']:.2f} 对 {K['q95']:.2f} · 磁轴对 efit_east 答案 dR {M['dR_mm']:+.1f} 对 {K['dR_mm']:+.1f} mm · "
                           f"边界中位 {M['boundary_seg_median_mm']:.1f} 对 {K['boundary_seg_median_mm']:.1f} mm · χ² {M['chi2']:.1f} 对 {K['chi2_last_iteration']:.1f}（两边都收敛；KEFIT 无错误标记）",
                           caveat=["efit_east 的答案只作比较参照（用户裁定 2026-09-15），不是本条的参考"]))
    f12 += [
        finding("全部探针：两个代码都拟不上", "fail",
                "fylite 纯磁 χ² " + " / ".join(f"{allp[k]['fylite_M']['chi2']:.0f}" for k in ("4.041", "4.944", "5.976")) +
                " · KEFIT " + " / ".join(f"{allp[k]['kefit']['mag']['chi2_last_iteration']:.0f}" for k in ("4.041", "4.944", "5.976")) + "（Error #1）",
                caveat=["同一批不自洽通道：KEFIT 纯磁 χ² 份额 HBPH1T 883 · HBPD10T 169 · HBPH2T 64 · HBPH1N 56 · HBPD10N 51 · HBPD8T 37 · HBPH3T 25，同一份剔除交给两个代码（读自拟合本身）"]),
        finding("加 POINT：两个代码都不稳", "inconclusive",
                "fylite 主集 q₀ " + " / ".join(f"{rej[k]['fylite_K_primary']['W4c']['q0']:.2f}" for k in ("4.041", "4.944", "5.976")) +
                " · KEFIT 4.041 s `Problem in CNTOUR`、4.944 s 带 Error #19–21、5.976 s q₀ " + f"{rej['5.976']['kefit']['primary']['q0']:.2f}",
                caveat=["原始输入上的档 K 没有可作参考的答案"]),
        finding("KEFIT 几何：GUI_v5 自带表 green2018_wpf_64 不是原始探针名读的道阵", "pass",
                "按位置与角度配对，79 槽中 56 对差 > 2 cm / 10°；改 green2022_pcs：76 槽中 74 槽 0 mm / 0° 重合",
                caveat=["这是 2026-09-14 GUI 原配方各例 `Problem in BOUND` 的原因"]),
        rerun_finding(reruns["B-12"])]
    c12 = [crit("B-12", 1, "同一组原始树输入上两个代码的纯磁读数（q₀ · q₉₅ · 磁轴 · 边界 · χ²）", "measured_band",
                caveat=["**不判、无带**：两个代码仍有三处实现差（KEFIT 拟合 PF 电流而 fylite 固定实测值、竖直位置的处理、边缘系数），本组分不开"])]
    recs.append(record(
        "B-12", "EAST #137985 原始树输入：fylite 与 KEFIT 在同一组数上（取代 B-06 · B-11）", "benchmark",
        "fylite: code/reconstruction（纯磁，竖直设定点扫描）与 W4b / W4c（POINT 法拉第行）经树门；输入经 fylite.io.raw.reduce_series 读原始树",
        [KEFIT_REF], c12, f12,
        [gate(f"{T}::test_b12_the_raw_tree_readings_are_the_registered_ones"),
         gate("$FYLITE_KERNEL/tools/benchmark-east-raw.py", ["私仓工具：产出本条读数（--pull · --fylite · --kefit · --reject · --compare）；本条写入时未重跑，门只核读数与归档的 sha256"])],
        [data(PTR + "raw/raw_slices_east137985.json", "experiment", sums["raw/raw_slices_east137985.json"], ["实验数据：原始树读数，只存指针"]),
         data(PTR + "kefit/kefit_raw_east137985.tar.gz", "experiment", sums["kefit/kefit_raw_east137985.tar.gz"], [KEFIT_CAVEAT_BUILD]),
         data(PTR + "fylite/fylite_raw_east137985.tar.gz", "experiment", sums["fylite/fylite_raw_east137985.tar.gz"]),
         data(PTR + "benchmark/comparison_readings_east137985.fyo.jsonld", "experiment",
              sums["benchmark/comparison_readings_east137985.fyo.jsonld"], ["读数块 `#R-raw-trees`"])],
        "B-12-east-raw-trees-kefit.md",
        ["★★取代 B-06（est2 测量集，2026-09-13 撤回）与 B-11（efit_east 树的输入，2026-09-15 撤回）：同一个对象（EAST #137985 的平衡反演），换成原始树输入，参考换成 KEFIT",
         "★所有进入反演的数都读自 east / pcs_east 原始树；efit_east 的答案只作比较（用户裁定 2026-09-15）", "纳入类别（参考数据）：experiment"],
        "inconclusive",
        validity="EAST #137985 @ 4.041 / 4.944 / 5.976 s；east 测量链（east_new 卡片）；同一份 7 探针剔除；两个代码同一组数的读数，不作判定"))
    reports["B-12"] = "B-12-east-raw-trees-kefit.md"

    # ---------------------------------------------------------------- B-14
    b = bands["B14_BAND"]
    c14 = [crit("B-14", 1, "磁轴距离（三片纯磁）", "measured_band", b["axis_mm"], "absolute", unit="mm"),
           crit("B-14", 2, "极向通量跨度 |ψ_b − ψ_a| 的相对差", "measured_band", b["span_abs"], "relative"),
           crit("B-14", 3, "KEFIT 边界内 ψ_N 差 rms / 最大", "measured_band", b["psin_rms"], "absolute",
                [f"最大值另带 {b['psin_max']}"]),
           crit("B-14", 4, "KEFIT 边界点到 fylite ψ_N = 1 等值线的距离：中位 / 最大", "measured_band", b["boundary_median_mm"], "absolute",
                [f"最大值另带 {b['boundary_max_mm']} mm"], "mm"),
           crit("B-14", 5, "下 X 点距离", "measured_band", b["xpoint_mm"], "absolute", unit="mm"),
           crit("B-14", 6, "Ip（两边都是等式约束）", "machine_precision", caveat=["★这是嵌在对拍记录里的一句 **verification** 断言：两个代码都以 Ip 为等式，判的是一条恒等式，不含可被物理带覆盖的建模差"])]
    f14 = []
    for name in ("t4041_mag", "t4944_mag", "t5976_mag"):
        c = fk[name]["compare"]
        f14.append(finding(f"{name[1]}.{name[2:5]} s 纯磁答案", "pass",
                           f"磁轴 {math.hypot(c['dR_axis_mm'], c['dZ_axis_mm']):.2f} mm · 跨度 {100 * c['span_rel']:+.3f} % · ψ_N rms {100 * c['psin_rms_inside']:.2f} % / 最大 {100 * c['psin_max_inside']:.2f} % · "
                           f"边界 {c['boundary_median_mm']:.2f} / {c['boundary_max_mm']:.1f} mm · X 点 {c['xpoint_dist_mm']:.1f} mm"))
    c = fk["t5976_primary"]["compare"]
    f14 += [finding("5.976 s 带 POINT 约束的剖面：出带", "inconclusive",
                    f"磁轴 {math.hypot(c['dR_axis_mm'], c['dZ_axis_mm']):.1f} mm · 跨度 {100 * c['span_rel']:+.2f} % · ψ_N rms {100 * c['psin_rms_inside']:.2f} % · 边界 {c['boundary_median_mm']:.1f} / {c['boundary_max_mm']:.0f} mm · 600 步未定",
                    caveat=["不进带；门把「出带」本身钉住，免得它悄悄变好或变坏"]),
            finding("收敛：fylite 的自由边界迭代在纯磁三例上「settled」而非「converged」", "inconclusive",
                    "残差 " + " / ".join(f"{fk[n]['fylite']['residual']:.1e}" for n in ("t4041_mag", "t4944_mag", "t5976_mag")) + "，约 62 步因掩膜稳定而停；缺省 tol 1e-9",
                    caveat=["带是在这一停止状态上量的；收紧停止判据是否移动这些数未测 [TBD]"]),
            rerun_finding(reruns["B-14"])]
    recs.append(record(
        "B-14", "自由边界正问题对 KEFIT：同一组线圈电流与 p′/FF′ 下的 GS 解", "benchmark",
        "fylite: code/forward（剖面表分支）经树门；EAST 卡片 65×65 盒，与 KEFIT green2022_pcs 表同一网格",
        [KEFIT_REF],
        c14, f14,
        [gate(f"{T}::test_b14_the_forward_solve_reproduces_its_recorded_readings"),
         gate(f"{T}::test_b14_the_forward_solve_stays_in_the_band_on_kefits_magnetics_answers"),
         gate(f"{T}::test_b14_the_point_profile_slice_is_recorded_outside_the_band")],
        [data(PTR + "kefit/kefit_raw_east137985.tar.gz", "experiment", sums["kefit/kefit_raw_east137985.tar.gz"],
              ["KEFIT 在原始树输入上收敛的答案（变体 rejected）：a-file CCBRSP · g-file PPRIME / FFPRIM / Ip", KEFIT_CAVEAT_BUILD]),
         data(PTR + "benchmark/forward_kefit_east137985.json", "experiment", sums["benchmark/forward_kefit_east137985.json"])],
        "B-14-forward-kefit.md",
        ["★★取代计划中的 libefit 对标（用户裁定 2026-09-15：废弃 libefit，直接对标 KEFIT）",
         "★同一组输入：KEFIT 拟合出的 12 路线圈安匝、它的 p′(ψ_N) 与 FF′(ψ_N)、它的 Ip；两边剩下的只有 GS 求解（网格、边界搜索、自由边界迭代）",
         "★口径：KEFIT 的 ψ 每弧度、轴处取极小；fylite 整圈、轴处取极大——ψ_fy = −2π ψ_KEFIT，p′ 与 FF′ 同除 −2π（由 g-file 的 simag < sibry 读出，不假设）",
         "纳入类别（参考数据）：experiment、private-artefact"],
        "pass",
        validity="EAST 几何（east_new 卡片 / green2022_pcs，65×65 盒）；KEFIT 在 #137985 原始树输入上的纯磁答案；带 POINT 约束的剖面不在带内"))
    reports["B-14"] = "B-14-forward-kefit.md"

    # ---------------------------------------------------------------- V-18 / B-15
    tf = tw["truth"]["facts"]

    def twin_crits(rid, band, kind):
        return [crit(rid, 1, "q₀ / q₉₅ 相对差", "measured_band", band["q0_abs"], "relative", [f"q₉₅ 另带 {band['q95_abs']}"]),
                crit(rid, 2, "磁轴距离", "measured_band", band["axis_mm"], "absolute", unit="mm"),
                crit(rid, 3, "ψ_N 差 rms / 最大（真值边界内）", "measured_band", band["psin_rms"], "absolute", [f"最大值另带 {band['psin_max']}"]),
                crit(rid, 4, "边界距离中位 / 最大", "measured_band", band["boundary_median_mm"], "absolute", [f"最大值另带 {band['boundary_max_mm']} mm"], "mm"),
                crit(rid, 5, "下 X 点距离 · 通量跨度 · Ip", "measured_band", band["xpoint_mm"], "absolute",
                     [f"跨度带 {band['span_abs']} · Ip 带 {band['ip_abs']}"], "mm")]

    def twin_find(side, tag):
        c = side["compare"]
        return finding(f"{tag}：孪生体 4.041 s", "pass",
                       f"q₀ {100 * side['q0_rel']:+.2f} % · q₉₅ {100 * side['q95_rel']:+.2f} % · 磁轴 {c['dR_axis_mm']:+.2f} / {c['dZ_axis_mm']:+.2f} mm · ψ_N rms {100 * c['psin_rms_inside']:.2f} % · "
                       f"边界 {c['boundary_median_mm']:.2f} / {c['boundary_max_mm']:.2f} mm · X 点 {c['xpoint_dist_mm']:.2f} mm · 跨度 {100 * c['span_rel']:+.3f} % · Ip {100 * c['ip_rel']:+.3f} %")

    truth_caveat = [f"真值：code/forward 解析族 β₀ {tw['truth']['settings']['beta0']} · e_mp = e_np = 1（p′ 与 FF′ 线性、边缘为零）；磁轴 ({tf['axis_r']:.3f}, {tf['axis_z']:+.3f}) m · q₀ {tf['q0']:.3f} · q₉₅ {tf['q95']:.2f}",
                    "线圈电流与 Ip 取 #137985 4.041 s 原始树读数（实验数据，只作驱动；测量值本身不进公开册）", "测量是模型输出：75 个磁通环（等离子体份额 + code/coilshare 线圈份额）· 79 个探针；无噪声"]
    fy = tw["fylite"]
    recs.append(record(
        "V-18", "反演孪生体（已知真值）：fylite 从自己正问题的合成测量反演回真值", "verification",
        "fylite: code/forward（真值与合成诊断）→ code/reconstruction（npp = nff = 1，竖直设定点扫描）经树门",
        [{"type": "spo:Code", "name": "fylite code/forward 的真值", "version": "解析族 e_mp = e_np = 1，EAST east_new 卡片", "license": "experiment"}],
        twin_crits("V-18", bands["V18_BAND"], "verification") ,
        [twin_find(fy, "fylite 反演"),
         finding("设定点扫描", "pass", f"−30 … +30 mm 每 4 mm；χ² 极小在 {1e3 * fy['zc_anchor_m']:+.0f} mm（χ² {fy['chi2']:.2f}），真值竖直位置 {1e3 * tf['zc']:+.1f} mm"),
         rerun_finding(reruns["V-18"])],
        [gate(f"{T}::test_v18_fylite_recovers_the_twin_truth_and_reproduces_its_readings")],
        [data(PTR + "benchmark/twin_east137985.json", "experiment", sums["benchmark/twin_east137985.json"], truth_caveat),
         data(PTR + "raw/raw_slices_east137985.json", "experiment", sums["raw/raw_slices_east137985.json"], ["线圈电流与 Ip 的来源"])],
        "V-18-twin-reconstruction.md",
        ["★类是 V、带是实测带而非机器精度，理由三条：真值的自由边界迭代停在「settled」（残差 2e-4）；竖直设定点按 4 mm 步长扫描；线圈份额在正问题里是 4×4 细丝、在 code/coilshare 里是另一套求积——三者都给出非零但可复现的差",
         "★真值在两个代码的基里都可精确表示（线性、边缘为零），所以剩下的差不是基的截断", "纳入类别（参考数据）：experiment"],
        "pass"))
    reports["V-18"] = "V-18-twin-reconstruction.md"
    ke = tw["kefit"]
    recs.append(record(
        "B-15", "反演孪生体（已知真值）：KEFIT 在同一份合成测量上", "benchmark",
        "fylite: code/forward 给出真值与合成测量（被比的是 KEFIT 对真值的偏差，与 V-18 的 fylite 偏差并列）",
        [KEFIT_REF],
        twin_crits("B-15", bands["B15_BAND"], "benchmark"),
        [twin_find(ke, "KEFIT 反演（无错误标记）"),
         finding("KEFIT 的输入配方", "pass",
                 f"KPPCUR = KFFCUR = 2、pcurbd = fcurbd = 1（与真值同基）；green2022_pcs 几何，76 槽中 74 槽按位置与角度配到卡片探针，槽 {ke['unmatched_kefit_slots']} 权重 0；35 环取 FL1B–FL35B；σ = max(0.05 |值|, bit)；FWTFC 0.3 拟合线圈、bitip 40000 拟合 Ip、fitdelz",
                 caveat=["q₀ 的 −4.9 % 是本条最大的差；Ip 的 −0.25 % 来自 KEFIT 把 Ip 当带权测量而非等式"]),
         rerun_finding(reruns["B-15"])],
        [gate(f"{T}::test_b15_kefit_on_the_twin_measurements_stays_in_its_band")],
        [data(PTR + "kefit/kefit_twin_east137985.tar.gz", "experiment", sums["kefit/kefit_twin_east137985.tar.gz"],
              ["KEFIT 孪生体运行件：namelist · g / a-file · fitout · 槽配对表", KEFIT_CAVEAT_BUILD]),
         data(PTR + "benchmark/twin_east137985.json", "experiment", sums["benchmark/twin_east137985.json"], truth_caveat)],
        "B-15-twin-kefit.md",
        ["★与 V-18 同一份合成测量、同一个真值：两个代码谁偏、偏多少并列可读", "纳入类别（参考数据）：experiment、private-artefact"],
        "pass"))
    reports["B-15"] = "B-15-twin-kefit.md"

    # ---------------------------------------------------------------- V-19 / B-16 (fixed boundary)
    fb_gate = consts(ROOT / "python/tests/test_benchmark_fixed_boundary.py", ("V19_FYLITE_129", "V19_CHEASE_80", "B16_BAND", "V19_ORDER_RATIO"))
    TF = "python/tests/test_benchmark_fixed_boundary.py"
    sv = solovev
    chease_ref = {"type": "spo:Code", "name": "CHEASE",
                  "version": "third_party/chease 本机 gfortran 构建；EXPEQ 输入（NSURF = 6 · NPPFUN = NFUNC = 4 · NSTTP = 1 · NCSCAL = 2），NS = NT = 80（另 40 作分辨率读数）",
                  "license": "public"}
    fb_conv = ("★口径（在 Solov'ev 算例上实测，不假设）：fylite 取整圈 Wb 的 p′ / FF′、轴处取极大；CHEASE 的 EXPEQ 取 −μ0 R0² / B0 · 2π p′ 与 −2π FF′ / B0，"
               "横轴 √ψ_N，轮廓以 R0EXP 为单位，边缘 T = 1（B0EXP = F_edge / R0EXP），CURRT = μ0 Ip / (R0EXP B0EXP)；符号取反则 CHEASE 不收敛")
    kernel_gate = gate("$FYLITE_KERNEL/rust/fylite/src/fixedbnd.rs::tests · case.rs::fixed_boundary_tests",
                       ["私仓的门：`cargo test --release --lib -- fixedbnd fixed_boundary_tests`（7 条；Solov'ev 二阶收敛 · Ip 对轮廓安培定律 · 电流目标线性缩放 · 门即模块 · q₀ 与 p₀ 闭式 · 拒绝语）",
                        "本条写入时在内核检出里跑过：7 passed（2026-09-15）"])
    f129 = sv["fylite"]["n129"]
    c129, cc80 = f129["compare"], sv["chease"]["ns80"]["compare"]
    b = fb_gate["V19_FYLITE_129"]
    v19_crit = [crit("V-19", 1, "fylite 129²：ψ_N 差 rms / 最大（轮廓内 121×201 点阵），对精确解", "measured_band", b["psin_rms"], "absolute", [f"最大值另带 {b['psin_max']}"]),
                crit("V-19", 2, "fylite 节点误差 max|Δψ| / ψ_c（整格在轮廓内的节点）与二阶收敛", "measured_band", b["node_error"], "relative",
                     [f"65² → 129² 的误差比须大于 {fb_gate['V19_ORDER_RATIO']}"]),
                crit("V-19", 3, "fylite 129²：Ip 对精确轮廓上的安培定律 · 通量跨度", "measured_band", b["ip_rel"], "relative", [f"跨度另带 {b['span_rel']}"]),
                crit("V-19", 4, "fylite 129²：磁轴距离 · 轮廓离 ψ = 0 面的最大距离", "measured_band", b["axis_mm"], "absolute", [f"轮廓距离另带 {b['gap_max_m']} m"], "mm"),
                crit("V-19", 5, "fylite 129²：q₀ 对局部展开闭式", "measured_band", b["q0_rel"], "relative", ["q₀ 是最内一对被追踪面外推到轴（`q_profile` 的约定），不是轴上的值"]),
                crit("V-19", 6, "CHEASE NS 80：ψ_N rms · 磁轴 · 跨度 · Ip · q₀，对精确解", "measured_band", fb_gate["V19_CHEASE_80"]["psin_rms"], "absolute",
                     [f"带 {json.dumps(fb_gate['V19_CHEASE_80'])}；第二个代码在同一问题上，不是 fylite 的参考"])]
    ne = [sv["fylite"][f"n{n}"]["node_error"] for n in (33, 65, 129)]
    fvc = sv["fylite_129_vs_chease_ns80"]
    v19_find = [finding("fylite 129² 对精确解", "pass",
                        f"ψ_N rms {c129['psin_rms']:.2e} · 最大 {c129['psin_max']:.2e} · 磁轴 {c129['axis_mm']:.3f} mm · 跨度 {c129['span_rel']:+.2e} · Ip {c129['ip_rel']:+.2e} · q₀ {100 * c129['q0_rel']:+.2f} % · "
                        f"轮廓距离最大 {f129['facts']['gap_max']:.1e} m · {f129['facts']['iterations']:.0f} 步收敛"),
                finding("收敛阶", "pass", f"节点误差 33² {ne[0]:.2e} · 65² {ne[1]:.2e} · 129² {ne[2]:.2e}（比 {ne[0] / ne[1]:.1f} · {ne[1] / ne[2]:.1f}）"),
                finding("CHEASE NS 80 对精确解", "pass",
                        f"ψ_N rms {cc80['psin_rms']:.2e} · 最大 {cc80['psin_max']:.2e} · 跨度 {cc80['span_rel']:+.1e} · Ip {cc80['ip_rel']:+.1e} · q₀ {cc80['q0_rel']:+.1e}"),
                finding("fylite 129² 对 CHEASE NS 80（读数）", "inconclusive",
                        f"ψ_N rms {fvc['psin_rms']:.2e} · q（ψ_N 0.1–0.9）rms {100 * fvc['q_rel_rms_01_09']:.3f} % · 最大 {100 * fvc['q_rel_max_01_09']:.3f} % · q₉₅ {100 * fvc['q95_rel']:+.3f} %",
                        caveat=["两个代码都对着精确解判过，彼此的差只作读数"]),
                rerun_finding(reruns["V-19"])]
    recs.append(record(
        "V-19", "定边界 GS：给定轮廓上的 Solov'ev 精确解（fylite code/fixed_boundary 与 CHEASE）", "verification",
        "fylite: code/fixed_boundary 经树门（内核 fixedbnd：轮廓外 64 根细丝的基本解法在 256 个配点上把 ψ = 0 钉在轮廓上；等离子体自身磁通由盒边自由空间格林函数给出；被轮廓切开的网格按面积分数计源）",
        [{"type": "spo:Code", "name": "Solov'ev 解析解",
          "version": f"ψ = ψ_c − e₁(R² − r₀²)² − e₂R²Z² − e₃Z²（r₀ {sv['problem']['r0']} m · e₁ {sv['problem']['e1']} · e₂ {sv['problem']['e2']:.6f} · e₃ {sv['problem']['e3']} · κ 1.7 · 外缘 2.25 m），常数 p′ 与 FF′；Ip 由精确轮廓上的安培定律，q₀ 由轴处局部展开",
          "license": "public"}, chease_ref],
        v19_crit, v19_find,
        [gate(f"{TF}::test_v19_fylite_recovers_the_solovev_map_inside_its_contour"), gate(f"{TF}::test_v19_chease_on_the_same_contour"), kernel_gate],
        [],
        "V-19-fixed-boundary-solovev.md",
        ["★★2026-09-15 用户「补全 fixed-boundary 情景」：此前没有任何门能让 fylite 在给定边界上求解（B-10 读的是 CHEASE 输出上的残差，已并入 V-16）；内核当日新增 code/fixed_boundary",
         fb_conv, "★精确解在两个代码里都可精确表示（常数源），剩下的差是离散误差；边缘电流不为零（p′ 常数），被轮廓切开的网格正是被考的地方",
         "纳入类别：无外部数据（解析 / 自带）"],
        "pass",
        validity="定边界、光滑轮廓（无 X 点）、常数 p′ / FF′；fylite 网格 33² / 65² / 129²，CHEASE NS = NT = 40 / 80"))
    reports["V-19"] = "V-19-fixed-boundary-solovev.md"

    fb = json.loads((case / "corpus/benchmark/fixed_boundary_east137985.json").read_text(encoding="utf-8"))
    cm, bb = fb["compare"], fb_gate["B16_BAND"]
    x = cm["fylite_129_vs_chease_80"]
    b16_crit = [crit("B-16", 1, "ψ_N 差 rms / 最大（该面内 121×201 点阵），fylite 129² 对 CHEASE NS 80", "measured_band", bb["psin_rms"], "absolute", [f"最大值另带 {bb['psin_max']}"]),
                crit("B-16", 2, "磁轴距离", "measured_band", bb["axis_mm"], "absolute", unit="mm"),
                crit("B-16", 3, "通量跨度 · Ip", "measured_band", bb["span_rel"], "relative", [f"Ip 另带 {bb['ip_rel']}（CHEASE 按面内安培电流归一，fylite 不缩放）"]),
                crit("B-16", 4, "q 相对差（ψ_N 0.1–0.9 九点）rms / 最大 · q₉₅", "measured_band", bb["q_rel_rms_01_09"], "relative",
                     [f"最大值另带 {bb['q_rel_max_01_09']} · q₉₅ 另带 {bb['q95_rel']}"])]

    def line(c):
        return (f"ψ_N rms {c['psin_rms']:.2e} / 最大 {c['psin_max']:.2e} · 磁轴 {c['axis_mm']:.3f} mm · 跨度 {100 * c['span_rel']:+.3f} % · Ip {100 * c['ip_rel']:+.3f} % · "
                f"q rms {100 * c['q_rel_rms_01_09']:.2f} % / 最大 {100 * c['q_rel_max_01_09']:.2f} % · q₉₅ {100 * c['q95_rel']:+.2f} %")
    b16_find = [finding("fylite 129² 对 CHEASE NS 80", "pass", line(x)),
                finding("分辨率（读数）", "inconclusive",
                        f"fylite 65² 对 CHEASE：{line(cm['fylite_65_vs_chease_80'])}；CHEASE NS 40 对 NS 80：ψ_N rms {cm['chease_40_vs_chease_80']['psin_rms']:.1e} · q rms {100 * cm['chease_40_vs_chease_80']['q_rel_rms_01_09']:.3f} %"),
                finding("KEFIT 自由边界图作背景（读数）", "inconclusive",
                        f"fylite 129²：ψ_N rms {cm['fylite_129_vs_kefit']['psin_rms']:.2e} · 磁轴 {cm['fylite_129_vs_kefit']['axis_mm']:.2f} mm；CHEASE NS 80：ψ_N rms {cm['chease_80_vs_kefit']['psin_rms']:.2e} · 磁轴 {cm['chease_80_vs_kefit']['axis_mm']:.2f} mm",
                        caveat=["两个定边界代码到 KEFIT 图的差相同：那是 KEFIT 65² 网格与该面在其图上的重构，不是任一求解器的", "对 KEFIT 的 Ip 不可比：KEFIT 记全电流，这里解的是 0.995 面内的电流"]),
                rerun_finding(reruns["B-16"])]
    recs.append(record(
        "B-16", "定边界平衡对 CHEASE：EAST #137985 4.041 s，KEFIT 纯磁答案的 ψ_N = 0.995 面与其 p′ / FF′", "benchmark",
        "fylite: code/fixed_boundary 经树门（129² 判带，65² 作分辨率读数）",
        [chease_ref, dict(KEFIT_REF, comment="背景：问题取自它的答案（面 · 剖面 · 面内电流）；它的自由边界图只作读数，不作参考")],
        b16_crit, b16_find,
        [gate(f"{TF}::test_b16_fylite_reproduces_its_readings_and_stays_in_the_band_against_chease"), gate(f"{TF}::test_b16_kefit_context_is_a_reading")],
        [data(PTR + "kefit/kefit_raw_east137985.tar.gz", "experiment", sums["kefit/kefit_raw_east137985.tar.gz"],
              [f"问题的来源：{EAST_G} 的 ψ 图、PPRIME / FFPRIM、FPOL", KEFIT_CAVEAT_BUILD]),
         data(PTR + "benchmark/fixed_boundary_east137985.json", "experiment", sums["benchmark/fixed_boundary_east137985.json"]),
         data(PTR + "chease/chease_fixed_boundary_east137985.tar.gz", "experiment", sums["chease/chease_fixed_boundary_east137985.tar.gz"],
              ["CHEASE 两个分辨率的 EXPEQ · namelist · EQDSK；输入由实验数据导出，故随实验类"])],
        "B-16-fixed-boundary-chease.md",
        ["★同一问题交给两个定边界代码：该面（KEFIT 图的双三次样条上自轴 360 条射线取首个穿越）、101 点 p′ / FF′（÷ −2π 换口径）、边缘 F = FPOL(0.995)；CHEASE 另需面内电流（KEFIT 图上的安培环路）作归一",
         fb_conv, "★该面光滑、不过 X 点：定边界代码的问题不含分界面；分界面上的比较在 B-14（自由边界）",
         "纳入类别（参考数据）：experiment、private-artefact"],
        "pass",
        validity="EAST #137985 4.041 s 纯磁答案的 ψ_N = 0.995 面；fylite 129² 对 CHEASE NS = NT = 80；剖面为 KEFIT 的 KPPCUR / KFFCUR 多项式经 65 点表线性插值"))
    reports["B-16"] = "B-16-fixed-boundary-chease.md"

    # ---------------------------------------------------------------- B-17 / B-18 (conducting wall · vertical instability)
    wv_gate = consts(ROOT / "python/tests/test_benchmark_wall_vstab.py", ("B17_BAND", "B18_BAND"))
    TW = "python/tests/test_benchmark_wall_vstab.py"
    wv = json.loads((case / "corpus/benchmark/wall_vstab_east137985.json").read_text(encoding="utf-8"))
    fgs_ref = {"type": "spo:Code", "name": "FreeGSNKE",
               "version": f"third_party/freegsnke-main + freegs4e {wv['freegsnke_environment']['freegs4e']}（PyPI）· numpy {wv['freegsnke_environment']['numpy']}；本地运行，同一张 EAST 卡片（efund 读法的多边形无源件 · 12 路 PF）",
               "license": "public"}
    fgs_caveat = ["FreeGSNKE 运行件不入仓：CASE-23 corpus/freegsnke/ 收其脚本（freegsnke_side.py · geom.py · run_all.sh）、JSON 与数组，sha256 索引；门不重跑它（线性化 10–20 分钟）",
                  "环境实测：本地 third_party/freegs4e 0.3.0 缺 Machine API；PyPI 0.14 经 MRO 盖住 FreeGSNKE 的 Jtor（Lao85 无 inputs）；0.13.1 可用"]
    shear_note = ("★★内核缺陷随本条修正（2026-09-15）：EFIT 平行四边形原被读成「倾斜边长 h」，efund 是剪切（w · h 为水平 / 竖直外延）——EAST 壳段间留缝 7.6 / 9.2 mm、"
                  "外壳 14 行塌成零面积线；修正移动 γ(三组) −1.1 %、τ₁ −0.6 %。修正前 FreeGSNKE 须用 efund 读法建多边形才可比；本条的读数是修正后的")
    ws = wv["wall"]["sets"]
    b = wv_gate["B17_BAND"]
    b17_crit = [crit("B-17", 1, "最长 L/R 时间 τ₁ 相对差（内壳 · 外壳 · 被动板各自单解 · 三组合）", "measured_band", b["tau1_rel"], "relative"),
                crit("B-17", 2, "无源互感矩阵逐元：对角相对差中位 / 最大", "measured_band", b["M_diag_rel_median"], "relative", [f"最大值另带 {b['M_diag_rel_max']}"]),
                crit("B-17", 3, "无源互感矩阵逐元：非对角相对差 p95 · Frobenius 相对差", "measured_band", b["M_offdiag_rel_p95"], "relative", [f"Frobenius 另带 {b['M_frobenius_rel']}"]),
                crit("B-17", 4, "元件电阻相对差最大", "measured_band", b["R_rel_absmax"], "relative", ["FreeGSNKE 以蒙特卡罗估多边形面积，±1 % 的散布来自那里"])]
    b17_find = [finding(f"{sname}：τ₁", "pass",
                        f"fylite {1e3 * s['fylite_tau1_s']:.3f} ms · FreeGSNKE {1e3 * s['freegsnke_tau1_s']:.3f} ms（{100 * s['tau1_rel']:+.3f} %）· "
                        f"M 对角中位 {100 * s['M']['diag_rel_median']:.2f} % / 最大 {100 * s['M']['diag_rel_max']:.2f} % · 非对角 p95 {100 * s['M']['offdiag_rel_p95']:.2f} % · R 最大 {100 * s['R_rel_absmax']:.2f} %")
                for sname, s in ws.items()]
    b17_find += [finding("离散（读数）", "inconclusive", "fylite 每元 3×3 细丝时自感偏高约 7 %（圆导线自感项取等面积半径，对细长子细丝偏大），τ₁ +0.8 %；8×8 对 16×16 τ₁ 差 0.14 %（code/wall 缺省 8×8，本条取 16×16）"),
                 rerun_finding(reruns["B-17"])]
    recs.append(record(
        "B-17", "导体壁作为电路：EAST 无源结构的 L/R 本征模对 FreeGSNKE", "benchmark",
        "fylite: code/wall 经树门（装置卡片的内壳 · 外壳 · 被动板；元件互感 · 电阻 · M dI/dt + R I = 0 的模，每组另单解；每元 16×16 细丝）",
        [fgs_ref], b17_crit, b17_find,
        [gate(f"{TW}::test_the_freegsnke_run_is_the_registered_one"), gate(f"{TW}::test_b17_the_wall_modes_reproduce_and_stay_in_the_band_against_freegsnke")],
        [data(PTR + "freegsnke/freegsnke_vstab_east137985.tar.gz", "experiment", sums["freegsnke/freegsnke_vstab_east137985.tar.gz"], fgs_caveat),
         data(PTR + "benchmark/wall_vstab_east137985.json", "experiment", sums["benchmark/wall_vstab_east137985.json"])],
        "B-17-wall-freegsnke.md",
        ["★★2026-09-15 用户「补全导体壁，垂直不稳定性算例」：内核当日新增 code/wall——导体壁先问「墙作为电路是什么」，不需要等离子体", shear_note,
         "★装置描述是 fydoc 装置书的 EAST pf_passive（A-Box `unverified`，手工维护：几何与电阻率出自未公开内部件）——本条比的是两个代码对**同一份**描述的电路，不是对 EAST 实物的确认",
         "纳入类别（参考数据）：experiment（FreeGSNKE 运行件随 KEFIT 输入归实验类）"],
        "pass",
        validity="EAST 卡片的 90 个无源元件（内壳 40 · 外壳 40 · 被动板 10，η 0.74 / 0.74 / 0.017 μΩ·m），仅环向电流、元件内均匀；无端口 / 波纹管等三维结构"))
    reports["B-17"] = "B-17-wall-freegsnke.md"

    vs = wv["vstab"]["sets"]
    bb = wv_gate["B18_BAND"]
    fe = wv["vstab"]["freegsnke_equilibrium"]
    b18_crit = [crit("B-18", 1, "增长率 γ 相对差（fylite code/vstab 对 FreeGSNKE 刚性色散，同一平衡；内壳 · 三组合）", "measured_band", bb["gamma_rel"], "relative"),
                crit("B-18", 2, "主动线圈失稳刚度 k 相对差", "measured_band", bb["k_rel"], "relative"),
                crit("B-18", 3, "理想刚度 k_ideal（被动稳定力）相对差", "measured_band", bb["k_ideal_rel"], "relative"),
                crit("B-18", 4, "稳定裕度 k_ideal / k − 1 绝对差", "measured_band", bb["margin_abs"], "absolute", ["与 FreeGSNKE 的感性稳定裕度同定义（刚性等离子体下代数核过）"])]
    b18_find = []
    for sname, s in vs.items():
        f, r_, c = s["fylite_on_freegsnke_eq"], s["freegsnke_rigid"], s["compare"]
        b18_find.append(finding(f"{sname}：刚性色散", "pass",
                                f"γ fylite {f['gamma']:.4g} · FreeGSNKE {r_['gamma']:.4g} s⁻¹（{100 * c['gamma_rel']:+.2f} %）· k {100 * c['k_rel']:+.2f} % · k_ideal {100 * c['k_ideal_rel']:+.3f} % · 裕度 {f['margin']:.3f} / {r_['margin']:.3f}"))
        d = s["freegsnke_deformable"]
        b18_find.append(finding(f"{sname}：FreeGSNKE 可变形等离子体（读数）", "inconclusive",
                                f"γ {d['gamma']:.4g} s⁻¹（刚性的 {s['readings']['deformable_over_rigid_gamma']:.2f} 倍）· 裕度 {d['margin']:.3f}；fylite 在 KEFIT 平衡上 γ {s['fylite_on_kefit_eq']['gamma']:.4g} s⁻¹",
                                caveat=["可变形响应是 fylite 刚性模型没有的物理；FreeGSNKE 雅可比的线性度（步长）未独立核，倍数只作读数"]))
    b18_find.append(rerun_finding(reruns["B-18"]))
    recs.append(record(
        "B-18", "垂直不稳定性：EAST #137985 4.041 s 的刚性增长率与裕度对 FreeGSNKE", "benchmark",
        "fylite: code/vstab 经树门（circuit: passive，主动线圈冻结；coarsen 1、每元 8×8 细丝；质量为零的刚性等离子体、恒 Ip）",
        [fgs_ref, dict(KEFIT_REF, comment="背景：线圈电流与剖面取自 KEFIT 纯磁答案 t4041_mag；两个代码在 FreeGSNKE 由其出发收敛的反演平衡上比")],
        b18_crit, b18_find,
        [gate(f"{TW}::test_the_freegsnke_run_is_the_registered_one"), gate(f"{TW}::test_b18_the_rigid_dispersion_reproduces_and_stays_in_the_band_against_freegsnke"),
         gate(f"{TW}::test_b18_the_deformable_growth_rate_is_a_reading_not_a_band")],
        [data(PTR + "freegsnke/freegsnke_vstab_east137985.tar.gz", "experiment", sums["freegsnke/freegsnke_vstab_east137985.tar.gz"], fgs_caveat),
         data(PTR + "benchmark/wall_vstab_east137985.json", "experiment", sums["benchmark/wall_vstab_east137985.json"]),
         data(PTR + "kefit/kefit_raw_east137985.tar.gz", "experiment", sums["kefit/kefit_raw_east137985.tar.gz"], ["线圈电流 CCBRSP 与剖面的来源", KEFIT_CAVEAT_BUILD])],
        "B-18-vertical-instability-freegsnke.md",
        ["★★取代 C-03（TokSys rzrig 锚点，门自 2026-09-14 起 skip、参考侧无指针）：可复跑的垂直稳定性对拍", shear_note,
         f"★同一张平衡：FreeGSNKE 反演收敛态（κ {fe['kappa']:.3f} 对 KEFIT 1.624，边界对 KEFIT 中位 {fe['boundary_dist_to_kefit_mm']['median']:.1f} mm）；前向解以 KEFIT 电流在 65² · 129² 网格都停滞于残差 1.7e-4",
         "★刚性模型的输入（M · R · 耦合梯度 g · 刚度 k）逐项两边一致到 1 % 内；本条判的是同一组输入下的色散根",
         "纳入类别（参考数据）：experiment、private-artefact"],
        "pass",
        validity="EAST #137985 4.041 s（FreeGSNKE 反演平衡）；无源组内壳 / 三组合；主动线圈冻结；刚性、质量为零；不含可变形等离子体（读数）与反馈控制"))
    reports["B-18"] = "B-18-vertical-instability-freegsnke.md"

    # ---------------------------------------------------------------- B-19 / B-20 (against KEFIT's electromagnetic layer: efund)
    kg = consts(ROOT / "python/tests/test_benchmark_wall_vstab.py", ("B19_BAND", "B20_BAND"))
    kv = json.loads((case / "corpus/benchmark/wall_vstab_kefit_east137985.json").read_text(encoding="utf-8"))
    efund_ref = {"type": "spo:Code", "name": "efund（KEFIT 的格林表生成器）",
                 "version": "KEFIT 参考包 green_2022_source/u/efundud6565.f，gfortran 本地构建于临时目录（参考包未改）；两处补丁随件：真空室行表控读入 · 写出 rvsvs；"
                            "构建件的 PF 线圈表对参考包原表 2.5e-15 / 4.7e-16",
                 "license": "private-artefact"}
    efund_caveat = ["efund 运行件（补丁 · README · 三次运行的表）在 CASE-23 corpus/efund/，sha256 索引；门只回放已记录的表，不重跑 efund",
                    "输入是参考包自带的 EAST 算表输入 green_2022_source/run/mhdin.dat（与交付的 green2022_pcs 同源：原 rvesel.dat 与 rv6565.ddd 逐字节相同）"]
    ww = kv["wall"]
    b19_crit = [crit("B-19", 1, "内壳 40 元 → 35 个磁通环的每弧度磁通响应，最大相对差", "measured_band", kg["B19_BAND"]["loops_rel_max"], "relative"),
                crit("B-19", 2, "内壳 40 元 → 65² 网格节点的每弧度磁通响应，最大相对差", "measured_band", kg["B19_BAND"]["grid_rel_max"], "relative"),
                crit("B-19", 3, "真空室互感矩阵：非对角相对差 p95（fylite 16×16 细丝 对 efund flux() 解析积分）", "measured_band", kg["B19_BAND"]["M_offdiag_rel_p95"], "relative",
                     [f"对角中位另带 {kg['B19_BAND']['M_diag_rel_median']}、最大 {kg['B19_BAND']['M_diag_rel_max']}（自感的求法不同）"]),
                crit("B-19", 4, "最长 L/R 时间 τ₁ 相对差（两边同用卡片电阻；efund 不带电阻）", "measured_band", kg["B19_BAND"]["tau1_rel"], "relative")]
    b19_find = [finding("元件 → 磁通环 · 网格", "pass",
                        f"环最大 {ww['loops']['rel_max']:.1e}（40 元全部 < 1e-3）· 网格最大 {ww['grid']['rel_max']:.1e} · 中位 {ww['grid']['rel_median']:.1e}"),
                finding("元件 → 探针（读数）", "inconclusive", f"{ww['probes_reading']['matched']} / {ww['probes_reading']['of']} 配对；中位 {ww['probes_reading']['rel_median']:.1e} · p95 {ww['probes_reading']['rel_p95']:.1e}",
                        caveat=["探针两边的配对按位置与角度；efund 沿探针长度取 NSMP2 点平均"]),
                finding("互感矩阵与 τ₁", "pass",
                        f"非对角 p95 {ww['M']['offdiag_rel_p95']:.2e} · 对角中位 {100 * ww['M']['diag_rel_median']:.2f} % / 最大 {100 * ww['M']['diag_rel_max']:.2f} % · "
                        f"τ₁ {ww['tau_card_R_ms']['fylite'][0]:.3f} 对 {ww['tau_card_R_ms']['efund_M'][0]:.3f} ms（{ww['tau_card_R_ms']['tau1_rel']:+.1e}）"),
                finding("参考包交付的 rv6565.ddd（读数）", "inconclusive",
                        f"对同一输入按原意重建的表：环最大差 {100 * ww['shipped_vs_rebuilt']['loops_rel_max']:.1f} %、网格 {100 * ww['shipped_vs_rebuilt']['grid_rel_max']:.1f} %",
                        caveat=["算表输入里 7 行真空室元件的列没有对齐 efund 的 6e12.6 定宽读法（如 138.4682 被切成 1 与 38.4682），交付表即其误读结果；EAST 上用真空室通道的 KEFIT 反演吃的是这份表"]),
                finding("内核几何读法两处修正（2026-09-15）", "pass",
                        "a1 = 0, a2 ≠ 90：efund 的 R 向剪切（此前读成倾斜边长 h）；a1 ≠ 0：efund 的 Z 向剪切（此前读成转角，内壳上下 14 段短 25 %、环响应差 1.6 %、网格 6 %）"),
                rerun_finding(reruns["B-19"])]
    TW2 = "python/tests/test_benchmark_wall_vstab.py"
    recs.append(record(
        "B-19", "导体壁对 KEFIT 的电磁层：EAST 真空室元件的格林响应与互感对 efund", "benchmark",
        "fylite: code/wall 经树门（每元 8×8 细丝的逐元响应 loops_psi · probes_b · grid_psi；16×16 的互感矩阵）",
        [efund_ref], b19_crit, b19_find,
        [gate(f"{TW2}::test_the_efund_run_is_the_registered_one"), gate(f"{TW2}::test_b19_the_wall_responses_and_inductance_reproduce_and_stay_in_the_band_against_efund"),
         gate(f"{TW2}::test_b19_the_shipped_kefit_vessel_table_is_recorded_as_the_misread_deck")],
        [data(PTR + "efund/efund_east137985.tar.gz", "private-artefact", sums["efund/efund_east137985.tar.gz"], efund_caveat),
         data(PTR + "benchmark/wall_vstab_kefit_east137985.json", "private-artefact", sums["benchmark/wall_vstab_kefit_east137985.json"])],
        "B-19-wall-efund.md",
        ["★★2026-09-15 用户「导体壁，垂直不稳定性，与 kefit 对拍」：KEFIT 本身不算增长率，它关于导体壁的电磁量全部出自 efund——参考取 efund 本体，在参考包自带的 EAST 输入上本地构建运行",
         "★本条查出并修正了内核两处 EFIT 平行四边形读法（见结果）；修正前 B-17 / B-18 的读数同日重录",
         "★口径：efund 表是每弧度磁通（M / 2π）、每安匝；fylite 的 loops_psi / grid_psi 同口径；元件顺序按中心位置配对（逐一相同）",
         "纳入类别（参考数据）：private-artefact"],
        "pass",
        validity="EAST 真空室内壳 40 元（efund 算表输入与装置卡片逐行同几何）；35 个磁通环、65² 网格；探针只作读数；外壳与被动板不在 efund 的 EAST 输入里"))
    reports["B-19"] = "B-19-wall-efund.md"

    vk = kv["vstab"]
    b20_crit = [crit("B-20", 1, "增长率 γ 相对差（fylite code/vstab 对 efund 表组装的刚性装置，同一 KEFIT 平衡；每元 8×8 与 16×16 两档）", "measured_band", kg["B20_BAND"]["gamma_rel"], "relative"),
                crit("B-20", 2, "失稳刚度 k 相对差", "measured_band", kg["B20_BAND"]["k_rel"], "relative"),
                crit("B-20", 3, "理想刚度 k_ideal 相对差 · 裕度绝对差", "measured_band", kg["B20_BAND"]["k_ideal_rel"], "relative", [f"裕度另带 {kg['B20_BAND']['margin_abs']}"]),
                crit("B-20", 4, "耦合梯度 g 逐元相对差中位 / 最大", "measured_band", kg["B20_BAND"]["g_rel_median"], "relative", [f"最大值另带 {kg['B20_BAND']['g_rel_max']}"])]
    b20_find = [finding("efund 装置", "pass",
                        f"γ {vk['efund']['gamma']:.4g} s⁻¹ · k {vk['efund']['k']:.6g} N/m · k_ideal {vk['efund']['k_ideal']:.6g} · 裕度 {vk['efund']['margin']:.4f}（M = 2π·rvsvs；g、k 由 ±{1e3 * vk['shift_m']:.0f} mm 平移网格两次运行差分；{vk['plasma_nodes']} 个等离子体节点）")]
    for tag, s in vk["fylite"].items():
        c = s["compare"]
        b20_find.append(finding(f"fylite（{tag}）", "pass",
                                f"γ {s['gamma']:.4g}（{100 * c['gamma_rel']:+.2f} %）· k {100 * c['k_rel']:+.2f} % · k_ideal {100 * c['k_ideal_rel']:+.2f} % · 裕度 {s['margin']:.4f}（{c['margin_abs']:+.4f}）· g 中位 {100 * c['g_rel_median']:.2f} % / 最大 {100 * c['g_rel_max']:.2f} %"))
    b20_find.append(rerun_finding(reruns["B-20"]))
    recs.append(record(
        "B-20", "垂直不稳定性对 KEFIT 的电磁层：KEFIT 平衡上 efund 表组装的刚性装置对 fylite code/vstab", "benchmark",
        "fylite: code/vstab 经树门（circuit: passive、内壳、coarsen 1；质量为零的刚性等离子体、恒 Ip、主动线圈冻结）",
        [efund_ref, dict(KEFIT_REF, comment="平衡（g-file 的 J 在同一 65² 网格上）与线圈电流（a-file CCBRSP，按算表 FCID · FCTURN 分到 14 个元件）取自 KEFIT 纯磁答案 t4041_mag")],
        b20_crit, b20_find,
        [gate(f"{TW2}::test_the_efund_run_is_the_registered_one"), gate(f"{TW2}::test_b20_the_rigid_plant_reproduces_and_stays_in_the_band_against_efund")],
        [data(PTR + "efund/efund_east137985.tar.gz", "private-artefact", sums["efund/efund_east137985.tar.gz"], efund_caveat),
         data(PTR + "benchmark/wall_vstab_kefit_east137985.json", "private-artefact", sums["benchmark/wall_vstab_kefit_east137985.json"]),
         data(PTR + "kefit/kefit_raw_east137985.tar.gz", "experiment", sums["kefit/kefit_raw_east137985.tar.gz"], ["平衡与线圈电流的来源", KEFIT_CAVEAT_BUILD])],
        "B-20-vertical-instability-efund.md",
        ["★KEFIT 不给垂直增长率：本条是 KEFIT **电磁层**（efund 的互感、格林表）组装的刚性装置对 fylite，不是 KEFIT 的稳定性结论",
         "★两边同用卡片电阻（efund 不带电阻）、同一刚性色散关系；差只在 M · g · k 的求法与等离子体离散（efund：g-file 网格节点；fylite：coarsen 1 细丝）",
         "纳入类别（参考数据）：private-artefact、experiment"],
        "pass",
        validity="EAST #137985 4.041 s KEFIT 纯磁平衡；无源组内壳（efund 的 EAST 输入只含内壳）；刚性、质量为零；不含可变形等离子体"))
    reports["B-20"] = "B-20-vertical-instability-efund.md"

    # ---------------------------------------------------------------- V-21 (free-boundary evolution coupled to the PF circuits and the passive set)
    eg = consts(ROOT / "python/tests/test_benchmark_evolve_free_boundary.py", ("V21_BAND",))["V21_BAND"]
    ev = json.loads((case / "corpus/benchmark/evolve_free_boundary_east137985.json").read_text(encoding="utf-8"))
    TW3 = "python/tests/test_benchmark_evolve_free_boundary.py"
    wd, ff, dr, fe = ev["wall_decay"], ev["flux_freezing"], ev["drive_reproduction"], ev["forward_edge"]
    v21_crit = [crit("V-21", 1, "无等离子体、通道冻结：无源件从 code/wall 的最慢模出发，逐步对隐式 Euler 衰减因子 (1 + dt/τ₁)^−k 的最大相对偏差", "machine_precision", eg["wall_decay_rel"], "relative"),
                crit("V-21", 2, "理想导体（电阻 0、电压 0）、Ip 三步升 2 %：每个导体的磁链 M I + ψ_p 的最大漂移 / 等离子体磁通的最大变化", "machine_precision", eg["flux_drift_over_moved"], "relative"),
                crit("V-21", 3, "回路方程在返回状态上的相对残差（解内耦合；自由边界解到 tol 1e-9）", "machine_precision", eg["circuit_residual"], "relative",
                     ["容差取自由边界解自己的停止判据：回路方程与平衡在同一轮里闭合"]),
                crit("V-21", 4, "电流驱动（给电压驱动算出的通道电流）复现电压驱动的无源件电流：最大差 / 最大无源件电流", "measured_band", eg["shell_rel_max"], "relative")]
    mags = {k: v for k, v in fe.items() if k.endswith("_mag")}
    def span(f, fmt=".1f"):
        lo, hi = min(f(v) for v in mags.values()), max(f(v) for v in mags.values())
        return f"{lo:{fmt}} 至 {hi:{fmt}}"
    v21_find = [finding("壳模衰减（无等离子体）", "pass",
                        f"τ₁ {1e3 * wd['tau_1_s']:.2f} ms（{wd['elements']} 元），dt = τ₁/10，{wd['steps']} 步：最大相对偏差 {wd['max_rel_deviation']:.1e}"),
                finding("理想导体的磁链", "pass",
                        f"磁链漂移 {ff['linked_flux_drift_Wb']:.1e} Wb 对等离子体磁通变化 {ff['plasma_flux_moved_Wb']:.3e} Wb（{ff['drift_over_moved']:.1e}）· 回路方程残差 {ff['facts']['max_circuit_residual']:.1e} · "
                        f"每步自由边界解 converged、虚拟对 0 · 无源件电流升到 {ff['passive_max_A'][-1]:.0f} A · 磁轴 Z {1e3 * ff['axis_z'][0]:.2f} → {1e3 * ff['axis_z'][-1]:.2f} mm"),
                finding("电流驱动复现电压驱动", "pass",
                        f"电压 = {1 + dr['drive_extra']:.2f} R I₀（保持 KEFIT 线圈电流并多给 {100 * dr['drive_extra']:.0f} %），通道电流最大变 {100 * dr['channel_change_rel_max']:.3f} % · "
                        f"无源件电流最大 {dr['shell_max_A']:.0f} A，两种驱动差 {dr['shell_rel_max']:.1e}"),
                finding("code/forward 两种边界规则（B-14 三片纯磁答案；读数）", "inconclusive",
                        f"节点规则 settled、虚拟对 {span(lambda v: 1e-3 * abs(v['node']['fb_amp']))} kA；边界格分数规则 converged（{span(lambda v: v['edge']['iterations'], '.0f')} 轮、对 ≤ {max(abs(v['edge']['fb_amp']) for v in mags.values()):.0f} A）· "
                        f"磁轴 Z 离 KEFIT {span(lambda v: v['edge']['compare']['dZ_axis_mm'])} mm（节点 {span(lambda v: v['node']['compare']['dZ_axis_mm'])} mm）· "
                        f"ψ_N rms {span(lambda v: 100 * v['edge']['compare']['psin_rms_inside'], '.2f')} %（节点 {span(lambda v: 100 * v['node']['compare']['psin_rms_inside'], '.2f')} %）",
                        caveat=["B-14 的读数是虚拟位置对撑着的平衡；B-14 的带不动。哪一种离实物近，KEFIT 回答不了（它的竖直位置由拟合给出）",
                                "带 POINT 约束剖面的 t5976_primary 两种规则都不收敛"]),
                rerun_finding(reruns["V-21"])]
    recs.append(record(
        "V-21", "自由边界演化与 PF 电路 · 无源件耦合：EAST 卡片上的恒等式（code/evolve_free_boundary）", "verification",
        "fylite: code/evolve_free_boundary 经树门（隐式 Euler；电压 / 电流驱动；三组无源件 90 元；解内耦合 · 边界格分数规则 · 起点带虚拟对）；另 code/forward 的 opt-in edge_fraction",
        [{"type": "spo:Code", "name": "解析恒等式", "version": "隐式 Euler 的衰减因子 · 理想导体磁链守恒 · 同一方程的两种驱动（无第二个代码）", "license": "public"},
         dict(KEFIT_REF, comment="剖面、Ip 与线圈电流取自 KEFIT 纯磁答案 t4041_mag，只作输入")],
        v21_crit, v21_find,
        [gate(f"{TW3}::test_the_readings_are_the_registered_ones"), gate(f"{TW3}::test_v21_a_shell_mode_decays_on_the_wall_time"),
         gate(f"{TW3}::test_v21_a_perfect_conductor_keeps_its_flux_while_the_plasma_ramps"), gate(f"{TW3}::test_v21_current_drive_reproduces_the_voltage_march"),
         gate(f"{TW3}::test_v21_the_forward_edge_rule_is_a_reading_not_a_band")],
        [data(PTR + "benchmark/evolve_free_boundary_east137985.json", "experiment", sums["benchmark/evolve_free_boundary_east137985.json"]),
         data(PTR + "kefit/kefit_raw_east137985.tar.gz", "experiment", sums["kefit/kefit_raw_east137985.tar.gz"], ["剖面与线圈电流的来源", KEFIT_CAVEAT_BUILD])],
        "V-21-evolve-free-boundary.md",
        ["★★2026-09-15 /goal「完善磁平衡相关计算功能 … pf 导体线圈，导体壁等被动导体耦合」：内核新门 code/evolve_free_boundary；此前唯一的电路 + 平衡演化是测试树里不带反作用的 EFIT 回放",
         "★V 类：判的是方程与实现自洽（恒等式到舍入），不是墙电流与位移响应的物理对错——无第二个代码；Ip 是给定轨迹",
         "★步长须 γ·dt < 1（竖直不稳定模）：只取内壳（刚性 γ ≈ 709 s⁻¹，B-18）时 2 ms 一步即离开平衡、电流驱动重跑落到镜像支；本条取三组无源件（γ ≈ 4 s⁻¹）",
         "★同日内核三处实测改法：边界格分数规则（节点规则的量化抖动与一步的磁通增量同量级）· 解内耦合（整解外套 Picard 等于没有墙）· 解内耦合时虚拟位置对缺省关、起点仍开",
         "纳入类别（参考数据）：experiment"],
        "pass",
        validity="EAST #137985 卡片（12 路 PF · 内壳 · 外壳 · 被动板 90 元）；KEFIT t4041_mag 的剖面与线圈电流；Ip 三步升 2 %、2 ms 一步；65² 网格；不含 Ip 电路方程、反馈控制与竖直位移增长率"))
    reports["V-21"] = "V-21-evolve-free-boundary.md"

    # ---------------------------------------------------------------- B-21 (the static inverse problem, against FreeGSNKE's inverse solve)
    ig = consts(ROOT / "python/tests/test_benchmark_inverse_shape.py", ("B21_BAND",))["B21_BAND"]
    iv = json.loads((case / "corpus/benchmark/inverse_shape_east137985.json").read_text(encoding="utf-8"))
    TW4 = "python/tests/test_benchmark_inverse_shape.py"
    fyb, fgb = iv["boundary_vs_target"]["fylite"], iv["boundary_vs_target"]["freegsnke"]
    cur, ns, inp0 = iv["currents"], iv["null_space"], iv["inputs"]
    psin = {k: ns[k]["compare"]["psin_rms_inside"] for k in ("kefit", "freegsnke", "fylite")}
    b21_crit = [crit("B-21", 1, "fylite 设计的实现边界离目标曲线（公平窗口：距 X 点 > 0.1 m、目标 Z 覆盖区间内缩 20 mm）：中位", "measured_band", ig["fylite_boundary_median_mm"], "absolute", None, "mm"),
                crit("B-21", 2, "同上：p95 · 最大", "measured_band", ig["fylite_boundary_p95_mm"], "absolute", [f"最大另带 {ig['fylite_boundary_max_mm']} mm"], "mm"),
                crit("B-21", 3, "零空间读数：三组电流各自正解后在 KEFIT 图上 ψ_N rms 的散布 · 磁轴散布", "measured_band", ig["null_space_psin_spread"], "absolute",
                     [f"磁轴散布另带 {ig['null_space_axis_spread_mm']} mm；判的是「三组差很大的电流给出同一张平衡」"]),
                crit("B-21", 4, "fylite 设计电流正解后的 ψ_N rms（对 KEFIT 图）", "measured_band", ig["fylite_psin_rms"], "absolute")]
    b21_find = [finding("fylite 设计（code/discharge，退火 8 遍）", "pass",
                        f"实现边界离目标 中位 {fyb['median_mm']:.2f} mm · p95 {fyb['p95_mm']:.2f} · 最大 {fyb['max_mm']:.2f}（公平窗口 {fyb['points']} / {fyb['of']} 点）· "
                        f"{iv['design']['seconds']:.1f} s · 未触线圈上限 · 内部自由边界解 settled（残差 {iv['design']['facts']['residual']:.1e}）"),
                finding("FreeGSNKE 反演（同一目标与零点，归档回放）", "pass",
                        f"实现边界离目标 中位 {fgb['median_mm']:.2f} mm · p95 {fgb['p95_mm']:.2f} · 最大 {fgb['max_mm']:.2f}（{fgb['points']} / {fgb['of']} 点）"),
                finding("零空间：电流差远大于平衡差", "pass",
                        f"两边设计电流差 {cur['fylite_vs_freegsnke_rms_kAt']:.1f} kA·t rms（单通道最大 {cur['fylite_vs_freegsnke_max_kAt']:.1f}）；"
                        f"三组电流正解后 ψ_N rms：KEFIT {psin['kefit']:.4f} · FreeGSNKE {psin['freegsnke']:.4f} · fylite {psin['fylite']:.4f}，"
                        f"磁轴 ΔR {min(ns[k]['compare']['dR_axis_mm'] for k in psin):.2f} 至 {max(ns[k]['compare']['dR_axis_mm'] for k in psin):.2f} mm",
                        caveat=["「谁的电流更像 KEFIT」不能读成「谁的设计更对」：KEFIT 的电流是它自己拟合出来的，不是真值",
                                f"离 KEFIT 电流：fylite {cur['fylite_vs_kefit_rms_kAt']:.1f} kA·t rms、FreeGSNKE {cur['freegsnke_vs_kefit_rms_kAt']:.2f}"]),
                finding("目标曲线本身的限制（读数）", "inconclusive",
                        f"KEFIT 轮廓 {inp0['target_points']} 点、相邻点中位 {inp0['target_segment_median_mm']:.1f} mm，Z 只到 {inp0['target_z_range'][1]:+.3f}（其上 X 点在 +0.767，差 134 mm）；"
                        f"不设窗口时 FreeGSNKE 最大距离读作 {iv['boundary_vs_target_all_points']['freegsnke']['max_mm']:.1f} mm，多数来自「目标没有那一段」",
                        caveat=["两种读法都存在读数件里（boundary_vs_target · boundary_vs_target_all_points）"]),
                rerun_finding(reruns["B-21"])]
    recs.append(record(
        "B-21", "静态逆问题：同一目标形状下 fylite 的线圈设计对 FreeGSNKE 的反演解", "benchmark",
        "fylite: code/discharge 经树门（目标曲线 + 两个零点，退火 ridge 8 遍，卡片供电上限，每遍一次自由边界解）",
        [{"type": "spo:Code", "name": "FreeGSNKE", "version": "third_party/freegsnke-main + PyPI freegs4e 0.13.1（归档回放，未重跑）：Inverse_optimizer，24 点 isoflux + 两个 null point，牛顿",
          "license": "LGPL-3"},
         dict(KEFIT_REF, comment="目标轮廓、两个 X 点、剖面表与 Ip 取自 KEFIT 纯磁答案 t4041_mag，只作输入")],
        b21_crit, b21_find,
        [gate(f"{TW4}::test_the_readings_are_the_registered_ones"), gate(f"{TW4}::test_b21_the_design_reproduces_its_recorded_readings"),
         gate(f"{TW4}::test_b21_the_designed_boundary_stays_in_the_band"), gate(f"{TW4}::test_b21_the_currents_differ_far_more_than_the_equilibria"),
         gate(f"{TW4}::test_b21_the_target_curve_limits_are_recorded")],
        [data(PTR + "benchmark/inverse_shape_east137985.json", "experiment", sums["benchmark/inverse_shape_east137985.json"]),
         data(PTR + "freegsnke/freegsnke_vstab_east137985.tar.gz", "experiment", sums["freegsnke/freegsnke_vstab_east137985.tar.gz"], fgs_caveat),
         data(PTR + "kefit/kefit_raw_east137985.tar.gz", "experiment", sums["kefit/kefit_raw_east137985.tar.gz"], ["目标轮廓 · X 点 · 剖面 · Ip 的来源", KEFIT_CAVEAT_BUILD])],
        "B-21-inverse-shape-freegsnke.md",
        ["★★2026-09-15 /goal「完善磁平衡相关计算功能 … 前向后向」：静态逆问题此前没有判定记录（评估 note 缺口 6）",
         "★两边的目标函数不同，这是差异的来源而不是缺陷：fylite 最小化六个形状量与边界间隙的带 ridge 正则目标并守线圈上限，FreeGSNKE 解 isoflux + null 的约束牛顿问题",
         "★判的是**形状**：电流在逆问题里只被约束到零空间（见结果），电流差不作判据",
         "★公平窗口的理由在结果里：目标曲线是 KEFIT 自己的 69 点轮廓，粗（中位 48.5 mm）且上方缺一段",
         "纳入类别（参考数据）：experiment、private-artefact"],
        "pass",
        validity="EAST #137985 4.041 s 一张形状；12 路 PF、卡片供电上限；交付 p′/FF′ 表、Ip 392708.734 A；65² 网格；不含 ITER 形状、不含电流不确定性的显式报告"))
    reports["B-21"] = "B-21-inverse-shape-freegsnke.md"

    # ---------------------------------------------------------------- V-22 (the same inverse problem on the ITER shape)
    vg = consts(ROOT / "python/tests/test_benchmark_inverse_shape_iter.py", ("V22_BAND",))["V22_BAND"]
    iv2 = json.loads((ROOT / "docs/benchmark/readings/inverse_shape_iter.json").read_text(encoding="utf-8"))
    TW5 = "python/tests/test_benchmark_inverse_shape_iter.py"
    sep, fa, cu, ip2 = iv2["separatrix_vs_target"], iv2["design"]["facts"], iv2["currents"], iv2["inputs"]
    tgt2 = {"r0": 6.2209, "a": 1.9819, "kappa": 1.8492, "delta_upper": 0.3456, "delta_lower": 0.5432, "z0": 0.3660}
    v22_crit = [crit("V-22", 1, "设计出的分离面离目标曲线（全点；ITER 的 trace 不含 X 点腿，无需窗口）：中位", "measured_band", vg["median_mm"], "absolute", None, "mm"),
                crit("V-22", 2, "同上：p95 · 最大", "measured_band", vg["p95_mm"], "absolute", [f"最大另带 {vg['max_mm']} mm"], "mm"),
                crit("V-22", 3, "六个形状量的归一 RMS（shape_error）", "measured_band", vg["shape_error"], "relative"),
                crit("V-22", 4, "峰值通道电流 |I| —— 卡片无供电额定，退火不守限，故以实测设计值为带", "measured_band", vg["max_abs_MAt"], "absolute", 
                     ["超过它的「更好形状」是另一台机器的设计，不是更好的设计"], "MA")]
    v22_find = [finding("ITER 参考分离面上的设计", "pass",
                        f"分离面离目标 中位 {sep['median_mm']:.1f} mm · p95 {sep['p95_mm']:.1f} · 最大 {sep['max_mm']:.1f}（门的 rms {1e3*fa['boundary_gap_rms']:.1f} mm）· "
                        f"shape_error {fa['shape_error']:.4f} · {iv2['design']['seconds']:.0f} s · 内部自由边界解 settled（残差 {fa['residual']:.1e}）"),
                finding("实现的形状量对目标", "pass",
                        f"R0 {fa['shape_r0']:.4f}（目标 {tgt2['r0']}）· a {fa['shape_a']:.4f}（{tgt2['a']}）· z0 {fa['shape_z0']:.4f}（{tgt2['z0']}）· "
                        f"δ上 {fa['shape_delta_upper']:.4f}（{tgt2['delta_upper']}）· κ {fa['shape_kappa']:.4f}（{tgt2['kappa']}）· δ下 {fa['shape_delta_lower']:.4f}（{tgt2['delta_lower']}）",
                        caveat=["κ 低约 3 %、δ下低约 0.055：在保持解收敛与电流不失真的前提下调不上去（见下条），是解析剖面族在这张形状上的表达力边界"]),
                finding("设置是这条记录的真内容（实测逼出）", "pass",
                        "盒子 65² → 129²：间隙 rms 157 → 63 mm；退火遍数 8 → 16 在 65² 上有效、129² 上已饱和；"
                        "c4 位置控制**必须**让设定点跟踪 R0（`pc_track_r0 = 1`）——固定在目标面积质心时边界被 Shafranov 位移拉偏（rms 180 mm）；"
                        "边界格分数规则在此无效（与基线逐位同），与 EAST 相反",
                        caveat=["`emp = 2` 是最后一个仍**收敛**的设置：emp 3 的 shape_error 略好（0.0269）却 600 轮不收敛（残差 0.019）",
                                "`enp = 0.5` 给出全场最好的 κ 1.834，代价是 37.5 MA·t 的电流且始终不收敛——形状分是用不存在的电流换的；" + "★给它 4 倍迭代预算（2400 轮、938 s）仍不收敛，残差反而由 0.12 升到 0.32：这是该设置本身不稳，不是预算不够"]),
                finding("目标曲线与卡片的缺陷（读数）", "inconclusive",
                        f"参考分离面是数字化 METIS 曲线：{ip2['target_points']} 个有限点、相邻中位 {ip2['target_segment_median_mm']:.0f} mm，且在 X 点处**开口 {ip2['target_open_gap_mm']:.0f} mm**（本条按尖角 {ip2['target_closed_through']} 补齐）；"
                        f"卡片的两条限制器轮廓都不是真空室内区域（First Wall 止于 Z = −3.069，比目标最低点高 230 mm；Divertor 不含主等离子体），本条注入 fydoc 的 METIS 壁（57 点闭合）作限制器；"
                        f"pf_active 无供电额定，退火不守限（实测峰值 {cu['max_abs_MAt']:.1f} MA·t）",
                        caveat=["ITER-FEAT 2000 那份 dev:currentMax 属另一套线圈（与 base 的 12 圈全不同），不可挪用作额定"]),
                rerun_finding(reruns["V-22"])]
    recs.append(record(
        "V-22", "静态逆问题的第二个形状：ITER 参考分离面上的线圈设计（无参考侧，自洽判据）", "verification",
        "fylite: code/discharge 经树门（ITER 卡片 12 路线圈；目标为卡片的 fylite:reference_boundary，按 X 点尖角补齐；注入 fydoc METIS 壁作限制器；129² 盒、16 遍、c4 位置控制跟踪 R0）",
        [{"type": "spo:Code", "name": "无参考侧（自洽判据）",
          "version": "ITER 平衡件不可达：TEQ / TOSCA 为指向未设 $ITER_SCENARIO_ROOT 的指针件；FreeGSNKE 不带 ITER 机器",
          "license": "n/a"}],
        v22_crit, v22_find,
        [gate(f"{TW5}::test_v22_the_design_reproduces_its_recorded_readings"),
         gate(f"{TW5}::test_v22_the_designed_separatrix_stays_in_the_band"),
         gate(f"{TW5}::test_v22_the_design_does_not_buy_shape_with_current_the_machine_lacks"),
         gate(f"{TW5}::test_v22_the_target_curve_is_recorded_with_its_defects")],
        [data("docs/benchmark/readings/inverse_shape_iter.json", "public"),
         data("dist/facts/device/iter.jsonld", "public", None, ["装置卡片与其参考分离面"]),
         data("fydoc facts/device/iter/abox/providers/wall/metis.jsonld", "public", None, ["注入的限制器轮廓（57 点闭合）"])],
        "V-22-inverse-shape-iter.md",
        ["★★2026-09-15 /goal「… 前向后向」第二个形状：B-21 立在 EAST 一张形状上，评估 note 缺口 6 要求补第二个形状",
         "★V 类而非 B 类：这张形状没有任何可达的参考平衡，判的是设计自身的闭合（要多少电流 · 解出什么分离面 · 离所要的曲线多远）与它需要的设置",
         "★电流带是缺额定的替身：卡片无 pf_active/supply，门里没有任何东西拦住退火；没有这条带，形状分可以用不存在的电流买",
         "★不需要 B-21 那种公平窗口：`surfaces::trace` 追出的分离面本就不含 X 点腿，三种窗口读数逐位相同",
         "纳入类别（参考数据）：public"],
        "pass",
        validity="ITER 卡片（EDA 几何的 12 路线圈，无额定）；15 MA、解析剖面族 β₀ 0.6 · emp 2；129² 盒；一张形状、一个时刻；不含参考平衡对拍、不含电流不确定性的显式报告"))
    reports["V-22"] = "V-22-inverse-shape-iter.md"

    # ---------------------------------------------------------------- V-23 (the ITER passive circuit)
    wb = consts(ROOT / "python/tests/test_benchmark_wall_iter.py", ("V23_R_BAND", "V23_TAU_BARE", "V23_TAU_SCREENED", "V23_BAND_CONTAINS_CREATE", "V23_L"))
    wi = json.loads((ROOT / "docs/benchmark/readings/wall_iter.json").read_text(encoding="utf-8"))
    TW6 = "python/tests/test_benchmark_wall_iter.py"
    ws_, wc, wl = wi["sets"], wi["checks"], wi["literature"]
    scr = ws_["vv_ots"]["sc_screened"]
    v23_crit = [crit("V-23", 1, "真空室双壳并联的环向电阻对 ITER_D_22FPWQ 自报值（7.9 µΩ）", "measured_band",
                     wb["V23_R_BAND"]["rel_to_literature"], "relative",
                     ["两条独立算法：内核的逐元电阻，与直接自原件按极向条带并联的解析和——两者逐位相同"]),
                crit("V-23", 2, "补上超导回路屏蔽后的 τ₁（VV + OTS）对 CREATE-NL 的 0.3623 s", "measured_band",
                     wb["V23_TAU_SCREENED"]["rel_to_create_nl"], "relative",
                     ["★这是一致性判据，但容差宽达 8 %：本仓自身因线圈自感取法的散布就有 ±7 %（见判据 3）"]),
                crit("V-23", 3, "本仓不确定度区间须**包含** CREATE 的 τ₁（0.3623 与 0.3705 s）", "measured_band",
                     None, None,
                     ["区间由线圈自感的三种取法给出：a = 0.25 m / a 自矩形单丝 / a 自矩形 3×3；"
                      "★「一致」的诚实形式是「残差小于我方自身的不确定度」，不是「对上了」"]),
                crit("V-23", 4, "屏蔽使均匀模电感下降的幅度（须 < 0.65 倍，即降幅 > 35 %）", "measured_band",
                     wb["V23_L"]["screened_uH"], "absolute",
                     ["这一项才是解释本身：零电阻回路保磁通，压低真空室模的有效电感"], "uH")]
    v23_find = [finding("真空室环向电阻对文献", "pass",
                        f"双壳并联 {ws_['vv_both']['R_toroidal_parallel_uOhm']:.4f} µΩ 对 ITER_D_22FPWQ 的 "
                        f"{wl['vv_toroidal_resistance_uOhm']} µΩ（{100 * wc['R_toroidal_rel_to_literature']:+.2f} %）；"
                        f"内壳 {ws_['vv_inner']['R_toroidal_parallel_uOhm']:.4f} · 外壳 {ws_['vv_outer']['R_toroidal_parallel_uOhm']:.4f} µΩ。"
                        "★比书页原有的 8.98 µΩ 粗估更接近真值"),
                finding("裸回路的时间常数（读数：高 57 %，保留在册）", "inconclusive",
                        f"不含线圈时 VV 双壳 τ₁ {ws_['vv_both']['tau_1_s']:.4f} s、加 OTS {ws_['vv_ots']['tau_1_s']:.4f} / "
                        f"{ws_['vv_ots']['tau_2_s']:.4f} s，对 CREATE 的 {wl['create_tau1_s'][0]} / {wl['create_tau2_s'][0]} s（NL）高约 57 %。"
                        "这个数**不删**：它是「不含超导回路」这一口径下的正确答案，也是下面那条解释的出发点",
                        caveat=["口径是对得上的：CREATE 按模式形状点名两个常数，本条实测 k=0 均匀度 1.0000、"
                                "k=1 上下反对称度 −0.9045，且恰为最慢的两个本征模"]),
                finding("五条候选解释逐一证伪（含本会话自己先提错的那一条）", "pass",
                        "①离散粒度：135+151 → 57+50（CREATE 自己的元数）→ 28+25，τ₁ 只动 < 0.5 %（0.568922 → 0.569345 → 0.571403）；"
                        "②增厚壳：照 CREATE 的 60 → 150 mm 配 η_eq 1.90 µΩ·m 重算，τ₁ **升** 5 %（0.5689 → 0.5977），方向相反；"
                        "③电阻率：ρ/t 为 12.67（CREATE）对 13.33（本仓），差 5 % 且方向相反；"
                        "④模式定义：见上条，是同一对模式；"
                        "★⑤**传导连接——这是本会话先提出、随即自证为错的一条**：对 n = 0 环向涡流，各环本就只有互感耦合，"
                        "内外壳之间的径向连接只让电流在两壳间重分配，而那已被并联电阻算进；把两壳强制短接得到的正是"
                        "已在求解的均匀模。该说法一度写进本登记册、plan 与内核笔记，此次一并订正",
                        caveat=["记下它，是因为它曾被当作结论写出去过；错的不是方向感，是没有先问「n=0 下传导连接改变什么」"]),
                finding("★真因：CREATE 的 plasmaless 系统含零电阻超导回路，屏蔽了真空室模", "pass",
                        f"22L4FE 第 2 页明写「All resistances (in SC coils, voltage amplifiers, connections) are **neglected**」，"
                        f"而其 L₀ / R₀ 装着十一条 PF/CS 回路。零电阻回路保磁通，故以 Schur 补消去线圈："
                        f"L_eff = M_vv − M_vc M_cc⁻¹ M_cv。均匀模电感 {wc['L_uniform_unscreened_uH']:.4f} → "
                        f"{wc['L_uniform_screened_uH']:.4f} µH（−{100 * (1 - wc['L_uniform_screened_uH'] / wc['L_uniform_unscreened_uH']):.0f} %），"
                        f"τ₁ {ws_['vv_ots']['tau_1_s']:.4f} → {scr['a_rect_1fil']['tau_1_s']:.4f} s，"
                        f"对 CREATE-NL 的 {wl['create_tau1_s'][0]} s 差 {100 * wc['tau1_screened_vs_create_nl']:+.2f} %",
                        caveat=["互感用 Maxwell 共轴圆环公式自算，先对内核的 M 验过：非对角相对差中位 −0.0094 %、p95 0.168 %，"
                                "L_uniform 5.0632 对 5.0657 µH——不是靠公式凑出来的"]),
                finding("★屏蔽已进内核：门直接给出 `tau_*_screened`（2026-09-16）", "pass",
                        f"`code/wall` 加设定 `screen_coils`（默认关闭），由内核做同一步 Schur 消去。"
                        f"VV + OTS 上门给 {ws_['vv_ots']['sc_screened']['door']['tau_1_s']:.6f} s、"
                        f"VV 双壳 {ws_['vv_both']['sc_screened']['door']['tau_1_s']:.6f} s，"
                        f"消去 {ws_['vv_ots']['sc_screened']['door']['n_coils']} 个线圈元；"
                        f"与本记录侧独立自算的 {ws_['vv_ots']['sc_screened']['a_rect_1fil']['tau_1_s']:.6f} s 差 "
                        f"{100 * ws_['vv_ots']['sc_screened']['door_vs_record_side_rel']:+.3f} %。"
                        f"对 CREATE-NL 的 {wl['create_tau1_s'][0]} s 差 {100 * wc['tau1_door_vs_create_nl']:+.2f} %",
                        caveat=["★这一条是本记录成立的前提之一：屏蔽此前只在记录侧算，内核漂了不会有任何东西红；"
                                "现在门的值才是读数，记录侧自算降为独立交叉核对，两者由门 "
                                "`test_v23_the_door_itself_now_yields_the_screened_spectrum` 守住（容差 0.5 %）",
                                "两侧的线圈自感取法不同（内核 8×8 细丝 / 记录侧解析圆环单丝），故这是**吻合**、不是同一次计算",
                                "默认关闭：B-17 · B-19 · B-20 是立在裸回路上的带，默认屏蔽会挪走已入册的答案"]),
                finding("残差小于本仓自身的不确定度（这才是「一致」的诚实形式）", "pass",
                        f"线圈自感的三种取法给出 τ₁ 区间 [{wc['tau1_screened_band'][0]:.4f}, {wc['tau1_screened_band'][1]:.4f}] s"
                        f"（a = 0.25 m / a 自矩形单丝 / a 自矩形 3×3），跨度约 14 %；"
                        f"CREATE 的 {wl['create_tau1_s'][0]} 与 {wl['create_tau1_s'][1]} s **都落在区间内**。"
                        f"主报值取 a 自矩形单丝（与内核 rect_of 的 a_eq 约定一致）= {scr['a_rect_1fil']['tau_1_s']:.4f} s",
                        caveat=["★不报 a = 0.25 m 那一档的 −0.44 %：它对得最准，但取法最随意，拿它当主结论是挑数"]),
                finding("回路拓扑与线圈几何都不影响结论（两条候选一并排除）", "pass",
                        f"十二条独立线圈与表 2.1.b–f 的十一条真实回路给出**逐位相同**的 L_uniform "
                        f"{wi['screening']['topology_independent']['12_independent_coils']['L_uniform_uH']:.4f} µH、"
                        f"τ₁ {wi['screening']['topology_independent']['12_independent_coils']['tau_1_s']:.4f} s"
                        f"（τ₂ 仅第四位差）——屏蔽由 M_vc M_cc⁻¹ M_cv 决定，回路只是基变换；"
                        f"线圈几何用卡片的 2ACJT3 v3.1 给 {wi['screening']['coil_geometry_independent']['card_2ACJT3_v3_1']['tau_1_s']:.4f} s、"
                        f"用 22L4FE 自己的表 2.1.a 给 {wi['screening']['coil_geometry_independent']['22L4FE_table_2_1_a']['tau_1_s']:.4f} s，差 0.7 %"),
                finding("端口组是本仓的建模过度（读数，且不供对比用）", "inconclusive",
                        f"三组端口内壳按**连续环**建模，而实物是 18 个约 5° 宽（环向占空比约 25 %）。"
                        f"加入后 R_parallel 由 {ws_['vv_ots']['R_toroidal_parallel_uOhm']:.4f} 降到 "
                        f"{ws_['vv_ots_ports']['R_toroidal_parallel_uOhm']:.4f} µΩ，裸 τ₁ 冲到 {ws_['vv_ots_ports']['tau_1_s']:.4f} s。"
                        "本条如实记录该组读数，但任何对比都不应当用它",
                        caveat=["改正方向：按占空比折算等效环向电阻，或把端口建成不闭合段——两者都需要 33NHXN / 22L4FE 未给的环向信息"]),
                rerun_finding(reruns["V-23"])]
    recs.append(record(
        "V-23", "ITER 被动导体回路：真空室环向电阻对文献；无等离子体时间常数补上超导回路屏蔽后对 CREATE 一致", "verification",
        "fylite: code/wall 经树门（ITER 卡片的 pf_passive，324 个 loop 自 fydoc 由 CC BY 原件离散；"
        "元件互感 · 电阻 · M dI/dt + R I = 0 的 L/R 本征模，每组另单解；每元 8×8 细丝）"
        "＋门自己的 `screen_coils`：把普通 pf_active 线圈作为零电阻回路消去（Schur 补），"
        "与裸谱并列给出 `tau_*_screened`）",
        [{"type": "spo:Code", "name": "ITER_D_22L4FE v1.0（CREATE）与 ITER_D_22FPWQ v4.0（真空室 DDD）",
          "version": "22L4FE 表 4.1.a 与 §2.1 / 表 2.1.a–f（EFDA/03-1108 D2，2004-03-03）；22FPWQ 表 2.1-1 的环向 / 极向电阻",
          "license": "ITER IDM Internal Use（只引数值，件不再分发）"}],
        v23_crit, v23_find,
        [gate(f"{TW6}::test_v23_the_vessel_toroidal_resistance_agrees_with_the_literature"),
         gate(f"{TW6}::test_v23_the_bare_time_constants_reproduce"),
         gate(f"{TW6}::test_v23_the_modes_are_the_ones_create_names"),
         gate(f"{TW6}::test_v23_screening_by_the_superconducting_circuits_closes_the_gap"),
         #: ★这两条守住「屏蔽已进内核」：门的 `tau_*_screened` 对记录侧独立自算（0.5 %），
         #: 以及门自己的值对 CREATE 落在本仓的不确定度区间内。没有它们，内核漂了不会有东西红。
         gate(f"{TW6}::test_v23_the_door_itself_now_yields_the_screened_spectrum"),
         gate(f"{TW6}::test_v23_the_doors_screened_tau_stays_in_the_band_against_create"),
         gate(f"{TW6}::test_v23_our_own_uncertainty_band_contains_creates_value"),
         gate(f"{TW6}::test_v23_neither_circuit_topology_nor_coil_geometry_changes_the_answer"),
         gate(f"{TW6}::test_v23_the_port_sets_are_recorded_but_flagged_as_over_modelled")],
        [data("docs/benchmark/readings/wall_iter.json", "public"),
         data("fydoc facts/device/iter/abox/static/now/pf_passive.jsonld", "public", None,
              ["324 个 loop，自 CC BY 4.0 的 Zenodo 原件（10.5281/zenodo.17113713）逐段离散"]),
         data("dist/facts/device/iter.jsonld", "public", None, ["装置卡片（本轮起带 pf_passive）"])],
        "V-23-wall-iter.md",
        ["★★2026-09-16 /goal「… 导体壁等被动导体耦合」的 ITER 侧：此前 ITER 卡片的 `pf_passive` 为 None、"
         "十四个 vessel 单元无一带 `element`，`code/wall` 与 `code/vstab` 在这台机器上**看不到任何被动导体**",
         "★V 类：参考侧是文献数值（两份 Internal Use 件），不是可回放的运行件",
         "★★★**本条首录时判「不可比」，同日据实测改判「补上屏蔽后一致」**。首录把差因归给「CREATE 侧有传导连接」，"
         "那是推测且已自证为错（n = 0 下径向连接不改变环向回路拓扑）；真因在同一份件的前一页——"
         "plasmaless 系统含零电阻超导回路，保磁通、屏蔽真空室模。两版都留在册里，因为错的那版曾被写出去过",
         "★不去凑 τ：把 η 或几何调到对上 0.3623 s 会毁掉已经成立的电阻一致性；"
         "主报值也不取对得最准的那一档（a = 0.25 m，−0.44 %），而取取法最自然的一档（−5.66 %）",
         "纳入类别（参考数据）：public"],
        "pass",
        validity="ITER 卡片的被动集（自 CC BY 原件离散的 324 元，8×8 细丝）；无等离子体、纯 L/R 电路；"
                 "屏蔽由门的 `screen_coils` 做（零电阻回路的 Schur 补，线圈自感取 8×8 细丝），"
                 "记录侧另以解析圆环单丝独立自算一遍作交叉核对；"
                 "端口按连续环建模（已知过度）；不含 3-D 端口结构、不含等离子体响应"))
    reports["V-23"] = "V-23-wall-iter.md"
    return recs, reports


def consts(path: Path, names: tuple[str, ...]) -> dict:
    """Module-level literal constants of a gate file (bands live in the gate, the record quotes them)."""
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


EAST_G = "kefit_raw_east137985/rejected/t4041_mag/g137985.04041"


# ------------------------------------------------------------------------------------------------ reports

def report_md(r: dict, rr: dict) -> str:
    rid = r["id"].split("/")[1]
    kind = {"verification": "V 验证", "benchmark": "B 对拍", "validation": "C 确认"}[r["comparison_kind"]]
    refs = "；".join(f"{x['name']} · {x.get('version', '')} · {x.get('license', '')}" for x in r["compared_reference"])
    gates = "；".join(f"`{g['name']}`" for g in r["run"]["realizes"])
    verdict = {"pass": "成立", "fail": "不成立", "inconclusive": "未判（读数）", "unevaluated": "未评估"}
    rerun = next(f for f in reversed(r["findings"]) if str(f.get("finding_kind", "")).startswith("re-run"))
    L = ["---", f"title: {rid} · {r['title']}", "---", "", f"# {rid} · {r['title']}", "", "| | |", "| :--- | :--- |",
         f"| **类** | **{kind}** |", f"| **参考** | {refs} |", f"| **对象** | {r['compared_subject']['comment']} |",
         f"| **数据** | 见 §5 表（{len(r['run']['has_input'])} 项） |", f"| **门** | {gates} |",
         f"| **登记册结论** | {verdict[r['overall_verdict']]}（`assertion_state: {r['assertion_state']}`） |",
         #: ★日期取自那条复测 finding 自己的标题，不取写册日 `DATE`：沿用的记录带的是它上次
         #: 那一次的日期，这一行必须跟着它，否则每次写册都会把所有旧复测显示成今天做的。
         f"| **复测** | {rerun.get('title', f'复测 {DATE}')}：{verdict[rerun['verdict']]}"
         f"——{rerun.get('deviation_literal', '')} |", "",
         "> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。", ""]
    if r.get("validity_domain"):
        L += [f"**适用域**：{r['validity_domain']}", ""]
    L += ["## 1. 判据", "", "| 量 | 范数 | 容差 | 容差来源 | 备注 |", "| :--- | :--- | ---: | :--- | :--- |"]
    for c in r["criteria"]:
        tol = c.get("tolerance", {})
        unit = tol.get("has_unit", {}).get("ucum_code", "")
        L.append(f"| {c['quantity_label']} | {c.get('norm', '')} | {tol.get('numeric_value', '—')}{(' ' + unit) if unit else ''} | {c['tolerance_basis']} | {'；'.join(c.get('caveat', []))} |")
    L += ["", "## 2. 口径与说明", ""] + [f"- {x}" for x in r["caveat"]] + ["", "## 3. 结果", "", "| 项 | 读数 | 判 | 备注 |", "| :--- | :--- | :--- | :--- |"]
    for f in r["findings"]:
        L.append(f"| {f['title']} | {f.get('deviation_literal', '')} | {verdict[f['verdict']]} | {'；'.join(f.get('caveat', []))} |")
    L += ["", "## 4. 不可比的部分", ""]
    L += rr.get("not_comparable", ["（见 §2）"])
    L += ["", "## 5. 数据与怎么重跑", "", "| 存储项 | 校验 | 纳入类别 |", "| :--- | :--- | :--- |"]
    for d in r["run"]["has_input"]:
        L.append(f"| {d['storage_uri']} | {d.get('checksum', '—')} | {d['license']} |")
    L += ["", "受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。", "", "```bash"] + rr["rerun_cmd"] + ["```", "",
          "## 6. 结论", "", rr["conclusion"], ""]
    return "\n".join(L)


REPORT_TEXT = {
    "V-16": {"not_comparable": ["- 三组语料都不是 fylite 解出的平衡：本条不对 fylite 的求解器下任何结论。",
                                "- 残差的数是「文件 × 判据 × 分辨率」三者的性质：同一份物理平衡换输出盒或内部网格，残差就换（原 B-10 的发现）。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "ITER_SCENARIO_ROOT=<ITER IDM 平衡件根> CHEASE_EXE=<本机构建的 chease> \\",
                           "  uv run --no-project --with pytest --with numpy --with scipy --with h5py \\",
                           "  python -m pytest python/tests/test_teq_equilibria.py python/tests/test_tosca_equilibria.py python/tests/test_chease_equilibrium.py"],
             "conclusion": "成立：本仓的 GS 残差判据在三组外部平衡上读出的数都落在各自点名分辨率的带内，COCOS 口径从数里读出且无须翻转。只回答「判据读出什么」，不回答「fylite 解得对不对」。"},
    "V-17": {"not_comparable": ["- 定边界、矩形盒、解析剖面：不含自由边界、限制器 / X 点边界搜索与测量拟合。"],
             "rerun_cmd": ["cd $FYLITE_KERNEL   # 私仓", "PYTHONPATH=$FYLITE_PUBLIC/python:tests FYLITE_KERNEL_LIB=rust/target/release/libfylite_kernel.so \\",
                           "  uv run --no-project --with pytest --with numpy --with scipy python -m pytest -p no:cacheprovider \\",
                           "  tests/test_rust_kernels.py::test_solovev_is_reproduced_through_the_abi \\",
                           "  tests/test_oracle_marshalling.py::test_the_deltastar_operator_returns_the_solovev_source",
                           "cargo test --manifest-path rust/fylite/Cargo.toml equilibrium::   # 单元测试（会在内核检出里构建）"],
             "conclusion": "成立（经 C-ABI 的两条门）：Δ* 算子与定边界求解在 Solov'ev 精确解上到机器精度。内核单元测试那一半本条写入时未跑，标未评估。"},
    "B-12": {"not_comparable": ["- 两个代码仍有三处实现差：KEFIT 以 FWTFC 0.3 拟合 PF 电流、fylite 固定实测值；KEFIT `fitdelz` 对 fylite 竖直设定点扫描；KEFIT 边缘系数 pcurbd = fcurbd = 0.5、fylite 无对应。",
                                "- B_T 取 TF 电流节点 `\\TOP.T2:TFP` 与 GUI_v5 注释式（130 匝 × 16 线圈）——装置书只记为候选（gap tf-current-no-ampere-signal-since-97286）。",
                                "- 探针误差下限取 `efit/2016/bitmp2.txt` 的中位（GUI_v5 逐探针的行按另一套槽序）。"],
             "rerun_cmd": ["# 读数由私仓工具产出（$FYLITE_KERNEL/tools/benchmark-east-raw.py，见 B-06 报告 §9）；本仓的门只核读数与归档",
                           "cd $FYLITE_PUBLIC && FYDOC_ORACLE=<fydoc cases/> python -m pytest python/tests/test_benchmark_equilibrium.py::test_b12_the_raw_tree_readings_are_the_registered_ones"],
             "conclusion": "读数，不判：在同一组原始树输入上，剔除同一批 7 个不自洽探针后两个代码的纯磁反演都收敛（q₀ fylite 2.04 / 1.98 / 1.92，KEFIT 1.91 / 1.92 / 2.00），磁轴相差 15–35 mm；全部探针时两边都拟不上；加 POINT 后两边都不稳。"},
    "B-14": {"not_comparable": ["- 网格同为 65×65（R 1.2–2.8 m，Z ±1.4 m），但边界搜索、限制器轮廓与自由边界迭代的停止判据各是各的：fylite 用卡片的 base 限制器，KEFIT 用 GUI_v5 的 60 点限制器。",
                                "- fylite 的剖面表分支按 Ip 归一，表的整体规格（每弧度 / 整圈）会被除掉；p′ 与 FF′ 的相对大小与符号保留。",
                                "- q 不在比较里：剖面表分支不输出 q。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_equilibrium.py -k b14",
                           "# 读数重写：python tools/benchmark-equilibrium.py forward-kefit --out <dir>"],
             "conclusion": "成立：拿 KEFIT 自己在 #137985 原始树输入上收敛的线圈电流与剖面，fylite 的自由边界正问题在三片纯磁答案上把磁轴放在 4.9 mm 内、边界中位 3.4 mm 内、ψ_N rms 0.74 % 内；带 POINT 约束的剖面出带（记为发现）。"},
    "V-18": {"not_comparable": ["- 无噪声、同一份卡片几何、同一个线圈描述：本条不含测量误差与装置描述误差。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_equilibrium.py -k v18",
                           "# 读数重写：python tools/benchmark-equilibrium.py twin --out <dir> [--kefit-exe <efitd6565d>]"],
             "conclusion": "成立：已知真值时 fylite 的反演把 q₀ 放回 0.06 %、q₉₅ 0.13 %、磁轴 1.2 mm、边界 1.7 mm 内。"},
    "B-15": {"not_comparable": ["- KEFIT 用 green2022_pcs 几何（与卡片探针 74 / 76 槽重合），fylite 用卡片自己；两个未配对的 KEFIT 槽权重 0。",
                                "- KEFIT 拟合线圈电流与 Ip（带权），fylite 固定线圈、Ip 为等式。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_equilibrium.py -k b15"],
             "conclusion": "成立：同一份合成测量上 KEFIT 反演无错误标记，q₀ 偏 −4.9 %、q₉₅ −1.1 %、磁轴 1.3 mm、边界 4.2 mm 内；与 V-18 并读，fylite 在这一真值上离得更近。"},
    "V-19": {"not_comparable": ["- 光滑轮廓、常数源：不含 X 点边界、剖面表插值与测量拟合；EAST 形状上的同一问题在 B-16。",
                                "- q₀ 两边约定不同：fylite 取最内一对被追踪面外推到轴，CHEASE 取其 ψ 网格的轴值；q 剖面的比较取 ψ_N 0.1–0.9。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "CHEASE_EXE=<本机构建的 chease> FYLITE_KERNEL_LIB=<带 code/fixed_boundary 的内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_fixed_boundary.py -k v19",
                           "# 读数重写：python tools/benchmark-fixed-boundary.py solovev --out <dir>",
                           "cd $FYLITE_KERNEL && cargo test --release --lib -- fixedbnd fixed_boundary_tests   # 私仓单元测试"],
             "conclusion": "成立：给定轮廓上 fylite 的定边界求解在 129² 上把 Solov'ev 精确解重现到 ψ_N rms 1.1e-5、Ip 1.7e-5、磁轴 0.026 mm，误差按二阶下降；CHEASE 在同一轮廓上到 ψ_N rms 3.9e-6。"},
    "B-16": {"not_comparable": ["- 该面光滑、不过 X 点：分界面上的比较在 B-14（自由边界）；两个定边界代码都不回答分界面问题。",
                                "- 对 KEFIT 自由边界图的读数不作判：KEFIT 65² 网格与该面在其图上的重构使两个定边界代码离它一样远；KEFIT 的 Ip 是全电流，与面内电流不可比。",
                                "- CHEASE 按面内安培电流归一（NCSCAL = 2），fylite 按剖面表原样解；两边 Ip 的 −0.1 % 即此。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_KERNEL_LIB=<带 code/fixed_boundary 的内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_fixed_boundary.py -k b16",
                           "# 读数与 CHEASE 运行件重写：CHEASE_EXE=<chease> python tools/benchmark-fixed-boundary.py east --out <dir>"],
             "conclusion": "成立：EAST 形状上同一定边界问题，fylite 129² 与 CHEASE NS 80 的 ψ_N 差 rms 4.9e-5、磁轴 5 µm、q（ψ_N 0.1–0.9）0.10 %；两者离 KEFIT 自由边界图一样远（2.3 mm），那是参考图的离散，不是求解器的。"},
    "B-17": {"not_comparable": ["- 两边的自感求法不同：fylite 每元 nu × nv 细丝加圆导线自感项，FreeGSNKE 按多边形裁剪的方格细丝——M 对角差 1.4 % 中位即此；τ₁ 对它不敏感。",
                                "- 装置描述是 fydoc 装置书里未经核的手工卡片：本条不确认 EAST 实物的时间常数。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_wall_vstab.py -k 'registered or b17'",
                           "# FreeGSNKE 侧（不在门里）：解开 corpus/freegsnke/freegsnke_vstab_east137985.tar.gz，按其 run_all.sh（freegs4e==0.13.*）"],
             "conclusion": "成立：同一张 EAST 卡片上，fylite code/wall 与 FreeGSNKE 的无源 L/R 本征模 τ₁ 在内壳 · 外壳 · 被动板 · 三组合上差 ≤ 0.08 %（12.75 / 13.10 / 400.6 / 413.5 ms），互感矩阵非对角 p95 ≤ 0.54 %、对角最大 1.9 %（2026-09-15 内核改正 a1 ≠ 0 的读法后重录；首录为 8.0 %）。"},
    "B-19": {"not_comparable": ["- efund 的 EAST 输入只含真空室内壳 40 元；外壳与被动板的格林列不在 KEFIT 里（B-17 对 FreeGSNKE 覆盖它们）。",
                                "- 互感对角：efund 用矩形截面解析积分，fylite 用 16×16 细丝加圆导线自感项——对角中位差 0.83 % 即此。",
                                "- 探针只作读数：efund 沿探针长度多点平均，配对按位置与角度（74 / 76）。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_wall_vstab.py -k 'efund or b19'",
                           "# efund 侧重建：python tools/benchmark-wall-vstab.py efund-build --out <dir>（需 gfortran 与 $KEFIT_REFERENCE_BUNDLE）"],
             "conclusion": "成立：EAST 真空室内壳 40 元的格林响应与 efund 一致到磁通环 2.0e-5、网格 2.1e-7，互感非对角 p95 3.7e-3，τ₁ 差 2.4e-4；本条同时查出参考包交付的 rv6565.ddd 是算表输入 7 行错列的误读结果（差 9 % / 29 %），并修正了内核两处 EFIT 平行四边形读法。"},
    "B-20": {"not_comparable": ["- KEFIT 没有稳定性计算：本条比的是它的电磁层组装出的刚性装置，不是 KEFIT 的结论。",
                                "- 等离子体离散不同：efund 侧在 g-file 的 65² 节点上取 J，fylite 在 coarsen 1 的细丝上；16×16 与 8×8 两档之间 fylite 自己的 γ 走 1.3 %。",
                                "- 只含内壳（efund 的 EAST 输入里只有内壳）；刚性、主动线圈冻结。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_wall_vstab.py -k 'efund or b20'",
                           "# 读数重写：python tools/benchmark-wall-vstab.py kefit-readings --out <dir> [--bundle <参考包>]"],
             "conclusion": "成立：KEFIT 平衡上，efund 表组装的刚性装置 γ 676.4 s⁻¹ 与 fylite code/vstab 差 +0.28 %（8×8）/ −1.0 %（16×16），k 差 0.38 %、k_ideal 0.2–0.6 %、裕度 ±0.003，耦合梯度逐元中位 0.31 %。"},
    "B-18": {"not_comparable": ["- 可变形等离子体：FreeGSNKE 的线性化雅可比给出三组合 γ 为刚性的 2.2 倍、内壳 0.92 倍；fylite 的 code/vstab 是刚性模型，这一项无对应（读数，雅可比线性度未核）。",
                                "- 平衡是 FreeGSNKE 的反演收敛态，不是 KEFIT 的（κ 高 3.5 %）；fylite 在 KEFIT 平衡上的 γ 低 4.3 %（内壳）/ 2.2 %（三组合），只作读数。",
                                "- 主动线圈冻结（与 circuit: passive 同义）；不含反馈控制、线圈电源与快控线圈。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_wall_vstab.py -k 'registered or b18'",
                           "# 读数重写：python tools/benchmark-wall-vstab.py readings --out <dir>"],
             "conclusion": "成立：同一张平衡与同一组输入下，fylite code/vstab 的刚性垂直增长率与 FreeGSNKE 的刚性色散差 −0.006 %（内壳，709 s⁻¹）/ +0.11 %（三组合，4.27 s⁻¹），裕度差 ≤ 0.005（内核改正 a1 ≠ 0 的读法后重录；首录内壳为 +0.37 %）；FreeGSNKE 的可变形增长率另记为读数。"},
    "V-22": {"not_comparable": ["- 没有参考侧：这张形状上没有任何可达的平衡件（TEQ / TOSCA 是指针，FreeGSNKE 无 ITER 机器），本条不是对拍。",
                                "- 目标曲线是数字化件：248 点、相邻中位 67 mm、X 点处开口 322 mm（本条按尖角补齐）；它不是某个代码解出的平衡。",
                                "- 卡片无供电额定，退火不守限；电流带只是实测设计值的替身，不是机器的能力。",
                                "- κ 与 δ下 在保持收敛与电流不失真的前提下调不上去——解析剖面族的表达力边界，不是设计误差（把 enp 降到 0.5 能把 κ 推到 1.836，但那个解不收敛，四倍预算下残差反升）。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYLITE_DEVICE_DIR=dist/facts/device/iter FYLITE_KERNEL_LIB=<当前内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_inverse_shape_iter.py",
                           "# 读数重写：FYLITE_DEVICE_DIR=dist/facts/device/iter python tools/benchmark-equilibrium.py inverse-shape-iter --out docs/benchmark/readings"],
             "conclusion": "成立（自洽）：ITER 参考分离面上，code/discharge 交出的设计把分离面放在离目标中位 15.4 mm（p95 69.8、最大 123.2）处，shape_error 0.0307，R0 · a · z0 · δ上 都贴目标；κ 与 δ下 差约 3 % 与 0.055，是解析剖面族的表达力边界。这条记录的真内容是设置：129² 盒、16 遍、c4 设定点跟踪 R0、目标按 X 点尖角补齐、注入 METIS 壁作限制器、emp = 2（最后一个仍收敛的设置）。★emp 3 与 enp 0.5 的形状分都出自不收敛的解；给 enp 0.5 四倍迭代预算（2400 轮、938 s）后残差反而由 0.12 升到 0.32，可见是设置本身不稳，不是预算不够。"},
    "V-23": {"not_comparable": ["- 参考侧是两份 ITER IDM Internal Use 件里的**数值**，不是可回放的运行件；公开读者无法复算参考侧。",
                                "- 端口组按**连续环**建模，实物是 18 个约 5° 宽（环向占空比约 25 %）：该组读数已记，但不供任何对比使用。",
                                "- 被动集本身来自 CC BY 原件的**离散**：段数即原件点数（不细分），元的角度按内核 efund 两分支约定写。",
                                "- 屏蔽由门的 `screen_coils` 做（零电阻回路的 Schur 补，线圈自感取 8×8 细丝）；记录侧另用 Maxwell 共轴圆环互感 + 解析圆环自感独立自算一遍作交叉核对，两者差 +0.12 %。CREATE 用的是有限元。本仓因线圈自感取法的散布达 ±7 %，**大于**与 CREATE 的残差——所以判词是「在本仓不确定度内一致」，不是「吻合」。",
                                "- 等离子体响应完全不在本条内：CREATE 表 4.1.a 的 γ 与稳定裕度是可变形线性化响应，本条只取它那两列无等离子体时间常数。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYLITE_DEVICE_DIR=dist/facts/device/iter FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_wall_iter.py",
                           "# 读数重写：见该门抬头（code/wall 逐组跑，屏蔽用 screen_coils=1；落 docs/benchmark/readings/wall_iter.json）"],
             "conclusion": "两项都成立，但第二项走过一次弯路，两版都留在册里。**电阻侧**：真空室双壳并联环向电阻 7.6272 µΩ 对 ITER_D_22FPWQ 的 7.9 µΩ，差 −3.45 %，由两条独立算法逐位复核，且比书页原有的 8.98 µΩ 粗估更接近真值。**时间常数侧**：裸回路给 τ₁ 0.5834 s，比 CREATE 的 0.3623 s 高 57 %；四条候选解释（离散粒度 · 增厚壳 · 电阻率 · 模式定义）逐一实测证伪后，本会话先提出「CREATE 侧有传导连接」——**随即自证为错**：n = 0 环向涡流下各环本就只有互感耦合，径向连接只在两壳间重分配电流，而那已被并联电阻算进。真因在同一份件的前一页：22L4FE 第 2 页写明「All resistances (in SC coils, voltage amplifiers, connections) are neglected」，其 plasmaless 矩阵装着十一条 PF/CS 回路，而**零电阻回路保磁通、屏蔽真空室模**。以 Schur 补消去线圈后均匀模电感 5.0657 → 2.9152 µH（−42 %），τ₁ 0.5834 → 0.3418 s，对 CREATE-NL 差 −5.66 %，且本仓因线圈自感取法的区间 [0.3257, 0.3717] s **包含** CREATE 的 0.3623 与 0.3705。另测两条不影响结论：回路拓扑（12 独立线圈与 11 条真实回路逐位相同）与线圈几何来源（卡片 0.3418 s 对 22L4FE 自己的 0.3395 s）。★不去凑 τ，也不取对得最准的 a = 0.25 m 那一档（−0.44 %）当主结论。"},
    "B-21": {"not_comparable": ["- 两个代码解的不是同一个优化问题：目标函数、正则化与约束都不同；本条比的是**同一目标下各自交出的形状**，不是优化器。",
                                "- 电流不可比作判据：逆问题在电流空间欠定（实测两组差 25.6 kA·t、正解出的平衡只差毫米级）；KEFIT 的电流也只是它自己的拟合结果。",
                                "- 目标曲线是 KEFIT 的 69 点轮廓：粗（相邻点中位 48.5 mm）、上方止于 Z = +0.658（其上 X 点 +0.767）；公平窗口即为此设，两种读法都在读数件里。",
                                "- 一装置一形状一时刻；fylite 侧内部的自由边界解停在 settled（与 B-14 同一底）。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<当前内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_inverse_shape.py",
                           "# 读数重写：python tools/benchmark-equilibrium.py inverse-shape --out <dir>"],
             "conclusion": "成立：同一目标（KEFIT 边界 + 其两个 X 点）下，fylite code/discharge 交出的形状比 FreeGSNKE 反演更贴目标（公平窗口中位 1.21 mm 对 5.00 mm），其电流正解后在 KEFIT 图上的 ψ_N rms 0.0046 也最小；同时读出逆问题的零空间——两边电流差 25.6 kA·t，而三组电流给出的平衡只差毫米级。"},
    "V-21": {"not_comparable": ["- 没有第二个代码：墙电流的大小、位移与形状的响应只由恒等式约束，物理对错要对 FreeGSNKE 的非线性演化（评估 note §4 第 7 条）。",
                                "- Ip 是给定轨迹，不解等离子体自身的电路方程；不含反馈控制、电源模型与快控线圈。",
                                "- 步长受竖直不稳定模限制（γ·dt < 1）：只取内壳时 2 ms 一步没有邻近解；本条取三组无源件。",
                                "- code/forward 两种边界规则的差（约 9–11 mm）只作读数：KEFIT 的竖直位置由拟合给出，回答不了哪一种离实物近。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/evolve_free_boundary 的内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_evolve_free_boundary.py",
                           "# 读数重写：python tools/benchmark-evolve-free-boundary.py readings --out <dir>",
                           "cd $FYLITE_KERNEL && cargo test --release --lib -- evolve_free_boundary_tests the_edge_rule   # 私仓单元测试"],
             "conclusion": "成立：EAST 卡片与 KEFIT 平衡上，code/evolve_free_boundary 让三组无源件的壳模按 code/wall 的 τ₁ 衰减到 8e-15，理想导体在 Ip 升 2 % 时磁链守恒到 2e-13，回路方程在每步平衡上闭合到 2e-13，电流驱动复现电压驱动的无源件电流到 5e-9；同时读出 B-14 的节点规则答案是虚拟位置对撑着的。"},
}


# ------------------------------------------------------------------------------------------------ apply

def apply(case: Path, reruns: dict, solovev: dict, only: set[str] | None = None) -> None:
    reg = json.loads(REG.read_text(encoding="utf-8"))
    #: ★没重跑的记录沿用它上次那条 re-run（见 `reruns_from_registry`）；本次实测的覆盖它。
    carried = reruns_from_registry(reg)
    fresh = dict(reruns or {})
    if only is not None:
        stray = sorted(set(fresh) - only)
        if stray:
            raise SystemExit(f"--reruns 给了 {stray} 的实测结果，但它们不在 --only 里。\n"
                             "  ★这两个必须一致：--only 说「本次重跑了哪些」，--reruns 是那些的结果。\n"
                             "  不一致时本工具不猜——把旧结果写成今天的复测是伪造。")
        missing = sorted(only - set(fresh))
        if missing:
            raise SystemExit(f"--only 点名重跑 {missing}，但 --reruns 里没有它们的结果。")
    merged = {**carried, **fresh}
    #: ★`build()` 取的每一个键都必须有来路：registry 里沿用的，或本次 `--reruns` 实测的。
    #: 新记录第一次写册时 registry 里还没有它，只能来自 `--reruns`——这条检查让「忘了给」
    #: 在这里停住，而不是到 `report_md` 里变成一个 StopIteration。
    if (absent := sorted(k for k in NEED_RERUN if k not in merged)):
        raise SystemExit(f"这些记录 build() 要取复测结果，但 registry 里没有、`--reruns` 也没给：{absent}\n"
                         "  ★新立的记录第一次写册时必属此列：把它列进 `--only` 并在 `--reruns` 里给出本次实测。")
    if (lack := sorted(k for k, v in merged.items() if v.get("verdict") is None)):
        raise SystemExit(f"这些记录既无本次实测、registry 里也没有可沿用的 re-run：{lack}")
    #: ★本函数在 `build()` 之外也直接取 `reruns`（下面给 C-03 补那一条），一并指向合并结果；
    #: 漏了这一步会在 C-03 上 KeyError——2026-09-16 实测过一次。
    reruns = merged
    recs, reports = build(case, reruns, solovev)
    graph = [r for r in reg["@graph"] if r["id"] not in {x["id"] for x in recs}]
    by = {r["id"]: r for r in graph}
    for rid in ("record/C-06", "record/C-07", "record/B-10"):
        r = by[rid]
        r["assertion_state"], r["superseded_by"] = "retired", "record/V-16"
        note = "★★2026-09-15 并入 V-16（GS 残差读法，改判为 V）：本条的门问的是「本仓的残差判据在别人写出的平衡上读出什么」，不是对另一套模型的确认或对拍；发现逐条迁入 V-16，本条保留作历史"
        if note not in r["caveat"]:
            r["caveat"].insert(0, note)
    by["record/C-03"]["superseded_by"] = "record/B-18"
    by["record/C-03"]["assertion_state"] = "retired"
    c03_note = "★★2026-09-15（第三批）：本条由 B-18 取代——同一问题（刚性等离子体的垂直增长率与裕度）对 FreeGSNKE 可复跑，参考侧有指针与 sha256，判据有实测带"
    if c03_note not in by["record/C-03"]["caveat"]:
        by["record/C-03"]["caveat"].insert(0, c03_note)
    b10_note = "★★2026-09-15（第二批）：本条原题「同一边界与剖面下 fylite 的 GS 解」由 V-19（Solov'ev 轮廓，fylite 与 CHEASE）与 B-16（EAST 形状，fylite 对 CHEASE）立——内核当日新增 code/fixed_boundary"
    if b10_note not in by["record/B-10"]["caveat"]:
        by["record/B-10"]["caveat"].insert(1, b10_note)
    for rid in ("record/B-06", "record/B-11"):
        by[rid]["superseded_by"] = "record/B-12"
    c03 = by["record/C-03"]
    c03["findings"] = [f for f in c03["findings"] if f.get("title") != f"复测 {DATE}（本条写入时把门跑一遍）"]
    c03["findings"].append(rerun_finding(reruns["C-03"]))
    for note in ("★★2026-09-15 复测：门 `test_benchmark_toksys.py` 自 2026-09-14 起两条都 skip（`NO_TOKSYS_FOR_CASE23`：其 rzrig 锚点属已归档的 est2 装置描述，CASE-23 没有 TokSys 参考）——登记册的 0.47 % / 0.72 % / 2.97 % 是那之前 Python 路径的读数，今天不可复测",
                 "★缺口 G-4 仍在：参考侧没有数据指针与 sha256，判据没有数值带"):
        if note not in c03.get("caveat", []):
            c03.setdefault("caveat", []).insert(0, note)
    reg["@graph"] = graph + recs
    REG.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for r in recs:
        rid = r["id"].split("/")[1]
        (BM / "reports" / reports[rid]).write_text(report_md(r, REPORT_TEXT[rid]), encoding="utf-8")
    print(f"register: {len(reg['@graph'])} records; wrote {', '.join(reports.values())}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reruns", type=Path,
                    help="本次实测的复测结果 {记录号: {verdict, literal, caveat?}}；"
                         "★可省：缺的键自 registry 已有的 re-run finding 反读（连原日期一起），"
                         "这样动一条记录不必替其余记录编造复测结论")
    ap.add_argument("--only", nargs="*", metavar="REC",
                    help="本次真正重跑的记录号（须与 --reruns 的键一致）；其余一律沿用上次")
    ap.add_argument("--case", required=True, type=Path)
    ap.add_argument("--solovev", type=Path, help="solovev_fixed_boundary.json (default: recomputed by tools/benchmark-fixed-boundary.py)")
    a = ap.parse_args()
    if a.solovev:
        sv = json.loads(a.solovev.read_text(encoding="utf-8"))
    else:
        import importlib.util
        import tempfile
        spec = importlib.util.spec_from_file_location("benchmark_fixed_boundary", ROOT / "tools" / "benchmark-fixed-boundary.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as d:
            sv = mod.solovev(Path(d))
    fresh = json.loads(a.reruns.read_text(encoding="utf-8")) if a.reruns else {}
    apply(a.case, fresh, sv, set(a.only) if a.only is not None else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
