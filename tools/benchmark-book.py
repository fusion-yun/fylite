#!/usr/bin/env python3
"""校验册的生成器：写章页里的生成块、`coverage.md`、`status.md` 与 `index.jsonld`。

★★**为什么这些必须由机器写**：旧册的 `reports/README.md` 是手维护的索引，结果最后一条
记录进册时它没跟上——查得到记录、查不到索引。索引与记录不同源，就一定会漂。

★**三张生成件各答一个问题，不是同一张表的三种排版**：

  章页 `<组>/<域>.md`  这一域**对着谁量到多少** —— 散文（手写）+ 判据原文（抄录）+ 本域记录
  `coverage.md`        **够不够** —— 需求 × 记录，没有记录的需求显示为空行
  `status.md`          这些记录**还作不作数** —— 版本 / 评审 / 内核 / 新鲜度；CI 读它

★**没有记录覆盖的需求显示为空行，不省略。** 一张只列"做过什么"的表回答不了"够不够"；
空行才是缺口本身。MUST 级的空行单独计数——那是硬缺口。

★★**新鲜度不拿本机内核当基准**。`status.md` 是入库的生成件，被 `--check` 守着；它若嵌入
跑这条命令的那台机器的内核指纹，换一台机器门就红，而那不是任何人的错。基准记在
`kernel.json`——一份**有意更新**的声明件（`--bump-kernel`）。内核一换就改它，于是所有
记在旧内核上的记录当场转为 `stale`，CI 据此重跑。这就是「随内核变更自动验证」的接口。

用法::

    python tools/benchmark-book.py                 # 写全部生成件
    python tools/benchmark-book.py --check         # 只核对是否最新（门 / CI 用），不写盘
    python tools/benchmark-book.py --ci            # 列出过期与不成立的记录；有则退 1
    python tools/benchmark-book.py --bump-kernel   # 把基准内核指纹更新为本机当前的
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BM = ROOT / "docs" / "benchmark"
#: ★机器读的那一半住在 `meta/`：轴（域树 / 需求树）、判据抄录件、词表、薄索引与基准内核。
#: 给人读的那一半（README + 两张生成件 + 三组十六章）留在册子根上——目录本身就把
#: 「谁读它」说清楚，不必靠扩展名去猜。
META = BM / "meta"

BEGIN = "<!-- BEGIN GENERATED: tools/benchmark-book.py —— 勿手改 -->"
END = "<!-- END GENERATED -->"

KIND_ZH = {"verification": "验证", "benchmark": "对拍", "validation": "确认"}
VERDICT_ZH = {"pass": "成立", "fail": "不成立", "inconclusive": "未判（读数）", "unevaluated": "未评估"}
REVIEW_ZH = {"draft": "草稿", "reviewed": "已评审", "superseded": "已被取代"}


# ────────────────────────────────────────────────────────────── 读

def load(name: str) -> dict:
    return json.loads((META / name).read_text(encoding="utf-8"))


def load_records() -> list[dict]:
    """`records/*.jsonld`——一条记录一个文件。

    ★不再是一份 481 KB 的 `registry.jsonld`：那样改一条记录的 diff 会扫全库、并发改必冲突。
    ★`TEMPLATE.jsonld` 与 `retired/` 不是记录。"""
    out = []
    for p in sorted((BM / "records").glob("*.jsonld")):
        if p.name == "TEMPLATE.jsonld":
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        d["_file"] = p.name
        out.append(d)
    return out


def domains() -> list[tuple[dict, dict]]:
    """展平成 (组, 域) 对，保序。"""
    return [(g, d) for g in load("domains.jsonld")["group"] for d in g["domain"]]


def criteria_by_requirement() -> dict[str, list[dict]]:
    """抄录件里，每条需求对应的判据行（可能不止一行：SRS 把一条需求拆成几档写）。"""
    out: dict[str, list[dict]] = {}
    for row in load("transcript.jsonld")["criterion_row"]:
        for rid in row["requirement"]:
            out.setdefault(rid, []).append(row)
    return out


def kernel_reference() -> dict:
    p = META / "kernel.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def local_kernel() -> dict | None:
    """本机当前的内核指纹。★取不到是正常的——分发件里不一定带内核。"""
    lib = os.environ.get("FYLITE_KERNEL_LIB")
    cands = [pathlib.Path(lib)] if lib else []
    cands.append(ROOT / "python" / "fylite" / "_lib" / "libfylite_kernel.so")
    for p in cands:
        if p.is_file():
            return {"name": "libfylite", "path": str(p),
                    "checksum": "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()}
    return None


# ───────────────────────────────────────────────────────── 呈现层的脱敏

_ROLE = re.compile(r"\{(?:ref|cite|numref|eq|doc)\}`([^`]*)`")


def defang(text: str) -> str:
    """抄录件逐字保留 SRS 的 MyST 角色；**渲染时**必须脱成普通代码号。

    ★那些 `{ref}` / `{cite}` 的锚点在本仓不存在，原样渲染会让 `myst build --strict` 变红——
    而红的原因会显示成本册的错，其实是抄来的字。脱敏只动呈现，不动抄录件。"""
    t = _ROLE.sub(lambda m: f"`{m.group(1)}`", text)
    #: 表格单元里的竖线会把一行拆成两格；抄来的判据要进表就得转义
    return t


def cell(text: str) -> str:
    return defang(text).replace("|", "\\|").replace("\n", " ").strip()


# ────────────────────────────────────────────────────────────── 章页

def chapter_block(g: dict, d: dict, reqs: dict[str, dict], recs: list[dict],
                  crit: dict[str, list[dict]], srs_ver: dict[str, str]) -> str:
    mine = [r for r in recs if r.get("domain") == d["id"]]
    by_req = {rid: [r for r in mine if rid in (r.get("requirement") or [])] for rid in d["requirement"]}

    L = [BEGIN, ""]

    # ——— 判据：抄录，不是引用
    L += [f"### 判据（抄自 `{g['srs']}` v{srs_ver.get(g['srs'], '?')}）", "",
          ":::{note} 这一节是**抄录**，不是引用",
          f"上游 `{g['srs']}` 标着 `distribution: internal`——本册的读者打不开它。"
          "一条读者打不开的引用没有分量，所以判据原文抄在这里，逐字。",
          "",
          "抄录件 `transcript.jsonld` 记着源的版本与 sha256；源一变，"
          "`python tools/benchmark-transcribe.py --check` 就红，逼人重抽。",
          ":::", ""]

    for rid in d["requirement"]:
        r = reqs[rid]
        rows = crit.get(rid, [])
        head = f"**`{rid}` · {r['title']}** — {r['level']}"
        if rows:
            methods = " / ".join(sorted({x["method"] for x in rows}))
            L.append(f"{head} · 验证方法：{methods}")
            L.append("")
            for x in rows:
                lab = f"（{x['label']}）" if x["label"] != rid else ""
                L.append(f"> {lab}{defang(x['criteria'])}")
                L.append("")
        else:
            #: ★SRS 自己的验证矩阵没给这一条判据。这是**上游的缺口**，照实写出来——
            #: 一条没有判据的需求，本册无从验起，遮住它等于替上游掩过。
            L.append(f"{head}")
            L.append("")
            L.append(f"> ★`{g['srs']}` 的〈验证矩阵〉**没有这一条的判据行**。"
                     f"上游追溯写的是「{r.get('upstream', '—')}」。"
                     "没有判据就无从验起——这是上游的缺口，记在这里等它补。")
            L.append("")

    # ——— 本域的记录
    L += ["### 本域的记录", ""]
    if mine:
        L += ["| 记录 | 类 | 判决 | 参考 | 记录版本 | 评审 |",
              "| :--- | :--- | :--- | :--- | :--- | :--- |"]
        for r in sorted(mine, key=lambda x: x["id"]):
            p = r.get("provenance", {})
            refs = " · ".join(x.get("name", "?") for x in (r.get("compared_reference") or []))
            L.append(f"| [`{r['id'].split('/')[-1]}`](../records/{r['_file']}) "
                     f"| {KIND_ZH.get(r.get('comparison_kind'), '?')} "
                     f"| {VERDICT_ZH.get(r.get('overall_verdict'), '?')} "
                     f"| {cell(refs) or '—'} "
                     f"| {p.get('record_version', '—')} "
                     f"| {REVIEW_ZH.get(p.get('review_status'), '—')} |")
        L.append("")
    else:
        L += ["★**本域尚无记录。** 这一行不是排版占位，是缺口本身：上面抄录的判据，"
              "本册还没有拿出任何一条对着外部答案量过的记录来回应。", ""]

    # ——— 缺口
    open_must = [rid for rid in d["requirement"]
                 if reqs[rid]["level"] == "MUST" and not by_req[rid]]
    L += ["### 缺口", ""]
    if open_must:
        L += [f"本域 **MUST 级空缺 {len(open_must)} 条**——SRS 写的是「必须」，而本册没有任何记录覆盖：", ""]
        L += [f"- `{rid}` {reqs[rid]['title']}" for rid in open_must]
        L.append("")
    else:
        L += ["本域没有 MUST 级空缺。", ""]

    L.append(END)
    return "\n".join(L)


def write_chapter(path: pathlib.Path, block: str) -> bool:
    """把生成块塞进章页的标记之间。★手写的散文在标记之外，生成器不碰它。"""
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{path.relative_to(ROOT)} 里没有生成块标记（{BEGIN} … {END}）")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    new = head + block + tail
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


# ─────────────────────────────────────────────────────────── coverage.md

def coverage_md(reqs: dict[str, dict], recs: list[dict], doms: list[tuple[dict, dict]],
                crit: dict[str, list[dict]]) -> str:
    by_req: dict[str, list[dict]] = {rid: [] for rid in reqs}
    orphan: list[tuple[str, str]] = []
    for rec in recs:
        for rid in rec.get("requirement") or []:
            if rid in by_req:
                by_req[rid].append(rec)
            else:
                #: ★记录引了需求树里没有的号——不静默忽略：要么 SRS 改了要重抽，要么号写错了
                orphan.append((rec.get("id", rec["_file"]), rid))

    total = len(reqs)
    covered = sum(1 for v in by_req.values() if v)
    must_open = [rid for rid, r in reqs.items() if r["level"] == "MUST" and not by_req[rid]]
    no_crit = [rid for rid in reqs if not crit.get(rid)]

    L = ["---", "title: 需求覆盖 (Requirement coverage)", "---", "",
         "# 需求覆盖 (Requirement coverage)", "",
         "<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。手维护的索引一定会与记录"
         "漂开——旧册的 reports/README.md 就是这么漏掉最后一条的。 -->", "",
         "这一页只答一个问题：**够不够。** 每条需求一行，没有记录覆盖它的显示为空行——"
         "★空行不是排版，是缺口本身。按谁答什么问题读：这一页答「够不够」，"
         "各域的章页答「对着谁量到多少」，[`status.md`](status.md) 答「这些记录还作不作数」。", "",
         f"- 生成于 (recorded)：{datetime.date.today().isoformat()}",
         f"- 需求 (requirements)：**{total}** 条，其中 **MUST {sum(1 for r in reqs.values() if r['level'] == 'MUST')}** 条",
         f"- 已有记录覆盖 (covered)：**{covered}** 条（{covered * 100 // total if total else 0} %）",
         f"- ★**MUST 级空缺 (open MUST)：{len(must_open)} 条**"]
    if no_crit:
        L.append(f"- ★上游未给判据 (no criterion in the SRS)：**{len(no_crit)}** 条")
    L.append("")

    for g, d in doms:
        L += [f"## {g['title']['zh']} · {d['title']['zh']}", "",
              f"{d['question']}　→ [本域章页]({d['path']})", "",
              "| 需求 | 级别 | 标题 | 覆盖它的记录 | 类 | 判决 |",
              "| :--- | :--- | :--- | :--- | :--- | :--- |"]
        for rid in d["requirement"]:
            r = reqs[rid]
            hit = by_req[rid]
            if hit:
                names = " · ".join(f"`{x['id'].split('/')[-1]}`" for x in hit)
                kinds = " · ".join(KIND_ZH.get(x.get("comparison_kind"), "?") for x in hit)
                verds = " · ".join(VERDICT_ZH.get(x.get("overall_verdict"), "?") for x in hit)
            else:
                names = kinds = verds = "—"
            L.append(f"| `{rid}` | {r['level']} | {cell(r['title'])} | {names} | {kinds} | {verds} |")
        L.append("")

    L += ["## MUST 级空缺 (open MUST requirements)", "",
          "★这些是**硬缺口**：SRS 写的是「必须」，而本册没有任何记录覆盖它们。", ""]
    if must_open:
        L += ["| 需求 | 域 | 标题 |", "| :--- | :--- | :--- |"]
        where = {rid: d for _, d in doms for rid in d["requirement"]}
        for rid in must_open:
            L.append(f"| `{rid}` | {where[rid]['title']['zh']} | {cell(reqs[rid]['title'])} |")
    else:
        L.append("没有。")
    L.append("")

    if no_crit:
        L += ["## 上游未给判据 (requirements the SRS gives no criterion for)", "",
              "★这些需求在 SRS 的〈验证矩阵〉里**没有判据行**。没有判据就无从验起——"
              "这是上游的缺口，不是本册的，照实记在这里等它补。", ""]
        L += [f"- `{rid}` {cell(reqs[rid]['title'])}" for rid in no_crit]
        L.append("")

    if orphan:
        L += ["## ★记录引了需求树里没有的号", ""]
        L += [f"- `{a}` → `{b}`" for a, b in orphan]
        L.append("")
    return "\n".join(L)


# ───────────────────────────────────────────────────────────── status.md

def freshness(rec: dict, ref: dict) -> str:
    """`current` / `stale` / `unknown`——记录跑在哪个内核上，与基准内核比。"""
    got = (rec.get("run") or {}).get("kernel") or {}
    if not got.get("checksum") or not ref.get("checksum"):
        return "unknown"
    return "current" if got["checksum"] == ref["checksum"] else "stale"


def status_md(reqs: dict[str, dict], recs: list[dict], doms: list[tuple[dict, dict]]) -> str:
    ref = kernel_reference()
    fr = {r["id"]: freshness(r, ref) for r in recs}
    n = len(recs)

    verd ={k: sum(1 for r in recs if r.get("overall_verdict") == k) for k in VERDICT_ZH}
    rev = {k: sum(1 for r in recs if (r.get("provenance") or {}).get("review_status") == k) for k in REVIEW_ZH}
    fresh = {k: sum(1 for v in fr.values() if v == k) for k in ("current", "stale", "unknown")}

    L = ["---", "title: 验证状态 (Verification status)", "---", "",
         "# 验证状态 (Verification status)", "",
         "<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。 -->", "",
         "这一页只答一个问题：**这些记录还作不作数。** 一条记录成立过，不等于它现在还成立——"
         "内核换了，它量的那个数就可能已经不是现在算出来的那个了。"
         "★所以每条记录记着它**跑在哪个内核上**，这一页拿它与基准内核比：不一致即 `stale`，等着重跑。", "",
         "## 基准内核 (reference kernel)", ""]

    if ref.get("checksum"):
        L += [f"- `{ref.get('name', 'libfylite')}` **{ref['checksum'][:23]}…**",
              f"- 声明于 (recorded)：{ref.get('recorded', '—')}"]
    else:
        L += ["- ★**尚未声明。** 没有基准就判不了新鲜度，所有记录一律记 `unknown`。",
              "  用 `python tools/benchmark-book.py --bump-kernel` 声明本机当前的内核指纹。"]
    L += ["",
          ":::{note} 为什么基准是一份**声明件**，不是本机当场算的指纹",
          "本页入库并受 `--check` 守。它若嵌入跑命令那台机器的内核指纹，换一台机器门就红——"
          "而那不是任何人的错。基准记在 `kernel.json` 里，**有意更新**：内核一换就改它，"
          "于是所有记在旧内核上的记录当场转 `stale`，CI 据此重跑。",
          ":::", "",
          "## 总览 (overview)", "",
          f"- 记录 (records)：**{n}** 条",
          f"- 判决 (verdict)：成立 {verd['pass']} · 不成立 **{verd['fail']}** · "
          f"未判 {verd['inconclusive']} · 未评估 {verd['unevaluated']}",
          f"- 新鲜度 (freshness)：当前 {fresh['current']} · **过期 {fresh['stale']}** · 未知 {fresh['unknown']}",
          f"- 评审 (review)：已评审 {rev['reviewed']} · 草稿 {rev['draft']} · 已被取代 {rev['superseded']}",
          ""]
    known = [r for r in recs if (r.get("provenance") or {}).get("open_defect")]
    if known:
        L += ["## 已裁定保留的缺口 (retained open defects)", "",
              "★★这些记录判 **fail**，而且**有意留着**——不是没人管，是量化清楚之后裁定先不改。",
              "",
              "★**它们与「新冒出来的失败」分开计**：`--ci` 对前者退 3、对后者退 1。"
              "若两者混在一个退出码里，红就成了常态，而常态的红没有人看——"
              "真正新出的失败会被它盖住。", ""]
        for r in known:
            L += [f"### `{r['id'].split('/')[-1]}`", "",
                  (r.get("provenance") or {})["open_defect"], ""]
    if n == 0:
        L += ["★**本册尚无记录。** 这一页此刻的用处不是报成绩，是把闸子摆在记录进来之前："
              "每一条进来的记录都必须自带版本、变更、评审与它跑的那个内核，"
              "否则 `python/tests/test_benchmark_register.py` 不收。", ""]

    L += ["## 按域 (by domain)", "",
          "| 组 | 域 | 需求 | 覆盖 | 记录 | 成立 | 不成立 | 过期 |",
          "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for g, d in doms:
        mine = [r for r in recs if r.get("domain") == d["id"]]
        cov = sum(1 for rid in d["requirement"]
                  if any(rid in (r.get("requirement") or []) for r in mine))
        L.append(f"| {g['title']['zh']} | [{d['title']['zh']}]({d['path']}) "
                 f"| {len(d['requirement'])} | {cov} | {len(mine)} "
                 f"| {sum(1 for r in mine if r.get('overall_verdict') == 'pass')} "
                 f"| {sum(1 for r in mine if r.get('overall_verdict') == 'fail')} "
                 f"| {sum(1 for r in mine if fr[r['id']] == 'stale')} |")
    L.append("")

    L += ["## 记录明细 (records)", ""]
    if recs:
        L += ["| 记录 | 域 | 类 | 判决 | 版本 | 末次修订 | 评审 | 跑在内核 | 新鲜度 |",
              "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"]
        for r in sorted(recs, key=lambda x: x["id"]):
            p = r.get("provenance") or {}
            k = (r.get("run") or {}).get("kernel") or {}
            L.append(f"| `{r['id'].split('/')[-1]}` | {r.get('domain', '—')} "
                     f"| {KIND_ZH.get(r.get('comparison_kind'), '?')} "
                     f"| {VERDICT_ZH.get(r.get('overall_verdict'), '?')} "
                     f"| {p.get('record_version', '—')} | {p.get('revised', p.get('recorded', '—'))} "
                     f"| {REVIEW_ZH.get(p.get('review_status'), '—')} "
                     f"| `{k.get('checksum', '—')[:19]}…` | {fr[r['id']]} |")
    else:
        L.append("（尚无记录）")
    L.append("")

    L += ["## 接 CI/CD (wiring this into CI)", "",
          "本页与它背后的记录是为流水线准备的，接法只有三条命令：", "",
          "```bash",
          "python tools/benchmark-transcribe.py --check   # 上游 SRS 动了没有（动了就重抽判据）",
          "python tools/benchmark-book.py --check         # 生成件是不是最新的",
          "python tools/benchmark-book.py --ci            # 有过期或不成立的记录就退 1",
          "```", "",
          "★**内核变更怎么触发重验**：内核换了之后跑 `--bump-kernel` 更新 `kernel.json`，"
          "所有记在旧内核上的记录当场转 `stale`；`--ci` 退 1 并列出**每条过期记录该重跑的那道门**"
          "（记录的 `run.realizes` 里点名的 pytest 目标），流水线照着跑一遍，"
          "重跑后把新的内核指纹与读数写回记录、记一条 `change`、退回 0。", "",
          "★★**退出码分四档**，因为「要处理」与「已知道」不是一回事：", "",
          "| 码 | 意思 | 流水线该做什么 |",
          "| :--- | :--- | :--- |",
          "| `0` | 全部当前且成立 | 放行 |",
          "| `1` | 有**过期**（内核换了，必须重验）或**未裁定**的不成立 | 拦下 |",
          "| `3` | 只剩**已裁定保留**的缺口 | 自己决定；缺口与理由都印在上面 |",
          "| `2` | 前提不在（如抄录件的源不在此检出） | 按环境问题处理，不是判决 |", "",
          "★**为什么 3 要与 1 分开**：一条量化清楚、归属明确、有人裁定保留的缺口，留在册上是**有用**的；"
          "但它若也让流水线红，红就成了常态，而常态的红没有人看——真正新出现的失败会被它盖住。"
          "要把一条 fail 挪进这一档，得在记录的 `provenance.open_defect` 里写明**谁、何时、为什么**保留；"
          "一个布尔挡不住下一个人把它当成陈年噪声删掉。", ""]
    return "\n".join(L)


def index_jsonld(reqs: dict[str, dict], recs: list[dict], doms: list[tuple[dict, dict]]) -> dict:
    ref = kernel_reference()
    by_req = {rid: [r for r in recs if rid in (r.get("requirement") or [])] for rid in reqs}
    return {
        "@context": "context.jsonld",
        "id": "benchmark/index",
        "type": "spo:InformationContentEntity",
        "title": {"zh": "本册记录索引", "en": "Index of records"},
        "abstract": {"zh": "★生成件，勿手改：`python tools/benchmark-book.py`。"},
        "recorded": datetime.date.today().isoformat(),
        "statistics": {
            "groups": len({g["id"] for g, _ in doms}),
            "domains": len(doms),
            "requirements": len(reqs),
            "covered": sum(1 for v in by_req.values() if v),
            "open_must": sum(1 for rid, r in reqs.items() if r["level"] == "MUST" and not by_req[rid]),
            "records": len(recs),
            "stale": sum(1 for r in recs if freshness(r, ref) == "stale"),
            "failing": sum(1 for r in recs if r.get("overall_verdict") == "fail"),
        },
        "record": [
            {"id": r["id"], "domain": r.get("domain"), "path": f"records/{r['_file']}",
             "comparison_kind": r.get("comparison_kind"), "overall_verdict": r.get("overall_verdict"),
             "requirement": r.get("requirement"),
             "record_version": (r.get("provenance") or {}).get("record_version"),
             "review_status": (r.get("provenance") or {}).get("review_status"),
             "freshness": freshness(r, ref)}
            for r in sorted(recs, key=lambda x: x["id"])
        ],
    }


# ────────────────────────────────────────────────────────────── 主流程

def build() -> dict[pathlib.Path, str]:
    reqs = {r["id"]: r for r in load("requirements.jsonld")["requirement"]}
    recs = load_records()
    doms = domains()
    crit = criteria_by_requirement()
    srs_ver = {s["id"]: s["version"] for s in load("transcript.jsonld")["source"]}

    out: dict[pathlib.Path, str] = {
        BM / "coverage.md": coverage_md(reqs, recs, doms, crit),
        BM / "status.md": status_md(reqs, recs, doms),
        META / "index.jsonld": json.dumps(index_jsonld(reqs, recs, doms), ensure_ascii=False, indent=1) + "\n",
    }
    for g, d in doms:
        out[BM / d["path"]] = chapter_block(g, d, reqs, recs, crit, srs_ver)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只核对生成件是否最新，不写盘")
    ap.add_argument("--ci", action="store_true", help="列出过期与不成立的记录；有则退 1")
    ap.add_argument("--bump-kernel", action="store_true", help="把基准内核指纹更新为本机当前的")
    a = ap.parse_args()

    if a.bump_kernel:
        k = local_kernel()
        if k is None:
            print("本机取不到内核（设 $FYLITE_KERNEL_LIB 指向 libfylite_kernel.so）", file=sys.stderr)
            return 2
        k["recorded"] = datetime.date.today().isoformat()
        k["comment"] = ("★基准内核：本册以它为「当前」。内核一换就更新本文件——"
                        "所有记在旧内核上的记录当场转 stale，CI 据此重跑。")
        k.pop("path", None)
        (META / "kernel.json").write_text(json.dumps(k, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"kernel.json → {k['checksum'][:23]}…")
        return 0

    if a.ci:
        recs = load_records()
        ref = kernel_reference()
        #: ★★**已裁定保留的负面结果，与新冒出来的失败，不能混在一个退出码里。**
        #: 2026-09-16 用户裁定「不改内核，保留负面结果」——一条量化的、归属明确的缺口挂在册上
        #: 是**有用**的。但若它也让流水线红，那么红就成了常态，常态的红没有人看，
        #: 真正新出现的失败于是被它盖住。所以分三档：
        #:   0  干净
        #:   1  **要处理**：过期（内核换了，必须重验）或**未裁定**的不成立
        #:   3  只剩**已裁定保留**的缺口——报出来，流水线自己决定放不放行
        stale = [r for r in recs if freshness(r, ref) == "stale"]
        failing = [r for r in recs if r.get("overall_verdict") == "fail"]
        known = [r for r in failing if (r.get("provenance") or {}).get("open_defect")]
        fresh_fail = [r for r in failing if r not in known]

        for r in stale:
            print(f"★{r['id']}：**过期**——它跑的内核已不是基准内核，读数不再作数")
            for gate in (r.get("run") or {}).get("realizes", []):
                print(f"    重跑：pytest {gate['name']}")
        for r in fresh_fail:
            print(f"★{r['id']}：**不成立**，且未经裁定保留")
            print("    这不是重跑能变绿的：判据没过。要么修，要么裁定保留"
                  "（记录里写 provenance.open_defect 与保留的理由）。")
        for r in known:
            p = r.get("provenance") or {}
            print(f"◇{r['id']}：已裁定保留的缺口 — {p.get('open_defect')}")

        if stale or fresh_fail:
            return 1
        if known:
            print(f"{len(recs)} 条记录：无过期、无新的不成立；"
                  f"另有 {len(known)} 条**已裁定保留**的缺口（退 3）")
            return 3
        print(f"{len(recs)} 条记录：无过期、无不成立")
        return 0

    out = build()
    if a.check:
        stale = []
        for p, text in out.items():
            if p.suffix == ".md" and p.name not in ("coverage.md", "status.md"):
                cur = p.read_text(encoding="utf-8") if p.is_file() else ""
                if BEGIN not in cur or END not in cur:
                    stale.append(p)
                    continue
                block = BEGIN + cur.split(BEGIN, 1)[1].split(END, 1)[0] + END
                if block != text:
                    stale.append(p)
            else:
                if not p.is_file() or p.read_text(encoding="utf-8") != text:
                    stale.append(p)
        if stale:
            for p in stale:
                print(f"已过期：{p.relative_to(ROOT)}", file=sys.stderr)
            print("跑 `python tools/benchmark-book.py` 重写", file=sys.stderr)
            return 1
        print("the generated pages are current")
        return 0

    changed = []
    for p, text in out.items():
        if p.suffix == ".md" and p.name not in ("coverage.md", "status.md"):
            if write_chapter(p, text):
                changed.append(p)
        else:
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                p.write_text(text, encoding="utf-8")
                changed.append(p)
    for p in changed:
        print(f"wrote {p.relative_to(ROOT)}")
    if not changed:
        print("nothing to write — already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
