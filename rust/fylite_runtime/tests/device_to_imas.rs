//! 一份装置文档写进 IMAS 数据入口时，**丢了什么**。
//!
//! ★★这道闸补的是 `test_fyo_paths_have_a_dd_home`（公开仓 Python 侧）看不见的那一半。
//! 那一道查的是**声明表里的名字**在 DD 里有没有家；这一道查的是**一份真文档**过归一化
//! 时的下场 —— 名字对了、形状或类型不对，同样会被丢掉，而且丢得同样安静。
//!
//! 2026-09-07 实测（EAST 的真装置文档）：184 条裸路径被丢，其中 90 条真空室元件几何、
//! 79 条探针位置、14 条线圈元件几何类型、1 条 `tf/b0`。产物 `wall.h5` 只剩 8 个叶子 ——
//! 一份看着像结果的空 IDS。四类各自的成因不同，这里各钉一条：
//!
//! * `tf/b0` —— DD 的 `tf` 没有 `b0`（有 `b_field_phi_vacuum_r`）。**名字**问题。
//! * `wall/…/element/geometry` —— DD 的真空室元件由 `outline` 描述，没有 `geometry`。
//!   **词汇**问题：fylite 借了 `pf_active` 线圈元件的参数化写法。
//! * `magnetics/b_field_pol_probe/position` —— DD 说是**结构**（r/phi/z），文档写成
//!   **列表** `[{r,z}]`。**形状**问题，2026-09-07 已修：DD 把 `flux_loop/position` 写成
//!   结构数组（一条环可以穿过好几个点）、把探针的写成一个结构（一个探针在一个点上），
//!   而文档两者同写；归一化现在解一元列表并记进 `unwrapped`。两个以上元素仍旧丢弃 ——
//!   取第一个是悄悄丢掉其余，比丢整支更坏。
//! * `pf_active/coil/element/geometry/geometry_type` —— DD 的类型是**整数索引**，文档
//!   写字符串 `"rectangle"`。**类型**问题；该用哪个整数，本仓里查不到，是 `[TBD]`。
//!
//! 判据只有一条：**这张表只准变小**。修好一条就从 `EXPECTED` 里删一条。
use std::collections::BTreeSet;
use std::path::Path;

use fylite_runtime::io::{self, Layout};
use fylite_runtime::detect::Format;

/// 合成装置牌 —— 不是 EAST 的数据，是**同样四种形状**的最小复现。
/// 真装置文档在内核仓，本仓不带；一条闸子不该依赖另一个仓的检出。
const FIXTURE: &str = "testdata/device_synthetic.json";

/// 2026-09-07 实测。逐条的成因见本文件抬头。
///
/// ★探针位置那一条**同日修好了**：DD 说一个结构、文档给一元列表，归一化现在把它
/// 解出来并记进 `unwrapped`（`build_dd` 的 `Kind::Structure` 一支）。剩下三条各要一个
/// 决定，不是改名能了的 —— 见抬头。
const EXPECTED: [&str; 3] = [
    "pf_active: coil/element/geometry/geometry_type",
    "tf: b0",
    "wall: description_2d/vessel/unit/element/geometry",
];

fn bare_drops() -> BTreeSet<String> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let bundle = io::read(&root.join(FIXTURE)).expect("the fixture reads");
    //: 与 `fy data convert --layout imas` 同一条路：容器先拆成它装着的 IDS
    let mut split = fylite_runtime::fyodoc::Bundle::new();
    for doc in bundle.docs {
        let known = fylite_runtime::fyodoc::ids_of(&doc)
            .map(|i| fylite_runtime::ids_meta::IdsMeta::get(&i).is_some());
        if known == Some(true) {
            split.push(doc);
            continue;
        }
        let mut inner = fylite_runtime::document::Map::new();
        for (k, v) in doc.as_map().expect("a map").iter() {
            if k != "@type" {
                inner.insert(k, v.clone());
            }
        }
        for d in fylite_runtime::fyodoc::Bundle::from_node(
            fylite_runtime::document::Node::Map(inner)).docs {
            split.push(d);
        }
    }
    let dir = std::env::temp_dir().join(format!("fylite-dev2imas-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let rep = io::write(&dir, &split, Some(Format::ImasHdf5Dir), Layout::Imas)
        .expect("the entry is written");
    let _ = std::fs::remove_dir_all(&dir);
    rep.dd.iter()
        .flat_map(|(ids, r)| r.dropped.iter().map(move |d| (ids.clone(), d.clone())))
        //: `@` 是 JSON-LD 的框架键；`fylite:` 是**声明的本地**（内核的 `OURS` 表逐条
        //: 登记过），两者在 DD 里没有家是设计，不是缺陷
        .filter(|(_, d)| !d.starts_with('@')
                && !d.split('/').any(|s| s.starts_with("fylite:")))
        .map(|(ids, d)| format!("{ids}: {d}"))
        .collect()
}

#[test]
fn the_set_of_bare_paths_a_device_loses_only_shrinks() {
    let now = bare_drops();
    let expected: BTreeSet<String> = EXPECTED.iter().map(|s| s.to_string()).collect();
    let new: Vec<&String> = now.difference(&expected).collect();
    assert!(new.is_empty(),
            "a device now loses paths it did not lose before: {new:?}\n\
             a bare path with no DD home is a quantity that leaves the document \
             silently — give it the `fylite:` prefix, or write the path the DD has.");
    let fixed: Vec<&String> = expected.difference(&now).collect();
    assert!(fixed.is_empty(),
            "these no longer drop — take them out of EXPECTED: {fixed:?}");
}

#[test]
fn the_fixture_still_carries_every_shape_the_gate_is_about() {
    //: ★闸子的前提。fixture 被简化到不再复现某一种形状时，这条闸会绿着而什么也没查。
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let text = std::fs::read_to_string(root.join(FIXTURE)).expect("the fixture is there");
    for needle in ["\"b0\"", "geometry_type", "b_field_pol_probe", "vessel"] {
        assert!(text.contains(needle), "the fixture no longer carries {needle}");
    }
}
