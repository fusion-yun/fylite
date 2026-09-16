//! 空壳 —— 内容全部来自 `rust/kernel-lib/libfylite_kernel-wasm32.a`。
//!
//! ★★★2026-09-16 用户裁定：「修改 fylite_kernel 仓生成物，仅生成静态链接库
//! libfylite_kernel.a 等，在 fylite 仓与 fylite_runtime 一起打包进可执行文件，
//! 动态链接库 libfylite.so，和 wasm。」内核仓因此只出两份归档（原生 + wasm32），
//! 而三种可载入的形都在本仓装配：
//!
//! | 形 | 谁装配 | 内核从哪来 |
//! |---|---|---|
//! | `fy`（可执行） | `fylite_runtime` 的 `[[bin]]` | `libfylite_kernel.a` |
//! | `libfylite.so` | `fylite_runtime` 的 `cdylib` | 同上（`build.rs::cdylib_args`） |
//! | `fylite_rs.wasm` · `fylite_kernel_ext.wasm` | **本包** | `libfylite_kernel-wasm32.a` |
//!
//! ★两份 `.wasm` 出自**同一份归档**，差别只在导出面（`build.rs` 的 `FY_WASM_FACE`）：
//! 核心那份是页面启动就取的平衡 / 重建 / 0-D 面，扩展那份是 TGLF 与 DKE——页面
//! 只在要湍流闭合时才去取它。名字沿用从前内核仓出的那两个，因为它们是**页面 fetch
//! 的 URL**，改 URL 与改构建是两件事（`app/assets/fylite.js` 等约三十处在念它们）。
