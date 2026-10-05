"""X3: assemble x3_law.json from the reports of the steps (nothing is typed by hand) and draw the 60 words to look at.
usage: assemble_x3.py [SUFFIX]   (cwd = the tree; SUFFIX "" = the first run (def_min 1), "_k2" = the repaired run (thresholds 2): reads law<SUFFIX>, control<SUFFIX>, writes x3_law<SUFFIX>.json ...)"""
import json
import os
import random
import re
import subprocess
import sys

SUF = sys.argv[1] if len(sys.argv) > 1 else ""
W = os.getcwd()
A = os.path.join(W, "artifacts/w12-c1")
B = os.path.join(W, "build/initial-layers")
PY = sys.executable
sys.path.insert(0, W)
from verantyx import placement_layer as PL  # noqa: E402
from verantyx import coarse_place  # noqa: E402


def j(p):
    return json.load(open(os.path.join(A, p), encoding="utf-8"))


def timing(log):
    t = open(log, encoding="utf-8").read()
    m = re.search(r"([\d.]+)\s+real", t)
    r = re.search(r"(\d+)\s+maximum resident set size", t)
    return {"seconds_real": float(m.group(1)) if m else None, "max_rss_bytes": int(r.group(1)) if r else None}


def counts(d):
    import sqlite3
    con = sqlite3.connect("file:%s/placement/placement.sqlite?mode=ro" % os.path.join(B, d), uri=True)
    rows = con.execute("SELECT state, COALESCE(origin,''), COUNT(*) FROM headwords GROUP BY 1,2").fetchall()
    con.close()
    man = json.load(open(os.path.join(B, d, "placement/manifest.json")))
    return {"headwords_by_state_origin": {"%s/%s" % (s, o): n for s, o, n in rows}, "content_sha256": man["content_sha256"], "config_sha256": man["config_sha256"],
            "builder_sha256": man["builder_sha256"], "args_generated_flags": {k: v for k, v in man["args"].items() if k.startswith("generated") or k.startswith("role") or k in ("frozen", "compare_to")},
            "families": man["args"]["families"]}


out = {"law": {"domain_db": j("x3_domain_db_law.json"), "placement": counts("law" + SUF), "builder": timing(os.path.join(B, "law%s/build.log" % SUF)), "layer": j("x3_law%s_layer.json" % SUF)},
       "control": {"domain_db": j("x3_domain_db_control.json"), "placement": counts("control" + SUF), "builder": timing(os.path.join(B, "control%s/build.log" % SUF)), "layer": j("x3_control%s_layer.json" % SUF)}}
r = subprocess.run([PY, "tools/build_initial_layers.py", "capacity", "--layer", os.path.join(B, "law%s/law%s.sqlite" % (SUF, SUF)), "--layer", os.path.join(B, "control%s/control%s.sqlite" % (SUF, SUF)), "--report", os.path.join(A, "x3_capacity%s.json" % SUF)],
                   capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=W, PYTHONDONTWRITEBYTECODE="1"))
out["capacity"] = j("x3_capacity%s.json" % SUF)
for d in ("law", "control"):
    g = out[d]["layer"]["growth"]
    out[d]["summary"] = {"layer_words_direct": g["words"]["direct"] if isinstance(g, dict) and "words" in g else None, "written": out[d]["layer"]["written"],
                         "not_written": out[d]["layer"]["not_written"], "domain_direct_candidates": out[d]["layer"]["domain_direct_candidates"]}
out["law_vs_control_note"] = ("a law layer of about the size of the control layer means the layer is an effect of narrowing the material to a subset of general_qa, not of the law scene (K409; vera1's granularity.control reasoning)")
json.dump(out, open(os.path.join(A, "x3_law%s.json" % (SUF or "_k1")), "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
# the 60 words (random.Random(20261004).sample(sorted(direct words), min(60, n))); the judgement columns are filled by hand afterwards
lay = PL.open_layer(os.path.join(B, "law%s/law%s.sqlite" % (SUF, SUF)))[0]
words = {}
for e in lay.all_entries():
    words.setdefault(e["word"], e["type"])
pick = random.Random(20261004).sample(sorted(words), min(60, len(words)))
R9 = os.environ["VERA_PLACEMENT"]
with open(os.path.join(A, "x3_sample60%s.tsv" % SUF), "w", encoding="utf-8") as fo:
    fo.write("# NOT ground truth: a look by the implementer at the words drawn with random.Random(20261004).sample(sorted(direct words of the law layer), min(60, n)). judgement (correct / doubtful / wrong) and reason were filled by hand.\n")
    fo.write("word\ttype\tr9_state\tr9_top\tjudgement\treason\n")
    for w in pick:
        a = coarse_place.query(w, placement=R9, layer=False)
        fo.write("%s\t%s\t%s\t%s\t\t\n" % (w, words[w], a.get("state"), ",".join(a.get("top") or [])))
print(json.dumps({"law": out["law"]["summary"], "control": out["control"]["summary"], "capacity": out["capacity"]["layers"]}, ensure_ascii=False))
