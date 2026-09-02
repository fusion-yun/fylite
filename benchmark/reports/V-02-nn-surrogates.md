---
title: V-02 · 两个神经代理的求值，对上游自己的求值
---

# V-02 · 两个神经代理的求值，对上游自己的求值

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | TGLFNN.jl · 1.7.1 · Apache-2.0；EPEDNN.jl · delta_ne_sqrt_power · Apache-2.0 |
| **对象** | fylite: nn.rs + fylite.nn |
| **算例** | `scenario/iter-15ma-flattop`（ITER 15 MA 感应燃烧，平顶段） |
| **数据** | 见 §5 表（3 项，纳入类别 private-artefact、public） |
| **门** | `$FYLITE_KERNEL/tests/test_nn_surrogate.py` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-02：未评估——0 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 代理输出 | relative | 1e-09 | machine_precision |  |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在私仓账本（`$FYLITE_KERNEL/nn_tables/README.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★这条只说「我们和它算得一样」，不说「该信它」：该 TGLF-NN 模型（DIII-D 训练）在 ITER 的 rho>=0.75 两面出训练域
- 单成员不能替 ensemble：同面 Qe 的 20 个成员散布 1.93-8.09，标准差是均值的 34 %
- （场景）★这是一个准稳态窗口：参考自己的 T_e(0) 在 16 s 内只走 −5.2 %，「什么都不做」的全剖面 RMS 就是 4.07 %。任何模型跑完若不比这条线好，它什么也没说。
- （场景）参考侧只解电流与电子温度两条方程；T_i 与 n_e 是给定的（见各 record 的 prescribes）。

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| TGLF-NN 4 通道 x 7 面 | 4.9e-14 |  | 成立 |  |
| EPED-NN 统一路径 vs 编译路径 (18 个数) | 0.0 |  | 成立 |  |

## 4. 复测（2026-09-02）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/test_nn_surrogate.py | 未执行 |  |

结论：**未评估**（`re-run: gate not executed`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYLITE_KERNEL/nn_tables/sat2_em_d3d_azf-1.npz | — | private-artefact |  |
| $FYLITE_KERNEL/nn_tables/epednn.npz | — | private-artefact |  |
| $FYDATA_ORACLE/fuse/iter_tglfnn.json | sha256:d3364500b9512a11f34e3280e2063fee8cf77bc1b19c7d291f9e09e5bb438662 | public | 1477 B |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备；`$FYDATA_ORACLE` 是 fydata 仓的 `oracle/` 树，本仓与内核仓都以 `tests/data -> …/fydata/oracle` 挂载）。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL && ln -s ../../fydata/oracle tests/data
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest tests/test_nn_surrogate.py
```

## 6. 结论

登记册：成立。复测 2026-09-02：未评估。只回答本条自己那一类（V 验证）的问题，不外推。
