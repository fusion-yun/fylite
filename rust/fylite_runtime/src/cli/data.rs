//! `data` — the data layer's command line: what a file is, format
//! conversion, merging, assembling several data sources by a JSON-LD / YAML
//! document, fetching a shot from a fydata machine manifest.  What each
//! subcommand TAKES is in `_cli.json` (`data`); this module is only what
//! they DO.
//!
//! Reached as `fylite data …` (the Python console script, which hands the
//! words on verbatim) or as `fylite data …` (the one executable) —
//! the same code either way.  ★2026-09-03 the `fylite-data` alias binary was
//! retired: one executable carries every command word.
//!
//! `--time` is `4.5` (one point), `4:5` (a window) or `4,4.5,5` (a list of
//! points); MDSplus sources are windowed on their own time base and the
//! slicing is done server-side.  `fetch` flattens a fydata machine manifest
//! into «geometry + bindings» and assembles — for instance EAST shot 138569,
//! 4–5 s, magnetics:
//!
//! ```text
//! fylite data fetch --machine fydata/machine/tokamak/east/machine.yaml --ids magnetics \
//!                  --shot 138569 --time 4:5 --host mds.ipp.ac.cn -o east_138569_magnetics.json
//! ```
//!
//! ★Every MDSplus read goes through `fylite_runtime::mdsip`'s read-only
//! client; there is no expression endpoint here — `assemble`'s `$link`
//! expressions are decomposed into «verb + node path + integer» by
//! `mdsbind::decompose` before anything is sent, and what cannot be
//! decomposed is listed among the failures.

use super::Args;
use crate::facts;
use crate::detect::Format;
use crate::document::{MergePolicy, Node};
use crate::fyodoc::{self, Bundle};
use crate::io::{self, Layout};
use std::path::{Path, PathBuf};

fn die(msg: &str) -> ! {
    eprintln!("fylite data: {msg}");
    std::process::exit(2);
}

fn layout_of(args: &Args) -> Layout {
    match args.flag("layout") {
        None => Layout::Fyo,
        Some(s) => Layout::parse(s).unwrap_or_else(|| die(&format!("--layout {s:?}: fyo or imas"))),
    }
}

fn format_of(args: &Args) -> Option<Format> {
    args.flag("to").map(|s| {
        Format::parse(s).unwrap_or_else(|| die(&format!("--to {s:?}: json, geqdsk, hdf5, netcdf or imas-hdf5")))
    })
}

fn select_ids(bundle: Bundle, args: &Args) -> Bundle {
    match args.flag("ids") {
        None => bundle,
        Some(list) => {
            let want: Vec<&str> = list.split(',').map(str::trim).collect();
            Bundle {
                docs: bundle
                    .docs
                    .into_iter()
                    .filter(|d| fyodoc::ids_of(d).map(|i| want.contains(&i.as_str())).unwrap_or(false))
                    .collect(),
            }
        }
    }
}

fn describe(n: &Node) -> String {
    match n {
        Node::Array(a) => format!(
            "{}{:?}",
            match &a.data {
                crate::document::ArrayData::F64(_) => "f64",
                crate::document::ArrayData::I64(_) => "i64",
                _ => "str",
            },
            a.shape
        ),
        Node::Float(x) => format!("{x}"),
        Node::Int(x) => format!("{x}"),
        Node::Str(s) => format!("{s:?}"),
        Node::Bool(b) => format!("{b}"),
        Node::Null => "null".into(),
        _ => "…".into(),
    }
}

fn info(args: &Args) {
    let path = PathBuf::from(args.flag("file").unwrap_or_else(|| die("info: which path?")));
    let d = io::detect(&path).unwrap_or_else(|e| die(&e.to_string()));
    let bundle = io::read_as(&path, d.format).unwrap_or_else(|e| die(&e.to_string()));
    if args.has("json") {
        let mut out = Node::map();
        out.set("format", d.format.name().into()).unwrap();
        out.set("layout", d.layout.name().into()).unwrap();
        let mut docs = Vec::new();
        for doc in &bundle.docs {
            let mut m = Node::map();
            m.set("ids", fyodoc::ids_of(doc).unwrap_or_default().into()).unwrap();
            m.set("occurrence", Node::Int(fyodoc::occurrence_of(doc))).unwrap();
            let mut leaves = Node::map();
            for (p, v) in doc.leaves() {
                leaves.set(&p.replace('/', "\u{1}"), describe(v).into()).ok();
            }
            //: keys with `/` were escaped above to keep them flat; restore
            let leaves = match leaves {
                Node::Map(m) => Node::Map(m.into_iter().map(|(k, v)| (k.replace('\u{1}', "/"), v)).collect()),
                other => other,
            };
            m.set("leaves", leaves).unwrap();
            docs.push(m);
        }
        out.set("documents", Node::List(docs)).unwrap();
        print!("{}", crate::json::to_string(&out, true));
        return;
    }
    println!("{}: {} ({} layout)", path.display(), d.format.name(), d.layout.name());
    for doc in &bundle.docs {
        let ids = fyodoc::ids_of(doc).unwrap_or_else(|| "?".into());
        let leaves = doc.leaves();
        println!("  {ids} (occurrence {}): {} leaves", fyodoc::occurrence_of(doc), leaves.len());
        for (p, v) in leaves.iter().take(40) {
            println!("    {p}: {}", describe(v));
        }
        if leaves.len() > 40 {
            println!("    … {} more", leaves.len() - 40);
        }
    }
}

fn dump(args: &Args) {
    let path = PathBuf::from(args.flag("file").unwrap_or_else(|| die("dump: which path?")));
    if args.has("raw") {
        //: the parsed tree as it is — for JSON / YAML that are not documents
        //: (a machine manifest, an assembly), and for checking the YAML reader
        let node = io::read_node(&path).unwrap_or_else(|e| die(&e.to_string()));
        let node = match args.flag("path") {
            Some(p) => node
                .walk(p, false)
                .unwrap_or_else(|| die(&format!("no {p} in {}", path.display())))
                .clone(),
            None => node,
        };
        print!("{}", crate::json::to_string(&node, !args.has("compact")));
        return;
    }
    let bundle = io::read(&path).unwrap_or_else(|e| die(&e.to_string()));
    let bundle = select_ids(bundle, args);
    let node = match args.flag("path") {
        Some(p) => {
            //: `<ids>[_<occ>]/a/b` first (the C ABI's path form), then the bare
            //: container path (a single document is not wrapped)
            let (head, rest) = p.split_once('/').unwrap_or((p, ""));
            let (ids, occ) = fyodoc::split_ids_key(head);
            let by_ids = bundle
                .get_occ(&ids, occ)
                .and_then(|d| if rest.is_empty() { Some(d) } else { d.walk(rest, true) });
            let root = bundle.to_node();
            match by_ids.cloned().or_else(|| root.walk(p, true).cloned()) {
                Some(n) => n,
                None => die(&format!("no {p} in {}", path.display())),
            }
        }
        None => bundle.to_node(),
    };
    print!("{}", crate::json::to_string(&node, !args.has("compact")));
}

fn report(rep: &io::WriteReport, out: &Path) {
    eprintln!(
        "wrote {} as {} ({} layout)",
        out.display(),
        rep.format.map(|f| f.name()).unwrap_or("?"),
        rep.layout.map(|l| l.name()).unwrap_or("?")
    );
    for d in &rep.synthesized_docs {
        eprintln!("  synthesized {d}");
    }
    for (key, r) in &rep.dd {
        let dropped: Vec<&String> = r.dropped.iter().filter(|p| !p.starts_with('@')).collect();
        if !dropped.is_empty() || !r.promoted.is_empty() || !r.synthesized.is_empty() {
            eprintln!(
                "  {key}: dropped {} non-DD path(s){}; promoted {:?}; synthesized {:?}",
                dropped.len(),
                if dropped.is_empty() { String::new() } else { format!(" {:?}", dropped) },
                r.promoted,
                r.synthesized
            );
        }
    }
}

fn convert(args: &Args) {
    let inp = PathBuf::from(args.flag("input").unwrap_or_else(|| die("convert: input path?")));
    let out = PathBuf::from(args.flag("output").unwrap_or_else(|| die("convert: output path?")));
    let bundle = select_ids(io::read(&inp).unwrap_or_else(|e| die(&e.to_string())), args);
    let rep = io::write(&out, &bundle, format_of(args), layout_of(args)).unwrap_or_else(|e| die(&e.to_string()));
    report(&rep, &out);
}

fn merge(args: &Args) {
    let out = PathBuf::from(args.flag("out").unwrap_or_else(|| die("merge: -o output?")));
    let paths: Vec<PathBuf> = args.all("inputs").iter().map(PathBuf::from).collect();
    if paths.is_empty() {
        die("merge: which inputs?");
    }
    let policy = if args.has("keep") { MergePolicy::KeepExisting } else { MergePolicy::Overwrite };
    let refs: Vec<&Path> = paths.iter().map(PathBuf::as_path).collect();
    let key = match args.flag("merge-key") {
        None => Some("name".to_string()),
        Some("none") | Some("") => None,
        Some(k) => Some(k.to_string()),
    };
    let bundle = io::merge_paths_with(&refs, policy, key.as_deref()).unwrap_or_else(|e| die(&e.to_string()));
    let rep = io::write(&out, &bundle, format_of(args), layout_of(args)).unwrap_or_else(|e| die(&e.to_string()));
    report(&rep, &out);
}

/// The overrides given on the command line (`assemble` and `fetch` share them).
#[cfg(feature = "mdsip")]
fn overrides(args: &Args) -> crate::assembly::Overrides {
    use crate::mdsbind::TimeSel;
    let mut o = crate::assembly::Overrides {
        shot: args.flag("shot").map(|s| s.parse::<i64>().unwrap_or_else(|_| die("--shot wants an integer"))),
        time: args.flag("time").map(|t| TimeSel::parse(t).unwrap_or_else(|e| die(&e))),
        max_points: args.flag("max-points").map(|m| {
            m.parse::<usize>()
                .ok()
                .filter(|x| *x > 0)
                .unwrap_or_else(|| die("--max-points wants a positive integer"))
        }),
        ..Default::default()
    };
    o.slots = args
        .all("param")
        .iter()
        .map(|kv| {
            let (k, v) = kv.split_once('=').unwrap_or_else(|| die("--param k=v"));
            (k.to_string(), v.parse::<i64>().unwrap_or_else(|_| die("--param values are integers")))
        })
        .collect();
    o.select = args
        .all("select")
        .iter()
        .flat_map(|s| s.split(','))
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect();
    o
}

#[cfg(feature = "mdsip")]
fn mds_user(args: &Args) -> String {
    args.flag("mds-user")
        .map(str::to_string)
        .unwrap_or_else(|| std::env::var("USER").unwrap_or_else(|_| "nobody".into()))
}

#[cfg(feature = "mdsip")]
fn timeout(args: &Args) -> u64 {
    args.flag("timeout-ms").map(|t| t.parse().unwrap_or(10_000)).unwrap_or(10_000)
}

#[cfg(feature = "mdsip")]
fn write_assembled(args: &Args, r: &crate::assembly::Assembled, out: &Path) {
    for n in &r.notes {
        eprintln!("  note: {n}");
    }
    for f in &r.failures {
        eprintln!("  failed: {f}");
    }
    let rep = io::write(out, &r.bundle, format_of(args), layout_of(args)).unwrap_or_else(|e| die(&e.to_string()));
    report(&rep, out);
    if !r.failures.is_empty() {
        std::process::exit(1);
    }
}

#[cfg(feature = "mdsip")]
fn assemble(args: &Args) {
    let asm = PathBuf::from(args.flag("assembly").unwrap_or_else(|| die("assemble: which assembly document?")));
    let out = PathBuf::from(args.flag("out").unwrap_or_else(|| die("assemble: -o output?")));
    let connector = crate::assembly::tcp_connector(mds_user(args), timeout(args));
    let r = crate::assembly::assemble_file(&asm, Some(&connector), &overrides(args)).unwrap_or_else(|e| die(&e.to_string()));
    write_assembled(args, &r, &out);
}

#[cfg(feature = "mdsip")]
fn fetch(args: &Args) {
    let manifest = PathBuf::from(args.flag("machine").unwrap_or_else(|| die("fetch: --machine <machine.yaml>?")));
    let ids: Vec<&str> = args
        .flag("ids")
        .unwrap_or_else(|| die("fetch: --ids a,b?"))
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .collect();
    let o = overrides(args);
    if o.shot.is_none() {
        die("fetch: --shot N?");
    }
    let port = args.flag("port").map(|p| p.parse::<u16>().unwrap_or_else(|_| die("--port wants a port number")));
    let (a, notes) =
        crate::assembly::from_manifest(&manifest, &ids, args.flag("provider"), args.flag("host"), port, &o)
            .unwrap_or_else(|e| die(&e.to_string()));
    if args.has("dry-run") {
        println!("device: {}", a.device.as_deref().unwrap_or("?"));
        println!("shot: {}  time: {:?}  max_points: {:?}", a.params.shot, a.params.time, a.params.max_points);
        for alias in &a.merge {
            println!("  {alias}: {:?}", a.sources.get(alias));
        }
        println!("select: {:?}", a.select);
        for n in &notes {
            println!("  note: {n}");
        }
        return;
    }
    let out = PathBuf::from(args.flag("out").unwrap_or_else(|| die("fetch: -o output?")));
    let connector = crate::assembly::tcp_connector(mds_user(args), timeout(args));
    let mut r = crate::assembly::assemble(&a, Some(&connector));
    r.notes.splice(0..0, notes);
    write_assembled(args, &r, &out);
}

#[cfg(not(feature = "mdsip"))]
fn assemble(_args: &Args) {
    die("assemble needs the `mdsip` feature (this build has no MDSplus client)");
}

#[cfg(not(feature = "mdsip"))]
fn fetch(_args: &Args) {
    die("fetch needs the `mdsip` feature (this build has no MDSplus client)");
}

fn tables() {
    println!("DD {}", crate::ids_tables::DD_VERSION);
    for n in crate::ids_meta::IdsMeta::names() {
        println!("  {n}");
    }
}

extern "C" {
    fn signal(sig: i32, handler: usize) -> usize;
}

/// Run one `data` subcommand (`args.command == ["data", <sub>]`).
pub fn run(args: &Args) {
    //: a closed pipe ends a listing (`tables | head`), it is not a panic
    unsafe { signal(13, 0) };
    apply_facts(args);
    match args.word(1) {
        "facts" => facts_face(args),
        "info" => info(args),
        "dump" => dump(args),
        "convert" => convert(args),
        "merge" => merge(args),
        "assemble" => assemble(args),
        "fetch" => fetch(args),
        "tables" => tables(),
        other => die(&format!("unknown data subcommand {other:?}; --help has the usage")),
    }
}

/// `--facts` -> 本进程的搜索路径，在任何东西读它之前。
///
/// ★★组级选项，`data` 与 `case` 都有（`_cli.json` 一处声明，两个宿主各自建出）。
/// **前置而不是替换**：给了自己的根，自带的与检出的仍在其后兜底。
/// ★被指名却不在的根**当场说**：等到某个条目找不到才报「没有这台机器」，会把
/// 「路径写错了」说成「语料里没有它」——两句话指向完全不同的处置。
pub fn apply_facts(args: &Args) {
    let given = args.all("facts");
    if !given.is_empty() {
        facts::use_roots(Some(facts::parse_roots(given)));
    }
    for line in facts::problems() {
        eprintln!("fylite: {line}");
    }
}

/// `fylite data facts [--roots] [域]` —— 搜索路径的问答面。
///
/// ★★多源之后「这份文档是哪来的」不再显然，所以它要有一个**问得出来**的答案：
/// 没有它，一次答案不对的运行只能靠猜是哪个根供的。
fn facts_face(args: &Args) {
    let roots = facts::roots();
    //: ★位置参数按**名字**取（`flag("domain")`），不是按命令词的深度——
    //: `word(2)` 数的是子命令那一串，位置参数不在其中。
    let domain = args.flag("domain").unwrap_or("");
    if args.has("roots") || domain.is_empty() {
        if roots.is_empty() {
            eprintln!(
                "fylite: facts 搜索路径上没有语料 —— 给 --facts，或设 ${}，\n\
                 或在检出里跑 python3 tools/abox-to-facts.py --all",
                facts::FACTS_ENV
            );
        }
        for (i, r) in roots.iter().enumerate() {
            println!("{}. {}", i + 1, r.display());
        }
        if args.has("roots") {
            return;
        }
        for d in facts::domains() {
            println!("   {d}: {} 条", facts::entries(&d).len());
        }
        return;
    }
    let items = facts::entries(domain);
    if items.is_empty() {
        eprintln!("fylite: 域 {domain:?} 在搜索路径上没有条目");
        return;
    }
    //: 逐条把「谁供的」印出来——这正是多源要能回答的那个问题。
    for e in items {
        let rights = if e.rights_path().is_some() { "" } else { "  (无许可账)" };
        println!("{:<16} {}{}", e.ident, e.root.display(), rights);
    }
}
