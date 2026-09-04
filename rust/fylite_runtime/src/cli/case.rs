//! `case` — a case from a fyo plan to a fyo record, through the kernel.
//! What each subcommand TAKES is in `_cli.json` (`case`); this module is
//! only what they DO.
//!
//! Reached as `fylite case …` (the Python console script, which hands the
//! words on verbatim) or as `fylite case …` (the one executable) —
//! the same code either way.  ★2026-09-03 the `fylite-case` alias binary was
//! retired: one executable carries every command word.
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

use super::Args;
use crate::case::{self, Plan, Produced, RecordInputs};
use crate::document::Node;
use crate::fyo_interface as fi;
use crate::json;
use crate::kernel::Kernel;
use std::path::{Path, PathBuf};

fn die(msg: &str) -> ! {
    eprintln!("fylite case: {msg}");
    std::process::exit(2);
}

fn load_plan(args: &Args) -> (Plan, PathBuf) {
    let plans = args.all("plans");
    if plans.is_empty() {
        die("give at least one plan document");
    }
    let mut docs = Vec::new();
    for p in &plans {
        match case::read_source(Path::new(p)) {
            Ok(d) => docs.push(d),
            Err(e) => die(&e.0),
        }
    }
    let base = Path::new(plans[0]).parent().map(Path::to_path_buf).unwrap_or_default();
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
    if let Some(k) = args
        .flag("kernel")
        .map(Path::new)
        .map(Some)
        .map(|p| Kernel::load(p))
        .or_else(|| Some(Kernel::load(None)))
    {
        match k {
            Ok(k) => println!(
                "kernel: {}  (abi {})",
                k.path.display(),
                k.abi_version.map(|v| v.to_string()).unwrap_or_else(|| "?".into())
            ),
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
    println!(
        "{}  ->  {}  ({})",
        plan.id,
        plan.code,
        plan.task_kind.as_deref().unwrap_or("task kind unstated")
    );
    if let Some(t) = &plan.title {
        println!("  {t}");
    }
    println!(
        "  {} settings, {} input bindings, {} output requests, {} caveats",
        plan.settings.len(),
        plan.inputs.len(),
        plan.outputs.len(),
        plan.caveats.len()
    );
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
        println!(
            "    input {:<10} {}{}",
            b.port,
            what,
            b.note.as_ref().map(|n| format!("  · {n}")).unwrap_or_default()
        );
    }
    for c in &plan.caveats {
        println!("    caveat: {}", c.chars().take(120).collect::<String>());
    }
}

fn write_text(path: &Path, text: &str) -> (String, usize) {
    if let Err(e) = std::fs::write(path, text) {
        die(&format!("{}: {e}", path.display()));
    }
    (crate::checksum::sha256_hex(text.as_bytes()), text.len())
}

fn run_cmd(args: &Args) {
    let quiet = args.has("quiet");
    let (plan, base) = load_plan(args);
    let (started_secs, started_at) = case::now_iso();
    let record_id = format!("run/{}-{}", started_at.replace([':', '-'], ""), plan.bar());
    let record_dir = args
        .flag("record")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("records").join(record_id.trim_start_matches("run/")));
    if let Err(e) = std::fs::create_dir_all(&record_dir) {
        die(&format!("{}: {e}", record_dir.display()));
    }
    let kernel = match Kernel::load(args.flag("kernel").map(Path::new)) {
        Ok(k) => k,
        Err(e) => die(&e.message),
    };
    let kernel_sha = std::fs::read(&kernel.path).ok().map(|b| crate::checksum::sha256_hex(&b));

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
    let mut dd_notes: Vec<String> = Vec::new();
    let outcome = match &result {
        Ok(raw) => match case::parse_outcome(raw) {
            Ok(o) => {
                //: the format: the flag, else what the plan's output ports ask for
                let asked = plan.outputs.iter().find_map(|r| r.format_iri.clone());
                let format = args
                    .flag("format")
                    .map(str::to_string)
                    .or_else(|| {
                        asked.map(|f| match f.as_str() {
                            "fyo:ImasHdf5Format" | "imas_hdf5" => "imas-hdf5".to_string(),
                            other if other.ends_with("ImasHdf5Format") => "imas-hdf5".to_string(),
                            other if other.ends_with("ld+json") => "jsonld".to_string(),
                            other => other.to_string(),
                        })
                    })
                    .unwrap_or_else(|| "jsonld".into())
                    .to_ascii_lowercase();
                let docs = case::documents(&o, raw, &record_id);
                if format == "imas-hdf5" || format == "imas" {
                    //: one IMAS data entry for the whole run: every produced
                    //: dataset is an IDS in it, the DD normaliser reports what
                    //: it could not place, and the record cites each IDS file
                    let mut bundle = crate::fyodoc::Bundle::new();
                    for (_ids, doc) in &docs {
                        bundle.push(doc.clone());
                    }
                    let dir = record_dir.join("imas");
                    let rep = crate::io::write(
                        &dir,
                        &bundle,
                        Some(crate::detect::Format::ImasHdf5Dir),
                        crate::io::Layout::Imas,
                    )
                    .unwrap_or_else(|e| die(&format!("imas: {e}")));
                    for (key, r) in &rep.dd {
                        for d in &r.dropped {
                            //: the JSON-LD envelope (`@context` / `@id` / `@type`) is
                            //: not data and is dropped by design; only a DATA path
                            //: the DD does not know is worth a note
                            if !d.starts_with('@') {
                                dd_notes.push(format!("imas {key}: dropped {d} (not in the DD)"));
                            }
                        }
                        for d in &r.promoted {
                            dd_notes.push(format!("imas {key}: {d} promoted to element 0"));
                        }
                        for d in &r.synthesized {
                            dd_notes.push(format!("imas {key}: {d} synthesized"));
                        }
                    }
                    for (ids, _doc) in &docs {
                        let file = format!("imas/{ids}.h5");
                        let bytes = std::fs::read(record_dir.join(&file)).unwrap_or_default();
                        let fields: Vec<String> = o
                            .fields
                            .iter()
                            .filter(|f| (if f.ids.is_empty() { "entry" } else { f.ids.as_str() }) == ids)
                            .map(|f| format!("{} [{}] {:?}", f.path, f.units, f.dims))
                            .collect();
                        produced.push(Produced {
                            port: ids.clone(),
                            doc_id: format!("{record_id}/{ids}"),
                            doc_type: format!("fyo:{ids}"),
                            storage_uri: file,
                            format_iri: "fyo:ImasHdf5Format".into(),
                            sha256: crate::checksum::sha256_hex(&bytes),
                            bytes: bytes.len(),
                            fields,
                            inline: None,
                        });
                    }
                    let master = std::fs::read(record_dir.join("imas/master.h5")).unwrap_or_default();
                    produced.push(Produced {
                        port: "imas".into(),
                        doc_id: format!("{record_id}/imas"),
                        doc_type: "spo:InformationContentEntity".into(),
                        storage_uri: "imas/master.h5".into(),
                        format_iri: "fyo:ImasHdf5Format".into(),
                        sha256: crate::checksum::sha256_hex(&master),
                        bytes: master.len(),
                        fields: vec!["the data entry's master file (external links to every IDS)".into()],
                        inline: None,
                    });
                }
                for (ids, doc) in docs {
                    if format == "imas-hdf5" || format == "imas" {
                        break;
                    }
                    let fields: Vec<String> = o
                        .fields
                        .iter()
                        .filter(|f| (if f.ids.is_empty() { "entry" } else { f.ids.as_str() }) == ids)
                        .map(|f| format!("{} [{}] {:?}", f.path, f.units, f.dims))
                        .collect();
                    let (file, format_iri, sha, bytes) = match format.as_str() {
                        "jsonld" | "json" => {
                            let file = format!("{ids}.fyo.jsonld");
                            let text = json::to_string(&doc, true) + "\n";
                            let (sha, bytes) = write_text(&record_dir.join(&file), &text);
                            (file, case::LD_JSON.to_string(), sha, bytes)
                        }
                        other => {
                            let ext = match other {
                                "hdf5" | "h5" => "h5",
                                "netcdf" | "nc" => "nc",
                                _ => die(&format!("unknown --format {other}")),
                            };
                            let file = format!("{ids}.{ext}");
                            let bundle = crate::fyodoc::Bundle::one(doc.clone());
                            if let Err(e) =
                                crate::io::write(&record_dir.join(&file), &bundle, None, crate::io::Layout::Fyo)
                            {
                                die(&format!("{file}: {e}"));
                            }
                            let bytes = std::fs::read(record_dir.join(&file)).unwrap_or_default();
                            (file, "[TBD]".to_string(), crate::checksum::sha256_hex(&bytes), bytes.len())
                        }
                    };
                    produced.push(Produced {
                        port: ids.clone(),
                        doc_id: format!("{record_id}/{ids}"),
                        doc_type: format!("fyo:{ids}"),
                        storage_uri: file,
                        format_iri,
                        sha256: sha,
                        bytes,
                        fields,
                        inline: None,
                    });
                }
                Some(o)
            }
            Err(e) => die(&e.0),
        },
        Err(_) => None,
    };
    let mut outcome = outcome;
    if let Some(o) = outcome.as_mut() {
        o.notes.extend(dd_notes.iter().cloned());
    }
    let rec = case::record(&RecordInputs {
        plan: &plan,
        plan_file: Some("plan.jsonld"),
        resolved: &resolved,
        kernel: Some(&kernel),
        kernel_sha256: kernel_sha,
        outcome: outcome.as_ref(),
        refusal: result.as_ref().err(),
        produced: &produced,
        started_at,
        ended_at,
        record_id: record_id.clone(),
    });
    let rec_text = json::to_string(&rec, true) + "\n";
    write_text(&record_dir.join("record.jsonld"), &rec_text);

    match (&result, &outcome) {
        (Ok(_), Some(o)) => {
            if !quiet {
                println!(
                    "{}  {} -> {}  entry {}  {}",
                    record_id,
                    plan.id,
                    plan.code,
                    o.entry,
                    o.dims.iter().map(|(k, n)| format!("{k}={n}")).collect::<Vec<_>>().join(" ")
                );
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
            eprintln!("fylite case: the kernel refused `{}`: {}", plan.code, e);
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
    let plans = args.all("plans");
    if plans.is_empty() {
        die("give at least one plan document");
    }
    let mut docs = Vec::new();
    for p in &plans {
        let text = std::fs::read_to_string(p).unwrap_or_else(|e| die(&format!("{p}: {e}")));
        docs.push(json::parse(&text).unwrap_or_else(|e| die(&format!("{p}: {e:?}"))));
    }
    let text = json::to_string(&Node::List(docs), false);
    let base = Path::new(plans[0]).parent().map(Path::to_path_buf).unwrap_or_default();
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

/// Run one `case` subcommand (`args.command == ["case", <sub>]`).
pub fn run(args: &Args) {
    //: a closed pipe ends the listing, it is not a panic (`| head`)
    unsafe { signal(13, 0) };
    match args.word(1) {
        "describe" => describe(args),
        "plan" => plan_cmd(args),
        "run" => run_cmd(args),
        "json" => json_cmd(args),
        other => die(&format!("unknown case subcommand {other:?}; --help has the usage")),
    }
}
