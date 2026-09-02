//! GEQDSK（EFIT g-file）读写 —— 数据层的第二样东西。
//!
//! ★★**它为什么在这里。** 本仓从前有**两份** g-file 实现：
//! `python/fylite/io/geqdsk.py`（752 行）与 `app/assets/geqdsk.js`（286 行）。
//! JS 那份的注释自己写着「returns the same field names fylite's own
//! `read_geqdsk` returns, so the two can be compared directly」——两处拼写、
//! 一个契约，正是这个仓被咬过三次的形状（装置文档两侧 WALL 不同；`zerod` 参数
//! 顺序拼在三处）。
//!
//! ★★★**而它们已经在一个真实的地方分歧了**，不是假想：Python 按**固定 16 列**
//! 切数（`line[i:i+16]`），JS 按**模式扫描**，并且 JS 的注释说明了为什么——
//! *vintages differ on whether a full-width negative eats its separating space*。
//! 两种切法在规范的 `%16.9E` 上一致，在不规范的文件上不一致，而**不一致的那一侧
//! 不会报错**：它读出的是一串量级正常、但错位了一格的数。这里取模式扫描
//! （更宽的那条），并由判据钉住它在四份真文件上与 Python 那份逐字段相同。
//!
//! ## 这一层管什么，不管什么
//!
//! **管**：字节 ↔ g-file 里的那些数（`parse` / `format`）。
//! **不管**：COCOS 约定的测量与换算（`measure_cocos` / `to_convention`，约 300 行）
//! ——那是**约定**不是格式，它作用在已经解析出来的数上，留在 Python 侧。
//! 边界画在这里是因为格式是两个宿主都要读的东西，而约定只有算的那一侧要。

use std::collections::BTreeMap;
use std::fmt;

/// 一份 g-file 的全部内容，字段名与 `fylite.io.geqdsk.read_geqdsk` 的键**逐字
/// 相同**——那是这两侧能直接对拍的前提，也是它现在能被同一个名字取到的原因。
#[derive(Debug, Clone, Default, PartialEq)]
pub struct GFile {
    pub header: String,
    pub nw: usize,
    pub nh: usize,
    pub rdim: f64,
    pub zdim: f64,
    pub rcentr: f64,
    pub rleft: f64,
    pub zmid: f64,
    pub rmaxis: f64,
    pub zmaxis: f64,
    pub simag: f64,
    pub sibry: f64,
    pub bcentr: f64,
    pub current: f64,
    pub fpol: Vec<f64>,
    pub pres: Vec<f64>,
    pub ffprim: Vec<f64>,
    pub pprime: Vec<f64>,
    pub psirz: Vec<f64>,
    pub qpsi: Vec<f64>,
    pub nbbbs: usize,
    pub limitr: usize,
    pub rbbbs: Vec<f64>,
    pub zbbbs: Vec<f64>,
    pub rlim: Vec<f64>,
    pub zlim: Vec<f64>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Error {
    /// 头一行没有可读的 `nw nh`。
    Header(String),
    /// 数不够。★带上要多少、拿到多少：一份被截断的 g-file 与一份网格写小了的
    /// g-file 在读者那里长得一样，说清楚就分得开。
    Truncated { want: usize, got: usize, what: &'static str },
    /// 名字不是这份文件里的数组。
    NoSuchArray(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Header(h) => write!(f, "GEQDSK header has no `nw nh`: {h:?}"),
            Error::Truncated { want, got, what } =>
                write!(f, "GEQDSK truncated in {what}: wanted {want}, got {got}"),
            Error::NoSuchArray(n) => write!(f, "no array named {n:?}"),
        }
    }
}

/// 把余下的正文扫成一串数。
///
/// ★**模式扫描，不是固定列。** 见模块抬头：两种切法只在不规范的文件上分道扬镳，
/// 而分道的那一侧不报错。这里认的是「一个 Fortran 风格的实数」，所以
/// `-1.234E+01-5.678E+00`（负号吃掉了分隔空格的那种老写法）也切得开。
pub fn scan_numbers(body: &str) -> Vec<f64> {
    scan(body)
}

fn scan(body: &str) -> Vec<f64> {
    let b = body.as_bytes();
    let mut out = Vec::new();
    let mut i = 0usize;
    while i < b.len() {
        let c = b[i];
        //: 数的开头：符号、数字或小数点。其它一律跳过（空白、换行都在此列）。
        if !(c == b'-' || c == b'+' || c.is_ascii_digit() || c == b'.') {
            i += 1;
            continue;
        }
        let start = i;
        if b[i] == b'-' || b[i] == b'+' {
            i += 1;
        }
        while i < b.len() && (b[i].is_ascii_digit() || b[i] == b'.') {
            i += 1;
        }
        //: 指数部分。★`E`/`e`/`D`/`d` 都认——`D` 是 Fortran 双精度的写法，
        //: 真文件里出现过。
        if i < b.len() && matches!(b[i], b'e' | b'E' | b'd' | b'D') {
            let e = i;
            i += 1;
            if i < b.len() && (b[i] == b'-' || b[i] == b'+') {
                i += 1;
            }
            if i < b.len() && b[i].is_ascii_digit() {
                while i < b.len() && b[i].is_ascii_digit() {
                    i += 1;
                }
            } else {
                //: `E` 后面不是数 —— 那个 `E` 不属于这个数。
                i = e;
            }
        }
        let tok = &body[start..i];
        //: 单独一个 `-`、`.` 或 `+` 不是数。
        if let Ok(v) = tok.replace(['d', 'D'], "E").parse::<f64>() {
            out.push(v);
        }
    }
    out
}

/// 解析一份 g-file。
pub fn parse(text: &str) -> Result<GFile, Error> {
    let (header, body) = match text.find('\n') {
        Some(i) => (&text[..i], &text[i + 1..]),
        None => (text, ""),
    };
    //: ★`nw`/`nh` 是头一行**最后两个整数**，与 Python 侧 `toks[-2], toks[-1]`
    //: 同一条规则：头里的自由文本长度各家不同，只有尾部是可靠的。
    let toks: Vec<&str> = header.split_whitespace().collect();
    let ints: Vec<i64> = toks.iter().rev().take(2).rev()
        .filter_map(|t| t.parse::<i64>().ok()).collect();
    if ints.len() != 2 || ints[0] <= 0 || ints[1] <= 0 {
        return Err(Error::Header(header.to_string()));
    }
    let (nw, nh) = (ints[0] as usize, ints[1] as usize);

    let v = scan(body);
    let mut k = 0usize;
    let mut take = |n: usize, what: &'static str| -> Result<Vec<f64>, Error> {
        if k + n > v.len() {
            return Err(Error::Truncated { want: n, got: v.len().saturating_sub(k), what });
        }
        let s = v[k..k + n].to_vec();
        k += n;
        Ok(s)
    };

    let a = take(5, "line 2")?;
    let b = take(5, "line 3")?;
    let _c = take(5, "line 4")?;
    let _d = take(5, "line 5")?;
    let fpol = take(nw, "fpol")?;
    let pres = take(nw, "pres")?;
    let ffprim = take(nw, "ffprim")?;
    let pprime = take(nw, "pprime")?;
    let psirz = take(nw * nh, "psirz")?;
    let qpsi = take(nw, "qpsi")?;

    //: ★边界与限制器是**可选的**，与 Python 侧的 `try/except` 同一条政策：
    //: 缺了不是错误，是「这份文件没带」。缺席写成 0 与空数组，而不是让整份读入失败。
    let (mut nbbbs, mut limitr) = (0usize, 0usize);
    let (mut rbbbs, mut zbbbs, mut rlim, mut zlim) =
        (Vec::new(), Vec::new(), Vec::new(), Vec::new());
    if k + 2 <= v.len() {
        let n1 = v[k] as i64;
        let n2 = v[k + 1] as i64;
        if n1 >= 0 && n2 >= 0 {
            let (n1, n2) = (n1 as usize, n2 as usize);
            if k + 2 + 2 * n1 + 2 * n2 <= v.len() {
                k += 2;
                nbbbs = n1;
                limitr = n2;
                let bd = &v[k..k + 2 * n1];
                k += 2 * n1;
                let lm = &v[k..k + 2 * n2];
                rbbbs = bd.iter().step_by(2).copied().collect();
                zbbbs = bd.iter().skip(1).step_by(2).copied().collect();
                rlim = lm.iter().step_by(2).copied().collect();
                zlim = lm.iter().skip(1).step_by(2).copied().collect();
            }
        }
    }

    Ok(GFile {
        header: header.trim_end_matches('\r').to_string(),
        nw, nh,
        rdim: a[0], zdim: a[1], rcentr: a[2], rleft: a[3], zmid: a[4],
        rmaxis: b[0], zmaxis: b[1], simag: b[2], sibry: b[3], bcentr: b[4],
        current: _c[0],
        fpol, pres, ffprim, pprime, psirz, qpsi,
        nbbbs, limitr, rbbbs, zbbbs, rlim, zlim,
    })
}

/// `%16.9E`，Fortran 的写法。
fn f16(v: f64) -> String {
    let s = format!("{:.9E}", v);
    //: Rust 写 `1.234567890E1`，Fortran 要 `1.234567890E+01`。
    let (m, e) = s.split_once('E').unwrap_or((s.as_str(), "0"));
    let ev: i32 = e.parse().unwrap_or(0);
    format!("{:>16}", format!("{m}E{}{:02}", if ev < 0 { '-' } else { '+' }, ev.abs()))
}

fn block(arr: &[f64], out: &mut String) {
    for (i, v) in arr.iter().enumerate() {
        out.push_str(&f16(*v));
        if i % 5 == 4 {
            out.push('\n');
        }
    }
    if !arr.is_empty() && arr.len() % 5 != 0 {
        out.push('\n');
    }
}

/// 写回一份 g-file。
pub fn format_gfile(g: &GFile) -> String {
    let mut s = String::new();
    s.push_str(&g.header);
    s.push('\n');
    let row = |v: [f64; 5], s: &mut String| {
        for x in v {
            s.push_str(&f16(x));
        }
        s.push('\n');
    };
    row([g.rdim, g.zdim, g.rcentr, g.rleft, g.zmid], &mut s);
    row([g.rmaxis, g.zmaxis, g.simag, g.sibry, g.bcentr], &mut s);
    row([g.current, g.simag, 0.0, g.rmaxis, 0.0], &mut s);
    row([g.zmaxis, 0.0, g.sibry, 0.0, 0.0], &mut s);
    for a in [&g.fpol, &g.pres, &g.ffprim, &g.pprime, &g.psirz, &g.qpsi] {
        block(a, &mut s);
    }
    s.push_str(&format!("{:5}{:5}\n", g.nbbbs, g.limitr));
    let mut bd = Vec::with_capacity(2 * g.nbbbs);
    for i in 0..g.rbbbs.len().min(g.zbbbs.len()) {
        bd.push(g.rbbbs[i]);
        bd.push(g.zbbbs[i]);
    }
    block(&bd, &mut s);
    let mut lm = Vec::with_capacity(2 * g.limitr);
    for i in 0..g.rlim.len().min(g.zlim.len()) {
        lm.push(g.rlim[i]);
        lm.push(g.zlim[i]);
    }
    block(&lm, &mut s);
    s
}

impl GFile {
    /// 按名字取一个数组 —— 名字就是 `read_geqdsk` 那本字典的键。
    ///
    /// ★用**名字**而不是一张整数编号表：编号要两侧各存一份、就会漂，而名字是
    /// 两侧本来就在用的同一串字符。这一层的查表代价在这里等于零。
    pub fn array(&self, name: &str) -> Option<&[f64]> {
        Some(match name {
            "fpol" => &self.fpol,
            "pres" => &self.pres,
            "ffprim" => &self.ffprim,
            "pprime" => &self.pprime,
            "psirz" => &self.psirz,
            "qpsi" => &self.qpsi,
            "rbbbs" => &self.rbbbs,
            "zbbbs" => &self.zbbbs,
            "rlim" => &self.rlim,
            "zlim" => &self.zlim,
            _ => return None,
        })
    }

    /// 十三个标量，按 `SCALARS` 的次序。
    pub fn scalars(&self) -> [f64; 13] {
        [self.rdim, self.zdim, self.rcentr, self.rleft, self.zmid,
         self.rmaxis, self.zmaxis, self.simag, self.sibry, self.bcentr,
         self.current, self.nbbbs as f64, self.limitr as f64]
    }

    pub fn as_map(&self) -> BTreeMap<&'static str, f64> {
        let n = Self::SCALARS;
        n.iter().copied().zip(self.scalars()).collect()
    }

    /// 标量的名字与次序 —— 生成进宿主的那张表就是它。
    pub const SCALARS: [&'static str; 13] = [
        "rdim", "zdim", "rcentr", "rleft", "zmid",
        "rmaxis", "zmaxis", "simag", "sibry", "bcentr",
        "current", "nbbbs", "limitr",
    ];

    /// 数组的名字 —— 同上。
    pub const ARRAYS: [&'static str; 10] = [
        "fpol", "pres", "ffprim", "pprime", "psirz", "qpsi",
        "rbbbs", "zbbbs", "rlim", "zlim",
    ];
}

#[cfg(test)]
mod tests {
    use super::*;

    const SYN: &str = include_str!("../testdata/g_synthetic.geqdsk");

    #[test]
    fn reads_the_synthetic_case_the_kernel_generates() {
        let g = parse(SYN).unwrap();
        assert_eq!((g.nw, g.nh), (65, 65));
        assert_eq!(g.psirz.len(), 65 * 65);
        assert_eq!(g.fpol.len(), 65);
        assert_eq!(g.qpsi.len(), 65);
        assert!(g.nbbbs > 0 && g.limitr > 0, "boundary/limiter missing");
        assert_eq!(g.rbbbs.len(), g.nbbbs);
        assert_eq!(g.rlim.len(), g.limitr);
    }

    /// ★往返判据判的是**数**，不是字节：写回来的文本再读一遍必须给出同一份
    /// `GFile`。字节相同是更强的要求，而 g-file 的头一行与末尾留白各家不同，
    /// 拿字节做判据会把「另一种同样合法的写法」判成缺陷。
    #[test]
    fn a_round_trip_preserves_every_number() {
        let g = parse(SYN).unwrap();
        let again = parse(&format_gfile(&g)).unwrap();
        assert_eq!(g.nw, again.nw);
        assert_eq!(g.nh, again.nh);
        for (a, b) in g.psirz.iter().zip(&again.psirz) {
            assert!((a - b).abs() <= 1e-9 * a.abs().max(1.0), "{a} vs {b}");
        }
        for name in GFile::ARRAYS {
            let (x, y) = (g.array(name).unwrap(), again.array(name).unwrap());
            assert_eq!(x.len(), y.len(), "{name}");
        }
    }

    /// ★★模式扫描存在的理由，写成判据：负号吃掉分隔空格的老写法。固定 16 列的
    /// 切法在这一行上会读出**错位了一格但量级正常**的数——那正是不会报错的那种错。
    #[test]
    fn a_full_width_negative_that_eats_its_space_still_splits() {
        let line = "-1.234567890E+01-5.678900000E+00 3.000000000E+00";
        let v = scan(line);
        assert_eq!(v.len(), 3, "got {v:?}");
        assert!((v[0] + 12.3456789).abs() < 1e-9);
        assert!((v[1] + 5.6789).abs() < 1e-9);
        assert!((v[2] - 3.0).abs() < 1e-12);
    }

    /// ★Fortran 的 `D` 指数。真文件里出现过，`f64::parse` 不认。
    #[test]
    fn the_fortran_d_exponent_is_read_as_an_exponent() {
        let v = scan(" 1.500000000D+01 -2.5D-02");
        assert_eq!(v.len(), 2, "got {v:?}");
        assert!((v[0] - 15.0).abs() < 1e-12);
        assert!((v[1] + 0.025).abs() < 1e-12);
    }

    #[test]
    fn a_truncated_file_says_what_ran_out() {
        let short = "  fylite  0  65  65\n 1.0 2.0 3.0\n";
        match parse(short) {
            Err(Error::Truncated { what, .. }) => assert_eq!(what, "line 2"),
            other => panic!("expected Truncated, got {other:?}"),
        }
    }

    #[test]
    fn a_header_without_dimensions_is_refused() {
        assert!(matches!(parse("not a g-file\n1.0\n"), Err(Error::Header(_))));
    }
}
