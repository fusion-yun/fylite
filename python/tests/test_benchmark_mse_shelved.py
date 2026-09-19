"""FR-EQ-007 · FR-EQ-009（MSE）的门：钉住「搁置」这条裁定的前提（register record `eq-reconstruct-mse-shelved`）。

★★用户 2026-09-17 裁定「搁置 MSE」。这里不验 MSE（它不存在），验的是**裁定所依据的事实仍然成立**：
内核里没有任何 MSE 响应行。一旦有人加了，这道门就红——那时这条裁定该重看，而不是被悄悄绕过。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

KERNEL_SRC = Path(__file__).resolve().parents[3] / "fylite_kernel" / "rust" / "fylite" / "src"


def test_the_kernel_still_has_no_mse_response_row():
    if not KERNEL_SRC.is_dir():
        pytest.skip(f"no kernel checkout next to this one ({KERNEL_SRC})")
    pat = re.compile(r"\bmse\b|motional|pitch_angle", re.IGNORECASE)
    hits = [f"{p.name}:{i + 1}" for p in sorted(KERNEL_SRC.glob("*.rs"))
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()) if pat.search(line)]
    assert hits == [], f"MSE 出现在内核里了——FR-EQ-007/009 的搁置裁定该重看：{hits[:10]}"
