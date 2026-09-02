//! fylite 的数据层 —— **取数与格式，不做物理**。
//!
//! ★★为什么它不在内核里。内核那本自己写着：*the kernel computes numbers; the
//! hosts put them into documents*（`fyo.rs`），并且点名装置描述是「内核唯一不读
//! 的文档」，理由是「在算数的那层做宿主已经在做的活」（FYL-SDD-01 DE-COMP-02）。
//! 一个网络协议编解码器按同一条判据也是宿主的活。2026-09-02 实测下来，内核库
//! 除了 `mdsip` 之外**已经**是装置中立、格式中立的：装置名在代码里零处（130 处
//! 提及全在注释与测试），没有任何文件格式解析器。所以搬走 `mdsip` 之后，那条
//! 判据在内核里就没有例外了。
//!
//! ★★为什么源码公开，而内核不公开。这里是**协议与格式**，不是物理 IP。公开它
//! 既不损内核那条私有边界，又让「一份实现」成立：Python 与桌面查看器用同一份，
//! 不再各写一个。本仓从前有两份 g-file 读入（`python/fylite/io/geqdsk.py` 752 行
//! 与 `app/assets/geqdsk.js` 286 行）与两份 mdsip 客户端——那正是这一层要收掉的。
//!
//! ## 三个制品，一份源
//!
//! | 制品 | 给谁 | 带 mdsip 吗 |
//! | --- | --- | --- |
//! | `libfylite_data.so` | Python（`ctypes`，与内核库同一种取法） | 是 |
//! | `fylite-app` | 单文件桌面查看器 | 是 |
//! | `fylite_data.wasm` | 浏览器 | **否**（用户裁定；浏览器打不开裸 TCP） |

#![allow(dead_code)]

#[cfg(feature = "mdsip")]
pub mod mdsip;

#[cfg(feature = "mdsip")]
pub mod c_api;
