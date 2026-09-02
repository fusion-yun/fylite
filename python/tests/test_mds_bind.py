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
#:
#: 2026-09-02  483 -> 481：上游删了 `equilibrium` 的 `boundary/type`（那是全表
#: 唯一一条 `const` 字面量）与 `global_quantities/q_min/{value,rho_tor_norm}`，
#: 新增 `boundary/minor_radius`。三删一增。★这是**绑定内容**变了，不是上游被
#: 重写了一遍——两者由 provenance 的两个指纹分开，`--check` 会直说是哪一种。
N_BINDINGS = 481
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

def test_every_verb_in_the_table_has_a_wire_code(table):
    """★表里的 verb 是**字符串**（`"data"`），而 `fylite_rs_mds_read` 收的是**整数**。
    那个映射就是两者之间的缝，它只有三行——而三行正是「看着抄一遍不会错」的长度，
    `zerod` 的参数顺序就是这么被拼到三处去的。所以它由 `rust/build.sh` 从
    `mdsip.rs` 的 `@mds-request` 生成进两个宿主，这里判表与它对得上。

    ★`const` 不在契约里，也不该在：那一条（`boundary/type`）是字面量，
    根本不上服务器。
    """
    from fylite import _mds_request as req
    used = {b["verb"] for b in table["bindings"]}
    assert used - set(req.VERBS) <= {"const"}, used - set(req.VERBS)
    assert req.ALL == -(2 ** 63), "`*` 哨兵必须是 i64::MIN"


def test_the_two_hosts_get_the_same_wire_codes():
    """生成物一式两份（Python 与浏览器），同一次写出——这里判它们没有分叉。"""
    from fylite import _mds_request as req
    js = (ROOT / "app" / "assets" / "mds-request.js")
    if not js.is_file():
        pytest.skip("mds-request.js not generated (rust/build.sh)")
    text = js.read_text(encoding="utf-8")
    for name, code in req.VERBS.items():
        assert re.search(rf"^\s*{name}: {code},$", text, re.M), (name, code)
    assert "-9223372036854775808n" in text, "JS 侧的 ALL 必须是 BigInt 字面量"


def test_the_data_library_exports_the_plane_and_the_kernel_does_not():
    """★★两件事一起判，因为它们是同一条边界的两面。

    数据层（`libfylite_data.so`，本仓 `rust/fylite_data/`）要有这七条；
    **内核（`libfylite_kernel.so`）一条都不许有**。这一组 2026-09-02 曾短暂地长在
    内核的 C ABI 上（ABI 124），当天判定为分层错误并搬走——判据留在这里，
    免得它某天又长回去：网络协议不是算数那层的接口。
    """
    from fylite import kernel
    data = kernel.load_data()
    if data is None:
        pytest.skip("libfylite_data.so not built (rust/build.sh)")
    names = ("open", "open_tree", "read", "last_f64", "last_dims",
             "last_error", "close")
    for n in names:
        assert hasattr(data, f"fylite_data_mds_{n}"), n
    core = kernel.load()
    if core is not None:
        back = [n for n in names if hasattr(core, f"fylite_rs_mds_{n}")]
        assert back == [], f"数据面又长回内核的 C ABI 上了：{back}"


def test_a_verb_the_contract_does_not_have_is_refused_here():
    """★不是在服务器上失败，是在这一层。拼错的动词到了那边会变成一次无害的
    握手，然后是一条读不出所以然的服务器状态码。"""
    from fylite import kernel
    with pytest.raises(kernel.KernelError, match="unknown mds verb"):
        kernel.MdsSession._verb("DATA")      # 大小写就是拼错
