---
title: 致谢 (Acknowledgements)
---

# 致谢

fylite 是 fyo 语义契约的一个独立、轻量实现，覆盖托卡马克平衡、输运与 0-D 建模。
 
fylite的开发是中国科学院等离子体物理研究所（ASIPP）**「集成建模讨论组」**工作的
一部分，版权归 ASIPP 与 fylite 贡献者所有，按 **Apache License 2.0**发布。

本项目受惠于下列工作与合作者。谨此致谢：

## 主要合作

- **集成建模讨论组**：孙有文、任启龙、简祥、夏天阳、于治、刘晓娟、胡也民、肖小涛等。
- **ASIPP EAST 团队**——放电数据、运行态 EFIT 工作流与逐道诊断几何。
- **钱金平、李国强、任启龙、L. L. Lao 等**——将 EFIT 移植至 EAST 并建立动理学重构
  （KEFIT），本仓重构线的上游参照基线。
- **孙有文**——HT-7 软 X 射线层析工作（相机几何参数化与弦-格林 / 加权伪逆方法骨架）。
- **兰婷**——整理 EAST 实验数据语料，逐道诊断几何经 fydata 到达本项目。
- **黄耀与 EAST PCS 组**——等离子体控制系统接口说明（磁探针几何与平衡↔PCS 变量的交叉核对）。
- **吴学民、盛回**——KEFIT 运行流程的梳理与指导，并提供 benchmark 算例。
 
## 随页面分发的第三方软件 (Third-party software shipped with the pages)

下列软件**以二进制 / 源码原样随浏览器页面分发**，不是移植、不是参照，而是别人的代码在
读者的浏览器里运行。列在这里是**许可义务**，不是客套。

| 上游 | 版本 | 许可 | 用途 | 位置 |
| :--- | :--- | :--- | :--- | :--- |
| **h5wasm**（美国国家标准与技术研究院，**NIST**） | 0.10.3 | NIST 公共服务条款（见 `app/assets/vendor/h5wasm/LICENSE.txt`，原样保留） | 在浏览器里读 HDF5：本仓的 HDF5 面链 `libhdf5` 这个 C 库，而该库在 `wasm32-unknown-unknown` 上编不出来（实测：`libc::FILE` / `off_t` / `ssize_t` 不存在），故浏览器侧由它把 `.h5` 解成一份 fyo 文档，再进源栈 | `app/assets/vendor/h5wasm/`，按需 `import()`（约 4.2 MB，不进预缓存） |

★**明确承认**：h5wasm 系 **NIST** 开发的软件；其许可要求「明确承认 NIST 为该软件的来源」，
此处即为该承认。本仓**未对其作任何修改**——`tools/vendor-h5wasm.mjs` 只拷贝、不打补丁，
逐文件的 sha256 记在 `app/assets/vendor/h5wasm/PROVENANCE.md`。h5wasm 内含经 Emscripten
编译的 **HDF5 C 库**（HDF Group），其许可随该包一并分发。

## 移植的上游代码（白盒翻译）

下列模块系上游代码的**白盒移植**，而非依文献所作的独立实现。此项区分属许可义务，
故在此正文陈述，而不置于脚注。

| 上游 | 作者 / 机构 | 许可 | fylite 取用了什么 | 位置 |
| :-- | :-- | :-- | :-- | :-- |
| **GACODE — GEO** | J. Candy，General Atomics | Apache-2.0 | 磁面局域几何（Miller 系形状与度规，`geo.f90`） | `rust/fylite/src/geometry.rs` |
| **GACODE — NEO** | E. Belli、J. Candy，General Atomics | Apache-2.0 | 新经典解析模型（`neo_equilibrium`、`neo_make_profiles`、`compute_Sauter*`）与漂移动理学求解 | `rust/fylite/src/neoclassical.rs`、`dke.rs` |
| **GACODE — TGLF** | G. M. Staebler et al.，General Atomics | Apache-2.0 | 回旋朗道流体模型、FLR 拟合表、俘获闭包表 | `rust/fylite/src/gyrofluid.rs`、`flr_tables.rs`、`closure_tables.rs` |
| **GACODE — TGYRO / expro** | General Atomics 与 GACODE 贡献者 | Apache-2.0 | NEO / TGLF 输入映射、源项与辐射、体积分、`expro_compute_derived`、`input.gacode` 读写 | `rust/fylite/src/mapping.rs`、`sources.rs`、`bundle.rs`；`python/fylite/scenario/model/{mapping,sources}.py`；`python/fylite/io/gacode.py` |
| **NCLASS**（随 GACODE 携带） | W. A. Houlberg | 随 NEO | 随 NEO 携带的新经典系数 | 经 NEO 移植线 |
| **METIS** | J. F. Artaud et al.，CEA/IRFM | CeCILL-C | 快中性束模型：弦衰减、Janev 停止截面、Stix 临界能量与束驱电流（公式级转写，见「依公开文献转写的物理」） | `rust/fylite/src/heating.rs` |
| **FyTok — fytrans** | 中国科学院等离子体物理研究所（fylite 的上级项目） | Apache-2.0 | 通道声明语法（保持逐字一致，使声明可在上级项目与本项目之间往返）；1.5D 输运核以它为逐位对拍基准 | `python/fylite/scenario/`，见「上级项目：FyTok」 |

 
**修改说明**（Apache-2.0 §4b）：移植是翻译不是复制——模块状态改为显式参数，
LAPACK / UMFPACK 换成本仓自写的稠密与稀疏例程，上游 `STOP` 的地方改返回错误码，
且可重入。若干处**有意偏离**上游行为（多在上游悄悄覆盖自己的输入之处），每一处都在
源码里就地写明。完整清单见 `NOTICE`。UMFPACK **未**移植——本仓的稀疏 LU 从零写起。

## 依公开文献转写的物理

| 出处 | 用于 | 位置 |
| :-- | :-- | :-- |
| **METIS** — J. F. Artaud et al., *Nucl. Fusion* 58 (2018) 105001；CEA/IRFM，CeCILL-C | 中性束快中性电离、束驱电流积分、慢化能量、杂质形式（`z0signbi`、`zicd0`、`zsupra0`、`zfract0`）；**少数离子 ICRH 链**（`z0icrh` — 共振层、Stix 分布、快离子含量、Eriksson 电子份额 — 与 `z0qp`）——公式级转写，与 METIS 保持逐位可比 | `rust/fylite/src/heating.rs` |
| L. L. Lao et al., *Nucl. Fusion* 25 (1985) 1611 | 重构结构（Picard + 最小二乘）——仅作算法参照，见「刻意未取的东西」 | `rust/fylite/src/inverse.rs` |
| O. Sauter, C. Angioni, Y. R. Lin-Liu, *Phys. Plasmas* 6 (1999) 2834 | 自举电流 / 电导率 | `rust/fylite/src/neoclassical.rs` |
| A. Redl, C. Angioni, E. Belli, O. Sauter, *Phys. Plasmas* 28 (2021) 022502 | 自举电流重新标定（两条读数**分开保留**：NEO 的 `compute_Sauter_mod` 与 IMAS.jl / FUSE 一脉） | `rust/fylite/src/neoclassical.rs`、`python/fylite/scenario/model/neoclassical.py` |
| Hinton–Hazeltine；Chang–Hinton；Hirshman–Sigmar；Taguchi；Hinton–Rosenbluth；Koh et al.；Y. R. Lin-Liu & R. L. Miller (1995) | 解析新经典变体与俘获份额 | `rust/fylite/src/neoclassical.rs`、`dke.rs` |
| Y. R. Lin-Liu & F. L. Hinton, *Phys. Plasmas* 4 (1997) 4179 | NBCD 电子屏蔽 | `rust/fylite/src/heating.rs` |
| T. H. Stix, *Nucl. Fusion* 15 (1975) 737 | 少数离子 ICRH 分布及其 H 函数 | `rust/fylite/src/heating.rs` |
| ITER Physics Basis, *Nucl. Fusion* 39 (1999) 2495, 第 6 章 §3.5（p. 2512）——实测快波驱流效率（JFT-2M、DIII-D、Tore-Supra）、其线性 `T_e0` 依赖与 ITER 外推；数据点本身取 METIS `fitetafwcd.m` 中的列表 | FWCD 效率及其闸门 | `rust/fylite/src/heating.rs` |
| M. Bornatici, R. Cano, O. De Barbieri, F. Engelmann, *Nucl. Fusion* 23 (1983) 1153, Table 12——经 A. Sabri et al., *Int. J. Emerging Technology and Advanced Engineering* 2 (8) (2012) 253, Table I 的逐字重印读到（原文此处未能取得；转写的是重印本，两条出处都写进源码） | `1/R` 平板的 EC 光学厚度（O 模 `n>=1`、X 模 `n>=2`）与冷等离子体垂直折射率 | `rust/fylite/src/heating.rs` |
| G. Giruzzi, *Nucl. Fusion* 27 (1987) 2069（按 METIS `zicd0.m` 的拟合）；Y. R. Lin-Liu, GA-A24257（`Z_eff` 依赖） | EC 驱流效率 | `rust/fylite/src/heating.rs` |
| ITER / IMAS 的 EC 发射角约定，按 **FUSE** 的实现（`IMAS.jl` `pol_tor_angles_2_vector`，Apache-2.0） | 装置描述所存的两个指向角，及其所指方向 | `rust/fylite/src/heating.rs` |
| R. K. Janev, C. D. Boley, D. E. Post (1989) | 中性束停止 / 电荷交换截面 | `rust/fylite/src/heating.rs` |
| S. Weiland et al., *Nucl. Fusion* 58 (2018) 082032（RABBIT） | 快 NBI 模型类 | `rust/fylite/src/heating.rs` |
| T. Pütterich et al., *Nucl. Fusion* 59 (2019) 056013；Open-ADAS（<https://open.adas.ac.uk>） | 冷却曲线 Chebyshev 拟合 | `rust/fylite/src/sources.rs` |
| ITER Physics Basis, *Nucl. Fusion* 39 (1999) 2175（IPB98(y,2)）；P. N. Yushmanov et al., *Nucl. Fusion* 30 (1990) 1999（ITER89-P）；Y. Martin et al., *J. Phys. Conf. Ser.* 123 (2008) 012033（L–H 阈值）；H.-S. Bosch & G. M. Hale, *Nucl. Fusion* 32 (1992) 611（D-T 反应率） | 0-D 标度律 | `rust/fylite/src/zerod.rs` |
| P. B. Snyder et al., *Phys. Plasmas* 16 (2009) 056118（EPED1 两条约束）；O. Meneghini et al., *Nucl. Fusion* 57 (2017) 086034（EPED1-NN 代理） | 台基模型；网络权重取自开源 EPEDNN.jl（ProjectTorreyPines，Apache-2.0，本仓随附许可与校验和） | 见「参考数据、oracle 与跨程序锚点」的 FUSE / EPEDNN 条 |
| S. Jardin, *Computational Methods in Plasma Physics* §4.4；Hockney 直接椭圆解法（*J. ACM* 12 (1965) 95）；Solov'ev 解析平衡 | GS 求解器数值与解析 oracle | `rust/fylite/src/equilibrium.rs` |
| Qian (2014) EFIT `&IN1` 汤姆逊密度样条约定 | k 文件约束块 | `python/fylite/io/kfile.py` |

## 刻意未取的东西

一份只列取用的致谢是不完整的。下面几项是**有意不取**的，理由各不相同，
但都属于同一份记录：

- **EFIT 一脉**：任何形式的 EFIT 族源码、格林表生成器或录得输出都不在仓内。
- **GRAY**：EC 射线追踪的移植已停止；其许可不容直接翻译，fylite 未读过任何 GRAY 物理源码。
- **UMFPACK**：未移植——本仓的稀疏 LU 从零写起（见「移植的上游代码」）。


## 参考数据、oracle 与跨程序锚点

| 数据 / oracle | 提供方 | 条款 | 用途 |
| :-- | :-- | :-- | :-- |
| GACODE 回归算例与录得输出（`tglf01` GA 标准算例、TGYRO `treg01`、libgeo/libneo/libtglf 录音） | General Atomics（GACODE `6357db306` / `5efddfdf1`） | Apache-2.0 | `tests/data/*`、`tests/oracles/`——移植的金标夹具 |
| **EAST 第 137985 炮 @ 4.0 s**（磁测量、POINT、汤姆逊；`efit_east` 树） | 中国科学院等离子体物理研究所（ASIPP）EAST 团队；所内网 MDSplus 服务器 | 机构内部 | 唯一一套实炮夹具（`examples/scripts/`、`examples/east137985-recon-figure/`）。★**不随演示发布** |
| EAST 运行态 EFIT 工作流（`EFIT_POINT_GUI_v5.m`、est2 `dprobe.dat`、`fitweight.dat`） | ASIPP | 机构内部；以无头方式复现，未复制 | `python/fylite/io/kfile.py`、`fylite.machine` |
| **KEFIT 参考包**（**不在仓内**） | EAST KEFIT——将 DIII-D 一脉的 EFIT 移植至 EAST 并建立动理学重构，李国强、任启龙、钱金平、L. L. Lao 等（*Plasma Phys. Control. Fusion* 55 (2013) 125008；内部 q 约束见 H. Fan et al. 2024）；ASIPP | 内部、未授权、不再分发 | 重构线的上游参照基线：g 文件逐位比对、k/g/a/m 文件契约、`python/fylite/io/kfile.py` 中复现的 GUI_v5 工作流 |
| **sxht7**——ASIPP HT-7 软 X 射线层析程序（约 2008） | 孙有文（Youwen SUN），ASIPP | 内部、未授权 | 相机几何参数化（4 相机 × 6 参数）与 Fourier–Bessel / 弦-格林 / 加权伪逆方法骨架，移植入 `python/fylite/device.py`（相机几何）与 `python/fylite/scenario/analysis/tomography.py`（方法骨架） |
| EAST 等离子体控制系统接口说明（《数字托克马克仿真模拟平台等离子体控制系统接口说明》，2022；ISO-FLUX 控制点、分段、X 点、磁几何） | 黄耀（Yao HUANG），EAST PCS 组，ASIPP | 内部文档 | 磁探针几何交叉核对；平衡↔PCS 接口变量 |
| EAST 实验数据语料 `YLK_*` / `eastylk`（第 137985–137989 炮等；逐道诊断几何 `<DIAG>_desc.json` 与信号） | 兰婷（Ting LAN）整理，ASIPP | 机构内部 | 经 fydata 到达 fylite 的逐道 EAST 诊断几何；基于 MDSplus 的实炮夹具的前身（语料文件本身已退出夹具路径） |
| **TokSys** EAST 电磁模型（`make_east_objects.m`、`rzrig`、`EAST_PS_params`） | General Atomics | 外部，未随仓携带 | 电路与垂直稳定性的跨程序锚点（`tests/test_benchmark_toksys.py`） |
| **METIS 认证基线** | CEA/IRFM（经 fywork CASE-07） | CeCILL-C；此处不再分发 | 0-D 能量账目对比（`examples/zerod-metis/`） |
| **METIS 认证套件——ICRH / ECCD 答案** | CEA/IRFM（J.-F. Artaud 与 METIS 贡献者） | CeCILL-C；存档**不在此再分发**——只有导出的表，表头写明每份存档的 sha256 | 未来 ICRH / ECRH 模型的判据（`tests/data/reference/metis_cert_hcd.csv`，由 `tools/metis-cert-to-oracle.py` 生成；评判见 `docs/note/icrh-ecrh-gap.md`） |
| **FUSE 装置算例——仅输入标量**（ITER、KSTAR、DTT、SPARC、ARC、FPP、K-DEMO、MANTA、EXCITE 的 `case_parameters(:X)`） | ProjectTorreyPines（FUSE.jl `494d565`，两条分辨率规则用 IMAS.jl 与 MillerExtendedHarmonic.jl v2.1.2） | Apache-2.0；**FUSE 的源码与数据文件都没有进仓**——进来的是从一次检出里读出的标量表，每份生成文档都写明提交号与源文件 | 含时演化栏提供的现成算例（`docs/cases/evolve-fuse-*.jsonld`，由 `tools/fuse-case-to-fylite.py` 生成；清单与评判见 `docs/note/fuse-cases.md`）。★这些只携带 FUSE 的**输入**——chi_0 与其余闭包是本仓的，因此不是对 FUSE 答案的复现 |
| **FUSE——一次 ITER 运行的输入与答案**（`FUSE.init(:ITER, init_from=:scalars)`，FUSE 0.7.0 / EPEDNN 1.0.7，录于 2026-08-29） | ProjectTorreyPines | Apache-2.0；**FUSE 的源码与数据文件都没有进仓**——记录里是 FUSE 选定的十个 EPED 输入与它给出的九个答案，外加它解出的平衡、0-D 账目与剖面 | T-C1′ 对拍：`tests/data/FYDOC-CASE-04-fuse/corpus/iter_eped.json`、`iter_init.json`，由 `tests/test_fuse_benchmark.py` 把闸，`tools/fuse/capture-iter.jl` 可重录。★台基这一层不是「两个模型一致」：FUSE 的 `ActorPedestal` 与本内核加载**同一份** EPEDNN BSON 权重，所以它量的是移植后还是不是同一个函数（4.4e-16） |
| **TGLF-NN——只取架构与一次运行的答案；不取权重** | ProjectTorreyPines（TGLFNN.jl 1.7.1） | Apache-2.0；★★**没有任何模型文件被再分发，也没有编译进来**——`rust/fylite/src/nn.rs` 实现所发布模型所用的 dense+residual 族，`tools/nn-export.jl` 在装有该包的宿主上转换一份，`$FYLITE_NN_DIR` 是用户自己存放的位置 | 代理路径，由 `tests/test_nn_surrogate.py` 对 TGLF-NN 自己在 FUSE ITER 算例上的答案把闸（`tests/data/FYDOC-CASE-04-fuse/corpus/iter_tglfnn.json`，4.9e-14）。每次导出都记录上游包名、版本、文件与 sha256，因此引用的数字可追溯到一件本仓并不持有的制品 |
| ITER 装置描述（PF/CS 线圈、壁、110 个磁通环；ITER EDA，2010-04-26） | ITER 组织，经 `fydata` 包 | 依 fydata 所记 | 浏览器预置装置（`app/facts/device/iter.jsonld`）；演示内置的 ITER 位形即出自此 |

## 库与工具链

`numpy`（必需）；可选 `PyYAML`、`matplotlib`、`MDSplus`（惰性加载，不在 PyPI）；
Rust crate `rayon`（可选 `parallel` 特性）。浏览器前端**不携带任何第三方 JavaScript**。
文档以 MyST 构建。

## 参考文献

本项目所用方法均为公开方法。以下按主题列出主要出处；逐模块的对应关系见「移植的上游代码」与「依公开文献转写的物理」。

### 平衡与重构

- 平衡本身是 Grad–Shafranov 方程（Grad 与 Rubin 1958；Shafranov 1966）。
- 由磁测量拟合 p′/FF′ 多项式、并在等离子体电流等式约束下与平衡交替求解，是 Lao 等人
  给出的重构框架：L. L. Lao, H. St. John, R. D. Stambaugh, A. G. Kellman, W. Pfeiffer,
  *Reconstruction of current profile parameters and plasma shapes in tokamaks*,
  Nuclear Fusion **25** (1985) 1611。
- 自由边界求解与垂直位置的稳定处理：S. C. Jardin, *Computational Methods in Plasma
  Physics*, CRC Press, 2010。
- 规则网格上的快速直接解法：R. W. Hockney, *A fast direct solution of Poisson's
  equation using Fourier analysis*, Journal of the ACM **12** (1965) 95。
- 安全因子、形状量等平衡量的定义，以及托卡马克物理的通用背景：J. Wesson, *Tokamaks*,
  4th ed., Oxford University Press, 2011。

### 输运与湍流

- 新经典电导率与自举电流的解析式：O. Sauter, C. Angioni, Y. R. Lin-Liu,
  *Neoclassical conductivity and bootstrap current formulas*,
  Physics of Plasmas **6** (1999) 2834。
- 自举电流的重新标定：
  A. Redl, C. Angioni, E. Belli, O. Sauter, *A new set of analytical formulae for the
  computation of the bootstrap current*, Physics of Plasmas **28** (2021) 022502。
- 解析新经典变体与俘获份额：C. S. Chang, F. L. Hinton, Physics of Fluids **25** (1982)
  1493；Y. R. Lin-Liu, R. L. Miller, Physics of Plasmas **2** (1995) 1666。
- 回旋朗道流体准线性输运模型（TGLF）：G. M. Staebler, J. E. Kinsey, R. E. Waltz,
  *A theory-based transport model with comprehensive physics*,
  Physics of Plasmas **14** (2007) 055909。
- 漂移动理学方程的直接求解（NEO）：E. A. Belli, J. Candy, *Kinetic calculation of
  neoclassical transport including self-consistent electron and impurity dynamics*,
  Plasma Physics and Controlled Fusion **50** (2008) 095010。

### 0-D 集成建模、源项与原子数据

- 能量约束标度律：ITER Physics Basis, Nuclear Fusion **39** (1999) 2175（IPB98(y,2)）；
  P. N. Yushmanov et al., Nuclear Fusion **30** (1990) 1999（ITER89-P）。
- D-T 反应率：H.-S. Bosch, G. M. Hale, *Improved formulas for fusion cross-sections and
  thermal reactivities*, Nuclear Fusion **32** (1992) 611。
- L–H 阈值功率：Y. Martin et al., *Power requirement for accessing the H-mode*,
  Journal of Physics: Conference Series **123** (2008) 012033。
- 0-D 集成建模的对标程序，也是快中性束模型的出处：J. F. Artaud et al.,
  *Metis: a fast integrated tokamak modelling tool*, Nuclear Fusion **58** (2018) 105001。
- 杂质辐射冷却曲线：T. Pütterich et al., Nuclear Fusion **59** (2019) 056013；
  Open-ADAS, <https://open.adas.ac.uk>。
- 中性束停止与电荷交换截面：R. K. Janev, C. D. Boley, D. E. Post, *Penetration of
  energetic neutral beams into fusion plasmas*, Nuclear Fusion **29** (1989) 2125。

## 完整文本

本文为可读的致谢全表。具约束力的、逐文件的声明见：

- 仓根 `LICENSE`——Apache License 2.0 全文
- 仓根 `CONTRIBUTORS.md`——维护者与版权归属

★这两处按**仓内路径**引用而不给链接：它们是许可件，不是本书的章，站点上没有它们
的页面。一条指向书外 `.md` 的 markdown 链接不会 404——MyST 会把那个文件当作原始
Markdown 资源伺服出去，读者拿到的是一个没有版式、也不在目录里的页面。
