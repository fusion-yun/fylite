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
//! 3. 检出自己的 `facts/`（自可执行文件位置上溯探得），**排在自带的那份之前**——
//!    否则一份打包时冻结的语料会悄无声息地盖住刚拖回来的那一份；
//! 4. 发行版自带的那一份（`$FY_FACTS_BUNDLED`，打包时指定）。
//!
//! ★不存在的根**静默跳过**，被指名却不可用的根由 [`problems`] 报出。两者不同：
//! 「语料还没拖回来」是新检出的常态，而「这条路径设了、却不是语料」是一个值得
//! 当场说出来的错。
//!
//! ★★**与 Python 侧 `fylite.facts` 是有意的两份实现**，判据同 `_cli.json` 的三个
//! 解析器：一份规则、多处建出、一道闸子比对（`python/tests/test_facts_corpus.py`
//! 的 `test_the_two_resolvers_agree`）。命令行走的是本模块，Python 里的调用走那一份。

use std::path::{Path, PathBuf};

/// 搜索路径的环境变量。与 `$PATH` 用同一个分隔符——同一个概念，平台已经有写法了。
pub const FACTS_ENV: &str = "FY_FACTS_PATH";

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
}

impl Entry {
    /// 许可账的路径（存在才给）。
    pub fn rights_path(&self) -> Option<PathBuf> {
        let p = self.dir.as_ref()?.join("rights.json");
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

/// 检出自己的 `facts/`：自可执行文件位置上溯，找一个既有 `facts/` 又有 `python/`
/// 的目录。★判据要**两样**：只看 `facts/` 会把任何恰好有同名目录的祖先当成检出。
fn repo_facts() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let mut here: &Path = exe.parent()?;
    loop {
        let cand = here.join("facts");
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

/// 第一个带有 `<域>/<标识>` 的根，没有则 `None`。
///
/// 一条条目可以是一份文档（`<id>.jsonld`）、一个目录（`<id>/`，卡片与许可账），
/// 或两者都有——任一半在，这个根就答；**另一半取自同一个根**，绝不落到下一个。
pub fn find(domain: &str, ident: &str) -> Option<Entry> {
    for r in roots() {
        let doc = r.join(domain).join(format!("{ident}.jsonld"));
        let dir = r.join(domain).join(ident);
        let (has_doc, has_dir) = (doc.is_file(), dir.is_dir());
        if has_doc || has_dir {
            return Some(Entry {
                domain: domain.to_string(),
                ident: ident.to_string(),
                root: r,
                document: has_doc.then_some(doc),
                dir: has_dir.then_some(dir),
            });
        }
    }
    None
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
        let doc = std::fs::read_to_string(e.document.as_ref().unwrap()).unwrap();
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
}
