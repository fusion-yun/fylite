---
title: V-17 · 定边界 GS 算子与求解器：Solov'ev 精确解与制造解
---

# V-17 · 定边界 GS 算子与求解器：Solov'ev 精确解与制造解

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | Solov'ev 解析解 · ψ = (f/8) R⁴ + (g/2) Z² + c₂ R²（公开闭式） · public |
| **对象** | fylite: 内核 equilibrium.rs 的 Δ* 算子、Hockney 快速直接解法与定边界 Picard 迭代（经 C-ABI） |
| **数据** | 见 §5 表（0 项） |
| **门** | `$FYLITE_KERNEL/tests/test_rust_kernels.py::test_solovev_is_reproduced_through_the_abi`；`$FYLITE_KERNEL/tests/test_oracle_marshalling.py::test_the_deltastar_operator_returns_the_solovev_source`；`$FYLITE_KERNEL/rust/fylite/src/equilibrium.rs` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-15：成立——2 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由公开检出的 `tools/benchmark-equilibrium-records.py` 自登记册写出（2026-09-15 起平衡相关记录在本仓直写，不经内核仓的发布器）；判据与读数是登记册的，「复测」是写入当日把门跑一遍的结果。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| Solov'ev 精确解经 C-ABI 重现 |  | — | machine_precision | 解析解：本条是 verification，机器精度即判据 |
| Δ* 算子作用于 Solov'ev 解给出其源项 |  | — | machine_precision |  |
| 内核单元测试：Solov'ev 误差 33² 网格 < 1e-10、65² < 1e-9；制造解二阶收敛；算子与解法互逆；定边界 Picard 收敛并如实报告 |  | — | machine_precision | 这几条是内核 `cargo test` 的断言（`equilibrium.rs` 单元测试），阈值照录断言本身，本条未另测数值 |

## 2. 口径与说明

- ★这是 S1 干路上第一条**针对求解器本身**的登记记录：此前平衡正问题的 V 只在内核单元测试里，公开册看不见
- ★只覆盖定边界与解析 / 制造解；自由边界正问题的外部对照在 B-14
- 纳入类别（参考数据）：public（解析闭式）

## 3. 结果

| 项 | 读数 | 判 | 备注 |
| :--- | :--- | :--- | :--- |
| Solov'ev 经 C-ABI（`test_rust_kernels.py::test_solovev_is_reproduced_through_the_abi`） | 门通过（2026-09-15 只读复测） | 成立 |  |
| Δ* 作用于 Solov'ev（`test_oracle_marshalling.py::test_the_deltastar_operator_returns_the_solovev_source`） | 门通过（2026-09-15 只读复测） | 成立 |  |
| 内核 Rust 单元测试（`solovev_is_reproduced_to_machine_precision` · `manufactured_solution_converges_at_second_order` · `stencil_and_solver_are_mutually_inverse` · `fixed_boundary_picard_converges_and_reports_it`） | 本条写入时未跑：`cargo test` 会在内核检出里构建，而本轮裁定不动内核仓 | 未评估 |  |
| 复测 2026-09-15（本条写入时把门跑一遍） | 2 passed, 0 failed, 0 error, 0 skipped, 0 stale | 成立 | 内核检出里只读复测（不写字节码与缓存）；cargo 单元测试未跑 |

## 4. 不可比的部分

- 定边界、矩形盒、解析剖面：不含自由边界、限制器 / X 点边界搜索与测量拟合。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 |
| :--- | :--- | :--- |

受限与实验类只存路径与 sha256，本体不在公开仓；CASE-23 的发布判定是 `internal`。

```bash
cd $FYLITE_KERNEL   # 私仓
PYTHONPATH=$FYLITE_PUBLIC/python:tests FYLITE_KERNEL_LIB=rust/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy python -m pytest -p no:cacheprovider \
  tests/test_rust_kernels.py::test_solovev_is_reproduced_through_the_abi \
  tests/test_oracle_marshalling.py::test_the_deltastar_operator_returns_the_solovev_source
cargo test --manifest-path rust/fylite/Cargo.toml equilibrium::   # 单元测试（会在内核检出里构建）
```

## 6. 结论

成立（经 C-ABI 的两条门）：Δ* 算子与定边界求解在 Solov'ev 精确解上到机器精度。内核单元测试那一半本条写入时未跑，标未评估。
