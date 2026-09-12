"""续跑：一份记录交出的状态，认得回来，摆得回去。

★★这一档钉的是 `FYL-DESIGN-18` U-19「同一份文档集在别处继续」。在 2026-09-12 之前
那句话只有浏览器一端成立（`-18` G-4：`fy run` 没有 `--resume-from`，本包没有 `resume=`），
而浏览器那一端的闸子用的是一个**确定性假件**做步进器——也就是说，跨宿主的续跑在
真内核上一次也没有被断言过。

这里断言三件事，都在真制品上：

1. 一次多步运行的记录**带 `fylite:state`**，且它的每一个标量都是内核声明过的参数名；
2. Python 与命令行**读同一份**那个子树（本档读，`fy run --resume-from` 摆）；
3. **N 步 ≡ k 步 + 续 (N−k) 步**——在滞后量不起作用的那一档上逐位相同。

★第三条**有范围**，而范围要写出来：`code/evolve` 的三条滞后量交不过去
（`FYL-DESIGN-16` F-2 / G-8，见 `engine/resume.py` 抬头），所以逐位那一条只对
常数闭合成立。开了新经典闭合是 61 %——那个数不在这里断言（它是缺口的大小，不是
判据），而是记在 `FYL-REPORT-07`。这里只断言**那一档确实逐位**，以及**记录如实
说了自己交不出滞后量**。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from fylite.engine import resume

ROOT = Path(__file__).resolve().parents[2]
FY = ROOT / "rust" / "fylite_runtime" / "target" / "release" / "fy"
CASE = ROOT / "docs" / "examples" / "evolve" / "evolve-default.jsonld"

pytestmark = pytest.mark.skipif(
    not FY.is_file() or not CASE.is_file(),
    reason="no built executable (bash rust/build.sh --exe) or no case corpus")


def _run(out: Path, *args: str) -> Path:
    cmd = [str(FY), "run", str(CASE), *args, "-o", str(out), "--quiet"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                       env={"FY_NO_BANNER": "1", "PATH": "/usr/bin:/bin"})
    assert (out / "record.jsonld").is_file(), (
        f"no record from {' '.join(cmd)}\nstdout: {r.stdout[-800:]}\nstderr: {r.stderr[-800:]}")
    return out


@pytest.fixture(scope="module")
def twenty(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("b1"), "nsteps=20")


def test_a_multi_step_record_carries_its_state(twenty):
    """★没有这个子树，断点仓只会说「这份记录没有 fylite:state」——而那句话在
    2026-09-12 之前对**每一份** `fy run` 的记录都成立。"""
    rec = json.loads((twenty / "record.jsonld").read_text(encoding="utf-8"))
    st = rec.get("fylite:state")
    assert st, "a 20-step march wrote no fylite:state"
    assert st["type"] == "fylite:CarriedState"
    assert st["code"] == "code/evolve"
    assert st["step"] == 20.0
    assert st["settings"], "the state carries no settings"
    assert "core_profiles" in st["documents"]


def test_every_carried_name_is_one_the_kernel_declares(twenty):
    """★★交接单里的名字要是**内核声明过的参数**，不是本仓编的。

    编一个内核不认识的名字，门会按名拒绝（`FR-KERNEL-002`）——那还算好的；
    真正坏的是编一个内核**认识但不是这个意思**的名字，那就没有任何东西会报错。
    """
    from fylite import _fyo_interface as fi

    blocks = getattr(fi, "BLOCKS", None)
    if not isinstance(blocks, dict):                        # 生成物的形变了就点名跳过
        pytest.skip("_fyo_interface exposes no BLOCKS mapping to check against")
    declared = {row["key"] for rows in blocks.values() for row in rows}
    st = resume.carried(twenty)
    unknown = sorted(set(st.settings) - declared)
    assert not unknown, f"the carried state names parameters the kernel does not declare: {unknown}"


def test_python_and_the_command_line_read_the_same_subtree(twenty):
    """★两侧读同一份，所以不可能各自长出一套续跑语义。"""
    st = resume.carried(twenty)
    raw = json.loads((twenty / "record.jsonld").read_text(encoding="utf-8"))["fylite:state"]
    assert st.settings == raw["settings"]
    assert st["step"] == raw["step"] and st["t"] == raw["t"]
    assert set(st.documents) == set(raw["documents"])
    #: 文档路径解析成绝对路径，且真的在盘上——相对路径在别处继续时解析不了
    for p in st.documents.values():
        assert Path(p).is_file(), p


def test_a_single_step_record_says_it_has_nothing_to_continue(tmp_path):
    """★「没有中间态」是**答案**，不是故障（U-10）——所以它是一句话，不是一个空 dict。"""
    f = tmp_path / "record.jsonld"
    f.write_text(json.dumps({"type": "spo:ComputationRecord", "id": "x"}), encoding="utf-8")
    with pytest.raises(resume.ResumeError, match="fylite:state"):
        resume.carried(f)
    #: 不是记录的东西也要点名，而不是当成一份空记录
    g = tmp_path / "not-a-record.jsonld"
    g.write_text(json.dumps({"type": "fyo:ScenarioSpecification"}), encoding="utf-8")
    with pytest.raises(resume.ResumeError, match="spo:ComputationRecord"):
        resume.carried(g)


def test_resuming_is_the_same_march_under_the_neoclassical_closure(tmp_path):
    """★★**40 步 ≡ 20 步 + 续 20 步，新经典闭合 + 密度 + 动量通道，逐位。**

    ★这一档此前差 **61 %**（Te）与 **70 %**（n_e），`FYL-REPORT-07` §9.1 ① 把它记作
    「`-16` G-8 的大小」。2026-09-12 查明**不是交接单的形**，是一条缝：`code/evolve`
    的新经典闭合读 q，而它写出的梯子只有九行、**独缺 q**；续跑绑回那份文档时门改走
    「绑定梯子」那一档，q 读成零，闭合内部把 q 夹到 1e-3，chi 塌成 ~0（整跑第 2 步
    0.19–1.6，续跑那一步 2e-6），于是续跑几乎无输运地升温。**两处都补了**：写出侧加
    q，绑定侧对「closure ≥ 2 而 q 全零」按名拒绝。补后逐位相同 —— 本判据钉的就是这个。
    """
    arg = ["closure=2", "ch-density=true", "ch-momentum=true"]
    forty = _run(tmp_path / "n40", "nsteps=40", *arg)
    twenty = _run(tmp_path / "n20", "nsteps=20", *arg)
    cont = tmp_path / "n20c"
    r = subprocess.run(
        [str(FY), "run", str(CASE), "nsteps=20", *arg, "--resume-from", str(twenty),
         "-o", str(cont), "--quiet"],
        capture_output=True, text=True, timeout=1800,
        env={"FY_NO_BANNER": "1", "PATH": "/usr/bin:/bin"})
    assert (cont / "record.jsonld").is_file(), f"resume wrote no record: {r.stderr[-800:]}"

    def prof(d: Path, leaf: str):
        o = json.loads((d / "core_profiles.fyo.jsonld").read_text(encoding="utf-8"))["profiles_1d"]
        return o["electrons"]["temperature"] if leaf == "te" else o["electrons"]["density"]

    for leaf in ("te", "ne"):
        a, b = prof(forty, leaf), prof(cont, leaf)
        assert len(a) == len(b) and a, leaf
        worst = max(abs(x / y - 1) if y else abs(x - y) for x, y in zip(b, a))
        assert worst == 0.0, f"{leaf}: 40 steps vs 20 + 20 differ by {worst:.3e} (was 6.08e-01 before the q row)"


def test_resuming_is_the_same_march_where_the_lag_does_not_bite(tmp_path, twenty):
    """★★判据：**40 步 ≡ 20 步 + 续 20 步**，逐位。

    ★范围是常数闭合（这条算例的缺省）。滞后量在这一档上是死的，所以交不过去也
    不改变答案——实测 0.000e+00。换成新经典闭合就不是了（61 %），而那是 G-8 的
    大小，不是这条判据的反例：本档断言的是**机制对**，缺口另有登记。
    """
    forty = _run(tmp_path / "a", "nsteps=40")
    cont = tmp_path / "b2"
    r = subprocess.run(
        [str(FY), "run", str(CASE), "nsteps=20", "--resume-from", str(twenty),
         "-o", str(cont), "--quiet"],
        capture_output=True, text=True, timeout=600,
        env={"FY_NO_BANNER": "1", "PATH": "/usr/bin:/bin"})
    assert (cont / "record.jsonld").is_file(), f"resume wrote no record: {r.stderr[-800:]}"

    def te(d: Path):
        doc = json.loads((d / "core_profiles.fyo.jsonld").read_text(encoding="utf-8"))

        def find(n, path=""):
            if isinstance(n, dict):
                for k, v in n.items():
                    if k.startswith("@"):
                        continue
                    got = find(v, f"{path}/{k}" if path else k)
                    if got is not None:
                        return got
            elif isinstance(n, list) and path.endswith("electrons/temperature"):
                return n
            return None

        return find(doc)

    a, b = te(forty), te(cont)
    assert a and b and len(a) == len(b)
    worst = max(abs(x - y) / max(abs(x), 1e-30) for x, y in zip(a, b))
    assert worst == 0.0, (
        f"40 steps and 20 + resume(20) differ by {worst:.3e} on Te — the handover lost something")
    #: 时刻也要对上：对得上剖面而对不上时钟，说明状态只搬了一半
    sa = json.loads((forty / "record.jsonld").read_text(encoding="utf-8"))["fylite:state"]
    sb = json.loads((cont / "record.jsonld").read_text(encoding="utf-8"))["fylite:state"]
    assert sa["t"] == sb["t"], f"the clocks disagree: {sa['t']} vs {sb['t']}"


def test_the_record_says_which_kernel_wrote_it(twenty):
    """★K-7 / S-6：续跑之前要比得了内核身份。这在 2026-09-12 之前对 `fy run` 的
    记录**不成立**——`environment` 键根本不在（`FYL-REPORT-07` C-6）。"""
    sha = resume.kernel_of(twenty)
    assert sha and len(sha) == 64, f"no kernel fingerprint on the record: {sha!r}"
