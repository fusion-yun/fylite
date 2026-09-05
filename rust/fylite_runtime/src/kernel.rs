//! The kernel, loaded at run time — the one door and nothing else.
//!
//! ★★Why `dlopen` and not a crate dependency.  The kernel's source is not
//! public and this crate is; a `path` dependency would make the public
//! crate unbuildable without the private checkout, and a `cdylib` link
//! at build time would pin one library to one binary.  Python loads the
//! same `libfylite_kernel.so` by name (`fylite/kernel.py`), and this does
//! the same: one artifact, two hosts, found by the same rule — an explicit
//! path, `FYLITE_KERNEL_LIB`, or the checkout's `python/fylite/_lib/`.
//!
//! ★What crosses the door is a STRUCTURE (`fylite_rs_fyo` in the kernel's
//! `c_api.rs`): the code, settings by name, inputs by fyo path; back come a
//! manifest (fields by fyo path, with offsets) and the flat data, in
//! buffers the kernel owns and this side releases through `fylite_rs_free`.
//! Turning that into documents is [`crate::case`]'s job.

use std::ffi::{c_char, c_int, c_void, CString};
use std::path::{Path, PathBuf};

#[link(name = "dl")]
extern "C" {
    fn dlopen(filename: *const c_char, flag: c_int) -> *mut c_void;
    fn dlsym(handle: *mut c_void, symbol: *const c_char) -> *mut c_void;
    fn dlerror() -> *const c_char;
}

const RTLD_NOW: c_int = 2;

type FyoFn = unsafe extern "C" fn(
    *const u8, u64,
    u64, *const *const u8, *const u64, *const f64,
    u64, *const *const u8, *const u64, *const *const u8, *const u64,
    u64, *const *const u8, *const u64, *const u64, *const f64,
    *mut *mut u8, *mut u64, *mut *mut f64, *mut u64) -> i32;
type FreeFn = unsafe extern "C" fn(*mut u8, u64);
type AbiFn = unsafe extern "C" fn() -> u32;

/// A loaded kernel.
pub struct Kernel {
    pub path: PathBuf,
    pub abi_version: Option<u32>,
    fyo: FyoFn,
    free: FreeFn,
}

/// What the kernel handed back for one case: the manifest text and the
/// flat data its offsets index.
#[derive(Debug, Clone)]
pub struct RawOutcome {
    pub manifest: String,
    pub data: Vec<f64>,
}

#[derive(Debug, Clone)]
pub struct KernelError {
    /// The kernel's code (negative), or 0 for a loader-side failure.
    pub code: i64,
    pub message: String,
}

impl std::fmt::Display for KernelError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if self.code != 0 { write!(f, "[{}] {}", self.code, self.message) } else { f.write_str(&self.message) }
    }
}

fn err(message: impl Into<String>) -> KernelError {
    KernelError { code: 0, message: message.into() }
}

/// Where to look for `libfylite_kernel.so`, in order: `explicit`, the
/// environment (`FYLITE_KERNEL_LIB`), the checkout above this binary or
/// the working directory (`python/fylite/_lib/libfylite_kernel.so`), and
/// finally the kernel's own build tree beside a sibling checkout.
pub fn candidates(explicit: Option<&Path>) -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Some(p) = explicit {
        out.push(p.to_path_buf());
    }
    if let Ok(p) = std::env::var("FYLITE_KERNEL_LIB") {
        if !p.is_empty() {
            out.push(PathBuf::from(p));
        }
    }
    let rel = Path::new("python/fylite/_lib/libfylite_kernel.so");
    if let Ok(cwd) = std::env::current_dir() {
        for up in [cwd.clone(), cwd.join(".."), cwd.join("../..")] {
            out.push(up.join(rel));
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        let mut d = exe.parent().map(Path::to_path_buf);
        for _ in 0..6 {
            let Some(dir) = d else { break };
            out.push(dir.join(rel));
            out.push(dir.join("libfylite_kernel.so"));
            d = dir.parent().map(Path::to_path_buf);
        }
    }
    if let Ok(cwd) = std::env::current_dir() {
        for up in [cwd.clone(), cwd.join(".."), cwd.join("../..")] {
            for profile in ["release", "debug"] {
                out.push(up.join(format!("../fylite_kernel/rust/fylite/target/{profile}/libfylite_kernel.so")));
            }
        }
    }
    out
}

//: ★★**链进来的那一份内核**（2026-09-05 用户裁定：「fy 封装 fylite_kernel 静态库，
//: .so 是留给 python 层，wasm 留给静态网页发布」）。声明三个符号就够了：结构门、
//: 它的释放函数、ABI 号——`run_case` 要的正是这三个。其余 250 个由生成的
//: `kernel_abi.rs` 声明，那是**调用门**（页面走 `/api/kernel`）。
//: ★`cfg(kernel_static)` 由 `build.rs` 在看见那份 `.a` 时打开。没有归档的检出编译
//: 照旧，只是这一段不存在，`load()` 退回 dlopen。
#[cfg(kernel_static)]
extern "C" {
    fn fylite_rs_fyo(
        code: *const u8, code_n: u64,
        n_num: u64, num_k: *const *const u8, num_kl: *const u64, num_v: *const f64,
        n_txt: u64, txt_k: *const *const u8, txt_kl: *const u64,
        txt_v: *const *const u8, txt_vl: *const u64,
        n_in: u64, in_k: *const *const u8, in_kl: *const u64, in_len: *const u64,
        in_data: *const f64,
        man: *mut *mut u8, man_n: *mut u64, data: *mut *mut f64, data_n: *mut u64,
    ) -> i32;
    fn fylite_rs_free(p: *mut u8, n: u64);
    fn fylite_rs_abi_version() -> u32;
}

impl Kernel {
    /// 链进本二进制的那一份内核，如果这一次构建带着它。
    ///
    /// ★★这条路**不碰文件系统**：算力是可执行文件自己的一部分，所以 `fy run` 在
    /// 一台没有装任何 `.so` 的机器上照样完整。`path` 记成 `<linked>` 而不是一条假
    /// 路径——问「内核从哪里来」的人应当得到真话。
    #[cfg(kernel_static)]
    pub fn linked() -> Kernel {
        Kernel {
            path: PathBuf::from("<linked>"),
            abi_version: Some(unsafe { fylite_rs_abi_version() }),
            fyo: fylite_rs_fyo,
            free: fylite_rs_free,
        }
    }

    /// 这一次构建是不是自带算力。
    pub fn is_linked_in() -> bool {
        cfg!(kernel_static)
    }

    /// Load the first candidate that exists and carries the door.
    pub fn load(explicit: Option<&Path>) -> Result<Kernel, KernelError> {
        //: ★★没人指定就用链进来的那一份。**显式给的路径仍然赢**（`--kernel` 或
        //: `$FYLITE_KERNEL_LIB`）：那是「就用这一个」的意思，通常是有人在拿一份
        //: 现编的内核对照本二进制里的这一份——把那条退路封掉，就没法比了。
        #[cfg(kernel_static)]
        if explicit.is_none() && std::env::var_os("FYLITE_KERNEL_LIB").is_none() {
            return Ok(Kernel::linked());
        }
        let cands = candidates(explicit);
        let mut tried = Vec::new();
        for c in &cands {
            if !c.is_file() {
                tried.push(format!("{} (absent)", c.display()));
                continue;
            }
            match Kernel::open(c) {
                Ok(k) => return Ok(k),
                Err(e) => tried.push(format!("{} ({})", c.display(), e.message)),
            }
        }
        Err(err(format!(
            "no kernel library with the fyo door found; looked at:\n  {}\n\
             (pass --kernel <path>, set FYLITE_KERNEL_LIB, or build it with the kernel's rust/build.sh)",
            tried.join("\n  "))))
    }

    fn open(path: &Path) -> Result<Kernel, KernelError> {
        let c = CString::new(path.to_string_lossy().as_bytes()).map_err(|_| err("path has a NUL"))?;
        let h = unsafe { dlopen(c.as_ptr(), RTLD_NOW) };
        if h.is_null() {
            let why = unsafe {
                let p = dlerror();
                if p.is_null() { String::from("dlopen failed") } else {
                    std::ffi::CStr::from_ptr(p).to_string_lossy().into_owned() }
            };
            return Err(err(why));
        }
        let sym = |name: &str| -> Result<*mut c_void, KernelError> {
            let cs = CString::new(name).unwrap();
            let p = unsafe { dlsym(h, cs.as_ptr()) };
            if p.is_null() { Err(err(format!("no symbol {name} — an older kernel without the fyo door"))) } else { Ok(p) }
        };
        let fyo: FyoFn = unsafe { std::mem::transmute(sym("fylite_rs_fyo")?) };
        let free: FreeFn = unsafe { std::mem::transmute(sym("fylite_rs_free")?) };
        let abi_version = sym("fylite_rs_abi_version").ok().map(|p| {
            let f: AbiFn = unsafe { std::mem::transmute(p) };
            unsafe { f() }
        });
        Ok(Kernel { path: path.to_path_buf(), abi_version, fyo, free })
    }

    /// Complete one case: the code, its numeric and text settings, and its
    /// bound inputs (key = fyo path or a raw entry's input key).
    pub fn run_case(&self, code: &str, numbers: &[(String, f64)], texts: &[(String, String)],
                    inputs: &[(String, Vec<f64>)]) -> Result<RawOutcome, KernelError> {
        let nk: Vec<*const u8> = numbers.iter().map(|(k, _)| k.as_ptr()).collect();
        let nkl: Vec<u64> = numbers.iter().map(|(k, _)| k.len() as u64).collect();
        let nv: Vec<f64> = numbers.iter().map(|(_, v)| *v).collect();
        let tk: Vec<*const u8> = texts.iter().map(|(k, _)| k.as_ptr()).collect();
        let tkl: Vec<u64> = texts.iter().map(|(k, _)| k.len() as u64).collect();
        let tv: Vec<*const u8> = texts.iter().map(|(_, v)| v.as_ptr()).collect();
        let tvl: Vec<u64> = texts.iter().map(|(_, v)| v.len() as u64).collect();
        let ik: Vec<*const u8> = inputs.iter().map(|(k, _)| k.as_ptr()).collect();
        let ikl: Vec<u64> = inputs.iter().map(|(k, _)| k.len() as u64).collect();
        let il: Vec<u64> = inputs.iter().map(|(_, v)| v.len() as u64).collect();
        let idata: Vec<f64> = inputs.iter().flat_map(|(_, v)| v.iter().copied()).collect();
        let (mut mp, mut ml, mut dp, mut dl) = (std::ptr::null_mut::<u8>(), 0u64, std::ptr::null_mut::<f64>(), 0u64);
        let rc = unsafe {
            (self.fyo)(code.as_ptr(), code.len() as u64,
                       nk.len() as u64, nk.as_ptr(), nkl.as_ptr(), nv.as_ptr(),
                       tk.len() as u64, tk.as_ptr(), tkl.as_ptr(), tv.as_ptr(), tvl.as_ptr(),
                       ik.len() as u64, ik.as_ptr(), ikl.as_ptr(), il.as_ptr(), idata.as_ptr(),
                       &mut mp, &mut ml, &mut dp, &mut dl)
        };
        let manifest = if mp.is_null() || ml == 0 { String::new() } else {
            let s = unsafe { std::slice::from_raw_parts(mp, ml as usize) };
            String::from_utf8_lossy(s).into_owned()
        };
        let data: Vec<f64> = if dp.is_null() || dl == 0 { Vec::new() } else {
            unsafe { std::slice::from_raw_parts(dp, dl as usize) }.to_vec()
        };
        unsafe {
            if !mp.is_null() {
                (self.free)(mp, ml);
            }
            if !dp.is_null() {
                (self.free)(dp as *mut u8, dl * 8);
            }
        }
        if rc != 0 {
            return Err(KernelError { code: rc as i64, message: if manifest.is_empty() {
                format!("the kernel refused with code {rc} and no sentence") } else { manifest } });
        }
        Ok(RawOutcome { manifest, data })
    }
}
