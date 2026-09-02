# fylite 物理校验 (Physics checks)

〔一句话〕**预设算例跑一遍，逐条量它满不满足物理定律、文档自己的定义，和算例声明的期望**——统计表在这里，逐条报告在 [`benchmark/physics/`](benchmark/physics/)。

这与公开 V&V 登记册（[`benchmark/`](benchmark/)）是**两个册子**，问题不同，别混着读：

| 册子 | 问的是 | 参考是什么 |
| :--- | :--- | :--- |
| [`benchmark/registry.jsonld`](benchmark/registry.jsonld) | 对着**外部答案**量到多少 | 另一个码、解析解、实验 |
| [`benchmark/physics/`](benchmark/physics/) （本表） | 这份产出**自洽吗** | 物理定律与文档自身的定义 |

- 日期 (recorded)：2026-09-02
- 算例 (cases)：7，其中没有产出可判的 6
- 检查 (checks)：12 条，评了 4 条，未通过 0 条

- 逐算例判决：通过 1 · 有条件 0 · 未通过 0 · 未评估 6

## 逐算例

| 算例 | 判决 | 通过 | 有条件 | 未通过 | 未评估 | 说明 |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| `evolve-default` | 未评估 | 0 | 0 | 0 | 0 | the case could not be run: KernelError: fylite_data_case_json returned -4: no kernel library with the fyo door |
| `evolve-iter-15ma` | 未评估 | 0 | 0 | 0 | 0 | the case could not be run: KernelError: fylite_data_case_json returned -4: no kernel library with the fyo door |
| `evolve-east-hmode` | 未评估 | 0 | 0 | 0 | 0 | the case could not be run: KernelError: fylite_data_case_json returned -4: no kernel library with the fyo door |
| `transport-iter-15ma` | 未评估 | 0 | 0 | 0 | 0 | the case could not be run: KernelError: fylite_data_case_json returned -4: no kernel library with the fyo door |
| `zerod-iter-15ma` | 未评估 | 0 | 0 | 0 | 0 | the case could not be run: KernelError: fylite_data_case_json returned -4: no kernel library with the fyo door |
| `discharge-iter` | 未评估 | 0 | 0 | 0 | 0 | the case could not be run: KernelError: fylite_data_case_json returned -4: no kernel library with the fyo door |
| `equilibrium-gfile` | 通过 | 4 | 0 | 0 | 8 | 判的是盘上的产出文件（g_synthetic.geqdsk），不是本批跑出来的 |

## 逐检查

| 检查 | 类 | 通过 | 有条件 | 未通过 | 未评估 |
| :--- | :--- | ---: | ---: | ---: | ---: |
| `finite` | 定律 | 1 | 0 | 0 | 0 |
| `positive-temperature` | 定律 | 0 | 0 | 0 | 1 |
| `positive-density` | 定律 | 0 | 0 | 0 | 1 |
| `grad-shafranov` | 定律 | 1 | 0 | 0 | 0 |
| `grid-monotone` | 定义 | 0 | 0 | 0 | 1 |
| `psi-endpoints` | 定义 | 1 | 0 | 0 | 0 |
| `volume-monotone` | 定义 | 0 | 0 | 0 | 1 |
| `boundary-closed` | 定义 | 1 | 0 | 0 | 0 |
| `pressure-consistency` | 定义 | 0 | 0 | 0 | 1 |
| `energy-balance` | 定义 | 0 | 0 | 0 | 1 |
| `greenwald-definition` | 定义 | 0 | 0 | 0 | 1 |
| `beta-normalized-definition` | 定义 | 0 | 0 | 0 | 1 |

## 怎么复算

```bash
# 一条：读一份已经跑出来的记录，只做判决（不需要内核）
python tools/benchmark-run.py --from records/<run> --only <entry>

# 整批：现跑（需要 libfylite_kernel.so 与数据层 .so）
python tools/benchmark-run.py --write
```

★没有内核的检出里，现跑那条路**按名拒绝**，统计表把它记成「未评估」并写明缺的是哪一件——不拿任何别的算法顶上。
