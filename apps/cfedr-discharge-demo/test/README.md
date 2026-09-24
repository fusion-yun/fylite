# 工作台的两道检查（node 跑，无需浏览器）

页面是单文件、没有构建期类型检查，`node --check` 只看语法——而「页面打得开、点什么都没反应」
那类故障正是语法完全正确的运行期错误（第一行一个 ReferenceError，后面的监听器全都没挂上，
且不报错）。所以这里放两道**真的把脚本跑一遍**的检查：

| 文件 | 做什么 |
| :--- | :--- |
| `domshim.mjs` | 极小 DOM 垫片：`getElementById` · `innerHTML` · `addEventListener` · `fire()` 等，够页面跑完初始化与绘图 |
| `smoke.mjs` | 初始化 + 载入一份输出：断言波形 / 截面 / Miller / 0-D 时序 / PF 波形 / 一维剖面都画出来了，并试写一份 g-file 与单片 JSON |
| `clicks.mjs` | **逐个按钮点一遍**：加删节点、撤销重做、切模式、改点数、主题三态、切页签、导出三件、拖时间条、播放 |

跑法（从算例根目录）：

```bash
node test/clicks.mjs app/cfedr_studio.html -                      # 逐个按钮点一遍
node test/smoke.mjs  app/cfedr_studio.html - app/run_full.json   # 初始化 + 导入一份输出
node test/smoke.mjs  app/cfedr_studio.html - app/run_full.json
```

★页面是**单文件**（默认算例内置、放电数据靠「导入」读），所以第二个参数给 `-`：
没有数据槽可注入了。`smoke.mjs` 的第三个参数就是要导入的那份输出 JSON——走的正是用户点
「导入输出 JSON」那条路。
