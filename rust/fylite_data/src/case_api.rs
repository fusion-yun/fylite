//! The JSON door — one function, a fyo plan in, a fyo record out.
//!
//! ★★This is the form the outside sees: ONE `spo:ComputationPlan`
//! (`fyo:ScenarioSpecification`) as JSON-LD text in, ONE
//! `spo:ComputationRecord` as JSON-LD text out, with the produced datasets
//! INLINE on their output ports.  Nothing touches the disk unless the plan
//! binds a file endpoint, and then the data layer reads it (`io::read`).
//! The kernel behind it is the structure door (`fylite_rs_fyo`); the JSON
//! codec is this crate's own, which is why the JSON form lives HERE and not
//! in the kernel (the kernel reads no documents — `fyo.rs`).
//!
//! ★Same conventions as `c_api.rs`: symbols `fylite_data_*`, strings as
//! `(pointer, byte length)`, no C strings; the answer is a buffer this
//! library owns and the caller releases with `fylite_data_case_free`.

use crate::case;
use std::path::Path;

/// Hand a string back as a buffer the caller frees with `fylite_data_case_free`.
fn hand_out(s: &str, out: *mut *mut u8, out_len: *mut u64) {
    let b = s.as_bytes();
    let mut v = b.to_vec().into_boxed_slice();
    let p = v.as_mut_ptr();
    let n = v.len();
    std::mem::forget(v);
    // SAFETY: the caller promised valid out pointers (see the export's contract).
    unsafe {
        *out = p;
        *out_len = n as u64;
    }
}

unsafe fn text<'a>(p: *const u8, n: u64) -> Option<&'a str> {
    if n == 0 {
        return Some("");
    }
    if p.is_null() {
        return None;
    }
    std::str::from_utf8(std::slice::from_raw_parts(p, n as usize)).ok()
}

/// A case, JSON in and JSON out.
///
/// `plan` is the JSON-LD text of one `fyo:ScenarioSpecification`, or a
/// JSON array of them composed in order (later ones override earlier
/// ones).  `base` is the directory file endpoints resolve against (empty =
/// the working directory).  `kernel` is a path to `libfylite_kernel.so`
/// (empty = `FYLITE_KERNEL_LIB` or the checkout's `python/fylite/_lib/`).
///
/// Returns **0** with the record (`run_state: succeeded`, datasets inline
/// on their output ports), **1** with the record of a REFUSAL
/// (`run_state: rejected`, the kernel's sentence in `comment`), or a
/// negative code with an error sentence instead of a record (**-1** bad
/// pointers, **-2** the plan does not parse or compose, **-3** an input
/// could not be resolved, **-4** the kernel could not be loaded).  In every
/// case `*out` / `*out_len` receive a UTF-8 buffer to release with
/// `fylite_data_case_free(pointer, length)`.
///
/// # Safety
/// `plan`: `plan_len` bytes; `base`: `base_len` bytes; `kernel`:
/// `kernel_len` bytes (a length of zero may pass null).  `out` and
/// `out_len` must be valid to write.
#[no_mangle]
pub unsafe extern "C" fn fylite_data_case_json(
    plan: *const u8, plan_len: u64,
    base: *const u8, base_len: u64,
    kernel: *const u8, kernel_len: u64,
    out: *mut *mut u8, out_len: *mut u64) -> i32 {
    if out.is_null() || out_len.is_null() {
        return -1;
    }
    *out = std::ptr::null_mut();
    *out_len = 0;
    let (Some(plan_s), Some(base_s), Some(kernel_s)) = (text(plan, plan_len), text(base, base_len), text(kernel, kernel_len))
    else {
        hand_out("fylite_data_case_json: bad pointer or length (or not UTF-8)", out, out_len);
        return -1;
    };
    let base_p = if base_s.is_empty() { None } else { Some(Path::new(base_s)) };
    let kernel_p = if kernel_s.is_empty() { None } else { Some(Path::new(kernel_s)) };
    match std::panic::catch_unwind(|| case::run_json(plan_s, base_p, kernel_p)) {
        Ok(Ok(r)) => {
            hand_out(&r.record_json, out, out_len);
            if r.refused { 1 } else { 0 }
        }
        Ok(Err(e)) => {
            hand_out(&e.message, out, out_len);
            e.code
        }
        Err(_) => {
            hand_out("fylite_data_case_json: panicked", out, out_len);
            -1
        }
    }
}

/// Release a buffer handed out by `fylite_data_case_json`.
///
/// # Safety
/// `p` / `n` must be exactly what that call handed back, released once.
#[no_mangle]
pub unsafe extern "C" fn fylite_data_case_free(p: *mut u8, n: u64) {
    if p.is_null() {
        return;
    }
    drop(Box::from_raw(std::slice::from_raw_parts_mut(p, n as usize)));
}
