# compares calls_before.jsonl and calls_after.jsonl per (frame, question, options); writes calls_changes.txt
import json, sys, os
here = os.path.dirname(os.path.abspath(__file__))
def load(n):
    d = {}
    for ln in open(os.path.join(here, n), encoding="utf-8"):
        r = json.loads(ln)
        d.setdefault((r["frame"] + ("@" + str(r["fsha"]) if r["frame"].endswith(".md") else ""), r["q"], json.dumps(r["opts"], ensure_ascii=False)), []).append(r)
    return d
b, a = load("calls_before.jsonl"), load("calls_after.jsonl")
def sig(r): return (r["decision"], r["index"], r["answer"], r["reason"], r["detail"])
cats = {"answer->escalate": [], "escalate->answer": [], "answer value/index changed": [], "escalate reason/detail changed": []}
nondet = 0
only_b = sorted(set(b) - set(a)); only_a = sorted(set(a) - set(b))
for k in sorted(set(b) & set(a)):
    sb = {sig(r) for r in b.get(k, [])}; sa = {sig(r) for r in a.get(k, [])}
    if len(sb) > 1 or len(sa) > 1: nondet += 1
    if sb == sa: continue
    x, y = sorted(sb)[0], sorted(sa)[0]
    if x[0] == "answer" and y[0] == "escalate": cats["answer->escalate"].append((k, x, y))
    elif x[0] == "escalate" and y[0] == "answer": cats["escalate->answer"].append((k, x, y))
    elif x[0] == "answer": cats["answer value/index changed"].append((k, x, y))
    else: cats["escalate reason/detail changed"].append((k, x, y))
out = [f"# calls_before.jsonl lines: {sum(len(v) for v in b.values())} distinct (frame,q,opts): {len(b)}",
       f"# calls_after.jsonl  lines: {sum(len(v) for v in a.values())} distinct (frame,q,opts): {len(a)} same key set: {set(a)==set(b)}",
       f"# keys only in before: {len(only_b)} / only in after: {len(only_a)} (a test of the new file that fails before the fix stops at its first failed assert, so a later question of the same test is not asked)",
       f"# keys with more than one distinct result inside one run: {nondet}",
       "# counts: " + str({k: len(v) for k, v in cats.items()})]
for k in only_b: out.append(f"   only-before {k[0]} | {k[1]} | {k[2]}")
for k in only_a: out.append(f"   only-after  {k[0]} | {k[1]} | {k[2]}")
for c, v in cats.items():
    out.append(f"== {c} {len(v)}")
    for k, x, y in v:
        tests = sorted({r["test"] for r in a.get(k, []) + b.get(k, [])})
        out.append(f"   [{','.join(tests)}] {k[0]} | {k[1]} | {k[2]} | {x[:3] if x[0]=='answer' else x} -> {y[:3] if y[0]=='answer' else y}")
open(os.path.join(here, "calls_changes.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out[:4]))
