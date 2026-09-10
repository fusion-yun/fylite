"""B-10：CHEASE 的定边界平衡，以及**一个 g-file 上的 GS 残差究竟在量什么**。

★★立项理由不是「参考取不到」——ITER IDM 的平衡件就在本机（`C-06` / `C-07` 已用）——
而是**受限载荷进不了公开渲染件**：那两条的语料标 Internal Use，读者复算不了。
CHEASE 是开源码、本机可构建、算例自带，于是这条给公开册子一份**可自行重跑**的平衡参考。

★而它能做那两条做不到的一件事：**旋钮可以拧**。IDM 件是固定的产物，CHEASE 可以换
分辨率重算——本门的主要产出正来自这一点。

实测（2026-09-08，`ntcase=2` 解析算例，本机构建的 CHEASE）
---------------------------------------------------------
**其一：加密输出网格，残差不降反升**（内部网格不变）::

    box 101×65    5.023e-02
    box 201×129   5.257e-02   （比 1.047）
    box 401×257   6.394e-02   （比 1.216）

**其二：固定输出网格（201×129），加密内部网格，残差下降**::

    ns=20 nt=20   8.722e-02
    默认          5.257e-02
    ns=60 nt=60   4.134e-02

两条合起来给出一个**读法**，而这个读法适用于本册子每一条用 g-file 判 GS 的记录：

★★★**在一份 g-file 上算出来的 GS 残差，量的是那份文件（解自身的精度 + 插值），
不是算子的截断误差；加密盒子不是一次收敛检验。** 盒子加密时，差分算子变锐，而被它
作用的 ψ 与右端的 p′/ff′ 仍只有内部解那么细——于是残差**变大**。

★这条读法回过头修正了 `C-06` 的注记：那边观察到 TEQ 的残差随盒子只掉**一阶**而非二阶，
当时记为「有一部分不是算子的截断误差」。本条给出了那部分是什么。

语料：本机 `third_party/chease`（源码开放，构建配方见其 `BUILD_RUN_RECIPE_fyeq.md`）。
没有构建产物就 skip 并点名——本门不替谁构建。
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess

import pytest

CHEASE = pathlib.Path(os.environ.get(
    "CHEASE_EXE", str(pathlib.Path.home() / "workspace/third_party/chease/src-f90/chease")))
CONDA_LIB = pathlib.Path.home() / ".claude-science/conda/envs/r/lib"

#: 默认内部网格、201×129 盒子上的实测 5.257e-02。带取 8e-2 并**点名两个分辨率**——
#: 它们各自都改变这个数，见抬头。
BAND = 8.0e-2


def _run(tmp: pathlib.Path, namelist: str) -> pathlib.Path:
    tmp.mkdir(parents=True, exist_ok=True)
    shutil.copy(CHEASE, tmp / "chease")
    (tmp / "chease_namelist").write_text(namelist)
    env = dict(os.environ)
    if CONDA_LIB.is_dir():
        env["LD_LIBRARY_PATH"] = f"{CONDA_LIB}:{env.get('LD_LIBRARY_PATH', '')}"
    r = subprocess.run([str(tmp / "chease")], cwd=tmp, capture_output=True,
                       text=True, timeout=900, env=env)
    out = tmp / "EQDSK_COCOS_02.OUT"
    assert out.is_file(), f"CHEASE 没写出 EQDSK（rc={r.returncode}）：{r.stdout[-300:]}"
    return out


def _gs(path: pathlib.Path) -> float:
    from fylite.engine import physics as ph, suite as sc
    rec, _ = sc.record_from_products([str(path)])
    r = ph._c_grad_shafranov(ph.Reader(sc.datasets_of(rec)), {})
    assert r.measured is not None, r.detail
    return float(r.measured)


def _namelist(nrbox: int, nzbox: int, extra: str = "") -> str:
    return (f"*** tcase2\n &EQDATA\n ntcase=2,\n nverbose=1,\n"
            f" nrbox={nrbox},\n nzbox={nzbox},\n{extra} /\n")


@pytest.fixture(scope="module", autouse=True)
def _built():
    if not CHEASE.is_file():
        pytest.skip(f"CHEASE 未构建：{CHEASE}（配方见 third_party/chease/BUILD_RUN_RECIPE_fyeq.md）")


def test_chease_equilibrium_satisfies_our_grad_shafranov(tmp_path):
    """★参考侧自己重跑一遍，不读任何冻结产物——这正是这条相对 C-06 / C-07 的价值。"""
    got = _gs(_run(tmp_path / "base", _namelist(201, 129)))
    assert got <= BAND, f"GS 残差 {got:.3e}（带 {BAND:.0e}，默认内部网格 · 盒 201×129）"


def test_the_convention_is_read_not_assumed(tmp_path):
    """CHEASE 写 COCOS 2，本仓自己量出规范：每弧度、`psi_axis` 取极小。

    ★量而不是信文件名：文件名说 `COCOS_02`，而口径是从数里读出来的（margin ≈ 70×）。"""
    from fylite.io.geqdsk import measure_cocos, read_geqdsk
    c = measure_cocos(read_geqdsk(_run(tmp_path / "cocos", _namelist(201, 129))))
    assert c["profile_gauge"].startswith("dpsi, per radian"), c["profile_gauge"]
    assert c["margin"] > 5, f"口径判读的余量只有 {c['margin']:.1f}×，不再无歧义"


def test_refining_the_internal_grid_lowers_the_residual(tmp_path):
    """★内部网格才是**解的精度**所在：加密它，残差降。"""
    coarse = _gs(_run(tmp_path / "c", _namelist(201, 129, " ns=20,nt=20,npsi=50,nchi=50,\n")))
    fine = _gs(_run(tmp_path / "f", _namelist(201, 129, " ns=60,nt=60,npsi=150,nchi=150,\n")))
    assert fine < coarse, f"加密内部网格没让残差下降：{coarse:.3e} → {fine:.3e}"
    assert coarse / fine > 1.5, f"只降了 {coarse / fine:.2f} 倍（实测 2.1 倍）"


def test_refining_the_output_box_does_not_lower_it_and_that_is_the_finding(tmp_path):
    """★★★本门最有价值的一条：**加密输出盒子，残差不降**（实测反升）。

    因此「在 g-file 上算 GS 残差」量的是**那份文件**（解自身的精度 + 插值到盒子），
    不是算子的截断误差；加密盒子**不是**一次收敛检验。本册子每一条用 g-file 判 GS 的
    记录都受这一条约束——`C-06` 观察到的「只掉一阶」由此得到解释。

    它若哪天真的随盒子二阶下降，说明写出方把源函数也一并加密了，那时这条读法要重写。"""
    small = _gs(_run(tmp_path / "s", _namelist(101, 65)))
    big = _gs(_run(tmp_path / "b", _namelist(401, 257)))
    assert big > small * 0.9, (
        f"加密盒子把残差降下去了（{small:.3e} → {big:.3e}）——"
        "本条的读法（残差由内部解与插值主导）不再成立，须重写")
