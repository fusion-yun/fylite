#!/usr/bin/env python3
"""CFEDR 堆芯模型（单文件工具）：按名表 dict 进出，物理由 fylite 内核库算。

两个入口：

1. :func:`step` —— 输入**当前等离子体状态** + **下一时刻的控制参数**（输入名表，dict：
   ``time`` · ``Ip`` · ``NBI`` · ``ECRH`` · ``ICRF`` · ``LHW`` · ``ne_bar`` · ``n_roh``
   · ``boundary``（控制点 R/Z）· ``pf_current``），返回**下一时刻的状态**与输出名表 dict
   （:data:`OUTPUTS` 那一张表：12 个 0-D 量 · 4 + 11 条剖面 · PF 电流）。
2. :func:`run_discharge` —— 循环调用 :func:`step`，按回放指令走完**上升 · 平顶 · 下降**整个放电，
   结果写成一份**扁平 JSON**（一层键 → 数组）。

物理调用：``libfylite.so`` 的 JSON 门 ``fylite_runtime_case_tree_json(code, plan, kernel_lib)``
把工况交给内核的 ``code/evolve``（本文件只用 ctypes，不 import fylite 包）。
fylite 只装**一个** ``libfylite.so``：内核（物理）与中间层（格式 · 装配）在同一个库里，所以
第三个参数留空——门用它自己链着的那份内核。库的位置**只有一处**：脚本旁边的
``libfylite.so``（:data:`LIB`），不搜索上层目录，也不读环境变量。

★本模型的边界（读数才算数，别的都写在这里）：

* 一次调用 = 一个内核工况（``code/evolve``，``t_stop`` 停在 ``time``），内核自己按交换上限
  取物理步，宿主只给窗边与步长上限 ``dt_max``。
* **宿主一条物理都不算**：输出名表里的每一格不是内核的事实 / 剖面，就是自由边界解的结果，
  或是回显指令（见 :data:`PROVENANCE`）。聚变与辅助加热的功率密度取内核的
  ``p_fus_dens`` / ``p_aux_dens``，热压强取 ``pressure_thermal``。
* **ECRH 与 ICRF 只能合并**：工况里只有一张沉积表（``sources = table``），两者按总功率整体缩放该表；
  分谱沉积要另给两张表。
* **NBI / LHW 不建模**：CFEDR 方案本身不含，装置描述也没有束能量 / 注入几何 / n_∥ 谱；非零即拒。
* **固定位形档**（``boundary_mode="check"``，缺省）**边界八点不进输运度规**：1.5-D 推进用工况自带的
  固定 g-file 度规（``geometry = gfile``）。八点只用来 ① 检查闭合与正 R，② 算 ``dfsdev``——
  指令边界点到模型实际用的 LCFS 的距离（rms, m）。要让位形随时间变，走 ``boundary_mode="isoflux"``：
  每步重解自由边界并把 ψ · 边界 · 磁轴 · q / F 换进推进的位形。
* ``wmhd`` = 热储能 + 快 α 储能（``w_th + w_fast``）。

★**跑一炮要的东西都在本脚本旁边**，命令就在这个目录里发：装置描述 ``device_cfedr.json`` ·
初始状态 ``state_init.json`` · 控制波形 ``waveform_d2025.json`` ·
库 ``libfylite.so``。本脚本不引用目录之外的任何文件，也没有绝对路径；产物落在 ``--out``
说的地方。

★★★**JSON 只有四类**，按**内容**认，命令行上一格一类：**装置描述**（``--device``）·
**状态**（起步态 + 物理设置 + 上一次内核记录；初始 · 中间 · 结束同一类，``--state`` 进、
``--out`` 出）· **控制波形**（名表节点表，``--waveform``）· **完整时序**（``--series``，出）。
上游那两种形状读进来当场转、并在 stderr 说一句：``code/evolve`` 工况 → 状态，PCS 回放 → 波形。

命令行::

    # 工况当起点 + 回放当波形，推 110 s，写出演化完成的状态与整段时序
    python cfedr_core_model.py --device device_cfedr.json \
        --state state_init.json --waveform waveform_d2025.json --t1 150 \
        --out state_150.json --series run_150.json

    # 接着走：上一份状态 + 一份节点表波形
    python cfedr_core_model.py --device device_cfedr.json \
        --state state_150.json --waveform waveform_d2025.json --duration 60 --out state_210.json

在 Python 里走**一步**（这是最小的一次完整调用）::

    import cfedr_core_model as M

    state = M.load_state("state_init.json")              # 起步状态
    state, out = M.step(state, {                                # 下一时刻的控制（输入名表）
        "time": 40.5, "Ip": 10.125e6,
        "ECRH": 20e6, "ICRF": 0.0, "NBI": 0.0, "LHW": 0.0,
        "ne_bar": 3.8e19,
    })
    print(out["P_fusion"] / 1e6, "MW", out["betan"], len(out["Te"]))   # 33.1 MW 0.56 52
    state, out = M.step(state, {"time": 41.0, "Ip": 10.25e6,    # 再一步：接着上一个 state
                                "ECRH": 20e6, "ICRF": 0.0, "NBI": 0.0, "LHW": 0.0,
                                "ne_bar": 3.9e19})
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# 名表：两张表（进 / 出），键就是名字；dict 是对外**唯一**的形状。
# --------------------------------------------------------------------------- #
#: 输入名表：1..8 为标量与边界点数，9.. 为 R1 Z1 R2 Z2 …（`2 × boundary_number` 个），
#: 其后 `coil_number` 与 I_coil1..n（PF 线圈电流，整匝安匝 [A·turns]，与装置卡 `i_max_aturn` 同口径）
#:
#: ★★★`ne_bar`（线平均密度指令 [m^-3]）**是名表的一项**。原始那张表
#: 只有 I_p 与四路加热，而密度在真机上是**独立的一路控制回路**（干涉仪弦平均作设定值、气/弹丸
#: 作执行器），CFEDR 文献给的场景规格也正是 n̄_e(t)。名表说的是「下一刻的控制参数」，缺它就是
#: 缺一路执行器：实测只按原名表走整炮，平顶密度掉到 4×10¹⁹ 量级、**P_fus 停在 54 MW**
#: （参考 1245 MW），燃烧点守不住。给 0 表示**不控密度**（回到工况自带的恒定加料率）。
#: ★点数不再是名表的一项：dict 里 `len(boundary)` 就是点数，再写一遍只会出现「两处不一致」
#: 这种只有位置表才有的毛病。★`n_roh`（剖面点数）是**输入**：它说的是「这一炮的径向分辨率」，
#: 属于请求，不属于答案；只在起步那一步生效（状态一旦在某张网格上推进，中途换网格要重映）。
INPUT_NAMELIST = ("time", "Ip", "NBI", "ECRH", "ICRF", "LHW", "ne_bar", "n_roh")
BOUNDARY_POINTS = 8
#: ★★★**输出名表就是这一张表**：0-D 与剖面并列，一张到底。
#: 一行 = 键 · 名字（带符号）· 单位 · 形状 · 来路 · 怎么取（`None` 表示 `_outputs` 里直接给）。
#: 形状：`0d` 每步一个数 · `1d` 每步一条剖面（nt × n）· `coil` 每步一组线圈值（nt × m）。
#: 来路三种：`kernel` 门直接给 · `solver` 自由边界解给 · `echo` 回显指令，外加一格
#: `check`（dfsdev 在固定位形档是指令曲线与工况 LCFS 的几何比对，门里没有「目标」可比）。
#: ★★★**宿主不算物理**：这张表里没有一条是这个脚本推出来的——P_fus(ρ) 与 P_aux(ρ) 取内核的
#: `p_fus_dens` / `p_aux_dens`，热压强取 `pressure_thermal`，0-D 全是门报的事实。
#: ★这张表是**唯一**的来源：扁平文件的列、`meta.namelist` / `meta.profiles` / `meta.provenance`、
#: 页面的通道选择器全从它出。
OUTPUTS = (
    ("P_fusion",     "聚变功率 P_fus",         "W",      "0d", "kernel",  None),
    ("betat",        "环向比压 β_t",            "%",      "0d", "kernel",  None),
    ("betan",        "归一比压 β_N",            "1",      "0d", "kernel",  None),
    ("betap",        "极向比压 β_p",            "1",      "0d", "kernel",  None),
    ("li",           "内感 l_i(3)",            "1",      "0d", "kernel",  None),
    ("dfsdev",       "边界偏差 dfsdev",         "m",      "0d", "check",   None),
    ("vloop",        "环电压 V_loop",           "V",      "0d", "kernel",  None),
    ("wmhd",         "储能 W_MHD",             "J",      "0d", "kernel",  None),
    ("ne_bar_cmd",   "线平均密度指令 n̄_e,cmd",  "m^-3",   "0d", "echo",    None),
    ("ne_bar",       "线平均密度 n̄_e",         "m^-3",   "0d", "kernel",  None),
    ("fuel_rate",    "加料率 Γ_fuel",          "s^-1",   "0d", "kernel",  None),
    ("n_coil",       "线圈数",                  "1",      "0d", "echo",    None),
    ("rho_tor_norm", "归一环向通量半径 ρ_tor,N", "1",      "1d", "kernel",  None),
    ("Te",           "电子温度 T_e",            "eV",     "1d", "kernel",  None),
    ("Ti",           "离子温度 T_i",            "eV",     "1d", "kernel",  None),
    ("Ne",           "电子密度 n_e",            "m^-3",   "1d", "kernel",  None),
    ("q",            "安全因子 q",              "1",      "1d", "kernel",  lambda c: c.cp("q")),
    ("p_fus",        "聚变功率密度 P_fus",       "W.m^-3", "1d", "kernel",  lambda c: c.fld("p_fus_dens")),
    ("p_aux",        "辅助加热功率密度 P_aux",   "W.m^-3", "1d", "kernel",  lambda c: c.fld("p_aux_dens")),
    ("p_ohm",        "欧姆加热功率密度 P_Ω",     "W.m^-3", "1d", "kernel",  lambda c: c.fld("ohm")),
    ("p_rad",        "辐射功率密度 P_rad",       "W.m^-3", "1d", "kernel",  lambda c: c.p_rad()),
    ("pressure",     "热压强 p_th",             "Pa",     "1d", "kernel",  lambda c: c.pressure()),
    ("p_fast_alpha", "快 α 压强 p_α,fast",      "Pa",     "1d", "kernel",  lambda c: c.sp("p_fast_alpha")),
    ("j_bs",         "自举电流密度 j_BS",        "A.m^-2", "1d", "kernel",  lambda c: c.fld("j_bs")),
    ("j_cd",         "驱动电流密度 j_CD",        "A.m^-2", "1d", "kernel",  lambda c: c.fld("j_cd")),
    ("fpol",         "极向流函数 F = R·B_φ",     "T.m",    "1d", "kernel",  lambda c: c.eqp("f")),
    ("psi_norm",     "归一磁通 ψ_N",            "1",      "1d", "kernel",  lambda c: c.psi_norm()),
    ("pf_current",   "PF 线圈电流 I_coil",       "A.turns", "coil", "echo",   None),
)
#: 按形状取键——写文件与建页面通道都用它，不另抄清单
OUT_KEYS = lambda shape: tuple(k for k, _l, _u, sh, _p, _t in OUTPUTS if sh == shape)  # noqa: E731
OUTPUT_NAMELIST = tuple(k for k, _l, _u, _sh, _p, _t in OUTPUTS)

#: 单位（本工具对外一律 SI）：Ip [A] · 功率 [W] · 时间 [s] · 边界 [m] · 温度 [eV] · 密度 [m^-3]
UNITS_IN = {"time": "s", "Ip": "A", "NBI": "W", "ECRH": "W", "ICRF": "W", "LHW": "W",
            "ne_bar": "m^-3", "n_roh": "1", "boundary": "m", "pf_current": "A.turns"}
UNITS_OUT = {"P_fusion": "W", "betat": "%", "betan": "1", "betap": "1", "li": "1", "dfsdev": "m",
             "vloop": "V", "wmhd": "J", "ne_bar_cmd": "m^-3", "ne_bar": "m^-3",
             #: 加料率：内核 `code/evolve` 的 `fuel_rate` 设置（弹丸粒子率），口径随工况
             "fuel_rate": "s^-1", "n_coil": "1", "Te": "eV", "Ti": "eV", "Ne": "m^-3",
             "pf_current": "A.turns"}

#: 续跑交接（内核 `fyo::EVOLVE_RESUME` 声明的同一张表；这里按字面带着，避免 import fylite 包）
_CARRY = (("t_end", "t_start"), ("dt_next", "dt_start"), ("edge_te_out", "edge_te_in"),
          ("edge_ti_out", "edge_ti_in"), ("dt_capped", "capped_in"),
          ("saw_elapsed_out", "saw_elapsed_in"), ("dt_fraction_used", "dt_fraction_in"),
          ("ipctl_ratio0_out", "ipctl_ratio0_in"), ("ipctl_integral_out", "ipctl_integral_in"),
          ("ipctl_calibrated_out", "ipctl_calibrated_in"), ("lh_phase_out", "lh_phase_in"),
          ("chi_scale_ploss_ref", "chi_scale_ploss_ref"), ("chi_scale_ne_ref", "chi_scale_ne_ref"),
          ("chi_scale_ip_ref", "chi_scale_ip_ref"), ("chi_scale_w_ref", "chi_scale_w_ref"),
          ("chi_scale_int", "chi_scale_int"))
_LAGS = (("psi_prev_out", "fylite:psi_prev"), ("sigma_prev_out", "fylite:sigma_prev"),
         ("exch_prev_out", "fylite:exch_prev"))
_PROFILE_LAGS = ("fylite:psi_prev", "fylite:sigma_prev", "fylite:exch_prev",
                 "fylite:dn_prev", "fylite:vn_prev", "zeff")


class KernelError(RuntimeError):
    """内核库没打开 / 门没走通。"""


class Refused(RuntimeError):
    """内核拒绝了这次工况（``code`` 与它自己的那句话）。"""

    def __init__(self, code: int, message: str, record=None):
        self.code, self.record = int(code), record
        super().__init__(f"内核拒绝（{code}）：{message}")


# --------------------------------------------------------------------------- #
# 内核门：JSON 进，记录 JSON 出
# --------------------------------------------------------------------------- #
#: ★★★**库就在脚本旁边，名字固定**：`app/libfylite.so`（一个真文件，没有版本后缀链接）。
#: 不搜索上层目录、不读环境变量、不认第二个名字——「到别处找库」找错了**不会报错**，
#: 它会静默地用另一份库算完整炮，而那种错误只在读数上露一点。要换库就换这个文件。
LIB = Path(__file__).resolve().parent / "libfylite.so"


class Kernel:
    """:data:`LIB` 的 JSON 门 —— 内核与中间层在同一个库里。"""

    def __init__(self) -> None:
        #: ★内核库这一格**留空**：内核与中间层在同一个 `libfylite.so` 里，门用它自己链着的那份。
        self.kernel_lib = ""
        try:
            self.lib = ctypes.CDLL(str(LIB))
        except OSError as exc:
            #: ★这份库**不链 HDF5 / netCDF**（`ldd` 上只有 libgcc_s / libm / libc），所以打不开
            #: 一般是文件不在、位数不对或没有执行权限，不是缺 C 库。
            raise KernelError(f"打不开 {LIB}：{exc}") from exc
        f = self.lib.fylite_runtime_case_tree_json
        f.argtypes = [ctypes.c_char_p, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_uint64,
                      ctypes.c_char_p, ctypes.c_uint64,
                      ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint64)]
        f.restype = ctypes.c_int32
        self.lib.fylite_runtime_case_free.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        self.lib.fylite_runtime_case_free.restype = None
        self.identity = self._identity()

    def _identity(self) -> dict:
        """算这些数的**内核是哪一份**：ABI 号 + 链进库的那次内核构建（版本 · 时刻 · sha256）。

        随输出走进 `meta.kernel_*`，页面页首显示。两处来源：
        `fylite_rs_abi_version()`（内核自己的 C 导出）与 `fylite_runtime_linked_kernel()`
        （中间层在链接期把 `kernel-static.json` 编了进去）。取不到就留空，不编。
        """
        out: dict = {}
        try:
            self.lib.fylite_rs_abi_version.restype = ctypes.c_uint32
            self.lib.fylite_rs_abi_version.argtypes = []
            out["abi"] = int(self.lib.fylite_rs_abi_version())
        except Exception:                                              # noqa: BLE001
            pass
        try:
            f = self.lib.fylite_runtime_linked_kernel
            f.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint64)]
            f.restype = ctypes.c_int32
            buf, n = ctypes.c_void_p(), ctypes.c_uint64(0)
            if f(ctypes.byref(buf), ctypes.byref(n)) == 0 and buf.value and n.value:
                try:
                    out.update(json.loads(ctypes.string_at(buf, n.value).decode("utf-8", "replace")) or {})
                finally:
                    self.lib.fylite_runtime_case_free(buf, n)
        except Exception:                                              # noqa: BLE001
            pass
        out["lib"] = str(getattr(self.lib, "_name", ""))
        return out

    def complete(self, code: str, plan: dict) -> dict:
        """一份工况进，一份记录出；被拒时抛 :class:`Refused`（记录里带内核那句话）。"""
        cb = code.encode(); jb = json.dumps(plan, allow_nan=True).encode(); kb = self.kernel_lib.encode()
        out, n = ctypes.c_void_p(), ctypes.c_uint64(0)
        rc = self.lib.fylite_runtime_case_tree_json(cb, len(cb), jb, len(jb), kb, len(kb),
                                                    ctypes.byref(out), ctypes.byref(n))
        try:
            text = ctypes.string_at(out, n.value).decode("utf-8", "replace") if out.value and n.value else ""
        finally:
            if out.value and n.value:
                self.lib.fylite_runtime_case_free(out, n)
        if rc < 0:
            raise KernelError(f"fylite_runtime_case_tree_json 返回 {rc}：{text}")
        rec = json.loads(text) if text else None
        if rc == 1:
            ref = (rec or {}).get("refusal", {})
            raise Refused(int(ref.get("code", rc)), ref.get("message", ""), rec)
        return rec


_KERNEL: Kernel | None = None


def kernel() -> Kernel:
    global _KERNEL
    if _KERNEL is None:
        _KERNEL = Kernel()
    return _KERNEL


# --------------------------------------------------------------------------- #
# 名表就是 dict —— 进出**只收 dict**，没有按位置的那一种写法
# --------------------------------------------------------------------------- #
#: ★**不提供**「按 index 顺序的一串数」与 dict 的互转：一份数据两种写法，位置一错就是
#: **静默错位**（第 7 项到底是 n̄_e 还是点数，没人看得出来），而 `INPUT_NAMELIST` /
#: `OUTPUT_NAMELIST` 两张表本来就把名字说全了。
#: 文件交换走 `write_waveform` / `read_waveform` / `write_output` 的扁平 dict，进程内交换走
#: `step(state, control_dict)`——两条路都按名字。

# --------------------------------------------------------------------------- #
# 状态与一步推进
# --------------------------------------------------------------------------- #
def init_state(plan, t0: float | None = None) -> dict:
    """起步状态：一份 ``code/evolve`` 工况（路径或 dict）+ 起步时刻。

    状态是纯 JSON：``{"t", "plan", "record"}``——可以整份存盘、下次接着走（快照 = 这份 dict）。
    """
    doc = json.loads(Path(plan).read_text(encoding="utf-8")) if isinstance(plan, (str, Path)) else plan
    t = float(doc["settings"].get("t_start", 0.0)) if t0 is None else float(t0)
    return {"t": t, "plan": {"settings": dict(doc["settings"]), "inputs": dict(doc.get("inputs") or {})},
            "record": None}


def save_state(path, state: dict) -> str:
    """把状态整份存盘（纯 JSON：时刻 · 工况 · 上一次内核记录 · 加料 / 位形控制器状态）——断点。"""
    #: 断点只给本工具自己读：NaN / Infinity 照写（Python 的 json 收；浏览器不读这份）
    Path(path).write_text(json.dumps(state, allow_nan=True, ensure_ascii=False,
                                     default=lambda o: None), encoding="utf-8")
    return str(path)


def load_state(path) -> dict:
    """`--state` 那一格：读回一份**状态**（初始 / 中间 / 结束都是这一类）。

    ★上游的 `code/evolve` **工况**也收：它就是「还没推进过的状态」，`init_state` 给它包一层
    （时刻取 `settings.t_start`，记录留空）。于是「起新炮」与「接着跑」是同一条命令，
    差别只在给的那份文件。
    """
    doc, kind = _load_kind(path, "state", {"plan": "工况 = 还没推进过的状态"})
    return doc if kind == "state" else init_state(doc)


#: 猜起步态时，模板从这里找——脚本旁边那份初始状态
TEMPLATE_STATE = Path(__file__).resolve().parent / "state_init.json"


def guess_state(nodes: list, device: dict | None = None, template=None, log=print) -> dict:
    """**没有初始状态时猜一个**：拿模板状态的物理设置，按波形第一个节点换掉能换的那几样。

    ★这是个**起头用的猜测**，不是标定：模板（缺省是脚本旁边的 `state_init.json`）提供的是
    χ 表 · 沉积表 · 成分 · 边界值这些**物理设置**，波形只能换掉四样——时刻 · I_p · 密度标度 ·
    位形（给了装置卡才换）。温度剖面沿用模板的，因为波形里没有任何能定它的东西。
    ★为什么不从零造：`code/evolve` 的设置有六十余项（χ 标定参考 · 成分 · 台基 · 加料 · 边界），
    凭空填出来的那份跑得动也不可信，而且失败时看不出是猜错了哪一项。有模板就诚实得多：
    换掉的四样写进 `meta`，没换的照旧是模板那一炮的。
    """
    tpl = Path(template) if template else TEMPLATE_STATE
    if not tpl.is_file():
        raise ValueError(f"没有初始状态，也找不到模板 {tpl}：给 --state，或把一份状态放到脚本旁边")
    st = load_state(tpl)
    n0 = nodes[0]
    plan = {"settings": dict(st["plan"]["settings"]), "inputs": dict(st["plan"].get("inputs") or {})}
    t0 = float(n0.get("time", st["t"]))
    changed = ["时刻", "I_p"]
    plan["settings"]["t_start"] = t0
    plan["settings"]["ip"] = float(n0.get("Ip", 0.0)) / 1e3
    #: 密度：把模板的起步剖面整体缩放到这一节点的 n̄_e（ρ 网格上的算术平均口径，与输出的 `ne_bar` 同）
    ne_cmd = float(n0.get("ne_bar", 0.0) or 0.0)
    cp = ((plan["inputs"].get("core_profiles") or {}).get("profiles_1d") or {})
    ne = [float(x) for x in ((cp.get("electrons") or {}).get("density") or [])]
    if ne_cmd > 0 and ne:
        k = ne_cmd / (sum(ne) / len(ne))
        prof = {kk: vv for kk, vv in cp.items()}
        prof["electrons"] = dict(prof.get("electrons") or {}, density=[v * k for v in ne])
        if prof.get("fylite:ion_density"):
            prof["fylite:ion_density"] = [float(v) * k for v in prof["fylite:ion_density"]]
        plan["inputs"] = dict(plan["inputs"], core_profiles={"profiles_1d": prof})
        plan["settings"]["ne0"] = float(plan["settings"].get("ne0", 0.0)) * k
        plan["settings"]["edgene"] = float(plan["settings"].get("edgene", 0.0)) * k
        changed.append("密度标度")
    #: 位形：给了装置卡与控制点就解一次自由边界，把 ψ · 边界 · 磁轴 · q / F 换进来
    if device is not None and (n0.get("boundary") or []):
        eq, _facts, _wall = solve_equilibrium(n0["boundary"], float(n0.get("Ip", 0.0)), device)
        old = plan["inputs"].get("equilibrium") or {}
        for key in ("fylite:limiter", "vacuum_toroidal_field"):
            if old.get(key):
                eq[key] = old[key]
        p1 = ((old.get("time_slice") or {}).get("profiles_1d"))
        if not ((eq.get("time_slice") or {}).get("profiles_1d") or {}).get("q") and p1:
            eq["time_slice"]["profiles_1d"] = p1
        plan["inputs"] = dict(plan["inputs"], equilibrium=eq)
        changed.append("位形")
    if log:
        log(f"★猜的起步态：模板 {tpl.name} 的物理设置 + 波形第一个节点（换了 {' · '.join(changed)}；"
            f"温度剖面与其余设置沿用模板）——这是开个头，不是标定")
    return {"t": t0, "plan": plan, "record": None, "guessed": {"template": str(tpl), "changed": changed}}


def _geometry(plan: dict) -> dict:
    """工况自带的位形：LCFS 点列、B_0、几何轴与小半径（``dfsdev`` 与 ``meta.*`` 要用）。"""
    eq = (plan.get("inputs") or {}).get("equilibrium") or {}
    ts = eq.get("time_slice") or {}
    bnd = ((ts.get("boundary") or {}).get("outline") or {})
    r, z = bnd.get("r") or [], bnd.get("z") or []
    vac = eq.get("vacuum_toroidal_field") or {}
    b0 = abs(float((vac.get("b0") or [6.3])[0] if isinstance(vac.get("b0"), list) else vac.get("b0", 6.3)))
    r0v = float((vac.get("r0") or [7.8])[0] if isinstance(vac.get("r0"), list) else vac.get("r0", 7.8))
    a = (max(r) - min(r)) / 2.0 if r else 2.45
    return {"lcfs_r": list(map(float, r)), "lcfs_z": list(map(float, z)), "b0": b0, "r0": r0v, "a": a}


def device_meta(plan: dict) -> dict:
    """装置常数与第一壁——**写进输出的 `meta.*`**，让输出文件自带写 g-file 所需的一切。

    ★为什么放在 meta 而不是逐时间片：R₀ / B₀ 与限制器在一炮里不变，逐片存 383 遍是死重。
    """
    geo = _geometry(plan)
    lim = ((plan.get("inputs") or {}).get("equilibrium") or {}).get("fylite:limiter") or {}
    return {"r0": geo["r0"], "b0": geo["b0"],
            "limiter_r": [float(x) for x in (lim.get("r") or [])],
            "limiter_z": [float(x) for x in (lim.get("z") or [])]}


def equilibrium_snapshot(plan: dict, facts: dict | None = None, *, stride: int = 1, bnd_points: int = 160,
                         psi_ends: tuple | None = None) -> dict:
    """推进当下所用位形的一帧：ψ(R,Z) 与网格 · 磁轴（O 点）· ψ_axis / ψ_bnd · LCFS 点列 · X 点。

    来源就是绑给 ``code/evolve`` 的那份平衡文档（isoflux 档里它就是刚解出来的），X 点取求解器的事实
    （限制器位形时为 NaN）。``stride`` 对 ψ 网格抽样（129 × 129 → stride 2 得 65 × 65）。

    ★★``psi_ends``（内核这一步**演化出来的**一维 ψ 的两端，`(轴, 边)`）给了就把二维 ψ 仿射拉到
    这两个值上。固定位形档里那份平衡文档是**冻结**的，它自带的 ψ 端值停在起步那一刻——实测 150 s
    处文档说轴上 −22.99 Wb，而内核演化出来的是 −141.44 Wb，差 118 Wb。ψ_N（等高线的位置）不受
    影响（仿射变换约掉了），受影响的是**绝对磁通**：写出去的 g-file 的 `simag` / `sibry` 与剖面
    是否对得上，全看这一步。isoflux 档不需要它——那里的 ψ 就是当步解出来的。
    """
    eq = (plan.get("inputs") or {}).get("equilibrium") or {}
    ts = eq.get("time_slice") or {}
    p2 = ts.get("profiles_2d") or {}
    grid = p2.get("grid") or {}
    one = lambda v: (float(v[0]) if isinstance(v, list) and v else (float(v) if isinstance(v, (int, float)) else math.nan))  # noqa: E731
    r = [float(x) for x in (grid.get("dim1") or [])][::stride]
    z = [float(x) for x in (grid.get("dim2") or [])][::stride]
    raw = p2.get("psi") or []
    nr, nz = len((grid.get("dim1") or [])), len((grid.get("dim2") or []))
    psi = []
    if raw and isinstance(raw[0], list):
        #: 求解器给的是二维（nr × nz）；工况文档里是摊平的一串
        psi = [[float(x) for x in row[::stride]] for row in raw[::stride]]
    elif raw and nr and nz and len(raw) == nr * nz:
        flat = [float(x) for x in raw]
        psi = [[flat[i * nz + j] for j in range(0, nz, stride)] for i in range(0, nr, stride)]
    gq = ts.get("global_quantities") or {}
    ax = gq.get("magnetic_axis") or {}
    out_b = (ts.get("boundary") or {}).get("outline") or {}
    br = [float(x) for x in (out_b.get("r") or [])]
    bz = [float(x) for x in (out_b.get("z") or [])]
    if len(br) > bnd_points:
        step_b = max(1, len(br) // bnd_points)
        br, bz = br[::step_b], bz[::step_b]
    f = facts or {}
    psi_ax, psi_bd = one(gq.get("psi_axis")), one(gq.get("psi_boundary"))
    if psi_ends and len(psi_ends) == 2:
        a_new, b_new = float(psi_ends[0]), float(psi_ends[1])
        span = psi_bd - psi_ax
        if all(math.isfinite(v) for v in (a_new, b_new, psi_ax, psi_bd)) and abs(span) > 1e-12:
            k = (b_new - a_new) / span
            psi = [[a_new + (v - psi_ax) * k for v in row] for row in psi]
            psi_ax, psi_bd = a_new, b_new
    return {"psi_r": r, "psi_z": z, "psi": psi,
            "axis_r": one(ax.get("r")), "axis_z": one(ax.get("z")),
            "psi_axis": psi_ax, "psi_bnd": psi_bd,
            "bnd_r": br, "bnd_z": bz,
            "xpt_r": float(f.get("xpt_r", math.nan)), "xpt_z": float(f.get("xpt_z", math.nan)),
            "diverted": float(f.get("bnd_kind", math.nan))}


def _sample_curve(r: list, z: list, n: int) -> list:
    """闭合曲线上按等间隔取 ``n`` 个点——工况那条上百点的 LCFS 变成目标曲线要用的几个点。"""
    if not r or len(r) != len(z) or n < 3:
        return []
    m = len(r)
    return [[float(r[(i * m) // n]), float(z[(i * m) // n])] for i in range(n)]


def _boundary_deviation(points, geo: dict) -> float:
    """指令边界点到模型实际用的 LCFS 的距离（rms, m）—— 名表里的 ``dfsdev``。"""
    r, z = geo["lcfs_r"], geo["lcfs_z"]
    if not points or not r:
        return math.nan
    acc = 0.0
    for pr, pz in points:
        acc += min((pr - a) ** 2 + (pz - b) ** 2 for a, b in zip(r, z))
    return math.sqrt(acc / len(points))


def _regrid_start(state: dict, n: int) -> dict:
    """把**起步工况**里所有落在径向网格上的剖面重采到 `n` 个点（`n_roh` 这个请求落在这里）。

    ★只动起步那一份：内核按 `n_surfaces` 建网格，而工况自带的剖面在另一张网格上时它按名拒绝
    （「the resumed electron temperature has 52 points, the grid 41」「the given chi profiles …」）。
    ★判据是**长度**：`inputs` 里凡是长度等于原网格点数的一维表都重采（起步剖面 · χ 表 …），
    其余原样——源项表在 ψ_N 的 201 点上、平衡在自己的网格上，都不该被这一步碰。
    ★`equilibrium` 整棵跳过：它有自己的横轴，长度偶然相同也不是这张网格。
    ★做的是**线性重采**，纯算术：横轴取 ρ_tor 归一后的同一条曲线。
    """
    plan = {"settings": dict(state["plan"]["settings"]), "inputs": dict(state["plan"].get("inputs") or {})}
    rho = [float(x) for x in (_dig(plan, ("inputs", "core_profiles", "profiles_1d", "grid", "rho_tor")) or [])]
    if len(rho) < 2:
        raise ValueError(f"n_roh = {n}：工况的起步剖面没有 rho_tor 网格，重采不了")
    plan["settings"]["n_surfaces"] = float(n - 1)
    if len(rho) == n:
        return dict(state, plan=plan)
    xs = [r / rho[-1] for r in rho]
    want = [i / (n - 1) for i in range(n)]

    def resample(node):
        if isinstance(node, dict):
            return {k: resample(v) for k, v in node.items()}
        if isinstance(node, list) and len(node) == len(rho) and all(isinstance(v, (int, float)) for v in node):
            ys = [float(v) for v in node]
            return [_interp(x, xs, ys) for x in want]
        return node

    plan["inputs"] = {k: (v if k == "equilibrium" else resample(v)) for k, v in plan["inputs"].items()}
    return dict(state, plan=plan)


def _check_control(ctl: dict, t_now: float) -> None:
    t = float(ctl["time"])
    if not t > t_now + 1e-12:
        raise ValueError(f"time {t} 不在当前时刻 {t_now} 之后")
    for name in ("Ip", "ECRH", "ICRF", "NBI", "LHW", "ne_bar", "n_roh"):
        v = float(ctl.get(name, 0.0))
        if not math.isfinite(v) or v < 0.0:
            raise ValueError(f"{name} 不是非负有限值：{ctl.get(name)}")
    if float(ctl.get("NBI", 0.0)) != 0.0:
        raise ValueError("NBI 非零：CFEDR 装置描述里没有中性束（缺束能量 · 注入几何 · 种类），本模型不建模")
    if float(ctl.get("LHW", 0.0)) != 0.0:
        raise ValueError("LHW 非零：CFEDR 装置描述里没有低杂波（缺频率 · n_∥ 谱 · 天线位置），本模型不建模")
    pts = ctl.get("boundary") or []
    if pts:
        if len(pts) < 3:
            raise ValueError(f"boundary 只有 {len(pts)} 点，至少 3 点才成一条边界")
        for i, (pr, _pz) in enumerate(pts):
            if not float(pr) > 0.0:
                raise ValueError(f"boundary 第 {i} 点的 R = {pr}（R 必须为正）")


def _resume_call(plan: dict, rec, t_stop: float, dt: float, dt_max: float | None, edge_ne: float | None = None) -> dict:
    """下一次内核调用的工况：本工况设置 + 上一记录的交接（内核声明的续跑集合）。"""
    st = dict(plan["settings"], globals=1.0, t_stop=float(t_stop))
    inp = dict(plan.get("inputs") or {})
    st["dttarget"] = float(dt_max) if dt_max else 0.0
    if dt_max:
        st["dt_max"] = float(dt_max)
    #: 本次调用的步数预算：按窗长 / 步长上限估，留四倍余量（内核还会被交换上限压得更小）
    t_now = float(rec["facts"]["t_end"]["value"]) if rec else float(st.get("t_start", 0.0))
    budget = math.ceil(max(t_stop - t_now, 0.0) / max(float(dt_max or 0.01), 1e-6)) * 4
    st["nsteps"] = float(max(16, min(budget or 16, 20000)))
    if rec is None:
        st["dt"] = float(dt)
        return {"settings": st, "inputs": inp}
    fc = rec["facts"]
    st.update({"resume": 1.0, "state": 1.0, "dt_start": float(dt)})
    for src, dst in _CARRY:
        if src in fc:
            st[dst] = fc[src]["value"]
    cp = rec["fields"]["core_profiles"]["profiles_1d"]
    prof = {"electrons": {"temperature": cp["electrons"]["temperature"]["data"],
                          "density": cp["electrons"]["density"]["data"]},
            "t_i_average": cp["t_i_average"]["data"],
            "fylite:ion_density": cp["fylite:ion_density"]["data"]}
    for slot in _PROFILE_LAGS:
        if slot in cp and isinstance(cp[slot], dict) and "data" in cp[slot]:
            prof[slot] = cp[slot]["data"]
    raw = rec["fields"]
    if "psi" in raw:
        prof["grid"] = {"psi": raw["psi"]["data"]}
    if edge_ne is not None and prof["electrons"]["density"] and float(prof["electrons"]["density"][-1]) > 0.0:
        #: 宿主侧边界密度：密度通道的边界是状态末点的 Dirichlet，按一个因子缩放电子 / 离子末点（成分不动）
        f = float(edge_ne) / float(prof["electrons"]["density"][-1])
        for key, holder in (("density", prof["electrons"]), ("fylite:ion_density", prof)):
            arr = list(holder[key])
            arr[-1] = float(arr[-1]) * f
            holder[key] = arr
    inp["core_profiles"] = {"profiles_1d": prof}
    inp["evolve"] = {dst: raw[src]["data"] for src, dst in _LAGS if src in raw}
    return {"settings": st, "inputs": inp}


#: ★★★**每个输出量是从哪来的**：写进 `meta.provenance`，页面在每张图的标题旁标出来——
#: 于是「这个数是内核算的还是宿主拼的」不必翻文档。四种来路：
#:   kernel —— 内核门直接给的（事实或剖面）；
#:   solver —— 自由边界解（`code/discharge`）给的（isoflux 档才有）；
#:   check  —— 宿主对指令与工况几何做的比对（只有 dfsdev 在固定位形档走这一格）；
#:   echo   —— 回显本步指令（不是算出来的）。
#: ★**没有 derived 这一格**：宿主一条物理都不算，剖面与 0-D 全部出自内核或求解器。
#: ★它不是第二张表——直接从 `OUTPUTS` 的「来路」那一列出。
PROVENANCE = {key: prov for key, _lab, _u, _sh, prov, _t in OUTPUTS}
#: 几条容易问「这到底是哪个口径」的量，把口径写清楚（同样写进 meta，页面做提示用）
PROVENANCE_NOTE = {
    "betat": "内核的 `beta_t`（比值）× 100",
    "dfsdev": "固定位形档：指令八点到工况所用 LCFS 的距离 rms（几何比对）；isoflux 档取求解器自己的边界间隙 rms",
    "ne_bar": "内核的 `ne_line`（∫n dρ / ρ_max）",
    "fuel_rate": "内核报的 `fuel_rate_used`（本步真正生效的那个）",
    "pressure": "内核的 `profiles_1d/pressure_thermal`",
    "p_fus": "内核的 `p_fus_dens`（α 功率按 E_α/E_fus 还原为总聚变功率密度）",
    "p_aux": "内核的 `p_aux_dens`（本步电子 + 离子加热沉积之和）",
}
def _sig(x, n: int = 7) -> float:
    """保留 n 位有效数字——剖面按整炮存，全精度会让文件涨一倍多。"""
    v = float(x)
    return v if not math.isfinite(v) else float(f"{v:.{n}g}")


def _interp(x: float, xs: list, ys: list) -> float:
    """单调 `xs` 上的线性插值（两端取端值）。"""
    if not xs:
        return math.nan
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    u = (x - xs[lo]) / ((xs[hi] - xs[lo]) or 1.0)
    return ys[lo] + (ys[hi] - ys[lo]) * u


class _Ctx:
    """一次调用里取剖面要用到的那些量——`OUTPUTS` 表里的 lambda 拿它算。

    取不到的一律返回 ``None``（那条剖面整列不写），**不编数**。
    """

    def __init__(self, rec: dict) -> None:
        self.F = F = rec["fields"]
        self._cp = F["core_profiles"]["profiles_1d"]
        self._sp = F.get("species") or {}
        self._eqp = _dig(F, ("equilibrium", "time_slice", "profiles_1d")) or {}

    @staticmethod
    def _row(node, path):
        v = _dig(node, path)
        return [float(x) for x in v] if v else None

    #: —— 门上直接有的那些 ——
    def cp(self, key):  return self._row(self._cp, (key, "data"))
    def fld(self, key): return self._row(self.F, (key, "data"))
    def sp(self, key):  return self._row(self._sp, (key, "data"))
    def eqp(self, key): return self._row(self._eqp, (key, "data"))

    def psi_norm(self):
        psi = self._row(self._cp, ("grid", "psi", "data"))
        if not psi:
            return None
        span = (psi[-1] - psi[0]) or 1.0
        return [(x - psi[0]) / span for x in psi]

    def p_rad(self):
        a, b = self.sp("rad_adas"), self.sp("rad_sync") or []
        if not a:
            return None
        return [a[i] + (b[i] if i < len(b) else 0.0) for i in range(len(a))]

    def pressure(self):
        """热压强：内核的 `profiles_1d/pressure_thermal`。

        门没给就整条不写——宿主**不**拿 e·(n_eT_e + n_iT_i) 顶上，那是第二套物理。"""
        return self.cp("pressure_thermal")


#: `OUTPUTS` 里「每步一条剖面、且要现取」的那几行——`rho_tor_norm` / `Te` / `Ti` / `Ne`
#: 由 `_outputs` 直接给（`take is None`），不走这里。
_PROFILE_ROWS = tuple((k, lab, u, prov, take) for k, lab, u, sh, prov, take in OUTPUTS
                      if sh == "1d" and take is not None)


def _profiles(rec: dict) -> dict:
    """按 :data:`OUTPUTS` 那张表取全部剖面；取不到的那条整列不写。"""
    c = _Ctx(rec)
    out = {}
    for key, _lab, _units, _prov, take in _PROFILE_ROWS:
        try:
            vals = take(c)
        except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
            vals = None
        if vals:
            out[key] = [_sig(x) for x in vals]
    return out


def _dig(d, path):
    """按路径取嵌套字典里的值；断在哪就返回 None。"""
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def _outputs(rec: dict, ctl: dict, geo: dict) -> dict:
    """记录 → 输出名表 dict（:data:`OUTPUTS` 那张表：12 个 0-D 量 · 15 条剖面 · PF 电流）。"""
    fc, F = rec["facts"], rec["fields"]
    fact = lambda k: float(fc[k]["value"]) if k in fc else math.nan  # noqa: E731
    cp = F["core_profiles"]["profiles_1d"]
    te = [float(x) for x in cp["electrons"]["temperature"]["data"]]
    ti = [float(x) for x in cp["t_i_average"]["data"]]
    ne = [float(x) for x in cp["electrons"]["density"]["data"]]
    rho = [float(x) for x in cp["grid"]["rho_tor"]["data"]]
    rho_n = [x / rho[-1] for x in rho] if rho and rho[-1] else rho
    #: ★0-D 这一组全部**照抄内核的事实**，一条都不在这里算：门没报就是 NaN（那说明这一步
    #: 内核没给，不是宿主该补的）。β_t 唯一的加工是 1 → % 的单位换算。
    p_fus = fact("p_fus")
    beta_n = fact("beta_n_tot")
    beta_t = 100.0 * fact("beta_t")
    w_th, w_fast = fact("w_th"), fact("w_fast")
    out = {
        "P_fusion": p_fus,
        "betat": beta_t,
        "betan": beta_n,
        "betap": fact("beta_pol"),
        "li": fact("li3"),
        "dfsdev": _boundary_deviation(ctl.get("boundary"), geo),
        "vloop": fact("v_loop_end"),
        "wmhd": w_th + (w_fast if math.isfinite(w_fast) else 0.0),
        #: 密度这一路**三格并列**：`ne_bar_cmd` 指令（0 = 本步不控密度）· `ne_bar` 实现 ·
        #: `fuel_rate` 执行器——读者因此不必回头翻输入就知道「要的密度」与「给的加料」。
        #: ★后两格取内核报的 `ne_line`（∫n dρ / ρ_max）与 `fuel_rate_used`（本步真正生效的
        #: 那个加料率）。反馈跟的是**比值**（目标 = 首步实现值 × 指令/首步指令），于是指令与
        #: 实现的口径差在比值里约掉，代价是整炮的绝对锚点落在首步状态上。
        "ne_bar_cmd": float(ctl.get("ne_bar", 0.0) or 0.0),
        "ne_bar": fact("ne_line"),
        "fuel_rate": fact("fuel_rate_used"),

        #: PF 线圈电流：isoflux 档取求解器解出的安匝，check 档回显指令（没给就空）
        "n_coil": len(ctl.get("pf_current") or []),
        "pf_current": [float(x) for x in (ctl.get("pf_current") or [])],
        "rho_tor_norm": rho_n,
        "Te": te, "Ti": ti, "Ne": ne,
        #: 名表里要现取的那十一条剖面（`OUTPUTS` 里 `1d` 且带取法的行）：q · 四档功率密度 ·
        #: 两档压强 · 两档电流密度 · F(ψ) · ψ_N。页面的 1-D 视图按 `meta.profiles` 现取现画。
        **_profiles(rec),
        #: 名表之外、同一次调用就有的量（不进名表，报告 / 诊断用）
        #: ★`ip_cmd` / `p_aux_cmd` 回显本步指令：输出文件因此**自带**写一份 g-file 所需的
        #: 全部量（等离子体电流在 g-file 的 `cpasma` 一格上，而它本是输入）。
        "extra": {"time": fact("t_end"), "ip_cmd": float(ctl.get("Ip", 0.0)),
                  "p_aux_cmd": float(ctl.get("ECRH", 0.0)) + float(ctl.get("ICRF", 0.0)),
                  "w_th": w_th, "w_fast": w_fast, "q_fus": fact("q_fus"),
                  "h98": fact("h98"), "f_gw": fact("f_gw"), "i_bs": fact("i_bs"), "tau_e": fact("tau_e"),
                  "beta_n_th": fact("beta_n_th"), "li1": fact("li1"), "steps": fact("steps"),
                  "lh_phase": fact("lh_phase_out"), "p_rad": _last(F, "p_rad"), "p_sep": _last(F, "p_sep")},
    }
    return out


def _last(fields: dict, key: str) -> float:
    d = (fields.get(key) or {}).get("data") or []
    return float(d[-1]) if d else math.nan


#: 反算 p′/FF′ 时，盒内重解的残差上限：低于它才投送给自由边界解。地板实测 5e-4，
#: 2e-3 把它收进来，而真发散那一档（长到盒边）是**拒绝**，走不到这里。
_INVERSION_RESIDUAL = 2e-3

#: 固定位形档的"位形该不该动"阈值 [m]：指令点到工况 LCFS 的 rms 超过它就提醒改用 isoflux。
#: 0.25 m 是这台机器上"形状确实换了"的量级（爬升段八点从小圆长到平顶形状，rms 走到 1 m 以上）。
_CHECK_SHAPE_TOL = 0.25

#: 自由边界解的缺省设置（与 `scripts/eq_sequence.py` 同口径）
DISCHARGE_SETTINGS = {"relax": 0.1, "position_control": "c4", "seed": "target"}


def solve_equilibrium(points, ip: float, device: dict, *, settings: dict | None = None,
                      pf_current=None, delivered: dict | None = None) -> tuple[dict, dict, float]:
    """八点当 LCFS：作目标曲线 + **isoflux 控制点**求一次自由边界平衡。

    返回 ``(equilibrium 文档, 形状事实, 墙钟秒)``。文档按 ``code/evolve`` 读的槽装：ψ(R,Z) 与网格 ·
    边界轮廓 · 磁轴 · ψ_axis / ψ_bnd · 限制器 · **q 与 F** · ``fylite:psi_convention``。

    ★``q`` / ``f`` **由内核给**：`code/discharge` 拿到 ``b0`` 之后按磁面几何算 q
    （F 取真空值 R₀B₀），随记录写在 ``profiles_1d/q`` 与 ``f`` 上。这两条不能拿工况自带的
    那份顶替——新位形下它并不自洽（同一时刻实测 q₀ 2.15 对 11.37）。

    ★★``delivered``（:func:`steady_profile` 给的 ``psi_norm`` / ``dpressure_dpsi`` /
    ``f_df_dpsi``）**把电流剖面换成演化出来的那一份**。不给它时求解器用自带的解析 j_φ 族，
    那一族与演化的剖面无关：解出来的 ψ 跨度与状态里那条 ψ 对不上（实测 70.11 对 65.15 Wb，
    差 7 %），度规与磁通因此在说两个等离子体。给了它，两者是同一份 p′ / FF′ 的两次求解。
    """
    import time as _time
    pts = [[float(r), float(z)] for r, z in points]
    ratings = [float(c["fylite:i_max_aturn"]) for c in device["pf_active"]["coil"]
               if not any((f or {}).get("name") == "b_field_fb" for f in (c.get("function") or []))]
    st = dict(DISCHARGE_SETTINGS, ip=float(ip))
    #: ★★真空环向场：内核要它才说得出 q（F = R₀·B₀）。装置卡给的是 **R·B_φ**（T·m，IMAS 的
    #: `b_field_phi_vacuum_r`，老名 `b_field_tor_vacuum_r`），除以卡里的 R₀ 得 B₀。
    tf = device.get("tf") or {}
    rb = tf.get("b_field_phi_vacuum_r", tf.get("b_field_tor_vacuum_r"))
    rb = rb.get("data") if isinstance(rb, dict) else rb
    if isinstance(rb, list) and rb:
        rb = rb[0]
    r0_dev = tf.get("r0")
    r0_dev = (r0_dev.get("data") if isinstance(r0_dev, dict) else r0_dev)
    if isinstance(r0_dev, list) and r0_dev:
        r0_dev = r0_dev[0]
    try:
        if rb is not None and r0_dev:
            st.setdefault("b0", abs(float(rb)) / abs(float(r0_dev)))
    except (TypeError, ValueError):
        pass
    st.update(settings or {})
    inp = {"device": device, "discharge": {
        "fylite:i_max_aturn": ratings,
        "fylite:target_r": [p[0] for p in pts], "fylite:target_z": [p[1] for p in pts],
        #: 同一组点再作 isoflux 控制行：「边界过这些点」
        "fylite:control_r": [p[0] for p in pts], "fylite:control_z": [p[1] for p in pts],
        "fylite:control_w": [1.0] * len(pts)}}
    if pf_current:
        #: 给了 PF 线圈电流就作**通道起始安匝**（求解器自己再调到位形上）
        inp["discharge"]["fylite:channel_aturns"] = [float(x) for x in pf_current]
    if delivered:
        #: ★演化出来的 p′ / FF′ 作**投送剖面**：给了这三行，求解器的解析 j_φ 族
        #: （β₀ / emp / enp）整族失效，电流剖面就是这一份。三行必须同长、一起给。
        inp["equilibrium"] = {"time_slice": {"profiles_1d": {
            "psi_norm": [float(x) for x in delivered["psi_norm"]],
            "dpressure_dpsi": [float(x) for x in delivered["dpressure_dpsi"]],
            "f_df_dpsi": [float(x) for x in delivered["f_df_dpsi"]]}}}
    c0 = _time.time()
    rec = kernel().complete("code/discharge", {"settings": st, "inputs": inp})
    wall = _time.time() - c0
    E = rec["fields"]["equilibrium"]
    F = E["time_slice"]
    val = lambda node: node["data"][0] if isinstance(node, dict) and "data" in node else node  # noqa: E731
    gq = F["global_quantities"]
    eq = {"time_slice": {
        "profiles_2d": {"grid": {"dim1": F["profiles_2d"]["grid"]["dim1"]["data"],
                                 "dim2": F["profiles_2d"]["grid"]["dim2"]["data"]},
                        "psi": F["profiles_2d"]["psi"]["data"]},
        "boundary": {"outline": {"r": F["boundary"]["outline"]["r"]["data"],
                                 "z": F["boundary"]["outline"]["z"]["data"]}},
        "global_quantities": {"psi_axis": val(gq["psi_axis"]), "psi_boundary": val(gq["psi_boundary"]),
                              "ip": val(gq["ip"]) if "ip" in gq else float(ip),
                              "magnetic_axis": {"r": val(gq["magnetic_axis"]["r"]),
                                                "z": val(gq["magnetic_axis"]["z"])}}},
        "fylite:limiter": {"r": E["fylite:limiter"]["r"]["data"], "z": E["fylite:limiter"]["z"]["data"]}}
    #: ★内核给了 q / F 就带上（同一张位形的 q，来路 kernel）；没给则调用方照旧补工况那份
    p1 = F.get("profiles_1d") or {}
    if p1.get("q") and p1.get("f"):
        eq["time_slice"]["profiles_1d"] = {
            "q": p1["q"]["data"] if isinstance(p1["q"], dict) else p1["q"],
            "f": p1["f"]["data"] if isinstance(p1["f"], dict) else p1["f"],
        }
        for key in ("psi_norm", "fylite:q_psi_norm"):
            if p1.get(key):
                node = p1[key]
                eq["time_slice"]["profiles_1d"][key] = node["data"] if isinstance(node, dict) else node
    facts = {k: v["value"] for k, v in rec["facts"].items()}
    #: ★★**通量规由出图的那一侧声明，这里照抄它报的 COCOS 号**。读文档那一侧「不声明 =
    #: 每弧度」（g-file / Python 的规），而求解器出的 ψ 是整匝 Wb —— 不声明就等于把整匝的
    #: 跨度当每弧度用：梯子的 Φ = 2π·Δψ·∫q dψ_N 大 2π，ρ_tor = √(Φ/(πB₀)) 大 √(2π)，
    #: 而输运的 q ∝ ρ² —— **q 整条大 2π**。实测（40.5 s 一步）：不声明 ρ_tor,边 6.781 m
    #: （a = 2.163 m 的机器上不可能）、q₀ 8.456；声明后 2.705 m、q₀ 1.342，对上求解器
    #: 自己那条 q（q₀ 1.280）。★不写死名字：号由记录说，宿主只是把它转给下一道门。
    if "cocos" not in facts:
        raise RuntimeError(
            "libfylite.so 的 code/discharge 没有报 cocos —— 这份库太旧（需要 ABI ≥ 155）。"
            "没有它就只能猜 ψ 的通量规，而猜错 2π 不会报错，只会让 q 整条偏。")
    eq["fylite:psi_convention"] = float(facts["cocos"])
    #: 解出的线圈电流（整匝安匝）与线圈名——输出名表的 PF 部分
    facts["_aturns"] = [float(x) for x in (rec["fields"].get("aturns") or {}).get("data", [])]
    facts["_coil_names"] = [c.get("name", f"coil{i}") for i, c in enumerate(
        [c for c in device["pf_active"]["coil"]
         if not any((f or {}).get("name") == "b_field_fb" for f in (c.get("function") or []))])]
    return eq, facts, wall


def steady_profile(state: dict) -> dict | None:
    """由**演化到此刻的状态**反算 p′ / FF′（``code/steady_equilibrium``）。

    返回 ``{"psi_norm", "dpressure_dpsi", "f_df_dpsi", "facts"}``，三条剖面同长，落在
    梯子自己的 ψ_N 标签上；喂给 :func:`solve_equilibrium` 的 ``delivered``。
    起步那一步还没有记录（梯子行不在），返回 ``None``——那一步照旧走解析 j_φ 族。

    ★★★**缺省不用它**（``--deliver-profile`` 才开），因为量出来的结果更差——这一段是
    那次尝试的账，留着是为了下一个人不必重做一遍：

    * 病象（两边确实不是一套）：平顶段自由边界解给 Δψ = −101.8 Wb、q₀ = 0.970，而演化出来的
      ψ 跨度 68.3 Wb、q₀ = 1.5–2.5——**差 48 %**，两边描述的电流剖面峰度不同（li 不同）。
    * 投送之后**更远**：Δψ 差 48 % → **54 %**，求解器的 q₀ 0.970 → **0.767**。
    * 根子不在管线上：这道门把演化态**自己的** ψ 拿去盒内重解，得到的 q₀ 是 **0.895**，
      而同一条 ψ 在一维梯子上按 q = 2πB₀ρ/(dψ/dρ) 读出来是 1.3–2.5。**同一条 ψ，两个 q，
      差一倍**——因为梯子的 ρ(ψ_N) 来自上一张位形，而 ψ 是这一步marched 出来的。
      投送只是把这个不一致换个地方冒出来。
    * 要真合成一套，得在**每个时间片**上把 `code/steady_current` ↔ `code/steady_equilibrium`
      这一对迭到不动点（内核对**定常**态是这么做的，约十轮收敛），那是耦合求解器的改法，
      不是接线的改法。
    * 另有一处实测：盒内 Picard 在这台机器上停在 **5e-4 的残差地板**（换松弛 0.3/0.5/0.8、
      预算 600/3000、容差 1e-9/1e-7/1e-6 六种组合，残差都落在 4.6–5.3e-4，落点一样），
      所以这里按残差判而不是按门的 `converged` 旗（那面旗比的是 1e-9）。

    ★成本实测：一次约 0.3 s，而一次自由边界解 7–13 s——只在位形重解那一步调用，可忽略。
    """
    plan, rec = state.get("plan") or {}, state.get("record") or {}
    eq0 = (plan.get("inputs") or {}).get("equilibrium")
    lad = _dig(rec, ("fields", "equilibrium", "time_slice", "profiles_1d")) or {}
    cp = _dig(plan, ("inputs", "core_profiles", "profiles_1d"))
    #: 梯子的四行是这道门的入口条件（`rho_tor · dvolume_drho_tor · gm2 · psi_norm`）
    need = ("rho_tor", "dvolume_drho_tor", "gm2", "psi_norm")
    if not eq0 or not cp or any(k not in lad for k in need):
        return None
    eq = json.loads(json.dumps(eq0))
    #: ★文档的一维栏**整栏换成梯子那一份**（而不是挑几行盖上去）：q / F / ψ_N 与面行
    #: 必须与 `rho_tor` 等长同格，留着求解器那份 51 点的 q 表会让同一栏里两个网格并存。
    eq.setdefault("time_slice", {})["profiles_1d"] = {
        k: [float(x) for x in v["data"]] for k, v in lad.items() if isinstance(v, dict) and "data" in v}
    #: ★★**不强加 I_p**（2026-09-17 实测）：给了 `ip_a`，这道门就得把 FF′ 抬到那个电流上，
    #: 而演化出来的磁通此刻**并没有携带**它——爬升段实测状态的磁通只带 9.59 MA，指令 15 MA，
    #: 于是盒内 Picard 一路长到盒边（`-34`）。不给，门就守着状态自己的磁通所携带的电流，
    #: 反算是自洽的；而投送给自由边界解的只是**形状**（那一侧按 I_p 归一），所以不损失什么。
    st = dict(plan.get("settings") or {}, source="inversion")
    #: ★★**反算不成就不投送**，而不是让整炮停在这里：盒内重解是个 Picard，遇到某些状态
    #: 会长到盒边（`-34`）。那一步退回求解器自带的解析 j_φ 族——读数会差，但差在看得见的
    #: 地方（`out["extra"]["delivered"]` 记下这一步投没投送），而不是把一炮打断。
    try:
        r = kernel().complete("code/steady_equilibrium",
                              {"settings": st, "inputs": {"equilibrium": eq,
                                                          "core_profiles": {"profiles_1d": cp}}})
    except Refused as e:
        return {"refused": f"{e}"}
    out = _dig(r, ("fields", "equilibrium", "time_slice", "profiles_1d")) or {}
    row = lambda k: [float(x) for x in (out.get(k) or {}).get("data", [])]  # noqa: E731
    x, pp, ff = row("psi_norm"), row("dpressure_dpsi"), row("f_df_dpsi")
    if not (len(x) == len(pp) == len(ff) >= 2):
        return None
    facts = {k: v["value"] for k, v in r["facts"].items()}
    #: ★★**按残差判，不按那面收敛旗**。门的 `converged` 比的是 `box_tol`（缺省 1e-9），
    #: 而这台机器上的盒内 Picard 落在 **5e-4 的残差地板**上就不动了——实测换松弛
    #: （0.3 / 0.5 / 0.8）、换预算（600 / 3000）、换容差（1e-9 / 1e-7 / 1e-6）六种组合，
    #: 残差都停在 4.6–5.3e-4，落点也一样（ip 9.59 MA · q0 0.895）：那是**不动点的地板**，
    #: 不是没跑够。旗子照报，投不投送按残差的量级判。
    if not (facts.get("residual", math.inf) < _INVERSION_RESIDUAL):
        return {"refused": f"盒内重解的残差 {facts.get('residual', float('nan')):.2e} 超过 {_INVERSION_RESIDUAL:.0e}"}
    return {"psi_norm": x, "dpressure_dpsi": pp, "f_df_dpsi": ff, "facts": facts}


def _points_moved(a, b, tol: float) -> bool:
    if not a or len(a) != len(b):
        return True
    return any(math.hypot(p[0] - q[0], p[1] - q[1]) > tol for p, q in zip(a, b))


def step(state: dict, control: dict, *, dt_max: float | None = 0.025, max_calls: int = 400,
         boundary_mode: str = "isoflux", device: dict | None = None, boundary_tol: float = 0.02,
         fuel_gain: float = 1.0, fuel_max_factor: float = 4.0,
         edge_ne_ref: tuple[float, float] | None = None, psi_stride: int = 1,
         deliver_profile: bool = False) -> tuple[dict, dict]:
    """一步：当前状态 + 下一时刻的控制 → 下一时刻的状态与输出名表 dict。

    这是这个工具的**最小完整调用**——:func:`run_discharge` 就是把它放进一个循环。
    一次调用 = 一个内核工况（``code/evolve``），从 ``state`` 记的时刻推到 ``control["time"]``。

    参数
    ----
    ``state``
        :func:`init_state` 给的起步状态，或上一次 :func:`step` 返回的那一个（带着内核记录、
        工况与控制器状态）。**不要复用旧的 state 去接新的时刻**：它就是"当前等离子体状态"。
    ``control``
        输入名表，dict：``time`` [s]（必给，且必须大于 ``state`` 的时刻）· ``Ip`` [A] ·
        ``ECRH`` / ``ICRF`` [W]（本工况合成一路射频）· ``NBI`` / ``LHW`` [W]（必须为 0，非零即拒）·
        ``ne_bar`` [m^-3]（线平均密度指令，0 或不给 = 不控密度）· ``n_roh``（剖面点数，**只在起步
        那一步**作数）· ``boundary``：控制点 ``[[R, Z], …]`` [m]（缺省八点）· ``pf_current``
        [A·turns]（可选，isoflux 档作通道起始安匝）。
    ``dt_max``
        交给内核的物理步长上限 [s]；内核自己还受交换上限约束，步数由它定。
    ``boundary_mode``
        * ``"isoflux"``（**缺省**）—— 八点**当 LCFS 的 isoflux 控制点**：点动过 ``boundary_tol`` [m]
          或 I_p 变过 0.05 MA 就调 ``code/discharge`` 重解一次自由边界（约 8–14 s），把 ψ(R,Z) ·
          边界 · 磁轴 · 限制器 · q / F 换进推进的位形，``dfsdev`` 取求解器自己的边界间隙 rms。
          需要 ``device``（装置卡 dict）。**整条波形的演化只能走这一档**——位形随 I_p 与形状指令变。
        * ``"check"`` —— 位形固定：用工况自带的度规，八点只作检查，``dfsdev`` 取「指令点到工况所用
          LCFS 的距离 rms」。**只适用于位形不变的那一段（平顶）**；指令位形动了还用它，等于拿平顶的
          度规算爬升段。不给 ``boundary`` 就没有可比的曲线，``dfsdev`` 记 NaN，不编数。
    ``edge_ne_ref`` / ``fuel_gain`` / ``fuel_max_factor``
        密度这一路的标定与限幅（见 :data:`INPUT_NAMELIST` 处那段说明）。

    返回
    ----
    ``(state_next, out)``——``out`` 是输出名表 dict（:data:`OUTPUTS`）：0-D 每格一个数，
    剖面每格一条 list，外加 ``equilibrium``（二维 ψ 等）与 ``extra``（诊断）。

    例::

        import cfedr_core_model as M

        state = M.load_state("state_init.json")
        ctl = {"time": 40.5, "Ip": 10.125e6, "ECRH": 20e6, "ICRF": 0.0,
               "NBI": 0.0, "LHW": 0.0, "ne_bar": 3.8e19}
        state, out = M.step(state, ctl)
        out["P_fusion"], out["betan"], out["q"][0]      # 0-D 两个 + 轴上 q

    自由边界那一档（八点当 isoflux 控制点，要装置卡）::

        device = json.load(open("device_cfedr.json"))
        pts = [[10.32, 0.0], [8.73, 3.29], [6.48, 4.66], [5.58, 3.29],
               [5.42, 0.0], [5.56, -3.29], [6.44, -4.66], [8.70, -3.29]]
        state, out = M.step(state, dict(ctl, time=41.0, boundary=pts),
                            boundary_mode="isoflux", device=device, boundary_tol=0.05)
        out["dfsdev"], out["pf_current"]                # 边界间隙 rms 与解出来的线圈安匝

    抛错：控制不合法（时间倒流 · NBI/LHW 非零 · 边界不闭合）抛 ``ValueError``；内核拒绝这一步
    抛 :class:`Refused`；库 / 门出错抛 :class:`KernelError`。整炮循环里接住这三个就是"停在这一步"。
    """
    _check_control(control, float(state["t"]))
    #: ★`n_roh`（剖面点数）是**请求**，只在起步那一步作数：状态一旦在某张径向网格上推进，
    #: 中途换网格要把所有剖面重映一遍——那是另一件事，这里按名拒绝，不静默照旧。
    want_n = int(float(control.get("n_roh", 0) or 0))
    if want_n > 0:
        have = len(((state.get("record") or {}).get("fields", {}).get("core_profiles", {})
                    .get("profiles_1d", {}).get("grid", {}).get("rho_tor", {}) or {}).get("data", []) or [])
        if state.get("record") is None:
            state = _regrid_start(state, want_n)
        elif have and have != want_n:
            raise ValueError(f"n_roh 中途从 {have} 改成 {want_n}：径向网格在推进中不能换（要换请从起步给）")
    plan, rec = state["plan"], state["record"]
    shape_facts = None
    #: ★★★**固定位形档只适用于位形不变的一段**（平顶）。指令位形动了还用它，等于拿平顶的度规
    #: 去算爬升段——输运答案会错，而输出里的等高线一动不动，看不出来。所以这里把"指令位形与
    #: 工况所用 LCFS 的距离"拿出来比一次：超过阈值就说一句，指向 `--isoflux`（每步重解）。
    if boundary_mode == "check" and (control.get("boundary") or []):
        dev = _boundary_deviation(control["boundary"], _geometry(plan))
        if math.isfinite(dev) and dev > _CHECK_SHAPE_TOL and not state.get("_shape_warned"):
            print(f"★指令位形与工况所用 LCFS 差 {dev:.3f} m（阈值 {_CHECK_SHAPE_TOL} m）："
                  f"固定位形档只适用于位形不变的那一段（平顶）；整条波形要演化位形，用 --isoflux",
                  file=sys.stderr)
            state = dict(state, _shape_warned=True)
    #: 指令里带了二维 ψ（上一次运行的输出、或别的码给的）：直接当推进的位形（q / f 仍取工况那份）
    if control.get("psi") and control.get("psi_r") and control.get("psi_z"):
        old_eq = (plan.get("inputs") or {}).get("equilibrium") or {}
        rows = control["psi"]
        eqd = {"time_slice": {
            "profiles_2d": {"grid": {"dim1": list(control["psi_r"]), "dim2": list(control["psi_z"])},
                            "psi": [float(x) for row in rows for x in row]},
            "boundary": {"outline": {"r": list(control.get("bnd_r") or []), "z": list(control.get("bnd_z") or [])}},
            "global_quantities": {"psi_axis": float(control.get("psi_axis", math.nan)),
                                  "psi_boundary": float(control.get("psi_bnd", math.nan)),
                                  "ip": float(control["Ip"]),
                                  "magnetic_axis": {"r": float(control.get("axis_r", math.nan)),
                                                    "z": float(control.get("axis_z", math.nan))}}}}
        p1 = ((old_eq.get("time_slice") or {}).get("profiles_1d"))
        if p1:
            eqd["time_slice"]["profiles_1d"] = p1
        for k in ("fylite:limiter", "vacuum_toroidal_field"):
            if old_eq.get(k):
                eqd[k] = old_eq[k]
        #: ★通量规跟着**这张图**走，不跟着被它换掉的那份文档走：调用方说了就照说的，
        #: 没说就按每弧度读（读文档那一侧的缺省）。本工具输出的时序里这一格是
        #: `psi_convention`，整匝 —— 拿自己的输出回放时把它一并传进来。
        if control.get("psi_convention"):
            eqd["fylite:psi_convention"] = str(control["psi_convention"])
        plan = {"settings": plan["settings"], "inputs": dict(plan.get("inputs") or {}, equilibrium=eqd)}
        state = dict(state, plan=plan)
    #: ★★名表里的密度这一路（`ne_bar`，线平均密度指令 [m^-3]）：非零就开两个宿主侧控制——
    #: 弹丸加料率按「窗末平均 n_e / 目标」比例调（限幅 `fuel_max_factor` × 工况加料率），
    #: 边界密度按指令线平均密度同比缩放（密度通道的边界是状态末点的 Dirichlet）。
    #: 给 0 / 不给则两者都不动，密度走工况自带的恒定加料率。
    #: 控制器状态（`fuel_state`）跟着 state 走，所以断点续跑接得上。
    ne_cmd = control.get("ne_bar")
    fuel_state = dict(state.get("fuel") or {})
    edge_ne = None
    if boundary_mode == "isoflux":
        pts = control.get("boundary") or []
        if not pts:
            raise ValueError("boundary_mode = isoflux 却没有给 boundary 点")
        if device is None:
            raise ValueError("boundary_mode = isoflux 需要 device（装置卡 dict）")
        eq_state = state.get("eq") or {}
        if _points_moved(eq_state.get("points"), pts, boundary_tol) or abs(float(eq_state.get("ip", 0.0)) - float(control["Ip"])) > 0.05e6:
            #: ★位形重解之前，可以把**演化到此刻的** p′ / FF′ 反算出来投送给求解器
            #: （`--deliver-profile`）。**缺省不投送**，理由是量出来的：见 `steady_profile`。
            delivered = steady_profile(state) if deliver_profile else None
            if delivered and delivered.get("refused"):
                if not state.get("_inv_warned"):
                    print(f"★演化态反算 p′/FF′ 被拒（{delivered['refused']}）：这一步退回解析 j_φ 族",
                          file=sys.stderr)
                    state = dict(state, _inv_warned=True)
                delivered = None
            eq, facts, wall = solve_equilibrium(pts, float(control["Ip"]), device,
                                                pf_current=control.get("pf_current"),
                                                delivered=delivered)
            facts["_delivered"] = 1.0 if delivered else 0.0
            if delivered:
                facts["_delivered_q0"] = float(delivered["facts"].get("q0", math.nan))
            #: ★**q / f 取求解器给的那份**（内核按磁面几何算，F 取真空值）：梯子的环向通量
            #: Φ = 2π·Δψ·∫q dψ_N 正是拿这张 q 表积出来的，换了位形还用工况那份就不自洽。
            #: 求解器没给时才退回工况自带的那份，那是个近似，读数上会看出来（轴上 q 跳出常识带）。
            #: ★另一半在 `solve_equilibrium` 里：Δψ 的**通量规**要随文档声明，否则 Φ 大 2π。
            old_eq = (plan.get("inputs") or {}).get("equilibrium") or {}
            p1 = ((old_eq.get("time_slice") or {}).get("profiles_1d"))
            solved_p1 = (eq.get("time_slice") or {}).get("profiles_1d") or {}
            if not solved_p1.get("q") and p1:
                eq["time_slice"]["profiles_1d"] = p1
            vac = old_eq.get("vacuum_toroidal_field")
            if vac:
                eq["vacuum_toroidal_field"] = vac
            plan = {"settings": plan["settings"], "inputs": dict(plan.get("inputs") or {}, equilibrium=eq)}
            state = dict(state, plan=plan, eq={"points": pts, "ip": float(control["Ip"]), "facts": facts, "wall_s": wall})
            shape_facts = facts
        else:
            shape_facts = eq_state.get("facts")
        plan = state["plan"]
    geo = _geometry(plan)
    #: ★★固定位形档 + 给了装置卡：**顺带把线圈电流解出来**。这一档不换位形——目标曲线就是
    #: 工况自带的那条 LCFS（指令给了八点就用八点），解出来的只取安匝，ψ / 度规一概不动。
    #: 于是「这一炮要多大的 PF 电流」有个答案，而输运的答案与不给装置卡时**逐位相同**。
    #: 重解的判据是 I_p：变过 5 % 才重解（爬升段约八次，平顶零次）；线圈随 I_p 走，
    #: 而 5 % 的台阶对「要多大电流」这个量级问题足够。
    pf_facts = None
    if boundary_mode == "check" and device is not None:
        cached = state.get("pf") or {}
        ip_now = float(control["Ip"])
        if not cached or abs(ip_now - float(cached.get("ip", 0.0))) > 0.05 * max(abs(ip_now), 1.0):
            pts = control.get("boundary") or _sample_curve(geo["lcfs_r"], geo["lcfs_z"], BOUNDARY_POINTS)
            if pts:
                _eq, pf_facts, wall = solve_equilibrium(pts, ip_now, device,
                                                        pf_current=control.get("pf_current"))
                state = dict(state, pf={"ip": ip_now, "facts": pf_facts, "wall_s": wall})
        else:
            pf_facts = cached.get("facts")
    t_end = float(control["time"])
    #: 指令 → 工况设置：I_p [kA]、射频总功率进那张沉积表
    plan = {"settings": dict(plan["settings"]), "inputs": plan.get("inputs") or {}}
    plan["settings"]["ip"] = float(control["Ip"]) / 1e3
    plan["settings"]["source_power_0"] = float(control.get("ECRH", 0.0)) + float(control.get("ICRF", 0.0))
    if ne_cmd:
        fuel0 = float(state["plan"]["settings"].get("fuel_rate", 0.0))
        edge0 = float(state["plan"]["settings"].get("edgene", 0.0)) * 1e19
        fuel = float(fuel_state.get("fuel", fuel0))
        #: 边界密度的参考对：显式给 (edge [m^-3], n̄_e [m^-3]) 最准（标定工况的那对）；否则用首步自己的
        ref = edge_ne_ref or ((fuel_state.get("edge_ref"), fuel_state.get("ne_bar_ref"))
                              if fuel_state.get("ne_bar_ref") else None)
        if ref and ref[0] and ref[1]:
            edge_ne = max(edge0, float(ref[0]) * float(ne_cmd) / float(ref[1]))
        plan["settings"]["fuel_rate"] = fuel
        plan["settings"]["gas_rate"] = 0.0
    calls = 0
    k = kernel()
    while True:
        t_now = float(state["t"]) if rec is None else float(rec["facts"]["t_end"]["value"])
        left = t_end - t_now
        if left <= 1e-9 * max(1.0, abs(t_end)):
            break
        if calls >= max_calls:
            raise KernelError(f"{max_calls} 次内核调用仍未走到 {t_end} s（现在 {t_now} s）")
        dt = min(left, float((rec or {}).get("facts", {}).get("dt_next", {}).get("value", dt_max or left)) if rec else left)
        rec = k.complete("code/evolve", _resume_call(plan, rec, t_end, dt, dt_max, edge_ne))
        calls += 1
    out = _outputs(rec, control, geo)
    out["extra"]["kernel_calls"] = calls
    if ne_cmd:
        ne_now = out["ne_bar"]
        if not fuel_state.get("ne_bar_ref"):
            fuel_state.update({"ne_ref": ne_now, "ne_bar_ref": float(ne_cmd),
                               "edge_ref": float(out["Ne"][-1]), "fuel": float(plan["settings"].get("fuel_rate", 0.0))})
        target = float(fuel_state["ne_ref"]) * float(ne_cmd) / float(fuel_state["ne_bar_ref"])
        cap = fuel_max_factor * float(state["plan"]["settings"].get("fuel_rate", 0.0))
        fuel_state["fuel"] = min(max(float(fuel_state.get("fuel", 0.0)) * (1.0 + fuel_gain * (target / ne_now - 1.0)), 0.0), cap)
        #: ★`fuel_rate_next` 是**下一步**的执行器值（本步那个在名表的 `fuel_rate` 里）。
        #: 两者同名过一次，读者会把反馈的输出当成本步的输入——所以这里按时刻分名字。
        out["extra"].update({"fuel_rate_next": fuel_state["fuel"], "ne_target": target,
                             "edge_ne": edge_ne})
    if pf_facts and not shape_facts:
        #: 固定位形档解出来的那一组：只写线圈这一路，dfsdev 与位形仍是这一档自己的
        out["pf_current"] = list(pf_facts.get("_aturns") or [])
        out["coil_names"] = list(pf_facts.get("_coil_names") or [])
        out["n_coil"] = len(out["pf_current"])
        out["extra"].update({"pf_solved": 1.0, "coil_limit_ratio": pf_facts.get("coil_limit_ratio"),
                             "n_at_coil_limit": pf_facts.get("n_at_coil_limit"),
                             "eq_solve_s": (state.get("pf") or {}).get("wall_s")})
    if shape_facts:
        #: isoflux 档：dfsdev 取求解器自己的边界间隙（指令边界与实现边界之差，rms）
        out["dfsdev"] = float(shape_facts.get("dfsdev", shape_facts.get("boundary_gap_rms", math.nan)))
        out["pf_current"] = list(shape_facts.get("_aturns") or [])
        out["coil_names"] = list(shape_facts.get("_coil_names") or [])
        out["n_coil"] = len(out["pf_current"])
        out["extra"].update({"shape_error": shape_facts.get("shape_error"),
                             "boundary_gap_max": shape_facts.get("boundary_gap_max"),
                             "coil_limit_ratio": shape_facts.get("coil_limit_ratio"),
                             "n_at_coil_limit": shape_facts.get("n_at_coil_limit"),
                             "diverted": shape_facts.get("bnd_kind"),
                             "eq_solve_s": (state.get("eq") or {}).get("wall_s")})
    #: 这一步用的位形（ψ 图 · O 点 · X 点 · LCFS）——进输出文件，供可视化
    #: ★二维 ψ 的端值对齐到**这一步演化出来的**一维 ψ（固定位形档里那份平衡文档是冻结的，
    #: 它的端值停在起步那一刻）；isoflux 档解出来的 ψ 本来就是当步的，端值一致，仿射是恒等变换。
    psi_1d = (rec.get("fields", {}).get("psi") or {}).get("data") or []
    ends = (float(psi_1d[0]), float(psi_1d[-1])) if len(psi_1d) >= 2 else None
    out["equilibrium"] = equilibrium_snapshot(plan, shape_facts, stride=psi_stride, psi_ends=ends)
    new_state = {"t": t_end, "plan": state["plan"], "record": rec}
    if fuel_state:
        new_state["fuel"] = fuel_state
    if state.get("eq"):
        new_state["eq"] = state["eq"]
    if state.get("pf"):
        new_state["pf"] = state["pf"]
    return new_state, out


# --------------------------------------------------------------------------- #
# 整炮：上升 · 平台 · 下降
# --------------------------------------------------------------------------- #
def miller_boundary(node: dict, n: int = BOUNDARY_POINTS) -> list:
    """回放节点的 Miller 形状 → n 点边界（名表要八点）。"""
    s = node.get("lcfs") or {}
    if not s:
        return []
    r0, z0, a = float(s.get("r0", 0.0)), float(s.get("z0", 0.0)), float(s.get("a", 0.0))
    kap, du, dl = float(s.get("kappa", 1.0)), float(s.get("delta_upper", 0.0)), float(s.get("delta_lower", 0.0))
    pts = []
    for i in range(n):
        th = 2.0 * math.pi * i / n
        d = du if math.sin(th) >= 0 else dl
        pts.append([r0 + a * math.cos(th + math.asin(max(-0.99, min(0.99, d))) * math.sin(th)),
                    z0 + kap * a * math.sin(th)])
    return pts


def nodes_from_replay(replay_nodes: list) -> list:
    """PCS 回放节点 → **名表节点**（本工具内部只认这一种节点）。

    一个节点 = 一个时刻上的控制名表（`time` · `Ip` · 四路加热 · `ne_bar` · `boundary`），
    外加一格 `phase`（回放自己的相位名，不进名表，页面拿它做相位芯片）。
    """
    out = []
    for n in replay_nodes:
        out.append({"time": float(n["t"]), "Ip": float(n["ip"]),
                    "ECRH": sum(float(v) for v in (n.get("p_ec") or {}).values()),
                    "ICRF": float(n.get("p_ic") or 0.0), "NBI": float(n.get("p_nbi") or 0.0),
                    "LHW": float(n.get("p_lh") or 0.0), "ne_bar": float(n.get("ne_bar", 0.0)),
                    "boundary": miller_boundary(n), "phase": n.get("phase")})
    return out


#: ★★★**这个工具只认四类 JSON**，按**内容**认，不看文件名（名字可以随手改，内容不会）：
#:
#:   | 类 | 里面是什么 | 命令行那一格 | 判据 |
#:   | :--- | :--- | :--- | :--- |
#:   | `device`   | 装置描述：线圈几何与额定安匝 · 第一壁 · TF | `--device`   | 有 `pf_active` / `tf` |
#:   | `state`    | 起步态 + 物理设置 + 上一次内核记录（初始 / 中间 / 结束是同一类） | `--state`   | 有 `t` 与 `plan` |
#:   | `waveform` | 控制波形：名表节点表 + `meta.interp` | `--waveform` | 有 `time` 与 `Ip` |
#:   | `series`   | 完整时序：整炮每一步的输出名表 · 剖面 · 位形 | `--series`（出） | 有 `time` 与 `Te` |
#:
#: ★另外两种是**上游的形状**，读进来时当场转成上面的类并在 stderr 说一句：`code/evolve`
#: **工况**（`settings` + `inputs`）转成 state——它就是还没推进过的状态；**PCS 回放**
#: （顶层 `nodes` 带 `ip` / `p_ec`）转成 waveform。转换只发生在读的那一刻，写出去的永远是这四类。
def _shape_of(doc) -> str:
    if not isinstance(doc, dict):
        return "unknown"
    if "t" in doc and "plan" in doc:
        return "state"
    if "pf_active" in doc or "tf" in doc:
        return "device"
    if isinstance(doc.get("time"), list):
        return "series" if ("Te" in doc or "P_fusion" in doc) else "waveform"
    if "settings" in doc and "inputs" in doc:
        return "plan"                      #: 上游形状：工况 → state
    if isinstance(doc.get("nodes"), list):
        #: 上游形状：PCS 回放（节点带 `ip` / `p_ec`）→ waveform。★按**节点里的键**认，不只看
        #: 有没有 `nodes`：页面那份预设也是顶层一个 `nodes`，但里面是名表节点。
        n0 = doc["nodes"][0] if doc["nodes"] else {}
        if "ip" in n0 or "p_ec" in n0:
            return "replay"
        if "Ip" in n0 or "time" in n0:
            return "waveform-nodes"        #: 名表节点的**列表**形（页面预设那一种）
    return "unknown"


#: 四类各自该出现在哪一格——认错了要说得出「你给的是什么、该给什么」
_KIND_CN = {"device": "装置描述", "state": "状态", "waveform": "控制波形", "series": "完整时序",
            "plan": "code/evolve 工况", "replay": "PCS 回放", "waveform-nodes": "名表节点列表",
            "unknown": "认不出的文件"}


def _load_kind(path, want: str, convert: dict) -> tuple:
    """读一份文件，认出类别；是 `want` 就收，是 `convert` 里的上游形状就转，否则按名拒绝。"""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    kind = _shape_of(doc)
    if kind == want:
        return doc, kind
    if kind in convert:
        print(f"[{path}] 是{_KIND_CN[kind]}：按{_KIND_CN[want]}读入（{convert[kind]}）", file=sys.stderr)
        return doc, kind
    raise ValueError(f"{path} 是{_KIND_CN[kind]}，这一格要的是{_KIND_CN[want]}")


def load_waveform(path) -> tuple:
    """`--waveform` 那一格：读一份**控制波形**（名表节点表），给出 `(节点表, 类别)`。

    上游的 **PCS 回放**也收，读进来当场转成节点表。
    """
    doc, kind = _load_kind(path, "waveform", {"replay": "节点逐条转成名表节点",
                                              "waveform-nodes": "节点列表按名表读入"})
    if kind == "waveform":
        return read_waveform(path), kind
    if kind == "replay":
        return nodes_from_replay(doc["nodes"]), kind
    #: 名表节点的列表形：键就是名表，`t` 与 `time` 都认
    return [dict(n, time=float(n.get("time", n.get("t", 0.0)))) for n in doc["nodes"]], kind


def load_device(path) -> dict:
    """`--device` 那一格：读一份**装置描述**。"""
    return _load_kind(path, "device", {})[0]


#: 名表节点里按数插值的那几项（`phase` 是名字，`boundary` 逐点插，另走一条）
_NODE_CHANNELS = ("Ip", "ECRH", "ICRF", "NBI", "LHW", "ne_bar", "n_roh")


def controls_at(nodes: list, t: float) -> dict:
    """名表节点 + 时刻 → 该时刻的控制 dict。

    ★**每条通道都是折线**：节点之间一律线性插值，四路加热也不例外（零阶保持会把
    「60 s 10 MW → 65 s 82 MW」画成一级台阶，而波形工作台上画的、读者看到的都是折线；
    两处用同一条规则，一份输入才对得上一份输出）。边界点逐点线性插——点数相同时才插，
    不同就取左节点那一组（点数在一炮里本来就不该变）。
    """
    ts = [float(x["time"]) for x in nodes]
    k = max(0, min(len(nodes) - 1, next((i for i in range(len(ts) - 1, -1, -1) if ts[i] <= t + 1e-9), 0)))
    a, b = nodes[k], nodes[min(k + 1, len(nodes) - 1)]
    span = float(b["time"]) - float(a["time"])
    u = 0.0 if span <= 0 else min(max((t - float(a["time"])) / span, 0.0), 1.0)
    lin = lambda key: float(a.get(key, 0.0)) + (float(b.get(key, 0.0)) - float(a.get(key, 0.0))) * u  # noqa: E731
    ctl = {"time": t, **{key: lin(key) for key in _NODE_CHANNELS if key in a or key in b}}
    pa, pb = a.get("boundary") or [], b.get("boundary") or []
    if pa:
        ctl["boundary"] = ([[pa[i][0] + (pb[i][0] - pa[i][0]) * u, pa[i][1] + (pb[i][1] - pa[i][1]) * u]
                            for i in range(len(pa))] if len(pb) == len(pa) else [list(q) for q in pa])
    if a.get("pf_current"):
        ctl["pf_current"] = list(a["pf_current"])
    if a.get("phase") is not None:
        ctl["phase"] = a["phase"]
    return ctl


def run_discharge(plan, nodes: list, t0: float, t1: float, dt: float = 0.5, *, dt_max: float | None = 0.025,
                  dt_flat: float | None = None, flat_span=(150.0, 6150.0), series_path=None,
                  boundary_mode: str = "isoflux", device=None, boundary_tol: float = 0.02,
                  density: bool = True, edge_ne_ref: tuple[float, float] | None = None,
                  fuel_gain: float = 1.0, fuel_max_factor: float = 4.0,
                  psi_stride: int = 1, psi_dedup: bool = False, deliver_profile: bool = False,
                  state: dict | None = None, log=print) -> dict:
    """循环调用 :func:`step` 走完上升 · 平顶 · 下降；返回逐步的输出，并可直接写成输出文件。

    参数
    ----
    ``plan``
        工况（路径或 dict）——``code/evolve`` 的第一块。``state`` 给了就用 state 里的那份。
    ``nodes``
        **名表节点**表（`[{"time":…, "Ip":…, "ECRH":…, …}, …]`）：每个控制节拍按
        :func:`controls_at` 线性插出一份控制 dict。PCS 回放的原始节点先经
        :func:`nodes_from_replay` 转成这一形。
    ``t0`` / ``t1``
        起止时刻 [s]。断点续跑时 ``t0`` 由 ``state`` 说了算。
    ``dt`` / ``dt_flat`` / ``flat_span``
        ``dt`` 是**控制节拍**（名表里两次 ``time`` 之差），与内核物理步（``dt_max``）无关；
        ``dt_flat`` 给稳态平顶（``flat_span``）另一个节拍——6 000 s 平顶不必按 0.5 s 发指令。
        节拍还会切在每个回放节点上，使一次调用内的指令不跳变。
    ``series_path``
        给了就把整段时序写成输出文件（``.json``，即 :func:`write_output`），路径记在
        ``summary["output"]`` 里；不给就只返回，不落盘。演化完成的**状态**在返回值的
        ``state`` 里，由调用方决定存不存（命令行上是 ``--out``）。
    其余
        ``boundary_mode`` · ``device`` · ``boundary_tol`` · ``density`` · ``edge_ne_ref`` ·
        ``fuel_gain`` · ``fuel_max_factor`` · ``psi_stride`` 原样转给 :func:`step`；
        ``state`` 给了就是**自断点续跑**；``log`` 是进度打印（``None`` 之外任何可调用）。

    返回 ``{"times": [...], "outputs": [...], "controls": [...], "state": …, "summary": …}``；
    内核中途拒绝不抛出——记在 ``summary["stopped"]`` 里，已经走完的那些步照常返回。

    例（整炮 40 → 150 s，平顶用粗节拍，写一份扁平输出）::

        import json, cfedr_core_model as M

        nodes, _kind = M.load_waveform("waveform_d2025.json")
        r = M.run_discharge(None, nodes, t0=40.0, t1=150.0,
                            dt=0.5, dt_flat=50.0, edge_ne_ref=(5.474e19, 1.139e20))
        M.write_output("run.json", r["times"], r["outputs"])
        M.write_waveform("waveform.json", nodes)
        r["summary"]        # {"t0":…, "t1":…, "steps":…, "stopped": None 或 "… 停下：…"}

    断点续跑：上一次的 ``r["state"]`` 传进来就接着走::

        r2 = M.run_discharge(None, nodes, t0=0.0, t1=300.0, state=r["state"])
    """
    #: `state` 给了就是自断点续跑（带着上一次的内核记录与控制器状态），否则按工况新起一炮
    state = state if state is not None else init_state(plan, t0)
    t0 = float(state["t"]) if state.get("record") is not None else t0
    node_t = sorted(float(n["time"]) for n in nodes)
    times, outs, ctls, stopped = [], [], [], None
    t = t0
    while t < t1 - 1e-9:
        step_dt = dt_flat if (dt_flat and flat_span[0] <= t < flat_span[1]) else dt
        t_next = min(t + step_dt, t1)
        nxt = next((x for x in node_t if t + 1e-9 < x < t_next - 1e-9), None)
        t = nxt if nxt is not None else t_next
        ctl = controls_at(nodes, t)
        #: ★缺省**跟随名表**：回放带来的 `ne_bar` 就是这一路的指令。`density=False` 是留给
        #: 「只想看不控密度会怎样」的那种对照跑法，不是常规路径。
        if not density:
            ctl.pop("ne_bar", None)
        try:
            state, out = step(state, ctl, dt_max=dt_max, boundary_mode=boundary_mode, device=device,
                              boundary_tol=boundary_tol, edge_ne_ref=edge_ne_ref, psi_stride=psi_stride,
                              deliver_profile=deliver_profile,
                              fuel_gain=fuel_gain, fuel_max_factor=fuel_max_factor)
        except (Refused, KernelError, ValueError) as exc:
            stopped = f"{t:.3f} s 停下：{exc}"
            log(stopped)
            break
        times.append(t); outs.append(out); ctls.append(ctl)
        if len(outs) % 20 == 0:
            log(f"t {t:8.2f} s · P_fus {out['P_fusion'] / 1e6:7.1f} MW · W_mhd {out['wmhd'] / 1e6:6.1f} MJ · "
                f"β_N {out['betan']:.2f} · V_loop {out['vloop']:+.3f} V · {ctl.get('phase')}")
    summary = {"t0": t0, "t1": times[-1] if times else t0, "steps": len(times), "stopped": stopped}
    if series_path and times:
        summary["output"] = write_output(series_path, times, outs, psi_dedup=psi_dedup,
                                         meta={"plan": str(plan), "stopped": stopped or "",
                                               **device_meta(state["plan"])})
        log(f"输出：{summary['output']}")
    return {"times": times, "outputs": outs, "controls": ctls, "state": state, "summary": summary}


# --------------------------------------------------------------------------- #
# 输入 / 输出文件：扁平 dict（一层键 → 数组），只有 JSON 一种格式
# --------------------------------------------------------------------------- #
#: 输出文件的键：时间 + 名表标量（每步一值）+ 剖面（nt × n）+ PF 电流（nt × m）+ `extra.*`
#: 值是嵌套列表；非有限值在文件里写成 `null`（`JSON.parse` 不收 NaN），读回来还原成 NaN。


def _flat_output(times, outs: list, meta: dict | None = None, psi_dedup: bool = False) -> dict:
    flat: dict = {"time": [float(t) for t in times]}
    for k in OUT_KEYS("0d"):
        flat[k] = [float(o.get(k, math.nan)) for o in outs]
    #: 剖面：有哪条写哪条（整炮里某一条一直取不到就整列不写，页面据此隐藏）
    for k in OUT_KEYS("1d"):
        if any(o.get(k) for o in outs):
            flat[k] = [[float(x) for x in (o.get(k) or [])] for o in outs]
    for k in OUT_KEYS("coil"):
        flat[k] = [[float(x) for x in (o.get(k) or [])] for o in outs]
    #: ★★★二维 ψ **逐帧写**：每个时间片一帧，`psi_index[i] = i`。读的人不必先解索引，
    #: 单独切一片出来也自带位形（页面的「导出当前片 JSON」与 g-file 都直接拿得到）。
    #: ★`psi_dedup=True` 才把相同的帧合并存一次（固定位形档整炮只有一帧，文件小五倍左右）——
    #: 那是**省字节**的选项，不是缺省：缺省应当是"要什么有什么"。
    eqs = [o.get("equilibrium") or {} for o in outs]
    frames, index, seen = [], [], {}
    for e in eqs:
        if not e.get("psi"):
            index.append(-1)
            continue
        key = ((round(float(e.get("psi_axis", 0.0)), 9), round(float(e.get("psi_bnd", 0.0)), 9),
                round(float(e.get("axis_r", 0.0)), 9), len(e["psi"]), len(e["psi"][0]),
                round(sum(e["psi"][0]), 6)) if psi_dedup else None)
        if key is not None and key in seen:
            index.append(seen[key])
            continue
        if key is not None:
            seen[key] = len(frames)
        index.append(len(frames))
        #: ★ψ 与剖面同一条精度规矩（`_sig`，7 位有效数字）：逐帧写之后 ψ 是文件里最大的一块，
        #: 全精度会让它再涨近一倍，而 7 位对画图与写 g-file 都绰绰有余。
        frames.append([[_sig(x) for x in row] for row in e["psi"]])
    if frames:
        flat["psi"] = frames
        flat["psi_index"] = [float(i) for i in index]
        g = next((e for e in eqs if e.get("psi_r")), {})
        flat["psi_r"] = [float(x) for x in g.get("psi_r", [])]
        flat["psi_z"] = [float(x) for x in g.get("psi_z", [])]
        for k in ("axis_r", "axis_z", "psi_axis", "psi_bnd", "xpt_r", "xpt_z", "diverted"):
            flat[k] = [float((e or {}).get(k, math.nan)) for e in eqs]
        #: ★ψ 的通量规写在文件里：这些帧都已按内核演化出来的一维 ψ 两端重标过，
        #: 与状态里那条 ψ 同规 —— **整匝 Wb、轴上取极大**。读的人算 ψ_N 不受它影响，
        #: 算 q / B_p 受，所以它必须写出来而不是让人猜（g-file 的规是每弧度，差 2π）。
        flat["meta.psi_convention"] = "full_flux_Wb_axis_max"
        flat["bnd_r"] = [[float(x) for x in (e.get("bnd_r") or [])] for e in eqs]
        flat["bnd_z"] = [[float(x) for x in (e.get("bnd_z") or [])] for e in eqs]
    names = next((o.get("coil_names") for o in outs if o.get("coil_names")), [])
    if names:
        flat["coil_names"] = list(names)
    keys = sorted({k for o in outs for k in (o.get("extra") or {})})
    for k in keys:
        col = [(o.get("extra") or {}).get(k) for o in outs]
        if all(v is None or isinstance(v, (int, float)) for v in col):
            flat[f"extra.{k}"] = [math.nan if v is None else float(v) for v in col]
    flat["meta.units"] = json.dumps(UNITS_OUT, ensure_ascii=False)
    flat["meta.namelist"] = json.dumps(list(OUTPUT_NAMELIST))
    #: ★页面按这张表建 1-D 视图的通道选择器（键 · 中文名 · 单位），不在页面里写死
    flat["meta.profiles"] = json.dumps([[k, lab, u] for k, lab, u, _p, _t in _PROFILE_ROWS
                                        if k in flat], ensure_ascii=False)
    #: ★每个量的来路（kernel / solver / check / echo），页面按图标注
    prov = dict(PROVENANCE)
    if any((o.get("extra") or {}).get("shape_error") is not None for o in outs):
        prov["dfsdev"] = "solver"      #: isoflux 档：边界间隙由自由边界解给出
        prov["pf_current"] = "solver"
    elif any((o.get("extra") or {}).get("pf_solved") for o in outs):
        prov["pf_current"] = "solver"  #: 固定位形档给了装置卡：线圈电流也是解出来的
    flat["meta.provenance"] = json.dumps(prov, ensure_ascii=False)
    #: ★算这份结果的内核是哪一份：版本 · ABI · 构建时刻 · 归档 sha256
    try:
        ident = kernel().identity
    except Exception:                                                  # noqa: BLE001
        ident = {}
    for key, val in (("kernel_version", ident.get("kernel_version")), ("kernel_abi", ident.get("abi")),
                     ("kernel_built", ident.get("built")), ("kernel_sha256", ident.get("sha256")),
                     ("kernel_lib", ident.get("lib"))):
        if val is not None:
            flat[f"meta.{key}"] = str(val)
    flat["meta.provenance_note"] = json.dumps(PROVENANCE_NOTE, ensure_ascii=False)
    for k, v in (meta or {}).items():
        flat[f"meta.{k}"] = v
    return flat


def _flat_input(nodes: list, meta: dict | None = None) -> dict:
    """名表节点表 → 扁平 dict。

    ★**输入文件存的是节点，不是逐步采样**：一炮的波形本来就是几十个顶点的折线，存成
    383 行逐步值既看不出形状，也把「顶点在哪」这件事丢了。展开规则随文件走
    （`meta.interp = "linear"`，即 :func:`controls_at` 那条），读的人与页面按同一条规则还原。
    """
    flat: dict = {"time": [float(n["time"]) for n in nodes]}
    for k in INPUT_NAMELIST[1:]:
        flat[k] = [float(n.get(k, 0.0)) for n in nodes]
    flat["boundary_r"] = [[float(r) for r, _ in (n.get("boundary") or [])] for n in nodes]
    flat["boundary_z"] = [[float(z) for _, z in (n.get("boundary") or [])] for n in nodes]
    flat["pf_current"] = [[float(x) for x in (n.get("pf_current") or [])] for n in nodes]
    #: `phase` 不是名表的一项（它是回放自己的相位名），但页面拿它做相位芯片，所以带着
    flat["phase"] = [str(n.get("phase") or "") for n in nodes]
    flat["meta.units"] = json.dumps(UNITS_IN, ensure_ascii=False)
    flat["meta.namelist"] = json.dumps(list(INPUT_NAMELIST))
    flat["meta.form"] = "nodes"
    flat["meta.interp"] = "linear"
    for k, v in (meta or {}).items():
        flat[f"meta.{k}"] = v
    return flat


def _write_flat(path, flat: dict) -> str:
    """一份扁平 dict 写成 JSON。

    ★**只有 JSON 一种格式**：这个工具（连同旁边那张页面）从头到尾只用标准库，
    ``import ctypes / json / math`` 就是全部。要 numpy 数组的读者在读入之后自己转
    （``np.array(json.load(open("run.json"))["Te"])``），那一行比这里多一条二进制
    写法便宜得多。
    """
    path = Path(path)
    _refuse_npz(path)
    #: JSON 里不写 NaN / Infinity（`JSON.parse` 不收）：非有限值一律 null，读回来还原成 NaN
    def clean(v):
        if isinstance(v, float):
            return v if math.isfinite(v) else None
        if isinstance(v, list):
            return [clean(x) for x in v]
        return v
    path.write_text(json.dumps({k: clean(v) for k, v in flat.items()}, ensure_ascii=False, allow_nan=False),
                    encoding="utf-8")
    return str(path)


def _nan_back(v):
    """读 JSON 时 ``null`` 还原成 NaN。"""
    if v is None:
        return math.nan
    if isinstance(v, list):
        return [_nan_back(x) for x in v]
    return v


def _refuse_npz(path: Path) -> None:
    """``.npz`` 按名拒绝——说清楚为什么，并给出那一行替代写法。"""
    if path.suffix == ".npz":
        raise ValueError(f"{path.name}：这个工具只读写 JSON（不依赖 numpy）。"
                         f"要 numpy 数组：np.array(json.load(open('run.json'))['Te'])")


def _read_flat(path) -> dict:
    path = Path(path)
    _refuse_npz(path)
    return {k: (v if isinstance(v, str) else _nan_back(v))
            for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


def write_output(path, times, outs: list, meta: dict | None = None, psi_dedup: bool = False) -> str:
    """逐步输出写成一份扁平 JSON（``psi_dedup=True`` 时相同的 ψ 帧只存一次）。"""
    return _write_flat(path, _flat_output(times, outs, meta, psi_dedup))


#: ★**没有 `read_output`**：本文件与页面都不读输出文件（页面自己 `JSON.parse`）。
#: 要在别处读，用 `_read_flat(path)`——它就是那一行。

def write_waveform(path, nodes: list, meta: dict | None = None) -> str:
    """名表节点表写成**控制波形**文件（节点之间线性展开，见 :func:`controls_at`）。"""
    return _write_flat(path, _flat_input(nodes, meta))


def read_waveform(path) -> list:
    """控制波形文件 → **名表节点**列表（交给 :func:`run_discharge`，或用 :func:`controls_at` 展开）。"""
    flat = _read_flat(path)
    out = []
    for i, ti in enumerate(flat["time"]):
        n = {"time": float(ti)}
        for k in INPUT_NAMELIST[1:]:
            if k in flat:
                n[k] = float(flat[k][i])
        br, bz = flat.get("boundary_r"), flat.get("boundary_z")
        if br and bz and len(br) > i:
            pts = [[float(r), float(z)] for r, z in zip(br[i], bz[i]) if math.isfinite(float(r))]
            if pts:
                n["boundary"] = pts
        pf = flat.get("pf_current")
        if pf and len(pf) > i:
            vals = [float(x) for x in pf[i] if math.isfinite(float(x))]
            if vals:
                n["pf_current"] = vals
        ph = flat.get("phase")
        if ph and len(ph) > i and ph[i]:
            n["phase"] = str(ph[i])
        out.append(n)
    return out


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    #: ★★★**一次调用做的事**：给装置卡 · 状态 · 控制波形，从**状态所记的时刻**往后演化一段，
    #: 写出**演化完成的状态**（缺省产物），要整段过程就另加 `--series`。三类文件进出各归其位：
    #: 状态进 → 状态出，波形驱动，时序是可选的旁记。
    p = argparse.ArgumentParser(description="CFEDR 堆芯模型：装置卡 + 状态 + 控制波形 → 演化后的状态"
                                            "（可选整段时序），物理由 fylite 内核算")
    p.add_argument("--state", required=False,
                   help="起点：一份**状态**（初始 / 中间 / 结束同一类）；上游的 code/evolve 工况也收。"
                        "不给就按模板猜一个（见 --state-template）")
    p.add_argument("--state-template", default=None,
                   help="猜起步态时借物理设置的那份状态（缺省：脚本旁边的 state_init.json）")
    p.add_argument("--waveform", default=None,
                   help="控制波形：本工具的**节点表**；上游的 PCS 回放也收（读进来当场转）")
    #: ★三个旧名按名拒绝：它们的活都归 `--waveform` / `--state` 了。静默接受会让两种叫法
    #: 长期并存，而那正是这次要消掉的东西。
    for _old in ("--plan", "--replay", "--input"):
        p.add_argument(_old, default=None, help=argparse.SUPPRESS)
    p.add_argument("--duration", type=float, default=None, help="演化时长 [s]（自状态时刻起；与 --t1 二选一）")
    p.add_argument("--t0", type=float, help="起始时刻 [s]（不给就取状态的时刻，或工况的 t_start）")
    p.add_argument("--t1", type=float, help="终止时刻 [s]（不给就按 --duration，再不给就走到波形最后一个节点）")
    p.add_argument("--dt", type=float, default=0.5, help="控制节拍 [s]（名表的 time 间隔）")
    p.add_argument("--dt-flat", type=float, default=None, help="稳态平顶（150–6150 s）的控制节拍 [s]")
    p.add_argument("--dt-max", type=float, default=0.025, help="内核物理步长上限 [s]")
    p.add_argument("--out", default=None, help="**演化完成的状态**写到这里（单一时间片，可再 --state 接着走）")
    p.add_argument("--series", default=None, help="可选：整段演化的完整时序（每一步的输出名表 · 剖面 · 位形）")
    p.add_argument("--write-waveform", default=None, help="把这次用的名表节点另存为控制波形文件（.json）")
    #: ★`--save-state` 按名拒绝：它的活现在是 `--out` 的（缺省产物就是状态）。静默接受会让
    #: 旧脚本"跑完什么都没写"，而那种失败最难看出来。
    p.add_argument("--save-state", default=None, help=argparse.SUPPRESS)
    #: ★isoflux 是**缺省**：整条波形的位形随指令变，只有这一档算得对。固定位形档退成
    #: `--fixed-shape`，且只该用在位形不变的那一段（平顶）。
    p.add_argument("--fixed-shape", action="store_true",
                   help="位形固定档：用工况自带的度规，不解自由边界。**只适用于平顶那一段**")
    p.add_argument("--isoflux", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--device", default=None,
                   help="装置描述 JSON（缺省的 isoflux 档必需；--fixed-shape 时给了它就顺带解一组线圈电流）")
    p.add_argument("--boundary-tol", type=float, default=0.02, help="点动过多少米才重解 [m]")
    p.add_argument("--edge-ne-ref", type=float, nargs=2, default=None, metavar=("EDGE_NE", "NE_BAR"),
                   help="边界密度的参考对 [m^-3]（标定工况的那一对最准；不给则按首步自标定）")
    p.add_argument("--psi-stride", type=int, default=1, help="ψ 网格抽样步长（129×129 → 2 得 65×65）")
    p.add_argument("--psi-dedup", action="store_true",
                   help="相同的 ψ 帧只存一次（固定位形档整炮一帧）：省字节，代价是读的人要解 psi_index")
    #: ★缺省关：量出来更差（见 `steady_profile` 的注释），留这个开关是为了那次测量可重跑
    p.add_argument("--deliver-profile", action="store_true",
                   help="位形重解时把演化态反算出来的 p′/FF′ 投送给求解器（缺省关：实测两边差得更远）")
    #: ★密度是名表的一项，所以**缺省就跟名表走**；`--no-density` 才是那个对照开关。
    #: `--density` 仍然收（不报错、无作用），免得写了它的脚本一跑就红。
    #: ★实测（40 → 150 s 复现）：加料率**自 55 s 起一直顶在限幅上**（220 步里 191 步），
    #: 于是燃烧段的密度实际上是被边界那条同比缩放托住的，弹丸这一环是开环。要试别的限幅
    #: 就得能从命令行调，否则读者只能改源码——而改了源码的那一跑没人能复现。
    p.add_argument("--fuel-max-factor", type=float, default=4.0,
                   help="加料率限幅：工况自带加料率的几倍（缺省 4）")
    p.add_argument("--fuel-gain", type=float, default=1.0, help="加料反馈增益（缺省 1）")
    p.add_argument("--no-density", action="store_true",
                   help="不控密度：丢掉名表里的 ne_bar，只用工况自带的恒定加料率（对照跑法）")
    p.add_argument("--density", action="store_true",
                   help="（已退役，无作用）密度现在是名表的一项，缺省即控")
    a = p.parse_args(argv)
    if a.save_state:
        p.error("--save-state 已并入 --out：--out 写的就是演化完成的状态，整段时序改用 --series")
    for _old, _new in (("plan", "--state（工况就是还没推进过的状态）或 --waveform（工况 = 恒定指令）"),
                       ("replay", "--waveform（PCS 回放是它收的三种形状之一）"),
                       ("input", "--waveform（它读的是控制波形，不是「输入」的统称）")):
        if getattr(a, _old):
            p.error(f"--{_old} 已改名：请用 {_new}")
    if not a.waveform:
        p.error("要给 --waveform：本工具的节点表、PCS 回放，或 code/evolve 工况（= 恒定指令）")
    #: ★文件后缀**先看一眼**：不然一炮跑完几十分钟，最后一步才在写文件时被拒。
    for opt, val in (("--out", a.out), ("--series", a.series),
                     ("--write-waveform", a.write_waveform), ("--waveform", a.waveform)):
        try:
            _refuse_npz(Path(val)) if val else None
        except ValueError as exc:
            p.error(f"{opt} {exc}")
    try:
        device = load_device(a.device) if a.device else None
    except ValueError as exc:
        p.error(str(exc))
    if a.isoflux:
        p.error("--isoflux 已是缺省，不必再给；固定位形那一档改用 --fixed-shape（只适用于平顶）")
    mode = "check" if a.fixed_shape else "isoflux"
    if mode == "isoflux" and device is None:
        p.error("缺省的 isoflux 档要 --device（装置描述）：位形每步按控制点重解，没有线圈几何解不出来。"
                "只跑平顶那一段可以加 --fixed-shape")
    edge_ref = tuple(a.edge_ne_ref) if a.edge_ne_ref else None
    #: ★波形那一格收三种形状，按内容认；认出来之后走的是同一个 `run_discharge`，
    #: 于是「回放一炮」「重放一份波形」「按工况恒定指令跑」是同一条命令。
    try:
        nodes, wave_kind = load_waveform(a.waveform)
    except ValueError as exc:
        p.error(str(exc))
    if not nodes:
        p.error(f"{a.waveform} 里没有节点")
    #: ★没给起步态就**猜一个**（模板的物理设置 + 波形第一个节点），并在 stderr 说清楚换了什么
    if not a.state:
        try:
            st0 = guess_state(nodes, device, template=a.state_template,
                              log=lambda m: print(m, file=sys.stderr))
        except ValueError as exc:
            p.error(str(exc))
    else:
        try:
            st0 = load_state(a.state)
        except ValueError as exc:
            p.error(str(exc))
    #: ★时间窗：起点取状态记的时刻（工况那种取它的 `t_start`）；终点按 `--duration`，
    #: 没给就用 `--t1`，再没给就走到波形最后一个节点。
    if a.t0 is None:
        a.t0 = float(st0["t"])
    if a.duration is not None:
        if a.t1 is not None:
            p.error("--duration 与 --t1 只能给一个")
        a.t1 = a.t0 + float(a.duration)
    if a.t1 is None:
        a.t1 = float(nodes[-1]["time"])
    if not a.t1 > a.t0:
        p.error(f"终点 {a.t1} s 不在起点 {a.t0} s 之后")
    #: ★还没推进过的状态（记录为空）可以**改盖时刻**：`--t0` 说从哪起步，状态与工况的
    #: `t_start` 就都挪到那里。已经推进过的状态不许改——它的剖面属于它记的那一刻。
    if st0.get("record") is None and abs(float(st0["t"]) - a.t0) > 1e-9:
        st0 = dict(st0, t=a.t0, plan=dict(st0["plan"], settings=dict(st0["plan"]["settings"], t_start=a.t0)))
    res = run_discharge(None, nodes, a.t0, a.t1, a.dt, dt_max=a.dt_max, dt_flat=a.dt_flat,
                        series_path=a.series, state=st0, boundary_mode=mode, device=device,
                        boundary_tol=a.boundary_tol, density=not a.no_density, edge_ne_ref=edge_ref,
                        psi_stride=a.psi_stride, psi_dedup=a.psi_dedup,
                        deliver_profile=a.deliver_profile,
                        fuel_gain=a.fuel_gain, fuel_max_factor=a.fuel_max_factor)
    #: ★缺省产物是**状态**：写到 `--out`，下一次 `--state` 接着走（跑满或中途被拒都写）。
    if a.out and res.get("state"):
        print(f"状态（t = {res['state']['t']:.3f} s）：{save_state(a.out, res['state'])}")
    if a.write_waveform:
        path = write_waveform(a.write_waveform, nodes, meta={"source": a.waveform, "source_kind": wave_kind})
        print(f"控制波形（{len(nodes)} 个节点）：{path}")
    print(json.dumps(res["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
