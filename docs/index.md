---
title: 开始使用 FyLite
---

# 开始使用 FyLite

当前维护路线是浏览器工作台连接应用服务，由服务调用发布的原生内核。首个应用是磁平衡；旧静态wasm站与`fy app`教程属于冻结的历史资料。

1. 阅读[当前路线、能力与边界](../README.md)。
2. 按[安装与运行](install.md)准备锁定原生包、应用服务和独立算例数据。
3. 查看[工作台使用方法](../delivery/eq/docs/USAGE.zh-CN.html)及[94048计算说明](../delivery/eq/docs/WORKFLOW-94048.zh-CN.html)。
4. 查看[工作流服务接口](../delivery/eq/apps/workflow/README.md)，按运行身份保存和分析结果。

当前rc3原生包不包含wheel；工作台不依赖开发仓源码，不通过wasm或旧同步XHR桥执行物理计算。单用户localhost/SSH部署不等于共享多用户服务。

## 历史资料

[旧快速上手](quickstart.md)、[旧浏览器](browser.md)、[旧CLI](cli.md)、[旧Python](python.md)及[既有算例](../examples/index.md)保留供版本匹配和迁移参考。旧页面“已实现/已验证”的表述属于其原版本，不能直接作为当前工作台的发布依据。
