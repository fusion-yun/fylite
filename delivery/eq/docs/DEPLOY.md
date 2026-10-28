# 部署与发布流程

本文说明 `delivery/eq`（开发源）、rc3 内核发布、以及线上部署点三者之间的关系，以及一次改动的完整上线步骤。

## 一、三层结构

```
D:\workspace_codex\fylite\delivery\eq\          开发源（git，分支 develop）
        │  提交 + scp
        ▼
/project/FyLite/v0.0.1-alpha-rc3/eq/           内核发布树（72 文件，只读基线，不要改）
        │  cp -a 再叠加
        ▼
/project/FyLite/v0.0.1-alpha-rc3/eq-ui-20261028/   线上部署点（rc3 + UI 叠加，79 文件）
```

要点：

- **rc3 是内核发布版本**，包含 `bin/`、`lib/`、`server/`、`tests/`、`licenses/` 和 `release-manifest.json`。它是基线，任何情况下都不直接修改。
- **部署点 = rc3 的完整拷贝 + UI 叠加**。这样内核部分永远和发布一致，差异可枚举。
- **开发源 `delivery/eq` 不是 rc3 的产物**：它缺少发布打包层（bin/lib/licenses/tests），并且带有 rc3 里还没有的新文件。不要直接拿它和 rc3 做等价比较。

## 二、一次改动的完整步骤

### 1. 本地修改并验证

```bash
cd /mnt/d/workspace_codex/fylite

# JS 语法
node --check delivery/eq/ui/assets/magnetic-live.js
node --check delivery/eq/ui/assets/eq-plots.js

# Python 语法（注意不能有 BOM）
python3 -c "import ast; ast.parse(open('delivery/eq/apps/workflow/magnetic_live.py',encoding='utf-8').read())"
```

### 2. 提交

```bash
git add delivery/eq/<改动的文件>
git commit -m "feat(eq): <一句话说明>"
```

未跟踪文件必须先 `git add`——`delivery/eq` 的历史上有过整批文件处于 untracked 状态，一次 `git clean -fd` 就会丢。

### 3. 部署到线上树

```bash
R=/project/FyLite/v0.0.1-alpha-rc3/eq-ui-20261028
cd /mnt/d/workspace_codex/fylite/delivery/eq

scp ui/assets/magnetic-live.js  NewShenma-direct:$R/ui/assets/
scp apps/workflow/magnetic_live.py NewShenma-direct:$R/apps/workflow/
```

只传改动的文件，不要整目录覆盖——会覆盖掉 rc3 的 `bin/`、`lib/`、`licenses/`。

### 4. 是否需要重启

| 改动 | 重启 | 说明 |
|---|---|---|
| `ui/**`（html/js/css） | 不要 | 静态文件，浏览器刷新即可 |
| `apps/workflow/*.py` | **要** | Python 启动时载入模块 |
| `bin/`、环境变量 | 要 | |

### 5. 重启（仅后端改动时）

```bash
ssh NewShenma-direct "/project/FyLite/v0.0.1-alpha-rc3/eq-ui-20261028/restart-8765.sh"
```

脚本做的事：

1. 找到占用 8765 的进程并 kill；
2. 导出五个必需环境变量：

   ```bash
   FYLITE_EQ_DATA=/project/FyLite/data/eq/east94048/v1
   FYLITE_EQ_V3_ROOT=/project/FyLite/artifacts/standalone-v3-20261027
   FYLITE_EQ_V3_M02_INPUT=/project/FyLite/data/eq/east164437/v1/diagnostics.json
   FYLITE_EQ_V3_DEPS=/project/FyLite/records/eq-multicase-v3-20261027/deps/usr/lib/x86_64-linux-gnu
   LD_LIBRARY_PATH=$FYLITE_EQ_V3_DEPS
   ```

   **缺 `FYLITE_EQ_V3_ROOT` 或 `FYLITE_EQ_V3_DEPS` 会让页面报「standalone-v3 包路径未配置」或「隔离 netCDF/HDF5 依赖未配置」。**

3. `nohup` 启动，日志追加到 `server-puremag.log`；
4. 检查端口和 `/api/info`，失败则打印日志尾部并退出非零。

### 6. 冒烟检查

```bash
# 服务活着
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/fylite/eq/api/info   # 期望 200

# 环境变量齐（这两个接口只有在包路径/依赖正确时才返回）
# readiness 必须为 True
GET /fylite/eq/api/workflow/archive-magnetic-info
GET /fylite/eq/api/workflow/archive-magnetic-dd?case_id=<case_id>   # 期望返回 12 个节点
```

本地访问：

```bash
ssh -N -L 18765:127.0.0.1:8765 NewShenma-direct
# 页面 http://127.0.0.1:18765/fylite/eq/ui/magnetic-live.html
```

### 7. 回归基准

改动涉及计算或数据处理时，用固定算例核对：

| 项 | 期望值 |
|---|---|
| 算例 | EAST 164437 / 6.301 s / m02_pinned |
| 数值状态 | converged |
| 门禁 | passed（15/15） |
| 迭代 / 残差 | 262 / 4.02869e-9 |
| q₀ / q₉₅ | 2.69601 / 2.18070 |
| χ²·mag | 364.468 |
| 拟合道数 | 79 |

任何一项对不上，说明改动影响了计算链路。

## 三、回滚

部署点是整棵目录，回滚即换回旧目录：

```bash
# 旧部署点（2026-10-27 的候选，仍可用）
/project/FyLite/v0.0.1-alpha-rc3/eq-v3cases-20261027

# 切换方式：改 restart-8765.sh 里的 R=，然后执行
```

纯前端回滚不需要重启：

```bash
scp /project/FyLite/.staging/eq-tree-20261028/magnetic-live.js.bak NewShenma-direct:$R/ui/assets/magnetic-live.js
```

## 四、已知注意事项

1. **`release-manifest.json` 尚未重建**。它是发布内容 + 哈希清单，叠加 UI 后已过期。正式出 rc4 时应由发布流程重新生成，不要手工改。
2. **`result.input.json` 里的 `btor` 恒为 −1.608**（来自 94048 数据集模板）。跨炮号计算会因此不收敛；修法见 `docs/research-94048/` 与后续的 Bt 采集改动。
3. **不要改 `input/native.json` 那个共享文件**——它是符号链接指向发行包，改一次所有算例一起变。按炮号设参数要走「每算例一份拷贝」。
4. **Python 文件不能有 BOM**。用 PowerShell 写文件时要用 `[IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding($false)))`，`Set-Content -Encoding UTF8` 会加 BOM，导致 `ast.parse` 失败。
5. **重启必须带环境变量**，直接 `nohup ./bin/fylite-eq serve ...` 会丢环境，页面报包路径未配置。
