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

//: ★★没给 `$FY_FACTS_RS` 时版别记 **internal**，不是「未知」也不是 public
//: （`FYL-SDD-03` A-18）。这一格只有一个读者——启动 banner 据它决定说不说
//: 「仅限内部测试」——而对一条**限制**来说，猜错的两个方向不等价：多说一句的
//: 代价是一份公开构建上多一行字，少说一句的代价是一份内部构建看起来可以外发。
const EMPTY: &str = "\
// 自带的那一档：这一次构建没有给 $FY_FACTS_RS，所以它是空的。\n\
pub static FLAVOUR: &str = \"internal\";\n\
pub static EMBEDDED: &[(&str, &str, &str)] = &[];\n\
pub static EMBEDDED_RESOLUTION: &[(&str, &str, &str)] = &[];\n";

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
                src.contains("pub static EMBEDDED: &[(&str, &str, &str)]")
                    && src.contains("pub static FLAVOUR: &str"),
                "FY_FACTS_RS={p} 不像 tools/facts-publish.py 今天的产物（要有 EMBEDDED 表与 FLAVOUR 常量）——重跑 tools/facts-publish.py"
            );
            //: ★2026-09-13 (R-S1): the per-device resolution rows (`EMBEDDED_RESOLUTION`) came
            //: later than the table; a `facts.rs` written before them still builds — with none,
            //: which `fy list devices` then reports as a card that does not resolve by shot.
            let mut src = src;
            if !src.contains("pub static EMBEDDED_RESOLUTION") {
                src.push_str("pub static EMBEDDED_RESOLUTION: &[(&str, &str, &str)] = &[];\n");
            }
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
    //: ★★2026-09-16 用户裁定「仅生成静态链接库 libfylite_kernel.a 等」之后，内核仓
    //: 装出来的名字是 `libfylite_kernel.a`；`libfylite_kernel_static.a` 是上一代的
    //: 名字（cargo 按 `[lib] name` 出的那个），留着是为了一个还没重建内核的检出
    //: 仍然链得出东西，而不是以「没有内核」静默降级。
    tried.push(root.join("..").join("kernel-lib").join("libfylite_kernel.a"));
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
        //: **所有目标**都拿到这份归档：可执行文件 `fy`、集成测试，以及 lib 自己的
        //: 单元测试。★这里曾按目标分开给（`-bins` / `-tests`），结果 `cargo test` 当场
        //: 红在**lib 的单元测试**上——`rustc-link-arg-tests` 管的是 `tests/` 下的集成
        //: 测试，`--lib` 那个测试二进制不在其中，于是它链不到 `fylite_rs_fyo` 一族
        //: （实测 1.98.1）。不分目标的这一条管得住全部。
        println!("cargo:rustc-link-arg={}", a.display());
        //: ★★两份 Rust 制品链在一起，std 的那几个符号（分配器垫片、unwind 个性
        //: 例程）会在归档与本二进制里各有一份**完全相同**的定义。链接器对此的缺省
        //: 答复是拒绝，而两份来自同一次 rustc、逐字节相同——所以这里明说「允许」，
        //: 而不是把内核改成动态库绕开它。
        println!("cargo:rustc-link-arg=-Wl,--allow-multiple-definition");
        //: ★★★`cdylib` **另外**再要几条（上面那条对它不够）：从今天起
        //: `libfylite.so` 就是内核的运行期形式（用户裁定：内核仓只出 `.a`，动态库在
        //: 本仓与中间层打包成一个），所以那 59 个 C 入口必须真的**导出**，而不是
        //: 「链接器认为没人引用就不取、或者取了也降成本地」。见 `cdylib_args`。
        cdylib_args(a, &pkg_version());
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

/// 本包的版本（`libfylite.so.<主版本>` 的那个主版本从它取）。
fn pkg_version() -> String {
    std::env::var("CARGO_PKG_VERSION").unwrap_or_default()
}

/// `cdylib` 那一份的链接参数 —— **让内核那 59 个 C 入口真的从 `libfylite.so` 导出**。
///
/// ★★★2026-09-16 用户裁定：「在 fylite 仓与 fylite_runtime 一起打包进可执行文件，
/// 动态链接库 libfylite.so，和 wasm」。于是这个库同时是**两层的运行期形式**：
/// `fylite_runtime_*`（本 crate 自己的导出，rustc 负责）与 `fylite_rs_*` /
/// `fylite_ext_*`（内核那份归档里的 C 入口）。
///
/// ★★两件事必须同时做，少一件就是一个**能编过、也能装、而 `dlopen` 之后按名找不到
/// 内核**的库（实测，2026-09-16）：
///
///   1. `--whole-archive`：不这么给，链接器只取本 crate 真引用到的那些成员，
///      其余 C 入口根本不进库。
///   2. **第二份 version script**：rustc 为每个 `cdylib` 自动写一份
///      `{ global: <本 crate 的导出>; local: *; };`，那条 `local: *` 会把归档里带进来的
///      符号全部降成本地——实测「静态符号表里有、`nm -D` 里没有」，而 ctypes 找的正是
///      后者。GNU ld 允许给多份脚本并按**精确/模式匹配的优先级**合并，于是这里补一份
///      只说 global 的：两个前缀通配，内核的 59 个入口回到动态符号表，本 crate 自己的
///      那些照旧由 rustc 那份管着。实测 57 个 `fylite_rs_*` + 2 个 `fylite_ext_*` ✓
///
/// ★`-soname`：产物文件名仍是 cargo 按 `[lib] name` 出的 `libfylite_runtime.so`，
/// 装出去时才改名 `libfylite.so.<版本>`（`rust/build.sh` → `tools/soname.sh`）。
/// soname 要与**装出去的那个名字**一致，否则将来谁按 `-lfylite` 链它，运行期找的会是
/// 一个不存在的 `libfylite_runtime.so`。
fn cdylib_args(archive: &Path, version: &str) {
    let out = PathBuf::from(std::env::var("OUT_DIR").expect("OUT_DIR"));
    let map = out.join("fylite-kernel-exports.map");
    //: ★写两个**通配**而不是把 `kernel-static.json` 的名单展开：名单会随每一刀退役
    //: 变，而这两个前缀是 ABI 的形状（`fylite_rs_` 核心与 TGLF/DKE、`fylite_ext_` 扩展
    //: 自己的两扇门），它不变。名单那份另有读者——`rust/build.sh` 拿它对着装好的库
    //: 逐个核对「该有的都在」。
    if let Err(e) = std::fs::write(&map, "{ global: fylite_rs_*; fylite_ext_*; };\n") {
        panic!("写不出 {}: {e}", map.display());
    }
    println!("cargo:rustc-link-arg-cdylib=-Wl,--whole-archive");
    println!("cargo:rustc-link-arg-cdylib={}", archive.display());
    println!("cargo:rustc-link-arg-cdylib=-Wl,--no-whole-archive");
    println!("cargo:rustc-link-arg-cdylib=-Wl,--allow-multiple-definition");
    println!("cargo:rustc-link-arg-cdylib=-Wl,--version-script={}", map.display());
    let major = version.split('.').next().unwrap_or("0");
    println!("cargo:rustc-link-arg-cdylib=-Wl,-soname,libfylite.so.{major}");
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
