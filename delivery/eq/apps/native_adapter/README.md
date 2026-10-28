# 原生求解适配器（native_adapter）

纯磁重构走的是原生内核（`libfylite`）。内核发布只给 `.so`、头文件和 ABI，
**调用它所需的一切由 fylite 自己带**——就是本目录。

## 内容

| 路径 | 作用 |
|---|---|
| `demo.py` | 内核的参考适配器：读装置事实与求解卡，驱动 `libfylite` 反演 |
| `facts/` | 装置事实（`east.jsonld` 静态卡 + `east/` 解析文档与变体） |
| `input/native.json` | 求解卡（几何、纵场、PF 表、拟合模板、求解控制） |
| `input/tables/*.ddd` | 三份装置响应表（`ec129129.ddd`、`ep129129.ddd`、`rfcoil.ddd`，不可在网页修改） |
| `input/diagnostics_*.json`、`M_baseline.json` | 冻结算例输入与基线 |
| `VERSION.json` | 绑定的内核身份（tag / ABI / 两个 .so 的 sha256） |
| `tools/build_package.py` | 组装运行时包（适配器 + 内核 .so + MANIFEST） |
| `tools/check.py` | 校验已部署的运行时包 |

内核 `.so` **不进本仓库**：构建时从内核发布树的 `lib/` 取。

## 构建运行时包

```bash
cd delivery/eq/apps/native_adapter

python3 tools/build_package.py \
    --release-dir /path/to/v0.0.1-alpha-rc3/eq \
    --out /path/to/standalone-rc3-<date>
```

脚本做的事：

1. 校验 `release-dir/lib/` 里两个 `.so` 的 sha256 与 `VERSION.json` 一致（不一致直接退出）；
2. 复制本目录的适配器文件（跳过 `tools/`、`output/`、`__pycache__`）；
3. 把 `libfylite_kernel.so` 复制为 `libfylite.so`、`libsp.so` 原样复制；
4. 把 `demo.py` 的 `LIB_SHA` 重钉为实际 `.so` 的 sha256；
5. 生成 `MANIFEST.sha256.json`（含两个 `.so`）。

## 校验已部署的包

```bash
python3 tools/check.py --package /path/to/standalone-rc3-<date>
```

检查三件事：manifest 逐文件 sha256、两个 `.so` 是否等于 `VERSION.json` 的钉子、
`demo.py` 的 `LIB_SHA` 是否与实际 `.so` 一致。

## 应用侧怎么用

`apps/workflow/archive_v3.py` 通过 `FYLITE_EQ_V3_ROOT` 找到运行时包，并校验：

| 位置 | 钉子 |
|---|---|
| `archive_v3.py` 的 `EXPECTED_LIBRARY` | `libfylite.so` 的 sha256 |
| 包内 `MANIFEST.sha256.json` | 每个文件 |
| `demo.py` 的 `LIB_SHA` | `libfylite.so` |

三处任一不符都会拒绝出结果（「standalone-v3 文件身份不匹配」/「原生库版本不匹配」/「动态库 SHA256 不符」）。

## 升级内核时

1. 改 `VERSION.json` 的 `kernel` 段（tag / ABI / commit / 两个 sha256）；
2. `tools/build_package.py` 构建新包；
3. 切换 `FYLITE_EQ_V3_ROOT` 并重启服务；
4. **注意**：算例的 `case.json` 记录了创建时的包路径与清单哈希，换包后旧算例不能重新求解（只读仍然可以），
   需要重跑或保留旧包目录。

## 出处

`demo.py`、`facts/`、`input/` 来自内核仓库的参考适配器（`kinetic_reconstruction-standalone-v3`），
`LIB_SHA` 已重钉到 rc3 内核。原始说明保留在 `README.standalone.md`。
