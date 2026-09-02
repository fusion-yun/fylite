//! IMAS DD 的结构表 —— 两种 IMAS 布局（netCDF、HDF5）写与读时查的那份元数据。
//!
//! ★★**它管什么。** 一条 DD 路径的**种类**（结构 / 结构数组 / 浮点 / 整数 / 字符串）、
//! **维数**、**单位**、**坐标声明**。写 IMAS netCDF 要它推**维度名**——imas-python
//! 读回时逐变量核对维名（`nc2ids.py::_validate_variable`），对不上就拒收，所以维名
//! 不是「取个合理的名字」而是「推出它会推出的那个名字」。写 IMAS HDF5 要它知道哪些
//! 段是结构数组（`time_slice[]&…`）与叶子的维数（`_SHAPE` 的长度）。
//!
//! ★表本身由 `tools/dd-ids-table.py` 从 DD 的 `IDSDef.xml` 生成（`ids/<ids>.tsv`，
//! `include_str!` 进 `ids_tables.rs`）——理由写在那个工具的抬头：与 imas-python 逐字
//! 一致，就从它读的同一份东西生成。**这里没有 DD 的一个字的文字**。
//!
//! ## 维度名的推法（imas-python `nc_metadata.py` 的移植）
//!
//! 逐条对照那份 Python，函数名也尽量保持，好让两边能并排读：
//!
//! 1. 坐标是 `1...N`（索引）→ 生一个以本路径命名的维（`a.b.c`）；若张量化后不止
//!    一维、或本身是结构数组，加 `:i`/`:j`… 后缀。叶子名叫 `time` 的是时间维。
//! 2. `coordinateN_same_as=X` → 与 X 的第 N 维同名（待解）。
//! 3. 坐标引用另一个量 `X`：若 X 在本节点之下（结构数组的 `time_slice(itime)/time`）
//!    → 维名就是 X 的点路径，且它是时间维；否则与 X 的第 0 维同名（待解）。
//! 4. `X OR Y`：主坐标 X，Y 并入 X 的维。
//! 5. `alternative_coordinate1`（DD 4）：各替代量并入主量的维。
//!
//! 张量化：每条路径的维 = 最近结构数组祖先的维 + 自己的维。齐次时间（`homogeneous_time
//! = 1`）下所有时间维并成根 `time`。

use std::collections::{HashMap, HashSet};
use std::sync::{Arc, Mutex, OnceLock};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Structure,
    StructArray,
    Float,
    Int,
    Complex,
    Str,
}

impl Kind {
    fn parse(c: &str) -> Option<Kind> {
        Some(match c {
            "S" => Kind::Structure,
            "A" => Kind::StructArray,
            "F" => Kind::Float,
            "I" => Kind::Int,
            "C" => Kind::Complex,
            "T" => Kind::Str,
            _ => return None,
        })
    }

    pub fn is_leaf(self) -> bool {
        !matches!(self, Kind::Structure | Kind::StructArray)
    }
}

#[derive(Debug, Clone)]
pub struct Entry {
    pub path: String,
    pub kind: Kind,
    pub ndim: usize,
    pub units: String,
    /// 逐维的坐标声明，DD 原文。
    pub coords: Vec<String>,
    pub same_as: Vec<String>,
    pub alternatives: Vec<String>,
}

impl Entry {
    /// 叶子名。
    pub fn name(&self) -> &str {
        self.path.rsplit('/').next().unwrap_or(&self.path)
    }
}

/// 一个 IDS 的结构表，加上 netCDF 维度推导的结果。
#[derive(Debug)]
pub struct IdsMeta {
    pub name: String,
    pub dd_version: String,
    entries: Vec<Entry>,
    index: HashMap<String, usize>,
    /// path -> 张量化后的维名（时间维未并）。
    dimensions: HashMap<String, Vec<String>>,
    /// path -> 坐标变量名表（CF `coordinates`）。
    coordinates: HashMap<String, Vec<String>>,
    /// path -> 最近的结构数组祖先。
    aos: HashMap<String, String>,
    time_dimensions: HashSet<String>,
    time_coordinates: HashSet<String>,
}

/// 把 DD 的坐标路径拆成段：去掉 `(itime)`/`(i1)`/`[0]` 这类下标，去掉前导 `/`。
pub fn path_parts(spec: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut depth = 0usize;
    for c in spec.chars() {
        match c {
            '(' | '[' => depth += 1,
            ')' | ']' => depth = depth.saturating_sub(1),
            '/' if depth == 0 => {
                if !cur.is_empty() {
                    out.push(std::mem::take(&mut cur));
                }
            }
            c if depth == 0 => cur.push(c),
            _ => {}
        }
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out
}

/// imas-python `IDSCoordinate`：一条坐标声明引用了哪些量。
struct Coord {
    /// 引用的量（`/` 连的段路径），`1...N` 与 `IDS:` 不算。
    refs: Vec<String>,
    is_time: bool,
}

fn coord_of(spec: &str) -> Coord {
    let mut refs = Vec::new();
    for s in spec.split(" OR ") {
        let s = s.trim();
        if s.is_empty() || s.starts_with("1...") || s.starts_with("IDS:") {
            continue;
        }
        let parts = path_parts(s);
        if !parts.is_empty() {
            refs.push(parts.join("/"));
        }
    }
    let is_time = refs.iter().any(|r| r.rsplit('/').next() == Some("time"));
    Coord { refs, is_time }
}

fn dot(path: &str) -> String {
    path.replace('/', ".")
}

impl IdsMeta {
    /// 解析一张表。
    pub fn parse(text: &str) -> Result<IdsMeta, String> {
        let mut name = String::new();
        let mut dd_version = String::new();
        let mut entries = Vec::new();
        for (ln, line) in text.lines().enumerate() {
            if let Some(rest) = line.strip_prefix('#') {
                let rest = rest.trim();
                if let Some(v) = rest.strip_prefix("ids ") {
                    name = v.trim().to_string();
                } else if let Some(v) = rest.strip_prefix("dd_version ") {
                    dd_version = v.trim().to_string();
                }
                continue;
            }
            if line.trim().is_empty() {
                continue;
            }
            let cols: Vec<&str> = line.split('\t').collect();
            if cols.len() < 5 {
                return Err(format!("ids table line {}: {} columns", ln + 1, cols.len()));
            }
            let kind = Kind::parse(cols[1]).ok_or_else(|| format!("ids table line {}: kind {:?}", ln + 1, cols[1]))?;
            let ndim: usize = cols[2].parse().map_err(|_| format!("ids table line {}: ndim {:?}", ln + 1, cols[2]))?;
            let split = |s: &str| -> Vec<String> {
                if s.is_empty() { Vec::new() } else { s.split('|').map(|x| x.to_string()).collect() }
            };
            let mut coords = split(cols[4]);
            coords.resize(ndim, String::new());
            let mut same_as = split(cols.get(5).copied().unwrap_or(""));
            same_as.resize(ndim, String::new());
            let alternatives: Vec<String> = cols.get(6).copied().unwrap_or("")
                .split(';').filter(|s| !s.is_empty()).map(|s| s.to_string()).collect();
            entries.push(Entry {
                path: cols[0].to_string(), kind, ndim, units: cols[3].to_string(),
                coords, same_as, alternatives,
            });
        }
        if name.is_empty() {
            return Err("ids table has no `# ids` header".into());
        }
        let index: HashMap<String, usize> = entries.iter().enumerate().map(|(i, e)| (e.path.clone(), i)).collect();
        let mut m = IdsMeta {
            name, dd_version, entries, index,
            dimensions: HashMap::new(), coordinates: HashMap::new(), aos: HashMap::new(),
            time_dimensions: HashSet::new(), time_coordinates: HashSet::new(),
        };
        m.derive_nc();
        Ok(m)
    }

    /// 内置表里的一个 IDS。缓存；没有这个 IDS 给 `None`。
    pub fn get(ids: &str) -> Option<Arc<IdsMeta>> {
        static CACHE: OnceLock<Mutex<HashMap<String, Arc<IdsMeta>>>> = OnceLock::new();
        let cache = CACHE.get_or_init(|| Mutex::new(HashMap::new()));
        if let Some(m) = cache.lock().unwrap().get(ids) {
            return Some(m.clone());
        }
        let text = crate::ids_tables::TABLES.iter().find(|(n, _)| *n == ids)?.1;
        let m = Arc::new(IdsMeta::parse(text).ok()?);
        cache.lock().unwrap().insert(ids.to_string(), m.clone());
        Some(m)
    }

    /// 内置表里有哪些 IDS。
    pub fn names() -> Vec<&'static str> {
        crate::ids_tables::TABLES.iter().map(|(n, _)| *n).collect()
    }

    pub fn entries(&self) -> &[Entry] {
        &self.entries
    }

    /// 一条路径的条目。★`_error_upper` / `_error_lower` / `_error_index` 不在表里：
    /// 前两个与本体同种类同维（imas-python 的 errorbar 规则），第三个是 0 维整数。
    pub fn entry(&self, path: &str) -> Option<Entry> {
        if let Some(&i) = self.index.get(path) {
            return Some(self.entries[i].clone());
        }
        for suffix in ["_error_upper", "_error_lower"] {
            if let Some(base) = path.strip_suffix(suffix) {
                let mut e = self.entries[*self.index.get(base)?].clone();
                if !e.kind.is_leaf() {
                    return None;
                }
                e.path = path.to_string();
                e.coords = vec![String::new(); e.ndim];
                e.same_as = (0..e.ndim).map(|_| base.to_string()).collect();
                e.alternatives.clear();
                return Some(e);
            }
        }
        if let Some(base) = path.strip_suffix("_error_index") {
            let e = &self.entries[*self.index.get(base)?];
            if !e.kind.is_leaf() {
                return None;
            }
            return Some(Entry { path: path.to_string(), kind: Kind::Int, ndim: 0, units: String::new(),
                                coords: vec![], same_as: vec![], alternatives: vec![] });
        }
        None
    }

    pub fn has(&self, path: &str) -> bool {
        self.entry(path).is_some()
    }

    pub fn kind(&self, path: &str) -> Option<Kind> {
        self.entry(path).map(|e| e.kind)
    }

    pub fn is_aos(&self, path: &str) -> bool {
        self.kind(path) == Some(Kind::StructArray)
    }

    /// 直接子条目的路径（DD 顺序）。
    pub fn children(&self, path: &str) -> Vec<&Entry> {
        let prefix = if path.is_empty() { String::new() } else { format!("{path}/") };
        self.entries.iter()
            .filter(|e| e.path.starts_with(&prefix) && !e.path[prefix.len()..].contains('/'))
            .collect()
    }

    /// 结构数组祖先，由外到内（不含自己）。
    pub fn aos_ancestors(&self, path: &str) -> Vec<String> {
        let segs: Vec<&str> = path.split('/').collect();
        let mut out = Vec::new();
        for n in 1..segs.len() {
            let p = segs[..n].join("/");
            if self.is_aos(&p) {
                out.push(p);
            }
        }
        out
    }

    /// imas-core HDF5 后端的数据集名：`time_slice[]&profiles_2d[]&psi`。
    pub fn hdf5_name(&self, path: &str) -> String {
        let segs: Vec<&str> = path.split('/').collect();
        let mut out = Vec::with_capacity(segs.len());
        for n in 1..=segs.len() {
            let p = segs[..n].join("/");
            if self.is_aos(&p) {
                out.push(format!("{}[]", segs[n - 1]));
            } else {
                out.push(segs[n - 1].to_string());
            }
        }
        out.join("&")
    }

    /// 反过来：数据集名 → DD 路径。
    pub fn path_of_hdf5_name(name: &str) -> String {
        name.replace("[]", "").replace('&', "/")
    }

    // ---- the NCMetadata port ------------------------------------------

    fn derive_nc(&mut self) {
        //: `_ut_dims`: path -> per-dimension name (None = pending)
        let mut ut_order: Vec<String> = Vec::new();
        let mut ut_dims: HashMap<String, Vec<Option<String>>> = HashMap::new();
        let mut pending: Vec<((String, usize), (String, usize))> = Vec::new();
        let mut dim_coordinates: HashMap<String, Vec<String>> = HashMap::new();
        let mut alternatives: Vec<(String, Vec<String>)> = Vec::new();
        let add_alt = |alternatives: &mut Vec<(String, Vec<String>)>, main: &str, others: Vec<String>| {
            if let Some((_, v)) = alternatives.iter_mut().find(|(m, _)| m == main) {
                v.extend(others);
            } else {
                alternatives.push((main.to_string(), others));
            }
        };

        for i in 0..self.entries.len() {
            let e = self.entries[i].clone();
            let ancestors = self.aos_ancestors(&e.path);
            let aos_level = ancestors.len();
            if let Some(parent) = ancestors.last() {
                self.aos.insert(e.path.clone(), parent.clone());
            }
            let ndim = if e.kind == Kind::StructArray { 1 } else { e.ndim };
            if e.kind == Kind::Structure {
                continue;
            }
            if ndim == 0 {
                if aos_level > 0 {
                    ut_order.push(e.path.clone());
                    ut_dims.insert(e.path.clone(), Vec::new());
                }
                continue;
            }
            // _parse_dimensions
            let mut dims: Vec<Option<String>> = Vec::with_capacity(ndim);
            for d in 0..ndim {
                let spec = e.coords.get(d).map(String::as_str).unwrap_or("");
                let coord = coord_of(spec);
                let mut dim_name: Option<String> = None;
                let mut is_time = false;
                let mut coordinates: Vec<String> = Vec::new();
                if !coord.refs.is_empty() {
                    let first = &coord.refs[0];
                    let is_ancestor = first.len() > e.path.len() && first.starts_with(&e.path)
                        && first.as_bytes()[e.path.len()] == b'/';
                    if is_ancestor {
                        dim_name = Some(dot(first));
                        is_time = coord.is_time;
                        coordinates = vec![dot(first)];
                    } else {
                        let main = first.clone();
                        if coord.refs.len() > 1 {
                            add_alt(&mut alternatives, &main, coord.refs[1..].to_vec());
                        }
                        pending.push(((e.path.clone(), d), (main, 0)));
                    }
                } else {
                    let same = coord_of(e.same_as.get(d).map(String::as_str).unwrap_or(""));
                    if !same.refs.is_empty() {
                        let main = same.refs[0].clone();
                        if same.refs.len() > 1 {
                            add_alt(&mut alternatives, &main, same.refs[1..].to_vec());
                        }
                        pending.push(((e.path.clone(), d), (main, d)));
                    } else {
                        let mut nm = dot(&e.path);
                        coordinates = vec![nm.clone()];
                        if aos_level + ndim != 1 || e.kind == Kind::StructArray {
                            nm = format!("{nm}:{}", ['i', 'j', 'k', 'l', 'm', 'n'][d.min(5)]);
                        }
                        is_time = e.name() == "time";
                        if e.kind == Kind::StructArray {
                            coordinates = self.aos_label_coordinates(&e.path);
                        }
                        dim_name = Some(nm);
                    }
                }
                if let Some(nm) = &dim_name {
                    if is_time {
                        self.time_dimensions.insert(nm.clone());
                    }
                    dim_coordinates.insert(nm.clone(), coordinates);
                }
                dims.push(dim_name);
            }
            if !e.alternatives.is_empty() {
                let alts: Vec<String> = e.alternatives.iter().map(|a| path_parts(a).join("/")).collect();
                add_alt(&mut alternatives, &e.path, alts.clone());
                if let Some(Some(nm)) = dims.last() {
                    let list = dim_coordinates.entry(nm.clone()).or_default();
                    for a in &alts {
                        list.push(dot(a));
                    }
                }
            }
            ut_order.push(e.path.clone());
            ut_dims.insert(e.path.clone(), dims);
        }

        // _merge_alternatives
        for (main, alts) in &alternatives {
            let main_dims = match ut_dims.get(main) {
                Some(d) if d.len() == 1 => d.clone(),
                _ => continue,
            };
            for alt in alts {
                match ut_dims.get_mut(alt) {
                    Some(d) if d.len() == 1 => {
                        if d[0].is_some() {
                            d[0] = None;
                            pending.push(((alt.clone(), 0), (main.clone(), 0)));
                        }
                    }
                    _ => continue,
                }
            }
            if let Some(nm) = &main_dims[0] {
                let list = dim_coordinates.entry(nm.clone()).or_default();
                for alt in alts {
                    let a = dot(alt);
                    if !list.contains(&a) {
                        list.push(a);
                    }
                }
            }
        }

        // _resolve_pending — iterate to a fixed point; an unresolvable reference
        // falls back to a name of its own so nothing is left dangling.
        loop {
            let mut progressed = false;
            let mut still = Vec::new();
            for ((path, d), (cp, cd)) in pending.drain(..) {
                let resolved = ut_dims.get(&cp).and_then(|v| v.get(cd)).cloned().flatten();
                match resolved {
                    Some(nm) => {
                        if let Some(v) = ut_dims.get_mut(&path) {
                            v[d] = Some(nm);
                        }
                        progressed = true;
                    }
                    None => still.push(((path, d), (cp, cd))),
                }
            }
            pending = still;
            if pending.is_empty() {
                break;
            }
            if !progressed {
                for ((path, d), _) in pending.drain(..) {
                    if let Some(v) = ut_dims.get_mut(&path) {
                        v[d] = Some(format!("{}:{}", dot(&path), ['i', 'j', 'k', 'l', 'm', 'n'][d.min(5)]));
                    }
                }
                break;
            }
        }

        // _tensorize_dimensions
        for path in &ut_order {
            let own: Vec<String> = ut_dims[path].iter().map(|d| d.clone().unwrap_or_default()).collect();
            let (mut dims, mut coords) = match self.aos.get(path) {
                Some(a) => (self.dimensions.get(a).cloned().unwrap_or_default(),
                            self.coordinates.get(a).cloned().unwrap_or_default()),
                None => (Vec::new(), Vec::new()),
            };
            dims.extend(own.iter().cloned());
            let e = &self.entries[self.index[path]];
            for (d, nm) in own.iter().enumerate() {
                let spec = e.coords.get(d).map(String::as_str).unwrap_or("");
                if !coord_of(spec).refs.is_empty() {
                    if let Some(c) = dim_coordinates.get(nm) {
                        coords.extend(c.iter().cloned());
                    }
                }
            }
            if e.kind == Kind::StructArray {
                coords.extend(self.aos_label_coordinates(path));
            }
            self.dimensions.insert(path.clone(), dims);
            if !coords.is_empty() {
                self.coordinates.insert(path.clone(), coords);
            }
        }
        self.time_coordinates = self.time_dimensions.iter()
            .map(|d| d.split(':').next().unwrap().to_string()).collect();
    }

    fn aos_label_coordinates(&self, path: &str) -> Vec<String> {
        let mut out = Vec::new();
        for child in ["name", "identifier", "label"] {
            if let Some(&i) = self.index.get(&format!("{path}/{child}")) {
                let e = &self.entries[i];
                if e.kind == Kind::Str && e.ndim == 0 {
                    out.push(dot(&e.path));
                }
            }
        }
        out
    }

    /// netCDF 变量的维名（`homogeneous`：时间维并成 `time`）。
    pub fn nc_dimensions(&self, path: &str, homogeneous: bool) -> Vec<String> {
        let base = self.error_base(path);
        let dims = match self.dimensions.get(base) {
            Some(d) => d,
            None => return Vec::new(),
        };
        dims.iter().map(|d| {
            if homogeneous && self.time_dimensions.contains(d) { "time".to_string() } else { d.clone() }
        }).collect()
    }

    /// netCDF 变量的 `coordinates`。
    pub fn nc_coordinates(&self, path: &str, homogeneous: bool) -> Vec<String> {
        //: an error-bar field carries only what its AoS parent carries
        let key = if path == self.error_base(path) { path.to_string() } else {
            self.aos.get(self.error_base(path)).cloned().unwrap_or_default()
        };
        let coords = match self.coordinates.get(&key) {
            Some(c) => c,
            None => return Vec::new(),
        };
        coords.iter().map(|c| {
            if homogeneous && self.time_coordinates.contains(c) { "time".to_string() } else { c.clone() }
        }).collect()
    }

    /// 最近的结构数组祖先。
    pub fn aos_parent(&self, path: &str) -> Option<&str> {
        self.aos.get(self.error_base(path)).map(String::as_str)
    }

    fn error_base<'a>(&self, path: &'a str) -> &'a str {
        if self.index.contains_key(path) {
            return path;
        }
        for suffix in ["_error_upper", "_error_lower", "_error_index"] {
            if let Some(b) = path.strip_suffix(suffix) {
                return b;
            }
        }
        path
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn path_parts_drops_indices() {
        assert_eq!(path_parts("time_slice(itime)/profiles_2d(i1)/grid/dim1"),
                   vec!["time_slice", "profiles_2d", "grid", "dim1"]);
        assert_eq!(path_parts("/time"), vec!["time"]);
        assert_eq!(path_parts("coordinate_system(process(i1)/coordinate_index)/coordinate(1)"),
                   vec!["coordinate_system", "coordinate"]);
    }

    /// ★这些期望值是 imas-python 2.x 对同一份 DD 4.1.1 写出的文件里**读出来**的
    /// （`netCDF4` 逐变量 dump），不是推的。
    #[test]
    fn equilibrium_dimensions_match_what_imas_python_writes() {
        let m = IdsMeta::get("equilibrium").expect("equilibrium table");
        let d = |p: &str| m.nc_dimensions(p, true);
        let c = |p: &str| m.nc_coordinates(p, true).join(" ");
        assert_eq!(d("time"), vec!["time"]);
        assert_eq!(d("vacuum_toroidal_field/b0"), vec!["time"]);
        assert_eq!(c("vacuum_toroidal_field/b0"), "time");
        assert!(d("vacuum_toroidal_field/r0").is_empty());
        assert_eq!(d("time_slice"), vec!["time"]);
        assert_eq!(d("time_slice/global_quantities/ip"), vec!["time"]);
        assert_eq!(c("time_slice/global_quantities/ip"), "time");
        assert_eq!(d("time_slice/profiles_1d/psi"), vec!["time", "time_slice.profiles_1d.psi:i"]);
        assert_eq!(c("time_slice/profiles_1d/psi"), "time");
        assert_eq!(d("time_slice/profiles_1d/q"), vec!["time", "time_slice.profiles_1d.psi:i"]);
        assert_eq!(c("time_slice/profiles_1d/q"), "time time_slice.profiles_1d.psi");
        assert_eq!(d("time_slice/boundary/outline/z"), vec!["time", "time_slice.boundary.outline.r:i"]);
        assert_eq!(c("time_slice/boundary/outline/z"), "time time_slice.boundary.outline.r");
        assert_eq!(d("time_slice/profiles_2d"), vec!["time", "time_slice.profiles_2d:i"]);
        assert_eq!(d("time_slice/profiles_2d/grid_type/name"), vec!["time", "time_slice.profiles_2d:i"]);
        assert_eq!(d("time_slice/profiles_2d/psi"),
                   vec!["time", "time_slice.profiles_2d:i", "time_slice.profiles_2d.grid.dim1:i",
                        "time_slice.profiles_2d.grid.dim2:i"]);
        assert_eq!(c("time_slice/profiles_2d/psi"),
                   "time time_slice.profiles_2d.grid.dim1 time_slice.profiles_2d.grid.dim2");
        //: 非齐次时间：时间维保留各自的名字
        assert_eq!(m.nc_dimensions("time_slice/global_quantities/ip", false), vec!["time_slice.time"]);
        assert_eq!(m.hdf5_name("time_slice/profiles_2d/psi"), "time_slice[]&profiles_2d[]&psi");
        assert_eq!(m.aos_ancestors("time_slice/profiles_2d/psi"), vec!["time_slice", "time_slice/profiles_2d"]);
        //: error bars follow their base
        assert_eq!(d("time_slice/profiles_1d/psi_error_upper"), d("time_slice/profiles_1d/psi"));
        assert_eq!(m.entry("time_slice/profiles_1d/psi_error_upper").unwrap().kind, Kind::Float);
    }

    #[test]
    fn core_profiles_alternative_coordinates_share_the_main_dimension() {
        let m = IdsMeta::get("core_profiles").unwrap();
        let d = |p: &str| m.nc_dimensions(p, true);
        let c = |p: &str| m.nc_coordinates(p, true).join(" ");
        assert_eq!(d("profiles_1d/grid/psi"), vec!["time", "profiles_1d.grid.rho_tor_norm:i"]);
        assert_eq!(d("profiles_1d/ion/temperature"),
                   vec!["time", "profiles_1d.ion:i", "profiles_1d.grid.rho_tor_norm:i"]);
        assert_eq!(c("profiles_1d/ion/name"), "time profiles_1d.ion.name");
        //: the full coordinate list before filtering to filled variables
        assert!(c("profiles_1d/electrons/temperature").starts_with("time profiles_1d.grid.rho_tor_norm profiles_1d.grid.rho_tor"));
        assert!(c("profiles_1d/electrons/temperature").contains("profiles_1d.grid.psi"));
    }

    #[test]
    fn magnetics_signal_time_is_a_time_dimension() {
        let m = IdsMeta::get("magnetics").unwrap();
        assert_eq!(m.nc_dimensions("flux_loop/flux/data", true), vec!["flux_loop:i", "time"]);
        assert_eq!(m.nc_dimensions("flux_loop/flux/data", false), vec!["flux_loop:i", "flux_loop.flux.time:i"]);
        assert_eq!(m.nc_coordinates("flux_loop/flux/data", true).join(" "), "flux_loop.name time");
        assert_eq!(m.nc_coordinates("flux_loop/flux/time", true).join(" "), "flux_loop.name");
        assert_eq!(m.nc_dimensions("flux_loop/position/r", true), vec!["flux_loop:i", "flux_loop.position:i"]);
        let w = IdsMeta::get("wall").unwrap();
        assert_eq!(w.nc_dimensions("description_2d/limiter/unit/outline/z", false),
                   vec!["description_2d:i", "description_2d.limiter.unit:i", "description_2d.limiter.unit.outline.r:i"]);
        assert_eq!(w.nc_coordinates("description_2d/limiter/unit/outline/z", false).join(" "),
                   "description_2d.limiter.unit.name description_2d.limiter.unit.outline.r");
    }

    #[test]
    fn every_embedded_table_parses() {
        for n in IdsMeta::names() {
            let m = IdsMeta::get(n).unwrap_or_else(|| panic!("{n}"));
            assert!(m.has("ids_properties/homogeneous_time"), "{n}");
            assert_eq!(m.dd_version, crate::ids_tables::DD_VERSION);
        }
        assert!(IdsMeta::names().len() >= 80);
    }
}
