//! 文件类型的自动识别 —— 看**内容**，扩展名只作备选。
//!
//! ★★为什么看内容：g-file 的名字是 `g063982.04800`（没有扩展名），IMAS 的 HDF5 数据项
//! 是一个**目录**，netCDF-4 文件本身就是 HDF5 文件（同一个魔数），而 `.txt` 里可能是
//! 一份 ITER 的 g-file。扩展名说的是作者的习惯，魔数说的是文件是什么。
//!
//! 判据（按序）：
//!
//! 1. 目录且有 `master.h5` → IMAS HDF5 数据项。
//! 2. 前 8 字节是 HDF5 魔数（或在 512·2ᵏ 处——user block 之后）→ HDF5 家族；根上有
//!    `_NCProperties`（netcdf-c ≥ 4.4 必写）→ netCDF-4，否则 HDF5。
//! 3. `CDF\x01` / `CDF\x02` / `CDF\x05` → 经典 netCDF。
//! 4. 文本：首个非空白是 `{`/`[` → JSON(-LD)；前几行有 `*<数>` 头行 → a-file；
//!    头一行以两个正整数收尾、第二行是五个数 → g-file。

use std::path::Path;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Format {
    Json,
    Geqdsk,
    Afile,
    Hdf5,
    NetCdf,
    /// 目录：`master.h5` + `<ids>.h5`。
    ImasHdf5Dir,
}

impl Format {
    pub fn name(self) -> &'static str {
        match self {
            Format::Json => "json",
            Format::Geqdsk => "geqdsk",
            Format::Afile => "afile",
            Format::Hdf5 => "hdf5",
            Format::NetCdf => "netcdf",
            Format::ImasHdf5Dir => "imas-hdf5",
        }
    }

    pub fn parse(s: &str) -> Option<Format> {
        Some(match s.to_ascii_lowercase().as_str() {
            "json" | "jsonld" | "json-ld" => Format::Json,
            "geqdsk" | "gfile" | "g-file" | "eqdsk" => Format::Geqdsk,
            "afile" | "a-file" | "aeqdsk" => Format::Afile,
            "hdf5" | "h5" => Format::Hdf5,
            "netcdf" | "nc" | "netcdf4" => Format::NetCdf,
            "imas-hdf5" | "imas_hdf5" | "imas" => Format::ImasHdf5Dir,
            _ => return None,
        })
    }

    /// 按扩展名猜（写文件时用：还没有内容可看）。
    pub fn from_extension(path: &Path) -> Option<Format> {
        let name = path.file_name()?.to_string_lossy().to_string();
        let ext = path.extension().map(|e| e.to_string_lossy().to_ascii_lowercase()).unwrap_or_default();
        Some(match ext.as_str() {
            "json" | "jsonld" => Format::Json,
            "h5" | "hdf5" | "hdf" => Format::Hdf5,
            "nc" | "nc4" | "cdf" | "netcdf" => Format::NetCdf,
            "geqdsk" | "eqdsk" | "gfile" => Format::Geqdsk,
            "aeqdsk" | "afile" => Format::Afile,
            _ => {
                if name.starts_with('g') && name[1..].chars().next().map(|c| c.is_ascii_digit()).unwrap_or(false) {
                    Format::Geqdsk
                } else if name.starts_with('a') && name[1..].chars().next().map(|c| c.is_ascii_digit()).unwrap_or(false) {
                    Format::Afile
                } else {
                    return None;
                }
            }
        })
    }
}

const HDF5_MAGIC: &[u8; 8] = b"\x89HDF\r\n\x1a\n";

/// HDF5 魔数在哪个偏移（0 或 user block 之后）。
pub fn hdf5_signature_offset(head: &[u8]) -> Option<usize> {
    let mut off = 0usize;
    while off + 8 <= head.len() {
        if &head[off..off + 8] == HDF5_MAGIC {
            return Some(off);
        }
        off = if off == 0 { 512 } else { off * 2 };
    }
    None
}

/// g-file 的样子：头一行以两个正整数收尾，第二行有五个数。
pub fn looks_like_geqdsk(text: &str) -> bool {
    let mut lines = text.lines();
    let (h, l2) = match (lines.next(), lines.next()) {
        (Some(h), Some(l2)) => (h, l2),
        _ => return false,
    };
    let toks: Vec<&str> = h.split_whitespace().collect();
    if toks.len() < 2 {
        return false;
    }
    let ints = toks[toks.len() - 2..].iter().all(|t| t.parse::<i64>().map(|v| v > 0).unwrap_or(false));
    ints && crate::geqdsk::scan_numbers(l2).len() >= 5
}

/// 看内容识别。`None` = 看不出来。
pub fn detect(path: &Path) -> std::io::Result<Option<Format>> {
    if path.is_dir() {
        return Ok(if path.join("master.h5").is_file() { Some(Format::ImasHdf5Dir) } else { None });
    }
    let mut head = vec![0u8; 8192];
    let n = {
        use std::io::Read;
        let mut f = std::fs::File::open(path)?;
        let mut got = 0usize;
        while got < head.len() {
            let k = f.read(&mut head[got..])?;
            if k == 0 { break; }
            got += k;
        }
        got
    };
    let head = &head[..n];
    if hdf5_signature_offset(head).is_some() {
        return Ok(Some(if is_netcdf4(path) { Format::NetCdf } else { Format::Hdf5 }));
    }
    if head.len() >= 4 && &head[..3] == b"CDF" && matches!(head[3], 1 | 2 | 5) {
        return Ok(Some(Format::NetCdf));
    }
    let text = String::from_utf8_lossy(head);
    let first = text.trim_start().chars().next();
    if matches!(first, Some('{') | Some('[')) {
        return Ok(Some(Format::Json));
    }
    if crate::afile::looks_like(&text) {
        return Ok(Some(Format::Afile));
    }
    if looks_like_geqdsk(&text) {
        return Ok(Some(Format::Geqdsk));
    }
    Ok(None)
}

#[cfg(feature = "hdf5")]
fn is_netcdf4(path: &Path) -> bool {
    match hdf5::File::open(path) {
        Ok(f) => f.attr("_NCProperties").is_ok() || f.attr("_nc3_strict").is_ok(),
        Err(_) => false,
    }
}

#[cfg(not(feature = "hdf5"))]
fn is_netcdf4(path: &Path) -> bool {
    matches!(Format::from_extension(path), Some(Format::NetCdf))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn text_formats_are_told_apart_by_content() {
        assert!(looks_like_geqdsk(include_str!("../testdata/g_synthetic.geqdsk")));
        assert!(!looks_like_geqdsk("{\"a\": 1}\n"));
        assert!(crate::afile::looks_like(" x\n 1 2\n*4800.000 1 0 SNT 1 1 CLC\n"));
        assert_eq!(hdf5_signature_offset(b"\x89HDF\r\n\x1a\nxxxx"), Some(0));
        let mut ub = vec![0u8; 1024];
        ub.extend_from_slice(b"\x89HDF\r\n\x1a\n");
        assert_eq!(hdf5_signature_offset(&ub), Some(1024));
        assert_eq!(Format::from_extension(Path::new("/x/g063982.04800")), Some(Format::Geqdsk));
        assert_eq!(Format::from_extension(Path::new("/x/a063982.04800")), Some(Format::Afile));
        assert_eq!(Format::from_extension(Path::new("eq.jsonld")), Some(Format::Json));
        assert_eq!(Format::from_extension(Path::new("eq.nc")), Some(Format::NetCdf));
        assert_eq!(Format::from_extension(Path::new("README")), None);
    }

    #[test]
    fn detect_reads_the_bytes() {
        let dir = std::env::temp_dir().join(format!("fylite_data_detect_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let g = dir.join("eq.txt");
        std::fs::write(&g, include_str!("../testdata/g_synthetic.geqdsk")).unwrap();
        assert_eq!(detect(&g).unwrap(), Some(Format::Geqdsk));
        let j = dir.join("doc.dat");
        std::fs::write(&j, "  {\"@type\": \"fyo:equilibrium\"}").unwrap();
        assert_eq!(detect(&j).unwrap(), Some(Format::Json));
        let o = dir.join("other");
        std::fs::write(&o, "hello world\n").unwrap();
        assert_eq!(detect(&o).unwrap(), None);
        let _ = std::fs::remove_dir_all(&dir);
    }
}
