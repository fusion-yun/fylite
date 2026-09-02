#!/usr/bin/env bash
# 把 `docs/guide/` 里 `public.yml` 点名的那几篇编译成静态 HTML，落进 `app/guide/`，
# 随浏览器演示一同发布。
#
# 渲染由 **MyST 自己的解析与渲染库**完成（`myst-parser` + `myst-to-html`）；
# 外壳套站点自己的样式。为什么不是 `myst build --html`：那条路要从
# `api.mystmd.org` 下载站点模板，给发布链加一个远端依赖——而产物入库的意义
# 正是任何人离线也能重建并逐字比对；何况 book-theme 自带一整套与本站无关的
# 设计系统。理由与实现都写在 `tools/make-guide-pages.mjs` 抬头。
#
# 为什么产物入库：`app/` 的其余生成物（三张说明页、三个 .wasm）也入库，
# 而发布流水线只做拷贝与逐字校验、不做构建。
#
# 为什么只发布一个子集：发布面不同，但那不必是两本书。`docs/guide/` 一本书，
# 里面既有仓内章节（引设计集编号与仓内路径），也有面向使用者的那几篇；
# `public.yml` 划的正是这条线。2026-09-01 之前它是独立的 `docs/user_guide/`，
# 收编进 `guide/` 后这条线由那张表继续管着。
#
# 用法：bash tools/build-guide.sh [--check]
#   --check  只比对，不写入（给门用）
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
command -v node >/dev/null || { echo "[guide] 需要 node" >&2; exit 1; }

# 渲染库装在 `tools/node_modules`（gitignore 掉）——ESM 的裸模块解析是按**导入方
# 所在目录**逐级向上找 `node_modules` 的，不认 `NODE_PATH`，所以这是让
# `tools/*.mjs` 能 `import 'myst-parser'` 的自然位置；装在别处再指过去都要靠
# 内部路径，那种写法会在库改目录结构的那天断掉。装过就复用，不重复下载。
DEPS="$DIR/tools/node_modules"
if [ ! -d "$DEPS/myst-to-html" ] || [ ! -d "$DEPS/myst-parser" ]; then
  echo "[guide] 取渲染库（myst-parser / myst-to-html）…"
  ( cd "$DIR/tools" && npm i --silent --no-fund --no-audit --no-save \
      myst-parser@1.7.3 myst-to-html@1.7.3 >/dev/null )
fi

node "$DIR/tools/make-guide-pages.mjs" "$@"
