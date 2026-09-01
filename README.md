# fylite

**自洽的托卡马克平衡 / 输运 / 湍流内核** —— Rust 计算核 + Python 装配层 +
WebAssembly 浏览器前端；运行期只依赖 `numpy`，不需要 Fortran、MPI、LAPACK
或任何系统数值库。

A self-contained tokamak equilibrium, transport and turbulence kernel —
Rust core, Python assembly layer, WebAssembly front end.

**本仓是 fylite 的发布面与反馈入口。** 源码目前不公开（见下「许可与源码」）。

---

## 在线演示 · Live demo

<https://fusion-yun.github.io/fylite/>

整个内核编译成 WebAssembly 在浏览器里跑，无需安装、不上传数据：平衡正解与
反演、1.5-D 输运推进、0-D 放电分析、击穿与垂直稳定性。

The whole kernel runs in the browser as WebAssembly — nothing to install,
nothing uploaded.

## 下载 · Downloads

发行制品挂在本仓的 **[Releases](../../releases)** 下。首个 Release 尚未发布；
在此之前，浏览器演示页承载的就是同一个内核。

Release artifacts are published under **[Releases](../../releases)**.
None yet — until then, the browser demo runs the same kernel.

## 报障与反馈 · Issues

**[提一个 issue](../../issues/new/choose)**。因为源码不公开，复现完全依赖你把
「跑的是哪一份二进制」说准，issue 模板里那三格（版本号 / 接口版本 ABI /
sha256）请务必填：

- **版本号**在演示页页脚；
- **接口版本**同一行，写作 `interface <N>` / `接口 <N>`；
- **sha256** 用 `sha256sum` 算你手上那份制品；浏览器演示可跳过此项。

Because the source is not published, reproducing a report depends entirely
on knowing **which binary** you ran. Please fill in the version / interface
(ABI) / sha256 fields in the template.

补丁与 PR：源码不在本仓，所以 PR 无处可合。请把问题写成 issue —— 定位与修复
在上游做，修好了随下一个 Release 出来。

## 验证记录与算例 · Evidence and cases

源码不公开，所以「我们测过了」这句话本身没有分量。能替代它的是**可复算的记录**：

- **[`benchmark/`](benchmark/)** —— 公开 V&V 登记册。对着外部答案量过什么、
  量到多少、哪一部分不可比。三类记录（**V 验证** / **B 对拍** / **C 确认**）
  不可互替，判据与可信度都不同；纳入判据是**读者能不能自己把参考侧重新取得
  一遍**。
- **[`cases/`](cases/)** —— 公开算例。一个算例是一份**会话文档**（演示页
  「导出」写出来的那个形状），**只装输入不装结果**，页面仍要自己算一遍。

两棵树目前都是**空骨架**：体例、词汇与模板已就位，记录逐条往里加。

Because the source is not published, the recomputable record is what carries
the weight. Both trees are **empty skeletons** for now — the conventions,
vocabulary and templates are in place; records land one at a time.

## 许可与源码 · Licence and source

制品按 **Apache License 2.0** 发布（见 [`LICENSE`](LICENSE) 与
[`NOTICE`](NOTICE)）。Apache-2.0 不要求分发者提供源码，因此**「按 Apache-2.0
发布二进制」与「源码仓当前不公开」两件事并不冲突**——你拿到的这份制品，其
Apache-2.0 权利是完整的。

Artifacts are released under the **Apache License 2.0**. Apache-2.0 does not
require a distributor to supply source, so "Apache-2.0 binaries" and "the
source repository is not currently public" are consistent: your rights in
the artifact you received are the full Apache-2.0 rights.

`NOTICE` 必须随任何再分发一起走（Apache-2.0 §4(d)），它里面逐项记着上游出处
——GACODE（GEO / NEO / TGLF / TGYRO，Apache-2.0）的署名义务由此承接。

**制品里没有什么**：受限的第三方物理码（EFIT 血统、GRAY、PENCIL / JINTRAC）
及一切由它们派生的构建产物都不在其中。

## 出处与致谢 · Credits

[`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md)（中文）/
[`ACKNOWLEDGEMENTS.en.md`](ACKNOWLEDGEMENTS.en.md)（English）逐项列出上游工作、
移植去向与「有意不取」的部分。维护者见 [`CONTRIBUTORS.md`](CONTRIBUTORS.md)。

Developed at the Institute of Plasma Physics, Chinese Academy of Sciences
(ASIPP).
