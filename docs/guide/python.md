---
title: Python 用法 (Using the Python Package)
---

# Python 用法

## 安装

```bash
pip install fylite
```

硬依赖只有 `numpy`。其余是可选项，且**缺失时抛错并给出安装行**，不静默降级：

```bash
pip install 'fylite[plot,yaml]'
```

:::{important} alpha 期的分发面：Linux x86-64
包里带的是**预编译**的内核，pip 不在安装时编译它。所以轮带**平台标签**，
alpha 期公开的是 Linux x86-64 一个面——别的平台在**安装时**就被拒绝，
而不是装完之后在第一次内核调用时报错。

其他平台上想用，两条路：用[浏览器](browser.md)一路（无平台限制），
或者从源码自行构建。
:::

## 三行开始

```python
from fylite import scenario as S

z = S.model.zerod()                     # 0 维放电，规定剖面
t = S.model.transport(power=4.0)        # 一步 1.5 维输运
f = S.analysis.profit(x, y, sigma_frac=0.05)   # 测量剖面拟合，GCV 定平滑
```

不需要装置描述、不需要炮号、不需要网络。确实需要装置的那些入口**显式**要一份——
经环境变量或直接把路径交给入口，不会偷偷去找。

## 命令行在别处

★★2026-09-04 起**本包没有命令行**：没有 `fylite` 控制台脚本，没有 `python -m fylite`。
装上它得到的是一个**库**——本章前面那些调用就是全部的用法。

机器上那一条命令行是 Rust 的 **`fy`**（`bash rust/build.sh --exe`），它承载 `app` /
`data` / `case` 三条；从前由 Python 承载的十一条动词都是库调用，逐条对照在
[命令行](cli.md)那一章的末节。两个常用的：

```python
from fylite.engine import manifest_catalog
manifest_catalog()          # 能力目录（JSON-LD）：有哪些入口、各要什么、各给什么

from fylite.engine.serve import mcp_stdio       # MCP stdio 服务器
raise SystemExit(mcp_stdio())                   # 宿主配置里写成一行 `python -c`
```

能力目录也是把 fylite 接进别的工具（含 AI 工具链）时读的那一份。

## 与浏览器互通

浏览器页面导出的会话文件可以在 Python 里加载并继续；反过来，Python 算出的结果
也能交给页面呈现。两边跑的是同一个内核，所以这不是「对得上」，是同一个数。
