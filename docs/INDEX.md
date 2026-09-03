---
title: fylite 文档 (fylite Documentation)
---

# fylite 文档

fylite 是一个**自足的托卡马克平衡—输运—湍流内核**：一套 Grad-Shafranov 正逆解、
一步 1.5 维芯部输运、新经典与回旋朗道流体闭包，以及一条平衡重构链，写成**一个可
重入的 Rust 内核**；Python 层做装配与编排，浏览器端跑的是同一个内核编译出的
WebAssembly。三种发布形态跑的是同一份算术。

本书**一本四篇**。它们回答四个不同的问题，顺序就是读者一路问下去的顺序：

| 篇 | 回答什么 | 读者 |
| :--- | :--- | :--- |
| [用户指南](guide/index.md) | **怎么用**，以及**结果怎么读** | 拿它算东西的人 |
| [参考](reference/fidelity.md) | 一个数**能不能用**：保真度边界、内核清单、调用面、判据与报告体例 | 要判断一个结果可不可信的人 |
| [物理与数值](physics/00-overview.md) | 那个数背后**是哪条方程、出自哪里、验到什么容差** | 要复核物理、或要移植它的人 |
| [设计集](design/INDEX.md) | 它**为什么长这样** | 要改它、或要把它接进别处的人 |

★**先读哪一篇**：没用过就从[用户指南](guide/index.md)进；手里已经有一个数、想知道
它可不可信，去[保真度边界](reference/fidelity.md)；要追到方程和文献，去
[物理与数值](physics/00-overview.md)；要接口去 [API](reference/api.md)，要接页面去
[设计集](design/INDEX.md)的 `FYL-SDD-01`。

## 三样在本书之外的东西

它们在仓里，但**不是本书的章**——各有各的理由，不是遗漏：

- `docs/benchmark/` —— **V&V 登记册与对拍报告**。它们是**按路径引用的记录**：门禁、
  CI 的底账校验、算例语料的 `account` 字段都写着 `docs/benchmark/…`，机器读的是
  `registry.jsonld`。一份被路径引用的记录要的是稳定路径，不是章节号。参考部分的
  [物理校验](reference/benchmark.md)一章讲它怎么用。
- `app/` 的**浏览器演示** —— 那是**产品**，不是本书的一章（2026-09-01 裁定）。讲它的
  说明页仍在书里（[浏览器演示](guide/browser-app.md)），链接给的是已发布站点的地址。
- `NOTICE` —— 逐文件的移植出处与修改说明，随 Rust 内核源码留在 `fylite_kernel`，
  打轮时装入分发件。可读的全表见本书的[致谢](ACKNOWLEDGEMENTS.md)。

## 文档编号与引用

设计集里的文档按 **`document_id`** 指认（`FYL-CONOPS-00`、`FYL-SRS-01`、`FYL-SDD-01`、
`FYL-DESIGN-NN`），路径经 [`design/INDEX.md`](design/INDEX.md) 那张表解析——
**不要在别处硬编码文档路径**。指南与参考两部分按文件名引用即可。

## 构建

```bash
cd docs && myst build --html     # 全书
myst start                       # 本地预览
myst build --strict              # 把警告当错误
```

★**一本书，一个目录源**：`docs/myst.yml` 的 `toc` 是唯一的目录。2026-09-02 之前这里
是三本独立的书（各自 `myst.yml`）挂成一个站点；那个形制下站点根上没有页面，本页
无处可放。`guide/public.yml` 不是第二个目录——它点名的是「哪几篇随浏览器演示公开
发布」，另由 `tools/build-guide.sh` 读。
