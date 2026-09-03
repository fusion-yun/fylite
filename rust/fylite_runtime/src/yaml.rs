//! YAML 子集读取 —— 够读 fydata 的 A-Box（PyYAML `safe_dump` 的方言），零依赖。
//!
//! ★★为什么是子集、为什么自己写。fydata 的装置 A-Box（`machine.yaml`、
//! `providers/*.yaml`、`bind/mdsplus/*.yaml`、`static/legacy/*.yaml`）全是 YAML，而
//! 本 crate 的依赖表是空的、wasm 也要成立。那些文件都由 PyYAML 写出：块式映射与序列、
//! 三种标量写法、少量单行流式 `{}` / `[]`——没有锚点、别名、标签、多文档。实测
//! （44 份文件）就是这些。一个只认这些的读者三百来行，足以让 Rust 侧**直接读
//! fydata**，不必先由 Python 投影成 JSON。
//!
//! 认的：
//!
//! * 注释、缩进块式映射与序列（含 `- key: v` 紧凑形与 `- - x` 嵌套）；
//! * 朴素标量按 YAML 1.1 核心类型断型（整数、浮点、`true/false`、`null`/`~`），
//!   引号里的一律是字符串（`'0'`、`'*'`）；
//! * 单引号（`''` 转义、跨行折叠）、双引号（转义、`\` 行尾续行、跨行折叠）；
//! * 块标量 `|` / `>`（带 `-` / `+` 收尾）；
//! * 单行流式序列 `[a, b]` 与映射 `{k: v}`，可嵌套；`---` 文档头。
//!
//! 不认的**报错**而不是猜：锚点 `&`、别名 `*`、标签 `!`、复杂键 `?`、多文档。
//! 数值列表照 [`crate::json::normalize_list`] 归一成数组，与 JSON 读入同形。

use crate::document::{Map, Node};

#[derive(Debug, Clone, PartialEq)]
pub struct YamlError {
    pub line: usize,
    pub message: String,
}

impl std::fmt::Display for YamlError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "YAML error at line {}: {}", self.line, self.message)
    }
}

impl std::error::Error for YamlError {}

type Result<T> = std::result::Result<T, YamlError>;

struct Line {
    no: usize,
    indent: usize,
    /// 去掉缩进与行尾注释后的内容；空行与纯注释行以空 `text` 留在表里
    /// （结构层用 [`Parser::structural_peek`] 跳过，块标量按原样读）。
    text: String,
}

fn err<T>(line: usize, m: impl Into<String>) -> Result<T> {
    Err(YamlError { line, message: m.into() })
}

/// 去掉行尾注释：`#` 前面是空白、且不在引号里。
fn strip_comment(s: &str) -> &str {
    let b = s.as_bytes();
    let (mut sq, mut dq) = (false, false);
    let mut i = 0;
    while i < b.len() {
        match b[i] {
            b'\'' if !dq => sq = !sq,
            b'"' if !sq => {
                //: `\"` inside double quotes
                if !(i > 0 && b[i - 1] == b'\\') { dq = !dq; }
            }
            b'#' if !sq && !dq && (i == 0 || b[i - 1] == b' ' || b[i - 1] == b'\t') => {
                return s[..i].trim_end();
            }
            _ => {}
        }
        i += 1;
    }
    s.trim_end()
}

struct Parser {
    lines: Vec<Line>,
    pos: usize,
}

impl Parser {
    fn peek(&self) -> Option<&Line> {
        self.lines.get(self.pos)
    }

    fn line_no(&self) -> usize {
        self.peek().map(|l| l.no).unwrap_or(self.lines.last().map(|l| l.no + 1).unwrap_or(1))
    }

    /// 一个块：从 `indent` 起，映射或序列或标量。
    fn block(&mut self, indent: usize) -> Result<Node> {
        let l = match self.structural_peek() {
            Some(l) => l,
            None => return Ok(Node::Null),
        };
        if l.indent < indent {
            return Ok(Node::Null);
        }
        let at = l.indent;
        if is_seq_item(&l.text) {
            self.sequence(at)
        } else if split_key(&l.text).is_some() {
            self.mapping(at)
        } else {
            //: a lone scalar (possibly multi-line plain / quoted)
            let no = l.no;
            let text = l.text.clone();
            self.pos += 1;
            self.scalar_continued(&text, no, at)
        }
    }

    fn mapping(&mut self, indent: usize) -> Result<Node> {
        let mut m = Map::new();
        while let Some(l) = self.structural_peek() {
            if l.indent < indent {
                break;
            }
            if l.indent > indent {
                return err(l.no, "unexpected indentation");
            }
            let no = l.no;
            let text = l.text.clone();
            let (key, rest) = match split_key(&text) {
                Some(kv) => kv,
                None => return err(no, format!("expected `key:`, got {text:?}")),
            };
            let key = self.key_text(&key, no)?;
            self.pos += 1;
            let value = if rest.is_empty() {
                //: value is the nested block, or a sequence at the SAME indent
                //: (PyYAML writes `key:\n- a\n- b` without indenting the dashes)
                match self.structural_peek().map(|n| (n.indent, is_seq_item(&n.text))) {
                    Some((ni, _)) if ni > indent => self.block(ni)?,
                    Some((ni, true)) if ni == indent => self.sequence(indent)?,
                    _ => Node::Null,
                }
            } else {
                self.inline_value(&rest, no, indent)?
            };
            if m.contains_key(&key) {
                return err(no, format!("duplicate key {key:?}"));
            }
            m.insert(key, value);
        }
        Ok(Node::Map(m))
    }

    fn sequence(&mut self, indent: usize) -> Result<Node> {
        let mut items = Vec::new();
        while let Some(l) = self.structural_peek() {
            if l.indent < indent {
                break;
            }
            if l.indent > indent || !is_seq_item(&l.text) {
                if l.indent == indent {
                    break;
                }
                return err(l.no, "unexpected indentation in sequence");
            }
            let no = l.no;
            let rest = l.text[1..].trim_start().to_string();
            let inner_indent = indent + 1 + (l.text.len() - 1 - l.text[1..].trim_start().len());
            self.pos += 1;
            if rest.is_empty() {
                let v = match self.structural_peek().map(|n| n.indent) {
                    Some(ni) if ni > indent => self.block(ni)?,
                    _ => Node::Null,
                };
                items.push(v);
                continue;
            }
            //: `- key: v` — the item is a mapping whose first entry is on this line;
            //: `- - x` — a nested sequence.  Splice a synthetic line back in.
            if is_seq_item(&rest) || split_key(&rest).is_some() && !starts_quoted(&rest) && !is_flow(&rest) {
                self.lines.insert(self.pos, Line { no, indent: inner_indent, text: rest });
                items.push(self.block(inner_indent)?);
            } else {
                items.push(self.inline_value(&rest, no, indent)?);
            }
        }
        Ok(crate::json::normalize_list(items))
    }

    fn key_text(&self, key: &str, no: usize) -> Result<String> {
        let k = key.trim();
        if k.starts_with('\'') || k.starts_with('"') {
            match self.scalar_inline(k, no)? {
                Node::Str(s) => Ok(s),
                other => Ok(format!("{other:?}")),
            }
        } else {
            Ok(k.to_string())
        }
    }

    /// 一个跟在 `key: ` 或 `- ` 后面的值。
    fn inline_value(&mut self, rest: &str, no: usize, indent: usize) -> Result<Node> {
        let r = rest.trim();
        if r.starts_with('|') || r.starts_with('>') {
            return self.block_scalar(r, no, indent);
        }
        if r.starts_with('&') || r.starts_with('*') || r.starts_with('!') {
            return err(no, format!("anchors, aliases and tags are not supported: {r:?}"));
        }
        if is_flow(r) {
            let mut p = Flow { s: r.as_bytes(), i: 0, no };
            let v = p.value()?;
            p.ws();
            if p.i != p.s.len() {
                return err(no, "trailing text after a flow collection");
            }
            return Ok(v);
        }
        self.scalar_continued(r, no, indent)
    }

    /// 标量，允许跨到后面缩进更深的行（引号内的折叠，或朴素标量的续行）。
    fn scalar_continued(&mut self, first: &str, no: usize, indent: usize) -> Result<Node> {
        let quoted = starts_quoted(first);
        let mut text = first.to_string();
        if quoted && !closed(first) {
            //: gather until the closing quote
            loop {
                let l = match self.peek() {
                    Some(l) => l,
                    None => return err(no, "unterminated quoted string"),
                };
                text.push('\n');
                text.push_str(&l.text);
                self.pos += 1;
                if closed(&text) {
                    break;
                }
            }
        } else if !quoted {
            //: plain multi-line scalar: continuation lines are more indented
            while let Some(l) = self.peek() {
                //: a blank or comment line ends a plain scalar (as in PyYAML)
                if l.text.is_empty() || l.indent <= indent || is_seq_item(&l.text) || split_key(&l.text).is_some() {
                    break;
                }
                text.push(' ');
                text.push_str(l.text.trim());
                self.pos += 1;
            }
        }
        self.scalar_inline(&text, no)
    }

    fn block_scalar(&mut self, header: &str, no: usize, indent: usize) -> Result<Node> {
        let folded = header.starts_with('>');
        let chomp = header[1..].trim();
        let keep = chomp.contains('+');
        let strip = chomp.contains('-');
        let mut raw: Vec<(usize, String)> = Vec::new();
        //: block scalar lines are taken RAW (comments and blanks included), so
        //: read them off the source text captured beside the logical lines
        let mut block_indent: Option<usize> = None;
        while let Some(l) = self.raw_peek() {
            let (ind, txt) = l;
            if txt.trim().is_empty() {
                raw.push((0, String::new()));
                self.raw_advance();
                continue;
            }
            if ind <= indent {
                break;
            }
            let bi = *block_indent.get_or_insert(ind);
            if ind < bi {
                break;
            }
            raw.push((ind, txt.to_string()));
            self.raw_advance();
        }
        let bi = block_indent.unwrap_or(indent + 1);
        //: trailing blank lines are the chomping question
        let mut lines: Vec<String> = raw.iter().map(|(ind, t)| if t.is_empty() { String::new() } else { format!("{}{}", " ".repeat(ind - bi), t) }).collect();
        let trailing = lines.iter().rev().take_while(|l| l.is_empty()).count();
        let body_len = lines.len() - trailing;
        lines.truncate(body_len + if keep { trailing } else { 0 });
        let mut out = if folded {
            let mut s = String::new();
            let mut prev_blank = true;
            for (i, l) in lines[..body_len].iter().enumerate() {
                if l.is_empty() {
                    s.push('\n');
                    prev_blank = true;
                } else {
                    if !prev_blank && i > 0 && !l.starts_with(' ') {
                        s.push(' ');
                    }
                    s.push_str(l);
                    prev_blank = false;
                }
            }
            s
        } else {
            lines[..body_len].join("\n")
        };
        if !strip && body_len > 0 {
            out.push('\n');
        }
        if keep {
            for _ in 0..trailing {
                out.push('\n');
            }
        }
        let _ = no;
        Ok(Node::Str(out))
    }

    fn raw_peek(&self) -> Option<(usize, &str)> {
        self.peek().map(|l| (l.indent, l.text.as_str()))
    }

    fn raw_advance(&mut self) {
        self.pos += 1;
    }

    /// 一个不再跨行的标量文本 → 节点。
    fn scalar_inline(&self, text: &str, no: usize) -> Result<Node> {
        let t = text.trim();
        if let Some(inner) = t.strip_prefix('\'') {
            let inner = inner.strip_suffix('\'').ok_or_else(|| YamlError { line: no, message: "unterminated single-quoted string".into() })?;
            return Ok(Node::Str(fold_quoted(&inner.replace("''", "\u{0}")).replace('\u{0}', "'")));
        }
        if let Some(inner) = t.strip_prefix('"') {
            let inner = inner.strip_suffix('"').ok_or_else(|| YamlError { line: no, message: "unterminated double-quoted string".into() })?;
            return Ok(Node::Str(unescape_double(inner, no)?));
        }
        Ok(plain_scalar(t))
    }
}

fn is_seq_item(s: &str) -> bool {
    s == "-" || s.starts_with("- ")
}

fn starts_quoted(s: &str) -> bool {
    s.starts_with('\'') || s.starts_with('"')
}

fn is_flow(s: &str) -> bool {
    s.starts_with('[') || s.starts_with('{')
}

/// `key: rest` → (key, rest)。键可以带引号；`:` 后必须是空白或行尾；URL 里的 `:`
/// 不算（`mdsplus://…` 后面没有空格）。
fn split_key(s: &str) -> Option<(String, String)> {
    let b = s.as_bytes();
    if b.is_empty() || is_seq_item(s) || is_flow(s) {
        return None;
    }
    let mut i = 0;
    if starts_quoted(s) {
        let q = b[0];
        i = 1;
        while i < b.len() {
            if b[i] == q {
                if q == b'\'' && i + 1 < b.len() && b[i + 1] == b'\'' { i += 2; continue; }
                if q == b'"' && b[i - 1] == b'\\' { i += 1; continue; }
                break;
            }
            i += 1;
        }
        i += 1;
        let rest = s[i..].trim_start();
        return match rest.strip_prefix(':') {
            Some(r) if r.is_empty() || r.starts_with(' ') || r.starts_with('\t') => Some((s[..i].to_string(), r.trim().to_string())),
            _ => None,
        };
    }
    while i < b.len() {
        if b[i] == b':' && (i + 1 == b.len() || b[i + 1] == b' ' || b[i + 1] == b'\t') {
            return Some((s[..i].to_string(), s[i + 1..].trim().to_string()));
        }
        if b[i] == b'#' && i > 0 && b[i - 1] == b' ' {
            return None;
        }
        i += 1;
    }
    None
}

fn closed(text: &str) -> bool {
    let b = text.as_bytes();
    let q = b[0];
    let mut i = 1;
    while i < b.len() {
        if b[i] == q {
            if q == b'\'' {
                if i + 1 < b.len() && b[i + 1] == b'\'' { i += 2; continue; }
                return true;
            }
            if b[i - 1] != b'\\' {
                return true;
            }
        }
        i += 1;
    }
    false
}

/// 引号内的跨行折叠：单个换行折成空格，空行折成换行；行首行尾空白去掉。
fn fold_quoted(s: &str) -> String {
    if !s.contains('\n') {
        return s.to_string();
    }
    let mut out = String::new();
    let mut pending_breaks = 0usize;
    for (i, line) in s.split('\n').enumerate() {
        let piece = if i == 0 { line.trim_end() } else { line.trim() };
        if i > 0 {
            if piece.is_empty() {
                pending_breaks += 1;
                continue;
            }
            if pending_breaks > 0 {
                for _ in 0..pending_breaks { out.push('\n'); }
                pending_breaks = 0;
            } else {
                out.push(' ');
            }
        }
        out.push_str(piece);
    }
    out
}

/// 双引号：先按 `\` 续行与折叠处理行，再解转义。
fn unescape_double(s: &str, no: usize) -> Result<String> {
    //: line folding: a `\` at the end of a line joins without a space and the
    //: next line's leading blanks are dropped; a plain line break folds to a
    //: space; an empty line to a newline.
    let mut joined = String::new();
    let lines: Vec<&str> = s.split('\n').collect();
    let mut pending_breaks = 0usize;
    let mut escaped_join = false;
    for (i, line) in lines.iter().enumerate() {
        let piece = if i == 0 { *line } else { line.trim_start() };
        let piece = if i + 1 < lines.len() { piece.trim_end() } else { piece };
        if i > 0 {
            if piece.is_empty() {
                pending_breaks += 1;
                continue;
            }
            if escaped_join || pending_breaks > 0 {
                //: after a `\` continuation nothing is inserted; blank lines fold to newlines
                for _ in 0..pending_breaks { joined.push('\n'); }
            } else {
                joined.push(' ');
            }
            pending_breaks = 0;
        }
        if let Some(stripped) = piece.strip_suffix('\\') {
            //: a trailing backslash that is not itself escaped
            let n_back = stripped.chars().rev().take_while(|c| *c == '\\').count();
            if n_back % 2 == 0 {
                joined.push_str(stripped);
                escaped_join = true;
                continue;
            }
        }
        joined.push_str(piece);
        escaped_join = false;
    }
    let mut out = String::new();
    let mut chars = joined.chars().peekable();
    while let Some(c) = chars.next() {
        if c != '\\' {
            out.push(c);
            continue;
        }
        match chars.next() {
            Some('n') => out.push('\n'),
            Some('t') => out.push('\t'),
            Some('r') => out.push('\r'),
            Some('"') => out.push('"'),
            Some('\\') => out.push('\\'),
            Some('/') => out.push('/'),
            Some(' ') => out.push(' '),
            Some('0') => out.push('\0'),
            Some('e') => out.push('\u{1b}'),
            Some('x') => { out.push(hex(&mut chars, 2, no)?); }
            Some('u') => { out.push(hex(&mut chars, 4, no)?); }
            Some('U') => { out.push(hex(&mut chars, 8, no)?); }
            Some(other) => { out.push('\\'); out.push(other); }
            None => out.push('\\'),
        }
    }
    Ok(out)
}

fn hex(chars: &mut std::iter::Peekable<std::str::Chars>, n: usize, no: usize) -> Result<char> {
    let mut v = 0u32;
    for _ in 0..n {
        let c = chars.next().ok_or_else(|| YamlError { line: no, message: "short escape".into() })?;
        v = v * 16 + c.to_digit(16).ok_or_else(|| YamlError { line: no, message: "bad hex escape".into() })?;
    }
    Ok(char::from_u32(v).unwrap_or('\u{FFFD}'))
}

/// 朴素标量断型（YAML 1.1 的核心几种；其余是字符串）。
pub fn plain_scalar(t: &str) -> Node {
    match t {
        "" | "~" | "null" | "Null" | "NULL" => return Node::Null,
        "true" | "True" | "TRUE" | "yes" | "Yes" | "on" | "On" => return Node::Bool(true),
        "false" | "False" | "FALSE" | "no" | "No" | "off" | "Off" => return Node::Bool(false),
        ".inf" | ".Inf" | ".INF" | "+.inf" => return Node::Float(f64::INFINITY),
        "-.inf" | "-.Inf" | "-.INF" => return Node::Float(f64::NEG_INFINITY),
        ".nan" | ".NaN" | ".NAN" => return Node::Float(f64::NAN),
        _ => {}
    }
    let s = t.replace('_', "");
    let (sign, mag) = match s.strip_prefix('-') {
        Some(m) => (-1i64, m),
        None => (1, s.strip_prefix('+').unwrap_or(&s)),
    };
    let digits = !mag.is_empty() && mag.chars().all(|c| c.is_ascii_digit());
    if digits && mag.len() > 1 && mag.starts_with('0') {
        //: YAML 1.1 (and PyYAML): a leading zero means octal; `089` is a string
        return match i64::from_str_radix(mag, 8) {
            Ok(i) => Node::Int(sign * i),
            Err(_) => Node::Str(t.to_string()),
        };
    }
    if let Ok(i) = s.parse::<i64>() {
        return Node::Int(i);
    }
    if let Some(h) = mag.strip_prefix("0x") {
        if let Ok(i) = i64::from_str_radix(h, 16) { return Node::Int(sign * i); }
    }
    if let Some(h) = mag.strip_prefix("0b") {
        if let Ok(i) = i64::from_str_radix(h, 2) { return Node::Int(sign * i); }
    }
    if s.chars().any(|c| c.is_ascii_digit()) && s.chars().all(|c| c.is_ascii_digit() || matches!(c, '.' | 'e' | 'E' | '+' | '-')) {
        if let Ok(f) = s.parse::<f64>() {
            return Node::Float(f);
        }
    }
    Node::Str(t.to_string())
}

/// 单行流式集合。
struct Flow<'a> {
    s: &'a [u8],
    i: usize,
    no: usize,
}

impl<'a> Flow<'a> {
    fn ws(&mut self) {
        while self.i < self.s.len() && (self.s[self.i] == b' ' || self.s[self.i] == b'\t') {
            self.i += 1;
        }
    }

    fn value(&mut self) -> Result<Node> {
        self.ws();
        match self.s.get(self.i) {
            Some(b'[') => {
                self.i += 1;
                let mut items = Vec::new();
                loop {
                    self.ws();
                    if self.s.get(self.i) == Some(&b']') { self.i += 1; break; }
                    items.push(self.value()?);
                    self.ws();
                    match self.s.get(self.i) {
                        Some(b',') => { self.i += 1; }
                        Some(b']') => { self.i += 1; break; }
                        _ => return err(self.no, "expected `,` or `]`"),
                    }
                }
                Ok(crate::json::normalize_list(items))
            }
            Some(b'{') => {
                self.i += 1;
                let mut m = Map::new();
                loop {
                    self.ws();
                    if self.s.get(self.i) == Some(&b'}') { self.i += 1; break; }
                    let key = match self.scalar(true)? { Node::Str(s) => s, other => format!("{other:?}") };
                    self.ws();
                    if self.s.get(self.i) != Some(&b':') {
                        return err(self.no, "expected `:` in a flow mapping");
                    }
                    self.i += 1;
                    let v = self.value()?;
                    m.insert(key, v);
                    self.ws();
                    match self.s.get(self.i) {
                        Some(b',') => { self.i += 1; }
                        Some(b'}') => { self.i += 1; break; }
                        _ => return err(self.no, "expected `,` or `}`"),
                    }
                }
                Ok(Node::Map(m))
            }
            _ => self.scalar(false),
        }
    }

    fn scalar(&mut self, as_key: bool) -> Result<Node> {
        self.ws();
        let start = self.i;
        match self.s.get(self.i) {
            Some(&q) if q == b'\'' || q == b'"' => {
                self.i += 1;
                while self.i < self.s.len() {
                    if self.s[self.i] == q {
                        if q == b'\'' && self.s.get(self.i + 1) == Some(&b'\'') { self.i += 2; continue; }
                        if q == b'"' && self.s[self.i - 1] == b'\\' { self.i += 1; continue; }
                        break;
                    }
                    self.i += 1;
                }
                self.i += 1;
                let text = std::str::from_utf8(&self.s[start..self.i.min(self.s.len())]).unwrap_or("");
                let inner = &text[1..text.len().saturating_sub(1)];
                Ok(Node::Str(if q == b'\'' { inner.replace("''", "'") } else { unescape_double(inner, self.no)? }))
            }
            _ => {
                while self.i < self.s.len() {
                    let c = self.s[self.i];
                    if c == b',' || c == b']' || c == b'}' || (as_key && c == b':') {
                        break;
                    }
                    if c == b':' && self.s.get(self.i + 1).map(|n| *n == b' ').unwrap_or(true) {
                        break;
                    }
                    self.i += 1;
                }
                let text = std::str::from_utf8(&self.s[start..self.i]).unwrap_or("").trim();
                Ok(plain_scalar(text))
            }
        }
    }
}

/// 解析一份 YAML 文本。
pub fn parse(text: &str) -> Result<Node> {
    let mut lines = Vec::new();
    for (i, raw) in text.lines().enumerate() {
        let no = i + 1;
        let raw = raw.trim_end_matches('\r');
        if raw.starts_with("---") {
            if raw.trim() != "---" && !raw.starts_with("--- ") {
                return err(no, "unsupported document header");
            }
            if lines.iter().any(|l: &Line| !l.text.is_empty()) {
                return err(no, "multi-document YAML is not supported");
            }
            continue;
        }
        if raw.starts_with("...") {
            break;
        }
        if raw.starts_with('%') {
            return err(no, "directives are not supported");
        }
        let expanded = raw.replace('\t', "    ");
        let indent = expanded.len() - expanded.trim_start().len();
        let body = strip_comment(expanded.trim_start());
        if body.is_empty() {
            //: blank / comment-only lines matter only inside block scalars,
            //: which read them through `text.is_empty()`
            lines.push(Line { no, indent, text: String::new() });
            continue;
        }
        lines.push(Line { no, indent, text: body.to_string() });
    }
    let mut p = Parser { lines, pos: 0 };
    let root = if p.structural_peek().is_none() { Node::Null } else { p.block(0)? };
    p.skip_blank();
    if let Some(l) = p.peek() {
        return err(l.no, format!("unexpected content {:?}", l.text));
    }
    Ok(root)
}

impl Parser {
    fn skip_blank(&mut self) {
        while let Some(l) = self.peek() {
            if l.text.is_empty() { self.pos += 1; } else { break; }
        }
    }

    /// 结构层的 `peek`：跳过空行与纯注释行（块标量另有读法，见 `raw_peek`）。
    fn structural_peek(&mut self) -> Option<&Line> {
        self.skip_blank();
        self.peek()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_the_shapes_pyyaml_writes() {
        let text = r#"
# a comment
_ids: magnetics
provenance:
  comment: "from x\n                east_fl.data — loops (R[m] Z[m])\n    \
    \            east_bp.data — probes"
  provider: Zhenping LUO zhpluo@ipp.ac.cn
  creation_date: '2020-10-12'
  homogeneous_time: 1
$source:
  efit_east: mdsplus://127.0.0.1/mdsplus/~t?shot={shot}&tree_name=efit_east
time:
  $link: efit_east:TIME
b_field_pol_probe:
- name: PCBPV1T
  position:
    r: 1.2905
    z: 0
  toroidal_angle: 90
- name: PCBPV2T   # trailing comment
  position: {r: 1.29, z: 0.248}
  flags: [1, 2, 3]
  outline:
  - - 2.277
    - 0.485
  - - 2.273
    - 0.485
time_slice:
- id: '*'
  boundary:
    type:
      $link: efit_east:1
    outline:
      r:
        $link: 'efit_east:BDRY[0, 0: NBDRY[{time_slice}]-1,{time_slice}]'
note: >-
  folded
  text
literal: |
  line one
  line two
empty:
tilde: ~
"#;
        let d = parse(text).unwrap();
        assert_eq!(d.get("_ids").and_then(Node::as_str), Some("magnetics"));
        assert_eq!(d.get("provenance/comment").and_then(Node::as_str), Some("from x\n                east_fl.data — loops (R[m] Z[m])\n                east_bp.data — probes"));
        assert_eq!(d.get("provenance/creation_date").and_then(Node::as_str), Some("2020-10-12"));
        assert_eq!(d.get("provenance/homogeneous_time").and_then(Node::as_i64), Some(1));
        assert_eq!(d.get("$source/efit_east").and_then(Node::as_str), Some("mdsplus://127.0.0.1/mdsplus/~t?shot={shot}&tree_name=efit_east"));
        assert_eq!(d.get("time/$link").and_then(Node::as_str), Some("efit_east:TIME"));
        assert_eq!(d.get("b_field_pol_probe/0/name").and_then(Node::as_str), Some("PCBPV1T"));
        assert_eq!(d.get("b_field_pol_probe/0/position/r").and_then(Node::as_f64), Some(1.2905));
        assert_eq!(d.get("b_field_pol_probe/0/position/z").and_then(Node::as_i64), Some(0));
        assert_eq!(d.get("b_field_pol_probe/1/position/z").and_then(Node::as_f64), Some(0.248));
        assert_eq!(d.get("b_field_pol_probe/1/flags").map(Node::shape), Some(vec![3]));
        assert_eq!(d.get("b_field_pol_probe/1/outline").map(Node::shape), Some(vec![2, 2]));
        assert_eq!(d.get("time_slice/0/id").and_then(Node::as_str), Some("*"));
        assert_eq!(d.get("time_slice/0/boundary/type/$link").and_then(Node::as_str), Some("efit_east:1"));
        assert_eq!(d.get("time_slice/0/boundary/outline/r/$link").and_then(Node::as_str), Some("efit_east:BDRY[0, 0: NBDRY[{time_slice}]-1,{time_slice}]"));
        assert_eq!(d.get("note").and_then(Node::as_str), Some("folded text"));
        assert_eq!(d.get("literal").and_then(Node::as_str), Some("line one\nline two\n"));
        assert!(d.get("empty").unwrap().is_null());
        assert!(d.get("tilde").unwrap().is_null());
    }

    #[test]
    fn what_is_not_supported_is_refused() {
        assert!(parse("a: &x 1\nb: *x\n").is_err());
        assert!(parse("a: !!str 1\n").is_err());
        assert!(parse("---\na: 1\n---\nb: 2\n").is_err());
        assert!(parse("a: 'unterminated\n").is_err());
    }

    #[test]
    fn scalars_are_typed_like_pyyaml() {
        assert_eq!(plain_scalar("12"), Node::Int(12));
        assert_eq!(plain_scalar("-1.5e3"), Node::Float(-1500.0));
        assert_eq!(plain_scalar("yes"), Node::Bool(true));
        assert_eq!(plain_scalar("1.0"), Node::Float(1.0));
        assert_eq!(plain_scalar("1_000"), Node::Int(1000));
        assert_eq!(plain_scalar("0123"), Node::Int(83));
        assert_eq!(plain_scalar("089"), Node::Str("089".into()));
        assert_eq!(plain_scalar("0x1f"), Node::Int(31));
        assert_eq!(plain_scalar("1e3"), Node::Float(1000.0));
        assert_eq!(plain_scalar("+7"), Node::Int(7));
        assert_eq!(plain_scalar("-"), Node::Str("-".into()));
        assert_eq!(plain_scalar("."), Node::Str(".".into()));
        assert_eq!(plain_scalar("PCBPV1T"), Node::Str("PCBPV1T".into()));
        assert_eq!(plain_scalar("2020-10-12"), Node::Str("2020-10-12".into()));
    }
}
