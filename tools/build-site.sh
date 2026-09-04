#!/usr/bin/env bash
# 发布类型二：**静态网页**——`app/` 的发布子集，任何静态服务器都能伺服的一个目录。
#
# 与另两条通道的分工（FYL-DESIGN-15 tbl-fylite-release-forms）：
#   单一可执行文件  —— tools/build-app-exe.sh：同一份 app/ 内嵌进一个程序，起本机服务
#   Python 包       —— tools/build-wheel.sh
#   本脚本          —— 给联网的人，零安装：一个目录，放到 GitHub Pages / 任何静态主机
#
# ★「动态网页」没有自己的构建：它是**同一份字节**由 `fylite`（= `fylite app`）伺服，
# 并多答一组 `/api/*`；页面用 `/api/health` 是否回答来判别，不看主机名（assets/host.js）。
# 所以这个目录与可执行文件内嵌的那张表（`tools/make-app-embed.mjs`）取的是**同一个子集**：
# 去 `tests/`、去 `server/`——发出去的站点不该比可执行文件多，也不该少。
#
# 三件事，都是「不做的后果只有别人才会发现」的那种：
#   1. 三个 wasm 必须在（它们不入库：内核仓 `rust/build.sh --wasm-check` 装进
#      `app/assets/`）——漏了的站点首页能开，场景页在第一次算数时以一句 TypeError 失败；
#   2. 装置牌 `app/facts/device/*.jsonld` 在仓里可能是指向 `machine_desc/` 的符号链接，
#      发布要 `cp -L` 落成实体——一个指向仓外的链接在静态主机上是一个 404；
#   3. 输出目录里不能有悬空链接或 `tests/`。
#
#   4. ★★2026-09-04 起构建分**公开版**与**内部版**（用户裁定）：公开版不带 EAST
#      装置数据（一次真实放电 #137985 的实测读数，属运行方），也不带上游逐 IDS
#      明写 `redistributable: false` 的那些。判据不在本脚本里，在每个条目的
#      `facts/<域>/<id>/rights.json`，由 `tools/facts-publish.py` 作答。
#
# 用法：bash tools/build-site.sh [--internal] [输出目录]   （默认 公开版 · dist/site）
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP="$DIR/app"
FLAVOUR=public
if [ "${1:-}" = "--internal" ]; then FLAVOUR=internal; shift; fi
OUT="${1:-$DIR/dist/site}"

for w in fylite_rs.wasm fylite_tglf.wasm fylite_dke.wasm; do
  [ -f "$APP/assets/$w" ] || {
    echo "[site] 找不到 app/assets/$w —— 先在内核仓跑 rust/build.sh --wasm-check" >&2
    echo "[site]   （wasm 不入库；内核仓的构建脚本把三份装进公开仓的 app/assets/）" >&2
    exit 1
  }
done

rm -rf "$OUT"
mkdir -p "$OUT"
#: 发布子集：与 make-app-embed.mjs 的 SKIP 同一份名单。
#: ★★`facts` 也跳过——它是**指向仓根 `facts/` 的符号链接**（2026-09-04 用户裁定：
#: 单一数据源），而那个目录装的是整个语料：逐个的卡片、许可账、以及只进内部版的条目。
#: `cp -RL` 会把它整棵解引用拷出去，那正是这次要防的事。装置文档改为按规则**逐份发**。
(cd "$APP" && find . -mindepth 1 -maxdepth 1 ! -name tests ! -name server ! -name facts -print0) \
  | while IFS= read -r -d '' entry; do
      #: `-L`：仓内其它链接一并解引用（静态主机上一条指向仓外的链接就是 404）
      cp -RL "$APP/$entry" "$OUT/${entry#./}"
    done

#: ★★**一条规则，一处实现**：谁进这一种构建，由 `tools/facts-publish.py` 作答
#: （它读每个条目的 `facts/<域>/<id>/rights.json`）。本脚本不自己判许可——两个地方各判
#: 一遍，某一天它们会给出不同的答案，而先发现的人是拿到制品的那个。
python3 "$DIR/tools/facts-publish.py" --flavour "$FLAVOUR" --out "$OUT"

#: 自检
bad=0
[ ! -e "$OUT/tests" ] || { echo "[site] 输出里有 tests/" >&2; bad=1; }
[ ! -e "$OUT/server" ] || { echo "[site] 输出里有 server/" >&2; bad=1; }
while IFS= read -r -d '' l; do echo "[site] 悬空链接：$l" >&2; bad=1; done \
  < <(find "$OUT" -xtype l -print0)
for w in fylite_rs.wasm fylite_tglf.wasm fylite_dke.wasm; do
  [ -s "$OUT/assets/$w" ] || { echo "[site] 输出里缺 assets/$w" >&2; bad=1; }
done
[ -s "$OUT/index.html" ] || { echo "[site] 输出里缺 index.html" >&2; bad=1; }
[ "$bad" = 0 ] || exit 1

n=$(find "$OUT" -type f | wc -l)
sz=$(du -sh "$OUT" | cut -f1)
echo "[site] $OUT：$n 个文件，$sz"
echo "[site] 本机预览：python3 -m http.server -d $OUT 8000   （静态：无 /api/*）"
echo "[site] 动态预览：fylite --app-dir $OUT            （同一份字节 + /api/*）"
