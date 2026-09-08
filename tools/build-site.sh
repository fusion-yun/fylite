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
#      ★2026-09-05 裁定（FYL-DESIGN-19 A-14）：**缺省是内部版**——fylite 作为内部
#      工具发布，全功能构建含 EAST。判据一个字没改，改的是「不说话时装哪一版」；
#      公开面因此必须**明写** `--public`，那正是 A-14 要求门禁核对的那句。
#
# 用法：bash tools/build-site.sh [--public|--internal] [输出目录]  （默认 内部版 · dist/site）
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP="$DIR/app"
FLAVOUR=internal
case "${1:-}" in
  --public)   FLAVOUR=public;   shift ;;
  --internal) FLAVOUR=internal; shift ;;
esac
OUT="${1:-$DIR/dist/site}"

#: ★★2026-09-05 起 wasm **按版本命名**（`tools/soname.sh`，与 `.so` 同规矩）：
#: `app/assets/` 里一份字节有三个名字——真文件 `fylite_rs.wasm.0.0.1` 加
#: `.wasm.0` 与 `.wasm` 两级符号链接。版本从 `assets/version.js` 读，那是内核仓
#: 构建写的同一份生成物，所以「站点发的版本」与「页面以为的版本」不可能是两个数。
KVER=$(sed -n "s/.*kernel: *'\([^']*\)'.*/\1/p" "$APP/assets/version.js")
[ -n "$KVER" ] || {
  echo "[site] 读不出 app/assets/version.js 的 kernel 版本 —— 先在内核仓跑构建" >&2
  exit 1; }
#: ★★中间层那一份**版本另有出处**（`assets/runtime-version.js`，本仓 `rust/build.sh`
#: 生成）：它与内核不是同一个版本号。拿内核的版本去找它会永远找不到。
RVER=$(sed -n "s/.*FyRuntimeVersion *= *'\([^']*\)'.*/\1/p" "$APP/assets/runtime-version.js" 2>/dev/null || true)
[ -n "$RVER" ] || {
  echo "[site] 读不出 app/assets/runtime-version.js —— 先跑 bash rust/build.sh" >&2
  exit 1; }
KERNEL_WASM="fylite_rs.wasm fylite_kernel_ext.wasm"
#: ★★2026-09-05：站点发的中间层那一份是 **`fylite_web.wasm`**（0.51 MB，页面真读的
#: 两扇门：装置与 g-file），不是 `fylite_runtime.wasm`（2.14 MB，全套 C 导出）。页面没有任何一处
#: 载入后者——`FYL-DESIGN-16` H-4 的其余消费者（g-file / fyo / 会话搬进中间层）
#: 尚未落地，在那之前发它就是两兆多的死重。小的那一份还**进预缓存**，于是断网时
#: 站点仍然列得出机器（见 `tools/make-sw.mjs` 那段）。
WASM_STEMS="$KERNEL_WASM fylite_web.wasm"
for w in $KERNEL_WASM; do
  [ -f "$APP/assets/$w.$KVER" ] || {
    echo "[site] 找不到 app/assets/$w.$KVER —— 先在内核仓跑 rust/build.sh --wasm-check" >&2
    echo "[site]   （wasm 不入库；内核仓的构建脚本把两份装进公开仓的 app/assets/）" >&2
    exit 1
  }
done
[ -f "$APP/assets/fylite_web.wasm.$RVER" ] || {
  echo "[site] 找不到 app/assets/fylite_web.wasm.$RVER —— 先跑 bash rust/build.sh" >&2
  exit 1; }

#: ★★**版别在编译期定死，发布时挑不了**（2026-09-05 用户裁定：页面也走中间层 wasm，
#: 撤掉 `facts.jsonld`）。装置信息编在那份 wasm 里，所以这里能做的只有**核对**：
#: 手上这一份是哪一版，与要发的这一版是不是同一个。不一致就红着退出并说清怎么重建——
#: 静默发出去的后果是一个标着「公开版」而带着 EAST 的站点。
FLAV=$(sed -n "s/.*FyFactsFlavour *= *'\([^']*\)'.*/\1/p" "$APP/assets/runtime-version.js")
if [ "$FLAV" != "$FLAVOUR" ]; then
  echo "[site] 装着的中间层 wasm 编的是 **$FLAV** 版的装置信息，而这次要发 $FLAVOUR 版。" >&2
  echo "[site]   重建：bash rust/build.sh --$FLAVOUR" >&2
  exit 1
fi

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

#: ★★别名不发（2026-09-05）。上面的 `-L` 是有意的——仓内的链接要解引用，否则静态
#: 主机上就是 404——但对版本化的 wasm，它把**同一份字节拷了三遍**：真文件、
#: `.wasm.0`、`.wasm` 各一兆多。站点因此凭空胖三兆，而没有任何读者会取那两个别名：
#: 页面按版本名取（`app/assets/fylite.js` 的 `versioned()`）。
#: ★删的是别名，不是真文件；下面的自检会核对这一点两头都成立。
#: ★★**中间层的全套那一份不发**（2026-09-05）。`cp -RL` 上面把 `app/` 整棵拷了过来，
#: 而 `fylite_runtime.wasm`（2.14 MB）在站点上**没有任何读者**：页面读装置走
#: `fylite_facts.wasm`，其余的中间层职责（g-file / fyo / 会话，`FYL-DESIGN-16` H-4）
#: 还没搬到页面上。解引用之后它还会变成三份（真文件加两级别名），实测让站点从
#: 12 MB 长到 16 MB。等 H-4 的消费者落地再发它——那时把这一行删掉即可。
rm -f "$OUT"/assets/fylite_runtime.wasm*

ver_of() { [ "$1" = fylite_web.wasm ] && echo "$RVER" || echo "$KVER"; }
#: ★★别名要按**输出目录里实有的**去删，不是按上面那三个名字（2026-09-08 实测）。
#: `$WASM_STEMS` 只列页面必须有的三份，而 `app/assets/` 里还躺着 `fylite_tglf.wasm`
#: 与 `fylite_dke.wasm`（内核仓装的扩展模块，按需载入）。它们不在名单里，于是
#: `cp -RL` 解引用出来的两级别名没人删——实测站点里各三份，白多 1.0 MB。
#: ★所以这里扫真文件：`X.wasm.<版本>` 在，就把 `X.wasm` 与 `X.wasm.<主版本>` 删掉。
for real in "$OUT"/assets/*.wasm.*.*; do
  [ -e "$real" ] || continue
  base=$(basename "$real")                 # fylite_tglf.wasm.0.0.1
  stem=${base%%.wasm.*}.wasm               # fylite_tglf.wasm
  v=${base#*.wasm.}                        # 0.0.1
  rm -f "$OUT/assets/$stem" "$OUT/assets/$stem.${v%%.*}"
done

#: ★★**版别还管一件与装置数据无关的事**（2026-09-05 用户裁定）：头条警示带上的
#: 「仅限内部测试，请勿公开传播！」只属于内部版。公开版把那个 `<span>` 连同两份语料
#: 里的词条整个删掉——照字面的不存在，不是 `display:none`。带子本身留下：它的前半句
#: 「alpha 版，用于概念验证」每一版都成立。
#: ★规则不在本脚本里，在 `tools/app-flavour.mjs`，因为**内嵌进可执行文件的那棵树
#: 就是本脚本装出来的这一棵**（`tools/build-app-exe.sh` 调本脚本）——一处实现，两个
#: 制品按构造同规则，与装置许可判据（`facts-publish.py`）同一分工。
if [ "$FLAVOUR" = public ]; then
  node "$DIR/tools/app-flavour.mjs" --strip "$OUT"
fi
#: ★两版都查，方向相反：公开版查「没有」，内部版查「有」。少了后面这一头，一个把
#: 提示悄悄漏掉的内部版看起来只是干净。
node "$DIR/tools/app-flavour.mjs" --check "$FLAVOUR" "$OUT"

#: ★★**算例按装置权利过滤**（2026-09-08）。`app/cases/` 是给「导入」按钮的实例
#: 会话文档，其中一份是 EAST 的——而公开版的装置语料**不带 EAST**（用户裁定
#: 2026-09-04）。判据不在文件名里，在每份算例自报的 `fylite:device`，与
#: `facts-publish.py` 这一版答应带的那几台比对：一份算例不能把装置语料判出去的
#: 机器从旁门带回来。★装置为空的算例（解析几何）不受影响。
if [ -d "$OUT/cases" ]; then
  ALLOWED=$(python3 "$DIR/tools/facts-publish.py" --flavour "$FLAVOUR" --list \
            | sed -n 's|^device/||p' | tr '\n' ' ')
  python3 - "$OUT/cases" "$ALLOWED" <<'PY'
import json, os, sys
d, allowed = sys.argv[1], set(sys.argv[2].split())
dropped = {}
for name in sorted(os.listdir(d)):
    if not name.endswith('.jsonld') or name == 'catalogue.jsonld':
        continue
    doc = json.load(open(os.path.join(d, name), encoding='utf8'))
    dev = (doc.get('fylite:case') or {}).get('fylite:device')
    if dev and dev not in allowed:
        os.remove(os.path.join(d, name))
        dropped[name] = dev
cat = os.path.join(d, 'catalogue.jsonld')
if os.path.exists(cat):
    c = json.load(open(cat, encoding='utf8'))
    keep = [e for e in c.get('fylite:cases', [])
            if e.get('fylite:document') not in dropped]
    c['fylite:cases'] = keep
    with open(cat, 'w', encoding='utf8') as f:
        json.dump(c, f, indent=1, ensure_ascii=False); f.write('\n')
#: ★过滤完再查一遍：留下的每一份都要么不点装置，要么点的是这一版带的。
#: 「删对了」不是判据，「没删干净会喊」才是。
left = []
for name in sorted(os.listdir(d)):
    if not name.endswith('.jsonld') or name == 'catalogue.jsonld':
        continue
    doc = json.load(open(os.path.join(d, name), encoding='utf8'))
    dev = (doc.get('fylite:case') or {}).get('fylite:device')
    if dev and dev not in allowed:
        left.append(name + '（' + dev + '）')
if left:
    print('[site] 算例过滤没干净：' + '、'.join(left), file=sys.stderr)
    raise SystemExit(1)
if dropped:
    print('[site] 算例：撤下 ' + '、'.join(
        '%s（%s）' % (k, v) for k, v in sorted(dropped.items())))
else:
    print('[site] 算例：%d 份全部可发' % len(
        [n for n in os.listdir(d) if n.endswith('.jsonld')]))
PY
fi

#: ★★**许可义务随发行件同行**（Apache-2.0 §4(d)，2026-09-08）。发出去的站点带着
#: `fylite_rs.wasm` 与 `fylite_kernel_ext.wasm`——它们正是 GACODE 白盒移植的编译
#: 产物——所以这一份目录**是一次分发**，§4(d) 附着在它上面，与轮子那一头
#: （`tools/build-wheel.sh`）是同一条义务、同一种做法：
#:   · `LICENSE` 取本仓的（Apache-2.0 全文）；
#:   · `NOTICE` **本仓没有**（`095374f` 裁定：它描述内核源码，随源码留在
#:     `fylite_kernel`），构建时自内核检出借入。
#: ★借不到就**红着退出**，不是少发一个文件了事：一份不带署名的分发不满足 §4(d)，
#: 而那种失败没有任何一步会自己喊——站点照常上线，只是少了一份文件。
cp "$DIR/LICENSE" "$OUT/LICENSE"
. "$DIR/tools/kernel-path.sh"
if fylite_resolve_kernel "$DIR" && [ -f "$KERNEL/NOTICE" ]; then
  cp "$KERNEL/NOTICE" "$OUT/NOTICE"
  echo "[site] NOTICE：自 $KERNEL 借入（§4(d) 附着在分发件上）"
else
  echo "::error:: 找不到 NOTICE —— 站点带着 GACODE 派生的 wasm，" >&2
  echo "  那样分发不满足 Apache-2.0 §4(d)。" >&2
  echo "  给 FYLITE_KERNEL=/path/to/fylite_kernel 再来一次。" >&2
  exit 1
fi

#: ★★**站点不再发装置文档**（2026-09-05 用户裁定）。它们编在 `fylite_web.wasm` 里，
#: 页面经那份 wasm 读（`app/assets/factsdb.js`）。此前这里调 `facts-publish.py` 逐台发
#: JSON，于是同一批 432 KB 在制品里有两份、两条通路，而没有任何东西保证它们描述同一批
#: 机器。许可闸没有松：它在 `rust/build.sh` 那一步施用（`--public` / `--internal`），
#: 上面那段核对确保这次发的与编进去的是同一版。

#: 自检
bad=0
[ ! -e "$OUT/tests" ] || { echo "[site] 输出里有 tests/" >&2; bad=1; }
[ ! -e "$OUT/server" ] || { echo "[site] 输出里有 server/" >&2; bad=1; }
while IFS= read -r -d '' l; do echo "[site] 悬空链接：$l" >&2; bad=1; done \
  < <(find "$OUT" -xtype l -print0)
#: ★别名一个都不该剩：上面按真文件删过，这里按真文件再查一遍（两头同一条规则）。
for real in "$OUT"/assets/*.wasm.*.*; do
  [ -e "$real" ] || continue
  base=$(basename "$real"); stem=${base%%.wasm.*}.wasm; v=${base#*.wasm.}
  for alias in "$stem" "$stem.${v%%.*}"; do
    [ ! -e "$OUT/assets/$alias" ] || {
      echo "[site] 输出里有别名 assets/$alias（应只发版本化的真文件）" >&2; bad=1; }
  done
done
for w in $WASM_STEMS; do
  v=$(ver_of "$w")
  [ -s "$OUT/assets/$w.$v" ] || { echo "[site] 输出里缺 assets/$w.$v" >&2; bad=1; }
  #: ★★两级别名**不该**留在站点里：`cp -RL` 把它们解引用成第二、第三份一兆多的
  #: 字节，站点凭空胖三兆，而没有任何读者会取它们——页面按版本名取
  #: （`app/assets/fylite.js` 的 `versioned()`）。上面已经删过，这里把「不该有」
  #: 变成一条会失败的断言，而不是一句注释里的保证。
  for alias in "$w" "$w.${v%%.*}"; do
    [ ! -e "$OUT/assets/$alias" ] || {
      echo "[site] 输出里有别名 assets/$alias（应只发版本化的真文件）" >&2; bad=1; }
  done
done
[ -s "$OUT/index.html" ] || { echo "[site] 输出里缺 index.html" >&2; bad=1; }
#: ★许可与署名：上面已经装过，这里把「装到了」变成一条会失败的断言。
[ -s "$OUT/LICENSE" ] || { echo "[site] 输出里缺 LICENSE" >&2; bad=1; }
[ -s "$OUT/NOTICE" ]  || { echo "[site] 输出里缺 NOTICE（Apache-2.0 §4(d)）" >&2; bad=1; }
#: ★把「不发那一份」变成一条会失败的断言，而不是一句注释里的保证。
[ ! -e "$OUT/assets/fylite_runtime.wasm.$RVER" ] || {
  echo "[site] 输出里有 fylite_runtime.wasm（站点没有读者，见上面那段）" >&2; bad=1; }
[ "$bad" = 0 ] || exit 1

n=$(find "$OUT" -type f | wc -l)
sz=$(du -sh "$OUT" | cut -f1)
echo "[site] $OUT：$n 个文件，$sz"
echo "[site] 本机预览：python3 -m http.server -d $OUT 8000   （静态：无 /api/*）"
echo "[site] 动态预览：fylite --app-dir $OUT            （同一份字节 + /api/*）"
