//! The flat tree — this side's encoder and decoder for the kernel's document door.
//!
//! ★★FYL-DESIGN-16 F-1..F-4 / H-4（T-1 的中间层一半，2026-09-05）：**编码器与解码器只有
//! 中间层一份（Rust），三种宿主共用。** 内核那一半在内核仓 `tree.rs`（阅读器 + 构建器）；
//! 这里把本 crate 的 [`Node`] 摊成四段、把四段收回 [`Node`]。两边逐条同一张表：
//!
//! ```text
//!   nodes  [u32; 8] × n     先序：kind · name_off · name_len · first_child · next_sibling
//!                           · payload_off · payload_len · shape_off      NONE = u32::MAX
//!   names  u8 …             UTF-8：键名 **与字符串载荷** 同块
//!   f64s   f64 …            8 字节对齐、独立成段
//!   ints   i64 …            布尔 / 整数载荷 · 形状 [ndims, d0, …] · 字符串数组的 (off, len) 对
//! ```
//!
//! | kind | | 对应的 [`Node`] |
//! | ---: | :--- | :--- |
//! | 0 | Null | `Node::Null` |
//! | 1 | Bool | `Node::Bool` |
//! | 2 | Int | `Node::Int` |
//! | 3 | F64 | `Node::Float` |
//! | 4 | Str | `Node::Str` |
//! | 5 | F64Array | `Node::Array(ArrayData::F64)` |
//! | 6 | I64Array | `Node::Array(ArrayData::I64)` |
//! | 7 | StrArray | `Node::Array(ArrayData::Str)` |
//! | 8 | List | `Node::List` |
//! | 9 | Map | `Node::Map`（插入有序，往返保序） |
//!
//! ★形的修订号 [`TREE_FORMAT`] 是内核仓生成进 `fyo_interface.rs` 的那个数——两侧的形
//! 不同，就不该有一个字节过门；解码前先比。
//!
//! ★这里**不解析文本**：JSON 进 `Node` 是 `json.rs` 的事，`Node` 进四段是这里的事。
//! 内核收到的是四段，交回的也是四段（`kernel.rs::Kernel::run_tree`）。

use crate::document::{Array, ArrayData, Map, Node};
pub use crate::fyo_interface::TREE_FORMAT;

pub const NONE: u32 = u32::MAX;
pub const NODE_WORDS: usize = 8;

const K_NULL: u32 = 0;
const K_BOOL: u32 = 1;
const K_INT: u32 = 2;
const K_F64: u32 = 3;
const K_STR: u32 = 4;
const K_F64S: u32 = 5;
const K_I64S: u32 = 6;
const K_STRS: u32 = 7;
const K_LIST: u32 = 8;
const K_MAP: u32 = 9;

/// The four segments, owned here.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Buffers {
    pub nodes: Vec<u32>,
    pub names: Vec<u8>,
    pub f64s: Vec<f64>,
    pub ints: Vec<i64>,
}

impl Buffers {
    pub fn n_nodes(&self) -> usize {
        self.nodes.len() / NODE_WORDS
    }
}

struct Encoder {
    out: Buffers,
}

impl Encoder {
    fn name(&mut self, s: &str) -> (u32, u32) {
        let off = self.out.names.len() as u32;
        self.out.names.extend_from_slice(s.as_bytes());
        (off, s.len() as u32)
    }

    fn shape(&mut self, shape: &[usize]) -> u32 {
        let off = self.out.ints.len() as u32;
        self.out.ints.push(shape.len() as i64);
        self.out.ints.extend(shape.iter().map(|d| *d as i64));
        off
    }

    fn write(&mut self, name: Option<&str>, v: &Node) -> usize {
        let (noff, nlen) = match name {
            Some(s) => self.name(s),
            None => (0, 0),
        };
        let mut rec = [K_NULL, noff, nlen, NONE, NONE, 0, 0, NONE];
        match v {
            Node::Null => {}
            Node::Bool(b) => {
                rec[0] = K_BOOL;
                rec[5] = self.out.ints.len() as u32;
                rec[6] = 1;
                self.out.ints.push(i64::from(*b));
            }
            Node::Int(i) => {
                rec[0] = K_INT;
                rec[5] = self.out.ints.len() as u32;
                rec[6] = 1;
                self.out.ints.push(*i);
            }
            Node::Float(x) => {
                rec[0] = K_F64;
                rec[5] = self.out.f64s.len() as u32;
                rec[6] = 1;
                self.out.f64s.push(*x);
            }
            Node::Str(s) => {
                rec[0] = K_STR;
                let (o, l) = self.name(s);
                rec[5] = o;
                rec[6] = l;
            }
            Node::Array(a) => match &a.data {
                ArrayData::F64(d) => {
                    rec[0] = K_F64S;
                    rec[5] = self.out.f64s.len() as u32;
                    rec[6] = d.len() as u32;
                    self.out.f64s.extend_from_slice(d);
                    rec[7] = self.shape(&a.shape);
                }
                ArrayData::I64(d) => {
                    rec[0] = K_I64S;
                    rec[7] = self.shape(&a.shape);
                    rec[5] = self.out.ints.len() as u32;
                    rec[6] = d.len() as u32;
                    self.out.ints.extend_from_slice(d);
                }
                ArrayData::Str(d) => {
                    rec[0] = K_STRS;
                    rec[7] = self.shape(&a.shape);
                    let pairs: Vec<(u32, u32)> = d.iter().map(|s| self.name(s)).collect();
                    rec[5] = self.out.ints.len() as u32;
                    rec[6] = d.len() as u32;
                    for (o, l) in pairs {
                        self.out.ints.push(i64::from(o));
                        self.out.ints.push(i64::from(l));
                    }
                }
            },
            Node::List(_) => rec[0] = K_LIST,
            Node::Map(_) => rec[0] = K_MAP,
        }
        let idx = self.out.n_nodes();
        self.out.nodes.extend_from_slice(&rec);
        let children: Vec<(Option<&str>, &Node)> = match v {
            Node::List(items) => items.iter().map(|c| (None, c)).collect(),
            Node::Map(m) => m.iter().map(|(k, c)| (Some(k), c)).collect(),
            _ => Vec::new(),
        };
        let mut prev: Option<usize> = None;
        for (cname, child) in children {
            let ci = self.write(cname, child);
            match prev {
                None => self.out.nodes[idx * NODE_WORDS + 3] = ci as u32,
                Some(p) => self.out.nodes[p * NODE_WORDS + 4] = ci as u32,
            }
            prev = Some(ci);
        }
        idx
    }
}

/// A document as four segments, pre-order.  The root carries no name.
pub fn encode(root: &Node) -> Buffers {
    let mut e = Encoder { out: Buffers::default() };
    e.write(None, root);
    e.out
}

/// Why four segments could not be read back.
#[derive(Debug, Clone, PartialEq)]
pub struct Malformed {
    pub node: usize,
    pub what: String,
}

/// Four borrowed segments back into a [`Node`].
///
/// ★The kernel validated what it HANDS OUT before handing it (its `Doc::new`),
/// and what we hand IN we built ourselves; so this reader checks bounds — a
/// wrong length would otherwise be a panic in a library a host loaded — but
/// does not re-derive the kernel's full F-3 pass.
pub fn decode(nodes: &[u32], names: &[u8], f64s: &[f64], ints: &[i64]) -> Result<Node, Malformed> {
    if nodes.len() % NODE_WORDS != 0 || nodes.is_empty() {
        return Err(Malformed { node: 0, what: format!("node table is {} words", nodes.len()) });
    }
    Reader { nodes, names, f64s, ints, n: nodes.len() / NODE_WORDS }.build(0)
}

struct Reader<'a> {
    nodes: &'a [u32],
    names: &'a [u8],
    f64s: &'a [f64],
    ints: &'a [i64],
    n: usize,
}

impl<'a> Reader<'a> {
    fn bad(&self, i: usize, what: impl Into<String>) -> Malformed {
        Malformed { node: i, what: what.into() }
    }

    fn rec(&self, i: usize) -> Result<&'a [u32], Malformed> {
        if i >= self.n {
            return Err(self.bad(i, format!("index {i} past {} nodes", self.n)));
        }
        Ok(&self.nodes[i * NODE_WORDS..(i + 1) * NODE_WORDS])
    }

    fn text(&self, i: usize, off: u32, len: u32) -> Result<String, Malformed> {
        let (o, l) = (off as usize, len as usize);
        let end = o.checked_add(l).filter(|e| *e <= self.names.len())
            .ok_or_else(|| self.bad(i, "name range past the names block"))?;
        std::str::from_utf8(&self.names[o..end]).map(str::to_string)
            .map_err(|_| self.bad(i, "name is not UTF-8"))
    }

    fn shape(&self, i: usize, r: &[u32]) -> Result<Vec<usize>, Malformed> {
        let so = r[7];
        if so == NONE {
            return Ok(Vec::new());
        }
        let so = so as usize;
        let nd = *self.ints.get(so).ok_or_else(|| self.bad(i, "shape past the ints"))?;
        if nd < 0 || so + 1 + nd as usize > self.ints.len() {
            return Err(self.bad(i, "shape dims past the ints"));
        }
        Ok(self.ints[so + 1..so + 1 + nd as usize].iter().map(|d| *d as usize).collect())
    }

    fn children(&self, i: usize) -> Vec<usize> {
        let mut out = Vec::new();
        let mut c = self.nodes[i * NODE_WORDS + 3];
        while c != NONE && (c as usize) < self.n {
            out.push(c as usize);
            c = self.nodes[c as usize * NODE_WORDS + 4];
        }
        out
    }

    fn build(&self, i: usize) -> Result<Node, Malformed> {
        let r = self.rec(i)?;
        let (po, pl) = (r[5] as usize, r[6] as usize);
        let f64s = |end: usize| self.f64s.get(po..end).ok_or_else(|| self.bad(i, "payload past the f64 segment"));
        let ints = |end: usize| self.ints.get(po..end).ok_or_else(|| self.bad(i, "payload past the ints segment"));
        Ok(match r[0] {
            K_NULL => Node::Null,
            K_BOOL => Node::Bool(ints(po + 1)?[0] != 0),
            K_INT => Node::Int(ints(po + 1)?[0]),
            K_F64 => Node::Float(f64s(po + 1)?[0]),
            K_STR => Node::Str(self.text(i, r[5], r[6])?),
            K_F64S => Node::Array(Array { shape: self.shape(i, r)?, data: ArrayData::F64(f64s(po + pl)?.to_vec()) }),
            K_I64S => Node::Array(Array { shape: self.shape(i, r)?, data: ArrayData::I64(ints(po + pl)?.to_vec()) }),
            K_STRS => {
                let pairs = ints(po + 2 * pl)?;
                let mut d = Vec::with_capacity(pl);
                for k in 0..pl {
                    d.push(self.text(i, pairs[2 * k] as u32, pairs[2 * k + 1] as u32)?);
                }
                Node::Array(Array { shape: self.shape(i, r)?, data: ArrayData::Str(d) })
            }
            K_LIST => {
                let mut l = Vec::new();
                for c in self.children(i) {
                    l.push(self.build(c)?);
                }
                Node::List(l)
            }
            K_MAP => {
                let mut m = Map::new();
                for c in self.children(i) {
                    let cr = self.rec(c)?;
                    let key = self.text(c, cr[1], cr[2])?;
                    m.insert(key, self.build(c)?);
                }
                Node::Map(m)
            }
            k => return Err(self.bad(i, format!("kind {k} is not one of 0..=9"))),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Node {
        let mut root = Map::new();
        root.insert("code", Node::Str("code/transport".into()));
        let mut s = Map::new();
        s.insert("nr", Node::Int(41));
        s.insert("on", Node::Bool(true));
        s.insert("chi0", Node::Float(1.5));
        s.insert("geometry", Node::Str("miller".into()));
        root.insert("settings", Node::Map(s));
        let mut ts = Map::new();
        let mut p1 = Map::new();
        p1.insert("rho_tor_norm", Node::Array(Array::vec_f64(vec![0.0, 0.5, 1.0])));
        ts.insert("profiles_1d", Node::Map(p1));
        let mut gq = Map::new();
        gq.insert("ip", Node::Float(1.5e7));
        ts.insert("global_quantities", Node::Map(gq));
        let mut eq = Map::new();
        eq.insert("time_slice", Node::List(vec![Node::Map(ts)]));
        let mut inputs = Map::new();
        inputs.insert("equilibrium", Node::Map(eq));
        root.insert("inputs", Node::Map(inputs));
        root.insert("labels", Node::Array(Array::str(vec![2], vec!["α".into(), "β—γ".into()]).unwrap()));
        root.insert("grid", Node::Array(Array::i64(vec![2, 2], vec![1, 2, 3, 4]).unwrap()));
        root.insert("nothing", Node::Null);
        root.insert("empty", Node::List(vec![]));
        Node::Map(root)
    }

    #[test]
    fn a_document_survives_the_round_trip_value_for_value_and_in_order() {
        let v = sample();
        let b = encode(&v);
        let back = decode(&b.nodes, &b.names, &b.f64s, &b.ints).unwrap();
        assert_eq!(back, v);
        assert_eq!(encode(&back), b);
        let keys: Vec<&str> = back.as_map().unwrap().keys().collect();
        assert_eq!(keys, vec!["code", "settings", "inputs", "labels", "grid", "nothing", "empty"]);
    }

    #[test]
    fn the_layout_is_the_kernels_pre_order_layout() {
        let b = encode(&sample());
        //: root map at 0; its first child (`code`) is node 1; `settings` is 2 and its
        //: first child `nr` is 3 — children follow their parent (pre-order)
        assert_eq!(b.nodes[0], K_MAP);
        assert_eq!(b.nodes[3], 1);
        assert_eq!(b.nodes[1 * NODE_WORDS], K_STR);
        assert_eq!(b.nodes[1 * NODE_WORDS + 4], 2);
        assert_eq!(b.nodes[2 * NODE_WORDS + 3], 3);
        //: the f64 segment holds only f64 payloads: chi0, ip, the three rho points
        assert_eq!(b.f64s, vec![1.5, 0.0, 0.5, 1.0, 1.5e7]);
    }

    #[test]
    fn a_short_buffer_is_refused_not_panicked_on() {
        let b = encode(&sample());
        let e = decode(&b.nodes, &b.names, &b.f64s[..1], &b.ints).unwrap_err();
        assert!(e.what.contains("f64 segment"), "{e:?}");
        let e = decode(&b.nodes[..8], &b.names, &b.f64s, &b.ints).unwrap();
        //: a root alone decodes to an empty map (its children are past the table)
        assert_eq!(e, Node::Map(Map::new()));
        assert!(decode(&[], &[], &[], &[]).is_err());
    }
}
