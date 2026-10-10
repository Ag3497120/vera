#!/usr/bin/env python
"""Embed the exported structure JSON into tools/structure_overview_template.html -> one self-contained index.html.

  python tools/build_structure_overview.py --json structure.json --out index.html
"""
import argparse
import os

ap = argparse.ArgumentParser()
ap.add_argument("--json", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--template", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "structure_overview_template.html"))
a = ap.parse_args()
tpl = open(a.template, encoding="utf-8").read()
data = open(a.json, encoding="utf-8").read().replace("</", "<\\/")   # keep the JSON inert inside <script>
assert "/*__DATA__*/" in tpl
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
open(a.out, "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/", data))
print("wrote", a.out, len(data), "bytes of data")
