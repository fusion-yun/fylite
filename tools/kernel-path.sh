#!/usr/bin/env bash
# 解析出**内核检出**（私有仓 fylite_kernel）的位置，供本仓需要它的脚本 source。
#
# ★★2026-09-05 这份文件**落在本仓**。`tools/build-wheel.sh` 从落地那天起就写着
# `. "$(dirname "$0")/kernel-path.sh"`，而本仓从来没有这个文件——同名的那份留在
# 内核仓的 `tools/` 里，仓一分为二时没跟过来。后果不是「少一个功能」：`set -e` 下
# source 一个不存在的文件当场退出，**打轮脚本在 develop 上一直是死的**，死在
# NOTICE 比对那一步之前。没人先发现，是因为 alpha 期还没走过一次真的发行。
#
# ★★2026-09-01 仓一分为二：本仓（fylite，公开）有 `app/` `python/` `tests/`
# `tools/`，Rust 源码在 **fylite_kernel**（私有）。于是本仓有两类脚本：
#
#   * 只用本仓东西的 —— `build-guide.sh`、各个 `make-*.mjs`。它们**不该**碰内核
#     检出，也就不该 source 本文件。
#   * 要问内核一句话的 —— `build-wheel.sh`（比对 NOTICE）、`rust/build.sh`
#     （构建前的内核检查：装着的 `.so` 是不是内核仓今天这一版）。
#
# 用法：
#     . "$(dirname "$0")/kernel-path.sh"
#     fylite_resolve_kernel "$REPO_ROOT" || …      # 成功后 $KERNEL 可用
#     FYLITE_KERNEL=/path/to/fylite_kernel bash tools/build-wheel.sh
#
# ★解析不到**返回非零，不猜**。调用方各自决定这算不算错——`build-wheel.sh` 少一次
# NOTICE 比对仍可打轮，`rust/build.sh` 少一次内核比对仍可构建中间层——但没有一个
# 调用方该拿一条猜出来的路径去读另一个仓。

fylite_resolve_kernel() {
    local root="$1" c main
    if [ -z "${FYLITE_KERNEL:-}" ]; then
        #: ★★按**主检出**的同级目录探测，不是 `$root/..`。本仓常在 worktree 里
        #: 干活（`.claude/worktrees/<name>/`），那时 `$root/..` 是 `worktrees/`，
        #: 同级探测必落空——而落空的表现是「没有内核检出」，一句听起来完全正常的
        #: 话。`--git-common-dir` 在 worktree 里指回主检出的 `.git`。
        main="$(git -C "$root" rev-parse --path-format=absolute \
                --git-common-dir 2>/dev/null || true)"
        [ -n "$main" ] && main="$(dirname "$main")"
        #: 同级目录探测。★两个名字都试：GitHub 上的仓叫 `fylite_kernel`，
        #: 而本机检出目录一度仍叫 `fylite_dev`（仓改名在前、目录改名在后）。
        #: 只认一个名字就会在改名的空档里探测失败。
        for c in "${main:-$root}/../fylite_kernel" "${main:-$root}/../fylite_dev" \
                 "$root/../fylite_kernel" "$root/../fylite_dev"; do
            if [ -f "$c/rust/fylite/Cargo.toml" ]; then
                FYLITE_KERNEL="$(cd "$c" && pwd)"; break
            fi
        done
    fi
    if [ -z "${FYLITE_KERNEL:-}" ] || [ ! -f "$FYLITE_KERNEL/rust/fylite/Cargo.toml" ]; then
        return 1
    fi
    KERNEL="$FYLITE_KERNEL"
    export FYLITE_KERNEL KERNEL
}

#: 内核检出**声明**的两个数：crate 版本与 ABI 号。装进本仓的制品应当与它们一致，
#: 而判据只有这一处——两个脚本各自 `sed` 一遍，某一天它们会读不同的行。
#: 成功后 $KERNEL_VERSION / $KERNEL_ABI 可用。
fylite_kernel_declared() {
    local k="$1"
    KERNEL_VERSION="$(sed -n '0,/^version *= *"\([^"]*\)".*/s//\1/p' \
                      "$k/rust/fylite/Cargo.toml" 2>/dev/null)"
    #: ★ABI 号 2026-09-04 从 `c_api.rs` 搬进了 `abi.rs`（分包：两个包都要它）。
    #: 内核仓自己的 `rust/build.sh` 读的就是这一处。
    KERNEL_ABI="$(sed -n 's/^pub const ABI_VERSION: u32 = \([0-9]*\);.*/\1/p' \
                  "$k/rust/fylite/src/abi.rs" 2>/dev/null)"
    [ -n "$KERNEL_VERSION" ] && [ -n "$KERNEL_ABI" ]
}
