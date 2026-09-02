//! g-file ↔ `fyo:equilibrium` —— 与 `python/fylite/fyo.py` 的 `equilibrium` / `as_geqdsk`
//! **同一张路径表**、同一个转置。
//!
//! ★★路径表是内核 `fyo.rs` 的 `@fyo-table EQUILIBRIUM`（生成进 `_fyo_interface.py`）。
//! 这里再抄一份是不得已：内核仓不公开，本 crate 不能 `use` 它。所以
//! `python/tests/test_fyo_interface.py` 那一侧把这一份与生成表逐行对——两份拼写
//! 只有在被对拍时才算一份契约（`abox-mds-bind.py` 抬头的那条教训）。
//!
//! ★★`psi` 的次序：文档存 `psi[R, Z]`（IMAS：`dim1` 是 R），g-file 存 `[z, r]`
//! 展平、R 最快。**一次转置，在一个地方**——与 Python 侧 `as_geqdsk` 的注记同一句话。
//!
//! 与 Python 侧不同的一点：这里**不量** COCOS / ψ 约定（T-C22）。那是约定不是格式，
//! 需要内核的 Δ* 算子，留在 Python 侧。

use crate::document::{Array, Node};
use crate::fyodoc;
use crate::geqdsk::GFile;

/// `[key, path]` —— 内核表的前两列；单位与秩在那边。
pub const EQUILIBRIUM_SLOTS: [(&str, &str); 20] = [
    ("ip",             "time_slice/global_quantities/ip"),
    ("axis_r",         "time_slice/global_quantities/magnetic_axis/r"),
    ("axis_z",         "time_slice/global_quantities/magnetic_axis/z"),
    ("psi_axis",       "time_slice/global_quantities/psi_axis"),
    ("psi_boundary",   "time_slice/global_quantities/psi_boundary"),
    ("r0",             "vacuum_toroidal_field/r0"),
    ("b0",             "vacuum_toroidal_field/b0"),
    ("psi_1d",         "time_slice/profiles_1d/psi"),
    ("f",              "time_slice/profiles_1d/f"),
    ("pressure",       "time_slice/profiles_1d/pressure"),
    ("f_df_dpsi",      "time_slice/profiles_1d/f_df_dpsi"),
    ("dpressure_dpsi", "time_slice/profiles_1d/dpressure_dpsi"),
    ("q_1d",           "time_slice/profiles_1d/q"),
    ("grid_r",         "time_slice/profiles_2d/grid/dim1"),
    ("grid_z",         "time_slice/profiles_2d/grid/dim2"),
    ("psi_2d",         "time_slice/profiles_2d/psi"),
    ("boundary_r",     "time_slice/boundary/outline/r"),
    ("boundary_z",     "time_slice/boundary/outline/z"),
    ("limiter_r",      "fylite:limiter/r"),
    ("limiter_z",      "fylite:limiter/z"),
];

/// 结构数组段 —— 内核 `AOS` 声明里本转换会走到的那几个。
const AOS: [&str; 2] = ["time_slice", "profiles_2d"];

/// 表里的路径 → 带 `/0/` 的显式路径（表的约定：不带索引即第 0 个）。
pub fn explicit(path: &str) -> String {
    path.split('/').map(|s| if AOS.contains(&s) { format!("{s}/0") } else { s.to_string() })
        .collect::<Vec<_>>().join("/")
}

fn slot(key: &str) -> String {
    explicit(EQUILIBRIUM_SLOTS.iter().find(|(k, _)| *k == key).map(|(_, p)| *p).unwrap())
}

/// 文件名或头一行里的炮号与时间：`g063982.04800` → (63982, 4.8 s)；
/// 头里的 `# 63982  4800ms` 同样认。
pub fn shot_time(header: &str, source: &str) -> (Option<i64>, Option<f64>) {
    let name = source.rsplit(['/', '\\']).next().unwrap_or(source);
    if let Some(rest) = name.strip_prefix('g') {
        if let Some((a, b)) = rest.split_once('.') {
            let b_digits: String = b.chars().take_while(|c| c.is_ascii_digit()).collect();
            if let (Ok(shot), Ok(ms)) = (a.parse::<i64>(), b_digits.parse::<i64>()) {
                if !b_digits.is_empty() {
                    return (Some(shot), Some(ms as f64 / 1000.0));
                }
            }
        }
    }
    //: `# 63982  4800ms`
    let mut shot = None;
    let mut time = None;
    if let Some(i) = header.find('#') {
        let toks: Vec<&str> = header[i + 1..].split_whitespace().collect();
        if let Some(t) = toks.first().and_then(|t| t.parse::<i64>().ok()) {
            shot = Some(t);
        }
        for t in toks.iter().skip(1) {
            //: `4800ms`, and the glued vintage `4800msmodified`
            let digits: String = t.chars().take_while(|c| c.is_ascii_digit() || *c == '.').collect();
            if !digits.is_empty() && t[digits.len()..].starts_with("ms") {
                if let Ok(ms) = digits.parse::<f64>() {
                    time = Some(ms / 1000.0);
                    break;
                }
            }
        }
    }
    (shot, time)
}

/// g-file → `fyo:equilibrium` 文档。
///
/// `source` 进 `@id`（`fylite:equilibrium/<source>`）并用来猜炮号与时间。
pub fn gfile_to_document(g: &GFile, source: &str) -> Node {
    let mut doc = fyodoc::new_document("equilibrium", &format!("fylite:equilibrium/{source}"));
    let (shot, time) = shot_time(&g.header, source);
    let n = g.fpol.len();
    let psi1d: Vec<f64> = (0..n).map(|i| {
        let x = if n > 1 { i as f64 / (n - 1) as f64 } else { 0.0 };
        g.simag + x * (g.sibry - g.simag)
    }).collect();
    let (r, z) = grid(g);
    let put = |doc: &mut Node, key: &str, v: Node| { doc.set(&slot(key), v).unwrap(); };
    put(&mut doc, "ip", g.current.into());
    put(&mut doc, "axis_r", g.rmaxis.into());
    put(&mut doc, "axis_z", g.zmaxis.into());
    put(&mut doc, "psi_axis", g.simag.into());
    put(&mut doc, "psi_boundary", g.sibry.into());
    put(&mut doc, "r0", g.rcentr.into());
    put(&mut doc, "b0", g.bcentr.into());
    put(&mut doc, "psi_1d", psi1d.into());
    put(&mut doc, "f", g.fpol.clone().into());
    put(&mut doc, "pressure", g.pres.clone().into());
    put(&mut doc, "f_df_dpsi", g.ffprim.clone().into());
    put(&mut doc, "dpressure_dpsi", g.pprime.clone().into());
    put(&mut doc, "q_1d", g.qpsi.clone().into());
    put(&mut doc, "grid_r", r.clone().into());
    put(&mut doc, "grid_z", z.clone().into());
    //: g-file: psirz[z][r] (R fastest) -> document psi[R][Z]
    let psi_zr = Array { shape: vec![g.nh, g.nw], data: crate::document::ArrayData::F64(g.psirz.clone()) };
    put(&mut doc, "psi_2d", Node::Array(psi_zr.transposed()));
    put(&mut doc, "boundary_r", g.rbbbs.clone().into());
    put(&mut doc, "boundary_z", g.zbbbs.clone().into());
    put(&mut doc, "limiter_r", g.rlim.clone().into());
    put(&mut doc, "limiter_z", g.zlim.clone().into());
    let p2 = "time_slice/0/profiles_2d/0";
    doc.set(&format!("{p2}/@type"), "fyo:equilibrium_profiles_2d".into()).unwrap();
    doc.set(&format!("{p2}/grid_type/index"), Node::Int(1)).unwrap();
    doc.set(&format!("{p2}/grid_type/name"), "rectangular".into()).unwrap();
    if let Some(t) = time {
        doc.set("time_slice/0/time", t.into()).unwrap();
    }
    if let Some(s) = shot {
        doc.set("fylite:shot", Node::Int(s)).unwrap();
    }
    //: 头一行与格子的几何：文档的 `dim1`/`dim2` 已经足够重建 rdim/zdim/rleft/zmid，
    //: 但头一行只能原样带着；`nbbbs`/`limitr` 由数组长度说话。
    doc.set("fylite:gfile/header", g.header.clone().into()).unwrap();
    doc
}

/// 头里的 (R, Z) 格。
pub fn grid(g: &GFile) -> (Vec<f64>, Vec<f64>) {
    let r: Vec<f64> = (0..g.nw).map(|i| g.rleft + g.rdim * i as f64 / (g.nw.max(2) - 1) as f64).collect();
    let z: Vec<f64> = (0..g.nh).map(|j| g.zmid - g.zdim / 2.0 + g.zdim * j as f64 / (g.nh.max(2) - 1) as f64).collect();
    (r, z)
}

#[derive(Debug, Clone, PartialEq)]
pub enum ConvError {
    /// 文档里没有这个槽。
    Missing(String),
    /// 剖面长度与格子对不上。★不重采样：那是数值选择，不是格式转换。
    Length { what: String, got: usize, want: usize },
    /// `psi_2d` 的形状不是 `[nw, nh]`。
    Shape { got: Vec<usize>, want: Vec<usize> },
}

impl std::fmt::Display for ConvError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ConvError::Missing(p) => write!(f, "fyo:equilibrium document has no {p}"),
            ConvError::Length { what, got, want } =>
                write!(f, "{what} has {got} points and the radial grid nw={want}; resample before writing a g-file"),
            ConvError::Shape { got, want } => write!(f, "psi_2d has shape {got:?}, expected {want:?} ([R, Z])"),
        }
    }
}

impl std::error::Error for ConvError {}

/// `fyo:equilibrium` 文档 → g-file（`as_geqdsk` 的逆向）。
///
/// `slice` 选时间片（缺省第 0 个）。
pub fn document_to_gfile(doc: &Node, slice: usize) -> Result<GFile, ConvError> {
    let at = |key: &str| -> String {
        let p = EQUILIBRIUM_SLOTS.iter().find(|(k, _)| *k == key).map(|(_, p)| *p).unwrap();
        explicit(p).replacen("time_slice/0", &format!("time_slice/{slice}"), 1)
    };
    let vec = |key: &str| -> Result<Vec<f64>, ConvError> {
        doc.get(&at(key)).and_then(Node::to_f64_vec).ok_or_else(|| ConvError::Missing(at(key)))
    };
    let opt_vec = |key: &str| -> Vec<f64> { doc.get(&at(key)).and_then(Node::to_f64_vec).unwrap_or_default() };
    let num = |key: &str| -> Result<f64, ConvError> {
        doc.get(&at(key)).and_then(Node::as_f64).ok_or_else(|| ConvError::Missing(at(key)))
    };
    let r = vec("grid_r")?;
    let z = vec("grid_z")?;
    let (nw, nh) = (r.len(), z.len());
    let psi = doc.get(&at("psi_2d")).and_then(Node::as_array).ok_or_else(|| ConvError::Missing(at("psi_2d")))?;
    if psi.shape != vec![nw, nh] {
        return Err(ConvError::Shape { got: psi.shape.clone(), want: vec![nw, nh] });
    }
    let mut g = GFile { nw, nh, ..Default::default() };
    for (name, key) in [("fpol", "f"), ("pres", "pressure"), ("ffprim", "f_df_dpsi"),
                        ("pprime", "dpressure_dpsi"), ("qpsi", "q_1d")] {
        let v = vec(key)?;
        if v.len() != nw {
            return Err(ConvError::Length { what: key.into(), got: v.len(), want: nw });
        }
        match name {
            "fpol" => g.fpol = v,
            "pres" => g.pres = v,
            "ffprim" => g.ffprim = v,
            "pprime" => g.pprime = v,
            _ => g.qpsi = v,
        }
    }
    g.rdim = r[nw - 1] - r[0];
    g.zdim = z[nh - 1] - z[0];
    g.rleft = r[0];
    g.zmid = 0.5 * (z[0] + z[nh - 1]);
    g.rcentr = num("r0")?;
    //: b0 may have been promoted to a 1-element array by a DD round trip
    g.bcentr = doc.get(&at("b0")).and_then(Node::to_f64_vec).and_then(|v| v.first().copied()).ok_or_else(|| ConvError::Missing(at("b0")))?;
    g.current = num("ip")?;
    g.rmaxis = num("axis_r")?;
    g.zmaxis = num("axis_z")?;
    g.simag = num("psi_axis")?;
    g.sibry = num("psi_boundary")?;
    g.psirz = psi.transposed().to_f64().unwrap();
    g.rbbbs = opt_vec("boundary_r");
    g.zbbbs = opt_vec("boundary_z");
    g.nbbbs = g.rbbbs.len().min(g.zbbbs.len());
    g.rlim = opt_vec("limiter_r");
    g.zlim = opt_vec("limiter_z");
    //: ★the limiter travels with the equilibrium in a fyo document; in a DD
    //: tree it has gone to the wall IDS — accept it from there too
    if g.rlim.is_empty() {
        if let Some(r) = doc.get("fylite:wall/description_2d/0/limiter/unit/0/outline/r").and_then(Node::to_f64_vec) {
            g.rlim = r;
            g.zlim = doc.get("fylite:wall/description_2d/0/limiter/unit/0/outline/z").and_then(Node::to_f64_vec).unwrap_or_default();
        }
    }
    g.limitr = g.rlim.len().min(g.zlim.len());
    g.header = match doc.get("fylite:gfile/header").and_then(Node::as_str) {
        Some(h) => h.to_string(),
        None => format!("{:<48}   0{:4}{:4}",
            format!("fylite {}", doc.get("@id").and_then(Node::as_str).unwrap_or("equilibrium")).chars().take(48).collect::<String>(),
            nw, nh),
    };
    Ok(g)
}

/// 文档里的限制器（`fylite:limiter`）→ 一份 `fyo:wall` 文档：DD 布局里它住在 wall IDS。
pub fn limiter_to_wall(doc: &Node) -> Option<Node> {
    let r = doc.get("fylite:limiter/r").and_then(Node::to_f64_vec)?;
    let z = doc.get("fylite:limiter/z").and_then(Node::to_f64_vec)?;
    if r.is_empty() {
        return None;
    }
    let id = doc.get("@id").and_then(Node::as_str).unwrap_or("equilibrium").replacen("equilibrium", "wall", 1);
    let mut w = fyodoc::new_document("wall", &id);
    w.set("ids_properties/homogeneous_time", Node::Int(2)).unwrap();
    w.set("description_2d/0/type/index", Node::Int(0)).unwrap();
    w.set("description_2d/0/limiter/type/index", Node::Int(0)).unwrap();
    w.set("description_2d/0/limiter/unit/0/name", "limiter".into()).unwrap();
    w.set("description_2d/0/limiter/unit/0/outline/r", r.into()).unwrap();
    w.set("description_2d/0/limiter/unit/0/outline/z", z.into()).unwrap();
    Some(w)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::geqdsk;

    const SYN: &str = include_str!("../testdata/g_synthetic.geqdsk");

    #[test]
    fn slots_walk_through_the_declared_aos_at_index_zero() {
        assert_eq!(explicit("time_slice/profiles_2d/psi"), "time_slice/0/profiles_2d/0/psi");
        assert_eq!(explicit("vacuum_toroidal_field/b0"), "vacuum_toroidal_field/b0");
    }

    #[test]
    fn shot_and_time_come_from_the_name_or_the_header() {
        assert_eq!(shot_time("", "/x/g063982.04800"), (Some(63982), Some(4.8)));
        assert_eq!(shot_time("  EFITD    12/10/2013    # 63982  4800msmodified   0 129 129", "eq.txt"),
                   (Some(63982), Some(4.8)));
        assert_eq!(shot_time("  fylite  0  65  65", "g_synthetic.geqdsk"), (None, None));
    }

    #[test]
    fn a_gfile_round_trips_through_the_document_with_psi_in_r_z_order() {
        let g = geqdsk::parse(SYN).unwrap();
        let d = gfile_to_document(&g, "g_synthetic.geqdsk");
        assert_eq!(d.get("@type").and_then(Node::as_str), Some("fyo:equilibrium"));
        let psi = d.get("time_slice/0/profiles_2d/0/psi").unwrap().as_array().unwrap();
        assert_eq!(psi.shape, vec![g.nw, g.nh]);
        //: document psi[i_r][j_z] == g-file psirz[j_z * nw + i_r]
        let (i, j) = (7, 11);
        assert_eq!(psi.as_f64().unwrap()[i * g.nh + j], g.psirz[j * g.nw + i]);
        assert_eq!(d.get("time_slice/0/profiles_2d/0/grid/dim1").map(Node::shape), Some(vec![g.nw]));
        assert_eq!(d.get("fylite:limiter/r").map(Node::shape), Some(vec![g.limitr]));
        let again = document_to_gfile(&d, 0).unwrap();
        assert_eq!(again.psirz, g.psirz);
        assert_eq!(again.fpol, g.fpol);
        assert_eq!((again.nw, again.nh, again.nbbbs, again.limitr), (g.nw, g.nh, g.nbbbs, g.limitr));
        assert!((again.rdim - g.rdim).abs() < 1e-12 && (again.zmid - g.zmid).abs() < 1e-12);
        assert_eq!(again.header, g.header);
        let text = geqdsk::format_gfile(&again);
        let g3 = geqdsk::parse(&text).unwrap();
        assert_eq!(g3.psirz.len(), g.psirz.len());
    }

    #[test]
    fn a_profile_of_the_wrong_length_is_refused_not_resampled() {
        let g = geqdsk::parse(SYN).unwrap();
        let mut d = gfile_to_document(&g, "x");
        d.set("time_slice/0/profiles_1d/q", vec![1.0, 2.0].into()).unwrap();
        assert!(matches!(document_to_gfile(&d, 0), Err(ConvError::Length { .. })));
    }

    #[test]
    fn the_limiter_becomes_a_wall_ids_in_dd_layout() {
        let g = geqdsk::parse(SYN).unwrap();
        let d = gfile_to_document(&g, "x");
        let w = limiter_to_wall(&d).unwrap();
        assert_eq!(fyodoc::ids_of(&w).as_deref(), Some("wall"));
        assert_eq!(w.get("description_2d/0/limiter/unit/0/outline/r").map(Node::shape), Some(vec![g.limitr]));
        let meta = crate::ids_meta::IdsMeta::get("wall").unwrap();
        let (_, rep) = fyodoc::dd_normalize("wall", &w, &meta);
        assert!(rep.dropped.iter().all(|p| p.starts_with('@')), "{:?}", rep.dropped);
    }

    /// ★每条槽路径都必须是 DD 认的（`fylite:` 的除外）——否则 IMAS 布局写不出去。
    #[test]
    fn every_dd_slot_path_exists_in_the_dd() {
        let meta = crate::ids_meta::IdsMeta::get("equilibrium").unwrap();
        for (_, p) in EQUILIBRIUM_SLOTS {
            if !p.starts_with("fylite:") {
                assert!(meta.has(p), "{p}");
            }
        }
    }
}
