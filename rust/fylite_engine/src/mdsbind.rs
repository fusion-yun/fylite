//! MDSplus 绑定表 → fyo 文档 —— **只读**，经 `mdsip` 那个由构造保证只读的客户端。
//!
//! ★★两份输入、一套分解、一个读法：
//!
//! * **扁平表** `fylite/mds-bind/1`（`app/assets/mds-bind.json`，由
//!   `tools/abox-mds-bind.py` 从 A-Box 分解出来）：每行 `{ids, path, source, verb, node,
//!   subscript, subscript_inside, value, scale}`——正是 `mdsip::Client::read` 的实参。
//! * **A-Box 绑定文档**（fydoc / fydata 的 `$source` + `$link`，JSON-LD）：叶子是
//!   `{"$link": "efit_east:DATA(\\X[0,*,{time_slice}])*1000"}`。这里把
//!   `abox-mds-bind.py::decompose` 逐条移植过来（剥法由外到内：倍率、下标、动词、
//!   动词括号里的下标），分解不了的（下标读另一个节点、未知动词）**列出来而不是猜**。
//!
//! 参数（`{shot}` / `{time_slice}` …）在读时代入；`{shot}` 决定开哪一炮，其余代入下标。
//! 一个源 = 一棵树（`tree_name`）；主机与端口来自源的 URI（`mdsplus://host:port/...`）
//! 或调用方给的覆盖——绑定表里的 `127.0.0.1` 是 A-Box 生成时的占位。
//!
//! **时间选择**（[`TimeSel`]：一个点、一个窗 `[t0, t1]`、一列点）在这一层落成整数：先读
//! 节点的时基（`dim_of`，按节点缓存），在时基上查出下标，再以 [`Index::Range`] /
//! [`Index::At`] 让服务端切片——整条信号不过网。`time_slice/*/…` 的绑定按 IDS 根
//! `time` 上选出的下标展开成若干时间片。见 [`resolve`] 与 [`read_one`]。

use crate::document::{Array, ArrayData, Node};
use crate::fyodoc::{self, Bundle};
use crate::mdsip::{Client, Index, MdsipError, Transport, Verb};
use std::collections::BTreeMap;
use std::sync::Arc;

/// 一条绑定：`[verb](node)[subscript]`，可带倍率；或一个常量。
#[derive(Debug, Clone, PartialEq)]
pub struct Binding {
    pub ids: String,
    /// 文档路径，带显式索引（`time_slice/0/boundary/outline/r`）；模板段 `*` 表示
    /// 「每个时间片」——由 `{time_slice}` 参数展开。
    pub path: String,
    pub source: String,
    pub verb: Option<Verb>,
    pub node: Option<String>,
    pub subscript: Vec<Item>,
    pub inside: bool,
    pub value: Option<f64>,
    pub scale: Option<f64>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Item {
    At(i64),
    All,
    Slot(String),
}

#[derive(Debug, Clone, Default)]
pub struct Source {
    pub tree: String,
    pub uri: String,
}

/// 一张读进来的绑定表。
#[derive(Debug, Clone, Default)]
pub struct BindTable {
    pub sources: BTreeMap<String, Source>,
    pub bindings: Vec<Binding>,
    /// 分解不了的：`(ids, path, link, why)`。
    pub unsupported: Vec<(String, String, String, String)>,
}

/// 从 URI 里取 `tree_name`（缺席用别名）与主机、端口。
pub fn parse_uri(uri: &str) -> (Option<String>, Option<String>, Option<u16>) {
    let tree = uri.split("tree_name=").nth(1).map(|t| t.split(['&', '#']).next().unwrap_or(t).to_lowercase());
    let rest = uri.strip_prefix("mdsplus://").unwrap_or(uri);
    let hostport = rest.split(['/', '?']).next().unwrap_or("");
    let (host, port) = match hostport.rsplit_once(':') {
        Some((h, p)) => (h.to_string(), p.parse::<u16>().ok()),
        None => (hostport.to_string(), None),
    };
    (tree, if host.is_empty() { None } else { Some(host) }, port)
}

// --------------------------------------------------------------------------
// the flat table
// --------------------------------------------------------------------------

fn item_of(n: &Node) -> Option<Item> {
    if let Some(m) = n.as_map() {
        if let Some(i) = m.get("int").and_then(Node::as_i64) { return Some(Item::At(i)); }
        if m.get("all").is_some() { return Some(Item::All); }
        if let Some(s) = m.get("slot").and_then(Node::as_str) { return Some(Item::Slot(s.to_string())); }
        return None;
    }
    if let Some(i) = n.as_i64() { return Some(Item::At(i)); }
    match n.as_str() {
        Some("*") => Some(Item::All),
        Some(s) if s.starts_with('{') && s.ends_with('}') => Some(Item::Slot(s[1..s.len() - 1].to_string())),
        Some(s) => s.parse::<i64>().ok().map(Item::At),
        None => None,
    }
}

/// 读 `fylite/mds-bind/1`。
pub fn parse_table(doc: &Node) -> Result<BindTable, String> {
    let m = doc.as_map().ok_or("binding table is not a mapping")?;
    if m.get("$schema").and_then(Node::as_str) != Some("fylite/mds-bind/1") {
        return Err("not a `fylite/mds-bind/1` table".into());
    }
    let mut t = BindTable::default();
    if let Some(src) = m.get("sources").and_then(Node::as_map) {
        for (alias, v) in src.iter() {
            t.sources.insert(alias.to_string(), Source {
                tree: v.get("tree").and_then(Node::as_str).unwrap_or(alias).to_lowercase(),
                uri: v.get("uri").and_then(Node::as_str).unwrap_or("").to_string(),
            });
        }
    }
    for b in m.get("bindings").and_then(Node::as_list).unwrap_or(&[]) {
        let bm = match b.as_map() { Some(x) => x, None => continue };
        let s = |k: &str| bm.get(k).and_then(Node::as_str).map(str::to_string);
        let verb = match s("verb").as_deref() {
            Some("data") => Some(Verb::Data),
            Some("dim_of") => Some(Verb::DimOf),
            Some("raw") => Some(Verb::Raw),
            Some("const") => None,
            other => { t.unsupported.push((s("ids").unwrap_or_default(), s("path").unwrap_or_default(),
                                           s("link").unwrap_or_default(), format!("verb {other:?}"))); continue; }
        };
        let subscript: Vec<Item> = match bm.get("subscript") {
            Some(Node::List(l)) => l.iter().filter_map(item_of).collect(),
            Some(Node::Array(a)) => a.to_f64().unwrap_or_default().iter().map(|&x| Item::At(x as i64)).collect(),
            _ => Vec::new(),
        };
        t.bindings.push(Binding {
            ids: s("ids").unwrap_or_default(),
            path: s("path").unwrap_or_default(),
            source: s("source").unwrap_or_default(),
            verb,
            node: s("node"),
            subscript,
            inside: bm.get("subscript_inside").map(|v| v.as_i64() == Some(1) || matches!(v, Node::Bool(true))).unwrap_or(false),
            value: bm.get("value").and_then(Node::as_f64),
            scale: bm.get("scale").and_then(Node::as_f64),
        });
    }
    for u in m.get("unsupported").and_then(Node::as_list).unwrap_or(&[]) {
        if let Some(um) = u.as_map() {
            let s = |k: &str| um.get(k).and_then(Node::as_str).unwrap_or("").to_string();
            t.unsupported.push((s("ids"), s("path"), s("link"), s("why")));
        }
    }
    Ok(t)
}

// --------------------------------------------------------------------------
// `$link` decomposition (the port of abox-mds-bind.py::decompose)
// --------------------------------------------------------------------------

fn is_number(s: &str) -> bool {
    !s.is_empty() && s.parse::<f64>().is_ok() && !s.contains(['\\', '(', '[']) && s.chars().all(|c| c.is_ascii_digit() || matches!(c, '-' | '+' | '.' | 'e' | 'E'))
}

fn parse_items(text: &str) -> Option<Vec<Item>> {
    let mut out = Vec::new();
    for raw in text.split(',') {
        let r = raw.trim();
        if r == "*" {
            out.push(Item::All);
        } else if let Ok(i) = r.parse::<i64>() {
            out.push(Item::At(i));
        } else if r.starts_with('{') && r.ends_with('}') && r.len() > 2
            && r[1..r.len() - 1].chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
            out.push(Item::Slot(r[1..r.len() - 1].to_string()));
        } else {
            return None;
        }
    }
    Some(out)
}

/// `\X[0, *]` → (`\X`, items)；没有尾随下标给 `None`；有但不能猜的给 `Err(why)`。
fn peel_subscript(text: &str) -> Result<(String, Option<Vec<Item>>), String> {
    let t = text.trim();
    if !t.ends_with(']') {
        return Ok((t.to_string(), None));
    }
    let open = match t.rfind('[') {
        Some(i) => i,
        None => return Err("unbalanced subscript".into()),
    };
    let inner = &t[open + 1..t.len() - 1];
    if inner.contains('[') || inner.contains(']') {
        return Err("subscript bound reads another node (NBDRY-style) — needs two round trips".into());
    }
    let head = t[..open].trim();
    if head.contains(']') {
        return Err("subscript bound reads another node (NBDRY-style) — needs two round trips".into());
    }
    match parse_items(inner) {
        Some(items) => Ok((head.to_string(), Some(items))),
        None => Err("subscript bound is not an integer — it reads another node, so it needs two round trips".into()),
    }
}

/// [`decompose`] 的结果：`(动词, 节点, 下标, 下标在动词括号内, 常量, 倍率)`。
pub type Decomposed = (Option<Verb>, Option<String>, Vec<Item>, bool, Option<f64>, Option<f64>);

/// 分解一条 `$link` 的表达式部分（别名已剥掉）。
pub fn decompose(expr: &str) -> Result<Decomposed, String> {
    let mut e = expr.trim().to_string();
    if is_number(&e) {
        return Ok((None, None, Vec::new(), false, e.parse::<f64>().ok(), None));
    }
    //: scale: a trailing `* <number>`
    let mut scale = None;
    if let Some(star) = e.rfind('*') {
        let tail = e[star + 1..].trim();
        let head = e[..star].trim();
        if is_number(tail) && !head.is_empty() && !head.ends_with('[') && !head.ends_with(',') {
            scale = tail.parse::<f64>().ok();
            e = head.to_string();
        }
    }
    let (mut e, mut sub) = peel_subscript(&e)?;
    let mut verb = Verb::Raw;
    let mut inside = false;
    if let Some(open) = e.find('(') {
        if e.ends_with(')') {
            let name = e[..open].trim().to_ascii_uppercase();
            let inner = e[open + 1..e.len() - 1].trim().to_string();
            verb = match name.as_str() {
                "DATA" => Verb::Data,
                "DIM_OF" => Verb::DimOf,
                other => return Err(format!("unknown verb {other:?} (only DATA / DIM_OF)")),
            };
            let (n, inner_sub) = peel_subscript(&inner)?;
            e = n;
            if let Some(items) = inner_sub {
                if sub.is_some() {
                    return Err("subscripted both inside and outside the verb".into());
                }
                sub = Some(items);
                inside = true;
            }
        }
    }
    if e.contains('[') || e.contains(']') {
        return Err("nested or unbalanced subscript".into());
    }
    let node = e.trim().to_string();
    if !crate::mdsip::is_node_path(&node) {
        return Err(format!("not a node path by the kernel's rule: {node:?}"));
    }
    Ok((Some(verb), Some(node), sub.unwrap_or_default(), inside, None, scale))
}

/// 从一份 A-Box 绑定文档（JSON-LD：`$source` + `$link`）建表。`ids` 缺省取
/// `_ids` / `@type`，再缺省取 `fallback_ids`。
pub fn table_from_abox(doc: &Node, fallback_ids: &str) -> Result<BindTable, String> {
    let m = doc.as_map().ok_or("binding document is not a mapping")?;
    let ids = fyodoc::ids_of(doc).unwrap_or_else(|| fallback_ids.to_string());
    let mut t = BindTable::default();
    if let Some(src) = m.get("$source").and_then(Node::as_map) {
        for (alias, v) in src.iter() {
            let uri = v.as_str().unwrap_or("").to_string();
            let (tree, _, _) = parse_uri(&uri);
            t.sources.insert(alias.to_string(), Source { tree: tree.unwrap_or_else(|| alias.to_lowercase()), uri });
        }
    }
    let mut leaves: Vec<(String, String)> = Vec::new();
    walk_links(doc, &mut Vec::new(), &mut leaves);
    for (path, link) in leaves {
        let (alias, expr) = match link.split_once(':') {
            Some((h, r)) if t.sources.contains_key(h) => (h.to_string(), r.to_string()),
            _ => { t.unsupported.push((ids.clone(), path, link, "no `$source` alias on the link".into())); continue; }
        };
        match decompose(&expr) {
            Ok((verb, node, subscript, inside, value, scale)) => t.bindings.push(Binding {
                ids: ids.clone(), path, source: alias, verb, node, subscript, inside, value, scale }),
            Err(why) => t.unsupported.push((ids.clone(), path, link, why)),
        }
    }
    Ok(t)
}

fn walk_links(n: &Node, path: &mut Vec<String>, out: &mut Vec<(String, String)>) {
    match n {
        Node::Map(m) => {
            if let Some(l) = m.get("$link").and_then(Node::as_str) {
                out.push((path.join("/"), l.to_string()));
                return;
            }
            for (k, v) in m.iter() {
                if k.starts_with('@') || k.starts_with('$') || k.starts_with("dcterms:") || k.starts_with("prov:")
                    || k.starts_with("rdfs:") || k == "provenance" || k == "_ids" {
                    continue;
                }
                path.push(k.to_string());
                walk_links(v, path, out);
                path.pop();
            }
        }
        Node::List(l) => {
            for (i, v) in l.iter().enumerate() {
                let seg = v.as_map().and_then(|m| m.get("$id")).and_then(|x| x.as_str().map(str::to_string).or_else(|| x.as_i64().map(|i| i.to_string())))
                    .unwrap_or_else(|| i.to_string());
                path.push(seg);
                walk_links(v, path, out);
                path.pop();
            }
        }
        _ => {}
    }
}

// --------------------------------------------------------------------------
// resolving
// --------------------------------------------------------------------------

/// 时间选择 —— 一个点、一个窗、一列点；单位随信号的时基（EAST 是秒）。
///
/// ★★为什么在这一层而不在 `mdsip`：客户端只认「动词 + 节点 + 整数」，一个时间窗要先
/// 在时基上查成下标才是整数——查表这一步需要读一次时基，这是绑定层的事。查出来的
/// 下标以 [`Index::Range`] / [`Index::At`] 发出去，切片在服务端做，整条信号不过网。
#[derive(Debug, Clone, PartialEq)]
pub enum TimeSel {
    /// 一个时刻：取时基上最近的一个样本。
    Point(f64),
    /// 一个闭区间 `[t0, t1]`。
    Window { t0: f64, t1: f64 },
    /// 若干时刻，各取最近的样本，按给定的次序。
    Points(Vec<f64>),
}

impl TimeSel {
    /// 文本形：`4.5`、`4:5`、`4,4.5,5`。
    pub fn parse(s: &str) -> Result<TimeSel, String> {
        let t = s.trim();
        if let Some((a, b)) = t.split_once(':') {
            let t0 = a.trim().parse::<f64>().map_err(|_| format!("time window {t:?}: bad start"))?;
            let t1 = b.trim().parse::<f64>().map_err(|_| format!("time window {t:?}: bad stop"))?;
            return Ok(TimeSel::Window { t0, t1 });
        }
        if t.contains(',') {
            let pts = t.split(',').map(|x| x.trim().parse::<f64>().map_err(|_| format!("time list {t:?}: {x:?} is not a number")))
                .collect::<Result<Vec<_>, _>>()?;
            return Ok(TimeSel::Points(pts));
        }
        t.parse::<f64>().map(TimeSel::Point).map_err(|_| format!("time {t:?}: a number, `t0:t1` or `t1,t2,…`"))
    }

    /// 节点形（装配文档的 `params.time`）：数 → 点；`[t0, t1]` / `{start, stop}` → 窗；
    /// 三个及以上的列表 → 点列；文本按 [`TimeSel::parse`]。
    pub fn from_node(n: &Node) -> Result<TimeSel, String> {
        if let Some(s) = n.as_str() {
            return TimeSel::parse(s);
        }
        if let Some(m) = n.as_map() {
            let g = |k: &str| m.get(k).and_then(Node::as_f64);
            return match (g("start").or_else(|| g("t0")), g("stop").or_else(|| g("t1")).or_else(|| g("end"))) {
                (Some(t0), Some(t1)) => Ok(TimeSel::Window { t0, t1 }),
                _ => Err("time as a mapping wants `start` and `stop`".into()),
            };
        }
        if let Some(v) = n.to_f64_vec() {
            return match v.len() {
                0 => Err("empty time list".into()),
                1 => Ok(TimeSel::Point(v[0])),
                2 => Ok(TimeSel::Window { t0: v[0], t1: v[1] }),
                _ => Ok(TimeSel::Points(v)),
            };
        }
        Err("time: a number, [t0, t1], a list of times, or `t0:t1` text".into())
    }

    pub fn to_node(&self) -> Node {
        match self {
            TimeSel::Point(t) => Node::Float(*t),
            TimeSel::Window { t0, t1 } => {
                let mut m = Node::map();
                m.set("start", Node::Float(*t0)).ok();
                m.set("stop", Node::Float(*t1)).ok();
                m
            }
            TimeSel::Points(p) => Node::Array(Array::vec_f64(p.clone())),
        }
    }
}

/// 参数：`shot`、代入下标的槽（`time_slice` 等）、时间选择与抽稀上限。
#[derive(Debug, Clone, Default)]
pub struct Params {
    pub shot: i64,
    pub slots: BTreeMap<String, i64>,
    /// 时间选择；`None` = 整条信号。
    pub time: Option<TimeSel>,
    /// 窗内最多取多少个样本（服务端按步长抽稀）；`None` = 全取。
    pub max_points: Option<usize>,
}

/// 在一条时基上选出的下标（两端都含）。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Picked {
    Range { start: usize, stop: usize, step: usize },
    List(Vec<usize>),
}

impl Picked {
    pub fn indices(&self) -> Vec<usize> {
        match self {
            Picked::Range { start, stop, step } => (*start..=*stop).step_by(*step).collect(),
            Picked::List(l) => l.clone(),
        }
    }
}

fn nearest_sorted(base: &[f64], t: f64) -> usize {
    let i = base.partition_point(|&x| x < t);
    if i == 0 {
        0
    } else if i >= base.len() {
        base.len() - 1
    } else if (t - base[i - 1]).abs() <= (base[i] - t).abs() {
        i - 1
    } else {
        i
    }
}

fn nearest_any(base: &[f64], t: f64) -> usize {
    let mut best = 0;
    let mut bd = f64::INFINITY;
    for (i, &x) in base.iter().enumerate() {
        let d = (x - t).abs();
        if d < bd {
            bd = d;
            best = i;
        }
    }
    best
}

fn thin(n: usize, max_points: Option<usize>) -> usize {
    match max_points {
        Some(m) if m > 0 && n > m => n.div_ceil(m),
        _ => 1,
    }
}

/// 按时间选择在时基上取下标。★不越界、不外推：点取最近的样本，窗取落在 `[t0, t1]`
/// 里的样本；窗里没有样本是错误而不是空数组。时基不单调时退化成逐点比较。
pub fn pick(base: &[f64], sel: &TimeSel, max_points: Option<usize>) -> Result<Picked, String> {
    if base.is_empty() {
        return Err("empty time base".into());
    }
    let sorted = base.windows(2).all(|w| w[0] <= w[1]);
    let nearest = |t: f64| if sorted { nearest_sorted(base, t) } else { nearest_any(base, t) };
    match sel {
        TimeSel::Point(t) => Ok(Picked::List(vec![nearest(*t)])),
        TimeSel::Points(ts) => Ok(Picked::List(ts.iter().map(|&t| nearest(t)).collect())),
        TimeSel::Window { t0, t1 } => {
            let (t0, t1) = if t0 <= t1 { (*t0, *t1) } else { (*t1, *t0) };
            if sorted {
                let i0 = base.partition_point(|&x| x < t0);
                let i1 = base.partition_point(|&x| x <= t1);
                if i1 <= i0 {
                    return Err(format!("no samples in [{t0}, {t1}] (the time base spans [{}, {}])", base[0], base[base.len() - 1]));
                }
                Ok(Picked::Range { start: i0, stop: i1 - 1, step: thin(i1 - i0, max_points) })
            } else {
                let all: Vec<usize> = base.iter().enumerate().filter(|(_, &x)| x >= t0 && x <= t1).map(|(i, _)| i).collect();
                if all.is_empty() {
                    return Err(format!("no samples in [{t0}, {t1}]"));
                }
                let step = thin(all.len(), max_points);
                Ok(Picked::List(all.into_iter().step_by(step).collect()))
            }
        }
    }
}

/// 一次解析的结果：文档束 + 逐条的失败 + 说明。
#[derive(Debug, Default)]
pub struct Resolved {
    pub bundle: Bundle,
    pub failures: Vec<(String, String, String)>,
    /// 不是失败、但读的人该知道的：哪条没开窗、时基从哪来。
    pub notes: Vec<String>,
    pub read: usize,
}

/// 一条会话能做的两件事——读一个「动词 + 节点 + 整数下标」，取一条时基。
///
/// ★对象安全，好让装配层把不同传输的会话装进一个表里（`Box<dyn Reader>`）；
/// 所有开窗、代槽、倍率都在这个 trait 之上做，会话本身只认整数。
pub trait Reader {
    fn read_items(&mut self, tree: &str, shot: i64, verb: Verb, node: &str, idx: &[Index], inside: bool) -> Result<Node, String>;
    /// `dim_of(node, axis)`，按 (树, 炮, 节点, 轴) 缓存——一炮里同一个节点的时基只过网一次。
    fn time_base(&mut self, tree: &str, shot: i64, node: &str, axis: i64) -> Result<Arc<Vec<f64>>, String>;
}

/// 一个源 = 一条已登录的连接（树在读时打开），带时基缓存。
pub struct Session<T: Transport> {
    pub client: Client<T>,
    open_tree: Option<(String, i64)>,
    bases: BTreeMap<(String, i64, String, i64), Arc<Vec<f64>>>,
}

impl<T: Transport> Session<T> {
    pub fn new(client: Client<T>) -> Self {
        Session { client, open_tree: None, bases: BTreeMap::new() }
    }

    fn ensure_tree(&mut self, tree: &str, shot: i64) -> Result<(), MdsipError> {
        if self.open_tree.as_ref().map(|(t, s)| t == tree && *s == shot).unwrap_or(false) {
            return Ok(());
        }
        self.client.open_tree(tree, shot)?;
        self.open_tree = Some((tree.to_string(), shot));
        Ok(())
    }
}

impl<T: Transport> Reader for Session<T> {
    fn read_items(&mut self, tree: &str, shot: i64, verb: Verb, node: &str, idx: &[Index], inside: bool) -> Result<Node, String> {
        self.ensure_tree(tree, shot).map_err(|e| e.to_string())?;
        let ans = self.client.read(verb, node, idx, inside).map_err(|e| e.to_string())?;
        Ok(answer_to_node(&ans, None))
    }

    fn time_base(&mut self, tree: &str, shot: i64, node: &str, axis: i64) -> Result<Arc<Vec<f64>>, String> {
        let key = (tree.to_string(), shot, node.to_string(), axis);
        if let Some(b) = self.bases.get(&key) {
            return Ok(b.clone());
        }
        self.ensure_tree(tree, shot).map_err(|e| e.to_string())?;
        let ans = self.client.get_dim_of_axis(node, axis).map_err(|e| e.to_string())?;
        let v = ans.data.to_f64().ok_or_else(|| format!("dim_of({node},{axis}) is not numeric"))?;
        let b = Arc::new(v);
        self.bases.insert(key, b.clone());
        Ok(b)
    }
}

impl Reader for Box<dyn Reader> {
    fn read_items(&mut self, tree: &str, shot: i64, verb: Verb, node: &str, idx: &[Index], inside: bool) -> Result<Node, String> {
        (**self).read_items(tree, shot, verb, node, idx, inside)
    }
    fn time_base(&mut self, tree: &str, shot: i64, node: &str, axis: i64) -> Result<Arc<Vec<f64>>, String> {
        (**self).time_base(tree, shot, node, axis)
    }
}

/// 一个答复 → 文档节点（标量或按行主序形状的数组），可带倍率。
pub fn answer_to_node(ans: &crate::mdsip::Answer, scale: Option<f64>) -> Node {
    let mut vals = match ans.data.to_f64() {
        Some(v) => v,
        None => return Node::Str(crate::mdsip::text_of(ans)),
    };
    if let Some(k) = scale {
        vals.iter_mut().for_each(|x| *x *= k);
    }
    let shape = ans.shape_row_major();
    if vals.len() == 1 && shape.len() <= 1 {
        return Node::Float(vals[0]);
    }
    let shape = if shape.iter().product::<usize>() == vals.len() { shape } else { vec![vals.len()] };
    Node::Array(Array { shape, data: ArrayData::F64(vals) })
}

/// 数值节点乘倍率。
fn scaled(n: Node, k: Option<f64>) -> Node {
    let k = match k { Some(k) => k, None => return n };
    match n {
        Node::Float(x) => Node::Float(x * k),
        Node::Int(i) => Node::Float(i as f64 * k),
        Node::Array(a) => match a.to_f64() {
            Some(mut v) => {
                v.iter_mut().for_each(|x| *x *= k);
                Node::Array(Array { shape: a.shape, data: ArrayData::F64(v) })
            }
            None => Node::Array(a),
        },
        other => other,
    }
}

/// 标量也成一维数组：开窗后的量总是「随时间的数组」，一个点是长度 1。
fn as_array(n: Node) -> Node {
    match n {
        Node::Float(x) => Node::Array(Array::vec_f64(vec![x])),
        Node::Int(i) => Node::Array(Array::vec_f64(vec![i as f64])),
        other => other,
    }
}

/// 逐点读回来的几份叠成一份：标量 → 一维；同形数值数组 → 前面加一维；其余留作列表。
fn stack(parts: Vec<Node>) -> Node {
    if parts.iter().all(|p| !matches!(p, Node::Array(a) if a.len() != 1) && p.as_f64().is_some()) {
        return Node::Array(Array::vec_f64(parts.iter().map(|p| p.as_f64().unwrap()).collect()));
    }
    if let Some(first) = parts.first().and_then(Node::as_array) {
        let shape = first.shape.clone();
        if parts.iter().all(|p| p.as_array().map(|a| a.shape == shape && a.is_numeric()).unwrap_or(false)) {
            let mut data = Vec::with_capacity(parts.len() * first.len());
            for p in &parts {
                data.extend(p.as_array().unwrap().to_f64().unwrap());
            }
            let mut s = vec![parts.len()];
            s.extend(shape);
            return Node::Array(Array { shape: s, data: ArrayData::F64(data) });
        }
    }
    Node::List(parts)
}

pub fn indices(items: &[Item], params: &Params) -> Result<Vec<Index>, String> {
    items.iter().map(|it| match it {
        Item::At(i) => Ok(Index::At(*i)),
        Item::All => Ok(Index::All),
        Item::Slot(s) => params.slots.get(s).map(|v| Index::At(*v)).ok_or_else(|| format!("no value for {{{s}}}")),
    }).collect()
}

fn subscript_text(items: &[Item]) -> String {
    if items.is_empty() {
        return String::new();
    }
    let parts: Vec<String> = items.iter().map(|i| match i {
        Item::At(x) => x.to_string(),
        Item::All => "*".into(),
        Item::Slot(s) => format!("{{{s}}}"),
    }).collect();
    format!("[{}]", parts.join(","))
}

/// 一条绑定的时间轴在下标的哪一位：没有下标 → 第 0 轴（一维信号）；恰有一个 `*` 且
/// 没有 `{time_slice}` → 那一位（EFIT 的 `\X[i,*]`）；其余 → 不开窗（`{time_slice}`
/// 由 [`resolve`] 展开成时间片）。
fn time_axis(items: &[Item]) -> Option<usize> {
    if items.is_empty() {
        return Some(0);
    }
    if items.iter().any(|i| matches!(i, Item::Slot(s) if s == "time_slice")) {
        return None;
    }
    let alls: Vec<usize> = items.iter().enumerate().filter(|(_, i)| **i == Item::All).map(|(k, _)| k).collect();
    if alls.len() == 1 { Some(alls[0]) } else { None }
}

/// 读一条已分解的绑定；`params.time` 给了就在时基上查下标、按下标切片。
///
/// ★两条捷径：`DIM_OF(节点)`（没有下标）就是时基本身，从缓存里切，不再过网；
/// 一个点或一列点逐点以 [`Index::At`] 读，叠成一维——一个时刻的量也是长度 1 的数组，
/// 与 DD 里「随时间的数组」同形。
#[allow(clippy::too_many_arguments)]
pub fn read_one<R: Reader + ?Sized>(r: &mut R, tree: &str, shot: i64, verb: Verb, node: &str, items: &[Item], inside: bool,
                                    scale: Option<f64>, params: &Params, notes: &mut Vec<String>) -> Result<Node, String> {
    let mut idx = indices(items, params)?;
    let (sel, axis) = match (&params.time, time_axis(items)) {
        (Some(sel), Some(axis)) => (sel, axis),
        (Some(_), None) => {
            notes.push(format!("{node}{}: read whole — the subscript has no single time axis", subscript_text(items)));
            return r.read_items(tree, shot, verb, node, &idx, inside).map(|n| scaled(n, scale));
        }
        (None, _) => return r.read_items(tree, shot, verb, node, &idx, inside).map(|n| scaled(n, scale)),
    };
    let base = r.time_base(tree, shot, node, axis as i64)?;
    let picked = pick(&base, sel, params.max_points)?;
    if verb == Verb::DimOf && items.is_empty() {
        let v: Vec<f64> = picked.indices().into_iter().map(|i| base[i]).collect();
        return Ok(scaled(Node::Array(Array::vec_f64(v)), scale));
    }
    let slot = if items.is_empty() { idx.push(Index::All); 0 } else { axis };
    match picked {
        Picked::Range { start, stop, step } => {
            idx[slot] = Index::Range { start: start as i64, stop: stop as i64, step: step as i64 };
            r.read_items(tree, shot, verb, node, &idx, inside).map(|n| as_array(scaled(n, scale)))
        }
        Picked::List(list) => {
            let mut parts = Vec::with_capacity(list.len());
            for i in list {
                idx[slot] = Index::At(i as i64);
                parts.push(r.read_items(tree, shot, verb, node, &idx, inside)?);
            }
            if parts.iter().any(|p| p.as_array().map(|a| a.ndim() > 1).unwrap_or(false)) {
                notes.push(format!("{node}{}: points stacked along a new leading axis", subscript_text(items)));
            }
            Ok(scaled(stack(parts), scale))
        }
    }
}

/// 读一条 `$link` 的表达式部分（装配文档的覆盖层用）：分解，再按 [`read_one`] 读。
pub fn read_link<R: Reader + ?Sized>(r: &mut R, tree: &str, shot: i64, link: &str, params: &Params, notes: &mut Vec<String>)
                                     -> Result<Node, String> {
    let (verb, node, items, inside, value, scale) = decompose(link)?;
    if let Some(v) = value {
        return Ok(Node::Float(v));
    }
    let (verb, node) = match (verb, node) { (Some(v), Some(n)) => (v, n), _ => return Err("binding without a node".into()) };
    read_one(r, tree, shot, verb, &node, &items, inside, scale, params, notes)
}

/// 把一条绑定的文档路径里的 `*` 段代成一个整数。
fn path_with_star(path: &str, j: usize) -> String {
    path.split('/').map(|s| if s == "*" { j.to_string() } else { s.to_string() }).collect::<Vec<_>>().join("/")
}

fn has_star(path: &str) -> bool {
    path.split('/').any(|s| s == "*")
}

/// 一个 IDS 的根 `time`（`path == "time"` 的那条绑定）整条读回来——它是 `{time_slice}`
/// 展开的时基。按 IDS 缓存。
fn root_time<R: Reader>(table: &BindTable, sessions: &mut BTreeMap<String, R>, params: &Params, ids: &str,
                        cache: &mut BTreeMap<String, Result<Arc<Vec<f64>>, String>>) -> Result<Arc<Vec<f64>>, String> {
    if let Some(c) = cache.get(ids) {
        return c.clone();
    }
    let r = (|| {
        let b = table.bindings.iter().find(|b| b.ids == ids && b.path == "time").ok_or("no root `time` binding")?;
        let (verb, node) = match (b.verb, &b.node) { (Some(v), Some(n)) => (v, n), _ => return Err("root `time` is a constant".to_string()) };
        let tree = table.sources.get(&b.source).map(|s| s.tree.clone()).ok_or_else(|| format!("no source {:?}", b.source))?;
        let sess = sessions.get_mut(&b.source).ok_or_else(|| format!("no session for source {:?}", b.source))?;
        let whole = Params { shot: params.shot, slots: params.slots.clone(), time: None, max_points: None };
        let idx = indices(&b.subscript, &whole)?;
        let n = scaled(sess.read_items(&tree, params.shot, verb, node, &idx, b.inside)?, b.scale);
        n.to_f64_vec().map(Arc::new).ok_or_else(|| "root `time` is not numeric".to_string())
    })();
    cache.insert(ids.to_string(), r.clone());
    r
}

/// 开过窗的文档收尾：`ids_properties/homogeneous_time`（各通道时基相同 → 1，并把根
/// `time` 补上；否则 0），以及 `fylite:time_selection` 记下问的是什么。
fn stamp_time(doc: &mut Node, sel: &TimeSel) {
    let mut channel_times: Vec<Vec<f64>> = Vec::new();
    for (p, v) in doc.leaves() {
        if p == "time" || p.starts_with("ids_properties") || p.starts_with("fylite:") || p.starts_with("code") {
            continue;
        }
        if p == "time" || p.ends_with("/time") {
            if let Some(t) = v.to_f64_vec() {
                channel_times.push(t);
            }
        }
    }
    let root = doc.get("time").and_then(Node::to_f64_vec);
    let homogeneous = match &root {
        Some(r) => channel_times.iter().all(|t| t == r),
        None => channel_times.windows(2).all(|w| w[0] == w[1]),
    };
    if root.is_none() && homogeneous {
        if let Some(t) = channel_times.first() {
            doc.set("time", Node::Array(Array::vec_f64(t.clone()))).ok();
        }
    }
    if root.is_some() || !channel_times.is_empty() {
        doc.set("ids_properties/homogeneous_time", Node::Int(if homogeneous { 1 } else { 0 })).ok();
    }
    doc.set("fylite:time_selection", sel.to_node()).ok();
}

/// 用一组会话（按源别名）读整张表。★只走 `Reader::read_items` / `time_base`——每一条
/// 都是 `verb + 节点路径 + 整数`，没有表达式经过这里。
///
/// 有时间选择时：一维信号与带单个 `*` 的节点在自己的时基上开窗（服务端切片）；
/// 路径带 `*`（`time_slice/*/…`）的绑定按 IDS 根 `time` 上选出的下标展开成若干时间片
/// （没有根 `time` 就退到该节点 `{time_slice}` 那一轴的 `dim_of`，并记一条说明）；
/// 显式给了 `time_slice` 槽就不展开，照槽读一片。
pub fn resolve<R: Reader>(table: &BindTable, sessions: &mut BTreeMap<String, R>, params: &Params,
                          only_ids: Option<&[&str]>) -> Resolved {
    let mut out = Resolved::default();
    let mut docs: BTreeMap<String, Node> = BTreeMap::new();
    let expand = params.time.is_some() && !params.slots.contains_key("time_slice");
    let mut root_cache: BTreeMap<String, Result<Arc<Vec<f64>>, String>> = BTreeMap::new();
    let mut expanded: BTreeMap<String, Vec<f64>> = BTreeMap::new();
    //: a source without a session fails ONCE, not once per binding
    let mut dead: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    for b in &table.bindings {
        if let Some(only) = only_ids {
            if !only.contains(&b.ids.as_str()) {
                continue;
            }
        }
        if b.value.is_none() && !sessions.contains_key(&b.source) {
            if dead.insert(b.source.clone()) {
                out.failures.push((b.ids.clone(), String::new(), format!("no session for source {:?}: its bindings are skipped", b.source)));
            }
            continue;
        }
        if !docs.contains_key(&b.ids) {
            let mut d = fyodoc::new_document(&b.ids, &format!("fylite:{}/mdsplus/{}", b.ids, params.shot));
            d.set("fylite:shot", Node::Int(params.shot)).ok();
            docs.insert(b.ids.clone(), d);
        }
        let tree = match table.sources.get(&b.source) {
            Some(s) => s.tree.clone(),
            None => { out.failures.push((b.ids.clone(), b.path.clone(), format!("no source {:?}", b.source))); continue; }
        };
        //: `time_slice/*/…` under a time selection: one read per picked index
        if expand && has_star(&b.path) {
            let sel = params.time.as_ref().unwrap();
            let base = match root_time(table, sessions, params, &b.ids, &mut root_cache) {
                Ok(base) => base,
                Err(why) => {
                    let pos = b.subscript.iter().position(|i| matches!(i, Item::Slot(s) if s == "time_slice"));
                    match (&b.node, pos, sessions.get_mut(&b.source)) {
                        (Some(node), Some(pos), Some(sess)) => match sess.time_base(&tree, params.shot, node, pos as i64) {
                            Ok(base) => {
                                out.notes.push(format!("{}: {}: {why}; time slices taken from dim_of({node},{pos})", b.ids, b.path));
                                base
                            }
                            Err(e) => { out.failures.push((b.ids.clone(), b.path.clone(), format!("cannot expand {{time_slice}}: {why}; {e}"))); continue; }
                        },
                        _ => { out.failures.push((b.ids.clone(), b.path.clone(), format!("cannot expand {{time_slice}}: {why}"))); continue; }
                    }
                }
            };
            let ks = match pick(&base, sel, params.max_points) {
                Ok(p) => p.indices(),
                Err(e) => { out.failures.push((b.ids.clone(), b.path.clone(), e)); continue; }
            };
            expanded.entry(b.ids.clone()).or_insert_with(|| ks.iter().map(|&k| base[k]).collect());
            let doc = docs.get_mut(&b.ids).unwrap();
            for (j, k) in ks.iter().enumerate() {
                let path = path_with_star(&b.path, j);
                if let Some(v) = b.value {
                    doc.set(&path, Node::Float(v)).ok();
                    continue;
                }
                let (verb, node) = match (b.verb, &b.node) {
                    (Some(v), Some(n)) => (v, n),
                    _ => { out.failures.push((b.ids.clone(), path, "binding without a node".into())); continue; }
                };
                let sess = match sessions.get_mut(&b.source) {
                    Some(s) => s,
                    None => { out.failures.push((b.ids.clone(), path, format!("no session for source {:?}", b.source))); continue; }
                };
                let mut p = Params { shot: params.shot, slots: params.slots.clone(), time: None, max_points: None };
                p.slots.insert("time_slice".into(), *k as i64);
                match read_one(sess, &tree, params.shot, verb, node, &b.subscript, b.inside, b.scale, &p, &mut out.notes) {
                    Ok(v) => { doc.set(&path, v).ok(); out.read += 1; }
                    Err(e) => out.failures.push((b.ids.clone(), path, e)),
                }
            }
            continue;
        }
        let path = path_with_star(&b.path, params.slots.get("time_slice").copied().unwrap_or(0) as usize);
        let doc = docs.get_mut(&b.ids).unwrap();
        if let Some(v) = b.value {
            doc.set(&path, Node::Float(v)).ok();
            continue;
        }
        let (verb, node) = match (b.verb, &b.node) {
            (Some(v), Some(n)) => (v, n),
            _ => { out.failures.push((b.ids.clone(), path, "binding without a node".into())); continue; }
        };
        //: the root `time` is its own time base: read whole, window on its values
        if let (true, Some(sel)) = (b.path == "time", &params.time) {
            match root_time(table, sessions, params, &b.ids, &mut root_cache) {
                Ok(base) => match pick(&base, sel, params.max_points) {
                    Ok(p) => {
                        let v: Vec<f64> = p.indices().into_iter().map(|i| base[i]).collect();
                        doc.set("time", Node::Array(Array::vec_f64(v))).ok();
                        out.read += 1;
                    }
                    Err(e) => out.failures.push((b.ids.clone(), path, e)),
                },
                Err(e) => out.failures.push((b.ids.clone(), path, e)),
            }
            continue;
        }
        let sess = match sessions.get_mut(&b.source) {
            Some(s) => s,
            None => { out.failures.push((b.ids.clone(), path, format!("no session for source {:?}", b.source))); continue; }
        };
        match read_one(sess, &tree, params.shot, verb, node, &b.subscript, b.inside, b.scale, params, &mut out.notes) {
            Ok(v) => { doc.set(&path, v).ok(); out.read += 1; }
            Err(e) => out.failures.push((b.ids.clone(), path, e)),
        }
    }
    for (ids, d) in docs.iter_mut() {
        if let Some(t) = expanded.get(ids) {
            d.set("time", Node::Array(Array::vec_f64(t.clone()))).ok();
        }
        if let Some(sel) = &params.time {
            stamp_time(d, sel);
        }
    }
    for (_, d) in docs {
        out.bundle.push(d);
    }
    out
}

/// 原生：按表里的源开 TCP 连接（`host_override` 覆盖 URI 里的主机）。
#[cfg(not(target_arch = "wasm32"))]
pub fn connect_sessions(table: &BindTable, host_override: Option<&str>, port_override: Option<u16>, user: &str,
                        timeout_ms: u64) -> Result<BTreeMap<String, Session<crate::mdsip::tcp::TcpTransport>>, MdsipError> {
    let mut out = BTreeMap::new();
    for (alias, src) in &table.sources {
        let (_, host, port) = parse_uri(&src.uri);
        let host = host_override.map(str::to_string).or(host).unwrap_or_else(|| "127.0.0.1".into());
        let port = port_override.or(port).unwrap_or(8000);
        let io = crate::mdsip::tcp::TcpTransport::connect(&host, port, Some(std::time::Duration::from_millis(timeout_ms)))?;
        out.insert(alias.clone(), Session::new(Client::login(io, user)?));
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn links_decompose_the_way_the_python_tool_does() {
        let (v, n, s, inside, val, k) = decompose("DATA(\\ECRH_EAST::PECRH1I)*1000").unwrap();
        assert_eq!((v, n.as_deref(), s, inside, val, k), (Some(Verb::Data), Some("\\ECRH_EAST::PECRH1I"), vec![], false, None, Some(1000.0)));
        let (v, n, s, inside, _, k) = decompose("DATA(\\BDRY[0, *, {time_slice}])").unwrap();
        assert_eq!((v, n.as_deref(), inside, k), (Some(Verb::Data), Some("\\BDRY"), true, None));
        assert_eq!(s, vec![Item::At(0), Item::All, Item::Slot("time_slice".into())]);
        let (v, n, s, inside, _, _) = decompose("DIM_OF(\\X)[0,*]").unwrap();
        assert_eq!((v, n.as_deref(), inside), (Some(Verb::DimOf), Some("\\X"), false));
        assert_eq!(s, vec![Item::At(0), Item::All]);
        let (v, n, _, _, _, _) = decompose("\\EFIT_MFILE:CCBRSP[ 1,*]").unwrap();
        assert_eq!((v, n.as_deref()), (Some(Verb::Raw), Some("\\EFIT_MFILE:CCBRSP")));
        assert_eq!(decompose("1").unwrap().4, Some(1.0));
        assert!(decompose("BDRY[0, 0: NBDRY[{time_slice}]-1,{time_slice}]").unwrap_err().contains("two round trips"));
        assert!(decompose("SIZE(\\X)").unwrap_err().contains("unknown verb"));
        assert!(decompose("getenv(\"HOME\")").is_err());
    }

    #[test]
    fn an_abox_document_becomes_a_table() {
        let doc = crate::json::parse(r#"{
          "$source": {"efit_east": "mdsplus://202.127.204.12:8000/mdsplus/~t?shot={shot}&tree_name=efit_east"},
          "_ids": "equilibrium",
          "provenance": {"x": {"$link": "efit_east:should_be_skipped"}},
          "time": {"$link": "efit_east:TIME"},
          "vacuum_toroidal_field": {"b0": {"$link": "efit_east:BCENTR"}},
          "time_slice": [{"$id": "*", "boundary": {"type": {"$link": "efit_east:1"},
                          "outline": {"r": {"$link": "efit_east:DATA(\\BDRY[0,*,{time_slice}])"}}}}]
        }"#).unwrap();
        let t = table_from_abox(&doc, "x").unwrap();
        assert_eq!(t.sources["efit_east"].tree, "efit_east");
        assert_eq!(parse_uri(&t.sources["efit_east"].uri), (Some("efit_east".into()), Some("202.127.204.12".into()), Some(8000)));
        let paths: Vec<&str> = t.bindings.iter().map(|b| b.path.as_str()).collect();
        assert_eq!(paths, vec!["time", "vacuum_toroidal_field/b0", "time_slice/*/boundary/type", "time_slice/*/boundary/outline/r"]);
        assert_eq!(t.bindings[2].value, Some(1.0));
        assert_eq!(t.bindings[3].subscript, vec![Item::At(0), Item::All, Item::Slot("time_slice".into())]);
        assert!(t.unsupported.is_empty());
    }

    #[test]
    fn time_selections_parse_and_pick_indices_without_extrapolating() {
        assert_eq!(TimeSel::parse("4.5").unwrap(), TimeSel::Point(4.5));
        assert_eq!(TimeSel::parse("4:5").unwrap(), TimeSel::Window { t0: 4.0, t1: 5.0 });
        assert_eq!(TimeSel::parse("4, 4.5,5").unwrap(), TimeSel::Points(vec![4.0, 4.5, 5.0]));
        assert!(TimeSel::parse("four").is_err());
        assert_eq!(TimeSel::from_node(&Node::Float(4.0)).unwrap(), TimeSel::Point(4.0));
        assert_eq!(TimeSel::from_node(&crate::json::parse("[4, 5]").unwrap()).unwrap(), TimeSel::Window { t0: 4.0, t1: 5.0 });
        assert_eq!(TimeSel::from_node(&crate::json::parse("[4, 4.5, 5]").unwrap()).unwrap(), TimeSel::Points(vec![4.0, 4.5, 5.0]));
        assert_eq!(TimeSel::from_node(&crate::json::parse(r#"{"start": 4, "stop": 5}"#).unwrap()).unwrap(), TimeSel::Window { t0: 4.0, t1: 5.0 });
        let base: Vec<f64> = (0..11).map(|i| i as f64 * 0.5).collect(); // 0, 0.5, …, 5
        assert_eq!(pick(&base, &TimeSel::Point(4.1), None).unwrap(), Picked::List(vec![8]));
        assert_eq!(pick(&base, &TimeSel::Point(9.0), None).unwrap(), Picked::List(vec![10]));
        assert_eq!(pick(&base, &TimeSel::Point(-1.0), None).unwrap(), Picked::List(vec![0]));
        assert_eq!(pick(&base, &TimeSel::Window { t0: 4.0, t1: 5.0 }, None).unwrap(), Picked::Range { start: 8, stop: 10, step: 1 });
        assert_eq!(pick(&base, &TimeSel::Window { t0: 5.0, t1: 4.0 }, None).unwrap(), Picked::Range { start: 8, stop: 10, step: 1 });
        assert_eq!(pick(&base, &TimeSel::Window { t0: 0.0, t1: 5.0 }, Some(4)).unwrap(), Picked::Range { start: 0, stop: 10, step: 3 });
        assert!(pick(&base, &TimeSel::Window { t0: 4.1, t1: 4.4 }, None).unwrap_err().contains("no samples"));
        assert_eq!(pick(&base, &TimeSel::Points(vec![0.2, 4.9]), None).unwrap(), Picked::List(vec![0, 10]));
        //: an unsorted base still picks by value
        let odd = [3.0, 1.0, 2.0, 5.0, 4.0];
        assert_eq!(pick(&odd, &TimeSel::Window { t0: 2.0, t1: 4.0 }, None).unwrap(), Picked::List(vec![0, 2, 4]));
        assert_eq!(pick(&odd, &TimeSel::Point(4.9), None).unwrap(), Picked::List(vec![3]));
        assert_eq!(Picked::Range { start: 2, stop: 8, step: 3 }.indices(), vec![2, 5, 8]);
    }

    /// 一个照本宣科的传输：按序吐出预先造好的答复帧。
    struct Script {
        answers: std::collections::VecDeque<Vec<u8>>,
        sent: std::rc::Rc<std::cell::RefCell<Vec<String>>>,
    }

    impl Transport for Script {
        fn send(&mut self, bytes: &[u8]) -> Result<(), MdsipError> {
            self.sent.borrow_mut().push(String::from_utf8_lossy(&bytes[crate::mdsip::HEADER_LEN..]).to_string());
            Ok(())
        }
        fn recv(&mut self, buf: &mut [u8]) -> Result<usize, MdsipError> {
            match self.answers.pop_front() {
                Some(a) => { buf[..a.len()].copy_from_slice(&a); Ok(a.len()) }
                None => Ok(0),
            }
        }
    }

    fn frame_f64(data: &[f64], dims: &[u32]) -> Vec<u8> {
        let total = crate::mdsip::HEADER_LEN + 8 * data.len();
        let mut b = vec![0u8; total];
        b[0..4].copy_from_slice(&(total as u32).to_be_bytes());
        b[4..8].copy_from_slice(&1i32.to_be_bytes());
        b[8..10].copy_from_slice(&8u16.to_be_bytes());
        b[13] = 11;
        b[15] = dims.len() as u8;
        for (i, d) in dims.iter().enumerate() {
            b[16 + 4 * i..20 + 4 * i].copy_from_slice(&d.to_be_bytes());
        }
        for (i, v) in data.iter().enumerate() {
            b[48 + 8 * i..56 + 8 * i].copy_from_slice(&v.to_be_bytes());
        }
        b
    }

    fn scripted(frames: Vec<Vec<u8>>) -> (Session<Script>, std::rc::Rc<std::cell::RefCell<Vec<String>>>) {
        let sent = std::rc::Rc::new(std::cell::RefCell::new(Vec::new()));
        let script = Script { answers: frames.into_iter().collect(), sent: sent.clone() };
        (Session::new(Client::login(script, "user").unwrap()), sent)
    }

    #[test]
    fn a_table_resolves_into_documents_through_the_read_only_client() {
        let table_doc = crate::json::parse(r#"{
          "$schema": "fylite/mds-bind/1",
          "sources": {"efit_east": {"tree": "efit_east", "uri": "mdsplus://127.0.0.1/x?tree_name=efit_east"}},
          "bindings": [
            {"ids": "equilibrium", "path": "vacuum_toroidal_field/b0", "source": "efit_east", "verb": "data", "node": "\\BCENTR", "subscript": null, "subscript_inside": false, "value": null, "scale": null},
            {"ids": "equilibrium", "path": "time_slice/*/boundary/outline/r", "source": "efit_east", "verb": "data", "node": "\\BDRY", "subscript": [{"int": 0}, {"all": true}, {"slot": "time_slice"}], "subscript_inside": true, "value": null, "scale": 0.01},
            {"ids": "equilibrium", "path": "time_slice/*/boundary/type", "source": "efit_east", "verb": "const", "node": null, "subscript": null, "subscript_inside": false, "value": 1, "scale": null},
            {"ids": "pf_active", "path": "coil/0/current/data", "source": "efit_east", "verb": "raw", "node": "\\CCBRSP", "subscript": [{"int": 1}, {"all": true}], "subscript_inside": false, "value": null, "scale": null}
          ]
        }"#).unwrap();
        let table = parse_table(&table_doc).unwrap();
        assert_eq!(table.bindings.len(), 4);
        let (session, sent) = scripted(vec![
            frame_f64(&[1.0], &[]),          // login
            frame_f64(&[265389633.0], &[]),  // TreeOpen
            frame_f64(&[1.8], &[]),          // BCENTR
            frame_f64(&[150.0, 220.0, 180.0], &[3]), // BDRY
            frame_f64(&[1.0, 2.0, 3.0, 4.0, 5.0, 6.0], &[3, 2]), // CCBRSP (wire dims fastest first)
        ]);
        let mut sessions = BTreeMap::new();
        sessions.insert("efit_east".to_string(), session);
        let mut params = Params { shot: 70754, ..Default::default() };
        params.slots.insert("time_slice".into(), 5);
        let r = resolve(&table, &mut sessions, &params, None);
        assert!(r.failures.is_empty(), "{:?}", r.failures);
        assert_eq!(r.read, 3);
        assert!(r.notes.is_empty(), "{:?}", r.notes);
        let eq = r.bundle.get("equilibrium").unwrap();
        assert_eq!(eq.get("vacuum_toroidal_field/b0").and_then(Node::as_f64), Some(1.8));
        assert_eq!(eq.get("time_slice/5/boundary/outline/r").and_then(Node::to_f64_vec), Some(vec![1.5, 2.2, 1.8]));
        assert_eq!(eq.get("time_slice/5/boundary/type").and_then(Node::as_f64), Some(1.0));
        assert_eq!(eq.get("fylite:shot").and_then(Node::as_i64), Some(70754));
        let pf = r.bundle.get("pf_active").unwrap();
        assert_eq!(pf.get("coil/0/current/data").map(Node::shape), Some(vec![2, 3]));
        assert!(sent.borrow().iter().any(|s| s.contains("data(\\BDRY[0,*,5])")), "{:?}", sent.borrow());
    }

    #[test]
    fn a_time_window_slices_on_the_server_and_expands_time_slices() {
        //: magnetics as fydata's `magnetics_pcs.yaml` binds it, plus an
        //: equilibrium with a root `time` and `{time_slice}` bindings
        let doc = crate::json::parse(r#"{
          "$source": {"pcs_east": "mdsplus://127.0.0.1/mdsplus/~t?shot={shot}&tree_name=pcs_east"},
          "_ids": "magnetics",
          "ip": [{"data": {"$link": "pcs_east:DATA(\\PCRL01)*1000"}, "time": {"$link": "pcs_east:DIM_OF(\\PCRL01)"}}],
          "b_field_pol_probe": [
            {"field": {"data": {"$link": "pcs_east:DATA(\\PCBPV1T)"}, "time": {"$link": "pcs_east:DIM_OF(\\PCBPV1T)"}}},
            {"field": {"data": {"$link": "pcs_east:DATA(\\PCBPV2T)"}, "time": {"$link": "pcs_east:DIM_OF(\\PCBPV2T)"}}}
          ]
        }"#).unwrap();
        let mut table = table_from_abox(&doc, "magnetics").unwrap();
        let eq = crate::json::parse(r#"{
          "$source": {"pcs_east": "mdsplus://127.0.0.1/mdsplus/~t?shot={shot}&tree_name=pcs_east"},
          "_ids": "equilibrium",
          "time": {"$link": "pcs_east:TIME"},
          "time_slice": [{"$id": "*", "boundary": {"type": {"$link": "pcs_east:1"},
                          "outline": {"r": {"$link": "pcs_east:DATA(\\BDRY[0,*,{time_slice}])"}}}}]
        }"#).unwrap();
        table.bindings.extend(table_from_abox(&eq, "equilibrium").unwrap().bindings);
        let (session, sent) = scripted(vec![
            frame_f64(&[1.0], &[]),                                   // login
            frame_f64(&[265389633.0], &[]),                           // TreeOpen
            frame_f64(&[3.9, 4.1, 4.9, 5.1], &[4]),                   // dim_of(\PCRL01)
            frame_f64(&[1.0, 2.0], &[2]),                             // data(\PCRL01)[1:2]
            frame_f64(&[3.0, 3.5, 4.0, 4.5, 5.0, 5.5], &[6]),         // dim_of(\PCBPV1T)
            frame_f64(&[10.0, 11.0, 12.0], &[3]),                     // data(\PCBPV1T)[2:4]
            frame_f64(&[3.0, 3.5, 4.0, 4.5, 5.0, 5.5], &[6]),         // dim_of(\PCBPV2T)
            frame_f64(&[20.0, 21.0, 22.0], &[3]),                     // data(\PCBPV2T)[2:4]
            frame_f64(&[3.9, 4.1, 4.9, 5.1], &[4]),                   // \TIME (root time, read whole once)
            frame_f64(&[1.5, 2.2], &[2]),                             // data(\BDRY[0,*,1])
            frame_f64(&[1.6, 2.3], &[2]),                             // data(\BDRY[0,*,2])
        ]);
        let mut sessions = BTreeMap::new();
        sessions.insert("pcs_east".to_string(), session);
        let params = Params { shot: 138569, time: Some(TimeSel::Window { t0: 4.0, t1: 5.0 }), ..Default::default() };
        let r = resolve(&table, &mut sessions, &params, None);
        assert!(r.failures.is_empty(), "{:?}", r.failures);
        let m = r.bundle.get("magnetics").unwrap();
        assert_eq!(m.get("ip/0/data").and_then(Node::to_f64_vec), Some(vec![1000.0, 2000.0]));
        assert_eq!(m.get("ip/0/time").and_then(Node::to_f64_vec), Some(vec![4.1, 4.9]));
        assert_eq!(m.get("b_field_pol_probe/0/field/data").and_then(Node::to_f64_vec), Some(vec![10.0, 11.0, 12.0]));
        assert_eq!(m.get("b_field_pol_probe/1/field/time").and_then(Node::to_f64_vec), Some(vec![4.0, 4.5, 5.0]));
        //: the probes share a base, ip does not → heterogeneous, no root time invented
        assert_eq!(m.get("ids_properties/homogeneous_time").and_then(Node::as_i64), Some(0));
        assert!(m.get("time").is_none());
        assert_eq!(m.get("fylite:time_selection/start").and_then(Node::as_f64), Some(4.0));
        let e = r.bundle.get("equilibrium").unwrap();
        assert_eq!(e.get("time").and_then(Node::to_f64_vec), Some(vec![4.1, 4.9]));
        assert_eq!(e.get("time_slice/0/boundary/outline/r").and_then(Node::to_f64_vec), Some(vec![1.5, 2.2]));
        assert_eq!(e.get("time_slice/1/boundary/outline/r").and_then(Node::to_f64_vec), Some(vec![1.6, 2.3]));
        assert_eq!(e.get("time_slice/1/boundary/type").and_then(Node::as_f64), Some(1.0));
        assert!(e.get("time_slice/2").is_none());
        assert_eq!(e.get("ids_properties/homogeneous_time").and_then(Node::as_i64), Some(1));
        let sent = sent.borrow();
        assert!(sent.iter().any(|s| s == "data(\\PCBPV1T)[2:4]"), "{sent:?}");
        assert!(sent.iter().any(|s| s == "dim_of(\\PCRL01)"), "{sent:?}");
        assert!(sent.iter().any(|s| s == "data(\\BDRY[0,*,2])"), "{sent:?}");
        //: DIM_OF bindings never went to the server: the cached base answered them
        assert_eq!(sent.iter().filter(|s| s.starts_with("dim_of(\\PCBPV1T")).count(), 1);
        assert_eq!(sent.len(), 11);
    }

    #[test]
    fn a_point_and_a_list_of_points_read_one_sample_each() {
        let (mut session, sent) = scripted(vec![
            frame_f64(&[1.0], &[]),                           // login
            frame_f64(&[265389633.0], &[]),                   // TreeOpen
            frame_f64(&[0.0, 1.0, 2.0, 3.0], &[4]),           // dim_of(\X, 1)
            frame_f64(&[7.0], &[]),                           // \X[3,2]
            frame_f64(&[9.0], &[]),                           // \X[3,3]
        ]);
        let params = Params { shot: 1, time: Some(TimeSel::Points(vec![2.1, 2.9])), ..Default::default() };
        let mut notes = Vec::new();
        let v = read_one(&mut session, "efit_east", 1, Verb::Raw, "\\X", &[Item::At(3), Item::All], false, None, &params, &mut notes).unwrap();
        assert_eq!(v.to_f64_vec(), Some(vec![7.0, 9.0]));
        assert!(notes.is_empty());
        let sent = sent.borrow();
        assert!(sent.iter().any(|s| s == "dim_of(\\X,1)"), "{sent:?}");
        assert!(sent.iter().any(|s| s == "\\X[3,2]"), "{sent:?}");
        drop(sent);
        //: two `*`: no single time axis → read whole, with a note, not a guess
        let (mut s2, _) = scripted(vec![frame_f64(&[1.0], &[]), frame_f64(&[1.0], &[]), frame_f64(&[1.0, 2.0, 3.0, 4.0], &[2, 2])]);
        let mut notes = Vec::new();
        let v = read_one(&mut s2, "t", 1, Verb::Data, "\\Y", &[Item::All, Item::All], false, None, &params, &mut notes).unwrap();
        assert_eq!(v.shape(), vec![2, 2]);
        assert_eq!(notes.len(), 1);
        assert!(notes[0].contains("no single time axis"));
    }
}
