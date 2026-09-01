# 安全问题的报告方式 · Reporting a security issue

**请不要**把安全问题写成公开 issue。

Please do **not** open a public issue for a security problem.

发邮件给维护者（见 [`CONTRIBUTORS.md`](CONTRIBUTORS.md)），标题带
`[fylite security]`。请附上：制品名与版本号、接口版本（ABI）、sha256、
以及能让人复现的最小输入。

Email the maintainers listed in [`CONTRIBUTORS.md`](CONTRIBUTORS.md) with
`[fylite security]` in the subject. Include the artifact name and version,
the interface (ABI) version, its sha256, and a minimal reproducing input.

## 范围 · Scope

本仓发布的是**计算内核**：它不开网络连接，不写调用者没指定的路径，浏览器里
跑在页面自己的沙箱内。因此这里的「安全问题」主要指内存安全（越界、未定义
行为）与在恶意输入下的崩溃/挂死，而不是 Web 服务类漏洞。

The artifacts are a **computational kernel**: it opens no network
connections and writes no paths the caller did not name. Security issues
here are memory safety and denial-of-service on hostile input, not
web-service vulnerabilities.

浏览器演示页 <https://fusion-yun.github.io/fylite/> 是静态站点，不接收上传、
不保存访问者数据。

## 处置 · What happens next

收到后一周内回执。确认成立的问题在下一个 Release 修复，并在 Release 说明里
记名（除非你要求不记）。
