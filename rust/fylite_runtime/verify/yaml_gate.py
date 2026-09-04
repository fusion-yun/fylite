#!/usr/bin/env python3
"""YAML 子集读者的门：拿 fydata 的每一份 YAML，比对 `fylite data dump` 与 PyYAML `safe_load`。

用法：verify/yaml_gate.py [--bin fy] [fydata 根目录]
没有 fydata（或没有 PyYAML）就跳过——这是核对，不是单元测试。
"""
import json, math, os, subprocess, sys
from pathlib import Path

def canon(x):
    """两边同形：dict 的键序不管；float 与 int 相等即可；NaN 记成字符串。"""
    if isinstance(x, dict):
        return {k: canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [canon(v) for v in x]
    if isinstance(x, float):
        return "nan" if math.isnan(x) else float(x)
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return float(x)
    if hasattr(x, "isoformat"):
        return x.isoformat()
    return x

def diff(a, b, path=""):
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        if lenient_float(a, b):
            return [f"note {path}: rust reads {b!r} as the number {a!r} (PyYAML: a string)"]
        return [f"{path}: {type(a).__name__} vs {type(b).__name__}: {a!r} vs {b!r}"]
    if isinstance(a, dict):
        out = []
        for k in set(a) | set(b):
            if k not in a: out.append(f"{path}/{k}: only in rust"); continue
            if k not in b: out.append(f"{path}/{k}: only in pyyaml"); continue
            out += diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}: len {len(a)} vs {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}/{i}")
        return out
    if isinstance(a, float) and isinstance(b, float):
        return [] if a == b or abs(a - b) <= 1e-12 * max(1.0, abs(a), abs(b)) else [f"{path}: {a!r} vs {b!r}"]
    return [] if a == b else [f"{path}: {a!r} vs {b!r}"]

def lenient_float(a, b):
    """PyYAML (YAML 1.1) 读 `2.2e6` / `140E9` 是字符串（指数要带符号、要有小数点）；
    Rust 侧按数读。这是已知且有意的差别，报告为 note 而不是 fail。"""
    if isinstance(a, float) and isinstance(b, str):
        try:
            return float(b) == a
        except ValueError:
            return False
    return False

def main():
    args = sys.argv[1:]
    binary = "fy"
    if args[:1] == ["--bin"]:
        binary, args = args[1], args[2:]
    root = Path(args[0]) if args else Path(os.environ.get("FYDATA_ROOT", "/home/user/fydata"))
    try:
        import yaml
    except ImportError:
        print("skip: PyYAML is not installed"); return 0
    if not root.is_dir():
        print(f"skip: no fydata at {root}"); return 0
    files = sorted(root.rglob("*.yaml"))
    bad = 0
    for f in files:
        with open(f, encoding="utf-8") as fh:
            ref = yaml.safe_load(fh)
        #: ★`data` 由这里给：只有一个可执行文件，它按命令词分派，
        #: 不给词的缺省是 `app`（起服务），那不是本门要的东西。
        r = subprocess.run([binary, "data", "dump", "--raw", str(f)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"FAIL {f}: {r.stderr.strip()}"); bad += 1; continue
        got = json.loads(r.stdout)
        d = diff(canon(got), canon(ref))
        notes = [x for x in d if x.startswith("note ")]
        d = [x for x in d if not x.startswith("note ")]
        if d:
            bad += 1
            print(f"FAIL {f}:")
            for line in d[:8]:
                print("   ", line)
        else:
            print(f"ok   {f.relative_to(root)}" + (f"  ({len(notes)} lenient float(s))" if notes else ""))
            for line in notes[:4]:
                print("   ", line)
    print(f"{len(files) - bad}/{len(files)} files agree with PyYAML")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
