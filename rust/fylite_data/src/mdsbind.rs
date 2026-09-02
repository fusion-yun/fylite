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

use crate::document::{Array, Node};
use crate::fyodoc::{self, Bundle};
use crate::mdsip::{Client, Index, MdsipError, Transport, Verb};
use std::collections::BTreeMap;

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

/// 分解一条 `$link` 的表达式部分（别名已剥掉）。
pub fn decompose(expr: &str) -> Result<(Option<Verb>, Option<String>, Vec<Item>, bool, Option<f64>, Option<f64>), String> {
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

/// 参数：`shot` 与代入下标的槽（`time_slice` 等）。
#[derive(Debug, Clone, Default)]
pub struct Params {
    pub shot: i64,
    pub slots: BTreeMap<String, i64>,
}

/// 一次解析的结果：文档束 + 逐条的失败。
#[derive(Debug, Default)]
pub struct Resolved {
    pub bundle: Bundle,
    pub failures: Vec<(String, String, String)>,
    pub read: usize,
}

/// 一个源 = 一条已登录的连接（树在读时打开）。
pub struct Session<T: Transport> {
    pub client: Client<T>,
    open_tree: Option<(String, i64)>,
}

impl<T: Transport> Session<T> {
    pub fn new(client: Client<T>) -> Self {
        Session { client, open_tree: None }
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
    Node::Array(Array { shape, data: crate::document::ArrayData::F64(vals) })
}

impl<T: Transport> Session<T> {
    /// 读一条已分解的绑定。
    #[allow(clippy::too_many_arguments)]
    pub fn read_binding(&mut self, tree: &str, shot: i64, verb: Verb, node: &str, items: &[Item], inside: bool,
                        scale: Option<f64>, params: &Params) -> Result<Node, String> {
        let idx = indices(items, params)?;
        self.ensure_tree(tree, shot).map_err(|e| e.to_string())?;
        let ans = self.client.read(verb, node, &idx, inside).map_err(|e| e.to_string())?;
        Ok(answer_to_node(&ans, scale))
    }
}

pub fn indices(items: &[Item], params: &Params) -> Result<Vec<Index>, String> {
    items.iter().map(|it| match it {
        Item::At(i) => Ok(Index::At(*i)),
        Item::All => Ok(Index::All),
        Item::Slot(s) => params.slots.get(s).map(|v| Index::At(*v)).ok_or_else(|| format!("no value for {{{s}}}")),
    }).collect()
}

/// 把一条绑定的文档路径里的 `*` 段代成 `{time_slice}` 的值。
fn concrete_path(path: &str, params: &Params) -> String {
    path.split('/').map(|s| {
        if s == "*" { params.slots.get("time_slice").map(|v| v.to_string()).unwrap_or_else(|| "0".into()) } else { s.to_string() }
    }).collect::<Vec<_>>().join("/")
}

/// 用一组会话（按源别名）读整张表。★只走 `Client::read`——每一条都是
/// `verb + 节点路径 + 整数`，没有表达式经过这里。
pub fn resolve<T: Transport>(table: &BindTable, sessions: &mut BTreeMap<String, Session<T>>, params: &Params,
                             only_ids: Option<&[&str]>) -> Resolved {
    let mut out = Resolved::default();
    let mut docs: BTreeMap<String, Node> = BTreeMap::new();
    for b in &table.bindings {
        if let Some(only) = only_ids {
            if !only.contains(&b.ids.as_str()) {
                continue;
            }
        }
        let path = concrete_path(&b.path, params);
        let doc = docs.entry(b.ids.clone()).or_insert_with(|| {
            let mut d = fyodoc::new_document(&b.ids, &format!("fylite:{}/mdsplus/{}", b.ids, params.shot));
            d.set("fylite:shot", Node::Int(params.shot)).ok();
            d
        });
        if let Some(v) = b.value {
            doc.set(&path, Node::Float(v)).ok();
            continue;
        }
        let (verb, node) = match (b.verb, &b.node) {
            (Some(v), Some(n)) => (v, n),
            _ => { out.failures.push((b.ids.clone(), path, "binding without a node".into())); continue; }
        };
        let tree = match table.sources.get(&b.source) {
            Some(s) => s.tree.clone(),
            None => { out.failures.push((b.ids.clone(), path, format!("no source {:?}", b.source))); continue; }
        };
        let sess = match sessions.get_mut(&b.source) {
            Some(s) => s,
            None => { out.failures.push((b.ids.clone(), path, format!("no session for source {:?}", b.source))); continue; }
        };
        let idx = match indices(&b.subscript, params) {
            Ok(i) => i,
            Err(e) => { out.failures.push((b.ids.clone(), path, e)); continue; }
        };
        if let Err(e) = sess.ensure_tree(&tree, params.shot) {
            out.failures.push((b.ids.clone(), path, e.to_string()));
            continue;
        }
        match sess.client.read(verb, node, &idx, b.inside) {
            Ok(ans) => {
                doc.set(&path, answer_to_node(&ans, b.scale)).ok();
                out.read += 1;
            }
            Err(e) => out.failures.push((b.ids.clone(), path, e.to_string())),
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

    /// 一个照本宣科的传输：按序吐出预先造好的答复帧。
    struct Script {
        answers: std::collections::VecDeque<Vec<u8>>,
        sent: Vec<String>,
    }

    impl Transport for Script {
        fn send(&mut self, bytes: &[u8]) -> Result<(), MdsipError> {
            self.sent.push(String::from_utf8_lossy(&bytes[crate::mdsip::HEADER_LEN..]).to_string());
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
        let script = Script {
            answers: [
                frame_f64(&[1.0], &[]),          // login
                frame_f64(&[265389633.0], &[]),  // TreeOpen
                frame_f64(&[1.8], &[]),          // BCENTR
                frame_f64(&[150.0, 220.0, 180.0], &[3]), // BDRY
                frame_f64(&[1.0, 2.0, 3.0, 4.0, 5.0, 6.0], &[3, 2]), // CCBRSP (wire dims fastest first)
            ].into_iter().collect(),
            sent: Vec::new(),
        };
        let client = Client::login(script, "user").unwrap();
        let mut sessions = BTreeMap::new();
        sessions.insert("efit_east".to_string(), Session::new(client));
        let mut params = Params { shot: 70754, ..Default::default() };
        params.slots.insert("time_slice".into(), 5);
        let r = resolve(&table, &mut sessions, &params, None);
        assert!(r.failures.is_empty(), "{:?}", r.failures);
        assert_eq!(r.read, 3);
        let eq = r.bundle.get("equilibrium").unwrap();
        assert_eq!(eq.get("vacuum_toroidal_field/b0").and_then(Node::as_f64), Some(1.8));
        assert_eq!(eq.get("time_slice/5/boundary/outline/r").and_then(Node::to_f64_vec), Some(vec![1.5, 2.2, 1.8]));
        assert_eq!(eq.get("time_slice/5/boundary/type").and_then(Node::as_f64), Some(1.0));
        assert_eq!(eq.get("fylite:shot").and_then(Node::as_i64), Some(70754));
        let pf = r.bundle.get("pf_active").unwrap();
        assert_eq!(pf.get("coil/0/current/data").map(Node::shape), Some(vec![2, 3]));
        let sent = &sessions["efit_east"].client;
        let _ = sent;
    }
}
