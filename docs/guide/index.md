---
title: 怎么开始 (Getting Started)
---

# 怎么开始

本篇讲**怎么用**与**结果怎么读**。fylite 是什么、本书分几部分，见[封面](../INDEX.md)。

## 三种发布形态，装哪一种取决于你手边有什么

:::{list-table}
:header-rows: 1

* - 形态
  - 要装什么
  - 适合
* - [浏览器站点](browser.md)
  - 什么都不用装
  - 上手、教学、快速试算、把一次运行分享给别人
* - [单一可执行文件](browser.md) `fylite-app`
  - 一个文件，双击即用；不装任何运行时
  - 离线、没有 Python 的机器（尤其 Windows）、要从 MDSplus 取数
* - [Python 包](python.md)
  - `pip install fylite`（alpha 期仅 Linux x86-64）
  - 脚本化、批量、把结果接进自己的分析流程
:::

三者装的是**同一份页面**与**同一版内核制品**，命令行也由同一个定义文件建出——
所以三条路上同名的命令是同一条命令（见[安装与环境](install.md)的分发面一节）。

★**两条路径调用的是同一个内核**：同一份 `c_api` 导出面，原生库与 WebAssembly
模块出自同一次编译配置。所以浏览器里得到的数与脚本里得到的数是同一个数——这一点由
自动门在每次改动时校验，不靠承诺。

## 往下读

- 先跑起来：[快速上手](quickstart.md) → [浏览器用法](browser.md) 或
  [Python 用法](python.md)。
- 想知道一个结果该怎么信：[结果怎么读](reading-results.md)、
  [能力与边界](limits.md)。
- 要一条能照抄的完整路径：[算例语料](../examples/index.md)以及它下面的五族典型算例——
  每章的命令与数字都是在本仓实测的。
