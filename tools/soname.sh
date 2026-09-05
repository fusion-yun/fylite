#!/usr/bin/env bash
# 制品的**版本化命名**——一条规则，两个仓，一份实现。
#
# 照 Linux 动态链接库的习惯，一个制品装出**三个名字**：
#
#   libfylite_kernel.so.0.0.1   真文件（唯一带字节的那个）
#   libfylite_kernel.so.0       -> .so.0.0.1   「soname」：兼容代
#   libfylite_kernel.so         -> .so.0       「linker name」：不问版本的那个名字
#
# ★★`.wasm` **同规则**（用户裁定 2026-09-05）：`fylite_rs.wasm.0.0.1` +
# `fylite_rs.wasm.0` + `fylite_rs.wasm`。它不是「Linux 习惯适用于 wasm」，而是
# **同一仓里两种制品不该有两套命名**——读者在 `_lib/` 看见的形状与在 `app/assets/`
# 看见的形状一样，就不必记两条规矩。
# ★把版本缀在**扩展名之后**，静态主机会按 `application/octet-stream` 发这个文件。
# 这在本仓不构成问题，且早于本次改动就已经不构成问题：页面的加载器
# （`app/assets/fylite.js` 的 `load()`）**有意不用** `instantiateStreaming`，
# 走 `fetch` → `arrayBuffer` → `instantiate`，那条路不看 Content-Type。
# 那段注释在那儿好几个月了，理由写的正是「有些静态主机 .wasm 的 Content-Type 是错的」。
#
# ★为什么要版本化：`_lib/` 与 `app/assets/` 装的是**别的仓构建出来的**字节，而
# 它们不入库。此前那里只有一个不带版本的名字，于是「这台机器上装的是哪一版内核」
# 只能靠 `_abi.py`（生成物，可能与 `.so` 不同批）回答，或者靠 `sha256` 反查。
# 现在文件名自己说得出来——`ls _lib/` 即是答案，也让 `rust/build.sh` 的内核检查
# 有一个不必打开二进制就能读的判据。
#
# ★★为什么这份文件在**公开仓**而内核仓 source 它：内核仓的 `rust/build.sh` 在做
# 任何事之前就要解析出公开仓检出（`$FYLITE_PUBLIC`，解析不出即报错退出），所以
# 「两个仓都能读到同一份实现」是现成的，不需要第三个地方。规则抄两遍就会分家，
# 而分家的那天，先发现的人是拿到制品的那个——这正是本仓其它几处生成物
# （`_abi.py` / `fyo-interface` / `mds-request`）反复写下的同一条理由。
#
# 用法：
#   source tools/soname.sh
#   fy_install_versioned <源文件> <目标目录> <逻辑名> <版本>
#   fy_installed_version <目标目录> <逻辑名>      # 打印装着的那一版，没有则空

#: 版本串的第一段。`0.0.1` -> `0`；`1.2.3-rc1` -> `1`。
#: ★兼容代取 MAJOR 而不是 ABI 号（`abi.rs` 的那个整数，今天 125）：ABI 号是
#: **另一个量**，装载方自己核对（`fylite_rs_abi_version` 与 `_abi.py`），把它塞进
#: 文件名会让一个名字同时承担两套编号，而读者分不清哪个在说话。
fy_soname_major() {
    printf '%s' "${1%%.*}"
}

#: 把 `$1` 装成 `$3.$4`，并补上 `$3.<major>` 与 `$3` 两级符号链接。
#:
#: ★**先清同名的旧版本再装**：不清就会攒——`_lib/` 里躺着 0.0.1 与 0.0.2 两个真
#: 文件，而不带版本的那个名字指着其中一个，「哪一份在跑」又变回一个要查的问题。
#: 目录里只留一版是有意的：这两个目录是**装配目标**，不是版本仓库。
#: ★用 `ln -sfn` 相对链接：`_lib/` 与 `app/assets/` 会被整个拷走（轮、站点、
#: 内嵌树），绝对链接一拷出去就是悬空的。
fy_install_versioned() {
    local src="$1" dest="$2" logical="$3" ver="$4"
    local major; major="$(fy_soname_major "$ver")"
    [ -f "$src" ] || { echo "[soname] 没有 $src" >&2; return 1; }
    [ -n "$ver" ] || { echo "[soname] $logical 没有版本号" >&2; return 1; }
    mkdir -p "$dest"
    #: ★★`find -maxdepth 1` 而不是 `rm -f "$dest/$logical".*`：后者的 glob 在
    #: 「一个都不匹配」时会把**字面量**传给 rm，而 `rm -f` 对它不报错——看起来
    #: 清过了，其实什么也没做。这里要的是「清干净或说清为什么」。
    find "$dest" -maxdepth 1 \( -name "$logical" -o -name "$logical.*" \) -exec rm -f {} +
    cp "$src" "$dest/$logical.$ver"
    ln -sfn "$logical.$ver" "$dest/$logical.$major"
    ln -sfn "$logical.$major" "$dest/$logical"
    echo "[soname] $dest/$logical -> $logical.$major -> $logical.$ver" \
         "($(stat -c%s "$dest/$logical.$ver") bytes)"
}

#: 目标目录里装着的是哪一版——**从真文件名读**，不打开文件。
#: 空输出 = 没装。★跟着链接走而不是列目录：目录里也可能有别的东西，而
#: 「不带版本的那个名字指着谁」才是装载方实际会拿到的那一份。
fy_installed_version() {
    local dest="$1" logical="$2" real
    [ -e "$dest/$logical" ] || return 0
    real="$(basename "$(readlink -f "$dest/$logical")")"
    case "$real" in
        "$logical".*) printf '%s' "${real#$logical.}" ;;
        #: 装的是个不带版本的真文件——上一版规矩留下的东西，或者有人手工拷了一份。
        #: 报一个可辨认的值，让调用方能说出「这不是本规则装的」而不是当成没装。
        *) printf 'unversioned' ;;
    esac
}
