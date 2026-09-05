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
# ★★2026-09-04：构建分**公开版**与**内部版**（用户裁定）。谁进哪一版由每台机器的
# `rights.json` 判：公开版不带 EAST，也不带上游禁止再分发的 IDS。
# 可执行文件因此**不直接内嵌 `app/`**，而是内嵌一棵**按这一版规则装好的树**——
# 与静态站点用的是同一个装配器（`tools/build-site.sh`），所以两种制品逐字节同源。
#
# ★★2026-09-05 用户裁定：**页面也走中间层 wasm，撤掉 `facts.jsonld`**。装置文档从此
# 只有一份 `facts.rs`，由 `rust/build.sh --<版别>` 编进 `fylite_runtime` 的 `.so` 与
# `.wasm`；页面经那份 wasm 读，命令行经同一张表读。本脚本因此**只核对版别**，不再
# 逐台发文档——此前同一批 432 KB 在一个可执行文件里装了两遍。
#
# ★★2026-09-04 用户裁定：**三种构建方式**，差别在带不带浏览器那一半：
#   --mode cli   纯 CLI —— 可执行文件不内嵌 `app/`、不起服务，`app` 命令按名拒绝；
#                算力走**原生内核 `.so`**（`case` 运行期 dlopen）。实测 3.38 MB。
#   --mode web   Web UI —— 内嵌整个 `app/`（含三个 `.wasm`），算力在**浏览器**里。
#   --mode full  完整（缺省）—— 两路都在：内嵌前端 + 原生内核。实测 8.47 MB。
#
# 用法：bash tools/build-app-exe.sh [--public|--internal] [--mode cli|web|full] [linux|windows|windows-msvc|both]
#   缺省 = 内部版（带全部装置，含 EAST）——2026-09-05 裁定，FYL-DESIGN-19 A-14
#   --public      = 公开版（按 rights.json 筛，不带 EAST）；公开面必须明写这一句
#   windows       = GNU ABI，链接器要 mingw（apt，需 root）
#   windows-msvc  = MSVC ABI，靠 cargo-xwin，**不需要 root**
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"

#: ★★2026-09-02：查看器的**内容**（内嵌的整个 `app/`）与**代码**
#: （`rust/fylite_runtime/src/bin/app/`）现在都在本仓——数据层从内核仓搬了过来。
#: 从前这里要跨仓解析内核检出，那一步随之取消。
CRATE="$DIR/rust/fylite_runtime"

OUT="$CRATE/target"
FLAVOUR=internal
MODE=full
while :; do
  case "${1:-}" in
    --public)   FLAVOUR=public;   shift ;;
    --internal) FLAVOUR=internal; shift ;;
    --mode)     MODE="${2:?--mode 要 cli|web|full}"; shift 2 ;;
    *) break ;;
  esac
done
case "$MODE" in
  cli)  FEATURES="cli,hdf5,netcdf" ;;
  web)  FEATURES="webui,hdf5,netcdf" ;;
  full) FEATURES="desktop,hdf5,netcdf" ;;
  *)    echo "[exe] --mode 要 cli|web|full（给了 $MODE）" >&2; exit 2 ;;
esac
WHICH="${1:-both}"

cd "$DIR"

#: ★★先装一棵**这一版的树**，再内嵌它。装配器就是站点那一个，所以「桌面版带什么」
#: 与「站点带什么」按构造相同——两个发布者各装一遍，某一天它们会不一样，而**先
#: 发现的人是拿到制品的那个**。装出来的树里，装置文档与目录都已按规则筛过。
if [ "$MODE" = cli ]; then
  #: ★纯 CLI 档不内嵌任何页面，所以既不装树也不重生成资源表——一个不带前端的
  #: 发行**不该**把 app 的字节背在身上，那正是这一档存在的理由。
  echo "[exe] 模式 cli：不内嵌 app/（算力走原生内核 .so）"
  STAGE=""
else
  STAGE="$DIR/dist/app-$FLAVOUR"
  #: ★两边都**明写**版别，不靠各自的缺省：缺省今天是 internal，而两个脚本的缺省
  #: 若某天分了岔，先发现的人是拿到制品的那个。
  bash tools/build-site.sh "--$FLAVOUR" "$STAGE" >/dev/null
  echo "[exe] 模式 $MODE · $FLAVOUR 版内容：$STAGE"

  #: ★★**这份可执行文件不带中间层的 wasm**（2026-09-05）。它本身就是原生的中间层，
  #: 那张 facts 表已经在它的地址空间里；内嵌页面因此改问它自己的 `/api/facts`
  #: （`app/assets/factsdb.js` 先探这条路，探不到才退回 wasm——静态站点走的正是后者）。
  #: 再内嵌一份同层的 wasm，等于把刚消掉的重复换个层次又做一遍：实测 +2.25 MB，
  #: 其中只有 432 KB 是装置信息，另外 1.8 MB 是同一层代码的第二份。
  #: ★这一条**有意打破**「站点与可执行文件内嵌同一个子集」那句：两者差的正是这一份，
  #: 而差的理由是两个宿主读同一批字节的**路不同**，不是内容不同。
  rm -f "$STAGE"/assets/fylite_runtime.wasm* "$STAGE"/assets/fylite_facts.wasm*
  echo "[exe] 内嵌树里去掉中间层的两份 wasm（页面改走本进程的 /api/facts）"

  #: ★★**内核那两份 wasm 也不带**（2026-09-05 用户裁定：「webui 中 fylite_rs /
  #: fylite_kernel_ext wasm 功能由 api 端提供，只静态网页走 wasm」；同日续裁
  #: 「fy 封装 fylite_kernel 静态库，.so 是留给 python 层，wasm 留给静态网页发布」）。
  #: 算力是这个可执行文件自己的一部分——内核静态库链在里面，页面把调用交给
  #: `/api/kernel`（`app/assets/kernelapi.js` 先探 `/api/health` 的 `kernel` 格，
  #: 探不到才实例化 wasm——静态站点走的正是后者）。
  #: ★这是同一天第二次消掉同一种重复：先是装置信息（两份字节、两条通路），
  #: 现在是**算力**（同一批物理编两遍，一遍原生一遍 wasm，谁也不保证两者一致）。
  #: 差别只在这一次两条路的等价性是**有闸子看着的**：`app/tests/validate-kernel-api.mjs`
  #: 让同一批调用两边各走一遍并逐位比对。
  #: 实测省下 1.46 MB（fylite_rs.wasm 0.99 + fylite_kernel_ext.wasm 0.47）。
  rm -f "$STAGE"/assets/fylite_rs.wasm* "$STAGE"/assets/fylite_kernel_ext.wasm*
  echo "[exe] 内嵌树里去掉内核 wasm（算力在本进程里：静态库 + /api/kernel）"

  #: ★★**h5wasm 也不带**（2026-09-05 用户裁定：hdf5 走 fy app 的文件端点，静态站点
  #: 保留 h5wasm）。那是 NIST 的 Emscripten 包，4.1 MB——HDF5 那个 C 库以 base64 骑在
  #: 里面——而**这个进程本来就链着 libhdf5**：页面把文件字节 POST 给 `/api/read`，
  #: 由中间层自己的读者（`io::read`，与 `fy data`、与 python 对拍的同一份）读完送回。
  #: 与内核那次同形：桌面版不该背一份第二实现。静态站点没有 `/api/*`，那里 h5wasm 是
  #: 唯一的读法，所以站点照发（仍惰性、仍不进预缓存）。
  rm -rf "$STAGE"/assets/vendor
  echo "[exe] 内嵌树里去掉 assets/vendor（h5wasm 4.1 MB —— 页面改走 /api/read）"

  # 资源表先与那棵树对齐——漏这一步的后果是运行时 404，只有别人才会发现
  #: ★它写的是 `rust/fylite_runtime/src/bin/app/assets.rs` —— 同一棵树里。
  #: ★`--from` 指**装好的那一棵**：表描述的必须就是编译期真在的那一棵，否则
  #: `include_bytes!` 指着不存在的文件，一屏 `couldn't read`。
  node tools/make-app-embed.mjs --flavour "$FLAVOUR" --from "$STAGE"
fi

#: ★★装置信息**编进二进制**（2026-09-05 用户裁定），而且**只编一遍**：同日续裁
#: 「页面也走中间层 wasm，撤掉 `facts.jsonld`」之后，页面与命令行读的是同一张表。
#: 那张表由 `rust/build.sh --$FLAVOUR` 在编译期编进 `fylite_runtime`——本脚本不自己
#: 编，只**核对**手上这一份是不是要发的那一版：版别在编译期定死，发布时挑不了。
FLAV=$(sed -n "s/.*FyFactsFlavour *= *'\([^']*\)'.*/\1/p" "$DIR/app/assets/runtime-version.js" 2>/dev/null || true)
if [ "$FLAV" != "$FLAVOUR" ]; then
  echo "[exe] 装着的中间层编的是 **${FLAV:-<无>}** 版的装置信息，而这次要出 $FLAVOUR 版。" >&2
  echo "[exe]   重建：bash rust/build.sh --$FLAVOUR" >&2
  exit 1
fi
export FY_FACTS_RS="$DIR/dist/facts.rs"
[ -s "$FY_FACTS_RS" ] || { echo "[exe] 找不到 $FY_FACTS_RS —— 先跑 bash rust/build.sh --$FLAVOUR" >&2; exit 1; }
echo "[exe] 装置信息（$FLAVOUR 版）内嵌自 $FY_FACTS_RS"


#: ★资源表里的 `include_bytes!` 走 `env!("FYLITE_APP_DIR")`，所以编译期必须给。
#: ★指向**装好的那棵树**，不是 `app/`：那一棵是这一版真正要发的字节。
[ -n "$STAGE" ] && export FYLITE_APP_DIR="$STAGE"

cd "$CRATE"

build_linux() {
  echo "[exe] linux x86-64 …"
  cargo build --release --no-default-features --features "$FEATURES" --bin fy
  ls -l "$OUT/release/fy"
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
    cargo build --release --no-default-features --features "$FEATURES" --bin fy --target "$target"
  local exe="$OUT/$target/release/fy.exe"
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
  cargo xwin build --release --features desktop --bin fy --target "$target"
  local exe="$OUT/$target/release/fy.exe"
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
