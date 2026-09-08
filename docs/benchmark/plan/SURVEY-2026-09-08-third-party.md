# 第三方源码盘点：哪几条阻塞其实有第二条路

**2026-09-08 晚，对 `~/workspace/third_party/`（89 个检出）逐条比对定序册的六条阻塞。**
起因是第三轮收尾时那句话——「不通的六条全部阻塞在参考侧」——它成立，但**没有人问过
参考侧的码是不是就在本机**。问了之后，六条里有两条的性质变了。

★本页只出**证据与判断**，不改判决：判决的唯一生成源是 `plan.jsonld`，本页被它引用，
不反过来复述它（这正是同日 `fd94f85` 那次勘正的教训）。

---

## 一、六条阻塞，逐条对盘

| 记录 | 参考侧 | 盘上有没有 | 性质变了吗 |
| :--- | :--- | :--- | :--- |
| `C-06` TEQ / CORSICA | ITER IDM 四份文档（`$ITER_SCENARIO_ROOT` 1.7 GB，Internal Use）| **没有**（`teq` `corsica` 皆无检出）| 不变 |
| `C-07` TOSCA | ITER IDM 两份 | **没有** | 不变 |
| `C-10` TRANSMAK | ITER IDM 3TPCKG（报告体）| **没有** | 不变 |
| `C-08` GENE | Zenodo 公开载荷 + 两个未发布的量 | GENE 本体**没有**（其载荷已在手）| 不变（本就是 `blocked-known`）|
| **`B-08` FUSE ITER_time** | 上游未随码发布输出，须自跑 | ★★**`third_party/FUSE` 就是 1.1.5**——正是本条点名要的版本，且 `ITER_time` 算例在 `FUSE.jl/src/test_cases.jl:135` 逐行写着 | ★**变了**：挡路的不再是「参考侧取不到」，是**本机没有 1.1.5 的 Julia 环境** |
| **`B-09` DINA** | ITER IDM 场景（Internal Use）| ★★**`third_party/DINA-IMAS` 是 DINA-PS 本体，LGPL 3.0**，带 `machines/iter` 与 `src/scenario/diter_1.f` | ★**多出一条路**：参考可以**自跑**而不是取回——但这一步要一次裁定 |

### `B-08` 的准确挡路点

本机 Julia 环境（`v1.10` / `v1.11` 两套）里装的 FUSE 是 **0.7.0**（`Manifest.toml:800`），
而本条的判据明写「**不得**用已遗弃的 0.7.0 旧记录顶替」。`third_party/FUSE` 的
`FUSE.jl/Project.toml` 写着 `version = "1.1.5"`。所以缺的是一件确定的活：**把盘上这份
`dev` 进一个环境，跑 `test_case(:ITER_time)`，把答案按算例书体例登记**。

★算例本身是自足的（`init_from=:ods` 装硬件 → `init_from=:scalars, time_dependent=true`
给日程 → `ActorStationaryPlasma` 收敛到自洽初态 → `ActorDynamicPlasma` 走 `Nt=60 · Δt=300`
六个演化开关）。**不需要任何外部数据**。

### `B-09` 要的是一次裁定，不是一次实现

DINA-PS 以 **LGPL 3.0** 释出，源在盘上，带 ITER 机器描述。于是「取回 IDM 场景」不再是
唯一的路——**自跑一份参考**同样能给出第二个答案。但这一步牵动两件事，都不该由我代拍：

1. **许可与清净室**：本仓对「读物理源码」有明确的既有裁定（GRAY 移植暂停时点名「勿读
   物理源，会关死清净室路线」）。**把 DINA 当 oracle 跑**与**读它的 Fortran**是两件事，
   但同一棵树上，前者容易滑向后者。
2. **可行性未探**：`imas/co-simulation/` 下有 `.mexa64`（MATLAB 依赖），能不能在本机跑
   起来**没有试过**。在试之前，把 `B-09` 从 `blocked-unknown` 改判是不诚实的。

---

## 二、盘上还有什么，本册子一次都没用过

登记册今天引用过的外码：TORAX · TGLF/GACODE · QLKNN · TGYRO · NEO · METIS · JINTRAC ·
FUSE · ASTRA · TokSys · EPED。**盘上另有这些，一次都没进过登记册**（只列与本仓能力对得上的）：

| 类别 | 检出 | 对得上本仓的哪一面 | 制品状态 |
| :--- | :--- | :--- | :--- |
| 定边界平衡 | `chease` · `toq4.0` | GS 正问题（S1 **最弱的一节，1/3**）| 未构建 |
| 自由边界平衡 | `nice` · `freegs` · `freegs4e` · `freegsnke-main` · `meq` · `feqis` · `veqpy` | 自由边界与反演 | `freegs` 跨仓用过（fywork CASE-09）|
| **湍流本体** | **`QuaLiKiz`** | **QLKNN 代理的地面真值** | ★**已构建可跑**（`bin/QuaLiKiz-gcc-release-default-mpi.exe`，2026-08-02）|
| 湍流（其他）| `stella` · `gyselalibxx` · `grillix` · `weiland` | 同上 | 未构建 |
| 射线追踪 / CD | `genray` · `toray1.8` · `cql3d` · `lsc` · `luke` | ECRH / LH 的第二答案（现只有 METIS 认证判据）| 未构建 |
| 快离子 | `ascot5` · `spot` · `nova-k` | NBI / α 慢化 | 未构建 |
| 杂质辐射 | `Aurora` | 现只有 Mavrin 非日冕（`V-09`）| 未构建 |
| 一维 SOL | `DIV1D` · `SOLPS-ITER` · `B2.5` · `EIRENE` | 现只有 Lengyel 闭式（`V-10`..`V-13`）| 未构建 |
| 中断 / 逃逸 | `DREAM` | 本仓无此面 | 未构建 |
| 整合模拟 | `cronos` · `ETS` · `transp_1403` · `transp_2201` · `raptor` | S8 | 未构建 |
| 系统码 | `PROCESS` · `bluemira` · `OpenSTEP` | 本仓无此面 | 未构建 |

★★**「盘上有」不等于「可当参考」**。一条记录要成立，参考侧必须**可复算**：装得起来、
跑得出同一个答案、许可允许把答案写进册子。上表的「制品状态」一列就是为此存在——
只有 `QuaLiKiz` 与 `freegs` 今天满足第一条。

---

## 三、本次立的两条与不立的一批

**立**（见 `plan.jsonld`，`status: planned`）：

- **S1 · `B-10` CHEASE 定边界平衡**——S1 是干路上唯一 1/3 的一节，而它的两条参考
  （TEQ · TOSCA）都锁在 IDM 里。CHEASE 是同一问题的**独立求解器**，且不需要任何受限
  数据：给定边界与两个剖面，答案由码自己产生。★与 `B-01`（FUSE）不重：`B-01` 比的是
  FUSE 的**整档**，这一条比的是 GS 解本身。
- **S4 · `C-11` QuaLiKiz 本体**——`V-03` 今天比的是「本仓能不能复现那张网」（参考是上游
  自己的推理路径），**代理相对于它所近似的物理有多大误差，本册子一个字都没有**。
  QuaLiKiz 是那张网的训练源，制品在本机已构建。★类别是 **C**（确认）不是 V：网络与
  第一性计算不是同一个函数的两个实现。

**不立**（候选，待你定）：射线追踪 · 快离子 · 杂质 · 一维 SOL · 中断 · 其他整合码。
理由一致：**都要先构建，而构建成本未估**；在估之前立条目，等于把「尚未立」换成
「立了但不动」，账面好看而实质更差。

★★**为什么只立两条**：本册子刚刚做到「尚未立归零」。新立条目会把它推回非零——这没问题，
**只要每一条都答得出「凭什么现在能做」**。上面两条答得出（参考侧的码在本机、已构建或
不需受限数据），其余答不出。
