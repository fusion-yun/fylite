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
//! ★Same conventions as `c_api.rs`: symbols `fylite_runtime_*`, strings as
//! `(pointer, byte length)`, no C strings; the answer is a buffer this
//! library owns and the caller releases with `fylite_runtime_case_free`.

use crate::case;
use std::path::Path;

/// Hand a string back as a buffer the caller frees with `fylite_runtime_case_free`.
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
/// `fylite_runtime_case_free(pointer, length)`.
///
/// # Safety
/// `plan`: `plan_len` bytes; `base`: `base_len` bytes; `kernel`:
/// `kernel_len` bytes (a length of zero may pass null).  `out` and
/// `out_len` must be valid to write.
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_case_json(
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
        hand_out("fylite_runtime_case_json: bad pointer or length (or not UTF-8)", out, out_len);
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
            hand_out("fylite_runtime_case_json: panicked", out, out_len);
            -1
        }
    }
}

/// Release a buffer handed out by `fylite_runtime_case_json`.
///
/// # Safety
/// `p` / `n` must be exactly what that call handed back, released once.
/// A case through the TREE door — `code` + a plan as JSON in, the record as JSON out.
///
/// ★★2026-09-05（T-1 中间层一半）。与 `fylite_runtime_case_json` 的分工：那一扇收的是
/// 一份 `fyo:ScenarioSpecification`（计划文档，带端点、来源与记录的账），走**旧形**内核门；
/// 这一扇收的是内核 `case::run_doc` 的**计划树本身**（`settings/*` · `inputs/*`），走
/// **树形**门（`fylite_rs_fyo_tree`），交回的是记录树。JSON 只在**宿主与中间层**之间——
/// 文本到 `Node` 是本 crate 的 `json.rs`，`Node` 到四段是 `tree.rs`；内核两头都是树。
///
/// Returns **0** with the record, **1** with the kernel's REFUSAL tree
/// (`refusal/{code, message}`), or a negative code with a sentence instead of a
/// record: **-1** bad pointers, **-2** the plan does not parse, **-4** the kernel
/// could not be loaded, **-5** the loaded kernel has no tree door (ABI < 126),
/// **-6** the kernel handed back a malformed tree.  `*out` / `*out_len` always
/// receive a UTF-8 buffer to release with `fylite_runtime_case_free`.
///
/// # Safety
/// `code`: `code_len` bytes; `plan`: `plan_len` bytes; `kernel`: `kernel_len`
/// bytes (zero may pass null).  `out` and `out_len` must be valid to write.
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_case_tree_json(
    code: *const u8, code_len: u64,
    plan: *const u8, plan_len: u64,
    kernel: *const u8, kernel_len: u64,
    out: *mut *mut u8, out_len: *mut u64) -> i32 {
    use crate::document::Node;
    if out.is_null() || out_len.is_null() {
        return -1;
    }
    *out = std::ptr::null_mut();
    *out_len = 0;
    let (Some(code_s), Some(plan_s), Some(kernel_s)) = (text(code, code_len), text(plan, plan_len), text(kernel, kernel_len))
    else { hand_out("bad pointer or non-UTF-8 text", out, out_len); return -1; };
    let node = match crate::json::parse(plan_s) {
        Ok(n) => n,
        Err(e) => { hand_out(&format!("the plan does not parse: {e:?}"), out, out_len); return -2; }
    };
    let kpath = if kernel_s.is_empty() { None } else { Some(Path::new(kernel_s)) };
    let k = match crate::kernel::Kernel::load(kpath) {
        Ok(k) => k,
        Err(e) => { hand_out(&e.message, out, out_len); return -4; }
    };
    match k.run_tree(code_s, &node) {
        Ok(rec) => { hand_out(&crate::json::to_string(&rec, true), out, out_len); 0 }
        Err(e) if e.code == -5 || e.code == -6 => { hand_out(&e.message, out, out_len); e.code as i32 }
        Err(e) => {
            //: the refusal as a tree, so the caller reads `refusal/code` and
            //: `refusal/message` the same way it reads a record
            let mut r = crate::document::Map::new();
            r.insert("code", Node::Int(e.code));
            r.insert("message", Node::Str(e.message));
            let mut root = crate::document::Map::new();
            root.insert("refusal", Node::Map(r));
            hand_out(&crate::json::to_string(&Node::Map(root), true), out, out_len);
            1
        }
    }
}

/// The fingerprint of the kernel LINKED INTO this library, as the JSON the kernel's
/// build wrote beside its archive (`kernel-static.json`: version · abi · built · sha256).
///
/// Returns **0** with the JSON text, or **1** with an empty buffer when this library
/// links no kernel (or the archive came without its json).  Release the buffer with
/// `fylite_runtime_case_free`.  ★This is what lets a caller tell「the kernel inside the
/// runtime」from「the kernel installed beside it」when both carry the same version, ABI
/// and interface digest — see `kernel::Kernel::linked_fingerprint`.
///
/// # Safety
/// `out` and `out_len` must be valid to write.
#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_linked_kernel(out: *mut *mut u8, out_len: *mut u64) -> i32 {
    if out.is_null() || out_len.is_null() {
        return -1;
    }
    *out = std::ptr::null_mut();
    *out_len = 0;
    match crate::kernel::Kernel::linked_fingerprint() {
        Some(j) => { hand_out(j, out, out_len); 0 }
        None => 1,
    }
}

/// The document door as ONE HTTP answer: `{"code": …, "plan": {…}}` in, `(status, JSON)` out.
///
/// ★Lives in the library, not in the `fy` binary, so it is tested where the tests run
/// (the binary embeds the whole app and cannot even be compiled on a host without the
/// wasm artefacts).  `fy`'s `POST /api/case` is three lines around this.
///
/// Answers: **200** `{"record": …}`; **200** `{"refusal": {"code", "message"}}` when
/// the kernel refused (a refusal is an answer, not a transport failure); **400** when
/// the body does not parse or names no `code`; **501** when no kernel is reachable
/// from this process (or it predates the tree door).
pub fn case_http(body: &str) -> (u16, String) {
    use crate::document::Node;
    use crate::json;
    use crate::kernel::Kernel;
    let jstr = |s: &str| json::to_string(&Node::Str(s.to_string()), false);
    let doc = match json::parse(body) {
        Ok(d) => d,
        Err(e) => return (400, format!("{{\"error\":{}}}", jstr(&format!("the request does not parse: {e:?}")))),
    };
    let Some(code) = doc.get("code").and_then(Node::as_str).map(str::to_string) else {
        return (400, "{\"error\":\"the request names no `code`\"}".to_string());
    };
    let plan = doc.get("plan").cloned().unwrap_or_else(Node::map);
    let k = match Kernel::load(None) {
        Ok(k) => k,
        Err(e) => return (501, format!("{{\"error\":{}}}", jstr(&e.message))),
    };
    match k.run_tree(&code, &plan) {
        Ok(rec) => (200, format!("{{\"record\":{}}}", json::to_string(&rec, false))),
        Err(e) if e.code == -5 || e.code == -6 => (501, format!("{{\"error\":{}}}", jstr(&e.message))),
        Err(e) => (200, format!("{{\"refusal\":{{\"code\":{},\"message\":{}}}}}", e.code, jstr(&e.message))),
    }
}

#[cfg(test)]
mod http_door_tests {
    use super::case_http;

    #[test]
    fn the_http_door_completes_transport_and_refuses_as_an_answer() {
        let plan = r#"{"code":"code/transport","plan":{"settings":{"power":12.0,"width":0.36,"pinch":0.0,"edge":3.0,"dpc":0.0,"n":41.0,"amin":2.0,"rmaj":3.1,"kappa":1.86,"delta":0.48,"q95":3.0,"chi0":0.4,"closure":"0"}}}"#;
        let (status, body) = case_http(plan);
        if status == 501 {
            eprintln!("skipping: {body}");
            return;
        }
        assert_eq!(status, 200, "{body}");
        assert!(body.starts_with("{\"record\":"), "{body}");
        assert!(body.contains("\"entry\":\"transport\""), "{body}");
        let (status, body) = case_http(r#"{"code":"code/nowhere","plan":{}}"#);
        assert_eq!(status, 200);
        assert!(body.starts_with("{\"refusal\":{\"code\":-30"), "{body}");
        assert_eq!(case_http("not json").0, 400);
        assert_eq!(case_http(r#"{"plan":{}}"#).0, 400);
    }
}

#[no_mangle]
pub unsafe extern "C" fn fylite_runtime_case_free(p: *mut u8, n: u64) {
    if p.is_null() {
        return;
    }
    drop(Box::from_raw(std::ptr::slice_from_raw_parts_mut(p, n as usize)));
}
