"""闸子：`_mds_bind.json` —— A-Box 分解出来的 MDSplus 绑定表。

★**为什么一份生成的数据文件需要自己的闸子。** 这张表说的是「哪个语义位置由哪个
节点喂、过哪个下标、乘哪个标度」。它错了不会报错：读回来的仍然是一个量级正常的
数组，只是来自另一条通道、或差一个 2π。判的因此不是「文件能解析」。

★★**第一条判据是条数，理由是这个文件自己的失败史。** 写 `tools/abox-mds-bind.py`
时，剥离顺序先剥动词后剥下标，于是 `DATA(\\X)[0,*]` 这一族（111 条）全被判成
「不是节点路径」进了 `unsupported`——**而生成器照常成功退出**，只是把 485 条里的
372 条写了出来。少三分之一的表不会让任何一步失败：读者只会发现某些语义位置没有
绑定，而那看起来和「上游本来就没绑」一模一样。所以数目在这里被钉住。

★两个宿主读的是**同一份字节**（`python/fylite/_mds_bind.json` 与
`app/assets/mds-bind.json` 由生成器同一次写出），这也判。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY_COPY = ROOT / "python" / "fylite" / "_mds_bind.json"
APP_COPY = ROOT / "app" / "assets" / "mds-bind.json"

#: 与内核 `mdsip::is_node_path` 逐字符同一条规则。抄在这里是有意的：这道闸问的
#: 正是「表里的每一条到了门口会不会被拒」，所以它必须用门口那条规则来问。
NODE_RE = re.compile(r"^[A-Za-z0-9_$\\.:-]+$")

#: 实测值。改动上游 A-Box 之后这两个数会变——**跟着改，但要在提交信息里说清楚
#: 多出来/少掉的是哪几条**，不要只把数字调到当天的样子。
N_BINDINGS = 483
N_UNSUPPORTED = 2

pytestmark = pytest.mark.skipif(not PY_COPY.is_file(),
                                reason=f"{PY_COPY.name} not generated "
                                       "(tools/abox-mds-bind.py)")


@pytest.fixture(scope="module")
def table():
    return json.loads(PY_COPY.read_text(encoding="utf-8"))


def test_the_two_hosts_read_the_same_bytes():
    assert APP_COPY.is_file(), "浏览器那一份不在——生成器只写了一半"
    assert PY_COPY.read_bytes() == APP_COPY.read_bytes()


def test_the_table_is_whole(table):
    """★见抬头：少了三分之一的表不会让任何一步失败。"""
    assert len(table["bindings"]) == N_BINDINGS
    assert len(table["unsupported"]) == N_UNSUPPORTED


def test_every_node_would_pass_the_kernels_door(table):
    """一条到了 `mdsip::is_node_path` 会被拒的绑定，留在表里就是一次运行期失败。"""
    bad = [b for b in table["bindings"]
           if b["verb"] != "const" and not NODE_RE.match(b["node"] or "")]
    assert bad == [], [b["link"] for b in bad[:5]]


def test_the_pieces_are_the_ones_the_kernel_assembles_from(table):
    """`{verb, node, subscript}` —— 校验过的节点路径与整数，没有表达式。"""
    for b in table["bindings"]:
        assert b["verb"] in {"data", "dim_of", "raw", "const"}, b
        for item in b["subscript"] or []:
            assert set(item) <= {"int", "all", "slot"} and len(item) == 1, b
            if "int" in item:
                assert isinstance(item["int"], int), b


def test_no_expression_survived_into_the_table(table):
    """★表里不许再出现 TDI 的语言成分。它们是被分解掉的，不是被搬运的。"""
    for b in table["bindings"]:
        if b["verb"] == "const":
            continue
        assert not (set("()*, ") & set(b["node"])), b["link"]


def test_what_cannot_be_decomposed_is_named_not_dropped(table):
    """★两条 `BDRY[…NBDRY[{t}]-1…]` 的切片上界是另一个节点的值。它们必须**在表里
    具名**：悄悄跳过与「上游没有绑定」在读者那里长得一模一样。"""
    for u in table["unsupported"]:
        assert u["why"] and u["link"] and u["path"], u
        assert "round trips" in u["why"] or "not a node path" in u["why"], u


def test_units_are_absent_and_say_so(table):
    """★退役的 `mapping/east-mds.json` 逐组声明过 `units_out`（磁通环那条是明写的
    `[TBD]`，附注「写一个猜的单位比留空更坏」）。A-Box 不带单位，所以这里一律
    `null`——**空着是一条声明，不是一处遗漏**。"""
    assert all(b["units"] is None for b in table["bindings"])
    assert "do not invent" in table["provenance"]["note"]


def test_regenerating_reproduces_it_byte_for_byte():
    """★生成物的判据只有一条能真正生效：重跑生成器，逐字节比。

    A-Box 在 fydoc（私有文档仓），所以只有两边检出都在的机器上跑得起来——够不到
    就 skip 并点名缺的是什么，与本仓其它「需要机器数据」的判据同一套政策。
    """
    abox = pathlib.Path(os.environ.get(
        "FYLITE_ABOX", pathlib.Path.home() / "workspace/fydoc/device/east/abox"))
    tool = None
    for c in (ROOT / "tools" / "abox-mds-bind.py",
              ROOT.parent / "fylite_kernel" / "tools" / "abox-mds-bind.py"):
        if c.is_file():
            tool = c
            break
    if tool is None:
        pytest.skip("tools/abox-mds-bind.py not reachable (it lives in the "
                    "kernel checkout)")
    if not (abox / "bind" / "mdsplus").is_dir():
        pytest.skip(f"no A-Box at {abox} (fydoc is a private checkout; "
                    "set $FYLITE_ABOX)")
    p = subprocess.run([sys.executable, str(tool), "--source", str(abox),
                        "--public", str(ROOT), "--check"],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
