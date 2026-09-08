---
title: V-15 · g-file 读写往返与 COCOS 口径：本仓的读入端对本仓的写出端
---

# V-15 · g-file 读写往返与 COCOS 口径：本仓的读入端对本仓的写出端

| | |
| :--- | :--- |
| **类** | **V 验证** |
| **参考** | fylite |
| **对象** | fylite: io/geqdsk.py 的 read_geqdsk / write_geqdsk 与 measure_cocos |
| **算例** | —（无场景：局部或解析） |
| **数据** | 见 §5 表（2 项，纳入类别 experiment、public） |
| **门** | `python/tests/test_gfile_roundtrip.py::test_every_number_survives_the_round_trip`；`python/tests/test_gfile_roundtrip.py::test_the_first_line_is_an_invariant`；`python/tests/test_gfile_roundtrip.py::test_the_cocos_measurement_does_not_move` |
| **登记册结论** | 成立（`assertion_state: accepted`） |
| **复测** | 2026-09-08：成立——6 passed, 0 failed, 0 error, 0 skipped, 0 stale |

> 本页由 `tools/benchmark-publish.py` 从内核仓登记册渲染；判据与量到的数是登记册的，「复测」一行是发布当日在私仓检出上把门跑一遍的结果，两者分开记。

## 1. 判据

| 量 | 范数 | 容差 | 容差来源 | 备注 |
| :--- | :--- | ---: | :--- | :--- |
| 往返后逐字段（26 个数值字段，两份语料） | relative | 1e-09 | machine_precision | 读—写—再读的不动点是恒等式，不是物理，故取机器精度 |
| 头一行（EFIT 头，`(a48,3i4)`） |  | — | machine_precision | ★分开判，不并进「逐字段」那一条：数值一直是对的，只有这一行不是。并成一条会让「26 个字段全对」把唯一的缺陷盖住 |
| COCOS 标签与符号往返不变 |  | — | machine_precision | 标签是离散值，判等不判带 |

## 2. 口径对齐与不可比的部分

四行表（解了哪几道方程 / 哪些量是喂进去的 / 单位与径向标签 / COCOS）的完整账在该组算例书随件的 README（`$FYLITE_KERNEL/tests/data/FYDOC-CASE-12-synthetic/FYDOC-CASE-12-synthetic.md`）；下面是登记册随本条记录携带的口径说明，逐条照录：

- ★这是 V 类：两端是同一个实现的两个方向，量的是恒等式还成不成立，不是两个码谁更接近真实
- （判据）读—写—再读的不动点是恒等式，不是物理，故取机器精度
- （判据）★分开判，不并进「逐字段」那一条：数值一直是对的，只有这一行不是。并成一条会让「26 个字段全对」把唯一的缺陷盖住
- （判据）标签是离散值，判等不判带

## 3. 结果（登记册所记）

| 项 | 偏差 | 种类 | 判 | 备注 |
| :--- | ---: | :--- | :--- | :--- |
| 26 个数值字段，两份语料 | 0.0（逐位相同） |  | 成立 |  |
| ★★头一行：一条自己声明的不变量被自己的写入端改掉 | EAST `g070754.05000` 的 `… 5000ms           3 129 129` 往返后成 `… 0 129 129` |  | 不成立 | ★★写入端把 EFIT 头的 `idum` 写死为 0，而本仓 `io/geqdsk.py` 自己的字段表把 `header` 记作 **invariant**「the file's own first line」——**改掉了，且没有任何一处报错**。已修：整行原样带回，`nw`/`nh` 仍按数组实际长度写（那两个不是注记，是后面每一块的形状）；★★**判据能不能抓住，是实测过的**：把写入端改回旧写法，这一条当场判负（1 failed / 5 passed），改回来即全绿 |
| COCOS 口径 | 往返不变（标签与符号逐项相同） |  | 成立 |  |

## 4. 复测（2026-09-08）

| 门 | 计数 | 首条信息 |
| :--- | :--- | :--- |
| python/tests/test_gfile_roundtrip.py::test_every_number_survives_the_round_trip | 2 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_gfile_roundtrip.py::test_the_first_line_is_an_invariant | 2 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |
| python/tests/test_gfile_roundtrip.py::test_the_cocos_measurement_does_not_move | 2 过 / 0 败 / 0 错 / 0 跳 / 0 陈旧 |  |

结论：**成立**（`re-run`）。

## 5. 数据与怎么重跑

| 存储项 | 校验 | 纳入类别 | 规模 |
| :--- | :--- | :--- | :--- |
| $FYLITE_KERNEL/tests/data/FYDOC-CASE-12-synthetic/corpus/g_synthetic.geqdsk | sha256:36abf675b548df8316e6073debf9631180a8651348deb6cf544df0c2894ad3c9 | public | 80133 B |
| $FYDOC/cases/FYDOC-CASE-19-east-efit/corpus/g070754.05000 | — | experiment |  |

参考侧：按上表的出处取得同一份（受限类别的项读者须自备）。语料自 2026-09-05 起**随内核仓检出**（`$FYLITE_KERNEL/tests/data/`），不再是指向别处的挂载。
本仓侧：门在 `$FYLITE_KERNEL`（私仓）中运行——

```bash
cd $FYLITE_KERNEL   # 语料已在检出里，无需挂载
PYTHONPATH=$FYLITE_PUBLIC/python FYLITE_KERNEL_LIB=rust/fylite/target/release/libfylite_kernel.so \
  uv run --no-project --with pytest --with numpy --with scipy --with h5py \
  python -m pytest python/tests/test_gfile_roundtrip.py::test_every_number_survives_the_round_trip python/tests/test_gfile_roundtrip.py::test_the_first_line_is_an_invariant python/tests/test_gfile_roundtrip.py::test_the_cocos_measurement_does_not_move
```

## 6. 结论

登记册：成立。复测 2026-09-08：成立。只回答本条自己那一类（V 验证）的问题，不外推。
