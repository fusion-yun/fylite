"""PCS 步进会话（台账 I-8 · PCS-W6）：一个 10 ms 步一个请求，状态留在会话里。

★★接口的真源是内核仓 `docs/note/cfedr-pcs-interface.md` v0.2（按 IMAS DD 4.1.1 自定）：
``open`` 给定一份工况文档（``code/evolve`` 的 ``settings`` / ``inputs``）与指令到文档的映射，
``step`` 送一步指令、得一步输出，``close`` 交回逐步墙钟分布与计数。本模块**不算任何物理**：
每一步都是内核的 ``code/evolve``（``dt = 0.01 s``、``nsteps = 1``），续跑按内核自己的交接名
（``t_end → t_start`` · ``dt_next → dt_start`` · ``edge_te_out → edge_te_in`` …）从上一步的
记录摆回——与 :mod:`fylite.scenario.model` 分块推进同一套摆法。

★**拒绝不中断会话**（接口表 §5）：被拒的一步 ``rejected = true``，输出沿用上一步，``reason``
按名说出哪一条；下一步照常可送。

★**本版如实说出的两件未做的事**：几何固定为工况文档自带的那一份（``geometry_fixed`` 恒真，
参考 LCFS 只核点数与自交，不驱动平衡）；放电相位模型未落（台账 I-7），``phase`` 在 t ≥ 1 s
为 ``None``。``engine`` 在导入时只用标准库：numpy 与内核都在调用时才装载。
"""
from __future__ import annotations

import time
import uuid

__all__ = ["STEP_S", "Session", "SessionError", "open_session", "step_session",
           "close_session", "sessions"]

#: 接口表 §1：固定步长 [s]
STEP_S = 0.01

#: 续跑标量：记录里的名 → 下一次调用的设置名（内核声明的配对）
_CARRY = (("t_end", "t_start"), ("dt_next", "dt_start"), ("edge_te_out", "edge_te_in"),
          ("edge_ti_out", "edge_ti_in"), ("dt_capped", "capped_in"),
          ("saw_elapsed_out", "saw_elapsed_in"), ("dt_fraction_used", "dt_fraction_in"),
          ("ipctl_ratio0_out", "ipctl_ratio0_in"), ("ipctl_integral_out", "ipctl_integral_in"),
          ("ipctl_calibrated_out", "ipctl_calibrated_in"),
          #: the L-H phase (ledger I-7) — present only when the case sets `lh_model`
          ("lh_phase_out", "lh_phase_in"),
          #: ★2026-09-14 (PCS I-10): the IPB98 scaling's references and tau_E-anchor integrator
          #: (`chi_scaling = ipb98`) — without them every call re-anchored to its own state, so the
          #: anchor never pulled back and a CFEDR burn slid from 1.5 GW to L mode in ~20 s
          ("chi_scale_ploss_ref", "chi_scale_ploss_ref"), ("chi_scale_ne_ref", "chi_scale_ne_ref"),
          ("chi_scale_ip_ref", "chi_scale_ip_ref"), ("chi_scale_w_ref", "chi_scale_w_ref"),
          ("chi_scale_int", "chi_scale_int"))

#: 滞后量：记录的原始条目 → ``evolve/fylite:*`` 输入（旧拼法，内核第二读）
_LAGS = (("psi_prev_out", "fylite:psi_prev"), ("sigma_prev_out", "fylite:sigma_prev"),
         ("exch_prev_out", "fylite:exch_prev"))

#: ★2026-09-14（PCS I-10 读出）：内核续跑读的**全部**滞后量都是声明的 ``core_profiles/profiles_1d``
#: 槽（内核 `-16` G-8，同名先读）——此前会话只经旧拼法交三份，闭包的 Z_eff 与粒子 D / V 两份滞后量
#: 每次调用都被置零。记录里带着哪一份，就按同名槽原样交回。
_PROFILE_LAGS = ("fylite:psi_prev", "fylite:sigma_prev", "fylite:exch_prev",
                 "fylite:dn_prev", "fylite:vn_prev", "zeff")

#: α 份额（3.518 / 17.589 MeV）：记录的 α 功率折回聚变功率
_ALPHA_SHARE = 3.518 / 17.589


class SessionError(ValueError):
    """会话本身用错了（未知会话号、工况文档缺件）——不是一步指令被拒。"""


def _rejection(k, cmd: dict, n_ec: int, t_now: float, require_lcfs_after: float) -> str | None:
    """接口表 §5 的拒绝条件，按名说出第一条；都不成立时 ``None``。"""
    if not isinstance(k, int) or isinstance(k, bool):
        return f"k must be an integer step index, got {k!r}"
    dt = cmd.get("dt", STEP_S)
    if abs(float(dt) - STEP_S) > 1e-12:
        return f"dt must be {STEP_S} s (fixed 10 ms step), got {dt}"
    if float(cmd.get("p_nbi", 0.0)) != 0.0:
        return ("p_nbi is nonzero: the CFEDR device description has no neutral beam — missing beam energy, "
                "injection geometry (tangency radius, height) and species")
    if float(cmd.get("p_lh", 0.0)) != 0.0:
        return ("p_lh is nonzero: the CFEDR device description has no lower hybrid system — missing frequency, "
                "parallel refractive index spectrum n_par and antenna position")
    for name in ("p_ic", "gas_rate", "ne_cmd"):
        if name in cmd and not float(cmd[name]) >= 0.0:
            return f"{name} is negative ({cmd[name]})"
    p_ec = cmd.get("p_ec")
    if p_ec is not None:
        if len(p_ec) != n_ec:
            return f"p_ec has {len(p_ec)} groups, the session opened with {n_ec}"
        for i, v in enumerate(p_ec):
            if not float(v) >= 0.0:
                return f"p_ec[{i}] is negative ({v})"
    for i, pel in enumerate(cmd.get("pellet") or []):
        if not float(pel.get("n_atoms", 0.0)) >= 0.0 or not float(pel.get("velocity_initial", 0.0)) >= 0.0:
            return f"pellet[{i}] has a negative particle count or velocity"
        if not 0.0 <= float(pel.get("fraction_t", 0.5)) <= 1.0:
            return f"pellet[{i}] fraction_t is outside [0, 1]"
    if "gas_fraction_t" in cmd and not 0.0 <= float(cmd["gas_fraction_t"]) <= 1.0:
        return f"gas_fraction_t is outside [0, 1] ({cmd['gas_fraction_t']})"
    r, z = cmd.get("lcfs_r"), cmd.get("lcfs_z")
    if r is None and z is None:
        if t_now >= require_lcfs_after:
            return f"lcfs_r / lcfs_z are missing at t {t_now:.3f} s (a closed LCFS is required from t {require_lcfs_after} s)"
        return None
    if r is None or z is None or len(r) != len(z):
        return "lcfs_r and lcfs_z must be given together with the same number of points"
    pts = [(float(a), float(b)) for a, b in zip(r, z)]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 16:
        return f"lcfs has {len(pts)} distinct points, at least 16 are required"
    for i, (a, _b) in enumerate(pts):
        if not a > 0.0:
            return f"lcfs point {i} has R = {a} (R must be positive)"
    bad = _self_intersection(pts)
    if bad is not None:
        return f"lcfs self-intersects: segment {bad[0]} crosses segment {bad[1]}"
    return None


def _self_intersection(pts):
    """闭合折线的第一对相交的非相邻线段，没有时 ``None``。"""
    n = len(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    for i in range(n):
        p1, p2 = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            q1, q2 = pts[j], pts[(j + 1) % n]
            d1, d2 = cross(q1, q2, p1), cross(q1, q2, p2)
            d3, d4 = cross(p1, p2, q1), cross(p1, p2, q2)
            if d1 * d2 < 0.0 and d3 * d4 < 0.0:
                return i, j
    return None


class Session:
    """一个步进会话：工况文档 + 指令映射 + 上一步的记录。"""

    def __init__(self, plan: dict, *, ec_sources=(), ic_source=None, t_start: float = 0.0,
                 require_lcfs_after: float = 1.0):
        if not isinstance(plan, dict) or not isinstance(plan.get("settings"), dict):
            raise SessionError("open needs plan: {settings: {...}, inputs: {...}} — the code/evolve case document")
        self.id = uuid.uuid4().hex
        self.plan = {"settings": dict(plan["settings"]), "inputs": dict(plan.get("inputs") or {})}
        #: EC 组序 → 内核的表格源号（``source_power_<k>``）；None = 该组无沉积表
        self.ec_sources = list(ec_sources)
        self.ic_source = ic_source
        self.t_start = float(t_start)
        self.require_lcfs_after = float(require_lcfs_after)
        self.k_next = 0
        self.prev = None
        self.last = None
        self.walls: list[float] = []
        #: kernel calls per accepted step, and the last step's count
        self.calls: list[int] = []
        self.last_calls = 0
        self.rejected = 0

    # -- one step ---------------------------------------------------------- #
    def step(self, k, cmd: dict) -> dict:
        clock = time.perf_counter()
        t_now = self.t_start + self.k_next * STEP_S
        reason = None
        if k != self.k_next:
            reason = f"k must be {self.k_next} (the next step), got {k!r}"
        if reason is None:
            reason = _rejection(k, cmd, len(self.ec_sources), t_now, self.require_lcfs_after)
        if reason is None:
            reason = self._unmapped_power(cmd)
        if reason is not None:
            self.rejected += 1
            out = dict(self.last) if self.last is not None else {"t": t_now}
            out["flags"] = dict(out.get("flags") or {}, rejected=True)
            out["reason"] = reason
            out["wall_ms"] = (time.perf_counter() - clock) * 1e3
            self.walls.append(out["wall_ms"])
            return out
        rec = self._march(cmd)
        self.prev = rec
        self.k_next += 1
        out = self._outputs(rec, cmd)
        out["wall_ms"] = (time.perf_counter() - clock) * 1e3
        out["calls"] = self.last_calls
        self.calls.append(self.last_calls)
        self.walls.append(out["wall_ms"])
        self.last = out
        return out

    def _unmapped_power(self, cmd: dict) -> str | None:
        for i, v in enumerate(cmd.get("p_ec") or []):
            if float(v) != 0.0 and self.ec_sources[i] is None:
                return f"p_ec[{i}] is nonzero and the session's case binds no deposition table for that EC group"
        if float(cmd.get("p_ic", 0.0)) != 0.0 and self.ic_source is None:
            return "p_ic is nonzero and the session's case binds no deposition table for ICRF"
        return None

    #: sub-calls allowed inside one 10 ms step before the session gives up by name
    MAX_SUBSTEPS = 10000

    #: the pellet deposit's parameterised penetration (CASE-20's TGYRO `gauss_add:(0.7, 0.2, …)`)
    PELLET_CENTRE = 0.7
    PELLET_WIDTH = 0.2

    def _commands_to_settings(self, cmd: dict) -> dict:
        """One step's commands as ``code/evolve`` settings (interface v0.2 §3 → the kernel's names).

        ``ip`` [A] → ``ip`` [kA] · ``p_ec[i]`` / ``p_ic`` [W] → ``source_power_<k>`` of the table the
        group is bound to · ``gas_rate`` [electrons/s] → ``gas_rate`` (the density channel's puff) ·
        the step's ``pellet`` events → ``fuel_rate`` = Σ ``n_atoms`` / 10 ms on the Gaussian at
        ``PELLET_CENTRE`` / ``PELLET_WIDTH`` (an event's own ``centre`` / ``width`` override them).
        A step with no pellet and no puff sends ``fuel_rate`` / ``gas_rate`` of zero, so a burst never
        leaks into the next step.
        """
        st: dict = {}
        if "ip" in cmd:
            st["ip"] = float(cmd["ip"]) / 1e3
        for i, v in enumerate(cmd.get("p_ec") or []):
            if self.ec_sources[i] is not None:
                st[f"source_power_{int(self.ec_sources[i])}"] = float(v)
        if self.ic_source is not None and "p_ic" in cmd:
            st[f"source_power_{int(self.ic_source)}"] = float(cmd["p_ic"])
        if "gas_rate" in cmd or "pellet" in cmd:
            st["gas_rate"] = float(cmd.get("gas_rate", 0.0))
            pellets = cmd.get("pellet") or []
            st["fuel_rate"] = sum(float(p.get("n_atoms", 0.0)) for p in pellets) / STEP_S
            if pellets:
                st["fuel_centre"] = float(pellets[0].get("centre", self.PELLET_CENTRE))
                st["fuel_width"] = float(pellets[0].get("width", self.PELLET_WIDTH))
        return st

    def _march(self, cmd: dict) -> dict:
        """One 10 ms step: ``code/evolve`` calls of one kernel step each, until the clock reaches it.

        ★The kernel caps a step at a quarter of the fastest exchange time (``dt_capped``) and
        ``nsteps`` counts the steps it RAN — on a dense, cold plasma one call covers ~1.5 ms, on
        CFEDR ~0.3 ms.  So the host hands each call the time still left to the step's end (``dt`` on
        the first call, ``dt_start`` on a resumed one) and resumes from the record until the clock
        is there; the kernel never grows a step past what it is handed (``dttarget = 0``).
        """
        from ..io import fydoc

        base = dict(self.plan["settings"], dttarget=0.0, nsteps=1.0, globals=1.0)
        base.update(self._commands_to_settings(cmd))
        t0 = self.t_start if self.prev is None else float(self.prev["facts"]["t_end"]["value"])
        target = self.t_start + (self.k_next + 1) * STEP_S
        rec = self.prev
        #: kernel calls this 10 ms step took (the host sub-steps against the kernel's exchange cap)
        self.last_calls = 0
        for _ in range(self.MAX_SUBSTEPS):
            t_now = t0 if rec is None else float(rec["facts"]["t_end"]["value"])
            left = target - t_now
            if left <= 1e-12:
                return rec
            self.last_calls += 1
            st, inp = self._resume(base, rec, left)
            rec = fydoc.complete("code/evolve", {"settings": st, "inputs": inp})
        raise SessionError(f"step {self.k_next} did not reach t {target:.6f} s within {self.MAX_SUBSTEPS} kernel steps")

    def _resume(self, base: dict, rec, left: float) -> tuple[dict, dict]:
        """The next call's settings and inputs: the plan, the step's commands, and ``rec``'s hand-over."""
        import numpy as np

        st = dict(base)
        inp = dict(self.plan["inputs"])
        if rec is None:
            st["dt"] = left
            if self.t_start != 0.0:
                st["t_start"] = self.t_start
            return st, inp
        fc = rec["facts"]
        st.update({"resume": 1.0, "state": 1.0})
        for src, dst in _CARRY:
            if src in fc:
                st[dst] = fc[src]["value"]
        #: the time left to the step's end, not the size the last call would hand on
        st["dt_start"] = left
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
            prof["grid"] = {"psi": np.asarray(raw["psi"]["data"], float)}
        inp["core_profiles"] = {"profiles_1d": prof}
        inp["evolve"] = {dst: raw[src]["data"] for src, dst in _LAGS if src in raw}
        return st, inp

    def _outputs(self, rec: dict, cmd: dict) -> dict:
        import numpy as np

        fc, F = rec["facts"], rec["fields"]
        fact = lambda key: float(fc[key]["value"]) if key in fc else None  # noqa: E731
        cp = F["core_profiles"]["profiles_1d"]
        te = np.asarray(cp["electrons"]["temperature"]["data"], float)
        ti = np.asarray(cp["t_i_average"]["data"], float)
        ne = np.asarray(cp["electrons"]["density"]["data"], float)
        p_alpha_trace = F.get("summary", {}).get("fusion", {}).get("power", {}).get("value", {}).get("data") or []
        p_alpha = float(p_alpha_trace[-1]) if len(p_alpha_trace) else None
        v_loop_trace = (F.get("v_loop_used") or {}).get("data") or []
        t = fact("t_end")
        #: ★the discharge phase (interface v0.2 §4 `flags.phase`): the zero-D layer's before 1 s,
        #: the kernel's L-H phase after it when the case runs one (`lh_model`, ledger I-7), else unknown
        lh_trace = (F.get("lh_phase") or {}).get("data") or []
        if t is not None and t < 1.0:
            phase = "zerod"
        elif len(lh_trace):
            phase = "H" if float(lh_trace[-1]) != 0.0 else "L"
        else:
            phase = None
        p_fus = fact("p_fus")
        if p_fus is None and p_alpha is not None:
            p_fus = p_alpha / _ALPHA_SHARE
        return {
            "t": t, "p_fus": p_fus, "p_alpha": p_alpha,
            "p_neutron": None if p_fus is None else p_fus * (1.0 - _ALPHA_SHARE),
            "v_loop": float(v_loop_trace[-1]) if len(v_loop_trace) else None,
            "beta_p": fact("beta_pol"), "li_3": fact("li_3"), "li_1": fact("li1"),
            "te": te.tolist(), "ti": ti.tolist(), "ne": ne.tolist(),
            "te0": float(te[0]), "ti0": float(ti[0]),
            "i_bs": fact("i_bs"), "i_ni": fact("i_ni"), "i_cd": fact("i_cd"),
            "r_plasma": fact("r_plasma"), "w_th": fact("w_th"),
            "lcfs_real_r": None, "lcfs_real_z": None, "lcfs_dev_rms": None, "lcfs_dev_max": None,
            "pf_hold": None, "vs_feedback": None, "flux_margin": None,
            "flags": {"rejected": False, "eq_updated": False, "eq_stale": False, "geometry_fixed": True,
                      "density_prescribed": True, "coils_at_limit": False, "lcfs_pf_mismatch": False,
                      "anchored": True, "synthetic": bool(cmd.get("synthetic", False)),
                      "phase": phase},
            "reason": None,
        }

    # -- the end ----------------------------------------------------------- #
    def close(self) -> dict:
        w = sorted(self.walls)

        def q(p):
            return w[min(len(w) - 1, int(round(p * (len(w) - 1))))] if w else None
        return {"session": self.id, "steps": self.k_next, "rejected": self.rejected,
                "t_end": None if self.last is None else self.last.get("t"),
                "wall_ms": {"p50": q(0.50), "p99": q(0.99), "max": w[-1] if w else None, "n": len(w)},
                "kernel_calls": {"total": sum(self.calls), "max": max(self.calls) if self.calls else None}}


#: 本进程里开着的会话（stdio 服务一进程一份）
sessions: dict[str, Session] = {}


def open_session(plan: dict, *, ec_sources=(), ic_source=None, t_start: float = 0.0,
                 require_lcfs_after: float = 1.0) -> dict:
    s = Session(plan, ec_sources=ec_sources, ic_source=ic_source, t_start=t_start,
                require_lcfs_after=require_lcfs_after)
    sessions[s.id] = s
    return {"session": s.id, "step_s": STEP_S, "ec_groups": len(s.ec_sources),
            "t_start": s.t_start}


def _get(session_id) -> Session:
    s = sessions.get(session_id)
    if s is None:
        raise SessionError(f"no open session {session_id!r}")
    return s


def step_session(session_id, k, commands: dict | None = None) -> dict:
    return _get(session_id).step(k, dict(commands or {}))


def close_session(session_id) -> dict:
    s = _get(session_id)
    del sessions[session_id]
    return s.close()
