#!/usr/bin/env python3
"""把一个 fylite 原生适配器包组装出来。

输入：
  - 本目录的适配器源码（demo.py / facts/ / input/，不含装置响应表）
  - 装置响应表：从公共只读目录取，按 input/tables.lock.json 的 sha256 校验
  - 内核发布树里的 .so（默认取 rc3 的 lib/）

输出：
  - 一个完整可运行的包目录：适配器文件 + input/tables/*.ddd + libfylite.so + libsp.so + MANIFEST.sha256.json

用法：
  python3 tools/build_package.py --release-dir /path/to/v0.0.1-alpha-rc3/eq --out /path/to/out
  python3 tools/build_package.py ... --tables-dir /path/to/tables        # 覆盖响应表目录
  python3 tools/build_package.py --release-dir ... --check-only          # 只校验身份，不写文件
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DEFAULT_TABLES = Path('/project/FyLite/data/native-adapter/tables')
SKIP_DIRS = {'__pycache__', 'output', 'tools', '.git'}
#: 装置响应表不进仓库，构建时从 --tables-dir 取
SKIP_REL = {'input/tables'}
KERNEL_LIB = ('libfylite_kernel.so', 'libfylite.so')
SP_LIB = ('libsp.so',)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def adapter_files() -> list[Path]:
    files = []
    for path in sorted(HERE.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(HERE)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if str(rel).replace('\\', '/') in SKIP_REL or str(rel.parent).replace('\\', '/') in SKIP_REL:
            continue
        if rel.name == 'MANIFEST.sha256.json':
            continue
        files.append(rel)
    return files


def find_one(root: Path, names: tuple[str, ...]) -> Path:
    for name in names:
        candidate = root / 'lib' / name
        if candidate.is_file():
            return candidate
    raise SystemExit(f'{root}/lib 下找不到 {names}')


def patch_lib_sha(demo: Path, expected: str) -> None:
    text = demo.read_text(encoding='utf-8')
    patched, count = re.subn(r"LIB_SHA\s*=\s*'[0-9a-f]{64}'", f"LIB_SHA = '{expected}'", text)
    if count != 1:
        raise SystemExit('demo.py 里没有找到唯一的 LIB_SHA 常量')
    if patched != text:
        demo.write_text(patched, encoding='utf-8')


def verify_tables(tables_dir: Path) -> dict[str, Path]:
    lock = json.loads((HERE / 'input/tables.lock.json').read_text(encoding='utf-8'))
    resolved = {}
    problems = []
    for name, meta in sorted(lock['files'].items()):
        path = tables_dir / name
        if not path.is_file():
            problems.append(f'缺少装置响应表 {path}')
            continue
        if path.stat().st_size != meta['size']:
            problems.append(f'{name} 大小不符（{path.stat().st_size} ≠ {meta["size"]}）')
        elif digest(path) != meta['sha256']:
            problems.append(f'{name} sha256 不符')
        else:
            resolved[name] = path
    if problems:
        for item in problems:
            print('ERROR', item, file=sys.stderr)
        raise SystemExit(2)
    return resolved


def build(release_dir: Path, out: Path | None, tables_dir: Path, check_only: bool) -> int:
    version = json.loads((HERE / 'VERSION.json').read_text(encoding='utf-8'))
    kernel = version['kernel']
    lib_kernel = find_one(release_dir, KERNEL_LIB)
    lib_sp = find_one(release_dir, SP_LIB)

    problems = []
    if digest(lib_kernel) != kernel['libfylite.so']:
        problems.append(f'{lib_kernel.name} 的 sha256 与 VERSION.json 不符')
    if digest(lib_sp) != kernel['libsp.so']:
        problems.append(f'{lib_sp.name} 的 sha256 与 VERSION.json 不符')
    if problems:
        for item in problems:
            print('ERROR', item, file=sys.stderr)
        return 2

    tables = verify_tables(tables_dir)

    if check_only:
        print(f"内核库身份 OK：{lib_kernel.name} = {kernel['libfylite.so'][:12]}…")
        print(f'装置响应表 OK：{len(tables)} 份，来自 {tables_dir}')
        return 0

    assert out is not None
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for rel in adapter_files():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / rel, target)

    tables_out = out / 'input' / 'tables'
    tables_out.mkdir(parents=True, exist_ok=True)
    for name, path in tables.items():
        shutil.copyfile(path, tables_out / name)

    shutil.copyfile(lib_kernel, out / 'libfylite.so')
    shutil.copyfile(lib_sp, out / 'libsp.so')
    patch_lib_sha(out / 'demo.py', kernel['libfylite.so'])

    manifest = {}
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name != 'MANIFEST.sha256.json':
            manifest[str(path.relative_to(out)).replace('\\', '/')] = digest(path)
    (out / 'MANIFEST.sha256.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    print(f'built {out}')
    print(f'  files      {len(manifest)}')
    print(f'  tables     {len(tables)}（来自 {tables_dir}）')
    print(f'  libfylite  {manifest["libfylite.so"][:12]}…')
    print(f'  libsp      {manifest["libsp.so"][:12]}…')
    print(f'  demo.py    {manifest["demo.py"][:12]}…')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', required=True, type=Path,
                        help='内核发布树（含 lib/libfylite_kernel.so 与 lib/libsp.so）')
    parser.add_argument('--out', type=Path, help='输出目录（运行时包）')
    parser.add_argument('--tables-dir', type=Path, default=DEFAULT_TABLES,
                        help=f'装置响应表目录（默认 {DEFAULT_TABLES}）')
    parser.add_argument('--check-only', action='store_true', help='只校验内核库与响应表身份，不写文件')
    args = parser.parse_args()
    if not args.check_only and args.out is None:
        parser.error('--out 是必需的（除非 --check-only）')
    return build(args.release_dir, args.out, args.tables_dir, args.check_only)


if __name__ == '__main__':
    raise SystemExit(main())
