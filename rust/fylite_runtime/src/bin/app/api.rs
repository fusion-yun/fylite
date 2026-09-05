//! `fylite` 的只读 mdsip 请求面 —— 让 `pages/data.html` 与反演页的
//! 「直接从 MDSplus 读」在**单文件可执行体里**也能用。
//!
//! ## 为什么在这里
//!
//! FYL-DESIGN-06 §1 早就结论过：浏览器打不开裸 TCP，wasm 也不改变这件事，
//! 所以**浏览器这条路总带一个服务端组件**，剩下的选择只是它暴露什么。
//! 站点那侧的组件是 `app/server/gateway.mjs`（Node）。桌面查看器把整个
//! `app/` 编了进去，包括 `pages/data.html`——**页面在，请求面不在**，于是那一页
//! 在可执行体里是死的：`/api/health` 404，面板自我禁用。这个模块补上那一半。
//!
//! ## 它暴露什么，以及不暴露什么
//!
//! 与 Node 网关**同一组端点、同一套 JSON 形状**，因为页面是同一份：
//! `/api/health` `/api/shot` `/api/tree` `/api/node` `/api/signal`
//! `/api/measurements`。★没有取表达式的端点，因为
//! [`fylite_runtime::mdsip::Client`] 没有取表达式的方法——每个 TDI 串都在内核里由
//! 校验过的节点路径与整数拼出（FYL-DESIGN-06 §5）。
//!
//! ★★**守卫在两侧各做一遍**，与网关同一形状：这里先查树名/节点路径/整数，
//! 客户端再查一遍。两遍查同一条规则是有意的。
//!
//! ★**只在给了 `--mdsip` 时才活**。没给的时候 `/api/health` 照答，
//! 只是 `ok:false` 且带一句为什么——页面据此把面板画成禁用并说明原因，
//! 这比 404（面板消失）教给读者的多。

use fylite_runtime::mdsip::{self, tcp, Client, MdsipError};

/// EFIT 的测量子树与结果子树前缀 —— 与 `gateway.mjs` 逐字相同。
const M: &str = "\\EFIT_EAST::TOP.MEASUREMENTS:";
const G: &str = "\\EFIT_EAST::TOP.RESULTS.GEQDSK:";
/// 装置文档里的探针闸门（`east_device.yaml` `operational.probe_gate`），
/// 原样转述给页面：判据在页面里，出处在这里。
const PROBE_GATE_MIN: f64 = 0.02;
const PROBE_GATE_MAX: f64 = 1.0;
/// 一次答复最多回多少个采样点——与网关的 `maxPoints` 同值。
const MAX_POINTS: i64 = 20_000;

pub struct Cfg {
    /// `HOST:PORT`；`None` 表示没接 mdsip（本程序仍然是个静态查看器）。
    pub server: Option<String>,
    pub user: String,
}

/// 处理一个 `/api/...` 请求；返回 (状态码, JSON 正文)。
pub fn handle(target: &str, cfg: &Cfg) -> (u16, String) {
    let (path, query) = match target.split_once('?') {
        Some((p, q)) => (p, q),
        None => (target, ""),
    };
    let q = Query::parse(query);
    let out = match path {
        "/api/health" => return (200, health(cfg)),
        //: ★★装置信息**不经 mdsip**，所以它在这一支的最前面、与 `health` 同类：
        //: 没接服务器的查看器照样答得出。见 `facts()` 抬头。
        "/api/facts" => facts(&q),
        "/api/shot" => shot(cfg, &q),
        "/api/tree" => tree(cfg, &q),
        "/api/node" => node(cfg, &q),
        "/api/signal" => signal(cfg, &q),
        "/api/measurements" => measurements(cfg, &q),
        _ => Err(Fail::Bad(format!("no endpoint {path}"))),
    };
    match out {
        Ok(body) => (200, body),
        Err(Fail::Bad(m)) => (400, format!("{{\"error\":{},\"kind\":\"BadRequest\"}}", jstr(&m))),
        Err(Fail::Mds(e)) => (502, format!("{{\"error\":{},\"kind\":\"server\"}}", jstr(&e.to_string()))),
    }
}

/// `/api/facts?domain=device[&id=east]` —— 装置信息，走**本进程自己的那一份**。
///
/// ★★2026-09-05 用户裁定「页面也走中间层 wasm，撤掉 `facts.jsonld`」之后，装置信息
/// 只有一个制品（`facts.rs`），由 `.so` 与 `.wasm` 各编进去。对**静态站点**而言那份
/// wasm 是页面唯一的读法；但对**这个可执行文件**而言它是多余的第二份：本程序本身
/// 就是原生的中间层，那张表已经在它的地址空间里，再内嵌一份同层的 wasm 等于把刚
/// 消掉的重复换个层次又做一遍（实测 +2.25 MB，其中 432 KB 是装置信息、1.8 MB 是
/// 同一层代码的第二份）。所以内嵌页面改问这条路，可执行文件不再带那份 wasm。
///
/// ★读的是 `facts::find` / `entries`，**不是**只读编进去的那一档：于是
/// `fy app --facts /我的语料` 之后页面看到的与 `fy list devices` 看到的是同一批，
/// 而不是两个答案。这是把「搜索路径」的语义一路带到页面上，不是额外开一个口子。
///
/// 答复：给了 `id` 就是那一份文档本身（原样转发，不重新序列化——重新序列化就是
/// 第二条序列化路径，而两条路径就是两份字节）；没给就是 `{"ids":[…]}`。
fn facts(q: &Query) -> Result<String, Fail> {
    let domain = q.get("domain").unwrap_or("device");
    if domain.is_empty() || !domain.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
        return Err(Fail::Bad(format!("bad domain {domain:?}")));
    }
    match q.get("id") {
        Some(id) if !id.is_empty() => {
            //: ★`catalogue` 与逐台文档走**同一条**路：页面先读目录再逐台读，
            //: 两次问的若是两个口子，某天它们会不一致。
            let hit = fylite_runtime::facts::find(domain, id)
                .ok_or_else(|| Fail::Bad(format!("no {domain}/{id} on the facts path")))?;
            hit.read()
                .ok_or_else(|| Fail::Bad(format!("{domain}/{id}: the document could not be read")))
        }
        _ => {
            let mut ids: Vec<String> =
                fylite_runtime::facts::entries(domain).into_iter().map(|e| e.ident).collect();
            //: ★目录也报出来：页面按目录的次序展示，而次序是目录说的，不是这里排的。
            if fylite_runtime::facts::find(domain, "catalogue").is_some() {
                ids.push("catalogue".into());
            }
            let items: Vec<String> = ids.iter().map(|s| jstr(s)).collect();
            Ok(format!("{{\"ids\":[{}]}}", items.join(",")))
        }
    }
}

// --------------------------------------------------------------------------
// 算力 —— 页面在这个宿主里调内核的那条路
// --------------------------------------------------------------------------

/// 一次调用的请求体上限。
///
/// ★与 [`fylite_runtime::kernel_call::MAX_FRAME`] 同量级但**更大**：那是解出来的
/// 二进制帧，这里是它的 JSON 文本形（一个 f64 写成十来个字符）。两处各自成立，
/// 因为它们量的是两样东西。
pub const MAX_BODY: usize = 256 << 20;

/// `POST /api/kernel` —— 一个内核符号、一批参数，算完把出参送回去。
///
/// ★★2026-09-05 用户裁定：「webui 中 fylite_rs / fylite_kernel_ext wasm 功能由 api
/// 端提供，只静态网页走 wasm」。桌面宿主里的页面因此不再实例化内核 wasm；它把
/// **本来要交给 wasm 的那次调用**原样交到这里，由链进本进程的静态库算。
///
/// ★这里没有任何一处知道某个函数是干什么的——参数怎么读、出参多长，全由内核仓
/// 生成的那张表说了算（`kernel_abi::KINDS`，页面手上是同一次生成的
/// `app/assets/kernel-abi.js`）。所以这条端点不是第二个计算接口，是同一个接口的
/// 另一种到达方式。
///
/// ★没链内核的构建（公开仓单独检出）**照答**，答的是一句说得清的话而不是 404：
/// 页面据此退回 wasm 或者把面板画成禁用，与 `/api/health` 同一条纪律。
pub fn kernel(body: &str) -> (u16, String) {
    #[cfg(kernel_static)]
    {
        use fylite_runtime::kernel_abi;
        use fylite_runtime::kernel_call as kc;
        let kinds_of = |n: &str| -> Option<&'static [&'static str]> {
            kernel_abi::KINDS.iter().find(|(k, _)| *k == n).map(|(_, v)| *v)
        };
        let (name, mut frame) = match kc::parse_request(body, kinds_of) {
            Ok(v) => v,
            Err(e) => return (400, format!("{{\"error\":{}}}", jstr(&e.to_string()))),
        };
        let ret = match kernel_abi::call(&name, &mut frame) {
            Ok(r) => r,
            Err(e) => return (400, format!("{{\"error\":{}}}", jstr(&e.to_string()))),
        };
        let kinds = kinds_of(&name).unwrap_or(&[]);
        (200, kc::render_answer(ret, &frame, kinds))
    }
    #[cfg(not(kernel_static))]
    {
        let _ = body;
        (
            501,
            format!(
                "{{\"error\":{}}}",
                jstr(&fylite_runtime::kernel_call::CallError::NoKernel.to_string())
            ),
        )
    }
}

// --------------------------------------------------------------------------
// 文件 —— 页面把一份文件交给本进程读
// --------------------------------------------------------------------------

/// `POST /api/read?name=<原名>` —— 一份文件的字节进，一份 fyo 文档出。
///
/// ★★2026-09-05 用户裁定：*hdf5 走 fy app 的文件端点，静态站点保留 h5wasm*。
/// 缘由是一件量得出来的事：浏览器读 HDF5 要 h5wasm（NIST 的 Emscripten 包，4.1 MB，
/// 因为 HDF5 那个 C 库以 base64 骑在里面），而**这个进程本来就链着 libhdf5**。桌面版
/// 再背一份 4.1 MB 的第二实现，与装置信息、算力那两次收敛掉的是同一种重复。
///
/// ★读法是中间层自己的（`io::read` 按内容识别格式，`Format::Hdf5` 走
/// `hdf5::read_fyo`）——不是为这条端点另写的读者。于是「桌面版读到的」与
/// `fy data` 读到的、与 `python/tests` 对拍的是同一份实现。
///
/// ★**按名拒绝 IMAS 单文件**，与页面那侧同一句话：IMAS 布局是一个**目录**
/// （`master.h5` + 每个 IDS 一份），单文件里带着 `ids_properties` 而没有 `@type` 的，
/// 半读一份会给出一份看着对、其实转置了的文档（`FYL-DESIGN-14` L-5 / L-6）。
///
/// ★不落盘超过一次：字节写进临时文件（中间层的读者按路径工作），读完就删。
#[cfg(not(target_arch = "wasm32"))]
pub fn read_file(name: &str, shape: &str, body: &[u8]) -> (u16, String) {
    use std::io::Write;
    //: ★原名只用来取扩展名与写进文档的 `source`，**不当路径用**：分隔符与上跳一律
    //: 拒绝，临时文件名由本进程拼。
    if name.contains('/') || name.contains('\\') || name.contains("..") {
        return (400, format!("{{\"error\":{}}}", jstr("bad file name")));
    }
    if body.is_empty() {
        return (400, format!("{{\"error\":{}}}", jstr("empty body")));
    }
    let ext = std::path::Path::new(name)
        .extension()
        .and_then(|e| e.to_str())
        .filter(|e| e.len() <= 8 && e.chars().all(|c| c.is_ascii_alphanumeric()))
        .map(|e| format!(".{e}"))
        .unwrap_or_default();
    let stem = format!("fy-api-{}-{}{}", std::process::id(),
                       std::time::SystemTime::now()
                           .duration_since(std::time::UNIX_EPOCH)
                           .map(|d| d.as_nanos())
                           .unwrap_or(0),
                       ext);
    let path = std::env::temp_dir().join(stem);
    let write = std::fs::File::create(&path).and_then(|mut f| f.write_all(body));
    if let Err(e) = write {
        return (500, format!("{{\"error\":{}}}", jstr(&format!("temp file: {e}"))));
    }
    //: ★★`shape=gfile` 要的是 g-file **自己的**字段（`g.pres` / `g.psirz` / `g.rbbbs`…），
    //: 不是按 DD 键名铸的 fyo 文档——页面那一侧要的就是前者（H-4 落地之后它不再自己解）。
    //: 同一个产出者两条到达方式：wasm 上是 `fylite_runtime_gfile_json`，这里是这一支，
    //: 中间是同一个 `GFile::to_node`。
    if shape == "gfile" {
        let text = std::fs::read_to_string(&path);
        let _ = std::fs::remove_file(&path);
        return match text {
            Ok(t) => match fylite_runtime::geqdsk::parse(&t) {
                Ok(g) => (200, fylite_runtime::json::to_string(&g.to_node(), false)),
                Err(e) => (400, format!("{{\"error\":{}}}", jstr(&e.to_string()))),
            },
            Err(e) => (400, format!("{{\"error\":{}}}", jstr(&e.to_string()))),
        };
    }
    let out = fylite_runtime::io::read(&path);
    let _ = std::fs::remove_file(&path);
    match out {
        Ok(bundle) => {
            let node = bundle.to_node();
            //: 与页面那侧逐字同一句拒绝（见抬头）。
            let imas = node.get("ids_properties").is_some() && node.get("@type").is_none();
            if imas {
                return (400, format!("{{\"error\":{}}}", jstr(
                    "按名拒绝：这看着是 IMAS 布局（结构数组张量化 · 数据轴转置，\
                     FYL-DESIGN-14 L-5 / L-6）——本读者只读本仓写的 fyo 布局，\
                     半读一份会给出一份看着对、其实转置了的文档")));
            }
            (200, fylite_runtime::json::to_string(&node, false))
        }
        Err(e) => (400, format!("{{\"error\":{}}}", jstr(&e.to_string()))),
    }
}

/// `/api/health` 里那一格：算力在不在本进程里，以及它是哪一版 ABI。
fn kernel_face() -> String {
    #[cfg(kernel_static)]
    {
        use fylite_runtime::kernel_abi;
        let mut f = fylite_runtime::kernel_call::Frame::default();
        let abi = kernel_abi::call("fylite_rs_abi_version", &mut f)
            .map(|r| r.as_f64())
            .unwrap_or(0.0);
        //: ★★身份也报：页面的续算闸按内核散列判「这份状态是不是当前这个内核写的」，
        //: 而走这条路时没有一份 `.wasm` 可散列。这里给的是**链进来的那份归档**的
        //: 散列（构建期 baked，见 `build.rs`）——正是跑起来的那些字节。
        let sha = env!("FYLITE_KERNEL_SHA256");
        let ver = env!("FYLITE_KERNEL_VERSION");
        format!(
            "{{\"linked\":true,\"abi\":{},\"symbols\":{},\"sha256\":{},\"version\":{}}}",
            abi as u64,
            kernel_abi::BRIDGED.len(),
            if sha.is_empty() { String::from("null") } else { jstr(sha) },
            if ver.is_empty() { String::from("null") } else { jstr(ver) }
        )
    }
    #[cfg(not(kernel_static))]
    {
        String::from("{\"linked\":false,\"abi\":null,\"symbols\":0,\"sha256\":null,\"version\":null}")
    }
}

enum Fail {
    Bad(String),
    Mds(MdsipError),
}

impl From<MdsipError> for Fail {
    fn from(e: MdsipError) -> Self {
        Fail::Mds(e)
    }
}

// --------------------------------------------------------------------------
// 查询串
// --------------------------------------------------------------------------

struct Query(Vec<(String, String)>);

impl Query {
    fn parse(s: &str) -> Self {
        Query(
            s.split('&')
                .filter(|p| !p.is_empty())
                .map(|p| match p.split_once('=') {
                    Some((k, v)) => (unesc(k), unesc(v)),
                    None => (unesc(p), String::new()),
                })
                .collect(),
        )
    }

    fn get(&self, k: &str) -> Option<&str> {
        self.0.iter().find(|(a, _)| a == k).map(|(_, v)| v.as_str())
    }

    fn tree(&self, default: &str) -> Result<String, Fail> {
        let t = self.get("tree").unwrap_or(default);
        if !mdsip::is_tree_name(t) {
            return Err(Fail::Bad(format!("tree name {t:?} is not a plain name")));
        }
        Ok(t.to_string())
    }

    fn shot(&self) -> Result<i64, Fail> {
        let s = self.get("shot").unwrap_or("");
        s.parse::<i64>()
            .map_err(|_| Fail::Bad(format!("shot {s:?} is not an integer")))
    }

    fn node(&self) -> Result<String, Fail> {
        let n = self.get("node").unwrap_or("");
        if !mdsip::is_node_path(n) {
            return Err(Fail::Bad(format!("node path {n:?} is not a node path")));
        }
        Ok(n.to_string())
    }

    fn int(&self, k: &str) -> Option<i64> {
        self.get(k).and_then(|v| v.parse::<i64>().ok())
    }
}

/// `%XX` 与 `+` 的还原。★不用第三方库：查询串里出现的只有路径字符与空格。
fn unesc(s: &str) -> String {
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        match b[i] {
            b'+' => {
                out.push(b' ');
                i += 1;
            }
            b'%' if i + 2 < b.len() => {
                let hex = std::str::from_utf8(&b[i + 1..i + 3]).unwrap_or("");
                match u8::from_str_radix(hex, 16) {
                    Ok(v) => {
                        out.push(v);
                        i += 3;
                    }
                    Err(_) => {
                        out.push(b[i]);
                        i += 1;
                    }
                }
            }
            c => {
                out.push(c);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

// --------------------------------------------------------------------------
// JSON —— 手写，因为这个 crate 只有一个可选依赖，为六个端点引一个序列化库
// 不划算；而形状是固定的，不是任意对象。
// --------------------------------------------------------------------------

fn jstr(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// 一个数：非有限值写成 `null`。★JSON 没有 NaN，写出来的 `NaN` 会让页面的
/// `JSON.parse` 整个失败——一个坏样本不该带走整条曲线。
fn jnum(v: f64) -> String {
    if v.is_finite() {
        let s = format!("{v}");
        s
    } else {
        String::from("null")
    }
}

fn jarr(v: &[f64]) -> String {
    let mut out = String::from("[");
    for (i, x) in v.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&jnum(*x));
    }
    out.push(']');
    out
}

// --------------------------------------------------------------------------
// 端点
// --------------------------------------------------------------------------

fn health(cfg: &Cfg) -> String {
    //: ★★★`locked` 为假，而这不是放松了什么：唯一的调用者就是启动这个进程的
    //: 人——他本可以直接打 `--mdsip`。这个查看器**只绑回环，且不可配置**
    //: （`main.rs` 的边界之一）。
    //:
    //: ★网关那边从前还有 `--host` / `--allow CIDR` 和一个 `allow` 字段（把绑到
    //: 站点网段时的放行名单报出来）；2026-09-01 那套连同字段一并移除，两个宿主
    //: 于是在「只绑回环」这条上也一致了。`locked` 这个键留着，因为页面靠它决定
    //: 要不要把服务器格置灰。
    //:
    //: ★用户名仍然不从页面取：mdsip 不做认证，页面自报的用户名什么也证明不了。
    let servers = match &cfg.server {
        Some(s) => format!("[{}]", jstr(s)),
        None => String::from("[]"),
    };
    format!(
        "{{\"ok\":true,\"mdsip\":{},\"user\":{},\"sessions\":0,\"maxPoints\":{},\
         \"trees\":[\"efit_east\",\"east\",\"pcs_east\",\"analysis\",\"efitrt_east\"],\
         \"servers\":{},\"locked\":false,\"kernel\":{},\"file\":{}{}}}",
        match &cfg.server {
            Some(s) => jstr(s),
            None => String::from("null"),
        },
        jstr(&cfg.user),
        MAX_POINTS,
        servers,
        //: ★★**算力在不在本进程里**（2026-09-05 用户裁定）。页面读这一格决定走哪条
        //: 路：`linked` 为真就把内核调用交给 `/api/kernel`，为假（或整个 `/api/health`
        //: 不在，比如静态站点）就实例化 wasm 自己算。探的是**这条路答不答**，
        //: 不是主机名——与 `factsdb.js` 探 `/api/facts` 同一条纪律。
        //: ★ABI 号一并报出：页面手上的那份契约（`assets/version.js` 的 `FyVersion.abi`）
        //: 与算力这一侧必须同源，不等就该当场说，而不是让第一个改过签名的函数
        //: 去表现成一个奇怪的数。
        kernel_face(),
        //: ★★**本进程能不能替页面读文件**（2026-09-05 用户裁定：hdf5 走 fy app 的
        //: 文件端点，静态站点保留 h5wasm）。页面读这一格决定走哪条路：为真就把文件
        //: 字节 POST 给 `/api/read`，为假（或整个 `/api/health` 不在，比如静态站点）
        //: 就惰性载入 h5wasm 那 4.1 MB。判据是**这一次构建带不带 hdf5 那一面**，
        //: 不是「有没有这条路由」——路由在而库不在，答的会是一句读不动。
        cfg!(all(feature = "hdf5", not(target_arch = "wasm32"))),
        //: 没给 `--mdsip` 时照样答，并说清这一格要自己填——一个消失的控件什么
        //: 也没教给读者，而「往哪里填」正是读者要知道的。
        if cfg.server.is_none() {
            format!(",\"reason\":{}", jstr(
                "这个查看器启动时没给 --mdsip —— 在上面的服务器格里填 HOST:PORT，\
                 或者重起它并加上 --mdsip"))
        } else {
            String::new()
        }
    )
}

/// 这次请求要连的服务器：页面给的（若给了）优先，否则启动时那个。
///
/// ★★守卫在这里做一遍，`fylite_runtime::mdsip::tcp::connect` 再做一遍——两遍查同一条
/// 规则是有意的（FYL-DESIGN-06 §5）。这里查的是**形状**：主机名/点分地址加一个
/// 端口，别的一律拒，且**在开 socket 之前**。
fn server_of(q: &Query, cfg: &Cfg) -> Result<String, Fail> {
    if let Some(v) = q.get("server") {
        let v = v.trim();
        if !v.is_empty() {
            if !is_server_string(v) {
                return Err(Fail::Bad(format!("server {v:?} is not HOST or HOST:PORT")));
            }
            return Ok(v.to_string());
        }
    }
    cfg.server.as_deref().map(str::to_string).ok_or_else(|| {
        Fail::Bad(String::from(
            "no mdsip server — type one in the server box, or start with --mdsip HOST:PORT",
        ))
    })
}

/// `HOST` 或 `HOST:PORT`：字母、数字、`.` `-` `_`，端口是 1..65535。
fn is_server_string(s: &str) -> bool {
    if s.len() > 255 {
        return false;
    }
    let (host, port) = match s.rsplit_once(':') {
        Some((h, p)) => (h, Some(p)),
        None => (s, None),
    };
    if host.is_empty()
        || !host
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'.' || b == b'-' || b == b'_')
    {
        return false;
    }
    match port {
        None => true,
        Some(p) => matches!(p.parse::<u32>(), Ok(n) if (1..=65535).contains(&n)),
    }
}

fn open(cfg: &Cfg, q: &Query, tree: &str, shot: i64)
        -> Result<(Client<tcp::TcpTransport>, String), Fail> {
    let server = server_of(q, cfg)?;
    let mut c = tcp::connect(&server, &cfg.user)?;
    if !tree.is_empty() {
        c.open_tree(tree, shot)?;
    }
    Ok((c, server))
}

fn shot(cfg: &Cfg, q: &Query) -> Result<String, Fail> {
    let tree = q.tree("")?;
    if tree.is_empty() {
        return Err(Fail::Bad(String::from("tree is required")));
    }
    let (mut c, server) = open(cfg, q, "", 0)?;
    let n = c.current_shot(&tree)?;
    Ok(format!(
        "{{\"server\":{},\"tree\":{},\"shot\":{},\"expr\":{}}}",
        jstr(&server),
        jstr(&tree),
        n,
        jstr(&format!("current_shot(\"{tree}\")"))
    ))
}

fn tree(cfg: &Cfg, q: &Query) -> Result<String, Fail> {
    let tree = q.tree("")?;
    let shot = q.shot()?;
    let at = q.get("path").unwrap_or("\\TOP").to_string();
    if !mdsip::is_node_path(&at) {
        return Err(Fail::Bad(format!("node path {at:?} is not a node path")));
    }
    let (mut c, server) = open(cfg, q, &tree, shot)?;
    let mut rows = Vec::new();
    for kind in ["children", "members"] {
        let names = c.list_nodes(&at, kind, "name")?;
        if names.is_empty() {
            continue;
        }
        let usages = c.list_nodes(&at, kind, "usage")?;
        let lengths = c.list_nodes(&at, kind, "length")?;
        for (i, n) in names.iter().enumerate() {
            //: 路径是**拼出来的**，不是问来的：`FULLPATH` 在一层两千多个
            //: 节点上要再花十秒，而它确认的规则是 MDSplus 自己的且是全称的
            //: ——子树用 `.` 挂在父节点下，成员用 `:`。
            let sep = if kind == "members" { ':' } else { '.' };
            rows.push(format!(
                "{{\"kind\":{},\"path\":{},\"name\":{},\"usage\":{},\"length\":{}}}",
                jstr(kind),
                jstr(&format!("{at}{sep}{n}")),
                jstr(n),
                jstr(usages.get(i).map(|s| s.as_str()).unwrap_or("")),
                lengths
                    .get(i)
                    .and_then(|s| s.parse::<i64>().ok())
                    .unwrap_or(0)
            ));
        }
    }
    Ok(format!(
        "{{\"server\":{},\"tree\":{},\"shot\":{},\"path\":{},\"nodes\":[{}]}}",
        jstr(&server),
        jstr(&tree),
        shot,
        jstr(&at),
        rows.join(",")
    ))
}

fn node(cfg: &Cfg, q: &Query) -> Result<String, Fail> {
    let tree = q.tree("")?;
    let shot = q.shot()?;
    let node = q.node()?;
    let (mut c, server) = open(cfg, q, &tree, shot)?;
    let size = c.size(&node).unwrap_or(0);
    let inserted = c.inserted_ms(&node).unwrap_or(None);
    let units = c.units_of(&node).unwrap_or_default();
    let has_time = c.dim_slice(&node, 0, 0, 1).map(|a| !a.data.is_empty()).unwrap_or(false);
    Ok(format!(
        "{{\"server\":{},\"tree\":{},\"shot\":{},\"node\":{},\"size\":{},\"units\":{},\
         \"hasTime\":{},\"inserted\":{},\"insertedIso\":{}}}",
        jstr(&server),
        jstr(&tree),
        shot,
        jstr(&node),
        size,
        jstr(&units),
        has_time,
        match inserted {
            Some(v) => v.to_string(),
            None => String::from("null"),
        },
        match inserted {
            Some(v) => jstr(&iso8601(v)),
            None => String::from("null"),
        }
    ))
}

fn signal(cfg: &Cfg, q: &Query) -> Result<String, Fail> {
    let tree = q.tree("")?;
    let shot = q.shot()?;
    let node = q.node()?;
    let want = q.int("points").unwrap_or(2_000).clamp(1, MAX_POINTS);
    let (mut c, server) = open(cfg, q, &tree, shot)?;
    let n = c.size(&node)?;
    if n <= 0 {
        return Err(Fail::Bad(format!("{node} holds no data on {tree} shot {shot}")));
    }
    //: ★窗口被**夹**而不是被拒：页面用同一个窗口问几条采样率不同、长度也
    //: 不同的信号，一条比别人短是这一炮的事实，不是一个坏请求。
    let first = q.int("first").unwrap_or(0).clamp(0, n - 1);
    let last = q.int("last").unwrap_or(n - 1).clamp(first, n - 1);
    let stride = (((last - first + 1) as f64) / (want as f64)).ceil() as i64;
    let stride = stride.max(1);
    let y = c.slice(&node, first, last, stride)?;
    let data = y.data.to_f64().unwrap_or_default();
    let time = c
        .dim_slice(&node, first, last, stride)
        .ok()
        .and_then(|d| d.data.to_f64())
        .filter(|t| t.len() == data.len());
    let units = c.units_of(&node).unwrap_or_default();
    let t_units = if time.is_some() {
        c.dim_units_of(&node).unwrap_or_default()
    } else {
        String::new()
    };
    Ok(format!(
        "{{\"server\":{},\"tree\":{},\"shot\":{},\"node\":{},\"units\":{},\"timeUnits\":{},\
         \"n\":{},\"first\":{},\"last\":{},\"stride\":{},\"returned\":{},\
         \"decimated\":{},\"windowed\":{},\"time\":{},\"data\":{}}}",
        jstr(&server),
        jstr(&tree),
        shot,
        jstr(&node),
        jstr(&units),
        jstr(if t_units.is_empty() && time.is_some() { "s" } else { &t_units }),
        n,
        first,
        last,
        stride,
        data.len(),
        stride > 1,
        first > 0 || last < n - 1,
        match &time {
            Some(t) => jarr(t),
            None => String::from("null"),
        },
        jarr(&data)
    ))
}

/// EFIT 自己的输入记录，取**离所要时刻最近的存储切片**。
///
/// ★★它不是本仓随 EAST deck 附的那份 est2 归算，也不在恰好那一瞬：
/// #137985 上 deck 是 est2 的 4.000 s，这里给 EFIT 的 4.041 s，两者在环上差
/// 2.3 %、在一路线圈上差 5.4 %——那是斜坡上的 41 ms，是两个来源的事实，
/// 不是任一方的错误。答复把实际拿到的切片一并报出来。
fn measurements(cfg: &Cfg, q: &Query) -> Result<String, Fail> {
    let tree = q.tree("efit_east")?;
    let shot = q.shot()?;
    let raw = q.get("time").unwrap_or("");
    let want: f64 = raw
        .parse()
        .map_err(|_| Fail::Bad(format!("time {raw:?} is not a number of seconds")))?;
    if !want.is_finite() {
        return Err(Fail::Bad(format!("time {raw:?} is not a number of seconds")));
    }
    let (mut c, server) = open(cfg, q, &tree, shot)?;

    let gtime = c
        .get(&format!("{G}GTIME"))?
        .data
        .to_f64()
        .unwrap_or_default();
    if gtime.is_empty() {
        return Err(Fail::Bad(format!("{tree} #{shot} has no GTIME — nothing was stored")));
    }
    let mut at = 0usize;
    for i in 1..gtime.len() {
        if (gtime[i] - want).abs() < (gtime[at] - want).abs() {
            at = i;
        }
    }

    //: ★★`dims[0]` 是**变化最快**的轴，也就是通道数；载荷按 (切片, 通道)
    //: 连续排列。反过来读会拿到某一路通道的历史，而且不报任何错。
    let mut row = |node: &str| -> Result<(Vec<f64>, usize), Fail> {
        let a = c.get(node)?;
        if a.dims.len() != 2 {
            return Err(Fail::Bad(format!("{node} is not (channels, time)")));
        }
        let w = a.dims[0];
        let d = a.data.to_f64().unwrap_or_default();
        let lo = at * w;
        let hi = (lo + w).min(d.len());
        if lo >= d.len() {
            return Err(Fail::Bad(format!("{node} has no slice {at}")));
        }
        Ok((d[lo..hi].to_vec(), w))
    };
    let (loops, n_loops) = row(&format!("{M}SILOPT"))?;
    let (probes, n_probes) = row(&format!("{M}EXPMPI"))?;
    let (coils, n_coils) = row(&format!("{M}FCCURT"))?;
    let plasma = c.get(&format!("{M}PLASMA"))?.data.to_f64().unwrap_or_default();

    //: ★★2026-09-01 改：真空场读的是**标签** `\\BCENTR`，不是 `{G}BCENTR`。
    //: 那条全路径在试过的每一炮上都是 size 0 / `%TREE-E-NODATA`（#100000
    //: #137984 #137985 #140000 #150000 #165704），标签则给 112 点、单位 `T`。
    //: 这里从前的注释写着「BCENTR 在有些炮上是 NODATA（#137985 就是）」——
    //: 那是**把自己的路径写错记成了机器没有这个量**。
    //:
    //: ★取不到时仍然给 null，不给替代值：真空场是页面自己的 deck 已经有的数，
    //: 在这里编一个就是把机器常数塞进一份测量记录。
    let bcentr = c
        .get("\\BCENTR")
        .ok()
        .and_then(|a| a.data.to_f64())
        .and_then(|v| v.get(at).copied())
        .filter(|v| v.is_finite());

    //: 第 13 路 FCCURT 是器壁内/IC 回路，**丢掉**，与 `io/mds.py` 同一处理；
    //: 前 12 路是 PF 线圈的安匝。
    let aturns: Vec<f64> = coils.iter().take(12).copied().collect();
    Ok(format!(
        "{{\"server\":{},\"tree\":{},\"shot\":{},\"time_requested\":{},\"time_s\":{},\
         \"slice_index\":{},\"slices\":{},\"times\":{},\"loops\":{},\"probes\":{},\
         \"aturns\":{},\"ip\":{},\"bcentr\":{},\
         \"counts\":{{\"loops\":{},\"probes\":{},\"coils\":{}}},\
         \"probe_gate\":{{\"min_tesla\":{},\"max_tesla\":{},\"source\":{}}},\
         \"provenance\":{{\"nodes\":{{\"time\":{},\"loops\":{},\"probes\":{},\"coils\":{},\
         \"ip\":{},\"bcentr\":{}}},\"kind\":{}}}}}",
        jstr(&server),
        jstr(&tree),
        shot,
        jnum(want),
        jnum(gtime[at]),
        at,
        gtime.len(),
        jarr(&gtime),
        jarr(&loops),
        jarr(&probes),
        jarr(&aturns),
        jnum(plasma.get(at).copied().unwrap_or(f64::NAN)),
        match bcentr {
            Some(v) => jnum(v),
            None => String::from("null"),
        },
        n_loops,
        n_probes,
        n_coils,
        PROBE_GATE_MIN,
        PROBE_GATE_MAX,
        jstr("machine_desc/east/east_device.yaml operational.probe_gate"),
        jstr(&format!("{G}GTIME")),
        jstr(&format!("{M}SILOPT")),
        jstr(&format!("{M}EXPMPI")),
        jstr(&format!("{M}FCCURT")),
        jstr(&format!("{M}PLASMA")),
        jstr("\\BCENTR"),
        jstr("EFIT's own input record, at the stored slice nearest the requested \
              time — not the est2 reduction of the raw trees")
    ))
}

/// Unix 毫秒 -> ISO-8601（UTC）。
///
/// ★手写而不是拉一个日期库：这里只有一处要它，输入是一个已经算好的毫秒数，
/// 而闰秒不在 Unix 时间里——所需的只是民用历的除法。公式是 Howard Hinnant 的
/// `civil_from_days`，与 `Date(ms).toISOString()` 对同一个数给同一串。
fn iso8601(ms: i64) -> String {
    let (days, rem) = (ms.div_euclid(86_400_000), ms.rem_euclid(86_400_000));
    let (h, m, s, milli) = (rem / 3_600_000, rem / 60_000 % 60, rem / 1000 % 60, rem % 1000);
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let mth = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if mth <= 2 { y + 1 } else { y };
    format!("{y:04}-{mth:02}-{d:02}T{h:02}:{m:02}:{s:02}.{milli:03}Z")
}


#[cfg(test)]
mod tests {
    use super::*;

    fn no_server() -> Cfg {
        Cfg { server: None, user: String::from("tester") }
    }

    #[test]
    fn facts_answers_without_a_server_and_names_what_it_lacks() {
        //: ★★装置信息**不经 mdsip**：一台没接服务器的查看器照样答得出这条路。
        //: 这一条钉的正是那件事——它与 `/api/health` 同类，而不是与取数那几条同类。
        let (code, body) = handle("/api/facts?domain=device", &no_server());
        assert_eq!(code, 200, "{body}");
        assert!(body.starts_with("{\"ids\":["), "{body}");

        //: ★「这一版不带这台」是 400 加一句点名，不是 404、也不是一个空文档：
        //: 页面拿这三者说三句不同的话（这个宿主没有这条路 / 这一版不带它 / 它坏了）。
        let (code, body) = handle("/api/facts?domain=device&id=nosuch-machine", &no_server());
        assert_eq!(code, 400, "{body}");
        assert!(body.contains("nosuch-machine"), "{body}");

        //: 域名只收 ASCII 字母数字与下划线——它要拼进搜索路径，不该是一段任意文本。
        let (code, _) = handle("/api/facts?domain=../etc", &no_server());
        assert_eq!(code, 400);
    }

    #[test]
    fn health_answers_when_no_mdsip_is_attached() {
        //: ★★答，而不是 404：404 会让面板整个消失，而一个消失的控件什么也没
        //: 教给读者。这正是接上请求面之前 `pages/data.html` 在可执行体里的样子。
        //:
        //: ★★★而它答的是 `ok: true, locked: false`——**没给 `--mdsip` 也照样
        //: 能用**，因为服务器那一格现在是可写的（2026-09-01）：这个查看器只绑
        //: 回环且不可配置，能敲那个框的人就是启动它的人。所以「没配」不是
        //: 「不能用」，是「还没填」，`reason` 说的正是这件事。
        let (code, body) = handle("/api/health", &no_server());
        assert_eq!(code, 200);
        assert!(body.contains("\"ok\":true"), "{body}");
        assert!(body.contains("\"locked\":false"), "{body}");
        assert!(body.contains("--mdsip"), "没有说清怎么填：{body}");
    }

    #[test]
    fn the_server_box_is_checked_before_a_socket_is_opened() {
        //: ★★守卫在这里做一遍，客户端再做一遍——两遍查同一条规则是有意的。
        //: 这里查的是**形状**，而且在开 socket 之前：一个会被拒的地址不该先
        //: 变成一次连接尝试。
        for ok in ["127.0.0.1:8000", "mds.example.org", "a-b_c.d:65535"] {
            assert!(is_server_string(ok), "应当接受 {ok}");
        }
        for bad in ["", "host:0", "host:70000", "host:port", "a b:8000",
                    "host;rm -rf /", "10.0.0.1:8000/x"] {
            assert!(!is_server_string(bad), "应当拒绝 {bad:?}");
        }
        let cfg = Cfg { server: None, user: String::from("t") };
        let (code, body) = handle("/api/measurements?shot=1&time=0&server=host%3Bwhoami", &cfg);
        assert_eq!(code, 400, "{body}");
        //: 而没有默认服务器、也没填的时候，说的是「填一个」不是「连不上」
        let (code, body) = handle("/api/measurements?shot=1&time=0", &cfg);
        assert_eq!(code, 400);
        assert!(body.contains("server box"), "{body}");
    }

    #[test]
    fn every_data_endpoint_refuses_before_opening_a_socket() {
        //: 没有服务器时不是「连不上」，是「没配」——两者对读者是不同的事。
        for t in [
            "/api/measurements?shot=1&time=0",
            "/api/signal?tree=east&shot=1&node=%5CTOP",
            "/api/tree?tree=east&shot=1",
        ] {
            let (code, body) = handle(t, &no_server());
            assert_eq!(code, 400, "{t} -> {body}");
            assert!(body.contains("--mdsip"), "{t} -> {body}");
        }
    }

    #[test]
    fn the_guard_runs_here_too_not_only_in_the_client() {
        //: ★★同一条规则查两遍是**有意的**（FYL-DESIGN-06 §5）：这里查一遍，
        //: `mdsip::Client` 再查一遍。会计算的东西在开 socket 之前就被拒。
        let cfg = Cfg { server: Some(String::from("127.0.0.1:8000")), user: String::from("t") };
        for t in [
            "/api/tree?tree=east;drop&shot=1",
            "/api/signal?tree=east&shot=1&node=getenv(%22HOME%22)",
            "/api/measurements?shot=notanumber&time=1",
            "/api/measurements?shot=1&time=abc",
        ] {
            let (code, body) = handle(t, &cfg);
            assert_eq!(code, 400, "{t} -> {body}");
        }
    }

    #[test]
    fn the_iso_timestamp_matches_the_one_the_node_gateway_prints() {
        //: 实测：EAST #137985 的 `\TOP.MEASUREMENTS:PLASMA` 记录写于
        //: 1713561943906 ms，Node 网关（`new Date(ms).toISOString()`）印
        //: `2024-04-19T21:25:43.906Z`。手写的民用历必须给出同一串。
        assert_eq!(iso8601(1_713_561_943_906), "2024-04-19T21:25:43.906Z");
        assert_eq!(iso8601(0), "1970-01-01T00:00:00.000Z");
        //: 闰年与月末各一个，因为除法在这两处最容易写错
        assert_eq!(iso8601(951_782_400_000), "2000-02-29T00:00:00.000Z");
        assert_eq!(iso8601(1_709_251_199_000), "2024-02-29T23:59:59.000Z");
    }

    #[test]
    fn json_strings_and_non_finite_numbers_are_written_legally() {
        //: ★JSON 没有 NaN：写出来的 `NaN` 会让页面的 `JSON.parse` 整个失败，
        //: 于是一个坏样本带走整条曲线。
        assert_eq!(jnum(f64::NAN), "null");
        assert_eq!(jnum(f64::INFINITY), "null");
        assert_eq!(jarr(&[1.0, f64::NAN, 2.5]), "[1,null,2.5]");
        assert_eq!(jstr("a\"b\\c\nd"), "\"a\\\"b\\\\c\\nd\"");
    }
}
