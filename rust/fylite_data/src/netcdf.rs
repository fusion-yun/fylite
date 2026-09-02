//! netCDF —— fyo 布局与 IMAS-netCDF（imas-python 的 netCDF 后端）布局的读写。
//!
//! ## IMAS 布局（imas-python `imas/backends/netcdf/`）
//!
//! 逐条对照 `ids2nc.py` / `nc2ids.py` / `nc_metadata.py`（读回时 `nc2ids.py`
//! **逐变量核对**：dtype、维名、`coordinates` 的每一项、`units`、`sparse`，多一个
//! 不认识的属性都拒收——所以下面写的每一个属性都是它认的，一个不多）：
//!
//! * 根属性 `Conventions = "IMAS"`、`data_dictionary_version`；每个 IDS 一个组
//!   `<ids>/<occurrence>`。
//! * 变量名 = 路径以 `.` 连；结构与结构数组各一个 **`S1` 标量占位变量**（`NC_CHAR`）。
//! * 维名由 [`crate::ids_meta::IdsMeta::nc_dimensions`] 推（`nc_metadata.py` 的移植），
//!   齐次时间下时间维并成 `time`。
//! * 叶子：`f8` / `i4` / 变长字符串；`_FillValue` 取 netCDF 的缺省（`9.969209968386869e+36`、
//!   `-2147483647`、`""`）；非字符串 zlib(1)。属性：`units`（DD 有的）、`coordinates`
//!   （过滤到**已写出的**变量）、`ancillary_variables`（误差杆在场时）、`sparse`。
//! * 稀疏：元素形状不全等于维长的张量化叶子另存 `<name>:shape`（`i4`，AoS 维 + `<ndim>D`）；
//!   0 维稀疏叶子靠 `_FillValue` 说「未设」。结构数组个数不齐也走 `:shape`。
//!
//! ★`documentation` 属性**不写**：那是 DD 的文字，本仓不带（fyo `CLAUDE.md`）；
//! imas-python 读到缺席只记一条 warning，不拒收。
//!
//! ## fyo 布局
//!
//! 与 HDF5 的 fyo 布局同形（组 / 变量 / 属性；结构数组 = 带 `fylite:aos` 属性的组），
//! 维度按长度共用、命名 `n<长度>`——netCDF 要求变量的每根轴都挂一个具名维，
//! 而 fyo 文档的数组没有维名。

use crate::document::{Array, ArrayData, Map, Node};
use crate::fyodoc::{self, Bundle, DdReport};
use crate::ids_meta::{IdsMeta, Kind};
use crate::tensor::{self, LeafBox};
use netcdf::types::NcVariableType;
use netcdf::AttributeValue;
use std::collections::{BTreeMap, HashSet};
use std::path::Path;

pub const FILL_F64: f64 = 9.969209968386869e36;
pub const FILL_I32: i32 = -2147483647;

#[derive(Debug)]
pub struct Error(pub String);

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "netcdf: {}", self.0)
    }
}

impl std::error::Error for Error {}

impl From<netcdf::Error> for Error {
    fn from(e: netcdf::Error) -> Self {
        Error(e.to_string())
    }
}

impl From<crate::document::DocError> for Error {
    fn from(e: crate::document::DocError) -> Self {
        Error(e.to_string())
    }
}

type Result<T> = std::result::Result<T, Error>;

// --------------------------------------------------------------------------
// IMAS layout — writer
// --------------------------------------------------------------------------

fn dot(p: &str) -> String {
    p.replace('/', ".")
}

/// 写一束文档到一个 IMAS netCDF 文件（缺则建，已有的追加；同一 `<ids>/<occ>` 已在则拒）。
pub fn write_imas(path: &Path, bundle: &Bundle) -> Result<Vec<(String, DdReport)>> {
    let dd_version = crate::ids_tables::DD_VERSION;
    let mut file = if path.is_file() {
        let f = netcdf::append(path)?;
        match f.attribute("data_dictionary_version").map(|a| a.value()) {
            Some(Ok(AttributeValue::Str(v))) if v == dd_version => {}
            Some(Ok(AttributeValue::Str(v))) =>
                return Err(Error(format!("{} carries DD {v}, this library writes DD {dd_version}", path.display()))),
            _ => return Err(Error(format!("{} is not an IMAS netCDF file (no data_dictionary_version)", path.display()))),
        }
        f
    } else {
        let mut f = netcdf::create(path)?;
        f.add_attribute("Conventions", "IMAS")?;
        f.add_attribute("data_dictionary_version", dd_version)?;
        f
    };
    let mut reports = Vec::new();
    for doc in &bundle.docs {
        let ids = fyodoc::ids_of(doc).ok_or_else(|| Error("a document without a known `@type: fyo:<ids>`".into()))?;
        let meta = IdsMeta::get(&ids).ok_or_else(|| Error(format!("no DD table for IDS {ids:?}")))?;
        let occ = fyodoc::occurrence_of(doc);
        let (tree, report) = fyodoc::dd_normalize(&ids, doc, &meta);
        if let Some(g) = file.group(&ids)? {
            if g.group(&occ.to_string()).is_some() {
                return Err(Error(format!("IDS {ids} occurrence {occ} already exists in {}", path.display())));
            }
        }
        let mut ids_group = match file.group_mut(&ids)? {
            Some(g) => g,
            None => file.add_group(&ids)?,
        };
        let mut g = ids_group.add_group(&occ.to_string())?;
        write_ids_group(&mut g, &meta, &tree)?;
        reports.push((fyodoc::ids_key(&ids, occ), report));
    }
    file.close()?;
    Ok(reports)
}

fn write_ids_group(g: &mut netcdf::GroupMut, meta: &IdsMeta, tree: &Node) -> Result<()> {
    let homogeneous = tree.get("ids_properties/homogeneous_time").and_then(Node::as_i64) == Some(1);
    let t = tensor::tensorize(meta, tree);

    //: dimension sizes: the maximum over everything that uses the dimension
    let mut dim_size: BTreeMap<String, usize> = BTreeMap::new();
    let mut dim_order: Vec<String> = Vec::new();
    fn bump(dim_size: &mut BTreeMap<String, usize>, order: &mut Vec<String>, name: &str, size: usize) {
        let e = dim_size.entry(name.to_string()).or_insert(0);
        if !order.iter().any(|o| o == name) {
            order.push(name.to_string());
        }
        *e = (*e).max(size);
    }
    for a in &t.aos {
        let dims = meta.nc_dimensions(&a.path, homogeneous);
        if let Some(last) = dims.last() {
            bump(&mut dim_size, &mut dim_order, last, a.max_count());
        }
    }
    for leaf in &t.leaves {
        let dims = meta.nc_dimensions(&leaf.path, homogeneous);
        let n = dims.len();
        for (d, size) in leaf.field_max.iter().enumerate() {
            if let Some(name) = dims.get(n - leaf.ndim + d) {
                bump(&mut dim_size, &mut dim_order, name, *size);
            }
        }
    }
    let filled: HashSet<String> = t.leaves.iter().map(|l| dot(&l.path))
        .chain(t.structures.iter().map(|s| dot(s))).collect();

    //: sparsity, per imas-python's `determine_data_shapes`
    struct Plan<'a> { leaf: &'a tensor::LeafTensor, dims: Vec<String>, field_dims: Vec<usize>, sparse: bool }
    let mut plans: Vec<Plan> = Vec::new();
    for leaf in &t.leaves {
        let dims = meta.nc_dimensions(&leaf.path, homogeneous);
        let n = dims.len();
        let field_dims: Vec<usize> = (0..leaf.ndim).map(|d| dims.get(n - leaf.ndim + d).and_then(|nm| dim_size.get(nm)).copied().unwrap_or(0)).collect();
        let n_slots: usize = leaf.aos_max.iter().product();
        let sparse = if leaf.aos_paths.is_empty() {
            leaf.ndim > 0 && leaf.elems.first().map(|(_, v)| { let mut s = v.shape(); s.resize(leaf.ndim, 0); s != field_dims }).unwrap_or(false)
        } else if leaf.ndim > 0 {
            leaf.elems.len() != n_slots || leaf.elems.iter().any(|(_, v)| { let mut s = v.shape(); s.resize(leaf.ndim, 0); s != field_dims })
        } else {
            leaf.elems.len() != n_slots
        };
        if sparse && leaf.ndim > 0 {
            bump(&mut dim_size, &mut dim_order, &format!("{}D", leaf.ndim), leaf.ndim);
        }
        plans.push(Plan { leaf, dims, field_dims, sparse });
    }
    let mut aos_sparse: Vec<(&tensor::AosTensor, Vec<String>)> = Vec::new();
    for a in &t.aos {
        let dims = meta.nc_dimensions(&a.path, homogeneous);
        let full = dims.last().and_then(|d| dim_size.get(d)).copied().unwrap_or(0);
        let n_slots: usize = a.parent_max.iter().product();
        let sparse = a.counts.len() != n_slots || a.counts.iter().any(|(_, c)| *c != full);
        if sparse {
            bump(&mut dim_size, &mut dim_order, "1D", 1);
            aos_sparse.push((a, dims));
        }
    }
    for name in &dim_order {
        g.add_dimension(name, dim_size[name])?;
    }

    //: structure placeholders (S1 scalars), in tree order
    for s in &t.structures {
        let name = dot(s);
        let mut v = g.add_variable_from_identifiers_with_type(&name, &[], &NcVariableType::Char)?;
        if let Some(e) = meta.entry(s) {
            if !e.units.is_empty() {
                v.put_attribute("units", e.units.as_str())?;
            }
        }
    }
    let shape_doc = |var: &str, ndim: usize| -> String {
        let idx = "i,j,k";
        let _ = ndim;
        format!("Shape information for {var}.\n{var}:shape[{idx},:] describes the shape of filled data of {var}[{idx},...]. Data outside this shape is unset (i.e. filled with _Fillvalue).")
    };
    for (a, dims) in &aos_sparse {
        let name = format!("{}:shape", dot(&a.path));
        let mut sdims: Vec<&str> = dims[..dims.len() - 1].iter().map(String::as_str).collect();
        sdims.push("1D");
        let mut v = g.add_variable::<i32>(&name, &sdims)?;
        let (_, data) = a.count_box();
        let vals: Vec<i32> = data.iter().map(|&x| x as i32).collect();
        v.put_values(&vals, ..)?;
        v.put_attribute("documentation", shape_doc(&dot(&a.path), 1).as_str())?;
    }
    for p in &plans {
        let leaf = p.leaf;
        let name = dot(&leaf.path);
        let dims: Vec<&str> = p.dims.iter().map(String::as_str).collect();
        let entry = meta.entry(&leaf.path).unwrap();
        let n_aos = leaf.aos_paths.len();
        let coords: Vec<String> = meta.nc_coordinates(&leaf.path, homogeneous).into_iter().filter(|c| filled.contains(c)).collect();
        let anc: Vec<String> = ["_error_upper", "_error_lower"].iter()
            .map(|s| format!("{name}{s}")).filter(|n| filled.contains(n)).collect();
        let mut attrs: Vec<(&str, String)> = Vec::new();
        if !entry.units.is_empty() {
            attrs.push(("units", entry.units.clone()));
        }
        if !anc.is_empty() {
            attrs.push(("ancillary_variables", anc.join(" ")));
        }
        if !coords.is_empty() {
            attrs.push(("coordinates", coords.join(" ")));
        }
        match leaf.kind {
            Kind::Str => {
                //: ★no `_FillValue` on strings: the netcdf crate has no public way to
                //: `nc_def_var_fill` a string (its `NcString` is private), and an
                //: attribute of another type is refused by the C library.  imas-python
                //: pops `_FillValue` before validating and reads an unset string as `""`
                //: either way, so nothing on its side changes.
                let mut v = g.add_string_variable(&name, &dims)?;
                for (k, val) in attrs {
                    v.put_attribute(k, val.as_str())?;
                }
                if p.sparse {
                    v.put_attribute("sparse", if leaf.ndim == 0 {
                        "Sparse data, missing data is filled with _FillValue ()".to_string()
                    } else { format!("Sparse data, data shapes are stored in {name}:shape") }.as_str())?;
                }
                let (shape, data) = leaf.box_str(Some(&p.field_dims));
                let n: usize = shape.iter().product();
                if shape.is_empty() {
                    v.put_string(&data[0], ..)?;
                } else {
                    for (f, item) in data.iter().enumerate().take(n) {
                        if item.is_empty() {
                            continue;
                        }
                        let mut rem = f;
                        let mut idx = vec![0usize; shape.len()];
                        for d in (0..shape.len()).rev() {
                            idx[d] = rem % shape[d];
                            rem /= shape[d];
                        }
                        let ext: Vec<netcdf::Extent> = idx.iter().map(|&i| netcdf::Extent::from(i)).collect();
                        v.put_string(item, netcdf::Extents::from(ext))?;
                    }
                }
            }
            Kind::Int | Kind::Float => {
                let is_int = leaf.kind == Kind::Int;
                let mut v = if is_int { g.add_variable::<i32>(&name, &dims)? } else { g.add_variable::<f64>(&name, &dims)? };
                if !dims.is_empty() {
                    v.set_compression(1, false)?;
                }
                if is_int { v.set_fill_value(FILL_I32)?; } else { v.set_fill_value(FILL_F64)?; }
                for (k, val) in attrs {
                    v.put_attribute(k, val.as_str())?;
                }
                if p.sparse {
                    v.put_attribute("sparse", if leaf.ndim == 0 {
                        format!("Sparse data, missing data is filled with _FillValue ({})", if is_int { FILL_I32.to_string() } else { FILL_F64.to_string() })
                    } else { format!("Sparse data, data shapes are stored in {name}:shape") }.as_str())?;
                }
                if is_int {
                    let (shape, data) = leaf.box_i64(FILL_I32 as i64, false, Some(&p.field_dims));
                    let vals: Vec<i32> = data.iter().map(|&x| x as i32).collect();
                    if shape.is_empty() { v.put_value(vals[0], ..)?; } else { v.put_values(&vals, ..)?; }
                } else {
                    let (shape, data) = leaf.box_f64(FILL_F64, false, Some(&p.field_dims));
                    if shape.is_empty() { v.put_value(data[0], ..)?; } else { v.put_values(&data, ..)?; }
                }
            }
            Kind::Complex => return Err(Error(format!("{}: complex data is not supported", leaf.path))),
            _ => {}
        }
        if p.sparse && leaf.ndim > 0 {
            let mut sdims: Vec<&str> = p.dims[..n_aos].iter().map(String::as_str).collect();
            let nd = format!("{}D", leaf.ndim);
            sdims.push(&nd);
            let mut sv = g.add_variable::<i32>(&format!("{name}:shape"), &sdims)?;
            let (_, data) = leaf.shape_box(false);
            let vals: Vec<i32> = data.iter().map(|&x| x as i32).collect();
            sv.put_values(&vals, ..)?;
            sv.put_attribute("documentation", shape_doc(&name, leaf.ndim).as_str())?;
        }
    }
    Ok(())
}

// --------------------------------------------------------------------------
// IMAS layout — reader
// --------------------------------------------------------------------------

fn var_shape(v: &netcdf::Variable) -> Vec<usize> {
    v.dimensions().iter().map(|d| d.len()).collect()
}

fn read_var(v: &netcdf::Variable) -> Result<(Vec<usize>, ArrayData)> {
    let shape = var_shape(v);
    let n: usize = shape.iter().product::<usize>().max(1);
    let data = match v.vartype() {
        NcVariableType::String => {
            let mut out = Vec::with_capacity(n);
            if shape.is_empty() {
                out.push(v.get_string(..)?);
            } else {
                for f in 0..n {
                    let mut rem = f;
                    let mut idx = vec![0usize; shape.len()];
                    for d in (0..shape.len()).rev() {
                        idx[d] = rem % shape[d];
                        rem /= shape[d];
                    }
                    let ext: Vec<netcdf::Extent> = idx.iter().map(|&i| netcdf::Extent::from(i)).collect();
                    out.push(v.get_string(netcdf::Extents::from(ext))?);
                }
            }
            ArrayData::Str(out)
        }
        NcVariableType::Float(netcdf::types::FloatType::F64) => ArrayData::F64(v.get_values::<f64, _>(..)?),
        NcVariableType::Float(netcdf::types::FloatType::F32) => ArrayData::F64(v.get_values::<f32, _>(..)?.into_iter().map(f64::from).collect()),
        NcVariableType::Int(netcdf::types::IntType::I32) => ArrayData::I64(v.get_values::<i32, _>(..)?.into_iter().map(i64::from).collect()),
        NcVariableType::Int(netcdf::types::IntType::I64) => ArrayData::I64(v.get_values::<i64, _>(..)?),
        NcVariableType::Int(netcdf::types::IntType::I16) => ArrayData::I64(v.get_values::<i16, _>(..)?.into_iter().map(i64::from).collect()),
        NcVariableType::Int(netcdf::types::IntType::I8) => ArrayData::I64(v.get_values::<i8, _>(..)?.into_iter().map(i64::from).collect()),
        NcVariableType::Int(netcdf::types::IntType::U8) => ArrayData::I64(v.get_values::<u8, _>(..)?.into_iter().map(i64::from).collect()),
        NcVariableType::Int(netcdf::types::IntType::U16) => ArrayData::I64(v.get_values::<u16, _>(..)?.into_iter().map(i64::from).collect()),
        NcVariableType::Int(netcdf::types::IntType::U32) => ArrayData::I64(v.get_values::<u32, _>(..)?.into_iter().map(i64::from).collect()),
        NcVariableType::Int(netcdf::types::IntType::U64) => ArrayData::I64(v.get_values::<u64, _>(..)?.into_iter().map(|x| x as i64).collect()),
        NcVariableType::Char => ArrayData::Str(vec![String::new(); n]),
        other => return Err(Error(format!("variable {} has an unsupported type {other:?}", v.name()))),
    };
    Ok((shape, data))
}

fn attr_str(v: &netcdf::Variable, name: &str) -> Option<String> {
    match v.attribute_value(name)? {
        Ok(AttributeValue::Str(s)) => Some(s),
        _ => None,
    }
}

fn attr_f64(v: &netcdf::Variable, name: &str) -> Option<f64> {
    match v.attribute_value(name)? {
        Ok(AttributeValue::Double(x)) => Some(x),
        Ok(AttributeValue::Float(x)) => Some(x as f64),
        Ok(AttributeValue::Int(x)) => Some(x as f64),
        Ok(AttributeValue::Longlong(x)) => Some(x as f64),
        _ => None,
    }
}

fn read_ids_group(g: &netcdf::Group, ids: &str, occ: i64, source: &str) -> Result<Node> {
    let meta = IdsMeta::get(ids);
    let vars: Vec<netcdf::Variable> = g.variables().collect();
    let name_of = |v: &netcdf::Variable| v.name();
    let mut counts: Vec<(String, Vec<usize>, Vec<i64>)> = Vec::new();
    let mut boxes: Vec<LeafBox> = Vec::new();
    //: structure arrays: their counts
    for v in &vars {
        let name = name_of(v);
        if name.ends_with(":shape") || name.contains(':') {
            continue;
        }
        let path = name.replace('.', "/");
        let kind = meta.as_ref().and_then(|m| m.kind(&path));
        if kind != Some(Kind::StructArray) {
            continue;
        }
        let m = meta.as_ref().unwrap();
        let parent_dims: Vec<usize> = m.aos_ancestors(&path).iter()
            .map(|a| g.variable(&dot(a)).map(|_| 0).unwrap_or(0)).collect();
        let _ = parent_dims;
        if attr_str(v, "sparse").is_some() {
            if let Some(sv) = g.variable(&format!("{name}:shape")) {
                let (shape, data) = read_var(&sv)?;
                if let ArrayData::I64(d) = data {
                    counts.push((path, shape, d));
                }
            }
        } else {
            //: all elements have the dimension's size; the parent extents come
            //: from the parent AoS dimensions
            let ancestors = m.aos_ancestors(&path);
            let homogeneous = g.variable("ids_properties.homogeneous_time").and_then(|hv| hv.get_value::<i32, _>(..).ok()) == Some(1);
            let dims = m.nc_dimensions(&path, homogeneous);
            let size = dims.last().and_then(|d| g.dimension(d).map(|x| x.len())).unwrap_or(0);
            let parent_shape: Vec<usize> = dims[..dims.len().saturating_sub(1)].iter()
                .map(|d| g.dimension(d).map(|x| x.len()).unwrap_or(0)).collect();
            let _ = ancestors;
            let mut shape = parent_shape.clone();
            shape.push(1);
            let n: usize = parent_shape.iter().product::<usize>().max(1);
            counts.push((path, shape, vec![size as i64; n]));
        }
    }
    for v in &vars {
        let name = name_of(v);
        if name.contains(':') {
            continue;
        }
        let path = name.replace('.', "/");
        let kind = meta.as_ref().and_then(|m| m.kind(&path));
        if matches!(kind, Some(Kind::Structure) | Some(Kind::StructArray)) || v.vartype() == NcVariableType::Char {
            continue;
        }
        let n_aos = meta.as_ref().map(|m| m.aos_ancestors(&path).len()).unwrap_or(0);
        let (shape, data) = read_var(v)?;
        let ndim = shape.len().saturating_sub(n_aos);
        let sparse = attr_str(v, "sparse").is_some();
        let shapes = if sparse && ndim > 0 {
            g.variable(&format!("{name}:shape")).and_then(|sv| read_var(&sv).ok())
                .and_then(|(_, d)| if let ArrayData::I64(d) = d { Some(d) } else { None })
        } else { None };
        let fill = match &data {
            ArrayData::F64(_) => Some(attr_f64(v, "_FillValue").unwrap_or(FILL_F64)),
            ArrayData::I64(_) => Some(attr_f64(v, "_FillValue").unwrap_or(FILL_I32 as f64)),
            _ => None,
        };
        //: an unset non-sparse 0-D leaf outside any AoS still reads as the fill: drop it
        if n_aos == 0 && ndim == 0 {
            if let (Some(f), Some(x)) = (fill, match &data { ArrayData::F64(d) => Some(d[0]), ArrayData::I64(d) => Some(d[0] as f64), _ => None }) {
                if x == f {
                    continue;
                }
            }
        }
        boxes.push(LeafBox { path, n_aos, shape, data, shapes, fill });
    }
    let tree = tensor::detensorize(meta.as_deref(), &boxes, &counts);
    Ok(fyodoc::from_dd(ids, tree, &format!("fylite:{ids}/{source}"), occ))
}

/// 读整个 IMAS netCDF 文件。
pub fn read_imas(path: &Path) -> Result<Bundle> {
    let file = netcdf::open(path)?;
    let mut b = Bundle::new();
    let source = path.file_name().map(|s| s.to_string_lossy().to_string()).unwrap_or_default();
    for g in file.groups()? {
        let ids = g.name();
        if IdsMeta::get(&ids).is_none() {
            continue;
        }
        for og in g.groups() {
            let occ: i64 = og.name().parse().unwrap_or(0);
            b.push(read_ids_group(&og, &ids, occ, &source)?);
        }
    }
    Ok(b)
}

/// 文件是不是 IMAS netCDF：根属性 `Conventions = "IMAS"`。
pub fn is_imas_file(path: &Path) -> bool {
    netcdf::open(path).ok().and_then(|f| f.attribute("Conventions").and_then(|a| a.value().ok()))
        .map(|v| matches!(v, AttributeValue::Str(s) if s == "IMAS")).unwrap_or(false)
}

// --------------------------------------------------------------------------
// fyo layout
// --------------------------------------------------------------------------

/// 写一棵 fyo 树。
pub fn write_fyo(path: &Path, root: &Node) -> Result<()> {
    let mut file = netcdf::create(path)?;
    let m = root.as_map().ok_or_else(|| Error("a fyo document is a mapping".into()))?;
    {
        let mut g = file.root_mut().ok_or_else(|| Error("no root group".into()))?;
        write_fyo_group(&mut g, m)?;
    }
    file.close()?;
    Ok(())
}

/// netCDF 的名字不能以 `@`/`$` 开头：语义键编码成 `at__x` / `dollar__x`。
fn nc_name(k: &str) -> String {
    let k = k.replace('/', "_");
    if let Some(r) = k.strip_prefix('@') { format!("at__{r}") }
    else if let Some(r) = k.strip_prefix('$') { format!("dollar__{r}") }
    else { k }
}

fn fyo_name(n: &str) -> String {
    if let Some(r) = n.strip_prefix("at__") { format!("@{r}") }
    else if let Some(r) = n.strip_prefix("dollar__") { format!("${r}") }
    else { n.to_string() }
}

fn dim_for(g: &mut netcdf::GroupMut, len: usize) -> Result<String> {
    let name = format!("n{len}");
    if g.dimension(&name).is_none() {
        g.add_dimension(&name, len)?;
    }
    Ok(name)
}

fn write_fyo_group(g: &mut netcdf::GroupMut, m: &Map) -> Result<()> {
    for (k, v) in m.iter() {
        let name = nc_name(k);
        if k.starts_with('@') || k.starts_with('$') {
            let text = match v { Node::Str(s) => s.clone(), other => crate::json::to_string(other, false).trim_end().to_string() };
            g.add_attribute(&name, text.as_str())?;
            continue;
        }
        match v {
            Node::Null => {}
            Node::Map(sub) => { let mut sg = g.add_group(&name)?; write_fyo_group(&mut sg, sub)?; }
            Node::List(l) if !l.is_empty() && l.iter().all(|x| x.as_map().is_some()) => {
                let mut sg = g.add_group(&name)?;
                sg.add_attribute("fylite:aos", 1i32)?;
                for (i, item) in l.iter().enumerate() {
                    let mut ig = sg.add_group(&i.to_string())?;
                    write_fyo_group(&mut ig, item.as_map().unwrap())?;
                }
            }
            Node::List(_) => {
                let text = crate::json::to_string(v, false).trim_end().to_string();
                g.add_attribute(&name, text.as_str())?;
            }
            Node::Array(a) if a.shape.is_empty() => match &a.data {
                ArrayData::F64(x) => { g.add_attribute(&name, x[0])?; }
                ArrayData::I64(x) => { g.add_attribute(&name, x[0])?; }
                ArrayData::Str(x) => { g.add_attribute(&name, x[0].as_str())?; }
            },
            Node::Array(a) => {
                let dims: Vec<String> = a.shape.iter().map(|&n| dim_for(g, n)).collect::<Result<_>>()?;
                let dref: Vec<&str> = dims.iter().map(String::as_str).collect();
                match &a.data {
                    ArrayData::F64(x) => { let mut var = g.add_variable::<f64>(&name, &dref)?; if !x.is_empty() { var.put_values(x, ..)?; } }
                    ArrayData::I64(x) => { let mut var = g.add_variable::<i64>(&name, &dref)?; if !x.is_empty() { var.put_values(x, ..)?; } }
                    ArrayData::Str(x) => { g.add_attribute(&name, x.clone())?; }
                }
            }
            Node::Bool(b) => { g.add_attribute(&name, *b as i8)?; }
            Node::Int(i) => { g.add_attribute(&name, *i)?; }
            Node::Float(x) => { g.add_attribute(&name, *x)?; }
            Node::Str(s) => { g.add_attribute(&name, s.as_str())?; }
        }
    }
    Ok(())
}

fn attr_node(v: AttributeValue) -> Node {
    match v {
        AttributeValue::Str(s) => Node::Str(s),
        AttributeValue::Strs(s) => Node::Array(Array { shape: vec![s.len()], data: ArrayData::Str(s) }),
        AttributeValue::Double(x) => Node::Float(x),
        AttributeValue::Float(x) => Node::Float(x as f64),
        AttributeValue::Doubles(x) => if x.len() == 1 { Node::Float(x[0]) } else { Node::Array(Array::vec_f64(x)) },
        AttributeValue::Floats(x) => Node::Array(Array::vec_f64(x.into_iter().map(f64::from).collect())),
        AttributeValue::Int(x) => Node::Int(x as i64),
        AttributeValue::Longlong(x) => Node::Int(x),
        AttributeValue::Short(x) => Node::Int(x as i64),
        AttributeValue::Schar(x) => Node::Int(x as i64),
        AttributeValue::Uchar(x) => Node::Int(x as i64),
        AttributeValue::Uint(x) => Node::Int(x as i64),
        AttributeValue::Ulonglong(x) => Node::Int(x as i64),
        AttributeValue::Ushort(x) => Node::Int(x as i64),
        AttributeValue::Ints(x) => Node::Array(Array { shape: vec![x.len()], data: ArrayData::I64(x.into_iter().map(i64::from).collect()) }),
        AttributeValue::Longlongs(x) => Node::Array(Array { shape: vec![x.len()], data: ArrayData::I64(x) }),
        other => Node::Str(format!("{other:?}")),
    }
}

fn read_fyo_group(g: &netcdf::Group) -> Result<Node> {
    let mut m = Map::new();
    for a in g.attributes() {
        if a.name() == "fylite:aos" {
            continue;
        }
        m.insert(fyo_name(a.name()), attr_node(a.value()?));
    }
    for v in g.variables() {
        let (shape, data) = read_var(&v)?;
        m.insert(fyo_name(&v.name()), if shape.is_empty() {
            match data { ArrayData::F64(d) => Node::Float(d[0]), ArrayData::I64(d) => Node::Int(d[0]), ArrayData::Str(d) => Node::Str(d.into_iter().next().unwrap_or_default()) }
        } else { Node::Array(Array { shape, data }) });
    }
    for sg in g.groups() {
        if sg.attribute("fylite:aos").is_some() {
            let mut items: Vec<(usize, Node)> = Vec::new();
            for ig in sg.groups() {
                if let Ok(i) = ig.name().parse::<usize>() {
                    items.push((i, read_fyo_group(&ig)?));
                }
            }
            items.sort_by_key(|(i, _)| *i);
            m.insert(fyo_name(&sg.name()), Node::List(items.into_iter().map(|(_, n)| n).collect()));
        } else {
            m.insert(fyo_name(&sg.name()), read_fyo_group(&sg)?);
        }
    }
    Ok(Node::Map(m))
}

/// 读一棵 fyo 树。
pub fn read_fyo(path: &Path) -> Result<Node> {
    let file = netcdf::open(path)?;
    let root = file.root().ok_or_else(|| Error("no root group".into()))?;
    read_fyo_group(&root)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fyodoc::new_document;
    use std::path::PathBuf;

    fn tmp(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("fylite_data_nc_{}_{}", std::process::id(), name));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    fn sample() -> Bundle {
        let mut eq = new_document("equilibrium", "fylite:equilibrium/test");
        eq.set("ids_properties/comment", "fylite_data".into()).unwrap();
        eq.set("time", vec![1.0, 2.0].into()).unwrap();
        eq.set("vacuum_toroidal_field/r0", 1.75.into()).unwrap();
        eq.set("vacuum_toroidal_field/b0", vec![1.8, 1.79].into()).unwrap();
        for i in 0..2usize {
            let ts = format!("time_slice/{i}");
            eq.set(&format!("{ts}/time"), (1.0 + i as f64).into()).unwrap();
            eq.set(&format!("{ts}/global_quantities/ip"), (4.0e5 + i as f64).into()).unwrap();
            let n = 5 + i;
            let psi: Vec<f64> = (0..n).map(|k| k as f64 / (n - 1) as f64).collect();
            eq.set(&format!("{ts}/profiles_1d/psi"), psi.clone().into()).unwrap();
            eq.set(&format!("{ts}/profiles_1d/q"), psi.iter().map(|x| 1.0 + 3.0 * x).collect::<Vec<_>>().into()).unwrap();
            eq.set(&format!("{ts}/boundary/outline/r"), vec![1.4, 2.2, 1.8].into()).unwrap();
            eq.set(&format!("{ts}/boundary/outline/z"), vec![0.0, 0.0, 0.8].into()).unwrap();
            eq.set(&format!("{ts}/profiles_2d/0/grid_type/index"), Node::Int(1)).unwrap();
            eq.set(&format!("{ts}/profiles_2d/0/grid_type/name"), "rectangular".into()).unwrap();
            eq.set(&format!("{ts}/profiles_2d/0/grid/dim1"), vec![1.2, 1.7, 2.3, 2.8].into()).unwrap();
            eq.set(&format!("{ts}/profiles_2d/0/grid/dim2"), vec![-1.0, 0.0, 1.0].into()).unwrap();
            let psi2: Vec<f64> = (0..12).map(|k| k as f64 * (i + 1) as f64).collect();
            eq.set(&format!("{ts}/profiles_2d/0/psi"), Node::Array(Array::f64(vec![4, 3], psi2).unwrap())).unwrap();
        }
        let mut wall = new_document("wall", "fylite:wall/test");
        wall.set("ids_properties/homogeneous_time", Node::Int(2)).unwrap();
        wall.set("description_2d/0/type/index", Node::Int(0)).unwrap();
        wall.set("description_2d/0/limiter/unit/0/name", "main".into()).unwrap();
        wall.set("description_2d/0/limiter/unit/0/outline/r", vec![1.3, 2.3, 2.3, 1.3].into()).unwrap();
        wall.set("description_2d/0/limiter/unit/0/outline/z", vec![-1.0, -1.0, 1.0, 1.0].into()).unwrap();
        wall.set("description_2d/0/limiter/unit/1/name", "second".into()).unwrap();
        wall.set("description_2d/0/limiter/unit/1/outline/r", vec![1.35, 2.25].into()).unwrap();
        wall.set("description_2d/0/limiter/unit/1/outline/z", vec![-0.9, -0.9].into()).unwrap();
        let mut b = Bundle::new();
        b.push(eq);
        b.push(wall);
        b
    }

    #[test]
    fn imas_layout_matches_imas_python_and_round_trips() {
        let dir = tmp("imas");
        let path = dir.join("out.nc");
        let b = sample();
        write_imas(&path, &b).unwrap();
        let f = netcdf::open(&path).unwrap();
        assert!(matches!(f.attribute("Conventions").unwrap().value().unwrap(), AttributeValue::Str(s) if s == "IMAS"));
        let eqg = f.group("equilibrium").unwrap().unwrap();
        let g = eqg.group("0").unwrap();
        let dims: BTreeMap<String, usize> = g.dimensions().map(|d| (d.name(), d.len())).collect();
        assert_eq!(dims.get("time"), Some(&2));
        assert_eq!(dims.get("time_slice.profiles_1d.psi:i"), Some(&6));
        assert_eq!(dims.get("time_slice.profiles_2d:i"), Some(&1));
        assert_eq!(dims.get("1D"), Some(&1));
        let psi = g.variable("time_slice.profiles_1d.psi").unwrap();
        let dn: Vec<String> = psi.dimensions().iter().map(|d| d.name()).collect();
        assert_eq!(dn, vec!["time", "time_slice.profiles_1d.psi:i"]);
        assert_eq!(attr_str(&psi, "coordinates").as_deref(), Some("time"));
        assert_eq!(attr_str(&psi, "units").as_deref(), Some("Wb"));
        assert!(attr_str(&psi, "sparse").unwrap().contains("time_slice.profiles_1d.psi:shape"));
        let q = g.variable("time_slice.profiles_1d.q").unwrap();
        assert_eq!(attr_str(&q, "coordinates").as_deref(), Some("time time_slice.profiles_1d.psi"));
        let z = g.variable("time_slice.boundary.outline.z").unwrap();
        assert_eq!(attr_str(&z, "coordinates").as_deref(), Some("time time_slice.boundary.outline.r"));
        assert!(attr_str(&z, "sparse").is_none());
        let sh = g.variable("time_slice.profiles_1d.psi:shape").unwrap();
        assert_eq!(sh.get_values::<i32, _>(..).unwrap(), vec![5, 6]);
        let p2 = g.variable("time_slice.profiles_2d.psi").unwrap();
        let dn: Vec<String> = p2.dimensions().iter().map(|d| d.name()).collect();
        assert_eq!(dn, vec!["time", "time_slice.profiles_2d:i", "time_slice.profiles_2d.grid.dim1:i", "time_slice.profiles_2d.grid.dim2:i"]);
        assert_eq!(&p2.get_values::<f64, _>(..).unwrap()[..3], &[0.0, 1.0, 2.0]);
        assert_eq!(g.variable("ids_properties").unwrap().vartype(), NcVariableType::Char);
        assert_eq!(g.variable("time_slice.profiles_2d.grid_type.name").unwrap().vartype(), NcVariableType::String);
        assert!(g.variable("vacuum_toroidal_field.b0").unwrap().fill_value::<f64>().unwrap().map(|x| (x - FILL_F64).abs() < 1e20).unwrap_or(false));
        let wg = f.group("wall").unwrap().unwrap();
        let w = wg.group("0").unwrap();
        let wr = w.variable("description_2d.limiter.unit.outline.r").unwrap();
        let dn: Vec<String> = wr.dimensions().iter().map(|d| d.name()).collect();
        assert_eq!(dn, vec!["description_2d:i", "description_2d.limiter.unit:i", "description_2d.limiter.unit.outline.r:i"]);
        assert_eq!(attr_str(&wr, "coordinates").as_deref(), Some("description_2d.limiter.unit.name"));
        drop(f);
        let back = read_imas(&path).unwrap();
        let eq = back.get("equilibrium").unwrap();
        assert_eq!(eq.get("time_slice/1/profiles_1d/psi"), b.docs[0].get("time_slice/1/profiles_1d/psi"));
        assert_eq!(eq.get("time_slice/0/profiles_1d/q"), b.docs[0].get("time_slice/0/profiles_1d/q"));
        assert_eq!(eq.get("time_slice/0/profiles_2d/0/psi"), b.docs[0].get("time_slice/0/profiles_2d/0/psi"));
        assert_eq!(eq.get("time_slice/1/profiles_2d/0/grid_type/name").and_then(Node::as_str), Some("rectangular"));
        assert_eq!(eq.get("ids_properties/comment").and_then(Node::as_str), Some("fylite_data"));
        assert_eq!(eq.get("ids_properties/homogeneous_time").and_then(Node::as_i64), Some(1));
        assert_eq!(eq.get("vacuum_toroidal_field/r0").and_then(Node::as_f64), Some(1.75));
        assert_eq!(eq.get("vacuum_toroidal_field/b0").and_then(Node::to_f64_vec), Some(vec![1.8, 1.79]));
        let wl = back.get("wall").unwrap();
        assert_eq!(wl.get("description_2d/0/limiter/unit/1/outline/r").and_then(Node::to_f64_vec), Some(vec![1.35, 2.25]));
        assert_eq!(wl.get("description_2d/0/limiter/unit/1/name").and_then(Node::as_str), Some("second"));
        assert_eq!(wl.get("description_2d/0/type/index").and_then(Node::as_i64), Some(0));
        //: appending another occurrence keeps the file valid
        let mut w2 = b.docs[1].clone();
        w2.set(fyodoc::OCCURRENCE_KEY, Node::Int(1)).unwrap();
        write_imas(&path, &Bundle::one(w2)).unwrap();
        let again = read_imas(&path).unwrap();
        assert_eq!(again.keys().len(), 3);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn fyo_layout_round_trips() {
        let dir = tmp("fyo");
        let path = dir.join("eq.nc");
        let b = sample();
        write_fyo(&path, &b.docs[0]).unwrap();
        let back = read_fyo(&path).unwrap();
        assert_eq!(back.get("@type").and_then(Node::as_str), Some("fyo:equilibrium"));
        assert_eq!(back.get("time_slice/1/profiles_1d/psi"), b.docs[0].get("time_slice/1/profiles_1d/psi"));
        assert_eq!(back.get("time_slice/0/profiles_2d/0/psi"), b.docs[0].get("time_slice/0/profiles_2d/0/psi"));
        assert_eq!(back.get("time_slice/0/profiles_2d/0/grid_type/name").and_then(Node::as_str), Some("rectangular"));
        assert_eq!(back.get("vacuum_toroidal_field/r0").and_then(Node::as_f64), Some(1.75));
        let _ = std::fs::remove_dir_all(&dir);
    }
}
