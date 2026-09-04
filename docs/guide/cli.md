---
title: 命令行 (Using the Command Line)
---

# 命令行

命令行只有一个，它叫 **`fy`**，是本仓 Rust 中间层的产物：

```bash
bash rust/build.sh --exe          # -> rust/fylite_runtime/target/release/fy
fy --help
```

它承载三条命令词——`app`（起浏览器演示）、`data`（数据层）、`case`（一份计划进、
一份记录出，直通内核）。不带命令词时它跑 `app`，所以双击也可用。逐条参数的全表在
参考篇的[命令行](../reference/cli.md)。

:::{important}
**Python 包没有命令行**（2026-09-04 用户裁定）。`pip install fylite` 装的是一个**库**：
没有 `fylite` 这条控制台脚本，没有 `python -m fylite`，也没有 `engine/cli.py` 那一层。
从前由它承载的十一条动词并没有消失——它们是**库调用**，本页最后一节给出逐条的对照。
:::

## 换一份数据的格式，或取一发炮

数据层是一条命令词底下的八条子命令（另有组级 `--facts PATH`）：

```bash
fy data info    shot.h5                        # 这是什么文件
fy data convert g063982.04800 shot.nc --layout imas    # imas-python 打得开
fy data merge   machine.h5 shot.nc -o all.jsonld       # 后者覆盖前者
fy data fetch   --machine east --ids magnetics \
                --shot 138569 --time 4:5 -o east.json  # 取一发炮的磁测量
fy data facts                                  # 哪些语料在场、每条条目由谁供
```

它能读哪些源、两种布局分别是什么、`--time` 怎么写、为什么 MDSplus 是只读的——
参考篇的[数据层](../reference/data-layer.md)一页讲完。

## 不经 Python 跑一个算例

`fy case` 直通内核：一份 fyo 计划进，一份 fyo 记录出。

```bash
fy case run plan.jsonld --record rec/ --format jsonld
fy case json plan.jsonld            # 记录直接打到 stdout
```

★跑不成也**回一份记录**（`run_state: rejected`，缺什么写在 `comment` 里），而不是抛一个
异常：一份跑不了的计划必须说出它缺什么。

## 起浏览器演示

```bash
fy app                                   # 找一个空闲端口，起服务，开浏览器
fy app --port 8123 --no-open             # 只伺服
fy app --page data --device east --lang en --mdsip 127.0.0.1:8000
```

 