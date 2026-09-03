//! HDF5 —— fyo 布局与 IMAS（imas-core HDF5 后端）布局的读写。
//!
//! ## fyo 布局
//!
//! 与 `python/fylite/fyo.py::write` **同一形状**：映射是组，数值数组是数据集，
//! `@` 键、标量、字符串、字符串表是属性；结构数组是带 `fylite:aos` 属性的组，
//! 元素是 `0`、`1`… 子组（顺序由此保住）。一份 Python 写的文件这里读得回来，反之亦然
//! ——`python/tests/test_fydoc.py` 对拍。
//!
//! ## IMAS 布局（imas-core 5.x 的 HDF5 后端）
//!
//! 一个**目录**：`master.h5` + 每个 IDS 一个 `<ids>[_<occ>].h5`。逐条对照
//! `IMAS-Core/src/hdf5/`（`hdf5_utils.cpp`、`hdf5_writer.cpp`、`hdf5_dataset_handler.cpp`）：
//!
//! * 每个文件 1024 字节 user block，开头写数据目录的路径；根属性
//!   `HDF5_BACKEND_VERSION = "1.0"`（定长 C 串）。master 里每个 IDS 一条外部链接
//!   `<key>` → `./<key>.h5:/<key>`。
//! * 数据集名：路径以 `&` 连，结构数组段带 `[]`：`time_slice[]&profiles_2d[]&psi`。
//! * 张量化：AoS 轴在前取最大个数，**数据轴反序**（Fortran 序：`dims[i+AOSRank] =
//!   size[dim-i-1]`），元素的真实形状（也反序）存 `<name>_SHAPE`（int32，AoS 轴 + [ndim]），
//!   各结构数组的元素个数存 `<aos>[]&AOS_SHAPE`（int32，父 AoS 轴 + [1]）。
//! * 非标量数据集：分块（imas-core 的块算法原样移植）、shuffle + deflate(1)、
//!   maxdims 无限；填充 double `-9.0E40`、int `-999999999`、形状表 0。
//!   标量数据集不分块、不填充。字符串是变长 UTF-8。
//!
//! ★★数据轴反序不是「形状反过来写」，是**转置**：`(4, 3)` 的 numpy 数组在盘上是
//! `(3, 4)`，且 `d[j][i] = a[i][j]`——实测（imas-core 5.7.2 写、h5py 读）。所以这里
//! 每个元素经 [`crate::document::Array::transposed`] 进盒子，读回时再转回来。
//! 把 `dims` 反过来而字节不动，读出来的是**静默转置**了的 ψ——与 mdsip 那一课
//! 同一形状的错（`mdsip.rs` 抬头「dimension order trap」）。

use crate::document::{Array, ArrayData, Map, Node};
use crate::fyodoc::{self, Bundle, DdReport};
use crate::ids_meta::{IdsMeta, Kind};
use crate::tensor::{self, LeafBox};
use hdf5::types::{FixedAscii, FloatSize, IntSize, TypeDescriptor, VarLenUnicode};
use hdf5::{File, Group, SimpleExtents};
use std::io::{Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

pub const BACKEND_VERSION: &str = "1.0";
pub const MASTER: &str = "master.h5";
pub const FILL_F64: f64 = -9.0e40;
pub const FILL_I32: i32 = -999_999_999;
const USERBLOCK: u64 = 1024;

#[derive(Debug)]
pub struct Error(pub String);

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "hdf5: {}", self.0)
    }
}

impl std::error::Error for Error {}

impl From<hdf5::Error> for Error {
    fn from(e: hdf5::Error) -> Self {
        Error(e.to_string())
    }
}

impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Error(e.to_string())
    }
}

impl From<crate::document::DocError> for Error {
    fn from(e: crate::document::DocError) -> Self {
        Error(e.to_string())
    }
}

type Result<T> = std::result::Result<T, Error>;

fn vlu(s: &str) -> Result<VarLenUnicode> {
    s.parse::<VarLenUnicode>().map_err(|e| Error(format!("string {s:?}: {e}")))
}

// --------------------------------------------------------------------------
// fyo layout
// --------------------------------------------------------------------------

/// 写一棵 fyo 树（单份文档或束的容器）。
pub fn write_fyo(path: &Path, root: &Node) -> Result<()> {
    let file = File::create(path)?;
    let m = root.as_map().ok_or_else(|| Error("a fyo document is a mapping".into()))?;
    write_group(&file, m)?;
    file.close()?;
    Ok(())
}

fn write_attr_str(g: &Group, name: &str, s: &str) -> Result<()> {
    g.new_attr::<VarLenUnicode>().create(name)?.write_scalar(&vlu(s)?)?;
    Ok(())
}

fn write_group(g: &Group, m: &Map) -> Result<()> {
    for (k, v) in m.iter() {
        let name = k.replace('/', "_");
        if k.starts_with('@') || k.starts_with('$') {
            let text = match v {
                Node::Str(s) => s.clone(),
                other => crate::json::to_string(other, false).trim_end().to_string(),
            };
            write_attr_str(g, &name, &text)?;
            continue;
        }
        match v {
            Node::Null => {}
            Node::Map(sub) => write_group(&g.create_group(&name)?, sub)?,
            Node::List(l) if !l.is_empty() && l.iter().all(|x| x.as_map().is_some()) => {
                let grp = g.create_group(&name)?;
                grp.new_attr::<bool>().create("fylite:aos")?.write_scalar(&true)?;
                for (i, item) in l.iter().enumerate() {
                    write_group(&grp.create_group(&i.to_string())?, item.as_map().unwrap())?;
                }
            }
            Node::List(l) => {
                //: an empty list or a ragged one: JSON text, marked as such
                let text = crate::json::to_string(v, false).trim_end().to_string();
                let _ = l;
                write_attr_str(g, &name, &text)?;
            }
            Node::Array(a) if a.shape.is_empty() => match &a.data {
                ArrayData::F64(x) => { g.new_attr::<f64>().create(name.as_str())?.write_scalar(&x[0])?; }
                ArrayData::I64(x) => { g.new_attr::<i64>().create(name.as_str())?.write_scalar(&x[0])?; }
                ArrayData::Str(x) => write_attr_str(g, &name, &x[0])?,
            },
            Node::Array(a) => match &a.data {
                ArrayData::F64(x) => {
                    let ds = g.new_dataset::<f64>().shape(a.shape.clone()).create(name.as_str())?;
                    ds.write_raw(x)?;
                }
                ArrayData::I64(x) => {
                    let ds = g.new_dataset::<i64>().shape(a.shape.clone()).create(name.as_str())?;
                    ds.write_raw(x)?;
                }
                ArrayData::Str(x) => {
                    //: a list of names — an attribute, beside the array it labels
                    let vals: Vec<VarLenUnicode> = x.iter().map(|s| vlu(s)).collect::<Result<_>>()?;
                    g.new_attr::<VarLenUnicode>().shape(vals.len()).create(name.as_str())?.write_raw(&vals)?;
                }
            },
            Node::Bool(b) => { g.new_attr::<bool>().create(name.as_str())?.write_scalar(b)?; }
            Node::Int(i) => { g.new_attr::<i64>().create(name.as_str())?.write_scalar(i)?; }
            Node::Float(x) => { g.new_attr::<f64>().create(name.as_str())?.write_scalar(x)?; }
            Node::Str(s) => write_attr_str(g, &name, s)?,
        }
    }
    Ok(())
}

/// 读一棵 fyo 树。
pub fn read_fyo(path: &Path) -> Result<Node> {
    let file = File::open(path)?;
    read_group(&file)
}

fn read_attr(g: &Group, name: &str) -> Result<Node> {
    let a = g.attr(name)?;
    let desc = a.dtype()?.to_descriptor()?;
    let shape = a.shape();
    let n: usize = shape.iter().product();
    let node = match desc {
        TypeDescriptor::Boolean => {
            let v: Vec<bool> = a.read_raw()?;
            if n == 1 { Node::Bool(v[0]) } else { Node::Array(Array::i64(shape, v.iter().map(|&b| b as i64).collect())?) }
        }
        TypeDescriptor::Integer(_) | TypeDescriptor::Unsigned(_) | TypeDescriptor::Enum(_) => {
            let v: Vec<i64> = a.read_raw()?;
            if n == 1 { Node::Int(v[0]) } else { Node::Array(Array::i64(shape, v)?) }
        }
        TypeDescriptor::Float(_) => {
            let v: Vec<f64> = a.read_raw()?;
            if n == 1 { Node::Float(v[0]) } else { Node::Array(Array::f64(shape, v)?) }
        }
        TypeDescriptor::VarLenUnicode | TypeDescriptor::VarLenAscii
        | TypeDescriptor::FixedAscii(_) | TypeDescriptor::FixedUnicode(_) => {
            let v: Vec<VarLenUnicode> = a.read_raw()?;
            let s: Vec<String> = v.iter().map(|x| x.as_str().to_string()).collect();
            if shape.is_empty() { Node::Str(s.into_iter().next().unwrap_or_default()) } else { Node::Array(Array::str(shape, s)?) }
        }
        other => return Err(Error(format!("attribute {name:?} has an unsupported type {other:?}"))),
    };
    Ok(node)
}

fn read_dataset_node(ds: &hdf5::Dataset) -> Result<Node> {
    let (shape, data) = read_dataset(ds)?;
    if shape.is_empty() {
        return Ok(match data {
            ArrayData::F64(v) => Node::Float(v[0]),
            ArrayData::I64(v) => Node::Int(v[0]),
            ArrayData::Str(v) => Node::Str(v.into_iter().next().unwrap_or_default()),
        });
    }
    Ok(Node::Array(Array { shape, data }))
}

/// 一个数据集的形状与内容（字符串按变长 UTF-8 读，定长的由 HDF5 转换）。
fn read_dataset(ds: &hdf5::Dataset) -> Result<(Vec<usize>, ArrayData)> {
    let desc = ds.dtype()?.to_descriptor()?;
    let shape = ds.shape();
    let data = match desc {
        TypeDescriptor::Float(FloatSize::U4) => ArrayData::F64(ds.read_raw::<f32>()?.into_iter().map(f64::from).collect()),
        TypeDescriptor::Float(_) => ArrayData::F64(ds.read_raw::<f64>()?),
        TypeDescriptor::Integer(IntSize::U1) => ArrayData::I64(ds.read_raw::<i8>()?.into_iter().map(i64::from).collect()),
        TypeDescriptor::Integer(IntSize::U2) => ArrayData::I64(ds.read_raw::<i16>()?.into_iter().map(i64::from).collect()),
        TypeDescriptor::Integer(IntSize::U4) => ArrayData::I64(ds.read_raw::<i32>()?.into_iter().map(i64::from).collect()),
        TypeDescriptor::Integer(_) => ArrayData::I64(ds.read_raw::<i64>()?),
        TypeDescriptor::Unsigned(IntSize::U1) => ArrayData::I64(ds.read_raw::<u8>()?.into_iter().map(i64::from).collect()),
        TypeDescriptor::Unsigned(IntSize::U2) => ArrayData::I64(ds.read_raw::<u16>()?.into_iter().map(i64::from).collect()),
        TypeDescriptor::Unsigned(IntSize::U4) => ArrayData::I64(ds.read_raw::<u32>()?.into_iter().map(i64::from).collect()),
        TypeDescriptor::Unsigned(_) => ArrayData::I64(ds.read_raw::<u64>()?.into_iter().map(|x| x as i64).collect()),
        TypeDescriptor::Boolean => ArrayData::I64(ds.read_raw::<bool>()?.into_iter().map(|b| b as i64).collect()),
        TypeDescriptor::VarLenUnicode | TypeDescriptor::VarLenAscii
        | TypeDescriptor::FixedAscii(_) | TypeDescriptor::FixedUnicode(_) => {
            let v: Vec<VarLenUnicode> = ds.read_raw()?;
            ArrayData::Str(v.iter().map(|x| x.as_str().to_string()).collect())
        }
        other => return Err(Error(format!("dataset {} has an unsupported type {other:?}", ds.name()))),
    };
    Ok((shape, data))
}

fn read_group(g: &Group) -> Result<Node> {
    let mut m = Map::new();
    let mut names = g.attr_names()?;
    names.retain(|n| n != "fylite:aos");
    for n in names {
        let v = read_attr(g, &n)?;
        //: a JSON-text attribute written for a ragged list reads back as text
        m.insert(n, v);
    }
    for name in g.member_names()? {
        match g.loc_type_by_name(&name)? {
            hdf5::LocationType::Group => {
                let sub = g.group(&name)?;
                if sub.attr("fylite:aos").is_ok() {
                    let mut items: Vec<(usize, Node)> = Vec::new();
                    for child in sub.member_names()? {
                        if let Ok(i) = child.parse::<usize>() {
                            items.push((i, read_group(&sub.group(&child)?)?));
                        }
                    }
                    items.sort_by_key(|(i, _)| *i);
                    m.insert(name, Node::List(items.into_iter().map(|(_, n)| n).collect()));
                } else {
                    m.insert(name, read_group(&sub)?);
                }
            }
            hdf5::LocationType::Dataset => {
                m.insert(name.clone(), read_dataset_node(&g.dataset(&name)?)?);
            }
            _ => {}
        }
    }
    Ok(Node::Map(m))
}

// --------------------------------------------------------------------------
// IMAS layout
// --------------------------------------------------------------------------

/// 目录里有 `master.h5` 就是一个 IMAS HDF5 数据项。
pub fn is_imas_dir(path: &Path) -> bool {
    path.is_dir() && path.join(MASTER).is_file()
}

fn write_header(file: &File) -> Result<()> {
    let v: FixedAscii<4> = FixedAscii::from_ascii(BACKEND_VERSION).map_err(|e| Error(e.to_string()))?;
    file.new_attr::<FixedAscii<4>>().create("HDF5_BACKEND_VERSION")?.write_scalar(&v)?;
    Ok(())
}

fn create_pulse_file(path: &Path) -> Result<File> {
    let file = File::with_options().with_fcpl(|p| p.userblock(USERBLOCK)).create(path)?;
    write_header(&file)?;
    Ok(file)
}

/// user block 的内容：数据目录的路径，其后补零（imas-core `writeUserBlock`）。
fn write_userblock(path: &Path, dir_text: &str) -> Result<()> {
    let mut f = std::fs::OpenOptions::new().write(true).open(path)?;
    f.seek(SeekFrom::Start(0))?;
    let bytes = dir_text.as_bytes();
    let n = bytes.len().min(USERBLOCK as usize);
    f.write_all(&bytes[..n])?;
    Ok(())
}

/// imas-core 的分块算法（`HDF5DataSetHandler::create`）。
pub fn chunk_dims(dims: &[usize], aos_rank: usize, type_size: usize) -> Vec<usize> {
    let rank = dims.len();
    let mut chunk: Vec<usize> = dims.to_vec();
    let vmin = (10.0 * 1024.0 / type_size as f64).floor() as usize;
    let vmax = (2.0 * 1024.0 * 1024.0 / type_size as f64).floor() as usize;
    let mut vp: usize = dims[..aos_rank].iter().product::<usize>().max(1);
    let mut vn: usize = dims[aos_rank..].iter().product::<usize>().max(1);
    if vp * vn > vmax {
        if vn < vmax {
            while vp > vmax / vn.max(1) {
                let mut v = 1usize;
                for c in chunk.iter_mut().take(aos_rank) {
                    let cs = ((*c as f64) / 2f64.powi(aos_rank as i32)) as usize;
                    *c = cs.max(1);
                    v *= *c;
                }
                if v == vp { break; }
                vp = v;
            }
        } else {
            for c in chunk.iter_mut().take(aos_rank) {
                *c = 1;
            }
            if rank > aos_rank {
                while vn > vmax {
                    let mut v = 1usize;
                    for c in chunk.iter_mut().skip(aos_rank) {
                        let cs = ((*c as f64) / 2f64.powi((rank - aos_rank) as i32)) as usize;
                        *c = cs.max(1);
                        v *= *c;
                    }
                    if v == vn { break; }
                    vn = v;
                }
            }
        }
    }
    if vp * vn < vmin && rank > aos_rank {
        let vn2 = vmin / vp.max(1);
        let cs = (vn2 as f64).powf(1.0 / (rank - aos_rank) as f64) as usize;
        for c in chunk.iter_mut().skip(aos_rank) {
            *c = cs.max(1);
        }
    }
    chunk.iter_mut().for_each(|c| *c = (*c).max(1));
    chunk
}

fn create_chunked<T: hdf5::H5Type>(g: &Group, name: &str, shape: &[usize], aos_rank: usize, type_size: usize,
                                   fill: Option<T>) -> Result<hdf5::Dataset> {
    let b = g.new_dataset_builder()
        .chunk(chunk_dims(shape, aos_rank, type_size))
        .shuffle()
        .deflate(1);
    let b = match fill {
        Some(f) => b.fill_value(f),
        None => b,
    };
    let ext = SimpleExtents::resizable(shape.to_vec());
    Ok(b.empty::<T>().shape(ext).create(name)?)
}

fn write_ids_group(g: &Group, meta: &IdsMeta, tree: &Node) -> Result<()> {
    let t = tensor::tensorize(meta, tree);
    for leaf in &t.leaves {
        let name = meta.hdf5_name(&leaf.path);
        let aos_rank = leaf.aos_paths.len();
        match leaf.kind {
            Kind::Str => {
                let (shape, data) = leaf.box_str(None);
                let vals: Vec<VarLenUnicode> = data.iter().map(|s| vlu(s)).collect::<Result<_>>()?;
                if shape.is_empty() {
                    g.new_dataset::<VarLenUnicode>().create(name.as_str())?.write_scalar(&vals[0])?;
                } else {
                    let ds = create_chunked::<VarLenUnicode>(g, &name, &shape, aos_rank, 16, None)?;
                    ds.write_raw(&vals)?;
                    if leaf.ndim > 0 {
                        write_shape(g, &name, leaf)?;
                    }
                }
            }
            Kind::Int => {
                let (shape, data) = leaf.box_i64(FILL_I32 as i64, true, None);
                let vals: Vec<i32> = data.iter().map(|&x| x as i32).collect();
                if shape.is_empty() {
                    g.new_dataset::<i32>().create(name.as_str())?.write_scalar(&vals[0])?;
                } else {
                    let ds = create_chunked::<i32>(g, &name, &shape, aos_rank, 4, Some(FILL_I32))?;
                    ds.write_raw(&vals)?;
                    if aos_rank > 0 && leaf.ndim > 0 {
                        write_shape(g, &name, leaf)?;
                    }
                }
            }
            Kind::Float => {
                let (shape, data) = leaf.box_f64(FILL_F64, true, None);
                if shape.is_empty() {
                    g.new_dataset::<f64>().create(name.as_str())?.write_scalar(&data[0])?;
                } else {
                    let ds = create_chunked::<f64>(g, &name, &shape, aos_rank, 8, Some(FILL_F64))?;
                    ds.write_raw(&data)?;
                    if aos_rank > 0 && leaf.ndim > 0 {
                        write_shape(g, &name, leaf)?;
                    }
                }
            }
            Kind::Complex => return Err(Error(format!("{}: complex data is not supported", leaf.path))),
            _ => {}
        }
    }
    for a in &t.aos {
        let name = format!("{}&AOS_SHAPE", meta.hdf5_name(&a.path));
        let (shape, data) = a.count_box();
        let vals: Vec<i32> = data.iter().map(|&x| x as i32).collect();
        let ds = create_chunked::<i32>(g, &name, &shape, a.parent_aos_paths.len(), 4, Some(0))?;
        ds.write_raw(&vals)?;
    }
    Ok(())
}

fn write_shape(g: &Group, name: &str, leaf: &tensor::LeafTensor) -> Result<()> {
    let (shape, data) = leaf.shape_box(true);
    let vals: Vec<i32> = data.iter().map(|&x| x as i32).collect();
    let ds = create_chunked::<i32>(g, &format!("{name}_SHAPE"), &shape, leaf.aos_paths.len(), 4, Some(0))?;
    ds.write_raw(&vals)?;
    Ok(())
}

/// 写一束文档到一个 IMAS HDF5 数据目录（缺则建；已有的 IDS 文件被替换）。
///
/// 返回每个 IDS 的归一化报告（丢掉的本地键、提成数组的标量、合成的时间）。
pub fn write_imas(dir: &Path, bundle: &Bundle) -> Result<Vec<(String, DdReport)>> {
    std::fs::create_dir_all(dir)?;
    let master_path = dir.join(MASTER);
    let dir_text = dir.to_string_lossy().to_string();
    let master = if master_path.is_file() {
        File::open_rw(&master_path)?
    } else {
        let f = create_pulse_file(&master_path)?;
        f.flush()?;
        f
    };
    let mut reports = Vec::new();
    for doc in &bundle.docs {
        let ids = fyodoc::ids_of(doc).ok_or_else(|| Error("a document without a known `@type: fyo:<ids>`".into()))?;
        let meta = IdsMeta::get(&ids).ok_or_else(|| Error(format!("no DD table for IDS {ids:?}")))?;
        let occ = fyodoc::occurrence_of(doc);
        let key = fyodoc::ids_key(&ids, occ);
        let (tree, report) = fyodoc::dd_normalize(&ids, doc, &meta);
        let ids_path = dir.join(format!("{key}.h5"));
        if ids_path.exists() {
            std::fs::remove_file(&ids_path)?;
        }
        {
            let f = create_pulse_file(&ids_path)?;
            let g = f.create_group(&key)?;
            write_ids_group(&g, &meta, &tree)?;
            f.close()?;
        }
        write_userblock(&ids_path, &dir_text)?;
        if !master.link_exists(&key) {
            master.link_external(&format!("./{key}.h5"), &key, &key)?;
        }
        reports.push((key, report));
    }
    master.close()?;
    write_userblock(&master_path, &dir_text)?;
    Ok(reports)
}

/// 数据目录里有哪些 IDS（`master.h5` 的链接名，`ids` 或 `ids_<occ>`）。
pub fn imas_ids_keys(dir: &Path) -> Result<Vec<String>> {
    let f = File::open(dir.join(MASTER))?;
    let mut names = f.member_names()?;
    names.sort();
    Ok(names)
}

/// 读一个 IDS（`key` = `ids` 或 `ids_<occ>`）成 fyo 文档。
pub fn read_imas_ids(dir: &Path, key: &str) -> Result<Node> {
    let (ids, occ) = fyodoc::split_ids_key(key);
    let path: PathBuf = dir.join(format!("{key}.h5"));
    let file = File::open(&path)?;
    let g = file.group(key)?;
    let meta = IdsMeta::get(&ids);
    let names = g.member_names()?;
    let mut counts: Vec<(String, Vec<usize>, Vec<i64>)> = Vec::new();
    let mut boxes: Vec<LeafBox> = Vec::new();
    for name in &names {
        if let Some(base) = name.strip_suffix("&AOS_SHAPE") {
            let ds = g.dataset(name)?;
            let (shape, data) = read_dataset(&ds)?;
            let data = match data { ArrayData::I64(v) => v, ArrayData::F64(v) => v.iter().map(|&x| x as i64).collect(), _ => continue };
            counts.push((IdsMeta::path_of_hdf5_name(base), shape, data));
        }
    }
    for name in &names {
        if name.ends_with("_SHAPE") {
            continue;
        }
        let ds = g.dataset(name)?;
        let (shape, data) = read_dataset(&ds)?;
        let n_aos = name.matches("[]").count();
        let path = IdsMeta::path_of_hdf5_name(name);
        let is_str = matches!(data, ArrayData::Str(_));
        //: HDF5 keeps the data axes reversed; put them back in numpy order
        let (shape, data) = match data {
            ArrayData::F64(v) => { let (s, d) = tensor::unreverse_field_axes(&shape, &v, n_aos); (s, ArrayData::F64(d)) }
            ArrayData::I64(v) => { let (s, d) = tensor::unreverse_field_axes(&shape, &v, n_aos); (s, ArrayData::I64(d)) }
            ArrayData::Str(v) => (shape, ArrayData::Str(v)),
        };
        let ndim = shape.len().saturating_sub(n_aos);
        let shapes = if ndim > 0 && n_aos > 0 {
            match g.dataset(&format!("{name}_SHAPE")) {
                Ok(sd) => {
                    let (_, sdata) = read_dataset(&sd)?;
                    let v: Vec<i64> = match sdata { ArrayData::I64(v) => v, _ => Vec::new() };
                    //: each element's shape is stored reversed too
                    let mut out = v.clone();
                    if !is_str {
                        for chunk in out.chunks_mut(ndim) {
                            chunk.reverse();
                        }
                    }
                    Some(out)
                }
                Err(_) => None,
            }
        } else { None };
        let fill = match &data {
            ArrayData::F64(_) => Some(FILL_F64),
            ArrayData::I64(_) => Some(FILL_I32 as f64),
            _ => None,
        };
        boxes.push(LeafBox { path, n_aos, shape, data, shapes, fill });
    }
    let tree = tensor::detensorize(meta.as_deref(), &boxes, &counts);
    Ok(fyodoc::from_dd(&ids, tree, &format!("fylite:{ids}/{}", path.display()), occ))
}

/// 读整个数据目录。
pub fn read_imas(dir: &Path) -> Result<Bundle> {
    let mut b = Bundle::new();
    for key in imas_ids_keys(dir)? {
        if dir.join(format!("{key}.h5")).is_file() {
            b.push(read_imas_ids(dir, &key)?);
        }
    }
    Ok(b)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::fyodoc::new_document;

    fn tmp(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("fylite_runtime_hdf5_{}_{}", std::process::id(), name));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn chunking_follows_imas_core() {
        assert_eq!(chunk_dims(&[2], 0, 8), vec![1280]);
        assert_eq!(chunk_dims(&[1], 0, 4), vec![2560]);
        assert_eq!(chunk_dims(&[2, 6], 1, 8), vec![2, 640]);
        assert_eq!(chunk_dims(&[2, 1], 1, 4), vec![2, 1280]);
        assert_eq!(chunk_dims(&[2], 1, 8), vec![2]);
        assert_eq!(chunk_dims(&[2, 1, 3, 4], 2, 8), vec![2, 1, 25, 25]);
        assert_eq!(chunk_dims(&[2, 1], 2, 16), vec![2, 1]);
    }

    fn sample_bundle() -> Bundle {
        let mut eq = new_document("equilibrium", "fylite:equilibrium/test");
        eq.set("ids_properties/comment", "fylite_runtime".into()).unwrap();
        eq.set("time", vec![1.0, 2.0].into()).unwrap();
        eq.set("vacuum_toroidal_field/r0", 1.75.into()).unwrap();
        eq.set("vacuum_toroidal_field/b0", vec![1.8, 1.79].into()).unwrap();
        for i in 0..2usize {
            let ts = format!("time_slice/{i}");
            eq.set(&format!("{ts}/time"), (1.0 + i as f64).into()).unwrap();
            eq.set(&format!("{ts}/global_quantities/ip"), (4.0e5 + i as f64).into()).unwrap();
            let n = 5 + i;
            let psi: Vec<f64> = (0..n).map(|k| k as f64 / (n - 1) as f64).collect();
            eq.set(&format!("{ts}/profiles_1d/psi"), psi.into()).unwrap();
            eq.set(&format!("{ts}/profiles_2d/0/grid_type/index"), Node::Int(1)).unwrap();
            eq.set(&format!("{ts}/profiles_2d/0/grid_type/name"), "rectangular".into()).unwrap();
            eq.set(&format!("{ts}/profiles_2d/0/grid/dim1"), vec![1.2, 1.7, 2.3, 2.8].into()).unwrap();
            eq.set(&format!("{ts}/profiles_2d/0/grid/dim2"), vec![-1.0, 0.0, 1.0].into()).unwrap();
            let psi2: Vec<f64> = (0..12).map(|k| k as f64 * (i + 1) as f64).collect();
            eq.set(&format!("{ts}/profiles_2d/0/psi"), Node::Array(Array::f64(vec![4, 3], psi2).unwrap())).unwrap();
        }
        eq.set("fylite:limiter/r", vec![1.0, 2.0].into()).unwrap();
        let mut wall = new_document("wall", "fylite:wall/test");
        wall.set("ids_properties/homogeneous_time", Node::Int(2)).unwrap();
        wall.set("description_2d/0/limiter/unit/0/name", "main".into()).unwrap();
        wall.set("description_2d/0/limiter/unit/0/outline/r", vec![1.3, 2.3, 2.3, 1.3].into()).unwrap();
        wall.set("description_2d/0/limiter/unit/1/name", "second".into()).unwrap();
        wall.set("description_2d/0/limiter/unit/1/outline/r", vec![1.35, 2.25].into()).unwrap();
        let mut b = Bundle::new();
        b.push(eq);
        b.push(wall);
        b
    }

    #[test]
    fn imas_layout_round_trips_and_has_the_backend_shape() {
        let dir = tmp("imas");
        let b = sample_bundle();
        let reports = write_imas(&dir, &b).unwrap();
        assert_eq!(reports.len(), 2);
        assert!(reports[0].1.dropped.iter().any(|p| p == "fylite:limiter"));
        assert!(dir.join("master.h5").is_file() && dir.join("equilibrium.h5").is_file() && dir.join("wall.h5").is_file());
        //: the user block carries the directory path
        let head = std::fs::read(dir.join("master.h5")).unwrap();
        assert!(head.starts_with(dir.to_string_lossy().as_bytes()));
        assert_eq!(&head[1024..1032], b"\x89HDF\r\n\x1a\n");
        let f = File::open(dir.join("equilibrium.h5")).unwrap();
        let g = f.group("equilibrium").unwrap();
        let psi = g.dataset("time_slice[]&profiles_1d&psi").unwrap();
        assert_eq!(psi.shape(), vec![2, 6]);
        assert_eq!(psi.chunk(), Some(vec![2, 640]));
        let sh = g.dataset("time_slice[]&profiles_1d&psi_SHAPE").unwrap();
        assert_eq!(sh.read_raw::<i32>().unwrap(), vec![5, 6]);
        let p2 = g.dataset("time_slice[]&profiles_2d[]&psi").unwrap();
        assert_eq!(p2.shape(), vec![2, 1, 3, 4]);
        let raw = p2.read_raw::<f64>().unwrap();
        //: transposed on disk: d[j][i] = a[i][j] with a = arange(12).reshape(4,3)
        assert_eq!(&raw[..4], &[0.0, 3.0, 6.0, 9.0]);
        assert_eq!(g.dataset("time_slice[]&profiles_2d[]&AOS_SHAPE").unwrap().read_raw::<i32>().unwrap(), vec![1, 1]);
        assert_eq!(g.dataset("time_slice[]&AOS_SHAPE").unwrap().read_raw::<i32>().unwrap(), vec![2]);
        assert_eq!(g.dataset("ids_properties&homogeneous_time").unwrap().read_scalar::<i32>().unwrap(), 1);
        assert_eq!(g.dataset("vacuum_toroidal_field&b0").unwrap().chunk(), Some(vec![1280]));
        assert_eq!(g.dataset("time_slice[]&profiles_2d[]&grid_type&name").unwrap().shape(), vec![2, 1]);
        drop(f);
        assert_eq!(imas_ids_keys(&dir).unwrap(), vec!["equilibrium", "wall"]);
        let back = read_imas(&dir).unwrap();
        let eq = back.get("equilibrium").unwrap();
        assert_eq!(eq.get("time_slice/1/profiles_1d/psi"), b.docs[0].get("time_slice/1/profiles_1d/psi"));
        assert_eq!(eq.get("time_slice/0/profiles_2d/0/psi"), b.docs[0].get("time_slice/0/profiles_2d/0/psi"));
        assert_eq!(eq.get("time_slice/1/profiles_2d/0/grid_type/name").and_then(Node::as_str), Some("rectangular"));
        assert_eq!(eq.get("ids_properties/comment").and_then(Node::as_str), Some("fylite_runtime"));
        assert_eq!(eq.get("vacuum_toroidal_field/r0").and_then(Node::as_f64), Some(1.75));
        assert_eq!(eq.get("time").and_then(Node::to_f64_vec), Some(vec![1.0, 2.0]));
        let w = back.get("wall").unwrap();
        assert_eq!(w.get("description_2d/0/limiter/unit/1/outline/r").and_then(Node::to_f64_vec), Some(vec![1.35, 2.25]));
        assert_eq!(w.get("description_2d/0/limiter/unit/0/name").and_then(Node::as_str), Some("main"));
        //: re-writing one IDS replaces it and keeps the master consistent
        write_imas(&dir, &Bundle::one(b.docs[1].clone())).unwrap();
        assert_eq!(imas_ids_keys(&dir).unwrap(), vec!["equilibrium", "wall"]);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn fyo_layout_round_trips_a_document() {
        let dir = tmp("fyo");
        let b = sample_bundle();
        let path = dir.join("eq.h5");
        write_fyo(&path, &b.docs[0]).unwrap();
        let back = read_fyo(&path).unwrap();
        assert_eq!(back.get("@type").and_then(Node::as_str), Some("fyo:equilibrium"));
        assert_eq!(back.get("time_slice/1/profiles_1d/psi"), b.docs[0].get("time_slice/1/profiles_1d/psi"));
        assert_eq!(back.get("time_slice/0/profiles_2d/0/psi"), b.docs[0].get("time_slice/0/profiles_2d/0/psi"));
        assert_eq!(back.get("time_slice/0/profiles_2d/0/grid_type/index").and_then(Node::as_i64), Some(1));
        assert_eq!(back.get("vacuum_toroidal_field/r0").and_then(Node::as_f64), Some(1.75));
        assert_eq!(back.get("fylite:limiter/r").and_then(Node::to_f64_vec), Some(vec![1.0, 2.0]));
        assert!(back.get("time_slice").unwrap().as_list().is_some());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
