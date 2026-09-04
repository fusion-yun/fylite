# 物理校验批：统计

- 日期 (recorded)：2026-09-04
- 算例 (cases)：7，其中没有产出可判的 2
- 检查 (checks)：88 条，评了 24 条，未通过 1 条

- 逐算例判决：通过 4 · 有条件 0 · 未通过 1 · 未评估 2

## 逐算例

| 算例 | 判决 | 通过 | 有条件 | 未通过 | 未评估 | 说明 |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| `evolve-default` | 通过 | 6 | 0 | 0 | 6 | 本批现跑了这个算例（数据层 JSON 门 + 内核） |
| `evolve-iter-15ma` | 通过 | 7 | 0 | 0 | 6 | 本批现跑了这个算例（数据层 JSON 门 + 内核） |
| `evolve-east-hmode` | 未评估 | 0 | 0 | 0 | 13 | the kernel rejected the case: refused: [-33] this case is outside the sunk scope of `evolve_heat`; it needs th |
| `transport-iter-15ma` | 通过 | 3 | 0 | 0 | 10 | 本批现跑了这个算例（数据层 JSON 门 + 内核） |
| `zerod-iter-15ma` | 未通过 | 3 | 0 | 1 | 9 | 本批现跑了这个算例（数据层 JSON 门 + 内核） |
| `discharge-iter` | 未评估 | 0 | 0 | 0 | 12 | the kernel rejected the case: refused: [-30] no code `code/discharge`: the kernel completes `code/evolve` / `c |
| `equilibrium-gfile` | 通过 | 4 | 0 | 0 | 8 | 判的是盘上的产出文件（g_synthetic.geqdsk），不是本批跑出来的 |

## 逐检查

| 检查 | 类 | 通过 | 有条件 | 未通过 | 未评估 |
| :--- | :--- | ---: | ---: | ---: | ---: |
| `finite` | 定律 | 4 | 0 | 1 | 2 |
| `positive-temperature` | 定律 | 4 | 0 | 0 | 3 |
| `positive-density` | 定律 | 3 | 0 | 0 | 4 |
| `grad-shafranov` | 定律 | 1 | 0 | 0 | 6 |
| `grid-monotone` | 定义 | 3 | 0 | 0 | 4 |
| `psi-endpoints` | 定义 | 1 | 0 | 0 | 6 |
| `volume-monotone` | 定义 | 3 | 0 | 0 | 4 |
| `boundary-closed` | 定义 | 3 | 0 | 0 | 4 |
| `pressure-consistency` | 定义 | 0 | 0 | 0 | 7 |
| `energy-balance` | 定义 | 0 | 0 | 0 | 7 |
| `greenwald-definition` | 定义 | 0 | 0 | 0 | 7 |
| `beta-normalized-definition` | 定义 | 0 | 0 | 0 | 7 |
| `declared-bounds` | 期望 | 1 | 0 | 0 | 2 |
| `steady-state` | 期望 | 0 | 0 | 0 | 1 |

## 怎么复算

```bash
# 一条：读一份已经跑出来的记录，只做判决（不需要内核）
python tools/benchmark-run.py --from records/<run> --only <entry>

# 整批：现跑（需要 libfylite_kernel.so 与数据层 .so）
python tools/benchmark-run.py --write
```

★没有内核的检出里，现跑那条路**按名拒绝**，统计表把它记成「未评估」并写明缺的是哪一件——不拿任何别的算法顶上。
