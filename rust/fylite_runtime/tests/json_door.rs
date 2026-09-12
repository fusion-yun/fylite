//! The JSON door, end to end — skipped (loudly) when no kernel library is reachable.
use fylite_runtime::case;
use std::path::Path;

#[test]
fn a_corpus_case_goes_through_the_json_door() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    //: ★语料 2026-09-04 由 `cases/` 迁入 `docs/examples/<族>/`（一例一目录）。
    let plan = root.join("docs/examples/evolve/evolve-default.jsonld");
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
    let rec = fylite_runtime::json::parse(&r.record_json).unwrap();
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
    //: ★★The refusal has to be READABLE IN THE RECORD, not merely signalled by
    //: the return value — a caller that keeps only the record must still learn
    //: why.  So the assertion reads the record's own `comment`, not the whole
    //: document text: `record_json.contains("beam")` would pass on the plan's
    //: `beampower` parameter alone and stop testing anything.  (It pinned the
    //: literal "NBI" until 2026-09-07 and had gone red: the message was
    //: reworded to name the missing psi map, which is the more useful
    //: sentence — the subsystem's acronym was never the invariant.)
    let rec = fylite_runtime::json::parse(&r.record_json).unwrap();
    let m = rec.as_map().unwrap();
    assert_eq!(m.get("run_state").and_then(|n| n.as_str()), Some("rejected"));
    let why = m.get("comment").map(|c| fylite_runtime::json::to_string(c, false)).unwrap_or_default();
    assert!(why.contains("refused") && why.contains("beam"),
            "the record does not say why it was refused: {why}");
}

/// ★★**一份文档的那条路也走树门**（F-1，2026-09-12）。
///
/// 这条路从前无条件调**扁平门**，而扁平门只递 f64 槽 —— 一个要**整份文档**的 code
/// （`case.rs::DOCUMENT_PORTS` 八个端口，`inputs/device` 是其中一个）于是在这里按名
/// 拒绝，而同一份计划经 `fy run` 就跑得动。物理校验册上实测的那句拒绝是
/// `[-33] code/discharge takes the whole device document and is reached through the
/// tree door only`：可评条数因此一直是 0。
///
/// 判据取**能跑通**这一件：`discharge-iter` 绑了装置文档（`docs/examples/design/`），
/// 经这条路跑出一份 `run_state: succeeded` 的记录，且记录里带着设计的落点
/// （`shape_error` 一条事实）。★装置文档是构建暂存区的拖回物（`dist/facts/device/`，
/// 仓顶不再有 `facts/`），所以不在场时**响亮跳过**而不是失败 —— 与上面缺内核那一条
/// 同一个办法。
#[test]
fn a_case_that_binds_a_device_document_goes_through_the_tree_door() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let plan = root.join("docs/examples/design/discharge-iter.jsonld");
    let text = std::fs::read_to_string(&plan).expect("the corpus is in the checkout");
    let kernel = std::env::var("FYLITE_KERNEL_LIB").ok();
    if kernel.is_none() && !root.join("python/fylite/_lib/libfylite_kernel.so").is_file() {
        eprintln!("SKIP: no kernel library (set FYLITE_KERNEL_LIB)");
        return;
    }
    if !root.join("dist/facts/device/iter.jsonld").is_file() {
        eprintln!("SKIP: no dist/facts/device/iter.jsonld (run tools/abox-to-facts.py iter)");
        return;
    }
    let base = root.join("docs/examples/design");
    let r = case::run_json(&text, Some(base.as_path()), kernel.as_deref().map(Path::new)).unwrap();
    assert!(!r.refused, "{}", r.record_json);
    let rec = fylite_runtime::json::parse(&r.record_json).unwrap();
    let m = rec.as_map().unwrap();
    assert_eq!(m.get("run_state").and_then(|n| n.as_str()), Some("succeeded"));
    //: 落点在记录里说得出来 —— 一个跑通而什么都没报的记录不算通过
    let text = fylite_runtime::json::to_string(m.get("inputs").unwrap(), false);
    assert!(text.contains("shape_error"), "记录里没有 `shape_error`：{text:.400}");
    //: ★而**没有**绑定的那一份仍按名拒绝（去掉 `inputs` 段重跑）：这条闸问的是
    //: 「绑了就跑得动」，不是「门变宽松了」
    let mut bare = fylite_runtime::json::parse(&std::fs::read_to_string(&plan).unwrap()).unwrap();
    bare.as_map_mut().unwrap().remove("inputs");
    let r2 = case::run_json(&fylite_runtime::json::to_string(&bare, false),
                            Some(base.as_path()), kernel.as_deref().map(Path::new)).unwrap();
    assert!(r2.refused, "没有装置文档也跑通了：{}", r2.record_json);
    assert!(r2.record_json.contains("device"), "拒绝没有指名装置文档：{}", r2.record_json);
}
