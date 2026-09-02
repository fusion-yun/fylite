//! fyo 文档的约定 —— 语义键、`@type` ↔ IDS 名、fyo 布局与 IMAS DD 布局的互换、多 IDS 的束。
//!
//! ★★**两种布局，一棵树。** 「fyo 格式」是本仓的文档：JSON-LD 语义键（`@context`
//! `@id` `@type`）在前，正文用 IMAS DD 的键名，DD 没有名字的量带 `fylite:` 前缀
//! （`python/fylite/fyo.py`；`@type` 是 `fyo:<ids>`）。「IMAS DD 格式」是 imas-python /
//! imas-core 读写的那棵树：**只有** DD 的键，没有语义键，没有本地词——一个 IDS 一个
//! 顶层名，出现号（occurrence）跟在名后。两者的差别全在键上，所以互换是两个纯函数
//! （[`to_dd`] / [`from_dd`]），不是两套写法。
//!
//! ★`SEMANTIC_KEYS` 与 `python/fylite/engine/manifest.py` 逐字相同（含 SpData 的
//! `$` 别名）——那是「语义通道离开内容面」这条规则在两侧的同一份拼写。

use crate::document::{Array, ArrayData, Map, MergePolicy, Node};
use crate::ids_meta::{IdsMeta, Kind};

pub const FYO_PREFIX: &str = "https://fusion-yun.github.io/fyo/latest/";
pub const FYLITE_PREFIX: &str = "urn:fylite:";

/// JSON-LD 关键字与它们的 SpData `$` 别名。
pub const SEMANTIC_KEYS: [&str; 7] =
    ["@context", "@id", "@type", "$context", "$id", "$type", "$onto"];

/// 出现号（IMAS occurrence）在 fyo 文档里的键；缺席即 0。
pub const OCCURRENCE_KEY: &str = "fylite:occurrence";

pub fn is_semantic_key(k: &str) -> bool {
    SEMANTIC_KEYS.contains(&k)
}

/// 带前缀的本地词（`fylite:x`、`fyo:x`……）——DD 里没有的名字。
pub fn is_prefixed_key(k: &str) -> bool {
    k.contains(':')
}

/// 每份文档都带的 `@context`。
pub fn context() -> Node {
    let mut m = Map::new();
    m.insert("fyo", FYO_PREFIX.into());
    m.insert("fylite", FYLITE_PREFIX.into());
    Node::Map(m)
}

/// 一份空的 fyo 文档：`@context` / `@id` / `@type: fyo:<ids>`。
pub fn new_document(ids: &str, id: &str) -> Node {
    let mut m = Map::new();
    m.insert("@context", context());
    m.insert("@id", id.into());
    m.insert("@type", format!("fyo:{ids}").into());
    Node::Map(m)
}

/// 文档说的是哪个 IDS：`@type: fyo:equilibrium` → `equilibrium`；A-Box 的 `_ids` 也认。
pub fn ids_of(doc: &Node) -> Option<String> {
    let m = doc.as_map()?;
    if let Some(t) = m.get("@type").and_then(Node::as_str).or_else(|| m.get("$type").and_then(Node::as_str)) {
        if let Some(rest) = t.strip_prefix("fyo:") {
            let name = rest.split('/').next().unwrap_or(rest);
            if IdsMeta::get(name).is_some() {
                return Some(name.to_string());
            }
        }
    }
    if let Some(i) = m.get("_ids").and_then(Node::as_str) {
        return Some(i.to_string());
    }
    None
}

pub fn occurrence_of(doc: &Node) -> i64 {
    doc.get(OCCURRENCE_KEY).and_then(Node::as_i64).unwrap_or(0)
}

/// 去掉语义键与带前缀的本地键 —— IMAS DD 布局的那棵树。
///
/// 返回被丢掉的路径，好让调用方能说「这份文档里有 N 个 IMAS 不认的量没写出去」，
/// 而不是静默地少了。
pub fn to_dd(doc: &Node) -> (Node, Vec<String>) {
    let mut dropped = Vec::new();
    let out = strip(doc, String::new(), &mut dropped);
    (out, dropped)
}

fn strip(n: &Node, prefix: String, dropped: &mut Vec<String>) -> Node {
    match n {
        Node::Map(m) => {
            let mut out = Map::new();
            for (k, v) in m.iter() {
                let p = if prefix.is_empty() { k.to_string() } else { format!("{prefix}/{k}") };
                if is_semantic_key(k) || is_prefixed_key(k) || k == "_ids" {
                    dropped.push(p);
                    continue;
                }
                out.insert(k, strip(v, p, dropped));
            }
            Node::Map(out)
        }
        Node::List(l) => Node::List(l.iter().enumerate()
            .map(|(i, v)| strip(v, format!("{prefix}/{i}"), dropped)).collect()),
        other => other.clone(),
    }
}

/// 给一棵 DD 树套上 fyo 的语义键。
pub fn from_dd(ids: &str, tree: Node, id: &str, occurrence: i64) -> Node {
    let mut doc = new_document(ids, id);
    if occurrence != 0 {
        doc.as_map_mut().unwrap().insert(OCCURRENCE_KEY, Node::Int(occurrence));
    }
    if let Node::Map(m) = tree {
        let d = doc.as_map_mut().unwrap();
        for (k, v) in m.into_iter() {
            d.insert(k, v);
        }
    }
    doc
}

/// IMAS 侧的一个 IDS 的名字带出现号：`equilibrium`、`equilibrium_1`（imas-core 的链接名）。
pub fn ids_key(ids: &str, occurrence: i64) -> String {
    if occurrence == 0 { ids.to_string() } else { format!("{ids}_{occurrence}") }
}

/// `equilibrium_1` → (`equilibrium`, 1)；没有已知 IDS 前缀则原样、0。
pub fn split_ids_key(key: &str) -> (String, i64) {
    if let Some((base, n)) = key.rsplit_once('_') {
        if let Ok(occ) = n.parse::<i64>() {
            if IdsMeta::get(base).is_some() {
                return (base.to_string(), occ);
            }
        }
    }
    (key.to_string(), 0)
}

// --------------------------------------------------------------------------
// bundle
// --------------------------------------------------------------------------

/// 若干份 fyo 文档 —— 一个数据源（一个文件、一炮）通常不止一个 IDS。
#[derive(Debug, Clone, Default)]
pub struct Bundle {
    pub docs: Vec<Node>,
}

impl Bundle {
    pub fn new() -> Self {
        Bundle { docs: Vec::new() }
    }

    pub fn one(doc: Node) -> Self {
        Bundle { docs: vec![doc] }
    }

    pub fn is_empty(&self) -> bool {
        self.docs.is_empty()
    }

    pub fn push(&mut self, doc: Node) {
        self.docs.push(doc);
    }

    /// `(ids, occurrence)` 逐份。
    pub fn keys(&self) -> Vec<(String, i64)> {
        self.docs.iter().map(|d| (ids_of(d).unwrap_or_default(), occurrence_of(d))).collect()
    }

    pub fn get(&self, ids: &str) -> Option<&Node> {
        self.get_occ(ids, 0)
    }

    pub fn get_occ(&self, ids: &str, occurrence: i64) -> Option<&Node> {
        self.docs.iter().find(|d| ids_of(d).as_deref() == Some(ids) && occurrence_of(d) == occurrence)
    }

    pub fn get_mut(&mut self, ids: &str, occurrence: i64) -> Option<&mut Node> {
        self.docs.iter_mut().find(|d| ids_of(d).as_deref() == Some(ids) && occurrence_of(d) == occurrence)
    }

    /// 合并另一束：同一 `(ids, occurrence)` 的文档树对树合并，其余追加。
    pub fn merge(&mut self, other: Bundle, policy: MergePolicy) {
        for doc in other.docs {
            let key = (ids_of(&doc), occurrence_of(&doc));
            match key.0.as_deref().and_then(|i| self.get_mut(i, key.1)) {
                Some(slot) => slot.merge(doc, policy),
                None => self.docs.push(doc),
            }
        }
    }

    /// 束的容器形：`{ "<ids>[_<occ>]": <文档> }`。单份文档不套容器。
    pub fn to_node(&self) -> Node {
        if self.docs.len() == 1 {
            return self.docs[0].clone();
        }
        let mut m = Map::new();
        for (d, (ids, occ)) in self.docs.iter().zip(self.keys()) {
            let key = if ids.is_empty() { format!("document_{}", m.len()) } else { ids_key(&ids, occ) };
            m.insert(key, d.clone());
        }
        Node::Map(m)
    }

    /// 反过来：根上有 `@type` 是一份文档；否则每个值是一份（没有 `@type` 的按键名
    /// 当 DD 树读，键名给 IDS 与出现号）。
    pub fn from_node(n: Node) -> Bundle {
        let m = match n {
            Node::Map(m) => m,
            _ => return Bundle::new(),
        };
        if m.get("@type").is_some() || m.get("$type").is_some() || m.get("_ids").is_some() {
            return Bundle::one(Node::Map(m));
        }
        let mut b = Bundle::new();
        for (k, v) in m.into_iter() {
            if is_semantic_key(&k) {
                continue;
            }
            if let Node::Map(vm) = &v {
                if vm.get("@type").is_some() || vm.get("_ids").is_some() {
                    b.push(v);
                    continue;
                }
                let (ids, occ) = split_ids_key(&k);
                if IdsMeta::get(&ids).is_some() {
                    b.push(from_dd(&ids, v, &format!("fylite:{ids}/{k}"), occ));
                }
            }
        }
        b
    }
}

// --------------------------------------------------------------------------
// DD normalisation — what an IMAS writer needs before it can lay a tree out
// --------------------------------------------------------------------------

/// 一次归一化说了什么。
#[derive(Debug, Default, Clone)]
pub struct DdReport {
    /// 被丢掉的键（语义键、本地词、DD 里没有的路径）。
    pub dropped: Vec<String>,
    /// 被从标量提成一元数组的路径（DD 说它是一维）。
    pub promoted: Vec<String>,
    /// 合成出来的路径（根 `time`、`homogeneous_time`）。
    pub synthesized: Vec<String>,
}

/// 把一份 fyo 文档整理成 imas-python 会认的 DD 树。
///
/// * 去掉语义键与本地词；去掉 DD 不认的路径（**记在报告里**，不是静默）；
/// * DD 说一维而文档给了标量的，提成一元数组（`vacuum_toroidal_field/b0` 在本仓的
///   文档里是一个数）；
/// * 缺 `ids_properties/homogeneous_time` 的补上：有时间片就 1（齐次），否则 2（常量）；
/// * 齐次时间下缺根 `time` 的，从时间片的 `time` 合成。
pub fn dd_normalize(ids: &str, doc: &Node, meta: &IdsMeta) -> (Node, DdReport) {
    let (tree, dropped) = to_dd(doc);
    let mut report = DdReport { dropped, ..Default::default() };
    let mut out = Node::map();
    walk_dd(meta, &tree, String::new(), &mut out, &mut report);

    // homogeneous_time / time
    let has_ht = out.get("ids_properties/homogeneous_time").is_some();
    let dyn_aos: Vec<&crate::ids_meta::Entry> = meta.entries().iter()
        .filter(|e| e.kind == Kind::StructArray && !e.path.contains('/') && meta.has(&format!("{}/time", e.path)))
        .collect();
    let mut slice_times: Vec<f64> = Vec::new();
    for e in &dyn_aos {
        if let Some(Node::List(l)) = out.get(&e.path) {
            let ts: Vec<f64> = l.iter().filter_map(|s| s.get("time").and_then(Node::as_f64)).collect();
            if ts.len() == l.len() && !ts.is_empty() && slice_times.is_empty() {
                slice_times = ts;
            }
        }
    }
    let has_root_time = out.get("time").map(|t| t.to_f64_vec().map(|v| !v.is_empty()).unwrap_or(false)).unwrap_or(false);
    if !has_ht {
        let ht = if has_root_time || !slice_times.is_empty() { 1 } else { 2 };
        out.set("ids_properties/homogeneous_time", Node::Int(ht)).ok();
        report.synthesized.push("ids_properties/homogeneous_time".into());
    }
    let ht = out.get("ids_properties/homogeneous_time").and_then(Node::as_i64).unwrap_or(2);
    if ht == 1 && !has_root_time && !slice_times.is_empty() && meta.has("time") {
        out.set("time", Node::Array(Array::vec_f64(slice_times))).ok();
        report.synthesized.push("time".into());
    }
    //: `ids_properties` 要排在最前 —— 与 DD 一样的顺序，读的人才好找
    if let Node::Map(m) = &mut out {
        if let Some(props) = m.remove("ids_properties") {
            let mut fresh = Map::new();
            fresh.insert("ids_properties", props);
            for (k, v) in std::mem::take(m).into_iter() {
                fresh.insert(k, v);
            }
            *m = fresh;
        }
    }
    let _ = ids;
    (out, report)
}

fn walk_dd(meta: &IdsMeta, n: &Node, path: String, out: &mut Node, report: &mut DdReport) {
    if let Some(built) = build_dd(meta, n, &path, report) {
        *out = built;
    }
}

/// 自底向上造 DD 树：映射造映射、结构数组造列表、叶子按 DD 的种类与维数矫正。
fn build_dd(meta: &IdsMeta, n: &Node, path: &str, report: &mut DdReport) -> Option<Node> {
    let m = n.as_map()?;
    let mut out = Map::new();
    for (k, v) in m.iter() {
        let p = if path.is_empty() { k.to_string() } else { format!("{path}/{k}") };
        let entry = match meta.entry(&p) {
            Some(e) => e,
            None => { report.dropped.push(p); continue; }
        };
        match entry.kind {
            Kind::Structure => match build_dd(meta, v, &p, report) {
                Some(sub) => { out.insert(k, sub); }
                None => report.dropped.push(p),
            },
            Kind::StructArray => match v {
                Node::List(l) => {
                    let items: Vec<Node> = l.iter().map(|item|
                        build_dd(meta, item, &p, report).unwrap_or_else(Node::map)).collect();
                    out.insert(k, Node::List(items));
                }
                Node::Map(_) => {
                    //: a bare mapping where the DD has an array: element 0
                    let item = build_dd(meta, v, &p, report).unwrap_or_else(Node::map);
                    out.insert(k, Node::List(vec![item]));
                    report.promoted.push(p);
                }
                _ => report.dropped.push(p),
            },
            _ => match coerce_leaf(&entry, v) {
                Some((leaf, promoted)) => {
                    if promoted {
                        report.promoted.push(p.clone());
                    }
                    out.insert(k, leaf);
                }
                None => report.dropped.push(p),
            },
        }
    }
    Some(Node::Map(out))
}

fn coerce_leaf(entry: &crate::ids_meta::Entry, v: &Node) -> Option<(Node, bool)> {
    match entry.kind {
        Kind::Str => match (entry.ndim, v) {
            (0, Node::Str(_)) => Some((v.clone(), false)),
            (0, Node::Array(a)) if a.as_str().map(|s| s.len() == 1).unwrap_or(false) =>
                Some((Node::Str(a.as_str().unwrap()[0].clone()), false)),
            (1, Node::Array(a)) if a.as_str().is_some() => Some((v.clone(), false)),
            (1, Node::Str(s)) => Some((Node::Array(Array::str(vec![1], vec![s.clone()]).ok()?), true)),
            (1, Node::List(l)) if l.iter().all(|x| x.as_str().is_some()) => {
                let s: Vec<String> = l.iter().map(|x| x.as_str().unwrap().to_string()).collect();
                Some((Node::Array(Array::str(vec![s.len()], s).ok()?), false))
            }
            _ => None,
        },
        Kind::Int | Kind::Float | Kind::Complex => {
            if entry.ndim == 0 {
                let x = v.as_f64()?;
                return Some((if entry.kind == Kind::Int { Node::Int(x as i64) } else { Node::Float(x) }, false));
            }
            match v {
                Node::Array(a) if a.is_numeric() => {
                    if a.ndim() == entry.ndim {
                        Some((v.clone(), false))
                    } else if a.ndim() == 0 || (a.len() == 1 && entry.ndim == 1) {
                        Some((Node::Array(Array { shape: vec![1], data: a.data.clone() }), true))
                    } else {
                        None
                    }
                }
                Node::Int(_) | Node::Float(_) if entry.ndim == 1 => {
                    let x = v.as_f64()?;
                    let data = if entry.kind == Kind::Int { ArrayData::I64(vec![x as i64]) } else { ArrayData::F64(vec![x]) };
                    Some((Node::Array(Array { shape: vec![1], data }), true))
                }
                Node::List(l) if l.is_empty() => Some((Node::Array(Array { shape: vec![0; entry.ndim.max(1)],
                    data: if entry.kind == Kind::Int { ArrayData::I64(vec![]) } else { ArrayData::F64(vec![]) } }), false)),
                _ => None,
            }
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn to_dd_strips_semantic_and_prefixed_keys_and_says_so() {
        let mut d = new_document("equilibrium", "fylite:equilibrium/x");
        d.set("time_slice/0/global_quantities/ip", 1.0.into()).unwrap();
        d.set("fylite:limiter/r", vec![1.0].into()).unwrap();
        d.set("time_slice/0/fylite:extra", 2.0.into()).unwrap();
        let (dd, dropped) = to_dd(&d);
        assert!(dd.get("@type").is_none() && dd.get("fylite:limiter").is_none());
        assert_eq!(dd.get("time_slice/0/global_quantities/ip").and_then(Node::as_f64), Some(1.0));
        assert_eq!(dropped, vec!["@context", "@id", "@type", "time_slice/0/fylite:extra", "fylite:limiter"]);
        assert_eq!(ids_of(&d).as_deref(), Some("equilibrium"));
        assert_eq!(ids_of(&from_dd("wall", dd, "x", 2)).as_deref(), Some("wall"));
        assert_eq!(split_ids_key("equilibrium_1"), ("equilibrium".to_string(), 1));
        assert_eq!(split_ids_key("core_profiles"), ("core_profiles".to_string(), 0));
    }

    #[test]
    fn dd_normalize_promotes_b0_and_synthesizes_time() {
        let meta = IdsMeta::get("equilibrium").unwrap();
        let mut d = new_document("equilibrium", "x");
        d.set("vacuum_toroidal_field/b0", 1.8.into()).unwrap();
        d.set("vacuum_toroidal_field/r0", 1.75.into()).unwrap();
        d.set("time_slice/0/time", 4.8.into()).unwrap();
        d.set("time_slice/0/global_quantities/ip", 4e5.into()).unwrap();
        d.set("time_slice/0/profiles_2d/0/psi", Node::Array(Array::f64(vec![2, 2], vec![1., 2., 3., 4.]).unwrap())).unwrap();
        d.set("time_slice/0/profiles_2d/0/grid_type/name", "rectangular".into()).unwrap();
        d.set("fylite:limiter/r", vec![1.0].into()).unwrap();
        d.set("time_slice/0/not_in_dd", 1.0.into()).unwrap();
        let (dd, rep) = dd_normalize("equilibrium", &d, &meta);
        assert_eq!(dd.get("vacuum_toroidal_field/b0").map(Node::shape), Some(vec![1]));
        assert_eq!(dd.get("time").and_then(Node::to_f64_vec), Some(vec![4.8]));
        assert_eq!(dd.get("ids_properties/homogeneous_time").and_then(Node::as_i64), Some(1));
        assert!(rep.promoted.contains(&"vacuum_toroidal_field/b0".to_string()));
        //: dropped DD-side paths are reported without the element index
        assert!(rep.dropped.contains(&"time_slice/not_in_dd".to_string()), "{:?}", rep.dropped);
        assert!(rep.dropped.contains(&"fylite:limiter".to_string()));
        let keys: Vec<&str> = dd.as_map().unwrap().keys().collect();
        assert_eq!(keys[0], "ids_properties");
        assert_eq!(dd.get("time_slice/0/profiles_2d/0/grid_type/name").and_then(Node::as_str), Some("rectangular"));
    }

    #[test]
    fn a_bundle_round_trips_through_its_container_node() {
        let mut b = Bundle::new();
        let mut eq = new_document("equilibrium", "e");
        eq.set("time", vec![1.0].into()).unwrap();
        b.push(eq);
        b.push(new_document("wall", "w"));
        let n = b.to_node();
        let again = Bundle::from_node(n);
        assert_eq!(again.keys(), vec![("equilibrium".to_string(), 0), ("wall".to_string(), 0)]);
        //: a plain DD container is recognised by its keys
        let mut m = Map::new();
        m.insert("tf", Node::map());
        m.insert("tf_2", Node::map());
        let c = Bundle::from_node(Node::Map(m));
        assert_eq!(c.keys(), vec![("tf".to_string(), 0), ("tf".to_string(), 2)]);
    }
}
