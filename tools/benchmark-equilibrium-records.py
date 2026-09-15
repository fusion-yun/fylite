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


def rerun_finding(r: dict) -> dict:
    return finding(f"复测 {DATE}（本条写入时把门跑一遍）", r["verdict"], r["literal"], kind="re-run", caveat=r.get("caveat"))


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
         f"| **复测** | {DATE}：{verdict[rerun['verdict']]}——{rerun.get('deviation_literal', '')} |", "",
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
             "conclusion": "成立：同一张 EAST 卡片上，fylite code/wall 与 FreeGSNKE 的无源 L/R 本征模 τ₁ 在内壳 · 外壳 · 被动板 · 三组合上差 ≤ 0.08 %（12.76 / 13.10 / 400.6 / 413.5 ms），互感矩阵非对角 p95 ≤ 0.54 %。"},
    "B-18": {"not_comparable": ["- 可变形等离子体：FreeGSNKE 的线性化雅可比给出三组合 γ 为刚性的 2.2 倍、内壳 0.92 倍；fylite 的 code/vstab 是刚性模型，这一项无对应（读数，雅可比线性度未核）。",
                                "- 平衡是 FreeGSNKE 的反演收敛态，不是 KEFIT 的（κ 高 3.5 %）；fylite 在 KEFIT 平衡上的 γ 低 4.3 %（内壳）/ 2.2 %（三组合），只作读数。",
                                "- 主动线圈冻结（与 circuit: passive 同义）；不含反馈控制、线圈电源与快控线圈。"],
             "rerun_cmd": ["cd $FYLITE_PUBLIC", "FYDOC_ORACLE=<fydoc cases/> FYLITE_DEVICE_DIR=dist/facts/device/east FYLITE_KERNEL_LIB=<带 code/wall 的内核库> \\",
                           "  uv run --no-project --with numpy --with scipy --with pyyaml --with matplotlib --with contourpy --with pytest \\",
                           "  python -m pytest python/tests/test_benchmark_wall_vstab.py -k 'registered or b18'",
                           "# 读数重写：python tools/benchmark-wall-vstab.py readings --out <dir>"],
             "conclusion": "成立：同一张平衡与同一组输入下，fylite code/vstab 的刚性垂直增长率与 FreeGSNKE 的刚性色散差 0.37 %（内壳，711 s⁻¹）/ 0.12 %（三组合，4.27 s⁻¹），裕度差 ≤ 0.005；FreeGSNKE 的可变形增长率另记为读数。"},
}


# ------------------------------------------------------------------------------------------------ apply

def apply(case: Path, reruns: dict, solovev: dict) -> None:
    reg = json.loads(REG.read_text(encoding="utf-8"))
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
    ap.add_argument("--reruns", required=True, type=Path)
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
    apply(a.case, json.loads(a.reruns.read_text(encoding="utf-8")), sv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
