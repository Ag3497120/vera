"""W5-d2: which top-level names (def / class / assignment) of a test file are CHANGED / ADDED / REMOVED against the base commit.
Usage: changed_functions.py <rev> <file>...                      (compares each file with `git show <rev>:<file>`)
       changed_functions.py --pairs <new>=<orig>...              (attack copies: compares <new> with <orig>, first line of both dropped)
Run from the tree root. A name is CHANGED when its source segment differs (ast.get_source_segment); decorators are part of the segment of a def."""
import ast, subprocess, sys

def segments(src):
    tree = ast.parse(src)
    lines = src.splitlines()
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            out[name] = "\n".join(lines[start - 1:node.end_lineno])
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            tg = node.targets if isinstance(node, ast.Assign) else [node.target]
            nm = ",".join(t.id if isinstance(t, ast.Name) else ast.dump(t) for t in tg)
            out["=" + nm] = "\n".join(lines[node.lineno - 1:node.end_lineno])
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            out["import:" + "\n".join(lines[node.lineno - 1:node.end_lineno])] = "\n".join(lines[node.lineno - 1:node.end_lineno])
    return out

def main(argv):
    pairs = []
    if argv and argv[0] == "--pairs":          # attack copies: <new>=<orig>, the first line of both is dropped
        for a in argv[1:]:
            new, orig = a.split("=", 1)
            pairs.append((new, open(orig, encoding="utf-8").read().split("\n", 1)[1], open(new, encoding="utf-8").read().split("\n", 1)[1]))
    else:
        rev, files = argv[0], argv[1:]
        for f in files:
            before = subprocess.run(["git", "show", f"{rev}:{f}"], capture_output=True, text=True).stdout
            pairs.append((f, before, open(f, encoding="utf-8").read()))
    for f, before, after in pairs:
        b, a = segments(before), segments(after)
        print(f"## {f}")
        for k in a:
            if k not in b: print(f"ADDED {k}")
            elif a[k] != b[k]: print(f"CHANGED {k}")
        for k in b:
            if k not in a: print(f"REMOVED {k}")

main(sys.argv[1:])
