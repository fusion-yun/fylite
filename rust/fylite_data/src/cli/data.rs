//! `data` — the data layer's command line: what a file is, format
//! conversion, merging, assembling several data sources by a JSON-LD
//! document.  What each subcommand TAKES is in `_cli.json` (`data`); this
//! module is only what they DO.
//!
//! Reached as `fylite-app data …` (the single executable) or as
//! `fylite-data …` (the thin alias binary) — the same code either way.
//!
//! ★Every MDSplus read goes through `fylite_data::mdsip`'s read-only
//! client; there is no expression endpoint here — `assemble`'s `$link`
//! expressions are decomposed into «verb + node path + integer» by
//! `mdsbind::decompose` before anything is sent, and what cannot be
//! decomposed is listed among the failures.

use super::Args;
use crate::detect::Format;
use crate::document::{MergePolicy, Node};
use crate::fyodoc::{self, Bundle};
use crate::io::{self, Layout};
use std::path::{Path, PathBuf};

fn die(msg: &str) -> ! {
    eprintln!("fylite-data: {msg}");
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
    let bundle = io::read(&path).unwrap_or_else(|e| die(&e.to_string()));
    let bundle = select_ids(bundle, args);
    let root = bundle.to_node();
    let node = match args.flag("path") {
        Some(p) => root
            .walk(p, true)
            .unwrap_or_else(|| die(&format!("no {p} in {}", path.display())))
            .clone(),
        None => root,
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
    let bundle = io::merge_paths(&refs, policy).unwrap_or_else(|e| die(&e.to_string()));
    let rep = io::write(&out, &bundle, format_of(args), layout_of(args)).unwrap_or_else(|e| die(&e.to_string()));
    report(&rep, &out);
}

#[cfg(feature = "mdsip")]
fn assemble(args: &Args) {
    let asm = PathBuf::from(args.flag("assembly").unwrap_or_else(|| die("assemble: which assembly document?")));
    let out = PathBuf::from(args.flag("out").unwrap_or_else(|| die("assemble: -o output?")));
    let shot = args.flag("shot").map(|s| s.parse::<i64>().unwrap_or_else(|_| die("--shot wants an integer")));
    let slots: Vec<(String, i64)> = args
        .all("param")
        .iter()
        .map(|kv| {
            let (k, v) = kv.split_once('=').unwrap_or_else(|| die("--param k=v"));
            (k.to_string(), v.parse::<i64>().unwrap_or_else(|_| die("--param values are integers")))
        })
        .collect();
    let user = args
        .flag("mds-user")
        .map(str::to_string)
        .unwrap_or_else(|| std::env::var("USER").unwrap_or_else(|_| "nobody".into()));
    let timeout: u64 = args.flag("timeout-ms").map(|t| t.parse().unwrap_or(10_000)).unwrap_or(10_000);
    let connector = crate::assembly::tcp_connector(user, timeout);
    let r = crate::assembly::assemble_file(&asm, Some(&connector), shot, &slots).unwrap_or_else(|e| die(&e.to_string()));
    for f in &r.failures {
        eprintln!("  failed: {f}");
    }
    let rep = io::write(&out, &r.bundle, format_of(args), layout_of(args)).unwrap_or_else(|e| die(&e.to_string()));
    report(&rep, &out);
    if !r.failures.is_empty() {
        std::process::exit(1);
    }
}

#[cfg(not(feature = "mdsip"))]
fn assemble(_args: &Args) {
    die("assemble needs the `mdsip` feature (this build has no MDSplus client)");
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
    match args.word(1) {
        "info" => info(args),
        "dump" => dump(args),
        "convert" => convert(args),
        "merge" => merge(args),
        "assemble" => assemble(args),
        "tables" => tables(),
        other => die(&format!("unknown data subcommand {other:?}; --help has the usage")),
    }
}
