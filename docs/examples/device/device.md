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

实测产出——五个 IDS 加一份 master，共 127 KB：

| 文件 | 字节 |
| :--- | ---: |
| `master.h5`（外部链接指向下面五份） | 2 176 |
| `wall.h5` | 38 992 |
| `magnetics.h5` | 31 048 |
| `pf_active.h5` | 32 608 |
| `lh_antennas.h5` | 16 968 |
| `tf.h5` | 5 864 |

读得回来，且逐值相同：

```console
$ fy data info rec/imas
rec/imas: imas-hdf5 (imas layout)
  lh_antennas (occurrence 0): 9 leaves
  magnetics (occurrence 0): 268 leaves
  pf_active (occurrence 0): 89 leaves
  tf (occurrence 0): 6 leaves
  wall (occurrence 0): 8 leaves
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
`fylite:a1` / `a2` 倾角）**不进数据入口**——数据入口只装 IDS。命令行逐条报出来：

```console
  pf_active: dropped 42 non-DD path(s) ["coil/0/element/0/fylite:a1", …]
  tf: dropped 1 non-DD path(s) ["b0"]
  magnetics: … unwrapped ["b_field_pol_probe/position"]
```

### 还有三支进不去，各有各的理由

实测（2026-09-07，EAST）除声明局部外还有 **105 条裸路径**丢在门外，三类：

| 条数 | 路径 | 性质 |
| ---: | :--- | :--- |
| 90 | `wall/…/vessel/unit/element/geometry` | **词汇**：DD 的真空室元件由 `outline` 描述，没有 `geometry`；fylite 借了线圈元件的参数化写法 |
| 14 | `pf_active/coil/element/geometry/geometry_type` | **类型**：DD 是整数索引，文档写字符串 `"rectangle"`（该用哪个整数本仓查不到，`[TBD]`） |
| 1 | `tf/b0` | **名字**：DD 的 `tf` 有 `b_field_phi_vacuum_r`，没有 `b0` |

三条都不是改个名就能了的，各要一个决定，所以都**记在闸子里**而不是悄悄留着：
`rust/fylite_runtime/tests/device_to_imas.rs` 的 `EXPECTED` 只准变小。

★**探针位置那一条同日修好了**，因为它不需要决定。DD 把 `flux_loop/position` 写成
**结构数组**（一条环可以穿过好几个点），把 `b_field_pol_probe/position` 写成**一个结构**
（一个探针在一个点上）；fylite 的文档两者同写成 `[{r,z}]`，于是环对了、探针错了——
EAST 的 **79 个探针位置全数静默丢失**。归一化现在解一元列表（并记进 `unwrapped`），
`magnetics` 从 268 个叶子回到 **426** 个，逐值与源文档相同。两个以上元素仍旧丢弃：
取第一个是悄悄丢掉其余，比丢整支更坏。

★所以**这份数据入口不能代替装置文档**：它是同一台机器给 IMAS 工具链看的那一面，
少了 fylite 自己那几行。要完整的一份，留着 fyo（`--layout fyo`）。这是 fyo 与 DD 之间
一处**真实**的表达差，不是转换缺陷；把它印在命令的输出里，比让它在下游某处变成一个
安静的零要好。
