//! JSON / JSON-LD 编解码 —— 零依赖。
//!
//! ★★**为什么自己写而不拉 `serde_json`。** 这一层要在 wasm 上也成立（浏览器读
//! g-file 与 fyo 文档，见 `lib.rs`），而它的整个依赖表到今天为止是空的；一个 JSON
//! 读写各三百行，换不来一整棵依赖树。JSON-LD 在这里**就是 JSON**：`@context`、
//! `@id`、`@type` 是普通的键，语义在读它的人那里（`fylite.engine.manifest`
//! 的 `SEMANTIC_KEYS`），不在语法上。
//!
//! ## 数值列表 → 数组
//!
//! 一个全是数的（嵌套）列表读成 [`Array`]（行主序、带形状），前提是它**矩形**
//! ——各层长度一致。参差的列表留作 [`Node::List`]，因为它没有形状。整数与浮点：
//! 全是整数字面量给 `I64`，否则 `F64`。写回去时数组展开成嵌套列表，与
//! `fylite.fyo.write` 的 `_jsonable` 同一形状。
//!
//! ## `NaN` / `Infinity`
//!
//! JSON 没有它们；Python 的 `json.dumps` 缺省却写 `NaN`、`Infinity`，而本仓
//! 已经在盘上的文档正是那样写出来的。所以读认它们，写也照 Python 的写法——
//! 一份文档来回一趟不该丢掉一个「没有值」。

use crate::document::{Array, ArrayData, Map, Node};
use std::fmt::Write as _;

#[derive(Debug, Clone, PartialEq)]
pub struct JsonError {
    pub offset: usize,
    pub message: String,
}

impl std::fmt::Display for JsonError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "JSON error at byte {}: {}", self.offset, self.message)
    }
}

impl std::error::Error for JsonError {}

struct Parser<'a> {
    b: &'a [u8],
    i: usize,
}

impl<'a> Parser<'a> {
    fn err<T>(&self, m: impl Into<String>) -> Result<T, JsonError> {
        Err(JsonError { offset: self.i, message: m.into() })
    }

    fn ws(&mut self) {
        while self.i < self.b.len() && matches!(self.b[self.i], b' ' | b'\t' | b'\n' | b'\r') {
            self.i += 1;
        }
    }

    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }

    fn expect(&mut self, c: u8) -> Result<(), JsonError> {
        if self.peek() == Some(c) {
            self.i += 1;
            Ok(())
        } else {
            self.err(format!("expected {:?}", c as char))
        }
    }

    fn starts_with(&self, s: &str) -> bool {
        self.b[self.i..].starts_with(s.as_bytes())
    }

    fn value(&mut self) -> Result<Node, JsonError> {
        self.ws();
        match self.peek() {
            None => self.err("unexpected end of input"),
            Some(b'{') => self.object(),
            Some(b'[') => self.list(),
            Some(b'"') => Ok(Node::Str(self.string()?)),
            Some(b't') if self.starts_with("true") => { self.i += 4; Ok(Node::Bool(true)) }
            Some(b'f') if self.starts_with("false") => { self.i += 5; Ok(Node::Bool(false)) }
            Some(b'n') if self.starts_with("null") => { self.i += 4; Ok(Node::Null) }
            Some(b'N') if self.starts_with("NaN") => { self.i += 3; Ok(Node::Float(f64::NAN)) }
            Some(b'I') if self.starts_with("Infinity") => { self.i += 8; Ok(Node::Float(f64::INFINITY)) }
            Some(b'-') if self.starts_with("-Infinity") => { self.i += 9; Ok(Node::Float(f64::NEG_INFINITY)) }
            Some(c) if c == b'-' || c.is_ascii_digit() => self.number(),
            Some(c) => self.err(format!("unexpected character {:?}", c as char)),
        }
    }

    fn object(&mut self) -> Result<Node, JsonError> {
        self.expect(b'{')?;
        let mut m = Map::new();
        self.ws();
        if self.peek() == Some(b'}') {
            self.i += 1;
            return Ok(Node::Map(m));
        }
        loop {
            self.ws();
            if self.peek() != Some(b'"') {
                return self.err("expected a string key");
            }
            let k = self.string()?;
            self.ws();
            self.expect(b':')?;
            let v = self.value()?;
            m.insert(k, v);
            self.ws();
            match self.peek() {
                Some(b',') => { self.i += 1; }
                Some(b'}') => { self.i += 1; return Ok(Node::Map(m)); }
                _ => return self.err("expected ',' or '}'"),
            }
        }
    }

    fn list(&mut self) -> Result<Node, JsonError> {
        self.expect(b'[')?;
        let mut items = Vec::new();
        self.ws();
        if self.peek() == Some(b']') {
            self.i += 1;
            return Ok(normalize_list(items));
        }
        loop {
            let v = self.value()?;
            items.push(v);
            self.ws();
            match self.peek() {
                Some(b',') => { self.i += 1; }
                Some(b']') => { self.i += 1; return Ok(normalize_list(items)); }
                _ => return self.err("expected ',' or ']'"),
            }
        }
    }

    fn number(&mut self) -> Result<Node, JsonError> {
        let start = self.i;
        if self.peek() == Some(b'-') {
            self.i += 1;
        }
        let mut is_float = false;
        while let Some(c) = self.peek() {
            match c {
                b'0'..=b'9' => self.i += 1,
                b'.' | b'e' | b'E' | b'+' | b'-' => { is_float = true; self.i += 1; }
                _ => break,
            }
        }
        let tok = std::str::from_utf8(&self.b[start..self.i]).unwrap();
        if !is_float {
            if let Ok(v) = tok.parse::<i64>() {
                return Ok(Node::Int(v));
            }
        }
        match tok.parse::<f64>() {
            Ok(v) => Ok(Node::Float(v)),
            Err(_) => { self.i = start; self.err(format!("bad number {tok:?}")) }
        }
    }

    fn string(&mut self) -> Result<String, JsonError> {
        self.expect(b'"')?;
        let mut out = String::new();
        loop {
            let c = match self.peek() {
                None => return self.err("unterminated string"),
                Some(c) => c,
            };
            self.i += 1;
            match c {
                b'"' => return Ok(out),
                b'\\' => {
                    let e = match self.peek() {
                        None => return self.err("unterminated escape"),
                        Some(e) => e,
                    };
                    self.i += 1;
                    match e {
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'/' => out.push('/'),
                        b'b' => out.push('\u{8}'),
                        b'f' => out.push('\u{c}'),
                        b'n' => out.push('\n'),
                        b'r' => out.push('\r'),
                        b't' => out.push('\t'),
                        b'u' => {
                            let mut cp = self.hex4()?;
                            if (0xD800..0xDC00).contains(&cp) {
                                //: surrogate pair
                                if self.starts_with("\\u") {
                                    self.i += 2;
                                    let lo = self.hex4()?;
                                    cp = 0x10000 + ((cp - 0xD800) << 10) + (lo.wrapping_sub(0xDC00) & 0x3FF);
                                }
                            }
                            out.push(char::from_u32(cp).unwrap_or('\u{FFFD}'));
                        }
                        _ => return self.err("bad escape"),
                    }
                }
                _ => {
                    //: copy a run of plain bytes (UTF-8 passes through)
                    let start = self.i - 1;
                    while self.i < self.b.len() && self.b[self.i] != b'"' && self.b[self.i] != b'\\' {
                        self.i += 1;
                    }
                    match std::str::from_utf8(&self.b[start..self.i]) {
                        Ok(s) => out.push_str(s),
                        Err(_) => return self.err("invalid UTF-8 in string"),
                    }
                }
            }
        }
    }

    fn hex4(&mut self) -> Result<u32, JsonError> {
        if self.i + 4 > self.b.len() {
            return self.err("short \\u escape");
        }
        let s = std::str::from_utf8(&self.b[self.i..self.i + 4]).map_err(|_| JsonError {
            offset: self.i, message: "bad \\u escape".into() })?;
        let v = u32::from_str_radix(s, 16).map_err(|_| JsonError {
            offset: self.i, message: "bad \\u escape".into() })?;
        self.i += 4;
        Ok(v)
    }
}

/// 把一个列表归一成数组（矩形数值/字符串列表）或留作列表。
pub fn normalize_list(items: Vec<Node>) -> Node {
    if items.is_empty() {
        return Node::List(items);
    }
    //: 全是标量数？
    if items.iter().all(|n| matches!(n, Node::Int(_) | Node::Float(_))) {
        if items.iter().all(|n| matches!(n, Node::Int(_))) {
            let v: Vec<i64> = items.iter().map(|n| n.as_i64().unwrap()).collect();
            return Node::Array(Array { shape: vec![v.len()], data: ArrayData::I64(v) });
        }
        let v: Vec<f64> = items.iter().map(|n| n.as_f64().unwrap()).collect();
        return Node::Array(Array { shape: vec![v.len()], data: ArrayData::F64(v) });
    }
    //: 全是字符串？（一维字符串数组：名字表、标签）
    if items.iter().all(|n| matches!(n, Node::Str(_))) {
        let v: Vec<String> = items.iter().map(|n| n.as_str().unwrap().to_string()).collect();
        return Node::Array(Array { shape: vec![v.len()], data: ArrayData::Str(v) });
    }
    //: 全是同形状的数值数组 → 叠成高一维
    if items.iter().all(|n| matches!(n, Node::Array(a) if a.is_numeric())) {
        let first = items[0].as_array().unwrap().shape.clone();
        if items.iter().all(|n| n.as_array().unwrap().shape == first) {
            let all_int = items.iter().all(|n| matches!(&n.as_array().unwrap().data, ArrayData::I64(_)));
            let mut shape = vec![items.len()];
            shape.extend(first);
            if all_int {
                let mut v = Vec::new();
                for n in &items {
                    v.extend_from_slice(n.as_array().unwrap().as_i64().unwrap());
                }
                return Node::Array(Array { shape, data: ArrayData::I64(v) });
            }
            let mut v = Vec::new();
            for n in &items {
                v.extend(n.as_array().unwrap().to_f64().unwrap());
            }
            return Node::Array(Array { shape, data: ArrayData::F64(v) });
        }
    }
    Node::List(items)
}

/// 解析 JSON 文本。
pub fn parse(text: &str) -> Result<Node, JsonError> {
    let mut p = Parser { b: text.as_bytes(), i: 0 };
    let v = p.value()?;
    p.ws();
    if p.i != p.b.len() {
        return p.err("trailing characters");
    }
    Ok(v)
}

// --------------------------------------------------------------------------
// writer
// --------------------------------------------------------------------------

fn write_str(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => { let _ = write!(out, "\\u{:04x}", c as u32); }
            c => out.push(c),
        }
    }
    out.push('"');
}

/// 一个 f64 的 JSON 写法：整数值也带 `.0`，好让读回来仍是浮点；`NaN`/`Infinity`
/// 照 Python。
pub fn fmt_f64(v: f64) -> String {
    if v.is_nan() {
        return "NaN".into();
    }
    if v.is_infinite() {
        return if v > 0.0 { "Infinity".into() } else { "-Infinity".into() };
    }
    let s = format!("{v}");
    //: `{}` 对 1e300 会写 300 个 0；Python 写 `1e+300`。量级很大或很小时用科学计数。
    if (v.abs() >= 1e16 || (v.abs() < 1e-5 && v != 0.0)) && !s.contains('e') {
        let e = format!("{v:e}");
        return if e.contains('.') { e } else { e.replacen('e', ".0e", 1) };
    }
    if s.contains('.') || s.contains('e') { s } else { format!("{s}.0") }
}

fn write_array_slice(out: &mut String, a: &Array, dim: usize, offset: usize, indent: usize, pretty: bool) {
    let d = a.shape[dim];
    if dim + 1 == a.shape.len() {
        out.push('[');
        for k in 0..d {
            if k > 0 {
                out.push_str(if pretty { ", " } else { "," });
            }
            match &a.data {
                ArrayData::F64(v) => out.push_str(&fmt_f64(v[offset + k])),
                ArrayData::I64(v) => { let _ = write!(out, "{}", v[offset + k]); }
                ArrayData::Str(v) => write_str(out, &v[offset + k]),
            }
        }
        out.push(']');
        return;
    }
    let stride: usize = a.shape[dim + 1..].iter().product();
    out.push('[');
    for k in 0..d {
        if k > 0 {
            out.push(',');
        }
        if pretty {
            out.push('\n');
            out.push_str(&" ".repeat(indent + 1));
        }
        write_array_slice(out, a, dim + 1, offset + k * stride, indent + 1, pretty);
    }
    if pretty && d > 0 {
        out.push('\n');
        out.push_str(&" ".repeat(indent));
    }
    out.push(']');
}

fn write_node(out: &mut String, n: &Node, indent: usize, pretty: bool) {
    match n {
        Node::Null => out.push_str("null"),
        Node::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Node::Int(v) => { let _ = write!(out, "{v}"); }
        Node::Float(v) => out.push_str(&fmt_f64(*v)),
        Node::Str(s) => write_str(out, s),
        Node::Array(a) => {
            if a.shape.is_empty() {
                //: 零维数组 → 标量
                match &a.data {
                    ArrayData::F64(v) => out.push_str(&fmt_f64(v[0])),
                    ArrayData::I64(v) => { let _ = write!(out, "{}", v[0]); }
                    ArrayData::Str(v) => write_str(out, &v[0]),
                }
            } else {
                write_array_slice(out, a, 0, 0, indent, pretty);
            }
        }
        Node::List(l) => {
            if l.is_empty() {
                out.push_str("[]");
                return;
            }
            out.push('[');
            for (k, v) in l.iter().enumerate() {
                if k > 0 {
                    out.push(',');
                }
                if pretty {
                    out.push('\n');
                    out.push_str(&" ".repeat(indent + 1));
                }
                write_node(out, v, indent + 1, pretty);
            }
            if pretty {
                out.push('\n');
                out.push_str(&" ".repeat(indent));
            }
            out.push(']');
        }
        Node::Map(m) => {
            if m.is_empty() {
                out.push_str("{}");
                return;
            }
            out.push('{');
            for (k, (key, v)) in m.iter().enumerate() {
                if k > 0 {
                    out.push(',');
                }
                if pretty {
                    out.push('\n');
                    out.push_str(&" ".repeat(indent + 1));
                }
                write_str(out, key);
                out.push_str(if pretty { ": " } else { ":" });
                write_node(out, v, indent + 1, pretty);
            }
            if pretty {
                out.push('\n');
                out.push_str(&" ".repeat(indent));
            }
            out.push('}');
        }
    }
}

/// 写成 JSON 文本；`pretty` 用一格缩进（与 `json.dumps(indent=1)` 同形）。
pub fn to_string(n: &Node, pretty: bool) -> String {
    let mut out = String::new();
    write_node(&mut out, n, 0, pretty);
    if pretty {
        out.push('\n');
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_numeric_nested_list_becomes_a_shaped_array() {
        let d = parse(r#"{"psi": [[1, 2, 3], [4, 5, 6]], "t": [0.5, 1.5], "n": [1, 2]}"#).unwrap();
        let psi = d.get("psi").unwrap().as_array().unwrap();
        assert_eq!(psi.shape, vec![2, 3]);
        assert_eq!(psi.as_i64().unwrap(), &[1, 2, 3, 4, 5, 6]);
        assert!(matches!(d.get("t").unwrap().as_array().unwrap().data, ArrayData::F64(_)));
        assert!(matches!(d.get("n").unwrap().as_array().unwrap().data, ArrayData::I64(_)));
    }

    #[test]
    fn a_ragged_list_stays_a_list_and_an_aos_stays_a_list() {
        let d = parse(r#"{"r": [[1, 2], [3]], "ts": [{"a": 1}, {"a": 2}]}"#).unwrap();
        assert!(matches!(d.get("r"), Some(Node::List(_))));
        assert_eq!(d.get("ts/1/a").and_then(Node::as_i64), Some(2));
    }

    #[test]
    fn round_trip_keeps_key_order_special_floats_and_unicode() {
        let text = "{\n \"@context\": {\"fyo\": \"https://x/\"},\n \"@type\": \"fyo:equilibrium\",\n \"v\": [1.5, NaN, Infinity],\n \"s\": \"\\u00e9\\n\\\"q\\\"\"\n}\n";
        let d = parse(text).unwrap();
        let keys: Vec<&str> = d.as_map().unwrap().keys().collect();
        assert_eq!(keys, vec!["@context", "@type", "v", "s"]);
        let v = d.get("v").unwrap().as_array().unwrap().as_f64().unwrap().to_vec();
        assert!(v[1].is_nan() && v[2].is_infinite());
        assert_eq!(d.get("s").unwrap().as_str(), Some("é\n\"q\""));
        let again = parse(&to_string(&d, true)).unwrap();
        assert_eq!(again.get("s"), d.get("s"));
        assert_eq!(again.get("@type"), d.get("@type"));
        let v2 = again.get("v").unwrap().as_array().unwrap().as_f64().unwrap().to_vec();
        assert!(v2[1].is_nan() && v2[2] == f64::INFINITY && v2[0] == 1.5);
    }

    #[test]
    fn floats_print_so_that_they_read_back_as_floats() {
        assert_eq!(fmt_f64(1.0), "1.0");
        assert_eq!(fmt_f64(0.1), "0.1");
        assert_eq!(parse(&fmt_f64(1e300)).unwrap().as_f64(), Some(1e300));
        assert_eq!(parse(&fmt_f64(-2.5e-7)).unwrap().as_f64(), Some(-2.5e-7));
        assert!(matches!(parse("[1.0]").unwrap().as_array().unwrap().data, ArrayData::F64(_)));
    }

    #[test]
    fn errors_say_where() {
        let e = parse("{\"a\": [1, 2}").unwrap_err();
        assert!(e.offset > 0 && e.message.contains("expected"));
    }
}
