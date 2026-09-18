"""Inline the assembled discharge JSON into the page template.

Usage: python build_page.py TEMPLATE.html DISCHARGE.json OUT.html
"""
import sys
from pathlib import Path

template, data, out = sys.argv[1:4]
text = Path(data).read_text(encoding="utf-8").replace("</", "<\\/")
page = Path(template).read_text(encoding="utf-8").replace("__DATA__", text, 1)
Path(out).write_text(page, encoding="utf-8")
print(f"{out}: {Path(out).stat().st_size / 1e6:.2f} MB")
