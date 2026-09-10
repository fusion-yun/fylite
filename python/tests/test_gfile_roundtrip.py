"""V-15 的门：g-file **读—写—再读**是不动点，且 COCOS 口径不因往返而变。

★★为什么这条判据不需要外部答案。登记册的三类里它是 **V（验证）**：问的不是「这份
g-file 的物理对不对」，而是「本仓的读与写互为逆」。恒等式的参考是它自己，所以容差取
**机器精度**，不取物理带——定序册 `plan/S0/gfile-roundtrip` 的判据栏就是这么写的。

★**它抓到过一件真事**（2026-09-08 首次跑）：26 个数值字段往返**逐位相同**（相对偏差
0.0，合成件与 EAST `g070754.05000` 各一份），而**头一行不是**——写出去时
`… 5000ms           3 129 129` 成了 `… 0 129 129`。写入端把 EFIT 头的 `idum` 写死成 0，
而本仓自己的字段表把 `header` 记作 *invariant*「the file's own first line」。
一条自己声明的不变量，被自己的写入端改掉了，且没有任何一处报错。已修（`format_geqdsk`）。

★为什么头一行值得判：g-file 没有版本号，头一行是它唯一的自述——谁写的、哪一炮、
哪一时刻。往返后换了内容，下游拿到的就是一份**出处被改写过**的文件。

★语料两份，各答一问：仓内合成件（永远在场，构造已知）与一份**真炮**（列宽、负号
吃空格、老写法都在里面——合成件挑不出这些）。真炮件够不到就 skip 并点名。
"""
from __future__ import annotations

import os
import pathlib
import tempfile

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
SYNTHETIC = REPO / "rust" / "fylite_runtime" / "testdata" / "g_synthetic.geqdsk"
#: 真炮件在 fydoc 检出里（本仓不带真炮 g-file）。
#: ★2026-09-08 迁址：这份真炮件此前住在 fydoc 的 `todelete/` 下——一批**不可重取**
#: 的 ASIPP 件被一个名叫「待删」的目录持有着。现按「原件与其登记同址」收进算例书
#: `FYDOC-CASE-19-east-efit/corpus/`（`case.yaml` 逐件记 sha256）。
#: 环境变量优先，好让别处的检出也能指过来；够不到时本门 skip 并点名，不拿合成件顶替。
REAL = pathlib.Path(os.environ.get("FYDOC_DIR", str(pathlib.Path.home() / "workspace/fydoc"))) \
    / "cases/FYDOC-CASE-19-east-efit/corpus/g070754.05000"

#: 恒等式的容差：机器精度。物理带会掩盖「写入端换了一个数」这类偏差。
TOL = 1e-9


def _cases():
    out = [pytest.param(SYNTHETIC, id="synthetic")]
    out.append(pytest.param(REAL, id="east-70754",
                            marks=pytest.mark.skipif(not REAL.is_file(),
                                                     reason=f"没有真炮 g-file：{REAL}")))
    return out


@pytest.fixture(scope="module")
def io():
    if not SYNTHETIC.is_file():
        pytest.skip(f"没有合成件：{SYNTHETIC}")
    from fylite.io import geqdsk
    return geqdsk


def _roundtrip(io, path):
    a = io.read_geqdsk(path)
    with tempfile.TemporaryDirectory() as td:
        return a, io.read_geqdsk(io.write_geqdsk(a, pathlib.Path(td) / "roundtrip.geqdsk"))


@pytest.mark.parametrize("path", _cases())
def test_every_number_survives_the_round_trip(path, io):
    import numpy as np
    a, b = _roundtrip(io, path)
    assert set(a) == set(b), f"往返丢/多了字段：{set(a) ^ set(b)}"
    worst, where = 0.0, None
    for k, x in a.items():
        if isinstance(x, str):
            continue
        x = np.atleast_1d(np.asarray(x, float))
        y = np.atleast_1d(np.asarray(b[k], float))
        assert x.shape == y.shape, f"{k}: 形状 {x.shape} -> {y.shape}"
        if not x.size:
            continue
        d = float(np.max(np.abs(x - y) / np.maximum(np.abs(x), 1e-300)))
        if d > worst:
            worst, where = d, k
    assert worst <= TOL, f"最劣相对偏差 {worst:.3e} 在 {where}（容差 {TOL:g}）"


@pytest.mark.parametrize("path", _cases())
def test_the_first_line_is_an_invariant(path, io):
    """头一行是这份文件的自述，本仓的字段表把它记作 invariant。

    ★★分开判、不并进上一条：数值往返一直是对的，**只有这一行不是**。并成一条的话，
    「26 个字段全对」会把它盖住——而它恰恰是那次唯一的缺陷。"""
    a, b = _roundtrip(io, path)
    assert a["header"] == b["header"], (
        f"头一行经一次往返变了：\n  in : {a['header']!r}\n  out: {b['header']!r}")


@pytest.mark.parametrize("path", _cases())
def test_the_cocos_measurement_does_not_move(path, io):
    """COCOS 是**量出来的**（`measure_cocos`），不是读标签读来的；往返不该改变它。

    ★标签是离散值，判等不判带（定序册的第二条判据）。"""
    a, b = _roundtrip(io, path)
    ca, cb = io.measure_cocos(a), io.measure_cocos(b)
    assert ca == cb, f"COCOS 量到的口径变了：\n  in : {ca}\n  out: {cb}"
