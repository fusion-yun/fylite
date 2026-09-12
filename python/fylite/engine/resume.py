"""续跑：读一份记录的 ``fylite:state``，摆回下一次调用的参数。

★★**为什么 Python 这一侧也要有它。** `FYL-DESIGN-18` U-19 说的是「同一份文档集在
别处继续」——桌面、Python、另一台浏览器认**同一份**记录。那句话在 2026-09-12 之前
只有浏览器一端成立（`-18` G-4）：`fy run` 没有 `--resume-from`，本包没有 ``resume=``。
CLI 那一半已经落地（`rust/fylite_runtime/src/resume.rs`），这一份是 Python 的那一半，
**读的是同一个 ``fylite:state`` 子树**，所以两边不会各自长出一套续跑语义。

★**本模块不算任何东西**，也不认识任何一个物理量：它把记录里写好的交接单取出来，
交给调用方去摆。配对（`X_out` → `X_in`、`t_end` → `t_start` …）是**写记录的那一侧**
按内核声明做的——见 Rust 那份的抬头。这一侧只读结果，所以两边不可能配错成两样。

★★**它有一条说不出口的限制，而那条限制要说出口**：`code/evolve` 的三条滞后量
（`psi_prev` / `sigma_prev` / `exch_prev`）**交不过去**——内核从 ``evolve/fylite:*``
读它们，却写在自己的原始条目块里，而中间层只把**声明过的表**里的槽压进扁平树
（`FYL-DESIGN-16` F-2 / G-8）。写记录的那一侧因此设 ``lag_reset``（内核自己的词）
并在计划里留痕。实测代价：常数闭合下 40 步 ≡ 20 + 续 20 **逐位相同**；换成新经典
闭合加密度 / 动量通道，同一个比法 Te 差 61 %。所以 :func:`carried` 把这件事一并
交出来（``lag_reset`` 键），调用方不该假装没看见。
"""
from __future__ import annotations

import json
from pathlib import Path

__all__ = ["CarriedState", "carried", "ResumeError"]


class ResumeError(ValueError):
    """要续的那份东西不能续——话本身就是答案。"""


class CarriedState(dict):
    """一次运行交出的状态：``settings`` · ``documents`` · ``step`` · ``t``。

    是一个 ``dict``，所以 ``**state["settings"]`` 直接摆得进参数表。
    """

    @property
    def settings(self) -> dict:
        return self.get("settings", {})

    @property
    def documents(self) -> dict:
        return self.get("documents", {})

    @property
    def lag_reset(self) -> bool:
        """滞后量交不过去吗（见模块抬头）。"""
        return bool(self.get("lag_reset"))


def _record_of(src) -> tuple[dict, Path]:
    """把 ``--resume-from`` 收的那几种东西认成 (记录, 记录所在目录)。

    ★三种都认，因为它们在读者那里是同一件事：一份 ``record.jsonld``、装着它的目录、
    或者 :func:`fylite.engine.cases.run` 刚交回来的那个 dict（它带 ``run_dir``）。
    认不出就**点名**，不猜。
    """
    if isinstance(src, dict):
        if src.get("type") == "spo:ComputationRecord":
            return src, Path.cwd()
        for key in ("record_dir", "run_dir"):
            if src.get(key):
                return _record_of(Path(src[key]))
        raise ResumeError(
            "这个 dict 既不是一份 spo:ComputationRecord，也没有 run_dir / record_dir —— "
            "把 `fy run … -o <目录>` 写下的那个目录交给我，或者那份 record.jsonld")
    p = Path(src)
    f = p / "record.jsonld" if p.is_dir() else p
    if not f.is_file():
        raise ResumeError(f"{f}：没有这份记录")
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResumeError(f"{f}：读不成 JSON —— {exc}") from exc
    if doc.get("type") != "spo:ComputationRecord":
        raise ResumeError(
            f"{f}：这不是一份记录（type 是 {doc.get('type')!r}，要的是 spo:ComputationRecord）")
    return doc, f.parent


def carried(src) -> CarriedState:
    """一份记录交出的状态，读成可以摆回去的形。

    ``src`` 是一份 ``record.jsonld``、装着它的目录，或 ``cases.run`` 的返回值。

    ★记录**没有**中间态时抛 :class:`ResumeError` 并说清楚为什么——单步 code 本来就
    没有可续的中间态，那是**答案**，不是故障（`-18` U-10 的同一句话）。
    """
    doc, base = _record_of(src)
    st = doc.get("fylite:state")
    if not isinstance(st, dict) or not (st.get("settings") or st.get("documents")):
        raise ResumeError(
            "这份记录没有 fylite:state —— 单步 code 的记录无中间态可续，"
            "而那是答案不是故障（FYL-DESIGN-18 U-10）")
    docs = {}
    for port, uri in (st.get("documents") or {}).items():
        q = Path(uri)
        docs[port] = str(q if q.is_absolute() else base / q)
    out = CarriedState(
        settings=dict(st.get("settings") or {}),
        documents=docs,
        step=st.get("step"),
        t=st.get("t"),
        code=st.get("code"),
        entry=st.get("entry"),
        record=doc.get("id"),
    )
    #: ★★滞后量交不交得过去，**按同一条判据**算（Rust 那侧的 `lag_carried`）：
    #: 看这次运行的原始条目块里那三条是不是真的非零。★第一版读的是**这份记录自己**
    #: 的 `plan.jsonld` 里有没有 `resume:lag-reset`——那答的是「上一次续跑设过没有」，
    #: 不是「这一次能不能交」，两者只在连着续第三次时才碰巧一样。
    out["lag_reset"] = _lag_lost(st.get("entry_block"), base)
    return out


#: 内核从 ``evolve/fylite:*`` 读回、却写在原始条目块里的那三条（模块抬头）。
_LAG = ("psi_prev_out", "sigma_prev_out", "exch_prev_out")


def _lag_lost(entry_uri, base: Path) -> bool:
    """这次运行结束时，滞后量非零吗——非零就意味着续跑要从零起。"""
    if not entry_uri:
        return False
    q = Path(entry_uri)
    f = q if q.is_absolute() else base / q
    if not f.is_file():
        return False
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for key in _LAG:
        v = doc.get(key)
        if isinstance(v, list) and any(x for x in v if isinstance(x, (int, float)) and x != 0):
            return True
    return False


def kernel_of(src) -> str | None:
    """写这份记录的内核指纹（K-7），认不出时 ``None``。

    ★续跑之前比一下它与手边这一份：不同就该拒绝（`-16` S-6），而放行要留痕。
    """
    doc, _ = _record_of(src)
    env = doc.get("environment") or {}
    return env.get("kernel_sha256")
