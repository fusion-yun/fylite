//! facts 的搜索路径 —— 多个语料，按优先级，**逐条决胜**。
//!
//! `facts/` 装的是关于具名个体的断言，按域分轴：`facts/device/east`、
//! `facts/amns/<provider>`、`facts/experiment/<machine>/<shot>`。本模块只回答一个
//! 问题：**给定域与标识，那份文件是哪一个？**
//!
//! ★★**多个根，而第一个根赢下整条**。发行版自带一份、站点有一份、排障的人手上还有
//! 一份，按序查，像 `$PATH`。本模块**不做的**是把它们合起来：两个根都描述 EAST，
//! 而它们描述得不一样（一个带参考放电，另一个线圈几何更新），拼一半出来的是一台
//! **没人运行的机器**——而且不报错。所以决胜的单位是**条目**：第一个有
//! `<域>/<id>` 的根供出文档、卡片与许可账三样，[`Entry::root`] 记下是哪个根。
//!
//! ★值级合并是另一层，而且是有意的：`assembly` 由一份清单（`$source` / `$link` /
//! `merge` / `merge_key`）说明**怎么合**，那是一次声明过的组合。因为两份文件恰好
//! 落在两个根里就偏取其一的线圈、其二的壁，不是。
//!
//! 顺序，优先级从高到低：
//!
//! 1. 显式覆盖 —— 命令行 `--facts`（见 [`use_roots`]）；
//! 2. `$FY_FACTS_PATH` —— 平台路径分隔符分隔，从左到右；
//! 3. 检出自己的暂存语料 `dist/facts/`（自可执行文件位置上溯探得），**排在自带的那份之前**——
//!    否则一份打包时冻结的语料会悄无声息地盖住刚拖回来的那一份；
//! 4. 发行版**自带的那一份**——`$FY_FACTS_BUNDLED` 指一棵树，或（今天的做法）
//!    **编进二进制的那张表**：装置信息随发行版走，一份纯二进制自己就答得出
//!    `fy list devices` 与 `fy run --device`（2026-09-05 用户裁定）。
//!
//! ★不存在的根**静默跳过**，被指名却不可用的根由 [`problems`] 报出。两者不同：
//! 「语料还没拖回来」是新检出的常态，而「这条路径设了、却不是语料」是一个值得
//! 当场说出来的错。
//!
//! ★★**与 Python 侧 `fylite.facts` 是有意的两份实现**，判据同 `_cli.json` 的三个
//! 解析器：一份规则、多处建出、一道闸子比对（`python/tests/test_facts_corpus.py`
//! 的 `test_the_two_resolvers_agree`）。命令行走的是本模块，Python 里的调用走那一份。

use std::path::{Path, PathBuf};

//: ★★自带的那一档：**编进二进制**的装置信息（2026-09-05 用户裁定「fylite 下已无
//: facts 目录；装置信息打包进发行版二进制」）。表由 `build.rs` 写进 `$OUT_DIR`，
//: 源里没有它——那些文档是受许可约束的数据，写成 `.rs` 提交进公开仓就是换一种语法
//: 发布同一批字节。源码检出里这张表是空的，发行构建给 `$FY_FACTS_DIR` 时才有内容。
include!(concat!(env!("OUT_DIR"), "/facts_table.rs"));

/// 搜索路径的环境变量。与 `$PATH` 用同一个分隔符——同一个概念，平台已经有写法了。
pub const FACTS_ENV: &str = "FY_FACTS_PATH";

/// 自带那一档的伪根名。它不是一条路径，所以不能是空串或一个真目录名——
/// 打印出来的「是谁供的」要一眼看得出这一份**不在盘上**。
pub const BUNDLED_ROOT: &str = "<bundled>";

/// 自带的那一档里，某个域的全部标识。
fn embedded_idents(domain: &str) -> Vec<String> {
    EMBEDDED
        .iter()
        .filter(|(d, id, _)| *d == domain && *id != "catalogue")
        .map(|(_, id, _)| id.to_string())
        .collect()
}

/// 自带的那一档里那一条的文本。
fn embedded_text(domain: &str, ident: &str) -> Option<&'static str> {
    EMBEDDED
        .iter()
        .find(|(d, id, _)| *d == domain && *id == ident)
        .map(|(_, _, t)| *t)
}

/// 自带的那一档带了几条（排障与 `fy list facts --roots` 用）。
pub fn embedded_count() -> usize {
    EMBEDDED.iter().filter(|(_, id, _)| *id != "catalogue").count()
}

/// 某一域里的每一个标识，**含** `catalogue`——给 C ABI 的那一面用。
///
/// ★与 [`embedded_idents`] 的分别只有一处：那个滤掉 `catalogue`（它不是一台机器），
/// 这个不滤（页面要先读目录才知道有哪几台）。
pub fn embedded_ids(domain: &str) -> Vec<&'static str> {
    EMBEDDED.iter().filter(|(d, _, _)| *d == domain).map(|(_, id, _)| *id).collect()
}

/// 自带那一档里某一条的正文；`catalogue` 也走这里。
pub fn embedded_doc(domain: &str, ident: &str) -> Option<&'static str> {
    embedded_text(domain, ident)
}

/// 打包时告诉本模块「自带的那份在哪」。发行方在构建时给；源码检出里没有。
pub const BUNDLED_ENV: &str = "FY_FACTS_BUNDLED";

/// 一条解析出来的条目，以及**供它的那个根**。
///
/// ★`root` 不是装饰。路径上有几个语料时，「这是哪一个 EAST」逐台各有答案，而一份
/// 说不出是哪个根供的记录，换台机器就复算不出来——与运行清单必须点名它的输入是
/// 同一条理由。
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub domain: String,
    pub ident: String,
    pub root: PathBuf,
    /// 页面读的那份文档，`<id>.jsonld`，有则在
    pub document: Option<PathBuf>,
    /// 卡片与许可账所在的目录，有则在
    pub dir: Option<PathBuf>,
    /// 自带那一档的文档正文。**与 `document` 二选一**：这一条是编进二进制的，
    /// 盘上没有对应的文件，所以 `document` 是 `None` 而这里有字。
    pub text: Option<&'static str>,
}

impl Entry {
    /// 这一条的文档正文——自带的直接给，盘上的读出来。
    ///
    /// ★消费方一律走这一个口，不要各自 `read_to_string(document)`：那样写的每一处
    /// 都会在自带那一档上安静地拿不到东西（`document` 是 `None`），而「拿不到」的
    /// 表现是少一台机器，不是一句错。
    pub fn read(&self) -> Option<String> {
        if let Some(t) = self.text {
            return Some(t.to_string());
        }
        self.document
            .as_ref()
            .and_then(|p| std::fs::read_to_string(p).ok())
    }

    /// 有没有一份文档可读——盘上的或自带的。
    pub fn has_document(&self) -> bool {
        self.text.is_some() || self.document.is_some()
    }
}

/// fydoc 那侧的 A-Box 目录名：**一条条目的数据部分**。
///
/// ★★★这是「数据」与「散文」之间那条线，而它已经在树里了，不必另立白名单：
/// fydoc 的一台机器是 `<id>/{abox/, corpus/, figures/, *.md, *.bib, provenance.yaml}`，
/// 其中只有 `abox/` 是断言，其余是书。实测 13 台全有 `abox/`，而 `tools/`（书的
/// 构建脚本）没有——于是「有 `abox/` 就是条目」一条判据就把它挡在机器表之外。
/// 此前没有这条判据时，`fy data facts device` 对着 fydoc 会把 `tools` 列成第 14 台机器。
///
/// ★分清它要紧的不是体积是**权属**：`corpus/` 装的是上游的 `.nc` / `.xlsx`，
/// 权属另算，它一旦进制品就是一次再分发。
pub const ABOX: &str = "abox";

/// 本仓生成的许可账（上游声明 + 本仓裁定，完整），与卡片同住。
pub const RIGHTS: &str = "rights.json";

/// fydoc 那侧的许可记录：A-Box 自己的 FAIR 件，相对条目目录。
///
/// ★★★**不另立 `rights.yaml`**（用户裁定 2026-09-04：收敛进 `dataset_fair`）。
/// 理由不是省一个文件：许可这件事只该有一处可编辑的真源，而 FAIR 件**本来就是**
/// 回答「这份数据可以拿来做什么」的那一份——`license` / `rights_holder` /
/// `license_by_ids` 都已经在里面。再开一个 `rights.yaml`，两份就会各自漂。
pub const FAIR: [&str; 4] = [ABOX, "static", "now", "dataset_fair.jsonld"];

/// 装置清单在条目里的约定位置，相对条目目录。
///
/// ★一个名字定在一处：解析器、错误话术与文档都问它，免得「叫什么」这件事在三个
/// 地方各写一遍、改一处漏两处。
///
/// ★★2026-09-04 由条目根的 `machine.yaml` 改为 **`abox/device.jsonld`**（用户裁定）。
/// 清单本来就是**关于这台装置的断言**，它属于 A-Box；留在 `abox/` 外面，就等于说
/// 「数据在 abox 里，但告诉你怎么取数据的那份不在」。收进来之后 fydoc 的一台机器
/// 才是一个**自足的**条目：数据、许可、清单同在 `abox/` 下，打包只取这一棵。
pub const MANIFEST: [&str; 2] = [ABOX, "device.jsonld"];

/// `MANIFEST` 拼在某个条目目录下的完整路径（也用于错误话术）。
pub fn manifest_under(dir: &Path) -> PathBuf {
    MANIFEST.iter().fold(dir.to_path_buf(), |a, s| a.join(s))
}

impl Entry {
    /// 许可账的路径（存在才给）。
    ///
    /// ★两处都认：本仓生成的 `rights.json`（上游声明 + 本仓裁定，完整），
    /// 与 fydoc 的 `abox/static/now/dataset_fair.jsonld`（上游声明 + 本仓裁定
    /// 同住一件）。**都在同一个根里**，所以这不是跨根拼账。
    pub fn rights_path(&self) -> Option<PathBuf> {
        let d = self.dir.as_ref()?;
        let generated = d.join(RIGHTS);
        if generated.is_file() {
            return Some(generated);
        }
        let fair = FAIR.iter().fold(d.clone(), |a, seg| a.join(seg));
        fair.is_file().then_some(fair)
    }

    /// 这条条目的 A-Box 目录（fydoc 形状），存在才给。
    pub fn abox_path(&self) -> Option<PathBuf> {
        let p = self.dir.as_ref()?.join(ABOX);
        p.is_dir().then_some(p)
    }

    /// 这条条目的装置清单（`<dir>/machine.yaml`），存在才给。
    ///
    /// ★★**不是每条 device 条目都有**：语料里多数装置只有一张卡片
    /// （`<id>_device.yaml` + 许可账），能取的是描述而不是一次抓取。所以这里
    /// 返回 `Option` 而不是拼出路径就走——「有这台机器」与「这台机器抓得动」
    /// 是两件事，把它们混成一句，用户看到的会是一条 YAML 解析错误。
    pub fn manifest_path(&self) -> Option<PathBuf> {
        let p = manifest_under(self.dir.as_ref()?);
        p.is_file().then_some(p)
    }
}

fn split_list(raw: &str) -> Vec<PathBuf> {
    let sep = if cfg!(windows) { ';' } else { ':' };
    raw.split(sep)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .collect()
}

thread_local! {
    //: 进程内覆盖，由 `--facts` 在入口处设一次。
    //: ★不是可重入的作用域：搜索路径若在一次调用中途变了，同一次运行里的两次读取
    //: 会解析到不同的根，而记录只会写下其中一个。
    static OVERRIDE: std::cell::RefCell<Option<Vec<PathBuf>>> =
        const { std::cell::RefCell::new(None) };
}

/// 设定（或 `None` 清除）进程内的覆盖。
pub fn use_roots(paths: Option<Vec<PathBuf>>) {
    OVERRIDE.with(|o| *o.borrow_mut() = paths);
}

/// 把一批 `--facts` 的取值（每个都可能自带分隔符）摊平成根的列表。
pub fn parse_roots<I: IntoIterator<Item = S>, S: AsRef<str>>(items: I) -> Vec<PathBuf> {
    items
        .into_iter()
        .flat_map(|s| split_list(s.as_ref()))
        .collect()
}

fn named() -> Vec<PathBuf> {
    if let Some(v) = OVERRIDE.with(|o| o.borrow().clone()) {
        return v;
    }
    std::env::var(FACTS_ENV)
        .ok()
        .filter(|s| !s.trim().is_empty())
        .map(|s| split_list(&s))
        .unwrap_or_default()
}

/// 检出自己的暂存语料 `dist/facts/`：自可执行文件位置上溯，找一个既有它、又有
/// `python/` 的目录。★判据要**两样**：只看一个目录名会把任何恰好同名的祖先当成检出。
///
/// ★★2026-09-05 用户裁定：**fylite 下已无 `facts/` 目录**。拖回来的语料落在
/// `dist/facts/`（构建暂存区，`dist/` 本来就不入库）。仓顶那个目录只靠一行
/// `.gitignore` 撑着，还有一条 `app/facts` 符号链接指着它——于是「哪些字节属于这个
/// 仓」要靠记忆回答；搬进 `dist/` 之后由目录名自己回答。
fn repo_facts() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let mut here: &Path = exe.parent()?;
    loop {
        let cand = here.join("dist").join("facts");
        if cand.is_dir() && here.join("python").is_dir() {
            return Some(cand);
        }
        here = here.parent()?;
    }
}

/// 路径上**存在**的每一个根，按优先级，去重。
///
/// ★按解析后的真实路径去重：同一个根被指了两次（比如环境变量与检出探测各一次），
/// 否则「是哪个根供的」会含糊成一个读起来像第二个来源的答案。
pub fn roots() -> Vec<PathBuf> {
    let mut out = named();
    if let Some(r) = repo_facts() {
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
        "--facts".to_string()
    } else {
        format!("${FACTS_ENV}")
    };
    named()
        .into_iter()
        .filter_map(|p| {
            if !p.exists() {
                Some(format!("{where_}: {} 不存在", p.display()))
            } else if !p.is_dir() {
                Some(format!("{where_}: {} 不是目录", p.display()))
            } else if !std::fs::read_dir(&p)
                .map(|mut d| d.any(|e| e.map(|e| e.path().is_dir()).unwrap_or(false)))
                .unwrap_or(false)
            {
                Some(format!(
                    "{where_}: {} 里没有域目录（应为 facts/<域>/，如 device/）",
                    p.display()
                ))
            } else {
                None
            }
        })
        .collect()
}

/// 任一根带有的每一个域，按名排序。
pub fn domains() -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for r in roots() {
        let Ok(rd) = std::fs::read_dir(&r) else { continue };
        for e in rd.flatten() {
            let p = e.path();
            if !p.is_dir() {
                continue;
            }
            if let Some(n) = p.file_name().and_then(|s| s.to_str()) {
                if !n.starts_with('.') && !n.starts_with('_') && !out.iter().any(|x| x == n) {
                    out.push(n.to_string());
                }
            }
        }
    }
    out.sort();
    out
}

/// 这个目录是一条**条目**，还是恰好躺在域目录下的别的东西？
///
/// ★★判据是「里面有没有本层认得出的部件」——A-Box、许可账、装置清单、装置牌。
/// 一个都认不出，那它就不是这一层的条目：fydoc 的 `device/tools/`（书的构建脚本）
/// 正是这种东西，而在有这条判据之前它会被列成一台机器。
/// ★反过来说，这也把「能消费什么」写成了一处可读的清单——加一种部件就在这里加。
fn is_entry_dir(dir: &Path, ident: &str) -> bool {
    dir.join(ABOX).is_dir()
        || manifest_under(dir).is_file()
        || dir.join(format!("{ident}_device.yaml")).is_file()
        || dir.join(RIGHTS).is_file()
}

/// 第一个带有 `<域>/<标识>` 的根，没有则 `None`。
///
/// 一条条目可以是一份文档（`<id>.jsonld`）、一个目录（`<id>/`，卡片与许可账），
/// 或两者都有——任一半在，这个根就答；**另一半取自同一个根**，绝不落到下一个。
pub fn find(domain: &str, ident: &str) -> Option<Entry> {
    for r in roots() {
        let doc = r.join(domain).join(format!("{ident}.jsonld"));
        let dir = r.join(domain).join(ident);
        let (has_doc, has_dir) = (doc.is_file(), dir.is_dir() && is_entry_dir(&dir, ident));
        if has_doc || has_dir {
            return Some(Entry {
                domain: domain.to_string(),
                ident: ident.to_string(),
                root: r,
                document: has_doc.then_some(doc),
                dir: has_dir.then_some(dir),
                text: None,
            });
        }
    }
    //: ★最后一档：编进二进制的那一份。**排在盘上的每一个根之后**，理由与从前
    //: `$FY_FACTS_BUNDLED` 排最后一样——一份打包时冻结的语料不该盖住刚拖回来的。
    embedded_text(domain, ident).map(|t| Entry {
        domain: domain.to_string(),
        ident: ident.to_string(),
        root: PathBuf::from(BUNDLED_ROOT),
        document: None,
        dir: None,
        text: Some(t),
    })
}

/// 某一域里的每一个标识，按名排序，各自来自赢下它的那个根。
///
/// ★跨根取并集，而**逐条**决胜——低优先级的根补上高优先级没有的那些，不补它有的。
pub fn entries(domain: &str) -> Vec<Entry> {
    let mut names: Vec<String> = Vec::new();
    for r in roots() {
        let Ok(rd) = std::fs::read_dir(r.join(domain)) else { continue };
        for e in rd.flatten() {
            let p = e.path();
            let n = if p.is_dir() {
                p.file_name().and_then(|s| s.to_str()).map(str::to_string)
            } else if p.extension().and_then(|s| s.to_str()) == Some("jsonld") {
                p.file_stem()
                    .and_then(|s| s.to_str())
                    .filter(|s| *s != "catalogue")
                    .map(str::to_string)
            } else {
                None
            };
            if let Some(n) = n {
                if !names.contains(&n) {
                    names.push(n);
                }
            }
        }
    }
    for n in embedded_idents(domain) {
        if !names.contains(&n) {
            names.push(n);
        }
    }
    names.sort();
    names.iter().filter_map(|n| find(domain, n)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    //: ★★`--facts` 是**前置**不是替换：给了自己的根，自带的与检出的仍在其后兜底
    //: （帮助文本写的就是「在自带的那份之前」）。于是这些用例跑在真检出里时，
    //: 路径上还会有仓自己的 `facts/`——那是**对的行为**，所以断言只看本用例造出来
    //: 的那几个根，而不是把环境当成空的。
    fn under<'a>(base: &Path, rs: &'a [PathBuf]) -> Vec<&'a PathBuf> {
        rs.iter().filter(|p| p.starts_with(base)).collect()
    }

    fn tmp(tag: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("fyfacts-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        std::fs::create_dir_all(&d).unwrap();
        d
    }

    fn entry(root: &Path, domain: &str, ident: &str, note: &str, rights: bool) {
        let d = root.join(domain);
        std::fs::create_dir_all(d.join(ident)).unwrap();
        std::fs::write(
            d.join(format!("{ident}.jsonld")),
            format!("{{\"fylite:device_id\":\"{ident}\",\"note\":\"{note}\"}}"),
        )
        .unwrap();
        if rights {
            std::fs::write(
                d.join(ident).join("rights.json"),
                format!("{{\"device\":\"{ident}\",\"ruling\":\"{note}\"}}"),
            )
            .unwrap();
        }
    }

    /// ★★优先级的单位是**条目**：文档与许可账必须同根。
    #[test]
    fn the_first_root_wins_the_whole_entry() {
        let base = tmp("whole");
        let (hi, lo) = (base.join("hi"), base.join("lo"));
        entry(&hi, "device", "east", "HIGH", true);
        entry(&lo, "device", "east", "LOW", true);
        entry(&lo, "device", "iter", "LOW", true);

        use_roots(Some(vec![hi.clone(), lo.clone()]));
        let e = find("device", "east").unwrap();
        assert_eq!(e.root, hi);
        let doc = e.read().unwrap();
        assert!(doc.contains("HIGH"), "{doc}");
        //: 许可账来自同一个根——这一条才是「不跨根拼」的实质
        let rp = e.rights_path().unwrap();
        assert!(rp.starts_with(&hi), "rights came from another root: {rp:?}");

        //: 低优先级的根补上高优先级没有的那台，不补它有的
        let ids: Vec<(String, PathBuf)> = entries("device")
            .into_iter()
            .filter(|e| e.root.starts_with(&base))
            .map(|e| (e.ident, e.root))
            .collect();
        assert_eq!(
            ids,
            vec![("east".into(), hi.clone()), ("iter".into(), lo.clone())]
        );
        use_roots(None);
    }

    /// ★被指名却不在的根要当场说：把「路径写错了」说成「语料里没有它」，两句话
    /// 指向完全不同的处置。
    #[test]
    fn a_named_root_that_is_not_there_is_named() {
        let missing = tmp("gone").join("nope");
        use_roots(Some(vec![missing.clone()]));
        let p = problems();
        assert!(p.iter().any(|s| s.contains("不存在")), "{p:?}");
        //: 它没有进搜索路径——而路径上剩下什么（检出的、自带的）不归本条管。
        assert!(!roots().contains(&missing));
        use_roots(None);
    }

    /// ★一个根被指两次只算一个：否则「是哪个根供的」会含糊成两个来源。
    #[test]
    fn a_root_named_twice_is_one_root() {
        let base = tmp("dup");
        let r = base.join("r");
        entry(&r, "device", "east", "ONE", true);
        use_roots(Some(vec![r.clone(), r.clone()]));
        let rs = roots();
        assert_eq!(under(&base, &rs).len(), 1, "{rs:?}");
        use_roots(None);
    }

    /// ★★★域目录下不是每个目录都是条目：fydoc 的 `device/tools/`（书的构建脚本）
    /// 在有形状判据之前会被列成第 14 台机器。
    #[test]
    fn a_directory_with_nothing_recognisable_is_not_an_entry() {
        let base = tmp("shape");
        std::fs::create_dir_all(base.join("device").join("tools")).unwrap();
        std::fs::write(base.join("device").join("tools").join("README.md"), "prose\n").unwrap();
        std::fs::create_dir_all(base.join("device").join("iter").join(ABOX)).unwrap();

        //: ★`--facts` 是前置不是替换，真检出的 `facts/` 仍在路径上——所以断言只看
        //: 本用例造出来的这两个名字，与本模块其它用例同一姿态。
        use_roots(Some(vec![base.clone()]));
        let names: Vec<String> = entries("device").into_iter().map(|e| e.ident).collect();
        assert!(names.contains(&"iter".to_string()), "{names:?}");
        assert!(!names.contains(&"tools".to_string()), "{names:?}");
        assert!(find("device", "tools").is_none());
    }

    /// ★fydoc 形状：有 `abox/` 就是一条条目，且认得出它的数据部分在哪。
    #[test]
    fn an_abox_makes_an_entry_and_is_reachable() {
        let base = tmp("abox");
        let a = base.join("device").join("iter").join(ABOX);
        std::fs::create_dir_all(&a).unwrap();
        use_roots(Some(vec![base]));
        let e = find("device", "iter").unwrap();
        assert_eq!(e.abox_path().unwrap(), a);
    }

    /// ★★许可账收敛进 FAIR 件：fydoc 那侧没有 `rights.json`，账在
    /// `abox/static/now/dataset_fair.jsonld`——同一个根，不是跨根拼。
    #[test]
    fn the_fair_record_serves_as_the_ledger() {
        let base = tmp("fair");
        let d = base.join("device").join("iter");
        let fair = FAIR.iter().fold(d.clone(), |acc, s| acc.join(s));
        std::fs::create_dir_all(fair.parent().unwrap()).unwrap();
        std::fs::write(&fair, "{}").unwrap();
        use_roots(Some(vec![base]));
        assert_eq!(find("device", "iter").unwrap().rights_path().unwrap(), fair);
    }

    /// ★两者都在时用本仓生成的那份——它是完整的（上游声明 + 本仓裁定）。
    #[test]
    fn the_generated_ledger_wins_over_the_fair_record() {
        let base = tmp("both");
        let d = base.join("device").join("iter");
        let fair = FAIR.iter().fold(d.clone(), |acc, s| acc.join(s));
        std::fs::create_dir_all(fair.parent().unwrap()).unwrap();
        std::fs::write(&fair, "{}").unwrap();
        std::fs::write(d.join(RIGHTS), "{}").unwrap();
        use_roots(Some(vec![base]));
        assert_eq!(find("device", "iter").unwrap().rights_path().unwrap(), d.join(RIGHTS));
    }
}

// ───────────────────────── experiment 域：一台机器的一发炮 ─────────────────────────
//
// ★★这一域比别的深一层：`experiment/<machine>/<shot>/`，而 [`find`] 与 [`entries`]
// 只认 `<域>/<标识>` 那一层。所以它有自己的两个函数，而不是把上面那两个改宽——
// 改宽的代价是每个域都要多回答一个「你有几层」，而只有这一域有第二层。
//
// 一发炮的目录里：`manifest.fyo.jsonld`（`fylite:slices` 逐片记时刻与文件）与逐时刻的
// `slice_<毫秒>ms.fyo.jsonld`。清单缺席时按文件名兜底——文件名里就写着毫秒。

/// 语料里的一发炮。
#[derive(Debug, Clone)]
pub struct Shot {
    pub machine: String,
    pub shot: String,
    /// 供它的那个根。
    pub root: PathBuf,
    /// `<root>/experiment/<machine>/<shot>`。
    pub dir: PathBuf,
}

impl Shot {
    /// 这发炮的清单（有则在）。
    pub fn manifest(&self) -> Option<PathBuf> {
        let p = self.dir.join("manifest.fyo.jsonld");
        p.is_file().then_some(p)
    }

    /// 逐片：时刻（秒）与文档路径，按时刻排序。
    ///
    /// 先读清单的 `fylite:slices`；没有清单就按文件名 `slice_<毫秒>ms` 兜底。
    /// ★两条路给同一个答案，所以调用方不必知道走的是哪一条。
    pub fn slices(&self) -> Vec<(f64, PathBuf)> {
        let mut out: Vec<(f64, PathBuf)> = Vec::new();
        if let Some(m) = self.manifest() {
            if let Ok(text) = std::fs::read_to_string(&m) {
                if let Ok(node) = crate::json::parse(&text) {
                    if let Some(list) = node
                        .as_map()
                        .and_then(|x| x.get("fylite:slices"))
                        .and_then(crate::document::Node::as_list)
                    {
                        for s in list {
                            let Some(sm) = s.as_map() else { continue };
                            let Some(t) = sm.get("fylite:time_s").and_then(crate::document::Node::as_f64) else {
                                continue;
                            };
                            let Some(doc) = sm.get("fylite:document").and_then(crate::document::Node::as_str) else {
                                continue;
                            };
                            let p = self.dir.join(doc);
                            if p.is_file() {
                                out.push((t, p));
                            }
                        }
                    }
                }
            }
        }
        if out.is_empty() {
            let Ok(rd) = std::fs::read_dir(&self.dir) else { return out };
            for e in rd.flatten() {
                let p = e.path();
                let Some(name) = p.file_name().and_then(|s| s.to_str()) else { continue };
                let Some(ms) = name.strip_prefix("slice_").and_then(|r| r.split("ms").next()) else {
                    continue;
                };
                if let Ok(v) = ms.parse::<f64>() {
                    out.push((v / 1000.0, p));
                }
            }
        }
        out.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
        out
    }
}

/// 一发具体的炮：第一个有 `experiment/<machine>/<shot>` 的根供出它。
pub fn shot(machine: &str, shot: &str) -> Option<Shot> {
    for r in roots() {
        let dir = r.join("experiment").join(machine).join(shot);
        if dir.is_dir() {
            return Some(Shot {
                machine: machine.to_string(),
                shot: shot.to_string(),
                root: r,
                dir,
            });
        }
    }
    None
}

/// 路径上的每一发炮（可按机器过滤），按机器、炮号排序，逐条决胜。
pub fn shots(machine: Option<&str>) -> Vec<Shot> {
    let mut out: Vec<Shot> = Vec::new();
    for r in roots() {
        let Ok(machines) = std::fs::read_dir(r.join("experiment")) else { continue };
        let mut dirs: Vec<PathBuf> = machines.flatten().map(|e| e.path()).filter(|p| p.is_dir()).collect();
        dirs.sort();
        for md in dirs {
            let Some(m) = md.file_name().and_then(|s| s.to_str()).map(str::to_string) else { continue };
            if machine.map(|want| want != m).unwrap_or(false) {
                continue;
            }
            let Ok(rd) = std::fs::read_dir(&md) else { continue };
            let mut shots: Vec<PathBuf> = rd.flatten().map(|e| e.path()).filter(|p| p.is_dir()).collect();
            shots.sort();
            for sd in shots {
                let Some(id) = sd.file_name().and_then(|s| s.to_str()).map(str::to_string) else { continue };
                if out.iter().any(|x| x.machine == m && x.shot == id) {
                    continue;
                }
                out.push(Shot { machine: m.clone(), shot: id, root: r.clone(), dir: sd });
            }
        }
    }
    out
}
