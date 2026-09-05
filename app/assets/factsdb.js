// facts —— 装置信息，**从中间层 wasm 里读**，不再 fetch 一份 JSON。
//
// ★★2026-09-05 用户裁定：**页面也走中间层 wasm，撤掉 `facts.jsonld`**。
// 在此之前同一批装置字节在一个制品里装两遍：一遍是页面 fetch 的 JSON（站点上是
// 文件，可执行文件里是 `assets.rs` 的 `include_bytes!`），一遍编进 Rust 给命令行。
// 两份字节、两条通路，而**没有任何东西保证它们描述同一批机器**——目录说有七台、
// 文件只有六台，这种事不会有任何东西红，只会让读者点下去得到一句「装置数据坏了」。
// 今天只剩一份 `facts.rs`：`libfylite_runtime.so` 与 `fylite_runtime.wasm` 各编进
// 它，命令行与页面读的是同一批字节。
//
// ★这份 wasm 与 `fylite_rs.wasm` / `fylite_kernel_ext.wasm` **不是一回事**：那两份
// 是物理核（私有仓），这一份是中间层（本仓 `rust/fylite_runtime/`）。它零导入
// （`FYL-DESIGN-16` H-5），所以实例化不需要任何宿主函数。
//
// ★★**惰性**：只有真要读装置时才取这份 wasm。装置面板不是首屏必需的东西，而这份
// wasm 比那份 JSON 大——把它放进启动路径，等于让每个只想看一眼首页的读者付这笔钱。
//
// 取字符串的写法与库里其余导出一致：`cap = 0` 先问长度，再给足缓冲问第二次。
// 输入串也要落进库的线性内存（wasm 上宿主与库不共享地址空间），所以有 alloc/free。

(function (root) {
  'use strict';

  var REQUIRED = [
    'fylite_runtime_alloc', 'fylite_runtime_free',
    'fylite_runtime_facts_ids', 'fylite_runtime_facts_doc',
    'fylite_runtime_facts_count', 'memory',
  ];

  var inst = null;      //: 实例，取回来之后一直用
  var pending = null;   //: 正在取的那次，免得并发触发两次下载

  function versioned(url) {
    //: 与 `fylite.js` 的 `versioned()` 同一条规矩：磁盘上的真文件带版本
    //: （`tools/soname.sh`），页面写不带版本的名字，这里补上。
    var v = root.FyRuntimeVersion;
    if (!v || !/\.wasm$/.test(url)) return url;
    return url + '.' + v;
  }

  /** Fetch and instantiate the middle layer.  Resolves to the exports. */
  function load(url) {
    if (inst) return Promise.resolve(inst);
    if (pending) return pending;
    var u = versioned(url || 'assets/fylite_runtime.wasm');
    pending = fetch(u)
      .then(function (r) {
        if (!r.ok) throw new Error('fetch ' + u + ': HTTP ' + r.status);
        return r.arrayBuffer();
      })
      //: ★不用 instantiateStreaming：有些静态主机把 .wasm 的 Content-Type 发错，
      //: 流式编译当场失败，而缓冲这条路照走（与 `fylite.js` 同一条注记）。
      .then(function (buf) { return WebAssembly.instantiate(buf, {}); })
      .then(function (res) {
        var e = res.instance.exports;
        var missing = REQUIRED.filter(function (k) { return !e[k]; });
        if (missing.length)
          throw new Error(u + ': 缺少导出 ' + missing.join(', '));
        inst = e;
        pending = null;
        return e;
      })
      .catch(function (err) { pending = null; throw err; });
    return pending;
  }

  function bytes(e) { return new Uint8Array(e.memory.buffer); }

  //: ★★长度与返回码在 C ABI 上是 `u64` / `i64`，wasm 里就是 `i64`，而 JS 那边
  //: **只能是 BigInt**——传 Number 会当场 `TypeError: Cannot convert 6 to a BigInt`。
  //: 指针是 `*const u8`，在 wasm32 上是 `i32`，仍是普通 Number。两种一起出现，所以
  //: 这两个转换函数就在这里，而不是散在每个调用点：散着写，漏掉一处的表现是一句
  //: 与 facts 毫无关系的类型错。
  function u64(n) { return BigInt(n); }
  function num(n) { return typeof n === 'bigint' ? Number(n) : n; }

  /** Copy a JS string into the module's memory; returns `[ptr, len]`. */
  function push(e, s) {
    var b = new TextEncoder().encode(s);
    if (!b.length) return [0, 0];
    var p = num(e.fylite_runtime_alloc(u64(b.length)));
    if (!p) throw new Error('fylite_runtime_alloc failed');
    bytes(e).set(b, p);
    return [p, b.length];
  }

  /**
   * The two-call read: ask for the length, then ask again with a buffer.
   *
   * ★`ask` returns the length it WANTED, so a short buffer is not silent
   * truncation — it is a number bigger than the buffer, and we grow.
   */
  function pull(e, ask) {
    var n = num(ask(0, u64(0)));
    if (n < 0) return n;                 //: 状态码原样交给调用方
    if (n === 0) return '';
    var p = num(e.fylite_runtime_alloc(u64(n)));
    if (!p) throw new Error('fylite_runtime_alloc failed');
    try {
      var got = num(ask(p, u64(n)));
      if (got < 0) return got;
      return new TextDecoder().decode(bytes(e).subarray(p, p + Math.min(got, n)));
    } finally {
      e.fylite_runtime_free(p, u64(n));
    }
  }

  function withStr(e, s, fn) {
    var a = push(e, s);
    try { return fn(a[0], a[1]); }
    finally { if (a[1]) e.fylite_runtime_free(a[0], u64(a[1])); }
  }

  /** Every id in a domain, `catalogue` included.  Resolves to an array. */
  function ids(domain) {
    return load().then(function (e) {
      return withStr(e, domain, function (dp, dn) {
        var t = pull(e, function (o, c) { return e.fylite_runtime_facts_ids(dp, u64(dn), o, c); });
        if (typeof t !== 'string') throw new Error('facts_ids(' + domain + ') -> ' + t);
        return t ? t.split('\n') : [];
      });
    });
  }

  /**
   * One entry's document, parsed.  `null` when this build does not carry it.
   *
   * ★「这一版不带它」与「它坏了」是两回事，所以缺条目回 `null` 而不是抛：调用方
   * 拿它对读者说前一句，抛出来的才是后一句。
   */
  function doc(domain, ident) {
    return load().then(function (e) {
      return withStr(e, domain, function (dp, dn) {
        return withStr(e, ident, function (ip, inn) {
          var t = pull(e, function (o, c) {
            return e.fylite_runtime_facts_doc(dp, u64(dn), ip, u64(inn), o, c);
          });
          if (t === -2) return null;
          if (typeof t !== 'string') throw new Error('facts_doc(' + domain + '/' + ident + ') -> ' + t);
          return JSON.parse(t);
        });
      });
    });
  }

  /** How many entries this build carries (catalogues excluded). */
  function count() {
    return load().then(function (e) { return num(e.fylite_runtime_facts_count()); });
  }

  root.FyFactsDb = { load: load, ids: ids, doc: doc, count: count, REQUIRED: REQUIRED };
})(typeof self !== 'undefined' ? self : this);
