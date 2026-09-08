#!/usr/bin/env bash
# 把在线演示发到公开主机（`fusion-yun.github.io`）的**准备工序**：
# 构建 → 过闸 → 落进站点仓的工作树，**到此为止**。提交与推送由人来按。
#
#   bash tools/publish-site.sh [站点仓路径]        # 缺省 ../fusion-yun.github.io
#
# ★★**为什么这是本机脚本，不是一条 GitHub Action**（2026-09-08）。分仓之后本仓
# 不含任何 wasm（`.gitignore` 里 `*.wasm.*`），它们由**私有仓** `fylite_kernel`
# 的构建装进 `app/assets/`。于是一台只检出本仓的托管 runner **根本构建不出站点**；
# 要让它能，就得把私有源码交给它——为发一个公开页面而扩大私有源码的暴露面，方向
# 反了。所以发布跑在两个检出都已经在的那台机器上，而这个脚本负责把「跑对」变成
# 一串不能跳过的步骤。
# ★分仓那天丢掉的正是这一条：旧的 `.github/workflows/publish-app.yml` 留在了老仓，
# 于是 2026-09-02 之后**没有任何发布路径**，而这件事不会自己喊——站点只是停在
# 上一次有人手工拷过去的那一版。
#
# ★★**只发公开版**。`FYL-DESIGN-19` A-14 定的是「不说话时装内部版」，那条缺省是
# 给本机用的；发到公开主机的这条路上，缺省必须反过来。传 `--internal` 会被拒绝，
# 而不是被照办——把一个带 EAST 装置数据、带「仅限内部测试」提示的构建推上公网，
# 是这条路上唯一不可挽回的错误（撤下来的字节已经被人取走了）。
#
# 做完什么、没做什么：
#   做   构建公开版站点、跑三道不需要浏览器的闸子、把 `fylite/` 整个换掉、报告增删
#   不做 `git add` / `git commit` / `git push` —— 曝光时机是人的决定，不是脚本的
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
SITE=""
for a in "$@"; do
  case "$a" in
    --internal)
      echo "::error:: 公开主机上只发公开版。" >&2
      echo "  内部版带 EAST 装置数据与「仅限内部测试」提示词；本机预览用" >&2
      echo "  bash tools/build-site.sh --internal dist/site 即可，不必经这条路。" >&2
      exit 1 ;;
    --public) ;;
    -*) echo "::error:: 不认识的开关：$a" >&2; exit 1 ;;
    *)  SITE="$a" ;;
  esac
done
SITE="${SITE:-$(cd "$DIR/.." && pwd)/fusion-yun.github.io}"

#: ★先认门再动手：`rm -rf "$SITE/fylite"` 指错地方的代价是删掉别人的目录。
#: 判据是站点仓自己的两份东西，不是路径长得像。
[ -f "$SITE/_config.yml" ] && [ -f "$SITE/index.md" ] || {
  echo "::error:: $SITE 看着不是站点仓（缺 _config.yml 或 index.md）" >&2
  echo "  用法：bash tools/publish-site.sh [站点仓路径]" >&2
  exit 1; }

echo "== 一、闸子（不需要浏览器的那几道）"
node "$DIR/tools/make-app-pages.mjs" --check
node "$DIR/app/tests/validate-site.mjs"
node "$DIR/tools/make-sw.mjs" --check
echo "   ★浏览器闸子（validate-offline / validate-published）不在这里跑：它们要"
echo "     playwright 与一个 chromium，是操作者的东西，不是本仓的依赖。"

echo
echo "== 二、构建公开版"
OUT="$DIR/dist/site-publish"
bash "$DIR/tools/build-site.sh" --public "$OUT"

echo
echo "== 三、换掉站点仓里的 fylite/"
OLD="$SITE/fylite"
#: ★★旧的 `fylite/LICENSE` 只存在于站点仓，而它写的是「Binary Redistribution
#: License · source not published · 不得修改」——与本仓今天的 Apache-2.0（页脚也
#: 这么印）互相矛盾。构建现在自己装 `LICENSE` 与 `NOTICE`，所以这次替换正是那份
#: 旧通告该走的时候；说一句，是为了让替换是**看见了才做**，不是顺手覆盖掉。
if [ -f "$OLD/LICENSE" ] && ! cmp -s "$OLD/LICENSE" "$OUT/LICENSE"; then
  echo "   ★站点上原有一份不同的 LICENSE，本次将被构建装入的那份替换："
  echo "     旧 $(head -1 "$OLD/LICENSE")"
  echo "     新 $(head -1 "$OUT/LICENSE")"
fi
before=$(find "$OLD" -type f 2>/dev/null | wc -l)
rm -rf "$OLD"
cp -R "$OUT" "$OLD"
after=$(find "$OLD" -type f | wc -l)
echo "   $OLD：$before -> $after 个文件"

echo
echo "== 四、看一眼再决定"
git -C "$SITE" add -A -n -- fylite >/dev/null 2>&1 || true
echo "   增删改（站点仓工作树）："
git -C "$SITE" status --short -- fylite | head -20
n=$(git -C "$SITE" status --short -- fylite | wc -l)
[ "$n" -gt 20 ] && echo "   …共 $n 行"
cat <<EOF

   本脚本到此为止 —— 没有 add、没有 commit、没有 push。
   要发出去：
     git -C "$SITE" add fylite
     git -C "$SITE" commit -m "chore: sync fylite/ from fylite@$(git -C "$DIR" rev-parse --short HEAD)"
     git -C "$SITE" push git@github.com:fusion-yun/fusion-yun.github.io.git main
   推上去之后，用发布闸对着**线上那个地址**再判一次（它判的是发布，不是源）：
     node app/tests/validate-published.mjs --playwright <装有 playwright 的目录>
EOF
