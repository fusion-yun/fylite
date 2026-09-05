#!/usr/bin/env bash
# 构建 fylite 的**中间层** `rust/fylite_runtime/`（格式 · 装配 · 计划→内核→记录 · 内核加载 ·
# Rust 命令行 · app 伺服）。★2026-09-04 两次改名：`fylite_data` → `fylite_engine` → `fylite_runtime`
# （FYL-DESIGN-16 N-1 / N-2）。`data` 只说了六项职责里的两项；`engine` 与 Python 包 `fylite.engine`
# 撞词，而那是另一个组件（DE-COMP-03 执行与溯源机械核）。
#
#   ./rust/build.sh              -> libfylite_runtime.so.<版本>，装进 python/fylite/_lib/
#                                   （附 .so.<major> 与 .so 两级符号链接，见 tools/soname.sh）
#   ./rust/build.sh --exe        -> 另外构建**唯一的可执行文件** fy（内嵌整个 app/，
#                                   并承载 app / data / run / list 四条命令），留在
#                                   rust/fylite_runtime/target/release/fy —— 不装进 Python 包
#   ./rust/build.sh --static     -> HDF5 / netCDF 从源码静态编进 .so（发行给没装库的机器）
#   ./rust/build.sh --no-install    只构建
#   ./rust/build.sh --fetch-kernel  内核检查前先在内核仓 git fetch（只动 refs）
#   ./rust/build.sh --no-kernel-check  跳过内核检查
#
# ★★每次构建都先跑一次**内核检查**（2026-09-05）：装着的 `libfylite_kernel.so` 与
# `_abi.py` 是不是内核仓检出今天这一版。**只看，不动**——不替谁构建内核，不改另一个
# 仓，不一致就红着退出并打印该跑的那条命令。理由写在 check_kernel 抬头。
#
# ★★2026-09-03 `--cli` 没有了：它从前另建 fylite-data / fylite-case 两个薄壳二进制，
# 而那两个已经收进 fylite（用户裁定「仅保留一个可执行程序」）。给 `--cli` 会被
# 按名拒绝并指向 `--exe`，不会静默地少装东西。
#
# ★数据层链两个 C 库（libhdf5、libnetcdf；`fylite_runtime/Cargo.toml` 的 [features] 说明
# 为什么）。缺省动态链接系统库：Debian/Ubuntu `apt install libhdf5-dev libnetcdf-dev`，
# conda `conda install hdf5 netcdf4`。`--static` 走 hdf5-metno-src / netcdf-src 从源码编，
# 第一次要十来分钟。
#
# ★IMAS DD 的结构表（`fylite_runtime/ids/*.tsv`、`src/ids_tables.rs`）是**提交进仓的生成物**，
# 由 `tools/dd-ids-table.py` 从 DD 的 IDSDef.xml 生成——本脚本不重生成它们。
#
# ★★2026-09-02 这一层从内核仓搬过来。理由写在 `fylite_runtime/src/lib.rs` 抬头：
# 网络协议与文件格式是**宿主的活**，内核那本自己就是这么写的。源码在本仓是公开的
# ——它是协议编解码，不是物理 IP。
#
# ★内核（`libfylite_kernel.so`）不由本脚本构建：它在私有仓 fylite_kernel，
# 由那边的 `rust/build.sh` 装进本仓的同一个 `_lib/`。两份 `.so`、两条来路、
# 一个目录。
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
CRATE="$DIR/fylite_runtime"
INSTALL=1
EXE=0
FEATURES=""
KCHECK=1
KFETCH=0
#: ★制品的版本化命名（`libfylite_runtime.so.0.0.1` + 两级符号链接）——规则与内核仓
#: 装 `.so` / `.wasm` 用的是**同一份实现**，就在这里 source 的这个文件里。
. "$ROOT/tools/soname.sh"
#: 内核检出的解析器 —— 与 `tools/build-wheel.sh` 用的是同一个（见 check_kernel）。
. "$ROOT/tools/kernel-path.sh"
#: 版本从 crate 自己那儿读，不另立一处。★与仓根 `VERSION`（发行版本）是两个量：
#: 那个说的是这一发行是哪一版，这个说的是中间层这个库是哪一版。
RVER="$(sed -n '0,/^version *= *"\([^"]*\)".*/s//\1/p' "$CRATE/Cargo.toml")"
[ -n "$RVER" ] || { echo "[runtime] 读不出 $CRATE/Cargo.toml 的 version" >&2; exit 1; }
for a in "$@"; do
    case "$a" in
        --no-install) INSTALL=0 ;;
        --exe) EXE=1 ;;
        #: ★按名拒绝而不是默默当成 --exe：调用方以为自己装了两个二进制，
        #: 而现在只有一个——说清楚比悄悄换掉好。
        --cli) echo "--cli 已撤：fylite-data / fylite-case 已收进 fylite，用 --exe" >&2; exit 2 ;;
        --static) FEATURES="--features static" ;;
        #: ★★哪一版的装置信息编进这个库（2026-09-05 用户裁定：页面也走中间层 wasm，
        #: 撤掉 `facts.jsonld`）。许可闸仍只有一处实现——`tools/facts-publish.py` 读每台
        #: 的 `rights.json`；这里只是把它的产物递给 `build.rs`。
        --public)   FACTS_FLAVOUR=public ;;
        --internal) FACTS_FLAVOUR=internal ;;
        --no-facts) FACTS_FLAVOUR= ;;
        --no-kernel-check) KCHECK=0 ;;
        --fetch-kernel) KFETCH=1 ;;
        *) echo "unknown option $a" >&2; exit 2 ;;
    esac
done

# --------------------------------------------------------------------------- #
# 内核检查 —— **只看，不动**（用户裁定 2026-09-05）                            #
# --------------------------------------------------------------------------- #
#: 内核（`libfylite_kernel.so` / `_ext` / 三个 `.wasm`）由**私有仓 fylite_kernel**
#: 构建并装进本仓的 `python/fylite/_lib/` 与 `app/assets/`。本脚本从不构建它，
#: 现在也不替谁去构建它：这一节把「装着的那一版」与「内核仓检出今天是哪一版」
#: 摆在一起，不一致就红着退出，并打印该跑的那一条命令。
#:
#: ★为什么值得在这里判：装着的 `.so` 与生成物 `_abi.py` 出自**同一次**内核构建，
#: 但它们装进来之后就各自独立了——有人拉了内核仓的新提交、只跑了半边，或者拷了
#: 一份别处的 `.so` 过来，两者就会说不同的话。而 ABI 对不上的后果不是编译失败，
#: 是**装载期被拒**（响亮）或者更糟：版本对得上而字节是旧的，算得出数，只是数是
#: 上一批的。文件名带上版本之后，前一半判据不必打开二进制就读得到。
#:
#: ★为什么**不**自动构建：内核仓是另一个仓，构建它要十几分钟且会写本仓的生成物。
#: 一条 `bash rust/build.sh` 顺手改动另一个仓的检出、再顺手改动本仓的六个生成
#: 文件，是「构建脚本做了没被要求的事」——那类惊喜的代价比省下的一条命令高。
check_kernel() {
    #: ★解析内核检出走 `tools/kernel-path.sh` —— 与 `build-wheel.sh` 同一个解析器。
    #: 这里曾经有一份自己的探测；两处各探一遍，某一天它们会在同一台机器上给出
    #: 不同的答案，而那正是本仓其它几处生成物反复写下的同一条理由。
    local kroot=""
    if fylite_resolve_kernel "$ROOT"; then kroot="$KERNEL"; fi

    local ilib="$ROOT/python/fylite/_lib"
    local iver iabi
    iver="$(fy_installed_version "$ilib" libfylite_kernel.so)"
    iabi="$(sed -n 's/^ABI_VERSION = \([0-9]*\).*/\1/p' \
            "$ROOT/python/fylite/_abi.py" 2>/dev/null || true)"

    if [ -z "$kroot" ]; then
        #: ★检出不在场**不是错**：本仓是公开仓，只检出它一个是受支持的状态
        #: （内核缺席时 `fy run` 说得清楚，页面走 wasm）。说一句就够了。
        if [ -n "$iver" ]; then
            echo "[kernel] 装着 kernel $iver (ABI ${iabi:-?})；没有内核仓检出可比对"
        else
            echo "[kernel] 未装内核，也没有内核仓检出 —— 本仓照常构建（fy run 需要它）"
        fi
        echo "[kernel]   要比对就给出：FYLITE_KERNEL=/path/to/fylite_kernel $0 $*"
        return 0
    fi

    local kver kabi
    fylite_kernel_declared "$kroot" || {
        echo "::error:: 读不出内核仓声明的版本/ABI（$kroot）" >&2; return 1; }
    kver="$KERNEL_VERSION"; kabi="$KERNEL_ABI"
    echo "[kernel] checkout: $kroot  (kernel $kver · ABI $kabi)"

    #: ★★「最新」是**相对于远端**说的，而远端要联网才知道。缺省不联网——
    #: 只读已有的远端跟踪引用，并把「这份跟踪引用有多旧」如实说出来；
    #: `--fetch-kernel` 才去 `git fetch`（它只动 refs，不动那个仓的工作树）。
    if [ "$KFETCH" = 1 ]; then
        echo "[kernel] git fetch（--fetch-kernel）…"
        git -C "$kroot" fetch --quiet || echo "[kernel] fetch 失败，按已有的跟踪引用比" >&2
    fi
    local up behind
    up="$(git -C "$kroot" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || true)"
    if [ -n "$up" ]; then
        behind="$(git -C "$kroot" rev-list --count "HEAD..@{upstream}" 2>/dev/null || echo 0)"
        if [ "${behind:-0}" != 0 ]; then
            echo "[kernel] ★检出落后 $up $behind 个提交" \
                 "$([ "$KFETCH" = 1 ] || echo '（未 fetch，这是上次取到的远端状态）')"
            echo "[kernel]   git -C $kroot pull   —— 然后重新构建内核"
        else
            echo "[kernel] 与 $up 齐平$([ "$KFETCH" = 1 ] || echo '（未 fetch）')"
        fi
    fi

    #: 一致性判据：装着的版本与 ABI，都要与内核仓检出**今天的源码**对得上。
    if [ -z "$iver" ]; then
        echo "[kernel] ★内核仓在场，但本仓没装内核 —— 页面走 wasm，fy run 不可用"
        echo "[kernel]   要装：FYLITE_PUBLIC=$ROOT bash $kroot/rust/build.sh --wasm-check"
        return 0
    fi
    local bad=0
    [ "$iver" = "$kver" ] || {
        echo "::error:: 装着的内核是 $iver，内核仓检出是 $kver" >&2; bad=1; }
    [ "$iabi" = "$kabi" ] || {
        echo "::error:: 装着的 ABI 是 ${iabi:-无}，内核仓检出是 $kabi" >&2; bad=1; }
    if [ "$bad" != 0 ]; then
        echo "::error::   本脚本不替你构建内核（只检查）。重新装它：" >&2
        echo "::error::   FYLITE_PUBLIC=$ROOT bash $kroot/rust/build.sh --wasm-check" >&2
        echo "::error::   确知不需要内核就跑本脚本时给 --no-kernel-check。" >&2
        return 1
    fi
    echo "[kernel] ok  kernel $iver · ABI $iabi —— 与检出一致"
}
#: ★写成 `if`，不是 `[ … ] && check_kernel`：`set -e` 下后者在 KCHECK=0 时整条
#: 命令返回 1，脚本当场退出——「跳过检查」的开关反而成了「不构建」的开关。
if [ "$KCHECK" = 1 ]; then check_kernel; fi

#: ★与内核同一条加固规矩：开发机路径不进制品。这里源码公开，所以泄漏的不是结构
#: 而只是构建者的目录布局连用户名——仍然不该发出去。
: "${CARGO_HOME:=$HOME/.cargo}"
: "${RUSTUP_HOME:=$HOME/.rustup}"
export RUSTFLAGS="${RUSTFLAGS:-} --remap-path-prefix=$CARGO_HOME=/cargo --remap-path-prefix=$RUSTUP_HOME=/rustup"

# --------------------------------------------------------------------------- #
# facts —— 先出那**一个**制品，再把它编进来                                     #
# --------------------------------------------------------------------------- #
#: ★★2026-09-05 用户裁定：**页面也走中间层 wasm，撤掉 `facts.jsonld`**。装置信息
#: 因此只有一个制品 `facts.rs`，由 `.so` 与 `.wasm` 各编进去；页面经 wasm 读它，
#: 命令行经 `facts::embedded_*` 读它——同一份字节，没有第二份可以跟它不一致。
#: ★**版别在这里定死**：编进去之后就换不掉了，所以下游（站点、可执行文件）不能再
#: 「发布时挑版别」。`app/assets/runtime-version.js` 记下这一次是哪一版，下游据此核对。
if [ -n "${FACTS_FLAVOUR:-internal}" ]; then
    FACTS_FLAVOUR="${FACTS_FLAVOUR:-internal}"
    if python3 "$ROOT/tools/facts-publish.py" --flavour "$FACTS_FLAVOUR" \
            --out "$ROOT/dist" >/dev/null 2>&1 && [ -s "$ROOT/dist/facts.rs" ]; then
        export FY_FACTS_RS="$ROOT/dist/facts.rs"
        echo "[runtime] facts: $FACTS_FLAVOUR 版 -> $FY_FACTS_RS"
    else
        echo "[runtime] facts: 搜索路径上没有语料——这一版不带装置信息"
        FACTS_FLAVOUR=none
    fi
else
    FACTS_FLAVOUR=none
    echo "[runtime] facts: --no-facts，这一版不带装置信息"
fi

echo "[runtime] cargo build --release $FEATURES ..."
cargo build --release $FEATURES --manifest-path "$CRATE/Cargo.toml"
SO="$CRATE/target/release/libfylite_runtime.so"
[ -f "$SO" ] || { echo "[runtime] 没有产出 $SO" >&2; exit 1; }

homes=$(strings -n 6 "$SO" | grep -c "$HOME" || true)
[ "$homes" = 0 ] || { echo "::error:: $SO 里有 $homes 条开发机路径" >&2; exit 1; }
exp=$(nm -D --defined-only "$SO" | grep -c 'fylite_runtime_' || true)
[ "$exp" -gt 0 ] || { echo "::error:: C ABI 导出没了（strip 过头）" >&2; exit 1; }
echo "[runtime] harden-ok  $(basename "$SO")  ($exp exports)"

if [ "$INSTALL" = 1 ]; then
    #: ★★版本化装入（2026-09-05 用户裁定），与内核仓装 `.so` / `.wasm` 同一条规则、
    #: 同一份实现（`tools/soname.sh`）：真文件 `libfylite_runtime.so.$RVER`，加
    #: `.so.<major>` 与 `.so` 两级链接。装载方（`fylite.kernel`、`fy` 的 dlopen、
    #: 轮）继续用不带版本的那个名字，拿到的仍是同一份字节——变的是「这台机器上
    #: 装的是哪一版」现在 `ls` 就能回答，不必打开二进制。
    fy_install_versioned "$SO" "$ROOT/python/fylite/_lib" libfylite_runtime.so "$RVER"
fi

# --------------------------------------------------------------------------- #
# 中间层的 wasm —— 页面读装置信息的那条路（2026-09-05 用户裁定）               #
# --------------------------------------------------------------------------- #
#: ★★**页面也走中间层 wasm，撤掉 `facts.jsonld`**。在此之前装置信息在一个制品里装
#: 两遍：一遍是页面 fetch 的 JSON（站点上是文件，可执行文件里是 `assets.rs` 的
#: `include_bytes!`），一遍是 CLI 读的那张 Rust 表——同一批 432 KB、两份字节、两条
#: 通路，而没有任何东西保证它们描述同一批机器。收成一处之后只剩 `facts.rs` 一个
#: 制品，页面与命令行读的是同一份字节。
#:
#: ★这份 wasm 与内核那两份**不是一回事**：那两份是物理核（私有仓 `fylite_kernel`），
#: 这一份是中间层。名字因此带 `runtime`，装法与它们同一条规则（`tools/soname.sh`）。
#: ★`--no-default-features`：wasm 上没有套接字（mdsip），也不链 libhdf5 / libnetcdf。
if [ "${WASM:-1}" = 1 ] && rustup target list --installed 2>/dev/null | grep -qx wasm32-unknown-unknown; then
    #: ★★**两份 wasm，同一份源码，差别只在导出面**（2026-09-05）。
    #:
    #:   fylite_facts.wasm    只导出装置那扇门（alloc / free / facts_*）。实测 0.43 MB。
    #:   fylite_runtime.wasm  另加 g-file · 文档树 · 打包 · 读文本。实测 2.14 MB。
    #:
    #: 为什么要小的那一份：wasm 上每个 `#[no_mangle]` 都是链接的**根**，导出面因此
    #: 决定产物大小；而页面今天从中间层只读装置信息（`factsdb.js` 用五个导出）。
    #: 2.14 MB 太大，进不了 service worker 的预缓存（那会让只看一眼首页的读者先付
    #: 这笔钱），于是**断网时站点一台机器也列不出来**——实测撞上过。0.43 MB 进得去。
    #: ★这不是第二份实现：装置那扇门两份产物用的是同一段 `facts.rs` / `c_api.rs`。
    for variant in facts full; do
        case "$variant" in
          facts) feats=""            ; name=fylite_facts.wasm   ;;
          full)  feats="abi_full"    ; name=fylite_runtime.wasm ;;
        esac
        echo "[runtime] wasm32（$variant）：cargo build --release --no-default-features ${feats:+--features $feats} ..."
        WOUT="$CRATE/target/wasm32-unknown-unknown/release/fylite_runtime.wasm"
        rm -f "$WOUT"
        cargo build --release --target wasm32-unknown-unknown --no-default-features \
            ${feats:+--features "$feats"} --manifest-path "$CRATE/Cargo.toml"
        [ -f "$WOUT" ] || { echo "[runtime] 没有产出 $WOUT" >&2; exit 1; }
        homes=$(strings -n 6 "$WOUT" | grep -c "$HOME" || true)
        [ "$homes" = 0 ] || { echo "::error:: $WOUT 里有 $homes 条开发机路径" >&2; exit 1; }
        echo "[runtime] harden-ok  $name ($(stat -c%s "$WOUT") bytes)"
        [ "$INSTALL" = 1 ] && fy_install_versioned "$WOUT" "$ROOT/app/assets" "$name" "$RVER"
    done
    if [ "$INSTALL" = 1 ]; then
        true
        #: ★★页面要拼出版本化的真文件名，所以它得知道中间层是哪一版。
        #: 单开一个生成物而不是往 `version.js` 里塞：那一份是**内核仓**生成的
        #: （kernel / abi / app 三个数），本仓往里写会在下一次内核构建时被抹掉，
        #: 而抹掉不报错——页面只是从此取不到 wasm，且只在版本变过之后才发作。
        printf '%s\n' \
          "// GENERATED by rust/build.sh from rust/fylite_runtime/Cargo.toml — do not edit." \
          "//" \
          "// 中间层这个库是哪一版。页面用它拼出版本化的真文件名" \
          "// (\`fylite_runtime.wasm.\$RUNTIME\`, tools/soname.sh)。" \
          "//" \
          "// ★与 assets/version.js 分开：那一份由**内核仓**生成，本仓写进去会被下一次" \
          "// 内核构建抹掉——而抹掉不报错，页面只是从此取不到这份 wasm。" \
          "self.FyRuntimeVersion = '$RVER';" \
          "" \
          "// 这一份 wasm 里编着哪一版的装置信息。★下游（build-site.sh /" \
          "// build-app-exe.sh）据此核对：版别在**编译期**定死，发布时挑不了。" \
          "self.FyFactsFlavour = '$FACTS_FLAVOUR';" \
          > "$ROOT/app/assets/runtime-version.js"
        echo "[runtime] -> app/assets/runtime-version.js ($RVER)"
    fi
else
    echo "[runtime] 跳过 wasm32（没装那个目标：rustup target add wasm32-unknown-unknown）"
fi

# ★★The mdsip REQUEST contract — the verb codes and the `*` sentinel.
#
# The A-Box binding table (`tools/abox-mds-bind.py`) spells a verb as a string;
# `fylite_rs_mds_read` takes an integer.  That mapping is the seam between them,
# it is three lines long, and three lines is exactly the size that feels safe to
# transcribe by hand — which is how `zerod`'s parameter order came to be spelled
# in three places.  Declared in `src/mdsip.rs` with `@mds-request`, generated
# here into both hosts.
python3 - "$ROOT/python/fylite/_mds_request.py" \
          "$ROOT/app/assets/mds-request.js" \
          "$CRATE/src/mdsip.rs" <<'PYMDS'
import re, sys

src = open(sys.argv[3]).read()
m = re.search(r"pub const REQUEST_VERBS:.*?=\s*\[(.*?)\];", src, re.S)
if not m:
    sys.exit("[build] REQUEST_VERBS not found in mdsip.rs")
verbs = re.findall(r'\("([a-z_]+)",\s*(-?\d+)\)', m.group(1))
if not verbs:
    sys.exit("[build] REQUEST_VERBS parsed empty")
sentinel = "-9223372036854775808"   # i64::MIN, spelled out for both hosts

head = ("GENERATED by rust/build.sh from rust/fylite/src/mdsip.rs "
        "(@mds-request) — do not edit.\n\n"
        "The verb codes `fylite_rs_mds_read` takes, keyed by the spelling the\n"
        "A-Box binding table uses.  ALL is the `*` subscript sentinel.")

with open(sys.argv[1], "w") as f:
    f.write('"""%s\n"""\n\n' % head)
    f.write("VERBS = {\n")
    for n, c in verbs:
        f.write('    "%s": %s,\n' % (n, c))
    f.write("}\n\n#: `*` in a subscript (i64::MIN).\nALL = %s\n" % sentinel)

with open(sys.argv[2], "w") as f:
    f.write("// " + head.replace("\n", "\n// ") + "\n\n")
    f.write("export const MDS_VERBS = Object.freeze({\n")
    for n, c in verbs:
        f.write("  %s: %s,\n" % (n, c))
    f.write("});\n\n// `*` in a subscript (i64::MIN).\n")
    f.write("export const MDS_ALL = %sn;\n" % sentinel)
print("[build] mds request: %d verbs" % len(verbs))
PYMDS
echo "[build] mds request -> python/fylite/_mds_request.py, app/assets/mds-request.js"

if [ "$EXE" = 1 ]; then
    #: ★查看器把整个 `app/` 编进可执行文件；资源表 `src/bin/app/assets.rs` 是
    #: 生成物（`tools/make-app-embed.mjs`），`include_bytes!` 走 `FYLITE_APP_DIR`。
    #: 搬到本仓之后 `app/` 就在隔壁，所以这里能给出确定的值——从前它是跨仓的。
    export FYLITE_APP_DIR="$ROOT/app"
    echo "[runtime] cargo build --release --features desktop (fy) ..."
    cargo build --release --features desktop --bin fy \
        --manifest-path "$CRATE/Cargo.toml"
    echo "[runtime] -> $CRATE/target/release/fy"
    #: ★★2026-09-04 用户裁定：**Python 侧不产出可执行文件**。此前这里把 `fy` 拷进
    #: `python/fylite/_bin/`，于是同一个二进制有两份、轮里带着一份平台相关的东西，
    #: 而「哪一份在跑」要靠查找顺序回答。现在只有一份，在 `target/release/`——
    #: 装到 `$PATH` 上是发行的事（`tools/build-app-exe.sh`），不是 `pip install` 的事。
    #: 命令行只有它一个：`app` / `data` / `run` / `list`（`case` 于 2026-09-04 收进 `run`）
    #: （`engine/cli.py` 的 `_RUST_EXE`），找不到就说清楚怎么构建。
fi
echo "[runtime] done."
