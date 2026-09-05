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
use std::path::PathBuf;

const EMPTY: &str = "\
// 自带的那一档：这一次构建没有给 $FY_FACTS_RS，所以它是空的。\n\
pub static EMBEDDED: &[(&str, &str, &str)] = &[];\n";

fn main() {
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
