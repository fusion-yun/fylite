# 动理学反演演示（内部独立包）

页面提供常用参数和完整 JSON 编辑、实际原生反演、完整磁面、压力/F/q 条件误差范围、磁诊断原信号误差棒、PF 电流和收敛历史。与磁反演 M 保存基线及 KEFIT 存档比较。详细字段、单位、来源、误差定义和操作说明已写入 `index.html`。

## 直接调用，不经过 HTML

Linux x86-64、AVX2（x86-64-v3），Python 3.10+。**仅用 Python 标准库**；预设压力离线运行不需要 NumPy、Matplotlib、浏览器、Fortran、Rust 工具链或网络下载。诊断阶梯另加载随包libsp，其系统动态依赖见下文。

在本目录执行：

```bash
python demo.py --run input/native.json --pressure input/pressure_onetwo.json --out output/my_run.json
```

计算通过随包 `libfylite.so` 的标准 `fylite_rs_fyo_json("code/kinetic", ...)` 完成，无第二个求解动态库。默认案例约30秒、55轮收敛（具体耗时随机器变化）。返回0表示收敛，2表示计算完成但未收敛，1表示输入/运行错误。所有已有输出拒绝覆盖；改变 `--out` 或省略它使用自动生成的新路径。

输出为 `my_run.json`、`my_run.input.json`、`my_run.identity.json`。身份文件保存实际输入、输出、动态库和响应表 SHA256、UTC创建时间及耗时。初始 PF 观测/权重与共享 Ip 在 Python 中同步为用户输入，实际配置单独保存。

## 可预设压力

页面可加载ONETWO原51点压力，或导入独立压力JSON（含psi_N、pressure_Pa、sigma_Pa、来源和可选fit_weights）。命令行通过`--pressure FILE`使用同一格式。不填造缺失误差，不接受来自当前反演输出的自约束；预设是带误差的拟合观测，结果并非强制等于输入。

- `input/pressure_onetwo.json`：现有ONETWO预设。
- [INTERACTION_DESIGN.md](INTERACTION_DESIGN.md)：已启用的EAST MDSplus与诊断配方，以及q₀/边界后续规划和能力边界。
- [PRESSURE_ASSESSMENT.md](PRESSURE_ASSESSMENT.md)：fylite压力组装替代ONETWO的证据、所需输入和限制。

独立CLI载入ONETWO预设已验证55轮收敛，输出与原基线精确相同。自定义源信息写入实际输入、页面和运行身份对应文件。预设来源schema示例及各字段说明见HTML。

## HTML 编辑与计算

```bash
python demo.py --serve --port 8765
```

浏览器打开 **http://127.0.0.1:8765**。修改参数或 JSON，点击“执行反演”；服务只监听本机，单次只执行一个反演。结果成功返回后更新图；失败时保留旧图并显示错误。Ctrl+C 停止服务。

直接双击 `index.html` 也能离线查看、编辑、导入/下载输入和保存可视化数据。离线 HTML 不能直接加载本机 `.so`；计算须用命令行或上述服务。普通静态 HTTP 服务不提供反演 API。

将命令行结果更新为 HTML 的内置保存结果：

```bash
python demo.py --build-html --out output/my_run.json
```

它读取配套输入和身份文件，校验输入/输出哈希后重绘 HTML；不重新求解、不依赖绘图库。省略 `--out` 则使用随包 `output/baseline.json`。图表可导出 SVG，整个输出视图可打印/保存 PDF。下载的可视化 JSON 包含配套输入，可重新导入离线页面。

## 文件布局

- `demo.py`：唯一 Python 文件，命令行、HTTP 服务和 SVG 数据准备。
- `index.html`：唯一 HTML，内嵌离线结果；全部图表使用原生 SVG，无 CDN。
- `libfylite.so`：合并后的原生内核，执行前校验 SHA256。
- `libsp.so`：固定发布0.1.0+01d4861b的数据层；MDSplus和诊断模式使用。
- `facts/device/east*`：按炮/测量链解析的内部EAST装置事实。
- `input/diagnostics_local.json`：#94048存档磁输入，缺少POINT和TS；选择相应配方会报错。
- `input/diagnostics_MP_cached.json`：本次真实MDSplus读取的#137985、4.041s磁+TS缓存；支持无网络MP演示，明确标记缓存来源。
- `input/native.json`：可编辑原始配置。
- `input/tables/`：三份必须保留的装置响应表（不能通过网页修改）。
- `input/reference.json`、`input/M_baseline.json`：固定参考和磁反演保存基线，仅用于对比，不进入动理学拟合。
- `input/fytok_logo.png`：原制图资产。
- `output/`：随包实际计算基线及新运行记录。
- `MANIFEST.sha256.json`：打包时的文件身份；自行运行或重绘 HTML 后输出会变化。

## 适用范围与误差解释

兼容模式固定原129×129网格、12组PF、35磁通环、76探针槽（前36物理槽、后40补零）、原张力样条节点及其历史归一化。输入文件名标识明确旧每弧度磁通约定，输出磁通转换为 COCOS17 整圈 Wb。F=RBφ 为带符号量；本例为负，σ非负。

磁环残差使用等离子体磁通**加拟合后的 PF 磁通**。磁/PF误差棒为原假定3%，压力为SIGPRE；蓝色阴影在 measurement 模式下为固定几何测量传播±1σ，objective 模式下为曲率条件σ。绿色M带为原生产库的曲率条件σ；其源内核身份保存在M基线中。M和KEFIT均不会随页面新输入重算。

压力取已有 ONETWO 6.510 s 输出，平衡时刻5.760 s，未重跑ONETWO。整体重构置信区间尚未得到验证。Te/Ti原始诊断的通道、时间和误差数据不足，本包不伪造这些误差棒，也不将压力反演等同于独立Te/Ti反演。该段仅描述预设压力复现模式；诊断模式已支持POINT实际拟合。

仓内目录 `examples` 已改名为 `demo`；原文档下的 `docs/user/examples` 和历史归档路径保持原位置。此包是内部演示与验证制品，不代表公开发布；实验输入、运行输出和动态库在该目录下被 Git 忽略，仍完整包含在独立ZIP中。

## MDSplus 与诊断配方（已启用）

页面选择 M / MK / MP / MKP，选择 EAST MDSplus、设置炮号和时间（s），点击读取，成功后再执行反演。也可导入诊断JSON。读取失败保留旧输入和输出；不以ONETWO替代缺失的POINT/TS。

```bash
python demo.py --pull --recipe M --shot 94048 --time 5.760 --out output/mds.json
python demo.py --run input/native.json --diagnostics output/mds.json --recipe M --out output/M.json
python demo.py --run input/native.json --diagnostics input/diagnostics_local.json --recipe M --out output/local-M.json
python demo.py --run input/native.json --diagnostics input/diagnostics_MP_cached.json --recipe MP --out output/cached-MP.json
```

沿用202.127.204.12:8000；--server显式覆盖，或设置FYLITE_MDSIP_SERVER；用户名用FYLITE_MDS_USER/USER。MDSplus为只读，数据层固定libsp.version版本并通过发布SHA256SUMS检查。需要Linux系统libnetcdf.so.19、libhdf5_serial.so.103及其依赖；内核仍只用libfylite.so。

诊断JSON结构为 `{ "recipe":"MP", "inputs":{"device":{},"measurements":{},"thomson":{},"options":{}},"settings":{} }`，也接受标准settings/inputs请求。device是本炮装置文档；磁测量含brsp（A·turn）、coils（旧Wb/rad）、expmp2（T）、fwtmp2、plasma（A）与tf/btor。POINT需bnel、bpolar、fwtnel、fwtpol等长有效数组；TS需r/z（m）、te（eV）、ne（m⁻³）、te_err/ne_err等长逐点实测误差。先保存原读取，再在独立运行输入中记录B-6/B-7几何、材料、被动模型与网格的显式转换，不修改事实源。

诊断模式的参数在workflow.inputs.options及workflow.settings编辑，原兼容参数表禁用。M→K→P都在Rust内执行；各档失败、动理学外环未收敛或物理检查不通过保留记录，退出2，不降档冒充成功。Te/ne显示原误差；拟合的是热压力，Ti由声明的闭合模型参与，不能解释为独立Te/ne反演。磁误差采用5%及位下限，POINT使用既有归约误差模型；各档磁通图使用整圈Wb，磁环展示由旧Wb/rad显式×2π。当前诊断阶梯F输出为幅值，界面写作|F|；带符号F及压力/F/q条件带仍由兼容复现模式提供。

已验证：MDSplus实际连接、#94048磁诊断与#137985磁+30点TS及原误差批量读取；77项kinetic测试；MP已知合成案例、MK/MKP的#137985存档实际执行；浏览器MP导入/执行/绘图/移动端；#137985在线MP读取并实际求解收敛。#94048存档纯磁结果被标为unphysical，在线磁输入在默认扫描下未收敛，均保留原因/尝试；不能以配方可执行声称每个输入均得到有效平衡。验证证据：workspace/output/kinetic-reconstruction-package-qa/validation_summary_v3.json。

在线#137985 MP通过数值和映射收敛判据，但TS清洗被内核标记为可疑（剔除比例/连续芯部拒点）；页面显式显示诊断质量警报。跑通、收敛不等于已验证实验剖面，不能将该结果当作诊断质量认证。
