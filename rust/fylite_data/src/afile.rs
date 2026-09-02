//! EFIT a-file（aeqdsk）—— **只读**，读成一组具名标量，再落成 `fyo:equilibrium`。
//!
//! ★字段次序抄自 `python/fylite/io/geqdsk.py::read_afile`，那一份抄自 EFIT 自己的
//! 写出例程（`weqdud6565.f` 的 `write (neqdsk,1040)` 序列），**不是**某个通用的
//! aeqdsk 规范——各家 vintage 不同。规则：标量四个一行；两组 CO2 块由头行的
//! `mco2v`/`mco2r` 定长；磁测量数组由第 21 组之后的 `nsilop magpri nfcoil nesum`
//! 整数行定长。文件到哪算哪：读不到的字段就不出现，不报错。
//!
//! ★★**单位。** a-file 是 EFIT 的 CGS 世界：长度 cm、面积 cm²、体积 cm³、`betat`
//! 是百分数；只有 `cpasma` [A]、`wplasm` [J]、`bcentr` [T]、`simagx`/`sibdry`
//! [V·s/rad] 不是。落到 DD 路径时按下面那张表换算；**原始值一个不少**地留在
//! `fylite:afile/<name>`，好让读者能核。ψ 的约定（每弧度 vs 总通量）这里不动，
//! 与 g-file 同一政策——那是约定不是格式。

use crate::document::{Map, Node};
use crate::fyodoc;

pub const SCALARS_1: [&str; 24] = [
    "tsaisq", "rcencm", "bcentr", "pasmat",
    "cpasma", "rout", "zout", "aout",
    "eout", "doutu", "doutl", "vout",
    "rcurrt", "zcurrt", "qsta", "betat",
    "betap", "ali", "oleft", "oright",
    "otop", "obott", "qpsib", "vertn",
];

pub const SCALARS_2: [&str; 44] = [
    "shearb", "bpolav", "s1", "s2",
    "s3", "qout", "olefs", "orighs",
    "otops", "sibdry", "areao", "wplasm",
    "terror", "elongm", "qqmagx", "cdflux",
    "alpha", "rttt", "psiref", "xndnt",
    "rseps1", "zseps1", "rseps2", "zseps2",
    "sepexp", "obots", "btaxp", "btaxv",
    "aaq1", "aaq2", "aaq3", "seplim",
    "rmagx", "zmagx", "simagx", "taumhd",
    "betapd", "betatd", "wplasmd", "fluxx",
    "vloopt", "taudia", "qmerci", "tavem",
];

pub const SCALARS_3: [&str; 24] = [
    "pbinj", "rvsin", "zvsin", "rvsout",
    "zvsout", "vsurfa", "wpdot", "wbdot",
    "slantu", "slantl", "zuperts", "chipre",
    "cjor95", "pp95", "ssep", "yyy2",
    "xnnc", "cprof", "oring", "cjor0",
    "fexpan", "qqmin", "chigamt", "ssi01",
];

/// 一份读完的 a-file。
#[derive(Debug, Clone, Default, PartialEq)]
pub struct AFile {
    /// 头一行（日期与 EFIT 版本）。
    pub header: String,
    pub shot: Option<i64>,
    /// 时间 [s]（头行的毫秒 ÷ 1000）。
    pub time: Option<f64>,
    /// 具名标量，按文件里的次序。
    pub scalars: Vec<(String, f64)>,
    /// 拟合模型算出的磁通环、探针、F 线圈电流（只在文件够长时有）。
    pub csilop: Vec<f64>,
    pub cmpr2: Vec<f64>,
    pub ccbrsp: Vec<f64>,
}

impl AFile {
    pub fn get(&self, name: &str) -> Option<f64> {
        self.scalars.iter().find(|(k, _)| k == name).map(|(_, v)| *v)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum Error {
    /// 没有以 `*` 开头的头行。
    Header,
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "a-file has no `*time …` header line")
    }
}

impl std::error::Error for Error {}

/// 文本是不是一份 a-file：前几行里有一行以 `*` 开头且后面跟着数。
pub fn looks_like(text: &str) -> bool {
    text.lines().take(6).any(|l| {
        let t = l.trim_start();
        t.starts_with('*') && t[1..].split_whitespace().next().map(|x| x.parse::<f64>().is_ok()).unwrap_or(false)
    })
}

/// 解析。
pub fn parse(text: &str) -> Result<AFile, Error> {
    let lines: Vec<&str> = text.lines().collect();
    let ih = lines.iter().position(|l| l.trim_start().starts_with('*')).ok_or(Error::Header)?;
    let hdr: Vec<&str> = lines[ih].split_whitespace().collect();
    //: `*4800.000 1 0 SNT 3 1 CLC` — the star is glued to the time
    let time = hdr.first().and_then(|t| t.trim_start_matches('*').trim().parse::<f64>().ok()).map(|ms| ms / 1000.0);
    let (mco2v, mco2r) = (
        hdr.get(4).and_then(|t| t.parse::<usize>().ok()).unwrap_or(0),
        hdr.get(5).and_then(|t| t.parse::<usize>().ok()).unwrap_or(0),
    );
    let shot = if ih > 0 {
        lines[ih - 1].split_whitespace().next().and_then(|t| t.parse::<i64>().ok())
    } else { None };
    let header = lines.first().map(|s| s.trim_end().to_string()).unwrap_or_default();
    let mut toks: Vec<f64> = Vec::new();
    for l in &lines[ih + 1..] {
        toks.extend(crate::geqdsk::scan_numbers(l));
    }
    let mut a = AFile { header, shot, time, ..Default::default() };
    let mut i = 0usize;
    let take = |names: &[&str], a: &mut AFile, i: &mut usize| -> bool {
        for n in names {
            if *i >= toks.len() {
                return false;
            }
            a.scalars.push((n.to_string(), toks[*i]));
            *i += 1;
        }
        true
    };
    if !take(&SCALARS_1, &mut a, &mut i) {
        return Ok(a);
    }
    i += 2 * mco2v + 2 * mco2r;
    if !take(&SCALARS_2, &mut a, &mut i) {
        return Ok(a);
    }
    if i + 4 > toks.len() {
        return Ok(a);
    }
    let (nsil, magp, nfc, nes) = (toks[i] as usize, toks[i + 1] as usize, toks[i + 2] as usize, toks[i + 3] as usize);
    i += 4;
    if i + nsil + magp + nfc <= toks.len() {
        a.csilop = toks[i..i + nsil].to_vec();
        a.cmpr2 = toks[i + nsil..i + nsil + magp].to_vec();
        a.ccbrsp = toks[i + nsil + magp..i + nsil + magp + nfc].to_vec();
    }
    i += nsil + magp + nfc + nes;
    take(&SCALARS_3, &mut a, &mut i);
    Ok(a)
}

const CM: f64 = 0.01;
const CM2: f64 = 1e-4;
const CM3: f64 = 1e-6;

/// a-file 名 → DD 路径（`time_slice/0/` 下）与换算因子。
///
/// ★只列 DD 里有对应量的；没有的留在 `fylite:afile`——X 点（`rseps`/`zseps`）与
/// 打击点在 DD 4.1.1 的 `boundary` 下没有槽（只有 `constraints` 里的测量/重建对），
/// 环电压也没有，所以只在原始块里。
pub const DD_MAP: [(&str, &str, f64); 23] = [
    ("cpasma", "time_slice/0/global_quantities/ip", 1.0),
    ("betap",  "time_slice/0/global_quantities/beta_pol", 1.0),
    ("betat",  "time_slice/0/global_quantities/beta_tor", 0.01),
    ("ali",    "time_slice/0/global_quantities/li_3", 1.0),
    ("wplasm", "time_slice/0/global_quantities/energy_mhd", 1.0),
    ("qpsib",  "time_slice/0/global_quantities/q_95", 1.0),
    ("qqmagx", "time_slice/0/global_quantities/q_axis", 1.0),
    ("qqmin",  "time_slice/0/global_quantities/q_min/value", 1.0),
    ("simagx", "time_slice/0/global_quantities/psi_axis", 1.0),
    ("sibdry", "time_slice/0/global_quantities/psi_boundary", 1.0),
    ("rmagx",  "time_slice/0/global_quantities/magnetic_axis/r", CM),
    ("zmagx",  "time_slice/0/global_quantities/magnetic_axis/z", CM),
    ("vout",   "time_slice/0/global_quantities/volume", CM3),
    ("areao",  "time_slice/0/global_quantities/area", CM2),
    ("rcurrt", "time_slice/0/global_quantities/current_centre/r", CM),
    ("zcurrt", "time_slice/0/global_quantities/current_centre/z", CM),
    ("rout",   "time_slice/0/boundary/geometric_axis/r", CM),
    ("zout",   "time_slice/0/boundary/geometric_axis/z", CM),
    ("aout",   "time_slice/0/boundary/minor_radius", CM),
    ("eout",   "time_slice/0/boundary/elongation", 1.0),
    ("doutu",  "time_slice/0/boundary/triangularity_upper", 1.0),
    ("doutl",  "time_slice/0/boundary/triangularity_lower", 1.0),
    ("bcentr", "vacuum_toroidal_field/b0", 1.0),
];

/// a-file → `fyo:equilibrium` 文档。
pub fn afile_to_document(a: &AFile, source: &str) -> Node {
    let mut doc = fyodoc::new_document("equilibrium", &format!("fylite:equilibrium/{source}"));
    for (name, path, k) in DD_MAP {
        if let Some(v) = a.get(name) {
            doc.set(path, (v * k).into()).unwrap();
        }
    }
    if let Some(r) = a.get("rcencm") {
        doc.set("vacuum_toroidal_field/r0", (r * CM).into()).unwrap();
    }
    if let Some(t) = a.time {
        doc.set("time_slice/0/time", t.into()).unwrap();
    }
    if let Some(s) = a.shot {
        doc.set("fylite:shot", Node::Int(s)).unwrap();
    }
    let mut raw = Map::new();
    raw.insert("header", a.header.clone().into());
    raw.insert("units", "EFIT a-file (CGS: cm, cm^2, cm^3; betat in %; psi in V.s/rad)".into());
    for (k, v) in &a.scalars {
        raw.insert(k.clone(), (*v).into());
    }
    if !a.csilop.is_empty() {
        raw.insert("csilop", a.csilop.clone().into());
        raw.insert("cmpr2", a.cmpr2.clone().into());
        raw.insert("ccbrsp", a.ccbrsp.clone().into());
    }
    doc.set("fylite:afile", Node::Map(raw)).unwrap();
    doc
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 一份最小的合成 a-file：头三行 + 第一组标量 + CO2 块 + 第二组 + 磁测量整数行。
    fn synthetic() -> String {
        let mut s = String::from("  EFITD    12/10/2013  v6565\n 63982   1\n*4800.000      1  0  SNT  1  1 CLC\n");
        let mut vals: Vec<f64> = Vec::new();
        for (i, _) in SCALARS_1.iter().enumerate() {
            vals.push(i as f64 + 0.5);
        }
        vals.extend([1.0, 2.0, 3.0, 4.0]); // rco2v dco2v rco2r dco2r (mco2v = mco2r = 1)
        for (i, _) in SCALARS_2.iter().enumerate() {
            vals.push(100.0 + i as f64);
        }
        vals.extend([2.0, 1.0, 1.0, 0.0]); // nsilop magpri nfcoil nesum
        vals.extend([0.11, 0.22, 0.33, 4.4e4]);
        for (i, _) in SCALARS_3.iter().enumerate() {
            vals.push(200.0 + i as f64);
        }
        for chunk in vals.chunks(4) {
            for v in chunk {
                s.push_str(&format!("{:16.9E}", v));
            }
            s.push('\n');
        }
        s
    }

    #[test]
    fn parses_every_group_and_the_magnetics_arrays() {
        let text = synthetic();
        assert!(looks_like(&text));
        let a = parse(&text).unwrap();
        assert_eq!(a.shot, Some(63982));
        assert_eq!(a.time, Some(4.8));
        assert_eq!(a.get("tsaisq"), Some(0.5));
        assert_eq!(a.get("vertn"), Some(23.5));
        assert_eq!(a.get("shearb"), Some(100.0));
        assert_eq!(a.get("tavem"), Some(143.0));
        assert_eq!(a.csilop, vec![0.11, 0.22]);
        assert_eq!(a.cmpr2, vec![0.33]);
        assert_eq!(a.ccbrsp, vec![4.4e4]);
        assert_eq!(a.get("pbinj"), Some(200.0));
        assert_eq!(a.get("ssi01"), Some(223.0));
        assert_eq!(a.scalars.len(), 24 + 44 + 24);
    }

    #[test]
    fn a_short_file_stops_cleanly() {
        let text: String = synthetic().lines().take(8).collect::<Vec<_>>().join("\n");
        let a = parse(&text).unwrap();
        assert!(a.scalars.len() < 24 + 44 && a.get("tsaisq").is_some());
        assert!(parse("no header\n1 2 3\n").is_err());
    }

    #[test]
    fn the_document_converts_cgs_and_keeps_the_raw_values() {
        let a = parse(&synthetic()).unwrap();
        let d = afile_to_document(&a, "a063982.04800");
        let rmagx = a.get("rmagx").unwrap();
        assert!((d.get("time_slice/0/global_quantities/magnetic_axis/r").and_then(Node::as_f64).unwrap() - rmagx * 0.01).abs() < 1e-12);
        assert_eq!(d.get("time_slice/0/global_quantities/ip").and_then(Node::as_f64), a.get("cpasma"));
        assert!((d.get("time_slice/0/global_quantities/beta_tor").and_then(Node::as_f64).unwrap() - a.get("betat").unwrap() * 0.01).abs() < 1e-12);
        assert_eq!(d.get("fylite:afile/rmagx").and_then(Node::as_f64), Some(rmagx));
        assert_eq!(d.get("time_slice/0/time").and_then(Node::as_f64), Some(4.8));
        assert_eq!(d.get("fylite:shot").and_then(Node::as_i64), Some(63982));
    }

    #[test]
    fn every_dd_path_in_the_map_exists() {
        let meta = crate::ids_meta::IdsMeta::get("equilibrium").unwrap();
        for (_, p, _) in DD_MAP {
            let dd = p.replace("/0/", "/");
            assert!(meta.has(&dd), "{p}");
        }
    }
}
