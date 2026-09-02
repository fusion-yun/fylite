//! `fylite-data` —— 数据层的命令行。看一眼文件是什么、格式互转、合并、按 JSON-LD 装配。
//!
//! ```text
//! fylite-data info <path> [--json]                    识别格式与布局，列出 IDS 与叶子
//! fylite-data dump <path> [--path a/b/c] [--ids x]    以 JSON 打印一棵子树
//! fylite-data convert <in> <out> [--to FMT] [--layout fyo|imas] [--ids a,b]
//! fylite-data merge <in>... -o <out> [--layout ..] [--keep]
//! fylite-data assemble <asm.jsonld> -o <out> [--shot N] [--param k=v] [--layout ..]
//!                      [--mds-user U] [--timeout-ms T]
//! fylite-data tables                                  内置的 DD 表：版本与 IDS 名
//! ```
//!
//! ★所有对 MDSplus 的读都经 `fylite_data::mdsip` 那个只读客户端；这里没有取表达式
//! 的入口——`assemble` 的 `$link` 表达式在 `mdsbind::decompose` 分解成
//! 「动词 + 节点路径 + 整数」才发出去，分解不了的列在失败里。

use fylite_data::document::{MergePolicy, Node};
use fylite_data::detect::Format;
use fylite_data::fyodoc::{self, Bundle};
use fylite_data::io::{self, Layout};
use std::path::{Path, PathBuf};

const HELP: &str = "fylite-data — fylite 数据层：不同数据源 ↔ fyo 文档

  fylite-data info <path> [--json]
  fylite-data dump <path> [--ids IDS] [--path A/B/C] [--compact]
  fylite-data convert <in> <out> [--to json|geqdsk|hdf5|netcdf|imas-hdf5] [--layout fyo|imas] [--ids a,b]
  fylite-data merge <in>... -o <out> [--layout fyo|imas] [--keep]
  fylite-data assemble <asm.jsonld> -o <out> [--shot N] [--param k=v]... [--layout fyo|imas]
                       [--mds-user U] [--timeout-ms T]
  fylite-data tables

格式看内容识别（HDF5 / netCDF / IMAS 目录 / JSON / g-file / a-file）；写文件按扩展名，
或 --to。--layout imas 写 imas-python / imas-core 读得回的形（IMAS HDF5 是一个目录）。";

fn die(msg: &str) -> ! {
    eprintln!("fylite-data: {msg}");
    std::process::exit(2);
}

struct Args {
    positional: Vec<String>,
    flags: Vec<(String, Option<String>)>,
}

impl Args {
    fn parse(argv: &[String]) -> Args {
        let mut positional = Vec::new();
        let mut flags = Vec::new();
        let mut i = 0;
        while i < argv.len() {
            let a = &argv[i];
            if let Some(name) = a.strip_prefix("--") {
                let takes_value = matches!(name, "to" | "layout" | "ids" | "path" | "shot" | "param" | "mds-user" | "timeout-ms" | "o" | "output");
                if takes_value {
                    i += 1;
                    flags.push((name.to_string(), argv.get(i).cloned()));
                } else {
                    flags.push((name.to_string(), None));
                }
            } else if a == "-o" {
                i += 1;
                flags.push(("o".to_string(), argv.get(i).cloned()));
            } else {
                positional.push(a.clone());
            }
            i += 1;
        }
        Args { positional, flags }
    }

    fn flag(&self, name: &str) -> Option<&str> {
        self.flags.iter().rev().find(|(n, _)| n == name).and_then(|(_, v)| v.as_deref())
    }

    fn has(&self, name: &str) -> bool {
        self.flags.iter().any(|(n, _)| n == name)
    }

    fn all(&self, name: &str) -> Vec<&str> {
        self.flags.iter().filter(|(n, _)| n == name).filter_map(|(_, v)| v.as_deref()).collect()
    }
}

fn layout_of(args: &Args) -> Layout {
    match args.flag("layout") {
        None => Layout::Fyo,
        Some(s) => Layout::parse(s).unwrap_or_else(|| die(&format!("--layout {s:?}: fyo or imas"))),
    }
}

fn select_ids(bundle: Bundle, args: &Args) -> Bundle {
    match args.flag("ids") {
        None => bundle,
        Some(list) => {
            let want: Vec<&str> = list.split(',').map(str::trim).collect();
            Bundle { docs: bundle.docs.into_iter().filter(|d| fyodoc::ids_of(d).map(|i| want.contains(&i.as_str())).unwrap_or(false)).collect() }
        }
    }
}

fn describe(n: &Node) -> String {
    match n {
        Node::Array(a) => format!("{}{:?}", match &a.data {
            fylite_data::document::ArrayData::F64(_) => "f64", fylite_data::document::ArrayData::I64(_) => "i64", _ => "str" }, a.shape),
        Node::Float(x) => format!("{x}"),
        Node::Int(x) => format!("{x}"),
        Node::Str(s) => format!("{s:?}"),
        Node::Bool(b) => format!("{b}"),
        Node::Null => "null".into(),
        _ => "…".into(),
    }
}

fn info(args: &Args) {
    let path = PathBuf::from(args.positional.get(1).unwrap_or_else(|| die("info: which path?")));
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
        print!("{}", fylite_data::json::to_string(&out, true));
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
    let path = PathBuf::from(args.positional.get(1).unwrap_or_else(|| die("dump: which path?")));
    let bundle = io::read(&path).unwrap_or_else(|e| die(&e.to_string()));
    let bundle = select_ids(bundle, args);
    let root = bundle.to_node();
    let node = match args.flag("path") {
        Some(p) => root.walk(p, true).unwrap_or_else(|| die(&format!("no {p} in {}", path.display()))).clone(),
        None => root,
    };
    print!("{}", fylite_data::json::to_string(&node, !args.has("compact")));
}

fn report(rep: &io::WriteReport, out: &Path) {
    eprintln!("wrote {} as {} ({} layout)", out.display(),
              rep.format.map(|f| f.name()).unwrap_or("?"), rep.layout.map(|l| l.name()).unwrap_or("?"));
    for d in &rep.synthesized_docs {
        eprintln!("  synthesized {d}");
    }
    for (key, r) in &rep.dd {
        let dropped: Vec<&String> = r.dropped.iter().filter(|p| !p.starts_with('@')).collect();
        if !dropped.is_empty() || !r.promoted.is_empty() || !r.synthesized.is_empty() {
            eprintln!("  {key}: dropped {} non-DD path(s){}; promoted {:?}; synthesized {:?}",
                      dropped.len(), if dropped.is_empty() { String::new() } else { format!(" {:?}", dropped) },
                      r.promoted, r.synthesized);
        }
    }
}

fn convert(args: &Args) {
    let inp = PathBuf::from(args.positional.get(1).unwrap_or_else(|| die("convert: input path?")));
    let out = PathBuf::from(args.positional.get(2).unwrap_or_else(|| die("convert: output path?")));
    let bundle = select_ids(io::read(&inp).unwrap_or_else(|e| die(&e.to_string())), args);
    let fmt = args.flag("to").map(|s| Format::parse(s).unwrap_or_else(|| die(&format!("--to {s:?}: json, geqdsk, hdf5, netcdf or imas-hdf5"))));
    let rep = io::write(&out, &bundle, fmt, layout_of(args)).unwrap_or_else(|e| die(&e.to_string()));
    report(&rep, &out);
}

fn merge(args: &Args) {
    let out = PathBuf::from(args.flag("o").unwrap_or_else(|| die("merge: -o output?")));
    let paths: Vec<PathBuf> = args.positional[1..].iter().map(PathBuf::from).collect();
    if paths.is_empty() {
        die("merge: which inputs?");
    }
    let policy = if args.has("keep") { MergePolicy::KeepExisting } else { MergePolicy::Overwrite };
    let refs: Vec<&Path> = paths.iter().map(PathBuf::as_path).collect();
    let bundle = io::merge_paths(&refs, policy).unwrap_or_else(|e| die(&e.to_string()));
    let fmt = args.flag("to").map(|s| Format::parse(s).unwrap_or_else(|| die(&format!("--to {s:?}"))));
    let rep = io::write(&out, &bundle, fmt, layout_of(args)).unwrap_or_else(|e| die(&e.to_string()));
    report(&rep, &out);
}

fn assemble(args: &Args) {
    let asm = PathBuf::from(args.positional.get(1).unwrap_or_else(|| die("assemble: which assembly document?")));
    let out = PathBuf::from(args.flag("o").unwrap_or_else(|| die("assemble: -o output?")));
    let shot = args.flag("shot").map(|s| s.parse::<i64>().unwrap_or_else(|_| die("--shot wants an integer")));
    let slots: Vec<(String, i64)> = args.all("param").iter().map(|kv| {
        let (k, v) = kv.split_once('=').unwrap_or_else(|| die("--param k=v"));
        (k.to_string(), v.parse::<i64>().unwrap_or_else(|_| die("--param values are integers")))
    }).collect();
    let user = args.flag("mds-user").map(str::to_string).unwrap_or_else(|| std::env::var("USER").unwrap_or_else(|_| "nobody".into()));
    let timeout: u64 = args.flag("timeout-ms").map(|t| t.parse().unwrap_or(10_000)).unwrap_or(10_000);
    let connector = fylite_data::assembly::tcp_connector(user, timeout);
    let r = fylite_data::assembly::assemble_file(&asm, Some(&connector), shot, &slots).unwrap_or_else(|e| die(&e.to_string()));
    for f in &r.failures {
        eprintln!("  failed: {f}");
    }
    let fmt = args.flag("to").map(|s| Format::parse(s).unwrap_or_else(|| die(&format!("--to {s:?}"))));
    let rep = io::write(&out, &r.bundle, fmt, layout_of(args)).unwrap_or_else(|e| die(&e.to_string()));
    report(&rep, &out);
    if !r.failures.is_empty() {
        std::process::exit(1);
    }
}

fn main() {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    if argv.is_empty() || argv[0] == "-h" || argv[0] == "--help" {
        println!("{HELP}");
        return;
    }
    let args = Args::parse(&argv);
    match args.positional.first().map(String::as_str) {
        Some("info") => info(&args),
        Some("dump") => dump(&args),
        Some("convert") => convert(&args),
        Some("merge") => merge(&args),
        Some("assemble") => assemble(&args),
        Some("tables") => {
            println!("DD {}", fylite_data::ids_tables::DD_VERSION);
            for n in fylite_data::ids_meta::IdsMeta::names() {
                println!("  {n}");
            }
        }
        Some(other) => die(&format!("unknown command {other:?}; --help has the usage")),
        None => die("no command; --help has the usage"),
    }
}
