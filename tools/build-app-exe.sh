#!/usr/bin/env bash
# 发布类型三：**单文件桌面查看器**（内嵌整个 `app/`，起本机服务并开浏览器）。
#
# 与另两条通道的分工：
#   pip 轮      —— 给写脚本的人，alpha 期 Linux x86-64（tools/build-wheel.sh）
#   浏览器站点  —— 给联网的人，零安装（tools/build-site.sh 出目录；FYL-DESIGN-15）
#   本脚本      —— 给**离线**或**没有 Python** 的人，尤其 Windows：
#                  一个文件，双击即用，不装任何运行时
#
# ★为什么不是 Tauri / Electron：前者实务上要 Windows runner 且依赖
# WebView2 运行时，后者要背一整个 Chromium（150 MB+，与「单机轻量」的
# 资源包络冲突）。这条路线用**用户自己的浏览器**做渲染器，程序只负责
# 伺服自己内嵌的字节——因此能从 Linux 一条命令交叉编译出 .exe，
# 且体积是资源本身的大小加上一层薄壳。
#
# 用法：bash tools/build-app-exe.sh [linux|windows|windows-msvc|both]  （默认 both）
#   windows       = GNU ABI，链接器要 mingw（apt，需 root）
#   windows-msvc  = MSVC ABI，靠 cargo-xwin，**不需要 root**
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"

#: ★★2026-09-02：查看器的**内容**（内嵌的整个 `app/`）与**代码**
#: （`rust/fylite_engine/src/bin/app/`）现在都在本仓——数据层从内核仓搬了过来。
#: 从前这里要跨仓解析内核检出，那一步随之取消。
CRATE="$DIR/rust/fylite_engine"

OUT="$CRATE/target"
WHICH="${1:-both}"

cd "$DIR"
# 资源表先与 app/ 对齐——漏这一步的后果是运行时 404，只有别人才会发现
#: ★它写的是 `rust/fylite_engine/src/bin/app/assets.rs` —— 同一棵树里。
node tools/make-app-embed.mjs

#: ★资源表里的 `include_bytes!` 走 `env!("FYLITE_APP_DIR")`，所以编译期必须给。
#: 导出而不是逐条命令加前缀：下面三个 `build_*` 都要它。
export FYLITE_APP_DIR="$DIR/app"

cd "$CRATE"

build_linux() {
  echo "[exe] linux x86-64 …"
  cargo build --release --features desktop --bin fylite-app
  ls -l "$OUT/release/fylite-app"
}

build_windows() {
  local target=x86_64-pc-windows-gnu
  if ! rustup target list --installed | grep -qx "$target"; then
    echo "[exe] 缺 $target —— rustup target add $target" >&2; exit 1
  fi
  if ! command -v x86_64-w64-mingw32-gcc >/dev/null; then
    echo "[exe] 缺 mingw 链接器 —— apt-get install gcc-mingw-w64-x86-64" >&2; exit 1
  fi
  echo "[exe] windows x86-64（交叉编译）…"
  CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER=x86_64-w64-mingw32-gcc \
    cargo build --release --features desktop --bin fylite-app --target "$target"
  local exe="$OUT/$target/release/fylite-app.exe"
  file "$exe" | grep -q 'PE32+' || { echo "[exe] 产物不是 PE32+" >&2; exit 1; }
  ls -l "$exe"
  echo "[exe] sha256: $(sha256sum "$exe" | cut -d' ' -f1)"
  echo "[exe] ★未签名：Windows 上首次运行会弹 SmartScreen 提示。"
  echo "[exe]   代码签名证书未采购（见发布通道报告）；分发时须一并说明。"
}

# ★第二条 Windows 路线：MSVC ABI，不要 root。
#
# `windows`（上面那个）走 GNU ABI，链接器是 mingw——装它要 `apt-get install
# gcc-mingw-w64-x86-64`，也就是要 root。没有 root 的机器上走这一条：
# `cargo-xwin` 把微软的 CRT 与 Windows SDK 拉进**用户目录**
# （`~/.cache/cargo-xwin`），链接器用 rustup 自带的 `rust-lld`。
#
# ★两条线出的是**不同 ABI 的两个产物**，不是同一个东西的两种做法：
#   * `-gnu`  链 mingw 的 libgcc/msvcrt，体积略大，与 MinGW 生态一致；
#   * `-msvc` 链微软自己的 CRT，是 Windows 上的原生约定，也是 crates.io 上
#     预编译产物的默认目标。
# 本仓这个查看器不依赖任何 C 库（只 std + 内嵌字节），所以两者对用户是等价的，
# 挑哪条只取决于**这台构建机装得起哪个**。
build_windows_msvc() {
  local target=x86_64-pc-windows-msvc
  if ! rustup target list --installed | grep -qx "$target"; then
    echo "[exe] 缺 $target —— rustup target add $target" >&2; exit 1
  fi
  #: ★问 cargo 而不是问 PATH：`cargo install` 装到 `$CARGO_HOME/bin`，而那一格
  #: 未必在 PATH 上（本机 PATH 上的是 **Windows 侧** 的 `.cargo/bin`——WSL 里
  #: 这种混淆很好犯）。cargo 自己会在 `$CARGO_HOME/bin` 里找 `cargo-*` 子命令。
  if ! cargo xwin --version >/dev/null 2>&1; then
    echo "[exe] 缺 cargo-xwin —— cargo install cargo-xwin --locked" >&2; exit 1
  fi
  echo "[exe] windows x86-64 / MSVC ABI（交叉编译）…"
  cargo xwin build --release --features desktop --bin fylite-app --target "$target"
  local exe="$OUT/$target/release/fylite-app.exe"
  file "$exe" | grep -q 'PE32+' || { echo "[exe] 产物不是 PE32+" >&2; exit 1; }
  ls -l "$exe"
  echo "[exe] sha256: $(sha256sum "$exe" | cut -d' ' -f1)"
  echo "[exe] ★未签名：Windows 上首次运行会弹 SmartScreen 提示。"
  echo "[exe]   代码签名证书未采购（见发布通道报告）；分发时须一并说明。"
}

case "$WHICH" in
  linux) build_linux ;;
  windows) build_windows ;;
  windows-msvc) build_windows_msvc ;;
  both) build_linux; build_windows ;;
  *) echo "用法：bash tools/build-app-exe.sh [linux|windows|windows-msvc|both]" >&2; exit 2 ;;
esac
