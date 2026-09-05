//! 一次内核调用穿过 HTTP 的样子 —— 参数进来、结果回去，中间没有第二份物理。
//!
//! ## 为什么有这一层
//!
//! ★★2026-09-05 用户裁定：「webui 中 fylite_rs / fylite_kernel_ext wasm 功能由 api
//! 端提供，只静态网页走 wasm」。在此之前，同一批物理在一次发行里有**两个实现路径**：
//! 桌面查看器内嵌的页面实例化内核 wasm 自己算，而同一个进程里链着（那时是 dlopen）
//! 一份原生内核给命令行用。两条路、两份字节，谁也不保证它们算的是同一件事。
//!
//! 今天桌面宿主里只剩一条：页面把**同一个符号、同一批参数**交给本进程的
//! `/api/kernel`，由链进来的静态库（`libfylite_kernel_static.a`）算完送回。静态站点
//! 没有 `/api/*`，那里仍然是 wasm——那是它唯一的算法，也是唯一还需要 wasm 的宿主。
//!
//! ## 传的是什么
//!
//! **不是**一个新的计算接口，是那 250 个 C 导出的**逐参数转述**：
//!
//! ```text
//! {"fn": "fylite_rs_b_field",
//!  "args": [1.8, 0.0, 2.0, 1.0, 65, 65, {"in": [...]}, ..., {"out": 4225}]}
//!  ->  {"rc": 0, "out": [[...], [...]]}
//! ```
//!
//! 每一格是标量、入缓冲、还是出缓冲，由**生成的表**说了算
//! （`kernel_abi.rs` 与页面的 `app/assets/kernel-abi.js` 出自内核 `c_api.rs` 的同一次
//! 生成）。所以这里没有任何一处知道某个函数「是干什么的」——它只搬字节，
//! 而搬得对不对由那张表和内核自己的返回码回答。
//!
//! ## 信任边界（照实说）
//!
//! ★★出缓冲的长度是**调用方报的**，与 wasm 那条路一字不差——那边页面 `alloc` 多少
//! 就传多少。差别在后果：wasm 上报错一个长度，坏的是页面自己那块线性内存（沙箱
//! 之内）；这里坏的是**桌面进程的内存**。所以这条端点：
//!
//! * 只在回环地址上答（`fy app` 的服务器本来就只绑回环）；
//! * 每格与整帧都有上限（见 [`MAX_ELEMS`] / [`MAX_FRAME`]），超了当场拒绝；
//! * 只受理生成表里**桥得过**的符号，结构门 `fylite_rs_fyo` 按名拒绝——那扇门是
//!   `fy run` 的（计划进、记录出），不该由一个 HTTP 请求摆布二级指针。
//!
//! 这不是把风险说没了，是把它说清楚：本进程已经在同一台机器上为同一个人算这些数，
//! 而这条路没有把权限扩大到别处。

use crate::document::Node;
use crate::json;

/// 单格缓冲的元素数上限（8 MiB 的 f64）。
pub const MAX_ELEMS: usize = 1 << 20;
/// 整帧缓冲字节数上限。
pub const MAX_FRAME: usize = 64 << 20;

/// 一格参数。
#[derive(Debug, Clone)]
pub enum Slot {
    F64(f64),
    U64(u64),
    U32(u32),
    I32(i32),
    I64(i64),
    /// 指针那几格：字节就在这里，`out` 说它是要送回去的那一种。
    Buf { bytes: Vec<u8>, out: bool },
}

/// 内核返回的那一个数。
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Ret {
    I32(i32),
    U32(u32),
    U64(u64),
    F64(f64),
    Unit,
}

impl Ret {
    /// 写进答复的那个数（`Unit` 记 0——那几个函数没有返回码）。
    pub fn as_f64(self) -> f64 {
        match self {
            Ret::I32(v) => v as f64,
            Ret::U32(v) => v as f64,
            Ret::U64(v) => v as f64,
            Ret::F64(v) => v,
            Ret::Unit => 0.0,
        }
    }
}

#[derive(Debug, Clone)]
pub enum CallError {
    /// 这一版不认识这个符号（或它有意不桥）。
    NoSuchSymbol(String),
    /// 参数个数或种类与生成表不符。
    Shape(String),
    /// 请求本身读不动。
    Malformed(String),
    /// 这一次构建没有链内核。
    NoKernel,
}

impl std::fmt::Display for CallError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CallError::NoSuchSymbol(n) => {
                write!(f, "这一版不桥接 {n}（结构门与未知符号都按名拒绝）")
            }
            CallError::Shape(m) => write!(f, "参数与内核签名不符：{m}"),
            CallError::Malformed(m) => write!(f, "请求读不动：{m}"),
            CallError::NoKernel => write!(
                f,
                "这一次构建没有链内核静态库——算力不在本进程里（见 rust/build.sh --help）"
            ),
        }
    }
}

/// 一次调用的全部参数。
#[derive(Debug, Clone, Default)]
pub struct Frame {
    pub slots: Vec<Slot>,
}

impl Frame {
    /// 每一格的裸指针；标量那几格是空指针（生成的调度不会去用它们）。
    ///
    /// ★先取指针再读标量，是为了让生成的调用一行写完：指针不是借用，取完之后
    /// 读标量的不可变借用与它不冲突。各格是各自的 `Vec`，互不重叠。
    pub fn ptrs(&mut self) -> Vec<*mut u8> {
        self.slots
            .iter_mut()
            .map(|s| match s {
                Slot::Buf { bytes, .. } => bytes.as_mut_ptr(),
                _ => std::ptr::null_mut(),
            })
            .collect()
    }

    /// 参数个数与**每一格的种类**都要对上生成表说的那一行。
    ///
    /// ★★种类也查，不只查个数。少查这一半的后果是：一个本该是指针的位置收到一个
    /// 标量，于是内核拿到一个空指针——而空指针在 C ABI 里不是错误码，是段错误。
    pub fn want(&self, kinds: &[&str], name: &str) -> Result<(), CallError> {
        if self.slots.len() != kinds.len() {
            return Err(CallError::Shape(format!(
                "{name} 要 {} 个参数，收到 {} 个",
                kinds.len(),
                self.slots.len()
            )));
        }
        for (i, (k, s)) in kinds.iter().zip(self.slots.iter()).enumerate() {
            let ok = match (*k, s) {
                ("f64", Slot::F64(_)) => true,
                ("u64", Slot::U64(_)) => true,
                ("u32", Slot::U32(_)) => true,
                ("i32", Slot::I32(_)) => true,
                ("i64", Slot::I64(_)) => true,
                (k, Slot::Buf { out, .. }) if k.starts_with("in_") => !*out,
                (k, Slot::Buf { out, .. }) if k.starts_with("out_") => *out,
                _ => false,
            };
            if !ok {
                return Err(CallError::Shape(format!(
                    "{name} 第 {i} 格应是 {k}，收到 {}",
                    kind_of(s)
                )));
            }
        }
        Ok(())
    }

    pub fn f64(&self, i: usize) -> Result<f64, CallError> {
        match self.slots.get(i) {
            Some(Slot::F64(v)) => Ok(*v),
            _ => Err(CallError::Shape(format!("第 {i} 格不是 f64"))),
        }
    }
    pub fn u64(&self, i: usize) -> Result<u64, CallError> {
        match self.slots.get(i) {
            Some(Slot::U64(v)) => Ok(*v),
            _ => Err(CallError::Shape(format!("第 {i} 格不是 u64"))),
        }
    }
    pub fn u32(&self, i: usize) -> Result<u32, CallError> {
        match self.slots.get(i) {
            Some(Slot::U32(v)) => Ok(*v),
            _ => Err(CallError::Shape(format!("第 {i} 格不是 u32"))),
        }
    }
    pub fn i32(&self, i: usize) -> Result<i32, CallError> {
        match self.slots.get(i) {
            Some(Slot::I32(v)) => Ok(*v),
            _ => Err(CallError::Shape(format!("第 {i} 格不是 i32"))),
        }
    }
    pub fn i64(&self, i: usize) -> Result<i64, CallError> {
        match self.slots.get(i) {
            Some(Slot::I64(v)) => Ok(*v),
            _ => Err(CallError::Shape(format!("第 {i} 格不是 i64"))),
        }
    }
}

fn kind_of(s: &Slot) -> &'static str {
    match s {
        Slot::F64(_) => "f64",
        Slot::U64(_) => "u64",
        Slot::U32(_) => "u32",
        Slot::I32(_) => "i32",
        Slot::I64(_) => "i64",
        Slot::Buf { out: false, .. } => "入缓冲",
        Slot::Buf { out: true, .. } => "出缓冲",
    }
}

/// 一格的元素宽度（字节），由生成表的种类名决定。
fn width(kind: &str) -> Result<usize, CallError> {
    Ok(match kind {
        "in_f64" | "out_f64" | "in_u64" | "out_u64" => 8,
        "in_i32" => 4,
        "in_u8" | "out_u8" => 1,
        other => return Err(CallError::Shape(format!("未知的参数种类 {other}"))),
    })
}

/// 请求：`{"fn": 名字, "args": [...]}` -> (名字, 帧)。
///
/// ★参数怎么读，取决于生成表说这一格是什么——所以调用方给的 JSON 里
/// `3` 既可能是个 `u64`，也可能是个 `f64`，由表决定，而不是由它长什么样决定。
/// 这正是「同一次调用」的意思：页面传的就是它本来要传给 wasm 的那些数。
pub fn parse_request(body: &str, kinds_of: impl Fn(&str) -> Option<&'static [&'static str]>)
    -> Result<(String, Frame), CallError>
{
    let doc = json::parse(body).map_err(|e| CallError::Malformed(e.to_string()))?;
    let name = doc
        .get("fn")
        .and_then(Node::as_str)
        .ok_or_else(|| CallError::Malformed("没有 \"fn\"".into()))?
        .to_string();
    let kinds = kinds_of(&name).ok_or_else(|| CallError::NoSuchSymbol(name.clone()))?;
    //: ★★`args` 可能是 `List`，**也可能是 `Array`**：本仓的 JSON 读法把整齐的数值
    //: 列表折成数组节点（`json::normalize_list` —— 那是为了让 IDS 那种大块数值不必
    //: 一个节点一个数地存）。于是「全是标量的那次调用」（`dt_reactivity(ti)`）读出来
    //: 是 `Array`，`as_list()` 答 `None`，而报出来的话是「没有 args 数组」——一句
    //: 与真相相反的话。两种都收。
    let args: Vec<Node> = match doc.get("args") {
        Some(Node::List(v)) => v.clone(),
        Some(Node::Array(a)) => a
            .to_f64()
            .ok_or_else(|| CallError::Malformed("\"args\" 里有读不成数的项".into()))?
            .into_iter()
            .map(Node::Float)
            .collect(),
        _ => return Err(CallError::Malformed("没有 \"args\" 数组".into())),
    };
    if args.len() != kinds.len() {
        return Err(CallError::Shape(format!(
            "{name} 要 {} 个参数，收到 {} 个",
            kinds.len(),
            args.len()
        )));
    }
    let mut frame = Frame::default();
    let mut total = 0usize;
    for (i, (a, k)) in args.iter().zip(kinds.iter()).enumerate() {
        let slot = if k.starts_with("in_") || k.starts_with("out_") {
            let w = width(k)?;
            let (bytes, out) = if let Some(n) = a.get("out").and_then(Node::as_i64) {
                if n < 0 || n as usize > MAX_ELEMS {
                    return Err(CallError::Shape(format!("第 {i} 格出缓冲 {n} 个元素越界")));
                }
                (vec![0u8; n as usize * w], true)
            } else if let Some(v) = a.get("in").and_then(Node::to_f64_vec) {
                if v.len() > MAX_ELEMS {
                    return Err(CallError::Shape(format!("第 {i} 格入缓冲 {} 个元素越界", v.len())));
                }
                (encode(&v, k)?, false)
            } else {
                return Err(CallError::Shape(format!(
                    "第 {i} 格要 {{\"in\": [...]}} 或 {{\"out\": n}}"
                )));
            };
            total += bytes.len();
            if total > MAX_FRAME {
                return Err(CallError::Shape("整帧超过上限".into()));
            }
            Slot::Buf { bytes, out }
        } else {
            let v = a
                .as_f64()
                .ok_or_else(|| CallError::Shape(format!("第 {i} 格不是数")))?;
            match *k {
                "f64" => Slot::F64(v),
                "u64" => Slot::U64(nonneg(v, i)? as u64),
                "u32" => Slot::U32(nonneg(v, i)? as u32),
                "i32" => Slot::I32(v as i32),
                "i64" => Slot::I64(v as i64),
                other => return Err(CallError::Shape(format!("未知的参数种类 {other}"))),
            }
        };
        frame.slots.push(slot);
    }
    Ok((name, frame))
}

fn nonneg(v: f64, i: usize) -> Result<f64, CallError> {
    if v < 0.0 || !v.is_finite() {
        return Err(CallError::Shape(format!("第 {i} 格要非负整数，收到 {v}")));
    }
    Ok(v)
}

fn encode(v: &[f64], kind: &str) -> Result<Vec<u8>, CallError> {
    let mut out = Vec::with_capacity(v.len() * width(kind)?);
    for x in v {
        match kind {
            "in_f64" => out.extend_from_slice(&x.to_ne_bytes()),
            "in_u64" => out.extend_from_slice(&(*x as u64).to_ne_bytes()),
            "in_i32" => out.extend_from_slice(&(*x as i32).to_ne_bytes()),
            "in_u8" => out.push(*x as u8),
            other => return Err(CallError::Shape(format!("未知的入参种类 {other}"))),
        }
    }
    Ok(out)
}

fn decode(bytes: &[u8], kind: &str) -> Vec<f64> {
    match kind {
        "out_f64" => bytes
            .chunks_exact(8)
            .map(|c| f64::from_ne_bytes(c.try_into().unwrap()))
            .collect(),
        "out_u64" => bytes
            .chunks_exact(8)
            .map(|c| u64::from_ne_bytes(c.try_into().unwrap()) as f64)
            .collect(),
        _ => bytes.iter().map(|b| *b as f64).collect(),
    }
}

/// 答复：`{"rc": 返回码, "out": [[...], ...]}`，出缓冲按参数序。
pub fn render_answer(ret: Ret, frame: &Frame, kinds: &[&str]) -> String {
    let mut s = String::from("{\"rc\":");
    s.push_str(&json::fmt_f64(ret.as_f64()));
    s.push_str(",\"out\":[");
    let mut first = true;
    for (slot, k) in frame.slots.iter().zip(kinds.iter()) {
        let Slot::Buf { bytes, out: true } = slot else { continue };
        if !first {
            s.push(',');
        }
        first = false;
        s.push('[');
        let vals = decode(bytes, k);
        for (i, v) in vals.iter().enumerate() {
            if i > 0 {
                s.push(',');
            }
            s.push_str(&json::fmt_f64(*v));
        }
        s.push(']');
    }
    s.push_str("]}");
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    const KINDS: &[&str] = &["f64", "u64", "in_f64", "out_f64"];

    fn kinds_of(n: &str) -> Option<&'static [&'static str]> {
        if n == "demo" {
            Some(KINDS)
        } else {
            None
        }
    }

    #[test]
    fn a_request_reads_each_slot_the_way_the_table_says() {
        let (name, f) = parse_request(
            r#"{"fn":"demo","args":[1.5, 3, {"in":[1,2,3]}, {"out":2}]}"#,
            kinds_of,
        )
        .expect("parses");
        assert_eq!(name, "demo");
        assert_eq!(f.f64(0).unwrap(), 1.5);
        assert_eq!(f.u64(1).unwrap(), 3);
        assert!(f.want(KINDS, "demo").is_ok());
        match &f.slots[2] {
            Slot::Buf { bytes, out } => {
                assert!(!out);
                assert_eq!(bytes.len(), 24);
            }
            _ => panic!("第 2 格该是入缓冲"),
        }
    }

    #[test]
    fn a_scalar_where_a_pointer_belongs_is_refused_rather_than_passed_as_null() {
        //: ★这条是本模块存在的理由之一：空指针在 C ABI 里不是错误码，是段错误。
        let e = parse_request(r#"{"fn":"demo","args":[1.5, 3, 7, {"out":2}]}"#, kinds_of)
            .expect_err("must refuse");
        assert!(matches!(e, CallError::Shape(_)), "{e}");
    }

    #[test]
    fn an_unbridged_name_is_refused_by_name() {
        let e = parse_request(r#"{"fn":"fylite_rs_fyo","args":[]}"#, kinds_of)
            .expect_err("must refuse");
        assert!(matches!(e, CallError::NoSuchSymbol(_)), "{e}");
    }

    #[test]
    fn an_out_buffer_beyond_the_cap_is_refused() {
        let big = format!(r#"{{"fn":"demo","args":[1,2,{{"in":[]}},{{"out":{}}}]}}"#,
                          MAX_ELEMS + 1);
        assert!(parse_request(&big, kinds_of).is_err());
    }

    //: ★★这一条是**链接期的判据**，不是逻辑判据：它证明那份静态库真的进了这个
    //: 二进制，而且按名调得动。没有它，「链上了」只能靠体积变大来推断——而体积
    //: 变大的原因可以有很多个。
    #[cfg(kernel_static)]
    #[test]
    fn the_linked_kernel_answers_through_the_generated_dispatch() {
        use crate::kernel_abi;
        let mut f = Frame::default();
        let ret = kernel_abi::call("fylite_rs_abi_version", &mut f).expect("dispatch");
        let abi = ret.as_f64();
        assert!(abi > 0.0, "内核报的 ABI 号是 {abi}");
        //: 扩展也在同一份归档里（TGLF + DKE），两个 ABI 号必须同源。
        let mut g = Frame::default();
        let ext = kernel_abi::call("fylite_ext_abi_version", &mut g).expect("dispatch");
        assert_eq!(ext.as_f64(), abi, "核心与扩展不是同一次构建");
    }

    #[cfg(kernel_static)]
    #[test]
    fn a_real_kernel_call_carries_its_arrays_both_ways() {
        use crate::kernel_abi;
        //: `fylite_rs_ellipke(m[], n, k_out[], e_out[])` —— 完全椭圆积分 K 与 E。
        //: 取 m = 0：K(0) = E(0) = π/2，这是闭式的，不必去查表，也不必信任何一份
        //: 参考数据——判据自带出处。
        let (name, mut f) = parse_request(
            r#"{"fn":"fylite_rs_ellipke","args":[{"in":[0.0]},1,{"out":1},{"out":1}]}"#,
            |n| kernel_abi::KINDS.iter().find(|(k, _)| *k == n).map(|(_, v)| *v),
        )
        .expect("parses");
        let rc = kernel_abi::call(&name, &mut f).expect("dispatch").as_f64();
        assert_eq!(rc, 0.0, "内核返回码 {rc}");
        let kinds = kernel_abi::KINDS.iter().find(|(k, _)| *k == name).unwrap().1;
        let answer = render_answer(Ret::I32(0), &f, kinds);
        let half_pi = std::f64::consts::FRAC_PI_2;
        let want = format!("{{\"rc\":{},\"out\":[[{}],[{}]]}}",
                           json::fmt_f64(0.0), json::fmt_f64(half_pi), json::fmt_f64(half_pi));
        assert_eq!(answer, want);
    }

    #[test]
    fn the_answer_carries_the_out_slots_in_argument_order() {
        let (_, mut f) = parse_request(
            r#"{"fn":"demo","args":[1.5, 3, {"in":[1,2,3]}, {"out":2}]}"#,
            kinds_of,
        )
        .unwrap();
        if let Slot::Buf { bytes, .. } = &mut f.slots[3] {
            bytes[..8].copy_from_slice(&2.5f64.to_ne_bytes());
            bytes[8..].copy_from_slice(&(-1.0f64).to_ne_bytes());
        }
        let s = render_answer(Ret::I32(0), &f, KINDS);
        //: 数的写法由 `json::fmt_f64` 定（`0` 写成 `0.0`）——这里不另立一种。
        assert_eq!(s, "{\"rc\":0.0,\"out\":[[2.5,-1.0]]}");
    }
}
