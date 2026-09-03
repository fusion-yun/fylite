---
title: 数据层 (The Data Layer · `fylite data`)
---

# 数据层

**内核只算数，取数与格式归这一层。** 它把不同来路的数据读成 fyo 文档、把 fyo 文档写成
别的格式、合并多个来源，并按一份装配文档把它们拼成一份；物理一行没有。

一份 Rust 源（`rust/fylite_engine/`，**源码公开**——这里是协议编解码与文件格式，不是物理），
三个面：命令行 `fylite data …`、Python 的 `fylite.io.fydoc`、以及供本仓 Rust 宿主用的
库 API。三个面调用同一份代码，所以命令行能做的 Python 都能做，反之亦然。

本页讲**它能做什么、怎么用**。每条选择背后的理由（为什么文件类型看内容而不看扩展名、
为什么 HDF5 的数据轴要转置、「IMAS 兼容」的判据是什么）在设计集的 `FYL-DESIGN-14`。

## 它认得哪些数据源

| 数据源 | 读 | 写 | 可写成哪种布局 |
| :--- | :-: | :-: | :--- |
| MDSplus（mdsip 协议） | ✓ | ✗ | — （**只读，由构造保证**） |
| fydata 装置 A-Box（YAML） | ✓ | ✗ | — |
| EFIT g-file | ✓ | ✓ | fyo |
| EFIT a-file | ✓ | ✗ | — |
| JSON / JSON-LD | ✓ | ✓ | fyo · IMAS |
| HDF5 | ✓ | ✓ | fyo · IMAS |
| netCDF | ✓ | ✓ | fyo · IMAS |

**两种布局，一棵树。** 「fyo 布局」是本仓的文档形（`@context` / `@id` / `@type` 语义键 +
IMAS DD 的键名 + `fylite:` 本地词）；「IMAS 布局」是 **imas-python / imas-core 原样读得回**
的形。中间是一棵与格式无关的树，所以 N 种格式是 2N 条转换而不是 N²，合并与筛选只在树上
做一次。

:::{note}
「IMAS 兼容」在这里是**量出来的**，不是声明的：`verify/imas_roundtrip.py` 让 imas-python
造一份参考数据 → 本层写出 IMAS netCDF 与 IMAS HDF5 → 本层读回逐叶子比 → imas-python /
imas-core 读回逐叶子比 → 过 imas-python 的 `nc_validate`。IMAS 布局的维名、坐标与块大小
取自 DD 的 `IDSDef.xml` 生成表（82 个 IDS，随仓提交；当前 **DD 4.1.1**，`fylite data tables`
打印），不是从 fyo 的 schema 推的。
:::

## 七条子命令

```bash
fylite data info     <file>                       # 这是什么文件
fylite data dump     <file> [--ids A] [--path P]  # 打印一棵子树（JSON）
fylite data convert  <in> <out> [--to F] [--layout fyo|imas]
fylite data merge    <in>... -o <out>             # 多份合成一份
fylite data assemble <assembly> -o <out>          # 按一份装配文档取多个源
fylite data fetch    --machine <machine.yaml> --ids A,B --shot N -o <out>
fylite data tables                                # 内置 DD 表：版本与 IDS 名
```

★与 `fylite-app data …` 是同一条命令：**只有一个可执行文件**，Python 侧的 `fylite`
把命令词原样交给它（见[命令行](cli.md)）。

### `info` —— 这是什么文件

```bash
$ fylite data info cases/evolve-default.jsonld
cases/evolve-default.jsonld: json (fyo layout)
```

文件里带 IDS 文档时，每个 IDS 连同它的 occurrence、叶子数与前四十条叶子一并列出；
`--json` 是同一份答案的机器可读形。

**类型看内容，扩展名只作备选**——这不是洁癖：g-file 根本没有扩展名（`g063982.04800`）、
IMAS HDF5 是**一个目录**、而 netCDF-4 本身就是 HDF5（同一个魔数）。

### `dump` —— 打印一棵子树

```bash
fylite data dump shot.h5 --ids equilibrium --path equilibrium/time_slice/profiles_1d/psi
fylite data dump fydata/machine/tokamak/east/machine.yaml --raw   # 不是文档的 JSON/YAML
```

取值路径是 `"<ids>[_<occ>]/a/b/c"`：头一段是 IDS，其余是文档路径，不带索引的名字段落到
结构数组的第 0 个——与内核取值用的是同一条规则。`--raw` 打印解析出来的原树，给**不是
fyo 文档**的 JSON / YAML 用（装置清单、装配文档），也是 YAML 读者的核对入口。

### `convert` / `merge` —— 换格式、合成

```bash
fylite data convert g063982.04800 shot.nc --layout imas    # imas-python 打得开
fylite data convert shot.nc out/ --to imas-hdf5            # 一个 IMAS 数据入口（目录）
fylite data merge machine.h5 shot.nc -o all.jsonld         # 后者覆盖前者
```

`--to` 取 `json` / `geqdsk` / `hdf5` / `netcdf` / `imas-hdf5`，不给时按输出扩展名定；
`--layout` 取 `fyo`（缺省）或 `imas`。

★**合并时结构数组按 `name` 对齐**（`--merge-key`，缺省 `name`，`none` 表示按下标）。
几何一份、测量一份、来路不同而次序未必相同，按值对齐才不会把第 7 号探针的位置安到
第 9 号身上；两边任一边没有该键时退回按下标。`--keep` 让先到的值胜出。

★**fyo → IMAS 是一次归一化，而且它报告丢了什么**：语义键、`fylite:` 本地词、DD 不认的
路径会被丢掉，丢掉的都记在报告里由命令行与 Python 一并转述——不是静默截断。

### `assemble` / `fetch` —— 一次取回一发炮

`assemble` 按一份 JSON-LD / YAML 装配文档取多个源并拼成一份；`fetch` 是它的常用捷径——
把 fydata 的装置清单摊成「几何 + MDSplus 绑定」，再取指定的 IDS：

```bash
fylite data fetch --machine fydata/machine/tokamak/east/machine.yaml \
                  --ids magnetics --shot 138569 --time 4:5 \
                  --host 127.0.0.1 --port 8000 -o east_138569_magnetics.json
```

出来的是一份 `fyo:magnetics`：`b_field_pol_probe[n].field.{data, time}` 是 4–5 s 的切片，
`position` 来自几何，`fylite:assembly` 记下炮号、时间窗与每个源。`--dry-run` 只打印
「会取哪台机器的哪些源、选了什么」然后停在任何一次读之前。

**`--time` 三种写法**，`assemble` 与 `fetch` 通用：

| 写法 | 含义 |
| :--- | :--- |
| `4.5` | 一个时间点 |
| `4:5` | 一个窗 `[4, 5]` |
| `4,4.5,5` | 一列点 |

★**切片在服务端做，不是取回来再切。** 时间不是 TDI 表达式：先读节点时基（一炮里一个
节点只过网一次），在时基上查出下标，再以整数区间发出——整条信号不过网。`--max-points`
给窗内的采样点数封顶（按步长抽稀）。

★**点不外推**：窗里没有样本是**失败**，不是一个空数组。

:::{important}
**MDSplus 只读是由构造保证的，不是由纪律保证的。** 客户端只认「动词 + 节点路径 + 整数」，
没有表达式端点；装配文档里的 `$link` 表达式先被分解成这三样才发得出去，分解不了的
（下标读另一个节点、未知动词、`getenv(...)`）**列在失败里，不猜也不发**。
:::

### `tables` —— 内置的 DD 表

```bash
$ fylite data tables
DD 4.1.1
  amns_data
  b_field_non_axisymmetric
  ...
```

## Python 面

同一份代码的另一头，`fylite.io.fydoc`：

```python
from fylite.io import fydoc

kind, layout = fydoc.detect("shot.nc")            # ('netcdf', 'imas')
b = fydoc.read("g063982.04800")                   # -> Bundle（按 IDS 取子文档）
fydoc.write(b, "shot.h5", layout="imas")
doc = fydoc.fetch("machine.yaml", "magnetics", shot=138569, time=(4.0, 5.0))
```

`Bundle` 按 IDS 取子文档，取值路径与命令行的 `--path` 同一条规则。归一化报告随返回值
一同交出，不静默。

## 它不做什么

- **不写 MDSplus。** 见上：只读是构造性的。
- **不算物理。** 一个数都不产生——产生数的是内核，本层只搬运与转换。
- **复数叶子**（DD `CPX_*`）不写 IMAS 布局：**拒绝**而不是猜（`FYL-DESIGN-14` G-1）。
- **文件侧不做时间片增量**：imas-core 的 `put_slice` / `get_slice` 不实现，整份读写；
  按时间开窗只在 MDSplus 那条路上（G-3）。

## 相关

- [命令行](cli.md) —— 十四条命令的全表与「谁承载哪一条」
- [API 速查](api.md) —— `fylite.io.*` 在模块地图里的位置
- 设计集 `FYL-DESIGN-14`（数据层的裁定 L-1…L-12）、`FYL-DESIGN-15`（一份规格三个宿主）
