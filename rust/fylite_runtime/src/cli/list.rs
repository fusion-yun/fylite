//! `list` —— 唯一的发现面：有什么可用。
//!
//! ```text
//! fy list devices [east]        fy list scenarios [reconstruction] [--line analysis]
//! fy list experiments [east]    fy list presets   [transport-iter-15ma]
//! fy list facts [device]        fy list kernel    fy list lines
//! ```
//!
//! 「有什么」在 `fy` 里有六类答案，而它们的形一样：一列名字、每个名字来自哪个根、
//! 今天能不能用。从前它们分挂在三条命令上（`data facts` · `case describe` · 翻目录），
//! 于是问得出口的前提是先知道装置归 `data`、场景归 `case`——这条命令词把那层先验
//! 知识收掉（`FYL-DESIGN-17` E-4 / E-24）。
//!
//! ★★**只读，且这条边界是它的用处**：不合成计划、不取数、不写记录、不开套接字。
//! 于是它在没有内核、没有网络、没有写权限的机器上仍然回答得了——而「这条命令**会**
//! 做什么」是 `run --dry-run` 的那一问，两者不重叠。
//!
//! ★装内核的只有 `kernel` 与 `scenarios` 的「门认不认」一列，且**装不上不是错**：
//! 那一列写「内核未找到」，其余照打。

use super::Args;
use crate::corpus::{self, Origin};
use crate::document::Node;
use crate::facts;
use crate::fyo_interface as fi;
use crate::json;
use crate::kernel::Kernel;

extern "C" {
    fn signal(sig: i32, handler: usize) -> usize;
}

fn die(msg: &str) -> ! {
    eprintln!("fy list: {msg}");
    std::process::exit(2);
}

/// 内核今天认哪些 code。装不上就是 `None`——不是错，是一列的取值。
fn door(args: &Args) -> Option<Vec<String>> {
    Kernel::load(args.flag("kernel").map(std::path::Path::new)).ok()?;
    Some(
        fi::BLOCKS
            .iter()
            .find(|b| b.name == "CASE_CODES")
            .map(|b| b.rows.iter().map(|r| format!("code/{}", r.key)).collect())
            .unwrap_or_default(),
    )
}

/// 一个字符在终端上占几列。★CJK 是两列，而 `{:<16}` 数的是**字符**——一张
/// 中英混排的表因此会错位，而这条命令的产物就是表。判据取 East Asian Wide /
/// Fullwidth 的那几段（UAX #11），够这里用。
fn columns(s: &str) -> usize {
    s.chars()
        .map(|c| {
            let u = c as u32;
            let wide = (0x1100..=0x115F).contains(&u)
                || (0x2E80..=0x303E).contains(&u)
                || (0x3041..=0x33FF).contains(&u)
                || (0x3400..=0x4DBF).contains(&u)
                || (0x4E00..=0x9FFF).contains(&u)
                || (0xA000..=0xA4CF).contains(&u)
                || (0xAC00..=0xD7A3).contains(&u)
                || (0xF900..=0xFAFF).contains(&u)
                || (0xFE30..=0xFE6F).contains(&u)
                || (0xFF00..=0xFF60).contains(&u)
                || (0xFFE0..=0xFFE6).contains(&u)
                || (0x20000..=0x3FFFD).contains(&u);
            usize::from(wide) + 1
        })
        .sum()
}

/// 左对齐到 `n` 列，按显示宽度而不是字符数。
fn pad(s: &str, n: usize) -> String {
    let w = columns(s);
    format!("{s}{}", " ".repeat(n.saturating_sub(w)))
}

fn as_json(args: &Args) -> bool {
    args.has("json")
}

fn print_json(node: &Node) {
    println!("{}", json::to_string(node, true));
}

fn map(pairs: Vec<(&str, Node)>) -> Node {
    let mut m = crate::document::Map::new();
    for (k, v) in pairs {
        m.insert(k, v);
    }
    Node::Map(m)
}

fn list(items: Vec<Node>) -> Node {
    Node::List(items)
}

// ───────────────────────────── devices ─────────────────────────────

fn devices(args: &Args) {
    let want: Vec<&str> = args.all("name");
    let entries = facts::entries("device");
    if entries.is_empty() {
        no_corpus("device");
        return;
    }
    if want.is_empty() {
        if as_json(args) {
            print_json(&list(
                entries
                    .iter()
                    .map(|e| {
                        map(vec![
                            ("id", e.ident.clone().into()),
                            ("root", e.root.display().to_string().into()),
                            ("manifest", Node::Bool(e.manifest_path().is_some())),
                            ("card", Node::Bool(e.has_document())),
                            ("rights", Node::Bool(e.rights_path().is_some())),
                        ])
                    })
                    .collect(),
            ));
            return;
        }
        println!("{} {} {} {}", pad("device", 16), pad("described", 10), pad("licence", 8), "from");
        for e in &entries {
            //: ★卡片与清单不是同一件事，而差别是**能不能抓一发炮**：清单是抓取
            //: 跑得起来的那一份（`facts.rs` MANIFEST），卡片只是描述。
            let described = if e.manifest_path().is_some() { "manifest" } else { "card" };
            let rights = if e.rights_path().is_some() { "yes" } else { "—" };
            println!("{} {} {} {}", pad(&e.ident, 16), pad(described, 10), pad(rights, 8), e.root.display());
        }
        println!("\n{} devices; `fy list devices <id>` prints one in full", entries.len());
        return;
    }
    for id in want {
        let Some(e) = entries.iter().find(|e| e.ident == id) else {
            let known: Vec<&str> = entries.iter().map(|e| e.ident.as_str()).collect();
            let near = corpus::nearest(id, &known, 3);
            let hint = if near.is_empty() { String::new() } else { format!("; did you mean {}?", near.join(", ")) };
            die(&format!("no device `{id}` on the facts path{hint}"));
        };
        println!("{}   ({})", e.ident, e.root.display());
        if let Some(d) = &e.document {
            println!("  card      {}", d.display());
        }
        if let Some(r) = e.rights_path() {
            println!("  licence   {}", r.display());
        }
        match e.manifest_path() {
            None => println!(
                "  manifest  — (described by a card; a scenario that needs coil geometry and \n\
                 \x20           channel tables will refuse this device)"
            ),
            Some(m) => {
                println!("  manifest  {}", m.display());
                describe_manifest(&m);
            }
        }
        println!();
    }
}

/// 清单里读得出来的那几样：装置名、逐 IDS 的提供者与缺省、年代数、绑定。
/// ★只打**清单自己说了的**：不推断、不补齐。
fn describe_manifest(path: &std::path::Path) {
    let Ok(node) = crate::io::read_node(path) else {
        println!("  (the manifest did not parse)");
        return;
    };
    let Some(m) = node.as_map() else { return };
    if let Some(d) = m.get("device").and_then(Node::as_str) {
        println!("  device    {d}");
    }
    if let Some(t) = m.get("tbox").and_then(Node::as_str) {
        println!("  t-box     {t}");
    }
    if let Some(e) = m.get("epochs").and_then(Node::as_list) {
        println!("  epochs    {}", e.len());
    }
    if let Some(p) = m.get("providers").and_then(Node::as_map) {
        for (ids, v) in p.iter() {
            let def = v.as_map().and_then(|x| x.get("default")).and_then(Node::as_str).unwrap_or("?");
            let avail: Vec<String> = v
                .as_map()
                .and_then(|x| x.get("available"))
                .and_then(Node::as_map)
                .map(|a| a.keys().map(str::to_string).collect())
                .unwrap_or_default();
            println!("  provider  {ids:<12} default {def}  ({})", avail.join(", "));
        }
    }
}

// ───────────────────────────── experiments ─────────────────────────────

fn experiments(args: &Args) {
    let want: Vec<&str> = args.all("name");
    let machine = want.first().copied();
    let shots = facts::shots(machine);
    if shots.is_empty() {
        match machine {
            Some(m) => println!("no shots for `{m}` on the facts path"),
            None => no_corpus("experiment"),
        }
        return;
    }
    //: 第二个名字点一发炮 → 打全
    if let (Some(m), Some(s)) = (machine, want.get(1)) {
        let Some(one) = shots.iter().find(|x| x.shot == *s) else {
            die(&format!("no shot {s} for {m} on the facts path"));
        };
        println!("{}/{}   ({})", one.machine, one.shot, one.root.display());
        if let Some(mf) = one.manifest() {
            println!("  manifest  {}", mf.display());
        }
        let slices = one.slices();
        println!("  slices    {}", slices.len());
        for (t, p) in &slices {
            println!("    t = {t:<8} {}", p.file_name().and_then(|x| x.to_str()).unwrap_or(""));
        }
        return;
    }
    if as_json(args) {
        print_json(&list(
            shots
                .iter()
                .map(|s| {
                    map(vec![
                        ("machine", s.machine.clone().into()),
                        ("shot", s.shot.clone().into()),
                        ("slices", Node::Int(s.slices().len() as i64)),
                        ("root", s.root.display().to_string().into()),
                    ])
                })
                .collect(),
        ));
        return;
    }
    println!("{} {} {} {}", pad("machine", 10), pad("shot", 12), pad("slices", 8), "from");
    for s in &shots {
        println!(
            "{} {} {} {}",
            pad(&s.machine, 10),
            pad(&s.shot, 12),
            pad(&s.slices().len().to_string(), 8),
            s.root.display()
        );
    }
    println!("\n{} shots; `fy list experiments <machine> <shot>` prints the slice table", shots.len());
}

// ───────────────────────────── scenarios ─────────────────────────────

fn scenarios(args: &Args) {
    let want: Vec<&str> = args.all("name");
    let line = args.flag("line");
    let cat = corpus::catalogue();
    if cat.scenarios.is_empty() {
        die("no scenario catalogue — the built-in one did not parse, and no corpus root supplies one");
    }
    let codes = door(args);

    if want.is_empty() {
        let rows: Vec<&corpus::ScenarioRow> = match line {
            Some(l) => {
                if cat.line(l).is_none() {
                    die(&format!("no line `{l}`; they are {}", cat.line_names().join(", ")));
                }
                cat.of_line(l)
            }
            None => cat.scenarios.iter().collect(),
        };
        if as_json(args) {
            print_json(&list(
                rows.iter()
                    .map(|s| {
                        let live = codes.as_ref().map(|c| c.iter().any(|x| *x == s.code));
                        map(vec![
                            ("name", s.name.clone().into()),
                            ("lines", list(s.lines.iter().map(|l| l.clone().into()).collect())),
                            ("template", Node::Bool(s.has_template)),
                            ("code", s.code.clone().into()),
                            ("parameters", Node::Int(s.parameters as i64)),
                            ("runnable_declared", Node::Bool(s.runnable)),
                            ("runnable_kernel", live.map(Node::Bool).unwrap_or(Node::Null)),
                            ("reason", s.reason.clone().into()),
                        ])
                    })
                    .collect(),
            ));
            return;
        }
        println!("{} {} {} {:>5}  {}", pad("scenario", 16), pad("line", 14), pad("code", 22), "par", "today");
        for s in &rows {
            let today = verdict(s, codes.as_deref());
            println!(
                "{} {} {} {:>5}  {}",
                pad(&s.name, 16),
                pad(&s.lines.join(","), 14),
                pad(if s.code.is_empty() { "—" } else { &s.code }, 22),
                if s.parameters == 0 { "—".to_string() } else { s.parameters.to_string() },
                today
            );
        }
        //: ★只有**没有模板**的那些要逐条说理由；门认不认已经写在 today 一列里，
        //: 逐条重复同一句话只是把表推下屏幕。
        let mut said = false;
        for s in rows.iter().filter(|s| !s.has_template && !s.reason.is_empty()) {
            if !said {
                println!("\nno template, and why (FYL-DESIGN-17 E-8):");
                said = true;
            }
            println!("  {:<14} {}", s.name, s.reason);
        }
        if codes.is_none() {
            println!("\n(no kernel loaded, so `today` is what the catalogue declares, not what the door answers)");
        }
        return;
    }

    for name in want {
        let Some(t) = corpus::template(name) else {
            match cat.scenario(name) {
                Some(row) => die(&format!("`{name}` has no template: {}", row.reason)),
                None => {
                    let names = corpus::template_names();
                    let near = corpus::nearest(name, &names, 3);
                    let hint = if near.is_empty() { String::new() } else { format!("; did you mean {}?", near.join(", ")) };
                    die(&format!("no scenario `{name}`{hint}"));
                }
            }
        };
        let row = cat.scenario(name);
        println!("{}  —  {}", t.name, t.title);
        println!("  code      {}", t.code);
        println!("  lines     {}", t.lines.join(", "));
        println!("  template  {}{}", t.origin, if t.origin == Origin::Embedded { "" } else { "  (overrides the built-in one)" });
        if let Some(r) = row {
            println!("  today     {}", verdict(r, codes.as_deref()));
            if !r.reason.is_empty() {
                println!("            {}", r.reason);
            }
        }
        if !t.common.is_empty() {
            println!("  common    {}", t.common.join(", "));
        }
        if !t.time.is_empty() {
            println!("  time      {} (a point, a window or a list — this scenario takes a {})", t.time, t.time);
        }
        if !t.ports.is_empty() {
            println!("\n  ports:");
            for p in &t.ports {
                let mut what = Vec::new();
                if p.primary {
                    what.push("primary (--input binds it)".to_string());
                }
                if p.optional {
                    what.push("optional".to_string());
                }
                if !p.requires.is_empty() {
                    what.push(format!("needs the device {}", p.requires));
                }
                if !p.ids.is_empty() {
                    what.push(format!("IDS {}", p.ids.join(", ")));
                }
                println!("    {:<14} {}", p.name, what.join(" · "));
                if !p.note.is_empty() {
                    println!("    {:<14} {}", "", p.note);
                }
            }
        }
        if !t.switches.is_empty() {
            println!("\n  switches (one name, a group of values — FYL-DESIGN-17 E-18):");
            for s in &t.switches {
                let sets: Vec<String> =
                    s.sets.iter().map(|(k, v)| format!("{k}={}", json::to_string(v, false))).collect();
                println!("    --{:<20} {}", s.name, sets.join(" "));
            }
        }
        println!("\n  parameters ({}):", t.vocab.len());
        println!("    {:<16} {:<8} {}", "name", "type", "range / from");
        for p in &t.vocab {
            let mut extra = Vec::new();
            if !p.choices.is_empty() {
                extra.push(p.choices.join(" | "));
            }
            if let Some(lo) = p.min {
                extra.push(format!(">= {lo}"));
            }
            if let Some(hi) = p.max {
                extra.push(format!("<= {hi}"));
            }
            if let Some(d) = &p.from_device {
                extra.push(format!("default from the device document ({d})"));
            }
            if !p.note.is_empty() {
                extra.push(p.note.clone());
            }
            println!("    {:<16} {:<8} {}", p.name, p.kind.name(), extra.join("; "));
        }
        println!("\n  `-` and `_` are the same character in a name; write a value with `=`.");
    }
}

fn verdict(s: &corpus::ScenarioRow, codes: Option<&[String]>) -> String {
    if !s.has_template {
        return match &s.folded_into {
            Some(f) => format!("no template — part of `{f}`"),
            None => "no template".to_string(),
        };
    }
    match codes {
        Some(c) => {
            if c.iter().any(|x| *x == s.code) {
                "runs".to_string()
            } else {
                "the kernel door does not carry this code".to_string()
            }
        }
        None => {
            if s.runnable {
                "declared runnable".to_string()
            } else {
                "declared not runnable".to_string()
            }
        }
    }
}

// ───────────────────────────── presets ─────────────────────────────

fn presets(args: &Args) {
    let want: Vec<&str> = args.all("name");
    let line = args.flag("line");
    let scenario = args.flag("scenario");
    let cat = corpus::catalogue();
    let all = corpus::presets();
    if all.is_empty() {
        println!(
            "no presets on the case path — roots: {}",
            corpus::roots().iter().map(|r| r.display().to_string()).collect::<Vec<_>>().join(", ")
        );
        return;
    }
    if !want.is_empty() {
        for name in want {
            let Some(d) = all.iter().find(|d| d.name == name) else {
                let names: Vec<&str> = all.iter().map(|d| d.name.as_str()).collect();
                let near = corpus::nearest(name, &names, 3);
                let hint = if near.is_empty() { String::new() } else { format!("; did you mean {}?", near.join(", ")) };
                die(&format!("no preset `{name}`{hint}"));
            };
            println!("{}", json::to_string(&d.node, true));
        }
        return;
    }
    let rows: Vec<(&corpus::Doc, String, String)> = all
        .iter()
        .map(|d| {
            let m = d.node.as_map();
            let code = m
                .and_then(|x| x.get("prescribes_code"))
                .and_then(Node::as_map)
                .and_then(|c| c.get("id"))
                .and_then(Node::as_str)
                .unwrap_or("")
                .to_string();
            let device = m
                .and_then(|x| x.get("about_discharge"))
                .and_then(Node::as_map)
                .and_then(|a| a.get("performed_on"))
                .and_then(Node::as_map)
                .and_then(|p| p.get("title"))
                .and_then(Node::as_map)
                .and_then(|t| t.get("en"))
                .and_then(Node::as_str)
                .unwrap_or("")
                .to_string();
            (d, code, device)
        })
        .filter(|(_, code, _)| {
            scenario.map(|s| *code == format!("code/{s}")).unwrap_or(true)
        })
        .filter(|(_, code, _)| {
            let Some(l) = line else { return true };
            let name = code.strip_prefix("code/").unwrap_or("");
            cat.scenario(name).map(|r| r.lines.iter().any(|x| x == l)).unwrap_or(false)
        })
        .collect();
    if as_json(args) {
        print_json(&list(
            rows.iter()
                .map(|(d, code, dev)| {
                    map(vec![
                        ("name", d.name.clone().into()),
                        ("code", code.clone().into()),
                        ("device", dev.clone().into()),
                        ("root", d.origin.to_string().into()),
                    ])
                })
                .collect(),
        ));
        return;
    }
    println!("{} {} {} {}", pad("preset", 36), pad("code", 22), pad("device", 8), "from");
    for (d, code, dev) in &rows {
        println!(
            "{} {} {} {}",
            pad(&d.name, 36),
            pad(if code.is_empty() { "—" } else { code }, 22),
            pad(if dev.is_empty() { "—" } else { dev }, 8),
            d.origin
        );
    }
    println!("\n{} presets; `fy list presets <name>` prints one, `fy run <name>.jsonld` runs it", rows.len());
}

// ───────────────────────────── facts / kernel / lines ─────────────────────────────

fn no_corpus(domain: &str) {
    let roots = facts::roots();
    if roots.is_empty() {
        eprintln!(
            "fy list: the facts path is empty — pass --facts, set ${}, or run\n  \
             python3 tools/abox-to-facts.py --all  in a checkout",
            facts::FACTS_ENV
        );
    } else {
        eprintln!(
            "fy list: no `{domain}` entries in {}",
            roots.iter().map(|r| r.display().to_string()).collect::<Vec<_>>().join(", ")
        );
    }
}

/// 搜索路径的问答面（从前的 `data facts`，原样搬家）。
fn facts_face(args: &Args) {
    let roots = facts::roots();
    let domain = args.flag("domain").unwrap_or("");
    let built_in = facts::embedded_count();
    if args.has("roots") || domain.is_empty() {
        if roots.is_empty() && built_in == 0 {
            eprintln!(
                "fy list: facts 搜索路径上没有语料，这份二进制也没有内嵌的 —— 给 --facts，\n\
                 或设 ${}，或在检出里跑 python3 tools/abox-to-facts.py --all",
                facts::FACTS_ENV
            );
        }
        for (i, r) in roots.iter().enumerate() {
            println!("{}. {}", i + 1, r.display());
        }
        //: ★★自带的那一档也是一个「根」，只是它不在盘上：装置信息编在这份二进制里
        //: （2026-09-05 用户裁定）。**要打印出来**——不然一个发行版的读者看到一张空
        //: 路径表，却又能 `list devices`，只能猜那些机器是从哪来的。
        if built_in > 0 {
            println!("{}. {}   ({built_in} 条，编在这份二进制里)", roots.len() + 1, facts::BUNDLED_ROOT);
        }
        if args.has("roots") {
            return;
        }
        for d in facts::domains() {
            println!("   {d}: {} 条", facts::entries(&d).len());
        }
        //: ★两条搜索路径，两个问题；一条命令里都答了才省得再问一次。
        let cr = corpus::roots();
        println!("\ncase corpus (scenario templates and presets):");
        if cr.is_empty() {
            println!("   (none on the path; the templates built into this executable are still there)");
        }
        for (i, r) in cr.iter().enumerate() {
            println!("{}. {}", i + 1, r.display());
        }
        println!("   templates: {}, presets: {}", corpus::template_names().len(), corpus::presets().len());
        return;
    }
    let items = facts::entries(domain);
    if items.is_empty() {
        eprintln!("fy list: 域 {domain:?} 在搜索路径上没有条目");
        return;
    }
    for e in items {
        let rights = if e.rights_path().is_some() { "" } else { "  (无许可账)" };
        println!("{:<16} {}{}", e.ident, e.root.display(), rights);
    }
}

/// 内核完成什么（从前的 `case describe`）。
fn kernel(args: &Args) {
    match Kernel::load(args.flag("kernel").map(std::path::Path::new)) {
        Ok(k) => println!(
            "kernel: {}  (abi {})",
            k.path.display(),
            k.abi_version.map(|v| v.to_string()).unwrap_or_else(|| "?".into())
        ),
        Err(e) => println!("kernel: not loaded — {}", e.message.lines().next().unwrap_or("")),
    }
    println!("\ncodes the kernel completes (code/<code> · the corpus's own vocabulary):");
    if let Some(b) = fi::BLOCKS.iter().find(|b| b.name == "CASE_CODES") {
        for r in b.rows {
            println!("  code/{:<12} -> {:<12} [{}]  {}", r.key, r.shape, r.units, r.gloss);
        }
    }
    println!("\nraw entries (entry/<name> · the declared blocks, nothing converted):");
    for e in fi::ENTRIES {
        println!("  entry/{:<12} dims {:?}", e.name, e.dims);
        for (role, name) in [("params", e.params), ("input", e.input), ("out", e.out)] {
            if let Some(b) = fi::BLOCKS.iter().find(|b| b.name == name) {
                let rows: Vec<String> = b.rows.iter().map(|r| format!("{}[{}]", r.key, r.units)).collect();
                println!("    {role:<6} {}", rows.join(" "));
            }
        }
    }
    println!("\noutput documents (fyo path per kernel slot):");
    for t in fi::TABLES {
        if t.slots.is_empty() {
            continue;
        }
        println!("  {} ({}):", t.doc_type, t.name);
        for s in t.slots {
            println!("    {:<12} {} [{}]", s.key, s.path, s.units);
        }
    }
}

fn lines(args: &Args) {
    let cat = corpus::catalogue();
    if as_json(args) {
        print_json(&list(
            cat.lines
                .iter()
                .map(|l| {
                    map(vec![
                        ("name", l.name.clone().into()),
                        ("title", l.title.clone().into()),
                        ("default", l.default_scenario.clone().into()),
                        ("conops", l.conops.clone().into()),
                        ("scenarios", Node::Int(cat.of_line(&l.name).len() as i64)),
                    ])
                })
                .collect(),
        ));
        return;
    }
    println!("{} {} {} {:>9}  {}", pad("line", 10), pad("title", 16), pad("default", 16), "scenarios", "CONOPS");
    for l in &cat.lines {
        println!(
            "{} {} {} {:>9}  {}",
            pad(&l.name, 10),
            pad(&l.title, 16),
            pad(&l.default_scenario, 16),
            cat.of_line(&l.name).len(),
            l.conops
        );
    }
    println!("\n`fy run <line>` runs that line's default scenario; `fy list scenarios --line <line>` lists them.");
}

/// Run one `list` subcommand (`args.command == ["list", <sub>]`).
pub fn run(args: &Args) {
    //: a closed pipe ends a listing, it is not a panic (`| head`)
    unsafe { signal(13, 0) };
    super::data::apply_facts(args);
    let given = args.all("cases");
    if !given.is_empty() {
        corpus::use_roots(Some(corpus::parse_roots(given)));
    }
    for line in corpus::problems() {
        eprintln!("fy list: {line}");
    }
    match args.word(1) {
        "devices" => devices(args),
        "experiments" => experiments(args),
        "scenarios" => scenarios(args),
        "presets" => presets(args),
        "facts" => facts_face(args),
        "kernel" => kernel(args),
        "lines" => lines(args),
        other => die(&format!("unknown list subcommand {other:?}; --help has the usage")),
    }
}
