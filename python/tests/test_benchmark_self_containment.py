"""`NR-EQ-005` 的门：自包含数值核。

★★**结构判据会腐烂，而且腐烂时一声不响**——加一个依赖、写一句动态导入，
数值一个都不会变，记录却已经不成立。所以这里守四件事，逐件对应记录
`docs/benchmark/records/eq-forward-self-contained-core.jsonld` 的一格：

  1. 数值核 crate 的直接外部依赖 <= 1（只许 `rayon`，且它不参与数值）
  2. 依赖闭包里**没有一个科学计算包**——线性代数与特殊函数全是自写件
  3. `python/fylite` 全包 AST 扫描，`sp` / `spdm` / `fytok` 导入 0 处
  4. ★把三根在 `sys.meta_path` 上**封死**再整包导一遍：AST 抓不到动态导入，这一步抓得到

★内核仓是私有检出，不在的机器**按名跳过**——与本册其余需要机器数据的门同一条政策。
"""
from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys
import textwrap

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
#: 内核仓与公开仓并列检出；没有就跳过
KERNEL = ROOT.parent / "fylite_kernel" / "rust"
BAN = ("sp", "spdm", "fytok", "fyutils", "fydoc", "fydata")
#: ★只许这一个，且 Cargo.toml 自己写明：开不开并行，结果逐位相同
ALLOWED_CRATE_DEPS = {"rayon"}
#: ★闭包里允许出现的外部包 —— 全是 rayon 那条线程栈。**多出任何一个都要回来说清它是什么。**
ALLOWED_CLOSURE = {"rayon", "rayon-core", "crossbeam-deque", "crossbeam-epoch", "crossbeam-utils", "either"}


def _kernel_or_skip() -> pathlib.Path:
    if not (KERNEL / "fylite" / "Cargo.toml").is_file():
        pytest.skip("内核仓不在这台机器上（fylite_kernel/rust 未检出）")
    return KERNEL


def _direct_deps(toml: pathlib.Path) -> list[str]:
    sec = re.search(r"^\[dependencies\](.*?)(?=^\[|\Z)", toml.read_text(encoding="utf-8"), re.S | re.M)
    if not sec:
        return []
    out = []
    for line in sec.group(1).splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+)\s*=", line.split("#")[0].strip())
        if m:
            out.append(m.group(1))
    return out


def test_the_numerical_core_depends_on_one_threading_crate_and_nothing_else():
    deps = set(_direct_deps(_kernel_or_skip() / "fylite" / "Cargo.toml"))
    assert deps <= ALLOWED_CRATE_DEPS, f"数值核多出了依赖：{sorted(deps - ALLOWED_CRATE_DEPS)}"


def test_the_dependency_closure_holds_no_scientific_computing_package():
    """★★这一格才是「自包含」的实质：不是依赖少，是**没有一个在替它算**。"""
    lock = _kernel_or_skip() / "Cargo.lock"
    if not lock.is_file():
        pytest.skip("没有 Cargo.lock（未解过依赖）")
    names = set(re.findall(r'^name = "([^"]+)"', lock.read_text(encoding="utf-8"), re.M))
    own = {"fylite", "fylite_ext", "fylite_static"}
    external = names - own
    assert external <= ALLOWED_CLOSURE, (
        f"依赖闭包里多出：{sorted(external - ALLOWED_CLOSURE)} —— "
        "若其中有线性代数 / 特殊函数 / 数组库，`NR-EQ-005` 就不再成立，记录须改")


def test_the_python_layer_imports_nothing_from_the_ecosystem():
    pkg = ROOT / "python" / "fylite"
    hits = []
    for f in sorted(pkg.rglob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module]
            hits += [f"{f.relative_to(ROOT)}:{node.lineno} {m}" for m in mods if m.split(".")[0] in BAN]
    assert not hits, "生态导入：\n  " + "\n  ".join(hits)


def test_the_package_still_loads_with_the_three_roots_blocked():
    """★AST 抓不到动态导入（`importlib` / `__import__` / 函数体里的延迟导入），封锁加载抓得到。

    ★在**子进程**里跑：封锁器要装到 `sys.meta_path` 上，留在本进程会污染同批其余的门。
    """
    code = textwrap.dedent(f"""
        import importlib, json, pkgutil, sys
        BAN = {("sp", "spdm", "fytok")!r}
        class Blocker:
            def find_module(self, name, path=None): return self.find_spec(name, path)
            def find_spec(self, name, path=None, target=None):
                if name.split('.')[0] in BAN:
                    raise ImportError('BLOCKED:' + name)
                return None
        sys.meta_path.insert(0, Blocker())
        sys.path.insert(0, {str(ROOT / "python")!r})
        import fylite
        blocked, n = [], 0
        for m in pkgutil.walk_packages(fylite.__path__, 'fylite.'):
            try:
                importlib.import_module(m.name); n += 1
            except ImportError as e:
                (blocked.append((m.name, str(e))) if 'BLOCKED:' in str(e) else None)
            except Exception:
                pass
        print(json.dumps({{'n': n, 'blocked': blocked}}))
    """)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, f"隔离加载的子进程炸了：\n{r.stderr[-2000:]}"
    import json as _json
    got = _json.loads(r.stdout.strip().splitlines()[-1])
    assert not got["blocked"], f"封锁三根之后这些模块导不进来：{got['blocked']}"
    assert got["n"] >= 40, f"只导进 {got['n']} 个模块，太少——这一格可能没真跑起来"
