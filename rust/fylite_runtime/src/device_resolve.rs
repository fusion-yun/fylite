//! 装置描述**按炮号与测量链**在使用时解析（用户裁定 R-S1 / R-S2 与 2026-09-13「测量链定装置构型」）。
//!
//! ★★Two things live here, and only here.
//!
//! 1. **The rule** that picks a provider for one IDS out of a machine manifest:
//!    * a request gives ONLY the device, the shot and the **measurement chain** — the chain the
//!      measurement document itself declares (`measurement_chain`).  No provider is named by a
//!      caller, ever;
//!    * an IDS whose providers carry `measurement_chain` (the measurement-ordered groups —
//!      magnetics) is resolved WITHIN the requested chain ([`choose_in_chain`]): the provider
//!      declaring a shot range that covers the shot wins; a rangeless one of that chain only when
//!      no ranged one covers it; a gap inside the chain, two geometry providers of one chain covering
//!      the shot, and a chain the manifest does not declare (`measurement_chains`) are each refused
//!      by name — never the nearest provider, never the default;
//!    * with no chain given, and for every IDS that carries none ([`choose`]): the SHOT-ANCHORED
//!      provider covering the shot; with **no shot given, the one covering the open upper end**
//!      (no shot = the latest shot, ruling R-S2); several covering: the narrowest range, then the
//!      manifest default, then the one marked `preferred`, then the first in manifest order — each
//!      named in a note; otherwise the manifest's `default`.
//!
//!    `assembly::from_manifest` (the fydoc A-Box route) and [`resolve`] (the shipped-card route)
//!    both call it; Python reaches it through the C ABI (`fylite_runtime_device_resolve`), and
//!    `tools/abox-to-facts.py` through Python.  There is no second implementation.
//!
//! 2. **The splice** ([`resolve`]) that turns the shipped static card — itself the no-shot
//!    resolution — into the card for one request.  The per-provider groups were converted ONCE, at
//!    build time, by `tools/abox-to-facts.py`, and ship in a `fylite:DeviceResolution` document beside
//!    the card (`<id>_resolution.jsonld`, and in the bundled tier).  This module chooses among them
//!    and writes the chosen group over the card; it converts nothing.
//!
//! ★★The pairing refusal lives with the two halves where they are bound (`cli/run.rs`
//! `check_channel_order`, `fylite.fyo`): a measurement declaring one chain and a card whose magnetics
//! group is in another are refused by name.

use crate::document::{Map, Node};

/// `[lo, hi]`, `hi` = `None` for an open upper end.
pub type ShotRange = (i64, Option<i64>);

/// `@type` of the resolution document written by `tools/abox-to-facts.py`.
pub const RESOLUTION_TYPE: &str = "fylite:DeviceResolution";

/// The key a provider, a chain declaration, a measurement document and a request all spell.
pub const CHAIN_KEY: &str = "measurement_chain";

/// The manifest table that declares the chains (`id -> {kind, tree | description, evidence}`).
pub const CHAINS_KEY: &str = "measurement_chains";

/// The rule in one sentence, written into every resolved document's provenance.
pub const RULE: &str = "a measurement-ordered IDS (its providers carry measurement_chain) is resolved \
    within the measurement's chain: the provider whose shot range covers the shot, else that chain's \
    rangeless provider — a gap in the chain, two covering providers or an undeclared chain is refused; \
    with no chain, and for every other IDS: the shot-anchored provider (valid_shots) covering the shot, \
    and with no shot the one covering the open upper end (no shot = the latest shot); otherwise the \
    manifest default (fylite_runtime::device_resolve; user rulings R-S1 / R-S2 and the measurement-chain \
    ruling, 2026-09-13)";

/// `valid_shots` / `applies_shots`: `[lo, hi]`, `hi` null = open-ended; `null` = no range.
pub fn shot_range(v: &Node) -> Option<ShotRange> {
    match v {
        Node::Null => None,
        Node::List(l) if !l.is_empty() => Some((l[0].as_i64()?, l.get(1).and_then(Node::as_i64))),
        other => {
            let f = other.to_f64_vec()?;
            Some((*f.first()? as i64, f.get(1).map(|x| *x as i64)))
        }
    }
}

pub fn covers(r: ShotRange, shot: i64) -> bool {
    shot >= r.0 && r.1.map(|hi| shot <= hi).unwrap_or(true)
}

/// With no shot, "covers" means "covers the open upper end" (ruling R-S2).
fn covers_at(r: ShotRange, shot: Option<i64>) -> bool {
    match shot {
        Some(s) => covers(r, s),
        None => r.1.is_none(),
    }
}

/// Two ranges share at least one shot.
fn overlap(a: ShotRange, b: ShotRange) -> bool {
    let hi = |r: ShotRange| r.1.unwrap_or(i64::MAX);
    a.0 <= hi(b) && b.0 <= hi(a)
}

pub fn show_range(r: ShotRange) -> String {
    format!("[{}, {}]", r.0, r.1.map(|h| h.to_string()).unwrap_or_else(|| "—".to_string()))
}

/// The assembly layer keeps `shot = 0` for "not given".
pub fn shot_given(shot: i64) -> Option<i64> {
    (shot > 0).then_some(shot)
}

fn at(shot: Option<i64>) -> String {
    match shot {
        Some(s) => format!("shot {s}"),
        None => "the latest shot (no shot given)".to_string(),
    }
}

fn backend_of(v: &Node) -> &str {
    v.as_map().and_then(|m| m.get("backend")).and_then(Node::as_str).unwrap_or("static")
}

fn range_of(v: &Node) -> Option<ShotRange> {
    v.as_map().and_then(|m| m.get("valid_shots")).and_then(shot_range)
}

fn chain_of(v: &Node) -> Option<&str> {
    v.as_map().and_then(|m| m.get(CHAIN_KEY)).and_then(Node::as_str)
}

fn available_of(providers: Option<&Node>) -> Vec<(&str, &Node)> {
    providers
        .and_then(Node::as_map)
        .and_then(|m| m.get("available"))
        .and_then(Node::as_map)
        .map(|a| a.iter().collect())
        .unwrap_or_default()
}

/// One IDS' provider, and why.
#[derive(Debug, Clone, PartialEq)]
pub struct Choice {
    pub provider: Option<String>,
    pub range: Option<ShotRange>,
    pub why: String,
    pub notes: Vec<String>,
    /// The chosen provider declares a shot range and the shot is outside it (a default used
    /// anyway).  A `strict` request refuses this.
    pub outside: bool,
}

/// `_valid_shots` of a document covers `shot`?  `Err(Some(range))` outside it, `Err(None)` no
/// range recorded.  ★The one comparison: `case.rs`'s `facts:…?shot=N` check calls this.
pub fn card_covers(card: &Node, shot: i64) -> Result<(), Option<ShotRange>> {
    match card.get("_valid_shots").and_then(shot_range) {
        Some(r) if covers(r, shot) => Ok(()),
        Some(r) => Err(Some(r)),
        None => Err(None),
    }
}

/// The IDS' providers carry `measurement_chain` — a measurement-ordered group.
pub fn carries_chain(providers: Option<&Node>) -> bool {
    available_of(providers).iter().any(|(_, v)| chain_of(v).is_some())
}

/// The chain ids a manifest declares (`measurement_chains`), in manifest order.
pub fn declared_chains(manifest_chains: Option<&Node>) -> Vec<String> {
    manifest_chains.and_then(Node::as_map).map(|m| m.keys().map(str::to_string).collect()).unwrap_or_default()
}

/// ★The manifest's own consistency for one IDS (the generator refuses a manifest that fails it,
/// because every card it writes is resolved through here): every `measurement_chain` a provider
/// carries is declared, and within one chain the `backend` providers never both cover one shot —
/// ranged ones do not overlap, and there is at most one rangeless one.
pub fn check_chains(ids: &str, providers: Option<&Node>, manifest_chains: Option<&Node>, backend: &str) -> Result<(), String> {
    let declared = declared_chains(manifest_chains);
    let avail = available_of(providers);
    for (name, v) in &avail {
        if let Some(c) = chain_of(v) {
            if !declared.iter().any(|d| d == c) {
                return Err(format!(
                    "{ids} provider {name:?} carries measurement_chain {c:?}, which the manifest does not declare \
                     in measurement_chains (declared: {})",
                    if declared.is_empty() { "none".to_string() } else { declared.join(", ") }
                ));
            }
        }
    }
    for c in &declared {
        let members: Vec<(&str, Option<ShotRange>)> = avail
            .iter()
            .filter(|(_, v)| chain_of(v) == Some(c.as_str()) && backend_of(v) == backend)
            .map(|(n, v)| (*n, range_of(v)))
            .collect();
        let ranged: Vec<(&str, ShotRange)> = members.iter().filter_map(|(n, r)| r.map(|r| (*n, r))).collect();
        for (i, a) in ranged.iter().enumerate() {
            for b in &ranged[i + 1..] {
                if overlap(a.1, b.1) {
                    return Err(format!(
                        "{ids}: measurement chain {c:?} has two {backend} providers covering the same shots — \
                         {:?} {} and {:?} {}; one shot must resolve to one provider within a chain",
                        a.0,
                        show_range(a.1),
                        b.0,
                        show_range(b.1)
                    ));
                }
            }
        }
        let rangeless: Vec<&str> = members.iter().filter(|(_, r)| r.is_none()).map(|(n, _)| *n).collect();
        if rangeless.len() > 1 {
            return Err(format!(
                "{ids}: measurement chain {c:?} has {} {backend} providers without a shot range ({}) — \
                 both would cover every shot; one shot must resolve to one provider within a chain",
                rangeless.len(),
                rangeless.iter().map(|n| format!("{n:?}")).collect::<Vec<_>>().join(", ")
            ));
        }
    }
    Ok(())
}

/// THE rule within a measurement chain (module header).  `chain` must be declared by the caller's
/// manifest ([`check_chains`] / [`selection`] refuse an undeclared one first).
pub fn choose_in_chain(ids: &str, providers: Option<&Node>, backend: &str, shot: Option<i64>, chain: &str) -> Result<Choice, String> {
    let avail = available_of(providers);
    let members: Vec<(&str, Option<ShotRange>)> = avail
        .iter()
        .filter(|(_, v)| chain_of(v) == Some(chain) && backend_of(v) == backend)
        .map(|(n, v)| (*n, range_of(v)))
        .collect();
    if members.is_empty() {
        let mut chains: Vec<&str> = avail.iter().filter(|(_, v)| backend_of(v) == backend).filter_map(|(_, v)| chain_of(v)).collect();
        chains.dedup();
        return Err(format!(
            "{ids}: no {backend} provider is in measurement chain {chain:?} (chains of this IDS: {})",
            if chains.is_empty() { "none".to_string() } else { chains.join(", ") }
        ));
    }
    let hits: Vec<(&str, ShotRange)> =
        members.iter().filter_map(|(n, r)| r.filter(|r| covers_at(*r, shot)).map(|r| (*n, r))).collect();
    if hits.len() > 1 {
        return Err(format!(
            "{ids}: measurement chain {chain:?} has two {backend} providers covering {}: {}",
            at(shot),
            hits.iter().map(|(n, r)| format!("{n:?} {}", show_range(*r))).collect::<Vec<_>>().join(", ")
        ));
    }
    if let Some((name, r)) = hits.first() {
        return Ok(Choice {
            provider: Some(name.to_string()),
            range: Some(*r),
            why: format!("the measurement chain {chain:?}: its provider {name:?} {} covers {}", show_range(*r), at(shot)),
            notes: Vec::new(),
            outside: false,
        });
    }
    let rangeless: Vec<&str> = members.iter().filter(|(_, r)| r.is_none()).map(|(n, _)| *n).collect();
    match rangeless.as_slice() {
        [one] => Ok(Choice {
            provider: Some(one.to_string()),
            range: None,
            why: format!("the measurement chain {chain:?}: its provider {one:?} declares no shot range"),
            notes: Vec::new(),
            outside: false,
        }),
        [] => {
            let ranges: Vec<String> = members.iter().filter_map(|(n, r)| r.map(|r| format!("{n:?} {}", show_range(r)))).collect();
            Err(format!(
                "{ids}: measurement chain {chain:?} has no provider for {} — its providers declare shots {}; \
                 a gap in a chain is refused, not filled with the nearest provider",
                at(shot),
                ranges.join(", ")
            ))
        }
        many => Err(format!(
            "{ids}: measurement chain {chain:?} has {} {backend} providers without a shot range ({})",
            many.len(),
            many.iter().map(|n| format!("{n:?}")).collect::<Vec<_>>().join(", ")
        )),
    }
}

/// THE rule with no chain (module header).  `providers` is the manifest's `providers.<ids>` node;
/// `backend` restricts the shot-anchored candidates (`static` for geometry).
pub fn choose(providers: Option<&Node>, backend: &str, shot: Option<i64>) -> Result<Choice, String> {
    let pm = providers.and_then(Node::as_map);
    let available = pm.and_then(|m| m.get("available")).and_then(Node::as_map);
    let default = pm.and_then(|m| m.get("default")).and_then(Node::as_str);

    //: shot-anchored candidates covering the shot, in manifest order
    let mut hits: Vec<(&str, ShotRange, bool)> = Vec::new();
    for (name, v) in available.map(|a| a.iter().collect::<Vec<_>>()).unwrap_or_default() {
        if backend_of(v) != backend {
            continue;
        }
        if let Some(r) = range_of(v).filter(|r| covers_at(*r, shot)) {
            let preferred = matches!(v.as_map().and_then(|m| m.get("preferred")), Some(Node::Bool(true)));
            hits.push((name, r, preferred));
        }
    }
    if !hits.is_empty() {
        let width = |r: ShotRange| r.1.unwrap_or(i64::MAX).saturating_sub(r.0);
        let best = hits.iter().map(|h| width(h.1)).min().unwrap_or(i64::MAX);
        let tied: Vec<&(&str, ShotRange, bool)> = hits.iter().filter(|h| width(h.1) == best).collect();
        let preferred: Vec<&&(&str, ShotRange, bool)> = tied.iter().filter(|h| h.2).collect();
        let (pick, how) = if let Some(d) = tied.iter().find(|h| Some(h.0) == default) {
            (**d, "the manifest default")
        } else if preferred.len() == 1 {
            (**preferred[0], "the one marked preferred")
        } else {
            (*tied[0], "the first in manifest order")
        };
        let mut notes = Vec::new();
        if tied.len() > 1 {
            let others: Vec<String> = tied.iter().filter(|h| h.0 != pick.0).map(|h| format!("{:?}", h.0)).collect();
            notes.push(format!(
                "{} also cover{} {} with the same range {}; {:?} is taken as {how}",
                others.join(", "),
                if others.len() == 1 { "s" } else { "" },
                at(shot),
                show_range(pick.1),
                pick.0
            ));
        }
        if let Some(d) = default.filter(|d| *d != pick.0) {
            match available.and_then(|a| a.get(d)).and_then(range_of) {
                Some(dr) if covers_at(dr, shot) => notes.push(format!(
                    "the default provider {d:?} {} covers {} too; the narrower {:?} {} is taken",
                    show_range(dr),
                    at(shot),
                    pick.0,
                    show_range(pick.1)
                )),
                Some(dr) => notes.push(format!(
                    "the default provider {d:?} {} does not cover {}; {:?} {} does",
                    show_range(dr),
                    at(shot),
                    pick.0,
                    show_range(pick.1)
                )),
                None => notes.push(format!(
                    "the default provider {d:?} declares no shot range and yields to the shot-anchored {:?} {}",
                    pick.0,
                    show_range(pick.1)
                )),
            }
        }
        let why = match shot {
            Some(s) => format!("the shot-anchored provider {:?} {} covers shot {s}", pick.0, show_range(pick.1)),
            None => format!(
                "no shot given, so resolved as the latest shot: the shot-anchored provider {:?} {} covers the open upper end",
                pick.0,
                show_range(pick.1)
            ),
        };
        return Ok(Choice { provider: Some(pick.0.to_string()), range: Some(pick.1), why, notes, outside: false });
    }

    match default {
        Some(d) => {
            let range = available.and_then(|a| a.get(d)).and_then(range_of);
            let mut notes = Vec::new();
            let outside = range.map(|r| !covers_at(r, shot)).unwrap_or(false);
            if let (Some(r), true) = (range, outside) {
                notes.push(format!(
                    "the default provider {d:?} {} does not cover {} and no single static provider does — used anyway",
                    show_range(r),
                    at(shot)
                ));
            }
            Ok(Choice {
                provider: Some(d.to_string()),
                range,
                why: format!("the manifest default {d:?} (no shot-anchored provider covers {})", at(shot)),
                notes,
                outside,
            })
        }
        None => Ok(Choice {
            provider: None,
            range: None,
            why: format!("the manifest names no default and no shot-anchored provider covers {}", at(shot)),
            notes: Vec::new(),
            outside: false,
        }),
    }
}

// ─────────────────────────── a request, and the shipped-card route ───────────────────────────

/// What a caller asks for: the shot and the measurement chain, nothing else (user ruling
/// 2026-09-13).  Everything optional: the empty request is the no-shot resolution, which is the
/// static card.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Request {
    pub shot: Option<i64>,
    /// The chain the measurement document declares (`measurement_chain`).
    pub measurement_chain: Option<String>,
    /// A document PINNED to the shot (a generated variant card, a plan's `facts:` entry): a
    /// default provider whose declared range does not cover the shot is refused, not used.
    pub strict: bool,
}

impl Request {
    /// `{"shot": N|null, "measurement_chain": "east"|null, "strict": bool}` — any other key is
    /// refused by name (`providers` / `basis` were request keys before the 2026-09-13 ruling).
    pub fn from_node(n: &Node) -> Result<Request, String> {
        let mut r = Request::default();
        let Some(m) = n.as_map() else { return Ok(r) };
        for (k, v) in m.iter() {
            match k {
                "shot" => match v {
                    Node::Null => {}
                    v => r.shot = shot_given(v.as_i64().ok_or("shot is not an integer")?),
                },
                CHAIN_KEY => match v {
                    Node::Null => {}
                    v => r.measurement_chain = Some(v.as_str().ok_or("measurement_chain is not a string")?.to_string()),
                },
                "strict" => match v {
                    Node::Null => {}
                    Node::Bool(b) => r.strict = *b,
                    _ => return Err("strict is not a boolean".into()),
                },
                other => {
                    return Err(format!(
                        "request key {other:?} is not accepted: a device request gives only shot and \
                         measurement_chain (the device configuration follows the measurement chain; \
                         naming a provider or a channel basis was removed, user ruling 2026-09-13)"
                    ))
                }
            }
        }
        Ok(r)
    }
}

/// Which spelling of the card the splice writes: the YAML card Python reads, or the
/// derived `<id>.jsonld` document the runtime and the pages read.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Form {
    Card,
    Document,
}

impl Form {
    pub fn parse(s: &str) -> Option<Form> {
        match s {
            "card" => Some(Form::Card),
            "" | "document" => Some(Form::Document),
            _ => None,
        }
    }
    pub fn key(self) -> &'static str {
        match self {
            Form::Card => "card",
            Form::Document => "document",
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Selected {
    pub ids: String,
    pub provider: String,
    pub range: Option<ShotRange>,
    pub why: String,
}

#[derive(Debug, Clone)]
pub struct Resolved {
    pub doc: Node,
    pub selected: Vec<Selected>,
    pub notes: Vec<String>,
}

fn strings(n: Option<&Node>) -> Vec<String> {
    match n {
        Some(Node::List(l)) => l.iter().filter_map(|x| x.as_str().map(str::to_string)).collect(),
        Some(Node::Array(a)) => a.as_str().map(|s| s.to_vec()).unwrap_or_default(),
        Some(Node::Str(s)) => vec![s.clone()],
        _ => Vec::new(),
    }
}

fn check_type(resolution: &Node) -> Result<&Map, String> {
    let m = resolution.as_map().ok_or("a device resolution document is a mapping")?;
    if m.get("@type").and_then(Node::as_str) != Some(RESOLUTION_TYPE) {
        return Err(format!("not a device resolution document (its @type is not {RESOLUTION_TYPE})"));
    }
    Ok(m)
}

/// The providers a request resolves to, per IDS the resolution document resolves.
pub fn selection(resolution: &Node, req: &Request) -> Result<(Vec<Selected>, Vec<String>), String> {
    let res = check_type(resolution)?;
    let manifest = res.get("manifest").and_then(Node::as_map);
    let providers = manifest.and_then(|m| m.get("providers"));
    let chains = manifest.and_then(|m| m.get(CHAINS_KEY));
    let of = |ids: &str| providers.and_then(Node::as_map).and_then(|p| p.get(ids));
    let resolved = strings(res.get("resolved_ids"));
    let declared = declared_chains(chains);
    let mut notes = Vec::new();

    if let Some(c) = &req.measurement_chain {
        if !declared.iter().any(|d| d == c) {
            return Err(format!(
                "measurement chain {c:?} is not declared for this device (declared: {}) — an undeclared chain is \
                 refused, not resolved to the default",
                if declared.is_empty() { "none".to_string() } else { declared.join(", ") }
            ));
        }
    }

    let mut out = Vec::new();
    let mut chain_used = false;
    for ids in &resolved {
        check_chains(ids, of(ids), chains, "static")?;
        let c = match &req.measurement_chain {
            Some(chain) if carries_chain(of(ids)) => {
                chain_used = true;
                choose_in_chain(ids, of(ids), "static", req.shot, chain)?
            }
            _ => choose(of(ids), "static", req.shot).map_err(|e| format!("{ids}: {e}"))?,
        };
        let provider = c.provider.clone().ok_or_else(|| format!("{ids}: {}", c.why))?;
        if req.strict && c.outside {
            let r = c.range.map(show_range).unwrap_or_default();
            return Err(format!(
                "{ids}: the default provider {provider:?} holds for shots {r}, {} is outside it, and no shot-anchored \
                 provider covers it",
                req.shot.map(|s| format!("shot {s}")).unwrap_or_else(|| "the latest shot".into())
            ));
        }
        notes.extend(c.notes.iter().map(|x| format!("{ids}: {x}")));
        out.push(Selected { ids: ids.clone(), provider, range: c.range, why: c.why.clone() });
    }
    if let (Some(c), false) = (&req.measurement_chain, chain_used) {
        notes.push(format!("the measurement chain {c:?} decides no IDS of this device (none of its resolved IDS carries a chain)"));
    }
    Ok((out, notes))
}

/// `{ids: {provider, shots, why}}` — the part of the record a caller compares.
pub fn selected_node(selected: &[Selected]) -> Node {
    let mut ids = Map::new();
    for s in selected {
        let mut e = Map::new();
        e.insert("provider", Node::Str(s.provider.clone()));
        e.insert(
            "shots",
            match s.range {
                Some((lo, hi)) => Node::List(vec![Node::Int(lo), hi.map(Node::Int).unwrap_or(Node::Null)]),
                None => Node::Str("all — the provider declares no shot range".into()),
            },
        );
        e.insert("why", Node::Str(s.why.clone()));
        ids.insert(s.ids.clone(), Node::Map(e));
    }
    Node::Map(ids)
}

/// `provenance.fylite:resolution`: the rule, the request, the chains the device declares, and per
/// IDS which provider and which shot range the document represents (R-S2).
pub fn record(selected: &[Selected], req: &Request, notes: &[String], chains: &[String]) -> Node {
    let mut m = Map::new();
    m.insert("rule", Node::Str(RULE.into()));
    //: the chains this device declares — a consumer holding a measurement compares its
    //: `measurement_chain` against the magnetics group's for these
    if !chains.is_empty() {
        m.insert(CHAINS_KEY, Node::List(chains.iter().map(|o| Node::Str(o.clone())).collect()));
    }
    m.insert(
        "shot",
        match req.shot {
            Some(s) => Node::Int(s),
            None => Node::Str("none given — resolved as the latest shot".into()),
        },
    );
    if let Some(c) = &req.measurement_chain {
        m.insert(CHAIN_KEY, Node::Str(c.clone()));
    }
    m.insert("ids", selected_node(selected));
    if !notes.is_empty() {
        m.insert("notes", Node::List(notes.iter().map(|n| Node::Str(n.clone())).collect()));
    }
    Node::Map(m)
}

/// A short `magnetics=east_new [97034, —], wall=base` for one-line reports.
pub fn summary(selected: &[Selected]) -> String {
    selected
        .iter()
        .map(|s| format!("{}={}{}", s.ids, s.provider, s.range.map(|r| format!(" {}", show_range(r))).unwrap_or_default()))
        .collect::<Vec<_>>()
        .join(", ")
}

/// Resolve `card` (the static, no-shot card, in `form`) for `req`.
pub fn resolve(card: &Node, resolution: &Node, req: &Request, form: Form) -> Result<Resolved, String> {
    let (selected, notes) = selection(resolution, req)?;
    if card.as_map().is_none() {
        return Err("the device card is not a mapping".into());
    }
    let mut doc = card.clone();
    for s in &selected {
        let variants = resolution.as_map().and_then(|m| m.get("variants")).and_then(Node::as_map)
            .and_then(|v| v.get(&s.ids)).and_then(Node::as_map);
        let v = variants.and_then(|m| m.get(&s.provider)).and_then(Node::as_map).ok_or_else(|| {
            format!(
                "{} provider {:?}: the device's resolution document carries no converted {} set for it (converted: {})",
                s.ids,
                s.provider,
                s.ids,
                variants.map(|m| m.keys().collect::<Vec<_>>().join(", ")).unwrap_or_default()
            )
        })?;
        if let Some(why) = v.get("fylite:absent") {
            return Err(format!(
                "{} provider {:?} ({}) cannot be used for this device: {}",
                s.ids,
                s.provider,
                s.why,
                why.as_str().map(str::to_string).unwrap_or_else(|| crate::json::to_string(why, false))
            ));
        }
        let owned = v.get(form.key()).and_then(Node::as_map).ok_or_else(|| {
            format!("{} provider {:?}: the resolution document carries no `{}` form", s.ids, s.provider, form.key())
        })?;
        for (k, val) in owned.iter() {
            doc.set(k, val.clone()).map_err(|e| format!("{}: cannot write `{k}`: {e:?}", s.ids))?;
        }
        if let Some(sf) = v.get("source_files").and_then(Node::as_map) {
            if let Some(files) = doc.get_mut("provenance/source_files").and_then(Node::as_map_mut) {
                let prefix = format!("{}:", s.ids);
                let stale: Vec<String> = files
                    .keys()
                    .filter(|k| (*k == s.ids || k.starts_with(&prefix)) && !sf.contains_key(k))
                    .map(str::to_string)
                    .collect();
                for k in stale {
                    files.remove(&k);
                }
                for (k, val) in sf.iter() {
                    files.insert(k, val.clone());
                }
            }
        }
    }
    //: the shot range the resolved document holds on as a whole — the intersection of the ranges
    //: its selected providers DECLARE; none declared and a shot given: that shot only (a
    //: date-anchored provider is not vouched for every shot).  The same `_valid_shots` a card
    //: generated for a shot records (`tools/abox-to-facts.py --shot`, read by `case.rs`).
    let declared: Vec<ShotRange> = selected.iter().filter_map(|s| s.range).collect();
    let valid = match (declared.is_empty(), req.shot) {
        (false, _) => Some((declared.iter().map(|r| r.0).max().unwrap_or(0), declared.iter().filter_map(|r| r.1).min())),
        (true, Some(s)) => Some((s, Some(s))),
        (true, None) => None,
    };
    match valid {
        Some((lo, hi)) => doc
            .set("_valid_shots", Node::List(vec![Node::Int(lo), hi.map(Node::Int).unwrap_or(Node::Null)]))
            .map_err(|e| format!("_valid_shots: {e:?}"))?,
        None => {
            if let Some(m) = doc.as_map_mut() {
                m.remove("_valid_shots");
            }
        }
    }
    let chains = declared_chains(
        resolution.as_map().and_then(|m| m.get("manifest")).and_then(Node::as_map).and_then(|m| m.get(CHAINS_KEY)),
    );
    doc.set("provenance/fylite:resolution", record(&selected, req, &notes, &chains))
        .map_err(|e| format!("provenance: {e:?}"))?;
    Ok(Resolved { doc, selected, notes })
}

/// For `fy list devices <id>`: per resolved IDS, the providers with their shot ranges and chains,
/// and what no shot resolves to.
pub fn describe(resolution: &Node) -> Vec<(String, String)> {
    let Ok(res) = check_type(resolution) else { return Vec::new() };
    let providers = res.get("manifest").and_then(Node::as_map).and_then(|m| m.get("providers"));
    let mut out = Vec::new();
    for ids in strings(res.get("resolved_ids")) {
        let p = providers.and_then(Node::as_map).and_then(|m| m.get(&ids));
        let pm = p.and_then(Node::as_map);
        let default = pm.and_then(|m| m.get("default")).and_then(Node::as_str).unwrap_or("?");
        let mut parts = Vec::new();
        for (name, v) in available_of(p) {
            if backend_of(v) != "static" {
                continue;
            }
            let mut s = match range_of(v) {
                Some(r) => format!("{name} {}", show_range(r)),
                None => name.to_string(),
            };
            if let Some(c) = chain_of(v) {
                s.push_str(&format!(" chain {c}"));
            }
            parts.push(s);
        }
        let latest = choose(p, "static", None).ok().and_then(|c| c.provider).unwrap_or_else(|| "?".into());
        out.push((ids, format!("no shot -> {latest} · default {default} · {}", parts.join(" · "))));
    }
    if let Some(f) = res.get("fixed").and_then(Node::as_map) {
        for (ids, v) in f.iter() {
            let why = v.as_map().and_then(|m| m.get("why")).and_then(Node::as_str).or_else(|| v.as_str()).unwrap_or("fixed");
            out.push((ids.to_string(), format!("fixed: {why}")));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::json;

    /// EAST's magnetics and wall providers in miniature, as fydoc's manifest writes them after the
    /// 2026-09-13 measurement-chain ruling (no est2 array, no duplicate `east`, wall default base).
    fn manifest(default: &str) -> Node {
        json::parse(&format!(r#"{{
          "magnetics": {{"default": "{default}", "available": {{
            "base":      {{"backend": "static", "valid_shots": [0, 97030], "measurement_chain": "east"}},
            "east_new":  {{"backend": "static", "valid_shots": [97034, null], "measurement_chain": "east", "preferred": true}},
            "pcs":       {{"backend": "static", "valid_shots": null, "measurement_chain": "pcs_east"}},
            "efit":      {{"backend": "static", "valid_shots": null, "measurement_chain": "efit_east"}},
            "pcs_vp_post80000": {{"backend": "mdsplus", "valid_shots": [80000, null], "measurement_chain": "pcs_east"}},
            "efit_east": {{"backend": "mdsplus", "valid_shots": null}}}}}},
          "wall": {{"default": "base", "available": {{
            "base": {{"backend": "static", "valid_shots": null}},
            "m093060": {{"backend": "static", "valid_shots": null}}}}}},
          "pf_active": {{"default": "base", "available": {{"base": {{"backend": "static"}}, "yu": {{"backend": "static"}}}}}}
        }}"#)).unwrap()
    }

    fn chains() -> Node {
        json::parse(r#"{"pcs_east": {"kind": "mdsplus_tree", "tree": "pcs_east"},
                        "east": {"kind": "mdsplus_tree", "tree": "east"},
                        "efit_east": {"kind": "mdsplus_tree", "tree": "efit_east"}}"#).unwrap()
    }

    fn pick(m: &Node, ids: &str, shot: Option<i64>) -> Choice {
        choose(m.get(ids), "static", shot).unwrap()
    }

    #[test]
    fn the_shot_decides_and_no_shot_is_the_latest_shot() {
        for default in ["east_new", "pcs"] {
            let m = manifest(default);
            //: ≤97030 → the old naming family
            let c = pick(&m, "magnetics", Some(70754));
            assert_eq!(c.provider.as_deref(), Some("base"), "{c:?}");
            assert_eq!(c.range, Some((0, Some(97030))));
            //: ≥97034, and no shot at all → east_new, whatever the default is
            for shot in [Some(97034), Some(137985), None] {
                let c = pick(&m, "magnetics", shot);
                assert_eq!(c.provider.as_deref(), Some("east_new"), "{default} {shot:?} {c:?}");
                assert_eq!(c.range, Some((97034, None)));
            }
            //: the unknown band [97031, 97033] with no chain: nothing shot-anchored covers it → the default, said
            let c = pick(&m, "magnetics", Some(97032));
            assert_eq!(c.provider.as_deref(), Some(default));
            //: the mdsplus era binding [80000, —] never competes for geometry
            assert_eq!(pick(&m, "magnetics", Some(120000)).provider.as_deref(), Some("east_new"));
            //: no shot anchors at all → the default, which is `base` again for the wall
            assert_eq!(pick(&m, "wall", Some(70754)).provider.as_deref(), Some("base"));
            assert_eq!(pick(&m, "wall", None).provider.as_deref(), Some("base"));
        }
    }

    #[test]
    fn the_measurement_chain_decides_within_itself_and_refuses_by_name() {
        let m = manifest("east_new");
        let mag = m.get("magnetics");
        let within = |shot: Option<i64>, chain: &str| choose_in_chain("magnetics", mag, "static", shot, chain);
        //: chain `east`: a ranged provider covering the shot wins, and no shot is the open upper end
        assert_eq!(within(Some(70754), "east").unwrap().provider.as_deref(), Some("base"));
        assert_eq!(within(Some(137985), "east").unwrap().provider.as_deref(), Some("east_new"));
        assert_eq!(within(None, "east").unwrap().provider.as_deref(), Some("east_new"));
        //: a gap inside the chain is refused naming the chain, the shot and the declared ranges — never the nearest
        let gap = within(Some(97032), "east").unwrap_err();
        assert!(gap.contains("\"east\"") && gap.contains("97032") && gap.contains("[0, 97030]") && gap.contains("[97034, —]"), "{gap}");
        //: a rangeless provider is used when no ranged one of its chain covers the shot; the era-limited
        //: mdsplus binding of the same chain does not compete for geometry
        let pcs = within(Some(137985), "pcs_east").unwrap();
        assert_eq!((pcs.provider.as_deref(), pcs.range), (Some("pcs"), None));
        assert!(pcs.why.contains("pcs_east"), "{pcs:?}");
        assert_eq!(within(Some(45000), "efit_east").unwrap().provider.as_deref(), Some("efit"));
        //: a chain no geometry provider of this IDS is in
        assert!(within(Some(1), "nope").unwrap_err().contains("no static provider is in measurement chain"));
        //: the manifest's own consistency: declared chains, no two covering providers within a chain
        assert!(check_chains("magnetics", mag, Some(&chains()), "static").is_ok());
        let undeclared = check_chains("magnetics", mag, Some(&json::parse(r#"{"east": {}}"#).unwrap()), "static").unwrap_err();
        assert!(undeclared.contains("\"pcs\"") && undeclared.contains("pcs_east") && undeclared.contains("does not declare"), "{undeclared}");
        let overlapping = json::parse(r#"{"available": {
            "base": {"backend": "static", "valid_shots": [0, 97030], "measurement_chain": "east"},
            "twin": {"backend": "static", "valid_shots": [0, 97030], "measurement_chain": "east"}}}"#).unwrap();
        let e = check_chains("magnetics", Some(&overlapping), Some(&chains()), "static").unwrap_err();
        assert!(e.contains("\"base\"") && e.contains("\"twin\"") && e.contains("\"east\""), "{e}");
        assert!(choose_in_chain("magnetics", Some(&overlapping), "static", Some(70754), "east").unwrap_err().contains("two static providers"));
        let two_rangeless = json::parse(r#"{"available": {
            "pcs": {"backend": "static", "valid_shots": null, "measurement_chain": "pcs_east"},
            "pcs2": {"backend": "static", "valid_shots": null, "measurement_chain": "pcs_east"}}}"#).unwrap();
        assert!(check_chains("magnetics", Some(&two_rangeless), Some(&chains()), "static").unwrap_err().contains("without a shot range"));
    }

    fn resolution() -> Node {
        let mut r = json::parse(r#"{"@type": "fylite:DeviceResolution", "resolved_ids": ["magnetics", "wall"],
            "fixed": {"pf_active": {"why": "one converted set (ruling)"}}}"#).unwrap();
        r.set("manifest/providers", manifest("east_new")).unwrap();
        r.set("manifest/measurement_chains", chains()).unwrap();
        let group = |name: &str, n: i64, chain: &str| -> Node {
            json::parse(&format!(r#"{{"card": {{"magnetics": {{"fylite:provider": "{name}", "measurement_chain": "{chain}", "n": {n}}}, "_basis": "{name} basis"}},
                                      "document": {{"magnetics": {{"fylite:provider": "{name}", "measurement_chain": "{chain}", "n": {n}, "doc": true}}, "_basis": "{name} basis"}},
                                      "source_files": {{"magnetics": "providers/magnetics/{name}.jsonld"}}}}"#)).unwrap()
        };
        for (name, n, chain) in [("base", 38, "east"), ("east_new", 79, "east"), ("pcs", 38, "pcs_east"), ("efit", 76, "efit_east")] {
            r.set(&format!("variants/magnetics/{name}"), group(name, n, chain)).unwrap();
        }
        r.set("variants/wall/base", json::parse(r#"{"card": {"wall": {"u": "base"}}, "document": {"wall": {"u": "base"}}}"#).unwrap()).unwrap();
        r.set("variants/wall/m093060", json::parse(r#"{"fylite:absent": "no reader-facing limiter unit name"}"#).unwrap()).unwrap();
        r
    }

    fn card() -> Node {
        json::parse(r#"{"_basis": "?", "magnetics": {"fylite:provider": "east_new", "n": 79}, "wall": {"u": "base"},
                        "pf_active": {"coil": []}, "provenance": {"source_files": {"magnetics": "x", "magnetics:pcs": "p", "tf": "t"}}}"#).unwrap()
    }

    fn ask(shot: Option<i64>, chain: Option<&str>) -> Request {
        Request { shot, measurement_chain: chain.map(str::to_string), ..Default::default() }
    }

    #[test]
    fn a_request_splices_the_converted_group_over_the_card() {
        let res = resolution();
        let r = resolve(&card(), &res, &ask(Some(70754), None), Form::Card).unwrap();
        assert_eq!(r.doc.get("magnetics/fylite:provider").and_then(Node::as_str), Some("base"));
        assert_eq!(r.doc.get("_basis").and_then(Node::as_str), Some("base basis"));
        //: the magnetics source files are the variant's; others untouched
        assert_eq!(r.doc.get("provenance/source_files/magnetics").and_then(Node::as_str), Some("providers/magnetics/base.jsonld"));
        assert_eq!(r.doc.get("provenance/source_files/tf").and_then(Node::as_str), Some("t"));
        assert!(r.doc.get("provenance/source_files/magnetics:pcs").is_none());
        assert_eq!(r.doc.get("provenance/fylite:resolution/ids/magnetics/shots/1").and_then(Node::as_i64), Some(97030));
        assert_eq!(r.doc.get("provenance/fylite:resolution/shot").and_then(Node::as_i64), Some(70754));
        assert_eq!(r.doc.get("_valid_shots"), Some(&Node::List(vec![Node::Int(0), Node::Int(97030)])));
        //: the record names the chains the device declares
        assert_eq!(r.doc.get("provenance/fylite:resolution/measurement_chains/1").and_then(Node::as_str), Some("east"));
        //: rangeless providers only, shot given: the document vouches for that shot alone
        let n = resolve(&r.doc, &res, &ask(Some(137985), Some("efit_east")), Form::Card).unwrap();
        assert_eq!(n.doc.get("magnetics/fylite:provider").and_then(Node::as_str), Some("efit"));
        assert_eq!(n.doc.get("magnetics/measurement_chain").and_then(Node::as_str), Some("efit_east"));
        assert_eq!(n.doc.get("_valid_shots"), Some(&Node::List(vec![Node::Int(137985), Node::Int(137985)])));
        assert_eq!(n.doc.get("provenance/fylite:resolution/measurement_chain").and_then(Node::as_str), Some("efit_east"));
        //: the document form writes the document spelling
        let d = resolve(&card(), &res, &Request::default(), Form::Document).unwrap();
        assert_eq!(d.doc.get("magnetics/doc"), Some(&Node::Bool(true)));
        assert!(d.doc.get("provenance/fylite:resolution/shot").and_then(Node::as_str).unwrap().contains("latest"));
        //: resolving twice is resolving once
        let again = resolve(&d.doc, &res, &Request::default(), Form::Document).unwrap();
        assert_eq!(again.doc, d.doc);
    }

    #[test]
    fn a_request_is_shot_and_chain_only_and_every_refusal_is_named() {
        let res = resolution();
        let prov = |shot, chain| selection(&res, &ask(shot, chain)).map(|(s, _)| s[0].provider.clone());
        assert_eq!(prov(Some(70754), Some("east")).unwrap(), "base");
        assert_eq!(prov(Some(137985), Some("east")).unwrap(), "east_new");
        assert_eq!(prov(Some(137985), Some("pcs_east")).unwrap(), "pcs");
        assert_eq!(prov(None, Some("efit_east")).unwrap(), "efit");
        //: the chain decides magnetics only: the wall keeps the manifest default
        let (s, _) = selection(&res, &ask(Some(137985), Some("pcs_east"))).unwrap();
        assert_eq!((s[1].ids.as_str(), s[1].provider.as_str()), ("wall", "base"));
        //: an undeclared chain (there is no est2 chain) is refused, never the default
        let e = prov(Some(137985), Some("est2")).unwrap_err();
        assert!(e.contains("\"est2\"") && e.contains("not declared") && e.contains("pcs_east, east, efit_east"), "{e}");
        //: a gap inside the chain, through the request
        assert!(prov(Some(97032), Some("east")).unwrap_err().contains("97032"));
        //: no chain: today's rule; strict refuses the default used outside its range
        assert_eq!(prov(Some(97032), None).unwrap(), "east_new");
        let strict = Request { strict: true, ..ask(Some(97032), None) };
        assert!(selection(&res, &strict).unwrap_err().contains("outside"));
        //: the request keys are shot / measurement_chain / strict — a provider or a basis is refused by name
        for (key, doc) in [("providers", r#"{"providers": {"magnetics": "efit"}}"#), ("basis", r#"{"basis": "est2"}"#),
                           ("provider", r#"{"shot": 1, "provider": "efit"}"#)] {
            let e = Request::from_node(&json::parse(doc).unwrap()).unwrap_err();
            assert!(e.contains(&format!("{key:?}")) && e.contains("measurement_chain"), "{e}");
        }
        let q = Request::from_node(&json::parse(r#"{"shot": 137985, "measurement_chain": "east", "strict": true}"#).unwrap()).unwrap();
        assert_eq!(q, Request { shot: Some(137985), measurement_chain: Some("east".into()), strict: true });
        //: a converted-away variant is refused with the converter's reason
        let mut no_base = resolution();
        no_base.set("manifest/providers/wall/default", Node::Str("m093060".into())).unwrap();
        let e = resolve(&card(), &no_base, &Request::default(), Form::Card).unwrap_err();
        assert!(e.contains("reader-facing"), "{e}");
        //: the one `_valid_shots` comparison
        let c = json::parse(r#"{"_valid_shots": [97034, null]}"#).unwrap();
        assert!(card_covers(&c, 160000).is_ok());
        assert_eq!(card_covers(&c, 70754), Err(Some((97034, None))));
        assert_eq!(card_covers(&json::parse("{}").unwrap(), 1), Err(None));
    }

    /// ★Gate (a), bundled tier: the EAST resolution compiled into this build.  A
    /// build without facts (`FY_FACTS_RS` unset) has nothing to check, and says so.
    #[test]
    fn the_bundled_east_resolution_resolves_by_shot_and_chain() {
        let Some(text) = crate::facts::embedded_resolution("device", "east") else {
            eprintln!("skip: no bundled device/east resolution in this build (FY_FACTS_RS)");
            return;
        };
        let res = json::parse(text).unwrap();
        let mag = |shot: Option<i64>, chain: Option<&str>| {
            selection(&res, &ask(shot, chain)).unwrap().0.into_iter().find(|s| s.ids == "magnetics").unwrap()
        };
        let old = mag(Some(70754), None);
        assert_eq!(old.range.and_then(|r| r.1), Some(97030), "{old:?}");
        for shot in [Some(137985), None] {
            assert_eq!(mag(shot, None).provider, "east_new", "{shot:?}");
        }
        assert_eq!(mag(Some(70754), Some("east")).provider, "base");
        assert_eq!(mag(Some(137985), Some("efit_east")).provider, "efit");
        assert!(selection(&res, &ask(Some(137985), Some("est2"))).unwrap_err().contains("not declared"));
    }
}
