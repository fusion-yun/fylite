//! 把**发行版自带的装置信息**编进这个库（2026-09-05 用户裁定：
//! 「fylite 下已无 facts 目录；装置信息打包进发行版二进制」，同日续裁
//! 「页面也走中间层 wasm，撤掉 `facts.jsonld`」）。
//!
//! ★★为什么是构建脚本，不是提交进仓的生成物。装置文档是**受许可约束的数据**
//! （EAST 明写 NOT OPEN），而本仓是公开的：把它们写成一个 `.rs` 提交进来，就是
//! 用另一种语法发布同一批字节。所以它落在 `$OUT_DIR` —— 在 `target/` 下、从不入库，
//! `git add -A` 够不着。
//!
//! ★★为什么抄一个现成的文件，而不是自己走目录。许可闸只有一处实现
//! （`tools/facts-publish.py` 读每台的 `rights.json`），这里若自己扫一遍目录，
//! 那条规则就有了第二份实现——而两处各判一遍，某天它们会给出不同的答案，先发现的
//! 人是拿到制品的那个。所以这里只做一件事：把那个工具写出来的 `facts.rs` 抄进来。
//!
//!   FY_FACTS_RS=dist/facts.rs cargo build --release
//!
//! 不给就写一张**空表**：源码检出里 `cargo build` 照常成功，而 `fy list devices`
//! 会说自带的那一档是空的——这与「构建失败」是两回事，也与「静默少带一台」是两回事。
use std::path::{Path, PathBuf};

const EMPTY: &str = "\
// 自带的那一档：这一次构建没有给 $FY_FACTS_RS，所以它是空的。\n\
pub static EMBEDDED: &[(&str, &str, &str)] = &[];\n";

fn main() {
    link_kernel();
    println!("cargo:rerun-if-env-changed=FY_FACTS_RS");
    let out = PathBuf::from(std::env::var("OUT_DIR").expect("OUT_DIR")).join("facts_table.rs");
    match std::env::var("FY_FACTS_RS") {
        Ok(p) if !p.trim().is_empty() => {
            println!("cargo:rerun-if-changed={p}");
            let src = std::fs::read_to_string(&p)
                .unwrap_or_else(|e| panic!("FY_FACTS_RS={p}: {e}"));
            //: ★按名核对它确实是那个工具的产物：一个指错了的路径会编出一个**能编过
            //: 而没有装置**的库，而那是静默的。
            assert!(
                src.contains("pub static EMBEDDED: &[(&str, &str, &str)]"),
                "FY_FACTS_RS={p} 不像 tools/facts-publish.py 的产物（没有 EMBEDDED 表）"
            );
            let n = src.matches("\n    (\"").count();
            std::fs::write(&out, src).expect("write facts_table.rs");
            println!("cargo:warning=fylite_runtime: {n} bundled facts document(s) from {p}");
        }
        _ => {
            std::fs::write(&out, EMPTY).expect("write facts_table.rs");
            println!("cargo:warning=fylite_runtime: no FY_FACTS_RS — bundled facts table is empty");
        }
    }
}

/// 内核的**静态库**形 —— `fy` 把它链进去（2026-09-05 用户裁定）。
///
/// ★★裁定原话：「fy 封装 fylite_kernel 静态库，.so 是留给 python 层，wasm 留给静态
/// 网页发布」。三种形各有唯一的读者，这里管第一种：看见那份 `.a` 就链上，并打开
/// `cfg(kernel_static)`——`src/kernel_abi.rs`（内核仓生成的调度表）整个挂在它后面。
///
/// ★为什么是 cfg 而不是 feature：feature 得由调用方在命令行上给，而「这台机器上有
/// 没有那份归档」是构建脚本才知道的事。给了 feature 却没有归档，报的是几百条
/// `undefined reference`；这样则是一句 `cargo:warning` 与一条**能编过**的构建。
///
/// ★wasm 目标一律不链：那边没有原生归档，也不需要——静态站点自己就是走 wasm 的
/// 那一端。
fn link_kernel() {
    //: ★声明这个 cfg 是本构建脚本设的，否则每个用到它的地方都会挂一条
    //: `unexpected_cfg` 警告——而警告多了就没人读了。
    println!("cargo::rustc-check-cfg=cfg(kernel_static)");
    println!("cargo:rerun-if-env-changed=FYLITE_KERNEL_A");
    let target = std::env::var("TARGET").unwrap_or_default();
    if target.contains("wasm32") {
        return;
    }
    let root = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let mut tried: Vec<PathBuf> = Vec::new();
    if let Ok(p) = std::env::var("FYLITE_KERNEL_A") {
        if !p.trim().is_empty() {
            tried.push(PathBuf::from(p));
        }
    }
    //: 内核仓的 `rust/build.sh` 装到这里（制品不入库，见 .gitignore）。
    tried.push(root.join("..").join("kernel-lib").join("libfylite_kernel_static.a"));
    for a in &tried {
        if !a.is_file() {
            continue;
        }
        let dir = a.parent().unwrap_or(Path::new("."));
        println!("cargo:rerun-if-changed={}", a.display());
        //: ★★2026-09-05 实测的坑：这份归档与装着的 .so 版本、ABI、接口摘要三者全同，却可以
        //: 是**不同的字节**（内核仓两次构建之间，同一版本号）。链进本 crate 的那份没有任何
        //: 自述，于是「运行时里的内核是哪一次构建」无处可查——八条门在它上面红、在新 .so 上
        //: 绿，而没有一个数说得出为什么。内核仓的 build.sh 在归档旁写了 kernel-static.json
        //: （built · sha256）；把它**编进本 crate**，运行期就答得出「我链的是哪一份」，
        //: 而 `check_kernel` / 一条 Python 闸子就能拿它对着归档现在的那份比。
        let json = dir.join("kernel-static.json");
        println!("cargo:rerun-if-changed={}", json.display());
        if let Ok(text) = std::fs::read_to_string(&json) {
            let one_line: String = text.split_whitespace().collect::<Vec<_>>().join(" ");
            println!("cargo:rustc-env=FYLITE_LINKED_KERNEL_JSON={one_line}");
        }
        println!("cargo:rustc-link-search=native={}", dir.display());
        //: ★★**按路径交给链接器**，而不是 `-l static=`。差别不是风格：`-l static=`
        //: 让 rustc 在**自己的 LTO 那一步**收下这份归档，而归档里的对象没有
        //: `.llvmbc` 段（`staticlib` 的产物是成品对象，不带位码），于是整条构建以
        //: 一句 `failed to get bitcode from object file for LTO` 停住——而本 crate 的
        //: 发布档正是 `lto = true`。写成链接参数则是在 LTO 之后交给链接器，
        //: 内核这份归档不参与 rustc 的 LTO（它本来也没什么可参与的：跨语言边界是
        //: C ABI，LTO 跨不过去），本 crate 自己的 LTO 一点没少。
        println!("cargo:rustc-link-arg={}", a.display());
        //: ★★两份 Rust 制品链在一起，std 的那几个符号（分配器垫片、unwind 个性
        //: 例程）会在归档与本二进制里各有一份**完全相同**的定义。链接器对此的缺省
        //: 答复是拒绝，而两份来自同一次 rustc、逐字节相同——所以这里明说「允许」，
        //: 而不是把内核改成动态库绕开它（那正是裁定分开的三种形之一，不能混用）。
        println!("cargo:rustc-link-arg=-Wl,--allow-multiple-definition");
        println!("cargo:rustc-cfg=kernel_static");
        //: ★★**算力的身份**要跟着进二进制。页面的续算闸（`app/assets/checkpoint.js`）
        //: 判的是「写这份状态的内核是不是当前这个」，判据是内核的 sha256——在 wasm
        //: 那条路上那是那份 `.wasm` 的散列。走 `/api/kernel` 时没有「那份文件」可散列，
        //: 于是这里把**链进来的那份归档**的散列baked 进去：它正是跑起来的那些字节。
        //: 内核仓装 `.a` 时把散列写在 `kernel-static.json` 里，这里读它——不在这里
        //: 现算，是因为 build.rs 没有散列实现，而多引一个依赖只为算一次散列不划算。
        let stamp = dir.join("kernel-static.json");
        let (sha, ver) = read_stamp(&stamp);
        println!("cargo:rerun-if-changed={}", stamp.display());
        println!("cargo:rustc-env=FYLITE_KERNEL_SHA256={sha}");
        println!("cargo:rustc-env=FYLITE_KERNEL_VERSION={ver}");
        println!("cargo:warning=fylite_runtime: kernel statically linked from {} ({} {})",
                 a.display(), ver, &sha[..sha.len().min(12)]);
        return;
    }
    println!("cargo:rustc-env=FYLITE_KERNEL_SHA256=");
    println!("cargo:rustc-env=FYLITE_KERNEL_VERSION=");
    println!(
        "cargo:warning=fylite_runtime: no kernel static library ({}) — /api/kernel will say so",
        tried.iter().map(|p| p.display().to_string()).collect::<Vec<_>>().join(", ")
    );
}

/// `kernel-static.json` 里的 `sha256` 与 `kernel_version`；读不到就是两个空串。
///
/// ★手写取值而不是引一个 JSON 库：构建脚本的依赖会进每一次构建，而这里要的是
/// 两个字符串。文件是同一次构建里由内核仓写的，格式不会漂——真漂了，读到空串，
/// 于是 `/api/health` 报 `null`，页面说「这个内核没报出身份」，而不是报一个错的。
fn read_stamp(p: &Path) -> (String, String) {
    let Ok(text) = std::fs::read_to_string(p) else {
        return (String::new(), String::new());
    };
    let field = |k: &str| -> String {
        text.split(&format!("\"{k}\""))
            .nth(1)
            .and_then(|rest| rest.split(':').nth(1))
            .and_then(|rest| rest.split('"').nth(1))
            .unwrap_or("")
            .to_string()
    };
    (field("sha256"), field("kernel_version"))
}
