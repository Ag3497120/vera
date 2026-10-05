"""K342: before と after の ask 出力を問ごとに比べる（マスクした全文）。差のある問を TSV に。
使い方: k342_compare.py OUT.tsv NAME:before.jsonl:after.jsonl[:before2.jsonl] ..."""
import json, sys
from pathlib import Path
KEYS = set(Path(__file__).with_name("nondeterministic_keys.txt").read_text().split())
def load(p):
    return {json.loads(l)["id"]: json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()}
def mask(o):
    if isinstance(o, dict): return {k: (0 if k in KEYS else mask(v)) for k, v in o.items()}
    if isinstance(o, list): return [mask(v) for v in o]
    return o
def parse(r):
    try: return json.loads(r["stdout"])
    except ValueError: return r["stdout"]
def mb(r): return (r["exit_code"], json.dumps(mask(parse(r)), ensure_ascii=False, sort_keys=True))
def summ(r):
    o = parse(r)
    if not isinstance(o, dict): return ("", "", "")
    return (str(o.get("verdict")), json.dumps(o.get("values"), ensure_ascii=False), str(o.get("text")))
rows = ["set\tid\tbefore_verdict\tbefore_values\tbefore_text\tafter_verdict\tafter_values\tafter_text\tdirection"]
for spec in sys.argv[2:]:
    parts = spec.split(":"); name, b, a = parts[:3]
    B, Af = load(b), load(a)
    ctrl = load(parts[3]) if len(parts) > 3 else None
    nd = sum(1 for k in B if ctrl and k in ctrl and mb(B[k]) != mb(ctrl[k]))
    diff = [k for k in B if mb(B[k]) != mb(Af[k])]
    print(f"{name}: n={len(B)} missing_after={len(set(B)-set(Af))} masked_differ={len(diff)} control_before_vs_before2_differ={nd if ctrl else 'n/a'}")
    for k in diff:
        sb, sa = summ(B[k]), summ(Af[k])
        # direction: values after contain before as a strict prefix of the full written form
        vb, va = json.loads(sb[1] or "null"), json.loads(sa[1] or "null")
        if sb[0] == sa[0] == "ANSWER" and isinstance(vb, list) and isinstance(va, list) and len(vb) == len(va) and all(y != x and y.startswith(x) for x, y in zip(vb, va)):
            d = "短縮が直った"
        elif sb == sa:
            d = "values・text 同じ（ほかの欄だけ違う）"
        else:
            d = "それ以外"
        rows.append("\t".join([name, k, *sb, *sa, d]))
Path(sys.argv[1]).write_text("\n".join(rows) + "\n", encoding="utf-8")
