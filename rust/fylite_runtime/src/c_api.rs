//! 数据层的 C ABI —— Python 经 `ctypes` 取数的那一面。
//!
//! ★★符号前缀是 **`fylite_runtime_`**，不是内核的 `fylite_rs_`。两个 `.so` 会被同一个
//! Python 进程同时 load（物理走内核那份、取数走这份），前缀分开是让它们**不可能**
//! 撞名；而且从符号名就看得出一个调用问的是哪一层。
//!
//! ★这一组 2026-09-02 曾短暂地长在内核的 C ABI 上（ABI 124）。搬到这里的理由见
//! `lib.rs` 抬头：网络协议不是算数那层的接口。内核已随之退回到「只算数」。

// =========================================================================== //
// THE DEVICE DATA PLANE — mdsip (FYL-DESIGN-06)
//
// ★★2026-09-02.  Until now `mdsip::Client` had exactly one consumer: the
// desktop viewer binary (`src/bin/app/api.rs`).  The Python layer read
// MDSplus through a client of its OWN — a second implementation of the same
// protocol, spelling the same `\EFIT_EAST::TOP…` node names separately, which
// is the shape this repository has been bitten by three times (the device
// description came out with a different WALL on the two sides; the `zerod`
// parameter order was spelled in three places).  These exports are the half
// that lets both hosts reach the one client.
//
// ★**Two patterns appear here for the first time in this ABI, deliberately
// and only here.**
//
//   1. A HANDLE.  Every other export is stateless — arrays in, arrays out.
//      An mdsip session is not: it is a socket with a login and a currently
//      open tree, and 483 bindings read over one connection rather than 483.
//      The handle is a `Box` pointer, not an index into a global table, so
//      the module preamble's "re-entrant" still holds: two sessions share
//      nothing.
//   2. STRINGS.  Passed as `(*const u8, len)` like every array here, NOT as
//      NUL-terminated `char*`: this ABI has no C-string contract and adding
//      one for four arguments would be a second convention to keep.
//
// ★The read-only guard is NOT relaxed by any of this.  `fylite_runtime_mds_read`
// takes a verb code, a node path and integers — `mdsip::tdi` assembles the
// TDI text and `is_node_path` refuses anything that is a language rather than
// a path.  There is still no export that takes an expression.
//
// ★Native only.  wasm has no socket; there the same `Client` is driven by a
// host-supplied `Transport` over a WebSocket (see the `mdsip` module).
// =========================================================================== //

#[cfg(not(target_arch = "wasm32"))]
mod mds_abi {
    #[cfg(feature = "mdsip")]
    pub use crate::mdsip::{self, tcp::TcpTransport, Answer, Client, Index, Verb};

    /// `*` in a subscript.  ★A sentinel and not a separate array, because the
    /// alternative — a parallel "is this one a star" mask — is a second array
    /// a caller can get out of step with the first.
    pub const ALL: i64 = i64::MIN;

    pub struct Session {
        pub client: Client<TcpTransport>,
        pub last: Option<Answer>,
        pub err: String,
    }

    /// `(ptr, len)` -> `&str`, or `None` when it is not UTF-8 / is null.
    ///
    /// # Safety
    /// `p` must point at `n` readable bytes.
    pub unsafe fn s<'a>(p: *const u8, n: u64) -> Option<&'a str> {
        if p.is_null() {
            return None;
        }
        std::str::from_utf8(std::slice::from_raw_parts(p, n as usize)).ok()
    }

    /// Copy `text` into `(out, cap)`; returns the length it wanted.
    ///
    /// # Safety
    /// `out` must point at `cap` writable bytes.
    pub unsafe fn put(text: &str, out: *mut u8, cap: u64) -> i64 {
        let b = text.as_bytes();
        if !out.is_null() && cap > 0 {
            let n = b.len().min(cap as usize);
            std::ptr::copy_nonoverlapping(b.as_ptr(), out, n);
        }
        b.len() as i64
    }

    pub fn verb_of(code: i32) -> Option<Verb> {
        match code {
            0 => Some(Verb::Raw),
            1 => Some(Verb::Data),
            2 => Some(Verb::DimOf),
            _ => None,
        }
    }

    pub fn indices(sub: &[i64]) -> Vec<Index> {
        sub.iter()
            .map(|&x| if x == ALL { Index::All } else { Index::At(x) })
            .collect()
    }

    pub fn open(host: &str, port: u16, user: &str, timeout_ms: i32)
                -> Result<Session, mdsip::MdsipError> {
        let t = if timeout_ms > 0 {
            Some(std::time::Duration::from_millis(timeout_ms as u64))
        } else {
            None
        };
        let io = TcpTransport::connect(host, port, t)?;
        Ok(Session { client: Client::login(io, user)?, last: None, err: String::new() })
    }
}

/// Open an mdsip session.  Writes the handle to `out_handle`.
///
/// Returns 0, `-1` on a null/!UTF-8 argument, or `-2` when the connection or
/// the login failed — in which case the reason is written to `(err, err_cap)`
/// (★a failed connection with no reason is the one error a data plane must
/// never produce; the caller has no second source for it).
///
/// # Safety
/// `host`: `host_n` bytes; `user`: `user_n`; `err`: `err_cap`; `out_handle`
/// one pointer.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn fylite_runtime_mds_open(
    host: *const u8, host_n: u64, port: u16, user: *const u8, user_n: u64,
    timeout_ms: i32, out_handle: *mut *mut std::ffi::c_void,
    err: *mut u8, err_cap: u64) -> i32 {
    let (Some(h), Some(u)) = (mds_abi::s(host, host_n), mds_abi::s(user, user_n))
    else { return -1 };
    if out_handle.is_null() {
        return -1;
    }
    match mds_abi::open(h, port, u, timeout_ms) {
        Ok(sess) => {
            *out_handle = Box::into_raw(Box::new(sess)) as *mut std::ffi::c_void;
            0
        }
        Err(e) => {
            mds_abi::put(&format!("{e:?}"), err, err_cap);
            *out_handle = std::ptr::null_mut();
            -2
        }
    }
}

/// Open `tree` at `shot`.  0 = ok, `-1` bad argument, `-2` the server refused
/// (reason available from `fylite_runtime_mds_last_error`).
///
/// # Safety
/// `handle` from `fylite_runtime_mds_open`; `tree`: `tree_n` bytes.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_mds_open_tree(
    handle: *mut std::ffi::c_void, tree: *const u8, tree_n: u64, shot: i64) -> i32 {
    if handle.is_null() {
        return -1;
    }
    let sess = &mut *(handle as *mut mds_abi::Session);
    let Some(t) = mds_abi::s(tree, tree_n) else { return -1 };
    match sess.client.open_tree(t, shot) {
        Ok(_) => { sess.err.clear(); 0 }
        Err(e) => { sess.err = format!("{e:?}"); -2 }
    }
}

/// Read one binding: `[verb](node)[sub]`.  `verb`: 0 raw, 1 `data`, 2
/// `dim_of`; `inside` puts the subscript inside the verb's parentheses;
/// `i64::MIN` in `sub` means `*`.
///
/// On success writes the element count to `n_out` and KEEPS the answer in the
/// handle for `fylite_runtime_mds_last_f64` / `_last_dims` — one round trip, two
/// calls, because the caller cannot size its buffer before the server has
/// answered.
///
/// 0 = ok, `-1` bad argument, `-2` refused/failed, `-3` unknown verb.
///
/// # Safety
/// `handle` from `fylite_runtime_mds_open`; `node`: `node_n` bytes; `sub`: `nsub`
/// i64s; `n_out` one u64.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn fylite_runtime_mds_read(
    handle: *mut std::ffi::c_void, verb: i32, node: *const u8, node_n: u64,
    sub: *const i64, nsub: u64, inside: i32, n_out: *mut u64) -> i32 {
    if handle.is_null() || n_out.is_null() {
        return -1;
    }
    let sess = &mut *(handle as *mut mds_abi::Session);
    let Some(nd) = mds_abi::s(node, node_n) else { return -1 };
    let Some(v) = mds_abi::verb_of(verb) else { return -3 };
    let idx = if nsub == 0 {
        Vec::new()
    } else if sub.is_null() {
        return -1;
    } else {
        mds_abi::indices(std::slice::from_raw_parts(sub, nsub as usize))
    };
    match sess.client.read(v, nd, &idx, inside != 0) {
        Ok(ans) => {
            *n_out = ans.data.len() as u64;
            sess.last = Some(ans);
            sess.err.clear();
            0
        }
        Err(e) => {
            sess.err = format!("{e:?}");
            sess.last = None;
            -2
        }
    }
}

/// Copy the last answer as `f64`.  0 = ok, `-1` bad argument, `-2` no answer
/// held, `-3` the answer is text (use `_last_text`), `-4` buffer too small.
///
/// # Safety
/// `handle` from `fylite_runtime_mds_open`; `out`: `cap` doubles.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_mds_last_f64(
    handle: *mut std::ffi::c_void, out: *mut f64, cap: u64) -> i32 {
    if handle.is_null() || out.is_null() {
        return -1;
    }
    let sess = &mut *(handle as *mut mds_abi::Session);
    let Some(ans) = sess.last.as_ref() else { return -2 };
    let Some(v) = ans.data.to_f64() else { return -3 };
    if (v.len() as u64) > cap {
        return -4;
    }
    std::ptr::copy_nonoverlapping(v.as_ptr(), out, v.len());
    0
}

/// The last answer's dimensions, **in wire order (fastest axis first)**.
/// Writes the rank to `n_out`.  Same status codes as `_last_f64`.
///
/// # Safety
/// `handle` from `fylite_runtime_mds_open`; `out`: `cap` u64s; `n_out` one u64.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_mds_last_dims(
    handle: *mut std::ffi::c_void, out: *mut u64, cap: u64, n_out: *mut u64) -> i32 {
    if handle.is_null() || n_out.is_null() {
        return -1;
    }
    let sess = &mut *(handle as *mut mds_abi::Session);
    let Some(ans) = sess.last.as_ref() else { return -2 };
    *n_out = ans.dims.len() as u64;
    if (ans.dims.len() as u64) > cap {
        return -4;
    }
    if !out.is_null() {
        for (i, d) in ans.dims.iter().enumerate() {
            *out.add(i) = *d as u64;
        }
    }
    0
}

/// The last error text.  Returns the length it wanted (so a caller can size a
/// buffer and ask again), or `-1` on a null handle.
///
/// # Safety
/// `handle` from `fylite_runtime_mds_open`; `out`: `cap` bytes.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_mds_last_error(
    handle: *mut std::ffi::c_void, out: *mut u8, cap: u64) -> i64 {
    if handle.is_null() {
        return -1;
    }
    let sess = &*(handle as *mut mds_abi::Session);
    mds_abi::put(&sess.err, out, cap)
}

/// Close the session and free the handle.  ★Idempotent only in the sense that
/// a null handle is accepted; passing the same non-null handle twice is a
/// double free, exactly as it is for any other `Box`.
///
/// # Safety
/// `handle` must come from `fylite_runtime_mds_open` and not have been closed.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_mds_close(handle: *mut std::ffi::c_void) {
    if !handle.is_null() {
        drop(Box::from_raw(handle as *mut mds_abi::Session));
    }
}


// =========================================================================== //
// GEQDSK —— 格式那一半的 C ABI
//
// ★取数组用**名字**（`"psirz"`），不是整数编号。编号要两侧各存一份、就会漂；
// 名字是 Python 的 `read_geqdsk` 与 JS 的 `parse` 本来就在用的同一串字符，
// 而这一层的查表代价等于零。
//
// ★两步取法（先 parse 拿句柄，再按名字取）与 mdsip 那组同一形状，理由也一样：
// 调用方在服务器/文件答复之前无法给缓冲区定长。
// =========================================================================== //

#[cfg(not(target_arch = "wasm32"))]
mod gfile_abi {
    pub use crate::geqdsk::GFile;
}

/// 解析一份 g-file 文本，写出句柄。0 = ok，`-1` 参数不合法，`-2` 解析失败
/// （原因写进 `(err, err_cap)` —— ★一份读不进来的 g-file，读者最需要知道的就是
/// 卡在哪个数组上）。
///
/// # Safety
/// `text`: `text_n` 字节；`out_handle` 一个指针；`err`: `err_cap` 字节。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_gfile_parse(
    text: *const u8, text_n: u64, out_handle: *mut *mut std::ffi::c_void,
    err: *mut u8, err_cap: u64) -> i32 {
    if out_handle.is_null() {
        return -1;
    }
    let Some(s) = mds_abi::s(text, text_n) else { return -1 };
    match crate::geqdsk::parse(s) {
        Ok(g) => {
            *out_handle = Box::into_raw(Box::new(g)) as *mut std::ffi::c_void;
            0
        }
        Err(e) => {
            mds_abi::put(&e.to_string(), err, err_cap);
            *out_handle = std::ptr::null_mut();
            -2
        }
    }
}

/// `nw` 与 `nh`。0 = ok。
///
/// # Safety
/// `handle` 来自 `fylite_runtime_gfile_parse`；`nw`/`nh` 各一个 u64。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_gfile_dims(
    handle: *mut std::ffi::c_void, nw: *mut u64, nh: *mut u64) -> i32 {
    if handle.is_null() || nw.is_null() || nh.is_null() {
        return -1;
    }
    let g = &*(handle as *mut gfile_abi::GFile);
    *nw = g.nw as u64;
    *nh = g.nh as u64;
    0
}

/// 十三个标量，按 `GFile::SCALARS` 的次序。0 = ok，`-4` 缓冲区太小。
///
/// # Safety
/// `handle` 来自 parse；`out`: `cap` 个 f64。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_gfile_scalars(
    handle: *mut std::ffi::c_void, out: *mut f64, cap: u64) -> i32 {
    if handle.is_null() || out.is_null() {
        return -1;
    }
    let g = &*(handle as *mut gfile_abi::GFile);
    let v = g.scalars();
    if (v.len() as u64) > cap {
        return -4;
    }
    std::ptr::copy_nonoverlapping(v.as_ptr(), out, v.len());
    0
}

/// 按名字取一个数组。返回它的长度（**即使 `cap` 不够也返回**，好让调用方按这个
/// 长度重来一次），`-1` 参数不合法，`-2` 没有这个名字。
///
/// # Safety
/// `handle` 来自 parse；`name`: `name_n` 字节；`out`: `cap` 个 f64。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_gfile_array(
    handle: *mut std::ffi::c_void, name: *const u8, name_n: u64,
    out: *mut f64, cap: u64) -> i64 {
    if handle.is_null() {
        return -1;
    }
    let g = &*(handle as *mut gfile_abi::GFile);
    let Some(nm) = mds_abi::s(name, name_n) else { return -1 };
    let Some(v) = g.array(nm) else { return -2 };
    if !out.is_null() && (v.len() as u64) <= cap {
        std::ptr::copy_nonoverlapping(v.as_ptr(), out, v.len());
    }
    v.len() as i64
}

/// 头一行。返回它的字节数。
///
/// # Safety
/// `handle` 来自 parse；`out`: `cap` 字节。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_gfile_header(
    handle: *mut std::ffi::c_void, out: *mut u8, cap: u64) -> i64 {
    if handle.is_null() {
        return -1;
    }
    let g = &*(handle as *mut gfile_abi::GFile);
    mds_abi::put(&g.header, out, cap)
}

/// 写回一份 g-file 文本。返回字节数。
///
/// # Safety
/// `handle` 来自 parse；`out`: `cap` 字节。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_gfile_format(
    handle: *mut std::ffi::c_void, out: *mut u8, cap: u64) -> i64 {
    if handle.is_null() {
        return -1;
    }
    let g = &*(handle as *mut gfile_abi::GFile);
    mds_abi::put(&crate::geqdsk::format_gfile(g), out, cap)
}

/// 释放句柄。
///
/// # Safety
/// `handle` 来自 parse，且未被释放过。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_gfile_free(handle: *mut std::ffi::c_void) {
    if !handle.is_null() {
        drop(Box::from_raw(handle as *mut gfile_abi::GFile));
    }
}


// =========================================================================== //
// DOCUMENTS —— 数据源 ↔ fyo 的那一面
//
// ★句柄是一束文档（`fyodoc::Bundle`）：一个文件、一炮通常不止一个 IDS。取值走
// **路径**：`"<ids>[_<occ>]/a/b/c"`——头一段是 IDS，其余是文档路径（整数段索引
// 结构数组；不带索引的名字段落到第 0 个，与内核 `fyo.rs` 那张表同一条规则）。
// 子树以 JSON 文本进出（宿主两侧都本来就会读 JSON），数值叶子另有一条 f64 快道
// （`_doc_array`）给 numpy。
//
// ★两步取法与上面的 mdsip / g-file 同一形状：先问长度，再给缓冲区。
// =========================================================================== //

#[cfg(not(target_arch = "wasm32"))]
mod doc_abi {
    use crate::document::{Array, ArrayData, MergePolicy, Node};
    use crate::fyodoc::{self, Bundle};

    pub struct Handle {
        pub bundle: Bundle,
    }

    /// `"equilibrium/time_slice/0/x"` → (文档, 余下路径)。
    pub fn locate<'a>(b: &'a Bundle, path: &str) -> Option<(&'a Node, String)> {
        let (head, rest) = path.split_once('/').unwrap_or((path, ""));
        let (ids, occ) = fyodoc::split_ids_key(head);
        let doc = b.get_occ(&ids, occ)?;
        Some((doc, rest.to_string()))
    }

    pub fn locate_mut<'a>(b: &'a mut Bundle, path: &str) -> Option<(&'a mut Node, String)> {
        let (head, rest) = path.split_once('/').unwrap_or((path, ""));
        let (ids, occ) = fyodoc::split_ids_key(head);
        if b.get_occ(&ids, occ).is_none() {
            b.push(fyodoc::new_document(&ids, &format!("fylite:{ids}/host")));
            if occ != 0 {
                b.docs.last_mut().unwrap().set(fyodoc::OCCURRENCE_KEY, Node::Int(occ)).ok();
            }
        }
        let doc = b.get_mut(&ids, occ)?;
        Some((doc, rest.to_string()))
    }

    pub fn policy_of(code: i32) -> MergePolicy {
        if code == 1 { MergePolicy::KeepExisting } else { MergePolicy::Overwrite }
    }

    pub fn array_from(data: &[f64], dims: &[u64]) -> Node {
        if dims.is_empty() {
            return Node::Float(data.first().copied().unwrap_or(f64::NAN));
        }
        let shape: Vec<usize> = dims.iter().map(|&d| d as usize).collect();
        Node::Array(Array { shape, data: ArrayData::F64(data.to_vec()) })
    }
}

/// 读一个路径（自动识别格式与布局）成一束文档。0 = ok，`-1` 参数不合法，`-2` 读失败
/// （原因写进 `(err, err_cap)`）。
///
/// # Safety
/// `path`: `path_n` 字节；`out_handle` 一个指针；`err`: `err_cap` 字节。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_read(
    path: *const u8, path_n: u64, out_handle: *mut *mut std::ffi::c_void,
    err: *mut u8, err_cap: u64) -> i32 {
    if out_handle.is_null() {
        return -1;
    }
    let Some(p) = mds_abi::s(path, path_n) else { return -1 };
    match crate::io::read(std::path::Path::new(p)) {
        Ok(bundle) => {
            *out_handle = Box::into_raw(Box::new(doc_abi::Handle { bundle })) as *mut std::ffi::c_void;
            0
        }
        Err(e) => {
            mds_abi::put(&e.to_string(), err, err_cap);
            *out_handle = std::ptr::null_mut();
            -2
        }
    }
}

/// 从文本读：`format` 是 `json` / `geqdsk` / `afile`（空 = JSON）。状态码同 `_read`。
///
/// # Safety
/// `text`: `text_n` 字节；`format`: `format_n` 字节；其余同 `_read`。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_read_text(
    text: *const u8, text_n: u64, format: *const u8, format_n: u64,
    out_handle: *mut *mut std::ffi::c_void, err: *mut u8, err_cap: u64) -> i32 {
    if out_handle.is_null() {
        return -1;
    }
    let Some(t) = mds_abi::s(text, text_n) else { return -1 };
    let f = if format_n == 0 { "json" } else { match mds_abi::s(format, format_n) { Some(f) => f, None => return -1 } };
    let result: Result<crate::fyodoc::Bundle, String> = match f {
        "json" | "jsonld" => crate::json::parse(t).map(crate::fyodoc::Bundle::from_node).map_err(|e| e.to_string()),
        "geqdsk" | "gfile" => crate::geqdsk::parse(t)
            .map(|g| crate::fyodoc::Bundle::one(crate::eqdsk_fyo::gfile_to_document(&g, "text"))).map_err(|e| e.to_string()),
        "afile" => crate::afile::parse(t)
            .map(|a| crate::fyodoc::Bundle::one(crate::afile::afile_to_document(&a, "text"))).map_err(|e| e.to_string()),
        other => Err(format!("unknown text format {other:?}")),
    };
    match result {
        Ok(bundle) => {
            *out_handle = Box::into_raw(Box::new(doc_abi::Handle { bundle })) as *mut std::ffi::c_void;
            0
        }
        Err(e) => {
            mds_abi::put(&e, err, err_cap);
            *out_handle = std::ptr::null_mut();
            -2
        }
    }
}

/// 一个空束。
///
/// # Safety
/// `out_handle` 一个指针。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_bundle_new(out_handle: *mut *mut std::ffi::c_void) -> i32 {
    if out_handle.is_null() {
        return -1;
    }
    *out_handle = Box::into_raw(Box::new(doc_abi::Handle { bundle: crate::fyodoc::Bundle::new() })) as *mut std::ffi::c_void;
    0
}

/// 写一束文档。`format` 空 = 按扩展名；`layout` 是 `fyo` / `imas`（空 = fyo）。
/// 0 = ok，`-1` 参数不合法，`-2` 写失败（原因在 `err`）。写成功时 `err` 里放报告
/// （合成的文档、丢掉的非 DD 路径），供宿主转述。
///
/// # Safety
/// `handle` 来自 `_read`/`_bundle_new`；字符串按 `(ptr, len)`；`err`: `err_cap` 字节。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn fylite_runtime_write(
    handle: *mut std::ffi::c_void, path: *const u8, path_n: u64,
    format: *const u8, format_n: u64, layout: *const u8, layout_n: u64,
    err: *mut u8, err_cap: u64) -> i32 {
    if handle.is_null() {
        return -1;
    }
    let h = &*(handle as *mut doc_abi::Handle);
    let Some(p) = mds_abi::s(path, path_n) else { return -1 };
    let fmt = if format_n == 0 { None } else {
        match mds_abi::s(format, format_n).and_then(crate::detect::Format::parse) { Some(f) => Some(f), None => return -1 }
    };
    let lay = if layout_n == 0 { crate::io::Layout::Fyo } else {
        match mds_abi::s(layout, layout_n).and_then(crate::io::Layout::parse) { Some(l) => l, None => return -1 }
    };
    match crate::io::write(std::path::Path::new(p), &h.bundle, fmt, lay) {
        Ok(rep) => {
            let mut note = String::new();
            for d in &rep.synthesized_docs {
                note.push_str(&format!("synthesized {d}; "));
            }
            for (k, r) in &rep.dd {
                let dropped: Vec<&String> = r.dropped.iter().filter(|x| !x.starts_with('@')).collect();
                if !dropped.is_empty() {
                    note.push_str(&format!("{k}: dropped {:?}; ", dropped));
                }
            }
            mds_abi::put(&note, err, err_cap);
            0
        }
        Err(e) => {
            mds_abi::put(&e.to_string(), err, err_cap);
            -2
        }
    }
}

/// 识别一个路径：写出 `"<format> <layout>"`。返回长度；`-1` 参数不合法；`-2` 认不出
/// （原因写进 `out`）。
///
/// # Safety
/// `path`: `path_n` 字节；`out`: `cap` 字节。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_detect(path: *const u8, path_n: u64, out: *mut u8, cap: u64) -> i64 {
    let Some(p) = mds_abi::s(path, path_n) else { return -1 };
    match crate::io::detect(std::path::Path::new(p)) {
        Ok(d) => mds_abi::put(&format!("{} {}", d.format.name(), d.layout.name()), out, cap),
        Err(e) => { mds_abi::put(&e.to_string(), out, cap); -2 }
    }
}

/// 整束的 JSON（fyo 布局的容器形：单份文档本身，多份为 `{ "<ids>": … }`）。
/// 返回字节数（`cap` 不够也返回，供再来一次）。
///
/// # Safety
/// `handle` 来自 `_read`；`out`: `cap` 字节。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_bundle_json(handle: *mut std::ffi::c_void, out: *mut u8, cap: u64) -> i64 {
    if handle.is_null() {
        return -1;
    }
    let h = &*(handle as *mut doc_abi::Handle);
    mds_abi::put(&crate::json::to_string(&h.bundle.to_node(), false), out, cap)
}

/// 束里有哪些文档：`"<ids>[_<occ>]"` 一行一个。返回字节数。
///
/// # Safety
/// 同 `_bundle_json`。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_bundle_keys(handle: *mut std::ffi::c_void, out: *mut u8, cap: u64) -> i64 {
    if handle.is_null() {
        return -1;
    }
    let h = &*(handle as *mut doc_abi::Handle);
    let keys: Vec<String> = h.bundle.keys().iter().map(|(i, o)| crate::fyodoc::ids_key(i, *o)).collect();
    mds_abi::put(&keys.join("\n"), out, cap)
}

/// 一条路径下的子树，JSON 文本。返回字节数；`-1` 参数不合法；`-2` 没有这条路径。
///
/// # Safety
/// `handle` 来自 `_read`；`path`: `path_n` 字节；`out`: `cap` 字节。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_doc_json(
    handle: *mut std::ffi::c_void, path: *const u8, path_n: u64, out: *mut u8, cap: u64) -> i64 {
    if handle.is_null() {
        return -1;
    }
    let h = &*(handle as *mut doc_abi::Handle);
    let Some(p) = mds_abi::s(path, path_n) else { return -1 };
    let Some((doc, rest)) = doc_abi::locate(&h.bundle, p) else { return -2 };
    let Some(node) = doc.walk(&rest, true) else { return -2 };
    mds_abi::put(&crate::json::to_string(node, false), out, cap)
}

/// 一个数值叶子按 f64 取，连同形状（行主序）。返回元素数（`cap` 不够也返回）；
/// `-1` 参数不合法；`-2` 没有这条路径；`-3` 不是数值。
///
/// # Safety
/// `handle` 来自 `_read`；`path`: `path_n` 字节；`out`: `cap` 个 f64；`dims`: `dims_cap`
/// 个 u64；`ndim_out` 一个 u64。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn fylite_runtime_doc_array(
    handle: *mut std::ffi::c_void, path: *const u8, path_n: u64,
    out: *mut f64, cap: u64, dims: *mut u64, dims_cap: u64, ndim_out: *mut u64) -> i64 {
    if handle.is_null() || ndim_out.is_null() {
        return -1;
    }
    let h = &*(handle as *mut doc_abi::Handle);
    let Some(p) = mds_abi::s(path, path_n) else { return -1 };
    let Some((doc, rest)) = doc_abi::locate(&h.bundle, p) else { return -2 };
    let Some(node) = doc.walk(&rest, true) else { return -2 };
    let Some(vals) = node.to_f64_vec() else { return -3 };
    let shape = node.shape();
    *ndim_out = shape.len() as u64;
    if !dims.is_null() && (shape.len() as u64) <= dims_cap {
        for (i, d) in shape.iter().enumerate() {
            *dims.add(i) = *d as u64;
        }
    }
    if !out.is_null() && (vals.len() as u64) <= cap {
        std::ptr::copy_nonoverlapping(vals.as_ptr(), out, vals.len());
    }
    vals.len() as i64
}

/// 把一段 JSON 放到路径上（缺的文档与中间层造出来）。0 = ok，`-1` 参数不合法，
/// `-2` JSON 不合法，`-3` 路径放不进去。
///
/// # Safety
/// `handle` 来自 `_read`；`path`: `path_n` 字节；`json`: `json_n` 字节。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_doc_set_json(
    handle: *mut std::ffi::c_void, path: *const u8, path_n: u64, json: *const u8, json_n: u64) -> i32 {
    if handle.is_null() {
        return -1;
    }
    let h = &mut *(handle as *mut doc_abi::Handle);
    let (Some(p), Some(j)) = (mds_abi::s(path, path_n), mds_abi::s(json, json_n)) else { return -1 };
    let Ok(value) = crate::json::parse(j) else { return -2 };
    let Some((doc, rest)) = doc_abi::locate_mut(&mut h.bundle, p) else { return -3 };
    if rest.is_empty() {
        //: the whole document: merge keeps the semantic keys
        doc.merge(value, crate::document::MergePolicy::Overwrite);
        return 0;
    }
    if doc.set(&rest, value).is_err() { -3 } else { 0 }
}

/// 把一个 f64 数组放到路径上（`ndim = 0` 是标量）。状态码同 `_doc_set_json`。
///
/// # Safety
/// `data`: `dims` 各维之积个 f64；`dims`: `ndim` 个 u64。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn fylite_runtime_doc_set_array(
    handle: *mut std::ffi::c_void, path: *const u8, path_n: u64,
    data: *const f64, dims: *const u64, ndim: u64) -> i32 {
    if handle.is_null() || data.is_null() {
        return -1;
    }
    let h = &mut *(handle as *mut doc_abi::Handle);
    let Some(p) = mds_abi::s(path, path_n) else { return -1 };
    let dims: Vec<u64> = if ndim == 0 || dims.is_null() { Vec::new() } else { std::slice::from_raw_parts(dims, ndim as usize).to_vec() };
    let n: usize = dims.iter().product::<u64>().max(1) as usize;
    let vals = std::slice::from_raw_parts(data, n);
    let Some((doc, rest)) = doc_abi::locate_mut(&mut h.bundle, p) else { return -3 };
    if doc.set(&rest, doc_abi::array_from(vals, &dims)).is_err() { -3 } else { 0 }
}

/// 把 `src` 合进 `dst`（`policy` 0 = 后者覆盖，1 = 只补缺）。`src` 不动。
///
/// # Safety
/// 两个句柄都来自 `_read`/`_bundle_new`。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_bundle_merge(
    dst: *mut std::ffi::c_void, src: *mut std::ffi::c_void, policy: i32) -> i32 {
    if dst.is_null() || src.is_null() {
        return -1;
    }
    let d = &mut *(dst as *mut doc_abi::Handle);
    let s = &*(src as *mut doc_abi::Handle);
    d.bundle.merge(s.bundle.clone(), doc_abi::policy_of(policy));
    0
}

/// 执行一份装配文档（`fylite:Assembly/1`，JSON 或 YAML）。`params` 是一段 JSON（可空）：
/// `{"shot": N, "time": 4.5 | [t0, t1] | [t…] | "4:5", "max_points": N, "select": [...],
/// "slots": {"time_slice": 0}}`，覆盖文档里的。`user` 是 mdsip 登录名。
/// 0 = ok（`err` 里放失败清单与 `note: …` 行，可能为空），`-1` 参数不合法，`-2` 读不到装配
/// 文档，`-3` `params` 不成话。
///
/// # Safety
/// `path`: `path_n` 字节；`params`: `params_n`；`user`: `user_n`；`out_handle` 一个指针；
/// `err`: `err_cap`。
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn fylite_runtime_assemble(
    path: *const u8, path_n: u64, params: *const u8, params_n: u64, user: *const u8, user_n: u64, timeout_ms: i32,
    out_handle: *mut *mut std::ffi::c_void, err: *mut u8, err_cap: u64) -> i32 {
    if out_handle.is_null() {
        return -1;
    }
    let Some(p) = mds_abi::s(path, path_n) else { return -1 };
    let overrides = match overrides_of(params, params_n) {
        Ok(o) => o,
        Err(e) => { mds_abi::put(&e, err, err_cap); *out_handle = std::ptr::null_mut(); return -3; }
    };
    let user = if user_n == 0 { "nobody".to_string() } else { match mds_abi::s(user, user_n) { Some(u) => u.to_string(), None => return -1 } };
    let connector = crate::assembly::tcp_connector(user, timeout_ms.max(1) as u64);
    match crate::assembly::assemble_file(std::path::Path::new(p), Some(&connector), &overrides) {
        Ok(r) => {
            mds_abi::put(&report_text(&r), err, err_cap);
            *out_handle = Box::into_raw(Box::new(doc_abi::Handle { bundle: r.bundle })) as *mut std::ffi::c_void;
            0
        }
        Err(e) => {
            mds_abi::put(&e.to_string(), err, err_cap);
            *out_handle = std::ptr::null_mut();
            -2
        }
    }
}

/// 从装置清单（fydata `machine.yaml`）取一炮的若干 IDS：几何 + MDSplus 绑定，按 `params`
/// 的 `shot` / `time` 开窗。`ids` 逗号分隔；`provider` 可空（取清单的缺省）；`host` 可空
/// （用绑定文档里的），`port <= 0` 同理。返回码同 `fylite_runtime_assemble`；`-2` 读不到清单。
///
/// # Safety
/// 各 `(ptr, n)` 对是 `n` 字节的 UTF-8；`out_handle` 一个指针；`err`: `err_cap`。
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn fylite_runtime_fetch(
    manifest: *const u8, manifest_n: u64, ids: *const u8, ids_n: u64, params: *const u8, params_n: u64,
    provider: *const u8, provider_n: u64, host: *const u8, host_n: u64, port: i32,
    user: *const u8, user_n: u64, timeout_ms: i32,
    out_handle: *mut *mut std::ffi::c_void, err: *mut u8, err_cap: u64) -> i32 {
    if out_handle.is_null() {
        return -1;
    }
    let Some(m) = mds_abi::s(manifest, manifest_n) else { return -1 };
    let Some(ids) = mds_abi::s(ids, ids_n) else { return -1 };
    let ids: Vec<&str> = ids.split(',').map(str::trim).filter(|s| !s.is_empty()).collect();
    let provider = if provider_n == 0 { None } else { mds_abi::s(provider, provider_n) };
    let host = if host_n == 0 { None } else { mds_abi::s(host, host_n) };
    let port = if port > 0 { Some(port as u16) } else { None };
    let overrides = match overrides_of(params, params_n) {
        Ok(o) => o,
        Err(e) => { mds_abi::put(&e, err, err_cap); *out_handle = std::ptr::null_mut(); return -3; }
    };
    let user = if user_n == 0 { "nobody".to_string() } else { match mds_abi::s(user, user_n) { Some(u) => u.to_string(), None => return -1 } };
    let (a, notes) = match crate::assembly::from_manifest(std::path::Path::new(m), &ids, provider, host, port, &overrides) {
        Ok(x) => x,
        Err(e) => { mds_abi::put(&e.to_string(), err, err_cap); *out_handle = std::ptr::null_mut(); return -2; }
    };
    let connector = crate::assembly::tcp_connector(user, timeout_ms.max(1) as u64);
    let mut r = crate::assembly::assemble(&a, Some(&connector));
    r.notes.splice(0..0, notes);
    mds_abi::put(&report_text(&r), err, err_cap);
    *out_handle = Box::into_raw(Box::new(doc_abi::Handle { bundle: r.bundle })) as *mut std::ffi::c_void;
    0
}

#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
unsafe fn overrides_of(params: *const u8, params_n: u64) -> Result<crate::assembly::Overrides, String> {
    if params_n == 0 {
        return Ok(crate::assembly::Overrides::default());
    }
    let text = mds_abi::s(params, params_n).ok_or("params is not UTF-8")?;
    if text.trim().is_empty() {
        return Ok(crate::assembly::Overrides::default());
    }
    let node = crate::json::parse(text).map_err(|e| e.to_string())?;
    crate::assembly::Overrides::from_node(&node)
}

#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
fn report_text(r: &crate::assembly::Assembled) -> String {
    let mut lines: Vec<String> = r.failures.clone();
    lines.extend(r.notes.iter().map(|n| format!("note: {n}")));
    lines.join("\n")
}

/// 释放一束。
///
/// # Safety
/// `handle` 来自 `_read`/`_bundle_new`/`_assemble`，且未被释放过。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_bundle_free(handle: *mut std::ffi::c_void) {
    if !handle.is_null() {
        drop(Box::from_raw(handle as *mut doc_abi::Handle));
    }
}
