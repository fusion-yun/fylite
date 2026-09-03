//! `fylite-app` —— 把浏览器演示装进一个可执行文件；也是 Rust 宿主的**唯一**命令行。
//!
//! ## 它是什么
//!
//! 一个自带全部站点资源的单文件程序：启动后在回环地址上伺服 `app/`，
//! 拉起系统浏览器，页面照常用 WebAssembly 计算。**没有安装、没有解压、
//! 没有外部运行时**——分发一个 `.exe` 或一个 ELF 就是分发整个演示。
//!
//! ★★2026-09-03（FYL-DESIGN-15）：它是本仓**唯一的可执行文件**——
//! `fylite-app data …` 与 `fylite-app case …` 就是从前的 `fylite-data` /
//! `fylite-case`。那两个二进制**已经撤掉**：它们各十行，做的就是把 `data` /
//! `case` 前置到 argv 再调用同一份代码，而那一次前置由调用方给就够了
//! （Python 宿主委托时前置，人在命令行上直接写 `fylite data …`）。
//! 命令行的**定义**在 `python/fylite/_cli.json`：Python 的 `fylite` 命令与本程序
//! 从同一个文件各自建自己的解析器，用法、选项、帮助一字不差；
//! 只属于一个宿主的少数参数在文件里标了 `hosts`。
//!
//! 不带子命令时它就是 `app`（起服务、开浏览器），所以双击仍然可用。
//!
//! ## 为什么需要它
//!
//! 演示站点本身是静态的，但 `file://` 下取不到 `.wasm`（浏览器不给
//! 本地文件流式编译，也不给 fetch），所以「双击 index.html」这条路走不通；
//! 而 alpha 期的 Python 轮只发 Linux，Windows 用户此前只剩一条联网访问站点的路。
//! 这个程序把两件事同时解决：**离线可分发**，且**不要求装 Python**。
//!
//! ## 边界，说在前面
//!
//! * 它只伺服静态资源。计算仍在页面里由 wasm 完成——**不是**原生内核。
//!   把原生内核接到这里（页面改走 HTTP 而不是 wasm）是下一步，需要一套
//!   请求面，不在本程序范围内。
//! * 只绑回环地址，且**不可配置**为其他地址：这是给本机用的查看器，
//!   不是服务端。想让别人访问，请用站点。
//! * 只答 `GET` 与 `HEAD`。没有上传、没有写入、没有目录列表。
//! * `--app-dir DIR`（开发用）伺服一棵活的目录而不是内嵌字节：同一个请求面，
//!   同一张 MIME 表；路径仍然拒绝 `..`，仍然只在回环上。
//!
//! ★布局用 `src/bin/app/main.rs` 而不是 `src/bin/app.rs`：cargo 会把
//! `src/bin/` 下的**每个** `.rs` 都当成一个可执行目标，于是生成的资源表
//! 会被当成一个缺 `main` 的 bin 而编译失败——wasm 构建门先撞上了这件事。
//! 一个目录一个 bin，同目录的兄弟文件是它的模块，是这件事的惯用写法。
//!
//! ## 用法
//!
//! 用法由 `_cli.json` 生成，`fylite-app --help` 打印；这里只留三行示例：
//!
//! ```text
//! fylite-app                          # 找一个空闲端口，开浏览器
//! fylite-app --port 8123 --no-open    # 指定端口，只伺服
//! fylite-app --page data --device east --lang en --mdsip 127.0.0.1:8000
//! fylite-app data info shot.h5        # 数据层（= `fylite data info shot.h5`）
//! fylite-app case run plan.jsonld --record rec/
//! ```

mod api;
mod assets;

use fylite_data::cli::{self, Args, Parsed, Spec};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream};
use std::path::{Component, Path, PathBuf};

/// 站点根：路径为空或 `/` 时给这一页。
const INDEX: &str = "index.html";
/// 请求行的上限。一个正常的 URL 远短于此；超过的直接拒，不去分配。
const MAX_REQUEST_LINE: usize = 8 * 1024;

/// 资源从哪里来：内嵌的表，或（开发时）一棵目录。
enum Source {
    Embedded,
    Dir(PathBuf),
}

fn main() {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    let spec = cli::spec();
    let args = match cli::parse(spec, cli::HOST, "fylite-app", &argv) {
        Parsed::Help(text) => {
            print!("{text}");
            return;
        }
        Parsed::Error(msg) => {
            eprintln!("{msg}");
            std::process::exit(2);
        }
        Parsed::Run(a) => a,
    };
    match args.word(0) {
        "data" => cli::data::run(&args),
        "case" => cli::case::run(&args),
        "app" => serve_app(spec, &args),
        other => die(&format!("命令 {other:?} 不归本程序；--help 列出它有的")),
    }
}

/// `app`：起服务、开浏览器。选项按 `_cli.json` 的 `app` 命令。
fn serve_app(spec: &Spec, args: &Args) {
    let port: Option<u16> = args.flag("port").map(|p| match p.parse::<u16>() {
        Ok(v) if v >= 1 => v,
        _ => die("--port 要一个 1..65535 的端口号"),
    });
    let open = !args.has("no-open");
    //: ★没有缺省服务器：一个查看器不该在别人机器上悄悄向某个地址开连接。
    //: 不给 `--mdsip` 时请求面照在，只是答 `ok:false` 并说明原因。
    let mdsip: Option<String> = args.flag("mdsip").map(str::to_string);
    let mds_user = args
        .flag("mds-user")
        .map(str::to_string)
        .unwrap_or_else(|| std::env::var("USER").unwrap_or_else(|_| String::from("nobody")));
    let source = match args.flag("app-dir") {
        Some(d) => {
            let dir = PathBuf::from(d);
            if !dir.join(INDEX).is_file() {
                die(&format!("--app-dir {d:?} 里没有 {INDEX}——它得是一份 app/"));
            }
            Source::Dir(dir)
        }
        None => Source::Embedded,
    };

    let listener = match bind(port) {
        Ok(l) => l,
        Err(e) => die(&format!("{e}")),
    };
    let addr = listener.local_addr().expect("已绑定的监听器必有地址");
    let base = format!("http://{addr}/");
    let url = launch_url(spec, args, &base);
    let cfg = std::sync::Arc::new(api::Cfg { server: mdsip, user: mds_user });
    let source = std::sync::Arc::new(source);

    println!("fylite 演示：{url}");
    if let Source::Dir(d) = &*source {
        println!("资源：{}（活目录，开发用）", d.display());
    }
    match &cfg.server {
        Some(s) => println!("mdsip：{s}（用户 {}）", cfg.user),
        //: ★不是「不能用」：服务器那一格在页面上可写（只绑回环，能敲它的人就是
        //: 启动这个进程的人），所以没给就是「在页面上填」。
        None => println!(
            "mdsip：未预设 —— 在装置数据页/反演页的服务器格里填 \
                          HOST:PORT，或重起时加 --mdsip"
        ),
    }
    println!("按 Ctrl-C 结束。");
    if open {
        //: 打不开浏览器不是错误——地址已经印在上面了，用户可以自己粘贴。
        //: 把它当致命错误会让无图形界面的机器上完全用不了。
        if let Err(e) = open_browser(&url) {
            println!("（没能自动打开浏览器：{e}；请手动访问上面的地址）");
        }
    }

    for stream in listener.incoming() {
        match stream {
            //: ★★每连接一个线程，而这不是从前的写法。从前「一次一个连接」
            //: 成立，是因为每个请求都只是把一块内存写回去；接上 mdsip 之后
            //: 一次读要**几秒到十几秒**（一条隧道另一端的整炮磁测量），
            //: 排队处理会让页面在那期间连一张图标都取不到——看上去像死了。
            //: 上限是浏览器自己的每主机并发数（~6），不是无界。
            Ok(s) => {
                let cfg = std::sync::Arc::clone(&cfg);
                let source = std::sync::Arc::clone(&source);
                std::thread::spawn(move || {
                    if let Err(e) = serve(s, &cfg, &source) {
                        //: 客户端中途断开是常态（刷新、关页），不值得刷屏
                        if e.kind() != std::io::ErrorKind::BrokenPipe
                            && e.kind() != std::io::ErrorKind::ConnectionReset
                        {
                            eprintln!("请求处理失败：{e}");
                        }
                    }
                });
            }
            Err(e) => eprintln!("接受连接失败：{e}"),
        }
    }
}

/// 打开的地址：`--page` 决定路径，其余带 `app_param` 的选项按 `hosts.app.params`
/// 里声明的载体（`query`）写进查询串——参数的**名字**只在 `_cli.json` 里说一次。
fn launch_url(spec: &Spec, args: &Args, base: &str) -> String {
    let mut url = String::from(base);
    let mut query: Vec<String> = Vec::new();
    for p in &spec.app_params {
        let Some(v) = args.flag(&p.name) else { continue };
        match p.carrier.as_str() {
            "path" => {
                if v != "home" {
                    url.push_str(&format!("pages/{v}.html"));
                }
            }
            "query" => query.push(format!("{}={}", p.name, percent(v))),
            _ => {}
        }
    }
    if !query.is_empty() {
        url.push('?');
        url.push_str(&query.join("&"));
    }
    url
}

/// 最小的百分号编码：字母数字与 `-_.~` 原样，其余逐字节编码。
fn percent(s: &str) -> String {
    let mut out = String::new();
    for b in s.bytes() {
        if b.is_ascii_alphanumeric() || b"-_.~".contains(&b) {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

fn die(msg: &str) -> ! {
    eprintln!("fylite-app: {msg}");
    std::process::exit(2)
}

/// 绑定回环地址。给定端口就用它（占用即失败并说清楚）；否则让系统挑。
fn bind(port: Option<u16>) -> std::io::Result<TcpListener> {
    let want = port.unwrap_or(0);
    let addr = SocketAddr::from((Ipv4Addr::LOCALHOST, want));
    TcpListener::bind(addr).map_err(|e| {
        if port.is_some() && e.kind() == std::io::ErrorKind::AddrInUse {
            std::io::Error::new(
                e.kind(),
                format!("端口 {want} 已被占用——换一个 --port，或者省略它让系统挑"),
            )
        } else {
            e
        }
    })
}

/// 用系统默认浏览器打开 URL。
///
/// ★三个平台三条命令，没有第四条路：这是唯一一处平台相关代码，
/// 集中在这里而不是散在调用点，是为了让「多支持一个平台」是一次编辑。
fn open_browser(url: &str) -> std::io::Result<()> {
    use std::process::{Command, Stdio};
    let mut cmd = if cfg!(target_os = "windows") {
        //: `start` 是 cmd 的内建命令，不是可执行文件，所以必须经 cmd；
        //: 空的 "" 是 start 的窗口标题位——省掉它会把 URL 当标题吃掉。
        let mut c = Command::new("cmd");
        c.args(["/C", "start", "", url]);
        c
    } else if cfg!(target_os = "macos") {
        let mut c = Command::new("open");
        c.arg(url);
        c
    } else {
        let mut c = Command::new("xdg-open");
        c.arg(url);
        c
    };
    cmd.stdout(Stdio::null()).stderr(Stdio::null()).spawn().map(|_| ())
}

/// 站点内路径 -> 资源。精确匹配，不拼接路径。
fn lookup(path: &str) -> Option<(&'static [u8], &'static str)> {
    let key = path.trim_start_matches('/');
    let key = if key.is_empty() { INDEX } else { key };
    assets::ASSETS
        .iter()
        .find(|(name, _, _)| *name == key)
        .map(|(_, body, mime)| (*body, *mime))
}

/// 扩展名 -> content-type，与 `tools/make-app-embed.mjs` 的表同一份。
fn mime_of(path: &str) -> &'static str {
    match path.rsplit_once('.').map(|(_, e)| e).unwrap_or("") {
        "html" => "text/html; charset=utf-8",
        "css" => "text/css; charset=utf-8",
        "js" | "mjs" => "text/javascript; charset=utf-8",
        "json" => "application/json; charset=utf-8",
        "jsonld" => "application/ld+json; charset=utf-8",
        //: ★这一行是整张表里唯一不能出错的：浏览器只在 `application/wasm` 下走
        //: 流式编译，MIME 错了就是一句 TypeError，而不是一个慢一点的页面。
        "wasm" => "application/wasm",
        "svg" => "image/svg+xml",
        "png" => "image/png",
        "ico" => "image/x-icon",
        "woff2" => "font/woff2",
        "txt" => "text/plain; charset=utf-8",
        "md" => "text/markdown; charset=utf-8",
        _ => "application/octet-stream",
    }
}

/// 站点内路径 -> 目录里的文件（`--app-dir`）。只接受相对的、不含 `..` 的路径。
fn lookup_dir(dir: &Path, path: &str) -> Option<(Vec<u8>, &'static str)> {
    let key = path.trim_start_matches('/');
    let key = if key.is_empty() { INDEX } else { key };
    let rel = Path::new(key);
    if rel.components().any(|c| !matches!(c, Component::Normal(_))) {
        return None;
    }
    let full = dir.join(rel);
    if !full.is_file() {
        return None;
    }
    std::fs::read(&full).ok().map(|body| (body, mime_of(key)))
}

fn serve(mut stream: TcpStream, cfg: &api::Cfg, source: &Source) -> std::io::Result<()> {
    let mut reader = BufReader::new(stream.try_clone()?);

    let mut line = String::new();
    //: 限长读：一个畸形的客户端不该能让本程序无限分配
    let mut limited = (&mut reader).take(MAX_REQUEST_LINE as u64);
    limited.read_line(&mut line)?;
    if line.is_empty() {
        return Ok(()); //: 连接开了又关，没说话
    }

    let mut parts = line.split_whitespace();
    let method = parts.next().unwrap_or("");
    let target = parts.next().unwrap_or("/");

    //: 请求头读完丢掉——本程序不看任何一个头（没有条件请求、没有范围请求、
    //: 没有内容协商）。不读完则会话缓冲里留着字节，keep-alive 下一次请求就错位。
    let mut header = String::new();
    loop {
        header.clear();
        let n = (&mut reader).take(MAX_REQUEST_LINE as u64).read_line(&mut header)?;
        if n == 0 || header == "\r\n" || header == "\n" {
            break;
        }
    }

    if method != "GET" && method != "HEAD" {
        return respond(&mut stream, 405, "text/plain; charset=utf-8", b"only GET and HEAD", true);
    }

    //: 查询串与片段不参与查找：`?v=123` 这类缓存破除参数是页面自己加的
    let path = target.split(['?', '#']).next().unwrap_or("/");

    //: ★请求面在静态查找之前：`/api/...` 不是站点里的文件，而资源表是精确
    //: 匹配的，落到 `lookup` 只会变成一个 404——那正是接上 mdsip 之前
    //: `pages/data.html` 在这个可执行体里的样子。
    if path.starts_with("/api/") {
        let (status, body) = api::handle(target, cfg);
        return respond(&mut stream, status, "application/json; charset=utf-8", body.as_bytes(), method == "GET");
    }

    match source {
        Source::Embedded => match lookup(path) {
            Some((body, mime)) => respond(&mut stream, 200, mime, body, method == "GET"),
            None => respond(&mut stream, 404, "text/plain; charset=utf-8", b"not found", method == "GET"),
        },
        Source::Dir(dir) => match lookup_dir(dir, path) {
            Some((body, mime)) => respond(&mut stream, 200, mime, &body, method == "GET"),
            None => respond(&mut stream, 404, "text/plain; charset=utf-8", b"not found", method == "GET"),
        },
    }
}

fn respond(stream: &mut TcpStream, status: u16, mime: &str, body: &[u8], with_body: bool) -> std::io::Result<()> {
    let reason = match status {
        200 => "OK",
        404 => "Not Found",
        405 => "Method Not Allowed",
        _ => "Error",
    };
    //: `Connection: close` 而不是 keep-alive：单连接串行处理的服务器上，
    //: 保持连接会让下一个请求等着前一个页面关掉。这台机器上省下的那几毫秒
    //: 不值得那种停顿。
    let head = format!(
        "HTTP/1.1 {status} {reason}\r\n\
         Content-Type: {mime}\r\n\
         Content-Length: {}\r\n\
         Cache-Control: no-store\r\n\
         Connection: close\r\n\r\n",
        body.len()
    );
    stream.write_all(head.as_bytes())?;
    if with_body {
        stream.write_all(body)?;
    }
    stream.flush()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 站点根要能给出首页，且首页确实在表里 —— 一个空表也能让
    /// 「服务器起来了」为真，所以这条同时是资源表非空的哨兵。
    #[test]
    fn the_site_root_serves_the_index() {
        let (body, mime) = lookup("/").expect("站点根应给出首页");
        assert!(mime.starts_with("text/html"), "首页的 content-type: {mime}");
        assert!(body.len() > 500, "首页只有 {} 字节，像是空的", body.len());
        assert_eq!(
            lookup("/index.html").unwrap().0.as_ptr(),
            body.as_ptr(),
            "`/` 与 `/index.html` 应是同一份字节"
        );
    }

    /// ★wasm 的 content-type 是这张表里唯一不能错的一条：错了浏览器不走
    /// 流式编译，页面以一句 TypeError 失败，而不是慢一点。
    #[test]
    fn every_wasm_is_served_as_application_wasm() {
        let mut seen = 0;
        for (name, _, mime) in assets::ASSETS {
            if name.ends_with(".wasm") {
                assert_eq!(*mime, "application/wasm", "{name} 的 content-type 是 {mime}");
                seen += 1;
            }
        }
        assert!(seen >= 3, "只找到 {seen} 个 wasm —— 站点应有三个内核模块");
    }

    /// 查找是精确匹配，所以路径穿越无从谈起 —— 这条把「无从谈起」
    /// 变成一条会失败的断言，而不是一句注释里的保证。
    #[test]
    fn traversal_and_absolute_paths_find_nothing() {
        for probe in ["../Cargo.toml", "/../../etc/passwd", "//etc/passwd", "assets/../../secret", "\\windows\\system32"] {
            assert!(lookup(probe).is_none(), "{probe} 不该匹配到任何资源");
        }
    }

    /// 活目录的查找同样拒绝穿越：`..`、绝对路径、根名都不是一个站点内路径。
    #[test]
    fn the_live_directory_refuses_traversal_too() {
        let dir = std::env::temp_dir().join(format!("fylite-app-test-{}", std::process::id()));
        std::fs::create_dir_all(dir.join("assets")).unwrap();
        std::fs::write(dir.join(INDEX), "<html>hello</html>").unwrap();
        std::fs::write(dir.join("assets/x.wasm"), b"\0asm").unwrap();
        assert_eq!(lookup_dir(&dir, "/").unwrap().1, "text/html; charset=utf-8");
        assert_eq!(lookup_dir(&dir, "/assets/x.wasm").unwrap().1, "application/wasm");
        for probe in ["../Cargo.toml", "/../../etc/passwd", "//etc/passwd", "assets/../index.html"] {
            assert!(lookup_dir(&dir, probe).is_none(), "{probe} 不该匹配到任何文件");
        }
        let _ = std::fs::remove_dir_all(&dir);
    }

    /// 每一份资源都要有内容：一个 0 字节的条目在页面上表现为
    /// 「白屏但 200」，比 404 更难查。
    #[test]
    fn no_asset_is_empty() {
        for (name, body, _) in assets::ASSETS {
            assert!(!body.is_empty(), "{name} 是空的");
        }
    }

    /// 打开的地址由 `--page` 与带 `app_param` 的选项拼出，名字来自 `_cli.json`。
    #[test]
    fn the_launch_url_carries_the_declared_parameters() {
        let spec = cli::spec();
        let argv: Vec<String> = "app --page data --device east --lang en --theme dark"
            .split_whitespace()
            .map(str::to_string)
            .collect();
        let args = match cli::parse(spec, cli::HOST, "fylite-app", &argv) {
            Parsed::Run(a) => a,
            other => panic!("{other:?}"),
        };
        let url = launch_url(spec, &args, "http://127.0.0.1:1/");
        assert_eq!(url, "http://127.0.0.1:1/pages/data.html?device=east&lang=en&theme=dark");
        let none = match cli::parse(spec, cli::HOST, "fylite-app", &[]) {
            Parsed::Run(a) => launch_url(spec, &a, "http://127.0.0.1:1/"),
            other => panic!("{other:?}"),
        };
        assert_eq!(none, "http://127.0.0.1:1/");
        assert_eq!(percent("a b/é"), "a%20b%2F%C3%A9");
    }
}
