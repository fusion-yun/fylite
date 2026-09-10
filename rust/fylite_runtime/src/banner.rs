//! 启动 banner —— 招牌、许可、版本，以及**提示词**。
//!
//! ★★2026-09-08 用户裁定：*python/cli 层添加启动 banner，参考 fytok 中 ASCII
//! 排版的 banner，包含版 header 提示词；提示词默认包含版本提醒；web ui / cli /
//! python 三个界面统一提示词*。
//!
//! 三个界面同一份文本，真源是 `python/fylite/_notice.json`，**编译期**
//! `include_str!` 进来——与 `_cli.json` 同一条规矩：一份数据，多处建出，一道闸子
//! 比对。浏览器那一面读 `app/assets/lang-{zh,en}.js` 的同两个词条（由
//! `app/tests/validate-site.mjs` 逐字押在这份 JSON 上），Python 那一面读同一个
//! 文件（`fylite.notice`）。
//!
//! ★为什么值得这么绕：一句在一个界面上说、在另一个界面上不说的提示，比不说更糟
//! ——**见过其中一面的人会以为自己已经被告知**。
//!
//! ★★**印到 stderr**。`fy list --json` 的 stdout 是给管道的；把招牌混进去等于让
//! 这个命令不能被脚本用。stderr 上它照样在人眼前。
//!
//! ★★**版别决定说几句**：`alpha` 那一句每一版都说，`仅限内部测试` 只有内部版说。
//! 版别不是运行时开关，它在编译期定死（`FYL-DESIGN-19` A-14 / A-18），本模块问的是
//! [`crate::facts::flavour`]——那一格由 `tools/facts-publish.py` 写进编进来的
//! `facts.rs`，与 `.so` / wasm / 站点是同一次构建的同一个值。

use crate::cli::str_items;
use crate::document::Node;
use crate::json;
use std::sync::OnceLock;

/// 真源，编译期读进来。★路径写死一个相对路径，因为它就是同一个仓里的同一个文件；
/// 找不到的后果是**编译失败**，而那正是想要的：一份印不出提示词的构建不该出得来。
pub const SOURCE: &str = include_str!("../../../python/fylite/_notice.json");

/// 一条提示词：说什么、哪些版别说。
pub struct Notice {
    pub id: String,
    pub zh: String,
    pub en: String,
    pub flavours: Vec<String>,
}

/// 整份 banner 的规格。
pub struct Spec {
    pub wordmark: Vec<String>,
    pub rule: String,
    pub rule_width: usize,
    pub spdx: String,
    pub copyright: String,
    pub notices: Vec<Notice>,
    pub quiet_env: String,
    pub lang_env: String,
    pub default_flavour: String,
}

fn s(n: Option<&Node>) -> String {
    n.and_then(Node::as_str).unwrap_or("").to_string()
}

/// 解析一次，之后走缓存。
pub fn spec() -> &'static Spec {
    static SPEC: OnceLock<Spec> = OnceLock::new();
    SPEC.get_or_init(|| {
        //: ★解析不了就 panic：这份 JSON 与本文件在同一个仓里，是构建的一部分，
        //: 不是运行时输入。悄悄退回一个空 banner 等于把提示词弄丢而不报错。
        let root = json::parse(SOURCE).expect("_notice.json: 解析失败");
        let notices: Vec<Notice> = root
            .get("notices")
            .and_then(Node::as_list)
            .map(|l| {
                l.iter()
                    .map(|n| Notice {
                        id: s(n.get("id")),
                        zh: s(n.get("zh")),
                        en: s(n.get("en")),
                        flavours: n.get("flavours").map(str_items).unwrap_or_default(),
                    })
                    .collect()
            })
            .unwrap_or_default();
        assert!(!notices.is_empty(), "_notice.json: 一条提示词也没有");
        Spec {
            wordmark: root.get("wordmark").map(str_items).unwrap_or_default(),
            rule: s(root.get("rule")),
            rule_width: root
                .get("rule_width")
                .and_then(Node::as_i64)
                .unwrap_or(78)
                .max(1) as usize,
            spdx: s(root.get("spdx")),
            copyright: s(root.get("copyright")),
            notices,
            quiet_env: s(root.get("quiet_env")),
            lang_env: s(root.get("lang_env")),
            default_flavour: s(root.get("default_flavour")),
        }
    })
}

/// `zh` 或 `en`：`$FY_LANG` > 区域设置 > `en`。★规则与 Python 侧同一条，写在
/// JSON 的 `lang_rule` 里；两处各实现一遍，但实现的是同一句话。
pub fn language() -> &'static str {
    let sp = spec();
    if let Ok(v) = std::env::var(&sp.lang_env) {
        if v == "zh" || v == "en" {
            return if v == "zh" { "zh" } else { "en" };
        }
    }
    for var in ["LC_ALL", "LC_MESSAGES", "LANG"] {
        if let Ok(v) = std::env::var(var) {
            if v.to_ascii_lowercase().starts_with("zh") {
                return "zh";
            }
        }
    }
    "en"
}

/// 这一版要说的几句，按 JSON 里的次序（先成熟度，再可及范围）。
pub fn notices(lang: &str, flavour: &str) -> Vec<String> {
    spec()
        .notices
        .iter()
        .filter(|n| n.flavours.iter().any(|f| f == flavour))
        .map(|n| if lang == "zh" { n.zh.clone() } else { n.en.clone() })
        .collect()
}

/// 整块 banner（不带末尾换行）。
///
/// `quiet` 时只留提示词——★招牌关得掉，提示词关不掉：那是使用条件，不是装饰。
pub fn text(lang: &str, flavour: &str, version_line: &str, quiet: bool) -> String {
    let sp = spec();
    let rule = sp.rule.repeat(sp.rule_width);
    let mut lines: Vec<String> = vec![rule.clone()];
    if !quiet {
        lines.extend(sp.wordmark.iter().cloned());
        lines.push(format!("{} · {}", sp.spdx, sp.copyright));
        if !version_line.is_empty() {
            lines.push(version_line.to_string());
        }
    }
    lines.extend(notices(lang, flavour));
    lines.push(rule);
    lines.join("\n")
}

/// 这个宿主自己那一行。★三个宿主提示词一字不差，版本行各说各的：它们是三个不同的
/// 制品，装作同一个才是说谎。
fn version_line(lang: &str, flavour: &str) -> String {
    let v = env!("CARGO_PKG_VERSION");
    //: ★不印内核 ABI 号：那个数要**问内核**（`fylite_rs_abi_version()`，一次
    //: 调用），而 banner 是启动时印的第一样东西——为一行招牌去唤醒算力，会把
    //: 「这份构建带不带内核」变成 banner 的问题。Python 那一面印得出来，是因为
    //: 它手上本来就有一个生成物 `_abi.py`；这一面没有，就不印。
    let linked = crate::kernel::Kernel::is_linked_in();
    if lang == "zh" {
        let core = if linked { "算力自带" } else { "算力另取" };
        format!("fy {v} · {core} · {flavour} 版")
    } else {
        let core = if linked { "kernel linked in" } else { "kernel loaded separately" };
        format!("fy {v} · {core} · {flavour} build")
    }
}

/// 印多少。★把**决定**与「谁在看」分开，好让它可测——`is_terminal()` 在测试进程里
/// 是什么值不由这个模块说了算。
#[derive(Debug, PartialEq, Eq, Clone, Copy)]
pub enum Show {
    /// 一个字也不印。
    Nothing,
    /// 只印提示词（招牌、许可行、版本行都不印）。
    NoticesOnly,
    /// 全印。
    Full,
}

/// 这一次要印多少：**有人看着**才印，`$FY_NO_BANNER` 只收掉装饰。
///
/// ★★2026-09-08 用户裁定：*fy cli 交互时显示 banner*。非交互时一个字也不印——
/// banner 的读者是人，而 `fy list --json | jq` 那条流上没有人，只有噪声。
/// ★代价说在明处：一份被重定向进日志的内部版构建，日志里不会留下「仅限内部测试」
/// 那一句。提示词仍在页面头条、README 与制品的 NOTICE 上。
pub fn decide(interactive: bool, quiet: bool) -> Show {
    match (interactive, quiet) {
        (false, _) => Show::Nothing,
        (true, true) => Show::NoticesOnly,
        (true, false) => Show::Full,
    }
}

/// `$FY_NO_BANNER` 说没说「安静」。空串与 `0` 都算没说。
fn quiet_asked() -> bool {
    std::env::var(&spec().quiet_env).map(|v| !v.is_empty() && v != "0").unwrap_or(false)
}

/// 启动时印一次，到 stderr——**stderr 是终端才印**（见 [`decide`]）。
pub fn emit() {
    use std::io::IsTerminal;
    emit_to(std::io::stderr().is_terminal(), false);
}

/// 命令行上有没有说「不要 banner」。★名字取自 `_cli.json` 的 `globals`，不写死在
/// 这里：写死的那一份与用法屏上印的那一个是两处，某天它们会不同名，而不报错。
pub fn quiet_flag(argv: &[String]) -> bool {
    crate::cli::spec()
        .globals
        .iter()
        .filter(|g| g.name == "nobanner")
        .any(|g| g.flags.iter().any(|f| argv.iter().any(|a| a == f)))
}

/// 带上这次调用的 argv 印一次：`--nobanner` 与 `$FY_NO_BANNER` 同效。
pub fn emit_argv(argv: &[String]) {
    use std::io::IsTerminal;
    emit_to(std::io::stderr().is_terminal(), quiet_flag(argv));
}

/// [`emit`] 的可测那一半：交互与否由调用方给。
fn emit_to(interactive: bool, quiet_flag: bool) {
    let show = decide(interactive, quiet_asked() || quiet_flag);
    if show == Show::Nothing {
        return;
    }
    let lang = language();
    let flavour = crate::facts::flavour();
    let line = version_line(lang, flavour);
    eprintln!("{}", text(lang, flavour, &line, show == Show::NoticesOnly));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_public_build_drops_the_internal_notice() {
        //: ★两头都断言。只查「公开版里没有」的话，一个把提示整个弄丢的改动会
        //: 悄悄通过——而那正是内部版最不该出的错。
        let sp = spec();
        let io = sp.notices.iter().find(|n| n.id == "internal_only").expect("internal_only");
        assert!(!io.flavours.iter().any(|f| f == "public"));
        assert_eq!(notices("zh", "internal").len(), sp.notices.len());
        assert_eq!(notices("zh", "public").len(), sp.notices.len() - 1);
        assert!(notices("zh", "public").iter().all(|t| *t != io.zh));
    }

    #[test]
    fn the_command_line_can_ask_for_quiet_too() {
        //: ★★`--nobanner` 与 `$FY_NO_BANNER` 同效，而名字取自规格的 `globals`
        //: ——这一条把两者钉在一起：规格里改了名字，这里当场红，而不是等到某天
        //: 有人按用法屏上印的那个名字敲、却得到一句 unknown option。
        let flag = &crate::cli::spec().globals.iter()
            .find(|g| g.name == "nobanner").expect("globals 里没有 nobanner")
            .flags[0].clone();
        assert!(quiet_flag(&[flag.to_string()]));
        assert!(quiet_flag(&["list".into(), flag.to_string(), "lines".into()]));
        assert!(!quiet_flag(&["list".into(), "lines".into()]));
    }

    #[test]
    fn quiet_keeps_the_notices_and_drops_the_decoration() {
        const MARK: &str = "VERSION-LINE-MARK";
        let loud = text("zh", "internal", MARK, false);
        let quiet = text("zh", "internal", MARK, true);
        //: ★这一条是本模块的**规矩**，不是排版偏好：安静关得掉招牌，关不掉提示词。
        for n in notices("zh", "internal") {
            assert!(quiet.contains(&n), "安静模式把提示词也关掉了：{n}");
        }
        assert!(loud.contains("SPDX") && loud.contains(MARK));
        assert!(!quiet.contains("SPDX") && !quiet.contains(MARK));
    }

    #[test]
    fn nothing_is_printed_when_nobody_is_watching() {
        //: ★★用户裁定 2026-09-08：交互时才显示。管道上一个字也不印——包括提示词，
        //: 因为那条流上没有读者，只有下一个程序的输入。
        assert_eq!(decide(false, false), Show::Nothing);
        assert_eq!(decide(false, true), Show::Nothing);
        //: ★而**有人看着**的时候，安静只收掉装饰：提示词是使用条件，不是装饰。
        assert_eq!(decide(true, false), Show::Full);
        assert_eq!(decide(true, true), Show::NoticesOnly);
    }

    #[test]
    fn every_notice_is_spelled_in_both_languages() {
        for n in &spec().notices {
            assert!(!n.zh.is_empty() && !n.en.is_empty(), "{} 缺一种语言", n.id);
        }
    }
}
