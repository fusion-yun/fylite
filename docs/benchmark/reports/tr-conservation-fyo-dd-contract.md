---
title: "tr-conservation-fyo-dd-contract"
---

# 声明的每条路径都要有出处：裸名在 DD 里查得到，自铸的必须带前缀

<!-- ★生成件，勿手改：`python tools/benchmark-book.py`。正本是 `records/tr-conservation-fyo-dd-contract.jsonld`，本页只是它的可读面。 -->

*输运 (Transport) · [守恒、金标 parity 与口径](../domains/tr/conservation.md)　|　记录正本：`records/tr-conservation-fyo-dd-contract.jsonld`*

## 摘要

- **类**：验证　**判决**：**成立**
- **量的是**：声明的每条路径都要有出处：裸名在 DD 里查得到，自铸的必须带前缀
- **参考**：仓内的 IMAS DD 表（`rust/fylite_runtime/ids/*.tsv`，82 个 IDS、26752 行）
- **验的需求**：`NR-TR-005`
- **跑在内核**：`sha256:ac8c0f5cdc4e6019…`（新鲜度 **current**）
- **记录版本**：1.0　**评审**：草稿　**日期**：2026-09-17

:::{warning} 这是一条**已裁定保留**的缺口

2026-09-17 ★第二格（摘要闸）的门在**内核仓的构建脚本**里，本仓 CI 跑不到——与 `tr-pedestal-sawtooth-kadomtsev` 同一处代价。★第三格是翻译差（LinkML vs JSON Schema），不是缺陷，但也**没有被消解**：要真答上游那一格，得有人决定 fylite 是否引入 LinkML，那是个设计决定不是测量。
:::

## 问的是什么

**被量的**：260 条声明路径：147 条裸 DD 名 + 113 条 fyo 自铸

**参考**：仓内的 IMAS DD 表（`rust/fylite_runtime/ids/*.tsv`，82 个 IDS、26752 行）

> ★**参照就在仓里**，这是这条判据能真查的前提：DD 表是提交进仓的生成物，所以「这个裸名 DD 里到底有没有」是个当场可答的问题，而不是一句信仰。

**口径与适用域**：

> 本次检出的接口契约（`python/fylite/_fyo_interface.py`，由内核的 `fyo.rs` 生成）与仓内 DD 表（`rust/fylite_runtime/ids/*.tsv`）。★判的是**声明层**：路径是否有出处、契约变更是否被闸住；**不判数据本身是否符合 DD 的类型与单位**——那是另一件事，本条不声称。

## 判据与量到多少

:::{figure} ../figures/tr-conservation-fyo-dd-contract-headroom.svg
:alt: tr-conservation-fyo-dd-contract 的判据余量图
:width: 100%

每条判据离它的带还有多远（对数轴，1 倍即判据本身）。★**绿而窄（< 2 倍）另着色**：它与余量一千倍的判据在下表里都只是一个「成立」。
:::

| 判据 | 容差 | 取法 | 量到 | 判 |
| :--- | ---: | :--- | :--- | :--- |
| 没有 DD 归宿的**裸**路径条数 | 0 | reference_self_reported | 260 条声明路径里 147 条是裸 DD 名，逐条在仓内 82 个 IDS 表（26752 行）里查有归宿，**0 条落空**；另 113 条是 fyo 自铸，一律带 `fylite:` 前缀 | **成立** |
| 接口内容变了而摘要没变的次数（构建期闸） | 0 | reference_self_reported | 当前 `INTERFACE_REVISION = 5` · `INTERFACE_DIGEST = 41f31b0f5a225eea`。★2026-09-17 往 `DISCHARGE` 加两槽（53 → 55）时，这道闸**当场拦下构建**，并要求先回答「这次改动会不会让旧读者读错」——不会（只加不改不删），于是只贴新摘要、修订号不动 | **成立** |
| 抄录点名的 LinkML 校验 | — | reference_self_reported | `python/fylite/_spec/` 下是 4 份 **JSON Schema**（`common` · `compute_artifact` · `data_artifact` · `workflow_ir`），不是 LinkML；路径契约则由 DD 表 + 上面两道闸守 | **未评估** |

**`没有 DD 归宿的**裸**路径条数`** — ★★**这一格防的事故是真发生过的**：`tf/b0` 裸着写进声明表——DD 4.1.1 的 `tf` 有 `r0`、有 `b_field_phi_vacuum_r`，**没有 `b0`**。把一台真实装置写成 IMAS 入口时它被**静默丢弃**，同批丢的还有 79 个探针位置与 90 个真空室元件。★**一份看着像结果的空 IDS，比一个错误更坏。**

**`接口内容变了而摘要没变的次数（构建期闸）`** — ★抄录的「节点数组契约回归」这一半：契约一改，**摘要必须跟着改**，而且改之前要先回答「旧读者会不会读错」——会则修订号加一，不会则只贴新摘要。

**`抄录点名的 LinkML 校验`** — ★★**本仓不用 LinkML**，见 finding。判据照抄立在这里，不删。

**每条裸名都在 DD 里查得到**

- ★★**这道闸补的是内核那道的「开世界」一半。** 内核只查**成员关系**（带前缀的要在手写的`OURS` 表里、裸的不在），它**从不查 DD**——于是一个没有 DD 归宿的裸名，只要没人想起把它加进 `OURS`，就一路绿灯。
- ★**前提在 2026-09-13 被改过，这一点要说明**：此前这道闸把 DD 当作**唯一**权威，而 fyo 的规矩写在它自己的 manifest 上——「fyo **不**硬绑 IMAS DD，它独立演化；DD 是导入基线」。所以一个 fyo 自铸的槽裸写是**对的**，旧前提会把它判红。★本条量的是改后的判准。

**★契约改了，摘要必须跟着改 —— 本轮亲身验过**

- ★★**这不是事后追述，是本轮真被它拦过。** 一道只在文档里存在的规矩与一道会让构建失败的闸，是两件东西——后者才拦得住人。

**★LinkML：**本仓不用它****

- ★★**这是一次翻译，说清楚而不是含混过去**：抄录点名 LinkML，是上游 fytok 的技术选择；fylite 用 JSON Schema 加 DD 表答同一个问题（**声明的东西有没有出处、契约改了会不会有人读错**）。★把 JSON Schema 说成「LinkML 校验通过」是冒充，所以这一格标 unevaluated。
- ★另有 `test_manifest_conformance.py`（94 项），但在本次检出上**全部跳过**（缺前提），所以它不作为本条的证据——**一道跳过的门不是门**。

## 不可比的部分

- ★★**结构判据会腐烂且腐烂时不出声**，所以这两格都由门守着：路径那格是本仓的 pytest，摘要那格是内核仓的构建闸。★后者不在本仓 CI 上，与锯齿那条同一处代价。
- ★本条只答 `NR-TR-005`。平衡侧同名的问题由 `eq-forward-self-contained-core` 的别的格答——两条不重叠：那条问「核依赖谁」，本条问「声明的名字有没有出处」。

## 追溯

- 首次入册 2026-09-17　末次修订 2026-09-17　版本 1.0　评审 草稿

**变更史**（★改判本身留在册里，不覆盖旧结论）：

| 版本 | 日期 | 谁 | 做了什么 |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-09-17 | Claude Opus 5 (1M context) | 首次入册：`NR-TR-005` **不是能力缺口**——260 条声明路径里 147 条裸 DD 名逐条有归宿（0 条落空），摘要闸本轮亲身把构建拦下过。★LinkML 那一格如实标 unevaluated：本仓用 JSON Schema + DD 表答同一个问题，**说成「LinkML 校验通过」是冒充** |

## 复算

**这次跑在**：

- 内核 `libfylite` `sha256:ac8c0f5cdc4e601951da0b1ad26a58616571913de15e1bd089065e8a94dc0e7a`

**输入（每一项都带 sha256，否则指针指不住任何东西）**：

- `docs/benchmark/readings/fyo_dd_contract.json`    `sha256:2a2a852bf93688669b02e6ba73eb049a25a634b0ae336d0094eef6c5dfa2e09c`    声明路径的裸/自铸清点、DD 表规模、当前接口修订号与摘要

**守它的门**：

- `python/tests/test_fyo_paths_have_a_dd_home.py` —— ★第一格的门（11 项，实跑）。第二格的闸在内核仓的 rust/build.sh，本仓 CI 跑不到

```bash
python tools/benchmark-book.py --check   # 本页与记录同源吗
python tools/benchmark-book.py --ci      # 过期了吗、不成立吗
```
