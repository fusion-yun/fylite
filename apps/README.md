# `apps/` —— 独立应用场景

一个目录一个场景：**拷走即可运行**的一套工具、页面与它的输入，建在 fylite 之上、但不属于
fylite 的包或站点。与仓里另外两处的分界：

| 目录 | 是什么 | 谁消费 |
| :--- | :--- | :--- |
| `webui/` | fylite 自己的浏览器前端（静态站点，内核跑在 WebAssembly 里；也整棵内嵌进 `fy app`） | 站点读者 · `fy app` |
| `docs/examples/` | 典型算例：计划文档 + 讲它的一章，经 `fy run` / Python 入口跑 | MyST 书的读者 |
| `apps/<场景>/` | **一个完整的应用场景**：自带模型工具、页面、输入与检查，只经动态库调 fylite | 这个场景的用户 |

## 规矩

- **只收源与输入，不收产物。** 动态库（`*.so`）与跑出来的数据（完整时序、结束状态、报告页、
  动画、IMAS 条目、复现运行的 CSV / 快照）**不入库**——每个场景的 README 写明它们怎么重新生成。
  `apps/.gitignore` 兜住常见的几类。
- **自成一体。** 场景内的脚本不写绝对路径、不引用场景目录之外的文件；要 fylite 的地方只经
  那份 `libfylite.so`（由本仓 `bash rust/build.sh --no-io` 出，见各场景 README）。
- **不进包、不进站点。** `python/fylite/` 不 import 这里的任何东西，`tools/build-site.sh` 也不发它们。

## 目录

| 场景 | 一句话 |
| :--- | :--- |
| [`cfedr-discharge-demo/`](cfedr-discharge-demo/README.md) | CFEDR d2025 15 MA 放电推演：单文件模型工具（`step` / 整炮）+ 单文件波形工作台页面 |
