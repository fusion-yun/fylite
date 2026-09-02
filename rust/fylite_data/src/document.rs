//! 文档模型 —— 数据层里**每一种格式都读成、写自**的那一棵树。
//!
//! ★★**为什么要有一棵中立的树。** 数据层的活是「不同数据源 ↔ fyo」：g-file、
//! a-file、HDF5、netCDF、JSON-LD、MDSplus 各有各的形状，而 fyo 文档只有一种形状
//! ——映射、结构数组（AoS）、数值数组、标量、字符串，键名是 IMAS DD 的名字或
//! `fylite:` 前缀的本地名（`fyo.rs` 的 `@fyo-table`）。每种格式各写一个「到别的
//! 每种格式」的转换是 N² 条路；每种格式只写「到这棵树」与「从这棵树」是 2N 条。
//! 合并多个数据源（`merge`）也只需在这棵树上做一次。
//!
//! ## 形状
//!
//! * [`Node::Map`] —— 一个结构（IDS 的一层）。**保持插入顺序**：JSON-LD 文档的
//!   `@context`/`@id`/`@type` 在前、正文在后，写回去应当还是这个样子；一张按键排序
//!   的表会把 `@type` 排到 `time_slice` 后面。
//! * [`Node::List`] —— 结构数组（AoS，`time_slice[]`）或任何非数值列表。
//! * [`Node::Array`] —— 数值/字符串 **N 维数组**，行主序（C order），带形状。
//!   ★数值列表在解析时归一成它（`json.rs`），因为 HDF5/netCDF 需要形状与 dtype，
//!   而「一串嵌套 JSON 列表」没有这两样。
//! * 标量：[`Node::Int`] / [`Node::Float`] / [`Node::Str`] / [`Node::Bool`] /
//!   [`Node::Null`]。
//!
//! ## 路径
//!
//! `time_slice/0/profiles_2d/0/psi` —— 段以 `/` 分，整数段索引 AoS。
//! ★与内核 `fyo.rs` 那张表同一条规则的第二形态：表里写 `time_slice/profiles_1d/psi`
//! 不带索引，意思是「**第 0 个**」（`AOS` 声明的段走索引 0）。[`Node::walk`] 的
//! `aos_zero = true` 就是那条规则；显式索引永远优先。

use std::fmt;

/// 一棵文档树的节点。
#[derive(Debug, Clone, PartialEq)]
pub enum Node {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Str(String),
    Array(Array),
    List(Vec<Node>),
    Map(Map),
}

/// 插入有序的映射。
///
/// ★线性查找，不是哈希：一层 IDS 结构通常十几个键，最多几百；而顺序是这棵树
/// 要保住的东西之一（见模块抬头）。
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Map {
    entries: Vec<(String, Node)>,
}

/// N 维数组，行主序。
#[derive(Debug, Clone, PartialEq)]
pub struct Array {
    pub shape: Vec<usize>,
    pub data: ArrayData,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ArrayData {
    F64(Vec<f64>),
    I64(Vec<i64>),
    Str(Vec<String>),
}

#[derive(Debug, Clone, PartialEq)]
pub enum DocError {
    /// 路径里的一段不是数、却落在了一个列表上，或反过来。
    Path(String),
    /// 形状与元素数对不上。
    Shape { shape: Vec<usize>, len: usize },
    /// 值不是要求的类型。
    Type(String),
}

impl fmt::Display for DocError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DocError::Path(p) => write!(f, "document path {p:?} is not addressable"),
            DocError::Shape { shape, len } =>
                write!(f, "array shape {shape:?} does not hold {len} elements"),
            DocError::Type(t) => write!(f, "document value is not a {t}"),
        }
    }
}

impl std::error::Error for DocError {}

// --------------------------------------------------------------------------
// Map
// --------------------------------------------------------------------------

impl Map {
    pub fn new() -> Self {
        Map { entries: Vec::new() }
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn get(&self, key: &str) -> Option<&Node> {
        self.entries.iter().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    pub fn get_mut(&mut self, key: &str) -> Option<&mut Node> {
        self.entries.iter_mut().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    pub fn contains_key(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    /// 插入或替换；替换保持原来的位置。
    pub fn insert(&mut self, key: impl Into<String>, value: Node) -> Option<Node> {
        let key = key.into();
        if let Some(slot) = self.entries.iter_mut().find(|(k, _)| *k == key) {
            return Some(std::mem::replace(&mut slot.1, value));
        }
        self.entries.push((key, value));
        None
    }

    pub fn remove(&mut self, key: &str) -> Option<Node> {
        let i = self.entries.iter().position(|(k, _)| k == key)?;
        Some(self.entries.remove(i).1)
    }

    /// 取一个键，没有就放一个空映射进去。
    pub fn entry_map(&mut self, key: &str) -> &mut Node {
        if !self.contains_key(key) {
            self.entries.push((key.to_string(), Node::Map(Map::new())));
        }
        self.get_mut(key).unwrap()
    }

    pub fn iter(&self) -> impl Iterator<Item = (&str, &Node)> {
        self.entries.iter().map(|(k, v)| (k.as_str(), v))
    }

    pub fn iter_mut(&mut self) -> impl Iterator<Item = (&str, &mut Node)> {
        self.entries.iter_mut().map(|(k, v)| (k.as_str(), v))
    }

    pub fn keys(&self) -> impl Iterator<Item = &str> {
        self.entries.iter().map(|(k, _)| k.as_str())
    }

    pub fn into_iter(self) -> impl Iterator<Item = (String, Node)> {
        self.entries.into_iter()
    }
}

impl FromIterator<(String, Node)> for Map {
    fn from_iter<T: IntoIterator<Item = (String, Node)>>(iter: T) -> Self {
        let mut m = Map::new();
        for (k, v) in iter {
            m.insert(k, v);
        }
        m
    }
}

// --------------------------------------------------------------------------
// Array
// --------------------------------------------------------------------------

impl Array {
    pub fn f64(shape: Vec<usize>, data: Vec<f64>) -> Result<Self, DocError> {
        let a = Array { shape, data: ArrayData::F64(data) };
        a.check()
    }

    pub fn i64(shape: Vec<usize>, data: Vec<i64>) -> Result<Self, DocError> {
        let a = Array { shape, data: ArrayData::I64(data) };
        a.check()
    }

    pub fn str(shape: Vec<usize>, data: Vec<String>) -> Result<Self, DocError> {
        let a = Array { shape, data: ArrayData::Str(data) };
        a.check()
    }

    /// 一维 f64。
    pub fn vec_f64(data: Vec<f64>) -> Self {
        Array { shape: vec![data.len()], data: ArrayData::F64(data) }
    }

    fn check(self) -> Result<Self, DocError> {
        let n: usize = self.shape.iter().product();
        if n != self.len() {
            return Err(DocError::Shape { shape: self.shape.clone(), len: self.len() });
        }
        Ok(self)
    }

    pub fn len(&self) -> usize {
        match &self.data {
            ArrayData::F64(v) => v.len(),
            ArrayData::I64(v) => v.len(),
            ArrayData::Str(v) => v.len(),
        }
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    pub fn ndim(&self) -> usize {
        self.shape.len()
    }

    /// 数值内容按 f64 取；字符串数组给 `None`。
    pub fn to_f64(&self) -> Option<Vec<f64>> {
        match &self.data {
            ArrayData::F64(v) => Some(v.clone()),
            ArrayData::I64(v) => Some(v.iter().map(|&x| x as f64).collect()),
            ArrayData::Str(_) => None,
        }
    }

    pub fn as_f64(&self) -> Option<&[f64]> {
        match &self.data {
            ArrayData::F64(v) => Some(v),
            _ => None,
        }
    }

    pub fn as_i64(&self) -> Option<&[i64]> {
        match &self.data {
            ArrayData::I64(v) => Some(v),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&[String]> {
        match &self.data {
            ArrayData::Str(v) => Some(v),
            _ => None,
        }
    }

    pub fn is_numeric(&self) -> bool {
        !matches!(self.data, ArrayData::Str(_))
    }

    /// 行主序 → 列主序（或反之：转置的形状与数据）。
    ///
    /// ★IMAS 的 HDF5 后端按 Fortran 序存数据轴（`hdf5_dataset_handler.cpp`：
    /// `dims[i + AOSRank] = size[dim - i - 1]`），同一段字节的形状是反过来的。
    /// 这里给的是**不动字节、只反形状**之外的另一件事：真正的转置。
    pub fn transposed(&self) -> Array {
        let nd = self.shape.len();
        if nd < 2 {
            return self.clone();
        }
        let rshape: Vec<usize> = self.shape.iter().rev().copied().collect();
        let n = self.len();
        // strides of the source, row-major
        let mut strides = vec![1usize; nd];
        for i in (0..nd - 1).rev() {
            strides[i] = strides[i + 1] * self.shape[i + 1];
        }
        let index_of = |flat: usize| -> usize {
            // flat index in the transposed (rshape) row-major layout -> source flat
            let mut rem = flat;
            let mut src = 0usize;
            for (k, &d) in rshape.iter().enumerate().rev() {
                let idx = rem % d;
                rem /= d;
                // axis k of rshape is axis nd-1-k of the source
                src += idx * strides[nd - 1 - k];
            }
            src
        };
        let data = match &self.data {
            ArrayData::F64(v) => ArrayData::F64((0..n).map(|i| v[index_of(i)]).collect()),
            ArrayData::I64(v) => ArrayData::I64((0..n).map(|i| v[index_of(i)]).collect()),
            ArrayData::Str(v) => ArrayData::Str((0..n).map(|i| v[index_of(i)].clone()).collect()),
        };
        Array { shape: rshape, data }
    }
}

// --------------------------------------------------------------------------
// Node
// --------------------------------------------------------------------------

impl Default for Node {
    fn default() -> Self {
        Node::Null
    }
}

impl From<f64> for Node {
    fn from(v: f64) -> Self {
        Node::Float(v)
    }
}
impl From<i64> for Node {
    fn from(v: i64) -> Self {
        Node::Int(v)
    }
}
impl From<&str> for Node {
    fn from(v: &str) -> Self {
        Node::Str(v.to_string())
    }
}
impl From<String> for Node {
    fn from(v: String) -> Self {
        Node::Str(v)
    }
}
impl From<bool> for Node {
    fn from(v: bool) -> Self {
        Node::Bool(v)
    }
}
impl From<Vec<f64>> for Node {
    fn from(v: Vec<f64>) -> Self {
        Node::Array(Array::vec_f64(v))
    }
}
impl From<Array> for Node {
    fn from(a: Array) -> Self {
        Node::Array(a)
    }
}
impl From<Map> for Node {
    fn from(m: Map) -> Self {
        Node::Map(m)
    }
}

impl Node {
    pub fn map() -> Node {
        Node::Map(Map::new())
    }

    pub fn is_null(&self) -> bool {
        matches!(self, Node::Null)
    }

    pub fn as_map(&self) -> Option<&Map> {
        match self {
            Node::Map(m) => Some(m),
            _ => None,
        }
    }

    pub fn as_map_mut(&mut self) -> Option<&mut Map> {
        match self {
            Node::Map(m) => Some(m),
            _ => None,
        }
    }

    pub fn as_list(&self) -> Option<&[Node]> {
        match self {
            Node::List(l) => Some(l),
            _ => None,
        }
    }

    pub fn as_array(&self) -> Option<&Array> {
        match self {
            Node::Array(a) => Some(a),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Option<&str> {
        match self {
            Node::Str(s) => Some(s),
            _ => None,
        }
    }

    /// 标量按 f64 —— `Int` 也算，一元数组也算。
    pub fn as_f64(&self) -> Option<f64> {
        match self {
            Node::Float(v) => Some(*v),
            Node::Int(v) => Some(*v as f64),
            Node::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
            Node::Array(a) if a.len() == 1 => a.to_f64().map(|v| v[0]),
            _ => None,
        }
    }

    pub fn as_i64(&self) -> Option<i64> {
        match self {
            Node::Int(v) => Some(*v),
            Node::Float(v) if v.fract() == 0.0 => Some(*v as i64),
            Node::Bool(b) => Some(*b as i64),
            Node::Array(a) if a.len() == 1 => match &a.data {
                ArrayData::I64(v) => Some(v[0]),
                ArrayData::F64(v) if v[0].fract() == 0.0 => Some(v[0] as i64),
                _ => None,
            },
            _ => None,
        }
    }

    /// 数值内容按 `Vec<f64>`：标量给一元，数组给全部。
    pub fn to_f64_vec(&self) -> Option<Vec<f64>> {
        match self {
            Node::Array(a) => a.to_f64(),
            other => other.as_f64().map(|v| vec![v]),
        }
    }

    /// 形状：标量 `[]`，数组它的形状，AoS 列表 `[len]`。
    pub fn shape(&self) -> Vec<usize> {
        match self {
            Node::Array(a) => a.shape.clone(),
            Node::List(l) => vec![l.len()],
            _ => Vec::new(),
        }
    }

    /// 是否是「叶子」——标量、字符串或数组。
    pub fn is_leaf(&self) -> bool {
        !matches!(self, Node::Map(_) | Node::List(_))
    }

    // ---- paths ---------------------------------------------------------

    /// 沿路径走；整数段索引列表；`aos_zero` 让**名字段**遇到列表时走第 0 个。
    pub fn walk(&self, path: &str, aos_zero: bool) -> Option<&Node> {
        let mut cur = self;
        for seg in path.split('/').filter(|s| !s.is_empty()) {
            cur = match cur {
                Node::Map(m) => m.get(seg)?,
                Node::List(l) => match seg.parse::<usize>() {
                    Ok(i) => l.get(i)?,
                    Err(_) if aos_zero => l.first()?.as_map()?.get(seg)?,
                    Err(_) => return None,
                },
                _ => return None,
            };
        }
        Some(cur)
    }

    /// `walk(path, false)`。
    pub fn get(&self, path: &str) -> Option<&Node> {
        self.walk(path, false)
    }

    pub fn get_mut(&mut self, path: &str) -> Option<&mut Node> {
        let mut cur = self;
        for seg in path.split('/').filter(|s| !s.is_empty()) {
            cur = match cur {
                Node::Map(m) => m.get_mut(seg)?,
                Node::List(l) => l.get_mut(seg.parse::<usize>().ok()?)?,
                _ => return None,
            };
        }
        Some(cur)
    }

    /// 放一个值到路径上，缺的中间层按段的样子造出来：整数段造列表（补到那个
    /// 长度，空位是空映射），名字段造映射。
    pub fn set(&mut self, path: &str, value: Node) -> Result<(), DocError> {
        let segs: Vec<&str> = path.split('/').filter(|s| !s.is_empty()).collect();
        if segs.is_empty() {
            *self = value;
            return Ok(());
        }
        let mut cur = self;
        for (n, seg) in segs.iter().enumerate() {
            let last = n + 1 == segs.len();
            match seg.parse::<usize>() {
                Ok(i) => {
                    if cur.is_null() {
                        *cur = Node::List(Vec::new());
                    }
                    let l = match cur {
                        Node::List(l) => l,
                        _ => return Err(DocError::Path(path.to_string())),
                    };
                    while l.len() <= i {
                        l.push(Node::Map(Map::new()));
                    }
                    if last {
                        l[i] = value;
                        return Ok(());
                    }
                    cur = &mut l[i];
                }
                Err(_) => {
                    if cur.is_null() {
                        *cur = Node::Map(Map::new());
                    }
                    let m = match cur {
                        Node::Map(m) => m,
                        _ => return Err(DocError::Path(path.to_string())),
                    };
                    if last {
                        m.insert(*seg, value);
                        return Ok(());
                    }
                    if !m.contains_key(seg) {
                        //: 下一段是数 → 列表；否则映射。
                        let next = if segs[n + 1].parse::<usize>().is_ok() {
                            Node::List(Vec::new())
                        } else {
                            Node::Map(Map::new())
                        };
                        m.insert(*seg, next);
                    }
                    cur = m.get_mut(seg).unwrap();
                }
            }
        }
        Ok(())
    }

    /// 删除一条路径上的值；返回被删的。
    pub fn remove(&mut self, path: &str) -> Option<Node> {
        let (parent, leaf) = match path.rsplit_once('/') {
            Some((p, l)) => (p, l),
            None => ("", path),
        };
        let node = if parent.is_empty() { self } else { self.get_mut(parent)? };
        match node {
            Node::Map(m) => m.remove(leaf),
            Node::List(l) => {
                let i = leaf.parse::<usize>().ok()?;
                if i < l.len() { Some(l.remove(i)) } else { None }
            }
            _ => None,
        }
    }

    /// 所有叶子的 `(路径, 节点)`，深度优先、插入序；AoS 元素以整数段出现。
    pub fn leaves(&self) -> Vec<(String, &Node)> {
        let mut out = Vec::new();
        self.collect_leaves(String::new(), &mut out);
        out
    }

    fn collect_leaves<'a>(&'a self, prefix: String, out: &mut Vec<(String, &'a Node)>) {
        match self {
            Node::Map(m) => {
                for (k, v) in m.iter() {
                    let p = if prefix.is_empty() { k.to_string() } else { format!("{prefix}/{k}") };
                    v.collect_leaves(p, out);
                }
            }
            Node::List(l) => {
                for (i, v) in l.iter().enumerate() {
                    let p = if prefix.is_empty() { i.to_string() } else { format!("{prefix}/{i}") };
                    v.collect_leaves(p, out);
                }
            }
            _ => out.push((prefix, self)),
        }
    }

    // ---- merge ---------------------------------------------------------

    /// 把 `other` 合进来。
    ///
    /// ★规则写死在一处，因为「多数据源合并」的全部语义就是它：映射逐键递归；
    /// 两边都是列表则逐索引递归（AoS 的时间片对时间片），长的那边多出来的接上；
    /// 叶子按 `policy`。类型不同（一边映射一边叶子）按 `policy` 整体处置。
    pub fn merge(&mut self, other: Node, policy: MergePolicy) {
        match (self, other) {
            (Node::Map(a), Node::Map(b)) => {
                for (k, v) in b.into_iter() {
                    match a.get_mut(&k) {
                        Some(slot) => slot.merge(v, policy),
                        None => {
                            a.insert(k, v);
                        }
                    }
                }
            }
            (Node::List(a), Node::List(b)) => {
                let mut it = b.into_iter();
                for slot in a.iter_mut() {
                    match it.next() {
                        Some(v) => slot.merge(v, policy),
                        None => break,
                    }
                }
                a.extend(it);
            }
            (slot, v) => {
                if policy == MergePolicy::Overwrite || slot.is_null() {
                    *slot = v;
                }
            }
        }
    }
}

/// 叶子冲突时谁赢。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MergePolicy {
    /// 后合进来的赢（缺省：`merge: [a, b]` 里 b 覆盖 a）。
    Overwrite,
    /// 已有的赢，只补缺。
    KeepExisting,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn set_builds_lists_and_maps_along_the_way() {
        let mut d = Node::map();
        d.set("time_slice/1/profiles_1d/psi", vec![1.0, 2.0].into()).unwrap();
        d.set("time_slice/0/time", 0.5.into()).unwrap();
        assert_eq!(d.get("time_slice/0/time").and_then(Node::as_f64), Some(0.5));
        assert_eq!(d.get("time_slice/1/profiles_1d/psi").map(Node::shape), Some(vec![2]));
        //: AoS-zero 走法：不带索引就是第 0 个
        assert_eq!(d.walk("time_slice/time", true).and_then(Node::as_f64), Some(0.5));
        assert!(d.walk("time_slice/time", false).is_none());
    }

    #[test]
    fn merge_is_recursive_over_maps_and_index_wise_over_lists() {
        let mut a = Node::map();
        a.set("x/p", 1.0.into()).unwrap();
        a.set("ts/0/a", 1.0.into()).unwrap();
        let mut b = Node::map();
        b.set("x/q", 2.0.into()).unwrap();
        b.set("x/p", 3.0.into()).unwrap();
        b.set("ts/0/b", 4.0.into()).unwrap();
        b.set("ts/1/b", 5.0.into()).unwrap();
        let mut keep = a.clone();
        keep.merge(b.clone(), MergePolicy::KeepExisting);
        assert_eq!(keep.get("x/p").and_then(Node::as_f64), Some(1.0));
        assert_eq!(keep.get("x/q").and_then(Node::as_f64), Some(2.0));
        a.merge(b, MergePolicy::Overwrite);
        assert_eq!(a.get("x/p").and_then(Node::as_f64), Some(3.0));
        assert_eq!(a.get("ts/0/a").and_then(Node::as_f64), Some(1.0));
        assert_eq!(a.get("ts/0/b").and_then(Node::as_f64), Some(4.0));
        assert_eq!(a.get("ts/1/b").and_then(Node::as_f64), Some(5.0));
    }

    #[test]
    fn transpose_reverses_shape_and_moves_elements() {
        let a = Array::f64(vec![2, 3], vec![0., 1., 2., 3., 4., 5.]).unwrap();
        let t = a.transposed();
        assert_eq!(t.shape, vec![3, 2]);
        assert_eq!(t.as_f64().unwrap(), &[0., 3., 1., 4., 2., 5.]);
        assert_eq!(t.transposed(), a);
    }

    #[test]
    fn leaves_walk_in_insertion_order() {
        let mut d = Node::map();
        d.set("b", 1.0.into()).unwrap();
        d.set("a/0/x", 2.0.into()).unwrap();
        let names: Vec<String> = d.leaves().into_iter().map(|(p, _)| p).collect();
        assert_eq!(names, vec!["b", "a/0/x"]);
    }
}
