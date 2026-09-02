"""数据源 ↔ fyo 文档：`libfylite_data.so` 的文档面（`rust/fylite_data/src/io.rs`）。

★★这是 :func:`fylite.fyo.write` / :func:`fylite.fyo.read` 之外的**第二条盘上通路**，
两者的分工：``fyo.write`` 写的是本包自己的 fyo 布局（JSON-LD / HDF5），这里除了同一
种布局之外还写 **IMAS DD 布局**——imas-python / imas-core 读得回的 netCDF 与 HDF5——
并且读 g-file / a-file / 任何一种上述文件时**看内容识别**，不看扩展名。多个数据源
的合并与按 JSON-LD 装配也在这里。

    from fylite.io import fydoc
    b = fydoc.read("g063982.04800")               # 自动识别 -> Bundle
    b.write("shot63982.nc", layout="imas")        # imas-python 读得回
    b.array("equilibrium/time_slice/0/profiles_2d/0/psi")   # numpy, [R, Z]
    fydoc.read("machine.h5").merge(b).write("all.jsonld")

路径的头一段是 IDS（`equilibrium`、`wall_1`），其余是文档路径；不带索引的名字段落到
结构数组的第 0 个（与 :mod:`fylite.fyo` 那张表同一条规则）。
"""
from __future__ import annotations

import ctypes
import json
from pathlib import Path

import numpy as np

from .. import kernel
from ..kernel import KernelError, _b, _BYTES, _VOID


def _buf(n: int):
    return (ctypes.c_uint8 * max(int(n), 1))()


def _text(buf, n: int) -> str:
    return bytes(buf)[:max(int(n), 0)].decode("utf-8", "replace")


def _err_text(err) -> str:
    return bytes(err).split(b"\0", 1)[0].decode("utf-8", "replace")


class Bundle:
    """一束 fyo 文档（一个文件 / 一炮通常不止一个 IDS），握着数据层的句柄。

    ★上下文管理器，理由与 :class:`fylite.kernel.MdsSession` 相同：句柄是对面的
    `Box`，丢了引用不 `close()` 就泄漏。
    """

    def __init__(self, handle):
        self._lib = kernel.require_data()
        self._h = handle
        #: 装配 / 取数留下的说明（没开窗的量、时基从哪来）；读文件的束为空。
        self.notes: list[str] = []

    # ---- construction ------------------------------------------------------

    @classmethod
    def read(cls, path) -> "Bundle":
        """读一个路径（自动识别格式与布局）。"""
        lib = kernel.require_data()
        pb, pn, _k = _b(str(Path(path)))
        h = _VOID()
        err = _buf(1024)
        rc = lib.fylite_data_read(pb, pn, ctypes.byref(h), ctypes.cast(err, _BYTES), len(err))
        if rc != 0:
            raise KernelError(f"read {path}: {_err_text(err)}")
        return cls(h)

    @classmethod
    def from_text(cls, text: str, format: str = "json") -> "Bundle":
        """从文本读：``json`` / ``geqdsk`` / ``afile``。"""
        lib = kernel.require_data()
        tb, tn, _k1 = _b(text)
        fb, fn, _k2 = _b(format)
        h = _VOID()
        err = _buf(1024)
        rc = lib.fylite_data_read_text(tb, tn, fb, fn, ctypes.byref(h), ctypes.cast(err, _BYTES), len(err))
        if rc != 0:
            raise KernelError(f"read {format} text: {_err_text(err)}")
        return cls(h)

    @classmethod
    def from_dict(cls, doc: dict) -> "Bundle":
        """从一份（或一束）fyo 文档字典来。"""
        return cls.from_text(json.dumps(_jsonable(doc), allow_nan=True), "json")

    @classmethod
    def empty(cls) -> "Bundle":
        lib = kernel.require_data()
        h = _VOID()
        lib.fylite_data_bundle_new(ctypes.byref(h))
        return cls(h)

    # ---- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        if self._h:
            self._lib.fylite_data_bundle_free(self._h)
            self._h = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:  # noqa: BLE001 — interpreter teardown
            pass

    # ---- reading -----------------------------------------------------------

    @property
    def keys(self) -> list[str]:
        """``["equilibrium", "wall_1", …]``。"""
        n = self._lib.fylite_data_bundle_keys(self._h, None, 0)
        buf = _buf(n)
        self._lib.fylite_data_bundle_keys(self._h, ctypes.cast(buf, _BYTES), len(buf))
        text = _text(buf, n)
        return [k for k in text.split("\n") if k]

    def to_dict(self) -> dict:
        """整束：单份文档本身，多份为 ``{"<ids>[_<occ>]": doc}``。"""
        n = self._lib.fylite_data_bundle_json(self._h, None, 0)
        buf = _buf(n)
        self._lib.fylite_data_bundle_json(self._h, ctypes.cast(buf, _BYTES), len(buf))
        return json.loads(_text(buf, n))

    def get(self, path: str, default=KeyError):
        """一条路径下的子树（JSON 形：数组是嵌套列表）。"""
        pb, pn, _k = _b(path)
        n = self._lib.fylite_data_doc_json(self._h, pb, pn, None, 0)
        if n < 0:
            if default is KeyError:
                raise KeyError(path)
            return default
        buf = _buf(n)
        self._lib.fylite_data_doc_json(self._h, pb, pn, ctypes.cast(buf, _BYTES), len(buf))
        return json.loads(_text(buf, n))

    def array(self, path: str) -> np.ndarray:
        """一个数值叶子，作为 ``float64`` 数组（行主序、带形状）。"""
        pb, pn, _k = _b(path)
        ndim = ctypes.c_uint64()
        dims = np.zeros(16, dtype=np.uint64)
        n = self._lib.fylite_data_doc_array(self._h, pb, pn, np.empty(0), 0, dims, dims.size,
                                            ctypes.byref(ndim))
        if n == -2:
            raise KeyError(path)
        if n == -3:
            raise TypeError(f"{path} is not numeric")
        if n < 0:
            raise KernelError(f"array {path}: {n}")
        out = np.empty(int(n), dtype=np.float64)
        self._lib.fylite_data_doc_array(self._h, pb, pn, out, out.size, dims, dims.size,
                                        ctypes.byref(ndim))
        shape = tuple(int(d) for d in dims[:int(ndim.value)])
        return out.reshape(shape) if shape else out[0]

    # ---- writing -----------------------------------------------------------

    def set(self, path: str, value) -> "Bundle":
        """放一个值：numpy 数组 / 数走 f64 快道，其余以 JSON 进。"""
        pb, pn, _k = _b(path)
        if isinstance(value, np.ndarray) and value.dtype.kind in "fiu":
            arr = np.ascontiguousarray(value, dtype=np.float64)
            dims = np.asarray(arr.shape, dtype=np.uint64)
            rc = self._lib.fylite_data_doc_set_array(self._h, pb, pn, arr.ravel(), dims, dims.size)
        else:
            jb, jn, _k2 = _b(json.dumps(_jsonable(value), allow_nan=True))
            rc = self._lib.fylite_data_doc_set_json(self._h, pb, pn, jb, jn)
        if rc != 0:
            raise KernelError(f"set {path}: {rc}")
        return self

    def merge(self, other: "Bundle", *, keep: bool = False) -> "Bundle":
        """把另一束合进来（缺省后者覆盖；``keep`` 只补缺）。"""
        self._lib.fylite_data_bundle_merge(self._h, other._h, 1 if keep else 0)
        return self

    def write(self, path, *, format: str | None = None, layout: str = "fyo") -> str:
        """写出去。``format`` 缺省按扩展名（``json`` / ``geqdsk`` / ``hdf5`` / ``netcdf`` /
        ``imas-hdf5``）；``layout`` 是 ``fyo`` 或 ``imas``。返回写出报告（可能为空）。"""
        pb, pn, _k1 = _b(str(Path(path)))
        fb, fn, _k2 = _b(format or "")
        lb, ln, _k3 = _b(layout)
        err = _buf(4096)
        rc = self._lib.fylite_data_write(self._h, pb, pn, fb, fn, lb, ln, ctypes.cast(err, _BYTES), len(err))
        if rc != 0:
            raise KernelError(f"write {path}: {_err_text(err)}")
        return _err_text(err)


def _jsonable(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def detect(path) -> tuple[str, str]:
    """``(format, layout)`` —— 看内容识别。"""
    lib = kernel.require_data()
    pb, pn, _k = _b(str(Path(path)))
    buf = _buf(1024)
    n = lib.fylite_data_detect(pb, pn, ctypes.cast(buf, _BYTES), len(buf))
    if n < 0:
        raise KernelError(f"detect {path}: {_text(buf, min(len(buf), 1024)).split(chr(0))[0]}")
    fmt, _, lay = _text(buf, n).partition(" ")
    return fmt, lay


def read(path) -> Bundle:
    """读一个路径成一束（自动识别）。"""
    return Bundle.read(path)


def write(doc, path, *, format: str | None = None, layout: str = "fyo") -> str:
    """写一份文档字典 / 一束。"""
    b = doc if isinstance(doc, Bundle) else Bundle.from_dict(doc)
    return b.write(path, format=format, layout=layout)


def _params_json(shot, time, max_points, select, slots) -> str:
    """装配参数 → 一段 JSON（Rust 侧 ``Overrides::from_node`` 读）。``time`` 是一个数（点）、
    ``(t0, t1)``（窗）、三个以上的序列（点列）或 ``"4:5"`` 文本。"""
    p: dict = {}
    if shot is not None:
        p["shot"] = int(shot)
    if time is not None:
        if isinstance(time, str):
            p["time"] = time
        elif isinstance(time, (int, float, np.generic)):
            p["time"] = float(time)
        else:
            p["time"] = [float(t) for t in np.asarray(time).ravel()]
    if max_points is not None:
        p["max_points"] = int(max_points)
    if select:
        p["select"] = [select] if isinstance(select, str) else list(select)
    if slots:
        p["slots"] = {k: int(v) for k, v in dict(slots).items()}
    return json.dumps(p)


def _split_report(err) -> tuple[list[str], list[str]]:
    lines = [f for f in _err_text(err).split("\n") if f]
    fails = [f for f in lines if not f.startswith("note: ")]
    notes = [f[len("note: "):] for f in lines if f.startswith("note: ")]
    return fails, notes


def assemble(path, *, shot: int | None = None, time=None, max_points: int | None = None,
             select=None, slots=None, user: str | None = None,
             timeout_ms: int = 10_000) -> tuple[Bundle, list[str]]:
    """执行一份装配文档（``fylite:Assembly/1``，JSON 或 YAML）。返回 ``(束, 失败清单)``；
    说明（没开窗的量、时基从哪来）在 ``束.notes``。

    ``time``：一个数是一个时刻（取最近样本），``(t0, t1)`` 是一个窗，更长的序列是一列
    时刻；MDSplus 源在各自的时基上开窗，切片在服务端做。``max_points`` 是窗内最多取的
    样本数。``select`` 是只留的 ``ids`` / ``ids/子树``。"""
    lib = kernel.require_data()
    pb, pn, _k1 = _b(str(Path(path)))
    jb, jn, _k2 = _b(_params_json(shot, time, max_points, select, slots))
    ub, un, _k3 = _b(user or "")
    h = _VOID()
    err = _buf(1 << 16)
    rc = lib.fylite_data_assemble(pb, pn, jb, jn, ub, un, int(timeout_ms),
                                  ctypes.byref(h), ctypes.cast(err, _BYTES), len(err))
    if rc != 0:
        raise KernelError(f"assemble {path}: {_err_text(err)}")
    fails, notes = _split_report(err)
    b = Bundle(h)
    b.notes = notes
    return b, fails


def fetch(machine, ids, *, shot: int, time=None, max_points: int | None = None, select=None,
          provider: str | None = None, host: str | None = None, port: int | None = None,
          user: str | None = None, timeout_ms: int = 10_000) -> tuple[Bundle, list[str]]:
    """从 fydata 的装置清单（``machine.yaml``）取一炮的若干 IDS：几何 + MDSplus 绑定，按
    ``shot`` / ``time`` 开窗。例如 EAST 138569 炮 4～5 秒的磁测量::

        b, fails = fetch("fydata/machine/tokamak/east/machine.yaml", "magnetics",
                         shot=138569, time=(4.0, 5.0), host="mds.ipp.ac.cn")
        b.array("magnetics/b_field_pol_probe/0/field/data")

    返回 ``(束, 失败清单)``；说明在 ``束.notes``。"""
    lib = kernel.require_data()
    mb, mn, _k1 = _b(str(Path(machine)))
    ib, in_, _k2 = _b(ids if isinstance(ids, str) else ",".join(ids))
    jb, jn, _k3 = _b(_params_json(shot, time, max_points, select, None))
    vb, vn, _k4 = _b(provider or "")
    hb, hn, _k5 = _b(host or "")
    ub, un, _k6 = _b(user or "")
    h = _VOID()
    err = _buf(1 << 16)
    rc = lib.fylite_data_fetch(mb, mn, ib, in_, jb, jn, vb, vn, hb, hn, int(port or 0), ub, un,
                               int(timeout_ms), ctypes.byref(h), ctypes.cast(err, _BYTES), len(err))
    if rc != 0:
        raise KernelError(f"fetch {machine}: {_err_text(err)}")
    fails, notes = _split_report(err)
    b = Bundle(h)
    b.notes = notes
    return b, fails


# --------------------------------------------------------------------------- #
# the JSON door: one plan in, one record out
# --------------------------------------------------------------------------- #
def case_json(plan, *, base=None, kernel_lib=None) -> dict:
    """One ``fyo:ScenarioSpecification`` in, one ``spo:ComputationRecord`` out.

    ``plan`` is a dict (one plan), a list of dicts (composed in order, later
    ones overriding earlier ones), or the JSON text of either.  File endpoints
    in the plan resolve against ``base``; ``kernel_lib`` names
    ``libfylite_kernel.so`` (default: ``$FYLITE_KERNEL_LIB`` or ``_lib/``).

    ★The whole run — composing the plan, resolving its inputs, the kernel's
    single door ``fylite_rs_fyo``, the record with the datasets INLINE on
    their output ports — is the data layer's ``fylite_data_case_json``; this
    is a thin face on it, so Python and the shell (``fylite-case json``) go
    through one implementation.  A refused case still comes back as a record
    (``run_state: rejected``) with the kernel's sentence in ``comment``;
    only a plan that yields no record at all raises.
    """
    lib = kernel.require_data()
    f = lib.fylite_data_case_json
    f.argtypes = [_BYTES, ctypes.c_uint64, _BYTES, ctypes.c_uint64, _BYTES, ctypes.c_uint64,
                  ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint64)]
    f.restype = ctypes.c_int32
    lib.fylite_data_case_free.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    lib.fylite_data_case_free.restype = None
    text = plan if isinstance(plan, str) else json.dumps(plan, ensure_ascii=False)
    pb, pn, _k1 = _b(text)
    bb, bn, _k2 = _b(str(Path(base)) if base is not None else "")
    kb, kn, _k3 = _b(str(Path(kernel_lib)) if kernel_lib is not None else "")
    out = ctypes.c_void_p()
    n = ctypes.c_uint64()
    rc = f(pb, pn, bb, bn, kb, kn, ctypes.byref(out), ctypes.byref(n))
    try:
        body = ctypes.string_at(out.value, n.value).decode("utf-8", "replace") if out.value else ""
    finally:
        if out.value:
            lib.fylite_data_case_free(out.value, n.value)
    if rc < 0:
        raise KernelError(f"fylite_data_case_json returned {rc}: {body}")
    return json.loads(body)
