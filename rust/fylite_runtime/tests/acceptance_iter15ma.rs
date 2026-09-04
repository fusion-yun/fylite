//! The acceptance case (2026-09-02): ITER 15 MA D-T evolution, fyo / JSON-LD
//! in, IMAS DD HDF5 out — `docs/examples/evolve/evolve-iter-15ma.jsonld` declares the
//! delivery itself (four output ports asking for `fyo:ImasHdf5Format`).
//!
//! Skipped (loudly) without a kernel library; needs the `hdf5` feature.
#![cfg(feature = "hdf5")]

use fylite_runtime::case;
use fylite_runtime::detect::Format;
use fylite_runtime::fyodoc::Bundle;
use fylite_runtime::io::{self, Layout};
use fylite_runtime::kernel::Kernel;
use std::path::Path;

#[test]
fn iter_15ma_dt_evolution_lands_as_an_imas_data_entry() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let kernel = std::env::var("FYLITE_KERNEL_LIB").ok();
    if kernel.is_none() && !root.join("python/fylite/_lib/libfylite_kernel.so").is_file() {
        eprintln!("SKIP: no kernel library (set FYLITE_KERNEL_LIB)");
        return;
    }
    //: ★2026-09-04 语料由 `cases/` 迁入 `docs/examples/<族>/`（一例一目录）。
    //: 这条路径是那次搬迁的**另一半**：只搬不改，本用例就会去开一个不在的文件。
    let plan_path = root.join("docs/examples/evolve/evolve-iter-15ma.jsonld");
    let (src, node) = case::read_source(&plan_path).unwrap();
    let plan = case::compose(vec![(src, node)]).unwrap();
    assert_eq!(plan.bar(), "evolve");
    //: the plan asks for the IMAS layout on its own output ports
    assert!(plan.outputs.iter().all(|o| o.format_iri.as_deref() == Some("fyo:ImasHdf5Format")));
    assert_eq!(plan.outputs.len(), 4);

    let k = Kernel::load(kernel.as_deref().map(Path::new)).unwrap();
    let (slots, _resolved) = case::resolve_inputs(&plan, root.join("cases").as_path()).unwrap();
    let (numbers, texts) = plan.kernel_settings().unwrap();
    let raw = k.run_case(&plan.code, &numbers, &texts, &slots).expect("the kernel completes the case");
    let out = case::parse_outcome(&raw).unwrap();
    assert_eq!(out.entry, "evolve_heat");
    let steps = out.facts.iter().find(|(k, _, _)| k == "steps").unwrap().2;
    assert_eq!(steps, 400.0, "the case prescribes 400 steps");

    //: one IMAS data entry for the run, written and read back through the data layer
    let dir = std::env::temp_dir().join(format!("fylite-acceptance-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let mut bundle = Bundle::new();
    for (_ids, doc) in case::documents(&out, &raw, "run/acceptance") {
        bundle.push(doc);
    }
    let rep = io::write(&dir, &bundle, Some(Format::ImasHdf5Dir), Layout::Imas).unwrap();
    let dropped: Vec<&String> = rep.dd.iter().flat_map(|(_, r)| r.dropped.iter()).filter(|d| !d.starts_with('@')).collect();
    assert!(dropped.is_empty(), "paths the DD does not know: {dropped:?}");
    for f in ["master.h5", "core_profiles.h5", "summary.h5", "equilibrium.h5", "core_transport.h5"] {
        assert!(dir.join(f).is_file(), "{f} missing");
    }
    let back = io::read(&dir).unwrap();
    let cp = back.get("core_profiles").expect("core_profiles reads back");
    let te = cp.walk("profiles_1d/0/electrons/temperature", true).and_then(|n| n.to_f64_vec()).unwrap();
    assert_eq!(te.len(), 31);
    assert!(te[0] > 20_000.0 && te[0] < 30_000.0, "axis Te at 8 s: {} eV (the case's own note says ~23.3 keV)", te[0]);
    assert!((te[30] - 3000.0).abs() < 1e-6, "the Dirichlet edge is 3 keV");
    let t = cp.walk("time", true).and_then(|n| n.to_f64_vec()).unwrap();
    assert_eq!(t.len(), 1);
    assert!((t[0] - 8.0).abs() < 1e-9, "the march ends at 8 s: {}", t[0]);
    let sm = back.get("summary").expect("summary reads back");
    let pa = sm.walk("fusion/power/value", true).and_then(|n| n.to_f64_vec()).unwrap();
    assert_eq!(pa.len(), 400);
    assert!(pa[399] > 5.0e7 && pa[399] < 1.0e8, "alpha power at the end: {} W (the note says 74.5 MW)", pa[399]);
    let ct = back.get("core_transport").expect("core_transport reads back");
    assert!(ct.walk("model/0/profiles_1d/0/grid_d/rho_tor", true).is_some(), "the diffusivity grid is under grid_d");
    let _ = std::fs::remove_dir_all(&dir);
}
