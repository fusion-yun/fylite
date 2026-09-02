//! A CASE, from documents to documents — the input / output half of a run.
//!
//! ★★The split.  The kernel completes a case handed to it as a STRUCTURE
//! (settings by name, bound inputs by fyo path) and answers with fields by
//! fyo path (`fylite_rs_case_*`, [`crate::kernel`]).  Everything on either
//! side of that door is this module's: reading the `fyo:ScenarioSpecification`
//! documents that make up a plan and composing them (graph union by
//! identity, later documents overriding earlier ones — FYL-REPORT-06 §5),
//! resolving the plan's bound inputs through the data layer ([`crate::io`]:
//! a g-file, a JSON / HDF5 / netCDF document, an inline dataset), and writing
//! the run back as ONE `spo:ComputationRecord` with its produced datasets as
//! fyo documents beside it — the one-structure-in, one-structure-out model.
//!
//! ★What a plan looks like here is the public corpus's compaction
//! (`cases/context.jsonld`): `parameters[]` of `{sets_parameter, literal_value}`,
//! `inputs[]` of `spo:PortBinding`, `prescribes_code.id` = `code/<bar>`.
//! The `spo:` / `fyo:` prefixed spellings of the same keys are read too, so
//! a document compacted against a context that keeps the prefixes composes
//! with one that drops them.  Full JSON-LD expansion is NOT performed: a
//! plan written against another context is refused rather than half-read.
//!
//! ★Vocabulary: the record and the datasets carry fyo / spo terms only.
//! Run facts the kernel reports as scalars (steps, settled, a residual) are
//! output ports bound to `spo:QuantityValue`s; the datasets are bound to
//! output ports as `spo:Concretization`s with a SHA-256 checksum.

use crate::checksum::sha256_hex;
use crate::document::{Array, Map, Node};
use crate::fyo_interface as fi;
use crate::json;
use crate::kernel::{Kernel, KernelError, RawOutcome};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct CaseError(pub String);

impl std::fmt::Display for CaseError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

fn err<T>(m: impl Into<String>) -> Result<T, CaseError> {
    Err(CaseError(m.into()))
}

pub const FYO: &str = "https://fusion-yun.github.io/fyo/latest/";
pub const SPO: &str = "https://fusion-yun.github.io/spo/latest/";
pub const LD_JSON: &str = "https://www.iana.org/assignments/media-types/application/ld+json";

// --------------------------------------------------------------------------- #
// the plan
// --------------------------------------------------------------------------- #

/// One document that went into the plan.
#[derive(Debug, Clone)]
pub struct Source {
    pub path: PathBuf,
    pub id: Option<String>,
    pub sha256: String,
    pub bytes: usize,
}

/// One parameter setting, as the plan states it.
#[derive(Debug, Clone)]
pub struct Setting {
    pub name: String,
    pub iri: String,
    pub value: Node,
    /// Index into `Plan::sources`; `None` for a command-line override.
    pub from: Option<usize>,
}

/// One input port binding: what the plan binds to the port, or nothing
/// yet (an OPEN port the caller has to supply).
#[derive(Debug, Clone)]
pub struct Binding {
    pub port: String,
    pub endpoint: Option<String>,
    pub inline: Option<Node>,
    pub note: Option<String>,
    pub from: Option<usize>,
}

/// A requested output concretization.
#[derive(Debug, Clone)]
pub struct OutputRequest {
    pub port: String,
    pub format_iri: Option<String>,
    pub storage_uri: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct Plan {
    pub id: String,
    pub code: String,
    pub task_kind: Option<String>,
    pub title: Option<String>,
    pub settings: Vec<Setting>,
    pub inputs: Vec<Binding>,
    pub outputs: Vec<OutputRequest>,
    pub caveats: Vec<String>,
    pub discharge: Option<Node>,
    pub sources: Vec<Source>,
}

fn get<'a>(m: &'a Map, keys: &[&str]) -> Option<&'a Node> {
    keys.iter().find_map(|k| m.get(k))
}

fn id_of(n: &Node) -> Option<String> {
    match n {
        Node::Str(s) => Some(s.clone()),
        Node::Map(m) => get(m, &["id", "@id"]).and_then(Node::as_str).map(str::to_string),
        _ => None,
    }
}

/// One string out of a language map (zh, then en, then the first), a
/// bare string, or a list's first string.
fn lang(n: &Node) -> Option<String> {
    match n {
        Node::Str(s) => Some(s.clone()),
        Node::Map(m) => {
            if let Some(v) = m.get("@value").and_then(Node::as_str) {
                return Some(v.to_string());
            }
            for k in ["zh", "en"] {
                if let Some(v) = m.get(k).and_then(Node::as_str) {
                    return Some(v.to_string());
                }
            }
            m.iter().find_map(|(_, v)| v.as_str().map(str::to_string))
        }
        Node::List(l) => l.iter().find_map(lang),
        _ => None,
    }
}

fn strings(n: &Node) -> Vec<String> {
    match n {
        Node::Str(s) => vec![s.clone()],
        Node::List(l) => l.iter().flat_map(strings).collect(),
        Node::Map(m) => {
            //: a language map of lists: every language's entries, zh first
            let mut out = Vec::new();
            for k in ["zh", "en"] {
                if let Some(v) = m.get(k) {
                    out.extend(strings(v));
                }
            }
            if out.is_empty() {
                out.extend(m.iter().flat_map(|(_, v)| strings(v)));
            }
            out
        }
        _ => Vec::new(),
    }
}

fn unwrap_value(n: &Node) -> Node {
    if let Node::Map(m) = n {
        if let Some(v) = m.get("@value") {
            return v.clone();
        }
    }
    n.clone()
}

fn fragment(iri: &str) -> String {
    iri.rsplit('#').next().unwrap_or(iri).to_string()
}

/// Read one plan document from disk.
pub fn read_source(path: &Path) -> Result<(Source, Node), CaseError> {
    let bytes = std::fs::read(path).map_err(|e| CaseError(format!("{}: {e}", path.display())))?;
    let text = String::from_utf8(bytes.clone()).map_err(|_| CaseError(format!("{}: not UTF-8", path.display())))?;
    let node = json::parse(&text).map_err(|e| CaseError(format!("{}: {e:?}", path.display())))?;
    let id = node.as_map().and_then(|m| get(m, &["id", "@id"])).and_then(Node::as_str).map(str::to_string);
    Ok((Source { path: path.to_path_buf(), id, sha256: sha256_hex(&bytes), bytes: bytes.len() }, node))
}

/// Compose the plan documents, in order of increasing precedence.
pub fn compose(docs: Vec<(Source, Node)>) -> Result<Plan, CaseError> {
    if docs.is_empty() {
        return err("no plan document given");
    }
    let mut plan = Plan::default();
    for (k, (src, node)) in docs.into_iter().enumerate() {
        let Some(m) = node.as_map() else {
            return err(format!("{}: the document is not an object", src.path.display()));
        };
        let ty = get(m, &["type", "@type"]).map(strings).unwrap_or_default();
        if !ty.iter().any(|t| t.ends_with("ScenarioSpecification") || t.ends_with("ComputationPlan")) {
            return err(format!("{}: not a fyo:ScenarioSpecification / spo:ComputationPlan (type {:?})",
                               src.path.display(), ty));
        }
        if k == 0 {
            plan.id = src.id.clone().unwrap_or_else(|| "plan".into());
        }
        if let Some(c) = get(m, &["prescribes_code", "spo:prescribes_code"]).and_then(id_of) {
            plan.code = c;
        }
        if let Some(t) = get(m, &["prescribed_task_kind", "fyo:prescribed_task_kind"]).and_then(id_of) {
            plan.task_kind = Some(t);
        }
        if let Some(t) = get(m, &["title", "rdfs:label"]).and_then(lang) {
            plan.title = Some(t);
        }
        if let Some(d) = get(m, &["about_discharge", "fyo:about_discharge"]) {
            plan.discharge = Some(d.clone());
        }
        if let Some(c) = get(m, &["caveat", "spo:caveat"]) {
            for s in strings(c) {
                if !plan.caveats.contains(&s) {
                    plan.caveats.push(s);
                }
            }
        }
        if let Some(Node::List(ps)) = get(m, &["parameters", "spo:has_parameter_setting"]) {
            for p in ps {
                let Some(pm) = p.as_map() else { continue };
                let Some(iri) = get(pm, &["sets_parameter", "spo:sets_parameter"]).and_then(id_of) else {
                    return err(format!("{}: a parameter setting names no `sets_parameter`", src.path.display()));
                };
                let value = get(pm, &["literal_value", "spo:literal_value"]).map(unwrap_value)
                    .or_else(|| get(pm, &["has_quantity_value", "spo:has_quantity_value"]).and_then(|q| {
                        q.as_map().and_then(|qm| get(qm, &["numeric_value", "spo:numeric_value"])).cloned()
                    }));
                let Some(value) = value else {
                    return err(format!("{}: parameter `{iri}` carries neither literal_value nor a quantity value",
                                       src.path.display()));
                };
                plan.set_from(fragment(&iri), iri, value, Some(k));
            }
        }
        if let Some(Node::List(bs)) = get(m, &["inputs", "spo:has_port_binding"]) {
            for b in bs {
                let Some(bm) = b.as_map() else { continue };
                let port_node = get(bm, &["binds_port", "spo:binds_port"]);
                let port = port_node.and_then(|pn| match pn {
                    Node::Map(pm) => get(pm, &["port_name", "spo:port_name"]).and_then(Node::as_str).map(str::to_string)
                        .or_else(|| id_of(pn).map(|s| fragment(&s))),
                    other => id_of(other).map(|s| fragment(&s)),
                });
                let Some(port) = port else {
                    return err(format!("{}: a port binding names no port", src.path.display()));
                };
                let direction = port_node.and_then(Node::as_map)
                    .and_then(|pm| get(pm, &["port_direction", "spo:port_direction"])).and_then(Node::as_str)
                    .unwrap_or("input").to_string();
                let conc = get(bm, &["bound_concretization", "spo:bound_concretization"]).and_then(Node::as_map);
                if direction == "output" {
                    plan.outputs.retain(|o| o.port != port);
                    plan.outputs.push(OutputRequest {
                        port,
                        format_iri: conc.and_then(|c| get(c, &["format_iri", "spo:format_iri"])).and_then(id_of),
                        storage_uri: conc.and_then(|c| get(c, &["storage_uri", "spo:storage_uri"])).and_then(Node::as_str).map(str::to_string),
                    });
                    continue;
                }
                let endpoint = get(bm, &["bound_endpoint", "spo:bound_endpoint"]).and_then(|e| match e {
                    Node::List(l) => l.first().cloned(),
                    other => Some(other.clone()),
                }).and_then(|e| match &e {
                    Node::Map(em) => get(em, &["endpoint_uri", "spo:endpoint_uri", "storage_uri", "spo:storage_uri"])
                        .and_then(Node::as_str).map(str::to_string),
                    other => id_of(other),
                }).or_else(|| conc.and_then(|c| get(c, &["storage_uri", "spo:storage_uri"])).and_then(Node::as_str).map(str::to_string));
                let inline = get(bm, &["bound_to", "spo:bound_to"]).cloned();
                let note = get(bm, &["note", "comment", "rdfs:comment"]).and_then(lang);
                plan.inputs.retain(|x| x.port != port);
                plan.inputs.push(Binding { port, endpoint, inline, note, from: Some(k) });
            }
        }
        plan.sources.push(src);
    }
    if plan.code.is_empty() {
        return err("the plan prescribes no code (`prescribes_code`); pass --code");
    }
    Ok(plan)
}

impl Plan {
    fn set_from(&mut self, name: String, iri: String, value: Node, from: Option<usize>) {
        self.settings.retain(|s| s.name != name);
        self.settings.push(Setting { name, iri, value, from });
    }

    /// The bar / code name: the last segment of the code IRI.
    pub fn bar(&self) -> String {
        self.code.trim_end_matches('/').rsplit('/').next().unwrap_or(&self.code).to_string()
    }

    /// A command-line override: `name=value`, the value a JSON literal
    /// where it parses as one and a string otherwise.
    pub fn set_override(&mut self, spec: &str) -> Result<(), CaseError> {
        let Some((k, v)) = spec.split_once('=') else {
            return err(format!("--set wants name=value, got `{spec}`"));
        };
        let value = json::parse(v).unwrap_or_else(|_| Node::Str(v.to_string()));
        let iri = format!("{}#{}", self.code, k);
        self.set_from(k.to_string(), iri, value, None);
        Ok(())
    }

    /// A command-line binding: `port=path`.
    pub fn bind_override(&mut self, spec: &str) -> Result<(), CaseError> {
        let Some((port, path)) = spec.split_once('=') else {
            return err(format!("--bind wants port=path, got `{spec}`"));
        };
        self.inputs.retain(|b| b.port != port);
        self.inputs.push(Binding { port: port.to_string(), endpoint: Some(path.to_string()),
                                   inline: None, note: None, from: None });
        Ok(())
    }

    /// The composed plan as one document (the corpus compaction).
    pub fn to_node(&self) -> Node {
        let mut m = Map::new();
        m.insert("@context", plan_context());
        m.insert("id", self.id.clone().into());
        m.insert("type", "fyo:ScenarioSpecification".into());
        if let Some(t) = &self.title {
            m.insert("title", t.clone().into());
        }
        if let Some(t) = &self.task_kind {
            m.insert("prescribed_task_kind", t.clone().into());
        }
        let mut code = Map::new();
        code.insert("id", self.code.clone().into());
        code.insert("type", "spo:Code".into());
        m.insert("prescribes_code", Node::Map(code));
        if let Some(d) = &self.discharge {
            m.insert("about_discharge", d.clone());
        }
        let params: Vec<Node> = self.settings.iter().map(|s| {
            let mut p = Map::new();
            p.insert("type", "spo:ParameterSetting".into());
            p.insert("sets_parameter", s.iri.clone().into());
            p.insert("literal_value", s.value.clone());
            Node::Map(p)
        }).collect();
        m.insert("parameters", Node::List(params));
        if !self.inputs.is_empty() {
            let inputs: Vec<Node> = self.inputs.iter().map(|b| {
                let mut p = Map::new();
                p.insert("type", "spo:PortBinding".into());
                let mut port = Map::new();
                port.insert("type", "spo:PortDefinition".into());
                port.insert("port_name", b.port.clone().into());
                port.insert("port_direction", "input".into());
                p.insert("binds_port", Node::Map(port));
                if let Some(e) = &b.endpoint {
                    let mut ep = Map::new();
                    ep.insert("type", "spo:DataSourceEndpoint".into());
                    ep.insert("endpoint_uri", e.clone().into());
                    p.insert("bound_endpoint", Node::List(vec![Node::Map(ep)]));
                }
                if let Some(i) = &b.inline {
                    p.insert("bound_to", i.clone());
                }
                if let Some(n) = &b.note {
                    p.insert("comment", n.clone().into());
                }
                Node::Map(p)
            }).collect();
            m.insert("inputs", Node::List(inputs));
        }
        if !self.caveats.is_empty() {
            m.insert("caveat", Node::List(self.caveats.iter().map(|c| c.clone().into()).collect()));
        }
        Node::Map(m)
    }

    /// The settings as the kernel takes them: numbers and texts.
    pub fn kernel_settings(&self) -> Result<(Vec<(String, f64)>, Vec<(String, String)>), CaseError> {
        let mut numbers = Vec::new();
        let mut texts = Vec::new();
        for s in &self.settings {
            match &s.value {
                Node::Bool(b) => numbers.push((s.name.clone(), if *b { 1.0 } else { 0.0 })),
                Node::Int(i) => numbers.push((s.name.clone(), *i as f64)),
                Node::Float(f) => numbers.push((s.name.clone(), *f)),
                Node::Str(t) => texts.push((s.name.clone(), t.clone())),
                Node::Null => texts.push((s.name.clone(), String::new())),
                other => return err(format!(
                    "setting `{}` is not a scalar ({}); the kernel takes numbers and texts",
                    s.name, kind_of(other))),
            }
        }
        Ok((numbers, texts))
    }
}

fn kind_of(n: &Node) -> &'static str {
    match n {
        Node::Null => "null", Node::Bool(_) => "boolean", Node::Int(_) => "integer",
        Node::Float(_) => "float", Node::Str(_) => "string", Node::Array(_) => "array",
        Node::List(_) => "list", Node::Map(_) => "object",
    }
}

fn plan_context() -> Node {
    let mut c = Map::new();
    c.insert("@version", Node::Float(1.1));
    c.insert("fyo", FYO.into());
    c.insert("spo", SPO.into());
    c.insert("rdfs", "http://www.w3.org/2000/01/rdf-schema#".into());
    c.insert("id", "@id".into());
    c.insert("type", "@type".into());
    c.insert("title", "rdfs:label".into());
    c.insert("comment", "rdfs:comment".into());
    c.insert("caveat", spo_term("caveat", Some("@set"), None));
    c.insert("prescribed_task_kind", {
        let mut t = Map::new();
        t.insert("@id", "fyo:prescribed_task_kind".into());
        t.insert("@type", "@id".into());
        Node::Map(t)
    });
    for k in ["prescribes_code", "bound_to", "bound_endpoint", "endpoint_uri", "binds_port", "port_name",
              "port_direction", "bound_concretization", "storage_uri", "checksum", "byte_size",
              "numeric_value", "has_unit", "run_state", "started_at", "ended_at", "executed_code",
              "realizes", "has_output", "has_input", "name", "version"] {
        c.insert(k, format!("spo:{k}").into());
    }
    c.insert("about_discharge", "fyo:about_discharge".into());
    c.insert("pulse_number", "fyo:pulse_number".into());
    c.insert("performed_on", "fyo:performed_on".into());
    c.insert("parameters", spo_term("has_parameter_setting", Some("@list"), None));
    c.insert("inputs", spo_term("has_port_binding", Some("@set"), None));
    c.insert("sets_parameter", spo_term("sets_parameter", None, Some("@id")));
    c.insert("literal_value", spo_term("literal_value", None, Some("@json")));
    c.insert("format_iri", spo_term("format_iri", None, Some("@id")));
    c.insert("concretized_as", {
        let mut t = Map::new();
        t.insert("@reverse", "http://purl.obolibrary.org/obo/BFO_0000059".into());
        t.insert("@container", "@set".into());
        Node::Map(t)
    });
    Node::Map(c)
}

fn spo_term(name: &str, container: Option<&str>, ty: Option<&str>) -> Node {
    let mut t = Map::new();
    t.insert("@id", format!("spo:{name}").into());
    if let Some(c) = container {
        t.insert("@container", c.into());
    }
    if let Some(y) = ty {
        t.insert("@type", y.into());
    }
    Node::Map(t)
}

// --------------------------------------------------------------------------- #
// the inputs, resolved through the data layer
// --------------------------------------------------------------------------- #

/// One input as it was actually resolved.
#[derive(Debug, Clone)]
pub struct Resolved {
    pub port: String,
    pub storage_uri: Option<String>,
    pub sha256: Option<String>,
    pub bytes: Option<usize>,
    /// The fyo paths handed to the kernel from this input.
    pub slots: Vec<String>,
    pub open: bool,
    /// Why nothing reached the kernel from an input that IS bound — an
    /// inline ICE with no declared slot (a transcription, not a dataset).
    pub unresolved: Option<String>,
}

fn numbers_of(n: &Node) -> Option<Vec<f64>> {
    match n {
        Node::Array(a) => a.to_f64(),
        Node::List(l) => l.iter().map(Node::as_f64).collect(),
        Node::Int(_) | Node::Float(_) => n.as_f64().map(|v| vec![v]),
        _ => None,
    }
}

/// Every declared slot of one fyo document, as `<ids>/<path>` arrays.
fn flatten(ids: &str, doc: &Node, into: &mut Vec<(String, Vec<f64>)>) -> Vec<String> {
    let mut got = Vec::new();
    let want = format!("fyo:{ids}");
    for t in fi::TABLES {
        if t.doc_type != want {
            continue;
        }
        for s in t.slots {
            if let Some(v) = doc.walk(s.path, true).and_then(numbers_of) {
                let key = format!("{ids}/{}", s.path);
                if !got.contains(&key) {
                    got.push(key.clone());
                    into.push((key, v));
                }
            }
        }
    }
    got
}

fn ids_of_doc(doc: &Node) -> Option<String> {
    let m = doc.as_map()?;
    for t in get(m, &["type", "@type"]).map(strings).unwrap_or_default() {
        let t = t.trim_start_matches("fyo:");
        let t = t.rsplit('/').next().unwrap_or(t);
        if fi::TABLES.iter().any(|tb| tb.doc_type == format!("fyo:{t}")) {
            return Some(t.to_string());
        }
        //: the ontology's class name for the same IDS (`fyo:CoreProfiles`)
        let snake: String = t.chars().enumerate().map(|(i, c)| {
            if c.is_ascii_uppercase() && i > 0 { format!("_{}", c.to_ascii_lowercase()) } else { c.to_ascii_lowercase().to_string() }
        }).collect();
        if fi::TABLES.iter().any(|tb| tb.doc_type == format!("fyo:{snake}")) {
            return Some(snake);
        }
    }
    None
}

/// Resolve the plan's input bindings into the slots the kernel takes.
pub fn resolve_inputs(plan: &Plan, base: &Path) -> Result<(Vec<(String, Vec<f64>)>, Vec<Resolved>), CaseError> {
    let mut slots = Vec::new();
    let mut resolved = Vec::new();
    for b in &plan.inputs {
        let mut r = Resolved { port: b.port.clone(), storage_uri: None, sha256: None, bytes: None,
                               slots: Vec::new(), open: false, unresolved: None };
        if let Some(inline) = &b.inline {
            if let Some(v) = numbers_of(inline) {
                r.slots.push(b.port.clone());
                slots.push((b.port.clone(), v));
            } else if let Some(ids) = ids_of_doc(inline) {
                r.slots = flatten(&ids, inline, &mut slots);
            } else if inline.as_map().map(|m| m.len() <= 2 && get(m, &["id", "@id"]).is_some()).unwrap_or(false) {
                //: a bare reference `{id}`: treat the id as a location
                r.storage_uri = id_of(inline);
            } else {
                //: bound, but to nothing the kernel can take — a transcribed
                //: reference table, say.  Not an error here: the plan is
                //: handed on as written and the kernel says what it lacks.
                r.unresolved = Some("the inline `bound_to` is neither a fyo document the kernel declares slots for nor a numeric array".into());
            }
        }
        let endpoint = r.storage_uri.clone().or_else(|| b.endpoint.clone());
        if let Some(e) = endpoint {
            let path = e.strip_prefix("file://").unwrap_or(&e);
            let path = path.strip_prefix("file+json://").unwrap_or(path);
            let path = path.split('#').next().unwrap_or(path);
            let p = Path::new(path);
            let p = if p.is_absolute() { p.to_path_buf() } else { base.join(p) };
            if !p.is_file() {
                return err(format!("input `{}`: `{}` is not a file (looked at {})", b.port, e, p.display()));
            }
            let bytes = std::fs::read(&p).map_err(|x| CaseError(format!("{}: {x}", p.display())))?;
            r.sha256 = Some(sha256_hex(&bytes));
            r.bytes = Some(bytes.len());
            r.storage_uri = Some(e.clone());
            let bundle = crate::io::read(&p).map_err(|x| CaseError(format!("input `{}`: {}: {}", b.port, p.display(), x)))?;
            let mut any = false;
            for (ids, occ) in bundle.keys() {
                if let Some(doc) = bundle.get_occ(&ids, occ) {
                    let got = flatten(&ids, doc, &mut slots);
                    any |= !got.is_empty();
                    r.slots.extend(got);
                }
            }
            if !any {
                //: a raw entry's port: the file may be a bare numeric array
                let text = String::from_utf8_lossy(&bytes);
                if let Some(v) = json::parse(&text).ok().and_then(|n| numbers_of(&n)) {
                    r.slots.push(b.port.clone());
                    slots.push((b.port.clone(), v));
                } else {
                    return err(format!("input `{}`: {} holds no slot the kernel declares", b.port, p.display()));
                }
            }
        }
        if r.slots.is_empty() && r.storage_uri.is_none() {
            r.open = true;
        }
        resolved.push(r);
    }
    Ok((slots, resolved))
}

// --------------------------------------------------------------------------- #
// the outcome, read off the manifest
// --------------------------------------------------------------------------- #

#[derive(Debug, Clone)]
pub struct FieldRef {
    pub ids: String,
    pub path: String,
    pub units: String,
    pub offset: usize,
    pub len: usize,
    pub dims: Vec<usize>,
}

#[derive(Debug, Clone, Default)]
pub struct Outcome {
    pub code: String,
    pub entry: String,
    pub dims: Vec<(String, usize)>,
    pub fields: Vec<FieldRef>,
    pub facts: Vec<(String, String, f64)>,
    pub notes: Vec<String>,
}

pub fn parse_outcome(raw: &RawOutcome) -> Result<Outcome, CaseError> {
    let mut o = Outcome::default();
    for line in raw.manifest.lines() {
        let cells: Vec<&str> = line.split('\t').collect();
        match cells.first().copied() {
            Some("code") => o.code = cells.get(1).unwrap_or(&"").to_string(),
            Some("entry") => o.entry = cells.get(1).unwrap_or(&"").to_string(),
            Some("dim") if cells.len() >= 3 => o.dims.push((cells[1].to_string(), cells[2].parse().unwrap_or(0))),
            Some("field") if cells.len() >= 7 => o.fields.push(FieldRef {
                ids: cells[1].to_string(), path: cells[2].to_string(), units: cells[3].to_string(),
                offset: cells[4].parse().unwrap_or(0), len: cells[5].parse().unwrap_or(0),
                dims: cells[6].split(',').filter_map(|d| d.parse().ok()).collect(),
            }),
            Some("fact") if cells.len() >= 4 => o.facts.push((cells[1].to_string(), cells[2].to_string(),
                                                              cells[3].parse().unwrap_or(f64::NAN))),
            Some("note") => o.notes.push(cells.get(1).unwrap_or(&"").to_string()),
            _ => {}
        }
    }
    for f in &o.fields {
        if f.offset + f.len > raw.data.len() {
            return err(format!("the manifest indexes past the data for `{}/{}`", f.ids, f.path));
        }
    }
    Ok(o)
}

/// The produced datasets: one fyo document per IDS the fields address.
pub fn documents(out: &Outcome, raw: &RawOutcome, record_id: &str) -> Vec<(String, Node)> {
    let mut order: Vec<String> = Vec::new();
    for f in &out.fields {
        let ids = if f.ids.is_empty() { "entry".to_string() } else { f.ids.clone() };
        if !order.contains(&ids) {
            order.push(ids);
        }
    }
    let mut docs = Vec::new();
    for ids in order {
        let mut m = Map::new();
        let mut ctx = Map::new();
        ctx.insert("fyo", FYO.into());
        m.insert("@context", Node::Map(ctx));
        m.insert("@id", format!("{record_id}/{ids}").into());
        m.insert("@type", format!("fyo:{ids}").into());
        let mut doc = Node::Map(m);
        for f in out.fields.iter().filter(|f| (if f.ids.is_empty() { "entry" } else { f.ids.as_str() }) == ids) {
            let data = raw.data[f.offset..f.offset + f.len].to_vec();
            if f.dims.len() == 2 && f.dims[0] > 0 {
                //: the leading dimension indexes the first path segment — one
                //: element per time slice of a time-indexed array of structure
                let (nt, nr) = (f.dims[0], f.dims[1]);
                let mut segs = f.path.splitn(2, '/');
                let head = segs.next().unwrap_or("").to_string();
                let rest = segs.next().unwrap_or("").to_string();
                for i in 0..nt {
                    let row = data[i * nr..(i + 1) * nr].to_vec();
                    let p = if rest.is_empty() { format!("{head}/{i}") } else { format!("{head}/{i}/{rest}") };
                    let _ = doc.set(&p, Node::Array(Array::vec_f64(row)));
                }
            } else {
                let explicit = explicit_path(&f.path);
                let _ = doc.set(&explicit, Node::Array(Array::vec_f64(data)));
            }
        }
        docs.push((ids, doc));
    }
    docs
}

/// A declared path with every array-of-structure segment given its index
/// (0 where the declaration leaves it implicit).
fn explicit_path(path: &str) -> String {
    let segs: Vec<&str> = path.split('/').filter(|s| !s.is_empty()).collect();
    let mut out: Vec<String> = Vec::new();
    let mut i = 0;
    while i < segs.len() {
        out.push(segs[i].to_string());
        if fi::AOS.contains(&segs[i]) {
            let next_is_index = segs.get(i + 1).map(|s| s.parse::<usize>().is_ok()).unwrap_or(false);
            if !next_is_index {
                out.push("0".into());
            }
        }
        i += 1;
    }
    out.join("/")
}

// --------------------------------------------------------------------------- #
// the record
// --------------------------------------------------------------------------- #

/// A produced file, as the record cites it.
#[derive(Debug, Clone)]
pub struct Produced {
    pub port: String,
    pub doc_id: String,
    pub doc_type: String,
    pub storage_uri: String,
    pub format_iri: String,
    pub sha256: String,
    pub bytes: usize,
    pub fields: Vec<String>,
    /// The whole document, when it travels inside the record (the JSON
    /// door) rather than as a file beside it.
    pub inline: Option<Node>,
}

pub struct RecordInputs<'a> {
    pub plan: &'a Plan,
    pub plan_file: Option<&'a str>,
    pub resolved: &'a [Resolved],
    pub kernel: Option<&'a Kernel>,
    pub kernel_sha256: Option<String>,
    pub outcome: Option<&'a Outcome>,
    pub refusal: Option<&'a KernelError>,
    pub produced: &'a [Produced],
    pub started_at: String,
    pub ended_at: String,
    pub record_id: String,
}

fn qv(value: f64, units: &str) -> Node {
    let mut q = Map::new();
    q.insert("type", "spo:QuantityValue".into());
    q.insert("numeric_value", if value.is_finite() { Node::Float(value) } else { Node::Null });
    q.insert("has_unit", units.into());
    Node::Map(q)
}

fn port(name: &str, direction: &str) -> Node {
    let mut p = Map::new();
    p.insert("type", "spo:PortDefinition".into());
    p.insert("port_name", name.into());
    p.insert("port_direction", direction.into());
    Node::Map(p)
}

fn concretization(uri: &str, format: &str, sha: &str, bytes: usize) -> Node {
    let mut c = Map::new();
    c.insert("type", "spo:Concretization".into());
    c.insert("storage_uri", uri.into());
    c.insert("format_iri", format.into());
    c.insert("checksum", format!("sha256:{sha}").into());
    c.insert("byte_size", Node::Int(bytes as i64));
    Node::Map(c)
}

/// The `spo:ComputationRecord` of one run.
pub fn record(r: &RecordInputs) -> Node {
    let mut m = Map::new();
    m.insert("@context", plan_context());
    m.insert("id", r.record_id.clone().into());
    m.insert("type", "spo:ComputationRecord".into());
    if let Some(t) = &r.plan.title {
        m.insert("title", t.clone().into());
    }
    // the plan realized, with the documents that concretize it
    let mut plan = Map::new();
    plan.insert("id", r.plan.id.clone().into());
    plan.insert("type", "fyo:ScenarioSpecification".into());
    let mut concs: Vec<Node> = r.plan.sources.iter().map(|s| {
        concretization(&s.path.to_string_lossy(), LD_JSON, &s.sha256, s.bytes)
    }).collect();
    if let Some(pf) = r.plan_file {
        let mut c = Map::new();
        c.insert("type", "spo:Concretization".into());
        c.insert("storage_uri", pf.into());
        c.insert("format_iri", LD_JSON.into());
        c.insert("comment", "the composed plan as it was run (every override applied)".into());
        concs.push(Node::Map(c));
    }
    plan.insert("concretized_as", Node::List(concs));
    m.insert("realizes", Node::Map(plan));
    // the code, and the library that concretized it
    let mut code = Map::new();
    code.insert("id", r.plan.code.clone().into());
    code.insert("type", "spo:Code".into());
    code.insert("name", "fylite".into());
    if let Some(k) = r.kernel {
        if let Some(v) = k.abi_version {
            code.insert("version", format!("abi {v}").into());
        }
        let mut c = Map::new();
        c.insert("type", "spo:Concretization".into());
        c.insert("storage_uri", k.path.to_string_lossy().to_string().into());
        if let Some(sha) = &r.kernel_sha256 {
            c.insert("checksum", format!("sha256:{sha}").into());
        }
        code.insert("concretized_as", Node::List(vec![Node::Map(c)]));
    }
    if let Some(o) = r.outcome {
        code.insert("comment", format!("kernel entry `{}`", o.entry).into());
    }
    m.insert("executed_code", Node::Map(code));
    m.insert("run_state", (if r.outcome.is_some() { "succeeded" } else { "rejected" }).into());
    m.insert("started_at", r.started_at.clone().into());
    m.insert("ended_at", r.ended_at.clone().into());
    // the settings as run
    let params: Vec<Node> = r.plan.settings.iter().map(|s| {
        let mut p = Map::new();
        p.insert("type", "spo:ParameterSetting".into());
        p.insert("sets_parameter", s.iri.clone().into());
        p.insert("literal_value", s.value.clone());
        if s.from.is_none() {
            p.insert("comment", "command-line override".into());
        }
        Node::Map(p)
    }).collect();
    m.insert("parameters", Node::List(params));
    // the bindings: inputs as resolved, outputs as produced, facts as values
    let mut bindings: Vec<Node> = Vec::new();
    for x in r.resolved {
        let mut b = Map::new();
        b.insert("type", "spo:PortBinding".into());
        b.insert("binds_port", port(&x.port, "input"));
        if let (Some(uri), Some(sha), Some(bytes)) = (&x.storage_uri, &x.sha256, x.bytes) {
            let fmt = if uri.ends_with(".jsonld") || uri.ends_with(".json") { LD_JSON } else { "[TBD]" };
            b.insert("bound_concretization", concretization(uri, fmt, sha, bytes));
        }
        if !x.slots.is_empty() {
            b.insert("comment", Node::List(x.slots.iter().map(|s| format!("slot {s}").into()).collect()));
        }
        if x.open {
            b.insert("comment", "OPEN: nothing was bound to this port".into());
        }
        if let Some(u) = &x.unresolved {
            b.insert("comment", format!("not handed to the kernel: {u}").into());
        }
        bindings.push(Node::Map(b));
    }
    for p in r.produced {
        let mut b = Map::new();
        b.insert("type", "spo:PortBinding".into());
        b.insert("binds_port", port(&p.port, "output"));
        if let Some(doc) = &p.inline {
            //: the dataset itself, inside the record: its own `@context` is
            //: dropped (the record's covers `fyo:`) and its fields are listed
            let mut d = doc.clone();
            if let Some(m) = d.as_map_mut() {
                m.remove("@context");
                if let Some(id) = m.remove("@id") { m.insert("id", id); }
                if let Some(t) = m.remove("@type") { m.insert("type", t); }
                m.insert("comment", Node::List(p.fields.iter().map(|f| f.clone().into()).collect()));
            }
            b.insert("bound_to", d);
        } else {
            let mut d = Map::new();
            d.insert("id", p.doc_id.clone().into());
            d.insert("type", p.doc_type.clone().into());
            d.insert("comment", Node::List(p.fields.iter().map(|f| f.clone().into()).collect()));
            b.insert("bound_to", Node::Map(d));
            b.insert("bound_concretization", concretization(&p.storage_uri, &p.format_iri, &p.sha256, p.bytes));
        }
        bindings.push(Node::Map(b));
    }
    if let Some(o) = r.outcome {
        for (k, n) in &o.dims {
            let mut b = Map::new();
            b.insert("type", "spo:PortBinding".into());
            b.insert("binds_port", port(k, "output"));
            b.insert("bound_to", qv(*n as f64, "1"));
            bindings.push(Node::Map(b));
        }
        for (k, u, v) in &o.facts {
            let mut b = Map::new();
            b.insert("type", "spo:PortBinding".into());
            b.insert("binds_port", port(k, "output"));
            b.insert("bound_to", qv(*v, u));
            bindings.push(Node::Map(b));
        }
    }
    m.insert("inputs", Node::List(bindings));
    let mut comments: Vec<Node> = Vec::new();
    if let Some(o) = r.outcome {
        for n in &o.notes {
            comments.push(n.clone().into());
        }
    }
    if let Some(e) = r.refusal {
        comments.push(format!("refused: {e}").into());
    }
    if !comments.is_empty() {
        m.insert("comment", Node::List(comments));
    }
    if !r.plan.caveats.is_empty() {
        m.insert("caveat", Node::List(r.plan.caveats.iter().map(|c| c.clone().into()).collect()));
    }
    Node::Map(m)
}

// --------------------------------------------------------------------------- #
// the JSON door: one plan text in, one record text out
// --------------------------------------------------------------------------- #

/// What the JSON door hands back.
#[derive(Debug, Clone)]
pub struct JsonRun {
    /// The `spo:ComputationRecord`, datasets inline, as pretty JSON-LD.
    pub record_json: String,
    /// True when the kernel refused: the record says `rejected` and why.
    pub refused: bool,
}

/// Why the JSON door could not even produce a record.
#[derive(Debug, Clone)]
pub struct JsonError {
    /// -2 the plan does not parse / compose · -3 an input could not be
    /// resolved · -4 the kernel could not be loaded · -5 a setting is not a scalar
    pub code: i32,
    pub message: String,
}

/// One plan text (a `fyo:ScenarioSpecification`, or a JSON array of them
/// composed in order) → one record text.  File endpoints in the plan
/// resolve against `base` (the working directory when `None`).
pub fn run_json(plan_text: &str, base: Option<&Path>, kernel_path: Option<&Path>) -> Result<JsonRun, JsonError> {
    let fail = |code: i32, m: String| JsonError { code, message: m };
    let node = json::parse(plan_text).map_err(|e| fail(-2, format!("the plan does not parse: {e:?}")))?;
    let docs: Vec<Node> = match node {
        Node::List(l) => l,
        other => vec![other],
    };
    let mut sources = Vec::new();
    for (i, d) in docs.into_iter().enumerate() {
        let text = json::to_string(&d, false);
        let id = d.as_map().and_then(|m| get(m, &["id", "@id"])).and_then(Node::as_str).map(str::to_string);
        sources.push((Source { path: PathBuf::from(format!("(request)[{i}]")), id,
                               sha256: sha256_hex(text.as_bytes()), bytes: text.len() }, d));
    }
    let plan = compose(sources).map_err(|e| fail(-2, e.0))?;
    let base_dir = base.map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    let (started_secs, started_at) = now_iso();
    let _ = started_secs;
    let record_id = format!("run/{}-{}", started_at.replace([':', '-'], ""), plan.bar());
    let kernel = Kernel::load(kernel_path).map_err(|e| fail(-4, e.message))?;
    let kernel_sha = std::fs::read(&kernel.path).ok().map(|b| sha256_hex(&b));
    let (slots, resolved) = resolve_inputs(&plan, &base_dir).map_err(|e| fail(-3, e.0))?;
    let (numbers, texts) = plan.kernel_settings().map_err(|e| fail(-5, e.0))?;
    let result = kernel.run_case(&plan.code, &numbers, &texts, &slots);
    let (_e, ended_at) = now_iso();
    let mut produced = Vec::new();
    let outcome = match &result {
        Ok(raw) => {
            let o = parse_outcome(raw).map_err(|e| fail(-5, e.0))?;
            for (ids, doc) in documents(&o, raw, &record_id) {
                let fields: Vec<String> = o.fields.iter()
                    .filter(|f| (if f.ids.is_empty() { "entry" } else { f.ids.as_str() }) == ids)
                    .map(|f| format!("{} [{}] {:?}", f.path, f.units, f.dims)).collect();
                produced.push(Produced { port: ids.clone(), doc_id: format!("{record_id}/{ids}"),
                                         doc_type: format!("fyo:{ids}"), storage_uri: String::new(),
                                         format_iri: String::new(), sha256: String::new(), bytes: 0,
                                         fields, inline: Some(doc) });
            }
            Some(o)
        }
        Err(_) => None,
    };
    let rec = record(&RecordInputs {
        plan: &plan, plan_file: None, resolved: &resolved, kernel: Some(&kernel), kernel_sha256: kernel_sha,
        outcome: outcome.as_ref(), refusal: result.as_ref().err(), produced: &produced,
        started_at, ended_at, record_id,
    });
    Ok(JsonRun { record_json: json::to_string(&rec, true) + "\n", refused: result.is_err() })
}

/// Seconds since the epoch as ISO-8601 UTC (`2026-09-02T12:34:56Z`).
pub fn iso_utc(secs: u64) -> String {
    let days = (secs / 86400) as i64;
    let rem = secs % 86400;
    //: civil-from-days (Howard Hinnant), proleptic Gregorian
    let z = days + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let mo = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if mo <= 2 { y + 1 } else { y };
    format!("{y:04}-{mo:02}-{d:02}T{:02}:{:02}:{:02}Z", rem / 3600, (rem % 3600) / 60, rem % 60)
}

pub fn now_iso() -> (u64, String) {
    let secs = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs()).unwrap_or(0);
    (secs, iso_utc(secs))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn iso_dates_are_civil() {
        assert_eq!(iso_utc(0), "1970-01-01T00:00:00Z");
        assert_eq!(iso_utc(951782400), "2000-02-29T00:00:00Z");
        assert_eq!(iso_utc(1788307200), "2026-09-02T00:00:00Z");
    }

    #[test]
    fn explicit_paths_index_the_declared_aos() {
        assert_eq!(explicit_path("time_slice/profiles_1d/q"), "time_slice/0/profiles_1d/q");
        assert_eq!(explicit_path("source/1/profiles_1d/j_parallel"), "source/1/profiles_1d/j_parallel");
        assert_eq!(explicit_path("time"), "time");
    }

    #[test]
    fn a_corpus_style_plan_composes_and_overrides() {
        let a = json::parse(r#"{"id": "cases/x", "type": "fyo:ScenarioSpecification",
            "prescribes_code": {"id": "code/evolve"},
            "parameters": [{"sets_parameter": "code/evolve#chi0", "literal_value": 0.4},
                           {"sets_parameter": "code/evolve#species", "literal_value": "Ne"}]}"#).unwrap();
        let b = json::parse(r#"{"type": "spo:ComputationPlan",
            "spo:has_parameter_setting": [{"spo:sets_parameter": {"@id": "code/evolve#chi0"}, "spo:literal_value": 0.6}]}"#).unwrap();
        let src = |n: &str| Source { path: PathBuf::from(n), id: None, sha256: String::new(), bytes: 0 };
        let mut plan = compose(vec![(src("a"), a), (src("b"), b)]).unwrap();
        assert_eq!(plan.id, "plan");
        assert_eq!(plan.bar(), "evolve");
        let chi0 = plan.settings.iter().find(|s| s.name == "chi0").unwrap();
        assert_eq!(chi0.value, Node::Float(0.6));
        assert_eq!(chi0.from, Some(1));
        plan.set_override("nsteps=12").unwrap();
        let (numbers, texts) = plan.kernel_settings().unwrap();
        assert!(numbers.iter().any(|(k, v)| k == "nsteps" && *v == 12.0));
        assert!(texts.iter().any(|(k, v)| k == "species" && v == "Ne"));
    }
}
