//! fyo 文档的约定 —— 语义键、`@type` ↔ IDS 名、fyo 布局与 IMAS DD 布局的互换、多 IDS 的束。
//!
//! ★★**两种布局，一棵树。** 「fyo 格式」是本仓的文档：JSON-LD 语义键（`@context`
//! `@id` `@type`）在前，正文用 IMAS DD 的键名，DD 没有名字的量带 `fylite:` 前缀
//! （`python/fylite/fyo.py`；`@type` 是 `fyo:<ids>`）。「IMAS DD 格式」是 imas-python /
//! imas-core 读写的那棵树：**只有** DD 的键，没有语义键，没有本地词——一个 IDS 一个
//! 顶层名，出现号（occurrence）跟在名后。两者的差别全在键上，所以互换是两个纯函数
//! （[`to_dd`] / [`from_dd`]），不是两套写法。
//!
//! ★`SEMANTIC_KEYS` 与 `python/fylite/engine/manifest.py` 逐字相同（含 SpData 的
//! `$` 别名）——那是「语义通道离开内容面」这条规则在两侧的同一份拼写。

use crate::document::{Array, ArrayData, Map, MergePolicy, Node};
use crate::ids_meta::{IdsMeta, Kind};

pub const FYO_PREFIX: &str = "https://fusion-yun.github.io/fyo/latest/";
pub const FYLITE_PREFIX: &str = "urn:fylite:";

/// JSON-LD 关键字与它们的 SpData `$` 别名。
pub const SEMANTIC_KEYS: [&str; 7] =
    ["@context", "@id", "@type", "$context", "$id", "$type", "$onto"];

/// 出现号（IMAS occurrence）在 fyo 文档里的键；缺席即 0。
pub const OCCURRENCE_KEY: &str = "fylite:occurrence";

pub fn is_semantic_key(k: &str) -> bool {
    SEMANTIC_KEYS.contains(&k)
}

/// 带前缀的本地词（`fylite:x`、`fyo:x`……）——DD 里没有的名字。
pub fn is_prefixed_key(k: &str) -> bool {
    k.contains(':')
}

/// 每份文档都带的 `@context`。
pub fn context() -> Node {
    let mut m = Map::new();
    m.insert("fyo", FYO_PREFIX.into());
    m.insert("fylite", FYLITE_PREFIX.into());
    Node::Map(m)
}

/// 一份空的 fyo 文档：`@context` / `@id` / `@type: fyo:<ids>`。
pub fn new_document(ids: &str, id: &str) -> Node {
    let mut m = Map::new();
    m.insert("@context", context());
    m.insert("@id", id.into());
    m.insert("@type", format!("fyo:{ids}").into());
    Node::Map(m)
}

/// 文档说的是哪个 IDS：`@type: fyo:equilibrium` → `equilibrium`；A-Box 的 `_ids` 也认。
/// A document's own name, for a message that has to point at it: its `@type`
/// minus the `fyo:` prefix when it has one, else its `@id`, else `<untyped>`.
///
/// ★Used by the IMAS writers to NAME what they skipped.  "a document without a
/// known `@type`" told the reader that something was wrong and nothing about
/// which thing.
pub fn doc_label(doc: &Node) -> String {
    let get = |k: &str| doc.as_map().and_then(|m| m.get(k)).and_then(Node::as_str);
    if let Some(t) = get("@type") {
        return t.strip_prefix("fyo:").unwrap_or(t).to_string();
    }
    get("@id").unwrap_or("<untyped>").to_string()
}

pub fn ids_of(doc: &Node) -> Option<String> {
    let m = doc.as_map()?;
    if let Some(t) = m.get("@type").and_then(Node::as_str).or_else(|| m.get("$type").and_then(Node::as_str)) {
        if let Some(rest) = t.strip_prefix("fyo:") {
            let name = rest.split('/').next().unwrap_or(rest);
            if IdsMeta::get(name).is_some() {
                return Some(name.to_string());
            }
            //: ★★★fydoc 的 A-Box 用**大驼峰**声明类型（`fyo:Wall` / `fyo:PfActive`），
            //: 而 IDS 名是蛇形（`wall` / `pf_active`）。不折算这一步，`@type` 认不出来就
            //: 悄悄落到 `_ids`——而 A-Box 里没有 `_ids`，于是这份源**一条也不进束**，
            //: 产物是一份 317 字节的空 netCDF，**退出码 0**。实测：挂 fydoc 直接取
            //: EAST 70754 的 wall + pf_active，得到的就是那个空件。
            let snake = camel_to_snake(name);
            if IdsMeta::get(&snake).is_some() {
                return Some(snake);
            }
        }
    }
    if let Some(i) = m.get("_ids").and_then(Node::as_str) {
        return Some(i.to_string());
    }
    None
}

/// `PfActive` -> `pf_active`。只在 `@type` 的局部名上用。
///
/// ★只做大驼峰→蛇形这一件事：已经是蛇形的原样返回（`wall` -> `wall`），
/// 所以两种写法都认，而不是把一种翻译成另一种。
fn camel_to_snake(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 4);
    for (i, c) in s.chars().enumerate() {
        if c.is_ascii_uppercase() {
            if i != 0 {
                out.push('_');
            }
            out.push(c.to_ascii_lowercase());
        } else {
            out.push(c);
        }
    }
    out
}

pub fn occurrence_of(doc: &Node) -> i64 {
    doc.get(OCCURRENCE_KEY).and_then(Node::as_i64).unwrap_or(0)
}

/// 去掉语义键与带前缀的本地键 —— IMAS DD 布局的那棵树。
///
/// 返回被丢掉的路径，好让调用方能说「这份文档里有 N 个 IMAS 不认的量没写出去」，
/// 而不是静默地少了。
pub fn to_dd(doc: &Node) -> (Node, Vec<String>) {
    let mut dropped = Vec::new();
    let out = strip(doc, String::new(), &mut dropped);
    (out, dropped)
}

fn strip(n: &Node, prefix: String, dropped: &mut Vec<String>) -> Node {
    match n {
        Node::Map(m) => {
            let mut out = Map::new();
            for (k, v) in m.iter() {
                let p = if prefix.is_empty() { k.to_string() } else { format!("{prefix}/{k}") };
                if is_semantic_key(k) || is_prefixed_key(k) || k == "_ids" {
                    dropped.push(p);
                    continue;
                }
                out.insert(k, strip(v, p, dropped));
            }
            Node::Map(out)
        }
        Node::List(l) => Node::List(l.iter().enumerate()
            .map(|(i, v)| strip(v, format!("{prefix}/{i}"), dropped)).collect()),
        other => other.clone(),
    }
}

/// 给一棵 DD 树套上 fyo 的语义键。
pub fn from_dd(ids: &str, tree: Node, id: &str, occurrence: i64) -> Node {
    let mut doc = new_document(ids, id);
    if occurrence != 0 {
        doc.as_map_mut().unwrap().insert(OCCURRENCE_KEY, Node::Int(occurrence));
    }
    if let Node::Map(m) = tree {
        let d = doc.as_map_mut().unwrap();
        for (k, v) in m.into_iter() {
            d.insert(k, v);
        }
    }
    doc
}

/// IMAS 侧的一个 IDS 的名字带出现号：`equilibrium`、`equilibrium_1`（imas-core 的链接名）。
pub fn ids_key(ids: &str, occurrence: i64) -> String {
    if occurrence == 0 { ids.to_string() } else { format!("{ids}_{occurrence}") }
}

/// `equilibrium_1` → (`equilibrium`, 1)；没有已知 IDS 前缀则原样、0。
pub fn split_ids_key(key: &str) -> (String, i64) {
    if let Some((base, n)) = key.rsplit_once('_') {
        if let Ok(occ) = n.parse::<i64>() {
            if IdsMeta::get(base).is_some() {
                return (base.to_string(), occ);
            }
        }
    }
    (key.to_string(), 0)
}

// --------------------------------------------------------------------------
// bundle
// --------------------------------------------------------------------------

/// 若干份 fyo 文档 —— 一个数据源（一个文件、一炮）通常不止一个 IDS。
#[derive(Debug, Clone, Default)]
pub struct Bundle {
    pub docs: Vec<Node>,
}

impl Bundle {
    pub fn new() -> Self {
        Bundle { docs: Vec::new() }
    }

    pub fn one(doc: Node) -> Self {
        Bundle { docs: vec![doc] }
    }

    pub fn is_empty(&self) -> bool {
        self.docs.is_empty()
    }

    pub fn push(&mut self, doc: Node) {
        self.docs.push(doc);
    }

    /// `(ids, occurrence)` 逐份。
    pub fn keys(&self) -> Vec<(String, i64)> {
        self.docs.iter().map(|d| (ids_of(d).unwrap_or_default(), occurrence_of(d))).collect()
    }

    pub fn get(&self, ids: &str) -> Option<&Node> {
        self.get_occ(ids, 0)
    }

    pub fn get_occ(&self, ids: &str, occurrence: i64) -> Option<&Node> {
        self.docs.iter().find(|d| ids_of(d).as_deref() == Some(ids) && occurrence_of(d) == occurrence)
    }

    pub fn get_mut(&mut self, ids: &str, occurrence: i64) -> Option<&mut Node> {
        self.docs.iter_mut().find(|d| ids_of(d).as_deref() == Some(ids) && occurrence_of(d) == occurrence)
    }

    /// 合并另一束：同一 `(ids, occurrence)` 的文档树对树合并，其余追加。
    pub fn merge(&mut self, other: Bundle, policy: MergePolicy) {
        self.merge_with(other, policy, None);
    }

    /// [`Bundle::merge`]，结构数组按 `key` 对齐（见 [`Node::merge_with`]）。
    pub fn merge_with(&mut self, other: Bundle, policy: MergePolicy, key: Option<&str>) {
        for doc in other.docs {
            let k = (ids_of(&doc), occurrence_of(&doc));
            match k.0.as_deref().and_then(|i| self.get_mut(i, k.1)) {
                Some(slot) => slot.merge_with(doc, policy, key),
                None => self.docs.push(doc),
            }
        }
    }

    /// 束的容器形：`{ "<ids>[_<occ>]": <文档> }`。单份文档不套容器。
    pub fn to_node(&self) -> Node {
        if self.docs.len() == 1 {
            return self.docs[0].clone();
        }
        let mut m = Map::new();
        for (d, (ids, occ)) in self.docs.iter().zip(self.keys()) {
            let key = if ids.is_empty() { format!("document_{}", m.len()) } else { ids_key(&ids, occ) };
            m.insert(key, d.clone());
        }
        Node::Map(m)
    }

    /// 反过来：根上有 `@type` 是一份文档；否则每个值是一份（没有 `@type` 的按键名
    /// 当 DD 树读，键名给 IDS 与出现号）。
    pub fn from_node(n: Node) -> Bundle {
        let m = match n {
            Node::Map(m) => m,
            _ => return Bundle::new(),
        };
        if m.get("@type").is_some() || m.get("$type").is_some() || m.get("_ids").is_some() {
            return Bundle::one(Node::Map(m));
        }
        let mut b = Bundle::new();
        for (k, v) in m.into_iter() {
            if is_semantic_key(&k) {
                continue;
            }
            if let Node::Map(vm) = &v {
                if vm.get("@type").is_some() || vm.get("_ids").is_some() {
                    b.push(v);
                    continue;
                }
                let (ids, occ) = split_ids_key(&k);
                if IdsMeta::get(&ids).is_some() {
                    b.push(from_dd(&ids, v, &format!("fylite:{ids}/{k}"), occ));
                }
            }
        }
        b
    }
}

// --------------------------------------------------------------------------
// DD normalisation — what an IMAS writer needs before it can lay a tree out
// --------------------------------------------------------------------------

/// 一次归一化说了什么。
#[derive(Debug, Default, Clone)]
pub struct DdReport {
    /// 被丢掉的键（语义键、本地词、DD 里没有的路径）。
    pub dropped: Vec<String>,
    /// 被从标量提成一元数组的路径（DD 说它是一维）。
    pub promoted: Vec<String>,
    /// 合成出来的路径（根 `time`、`homogeneous_time`）。
    pub synthesized: Vec<String>,
    /// 搬了家的路径（`from -> to`），见 [`RELOCATIONS`]。
    pub relocated: Vec<String>,
    /// 从**一元列表**里取出来的结构：DD 说这里是一个结构，文档给了一个只有一个
    /// 元素的列表。见 [`build_dd`] 里 `Kind::Structure` 那一支。
    pub unwrapped: Vec<String>,
    /// 算出来的 DD 叶子（`目标 = a * b`），见 [`DERIVATIONS`]。
    pub derived: Vec<String>,
    /// 由名字换成 DD 索引的叶子，见 [`ENUM_NAMES`]。
    pub named: Vec<String>,
}

/// **同一个量在 fyo 与 DD 里挂的地方不同**时，搬家的那张表。
///
/// ★★2026-09-04 实测：EAST 的 `wall` 文档把 `limiter` 与 `vessel` 挂在 IDS 顶层，
/// 而 DD 4.1.1 的家在 `wall/description_2d[]/` 之下。归一化据实把顶层那两支当作
/// 「DD 不认的路径」丢掉——**丢得是响的**（报告里逐条点名），但产物是一份只剩
/// `ids_properties` 的空 `wall`。一份空的 IDS 比一个错误更坏：它看着像结果。
///
/// ★**一张表，不是一条推断规则**。「顶层的键在某个中间层下面找得到同名的，就搬
/// 过去」听着通用，实则是猜：DD 里同名而不同义的路径不止一处，猜错了会把一支数据
/// 搬到一个**看着合理**的错地方，而且照样不报错。所以只搬写在这里的、逐条有据的
/// 那几支，其余仍旧丢掉并报告。
///
/// 每条的判据（`apply_relocations` 逐条核）：源路径在文档里**在**、目标路径在 DD 里
/// **有**、而源路径在 DD 里**没有**。三条缺一即不搬——那说明这份文档已经是 DD 的形，
/// 或者这条表项过期了。
pub const RELOCATIONS: &[(&str, &str, &str)] = &[
    //: (IDS, 文档里的路径, DD 里的家)
    ("wall", "limiter", "description_2d/limiter"),
    ("wall", "vessel", "description_2d/vessel"),
];

/// **DD 用整数索引、fyo 用名字**的那些叶子。
///
/// ★★DD 的 `pf_active/coil/element/geometry/geometry_type` 是一个整数；fylite 的装置
/// 文档写 `"rectangle"`。名字读得懂而 DD 读不懂，于是整支被丢——实测 2026-09-07，
/// EAST 的 14 个线圈元件全数丢了几何类型。
///
/// ★**取值的出处**：IMAS Data Dictionary 源码
/// （`iterorganization/imas-data-dictionary`，`schemas/utilities/dd_support.xsd` 的
/// `outline_2d_geometry_static` —— `pf_coils_elements` 用的正是这个类型）。它的
/// `geometry_type` 上写着，逐字：
///
/// > Type used to describe the element shape (1:'outline', 2:'rectangle',
/// > 3:'oblique', 4:'arcs of circle, 5: 'annulus', 6 : 'thick line')
///
/// ★读自该仓默认分支 f5d44e8（2026-09-04）；本仓的 DD 表标 4.1.1，两者的版本关系
/// 未逐条核过。用得上的那一个（`rectangle = 2`）另有**独立佐证**：本生态自己的
/// `facts/device/west/abox/static/now/pf_active.jsonld`（`metis2fyo.py` 生成，自述
/// 「IMAS DD v4 shape」）里每一个元件都是 `geometry_type: 2` 配一个 `rectangle` 块。
///
/// ★六个名字全列在这里，**不是**因为都用得上，而是因为半张表比整张表更容易被
/// 后来的人误读成「其余的没有索引」。
pub const ENUM_NAMES: &[(&str, &str, &[(&str, i64)])] = &[
    ("pf_active", "coil/element/geometry/geometry_type", GEOMETRY_TYPE),
    ("wall", "description_2d/vessel/unit/element/geometry/geometry_type", GEOMETRY_TYPE),
];

/// `outline_2d_geometry_static` 的形状词表，见 [`ENUM_NAMES`] 的出处说明。
pub const GEOMETRY_TYPE: &[(&str, i64)] = &[
    ("outline", 1), ("rectangle", 2), ("oblique", 3),
    ("arcs of circle", 4), ("arcs_of_circle", 4),
    ("annulus", 5), ("thick line", 6), ("thick_line", 6),
];

/// **同一个物理量，fyo 与 DD 用不同的定义**时，换算的那张表。
///
/// ★★与 [`RELOCATIONS`] 是两件事：那张表只搬位置，值一字不动；这张表**要算**。
/// DD 的 `tf` 没有 `b0`，它有 `b_field_phi_vacuum_r` —— 真空环向场乘以它所在的半径，
/// 即 R0·B0。fylite 的装置牌写 `tf/r0` 与 `tf/b0` 两个数；`b0` 裸着写而 DD 无家，
/// 于是被丢（实测 2026-09-07）。
///
/// ★每条的判据（[`apply_derivations`] 逐条核）：两个源都在、目标在 DD 里有、而源
/// 路径在 DD 里没有。三条缺一即不算——那说明这份文档已经是 DD 的形，或这条过期了。
/// 算完**不删源**：`b0` 与 `r0` 仍是 fylite 侧读者要的两个数，只是它们不进数据入口。
pub const DERIVATIONS: &[(&str, [&str; 2], &str)] = &[
    //: (IDS, [源 a, 源 b], DD 里的目标叶子) —— 目标 = a * b
    //:
    //: ★目标写到 `/data` 上，不是写到 `b_field_phi_vacuum_r` 上：DD 那一支是一个
    //: **信号结构**（`data` 随 `time` 走），不是一个裸浮点。写在结构上会被整支丢掉
    //: ——第一版就是这么写的，闸子当场抓住。
    ("tf", ["r0", "b0"], "b_field_phi_vacuum_r/data"),
];

/// 按 [`DERIVATIONS`] 算出 DD 要的那个量，逐条记进报告。
fn apply_derivations(ids: &str, tree: &mut Node, meta: &IdsMeta, report: &mut DdReport) {
    for (which, from, to) in DERIVATIONS {
        if *which != ids || meta.has(from[0]) && meta.has(from[1]) || !meta.has(to) {
            continue;
        }
        let (Some(a), Some(b)) = (tree.get(from[0]).and_then(Node::as_f64),
                                  tree.get(from[1]).and_then(Node::as_f64)) else { continue };
        if tree.get(to).is_some() {
            continue;
        }
        if tree.set(to, Node::Float(a * b)).is_ok() {
            report.derived.push(format!("{to} = {} * {}", from[0], from[1]));
        }
    }
}

/// 按 [`ENUM_NAMES`] 把名字换成 DD 的索引，逐条记进报告。
fn apply_enum_names(ids: &str, tree: &mut Node, report: &mut DdReport) {
    for (which, path, table) in ENUM_NAMES {
        if *which != ids {
            continue;
        }
        for (name, index) in *table {
            for p in paths_matching(tree, path) {
                if tree.get(&p).and_then(Node::as_str) == Some(*name)
                    && tree.set(&p, Node::Int(*index)).is_ok()
                {
                    report.named.push(format!("{p} = {index} ({name})"));
                }
            }
        }
    }
}

/// 树里所有匹配一条**不带下标**的路径的实际路径（结构数组逐元素展开）。
fn paths_matching(tree: &Node, pattern: &str) -> Vec<String> {
    fn walk(n: &Node, segs: &[&str], at: String, out: &mut Vec<String>) {
        let Some((head, rest)) = segs.split_first() else { out.push(at); return };
        let Some(child) = n.as_map().and_then(|m| m.get(*head)) else { return };
        let here = if at.is_empty() { head.to_string() } else { format!("{at}/{head}") };
        match child {
            Node::List(l) => for (i, item) in l.iter().enumerate() {
                walk(item, rest, format!("{here}/{i}"), out);
            },
            other => walk(other, rest, here, out),
        }
    }
    let segs: Vec<&str> = pattern.split('/').collect();
    let mut out = Vec::new();
    walk(tree, &segs, String::new(), &mut out);
    out
}

/// 把 `wall` 的元件几何换成 DD 要的 **outline**，原矩形留作参考。
///
/// ★★DD 的真空室 / 限制器元件只有一种写法：`element/outline/{r,z}`（「Irregular
/// outline of the element. Repeat the first point since this is a closed
/// contour」——DD 原文）。它**没有** `geometry`，也没有 `rectangle`。fylite 的装置牌
/// 借了 `pf_active` 线圈元件的参数化写法，于是整支被丢：实测 2026-09-07，EAST 的
/// 90 个真空室元件几何全数丢失，`wall.h5` 只剩 8 个叶子。
///
/// ★**角点不是这里算的**：它是内核 `kernels::element_filaments` 的那一个映射，逐字
/// 照搬 —— 局部 (u, v) 走 `r = r0 + u + v·cos a2`、`z = z0 + v·sin a2`，再绕 (r0, z0)
/// 转 a1。两处各写一份，就是两份可以分歧的几何。
///
/// ★**倾角在 unit 上也在 element 上**，读法与 `device.py` 同：element 先，unit 次，
/// 都没有才用缺省。`a2` 的缺省是 **90**（一个正常矩形），不是 0 —— efund 的 deck
/// 用同一条替换，理由相同：a2 = 0 不是退化矩形，是缺值。
///
/// ★★**没有做的事：把相邻元件并成内外两层轮廓。** 那要求相邻矩形共边，而 EAST 的
/// 不共：实测同一层内相邻元件的最近角点距离中位数 **9–10 mm**、最大 **40 mm**
/// （inner_shell / outer_shell 各 40 段，1e-6 容差下 160 条边里只有 4 条真正共用）。
/// 跨过一厘米把它们缝起来，就是往产物里写数据里没有的几何。所以这里按 DD 自己的
/// 单位办：**一个元件一条闭合轮廓**，逐点精确，一个也不丢。层轮廓要不要、按什么
/// 判据缝，是另一个决定。
fn wall_outlines(tree: &mut Node, derived: &mut Vec<String>) {
    let Some(d2) = tree.as_map_mut().and_then(|m| m.get_mut("description_2d")) else { return };
    let slices: &mut Vec<Node> = match d2 {
        Node::List(l) => l,
        one => { rewrite_units(one, derived); return }
    };
    for s in slices.iter_mut() {
        rewrite_units(s, derived);
    }
}

fn rewrite_units(slice: &mut Node, derived: &mut Vec<String>) {
    for section in ["vessel", "limiter"] {
        let Some(units) = slice.as_map_mut().and_then(|m| m.get_mut(section)) else { continue };
        let Some(units) = units.as_map_mut().and_then(|m| m.get_mut("unit")) else { continue };
        let list: Vec<&mut Node> = match units {
            Node::List(l) => l.iter_mut().collect(),
            one => vec![one],
        };
        for (iu, unit) in list.into_iter().enumerate() {
            let (ua, ua2) = (num(unit, "fylite:a1"), num(unit, "fylite:a2"));
            let Some(els) = unit.as_map_mut().and_then(|m| m.get_mut("element")) else { continue };
            let elist: Vec<&mut Node> = match els {
                Node::List(l) => l.iter_mut().collect(),
                one => vec![one],
            };
            for (ie, el) in elist.into_iter().enumerate() {
                if el.get("outline").is_some() {
                    continue;                      //: already the DD's shape
                }
                let (ea, ea2) = (num(el, "fylite:a1").or(ua), num(el, "fylite:a2").or(ua2));
                let Some(rect) = el.get("geometry/rectangle").cloned() else { continue };
                let g = |k: &str| rect.get(k).and_then(Node::as_f64);
                let (Some(r0), Some(z0), Some(w), Some(h)) =
                    (g("r"), g("z"), g("width"), g("height")) else { continue };
                let (r, z) = rectangle_outline(r0, z0, w, h, ea.unwrap_or(0.0), ea2.unwrap_or(90.0));
                let _ = el.set("outline/r", Node::Array(Array::f64(vec![r.len()], r).unwrap()));
                let _ = el.set("outline/z", Node::Array(Array::f64(vec![z.len()], z).unwrap()));
                //: ★原矩形留作参考，改挂到本地名下：DD 的 wall 元件没有 `geometry`，
                //: 裸着留就是声称一个它没有的出处（也照旧会被丢）。
                if let Some(m) = el.as_map_mut() {
                    if let Some(geom) = m.remove("geometry") {
                        m.insert("fylite:geometry", geom);
                    }
                }
                derived.push(format!(
                    "description_2d/{section}/unit/{iu}/element/{ie}/outline \
                     (from fylite:geometry/rectangle, 5 points closed)"));
            }
        }
    }
}

fn num(n: &Node, key: &str) -> Option<f64> {
    n.get(key).and_then(Node::as_f64)
}

/// 一个（可倾斜的）矩形的四个角，首点重复一次以闭合。
///
/// 逐字照搬内核 `kernels::element_filaments` 的映射（那里是逐格取样，这里取
/// u = ±w/2、v = ±h/2 四个角），逆时针一圈。
fn rectangle_outline(r0: f64, z0: f64, w: f64, h: f64, a: f64, a2: f64)
                     -> (Vec<f64>, Vec<f64>) {
    let rad = std::f64::consts::PI / 180.0;
    let (ca2, sa2) = ((a2 * rad).cos(), (a2 * rad).sin());
    let (ca, sa) = ((a * rad).cos(), (a * rad).sin());
    let (mut rr, mut zz) = (Vec::with_capacity(5), Vec::with_capacity(5));
    for (u, v) in [(-w / 2.0, -h / 2.0), (w / 2.0, -h / 2.0),
                   (w / 2.0, h / 2.0), (-w / 2.0, h / 2.0)] {
        let (mut r, mut z) = (r0 + u + v * ca2, z0 + v * sa2);
        if a != 0.0 {
            let (dr, dz) = (r - r0, z - z0);
            r = r0 + dr * ca - dz * sa;
            z = z0 + dr * sa + dz * ca;
        }
        rr.push(r);
        zz.push(z);
    }
    //: DD: "Repeat the first point since this is a closed contour"
    rr.push(rr[0]);
    zz.push(zz[0]);
    (rr, zz)
}

/// 按 [`RELOCATIONS`] 把该搬的支搬到 DD 的位置上，逐条记进报告。
///
/// ★目标里的 `description_2d` 在 DD 里是**结构数组**，所以搬进去的是它的第 0 个
/// 元素——与 `build_dd` 对「DD 说数组而文档给映射」的处置同一条（那里记 promoted）。
fn apply_relocations(ids: &str, tree: &mut Node, meta: &IdsMeta, report: &mut DdReport) {
    for (which, from, to) in RELOCATIONS {
        if *which != ids {
            continue;
        }
        let Some(m) = tree.as_map() else { return };
        if !m.contains_key(*from) || meta.has(from) || !meta.has(to) {
            continue;
        }
        let Some(value) = tree.as_map_mut().and_then(|m| m.remove(*from)) else { continue };
        //: `a/b` -> 在 `a` 这个结构数组的第 0 个元素里放 `b`
        let (head, tail) = to.split_once('/').unwrap_or((to, ""));
        let slot = tree.as_map_mut().unwrap();
        let elem = match slot.remove(head) {
            Some(Node::List(mut l)) => {
                if l.is_empty() { l.push(Node::map()); }
                Node::List(l)
            }
            Some(other) => Node::List(vec![other]),
            None => Node::List(vec![Node::map()]),
        };
        let Node::List(mut items) = elem else { continue };
        if tail.is_empty() {
            items[0] = value;
        } else if let Some(im) = items[0].as_map_mut() {
            im.insert(tail, value);
        }
        slot.insert(head, Node::List(items));
        report.relocated.push(format!("{from} -> {to}"));
    }
}

/// 把一份 fyo 文档整理成 imas-python 会认的 DD 树。
///
/// * 去掉语义键与本地词；去掉 DD 不认的路径（**记在报告里**，不是静默）；
/// * DD 说一维而文档给了标量的，提成一元数组（`vacuum_toroidal_field/b0` 在本仓的
///   文档里是一个数）；
/// * 缺 `ids_properties/homogeneous_time` 的补上：有时间片就 1（齐次），否则 2（常量）；
/// * 齐次时间下缺根 `time` 的，从时间片的 `time` 合成。
pub fn dd_normalize(ids: &str, doc: &Node, meta: &IdsMeta) -> (Node, DdReport) {
    //: ★元件几何换成 DD 的 outline 要在 `to_dd` **之前**：倾角 `fylite:a1` / `a2`
    //: 是本地词，`to_dd` 把本地词一律去掉（记进 dropped）。放在它之后，倾角已经
    //: 不在树上了，四个角会按 0°/90° 算出来——形状对，位置错，而且不报错。
    let mut derived = Vec::new();
    let doc = &if ids == "wall" {
        let mut src = doc.clone();
        wall_outlines(&mut src, &mut derived);
        src
    } else {
        doc.clone()
    };
    let (mut tree, dropped) = to_dd(doc);
    let mut report = DdReport { dropped, derived, ..Default::default() };
    //: ★搬家在丢弃**之前**：否则该搬的那几支已经被当作「DD 不认的路径」丢掉了。
    //: 换算与改名同理 —— 三者都要在 `walk_dd` 之前动手。
    apply_relocations(ids, &mut tree, meta, &mut report);
    apply_derivations(ids, &mut tree, meta, &mut report);
    apply_enum_names(ids, &mut tree, &mut report);
    let mut out = Node::map();
    walk_dd(meta, &tree, String::new(), &mut out, &mut report);

    // homogeneous_time / time
    let has_ht = out.get("ids_properties/homogeneous_time").is_some();
    let dyn_aos: Vec<&crate::ids_meta::Entry> = meta.entries().iter()
        .filter(|e| e.kind == Kind::StructArray && !e.path.contains('/') && meta.has(&format!("{}/time", e.path)))
        .collect();
    let mut slice_times: Vec<f64> = Vec::new();
    for e in &dyn_aos {
        if let Some(Node::List(l)) = out.get(&e.path) {
            let ts: Vec<f64> = l.iter().filter_map(|s| s.get("time").and_then(Node::as_f64)).collect();
            if ts.len() == l.len() && !ts.is_empty() && slice_times.is_empty() {
                slice_times = ts;
            }
        }
    }
    let has_root_time = out.get("time").map(|t| t.to_f64_vec().map(|v| !v.is_empty()).unwrap_or(false)).unwrap_or(false);
    if !has_ht {
        let ht = if has_root_time || !slice_times.is_empty() { 1 } else { 2 };
        out.set("ids_properties/homogeneous_time", Node::Int(ht)).ok();
        report.synthesized.push("ids_properties/homogeneous_time".into());
    }
    let ht = out.get("ids_properties/homogeneous_time").and_then(Node::as_i64).unwrap_or(2);
    if ht == 1 && !has_root_time && !slice_times.is_empty() && meta.has("time") {
        out.set("time", Node::Array(Array::vec_f64(slice_times))).ok();
        report.synthesized.push("time".into());
    }
    //: `ids_properties` 要排在最前 —— 与 DD 一样的顺序，读的人才好找
    if let Node::Map(m) = &mut out {
        if let Some(props) = m.remove("ids_properties") {
            let mut fresh = Map::new();
            fresh.insert("ids_properties", props);
            for (k, v) in std::mem::take(m).into_iter() {
                fresh.insert(k, v);
            }
            *m = fresh;
        }
    }
    (out, report)
}

fn walk_dd(meta: &IdsMeta, n: &Node, path: String, out: &mut Node, report: &mut DdReport) {
    if let Some(built) = build_dd(meta, n, &path, report) {
        *out = built;
    }
}

/// 自底向上造 DD 树：映射造映射、结构数组造列表、叶子按 DD 的种类与维数矫正。
fn build_dd(meta: &IdsMeta, n: &Node, path: &str, report: &mut DdReport) -> Option<Node> {
    let m = n.as_map()?;
    let mut out = Map::new();
    for (k, v) in m.iter() {
        let p = if path.is_empty() { k.to_string() } else { format!("{path}/{k}") };
        let entry = match meta.entry(&p) {
            Some(e) => e,
            None => { report.dropped.push(p); continue; }
        };
        match entry.kind {
            Kind::Structure => {
                //: ★★DD 说一个结构，文档给了**一元列表**。这是 `Kind::StructArray`
                //: 那一支的镜像（那里接受「DD 说数组而文档给映射」，记 promoted），
                //: 而这一支从前直接丢掉整支。
                //:
                //: ★实测（2026-09-07）：DD 把 `flux_loop/position` 写成**结构数组**
                //: （一条环可以穿过好几个点），把 `b_field_pol_probe/position` 写成
                //: **一个结构**（一个探针在一个点上）；fylite 的装置文档两者都写成
                //: `[{r,z}]`。于是环对了、探针错了 —— EAST 的 79 个探针位置全数
                //: 静默丢失。
                //:
                //: ★**只解一元的**。两个以上元素而 DD 只要一个，是真的装不下：
                //: 取第一个就是悄悄丢掉其余，那比丢掉整支更坏。那一种仍旧丢弃并报告。
                let one = match v {
                    Node::List(l) if l.len() == 1 => {
                        report.unwrapped.push(p.clone());
                        Some(&l[0])
                    }
                    Node::List(_) => None,
                    other => Some(other),
                };
                match one.and_then(|n| build_dd(meta, n, &p, report)) {
                    Some(sub) => { out.insert(k, sub); }
                    None => report.dropped.push(p),
                }
            }
            Kind::StructArray => match v {
                Node::List(l) => {
                    let items: Vec<Node> = l.iter().map(|item|
                        build_dd(meta, item, &p, report).unwrap_or_else(Node::map)).collect();
                    out.insert(k, Node::List(items));
                }
                Node::Map(_) => {
                    //: a bare mapping where the DD has an array: element 0
                    let item = build_dd(meta, v, &p, report).unwrap_or_else(Node::map);
                    out.insert(k, Node::List(vec![item]));
                    report.promoted.push(p);
                }
                _ => report.dropped.push(p),
            },
            _ => match coerce_leaf(&entry, v) {
                Some((leaf, promoted)) => {
                    if promoted {
                        report.promoted.push(p.clone());
                    }
                    out.insert(k, leaf);
                }
                None => report.dropped.push(p),
            },
        }
    }
    Some(Node::Map(out))
}

fn coerce_leaf(entry: &crate::ids_meta::Entry, v: &Node) -> Option<(Node, bool)> {
    match entry.kind {
        Kind::Str => match (entry.ndim, v) {
            (0, Node::Str(_)) => Some((v.clone(), false)),
            (0, Node::Array(a)) if a.as_str().map(|s| s.len() == 1).unwrap_or(false) =>
                Some((Node::Str(a.as_str().unwrap()[0].clone()), false)),
            (1, Node::Array(a)) if a.as_str().is_some() => Some((v.clone(), false)),
            (1, Node::Str(s)) => Some((Node::Array(Array::str(vec![1], vec![s.clone()]).ok()?), true)),
            (1, Node::List(l)) if l.iter().all(|x| x.as_str().is_some()) => {
                let s: Vec<String> = l.iter().map(|x| x.as_str().unwrap().to_string()).collect();
                Some((Node::Array(Array::str(vec![s.len()], s).ok()?), false))
            }
            _ => None,
        },
        Kind::Int | Kind::Float | Kind::Complex => {
            if entry.ndim == 0 {
                let x = v.as_f64()?;
                return Some((if entry.kind == Kind::Int { Node::Int(x as i64) } else { Node::Float(x) }, false));
            }
            match v {
                Node::Array(a) if a.is_numeric() => {
                    if a.ndim() == entry.ndim {
                        Some((v.clone(), false))
                    } else if a.ndim() == 0 || (a.len() == 1 && entry.ndim == 1) {
                        Some((Node::Array(Array { shape: vec![1], data: a.data.clone() }), true))
                    } else {
                        None
                    }
                }
                Node::Int(_) | Node::Float(_) if entry.ndim == 1 => {
                    let x = v.as_f64()?;
                    let data = if entry.kind == Kind::Int { ArrayData::I64(vec![x as i64]) } else { ArrayData::F64(vec![x]) };
                    Some((Node::Array(Array { shape: vec![1], data }), true))
                }
                Node::List(l) if l.is_empty() => Some((Node::Array(Array { shape: vec![0; entry.ndim.max(1)],
                    data: if entry.kind == Kind::Int { ArrayData::I64(vec![]) } else { ArrayData::F64(vec![]) } }), false)),
                _ => None,
            }
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn to_dd_strips_semantic_and_prefixed_keys_and_says_so() {
        let mut d = new_document("equilibrium", "fylite:equilibrium/x");
        d.set("time_slice/0/global_quantities/ip", 1.0.into()).unwrap();
        d.set("fylite:limiter/r", vec![1.0].into()).unwrap();
        d.set("time_slice/0/fylite:extra", 2.0.into()).unwrap();
        let (dd, dropped) = to_dd(&d);
        assert!(dd.get("@type").is_none() && dd.get("fylite:limiter").is_none());
        assert_eq!(dd.get("time_slice/0/global_quantities/ip").and_then(Node::as_f64), Some(1.0));
        assert_eq!(dropped, vec!["@context", "@id", "@type", "time_slice/0/fylite:extra", "fylite:limiter"]);
        assert_eq!(ids_of(&d).as_deref(), Some("equilibrium"));
        assert_eq!(ids_of(&from_dd("wall", dd, "x", 2)).as_deref(), Some("wall"));
        assert_eq!(split_ids_key("equilibrium_1"), ("equilibrium".to_string(), 1));
        assert_eq!(split_ids_key("core_profiles"), ("core_profiles".to_string(), 0));
    }

    #[test]
    fn wall_limiter_and_vessel_move_under_description_2d() {
        //: ★★实测 2026-09-04：EAST 的 wall 文档把 `limiter` / `vessel` 挂在 IDS 顶层，
        //: 而 DD 4.1.1 的家在 `description_2d[]/` 之下。没有这张搬家表时，归一化把
        //: 两支都当作「DD 不认的路径」丢掉——**丢得是响的**，但产物是一份只剩
        //: `ids_properties` 的空 wall（3.5 KB），而一份空的 IDS 比一个错误更坏：
        //: 它看着像结果。搬家之后同一份源出 71 KB，limiter 的 64 点轮廓在里面。
        let Some(meta) = IdsMeta::get("wall") else {
            //: DD 表是生成物（`tools/dd-ids-table.py`）；没有它就没得判，跳过而不是假过。
            eprintln!("no wall DD table in this checkout — skipping");
            return;
        };
        let mut doc = new_document("wall", "urn:test:wall");
        {
            let m = doc.as_map_mut().unwrap();
            let mut lim = Map::new();
            let mut unit = Map::new();
            unit.insert("name", Node::Str("limiter".into()));
            let mut outline = Map::new();
            outline.insert("r", Node::Array(Array::vec_f64(vec![1.3, 2.3, 2.3, 1.3])));
            outline.insert("z", Node::Array(Array::vec_f64(vec![-1.0, -1.0, 1.0, 1.0])));
            unit.insert("outline", Node::Map(outline));
            lim.insert("unit", Node::List(vec![Node::Map(unit)]));
            m.insert("limiter", Node::Map(lim));
        }
        let (out, rep) = dd_normalize("wall", &doc, &meta);

        //: 搬到位了，且**说了出来**——一支数据换了挂点，读者从产物上看不出它原来在哪。
        assert!(rep.relocated.iter().any(|s| s.starts_with("limiter ->")), "{:?}", rep.relocated);
        assert!(!rep.dropped.iter().any(|p| p == "limiter"), "still dropped: {:?}", rep.dropped);

        let r = out.get("description_2d/0/limiter/unit/0/outline/r")
            .and_then(Node::to_f64_vec)
            .expect("limiter outline survived the move");
        assert_eq!(r.len(), 4);

        //: ★源已经是 DD 的形时**不搬**：判据里那三条（源在、目标有、源在 DD 里没有）
        //: 缺一即不动，否则第二次归一化会把它再搬一层。
        let (again, rep2) = dd_normalize("wall", &from_dd("wall", out, "urn:test:wall", 0), &meta);
        assert!(rep2.relocated.is_empty(), "relocated twice: {:?}", rep2.relocated);
        assert!(again.get("description_2d/0/limiter/unit/0/outline/r").is_some());
    }

    #[test]
    fn dd_normalize_promotes_b0_and_synthesizes_time() {
        let meta = IdsMeta::get("equilibrium").unwrap();
        let mut d = new_document("equilibrium", "x");
        d.set("vacuum_toroidal_field/b0", 1.8.into()).unwrap();
        d.set("vacuum_toroidal_field/r0", 1.75.into()).unwrap();
        d.set("time_slice/0/time", 4.8.into()).unwrap();
        d.set("time_slice/0/global_quantities/ip", 4e5.into()).unwrap();
        d.set("time_slice/0/profiles_2d/0/psi", Node::Array(Array::f64(vec![2, 2], vec![1., 2., 3., 4.]).unwrap())).unwrap();
        d.set("time_slice/0/profiles_2d/0/grid_type/name", "rectangular".into()).unwrap();
        d.set("fylite:limiter/r", vec![1.0].into()).unwrap();
        d.set("time_slice/0/not_in_dd", 1.0.into()).unwrap();
        let (dd, rep) = dd_normalize("equilibrium", &d, &meta);
        assert_eq!(dd.get("vacuum_toroidal_field/b0").map(Node::shape), Some(vec![1]));
        assert_eq!(dd.get("time").and_then(Node::to_f64_vec), Some(vec![4.8]));
        assert_eq!(dd.get("ids_properties/homogeneous_time").and_then(Node::as_i64), Some(1));
        assert!(rep.promoted.contains(&"vacuum_toroidal_field/b0".to_string()));
        //: dropped DD-side paths are reported without the element index
        assert!(rep.dropped.contains(&"time_slice/not_in_dd".to_string()), "{:?}", rep.dropped);
        assert!(rep.dropped.contains(&"fylite:limiter".to_string()));
        let keys: Vec<&str> = dd.as_map().unwrap().keys().collect();
        assert_eq!(keys[0], "ids_properties");
        assert_eq!(dd.get("time_slice/0/profiles_2d/0/grid_type/name").and_then(Node::as_str), Some("rectangular"));
    }

    #[test]
    fn a_bundle_round_trips_through_its_container_node() {
        let mut b = Bundle::new();
        let mut eq = new_document("equilibrium", "e");
        eq.set("time", vec![1.0].into()).unwrap();
        b.push(eq);
        b.push(new_document("wall", "w"));
        let n = b.to_node();
        let again = Bundle::from_node(n);
        assert_eq!(again.keys(), vec![("equilibrium".to_string(), 0), ("wall".to_string(), 0)]);
        //: a plain DD container is recognised by its keys
        let mut m = Map::new();
        m.insert("tf", Node::map());
        m.insert("tf_2", Node::map());
        let c = Bundle::from_node(Node::Map(m));
        assert_eq!(c.keys(), vec![("tf".to_string(), 0), ("tf".to_string(), 2)]);
    }

    /// ★★★A-Box 用大驼峰声明类型，IDS 名是蛇形。不折算就**静默**认不出——
    /// 实测后果是一份 317 字节的空 netCDF 加一个 0 退出码。
    #[test]
    fn a_camel_case_type_names_its_ids() {
        let mk = |ty: &str| {
            let mut n = Node::map();
            n.as_map_mut().unwrap().insert("@type", Node::from(ty));
            n
        };
        assert_eq!(ids_of(&mk("fyo:PfActive")).as_deref(), Some("pf_active"));
        assert_eq!(ids_of(&mk("fyo:Wall")).as_deref(), Some("wall"));
        //: 已经是蛇形的照旧认，不是把一种翻成另一种
        assert_eq!(ids_of(&mk("fyo:wall")).as_deref(), Some("wall"));
        //: ★`dataset_fair` **是**一个真的 DD IDS，所以 `fyo:DatasetFair` 认出来是对的
        assert_eq!(ids_of(&mk("fyo:DatasetFair")).as_deref(), Some("dataset_fair"));
        //: ★★不是 IDS 的仍然不认。清单自己就是这种：`abox/device.jsonld` 的
        //: `@type` 是 `fyo:DeviceManifest`——它要是被当成一个 IDS，取数就会把
        //: 「怎么取」那份文件本身当成数据装进产物。
        assert_eq!(ids_of(&mk("fyo:DeviceManifest")), None);
    }
}
