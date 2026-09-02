//! 装配 —— 用一份 fyo/JSON-LD 文档把多个数据源拼成一束文档。
//!
//! ★★**它长什么样**，与 A-Box 绑定文档同一套写法（`$source` 登记源、`$link` 指向源），
//! 只是源可以是**文件**、**MDSplus 绑定表**或 **MDSplus 树**，并且可以整份合并：
//!
//! ```json
//! {
//!   "@context": {"fyo": "https://fusion-yun.github.io/fyo/latest/", "fylite": "urn:fylite:"},
//!   "@type": "fylite:Assembly/1",
//!   "$source": {
//!     "machine": "file:./iter_md_wall.nc",
//!     "efit":    "file:./g063982.04800",
//!     "east":    "mdsbind:./mds-bind.json?host=mds.example.org&port=8000"
//!   },
//!   "params": {"shot": 63982, "time_slice": 0},
//!   "merge": ["machine", "efit", "east"],
//!   "equilibrium": {
//!     "time_slice": [{"global_quantities": {"ip": {"$link": "east:DATA(\\PLASMA)"}}}],
//!     "vacuum_toroidal_field": {"r0": 1.75}
//!   }
//! }
//! ```
//!
//! 语义，按序：`merge` 里的源逐个读进来合并（后者覆盖前者，叶子级）；然后顶层的
//! IDS 名下的子树作为**覆盖层**叠上去——`$link` 叶子解析（`file` 源：`别名:ids/路径`
//! 取那份文档的一条路径；MDSplus 源：`别名:表达式`，与 A-Box 的 `$link` 同一分解），
//! 其余字面值原样写入。每份产出文档带一块 `fylite:assembly`：合并了哪些源、
//! 参数是什么——出处在数据里，不在旁边的散文里。
//!
//! ★源的路径相对**装配文档所在目录**解析，不相对进程的 cwd：一份装配文档搬到哪里，
//! 它旁边的文件跟着搬。

use crate::document::{MergePolicy, Node};
use crate::fyodoc::{self, Bundle};
use crate::io::{self, IoError};
use crate::mdsbind::{self, BindTable, Params};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

/// 给 MDSplus 源开会话的办法：`(host, port, tree) -> 会话`。
pub type Connector<'a> = &'a dyn Fn(&str, u16, &str) -> Option<Box<dyn AnySession>>;

/// 一个已登记的源。
#[derive(Debug, Clone)]
pub enum SourceSpec {
    /// 一个文件或 IMAS 目录（自动识别）。
    File(PathBuf),
    /// 一张绑定表（`fylite/mds-bind/1`）或一份 A-Box 绑定文档，经 mdsip 读。
    MdsBind { path: PathBuf, host: Option<String>, port: Option<u16> },
    /// 一棵 MDSplus 树：`mdsplus://host:port/tree`——`$link` 里直接写表达式。
    Mdsplus { host: String, port: u16, tree: String },
}

#[derive(Debug, Clone)]
pub struct Assembly {
    pub dir: PathBuf,
    pub sources: BTreeMap<String, SourceSpec>,
    pub params: Params,
    pub merge: Vec<String>,
    /// 覆盖层：IDS 名 → 子树（含 `$link` 叶子）。
    pub overlays: Vec<(String, Node)>,
    pub policy: MergePolicy,
}

fn query_of(uri: &str) -> (String, BTreeMap<String, String>) {
    let (base, q) = match uri.split_once('?') { Some((b, q)) => (b, q), None => (uri, "") };
    let mut map = BTreeMap::new();
    for kv in q.split('&').filter(|s| !s.is_empty()) {
        let (k, v) = kv.split_once('=').unwrap_or((kv, ""));
        map.insert(k.to_string(), v.to_string());
    }
    (base.to_string(), map)
}

/// 解析一份装配文档。
pub fn parse(doc: &Node, dir: &Path) -> Result<Assembly, IoError> {
    let m = doc.as_map().ok_or_else(|| IoError("an assembly document is a mapping".into()))?;
    let mut a = Assembly { dir: dir.to_path_buf(), sources: BTreeMap::new(), params: Params::default(),
                           merge: Vec::new(), overlays: Vec::new(), policy: MergePolicy::Overwrite };
    for (alias, v) in m.get("$source").and_then(Node::as_map).map(|s| s.iter().collect::<Vec<_>>()).unwrap_or_default() {
        let uri = v.as_str().ok_or_else(|| IoError(format!("$source {alias:?} is not a string")))?;
        let spec = if let Some(rest) = uri.strip_prefix("file:") {
            SourceSpec::File(dir.join(rest.trim_start_matches("//")))
        } else if let Some(rest) = uri.strip_prefix("mdsbind:") {
            let (base, q) = query_of(rest);
            SourceSpec::MdsBind { path: dir.join(base), host: q.get("host").cloned(),
                                  port: q.get("port").and_then(|p| p.parse().ok()) }
        } else if uri.starts_with("mdsplus://") {
            let (tree, host, port) = mdsbind::parse_uri(uri);
            let tree = tree.or_else(|| uri.strip_prefix("mdsplus://").and_then(|r| r.split('/').nth(1)).map(|t| t.split('?').next().unwrap_or(t).to_lowercase()))
                .ok_or_else(|| IoError(format!("mdsplus source {alias:?} names no tree")))?;
            SourceSpec::Mdsplus { host: host.unwrap_or_else(|| "127.0.0.1".into()), port: port.unwrap_or(8000), tree }
        } else {
            SourceSpec::File(dir.join(uri))
        };
        a.sources.insert(alias.to_string(), spec);
    }
    if let Some(p) = m.get("params").and_then(Node::as_map) {
        for (k, v) in p.iter() {
            if let Some(i) = v.as_i64() {
                if k == "shot" { a.params.shot = i; } else { a.params.slots.insert(k.to_string(), i); }
            }
        }
    }
    if let Some(l) = m.get("merge") {
        match l {
            Node::List(items) => a.merge = items.iter().filter_map(|x| x.as_str().map(str::to_string)).collect(),
            Node::Array(arr) => a.merge = arr.as_str().map(|s| s.to_vec()).unwrap_or_default(),
            Node::Str(s) => a.merge = vec![s.clone()],
            _ => {}
        }
    }
    if m.get("policy").and_then(Node::as_str) == Some("keep") {
        a.policy = MergePolicy::KeepExisting;
    }
    for (k, v) in m.iter() {
        if fyodoc::is_semantic_key(k) || k.starts_with('$') || k == "params" || k == "merge" || k == "policy" || k.contains(':') {
            continue;
        }
        if crate::ids_meta::IdsMeta::get(&fyodoc::split_ids_key(k).0).is_some() {
            a.overlays.push((k.to_string(), v.clone()));
        }
    }
    Ok(a)
}

/// 装配的产物：束 + 逐条的失败（源读不到、链接解析不了）。
#[derive(Debug, Default)]
pub struct Assembled {
    pub bundle: Bundle,
    pub failures: Vec<String>,
    pub sources_used: Vec<String>,
}

/// 读源、合并、叠覆盖层。
///
/// `connect`：给 MDSplus 源开会话的办法（测试可以递一个照本宣科的传输进来；
/// `None` = 不开网络，MDSplus 源一律记为失败）。
pub fn assemble(a: &Assembly, connect: Option<Connector<'_>>) -> Assembled {
    let mut out = Assembled::default();
    let mut cache: BTreeMap<String, Bundle> = BTreeMap::new();
    let mut load = |alias: &str, out: &mut Assembled| -> Option<Bundle> {
        if let Some(b) = cache.get(alias) {
            return Some(b.clone());
        }
        let spec = match a.sources.get(alias) {
            Some(s) => s,
            None => { out.failures.push(format!("no source {alias:?}")); return None; }
        };
        let b = match spec {
            SourceSpec::File(p) => match io::read(p) {
                Ok(b) => b,
                Err(e) => { out.failures.push(format!("{alias}: {e}")); return None; }
            },
            SourceSpec::MdsBind { path, host, port } => {
                let text = match std::fs::read_to_string(path) { Ok(t) => t, Err(e) => { out.failures.push(format!("{alias}: {e}")); return None; } };
                let doc = match crate::json::parse(&text) { Ok(d) => d, Err(e) => { out.failures.push(format!("{alias}: {e}")); return None; } };
                let table = match mdsbind::parse_table(&doc).or_else(|_| mdsbind::table_from_abox(&doc, path.file_stem().map(|s| s.to_string_lossy().to_string()).as_deref().unwrap_or("unknown"))) {
                    Ok(t) => t, Err(e) => { out.failures.push(format!("{alias}: {e}")); return None; }
                };
                match resolve_table(&table, host.as_deref(), *port, &a.params, connect) {
                    Ok((b, fails)) => { out.failures.extend(fails.into_iter().map(|f| format!("{alias}: {f}"))); b }
                    Err(e) => { out.failures.push(format!("{alias}: {e}")); return None; }
                }
            }
            SourceSpec::Mdsplus { .. } => Bundle::new(),
        };
        cache.insert(alias.to_string(), b.clone());
        Some(b)
    };
    for alias in &a.merge {
        if let Some(b) = load(alias, &mut out) {
            out.bundle.merge(b, a.policy);
            out.sources_used.push(alias.clone());
        }
    }
    //: overlays
    let mut live: BTreeMap<String, Box<dyn AnySession>> = BTreeMap::new();
    for (key, overlay) in &a.overlays {
        let (ids, occ) = fyodoc::split_ids_key(key);
        let resolved = resolve_links(overlay, a, &mut load, &mut live, connect, &mut out);
        if out.bundle.get_occ(&ids, occ).is_none() {
            let d = fyodoc::from_dd(&ids, Node::map(), &format!("fylite:{ids}/assembly"), occ);
            out.bundle.push(d);
        }
        out.bundle.get_mut(&ids, occ).unwrap().merge(resolved, MergePolicy::Overwrite);
    }
    //: provenance
    let mut prov = Node::map();
    let used: Vec<Node> = out.sources_used.iter().map(|s| Node::Str(s.clone())).collect();
    prov.set("merged", Node::List(used)).ok();
    prov.set("shot", Node::Int(a.params.shot)).ok();
    for (k, v) in &a.params.slots {
        prov.set(&format!("params/{k}"), Node::Int(*v)).ok();
    }
    for d in out.bundle.docs.iter_mut() {
        d.set("fylite:assembly", prov.clone()).ok();
    }
    out
}

/// 一个开着的 MDSplus 会话，抹掉传输类型。
pub trait AnySession {
    fn read_expr(&mut self, tree: &str, shot: i64, link: &str, params: &Params) -> Result<Node, String>;
}

impl<T: crate::mdsip::Transport> AnySession for mdsbind::Session<T> {
    fn read_expr(&mut self, tree: &str, shot: i64, link: &str, params: &Params) -> Result<Node, String> {
        let (verb, node, items, inside, value, scale) = mdsbind::decompose(link)?;
        if let Some(v) = value {
            return Ok(Node::Float(v));
        }
        let (verb, node) = match (verb, node) { (Some(v), Some(n)) => (v, n), _ => return Err("binding without a node".into()) };
        self.read_binding(tree, shot, verb, &node, &items, inside, scale, params)
    }
}

fn resolve_table(table: &BindTable, host: Option<&str>, port: Option<u16>, params: &Params,
                 connect: Option<Connector<'_>>)
                 -> Result<(Bundle, Vec<String>), String> {
    let connect = connect.ok_or("no network: MDSplus sources are disabled")?;
    let mut fails = Vec::new();
    let mut bundle = Bundle::new();
    //: one session per source alias; each binding is a one-expression read
    let mut sessions: BTreeMap<String, Box<dyn AnySession>> = BTreeMap::new();
    for (alias, src) in &table.sources {
        let (_, h, p) = mdsbind::parse_uri(&src.uri);
        let h = host.map(str::to_string).or(h).unwrap_or_else(|| "127.0.0.1".into());
        let p = port.or(p).unwrap_or(8000);
        match connect(&h, p, &src.tree) {
            Some(s) => { sessions.insert(alias.clone(), s); }
            None => fails.push(format!("cannot connect to {h}:{p} for {alias}")),
        }
    }
    let mut docs: BTreeMap<String, Node> = BTreeMap::new();
    for b in &table.bindings {
        let path = b.path.split('/').map(|s| if s == "*" { params.slots.get("time_slice").map(|v| v.to_string()).unwrap_or_else(|| "0".into()) } else { s.to_string() }).collect::<Vec<_>>().join("/");
        let doc = docs.entry(b.ids.clone()).or_insert_with(|| fyodoc::new_document(&b.ids, &format!("fylite:{}/mdsplus/{}", b.ids, params.shot)));
        if let Some(v) = b.value {
            doc.set(&path, Node::Float(v)).ok();
            continue;
        }
        let link = match (&b.node, b.verb) {
            (Some(n), Some(v)) => {
                let sub: Vec<String> = b.subscript.iter().map(|i| match i { mdsbind::Item::At(x) => x.to_string(), mdsbind::Item::All => "*".into(), mdsbind::Item::Slot(s) => format!("{{{s}}}") }).collect();
                let subs = if sub.is_empty() { String::new() } else { format!("[{}]", sub.join(",")) };
                let core = match v { crate::mdsip::Verb::Raw => format!("{n}{subs}"),
                    crate::mdsip::Verb::Data => if b.inside { format!("DATA({n}{subs})") } else { format!("DATA({n}){subs}") },
                    crate::mdsip::Verb::DimOf => if b.inside { format!("DIM_OF({n}{subs})") } else { format!("DIM_OF({n}){subs}") } };
                match b.scale { Some(k) => format!("{core}*{k}"), None => core }
            }
            _ => { fails.push(format!("{}: binding without a node", b.path)); continue; }
        };
        let tree = table.sources.get(&b.source).map(|s| s.tree.clone()).unwrap_or_default();
        match sessions.get_mut(&b.source) {
            Some(s) => match s.read_expr(&tree, params.shot, &link, params) {
                Ok(v) => { doc.set(&path, v).ok(); }
                Err(e) => fails.push(format!("{}: {e}", b.path)),
            },
            None => fails.push(format!("{}: no session for {}", b.path, b.source)),
        }
    }
    for (_, d) in docs {
        bundle.push(d);
    }
    Ok((bundle, fails))
}

fn resolve_links(n: &Node, a: &Assembly, load: &mut dyn FnMut(&str, &mut Assembled) -> Option<Bundle>,
                 live: &mut BTreeMap<String, Box<dyn AnySession>>,
                 connect: Option<Connector<'_>>, out: &mut Assembled) -> Node {
    match n {
        Node::Map(m) => {
            if let Some(link) = m.get("$link").and_then(Node::as_str) {
                return match resolve_one(link, a, load, live, connect, out) {
                    Some(v) => v,
                    None => Node::Null,
                };
            }
            let mut o = crate::document::Map::new();
            for (k, v) in m.iter() {
                o.insert(k, resolve_links(v, a, load, live, connect, out));
            }
            Node::Map(o)
        }
        Node::List(l) => Node::List(l.iter().map(|v| resolve_links(v, a, load, live, connect, out)).collect()),
        other => other.clone(),
    }
}

fn resolve_one(link: &str, a: &Assembly, load: &mut dyn FnMut(&str, &mut Assembled) -> Option<Bundle>,
               live: &mut BTreeMap<String, Box<dyn AnySession>>,
               connect: Option<Connector<'_>>, out: &mut Assembled) -> Option<Node> {
    let (alias, rest) = match link.split_once(':') {
        Some(x) => x,
        None => { out.failures.push(format!("$link {link:?} has no source alias")); return None; }
    };
    match a.sources.get(alias) {
        Some(SourceSpec::File(_)) | Some(SourceSpec::MdsBind { .. }) => {
            let b = load(alias, out)?;
            let (ids, path) = rest.split_once('/').unwrap_or((rest, ""));
            let (ids, occ) = fyodoc::split_ids_key(ids);
            let doc = match b.get_occ(&ids, occ) { Some(d) => d, None => { out.failures.push(format!("{alias} has no {ids}")); return None; } };
            match doc.walk(path, true) {
                Some(v) => Some(v.clone()),
                None => { out.failures.push(format!("{alias}:{rest} not found")); None }
            }
        }
        Some(SourceSpec::Mdsplus { host, port, tree }) => {
            if !live.contains_key(alias) {
                match connect.and_then(|c| c(host, *port, tree)) {
                    Some(s) => { live.insert(alias.to_string(), s); }
                    None => { out.failures.push(format!("{alias}: cannot connect to {host}:{port}")); return None; }
                }
            }
            let s = live.get_mut(alias).unwrap();
            match s.read_expr(tree, a.params.shot, rest, &a.params) {
                Ok(v) => Some(v),
                Err(e) => { out.failures.push(format!("{alias}:{rest}: {e}")); None }
            }
        }
        None => { out.failures.push(format!("$link {link:?}: no source {alias:?}")); None }
    }
}

/// 读装配文档并执行（源相对文档所在目录）。
pub fn assemble_file(path: &Path, connect: Option<Connector<'_>>,
                     shot: Option<i64>, slots: &[(String, i64)]) -> Result<Assembled, IoError> {
    let text = std::fs::read_to_string(path)?;
    let doc = crate::json::parse(&text)?;
    let dir = path.parent().map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let mut a = parse(&doc, &dir)?;
    if let Some(s) = shot {
        a.params.shot = s;
    }
    for (k, v) in slots {
        a.params.slots.insert(k.clone(), *v);
    }
    Ok(assemble(&a, connect))
}

/// 原生的连接办法：TCP 到 host:port，登录 `user`。
#[cfg(not(target_arch = "wasm32"))]
pub fn tcp_connector(user: String, timeout_ms: u64) -> impl Fn(&str, u16, &str) -> Option<Box<dyn AnySession>> {
    move |host: &str, port: u16, _tree: &str| {
        let io = crate::mdsip::tcp::TcpTransport::connect(host, port, Some(std::time::Duration::from_millis(timeout_ms))).ok()?;
        let client = crate::mdsip::Client::login(io, &user).ok()?;
        Some(Box::new(mdsbind::Session::new(client)) as Box<dyn AnySession>)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn files_merge_and_links_pull_leaves_from_them() {
        let dir = std::env::temp_dir().join(format!("fylite_data_asm_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("g000001.00100"), include_str!("../testdata/g_synthetic.geqdsk")).unwrap();
        let mut w = fyodoc::new_document("wall", "w");
        w.set("description_2d/0/limiter/unit/0/outline/r", vec![9.0, 9.5].into()).unwrap();
        std::fs::write(dir.join("machine.json"), crate::json::to_string(&w, true)).unwrap();
        let mut e2 = fyodoc::new_document("equilibrium", "e2");
        e2.set("vacuum_toroidal_field/r0", 9.9.into()).unwrap();
        e2.set("time_slice/0/global_quantities/ip", 7.0.into()).unwrap();
        std::fs::write(dir.join("override.json"), crate::json::to_string(&e2, true)).unwrap();
        let asm = r#"{
          "@type": "fylite:Assembly/1",
          "$source": {"efit": "file:g000001.00100", "machine": "file:./machine.json", "over": "file:override.json"},
          "params": {"shot": 1, "time_slice": 0},
          "merge": ["efit", "machine", "over"],
          "equilibrium": {
            "vacuum_toroidal_field": {"b0": 2.5},
            "time_slice": [{"boundary": {"outline": {"r": {"$link": "efit:equilibrium/time_slice/0/boundary/outline/r"}}}}],
            "fylite:note": "assembled"
          },
          "pf_active": {"coil": [{"name": "PF1", "current": {"data": {"$link": "machine:wall/description_2d/0/limiter/unit/0/outline/r"}}}]}
        }"#;
        std::fs::write(dir.join("asm.jsonld"), asm).unwrap();
        let r = assemble_file(&dir.join("asm.jsonld"), None, None, &[]).unwrap();
        assert!(r.failures.is_empty(), "{:?}", r.failures);
        assert_eq!(r.sources_used, vec!["efit", "machine", "over"]);
        let eq = r.bundle.get("equilibrium").unwrap();
        //: the later source overrode r0 and ip, the overlay set b0 and copied a link
        assert_eq!(eq.get("vacuum_toroidal_field/r0").and_then(Node::as_f64), Some(9.9));
        assert_eq!(eq.get("time_slice/0/global_quantities/ip").and_then(Node::as_f64), Some(7.0));
        assert_eq!(eq.get("vacuum_toroidal_field/b0").and_then(Node::as_f64), Some(2.5));
        let g = crate::geqdsk::parse(include_str!("../testdata/g_synthetic.geqdsk")).unwrap();
        assert_eq!(eq.get("time_slice/0/boundary/outline/r").and_then(Node::to_f64_vec), Some(g.rbbbs.clone()));
        assert_eq!(eq.get("time_slice/0/profiles_1d/f").and_then(Node::to_f64_vec), Some(g.fpol.clone()));
        assert_eq!(eq.get("fylite:note").and_then(Node::as_str), Some("assembled"));
        assert_eq!(eq.get("fylite:assembly/shot").and_then(Node::as_i64), Some(1));
        assert!(r.bundle.get("wall").is_some());
        let pf = r.bundle.get("pf_active").unwrap();
        assert_eq!(pf.get("coil/0/current/data").and_then(Node::to_f64_vec), Some(vec![9.0, 9.5]));
        //: a missing link is a named failure, not a silent null
        let bad = r#"{"$source": {"efit": "file:g000001.00100"}, "merge": ["efit"], "equilibrium": {"x": {"$link": "efit:equilibrium/nope"}}}"#;
        std::fs::write(dir.join("bad.jsonld"), bad).unwrap();
        let r2 = assemble_file(&dir.join("bad.jsonld"), None, None, &[]).unwrap();
        assert_eq!(r2.failures.len(), 1);
        assert!(r2.failures[0].contains("not found"));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
