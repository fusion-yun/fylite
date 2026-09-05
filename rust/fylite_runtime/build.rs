//! 把**发行版自带的装置信息**编进二进制（2026-09-05 用户裁定：
//! 「fylite 下已无 facts 目录；装置信息打包进发行版二进制」）。
//!
//! ★★为什么是构建脚本，不是提交进仓的生成物。装置文档是**受许可约束的数据**
//! （EAST 明写 NOT OPEN），而本仓是公开的：把它们写成一个 `.rs` 提交进来，就是
//! 用另一种语法发布同一批字节。所以生成物落在 `$OUT_DIR` —— 它在 `target/` 下、
//! 从不入库，`git add -A` 够不着。
//!
//! ★★为什么不是 `include_str!` 一条相对路径。`corpus.rs` 的场景模板可以那样写，
//! 因为那些文件**在仓里**；装置文档不在。用环境变量指一棵编译期的树，与
//! `src/bin/app/assets.rs` 走 `$FYLITE_APP_DIR` 是同一条路。
//!
//!   FY_FACTS_DIR=/path/to/staged/facts cargo build --release
//!
//! 不给就写一张**空表**：源码检出里 `cargo build` 照常成功，而 `fy list devices`
//! 会说自带的那一档是空的——这与「构建失败」是两回事，也与「静默少带一台」是两回事。
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

/// 一段文本能安全放进 `r#"..."#` 需要几个 `#`。
fn hashes(s: &str) -> usize {
    let mut n = 1;
    while s.contains(&format!("\"{}", "#".repeat(n))) {
        n += 1;
        //: ★不设上限的循环在这里是安全的：每多一个 `#` 都要求文本里真的有那么长
        //: 的一串，而文本是有限的。留个断言免得将来有人改了这段还以为它无害。
        assert!(n < 64, "a facts document with 64 consecutive '#' after a quote?");
    }
    n
}

fn entries(root: &Path) -> Vec<(String, String, String)> {
    let mut out = Vec::new();
    let Ok(domains) = std::fs::read_dir(root) else { return out };
    for d in domains.flatten() {
        if !d.path().is_dir() {
            continue;
        }
        let Some(domain) = d.file_name().to_str().map(str::to_string) else { continue };
        let Ok(files) = std::fs::read_dir(d.path()) else { continue };
        for f in files.flatten() {
            let p = f.path();
            if p.extension().and_then(|s| s.to_str()) != Some("jsonld") {
                continue;
            }
            let Some(stem) = p.file_stem().and_then(|s| s.to_str()) else { continue };
            let Ok(text) = std::fs::read_to_string(&p) else { continue };
            out.push((domain.clone(), stem.to_string(), text));
        }
    }
    //: 稳定次序：同一棵树两次构建给出同一份表，否则二进制无谓地不可复现。
    out.sort_by(|a, b| (&a.0, &a.1).cmp(&(&b.0, &b.1)));
    out
}

fn main() {
    println!("cargo:rerun-if-env-changed=FY_FACTS_DIR");
    let out = PathBuf::from(std::env::var("OUT_DIR").expect("OUT_DIR"));
    let mut src = String::from(
        "// 自带的那一档装置信息 —— 生成物（build.rs），在 $OUT_DIR 里，从不入库。\n\
         // 它由 `include!` 落进 `facts.rs` 的中间，所以只能用**行注释**：`//!` 是\n\
         // 模块级文档注释，只在文件开头合法，include 进去当场编不过。\n\
         pub static EMBEDDED: &[(&str, &str, &str)] = &[\n",
    );
    let mut n = 0;
    if let Ok(dir) = std::env::var("FY_FACTS_DIR") {
        let root = PathBuf::from(&dir);
        println!("cargo:rerun-if-changed={dir}");
        for (domain, ident, text) in entries(&root) {
            let h = "#".repeat(hashes(&text));
            let _ = write!(src, "    ({domain:?}, {ident:?}, r{h}\"{text}\"{h}),\n");
            n += 1;
        }
    }
    src.push_str("];\n");
    std::fs::write(out.join("facts_table.rs"), src).expect("write facts_table.rs");
    println!("cargo:warning=fylite_runtime: {n} bundled facts document(s)");
}
