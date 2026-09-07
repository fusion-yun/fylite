"""装置结构数据导出成 IMAS 数据入口时的**数据完整性**。

★★这道闸问的是三个问题，一个比一个具体：

1. **出得来吗** —— 一份装置描述是一个**容器**（`tf` · `pf_active` · `wall` · `magnetics`
   … 各是它下面的一支），数据入口装的是 IDS。拆分做对了，入口里就是一支一份文件；
   做错了，产物是一个**空的** `master.h5`，底下什么也没链接，而退出码是 0。
2. **数对吗** —— 入口里的每一个数，回到源文档里都找得到同一个数。归一化允许**搬家**
   （`limiter` 挪到 `description_2d/` 之下）、**换算**（`b_field_phi_vacuum_r = r0·b0`）、
   **改名**（`"rectangle"` → 2）与**展开**（矩形 → 四角），但**不许改值**。
3. **丢了什么** —— 没进入口的裸路径逐条记在 :data:`BASELINE` 里。判据只有一条：
   **这张表只准变小**。丢东西不可怕，丢得没人知道才可怕。

★★为什么走 :mod:`fylite.io.fydoc` 而不是 `fy` 命令行：两者是**同一个库**
（`libfylite_runtime.so` / `fy` 都由 `rust/fylite_runtime` 出），而库这一侧不需要先
构建可执行文件。2026-09-07 之前拆分只写在命令行里，于是 Python 宿主照旧写出那份
空件——同一个库、两种行为。现在拆分在库里，这道闸从 Python 这一侧查它，正好也是
对那次收敛的守卫。

★装置描述取**编译进二进制的那一层**（`facts.bundled_doc`）：一份发行版不带盘上语料
也答得出 `list devices`，所以这道闸在没有任何语料检出的机器上照样跑得起来。
一份没有编译进 facts 的构建（`build.sh --no-facts`）里它整体跳过，并说清为什么。
"""
from __future__ import annotations

import json
import re

import numpy as np
import pytest

from fylite import facts, machine_svg
from fylite.io import fydoc


def _device_docs() -> dict[str, dict]:
    """编译进来的那些**完整装置描述**（只有牌的条目没有结构，不在此列）。"""
    out = {}
    for ident in facts.bundled_ids("device"):
        text = facts.bundled_doc("device", ident)
        if not text:
            continue
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and doc.get("@type") == "fyo:DeviceDescription":
            out[ident] = doc
    return out


DEVICES = _device_docs()

pytestmark = pytest.mark.skipif(
    not DEVICES,
    reason="这份构建里没有编译进装置描述（`build.sh --no-facts`）——"
           "闸子要查的东西不在，所以整体跳过，而不是绿着什么也没查")


#: 每台机器**没进数据入口**的裸路径。逐条注了成因；三类，没有一类是转换缺陷。
#:
#: ① `tf/b0` · `tf/b_field_phi_vacuum_r/unit` —— DD 的 `tf` 没有 `b0`；单位在 DD 里
#:    是**模式**里的信息，不是数据里的一个叶子。`b0` 已被换算消费
#:    （`b_field_phi_vacuum_r/data = r0 * b0`），源槽本身仍无归宿。
#: ② `tf/coils_n`（CFEDR）—— **源文档里就是 `null`**。DD 里有 `coils_n` 这个名字，
#:    丢的不是名字对不上，是那一格本来就空：上游那份 A-Box 自己注了「TF 线圈数
#:    已公开为 16（104005 §2），而本件未载」。要它有值得先补上游，不能在这里编。
#: ③ `wall/…/closed` —— fylite 自己的闭合标志，DD 的轮廓没有这一位。
#:
#: ★★**ITER 那两条同日修掉了**，而且不是靠编：上游的文献件里 `b0` = 5.3 T（两条
#: 一手源，并注明 Baseline 2024 下仍成立）与 `coil.dev:count` = 18（带出处）**本来
#: 就在**，只是 `tools/abox-to-facts.py` 认的是另外两个名字（`b_field_phi_vacuum_r`
#: 与 `coils_n`），于是两个量都写成了 `null`。实测：ITER 的 `machine` 块因此
#: **根本没有 `fylite:b0`**。现在两种写法都认，`b0` 原样带进 `tf`，DD 那一支由
#: 归一化按 `r0 * b0` = 6.2 × 5.3 = 32.86 T·m 算出。
#:
#: ★★**第四类修掉了**（用户裁定 2026-09-07）：`count`。A-Box 在每个结构数组旁边
#: 写一个计数，它等于列表长度，DD 里没有这个名字，六台机器每一台都丢它（WEST 一台
#: 93 条）。源头是 `tools/abox-to-facts.py` 的三处；那里现在不写了，语料重新生成，
#: 逐叶对过：**只少了 `count`，其余一个不动**。JT-60SA 由此一条裸路径都不丢。
#:
#: ★★这张表**第一版是错的**，错得很有教训：WEST 那一行漏了四条。中间层把写出报告
#: 装进调用方给的缓冲，而 Python 宿主给的是 4 KiB，WEST 的报告过了 5 KiB——**尾巴
#: 被悄悄砍掉**，据它记下来的基线因此不全。同日两处一起修：中间层装不下时把尾巴
#: 换成 `…[truncated: N of M bytes]`（截断看得见），宿主的缓冲给到 64 KiB
#: （平时根本不发生）。下面那条「报告没有被截断」的断言，就是防它再回来。
BASELINE: dict[str, set[str]] = {
    "best": {"tf: b0", "tf: b_field_phi_vacuum_r/unit"},
    "cfedr": {"tf: b0", "tf: b_field_phi_vacuum_r/unit", "tf: coils_n"},
    "cfetr": {
        "tf: b0", "tf: b_field_phi_vacuum_r/unit",
        "wall: description_2d/vessel/unit/annular/outline_inner/closed",
        "wall: description_2d/vessel/unit/annular/outline_outer/closed",
    },
    #: ★★EAST 2026-09-07 进来：它的卡片是**手工维护**的那一张（在内核仓
    #: `machine_desc/east/`），比上游全，也因此带着自己的一套词。下面这些是那套词里
    #: DD 不认的部分 —— `count` · `note` 是同一类冗余/说明，`weight` · `bit_error` ·
    #: `pcs` 是 EFIT 反演那一侧的东西，`pf_passive/*` 是
    #: 按层分组的被动结构（DD 的 `pf_passive` 没有这些名字）。
    #: **该给它们加 `fylite:` 前缀**，而那张卡片在另一个仓，是一次要协调的改动。
    "east": {
        "ec_launchers: beam/frequency", "ec_launchers: beam/mode",
        "ec_launchers: count", "ec_launchers: note",
        "ic_antennas: antenna/level", "ic_antennas: count", "ic_antennas: note",
        "interferometer: channel/line_of_sight/theta", "interferometer: count",
        "interferometer: laser_wavelength", "interferometer: note",
        "lh_antennas: count", "lh_antennas: note",
        "magnetics: b_field_pol_probe/bit_error", "magnetics: b_field_pol_probe/weight",
        "magnetics: flux_loop/bit_error", "magnetics: flux_loop/weight",
        "magnetics: pcs",
        "pf_active: count", "pf_active: note",
        "pf_passive: note", "pf_passive: outer_shell", "pf_passive: passive_plates",
        "pf_passive: vessel",
        "polarimeter: baseline", "polarimeter: channel/line_of_sight/theta",
        "polarimeter: count", "polarimeter: faraday_constant", "polarimeter: note",
        "tf: b0",
        "wall: description_2d/limiter/unit/count",
    },
    "iter": {"tf: b0"},
    #: ★一条也不丢。这不是「没查」——`CHECKED_AT_LEAST` 说它逐值核对过 6 个叶子。
    "jt60sa": set(),
    "west": {
        "wall: description_2d/vessel/unit/annular/outline_inner/closed",
        "wall: description_2d/vessel/unit/annular/outline_outer/closed",
    },
}

#: 入口里**不来自源文档**的叶子，逐条有据：归一化合成或换算出来的那些。
#: 其余任何一条对不上源的叶子都是失败——那意味着入口里有一个凭空出现的数。
SYNTHESIZED = (
    "ids_properties/homogeneous_time",   #: 没有时间片就是 2（常量）
    "b_field_phi_vacuum_r/data",         #: = r0 * b0（DERIVATIONS）
    "/outline/r", "/outline/z",          #: 矩形展成四角（wall 元件）
    "/geometry/geometry_type",           #: 名字换成 DD 的整数索引
)

#: 上一条表**放行**的叶子数不能悄悄涨上去。这里记的是每台机器**真正逐值核对过**
#: 的叶子数（2026-09-07 实测，只准增不准减）：没有这一条，往 :data:`SYNTHESIZED`
#: 里多加一个宽泛的词就能让整道闸绿着什么也不查。
CHECKED_AT_LEAST = {"best": 124, "cfedr": 96, "cfetr": 102, "east": 591,
                    "iter": 165, "jt60sa": 6, "west": 200}

#: 语义键与声明的本地词 —— 不进数据入口是设计，不是缺陷。
_LOCAL = re.compile(r"(^|/)(@|\$|fylite:|_)")


def _leaves(node, prefix: str = "") -> dict[str, object]:
    """一棵 JSON 树 → `{路径: 叶子}`；数组按整支给（不逐元素展开）。"""
    out: dict[str, object] = {}
    if isinstance(node, dict):
        for k, v in node.items():
            out.update(_leaves(v, f"{prefix}/{k}" if prefix else str(k)))
    elif isinstance(node, list) and node and isinstance(node[0], (dict, list)):
        for i, v in enumerate(node):
            out.update(_leaves(v, f"{prefix}/{i}"))
    elif node is not None:
        out[prefix] = node
    return out


def _export(doc: dict, tmp_path):
    """一份装置描述 → 一个 IMAS HDF5 数据入口；返回 `(目录, 写出报告)`。"""
    out = tmp_path / "imas"
    report = fydoc.Bundle.from_dict(doc).write(out, layout="imas")
    return out, report


def _bare_drops(report: str) -> set[str]:
    """写出报告里被丢掉的**裸**路径（语义键与本地词不算）。"""
    bare = set()
    for chunk in report.split(";"):
        if "dropped" not in chunk:
            continue
        ids = chunk.split(":", 1)[0].strip()
        for path in re.findall(r'"([^"]+)"', chunk):
            if not _LOCAL.search(path):
                bare.add(f"{ids}: {path}")
    return bare


def _equalish(a, b) -> bool:
    """两个叶子是不是同一个值。★逐位相同，不设容差：归一化搬家换名，不改值。"""
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    try:
        av, bv = np.asarray(a, dtype=float).ravel(), np.asarray(b, dtype=float).ravel()
    except (TypeError, ValueError):
        return a == b
    return av.shape == bv.shape and bool(np.array_equal(av, bv))


def _split(path: str) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """一条路径拆成**名字**与**下标**两串。"""
    segs = path.split("/")
    return (tuple(s for s in segs if not s.isdigit()),
            tuple(int(s) for s in segs if s.isdigit()))


def _index(src: dict[str, object]) -> dict[tuple[str, ...], list]:
    """源文档按「去掉 IDS 名之后的名字串」建索引，一格里放它的各个下标。"""
    out: dict[tuple[str, ...], list] = {}
    for path, value in src.items():
        names, idx = _split(path)
        out.setdefault(names[1:], []).append((idx, path, value))
    return out


def _one_zero_apart(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    """两串下标相同，或其中一串删掉一个 `0` 之后相同。

    ★★两种结构变化各贡献一个 `0`，两个都是**记在报告里的**：
    * `unwrapped` —— DD 说结构而文档给一元列表，解出来少一层
      （源 `…/position/0/r` → 入口 `…/position/r`）；
    * `relocated` —— 搬进 `description_2d` 这个结构数组的第 0 个
      （源 `limiter/…` → 入口 `description_2d/0/limiter/…`）。
    """
    if a == b:
        return True
    long, short = (a, b) if len(a) > len(b) else (b, a)
    if len(long) != len(short) + 1:
        return False
    return any(long[i] == 0 and long[:i] + long[i + 1:] == short for i in range(len(long)))


def _carried(index, tail: str):
    """源文档里**对得上这条入口路径**的那些叶子。对不上就是空。

    ★★对法从「后缀匹配」改成这个（2026-09-07）。后缀匹配在小文档上够用，在
    EAST 那样一份文档里**会指错**：入口的 `b_field_pol_probe/0/position/r` 在源里
    是 `…/position/0/r`，后缀对不上，而别的探针的某条路径反倒对上了 —— 于是闸子
    报出 142 条「值不符」，条条都是匹配错了，不是数错了。一道会误报的闸子，
    读到的人下一次就会略过它。

    现在两串分开对：**名字**串要求源是入口的后缀（搬家只会往前加名字），
    **下标**串要求逐位相同或差一个 `0`（解一元列表与搬进 `[0]` 各贡献一个）。
    两边都是精确查表，不再有「碰巧结尾一样」。
    """
    names, idx = _split(tail)
    for cut in range(len(names)):
        for (sidx, path, value) in index.get(names[cut:], ()):
            if _one_zero_apart(idx, sidx):
                yield path, value


@pytest.mark.parametrize("device", sorted(DEVICES))
def test_the_entry_holds_one_file_per_ids(device, tmp_path):
    """容器拆成了它装着的那几个 IDS，而不是原样放到一边。"""
    out, report = _export(DEVICES[device], tmp_path)
    files = {p.name for p in out.iterdir()}
    assert "master.h5" in files, f"{device}: 数据入口没有 master"
    ids_files = sorted(f for f in files if f != "master.h5")
    assert ids_files, (
        f"{device}: 入口里一个 IDS 也没有——容器被整份放到一边了。\n报告：{report}")
    for name in ids_files:
        assert (out / name).stat().st_size > 0, f"{device}: {name} 是空的"
    #: 读得回来，而且回来的还是那几支
    back = fydoc.read(out)
    assert set(back.keys) == {f[:-3] for f in ids_files}, (
        f"{device}: 写出去的文件与读回来的 IDS 对不上")


@pytest.mark.parametrize("device", sorted(DEVICES))
def test_every_number_in_the_entry_is_the_source_number(device, tmp_path):
    """入口里的每一个数，源文档里找得到同一个数（或逐条有据地是算出来的）。

    ★对法见 :func:`_carried`：名字串与下标串分开对，两边都是精确查表。
    宽在结构、严在数值——正是这里要的：结构本来就允许变，数值不允许。
    """
    source = DEVICES[device]
    out, _ = _export(source, tmp_path)
    entry = _leaves(fydoc.read(out).to_dict())
    index = _index(_leaves(source))

    unexplained, checked = [], 0
    for path, value in entry.items():
        if _LOCAL.search(path):
            continue
        if any(tag in path for tag in SYNTHESIZED):
            continue
        checked += 1
        tail = "/".join(path.split("/")[1:])          #: 去掉入口那一层的 IDS 名
        hits = list(_carried(index, tail))
        if not hits:
            unexplained.append(f"{path} = {value!r} —— 源文档里没有这一条")
        elif not any(_equalish(value, v) for _, v in hits):
            unexplained.append(
                f"{path} = {value!r} —— 源 {hits[0][0]} 是 {hits[0][1]!r}")
    assert not unexplained, (
        f"{device}: 数据入口里有对不上源文档的数：\n  " + "\n  ".join(unexplained[:20])
        + "\n\n归一化允许搬家 · 换算 · 改名 · 展开，**不允许改值**。")
    floor = CHECKED_AT_LEAST[device]
    assert checked >= floor, (
        f"{device}: 逐值核对过的叶子从 {floor} 掉到 {checked} ——"
        "要么入口里少了东西，要么放行表放宽了。两种都要先说清楚再改这个数。")


@pytest.mark.parametrize("device", sorted(DEVICES))
def test_the_paths_a_device_loses_are_the_recorded_ones(device, tmp_path):
    """丢在门外的裸路径，逐条在册。这张表只准变小。"""
    _, report = _export(DEVICES[device], tmp_path)
    assert "truncated" not in report, (
        f"{device}: 写出报告被截断了——按半截报告记下来的基线是假的。\n{report[-200:]}")
    now = _bare_drops(report)
    known = BASELINE[device]
    new = sorted(now - known)
    assert not new, (
        f"{device}: 现在丢的路径，以前不丢：\n  " + "\n  ".join(new)
        + "\n\n裸着丢就是一个量悄悄离开了文档。要么给它（或它整节）加 `fylite:` "
          "前缀，要么改成 DD 真有的那条路径。")
    fixed = sorted(known - now)
    assert not fixed, (
        f"{device}: 这些不丢了——从 BASELINE 里删掉：\n  " + "\n  ".join(fixed))


@pytest.mark.parametrize("device", sorted(DEVICES))
def test_the_cross_section_survives_the_export(device, tmp_path):
    """**画得出来**才算导出成功：几何过一遍数据入口，逐点不变。

    ★这一条查的东西前三条查不到：一份入口可以叶子齐全、数值正确，而几何**读不出来**
    ——比如轮廓的 `r` 与 `z` 落在两个不同的地方。截面图是这件事最直接的判据。
    """
    source = DEVICES[device]
    out, _ = _export(source, tmp_path)
    before = machine_svg.cross_section(source, device=device)
    after = machine_svg.cross_section(fydoc.read(out).to_dict(), device=device)
    if before.is_empty():
        pytest.skip(f"{device} 的描述里没有几何——没有可画的，也就没有可比的")

    for kind in ("limiter", "vessel", "coils"):
        b, a = getattr(before, kind), getattr(after, kind)
        assert len(a) == len(b), (
            f"{device}: 过一遍数据入口之后 {kind} 从 {len(b)} 条变成 {len(a)} 条")
        for cb, ca in zip(b, a):
            assert np.array_equal(np.asarray(cb.r, dtype=float),
                                  np.asarray(ca.r, dtype=float)), f"{device}: {cb.path} 的 r 变了"
            assert np.array_equal(np.asarray(cb.z, dtype=float),
                                  np.asarray(ca.z, dtype=float)), f"{device}: {cb.path} 的 z 变了"
    assert len(after.probes) == len(before.probes)
    assert len(after.flux_loops) == len(before.flux_loops)


def test_the_baseline_names_only_devices_that_exist():
    """编译进来的每一台都要在基线里 —— 否则它挡不住任何回归。

    ★★反过来**不**要求相等：EAST 只在 `abox-to-facts.py --from-kernel` 拉过卡片的
    检出里才编得进去（那个开关是 opt-in 的，见那里的注释），所以基线里有而这份
    构建里没有，是常态，不是错。多出来的那几行会由
    `test_the_paths_a_device_loses_are_the_recorded_ones` 在有它的检出上守住。
    """
    missing = sorted(set(DEVICES) - set(BASELINE))
    assert not missing, (
        f"这些装置编译进来了，而基线里没有：{missing}。"
        "先量一遍它丢什么，再把那几行写进 BASELINE。")
