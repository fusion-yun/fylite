"""每个不带 `fylite:` 前缀的 fyo 路径，DD 里必须真有它。

★★这道闸补的是内核那道的**开世界**一半。内核有一条规则并且守着它：
「一个不是 IMAS DD 名字的段必须带 `fylite:` 前缀，因为裸着就是在声称一个它没有的
出处」——但那道闸只查**成员关系**：带前缀的段要在手写的 `OURS` 表里，裸段要不在
`OURS` 里。它**从不查 DD**。于是一个没有 DD 归宿的裸名，只要没人想起把它加进
`OURS`，就一路绿灯。

2026-09-07 实测，这正是发生过的事：`tf/b0` 在声明表里裸着写了 —— DD 4.1.1 的 `tf`
有 `r0`、有 `b_field_phi_vacuum_r`，**没有 `b0`**。把一台真实装置写成 IMAS 数据入口
时它被静默丢弃，同批丢的还有 79 个探针位置与 90 个真空室元件。一份看着像结果的空
IDS，比一个错误更坏。

本仓能查是因为 **DD 表就在本仓**（`rust/fylite_runtime/ids/*.tsv`，提交进仓的生成物）。
内核不该反向依赖公开仓，所以这一半装在这里，量的是内核生成到本仓的那份契约
（`python/fylite/_fyo_interface.py`）。

★★**2026-09-13 改了判据的前提**（用户裁定 2026-09-12「fylite 不作为本体前缀，本体增加，
入 fyo」，fyo 侧落点 `FYO-ADR-16`，2026-09-13——09-12 此处曾记作 `FYO-ADR-11`，fyo 并无此件）。此前这道闸把 **DD 当作唯一权威**：裸路径要么在 DD 里，
要么在基线里认罪。那个前提**从来就不对** —— fyo 的规矩写在它自己的 manifest 上：
「fyo **不**硬绑 IMAS DD，它独立演化；DD 是导入基线」。于是一个 **fyo 自己铸的槽**裸写是
**对的**，而这道闸会把它判红。

所以判据改成两条来源：裸路径要么有 **DD 归宿**，要么在下面的 `FYO_OWNED` 里**逐条登记**
并注明**是哪一条 ADR 铸的**。`FYO_OWNED` 不是第二个基线：基线是「认下的债，只准变小」，
它是「已经治理过的槽，来路可查」。两者**禁止重叠**（下面有一条闸子查这件事），因为同一条
路径不可能既是欠着的债又是治理过的槽。
"""
from __future__ import annotations

import pathlib

import pytest

from fylite import _fyo_interface as F

IDS_DIR = pathlib.Path(__file__).resolve().parents[2] / "rust" / "fylite_runtime" / "ids"

#: ★DD 里写成**结构数组**的段。声明表按「一个元素的内部」写路径（`CORE_TRANSPORT`
#: 的抬头就写着「One `model` element's `profiles_1d`」），而 DD 的绝对路径带着这个
#: 父段。所以判据是：裸路径要么在 DD 里，要么是某条 DD 路径的**后缀**，且多出来的
#: 前导段**全是**结构数组名。
#:
#: ★这张表是**判据的一部分**，不是便利：把它放宽到「任意前导段」，`tf/b0` 会因为
#: 别的 IDS 里某处有个 `b0` 而蒙混过关，闸子就不再是闸子。
AOS = frozenset({
    "time_slice", "profiles_2d", "profiles_1d", "source", "model", "coils",
    "coil", "channel", "antenna", "beam", "unit", "element", "description_2d",
    "supply", "function",
})

#: 2026-09-07 实测的基线：**只准变小**。逐条的性质见下面 `_WHY`。
#: 修一条就从这里删一条 —— 与 `test_flat_calls_only_shrink` 同一条规矩。
BASELINE: dict[str, str] = {
    #: ① DD 里根本没有这一节：整节是 fylite 自己的。按内核自己的规则，
    #: 前缀「可以出现在一个叶子上，也可以出现在整个节上」，所以这些该写
    #: `fylite:machine/…` 等。改名会动线上的路径，要一并升 `INTERFACE_REVISION`
    #: 并迁移盘上的装置文档 —— 是一次协调的迁移，不是一次改名。
    "DEVICE/grid_r_min": "machine/default_grid/r_min",
    "DEVICE/grid_r_max": "machine/default_grid/r_max",
    "DEVICE/grid_z_min": "machine/default_grid/z_min",
    "DEVICE/grid_z_max": "machine/default_grid/z_max",
    "DEVICE/grid_nw": "solver_dims/nw",
    "DEVICE/grid_nh": "solver_dims/nh",
    #: ★K-2 第一批（2026-09-13，用户裁定「进文档」）从基线删去十条：`pf_eta` · `element_turns` ·
    #: `ic_*` 六条 · `ps_max_voltage` · `ps_current_kA` 改走 DD 的 `pf_active/coil/resistance` ·
    #: `coil/function` · `element/turns_with_sign` · `pf_active/supply/*`。上面六条解算盒随第二批。
    #: ★★★**② ③ ④ 三类六条 2026-09-11 修好，按本表的规矩从基线删除。**
    #:
    #: **② 真空室矩形四条**（`.../vessel/unit/element/geometry/rectangle/{r,z,width,height}`
    #: → `geometry/...`）。此前这四条**特意留在基线里**，理由写作「查的是声明表，
    #: 内核的扁平槽给的就是矩形，它在 DD 里确实没有家」。★**那条理由本轮判为把两件事
    #: 混在了一起**：「这个量在 DD 里没有家」是本闸子记录的事实，而「所以它的路径必须带
    #: `fylite:`」是内核模块自己的规则（裸写非 DD 名 = 声称一个它没有的出处）。两者不冲突，
    #: 后者才是修法。佐证是同一段注释自己写着的：`fylite_runtime` 归一化时**原矩形就是
    #: 挂在 `geometry` 下**的 —— 也就是说声明表里那个裸 `geometry` 指的路径，
    #: 真文档里一处都没有。
    #:
    #: **③ `tf/b0` → `tf/fylite:b0`**。DD 的 `tf` 有 `r0` 与 `b_field_phi_vacuum_r`
    #: （= R0·B0，是信号结构不是裸浮点），没有 `b0`；同名在 `equilibrium/vacuum_toroidal_field`
    #: 下合法，所以词表里这一条 `gated: false` 并写明两个家。
    #:
    #: **④ `core_transport` 的 `profiles_1d/grid/rho_tor` → `profiles_1d/fylite:grid/rho_tor`**。
    #: DD 的 transport model 只有 `grid_d` / `grid_v` / `grid_flux`。★**注意这一条只修好了
    #: 名字，没有回答基线原先提的那个问题**：`rho` 与 `rho_d` 是不是同一条网格（是就该合并）。
    #: 那个问题仍然开着，已记进公开仓 TODO。
    #:
    #: 三类都在内核 `rust/fylite/src/fyo.rs` 改，接口修订 **1 → 2**（改 path 必须升号）。
}

#: **fyo 自己铸的槽**：DD 里没有，而 fyo 治理过。逐条注明铸它的 ADR。
#: ★加一条**必须**同时改 fyo 仓的 schema 并在那边的 ADR 里写下理由 —— 这张表登记的是
#: 「上游已经说过的话」，不是本仓可以自行扩充的清单。
FYO_OWNED: dict[str, str] = {
    #: `FYO-ADR-16` D-1：共享径向网格补 `psi_norm`（`CoreRadialGrid`）。fyo 的
    #: `equilibrium/time_slice/profiles_1d` 早有同名槽，核心径向网格却只有它的平方根
    #: `rho_pol_norm` —— 消费者要自己开平方并自己选一支根。补的是这个不对称。
    "CORE_PROFILES/psin": "FYO-ADR-16 D-1 (CoreRadialGrid.psi_norm)",
    "CORE_SOURCES/psin": "FYO-ADR-16 D-1 (CoreRadialGrid.psi_norm)",
    "CORE_TRANSPORT/psin": "FYO-ADR-16 D-1 (CoreRadialGrid.psi_norm)",
    #: `FYO-ADR-16` D-1：局部平衡（Miller / MXH）那一族，DD 一个没有。
    "LADDER/r2": "FYO-ADR-16 D-1 (EquilibriumProfiles1d.r2_average)",
    "LADDER/shift": "FYO-ADR-16 D-1 (EquilibriumProfiles1d.geometric_axis_shift)",
    "LADDER/dzmag": "FYO-ADR-16 D-1 (EquilibriumProfiles1d.geometric_axis_z_shift)",
    "LADDER/s_kappa": "FYO-ADR-16 D-1 (EquilibriumProfiles1d.elongation_shear)",
    "LADDER/s_delta": "FYO-ADR-16 D-1 (EquilibriumProfiles1d.triangularity_shear)",
    "LADDER/zeta": "FYO-ADR-16 D-1 (EquilibriumProfiles1d.squareness_mxh)",
    "LADDER/s_zeta": "FYO-ADR-16 D-1 (EquilibriumProfiles1d.squareness_mxh_shear)",
    "LADDER/mxh": "FYO-ADR-16 D-1 (EquilibriumProfiles1d.mxh_harmonics)",
    #: `FYO-ADR-16` D-1：器壁元件的**参数化**截面。DD 只给它 `outline`；有 `geometry`
    #: 的是线圈元件。落地时才判明（ADR D-2 末记着这次订正）。
    "DEVICE/vessel_r": "FYO-ADR-16 D-1 (Vessel2dElement.geometry)",
    "DEVICE/vessel_z": "FYO-ADR-16 D-1 (Vessel2dElement.geometry)",
    "DEVICE/vessel_width": "FYO-ADR-16 D-1 (Vessel2dElement.geometry)",
    "DEVICE/vessel_height": "FYO-ADR-16 D-1 (Vessel2dElement.geometry)",
    #: `FYO-ADR-10` D-2：O/X **支**由 fyo 自有的 `mode` 治理（1 = O、−1 = X），
    #: DD v4 那个 `polarization/o_mode_fraction` 是**份额**、不是支。
    "EC_LAUNCHERS/mode": "FYO-ADR-10 D-2 (ec_launchers beam/mode, fyo_owned)",
}

#: 逐条的性质，给读到失败的人看（不参与判定）
_WHY = "① 整节非 DD  ② 节在 DD 而这一支不在  ③ DD 里是别的写法  ④ DD 里没有这条网格"


def _dd(ids: str) -> dict[str, tuple[str, str]] | None:
    """`<ids>.tsv` 的 path -> (kind, ndim)，没有这张表就是 None。"""
    f = IDS_DIR / f"{ids}.tsv"
    if not f.is_file():
        return None
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        c = line.split("\t")
        out[c[0]] = (c[1], c[2])
    return out


def _reachable(dd: dict, path: str) -> bool:
    if path in dd:
        return True
    tail = "/" + path
    return any(k.endswith(tail) and all(s in AOS for s in k[: -len(tail)].split("/"))
               for k in dd)


def _homeless() -> dict[str, str]:
    """当前**没有** DD 归宿的裸路径：`<表>/<键>` -> 路径。"""
    out = {}
    for name, t in F.TABLES.items():
        ids = t["type"].split(":", 1)[1]
        for key, slot in t["slots"].items():
            path = slot["path"]
            if any(seg.startswith("fylite:") for seg in path.split("/")):
                continue
            #: ★`DeviceDescription` 是 fylite 的**容器**，不是一个 IDS：它的路径
            #: 自带 IDS 名作第一段，所以按第一段挑表。
            if ids == "DeviceDescription":
                head, _, rest = path.partition("/")
            else:
                head, rest = ids, path
            dd = _dd(head)
            if dd is None or not _reachable(dd, rest):
                out[f"{name}/{key}"] = path
    return out


def test_the_dd_tables_are_here_to_check_against():
    """★闸子的前提：DD 表在本仓。它不在，这道闸就什么也没查而绿着。"""
    assert IDS_DIR.is_dir(), IDS_DIR
    n = len(list(IDS_DIR.glob("*.tsv")))
    assert n > 50, f"only {n} DD tables — a truncated set would pass this gate vacuously"
    assert _dd("core_profiles"), "core_profiles.tsv does not parse"


def test_no_new_bare_path_without_a_dd_home():
    """裸路径的集合**只准变小**。"""
    now = _homeless()
    new = {k: v for k, v in now.items() if k not in BASELINE and k not in FYO_OWNED}
    assert not new, (
        "这些 fyo 路径裸着写，而 DD 里没有它们：\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in sorted(new.items()))
        + "\n\n裸着就是在声称一个它没有的出处。要么给它（或它所在的整节）加 "
          "`fylite:` 前缀，要么改成 DD 真有的那条路径。"
          f"\n★基线里已有 {len(BASELINE)} 条，逐条注了性质：{_WHY}")


def test_the_baseline_is_the_measurement_not_a_wish():
    """基线里修好的条目要从基线里删掉，否则它会挡住下一次回归。"""
    fixed = {k: v for k, v in BASELINE.items() if k not in _homeless()}
    assert not fixed, (
        "这些已经有 DD 归宿了 —— 从 BASELINE 里删掉：\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in sorted(fixed.items())))


@pytest.mark.parametrize("key", sorted(BASELINE))
def test_each_baseline_entry_still_says_what_it_said(key: str):
    """基线钉的是**路径**，不只是键：路径改了而归宿没改，要重新判一次性质。"""
    name, _, slot = key.partition("/")
    assert F.TABLES[name]["slots"][slot]["path"] == BASELINE[key], (
        f"{key} 的路径变了 —— 重新判定它有没有 DD 归宿，再更新 BASELINE")


def test_the_two_tables_do_not_overlap_and_every_owned_slot_names_its_adr():
    """★★`BASELINE` 与 `FYO_OWNED` **禁止重叠**，且后者逐条注明铸它的 ADR。

    重叠意味着同一条路径既是「认下的债」又是「治理过的槽」—— 那时读到失败的人无从
    知道该去修它还是该放它过去，而一张分不清这两件事的表比没有表更坏。
    ★「注明 ADR」不是格式要求：`FYO_OWNED` 的每一条都对应上游 `fyo` 仓 schema 里一个
    真实存在的槽，ADR 号是去核对它的入口。没有号的条目等于一句「相信我」。
    """
    both = sorted(set(BASELINE) & set(FYO_OWNED))
    assert not both, "同时在两张表里：" + ", ".join(both)
    for k, why in FYO_OWNED.items():
        assert "FYO-ADR-" in why, f"{k}: 没有注明铸它的 ADR（{why!r}）"


def test_every_owned_slot_is_actually_bare_and_homeless():
    """★`FYO_OWNED` 只准登记**真的**裸着且 DD 里没有的路径。

    一条已经有 DD 归宿的路径留在这里，就是给未来的回归留一个洞：它哪天改错了，
    这张表会替它挡住闸子。★与 `test_the_baseline_is_the_measurement_not_a_wish`
    同一条规矩，只是方向相反。
    """
    homeless = _homeless()
    stale = [k for k in FYO_OWNED if k not in homeless]
    assert not stale, (
        "这些已经有 DD 归宿（或已不再裸写）—— 从 FYO_OWNED 里删掉：" + ", ".join(sorted(stale)))
