---
title: 装置信息 (Device Information) —— 补全，并交付成 IMAS 数据入口
---

# 装置信息：补全，并交付成 IMAS 数据入口

前五章各算一段物理。这一章算的是**机器本身**：一台装置的描述进来，补全它只是隐含
给出的那一部分，再把整份交付成一个 **IMAS 数据入口**。以 EAST 为例，全程在命令行上，
**不联网**。

:::{note}
本仓**不带任何装置的清单文档**：`facts/device/<id>/` 里只有 `rights.json`，文档在 fydoc
（[命令行](../../guide/cli.md)那一节说明了为什么）。所以本章的装置文档由 `--bind` 从盘上
绑定，路径写作 `<装置文档>`——把它换成你自己那一份。
:::

## 一 · 牌里有什么

```console
$ fy data info <装置文档>
<装置文档>: json (fyo layout)
  ? (occurrence 0): 1959 leaves
    @type: "fylite:DeviceDescription/1"
    fylite:device_id: "east"
```

★读作：这是一份 **fylite 容器**，不是一个 IDS。它把 `tf` · `pf_active` · `wall` ·
`magnetics` · `lh_antennas` 五支**当作子树**装在一个屋顶下，另带 `fylite:channel_map`
`fylite:grid` 这些 DD 不认识的行。数据入口只装 IDS——第三节回到这一点。

## 二 · 补全：通道图由内核算

装置的**电路侧**在牌里只是隐含的。deck 给出每个线圈的元件与匝数；控制与反解要的是
BRSP **通道 → 元件**的稠密权重图。`code/channels` 把它算出来：

这一步没有现成的**场景**可用——语料收的是场景算例，而 `code/channels` 是一扇门，
没有对应的场景模板（`fy list scenarios` 里没有它）。所以计划直接写出来，四行：

```bash
cat > channels.jsonld <<'JSON'
{ "@context": {"fyo":"https://fusion-yun.github.io/fyo/latest/",
               "spo":"https://spdata.org/spo#"},
  "type": "fyo:ScenarioSpecification",
  "prescribes_code": {"id": "code/channels"},
  "inputs": [{"type": "spo:PortBinding",
              "binds_port": {"type": "spo:PortDefinition",
                             "port_name": "device", "port_direction": "input"}}] }
JSON

fy run channels.jsonld --bind device=<装置文档> -o rec/
```

★端口在计划里**只声明不绑定**，值由命令行的 `--bind` 给：同一份计划因此对任何一台
装置都成立，换机器只换那一个参数。

实测（2026-09-07，本仓检出 · 内核 ABI 152），`run_state: succeeded`：

| 文件 | 内容 | 字节 |
| :--- | :--- | ---: |
| `plan.jsonld` | 合成好的计划 | — |
| `record.jsonld` | 记录 | — |
| `entry.fyo.jsonld` | `weights`：**14 × 14** 的通道权重矩阵 | — |

★**这一族算例 2026-09-07 之前从命令行跑不起来**。`code/channels` 与其余十七个 code
一样吃**整份文档**，只经树门到达，而 `fy run` 走的是扁平门，于是按名拒绝
（`[-33] … is reached through the tree door only`）。现在两扇门都由这条命令走得到：
逐位对拍过——0-D · 输运 · 演化三档的每一份产出文档在两扇门下**逐字节相同**。

★答案落在 `entry` 里而不是某个 IDS 里，因为**权重矩阵在 DD 里没有家**。这不是缺陷，
是 DD 的边界：它记录线圈与元件的几何，不记录某台机器把哪几个元件接到同一个电源上。

## 三 · 交付：整份装置写成一个 IMAS 数据入口

```bash
fy data convert <装置文档> rec/imas --layout imas --to hdf5
```

实测产出——五个 IDS 加一份 master，共 161 KB：

| 文件 | 字节 |
| :--- | ---: |
| `master.h5`（外部链接指向下面五份） | 2 176 |
| `wall.h5` | 62 752 |
| `magnetics.h5` | 38 536 |
| `pf_active.h5` | 36 200 |
| `lh_antennas.h5` | 16 968 |
| `tf.h5` | 8 408 |

读得回来，且逐值相同：

```console
$ fy data info rec/imas
rec/imas: imas-hdf5 (imas layout)
  lh_antennas (occurrence 0): 9 leaves
  magnetics (occurrence 0): 426 leaves
  pf_active (occurrence 0): 103 leaves
  tf (occurrence 0): 7 leaves
  wall (occurrence 0): 188 leaves
$ fy data dump rec/imas --path pf_active/coil/0/element/0/geometry/rectangle/r --compact
0.62866
```

（源文档同一路径也是 `0.62866`。另两处抽查：`tf/r0` 1.75 · `magnetics/flux_loop/0/position/0/r`
1.2707，两边一致。）

### 这一步做了什么，没做什么

**做了**：把容器**拆成它装着的那几个 IDS**，每个写成一份数据入口文件。★2026-09-07
之前这一步产出一个**空的** `master.h5`——容器自己没有 DD 归宿，写入方把整份放到一边，
而命令行对此一言不发。现在拆分在 IMAS 布局下自动进行，并且**说出**放到一边的是什么。

**没做**：容器自己的 `fylite:` 行（`fylite:channel_map` · `fylite:grid` · 线圈元件的
`fylite:a1` / `a2` 倾角）**不进数据入口**——数据入口只装 IDS。命令行逐条报出来。

## 四 · 四类「进不去」，三类同日修好

装置文档写进数据入口时，**丢了什么**，是这一章真正要说的事。实测 2026-09-07（EAST），
除声明局部（`fylite:` 前缀的行，那是设计）外，起初有 **184 条裸路径**丢在门外，
`wall.h5` 只剩 8 个叶子——一份**看着像结果的空 IDS**。四类，成因各不相同：

| 条数 | 路径 | 性质 | 处置 |
| ---: | :--- | :--- | :--- |
| 90 | `wall/…/vessel/unit/element/geometry` | **词汇**：DD 的真空室元件由 `outline` 描述，没有 `geometry` | 已修，见下 |
| 79 | `magnetics/b_field_pol_probe/position` | **形状**：DD 说结构，文档给一元列表 | 已修，见下 |
| 14 | `pf_active/coil/element/geometry/geometry_type` | **类型**：DD 是整数索引，文档写字符串 | 已修，见下 |
| 1 | `tf/b0` | **名字**：DD 的 `tf` 没有 `b0` | 源仍无家，**留在闸子里** |

判据只有一条，钉在 `rust/fylite_runtime/tests/device_to_imas.rs`：**这张表只准变小**。

### 形状 —— 79 个探针位置

DD 把 `flux_loop/position` 写成**结构数组**（一条环可以穿过好几个点），把
`b_field_pol_probe/position` 写成**一个结构**（一个探针在一个点上）；fylite 的文档
两者同写成 `[{r,z}]`，于是环对了、探针错了——EAST 的 79 个探针位置**全数静默丢失**。
归一化现在解一元列表（记进 `unwrapped`），`magnetics` 从 268 个叶子回到 **426** 个，
逐值与源文档相同。两个以上元素仍旧丢弃：取第一个是悄悄丢掉其余，比丢整支更坏。

### 类型 —— 14 个线圈元件

DD 的 `pf_active/coil/element/geometry/geometry_type` 是**整数索引**，文档写
`"rectangle"`。索引表逐条抄自 DD 自己的 `schemas/utilities/dd_support.xsd`
（`outline_2d_geometry_static`：1 outline · 2 rectangle · 3 oblique · 4 arcs of circle ·
5 annulus · 6 thick line），换名记进 `named`：

```console
  pf_active: … named ["coil/0/element/0/geometry/geometry_type = 2 (rectangle)", …]
```

### 词汇 —— 90 个真空室元件

DD 的 `wall` 元件**只有** `outline/{r,z}`（加 `name` · `midplane_thickness` ·
`resistivity` · `j_phi` · `resistance`），根本没有 `geometry`；fylite 借了 `pf_active`
线圈元件的参数化写法。归一化现在把矩形展成轮廓的四个角，首点重复以闭合（DD 自己的话：
"Repeat the first point since this is a closed contour"），用的是**内核
`kernels::element_filaments` 的同一个映射**——同一个矩形在内核里怎么铺成电流丝，
在这里就怎么铺成四个角，倾角 `fylite:a1` / `fylite:a2` 一并算上：

```
r = r0 + u + v·cos a2 ,  z = z0 + v·sin a2 ,  再绕 (r0, z0) 转 a1
u = ±w/2 ,  v = ±h/2
```

原矩形**留作参考**，改挂本地名 `fylite:geometry`——DD 的 wall 元件没有 `geometry`，
裸着留就是声称一个它没有的出处。实测：`wall.h5` 从 8 个叶子到 **188** 个，
90 条真空室元件一条不丢。抽一个核对（内圈第 0 个元件，`r` 2.7286 · `z` 0.0833 ·
`width` 0.008 · `height` 0.1666 · `a2` 93.743°）：

```console
$ fy data dump rec/imas --path wall/description_2d/0/vessel/unit/0/element/0/outline/r --compact
[2.730037925399138,2.738037925399138,2.7271620746008622,2.7191620746008622,2.730037925399138]
```

★**没有做「合并成内外两层轮廓」那一步**，因为 EAST 的矩形**并不相邻**：实测相邻角点
中位距 9–10 mm、最大 40 mm；按 1e-6 判等，每层 160 条边里只有 4 条是共享的
（`inner_shell` 40 · `outer_shell` 40 · `passive_plates` 10 个单元，各一个矩形）。
把它们并成一条层轮廓要**捏合约 1 cm 数据里没有的几何**——那是一个近似产品，
应当另立本地名并标明是近似，而不是冒充 DD 的 `outline`。

### 名字 —— `tf/b0`

DD 的 `tf` 没有 `b0`，有 `b_field_phi_vacuum_r`——而且那是一个**信号结构**
（`data` 随 `time` 走），不是裸浮点。换算写在 `data` 上，记进 `derived`：

```console
  tf: dropped 1 non-DD path(s) ["b0"]; … derived ["b_field_phi_vacuum_r/data = r0 * b0"]
$ fy data dump rec/imas --path tf/b_field_phi_vacuum_r/data --compact
[3.15]
```

（源文档 `r0` 1.75 · `b0` 1.8。）**源**槽 `b0` 本身在 DD 里仍旧没有家，照旧丢弃并点名
——所以它是闸子里剩下的**唯一**一条。

★所以**这份数据入口不能代替装置文档**：它是同一台机器给 IMAS 工具链看的那一面，
少了 fylite 自己那几行。要完整的一份，留着 fyo（`--layout fyo`）。这是 fyo 与 DD 之间
一处**真实**的表达差，不是转换缺陷；把它印在命令的输出里，比让它在下游某处变成一个
安静的零要好。
