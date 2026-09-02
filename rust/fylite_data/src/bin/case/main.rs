//! `fylite-case` — a case from a fyo plan to a fyo record, through the kernel.
//!
//! ```text
//! fylite-case describe [--kernel PATH]                       what the kernel completes: codes, entries, their declared blocks
//! fylite-case plan <plan.jsonld>... [--set k=v]... [--bind port=path]... [--code IRI] [--json]
//! fylite-case run  <plan.jsonld>... [--set k=v]... [--bind port=path]... [--code IRI]
//!                  [--record DIR] [--format jsonld|hdf5|netcdf] [--kernel PATH] [--quiet]
//! fylite-case json <plan.jsonld>... [--kernel PATH]          the JSON door: the record, datasets inline, on stdout
//! ```
//!
//! One structure in, one structure out (FYL-REPORT-06): the plan documents
//! compose into ONE `fyo:ScenarioSpecification` (later ones override
//! earlier ones, `--set` / `--bind` last), the kernel completes it, and the
//! run comes back as ONE `spo:ComputationRecord` in `--record DIR` with the
//! produced datasets beside it as fyo documents (`<ids>.fyo.jsonld`; another
//! format on request, through the data layer).  `plan` stops before the
//! kernel and prints the composed plan; `describe` needs no plan at all.
//!
//! ★A case the kernel cannot complete is REFUSED with the missing thing
//! named, and the refusal is recorded too (`run_state: rejected`): a plan
//! that cannot run must say what it needs, not run something else.

use fylite_data::case::{self, Plan, Produced, RecordInputs};
use fylite_data::document::Node;
use fylite_data::fyo_interface as fi;
use fylite_data::json;
use fylite_data::kernel::Kernel;
use std::path::{Path, PathBuf};

const HELP: &str = "fylite-case — a case from a fyo plan to a fyo record, through the kernel

  fylite-case describe [--kernel PATH]
  fylite-case plan <plan.jsonld>... [--set k=v]... [--bind port=path]... [--code IRI] [--json]
  fylite-case run  <plan.jsonld>... [--set k=v]... [--bind port=path]... [--code IRI]
                   [--record DIR] [--format jsonld|hdf5|netcdf] [--kernel PATH] [--quiet]
  fylite-case json <plan.jsonld>... [--kernel PATH]

The plan documents are fyo:ScenarioSpecification (spo:ComputationPlan) JSON-LD in the
corpus compaction (cases/context.jsonld); later documents override earlier ones, then
--set / --bind.  The kernel is libfylite_kernel.so: --kernel, $FYLITE_KERNEL_LIB, or the
checkout's python/fylite/_lib/.  The record directory gets record.jsonld, plan.jsonld
and one <ids>.fyo.jsonld per produced dataset.";

fn die(msg: &str) -> ! {
    eprintln!("fylite-case: {msg}");
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
                let takes_value = matches!(name, "set" | "bind" | "code" | "record" | "format" | "kernel" | "out");
                if takes_value {
                    i += 1;
                    flags.push((name.to_string(), argv.get(i).cloned()));
                } else {
                    flags.push((name.to_string(), None));
                }
            } else if a == "-o" {
                i += 1;
                flags.push(("record".to_string(), argv.get(i).cloned()));
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

fn load_plan(args: &Args) -> (Plan, PathBuf) {
    if args.positional.len() < 2 {
        die("give at least one plan document");
    }
    let mut docs = Vec::new();
    for p in &args.positional[1..] {
        match case::read_source(Path::new(p)) {
            Ok(d) => docs.push(d),
            Err(e) => die(&e.0),
        }
    }
    let base = Path::new(&args.positional[1]).parent().map(Path::to_path_buf).unwrap_or_default();
    let mut plan = match case::compose(docs) {
        Ok(p) => p,
        Err(e) => die(&e.0),
    };
    if let Some(c) = args.flag("code") {
        plan.code = c.to_string();
    }
    for s in args.all("set") {
        if let Err(e) = plan.set_override(s) {
            die(&e.0);
        }
    }
    for b in args.all("bind") {
        if let Err(e) = plan.bind_override(b) {
            die(&e.0);
        }
    }
    (plan, base)
}

fn describe(args: &Args) {
    if let Some(k) = args.flag("kernel").map(Path::new).map(Some).map(|p| Kernel::load(p)).or_else(|| Some(Kernel::load(None))) {
        match k {
            Ok(k) => println!("kernel: {}  (abi {})", k.path.display(),
                              k.abi_version.map(|v| v.to_string()).unwrap_or_else(|| "?".into())),
            Err(e) => println!("kernel: not loaded — {}", e.message.lines().next().unwrap_or("")),
        }
    }
    println!("\ncodes the kernel completes (code/<code> · the corpus's own vocabulary):");
    if let Some(b) = fi::BLOCKS.iter().find(|b| b.name == "CASE_CODES") {
        for r in b.rows {
            println!("  code/{:<12} -> {:<12} [{}]  {}", r.key, r.shape, r.units, r.gloss);
        }
    }
    println!("\nraw entries (entry/<name> · the declared blocks, nothing converted):");
    for e in fi::ENTRIES {
        println!("  entry/{:<12} dims {:?}", e.name, e.dims);
        for (role, name) in [("params", e.params), ("input", e.input), ("out", e.out)] {
            if let Some(b) = fi::BLOCKS.iter().find(|b| b.name == name) {
                let rows: Vec<String> = b.rows.iter().map(|r| format!("{}[{}]", r.key, r.units)).collect();
                println!("    {role:<6} {}", rows.join(" "));
            }
        }
    }
    println!("\noutput documents (fyo path per kernel slot):");
    for t in fi::TABLES {
        if t.slots.is_empty() {
            continue;
        }
        println!("  {} ({}):", t.doc_type, t.name);
        for s in t.slots {
            println!("    {:<12} {} [{}]", s.key, s.path, s.units);
        }
    }
}

fn plan_cmd(args: &Args) {
    let (plan, _base) = load_plan(args);
    if args.has("json") {
        println!("{}", json::to_string(&plan.to_node(), true));
        return;
    }
    println!("{}  ->  {}  ({})", plan.id, plan.code,
             plan.task_kind.as_deref().unwrap_or("task kind unstated"));
    if let Some(t) = &plan.title {
        println!("  {t}");
    }
    println!("  {} settings, {} input bindings, {} output requests, {} caveats",
             plan.settings.len(), plan.inputs.len(), plan.outputs.len(), plan.caveats.len());
    for s in &plan.settings {
        let from = match s.from {
            Some(i) => plan.sources.get(i).map(|x| x.path.display().to_string()).unwrap_or_default(),
            None => "--set".into(),
        };
        println!("    {:<14} = {:<24} {}", s.name, json::to_string(&s.value, false), from);
    }
    for b in &plan.inputs {
        let what = match (&b.endpoint, &b.inline) {
            (Some(e), _) => e.clone(),
            (None, Some(_)) => "(inline)".into(),
            (None, None) => "OPEN — nothing bound".into(),
        };
        println!("    input {:<10} {}{}", b.port, what,
                 b.note.as_ref().map(|n| format!("  · {n}")).unwrap_or_default());
    }
    for c in &plan.caveats {
        println!("    caveat: {}", c.chars().take(120).collect::<String>());
    }
}

fn write_text(path: &Path, text: &str) -> (String, usize) {
    if let Err(e) = std::fs::write(path, text) {
        die(&format!("{}: {e}", path.display()));
    }
    (fylite_data::checksum::sha256_hex(text.as_bytes()), text.len())
}

fn run_cmd(args: &Args) {
    let quiet = args.has("quiet");
    let (plan, base) = load_plan(args);
    let (started_secs, started_at) = case::now_iso();
    let record_id = format!("run/{}-{}", started_at.replace([':', '-'], ""), plan.bar());
    let record_dir = args.flag("record").map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("records").join(record_id.trim_start_matches("run/")));
    if let Err(e) = std::fs::create_dir_all(&record_dir) {
        die(&format!("{}: {e}", record_dir.display()));
    }
    let kernel = match Kernel::load(args.flag("kernel").map(Path::new)) {
        Ok(k) => k,
        Err(e) => die(&e.message),
    };
    let kernel_sha = std::fs::read(&kernel.path).ok().map(|b| fylite_data::checksum::sha256_hex(&b));

    // the plan as it will be run, written first: a record cites it
    let plan_text = json::to_string(&plan.to_node(), true) + "\n";
    write_text(&record_dir.join("plan.jsonld"), &plan_text);

    let (slots, resolved) = match case::resolve_inputs(&plan, &base) {
        Ok(x) => x,
        Err(e) => die(&e.0),
    };
    let (numbers, texts) = match plan.kernel_settings() {
        Ok(x) => x,
        Err(e) => die(&e.0),
    };
    let result = kernel.run_case(&plan.code, &numbers, &texts, &slots);
    let (_end_secs, ended_at) = case::now_iso();
    let _ = started_secs;

    let mut produced: Vec<Produced> = Vec::new();
    let outcome = match &result {
        Ok(raw) => match case::parse_outcome(raw) {
            Ok(o) => {
                let format = args.flag("format").unwrap_or("jsonld").to_ascii_lowercase();
                for (ids, doc) in case::documents(&o, raw, &record_id) {
                    let fields: Vec<String> = o.fields.iter()
                        .filter(|f| (if f.ids.is_empty() { "entry" } else { f.ids.as_str() }) == ids)
                        .map(|f| format!("{} [{}] {:?}", f.path, f.units, f.dims)).collect();
                    let (file, format_iri, sha, bytes) = match format.as_str() {
                        "jsonld" | "json" => {
                            let file = format!("{ids}.fyo.jsonld");
                            let text = json::to_string(&doc, true) + "\n";
                            let (sha, bytes) = write_text(&record_dir.join(&file), &text);
                            (file, case::LD_JSON.to_string(), sha, bytes)
                        }
                        other => {
                            let ext = match other { "hdf5" | "h5" => "h5", "netcdf" | "nc" => "nc", _ => die(&format!("unknown --format {other}")) };
                            let file = format!("{ids}.{ext}");
                            let bundle = fylite_data::fyodoc::Bundle::one(doc.clone());
                            if let Err(e) = fylite_data::io::write(&record_dir.join(&file), &bundle, None,
                                                                   fylite_data::io::Layout::Fyo) {
                                die(&format!("{file}: {e}"));
                            }
                            let bytes = std::fs::read(record_dir.join(&file)).unwrap_or_default();
                            (file, "[TBD]".to_string(), fylite_data::checksum::sha256_hex(&bytes), bytes.len())
                        }
                    };
                    produced.push(Produced { port: ids.clone(), doc_id: format!("{record_id}/{ids}"),
                                             doc_type: format!("fyo:{ids}"), storage_uri: file,
                                             format_iri, sha256: sha, bytes, fields, inline: None });
                }
                Some(o)
            }
            Err(e) => die(&e.0),
        },
        Err(_) => None,
    };
    let rec = case::record(&RecordInputs {
        plan: &plan, plan_file: Some("plan.jsonld"), resolved: &resolved, kernel: Some(&kernel),
        kernel_sha256: kernel_sha, outcome: outcome.as_ref(), refusal: result.as_ref().err(),
        produced: &produced, started_at, ended_at, record_id: record_id.clone(),
    });
    let rec_text = json::to_string(&rec, true) + "\n";
    write_text(&record_dir.join("record.jsonld"), &rec_text);

    match (&result, &outcome) {
        (Ok(_), Some(o)) => {
            if !quiet {
                println!("{}  {} -> {}  entry {}  {}", record_id, plan.id, plan.code, o.entry,
                         o.dims.iter().map(|(k, n)| format!("{k}={n}")).collect::<Vec<_>>().join(" "));
                for (k, u, v) in &o.facts {
                    println!("  {k:<16} {v} {u}");
                }
                for p in &produced {
                    println!("  {:<24} {} ({} fields, {} bytes)", p.port, p.storage_uri, p.fields.len(), p.bytes);
                }
                for n in &o.notes {
                    println!("  note: {n}");
                }
                println!("  record: {}", record_dir.join("record.jsonld").display());
            }
        }
        (Err(e), _) => {
            eprintln!("fylite-case: the kernel refused `{}`: {}", plan.code, e);
            eprintln!("  record: {}  (run_state: rejected)", record_dir.join("record.jsonld").display());
            std::process::exit(1);
        }
        _ => {}
    }
}

extern "C" {
    fn signal(sig: i32, handler: usize) -> usize;
}

/// The JSON door from the shell: the plan documents composed in order, the
/// record (datasets inline) on stdout.  Exit 0 ran, 1 refused, 2 no record.
fn json_cmd(args: &Args) {
    if args.positional.len() < 2 {
        die("give at least one plan document");
    }
    let mut docs = Vec::new();
    for p in &args.positional[1..] {
        let text = std::fs::read_to_string(p).unwrap_or_else(|e| die(&format!("{p}: {e}")));
        docs.push(json::parse(&text).unwrap_or_else(|e| die(&format!("{p}: {e:?}"))));
    }
    let text = json::to_string(&Node::List(docs), false);
    let base = Path::new(&args.positional[1]).parent().map(Path::to_path_buf).unwrap_or_default();
    match case::run_json(&text, Some(&base), args.flag("kernel").map(Path::new)) {
        Ok(r) => {
            print!("{}", r.record_json);
            if r.refused {
                std::process::exit(1);
            }
        }
        Err(e) => die(&format!("[{}] {}", e.code, e.message)),
    }
}

fn main() {
    //: a closed pipe ends the listing, it is not a panic (`| head`)
    unsafe { signal(13, 0) };
    let argv: Vec<String> = std::env::args().skip(1).collect();
    if argv.is_empty() || argv.iter().any(|a| a == "-h" || a == "--help") {
        println!("{HELP}");
        return;
    }
    let args = Args::parse(&argv);
    match args.positional.first().map(String::as_str) {
        Some("describe") => describe(&args),
        Some("plan") => plan_cmd(&args),
        Some("run") => run_cmd(&args),
        Some("json") => json_cmd(&args),
        Some(other) => die(&format!("unknown command `{other}`\n{HELP}")),
        None => println!("{HELP}"),
    }
    let _: Option<Node> = None;
}
