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

## 命令行

装上包就有 `fylite`（`python -m fylite` 是同一个入口）。命令分两类：

```bash
fylite --help                       # 全部命令
# —— 这个宿主自己实现的 ——
fylite run --east --shot 70754 --time 3.5   # 一次平衡反演
fylite plot g137985.04000 -o flux.png       # 画一份 g-file 的磁面图
fylite describe                             # 能力目录，JSON-LD 形式
fylite cases --check                        # 算例语料；--report 出一份算例报告
fylite report <run>  ·  whence <文件>  ·  alias <run> <名字>   # 记录：渲染 / 溯源 / 起名
fylite manifest  ·  serve  ·  mcp           # 清单校验 / JSON-RPC / MCP（后两者走 stdio）
# —— 由本机可执行文件承载、这里逐字转交的（三条，同一个可执行文件）——
fylite app --page model --lang en           # 起本机服务并开浏览器
fylite data info shot.h5  ·  fylite data convert a.json b.nc   # 数据层
fylite case run plan.jsonld -o rec/         # 一份计划进、一份记录出
```

逐条参数与它们各自的动词见参考篇的[命令行](../reference/cli.md)；按任务走一遍见
[命令行](cli.md)那一章。

`describe` 出的是**机器可读的能力目录**：有哪些入口、各要什么、各给什么。
它也是把 fylite 接进别的工具（含 AI 工具链）时读的那一份。

:::{note} 后三条为什么是「转交」
`app` / `data` / `case` 的实现在**一个** Rust 可执行文件里（`fylite`，本仓只有这一个），
Python 侧**不重写第二份**：它找到随包带的那个可执行文件（或 `--bin-dir`、`$PATH`），
把命令词放回最前面，其余的字原样交过去。没找到时它**按名说明要构建什么**并以退出码 2
结束，而不是退化成一个能力更少的实现。
`fylite data --help` 与 `fylite data --help` 读到的是同一份用法——两边由同一个定义
文件建出。
:::

## 与浏览器互通

浏览器页面导出的会话文件可以在 Python 里加载并继续；反过来，Python 算出的结果
也能交给页面呈现。两边跑的是同一个内核，所以这不是「对得上」，是同一个数。
