#!/usr/bin/env python3
"""校验一个已部署的原生适配器包是否与 VERSION.json 一致。

检查项：
  1. 每个 MANIFEST.sha256.json 条目与文件内容一致；
  2. libfylite.so / libsp.so 的 sha256 与 VERSION.json 的内核钉子一致；
  3. demo.py 的 LIB_SHA 常量与实际 libfylite.so 一致。

用法：
  python3 tools/check.py --package /path/to/runtime-package
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check(package: Path) -> int:
    failures = []
    version = json.loads((HERE / 'VERSION.json').read_text(encoding='utf-8'))
    kernel = version['kernel']

    manifest_path = package / 'MANIFEST.sha256.json'
    if not manifest_path.is_file():
        print(f'ERROR 缺少 {manifest_path}', file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

    for name, expected in sorted(manifest.items()):
        path = package / name
        if not path.is_file():
            failures.append(f'缺少文件 {name}')
            continue
        actual = digest(path)
        if actual != expected:
            failures.append(f'{name} sha256 不符（{actual[:12]}… ≠ {expected[:12]}…）')

    for name, expected in (('libfylite.so', kernel['libfylite.so']), ('libsp.so', kernel['libsp.so'])):
        path = package / name
        if not path.is_file():
            failures.append(f'缺少内核库 {name}')
        elif digest(path) != expected:
            failures.append(f'{name} 与 VERSION.json 的内核钉子不符')

    demo = package / 'demo.py'
    if demo.is_file():
        text = demo.read_text(encoding='utf-8')
        match = re.search(r"LIB_SHA\s*=\s*'([0-9a-f]{64})'", text)
        if not match:
            failures.append('demo.py 没有 LIB_SHA 常量')
        else:
            lib = package / 'libfylite.so'
            if lib.is_file() and match.group(1) != digest(lib):
                failures.append('demo.py 的 LIB_SHA 与实际 libfylite.so 不一致')

    if failures:
        for item in failures:
            print('ERROR', item, file=sys.stderr)
        return 1

    print(f'OK {package}')
    print(f'   files      {len(manifest)}')
    print(f'   libfylite  {kernel["libfylite.so"][:12]}…')
    print(f'   kernel     {kernel["tag"]} · ABI {kernel["abi"]}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    args = parser.parse_args()
    if not args.package.is_dir():
        print(f'ERROR 不是目录：{args.package}', file=sys.stderr)
        return 2
    return check(args.package)


if __name__ == '__main__':
    raise SystemExit(main())
