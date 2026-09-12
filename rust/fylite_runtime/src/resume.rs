//! 续跑：把一次运行交出的状态，认回成下一次运行的输入。
//!
//! ★★**为什么这一层在这里。** `FYL-DESIGN-16` 把状态的五件事分给三层（S-5）：内核
//! **声明**状态是什么、**产生/消费**它；中间层**携带**；宿主**持久化**、并**决定**
//! 何时续。这个模块是「携带」的那一格——它不算任何东西，只把内核已经交出来的那些值
//! 按内核自己声明的配对规则重新摆到入口上。
//!
//! ★**状态本来就在记录里，只是没有名字。** 实测一次 `code/evolve`：记录的输出端口
//! 上已经躺着 `t_end` · `dt_next` · `edge_te_out` · `edge_ti_out` · `saw_elapsed_out` ·
//! `dt_capped` · `dt_fraction_used` · `ipctl_{ratio0,integral,calibrated}_out` 与一份
//! `core_profiles.fyo.jsonld`——续跑要的东西**一件不缺**。缺的是两样：一个把它们指成
//! 一件事的名字（`fylite:state`，`-16` S-2），和一条把它们摆回去的路（`--resume-from`，
//! `-18` U-19 / G-4）。本模块给这两样。
//!
//! ★**配对规则不是本模块发明的**：内核的声明面把交接量成对命名（`X_out` ↔ `X_in`），
//! 另有四对名字不同的（`t_end` → `t_start` · `dt_next` → `dt_start` ·
//! `dt_capped` → `capped_in` · `dt_fraction_used` → `dt_fraction_in`）。这四对写在
//! 下面那张表里，**并且每一对都要在内核声明的参数表里查得到**——查不到就不摆，
//! 而不是硬塞一个内核不认识的名字（`FR-KERNEL-002` 的「按名拒绝」在调用方这一侧的
//! 对应物）。
//!
//! ★★**这是 `-16` G-8 未决之前的形。** G-8 问的是 `fylite:state` 该长成一块还是逐
//! code 一块、跨 code 的状态怎么并。本模块**不回答**它：它写出的 `fylite:state` 是
//! 一份**平的**交接单（标量 + 文档指针），来源逐条可查。G-8 落定时，这里换的是
//! 写法，不是语义。

use crate::document::{Map, Node};
use crate::json;
use std::path::{Path, PathBuf};

/// 名字不同的那几对交接量：(记录里的输出名, 下一次运行的参数名)。
///
/// ★其余的按 `X_out` → `X_in` 机械配对，不列在这里。
const RENAMED: &[(&str, &str)] = &[
    ("t_end", "t_start"),
    ("dt_next", "dt_start"),
    ("dt_capped", "capped_in"),
    ("dt_fraction_used", "dt_fraction_in"),
];

/// 这个参数名，内核的声明面里有吗？
///
/// ★★判据是内核**自己生成**的那张表（`fyo_interface.rs`，由 `rust/build.sh` 从
/// `fyo.rs` 写出），不是本模块的一份名单：后者会在内核加一个交接量的那天悄悄地少
/// 摆一个值，而少摆一个交接量的表现是**答案慢慢地不对**，不是报错。
fn kernel_declares(param: &str) -> bool {
    crate::fyo_interface::BLOCKS
        .iter()
        .any(|b| b.rows.iter().any(|r| r.key == param))
}

/// 一个输出端口名对应的下一次运行的参数名，若内核声明了它。
fn carried_as(out_name: &str) -> Option<&'static str> {
    for (from, to) in RENAMED {
        if *from == out_name {
            return kernel_declares(to).then_some(*to);
        }
    }
    let stem = out_name.strip_suffix("_out")?;
    let target = crate::fyo_interface::BLOCKS.iter().find_map(|b| {
        b.rows
            .iter()
            .find(|r| r.key.strip_suffix("_in") == Some(stem))
            .map(|r| r.key)
    })?;
    Some(target)
}

/// 一次运行交出的状态。
#[derive(Debug, Clone, Default)]
pub struct Carried {
    /// 下一次运行要设的参数（已按内核声明改名）。
    pub settings: Vec<(String, f64)>,
    /// 要绑回输入端口的文档：(端口名, 相对记录目录的路径)。
    pub documents: Vec<(String, String)>,
    /// 这次走到第几步、到了什么时刻——给人看的，也给断点仓列表用。
    pub step: Option<f64>,
    pub t: Option<f64>,
    /// 这个入口的原始块住在哪（相对记录目录）。**不是**要绑的文档，见 `from_ports`。
    pub entry_uri: Option<String>,
}

impl Carried {
    pub fn is_empty(&self) -> bool {
        self.settings.is_empty() && self.documents.is_empty()
    }

    /// 记录里的 `fylite:state` 子树。
    pub fn to_node(&self, code: &str, entry: &str) -> Node {
        let mut m = Map::new();
        m.insert("type", "fylite:CarriedState".into());
        m.insert("code", code.into());
        m.insert("entry", entry.into());
        if let Some(s) = self.step {
            m.insert("step", Node::Float(s));
        }
        if let Some(t) = self.t {
            m.insert("t", Node::Float(t));
        }
        let mut sc = Map::new();
        for (k, v) in &self.settings {
            sc.insert(k.clone(), Node::Float(*v));
        }
        m.insert("settings", Node::Map(sc));
        let mut docs = Map::new();
        for (port, uri) in &self.documents {
            docs.insert(port.clone(), uri.clone().into());
        }
        m.insert("documents", Node::Map(docs));
        if let Some(u) = &self.entry_uri {
            //: ★不是要绑的文档，是**查滞后量**用的那一份（`lag_carried`）。
            m.insert("entry_block", u.clone().into());
        }
        m.insert(
            "comment",
            "what a next run needs to continue this one: settings go on as they are \
             (`resume` is set by the caller), documents bind to the ports they name. \
             The names are the kernel's own (`X_out` -> `X_in`); see `resume.rs`."
                .into(),
        );
        Node::Map(m)
    }
}

/// 从一份记录里读出交接单。
///
/// ★读的是**记录**，不是任何一份私有格式：断点与导出是同一份文档（`-18` U-10）。
pub fn from_record(record: &Node) -> Carried {
    let mut out = Carried::default();
    let Some(m) = record.as_map() else { return out };
    // 已经写好的那一份，优先
    if let Some(st) = m.get("fylite:state").and_then(Node::as_map) {
        if let Some(sc) = st.get("settings").and_then(Node::as_map) {
            for (k, v) in sc.iter() {
                if let Some(f) = num(v) {
                    out.settings.push((k.to_string(), f));
                }
            }
        }
        if let Some(d) = st.get("documents").and_then(Node::as_map) {
            for (k, v) in d.iter() {
                if let Some(s) = v.as_str() {
                    out.documents.push((k.to_string(), s.to_string()));
                }
            }
        }
        out.step = st.get("step").and_then(num);
        out.t = st.get("t").and_then(num);
        out.entry_uri = st.get("entry_block").and_then(Node::as_str).map(str::to_string);
        if !out.is_empty() {
            return out;
        }
    }
    // 没有那一份时，从端口上重建（旧记录，或别的写入方）
    from_ports(m, &mut out);
    out
}

fn num(n: &Node) -> Option<f64> {
    match n {
        Node::Float(f) => Some(*f),
        Node::Int(i) => Some(*i as f64),
        Node::Bool(b) => Some(if *b { 1.0 } else { 0.0 }),
        _ => None,
    }
}

/// 从输出端口重建交接单——`record()` 写 `fylite:state` 用的也是这一条。
pub fn from_ports(record: &Map, out: &mut Carried) {
    let Some(list) = record.get("inputs").and_then(Node::as_list) else { return };
    for b in list {
        let Some(bm) = b.as_map() else { continue };
        let port = bm.get("binds_port").and_then(Node::as_map);
        let dir = port.and_then(|p| p.get("port_direction")).and_then(Node::as_str);
        if dir != Some("output") {
            continue;
        }
        let Some(name) = port.and_then(|p| p.get("port_name")).and_then(Node::as_str) else {
            continue;
        };
        let Some(bound) = bm.get("bound_to").and_then(Node::as_map) else { continue };
        match bound.get("type").and_then(Node::as_str) {
            Some("spo:QuantityValue") => {
                let Some(v) = bound.get("numeric_value").and_then(num) else { continue };
                if name == "steps" {
                    out.step = Some(v);
                }
                if name == "t_end" {
                    out.t = Some(v);
                }
                if let Some(target) = carried_as(name) {
                    out.settings.push((target.to_string(), v));
                }
            }
            _ => {
                //: 产出的数据集：只有内核**也当输入收**的那些才是状态
                //: （`core_profiles` 是；`summary` 不是）。
                let uri = bm
                    .get("bound_concretization")
                    .and_then(Node::as_map)
                    .and_then(|c| c.get("storage_uri"))
                    .and_then(Node::as_str);
                if let Some(u) = uri {
                    if matches!(name, "core_profiles" | "equilibrium") {
                        out.documents.push((name.to_string(), u.to_string()));
                    }
                    //: ★`entry` 不当状态文档绑（绑了也不起作用：中间层只把**声明过
                    //: 的表**里的槽压进扁平树，而这个入口的原始块没有表——`-16` F-2）。
                    //: 它在这里只有一个用处：**查滞后量是不是零**，见 `lag_carried`。
                    if name == "entry" {
                        out.entry_uri = Some(u.to_string());
                    }
                }
            }
        }
    }
}

/// `--resume-from` 给的那个路径：一份 `record.jsonld`，或装着它的目录。
pub fn read(path: &Path) -> Result<(Carried, PathBuf), String> {
    let file = if path.is_dir() { path.join("record.jsonld") } else { path.to_path_buf() };
    let text = std::fs::read_to_string(&file)
        .map_err(|e| format!("--resume-from {}: {e}", file.display()))?;
    let node = json::parse(&text).map_err(|e| format!("--resume-from {}: {e:?}", file.display()))?;
    let ty = node.as_map().and_then(|m| m.get("type")).and_then(Node::as_str);
    if ty != Some("spo:ComputationRecord") {
        return Err(format!(
            "--resume-from {}: this is not a record (type {:?}, wanted spo:ComputationRecord)",
            file.display(),
            ty.unwrap_or("-")
        ));
    }
    let carried = from_record(&node);
    if carried.is_empty() {
        return Err(format!(
            "--resume-from {}: this record carries no state to continue from — a single-step \
             code has no mid-march state, and that is an answer rather than a fault",
            file.display()
        ));
    }
    let base = file.parent().map(Path::to_path_buf).unwrap_or_default();
    Ok((carried, base))
}

/// 这次续跑，**滞后量交得过去吗**。
///
/// ★★这是本模块唯一一处「判断」，而它存在的理由是一个量到的数。`code/evolve` 的
/// 三条滞后量（`psi_prev` / `sigma_prev` / `exch_prev`）由内核从
/// `evolve/fylite:psi_prev` 一类的输入读回，而它一次跑完写出去的那一份叫
/// `psi_prev_out`，住在这个入口的**原始块**里——中间层只把声明过的表里的槽压进
/// 扁平树（`-16` F-2），原始块没有表，所以那三条**过不去**。
///
/// 后果是可以量的：常数闭合（`closure=0`）下滞后量本来就是零，40 步 ≡ 20 + 续 20
/// **逐位相同**（实测 max rel 0.000e+00）；开了新经典闭合与密度 / 动量通道之后，
/// 同一个比法 Te 差 **61 %**、n_e 差 **70 %**，而两次都**退出 0**——一个不报错的错。
///
/// 所以这里按名判：原始块里的滞后量有非零的，就说清楚它过不去。`-16` G-8（`fylite:state`
/// 到底是一棵什么形状的子树）落定之前，这是能给的最诚实的答案。
///
/// 返回 `Ok(())` = 交得过去（本来就是零）；`Err(话)` = 交不过去，话是给人看的那一句。
pub fn lag_carried(carried: &Carried, base: &Path) -> Result<(), String> {
    const LAG: [&str; 3] = ["psi_prev_out", "sigma_prev_out", "exch_prev_out"];
    //: ★★**2026-09-12: the declared route, when the record has it.** The three
    //: arrays are now DECLARED slots of `core_profiles`
    //: (`profiles_1d/fylite:psi_prev` · `sigma_prev` · `exch_prev`), which is
    //: the state document a resume already binds — so they cross with no new
    //: plumbing and nothing is reset.  ★They are NOT on a table of their own:
    //: the door's old spelling `evolve/fylite:*` names the document after the
    //: CODE, and the middle layer builds a document per IDS the DD knows, so
    //: that one could never be built (measured: no `evolve.fyo.jsonld` in any
    //: record).  A record written before this declaration has no such slots,
    //: and then the raw-block check below still applies: the honest answer for
    //: an old record is the old answer.
    if let Some((_, uri)) = carried.documents.iter().find(|(n, _)| n == "core_profiles") {
        let path = if Path::new(uri).is_absolute() { PathBuf::from(uri) } else { base.join(uri) };
        if let Ok(text) = std::fs::read_to_string(&path) {
            if let Ok(doc) = json::parse(&text) {
                let has = ["profiles_1d/fylite:psi_prev", "profiles_1d/fylite:sigma_prev",
                           "profiles_1d/fylite:exch_prev"]
                    .iter()
                    .all(|k| doc.get(k).is_some());
                if has {
                    return Ok(());
                }
            }
        }
    }
    let Some(uri) = &carried.entry_uri else { return Ok(()) };
    let path = if Path::new(uri).is_absolute() { PathBuf::from(uri) } else { base.join(uri) };
    let Ok(text) = std::fs::read_to_string(&path) else { return Ok(()) };
    let Ok(doc) = json::parse(&text) else { return Ok(()) };
    let Some(m) = doc.as_map() else { return Ok(()) };
    let mut live = Vec::new();
    for key in LAG {
        let any = m.get(key).and_then(|n| match n {
            Node::Array(a) => a.to_f64().map(|v| v.iter().any(|x| *x != 0.0)),
            Node::List(l) => Some(l.iter().filter_map(num).any(|x| x != 0.0)),
            _ => None,
        });
        if any == Some(true) {
            live.push(key);
        }
    }
    if live.is_empty() {
        return Ok(());
    }
    Err(format!(
        "the lagged arrays this run ended on ({}) are not handed over: the kernel reads them back \
         from `evolve/fylite:*` but writes them into its raw entry block, which the flat door \
         carries no table for (FYL-DESIGN-16 F-2 / G-8). `lag_reset` is set instead -- the kernel's \
         own word for「the state was remapped」, so the first step carries no Ohmic term rather than \
         treating three zero arrays as the previous block's answer. This is recorded in the plan \
         (`fylite:from` = resume:lag-reset). Until G-8 lands, a resumed march is NOT bit-for-bit \
         the same as the undivided one wherever those arrays bite: measured 0.0e+00 with the \
         constant closure, 61 % on Te with the neoclassical one",
        live.join(" / ")
    ))
}

/// 写它的那个内核，与现在这个，是不是同一份（S-6 / K-7）。
///
/// ★`Ok(())` = 可以续；`Err(话)` = 不可以，话就是给人看的那一句。允许显式漂移由
/// 调用方决定，并且**要写进记录**——这里只回答「同不同」。
pub fn same_kernel(record: &Node, kernel_sha256: Option<&str>) -> Result<(), String> {
    let was = record
        .as_map()
        .and_then(|m| m.get("environment"))
        .and_then(Node::as_map)
        .and_then(|e| e.get("kernel_sha256"))
        .and_then(Node::as_str);
    match (was, kernel_sha256) {
        (Some(a), Some(b)) if a == b => Ok(()),
        (Some(a), Some(b)) => Err(format!(
            "the record was written by a different kernel: {}… -> {}… \
             (pass --allow-kernel-drift to continue anyway; it is written into the record)",
            &a[..a.len().min(8)],
            &b[..b.len().min(8)]
        )),
        (None, _) => Err("the record does not say which kernel wrote it (K-7), \
                          so it cannot be judged resumable"
            .into()),
        (_, None) => Err("this kernel does not report its own identity, \
                          so it cannot be judged against the record"
            .into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renamed_pairs_are_all_declared_by_the_kernel() {
        //: ★这张表是**手写**的四行，而它要对得上内核的声明面。内核改名时这条先红。
        for (from, to) in RENAMED {
            assert!(kernel_declares(to), "{from} -> {to}: the kernel declares no `{to}`");
        }
    }

    #[test]
    fn the_mechanical_pairing_finds_the_evolve_handover() {
        //: 实测过的那几个：`edge_te_out` → `edge_te_in` 一类。
        assert_eq!(carried_as("edge_te_out"), Some("edge_te_in"));
        assert_eq!(carried_as("saw_elapsed_out"), Some("saw_elapsed_in"));
        assert_eq!(carried_as("t_end"), Some("t_start"));
        assert_eq!(carried_as("dt_next"), Some("dt_start"));
        //: 不是交接量的输出不该被摆回去
        assert_eq!(carried_as("balance_worst"), None);
        assert_eq!(carried_as("summary"), None);
    }

    #[test]
    fn a_record_without_state_says_so_rather_than_resuming_empty() {
        let node = json::parse(r#"{"type":"spo:ComputationRecord","inputs":[]}"#).unwrap();
        assert!(from_record(&node).is_empty());
    }
}
