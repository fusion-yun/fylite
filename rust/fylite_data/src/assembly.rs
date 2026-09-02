//! 装配 —— 用一份 fyo/JSON-LD（或 YAML）文档把多个数据源拼成一束文档。
//!
//! ★★**它长什么样**，与 A-Box 绑定文档同一套写法（`$source` 登记源、`$link` 指向源），
//! 只是源可以是**文件**、**MDSplus 绑定表**或 **MDSplus 树**，并且可以整份合并：
//!
//! ```json
//! {
//!   "@context": {"fyo": "https://fusion-yun.github.io/fyo/latest/", "fylite": "urn:fylite:"},
//!   "@type": "fylite:Assembly/1",
//!   "$source": {
//!     "geometry": "file:../fydata/machine/tokamak/east/fyo/0.0.0/providers/magnetics/pcs.yaml",
//!     "east":     "mdsbind:../fydata/machine/tokamak/east/fyo/0.0.0/bind/mdsplus/magnetics_pcs.yaml?host=mds.example.org&port=8000"
//!   },
//!   "params": {"shot": 138569, "time": [4.0, 5.0], "max_points": 20000},
//!   "merge": ["geometry", "east"],
//!   "select": ["magnetics/b_field_pol_probe", "magnetics/ip"],
//!   "magnetics": {"fylite:note": "EAST magnetics, PCS provider"}
//! }
//! ```
//!
//! 语义，按序：`merge` 里的源逐个读进来合并（后者覆盖前者，叶子级；结构数组按
//! `merge_key`——缺省 `name`——对齐，两边都没有键才按下标）；然后顶层的 IDS 名下的子树
//! 作为**覆盖层**叠上去——`$link` 叶子解析（`file` 源：`别名:ids/路径` 取那份文档的一条
//! 路径；MDSplus 源：`别名:表达式`，与 A-Box 的 `$link` 同一分解），其余字面值原样写入；
//! 最后 `select` 只留列出的 IDS / 子树。每份产出文档带一块 `fylite:assembly`：合并了
//! 哪些源、参数是什么——出处在数据里，不在旁边的散文里。
//!
//! `params.time`（数 / `[t0, t1]` / 列表 / `"4:5"` 文本）是时间选择：MDSplus 源在各自的
//! 时基上开窗（见 `mdsbind`），文件源不受影响。
//!
//! ★源的路径相对**装配文档所在目录**解析，不相对进程的 cwd：一份装配文档搬到哪里，
//! 它旁边的文件跟着搬。
//!
//! 装置清单（fydata 的 `machine.yaml`）是装配文档的另一种来路：[`from_manifest`] 按
//! `(炮 → epoch, 提供者 → 几何文件, 绑定 → 绑定文件)` 摊成同一个 [`Assembly`]。

use crate::document::{Map, MergePolicy, Node};
use crate::fyodoc::{self, Bundle};
use crate::io::{self, IoError};
use crate::mdsbind::{self, BindTable, Params, Reader, TimeSel};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

/// 一条开着的 MDSplus 会话，抹掉传输类型（[`mdsbind::Reader`]）。
pub type AnySession = Box<dyn Reader>;

/// 给 MDSplus 源开会话的办法：`(host, port, tree) -> 会话`。
pub type Connector<'a> = &'a dyn Fn(&str, u16, &str) -> Option<AnySession>;

/// 一个已登记的源。
#[derive(Debug, Clone)]
pub enum SourceSpec {
    /// 一个文件或 IMAS 目录（自动识别；fydata 的 YAML 也在内）。
    File(PathBuf),
    /// 一张绑定表（`fylite/mds-bind/1`）或一份 A-Box 绑定文档（JSON / YAML），经 mdsip 读。
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
    /// 结构数组按哪个键对齐；`None` = 只按下标。
    pub merge_key: Option<String>,
    /// 只留这些：`ids` 或 `ids/子树/路径`；空 = 全留。
    pub select: Vec<String>,
    /// 出处里记的装置名（清单来路才有）。
    pub device: Option<String>,
}

/// 调用方在文档之上的覆盖（命令行 / C ABI / Python 都递这一个）。
#[derive(Debug, Clone, Default)]
pub struct Overrides {
    pub shot: Option<i64>,
    pub slots: Vec<(String, i64)>,
    pub time: Option<TimeSel>,
    pub max_points: Option<usize>,
    pub select: Vec<String>,
}

impl Overrides {
    /// 从一份 JSON 节点：`{"shot": N, "time": …, "max_points": N, "select": [...], "slots": {k: v}}`。
    pub fn from_node(n: &Node) -> Result<Overrides, String> {
        let m = match n.as_map() { Some(m) => m, None => return Ok(Overrides::default()) };
        let mut o = Overrides::default();
        if let Some(v) = m.get("shot") {
            o.shot = Some(v.as_i64().ok_or("shot is not an integer")?);
        }
        if let Some(v) = m.get("time") {
            if !v.is_null() {
                o.time = Some(TimeSel::from_node(v)?);
            }
        }
        if let Some(v) = m.get("max_points") {
            if !v.is_null() {
                o.max_points = Some(v.as_i64().filter(|x| *x > 0).ok_or("max_points is not a positive integer")? as usize);
            }
        }
        o.select = string_list(m.get("select"));
        if let Some(s) = m.get("slots").and_then(Node::as_map) {
            for (k, v) in s.iter() {
                o.slots.push((k.to_string(), v.as_i64().ok_or_else(|| format!("slot {k:?} is not an integer"))?));
            }
        }
        Ok(o)
    }

    pub fn apply(&self, a: &mut Assembly) {
        if let Some(s) = self.shot {
            a.params.shot = s;
        }
        for (k, v) in &self.slots {
            a.params.slots.insert(k.clone(), *v);
        }
        if self.time.is_some() {
            a.params.time = self.time.clone();
        }
        if self.max_points.is_some() {
            a.params.max_points = self.max_points;
        }
        if !self.select.is_empty() {
            a.select = self.select.clone();
        }
    }
}

fn string_list(n: Option<&Node>) -> Vec<String> {
    match n {
        Some(Node::List(items)) => items.iter().filter_map(|x| x.as_str().map(str::to_string)).collect(),
        Some(Node::Array(arr)) => arr.as_str().map(|s| s.to_vec()).unwrap_or_default(),
        Some(Node::Str(s)) => s.split(',').map(str::trim).filter(|s| !s.is_empty()).map(str::to_string).collect(),
        _ => Vec::new(),
    }
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

fn source_spec(alias: &str, uri: &str, dir: &Path) -> Result<SourceSpec, IoError> {
    Ok(if let Some(rest) = uri.strip_prefix("file:") {
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
    })
}

fn empty_assembly(dir: &Path) -> Assembly {
    Assembly { dir: dir.to_path_buf(), sources: BTreeMap::new(), params: Params::default(), merge: Vec::new(),
               overlays: Vec::new(), policy: MergePolicy::Overwrite, merge_key: Some("name".into()), select: Vec::new(), device: None }
}

/// 解析一份装配文档。
pub fn parse(doc: &Node, dir: &Path) -> Result<Assembly, IoError> {
    let m = doc.as_map().ok_or_else(|| IoError("an assembly document is a mapping".into()))?;
    let mut a = empty_assembly(dir);
    for (alias, v) in m.get("$source").and_then(Node::as_map).map(|s| s.iter().collect::<Vec<_>>()).unwrap_or_default() {
        let uri = v.as_str().ok_or_else(|| IoError(format!("$source {alias:?} is not a string")))?;
        a.sources.insert(alias.to_string(), source_spec(alias, uri, dir)?);
    }
    if let Some(p) = m.get("params").and_then(Node::as_map) {
        for (k, v) in p.iter() {
            match k {
                "shot" => a.params.shot = v.as_i64().ok_or_else(|| IoError("params.shot is not an integer".into()))?,
                "time" => if !v.is_null() { a.params.time = Some(TimeSel::from_node(v).map_err(|e| IoError(format!("params.time: {e}")))?) },
                "max_points" => a.params.max_points = v.as_i64().filter(|x| *x > 0).map(|x| x as usize),
                _ => if let Some(i) = v.as_i64() { a.params.slots.insert(k.to_string(), i); },
            }
        }
    }
    a.merge = string_list(m.get("merge"));
    if m.get("policy").and_then(Node::as_str) == Some("keep") {
        a.policy = MergePolicy::KeepExisting;
    }
    if let Some(k) = m.get("merge_key") {
        a.merge_key = match k { Node::Null | Node::Bool(false) => None, other => other.as_str().map(str::to_string) };
    }
    a.select = string_list(m.get("select"));
    for (k, v) in m.iter() {
        if fyodoc::is_semantic_key(k) || k.starts_with('$') || matches!(k, "params" | "merge" | "policy" | "merge_key" | "select") || k.contains(':') {
            continue;
        }
        if crate::ids_meta::IdsMeta::get(&fyodoc::split_ids_key(k).0).is_some() {
            a.overlays.push((k.to_string(), v.clone()));
        }
    }
    Ok(a)
}

/// 装配的产物：束 + 逐条的失败（源读不到、链接解析不了）+ 说明。
#[derive(Debug, Default)]
pub struct Assembled {
    pub bundle: Bundle,
    pub failures: Vec<String>,
    pub notes: Vec<String>,
    pub sources_used: Vec<String>,
}

/// 读源、合并、叠覆盖层、挑选。
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
                let doc = match io::read_node(path) { Ok(d) => d, Err(e) => { out.failures.push(format!("{alias}: {e}")); return None; } };
                let fallback = path.file_stem().map(|s| s.to_string_lossy().to_string()).unwrap_or_else(|| "unknown".into());
                let table = match mdsbind::parse_table(&doc).or_else(|_| mdsbind::table_from_abox(&doc, &fallback)) {
                    Ok(t) => t, Err(e) => { out.failures.push(format!("{alias}: {e}")); return None; }
                };
                for (ids, path, link, why) in &table.unsupported {
                    out.notes.push(format!("{alias}: {ids}/{path}: {link:?} not bound — {why}"));
                }
                match resolve_table(&table, host.as_deref(), *port, &a.params, connect) {
                    Ok(r) => {
                        out.failures.extend(r.failures.into_iter().map(|(ids, p, e)| format!("{alias}: {ids}/{p}: {e}")));
                        out.notes.extend(r.notes.into_iter().map(|n| format!("{alias}: {n}")));
                        r.bundle
                    }
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
            out.bundle.merge_with(b, a.policy, a.merge_key.as_deref());
            out.sources_used.push(alias.clone());
        }
    }
    //: overlays
    let mut live: BTreeMap<String, AnySession> = BTreeMap::new();
    for (key, overlay) in &a.overlays {
        let (ids, occ) = fyodoc::split_ids_key(key);
        let resolved = resolve_links(overlay, a, &mut load, &mut live, connect, &mut out);
        if out.bundle.get_occ(&ids, occ).is_none() {
            let d = fyodoc::from_dd(&ids, Node::map(), &format!("fylite:{ids}/assembly"), occ);
            out.bundle.push(d);
        }
        out.bundle.get_mut(&ids, occ).unwrap().merge_with(resolved, MergePolicy::Overwrite, a.merge_key.as_deref());
    }
    //: selection
    if !a.select.is_empty() {
        select(&mut out.bundle, &a.select);
    }
    //: provenance
    let mut prov = Node::map();
    let used: Vec<Node> = out.sources_used.iter().map(|s| Node::Str(s.clone())).collect();
    prov.set("merged", Node::List(used)).ok();
    prov.set("shot", Node::Int(a.params.shot)).ok();
    for (k, v) in &a.params.slots {
        prov.set(&format!("params/{k}"), Node::Int(*v)).ok();
    }
    if let Some(t) = &a.params.time {
        prov.set("params/time", t.to_node()).ok();
    }
    if let Some(m) = a.params.max_points {
        prov.set("params/max_points", Node::Int(m as i64)).ok();
    }
    if let Some(d) = &a.device {
        prov.set("device", Node::Str(d.clone())).ok();
    }
    if !a.select.is_empty() {
        prov.set("select", Node::List(a.select.iter().map(|s| Node::Str(s.clone())).collect())).ok();
    }
    for d in out.bundle.docs.iter_mut() {
        d.set("fylite:assembly", prov.clone()).ok();
    }
    out
}

/// `select`：`ids` 留整份，`ids/a/b` 留那棵子树（语义键、`ids_properties`、`time`、
/// `fylite:*` 总是留着；结构数组的每个元素照同一条余下路径修剪，`name` / `identifier`
/// 跟着留）。没被点名的 IDS 整份去掉。
pub fn select(bundle: &mut Bundle, keep: &[String]) {
    let mut docs = Vec::new();
    for doc in std::mem::take(&mut bundle.docs) {
        let ids = fyodoc::ids_of(&doc).unwrap_or_default();
        let key = fyodoc::ids_key(&ids, fyodoc::occurrence_of(&doc));
        let mine: Vec<&str> = keep.iter().filter_map(|k| {
            let (head, rest) = k.split_once('/').unwrap_or((k, ""));
            if head == ids || head == key { Some(rest) } else { None }
        }).collect();
        if mine.is_empty() {
            continue;
        }
        if mine.iter().any(|r| r.is_empty()) {
            docs.push(doc);
            continue;
        }
        docs.push(prune(doc, &mine, true));
    }
    bundle.docs = docs;
}

fn prune(n: Node, keep: &[&str], root: bool) -> Node {
    match n {
        Node::Map(m) => {
            let mut o = Map::new();
            for (k, v) in m.into_iter() {
                let always = if root {
                    fyodoc::is_semantic_key(&k) || k.contains(':') || k == "ids_properties" || k == "time" || k == "_ids"
                } else {
                    k == "name" || k == "identifier"
                };
                if always {
                    o.insert(k, v);
                    continue;
                }
                let rest: Vec<&str> = keep.iter().filter_map(|p| {
                    let (head, tail) = p.split_once('/').unwrap_or((p, ""));
                    if head == k || head == "*" { Some(tail) } else { None }
                }).collect();
                if rest.is_empty() {
                    continue;
                }
                if rest.iter().any(|r| r.is_empty()) {
                    o.insert(k, v);
                } else {
                    o.insert(k, prune(v, &rest, false));
                }
            }
            Node::Map(o)
        }
        Node::List(l) => Node::List(l.into_iter().map(|e| prune(e, keep, false)).collect()),
        other => other,
    }
}

fn resolve_table(table: &BindTable, host: Option<&str>, port: Option<u16>, params: &Params,
                 connect: Option<Connector<'_>>) -> Result<mdsbind::Resolved, String> {
    let connect = connect.ok_or("no network: MDSplus sources are disabled")?;
    let mut fails = Vec::new();
    let mut sessions: BTreeMap<String, AnySession> = BTreeMap::new();
    for (alias, src) in &table.sources {
        let (_, h, p) = mdsbind::parse_uri(&src.uri);
        let h = host.map(str::to_string).or(h).unwrap_or_else(|| "127.0.0.1".into());
        let p = port.or(p).unwrap_or(8000);
        match connect(&h, p, &src.tree) {
            Some(s) => { sessions.insert(alias.clone(), s); }
            None => fails.push((String::new(), alias.clone(), format!("cannot connect to {h}:{p}"))),
        }
    }
    let mut r = mdsbind::resolve(table, &mut sessions, params, None);
    r.failures.splice(0..0, fails);
    Ok(r)
}

fn resolve_links(n: &Node, a: &Assembly, load: &mut dyn FnMut(&str, &mut Assembled) -> Option<Bundle>,
                 live: &mut BTreeMap<String, AnySession>,
                 connect: Option<Connector<'_>>, out: &mut Assembled) -> Node {
    match n {
        Node::Map(m) => {
            if let Some(link) = m.get("$link").and_then(Node::as_str) {
                return match resolve_one(link, a, load, live, connect, out) {
                    Some(v) => v,
                    None => Node::Null,
                };
            }
            let mut o = Map::new();
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
               live: &mut BTreeMap<String, AnySession>,
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
            let mut notes = Vec::new();
            let r = mdsbind::read_link(s, tree, a.params.shot, rest, &a.params, &mut notes);
            out.notes.extend(notes.into_iter().map(|n| format!("{alias}: {n}")));
            match r {
                Ok(v) => Some(v),
                Err(e) => { out.failures.push(format!("{alias}:{rest}: {e}")); None }
            }
        }
        None => { out.failures.push(format!("$link {link:?}: no source {alias:?}")); None }
    }
}

/// 读装配文档（JSON 或 YAML）并执行（源相对文档所在目录）。
pub fn assemble_file(path: &Path, connect: Option<Connector<'_>>, overrides: &Overrides) -> Result<Assembled, IoError> {
    let doc = io::read_node(path)?;
    let dir = path.parent().map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let mut a = parse(&doc, &dir)?;
    overrides.apply(&mut a);
    Ok(assemble(&a, connect))
}

// --------------------------------------------------------------------------
// the machine manifest (fydata `machine.yaml`) as a source of assemblies
// --------------------------------------------------------------------------

/// 从装置清单摊出一份装配：每个 IDS 一份几何（静态文件）+ 一份绑定（MDSplus 绑定文档）。
///
/// 清单里看的字段（fydata `machine/tokamak/<dev>/machine.yaml`，起步草稿的形）：
///
/// * `epochs[].valid_shots: [lo, hi|null]` + `epochs[].static` + `epochs[].ids.<ids>`：
///   含 `shot` 的那层；值是文件名（相对 `static`）或 `"@provider"`；
/// * `providers.<ids>.default` / `.available.<name>: {backend, path}`：`static` 的是几何，
///   `mdsplus` 的是绑定；`provider` 点名哪个，缺省取 `default`；
/// * `bindings.mdsplus.ids.<ids>`（相对 `bindings.mdsplus.root`）：缺省的绑定文档。
///
/// 没有几何或没有绑定都不是错——有什么装什么，缺的记在 `notes` 里。
pub fn from_manifest(manifest: &Path, ids: &[&str], provider: Option<&str>, host: Option<&str>, port: Option<u16>,
                     overrides: &Overrides) -> Result<(Assembly, Vec<String>), IoError> {
    let doc = io::read_node(manifest)?;
    let m = doc.as_map().ok_or_else(|| IoError(format!("{}: a machine manifest is a mapping", manifest.display())))?;
    let dir = manifest.parent().map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let mut a = empty_assembly(&dir);
    let mut notes = Vec::new();
    overrides.apply(&mut a);
    a.device = m.get("device").and_then(Node::as_str).map(str::to_string);
    let shot = a.params.shot;
    //: the epoch that holds the shot
    let epoch = m.get("epochs").and_then(Node::as_list).and_then(|eps| eps.iter().find(|e| {
        let range = e.get("valid_shots").map(|v| match v {
            Node::List(l) => l.iter().map(|x| x.as_i64()).collect::<Vec<_>>(),
            other => other.to_f64_vec().unwrap_or_default().into_iter().map(|x| Some(x as i64)).collect(),
        }).unwrap_or_default();
        let lo = range.first().copied().flatten().unwrap_or(i64::MIN);
        let hi = range.get(1).copied().flatten().unwrap_or(i64::MAX);
        shot >= lo && shot <= hi
    }));
    for &one in ids {
        let mut geometry: Option<PathBuf> = None;
        let mut bind: Option<PathBuf> = None;
        let providers = m.get("providers").and_then(|p| p.get(one));
        let available = providers.and_then(|p| p.get("available"));
        let pick_provider = |name: &str| -> Option<(String, PathBuf)> {
            let v = available?.get(name)?;
            let backend = v.get("backend").and_then(Node::as_str).unwrap_or("static").to_string();
            let path = v.get("path").and_then(Node::as_str)?;
            Some((backend, dir.join(path)))
        };
        //: geometry: the epoch's file, or the provider's static file
        match epoch.and_then(|e| e.get(&format!("ids/{one}"))).and_then(Node::as_str) {
            Some("@provider") | None => {
                let name = provider.map(str::to_string).or_else(|| providers.and_then(|p| p.get("default")).and_then(Node::as_str).map(str::to_string));
                if let Some(name) = &name {
                    match pick_provider(name) {
                        Some((backend, path)) if backend == "static" => geometry = Some(path),
                        Some((_, path)) => bind = Some(path),
                        None => notes.push(format!("{one}: provider {name:?} is not in the manifest")),
                    }
                    //: a named mdsplus provider still wants the default static geometry
                    if geometry.is_none() && bind.is_some() {
                        if let Some(d) = providers.and_then(|p| p.get("default")).and_then(Node::as_str) {
                            if let Some((backend, path)) = pick_provider(d) {
                                if backend == "static" { geometry = Some(path); }
                            }
                        }
                    }
                } else if epoch.is_none() {
                    notes.push(format!("{one}: no epoch holds shot {shot} and no provider is named"));
                }
            }
            Some(file) => {
                let root = epoch.and_then(|e| e.get("static")).and_then(Node::as_str).unwrap_or("");
                geometry = Some(dir.join(root).join(file));
            }
        }
        if bind.is_none() {
            //: (`bindings.mdsplus.{root, ids}` looked up in two steps: build.sh greps the
            //: release .so for `$HOME`, and a literal `…/root` would trip it)
            let mds = doc.get("bindings/mdsplus");
            if let Some(file) = mds.and_then(|b| b.get(&format!("ids/{one}"))).and_then(Node::as_str) {
                let root = mds.and_then(|b| b.get("root")).and_then(Node::as_str).unwrap_or("");
                bind = Some(dir.join(root).join(file));
            }
        }
        if let Some(g) = geometry {
            let alias = format!("geometry:{one}");
            a.sources.insert(alias.clone(), SourceSpec::File(g));
            a.merge.push(alias);
        } else {
            notes.push(format!("{one}: no static geometry in the manifest"));
        }
        if let Some(b) = bind {
            let alias = format!("bind:{one}");
            a.sources.insert(alias.clone(), SourceSpec::MdsBind { path: b, host: host.map(str::to_string), port });
            a.merge.push(alias);
        } else {
            notes.push(format!("{one}: no MDSplus binding in the manifest"));
        }
    }
    //: geometry first, bindings after: measured values override description
    a.merge.sort_by_key(|s| if s.starts_with("bind:") { 1 } else { 0 });
    if a.select.is_empty() {
        a.select = ids.iter().map(|s| s.to_string()).collect();
    }
    Ok((a, notes))
}

/// 原生的连接办法：TCP 到 host:port，登录 `user`。
#[cfg(not(target_arch = "wasm32"))]
pub fn tcp_connector(user: String, timeout_ms: u64) -> impl Fn(&str, u16, &str) -> Option<AnySession> {
    move |host: &str, port: u16, _tree: &str| {
        let io = crate::mdsip::tcp::TcpTransport::connect(host, port, Some(std::time::Duration::from_millis(timeout_ms))).ok()?;
        let client = crate::mdsip::Client::login(io, &user).ok()?;
        Some(Box::new(mdsbind::Session::new(client)) as AnySession)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("fylite_data_asm_{}_{name}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn files_merge_and_links_pull_leaves_from_them() {
        let dir = tmp("files");
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
        let r = assemble_file(&dir.join("asm.jsonld"), None, &Overrides::default()).unwrap();
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
        let r2 = assemble_file(&dir.join("bad.jsonld"), None, &Overrides::default()).unwrap();
        assert_eq!(r2.failures.len(), 1);
        assert!(r2.failures[0].contains("not found"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn yaml_geometry_merges_by_name_and_select_prunes() {
        let dir = tmp("yaml");
        //: geometry as fydata writes it, and a second file keyed by name in another order
        std::fs::write(dir.join("pcs.yaml"), "_ids: magnetics\nb_field_pol_probe:\n- name: PCBPV1T\n  position:\n  - r: 1.29\n    z: 0.0\n  toroidal_angle: 90.0\n- name: PCBPV2T\n  position:\n  - r: 1.29\n    z: 0.248\n  toroidal_angle: 90.0\nflux_loop:\n- name: PCFL1\n  position:\n  - r: 1.0\n    z: 0.5\n").unwrap();
        std::fs::write(dir.join("calib.yaml"), "_ids: magnetics\nb_field_pol_probe:\n- name: PCBPV2T\n  field:\n    data: [0.1, 0.2]\n- name: PCBPV1T\n  field:\n    data: [0.3, 0.4]\n").unwrap();
        let asm = "$source:\n  geo: file:pcs.yaml\n  cal: file:calib.yaml\nparams:\n  shot: 138569\n  time: [4.0, 5.0]\n  max_points: 100\nmerge: [geo, cal]\nselect: [magnetics/b_field_pol_probe/field, magnetics/b_field_pol_probe/position]\n";
        std::fs::write(dir.join("asm.yaml"), asm).unwrap();
        let r = assemble_file(&dir.join("asm.yaml"), None, &Overrides::default()).unwrap();
        assert!(r.failures.is_empty(), "{:?}", r.failures);
        let m = r.bundle.get("magnetics").unwrap();
        //: aligned by name, not by position in the list
        assert_eq!(m.get("b_field_pol_probe/0/name").and_then(Node::as_str), Some("PCBPV1T"));
        assert_eq!(m.get("b_field_pol_probe/0/field/data").and_then(Node::to_f64_vec), Some(vec![0.3, 0.4]));
        assert_eq!(m.get("b_field_pol_probe/1/field/data").and_then(Node::to_f64_vec), Some(vec![0.1, 0.2]));
        assert_eq!(m.get("b_field_pol_probe/1/position/0/z").and_then(Node::as_f64), Some(0.248));
        //: `select` kept the probes' field/position (and names), dropped angles and loops
        assert!(m.get("b_field_pol_probe/0/toroidal_angle").is_none());
        assert!(m.get("flux_loop").is_none());
        assert_eq!(m.get("fylite:assembly/params/time/stop").and_then(Node::as_f64), Some(5.0));
        assert_eq!(m.get("fylite:assembly/params/max_points").and_then(Node::as_i64), Some(100));
        //: overrides win over the document
        let o = Overrides::from_node(&crate::json::parse(r#"{"shot": 7, "time": "4.5", "select": ["magnetics"]}"#).unwrap()).unwrap();
        let r2 = assemble_file(&dir.join("asm.yaml"), None, &o).unwrap();
        let m2 = r2.bundle.get("magnetics").unwrap();
        assert_eq!(m2.get("fylite:assembly/shot").and_then(Node::as_i64), Some(7));
        assert_eq!(m2.get("fylite:assembly/params/time").and_then(Node::as_f64), Some(4.5));
        assert!(m2.get("flux_loop").is_some());
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn a_manifest_flattens_into_geometry_plus_binding_sources() {
        let dir = tmp("manifest");
        std::fs::create_dir_all(dir.join("static")).unwrap();
        std::fs::create_dir_all(dir.join("bind")).unwrap();
        std::fs::write(dir.join("static/pcs.yaml"), "_ids: magnetics\nb_field_pol_probe:\n- name: P1\n  toroidal_angle: 90.0\n").unwrap();
        std::fs::write(dir.join("static/wall.yaml"), "_ids: wall\ndescription_2d:\n- type:\n    name: limiter\n").unwrap();
        std::fs::write(dir.join("bind/magnetics.yaml"), "$source:\n  pcs_east: mdsplus://127.0.0.1/mdsplus/~t?shot={shot}&tree_name=pcs_east\n_ids: magnetics\nb_field_pol_probe:\n- id: '0'\n  field:\n    data:\n      $link: pcs_east:DATA(\\PCBPV1T)\n").unwrap();
        std::fs::write(dir.join("machine.yaml"), "device: EAST\nepochs:\n  - id: legacy\n    valid_shots: [0, null]\n    static: static\n    ids:\n      wall: wall.yaml\n      magnetics: \"@provider\"\nproviders:\n  magnetics:\n    default: pcs\n    available:\n      pcs: { backend: static, path: static/pcs.yaml }\n      efit: { backend: mdsplus, path: bind/efit.yaml }\nbindings:\n  mdsplus:\n    root: bind\n    ids:\n      magnetics: magnetics.yaml\n").unwrap();
        let o = Overrides { shot: Some(138569), time: Some(TimeSel::Window { t0: 4.0, t1: 5.0 }), ..Default::default() };
        let (a, notes) = from_manifest(&dir.join("machine.yaml"), &["magnetics", "wall"], None, Some("mds.example.org"), Some(8000), &o).unwrap();
        assert_eq!(a.device.as_deref(), Some("EAST"));
        assert_eq!(a.merge, vec!["geometry:magnetics", "geometry:wall", "bind:magnetics"]);
        assert!(matches!(a.sources.get("bind:magnetics"), Some(SourceSpec::MdsBind { host: Some(h), port: Some(8000), .. }) if h == "mds.example.org"));
        assert!(notes.iter().any(|n| n.contains("wall: no MDSplus binding")), "{notes:?}");
        assert_eq!(a.select, vec!["magnetics", "wall"]);
        //: without a network the binding is a named failure; the geometry still comes through
        let r = assemble(&a, None);
        assert!(r.failures.iter().any(|f| f.contains("no network")), "{:?}", r.failures);
        let m = r.bundle.get("magnetics").unwrap();
        assert_eq!(m.get("b_field_pol_probe/0/name").and_then(Node::as_str), Some("P1"));
        assert_eq!(m.get("fylite:assembly/device").and_then(Node::as_str), Some("EAST"));
        assert!(r.bundle.get("wall").is_some());
        //: naming the mdsplus provider swaps the binding and keeps the default geometry
        let (a2, _) = from_manifest(&dir.join("machine.yaml"), &["magnetics"], Some("efit"), None, None, &o).unwrap();
        assert!(matches!(a2.sources.get("bind:magnetics"), Some(SourceSpec::MdsBind { path, .. }) if path.ends_with("bind/efit.yaml")));
        assert!(a2.sources.contains_key("geometry:magnetics"));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
