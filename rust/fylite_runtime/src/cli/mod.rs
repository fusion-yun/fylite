//! The command line of the Rust host — built from the SAME spec file the
//! Python console script builds its argparse parser from (FYL-DESIGN-15).
//!
//! `python/fylite/_cli.json` is included at compile time, so the single
//! executable and the Python package cannot disagree about a command, an
//! option or a help line: one file, three hosts.  What is host-specific is
//! said IN the file (`hosts` on a command or an argument), not in code.
//!
//! What this module does:
//!
//! * [`spec`] — parse the spec once; [`Spec`] is the typed view of it.
//! * [`parse`] — turn an argv into [`Args`] for one host, walking the
//!   command tree (`data convert …`), refusing an unknown option BY NAME,
//!   checking types, choices, required options and positional counts.
//! * [`usage`] — the help text, generated from the spec, one format for
//!   every command and every host.
//!
//! What it does not do: no dispatch.  The bodies (`data`, `run`, `list`, the
//! app server) match on [`Args::command`] themselves — the spec says what a
//! command TAKES, the host says what it DOES.
//!
//! ★★Two things here are NOT the usual argument parsing, and both are the
//! spec's doing rather than this module's (FYL-DESIGN-17):
//!
//! * **open parameters** (`open_parameters` on a command) — `run` carries a
//!   parameter table this file does not hold: it belongs to the scenario
//!   template, because a scenario is data.  So the tokens this parser does
//!   not recognise are COLLECTED ([`Args::open`]) instead of refused, and
//!   `run.rs` refuses them by name against the template it loaded.  A
//!   command without the declaration behaves exactly as before.
//! * **retired words** (`retired` at the top of the spec) — `case` folded
//!   into `run` and `data facts` into `list facts`; a retired word is
//!   refused BY NAME with the replacement, never silently forwarded.  Two
//!   words for one thing is what the fold was for.
//!
//! ★Hand-rolled on purpose.  The crate has no dependencies beyond the two
//! optional C-library bindings and it stays that way; a spec of this size
//! needs ~400 lines, and those lines are the contract made executable.

use crate::document::Node;
use crate::json;
use std::sync::OnceLock;

pub mod data;
pub mod list;
pub mod run;

/// The spec, verbatim, from the one place it lives.
/// 改过名的选项：报「不认识」之前先看看它是不是搬了家。
///
/// ★只放**真的改过名**的：把它当同义词表用，就等于两个名字都还在，而那正是
/// 改名要消掉的东西——旧名此后只出现在这一句错误话术里。
const RENAMED: &[(&str, &str)] = &[
    //: 2026-09-04：取值主用法是 facts 上的装置名，`--machine` 读起来像在要一个文件。
    ("--machine", "--device"),
];

pub const SPEC_TEXT: &str = include_str!("../../../../python/fylite/_cli.json");

/// The host this executable is (`hosts` in the spec).
pub const HOST: &str = "rust";

/// What a flag does with its value.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action {
    Store,
    StoreTrue,
    StoreFalse,
    Append,
}

/// How many values an argument takes.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Nargs {
    One,
    Optional,
    Plus,
    Star,
    N(usize),
}

/// The scalar type a value is checked against.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Str,
    Int,
    Float,
}

/// One argument (a positional or a flag) as the spec declares it.
#[derive(Clone, Debug)]
pub struct ArgDef {
    /// `["-o", "--out"]` or `["input"]`.
    pub flags: Vec<String>,
    /// The name a body reads it back by: the long flag without dashes, or
    /// the positional's name.
    pub name: String,
    pub positional: bool,
    pub action: Action,
    pub nargs: Nargs,
    pub kind: Kind,
    pub choices: Vec<String>,
    pub help: String,
    pub metavar: String,
    pub required: bool,
    pub hosts: Option<Vec<String>>,
    /// The browser launch parameter this option writes into the URL
    /// (`hosts.app.params` in the spec).
    pub app_param: Option<String>,
}

/// One command, possibly a group of subcommands.
#[derive(Clone, Debug)]
pub struct CommandDef {
    pub name: String,
    pub help: String,
    pub args: Vec<ArgDef>,
    pub commands: Vec<CommandDef>,
    pub hosts: Option<Vec<String>>,
    /// The command takes a parameter table this file does not declare
    /// (`open_parameters` in the spec; `run` says `"scenario"`).  Unknown
    /// `--k=v` / `--k` / `--no-k` / `k=v` tokens go to [`Args::open`]
    /// instead of being refused here.
    pub open_parameters: Option<String>,
}

/// How an open parameter was written — the spelling decides the value when
/// none was given, and it is what an error message quotes back.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Spelling {
    /// `k=v`
    Bare,
    /// `--k=v` or `--k`
    Flag,
    /// `--no-k`
    NoFlag,
}

/// One collected open parameter, in the order it was written.
#[derive(Clone, Debug)]
pub struct OpenArg {
    /// The name as written, dashes and all (`only-magnetic`).
    pub key: String,
    /// The literal after `=`; `None` for `--k` / `--no-k`.
    pub value: Option<String>,
    pub spelling: Spelling,
}

impl OpenArg {
    /// The value a template sees: the literal, or the boolean the spelling
    /// stands for (`--k` = true, `--no-k` = false).
    pub fn literal(&self) -> &str {
        match (&self.value, self.spelling) {
            (Some(v), _) => v,
            (None, Spelling::NoFlag) => "false",
            (None, _) => "true",
        }
    }

    /// How it was written, for an error message.
    pub fn as_written(&self) -> String {
        match (self.spelling, &self.value) {
            (Spelling::Bare, Some(v)) => format!("{}={v}", self.key),
            (Spelling::Bare, None) => self.key.clone(),
            (Spelling::Flag, Some(v)) => format!("--{}={v}", self.key),
            (Spelling::Flag, None) => format!("--{}", self.key),
            (Spelling::NoFlag, _) => format!("--no-{}", self.key),
        }
    }
}

/// A browser launch parameter (`hosts.app.params`).
#[derive(Clone, Debug)]
pub struct AppParam {
    pub name: String,
    /// `query` (a `?name=` pair), `path` (which page).
    pub carrier: String,
    pub choices: Vec<String>,
    pub help: String,
}

/// The typed spec.
#[derive(Debug)]
pub struct Spec {
    pub prog: String,
    pub description: String,
    pub commands: Vec<CommandDef>,
    /// The command run when the argv names none (`hosts.rust.default_command`).
    pub default_command: Option<String>,
    pub app_params: Vec<AppParam>,
    /// Retired command words and where each went (`retired` in the spec),
    /// longest key first so `case run` is found before `case`.
    pub retired: Vec<(String, String)>,
}

/// The parsed command line.
#[derive(Debug, Default)]
pub struct Args {
    /// The command words: `["data", "convert"]`.
    pub command: Vec<String>,
    /// Every positional value, in order, after the command words.
    pub positional: Vec<String>,
    /// The tokens this file does not declare, for a command that says it
    /// takes a parameter table of its own (`open_parameters`).
    pub open: Vec<OpenArg>,
    values: Vec<(String, Option<String>)>,
}

impl Args {
    /// The last value given for `name` (a flag's long name without dashes,
    /// or a positional's name).
    pub fn flag(&self, name: &str) -> Option<&str> {
        self.values.iter().rev().find(|(n, _)| n == name).and_then(|(_, v)| v.as_deref())
    }

    /// Whether `name` was given at all (a boolean flag, or any valued one).
    pub fn has(&self, name: &str) -> bool {
        self.values.iter().any(|(n, _)| n == name)
    }

    /// Every value given for `name`, in order (`--set k=v --set k=v`).
    pub fn all(&self, name: &str) -> Vec<&str> {
        self.values.iter().filter(|(n, _)| n == name).filter_map(|(_, v)| v.as_deref()).collect()
    }

    /// The subcommand word at `depth` (0 = the top-level command).
    pub fn word(&self, depth: usize) -> &str {
        self.command.get(depth).map(String::as_str).unwrap_or("")
    }
}

/// What a parse produced.
#[derive(Debug)]
pub enum Parsed {
    Run(Args),
    /// `-h` / `--help` somewhere: the usage text to print, exit 0.
    Help(String),
    /// A refusal, by name: the message to print, exit 2.
    Error(String),
}

fn s(n: Option<&Node>) -> String {
    n.and_then(Node::as_str).unwrap_or("").to_string()
}

/// The strings of a JSON array.  ★The crate's parser normalises a
/// homogeneous list of strings into `Node::Array` (a string tensor) and
/// keeps a mixed or nested one as `Node::List`; a spec reader has to take
/// both spellings, so this is the one place that does.
fn str_items(n: &Node) -> Vec<String> {
    match n {
        Node::List(l) => l.iter().filter_map(Node::as_str).map(str::to_string).collect(),
        Node::Array(a) => a.as_str().map(|s| s.to_vec()).unwrap_or_default(),
        Node::Str(s) => vec![s.clone()],
        _ => Vec::new(),
    }
}

fn strs(n: Option<&Node>) -> Vec<String> {
    n.map(str_items).unwrap_or_default()
}

fn hosts_of(n: Option<&Node>) -> Option<Vec<String>> {
    n.map(str_items)
}

fn carried(hosts: &Option<Vec<String>>, host: &str) -> bool {
    match hosts {
        None => true,
        Some(h) => h.iter().any(|x| x == host),
    }
}

fn arg_def(n: &Node) -> ArgDef {
    let m = n.as_map().expect("an argument is a map");
    let flags = strs(m.get("flags"));
    let positional = flags.first().map(|f| !f.starts_with('-')).unwrap_or(true);
    let name = if positional {
        flags.first().cloned().unwrap_or_default()
    } else {
        flags
            .iter()
            .find(|f| f.starts_with("--"))
            .or(flags.first())
            .map(|f| f.trim_start_matches('-').to_string())
            .unwrap_or_default()
    };
    let action = match m.get("action").and_then(Node::as_str) {
        Some("store_true") => Action::StoreTrue,
        Some("store_false") => Action::StoreFalse,
        Some("append") => Action::Append,
        _ => Action::Store,
    };
    let nargs = match m.get("nargs") {
        Some(Node::Str(x)) if x == "?" => Nargs::Optional,
        Some(Node::Str(x)) if x == "+" => Nargs::Plus,
        Some(Node::Str(x)) if x == "*" => Nargs::Star,
        Some(Node::Int(k)) => Nargs::N(*k as usize),
        Some(Node::Float(k)) => Nargs::N(*k as usize),
        _ => Nargs::One,
    };
    let kind = match m.get("type").and_then(Node::as_str) {
        Some("int") => Kind::Int,
        Some("float") => Kind::Float,
        _ => Kind::Str,
    };
    let metavar = m.get("metavar").map(|v| str_items(v).join(" ")).unwrap_or_default();
    ArgDef {
        name,
        positional,
        action,
        nargs,
        kind,
        choices: strs(m.get("choices")),
        help: s(m.get("help")),
        metavar,
        required: matches!(m.get("required"), Some(Node::Bool(true))),
        hosts: hosts_of(m.get("hosts")),
        app_param: m.get("app_param").and_then(Node::as_str).map(str::to_string),
        flags,
    }
}

fn command_def(n: &Node) -> CommandDef {
    let m = n.as_map().expect("a command is a map");
    CommandDef {
        name: s(m.get("name")),
        help: s(m.get("help")),
        args: m.get("args").and_then(Node::as_list).map(|l| l.iter().map(arg_def).collect()).unwrap_or_default(),
        commands: m.get("commands").and_then(Node::as_list).map(|l| l.iter().map(command_def).collect()).unwrap_or_default(),
        hosts: hosts_of(m.get("hosts")),
        open_parameters: m.get("open_parameters").and_then(Node::as_str).map(str::to_string),
    }
}

/// Parse the spec text into its typed view.
pub fn parse_spec(text: &str) -> Result<Spec, String> {
    let root = json::parse(text).map_err(|e| format!("_cli.json: {e}"))?;
    let m = root.as_map().ok_or("_cli.json: not an object")?;
    let hosts = m.get("hosts").and_then(Node::as_map);
    let rust = hosts.and_then(|h| h.get(HOST)).and_then(Node::as_map);
    let app = hosts.and_then(|h| h.get("app")).and_then(Node::as_map);
    let app_params = app
        .and_then(|a| a.get("params"))
        .and_then(Node::as_list)
        .map(|l| {
            l.iter()
                .filter_map(Node::as_map)
                .map(|p| AppParam {
                    name: s(p.get("name")),
                    carrier: s(p.get("carrier")),
                    choices: strs(p.get("choices")),
                    help: s(p.get("help")),
                })
                .collect()
        })
        .unwrap_or_default();
    Ok(Spec {
        prog: rust.map(|r| s(r.get("exe"))).filter(|x| !x.is_empty()).unwrap_or_else(|| s(m.get("prog"))),
        description: s(m.get("description")),
        commands: m.get("commands").and_then(Node::as_list).map(|l| l.iter().map(command_def).collect()).unwrap_or_default(),
        default_command: rust.and_then(|r| r.get("default_command")).and_then(Node::as_str).map(str::to_string),
        app_params,
        retired: {
            let mut v: Vec<(String, String)> = m
                .get("retired")
                .and_then(Node::as_map)
                .map(|r| r.iter().filter_map(|(k, x)| x.as_str().map(|s| (k.to_string(), s.to_string()))).collect())
                .unwrap_or_default();
            //: longest first: `case run` must be found before `case`
            v.sort_by(|a, b| b.0.split_whitespace().count().cmp(&a.0.split_whitespace().count()));
            v
        },
    })
}

/// The spec, parsed once for the process.
pub fn spec() -> &'static Spec {
    static SPEC: OnceLock<Spec> = OnceLock::new();
    SPEC.get_or_init(|| parse_spec(SPEC_TEXT).unwrap_or_else(|e| panic!("{e}")))
}

impl Spec {
    /// The commands `host` carries, top level.
    pub fn commands_for(&self, host: &str) -> Vec<&CommandDef> {
        self.commands.iter().filter(|c| carried(&c.hosts, host)).collect()
    }

    /// Where a retired word went, given the words the argv opens with.
    ///
    /// ★Longest match: `fy case run x` is answered by the `case run` row,
    /// not by the `case` one — the reader is holding a whole command line,
    /// and the useful reply names the whole replacement.
    pub fn retired_hint(&self, words: &[&str]) -> Option<(&str, &str)> {
        self.retired
            .iter()
            .find(|(k, _)| {
                let ks: Vec<&str> = k.split_whitespace().collect();
                ks.len() <= words.len() && ks.iter().zip(words).all(|(a, b)| a == b)
            })
            .map(|(k, v)| (k.as_str(), v.as_str()))
    }

    /// Resolve a command path (`["data", "convert"]`) for `host`.
    pub fn command(&self, host: &str, path: &[&str]) -> Option<Vec<&CommandDef>> {
        let mut out = Vec::new();
        let mut level = &self.commands;
        for word in path {
            let c = level.iter().find(|c| c.name == *word && carried(&c.hosts, host))?;
            out.push(c);
            level = &c.commands;
        }
        Some(out)
    }
}

impl CommandDef {
    fn args_for(&self, host: &str) -> Vec<&ArgDef> {
        self.args.iter().filter(|a| carried(&a.hosts, host)).collect()
    }
}

fn synopsis_of(a: &ArgDef) -> String {
    let meta = if !a.metavar.is_empty() {
        a.metavar.clone()
    } else if !a.choices.is_empty() {
        a.choices.join("|")
    } else {
        a.name.to_ascii_uppercase().replace('-', "_")
    };
    if a.positional {
        let one = format!("<{}>", a.name);
        return match a.nargs {
            Nargs::One => one,
            Nargs::Optional => format!("[{one}]"),
            Nargs::Plus => format!("{one}..."),
            Nargs::Star => format!("[{one}...]"),
            Nargs::N(k) => vec![one; k].join(" "),
        };
    }
    let flag = a.flags.iter().find(|f| f.starts_with("--")).or(a.flags.first()).cloned().unwrap_or_default();
    let body = match a.action {
        Action::StoreTrue | Action::StoreFalse => flag,
        Action::Append => format!("{flag} {meta}]..."),
        Action::Store => match a.nargs {
            Nargs::Optional => format!("{flag} [{meta}]"),
            Nargs::N(k) => format!("{flag} {}", vec![meta; k].join(" ")),
            _ => format!("{flag} {meta}"),
        },
    };
    if a.action == Action::Append {
        format!("[{body}")
    } else if a.required {
        body
    } else {
        format!("[{body}]")
    }
}

/// The usage text for a command path (empty = the top level), for `host`,
/// under the program name `prog`.
pub fn usage(spec: &Spec, host: &str, prog: &str, path: &[&str]) -> String {
    let mut out = String::new();
    let chain = match spec.command(host, path) {
        Some(c) => c,
        None => return format!("{prog}: no such command {}", path.join(" ")),
    };
    let words = if path.is_empty() { String::new() } else { format!(" {}", path.join(" ")) };
    let last = chain.last().copied();
    let is_group = last.map(|c| !c.commands.is_empty()).unwrap_or(true);
    // synopsis
    let mut syn = format!("{prog}{words}");
    if is_group {
        syn.push_str(" <command> [...]");
    }
    if let Some(c) = last {
        for a in c.args_for(host) {
            syn.push(' ');
            syn.push_str(&synopsis_of(a));
        }
        if c.open_parameters.is_some() {
            syn.push_str(" [key=value...]");
        }
    }
    out.push_str(&syn);
    out.push('\n');
    let blurb = last.map(|c| c.help.clone()).unwrap_or_else(|| spec.description.clone());
    if !blurb.is_empty() {
        out.push_str("\n  ");
        out.push_str(&blurb);
        out.push('\n');
    }
    if is_group {
        let list: Vec<&CommandDef> = match last {
            Some(c) => c.commands.iter().filter(|x| carried(&x.hosts, host)).collect(),
            None => spec.commands_for(host),
        };
        out.push_str("\ncommands:\n");
        let w = list.iter().map(|c| c.name.len()).max().unwrap_or(8).max(8);
        for c in list {
            out.push_str(&format!("  {:<w$}  {}\n", c.name, c.help, w = w));
        }
        if path.is_empty() {
            if let Some(d) = &spec.default_command {
                out.push_str(&format!("\n  With no command, `{prog}` runs `{d}`.\n"));
            }
        }
    }
    if let Some(c) = last {
        let args = c.args_for(host);
        if !args.is_empty() {
            out.push_str("\narguments:\n");
            let labels: Vec<String> = args
                .iter()
                .map(|a| {
                    if a.positional {
                        format!("<{}>", a.name)
                    } else {
                        let meta = if a.action == Action::StoreTrue || a.action == Action::StoreFalse {
                            String::new()
                        } else if !a.metavar.is_empty() {
                            format!(" {}", a.metavar)
                        } else if !a.choices.is_empty() {
                            format!(" {}", a.choices.join("|"))
                        } else {
                            format!(" {}", a.name.to_ascii_uppercase().replace('-', "_"))
                        };
                        format!("{}{}", a.flags.join(", "), meta)
                    }
                })
                .collect();
            let w = labels.iter().map(String::len).max().unwrap_or(10).min(32);
            for (a, l) in args.iter().zip(labels) {
                let mut help = a.help.clone();
                if !a.choices.is_empty() && a.metavar.is_empty() {
                    help = format!("{help} ({})", a.choices.join("|"));
                }
                if a.required {
                    help = format!("{help} [required]");
                }
                if l.len() > w {
                    out.push_str(&format!("  {l}\n  {:<w$}  {help}\n", "", w = w));
                } else {
                    out.push_str(&format!("  {:<w$}  {help}\n", l, w = w));
                }
            }
        }
    }
    if let Some(kind) = last.and_then(|c| c.open_parameters.as_deref()) {
        out.push_str(&format!(
            "\n{kind} parameters:\n  \
             Anything else written `key=value` — equivalently `--key=value`, `--key` (true) or\n  \
             `--no-key` (false) — is a parameter of the {kind} itself.  The names, types and\n  \
             defaults are the {kind} template's, not this file's: `{prog} list scenarios <name>`\n  \
             prints the table.  `-` and `_` are the same character in a name; `--key value`\n  \
             (a space instead of `=`) is not a parameter.\n"
        ));
    }
    out.push_str("\n  -h, --help  show this usage\n");
    out
}

/// A name a template could plausibly declare: a letter, then letters,
/// digits, `_`, `-` or `.` (`turb-nky`, `provider.magnetics`).
fn open_key_ok(k: &str) -> bool {
    !k.is_empty()
        && k.starts_with(|c: char| c.is_ascii_alphabetic())
        && k.chars().all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-' || c == '.')
}

/// `k=v` written without dashes, on a command that takes a parameter table.
fn open_bare(tok: &str) -> Option<OpenArg> {
    let (k, v) = tok.split_once('=')?;
    open_key_ok(k).then(|| OpenArg { key: k.to_string(), value: Some(v.to_string()), spelling: Spelling::Bare })
}

/// `--k=v`, `--k`, `--no-k` — the same parameter, three spellings (E-12).
fn open_flag(name: &str, inline: Option<String>) -> Option<OpenArg> {
    let bare = name.strip_prefix("--")?;
    if let Some(k) = bare.strip_prefix("no-") {
        //: `--no-k` IS the value `false`; carrying another one is a mistake
        //: worth saying out loud rather than resolving silently.
        if inline.is_some() || !open_key_ok(k) {
            return None;
        }
        return Some(OpenArg { key: k.to_string(), value: None, spelling: Spelling::NoFlag });
    }
    open_key_ok(bare).then(|| OpenArg { key: bare.to_string(), value: inline, spelling: Spelling::Flag })
}

fn check_value(a: &ArgDef, v: &str) -> Result<(), String> {
    match a.kind {
        Kind::Int => {
            v.parse::<i64>().map_err(|_| format!("{} wants an integer, not {v:?}", a.flags.join("/")))?;
        }
        Kind::Float => {
            v.parse::<f64>().map_err(|_| format!("{} wants a number, not {v:?}", a.flags.join("/")))?;
        }
        Kind::Str => {}
    }
    if !a.choices.is_empty() && !a.choices.iter().any(|c| c == v) {
        return Err(format!("{} takes one of {}, not {v:?}", a.flags.join("/"), a.choices.join("|")));
    }
    Ok(())
}

/// Parse `argv` (without the program name) for `host`.  `prog` is only
/// used in messages and usage.
pub fn parse(spec: &Spec, host: &str, prog: &str, argv: &[String]) -> Parsed {
    let mut i = 0;
    let mut chain: Vec<&CommandDef> = Vec::new();
    let mut path: Vec<String> = Vec::new();
    let top_help = |p: &[String]| {
        let refs: Vec<&str> = p.iter().map(String::as_str).collect();
        Parsed::Help(usage(spec, host, prog, &refs))
    };
    // top level: a command word, `--help`, or the default command
    let first = argv.first().map(String::as_str);
    let mut level = &spec.commands;
    match first {
        Some("-h") | Some("--help") => return top_help(&[]),
        Some(w) if !w.starts_with('-') => {
            if let Some(c) = level.iter().find(|c| c.name == w && carried(&c.hosts, host)) {
                chain.push(c);
                path.push(w.to_string());
                level = &c.commands;
                i = 1;
            } else {
                //: ★★a word that USED to be a command is not an unknown word:
                //: the reader has a command line that worked last month, and
                //: what they need is the replacement, not a pointer at --help.
                let words: Vec<&str> = argv.iter().map(String::as_str).collect();
                if let Some((old, new)) = spec.retired_hint(&words) {
                    return Parsed::Error(format!(
                        "{prog}: `{old}` is retired — use `{prog} {new}`"
                    ));
                }
                return Parsed::Error(format!(
                    "{prog}: unknown command {w:?}; --help lists the commands"
                ));
            }
        }
        _ => match &spec.default_command {
            Some(d) => {
                let c = match level.iter().find(|c| &c.name == d) {
                    Some(c) => c,
                    None => return Parsed::Error(format!("{prog}: default command {d:?} is not in the spec")),
                };
                chain.push(c);
                path.push(d.clone());
                level = &c.commands;
            }
            None => return Parsed::Error(format!("{prog}: no command; --help lists them")),
        },
    }
    // descend into groups
    while !level.is_empty() {
        match argv.get(i).map(String::as_str) {
            Some("-h") | Some("--help") => return top_help(&path),
            Some(w) if !w.starts_with('-') => {
                if let Some(c) = level.iter().find(|c| c.name == w && carried(&c.hosts, host)) {
                    chain.push(c);
                    path.push(w.to_string());
                    level = &c.commands;
                    i += 1;
                } else {
                    let mut words: Vec<&str> = path.iter().map(String::as_str).collect();
                    words.push(w);
                    if let Some((old, new)) = spec.retired_hint(&words) {
                        return Parsed::Error(format!(
                            "{prog}: `{old}` is retired — use `{prog} {new}`"
                        ));
                    }
                    return Parsed::Error(format!(
                        "{prog} {}: unknown subcommand {w:?}; --help lists them",
                        path.join(" ")
                    ));
                }
            }
            _ => {
                return Parsed::Error(format!(
                    "{prog} {}: needs a subcommand ({}); --help has the usage",
                    path.join(" "),
                    level.iter().filter(|c| carried(&c.hosts, host)).map(|c| c.name.as_str()).collect::<Vec<_>>().join(", ")
                ))
            }
        }
    }
    // the arguments a command takes: its own, plus its ancestors' (a group's
    // options apply to every subcommand under it)
    let defs: Vec<&ArgDef> = chain.iter().flat_map(|c| c.args_for(host)).collect();
    //: does THIS command carry a table of its own (`open_parameters`)?
    let open_ok = chain.last().map(|c| c.open_parameters.is_some()).unwrap_or(false);
    let where_ = format!("{prog} {}", path.join(" "));
    let mut args = Args { command: path.clone(), ..Default::default() };
    let mut positional: Vec<String> = Vec::new();
    let mut only_positional = false;
    while i < argv.len() {
        let tok = &argv[i];
        i += 1;
        if only_positional || tok == "-" || !tok.starts_with('-') {
            //: ★`k=v` on a command with a parameter table is a PARAMETER, not
            //: a positional (E-12 ①).  After `--` it is a positional again —
            //: which is how a path that really contains `=` gets through.
            if !only_positional && open_ok {
                if let Some(o) = open_bare(tok) {
                    //: ★★E-12 ④ **the name decides, not the spelling**: `shot=1`
                    //: is the declared `--shot`, because that word already means
                    //: one thing everywhere in `fy` (`data fetch --shot`).  A
                    //: template may therefore not declare a name this file has.
                    let as_flag = format!("--{}", o.key);
                    if let Some(d) = defs.iter().find(|d| !d.positional && d.flags.contains(&as_flag)) {
                        let v = o.value.clone().unwrap_or_default();
                        if let Err(e) = check_value(d, &v) {
                            return Parsed::Error(format!("{where_}: {e}"));
                        }
                        args.values.push((d.name.clone(), Some(v)));
                        continue;
                    }
                    args.open.push(o);
                    continue;
                }
            }
            positional.push(tok.clone());
            continue;
        }
        if tok == "--" {
            only_positional = true;
            continue;
        }
        if tok == "-h" || tok == "--help" {
            return top_help(&path);
        }
        let (name, inline) = match tok.split_once('=') {
            Some((n, v)) if n.starts_with("--") => (n.to_string(), Some(v.to_string())),
            _ => (tok.clone(), None),
        };
        let def = match defs.iter().find(|d| !d.positional && d.flags.contains(&name)) {
            Some(d) => *d,
            None => {
                //: ★an option this file does not declare, on a command that
                //: says its parameters live elsewhere: collect it and let the
                //: template refuse it by name (E-11).  The refusal still
                //: happens — one stage later, where the names are known.
                if open_ok {
                    if let Some(o) = open_flag(&name, inline.clone()) {
                        args.open.push(o);
                        continue;
                    }
                }
                //: ★★「你打错了」与「它改名了」是两件事，而 `unknown option` 把它们
                //: 说成同一句。手边的命令行和已经发出去的文档里还写着旧名的人，需要
                //: 的是新名字，不是一句「去看 --help」。表很小，改名也不常有。
                let hint = RENAMED
                    .iter()
                    .find(|(old, _)| *old == name)
                    .map(|(_, new)| format!(" — renamed to {new}"))
                    .unwrap_or_default();
                return Parsed::Error(format!(
                    "{where_}: unknown option {name:?}{hint}; --help has the usage"
                ))
            }
        };
        match def.action {
            Action::StoreTrue | Action::StoreFalse => {
                if inline.is_some() {
                    return Parsed::Error(format!("{where_}: {name} takes no value"));
                }
                args.values.push((def.name.clone(), None));
            }
            Action::Store | Action::Append => {
                let count = match def.nargs {
                    Nargs::N(k) => k,
                    _ => 1,
                };
                let mut vals: Vec<String> = Vec::new();
                if let Some(v) = inline {
                    vals.push(v);
                }
                while vals.len() < count {
                    match argv.get(i) {
                        Some(v) if def.nargs == Nargs::Optional && v.starts_with('-') => break,
                        Some(v) => {
                            vals.push(v.clone());
                            i += 1;
                        }
                        None => break,
                    }
                }
                if vals.len() < count {
                    if def.nargs == Nargs::Optional {
                        args.values.push((def.name.clone(), None));
                        continue;
                    }
                    return Parsed::Error(format!(
                        "{where_}: {name} wants {} value{}",
                        count,
                        if count == 1 { "" } else { "s" }
                    ));
                }
                for v in &vals {
                    if let Err(e) = check_value(def, v) {
                        return Parsed::Error(format!("{where_}: {e}"));
                    }
                }
                let joined = vals.join(" ");
                args.values.push((def.name.clone(), Some(joined)));
            }
        }
    }
    // required options
    for d in defs.iter().filter(|d| !d.positional && d.required) {
        if !args.has(&d.name) {
            return Parsed::Error(format!("{where_}: {} is required", d.flags.join("/")));
        }
    }
    // positionals: bind in order; a `+`/`*` one takes what the later ones
    // do not need
    let pdefs: Vec<&ArgDef> = defs.iter().copied().filter(|d| d.positional).collect();
    let need_after = |k: usize| -> usize {
        pdefs[k + 1..]
            .iter()
            .map(|d| match d.nargs {
                Nargs::One => 1,
                Nargs::N(n) => n,
                Nargs::Plus => 1,
                _ => 0,
            })
            .sum()
    };
    let mut p = 0;
    for (k, d) in pdefs.iter().enumerate() {
        let left = positional.len().saturating_sub(p);
        let take = match d.nargs {
            Nargs::One => {
                if left == 0 {
                    return Parsed::Error(format!("{where_}: missing <{}>", d.name));
                }
                1
            }
            Nargs::N(n) => {
                if left < n {
                    return Parsed::Error(format!("{where_}: <{}> wants {n} values", d.name));
                }
                n
            }
            Nargs::Optional => usize::from(left > need_after(k) && left > 0),
            Nargs::Plus => {
                let t = left.saturating_sub(need_after(k));
                if t == 0 {
                    return Parsed::Error(format!("{where_}: needs at least one <{}>", d.name));
                }
                t
            }
            Nargs::Star => left.saturating_sub(need_after(k)),
        };
        for v in &positional[p..p + take] {
            if let Err(e) = check_value(d, v) {
                return Parsed::Error(format!("{where_}: {e}"));
            }
            args.values.push((d.name.clone(), Some(v.clone())));
        }
        p += take;
    }
    if p < positional.len() {
        return Parsed::Error(format!(
            "{where_}: unexpected argument {:?}; --help has the usage",
            positional[p]
        ));
    }
    args.positional = positional;
    Parsed::Run(args)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn argv(s: &str) -> Vec<String> {
        s.split_whitespace().map(str::to_string).collect()
    }

    fn run(s: &str) -> Args {
        match parse(spec(), HOST, "fylite", &argv(s)) {
            Parsed::Run(a) => a,
            other => panic!("{s:?} did not parse: {other:?}"),
        }
    }

    fn err(s: &str) -> String {
        match parse(spec(), HOST, "fylite", &argv(s)) {
            Parsed::Error(e) => e,
            other => panic!("{s:?} should have been refused: {other:?}"),
        }
    }

    #[test]
    fn the_spec_parses_and_the_rust_host_carries_four_commands() {
        let names: Vec<&str> = spec().commands_for(HOST).iter().map(|c| c.name.as_str()).collect();
        //: ★one verb each: serve the page, move data, compute, look.
        assert_eq!(names, ["app", "data", "run", "list"]);
        assert_eq!(spec().default_command.as_deref(), Some("app"));
        //: ★the program name comes from `hosts.rust.exe` — `fy` since 2026-09-04.
        //: `main.rs` hands THIS to the parser, so a rename lands in the usage
        //: text of both hosts at once and cannot be forgotten in one of them.
        assert_eq!(spec().prog, "fy");
    }

    #[test]
    fn no_command_means_the_default_one() {
        let a = run("");
        assert_eq!(a.command, ["app"]);
        let a = run("--port 8123 --no-open");
        assert_eq!(a.command, ["app"]);
        assert_eq!(a.flag("port"), Some("8123"));
        assert!(a.has("no-open"));
    }

    #[test]
    fn a_group_descends_and_binds_positionals() {
        let a = run("data convert in.json out.h5 --to hdf5 --layout imas");
        assert_eq!(a.command, ["data", "convert"]);
        assert_eq!(a.flag("input"), Some("in.json"));
        assert_eq!(a.flag("output"), Some("out.h5"));
        assert_eq!(a.flag("to"), Some("hdf5"));
        let a = run("data merge a.json b.json -o out.json --keep");
        assert_eq!(a.all("inputs"), ["a.json", "b.json"]);
        assert_eq!(a.flag("out"), Some("out.json"));
        let a = run("run p1.jsonld p2.jsonld -o rec");
        assert_eq!(a.all("target"), ["p1.jsonld", "p2.jsonld"]);
        assert_eq!(a.flag("record"), Some("rec"));
        let a = run("list scenarios reconstruction --line analysis");
        assert_eq!(a.command, ["list", "scenarios"]);
        assert_eq!(a.all("name"), ["reconstruction"]);
        assert_eq!(a.flag("line"), Some("analysis"));
    }

    #[test]
    fn a_scenario_parameter_is_collected_not_refused() {
        //: the four spellings of one parameter (E-12), and the fixed options
        //: around them keeping their own meaning
        let a = run("run analysis --device east shot=123456 time=4.4 --only-magnetic=true");
        assert_eq!(a.all("target"), ["analysis"]);
        assert_eq!(a.flag("device"), Some("east"));
        //: `shot=` and `time=` are FIXED options under those names, not open
        //: ones — the name decides, not the spelling (E-12 ④)
        assert!(a.open.iter().all(|o| o.key != "shot" && o.key != "time"), "{:?}", a.open);
        assert_eq!(a.flag("shot"), Some("123456"));
        assert_eq!(a.flag("time"), Some("4.4"));
        //: and the same values written as flags land in the same place
        let b = run("run analysis --device east --shot 123456 --time 4.4");
        assert_eq!((b.flag("shot"), b.flag("time")), (a.flag("shot"), a.flag("time")));
        //: a bare `k=v` whose name IS a declared option is type-checked there
        assert!(err("run analysis shot=nine").contains("wants an integer"));
        let one = a.open.iter().find(|o| o.key == "only-magnetic").expect("collected");
        assert_eq!(one.literal(), "true");
        let a = run("run model transport --alpha --no-bootstrap chi0=0.4");
        let got: Vec<(&str, &str)> = a.open.iter().map(|o| (o.key.as_str(), o.literal())).collect();
        assert_eq!(got, [("alpha", "true"), ("bootstrap", "false"), ("chi0", "0.4")]);
        //: after `--`, a token with `=` is a path again, not a parameter
        let a = run("run -- weird=name.jsonld");
        assert!(a.open.is_empty());
        assert_eq!(a.all("target"), ["weird=name.jsonld"]);
        //: and a command WITHOUT the declaration is unchanged: still refused
        assert!(err("data tables --only-magnetic=true").contains("unknown option"));
    }

    #[test]
    fn a_retired_word_is_refused_with_its_replacement() {
        //: ★the whole line matters: `case run` answers with `run`, and the
        //: bare word answers too — neither is silently forwarded.
        let e = err("case run plan.jsonld -o rec");
        assert!(e.contains("`case run` is retired") && e.contains("run <the same plans>"), "{e}");
        let e = err("case describe");
        assert!(e.contains("list kernel"), "{e}");
        let e = err("case");
        assert!(e.contains("`case` is retired"), "{e}");
        let e = err("data facts device");
        assert!(e.contains("`data facts` is retired") && e.contains("list facts"), "{e}");
    }

    #[test]
    fn refusals_are_by_name() {
        assert!(err("data convert in out --bogus").contains("unknown option \"--bogus\""));
        //: ★改过名的旧选项要说出新名字，而不是只说「不认识」。
        let renamed = err("data fetch --machine east --ids wall --shot 1");
        assert!(renamed.contains("--machine") && renamed.contains("renamed to --device"),
                "{renamed}");
        assert!(err("data merge a.json").contains("-o/--out is required"));
        assert!(err("data convert in out --to xml").contains("takes one of"));
        assert!(err("app --port x").contains("wants an integer"));
        assert!(err("data").contains("needs a subcommand"));
        assert!(err("frobnicate").contains("unknown command"));
        //: a python-only option is not the Rust host's to accept
        assert!(err("app --bin-dir x").contains("unknown option"));
    }

    #[test]
    fn help_is_generated_from_the_spec() {
        let u = usage(spec(), HOST, &spec().prog, &[]);
        assert!(u.contains("app ") && u.contains("data ") && u.contains("run ") && u.contains("list "));
        assert!(u.contains("runs `app`"));
        let u = usage(spec(), HOST, &spec().prog, &["data", "convert"]);
        assert!(u.contains("--to json|geqdsk|hdf5|netcdf|imas-hdf5"), "{u}");
        assert!(!u.contains("--bin-dir"));
        //: the open table is announced where it applies, and nowhere else
        let u = usage(spec(), HOST, &spec().prog, &["run"]);
        assert!(u.contains("[key=value...]") && u.contains("scenario parameters:"), "{u}");
        assert!(!usage(spec(), HOST, &spec().prog, &["data", "merge"]).contains("key=value..."));
        match parse(spec(), HOST, "fylite", &argv("run --help")) {
            Parsed::Help(h) => assert!(h.contains("--record")),
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn app_launch_options_name_the_browser_parameters() {
        let app = spec().command(HOST, &["app"]).unwrap()[0];
        let declared: Vec<&str> = spec().app_params.iter().map(|p| p.name.as_str()).collect();
        let bound: Vec<&str> = app.args.iter().filter_map(|a| a.app_param.as_deref()).collect();
        for d in &declared {
            assert!(bound.contains(d), "app param {d} has no --{d} option");
        }
        for b in &bound {
            assert!(declared.contains(b), "--{b} names an undeclared app param");
        }
    }
}
