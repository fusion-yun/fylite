//! 数据层的 C ABI —— Python 经 `ctypes` 取数的那一面。
//!
//! ★★符号前缀是 **`fylite_data_`**，不是内核的 `fylite_rs_`。两个 `.so` 会被同一个
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
// ★The read-only guard is NOT relaxed by any of this.  `fylite_data_mds_read`
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
pub unsafe extern "C" fn fylite_data_mds_open(
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
/// (reason available from `fylite_data_mds_last_error`).
///
/// # Safety
/// `handle` from `fylite_data_mds_open`; `tree`: `tree_n` bytes.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_data_mds_open_tree(
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
/// handle for `fylite_data_mds_last_f64` / `_last_dims` — one round trip, two
/// calls, because the caller cannot size its buffer before the server has
/// answered.
///
/// 0 = ok, `-1` bad argument, `-2` refused/failed, `-3` unknown verb.
///
/// # Safety
/// `handle` from `fylite_data_mds_open`; `node`: `node_n` bytes; `sub`: `nsub`
/// i64s; `n_out` one u64.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn fylite_data_mds_read(
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
/// `handle` from `fylite_data_mds_open`; `out`: `cap` doubles.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_data_mds_last_f64(
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
/// `handle` from `fylite_data_mds_open`; `out`: `cap` u64s; `n_out` one u64.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_data_mds_last_dims(
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
/// `handle` from `fylite_data_mds_open`; `out`: `cap` bytes.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_data_mds_last_error(
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
/// `handle` must come from `fylite_data_mds_open` and not have been closed.
#[cfg(all(feature = "mdsip", not(target_arch = "wasm32")))]
#[no_mangle]
pub unsafe extern "C" fn fylite_data_mds_close(handle: *mut std::ffi::c_void) {
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
pub unsafe extern "C" fn fylite_data_gfile_parse(
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
/// `handle` 来自 `fylite_data_gfile_parse`；`nw`/`nh` 各一个 u64。
#[cfg(not(target_arch = "wasm32"))]
#[no_mangle]
pub unsafe extern "C" fn fylite_data_gfile_dims(
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
pub unsafe extern "C" fn fylite_data_gfile_scalars(
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
pub unsafe extern "C" fn fylite_data_gfile_array(
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
pub unsafe extern "C" fn fylite_data_gfile_header(
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
pub unsafe extern "C" fn fylite_data_gfile_format(
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
pub unsafe extern "C" fn fylite_data_gfile_free(handle: *mut std::ffi::c_void) {
    if !handle.is_null() {
        drop(Box::from_raw(handle as *mut gfile_abi::GFile));
    }
}
