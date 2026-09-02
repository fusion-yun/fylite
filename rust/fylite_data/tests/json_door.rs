//! The JSON door, end to end — skipped (loudly) when no kernel library is reachable.
use fylite_data::case;
use std::path::Path;

#[test]
fn a_corpus_case_goes_through_the_json_door() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let plan = root.join("cases/evolve-default.jsonld");
    let text = std::fs::read_to_string(&plan).expect("the corpus is in the checkout");
    let kernel = std::env::var("FYLITE_KERNEL_LIB").ok();
    if kernel.is_none() && !root.join("python/fylite/_lib/libfylite_kernel.so").is_file() {
        eprintln!("SKIP: no kernel library (set FYLITE_KERNEL_LIB)");
        return;
    }
    //: two documents compose: the case, then an override shortening the march
    let composed = format!("[{text}, {{\"type\": \"spo:ComputationPlan\", \"parameters\": [{{\"sets_parameter\": \"code/evolve#nsteps\", \"literal_value\": 6}}]}}]");
    let r = case::run_json(&composed, Some(root.join("cases").as_path()), kernel.as_deref().map(Path::new)).unwrap();
    assert!(!r.refused, "{}", r.record_json);
    let rec = fylite_data::json::parse(&r.record_json).unwrap();
    let m = rec.as_map().unwrap();
    assert_eq!(m.get("run_state").and_then(|n| n.as_str()), Some("succeeded"));
    assert_eq!(m.get("type").and_then(|n| n.as_str()), Some("spo:ComputationRecord"));
    let inputs = m.get("inputs").and_then(|n| n.as_list()).unwrap();
    //: the datasets travel inline on their output ports
    let inline = inputs.iter().filter(|b| b.as_map().and_then(|bm| bm.get("bound_to")).and_then(|d| d.as_map())
        .map(|dm| dm.get("type").and_then(|t| t.as_str()).map(|t| t.starts_with("fyo:")).unwrap_or(false)).unwrap_or(false)).count();
    assert!(inline >= 4, "{inline} inline datasets");
    //: and a plan the kernel refuses still yields a record, marked so
    let refused = format!("[{text}, {{\"type\": \"spo:ComputationPlan\", \"parameters\": [{{\"sets_parameter\": \"code/evolve#beam\", \"literal_value\": true}}]}}]");
    let r = case::run_json(&refused, Some(root.join("cases").as_path()), kernel.as_deref().map(Path::new)).unwrap();
    assert!(r.refused);
    assert!(r.record_json.contains("\"rejected\"") && r.record_json.contains("NBI"), "{}", r.record_json);
}
