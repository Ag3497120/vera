"""W5-d2: write (or check) the <!-- w5d2-amended --> region of a doc: for every CHANGED top-level def/class/assignment of the given test files,
the full text before (git show <rev>:<file>, or the attack original) and after. Generated, never hand-copied.
Usage: amended_texts.py --doc docs/X.md --rev c875ed3 --files f1 f2 ... [--pairs new=orig ...] (--write | --check)
Run from the tree root. --check exits 0 when the region in the doc equals what the files produce now."""
import ast, re, subprocess, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])

def segments(src):
    tree = ast.parse(src); lines = src.splitlines(); out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            out[node.name] = "\n".join(lines[start - 1:node.end_lineno])
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            tg = node.targets if isinstance(node, ast.Assign) else [node.target]
            out["=" + ",".join(t.id if isinstance(t, ast.Name) else ast.dump(t) for t in tg)] = "\n".join(lines[node.lineno - 1:node.end_lineno])
    return out

def build(rev, files, pairs):
    items = []
    for f in files:
        before = subprocess.run(["git", "show", f"{rev}:{f}"], capture_output=True, text=True).stdout
        items.append((f, f"git show {rev}:{f}", before, open(f, encoding="utf-8").read()))
    for p in pairs:
        new, orig = p.split("=", 1)
        items.append((new, f"the attack original {orig} (first line dropped)", open(orig, encoding="utf-8").read().split("\n", 1)[1], open(new, encoding="utf-8").read().split("\n", 1)[1]))
    out = []
    for f, src, before, after in items:
        b, a = segments(before), segments(after)
        changed = [k for k in a if k in b and a[k] != b[k]]
        added = [k for k in a if k not in b]
        out.append(f"#### `{f}` (before = {src})\n")
        out.append("Added (helpers / tests, not amendments): " + (", ".join(f"`{k}`" for k in added) if added else "none") + "\n")
        for k in changed:
            out.append(f"##### `{k}` — before\n\n```python\n{b[k]}\n```\n\n##### `{k}` — after\n\n```python\n{a[k]}\n```\n")
    return "\n".join(out)

def main(argv):
    doc = rev = None; files = []; pairs = []; mode = None; cur = None
    i = 0
    while i < len(argv):
        x = argv[i]
        if x == "--doc": doc = argv[i + 1]; i += 2; continue
        if x == "--rev": rev = argv[i + 1]; i += 2; continue
        if x == "--files": cur = files; i += 1; continue
        if x == "--pairs": cur = pairs; i += 1; continue
        if x in ("--write", "--check"): mode = x; i += 1; continue
        cur.append(x); i += 1
    body = "\n" + build(rev, files, pairs) + "\n"
    text = open(doc, encoding="utf-8").read()
    pat = re.compile(r"(<!-- w5d2-amended:begin -->)(.*?)(<!-- w5d2-amended:end -->)", re.S)
    m = pat.search(text)
    if mode == "--check":
        sys.exit(0 if m and m.group(2) == body else 1)
    if m: text = text[:m.start(2)] + body + text[m.end(2):]
    else: text = text.rstrip("\n") + "\n\n<!-- w5d2-amended:begin -->" + body + "<!-- w5d2-amended:end -->\n"
    open(doc, "w", encoding="utf-8").write(text)

main(sys.argv[1:])
