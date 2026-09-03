"""闸子：数据层的 g-file 读入与 `fylite.io.geqdsk` 那份**逐字段相同**。

★★**这道闸是搬迁本身的判据。** 本仓从前有两份 g-file 实现——
`python/fylite/io/geqdsk.py`（752 行）与 `app/assets/geqdsk.js`（286 行），
后者的注释自己写着「returns the same field names fylite's own `read_geqdsk`
returns, so the two can be compared directly」。数据层（`rust/fylite_engine/`）
写了第三份，为的是最终只剩一份；而搬迁的规矩是
`tests/PHYSICS-MIGRATION.md` 那本台账一直在走的那条——**一条判据只有在对面
已经存在之后才算搬过去**。所以这里不删任何一份，先判它们相等。

★★★**它们已经在一个真实的地方不同**，不是假想的：Python 按**固定 16 列**切数
（`line[i:i+16]`），Rust 与 JS 按**模式扫描**。两者在规范的 `%16.9E` 上一致，
在负号吃掉分隔空格的老写法上不一致——**而不一致的那一侧不会报错**，它读出的是
一串量级正常、错位了一格的数。所以下面比的是**每一个数**，不是「形状对得上」。

★语料：仓内自带一份合成算例（数据层的 `testdata/`，`cargo test` 也用它），
外加 fydata 里的真炮 g-file（私有检出，够不到就 skip 并点名）。
"""
from __future__ import annotations

import pathlib

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: 仓内自带的那份 —— 它保证这道闸在只有本仓的检出上也跑得起来。
BUNDLED = ROOT / "rust" / "fylite_engine" / "testdata" / "g_synthetic.geqdsk"

#: 真炮。★出处是 fydata（私有），所以是「有就跑」——合成那份已经覆盖了语法，
#: 这些覆盖的是真文件的脾气（各家 vintage 的写法差异）。
CORPUS = ROOT.parent / "fydata" / "corpus" / "experiment" / "east"


def _cases():
    out = []
    if BUNDLED.is_file():
        out.append(pytest.param(BUNDLED, id="synthetic"))
    if CORPUS.is_dir():
        for p in sorted(CORPUS.glob("g[0-9]*"))[:3]:
            out.append(pytest.param(p, id=p.name))
    return out


CASES = _cases()

pytestmark = pytest.mark.skipif(not CASES, reason="no g-file reachable")


@pytest.fixture(scope="module")
def data_lib():
    from fylite import kernel
    lib = kernel.load_data()
    if lib is None:
        pytest.skip("libfylite_engine.so not built (rust/build.sh)")
    return lib


@pytest.mark.parametrize("path", CASES)
def test_the_two_readers_agree_on_every_number(path, data_lib):
    from fylite import kernel
    from fylite.io import geqdsk as py

    #: ★参照是**固定列**那份（`_read_geqdsk_reference`），不是 `read_geqdsk`
    #: ——后者 2026-09-02 起已经是数据层的薄壳，拿它当参照就是自己比自己。
    ref = py._read_geqdsk_reference(path)
    got = kernel.read_gfile(path)

    assert (got["nw"], got["nh"]) == (ref["nw"], ref["nh"])
    for name in kernel.GFILE_SCALARS:
        a, b = ref[name], got[name]
        assert a == pytest.approx(b, rel=0, abs=0), f"{name}: {a!r} vs {b!r}"
    for name in kernel.GFILE_ARRAYS:
        a = np.asarray(ref[name], dtype=float)
        b = np.asarray(got[name], dtype=float)
        assert a.shape == b.shape, f"{name}: {a.shape} vs {b.shape}"
        #: ★逐位相同，不是「近似」。两份实现读的是同一串十进制文本，
        #: 任何差都说明有一侧切错了位置——那不是容差问题。
        assert np.array_equal(a, b), (
            f"{name}: first differing index "
            f"{int(np.flatnonzero(a != b)[0])} of {a.size}")


@pytest.mark.parametrize("path", CASES)
def test_the_header_survives_verbatim(path, data_lib):
    """★头一行带着装置、炮号与时刻。它不是装饰：`gfile_name()` 与记录册都读它。"""
    from fylite import kernel
    from fylite.io import geqdsk as py
    assert (kernel.read_gfile(path)["header"]
            == py._read_geqdsk_reference(path)["header"])


def test_the_rust_reader_reads_a_fortran_d_exponent_and_the_python_one_raises():
    """★★把两份实现**唯一实测到的**行为差别钉成判据。

    Python 那份按固定 16 列切完之后直接 `float(chunk)`，而 `float()` 不认 Fortran
    的 `D` 指数（`1.5D+01`）——实测抛 `ValueError`。数据层那份按模式扫描并把
    `D` 当作指数读。

    ★**这条不是「Rust 更对」的宣言，是一条记录**：两份在四份真文件（合成一份
    + EAST 三炮）上逐位相同，唯一分开的地方是这个。换掉 Python 那份的时候，
    这就是要一起交代的行为变化；而如果有人把 Rust 那份改成固定列「与 Python
    对齐」，这条会先红。

    ★写这道闸时先推断的是另一条（「负号吃掉分隔空格会让固定列错位」，JS 的注释
    提到过那种写法）。实测**不成立**：负号吃掉空格恰好让字段填满 16 列，固定列
    反而正好。推断与实测不一致时，留下的是实测。
    """
    import io

    from fylite import kernel
    from fylite.io import geqdsk as py

    line = " 1.500000000D+01 -2.500000000D-02"
    with pytest.raises(ValueError):
        py._read_floats(io.StringIO(line + "\n"), 2)
    #: ★而产品路径（数据层的薄壳）读得出来 —— 这就是换掉它买到的东西。

    #: 同一行喂给数据层：它读得出来（借一份最小的 g-file 外壳）。
    text = ("  probe  0  2  1\n"
            " 1.0 2.0 3.0 4.0 5.0\n 1.0 2.0 3.0 4.0 5.0\n"
            " 1.0 2.0 3.0 4.0 5.0\n 1.0 2.0 3.0 4.0 5.0\n"
            + line + "\n"          # fpol (2)
            " 1.0 2.0\n 1.0 2.0\n 1.0 2.0\n"   # pres ffprim pprime
            " 1.0 2.0\n"                          # psirz (2*1)
            " 1.0 2.0\n")                         # qpsi
    g = kernel.read_gfile(text)
    assert g["fpol"] == pytest.approx([15.0, -0.025])
