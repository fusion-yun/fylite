//! 把内核那份 wasm32 归档里的 C 入口**按名钉成链接的根**。
//!
//! ★★wasm 与原生在这一点上完全不同（两处都实测过，2026-09-16）：
//!
//! * 原生的 `.so`：rustc 自动写一份 version script，末尾一条 `local: *` 把归档带进来
//!   的符号全部降成本地——那边的解法是**补第二份 version script**
//!   （`fylite_runtime/build.rs::cdylib_args`）。
//! * wasm：没有 version script 这回事。`wasm-ld` 只导出被明说的符号，而且**归档成员
//!   要有人引用才会被取进来**——没有任何 Rust 代码引用内核，于是不给 `--undefined`
//!   的话链出来的是一个 2 KB 的空模块（编译绿、页面一调就说函数不存在）。所以每个
//!   入口都要**两条**参数：`--undefined` 取进来，`--export` 导出去。
//!
//! ★★名单从 `kernel-static.json` 现读，不在本仓手抄一份：内核的导出面每隔几天就有
//! 一刀退役（见内核仓 build.sh 那段刀数记录），手抄的那份漂了不会有人发现——链接
//! 照样成功，只是少了几个入口，而发作是在页面上调用它的时候。
//!
//! ★参数**不带 `-Wl,`**：wasm32 目标上 rustc 直接调 `rust-lld`，不经 `cc`；带前缀
//! 会得到一串 `unknown argument: -Wl,--export=…`（实测）。
use std::path::PathBuf;

fn main() {
    println!("cargo:rerun-if-env-changed=FY_WASM_FACE");
    println!("cargo:rerun-if-env-changed=FYLITE_KERNEL_WASM_A");
    let target = std::env::var("TARGET").unwrap_or_default();
    if !target.contains("wasm32") {
        //: 原生下本包是个空库（没人链它）。不在这里报错：`cargo test` 一类会顺手
        //: 把工作区里每个包都编一遍，而那不是缺陷。
        return;
    }
    let root = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let dir = root.join("..").join("kernel-lib");
    let archive = match std::env::var("FYLITE_KERNEL_WASM_A") {
        Ok(p) if !p.trim().is_empty() => PathBuf::from(p),
        _ => dir.join("libfylite_kernel-wasm32.a"),
    };
    let stamp = archive.parent().unwrap_or(&dir).join("kernel-static.json");
    assert!(archive.is_file(), "没有内核的 wasm32 归档：{}（跑内核仓 rust/build.sh --wasm-check）",
            archive.display());
    println!("cargo:rerun-if-changed={}", archive.display());
    println!("cargo:rerun-if-changed={}", stamp.display());

    let face = std::env::var("FY_WASM_FACE").unwrap_or_else(|_| "core".into());
    let json = std::fs::read_to_string(&stamp)
        .unwrap_or_else(|e| panic!("读不出 {}: {e}", stamp.display()));
    let mut syms: Vec<&str> = json
        .split('"')
        .filter(|t| t.starts_with("fylite_rs_") || t.starts_with("fylite_ext_"))
        .collect();
    syms.sort_unstable();
    syms.dedup();
    //: ★★两份 `.wasm` 怎么分（沿用内核仓从前分两个包的那条线）：TGLF 与 DKE 的入口，
    //: 连同扩展自己的两扇门，归 `ext`；其余归 `core`。判据写在名字上（`_tglf_` /
    //: `_dke_` / `fylite_ext_` 前缀）而不是靠一份手抄的清单——那 15 个入口的名字与
    //: 它们属于哪个包是同一件事，内核仓的 `fylite_ext` 包里定义的正是这些。
    let is_ext = |s: &str| s.contains("_tglf_") || s.contains("_dke_") || s.starts_with("fylite_ext_");
    let want: Vec<&str> = syms.into_iter().filter(|s| is_ext(s) == (face == "ext")).collect();
    assert!(!want.is_empty(), "{} 里没有 {face} 面的入口", stamp.display());
    println!("cargo:warning=fylite_kernel_wasm: face={face}, {} 个入口 <- {}",
             want.len(), archive.display());

    //: ★归档里核心与扩展各带一份 `fylite_rs_alloc` / `_free` / `_abi_version`（两个包
    //: 都编了 capi 的那一小块）。原生那边同样要 `--allow-multiple-definition`——两份
    //: 出自同一次 rustc，逐字节相同。
    println!("cargo:rustc-link-arg-cdylib=--allow-multiple-definition");
    println!("cargo:rustc-link-arg-cdylib={}", archive.display());
    for s in &want {
        println!("cargo:rustc-link-arg-cdylib=--undefined={s}");
        println!("cargo:rustc-link-arg-cdylib=--export={s}");
    }
    //: ★DWARF 不进发行物（页面下载的是它）。`--strip-debug` 留下 name 段——出了事
    //: 浏览器的调用栈仍然有函数名，而那正是 wasm 这条路唯一的现场。
    println!("cargo:rustc-link-arg-cdylib=--strip-debug");
}
