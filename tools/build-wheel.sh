#!/usr/bin/env bash
# Build the fylite wheel, with the platform tag the binary actually earns.
#
# alpha 期的分发面是 **Linux x86-64 一个**（裁定 2026-08-30，见发布通道评估
# 报告）：轮里带的是预编译的 `_lib/libfylite_kernel.so`，pip 不现场编译，所以别的
# 平台上「装上了」并不等于「能用」。这个脚本做三件 pyproject 说不出的事：
#
#   1. 拒绝在错误的平台上出轮（现在的 .so 是 ELF x86-64）；
#   2. 从 .so 自己读 glibc 下限，据此定 manylinux tag —— 不写死一个数字，
#      因为写死的那个数字会在换构建机的当天变成谎；
#   3. 只出 wheel，不出 sdist —— sdist 会让别的平台上的 pip 拿去「构建」，
#      得到的还是这一份 Linux .so，正是 tag 要挡住的那件事。
#
# 用法：bash tools/build-wheel.sh [输出目录]   （默认 python/dist）
#   解释器经 $PYTHON 指定（需要 `build` 与 `setuptools`；不加引号展开，
#   所以可以是一条带参数的命令行）；仓内常用：
#   PYTHON="uv run --no-project --with build --with setuptools python" bash tools/build-wheel.sh
#
# ★★`--no-project` 不是可省的。本脚本会 `cd` 进工程目录（2026-09-02 起是
# `python/`），`uv run` 在那里看得见 `pyproject.toml`，于是会**就地建一个
# `.venv/`**（实测 244 MB）——而裁定是**不建单独环境**，Python 一律走 uv 的临时
# 环境。加上它，uv 只解 `--with` 的那几个包，不碰工作树。
# ★工程目录 09-01 曾上移到仓根、09-02 又收敛回 `python/`；两种落法下这条都成立，
# 只是「uv 在哪里看见工程」换了地方。
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
#: ★工程目录（`pyproject.toml` 所在处）—— NOTICE 借入、`python -m build` 与
#: `license-files` 解析都以它为准，写一次，下面三处引用它。
PROJ="$DIR/python"
OUT="${1:-$PROJ/dist}"
#: ★★**轮里不再带 facts 语料**（2026-09-05 用户裁定：页面也走中间层 wasm，撤掉
#: `facts.jsonld`）。装置文档只有一个制品 `facts.rs`，由 `rust/build.sh --<版别>`
#: 编进 `libfylite_runtime.so`——而那一份 `.so` 本来就在轮里。于是轮里的装置信息
#: 与命令行、与浏览器读的是同一批字节，而不是第三份拷贝。
#: ★许可闸没有松：进那张表的仍是 `tools/facts-publish.py` 按每台 `rights.json` 选出
#: 来的那几台；版别在编译 `.so` 时定死，打包时挑不了。
FACTS_DIR="$PROJ/fylite/_facts"
rm -rf "$FACTS_DIR"
FLAV=$(sed -n "s/.*FyFactsFlavour *= *'\([^']*\)'.*/\1/p" "$DIR/app/assets/runtime-version.js" 2>/dev/null || true)
echo "[wheel] facts: 编在 libfylite_runtime.so 里（${FLAV:-未知} 版）——轮里不另带一份"

SO="$PROJ/fylite/_lib/libfylite_kernel.so"
#: ★★2026-09-02：轮里现在有**两份** `.so`。数据层（`libfylite_runtime.so`，公开仓
#: `rust/fylite_runtime/` 构建）与内核是两条来路，缺任何一份轮都不完整——但只有内核
#: 这份由本脚本所在的仓构建，所以数据层那份在这里只**查在不在**，不代它构建。
DATA_SO="$PROJ/fylite/_lib/libfylite_runtime.so"
[ -f "$DATA_SO" ] || { echo "[wheel] 找不到 $DATA_SO —— 先在公开仓跑 rust/build.sh" >&2
                       echo "[wheel]   （数据层在公开仓，取数与格式都靠它）" >&2
                       exit 1; }

[ -f "$SO" ] || { echo "[wheel] 找不到 $SO —— 先在内核仓跑 rust/build.sh" >&2
                  echo "[wheel]   （Rust 源码在 fylite_kernel；它会把 .so 装进本仓）" >&2
                  exit 1; }

#: ★★`-L`：跟着符号链接问真文件（2026-09-05）。制品从这天起按 Linux 的习惯装成
#: `libfylite_kernel.so -> .so.0 -> .so.0.0.1`，而 `file -b` 对一条链接答的是
#: 「symbolic link to …」——不是 ELF，于是这道**平台闸**会把每一次打轮都拒掉，
#: 拒的理由还是一句看起来像真事故的「不是 ELF x86-64」。`readelf` 自己跟随链接，
#: 所以下面两处不必改。
case "$(file -bL "$SO")" in
  *"ELF 64-bit"*"x86-64"*) ;;
  *) echo "[wheel] $SO 不是 ELF x86-64，本脚本只出 alpha 期声明的那一个面" >&2
     echo "[wheel] 实际是：$(file -b "$SO")" >&2; exit 1 ;;
esac

# glibc 下限 = .so 里出现过的最高 GLIBC_x.y 版本符号需求
FLOOR="$(readelf -V "$SO" | grep -o 'GLIBC_[0-9]\+\.[0-9]\+' | sort -uV | tail -1)"
[ -n "$FLOOR" ] || { echo "[wheel] 读不出 glibc 下限" >&2; exit 1; }
MAJOR="${FLOOR#GLIBC_}"; MINOR="${MAJOR#*.}"; MAJOR="${MAJOR%%.*}"
PLAT="manylinux_${MAJOR}_${MINOR}_x86_64"

# manylinux 只允许一小组系统库；出现别的说明构建机漏进了依赖
ALLOWED='libgcc_s.so.1|libm.so.6|libc.so.6|ld-linux-x86-64.so.2|libdl.so.2|libpthread.so.0|librt.so.1'
BAD="$(readelf -d "$SO" | sed -n 's/.*NEEDED.*\[\(.*\)\]/\1/p' | grep -Ev "^($ALLOWED)$" || true)"
[ -z "$BAD" ] || { echo "[wheel] .so 依赖了 manylinux 允许名单外的库：$BAD" >&2; exit 1; }

echo "[wheel] glibc 下限 $FLOOR -> $PLAT"
#: ★★轮里装的是**完全版本化的那一个真文件**（`pyproject.toml` 的 `package-data`
#: 是 `_lib/*.so.*.*.*`——轮里没有符号链接，装三个名字就是把同一份字节存三遍）。
#: 把装了哪几版打出来：出了问题时，「这个轮里是哪一版内核」不该靠解压去查。
. "$DIR/tools/soname.sh"
for l in libfylite_kernel.so libfylite_kernel_ext.so libfylite_runtime.so; do
    v="$(fy_installed_version "$PROJ/fylite/_lib" "$l")"
    [ -n "$v" ] && echo "[wheel] $l  $v" || echo "[wheel] $l  ——（不在 _lib/）"
done
#: ★★Apache-2.0 §4(d)：NOTICE 必须随**分发**走。本包带的 `_lib/libfylite_kernel.so`
#: 正是 GACODE 白盒移植的编译产物，这一条不是装饰。
#: ★★2026-09-02：公开仓**已自带一份仓根 `NOTICE`**（用户裁定恢复），并由
#: `python/NOTICE -> ../NOTICE` 把它引进工程目录——`license-files` 只在工程目录内
#: 解析，放在仓根等于没放，而那种失败**没有任何一步会报错**，只是轮里少一份文件。
#: 于是这里的活从「借入再撤走」变成**两份逐字节比对**：两处都有 NOTICE，就会漂移，
#: 除非有人比。比不上就拒绝打轮——一份说谎的署名比没有署名更糟。
. "$(cd "$(dirname "$0")" && pwd)/kernel-path.sh"
NOTICE_LOCAL="$PROJ/NOTICE"
if fylite_resolve_kernel "$DIR" && [ -f "$KERNEL/NOTICE" ]; then
    if [ -e "$NOTICE_LOCAL" ]; then
        if cmp -s "$NOTICE_LOCAL" "$KERNEL/NOTICE"; then
            echo "[wheel] NOTICE：本仓自带，与 $KERNEL 的那份逐字节一致"
        else
            echo "::error:: 两份 NOTICE 不一致：" >&2
            echo "  本仓 $NOTICE_LOCAL（$(readlink -f "$NOTICE_LOCAL")）" >&2
            echo "  内核 $KERNEL/NOTICE" >&2
            echo "  署名文件漂移了。先定哪一份是对的，再打轮。" >&2
            exit 1
        fi
    else
        #: 只检出了公开仓、而它那份不知怎么没了——借入并在 build 后撤走。
        cp "$KERNEL/NOTICE" "$NOTICE_LOCAL"
        trap 'rm -f "$NOTICE_LOCAL"' EXIT
        echo "[wheel] NOTICE：本仓缺，自 $KERNEL 借入（build 后撤走）"
    fi
elif [ -e "$NOTICE_LOCAL" ]; then
    #: 没有内核检出，但本仓自带 —— 可以打，只是没人替它核对。
    echo "[wheel] ★NOTICE：用本仓自带的那份；无内核检出，未做漂移比对。"
else
    echo "[wheel] ★两处都找不到 NOTICE —— 打出来的轮将不带它，" >&2
    echo "[wheel]   而它带着 GACODE 派生的 .so：那样分发不满足 Apache-2.0 §4(d)。" >&2
    echo "[wheel]   给 FYLITE_KERNEL=/path/to/fylite_kernel 再来一次。" >&2
    exit 1
fi

mkdir -p "$OUT"
#: ★★2026-09-02：工程目录收敛回 `python/`（`pyproject.toml` / `setup.py` 都在那里，
#: 见那份文件的注记），推翻 09-01 的「上移到仓根」。这里跟着改，否则 build 在仓根
#: 找不到工程。
cd "$PROJ"
${PYTHON:-python} -m build --wheel --outdir "$OUT" \
  --config-setting=--build-option=--plat-name="$PLAT"

echo "[wheel] 产物："
ls -1 "$OUT"/*.whl
echo "[wheel] 提醒：只发 wheel，不要发 sdist（理由见本脚本抬头）。"
