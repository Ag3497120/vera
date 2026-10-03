"""W5-d2 G1-b (the plan's zsh form `set -- $p` does not split in zsh, so the same comparison is a script).
For each revised attack copy: unified diff of the ORIGINAL (whole file) against the COPY MINUS ITS FIRST LINE (the copy adds one provenance line on top of the
original; the plan's `tail -n +2` on both sides would also drop the original's own first line). Writes <out>/attack_copy_<name>.diff, prints the hunk count and the
names of the top-level defs the hunks fall in. Usage: g1b_diff.py <tree> <out_dir>   (run from anywhere)"""
import ast, difflib, os, re, sys

tree, out = sys.argv[1], sys.argv[2]
PAIRS = [("w3c2", "attacks/W3-c2/test_attack_question_cross.py", "tests/attack/w3c2/test_attack_w3c2_question_cross.py"),
         ("w5b", "attacks/W5-b/test_attack_w5b_wave2.py", "tests/attack/test_attack_w5b_wave2.py"),
         ("w3a3", "attacks/W3-a3/test_attack_w3a3.py", "tests/attack/w3a3/test_attack_w3a3_r6.py")]
os.makedirs(out, exist_ok=True)
allp = []
for name, orig, copy in PAIRS:
    a = open(os.path.join(tree, orig), encoding="utf-8").read().splitlines(keepends=True)
    b = open(os.path.join(tree, copy), encoding="utf-8").read().splitlines(keepends=True)[1:]
    d = list(difflib.unified_diff(a, b, orig, copy + " (minus its first line)", n=3))
    text = "".join(d)
    open(os.path.join(out, f"attack_copy_{name}.diff"), "w", encoding="utf-8").write(text)
    allp.append(text)
    # which top-level names do the changed lines (in the copy's numbering) fall in
    src = "".join(b); mod = ast.parse(src)
    spans = [(n.name, min([n.lineno] + [x.lineno for x in getattr(n, "decorator_list", [])]), n.end_lineno)
             for n in mod.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    names = set(); outside = []
    for m in re.finditer(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,(\d+))? @@", text, re.M): pass
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal": continue
        lo, hi = j1 + 1, max(j2, j1 + 1)
        hit = [nm for nm, s, e in spans if not (hi < s or lo > e)]
        if hit: names.update(hit)
        else: outside.append((tag, lo, hi, "".join(b[j1:j2])[:100]))
    print(f"{name}: hunks={len(re.findall(r'^@@', text, re.M))} changed-in-defs={sorted(names)} changed-outside-defs={outside}")
open(os.path.join(out, "attack_copy_revisions.diff"), "w", encoding="utf-8").write("".join(allp))
