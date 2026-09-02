//! 统一的读写面 —— 一个路径进来，识别格式，读成一束 fyo 文档；一束文档出去，按格式
//! 与布局落盘。每种格式的细节在各自的模块里，这里只做分派与两条跨格式的规则：
//!
//! * **限制器随平衡走**：fyo 文档把它放在 `fylite:limiter`（`fyo.rs` 的表）；写 IMAS
//!   布局时它在 DD 里的家是 `wall` IDS——束里没有 `wall` 就从限制器合成一份。
//! * **写回 g-file 只认平衡**：束里要有一份 `fyo:equilibrium`；a-file 是只读的。

use crate::detect::{self, Format};
use crate::document::{MergePolicy, Node};
use crate::fyodoc::{self, Bundle, DdReport};
use std::path::Path;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Layout {
    /// fyo 文档：语义键 + DD 键名 + `fylite:` 本地词。
    Fyo,
    /// IMAS DD：imas-python / imas-core 读写的形。
    Imas,
}

impl Layout {
    pub fn parse(s: &str) -> Option<Layout> {
        match s.to_ascii_lowercase().as_str() {
            "fyo" => Some(Layout::Fyo),
            "imas" | "dd" | "imas-dd" => Some(Layout::Imas),
            _ => None,
        }
    }

    pub fn name(self) -> &'static str {
        match self { Layout::Fyo => "fyo", Layout::Imas => "imas" }
    }
}

#[derive(Debug)]
pub struct IoError(pub String);

impl std::fmt::Display for IoError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for IoError {}

impl From<std::io::Error> for IoError {
    fn from(e: std::io::Error) -> Self { IoError(e.to_string()) }
}
impl From<crate::json::JsonError> for IoError {
    fn from(e: crate::json::JsonError) -> Self { IoError(e.to_string()) }
}
impl From<crate::yaml::YamlError> for IoError {
    fn from(e: crate::yaml::YamlError) -> Self { IoError(e.to_string()) }
}
impl From<crate::geqdsk::Error> for IoError {
    fn from(e: crate::geqdsk::Error) -> Self { IoError(e.to_string()) }
}
impl From<crate::afile::Error> for IoError {
    fn from(e: crate::afile::Error) -> Self { IoError(e.to_string()) }
}
impl From<crate::eqdsk_fyo::ConvError> for IoError {
    fn from(e: crate::eqdsk_fyo::ConvError) -> Self { IoError(e.to_string()) }
}
impl From<crate::document::DocError> for IoError {
    fn from(e: crate::document::DocError) -> Self { IoError(e.to_string()) }
}
#[cfg(feature = "hdf5")]
impl From<crate::hdf5::Error> for IoError {
    fn from(e: crate::hdf5::Error) -> Self { IoError(e.to_string()) }
}
#[cfg(feature = "netcdf")]
impl From<crate::netcdf::Error> for IoError {
    fn from(e: crate::netcdf::Error) -> Self { IoError(e.to_string()) }
}

pub type Result<T> = std::result::Result<T, IoError>;

/// 识别出来的样子。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Detected {
    pub format: Format,
    pub layout: Layout,
}

/// 看一个路径是什么。
pub fn detect(path: &Path) -> Result<Detected> {
    let format = match detect::detect(path)? {
        Some(f) => f,
        None => Format::from_extension(path).ok_or_else(|| IoError(format!(
            "{}: not a g-file, a-file, JSON, YAML, HDF5, netCDF or IMAS data directory", path.display())))?,
    };
    let layout = match format {
        Format::ImasHdf5Dir => Layout::Imas,
        Format::NetCdf => {
            #[cfg(feature = "netcdf")]
            { if crate::netcdf::is_imas_file(path) { Layout::Imas } else { Layout::Fyo } }
            #[cfg(not(feature = "netcdf"))]
            { Layout::Fyo }
        }
        Format::Json => {
            let text = std::fs::read_to_string(path)?;
            let root = crate::json::parse(&text)?;
            json_layout(&root)
        }
        Format::Yaml => {
            let text = std::fs::read_to_string(path)?;
            let root = crate::yaml::parse(&text)?;
            json_layout(&root)
        }
        _ => Layout::Fyo,
    };
    Ok(Detected { format, layout })
}

fn json_layout(root: &Node) -> Layout {
    let m = match root.as_map() { Some(m) => m, None => return Layout::Fyo };
    if m.keys().any(fyodoc::is_semantic_key) || m.contains_key("_ids") {
        return Layout::Fyo;
    }
    if m.iter().any(|(_, v)| v.as_map().map(|vm| vm.keys().any(fyodoc::is_semantic_key)).unwrap_or(false)) {
        return Layout::Fyo;
    }
    if m.keys().all(|k| crate::ids_meta::IdsMeta::get(&fyodoc::split_ids_key(k).0).is_some()) {
        return Layout::Imas;
    }
    Layout::Fyo
}

/// 读一份 JSON / YAML 文本成一棵原样的树（不套文档束）：装配文档、绑定表、装置清单
/// 都从这里进。格式看内容，看不出来按扩展名，再看不出来当 JSON。
pub fn read_node(path: &Path) -> Result<Node> {
    let text = std::fs::read_to_string(path)?;
    let format = detect::detect(path)?.or_else(|| Format::from_extension(path)).unwrap_or(Format::Json);
    match format {
        Format::Yaml => Ok(crate::yaml::parse(&text)?),
        Format::Json => Ok(crate::json::parse(&text)?),
        other => Err(IoError(format!("{}: {} is not a JSON or YAML text", path.display(), other.name()))),
    }
}

/// 读一个路径（自动识别）。
pub fn read(path: &Path) -> Result<Bundle> {
    let d = detect(path)?;
    read_as(path, d.format)
}

/// 读一个路径，按指定格式。
pub fn read_as(path: &Path, format: Format) -> Result<Bundle> {
    let source = path.file_name().map(|s| s.to_string_lossy().to_string()).unwrap_or_default();
    match format {
        Format::Json => {
            let text = std::fs::read_to_string(path)?;
            let root = crate::json::parse(&text)?;
            Ok(Bundle::from_node(root))
        }
        Format::Yaml => {
            //: fydata's A-Box dialect; same document shape as the JSON side
            let text = std::fs::read_to_string(path)?;
            let root = crate::yaml::parse(&text)?;
            Ok(Bundle::from_node(root))
        }
        Format::Geqdsk => {
            let text = std::fs::read_to_string(path)?;
            let g = crate::geqdsk::parse(&text)?;
            Ok(Bundle::one(crate::eqdsk_fyo::gfile_to_document(&g, &source)))
        }
        Format::Afile => {
            let text = std::fs::read_to_string(path)?;
            let a = crate::afile::parse(&text)?;
            Ok(Bundle::one(crate::afile::afile_to_document(&a, &source)))
        }
        Format::Hdf5 => {
            #[cfg(feature = "hdf5")]
            { Ok(Bundle::from_node(crate::hdf5::read_fyo(path)?)) }
            #[cfg(not(feature = "hdf5"))]
            { Err(IoError("built without the `hdf5` feature".into())) }
        }
        Format::ImasHdf5Dir => {
            #[cfg(feature = "hdf5")]
            { Ok(crate::hdf5::read_imas(path)?) }
            #[cfg(not(feature = "hdf5"))]
            { Err(IoError("built without the `hdf5` feature".into())) }
        }
        Format::NetCdf => {
            #[cfg(feature = "netcdf")]
            {
                if crate::netcdf::is_imas_file(path) {
                    Ok(crate::netcdf::read_imas(path)?)
                } else {
                    Ok(Bundle::from_node(crate::netcdf::read_fyo(path)?))
                }
            }
            #[cfg(not(feature = "netcdf"))]
            { Err(IoError("built without the `netcdf` feature".into())) }
        }
    }
}

/// 一次写出说了什么。
#[derive(Debug, Default, Clone)]
pub struct WriteReport {
    pub format: Option<Format>,
    pub layout: Option<Layout>,
    /// 每个 IDS 的 DD 归一化报告（只在 IMAS 布局下）。
    pub dd: Vec<(String, DdReport)>,
    /// 合成出来的文档（例如从限制器合成的 `wall`）。
    pub synthesized_docs: Vec<String>,
}

/// 写一束文档。`format` 缺省按扩展名；IMAS 布局的 HDF5 是一个目录。
pub fn write(path: &Path, bundle: &Bundle, format: Option<Format>, layout: Layout) -> Result<WriteReport> {
    let format = match format {
        Some(f) => f,
        None => {
            if layout == Layout::Imas && (path.is_dir() || path.extension().is_none()) {
                Format::ImasHdf5Dir
            } else {
                Format::from_extension(path).ok_or_else(|| IoError(format!(
                    "{}: cannot tell the output format from the name; pass one", path.display())))?
            }
        }
    };
    let format = if format == Format::Hdf5 && layout == Layout::Imas { Format::ImasHdf5Dir } else { format };
    let mut report = WriteReport { format: Some(format), layout: Some(layout), ..Default::default() };
    let bundle = if layout == Layout::Imas { with_wall_from_limiter(bundle, &mut report) } else { bundle.clone() };
    match format {
        Format::Json => {
            let root = match layout {
                Layout::Fyo => bundle.to_node(),
                Layout::Imas => {
                    let mut m = crate::document::Map::new();
                    for doc in &bundle.docs {
                        let ids = fyodoc::ids_of(doc).ok_or_else(|| IoError("a document without a known `@type: fyo:<ids>`".into()))?;
                        let meta = crate::ids_meta::IdsMeta::get(&ids).unwrap();
                        let (tree, rep) = fyodoc::dd_normalize(&ids, doc, &meta);
                        let key = fyodoc::ids_key(&ids, fyodoc::occurrence_of(doc));
                        report.dd.push((key.clone(), rep));
                        m.insert(key, tree);
                    }
                    Node::Map(m)
                }
            };
            std::fs::write(path, crate::json::to_string(&root, true))?;
        }
        Format::Geqdsk => {
            let eq = bundle.get("equilibrium").ok_or_else(|| IoError("no fyo:equilibrium document to write as a g-file".into()))?;
            let g = crate::eqdsk_fyo::document_to_gfile(eq, 0)?;
            std::fs::write(path, crate::geqdsk::format_gfile(&g))?;
        }
        Format::Afile => return Err(IoError("a-files are read-only in this library".into())),
        Format::Yaml => return Err(IoError("YAML is read-only in this library; write JSON".into())),
        Format::Hdf5 => {
            #[cfg(feature = "hdf5")]
            { crate::hdf5::write_fyo(path, &bundle.to_node())?; }
            #[cfg(not(feature = "hdf5"))]
            { return Err(IoError("built without the `hdf5` feature".into())); }
        }
        Format::ImasHdf5Dir => {
            #[cfg(feature = "hdf5")]
            { report.dd = crate::hdf5::write_imas(path, &bundle)?; }
            #[cfg(not(feature = "hdf5"))]
            { return Err(IoError("built without the `hdf5` feature".into())); }
        }
        Format::NetCdf => {
            #[cfg(feature = "netcdf")]
            {
                match layout {
                    Layout::Fyo => crate::netcdf::write_fyo(path, &bundle.to_node())?,
                    Layout::Imas => report.dd = crate::netcdf::write_imas(path, &bundle)?,
                }
            }
            #[cfg(not(feature = "netcdf"))]
            { return Err(IoError("built without the `netcdf` feature".into())); }
        }
    }
    Ok(report)
}

/// IMAS 布局：平衡文档里的限制器要有一个 `wall` 才写得出去。
fn with_wall_from_limiter(bundle: &Bundle, report: &mut WriteReport) -> Bundle {
    let mut out = bundle.clone();
    if out.get("wall").is_none() {
        if let Some(eq) = out.get("equilibrium") {
            if let Some(w) = crate::eqdsk_fyo::limiter_to_wall(eq) {
                report.synthesized_docs.push("wall".into());
                out.push(w);
            }
        }
    }
    out
}

/// 合并若干路径成一束（后者覆盖前者；结构数组按 `name` 对齐）。
pub fn merge_paths(paths: &[&Path], policy: MergePolicy) -> Result<Bundle> {
    merge_paths_with(paths, policy, Some("name"))
}

/// [`merge_paths`]，结构数组按 `key` 对齐（`None` = 只按下标）。
pub fn merge_paths_with(paths: &[&Path], policy: MergePolicy, key: Option<&str>) -> Result<Bundle> {
    let mut out = Bundle::new();
    for p in paths {
        out.merge_with(read(p)?, policy, key);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn tmp(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("fylite_data_io_{}_{}", std::process::id(), name));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    #[test]
    fn a_gfile_goes_through_every_format_and_comes_back() {
        let dir = tmp("gfile");
        let g = dir.join("g000001.00100");
        std::fs::write(&g, include_str!("../testdata/g_synthetic.geqdsk")).unwrap();
        let d = detect(&g).unwrap();
        assert_eq!((d.format, d.layout), (Format::Geqdsk, Layout::Fyo));
        let b = read(&g).unwrap();
        let eq = b.get("equilibrium").unwrap();
        assert_eq!(eq.get("time_slice/0/time").and_then(Node::as_f64), Some(0.1));
        //: fyo JSON
        let j = dir.join("eq.jsonld");
        write(&j, &b, None, Layout::Fyo).unwrap();
        assert_eq!(detect(&j).unwrap(), Detected { format: Format::Json, layout: Layout::Fyo });
        let bj = read(&j).unwrap();
        assert_eq!(bj.get("equilibrium").unwrap().get("time_slice/0/profiles_2d/0/psi"), eq.get("time_slice/0/profiles_2d/0/psi"));
        //: DD JSON grows a wall
        let jd = dir.join("dd.json");
        let rep = write(&jd, &b, None, Layout::Imas).unwrap();
        assert_eq!(rep.synthesized_docs, vec!["wall"]);
        assert_eq!(detect(&jd).unwrap(), Detected { format: Format::Json, layout: Layout::Imas });
        let bd = read(&jd).unwrap();
        assert_eq!(bd.keys().len(), 2);
        assert!(bd.get("wall").unwrap().get("description_2d/0/limiter/unit/0/outline/r").is_some());
        //: back to a g-file: identical numbers
        let g2 = dir.join("out.geqdsk");
        write(&g2, &bj, None, Layout::Fyo).unwrap();
        let again = crate::geqdsk::parse(&std::fs::read_to_string(&g2).unwrap()).unwrap();
        let orig = crate::geqdsk::parse(include_str!("../testdata/g_synthetic.geqdsk")).unwrap();
        assert_eq!(again.psirz, orig.psirz);
        #[cfg(all(feature = "hdf5", feature = "netcdf"))]
        {
            let h = dir.join("eq.h5");
            write(&h, &b, None, Layout::Fyo).unwrap();
            assert_eq!(detect(&h).unwrap(), Detected { format: Format::Hdf5, layout: Layout::Fyo });
            let n = dir.join("eq.nc");
            write(&n, &b, None, Layout::Imas).unwrap();
            assert_eq!(detect(&n).unwrap(), Detected { format: Format::NetCdf, layout: Layout::Imas });
            let nf = dir.join("eqf.nc");
            write(&nf, &b, None, Layout::Fyo).unwrap();
            assert_eq!(detect(&nf).unwrap(), Detected { format: Format::NetCdf, layout: Layout::Fyo });
            let idir = dir.join("imas");
            let rep = write(&idir, &b, None, Layout::Imas).unwrap();
            assert_eq!(rep.format, Some(Format::ImasHdf5Dir));
            assert_eq!(detect(&idir).unwrap(), Detected { format: Format::ImasHdf5Dir, layout: Layout::Imas });
            for p in [&h, &n, &nf, &idir] {
                let back = read(p).unwrap();
                let e = back.get("equilibrium").unwrap_or_else(|| panic!("{}", p.display()));
                assert_eq!(e.get("time_slice/0/profiles_2d/0/psi"), eq.get("time_slice/0/profiles_2d/0/psi"), "{}", p.display());
                assert_eq!(e.get("time_slice/0/profiles_1d/f"), eq.get("time_slice/0/profiles_1d/f"), "{}", p.display());
            }
            //: from an IMAS container back to a g-file, limiter included via the wall
            let back = read(&idir).unwrap();
            let g3 = dir.join("from_imas.geqdsk");
            let mut eqd = back.get("equilibrium").unwrap().clone();
            let w = back.get("wall").unwrap();
            eqd.set("fylite:limiter/r", w.get("description_2d/0/limiter/unit/0/outline/r").unwrap().clone()).unwrap();
            eqd.set("fylite:limiter/z", w.get("description_2d/0/limiter/unit/0/outline/z").unwrap().clone()).unwrap();
            write(&g3, &Bundle::one(eqd), None, Layout::Fyo).unwrap();
            let g3p = crate::geqdsk::parse(&std::fs::read_to_string(&g3).unwrap()).unwrap();
            assert_eq!(g3p.rlim, orig.rlim);
            assert_eq!(g3p.psirz, orig.psirz);
        }
        let _ = std::fs::remove_dir_all(&dir);
    }
}
