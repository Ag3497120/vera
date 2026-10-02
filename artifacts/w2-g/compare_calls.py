# compares calls_before.jsonl and calls_after.jsonl per (frame, q, opts, mode, map); writes calls_changes.txt
import json, sys, os
here = os.path.dirname(os.path.abspath(__file__))
def load(n):
    d = {}
    for ln in open(os.path.join(here, n), encoding="utf-8"):
        r = json.loads(ln)
        d.setdefault((r["frame"] + ("@" + str(r["fsha"]) if r["frame"].endswith(".md") else ""), r["q"], json.dumps(r["opts"], ensure_ascii=False),
                      r["mode"], r["map"]), []).append(r)
    return d
b, a = load("calls_before.jsonl"), load("calls_after.jsonl")
def sig(r): return (r["decision"], r["index"], r["answer"], r["reason"], r["detail"])
def cls(x, y):
    if x[0] == "answer" and y[0] == "escalate": return "answer->escalate"
    if x[0] == "escalate" and y[0] == "answer": return "escalate->answer"
    if x[0] == "answer": return "answer value/index changed"
    return "escalate reason/detail changed"
names = ["answer->escalate", "escalate->answer", "answer value/index changed", "escalate reason/detail changed"]
cats = {"off_or_scripted_only": {n: [] for n in names}, "other(codex/claude/map)": {n: [] for n in names}}
nondet = 0
only_b = sorted(set(b) - set(a)); only_a = sorted(set(a) - set(b))
for k in sorted(set(b) & set(a)):
    sb = {sig(r) for r in b[k]}; sa = {sig(r) for r in a[k]}
    if len(sb) > 1 or len(sa) > 1: nondet += 1
    if sb == sa: continue
    x, y = sorted(sb)[0], sorted(sa)[0]
    grp = "off_or_scripted_only" if (k[3] in ("off", "fake") and not k[4]) else "other(codex/claude/map)"
    cats[grp][cls(x, y)].append((k, x, y))
out = [f"# calls_before.jsonl lines: {sum(len(v) for v in b.values())} distinct keys: {len(b)}",
       f"# calls_after.jsonl  lines: {sum(len(v) for v in a.values())} distinct keys: {len(a)}",
       f"# keys only in before: {len(only_b)} / only in after: {len(only_a)} (only-after = calls of the new test files; not counted as changes)",
       f"# keys with more than one distinct result inside one run: {nondet}"]
for g, c in cats.items():
    out.append(f"# counts [{g}]: " + str({k: len(v) for k, v in c.items()}))
for k in only_b: out.append(f"   only-before {k[0]} | {k[1]} | {k[2]} | {k[3]} {k[4]}")
for g, c in cats.items():
    for n, v in c.items():
        out.append(f"== [{g}] {n} {len(v)}")
        for k, x, y in v:
            tests = sorted({r["test"] for r in a.get(k, []) + b.get(k, [])})
            out.append(f"   [{','.join(tests)}] {k[0]} | {k[1]} | {k[2]} | mode={k[3]} map={k[4]} | {x} -> {y}")
open(os.path.join(here, "calls_changes.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out[:4 + len(cats)]))
