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

use super::{shown, tilde, BUILTIN};

/// `from` 那一格：这一条是哪个根供的。
///
/// ★★写**路径**，不写编号（用户裁定 2026-09-08）。编号要读者再去查一张图例，
/// 而「哪一个根」正是这一列存在的理由——查得到不等于说得出。
fn from_cell(root: &std::path::Path) -> String {
    shown(root)
}

/// 生效的搜索路径，写成 `$PATH` 的样子：冒号分隔，内置的那一档排在最前
/// （用户裁定 2026-09-08），其后是 `--facts` / `$FY_FACTS_PATH` 解析出来的那些根。
fn search_path(roots: &[std::path::PathBuf], built_in: bool) -> String {
    let mut parts: Vec<String> = Vec::new();
    if built_in || roots.iter().any(|r| shown(r) == BUILTIN) {
        parts.push(BUILTIN.to_string());
    }
    //: ★后面只列**命令行或环境变量解析出来的**那些根：检出的暂存语料已经由
    //: `<buildin>` 说了，再打一次它的路径就是同一个根说两遍。
    parts.extend(roots.iter().filter(|r| shown(r) != BUILTIN).map(|r| shown(r)));
    parts.join(":")
}

/// 这一条可以据以介绍自己的那份文档：先卡片，没有卡片就用清单。
///
/// ★★不写成「只读卡片」：fydoc 那侧的条目**只有清单**（`abox/device.jsonld`），
/// 于是那一版的介绍列对着挂了 fydoc 的检出整列打 `—`——有话可说而没说。
fn entry_doc(e: &facts::Entry) -> Option<Node> {
    if let Some(t) = e.read() {
        if let Ok(n) = crate::json::parse(&t).or_else(|_| crate::yaml::parse(&t)) {
            return Some(n);
        }
    }
    crate::io::read_node(&e.manifest_path()?).ok()
}

/// 一个数写成人读的短形（`1.75`，不是 `1.7500000000000002`）。
fn num(x: f64) -> String {
    let s = format!("{x:.4}");
    let s = s.trim_end_matches('0').trim_end_matches('.');
    if s.is_empty() { "0".to_string() } else { s.to_string() }
}

/// 这一条的**简短介绍**。
///
/// ★★取值只出自**文档自己**：先找全称一类的标注（`rdfs:label` / `dcterms:title` /
/// `fylite:full_name`），没有就用这台机器自己的几何与场。**不从散文里取**——
/// `abox/` 外是散文、内是数据（用户裁定 2026-09-04），而这条命令读的是数据；
/// 也不在这里写一张「east = Experimental Advanced Superconducting Tokamak」的
/// 名字表：那是把数据搬进代码，改一个名字要重编一次二进制，且这份表与 fydoc
/// 那侧的说法从此可以各说各话而不报错。
///
/// ★实测（2026-09-08）：十三台**一台也没有全称**，所以今天打出来的都是后一种。
/// 要全称，得先进 fydoc 的可编辑真源（`facts/device/<id>/provenance.yaml`）
/// 再生成 A-Box——那一步在数据那侧，不在这里。
fn describe(doc: &Node) -> String {
    let Some(m) = doc.as_map() else { return "—".to_string() };
    for k in ["rdfs:label", "dcterms:title", "fylite:full_name", "fyo:full_name"] {
        if let Some(v) = m.get(k).and_then(Node::as_str) {
            if !v.trim().is_empty() {
                return v.trim().to_string();
            }
        }
    }
    //: 装置清单（fydoc 形）：`device` 是那台机器的名字。
    let machine = m.get("machine").and_then(Node::as_map);
    let mut bits: Vec<String> = Vec::new();
    if let Some(r) = machine.and_then(|x| x.get("r_centre")).and_then(Node::as_f64) {
        bits.push(format!("R {} m", num(r)));
    }
    if let Some(b) = machine.and_then(|x| x.get("fylite:b0")).and_then(Node::as_f64) {
        bits.push(format!("B0 {} T", num(b)));
    }
    if !bits.is_empty() {
        return bits.join(" · ");
    }
    for k in ["device", "name", "_machine"] {
        if let Some(v) = m.get(k).and_then(Node::as_str) {
            if !v.trim().is_empty() {
                return v.trim().to_string();
            }
        }
    }
    "—".to_string()
}

/// 上游声明的许可，原样。★两种账的键不同名：本仓生成的 `rights.json` 记
/// `declared`，fydoc 那侧的 FAIR 件记 `license`——同一件事的两个写法，都读。
fn licence_raw(path: Option<&std::path::Path>) -> Option<String> {
    let node = crate::io::read_node(path?).ok()?;
    let m = node.as_map()?;
    for k in ["declared", "license", "licence", "dcterms:license"] {
        if let Some(v) = m.get(k).and_then(Node::as_str) {
            if !v.trim().is_empty() {
                return Some(v.trim().to_string());
            }
        }
    }
    None
}

/// 许可**类型**，给表用的短形。
///
/// ★★列里从前写 `yes` / `—`，答的是「有没有账」——而读者要问的是「我拿它能做
/// 什么」。这两问不同：一台 `NOT OPEN` 与一台按文献重述的机器都「有账」，
/// 而它们能做的事相反。
///
/// ★短形只是**排版**：它由下面这张小词表从声明原文压出来，原文一字不改地留在
/// `fy list devices <id>` 与 `--json` 里。压不出来的照原样截断——不猜。
fn licence_kind(raw: Option<&str>) -> String {
    let Some(raw) = raw else { return "—".to_string() };
    let low = raw.to_lowercase();
    if low.contains("not open") {
        "NOT OPEN".to_string()
    } else if low.contains("literature") {
        "literature".to_string()
    } else if low.contains("mixed") {
        "mixed".to_string()
    } else {
        let head = raw.split('—').next().unwrap_or(raw).trim();
        if columns(head) > 14 {
            format!("{}…", head.chars().take(13).collect::<String>())
        } else {
            head.to_string()
        }
    }
}

/// 这一条描述了哪些 IDS。
///
/// ★判据是**内置的 DD 表**，不是一张手写的「哪些键算 IDS」白名单：文档顶层还有
/// `provenance` / `machine` / `solver_dims` 一类的自有键，而 DD 的 82 个 IDS 名
/// 这份二进制自己就带着（`ids_tables::TABLES`）。手写白名单会在 DD 加一个 IDS
/// 的那天悄悄少列一项。
fn ids_of(e: &facts::Entry) -> Vec<String> {
    //: 装置清单（fydoc 形）：`providers` 的键就是 IDS 名，一条一台数据源。
    if let Some(m) = e.manifest_path() {
        if let Ok(node) = crate::io::read_node(&m) {
            if let Some(p) = node.as_map().and_then(|x| x.get("providers")).and_then(Node::as_map) {
                let mut v: Vec<String> = p.iter().map(|(k, _)| k.to_string()).collect();
                sort_ids(&mut v);
                return v;
            }
        }
    }
    let Some(text) = e.read() else { return Vec::new() };
    let Ok(node) = crate::json::parse(&text).or_else(|_| crate::yaml::parse(&text)) else {
        return Vec::new();
    };
    let Some(m) = node.as_map() else { return Vec::new() };
    let mut v: Vec<String> = m
        .iter()
        .map(|(k, _)| k.to_string())
        .filter(|k| crate::ids_tables::TABLES.iter().any(|(n, _)| n == k))
        .collect();
    sort_ids(&mut v);
    v
}

/// 常用的排前面，其余按名。
///
/// ★★表里只放得下前几个，所以**顺序就是选谁**。按字母排的那一版让 EAST 的头两个
/// 成了 `ec_launchers, ic_antennas`——两条加热天线——而把这台机器拿来做什么全看
/// 线圈、壁与磁测。这张次序表说的是「问『这台机器带什么』时先想知道哪几个」，
/// 不是重要性排序：其余的一个不少，都在 `fy list devices <id>` 与 `--json` 里。
const PRIMARY_IDS: [&str; 6] =
    ["pf_active", "wall", "magnetics", "tf", "interferometer", "polarimeter"];

fn sort_ids(v: &mut [String]) {
    v.sort_by_key(|k| {
        (PRIMARY_IDS.iter().position(|p| p == k).unwrap_or(PRIMARY_IDS.len()), k.clone())
    });
}

/// 装得下的前几个 + 省略号。
///
/// ★省略号后面带上**还有几个**：一个光秃秃的 `…` 只说「不止这些」，而「还有 3 个」
/// 与「还有 30 个」是两件事。
///
/// ★★按**列宽**裁，不按个数裁：按个数裁的那一版实测把 `from` 那一列挤出了对齐
/// （EAST 十个 IDS，名字又长），而一张对不齐的表正是这条命令的产物本身。
fn ids_cell(ids: &[String], width: usize) -> String {
    if ids.is_empty() {
        return "—".to_string();
    }
    for k in (1..=ids.len()).rev() {
        let cell = if k == ids.len() {
            ids.join(", ")
        } else {
            format!("{} …+{}", ids[..k].join(", "), ids.len() - k)
        };
        if columns(&cell) <= width {
            return cell;
        }
    }
    //: 一个都放不下：截第一个，仍把剩下几个说出来。
    let head: String = ids[0].chars().take(width.saturating_sub(6)).collect();
    format!("{head}… +{}", ids.len() - 1)
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
        //: ★★空也要答**同一种形**。`--json` 下打一句给人看的话，调用方拿到的是
        //: 一段解析不了的文本而退出码 0 —— 与「点名时忽略 --json」是同一个错。
        if as_json(args) {
            print_json(&list(Vec::new()));
            return;
        }
        no_corpus("device");
        return;
    }
    if want.is_empty() {
        if as_json(args) {
            print_json(&list(
                entries
                    .iter()
                    .map(|e| {
                        {
                            //: ★★人看的与机器读的**同一次读取、同一批字段**：分开写的
                            //: 那一刻，表里的省略号与 JSON 里的全表就开始各说各话。
                            //: JSON 不省略——它的读者不看宽度。
                            let raw = licence_raw(e.rights_path().as_deref());
                            let doc = entry_doc(e);
                            map(vec![
                                ("id", e.ident.clone().into()),
                                ("root", e.root.display().to_string().into()),
                                ("description", doc.as_ref().map(describe)
                                    .map(Node::from).unwrap_or(Node::Null)),
                                ("licence", raw.clone().map(Node::from).unwrap_or(Node::Null)),
                                ("licence_kind", licence_kind(raw.as_deref()).into()),
                                ("ids", list(ids_of(e).into_iter().map(Node::from).collect())),
                                ("manifest", Node::Bool(e.manifest_path().is_some())),
                                ("card", Node::Bool(e.has_document())),
                                ("rights", Node::Bool(e.rights_path().is_some())),
                            ])
                        }
                    })
                    .collect(),
            ));
            return;
        }
        //: ★`kind`（card / manifest）那一列已撤（用户裁定 2026-09-08）。这件事仍然
        //: 说得出——`fy list devices <id>` 的 `manifest` 一行与 `--json` 的 `manifest`
        //: 字段都在，撤掉的只是表上那一列。
        println!("{} {} {} {} {}",
                 pad("device id", 10), pad("description", 22), pad("licence", 11),
                 pad("ids", 38), "from");
        for e in &entries {
            let desc = entry_doc(e).as_ref().map(describe).unwrap_or_else(|| "—".to_string());
            let lic = licence_kind(licence_raw(e.rights_path().as_deref()).as_deref());
            println!("{} {} {} {} {}",
                     pad(&e.ident, 10), pad(&desc, 22), pad(&lic, 11),
                     pad(&ids_cell(&ids_of(e), 38), 38), from_cell(&e.root));
        }
        println!("\n{} devices; `fy list devices <id>` prints one in full", entries.len());
        println!("facts: {}", search_path(&facts::roots(), facts::embedded_count() > 0));
        return;
    }
    for id in want {
        let Some(e) = entries.iter().find(|e| e.ident == id) else {
            let known: Vec<&str> = entries.iter().map(|e| e.ident.as_str()).collect();
            let near = corpus::nearest(id, &known, 3);
            let hint = if near.is_empty() { String::new() } else { format!("; did you mean {}?", near.join(", ")) };
            die(&format!("no device `{id}` on the facts path{hint}"));
        };
        if as_json(args) {
            //: ★★`--json` 是**整个 `fy list` 的**参数（用法里就这么声明的）。
            //: 点名一台机器时它原先被静默忽略——声明了却不生效，比没有更坏：
            //: 脚本拿到的是给人看的排版，而退出码是 0。
            let raw = licence_raw(e.rights_path().as_deref());
            let doc = entry_doc(e);
            print_json(&map(vec![
                ("id", e.ident.clone().into()),
                ("root", e.root.display().to_string().into()),
                ("description", doc.as_ref().map(describe).map(Node::from).unwrap_or(Node::Null)),
                ("licence", raw.clone().map(Node::from).unwrap_or(Node::Null)),
                ("licence_kind", licence_kind(raw.as_deref()).into()),
                ("ids", list(ids_of(e).into_iter().map(Node::from).collect())),
                //: ★★点名形与清单形说的必须是**同一件事**：清单形的 `card` 答「这一条有没有
                //: 文档」（`has_document`，自带那一档的文档在二进制里，没有路径），而点名形
                //: 从前答的是**路径**——于是一条编进二进制的条目，清单形说 `card: true`、
                //: 点名形说 `card: null`。实测（2026-09-08，在没有盘上语料的检出里）：
                //: `test_naming_one_device_answers_json_too` 当场红。路径另开一个键。
                ("card", Node::Bool(e.has_document())),
                ("card_path", e.document.as_ref().map(|d| d.display().to_string().into()).unwrap_or(Node::Null)),
                ("rights", e.rights_path().map(|r| r.display().to_string().into()).unwrap_or(Node::Null)),
                ("manifest", e.manifest_path().map(|m| m.display().to_string().into()).unwrap_or(Node::Null)),
                ("described", manifest_json(e.manifest_path().as_deref())),
            ]));
            continue;
        }
        //: ★这里路径**该**出现，而且是完整的：点名一台机器问的就是「去哪儿看」，
        //: 而它只印一次，不是十三行重复同一段目录。`~` 只是收掉家目录那一截。
        println!("{}   ({})", e.ident, shown(&e.root));
        //: ★点名一台机器时，许可打的是**声明原文**，不是表里那个压出来的短形：
        //: 表要窄，这里不必；而裁定读的是原文。
        let doc = entry_doc(e);
        if let Some(d) = doc.as_ref().map(describe) {
            if d != "—" {
                println!("  about     {d}");
            }
        }
        let ids = ids_of(e);
        if !ids.is_empty() {
            println!("  ids       {} ({})", ids.join(", "), ids.len());
        }
        if let Some(d) = &e.document {
            println!("  card      {}", shown(d));
        }
        if let Some(r) = e.rights_path() {
            match licence_raw(Some(&r)) {
                Some(raw) => println!("  licence   {raw}"),
                None => println!("  licence   — (the ledger declares none)"),
            }
            println!("  ledger    {}", shown(&r));
        }
        match e.manifest_path() {
            None => println!(
                "  manifest  — (described by a card; a scenario that needs coil geometry and \n\
                 \x20           channel tables will refuse this device)"
            ),
            Some(m) => {
                println!("  manifest  {}", shown(&m));
                describe_manifest(&m);
            }
        }
        println!();
    }
}

/// [`describe_manifest`] 的机器可读一半 —— 同一份读取，两种排版。
///
/// ★两处**读同一个清单的同几个键**，所以它们放在一起：分开写的那一刻，
/// 人看到的与脚本拿到的就开始各说各话。
fn manifest_json(path: Option<&std::path::Path>) -> Node {
    let Some(path) = path else { return Node::Null };
    let Ok(node) = crate::io::read_node(path) else {
        return map(vec![("error", "the manifest did not parse".into())]);
    };
    let Some(m) = node.as_map() else { return Node::Null };
    let providers: Vec<Node> = m
        .get("providers")
        .and_then(Node::as_map)
        .map(|p| {
            p.iter()
                .map(|(ids, v)| {
                    map(vec![
                        ("ids", ids.to_string().into()),
                        ("default", v.as_map().and_then(|x| x.get("default")).cloned().unwrap_or(Node::Null)),
                        ("available", list(v.as_map()
                            .and_then(|x| x.get("available"))
                            .and_then(Node::as_map)
                            .map(|a| a.keys().map(|k| k.to_string().into()).collect())
                            .unwrap_or_default())),
                    ])
                })
                .collect()
        })
        .unwrap_or_default();
    map(vec![
        ("device", m.get("device").cloned().unwrap_or(Node::Null)),
        ("tbox", m.get("tbox").cloned().unwrap_or(Node::Null)),
        ("epochs", m.get("epochs").and_then(Node::as_list)
            .map(|e| Node::Int(e.len() as i64)).unwrap_or(Node::Null)),
        ("providers", list(providers)),
    ])
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
        if as_json(args) {
            print_json(&list(Vec::new()));
            return;
        }
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
        if as_json(args) {
            let slices: Vec<Node> = one.slices().iter()
                .map(|(t, p)| map(vec![
                    ("time", t.clone().into()),
                    ("file", p.file_name().and_then(|x| x.to_str()).unwrap_or("").into()),
                ]))
                .collect();
            print_json(&map(vec![
                ("machine", one.machine.clone().into()),
                ("shot", one.shot.clone().into()),
                ("root", one.root.display().to_string().into()),
                ("manifest", one.manifest().map(|m| m.display().to_string().into()).unwrap_or(Node::Null)),
                ("slices", list(slices)),
            ]));
            return;
        }
        println!("{}/{}   ({})", one.machine, one.shot, shown(&one.root));
        if let Some(mf) = one.manifest() {
            println!("  manifest  {}", shown(&mf));
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
            from_cell(&s.root)
        );
    }
    println!("\n{} shots; `fy list experiments <machine> <shot>` prints the slice table", shots.len());
    println!("facts: {}", search_path(&facts::roots(), facts::embedded_count() > 0));
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
        if as_json(args) {
            print_json(&template_json(&t, row, codes.as_deref()));
            continue;
        }
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

/// 一个场景模板的机器可读面 —— 与它上面那段人读的排版**同一批字段**。
fn template_json(t: &corpus::Template, row: Option<&corpus::ScenarioRow>,
                 codes: Option<&[String]>) -> Node {
    let ports: Vec<Node> = t.ports.iter()
        .map(|p| map(vec![
            ("name", p.name.clone().into()),
            ("primary", Node::Bool(p.primary)),
            ("optional", Node::Bool(p.optional)),
            ("requires", p.requires.clone().into()),
            ("ids", list(p.ids.iter().map(|i| i.clone().into()).collect())),
            ("note", p.note.clone().into()),
        ]))
        .collect();
    let switches: Vec<Node> = t.switches.iter()
        .map(|s| map(vec![
            ("name", s.name.clone().into()),
            ("sets", map(s.sets.iter().map(|(k, v)| (k.as_str(), v.clone())).collect())),
        ]))
        .collect();
    let parameters: Vec<Node> = t.vocab.iter()
        .map(|p| map(vec![
            ("name", p.name.clone().into()),
            ("key", p.key.clone().into()),
            ("kind", p.kind.name().into()),   //: 与人读那一栏同一个拼法
            ("choices", list(p.choices.iter().map(|c| c.clone().into()).collect())),
            ("min", p.min.map(Node::Float).unwrap_or(Node::Null)),
            ("max", p.max.map(Node::Float).unwrap_or(Node::Null)),
            ("from_device", p.from_device.clone().map(Node::from).unwrap_or(Node::Null)),
            ("note", p.note.clone().into()),
        ]))
        .collect();
    map(vec![
        ("name", t.name.clone().into()),
        ("title", t.title.clone().into()),
        ("code", t.code.clone().into()),
        ("lines", list(t.lines.iter().map(|l| l.clone().into()).collect())),
        ("template", t.origin.to_string().into()),
        ("path", t.path.as_ref().map(|p| p.display().to_string().into()).unwrap_or(Node::Null)),
        ("common", list(t.common.iter().map(|c| c.clone().into()).collect())),
        ("time", t.time.clone().into()),
        ("today", row.map(|r| verdict(r, codes).into()).unwrap_or(Node::Null)),
        ("reason", row.map(|r| r.reason.clone().into()).unwrap_or(Node::Null)),
        ("ports", list(ports)),
        ("switches", list(switches)),
        ("parameters", list(parameters)),
    ])
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
            corpus::roots().iter().map(|r| shown(r)).collect::<Vec<_>>().join(", ")
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
    //: ★与装置表同一条：`from` 写路径。案例语料走的是**另一条**搜索路径
    //: （`corpus::roots()`），所以底下那一行说的是它，不是 facts 那条。
    println!("{} {} {} {}", pad("preset", 36), pad("code", 22), pad("device", 8), "from");
    for (d, code, dev) in &rows {
        let from = match &d.origin {
            Origin::Root(p) => shown(p),
            Origin::Embedded => BUILTIN.to_string(),
        };
        println!(
            "{} {} {} {}",
            pad(&d.name, 36),
            pad(if code.is_empty() { "—" } else { code }, 22),
            pad(if dev.is_empty() { "—" } else { dev }, 8),
            from
        );
    }
    println!("\n{} presets; `fy list presets <name>` prints one, `fy run <name>.jsonld` runs it", rows.len());
    println!("cases: {}", search_path(&corpus::roots(), true));
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
            roots.iter().map(|r| shown(r)).collect::<Vec<_>>().join(", ")
        );
    }
}

/// 搜索路径的问答面（从前的 `data facts`，原样搬家）。
fn facts_face(args: &Args) {
    let roots = facts::roots();
    let domain = args.flag("domain").unwrap_or("");
    let built_in = facts::embedded_count();
    if as_json(args) {
        if !domain.is_empty() && !args.has("roots") {
            print_json(&list(facts::entries(domain).iter()
                .map(|e| map(vec![
                    ("id", e.ident.clone().into()),
                    ("root", e.root.display().to_string().into()),
                    ("rights", Node::Bool(e.rights_path().is_some())),
                ]))
                .collect()));
            return;
        }
        let domains: Vec<Node> = facts::domains().iter()
            .map(|d| map(vec![
                ("domain", d.clone().into()),
                ("entries", Node::Int(facts::entries(d).len() as i64)),
            ]))
            .collect();
        print_json(&map(vec![
            ("facts_roots", list(roots.iter().map(|r| r.display().to_string().into()).collect())),
            //: ★自带的那一档也是一个根，只是它不在盘上（2026-09-05 裁定）
            ("bundled", map(vec![
                ("root", facts::BUNDLED_ROOT.into()),
                ("entries", Node::Int(built_in as i64)),
            ])),
            ("domains", list(domains)),
            ("case_roots", list(corpus::roots().iter()
                .map(|r| r.display().to_string().into()).collect())),
            ("templates", Node::Int(corpus::template_names().len() as i64)),
            ("presets", Node::Int(corpus::presets().len() as i64)),
        ]));
        return;
    }
    if args.has("roots") || domain.is_empty() {
        if roots.is_empty() && built_in == 0 {
            eprintln!(
                "fy list: facts 搜索路径上没有语料，这份二进制也没有内嵌的 —— 给 --facts，\n\
                 或设 ${}，或在检出里跑 python3 tools/abox-to-facts.py --all",
                facts::FACTS_ENV
            );
        }
        for (i, r) in roots.iter().enumerate() {
            //: ★检出的暂存区与编进二进制的那一份**都写 `<buildin>`**（构建期路径不
            //: 出现在输出里，用户裁定 2026-09-08），所以这里要另说一句是哪一种——
            //: 否则两行一模一样，而它们是两份可以互不相同的字节。
            let note = if shown(r) == BUILTIN { "   (检出暂存区，盘上的那一份)" } else { "" };
            println!("{}. {}{note}", i + 1, shown(r));
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
            println!("{}. {}", i + 1, shown(r));
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
        println!("{:<16} {}{}", e.ident, shown(&e.root), rights);
    }
}

/// 内核完成什么（从前的 `case describe`）。
fn kernel(args: &Args) {
    if as_json(args) {
        let loaded = Kernel::load(args.flag("kernel").map(std::path::Path::new));
        let codes: Vec<Node> = fi::BLOCKS.iter().find(|b| b.name == "CASE_CODES")
            .map(|b| b.rows.iter()
                .map(|r| map(vec![
                    ("code", format!("code/{}", r.key).into()),
                    ("entry", r.shape.into()),
                    ("kind", r.units.into()),
                    ("gloss", r.gloss.into()),
                ]))
                .collect())
            .unwrap_or_default();
        let entries: Vec<Node> = fi::ENTRIES.iter()
            .map(|e| {
                let block = |name: &str| list(fi::BLOCKS.iter().find(|b| b.name == name)
                    .map(|b| b.rows.iter()
                        .map(|r| map(vec![("key", r.key.into()), ("units", r.units.into())]))
                        .collect())
                    .unwrap_or_default());
                map(vec![
                    ("entry", format!("entry/{}", e.name).into()),
                    ("dims", list(e.dims.iter().map(|d| (*d).into()).collect())),
                    ("params", block(e.params)),
                    ("input", block(e.input)),
                    ("out", block(e.out)),
                ])
            })
            .collect();
        let tables: Vec<Node> = fi::TABLES.iter()
            .filter(|t| !t.slots.is_empty())
            .map(|t| map(vec![
                ("table", t.name.into()),
                ("document", t.doc_type.into()),
                ("slots", list(t.slots.iter()
                    .map(|s| map(vec![
                        ("key", s.key.into()),
                        ("path", s.path.into()),
                        ("units", s.units.into()),
                    ]))
                    .collect())),
            ]))
            .collect();
        print_json(&map(vec![
            ("kernel", match &loaded {
                Ok(k) => map(vec![
                    ("loaded", Node::Bool(true)),
                    ("path", k.path.display().to_string().into()),
                    ("abi", k.abi_version.map(|v| Node::Int(v as i64)).unwrap_or(Node::Null)),
                ]),
                Err(e) => map(vec![
                    ("loaded", Node::Bool(false)),
                    ("reason", e.message.lines().next().unwrap_or("").into()),
                ]),
            }),
            ("codes", list(codes)),
            ("entries", list(entries)),
            ("tables", list(tables)),
        ]));
        return;
    }
    match Kernel::load(args.flag("kernel").map(std::path::Path::new)) {
        Ok(k) => println!(
            "kernel: {}  (abi {})",
            shown(&k.path),
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
