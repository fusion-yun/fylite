#!/usr/bin/env python3
"""抄录器：把 FYTOK SRS 的判据**原文**抄进 `docs/benchmark/transcript.jsonld`。

★★**为什么是抄录而不是引用**。`FYTOK-SRS-03` / `-04` 的文件头都写着
`distribution: internal`。本册是**公开**登记册，它的读者打不开那两份文件——于是
「本条覆盖 `FR-EQ-016`」对他们只是一个不可解的记号。本册 README 立的规矩是「源码
不公开，所以『我们测过了』没有分量，能替代它的只有可复算的记录」；同一条逻辑打在
引用上：**需求不公开，引用就没有分量**。所以判据原文抄进来，读者当场能读。

★★**抄录的代价是漂，所以必须配这道工具**。抄来的字不会跟着源走，而两份 SRS 都还是
`status: WD`（SRS-03 v0.43 / SRS-04 v0.11，都在改）。于是抄录件记下每份源的 **版本号
与 sha256**，`--check` 一比就知道源动没动；源动了门就红，逼人重抽。手抄一次然后忘掉，
比引用更坏——引用至少永远指向最新版。

★**抄录件逐字保留，不做清洗**。`{ref}`…`` / `{cite}`…`` 这些 MyST 角色原样留在
transcript 里；把它们脱成普通代码号是**呈现层**的事（`tools/benchmark-book.py` 渲染时
做），因为那些交叉引用的锚点在本仓不存在，直接渲染会让 `myst build --strict` 变红。

用法::

    python tools/benchmark-transcribe.py            # 重抽，写 transcript.jsonld
    python tools/benchmark-transcribe.py --check    # 只核对（门用），不写盘

源的位置：`$FYTOK_SRS_DIR`，否则在仓的兄弟目录里找 `fytok/docs/design`。
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
OUT = ROOT / "docs" / "benchmark" / "meta" / "transcript.jsonld"

SRS = {
    "FYTOK-SRS-03": ("FYTOK-SRS-03_fyeq_equilibrium.md", "fyeq", "平衡求解器 (Equilibrium solver)"),
    "FYTOK-SRS-04": ("FYTOK-SRS-04_fytrans_transport.md", "fytrans", "输运求解器 (Transport solver)"),
}
ID_RE = re.compile(r"\b((?:FR|NR)-(?:EQ|TR)-\d{3})\b")


def srs_dir() -> pathlib.Path | None:
    """SRS 在另一个仓（fytok）。它不在场是**正常**的——本仓的分发件里没有它。"""
    if os.environ.get("FYTOK_SRS_DIR"):
        p = pathlib.Path(os.environ["FYTOK_SRS_DIR"])
        return p if p.is_dir() else None
    #: ★逐级往上找，不写死层数：本仓可能是主检出，也可能是 `.claude/worktrees/<名>/` 下
    #: 的一份工作树——后者离工作区根多三层，写死层数就找不到。
    for up in ROOT.parents:
        p = up / "fytok" / "docs" / "design"
        if p.is_dir():
            return p
    return None


#: 验证矩阵的「需求」格里，第二个号常写成**裸三位数**：`FR-TR-001/002`、`FR-EQ-007..009`。
#: ★这必须解开。2026-09-16 实测：不解开时 `FR-EQ-008` / `-009` / `FR-TR-002` / `-004` 四条
#: 会被当成「没有判据原文」，在覆盖表上显示成空缺——而那是抄录器的错，不是真缺口。
#: **一个把工具缺陷显示成项目缺口的表，比没有表更坏。**
CONT_RE = re.compile(r"((?:FR|NR)-(?:EQ|TR))-(\d{3})((?:\s*(?:/|\.\.|,|、|-|–|—)\s*\d{3})+)")


def expand(label: str) -> list[str]:
    """一行验证矩阵的「需求」格：`FR-EQ-001` · `FR-TR-001/002` · `FR-EQ-007..009`
    · `FR-EQ-013 (a)-(d)(f)`。★`..` 是**区间**（展开中间各条），`/` 与顿号是**枚举**。"""
    out: list[str] = []
    for m in CONT_RE.finditer(label):
        prefix, first, tail = m.group(1), int(m.group(2)), m.group(3)
        nums = [int(x) for x in re.findall(r"\d{3}", tail)]
        if ".." in tail or "–" in tail or "—" in tail:
            for a, b in zip([first] + nums, nums):
                out += [f"{prefix}-{n:03d}" for n in range(a, b + 1)]
        else:
            out += [f"{prefix}-{n:03d}" for n in [first] + nums]
    out += ID_RE.findall(label)
    seen: dict[str, None] = {}
    for x in out:
        seen.setdefault(x, None)
    return list(seen)


def section(lines: list[str], pattern: str) -> str:
    """抄一节的正文：从标题行到下一个同级或更高级标题之间，逐字。"""
    for i, ln in enumerate(lines):
        if re.match(pattern, ln):
            depth = len(ln) - len(ln.lstrip("#"))
            j = i + 1
            body: list[str] = []
            while j < len(lines):
                m = re.match(r"^(#{1,6}) ", lines[j])
                if m and len(m.group(1)) <= depth:
                    break
                body.append(lines[j])
                j += 1
            #: 末尾的 `(anchor)=` 之类 MyST 目标不是判据正文，抄进来只会是噪声
            while body and (not body[-1].strip() or re.match(r"^\(.+\)=\s*$", body[-1].strip())):
                body.pop()
            return "\n".join(body).strip()
    return ""


def rows(lines: list[str]) -> list[dict]:
    """抄〈验证矩阵〉的每一行：需求 / 方法 / 判据 / 证据。"""
    start = next((i for i, l in enumerate(lines) if re.match(r"^## 验证矩阵", l)), None)
    if start is None:
        return []
    out = []
    for ln in lines[start:]:
        if re.match(r"^## ", ln) and not re.match(r"^## 验证矩阵", ln):
            break
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in ("需求",) or set(cells[0]) <= set(":- "):
            continue
        ids = expand(cells[0])
        if not ids:
            continue
        out.append({"label": cells[0], "requirement": ids,
                    "method": cells[1], "criteria": cells[2], "evidence": cells[3]})
    return out


def transcribe(d: pathlib.Path) -> dict:
    source, basis, rowset = [], [], []
    for sid, (fname, component, title) in SRS.items():
        p = d / fname
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        lines = text.splitlines()
        m = re.search(r"^version: ['\"]?([^'\"\n]+)['\"]?$", text, re.M)
        st = re.search(r"^status: (\S+)$", text, re.M)
        source.append({
            "id": sid, "title": title, "component": component,
            "path": f"fytok docs/design/{fname}",
            "version": (m.group(1).strip() if m else "?"),
            "status": (st.group(1) if st else "?"),
            "checksum": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "distribution": "internal",
        })
        b = section(lines, r"^### 验证基准")
        if b:
            basis.append({"srs": sid, "text": b})
        for r in rows(lines):
            r["srs"] = sid
            rowset.append(r)
    return {
        "@context": "context.jsonld",
        "id": "benchmark/transcript",
        "type": "spo:InformationContentEntity",
        "title": {"zh": "判据抄录件：自 FYTOK SRS 逐字抄来",
                  "en": "Transcribed acceptance criteria, verbatim from the FYTOK SRS"},
        "abstract": {
            "zh": "★生成件，勿手改：`python tools/benchmark-transcribe.py`。"
                  "★**抄录不是引用**：上游两份 SRS 都是 `distribution: internal`，"
                  "公开册的读者打不开它们，所以判据原文抄进来。"
                  "★抄录会漂，所以每份源记下版本号与 sha256；源一变 `--check` 就红，逼人重抽。"
                  "★正文逐字保留（含 `{ref}` / `{cite}` 角色），脱敏在呈现层做。",
            "en": "Generated, verbatim transcription. The upstream SRS are internal-distribution, "
                  "so a public register must transcribe rather than cite. Each source carries its "
                  "version and sha256 so drift turns the gate red.",
        },
        "source": source,
        "verification_basis": basis,
        "criterion_row": rowset,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只核对是否与源一致，不写盘")
    a = ap.parse_args()

    d = srs_dir()
    if d is None:
        #: ★源不在场**不是**「一切正常」。抄录件若已在盘上，就报出它抄的是哪个版本——
        #: 一句「skip」而不说抄的是哪一版，等于没说。
        if OUT.is_file():
            cur = json.loads(OUT.read_text(encoding="utf-8"))
            have = " · ".join(f"{s['id']} v{s['version']}" for s in cur.get("source", []))
            print(f"SRS 源不在此检出（设 $FYTOK_SRS_DIR 指向 fytok/docs/design 可重抽）。"
                  f"盘上的抄录件抄自：{have}", file=sys.stderr)
            return 2
        print("SRS 源不在此检出，且盘上没有抄录件", file=sys.stderr)
        return 2

    fresh = transcribe(d)
    if a.check:
        if not OUT.is_file():
            print("transcript.jsonld 不在盘上：跑 `python tools/benchmark-transcribe.py`", file=sys.stderr)
            return 1
        cur = json.loads(OUT.read_text(encoding="utf-8"))
        drift = [(s["id"], s["version"], s["checksum"][:19])
                 for s, f in zip(cur.get("source", []), fresh["source"])
                 if s.get("checksum") != f["checksum"]]
        if drift or cur.get("criterion_row") != fresh["criterion_row"] \
                or cur.get("verification_basis") != fresh["verification_basis"]:
            for sid, ver, cs in drift:
                print(f"★源已变：{sid} 抄录件记的是 v{ver} / {cs}…，当前源已不是它", file=sys.stderr)
            print("抄录件已与 SRS 源漂开：跑 `python tools/benchmark-transcribe.py` 重抽", file=sys.stderr)
            return 1
        print("transcript.jsonld is current")
        return 0

    fresh["recorded"] = datetime.date.today().isoformat()
    OUT.write_text(json.dumps(fresh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = len(fresh["criterion_row"])
    print(f"wrote {OUT.relative_to(ROOT)} — {len(fresh['source'])} 份源 · {n} 行判据")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
