"""Flat kernel calls in the assembly layer only ever SHRINK — K-1's own criterion.

FYL-DESIGN-16 K-1: 「`scenario/` 与页面 JS 里不再出现 `fylite_rs_*` 符号名」——文档门是
内核唯一的接口，扁平 C 导出面是本地后端的实现细节。这条闸子是那句话在 Python 侧的
**棘轮**（内核仓 `tests/test_seam_is_fyo_only.py` 是同一条缝的另一面）：今天的数是
基线，只准降；一个文件降到 0 就从表里删掉。

★What is counted: every call through the kernel module alias (``kernel.X(…)`` /
``K.X(…)``) in ``scenario/**``, ``device.py`` and ``fyo.py`` — EXCEPT the doors
(``scenario``) and the loader's own face (``grid_of``, ``require_data``, ``load``,
``abi_version``).  Counted by AST, not by grep: a call in a docstring is not a call.

★Why a ratchet and not a target.  P1 (FYL-DESIGN-16 §分期) is the critical path
and the largest phase — 271 call points when the design was written.  A number
that may only fall makes every sink visible and every regression loud; a
target date makes neither.  ★2026-09-05: `vertical_system` went first (15 -> 5
host-side assembly calls in `scenario/control/vertical.py`; the plant is
`code/vstab`'s, the five left are the diagnostic rows and the closed loop).
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "fylite"
FILES = sorted(list((ROOT / "scenario").rglob("*.py")) + [ROOT / "device.py", ROOT / "fyo.py"])
ALIASES = {"kernel", "K"}
DOORS = {"scenario", "grid_of", "require_data", "load", "abi_version"}

#: 2026-09-05 measured baseline, after `code/vstab` (vertical_system 15 -> 5, vertical_mode 7 -> 6, breakdown 14 -> 13).
#: Only ever lower these.
BASELINE = {
    'device.py': 7,
    'fyo.py': 5,
    'scenario/analysis/__init__.py': 2,
    'scenario/analysis/loop.py': 4,
    'scenario/analysis/moments.py': 2,
    'scenario/analysis/recon_rs.py': 12,
    'scenario/control/evolution.py': 1,
    'scenario/control/stability.py': 6,
    'scenario/control/vertical.py': 1,
    'scenario/design/__init__.py': 13,
    'scenario/design/pulse.py': 3,
    'scenario/design/shape.py': 1,
    'scenario/model/__init__.py': 17,
    'scenario/model/assembly.py': 13,
    'scenario/model/closure.py': 49,
    'scenario/model/edge.py': 2,
    'scenario/model/gyrofluid.py': 8,
    'scenario/model/ic.py': 2,
    'scenario/model/lh.py': 5,
    'scenario/model/mapping.py': 3,
    'scenario/model/nbi.py': 29,
    'scenario/model/neoclassical.py': 11,
    'scenario/model/qlknn_closure.py': 21,
    'scenario/waveform.py': 2,
}


def _sites() -> dict[str, int]:
    out: dict[str, int] = {}
    for f in FILES:
        tree = ast.parse(f.read_text(encoding="utf-8"), str(f))
        n = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in ALIASES and node.func.attr not in DOORS:
                n += 1
        if n:
            out[str(f.relative_to(ROOT))] = n
    return out


def test_flat_kernel_calls_in_the_assembly_layer_never_grow():
    seen = _sites()
    grew = {k: (BASELINE.get(k, 0), v) for k, v in seen.items() if v > BASELINE.get(k, 0)}
    assert not grew, (
        "the assembly layer took on NEW flat kernel calls:\n  "
        + "\n  ".join(f"{k}: baseline {a} -> now {b}" for k, (a, b) in sorted(grew.items()))
        + "\n\nK-1: the document door is the kernel's only interface; a new capability is a "
          "code behind `fydoc.complete(...)`, not another flat export call. "
          "See FYL-DESIGN-16 §裁定 K-1 / K-3.")


def test_the_baseline_is_the_measurement_not_a_wish():
    seen = _sites()
    stale = sorted(k for k, v in BASELINE.items() if v > 0 and seen.get(k, 0) == 0)
    assert not stale, f"these files are clean now — drop them from BASELINE: {stale}"
    total_base, total_now = sum(BASELINE.values()), sum(seen.values())
    assert total_now <= total_base, (total_now, total_base)
