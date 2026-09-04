# `benchmark/` — 公开 V&V 登记册

这里回答一个问题：**fylite 对着外部答案量过什么，各自量到多少。**

源码不公开，所以「我们测过了」这句话本身没有分量——能替代它的只有**可复算的
记录**：输入是什么、参考是谁、判据是什么、量到多少、哪一部分不可比。本目录存
的就是这个，一条一条。

The kernel's source is not published, so "we tested it" carries no weight on
its own. What replaces it is a **recomputable record**: the inputs, the
reference, the criterion, the measured number, and the part that is not
comparable. That is what this directory holds.

★★**本目录是渲染件，不是手写件**（2026-09-02 起）。真源是内核仓的登记册
`docs/cases/registry.jsonld`；内核仓的 `tools/benchmark-publish.py` 把它渲染到这里：
同一批记录，仓内指针改为仓外地址（`$FYLITE_KERNEL/…` 私仓检出、`$FYDOC_ORACLE/…`
参考库），每项参考数据标**纳入类别** 与 **sha256**，并给每条记录追加一条 finding——
发布当日把它的门跑一遍的结果（`finding_kind: re-run…`）。改记录要改真源再重渲染。

## 两半

| | 装什么 | 谁读 |
| :--- | :--- | :--- |
| [`registry.jsonld`](registry.jsonld) | 机器可读的登记册，一条记录一份 `fyo:ComparisonRecord`（fyo / spo 词汇，FYO-ADR-08） | 程序 |
| [`reports/`](reports/) | 每条记录的散文报告：口径对齐、逐项数、结论 | 人 |
| [`scenarios/`](scenarios/) | 对拍场景（`fyo:ScenarioSpecification`，无代码的场景规格）——记录的 `scenario` 指向它 | 两者 |
| [`reports/README.md`](reports/README.md) | 索引：每条记录一行——类、参考、纳入类别、登记册结论、复测结论、报告 | 人 |
| [`context.jsonld`](context.jsonld) | fyo / spo 词汇的 JSON-LD `@context`（与内核仓登记册同一份） | 程序 |

## 三类记录，不要混

判据与可信度都不同。混称会让读者高估其中一类。

| 类 | 问的是 | 参考是什么 | 容差取法 |
| :--- | :--- | :--- | :--- |
| **V — 验证** verification | 这段代码算的是不是它声称的那个函数 | 同一函数的另一实现，或解析解 | **机器精度**（1e-9 或更严）——物理带会掩盖变形 |
| **B — 对拍** benchmark | 两套**不同模型** 在同一状态上给的数差多少 | 另一个码的一次运行 | **实测后定带**，并写明差在哪一笔 |
| **C — 确认** validation | 模型对不对得上**实验或权威参考算例** | 实验数据 / 机构参考算例 | 物理带，取参考自报精度 |

★**一条记录属于哪一类，由「参考是什么」决定，不由做得多认真决定。** 把 B 说成
V 是最常见的夸大：两套模型吻合到 1 % 不等于移植正确——两个错误也能互相抵消。

★同理，**V 不能替 C 用**：「我们和另一个码算得一样」（验证）与「该信这个模型」
（确认）是两句话。一条记录只回答它自己那一句。

## 一条记录必须自带的四样

缺任何一样，这条记录以后就不可复算，只能当传说：

1. **输入** ——不是只有答案。读者要能看出「问的是什么问题」；
2. **出处** ——上游包名、版本、文件名与 **sha256**；一次运行还要记日期；
3. **口径** ——单位、坐标标签、符号约定（COCOS），以及**径向标签**
   （`ρ` 还是 Miller `r`——这一条最常咬人）；
4. **不可比的部分** ——参考解了哪几道方程、哪些量是**喂进去的** 而不是算出来的。

## 什么能进这个公开登记册

判据是**读者能不能自己把参考侧重新取得一遍** ——它决定的是记录的**纳入类别**，
不再决定记录进不进来。★2026-09-02 裁定（「fydata 下有对拍 Oracle 数据的 case 收录进
benchmark」）：受限参考**也收录**，但** 只收指针**——路径、sha256、许可、类别——本体
不在任何公开仓。此前的「❌ 不进」改为「仅指针」，因为把一条比较从公开册里拿掉，
隐藏的是「这条比较存在」这个事实本身，而那正是读者最该知道的。

| 纳入类别 | 参考是什么 | 公开册里有什么 |
| :--- | :--- | :--- |
| `public` | 上游**公开发布** 的算例与答案（GACODE、TORAX、FUSE、fusion_surrogates…）、解析解、已发表的表 | 包名、版本、sha256——存指针不存本体 |
| `public-derived` | 由公开上游产物经本仓工具转换的表（METIS 认证表、GACODE 库的录音） | 同上，外加转换脚本名 |
| `restricted` | 受限许可的源码 / 二进制的输出（JINTRAC 运行树、ITER 参考算例、离仓求解器的录音） | **仅指针**：`$FYDOC_ORACLE` 下的路径、sha256、许可 |
| `restricted-derived` | 表值由受限运行的产物派生（答案侧可复取，输入侧不可） | 仅指针 |
| `experiment` | 实验炮与装置数据，未经数据属主同意不可再分发 | 仅指针 |
| `private-artefact` | 内核仓的制品（神经权重导出件、导出脚本） | `$FYLITE_KERNEL` 指针 + sha256 |

★读者复算得了的只有 `public` / `public-derived` 两类；其余四类，公开册能保证的是
「这条比较存在、参考是哪一份（sha256）、门叫什么、发布当日跑成什么样」。这不是
遗漏，是纳入类别在起作用：一条记录说清自己属于哪一类，比不出现在册子里诚实。

参考库 `$FYDOC_ORACLE` 是 fydoc 仓（私有）的 `cases/` 树（2026-09-04 前在 fydata）；本仓与内核仓各以一条
符号链接 `tests/data -> …/fydoc/cases` 挂载它（`.gitignore` 说明了建法）。

## 怎么读一条记录

先看 `comparison_kind`（V/B/C）与 `compared_reference` 里谁是参考——这两项决定了
后面每个数该怎么读。再看 `criteria`：`tolerance_basis` 是 `machine_precision` 还是
`measured_band`，差别是「这是判据」还是「这是实测后记下来的现状」。再看 `findings`：
前面各条是登记册**量到的**，末条 `re-run…` 是** 发布当日门跑出来的**——两者分开记，
一条记录可以「登记册成立、复测未评估」（门跳过或陈旧）。最后看 `run.has_input[]`
每项的 `license`（纳入类别）与 `checksum`。`caveat` 不是免责声明，是**记录的一部分**。

报告体例见 [`reports/TEMPLATE.md`](reports/TEMPLATE.md)；渲染出的报告按同一体例，
§2 只照录登记册随记录携带的口径说明（四行表的完整账在私仓账本）。

## 复算

```bash
fylite cases --benchmark               # 列出记录：类、登记册结论、复测结论、纳入类别
fylite cases --benchmark V-01          # 打印一条记录（JSON-LD）
fylite cases --benchmark --check       # 结构检查（与 python/tests/test_public_register.py 同一函数）
fylite cases --benchmark --plan V-01   # 这条记录的门在哪跑、哪些跑不了
FYLITE_KERNEL=../fylite_kernel fylite cases --benchmark --run V-01   # 在私仓检出里跑它的 pytest 门
```

每条记录的 `run.realizes[]` 指明哪些闸子把它钉住。`$FYLITE_KERNEL/tests/…` 的门在内核
检出里跑（store 挂在 `tests/data`）；`app/tests/…` 的门在本仓用 node + playwright 跑；
`$FYLITE_KERNEL/rust/…` 的门是 `cargo test`。没有内核检出的读者能做的是：按 `scenario`
与 `criteria` 用自己的工具重跑参考侧，再与 `findings` 对。**对不上就开一个 issue** ——
这正是这个登记册公开的意义。
