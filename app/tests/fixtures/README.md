# 夹具 (Fixtures)

〔`equilibrium.h5` + `equilibrium.json`〕`validate-h5.mjs` 用的一对：前者是**本仓自己写出的
fyo 布局 HDF5**，后者是**原生读者从同一份文件读回来的文档**。两份都入库，所以那道闸是纯
JS 的——参照物是**数据**，不是第二个进程，闸的回路里没有 Python（2026-09-04 用户裁定
「Python 不接入前端」）。

★**为什么参照物要是原生读者的答案，而不是我手写的 JSON。** 手写的参照只能证明浏览器读出了
「我以为它该读出的东西」；与原生读法逐叶子比对，证的是**两个读者对同一份文件不谋而合**——
转置（`FYL-DESIGN-14` L-5）、int64 属性变成 BigInt 之后消失、标量与长度 1 数组混淆，这三类
错都能通过「结构看着对」而只在取值上现形。

布局变了就重新生成，两份一起：

```python
# PYTHONPATH=python python3 -
import json
from fylite.io import fydoc
doc = {...}                                   # 见下方「当前这份的内容」
b = fydoc.Bundle.from_dict(doc)
b.write("app/tests/fixtures/equilibrium.h5")
back = fydoc.read("app/tests/fixtures/equilibrium.h5").to_dict()
open("app/tests/fixtures/equilibrium.json", "w").write(
    json.dumps(back, ensure_ascii=False, indent=1) + "\n")
```

★生成要中间层的 `.so`（`bash rust/build.sh`）。这是**造夹具**，不是闸的回路：闸跑起来只读
这两个文件。

〔当前这份的内容〕一份最小的 `fyo:equilibrium`，刻意把三种情形都放进去：**数组**（`time` ·
轮廓 · 剖面，落成 dataset）、**标量**（`ip` · `r0` · 磁轴，落成属性）、**字符串**（`@id` ·
`@type` · `comment`，落成属性）。少了任何一类，这道闸就有一整类错看不见。
