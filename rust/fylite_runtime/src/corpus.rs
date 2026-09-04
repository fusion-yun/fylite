//! The case corpus —— 场景模板与预设住在哪，以及一份模板说了什么。
//!
//! 与 [`crate::facts`] **同构**（`FYL-DESIGN-17` E-3）：多个根，按优先级，逐条决胜。
//! 差别只有两处，两处都有理由：
//!
//! 1. **模板另有一份内嵌的**。模板与内核的 code 表是一对（`fylite:vocabulary` 对
//!    `CASE_CODES`），一份装到 `$PATH` 上的 `fy` 必须自带一套能跑的模板，否则
//!    「有什么场景」这个问题在没有检出的机器上没有答案。搜索路径上的同名模板
//!    **覆盖**内嵌的那份——排障时改一个文件就够，不必重建二进制（E-22）。
//! 2. **预设没有内嵌**。预设是数据，随语料走；`--cases` / `$FY_CASES_PATH` /
//!    检出的 `docs/examples/` / `$FY_CASES_BUNDLED` 四级，与 facts 逐位对应。
//!
//! ★本模块只回答「哪一份文档」与「它说了什么」。合成是 [`crate::case`] 的事，
//! 参数怎么落到计划上是 `cli/run.rs` 的事——一份规矩一处实现（`FYL-DESIGN-16` D-3）。

use crate::document::Node;
use crate::json;
use std::path::{Path, PathBuf};

/// 搜索路径的环境变量（`$PATH` 形，平台分隔符）。
pub const CASES_ENV: &str = "FY_CASES_PATH";

/// 打包时告诉本模块「自带的那份语料在哪」。源码检出里没有。
pub const BUNDLED_ENV: &str = "FY_CASES_BUNDLED";

/// 语料根下模板所在的子目录。
pub const SCENARIO_DIR: &str = "scenario";

/// 场景目录（四条线、缺省场景、以及每个场景可跑与否）的文档名。
pub const INDEX_NAME: &str = "lines";

//: ★内嵌的那一套：**由 `tools/make-scenario-templates.py` 生成的同一批字节**，
//: 编译期读进来。所以「二进制里的模板」与「仓里的模板」不是两份需要同步的东西，
//: 是同一份文件的两个读法——与 `_cli.json` 的 `include_str!` 同一条规矩。
const EMBEDDED: &[(&str, &str)] = &[
    ("breakdown", include_str!("../../../docs/examples/scenario/breakdown.jsonld")),
    ("discharge", include_str!("../../../docs/examples/scenario/discharge.jsonld")),
    ("evolve", include_str!("../../../docs/examples/scenario/evolve.jsonld")),
    ("lines", include_str!("../../../docs/examples/scenario/lines.jsonld")),
    ("pfwave", include_str!("../../../docs/examples/scenario/pfwave.jsonld")),
    ("profile", include_str!("../../../docs/examples/scenario/profile.jsonld")),
    ("reconstruction", include_str!("../../../docs/examples/scenario/reconstruction.jsonld")),
    ("series", include_str!("../../../docs/examples/scenario/series.jsonld")),
    ("transport", include_str!("../../../docs/examples/scenario/transport.jsonld")),
    ("zerod", include_str!("../../../docs/examples/scenario/zerod.jsonld")),
];

// ───────────────────────────── 搜索路径 ─────────────────────────────

fn split_list(raw: &str) -> Vec<PathBuf> {
    let sep = if cfg!(windows) { ';' } else { ':' };
    raw.split(sep).map(str::trim).filter(|s| !s.is_empty()).map(PathBuf::from).collect()
}

thread_local! {
    static OVERRIDE: std::cell::RefCell<Option<Vec<PathBuf>>> =
        const { std::cell::RefCell::new(None) };
}

/// 设定（或 `None` 清除）进程内的覆盖，由 `--cases` 在入口处设一次。
pub fn use_roots(paths: Option<Vec<PathBuf>>) {
    OVERRIDE.with(|o| *o.borrow_mut() = paths);
}

/// 把一批 `--cases` 的取值（每个都可能自带分隔符）摊平成根的列表。
pub fn parse_roots<I: IntoIterator<Item = S>, S: AsRef<str>>(items: I) -> Vec<PathBuf> {
    items.into_iter().flat_map(|s| split_list(s.as_ref())).collect()
}

fn named() -> Vec<PathBuf> {
    if let Some(v) = OVERRIDE.with(|o| o.borrow().clone()) {
        return v;
    }
    std::env::var(CASES_ENV)
        .ok()
        .filter(|s| !s.trim().is_empty())
        .map(|s| split_list(&s))
        .unwrap_or_default()
}

/// 检出自己的 `docs/examples/`：自可执行文件位置上溯，找一个**同时**有
/// `docs/examples/` 与 `python/` 的目录（判据要两样，理由同 `facts::repo_facts`）。
fn repo_cases() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let mut here: &Path = exe.parent()?;
    loop {
        let cand = here.join("docs").join("examples");
        if cand.is_dir() && here.join("python").is_dir() {
            return Some(cand);
        }
        here = here.parent()?;
    }
}

/// 路径上**存在**的每一个根，按优先级，按真实路径去重。
pub fn roots() -> Vec<PathBuf> {
    let mut out = named();
    if let Some(r) = repo_cases() {
        out.push(r);
    }
    if let Ok(b) = std::env::var(BUNDLED_ENV) {
        if !b.trim().is_empty() {
            out.push(PathBuf::from(b));
        }
    }
    let mut seen: Vec<PathBuf> = Vec::new();
    let mut keep = Vec::new();
    for p in out {
        if !p.is_dir() {
            continue;
        }
        let key = p.canonicalize().unwrap_or_else(|_| p.clone());
        if seen.contains(&key) {
            continue;
        }
        seen.push(key);
        keep.push(p);
    }
    keep
}

/// 被指名却不可用的根，逐条说清哪里不对。
pub fn problems() -> Vec<String> {
    let where_ = if OVERRIDE.with(|o| o.borrow().is_some()) {
        "--cases".to_string()
    } else {
        format!("${CASES_ENV}")
    };
    named()
        .into_iter()
        .filter_map(|p| {
            if !p.exists() {
                Some(format!("{where_}: {} 不存在", p.display()))
            } else if !p.is_dir() {
                Some(format!("{where_}: {} 不是目录", p.display()))
            } else {
                None
            }
        })
        .collect()
}

// ───────────────────────────── 文档 ─────────────────────────────

/// 一份文档是从哪来的。★不是装饰：模板可以被路径上的一份盖掉，而「跑的是哪一份」
/// 必须问得出来——记录里也写着它。
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Origin {
    /// 编译进可执行文件的那一份。
    Embedded,
    /// 搜索路径上的一个根供的。
    Root(PathBuf),
}

impl std::fmt::Display for Origin {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Origin::Embedded => f.write_str("(built in)"),
            Origin::Root(p) => write!(f, "{}", p.display()),
        }
    }
}

/// 一份取回来的语料文档。
#[derive(Debug, Clone)]
pub struct Doc {
    pub name: String,
    pub node: Node,
    pub origin: Origin,
    /// 盘上的路径（内嵌的那份没有）。
    pub path: Option<PathBuf>,
}

fn read(path: &Path) -> Option<Node> {
    let text = std::fs::read_to_string(path).ok()?;
    json::parse(&text).ok()
}

/// 一份场景模板（或场景目录）的原始文档：路径上的先，内嵌的兜底。
pub fn document(name: &str) -> Option<Doc> {
    for r in roots() {
        let p = r.join(SCENARIO_DIR).join(format!("{name}.jsonld"));
        if let Some(node) = read(&p) {
            return Some(Doc { name: name.to_string(), node, origin: Origin::Root(r), path: Some(p) });
        }
    }
    EMBEDDED.iter().find(|(n, _)| *n == name).and_then(|(_, text)| {
        json::parse(text).ok().map(|node| Doc {
            name: name.to_string(),
            node,
            origin: Origin::Embedded,
            path: None,
        })
    })
}

/// 每一个模板的名字（内嵌的与路径上的并集，去掉场景目录本身），按名排序。
pub fn template_names() -> Vec<String> {
    let mut out: Vec<String> = EMBEDDED.iter().map(|(n, _)| n.to_string()).collect();
    for r in roots() {
        let Ok(rd) = std::fs::read_dir(r.join(SCENARIO_DIR)) else { continue };
        for e in rd.flatten() {
            let p = e.path();
            if p.extension().and_then(|s| s.to_str()) != Some("jsonld") {
                continue;
            }
            if let Some(stem) = p.file_stem().and_then(|s| s.to_str()) {
                if !out.iter().any(|x| x == stem) {
                    out.push(stem.to_string());
                }
            }
        }
    }
    out.retain(|n| n != INDEX_NAME);
    out.sort();
    out
}

/// 一条预设（语料里除模板之外的每一份 `fyo:ScenarioSpecification`）。
///
/// ★决胜单位是**条目**：第一个有这个名字的根供出它，绝不跨根拼。
pub fn preset(name: &str) -> Option<Doc> {
    presets().into_iter().find(|d| d.name == name)
}

/// 路径上的每一条预设，按名排序，各自来自赢下它的那个根。
pub fn presets() -> Vec<Doc> {
    let mut out: Vec<Doc> = Vec::new();
    for r in roots() {
        let Ok(groups) = std::fs::read_dir(&r) else { continue };
        let mut dirs: Vec<PathBuf> = groups
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.is_dir() && p.file_name().and_then(|s| s.to_str()) != Some(SCENARIO_DIR))
            .collect();
        dirs.sort();
        for d in dirs {
            let Ok(files) = std::fs::read_dir(&d) else { continue };
            let mut paths: Vec<PathBuf> = files
                .flatten()
                .map(|e| e.path())
                .filter(|p| p.extension().and_then(|s| s.to_str()) == Some("jsonld"))
                .collect();
            paths.sort();
            for p in paths {
                let Some(stem) = p.file_stem().and_then(|s| s.to_str()).map(str::to_string) else { continue };
                if out.iter().any(|x| x.name == stem) {
                    continue;
                }
                let Some(node) = read(&p) else { continue };
                //: 只有计划才是预设：`catalogue.jsonld` 与 `context.jsonld` 不是。
                let is_plan = node
                    .as_map()
                    .and_then(|m| m.get("type").or_else(|| m.get("@type")))
                    .and_then(Node::as_str)
                    .map(|t| t.ends_with("ScenarioSpecification") || t.ends_with("ComputationPlan"))
                    .unwrap_or(false);
                if !is_plan {
                    continue;
                }
                out.push(Doc { name: stem, node, origin: Origin::Root(r.clone()), path: Some(p) });
            }
        }
    }
    out.sort_by(|a, b| a.name.cmp(&b.name));
    out
}

// ───────────────────────────── 模板的读法 ─────────────────────────────

/// 一个参数的类型。★`Time` 是唯一不按 JSON 字面量解析的那一个
/// （`3:5` 不是 JSON，而它是一个合法的时间选择，`FYL-DESIGN-14` L-10）。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParamKind {
    Bool,
    Int,
    Float,
    Str,
    Choice,
    Time,
}

impl ParamKind {
    pub fn name(&self) -> &'static str {
        match self {
            ParamKind::Bool => "bool",
            ParamKind::Int => "int",
            ParamKind::Float => "float",
            ParamKind::Str => "str",
            ParamKind::Choice => "choice",
            ParamKind::Time => "time",
        }
    }
}

/// 一个参数的声明。
#[derive(Debug, Clone)]
pub struct ParamDef {
    /// 模板里的拼法（错误话术与计划里用它）。
    pub name: String,
    /// 归一后的键：`-` 与 `_` 是同一个字符（E-12 ③）。
    pub key: String,
    pub kind: ParamKind,
    pub choices: Vec<String>,
    pub min: Option<f64>,
    pub max: Option<f64>,
    /// 取自装置文档的哪条 fyo 路径（有则第 2 层按它取缺省，E-14）。
    pub from_device: Option<String>,
    pub note: String,
}

/// 一个输入端口的声明。
#[derive(Debug, Clone)]
pub struct Port {
    pub name: String,
    /// 装置端口要卡片还是清单（`card` / `manifest`）；其余端口为空。
    pub requires: String,
    pub primary: bool,
    pub optional: bool,
    /// 取数时要哪些 IDS（`measurements` 端口）。
    pub ids: Vec<String>,
    pub note: String,
}

/// 一条开关：一个名字 → 一组基础参数的值（E-18）。
#[derive(Debug, Clone)]
pub struct Switch {
    pub name: String,
    pub key: String,
    pub sets: Vec<(String, Node)>,
}

/// 一份场景模板，读成本层认得的形。
#[derive(Debug, Clone)]
pub struct Template {
    pub name: String,
    pub code: String,
    pub title: String,
    pub lines: Vec<String>,
    pub ports: Vec<Port>,
    pub common: Vec<String>,
    /// `point` / `selection`；空表示模板不限定 `time` 的形。
    pub time: String,
    pub vocab: Vec<ParamDef>,
    pub switches: Vec<Switch>,
    pub origin: Origin,
    pub path: Option<PathBuf>,
    /// 模板文档本身——它就是一份计划，合成时当第一份用。
    pub node: Node,
}

/// `-` 与 `_` 是同一个字符。
pub fn normalize(name: &str) -> String {
    name.replace('-', "_")
}

fn lang(n: Option<&Node>) -> String {
    match n {
        Some(Node::Str(s)) => s.clone(),
        Some(Node::Map(m)) => m
            .get("zh")
            .or_else(|| m.get("en"))
            .and_then(Node::as_str)
            .map(str::to_string)
            .unwrap_or_default(),
        _ => String::new(),
    }
}

fn strings(n: Option<&Node>) -> Vec<String> {
    match n {
        Some(Node::List(l)) => l.iter().filter_map(Node::as_str).map(str::to_string).collect(),
        Some(Node::Array(a)) => a.as_str().map(|s| s.to_vec()).unwrap_or_default(),
        Some(Node::Str(s)) => vec![s.clone()],
        _ => Vec::new(),
    }
}

fn flag(m: &crate::document::Map, key: &str) -> bool {
    matches!(m.get(key), Some(Node::Bool(true)))
}

impl Template {
    /// 按名取一个参数声明（归一后比较）。
    pub fn param(&self, name: &str) -> Option<&ParamDef> {
        let k = normalize(name);
        self.vocab.iter().find(|p| p.key == k)
    }

    /// 按名取一条开关。
    pub fn switch(&self, name: &str) -> Option<&Switch> {
        let k = normalize(name);
        self.switches.iter().find(|s| s.key == k)
    }

    /// 这个通用参数这条场景收不收（`fylite:common`）。
    pub fn takes_common(&self, name: &str) -> bool {
        let k = normalize(name);
        self.common.iter().any(|c| normalize(c) == k)
    }

    /// 主输入端口（`--input` 绑的那个）。
    pub fn primary_port(&self) -> Option<&Port> {
        self.ports.iter().find(|p| p.primary)
    }

    pub fn port(&self, name: &str) -> Option<&Port> {
        self.ports.iter().find(|p| p.name == name)
    }

    /// 这条场景认得的每一个名字：参数、开关、以及它收的通用参数。
    /// 用于「按名拒绝并列最接近的三个」。
    pub fn known_names(&self) -> Vec<String> {
        let mut out: Vec<String> = self.vocab.iter().map(|p| p.name.clone()).collect();
        out.extend(self.switches.iter().map(|s| s.name.clone()));
        out.extend(self.common.iter().cloned());
        out.sort();
        out.dedup();
        out
    }
}

/// 读一份场景模板。
pub fn template(name: &str) -> Option<Template> {
    let doc = document(name)?;
    let m = doc.node.as_map()?;
    let code = m
        .get("prescribes_code")
        .and_then(Node::as_map)
        .and_then(|c| c.get("id"))
        .and_then(Node::as_str)
        .unwrap_or("")
        .to_string();
    let ports = m
        .get("fylite:ports")
        .and_then(Node::as_map)
        .map(|pm| {
            pm.iter()
                .map(|(k, v)| {
                    let vm = v.as_map();
                    Port {
                        name: k.to_string(),
                        requires: vm
                            .and_then(|x| x.get("requires"))
                            .and_then(Node::as_str)
                            .unwrap_or("")
                            .to_string(),
                        primary: vm.map(|x| flag(x, "primary")).unwrap_or(false),
                        optional: vm.map(|x| flag(x, "optional")).unwrap_or(false),
                        ids: vm.map(|x| strings(x.get("ids"))).unwrap_or_default(),
                        note: vm.map(|x| lang(x.get("note"))).unwrap_or_default(),
                    }
                })
                .collect()
        })
        .unwrap_or_default();
    let vocab = m
        .get("fylite:vocabulary")
        .and_then(Node::as_map)
        .map(|vm| {
            vm.iter()
                .map(|(k, v)| {
                    let d = v.as_map();
                    let kind = match d.and_then(|x| x.get("type")).and_then(Node::as_str).unwrap_or("str") {
                        "bool" => ParamKind::Bool,
                        "int" => ParamKind::Int,
                        "float" => ParamKind::Float,
                        "choice" => ParamKind::Choice,
                        "time" => ParamKind::Time,
                        _ => ParamKind::Str,
                    };
                    ParamDef {
                        name: k.to_string(),
                        key: normalize(k),
                        kind,
                        choices: d.map(|x| strings(x.get("choices"))).unwrap_or_default(),
                        min: d.and_then(|x| x.get("min")).and_then(Node::as_f64),
                        max: d.and_then(|x| x.get("max")).and_then(Node::as_f64),
                        from_device: d
                            .and_then(|x| x.get("from_device"))
                            .and_then(Node::as_str)
                            .map(str::to_string),
                        note: d.map(|x| lang(x.get("note"))).unwrap_or_default(),
                    }
                })
                .collect()
        })
        .unwrap_or_default();
    let switches = m
        .get("fylite:switches")
        .and_then(Node::as_map)
        .map(|sm| {
            sm.iter()
                .map(|(k, v)| Switch {
                    name: k.to_string(),
                    key: normalize(k),
                    sets: v
                        .as_map()
                        .map(|x| x.iter().map(|(a, b)| (a.to_string(), b.clone())).collect())
                        .unwrap_or_default(),
                })
                .collect()
        })
        .unwrap_or_default();
    Some(Template {
        name: name.to_string(),
        code,
        title: lang(m.get("title")),
        lines: strings(m.get("fylite:lines")),
        ports,
        common: strings(m.get("fylite:common")),
        time: m.get("fylite:time").and_then(Node::as_str).unwrap_or("").to_string(),
        vocab,
        switches,
        origin: doc.origin,
        path: doc.path,
        node: doc.node,
    })
}

// ───────────────────────────── 场景目录 ─────────────────────────────

/// 一条线。
#[derive(Debug, Clone)]
pub struct LineDef {
    pub name: String,
    pub title: String,
    pub default_scenario: String,
    pub conops: String,
}

/// 目录里的一行：一个场景，有没有模板、今天可不可跑、不然为什么。
#[derive(Debug, Clone)]
pub struct ScenarioRow {
    pub name: String,
    pub lines: Vec<String>,
    pub has_template: bool,
    pub code: String,
    pub parameters: usize,
    /// 数据里记的判定（E-8）。活的那个判定由内核的 code 表给，`fy list` 两个都打。
    pub runnable: bool,
    pub folded_into: Option<String>,
    pub reason: String,
}

/// 四条线与全部场景。
#[derive(Debug, Clone, Default)]
pub struct Catalogue {
    pub lines: Vec<LineDef>,
    pub scenarios: Vec<ScenarioRow>,
    pub origin: Option<Origin>,
}

impl Catalogue {
    pub fn line(&self, name: &str) -> Option<&LineDef> {
        self.lines.iter().find(|l| l.name == name)
    }

    pub fn scenario(&self, name: &str) -> Option<&ScenarioRow> {
        self.scenarios.iter().find(|s| s.name == name)
    }

    /// 一条线上的场景，按目录里的次序。
    pub fn of_line(&self, line: &str) -> Vec<&ScenarioRow> {
        self.scenarios.iter().filter(|s| s.lines.iter().any(|l| l == line)).collect()
    }

    pub fn line_names(&self) -> Vec<&str> {
        self.lines.iter().map(|l| l.name.as_str()).collect()
    }
}

/// 读场景目录（`scenario/lines.jsonld`）。
pub fn catalogue() -> Catalogue {
    let Some(doc) = document(INDEX_NAME) else { return Catalogue::default() };
    let Some(m) = doc.node.as_map() else { return Catalogue::default() };
    let lines = m
        .get("fylite:lines")
        .and_then(Node::as_map)
        .map(|lm| {
            lm.iter()
                .map(|(k, v)| {
                    let d = v.as_map();
                    LineDef {
                        name: k.to_string(),
                        title: d.map(|x| lang(x.get("title"))).unwrap_or_default(),
                        default_scenario: d
                            .and_then(|x| x.get("default"))
                            .and_then(Node::as_str)
                            .unwrap_or("")
                            .to_string(),
                        conops: d
                            .and_then(|x| x.get("conops"))
                            .and_then(Node::as_str)
                            .unwrap_or("")
                            .to_string(),
                    }
                })
                .collect()
        })
        .unwrap_or_default();
    let scenarios = m
        .get("fylite:scenarios")
        .and_then(Node::as_list)
        .map(|rows| {
            rows.iter()
                .filter_map(Node::as_map)
                .map(|r| ScenarioRow {
                    name: r.get("name").and_then(Node::as_str).unwrap_or("").to_string(),
                    lines: strings(r.get("lines")),
                    has_template: flag(r, "template"),
                    code: r.get("code").and_then(Node::as_str).unwrap_or("").to_string(),
                    parameters: r.get("parameters").and_then(Node::as_i64).unwrap_or(0) as usize,
                    runnable: flag(r, "runnable"),
                    folded_into: r.get("folded_into").and_then(Node::as_str).map(str::to_string),
                    reason: lang(r.get("reason")),
                })
                .collect()
        })
        .unwrap_or_default();
    Catalogue { lines, scenarios, origin: Some(doc.origin) }
}

// ───────────────────────────── 「你是不是要打这个」 ─────────────────────────────

fn distance(a: &str, b: &str) -> usize {
    let (a, b): (Vec<char>, Vec<char>) = (a.chars().collect(), b.chars().collect());
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    let mut cur = vec![0usize; b.len() + 1];
    for i in 1..=a.len() {
        cur[0] = i;
        for j in 1..=b.len() {
            let cost = usize::from(a[i - 1] != b[j - 1]);
            cur[j] = (prev[j] + 1).min(cur[j - 1] + 1).min(prev[j - 1] + cost);
        }
        std::mem::swap(&mut prev, &mut cur);
    }
    prev[b.len()]
}

/// 最接近 `want` 的 `k` 个名字——按名拒绝时跟在后面的那一句。
///
/// ★门槛：编辑距离不超过名字长度的一半（至少 3）。没有近名时**不给建议**，
/// 因为一句凑数的「你是不是要…」比没有建议更费时间。
pub fn nearest<S: AsRef<str>>(want: &str, pool: &[S], k: usize) -> Vec<String> {
    let want_n = normalize(want);
    let limit = (want_n.len() / 2).max(3);
    let mut scored: Vec<(usize, String)> = pool
        .iter()
        .map(|c| (distance(&want_n, &normalize(c.as_ref())), c.as_ref().to_string()))
        .filter(|(d, _)| *d <= limit)
        .collect();
    scored.sort_by(|a, b| a.0.cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
    scored.dedup_by(|a, b| a.1 == b.1);
    scored.into_iter().take(k).map(|(_, n)| n).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_embedded_template_parses_and_declares_its_code() {
        for (name, _) in EMBEDDED {
            if *name == INDEX_NAME {
                continue;
            }
            let t = template(name).unwrap_or_else(|| panic!("{name} did not load"));
            assert_eq!(t.code, format!("code/{name}"), "{name}");
            assert!(!t.vocab.is_empty(), "{name} declares no parameters");
            assert!(!t.lines.is_empty(), "{name} serves no line");
            //: 归一后不得有两个名字撞在一起（E-12 ③）
            let mut keys: Vec<&str> = t.vocab.iter().map(|p| p.key.as_str()).collect();
            keys.sort();
            let n = keys.len();
            keys.dedup();
            assert_eq!(keys.len(), n, "{name}: two parameters differ only by - / _");
        }
    }

    #[test]
    fn the_catalogue_lists_a_default_scenario_for_every_line() {
        let c = catalogue();
        assert_eq!(c.line_names(), ["analysis", "model", "design", "control"]);
        for l in &c.lines {
            assert!(!l.default_scenario.is_empty(), "{} has no default", l.name);
            let row = c.scenario(&l.default_scenario).expect("the default is in the catalogue");
            assert!(row.has_template, "{}'s default has no template", l.name);
        }
        //: 每个不设模板的场景都要在数据里给出理由（E-8）
        for s in &c.scenarios {
            if !s.has_template {
                assert!(!s.reason.is_empty(), "{} has no template and no reason", s.name);
            }
        }
    }

    #[test]
    fn a_switch_expands_to_booleans_the_vocabulary_knows() {
        let t = template("reconstruction").unwrap();
        let sw = t.switch("only-magnetic").expect("- and _ are the same character");
        assert_eq!(sw.sets.len(), 6);
        for (k, v) in &sw.sets {
            let p = t.param(k).unwrap_or_else(|| panic!("{k} is not in the vocabulary"));
            assert_eq!(p.kind, ParamKind::Bool, "{k}");
            assert!(matches!(v, Node::Bool(_)), "{k} expands to a non-boolean");
        }
    }

    #[test]
    fn nearest_suggests_only_when_it_is_close() {
        let pool = ["pointfit", "probefit", "vesselfit", "maxit"];
        assert_eq!(nearest("pointfi", &pool, 3), ["pointfit"]);
        assert!(nearest("chi0", &pool, 3).is_empty());
        //: 归一后比较：写 `mc-basis` 与 `mc_basis` 找到同一个
        assert_eq!(nearest("mc_basis", &["mc-basis"], 3), ["mc-basis"]);
    }
}
