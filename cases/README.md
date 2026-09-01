# `cases/` — 公开算例

一个**算例**就是一份**会话文档**：演示页「导出 → 会话文件」写出来的那个形状，
一字不差。把算例喂回页面走的是与导入同一条路（`FySession.apply`）。

A **case** is a **session document** — byte-for-byte the shape the demo's
"export → session file" writes. Applying one goes through the same code path
as importing your own file.

两条因此成立：

- 你自己跑一次、存下来，那就是一个算例——没有第二种格式；
- 算例**不可能漂移**成只有菜单读得懂的东西。

★**算例只装输入，不装结果。** 它是一组输入，页面仍然要自己算一遍。一份带着
答案的「算例」没法证明任何事——读者无从知道那个答案是不是这组输入算出来的。

## 目录

| | |
| :--- | :--- |
| [`catalogue.jsonld`](catalogue.jsonld) | 算例目录：id、文档、挂在哪条功能栏、次序 |
| `<case-id>.jsonld` | 算例文档本体（会话文档） |

## 怎么跑

在 <https://fusion-yun.github.io/fylite/> 打开对应场景页，从功能栏的算例下拉里
选；或者把 `.jsonld` 文件直接拖进页面。**不上传**——一切都在你自己的浏览器里。

## 怎么贡献一个

1. 在演示页把输入调到你要的样子，**导出会话文件**；
2. 确认它只有输入（导出本来就不带结果）；
3. 开一个 issue，附上文件，说明这个算例**回答什么问题**——一个不说明用途的
   算例进不来，因为没人知道它变红时意味着什么。

★算例里不要放**受限或未授权**的装置数据与实验炮。判据与
[`../benchmark/README.md`](../benchmark/README.md) 同一条：**读者能不能自己
把它重新取得一遍**。

## 与 `benchmark/` 的分工

`cases/` 是**输入**；`benchmark/` 是**对着外部答案量出来的判定**。一条登记册
记录可以指向这里的某个算例作为它的 `scenario`，反过来不成立——算例自己不作
任何断言。
