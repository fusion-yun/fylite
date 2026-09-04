# 缺省演化：一次 1.5-D 输运推进的自洽性

- 算例 (case)：`cases/evolve-default`
- 判决 (verdict)：**未评估**（unevaluated）
- 产出 (datasets)：—
- 记录 (record)：`—`
- 日期：2026-09-02

## 没有产出

本条**没有可判的产出**：the case could not be run: KernelError: fylite_data_case_json returned -4: no kernel library with the fyo door found; looked at:
  /home/user/fylite/python/fylite/_lib/libfylite_kernel.so (absent)
  /home/user/fylite/../python/fylite/_lib/libfylite_kernel.so (absent)
  /home/user/fylite/../../python/fylite/_lib/libfylite_kernel.so (absent)
  /usr/bin/python/fylite/_lib/libfylite_kernel.so (absent)
  /usr/bin/libfylite_kernel.so (absent)
  /usr/python/fylite/_lib/libfylite_kernel.so (absent)
  /usr/libfylite_kernel.so (absent)
  /python/fylite/_lib/libfylite_kernel.so (absent)
  /libfylite_kernel.so (absent)
  /home/user/fylite/../fylite_kernel/rust/fylite/target/release/libfylite_kernel.so (absent)
  /home/user/fylite/../fylite_kernel/rust/fylite/target/debug/libfylite_kernel.so (absent)
  /home/user/fylite/../../fylite_kernel/rust/fylite/target/release/libfylite_kernel.so (absent)
  /home/user/fylite/../../fylite_kernel/rust/fylite/target/debug/libfylite_kernel.so (absent)
  /home/user/fylite/../../../fylite_kernel/rust/fylite/target/release/libfylite_kernel.so (absent)
  /home/user/fylite/../../../fylite_kernel/rust/fylite/target/debug/libfylite_kernel.so (absent)
(pass --kernel <path>, set FYLITE_KERNEL_LIB, or build it with the kernel's rust/build.sh)

★这不是「通过」也不是「未通过」——判决是 `unevaluated`，统计表把它单列。

---

本报告由 `tools/benchmark-run.py` 渲染（判据册 `fylite.engine.physics`）；机器可读的一份在同名 `.jsonld` 里。
