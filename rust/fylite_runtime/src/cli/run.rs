//! `run` —— 一次日常建模或分析：一条线（或几份计划）进，一份记录出。
//!
//! ```text
//! fy run analysis --device east shot=123456 time=4.4 --only-magnetic=true
//! fy run model transport chi0=0.4 --preset transport-iter-15ma -o rec/
//! fy run plan.jsonld other.jsonld --bind measurements=meas.json -o rec/
//! ```
//!
//! 本模块是 `case` 那条门**之上的解析层**（`FYL-DESIGN-17`）：把线变成模板、把装置名
//! 变成文档、把炮号变成文档、把开关变成参数，然后交给 [`crate::case`] 合成与运行。
//! ★★合成器只有一份：这里**不出现**第二处「后者覆盖前者」（E-21 / `FYL-DESIGN-16` D-3）。
//!
//! 两种位置参数形，一条路（E-2 / E-10）：
//!
//! * **场景形** `run <线> [<场景>]` —— 线选出缺省场景，场景选出模板；
//! * **计划文件形** `run <plan.jsonld>...` —— 就是从前的 `case run`，模板由合成后计划的
//!   `prescribes_code` 末段反查，于是 `key=value` 在两种形上**同样受模板校验**。查不到
//!   模板时开放参数不校验直接透传（等于从前的 `--set`），`--dry-run` 标 `cli (unchecked)`。
//!
//! 六层合成，逐值记来源（E-13）：模板缺省 → 装置 → 预设 → `--plan` → 命令行
//! （开关低于显式参数）→ 端口绑定。每个值带 `fylite:from`，写进 `plan.jsonld`。
//!
//! 拒绝分四个阶段（E-20）：`compose` · `device` · `measurements` · `kernel`。语法错退 2
//! 且**不落记录**；合成之后的任何拒绝退 1 且**落一份记录**——一份跑不了的计划必须说出
//! 它缺什么，而说在哪一步缺的，比只说「缺」有用。

use super::{Args, OpenArg};
use crate::case::{self, Plan, Produced, RecordInputs, Source};
use crate::corpus::{self, ParamDef, ParamKind, Template};
use crate::document::Node;
use crate::facts;
use crate::json;
use crate::kernel::{Kernel, KernelError};
use std::path::{Path, PathBuf};

/// 一次拒绝：哪一步，以及缺什么。
struct Refusal {
    stage: &'static str,
    message: String,
}

fn refuse(stage: &'static str, message: impl Into<String>) -> Refusal {
    Refusal { stage, message: message.into() }
}

/// 语法层的拒绝：退 2，不落记录（E-20）。
fn die(msg: &str) -> ! {
    eprintln!("fy run: {msg}");
    std::process::exit(2);
}

extern "C" {
    fn signal(sig: i32, handler: usize) -> usize;
}

// ───────────────────────────── 来源账 ─────────────────────────────

/// 逐值的来源，`fylite:from` 就是它。
#[derive(Default)]
struct Prov(Vec<(String, String)>);

impl Prov {
    fn set(&mut self, name: &str, from: impl Into<String>) {
        let from = from.into();
        match self.0.iter_mut().find(|(k, _)| k == name) {
            Some(slot) => slot.1 = from,
            None => self.0.push((name.to_string(), from)),
        }
    }

    fn get(&self, name: &str) -> Option<&str> {
        self.0.iter().find(|(k, _)| k == name).map(|(_, v)| v.as_str())
    }
}

/// 把来源写进计划文档的每一条参数设定。
fn stamp(node: &mut Node, prov: &Prov) {
    let Some(m) = node.as_map_mut() else { return };
    let Some(Node::List(ps)) = m.get_mut("parameters") else { return };
    for p in ps {
        let Some(pm) = p.as_map_mut() else { continue };
        let name = pm
            .get("sets_parameter")
            .and_then(Node::as_str)
            .and_then(|i| i.split('#').nth(1))
            .map(str::to_string);
        if let Some(f) = name.as_deref().and_then(|n| prov.get(n)) {
            let f = f.to_string();
            pm.insert("fylite:from", f.into());
        }
    }
}

// ───────────────────────────── 目标 ─────────────────────────────

enum Target {
    /// 场景形：线 + 模板。
    Scenario { line: String, template: Template },
    /// 计划文件形：按序合成的那几份，以及反查到的模板（可能没有）。
    Plans { paths: Vec<PathBuf>, template: Option<Template> },
}

impl Target {
    fn template(&self) -> Option<&Template> {
        match self {
            Target::Scenario { template, .. } => Some(template),
            Target::Plans { template, .. } => template.as_ref(),
        }
    }

    /// 记录目录的名字里用哪个词。
    fn tag(&self) -> String {
        match self {
            Target::Scenario { template, .. } => template.name.clone(),
            Target::Plans { template: Some(t), .. } => t.name.clone(),
            Target::Plans { paths, .. } => paths
                .first()
                .and_then(|p| p.file_stem())
                .and_then(|s| s.to_str())
                .unwrap_or("case")
                .to_string(),
        }
    }
}

/// 含 `/` 或以 `.json` / `.jsonld` / `.yaml` 结尾的当路径，否则当名字（E-2）。
fn looks_like_path(spec: &str) -> bool {
    spec.contains('/')
        || spec.contains(std::path::MAIN_SEPARATOR)
        || matches!(
            Path::new(spec).extension().and_then(|s| s.to_str()),
            Some("json") | Some("jsonld") | Some("yaml") | Some("yml")
        )
}

fn resolve_target(args: &Args) -> Target {
    let targets: Vec<&str> = args.all("target");
    let cat = corpus::catalogue();
    let first = targets.first().copied().unwrap_or_default();

    //: 第一个位置参数是四个线词之一 → 场景形；否则按 E-2 判路径。
    if let Some(line) = cat.line(first) {
        let scenario = match targets.len() {
            1 => line.default_scenario.clone(),
            2 => targets[1].to_string(),
            _ => die(&format!(
                "the scenario form takes a line and at most one scenario; got {:?}.\n  \
                 ★a parameter is written `key=value` (or `--key=value`) — `--key value`, with a \
                 space, leaves the value here as a second scenario",
                targets
            )),
        };
        let Some(template) = corpus::template(&scenario) else {
            let known = cat.of_line(&line.name);
            let names: Vec<String> = known.iter().map(|s| s.name.clone()).collect();
            let near = corpus::nearest(&scenario, &names, 3);
            let hint = if near.is_empty() {
                String::new()
            } else {
                format!("; did you mean {}?", near.join(", "))
            };
            //: ★目录知道这个名字、但它没有模板时，理由已经写在数据里（E-8）——
            //: 说出那句理由，而不是说「没有这个场景」。
            if let Some(row) = cat.scenario(&scenario) {
                die(&format!(
                    "`{scenario}` has no template: {}{}",
                    row.reason,
                    row.folded_into
                        .as_ref()
                        .map(|f| format!("  (it is part of `{f}`)"))
                        .unwrap_or_default()
                ));
            }
            die(&format!(
                "unknown scenario `{scenario}` on the {} line{hint}\n  \
                 `fy list scenarios --line {}` lists them",
                line.name, line.name
            ));
        };
        return Target::Scenario { line: line.name.clone(), template };
    }

    if targets.is_empty() {
        die("give a line (analysis / model / design / control) or a plan document; \
             `fy list lines` lists the lines");
    }
    if !looks_like_path(first) {
        let mut names: Vec<String> = cat.line_names().iter().map(|s| s.to_string()).collect();
        names.extend(corpus::template_names());
        let near = corpus::nearest(first, &names, 3);
        let hint = if near.is_empty() {
            String::new()
        } else {
            format!("; did you mean {}?", near.join(", "))
        };
        die(&format!(
            "`{first}` is neither a line nor a plan document{hint}\n  \
             a plan is a path, or a name ending .json / .jsonld / .yaml (FYL-DESIGN-17 E-2)"
        ));
    }
    let paths: Vec<PathBuf> = targets.iter().map(PathBuf::from).collect();
    for p in &paths {
        if !p.is_file() {
            die(&format!("{}: no such plan document", p.display()));
        }
    }
    Target::Plans { paths, template: None }
}

// ───────────────────────────── 第二段解析 ─────────────────────────────

/// 一个字面量按声明的类型落成一个值。
fn coerce(p: &ParamDef, raw: &str) -> Result<Node, String> {
    let bad = |want: &str| Err(format!("`{}` wants {want}, not {raw:?}", p.name));
    let node = match p.kind {
        ParamKind::Bool => match raw {
            "true" | "1" | "yes" | "on" => Node::Bool(true),
            "false" | "0" | "no" | "off" => Node::Bool(false),
            _ => return bad("true or false"),
        },
        ParamKind::Int => match raw.parse::<i64>() {
            Ok(v) => Node::Int(v),
            Err(_) => return bad("an integer"),
        },
        ParamKind::Float => match raw.parse::<f64>() {
            Ok(v) => Node::Float(v),
            Err(_) => return bad("a number"),
        },
        ParamKind::Choice => {
            if !p.choices.iter().any(|c| c == raw) {
                return Err(format!("`{}` takes one of {}, not {raw:?}", p.name, p.choices.join(" | ")));
            }
            Node::Str(raw.to_string())
        }
        ParamKind::Time => {
            //: 时间选择不按 JSON 解析（`3:5` 不是 JSON），按 L-10 的三种形校验。
            crate::mdsbind::TimeSel::parse(raw).map_err(|e| format!("`{}`: {e}", p.name))?;
            Node::Str(raw.to_string())
        }
        ParamKind::Str => Node::Str(raw.to_string()),
    };
    if let Some(v) = node.as_f64() {
        if let Some(lo) = p.min {
            if v < lo {
                return Err(format!("`{}` is at least {lo}, got {v}", p.name));
            }
        }
        if let Some(hi) = p.max {
            if v > hi {
                return Err(format!("`{}` is at most {hi}, got {v}", p.name));
            }
        }
    }
    Ok(node)
}

/// 没有模板时的落法：与从前的 `--set` 逐字一致（JSON 字面量，否则字符串）。
fn unchecked(raw: &str) -> Node {
    json::parse(raw).unwrap_or_else(|_| Node::Str(raw.to_string()))
}

fn set(plan: &mut Plan, prov: &mut Prov, name: &str, value: Node, from: &str) {
    let iri = format!("{}#{name}", plan.code);
    //: ★经 `Plan::set_override` 的同一条路：本模块不自己改 `settings`。
    let literal = json::to_string(&value, false);
    if plan.set_override(&format!("{name}={literal}")).is_err() {
        //: `set_override` 只在没有 `=` 时失败，而这里总有一个
        return;
    }
    let _ = iri;
    prov.set(name, from);
}

/// 命令行上的参数与开关（E-12 / E-18）。
///
/// 两遍：开关先展开，显式参数后落——于是**同一条命令行上显式给的基础参数永远
/// 胜过开关展开的值**，与写的先后无关。
fn apply_open(plan: &mut Plan, prov: &mut Prov, t: Option<&Template>, open: &[OpenArg]) -> Result<(), Refusal> {
    let Some(t) = t else {
        for o in open {
            set(plan, prov, &corpus::normalize(&o.key), unchecked(o.literal()), "cli (unchecked)");
        }
        return Ok(());
    };

    // 先分类，未知的当场按名拒绝（E-11）
    let mut switches: Vec<&OpenArg> = Vec::new();
    let mut params: Vec<(&OpenArg, &ParamDef)> = Vec::new();
    for o in open {
        if t.switch(&o.key).is_some() {
            switches.push(o);
        } else if let Some(p) = t.param(&o.key) {
            params.push((o, p));
        } else if t.takes_common(&o.key) {
            //: 通用参数由固定选项承载（`--shot` / `--time`）或在别处处理；
            //: 走到这里说明模板收它而解析器没有对应的固定选项。
            set(plan, prov, &corpus::normalize(&o.key), unchecked(o.literal()), "cli");
        } else {
            let near = corpus::nearest(&o.key, &t.known_names(), 3);
            let hint = if near.is_empty() {
                format!("`fy list scenarios {}` prints the whole table", t.name)
            } else {
                format!("did you mean {}?", near.join(", "))
            };
            die(&format!(
                "{}: `{}` takes no parameter {:?} — {hint}",
                t.name,
                t.name,
                o.as_written()
            ));
        }
    }

    let explicit: Vec<String> = params.iter().map(|(_, p)| p.key.clone()).collect();
    for o in &switches {
        let sw = t.switch(&o.key).expect("classified as a switch");
        //: `--no-<switch>` / `<switch>=false` 关掉一条开关：不展开任何东西。
        let on = match coerce(
            &ParamDef {
                name: sw.name.clone(),
                key: sw.key.clone(),
                kind: ParamKind::Bool,
                choices: Vec::new(),
                min: None,
                max: None,
                from_device: None,
                note: String::new(),
            },
            o.literal(),
        ) {
            Ok(Node::Bool(b)) => b,
            Ok(_) => true,
            Err(e) => die(&format!("{}: {e}", t.name)),
        };
        if !on {
            continue;
        }
        for (name, value) in &sw.sets {
            let key = corpus::normalize(name);
            if explicit.contains(&key) {
                continue; //: 显式给的胜过展开的（E-18）
            }
            set(plan, prov, &key, value.clone(), &format!("cli:switch {}", sw.name));
        }
    }
    for (o, p) in &params {
        let value = coerce(p, o.literal()).unwrap_or_else(|e| die(&format!("{}: {e}", t.name)));
        set(plan, prov, &p.key, value, "cli");
    }
    Ok(())
}

// ───────────────────────────── 装置 ─────────────────────────────

/// 一条 fyo 路径（`a/b/c` 或 `a.b.c`）在文档里取值。
fn at_path<'a>(node: &'a Node, path: &str) -> Option<&'a Node> {
    let mut cur = node;
    for seg in path.split(['/', '.']).filter(|s| !s.is_empty()) {
        cur = cur.as_map()?.get(seg)?;
    }
    Some(cur)
}

struct DeviceDoc {
    id: String,
    root: String,
    /// 落在记录目录里的那一份（相对记录目录）。
    file: String,
    node: Node,
}

/// 路一：把整份装置文档装出来（K-8），落进记录目录，绑到 `device` 端口。
fn load_device(args: &Args, t: Option<&Template>, spec: &str, out_dir: &Path, dry: bool) -> Result<DeviceDoc, Refusal> {
    let want_manifest = t
        .and_then(|t| t.port("device"))
        .map(|p| p.requires == "manifest")
        .unwrap_or(false);
    let ids: Vec<String> = t
        .and_then(|t| t.port("device"))
        .map(|p| p.ids.clone())
        .unwrap_or_default();

    //: 一份路径直接就是那份文档。
    if looks_like_path(spec) {
        let p = PathBuf::from(spec);
        if !p.is_file() {
            return Err(refuse("device", format!("--device {spec}: no such file")));
        }
        let node = crate::io::read_node(&p)
            .map_err(|e| refuse("device", format!("--device {spec}: {e}")))?;
        let file = if dry { p.display().to_string() } else { copy_into(&p, out_dir, "device")? };
        return Ok(DeviceDoc { id: spec.to_string(), root: p.display().to_string(), file, node });
    }

    let Some(entry) = facts::find("device", spec) else {
        let known: Vec<String> = facts::entries("device").into_iter().map(|e| e.ident).collect();
        let roots: Vec<String> = facts::roots().iter().map(|r| r.display().to_string()).collect();
        let where_ = if roots.is_empty() {
            format!(" — the facts path is empty; set ${} or pass --facts", facts::FACTS_ENV)
        } else {
            format!(" — looked in {}", roots.join(", "))
        };
        let near = corpus::nearest(spec, &known, 3);
        let hint = if near.is_empty() { String::new() } else { format!("; did you mean {}?", near.join(", ")) };
        return Err(refuse("device", format!("--device {spec}: no device by that name{where_}{hint}")));
    };
    let root = entry.root.display().to_string();

    if let Some(manifest) = entry.manifest_path() {
        return device_from_manifest(args, spec, &root, &manifest, &ids, out_dir, dry);
    }
    if want_manifest {
        return Err(refuse(
            "device",
            format!(
                "--device {spec}: {} has the entry but no {} — this scenario needs coil geometry \
                 and channel tables, and that device is described by a card, not by a manifest",
                entry.root.join("device").join(spec).display(),
                facts::MANIFEST.join("/")
            ),
        ));
    }
    let Some(doc) = entry.document.clone() else {
        return Err(refuse(
            "device",
            format!("--device {spec}: the entry in {root} carries neither a card nor a manifest"),
        ));
    };
    let node = crate::io::read_node(&doc)
        .map_err(|e| refuse("device", format!("--device {spec}: {e}")))?;
    let file = if dry { doc.display().to_string() } else { copy_into(&doc, out_dir, "device")? };
    Ok(DeviceDoc { id: spec.to_string(), root, file, node })
}

#[cfg(feature = "mdsip")]
#[allow(clippy::too_many_arguments)]
fn device_from_manifest(
    args: &Args,
    spec: &str,
    root: &str,
    manifest: &Path,
    ids: &[String],
    out_dir: &Path,
    dry: bool,
) -> Result<DeviceDoc, Refusal> {
    let want: Vec<&str> = ids.iter().map(String::as_str).collect();
    let mut over = crate::assembly::Overrides::default();
    over.select = Vec::new();
    let (a, notes) = crate::assembly::from_manifest(manifest, &want, args.flag("provider"), None, None, &over)
        .map_err(|e| refuse("device", format!("--device {spec}: {e}")))?;
    //: ★**不开套接字**：装置描述是几何与通道表，是 `static` 那半边。MDSplus 源在
    //: 这里一律记为失败，而那正确——取数是测量的事，不是装置的事（E-6 / L-8）。
    let asm = crate::assembly::assemble(&a, None);
    if dry {
        //: 装出来了，但不落盘：`--dry-run` 不写记录目录（E-19）。装置那一层的缺省
        //: 因此照样看得见——它是**这次运行会用的值**，正是 dry-run 要回答的。
        return Ok(DeviceDoc {
            id: spec.to_string(),
            root: root.to_string(),
            file: format!("(would assemble from {})", manifest.display()),
            node: asm.bundle.to_node(),
        });
    }
    let file = "device.fyo.jsonld";
    let path = out_dir.join(file);
    ensure_dir(out_dir)?;
    crate::io::write(&path, &asm.bundle, None, crate::io::Layout::Fyo)
        .map_err(|e| refuse("device", format!("{}: {e}", path.display())))?;
    let node = crate::io::read_node(&path)
        .map_err(|e| refuse("device", format!("{}: {e}", path.display())))?;
    for n in notes.iter().chain(asm.notes.iter()) {
        eprintln!("fy run: device: {n}");
    }
    Ok(DeviceDoc { id: spec.to_string(), root: root.to_string(), file: file.to_string(), node })
}

#[cfg(not(feature = "mdsip"))]
#[allow(clippy::too_many_arguments)]
fn device_from_manifest(
    _args: &Args,
    spec: &str,
    _root: &str,
    _manifest: &Path,
    _ids: &[String],
    _out_dir: &Path,
    _dry: bool,
) -> Result<DeviceDoc, Refusal> {
    Err(refuse(
        "device",
        format!("--device {spec}: this build has no assembly layer (feature `mdsip`), so a device \
                 manifest cannot be flattened into a document here"),
    ))
}

/// 路二：模板的 `from_device` 表按 fyo 路径给参数缺省（E-14）。
///
/// 取到就设、取不到**不设**；只盖模板给的那一层，预设与命令行都在它之上。
fn apply_device_defaults(plan: &mut Plan, prov: &mut Prov, t: &Template, dev: &DeviceDoc) {
    for p in &t.vocab {
        let Some(path) = &p.from_device else { continue };
        let Some(v) = at_path(&dev.node, path) else { continue };
        let beats = match prov.get(&p.key) {
            None => true,
            Some(f) => f.starts_with("template:"),
        };
        if !beats {
            continue;
        }
        set(plan, prov, &p.key, v.clone(), &format!("device:{}@{}", dev.id, dev.root));
    }
}

// ───────────────────────────── 测量 ─────────────────────────────

struct Measurements {
    /// 相对记录目录的文件名，或一条绝对 / 相对路径。
    endpoint: String,
    from: String,
    /// `--dry-run` 下第 3 级不连接，于是端口**不绑**：那一行说的是「将要取什么」。
    bound: bool,
}

/// 三级解析（E-15）：`--input` → 语料里的离线切片 → 取数。
#[allow(clippy::too_many_arguments)]
fn resolve_measurements(
    args: &Args,
    t: &Template,
    port: &str,
    device: Option<&str>,
    out_dir: &Path,
    dry: bool,
) -> Result<Measurements, Refusal> {
    let mut tried: Vec<String> = Vec::new();

    if let Some(f) = args.flag("input") {
        let p = PathBuf::from(f);
        if !p.is_file() {
            return Err(refuse("measurements", format!("--input {f}: no such file")));
        }
        return Ok(Measurements { endpoint: f.to_string(), from: "cli:input".into(), bound: true });
    }
    tried.push("--input was not given".into());

    let Some(shot) = args.flag("shot") else {
        return Err(refuse(
            "measurements",
            format!(
                "the `{port}` port of `{}` has nothing bound: give --input <document>, or a \
                 shot (shot=N) to resolve one\n  tried: {}",
                t.name,
                tried.join("; ")
            ),
        ));
    };
    let machine = device.unwrap_or("");
    let time = args.flag("time");

    if machine.is_empty() {
        tried.push("no --device, so the corpus cannot be asked which machine's shot this is".into());
    } else {
        match facts::shot(machine, shot) {
            Some(s) => {
                let slices = s.slices();
                if slices.is_empty() {
                    tried.push(format!("{} has no slice documents", s.dir.display()));
                } else if let Some(t_s) = time {
                    match crate::mdsbind::TimeSel::parse(t_s) {
                        Ok(_) => {}
                        Err(e) => return Err(refuse("measurements", format!("time: {e}"))),
                    }
                    match nearest_slice(&slices, t_s) {
                        Some((at, path)) => {
                            return Ok(Measurements {
                                endpoint: path.display().to_string(),
                                from: format!("resolved:experiment/{machine}/{shot}@{} (t={at} s)", s.root.display()),
                                bound: true,
                            })
                        }
                        None => tried.push(format!(
                            "{} carries {} slices, none within the tolerance of t={t_s}",
                            s.dir.display(),
                            slices.len()
                        )),
                    }
                } else {
                    tried.push(format!(
                        "{} carries {} slices but no `time=` said which",
                        s.dir.display(),
                        slices.len()
                    ));
                }
            }
            None => tried.push(format!("no experiment/{machine}/{shot} entry on the facts path")),
        }
    }

    if offline(args) {
        return Err(refuse(
            "measurements",
            format!(
                "offline, and shot {shot} did not resolve from the corpus\n  tried: {}",
                tried.join("; ")
            ),
        ));
    }
    if dry {
        //: ★★`--dry-run` 停在套接字之前（E-19）：说出**将要**取什么，不连接、不落文件。
        //: 与 `data fetch --dry-run` 同形。
        let ids = t.port(port).map(|p| p.ids.join(", ")).unwrap_or_default();
        let host = args
            .flag("mdsip")
            .map(str::to_string)
            .or_else(|| std::env::var("FYLITE_MDSIP_SERVER").ok())
            .unwrap_or_else(|| "the manifest's own server".into());
        return Ok(Measurements {
            endpoint: String::new(),
            from: format!(
                "would fetch: device={machine} shot={shot}{} ids=[{ids}] via {host}",
                time.map(|t| format!(" time={t}")).unwrap_or_default()
            ),
            bound: false,
        });
    }
    fetch_measurements(args, t, port, machine, shot, time, out_dir, &mut tried)
}

fn nearest_slice(slices: &[(f64, PathBuf)], want: &str) -> Option<(f64, PathBuf)> {
    //: 一个点才谈得上「最近的一片」；窗与表逐片，那是 `series` 的事，P1 不做。
    let t: f64 = want.parse().ok()?;
    let mut best: Option<(f64, &(f64, PathBuf))> = None;
    for s in slices {
        let d = (s.0 - t).abs();
        if best.map(|(bd, _)| d < bd).unwrap_or(true) {
            best = Some((d, s));
        }
    }
    //: 容差 1 ms：切片文件名就是毫秒（`slice_04000ms`），所以「最近」在这个粒度上
    //: 才有意义。超出容差**不取邻片**——邻片是另一个时刻的等离子体。
    best.filter(|(d, _)| *d <= 1e-3).map(|(_, s)| (s.0, s.1.clone()))
}

fn offline(args: &Args) -> bool {
    args.has("offline")
        || std::env::var("FYLITE_OFFLINE").map(|v| !v.trim().is_empty() && v != "0").unwrap_or(false)
}

#[cfg(feature = "mdsip")]
#[allow(clippy::too_many_arguments)]
fn fetch_measurements(
    args: &Args,
    t: &Template,
    port: &str,
    machine: &str,
    shot: &str,
    time: Option<&str>,
    out_dir: &Path,
    tried: &mut Vec<String>,
) -> Result<Measurements, Refusal> {
    if machine.is_empty() {
        return Err(refuse(
            "measurements",
            format!("a fetch needs --device (which machine is shot {shot}?)\n  tried: {}", tried.join("; ")),
        ));
    }
    let Some(entry) = facts::find("device", machine) else {
        return Err(refuse("measurements", format!("--device {machine}: not on the facts path")));
    };
    let Some(manifest) = entry.manifest_path() else {
        return Err(refuse(
            "measurements",
            format!("--device {machine}: described by a card, not by a manifest — nothing to fetch against\n  \
                     tried: {}", tried.join("; ")),
        ));
    };
    let ids: Vec<&str> = t
        .port(port)
        .map(|p| p.ids.iter().map(String::as_str).collect())
        .unwrap_or_default();
    if ids.is_empty() {
        return Err(refuse(
            "measurements",
            format!("the `{port}` port of `{}` declares no IDS to fetch", t.name),
        ));
    }
    let mut over = crate::assembly::Overrides {
        shot: Some(shot.parse::<i64>().map_err(|_| refuse("measurements", "shot wants an integer"))?),
        ..Default::default()
    };
    if let Some(x) = time {
        over.time = Some(crate::mdsbind::TimeSel::parse(x).map_err(|e| refuse("measurements", e))?);
    }
    let host = args.flag("mdsip").map(str::to_string).or_else(|| std::env::var("FYLITE_MDSIP_SERVER").ok());
    let (host, port_no) = match host.as_deref() {
        Some(h) => match h.split_once(':') {
            Some((a, b)) => (Some(a.to_string()), b.parse::<u16>().ok()),
            None => (Some(h.to_string()), None),
        },
        None => (None, None),
    };
    let (a, notes) = crate::assembly::from_manifest(&manifest, &ids, args.flag("provider"), host.as_deref(), port_no, &over)
        .map_err(|e| refuse("measurements", format!("{e}")))?;
    let user = args
        .flag("mds-user")
        .map(str::to_string)
        .or_else(|| std::env::var("FYLITE_MDSIP_USER").ok())
        .or_else(|| std::env::var("USER").ok())
        .unwrap_or_else(|| "fylite".into());
    let timeout = args.flag("timeout-ms").and_then(|s| s.parse::<u64>().ok()).unwrap_or(10_000);
    let connector = crate::assembly::tcp_connector(user, timeout);
    let mut asm = crate::assembly::assemble(&a, Some(&connector));
    asm.notes.splice(0..0, notes);
    if !asm.failures.is_empty() {
        return Err(refuse(
            "measurements",
            format!(
                "the fetch of shot {shot} from {machine} failed: {}\n  tried: {}",
                asm.failures.join("; "),
                tried.join("; ")
            ),
        ));
    }
    //: ★★取回来的先落地再进门（E-15）：于是同一次分析可以离线重放。
    ensure_dir(out_dir)?;
    let file = "measurements.fyo.jsonld";
    let path = out_dir.join(file);
    crate::io::write(&path, &asm.bundle, None, crate::io::Layout::Fyo)
        .map_err(|e| refuse("measurements", format!("{}: {e}", path.display())))?;
    for n in &asm.notes {
        eprintln!("fy run: measurements: {n}");
    }
    Ok(Measurements {
        endpoint: file.to_string(),
        from: format!("resolved:mdsip shot={shot} device={machine}"),
        bound: true,
    })
}

#[cfg(not(feature = "mdsip"))]
#[allow(clippy::too_many_arguments)]
fn fetch_measurements(
    _args: &Args,
    _t: &Template,
    _port: &str,
    _machine: &str,
    shot: &str,
    _time: Option<&str>,
    _out_dir: &Path,
    tried: &mut Vec<String>,
) -> Result<Measurements, Refusal> {
    Err(refuse(
        "measurements",
        format!(
            "shot {shot} did not resolve from the corpus, and this build has no MDSplus client \
             (feature `mdsip`)\n  tried: {}",
            tried.join("; ")
        ),
    ))
}

/// 这次运行要写哪种格式：`--format` 优先，否则计划的输出端口自己要的那种，
/// 都没有就 `jsonld`。★一处判定：`build` 拿它来**先问**这份构建写不写得了，
/// `execute` 拿它来写——两处若各判一次，某一天它们会给出不同的答案。
fn effective_format(args: &Args, plan: &Plan) -> String {
    let asked = plan.outputs.iter().find_map(|r| r.format_iri.clone());
    args.flag("format")
        .map(str::to_string)
        .or_else(|| {
            asked.map(|f| match f.as_str() {
                "fyo:ImasHdf5Format" | "imas_hdf5" => "imas-hdf5".to_string(),
                other if other.ends_with("ImasHdf5Format") => "imas-hdf5".to_string(),
                other if other.ends_with("ld+json") => "jsonld".to_string(),
                other => other.to_string(),
            })
        })
        .unwrap_or_else(|| "jsonld".into())
        .to_ascii_lowercase()
}

/// 这份构建写得了这种格式吗（`hdf5` / `netcdf` 是编译期特性）。
///
/// ★★**先问，别写到一半才发现**（`FYL-DESIGN-16` B-1 的同一条姿态）。实测过反面：
/// 一份不带 `hdf5` 特性的 `fy` 跑 `evolve-iter-15ma`（它的输出端口要 IMAS HDF5）
/// 会**先把内核跑完**，再在写第一个数据集时以 `exit 2` 停住——那个码在本篇里的
/// 意思是「语法错，没有记录」，而这里既不是语法错、又已经算出了结果。
/// 现在它是合成阶段的一次按名拒绝：退 1、落记录、说清楚换什么。
fn writable(format: &str) -> Result<(), String> {
    let (need, have) = match format {
        "jsonld" | "json" => return Ok(()),
        "hdf5" | "h5" => ("hdf5", cfg!(feature = "hdf5")),
        "netcdf" | "nc" => ("netcdf", cfg!(feature = "netcdf")),
        "imas-hdf5" | "imas" => ("hdf5", cfg!(feature = "hdf5")),
        other => {
            return Err(format!(
                "unknown format `{other}` — one of jsonld, hdf5, netcdf, imas-hdf5"
            ))
        }
    };
    if have {
        return Ok(());
    }
    Err(format!(
        "this build cannot write `{format}`: it was compiled without the `{need}` feature.\n           Either rebuild with it (`bash rust/build.sh --exe`, or `--static` on a machine \n           without libhdf5 / libnetcdf), or ask for a format it has: --format jsonld"
    ))
}

// ───────────────────────────── 记录目录 ─────────────────────────────

fn ensure_dir(dir: &Path) -> Result<(), Refusal> {
    std::fs::create_dir_all(dir).map_err(|e| refuse("compose", format!("{}: {e}", dir.display())))
}

fn copy_into(src: &Path, out_dir: &Path, tag: &str) -> Result<String, Refusal> {
    ensure_dir(out_dir)?;
    let ext = src.extension().and_then(|s| s.to_str()).unwrap_or("jsonld");
    let name = format!("{tag}.{ext}");
    std::fs::copy(src, out_dir.join(&name))
        .map_err(|e| refuse("compose", format!("{}: {e}", src.display())))?;
    Ok(name)
}

fn write_text(path: &Path, text: &str) -> (String, usize) {
    if let Err(e) = std::fs::write(path, text) {
        eprintln!("fy run: {}: {e}", path.display());
        std::process::exit(2);
    }
    (crate::checksum::sha256_hex(text.as_bytes()), text.len())
}

// ───────────────────────────── 合成 ─────────────────────────────

/// 模板 → 装置 → 预设 → `--plan` → 命令行 → 端口（E-13）。
fn build(args: &Args, target: &Target, out_dir: &Path, dry: bool) -> Result<(Plan, Prov, PathBuf, Option<DeviceDoc>), Refusal> {
    let mut docs: Vec<(Source, Node)> = Vec::new();
    let base;

    match target {
        Target::Scenario { template, .. } => {
            let text = json::to_string(&template.node, true);
            let path = template.path.clone().unwrap_or_else(|| PathBuf::from(format!("scenario/{}", template.name)));
            base = path.parent().map(Path::to_path_buf).unwrap_or_default();
            docs.push((
                Source {
                    path,
                    id: Some(format!("scenario/{}", template.name)),
                    sha256: crate::checksum::sha256_hex(text.as_bytes()),
                    bytes: text.len(),
                },
                template.node.clone(),
            ));
        }
        Target::Plans { paths, .. } => {
            for p in paths {
                let d = case::read_source(p).map_err(|e| refuse("compose", e.0))?;
                docs.push(d);
            }
            base = paths[0].parent().map(Path::to_path_buf).unwrap_or_default();
        }
    }
    let template_layers = docs.len();

    if let Some(name) = args.flag("preset") {
        let doc = if looks_like_path(name) {
            case::read_source(Path::new(name)).map_err(|e| refuse("compose", e.0))?
        } else {
            let Some(p) = corpus::preset(name) else {
                let names: Vec<String> = corpus::presets().into_iter().map(|d| d.name).collect();
                let near = corpus::nearest(name, &names, 3);
                let hint = if near.is_empty() {
                    "`fy list presets` lists them".to_string()
                } else {
                    format!("did you mean {}?", near.join(", "))
                };
                return Err(refuse("compose", format!("--preset {name}: no preset by that name — {hint}")));
            };
            let path = p.path.clone().unwrap_or_default();
            case::read_source(&path).map_err(|e| refuse("compose", e.0))?
        };
        docs.push(doc);
    }
    for p in args.all("plan") {
        docs.push(case::read_source(Path::new(p)).map_err(|e| refuse("compose", e.0))?);
    }

    let mut plan = case::compose(docs).map_err(|e| refuse("compose", e.0))?;
    if let Some(c) = args.flag("code") {
        plan.code = c.to_string();
    }

    //: 来源账：合成把每个值标了「第几份文档」，这里翻成一句读得懂的话。
    let mut prov = Prov::default();
    for s in &plan.settings {
        let from = match s.from {
            Some(i) if i < template_layers => match target {
                Target::Scenario { template, .. } => format!("template:{}", template.name),
                Target::Plans { .. } => format!("plan:{}", plan.sources[i].path.display()),
            },
            Some(i) => {
                let path = plan.sources[i].path.display().to_string();
                if args.flag("preset").is_some() && i == template_layers {
                    format!("preset:{path}")
                } else {
                    format!("plan:{path}")
                }
            }
            None => "cli".into(),
        };
        prov.set(&s.name.clone(), from);
    }

    //: 装置：整份文档绑端口，`from_device` 表给缺省（E-14）
    let mut device = None;
    if let Some(spec) = args.flag("device") {
        let d = load_device(args, target.template(), spec, out_dir, dry)?;
        if let Some(t) = target.template() {
            apply_device_defaults(&mut plan, &mut prov, t, &d);
            if t.port("device").is_some() {
                plan.bind_override(&format!("device={}", d.file)).map_err(|e| refuse("compose", e.0))?;
                prov.set("__port_device", format!("device:{}@{}", d.id, d.root));
            }
        } else {
            plan.bind_override(&format!("device={}", d.file)).map_err(|e| refuse("compose", e.0))?;
        }
        device = Some(d);
    }

    //: 命令行：开关先展开，显式参数后落（E-18）
    apply_open(&mut plan, &mut prov, target.template(), &args.open)?;

    //: 通用参数：`shot` / `time` 由固定选项承载，模板声明它收才落进计划
    for name in ["shot", "time"] {
        let Some(v) = args.flag(name) else { continue };
        let takes = target.template().map(|t| t.takes_common(name)).unwrap_or(true);
        if !takes {
            continue;
        }
        let node = if name == "shot" {
            v.parse::<i64>().map(Node::Int).unwrap_or_else(|_| Node::Str(v.to_string()))
        } else {
            Node::Str(v.to_string())
        };
        set(&mut plan, &mut prov, name, node, "cli");
    }

    //: 端口：`--input` 绑主端口，`--bind` 绑其余；测量三级解析（E-15）
    for b in args.all("bind") {
        plan.bind_override(b).map_err(|e| refuse("compose", e.0))?;
    }
    let bound: Vec<String> = args
        .all("bind")
        .iter()
        .filter_map(|b| b.split_once('=').map(|(p, _)| p.to_string()))
        .collect();
    if let Some(t) = target.template() {
        if let Some(port) = t.primary_port() {
            let name = port.name.clone();
            if !bound.contains(&name) {
                let need_input = args.flag("input").is_some()
                    || args.flag("shot").is_some()
                    || !port.optional;
                if need_input {
                    match resolve_measurements(args, t, &name, args.flag("device"), out_dir, dry) {
                        Ok(m) => {
                            if m.bound {
                                plan.bind_override(&format!("{name}={}", m.endpoint))
                                    .map_err(|e| refuse("compose", e.0))?;
                            }
                            prov.set(&format!("__port_{name}"), m.from);
                        }
                        //: ★★`--dry-run` 下解析不到**不是拒绝，是一行输出**。这条命令
                        //: 回答的是「会发生什么」，而「这个端口今天绑不上，因为…」正是
                        //: 要回答的一部分——要求先把每个输入备齐才肯给出计划，恰好
                        //: 取消了先看一眼的用处。真跑的那一次照旧拒绝。
                        Err(r) if dry => {
                            prov.set(
                                &format!("__port_{name}"),
                                format!("unresolved ({}): {}", r.stage, r.message.lines().next().unwrap_or("")),
                            );
                        }
                        Err(r) => return Err(r),
                    }
                }
            }
        }
    } else if let Some(f) = args.flag("input") {
        return Err(refuse(
            "compose",
            format!("--input {f}: these plans resolve to no template, so there is no primary port \
                     to bind it to — name the port with --bind <port>={f}"),
        ));
    }

    Ok((plan, prov, base, device))
}

// ───────────────────────────── 出口 ─────────────────────────────

/// `run` 的全部（`args.command == ["run"]`）。
pub fn run(args: &Args) {
    //: a closed pipe ends a listing, it is not a panic (`| head`)
    unsafe { signal(13, 0) };
    super::data::apply_facts(args);
    apply_cases(args);

    let mut target = resolve_target(args);
    //: 计划文件形：模板由合成后计划的 code 末段反查——查得到就校验，查不到就透传。
    if let Target::Plans { paths, template } = &mut target {
        if let Ok(docs) = paths.iter().map(|p| case::read_source(p)).collect::<Result<Vec<_>, _>>() {
            if let Ok(p) = case::compose(docs) {
                *template = corpus::template(&p.bar());
            }
        }
    }

    let dry = args.has("dry-run");
    let record_dir = record_dir(args, &target);
    //: ★dry-run 不写任何东西，所以它也不需要一个输出目录——`load_device` 与
    //: 测量解析在这一档都只读。
    let out_dir = record_dir.clone();

    let built = build(args, &target, &out_dir, dry);
    let (plan, prov, base, device) = match built {
        Ok(x) => x,
        Err(r) => {
            //: 合成之前的拒绝落不了记录（还没有计划）；合成之后的由 `execute` 落。
            eprintln!("fy run: [{}] {}", r.stage, r.message);
            std::process::exit(1);
        }
    };

    let mut node = plan.to_node();
    stamp(&mut node, &prov);

    if dry {
        if args.has("json") {
            println!("{}", json::to_string(&node, true));
        } else {
            print_dry(args, &target, &plan, &prov, device.as_ref(), &record_dir);
        }
        return;
    }
    execute(args, &target, plan, node, &prov, &base, &record_dir);
}

fn apply_cases(args: &Args) {
    let given = args.all("cases");
    if !given.is_empty() {
        corpus::use_roots(Some(corpus::parse_roots(given)));
    }
    for line in corpus::problems() {
        eprintln!("fy run: {line}");
    }
}

fn record_dir(args: &Args, target: &Target) -> PathBuf {
    if let Some(d) = args.flag("record") {
        return PathBuf::from(d);
    }
    let (_secs, stamp) = case::now_iso();
    let parent = std::env::var("FYLITE_RUN_DIR").unwrap_or_else(|_| "records".into());
    PathBuf::from(parent).join(format!("{}-{}", stamp.replace([':', '-'], ""), target.tag()))
}

fn print_dry(args: &Args, target: &Target, plan: &Plan, prov: &Prov, device: Option<&DeviceDoc>, record_dir: &Path) {
    match target {
        Target::Scenario { line, template } => println!(
            "{line} · {}  ->  {}   (template {}, {} parameters declared)",
            template.name,
            plan.code,
            template.origin,
            template.vocab.len()
        ),
        Target::Plans { paths, template } => println!(
            "{}  ->  {}   ({})",
            paths.iter().map(|p| p.display().to_string()).collect::<Vec<_>>().join(" + "),
            plan.code,
            template
                .as_ref()
                .map(|t| format!("template {} checks the parameters", t.name))
                .unwrap_or_else(|| "no template for this code — parameters pass through unchecked".into())
        ),
    }
    if let Some(d) = device {
        println!("  device   {} from {}  -> {}", d.id, d.root, d.file);
    }
    println!("  record   {}  (not written: --dry-run)", record_dir.display());
    if let Err(e) = writable(&effective_format(args, plan)) {
        println!("  format   ★ {}", e.lines().next().unwrap_or(""));
    }
    println!("\n  {:<20} {:<22} {}", "parameter", "value", "from");
    for s in &plan.settings {
        println!(
            "  {:<20} {:<22} {}",
            s.name,
            json::to_string(&s.value, false),
            prov.get(&s.name).unwrap_or("?")
        );
    }
    for b in &plan.inputs {
        let what = match (&b.endpoint, &b.inline) {
            (Some(e), _) => e.clone(),
            (None, Some(_)) => "(inline)".into(),
            (None, None) => "OPEN — nothing bound".into(),
        };
        println!(
            "  input {:<14} {:<22} {}",
            b.port,
            what,
            prov.get(&format!("__port_{}", b.port)).unwrap_or("cli:bind")
        );
    }
    //: 还没绑上、但这次运行会去取的那些端口（dry-run 的第 3 级）
    for (k, v) in prov.0.iter() {
        let Some(port) = k.strip_prefix("__port_") else { continue };
        if plan.inputs.iter().any(|b| b.port == port) {
            continue;
        }
        println!("  input {port:<14} {:<22} {v}", "(not fetched)");
    }
    if plan.settings.is_empty() && plan.inputs.is_empty() {
        println!("  (nothing set and nothing bound)");
    }
}

/// 装内核、跑、落记录。★这一段是从前 `cli/case.rs` 的 `run_cmd`，逐字搬过来的：
/// 搬家不是改写，产出的记录与从前逐字节同形。
fn execute(args: &Args, target: &Target, plan: Plan, plan_node: Node, prov: &Prov, base: &Path, record_dir: &Path) {
    let quiet = args.has("quiet");
    let to_stdout = args.has("json");
    let (_started_secs, started_at) = case::now_iso();
    let record_id = format!("run/{}-{}", started_at.replace([':', '-'], ""), target.tag());
    if let Err(e) = std::fs::create_dir_all(record_dir) {
        eprintln!("fy run: {}: {e}", record_dir.display());
        std::process::exit(2);
    }
    let plan_text = json::to_string(&plan_node, true) + "\n";
    write_text(&record_dir.join("plan.jsonld"), &plan_text);

    //: ★格式是**计划的一部分**（输出端口自己要的那种），所以「这份构建写不写得了」
    //: 与「缺哪个绑定」同属合成阶段——在装内核之前问，而不是把内核跑完、再在写第一
    //: 个数据集时停住。问得早，那次拒绝才带得上记录（E-20：退 1 必有记录）。
    if let Err(e) = writable(&effective_format(args, &plan)) {
        finish_refused(&plan, record_dir, &record_id, "compose", &e, &started_at, prov);
        return;
    }

    let kernel = match Kernel::load(args.flag("kernel").map(Path::new)) {
        Ok(k) => k,
        Err(e) => {
            finish_refused(&plan, record_dir, &record_id, "kernel", &e.message, &started_at, prov);
            return;
        }
    };
    let kernel_sha = std::fs::read(&kernel.path).ok().map(|b| crate::checksum::sha256_hex(&b));

    //: 绑定的解析相对**计划自己的目录**；从记录目录里那两份文档来的是相对记录目录的。
    let (slots, resolved) = match case::resolve_inputs(&plan, base) {
        Ok(x) => x,
        Err(e) => match case::resolve_inputs(&plan, record_dir) {
            Ok(x) => x,
            Err(_) => {
                finish_refused(&plan, record_dir, &record_id, "compose", &e.0, &started_at, prov);
                return;
            }
        },
    };
    let (numbers, texts) = match plan.kernel_settings() {
        Ok(x) => x,
        Err(e) => {
            finish_refused(&plan, record_dir, &record_id, "compose", &e.0, &started_at, prov);
            return;
        }
    };
    let result = kernel.run_case(&plan.code, &numbers, &texts, &slots);
    let (_end_secs, ended_at) = case::now_iso();

    let mut produced: Vec<Produced> = Vec::new();
    let mut dd_notes: Vec<String> = Vec::new();
    let outcome = match &result {
        Ok(raw) => match case::parse_outcome(raw) {
            Ok(o) => {
                //: `build` 已经问过这份构建写不写得了（`writable`）；这里只是取同一个答案。
                let format = effective_format(args, &plan);
                let docs = case::documents(&o, raw, &record_id);
                if format == "imas-hdf5" || format == "imas" {
                    let mut bundle = crate::fyodoc::Bundle::new();
                    for (_ids, doc) in &docs {
                        bundle.push(doc.clone());
                    }
                    let dir = record_dir.join("imas");
                    let rep = crate::io::write(&dir, &bundle, Some(crate::detect::Format::ImasHdf5Dir), crate::io::Layout::Imas)
                        .unwrap_or_else(|e| {
                            eprintln!("fy run: imas: {e}");
                            std::process::exit(2);
                        });
                    for (key, r) in &rep.dd {
                        for d in &r.dropped {
                            if !d.starts_with('@') {
                                dd_notes.push(format!("imas {key}: dropped {d} (not in the DD)"));
                            }
                        }
                        for d in &r.promoted {
                            dd_notes.push(format!("imas {key}: {d} promoted to element 0"));
                        }
                        for d in &r.synthesized {
                            dd_notes.push(format!("imas {key}: {d} synthesized"));
                        }
                    }
                    for (ids, _doc) in &docs {
                        let file = format!("imas/{ids}.h5");
                        let bytes = std::fs::read(record_dir.join(&file)).unwrap_or_default();
                        let fields: Vec<String> = o
                            .fields
                            .iter()
                            .filter(|f| (if f.ids.is_empty() { "entry" } else { f.ids.as_str() }) == ids)
                            .map(|f| format!("{} [{}] {:?}", f.path, f.units, f.dims))
                            .collect();
                        produced.push(Produced {
                            port: ids.clone(),
                            doc_id: format!("{record_id}/{ids}"),
                            doc_type: format!("fyo:{ids}"),
                            storage_uri: file,
                            format_iri: "fyo:ImasHdf5Format".into(),
                            sha256: crate::checksum::sha256_hex(&bytes),
                            bytes: bytes.len(),
                            fields,
                            inline: None,
                        });
                    }
                    let master = std::fs::read(record_dir.join("imas/master.h5")).unwrap_or_default();
                    produced.push(Produced {
                        port: "imas".into(),
                        doc_id: format!("{record_id}/imas"),
                        doc_type: "spo:InformationContentEntity".into(),
                        storage_uri: "imas/master.h5".into(),
                        format_iri: "fyo:ImasHdf5Format".into(),
                        sha256: crate::checksum::sha256_hex(&master),
                        bytes: master.len(),
                        fields: vec!["the data entry's master file (external links to every IDS)".into()],
                        inline: None,
                    });
                }
                for (ids, doc) in docs {
                    if format == "imas-hdf5" || format == "imas" {
                        break;
                    }
                    let fields: Vec<String> = o
                        .fields
                        .iter()
                        .filter(|f| (if f.ids.is_empty() { "entry" } else { f.ids.as_str() }) == ids)
                        .map(|f| format!("{} [{}] {:?}", f.path, f.units, f.dims))
                        .collect();
                    let (file, format_iri, sha, bytes) = match format.as_str() {
                        "jsonld" | "json" => {
                            let file = format!("{ids}.fyo.jsonld");
                            let text = json::to_string(&doc, true) + "\n";
                            let (sha, bytes) = write_text(&record_dir.join(&file), &text);
                            (file, case::LD_JSON.to_string(), sha, bytes)
                        }
                        other => {
                            let ext = match other {
                                "hdf5" | "h5" => "h5",
                                "netcdf" | "nc" => "nc",
                                //: `writable` 在合成阶段已经拒过每一个别的取值
                                _ => unreachable!("writable() accepted {other}"),
                            };
                            let file = format!("{ids}.{ext}");
                            let bundle = crate::fyodoc::Bundle::one(doc.clone());
                            if let Err(e) = crate::io::write(&record_dir.join(&file), &bundle, None, crate::io::Layout::Fyo) {
                                eprintln!("fy run: {file}: {e}");
                                std::process::exit(2);
                            }
                            let bytes = std::fs::read(record_dir.join(&file)).unwrap_or_default();
                            (file, "[TBD]".to_string(), crate::checksum::sha256_hex(&bytes), bytes.len())
                        }
                    };
                    produced.push(Produced {
                        port: ids.clone(),
                        doc_id: format!("{record_id}/{ids}"),
                        doc_type: format!("fyo:{ids}"),
                        storage_uri: file,
                        format_iri,
                        sha256: sha,
                        bytes,
                        fields,
                        inline: None,
                    });
                }
                Some(o)
            }
            Err(e) => {
                finish_refused(&plan, record_dir, &record_id, "kernel", &e.0, &started_at, prov);
                return;
            }
        },
        Err(_) => None,
    };
    let mut outcome = outcome;
    if let Some(o) = outcome.as_mut() {
        o.notes.extend(dd_notes.iter().cloned());
    }
    let mut rec = case::record(&RecordInputs {
        plan: &plan,
        plan_file: Some("plan.jsonld"),
        resolved: &resolved,
        kernel: Some(&kernel),
        kernel_sha256: kernel_sha,
        outcome: outcome.as_ref(),
        refusal: result.as_ref().err(),
        produced: &produced,
        started_at,
        ended_at,
        record_id: record_id.clone(),
    });
    if result.is_err() {
        stage_of(&mut rec, "kernel");
    }
    let rec_text = json::to_string(&rec, true) + "\n";
    write_text(&record_dir.join("record.jsonld"), &rec_text);

    match (&result, &outcome) {
        (Ok(_), Some(o)) => {
            if to_stdout {
                print!("{rec_text}");
            } else if !quiet {
                println!(
                    "{}  {} -> {}  entry {}  {}",
                    record_id,
                    plan.id,
                    plan.code,
                    o.entry,
                    o.dims.iter().map(|(k, n)| format!("{k}={n}")).collect::<Vec<_>>().join(" ")
                );
                for (k, u, v) in &o.facts {
                    println!("  {k:<16} {v} {u}");
                }
                for p in &produced {
                    println!("  {:<24} {} ({} fields, {} bytes)", p.port, p.storage_uri, p.fields.len(), p.bytes);
                }
                for n in &o.notes {
                    println!("  note: {n}");
                }
                println!("  record: {}", record_dir.join("record.jsonld").display());
            }
        }
        (Err(e), _) => {
            if to_stdout {
                print!("{rec_text}");
            }
            eprintln!("fy run: [kernel] the kernel refused `{}`: {}", plan.code, e);
            eprintln!("  record: {}  (run_state: rejected)", record_dir.join("record.jsonld").display());
            std::process::exit(1);
        }
        _ => {}
    }
}

/// 记录里那一行「哪一步拒的」（E-20）。
fn stage_of(rec: &mut Node, stage: &str) {
    if let Some(m) = rec.as_map_mut() {
        m.insert("fylite:refusal_stage", stage.into());
    }
}

/// 合成之后、内核之外的拒绝：落一份 `run_state: rejected` 的记录，退 1。
fn finish_refused(
    plan: &Plan,
    record_dir: &Path,
    record_id: &str,
    stage: &'static str,
    message: &str,
    started_at: &str,
    _prov: &Prov,
) {
    let (_s, ended_at) = case::now_iso();
    let err = KernelError { code: 0, message: message.to_string() };
    let mut rec = case::record(&RecordInputs {
        plan,
        plan_file: Some("plan.jsonld"),
        resolved: &[],
        kernel: None,
        kernel_sha256: None,
        outcome: None,
        refusal: Some(&err),
        produced: &[],
        started_at: started_at.to_string(),
        ended_at,
        record_id: record_id.to_string(),
    });
    stage_of(&mut rec, stage);
    let text = json::to_string(&rec, true) + "\n";
    write_text(&record_dir.join("record.jsonld"), &text);
    eprintln!("fy run: [{stage}] {message}");
    eprintln!("  record: {}  (run_state: rejected)", record_dir.join("record.jsonld").display());
    std::process::exit(1);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_path_is_told_from_a_name() {
        assert!(looks_like_path("docs/examples/zerod/zerod-iter-15ma.jsonld"));
        assert!(looks_like_path("plan.jsonld"));
        assert!(looks_like_path("a.yaml"));
        assert!(!looks_like_path("analysis"));
        assert!(!looks_like_path("transport-iter-15ma"));
    }

    #[test]
    fn a_value_is_checked_against_the_template_not_against_json() {
        let t = corpus::template("reconstruction").unwrap();
        let kin = t.param("kin").unwrap();
        assert!(matches!(coerce(kin, "true"), Ok(Node::Bool(true))));
        assert!(matches!(coerce(kin, "false"), Ok(Node::Bool(false))));
        assert!(coerce(kin, "0.5").is_err());
        let basis = t.param("basis").unwrap();
        assert!(coerce(basis, "delivered").is_ok());
        let e = coerce(basis, "cooked").unwrap_err();
        assert!(e.contains("delivered") && e.contains("raw"), "{e}");
        let mcn = t.param("mcn").unwrap();
        assert!(coerce(mcn, "-1").is_err(), "the declared minimum is checked");
        assert!(matches!(coerce(mcn, "16"), Ok(Node::Int(16))));
    }

    #[test]
    fn the_nearest_slice_is_the_one_within_a_millisecond() {
        let s = vec![
            (3.0, PathBuf::from("slice_03000ms.fyo.jsonld")),
            (4.0, PathBuf::from("slice_04000ms.fyo.jsonld")),
        ];
        assert_eq!(nearest_slice(&s, "4.0").unwrap().0, 4.0);
        assert_eq!(nearest_slice(&s, "3.0005").unwrap().0, 3.0);
        //: ★邻片是另一个时刻的等离子体：超出容差就没有答案，不取最近的那一片
        assert!(nearest_slice(&s, "3.5").is_none());
    }

    #[test]
    fn a_format_this_build_cannot_write_is_refused_before_the_kernel_runs() {
        assert!(writable("jsonld").is_ok());
        assert!(writable("nonsense").unwrap_err().contains("unknown format"));
        //: 逐特性：带着它就写得了，不带就给出一句说清楚换什么的话
        for (fmt, feat) in [("hdf5", cfg!(feature = "hdf5")), ("netcdf", cfg!(feature = "netcdf"))] {
            match writable(fmt) {
                Ok(()) => assert!(feat, "{fmt} accepted without the feature"),
                Err(e) => {
                    assert!(!feat, "{fmt} refused with the feature: {e}");
                    assert!(e.contains("--format jsonld"), "{e}");
                }
            }
        }
    }

    #[test]
    fn a_fyo_path_reaches_into_the_device_document() {
        let node = json::parse(r#"{"a": {"b": {"c": 7}}}"#).unwrap();
        assert_eq!(at_path(&node, "a/b/c").and_then(Node::as_i64), Some(7));
        assert_eq!(at_path(&node, "a.b.c").and_then(Node::as_i64), Some(7));
        assert!(at_path(&node, "a/x").is_none());
    }
}
